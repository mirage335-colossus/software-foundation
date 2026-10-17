#include "foundation/appended/document_forms.hpp"

#include <algorithm>
#include <cstdint>
#include <functional>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace {
using namespace foundation::appended;

void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
template<class Action>
void invalid(Action action, const char* message) {
    try { action(); }
    catch (const std::invalid_argument&) { return; }
    throw std::runtime_error(message);
}
constexpr FormVersion version{7,11,13};
constexpr FormCapabilities text_capabilities = form_capability(FormCapability::replace_text) |
    form_capability(FormCapability::finish);

FormUpdate text_control(std::string editing = "a", FormKind kind = FormKind::text,
                        std::uint64_t lease = 101, FormVersion observed = version) {
    FormControl control;
    control.node = 1; control.kind = kind;
    control.native_type = kind == FormKind::number ? "number" :
        kind == FormKind::textarea ? "textarea" : "text";
    control.focusable = true; control.focused = true; control.complete = true; control.capabilities = text_capabilities;
    const auto range = form_control_range(editing,{editing.size(),editing.size()});
    control.state = FormTextState{editing,editing,range};
    control.lease = FormLease{observed,control.node,lease};
    return {observed,std::move(control)};
}
FormUpdate checked_control(bool checked = false, std::uint64_t lease = 201,
                           FormVersion observed = version) {
    FormControl control;
    control.node = 2; control.kind = FormKind::checkbox; control.native_type = "checkbox";
    control.focusable = true; control.focused = true; control.complete = true;
    control.capabilities = form_capability(FormCapability::set_checked) |
        form_capability(FormCapability::finish);
    control.state = FormCheckState{checked,true};
    control.lease = FormLease{observed,control.node,lease};
    return {observed,std::move(control)};
}
FormUpdate select_control(bool multiple = true, std::uint64_t lease = 301,
                          FormVersion observed = version) {
    FormControl control;
    control.node = multiple ? 3 : 4;
    control.kind = multiple ? FormKind::select_many : FormKind::select_one;
    control.native_type = multiple ? "select-multiple" : "select-one";
    control.focusable = true; control.focused = true; control.complete = true;
    control.capabilities = form_capability(multiple ? FormCapability::set_option :
        FormCapability::open_popup) | form_capability(FormCapability::finish);
    // Identical labels must not collapse distinct native option identities.
    control.state = FormSelectState{multiple,!multiple,
        {{31,"Same label",true,false,false},{32,"Same label",false,false,false},
         {33,"Disabled",false,true,false},{34,"Omitted",false,false,true}}};
    if (!multiple)
        for (auto& option : std::get<FormSelectState>(control.state).options) option.node += 10;
    control.lease = FormLease{observed,control.node,lease};
    return {observed,std::move(control)};
}
DocumentFormsSnapshot snapshot(FormUpdate update = text_control()) {
    return {document_forms_version,update.version,{std::move(update.control)}};
}
const FormTextState& text_state(const FormUpdate& update) {
    return std::get<FormTextState>(update.control.state);
}

void unicode_source_offsets() {
    // A, U+1F600, e, U+0301, Z: 9 UTF-8 bytes, 6 UTF-16 units.
    const std::string text = "A\xF0\x9F\x98\x80" "e\xCC\x81" "Z";
    const std::vector<std::pair<std::size_t,std::uint32_t>> boundaries{
        {0,0},{1,1},{5,3},{6,4},{8,5},{9,6}};
    for (const auto& [bytes,units] : boundaries) {
        require(form_control_range(text,{bytes,bytes}) == FormControlRange{units,units,FormDirection::none},
            "Collapsed GUI source offsets did not map to native UTF-16 boundaries");
        require(form_byte_selection(text,{units,units,FormDirection::none}) == FormByteSelection{bytes,bytes},
            "Collapsed native UTF-16 offsets did not map to GUI source bytes");
    }
    require(form_control_range(text,{8,1}) == FormControlRange{1,5,FormDirection::backward} &&
        form_byte_selection(text,{1,5,FormDirection::backward}) == FormByteSelection{8,1},
        "Backward astral/combining selection lost direction or source boundaries");
    require(form_control_range(text,{1,8}) == FormControlRange{1,5,FormDirection::forward} &&
        form_byte_selection(text,{1,5,FormDirection::forward}) == FormByteSelection{1,8},
        "Forward source selection counted glyphs, cells or Unicode scalars instead of UTF-16");
    for (const auto offset : {2u,3u,4u,7u})
        invalid([&] { (void)form_control_range(text,{offset,8}); },
            "A GUI selection inside a UTF-8 scalar was accepted");
    invalid([&] { (void)form_control_range(text,{0,10}); },"Out-of-range GUI selection was accepted");
    invalid([&] { (void)form_byte_selection(text,{1,2,FormDirection::forward}); },
        "A native selection splitting a surrogate pair was accepted");
    invalid([&] { (void)form_byte_selection(text,{3,1,FormDirection::forward}); },
        "A native selection with reversed sorted endpoints was accepted");
    invalid([&] { (void)form_byte_selection(text,{0,7,FormDirection::forward}); },
        "An out-of-range native selection was accepted");
    const std::vector<std::string> malformed{
        std::string("\x80"), std::string("\xC0\xAF"), std::string("\xE2\x82"),
        std::string("\xED\xA0\x80"), std::string("\xF4\x90\x80\x80")};
    for (const auto& value : malformed) {
        invalid([&] { (void)form_control_range(value,{0,0}); },
            "Malformed UTF-8 was accepted by byte-to-native conversion");
        invalid([&] { (void)form_byte_selection(value,{0,0,FormDirection::none}); },
            "Malformed UTF-8 was accepted by native-to-byte conversion");
    }
}

