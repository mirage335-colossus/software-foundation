#pragma once

#include "appended_engine_owner.hpp"
#include "appended_engine_input_profile.hpp"
#include "engine_editor_profile.hpp"
#include "engine_document_actions_profile.hpp"
#include "engine_surface_port.hpp"
#include "engine_region_composition.hpp"
#include "native_editor_context_adapter.hpp"
#include <foundation/gui/document_endpoint.hpp>
#include <gui/contract.hpp>
#include <gui/runtime.hpp>
#include <array>
#include <functional>
#include <memory>

namespace foundation::ui {

// One checked commit owns the bitmap, generic surface declaration, editor
// basis/settlement and logical composition. The concrete adapter remains in
// the composition root and outlives this port and the application.
class EngineEditorPort : public EngineSurfacePort {
public:
    virtual gui_surface::CommitResult present_editor_pair(
        gui::Snapshot, const gui_surface::Presentation&,
        std::optional<native_editor::EditorPublication>,
        std::optional<native_editor::CompositionFact>) = 0;
    // A checked null readback may retire an owner removed by safe redaction.
    // It publishes no active surface and never requires a fabricated widget.
    virtual gui_surface::CommitResult present_editor_retirement(
        gui::Snapshot, native_editor::EditorPublication) = 0;
};

// Separate opt-in prevents an editor profile from falling through a legacy or
// bitmap-observation-only constructor. Construction requires a nonnull port.
struct BoundEngineEditorPort {
    std::unique_ptr<EngineEditorPort> port;
};

// Explicit observation-only selection under the same exact actions profile.
// No physical/editor port or Controller is created by this composition.
struct ReadOnlyEngineBitmap {};

// Verifies the decoded HTML carrier suffix using the shared canonical package
// reader. The supplied prefix identity is the immutable kernel's identity; this
// consistency check cannot authenticate raw HTML prefix bytes from a DOM value.
appended::Package prepare_engine_html_package(
    std::span<const std::uint8_t> suffix, std::uint64_t expected_prefix_length,
    std::span<const std::uint8_t, 32> expected_prefix_sha256);

// The engine owns document behavior. This application owns only an ordinary,
// immutable bitmap presentation. Its injected owner outlives all retained frames;
// no package document, script, module view or engine callback reaches an adapter.
class AppendedEngineApplication {
public:
    AppendedEngineApplication(gui::Adapter&, std::shared_ptr<appended::EngineOwner>,
                             std::optional<EngineRegionComposition> = {});
    AppendedEngineApplication(gui::Adapter&, std::shared_ptr<appended::EngineOwner>,
                             std::unique_ptr<EngineSurfacePort>,
                             const appended::engine_input::EngineSurfaceProfileFacts&,
                             std::optional<EngineRegionComposition> = {});
    // Exact document facts must agree with the configured Owner. Pixel1795
    // accepts no port; physical2003 without one is bitmap observation only.
    // A physical browser composition must supply its actual8225 port. Native
    // effects require successful redaction, settled work and a fresh actual
    // post-release frame before bitmap/input rearm; no frame is synthesized.
    AppendedEngineApplication(gui::Adapter&, std::shared_ptr<appended::EngineOwner>,
                             const appended::engine_document::EngineDocumentProfileFacts&,
                             std::unique_ptr<EngineSurfacePort> = {},
                             std::optional<EngineRegionComposition> = {});
    AppendedEngineApplication(gui::Adapter&, std::shared_ptr<appended::EngineOwner>,
                             const appended::engine_editor::EngineEditorProfileFacts&,
                             BoundEngineEditorPort, std::optional<EngineRegionComposition> = {});
    AppendedEngineApplication(gui::Adapter&, std::shared_ptr<appended::EngineOwner>,
                             const appended::engine_document_actions::EngineDocumentActionsProfileFacts&,
                             BoundEngineEditorPort, std::optional<EngineRegionComposition> = {});
    AppendedEngineApplication(gui::Adapter&, std::shared_ptr<appended::EngineOwner>,
                             const appended::engine_document_actions::EngineDocumentActionsProfileFacts&,
                             ReadOnlyEngineBitmap, std::optional<EngineRegionComposition> = {});
    ~AppendedEngineApplication();
    AppendedEngineApplication(const AppendedEngineApplication&) = delete;
    AppendedEngineApplication& operator=(const AppendedEngineApplication&) = delete;

    const gui::Snapshot& view() const noexcept;
    void handle(gui::Event);
    // Owned compiled candidates/events use the same serialized application and
    // sole checked presenter. Layout is immutable after construction.
    bool queue_compiled_region(EngineRegionComposition);
    std::optional<CompiledRegionEvent> take_compiled_event();
    std::uint64_t compiled_region_published_revision() const noexcept;
    void tick();
    void shutdown() noexcept;
    void retry_presentation();
    std::optional<gui::ServiceRequest> next_service();
    bool complete_service(gui::ServiceResult);
    void qualify(const std::function<void()>& present);
    bool presentation_pending() const noexcept;
    // Local close barriers, including an explicit Take of a known editor head.
    // This does not establish Owner or native Driver detachment.
    bool shutdown_complete() const noexcept;
    std::uint64_t input_epoch() const noexcept;

    // Browser callbacks retain owned values only. Normal owner ticks perform
    // normalization and stage copied commands after the complete turn returns.
    void surface_connected(gui_surface::Capabilities);
    void surface_input(gui_surface::AcceptedEvent);
    void surface_revoked(gui_surface::Revocation);
    void set_owned_service_active(bool);
    bool owned_service_ready() const noexcept;

    // These callbacks retain bounded owned values only. Accepted heads wait
    // for normal Owner work and checked atomic publication before a completion
    // can be taken. Terminal failures close promptly; busy transport never
    // fabricates a receipt or retries an accepted native attempt.
    std::optional<std::uint64_t> editor_submit(native_editor::Packet);
    std::optional<std::uint64_t> editor_revoke(native_editor::Revocation);
    std::optional<native_editor::EditorCompletion> editor_take(std::uint64_t);
    void editor_resync();

    // Semantic intents retain owned application values. The shared broker
    // stages native work only from normal ticks and exposes accepted content
    // only after this application's sole presenter commits its exact candidate.
    gui_document::Submission document_submit(gui_document::Intent);
    std::optional<gui_document::Completion> document_take(gui_document::Ticket);
    gui_document::State document_state() const;
    gui_document::TerminalHook document_terminal() noexcept;

    // Default bitmap-only construction declares no physical surface input.
    // This is separate from the existing public GUI snapshot wire contract.
    static constexpr std::uint64_t physical_surface_capabilities() noexcept { return 0; }

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace foundation::ui
