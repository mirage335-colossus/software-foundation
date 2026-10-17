#include "appended_application.hpp"
#include "appended_binary_view_model.hpp"

#include <foundation/appended/module.hpp>
#include <foundation/appended/startup.hpp>
#include <deque>
#include <limits>
#include <mutex>
#include <stdexcept>
#include <thread>

namespace foundation::ui {
namespace {
using namespace appended;
using Span = std::span<const std::uint8_t>;
constexpr std::size_t max_queued_events = 64;
std::uint64_t instance_generation(std::uint64_t explicit_generation) {
    if (explicit_generation) return explicit_generation;
    static std::mutex mutex;
    static GenerationSource generations;
    std::lock_guard lock(mutex);
    const auto generation = generations.next();
    if (!generation) throw std::overflow_error("Binary instance generations exhausted");
    return *generation;
}

Bytes self_module() {
    const auto package = appended::load_self();
    if (!package || !package->binary.present || !package->binary.entry)
        throw std::runtime_error("Compose a binary application into this GUI kernel before launching it");
    if (package->web.present) throw std::runtime_error("This binary GUI kernel has no rich document engine");
    if (package->abi_major != 1 || package->abi_minor != 0 ||
        package->binary.profile != std::optional<std::string>{"foundation-guest-v1"})
        throw std::runtime_error("Unsupported binary application ABI or guest profile");
    for (const auto& service : package->services)
        if (service != "foundation.kernel" && service != "foundation.view" && service != "foundation.providers")
            throw std::runtime_error("Required binary GUI service is unavailable: " + service);
    for (const auto& capability : package->capabilities)
        if (capability != "foundation.view.v1" && capability != "foundation.providers.v1")
            throw std::runtime_error("Required binary GUI capability is unavailable: " + capability);
    const auto* file = package->find_file(*package->binary.entry);
    if (!file) throw std::runtime_error("Binary application entry is missing");
    return file->data;
}
} // namespace

struct AppendedApplication::Impl {
    gui::Adapter& adapter;
    Registry registry;
    std::unique_ptr<appended::Module> module;
    std::unique_ptr<appended::ModuleProviders> providers;
    EngineModuleView model;
    const gui::Snapshot& view = model.snapshot();
    std::deque<std::variant<gui::Event, gui::ServiceResult>> events;
    std::thread::id owner = std::this_thread::get_id();
    std::uint64_t service_handle = 0, event_sequence = 0;
    bool busy = false, presenting = false, stopped = false, stop_requested = false;
    bool close_requested = false, completion_queued = false;

    Impl(gui::Adapter& output, Span bytes, std::uint64_t generation) : adapter(output), registry(instance_generation(generation)) {
        ServiceDescriptor descriptor; descriptor.name = "foundation.view"; descriptor.schema = AppendedApplication::view_schema();
        descriptor.max_reply_bytes = 16;
        const auto service = registry.register_service(std::move(descriptor), [this](std::uint32_t operation, Span request,
            std::span<std::uint8_t> reply) { return call(operation, request, reply); });
        if (service.status != appended::ServiceStatus::ok) throw std::runtime_error("Cannot register binary view service");
        service_handle = service.handle;
        module = std::make_unique<appended::Module>(bytes, registry);
        providers = std::make_unique<appended::ModuleProviders>(*module, registry, [this] { return next_event(); });
        invoke([&] { return module->initialize(); }, false);
        if (providers->activate() != appended::ServiceStatus::ok) {
            stop(); throw std::runtime_error("Cannot activate binary application providers");
        }
    }

    void check_owner() const {
        if (owner != std::this_thread::get_id()) throw std::logic_error("Binary application requires its event-loop owner");
    }
    ServiceReply call(std::uint32_t operation, Span request, std::span<std::uint8_t> reply) {
        if (stopped || stop_requested) return {appended::ServiceStatus::closed, 0};
        return model.call(operation, request, reply);
    }