void typed_observations_and_authority() {
    auto all = snapshot();
    auto number = text_control("-",FormKind::number);
    number.control.node = 5; number.control.lease->node = 5;
    std::get<FormTextState>(number.control.state).value.clear();
    auto textarea = text_control("first\nsecond",FormKind::textarea);
    textarea.control.node = 6; textarea.control.lease->node = 6;
    all.controls.push_back(number.control); all.controls.push_back(textarea.control);
    all.controls.push_back(checked_control().control);
    all.controls.push_back(select_control().control); all.controls.push_back(select_control(false).control);
    for (std::size_t i = 1; i < all.controls.size(); ++i) {
        all.controls[i].focused = false;
        all.controls[i].lease.reset();
    }
    validate_document_forms(all);
    require(text_state(number).value.empty() && text_state(number).editing_text == "-",
        "Number fixture lost the distinct native intermediate editing text");

    auto reject = [](auto mutate, const char* message) {
        auto value = text_control(); mutate(value); invalid([&] { validate_form_update(value); },message);
    };
    reject([](FormUpdate& value) { value.control.node = 0; },"Zero control identity was accepted");
    reject([](FormUpdate& value) { value.control.native_type = "number"; },
        "A text kind/native-type mismatch was accepted");
    reject([](FormUpdate& value) { value.control.state = FormCheckState{}; },
        "A text control carried checkbox state");
    reject([](FormUpdate& value) { value.control.native_type.clear(); },"Empty native control type was accepted");
    reject([](FormUpdate& value) { value.control.label = "\xED\xA0\x80"; },
        "A malformed owned observation label was accepted");
    reject([](FormUpdate& value) { value.control.capabilities |= 0x80000000u; },
        "Unknown capability bits granted authority");
    reject([](FormUpdate& value) { value.control.capabilities |= form_capability(FormCapability::set_checked); },
        "A text control acquired checkbox authority");
    reject([](FormUpdate& value) { value.control.disabled = true; },"Disabled control granted editing authority");
    reject([](FormUpdate& value) { value.control.read_only = true; },"Readonly control granted editing authority");
    reject([](FormUpdate& value) { value.control.focusable = false; },"Unfocusable control granted editing authority");
    reject([](FormUpdate& value) { value.control.focused = false; },"Unfocused native control retained an issued editing lease");
    reject([](FormUpdate& value) { value.control.omitted = true; },"Omitted control granted editing authority");
    reject([](FormUpdate& value) { value.control.complete = false; },"Incomplete control granted editing authority");
    reject([](FormUpdate& value) { value.control.lease->id = 0; },"Zero opaque lease identity was accepted");
    reject([](FormUpdate& value) { ++value.control.lease->node; },"A lease for another control was accepted");
    reject([](FormUpdate& value) { ++value.control.lease->captured.generation; },
        "A lease from another document generation was accepted");
    reject([](FormUpdate& value) { ++value.control.lease->captured.epoch; },
        "A lease from another document epoch was accepted");
    reject([](FormUpdate& value) { ++value.control.lease->captured.revision; },
        "A lease from another observed revision was accepted");
    for (const auto zero : {0u,1u,2u}) {
        auto missing_version = text_control();
        if (zero == 0) missing_version.version.generation = 0;
        if (zero == 1) missing_version.version.epoch = 0;
        if (zero == 2) missing_version.version.revision = 0;
        missing_version.control.lease->captured = missing_version.version;
        invalid([&] { validate_form_update(missing_version); },"A zero document lifetime/version component was accepted");
    }
    reject([](FormUpdate& value) {
        auto& state = std::get<FormTextState>(value.control.state);
        state.editing_text = "\xF0\x9F\x98\x80";
        state.selection = FormControlRange{0,1,FormDirection::forward};
    },"Observed native selection split a surrogate pair");

    auto incomplete = text_control("bounded summary");
    incomplete.control.complete = false; incomplete.control.capabilities = 0; incomplete.control.lease.reset();
    std::get<FormTextState>(incomplete.control.state).selection.reset();
    validate_form_update(incomplete);
    auto secure = text_control();
    secure.control.kind = FormKind::secure_readonly; secure.control.native_type = "password";
    secure.control.read_only = true; secure.control.focusable = false; secure.control.focused = false;
    secure.control.capabilities = 0; secure.control.state = std::monostate{}; secure.control.lease.reset();
    validate_form_update(secure);
    auto leaked = secure; leaked.control.state = FormTextState{"secret","secret",{}};
    invalid([&] { validate_form_update(leaked); },"Secure observation retained an old secret or its selection metadata");
    leaked = secure; leaked.control.lease = FormLease{version,1,99};
    invalid([&] { validate_form_update(leaked); },"Secure readonly observation retained an editing lease");
    leaked = secure; leaked.control.capabilities = text_capabilities;
    invalid([&] { validate_form_update(leaked); },"Secure readonly observation granted editing authority");

    for (const auto protocol : {0u,1u,3u}) {
        auto wrong = all; wrong.protocol = protocol;
        invalid([&] { validate_document_forms(wrong); },"Unsupported semantic/forms protocol was accepted");
    }
    auto duplicate = all; duplicate.controls.push_back(duplicate.controls.front());
    duplicate.controls.back().focused = false; duplicate.controls.back().lease.reset();
    invalid([&] { validate_document_forms(duplicate); },"Duplicate native control identities were accepted");
    auto focused_conflict = all; focused_conflict.controls[1].focused = true;
    invalid([&] { validate_document_forms(focused_conflict); },"One native document reported two focused controls");
    auto choices = select_control();
    auto& options = std::get<FormSelectState>(choices.control.state).options;
    options[1].node = options[0].node;
    invalid([&] { validate_form_update(choices); },"Duplicate native option identities were accepted");
    choices = select_control(); std::get<FormSelectState>(choices.control.state).options[0].node = 0;
    invalid([&] { validate_form_update(choices); },"Zero native option identity was accepted");
    choices = select_control(); std::get<FormSelectState>(choices.control.state).multiple = false;
    invalid([&] { validate_form_update(choices); },"Select-many state lost its native multiple mode");
}

