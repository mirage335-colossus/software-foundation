#pragma once

#include <foundation/appended/web_services.hpp>

#include <cstdint>
#include <functional>
#include <memory>
#include <span>

namespace foundation::appended {

/* Private optional composition leaf. The neutral owner links only this value
 * interface; a web-only host neither references the actual factory below nor
 * links Module, ModuleProviders or an interpreter. One binding, including its
 * host/event sequence and ACK domain, survives every replacement document.
 * Borrowed construction spans refer to the owner's immutable Package/config.
 * All documents/hooks must die before their binding; close is idempotent. */
class EngineModuleView;
struct EngineModuleServiceRequest;

class EngineModuleBinding {
public:
    virtual ~EngineModuleBinding() = default;
    virtual WebModuleServices services() = 0;
    virtual void close() noexcept = 0;

    // Optional binary GUI lane. Values are staged on the same serialized owner;
    // only the concrete module leaf includes the GUI value model. No callback
    // here presents a scene or enters the guest from a native/renderer callback.
    virtual bool supports_view() const noexcept { return false; }
    virtual std::shared_ptr<const EngineModuleView> view() const noexcept { return {}; }
    virtual bool acknowledge_view(std::uint64_t) noexcept { return false; }
    virtual bool stage_view_event(std::uint64_t, std::span<const std::uint8_t>) { return false; }
    virtual std::shared_ptr<const EngineModuleServiceRequest> begin_view_service() { return {}; }
    virtual std::shared_ptr<const EngineModuleServiceRequest> current_view_service() const noexcept { return {}; }
    virtual bool stage_view_service_result(std::span<const std::uint8_t>) { return false; }
    virtual void tick_view() {}
};

using EngineModuleFactory = std::function<std::unique_ptr<EngineModuleBinding>(
    std::span<const std::uint8_t> module,
    std::span<const NativeServiceRegistration> native_services,
    std::uint64_t generation)>;

/* Implemented solely by the optional module leaf. A binary-capable host binds
 * this explicitly under its build capability; there is no default/fallback
 * reference from EngineOwner or this header's inline code. Construction starts
 * the actual provider-only Module once, on the serialized outside-engine owner. */
std::unique_ptr<EngineModuleBinding> make_engine_module_binding(
    std::span<const std::uint8_t> module,
    std::span<const NativeServiceRegistration> native_services,
    std::uint64_t generation);

// An explicit view-capable factory for a binary-primary rich composition. It
// registers the existing foundation.view v1 service before the single guest
// initializes. Provider-only and web-only factories keep their existing paths.
std::unique_ptr<EngineModuleBinding> make_engine_binary_view_module_binding(
    std::span<const std::uint8_t> module,
    std::span<const NativeServiceRegistration> native_services,
    std::uint64_t generation);

} // namespace foundation::appended