    void stop() noexcept {
        stop_requested = true;
        if (busy || presenting) return;
        if (!stopped) {
            stopped = true; model.shutdown(); events.clear(); completion_queued = false;
            if (providers) providers->close();
            if (module) module->shutdown();
            registry.close();
        }
        if (close_requested) {
            // close() is deferred until presentation and guest callbacks end.
            // Shutdown is noexcept even for a failing external adapter.
            try { adapter.close(); } catch (...) {}
        }
    }
    void publish() {
        if (!model.pending() || stopped || adapter.closed() || busy || presenting) return;
        presenting = true;
        try {
            const auto revision = view.revision;
            adapter.present(view);
            (void)model.acknowledge_published(revision);
            presenting = false;
        }
        catch (...) { presenting = false; if (stop_requested) stop(); throw; }
        if (stop_requested) stop();
    }
    template<class Function> void invoke(Function function, bool stepping) {
        check_owner();
        if (stopped || stop_requested || busy || presenting) throw std::logic_error("Binary module invocation is unavailable");
        busy = true;
        try {
            const auto status = function(); busy = false;
            if ((!stepping && status != FOUNDATION_APPENDED_APP_OK) ||
                (stepping && status != FOUNDATION_APPENDED_STEP_IDLE && status != FOUNDATION_APPENDED_STEP_MORE)) {
                stop(); throw std::runtime_error("Binary application returned a terminal status");
            }
        } catch (...) { busy = false; stop(); throw; }
        if (stop_requested) stop();
        else publish();
    }
    std::optional<std::uint64_t> next_event() {
        if (event_sequence == std::numeric_limits<std::uint64_t>::max()) return std::nullopt;
        return ++event_sequence;
    }
    void dispatch(std::uint32_t operation, Bytes payload) {
        const auto sequence = next_event();
        if (!sequence) { stop(); throw std::overflow_error("Binary event sequence exhausted"); }
        Envelope envelope; envelope.kind = FOUNDATION_APPENDED_MESSAGE_EVENT; envelope.generation = registry.generation();
        envelope.sequence = *sequence; envelope.interface_handle = service_handle; envelope.operation = operation;
        Bytes bytes;
        if (encode_envelope(envelope, payload, bytes) != CodecStatus::ok) { stop(); throw std::runtime_error("Cannot encode binary application event"); }
        invoke([&] { return module->dispatch(bytes); }, false);
    }
    void handle(gui::Event event) {
        check_owner();
        if (std::holds_alternative<gui::CloseEvent>(event)) {
            close_requested = true; stop(); return;
        }
        if (stopped || stop_requested || adapter.closed()) return;
        if (busy || presenting) {
            if (events.size() == max_queued_events) { close_requested = true; stop(); return; }
            events.push_back(std::move(event)); return;
        }
        // Retained focus, scrolling and editor state describe the last painted
        // view. Do not combine them with a newer failed presentation.
        if (model.pending()) return;
        if (!model.normalize_event(event,
                [&](const gui::WidgetKey& target) { return adapter.scroll_offset(target); },
                [&] { return adapter.focused(); })) return;
        model.advance_epoch(); dispatch(1, EngineModuleView::encode_event(event, view.revision));
    }
    bool complete(gui::ServiceResult result) {
        check_owner();
        if (stopped || stop_requested || adapter.closed()) return false;
        const auto active = model.current_service();
        if (!active || active->id != result.id || completion_queued) return false;
        if (result.status == gui::ServiceStatus::cancelled) {
            result.value.clear(); result.error.clear();
        } else if (result.value.size() > 65536 || result.error.size() > 65536) {
            result.status = gui::ServiceStatus::error; result.value.clear();
            result.error = "Host service result exceeds the 64 KiB view limit";
        }
        if (busy || presenting) {
            if (events.size() == max_queued_events) { close_requested = true; stop(); return false; }
            events.push_back(std::move(result)); completion_queued = true; return true;
        }
        if (!model.complete_service(result)) return false;
        try {
            auto prepared = EngineModuleView::prepare_service_result(result);
            model.advance_epoch(); dispatch(2, prepared.finish()); return true;
        } catch (...) {
            // Once the completion is consumed, an encoding/allocation failure
            // terminates the instance; it can never continue after losing it.
            stop(); throw;
        }
    }
};

AppendedApplication::AppendedApplication(gui::Adapter& adapter) : AppendedApplication(adapter, self_module()) {}
AppendedApplication::AppendedApplication(gui::Adapter& adapter, Span bytes, std::uint64_t generation)
    : impl_(std::make_unique<Impl>(adapter, bytes, generation)) {}
AppendedApplication::~AppendedApplication() { shutdown(); }
const gui::Snapshot& AppendedApplication::view() const noexcept { return impl_->view; }
bool AppendedApplication::presentation_pending() const noexcept { return impl_->model.pending(); }
std::uint64_t AppendedApplication::input_epoch() const noexcept { return impl_->model.input_epoch(); }
std::uint64_t AppendedApplication::generation() const noexcept { return impl_->registry.generation(); }
void AppendedApplication::handle(gui::Event event) { impl_->handle(std::move(event)); }
void AppendedApplication::shutdown() noexcept { if (impl_) impl_->stop(); }
void AppendedApplication::retry_presentation() { impl_->check_owner(); impl_->publish(); }
void AppendedApplication::tick() {
    impl_->check_owner();
    if (impl_->adapter.closed()) { impl_->stop(); return; }
    if (impl_->stopped || impl_->busy || impl_->presenting) return;
    impl_->publish();
    const auto count = impl_->events.size();
    for (std::size_t n = 0; n < count && !impl_->stopped; ++n) {
        auto event = std::move(impl_->events.front()); impl_->events.pop_front();
        if (auto* input = std::get_if<gui::Event>(&event)) impl_->handle(std::move(*input));
        else {
            impl_->completion_queued = false;
            impl_->complete(std::move(std::get<gui::ServiceResult>(event)));
        }
    }
    if (!impl_->stopped) impl_->invoke([&] { return impl_->module->step(1000); }, true);
}
std::optional<gui::ServiceRequest> AppendedApplication::next_service() {
    impl_->check_owner();
    if (impl_->stopped || impl_->busy || impl_->presenting || impl_->adapter.closed()) return std::nullopt;
    return impl_->model.next_service();
}
bool AppendedApplication::complete_service(gui::ServiceResult result) {
    return impl_->complete(std::move(result));
}
appended::ProviderDiscovery AppendedApplication::discover_provider(const appended::DiscoveryQuery& query) const {
    impl_->check_owner();
    if (impl_->stopped || impl_->stop_requested || impl_->adapter.closed()) return {ServiceStatus::closed, 0, {}};
    if (impl_->busy || impl_->presenting || impl_->model.pending()) return {ServiceStatus::unavailable, 0, {}};
    return impl_->providers->discover(query);
}
appended::ProviderOutcome AppendedApplication::invoke_provider(const appended::ProviderRequest& request) {
    impl_->check_owner();
    if (impl_->stopped || impl_->stop_requested || impl_->adapter.closed()) return {ServiceStatus::closed, {}};
    if (impl_->busy || impl_->presenting || impl_->model.pending()) return {ServiceStatus::unavailable, {}};
    impl_->busy = true;
    appended::ProviderOutcome result;
    try { result = impl_->providers->invoke(request); }
    catch (...) { impl_->busy = false; impl_->stop(); throw; }
    impl_->busy = false;
    if (impl_->stop_requested || impl_->module->closed() || impl_->providers->closed()) impl_->stop();
    else impl_->publish();
    return result;
}
appended::ServiceStatus AppendedApplication::acknowledge_provider(std::uint64_t through) noexcept {
    if (impl_->owner != std::this_thread::get_id() || impl_->busy || impl_->presenting) return ServiceStatus::unavailable;
    if (impl_->stopped || impl_->stop_requested) return ServiceStatus::closed;
    // Adapter queries are not noexcept in the shared GUI contract. A failing
    // query must not terminate the process or acknowledge an unknown outcome.
    try { if (impl_->adapter.closed()) return ServiceStatus::closed; }
    catch (...) { return ServiceStatus::internal_error; }
    return impl_->providers->acknowledge(through);
}
void AppendedApplication::qualify(const std::function<void()>& present) {
    present();
    if (impl_->stopped || impl_->adapter.closed() || impl_->model.pending() || view().revision == 0)
        throw std::runtime_error("Binary application did not present an initial view");
}

const appended::SchemaId& AppendedApplication::view_schema() noexcept {
    return EngineModuleView::schema();
}
} // namespace foundation::ui