void complete_string_and_collection_budgets() {
    auto value = text_control("\xF0\x9F\x98\x80");
    // native_type 4 + canonical 2 + editing buffer 2 = 8 UTF-16 units.
    FormLimits limits{1,1,4,8};
    validate_document_forms(snapshot(value),limits);
    value.control.label = "x";
    invalid([&] { validate_document_forms(snapshot(value),limits); },
        "Aggregate budget omitted duplicated native/canonical editing strings");
    value = text_control("abcd"); limits.total_utf16 = 64;
    validate_form_update(value,limits);
    std::get<FormTextState>(value.control.state).value = "abcde";
    invalid([&] { validate_form_update(value,limits); },"A per-field UTF-16 limit accepted one extra unit");

    auto controls = snapshot(text_control());
    auto second = checked_control(); second.control.focused = false; second.control.lease.reset();
    controls.controls.push_back(second.control);
    invalid([&] { validate_document_forms(controls,limits); },"Control count exceeded its complete snapshot limit");
    limits.controls = 2; limits.field_utf16 = 32; validate_document_forms(controls,limits);
    auto first_select = select_control(), second_select = select_control(false);
    second_select.control.focused = false; second_select.control.lease.reset();
    std::get<FormSelectState>(first_select.control.state).options.resize(1);
    std::get<FormSelectState>(second_select.control.state).options.resize(1);
    std::get<FormSelectState>(second_select.control.state).options[0].node = 41;
    auto option_snapshot = snapshot(first_select); option_snapshot.controls.push_back(second_select.control);
    limits.total_utf16 = 128;
    invalid([&] { validate_document_forms(option_snapshot,limits); },
        "Aggregate option limit was applied separately to each control");
    limits.options = 2; validate_document_forms(option_snapshot,limits);
}

void compare_observed_control_state() {
    const auto original = text_control("a").control;
    auto changed = original; ++changed.lease->id;
    require(form_control_state_matches(original,changed),"Opaque lease issuance changed equal observed native state");
    changed = original; std::get<FormTextState>(changed.state).value = "different canonical value";
    require(!form_control_state_matches(original,changed),"Canonical value change was ignored without a global revision");
    changed = original; std::get<FormTextState>(changed.state).editing_text = "-";
    require(!form_control_state_matches(original,changed),"Native editing buffer change was ignored");
    changed = original; std::get<FormTextState>(changed.state).selection = FormControlRange{};
    require(!form_control_state_matches(original,changed),"Native control selection change was ignored");
    changed = original; changed.focusable = false;
    require(!form_control_state_matches(original,changed),"Effective focusability change was ignored");
    changed = original; changed.focused = false;
    require(!form_control_state_matches(original,changed),"Actual native control focus change was ignored");
    changed = original; changed.native_type = "number";
    require(!form_control_state_matches(original,changed),"Native control type change was ignored");
    changed = original; ++changed.node;
    require(!form_control_state_matches(original,changed),"Native node replacement was ignored");
    const auto select = select_control().control;
    changed = select;
    auto& options = std::get<FormSelectState>(changed.state).options;
    std::swap(options[0],options[1]);
    require(!form_control_state_matches(select,changed),"Reordered equal-label options retained the old state guard");
    changed = select; std::get<FormSelectState>(changed.state).options[1].disabled = true;
    require(!form_control_state_matches(select,changed),"Effective option-disabled change was ignored");
}

struct Published {
    FormDraftView current;
    std::vector<FormDraftView> attempts;
    unsigned failures{0};
    void operator()(const FormDraftView& view) {
        attempts.push_back(view);
        if (failures) { --failures; throw std::runtime_error("deliberate local publication failure"); }
        current = view;
    }
};
FormDraftRequest take_request(FormDraft& draft, const char* message) {
    auto request = draft.next_request(); require(bool(request),message);
    require(draft.request_pending() && !draft.next_request(),"More than one form action became outstanding");
    return std::move(*request);
}
const ReplaceFormText& replacement(const FormDraftRequest& request) {
    const auto* action = std::get_if<ReplaceFormText>(&request.action);
    require(action != nullptr,"Text draft emitted a different native action"); return *action;
}

