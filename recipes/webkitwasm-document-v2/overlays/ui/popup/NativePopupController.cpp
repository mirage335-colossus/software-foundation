// SPDX-License-Identifier: CC0-1.0
#include "NativePopupController.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>

namespace bib::provider_candidate::native_popup {
namespace {
bool point(double x, double y) noexcept {
    return std::isfinite(x) && std::isfinite(y) && std::abs(x) <= 1000000 && std::abs(y) <= 1000000;
}
bool stateValid(PointerState s) noexcept {
    return s.buttons <= 31 && ((s.buttons == 0) == (s.capture_token == 0))
        && (s.context || (!s.buttons && !s.capture_token));
}
std::uint32_t buttonBit(std::uint32_t button) noexcept {
    constexpr std::uint32_t bits[]{1, 4, 2, 8, 16};
    return button < 5 ? bits[button] : 0;
}
bool pointerTransition(const LifecycleKey& key, const PointerPacket& p,
    PointerState previous, PointerState next) noexcept {
    const auto phase = static_cast<std::uint32_t>(p.phase);
    if (!key.valid() || !stateValid(previous) || !stateValid(next)
        || previous.context != key.input_context || next.context != key.input_context
        || phase > 5 || p.button > 4 || p.buttons > 31 || p.modifiers > 31
        || p.context_origin > 1 || !point(p.x, p.y) || !point(p.wheel_x, p.wheel_y)
        || (phase != 5 && p.context_origin) || (phase != 3 && (p.wheel_x || p.wheel_y))) return false;
    if (phase != 1 && phase != 2 && p.button) return false;
    if (phase == 3 && !p.wheel_x && !p.wheel_y) return false;
    if (phase == 5 && p.context_origin == 1 && (p.x || p.y || p.modifiers)) return false;
    const auto bit = buttonBit(p.button);
    auto expected = previous;
    if (phase == 1) {
        if (!p.capture_token || (previous.buttons & bit) || p.buttons != (previous.buttons | bit)) return false;
        if (previous.capture_token && p.capture_token != previous.capture_token) return false;
        expected.capture_token = p.capture_token;
        expected.buttons = p.buttons;
    } else if (phase == 2) {
        if (!previous.capture_token || p.capture_token != previous.capture_token
            || !(previous.buttons & bit) || p.buttons != (previous.buttons & ~bit)) return false;
        expected.buttons = p.buttons;
        if (!p.buttons) expected.capture_token = 0;
    } else if (phase == 4) {
        if (!previous.capture_token || p.capture_token != previous.capture_token
            || p.buttons || p.modifiers || p.x || p.y) return false;
        expected.capture_token = 0; expected.buttons = 0;
    } else if (p.capture_token != previous.capture_token || p.buttons != previous.buttons) return false;
    return next == expected;
}
bool keyValid(const KeyPacket& p) noexcept {
    return p.phase <= 1 && p.location <= 3 && p.modifiers <= 31 && !(p.phase == 1 && p.repeat)
        && p.code.size() <= 64 && std::all_of(p.code.begin(), p.code.end(), [](unsigned char c) { return c >= 0x21 && c <= 0x7e; });
}
} // namespace

bool LifecycleKey::valid() const noexcept {
    return runtime && worker && application && document && service && resource && input_context;
}
NativePopupController::NativePopupController(SerialLimits limits) noexcept : serial_limits_(limits) {
    faulted_ = !limits.epoch || !limits.revision;
}
Result NativePopupController::result(Route route, Status status) const noexcept {
    Result r; r.route = route; r.status = status; r.token = token_; return r;
}
void NativePopupController::closeInto(Result& r) noexcept {
    if (!active()) return;
    r.closed = token_; r.damage = true;
    token_ = {}; key_ = {}; row_count_ = 0; highlight_ = armed_row_ = 0;
    opening_group_ = opening_moved_ = false;
    r.token = {};
}
Result NativePopupController::faultInto(Result r) noexcept {
    faulted_ = true; closeInto(r); r.status = Status::faulted; r.route = Route::fault; return r;
}
Result NativePopupController::fail() noexcept { return faultInto(result()); }

bool NativePopupController::validRows(std::span<const Row> rows) const noexcept {
    if (rows.empty() || rows.size() > maximum_rows) return false;
    for (std::size_t i = 0; i < rows.size(); ++i) {
        if (!rows[i].id || rows[i].list_index > 0x7fffffffu || (rows[i].label && rows[i].separator)
            || (i && rows[i - 1].list_index >= rows[i].list_index)) return false;
        for (std::size_t j = 0; j < i; ++j) if (rows[j].id == rows[i].id) return false;
    }
    return true;
}
const Row* NativePopupController::row(std::uint64_t id) const noexcept {
    if (!id) return nullptr;
    for (std::size_t i = 0; i < row_count_; ++i) if (rows_[i].id == id) return &rows_[i];
    return nullptr;
}
Result NativePopupController::open(const LifecycleKey& key, std::span<const Row> rows,
    std::uint64_t selected, std::uint32_t page_rows) noexcept {
    if (faulted_) return result(Route::fault, Status::faulted);
    auto r = result(Route::consumed);
    if (!key.valid() || !validRows(rows) || !page_rows || page_rows > maximum_rows) {
        closeInto(r); r.status = Status::declined; return r;
    }
    if (last_epoch_ == serial_limits_.epoch) return faultInto(r);
    const auto accepted_key = key; // activeKey() may be the caller's argument.
    closeInto(r);
    token_ = {++last_epoch_, 1}; key_ = accepted_key; row_count_ = rows.size(); page_rows_ = page_rows;
    // Indexed forward assignment also supports rows()/rows().subspan() input.
    for (std::size_t i = 0; i < rows.size(); ++i) rows_[i] = rows[i];
    const auto* selected_row = row(selected);
    highlight_ = selected_row && selected_row->selectable() ? selected : 0;
    if (!highlight_) for (const auto& candidate : this->rows()) if (candidate.selectable()) { highlight_ = candidate.id; break; }
    r.token = token_; r.damage = true; return r;
}
Result NativePopupController::update(const LifecycleKey& key, PopupToken expected, std::span<const Row> rows) noexcept {
    if (faulted_) return result(Route::fault, Status::faulted);
    auto r = result(Route::consumed);
    if (!active() || key != key_ || expected != token_) return result(Route::page, Status::stale);
    if (!validRows(rows)) { closeInto(r); r.status = Status::declined; return r; }
    if (token_.revision == serial_limits_.revision) return faultInto(r);
    ++token_.revision;
    for (std::size_t i = 0; i < rows.size(); ++i) rows_[i] = rows[i];
    row_count_ = rows.size();
    const auto* old_highlight = row(highlight_);
    if (!old_highlight || !old_highlight->selectable()) {
        highlight_ = 0;
        for (const auto& candidate : this->rows()) if (candidate.selectable()) { highlight_ = candidate.id; break; }
    }
    armed_row_ = 0; opening_group_ = opening_moved_ = false;
    r.token = token_; r.damage = true; return r;
}
Result NativePopupController::close(PopupToken expected) noexcept {
    if (faulted_) return result(Route::fault, Status::faulted);
    if (!active() || expected != token_) return result(Route::page, Status::stale);
    auto r = result(Route::consumed); closeInto(r); return r;
}
bool NativePopupController::currentOrigin(const LifecycleKey& key, PopupToken token) const noexcept {
    return active() && key == key_ && token == token_;
}
void NativePopupController::clearDebts(const LifecycleKey& key) noexcept {
    if (pointer_debt_.present && pointer_debt_.key == key) pointer_debt_ = {};
    for (auto& debt : key_debts_) if (debt.present && debt.key == key) { debt = {}; --key_debt_count_; }
}
Result NativePopupController::retireAuthority(const LifecycleKey& retired) noexcept {
    auto r = result(faulted_ ? Route::fault : Route::consumed, faulted_ ? Status::faulted : Status::ok);
    if (!retired.valid()) { if (!faulted_) r.status = Status::invalid; return r; }
    clearDebts(retired);
    if (active() && key_ == retired) closeInto(r);
    return r;
}
Result NativePopupController::observeFocus(const LifecycleKey& key, PointerState previous,
    PointerState next, bool focused, bool active) noexcept {
    if (faulted_) return result(Route::fault, Status::faulted);
    auto r = result(Route::consumed);
    if (!key.valid() || !stateValid(previous) || !stateValid(next) || previous.context != key.input_context)
        return faultInto(r);
    if (!next.context) {
        if (focused || active || next.capture_token || next.buttons) return faultInto(r);
        return retireAuthority(key);
    }
    if (next.context != key.input_context) return faultInto(r);
    if (!focused || !active) {
        if (next.capture_token || next.buttons) return faultInto(r);
        if (pointer_debt_.present && pointer_debt_.key == key) {
            if (pointer_debt_.state != previous) return faultInto(r);
            pointer_debt_ = {};
        }
        if (this->active() && key_ == key) closeInto(r);
    } else if (next != previous) return faultInto(r);
    return r;
}
Result NativePopupController::adoptOpeningPointer(const LifecycleKey& key, PopupToken expected,
    PointerState committed, double x, double y) noexcept {
    if (faulted_) return result(Route::fault, Status::faulted);
    if (!currentOrigin(key, expected)) return result(Route::consumed, Status::stale);
    auto r = result(Route::consumed);
    if (!stateValid(committed) || committed.context != key.input_context || !committed.capture_token
        || !committed.buttons || !point(x, y)) return faultInto(r);
    if (pointer_debt_.present) {
        if (pointer_debt_.key == key && pointer_debt_.origin == expected && pointer_debt_.state == committed) return r;
        return faultInto(r);
    }
    pointer_debt_ = {true, key, expected, committed};
    opening_group_ = true; opening_moved_ = false; opening_x_ = x; opening_y_ = y; armed_row_ = 0;
    r.handoff = true; return r;
}
Result NativePopupController::adoptOpeningKey(const LifecycleKey& key, PopupToken expected,
    const KeyPacket& p) noexcept {
    if (faulted_) return result(Route::fault, Status::faulted);
    if (!currentOrigin(key, expected)) return result(Route::consumed, Status::stale);
    auto r = result(Route::consumed);
    if (!keyValid(p) || p.phase != 0) return faultInto(r);
    r.observe_modifiers = true; r.modifiers = p.modifiers;
    if (!p.qualified_stable_code || !standardCode(p.code) || p.code == "Tab") {
        closeInto(r); return r; // The opener was already dispatched: never page-route it twice.
    }
    const auto debt = findKeyDebt(key, p);
    if (debt != maximum_key_debts) {
        if (key_debts_[debt].origin != expected) return faultInto(r);
        return r; // Idempotent receipt adoption, never repeats the key action.
    }
    if (!addKeyDebt(key, p)) return faultInto(r);
    return r;
}

void NativePopupController::choose(Result& r, std::uint64_t id) noexcept {
    const auto* selected = row(id);
    if (selected && selected->selectable()) r.choice = {token_, selected->id, selected->list_index};
    closeInto(r);
}
void NativePopupController::endpoint(bool last, Result& r) noexcept {
    std::uint64_t next{};
    for (std::size_t i = 0; i < row_count_; ++i) {
        const auto& candidate = rows_[last ? row_count_ - i - 1 : i];
        if (candidate.selectable()) { next = candidate.id; break; }
    }
    if (next != highlight_) { highlight_ = next; r.damage = true; }
}
void NativePopupController::navigate(int direction, std::uint32_t count, Result& r) noexcept {
    if (!highlight_) { endpoint(direction < 0, r); return; }
    std::size_t index{};
    for (; index < row_count_; ++index) if (rows_[index].id == highlight_) break;
    if (index == row_count_) { endpoint(direction < 0, r); return; }
    for (std::uint32_t step = 0; step < count; ++step) {
        auto next = index;
        bool found{};
        while (direction > 0 ? next + 1 < row_count_ : next > 0) {
            direction > 0 ? ++next : --next;
            if (rows_[next].selectable()) { found = true; break; }
        }
        if (!found) break;
        index = next;
    }
    if (highlight_ != rows_[index].id) { highlight_ = rows_[index].id; r.damage = true; }
}

Result NativePopupController::pointer(const LifecycleKey& key, const PointerPacket& p,
    PointerState previous, PointerState next, std::uint64_t hit) noexcept {
    if (faulted_) return result(Route::fault, Status::faulted);
    auto r = result();
    if (!pointerTransition(key, p, previous, next)) return faultInto(r);
    const bool matching = pointer_debt_.present && pointer_debt_.key == key
        && pointer_debt_.state == previous && p.capture_token == previous.capture_token;
    if (pointer_debt_.present && pointer_debt_.key == key && !matching) return faultInto(r);
    bool apply{};
    if (matching) {
        r.route = Route::consumed;
        apply = currentOrigin(key, pointer_debt_.origin);
        pointer_debt_.state = next;
    } else if (active() && key == key_) {
        r.route = Route::consumed; apply = true;
        // A previously-held page group must have been explicitly handed off at
        // popup open. Swallowing its release without native cancellation is unsafe.
        if (previous.capture_token) return faultInto(r);
        if (p.phase == PointerPhase::down) {
            if (pointer_debt_.present) return faultInto(r);
            pointer_debt_ = {true, key, token_, next};
            opening_group_ = opening_moved_ = false;
        }
    }
    if (apply) {
        const auto* hit_row = row(hit);
        const bool eligible = hit_row && hit_row->selectable();
        switch (p.phase) {
        case PointerPhase::move:
            if (eligible && highlight_ != hit) { highlight_ = hit; r.damage = true; }
            if (opening_group_ && (p.x != opening_x_ || p.y != opening_y_)) opening_moved_ = true;
            if (next.buttons & 1u) armed_row_ = eligible && (!opening_group_ || opening_moved_) ? hit : 0;
            break;
        case PointerPhase::down:
            if (!hit_row) closeInto(r);
            else if (p.button == 0) {
                armed_row_ = eligible ? hit : 0;
                if (eligible && highlight_ != hit) { highlight_ = hit; r.damage = true; }
            }
            break;
        case PointerPhase::up:
            if (p.button == 0) {
                if (eligible && armed_row_ == hit) choose(r, hit);
                armed_row_ = 0;
            }
            break;
        case PointerPhase::wheel:
            armed_row_ = 0; r.wheel = true; r.wheel_x = p.wheel_x; r.wheel_y = p.wheel_y;
            break;
        case PointerPhase::cancel:
            closeInto(r); break;
        case PointerPhase::context:
            break; // Modal original intent only; never manufacture cancellation.
        }
    }
    if (matching && !next.capture_token) {
        pointer_debt_ = {}; armed_row_ = 0; opening_group_ = opening_moved_ = false;
    }
    r.token = token_; return r;
}

bool NativePopupController::standardCode(std::string_view code) noexcept {
    if (code.size() == 4 && code.substr(0, 3) == "Key" && code[3] >= 'A' && code[3] <= 'Z') return true;
    if (code.size() == 6 && code.substr(0, 5) == "Digit" && code[5] >= '0' && code[5] <= '9') return true;
    if (code.size() == 7 && code.substr(0, 6) == "Numpad" && code[6] >= '0' && code[6] <= '9') return true;
    if (code.size() >= 2 && code.size() <= 3 && code[0] == 'F' && code[1] >= '1' && code[1] <= '9') {
        unsigned number = static_cast<unsigned>(code[1] - '0');
        if (code.size() == 3) {
            if (code[2] < '0' || code[2] > '9') return false;
            number = number * 10 + static_cast<unsigned>(code[2] - '0');
        }
        if (number <= 24) return true;
    }
    constexpr std::string_view codes[]{"ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End", "PageUp", "PageDown",
        "Enter", "NumpadEnter", "Space", "Escape", "Tab", "Backspace", "Delete", "Insert", "CapsLock", "NumLock", "ScrollLock",
        "Pause", "PrintScreen", "ContextMenu", "ShiftLeft", "ShiftRight", "ControlLeft", "ControlRight", "AltLeft", "AltRight",
        "MetaLeft", "MetaRight", "Backquote", "Minus", "Equal", "BracketLeft", "BracketRight", "Backslash", "Semicolon", "Quote",
        "Comma", "Period", "Slash", "IntlBackslash", "IntlRo", "IntlYen", "NumpadAdd", "NumpadSubtract", "NumpadMultiply",
        "NumpadDivide", "NumpadDecimal", "NumpadEqual", "NumpadComma", "NumpadParenLeft", "NumpadParenRight", "NumpadBackspace",
        "NumpadClear", "NumpadClearEntry"};
    return std::find(std::begin(codes), std::end(codes), code) != std::end(codes);
}
std::size_t NativePopupController::findKeyDebt(const LifecycleKey& key, const KeyPacket& p) const noexcept {
    for (std::size_t i = 0; i < key_debts_.size(); ++i) {
        const auto& debt = key_debts_[i];
        if (debt.present && debt.key == key && debt.location == p.location && debt.length == p.code.size()
            && std::equal(p.code.begin(), p.code.end(), debt.code.begin())) return i;
    }
    return maximum_key_debts;
}
bool NativePopupController::addKeyDebt(const LifecycleKey& key, const KeyPacket& p) noexcept {
    if (key_debt_count_ == maximum_key_debts) return false;
    for (auto& debt : key_debts_) if (!debt.present) {
        debt.present = true; debt.key = key; debt.origin = token_; debt.location = p.location;
        debt.length = static_cast<std::uint8_t>(p.code.size());
        std::copy(p.code.begin(), p.code.end(), debt.code.begin()); ++key_debt_count_; return true;
    }
    return false;
}
void NativePopupController::processKey(const KeyPacket& p, Result& r) noexcept {
    if (p.code == "ArrowDown" || p.code == "ArrowRight") navigate(1, 1, r);
    else if (p.code == "ArrowUp" || p.code == "ArrowLeft") navigate(-1, 1, r);
    else if (p.code == "PageDown") navigate(1, page_rows_, r);
    else if (p.code == "PageUp") navigate(-1, page_rows_, r);
    else if (p.code == "Home") endpoint(false, r);
    else if (p.code == "End") endpoint(true, r);
    else if (p.code == "Escape") closeInto(r);
    else if (p.code == "Enter" || p.code == "NumpadEnter" || p.code == "Space") choose(r, highlight_);
}
Result NativePopupController::key(const LifecycleKey& key, const KeyPacket& p) noexcept {
    if (faulted_) return result(Route::fault, Status::faulted);
    auto r = result();
    if (!key.valid() || !keyValid(p)) return faultInto(r);
    r.observe_modifiers = true; r.modifiers = p.modifiers;
    const auto debt = findKeyDebt(key, p);
    if (debt != maximum_key_debts) {
        r.route = Route::consumed;
        if (p.phase == 1) { key_debts_[debt] = {}; --key_debt_count_; }
        else if (currentOrigin(key, key_debts_[debt].origin)) processKey(p, r);
    } else if (!p.phase && active() && key == key_) {
        if (!p.qualified_stable_code || !standardCode(p.code) || p.code == "Tab") {
            closeInto(r); // Dispatch this ORIGINAL event once, with fresh owner fence.
        } else {
            r.route = Route::consumed;
            if (!addKeyDebt(key, p)) return faultInto(r);
            processKey(p, r);
        }
    }
    r.token = token_; return r;
}
} // namespace bib::provider_candidate::native_popup
