#include "shared/appended_document_forms.hpp"

#include <gui/terminal.hpp>
#include <algorithm>
#include <cstdint>
#include <functional>
#include <iostream>
#include <limits>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <variant>
#include <vector>

namespace {
using namespace foundation::ui;
using namespace foundation::appended;

std::size_t assertions = 0;
void check(bool value, const char* message) {
    ++assertions;
    if (!value) throw std::runtime_error(message);
}
constexpr FormVersion initial_version{7,11,13};
constexpr FormVersion begin_version{7,11,14};
constexpr FormCapabilities text_capabilities = form_capability(FormCapability::replace_text) |
    form_capability(FormCapability::finish);

DocumentNode element(std::uint64_t id, std::uint64_t parent, std::string tag) {
    DocumentNode result; result.id = id; result.parent = parent; result.tag = std::move(tag); return result;
}
DocumentNode prose(std::uint64_t id, std::uint64_t parent, std::string value) {
    auto result = element(id,parent,{}); result.kind = DocumentNodeKind::text;
    result.text = std::move(value); return result;
}
FormControl text_control(std::uint64_t node, std::string label, std::string value = {},
                         FormKind kind = FormKind::text) {
    FormControl result; result.node = node; result.kind = kind;
    result.native_type = kind == FormKind::number ? "number" : kind == FormKind::textarea ? "textarea" : "text";
    result.label = std::move(label); result.focusable = true; result.complete = true;
    result.capabilities = text_capabilities;
    const auto selection = form_control_range(value,{value.size(),value.size()});
    result.state = FormTextState{value,value,selection}; return result;
}
std::vector<FormControl> controls(std::string first = {}) {
    std::vector<FormControl> result{text_control(10,"First field",std::move(first)),
        text_control(20,"Second field"),text_control(30,"Third field")};
    result.front().focused = true; return result;
}
DocumentSnapshot document(const std::vector<FormControl>& fields = controls(), FormVersion version = initial_version) {
    DocumentSnapshot result; result.version = {version.generation,version.epoch,version.revision};
    result.nodes.push_back(element(1,0,"body"));
    for (const auto& field : fields) {
        auto node = element(field.node,1,field.kind == FormKind::textarea ? "textarea" :
            field.kind == FormKind::select_one || field.kind == FormKind::select_many ? "select" : "input");
        node.name = field.label;
        if (const auto* state = std::get_if<FormTextState>(&field.state)) node.value = state->editing_text;
        node.masked = field.kind == FormKind::secure_readonly; node.omitted = field.omitted;
        node.disabled = field.disabled;
        result.nodes.push_back(std::move(node));
    }
    auto link = element(70,1,"a"); link.name = "Ordinary project link"; link.href = "guide.html";
    result.nodes.push_back(std::move(link)); result.nodes.push_back(prose(71,70,"Ordinary project link"));
    result.active_node = fields.empty() ? std::optional<std::uint64_t>{70} : fields.front().node;
    return result;
}
FormUpdate leased(FormControl field, FormVersion version = begin_version, std::uint64_t lease = 101) {
    field.focused = true; field.lease = FormLease{version,field.node,lease};
    return {version,std::move(field)};
}

std::string exported_text(const gui::Snapshot& snapshot) {
    std::string result = snapshot.title;
    for (const auto& page : snapshot.pages) result += page.id + page.label;
    for (const auto& widget : snapshot.widgets) {
        result += widget.state.text + widget.state.label + widget.state.help + widget.state.accessible_name +
            widget.state.placeholder + widget.state.display_text;
        for (const auto& option : widget.state.options) result += option.id + option.label + option.value;
        for (const auto& option : widget.state.actions) result += option.id + option.label + option.value;
        for (const auto& row : widget.state.records) {
            result += row.id + row.accessible_text;
            for (const auto& cell : row.cells) result += cell.text;
        }
    }
    return result;
}
const gui::Widget& body_list(const gui::Snapshot& snapshot) {
    const auto found = std::find_if(snapshot.widgets.begin(),snapshot.widgets.end(),
        [&](const gui::Widget& widget) { return widget.spec.kind == gui::Kind::list &&
            (!snapshot.modal_root || !gui::in_modal_scope(snapshot,widget.spec.key)); });
    check(found != snapshot.widgets.end(),"Compositor did not retain its generic document list"); return *found;
}
const gui::Widget& editor(const gui::Snapshot& snapshot) {
    const auto found = std::find_if(snapshot.widgets.begin(),snapshot.widgets.end(),
        [](const gui::Widget& widget) { return widget.spec.kind == gui::Kind::text; });
    check(found != snapshot.widgets.end(),"Leased text control did not produce a generic text editor"); return *found;
}
const gui::Widget& native_value(const gui::Snapshot& snapshot) {
    const auto found = std::find_if(snapshot.widgets.begin(),snapshot.widgets.end(),
        [](const gui::Widget& widget) { return widget.spec.kind == gui::Kind::text &&
            widget.state.label == "Current native value"; });
    check(found != snapshot.widgets.end() && found->spec.text_policy.read_only,
        "Recovery did not retain a separate read-only native value pane"); return *found;
}
gui::WidgetKey button(const gui::Snapshot& snapshot, std::string_view label) {
    const auto found = std::find_if(snapshot.widgets.begin(),snapshot.widgets.end(),
        [&](const gui::Widget& widget) { return widget.spec.kind == gui::Kind::button &&
            (widget.state.text == label || widget.state.label == label); });
    check(found != snapshot.widgets.end(),"Compositor did not declare the expected local form button");
    return found->spec.key;
}
bool button_enabled(const gui::Snapshot& snapshot, std::string_view label) {
    return gui::find_widget(snapshot,button(snapshot,label))->state.enabled;
}
std::string row(const gui::Snapshot& snapshot, std::string_view label) {
    const auto& records = body_list(snapshot).state.records;
    const auto found = std::find_if(records.begin(),records.end(),
        [&](const gui::Record& record) { return record.accessible_text.find(label) != std::string::npos; });
    check(found != records.end(),"Compositor lost a fixture's actual projected native control row"); return found->id;
}
std::string terminal_cells(gui::TerminalAdapter& terminal) {
    std::string result;
    for (const auto& line : terminal.render()) result += line + '\n';
    return result;
}

// The actual public retained terminal handles all input, focus and selection.
// The forwarding boundary only observes transactions and injects delivery faults.
class RecordingAdapter final : public gui::Adapter {
public:
    gui::TerminalAdapter terminal;
    std::vector<gui::Snapshot> attempts;
    mutable std::vector<std::string> measurements;
    std::function<void()> during_present;
    mutable std::function<void()> during_measure;
    bool fail_before = false, fail_after = false;
    explicit RecordingAdapter(gui::EventSink sink) : terminal(std::move(sink)) {}
    void present(gui::Snapshot snapshot) override {
        attempts.push_back(snapshot);
        if (during_present) during_present();
        if (std::exchange(fail_before,false)) throw std::runtime_error("injected before actual present");
        terminal.present(std::move(snapshot));
        if (std::exchange(fail_after,false)) throw std::runtime_error("injected after actual present");
    }
    gui::Size measure_text(const gui::TextMeasureRequest& request) const override {
        measurements.push_back(request.text);
        if (during_measure) during_measure();
        return terminal.measure_text(request);
    }
    gui::Availability resolved_availability(const gui::WidgetKey& key) const override { return terminal.resolved_availability(key); }
    std::optional<gui::WidgetKey> focused() const override { return terminal.focused(); }
    bool focus(std::optional<gui::WidgetKey> key) override { return terminal.focus(std::move(key)); }
    bool focus_next(bool reverse = false) override { return terminal.focus_next(reverse); }
    void scroll(const gui::WidgetKey& key, gui::Point offset) override { terminal.scroll(key,offset); }
    gui::Point scroll_offset(const gui::WidgetKey& key) const override { return terminal.scroll_offset(key); }
    gui::TextSelection text_selection(const gui::WidgetKey& key) const override { return terminal.text_selection(key); }
    void text_selection(const gui::WidgetKey& key, gui::TextSelection selected) override { terminal.text_selection(key,selected); }
    bool open_popup(const gui::WidgetKey& key) override { return terminal.open_popup(key); }
    void close_popup(const gui::WidgetKey& key) override { terminal.close_popup(key); }
    void invalidate(const gui::WidgetKey& key, gui::PixelRect damage) override { terminal.invalidate(key,damage); }
    bool closed() const override { return terminal.closed(); }
    void close() override { terminal.close(); }
};

struct Fixture {
    AppendedDocumentForms* current = nullptr;
    unsigned callbacks = 0;
    RecordingAdapter adapter;
    AppendedDocumentForms forms;
    explicit Fixture(bool initialize = true, std::vector<FormControl> fields = controls())
        : adapter([this](const gui::Event& event) { ++callbacks; if (current) current->handle(event); }),
          forms(adapter,7,{48,14}) {
        start(initialize,std::move(fields));
    }
    explicit Fixture(AppendedDocumentForms::RequestSequenceSource source, bool initialize = true,
                     std::vector<FormControl> fields = controls())
        : adapter([this](const gui::Event& event) { ++callbacks; if (current) current->handle(event); }),
          forms(adapter,7,{48,14},std::move(source)) {
        start(initialize,std::move(fields));
    }
    void start(bool initialize, std::vector<FormControl> fields) {
        current = &forms; adapter.terminal.terminal_size(48,15);
        forms.document_actions_available(true);
        if (initialize) {
            forms.tick(); const auto initial = take();
            check(std::holds_alternative<DocumentEngineRequest>(initial.action),"Initial outer request was not a real document snapshot");
            check(complete_document(initial,std::move(fields)),"Initial owned native-v2 join was rejected"); forms.tick();
            check(forms.body_ready() && !forms.presentation_pending(),"Initial native-v2 join did not arm the committed body");
        }
        callbacks = 0;
    }
    DocumentFormsRequest take() {
        auto request = forms.next_request(); check(request.has_value(),"Expected one admitted outer native request");
        check(request->token.generation == 7 && request->token.sequence,"Outer request lacks its native generation/sequence");
        check(!forms.next_request(),"Compositor exposed two concurrent outer native requests"); return *request;
    }
    NativeFormsDocumentObservation observation(const DocumentFormsRequest& request,
        std::vector<FormControl> fields = controls(), FormVersion version = initial_version) {
        const auto* inner = std::get_if<DocumentEngineRequest>(&request.action);
        check(inner != nullptr,"Fixture tried to fabricate a document token for a form action");
        NativeFormsDocumentObservation value; value.publication = version;
        value.body.request_id = inner->token.id; value.body.epoch = version.epoch;
        value.body.snapshot = document(fields,version); value.body.editor_state = DocumentEditorState{1,0};
        value.forms = {document_forms_version,version,std::move(fields)}; return value;
    }
    bool complete_document(const DocumentFormsRequest& request, std::vector<FormControl> fields = controls(),
                           FormVersion version = initial_version) {
        auto value=observation(request,std::move(fields),version);
        if (std::get<DocumentEngineRequest>(request.action).intent) {
            value.body.request_id=0;
            return forms.complete(request.token,DocumentBodyCompletion{DocumentBodyOutcome::completed,std::move(value)});
        }
        return forms.complete(request.token,std::move(value));
    }
    void activate_row(std::string_view label = "First field") {
        const auto key = body_list(forms.view()).spec.key; const auto id = row(forms.view(),label);
        forms.handle(gui::WidgetEvent{key,gui::ActivateRecord{id}});
    }
    void click(std::string_view label) { forms.handle(gui::WidgetEvent{button(forms.view(),label),gui::Activate{}}); }
    DocumentFormsRequest begin(std::string_view label = "First field") {
        activate_row(label); auto request = take();
        check(std::holds_alternative<BeginFormControl>(request.action),"Form row became a v1 document action instead of explicit native Begin");
        return request;
    }
    void open(FormUpdate actual = leased(text_control(10,"First field"))) {
        auto request = begin(); const auto begin_action = std::get<BeginFormControl>(request.action);
        check(begin_action.expected == initial_version && begin_action.node == actual.control.node,
            "Begin lost the exact displayed v2 publication and native control identity");
        auto observed = controls(); observed.front() = actual.control; observed.front().lease.reset();
        auto version = actual.version; ++version.revision;
        check(forms.complete(request.token,DocumentFormsControlReply{FormDraftOutcome::accepted,std::move(actual)}),
            "Owned focused leased Begin readback was ignored");
        forms.tick(); check(forms.modal_open() && forms.draft_phase() == FormDraftPhase::editing,
            "Begin did not publish a leased local modal editor");
        refresh(std::move(observed),version);
        check(adapter.terminal.focus(editor(forms.view()).spec.key),"Real retained terminal could not focus the local form editor");
    }
    void refresh(std::vector<FormControl> fields = controls(), FormVersion version = initial_version) {
        forms.tick(); const auto request = take();
        const auto* action = std::get_if<DocumentEngineRequest>(&request.action);
        check(action && !action->intent,"Native form settlement did not request an actual paired document snapshot");
        check(complete_document(request,std::move(fields),version),"Fresh native-v2 paired snapshot was ignored"); forms.tick();
    }
};

void actual_terminal_batch_selection_and_exact_lease() {
    Fixture fixture; fixture.open(); auto& forms = fixture.forms; auto& terminal = fixture.adapter.terminal;
    const auto key = editor(forms.view()).spec.key;
    fixture.callbacks = 0; terminal.input("abc");
    check(fixture.callbacks == 3 && editor(forms.view()).state.text == "abc" &&
        editor(terminal.snapshot()).state.text == "abc" && terminal.text_selection(key) == gui::TextSelection{3,3},
        "Real terminal batched a/ab/abc lost synchronous publication or physical caret");
    check(!forms.next_request() && forms.local_selection() == FormByteSelection{3,3},
        "Selection polling occurred inside the edit callback or ordinary typing reached native execution");
    const std::string unicode = "A\xF0\x9F\x98\x80" "e\xCC\x81" "Z";
    terminal.input("\x01\x1b[200~" + unicode + "\x1b[201~");
    check(editor(forms.view()).state.text == unicode,"Bracketed terminal paste did not replace the selected local buffer atomically");
    terminal.text_selection(key,{8,8});
    terminal.input("\x1b[1;2D\x1b[1;2D\x1b[1;2D");
    check(terminal.text_selection(key) == gui::TextSelection{8,1} && !forms.next_request() &&
        forms.local_selection() == FormByteSelection{8,1} &&
        terminal.text_selection(key) == gui::TextSelection{8,1} &&
        form_control_range(unicode,*forms.local_selection()) == FormControlRange{1,5,FormDirection::backward},
        "Backward astral/combining selection used display cells or was overwritten by modal publication");
    terminal.input("\x13"); const auto request = fixture.take();
    const auto* draft = std::get_if<FormDraftRequest>(&request.action);
    check(draft && std::holds_alternative<ReplaceFormText>(draft->action),"Ctrl+Enter did not admit exactly one explicit text Apply");
    const auto& replace = std::get<ReplaceFormText>(draft->action);
    check(replace.expected == FormLease{begin_version,10,101} && replace.range == FormControlRange{0,0,FormDirection::none} &&
        replace.text == unicode,"Apply rebased its exact native lease, borrowed text, or confused full replacement with source selection");
}

void textarea_newlines_and_number_native_editing_buffer() {
    {
        auto fields = controls(); fields.front() = text_control(10,"First field",{},FormKind::textarea);
        fields.front().focused = true; Fixture fixture(true,fields);
        fixture.open(leased(fields.front())); fixture.adapter.terminal.input("first\rsecond\n");
        check(editor(fixture.forms.view()).spec.text_policy.multiline &&
            editor(fixture.forms.view()).state.text == "first\nsecond\n" && !fixture.forms.next_request(),
            "Textarea CR/LF became Apply or lost ordinary native terminal newline editing");
        fixture.adapter.terminal.input("\x13"); const auto request = fixture.take();
        const auto* draft = std::get_if<FormDraftRequest>(&request.action);
        check(draft && std::get<ReplaceFormText>(draft->action).text == "first\nsecond\n",
            "Textarea Ctrl+Enter did not submit exactly the owned multiline draft");
    }
    {
        auto fields = controls(); fields.front() = text_control(10,"First field","-",FormKind::number);
        fields.front().focused = true; std::get<FormTextState>(fields.front().state).value.clear();
        Fixture fixture(true,fields); fixture.open(leased(fields.front()));
        const auto key = editor(fixture.forms.view()).spec.key; fixture.adapter.terminal.text_selection(key,{1,1});
        fixture.adapter.terminal.input("2\x13"); const auto request = fixture.take();
        const auto* draft = std::get_if<FormDraftRequest>(&request.action);
        check(draft && std::holds_alternative<ReplaceFormText>(draft->action),"Number draft lost its explicit native text operation");
        const auto& replace = std::get<ReplaceFormText>(draft->action);
        check(replace.text == "-2" && replace.range == FormControlRange{0,1,FormDirection::forward},
            "Number Apply used canonical empty value instead of the actual native intermediate editing buffer");
    }
}

void synchronous_form_row_cursor_and_busy_refusal() {
    {
        Fixture fixture; auto& forms = fixture.forms;
        const auto key = body_list(forms.view()).spec.key;
        check(fixture.adapter.terminal.focus(key),"Could not focus the real document list");
        fixture.adapter.terminal.input("\x1b[B\x1b[B\r"); const auto request = fixture.take();
        const auto* begin = std::get_if<BeginFormControl>(&request.action);
        check(begin && begin->node == 30 && begin->expected == initial_version,
            "Down,Down,Enter batch did not use each synchronously committed local form-row cursor");
    }
    {
        Fixture fixture; auto& forms = fixture.forms;
        const auto key = body_list(forms.view()).spec.key;
        const auto link = row(forms.view(),"Ordinary project link");
        forms.handle(gui::WidgetEvent{key,gui::ActivateRecord{link}});
        fixture.activate_row(); const auto request = fixture.take();
        const auto* document_action = std::get_if<DocumentEngineRequest>(&request.action);
        check(document_action && document_action->intent && document_action->intent->action == DocumentAction::activate &&
            document_action->intent->node == 70 && document_action->intent->version == DocumentVersion{7,11,13} &&
            !forms.modal_open(),"Busy form activation dropped or overtook a previously admitted native link action");
        check(fixture.complete_document(request,controls(),{7,11,14}),"Prior native link completion was lost after busy form refusal");
        check(!forms.body_ready() && !forms.accepted_query(),"Body readback rearmed input before a fresh paired query");
        fixture.refresh(controls(),{7,11,14}); check(forms.body_ready() && !forms.next_request(),
            "Busy form activation was secretly queued/rebased after the earlier native action settled");
    }
}

void readonly_and_incomplete_rows_show_only_authoritative_value() {
    for (const bool incomplete : {false,true}) {
        const std::string canonical = "42", editing = "PRIVATE_NATIVE_EDITING_BUFFER_MUST_NOT_EXPORT_853";
        auto fields = controls(); auto& control = fields.front();
        control.read_only = !incomplete; control.complete = !incomplete; control.capabilities = 0;
        auto& state = std::get<FormTextState>(control.state);
        state.value = canonical; state.editing_text = editing;
        state.selection = incomplete ? std::optional<FormControlRange>{} :
            std::optional<FormControlRange>{FormControlRange{2,7,FormDirection::backward}};
        Fixture fixture(false); auto& forms = fixture.forms;
        forms.tick(); const auto initial = fixture.take(); auto observed = fixture.observation(initial,std::move(fields));
        // The native body publisher exposes the canonical value separately
        // from its private editing buffer and native selection.
        observed.body.snapshot->nodes[1].value = canonical;
        check(forms.complete(initial.token,std::move(observed)),"Safe readonly/incomplete paired state was not consumed");
        forms.tick();
        check(forms.body_ready() && !forms.modal_open(),"Safe readonly/incomplete rows did not admit the ordinary document");
        const auto id = row(forms.view(),"First field");
        const auto check_row = [&](const gui::Snapshot& snapshot) {
            const auto& list = body_list(snapshot);
            const auto found = std::find_if(list.state.records.begin(),list.state.records.end(),
                [&](const auto& record) { return record.id == id; });
            check(found != list.state.records.end() && found->accessible_text == "[control: read only] First field: 42" &&
                !found->activatable && !found->cells.empty(),
                "Safe readonly/incomplete row hid its authoritative value or advertised native editing");
            for (const auto& cell : found->cells)
                check(cell.text == "[control: read only] First field: 42",
                    "Readonly/incomplete visible row differs from its authoritative accessible value");
        };
        check_row(forms.view()); check_row(fixture.adapter.terminal.snapshot());
        check(terminal_cells(fixture.adapter.terminal).find(canonical) != std::string::npos,
            "Real terminal did not render the safe readonly/incomplete canonical value");
        const auto key = body_list(forms.view()).spec.key;
        forms.handle(gui::WidgetEvent{key,gui::SelectRecord{id}});
        check(fixture.adapter.terminal.focus(key),"Real terminal could not focus the readonly/incomplete document list");
        fixture.adapter.terminal.input("\r"); fixture.activate_row(); forms.tick();
        check(!forms.modal_open() && !forms.local_selection() && !forms.next_request(),
            "Readonly/incomplete Enter or activation created a draft, native selection, or request");
        check_row(forms.view()); check_row(fixture.adapter.terminal.snapshot());
        for (const auto& attempt : fixture.adapter.attempts)
            check(exported_text(attempt).find(editing) == std::string::npos,
                "Readonly/incomplete native editing buffer escaped in an actual presentation, including hidden widgets");
        for (const auto& measured : fixture.adapter.measurements)
            check(measured.find(editing) == std::string::npos,
                "Readonly/incomplete native editing buffer escaped through public text measurement");
    }
}

void checkbox_and_multiple_select_publish_local_drafts_before_exact_native_actions() {
    for (const bool multiple : {false,true}) {
        auto fields=controls(); auto& field=fields.front();
        field.kind=multiple ? FormKind::select_many : FormKind::checkbox;
        field.native_type=multiple ? "select-multiple" : "checkbox";
        field.capabilities=form_capability(multiple ? FormCapability::set_option : FormCapability::set_checked) |
            form_capability(FormCapability::finish);
        if (multiple) field.state=FormSelectState{true,false,{{101,"First option",false,false,false},{102,"Second option",true,false,false}}};
        else field.state=FormCheckState{false,false};
        Fixture fixture(true,fields); auto& forms=fixture.forms; const auto begin=fixture.begin();
        const auto actual=leased(field);
        check(forms.complete(begin.token,DocumentFormsControlReply{FormDraftOutcome::accepted,actual}),
            "Native checkbox/multiple-select Begin was ignored");
        forms.tick(); fixture.refresh(fields,{7,11,15});
        auto find_kind=[&](gui::Kind kind)->const gui::Widget& {
            const auto found=std::find_if(forms.view().widgets.begin(),forms.view().widgets.end(),[&](const auto& w){return w.spec.kind==kind;});
            check(found!=forms.view().widgets.end(),"Native form kind did not produce its shared generic widget"); return *found;
        };
        std::optional<gui::WidgetKey> choice;
        if (multiple) {
            choice=find_kind(gui::Kind::choice).spec.key;
            forms.handle(gui::WidgetEvent{*choice,gui::ChooseOption{"102"}});
            check(find_kind(gui::Kind::choice).state.selected=="102","Local multiple-select chooser lost its actual native option identity");
        }
        const auto toggle=find_kind(gui::Kind::toggle).spec.key;
        check(fixture.adapter.terminal.focus(toggle),"Real terminal could not focus the native form's local draft toggle");
        fixture.adapter.terminal.input(" ");
        check(find_kind(gui::Kind::toggle).state.checked==!multiple && !forms.next_request(),
            "Local checkbox/option editing entered the native engine before explicit Apply");
        if (multiple) {
            check(!find_kind(gui::Kind::choice).state.enabled,"Dirty one-option draft left another option selectable");
            forms.handle(gui::WidgetEvent{*choice,gui::ChooseOption{"101"}});
            check(find_kind(gui::Kind::choice).state.selected=="102",
                "Another option hid the dirty native option that Apply would change");
        }
        fixture.adapter.terminal.input("\x13"); const auto request=fixture.take();
        const auto* draft=std::get_if<FormDraftRequest>(&request.action);
        check(draft!=nullptr,"Explicit checkbox/option Apply did not produce an owned native draft request");
        if (multiple) {
            const auto* selected=std::get_if<SetFormOption>(&draft->action);
            check(selected && selected->expected==*actual.control.lease && selected->option==102 && !selected->selected,
                "Multiple-select Apply changed a hidden/different native option or lost its exact lease");
        } else {
            const auto* checked=std::get_if<SetFormChecked>(&draft->action);
            check(checked && checked->expected==*actual.control.lease && checked->checked,
                "Checkbox Apply did not preserve its explicit local value and exact native lease");
        }
    }
}

void strict_native_v2_join_and_owned_values() {
    for (unsigned variant = 0; variant < 13; ++variant) {
        Fixture fixture(false); fixture.forms.tick(); const auto request = fixture.take();
        auto invalid = fixture.observation(request);
        if (variant == 0) invalid.protocol = 1; // v1 numeric coincidence supplies no native-v2 authority.
        if (variant == 1) invalid.forms.protocol = 1;
        if (variant == 2) ++invalid.publication.revision;
        if (variant == 3) ++invalid.forms.version.epoch;
        if (variant == 4) ++invalid.body.snapshot->version.generation;
        if (variant == 5) invalid.forms.controls.front().node = (std::uint64_t{1} << 53);
        if (variant == 6) invalid.body.snapshot->nodes[1].id = (std::uint64_t{1} << 53);
        if (variant == 7) {
            invalid.publication.epoch = std::uint64_t{1} << 32; invalid.forms.version = invalid.publication;
            invalid.body.epoch = invalid.publication.epoch; invalid.body.snapshot->version.epoch = invalid.publication.epoch;
        }
        if (variant == 8) invalid.body.editor_state->revision = std::uint32_t{1} << 31;
        if (variant == 9) invalid.body.editor_state->flags = 32;
        if (variant == 10 || variant == 11) {
            auto& secure = invalid.forms.controls.front(); secure.kind = FormKind::secure_readonly;
            secure.native_type = "password"; secure.label.clear(); secure.capabilities = 0; secure.state = std::monostate{};
            invalid.body.snapshot->nodes[1].value = "unredacted native old buffer";
            invalid.body.snapshot->nodes[1].masked = variant == 11;
        }
        if (variant == 12) {
            auto& select = invalid.forms.controls.front(); select.kind = FormKind::select_one; select.native_type = "select-one";
            select.capabilities = form_capability(FormCapability::open_popup);
            select.state = FormSelectState{false,true,{{std::uint64_t{1} << 53,"Unsafe native option",true,false,false}}};
        }
        check(fixture.forms.complete(request.token,std::move(invalid)),"Matching malformed native-v2 join did not retire its single outer request");
        fixture.forms.tick(); check(!fixture.forms.body_ready() && !fixture.forms.modal_open() &&
            !fixture.forms.last_error().empty() && !fixture.forms.next_request(),
            "Invalid or unrepresentable native join partially armed a document or automatically retried");
    }
    {
        Fixture fixture(false); fixture.forms.tick(); const auto request = fixture.take();
        auto owned = fixture.observation(request); auto foreign = request.token; ++foreign.generation;
        check(!fixture.forms.complete(foreign,owned) && !fixture.forms.next_request(),
            "Foreign native completion displaced the outstanding joined document request");
        check(fixture.forms.complete(request.token,owned),"Owned v2 join was rejected");
        check(!fixture.forms.complete(request.token,owned),"Duplicate joined document completion was consumed twice");
        owned.forms.controls.front().label = "caller mutated forms"; owned.body.snapshot->nodes[1].name = "caller mutated body";
        fixture.forms.tick(); check(fixture.forms.body_ready() && exported_text(fixture.forms.view()).find("caller mutated") == std::string::npos,
            "Compositor borrowed completion storage rather than owning the paired native observation");
    }
    for (const bool omitted : {false,true}) {
        auto fields = controls(); fields.front().capabilities = 0; fields.front().complete = false;
        fields.front().omitted = omitted; std::get<FormTextState>(fields.front().state).selection.reset();
        Fixture fixture(true,fields);
        const auto& records = body_list(fixture.forms.view()).state.records;
        for (const auto& record : records) if (record.accessible_text.find("First field") != std::string::npos)
            check(!record.activatable,"Incomplete or omitted native metadata gained local editing authority");
        if (!omitted) fixture.activate_row();
        check(!fixture.forms.next_request() && !fixture.forms.modal_open(),"Unavailable form metadata invented native Begin authority");
    }
    for (unsigned variant = 0; variant < 3; ++variant) {
        Fixture fixture(false); fixture.forms.tick(); const auto request = fixture.take();
        auto observed = fixture.observation(request);
        if (variant == 0) observed.body.snapshot->nodes.erase(observed.body.snapshot->nodes.begin() + 1);
        if (variant == 1) observed.body.snapshot->nodes[1].masked = true;
        if (variant == 2) observed.body.snapshot->nodes[1].omitted = true;
        check(fixture.forms.complete(request.token,std::move(observed)),"Pruned/masked body join fixture was not consumed");
        fixture.forms.tick();
        if (!fixture.forms.body_ready()) {
            check(!fixture.forms.modal_open() && !fixture.forms.next_request(),"Rejected pruned/masked join retained native editing admission");
            continue;
        }
        const auto& list = body_list(fixture.forms.view());
        for (const auto& record : list.state.records) if (record.id == "node/10")
            check(!record.activatable,"Pruned, masked or omitted body element acquired a native editable binding");
        fixture.forms.handle(gui::WidgetEvent{list.spec.key,gui::ActivateRecord{"node/10"}});
        check(!fixture.forms.next_request() && !fixture.forms.modal_open(),
            "Form descriptor invented an editable row absent from the actual visible unmasked typed body projection");
    }
}

void single_presenter_global_revisions_and_reentrant_admission() {
    Fixture fixture; auto& forms = fixture.forms;
    unsigned guarded = 0, measured = 0;
    fixture.adapter.during_present = [&] {
        ++guarded; bool blocked = false;
        try { blocked = !forms.next_request(); } catch (const std::logic_error&) { blocked = true; }
        check(blocked,"Actual presentation callback reentered the global native request drain");
        check(!forms.body_ready(),"Body row bindings armed before the outer document/modal publication acknowledgment");
    };
    fixture.adapter.during_measure = [&] {
        ++measured; bool blocked = false;
        try { blocked = !forms.next_request(); } catch (const std::logic_error&) { blocked = true; }
        check(blocked,"Public text measurement callback reentered the global native request drain");
    };
    fixture.open(); fixture.adapter.terminal.input("abc");
    fixture.adapter.during_present = {}; fixture.adapter.during_measure = {};
    check(guarded >= 4,"Fixture did not observe real modal and per-character presentations");
    check(measured > 0,"Fixture did not exercise the forwarding public measurement boundary");
    std::uint64_t previous = 0;
    for (const auto& attempt : fixture.adapter.attempts) {
        check(attempt.revision > previous,"Document and FormDraft component revisions collided at the single actual presenter");
        previous = attempt.revision;
    }
    check(forms.view().revision == fixture.adapter.terminal.snapshot().revision &&
        terminal_cells(fixture.adapter.terminal).find("abc") != std::string::npos,
        "Compositor committed view diverged from its one real retained presenter");
}

void exact_publication_retry_and_completion_redelivery() {
    {
        Fixture fixture(false); auto& forms = fixture.forms; forms.tick(); const auto request = fixture.take();
        check(fixture.complete_document(request),"Base failure fixture did not accept its paired native observation");
        fixture.adapter.fail_after = true; bool threw = false;
        try { forms.tick(); } catch (const std::runtime_error&) { threw = true; }
        check(threw && forms.presentation_pending() && !forms.body_ready(),"Post-install base publication failure armed input or lost debt");
        const auto failed = fixture.adapter.attempts.back();
        check(fixture.adapter.terminal.snapshot().revision == failed.revision,"Failure did not occur after real retained installation");
        const auto key = body_list(failed).spec.key; const auto id = row(failed,"First field");
        forms.handle(gui::WidgetEvent{key,gui::ActivateRecord{id}});
        check(!forms.next_request() && !forms.modal_open(),"An installed but unacknowledged base admitted a modal/native action");
        forms.retry_presentation();
        check(!forms.presentation_pending() && forms.body_ready() && fixture.adapter.attempts.back().revision == failed.revision &&
            exported_text(fixture.adapter.attempts.back()) == exported_text(failed),"Base retry changed transaction origin/revision or failed to acknowledge exact bytes");
        check(!forms.next_request(),"Retry replayed an engine effect");
    }
    {
        Fixture fixture; fixture.open(); auto& forms = fixture.forms; auto& terminal = fixture.adapter.terminal;
        fixture.adapter.fail_after = true; terminal.input("a");
        check(forms.presentation_pending() && !forms.body_ready(),"Post-install modal failure did not retain its publication barrier");
        const auto failed = fixture.adapter.attempts.back(); const auto failed_key = editor(failed).spec.key;
        forms.handle(gui::WidgetEvent{failed_key,gui::EditText{"different","a"}});
        forms.viewport({32,10});
        check(!forms.next_request() && fixture.adapter.attempts.back().revision == failed.revision,
            "New edit/resize superseded failed modal origin before exact retry");
        const auto retry_index = fixture.adapter.attempts.size(); forms.retry_presentation();
        check(fixture.adapter.attempts.size() > retry_index,"Modal retry did not reach the actual presenter");
        const auto& retried = fixture.adapter.attempts[retry_index];
        check(retried.revision == failed.revision && editor(retried).spec.key == failed_key && editor(retried).state.text == "a",
            "Modal retry acknowledged a competing base/resize transaction or changed immutable candidate bytes");
        forms.tick(); check(!forms.presentation_pending() && forms.view().client_size == gui::Size{256,160},
            "Deferred actual-cell viewport update was dropped or stranded after exact modal retry");
        fixture.click("Apply"); const auto action = fixture.take();
        check(std::holds_alternative<FormDraftRequest>(action.action),"Retried local draft did not permit explicit Apply");
        fixture.adapter.fail_after = true;
        auto actual = leased(text_control(10,"First field","native readback"),{7,11,16},102);
        check(forms.complete(action.token,DocumentFormsControlReply{FormDraftOutcome::accepted,actual}),
            "Native completion was not consumed once when its resulting local publication failed");
        check(forms.presentation_pending() && !forms.next_request(),"Failed completion presentation admitted a second native action");
        forms.retry_presentation(); forms.tick();
        check(!forms.complete(action.token,DocumentFormsControlReply{FormDraftOutcome::accepted,actual}),
            "Duplicate native completion was consumed after exact local publication retry");
        fixture.refresh(controls("native readback"),{7,11,17});
        check(!forms.next_request(),"Completion retry replayed Apply or invented another native snapshot");
    }
    {
        Fixture fixture; fixture.open(); auto& forms = fixture.forms;
        fixture.adapter.terminal.input("a"); fixture.click("Apply"); const auto action = fixture.take();
        fixture.adapter.fail_after = true; fixture.click("Cancel");
        check(forms.presentation_pending(),"Cancel publication failure did not retain its exact modal origin");
        const auto failed = fixture.adapter.attempts.back();
        const auto completion = DocumentFormsControlReply{FormDraftOutcome::accepted,
            leased(text_control(10,"First field","native actual"),{7,11,16},102)};
        check(!forms.complete(action.token,completion) && !forms.next_request(),
            "Native completion was consumed through failed Cancel publication instead of retained for redelivery");
        forms.retry_presentation();
        check(fixture.adapter.attempts.back().revision == failed.revision &&
            forms.complete(action.token,completion),"Exact Cancel retry lost the one delivered native action token");
        fixture.refresh(controls("native actual"),{7,11,17});
        check(forms.body_ready() && !forms.modal_open() && !forms.next_request() &&
            !forms.complete(action.token,completion),"Cancel completion redelivery replayed Apply or rearmed without fresh paired state");
    }
}

void cancel_inflight_keeps_one_outer_ledger_and_requires_paired_refresh() {
    Fixture fixture; fixture.open(); auto& forms = fixture.forms;
    const auto old_body_key = body_list(forms.view()).spec.key;
    fixture.adapter.terminal.input("draft"); fixture.click("Apply"); const auto apply = fixture.take();
    check(std::holds_alternative<FormDraftRequest>(apply.action),"Cancel fixture failed to deliver its one native Apply");
    fixture.click("Cancel");
    forms.handle(gui::WidgetEvent{old_body_key,gui::ActivateRecord{"node/70"}});
    check(!forms.body_ready() && !forms.next_request(),"Cancel forgot delivered native work or rearmed the previous body");
    auto foreign = apply.token; ++foreign.sequence;
    check(!forms.fail(foreign,DocumentRequestFailure::unknown) && !forms.next_request(),
        "Foreign failure retired the cancelled draft's outstanding native action");
    check(forms.fail(apply.token,DocumentRequestFailure::unknown),"Cancel discarded the outer Apply token before native settlement");
    check(!forms.fail(apply.token,DocumentRequestFailure::unknown) && !forms.body_ready(),
        "Duplicate native settlement consumed twice or armed body before a fresh joined snapshot");
    const auto refresh = fixture.take();
    const auto* document_request = std::get_if<DocumentEngineRequest>(&refresh.action);
    check(document_request && !document_request->intent && refresh.token.sequence > apply.token.sequence,
        "Unknown cancelled Apply repeated an effect, spent-lease Finish, or old document action");
    forms.handle(gui::WidgetEvent{old_body_key,gui::ActivateRecord{"node/70"}});
    check(!forms.next_request(),"Outstanding paired refresh allowed background actions to overtake native settlement");
    check(fixture.complete_document(refresh,controls("native may have changed"),{7,11,16}),
        "Real paired refresh after unknown cancelled Apply was ignored");
    check(!forms.body_ready(),"Body bindings armed before the fresh joined base was actually committed");
    forms.tick(); check(forms.body_ready() && !forms.modal_open() && !forms.next_request(),
        "Fresh paired snapshot did not rearm body or silently replayed cancelled input");
}

void stale_and_unknown_recovery_requires_fresh_native_lease_and_new_user_intent() {
    for (const auto outcome : {FormDraftOutcome::rejected,FormDraftOutcome::unknown}) {
        for (const bool reapply : {false,true}) {
            Fixture fixture(true,controls("original native"));
            fixture.open(leased(text_control(10,"First field","original native")));
            auto& forms = fixture.forms;
            const std::string saved = "private saved recovery draft";
            fixture.adapter.terminal.input("\x01" + saved); fixture.click("Apply"); const auto first = fixture.take();
            check(forms.complete(first.token,DocumentFormsControlReply{outcome,{}}),
                "Stale/unknown Apply did not settle its one outer native request");
            fixture.refresh(controls("native after failed Apply"),{7,11,16});
            check(forms.draft_phase() == (outcome == FormDraftOutcome::rejected ? FormDraftPhase::stale : FormDraftPhase::unknown) &&
                editor(forms.view()).state.text == saved && !editor(forms.view()).state.enabled &&
                native_value(forms.view()).state.visible && native_value(forms.view()).state.text == "native after failed Apply" &&
                editor(forms.view()).spec.key != native_value(forms.view()).spec.key &&
                !button_enabled(forms.view(),"Apply") && !button_enabled(forms.view(),"Reload") &&
                !button_enabled(forms.view(),"Reapply") && !forms.next_request(),
                "Paired unleased native state overwrote the saved draft, hid actual readback, or granted recovery authority");
            fixture.click("Apply"); fixture.click("Reload"); fixture.click("Reapply");
            check(editor(forms.view()).state.text == saved && !forms.next_request(),
                "Stale/unknown buttons reused a spent lease or replayed Apply before explicit native Refresh");

            fixture.click("Refresh native"); const auto refresh = fixture.take();
            const auto* begin = std::get_if<BeginFormControl>(&refresh.action);
            check(begin && begin->expected == FormVersion{7,11,16} && begin->node == 10 &&
                refresh.token.sequence > first.token.sequence && !editor(forms.view()).state.enabled,
                "Refresh native did not begin against the latest paired publication or left the old editor active");
            const auto actual = leased(text_control(10,"First field","native after focus"),{7,11,17},202);
            check(forms.complete(refresh.token,DocumentFormsControlReply{FormDraftOutcome::accepted,actual}),
                "Explicit Refresh native lost its separately issued native lease");
            fixture.refresh(controls("native after focus"),{7,11,18});
            check(editor(forms.view()).state.text == saved && !editor(forms.view()).state.enabled &&
                native_value(forms.view()).state.text == "native after focus" &&
                button_enabled(forms.view(),"Reload") && button_enabled(forms.view(),"Reapply") &&
                !button_enabled(forms.view(),"Apply") && !forms.next_request(),
                "Refresh or its unleased paired settlement silently applied/reloaded the draft or discarded its fresh recovery lease");

            fixture.click(reapply ? "Reapply" : "Reload");
            if (reapply) {
                const auto request = fixture.take(); const auto* draft = std::get_if<FormDraftRequest>(&request.action);
                check(draft && std::holds_alternative<ReplaceFormText>(draft->action),
                    "Explicit Reapply did not produce exactly one new native replacement");
                const auto& replacement = std::get<ReplaceFormText>(draft->action);
                check(request.token.sequence > refresh.token.sequence && replacement.expected == *actual.control.lease &&
                    replacement.text == saved && replacement.range == FormControlRange{0,18,FormDirection::forward} &&
                    editor(forms.view()).state.text == saved && native_value(forms.view()).state.text == "native after focus" &&
                    !forms.complete(first.token,DocumentFormsControlReply{FormDraftOutcome::accepted,actual}),
                    "Explicit Reapply used the old native range/lease, overwrote its native pane, or accepted the retired action token");
            } else {
                check(editor(forms.view()).state.text == "native after focus" && editor(forms.view()).state.enabled &&
                    !button_enabled(forms.view(),"Apply") && !forms.next_request(),
                    "Explicit Reload did not adopt only the refreshed native baseline without an engine effect");
            }
        }
    }
}

void completion_without_authoritative_readback_conceals_until_fresh_compatible_state() {
    enum class Settlement { failed, unknown, accepted_without_readback, rejected_without_readback,
        malformed_readback, stale_readback, wrong_completion, invalid_outcome, invalid_outcome_with_readback };
    for (const auto settlement : {Settlement::failed, Settlement::unknown, Settlement::accepted_without_readback,
        Settlement::rejected_without_readback, Settlement::malformed_readback, Settlement::stale_readback,
        Settlement::wrong_completion, Settlement::invalid_outcome, Settlement::invalid_outcome_with_readback}) for (const bool reapply : {false,true}) {
        const std::string original = "ORIGINAL_NATIVE_BEFORE_UNCERTAIN_APPLY_642";
        const std::string saved = "PRIVATE_DRAFT_DURING_UNCERTAIN_APPLY_983";
        const std::string invalid = "INVALID_NATIVE_READBACK_MUST_NOT_ESCAPE_735";
        Fixture fixture(true,controls(original));
        fixture.open(leased(text_control(10,"First field",original)));
        auto& forms = fixture.forms;
        fixture.adapter.terminal.input("\x01" + saved); fixture.click("Apply"); const auto apply = fixture.take();
        const auto* submitted = std::get_if<FormDraftRequest>(&apply.action);
        check(submitted && std::holds_alternative<ReplaceFormText>(submitted->action) &&
            std::get<ReplaceFormText>(submitted->action).text == saved,
            "Uncertain-completion fixture did not deliver its exact private draft once");
        const auto first_attempt = fixture.adapter.attempts.size(); fixture.adapter.measurements.clear();
        bool consumed = false;
        switch (settlement) {
        case Settlement::failed:
            consumed = forms.fail(apply.token,DocumentRequestFailure::unknown); break;
        case Settlement::unknown:
            consumed = forms.complete(apply.token,DocumentFormsControlReply{FormDraftOutcome::unknown,{}}); break;
        case Settlement::accepted_without_readback:
            consumed = forms.complete(apply.token,DocumentFormsControlReply{FormDraftOutcome::accepted,{}}); break;
        case Settlement::rejected_without_readback:
            consumed = forms.complete(apply.token,DocumentFormsControlReply{FormDraftOutcome::rejected,{}}); break;
        case Settlement::malformed_readback: {
            auto malformed = leased(text_control(10,"First field",invalid),{7,11,16},302);
            malformed.control.native_type = "password";
            consumed = forms.complete(apply.token,DocumentFormsControlReply{FormDraftOutcome::accepted,std::move(malformed)});
            break;
        }
        case Settlement::stale_readback:
            consumed = forms.complete(apply.token,DocumentFormsControlReply{FormDraftOutcome::rejected,
                leased(text_control(10,"First field",invalid),begin_version,302)}); break;
        case Settlement::wrong_completion:
            consumed = forms.complete(apply.token,NativeFormsDocumentObservation{}); break;
        case Settlement::invalid_outcome:
            consumed = forms.complete(apply.token,DocumentFormsControlReply{static_cast<FormDraftOutcome>(99),{}}); break;
        case Settlement::invalid_outcome_with_readback:
            consumed = forms.complete(apply.token,DocumentFormsControlReply{static_cast<FormDraftOutcome>(99),
                leased(text_control(10,"First field",invalid),{7,11,16},302)}); break;
        }
        check(consumed && !forms.body_ready() && !forms.presentation_pending(),
            "Owned uncertain Apply completion was lost or retained old native admission");
        check(!forms.complete(apply.token,DocumentFormsControlReply{FormDraftOutcome::accepted,
            leased(text_control(10,"First field",invalid),{7,11,16},302)}) &&
            !forms.fail(apply.token,DocumentRequestFailure::unknown),
            "An uncertain native Apply token was consumed twice");
        const auto assert_concealed = [&] {
            const auto absent = [&](const std::string& bytes) {
                return bytes.find(original) == std::string::npos && bytes.find(saved) == std::string::npos &&
                    bytes.find(invalid) == std::string::npos;
            };
            check(fixture.adapter.attempts.size() > first_attempt && absent(exported_text(forms.view())) &&
                absent(exported_text(fixture.adapter.terminal.snapshot())) && absent(terminal_cells(fixture.adapter.terminal)),
                "Uncertain completion exported an old native buffer, retained draft, or rejected readback to the real terminal");
            for (auto index = first_attempt; index < fixture.adapter.attempts.size(); ++index)
                check(absent(exported_text(fixture.adapter.attempts[index])),
                    "A transient actual presentation exported uncertain native/draft data, including hidden widgets");
            for (const auto& measured : fixture.adapter.measurements)
                check(absent(measured),"Uncertain completion exported retained native/draft data through text measurement");
        };
        assert_concealed();
        check(editor(forms.view()).state.text.empty() && !editor(forms.view()).state.enabled &&
            !button_enabled(forms.view(),"Apply") && !button_enabled(forms.view(),"Reload") &&
            !button_enabled(forms.view(),"Reapply"),
            "Uncertain completion left the old editor or recovery actions armed before current kind was observed");
        forms.tick(); const auto paired = fixture.take();
        const auto* snapshot = std::get_if<DocumentEngineRequest>(&paired.action);
        check(snapshot && !snapshot->intent && paired.token.sequence > apply.token.sequence,
            "Uncertain Apply automatically replayed an effect instead of requesting one paired observation");
        fixture.click("Apply"); fixture.click("Reload"); fixture.click("Reapply"); forms.tick();
        check(!forms.next_request(),"A concealed draft submitted a native action while its paired observation was outstanding");
        assert_concealed();

        check(fixture.complete_document(paired,controls("fresh ordinary native"),{7,11,16}),
            "Fresh compatible native observation was not consumed after uncertain Apply");
        forms.tick();
        check(editor(forms.view()).state.text == saved && !editor(forms.view()).state.enabled &&
            native_value(forms.view()).state.text == "fresh ordinary native" &&
            !button_enabled(forms.view(),"Apply") && !button_enabled(forms.view(),"Reload") &&
            !button_enabled(forms.view(),"Reapply") && !forms.next_request(),
            "Fresh paired state lost the exact private draft or silently authorized an old native lease");
        fixture.click("Refresh native"); const auto refresh = fixture.take();
        const auto* begin = std::get_if<BeginFormControl>(&refresh.action);
        check(begin && begin->expected == FormVersion{7,11,16} && begin->node == 10,
            "Uncertain draft recovery did not explicitly request a new lease from the fresh paired publication");
        const auto actual = leased(text_control(10,"First field","fresh focused native"),{7,11,17},303);
        check(forms.complete(refresh.token,DocumentFormsControlReply{FormDraftOutcome::accepted,actual}),
            "Explicit uncertain-draft recovery lost its fresh native lease");
        fixture.refresh(controls("fresh focused native"),{7,11,18});
        check(editor(forms.view()).state.text == saved && !editor(forms.view()).state.enabled &&
            button_enabled(forms.view(),"Reload") && button_enabled(forms.view(),"Reapply") && !forms.next_request(),
            "Fresh recovery lease automatically changed or replayed the saved private draft");
        fixture.click(reapply ? "Reapply" : "Reload");
        if (reapply) {
            const auto recovered = fixture.take(); const auto* draft = std::get_if<FormDraftRequest>(&recovered.action);
            check(draft && std::holds_alternative<ReplaceFormText>(draft->action) &&
                std::get<ReplaceFormText>(draft->action).expected == *actual.control.lease &&
                std::get<ReplaceFormText>(draft->action).text == saved &&
                std::get<ReplaceFormText>(draft->action).range == FormControlRange{0,20,FormDirection::forward} &&
                recovered.token.sequence > refresh.token.sequence,
                "Explicit uncertain-draft Reapply did not preserve its exact saved text and new native lease/range");
        } else {
            check(editor(forms.view()).state.text == "fresh focused native" && editor(forms.view()).state.enabled &&
                !forms.next_request(),"Explicit uncertain-draft Reload did not adopt the refreshed value without a native effect");
        }
    }
}

void uncertain_apply_does_not_reveal_saved_text_when_fresh_kind_is_ineligible() {
    enum class Current { secure, omitted, missing, number, changed_type, incomplete, replacement_document };
    for (const auto current : {Current::secure,Current::omitted,Current::missing,Current::number,
        Current::changed_type,Current::incomplete,Current::replacement_document}) {
        const std::string original = "OLD_NATIVE_BEFORE_UNCERTAIN_KIND_561";
        const std::string saved = "PRIVATE_DRAFT_BEFORE_UNCERTAIN_KIND_674";
        Fixture fixture(true,controls(original)); fixture.open(leased(text_control(10,"First field",original)));
        auto& forms = fixture.forms;
        fixture.adapter.terminal.input("\x01" + saved); fixture.click("Apply"); const auto apply = fixture.take();
        const auto first_attempt = fixture.adapter.attempts.size(); fixture.adapter.measurements.clear();
        check(forms.fail(apply.token,DocumentRequestFailure::unknown),"Unknown native kind fixture lost its Apply completion");
        auto fields = controls("fresh ineligible native"); auto& control = fields.front();
        if (current == Current::secure) {
            control.kind = FormKind::secure_readonly; control.native_type = "password"; control.label.clear();
            control.capabilities = 0; control.focused = false; control.state = std::monostate{};
        } else if (current == Current::omitted || current == Current::incomplete) {
            control.omitted = current == Current::omitted; control.complete = false; control.capabilities = 0;
            control.state = FormTextState{};
        } else if (current == Current::missing) fields.erase(fields.begin());
        else if (current == Current::number) control = text_control(10,"First field","17",FormKind::number);
        else if (current == Current::changed_type) control.native_type = "search";
        fixture.refresh(std::move(fields),current == Current::replacement_document ? FormVersion{7,12,1} : FormVersion{7,11,16});
        check(!forms.body_ready() && editor(forms.view()).state.text.empty() && !editor(forms.view()).state.enabled &&
            !button_enabled(forms.view(),"Apply") && !button_enabled(forms.view(),"Reload") &&
            !button_enabled(forms.view(),"Reapply") && !forms.next_request(),
            "Fresh ineligible native kind/type revived the uncertain saved editor or old lease authority");
        if (current == Current::replacement_document)
            check(!forms.local_selection(),"A new document reusing the numeric control ID exposed the prior draft selection");
        if (current == Current::number || current == Current::changed_type) {
            fixture.click("Refresh native"); const auto refresh = fixture.take();
            const auto* begin = std::get_if<BeginFormControl>(&refresh.action);
            check(begin && begin->expected == FormVersion{7,11,16} && begin->node == 10 &&
                refresh.token.sequence > apply.token.sequence,
                "Changed-kind recovery did not explicitly begin against its current paired publication");
            const std::string fresh = current == Current::number ? "42" : "fresh search native";
            auto native = text_control(10,"First field",fresh,
                current == Current::number ? FormKind::number : FormKind::text);
            if (current == Current::changed_type) native.native_type = "search";
            const auto actual = leased(std::move(native),{7,11,17},304);
            check(forms.complete(refresh.token,DocumentFormsControlReply{FormDraftOutcome::accepted,actual}),
                "Explicit changed-kind Refresh lost its actual new native lease");
            auto observed = controls(); observed.front() = actual.control; observed.front().lease.reset();
            fixture.refresh(std::move(observed),{7,11,18});
            check(editor(forms.view()).state.text.empty() && !editor(forms.view()).state.enabled &&
                native_value(forms.view()).state.visible && native_value(forms.view()).state.text == fresh &&
                button_enabled(forms.view(),"Reload") && !button_enabled(forms.view(),"Reapply") &&
                !button_enabled(forms.view(),"Apply") && !forms.next_request(),
                "Fresh changed-kind lease exposed the saved draft, rearmed incompatible Reapply, or failed to permit explicit Reload");
            fixture.click("Reapply");
            check(editor(forms.view()).state.text.empty() && !forms.next_request(),
                "Disabled changed-kind Reapply submitted the incompatible saved draft");
            fixture.click("Reload");
            check(forms.draft_phase() == FormDraftPhase::editing && editor(forms.view()).state.text == fresh &&
                editor(forms.view()).state.enabled && !button_enabled(forms.view(),"Apply") && !forms.next_request(),
                "Explicit changed-kind Reload failed to adopt only the current native value without replaying Apply");
        }
        for (auto index = first_attempt; index < fixture.adapter.attempts.size(); ++index) {
            const auto bytes = exported_text(fixture.adapter.attempts[index]);
            check(bytes.find(original) == std::string::npos && bytes.find(saved) == std::string::npos,
                "Unknown Apply followed by ineligible native state exported an old buffer in an actual presentation");
        }
        for (const auto& measured : fixture.adapter.measurements)
            check(measured.find(original) == std::string::npos && measured.find(saved) == std::string::npos,
                "Unknown Apply followed by ineligible native state measured an old native or saved draft buffer");
    }
}

void uncertain_completion_publication_retries_exact_concealed_snapshot() {
    for (const bool after_install : {false,true}) {
        const std::string original = "NATIVE_BEFORE_UNCERTAIN_PUBLICATION_FAILURE_267";
        const std::string saved = "PRIVATE_DRAFT_UNCERTAIN_PUBLICATION_FAILURE_834";
        Fixture fixture(true,controls(original)); fixture.open(leased(text_control(10,"First field",original)));
        auto& forms = fixture.forms;
        fixture.adapter.terminal.input("\x01" + saved); fixture.click("Apply"); const auto apply = fixture.take();
        const auto first_attempt = fixture.adapter.attempts.size(); fixture.adapter.measurements.clear();
        fixture.adapter.fail_before = !after_install; fixture.adapter.fail_after = after_install;
        check(forms.fail(apply.token,DocumentRequestFailure::unknown),
            "Unknown native completion was not consumed when its concealed publication failed");
        check(forms.presentation_pending() && !forms.body_ready() && !forms.local_selection() && !forms.next_request(),
            "Failed concealment publication lost its exact retry barrier or retained old native admission");
        check(fixture.adapter.attempts.size() > first_attempt,
            "Concealment publication failure did not reach the real adapter boundary");
        const auto failed = fixture.adapter.attempts.back();
        check(editor(failed).state.text.empty() && !editor(failed).state.enabled &&
            (after_install ? fixture.adapter.terminal.snapshot().revision == failed.revision :
                fixture.adapter.terminal.snapshot().revision != failed.revision),
            "Concealment fault did not distinguish before-install and after-install actual terminal delivery");
        check(!forms.fail(apply.token,DocumentRequestFailure::unknown),
            "A consumed uncertain completion was accepted through pending concealed publication debt");
        const auto retry_index = fixture.adapter.attempts.size(); forms.retry_presentation();
        check(fixture.adapter.attempts.size() > retry_index,"Concealed publication retry never reached the real adapter");
        const auto& retried = fixture.adapter.attempts[retry_index];
        check(retried.revision == failed.revision && retried.modal_root == failed.modal_root &&
            retried.client_size == failed.client_size && retried.widgets.size() == failed.widgets.size() &&
            exported_text(retried) == exported_text(failed),
            "Concealment retry changed its failed publication revision, modal identity, geometry, or exported text");
        for (std::size_t index = 0; index < failed.widgets.size(); ++index) {
            const auto& a = retried.widgets[index]; const auto& b = failed.widgets[index];
            check(a.spec == b.spec && a.state.bounds == b.state.bounds && a.state.content_clip == b.state.content_clip &&
                a.state.visible == b.state.visible && a.state.enabled == b.state.enabled && a.state.checked == b.state.checked &&
                a.state.selected == b.state.selected && a.state.options == b.state.options &&
                a.state.actions == b.state.actions && a.state.records == b.state.records && a.state.content_size == b.state.content_size,
                "Concealment retry changed a retained widget key/spec, hidden state, native selection, or owned record contents");
        }
        check(!forms.presentation_pending() && editor(forms.view()).state.text.empty() &&
            editor(fixture.adapter.terminal.snapshot()).state.text.empty() && !forms.local_selection() &&
            !forms.fail(apply.token,DocumentRequestFailure::unknown),
            "Exact concealment retry reexported the saved draft or accepted its consumed native completion twice");
        forms.tick(); const auto paired = fixture.take();
        const auto* snapshot = std::get_if<DocumentEngineRequest>(&paired.action);
        check(snapshot && !snapshot->intent && paired.token.sequence > apply.token.sequence,
            "Concealment retry automatically repeated a native action instead of requesting current paired state");
        for (auto index = first_attempt; index < fixture.adapter.attempts.size(); ++index) {
            const auto bytes = exported_text(fixture.adapter.attempts[index]);
            check(bytes.find(original) == std::string::npos && bytes.find(saved) == std::string::npos,
                "Failed or retried actual concealment publication exported an old native or saved draft buffer");
        }
        for (const auto& measured : fixture.adapter.measurements)
            check(measured.find(original) == std::string::npos && measured.find(saved) == std::string::npos,
                "Failed or retried concealment publication measured an old native or saved draft buffer");
        check(fixture.complete_document(paired,controls("safe native after concealment retry"),{7,11,16}),
            "Actual paired state after concealment retry was not consumed");
        forms.tick();
        check(editor(forms.view()).state.text == saved && !editor(forms.view()).state.enabled &&
            native_value(forms.view()).state.text == "safe native after concealment retry" &&
            !button_enabled(forms.view(),"Apply") && !button_enabled(forms.view(),"Reload") &&
            !button_enabled(forms.view(),"Reapply") && !forms.next_request() &&
            !forms.fail(apply.token,DocumentRequestFailure::unknown),
            "Fresh paired state after exact concealment retry lost the saved draft or automatically replayed native work");
    }
}

void foreground_recovery_preserves_draft_and_requires_explicit_native_refresh() {
    for (const bool reapply : {false,true}) {
        Fixture fixture; fixture.open(); auto& forms = fixture.forms;
        const std::string saved = "private foreground draft";
        fixture.adapter.terminal.input(saved); const auto old_editor = editor(forms.view()).spec.key;
        const auto old_apply = button(forms.view(),"Apply"); const auto epoch = forms.input_epoch();
        forms.foreground(false);
        check(forms.input_epoch() > epoch && !forms.body_ready() && !forms.local_selection() &&
            editor(forms.view()).state.text == saved && !editor(forms.view()).state.enabled && !forms.next_request(),
            "Foreground loss discarded the draft or retained local/native input authority");
        forms.handle(gui::WidgetEvent{old_editor,gui::EditText{"unwanted background edit",saved}});
        forms.handle(gui::WidgetEvent{old_apply,gui::Activate{}});
        forms.foreground(true); fixture.refresh(controls("native after foreground restore"),{7,11,16});
        check(editor(forms.view()).state.text == saved && !editor(forms.view()).state.enabled &&
            native_value(forms.view()).state.text == "native after foreground restore" &&
            !button_enabled(forms.view(),"Apply") && !button_enabled(forms.view(),"Reload") &&
            !button_enabled(forms.view(),"Reapply") && !forms.next_request(),
            "Foreground restoration or its paired snapshot revived old input instead of preserving separate draft/native state");
        fixture.click("Refresh native"); const auto begin = fixture.take();
        check(std::holds_alternative<BeginFormControl>(begin.action) &&
            std::get<BeginFormControl>(begin.action).expected == FormVersion{7,11,16},
            "Foreground recovery Refresh did not use the current actual paired publication");
        const auto actual = leased(text_control(10,"First field","fresh foreground native"),{7,11,17},203);
        check(forms.complete(begin.token,DocumentFormsControlReply{FormDraftOutcome::accepted,actual}),
            "Foreground recovery did not accept explicit native focus/readback");
        fixture.refresh(controls("fresh foreground native"),{7,11,18});
        check(editor(forms.view()).state.text == saved && !editor(forms.view()).state.enabled &&
            native_value(forms.view()).state.text == "fresh foreground native" && !forms.next_request(),
            "Explicit native Refresh automatically revived or submitted the foreground draft");
        fixture.click(reapply ? "Reapply" : "Reload");
        check(editor(forms.view()).spec.key != old_editor,
            "Deliberate foreground recovery reused a retired modal editor key");
        if (reapply) {
            const auto request = fixture.take(); const auto* draft = std::get_if<FormDraftRequest>(&request.action);
            check(draft && std::holds_alternative<ReplaceFormText>(draft->action) &&
                std::get<ReplaceFormText>(draft->action).expected == *actual.control.lease &&
                std::get<ReplaceFormText>(draft->action).text == saved,
                "Explicit foreground Reapply lost the saved draft or reused the previous focus lease");
        } else {
            check(editor(forms.view()).state.text == "fresh foreground native" && editor(forms.view()).state.enabled &&
                !forms.next_request(),"Explicit foreground Reload failed to recover the fresh native baseline without replay");
        }
    }
    Fixture fixture; auto& forms = fixture.forms;
    std::optional<gui::WidgetKey> previous_cover;
    for (std::uint64_t cycle = 0; cycle < 2; ++cycle) {
        forms.foreground(false);
        check(forms.view().modal_root && (!previous_cover || *forms.view().modal_root != *previous_cover) &&
            !forms.body_ready() && !forms.next_request(),
            "A later foreground cover reused a retired retained overlay key or admitted background input");
        previous_cover = forms.view().modal_root;
        forms.foreground(true); fixture.refresh(controls(),{7,11,16+cycle});
        check(forms.body_ready() && !forms.modal_open() && !forms.view().modal_root &&
            !forms.presentation_pending() && !forms.next_request(),
            "Repeated foreground restoration stranded a retired overlay or failed to commit the fresh native body");
    }
}

void foreground_transition_retries_exact_failed_draft_before_current_recovery_scene() {
    for (const bool after_install : {false,true}) for (const bool inside_present : {false,true}) {
        Fixture fixture; fixture.open(); auto& forms = fixture.forms;
        fixture.adapter.terminal.input("saved");
        bool transitioned = false;
        if (inside_present) fixture.adapter.during_present = [&] {
            if (std::exchange(transitioned,true)) return;
            forms.foreground(false); forms.foreground(true);
        };
        fixture.adapter.fail_before = !after_install; fixture.adapter.fail_after = after_install;
        fixture.adapter.terminal.input("!");
        fixture.adapter.during_present = {};
        check(forms.presentation_pending(),"Lifecycle retry fixture did not retain a failed local publication");
        const auto failed = fixture.adapter.attempts.back(); const auto failed_editor = editor(failed);
        if (!inside_present) { forms.foreground(false); forms.foreground(true); }
        check(forms.presentation_pending() && !forms.body_ready() && !forms.next_request(),
            "Lifecycle transition superseded the failed publication or admitted old input before exact retry");
        const auto retry_index = fixture.adapter.attempts.size(); forms.retry_presentation();
        check(fixture.adapter.attempts.size() > retry_index + 1,
            "Exact retry did not publish the subsequent current disabled recovery scene");
        const auto& retried = fixture.adapter.attempts[retry_index];
        check(retried.revision == failed.revision && editor(retried).spec.key == failed_editor.spec.key &&
            editor(retried).state.text == failed_editor.state.text &&
            editor(retried).state.enabled == failed_editor.state.enabled &&
            exported_text(retried) == exported_text(failed),
            "Lifecycle transition changed the failed transaction's revision, keys, text or enabled state before acknowledgment");
        check(forms.view().revision > failed.revision && editor(forms.view()).state.text == "saved!" &&
            !editor(forms.view()).state.enabled && !forms.presentation_pending() && !forms.body_ready(),
            "Retired helper publication debt stranded the current foreground recovery scene");
        fixture.refresh(controls("native after retry"),{7,11,16});
        fixture.click("Refresh native"); const auto refresh = fixture.take();
        check(std::holds_alternative<BeginFormControl>(refresh.action) &&
            std::get<BeginFormControl>(refresh.action).expected == FormVersion{7,11,16},
            "Lifecycle retry bypassed the fresh paired publication for explicit recovery");
        check(forms.complete(refresh.token,DocumentFormsControlReply{FormDraftOutcome::accepted,
            leased(text_control(10,"First field","native after retry"),{7,11,17},204)}),
            "Lifecycle retry left a permanent barrier against explicit native Refresh");
        fixture.refresh(controls("native after retry"),{7,11,18}); fixture.click("Reload");
        check(editor(forms.view()).state.text == "native after retry" && editor(forms.view()).state.enabled &&
            !forms.presentation_pending() && !forms.next_request(),
            "Exact lifecycle retry could not finish explicit recovery without repeating an old action");
    }
}

void explicit_reapply_survives_replacement_and_saved_text_publication_failures() {
    for (const bool after_install : {false,true}) for (const bool restoring_saved_text : {false,true}) {
        Fixture fixture; fixture.open(); auto& forms = fixture.forms;
        const std::string saved = "private draft survives retry", native = "fresh recovery native";
        fixture.adapter.terminal.input(saved); fixture.click("Apply"); const auto uncertain = fixture.take();
        check(forms.fail(uncertain.token,DocumentRequestFailure::unknown),
            "Reapply retry fixture did not settle its uncertain native Apply");
        fixture.refresh(controls(native),{7,11,16}); fixture.click("Refresh native"); const auto refresh = fixture.take();
        const auto actual = leased(text_control(10,"First field",native),{7,11,17},207);
        check(std::holds_alternative<BeginFormControl>(refresh.action) &&
            forms.complete(refresh.token,DocumentFormsControlReply{FormDraftOutcome::accepted,actual}),
            "Reapply retry fixture did not acquire one explicit fresh native lease");
        fixture.refresh(controls(native),{7,11,18}); const auto old_editor = editor(forms.view()).spec.key;
        bool injected = false;
        fixture.adapter.during_present = [&] {
            const auto& candidate = editor(fixture.adapter.attempts.back());
            if (injected || candidate.spec.key == old_editor ||
                candidate.state.text != (restoring_saved_text ? saved : native)) return;
            injected = true;
            fixture.adapter.fail_before = !after_install; fixture.adapter.fail_after = after_install;
        };
        fixture.click("Reapply"); fixture.adapter.during_present = {};
        check(injected && forms.presentation_pending() && !forms.next_request(),
            "Reapply local failure did not block native execution until exact replacement/restore publication retry");
        const auto failed = fixture.adapter.attempts.back();
        check(editor(failed).state.text == (restoring_saved_text ? saved : native),
            "Reapply fault did not discriminate replacement baseline from saved-text restoration");
        const auto retry_index = fixture.adapter.attempts.size(); forms.retry_presentation();
        check(fixture.adapter.attempts.size() > retry_index &&
            fixture.adapter.attempts[retry_index].revision == failed.revision &&
            editor(fixture.adapter.attempts[retry_index]).spec.key == editor(failed).spec.key &&
            exported_text(fixture.adapter.attempts[retry_index]) == exported_text(failed),
            "Reapply retry changed the failed local transaction before continuing the explicit user intent");
        check(!forms.presentation_pending() && editor(forms.view()).state.text == saved &&
            native_value(forms.view()).state.text == native,
            "Replacement/restore publication failure lost the private draft or replaced its separate actual native pane");
        const auto reapplied = fixture.take(); const auto* draft = std::get_if<FormDraftRequest>(&reapplied.action);
        check(draft && std::holds_alternative<ReplaceFormText>(draft->action) &&
            reapplied.token.sequence > refresh.token.sequence &&
            std::get<ReplaceFormText>(draft->action).expected == *actual.control.lease &&
            std::get<ReplaceFormText>(draft->action).text == saved &&
            std::get<ReplaceFormText>(draft->action).range == FormControlRange{0,21,FormDirection::forward},
            "Retried explicit Reapply disappeared, repeated its uncertain action, or lost its saved text/fresh native range");
        check(forms.complete(reapplied.token,DocumentFormsControlReply{FormDraftOutcome::accepted,
            leased(text_control(10,"First field","native accepted recovery"),{7,11,19},208)}),
            "Retried explicit Reapply did not consume its one new native completion");
        fixture.refresh(controls("native accepted recovery"),{7,11,20});
        check(editor(forms.view()).state.text == "native accepted recovery" && !forms.next_request() &&
            !forms.complete(reapplied.token,DocumentFormsControlReply{FormDraftOutcome::unknown,{}}),
            "Retried recovery repeated an engine effect or accepted its completed outer token twice");
    }
}

void immutable_forms_metadata_and_newer_native_readback_guard_paired_admission() {
    {
        Fixture fixture; auto& forms = fixture.forms;
        forms.foreground(false); forms.foreground(true); const auto request = fixture.take();
        auto conflicting = fixture.observation(request);
        const auto original_body = *conflicting.body.snapshot;
        conflicting.forms.controls.front().focused = false;
        check(*conflicting.body.snapshot == original_body,
            "Forms-only conflict fixture accidentally changed its identical document body");
        check(forms.complete(request.token,std::move(conflicting)),
            "Owned same-publication forms metadata conflict was not consumed as unknown");
        forms.tick(); check(!forms.body_ready() && !forms.modal_open() && !forms.last_error().empty() &&
            !forms.next_request(),"Identical body bytes let different forms metadata reuse one immutable native publication");
    }
    {
        Fixture fixture; fixture.open(); auto& forms = fixture.forms;
        const auto old_body = body_list(forms.view()).spec.key;
        fixture.adapter.terminal.input("private update"); fixture.click("Apply"); const auto apply = fixture.take();
        check(forms.complete(apply.token,DocumentFormsControlReply{FormDraftOutcome::accepted,
            leased(text_control(10,"First field","newest native readback"),{7,11,18},205)}),
            "Newer actual native readback fixture was not consumed");
        forms.tick(); const auto snapshot = fixture.take();
        check(std::holds_alternative<DocumentEngineRequest>(snapshot.action) &&
            fixture.complete_document(snapshot,controls("older paired native"),{7,11,17}),
            "Owned older paired snapshot was not retired");
        forms.tick(); forms.handle(gui::WidgetEvent{old_body,gui::ActivateRecord{"node/70"}}); fixture.click("Apply");
        check(!forms.body_ready() && !button_enabled(forms.view(),"Apply") && !forms.last_error().empty() &&
            native_value(forms.view()).state.text == "newest native readback" &&
            exported_text(forms.view()).find("older paired native") == std::string::npos && !forms.next_request(),
            "Paired snapshot older than actual native readback armed input or replaced newer native state");
    }
}

void concealed_and_missing_native_controls_cannot_reflow_visible_old_body_data() {
    for (const bool inherited_omission : {false,true}) {
        Fixture fixture(false); auto& forms=fixture.forms; forms.tick(); const auto request=fixture.take();
        auto value=fixture.observation(request);
        auto& control=value.forms.controls.front();
        control.omitted=true; control.complete=false; control.capabilities=0; control.state=FormTextState{};
        const std::string old="OMITTED_BODY_MUST_NOT_BE_MEASURED_519";
        value.body.snapshot->nodes[1].value=old;
        value.body.snapshot->nodes.front().omitted=inherited_omission;
        fixture.adapter.measurements.clear();
        check(forms.complete(request.token,std::move(value)),"Owned omitted/body observation was not consumed");
        forms.tick();
        check(inherited_omission ? forms.body_ready() : !forms.body_ready() && !forms.last_error().empty(),
            "Omitted native control did not require direct or inherited body omission before admission");
        check(exported_text(forms.view()).find(old)==std::string::npos && !forms.next_request(),
            "Omitted native metadata let visible body data escape or invented an action");
        for (const auto& measured:fixture.adapter.measurements)
            check(measured.find(old)==std::string::npos,"Omitted body data reached public text measurement before rejection");
    }
    Fixture fixture; fixture.open(); auto& forms=fixture.forms;
    fixture.adapter.terminal.input("private saved input"); fixture.click("Apply"); const auto apply=fixture.take();
    check(forms.fail(apply.token,DocumentRequestFailure::unknown),"Missing-control fixture did not settle its one native action");
    forms.tick(); const auto request=fixture.take(); auto fields=controls(); fields.erase(fields.begin());
    auto value=fixture.observation(request,std::move(fields),{7,11,16});
    const std::string old="ABSENT_CONTROL_BODY_MUST_NOT_BE_MEASURED_726";
    value.body.snapshot=document(controls(old),{7,11,16});
    fixture.adapter.measurements.clear();
    check(forms.complete(request.token,std::move(value)),"Owned missing-control/body mismatch was not consumed");
    forms.tick();
    check(!forms.body_ready() && !forms.last_error().empty() && !forms.next_request() &&
        exported_text(forms.view()).find(old)==std::string::npos,
        "A disappeared native editor target was accepted as visible ordinary body data");
    for (const auto& measured:fixture.adapter.measurements)
        check(measured.find(old)==std::string::npos,"Missing native target body reached public measurement before rejection");
}

void secure_and_omitted_transition_never_exports_retained_old_buffer() {
    for (const bool omitted : {false,true}) {
        const std::string old = omitted ? "OLD_NATIVE_OMITTED_391" : "OLD_NATIVE_SECURE_724";
        Fixture fixture(true,controls(old)); fixture.open(leased(text_control(10,"First field",old)));
        auto& forms = fixture.forms;
        fixture.adapter.terminal.input("\x01private user draft"); fixture.click("Apply"); const auto action = fixture.take();
        fixture.adapter.measurements.clear(); const auto first_new_attempt = fixture.adapter.attempts.size();
        auto unavailable = text_control(10,"First field"); unavailable.capabilities = 0; unavailable.focused = false;
        if (omitted) { unavailable.omitted = true; unavailable.complete = false; unavailable.state = FormTextState{}; }
        else {
            unavailable.kind = FormKind::secure_readonly; unavailable.native_type = "password";
            unavailable.label.clear(); unavailable.state = std::monostate{};
        }
        check(forms.complete(action.token,DocumentFormsControlReply{FormDraftOutcome::accepted,FormUpdate{{7,11,16},unavailable}}),
            "Actual unavailable native readback was not consumed");
        check(forms.draft_phase() == FormDraftPhase::unavailable &&
            exported_text(forms.view()).find(old) == std::string::npos &&
            exported_text(fixture.adapter.terminal.snapshot()).find(old) == std::string::npos &&
            exported_text(forms.view()).find("private user draft") == std::string::npos,
            "Secure/omitted transition reexported retained old native or recovery draft bytes, including hidden widgets");
        for (const auto& measurement : fixture.adapter.measurements)
            check(measurement.find(old) == std::string::npos && measurement.find("private user draft") == std::string::npos,
                "Secure/omitted old buffer escaped through generic text measurement");
        auto fields = controls(); fields.front() = unavailable;
        fixture.refresh(fields,{7,11,17});
        check(exported_text(forms.view()).find(old) == std::string::npos &&
            exported_text(forms.view()).find("private user draft") == std::string::npos,
            "Fresh paired snapshot revived a hidden secure/omitted recovery buffer");
        fixture.click("Refresh native"); const auto refresh = fixture.take();
        const auto* begin = std::get_if<BeginFormControl>(&refresh.action);
        check(begin && begin->expected == FormVersion{7,11,17} && begin->node == 10,
            "Concealed control recovery did not request an explicit fresh native Begin");
        check(forms.complete(refresh.token,DocumentFormsControlReply{FormDraftOutcome::accepted,
            leased(text_control(10,"First field","safe ordinary native"),{7,11,18},206)}),
            "Later normal native control readback was ignored");
        fixture.refresh(controls("safe ordinary native"),{7,11,19});
        check(editor(forms.view()).state.text.empty() && !editor(forms.view()).state.enabled &&
            native_value(forms.view()).state.visible && native_value(forms.view()).state.text == "safe ordinary native" &&
            button_enabled(forms.view(),"Reload") && button_enabled(forms.view(),"Reapply") && !forms.next_request(),
            "A later normal paired snapshot automatically exported the saved concealed buffer or hid its separate safe native readback");
        for (auto index = first_new_attempt; index < fixture.adapter.attempts.size(); ++index) {
            const auto bytes = exported_text(fixture.adapter.attempts[index]);
            check(bytes.find(old) == std::string::npos && bytes.find("private user draft") == std::string::npos,
                "A transient actual publication exported secure/omitted old native or recovery draft bytes");
        }
        for (const auto& measurement : fixture.adapter.measurements)
            check(measurement.find(old) == std::string::npos && measurement.find("private user draft") == std::string::npos,
                "Later normal paired state exported a saved concealed buffer through text measurement");
    }
}

void modal_lifetimes_shutdown_and_unfocused_begin() {
    {
        Fixture fixture; fixture.open(); auto& forms = fixture.forms;
        const auto old_editor = editor(forms.view()).spec.key; const auto old_apply = button(forms.view(),"Apply");
        fixture.click("Cancel"); auto request = fixture.take();
        if (const auto* finish = std::get_if<FinishFormControl>(&request.action)) {
            check(finish->expected == FormLease{begin_version,10,101},"Cancel Finish did not use its known fresh unspent lease");
            auto actual = text_control(10,"First field");
            check(forms.complete(request.token,DocumentFormsControlReply{FormDraftOutcome::accepted,FormUpdate{{7,11,16},actual}}),
                "Native Finish readback was ignored");
            request = fixture.take();
        }
        check(std::holds_alternative<DocumentEngineRequest>(request.action) && fixture.complete_document(request,controls(),{7,11,17}),
            "Cancel did not settle through an actual fresh paired snapshot");
        forms.tick(); fixture.activate_row(); const auto begin = fixture.take();
        check(std::get<BeginFormControl>(begin.action).expected == FormVersion{7,11,17},"New editor reused the retired publication");
        check(forms.complete(begin.token,DocumentFormsControlReply{FormDraftOutcome::accepted,
            leased(text_control(10,"First field"),{7,11,18},102)}),"New deliberate Begin was ignored");
        forms.tick(); fixture.refresh(controls(),{7,11,19}); const auto fresh_editor = editor(forms.view()).spec.key;
        check(fresh_editor != old_editor,"New modal lifetime reused a retired retained GUI key");
        forms.handle(gui::WidgetEvent{old_editor,gui::EditText{"resurrected",""}});
        forms.handle(gui::WidgetEvent{old_apply,gui::Activate{}});
        check(editor(forms.view()).state.text.empty() && !forms.next_request(),"Retired modal key revived old draft input or Apply");
        forms.shutdown();
        check(forms.closed() && !fixture.adapter.terminal.closed() && !forms.next_request() && !forms.body_ready(),
            "Composer shutdown retained native admission or destroyed its composition-owned adapter");
    }
    {
        Fixture fixture; const auto begin = fixture.begin();
        auto unfocused = leased(text_control(10,"First field")); unfocused.control.focused = false; unfocused.control.lease.reset();
        check(fixture.forms.complete(begin.token,DocumentFormsControlReply{FormDraftOutcome::accepted,unfocused}) &&
            fixture.forms.draft_phase() != FormDraftPhase::editing,
            "An unfocused Begin readback acquired a native editing lease");
    }
    {
        Fixture fixture; const auto begin = fixture.begin(); fixture.forms.handle(gui::CloseEvent{});
        check(fixture.forms.closed() && !fixture.forms.complete(begin.token,DocumentFormsControlReply{
            FormDraftOutcome::accepted,leased(text_control(10,"First field"))}) && !fixture.forms.next_request(),
            "Late Begin completion resurrected a closed compositor/modal generation");
    }
}

void single_select_requires_a_real_popup_owner_and_tiny_viewport_is_inert() {
    auto fields = controls(); auto& field = fields.front(); field.kind = FormKind::select_one;
    field.native_type = "select-one"; field.capabilities = form_capability(FormCapability::open_popup) |
        form_capability(FormCapability::finish);
    field.state = FormSelectState{false,true,{{101,"Same label",true,false,false},{102,"Same label",false,false,false}}};
    Fixture fixture(true,fields); fixture.forms.document_actions_available(false); fixture.forms.tick();
    const auto id = row(fixture.forms.view(),"First field");
    const auto& list = body_list(fixture.forms.view());
    const auto record = std::find_if(list.state.records.begin(),list.state.records.end(),
        [&](const gui::Record& candidate) { return candidate.id == id; });
    check(record != list.state.records.end() && !record->activatable,
        "Single select advertised editing without the explicit document-actions-v1 capability");
    check(exported_text(fixture.forms.view()).find("document-actions-v1")!=std::string::npos,
        "Old provider did not expose its concrete missing document-actions capability");
    fixture.activate_row(); check(!fixture.forms.next_request() && !fixture.forms.modal_open(),
        "Single select synthesized Begin/Open/choice authority from an unsupported generic list");
    fixture.forms.viewport({1,1}); fixture.forms.tick();
    check(!fixture.forms.body_ready() && fixture.forms.view().client_size == gui::Size{8,16} &&
        !fixture.forms.next_request(),"Terminal minimum canvas invented drawable cells or tiny-viewport native authority");
}

void injected_sequences_keep_shared_64bit_identity_across_navigation() {
    const auto origin = (std::uint64_t{1} << 60) + 37;
    auto shared_sequence = origin;
    unsigned allocations = 0;
    Fixture fixture([&]() -> std::optional<std::uint64_t> { ++allocations; return ++shared_sequence; },false);
    auto& forms = fixture.forms; forms.tick(); const auto initial = fixture.take();
    check(initial.token.sequence == origin + 1 &&
        std::get<DocumentEngineRequest>(initial.action).token == DocumentRequestToken{7,1},
        "Injected initial identity was narrowed, remapped, or confused with the nested controller token");
    check(fixture.complete_document(initial),"Shared-sequence fixture rejected its initial paired observation");
    forms.tick();
    const auto physical = ++shared_sequence, acknowledgement = ++shared_sequence;
    const auto key = body_list(forms.view()).spec.key;
    forms.handle(gui::WidgetEvent{key,gui::ActivateRecord{row(forms.view(),"Ordinary project link")}});
    const auto navigation = fixture.take();
    const auto* action = std::get_if<DocumentEngineRequest>(&navigation.action);
    check(action && action->token == DocumentRequestToken{7,2} && action->intent &&
        action->intent->version == DocumentVersion{7,11,13} && action->intent->node == 70 &&
        navigation.token.sequence == acknowledgement + 1 && physical + 1 == acknowledgement,
        "Document action did not share the exact high 64-bit physical/query/ACK counter");
    check(forms.complete(navigation.token,DocumentBodyCompletion{DocumentBodyOutcome::needs_current_observation,{}}),
        "Same-compositor navigation did not consume its old-document action without a fabricated publication");
    fixture.refresh(controls("new document"),{7,12,1});
    ++shared_sequence; // A separate owner's physical input reservation.
    fixture.activate_row(); const auto begin = fixture.take();
    check(begin.token.sequence == navigation.token.sequence + 3 &&
        std::get<BeginFormControl>(begin.action).expected == FormVersion{7,12,1} && allocations == 4,
        "Navigation reset the application-lived counter or rebased a reserved outer identity");
    check(!forms.next_request() && allocations == 4,
        "An already delivered outer request reserved another shared identity");
}

void busy_initial_query_keeps_one_inner_token_and_absorbs_poll_hints() {
    bool busy = true; unsigned allocations = 0;
    Fixture fixture([&]() -> std::optional<std::uint64_t> {
        ++allocations; return busy ? std::nullopt : std::optional<std::uint64_t>{901};
    },false);
    auto& forms = fixture.forms; forms.tick();
    for (unsigned attempt = 1; attempt <= 3; ++attempt) {
        forms.request_observation(); forms.request_observation();
        check(!forms.next_request() && allocations == attempt && !forms.body_ready() && !forms.closed(),
            "Busy initial query was lost, handed out without identity, or treated as a fatal sequence");
        forms.tick();
        check(allocations == attempt,"tick invoked the owner's pure sequence allocator");
    }
    busy = false; const auto request = fixture.take();
    const auto* query = std::get_if<DocumentEngineRequest>(&request.action);
    check(request.token.sequence == 901 && query && query->token == DocumentRequestToken{7,1} &&
        !query->intent && allocations == 4,
        "Busy query was redrained or replaced instead of retaining its first exact nested token");
    forms.request_observation(); forms.request_observation();
    check(!forms.next_request() && allocations == 4,
        "A late poll allocated work beside an already delivered read-only query");
    check(fixture.complete_document(request),"The query retained across scheduler backpressure could not settle");
    forms.tick();
    check(forms.body_ready() && !forms.next_request() && allocations == 4,
        "Poll hints attached to a prepared/outstanding query caused a redundant follow-up query");
}

void busy_apply_keeps_exact_lease_range_text_and_nested_identity() {
    bool busy = false; unsigned allocations = 0; std::uint64_t sequence = 1000;
    Fixture fixture([&]() -> std::optional<std::uint64_t> {
        ++allocations; return busy ? std::nullopt : std::optional<std::uint64_t>{++sequence};
    },true,controls("A\xF0\x9F\x98\x80" "e\xCC\x81"));
    const std::string native = "A\xF0\x9F\x98\x80" "e\xCC\x81";
    fixture.open(leased(text_control(10,"First field",native)));
    auto& forms = fixture.forms; auto& terminal = fixture.adapter.terminal;
    const auto editor_key = editor(forms.view()).spec.key;
    const std::string saved = "owned \xF0\x9F\x98\x80" " text";
    terminal.input("\x01" + saved); terminal.text_selection(editor_key,{8,1});
    busy = true; fixture.click("Apply"); const auto before = allocations;
    check(!forms.next_request() && allocations == before + 1 &&
        forms.draft_phase() == FormDraftPhase::pending && !button_enabled(forms.view(),"Apply"),
        "Busy allocator failed to retain and publish a noninteractive prepared Apply");
    forms.handle(gui::WidgetEvent{editor_key,gui::EditText{"mutated while waiting",saved}});
    fixture.click("Apply"); forms.request_observation(); forms.tick();
    check(!forms.next_request() && allocations == before + 2 && editor(forms.view()).state.text == saved,
        "Busy Apply admitted another local edit, lost its text, or allocated from tick");
    busy = false; const auto request = fixture.take();
    const auto* draft = std::get_if<FormDraftRequest>(&request.action);
    check(draft && draft->token.generation == editor_key.generation && draft->token.sequence == 1 &&
        std::holds_alternative<ReplaceFormText>(draft->action),
        "Busy Apply was redrained or replaced with another draft action/token");
    const auto& replace = std::get<ReplaceFormText>(draft->action);
    check(request.token.sequence == sequence && replace.expected == FormLease{begin_version,10,101} &&
        replace.range == FormControlRange{0,5,FormDirection::forward} && replace.text == saved &&
        allocations == before + 3,
        "Scheduler backpressure changed the prepared Apply's exact lease, native range, or owned text");
    check(forms.complete(request.token,DocumentFormsControlReply{FormDraftOutcome::accepted,
        leased(text_control(10,"First field","native accepted"),{7,11,16},102)}),
        "Exact Apply retained across busy allocation did not settle once");
    fixture.refresh(controls("native accepted"),{7,11,17});
    check(!forms.next_request() && allocations == before + 4 &&
        !forms.complete(request.token,DocumentFormsControlReply{}),
        "Busy Apply replayed an effect or its poll added a second mandatory paired readback");
}

void busy_apply_cancel_foreground_and_shutdown_retire_known_unhanded_work() {
    for (unsigned transition = 0; transition != 3; ++transition) {
        bool busy = false; unsigned allocations = 0; std::uint64_t sequence = 2000;
        Fixture fixture([&]() -> std::optional<std::uint64_t> {
            ++allocations; return busy ? std::nullopt : std::optional<std::uint64_t>{++sequence};
        });
        fixture.open(); auto& forms = fixture.forms;
        fixture.adapter.terminal.input("never executed"); fixture.click("Apply"); busy = true;
        check(!forms.next_request() && forms.draft_phase() == FormDraftPhase::pending,
            "Retirement fixture did not retain one prepared unhanded Apply");
        const auto before = allocations;
        if (transition == 0) fixture.click("Cancel");
        else if (transition == 1) forms.foreground(false);
        else forms.shutdown();
        if (transition == 2) {
            busy = false;
            check(forms.closed() && !forms.next_request() && allocations == before && !forms.body_ready(),
                "Shutdown reserved identity for or resurrected a prepared unhanded Apply");
            continue;
        }
        if (transition == 1) {
            check(!forms.next_request() && allocations == before,
                "Background compositor allocated an identity for retired prepared work");
            forms.foreground(true);
        }
        busy = false; const auto refresh = fixture.take();
        const auto* query = std::get_if<DocumentEngineRequest>(&refresh.action);
        check(query && !query->intent && allocations == before + 1,
            "Cancel/foreground recovery handed out the known-unexecuted Apply or a spent-lease Finish");
        check(fixture.complete_document(refresh,controls("actual after retirement"),{7,11,16}),
            "Retiring a prepared Apply stranded its mandatory paired refresh");
        forms.tick();
        check(!forms.next_request() && allocations == before + 1 &&
            (transition == 0 ? forms.body_ready() && !forms.modal_open() :
                forms.modal_open() && !button_enabled(forms.view(),"Apply")),
            "Retired prepared Apply revived after fresh native state or bypassed foreground recovery");
    }
}

void invalid_sequence_sources_stop_before_any_bad_handout() {
    for (unsigned invalid = 0; invalid != 4; ++invalid) {
        unsigned allocations = 0;
        Fixture fixture([&]() -> std::optional<std::uint64_t> {
            ++allocations;
            if (invalid == 3) throw std::runtime_error("injected sequence source failure");
            if (invalid == 0) return 0;
            return allocations == 1 ? 800 : invalid == 1 ? 800 : 799;
        },false);
        auto& forms = fixture.forms; forms.tick();
        if (invalid == 1 || invalid == 2) {
            const auto initial = fixture.take();
            check(fixture.complete_document(initial),"Nonmonotonic fixture lost its preceding valid allocation");
            forms.tick(); forms.request_observation();
        }
        bool threw = false; std::optional<DocumentFormsRequest> request;
        try { request = forms.next_request(); } catch (const std::exception&) { threw = true; }
        const auto failed_calls = allocations;
        check(threw && !request && forms.closed() && !forms.last_error().empty() && !forms.body_ready(),
            "Zero, repeated, decreasing, or throwing sequence source did not fail closed before handout");
        forms.tick(); forms.request_observation();
        check(!forms.next_request() && allocations == failed_calls,
            "Fatal sequence source was retried or its retained action resurrected");
    }
}

void maximum_sequence_is_valid_once_and_exhaustion_precedes_callback() {
    unsigned allocations = 0;
    Fixture fixture([&]() -> std::optional<std::uint64_t> {
        ++allocations; return std::numeric_limits<std::uint64_t>::max();
    },false);
    auto& forms = fixture.forms; forms.tick(); const auto request = fixture.take();
    check(request.token.sequence == std::numeric_limits<std::uint64_t>::max() && allocations == 1,
        "Generic compositor rejected or remapped UINT64_MAX instead of retaining its last valid identity");
    check(fixture.complete_document(request),"Last valid outer sequence could not settle normally");
    forms.tick(); check(forms.body_ready(),"Last valid sequence stopped the compositor before new work was requested");
    forms.request_observation(); bool threw = false;
    try { (void)forms.next_request(); } catch (const std::overflow_error&) { threw = true; }
    check(threw && forms.closed() && !forms.last_error().empty() && allocations == 1 && !forms.next_request(),
        "Exhausted outer sequence called its source again, wrapped, or handed out another request");
    Fixture legacy(false); legacy.forms.tick(); const auto first = legacy.take();
    check(first.token.sequence == 1 && legacy.complete_document(first),
        "Existing three-argument constructor lost its original per-compositor sequence source");
    legacy.forms.tick(); const auto next = legacy.begin();
    check(next.token.sequence == 2,"Default sequence compatibility changed after adding the injected source");
}

void sequence_callback_cannot_reenter_drain_tick_or_completion() {
    Fixture* active = nullptr; unsigned allocations = 0, probes = 0;
    Fixture fixture([&]() -> std::optional<std::uint64_t> {
        ++allocations;
        check(allocations == 1,"Sequence callback recursively allocated a second outer identity");
        const auto attempts = active->adapter.attempts.size();
        const auto measurements = active->adapter.measurements.size();
        check(active && !active->forms.next_request(),"Sequence callback recursively drained controller/draft work");
        active->forms.tick(); ++probes;
        check(active->adapter.attempts.size() == attempts && active->adapter.measurements.size() == measurements,
            "Sequence callback recursively ran a presentation or controller tick measurement");
        check(!active->forms.complete({7,1},DocumentFormsControlReply{}),
            "Sequence callback consumed an outer completion before handout");
        return 6000;
    },false);
    active = &fixture; fixture.forms.tick(); const auto request = fixture.take();
    check(allocations == 1 && probes == 1 && request.token.sequence == 6000 &&
        std::get<DocumentEngineRequest>(request.action).token == DocumentRequestToken{7,1},
        "Reentrant sequence reservation lost the one prepared query or changed its identity");
    check(fixture.complete_document(request),"Guarded allocation left its normal outer completion unusable");
    fixture.forms.tick();
    check(fixture.forms.body_ready() && !fixture.forms.next_request() && allocations == 1,
        "Guarded callback left hidden work or a stranded tick/completion guard");
}

void sequence_callback_foreground_and_shutdown_revoke_unhanded_query() {
    for (const bool closing : {false,true}) {
        Fixture* active = nullptr; unsigned allocations = 0; bool revoke = true;
        Fixture fixture([&]() -> std::optional<std::uint64_t> {
            ++allocations;
            if (std::exchange(revoke,false)) {
                if (closing) active->forms.shutdown(); else active->forms.foreground(false);
            }
            return 7000 + allocations;
        },false);
        active = &fixture; auto& forms = fixture.forms; forms.tick();
        check(!forms.next_request() && allocations == 1 && !forms.body_ready(),
            "Lifecycle transition inside sequence reservation still handed out its prepared query");
        if (closing) {
            check(forms.closed() && !forms.next_request() && allocations == 1,
                "Allocator-triggered shutdown did not permanently revoke request admission");
        } else {
            check(!forms.closed() && !forms.next_request() && allocations == 1,
                "Allocator-triggered foreground loss allocated while background or stopped normal recovery");
            forms.foreground(true); const auto fresh = fixture.take();
            check(fresh.token.sequence == 7002 && std::get<DocumentEngineRequest>(fresh.action).token.id == 2 &&
                fixture.complete_document(fresh,controls(),{7,11,14}),
                "Foreground recovery reused the known-unexecuted prepared query or its reserved identity");
            forms.tick(); check(forms.body_ready() && allocations == 2,
                "Reentrant foreground revocation stranded the fresh paired recovery");
        }
    }
}

void busy_query_resize_measurement_foreground_loss_defers_inner_retirement() {
    bool busy = false; unsigned allocations = 0; std::uint64_t sequence = 7600;
    Fixture fixture([&]() -> std::optional<std::uint64_t> {
        ++allocations; return busy ? std::nullopt : std::optional<std::uint64_t>{++sequence};
    });
    auto& forms = fixture.forms; forms.request_observation(); busy = true;
    check(!forms.next_request() && allocations == 2,
        "Measurement-retirement fixture did not retain its second real paired query while busy");
    forms.viewport({40,12}); bool transitioned = false;
    fixture.adapter.during_measure = [&] {
        // Forms metrics also asks for M. Revoke while the controller is actively
        // projecting actual semantic row text, where direct fail_request reentry
        // would violate the inner controller's serialized callback contract.
        if (transitioned || fixture.adapter.measurements.back().find("Ordinary project link") == std::string::npos) return;
        transitioned = true; forms.foreground(false);
    };
    bool threw = false;
    try { forms.tick(); } catch (const std::exception&) { threw = true; }
    fixture.adapter.during_measure = {};
    check(transitioned && !threw && !forms.closed() && !forms.body_ready() &&
        !forms.next_request() && allocations == 2,
        "Foreground loss in controller projection reentered inner retirement or handed out the busy old query");
    busy = false; forms.foreground(true); const auto fresh = fixture.take();
    const auto* query = std::get_if<DocumentEngineRequest>(&fresh.action);
    check(query && !query->intent && query->token == DocumentRequestToken{7,3} && allocations == 3 &&
        fixture.complete_document(fresh,controls(),{7,11,14}),
        "Deferred known-unexecuted retirement reused its old nested query or stranded foreground recovery");
    forms.tick();
    check(forms.body_ready() && !forms.presentation_pending() && forms.view().client_size == gui::Size{320,192} &&
        !forms.next_request() && allocations == 3,
        "Projection callback retirement lost the queued viewport or revived old native work after fresh state");
}

void allocated_and_busy_publication_retries_do_not_reserve_or_change_work() {
    for (const bool initially_busy : {false,true}) for (const bool after_install : {false,true}) {
        unsigned allocations = 0; bool busy = initially_busy; Fixture* active = nullptr;
        Fixture fixture([&]() -> std::optional<std::uint64_t> {
            ++allocations;
            if (allocations == 1) {
                active->adapter.fail_before = !after_install; active->adapter.fail_after = after_install;
            }
            return busy ? std::nullopt : std::optional<std::uint64_t>{8100};
        },false);
        active = &fixture; auto& forms = fixture.forms; forms.tick();
        check(!forms.next_request() && allocations == 1 && forms.presentation_pending(),
            "Prepared/allocated query publication failure did not retain exact local presentation debt");
        const auto failed = fixture.adapter.attempts.back();
        forms.request_observation(); forms.tick();
        check(!forms.next_request() && allocations == 1,
            "Failed waiting/request presentation called the sequence source again before exact retry");
        busy = false; const auto retry_index = fixture.adapter.attempts.size(); forms.retry_presentation();
        check(fixture.adapter.attempts.size() > retry_index &&
            fixture.adapter.attempts[retry_index].revision == failed.revision &&
            fixture.adapter.attempts[retry_index].modal_root == failed.modal_root &&
            fixture.adapter.attempts[retry_index].client_size == failed.client_size &&
            exported_text(fixture.adapter.attempts[retry_index]) == exported_text(failed) && allocations == 1,
            "Exact retry changed the failed frame or reserved an identity from presentation/tick");
        const auto& retried = fixture.adapter.attempts[retry_index];
        check(retried.widgets.size() == failed.widgets.size(),"Exact retry changed the prepared request's retained widget inventory");
        for (std::size_t i = 0; i != failed.widgets.size(); ++i)
            check(retried.widgets[i].spec.key == failed.widgets[i].spec.key &&
                retried.widgets[i].state.enabled == failed.widgets[i].state.enabled,
                "Exact retry changed a retained widget identity or input eligibility");
        const auto request = fixture.take();
        check(request.token.sequence == 8100 && std::get<DocumentEngineRequest>(request.action).token.id == 1 &&
            allocations == (initially_busy ? 2u : 1u),
            "Presentation retry redrained the query or reallocated an already-owned outer token");
        check(fixture.complete_document(request),"Exact waiting/request publication retry lost its retained query");
        forms.tick();
        check(forms.body_ready() && !forms.next_request(),
            "Waiting/request publication retry introduced duplicate polling or hidden native work");
    }
}

void idle_poll_bursts_coalesce_and_preserve_queued_body_action_priority() {
    unsigned allocations = 0; std::uint64_t sequence = 9000;
    Fixture fixture([&]() -> std::optional<std::uint64_t> { ++allocations; return ++sequence; });
    auto& forms = fixture.forms; auto& terminal = fixture.adapter.terminal;
    const auto key = body_list(forms.view()).spec.key;
    check(terminal.focus(key),"Idle poll fixture could not focus its real retained list");
    const auto focus = terminal.focused(); const auto epoch = forms.input_epoch();
    const auto revision = forms.view().revision; const auto attempts = fixture.adapter.attempts.size();
    for (unsigned i = 0; i != 8; ++i) forms.request_observation();
    check(forms.body_ready() && forms.input_epoch() == epoch && forms.view().revision == revision &&
        fixture.adapter.attempts.size() == attempts && terminal.focused() == focus && allocations == 1,
        "Read-only poll hint revoked input authority, published a scene, moved focus, or allocated synchronously");
    forms.handle(gui::WidgetEvent{key,gui::ActivateRecord{row(forms.view(),"Ordinary project link")}});
    const auto action = fixture.take(); const auto* inner = std::get_if<DocumentEngineRequest>(&action.action);
    check(inner && inner->intent && inner->intent->node == 70 && allocations == 2,
        "Idle poll overtook a previously queued exact-version native body action");
    check(fixture.complete_document(action,controls(),{7,11,14}),"Queued body action failed during coalesced polling");
    check(!forms.body_ready() && !forms.accepted_query(),"Action readback satisfied the fresh-query input barrier");
    fixture.refresh(controls(),{7,11,14});
    check(forms.body_ready() && !forms.next_request() && allocations == 3,
        "The mandatory paired query failed to absorb coalesced read-only hints");
    forms.request_observation(); const auto query = fixture.take();
    check(std::holds_alternative<DocumentEngineRequest>(query.action) &&
        !std::get<DocumentEngineRequest>(query.action).intent && allocations == 4,
        "Queued body action discarded the requested read-only observation or duplicated it");
    for (unsigned i = 0; i != 8; ++i) forms.request_observation();
    check(!forms.next_request() && allocations == 4,"Outstanding read-only poll query allocated another request");
    check(fixture.complete_document(query,controls(),{7,11,15}),"Coalesced read-only poll did not settle normally");
    forms.tick(); check(forms.body_ready() && !forms.next_request() && allocations == 4,
        "Poll bursts caused redundant follow-up capture after an already in-flight paired query");
    forms.request_observation(); forms.tick(); forms.request_observation();
    const auto scheduled = fixture.take();
    check(!std::get<DocumentEngineRequest>(scheduled.action).intent && allocations == 5 &&
        fixture.complete_document(scheduled,controls(),{7,11,16}),
        "Hints between scheduling and draining a query did not join the same pending read-only observation");
    forms.tick(); check(!forms.next_request() && allocations == 5,
        "A poll hint added after tick but before query handout scheduled a redundant observation");
}

void modal_and_apply_polls_preserve_draft_focus_selection_and_lease() {
    unsigned allocations = 0; std::uint64_t sequence = 10000;
    Fixture fixture([&]() -> std::optional<std::uint64_t> { ++allocations; return ++sequence; });
    fixture.open(); auto& forms = fixture.forms; auto& terminal = fixture.adapter.terminal;
    terminal.input("local draft"); const auto key = editor(forms.view()).spec.key;
    terminal.text_selection(key,{8,2}); forms.tick();
    const auto epoch = forms.input_epoch(); const auto before = allocations; const auto focus = terminal.focused();
    for (unsigned i = 0; i != 8; ++i) forms.request_observation();
    forms.tick();
    check(!forms.next_request() && allocations == before && forms.modal_open() &&
        forms.draft_phase() == FormDraftPhase::editing && editor(forms.view()).state.text == "local draft" &&
        editor(forms.view()).state.enabled && button_enabled(forms.view(),"Apply") &&
        forms.input_epoch() == epoch && terminal.focused() == focus &&
        terminal.text_selection(key) == gui::TextSelection{8,2} && forms.local_selection() == FormByteSelection{8,2},
        "Modal poll churn revoked draft/lease authority, changed physical selection/focus, or automatically submitted Apply");
    fixture.click("Apply"); const auto request = fixture.take();
    const auto& replace = std::get<ReplaceFormText>(std::get<FormDraftRequest>(request.action).action);
    check(replace.expected == FormLease{begin_version,10,101} && replace.text == "local draft" &&
        replace.range == FormControlRange{0,0,FormDirection::none},
        "Deferred modal polling changed the exact lease or original native replacement range");
    forms.request_observation(); forms.tick();
    check(!forms.next_request() && allocations == before + 1,
        "Poll during a delivered Apply reserved a competing native query");
    check(forms.complete(request.token,DocumentFormsControlReply{FormDraftOutcome::accepted,
        leased(text_control(10,"First field","actual native"),{7,11,16},102)}),
        "Explicit Apply under deferred poll did not accept its native readback");
    forms.request_observation(); fixture.refresh(controls("actual native"),{7,11,17});
    check(!forms.next_request() && allocations == before + 2 && forms.modal_open() &&
        editor(forms.view()).state.text == "actual native" && forms.draft_phase() == FormDraftPhase::editing,
        "Mandatory action readback did not absorb polling into one real paired query");
    forms.request_observation(); forms.tick();
    check(!forms.next_request() && allocations == before + 2,
        "A fresh modal poll started a native query while the user's modal lease remained open");
    fixture.click("Cancel"); const auto finish = fixture.take();
    check(std::holds_alternative<FinishFormControl>(finish.action) &&
        std::get<FinishFormControl>(finish.action).expected == FormLease{{7,11,16},10,102},
        "Modal polling lost the current unspent native lease before explicit Cancel Finish");
    check(forms.complete(finish.token,DocumentFormsControlReply{FormDraftOutcome::accepted,
        FormUpdate{{7,11,18},text_control(10,"First field","actual native")}}),
        "Cancel Finish did not settle before the deferred modal poll");
    fixture.refresh(controls("actual native"),{7,11,19});
    check(forms.body_ready() && !forms.modal_open() && !forms.next_request() && allocations == before + 4,
        "Closing a modal stranded its deferred poll or added another query after mandatory readback");
}

void polls_defer_through_background_and_failed_base_publication() {
    {
        unsigned allocations = 0; std::uint64_t sequence = 11000;
        Fixture fixture([&]() -> std::optional<std::uint64_t> { ++allocations; return ++sequence; });
        auto& forms = fixture.forms; forms.foreground(false); const auto epoch = forms.input_epoch();
        const auto attempts = fixture.adapter.attempts.size();
        for (unsigned i = 0; i != 8; ++i) forms.request_observation();
        forms.tick();
        check(!forms.next_request() && allocations == 1 && forms.input_epoch() == epoch &&
            fixture.adapter.attempts.size() == attempts,
            "Background polling allocated, published churn, or changed lifecycle authority");
        forms.foreground(true); forms.request_observation(); const auto query = fixture.take();
        check(!std::get<DocumentEngineRequest>(query.action).intent && allocations == 2,
            "Foreground restoration did not merge polling into its one mandatory snapshot");
        forms.request_observation();
        check(fixture.complete_document(query,controls(),{7,11,14}),"Foreground paired query did not accept its observation");
        forms.tick(); check(forms.body_ready() && !forms.next_request() && allocations == 2,
            "Poll during foreground recovery scheduled a redundant follow-up query");
    }
    for (const bool after_install : {false,true}) {
        unsigned allocations = 0; std::uint64_t sequence = 12000;
        Fixture fixture([&]() -> std::optional<std::uint64_t> { ++allocations; return ++sequence; },false);
        auto& forms = fixture.forms; forms.tick(); const auto initial = fixture.take();
        check(fixture.complete_document(initial),"Publication-deferred poll fixture lost its initial observation");
        fixture.adapter.fail_before = !after_install; fixture.adapter.fail_after = after_install;
        bool threw = false;
        try { forms.tick(); } catch (const std::runtime_error&) { threw = true; }
        check(threw && forms.presentation_pending(),"Poll fixture did not retain failed base publication debt");
        const auto failed = fixture.adapter.attempts.back();
        for (unsigned i = 0; i != 8; ++i) forms.request_observation();
        forms.tick(); check(!forms.next_request() && allocations == 1,
            "Poll bypassed an unacknowledged base publication to allocate a query");
        const auto retry_index = fixture.adapter.attempts.size(); forms.retry_presentation();
        check(fixture.adapter.attempts.size() > retry_index &&
            fixture.adapter.attempts[retry_index].revision == failed.revision &&
            exported_text(fixture.adapter.attempts[retry_index]) == exported_text(failed),
            "Pending poll replaced the failed base frame before exact publication retry");
        const auto query = fixture.take();
        check(!std::get<DocumentEngineRequest>(query.action).intent && allocations == 2 &&
            fixture.complete_document(query,controls(),{7,11,14}),
            "Publication-deferred poll did not become one read-only query after exact retry");
        forms.tick(); check(forms.body_ready() && !forms.next_request() && allocations == 2,
            "Publication-deferred poll generated redundant observations after successful settlement");
    }
}
void accepted_query_receipt_keeps_exact_outer_identity_without_presentation_authority() {
    const auto origin = (std::uint64_t{1} << 60) + 83;
    auto sequence = origin;
    Fixture fixture([&]() -> std::optional<std::uint64_t> { return ++sequence; },false);
    auto& forms = fixture.forms;
    check(!forms.accepted_query(),"A fresh compositor invented an accepted paired query");
    forms.tick(); const auto query = fixture.take();
    check(query.token == DocumentFormsRequestToken{7,origin+1} &&
        !std::get<DocumentEngineRequest>(query.action).intent && !forms.accepted_query(),
        "Handing out a high 64-bit outer query fabricated or narrowed its semantic receipt");
    const auto observation = fixture.observation(query);
    auto foreign = query.token; ++foreign.generation;
    check(!forms.complete(foreign,observation) && !forms.accepted_query(),
        "A foreign generation produced an accepted-query receipt");
    foreign = query.token; ++foreign.sequence;
    check(!forms.complete(foreign,observation) && !forms.accepted_query(),
        "A foreign outer sequence produced an accepted-query receipt");
    const auto attempts = fixture.adapter.attempts.size();
    const auto actual_revision = fixture.adapter.terminal.snapshot().revision;
    check(forms.complete(query.token,observation) && forms.accepted_query() == query.token &&
        !forms.body_ready() && fixture.adapter.attempts.size() == attempts &&
        fixture.adapter.terminal.snapshot().revision == actual_revision,
        "Whole paired-query acceptance did not retain its exact outer token independently of actual presentation");
    check(!forms.complete(query.token,observation) && forms.accepted_query() == query.token,
        "Duplicate completion changed the accepted paired-query receipt");
    forms.tick();
    check(forms.body_ready() && forms.accepted_query() == query.token &&
        forms.view().revision == fixture.adapter.terminal.snapshot().revision,
        "Successful actual publication lost its already accepted semantic query token");
    check(!forms.complete(foreign,observation) && !forms.complete(query.token,observation) &&
        !forms.fail(foreign,DocumentRequestFailure::unknown) &&
        forms.accepted_query() == query.token,
        "A settled query's foreign failure or foreign/duplicate completion replaced its exact receipt");
    forms.request_observation();
    check(forms.accepted_query() == query.token,
        "A read-only observation hint revoked a completed semantic query");
    forms.tick();
    check(forms.accepted_query() == query.token,
        "Scheduling a read-only query revoked the receipt before native work was reserved");
    const auto next = fixture.take();
    check(next.token.sequence == query.token.sequence + 1 && !forms.accepted_query(),
        "A newly reserved native query retained the previous query's semantic receipt");
    foreign = next.token; ++foreign.sequence;
    check(!forms.fail(foreign,DocumentRequestFailure::unknown) && !forms.accepted_query(),
        "A foreign failure changed a pending query's receipt state");
    check(forms.fail(next.token,DocumentRequestFailure::unknown) && !forms.accepted_query() &&
        !forms.fail(next.token,DocumentRequestFailure::unknown),
        "A matching document failure produced a receipt or consumed its native token twice");
}

void malformed_paired_queries_never_produce_semantic_receipts() {
    for (unsigned variant = 0; variant != 4; ++variant) {
        Fixture fixture(false); auto& forms = fixture.forms; forms.tick(); const auto query = fixture.take();
        auto observation = fixture.observation(query);
        bool consumed = false;
        if (variant == 0) consumed = forms.complete(query.token,DocumentFormsControlReply{});
        else {
            if (variant == 1) ++observation.body.request_id;
            if (variant == 2) ++observation.forms.version.revision;
            if (variant == 3) observation.forms.protocol = 1;
            consumed = forms.complete(query.token,std::move(observation));
        }
        check(consumed && !forms.accepted_query() && !forms.last_error().empty(),
            "Consuming a matching malformed query was confused with semantic paired-query acceptance");
        forms.tick();
        check(!forms.accepted_query() && !forms.body_ready() && !forms.next_request(),
            "A rejected paired query gained a receipt or native admission through later presentation");
    }
}

void immutable_forms_and_native_readback_conflicts_cannot_receipt_a_query() {
    {
        Fixture fixture; auto& forms = fixture.forms;
        check(forms.accepted_query().has_value(),"Initial valid query did not establish the conflict fixture's receipt");
        forms.request_observation(); const auto query = fixture.take();
        auto observation = fixture.observation(query);
        const auto body = *observation.body.snapshot;
        observation.forms.controls.front().focused = false;
        check(*observation.body.snapshot == body && !forms.accepted_query(),
            "Forms-only immutable-publication conflict changed its body or retained an earlier receipt");
        check(forms.complete(query.token,std::move(observation)) && !forms.accepted_query() &&
            !forms.last_error().empty(),
            "An identical body with conflicting immutable forms metadata produced a query receipt");
    }
    {
        Fixture fixture; auto& forms = fixture.forms; const auto begin = fixture.begin();
        check(forms.complete(begin.token,DocumentFormsControlReply{FormDraftOutcome::accepted,
            leased(text_control(10,"First field","actual focused readback"))}),
            "Native-readback conflict fixture did not accept its actual leased Begin");
        forms.tick(); const auto query = fixture.take();
        auto observation = fixture.observation(query,controls("conflicting paired text"),begin_version);
        check(forms.complete(query.token,std::move(observation)) && !forms.accepted_query() &&
            !forms.last_error().empty(),
            "A generically valid paired query conflicting with same-version native readback produced a receipt");
        forms.tick();
        check(!forms.accepted_query() && !forms.body_ready() && !forms.next_request(),
            "A native-readback conflict acquired a query receipt after its unknown completion settled");
    }
}

void native_control_readback_and_body_actions_never_produce_query_receipts() {
    {
        Fixture fixture; auto& forms = fixture.forms; const auto begin = fixture.begin();
        check(!forms.accepted_query(),"Native Begin retained an earlier query receipt after reservation");
        check(forms.complete(begin.token,DocumentFormsControlReply{FormDraftOutcome::accepted,
            leased(text_control(10,"First field"))}) && !forms.accepted_query(),
            "Accepted native Begin readback was presented as a paired-query receipt");
        fixture.refresh(controls(),{7,11,15});
        const auto receipt = forms.accepted_query();
        check(receipt && *receipt != begin.token,
            "The actual paired query after Begin did not establish its own distinct receipt");
        const auto key = editor(forms.view()).spec.key;
        check(fixture.adapter.terminal.focus(key),"Receipt fixture could not focus the actual retained form editor");
        fixture.adapter.terminal.input("new local draft");
        check(forms.accepted_query() == receipt && editor(forms.view()).state.text == "new local draft",
            "Local terminal editing revoked the semantic query receipt without native work");
        fixture.click("Apply"); const auto apply = fixture.take();
        check(std::holds_alternative<FormDraftRequest>(apply.action) && !forms.accepted_query(),
            "Explicit native Apply retained the previous paired query's receipt");
        check(forms.complete(apply.token,DocumentFormsControlReply{FormDraftOutcome::accepted,
            leased(text_control(10,"First field","actual accepted native"),{7,11,16},102)}) &&
            !forms.accepted_query(),"Native Apply readback fabricated a paired-query receipt");
        fixture.refresh(controls("actual accepted native"),{7,11,17});
        check(forms.accepted_query().has_value(),"The actual paired query after Apply did not establish a receipt");
        fixture.click("Cancel"); const auto finish = fixture.take();
        check(std::holds_alternative<FinishFormControl>(finish.action) && !forms.accepted_query(),
            "Explicit native Finish retained the previous paired query's receipt");
        check(forms.complete(finish.token,DocumentFormsControlReply{FormDraftOutcome::accepted,
            FormUpdate{{7,11,18},text_control(10,"First field","actual accepted native")}}) &&
            !forms.accepted_query(),"Native Finish readback fabricated a paired-query receipt");
    }
    for (const bool malformed : {false,true}) {
        Fixture fixture; auto& forms = fixture.forms;
        fixture.activate_row("Ordinary project link"); const auto action = fixture.take();
        const auto* inner = std::get_if<DocumentEngineRequest>(&action.action);
        check(inner && inner->intent && inner->intent->node == 70 && !forms.accepted_query(),
            "The real document-link action did not revoke its preceding query receipt");
        auto observation = fixture.observation(action,controls("actual document"),{7,11,14});
        observation.body.request_id=0;
        if (malformed) observation.protocol = 1;
        check(forms.complete(action.token,DocumentBodyCompletion{DocumentBodyOutcome::completed,std::move(observation)}) && !forms.accepted_query(),
            "A matching body action's paired completion became an accepted-query receipt");
        forms.tick();
        check(!forms.accepted_query() && !forms.body_ready() && (malformed ? !forms.last_error().empty() :
            forms.last_error().empty()),
            "Body-action presentation invented a query receipt or lost its actual success/failure outcome");
        fixture.refresh(controls("actual document"),{7,11,14});
        check(forms.body_ready() && forms.accepted_query(),"Fresh paired query did not rearm a consumed body action");
    }
}

void semantic_query_receipt_survives_failed_actual_publication_and_exact_retry() {
    for (const bool after_install : {false,true}) {
        Fixture fixture(false); auto& forms = fixture.forms; forms.tick(); const auto query = fixture.take();
        check(fixture.complete_document(query,controls("accepted current native")) &&
            forms.accepted_query() == query.token && !forms.body_ready(),
            "Valid paired-query acceptance required an actual publication acknowledgment");
        fixture.adapter.fail_before = !after_install; fixture.adapter.fail_after = after_install;
        bool threw = false;
        try { forms.tick(); } catch (const std::runtime_error&) { threw = true; }
        check(threw && forms.presentation_pending() && !forms.body_ready() && forms.accepted_query() == query.token,
            "Failed actual publication erased the semantic receipt or falsely acknowledged body input");
        const auto failed = fixture.adapter.attempts.back();
        check((fixture.adapter.terminal.snapshot().revision == failed.revision) == after_install,
            "Receipt publication fault did not distinguish failure before and after actual terminal installation");
        check(!forms.complete(query.token,fixture.observation(query)) && !forms.next_request() &&
            forms.accepted_query() == query.token,
            "Local publication debt redelivered native work or confused its semantic receipt with completion admission");
        const auto retry_index = fixture.adapter.attempts.size(); forms.retry_presentation();
        check(fixture.adapter.attempts.size() > retry_index &&
            fixture.adapter.attempts[retry_index].revision == failed.revision &&
            fixture.adapter.attempts[retry_index].widgets.size() == failed.widgets.size() &&
            exported_text(fixture.adapter.attempts[retry_index]) == exported_text(failed) &&
            body_list(fixture.adapter.attempts[retry_index]).state.records == body_list(failed).state.records,
            "Query presentation retry changed its failed actual revision or native projected contents");
        for (std::size_t i = 0; i != failed.widgets.size(); ++i)
            check(fixture.adapter.attempts[retry_index].widgets[i].spec == failed.widgets[i].spec &&
                fixture.adapter.attempts[retry_index].widgets[i].state.enabled == failed.widgets[i].state.enabled &&
                fixture.adapter.attempts[retry_index].widgets[i].state.visible == failed.widgets[i].state.visible,
                "Query presentation retry changed a retained widget identity or input eligibility");
        check(forms.accepted_query() == query.token && forms.body_ready() && !forms.presentation_pending() &&
            forms.view().revision == fixture.adapter.terminal.snapshot().revision && !forms.next_request(),
            "Exact actual publication retry failed to retain the semantic receipt and acknowledge current body input separately");
    }
}

void local_draft_publication_debt_preserves_an_accepted_query_receipt() {
    for (const bool after_install : {false,true}) {
        Fixture fixture; fixture.open(); auto& forms = fixture.forms;
        const auto receipt = forms.accepted_query();
        check(receipt.has_value(),"The local draft retry fixture lacks its accepted mandatory paired query");
        fixture.adapter.fail_before = !after_install; fixture.adapter.fail_after = after_install;
        fixture.adapter.terminal.input("x");
        check(forms.presentation_pending() && forms.accepted_query() == receipt && !forms.next_request(),
            "Failed local draft publication erased the paired-query receipt or admitted native work");
        const auto failed = fixture.adapter.attempts.back();
        check(editor(failed).state.text == "x" &&
            (fixture.adapter.terminal.snapshot().revision == failed.revision) == after_install,
            "Local draft fault did not exercise actual terminal installation on the selected side of failure");
        const auto retry_index = fixture.adapter.attempts.size(); forms.retry_presentation();
        check(fixture.adapter.attempts.size() > retry_index &&
            fixture.adapter.attempts[retry_index].revision == failed.revision &&
            editor(fixture.adapter.attempts[retry_index]).spec.key == editor(failed).spec.key &&
            exported_text(fixture.adapter.attempts[retry_index]) == exported_text(failed),
            "Semantic-receipt retention replaced the exact failed local draft transaction");
        check(forms.accepted_query() == receipt && !forms.presentation_pending() &&
            editor(forms.view()).state.text == "x" && editor(fixture.adapter.terminal.snapshot()).state.text == "x" &&
            !forms.next_request(),"Successful local draft retry changed the semantic receipt or submitted native work");
    }
}

void prepared_native_query_revokes_receipt_before_sequence_backpressure_clears() {
    bool busy = false; unsigned allocations = 0; std::uint64_t sequence = 14000;
    Fixture* active = nullptr;
    Fixture fixture([&]() -> std::optional<std::uint64_t> {
        ++allocations;
        if (busy) {
            check(active && !active->forms.accepted_query(),
                "The sequence allocator observed an old query receipt after new native work was prepared");
            return std::nullopt;
        }
        return ++sequence;
    });
    active = &fixture; auto& forms = fixture.forms; const auto receipt = forms.accepted_query();
    check(receipt.has_value(),"Backpressure receipt fixture lacks its initial accepted query");
    forms.request_observation(); forms.tick();
    check(forms.accepted_query() == receipt,"An undrained poll revoked its semantic receipt before native reservation");
    busy = true;
    check(!forms.next_request() && allocations == 2 && !forms.accepted_query() && !forms.body_ready(),
        "A native query waiting for its outer sequence retained a stale semantic receipt");
    forms.request_observation(); forms.tick();
    check(!forms.accepted_query() && allocations == 2,
        "A deferred poll or tick restored the revoked receipt or retried the allocator");
    busy = false; const auto query = fixture.take();
    check(query.token.sequence == receipt->sequence + 1 && !forms.accepted_query() &&
        !std::get<DocumentEngineRequest>(query.action).intent && allocations == 3,
        "Retained prepared query lost its sequence or recovered its predecessor's receipt before completion");
    check(fixture.complete_document(query,controls(),{7,11,14}) && forms.accepted_query() == query.token,
        "The retained query could not replace the revoked receipt with its own exact accepted token");
    forms.tick();
    check(forms.body_ready() && forms.accepted_query() == query.token && !forms.next_request(),
        "Backpressure settlement stranded input or fabricated a further native query");
}

void foreground_and_shutdown_revoke_accepted_query_receipts() {
    Fixture fixture; auto& forms = fixture.forms; const auto initial = forms.accepted_query();
    check(initial.has_value(),"Lifecycle receipt fixture lacks its initial semantic query");
    forms.foreground(false);
    check(!forms.accepted_query() && !forms.body_ready() && !forms.next_request(),
        "Foreground loss retained a semantic query receipt or native admission");
    forms.foreground(true);
    check(!forms.accepted_query(),"Foreground restoration revived a receipt without a fresh paired query");
    const auto query = fixture.take();
    check(query.token != *initial && fixture.complete_document(query,controls(),{7,11,14}) &&
        forms.accepted_query() == query.token,
        "Foreground recovery did not establish a fresh exact paired-query receipt");
    forms.tick(); forms.shutdown();
    check(forms.closed() && !forms.accepted_query() && !forms.body_ready() && !forms.next_request(),
        "Shutdown retained an accepted-query receipt or admitted new native work");
    check(!forms.complete(query.token,fixture.observation(query,controls(),{7,11,14})) && !forms.accepted_query(),
        "Post-shutdown completion resurrected a retired semantic query receipt");
}

void lifecycle_reentry_during_query_draft_publication_cannot_restore_a_receipt() {
    for (unsigned transition = 0; transition != 4; ++transition) {
        Fixture fixture; auto& forms = fixture.forms; const auto begin = fixture.begin();
        check(forms.complete(begin.token,DocumentFormsControlReply{FormDraftOutcome::accepted,
            leased(text_control(10,"First field"))}),
            "Reentrant query receipt fixture did not establish a native leased form editor");
        forms.tick(); const auto query = fixture.take(); bool entered = false;
        fixture.adapter.during_present = [&] {
            if (std::exchange(entered,true)) return;
            if (transition == 0) forms.request_observation();
            if (transition == 1) forms.foreground(false);
            if (transition == 2) forms.viewport({40,12});
            if (transition == 3) forms.shutdown();
        };
        const bool consumed = fixture.complete_document(query,controls(),{7,11,15});
        fixture.adapter.during_present = {};
        check(consumed && entered && forms.last_error().empty(),
            "Reentrant receipt fixture did not complete the query through actual draft presentation");
        check(transition == 0 ? forms.accepted_query() == query.token : !forms.accepted_query(),
            "A lifecycle change during paired-query publication was overwritten by a late semantic receipt");
        if (transition == 3)
            check(forms.closed() && !forms.next_request(),"Shutdown inside query presentation did not close native admission");
        check(!forms.complete(query.token,fixture.observation(query,controls(),{7,11,15})),
            "Reentrant query completion consumed its outer native identity twice");
    }
}
void background_presentation_hints_coalesce_into_one_fresh_actual_revision() {
    unsigned allocations = 0; std::uint64_t sequence = 15000;
    Fixture fixture([&]() -> std::optional<std::uint64_t> { ++allocations; return ++sequence; });
    auto& forms = fixture.forms; forms.foreground(false);
    const auto attempts = fixture.adapter.attempts.size(); const auto revision = forms.view().revision;
    const auto epoch = forms.input_epoch(); const auto prior = exported_text(forms.view());
    for (unsigned i = 0; i != 8; ++i) forms.request_presentation();
    check(fixture.adapter.attempts.size() == attempts && forms.input_epoch() == epoch && allocations == 1 &&
        !forms.accepted_query() && forms.presentation_pending(),
        "Background presentation hints published or allocated synchronously, changed authority, or invented a query receipt");
    forms.tick();
    check(fixture.adapter.attempts.size() == attempts + 1 && forms.view().revision > revision &&
        forms.view().revision == fixture.adapter.terminal.snapshot().revision &&
        exported_text(forms.view()) == prior && forms.input_epoch() == epoch && !forms.presentation_pending(),
        "Coalesced background hints did not present one strictly newer actual local revision with unchanged scene and authority");
    forms.tick();
    check(fixture.adapter.attempts.size() == attempts + 1 && !forms.body_ready() && !forms.next_request() &&
        allocations == 1 && !forms.accepted_query(),
        "A background local repaint repeated publication, queried the engine, or restored input authority");
    forms.shutdown(); forms.request_presentation(); forms.tick();
    check(forms.closed() && fixture.adapter.attempts.size() == attempts + 1 && allocations == 1,
        "A presentation hint reopened a stopped compositor or reached its actual adapter");
}

void presentation_hint_callbacks_defer_until_the_current_actual_publication_finishes() {
    unsigned allocations = 0; std::uint64_t sequence = 16000;
    Fixture fixture([&]() -> std::optional<std::uint64_t> { ++allocations; return ++sequence; });
    auto& forms = fixture.forms; forms.foreground(false);
    const auto attempts = fixture.adapter.attempts.size(); const auto epoch = forms.input_epoch();
    bool entered = false;
    fixture.adapter.during_present = [&] {
        if (std::exchange(entered,true)) return;
        const auto in_callback = fixture.adapter.attempts.size();
        forms.request_presentation(); forms.request_presentation(); forms.tick();
        check(fixture.adapter.attempts.size() == in_callback && !forms.next_request() && allocations == 1,
            "A presentation hint inside actual present recursively published or entered native execution");
    };
    forms.request_presentation(); forms.tick(); fixture.adapter.during_present = {};
    check(entered && fixture.adapter.attempts.size() == attempts + 1 && forms.presentation_pending() &&
        forms.view().revision == fixture.adapter.terminal.snapshot().revision && forms.input_epoch() == epoch,
        "A callback hint was lost or published its next scene before the current actual transaction finished");
    const auto first = forms.view().revision; forms.tick();
    check(fixture.adapter.attempts.size() == attempts + 2 && forms.view().revision > first &&
        forms.view().revision == fixture.adapter.terminal.snapshot().revision && !forms.presentation_pending() &&
        !forms.body_ready() && !forms.next_request() && allocations == 1 && forms.input_epoch() == epoch,
        "The deferred callback hints failed to coalesce into one newer actual local publication without native work");
}

void presentation_hints_retry_the_exact_failed_origin_before_a_newer_scene() {
    for (const bool after_install : {false,true}) {
        unsigned allocations = 0; std::uint64_t sequence = 17000;
        Fixture fixture([&]() -> std::optional<std::uint64_t> { ++allocations; return ++sequence; });
        auto& forms = fixture.forms; forms.foreground(false); const auto epoch = forms.input_epoch();
        fixture.adapter.fail_before = !after_install; fixture.adapter.fail_after = after_install;
        forms.request_presentation(); bool threw = false;
        try { forms.tick(); } catch (const std::runtime_error&) { threw = true; }
        check(threw && forms.presentation_pending() && !forms.body_ready() && allocations == 1,
            "Hinted background publication did not retain its failed local transaction");
        const auto failed = fixture.adapter.attempts.back();
        check((fixture.adapter.terminal.snapshot().revision == failed.revision) == after_install,
            "Hinted local publication fault did not distinguish before-install and after-install failure");
        const auto attempts = fixture.adapter.attempts.size();
        for (unsigned i = 0; i != 8; ++i) forms.request_presentation();
        forms.tick();
        check(fixture.adapter.attempts.size() == attempts && forms.view().revision == failed.revision &&
            forms.presentation_pending() && !forms.next_request() && allocations == 1,
            "New presentation hints superseded a failed exact local transaction or entered native execution");
        const auto retry_index = fixture.adapter.attempts.size(); forms.retry_presentation();
        check(fixture.adapter.attempts.size() == retry_index + 2,
            "Exact retry did not publish its old origin once before the one coalesced current hinted scene");
        const auto& retried = fixture.adapter.attempts[retry_index];
        const auto& current = fixture.adapter.attempts[retry_index+1];
        check(retried.revision == failed.revision && retried.modal_root == failed.modal_root &&
            retried.client_size == failed.client_size && retried.widgets.size() == failed.widgets.size() &&
            exported_text(retried) == exported_text(failed),
            "A hinted publication retry changed the retained failed origin, revision, geometry, or scene contents");
        for (std::size_t i = 0; i != failed.widgets.size(); ++i)
            check(retried.widgets[i].spec == failed.widgets[i].spec &&
                retried.widgets[i].state.enabled == failed.widgets[i].state.enabled &&
                retried.widgets[i].state.visible == failed.widgets[i].state.visible,
                "Exact hinted retry changed a retained widget identity or input visibility");
        check(current.revision > failed.revision && current.revision == forms.view().revision &&
            current.revision == fixture.adapter.terminal.snapshot().revision &&
            exported_text(current) == exported_text(failed) && !forms.presentation_pending() &&
            !forms.body_ready() && !forms.next_request() && allocations == 1 && forms.input_epoch() == epoch &&
            !forms.accepted_query(),
            "The post-retry hint failed to create a newer actual background revision or changed native authority");
    }
}

void local_presentation_hints_preserve_the_modal_draft_receipt_and_native_lease() {
    unsigned allocations = 0; std::uint64_t sequence = 18000;
    Fixture fixture([&]() -> std::optional<std::uint64_t> { ++allocations; return ++sequence; });
    fixture.open(); auto& forms = fixture.forms; auto& terminal = fixture.adapter.terminal;
    terminal.input("kept local draft"); const auto key = editor(forms.view()).spec.key;
    terminal.text_selection(key,{12,3}); forms.tick();
    const auto receipt = forms.accepted_query(); const auto epoch = forms.input_epoch();
    const auto focus = terminal.focused(); const auto before = allocations;
    const auto attempts = fixture.adapter.attempts.size(); const auto revision = forms.view().revision;
    for (unsigned i = 0; i != 8; ++i) forms.request_presentation();
    check(receipt.has_value() && forms.accepted_query() == receipt && allocations == before && forms.input_epoch() == epoch &&
        fixture.adapter.attempts.size() == attempts,
        "A local presentation hint revoked its paired receipt or synchronously changed draft/native authority");
    forms.tick();
    check(fixture.adapter.attempts.size() == attempts + 1 && forms.view().revision > revision &&
        forms.view().revision == terminal.snapshot().revision &&
        forms.accepted_query() == receipt && editor(forms.view()).spec.key == key &&
        editor(forms.view()).state.text == "kept local draft" && editor(forms.view()).state.enabled &&
        terminal.focused() == focus && terminal.text_selection(key) == gui::TextSelection{12,3} &&
        forms.local_selection() == FormByteSelection{12,3} && forms.input_epoch() == epoch &&
        !forms.next_request() && allocations == before,
        "A hinted local repaint changed the real modal draft, focus, source selection, receipt, or native lease authority");
    fixture.click("Apply"); const auto apply = fixture.take();
    const auto* draft = std::get_if<FormDraftRequest>(&apply.action);
    check(draft && std::holds_alternative<ReplaceFormText>(draft->action) &&
        std::get<ReplaceFormText>(draft->action).expected == FormLease{begin_version,10,101} &&
        std::get<ReplaceFormText>(draft->action).text == "kept local draft" && !forms.accepted_query(),
        "A local repaint changed the exact native lease/text of the later deliberate Apply");
}
void observation_hint_retries_a_rejected_mandatory_query_with_a_fresh_token() {
    Fixture fixture;
    auto& forms=fixture.forms;
    forms.foreground(false); forms.foreground(true);
    const auto rejected=fixture.take();
    auto conflict=fixture.observation(rejected,controls("conflicting same revision"));
    check(forms.complete(rejected.token,std::move(conflict)),
        "Mandatory query conflict was not consumed by its exact outer token");
    forms.tick();
    check(!forms.accepted_query() && !forms.body_ready() && !forms.last_error().empty() && !forms.next_request(),
        "Rejected mandatory observation armed input, forged acceptance, or retried without an explicit hint");
    const auto epoch=forms.input_epoch();
    const auto attempts=fixture.adapter.attempts.size();
    const auto focus=fixture.adapter.terminal.focused();
    for (unsigned hint=0;hint!=8;++hint) forms.request_observation();
    check(forms.input_epoch()==epoch && fixture.adapter.attempts.size()==attempts &&
        fixture.adapter.terminal.focused()==focus && !forms.accepted_query(),
        "Mandatory readonly retry hint changed foreground, focus, publication or query acceptance synchronously");
    const auto fresh=fixture.take();
    const auto* query=std::get_if<DocumentEngineRequest>(&fresh.action);
    check(query && !query->intent && fresh.token.generation==rejected.token.generation &&
        fresh.token.sequence>rejected.token.sequence &&
        query->token.id==std::get<DocumentEngineRequest>(rejected.action).token.id+1,
        "Explicit mandatory retry reused a retired token or submitted a native action instead of a fresh query");
    check(!forms.complete(rejected.token,fixture.observation(rejected)),
        "Retired mandatory completion consumed or rebased its fresh retry");
    check(fixture.complete_document(fresh,controls("fresh native state"),{7,11,14}),
        "Fresh readonly mandatory observation could not settle");
    forms.tick();
    check(forms.accepted_query()==fresh.token && forms.body_ready() && !forms.next_request() &&
        exported_text(forms.view()).find("fresh native state")!=std::string::npos,
        "Mandatory retry hints duplicated a query or failed to publish only the newly accepted native state");
}

std::vector<FormControl> single_controls() {
    auto fields=controls(); auto& control=fields.front();
    control.kind=FormKind::select_one; control.native_type="select-one";
    // The separate document-actions profile grants this operation. Frozen
    // FormDraft select-one capability bits remain unchanged and unnecessary.
    control.capabilities=0;
    control.state=FormSelectState{false,true,{{101,"Same label",true,false,false},
        {202,"Same label",false,false,false},{303,"Disabled option",false,true,false}}};
    return fields;
}
const gui::Widget& single_options(const gui::Snapshot& snapshot) {
    const auto found=std::find_if(snapshot.widgets.begin(),snapshot.widgets.end(),[](const auto& widget){
        return widget.spec.kind==gui::Kind::choice && widget.spec.key.id.ends_with("/single-options");
    });
    check(found!=snapshot.widgets.end(),"Single-option modal lacks its generic choice widget");
    return *found;
}
NativeFormsDocumentObservation action_observation(std::vector<FormControl> fields,FormVersion version) {
    NativeFormsDocumentObservation observation;
    observation.publication=version; observation.body.epoch=version.epoch;
    observation.body.snapshot=document(fields,version); observation.body.editor_state=DocumentEditorState{1,0};
    observation.forms={document_forms_version,version,std::move(fields)};
    return observation;
}

void single_option_chooser_is_local_until_apply_and_cancel_restores_without_native_work() {
    unsigned allocations=0;
    Fixture fixture([&]() -> std::optional<std::uint64_t> { return 100+ ++allocations; },true,single_controls());
    auto& forms=fixture.forms;
    fixture.activate_row();
    check(forms.modal_open() && !forms.draft_phase() && !forms.body_ready() &&
        single_options(forms.view()).state.selected=="101" && allocations==1 && !forms.next_request(),
        "Opening single select issued native Begin/popup work or widened FormDraft editing");
    const auto key=single_options(forms.view()).spec.key;
    check(fixture.adapter.terminal.focus(key),"Real terminal could not focus the generic local single chooser");
    forms.handle(gui::WidgetEvent{key,gui::ChooseOption{"202"}});
    check(single_options(forms.view()).state.selected=="202" && !forms.next_request() && allocations==1,
        "Local option selection issued a native request or replaced option identity with duplicate label");
    forms.handle(gui::WidgetEvent{key,gui::ChooseOption{"303"}});
    check(single_options(forms.view()).state.selected=="202" && !forms.next_request(),
        "Disabled single option was admitted by a forged generic selection");
    fixture.click("Cancel");
    check(!forms.modal_open() && forms.body_ready() && !forms.next_request() && allocations==1,
        "Cancel submitted native selection/query work instead of restoring its unchanged suspended publication");
    fixture.activate_row();
    check(single_options(forms.view()).state.selected=="101" && !forms.next_request(),
        "Canceled local option was mistaken for actual native selected state");
}

void single_option_apply_retains_exact_ids_and_uses_actual_readback_after_fresh_query() {
    bool busy=false; unsigned allocations=0;
    Fixture fixture([&]() -> std::optional<std::uint64_t> {
        ++allocations; return busy ? std::nullopt : std::optional<std::uint64_t>{1000+allocations};
    },true,single_controls());
    auto& forms=fixture.forms; fixture.activate_row();
    forms.handle(gui::WidgetEvent{single_options(forms.view()).spec.key,gui::ChooseOption{"202"}});
    busy=true; fixture.click("Apply");
    check(!forms.next_request() && allocations==2 && forms.modal_open() && !button_enabled(forms.view(),"Apply"),
        "Busy single-option Apply escaped reservation backpressure or left another Apply enabled");
    const auto waiting=single_options(forms.view()).spec.key;
    forms.handle(gui::WidgetEvent{waiting,gui::ChooseOption{"101"}});
    busy=false; const auto request=fixture.take();
    const auto* action=std::get_if<ChooseSingleDocumentOption>(&request.action);
    check(action && action->expected==DocumentVersion{7,11,13} && action->node==10 && action->option==202 &&
        request.token.sequence==1003 && allocations==3 && !forms.accepted_query(),
        "Single-option Apply rebased its displayed Version, option ID, control ID or reserved outer sequence");
    auto actual=single_controls(); // Native change handler retained the original option.
    auto completion=DocumentBodyCompletion{DocumentBodyOutcome::completed,action_observation(actual,{7,11,14})};
    check(forms.complete(request.token,completion) && !forms.modal_open() && !forms.body_ready() && !forms.accepted_query(),
        "Single-option action readback rearmed the old body or became a query receipt");
    check(!forms.complete(request.token,completion),"Single-option action completion was consumed twice");
    fixture.refresh(actual,{7,11,14});
    check(forms.body_ready() && forms.accepted_query() && !forms.next_request(),
        "Fresh current paired query failed to settle the single-option completion barrier");
    fixture.activate_row();
    check(single_options(forms.view()).state.selected=="101" && !forms.next_request(),
        "Chooser displayed its requested option instead of the actual native handler readback");
}

void every_body_outcome_requires_a_fresh_published_query_and_never_replays_queued_input() {
    for (const auto outcome:{DocumentBodyOutcome::completed,DocumentBodyOutcome::needs_current_observation,
                            DocumentBodyOutcome::rejected,DocumentBodyOutcome::indeterminate}) {
        Fixture fixture; auto& forms=fixture.forms;
        fixture.activate_row("Ordinary project link");
        fixture.activate_row("Ordinary project link"); // Same-version stale queued input must be cleared.
        const auto action=fixture.take();
        DocumentBodyCompletion completion{outcome,{}};
        if (outcome==DocumentBodyOutcome::completed) completion.publication=action_observation(controls(),initial_version);
        check(forms.complete(action.token,completion) && !forms.body_ready() && !forms.accepted_query(),
            "A certain body-action outcome rearmed input before a fresh current query");
        check(!forms.complete(action.token,completion),"A consumed body action accepted duplicate completion");
        const auto query=fixture.take();
        check(!std::get<DocumentEngineRequest>(query.action).intent && query.token.sequence>action.token.sequence,
            "A body outcome replayed stale queued input or fabricated a query token from action readback");
        check(fixture.complete_document(query,controls("current observed"),{7,12,1}) && forms.accepted_query()==query.token,
            "A real current query did not establish its own distinct exact receipt");
        fixture.adapter.fail_before=true;
        bool threw=false;
        try { forms.tick(); } catch (const std::runtime_error&) { threw=true; }
        check(threw && forms.presentation_pending() && !forms.body_ready() && !forms.next_request(),
            "Fresh semantic query acceptance rearmed body input through failed actual publication");
        const auto failed=forms.view(); forms.retry_presentation();
        check(forms.body_ready() && !forms.presentation_pending() && !forms.next_request() &&
            fixture.adapter.attempts.back().revision==failed.revision &&
            exported_text(forms.view()).find("current observed")!=std::string::npos,
            "Exact current publication retry repeated an action or failed to restore observed body input");
    }
}

void body_action_readback_cannot_borrow_query_or_nested_tokens() {
    for (const bool foreign_query_kind:{false,true}) {
        Fixture fixture; fixture.activate_row("Ordinary project link"); const auto action=fixture.take();
        auto actual=action_observation(controls(),{7,11,14});
        actual.body.request_id=std::get<DocumentEngineRequest>(action.action).token.id;
        const bool consumed=foreign_query_kind ? fixture.forms.complete(action.token,std::move(actual)) :
            fixture.forms.complete(action.token,DocumentBodyCompletion{DocumentBodyOutcome::completed,std::move(actual)});
        check(consumed && !fixture.forms.body_ready() && !fixture.forms.accepted_query() && !fixture.forms.last_error().empty(),
            "Action readback accepted a query completion kind or producer-invented nested Controller token");
        fixture.refresh(controls(),{7,11,14});
        check(fixture.forms.body_ready(),"Malformed action readback was replayed or prevented a fresh current observation");
    }
    Fixture fixture; fixture.forms.document_actions_available(false); fixture.forms.tick();
    fixture.activate_row("Ordinary project link");
    const auto unsupported=fixture.take();
    check(std::get<DocumentEngineRequest>(unsupported.action).intent &&
        !fixture.forms.queue_selection({{71,0},{71,1}}) &&
        exported_text(fixture.forms.view()).find("document-actions-v1")!=std::string::npos,
        "An old profile lost its owner-rejectable intent, admitted host selection, or concealed its concrete missing capability");
    check(fixture.forms.fail(unsupported.token,DocumentRequestFailure::known_rejected) && !fixture.forms.body_ready(),
        "The execution owner's no-effect unsupported-body rejection rearmed the old view");
}
void single_chooser_capability_loss_retires_only_undelivered_apply() {
    for (const bool failed_publication:{false,true}) {
        Fixture fixture(true,single_controls()); auto& forms=fixture.forms;
        fixture.activate_row();
        forms.handle(gui::WidgetEvent{single_options(forms.view()).spec.key,gui::ChooseOption{"202"}});
        fixture.click("Apply");
        bool revoked=false;
        if (failed_publication) fixture.adapter.fail_after=true;
        else fixture.adapter.during_present=[&] {
            if (!revoked) { revoked=true; forms.document_actions_available(false); }
        };
        check(!forms.next_request(),"A chooser Apply escaped its revoked or failed disable publication");
        if (failed_publication) {
            check(forms.presentation_pending(),"Injected post-install chooser request publication failure was not retained");
            forms.document_actions_available(false); forms.retry_presentation();
        }
        forms.tick(); const auto fresh=fixture.take();
        check(!std::get<DocumentEngineRequest>(fresh.action).intent && !forms.accepted_query(),
            "Capability loss redelivered an unhanded chooser action or forged a paired receipt");
        check(fixture.complete_document(fresh,single_controls(),initial_version),
            "Capability-loss paired observation failed to settle");
        forms.tick();
        check(!forms.modal_open() && forms.body_ready() && !forms.next_request(),
            "Retired chooser Apply stranded a modal or resurfaced after its mandatory current query");
    }
    Fixture fixture(true,single_controls()); fixture.activate_row(); fixture.click("Apply");
    const auto delivered=fixture.take(); fixture.forms.document_actions_available(false); fixture.forms.tick();
    check(fixture.forms.complete(delivered.token,DocumentBodyCompletion{DocumentBodyOutcome::needs_current_observation,{}}),
        "Capability loss discarded the settlement obligation of an already delivered chooser action");
    fixture.refresh(single_controls(),{7,12,1});
    check(fixture.forms.body_ready() && !fixture.forms.modal_open(),
        "Delivered chooser settlement did not recover through a fresh actual paired query");
}

std::vector<FormControl> input_button_controls(std::string type = "button") {
    FormControl control; control.node=10; control.kind=FormKind::unsupported;
    control.native_type=std::move(type); control.label="Native action";
    control.focusable=true; control.focused=true; control.complete=true;
    return {std::move(control)};
}

void input_buttons_use_typed_activation_without_a_form_lease_or_modal() {
    for (const auto type:{"button","reset","submit"}) {
        const auto fields=input_button_controls(type); Fixture fixture(true,fields); auto& forms=fixture.forms;
        const auto& list=body_list(forms.view()); const auto id=row(forms.view(),"Native action");
        const auto record=std::find_if(list.state.records.begin(),list.state.records.end(),
            [&](const auto& value){return value.id==id;});
        check(record!=list.state.records.end() && record->activatable && !fields.front().lease && !fields.front().capabilities,
            "A published input button required form-edit capability or a native lease");
        check(fixture.adapter.terminal.focus(list.spec.key),"Real terminal could not focus the input-button list");
        fixture.adapter.terminal.input("\r");
        check(fixture.callbacks && !forms.modal_open() && !forms.draft_phase() && !forms.body_ready(),
            "Real terminal input-button activation opened a draft or left the old body armed");
        const auto request=fixture.take(); const auto* action=std::get_if<ActivateDocumentControl>(&request.action);
        check(action && action->expected==DocumentVersion{7,11,13} && action->node==10 && !forms.accepted_query(),
            "Input button became Begin/Apply or lost its exact displayed version and native node");
        fixture.activate_row("Native action");
        check(!forms.next_request(),"Repeated input-button activation escaped the one-outstanding-action ledger");
        const auto completion=DocumentBodyCompletion{DocumentBodyOutcome::completed,action_observation(fields,{7,11,14})};
        check(forms.complete(request.token,completion) && !forms.body_ready() && !forms.accepted_query() &&
            !forms.complete(request.token,completion),"Input-button readback rearmed the old body or settled twice");
        fixture.refresh(fields,{7,11,14});
        check(forms.body_ready() && !forms.modal_open() && forms.accepted_query() && !forms.next_request(),
            "Input-button completion did not settle through one fresh current paired query");
    }
}

void input_button_eligibility_does_not_widen_unsupported_or_concealed_controls() {
    for (unsigned variant=0;variant!=11;++variant) {
        auto fields=input_button_controls(); auto& control=fields.front();
        if (variant==0) control.complete=false;
        else if (variant==1) { control.disabled=true; control.focused=false; }
        else if (variant==2) control.read_only=true;
        else if (variant==3) { control.focusable=false; control.focused=false; }
        else if (variant==4) {
            control.omitted=true; control.label.clear(); control.focusable=false; control.focused=false;
        } else if (variant==5) {
            control.kind=FormKind::secure_readonly; control.native_type="password"; control.label.clear();
            control.omitted=true; control.focusable=false; control.focused=false;
        }
        else if (variant==6) control.native_type="file";
        else if (variant==7) control.native_type="image";
        else if (variant==8) control.native_type="radio";
        else if (variant==9) control.native_type="date";
        Fixture fixture(false); auto& forms=fixture.forms; forms.tick(); const auto initial=fixture.take();
        auto observation=fixture.observation(initial,fields);
        if (variant==4 || variant==5) observation.body.snapshot->active_node.reset();
        check(forms.complete(initial.token,std::move(observation)),"Negative input-button fixture rejected its paired observation");
        forms.tick();
        check(forms.body_ready(),"Negative input-button fixture failed to admit a current paired observation");
        if (variant==10) { forms.document_actions_available(false); forms.tick(); }
        const auto& list=body_list(forms.view());
        const auto record=std::find_if(list.state.records.begin(),list.state.records.end(),
            [](const auto& value){return value.id=="node/10";});
        check(record==list.state.records.end() || !record->activatable,
            "An unavailable, masked or unsupported native control advertised button activation");
        forms.handle(gui::WidgetEvent{list.spec.key,gui::ActivateRecord{"node/10"}});
        check(!forms.next_request() && !forms.modal_open() && !forms.draft_phase(),
            "Forged activation widened a native control's availability or created form-edit authority");
    }
    Fixture fixture(false); auto& forms=fixture.forms; forms.tick(); const auto initial=fixture.take();
    auto observation=fixture.observation(initial,input_button_controls());
    observation.body.snapshot->nodes[1].tag="button";
    observation.forms.controls.clear(); // Native button elements use the body route without an input descriptor.
    check(forms.complete(initial.token,std::move(observation)),"Ordinary button fixture rejected its paired observation");
    forms.tick(); fixture.activate_row("Native action"); const auto request=fixture.take();
    const auto* action=std::get_if<DocumentEngineRequest>(&request.action);
    check(action && action->intent && action->intent->action==DocumentAction::activate && action->intent->node==10,
        "Ordinary button element lost its existing Controller body-action route");
}

void input_button_backpressure_preserves_the_shared_64bit_reservation() {
    const auto origin=(std::uint64_t{1}<<60)+123; auto sequence=origin; unsigned allocations=0; bool busy=false;
    const auto fields=input_button_controls("submit");
    Fixture fixture([&]() -> std::optional<std::uint64_t> {
        ++allocations; return busy ? std::nullopt : std::optional<std::uint64_t>{++sequence};
    },true,fields);
    auto& forms=fixture.forms; ++sequence; // An independent physical-input reservation.
    busy=true; fixture.activate_row("Native action");
    check(!forms.next_request() && allocations==2 && !forms.body_ready() && !forms.modal_open(),
        "Busy button activation was discarded, executed without a sequence or converted to a modal");
    fixture.activate_row("Native action"); forms.request_observation(); forms.request_observation(); forms.tick();
    check(allocations==2 && !forms.next_request() && allocations==3,
        "Polling/repeated activation reserved from tick or replaced the prepared button action");
    busy=false; const auto request=fixture.take(); const auto* action=std::get_if<ActivateDocumentControl>(&request.action);
    check(action && action->expected==DocumentVersion{7,11,13} && action->node==10 &&
        request.token.sequence==origin+3 && allocations==4 && !forms.accepted_query(),
        "Backpressure rebased button metadata, narrowed its sequence or lost the owner's exact reservation gap");
    forms.request_observation(); forms.tick();
    check(!forms.next_request() && allocations==4,"Delivered button action reserved a second global identity");
    check(forms.complete(request.token,DocumentBodyCompletion{DocumentBodyOutcome::needs_current_observation,{}}),
        "Backpressured button action lost its delivered settlement obligation");
    fixture.refresh(fields,{7,11,14});
    check(forms.body_ready() && !forms.next_request() && allocations==5,
        "Button settlement replayed activation or turned coalesced polls into duplicate queries");
}

void input_button_lifecycle_retires_only_undelivered_activation() {
    for (unsigned transition=0;transition!=6;++transition) {
        bool busy=false; unsigned allocations=0; std::uint64_t sequence=4000;
        const auto fields=input_button_controls("reset");
        Fixture fixture([&]() -> std::optional<std::uint64_t> {
            ++allocations; return busy ? std::nullopt : std::optional<std::uint64_t>{++sequence};
        },true,fields);
        auto& forms=fixture.forms; fixture.activate_row("Native action"); bool revoked=false;
        if (transition==1 || transition==4 || transition==5) {
            busy=true; check(!forms.next_request(),"Lifecycle fixture failed to retain a busy activation");
        } else if (transition==2) {
            fixture.adapter.during_present=[&] {
                if (!revoked) { revoked=true; forms.document_actions_available(false); }
            };
            check(!forms.next_request() && revoked,"Capability loss during publication handed out an unowned activation");
            fixture.adapter.during_present={};
        } else if (transition==3) {
            fixture.adapter.fail_after=true;
            check(!forms.next_request() && forms.presentation_pending(),
                "Activation publication failure did not retain exact undelivered request debt");
        }
        const auto before=allocations;
        if (transition==4) forms.foreground(false);
        else if (transition==5) forms.shutdown();
        else forms.document_actions_available(false);
        if (transition==3) forms.retry_presentation();
        if (transition==4 || transition==5) {
            check(!forms.next_request() && allocations==before && !forms.body_ready(),
                "Foreground loss/shutdown allocated or resurrected undelivered button input");
        }
        if (transition==5) { check(forms.closed(),"Shutdown did not close the button compositor"); continue; }
        busy=false;
        if (transition==4) forms.foreground(true);
        else forms.document_actions_available(true);
        forms.tick(); const auto fresh=fixture.take(); const auto* query=std::get_if<DocumentEngineRequest>(&fresh.action);
        check(query && !query->intent && allocations==before+1 && !forms.accepted_query(),
            "Restoring capability/foreground redelivered retired activation or skipped its current query");
        check(fixture.complete_document(fresh,fields,{7,11,14}),"Retired button activation stranded its paired refresh");
        forms.tick();
        check(forms.body_ready() && !forms.modal_open() && !forms.next_request(),
            "Retired input-button activation resurfaced after current-state recovery");
    }
}

void delivered_input_button_outcomes_refresh_without_replay_or_stale_authority() {
    for (unsigned outcome=0;outcome!=7;++outcome) {
        const auto fields=input_button_controls(); Fixture fixture(true,fields); auto& forms=fixture.forms;
        fixture.activate_row("Native action"); const auto action=fixture.take();
        auto foreign=action.token; ++foreign.sequence;
        check(!forms.complete(foreign,DocumentBodyCompletion{DocumentBodyOutcome::indeterminate,{}}),
            "Foreign completion retired the delivered input-button action");
        if (outcome==4) { forms.document_actions_available(false); forms.tick(); }
        if (outcome==5) { forms.foreground(false); forms.tick(); }
        bool consumed=false;
        if (outcome==0) consumed=forms.complete(action.token,DocumentBodyCompletion{DocumentBodyOutcome::completed,
            action_observation(fields,{7,11,14})});
        else if (outcome==1) consumed=forms.complete(action.token,DocumentBodyCompletion{DocumentBodyOutcome::needs_current_observation,{}});
        else if (outcome==2) consumed=forms.complete(action.token,DocumentBodyCompletion{DocumentBodyOutcome::rejected,{}});
        else if (outcome==3) consumed=forms.complete(action.token,DocumentBodyCompletion{DocumentBodyOutcome::indeterminate,{}});
        else if (outcome==4) consumed=forms.fail(action.token,DocumentRequestFailure::unknown);
        else if (outcome==5) consumed=forms.fail(action.token,DocumentRequestFailure::known_rejected);
        else consumed=forms.complete(action.token,DocumentBodyCompletion{DocumentBodyOutcome::completed,
            action_observation(fields,{7,11,12})});
        check(consumed && !forms.body_ready() && !forms.accepted_query() && !forms.modal_open() &&
            !forms.complete(action.token,DocumentBodyCompletion{DocumentBodyOutcome::indeterminate,{}}) &&
            !forms.fail(action.token,DocumentRequestFailure::unknown),
            "Delivered button outcome was lost, settled twice or restored stale body authority");
        if (outcome==6) check(!forms.last_error().empty(),"Stale button readback was accepted as current native state");
        if (outcome==4) forms.document_actions_available(true);
        if (outcome==5) forms.foreground(true);
        forms.tick(); const auto fresh=fixture.take(); const auto* query=std::get_if<DocumentEngineRequest>(&fresh.action);
        check(query && !query->intent && fresh.token.sequence>action.token.sequence,
            "Delivered button outcome replayed an effect instead of requesting current paired state");
        check(fixture.complete_document(fresh,fields,{7,12,1}) && forms.accepted_query()==fresh.token,
            "Current button query did not retain its own distinct exact receipt");
        fixture.adapter.fail_before=true; bool threw=false;
        try { forms.tick(); } catch (const std::runtime_error&) { threw=true; }
        check(threw && forms.presentation_pending() && !forms.body_ready() && !forms.next_request(),
            "Button query receipt bypassed its failed actual terminal publication");
        const auto failed=forms.view(); forms.retry_presentation();
        check(forms.body_ready() && !forms.presentation_pending() && !forms.next_request() &&
            fixture.adapter.attempts.back().revision==failed.revision,
            "Button presentation retry changed the retained revision or replayed native activation");
    }
}
} // namespace

