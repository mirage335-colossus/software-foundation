// SPDX-License-Identifier: CC0-1.0
// Portable value/authority tests only; no native engine or browser is exercised.
#include "appended_engine_input_codec.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string_view>

namespace input = foundation::appended::engine_input;
using namespace input;
namespace {
std::size_t assertions{};
void require(bool value, std::string_view label) {
    ++assertions;
    if (!value) throw std::runtime_error(std::string(label));
}
constexpr std::uint64_t context = UINT64_C(0x8000000000000001);
constexpr std::uint64_t token = UINT64_C(0x8000000000000002);
constexpr std::uint64_t sequence = UINT64_C(0xffffffffffffffff);
Bytes hex(std::string_view source) {
    require(source.size() % 2 == 0, "odd fixture hex");
    auto digit = [](char c) -> unsigned {
        if (c >= '0' && c <= '9') return static_cast<unsigned>(c - '0');
        if (c >= 'a' && c <= 'f') return static_cast<unsigned>(c - 'a' + 10);
        throw std::runtime_error("invalid fixture hex");
    };
    Bytes result;
    for (std::size_t i = 0; i < source.size(); i += 2)
        result.push_back(static_cast<std::uint8_t>(16 * digit(source[i]) + digit(source[i + 1])));
    return result;
}
void set32(Bytes& bytes, std::size_t offset, std::uint32_t value) {
    require(offset + 4 <= bytes.size(), "mutation escaped fixture");
    for (unsigned i = 0; i < 4; ++i) bytes[offset + i] = static_cast<std::uint8_t>(value >> (8 * i));
}
void set64(Bytes& bytes, std::size_t offset, std::uint64_t value) {
    require(offset + 8 <= bytes.size(), "mutation escaped fixture");
    for (unsigned i = 0; i < 8; ++i) bytes[offset + i] = static_cast<std::uint8_t>(value >> (8 * i));
}
Key ordinary_key() { return {0, 0, 0, 0, context, "z", "KeyY"}; }
Focus bind(std::uint64_t id = context) { return {1, 0, 0, 0, id, 0}; }
Mouse mouse(std::uint32_t phase, std::uint32_t button, std::uint32_t buttons,
            std::uint64_t capture = token) {
    return {phase, button, buttons, 0, 0, 0, context, capture, 12.25, 35.5, 0, 0};
}
template<class T, class Encode>
void short_outputs(const T& value, std::size_t size, Encode encode) {
    for (std::size_t limit = 0; limit < size; ++limit) {
        Bytes storage(size + 5, 0xa7); const auto original = storage;
        std::size_t written = 913;
        require(encode(value, std::span(storage).first(limit), written) == Status::insufficient_capacity,
            "short output was not rejected");
        require(storage == original && written == 913, "short output changed bytes/count");
    }
}
void key_goldens() {
    const auto layout = hex("00000000000000000000000000000000010000000400000001000000000000807a4b657959");
    Bytes actual; auto value = ordinary_key();
    require(encode_key(value, actual) == Status::ok && actual == layout, "key exact independent LE golden");
    Key decoded;
    require(decode_key(layout, decoded) == Status::ok && decoded == value, "key decode layout/code independent");
    value = {0, 2, 22, 0, context, "AltGraph", "AltRight"};
    const auto altgraph = hex("0000000002000000160000000000000008000000080000000100000000000080416c744772617068416c745269676874");
    require(encode_key(value, actual) == Status::ok && actual == altgraph, "independent AltGraph modifiers golden");
    value = {0, 1, 16, 0, context, "\xc3\xa9", ""};
    const auto unicode = hex("0000000001000000100000000000000002000000000000000100000000000080c3a9");
    require(decode_key(unicode, decoded) == Status::ok && decoded == value, "arbitrary nonmodifier sided location preserved");
    require(encode_key(value, actual) == Status::ok && actual == unicode, "nonempty scalar Unicode exact");
    for (std::uint32_t modifiers = 0; modifiers < 32; ++modifiers) {
        for (std::uint32_t location = 0; location < 4; ++location) {
            for (std::uint32_t phase = 0; phase < 2; ++phase) {
                Key original{phase, location, modifiers, 0, context, "Dead", "KeyY"};
                require(encode_key(original, actual) == Status::ok, "key field combinations accepted without inference");
                require(decode_key(actual, decoded) == Status::ok && decoded == original, "key fields preserved independently");
            }
        }
    }
    Key boundary{0, 3, 31, 1, context, std::string(64, 'K'), std::string(64, '~')};
    require(encode_key(boundary, actual) == Status::ok && actual.size() == 160, "maximum160 key");
    require(decode_key(actual, decoded) == Status::ok && decoded == boundary, "maximum key decoded");
    auto copied = actual;
    require(decode_key(copied, decoded) == Status::ok, "key owned decode");
    copied.assign(copied.size(), 0); require(decoded == boundary, "decoded strings borrowed caller bytes");
    for (auto text : {std::string("\x01", 1), std::string("\xef\xbf\xbf", 3), std::string("\xf4\x8f\xbf\xbf", 4), std::string("e\xcc\x81", 3)}) {
        auto raw = ordinary_key(); raw.key = text;
        require(encode_key(raw, actual) == Status::ok && decode_key(actual, decoded) == Status::ok && decoded.key == text,
            "scalar UTF-8 unexpectedly normalized/rejected");
    }
    short_outputs(boundary, 160, [](const Key& key, auto out, auto& count) { return encode_key(key, out, count); });
}
void malformed_keys() {
    Bytes valid; require(encode_key(ordinary_key(), valid) == Status::ok, "key malformed baseline");
    Key output{1, 3, 3, 0, 123, "sentinel", "Sentinel"}; const auto initial = output;
    auto reject = [&](const Bytes& bytes) {
        require(decode_key(bytes, output) == Status::invalid && output == initial, "malformed key changed output/accepted");
    };
    for (std::size_t length = 0; length < valid.size(); ++length) reject(Bytes(valid.begin(), valid.begin() + length));
    auto extra = valid; extra.push_back(0); reject(extra);
    for (auto [offset, field] : std::array<std::pair<std::size_t, std::uint32_t>, 10>{{{0, 2}, {4, 4}, {8, 32}, {12, 2}, {16, 0}, {16, 65}, {16, 0xffffffffu}, {20, 65}, {20, 0xffffffffu}, {0, 0xffffffffu}}}) {
        auto bytes = valid; set32(bytes, offset, field); reject(bytes);
    }
    auto no_context = valid; set64(no_context, 24, 0); reject(no_context);
    auto repeat_up = valid; set32(repeat_up, 0, 1); set32(repeat_up, 12, 1); reject(repeat_up);
    const std::array<std::string, 11> invalid_text{{std::string("\0", 1), "\xc0\xaf", "\xc1\xbf", "\xe0\x80\x80", "\xed\xa0\x80", "\xf0\x80\x80\x80", "\xf4\x90\x80\x80", "\xf5\x80\x80\x80", "\x80", "\xc2", "\xe2\x28\xa1"}};
    for (const auto& text : invalid_text) {
        auto value = ordinary_key(); value.key = text;
        Bytes output_bytes{0x41, 0x42}; const auto before = output_bytes;
        require(encode_key(value, output_bytes) == Status::invalid && output_bytes == before, "bad UTF-8 encode mutation");
        Bytes bytes(valid.begin(), valid.begin() + 32); set32(bytes, 16, static_cast<std::uint32_t>(text.size()));
        bytes.insert(bytes.end(), text.begin(), text.end()); bytes.insert(bytes.end(), {'K', 'e', 'y', 'Y'}); reject(bytes);
    }
    for (auto code : {std::string(" "), std::string("\x7f", 1), std::string("\x80", 1), std::string("\0", 1)}) {
        auto value = ordinary_key(); value.code = code;
        require(validate_key(value) == Status::invalid, "code must be ASCII visible or empty");
    }
    auto empty = ordinary_key(); empty.key.clear(); require(validate_key(empty) == Status::invalid, "empty logical key");
    empty.key.assign(65, 'a'); require(validate_key(empty) == Status::invalid, "oversized logical key");
    empty = ordinary_key(); empty.code.assign(65, 'a'); require(validate_key(empty) == Status::invalid, "oversized code");
}
void focus_lifecycle() {
    const auto golden = hex("0100000000000000000000000000000001000000000000800000000000000000");
    Bytes bytes; Focus decoded;
    require(encode_focus(bind(), bytes) == Status::ok && bytes == golden, "bind exact high-u64 golden");
    require(decode_focus(golden, decoded) == Status::ok && decoded == bind(), "bind high-u64 decode");
    State state;
    require(accept_focus(state, bind()) == Status::ok && state.active_context == context && state.highest_context == context,
        "bind fresh metadata context");
    require(!state.focused && !state.active && !state.has_last_point, "bind fabricated focus or point");
    auto before = state;
    require(accept_focus(state, bind(context + 1)) == Status::invalid_transition && state == before, "bind replaced live context");
    Focus ordinary{0, 1, 0, 3, context, context};
    require(accept_focus(state, ordinary) == Status::ok && state.focused && !state.active, "focused/active independence");
    ordinary.focused = 0; ordinary.active = 1;
    require(accept_focus(state, ordinary) == Status::ok && !state.focused && state.active, "active/focused independence");
    auto key = ordinary_key(); require(accept_key(state, key) == Status::ok, "active key context");
    key.phase = 1; require(accept_key(state, key) == Status::ok, "raw key-up incorrectly requires held-key history");
    key.input_context = context - 1; before = state;
    require(accept_key(state, key) == Status::stale_context && state == before, "key stale context");
    Focus retire{2, 0, 0, 2, 0, context};
    require(accept_focus(state, retire) == Status::ok && !state.active_context && !state.focused && !state.active, "retire authority before callbacks");
    require(state.highest_context == context, "retirement reset context highwater"); before = state;
    require(accept_focus(state, bind()) == Status::invalid_transition && state == before, "same-document resurrection");
    require(accept_focus(state, retire) == Status::stale_context && state == before, "duplicate retirement accepted");
    require(accept_focus(state, bind(context + 1)) == Status::ok, "fresh replacement context");
    retire_document(state); require(state.highest_context == context + 1 && !state.active_context, "navigation reset highwater");
    state.highest_context = std::numeric_limits<std::uint64_t>::max(); before = state;
    require(accept_focus(state, bind(1)) == Status::invalid_transition && state == before, "exhausted context wrapped");
    short_outputs(bind(), 32, [](const Focus& value, auto out, auto& count) { return encode_focus(value, out, count); });
    for (auto invalid : {Focus{3, 0, 0, 0, context, 0}, Focus{0, 2, 0, 0, context, context}, Focus{0, 0, 2, 0, context, context},
        Focus{0, 0, 0, 4, context, context}, Focus{0, 0, 0, 0, context, context + 1}, Focus{0, 0, 0, 0, 0, 0},
        Focus{1, 1, 0, 0, context, 0}, Focus{1, 0, 0, 1, context, 0}, Focus{1, 0, 0, 0, context, context},
        Focus{2, 0, 0, 0, 0, context}, Focus{2, 0, 0, 3, context, context}, Focus{2, 0, 1, 3, 0, context}})
        require(validate_focus(invalid) == Status::invalid, "invalid focus action shape");
    decoded = bind(9); const auto initial = decoded;
    for (std::size_t length = 0; length < 32; ++length)
        require(decode_focus(std::span(golden).first(length), decoded) == Status::invalid && decoded == initial, "short focus changed output");
    bytes = golden; bytes.push_back(0); require(decode_focus(bytes, decoded) == Status::invalid && decoded == initial, "focus trailing bytes");
}
void mouse_goldens_and_malformed() {
    const auto golden = hex("01000000000000000000000001000000000000000000000000000000000000000100000000000080020000000000008000000000008028400000000000c0414000000000000000000000000000000000");
    auto down = mouse(1, 0, 1); Bytes bytes; Mouse decoded;
    require(encode_mouse(down, bytes) == Status::ok && bytes == golden, "mouse exact independent binary64/high-u64 golden");
    require(decode_mouse(golden, decoded) == Status::ok && decoded == down && decoded.clicks == 0, "unknown click count retained");
    short_outputs(down, 80, [](const Mouse& value, auto out, auto& count) { return encode_mouse(value, out, count); });
    decoded = mouse(0, 0, 0, 0); const auto initial = decoded;
    auto reject = [&](const Bytes& value) { require(decode_mouse(value, decoded) == Status::invalid && decoded == initial, "malformed mouse accepted/changed output"); };
    for (std::size_t length = 0; length < 80; ++length) reject(Bytes(golden.begin(), golden.begin() + length));
    auto extra = golden; extra.push_back(0); reject(extra);
    for (auto [offset, value] : std::array<std::pair<std::size_t, std::uint32_t>, 9>{{{0, 6}, {4, 1}, {8, 5}, {12, 32}, {16, 4}, {20, 32}, {24, 2}, {24, 1}, {28, 1}}}) {
        bytes = golden; set32(bytes, offset, value); reject(bytes);
    }
    for (auto value : {std::numeric_limits<double>::infinity(), -std::numeric_limits<double>::infinity(), std::numeric_limits<double>::quiet_NaN(), 1000000.01, -1000000.01}) {
        bytes = golden; set64(bytes, 48, std::bit_cast<std::uint64_t>(value)); reject(bytes);
    }
    bytes = golden; set64(bytes, 32, 0); reject(bytes);
    bytes = golden; set64(bytes, 40, 0); reject(bytes);
    bytes = golden; set32(bytes, 12, 0); reject(bytes);
    auto wheel = mouse(3, 0, 0, 0); wheel.wheel_y = 16;
    require(validate_mouse(wheel) == Status::ok, "pixel wheel valid");
    wheel.wheel_y = 0.1; require(validate_mouse(wheel) == Status::invalid, "wheel accepted non-binary32 double");
    wheel.wheel_y = static_cast<double>(std::numeric_limits<float>::denorm_min());
    require(validate_mouse(wheel) == Status::ok, "representable fractional wheel rejected");
    wheel.wheel_y = 0; require(validate_mouse(wheel) == Status::invalid, "zero wheel stroke accepted");
    wheel.wheel_y = -16; wheel.button = 1; require(validate_mouse(wheel) == Status::invalid, "wheel unused button");
    wheel.button = 0; wheel.clicks = 1; require(validate_mouse(wheel) == Status::invalid, "wheel unused clicks");
    auto context_mouse = mouse(5, 0, 0, 0); context_mouse.context_origin = 1;
    require(validate_mouse(context_mouse) == Status::invalid, "keyboard context inferred from nonzero point");
    context_mouse.x = context_mouse.y = 0;
    require(validate_mouse(context_mouse) == Status::ok, "explicit keyboard context intent");
    context_mouse.modifiers = 1; require(validate_mouse(context_mouse) == Status::invalid, "keyboard context recovered modifiers");
    auto move = mouse(0, 0, 0, 0); move.x = -0.0; move.y = -1000000;
    require(encode_mouse(move, bytes) == Status::ok && decode_mouse(bytes, decoded) == Status::ok
        && std::signbit(decoded.x) && decoded.y == -1000000, "coordinates normalized/clamped");
    require(mouse_button_bit(0) == 1 && mouse_button_bit(1) == 4 && mouse_button_bit(2) == 2
        && mouse_button_bit(3) == 8 && mouse_button_bit(4) == 16 && mouse_button_bit(5) == 0, "five DOM button ordinals");
    require(native_move_button(31) == 0 && native_move_button(30) == 1 && native_move_button(26) == 2
        && native_move_button(24) == 3 && native_move_button(16) == 4 && native_move_button(0) == -1
        && native_move_button(32) == -1, "normal native held-button priority");
    Mouse cancel{4, 0, 0, 0, 0, 0, context, token, 0, 0, 0, 0};
    require(validate_mouse(cancel) == Status::ok, "canonical cancellation");
    for (unsigned field = 0; field < 8; ++field) {
        auto invalid = cancel;
        switch (field) {
        case 0: invalid.button = 1; break;
        case 1: invalid.buttons = 1; break;
        case 2: invalid.modifiers = 1; break;
        case 3: invalid.x = 1; break;
        case 4: invalid.y = 1; break;
        case 5: invalid.wheel_x = 1; break;
        case 6: invalid.clicks = 1; break;
        case 7: invalid.capture_token = 0; break;
        }
        require(validate_mouse(invalid) == Status::invalid, "cancel unused fields must be zero");
    }
}
void mouse_capture_lifecycle() {
    State state; require(accept_focus(state, bind()) == Status::ok, "capture bind");
    auto before = state;
    require(accept_mouse(state, mouse(2, 0, 0)) == Status::invalid_transition && state == before, "release without press");
    auto first = mouse(1, 0, 1);
    require(accept_mouse(state, first) == Status::ok && state.capture_token == token && state.buttons == 1, "fresh first press");
    before = state;
    require(accept_mouse(state, first) == Status::invalid_transition && state == before, "repeated down not rejected transactionally");
    auto wrong = mouse(1, 2, 7); require(accept_mouse(state, wrong) == Status::invalid_transition && state == before, "multiple changed bits fabricated order");
    wrong = mouse(1, 2, 3, token + 1); require(accept_mouse(state, wrong) == Status::invalid_transition && state == before, "second logical mouse accepted");
    std::uint32_t held = 1;
    for (auto [button, bit] : std::array<std::pair<std::uint32_t, std::uint32_t>, 4>{{{2, 2}, {1, 4}, {3, 8}, {4, 16}}}) {
        held |= bit; auto press = mouse(1, button, held); press.clicks = 3;
        require(accept_mouse(state, press) == Status::ok && state.buttons == held && state.capture_token == token,
            "five-button chord did not retain full token/mask");
    }
    auto move = mouse(0, 0, 31); move.x = -77.5; move.y = 99.125;
    require(accept_mouse(state, move) == Status::ok && state.last_x == -77.5 && state.last_y == 99.125, "captured move real point");
    before = state;
    auto pointer_context = mouse(5, 0, 31); pointer_context.modifiers = 31;
    require(accept_mouse(state, pointer_context) == Status::ok && state.capture_token == before.capture_token
        && state.buttons == before.buttons && state.last_x == 12.25 && state.last_y == 35.5,
        "pointer context lost capture/real context point"); before = state;
    auto keyboard_context = mouse(5, 0, 31); keyboard_context.context_origin = 1; keyboard_context.x = keyboard_context.y = 0;
    require(accept_mouse(state, keyboard_context) == Status::ok && state == before, "keyboard context lost capture/last real point");
    auto cancelled_context = state;
    const Mouse context_cancel{4, 0, 0, 0, 0, 0, context, token, 0, 0, 0, 0};
    require(accept_mouse(cancelled_context, context_cancel) == Status::ok && !cancelled_context.capture_token
        && !cancelled_context.buttons && cancelled_context.last_x == 12.25 && cancelled_context.last_y == 35.5,
        "pointer context then keyboard context then cancel lost real point");
    auto incompatible_context = keyboard_context; incompatible_context.capture_token = token + 1;
    require(accept_mouse(state, incompatible_context) == Status::invalid_transition && state == before, "context replaced capture token");
    incompatible_context = keyboard_context; incompatible_context.buttons = 1;
    require(accept_mouse(state, incompatible_context) == Status::invalid_transition && state == before, "context changed chord");
    move.buttons = 30; require(accept_mouse(state, move) == Status::invalid_transition && state == before, "ordinary move changed held state");
    held = 31;
    for (auto [button, bit] : std::array<std::pair<std::uint32_t, std::uint32_t>, 5>{{{2, 2}, {0, 1}, {4, 16}, {1, 4}, {3, 8}}}) {
        held &= ~bit;
        require(accept_mouse(state, mouse(2, button, held)) == Status::ok && state.buttons == held
            && state.capture_token == (held ? token : 0), "partial/final chord release");
    }
    require(state.highest_capture_token == token, "final release reset token highwater"); before = state;
    require(accept_mouse(state, first) == Status::invalid_transition && state == before, "retired token resurrected");
    auto fresh = mouse(1, 4, 16, token + 1); fresh.x = 300; fresh.y = 200;
    require(accept_mouse(state, fresh) == Status::ok, "fresh capture after full release");
    Mouse cancel{4, 0, 0, 0, 0, 0, context, token + 1, 0, 0, 0, 0};
    require(accept_mouse(state, cancel) == Status::ok && !state.capture_token && !state.buttons
        && state.last_x == 300 && state.last_y == 200, "cancel placeholder overwrote real point"); before = state;
    require(accept_mouse(state, cancel) == Status::invalid_transition && state == before, "cancel replay");
    fresh.capture_token = token + 2; require(accept_mouse(state, fresh) == Status::ok, "retirement test capture");
    Focus retire{2, 0, 0, 3, 0, context};
    require(accept_focus(state, retire) == Status::ok && !state.capture_token && !state.active_context
        && state.highest_capture_token == token + 2 && state.highest_context == context && state.last_x == 300,
        "context retirement lost cancellation point/highwaters"); before = state;
    require(accept_mouse(state, fresh) == Status::stale_context && state == before, "retired context admitted mouse");
    require(accept_focus(state, bind(context + 1)) == Status::ok, "successor context for token test");
    fresh.input_context = context + 1;
    require(accept_mouse(state, fresh) == Status::invalid_transition, "token resurrected across navigation");
    state.highest_capture_token = sequence; before = state; fresh.capture_token = 1;
    require(accept_mouse(state, fresh) == Status::invalid_transition && state == before, "exhausted token wrapped");
    State last;
    require(accept_focus(last, bind(sequence)) == Status::ok && last.active_context == sequence, "UINT64_MAX context valid once");
    auto final_press = mouse(1, 0, 1, sequence); final_press.input_context = sequence;
    require(accept_mouse(last, final_press) == Status::ok && last.highest_capture_token == sequence, "UINT64_MAX capture valid once");
    retire_document(last); before = last;
    require(accept_focus(last, bind(sequence)) == Status::invalid_transition && last == before, "maximum context resurrected");
    State losing_focus;
    require(accept_focus(losing_focus, bind()) == Status::ok
        && accept_mouse(losing_focus, first) == Status::ok, "focus-loss held capture fixture");
    const Focus blur{0, 0, 1, 3, context, context};
    require(accept_focus(losing_focus, blur) == Status::ok && !losing_focus.capture_token && !losing_focus.buttons
        && losing_focus.active_context == context && losing_focus.highest_context == context
        && losing_focus.highest_capture_token == token && losing_focus.last_x == 12.25 && losing_focus.last_y == 35.5,
        "focus loss did not clear capture before callbacks/preserve context and real point"); before = losing_focus;
    require(accept_mouse(losing_focus, context_cancel) == Status::invalid_transition && losing_focus == before,
        "old cancellation after focus loss reused retired token");
    auto new_press = mouse(1, 4, 16, token + 1);
    require(accept_mouse(losing_focus, new_press) == Status::ok && losing_focus.capture_token == token + 1,
        "fresh token after focus loss rejected");
    const Focus inactive{0, 1, 0, 0, context, context};
    require(accept_focus(losing_focus, inactive) == Status::ok && losing_focus.focused && !losing_focus.active
        && !losing_focus.capture_token && !losing_focus.buttons && losing_focus.highest_capture_token == token + 1,
        "inactivation did not cancel capture independently of focused flag");
}
void command_envelope() {
    const auto key_bytes = hex("00000000000000000000000000000000010000000400000001000000000000807a4b657959");
    Command command{1, sequence, kKeySchema, key_bytes};
    const auto golden = hex("0100000000000000ffffffffffffffff86b7baad1c95bfb8de3e6b7a9a7c433b528278bbcf84199ca0b2b4ee6134dbc9100000002500000000000000000000000000000000000000010000000400000001000000000000807a4b657959");
    Bytes encoded; require(encode_command(command, encoded) == Status::ok && encoded == golden, "COMMAND56 exact independent golden");
    Command output;
    require(decode_command(golden, output) == Status::ok && output == command, "COMMAND high-u64/schema decode");
    auto copied = encoded; require(decode_command(copied, output) == Status::ok, "command ownership decode");
    copied.assign(copied.size(), 0); require(output == command, "command borrowed input bytes");
    auto alias = command;
    // The owning output can be the same object as the input payload.
    require(encode_command(alias, alias.payload) == Status::ok && alias.payload == golden, "owning command output aliases payload");
    short_outputs(command, golden.size(), [](const Command& value, auto out, auto& count) { return encode_command(value, out, count); });
    output = {5, 1, kMouseSchema, {1, 2}}; const auto initial = output;
    auto reject = [&](const Bytes& bytes, Status expected = Status::invalid) {
        require(decode_command(bytes, output) == expected && output == initial, "invalid command accepted/changed output");
    };
    for (std::size_t length = 0; length < golden.size(); ++length) reject(Bytes(golden.begin(), golden.begin() + length));
    auto trailing = golden; trailing.push_back(0); reject(trailing);
    for (auto [offset, value] : std::array<std::pair<std::size_t, std::uint32_t>, 8>{{{4, 1}, {48, 0}, {48, 15}, {48, 17}, {52, 0}, {52, 161}, {52, 0xffffffffu}, {56, 2}}}) {
        copied = golden; set32(copied, offset, value); reject(copied);
    }
    copied = golden; copied[16] ^= 1; reject(copied);
    copied = golden; set64(copied, 8, 0); reject(copied);
    copied = golden; set32(copied, 0, 2); reject(copied, Status::unsupported);
    copied.assign(217, 0); reject(copied);
    Key maximum{0, 0, 0, 0, context, std::string(64, 'x'), std::string(64, '!')};
    require(encode_key(maximum, command.payload) == Status::ok, "max command key payload");
    require(encode_command(command, encoded) == Status::ok && encoded.size() == 216, "maximum216 command accepted");
    command.payload.push_back(0); require(validate_command(command) == Status::invalid, "oversized command");
    command = {3, 1, kFocusSchema, {}}; require(encode_focus(bind(), command.payload) == Status::ok && validate_command(command) == Status::ok, "exact focus catalog descriptor");
    command = {5, 1, kMouseSchema, {}}; require(encode_mouse(mouse(1, 0, 1), command.payload) == Status::ok && validate_command(command) == Status::ok, "exact mouse catalog descriptor");
    command.schema_sha256 = kFocusSchema; require(validate_command(command) == Status::invalid, "schema operation substitution");
    require(!operation_facts(0) && !operation_facts(2) && !operation_facts(4) && !operation_facts(6), "unknown command catalog operation");
}
void actual_result_receipt() {
    CommandResult rejected{-5, 0, sequence, 0, 0}; Bytes bytes;
    const auto golden = hex("fbffffff00000000ffffffffffffffff0000000000000000");
    require(encode_command_result(rejected, bytes) == Status::ok && bytes == golden, "actual24 signed/high-u64 result golden");
    CommandResult output;
    require(decode_command_result(golden, output) == Status::ok && output == rejected, "signed status result decode");
    short_outputs(rejected, 24, [](const CommandResult& value, auto out, auto& count) { return encode_command_result(value, out, count); });
    for (std::int32_t status = -8; status <= -1; ++status) {
        for (std::uint32_t disposition : {0u, 2u})
            require(validate_command_result({status, disposition, sequence, 0, 0}) == Status::ok, "actual rejected/unknown status domain");
    }
    for (std::uint32_t handled : {0u, 1u}) {
        CommandResult consumed{0, 1, sequence, 0, handled};
        require(encode_command_result(consumed, bytes) == Status::ok && decode_command_result(bytes, output) == Status::ok && output == consumed,
            "consumed unhandled conflated with rejected");
    }
    for (auto invalid : {CommandResult{0, 0, 1, 0, 0}, CommandResult{0, 2, 1, 0, 0}, CommandResult{-1, 1, 1, 0, 0},
        CommandResult{-1, 0, 1, 0, 1}, CommandResult{-1, 2, 1, 0, 1}, CommandResult{0, 1, 1, 1, 0}, CommandResult{0, 1, 1, 0, 2},
        CommandResult{-9, 2, 1, 0, 0}, CommandResult{1, 0, 1, 0, 0}, CommandResult{0, 1, 0, 0, 0}, CommandResult{-1, 3, 1, 0, 0}})
        require(validate_command_result(invalid) == Status::invalid, "malformed actual result accepted");
    output = {0, 1, 42, 0, 1}; const auto initial = output;
    for (std::size_t length = 0; length < 24; ++length)
        require(decode_command_result(std::span(golden).first(length), output) == Status::invalid && output == initial, "short result mutated output");
    bytes = golden; bytes.push_back(0); require(decode_command_result(bytes, output) == Status::invalid && output == initial, "result trailing bytes");
    bytes = golden; set32(bytes, 0, 0x80000000u);
    require(decode_command_result(bytes, output) == Status::invalid && output == initial, "signed minimum status domain");
}
EngineSurfaceProfileFacts test_facts() {
    // Deliberate fixture identities, never retained build/runtime evidence.
    EngineSurfaceProfileFacts result;
    result.enabled = true; result.name = kInputProfileName; result.contract_sha256 = kProviderContractSha256;
    result.build_sha256.fill(0x11); result.source_recipe_sha256.fill(0x22); result.catalog_sha256 = kInputCatalogSha256;
    result.provider_capabilities = 467; result.surface_capabilities = 8225;
    result.surface_protocol_version = 1; result.mouse_input_version = 1; result.raw_key_mapping_revision = 1;
    result.viewport_width = 800; result.viewport_height = 600; result.display_scale = 1;
    result.commands = kCommands; return result;
}
void explicit_profile_facts() {
    require(!input_profile_valid({}), "default profile unexpectedly enabled");
    auto expected = test_facts(); require(input_profile_valid(expected), "explicit complete fixture facts");
    require(input_profile_agrees(expected, expected), "equal complete immutable facts");
    auto actual = expected; actual.build_sha256[0] ^= 1;
    require(input_profile_valid(actual) && !input_profile_agrees(actual, expected), "actual build identity substitution");
    actual = expected; actual.catalog_sha256[0] ^= 1;
    require(!input_profile_valid(actual) && !input_profile_agrees(actual, expected), "named physical-v1 catalog identity substitution");
    actual = expected; actual.catalog_sha256.fill(0x33);
    require(!input_profile_valid(actual) && !input_profile_agrees(actual, expected), "arbitrary nonzero future catalog accepted as physical-v1");
    actual = expected; actual.source_recipe_sha256[0] ^= 1; require(!input_profile_agrees(actual, expected), "actual source identity substitution");
    actual = expected; actual.contract_sha256[0] ^= 1; require(!input_profile_valid(actual), "C ABI contract identity substitution");
    for (unsigned field = 0; field < 18; ++field) {
        actual = expected;
        switch (field) {
        case 0: actual.enabled = false; break;
        case 1: actual.name = "copied259"; break;
        case 2: actual.build_sha256 = {}; break;
        case 3: actual.source_recipe_sha256 = {}; break;
        case 4: actual.catalog_sha256 = {}; break;
        case 5: actual.provider_capabilities = 259; break;
        case 6: actual.surface_capabilities |= 64; break;
        case 7: actual.surface_protocol_version = 2; break;
        case 8: actual.mouse_input_version = 0; break;
        case 9: actual.raw_key_mapping_revision = 0; break;
        case 10: actual.viewport_width = 801; break;
        case 11: actual.viewport_height = 601; break;
        case 12: actual.display_scale = 2; break;
        case 13: actual.commands[0].schema_sha256[0] ^= 1; break;
        case 14: actual.commands[1].maximum_input_bytes = 16; break;
        case 15: actual.commands[2].required_reply_capacity = 0; break;
        case 16: std::swap(actual.commands[0], actual.commands[1]); break;
        case 17: actual.query_count = 1; break;
        }
        require(!input_profile_valid(actual) && !input_profile_agrees(actual, expected), "incomplete/widened profile accepted");
    }
}
} // namespace

int main() {
    try {
        key_goldens(); malformed_keys(); focus_lifecycle(); mouse_goldens_and_malformed();
        mouse_capture_lifecycle(); command_envelope(); actual_result_receipt(); explicit_profile_facts();
        std::cout << "PASS: 8 portable input codec groups, " << assertions << " assertions; no engine/browser execution\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL after " << assertions << " assertions: " << error.what() << '\n'; return 1;
    }
}
