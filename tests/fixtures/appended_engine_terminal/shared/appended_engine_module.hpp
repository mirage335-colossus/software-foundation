// TEST ONLY: no interpreter, Registry, provider, loader or runtime is linked.
#pragma once
#include "state.hpp"
#include <span>
#include <foundation/appended/web_services.hpp>
namespace foundation::appended {
// Only the complete metadata type needed to type-check the real entry is
// provided. No decoded Module view or binary-primary behavior is simulated.
class EngineModuleView {
    gui::Snapshot snapshot_;
public:
    const gui::Snapshot& snapshot() const noexcept { return snapshot_; }
};
class EngineModuleBinding { public: virtual ~EngineModuleBinding()=default; };
using EngineModuleFactory=std::function<std::unique_ptr<EngineModuleBinding>(std::span<const std::uint8_t>,std::span<const NativeServiceRegistration>,std::uint64_t)>;
std::unique_ptr<EngineModuleBinding> make_engine_module_binding(std::span<const std::uint8_t>,std::span<const NativeServiceRegistration>,std::uint64_t);
std::unique_ptr<EngineModuleBinding> make_engine_binary_view_module_binding(std::span<const std::uint8_t>,std::span<const NativeServiceRegistration>,std::uint64_t);
}
