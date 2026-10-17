// SPDX-License-Identifier: CC0-1.0
#pragma once

#include "native_surface_composition.hpp"
#include <gui/framebuffer.hpp>
#include <SDL.h>
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <functional>
#include <memory>

namespace foundation::host {

// SDL2 reports an unmodified logical key separately from text input. Printable
// keys retain that reported symbol; only TEXTINPUT can commit characters.
gui_surface::KeyTransition sdl_surface_key(const SDL_KeyboardEvent&);
std::uint32_t sdl_surface_modifiers(SDL_Keymod) noexcept;
std::optional<unsigned> sdl_surface_button(Uint8) noexcept;
unsigned sdl_surface_buttons(Uint32) noexcept;

// The actual optional runner uses this same loop with an SDL event pump and
// renderer. A nonzero App result ends pumping without claiming native work was
// settled; the Session continues to own all retained state and normal lifetime.
// Keeping the pump injectable permits closed lifecycle tests without SDL video.
template<class Session, class Pump, class Paint>
int run_native_sdl_surface_loop(Session& session, Pump pump, Paint paint) {
    for (;;) {
        const auto before=session.runner_state();
        if (before.exit_code || before.close_complete) return before.exit_code;
        int timeout=16;
        if (before.deadline) {
            const auto remaining=std::chrono::duration_cast<std::chrono::milliseconds>(
                *before.deadline-std::chrono::steady_clock::now()).count();
            timeout=static_cast<int>(std::clamp<std::int64_t>(remaining,0,timeout));
        }
        pump(timeout);
        const auto pumped=session.runner_state();
        if (pumped.exit_code || pumped.close_complete) return pumped.exit_code;
        session.tick();
        const auto after=session.runner_state();
        if (after.exit_code || after.close_complete) return after.exit_code;
        if (!session.adapter.closed()) paint();
    }
}

// The generic SDL frontend owns provisional editing values, never native DOM
// authority. Capture remains the sole causal collector. Preedit selection is an
// explicitly frontend-owned collapsed end cursor: SDL2's undocumented start/
// length units are not reinterpreted as UTF-8 or UTF-16 offsets.
class NativeSdlSurfaceInput final {
public:
    struct Hooks {
        std::function<bool(bool)> capture;
        std::function<SDL_Keymod()> modifiers;
        std::function<void(bool)> text_input;
        std::function<void(gui_surface::Rect)> caret;
        std::function<void()> clear_composition;
        // Window logical pixels -> the exact committed snapshot coordinates.
        // Empty is the identity transform, useful for closed translation tests.
        std::function<gui::Point(gui::Point)> point;
    };
    NativeSdlSurfaceInput(NativeSurfaceIngress, NativeSurfaceMode, Hooks);
    ~NativeSdlSurfaceInput();
    NativeSdlSurfaceInput(const NativeSdlSurfaceInput&) = delete;
    NativeSdlSurfaceInput& operator=(const NativeSdlSurfaceInput&) = delete;
    // True means the native event belongs to this optional Surface path.
    bool event(const SDL_Event&);
    // Only after a fresh paired commit: actual window focus/visibility facts.
    void activate(bool focused, bool active);
    // Actual queried renderer pixels/foreground, value-deduplicated; no authority.
    void platform_facts(std::int64_t width, std::int64_t height, bool foreground);
    void editor(const NativeEditorPresentation&);
    void suspend() noexcept;
    void invalidate(gui_surface::RevocationReason = gui_surface::RevocationReason::replaced);
    unsigned held_buttons() const noexcept;
    std::uint64_t capture_token() const noexcept;
    const gui_editor::TextObservation* draft() const noexcept;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

// Construct after SDL video initialization, before App construction. The peer
// owns one window/renderer/texture and renders the same FramebufferAdapter.
// present returns the Snapshot revision only after real texture upload and
// SDL_RenderPresent. This is not a physical-display/scanout attestation.
class NativeSdlSurfacePeer final {
public:
    NativeSdlSurfacePeer(gui::FramebufferAdapter&, const NativeSurfaceWindow&,
        NativeSurfaceIngress, NativeSurfaceMode, bool hidden = false);
    ~NativeSdlSurfacePeer();
    NativeSdlSurfacePeer(const NativeSdlSurfacePeer&) = delete;
    NativeSdlSurfacePeer& operator=(const NativeSdlSurfacePeer&) = delete;
    NativeSurfacePeer peer() const;
    // Resize retires the old input transform before resizing the adapter.
    // Close/quit remain ordinary runner lifecycle events, returned as false.
    bool event(const SDL_Event&);
    void redraw();
    SDL_Window* window() const noexcept;
    SDL_Renderer* renderer() const noexcept;
    const gui::Frame& frame() const noexcept;
private:
    struct Impl;
    std::shared_ptr<Impl> impl_;
};

} // namespace foundation::host
