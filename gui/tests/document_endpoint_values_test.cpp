// SPDX-License-Identifier: CC0-1.0
// Public value/header contract only. No broker, native owner or provider runs.
#include <foundation/gui/document_endpoint.hpp>
#include <foundation/gui/document_values.hpp>

// Existing consumers must retain the identical types through these forwards.
#include "shared/appended_document.hpp"
#include "shared/appended_document_codec.hpp"
#include "shared/appended_document_forms.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <limits>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>
#include <variant>

namespace {
namespace D = foundation::gui_document;
namespace F = foundation::appended;
namespace U = foundation::ui;
constexpr std::uint64_t large = 9007199254740993ULL;
std::size_t checks{};

using ExpectedIntent = std::variant<D::Observe, D::Begin, D::EditText, D::SelectText,
    D::SetChecked, D::SetOption, D::Apply, D::Reload, D::Reapply, D::Cancel, D::Finish>;
static_assert(std::is_same_v<D::Intent, ExpectedIntent>);
static_assert(std::variant_size_v<D::Intent> == 11);
static_assert(std::is_same_v<decltype(D::State{}.publication_revision), std::uint64_t>);
static_assert(std::is_same_v<decltype(D::State{}.document),
    std::shared_ptr<const U::NativeFormsDocumentObservation>>);
static_assert(std::is_same_v<decltype(U::NativeFormsDocumentObservation{}.body), U::DocumentSemanticReply>);
static_assert(std::is_same_v<decltype(U::NativeFormsDocumentObservation{}.forms), F::DocumentFormsSnapshot>);
static_assert(std::is_same_v<decltype(U::DocumentSemanticReply{}.snapshot), std::optional<U::DocumentSnapshot>>);
static_assert(std::is_same_v<decltype(U::DocumentProjection{}.version), U::DocumentVersion>);
static_assert(std::is_same_v<decltype(U::DocumentBodyCompletion{}.publication),
    std::optional<U::NativeFormsDocumentObservation>>);
static_assert(std::is_same_v<decltype(std::declval<const U::AppendedDocument&>().snapshot()),
    const U::DocumentSnapshot*>);
static_assert(sizeof(U::NativeFormsDocumentObservation) > 0);
static_assert(std::is_copy_constructible_v<U::NativeFormsDocumentObservation>);
static_assert(std::is_aggregate_v<D::State> && std::is_aggregate_v<D::Completion>);
static_assert(std::is_aggregate_v<D::DraftView> && !std::is_abstract_v<D::DraftView>);
using TerminalNotification = void (*)(void*) noexcept;
static_assert(std::is_standard_layout_v<D::TerminalHook> && std::is_trivially_copyable_v<D::TerminalHook>);
static_assert(std::is_same_v<decltype(D::TerminalHook{}.context), void*>);
static_assert(std::is_same_v<decltype(D::TerminalHook{}.notify), TerminalNotification>);
static_assert(!std::is_convertible_v<std::uint64_t, D::Observation>);
static_assert(!std::is_convertible_v<D::Observation, D::Draft>);
static_assert(!std::is_convertible_v<D::Draft, D::Ticket>);
static_assert(D::Observation{large} == D::Observation{large});
static_assert(D::Draft{large} != D::Draft{large + 1});

void check(bool condition, const char* message) {
    ++checks;
    if (!condition) throw std::runtime_error(message);
}

void endpoint_defaults() {
    const D::State state;
    check(state.version == 1 && state.publication_revision == 0,
          "A new endpoint state must have no accepted GUI publication");
    check(!state.available && state.phase == D::Phase::idle && !state.pending,
          "A new endpoint state advertised live work or availability");
    check(!state.observation && !state.draft && !state.document,
          "A new endpoint state invented accepted content");
    const D::Submission submission;
    check(submission.admission == D::Admission::unavailable && !submission.ticket,
          "A default submission invented admission or a ticket");
    const D::Completion completion;
    check(completion.outcome == D::Outcome::unknown && !completion.observation
          && !completion.draft && completion.detail.empty(), "A default completion invented an outcome");
    const D::TerminalHook terminal;
    check(terminal.context == nullptr && terminal.notify == nullptr,
          "A default terminal hook invented a callback or context");
}

void draft_shape() {
    D::DraftView draft;
    // Exactly nine fields: adding any native authority field breaks this shape.
    auto& [id, kind, phase, text, selection, checked, dirty, apply_queued, option] = draft;
    static_assert(std::is_same_v<decltype(id), D::Draft>);
    static_assert(std::is_same_v<decltype(kind), F::FormKind>);
    static_assert(std::is_same_v<decltype(phase), F::FormDraftPhase>);
    static_assert(std::is_same_v<decltype(text), std::string>);
    static_assert(std::is_same_v<decltype(selection), F::FormByteSelection>);
    static_assert(std::is_same_v<decltype(checked), bool> && std::is_same_v<decltype(dirty), bool>
                  && std::is_same_v<decltype(apply_queued), bool>);
    static_assert(std::is_same_v<decltype(option), std::optional<F::FormOptionDraft>>);
    check(id == D::Draft{} && kind == F::FormKind::unsupported
          && phase == F::FormDraftPhase::unavailable, "A default draft invented editable native state");
    check(text.empty() && selection == F::FormByteSelection{} && !checked && !dirty
          && !apply_queued && !option, "A default draft invented local input");
    id = D::Draft{large}; text = "saved local input"; dirty = true;
    check(draft.id.value == large && draft.text == "saved local input" && draft.dirty,
          "Draft fields did not retain their owned local values");
}

void intent_values() {
    const D::Observation observation{large};
    const D::Draft draft{large + 1};
    std::string before = "old text", after = "new \xf0\x9f\x99\x82 text";
    std::array<D::Intent, 11> intents{D::Observe{}, D::Begin{observation, large + 2},
        D::EditText{draft, before, after}, D::SelectText{draft, {2, 6}},
        D::SetChecked{draft, true}, D::SetOption{draft, large + 3, true},
        D::Apply{draft}, D::Reload{draft}, D::Reapply{draft}, D::Cancel{draft}, D::Finish{draft}};
    before.clear(); after.clear();
    for (std::size_t index = 0; index < intents.size(); ++index)
        check(intents[index].index() == index, "An endpoint intent changed its declared alternative");
    check(std::get<D::Begin>(intents[1]).observation == observation
          && std::get<D::Begin>(intents[1]).node == large + 2, "Begin lost its returned handle or node");
    const auto& edit = std::get<D::EditText>(intents[2]);
    check(edit.draft == draft && edit.base_text == "old text" && edit.text == "new \xf0\x9f\x99\x82 text",
          "EditText did not own both input strings");
    check(std::get<D::SelectText>(intents[3]).selection == F::FormByteSelection{2, 6},
          "SelectText changed source-byte selection");
    check(std::get<D::SetChecked>(intents[4]).checked
          && std::get<D::SetOption>(intents[5]).node == large + 3
          && std::get<D::SetOption>(intents[5]).selected, "Form intents changed their owned values");
    for (std::size_t index = 2; index < intents.size(); ++index) {
        const auto handle = std::visit([](const auto& value) -> D::Draft {
            if constexpr (requires { value.draft; }) return value.draft;
            else return {};
        }, intents[index]);
        check(handle == draft, "A draft intent lost its exact returned handle");
    }
}

// Synthetic structural values cover retained fields and lifetime only. The
// deliberately combined flags/selection are not a valid NDV2 publication claim;
// no native codec, validation, paired-publication or broker behavior is tested.
U::NativeFormsDocumentObservation observation_value_fixture() {
    U::NativeFormsDocumentObservation result;
    result.publication = {large + 1, large + 2, large + 3};
    auto& body = result.body;
    body.request_id = large + 4; body.epoch = large + 2;
    U::DocumentSnapshot snapshot;
    snapshot.version = {large + 1, large + 2, large + 3};
    U::DocumentNode root; root.id = 11; root.tag = "body";
    U::DocumentNode text; text.id = 12; text.parent = 11;
    text.kind = U::DocumentNodeKind::text; text.text = "A\xf0\x9f\x99\x82Z";
    text.white_space = U::DocumentWhiteSpace::pre_wrap;
    snapshot.nodes = {root, text}; snapshot.active_node = 12;
    snapshot.selection = U::DocumentSelection{{12, 1}, {12, 3}}; snapshot.truncated = true;
    body.snapshot = std::move(snapshot); body.editor_state = U::DocumentEditorState{23, 7};
    body.metadata.push_back({12, "textbox", "block", "pre-wrap", true, false});
    U::DocumentWireSelection original;
    original.endpoints = {{12, 1, U::DocumentNativeOffsetKind::text_utf16},
                          {11, 1, U::DocumentNativeOffsetKind::element_child_index}};
    original.focus_rect = {2, 3, 4, 5}; body.original_selection = original;
    body.degraded = {true, true, true};
    result.forms.version = result.publication;
    F::FormControl text_control;
    text_control.node = 13; text_control.kind = F::FormKind::textarea;
    text_control.native_type = "textarea"; text_control.label = "Notes";
    text_control.focusable = true; text_control.focused = true; text_control.complete = true;
    text_control.capabilities = F::form_capability(F::FormCapability::replace_text);
    text_control.state = F::FormTextState{"native text", "editing text",
        F::FormControlRange{1, 4, F::FormDirection::backward}};
    text_control.lease = F::FormLease{result.publication, 13, std::numeric_limits<std::uint64_t>::max()};
    F::FormControl options;
    options.node = 14; options.kind = F::FormKind::select_many; options.label = "Choices";
    options.complete = true; options.focusable = true;
    options.state = F::FormSelectState{true, false, {{21, "first", true, false, false},
                                                  {22, "second", false, true, true}}};
    result.forms.controls = {std::move(text_control), std::move(options)};
    return result;
}

D::State retained_state() {
    auto source = observation_value_fixture();
    D::State result;
    result.document = std::make_shared<const U::NativeFormsDocumentObservation>(source);
    source.publication.revision = 0;
    source.body.snapshot->nodes[1].text = "producer changed";
    source.body.metadata[0].role.clear();
    std::get<F::FormTextState>(source.forms.controls[0].state).editing_text.clear();
    source.forms.controls[0].lease.reset();
    std::get<F::FormSelectState>(source.forms.controls[1].state).options[0].label.clear();
    return result; // The mutable source and all its storage are destroyed here.
}

void owned_complete_observation() {
    const auto state = retained_state();
    const auto& value = *state.document;
    check(value.protocol == F::document_forms_version && value.publication.revision == large + 3
          && value.forms.protocol == F::document_forms_version && value.forms.version == value.publication,
          "Complete native publication/form versions were not retained");
    const auto& body = value.body;
    check(body.request_id == large + 4 && body.epoch == large + 2 && body.error_code.empty(),
          "Owned body correlation values changed");
    check(body.snapshot && body.snapshot->nodes.size() == 2 && body.snapshot->version.revision == large + 3
          && body.snapshot->nodes[1].text == "A\xf0\x9f\x99\x82Z"
          && body.snapshot->nodes[1].white_space == U::DocumentWhiteSpace::pre_wrap,
          "Owned body nodes or content version changed with producer storage");
    check(body.snapshot->active_node == 12 && body.snapshot->selection == U::DocumentSelection{{12, 1}, {12, 3}}
          && body.snapshot->truncated, "Body selection/truncation metadata was dropped");
    check(body.editor_state && body.editor_state->revision == 23 && body.editor_state->flags == 7
          && body.metadata.size() == 1 && body.metadata[0].role == "textbox"
          && body.metadata[0].display == "block" && body.metadata[0].white_space == "pre-wrap"
          && body.metadata[0].read_only, "Complete semantic metadata was dropped");
    check(body.original_selection && body.original_selection->endpoints.focus.kind
          == U::DocumentNativeOffsetKind::element_child_index && body.original_selection->focus_rect.width == 4
          && body.degraded.whitespace && body.degraded.element_selection && body.degraded.truncated_selection,
          "Original native selection/geometry/degradation was replaced by a narrow caret");
    check(value.forms.controls.size() == 2 && value.forms.controls[0].label == "Notes",
          "Owned form controls were dropped");
    const auto& text = std::get<F::FormTextState>(value.forms.controls[0].state);
    check(text.value == "native text" && text.editing_text == "editing text"
          && text.selection == F::FormControlRange{1, 4, F::FormDirection::backward},
          "Native form text or selection borrowed producer storage");
    const auto& lease = value.forms.controls[0].lease;
    check(lease && lease->captured == value.publication && lease->node == 13
          && lease->id == std::numeric_limits<std::uint64_t>::max(),
          "Immutable observed native lease data was narrowed or dropped");
    const auto& options = std::get<F::FormSelectState>(value.forms.controls[1].state);
    check(options.multiple && !options.menu_list && options.options.size() == 2
          && options.options[0] == F::FormOption{21, "first", true, false, false}
          && options.options[1] == F::FormOption{22, "second", false, true, true},
          "Complete owned native option observations changed with producer storage");
}

void publication_and_live_metadata() {
    auto accepted = retained_state();
    accepted.publication_revision = large + 10;
    accepted.observation = D::Observation{large + 11};
    accepted.draft = D::DraftView{}; accepted.draft->id = D::Draft{large + 12};
    accepted.draft->text = "saved input"; accepted.available = true;
    auto live = accepted;
    live.available = false; live.phase = D::Phase::waiting_ack; live.pending = D::Ticket{large + 13};
    check(live.publication_revision == large + 10 && live.publication_revision != live.document->publication.revision
          && live.document->body.snapshot->version.revision == large + 3,
          "GUI publication revision was confused with native content revision");
    check(live.document == accepted.document && live.observation == accepted.observation
          && live.draft->id == accepted.draft->id && live.draft->text == "saved input",
          "Live metadata changes replaced accepted content");
    check(accepted.available && accepted.phase == D::Phase::idle && !accepted.pending
          && !live.available && live.phase == D::Phase::waiting_ack && live.pending == D::Ticket{large + 13},
          "Copied endpoint states aliased live work metadata");
    live.pending.reset(); live.phase = D::Phase::idle;
    check(live.publication_revision == accepted.publication_revision && live.document == accepted.document,
          "Clearing local pending metadata changed retained publication identity");
}
} // namespace

int main() {
    try {
        endpoint_defaults(); draft_shape(); intent_values();
        owned_complete_observation(); publication_and_live_metadata();
        std::cout << "document endpoint values: " << checks
                  << " assertions passed; header/value contract only, no broker or native execution\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << " (completed assertions=" << checks << ")\n";
        return 1;
    }
}
