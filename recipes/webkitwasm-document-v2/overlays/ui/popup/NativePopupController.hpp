// SPDX-License-Identifier: CC0-1.0
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <span>
#include <string_view>

namespace bib::provider_candidate::native_popup {

struct LifecycleKey {
    std::uint64_t runtime{}, worker{}, application{}, document{}, service{}, resource{}, input_context{};
    bool operator==(const LifecycleKey&) const = default;
    bool valid() const noexcept;
};
struct PopupToken {
    std::uint64_t epoch{}, revision{};
    bool operator==(const PopupToken&) const = default;
    explicit operator bool() const noexcept { return epoch && revision; }
};
struct Row {
    std::uint64_t id{};
    std::uint32_t list_index{};
    bool enabled{}, label{}, separator{}, hidden{};
    bool selectable() const noexcept { return enabled && !label && !separator && !hidden; }
};
struct PointerState {
    std::uint64_t context{}, capture_token{};
    std::uint32_t buttons{};
    bool operator==(const PointerState&) const = default;
};
enum class PointerPhase : std::uint32_t { move, down, up, wheel, cancel, context };
struct PointerPacket {
    PointerPhase phase{};
    std::uint64_t capture_token{};
    std::uint32_t button{}, buttons{}, modifiers{}, context_origin{};
    double x{}, y{}, wheel_x{}, wheel_y{};
};
struct KeyPacket {
    // phase0=down, phase1=up. Code is borrowed only for this synchronous call.
    std::uint32_t phase{}, location{}, modifiers{};
    bool repeat{};
    std::string_view code;
    // Admitted normalized adapter code identity, independently of this closed
    // whitelist. This does not claim actual OS/release qualification has passed.
    bool qualified_stable_code{};
};
enum class Route { page, consumed, fault };
enum class Status { ok, declined, stale, invalid, faulted };
struct Choice {
    PopupToken token{};
    std::uint64_t row_id{};
    std::uint32_t list_index{};
    explicit operator bool() const noexcept { return row_id != 0; }
};
struct Result {
    Status status{Status::ok};
    Route route{Route::page};
    PopupToken token{};       // Active token after this transition, if any.
    PopupToken closed{};      // Notify only this old token; no callback is made here.
    Choice choice{};          // Revalidate DOM/weak row, hide, then callback once.
    bool damage{}, handoff{}, observe_modifiers{}; // Every admitted key conveys its original mask, even page routes.
    std::uint32_t modifiers{};
    bool wheel{};             // Apply only to the token returned in token.
    double wheel_x{}, wheel_y{};
};
struct SerialLimits {
    // Production uses the defaults. Smaller bounds permit finite exhaustion tests.
    std::uint64_t epoch{std::numeric_limits<std::uint64_t>::max()};
    std::uint64_t revision{std::numeric_limits<std::uint64_t>::max()};
};
struct PointerDebt {
    bool present{};
    LifecycleKey key{};
    PopupToken origin{};
    PointerState state{};
};

// Pure, allocation-free C++20 policy. No callbacks, threads, DOM/Host/GUI objects
// or public protocol. Caller enforces exact owner and supplies only already
// accepted/committed physical packets plus their original previous/next states.
// Close and snapshot update NEVER retire input debt. Fault is sticky for the
// entire object lifetime; retirement may clear metadata but never restore service.
class NativePopupController final {
public:
    static constexpr std::size_t maximum_rows = 2048;
    static constexpr std::size_t maximum_key_debts = 128;

    explicit NativePopupController(SerialLimits = {}) noexcept;
    Result open(const LifecycleKey&, std::span<const Row>, std::uint64_t selected_row = 0,
        std::uint32_t page_rows = 8) noexcept;
    Result update(const LifecycleKey&, PopupToken expected, std::span<const Row>) noexcept;
    Result close(PopupToken expected) noexcept;
    Result fail() noexcept; // Owner allocation/callback/identity uncertainty.

