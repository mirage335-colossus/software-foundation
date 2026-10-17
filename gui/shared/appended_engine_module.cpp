#include "appended_engine_module.hpp"

// The ordinary provider-only leaf remains available without GUI headers or
// targets. Only the explicitly selected GUI composition enables the view lane.
#ifndef FOUNDATION_APPENDED_MODULE_VIEW_CAPABILITY
#define FOUNDATION_APPENDED_MODULE_VIEW_CAPABILITY 0
#endif
#if FOUNDATION_APPENDED_MODULE_VIEW_CAPABILITY != 0 && FOUNDATION_APPENDED_MODULE_VIEW_CAPABILITY != 1
#error "FOUNDATION_APPENDED_MODULE_VIEW_CAPABILITY must be exactly 0 or 1"
#endif
#if FOUNDATION_APPENDED_MODULE_VIEW_CAPABILITY
#include "appended_binary_view_model.hpp"
#endif

#include <foundation/appended/module.hpp>

#include <deque>
#include <iterator>
#include <map>
#include <optional>
#include <stdexcept>
#include <thread>
#include <utility>

namespace foundation::appended {
namespace {
#if FOUNDATION_APPENDED_MODULE_VIEW_CAPABILITY
constexpr std::size_t maximum_view_events = 64;
constexpr std::size_t maximum_view_event_bytes = 1024 * 1024;
#endif

class ActualEngineModule final : public EngineModuleBinding {
public:
    ActualEngineModule(std::span<const std::uint8_t> bytes,
                      std::span<const NativeServiceRegistration> registrations,
                      std::uint64_t generation, bool enable_view = false)
        : registry_(generation), generation_(generation) {
        if (install_native_services(registry_, registrations) != ServiceStatus::ok)
            throw std::invalid_argument("rich native guest registrations conflict");
#if FOUNDATION_APPENDED_MODULE_VIEW_CAPABILITY
        if (enable_view) {
            view_ = std::make_shared<EngineModuleView>();
            ServiceDescriptor descriptor;
            descriptor.name = "foundation.view";
            descriptor.schema = EngineModuleView::schema();
            descriptor.max_reply_bytes = 16;
            const auto registered = registry_.register_service(std::move(descriptor),
                [this](std::uint32_t operation, std::span<const std::uint8_t> request,
                       std::span<std::uint8_t> reply) {
                    if (stopped_ || owner_ != std::this_thread::get_id())
                        return ServiceReply{ServiceStatus::closed, 0};
                    // Only owned values change. No presenter, backend, event
                    // dispatch or recursive module invocation runs in Registry.
                    return view_->call(operation, request, reply);
                });
            if (registered.status != ServiceStatus::ok)
                throw std::invalid_argument("rich binary view service conflicts");
            view_handle_ = registered.handle;
        }
#else
        (void)enable_view;
#endif
        module_ = std::make_unique<Module>(bytes, registry_);
        providers_ = std::make_unique<ModuleProviders>(*module_, registry_, [this] { return events_.next(); });
        if (invoke([&] { return module_->initialize(); }) != 0 ||
            providers_->activate() != ServiceStatus::ok)
#if FOUNDATION_APPENDED_MODULE_VIEW_CAPABILITY
            throw std::runtime_error(view_ ? "view-capable rich binary initialization failed" :
                "provider-only rich binary initialization failed");
#else
            throw std::runtime_error("provider-only rich binary initialization failed");
#endif
    }
    ~ActualEngineModule() override { close(); }

    WebModuleServices services() override {
        return {generation_,
            [this](const DiscoveryQuery& query) { return providers_->discover(query); },
            [this](const ProviderRequest& request) {
                // Reserve the persistent broker record before a guest effect.
                const auto [position, inserted] = outcomes_.emplace(request.sequence, false);
                if (!inserted) return ProviderOutcome{ServiceStatus::conflict, {}};
                auto outcome = invoke([&] { return providers_->invoke(request); });
                position->second = true;
                return outcome;
            },
            [this](std::uint64_t sequence) {
                const auto found = outcomes_.find(sequence);
                if (found == outcomes_.end() || !found->second) return ServiceStatus::unavailable;
                const auto status = invoke([&] { return providers_->acknowledge(sequence); });
                if (status == ServiceStatus::ok || status == ServiceStatus::invalid_request || status == ServiceStatus::closed)
                    outcomes_.erase(outcomes_.begin(), std::next(found));
                return status;
            }, [this] { return hosts_.next(); }};
    }

#if FOUNDATION_APPENDED_MODULE_VIEW_CAPABILITY
    bool supports_view() const noexcept override { return view_ != nullptr; }
    std::shared_ptr<const EngineModuleView> view() const noexcept override { return view_; }

