#pragma once

#include "appended_engine_module.hpp"
#include "appended_engine_input_profile.hpp"
#include "engine_document_work.hpp"
#include "engine_editor_profile.hpp"
#include "engine_editor_work.hpp"

#include <foundation/appended/container.hpp>
#include <foundation/appended/web_services.hpp>

#include <cstdint>
#include <memory>
#include <optional>
#include <span>
#include <string>
#include <vector>

namespace foundation::appended {

struct EngineIdentity {
    std::uint64_t worker_epoch{}, application_instance{}, document_sequence{}, service_generation{};
    bool operator==(const EngineIdentity&) const = default;
};
struct EngineFrame {
    EngineIdentity identity;
    std::uint32_t width{}, height{}, stride{};
    std::uint64_t frame_revision{};
    Bytes rgba;
};
using EngineInputTicket = std::uint64_t;
enum class EngineInputCommandStatus { pending, rejected, consumed, unknown, cancelled };
struct EngineInputOutcome {
    EngineInputCommandStatus status{EngineInputCommandStatus::pending};
    std::int32_t provider_status{};
    bool handled{};
};
struct EngineNativeEffect {
    std::uint64_t ticket{};
    EngineIdentity target;
    std::uint64_t input_context{};
    bool entered{};
};
enum class EngineStartupPrimary { web, compiled, binary };
// Exact canonical startup intent from an actual verified Package. The selected
// native configuration and binding must still independently admit that intent.
EngineStartupPrimary read_engine_startup_primary(const Package&);
struct EngineOwnerConfiguration {
    EngineStartupPrimary startup_primary = EngineStartupPrimary::web;
    std::uint64_t worker_epoch{1}, application_instance{0}, module_generation{1};
    WebServiceLimits services;
    std::vector<NativeServiceRegistration> native_services;
    EngineModuleFactory module_factory; // Empty for a VM-free web-only kernel.
    /* Trusted CLOSE/replacement may abandon results belonging to a disposed
     * page through the immutable owner audit protocol, never a page callback. */
    bool abandon_closed_document_outcomes{false};
    /* Explicitly maintained compiled facts only. Disabled preserves the
     * original bitmap-only copied bridge, including its empty input catalog. */
    engine_input::EngineSurfaceProfileFacts input_profile;
    /* Additive, explicitly maintained ABI1.1 document profile. Its physical
     * variant owns the separate physical catalog; do not also enable legacy
     * ABI1.0 input_profile facts. Disabled preserves all existing profiles. */
    engine_document::EngineDocumentProfileFacts document_profile;
    /* Exact independent editor2035 facts. This selection is mutually exclusive
     * with input_profile/document_profile; old facts never advertise editor. */
    engine_editor::EngineEditorProfileFacts editor_profile;
    /* Independent explicit kind4/4083 facts. Never cast these into an old
     * document/editor profile or infer admission from capability bits. */
    engine_document_actions::EngineDocumentActionsProfileFacts document_actions_profile;
};

/* Serialized real kernel owner. Package must have come from the common verified
 * container reader. It is moved/copied once and remains immutable. This owner
 * has no GUI/engine dependency and never enters an engine or host filesystem.
 * Native registrations capture actual application owners and outlive this object.
 * An explicit optional factory creates a binary Registry/Module/Providers domain;
 * its host/event sequences and outcome retirement survive document replacement.
 */
class EngineOwner final {
public:
    EngineOwner(Package, EngineOwnerConfiguration);
    ~EngineOwner();
    EngineStartupPrimary startup_primary() const noexcept;
    std::shared_ptr<const EngineModuleView> binary_view() const noexcept;
    bool acknowledge_binary_view(std::uint64_t revision) noexcept;
    bool stage_binary_view_event(std::uint64_t revision,std::span<const std::uint8_t>);
    void tick_binary_view();
    std::shared_ptr<const EngineModuleServiceRequest> begin_binary_view_service();
    std::shared_ptr<const EngineModuleServiceRequest> current_binary_view_service() const noexcept;
    bool stage_binary_view_service_result(std::span<const std::uint8_t>);
    EngineOwner(const EngineOwner&) = delete;
    EngineOwner& operator=(const EngineOwner&) = delete;