int main() {
    struct TestCase { const char* name; void (*run)(); };
    const TestCase cases[] = {
        {"actual_terminal_batch_selection_and_exact_lease",actual_terminal_batch_selection_and_exact_lease},
        {"textarea_newlines_and_number_native_editing_buffer",textarea_newlines_and_number_native_editing_buffer},
        {"synchronous_form_row_cursor_and_busy_refusal",synchronous_form_row_cursor_and_busy_refusal},
        {"readonly_and_incomplete_rows_show_only_authoritative_value",readonly_and_incomplete_rows_show_only_authoritative_value},
        {"checkbox_and_multiple_select_publish_local_drafts_before_exact_native_actions",checkbox_and_multiple_select_publish_local_drafts_before_exact_native_actions},
        {"strict_native_v2_join_and_owned_values",strict_native_v2_join_and_owned_values},
        {"single_presenter_global_revisions_and_reentrant_admission",single_presenter_global_revisions_and_reentrant_admission},
        {"exact_publication_retry_and_completion_redelivery",exact_publication_retry_and_completion_redelivery},
        {"cancel_inflight_keeps_one_outer_ledger_and_requires_paired_refresh",cancel_inflight_keeps_one_outer_ledger_and_requires_paired_refresh},
        {"stale_and_unknown_recovery_requires_fresh_native_lease_and_new_user_intent",stale_and_unknown_recovery_requires_fresh_native_lease_and_new_user_intent},
        {"completion_without_authoritative_readback_conceals_until_fresh_compatible_state",completion_without_authoritative_readback_conceals_until_fresh_compatible_state},
        {"uncertain_apply_does_not_reveal_saved_text_when_fresh_kind_is_ineligible",uncertain_apply_does_not_reveal_saved_text_when_fresh_kind_is_ineligible},
        {"uncertain_completion_publication_retries_exact_concealed_snapshot",uncertain_completion_publication_retries_exact_concealed_snapshot},
        {"foreground_recovery_preserves_draft_and_requires_explicit_native_refresh",foreground_recovery_preserves_draft_and_requires_explicit_native_refresh},
        {"foreground_transition_retries_exact_failed_draft_before_current_recovery_scene",foreground_transition_retries_exact_failed_draft_before_current_recovery_scene},
        {"explicit_reapply_survives_replacement_and_saved_text_publication_failures",explicit_reapply_survives_replacement_and_saved_text_publication_failures},
        {"immutable_forms_metadata_and_newer_native_readback_guard_paired_admission",immutable_forms_metadata_and_newer_native_readback_guard_paired_admission},
        {"concealed_and_missing_native_controls_cannot_reflow_visible_old_body_data",concealed_and_missing_native_controls_cannot_reflow_visible_old_body_data},
        {"secure_and_omitted_transition_never_exports_retained_old_buffer",secure_and_omitted_transition_never_exports_retained_old_buffer},
        {"modal_lifetimes_shutdown_and_unfocused_begin",modal_lifetimes_shutdown_and_unfocused_begin},
        {"single_select_requires_a_real_popup_owner_and_tiny_viewport_is_inert",single_select_requires_a_real_popup_owner_and_tiny_viewport_is_inert},
        {"injected_sequences_keep_shared_64bit_identity_across_navigation",injected_sequences_keep_shared_64bit_identity_across_navigation},
        {"busy_initial_query_keeps_one_inner_token_and_absorbs_poll_hints",busy_initial_query_keeps_one_inner_token_and_absorbs_poll_hints},
        {"busy_apply_keeps_exact_lease_range_text_and_nested_identity",busy_apply_keeps_exact_lease_range_text_and_nested_identity},
        {"busy_apply_cancel_foreground_and_shutdown_retire_known_unhanded_work",busy_apply_cancel_foreground_and_shutdown_retire_known_unhanded_work},
        {"invalid_sequence_sources_stop_before_any_bad_handout",invalid_sequence_sources_stop_before_any_bad_handout},
        {"maximum_sequence_is_valid_once_and_exhaustion_precedes_callback",maximum_sequence_is_valid_once_and_exhaustion_precedes_callback},
        {"sequence_callback_cannot_reenter_drain_tick_or_completion",sequence_callback_cannot_reenter_drain_tick_or_completion},
        {"sequence_callback_foreground_and_shutdown_revoke_unhanded_query",sequence_callback_foreground_and_shutdown_revoke_unhanded_query},
        {"busy_query_resize_measurement_foreground_loss_defers_inner_retirement",busy_query_resize_measurement_foreground_loss_defers_inner_retirement},
        {"allocated_and_busy_publication_retries_do_not_reserve_or_change_work",allocated_and_busy_publication_retries_do_not_reserve_or_change_work},
        {"idle_poll_bursts_coalesce_and_preserve_queued_body_action_priority",idle_poll_bursts_coalesce_and_preserve_queued_body_action_priority},
        {"modal_and_apply_polls_preserve_draft_focus_selection_and_lease",modal_and_apply_polls_preserve_draft_focus_selection_and_lease},
        {"polls_defer_through_background_and_failed_base_publication",polls_defer_through_background_and_failed_base_publication},
        {"accepted_query_receipt_keeps_exact_outer_identity_without_presentation_authority",accepted_query_receipt_keeps_exact_outer_identity_without_presentation_authority},
        {"malformed_paired_queries_never_produce_semantic_receipts",malformed_paired_queries_never_produce_semantic_receipts},
        {"immutable_forms_and_native_readback_conflicts_cannot_receipt_a_query",immutable_forms_and_native_readback_conflicts_cannot_receipt_a_query},
        {"native_control_readback_and_body_actions_never_produce_query_receipts",native_control_readback_and_body_actions_never_produce_query_receipts},
        {"semantic_query_receipt_survives_failed_actual_publication_and_exact_retry",semantic_query_receipt_survives_failed_actual_publication_and_exact_retry},
        {"local_draft_publication_debt_preserves_an_accepted_query_receipt",local_draft_publication_debt_preserves_an_accepted_query_receipt},
        {"prepared_native_query_revokes_receipt_before_sequence_backpressure_clears",prepared_native_query_revokes_receipt_before_sequence_backpressure_clears},
        {"foreground_and_shutdown_revoke_accepted_query_receipts",foreground_and_shutdown_revoke_accepted_query_receipts},
        {"lifecycle_reentry_during_query_draft_publication_cannot_restore_a_receipt",lifecycle_reentry_during_query_draft_publication_cannot_restore_a_receipt},
        {"background_presentation_hints_coalesce_into_one_fresh_actual_revision",background_presentation_hints_coalesce_into_one_fresh_actual_revision},
        {"presentation_hint_callbacks_defer_until_the_current_actual_publication_finishes",presentation_hint_callbacks_defer_until_the_current_actual_publication_finishes},
        {"presentation_hints_retry_the_exact_failed_origin_before_a_newer_scene",presentation_hints_retry_the_exact_failed_origin_before_a_newer_scene},
        {"local_presentation_hints_preserve_the_modal_draft_receipt_and_native_lease",local_presentation_hints_preserve_the_modal_draft_receipt_and_native_lease},
        {"observation_hint_retries_a_rejected_mandatory_query_with_a_fresh_token",observation_hint_retries_a_rejected_mandatory_query_with_a_fresh_token},
        {"single_option_chooser_is_local_until_apply_and_cancel_restores_without_native_work",single_option_chooser_is_local_until_apply_and_cancel_restores_without_native_work},
        {"single_option_apply_retains_exact_ids_and_uses_actual_readback_after_fresh_query",single_option_apply_retains_exact_ids_and_uses_actual_readback_after_fresh_query},
        {"every_body_outcome_requires_a_fresh_published_query_and_never_replays_queued_input",every_body_outcome_requires_a_fresh_published_query_and_never_replays_queued_input},
        {"body_action_readback_cannot_borrow_query_or_nested_tokens",body_action_readback_cannot_borrow_query_or_nested_tokens},
        {"single_chooser_capability_loss_retires_only_undelivered_apply",single_chooser_capability_loss_retires_only_undelivered_apply},
        {"input_buttons_use_typed_activation_without_a_form_lease_or_modal",input_buttons_use_typed_activation_without_a_form_lease_or_modal},
        {"input_button_eligibility_does_not_widen_unsupported_or_concealed_controls",input_button_eligibility_does_not_widen_unsupported_or_concealed_controls},
        {"input_button_backpressure_preserves_the_shared_64bit_reservation",input_button_backpressure_preserves_the_shared_64bit_reservation},
        {"input_button_lifecycle_retires_only_undelivered_activation",input_button_lifecycle_retires_only_undelivered_activation},
        {"delivered_input_button_outcomes_refresh_without_replay_or_stale_authority",delivered_input_button_outcomes_refresh_without_replay_or_stale_authority},
    };
    const char* current_case = "initialization";
    std::size_t passed = 0;
    try {
        for (const auto& test : cases) {
            current_case = test.name; const auto before = assertions; test.run(); ++passed;
            std::cout << "PASS " << test.name << " (" << assertions - before << " assertions)\n";
        }
        std::cout << "Document forms compositor policy and real retained terminal tests passed: " << passed <<
            " cases, " << assertions << " assertions; native completions are owned mocks\n";
    } catch (const std::exception& error) {
        std::cerr << "FAIL " << current_case << " after " << passed << " passed cases and " << assertions <<
            " assertions: " << error.what() << '\n'; return 1;
    }
}