    bool acknowledge_view(std::uint64_t revision) noexcept override {
        if (!available() || busy_ || !view_) return false;
        if (!view_->acknowledge_published(revision)) return false;
        published_revision_ = revision;
        return true;
    }

    bool stage_view_event(std::uint64_t revision,
                          std::span<const std::uint8_t> bytes) override {
        if (!available() || busy_ || !view_ || view_->pending() || !revision ||
            revision != published_revision_ || revision != view_->snapshot().revision ||
            work_.size() >= maximum_view_events || bytes.empty() ||
            bytes.size() > maximum_view_event_bytes - queued_bytes_)
            return false;
        // This internal lane accepts only the already-normalized shared view
        // event codec, preserving the module-local painted revision. It never
        // substitutes the composed application's presentation revision.
        std::vector<FieldView> fields;
        if (decode_record(bytes, fields) != CodecStatus::ok) return false;
        std::uint64_t encoded_revision = 0;
        std::uint32_t event_kind = 0;
        bool has_revision = false, has_kind = false;
        for (const auto& field : fields) {
            if (field.id == 1) has_revision = read_u64(field, encoded_revision);
            else if (field.id == 2) has_kind = read_u32(field, event_kind);
        }
        if (!has_revision || !has_kind || encoded_revision != revision || event_kind < 1 || event_kind > 3)
            return false;
        ViewWork next;
        next.operation = 1;
        next.revision = revision;
        next.bytes.assign(bytes.begin(), bytes.end());
        work_.push_back(std::move(next));
        queued_bytes_ += bytes.size();
        return true;
    }

    std::shared_ptr<const EngineModuleServiceRequest> begin_view_service() override {
        if (!available() || busy_ || !view_ || active_view_service_) return {};
        try {
            auto request = view_->next_service();
            if (!request) return {};
            active_view_service_ = std::make_shared<const EngineModuleServiceRequest>(
                EngineModuleServiceRequest{std::move(*request)});
            return active_view_service_;
        } catch (...) {
            // Queue.begin_next may already own the request. Losing its wrapper
            // must never leave a live module whose accepted work can vanish.
            close();
            throw;
        }
    }

    std::shared_ptr<const EngineModuleServiceRequest> current_view_service() const noexcept override {
        return available() ? active_view_service_ : nullptr;
    }

    bool stage_view_service_result(std::span<const std::uint8_t> bytes) override {
        if (!available() || busy_ || !view_ || service_result_queued_ ||
            work_.size() >= maximum_view_events || bytes.empty() ||
            bytes.size() > maximum_view_event_bytes - queued_bytes_)
            return false;
        try {
            auto result = EngineModuleView::decode_service_result(bytes);
            if (!active_view_service_ || active_view_service_->request.id != result.id) return false;
            ViewWork next;
            next.operation = 2;
            next.bytes.assign(bytes.begin(), bytes.end());
            next.service = std::move(result);
            work_.push_back(std::move(next));
            queued_bytes_ += bytes.size();
            service_result_queued_ = true;
            return true;
        } catch (const std::invalid_argument&) {
            return false; // Parsing has no guest or service-queue side effect.
        }
    }

