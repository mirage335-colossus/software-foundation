// SPDX-License-Identifier: CC0-1.0
#include <foundation/gui/surface.hpp>

#include <algorithm>
#include <cmath>
#include <limits>
#include <set>
#include <stdexcept>
#include <type_traits>
#include <utility>

namespace foundation::gui_surface {
namespace {
constexpr std::size_t key_bytes = 64;
constexpr std::size_t owner_bytes = 128;
constexpr double coordinate_limit = 1000000;
constexpr std::uint64_t maximum_id = std::numeric_limits<std::uint64_t>::max();

bool has(const Capabilities& c, Feature f) noexcept { return (c.supported & feature(f)) != 0; }
bool scalar_text(const std::string& text) noexcept {
    const auto* bytes = reinterpret_cast<const unsigned char*>(text.data());
    for (std::size_t i = 0; i < text.size();) {
        const unsigned first = bytes[i++];
        if (first == 0) return false;
        if (first < 0x80) continue;
        unsigned count = 0, value = 0, minimum = 0;
        if (first >= 0xc2 && first <= 0xdf) { count = 1; value = first & 31; minimum = 0x80; }
        else if (first >= 0xe0 && first <= 0xef) { count = 2; value = first & 15; minimum = 0x800; }
        else if (first >= 0xf0 && first <= 0xf4) { count = 3; value = first & 7; minimum = 0x10000; }
        else return false;
        if (count > text.size() - i) return false;
        while (count--) {
            const unsigned next = bytes[i++];
            if ((next & 0xc0) != 0x80) return false;
            value = (value << 6) | (next & 63);
        }
        if (value < minimum || value > 0x10ffff || (value >= 0xd800 && value <= 0xdfff)) return false;
    }
    return true;
}
bool boundary_unchecked(const std::string& text, std::size_t position) noexcept {
    return position <= text.size() && (position == text.size() ||
        (static_cast<unsigned char>(text[position]) & 0xc0) != 0x80);
}
bool valid_rect(const Rect& r) noexcept {
    return std::isfinite(r.x) && std::isfinite(r.y) && std::isfinite(r.width) && std::isfinite(r.height) &&
        std::abs(r.x) <= coordinate_limit && std::abs(r.y) <= coordinate_limit &&
        r.width >= 0 && r.height >= 0 && r.width <= coordinate_limit && r.height <= coordinate_limit;
}
bool inside(const Rect& outer, const Rect& inner) noexcept {
    return inner.x >= outer.x && inner.y >= outer.y &&
        inner.x + inner.width <= outer.x + outer.width && inner.y + inner.height <= outer.y + outer.height;
}
bool key_valid(const std::string& key, const std::string& code, bool wildcard = false) noexcept {
    if ((!wildcard && key.empty()) || key.size() > key_bytes || code.size() > key_bytes || !valid_text(key)) return false;
    return std::all_of(code.begin(), code.end(), [](unsigned char c) { return c >= 33 && c <= 126; });
}
bool capture_valid(Capture value) noexcept { return value == Capture::pass || value == Capture::capture; }
Status validate_keys(const KeyCapturePolicy& policy, const Capabilities& capabilities) {
    if (!capture_valid(policy.fallback)) return Status::invalid_value;
    if (policy.rules.size() > capabilities.limits.capture_rules) return Status::limit_exceeded;
    if ((policy.fallback == Capture::capture || !policy.rules.empty()) && !has(capabilities, Feature::raw_keys)) return Status::unsupported;
    for (const auto& rule : policy.rules)
        if (!key_valid(rule.key, rule.code, true) || !capture_valid(rule.disposition) || (!rule.down && !rule.up) ||
            ((rule.required_modifiers | rule.forbidden_modifiers) & ~known_modifiers) ||
            (rule.required_modifiers & rule.forbidden_modifiers)) return Status::invalid_value;
    return Status::ok;
}
Status validate_formats(const std::vector<MimeText>& formats, const Capabilities& capabilities, bool allow_empty = false) {
    if (formats.empty()) return allow_empty ? Status::ok : Status::invalid_value;
    if (formats.size() > 2) return Status::limit_exceeded;
    bool plain = false, html = false;
    std::size_t bytes = 0;
    for (const auto& format : formats) {
        if (format.type == "text/plain") {
            if (plain) return Status::invalid_value;
            plain = true;
            if (!has(capabilities, Feature::clipboard_text)) return Status::unsupported;
        } else if (format.type == "text/html") {
            if (html) return Status::invalid_value;
            html = true;
            if (!has(capabilities, Feature::clipboard_html)) return Status::unsupported;
        } else return Status::unsupported;
        if (format.text.size() > capabilities.limits.clipboard_bytes - bytes) return Status::limit_exceeded;
        if (!valid_text(format.text)) return Status::invalid_value;
        bytes += format.text.size();
    }
    return Status::ok;
}
Feature popup_feature(PopupKind kind) {
    switch (kind) {
        case PopupKind::single_choice: return Feature::choice_popup;
        case PopupKind::action_menu: return Feature::action_popup;
        case PopupKind::search_results: return Feature::search_popup;
    }
    return Feature::choice_popup;
}
bool popup_kind_valid(PopupKind kind) noexcept {
    return kind == PopupKind::single_choice || kind == PopupKind::action_menu || kind == PopupKind::search_results;
}
struct PopupValidation {
    const Capabilities& capabilities;
    const Popup& popup;
    std::set<PopupItemId> ids;
    std::size_t count = 0, bytes = 0;
    const PopupItem* selected = nullptr;
    Status items(const std::vector<PopupItem>& rows, unsigned depth) {
        if (depth > capabilities.limits.popup_depth) return Status::limit_exceeded;
        if (rows.size() > capabilities.limits.popup_items - count) return Status::limit_exceeded;
        count += rows.size();
        for (const auto& row : rows) {
            for (const auto* text : {&row.label, &row.accessible_name}) {
                if (text->size() > capabilities.limits.popup_text_bytes - bytes) return Status::limit_exceeded;
                if (!valid_text(*text)) return Status::invalid_value;
                bytes += text->size();
            }
            if (!row.id || !ids.insert(row.id).second) return Status::invalid_value;
            if (popup.selected == row.id) selected = &row;
            switch (row.kind) {
                case PopupItemKind::item:
                    if (!row.children.empty()) return Status::invalid_value;
                    break;
                case PopupItemKind::group_label: case PopupItemKind::separator:
                    if (row.enabled || row.selected || row.checked || row.checkable || !row.children.empty()) return Status::invalid_value;
                    break;
                case PopupItemKind::submenu:
                    if (popup.kind != PopupKind::action_menu || row.children.empty() || row.selected || row.checked || row.checkable) return Status::invalid_value;
                    if (!has(capabilities, Feature::popup_submenus)) return Status::unsupported;
                    if (const auto status = items(row.children, depth + 1); status != Status::ok) return status;
                    break;
                default: return Status::invalid_value;
            }
            if ((row.checked && !row.checkable) || (row.checkable && popup.kind != PopupKind::action_menu)) return Status::invalid_value;
        }
        return Status::ok;
    }
};
Status validate_popup(const Popup& popup, const Identity& identity, const Capabilities& capabilities) {
    if (!popup_kind_valid(popup.kind) || (popup.direction != Direction::left_to_right && popup.direction != Direction::right_to_left) ||
        !popup.token.instance || !popup.token.revision || popup.token.generation != identity.generation || popup.token.epoch != identity.epoch ||
        !valid_rect(popup.anchor) || popup.items.empty()) return Status::invalid_value;
    if (!has(capabilities, popup_feature(popup.kind))) return Status::unsupported;
    PopupValidation validation{capabilities, popup, {}, 0, 0, nullptr};
    if (const auto result = validation.items(popup.items, 1); result != Status::ok) return result;
    if (popup.selected && (!validation.selected || validation.selected->kind != PopupItemKind::item)) return Status::invalid_value;
    return Status::ok;
}
Status validate_presentation(const Presentation& p, const Capabilities& capabilities, std::uint64_t generation) {
    if (const auto result = negotiate(capabilities, p.required); result != Status::ok) return result;
    const auto& identity = p.identity;
    if (identity.owner.id.empty() || identity.owner.id.size() > owner_bytes || !valid_text(identity.owner.id) ||
        !identity.owner.generation || !identity.presentation_revision || identity.generation != generation || !identity.epoch || !identity.context ||
        !valid_rect(p.bounds) || !valid_rect(p.clip) || !inside(p.bounds, p.clip) || !std::isfinite(p.display_scale) ||
        p.display_scale <= 0 || p.display_scale > 16) return Status::invalid_value;
    if (const auto result = validate_keys(p.keys, capabilities); result != Status::ok) return result;
    if (p.editor) {
        if (!has(capabilities, Feature::surrounding_text)) return Status::unsupported;
        const auto& editor = *p.editor;
        if (editor.surrounding.size() > capabilities.limits.text_bytes) return Status::limit_exceeded;
        if (editor.composition_transaction && !has(capabilities, Feature::composition)) return Status::unsupported;
        if (editor.composition_transaction && !editor.editable) return Status::invalid_value;
        if (!editor.revision || !valid_text(editor.surrounding) || !valid_range(editor.surrounding, editor.selection) ||
            !valid_rect(editor.caret) || editor.input_purpose.size() > key_bytes || !valid_text(editor.input_purpose)) return Status::invalid_value;
    }
    if (p.clipboard) {
        if (!p.editor || !p.clipboard->id || p.clipboard->editor_revision != p.editor->revision) return Status::invalid_value;
        if (const auto result = validate_formats(p.clipboard->formats, capabilities); result != Status::ok) return result;
    }
    if (p.popup) {
        if (!p.available) return Status::unavailable;
        if (const auto result = validate_popup(*p.popup, identity, capabilities); result != Status::ok) return result;
    }
    return Status::ok;
}
bool same_context(const Identity& a, const Identity& b) noexcept {
    return a.owner == b.owner && a.generation == b.generation && a.epoch == b.epoch && a.context == b.context;
}
bool same_editor_basis(const EditorContext& a, const EditorContext& b) noexcept {
    return a.composition_transaction == b.composition_transaction && a.surrounding == b.surrounding &&
        a.selection == b.selection && a.selection_backward == b.selection_backward &&
        a.editable == b.editable && a.input_purpose == b.input_purpose;
}
bool same_key(const KeyTransition& a, const KeyTransition& b) noexcept {
    return a.location == b.location && ((!a.code.empty() && !b.code.empty()) ? a.code == b.code : a.code == b.code && a.key == b.key);
}
const PopupItem* actionable_item(const std::vector<PopupItem>& rows, PopupItemId id, bool enabled = true) {
    for (const auto& row : rows) {
        const bool available = enabled && row.enabled;
        if (row.id == id) return available && row.kind == PopupItemKind::item ? &row : nullptr;
        if (const auto* found = actionable_item(row.children, id, available)) return found;
    }
    return nullptr;
}
} // namespace

const char* status_name(Status status) noexcept {
    switch (status) {
        case Status::ok: return "ok";
        case Status::invalid_value: return "invalid_value";
        case Status::limit_exceeded: return "limit_exceeded";
        case Status::unsupported: return "unsupported";
        case Status::busy: return "busy";
        case Status::closed: return "closed";
        case Status::stale_identity: return "stale_identity";
        case Status::stale_revision: return "stale_revision";
        case Status::stale_preparation: return "stale_preparation";
        case Status::duplicate: return "duplicate";
        case Status::not_focused: return "not_focused";
        case Status::unavailable: return "unavailable";
        case Status::popup_active: return "popup_active";
        case Status::invalid_transaction: return "invalid_transaction";
    }
    return "unknown_status";
}
Status validate_capabilities(const Capabilities& c) noexcept {
    if (c.version != protocol_version || (c.supported & ~known_features)) return Status::unsupported;
    if (c.mouse_input_version != (has(c, Feature::mouse_input) ? mouse_input_version : 0)) return Status::unsupported;
    const auto& l = c.limits;
    if (!l.text_bytes || l.text_bytes > 65536 || !l.clipboard_bytes || l.clipboard_bytes > 65536 ||
        !l.popup_items || l.popup_items > 1024 || !l.popup_text_bytes || l.popup_text_bytes > 65536 ||
        !l.capture_rules || l.capture_rules > 64 || !l.held_keys || l.held_keys > 64 || !l.popup_depth || l.popup_depth > 8)
        return Status::limit_exceeded;
    return Status::ok;
}
Status negotiate(const Capabilities& c, Features required) noexcept {
    if (const auto result = validate_capabilities(c); result != Status::ok) return result;
    return (required & ~known_features) || (required & ~c.supported) ? Status::unsupported : Status::ok;
}
bool valid_text(const std::string& text) noexcept { return scalar_text(text); }
bool text_boundary(const std::string& text, std::size_t offset) noexcept { return scalar_text(text) && boundary_unchecked(text, offset); }
bool valid_range(const std::string& text, ByteRange range) noexcept {
    return range.begin <= range.end && scalar_text(text) && boundary_unchecked(text, range.begin) && boundary_unchecked(text, range.end);
}
Capture capture_key(const KeyCapturePolicy& policy, const KeyTransition& key) noexcept {
    if (!key_valid(key.key, key.code) || key.location > 3 || (key.modifiers & ~known_modifiers) ||
        (key.phase != KeyPhase::down && key.phase != KeyPhase::up) || !capture_valid(policy.fallback) || policy.rules.size() > 64)
        return Capture::pass;
    for (const auto& rule : policy.rules)
        if (!key_valid(rule.key, rule.code, true) || !capture_valid(rule.disposition) || (!rule.down && !rule.up) ||
            ((rule.required_modifiers | rule.forbidden_modifiers) & ~known_modifiers) ||
            (rule.required_modifiers & rule.forbidden_modifiers)) return Capture::pass;
    for (const auto& rule : policy.rules)
        if ((key.phase == KeyPhase::down ? rule.down : rule.up) && (rule.key.empty() || rule.key == key.key) &&
            (rule.code.empty() || rule.code == key.code) && (key.modifiers & rule.required_modifiers) == rule.required_modifiers &&
            !(key.modifiers & rule.forbidden_modifiers)) return rule.disposition;
    return policy.fallback;
}
bool AcceptedEvent::permits_cut() const noexcept {
    const auto* clipboard = std::get_if<ClipboardInput>(&event.input);
    return clipboard && clipboard->operation == ClipboardOperation::cut && clipboard->status == TransferStatus::accepted;
}

namespace detail {
struct MouseState {
    std::uint64_t token = 0, highest_token = 0;
    unsigned buttons = 0;
    double x = 0, y = 0;
    bool has_point = false;
};
struct Interaction {
    bool focused = false, active = true;
    std::optional<std::uint64_t> composition;
    std::uint64_t last_transaction = 0, highest_popup = 0, highest_offer = 0, last_transfer = 0;
    std::vector<KeyTransition> held_keys;
    MouseState mouse;
};
struct Stage {
    std::uint64_t token = 0, base_serial = 0;
    Presentation presentation;
    Interaction interaction;
    Revocation revoked;
};
struct PolicyState {
    Capabilities capabilities;
    std::uint64_t generation = 0, serial = 0, next_token = 0, last_sequence = 0;
    std::uint64_t highest_epoch = 0, highest_context = 0, highest_presentation = 0;
    bool closed = false;
    std::optional<Presentation> accepted;
    std::optional<Stage> staged;
    Interaction interaction;
};
} // namespace detail
namespace {
Revocation revoke(const detail::PolicyState& state, RevocationReason reason, bool all) {
    Revocation result;
    result.reason = reason;
    if (state.accepted) result.identity = state.accepted->identity;
    if (all) { result.composition = state.interaction.composition; result.held_keys = state.interaction.held_keys; }
    if (state.accepted && state.accepted->popup) result.popup = state.accepted->popup->token;
    return result;
}
void retire_mouse(detail::MouseState& mouse) noexcept {
    mouse.token = 0;
    mouse.buttons = 0;
}
void clear_mouse(detail::MouseState& mouse) noexcept {
    retire_mouse(mouse);
    mouse.x = mouse.y = 0;
    mouse.has_point = false;
    // The high water belongs to the Policy session, not its current context.
}
void clear_interaction(detail::Interaction& interaction) noexcept {
    if (interaction.composition) interaction.last_transaction = std::max(interaction.last_transaction, *interaction.composition);
    interaction.composition.reset();
    interaction.held_keys.clear();
    clear_mouse(interaction.mouse);
}
Status accept_mouse(const MouseTransition& input, const Capabilities& capabilities, detail::MouseState& mouse) noexcept {
    if (!has(capabilities, Feature::mouse_input) || input.version != mouse_input_version) return Status::unsupported;
    if (!std::isfinite(input.x) || !std::isfinite(input.y) || !std::isfinite(input.wheel_x) || !std::isfinite(input.wheel_y) ||
        std::abs(input.x) > coordinate_limit || std::abs(input.y) > coordinate_limit ||
        std::abs(input.wheel_x) > coordinate_limit || std::abs(input.wheel_y) > coordinate_limit ||
        input.button > 4 || input.buttons > 31 || input.clicks > 3 || (input.modifiers & ~known_modifiers) ||
        (input.context_origin != ContextOrigin::pointer && input.context_origin != ContextOrigin::keyboard)) return Status::invalid_value;
    if (input.phase != MousePhase::context && input.context_origin != ContextOrigin::pointer) return Status::invalid_value;
    if (input.phase != MousePhase::wheel && (input.wheel_x || input.wheel_y)) return Status::invalid_value;
    if (input.phase != MousePhase::down && input.phase != MousePhase::up && (input.button || input.clicks)) return Status::invalid_value;
    switch (input.phase) {
        case MousePhase::down: {
            if (!input.capture_token) return Status::invalid_value;
            const auto bit = mouse_button_bit(input.button);
            if ((mouse.buttons & bit) || input.buttons != (mouse.buttons | bit)) return Status::invalid_value;
            if (mouse.token) {
                if (input.capture_token != mouse.token) return Status::invalid_transaction;
            } else {
                if (input.capture_token <= mouse.highest_token) return Status::duplicate;
                mouse.token = input.capture_token;
                mouse.highest_token = input.capture_token;
            }
            mouse.buttons = input.buttons;
            break;
        }
        case MousePhase::up: {
            if (!input.capture_token) return Status::invalid_value;
            if (!mouse.token || input.capture_token != mouse.token) return Status::invalid_transaction;
            const auto bit = mouse_button_bit(input.button);
            if (!(mouse.buttons & bit) || input.buttons != (mouse.buttons & ~bit)) return Status::invalid_value;
            mouse.buttons = input.buttons;
            if (!mouse.buttons) retire_mouse(mouse);
            break;
        }
        case MousePhase::cancel:
            if (!input.capture_token || input.buttons || input.modifiers || input.x || input.y) return Status::invalid_value;
            if (!mouse.token || input.capture_token != mouse.token) return Status::invalid_transaction;
            // Canonical cancellation has no new point. Retire before the caller
            // dispatches owned work; its native authority retains the real point.
            retire_mouse(mouse);
            return Status::ok;
        case MousePhase::wheel:
            if ((!input.wheel_x && !input.wheel_y) ||
                static_cast<double>(static_cast<float>(input.wheel_x)) != input.wheel_x ||
                static_cast<double>(static_cast<float>(input.wheel_y)) != input.wheel_y) return Status::invalid_value;
            [[fallthrough]];
        case MousePhase::move: case MousePhase::context:
            if (input.capture_token != mouse.token || input.buttons != mouse.buttons) return Status::invalid_transaction;
            if (input.phase == MousePhase::context && input.context_origin == ContextOrigin::keyboard) {
                if (input.x || input.y || input.modifiers) return Status::invalid_value;
                // Keyboard context uses the engine focus/selection anchor. It
                // preserves capture and contributes no physical mouse position.
                return Status::ok;
            }
            break;
        default: return Status::invalid_value;
    }
    mouse.x = input.x;
    mouse.y = input.y;
    mouse.has_point = true;
    return Status::ok;
}
Status editor_ready(const Presentation& p, std::uint64_t revision, bool editable) noexcept {
    if (!p.editor || revision != p.editor->revision) return Status::stale_revision;
    return editable && !p.editor->editable ? Status::unavailable : Status::ok;
}
bool transfer_status_valid(TransferStatus s) noexcept {
    return s == TransferStatus::accepted || s == TransferStatus::unavailable || s == TransferStatus::cancelled || s == TransferStatus::error;
}
} // namespace

PreparedPresentation::PreparedPresentation() noexcept = default;
PreparedPresentation::PreparedPresentation(std::shared_ptr<detail::PolicyState> state, std::uint64_t token) noexcept
    : state_(std::move(state)), token_(token) {}
PreparedPresentation::~PreparedPresentation() { abandon(); }
PreparedPresentation::PreparedPresentation(PreparedPresentation&& other) noexcept : state_(std::move(other.state_)), token_(std::exchange(other.token_, 0)) {}
PreparedPresentation& PreparedPresentation::operator=(PreparedPresentation&& other) noexcept {
    if (this != &other) { abandon(); state_ = std::move(other.state_); token_ = std::exchange(other.token_, 0); }
    return *this;
}
PreparedPresentation::operator bool() const noexcept {
    return state_ && token_ && state_->staged && state_->staged->token == token_ &&
        state_->staged->base_serial == state_->serial && !state_->closed;
}
void PreparedPresentation::abandon() noexcept {
    if (state_ && state_->staged && state_->staged->token == token_) state_->staged.reset();
    state_.reset(); token_ = 0;
}

Policy::Policy(Capabilities capabilities, std::uint64_t generation) : state_(std::make_shared<detail::PolicyState>()) {
    if (!generation || validate_capabilities(capabilities) != Status::ok) throw std::invalid_argument("Invalid surface capability/generation");
    state_->capabilities = capabilities;
    state_->generation = generation;
}
Policy::~Policy() {
    state_->closed = true;
    state_->staged.reset(); state_->accepted.reset(); state_->interaction.held_keys.clear();
}
const Capabilities& Policy::capabilities() const noexcept { return state_->capabilities; }
const Presentation* Policy::accepted() const noexcept { return state_->accepted ? &*state_->accepted : nullptr; }
bool Policy::focused() const noexcept { return state_->interaction.focused; }
bool Policy::active() const noexcept { return state_->interaction.active; }
std::optional<std::uint64_t> Policy::composition() const noexcept { return state_->interaction.composition; }
std::uint64_t Policy::last_sequence() const noexcept { return state_->last_sequence; }

Preparation Policy::prepare(const Presentation& next) {
    auto& state = *state_;
    if (state.closed) return {Status::closed, {}};
    if (state.staged) return {Status::busy, {}};
    if (state.serial == maximum_id || state.next_token == maximum_id) return {Status::limit_exceeded, {}};
    if (const auto result = validate_presentation(next, state.capabilities, state.generation); result != Status::ok) return {result, {}};
    const auto& identity = next.identity;
    const auto* old = accepted();
    const bool same = old && same_context(identity, old->identity);
    if (identity.presentation_revision < state.highest_presentation || identity.epoch < state.highest_epoch ||
        (identity.epoch == state.highest_epoch && !same && identity.context <= state.highest_context)) return {Status::stale_identity, {}};
    if (identity.presentation_revision == state.highest_presentation && (!old || next != *old)) return {Status::stale_revision, {}};
    if (same && old->editor) {
        if (!next.editor) return {Status::stale_identity, {}};
        if (next.editor->revision < old->editor->revision) return {Status::stale_revision, {}};
        if (next.editor->revision == old->editor->revision && !same_editor_basis(*next.editor, *old->editor)) return {Status::stale_revision, {}};
    } else if (same && next.editor) return {Status::stale_identity, {}};

    detail::Stage stage;
    stage.presentation = next;
    stage.interaction = state.interaction;
    if (!same) {
        stage.revoked = revoke(state, RevocationReason::replaced, true);
        clear_interaction(stage.interaction);
        stage.interaction.last_transaction = 0;
        stage.interaction.last_transfer = 0;
        if (!old || old->identity.owner != identity.owner) stage.interaction.focused = false;
        if (identity.epoch > state.highest_epoch) { stage.interaction.highest_popup = 0; stage.interaction.highest_offer = 0; }
    }
    if (!next.available) {
        stage.revoked = revoke(state, RevocationReason::unavailable, true);
        clear_interaction(stage.interaction);
        stage.interaction.focused = false;
    }
    if (same && (old->bounds != next.bounds || old->clip != next.clip || old->display_scale != next.display_scale)) {
        if (state.interaction.mouse.token) stage.revoked.identity = old->identity;
        clear_mouse(stage.interaction.mouse);
    }
    if (next.editor && next.editor->composition_transaction) {
        if (!stage.interaction.composition || *stage.interaction.composition != next.editor->composition_transaction)
            return {Status::invalid_transaction, {}};
    } else if (stage.interaction.composition) {
        stage.revoked.identity = old->identity;
        stage.revoked.composition = stage.interaction.composition;
        stage.interaction.last_transaction = std::max(stage.interaction.last_transaction, *stage.interaction.composition);
        stage.interaction.composition.reset();
    }
    if (next.popup) {
        const auto& popup = *next.popup;
        if (same && old->popup && popup.token.instance == old->popup->token.instance) {
            if (popup.token.revision < old->popup->token.revision ||
                (popup.token.revision == old->popup->token.revision && popup != *old->popup)) return {Status::stale_revision, {}};
        } else if (popup.token.instance <= stage.interaction.highest_popup) return {Status::stale_identity, {}};
        if (!same || !old->popup || popup.token.instance != old->popup->token.instance) {
            // The popup owns ensuing key releases. Do not strand the key that
            // opened it in the engine's held set when those releases are local.
            if (old) stage.revoked.identity = old->identity;
            stage.revoked.held_keys = state.interaction.held_keys;
            stage.interaction.held_keys.clear();
            clear_mouse(stage.interaction.mouse);
        }
        stage.interaction.highest_popup = std::max(stage.interaction.highest_popup, popup.token.instance);
    }
    if (same && old->popup && (!next.popup || next.popup->token.instance != old->popup->token.instance)) {
        stage.revoked.identity = old->identity;
        stage.revoked.popup = old->popup->token;
    }
    if (next.clipboard) {
        if (same && old->clipboard && next.clipboard->id == old->clipboard->id) {
            if (*next.clipboard != *old->clipboard) return {Status::stale_revision, {}};
        } else if (next.clipboard->id <= stage.interaction.highest_offer) return {Status::stale_identity, {}};
        stage.interaction.highest_offer = std::max(stage.interaction.highest_offer, next.clipboard->id);
    }
    stage.base_serial = state.serial;
    stage.token = state.next_token + 1;
    state.staged.emplace(std::move(stage));
    state.next_token = state.staged->token;
    return {Status::ok, PreparedPresentation(state_, state.next_token)};
}
CommitResult Policy::commit(PreparedPresentation&& prepared, std::uint64_t published_revision) noexcept {
    static_assert(std::is_nothrow_move_constructible_v<detail::Stage>);
    static_assert(std::is_nothrow_move_assignable_v<Presentation>);
    static_assert(std::is_nothrow_move_assignable_v<detail::Interaction>);
    auto& state = *state_;
    Status status = Status::ok;
    if (state.closed) status = Status::closed;
    else if (prepared.state_ != state_ || !prepared.token_ || !state.staged || state.staged->token != prepared.token_) status = Status::stale_preparation;
    else if (state.staged->base_serial != state.serial) status = Status::stale_preparation;
    else if (published_revision != state.staged->presentation.identity.presentation_revision) status = Status::stale_revision;
    if (status != Status::ok) { prepared.abandon(); return {status, {}}; }
    auto stage = std::move(*state.staged);
    state.staged.reset();
    prepared.token_ = 0; prepared.state_.reset();
    const auto identity_epoch = stage.presentation.identity.epoch;
    if (identity_epoch > state.highest_epoch) state.highest_context = 0;
    state.highest_epoch = identity_epoch;
    state.highest_context = std::max(state.highest_context, stage.presentation.identity.context);
    state.highest_presentation = stage.presentation.identity.presentation_revision;
    state.accepted = std::move(stage.presentation);
    state.interaction = std::move(stage.interaction);
    ++state.serial;
    return {Status::ok, std::move(stage.revoked)};
}
CommitResult Policy::legacy_present(std::uint64_t published_revision) {
    auto& state = *state_;
    if (state.closed) return {Status::closed, {}};
    if (!published_revision) return {Status::invalid_value, {}};
    if (published_revision < state.highest_presentation) return {Status::stale_revision, {}};
    if (state.serial == maximum_id) return {Status::limit_exceeded, {}};
    auto revoked = revoke(state, RevocationReason::legacy_presentation, true);
    clear_interaction(state.interaction);
    state.interaction.focused = false;
    state.accepted.reset(); state.staged.reset();
    state.highest_presentation = published_revision;
    ++state.serial;
    return {Status::ok, std::move(revoked)};
}
Revocation Policy::close() {
    auto& state = *state_;
    if (state.closed) return {};
    auto revoked = revoke(state, RevocationReason::closed, true);
    state.closed = true;
    state.staged.reset(); state.accepted.reset();
    clear_interaction(state.interaction);
    state.interaction.focused = false;
    state.interaction.active = false;
    return revoked;
}

AcceptResult Policy::accept(Event event) {
    auto& state = *state_;
    if (state.closed) return {Status::closed, {}};
    if (!state.accepted || event.identity != state.accepted->identity) return {Status::stale_identity, {}};
    if (!event.sequence) return {Status::invalid_value, {}};
    if (event.sequence <= state.last_sequence) return {Status::duplicate, {}};
    if (state.serial == maximum_id) return {Status::limit_exceeded, {}};
    const auto& p = *state.accepted;
    const auto& capabilities = state.capabilities;
    auto next = state.interaction;
    AcceptedEvent result{std::move(event), Capture::pass, {}};
    bool consume_popup = false, consume_offer = false;
    const auto status = std::visit([&](const auto& input) -> Status {
        using T = std::decay_t<decltype(input)>;
        if constexpr (std::is_same_v<T, FocusChange>) {
            if (!has(capabilities, Feature::focus)) return Status::unsupported;
            switch (input.cause) {
                case FocusCause::owned_popup: return p.popup ? Status::ok : Status::stale_identity;
                case FocusCause::owned_service:
                    result.revoked = revoke(state, RevocationReason::service, true);
                    clear_interaction(next); consume_popup = bool(p.popup); return Status::ok;
                case FocusCause::direct: case FocusCause::external: break;
                default: return Status::invalid_value;
            }
            next.focused = input.focused && p.available;
            next.active = input.active;
            if (!next.focused || !next.active) {
                result.revoked = revoke(state, RevocationReason::focus_loss, true);
                clear_interaction(next); consume_popup = bool(p.popup);
            }
            return Status::ok;
        } else {
            if (!p.available) return Status::unavailable;
            if constexpr (!std::is_same_v<T, PointerTransition> && !std::is_same_v<T, MouseTransition>) {
                if (!next.focused || !next.active) return Status::not_focused;
            } else if (!next.active) return Status::not_focused;
            if constexpr (!std::is_same_v<T, PopupReply>) if (p.popup) return Status::popup_active;
            if constexpr (std::is_same_v<T, KeyTransition>) {
                if (!has(capabilities, Feature::raw_keys)) return Status::unsupported;
                if (!key_valid(input.key, input.code) || input.location > 3 || (input.modifiers & ~known_modifiers) ||
                    (input.phase != KeyPhase::down && input.phase != KeyPhase::up) || (input.phase == KeyPhase::up && input.repeat)) return Status::invalid_value;
                const auto held = std::find_if(next.held_keys.begin(), next.held_keys.end(), [&](const auto& key) { return same_key(key, input); });
                if (input.phase == KeyPhase::up) {
                    if (held == next.held_keys.end()) return Status::duplicate;
                    next.held_keys.erase(held);
                } else if (input.repeat) {
                    if (held == next.held_keys.end()) return Status::invalid_transaction;
                } else {
                    if (held != next.held_keys.end()) return Status::duplicate;
                    if (next.held_keys.size() == capabilities.limits.held_keys) return Status::limit_exceeded;
                    next.held_keys.push_back(input);
                }
                result.capture = capture_key(p.keys, input);
                return Status::ok;
            } else if constexpr (std::is_same_v<T, TextCommit>) {
                if (!has(capabilities, Feature::committed_text)) return Status::unsupported;
                if (const auto ready = editor_ready(p, input.editor_revision, true); ready != Status::ok) return ready;
                if (input.text.size() > capabilities.limits.text_bytes) return Status::limit_exceeded;
                if (!input.transaction || !valid_text(input.text)) return Status::invalid_value;
                if (next.composition) return Status::invalid_transaction;
                if (input.transaction <= next.last_transaction) return Status::duplicate;
                if (input.replacement && !valid_range(p.editor->surrounding, *input.replacement)) return Status::invalid_value;
                const auto replaced = input.replacement.value_or(p.editor->selection);
                if (input.text.empty() && replaced.begin == replaced.end) return Status::invalid_value;
                next.last_transaction = input.transaction;
                return Status::ok;
            } else if constexpr (std::is_same_v<T, CompositionEdit>) {
                if (!has(capabilities, Feature::composition)) return Status::unsupported;
                if (const auto ready = editor_ready(p, input.editor_revision, true); ready != Status::ok) return ready;
                if (input.text.size() > capabilities.limits.text_bytes) return Status::limit_exceeded;
                if (!input.transaction || !valid_text(input.text) || !valid_range(input.text, input.selection)) return Status::invalid_value;
                switch (input.operation) {
                    case CompositionOperation::begin:
                        if (next.composition) return Status::invalid_transaction;
                        if (input.transaction <= next.last_transaction) return Status::duplicate;
                        if (input.replacement && !valid_range(p.editor->surrounding, *input.replacement)) return Status::invalid_value;
                        next.composition = input.transaction; return Status::ok;
                    case CompositionOperation::update: case CompositionOperation::commit: case CompositionOperation::cancel:
                        if (input.replacement) return Status::invalid_value;
                        if (!next.composition || *next.composition != input.transaction)
                            return input.transaction <= next.last_transaction ? Status::duplicate : Status::invalid_transaction;
                        if (input.operation == CompositionOperation::cancel && (!input.text.empty() || input.selection != ByteRange{})) return Status::invalid_value;
                        if (input.operation != CompositionOperation::update) {
                            next.last_transaction = input.transaction; next.composition.reset();
                        }
                        return Status::ok;
                }
                return Status::invalid_value;
            } else if constexpr (std::is_same_v<T, SelectionChange>) {
                if (!has(capabilities, Feature::selection)) return Status::unsupported;
                if (const auto ready = editor_ready(p, input.editor_revision, false); ready != Status::ok) return ready;
                if (!valid_range(p.editor->surrounding, input.selection)) return Status::invalid_value;
                return Status::ok;
            } else if constexpr (std::is_same_v<T, PointerTransition>) {
                if (!has(capabilities, Feature::raw_pointer)) return Status::unsupported;
                if (!std::isfinite(input.x) || !std::isfinite(input.y) || !std::isfinite(input.wheel_x) || !std::isfinite(input.wheel_y) ||
                    std::abs(input.x) > coordinate_limit || std::abs(input.y) > coordinate_limit ||
                    std::abs(input.wheel_x) > coordinate_limit || std::abs(input.wheel_y) > coordinate_limit ||
                    input.button > 4 || input.buttons > 31 || !input.clicks || input.clicks > 3 || (input.modifiers & ~known_modifiers)) return Status::invalid_value;
                switch (input.phase) {
                    case PointerPhase::down: case PointerPhase::up: case PointerPhase::cancel:
                        if (!input.pointer) return Status::invalid_value;
                        break;
                    case PointerPhase::move: case PointerPhase::context: break;
                    case PointerPhase::wheel:
                        if (!input.wheel_x && !input.wheel_y) return Status::invalid_value;
                        break;
                    default: return Status::invalid_value;
                }
                if (input.phase != PointerPhase::wheel && (input.wheel_x || input.wheel_y)) return Status::invalid_value;
                // Physical capture/hit testing remains the existing adapter's
                // responsibility; this companion guards identity and values.
                return Status::ok;
            } else if constexpr (std::is_same_v<T, MouseTransition>) {
                return accept_mouse(input, capabilities, next.mouse);
            } else if constexpr (std::is_same_v<T, ClipboardInput>) {
                if (!has(capabilities, Feature::clipboard_text) && !has(capabilities, Feature::clipboard_html)) return Status::unsupported;
                if (!input.transfer || !transfer_status_valid(input.status)) return Status::invalid_value;
                if (input.transfer <= next.last_transfer) return Status::duplicate;
                if (input.operation != ClipboardOperation::copy && input.operation != ClipboardOperation::cut && input.operation != ClipboardOperation::paste) return Status::invalid_value;
                if (const auto ready = editor_ready(p, input.editor_revision, input.operation != ClipboardOperation::copy); ready != Status::ok) return ready;
                if (input.operation == ClipboardOperation::paste) {
                    if (input.offer) return Status::invalid_value;
                    if (const auto valid = validate_formats(input.formats, capabilities, input.status != TransferStatus::accepted); valid != Status::ok) return valid;
                } else {
                    if (!input.formats.empty() || !p.clipboard || input.offer != p.clipboard->id || p.clipboard->editor_revision != input.editor_revision) return Status::stale_revision;
                    consume_offer = input.operation == ClipboardOperation::cut && input.status == TransferStatus::accepted;
                }
                next.last_transfer = input.transfer;
                return Status::ok;
            } else if constexpr (std::is_same_v<T, PopupReply>) {
                if (!p.popup || input.token != p.popup->token) return Status::stale_identity;
                if (input.operation == PopupOperation::accept) {
                    if (!input.item || !actionable_item(p.popup->items, *input.item)) return Status::unavailable;
                } else if (input.operation != PopupOperation::cancel || input.item) return Status::invalid_value;
                consume_popup = true;
                return Status::ok;
            }
        }
        return Status::invalid_value;
    }, result.event.input);
    if (status != Status::ok) return {status, {}};
    state.interaction = std::move(next);
    if (consume_popup) state.accepted->popup.reset();
    if (consume_offer) state.accepted->clipboard.reset();
    state.last_sequence = result.event.sequence;
    ++state.serial;
    return {Status::ok, std::move(result)};
}
} // namespace foundation::gui_surface
