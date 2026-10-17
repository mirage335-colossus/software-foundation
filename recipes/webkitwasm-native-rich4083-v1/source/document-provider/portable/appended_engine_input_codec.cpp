// SPDX-License-Identifier: CC0-1.0
#include "appended_engine_input_codec.hpp"

#include <algorithm>
#include <bit>
#include <cmath>
#include <limits>
#include <utility>

namespace foundation::appended::engine_input {
namespace {
using View = std::span<const std::uint8_t>;
using Output = std::span<std::uint8_t>;
static_assert(sizeof(double) == 8 && std::numeric_limits<double>::is_iec559
    && std::numeric_limits<double>::radix == 2 && std::numeric_limits<double>::digits == 53
    && std::numeric_limits<double>::max_exponent == 1024);
static_assert(sizeof(float) == 4 && std::numeric_limits<float>::is_iec559
    && std::numeric_limits<float>::radix == 2 && std::numeric_limits<float>::digits == 24
    && std::numeric_limits<float>::max_exponent == 128);

std::uint64_t get(View bytes, std::size_t offset, unsigned count) noexcept {
    std::uint64_t value{};
    for (unsigned i = 0; i < count; ++i) value |= std::uint64_t(bytes[offset + i]) << (i * 8);
    return value;
}
void put(Output bytes, std::size_t offset, std::uint64_t value, unsigned count) noexcept {
    for (unsigned i = 0; i < count; ++i) bytes[offset + i] = static_cast<std::uint8_t>(value >> (i * 8));
}
std::uint32_t u32(View bytes, std::size_t offset) noexcept { return static_cast<std::uint32_t>(get(bytes, offset, 4)); }
double f64(View bytes, std::size_t offset) noexcept { return std::bit_cast<double>(get(bytes, offset, 8)); }
bool finite(double value) noexcept { return std::isfinite(value) && std::abs(value) <= 1000000; }
bool pixel_delta(double value) noexcept { return finite(value) && static_cast<double>(static_cast<float>(value)) == value; }
bool key_text(std::string_view text) noexcept {
    // Unicode scalar UTF-8, shortest form, no U+0000; no normalization.
    const auto* p = reinterpret_cast<const unsigned char*>(text.data());
    for (std::size_t i = 0; i < text.size();) {
        auto first = p[i++];
        if (first >= 1 && first <= 0x7f) continue;
        unsigned more{}; std::uint32_t scalar{}, minimum{};
        if (first >= 0xc2 && first <= 0xdf) { more = 1; scalar = first & 0x1f; minimum = 0x80; }
        else if (first >= 0xe0 && first <= 0xef) { more = 2; scalar = first & 0x0f; minimum = 0x800; }
        else if (first >= 0xf0 && first <= 0xf4) { more = 3; scalar = first & 7; minimum = 0x10000; }
        else return false;
        if (more > text.size() - i) return false;
        while (more--) {
            auto next = p[i++];
            if ((next & 0xc0) != 0x80) return false;
            scalar = (scalar << 6) | (next & 0x3f);
        }
        if (scalar < minimum || scalar > 0x10ffff || (scalar >= 0xd800 && scalar <= 0xdfff)) return false;
    }
    return true;
}
bool code_text(std::string_view text) noexcept {
    return std::all_of(text.begin(), text.end(), [](unsigned char c) { return c >= 0x21 && c <= 0x7e; });
}
Status key_wire(View bytes) noexcept {
    if (bytes.size() < kKeyFixedBytes || bytes.size() > kMaximumKeyBytes) return Status::invalid;
    const auto key_size = u32(bytes, 16), code_size = u32(bytes, 20);
    if (!key_size || key_size > 64 || code_size > 64 || bytes.size() != kKeyFixedBytes + key_size + code_size
        || u32(bytes, 0) > 1 || u32(bytes, 4) > 3 || u32(bytes, 8) > 31 || u32(bytes, 12) > 1
        || (u32(bytes, 0) == 1 && u32(bytes, 12)) || !get(bytes, 24, 8)) return Status::invalid;
    const auto* chars = reinterpret_cast<const char*>(bytes.data() + kKeyFixedBytes);
    return key_text({chars, key_size}) && code_text({chars + key_size, code_size}) ? Status::ok : Status::invalid;
}
Status payload_wire(std::uint32_t operation, View payload) noexcept {
    if (operation == 1) return key_wire(payload);
    if (operation == 3) { Focus value; return decode_focus(payload, value); }
    if (operation == 5) { Mouse value; return decode_mouse(payload, value); }
    return Status::unsupported;
}
bool state_valid(const State& value) noexcept {
    return value.active_context <= value.highest_context && value.capture_token <= value.highest_capture_token
        && value.buttons <= 31 && ((value.buttons == 0) == (value.capture_token == 0))
        && (!value.capture_token || (value.active_context && value.has_last_point))
        && (value.active_context || (!value.focused && !value.active))
        && (!value.has_last_point || (finite(value.last_x) && finite(value.last_y)));
}
template<std::size_t Capacity, class Value, class Function>
Status owned_encode(const Value& value, Bytes& output, Function function) {
    std::array<std::uint8_t, Capacity> storage{};
    std::size_t written{};
    auto status = function(value, Output(storage), written);
    if (status == Status::ok) { Bytes temporary(storage.begin(), storage.begin() + written); output = std::move(temporary); }
    return status;
}
} // namespace

Status validate_key(const Key& value) noexcept {
    return value.phase <= 1 && value.location <= 3 && value.modifiers <= 31 && value.repeat <= 1
        && !(value.phase == 1 && value.repeat) && value.input_context
        && !value.key.empty() && value.key.size() <= 64 && value.code.size() <= 64
        && key_text(value.key) && code_text(value.code) ? Status::ok : Status::invalid;
}
Status validate_focus(const Focus& value) noexcept {
    if (value.focused > 1 || value.active > 1 || value.cause > 3) return Status::invalid;
    switch (value.action) {
    case 0: return value.input_context && value.input_context == value.expected_context ? Status::ok : Status::invalid;
    case 1: return value.input_context && !value.expected_context && !value.focused && !value.active && !value.cause ? Status::ok : Status::invalid;
    case 2: return !value.input_context && value.expected_context && !value.focused && !value.active && value.cause ? Status::ok : Status::invalid;
    default: return Status::invalid;
    }
}
std::uint32_t mouse_button_bit(std::uint32_t button) noexcept {
    constexpr std::array<std::uint32_t, 5> bits{1, 4, 2, 8, 16};
    return button < bits.size() ? bits[button] : 0;
}
std::int32_t native_move_button(std::uint32_t buttons) noexcept {
    if (buttons > 31) return -1;
    for (std::uint32_t button = 0; button < 5; ++button)
        if (buttons & mouse_button_bit(button)) return static_cast<std::int32_t>(button);
    return -1;
}
Status validate_mouse(const Mouse& value) noexcept {
    if (value.phase > 5 || value.button > 4 || value.buttons > 31 || value.clicks > 3 || value.modifiers > 31
        || value.context_origin > 1 || !value.input_context || !finite(value.x) || !finite(value.y)
        || !pixel_delta(value.wheel_x) || !pixel_delta(value.wheel_y)) return Status::invalid;
    if (value.phase != 5 && value.context_origin) return Status::invalid;
    if (value.phase != 3 && (value.wheel_x != 0 || value.wheel_y != 0)) return Status::invalid;
    if (value.phase == 1 || value.phase == 2) {
        if (!value.capture_token || ((value.buttons & mouse_button_bit(value.button)) != 0) != (value.phase == 1)) return Status::invalid;
        return Status::ok;
    }
    if (value.button || value.clicks) return Status::invalid;
    if (value.phase == 4) return value.capture_token && !value.buttons && !value.modifiers
        && value.x == 0 && value.y == 0 ? Status::ok : Status::invalid;
    if ((value.buttons == 0) != (value.capture_token == 0)) return Status::invalid;
    if (value.phase == 3 && value.wheel_x == 0 && value.wheel_y == 0) return Status::invalid;
    if (value.phase == 5 && value.context_origin == 1 && (value.x != 0 || value.y != 0 || value.modifiers)) return Status::invalid;
    return Status::ok;
}

Status encode_key(const Key& value, Output target, std::size_t& written) noexcept {
    auto status = validate_key(value); if (status != Status::ok) return status;
    const auto size = kKeyFixedBytes + value.key.size() + value.code.size();
    if (target.size() < size) return Status::insufficient_capacity;
    std::array<std::uint8_t, kMaximumKeyBytes> storage{};
    Output output(storage);
    put(output, 0, value.phase, 4); put(output, 4, value.location, 4); put(output, 8, value.modifiers, 4); put(output, 12, value.repeat, 4);
    put(output, 16, value.key.size(), 4); put(output, 20, value.code.size(), 4); put(output, 24, value.input_context, 8);
    std::copy(value.key.begin(), value.key.end(), output.begin() + kKeyFixedBytes);
    std::copy(value.code.begin(), value.code.end(), output.begin() + kKeyFixedBytes + value.key.size());
    std::copy_n(storage.begin(), size, target.begin());
    written = size; return Status::ok;
}
Status encode_focus(const Focus& value, Output output, std::size_t& written) noexcept {
    auto status = validate_focus(value); if (status != Status::ok) return status;
    if (output.size() < kFocusBytes) return Status::insufficient_capacity;
    put(output, 0, value.action, 4); put(output, 4, value.focused, 4); put(output, 8, value.active, 4); put(output, 12, value.cause, 4);
    put(output, 16, value.input_context, 8); put(output, 24, value.expected_context, 8);
    written = kFocusBytes; return Status::ok;
}
Status encode_mouse(const Mouse& value, Output output, std::size_t& written) noexcept {
    auto status = validate_mouse(value); if (status != Status::ok) return status;
    if (output.size() < kMouseBytes) return Status::insufficient_capacity;
    put(output, 0, value.phase, 4); put(output, 4, 0, 4); put(output, 8, value.button, 4); put(output, 12, value.buttons, 4);
    put(output, 16, value.clicks, 4); put(output, 20, value.modifiers, 4); put(output, 24, value.context_origin, 4); put(output, 28, 0, 4);
    put(output, 32, value.input_context, 8); put(output, 40, value.capture_token, 8);
    put(output, 48, std::bit_cast<std::uint64_t>(value.x), 8); put(output, 56, std::bit_cast<std::uint64_t>(value.y), 8);
    put(output, 64, std::bit_cast<std::uint64_t>(value.wheel_x), 8); put(output, 72, std::bit_cast<std::uint64_t>(value.wheel_y), 8);
    written = kMouseBytes; return Status::ok;
}
Status encode_key(const Key& value, Bytes& output) { return owned_encode<kMaximumKeyBytes>(value, output, static_cast<Status (*)(const Key&, Output, std::size_t&) noexcept>(encode_key)); }
Status encode_focus(const Focus& value, Bytes& output) { return owned_encode<kFocusBytes>(value, output, static_cast<Status (*)(const Focus&, Output, std::size_t&) noexcept>(encode_focus)); }
Status encode_mouse(const Mouse& value, Bytes& output) { return owned_encode<kMouseBytes>(value, output, static_cast<Status (*)(const Mouse&, Output, std::size_t&) noexcept>(encode_mouse)); }
Status decode_key(View bytes, Key& output) {
    auto status = key_wire(bytes); if (status != Status::ok) return status;
    const auto key_size = u32(bytes, 16), code_size = u32(bytes, 20);
    const auto* chars = reinterpret_cast<const char*>(bytes.data() + kKeyFixedBytes);
    Key value{u32(bytes, 0), u32(bytes, 4), u32(bytes, 8), u32(bytes, 12), get(bytes, 24, 8), {chars, key_size}, {chars + key_size, code_size}};
    output = std::move(value); return Status::ok;
}
Status decode_focus(View bytes, Focus& output) noexcept {
    if (bytes.size() != kFocusBytes) return Status::invalid;
    Focus value{u32(bytes, 0), u32(bytes, 4), u32(bytes, 8), u32(bytes, 12), get(bytes, 16, 8), get(bytes, 24, 8)};
    auto status = validate_focus(value); if (status == Status::ok) output = value; return status;
}
Status decode_mouse(View bytes, Mouse& output) noexcept {
    if (bytes.size() != kMouseBytes || u32(bytes, 4) || u32(bytes, 28)) return Status::invalid;
    Mouse value{u32(bytes, 0), u32(bytes, 8), u32(bytes, 12), u32(bytes, 16), u32(bytes, 20), u32(bytes, 24),
        get(bytes, 32, 8), get(bytes, 40, 8), f64(bytes, 48), f64(bytes, 56), f64(bytes, 64), f64(bytes, 72)};
    auto status = validate_mouse(value); if (status == Status::ok) output = value; return status;
}

Status accept_key(const State& state, const Key& value) noexcept {
    auto status = validate_key(value); if (status != Status::ok) return status;
    if (!state_valid(state)) return Status::invalid_transition;
    return value.input_context == state.active_context ? Status::ok : Status::stale_context;
}
Status accept_focus(State& state, const Focus& value) noexcept {
    auto status = validate_focus(value); if (status != Status::ok) return status;
    if (!state_valid(state)) return Status::invalid_transition;
    if (value.action == 1) {
        if (state.active_context || value.input_context <= state.highest_context) return Status::invalid_transition;
        state.active_context = state.highest_context = value.input_context;
    } else if (value.action == 2) {
        if (value.expected_context != state.active_context) return Status::stale_context;
        retire_document(state);
    } else {
        if (value.input_context != state.active_context) return Status::stale_context;
        state.focused = value.focused != 0; state.active = value.active != 0;
        if (!state.focused || !state.active) { state.capture_token = 0; state.buttons = 0; }
    }
    return Status::ok;
}
Status accept_mouse(State& state, const Mouse& value) noexcept {
    auto status = validate_mouse(value); if (status != Status::ok) return status;
    if (!state_valid(state)) return Status::invalid_transition;
    if (value.input_context != state.active_context) return Status::stale_context;
    State next = state;
    if (value.phase == 1) {
        const auto bit = mouse_button_bit(value.button);
        if (state.capture_token) {
            if (value.capture_token != state.capture_token || (state.buttons & bit) || value.buttons != (state.buttons | bit)) return Status::invalid_transition;
        } else {
            if (value.capture_token <= state.highest_capture_token || value.buttons != bit) return Status::invalid_transition;
            next.capture_token = next.highest_capture_token = value.capture_token;
        }
        next.buttons = value.buttons;
    } else if (value.phase == 2) {
        const auto bit = mouse_button_bit(value.button);
        if (!state.capture_token || value.capture_token != state.capture_token || !(state.buttons & bit) || value.buttons != (state.buttons & ~bit)) return Status::invalid_transition;
        next.buttons = value.buttons; if (!value.buttons) next.capture_token = 0;
    } else if (value.phase == 4) {
        if (!state.capture_token || value.capture_token != state.capture_token) return Status::invalid_transition;
        next.capture_token = 0; next.buttons = 0;
    } else if (value.capture_token != state.capture_token || value.buttons != state.buttons) return Status::invalid_transition;
    // Pointer context has a real point; cancel and keyboard context have placeholders.
    // Retain the last real point for native cancellation after authority clears.
    if (value.phase != 4 && !(value.phase == 5 && value.context_origin == 1)) {
        next.last_x = value.x; next.last_y = value.y; next.has_last_point = true;
    }
    state = next; return Status::ok;
}
void retire_document(State& state) noexcept {
    state.active_context = state.capture_token = 0; state.buttons = 0; state.focused = state.active = false;
}

const OperationFacts* operation_facts(std::uint32_t operation) noexcept {
    for (const auto& facts : kCommands) if (facts.operation == operation) return &facts;
    return nullptr;
}
Status validate_command(const Command& value) noexcept {
    const auto* facts = operation_facts(value.operation); if (!facts) return Status::unsupported;
    if (!value.request_sequence || value.schema_sha256 != facts->schema_sha256 || value.payload.size() > facts->maximum_input_bytes) return Status::invalid;
    return payload_wire(value.operation, value.payload);
}
Status encode_command(const Command& value, Output target, std::size_t& written) noexcept {
    auto status = validate_command(value); if (status != Status::ok) return status;
    const auto size = kCommandFixedBytes + value.payload.size();
    if (target.size() < size) return Status::insufficient_capacity;
    std::array<std::uint8_t, kMaximumCommandBytes> storage{};
    Output output(storage);
    put(output, 0, value.operation, 4); put(output, 4, 0, 4); put(output, 8, value.request_sequence, 8);
    std::copy(value.schema_sha256.begin(), value.schema_sha256.end(), output.begin() + 16);
    put(output, 48, kRequiredReplyCapacity, 4); put(output, 52, value.payload.size(), 4);
    std::copy(value.payload.begin(), value.payload.end(), output.begin() + kCommandFixedBytes);
    std::copy_n(storage.begin(), size, target.begin());
    written = size; return Status::ok;
}
Status encode_command(const Command& value, Bytes& output) { return owned_encode<kMaximumCommandBytes>(value, output, static_cast<Status (*)(const Command&, Output, std::size_t&) noexcept>(encode_command)); }
Status decode_command(View bytes, Command& output) {
    if (bytes.size() < kCommandFixedBytes || bytes.size() > kMaximumCommandBytes || u32(bytes, 4)
        || !get(bytes, 8, 8) || u32(bytes, 48) != kRequiredReplyCapacity) return Status::invalid;
    const auto* facts = operation_facts(u32(bytes, 0)); if (!facts) return Status::unsupported;
    const auto payload_size = u32(bytes, 52);
    if (payload_size > facts->maximum_input_bytes || bytes.size() != kCommandFixedBytes + payload_size
        || !std::equal(facts->schema_sha256.begin(), facts->schema_sha256.end(), bytes.begin() + 16)) return Status::invalid;
    auto status = payload_wire(facts->operation, bytes.subspan(kCommandFixedBytes)); if (status != Status::ok) return status;
    Command value{facts->operation, get(bytes, 8, 8), facts->schema_sha256, {bytes.begin() + kCommandFixedBytes, bytes.end()}};
    output = std::move(value); return Status::ok;
}
Status validate_command_result(const CommandResult& value) noexcept {
    if (!value.request_sequence || value.disposition > 2 || value.bytes_written || value.handled > 1
        || value.provider_status < -8 || value.provider_status > 0) return Status::invalid;
    if (value.disposition == 1) return value.provider_status == 0 ? Status::ok : Status::invalid;
    return value.provider_status != 0 && !value.handled ? Status::ok : Status::invalid;
}
Status encode_command_result(const CommandResult& value, Output output, std::size_t& written) noexcept {
    auto status = validate_command_result(value); if (status != Status::ok) return status;
    if (output.size() < kCommandResultBytes) return Status::insufficient_capacity;
    put(output, 0, static_cast<std::uint32_t>(value.provider_status), 4); put(output, 4, value.disposition, 4);
    put(output, 8, value.request_sequence, 8); put(output, 16, value.bytes_written, 4); put(output, 20, value.handled, 4);
    written = kCommandResultBytes; return Status::ok;
}
Status encode_command_result(const CommandResult& value, Bytes& output) { return owned_encode<kCommandResultBytes>(value, output, static_cast<Status (*)(const CommandResult&, Output, std::size_t&) noexcept>(encode_command_result)); }
Status decode_command_result(View bytes, CommandResult& output) noexcept {
    if (bytes.size() != kCommandResultBytes) return Status::invalid;
    const auto wire_status = u32(bytes, 0);
    // Avoid implementation-defined unsigned-to-signed conversion.
    const auto status = wire_status <= 0x7fffffffu ? static_cast<std::int32_t>(wire_status)
        : -1 - static_cast<std::int32_t>(0xffffffffu - wire_status);
    CommandResult value{status, u32(bytes, 4), get(bytes, 8, 8), u32(bytes, 16), u32(bytes, 20)};
    auto checked = validate_command_result(value); if (checked == Status::ok) output = value; return checked;
}

} // namespace foundation::appended::engine_input
