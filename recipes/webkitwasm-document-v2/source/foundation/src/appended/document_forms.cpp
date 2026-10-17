#include <foundation/appended/document_forms.hpp>
#include <foundation/appended/registry.hpp>

#include <algorithm>
#include <limits>
#include <set>
#include <stdexcept>
#include <utility>

namespace foundation::appended {
namespace {
[[noreturn]] void invalid(const char* reason) { throw std::invalid_argument(reason); }
void limits_valid(const FormLimits& value) {
    const FormLimits maximum;
    if (!value.controls || value.controls > maximum.controls || !value.options || value.options > maximum.options ||
        !value.field_utf16 || value.field_utf16 > maximum.field_utf16 ||
        !value.total_utf16 || value.total_utf16 > maximum.total_utf16)
        invalid("invalid form limits");
}
bool version_valid(FormVersion value) { return value.generation && value.epoch && value.revision; }
bool same_document(FormVersion a, FormVersion b) { return a.generation == b.generation && a.epoch == b.epoch; }
bool direction_valid(FormDirection value) {
    return value == FormDirection::none || value == FormDirection::forward || value == FormDirection::backward;
}
struct Boundary { std::size_t byte; std::uint32_t units; };
std::vector<Boundary> boundaries(std::string_view text) {
    // Reuse the project's scalar UTF-8 validator, then count native UTF-16 units.
    if (text.size() > FormLimits{}.field_utf16 * 4 || text.find('\0') != text.npos ||
        !valid_utf8({reinterpret_cast<const std::uint8_t*>(text.data()), text.size()}))
        invalid("invalid bounded form UTF-8");
    std::vector<Boundary> result{{0, 0}};
    std::size_t position = 0;
    std::uint32_t units = 0;
    while (position < text.size()) {
        const auto first = static_cast<unsigned char>(text[position]);
        const auto bytes = first < 0x80 ? 1u : first < 0xe0 ? 2u : first < 0xf0 ? 3u : 4u;
        units += bytes == 4 ? 2u : 1u;
        if (units > FormLimits{}.field_utf16) invalid("form text exceeds UTF-16 bound");
        position += bytes;
        result.push_back({position, units});
    }
    return result;
}
std::uint32_t units_at(const std::vector<Boundary>& index, std::size_t byte) {
    const auto found = std::lower_bound(index.begin(), index.end(), byte,
        [](const Boundary& value, std::size_t key) { return value.byte < key; });
    if (found == index.end() || found->byte != byte) invalid("form selection is not a UTF-8 scalar boundary");
    return found->units;
}
std::size_t byte_at(const std::vector<Boundary>& index, std::uint32_t units) {
    const auto found = std::lower_bound(index.begin(), index.end(), units,
        [](const Boundary& value, std::uint32_t key) { return value.units < key; });
    if (found == index.end() || found->units != units) invalid("form selection is not a UTF-16 scalar boundary");
    return found->byte;
}
std::size_t text_units(std::string_view text) { return boundaries(text).back().units; }
struct Budget {
    FormLimits limits;
    std::size_t units{0}, options{0};
    std::set<std::uint64_t> nodes;
    void text(std::string_view value) {
        const auto count = text_units(value);
        if (count > limits.field_utf16 || count > limits.total_utf16 - units)
            invalid("form aggregate text bound exceeded");
        units += count;
    }
    void node(std::uint64_t value) {
        if (!value || !nodes.insert(value).second) invalid("invalid or duplicate form node identity");
    }
};
bool text_kind(FormKind kind) { return kind == FormKind::text || kind == FormKind::number || kind == FormKind::textarea; }
void validate_control(FormVersion version, const FormControl& control, Budget& budget) {
    budget.node(control.node);
    budget.text(control.native_type);
    budget.text(control.label);
    if (control.native_type.empty()) invalid("form native type is absent");
    for (unsigned char c : control.native_type)
        if (!(c >= 'a' && c <= 'z') && !(c >= '0' && c <= '9') && c != '-') invalid("invalid native form type");
    constexpr FormCapabilities all = 31;
    if (control.capabilities & ~all) invalid("unknown form capability");
    if (control.capabilities && (!control.complete || control.disabled || control.read_only ||
        !control.focusable || control.omitted)) invalid("unavailable form grants authority");
    if (control.lease && !control.capabilities) invalid("form lease has no supported operations");
    if (control.lease && (!control.focused || !control.lease->id || control.lease->node != control.node ||
        !version_valid(control.lease->captured) || !same_document(control.lease->captured, version) ||
        control.lease->captured.revision > version.revision)) invalid("invalid form lease identity");
    FormCapabilities allowed = 0;
    if (text_kind(control.kind)) {
        const auto* state = std::get_if<FormTextState>(&control.state);
        if (!state) invalid("text form state is absent");
        if ((control.kind == FormKind::number && control.native_type != "number") ||
            (control.kind == FormKind::textarea && control.native_type != "textarea") ||
            (control.kind == FormKind::text && control.native_type != "text" && control.native_type != "search" &&
             control.native_type != "url" && control.native_type != "tel" && control.native_type != "email"))
            invalid("native type does not match text form kind");
        budget.text(state->value);
        budget.text(state->editing_text);
        if (state->selection) {
            if (!control.complete) invalid("incomplete form exposes native selection");
            (void)form_byte_selection(state->editing_text, *state->selection);
        }
        if (form_has(control.capabilities, FormCapability::replace_text) && !state->selection)
            invalid("editable form selection is absent");
        allowed = form_capability(FormCapability::replace_text) | form_capability(FormCapability::finish);
    } else if (control.kind == FormKind::checkbox) {
        if (control.native_type != "checkbox" || !std::holds_alternative<FormCheckState>(control.state))
            invalid("invalid native checkbox state");
        allowed = form_capability(FormCapability::set_checked) | form_capability(FormCapability::finish);
    } else if (control.kind == FormKind::select_one || control.kind == FormKind::select_many) {
        const auto* state = std::get_if<FormSelectState>(&control.state);
        if (!state || state->multiple != (control.kind == FormKind::select_many) ||
            control.native_type != (state->multiple ? "select-multiple" : "select-one"))
            invalid("invalid native select state");
        std::size_t selected = 0;
        for (const auto& option : state->options) {
            if (++budget.options > budget.limits.options) invalid("form option bound exceeded");
            budget.node(option.node);
            budget.text(option.label);
            selected += option.selected;
        }
        if (!state->multiple && selected > 1) invalid("single select has multiple selected options");
        allowed = form_capability(FormCapability::finish);
        if (!state->multiple) allowed |= form_capability(FormCapability::open_popup);
        else if (!state->menu_list) allowed |= form_capability(FormCapability::set_option);
    } else if (control.kind == FormKind::secure_readonly || control.kind == FormKind::unsupported) {
        if (!std::holds_alternative<std::monostate>(control.state)) invalid("unsupported form retains private state");
        // Even a string length or selection in a secure observation is forbidden.
        // The compositor supplies its own fixed masked label.
        if (control.kind == FormKind::secure_readonly && !control.label.empty()) invalid("secure form exposes label data");
    } else invalid("unknown form kind");
    if (control.capabilities & ~allowed) invalid("form kind grants unsupported action");
}
bool editable(const FormControl& control) {
    if (!control.lease) return false;
    if (text_kind(control.kind)) return form_has(control.capabilities, FormCapability::replace_text);
    if (control.kind == FormKind::checkbox) return form_has(control.capabilities, FormCapability::set_checked);
    return control.kind == FormKind::select_many && form_has(control.capabilities, FormCapability::set_option);
}
const FormOption* option(const FormControl& control, std::uint64_t node) {
    const auto* state = std::get_if<FormSelectState>(&control.state);
    if (!state) return nullptr;
    const auto found = std::find_if(state->options.begin(), state->options.end(),
        [node](const auto& value) { return value.node == node; });
    return found == state->options.end() ? nullptr : &*found;
}
} // namespace

FormControlRange form_control_range(std::string_view text, FormByteSelection selected) {
    const auto index = boundaries(text);
    const auto anchor = units_at(index, selected.anchor), caret = units_at(index, selected.caret);
    return {std::min(anchor, caret), std::max(anchor, caret), anchor == caret ? FormDirection::none :
        anchor < caret ? FormDirection::forward : FormDirection::backward};
}
FormByteSelection form_byte_selection(std::string_view text, FormControlRange range) {
    if (range.start > range.end || !direction_valid(range.direction)) invalid("invalid native form range");
    const auto index = boundaries(text);
    const auto start = byte_at(index, range.start), end = byte_at(index, range.end);
    return range.direction == FormDirection::backward ? FormByteSelection{end, start} : FormByteSelection{start, end};
}
void validate_document_forms(const DocumentFormsSnapshot& snapshot, FormLimits limits) {
    limits_valid(limits);
    if (snapshot.protocol != document_forms_version || !version_valid(snapshot.version) || snapshot.controls.size() > limits.controls)
        invalid("invalid forms snapshot identity or bound");
    Budget budget{limits, 0, 0, {}};
    std::size_t focused = 0;
    for (const auto& control : snapshot.controls) {
        if (control.focused && ++focused > 1) invalid("forms snapshot has multiple focused controls");
        validate_control(snapshot.version, control, budget);
    }
}
void validate_form_update(const FormUpdate& update, FormLimits limits) {
    limits_valid(limits);
    if (!version_valid(update.version)) invalid("invalid form update identity");
    Budget budget{limits, 0, 0, {}};
    validate_control(update.version, update.control, budget);
}
bool form_control_state_matches(const FormControl& a, const FormControl& b) {
    return a.node == b.node && a.kind == b.kind && a.native_type == b.native_type && a.label == b.label &&
        a.disabled == b.disabled && a.read_only == b.read_only && a.focusable == b.focusable && a.focused == b.focused &&
        a.omitted == b.omitted && a.complete == b.complete && a.capabilities == b.capabilities && a.state == b.state;
}

struct FormDraft::Impl {
    std::uint64_t generation, sequence{0};
    FormLimits limits;
    Publish publish;
    FormDraftView view;
    std::optional<FormDraftRequest> request;
    std::set<std::uint64_t> spent_leases;
    bool delivered{false}, busy{false}, closed{false}, teardown{false}, retired{false}, fresh_after_failure{false};
    std::uint64_t failed_lease{0};

