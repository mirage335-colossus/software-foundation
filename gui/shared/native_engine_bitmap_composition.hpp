// SPDX-License-Identifier: CC0-1.0
#pragma once

#include "engine_primary_region_application.hpp"
#include "native_engine_driver.hpp"

#include <chrono>
#include <cstdint>
#include <functional>
#include <memory>
#include <optional>

namespace foundation::ui {

// Application-side native bitmap composition. The caller supplies one already
// started Driver, its exact shared Owner, and an actual renderer-owned Adapter.
// This facade neither loads nor starts a provider and never owns another editor
// Controller. Interactive publication uses the supplied actual checked port.
class NativeEngineBitmapComposition final {
public:
    using Clock = std::chrono::steady_clock;
    // Scheduling only, possibly from a worker. A process-held relay must be
    // installed before Driver::bind_once; the Driver cannot rebind its wake.
    // The caller keeps this facade alive through every call and callback.
    using PostOwnerWake = std::function<void()>;

    NativeEngineBitmapComposition(gui::Adapter&, std::shared_ptr<appended::EngineOwner>,
        appended::NativeEngineDriver&,
        const appended::engine_document_actions::EngineDocumentActionsProfileFacts&,
        BoundEngineEditorPort, PostOwnerWake = {});
    NativeEngineBitmapComposition(gui::Adapter&, std::shared_ptr<appended::EngineOwner>,
        appended::NativeEngineDriver&,
        const appended::engine_document_actions::EngineDocumentActionsProfileFacts&,
        ReadOnlyEngineBitmap, PostOwnerWake = {});
    NativeEngineBitmapComposition(gui::Adapter&, std::shared_ptr<appended::EngineOwner>,
        appended::NativeEngineDriver&, const appended::engine_document::EngineDocumentProfileFacts&,
        ReadOnlyEngineBitmap, PostOwnerWake = {});
    // Drain normal turns until close_complete(). An unresolved/uncertain close retains
    // the complete App/Owner/port/callback lifetime until process exit; it never
    // forces ACK, disposal, provider unload or a successful close receipt.
    ~NativeEngineBitmapComposition();
    NativeEngineBitmapComposition(const NativeEngineBitmapComposition&) = delete;
    NativeEngineBitmapComposition& operator=(const NativeEngineBitmapComposition&) = delete;

    // Drawable native pixels only. The peer owns letterboxing and its checked
    // transform/clip; the admitted provider viewport remains fixed at800x600.
    // Invalid/empty extent suspends admission. These facts only queue work.
    void drawable_pixels(std::int64_t width, std::int64_t height);
    void foreground(bool);
    void set_owned_service_active(bool);
    bool owned_service_ready() const noexcept;
    void request_frame() noexcept; // A later owner turn may request advance.
    void wake() noexcept; // Coalesced scheduling only; safe while alive.
    void handle(gui::Event);
    bool queue_compiled_region(EngineRegionComposition);
    std::optional<CompiledRegionEvent> take_compiled_event();
    std::uint64_t compiled_region_published_revision() const noexcept;

    // One bounded App stage -> Driver tick -> App settle cycle after native,
    // renderer and Registry callbacks return. Settlement work waits for another
    // turn. Close uses this same cycle to settle real editor retirement.
    void tick(Clock::time_point now = Clock::now());
    void retry_presentation(); // App only; never a provider export/replay.
    void qualify(const std::function<void()>& present);
    void shutdown() noexcept; // Queue close only, safe from an OS callback.

    const gui::Snapshot& view() const noexcept;
    std::uint64_t input_epoch() const noexcept;
    bool presentation_pending() const noexcept;
    // True only for a completed nonempty actual frame publication, never an
    // initial empty candidate, pending publication or redacted/native-effect UI.
    bool frame_ready() const noexcept;
    bool closed() const noexcept;
    // Native detach and local checked head consumption must both finish. A
    // detached metadata turn never enters the Driver or provider again.
    bool close_complete() const noexcept;
    bool close_timed_out() const noexcept;
    appended::NativeEngineState native_state() const noexcept;
    // Includes queued work, native readiness/timers, frame demand and the
    // bounded10second close budget. Publication debt alone never selects spin.
    std::optional<Clock::time_point> deadline() const noexcept;

    // Owned callback values only. Driver/provider entry occurs in tick, never
    // from physical or editor callbacks; rejected input is not rebased/replayed.
    void surface_connected(gui_surface::Capabilities);
    void surface_input(gui_surface::AcceptedEvent);
    void surface_revoked(gui_surface::Revocation);
    std::optional<std::uint64_t> editor_submit(native_editor::Packet);
    std::optional<std::uint64_t> editor_revoke(native_editor::Revocation);
    std::optional<native_editor::EditorCompletion> editor_take(std::uint64_t);
    void editor_resync();

    // Actual Registry/native services belong to the injected Owner/Driver.
    std::optional<gui::ServiceRequest> next_service();
    bool complete_service(gui::ServiceResult);

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace foundation::ui
