// SPDX-License-Identifier: CC0-1.0
#pragma once

#include "appended_engine_owner.hpp"
#include "appended_document_v2_codec.hpp"
#include "document_action_v1_codec.hpp"
#include <foundation/gui/document_endpoint.hpp>
#include <functional>
#include <memory>
#include <optional>
#include <utility>

namespace foundation::ui {

// Shared local draft/recovery composition. FormDraft remains the only edit
// state machine; this owner has no Adapter, engine entry or lease issuer.
class EngineDocumentDraftSession final {
public:
    enum class RecoveryProgress { idle, pending, completed, blocked };
    using Publish = appended::FormDraft::Publish;
    EngineDocumentDraftSession(std::uint64_t, appended::FormUpdate, Publish,
                               appended::FormLimits = {});
    ~EngineDocumentDraftSession();
    EngineDocumentDraftSession(const EngineDocumentDraftSession&) = delete;
    EngineDocumentDraftSession& operator=(const EngineDocumentDraftSession&) = delete;
    const appended::FormDraftView& view() const noexcept;
    std::uint64_t generation() const noexcept;
    bool handle(appended::FormDraftEvent);
    bool selection(appended::FormByteSelection);
    std::optional<appended::FormDraftRequest> next_request();
    bool complete(appended::FormDraftToken, appended::FormDraftOutcome,
                  std::optional<appended::FormUpdate> = {});
    bool observe(appended::FormUpdate);
    void retry_publication();
    bool request_pending() const noexcept;
    void close() noexcept;
    bool recover(appended::FormDraftView, appended::FormUpdate, bool reapply);
    bool recovery_generation(std::uint64_t) noexcept;
    RecoveryProgress advance_recovery(const std::function<bool()>& presentation_clear);
    void cancel_recovery() noexcept;
    bool recovery_pending() const noexcept;
    bool recovery_install_pending() const noexcept;
    bool recovery_blocked() const noexcept;
    const appended::FormDraftView* recovery_saved() const noexcept;
    const appended::FormUpdate* recovery_fresh() const noexcept;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

class AppendedEngineApplication;
class AppendedEngineDocumentApplication;
struct EngineDocumentBrokerTestAccess;

// One serialized application-side document ledger. Owner issues every native
// target, sequence, ticket and transfer. Public intents contain no native lease,
// wire bytes or native operation selector. tick only stages/polls Owner metadata;
// the existing bridge performs native entry after callbacks have returned.
class EngineDocumentBroker final {
public:
    EngineDocumentBroker(std::shared_ptr<appended::EngineOwner>,
        const appended::engine_document::EngineDocumentProfileFacts&);
    EngineDocumentBroker(std::shared_ptr<appended::EngineOwner>,
        const appended::engine_editor::EngineEditorProfileFacts&);
    ~EngineDocumentBroker();
    EngineDocumentBroker(const EngineDocumentBroker&) = delete;
    EngineDocumentBroker& operator=(const EngineDocumentBroker&) = delete;
    gui_document::Submission submit(gui_document::Intent);
    std::optional<gui_document::Completion> take(gui_document::Ticket);
    gui_document::State state() const;
    void tick();
    void shutdown() noexcept;
    void notify_terminal() noexcept;
    bool pending() const noexcept;
    bool terminal() const noexcept;

    struct Publication final {
        const std::uint64_t serial;
        const gui_document::State state;
    private:
        friend class EngineDocumentBroker;
        Publication(std::uint64_t value, gui_document::State content)
            : serial(value), state(std::move(content)) {}
    };
    using Candidate = Publication;
    enum class CommitKind { normal, safe_redaction };
    enum class Suspension { service, navigation, foreground_loss, closing };

private:
    friend class AppendedEngineApplication;
    friend class AppendedEngineDocumentApplication;
    // Unit tests exercise this same trusted metadata seam, never a raw engine
    // input or failure-injection operation. It is not an installed interface.
    friend struct EngineDocumentBrokerTestAccess;
    std::shared_ptr<const Publication> publication_candidate() const;
    bool publication_committed(std::shared_ptr<const Publication>,
                               std::uint64_t actual_snapshot_revision, CommitKind);
    void suspend(Suspension);
    void form_admission_ready(bool) noexcept;
    bool native_effect_quiescent() const noexcept;
    bool form_gate_required() const noexcept;

    // Trusted terminal compositor binding. It retains its existing local
    // request/publication ledger and4083 presentation. This is never reachable
    // through JSON; typed body codecs are supplied only by that admitted App.
    struct LegacyBindings {
        std::function<std::optional<DocumentFormsRequest>()> next;
        std::function<bool(DocumentFormsRequestToken,DocumentFormsCompletion)> complete;
        std::function<bool(DocumentFormsRequestToken,DocumentRequestFailure)> fail;
        std::function<void()> progress;
        std::function<bool()> presentation_pending;
        std::function<bool()> can_stage;
        std::function<bool()> fresh_query;
        std::function<std::uint64_t()> barrier;
        std::function<void(DocumentFormsRequestToken,appended::EngineDocumentTarget,
                           std::uint64_t,bool)> query_delivered;
        std::function<void(const char*)> failure;
        std::function<void(const char*)> rejection;
        std::function<std::optional<DocumentActionV1Request>(const DocumentFormsRequest&,
            appended::EngineDocumentTarget,std::uint64_t)> encode_body;
        std::function<DocumentBodyCompletion(std::span<const std::uint8_t>,
            const DocumentActionV1Request&)> decode_body;
        std::function<bool(std::span<const std::uint8_t>,std::uint64_t)> body_ack;
    };
    EngineDocumentBroker(std::shared_ptr<appended::EngineOwner>, LegacyBindings);
    std::optional<std::uint64_t> reserve_legacy();
    void cancel_legacy_reservation() noexcept;
    void retire_legacy_unadmitted() noexcept;
    void settle_legacy();
    void stage_legacy();
    bool legacy_pending() const noexcept;
    bool legacy_has_work() const noexcept;
    bool legacy_unadmitted() const noexcept;

    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace foundation::ui