    /* Always contains exceptions. A nonnegative result is a complete initialized
     * copied record; negatives are FoundationEngineTransportError. The caller
     * owns and validates local Wasm pointers before constructing these spans.
     * No borrowed input/output span or engine callback is retained. */
    std::int32_t dispatch(std::uint32_t operation, std::span<const std::uint8_t> input,
                          std::span<std::uint8_t> output) noexcept;
    [[nodiscard]] const Package& package() const noexcept;
    [[nodiscard]] EngineIdentity identity() const noexcept;
    [[nodiscard]] std::uint32_t callback_depth() const noexcept;
    [[nodiscard]] bool configured() const noexcept;
    [[nodiscard]] bool closed() const noexcept;
    [[nodiscard]] bool has_module() const noexcept;
    [[nodiscard]] const std::optional<EngineFrame>& frame() const noexcept;
    /* These owner-thread APIs copy values only; they never invoke an engine or
     * a service. There is one bounded mailbox and one latest terminal outcome.
     * Ticket/request_sequence is owner-issued and persists across navigation. */
    [[nodiscard]] bool input_enabled() const noexcept;
    [[nodiscard]] bool input_suspended() const noexcept;
    [[nodiscard]] std::optional<EngineInputTicket> stage_command(EngineIdentity target,
        std::uint64_t input_context, std::uint32_t operation,
        const engine_input::Digest& schema_sha256, Bytes payload, bool lifecycle = false) noexcept;
    [[nodiscard]] std::optional<EngineInputOutcome> command_outcome(EngineInputTicket) const noexcept;
    void cancel_input_context(EngineIdentity target, std::uint64_t input_context) noexcept;
    /* Before an actual queued service handler, the App closes publication,
     * settles exact provider retirement, then acknowledges this trusted ticket.
     * Known completion resumes ordinary admission automatically. A handler may
     * retain a UI hold only during its actual entry; only trusted UI closure
     * releases that hold. No renderer field supplies this authority. */
    [[nodiscard]] std::optional<EngineNativeEffect> native_effect() const noexcept;
    [[nodiscard]] bool acknowledge_native_effect(std::uint64_t ticket) noexcept;
    [[nodiscard]] bool hold_native_effect(std::uint64_t ticket) noexcept;
    [[nodiscard]] bool release_native_effect(std::uint64_t ticket) noexcept;
    /* Separate bounded document work/result and action-ACK lanes. These APIs
     * retain owned values only and never enter a provider, GUI or Registry.
     * The one ordinary reservation blocks later physical work from overtaking
     * its sequence. Cancelling only the exact held reservation burns that
     * value; it never rewinds. nullopt is temporary busy; exhausted ordinary
     * sequence space throws overflow_error while preserving final ACK at MAX. */
    [[nodiscard]] bool document_enabled() const noexcept;
    [[nodiscard]] bool document_actions_enabled() const noexcept;
    [[nodiscard]] const engine_document_actions::EngineDocumentActionsProfileFacts& document_actions_profile() const noexcept;
    /* Immutable admitted facts for exact Driver/provider agreement before START. */
    [[nodiscard]] const engine_document::EngineDocumentProfileFacts& document_profile() const noexcept;
    /* Trusted terminal notification while this owner's lifetime is held. May
     * run off-thread: only atomic terminal state is published, idempotently,
     * without exports, allocation, callbacks or cleanup. Enabled document
     * profiles then require process exit; other profiles are unchanged.
     * An already admitted turn may finish naturally; no result is fabricated. */
    void notify_document_terminal() noexcept;
    [[nodiscard]] std::optional<std::uint64_t> reserve_document_sequence();
    [[nodiscard]] bool cancel_document_sequence(std::uint64_t sequence) noexcept;
    [[nodiscard]] EngineDocumentAdmission stage_document_work(EngineDocumentWork) noexcept;
    /* Repeated reads/redelivery return the same immutable owned completion,
     * never a new provider attempt. No value means pending or no such ticket.
     * A consumed native form action is retained through local presentation
     * debt until its original full identity/action receives checked ACK0/1. */
    [[nodiscard]] std::shared_ptr<const EngineDocumentCompletion>
        document_outcome(EngineDocumentTicket) const noexcept;
    [[nodiscard]] bool consume_document_outcome(EngineDocumentTicket) noexcept;
    [[nodiscard]] EngineDocumentAdmission stage_document_action_ack(
        EngineDocumentTarget, std::uint64_t original_action_sequence) noexcept;
    [[nodiscard]] EngineDocumentAdmission stage_document_body_action_ack(
        EngineDocumentTarget, std::uint64_t original_action_sequence) noexcept;
    /* Separate editor work owns its payload and complete bounded completion
     * before a driver may claim it. It shares ordinary sequence ordering with
     * document/physical work; editor8/9 have no ACK or native replay cache.
     * Immutable local completion redelivery never remints a provider call. */
    [[nodiscard]] bool editor_enabled() const noexcept;
    [[nodiscard]] const engine_editor::EngineEditorProfileFacts& editor_profile() const noexcept;
    [[nodiscard]] std::optional<std::uint64_t> reserve_editor_sequence();
    [[nodiscard]] bool cancel_editor_sequence(std::uint64_t sequence) noexcept;
    [[nodiscard]] EngineEditorAdmission stage_editor_work(EngineEditorWork) noexcept;
    [[nodiscard]] std::shared_ptr<const EngineEditorCompletion>
        editor_outcome(EngineEditorTicket) const noexcept;
    [[nodiscard]] bool consume_editor_outcome(EngineEditorTicket) noexcept;
    /* Trusted sole presenter calls this only after actual suspension/redaction
     * was successfully published. A fresh nonzero publication revision, exact
     * effect ticket/target and fully settled work/ACK barriers are required.
     * Ordinary acknowledge_native_effect cannot bypass this document gate.
     * Release still requires a fresh paired observation; no old GUI authority
     * or physical input_context is manufactured by this acknowledgement. */
    [[nodiscard]] bool acknowledge_document_native_effect(std::uint64_t ticket,
        EngineDocumentTarget target, std::uint64_t safe_publication_revision) noexcept;
    /* Graceful shutdown refuses effects until the complete native turn returns.
     * Destruction is performed only after the owning worker has stopped entry. */
    void close() noexcept;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace foundation::appended
