#include "appended_document_forms.hpp"
#include "engine_document_broker.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <stdexcept>
#include <thread>
#include <utility>

namespace foundation::ui {
namespace F = appended;
namespace {
struct Guard { bool& flag; explicit Guard(bool& v) : flag(v) { flag = true; } ~Guard() { flag = false; } };
F::FormVersion form_version(DocumentVersion v) { return {v.generation, v.epoch, v.revision}; }
bool same_document(F::FormVersion a, F::FormVersion b) { return a.generation == b.generation && a.epoch == b.epoch; }
bool editable(const F::FormControl& c) {
    return c.complete && !c.disabled && !c.read_only && c.focusable && !c.omitted &&
        ((F::form_has(c.capabilities, F::FormCapability::replace_text) &&
          (c.kind == F::FormKind::text || c.kind == F::FormKind::number || c.kind == F::FormKind::textarea)) ||
         (c.kind == F::FormKind::checkbox && F::form_has(c.capabilities, F::FormCapability::set_checked)) ||
         (c.kind == F::FormKind::select_many && F::form_has(c.capabilities, F::FormCapability::set_option)));
}
bool single_select(const F::FormControl& c) {
    const auto* state=std::get_if<F::FormSelectState>(&c.state);
    return c.kind==F::FormKind::select_one && c.complete && !c.disabled && !c.read_only &&
        c.focusable && !c.omitted && state && !state->multiple &&
        std::none_of(state->options.begin(),state->options.end(),[](const auto& option){return option.omitted;});
}
bool input_button(const F::FormControl& c) {
    return c.kind==F::FormKind::unsupported && c.complete && !c.disabled && !c.read_only &&
        c.focusable && !c.omitted && (c.native_type=="button" || c.native_type=="reset" || c.native_type=="submit");
}
bool concealed(const F::FormControl& c) { return c.omitted || c.kind == F::FormKind::secure_readonly; }
bool body_hidden(const DocumentSnapshot& snapshot,std::uint64_t id) {
    std::map<std::uint64_t,bool> omitted;
    for (const auto& node:snapshot.nodes) {
        const bool hidden=node.omitted || (node.parent && omitted.at(node.parent));
        omitted.emplace(node.id,hidden);
        if (node.id==id) return hidden;
    }
    return true;
}
void validate_update(const F::FormUpdate& value) {
    F::validate_form_update(value);
    constexpr std::uint64_t max_id=9007199254740991ULL;
    if (value.version.epoch>UINT32_MAX || value.version.revision>max_id || value.control.node>max_id)
        throw std::invalid_argument("Unrepresentable native control publication");
    if (const auto* select=std::get_if<F::FormSelectState>(&value.control.state))
        for (const auto& option:select->options) if (option.node>max_id)
            throw std::invalid_argument("Unrepresentable native option identity");
}
void validate_join(const NativeFormsDocumentObservation& value, std::uint64_t generation) {
    constexpr std::uint64_t max_id=9007199254740991ULL;
    if (value.protocol != F::document_forms_version || value.forms.protocol != F::document_forms_version ||
        !value.body.snapshot || !value.body.error_code.empty() || !value.body.editor_state ||
        value.publication != value.forms.version || value.publication != form_version(value.body.snapshot->version) ||
        value.publication.generation != generation || value.body.epoch != value.publication.epoch ||
        value.publication.epoch > std::numeric_limits<std::uint32_t>::max() ||
        !value.body.editor_state->revision || value.body.editor_state->revision > std::uint32_t(INT32_MAX) ||
        value.body.editor_state->flags > 31)
        throw std::invalid_argument("Invalid native-v2 document/forms join");
    F::validate_document_forms(value.forms);
    AppendedDocument checked;
    checked.accept(*value.body.snapshot); // exact current projection bounds, no narrowing
    std::map<std::uint64_t,bool> omitted;
    for (const auto& node:value.body.snapshot->nodes)
        omitted.emplace(node.id,node.omitted || (node.parent && omitted.at(node.parent)));
    for (const auto& control : value.forms.controls) {
        if (control.node>max_id) throw std::invalid_argument("Unrepresentable native control identity");
        if (const auto* select=std::get_if<F::FormSelectState>(&control.state))
            for (const auto& option:select->options) if (option.node>max_id)
                throw std::invalid_argument("Unrepresentable native option identity");
        const auto node = std::find_if(value.body.snapshot->nodes.begin(), value.body.snapshot->nodes.end(),
            [&](const auto& n) { return n.id == control.node; });
        if (node != value.body.snapshot->nodes.end() && node->kind != DocumentNodeKind::element)
            throw std::invalid_argument("Native control is not a body element");
        if (control.omitted && node != value.body.snapshot->nodes.end() && !omitted.at(node->id))
            throw std::invalid_argument("Native omitted control is visible in body");
        if (control.kind == F::FormKind::secure_readonly && node != value.body.snapshot->nodes.end() &&
            (!node->masked || !node->value.empty() || !node->name.empty() || !node->href.empty()))
            throw std::invalid_argument("Native secure body was not redacted");
    }
}
} // namespace

struct AppendedDocumentForms::Impl {
    enum class OriginKind { base, draft, local };
    struct Origin {
        OriginKind kind; std::uint64_t instance, revision;
        bool operator==(const Origin&) const = default;
    };
    struct Publication { gui::Snapshot view; Origin origin; };
    struct SingleChoice {
        DocumentVersion expected;
        F::FormControl control;
        std::optional<std::uint64_t> selected;
    };
    struct Proxy final : gui::Adapter {
        Impl& owner;
        explicit Proxy(Impl& v) : owner(v) {}
        void present(gui::Snapshot v) override { owner.base_present(std::move(v)); }
        gui::Size measure_text(const gui::TextMeasureRequest& v) const override { return owner.actual.measure_text(v); }
        gui::Availability resolved_availability(const gui::WidgetKey& v) const override { return owner.actual.resolved_availability(v); }
        std::optional<gui::WidgetKey> focused() const override { return owner.actual.focused(); }
        bool focus(std::optional<gui::WidgetKey> v) override { return owner.actual.focus(std::move(v)); }
        bool focus_next(bool reverse) override { return owner.actual.focus_next(reverse); }
        void scroll(const gui::WidgetKey& v, gui::Point p) override { owner.actual.scroll(v,p); }
        gui::Point scroll_offset(const gui::WidgetKey& v) const override { return owner.actual.scroll_offset(v); }
        gui::TextSelection text_selection(const gui::WidgetKey& v) const override { return owner.actual.text_selection(v); }
        void text_selection(const gui::WidgetKey& v, gui::TextSelection s) override { owner.actual.text_selection(v,s); }
        bool open_popup(const gui::WidgetKey& v) override { return owner.actual.open_popup(v); }
        void close_popup(const gui::WidgetKey& v) override { owner.actual.close_popup(v); }
        void invalidate(const gui::WidgetKey& v, gui::PixelRect r) override { owner.actual.invalidate(v,r); }
        bool closed() const override { return owner.stopped || owner.actual.closed(); }
        void close() override { owner.stop(); }
    };
    gui::Adapter& actual;
    const std::uint64_t generation;
    const std::thread::id owner_thread{std::this_thread::get_id()};
    DocumentViewport viewport;
    Proxy proxy;
    AppendedDocumentController document;
    gui::Snapshot base, committed;
    std::optional<DocumentProjection> projection;
    std::optional<NativeFormsDocumentObservation> joined;
    std::optional<DocumentViewport> queued_viewport;
    std::map<std::string,F::FormControl> bindings;
    std::optional<Publication> pending;
    std::optional<Origin> local_plan;
    std::unique_ptr<EngineDocumentDraftSession> draft;
    std::optional<SingleChoice> single_choice;
    std::optional<ChooseSingleDocumentOption> choose;
    std::optional<ActivateDocumentControl> activate_control;
    std::optional<F::FormUpdate> recovery_update;
    std::optional<F::FormUpdate> native_observation;
    std::optional<F::BeginFormControl> begin;
    std::optional<F::FinishFormControl> finish;
    std::optional<DocumentFormsRequest> outstanding;
    std::optional<DocumentFormsAction> prepared;
    std::optional<DocumentRequestToken> retired_document;
    std::optional<DocumentFormsRequestToken> accepted_query;
    RequestSequenceSource sequence_source;
    std::optional<Origin> request_origin;
    std::optional<std::string> cursor;
    std::optional<gui::WidgetKey> old_focus;
    std::uint64_t global_revision{0}, local_revision{0}, input_epoch{1}, request_sequence{0}, modal_generation{0};
    std::uint64_t target{0};
    std::optional<F::FormKind> modal_kind;
    gui::Size cell{8,16};
    bool stopped{false}, handling{false}, ticking{false}, publishing{false}, sequencing{false}, foreground{true};
    bool modal{false}, closing{false}, paused{false}, refresh_due{false}, refresh_pending{false}, delivered{false}, request_visible{false};
    bool base_ack{false}, authority_lost{false}, redacted{false}, awaiting_observation{false}, refresh_begin{false}, scene_dirty{false};
    bool sequence_wait_visible{false}, observation_requested{false}, observation_scheduled{false}, actions_available{false};
    std::string error;