void synchronous_draft_batch_and_exact_request() {
    Published published;
    auto baseline = text_control("");
    FormDraft draft(41,baseline,[&](const auto& view) { published(view); });
    require(published.attempts.size() == 1 && draft.view().phase == FormDraftPhase::editing &&
        !draft.view().dirty && !draft.handle(ApplyFormDraft{}) && !draft.next_request(),
        "Untouched draft did not publish locally or issued a no-op native edit");
    for (const auto character : {'a','b','c'}) {
        const auto before = published.current.text;
        const auto candidate = before + character;
        require(draft.handle(EditFormDraft{before,candidate}) && published.current.text == candidate &&
            draft.view().text == candidate && !draft.view().publication_pending && !draft.next_request(),
            "Batched local typing did not synchronously publish the exact candidate before return");
    }
    require(published.current.text == "abc" && draft.view().dirty,
        "A batched a-to-ab-to-abc edit derived a candidate from old retained text");
    const auto revision = draft.view().revision;
    require(!draft.handle(EditFormDraft{"a","discarded"}) && draft.view().text == "abc" &&
        draft.view().revision == revision,"An edit with stale base_text overwrote the local draft");
    require(draft.handle(ApplyFormDraft{}) && draft.view().apply_queued && !draft.request_pending(),
        "Apply did not queue for the composition owner to drain outside GUI callbacks");
    require(draft.selection({3,1}) && draft.view().selection == FormByteSelection{3,1},
        "Final GUI selection could not be polled after queuing Apply");
    const auto request = take_request(draft,"Queued local text Apply was not available to the owner");
    require(request.token.generation == 41 && request.token.sequence != 0 &&
        replacement(request).expected == *baseline.control.lease && replacement(request).text == "abc" &&
        replacement(request).range == FormControlRange{0,0,FormDirection::none},
        "Queued text action lost its exact lease, native baseline range or owned draft bytes");
    require(!draft.handle(EditFormDraft{"abc","pending overwrite"}) && !draft.handle(ApplyFormDraft{}),
        "Outstanding native action admitted a second draft action");
    auto actual = text_control("AB",FormKind::text,102,{7,11,14});
    require(draft.complete(request.token,FormDraftOutcome::accepted,actual) &&
        !draft.request_pending() && draft.view().phase == FormDraftPhase::editing &&
        draft.view().text == "AB" && !draft.view().dirty && !draft.next_request(),
        "Accepted action claimed desired equality instead of installing actual native readback");
    actual.control.label = "mutated caller storage";
    require(draft.view().base.control.label.empty(),"Accepted observation borrowed mutable caller storage");
    require(!draft.complete(request.token,FormDraftOutcome::accepted,text_control("duplicate")),
        "A duplicate completion was accepted after its request retired");
}

void publication_failure_and_recursive_mutation() {
    Published published; published.failures = 1;
    FormDraft draft(42,text_control("a"),[&](const auto& view) { published(view); });
    require(draft.view().publication_pending && draft.view().text == "a" && !draft.next_request() &&
        !draft.handle(ApplyFormDraft{}) && !draft.handle(EditFormDraft{"a","lost"}),
        "Failed initial local publication admitted an edit or native action");
    const auto initial_revision = draft.view().revision;
    draft.retry_publication();
    require(!draft.view().publication_pending && published.current.text == "a" &&
        published.current.revision == initial_revision,
        "Retry of initial publication replaced the retained candidate or revision");
    published.failures = 1;
    (void)draft.handle(EditFormDraft{"a","ab"});
    require(draft.view().publication_pending && draft.view().text == "ab" && published.current.text == "a" &&
        !draft.handle(ApplyFormDraft{}) && !draft.next_request(),
        "Failed draft publication discarded its candidate or armed Apply");
    const auto candidate_revision = draft.view().revision;
    published.failures = 1;
    bool propagated = false;
    try { draft.retry_publication(); }
    catch (const std::runtime_error&) { propagated = true; }
    require(propagated && draft.view().publication_pending && draft.view().revision == candidate_revision &&
        published.attempts.back().text == "ab" && published.attempts.back().revision == candidate_revision,
        "Failed explicit retry did not preserve the exact candidate/revision");
    draft.retry_publication();
    require(!draft.view().publication_pending && published.current.text == "ab" &&
        published.current.revision == candidate_revision && !draft.next_request(),
        "Publication retry submitted a native action or silently changed the candidate");

    published.failures = 1;
    (void)draft.handle(ApplyFormDraft{});
    require(draft.view().publication_pending && !draft.next_request() && !draft.request_pending(),
        "Failed queued-Apply publication exposed an unpresented native request");
    draft.retry_publication();
    const auto request = take_request(draft,"Successfully retried Apply publication did not expose its queued action");
    require(replacement(request).text == "ab","Retry of Apply used a different draft");
    draft.close();

    Published pending;
    const auto baseline = text_control("a");
    FormDraft pending_draft(61,baseline,[&](const auto& view) { pending(view); });
    require(pending_draft.handle(EditFormDraft{"a","ab"}) && pending_draft.handle(ApplyFormDraft{}),
        "Pending-publication fixture did not queue its local draft");
    pending.failures = 1;
    require(!pending_draft.next_request() && pending_draft.request_pending() &&
        pending_draft.view().publication_pending && pending_draft.view().phase == FormDraftPhase::pending &&
        !pending_draft.next_request(),
        "Failed pending-view publication exposed an unpresented action or lost its reservation");
    const auto pending_revision = pending_draft.view().revision;
    pending_draft.retry_publication();
    require(!pending_draft.view().publication_pending && pending.current.revision == pending_revision &&
        pending.current.phase == FormDraftPhase::pending,"Pending-view retry changed the exact candidate or revision");
    const auto publication_count = pending.attempts.size();
    const auto pending_request = take_request(pending_draft,"Retried pending publication did not release its single owned request");
    require(pending.attempts.size() == publication_count && replacement(pending_request).expected == *baseline.control.lease &&
        replacement(pending_request).text == "ab", "Draining a retried pending view republished or changed its native action");

    FormDraft* current = nullptr;
    bool recursive_handle = true, recursive_selection = true, recursive_request = true;
    FormDraft recursive(43,text_control("x"),[&](const auto&) {
        if (!current) return;
        recursive_handle = current->handle(EditFormDraft{"xy","recursive overwrite"});
        recursive_selection = current->selection({0,0});
        recursive_request = bool(current->next_request());
    });
    current = &recursive;
    require(recursive.handle(EditFormDraft{"x","xy"}) && recursive.view().text == "xy" &&
        !recursive_handle && !recursive_selection && !recursive_request,
        "A local publication callback recursively mutated or drained the form draft");

    FormDraft* closing_current = nullptr;
    unsigned close_publications = 0;
    FormDraft closing(59,text_control(),[&](const auto&) {
        ++close_publications;
        if (!closing_current) return;
        closing_current->close();
        throw std::runtime_error("publisher failed after lifecycle close");
    });
    closing_current = &closing;
    (void)closing.handle(EditFormDraft{"a","unsaved"});
    require(closing.view().phase == FormDraftPhase::closed && !closing.view().publication_pending &&
        !closing.request_pending() && !closing.next_request(),
        "A publication exception revived pending work after the callback closed its draft");
    const auto closed_attempts = close_publications;
    closing.retry_publication();
    require(close_publications == closed_attempts && !closing.handle(ApplyFormDraft{}),
        "A closed draft retried publication or submitted a final Apply");

    Published cancelled;
    FormDraft cancelling(63,text_control(),[&](const auto& view) { cancelled(view); });
    require(cancelling.handle(EditFormDraft{"a","unsaved"}),"Cancel-publication fixture edit");
    cancelled.failures = 1;
    (void)cancelling.handle(CancelFormDraft{});
    require(cancelling.view().phase == FormDraftPhase::closed && cancelling.view().publication_pending &&
        !cancelling.request_pending() && !cancelling.next_request() && !cancelling.handle(ApplyFormDraft{}),
        "Failed Cancel publication revived action authority or lost its closed-view candidate");
    const auto cancelled_revision = cancelling.view().revision;
    const auto cancelled_attempts = cancelled.attempts.size();
    cancelling.retry_publication();
    require(cancelled.attempts.size() == cancelled_attempts + 1 &&
        cancelled.current.phase == FormDraftPhase::closed && cancelled.current.revision == cancelled_revision &&
        !cancelling.view().publication_pending && !cancelling.next_request(),
        "Cancel retry did not publish the exact closed candidate once");
    cancelling.retry_publication();
    require(cancelled.attempts.size() == cancelled_attempts + 1,
        "Successful Cancel publication remained retryable");
}