    // AFTER actual portable authority retirement. Metadata only, even if faulted.
    Result retireAuthority(const LifecycleKey& retired) noexcept;
    // AFTER a real committed Focus action0/2; next.context0 means full retirement.
    // Blur/inactivation must have next capture/buttons0; key debts then survive.
    Result observeFocus(const LifecycleKey&, PointerState previous, PointerState next,
        bool focused, bool active) noexcept;

    // After the original opening mouse press returns, BEFORE native cancellation.
    // Supplies committed POST-PRESS state, not Prepared.previous. Handoff is an
    // intent only: owner fences actual cancellation/reentry and never resets the
    // portable state. The first stationary release cannot choose a row. Stale
    // adoption is consumed too: the opening event was already dispatched once.
    Result adoptOpeningPointer(const LifecycleKey&, PopupToken expected,
        PointerState committed, double x, double y) noexcept;
    // Original opening keydown was ALREADY delivered to EventHandler once. Adopt
    // only its stable qualified identity after that call. Ambiguity closes the
    // new popup with consumed routing, never a redispatch of the original event.
    // Stale adoption likewise returns consumed+stale without touching a successor.
    Result adoptOpeningKey(const LifecycleKey&, PopupToken expected, const KeyPacket&) noexcept;

    // hit_row is the current owned-snapshot row ID, or0 outside/non-row. It is not
    // a display index. Old debt wins over a reentrant successor popup.
    Result pointer(const LifecycleKey&, const PointerPacket&, PointerState previous,
        PointerState next, std::uint64_t hit_row = 0) noexcept;
    Result key(const LifecycleKey&, const KeyPacket&) noexcept;

    bool active() const noexcept { return static_cast<bool>(token_); }
    bool faulted() const noexcept { return faulted_; }
    PopupToken token() const noexcept { return token_; }
    const LifecycleKey& activeKey() const noexcept { return key_; }
    std::span<const Row> rows() const noexcept { return {rows_.data(), row_count_}; }
    std::uint64_t highlightedRow() const noexcept { return highlight_; }
    std::size_t keyDebtCount() const noexcept { return key_debt_count_; }
    PointerDebt pointerDebt() const noexcept { return pointer_debt_; }
    static bool standardCode(std::string_view) noexcept;

private:
    struct KeyDebt {
        bool present{};
        LifecycleKey key{};
        PopupToken origin{};
        std::uint32_t location{};
        std::uint8_t length{};
        std::array<char, 64> code{};
    };
    Result result(Route = Route::page, Status = Status::ok) const noexcept;
    void closeInto(Result&) noexcept;
    Result faultInto(Result) noexcept;
    bool validRows(std::span<const Row>) const noexcept;
    const Row* row(std::uint64_t) const noexcept;
    void choose(Result&, std::uint64_t) noexcept;
    void navigate(int direction, std::uint32_t count, Result&) noexcept;
    void endpoint(bool last, Result&) noexcept;
    bool currentOrigin(const LifecycleKey&, PopupToken) const noexcept;
    void clearDebts(const LifecycleKey&) noexcept;
    std::size_t findKeyDebt(const LifecycleKey&, const KeyPacket&) const noexcept;
    bool addKeyDebt(const LifecycleKey&, const KeyPacket&) noexcept;
    void processKey(const KeyPacket&, Result&) noexcept;

    SerialLimits serial_limits_{};
    std::uint64_t last_epoch_{};
    bool faulted_{};
    LifecycleKey key_{};
    PopupToken token_{};
    std::array<Row, maximum_rows> rows_{};
    std::size_t row_count_{};
    std::uint32_t page_rows_{8};
    std::uint64_t highlight_{}, armed_row_{};
    bool opening_group_{}, opening_moved_{};
    double opening_x_{}, opening_y_{};
    PointerDebt pointer_debt_{};
    std::array<KeyDebt, maximum_key_debts> key_debts_{};
    std::size_t key_debt_count_{};
};
} // namespace bib::provider_candidate::native_popup