    Impl(gui::Adapter& value, std::uint64_t instance, DocumentViewport size, RequestSequenceSource source)
        : actual(value), generation(instance), viewport(size), proxy(*this), document(proxy,instance,size), sequence_source(std::move(source)) {}
    void owner() const {
        if (owner_thread != std::this_thread::get_id()) throw std::logic_error("Forms compositor requires its serialized owner");
    }
    bool quiet() const { return !handling && !ticking && !publishing && !sequencing; }
    bool draft_debt() const { return draft && draft->view().publication_pending; }
    bool recovering() const noexcept { return draft && draft->recovery_pending(); }
    const F::FormDraftView& saved_draft(const F::FormDraftView& fallback) const noexcept {
        const auto* saved=draft ? draft->recovery_saved() : nullptr;
        return saved ? *saved : fallback;
    }
    void advance(std::uint64_t& value) {
        if (value == std::numeric_limits<std::uint64_t>::max()) { stop(); throw std::overflow_error("Forms identity exhausted"); }
        ++value;
    }
    void stop() noexcept {
        stopped = true; base_ack = false; begin.reset(); finish.reset(); choose.reset(); activate_control.reset(); prepared.reset(); retired_document.reset(); accepted_query.reset();
        observation_requested=false; observation_scheduled=false;
        if (draft) draft->close();
        document.shutdown();
    }
    gui::WidgetKey key(std::string_view suffix) const {
        return {"appended/forms/" + std::to_string(generation) + "/" + std::string(suffix), modal_generation};
    }
    bool body_ready() const {
        return !stopped && foreground && !modal && !refresh_due && !authority_lost && !outstanding && !prepared && !activate_control && !retired_document && !pending && !local_plan && !draft_debt() && !queued_viewport && !scene_dirty &&
            base_ack && joined && document.synchronized() && !document.presentation_pending();
    }
    void metrics() {
        const auto m = actual.measure_text({"M",{},gui::coordinate_limit,1,gui::TextWrap::none});
        if (!std::isfinite(m.width) || !std::isfinite(m.height) || m.width <= 0 || m.height <= 0 || m.width > 4096 || m.height > 4096)
            throw std::invalid_argument("Invalid compositor cell measurement");
        cell = m;
    }
    std::string summary(const F::FormControl& c) const {
        if (concealed(c)) return "[control unavailable]";
        if (input_button(c)) return (actions_available ? "[button] " : "[document-actions-v1 required] ") +
            (c.label.empty() ? c.native_type : c.label);
        if (c.kind==F::FormKind::select_one && single_select(c))
            return actions_available ? "[choose] " + c.label : "[document-actions-v1 required] " + c.label;
        if (!editable(c)) {
            std::string result = "[control: read only] " + c.label;
            if (const auto* text = std::get_if<F::FormTextState>(&c.state); text && !text->value.empty())
                result += ": " + text->value;
            return result;
        }
        std::string result = "[edit] " + c.label;
        if (const auto* text = std::get_if<F::FormTextState>(&c.state)) result += ": " + text->editing_text;
        if (const auto* check = std::get_if<F::FormCheckState>(&c.state)) result += check->checked ? " [x]" : " [ ]";
        return result;
    }
    gui::Widget widget(std::string_view id, gui::Kind kind, gui::Rect bounds, std::string label = {}) const {
        gui::Widget result;
        result.spec.key = key(id); result.spec.kind = kind;
        result.spec.parent = kind == gui::Kind::group ? "" : key("modal").id;
        result.state.bounds = bounds; result.state.label = std::move(label);
        return result;
    }
    gui::Snapshot scene(const F::FormDraftView* supplied = nullptr) const {
        auto result = base;
        if (result.client_size.width <= 0 || result.client_size.height <= 0)
            result.client_size = {double(viewport.columns)*cell.width,double(viewport.drawable_rows)*cell.height};
        result.title = error.empty() ? actions_available ? "Appended document" :
            "Appended document: document-actions-v1 capability unavailable" : error;
        const bool cover = modal || refresh_due || authority_lost;
        if (cover) {
            // Do not export old native buffers even in invisible background
            // widgets. Keep immutable keys/specs and only nontext geometry.
            for (auto& w : result.widgets) {
                const auto bounds = w.state.bounds; const auto extent = w.state.content_size;
                w.state = {}; w.state.bounds = bounds; w.state.content_size = extent;
                w.state.visible = false; w.state.enabled = false;
            }
            result.commands.clear(); result.key_bindings.clear();
        } else {
            for (auto& w : result.widgets) if (w.spec.kind == gui::Kind::list) {
                if (cursor) w.state.selected = cursor;
                for (auto& row : w.state.records) if (const auto f = bindings.find(row.id); f != bindings.end()) {
                    const auto value = summary(f->second);
                    row.accessible_text = value; row.activatable = (editable(f->second) || (actions_available && single_select(f->second))) && viewport.columns>=8 && viewport.drawable_rows>=5;
                    if (actions_available && input_button(f->second)) row.activatable=true;
                    for (auto& c : row.cells) c.text = value;
                }
                if (!foreground || outstanding || prepared || activate_control || retired_document) w.state.enabled = false;
            }
        }
        if (!cover) return result;
        const auto width = result.client_size.width, height = result.client_size.height;
        if (width < cell.width*8 || height < cell.height*5) {
            result.modal_root.reset();
            auto notice = widget("small",gui::Kind::label,{0,0,width,height},"Form viewport is too small");
            notice.spec.parent.clear(); result.widgets.push_back(std::move(notice)); return result;
        }
        auto root = widget("modal",gui::Kind::group,{0,0,width,height});
        result.modal_root = root.spec.key; result.widgets.push_back(std::move(root));
        if (single_choice) {
            const bool enabled=foreground && actions_available && !authority_lost && !refresh_due && !closing && !choose && !prepared && !outstanding;
            const auto status=closing ? "Waiting for current document" : authority_lost ?
                "Document changed; cancel and refresh before choosing again" : "Choose an option; Apply commits the choice";
            result.widgets.push_back(widget("status",gui::Kind::label,{cell.width,0,width-cell.width,cell.height},status));
            auto options=widget("single-options",gui::Kind::choice,{cell.width,cell.height,width-2*cell.width,cell.height},single_choice->control.label);
            if (!authority_lost) for (const auto& option:std::get<F::FormSelectState>(single_choice->control.state).options) {
                options.state.options.push_back({std::to_string(option.node),option.label,"",!option.disabled&&!option.omitted});
                if (single_choice->selected==option.node) options.state.selected=std::to_string(option.node);
            }
            options.state.enabled=enabled;
            result.widgets.push_back(std::move(options));
            auto apply=widget("apply",gui::Kind::button,{cell.width,height-2*cell.height,(width-2*cell.width)/2,cell.height},"Apply");
            apply.state.enabled=enabled && single_choice->selected.has_value();
            result.widgets.push_back(std::move(apply));
            auto cancel=widget("cancel",gui::Kind::button,{width/2,height-2*cell.height,(width-2*cell.width)/2,cell.height},"Cancel");
            cancel.state.enabled=!closing && !outstanding && !prepared;
            result.widgets.push_back(std::move(cancel));
            result.key_bindings.push_back({gui::ShortcutKey::escape,key("cancel"),false,false,false,{}});
            result.key_bindings.push_back({gui::ShortcutKey::enter,key("apply"),true,false,false,{}});
            return result;
        }
        const auto* value = supplied ? supplied : draft ? &draft->view() : nullptr;
        const bool secret = redacted || awaiting_observation || (value && value->latest && concealed(value->latest->control));
        const bool native_busy = (outstanding && !std::holds_alternative<DocumentEngineRequest>(outstanding->action)) ||
            (prepared && !std::holds_alternative<DocumentEngineRequest>(*prepared));
        const bool safe_recovery = !awaiting_observation && recovery_update && !concealed(recovery_update->control);
        const std::string status = safe_recovery ? "Native state refreshed; reload or reapply the saved draft" : secret ? "Control unavailable" : closing ? "Closing form" :
            authority_lost ? "Refresh native state before recovering the draft" :
            !value ? "Opening form" : value->phase == F::FormDraftPhase::stale ? "Native state changed; draft retained" :
            value->phase == F::FormDraftPhase::unknown ? "Outcome unknown; draft retained" : "Unsaved draft";
        result.widgets.push_back(widget("status",gui::Kind::label,{cell.width,0,width-cell.width,cell.height},status));
        if (value) {
            const auto& control = value->base.control;
            if (std::holds_alternative<F::FormTextState>(control.state)) {
                auto editor = widget("editor",gui::Kind::text,{cell.width,cell.height,width-2*cell.width,std::max(cell.height,height-4*cell.height)});
                editor.spec.text_policy.multiline = control.kind == F::FormKind::textarea;
                editor.spec.text_policy.max_bytes = 8192;
                editor.spec.text_policy.submit = gui::SubmitKey::control_enter;
                editor.state.text = secret ? "" : value->text;
                editor.state.enabled = !secret && !closing && !authority_lost && !native_busy && !value->apply_queued && value->phase == F::FormDraftPhase::editing;
                result.widgets.push_back(std::move(editor));
                // Retain this immutable widget even when hidden: repeated
                // conflict/reload cycles must not resurrect a retired key.
                auto native = widget("native",gui::Kind::text,{cell.width,height-3*cell.height,width-2*cell.width,cell.height},"Current native value");
                native.spec.text_policy.read_only=true;
                native.spec.text_policy.multiline=control.kind==F::FormKind::textarea;
                const auto* latest = safe_recovery ? &recovery_update->control : native_observation ? &native_observation->control :
                    value->latest && !concealed(value->latest->control) ? &value->latest->control : nullptr;
                const auto* native_text = latest ? std::get_if<F::FormTextState>(&latest->state) : nullptr;
                native.state.visible=native_text && (!secret || safe_recovery);
                native.state.enabled=native.state.visible;
                if (native.state.visible) native.state.text=native_text->editing_text;
                result.widgets.push_back(std::move(native));
            } else if (std::holds_alternative<F::FormCheckState>(control.state)) {
                auto toggle = widget("check",gui::Kind::toggle,{cell.width,cell.height,width-2*cell.width,cell.height},"Checked");
                toggle.state.checked = !secret && value->checked;
                toggle.state.enabled = !secret && !closing && !authority_lost && !native_busy && value->phase == F::FormDraftPhase::editing;
                result.widgets.push_back(std::move(toggle));
            } else if (const auto* select = std::get_if<F::FormSelectState>(&control.state)) {
                auto options = widget("options",gui::Kind::choice,{cell.width,cell.height,width-2*cell.width,cell.height},"Option");
                if (!secret) for (const auto& option : select->options) {
                    options.state.options.push_back({std::to_string(option.node),option.label,"",!option.disabled&&!option.omitted});
                    if (selected_option && *selected_option==option.node) options.state.selected = std::to_string(option.node);
                    else if (!selected_option && !options.state.selected && !option.disabled && !option.omitted) options.state.selected = std::to_string(option.node);
                }
                // Phase one submits one option per Apply. Keep that visible
                // option fixed while dirty so another selection cannot conceal
                // which native option the pending draft will change.
                options.state.enabled = !secret && !closing && !authority_lost && !native_busy && !value->dirty && value->phase == F::FormDraftPhase::editing;
                result.widgets.push_back(std::move(options));
                auto check = widget("check",gui::Kind::toggle,{cell.width,2*cell.height,width-2*cell.width,cell.height},"Selected");
                if (!secret && selected_option) {
                    const auto found = std::find_if(select->options.begin(),select->options.end(),[&](const auto& o){return o.node==*selected_option;});
                    if (found != select->options.end()) check.state.checked = value->option && value->option->node == found->node ? value->option->selected : found->selected;
                }
                check.state.enabled = options_enabled(value,secret);
                result.widgets.push_back(std::move(check));
            }
        }
        const std::pair<const char*,const char*> buttons[] = {{"apply","Apply"},{"cancel","Cancel"},{"reload","Reload"},{"reapply","Reapply"},{"refresh","Refresh native"}};
        const double button_width = (width-2*cell.width)/5;
        for (std::size_t i=0;i<5;++i) {
            auto button = widget(buttons[i].first,gui::Kind::button,{cell.width+i*button_width,height-2*cell.height,button_width,cell.height},buttons[i].second);
            button.state.enabled = !closing;
            if (i==0) button.state.enabled = value && !secret && !authority_lost && !refresh_due && !outstanding && !prepared && !value->apply_queued && value->phase==F::FormDraftPhase::editing && value->dirty;
            if (i==2 || i==3) button.state.enabled = value && (!secret || safe_recovery) && !outstanding && !prepared &&
                ((recovery_update && recovery_update->control.lease) || (!authority_lost && value->latest && value->latest->control.lease));
            if (i==3 && button.state.enabled && recovery_update) {
                const auto& saved=saved_draft(*value);
                button.state.enabled=saved.base.control.kind==recovery_update->control.kind &&
                    saved.base.control.native_type==recovery_update->control.native_type;
            }
            if (i==4) button.state.enabled = value && !outstanding && !prepared && !refresh_due && joined.has_value();
            result.widgets.push_back(std::move(button));
        }
        result.key_bindings.push_back({gui::ShortcutKey::escape,key("cancel"),false,false,false,{}});
        result.key_bindings.push_back({gui::ShortcutKey::enter,key("apply"),true,false,false,{}});
        return result;
    }
    std::optional<std::uint64_t> selected_option;
    bool options_enabled(const F::FormDraftView* value,bool secret) const {
        return !secret && !closing && !authority_lost && (!outstanding || std::holds_alternative<DocumentEngineRequest>(outstanding->action)) &&
            (!prepared || std::holds_alternative<DocumentEngineRequest>(*prepared)) &&
            value->phase == F::FormDraftPhase::editing && selected_option.has_value();
    }
    void send(Publication value) {
        if (pending) {
            if (pending->origin != value.origin) throw std::logic_error("A different combined publication needs exact retry");
        } else {
            advance(global_revision); value.view.revision = global_revision;
            gui::validate_snapshot(value.view); pending = std::move(value);
        }
        auto commit = pending->view; // reserve before adapter/native callbacks
        Guard guard(publishing);
        actual.present(pending->view);
        if (stopped || actual.closed()) { if (!stopped) stop(); return; }
        if (request_origin && *request_origin==pending->origin) request_visible=true;
        committed = std::move(commit); pending.reset();
    }
    void local() {
        if (local_plan) throw std::logic_error("Local publication needs exact retry");
        advance(local_revision);
        local_plan=Origin{OriginKind::local,modal_generation,local_revision};
        send({scene(),*local_plan});
        local_plan.reset();
    }
    void conceal_unobserved_control() {
        awaiting_observation=true;
        if (!modal || !draft) return;
        if (pending || local_plan || draft_debt()) { scene_dirty=true; return; }
        try { local(); }
        catch (...) { if (!pending && !local_plan && !draft_debt()) throw; }
    }
    void draft_publish(const F::FormDraftView& value) {
        if (pending && pending->origin.kind != OriginKind::draft) throw std::logic_error("Base publication is pending");
        if (modal_kind && *modal_kind!=value.base.control.kind) advance(modal_generation);
        modal_kind=value.base.control.kind;
        send({scene(&value),{OriginKind::draft,modal_generation,value.revision}});
    }
    void base_present(gui::Snapshot value) {
        if (!ticking) throw std::logic_error("Document presentation escaped compositor tick");
        if (pending && pending->origin.kind != OriginKind::base) throw std::logic_error("Modal publication is pending");
        const auto* candidate = document.candidate_projection();
        projection = candidate ? std::optional<DocumentProjection>(*candidate) : std::nullopt;
        bindings.clear();
        if (projection && joined && form_version(projection->version) == joined->publication) {
            for (const auto& row : projection->rows) if (row.node) {
                const auto found = std::find_if(joined->forms.controls.begin(),joined->forms.controls.end(),[&](const auto& c){return c.node==*row.node;});
                const auto body_node=std::find_if(joined->body.snapshot->nodes.begin(),joined->body.snapshot->nodes.end(),[&](const auto& n){return n.id==*row.node;});
                if (found != joined->forms.controls.end() && body_node!=joined->body.snapshot->nodes.end() &&
                    !body_node->masked && !body_node->omitted && !found->omitted &&
                    (!input_button(*found) || body_node->tag=="input")) bindings.emplace(row.id,*found);
            }
        }
        base = std::move(value); base_ack = false;
        send({scene(),{OriginKind::base,0,base.revision}});
    }
    void ack() {
        base_ack = !pending && !document.presentation_pending() && document.synchronized() && joined && projection &&
            form_version(projection->version) == joined->publication && base.revision == document.view().revision;
        if (base_ack && !modal && foreground && old_focus && !actual.focused()) {
            if (gui::find_widget(committed,*old_focus)) (void)actual.focus(old_focus);
            old_focus.reset();
        }
    }
    void poll_selection() {
        if (!draft || redacted || awaiting_observation || authority_lost || pending || !modal || closing) return;
        const auto* w = gui::find_widget(committed,key("editor"));
        if (w && w->state.visible && draft->view().phase==F::FormDraftPhase::editing) {
            const auto s = actual.text_selection(w->spec.key);
            (void)draft->selection({s.anchor,s.caret});
        }
    }
    bool query_waiting() const {
        const auto query=[](const DocumentFormsAction& action) {
            const auto* value=std::get_if<DocumentEngineRequest>(&action);
            return value && !value->intent;
        };
        return (prepared && query(*prepared)) || (outstanding && query(outstanding->action));
    }
    void request_observation() {
        owner();
        if (stopped || observation_scheduled || refresh_pending || query_waiting()) return;
        // A retired/rejected mandatory query may leave the native-effect
        // refresh barrier active. An explicit readonly hint retries that same
        // required capture; it never starts polling a healthy modal lease.
        if (refresh_due) refresh_pending=true;
        else observation_requested=true;
    }
    void tick() {
        owner(); if (!quiet() || pending || local_plan || draft_debt() || (outstanding&&!delivered&&!request_visible) || stopped) return;
        if (retired_document) {
            // Lifecycle changes can arrive from the controller's measurement
            // callback. Retire its unhanded request only after that call unwinds.
            (void)document.fail_request(*retired_document,DocumentRequestFailure::known_rejected);
            retired_document.reset();
        }
        Guard guard(ticking);
        if (actual.closed()) { stop(); return; }
        if (scene_dirty) {
            scene_dirty=false;
            local();
            if (scene_dirty || stopped || pending || local_plan) return;
        }
        if (queued_viewport) {
            viewport=*queued_viewport;
            if (modal || authority_lost || refresh_due) advance(modal_generation);
            document.viewport(viewport); queued_viewport.reset();
        }
        metrics(); poll_selection();
        continue_recovery();
        if (pending || local_plan || draft_debt() || stopped) return;
        if (refresh_pending) {
            document.request_snapshot(); refresh_pending=false;
            observation_requested=false; observation_scheduled=true;
        } else if (observation_requested && foreground && !modal && !closing && !outstanding && !prepared && !activate_control && !begin && !finish && !recovering()) {
            // Ordinary polling does not enter the native-effect refresh barrier
            // or revoke a draft/lease. Queued controller actions retain priority.
            document.request_snapshot(); observation_requested=false; observation_scheduled=true;
        }
        document.tick(); ack();
    }
    void request_refresh() {
        if (!modal && !refresh_due && !authority_lost) advance(modal_generation);
        refresh_due = true; base_ack = false;
        // Lifecycle changes can arrive from actual.present/measure_text. The
        // controller itself is entered only after those callbacks have left.
        refresh_pending = true;
    }
    void retire_prepared(const char* message) {
        if (!prepared) return;
        if (const auto* request=std::get_if<DocumentEngineRequest>(&*prepared)) {
            retired_document=request->token;
            observation_scheduled=false;
        }
        prepared.reset(); sequence_wait_visible=false; error=message;
    }
    void cancel() {
        if (!modal) return;
        retire_prepared("Undelivered input retired after Cancel");
        if (single_choice) {
            if (outstanding) return;
            const auto expected=single_choice->expected;
            choose.reset();
            single_choice.reset(); modal=false; closing=false;
            if (foreground && !authority_lost && !refresh_due && document.resume_input(expected)) {
                paused=false; ack();
            } else request_refresh();
            local();
            return;
        }
        if (draft) draft->cancel_recovery();
        closing = true;
        if (draft) {
            const auto& v = draft->view();
            if (!outstanding && v.phase == F::FormDraftPhase::editing && v.base.control.lease &&
                F::form_has(v.base.control.capabilities,F::FormCapability::finish)) finish = F::FinishFormControl{*v.base.control.lease};
            (void)draft->handle(F::CancelFormDraft{});
        } else local();
        begin.reset();
        if (!outstanding && !finish) request_refresh();
    }
    void handle(gui::Event event) {
        owner();
        if (std::holds_alternative<gui::CloseEvent>(event)) { stop(); return; }
        if (stopped || handling || ticking || publishing || sequencing || pending || local_plan || draft_debt() || scene_dirty || document.presentation_pending() || !foreground) return;
        Guard guard(handling);
        if (!gui::normalize_event(committed,event,[&](const auto& k){return actual.scroll_offset(k);})) return;
        const auto* w = std::get_if<gui::WidgetEvent>(&event);
        if (!w) return;
        try {
            if (modal) {
                if (w->target == key("cancel")) { cancel(); return; }
                if (single_choice) {
                    if (!actions_available || closing || authority_lost || refresh_due || choose || prepared || outstanding) return;
                    if (const auto* selected=std::get_if<gui::ChooseOption>(&w->input); selected && w->target==key("single-options")) {
                        const auto& options=std::get<F::FormSelectState>(single_choice->control.state).options;
                        const auto found=std::find_if(options.begin(),options.end(),[&](const auto& option){return std::to_string(option.node)==selected->id;});
                        if (found!=options.end() && !found->disabled && !found->omitted) { single_choice->selected=found->node; local(); }
                    } else if (w->target==key("apply") && single_choice->selected) {
                        choose=ChooseSingleDocumentOption{single_choice->expected,single_choice->control.node,*single_choice->selected};
                        closing=true; local();
                    }
                    return;
                }
                if (!draft || closing || (outstanding && !std::holds_alternative<DocumentEngineRequest>(outstanding->action)) ||
                    (prepared && !std::holds_alternative<DocumentEngineRequest>(*prepared))) return;
                if (const auto* e = std::get_if<gui::EditText>(&w->input); e && w->target == key("editor"))
                    (void)draft->handle(F::EditFormDraft{e->base_text,e->value});
                else if (const auto* e = std::get_if<gui::SetChecked>(&w->input); e && w->target == key("check")) {
                    if (draft->view().base.control.kind == F::FormKind::checkbox) (void)draft->handle(F::CheckFormDraft{e->value});
                    else if (selected_option) (void)draft->handle(F::OptionFormDraft{*selected_option,e->value});
                } else if (const auto* e = std::get_if<gui::ChooseOption>(&w->input); e && w->target == key("options")) {
                    const auto& options = std::get<F::FormSelectState>(draft->view().base.control.state).options;
                    const auto found = std::find_if(options.begin(),options.end(),[&](const auto& o){return std::to_string(o.node)==e->id;});
                    if (found != options.end()) { selected_option=found->node; local(); }
                } else if (w->target == key("apply") || (w->target == key("editor") && std::holds_alternative<gui::SubmitText>(w->input))) {
                    if (!authority_lost && !refresh_due) (void)draft->handle(F::ApplyFormDraft{});
                } else if ((w->target == key("reload") || w->target == key("reapply")) && recovery_update) {
                    const bool reapply=w->target==key("reapply");
                    const auto& saved=saved_draft(draft->view());
                    if (reapply && (saved.base.control.kind!=recovery_update->control.kind || saved.base.control.native_type!=recovery_update->control.native_type)) return;
                    if (!draft->recover(saved,*recovery_update,reapply)) return;
                    authority_lost=false;
                    continue_recovery();
                } else if (w->target == key("reload")) (void)draft->handle(F::ReloadFormDraft{});
                else if (w->target == key("reapply")) (void)draft->handle(F::ReapplyFormDraft{});
                else if (w->target == key("refresh") && joined && !refresh_due) {
                    begin = F::BeginFormControl{joined->publication,target}; refresh_begin = true; local();
                }
                return;
            }
            if (!body_ready()) return;
            if (const auto* select = std::get_if<gui::SelectRecord>(&w->input)) {
                cursor=select->id;
                if (!bindings.contains(select->id)) document.handle(event);
                local();
            } else if (const auto* activate = std::get_if<gui::ActivateRecord>(&w->input)) {
                if (const auto found=bindings.find(activate->id); found!=bindings.end()) {
                    if (actions_available && input_button(found->second)) {
                        if (!document.suspend_input()) { error="Navigation is pending; activate the button again after it completes"; local(); return; }
                        paused=true; activate_control=ActivateDocumentControl{projection->version,found->second.node};
                        advance(input_epoch); local(); return;
                    }
                    const bool chooser=actions_available && single_select(found->second);
                    if (!editable(found->second) && !chooser) return;
                    if (!document.suspend_input()) { error="Navigation is pending; activate the form again after it completes"; local(); return; }
                    advance(input_epoch); advance(modal_generation);
                    old_focus=actual.focused(); target=found->second.node;
                    modal=true; closing=false; paused=true; redacted=false; awaiting_observation=false; authority_lost=false;
                    modal_kind.reset(); recovery_update.reset(); native_observation.reset();
                    if (draft) draft->cancel_recovery();
                    selected_option.reset();
                    if (chooser) {
                        single_choice=SingleChoice{projection->version,found->second,{}};
                        for (const auto& option:std::get<F::FormSelectState>(found->second.state).options)
                            if (!option.disabled && !option.omitted && (option.selected || !single_choice->selected)) {
                                single_choice->selected=option.node;
                                if (option.selected) break;
                            }
                    } else begin=F::BeginFormControl{joined->publication,target};
                    local();
                } else document.handle(event);
            }
        } catch (...) { if (!pending && !local_plan && !draft_debt()) throw; }
    }
    std::optional<DocumentFormsRequest> reserve_prepared() {
        if (!prepared) return {};
        if (request_sequence == std::numeric_limits<std::uint64_t>::max()) {
            stop(); error="Forms request sequence exhausted"; throw std::overflow_error("Forms request exhausted");
        }
        if (local_revision==std::numeric_limits<std::uint64_t>::max()) {
            stop(); error="Forms local publication exhausted"; throw std::overflow_error("Forms local publication exhausted");
        }
        // Both action copies precede the pure reservation. A failed copy leaves
        // the already-drained inner request owned, without burning a sequence.
        DocumentFormsRequest request{{generation,0},*prepared};
        auto returned=request;
        std::optional<std::uint64_t> sequence;
        try {
            Guard guard(sequencing);
            sequence=sequence_source ? sequence_source() : std::optional<std::uint64_t>{request_sequence+1};
        } catch (...) {
            stop(); error="Forms request sequence source failed"; throw;
        }
        if (sequence && (!*sequence || *sequence<=request_sequence)) {
            stop(); error="Forms request sequence did not increase";
            throw std::invalid_argument("Forms request sequence must be nonzero and increase");
        }
        if (sequence) request_sequence=*sequence; // Exact reservation burns even after lifecycle revocation.
        if (stopped || !foreground || !prepared) return {};
        if (!sequence) {
            if (!sequence_wait_visible) {
                sequence_wait_visible=true;
                try { local(); } catch (...) { return {}; }
            }
            return {};
        }
        request.token.sequence=*sequence; returned.token.sequence=*sequence;
        outstanding=std::move(request); prepared.reset(); sequence_wait_visible=false; delivered=false; request_visible=false;
        request_origin=Origin{OriginKind::local,modal_generation,local_revision+1};
        try { local(); } catch (...) { return {}; }
        if (!outstanding || stopped || !foreground || pending) return {};
        delivered=true; return returned;
    }
    std::optional<DocumentFormsRequest> reserve(DocumentFormsAction action) {
        if (prepared) throw std::logic_error("An inner request already awaits a sequence");
        prepared=std::move(action);
        accepted_query.reset();
        return reserve_prepared();
    }
    bool pause() {
        if (paused) return true;
        if (!document.suspend_input()) return false;
        paused=true; return true;
    }
    std::optional<DocumentFormsRequest> next() {
        owner(); if (!quiet() || stopped || pending || local_plan || draft_debt() || !foreground) return {};
        tick(); if (pending || local_plan || draft_debt() || scene_dirty || !foreground || stopped) return {};
        if (outstanding) {
            if (delivered) return {};
            if (!request_visible) {
                try { send({scene(),*request_origin}); } catch (...) { return {}; }
            }
            if (!outstanding || stopped || !foreground || pending) return {};
            auto result=outstanding; delivered=true; return result;
        }
        if (prepared) return reserve_prepared();
        if (activate_control) {
            auto action=*activate_control; auto result=reserve(action);
            if (outstanding || prepared) activate_control.reset();
            return result;
        }
        if (choose) {
            auto action=*choose; auto result=reserve(action);
            if (outstanding || prepared) choose.reset();
            return result;
        }
        if (begin) {
            if (!pause()) return {};
            auto action=*begin; auto result=reserve(action);
            if (outstanding || prepared) begin.reset();
            return result;
        }
        if (finish) {
            auto action=*finish; auto result=reserve(action);
            if (outstanding || prepared) finish.reset();
            return result;
        }
        if (refresh_due || !modal) {
            if (auto request=document.next_request()) return reserve(std::move(*request));
        }
        if (modal && draft && !closing && !authority_lost && !refresh_due) {
            if (recovering()) return {};
            poll_selection();
            if (draft->view().apply_queued && !pause()) return {};
            if (auto request=draft->next_request()) return reserve(std::move(*request));
        }
        return {};
    }
    void prepare_draft_display(const F::FormUpdate& update) {
        redacted=concealed(update.control);
        awaiting_observation=false;
        selected_option.reset();
        if (const auto* select=std::get_if<F::FormSelectState>(&update.control.state))
            for (const auto& o:select->options) if (!o.disabled&&!o.omitted) { selected_option=o.node; break; }
    }
    void focus_installed_draft() {
        if (!pending && !redacted && foreground) {
            if (gui::find_widget(committed,key("editor"))) (void)actual.focus(key("editor"));
            else if (gui::find_widget(committed,key("check"))) (void)actual.focus(key("check"));
            else (void)actual.focus(key("cancel"));
        }
    }
    void install_draft(F::FormUpdate update) {
        if (draft) { advance(modal_generation); modal_kind.reset(); }
        prepare_draft_display(update);
        draft=std::make_unique<EngineDocumentDraftSession>(modal_generation,std::move(update),
            [this](const F::FormDraftView& v){draft_publish(v);});
        focus_installed_draft();
    }
    bool recovery_presentation_clear() const {
        return !pending && !local_plan && !draft_debt() && !scene_dirty &&
            !stopped && foreground && !authority_lost && !closing;
    }
    void continue_recovery() {
        using Progress=EngineDocumentDraftSession::RecoveryProgress;
        if (!recovering() || !recovery_presentation_clear()) return;
        // One checkpoint keeps focus between baseline installation and saved
        // value restoration, with actual publication/lifecycle checks between.
        for (unsigned checkpoint=0; checkpoint<4 && recovering(); ++checkpoint) {
            if (!recovery_presentation_clear()) return;
            const bool installing=draft->recovery_install_pending();
            if (installing) {
                const auto* fresh=draft->recovery_fresh();
                if (!fresh) throw std::logic_error("Draft recovery lost its fresh Begin");
                advance(modal_generation);
                if (!draft->recovery_generation(modal_generation))
                    throw std::logic_error("Draft recovery rejected its fresh local generation");
                modal_kind.reset();
                prepare_draft_display(*fresh);
            }
            const auto progress=draft->advance_recovery(
                [this]{return recovery_presentation_clear();});
            if (installing) {
                if (draft->generation()!=modal_generation)
                    throw std::logic_error("Draft recovery failed its installation checkpoint");
                focus_installed_draft();
            }
            if (progress==Progress::blocked) {
                authority_lost=true;
                error="Saved draft cannot be reapplied to this native state; reload or refresh explicitly";
                local();
                return;
            }
            if (progress==Progress::completed) {
                recovery_update.reset();
                local();
                return;
            }
            if (progress==Progress::idle || !recovery_presentation_clear()) return;
        }
    }
    bool complete(DocumentFormsRequestToken token, DocumentFormsCompletion completion) {
        owner(); if (!quiet() || stopped || pending || local_plan || draft_debt() || scene_dirty || !outstanding || !delivered || outstanding->token!=token) return false;
        const auto receipt_epoch=input_epoch;
        auto request=std::move(*outstanding); outstanding.reset(); delivered=false; request_origin.reset(); request_visible=false;
        if (std::holds_alternative<DocumentEngineRequest>(request.action)) { observation_scheduled=false; accepted_query.reset(); }
        try {
            const auto* body_request=std::get_if<DocumentEngineRequest>(&request.action);
            const auto* choice_request=std::get_if<ChooseSingleDocumentOption>(&request.action);
            const auto* control_request=std::get_if<ActivateDocumentControl>(&request.action);
            if ((body_request && body_request->intent) || choice_request || control_request) {
                auto* value=std::get_if<DocumentBodyCompletion>(&completion);
                if (!value) throw std::invalid_argument("Wrong body action completion kind");
                if (value->outcome!=DocumentBodyOutcome::completed && value->outcome!=DocumentBodyOutcome::needs_current_observation &&
                    value->outcome!=DocumentBodyOutcome::rejected && value->outcome!=DocumentBodyOutcome::indeterminate)
                    throw std::invalid_argument("Unknown body action outcome");
                if ((value->outcome==DocumentBodyOutcome::completed && !value->publication) ||
                    (value->outcome==DocumentBodyOutcome::needs_current_observation && value->publication))
                    throw std::invalid_argument("Body action outcome lacks its required observation boundary");
                const auto expected=body_request ? body_request->intent->version : choice_request ? choice_request->expected : control_request->expected;
                if (value->publication) {
                    auto& publication=*value->publication;
                    validate_join(publication,generation);
                    if (publication.body.request_id || !same_document(publication.publication,form_version(expected)) ||
                        publication.publication.revision<expected.revision)
                        throw std::invalid_argument("Wrong body action publication identity");
                    if (joined && publication.publication==joined->publication && publication.forms.controls!=joined->forms.controls)
                        throw std::invalid_argument("Native forms publication reused with different values");
                    if (body_request) {
                        // A native action record has no query/controller request
                        // ID. Bind only this exact outstanding action receipt.
                        publication.body.request_id=body_request->token.id;
                        if (!document.complete_request(body_request->token,std::move(publication.body)) || !document.synchronized())
                            throw std::invalid_argument("Rejected body action publication");
                        publication.body=*document.observation();
                    }
                    joined=std::move(publication); cursor.reset();
                } else if (body_request && !document.consume_request_without_publication(body_request->token))
                    throw std::invalid_argument("Body action token is no longer outstanding");
                if (choice_request) { single_choice.reset(); modal=false; closing=false; }
                if (value->outcome==DocumentBodyOutcome::rejected) error="Native document action rejected; refreshing current document";
                else if (value->outcome==DocumentBodyOutcome::indeterminate) error="Native document action outcome indeterminate; refreshing current document";
                else error.clear();
                accepted_query.reset();
                advance(input_epoch); request_refresh();
            } else if (const auto* base_request=std::get_if<DocumentEngineRequest>(&request.action)) {
                auto* value=std::get_if<NativeFormsDocumentObservation>(&completion);
                if (!value) throw std::invalid_argument("Wrong document completion kind");
                validate_join(*value,generation);
                if (modal && draft && std::none_of(value->forms.controls.begin(),value->forms.controls.end(),[&](const auto& c){return c.node==target;}) &&
                    !body_hidden(*value->body.snapshot,target))
                    throw std::invalid_argument("Missing native control remains visible in body");
                if (joined && value->publication==joined->publication && value->forms.controls!=joined->forms.controls)
                    throw std::invalid_argument("Native forms publication reused with different values");
                if (modal && native_observation && same_document(value->publication,native_observation->version)) {
                    if (value->publication.revision<native_observation->version.revision)
                        throw std::invalid_argument("Paired snapshot predates native control readback");
                    if (value->publication==native_observation->version) {
                        const auto current=std::find_if(value->forms.controls.begin(),value->forms.controls.end(),[&](const auto& c){return c.node==target;});
                        if (current==value->forms.controls.end() || !F::form_control_state_matches(*current,native_observation->control))
                            throw std::invalid_argument("Paired snapshot conflicts with native control readback");
                    }
                }
                const auto prior=joined ? std::optional<F::FormVersion>(joined->publication) : std::nullopt;
                if (!document.complete_request(base_request->token,std::move(value->body)) || !document.synchronized())
                    throw std::invalid_argument("Rejected joined document completion");
                value->body=*document.observation(); joined=std::move(*value); refresh_due=false; paused=false; error.clear();
                if (!modal) { authority_lost=false; redacted=false; awaiting_observation=false; }
                if (!prior || *prior!=joined->publication) cursor.reset();
                if (modal && draft && !closing) {
                    const auto c=std::find_if(joined->forms.controls.begin(),joined->forms.controls.end(),[&](const auto& x){return x.node==target;});
                    if (c==joined->forms.controls.end()) {
                        redacted=true; authority_lost=true; recovery_update.reset(); native_observation.reset();
                        draft->close(); local();
                    }
                    else {
                        redacted=redacted||concealed(*c);
                        if (recovery_update && !F::form_control_state_matches(recovery_update->control,*c)) recovery_update.reset();
                        native_observation=F::FormUpdate{joined->publication,*c};
                        const auto& prior_control=draft->view().base.control;
                        if (awaiting_observation && editable(*c)) {
                            if (!same_document(joined->publication,draft->view().base.version) ||
                                c->kind!=prior_control.kind || c->native_type!=prior_control.native_type)
                                redacted=true; // Only explicit Reload may adopt this new safe kind.
                            awaiting_observation=false;
                        }
                        (void)draft->observe({joined->publication,*c});
                    }
                }
                if (closing) {
                    modal=false; closing=false; draft.reset(); single_choice.reset(); authority_lost=false; redacted=false; awaiting_observation=false;
                }
                if (!base_request->intent && !stopped && input_epoch==receipt_epoch) accepted_query=token;
            } else {
                auto* value=std::get_if<DocumentFormsControlReply>(&completion);
                if (!value) throw std::invalid_argument("Wrong form completion kind");
                if (value->outcome!=F::FormDraftOutcome::accepted && value->outcome!=F::FormDraftOutcome::rejected &&
                    value->outcome!=F::FormDraftOutcome::unknown)
                    throw std::invalid_argument("Unknown native form outcome");
                if (!value->update && modal && draft) {
                    // No-effects rejection still says nothing about the current
                    // native kind. Retain the draft privately until a paired
                    // observation proves this same control safe to display.
                    awaiting_observation=true;
                }
                if (value->update) {
                    validate_update(*value->update);
                    if (!joined || !same_document(value->update->version,joined->publication) || value->update->control.node!=target)
                        throw std::invalid_argument("Wrong native control identity");
                    if (value->update->version.revision<joined->publication.revision)
                        throw std::invalid_argument("Stale native control readback");
                    if (value->update->version==joined->publication) {
                        const auto current=std::find_if(joined->forms.controls.begin(),joined->forms.controls.end(),[&](const auto& c){return c.node==target;});
                        if (current==joined->forms.controls.end() || !F::form_control_state_matches(*current,value->update->control))
                            throw std::invalid_argument("Native control readback conflicts with paired publication");
                    }
                    if (native_observation && same_document(value->update->version,native_observation->version) &&
                        (value->update->version.revision<native_observation->version.revision ||
                         (value->update->version==native_observation->version && !F::form_control_state_matches(value->update->control,native_observation->control))))
                        throw std::invalid_argument("Native control readback conflicts with previous observation");
                    redacted=redacted||concealed(value->update->control);
                    native_observation=*value->update;
                }
                if (std::holds_alternative<F::BeginFormControl>(request.action)) {
                    if (value->outcome==F::FormDraftOutcome::accepted && value->update && value->update->control.lease) {
                        if (refresh_begin && draft) { recovery_update=*value->update; authority_lost=true; local(); }
                        else if (!closing) install_draft(*value->update);
                        if (!recovery_update) authority_lost=false;
                    } else { error="Native form entry rejected"; if (!draft) closing=true; }
                    refresh_begin=false;
                } else if (const auto* action=std::get_if<F::FormDraftRequest>(&request.action)) {
                    if (draft && !closing) {
                        (void)draft->complete(action->token,value->outcome,std::move(value->update));
                        if (!pending && foreground && !authority_lost && !redacted) {
                            if (const auto* editor=gui::find_widget(committed,key("editor")); editor && editor->state.enabled)
                                (void)actual.focus(editor->spec.key);
                        }
                    }
                }
                request_refresh();
                if (awaiting_observation) conceal_unobserved_control();
            }
        } catch (const std::exception&) {
            error="Malformed or unknown native forms completion";
            if (modal && draft && !std::holds_alternative<DocumentEngineRequest>(request.action)) awaiting_observation=true;
            if (const auto* action=std::get_if<DocumentEngineRequest>(&request.action)) {
                (void)document.fail_request(action->token,DocumentRequestFailure::unknown);
                if (action->intent) request_refresh();
            } else {
                if (const auto* action=std::get_if<F::FormDraftRequest>(&request.action); action && draft && !closing)
                    (void)draft->complete(action->token,F::FormDraftOutcome::unknown);
                request_refresh();
            }
            if (std::holds_alternative<ChooseSingleDocumentOption>(request.action)) {
                single_choice.reset(); modal=false; closing=false;
            }
            if (awaiting_observation) conceal_unobserved_control();
            base_ack=false;
        }
        return true;
    }
};

AppendedDocumentForms::AppendedDocumentForms(gui::Adapter& actual,std::uint64_t generation,DocumentViewport viewport)
    : AppendedDocumentForms(actual,generation,viewport,{}) {}
AppendedDocumentForms::AppendedDocumentForms(gui::Adapter& actual,std::uint64_t generation,DocumentViewport viewport,RequestSequenceSource source)
    : impl_(std::make_unique<Impl>(actual,generation,viewport,std::move(source))) {}
AppendedDocumentForms::~AppendedDocumentForms() { shutdown(); }
void AppendedDocumentForms::handle(gui::Event e) { impl_->handle(std::move(e)); }
void AppendedDocumentForms::tick() { impl_->tick(); }
void AppendedDocumentForms::retry_presentation() {
    impl_->owner(); if (!impl_->quiet() || impl_->stopped) return;
    if (!impl_->pending) {
        if (impl_->local_plan) { impl_->send({impl_->scene(),*impl_->local_plan}); impl_->local_plan.reset(); }
        else if (impl_->draft_debt()) impl_->draft->retry_publication();
        else if (impl_->document.presentation_pending()) {
            Guard guard(impl_->ticking); impl_->document.retry_presentation(); impl_->ack();
        }
        if (!impl_->draft_debt()) impl_->tick();
        return;
    }
    const auto origin=impl_->pending->origin;
    if (origin.kind==Impl::OriginKind::base) {
        Guard guard(impl_->ticking); impl_->document.retry_presentation(); impl_->ack();
    } else if (origin.kind==Impl::OriginKind::draft && impl_->draft_debt()) impl_->draft->retry_publication();
    else { impl_->send(*impl_->pending); if (!impl_->pending) impl_->local_plan.reset(); }
    if (!impl_->pending) impl_->tick();
}
void AppendedDocumentForms::viewport(DocumentViewport v) {
    impl_->owner(); if (!v.columns || v.columns>500 || !v.drawable_rows || v.drawable_rows>200) throw std::invalid_argument("Invalid forms viewport");
    if (impl_->stopped) return;
    impl_->advance(impl_->input_epoch);
    if (!impl_->quiet() || impl_->pending || impl_->local_plan || impl_->draft_debt() || impl_->document.presentation_pending()) { impl_->queued_viewport=v; return; }
    if (impl_->modal || impl_->authority_lost || impl_->refresh_due) impl_->advance(impl_->modal_generation);
    impl_->viewport=v; impl_->document.viewport(v);
}
void AppendedDocumentForms::foreground(bool value) {
    impl_->owner(); if (impl_->stopped || impl_->foreground==value) return;
    const bool had_cover=impl_->modal || impl_->refresh_due || impl_->authority_lost;
    if (!had_cover) impl_->advance(impl_->modal_generation);
    impl_->foreground=value; impl_->advance(impl_->input_epoch); impl_->authority_lost=true;
    impl_->accepted_query.reset();
    impl_->scene_dirty=true;
    impl_->retire_prepared("Undelivered input retired after foreground loss");
    impl_->begin.reset(); impl_->finish.reset(); impl_->choose.reset(); impl_->activate_control.reset(); if (impl_->draft) impl_->draft->close();
    if (impl_->outstanding && !impl_->delivered) {
        if (const auto* request=std::get_if<DocumentEngineRequest>(&impl_->outstanding->action))
            impl_->retired_document=request->token;
        impl_->outstanding.reset(); impl_->request_origin.reset(); impl_->request_visible=false;
        impl_->error="Undelivered input retired after foreground loss";
    }
    if (value && !impl_->outstanding) impl_->request_refresh();
    if (impl_->quiet() && !impl_->pending && !impl_->local_plan) {
        impl_->scene_dirty=false;
        try { impl_->local(); } catch (...) { if (!impl_->pending && !impl_->local_plan) throw; }
    }
}
void AppendedDocumentForms::document_actions_available(bool value) {
    impl_->owner();
    if (impl_->stopped || impl_->actions_available==value) return;
    impl_->actions_available=value; impl_->advance(impl_->input_epoch); impl_->scene_dirty=true;
    if (!value) {
        impl_->choose.reset();
        const bool had_control=impl_->activate_control.has_value() ||
            (impl_->prepared && std::holds_alternative<ActivateDocumentControl>(*impl_->prepared)) ||
            (impl_->outstanding && std::holds_alternative<ActivateDocumentControl>(impl_->outstanding->action));
        impl_->activate_control.reset();
        if (impl_->prepared && (std::holds_alternative<ChooseSingleDocumentOption>(*impl_->prepared) ||
                std::holds_alternative<ActivateDocumentControl>(*impl_->prepared)))
            impl_->retire_prepared("Undelivered document action retired after capability loss");
        if (impl_->outstanding && !impl_->delivered &&
            (std::holds_alternative<ChooseSingleDocumentOption>(impl_->outstanding->action) ||
             std::holds_alternative<ActivateDocumentControl>(impl_->outstanding->action))) {
            impl_->outstanding.reset(); impl_->request_origin.reset(); impl_->request_visible=false;
        }
        if (had_control) {
            if (!impl_->modal && !impl_->refresh_due && !impl_->authority_lost) impl_->advance(impl_->modal_generation);
            impl_->authority_lost=true;
            if (!impl_->outstanding) impl_->request_refresh();
        }
        if (impl_->single_choice) {
            impl_->authority_lost=true;
            if (!impl_->outstanding) { impl_->closing=true; impl_->request_refresh(); }
        }
    }
}
bool AppendedDocumentForms::queue_selection(DocumentSelection selection) {
    impl_->owner();
    return impl_->quiet() && impl_->actions_available && impl_->body_ready() && impl_->document.queue_selection(std::move(selection));
}
void AppendedDocumentForms::request_observation() { impl_->request_observation(); }
void AppendedDocumentForms::request_presentation() { impl_->owner(); if (!impl_->stopped) impl_->scene_dirty=true; }
std::optional<DocumentFormsRequest> AppendedDocumentForms::next_request() { return impl_->next(); }
bool AppendedDocumentForms::complete(DocumentFormsRequestToken token,DocumentFormsCompletion value) { return impl_->complete(token,std::move(value)); }
bool AppendedDocumentForms::fail(DocumentFormsRequestToken token,DocumentRequestFailure value) {
    impl_->owner(); if (!impl_->quiet() || impl_->stopped || impl_->pending || impl_->local_plan || impl_->draft_debt() || impl_->scene_dirty || !impl_->outstanding || !impl_->delivered || impl_->outstanding->token!=token) return false;
    const auto* body=std::get_if<DocumentEngineRequest>(&impl_->outstanding->action);
    if ((body && body->intent) || std::holds_alternative<ChooseSingleDocumentOption>(impl_->outstanding->action) ||
        std::holds_alternative<ActivateDocumentControl>(impl_->outstanding->action))
        return impl_->complete(token,DocumentBodyCompletion{value==DocumentRequestFailure::unknown ? DocumentBodyOutcome::indeterminate : DocumentBodyOutcome::rejected,{}});
    if (auto* request=std::get_if<DocumentEngineRequest>(&impl_->outstanding->action)) {
        (void)impl_->document.fail_request(request->token,value); impl_->outstanding.reset(); impl_->delivered=false;
        impl_->observation_scheduled=false;
        impl_->accepted_query.reset();
        impl_->request_origin.reset(); impl_->request_visible=false;
        impl_->base_ack=false; impl_->error="Document outcome is unknown"; return true;
    }
    return impl_->complete(token,DocumentFormsControlReply{value==DocumentRequestFailure::unknown?F::FormDraftOutcome::unknown:F::FormDraftOutcome::rejected,{}});
}
void AppendedDocumentForms::shutdown() noexcept { if (impl_) impl_->stop(); }
const gui::Snapshot& AppendedDocumentForms::view() const noexcept { return impl_->pending?impl_->pending->view:impl_->committed; }
std::uint64_t AppendedDocumentForms::input_epoch() const noexcept { return impl_->input_epoch; }
bool AppendedDocumentForms::presentation_pending() const noexcept { return !impl_->stopped && (bool(impl_->pending)||bool(impl_->local_plan)||impl_->document.presentation_pending()||impl_->draft_debt()||impl_->scene_dirty); }
bool AppendedDocumentForms::closed() const noexcept { return impl_->stopped; }
bool AppendedDocumentForms::body_ready() const noexcept { return impl_->body_ready(); }
bool AppendedDocumentForms::modal_open() const noexcept { return impl_->modal; }
std::optional<DocumentFormsRequestToken> AppendedDocumentForms::accepted_query() const noexcept { return impl_->accepted_query; }
std::optional<F::FormDraftPhase> AppendedDocumentForms::draft_phase() const noexcept { return impl_->draft?std::optional(impl_->draft->view().phase):std::nullopt; }
std::optional<F::FormByteSelection> AppendedDocumentForms::local_selection() const noexcept { return impl_->draft&&!impl_->redacted&&!impl_->awaiting_observation&&!impl_->authority_lost?std::optional(impl_->draft->view().selection):std::nullopt; }
const std::string& AppendedDocumentForms::last_error() const noexcept { return impl_->error; }

} // namespace foundation::ui