void bounded_number_and_textarea_drafts() {
    Published published;
    FormDraft bounded(44,text_control("a"),[&](const auto& view) { published(view); },FormLimits{1,1,4,64});
    const std::string at_limit = "\xF0\x9F\x98\x80\xF0\x9F\x98\x80";
    require(bounded.handle(EditFormDraft{"a",at_limit}) && bounded.view().text == at_limit,
        "Draft limit counted UTF-8 bytes instead of UTF-16 units");
    const auto revision = bounded.view().revision;
    require(!bounded.handle(EditFormDraft{at_limit,at_limit + "x"}) &&
        !bounded.handle(EditFormDraft{at_limit,"\xED\xA0\x80"}) &&
        !bounded.selection({1,at_limit.size()}) && bounded.view().text == at_limit &&
        bounded.view().revision == revision && !bounded.next_request(),
        "Overlimit, malformed or split-scalar local input changed a bounded draft");

    auto numeric = text_control("-",FormKind::number);
    std::get<FormTextState>(numeric.control.state).value.clear();
    FormDraft number(45,numeric,[](const auto&) {});
    require(number.view().text == "-" && number.handle(EditFormDraft{"-","-1"}) &&
        number.handle(ApplyFormDraft{}),"Number editor discarded an actual noncanonical intermediate buffer");
    const auto numeric_request = take_request(number,"Number draft did not queue a typed native text action");
    require(replacement(numeric_request).text == "-1" &&
        replacement(numeric_request).range == FormControlRange{0,1,FormDirection::forward},
        "Number replacement used canonical empty value instead of actual native editing text");

    const std::string native_text = "A\xF0\x9F\x98\x80" "e\xCC\x81" "Z\n";
    const std::string pasted = "A\xF0\x9F\x98\x80" "\npasted";
    auto multiline = text_control(native_text,FormKind::textarea);
    FormDraft textarea(46,multiline,[](const auto&) {});
    require(textarea.handle(EditFormDraft{native_text,pasted}) && textarea.selection({pasted.size(),1}) &&
        textarea.handle(ApplyFormDraft{}),"Textarea draft rejected paste/newline or backward source selection");
    const auto multiline_request = take_request(textarea,"Textarea Apply was not queued");
    require(replacement(multiline_request).range == FormControlRange{0,7,FormDirection::forward} &&
        replacement(multiline_request).expected == *multiline.control.lease &&
        replacement(multiline_request).text == pasted,
        "Textarea Apply confused source bytes, UTF-16 native range or current control selection");
}

