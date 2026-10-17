#pragma once

#include <cstddef>
#include <cstdint>
#include <functional>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <variant>
#include <vector>

namespace foundation::appended {

inline constexpr std::uint32_t document_forms_version = 2;
struct FormLimits {
    std::size_t controls{2048}, options{2048}, field_utf16{2048}, total_utf16{65536};
};
struct FormVersion {
    // Immutable publication identity. A v2 producer advances a nonwrapping
    // revision for newly captured native state, including property-only changes
    // missed by DOM observers. The generation is issued by the composition owner.
    std::uint64_t generation{0}, epoch{0}, revision{0};
    bool operator==(const FormVersion&) const = default;
};
enum class FormDirection { none, forward, backward };
// Native control editing text offsets, NEVER DOM node offsets or display cells.
struct FormControlRange {
    std::uint32_t start{0}, end{0};
    FormDirection direction{FormDirection::none};
    bool operator==(const FormControlRange&) const = default;
};
// GUI text APIs use UTF-8 source bytes, including on terminals rendering escapes.
struct FormByteSelection {
    std::size_t anchor{0}, caret{0};
    bool operator==(const FormByteSelection&) const = default;
};
FormControlRange form_control_range(std::string_view, FormByteSelection);
FormByteSelection form_byte_selection(std::string_view, FormControlRange);

enum class FormKind { text, number, textarea, checkbox, select_one,
                      select_many, secure_readonly, unsupported };
enum class FormCapability : std::uint32_t {
    replace_text = 1, set_checked = 2, open_popup = 4, set_option = 8, finish = 16
};
using FormCapabilities = std::uint32_t;
constexpr FormCapabilities form_capability(FormCapability value) noexcept {
    return static_cast<FormCapabilities>(value);
}
constexpr bool form_has(FormCapabilities values, FormCapability value) noexcept {
    return (values & form_capability(value)) != 0;
}
// Issued by the engine after native focus and exact control-state capture.
// The opaque id refers to private native state, NOT a hash/value on the wire.
struct FormLease {
    FormVersion captured;
    std::uint64_t node{0}, id{0};
    bool operator==(const FormLease&) const = default;
};
struct FormTextState {
    std::string value, editing_text; // numeric value may differ from inner text
    std::optional<FormControlRange> selection;
    bool operator==(const FormTextState&) const = default;
};
struct FormCheckState {
    bool checked{false}, indeterminate{false};
    bool operator==(const FormCheckState&) const = default;
};
struct FormOption {
    std::uint64_t node{0};
    std::string label;
    bool selected{false}, disabled{false}, omitted{false};
    bool operator==(const FormOption&) const = default;
};
struct FormSelectState {
    bool multiple{false}, menu_list{false};
    std::vector<FormOption> options;
    bool operator==(const FormSelectState&) const = default;
};
using FormState = std::variant<std::monostate, FormTextState, FormCheckState, FormSelectState>;
struct FormControl {
    std::uint64_t node{0};
    FormKind kind{FormKind::unsupported};
    std::string native_type, label;
    bool disabled{false}, read_only{false}, focusable{false}, focused{false}, omitted{false}, complete{false};
    // Native supported operations can be advertised BEFORE Begin issues a lease.
    // Support alone grants no lease-bound action authority.
    FormCapabilities capabilities{0};
    FormState state;
    std::optional<FormLease> lease;
    bool operator==(const FormControl&) const = default;
};
struct FormUpdate {
    FormVersion version;
    FormControl control;
    bool operator==(const FormUpdate&) const = default;
};
struct DocumentFormsSnapshot {
    std::uint32_t protocol{document_forms_version};
    FormVersion version;
    std::vector<FormControl> controls;
};
// Strict bounded owned-value validation; invalid input throws invalid_argument.
// Secure controls carry only monostate and no authority. Incomplete, omitted,
// disabled, readonly or unfocusable controls cannot grant editing capabilities.
// This validates observations, not live native state or an engine action.
void validate_document_forms(const DocumentFormsSnapshot&, FormLimits = {});
void validate_form_update(const FormUpdate&, FormLimits = {});
// Exact compared observation state excluding only the opaque lease identity.
// Engines must re-read native state; this pure comparison is not a native guard.
bool form_control_state_matches(const FormControl&, const FormControl&);

struct BeginFormControl { FormVersion expected; std::uint64_t node{0}; };
struct ReplaceFormText { FormLease expected; FormControlRange range; std::string text; };
struct SetFormChecked { FormLease expected; bool checked{false}; };
struct SetFormOption { FormLease expected; std::uint64_t option{0}; bool selected{false}; };
struct OpenFormPopup { FormVersion expected; std::uint64_t node{0}; };
struct FinishFormControl { FormLease expected; };
// Popup accept/cancel belong to the shared native PopupMenu contract. An open
// action alone never authorizes choosing a stale index or submitted option value.
using FormAction = std::variant<BeginFormControl, ReplaceFormText, SetFormChecked,
    SetFormOption, OpenFormPopup, FinishFormControl>;
struct FormDraftToken {
    std::uint64_t generation{0}, sequence{0};
    bool operator==(const FormDraftToken&) const = default;
};
struct FormDraftRequest { FormDraftToken token; FormAction action; };
enum class FormDraftPhase { editing, pending, stale, unknown, unavailable, closed };
enum class FormDraftOutcome { accepted, rejected, unknown };
struct FormOptionDraft { std::uint64_t node{0}; bool selected{false}; };
struct FormDraftView {
    std::uint64_t revision{0};
    FormDraftPhase phase{FormDraftPhase::unavailable};
    FormUpdate base;
    std::optional<FormUpdate> latest;
    std::string text;
    FormByteSelection selection;
    bool checked{false};
    std::optional<FormOptionDraft> option;
    bool dirty{false}, apply_queued{false}, publication_pending{false};
};
struct EditFormDraft { std::string base_text, text; };
struct CheckFormDraft { bool checked{false}; };
// Multiple-select phase one edits ONE native option per Apply, never a set/batch.
struct OptionFormDraft { std::uint64_t node{0}; bool selected{false}; };
struct ApplyFormDraft {};
struct ReloadFormDraft {};
struct ReapplyFormDraft {};
struct CancelFormDraft {};
using FormDraftEvent = std::variant<EditFormDraft, CheckFormDraft, OptionFormDraft,
    ApplyFormDraft, ReloadFormDraft, ReapplyFormDraft, CancelFormDraft>;

// A bounded unsaved user-input buffer on ONE serialized composition owner. It owns no Adapter,
// HTML/JS engine, second DOM, event loop, transport, or native action callback.
// Publish synchronously installs ONLY a small LOCAL modal view; the owner maps
// it to its single generic GUI snapshot. This is needed for terminal batched
// typing, whose retained caret advances only after exact candidate publication.
// Publish may throw: constructor/handle/drain retain the candidate, mark it
// pending, and block input/Apply until retry_publication succeeds. Explicit retry
// propagates callback failure. No failed publication can arm an engine request.
// Do not destroy this object from Publish; recursive mutation is rejected.
class FormDraft {
public:
    // Bounds the no-reuse ledger. Exhaustion leaves a recoverable readonly draft;
    // a new explicit native Begin/session is required, never a recycled lease.
    static constexpr std::size_t max_retired_leases = 2048;
    using Publish = std::function<void(const FormDraftView&)>;
    FormDraft(std::uint64_t draft_generation, FormUpdate, Publish, FormLimits = {});
    ~FormDraft();
    FormDraft(const FormDraft&) = delete;
    FormDraft& operator=(const FormDraft&) = delete;

    bool handle(FormDraftEvent);
    // Poll the GUI's final source-byte selection after its callback returns.
    // Selection may be updated while Apply is queued, before next_request(). It
    // belongs to the LOCAL draft. Initial full-buffer Apply uses the native
    // editor's resulting caret, with no post-Apply selection-restoration claim.
    bool selection(FormByteSelection);
    // Must be drained AFTER all GUI callbacks return. Never calls an engine.
    // One outstanding request; no returned action is automatically retried.
    std::optional<FormDraftRequest> next_request();
    // Foreign/duplicate tokens or a pending local publication return false
    // without consuming the request. The owner retains a completion until the
    // exact publication retry succeeds; it must not repeat the engine action.
    // Accepted completions require actual native readback. Malformed
    // matching readback consumes the request as unknown and throws.
    bool complete(FormDraftToken, FormDraftOutcome, std::optional<FormUpdate> = {});
    // Fresh observation does not silently rebase/submit a saved user draft.
    // Reapply/Reload are explicit events and require a fresh lease after failure.
    bool observe(FormUpdate);
    void retry_publication();
    void close() noexcept;
    const FormDraftView& view() const noexcept;
    bool request_pending() const noexcept;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace foundation::appended