    Impl(std::uint64_t id, FormUpdate update, Publish sink, FormLimits bounds)
        : generation(id), limits(bounds), publish(std::move(sink)) {
        if (!generation || !publish) invalid("form draft requires identity and local publisher");
        validate_form_update(update, limits);
        reset(view, std::move(update));
        (void)install(view);
    }
    static void dirty(FormDraftView& value) {
        if (const auto* state = std::get_if<FormTextState>(&value.base.control.state)) value.dirty = value.text != state->editing_text;
        else if (const auto* state = std::get_if<FormCheckState>(&value.base.control.state)) value.dirty = value.checked != state->checked;
        else if (value.option) {
            const auto* found = option(value.base.control, value.option->node);
            value.dirty = found && found->selected != value.option->selected;
        } else value.dirty = false;
    }
    static void reset(FormDraftView& value, FormUpdate update) {
        const auto revision = value.revision;
        value = {};
        value.revision = revision;
        value.base = std::move(update);
        value.phase = editable(value.base.control) ? FormDraftPhase::editing : FormDraftPhase::unavailable;
        if (const auto* text = std::get_if<FormTextState>(&value.base.control.state)) {
            value.text = text->editing_text;
            if (text->selection) value.selection = form_byte_selection(value.text, *text->selection);
        }
        if (const auto* check = std::get_if<FormCheckState>(&value.base.control.state)) value.checked = check->checked;
    }
    bool install(FormDraftView candidate) {
        if (view.revision == std::numeric_limits<std::uint64_t>::max()) throw std::overflow_error("form draft revision exhausted");
        candidate.revision = view.revision + 1;
        candidate.publication_pending = false;
        view = std::move(candidate);
        return publish_current(false);
    }
    bool publish_current(bool propagate) {
        // The callback gets the SAME owned candidate/revision on every retry.
        view.publication_pending = true;
        busy = true;
        try {
            auto candidate = view;
            candidate.publication_pending = false;
            publish(candidate);
            busy = false;
            view.publication_pending = false;
            return true;
        } catch (...) {
            busy = false;
            view.publication_pending = !teardown;
            if (propagate) throw;
            return false;
        }
    }
    bool compatible(const FormUpdate& update) const {
        return same_document(update.version, view.base.version) && update.control.node == view.base.control.node &&
            update.control.kind == view.base.control.kind && update.control.native_type == view.base.control.native_type;
    }
    void check_order(const FormUpdate& update) const {
        if (same_document(update.version, view.base.version)) {
            const auto newest = view.latest ? std::max(view.latest->version.revision, view.base.version.revision) : view.base.version.revision;
            if (update.version.revision < newest) invalid("stale form observation");
            if (update.version == view.base.version && !form_control_state_matches(update.control, view.base.control))
                invalid("conflicting form observation at same revision");
            if (view.latest && update.version == view.latest->version &&
                !form_control_state_matches(update.control, view.latest->control)) invalid("conflicting fresh form observation");
        }
    }
    bool fresh(const FormUpdate& update) const {
        return compatible(update) && editable(update.control) && update.control.lease->id != failed_lease &&
            !spent_leases.contains(update.control.lease->id);
    }
    bool draft_allowed(const FormDraftView& value) const {
        if (!editable(value.base.control)) return false;
        if (text_kind(value.base.control.kind)) {
            return text_units(value.text) <= limits.field_utf16;
        }
        if (value.base.control.kind == FormKind::select_many && value.option) {
            const auto* found = option(value.base.control, value.option->node);
            return found && !found->disabled && !found->omitted;
        }
        return value.base.control.kind == FormKind::checkbox;
    }
    bool handle(FormDraftEvent event) {
        if (busy || closed || view.publication_pending) return false;
        auto candidate = view;
        if (std::holds_alternative<CancelFormDraft>(event)) {
            closed = true;
            request.reset();
            candidate.phase = FormDraftPhase::closed;
            candidate.apply_queued = false;
            return install(std::move(candidate));
        }
        if (retired) return false;
        if (request) return false;
        if (std::holds_alternative<ReloadFormDraft>(event)) {
            if (retired || !view.latest || !same_document(view.latest->version, view.base.version) ||
                view.latest->control.node != view.base.control.node) return false;
            if ((view.phase == FormDraftPhase::stale || view.phase == FormDraftPhase::unknown) &&
                !fresh_after_failure) return false;
            if (view.latest->control.lease && spent_leases.contains(view.latest->control.lease->id)) return false;
            reset(candidate, *view.latest);
            fresh_after_failure = false;
            return install(std::move(candidate));
        }
        if (std::holds_alternative<ReapplyFormDraft>(event)) {
            if (retired || (view.phase != FormDraftPhase::stale && view.phase != FormDraftPhase::unknown) ||
                !fresh_after_failure || !view.latest || !fresh(*view.latest)) return false;
            candidate.base = *view.latest;
            candidate.latest.reset();
            candidate.phase = FormDraftPhase::editing;
            if (!draft_allowed(candidate)) return false;
            dirty(candidate);
            candidate.apply_queued = candidate.dirty;
            fresh_after_failure = false;
            return install(std::move(candidate));
        }
        if (view.phase != FormDraftPhase::editing || view.apply_queued) return false;
        try {
            if (auto* edit = std::get_if<EditFormDraft>(&event)) {
                if (!text_kind(view.base.control.kind) || edit->base_text != view.text || edit->text == view.text ||
                    text_units(edit->text) > limits.field_utf16) return false;
                candidate.text = std::move(edit->text);
                // GUI retained selection is polled after its callback. Until
                // then retain only a valid collapsed source-byte boundary.
                candidate.selection = {candidate.text.size(), candidate.text.size()};
            } else if (auto* check = std::get_if<CheckFormDraft>(&event)) {
                if (view.base.control.kind != FormKind::checkbox || check->checked == view.checked) return false;
                candidate.checked = check->checked;
            } else if (auto* selected = std::get_if<OptionFormDraft>(&event)) {
                if (view.base.control.kind != FormKind::select_many) return false;
                const auto* found = option(view.base.control, selected->node);
                if (!found || found->disabled || found->omitted ||
                    (view.option && view.dirty && view.option->node != selected->node)) return false;
                candidate.option = FormOptionDraft{selected->node, selected->selected};
            } else if (std::holds_alternative<ApplyFormDraft>(event)) {
                if (!view.dirty || !draft_allowed(view)) return false;
                candidate.apply_queued = true;
            } else return false;
        } catch (const std::invalid_argument&) { return false; }
        dirty(candidate);
        return install(std::move(candidate));
    }
    FormAction action() const {
        const auto& expected = *view.base.control.lease;
        if (const auto* text = std::get_if<FormTextState>(&view.base.control.state)) {
            const auto count = static_cast<std::uint32_t>(text_units(text->editing_text));
            return ReplaceFormText{expected, {0, count, count ? FormDirection::forward : FormDirection::none}, view.text};
        }
        if (view.base.control.kind == FormKind::checkbox) return SetFormChecked{expected, view.checked};
        return SetFormOption{expected, view.option->node, view.option->selected};
    }
    std::optional<FormDraftRequest> next() {
        if (busy || closed || retired || view.publication_pending) return {};
        if (!request) {
            if (!view.apply_queued || view.phase != FormDraftPhase::editing || !view.dirty || !draft_allowed(view)) return {};
            if (sequence == std::numeric_limits<std::uint64_t>::max()) throw std::overflow_error("form request identity exhausted");
            if (view.revision == std::numeric_limits<std::uint64_t>::max()) throw std::overflow_error("form draft revision exhausted");
            if (spent_leases.size() == FormDraft::max_retired_leases || spent_leases.contains(view.base.control.lease->id)) {
                auto unavailable = view;
                unavailable.phase = FormDraftPhase::unavailable;
                unavailable.apply_queued = false;
                retired = true;
                (void)install(std::move(unavailable));
                return {};
            }
            FormDraftRequest next{{generation, sequence + 1}, action()};
            auto candidate = view;
            candidate.phase = FormDraftPhase::pending;
            candidate.apply_queued = false;
            spent_leases.insert(view.base.control.lease->id);
            request = std::move(next);
            ++sequence;
            delivered = false;
            if (!install(std::move(candidate))) return {};
            if (closed) return {};
        }
        if (delivered) return {};
        auto result = request;
        delivered = true;
        return result;
    }
    bool observe(FormUpdate update) {
        if (busy || closed || view.publication_pending) return false;
        validate_form_update(update, limits);
        check_order(update);
        auto candidate = view;
        candidate.latest = std::move(update);
        if (!compatible(*candidate.latest)) {
            candidate.phase = FormDraftPhase::unavailable;
            candidate.apply_queued = false;
            fresh_after_failure = false;
            // A replacement lifetime cannot revive this editor even if a later
            // observation reuses its numeric node. A new editor requires a new
            // deliberate composition-owned Begin, never old queued input.
            if (!same_document(candidate.latest->version, view.base.version) ||
                candidate.latest->control.node != view.base.control.node) retired = true;
            request.reset();
            delivered = false;
        } else if ((!request && view.phase == FormDraftPhase::editing) || (request && !delivered)) {
            if (!form_control_state_matches(view.base.control, candidate.latest->control)) {
                failed_lease = view.base.control.lease ? view.base.control.lease->id : 0;
                candidate.phase = FormDraftPhase::stale;
                candidate.apply_queued = false;
                fresh_after_failure = fresh(*candidate.latest);
                request.reset();
                delivered = false;
            }
        } else if (view.phase == FormDraftPhase::stale || view.phase == FormDraftPhase::unknown) {
            fresh_after_failure = fresh(*candidate.latest);
        }
        return install(std::move(candidate));
    }
    bool complete(FormDraftToken token, FormDraftOutcome outcome, std::optional<FormUpdate> update) {
        if (busy || closed || view.publication_pending || !request || !delivered || request->token != token) return false;
        auto candidate = view;
        failed_lease = view.base.control.lease ? view.base.control.lease->id : 0;
        request.reset();
        delivered = false;
        fresh_after_failure = false;
        candidate.phase = outcome == FormDraftOutcome::rejected ? FormDraftPhase::stale : FormDraftPhase::unknown;
        candidate.apply_queued = false;
        try {
            if (outcome != FormDraftOutcome::accepted && outcome != FormDraftOutcome::rejected && outcome != FormDraftOutcome::unknown)
                invalid("unknown form completion status");
            if (outcome == FormDraftOutcome::accepted && !update) invalid("accepted form action lacks native readback");
            if (update) {
                validate_form_update(*update, limits);
                check_order(*update);
                candidate.latest = *update;
                if (!same_document(view.base.version, update->version) || update->control.node != view.base.control.node)
                    retired = true;
                if (!compatible(*update)) candidate.phase = FormDraftPhase::unavailable;
                else if (outcome == FormDraftOutcome::accepted && fresh(*update))
                    reset(candidate, std::move(*update));
                else if (outcome == FormDraftOutcome::accepted && !editable(update->control))
                    candidate.phase = FormDraftPhase::unavailable;
                else fresh_after_failure = fresh(*update);
            }
        } catch (...) {
            candidate.phase = FormDraftPhase::unknown;
            candidate.latest.reset();
            (void)install(std::move(candidate));
            throw;
        }
        (void)install(std::move(candidate));
        return true;
    }
};

FormDraft::FormDraft(std::uint64_t generation, FormUpdate update, Publish publish, FormLimits limits)
    : impl_(std::make_unique<Impl>(generation, std::move(update), std::move(publish), limits)) {}
FormDraft::~FormDraft() = default;
bool FormDraft::handle(FormDraftEvent event) { return impl_->handle(std::move(event)); }
bool FormDraft::selection(FormByteSelection selected) {
    if (impl_->busy || impl_->closed || impl_->view.publication_pending || impl_->request ||
        impl_->view.phase != FormDraftPhase::editing || !text_kind(impl_->view.base.control.kind)) return false;
    try { (void)form_control_range(impl_->view.text, selected); }
    catch (const std::invalid_argument&) { return false; }
    impl_->view.selection = selected;
    return true;
}
std::optional<FormDraftRequest> FormDraft::next_request() { return impl_->next(); }
bool FormDraft::complete(FormDraftToken token, FormDraftOutcome outcome, std::optional<FormUpdate> update) {
    return impl_->complete(token, outcome, std::move(update));
}
bool FormDraft::observe(FormUpdate update) { return impl_->observe(std::move(update)); }
void FormDraft::retry_publication() {
    if (!impl_->busy && !impl_->teardown && impl_->view.publication_pending) (void)impl_->publish_current(true);
}
void FormDraft::close() noexcept {
    impl_->closed = true;
    impl_->teardown = true;
    impl_->request.reset();
    impl_->view.phase = FormDraftPhase::closed;
    impl_->view.apply_queued = false;
    impl_->view.publication_pending = false;
}
const FormDraftView& FormDraft::view() const noexcept { return impl_->view; }
bool FormDraft::request_pending() const noexcept { return bool(impl_->request); }

} // namespace foundation::appended