void rejected_draft_requires_explicit_fresh_reapply() {
    auto baseline = text_control("a");
    FormDraft draft(47,baseline,[](const auto&) {});
    require(draft.handle(EditFormDraft{"a","mine"}) && draft.selection({4,1}) &&
        draft.handle(ApplyFormDraft{}),"Stale recovery fixture could not queue its user draft");
    const auto first = take_request(draft,"Stale recovery fixture has no outstanding action");
    auto fresh = text_control("script",FormKind::text,102,{7,11,14});
    require(draft.complete(first.token,FormDraftOutcome::rejected,fresh) && !draft.request_pending() &&
        draft.view().phase == FormDraftPhase::stale && draft.view().text == "mine" && draft.view().dirty &&
        draft.view().selection == FormByteSelection{4,1} && draft.view().base == baseline &&
        draft.view().latest && *draft.view().latest == fresh && !draft.next_request(),
        "Rejected action erased, automatically rebound or replayed the saved user draft");
    require(!draft.handle(ApplyFormDraft{}) && !draft.next_request(),
        "Ordinary Apply bypassed explicit recovery after a stale result");
    fresh = text_control("new native",FormKind::text,103,{7,11,15});
    require(draft.observe(fresh) && draft.view().text == "mine" && draft.view().base == baseline &&
        !draft.next_request(),"Fresh observation silently rebased or submitted a stale user draft");
    require(draft.handle(ReapplyFormDraft{}),"Explicit Reapply did not use a fresh observed lease");
    const auto reapplied = take_request(draft,"Explicit Reapply did not queue one fresh action");
    require(reapplied.token.generation == first.token.generation && reapplied.token.sequence > first.token.sequence &&
        replacement(reapplied).expected == *fresh.control.lease && replacement(reapplied).text == "mine" &&
        replacement(reapplied).range == FormControlRange{0,10,FormDirection::forward},
        "Reapply reused the retired request/lease or replaced the old native range");
    auto sanitized = text_control("mi",FormKind::text,104,{7,11,16});
    require(draft.complete(reapplied.token,FormDraftOutcome::accepted,sanitized) &&
        draft.view().text == "mi" && !draft.view().dirty && !draft.next_request(),
        "Reapply result did not install actual native sanitized readback");

    FormDraft reload(48,baseline,[](const auto&) {});
    require(reload.handle(EditFormDraft{"a","saved"}) && reload.handle(ApplyFormDraft{}),"Reload fixture edit");
    const auto old = take_request(reload,"Reload fixture request");
    require(reload.complete(old.token,FormDraftOutcome::rejected,fresh) && reload.view().text == "saved" &&
        reload.handle(ReloadFormDraft{}) && reload.view().text == "new native" &&
        reload.view().base == fresh && !reload.view().dirty && !reload.next_request(),
        "Explicit Reload failed to discard only the local draft and adopt the latest observation");
}

void unknown_and_same_lease_never_replay() {
    const auto baseline = text_control("native");
    FormDraft draft(49,baseline,[](const auto&) {});
    require(draft.handle(EditFormDraft{"native","saved"}) && draft.handle(ApplyFormDraft{}),"Unknown fixture edit");
    const auto uncertain = take_request(draft,"Unknown fixture request");
    require(draft.complete(uncertain.token,FormDraftOutcome::unknown) &&
        draft.view().phase == FormDraftPhase::unknown && draft.view().text == "saved" &&
        !draft.request_pending() && !draft.handle(ApplyFormDraft{}) &&
        !draft.handle(ReapplyFormDraft{}) && !draft.next_request(),
        "Unknown transport outcome automatically replayed or discarded the user's draft");
    (void)draft.observe(baseline);
    require(draft.view().text == "saved" && !draft.handle(ReapplyFormDraft{}) &&
        !draft.handle(ReloadFormDraft{}) && !draft.next_request(),
        "Reapply or Reload using the failed lease reacquired action authority");
    auto fresh = baseline; ++fresh.control.lease->id;
    require(draft.observe(fresh) && !draft.next_request() && draft.handle(ReapplyFormDraft{}),
        "Explicit recovery could not use a separately issued fresh lease at the same version");
    const auto recovery = take_request(draft,"Unknown recovery did not queue one explicit new action");
    require(recovery.token.sequence > uncertain.token.sequence && replacement(recovery).expected == *fresh.control.lease &&
        replacement(recovery).text == "saved", "Unknown recovery reused an uncertain request or lease");
    require(!draft.complete(uncertain.token,FormDraftOutcome::accepted,text_control("late")) &&
        draft.request_pending(),"A late uncertain result consumed a newer explicit recovery action");
    draft.close();
    require(draft.view().phase == FormDraftPhase::closed && !draft.request_pending() && !draft.next_request() &&
        !draft.complete(recovery.token,FormDraftOutcome::accepted,text_control("closed")) &&
        !draft.handle(ReapplyFormDraft{}),"Close replayed or revived retired action authority");
}

void every_spent_lease_stays_retired() {
    const auto baseline = text_control("native");
    FormDraft draft(60,baseline,[](const auto&) {});
    require(draft.handle(EditFormDraft{"native","saved"}) && draft.handle(ApplyFormDraft{}),"Spent-lease fixture edit");
    const auto first = take_request(draft,"Spent-lease fixture first request");
    require(draft.complete(first.token,FormDraftOutcome::unknown),"Spent-lease fixture first unknown completion");
    auto second = baseline; second.control.lease->id = 102;
    require(draft.observe(second) && draft.handle(ReapplyFormDraft{}),"Fresh second lease did not permit explicit Reapply");
    const auto retried = take_request(draft,"Fresh second lease explicit request missing");
    require(replacement(retried).expected.id == 102 && draft.complete(retried.token,FormDraftOutcome::unknown),
        "Second uncertain action did not retire its exact lease");
    require(draft.observe(baseline) && draft.view().text == "saved" &&
        !draft.handle(ReapplyFormDraft{}) && !draft.handle(ReloadFormDraft{}) && !draft.next_request(),
        "An older spent lease regained authority after a newer lease also became uncertain");
    auto third = baseline; third.control.lease->id = 103;
    require(draft.observe(third) && draft.handle(ReloadFormDraft{}) &&
        draft.view().base == third && draft.view().text == "native" && !draft.view().dirty && !draft.next_request(),
        "Explicit Reload could not adopt a genuinely fresh lease after uncertain attempts");
}

