#include "native_engine_document_composition.hpp"
#include "appended_engine_document_application.hpp"

#include <atomic>
#include <limits>
#include <stdexcept>
#include <thread>
#include <utility>

namespace foundation::ui {
namespace {
struct Activity {
    bool& active;
    explicit Activity(bool& value) : active(value) { active = true; }
    ~Activity() { active = false; }
};
constexpr auto observation_interval = std::chrono::milliseconds(250);
}

struct NativeEngineDocumentComposition::Impl {
    // Value-only lifecycle visibility. The existing presenter sees a close
    // queued by an Adapter callback before admitting more work, while its
    // actual shutdown still runs after that callback returns.
    struct Bridge final : gui::Adapter {
        Impl& composition;
        explicit Bridge(Impl& owner) : composition(owner) {}
        void present(gui::Snapshot value) override { composition.adapter.present(std::move(value)); }
        gui::Size measure_text(const gui::TextMeasureRequest& value) const override { return composition.adapter.measure_text(value); }
        gui::Availability resolved_availability(const gui::WidgetKey& key) const override { return composition.adapter.resolved_availability(key); }
        std::optional<gui::WidgetKey> focused() const override { return composition.adapter.focused(); }
        bool focus(std::optional<gui::WidgetKey> key) override { return composition.adapter.focus(std::move(key)); }
        bool focus_next(bool reverse) override { return composition.adapter.focus_next(reverse); }
        void scroll(const gui::WidgetKey& key, gui::Point value) override { composition.adapter.scroll(key,value); }
        gui::Point scroll_offset(const gui::WidgetKey& key) const override { return composition.adapter.scroll_offset(key); }
        gui::TextSelection text_selection(const gui::WidgetKey& key) const override { return composition.adapter.text_selection(key); }
        void text_selection(const gui::WidgetKey& key, gui::TextSelection value) override { composition.adapter.text_selection(key,value); }
        bool open_popup(const gui::WidgetKey& key) override { return composition.adapter.open_popup(key); }
        void close_popup(const gui::WidgetKey& key) override { composition.adapter.close_popup(key); }
        void invalidate(const gui::WidgetKey& key, gui::PixelRect value) override { composition.adapter.invalidate(key,value); }
        bool closed() const override { return composition.close_requested.load(std::memory_order_acquire) || composition.adapter.closed(); }
        void close() override { composition.adapter.close(); }
    };
    gui::Adapter& adapter;
    const std::shared_ptr<appended::EngineOwner> owner;
    appended::NativeEngineDriver& driver;
    const PostOwnerWake post;
    const std::thread::id thread{std::this_thread::get_id()};
    Bridge bridge;
    std::unique_ptr<AppendedEngineDocumentApplication> application;
    gui::Snapshot suspended;
    std::optional<DocumentViewport> cells, applied_cells;
    std::optional<Clock::time_point> observation_deadline;
    std::atomic<bool> close_requested{}, wake_pending{};
    std::atomic<unsigned> scheduling{};
    bool foreground_requested{true}, facts_pending{true}, active{}, observation_clock_exhausted{};
    bool owned_service_active{}, owned_service_offered{};
    std::uint64_t epoch{1}, observed_application_epoch{}, facts_version{1};
    const std::string empty_error;

