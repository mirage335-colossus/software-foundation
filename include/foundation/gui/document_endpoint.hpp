// SPDX-License-Identifier: CC0-1.0
#pragma once

#include <foundation/gui/document_values.hpp>
#include <cstdint>
#include <memory>
#include <optional>
#include <string>
#include <variant>

namespace foundation::gui_document {
struct Observation { std::uint64_t value{}; bool operator==(const Observation&) const = default; };
struct Draft { std::uint64_t value{}; bool operator==(const Draft&) const = default; };
struct Ticket { std::uint64_t value{}; bool operator==(const Ticket&) const = default; };
// Every handle is issued by this application endpoint and resolved through its
// retained ledger. A caller can only echo a returned handle. Numeric coincidence
// with a native lease, native token or Owner sequence confers no authority.
struct Observe {};
struct Begin { Observation observation; std::uint64_t node{}; };
struct EditText { Draft draft; std::string base_text, text; };
struct SelectText { Draft draft; appended::FormByteSelection selection; };
struct SetChecked { Draft draft; bool checked{}; };
struct SetOption { Draft draft; std::uint64_t node{}; bool selected{}; };
struct Apply { Draft draft; };
struct Reload { Draft draft; };
struct Reapply { Draft draft; };
struct Cancel { Draft draft; };
struct Finish { Draft draft; };
using Intent = std::variant<Observe,Begin,EditText,SelectText,SetChecked,SetOption,
                            Apply,Reload,Reapply,Cancel,Finish>;
enum class Admission { accepted,busy,unavailable,stale,invalid,limit,closed };
struct Submission { Admission admission{Admission::unavailable}; std::optional<Ticket> ticket; };
enum class Phase { idle,queued,waiting_native,waiting_publication,waiting_ack,waiting_take,terminal };
enum class Outcome { completed,rejected,cancelled,unknown };
struct DraftView {
    Draft id;
    appended::FormKind kind{appended::FormKind::unsupported};
    appended::FormDraftPhase phase{appended::FormDraftPhase::unavailable};
    std::string text;
    appended::FormByteSelection selection;
    bool checked{}, dirty{}, apply_queued{};
    std::optional<appended::FormOptionDraft> option;
    // Deliberately no FormLease, native id, target, native sequence or bytes.
};
struct State {
    std::uint32_t version{1};
    // Actual sole-presenter revision for the last accepted content below; zero
    // means none. It is not a native version, query sequence or public ACK.
    std::uint64_t publication_revision{0};
    // Live eligibility/work metadata may change after native ACK or local Take
    // without replacing the last accepted observation, draft or document.
    bool available{};
    Phase phase{Phase::idle};
    // Last accepted publication content. Failed/queued presentation preserves
    // these values and publication_revision until the exact commit succeeds.
    std::optional<Observation> observation;
    std::optional<DraftView> draft;
    // Live local request metadata, separate from accepted content.
    std::optional<Ticket> pending;
    // Immutable actual native observation, not an editable model. The concrete
    // public leaf retains the complete existing type. No output is resubmitted whole.
    std::shared_ptr<const ui::NativeFormsDocumentObservation> document;
};
struct Completion {
    Ticket ticket;
    Outcome outcome{Outcome::unknown};
    std::optional<Observation> observation;
    std::optional<DraftView> draft;
    std::string detail; // bounded diagnostic, never an authority token
};
struct TerminalHook {
    void* context{};
    // Trusted metadata-only poison notification, including foreign-thread
    // failure. No engine entry, allocation, cleanup or synthetic completion.
    void (*notify)(void*) noexcept{};
};
// Exact application hook signatures; generic session code copies values only.
// document_take consumes only local known-complete metadata after publication
// and native ACK retirement. It cannot publish or ACK provider work itself.
// Submission document_submit(Intent);
// std::optional<Completion> document_take(Ticket);
// State document_state() const; // paired with the accepted GUI publication
// TerminalHook document_terminal() noexcept;
// All four hooks bind one capability; partial binding must fail closed.
}

