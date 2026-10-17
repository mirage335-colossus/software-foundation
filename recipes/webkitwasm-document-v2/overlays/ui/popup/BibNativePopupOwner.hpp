// SPDX-License-Identifier: CC0-1.0
#pragma once
#include "NativePopupController.hpp"
#include "appended_engine_input_codec.hpp"
#include <optional>
namespace WebCore { class GraphicsContext; class IntRect; class HTMLSelectElement; }
namespace BIB::FormsV2Combined { class SharedGuard; }
namespace BIB::EnginePopup {
namespace Policy=bib::provider_candidate::native_popup;
struct RouteResult { bool claimed{},handled{}; };
struct Handoff {
    Policy::PopupToken token{};
    Policy::LifecycleKey key{};
    Policy::PointerState pointer{};
    std::uint64_t physical_version{},sequence{};
};
bool openUserPopup(WebCore::HTMLSelectElement&,BIB::FormsV2Combined::SharedGuard&) noexcept;
Policy::PopupToken token() noexcept;
bool blocksScrollBlit() noexcept;
// Actual owner/Bridge/JSC turn only. No new turn/Host entry is performed.
void reconcile() noexcept;
bool paint(WebCore::GraphicsContext&,const WebCore::IntRect&) noexcept;
RouteResult routeKey(const foundation::appended::engine_input::Key&) noexcept;
RouteResult routePointer(const foundation::appended::engine_input::Mouse&,
    Policy::PointerState previous,Policy::PointerState next) noexcept;
// AFTER the actual original EventHandler returns. A borrowed key or mouse may
// be supplied, never both. State is the already committed current physical state.
std::optional<Handoff> afterPageInput(Policy::PopupToken before,
    const foundation::appended::engine_input::Key*,
    const foundation::appended::engine_input::Mouse*,Policy::PointerState committed,
    double pointer_x,double pointer_y,bool has_pointer_point,std::uint64_t physical_version,std::uint64_t sequence) noexcept;
bool handoffCurrent(const Handoff&) noexcept;
void finishHandoff(const Handoff&,bool completed,bool native_effects_started) noexcept;
// Metadata-only, called AFTER actual portable focus/context state commits.
void observeFocus(Policy::PointerState previous,Policy::PointerState next,bool focused,bool active) noexcept;
void retireAuthority() noexcept;
} // namespace BIB::EnginePopup
