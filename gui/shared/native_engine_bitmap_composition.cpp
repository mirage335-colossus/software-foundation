// SPDX-License-Identifier: CC0-1.0
#include "native_engine_bitmap_composition.hpp"

#include <algorithm>
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
struct Ingress {
    unsigned& depth;
    explicit Ingress(unsigned& value) : depth(value) { ++depth; }
    ~Ingress() { --depth; }
};
constexpr auto close_budget = std::chrono::seconds(10);
constexpr auto close_poll = std::chrono::milliseconds(10);
constexpr unsigned settlement_turns = 8;
}

struct NativeEngineBitmapComposition::Impl {
    struct Extent {
        std::int64_t width{}, height{};
        bool operator==(const Extent&) const = default;
    };
    gui::Adapter& adapter;
    const std::shared_ptr<appended::EngineOwner> owner;
    appended::NativeEngineDriver& driver;
    const PostOwnerWake post;
    const std::thread::id thread{std::this_thread::get_id()};
    std::unique_ptr<EnginePrimaryRegionApplication> application;
    std::optional<Extent> pixels, applied_pixels;
    std::optional<Clock::time_point> last_turn, close_limit, close_next;
    std::atomic<bool> close_requested{}, wake_pending{}, advance_pending{}, timed_out{}, close_finished{};
    std::atomic<unsigned> posting{};
    bool foreground_requested{true}, manual_service_requested{}, facts_pending{true};
    bool service_applied{}, resize_release{}, close_sent{}, active{};
    unsigned ingress{}, continuations{};
    std::uint64_t epoch{1}, facts_version{1}, observed_application_epoch{};