void immutable_publications_and_unleased_discovery() {
    const auto baseline = text_control("a");
    FormDraft text(56,baseline,[](const auto&) {});
    require(text.handle(EditFormDraft{"a","mine"}) && text.handle(ApplyFormDraft{}),
        "Same-version property fixture could not queue its user draft");
    const auto first = take_request(text,"Same-version property fixture has no native request");
    // Each native capture publishes a fresh version even when property changes
    // produced no watched DOM mutation. One published version cannot name two states.
    auto changed = text_control("script",FormKind::text,102,version);
    invalid([&] { (void)text.complete(first.token,FormDraftOutcome::rejected,changed); },
        "Two conflicting native states shared one immutable publication identity");
    require(text.view().phase == FormDraftPhase::unknown && text.view().text == "mine" && !text.request_pending(),
        "Conflicting publication readback retained action authority or erased the user's draft");
    changed.version.revision = 14; changed.control.lease->captured = changed.version;
    require(text.observe(changed) && text.view().text == "mine" &&
        text.view().latest && *text.view().latest == changed && !text.next_request() &&
        text.handle(ReapplyFormDraft{}),
        "New native property capture prevented explicit recovery of the preserved draft");
    const auto reapplied = take_request(text,"Fresh native publication did not support explicit Reapply");
    require(replacement(reapplied).expected == *changed.control.lease && replacement(reapplied).text == "mine",
        "Native property recovery reused the superseded baseline lease");

    auto initial = checked_control(false);
    FormDraft checkbox(57,initial,[](const auto&) {});
    require(checkbox.handle(CheckFormDraft{true}) && checkbox.handle(ApplyFormDraft{}),
        "Queued checkbox property fixture edit");
    auto checked = checked_control(true,202,{7,11,14});
    require(checkbox.observe(checked) && checkbox.view().phase == FormDraftPhase::stale &&
        checkbox.view().checked && !checkbox.view().apply_queued && !checkbox.next_request(),
        "Observed native property change failed to revoke a queued old-lease Apply");
    require(checkbox.handle(ReapplyFormDraft{}) && !checkbox.view().dirty && !checkbox.next_request(),
        "Explicit recovery repeated a desired checkbox state already present in fresh native readback");

    auto discoverable = text_control(); discoverable.control.lease.reset(); discoverable.control.focused = false;
    validate_form_update(discoverable);
    FormDraft unleased(58,discoverable,[](const auto&) {});
    require(unleased.view().phase == FormDraftPhase::unavailable && !unleased.handle(EditFormDraft{"a","b"}) &&
        !unleased.handle(ApplyFormDraft{}) && !unleased.next_request(),
        "Discoverable capability metadata without an issued lease granted local editing authority");
}

void completion_tokens_malformed_readback_and_lifecycle() {
    FormDraft draft(50,text_control("a"),[](const auto&) {});
    require(draft.handle(EditFormDraft{"a","saved"}) && draft.handle(ApplyFormDraft{}),"Completion fixture edit");
    const auto request = take_request(draft,"Completion fixture request");
    auto malformed = text_control(); malformed.control.lease->id = 0;
    auto foreign = request.token; ++foreign.generation;
    require(!draft.complete(foreign,FormDraftOutcome::accepted,malformed) && draft.request_pending(),
        "Foreign completion validated or consumed an outstanding request");
    foreign = request.token; ++foreign.sequence;
    require(!draft.complete(foreign,FormDraftOutcome::rejected) && draft.request_pending(),
        "Wrong-sequence completion consumed an outstanding request");
    invalid([&] { (void)draft.complete(request.token,FormDraftOutcome::accepted,malformed); },
        "Malformed matching native readback was accepted as a successful action");
    require(!draft.request_pending() && draft.view().phase == FormDraftPhase::unknown &&
        draft.view().text == "saved" && !draft.next_request() &&
        !draft.complete(request.token,FormDraftOutcome::accepted,text_control("late")),
        "Malformed completion retained replay authority or erased the saved user draft");

    FormDraft absent(51,text_control(),[](const auto&) {});
    require(absent.handle(EditFormDraft{"a","b"}) && absent.handle(ApplyFormDraft{}),"Missing-readback fixture edit");
    const auto missing = take_request(absent,"Missing-readback fixture request");
    invalid([&] { (void)absent.complete(missing.token,FormDraftOutcome::accepted); },
        "Accepted completion did not require actual native readback");
    require(!absent.request_pending() && absent.view().phase == FormDraftPhase::unknown && absent.view().text == "b",
        "Missing readback did not consume its uncertain request and preserve local input");

    FormDraft queued(52,text_control(),[](const auto&) {});
    require(queued.handle(EditFormDraft{"a","unsaved"}) && queued.handle(ApplyFormDraft{}),"Close fixture edit");
    queued.close();
    require(queued.view().phase == FormDraftPhase::closed && !queued.next_request() && !queued.request_pending(),
        "Close attempted a final queued Apply");

    FormDraft replaced(53,text_control(),[](const auto&) {});
    require(replaced.handle(EditFormDraft{"a","orphan"}),"Navigation fixture edit");
    (void)replaced.observe(text_control("replacement document",FormKind::text,999,{8,1,1}));
    require(replaced.view().text == "orphan" && !replaced.handle(ApplyFormDraft{}) &&
        !replaced.handle(ReapplyFormDraft{}) && !replaced.next_request(),
        "A replacement document inherited the old draft's action authority");
}

