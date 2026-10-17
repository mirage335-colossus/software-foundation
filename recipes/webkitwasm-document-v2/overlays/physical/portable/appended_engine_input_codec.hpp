// SPDX-License-Identifier: CC0-1.0
#pragma once

#include "appended_engine_input_profile.hpp"
#include <cstddef>
#include <span>
#include <vector>

namespace foundation::appended::engine_input {

using Bytes = std::vector<std::uint8_t>;
enum class Status { ok, invalid, unsupported, stale_context, invalid_transition, insufficient_capacity };
inline constexpr std::size_t kKeyFixedBytes = 32, kMaximumKeyBytes = 160;
inline constexpr std::size_t kFocusBytes = 32, kMouseBytes = 80;
inline constexpr std::size_t kCommandFixedBytes = 56, kMaximumCommandBytes = 216;
inline constexpr std::size_t kCommandResultBytes = 24;

struct Key {
    std::uint32_t phase{}, location{}, modifiers{}, repeat{};
    std::uint64_t input_context{};
    std::string key, code;
    friend bool operator==(const Key&, const Key&) = default;
};
struct Focus {
    std::uint32_t action{}, focused{}, active{}, cause{};
    std::uint64_t input_context{}, expected_context{};
    friend bool operator==(const Focus&, const Focus&) = default;
};
struct Mouse {
    std::uint32_t phase{}, button{}, buttons{}, clicks{}, modifiers{}, context_origin{};
    std::uint64_t input_context{}, capture_token{};
    double x{}, y{}, wheel_x{}, wheel_y{};
    friend bool operator==(const Mouse&, const Mouse&) = default;
};

Status validate_key(const Key&) noexcept;
Status validate_focus(const Focus&) noexcept;
Status validate_mouse(const Mouse&) noexcept;

// Exact LE values only. Rejection leaves every output byte/value unchanged.
// Owning overloads may throw on allocation, also without replacing the output.
Status encode_key(const Key&, std::span<std::uint8_t>, std::size_t& written) noexcept;
Status encode_focus(const Focus&, std::span<std::uint8_t>, std::size_t& written) noexcept;
Status encode_mouse(const Mouse&, std::span<std::uint8_t>, std::size_t& written) noexcept;
Status encode_key(const Key&, Bytes&);
Status encode_focus(const Focus&, Bytes&);
Status encode_mouse(const Mouse&, Bytes&);
Status decode_key(std::span<const std::uint8_t>, Key&);
Status decode_focus(std::span<const std::uint8_t>, Focus&) noexcept;
Status decode_mouse(std::span<const std::uint8_t>, Mouse&) noexcept;

// No native engine or Surface object is stored. The caller independently checks
// DocumentV1 and full GUI authority, then commits metadata before native entry.
// Rejected transitions leave all state unchanged. Capture tokens and contexts
// keep separate persistent high waters across retire_document/navigation.
// Ordinary focus loss/inactivation clears capture before caller cancellation,
// retaining the active context and last real point for that native operation.
struct State {
    std::uint64_t active_context{}, highest_context{}, capture_token{}, highest_capture_token{};
    std::uint32_t buttons{};
    bool focused{}, active{}, has_last_point{};
    double last_x{}, last_y{};
    friend bool operator==(const State&, const State&) = default;
};
Status accept_key(const State&, const Key&) noexcept;
Status accept_focus(State&, const Focus&) noexcept;
Status accept_mouse(State&, const Mouse&) noexcept;
void retire_document(State&) noexcept;
// DOM ordinal 0/1/2/3/4 -> held bit 1/4/2/8/16. Unknown ordinal -> zero.
std::uint32_t mouse_button_bit(std::uint32_t button) noexcept;
// Normal native held-button priority Left, Middle, Right, Back, Forward;
// -1 denotes idle/invalid. This is not the changed-button wire field.
std::int32_t native_move_button(std::uint32_t buttons) noexcept;

struct Command {
    std::uint32_t operation{};
    std::uint64_t request_sequence{};
    Digest schema_sha256{};
    Bytes payload;
    friend bool operator==(const Command&, const Command&) = default;
};
const OperationFacts* operation_facts(std::uint32_t operation) noexcept;
Status validate_command(const Command&) noexcept;
Status encode_command(const Command&, std::span<std::uint8_t>, std::size_t& written) noexcept;
Status encode_command(const Command&, Bytes&);
Status decode_command(std::span<const std::uint8_t>, Command&);

// This catalog has no reply payload. These are actual provider values, not the
// handled bit reinterpreted as a consumption disposition. Every sequence is u64.
// 0 = rejected (status -1..-8), 1 = consumed (status 0), 2 = consumed-unknown
// (status -1..-8). Rejected/unknown require handled=bytes_written=0.
struct CommandResult {
    std::int32_t provider_status{};
    std::uint32_t disposition{};
    std::uint64_t request_sequence{};
    std::uint32_t bytes_written{}, handled{};
    friend bool operator==(const CommandResult&, const CommandResult&) = default;
};
Status validate_command_result(const CommandResult&) noexcept;
Status encode_command_result(const CommandResult&, std::span<std::uint8_t>, std::size_t& written) noexcept;
Status encode_command_result(const CommandResult&, Bytes&);
Status decode_command_result(std::span<const std::uint8_t>, CommandResult&) noexcept;

} // namespace foundation::appended::engine_input