    Impl(gui::Adapter& target, std::shared_ptr<appended::EngineOwner> kernel,
            appended::NativeEngineDriver& engine, PostOwnerWake notify)
        : adapter(target), owner(std::move(kernel)), driver(engine), post(std::move(notify)) {
        if (!owner || driver.owner() != owner || !owner->configured() || owner->closed() ||
            !owner->identity().application_instance || owner->callback_depth() ||
            (driver.state() != appended::NativeEngineState::ready &&
             driver.state() != appended::NativeEngineState::waiting_document))
            throw std::invalid_argument("Native bitmap composition requires its started Driver and same configured Owner");
    }
    void check_thread() const {
        if (thread != std::this_thread::get_id())
            throw std::logic_error("Native bitmap composition requires its serialized owner");
    }
    bool terminal() const noexcept {
        return driver.state() == appended::NativeEngineState::process_exit_required;
    }
    bool inactive() const noexcept {
        return hard_inactive() ||
            driver.state() == appended::NativeEngineState::detached;
    }
    bool hard_inactive() const noexcept {
        return terminal() || timed_out.load(std::memory_order_acquire);
    }
    bool complete() const noexcept {
        return !hard_inactive() && driver.state() == appended::NativeEngineState::detached &&
            application->shutdown_complete();
    }
    bool barrier() const noexcept {
        return active || ingress || posting.load(std::memory_order_acquire) || owner->callback_depth();
    }
    bool held() const noexcept {
        return !pixels || !foreground_requested || manual_service_requested || service_applied || facts_pending || application->owned_service_pending();
    }
    bool admission_closed() const noexcept {
        return close_requested.load(std::memory_order_acquire) || inactive() || held() || adapter.closed();
    }
    void invalidate() noexcept {
        if (epoch == std::numeric_limits<std::uint64_t>::max()) close_requested.store(true, std::memory_order_release);
        else ++epoch;
    }
    void observe_application() noexcept {
        if (observed_application_epoch != application->input_epoch()) {
            observed_application_epoch = application->input_epoch(); invalidate();
        }
    }
    void post_only() noexcept {
        if (!post) return;
        posting.fetch_add(1, std::memory_order_acq_rel);
        try { post(); } catch (...) {} // Never unwind through a worker C callback.
        posting.fetch_sub(1, std::memory_order_acq_rel);
    }
    void wake() noexcept {
        if (hard_inactive() || close_finished.load(std::memory_order_acquire) ||
            wake_pending.exchange(true, std::memory_order_acq_rel)) return;
        post_only();
    }
    void changed() noexcept {
        if (facts_version == std::numeric_limits<std::uint64_t>::max())
            close_requested.store(true, std::memory_order_release);
        else ++facts_version;
        facts_pending = true; invalidate(); wake();
    }
    void apply_facts() {
        if (!facts_pending && !resize_release) return;
        const auto applying = facts_version;
        const auto selected_pixels = pixels;
        const bool base_hold = !selected_pixels || !foreground_requested || manual_service_requested;
        // A changed transform retires old physical ownership before it can be
        // used again. The following normal turn releases only this resize hold.
        const bool resize = !resize_release && applied_pixels && selected_pixels && applied_pixels != selected_pixels;
        const bool next_hold = base_hold || resize;
        if (service_applied != next_hold) {
            application->set_owned_service_active(next_hold);
            service_applied = next_hold;
            if (!next_hold) advance_pending.store(true, std::memory_order_release);
        }
        applied_pixels = selected_pixels;
        resize_release = resize;
        facts_pending = facts_version != applying;
        observe_application();
    }
    void begin_close(Clock::time_point now) noexcept {
        if (close_limit) return;
        close_limit = now > Clock::time_point::max() - close_budget ? Clock::time_point::max() : now + close_budget;
    }
    void finish_turn(Clock::time_point now) noexcept {
        if (complete()) {
            close_finished.store(true, std::memory_order_release); close_next.reset(); return;
        }
        if (close_requested.load(std::memory_order_acquire))
            close_next = now > Clock::time_point::max() - close_poll ? Clock::time_point::max() : now + close_poll;
        else close_next.reset();
    }
    void tick(Clock::time_point now) {
        check_thread();
        if (barrier() || hard_inactive() || close_finished.load(std::memory_order_acquire)) return;
        Activity guard(active);
        last_turn = now;
        if (complete()) { finish_turn(now); return; }
        if (wake_pending.exchange(false, std::memory_order_acq_rel)) continuations = settlement_turns;
        if (continuations) --continuations;
        if (adapter.closed() || driver.state() == appended::NativeEngineState::detached)
            close_requested.store(true, std::memory_order_release);
        const bool closing = close_requested.load(std::memory_order_acquire);
        if (closing) {
            begin_close(now);
            if (now >= *close_limit) { timed_out.store(true, std::memory_order_release); return; }
            application->shutdown();
        } else apply_facts();
        if (driver.state() == appended::NativeEngineState::detached) {
            // The native owner is finished. Only a retained known completion,
            // its checked publication and local shutdown may drain here.
            application->tick(); observe_application(); finish_turn(now); return;
        }
        const auto applied_version = facts_version;
        // No provider entry occurs during either App phase. In particular,
        // close must continue its real native9/editor retirement settlement.
        application->tick(); observe_application();
        if (inactive()) return;
        if (!closing && (facts_pending || applied_version != facts_version)) { wake(); return; }
        if (adapter.closed()) close_requested.store(true, std::memory_order_release);
        if (close_requested.load(std::memory_order_acquire)) {
            begin_close(now); application->shutdown();
            if (!close_sent) { close_sent = true; driver.request_close(); }
        } else if (!held() && !application->presentation_pending() && !owner->native_effect() &&
                   advance_pending.exchange(false, std::memory_order_acq_rel)) {
            driver.request_advance();
        }
        driver.tick(now);
        if (terminal()) return; // Preserve the exact uncertain attempt intact.
        application->tick(); observe_application();
        finish_turn(now);
        // App settlement can stage the next bounded lane head without a native
        // wake. A finite continuation budget covers that pipeline; publication
        // debt alone never replenishes it or continuously requests ADVANCE.
        if (!close_requested.load(std::memory_order_acquire) && (continuations || resize_release) && !inactive()) post_only();
    }
};