    Impl(gui::Adapter& value, std::shared_ptr<appended::EngineOwner> kernel,
            appended::NativeEngineDriver& engine, PostOwnerWake notify)
        : adapter(value), owner(std::move(kernel)), driver(engine), post(std::move(notify)), bridge(*this) {
        // Identity agreement precedes even construction of the presenter.
        const bool pixel = owner && owner->document_enabled() &&
            appended::engine_document::document_profile_valid(owner->document_profile()) &&
            owner->document_profile().kind == appended::engine_document::ProfileKind::pixel;
        const bool actions = owner && owner->document_actions_enabled() &&
            appended::engine_document_actions::document_actions_profile_valid(owner->document_actions_profile());
        if (!owner || driver.owner() != owner || !owner->configured() || owner->closed() ||
            !owner->identity().application_instance || pixel == actions ||
            (driver.state() != appended::NativeEngineState::ready &&
             driver.state() != appended::NativeEngineState::waiting_document))
            throw std::invalid_argument("Native document composition requires its started Driver and same configured Owner");
        suspended.title = "Appended document suspended";
    }
    void check_thread() const {
        if (thread != std::this_thread::get_id())
            throw std::logic_error("Native document composition requires its serialized owner");
    }
    bool terminal() const noexcept {
        return driver.state() == appended::NativeEngineState::process_exit_required;
    }
    bool callback_barrier() const noexcept {
        return active || scheduling.load(std::memory_order_acquire) || owner->callback_depth();
    }
    bool gated() const noexcept {
        return close_requested.load(std::memory_order_acquire) || terminal() || !cells ||
            !foreground_requested || facts_pending || owned_service_active;
    }
    bool observation_eligible() const noexcept {
        const auto state = driver.state();
        return !gated() && application && !application->closed() &&
            (state == appended::NativeEngineState::ready || state == appended::NativeEngineState::waiting_document);
    }
    void arm_observation(Clock::time_point now) noexcept {
        // A caller-supplied fake clock can reach its representable end. Do not
        // wrap the deadline or leave an expired value selecting a busy loop.
        if (now > Clock::time_point::max() - observation_interval) {
            observation_clock_exhausted = true;
            observation_deadline.reset();
        } else observation_deadline = now + observation_interval;
    }
    void observe_document(Clock::time_point now) {
        if (!observation_eligible()) { observation_deadline.reset(); return; }
        if (observation_clock_exhausted) return;
        if (!observation_deadline) { arm_observation(now); return; }
        if (now < *observation_deadline) return;
        // Advance before the hint. The existing presenter coalesces it behind
        // native work, modal drafts and exact presentation retries; none of
        // those barriers may turn a past observation deadline into a spin.
        arm_observation(now);
        application->request_observation();
    }
    void invalidate() noexcept {
        if (epoch == std::numeric_limits<std::uint64_t>::max()) close_requested.store(true, std::memory_order_release);
        else ++epoch;
    }
    void observe_application() noexcept {
        if (application && observed_application_epoch != application->input_epoch()) {
            observed_application_epoch = application->input_epoch(); invalidate();
        }
    }
    void wake() noexcept {
        if (terminal() || wake_pending.exchange(true, std::memory_order_acq_rel)) return;
        if (!post) return;
        scheduling.fetch_add(1, std::memory_order_acq_rel);
        try { post(); } catch (...) {} // A wake cannot unwind through a worker C callback.
        scheduling.fetch_sub(1, std::memory_order_acq_rel);
    }
    void apply_facts() {
        if (!facts_pending) return;
        // Adapter publication/measurement may synchronously enqueue newer
        // facts. Never mark that later version applied to this older snapshot.
        const auto applying = facts_version;
        const auto viewport = cells;
        const auto foreground = foreground_requested;
        if (viewport) {
            if (!application) {
                application = std::make_unique<AppendedEngineDocumentApplication>(bridge, owner, *viewport);
                applied_cells = viewport;
            } else if (applied_cells != viewport) {
                application->viewport(*viewport); applied_cells = viewport;
            }
        }
        if (application) {
            application->foreground(viewport.has_value() && foreground);
            application->set_owned_service_active(owned_service_active);
        }
        facts_pending = facts_version != applying;
        observe_application();
    }
    void tick(Clock::time_point now) {
        check_thread();
        if (callback_barrier() || terminal()) return;
        Activity guard(active);
        wake_pending.store(false, std::memory_order_release);
        if (close_requested.load(std::memory_order_acquire)) {
            driver.request_close();
            if (application) application->shutdown();
            if (!owned_service_offered) driver.tick(now);
            observe_application();
            return;
        }
        apply_facts();
        observe_document(now);
        if (application) application->tick();
        observe_application();
        // A new lifecycle fact queued by an Adapter callback must take its
        // safe publication turn before any later native effect can enter.
        if (facts_pending) return;
        if (close_requested.load(std::memory_order_acquire) || (application && application->closed())) {
            close_requested.store(true, std::memory_order_release); driver.request_close();
            if (application) application->shutdown();
        }
        // Preparation drained real metadata above. Once the UI was actually
        // offered, its matching completion is required before another export.
        if (owned_service_offered) return;
        driver.tick(now);
        // Uncertain provider entry is process-terminal. Keep the presenter and
        // its original evidence alive without shutdown, ACK or cleanup entry.
        if (terminal()) return;
        if (application) application->tick();
        observe_application();
        if (application && application->closed()) {
            close_requested.store(true, std::memory_order_release); driver.request_close();
        }
    }
};

NativeEngineDocumentComposition::NativeEngineDocumentComposition(gui::Adapter& adapter,
        std::shared_ptr<appended::EngineOwner> owner, appended::NativeEngineDriver& driver, PostOwnerWake post)
    : impl_(std::make_unique<Impl>(adapter, std::move(owner), driver, std::move(post))) {}
NativeEngineDocumentComposition::~NativeEngineDocumentComposition() {
    if (!impl_) return;
    shutdown();
    // Any unresolved close/uncertainty retains the complete bridge, presenter,
    // Owner and scheduling captures. No destructor invents a cleanup export or
    // destroys dependencies beneath retained work. The host exits the process.
    if (impl_->driver.state() != appended::NativeEngineState::detached ||
        impl_->thread != std::this_thread::get_id() || impl_->active ||
        impl_->scheduling.load(std::memory_order_acquire) || impl_->owner->callback_depth()) (void)impl_.release();
}
void NativeEngineDocumentComposition::drawable_cells(std::int64_t columns, std::int64_t rows) {
    impl_->check_thread();
    std::optional<DocumentViewport> value;
    if (columns > 0 && columns <= 500 && rows > 0 && rows <= 200)
        value = DocumentViewport{static_cast<std::size_t>(columns), static_cast<std::size_t>(rows)};
    if (impl_->cells == value) return;
    impl_->cells = value; impl_->facts_pending = true; ++impl_->facts_version; impl_->invalidate(); impl_->wake();
    impl_->observation_deadline.reset();
}
void NativeEngineDocumentComposition::foreground(bool value) {
    impl_->check_thread();
    if (impl_->foreground_requested == value) return;
    impl_->foreground_requested = value; impl_->facts_pending = true; ++impl_->facts_version; impl_->invalidate(); impl_->wake();
    impl_->observation_deadline.reset();
}
void NativeEngineDocumentComposition::set_owned_service_active(bool value) {
    impl_->check_thread();
    if (impl_->owned_service_active==value) return;
    impl_->owned_service_active=value; impl_->facts_pending=true;
    ++impl_->facts_version; impl_->invalidate(); impl_->wake();
    impl_->observation_deadline.reset();
}
bool NativeEngineDocumentComposition::owned_service_ready() const noexcept {
    const auto state=impl_->driver.state();
    return impl_->thread==std::this_thread::get_id() && impl_->owned_service_active &&
        !impl_->facts_pending && !impl_->callback_barrier() && !impl_->close_requested.load() &&
        impl_->cells && impl_->foreground_requested && impl_->application &&
        (state==appended::NativeEngineState::ready || state==appended::NativeEngineState::waiting_document) &&
        impl_->application->owned_service_ready();
}
void NativeEngineDocumentComposition::set_owned_service_offered(bool value) {
    impl_->check_thread();
    if (value && !impl_->owned_service_offered && !owned_service_ready())
        throw std::logic_error("External GUI service requires settled document hold");
    impl_->owned_service_offered=value;
    if (!value) impl_->wake();
}
void NativeEngineDocumentComposition::wake() noexcept { impl_->wake(); }
void NativeEngineDocumentComposition::handle(gui::Event event) {
    impl_->check_thread();
    if (std::holds_alternative<gui::CloseEvent>(event)) { shutdown(); return; }
    if (impl_->callback_barrier() || impl_->gated() || !impl_->application) return;
    Activity guard(impl_->active);
    impl_->application->handle(std::move(event)); impl_->observe_application();
}
bool NativeEngineDocumentComposition::queue_selection(DocumentSelection selection) {
    impl_->check_thread();
    if (impl_->callback_barrier() || impl_->gated() || !impl_->application ||
        !impl_->owner->document_actions_enabled()) return false;
    Activity guard(impl_->active);
    const bool accepted = impl_->application->queue_selection(std::move(selection));
    impl_->observe_application();
    if (accepted) impl_->wake();
    return accepted;
}
void NativeEngineDocumentComposition::tick(Clock::time_point now) { impl_->tick(now); }
void NativeEngineDocumentComposition::retry_presentation() {
    impl_->check_thread();
    if (impl_->callback_barrier() || impl_->gated() || !impl_->application) return;
    Activity guard(impl_->active);
    impl_->application->retry_presentation(); impl_->observe_application();
}
void NativeEngineDocumentComposition::qualify(const std::function<void()>& present) {
    impl_->check_thread();
    if (impl_->callback_barrier() || impl_->terminal()) return;
    Activity guard(impl_->active);
    if (impl_->application && !impl_->gated()) impl_->application->retry_presentation();
    impl_->observe_application();
    if (present) present();
}
void NativeEngineDocumentComposition::shutdown() noexcept {
    if (!impl_ || impl_->terminal()) return;
    impl_->close_requested.store(true, std::memory_order_release); impl_->wake();
}
const gui::Snapshot& NativeEngineDocumentComposition::view() const noexcept {
    return impl_->application && !impl_->gated() ? impl_->application->view() : impl_->suspended;
}
std::uint64_t NativeEngineDocumentComposition::input_epoch() const noexcept { return impl_->epoch; }
bool NativeEngineDocumentComposition::presentation_pending() const noexcept {
    return !impl_->terminal() && !impl_->close_requested.load() &&
        (impl_->facts_pending || (impl_->application && impl_->application->presentation_pending()));
}
bool NativeEngineDocumentComposition::body_ready() const noexcept {
    return !impl_->gated() && impl_->application && impl_->application->body_ready();
}
bool NativeEngineDocumentComposition::modal_open() const noexcept {
    return !impl_->gated() && impl_->application && impl_->application->modal_open();
}
bool NativeEngineDocumentComposition::closed() const noexcept {
    return impl_->close_requested.load() || impl_->terminal() ||
        impl_->driver.state() == appended::NativeEngineState::detached ||
        (impl_->application && impl_->application->closed());
}
const std::string& NativeEngineDocumentComposition::last_error() const noexcept {
    return impl_->application ? impl_->application->last_error() : impl_->empty_error;
}
appended::NativeEngineState NativeEngineDocumentComposition::native_state() const noexcept { return impl_->driver.state(); }
std::optional<NativeEngineDocumentComposition::Clock::time_point> NativeEngineDocumentComposition::deadline() const noexcept {
    if (impl_->owned_service_offered) return {};
    auto result = impl_->driver.deadline();
    if (impl_->observation_eligible() && impl_->observation_deadline &&
        (!result || *impl_->observation_deadline < *result)) result = impl_->observation_deadline;
    return result;
}
std::optional<gui::ServiceRequest> NativeEngineDocumentComposition::next_service() { return {}; }
bool NativeEngineDocumentComposition::complete_service(gui::ServiceResult) { return false; }

} // namespace foundation::ui
