#pragma once

#include <foundation/gui/document_values.hpp>

#include "appended_document_controller.hpp"
#include <foundation/appended/document_forms.hpp>
#include <functional>
#include <memory>
#include <optional>
#include <variant>

namespace foundation::ui {

struct DocumentFormsRequestToken {
    std::uint64_t generation{0}, sequence{0};
    bool operator==(const DocumentFormsRequestToken&) const = default;
};
// Local generic chooser commit. The option is a held published native node ID,
// never a display ordinal or submitted form value.
struct ChooseSingleDocumentOption {
    DocumentVersion expected;
    std::uint64_t node{0}, option{0};
};
// Local activation of an actual published input button, reset or submit control.
// No form editing capability or lease is inferred from this body action.
struct ActivateDocumentControl {
    DocumentVersion expected;
    std::uint64_t node{0};
};
using DocumentFormsAction = std::variant<DocumentEngineRequest, appended::BeginFormControl,
    appended::FormDraftRequest, appended::FinishFormControl, ChooseSingleDocumentOption,
    ActivateDocumentControl>;
struct DocumentFormsRequest { DocumentFormsRequestToken token; DocumentFormsAction action; };
struct DocumentFormsControlReply {
    appended::FormDraftOutcome outcome{appended::FormDraftOutcome::unknown};
    std::optional<appended::FormUpdate> update;
};
enum class DocumentBodyOutcome { completed, needs_current_observation, rejected, indeterminate };
struct DocumentBodyCompletion {
    DocumentBodyOutcome outcome{DocumentBodyOutcome::indeterminate};
    // Actual command readback only. Its decoded body request ID is zero; the
    // compositor binds it to its exact outstanding Controller action token.
    std::optional<NativeFormsDocumentObservation> publication;
};
using DocumentFormsCompletion = std::variant<NativeFormsDocumentObservation, DocumentFormsControlReply,
    DocumentBodyCompletion>;

// One serialized compositor, presenter and global request ledger. Actual engine
// execution belongs to the owner AFTER all GUI callbacks return. The compositor
// owns no engine, HTML parser or second DOM. Its private forwarding Adapter is
// the sole Adapter supplied to its document controller; never wire another sink
// or presenter to actual while this object is alive.
//
// Native body actions require an explicitly admitted document-actions profile.
// Single select uses a local generic chooser and an explicit Apply, without a
// platform popup or widening the frozen FormDraft select-one capability.
class AppendedDocumentForms {
public:
    // Pure reservation on the serialized application owner; no engine entry.
    // nullopt means temporary backpressure, exhaustion must throw. Returned
    // nonzero values strictly increase and are used unchanged, including gaps.
    using RequestSequenceSource = std::function<std::optional<std::uint64_t>()>;
    AppendedDocumentForms(gui::Adapter& actual, std::uint64_t engine_generation, DocumentViewport);
    AppendedDocumentForms(gui::Adapter& actual, std::uint64_t engine_generation, DocumentViewport,
                          RequestSequenceSource);
    ~AppendedDocumentForms();
    AppendedDocumentForms(const AppendedDocumentForms&) = delete;
    AppendedDocumentForms& operator=(const AppendedDocumentForms&) = delete;

    void handle(gui::Event);
    void tick();
    void retry_presentation();
    void viewport(DocumentViewport);
    // Loss revokes local/native admission; restoration requests fresh state and
    // requires explicit native Refresh before saved draft Apply can be rearmed.
    void foreground(bool);
    // Explicit provider capability, false initially. Gates the local chooser
    // and host selection; the execution owner must reject ordinary Controller
    // body intents before native entry when its selected profile lacks it.
    void document_actions_available(bool);
    // Composition-owned semantic DOM endpoints; no terminal selection gesture
    // or Adapter text-selection coordinates are inferred by this method.
    bool queue_selection(DocumentSelection);
    // Readonly coalesced polling hint, safe from callbacks. Defers while a modal,
    // native work, presentation or foreground barrier exists. An existing query
    // can satisfy it; this does not promise capture-after-call for an in-flight
    // query. Does not revoke a lease, submit an edit or acknowledge native effects.
    void request_observation();
    // Coalesced local repaint only; tick publishes a fresh revision after exact
    // pending retries. No native query, authority change or effect ACK occurs.
    void request_presentation();
    std::optional<DocumentFormsRequest> next_request();
    // False: foreign/duplicate token or a failed local publication still needs
    // exact retry. Retain/redeliver the completion; NEVER repeat the engine action.
    // Matching malformed completion consumes the request as unknown.
    bool complete(DocumentFormsRequestToken, DocumentFormsCompletion);
    bool fail(DocumentFormsRequestToken, DocumentRequestFailure);
    // Safe from callbacks. Delivered native work remains an owner teardown
    // obligation; shutdown cannot undo effects or submit a last-minute Apply.
    void shutdown() noexcept;

    const gui::Snapshot& view() const noexcept;
    std::uint64_t input_epoch() const noexcept;
    bool presentation_pending() const noexcept;
    bool closed() const noexcept;
    bool body_ready() const noexcept;
    bool modal_open() const noexcept;
    // Last whole accepted paired QUERY token, not an action's readback or an
    // actual presentation acknowledgement. New native work, foreground changes
    // and shutdown revoke it; local retry preserves an accepted receipt.
    std::optional<DocumentFormsRequestToken> accepted_query() const noexcept;
    std::optional<appended::FormDraftPhase> draft_phase() const noexcept;
    std::optional<appended::FormByteSelection> local_selection() const noexcept;
    const std::string& last_error() const noexcept;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace foundation::ui