NativeEngineBitmapComposition::NativeEngineBitmapComposition(gui::Adapter& adapter,
        std::shared_ptr<appended::EngineOwner> owner, appended::NativeEngineDriver& driver,
        const appended::engine_document_actions::EngineDocumentActionsProfileFacts& facts,
        BoundEngineEditorPort port, PostOwnerWake post)
    : impl_(std::make_unique<Impl>(adapter,std::move(owner),driver,std::move(post))) {
    if (!impl_->owner->document_actions_enabled() ||
        !appended::engine_document_actions::document_actions_profile_agrees(facts,impl_->owner->document_actions_profile()))
        throw std::invalid_argument("Native bitmap composition requires exact document-actions facts");
    impl_->application = std::make_unique<EnginePrimaryRegionApplication>(adapter,impl_->owner,facts,std::move(port));
    impl_->observe_application();
}
NativeEngineBitmapComposition::NativeEngineBitmapComposition(gui::Adapter& adapter,
        std::shared_ptr<appended::EngineOwner> owner, appended::NativeEngineDriver& driver,
        const appended::engine_document_actions::EngineDocumentActionsProfileFacts& facts,
        ReadOnlyEngineBitmap tag, PostOwnerWake post)
    : impl_(std::make_unique<Impl>(adapter,std::move(owner),driver,std::move(post))) {
    if (!impl_->owner->document_actions_enabled() ||
        !appended::engine_document_actions::document_actions_profile_agrees(facts,impl_->owner->document_actions_profile()))
        throw std::invalid_argument("Native bitmap composition requires exact document-actions facts");
    impl_->application = std::make_unique<EnginePrimaryRegionApplication>(adapter,impl_->owner,facts,tag);
    impl_->observe_application();
}
NativeEngineBitmapComposition::NativeEngineBitmapComposition(gui::Adapter& adapter,
        std::shared_ptr<appended::EngineOwner> owner, appended::NativeEngineDriver& driver,
        const appended::engine_document::EngineDocumentProfileFacts& facts,
        ReadOnlyEngineBitmap, PostOwnerWake post)
    : impl_(std::make_unique<Impl>(adapter,std::move(owner),driver,std::move(post))) {
    if (!impl_->owner->document_enabled() || facts.kind != appended::engine_document::ProfileKind::pixel ||
        impl_->owner->document_actions_enabled() || impl_->owner->editor_enabled() ||
        !appended::engine_document::document_profile_agrees(facts,impl_->owner->document_profile()))
        throw std::invalid_argument("Native bitmap composition requires exact observation-only pixel facts");
    impl_->application = std::make_unique<EnginePrimaryRegionApplication>(adapter,impl_->owner,facts,nullptr);
    impl_->observe_application();
}
NativeEngineBitmapComposition::~NativeEngineBitmapComposition() {
    if (!impl_) return;
    shutdown();
    // The root port's publisher handle must already be disarmed before its
    // renderer dies. Retention keeps unknown metadata/captures, not authority
    // to call a dead renderer or to attempt another provider export.
    if (impl_->thread != std::this_thread::get_id() || impl_->barrier() || !impl_->complete())
        (void)impl_.release();
}
void NativeEngineBitmapComposition::drawable_pixels(std::int64_t width, std::int64_t height) {
    impl_->check_thread();
    if (impl_->close_requested.load(std::memory_order_acquire) || impl_->inactive()) return;
    std::optional<Impl::Extent> next;
    if (width > 0 && height > 0 && width <= std::numeric_limits<std::int32_t>::max() &&
        height <= std::numeric_limits<std::int32_t>::max()) next = Impl::Extent{width,height};
    if (impl_->pixels == next) return;
    impl_->pixels = next; impl_->changed();
}
void NativeEngineBitmapComposition::foreground(bool value) {
    impl_->check_thread();
    if (impl_->close_requested.load(std::memory_order_acquire) || impl_->inactive() || impl_->foreground_requested == value) return;
    impl_->foreground_requested = value; impl_->changed();
}
void NativeEngineBitmapComposition::set_owned_service_active(bool value) {
    impl_->check_thread();
    if (impl_->close_requested.load(std::memory_order_acquire) || impl_->inactive() || impl_->manual_service_requested == value) return;
    impl_->manual_service_requested = value; impl_->changed();
}
bool NativeEngineBitmapComposition::owned_service_ready() const noexcept {
    return impl_->thread==std::this_thread::get_id() && !impl_->inactive() && !impl_->barrier() &&
        impl_->manual_service_requested && impl_->service_applied && impl_->application->owned_service_ready();
}
void NativeEngineBitmapComposition::request_frame() noexcept {
    if (impl_->inactive() || impl_->close_requested.load(std::memory_order_acquire)) return;
    impl_->advance_pending.store(true,std::memory_order_release); impl_->wake();
}
void NativeEngineBitmapComposition::wake() noexcept { impl_->wake(); }
void NativeEngineBitmapComposition::handle(gui::Event event) {
    impl_->check_thread();
    if (std::holds_alternative<gui::CloseEvent>(event)) { shutdown(); return; }
    if (impl_->admission_closed() || impl_->ingress || impl_->owner->callback_depth()) return;
    Ingress guard(impl_->ingress); impl_->application->handle(std::move(event)); impl_->observe_application(); impl_->wake();
}
bool NativeEngineBitmapComposition::queue_compiled_region(EngineRegionComposition value) {
    impl_->check_thread();
    if (impl_->admission_closed() || impl_->ingress) return false;
    Ingress guard(impl_->ingress); const auto accepted = impl_->application->queue_compiled_region(std::move(value));
    if (accepted) impl_->wake();
    return accepted;
}
std::optional<CompiledRegionEvent> NativeEngineBitmapComposition::take_compiled_event() {
    impl_->check_thread();
    if (impl_->admission_closed() || impl_->barrier()) return {};
    Ingress guard(impl_->ingress); return impl_->application->take_compiled_event();
}
std::uint64_t NativeEngineBitmapComposition::compiled_region_published_revision() const noexcept {
    return impl_->thread == std::this_thread::get_id() ? impl_->application->compiled_region_published_revision() : 0;
}
void NativeEngineBitmapComposition::tick(Clock::time_point now) { impl_->tick(now); }
void NativeEngineBitmapComposition::retry_presentation() {
    impl_->check_thread(); if (impl_->barrier() || impl_->inactive()) return;
    Activity guard(impl_->active); impl_->application->retry_presentation(); impl_->observe_application(); impl_->wake();
}
void NativeEngineBitmapComposition::qualify(const std::function<void()>& present) {
    impl_->check_thread(); if (impl_->barrier() || impl_->inactive()) return;
    Activity guard(impl_->active); impl_->application->qualify(present); impl_->observe_application(); impl_->wake();
}
void NativeEngineBitmapComposition::shutdown() noexcept {
    if (!impl_ || impl_->hard_inactive() || impl_->close_finished.load(std::memory_order_acquire)) return;
    impl_->close_requested.store(true,std::memory_order_release); impl_->wake();
}
const gui::Snapshot& NativeEngineBitmapComposition::view() const noexcept { return impl_->application->view(); }
std::uint64_t NativeEngineBitmapComposition::input_epoch() const noexcept { return impl_->epoch; }
bool NativeEngineBitmapComposition::presentation_pending() const noexcept {
    return !impl_->inactive() && (impl_->facts_pending || impl_->resize_release || impl_->application->presentation_pending());
}
bool NativeEngineBitmapComposition::frame_ready() const noexcept {
    if (impl_->admission_closed() || impl_->application->presentation_pending() || impl_->owner->native_effect()) return false;
    const auto& snapshot = impl_->application->view();
    const auto& frame = impl_->owner->frame();
    return frame && frame->identity == impl_->owner->identity() && frame->frame_revision && !frame->rgba.empty() &&
        std::any_of(snapshot.widgets.begin(), snapshot.widgets.end(), [&](const auto& widget) {
            return widget.spec.key.id == EngineRegionComposition::engine_id && widget.spec.kind == gui::Kind::bitmap &&
                widget.state.bitmap.revision == frame->frame_revision;
        });
}
bool NativeEngineBitmapComposition::closed() const noexcept {
    return impl_->close_requested.load(std::memory_order_acquire) || impl_->inactive() || impl_->adapter.closed();
}
bool NativeEngineBitmapComposition::close_complete() const noexcept {
    // Owner-thread validation precedes every mutable App/Owner metadata read.
    return impl_->thread == std::this_thread::get_id() && !impl_->barrier() && impl_->complete();
}
bool NativeEngineBitmapComposition::close_timed_out() const noexcept { return impl_->timed_out.load(std::memory_order_acquire); }
appended::NativeEngineState NativeEngineBitmapComposition::native_state() const noexcept { return impl_->driver.state(); }
std::optional<NativeEngineBitmapComposition::Clock::time_point> NativeEngineBitmapComposition::deadline() const noexcept {
    if (impl_->hard_inactive() || impl_->close_finished.load(std::memory_order_acquire)) return {};
    auto result = impl_->driver.deadline();
    const auto include = [&](Clock::time_point value) { if (!result || value < *result) result = value; };
    if (impl_->wake_pending.load(std::memory_order_acquire) ||
        (!impl_->close_requested.load(std::memory_order_acquire) &&
         (impl_->facts_pending || impl_->resize_release || impl_->continuations)))
        include(impl_->last_turn.value_or(Clock::time_point::min()));
    if (impl_->close_limit) include(*impl_->close_limit);
    if (impl_->close_next) include(*impl_->close_next);
    return result;
}
void NativeEngineBitmapComposition::surface_connected(gui_surface::Capabilities value) {
    impl_->check_thread(); if (impl_->inactive() || impl_->close_requested.load() || impl_->ingress) return;
    Ingress guard(impl_->ingress); impl_->application->surface_connected(std::move(value)); impl_->wake();
}
void NativeEngineBitmapComposition::surface_input(gui_surface::AcceptedEvent value) {
    impl_->check_thread(); if (impl_->admission_closed() || impl_->ingress || impl_->owner->callback_depth()) return;
    Ingress guard(impl_->ingress); impl_->application->surface_input(std::move(value)); impl_->observe_application(); impl_->wake();
}
void NativeEngineBitmapComposition::surface_revoked(gui_surface::Revocation value) {
    impl_->check_thread(); if (impl_->inactive() || impl_->close_requested.load() || impl_->ingress) return;
    Ingress guard(impl_->ingress); impl_->application->surface_revoked(std::move(value)); impl_->observe_application(); impl_->wake();
}
std::optional<std::uint64_t> NativeEngineBitmapComposition::editor_submit(native_editor::Packet value) {
    impl_->check_thread(); if (impl_->admission_closed() || impl_->ingress || impl_->owner->callback_depth()) return {};
    Ingress guard(impl_->ingress); auto result = impl_->application->editor_submit(std::move(value));
    if (result) impl_->wake();
    return result;
}
std::optional<std::uint64_t> NativeEngineBitmapComposition::editor_revoke(native_editor::Revocation value) {
    impl_->check_thread();
    if (impl_->inactive() || impl_->close_requested.load() || impl_->ingress || impl_->owner->callback_depth()) return {};
    Ingress guard(impl_->ingress); auto result = impl_->application->editor_revoke(std::move(value));
    if (result) impl_->wake();
    return result;
}
std::optional<native_editor::EditorCompletion> NativeEngineBitmapComposition::editor_take(std::uint64_t ticket) {
    impl_->check_thread();
    if (impl_->hard_inactive() || impl_->close_finished.load(std::memory_order_acquire) || impl_->barrier()) return {};
    Ingress guard(impl_->ingress); auto result = impl_->application->editor_take(ticket);
    if (result) impl_->wake();
    return result;
}
void NativeEngineBitmapComposition::editor_resync() {
    impl_->check_thread(); if (impl_->admission_closed() || impl_->ingress || impl_->owner->callback_depth()) return;
    Ingress guard(impl_->ingress); impl_->application->editor_resync(); impl_->wake();
}
std::optional<gui::ServiceRequest> NativeEngineBitmapComposition::next_service() {
    impl_->check_thread();
    if (impl_->inactive() || impl_->close_requested.load(std::memory_order_acquire) ||
        impl_->adapter.closed() || impl_->barrier()) return {};
    Ingress guard(impl_->ingress);
    auto result=impl_->application->next_service();
    if (result || impl_->application->owned_service_pending()) impl_->wake();
    return result;
}
bool NativeEngineBitmapComposition::complete_service(gui::ServiceResult value) {
    impl_->check_thread();
    // Like metadata editor Take, a matching already-offered completion may
    // drain after native detach. Fresh offers/exports remain inadmissible.
    if (impl_->hard_inactive() || impl_->close_finished.load(std::memory_order_acquire) || impl_->barrier()) return false;
    Ingress guard(impl_->ingress);
    // Close intent may arrive between normal turns. Mark the shared root before
    // it consumes metadata, so a detached or closing guest is never re-entered.
    if (impl_->close_requested.load(std::memory_order_acquire) ||
        impl_->driver.state()==appended::NativeEngineState::detached) impl_->application->shutdown();
    const bool accepted=impl_->application->complete_service(std::move(value));
    if (accepted) impl_->wake();
    return accepted;
}
} // namespace foundation::ui