void completion_waits_for_local_publication_recovery() {
    Published published;
    FormDraft draft(62,text_control("a"),[&](const auto& view) { published(view); });
    require(draft.handle(EditFormDraft{"a","ab"}) && draft.handle(ApplyFormDraft{}),"Blocked-completion fixture edit");
    const auto request = take_request(draft,"Blocked-completion fixture request");
    published.failures = 1;
    (void)draft.observe(text_control("a",FormKind::text,102,{7,11,14}));
    require(draft.view().publication_pending && draft.request_pending(),
        "Failed local observation publication consumed the delivered request");
    const auto candidate_revision = draft.view().revision;
    const auto actual = text_control("AB",FormKind::text,103,{7,11,15});
    require(!draft.complete(request.token,FormDraftOutcome::accepted,actual) && draft.request_pending() &&
        draft.view().revision == candidate_revision && draft.view().publication_pending && draft.view().text == "ab",
        "Matching completion overwrote a local candidate awaiting exact publication retry");
    draft.retry_publication();
    require(published.current.revision == candidate_revision && !draft.view().publication_pending &&
        draft.request_pending() && !draft.next_request(),
        "Local publication retry changed candidate identity or replayed the delivered native request");
    require(draft.complete(request.token,FormDraftOutcome::accepted,actual) &&
        !draft.request_pending() && draft.view().text == "AB" && !draft.view().dirty &&
        !draft.complete(request.token,FormDraftOutcome::accepted,actual) && !draft.next_request(),
        "Redelivered owned completion was lost, accepted twice or triggered action replay");
}

void checkbox_and_one_option_actions() {
    const auto baseline = checked_control();
    FormDraft checkbox(54,baseline,[](const auto&) {});
    require(!checkbox.handle(EditFormDraft{"","text"}) && checkbox.handle(CheckFormDraft{true}) &&
        checkbox.view().checked && checkbox.view().dirty && !checkbox.next_request() &&
        checkbox.handle(ApplyFormDraft{}),"Checkbox draft did not remain a local desired-boolean edit");
    const auto request = take_request(checkbox,"Checkbox Apply did not queue a native desired-state action");
    const auto* checked = std::get_if<SetFormChecked>(&request.action);
    require(checked && checked->expected == *baseline.control.lease && checked->checked,
        "Checkbox Apply lost its exact native baseline lease or desired boolean");
    auto actual = checked_control(false,202,{7,11,14});
    std::get<FormCheckState>(actual.control.state).indeterminate = false;
    require(checkbox.complete(request.token,FormDraftOutcome::accepted,actual) && !checkbox.view().checked &&
        !checkbox.view().dirty && !checkbox.next_request(),
        "Checkbox completion asserted desired state instead of displaying actual native readback");

    auto choices = select_control();
    FormDraft multiple(55,choices,[](const auto&) {});
    require(!multiple.handle(OptionFormDraft{999,true}) && !multiple.handle(OptionFormDraft{33,true}) &&
        !multiple.handle(OptionFormDraft{34,true}) && multiple.handle(OptionFormDraft{32,true}) &&
        multiple.view().option && multiple.view().option->node == 32 && multiple.view().option->selected &&
        multiple.handle(ApplyFormDraft{}),"Multiple-select draft accepted an unavailable option or lost stable identity");
    const auto selected = take_request(multiple,"One-option Apply did not queue a native action");
    const auto* option = std::get_if<SetFormOption>(&selected.action);
    require(option && option->expected == *choices.control.lease && option->option == 32 && option->selected &&
        std::get<FormSelectState>(multiple.view().base.control.state).options[0].selected &&
        !std::get<FormSelectState>(multiple.view().base.control.state).options[1].selected,
        "Multiple-select Apply optimistically replaced the whole selected set or chose by label");
    auto observed = choices; observed.version.revision = 14;
    observed.control.lease = FormLease{observed.version,observed.control.node,302};
    std::get<FormSelectState>(observed.control.state).options[1].selected = true;
    require(multiple.complete(selected.token,FormDraftOutcome::accepted,observed) &&
        multiple.handle(OptionFormDraft{31,false}) && multiple.handle(ApplyFormDraft{}),
        "A later explicit one-option draft could not use the latest actual native state");
    const auto toggled = take_request(multiple,"Second explicit one-option action missing");
    option = std::get_if<SetFormOption>(&toggled.action);
    require(option && option->expected == *observed.control.lease && option->option == 31 && !option->selected &&
        toggled.token.sequence > selected.token.sequence,"A multiple-select action became an implicit batch or old-list replay");
}

} // namespace

int main() {
    try {
        unicode_source_offsets();
        typed_observations_and_authority();
        complete_string_and_collection_budgets();
        compare_observed_control_state();
        synchronous_draft_batch_and_exact_request();
        publication_failure_and_recursive_mutation();
        bounded_number_and_textarea_drafts();
        rejected_draft_requires_explicit_fresh_reapply();
        unknown_and_same_lease_never_replay();
        every_spent_lease_stays_retired();
        immutable_publications_and_unleased_discovery();
        completion_tokens_malformed_readback_and_lifecycle();
        completion_waits_for_local_publication_recovery();
        checkbox_and_one_option_actions();
        std::cout << "Appended document forms tests passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Appended document forms test failure: " << error.what() << '\n';
        return 1;
    }
}
