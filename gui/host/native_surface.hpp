// SPDX-License-Identifier: CC0-1.0
#pragma once

#include "native_editor_capture.hpp"
#include <gui/contract.hpp>
#include <gui/runtime.hpp>
#include <foundation/gui/surface.hpp>
#include <foundation/gui/surface_editor.hpp>
#include <cstdint>
#include <algorithm>
#include <cmath>
#include <functional>
#include <limits>
#include <memory>
#include <optional>
#include <stdexcept>
#include <thread>

namespace foundation::host {

enum class NativeSurfaceMode { none, mouse_v1, editor_v1 };
struct NativeRenderReceipt { std::uint64_t snapshot_revision{}; };
enum class NativeEditorAdmission { active, paused, withdrawn };
struct NativeEditorPresentation {
    std::optional<gui_editor::EditorPublication> publication;
    // Accepted output geometry/clip/scale, for generic native caret transforms.
    std::optional<gui_surface::Presentation> surface;
    // Empty while capture is suspended, even if publication retains an owned
    // unresolved Basis for settlement. Peers must withdraw native editability.
    std::optional<gui_surface::EditorContext> context;
    std::optional<gui_editor::CompositionFact> composition;
    std::optional<gui_editor::TextObservation> draft;
    bool preserve_passage{};
    NativeEditorAdmission admission{NativeEditorAdmission::withdrawn};
    // Correlation only, NEVER a native publication or new action authority.
    // Paused peers preserve their OS passage and keep collecting bounded facts;
    // only a checked current publication may return admission to active.
    std::optional<gui_editor::Basis> passage_basis;
    std::optional<gui_editor::CompositionFact> passage_composition;
};

// Trusted backend facts and actual synchronous installation/rendering. A queued
// redraw is not a receipt. Window/renderer and input hooks precede App creation.
// The concrete backend remains window owner; no engine or application lives here.
struct NativeSurfacePeer {
    gui_surface::Capabilities capabilities;
    std::function<bool()> ready;
    std::function<NativeRenderReceipt(gui::Snapshot)> present;
    std::function<void(const NativeEditorPresentation&)> editor;
    // Reversible INPUT/IME/capture suspension. Rendering must remain ready for
    // safe redaction and a later fresh context. This never closes the window.
    std::function<void()> suspend;
    // Query and emit ACTUAL current drawable/foreground/focus facts through
    // the bound ingress. Invoked after arming and after new paired commits.
    std::function<void()> activate;
    // Irreversible peer-output cleanup, at actual proxy close only, once.
    std::function<void()> close;
};
// Owned facts plus weak publication callbacks. A retained application port must
// not keep a reference to a dead proxy/window. Disarm permanently expires these
// callbacks; initial construction publications work before input is armed.
struct NativeSurfacePublisher {
    gui_surface::Capabilities capabilities;
    std::uint64_t generation{};
    std::function<gui_surface::CommitResult(gui::Snapshot, const gui_surface::Presentation&)> present_pair;
    std::function<gui_surface::CommitResult(gui::Snapshot, const gui_surface::Presentation&,
        std::optional<gui_editor::EditorPublication>, std::optional<gui_editor::CompositionFact>)> present_editor_pair;
    std::function<gui_surface::CommitResult(gui::Snapshot, gui_editor::EditorPublication)> present_editor_retirement;
    std::function<bool(bool)> set_owned_service_active;
    bool bound() const noexcept {
        return generation && present_pair && present_editor_pair &&
            present_editor_retirement && set_owned_service_active;
    }
};

class NativeSurfaceAdapter final : public gui::Adapter {
public:
    using InputSink = std::function<void(gui_surface::AcceptedEvent)>;
    using Connected = std::function<void(gui_surface::Capabilities)>;
    using Revoked = std::function<void(gui_surface::Revocation)>;
    NativeSurfaceAdapter(gui::Adapter& concrete, std::uint64_t generation,
        NativeSurfacePeer, NativeSurfaceMode, NativeEditorEndpoint = {},
        gui::EventSink = {}, Revoked = {});
    ~NativeSurfaceAdapter();
    NativeSurfaceAdapter(const NativeSurfaceAdapter&) = delete;
    NativeSurfaceAdapter& operator=(const NativeSurfaceAdapter&) = delete;

    // Arm only after App construction; disarm before shutdown/unwind. No event
    // captured through an unarmed or expired lifetime gate is replayed later.
    void arm(InputSink, Connected, Revoked = {});
    void disarm() noexcept;
    bool failed() const noexcept;
    bool input_admitted() const noexcept;
    bool editor_endpoint_bound() const noexcept;
    const gui_surface::Capabilities& capabilities() const noexcept;
    std::uint64_t generation() const noexcept;
    NativeSurfacePublisher publisher();
    const gui_surface::Presentation* accepted() const noexcept;
    const gui_editor::EditorPublication* editor_publication() const noexcept;
    const gui::Snapshot& snapshot() const noexcept;
    NativeEditorCapture* editor_capture() noexcept;
    gui_surface::CommitResult present_pair(gui::Snapshot, const gui_surface::Presentation&);
    gui_surface::CommitResult present_editor_pair(gui::Snapshot, const gui_surface::Presentation&,
        std::optional<gui_editor::EditorPublication>, std::optional<gui_editor::CompositionFact>);
    gui_surface::CommitResult present_editor_retirement(gui::Snapshot, gui_editor::EditorPublication);
    void set_owned_service_active(bool);
    // Transform/capture/lifecycle changes retire the exact old context. They
    // never invent focus loss or an owned service and do not restore input.
    void invalidate(gui_surface::RevocationReason = gui_surface::RevocationReason::replaced);
    gui_surface::AcceptResult input(gui_surface::Event);
    gui_surface::AcceptResult dispatch_input(gui_surface::Input);
    std::optional<std::uint64_t> observe_editor(NativeEditorObservation);
    void legacy_event(gui::Event);
    // Normal serialized owner phase only; never called by a raw input callback.
    void tick();

    void present(gui::Snapshot) override;
    gui::Size measure_text(const gui::TextMeasureRequest&) const override;
    gui::Availability resolved_availability(const gui::WidgetKey&) const override;
    std::optional<gui::WidgetKey> focused() const override;
    bool focus(std::optional<gui::WidgetKey>) override;
    bool focus_next(bool) override;
    void scroll(const gui::WidgetKey&, gui::Point) override;
    gui::Point scroll_offset(const gui::WidgetKey&) const override;
    gui::TextSelection text_selection(const gui::WidgetKey&) const override;
    void text_selection(const gui::WidgetKey&, gui::TextSelection) override;
    bool open_popup(const gui::WidgetKey&) override;
    void close_popup(const gui::WidgetKey&) override;
    void invalidate(const gui::WidgetKey&, gui::PixelRect) override;
    bool closed() const override;
    void close() override;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace foundation::host