    void tick_view() override {
        if (!view_ || !available() || busy_) return;
        try {
            const auto count = work_.size();
            for (std::size_t index = 0; index < count && available(); ++index) {
                auto next = std::move(work_.front());
                work_.pop_front();
                queued_bytes_ -= next.bytes.size();
                if (next.operation == 1) {
                    // A previous event may have synchronously published a successor
                    // view. An old queued input is known not entered and is dropped,
                    // exactly as the ordinary binary app refuses input while pending.
                    if (view_->pending() || next.revision != published_revision_ ||
                        next.revision != view_->snapshot().revision) continue;
                } else {
                    service_result_queued_ = false;
                    if (!next.service || !view_->complete_service(*next.service)) {
                        close();
                        throw std::runtime_error("rich binary view service completion lost its owned request");
                    }
                    active_view_service_.reset();
                    // ServiceQueue normalizes cancellation and the actual
                    // request's byte limit. Dispatch that consumed value,
                    // preserving the old prepare -> epoch -> finish order.
                    auto prepared = EngineModuleView::prepare_service_result(*next.service);
                    view_->advance_epoch();
                    dispatch(next.operation, prepared.finish());
                    continue;
                }
                view_->advance_epoch();
                dispatch(next.operation, next.bytes);
            }
            if (!available()) return;
            const auto status = invoke([&] { return module_->step(1000); });
            if (status != FOUNDATION_APPENDED_STEP_IDLE && status != FOUNDATION_APPENDED_STEP_MORE) {
                close();
                throw std::runtime_error("rich binary view step returned a terminal status");
            }
        } catch (...) {
            // A work item may already be popped, or a service completion
            // consumed, before epoch/envelope allocation or guest entry fails.
            // Terminate the same module; never continue after losing that work.
            close();
            throw;
        }
    }

#endif
    void close() noexcept override {
        if (stopped_) return;
        stopped_ = true;
#if FOUNDATION_APPENDED_MODULE_VIEW_CAPABILITY
        work_.clear();
        queued_bytes_ = 0;
        active_view_service_.reset();
        service_result_queued_ = false;
#endif
        if (providers_) providers_->close();
#if FOUNDATION_APPENDED_MODULE_VIEW_CAPABILITY
        if (view_) view_->shutdown();
#endif
        if (module_) module_->shutdown();
        registry_.close();
    }

private:
#if FOUNDATION_APPENDED_MODULE_VIEW_CAPABILITY
    struct ViewWork {
        std::uint32_t operation{};
        std::uint64_t revision{};
        Bytes bytes;
        std::optional<gui::ServiceResult> service;
    };
    bool available() const noexcept {
        return !stopped_ && owner_ == std::this_thread::get_id() && module_ && !module_->closed();
    }
#endif
    template<class Function> auto invoke(Function function) -> decltype(function()) {
#if FOUNDATION_APPENDED_MODULE_VIEW_CAPABILITY
        // The original provider-only path retains its direct behavior. The
        // explicit view factory adds the serialized guest-entry barrier needed
        // when GUI events and providers share this same Module and sequence.
        if (!view_) return function();
        if (stopped_ || owner_ != std::this_thread::get_id() || busy_)
            throw std::logic_error("rich binary view requires its serialized owner");
        busy_ = true;
        try {
            auto result = function();
            busy_ = false;
            if (module_->closed() || providers_->closed()) close();
            return result;
        } catch (...) {
            busy_ = false;
            close();
            throw;
        }
#else
        return function();
#endif
    }
#if FOUNDATION_APPENDED_MODULE_VIEW_CAPABILITY
    void dispatch(std::uint32_t operation, std::span<const std::uint8_t> payload) {
        const auto sequence = events_.next();
        if (!sequence) { close(); throw std::overflow_error("rich binary event sequence exhausted"); }
        Envelope envelope;
        envelope.kind = FOUNDATION_APPENDED_MESSAGE_EVENT;
        envelope.generation = registry_.generation();
        envelope.sequence = *sequence;
        envelope.interface_handle = view_handle_;
        envelope.operation = operation;
        Bytes encoded;
        if (encode_envelope(envelope, payload, encoded) != CodecStatus::ok) {
            close();
            throw std::runtime_error("rich binary view event cannot be encoded");
        }
        if (invoke([&] { return module_->dispatch(encoded); }) != FOUNDATION_APPENDED_APP_OK) {
            close();
            throw std::runtime_error("rich binary view dispatch returned a terminal status");
        }
    }

#endif
    Registry registry_;
    const std::uint64_t generation_;
    GenerationSource hosts_, events_;
    std::map<std::uint64_t, bool> outcomes_;
#if FOUNDATION_APPENDED_MODULE_VIEW_CAPABILITY
    std::shared_ptr<EngineModuleView> view_;
    std::shared_ptr<const EngineModuleServiceRequest> active_view_service_;
#endif
    std::unique_ptr<Module> module_;
    std::unique_ptr<ModuleProviders> providers_;
#if FOUNDATION_APPENDED_MODULE_VIEW_CAPABILITY
    std::deque<ViewWork> work_;
    std::thread::id owner_ = std::this_thread::get_id();
    std::uint64_t view_handle_{}, published_revision_{};
    std::size_t queued_bytes_{};
    bool busy_{}, service_result_queued_{};
#endif
    bool stopped_{};
};
} // namespace

std::unique_ptr<EngineModuleBinding> make_engine_module_binding(
    std::span<const std::uint8_t> module,
    std::span<const NativeServiceRegistration> registrations,
    std::uint64_t generation) {
    return std::make_unique<ActualEngineModule>(module, registrations, generation);
}

#if FOUNDATION_APPENDED_MODULE_VIEW_CAPABILITY
std::unique_ptr<EngineModuleBinding> make_engine_binary_view_module_binding(
    std::span<const std::uint8_t> module,
    std::span<const NativeServiceRegistration> registrations,
    std::uint64_t generation) {
    return std::make_unique<ActualEngineModule>(module, registrations, generation, true);
}
#endif
} // namespace foundation::appended
