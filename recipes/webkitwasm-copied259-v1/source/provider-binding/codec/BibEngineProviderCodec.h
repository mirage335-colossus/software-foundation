// SPDX-License-Identifier: CC0-1.0
// Source-only input decoder candidate; no engine execution is supplied here.
#pragma once

#include "foundation/appended/engine_provider.h"

#include <cstdint>
#include <string>
#include <variant>

namespace bib::provider_candidate::codec {

inline constexpr std::uint32_t maximum_key_bytes = 33120;
inline constexpr std::uint32_t maximum_focus_bytes = 16;
inline constexpr std::uint32_t maximum_mouse_bytes = 72;
// Negotiated positive scratch capacity for the outer provider guard; these
// commands still return no reply payload bytes.
inline constexpr std::uint32_t required_reply_capacity = 16;

enum class KeyPhase : std::uint32_t { down = 0, up = 1, committed_text = 2 };

struct KeyInput {
    KeyPhase phase{};
    std::uint32_t location{};
    std::uint32_t modifiers{};
    bool repeat{};
    std::uint32_t virtual_key{};
    std::string key;
    std::string code;
    std::string text;
};

enum class FocusCause : std::uint32_t { direct = 0, external = 3 };

struct FocusInput {
    bool focused{};
    bool active{};
    FocusCause cause{};
};

enum class MousePhase : std::uint32_t {
    move = 0, down = 1, up = 2, wheel = 3, cancel = 4
};

// The wire kind must be mouse (zero). This logical ID is exactly one and must
// map to WebCore::mousePointerID; it is never a raw native pointer ID. Stateful
// held-button and modifier transition validation belongs to the binding.
struct MouseInput {
    MousePhase phase{};
    std::uint32_t button{};
    std::uint32_t buttons{};
    std::uint32_t clicks{};
    std::uint32_t modifiers{};
    std::uint64_t logical_pointer_id{};
    double x{};
    double y{};
    double wheel_x{};
    double wheel_y{};
};

using Input = std::variant<KeyInput, FocusInput, MouseInput>;

// Decode an exact little-endian scalar payload. All string fields are owned
// copies and strictly valid UTF-8 without NUL. Output is unchanged on failure.
// Returns BIB_ENGINE_OK, INVALID, UNSUPPORTED or LIMIT (allocation failure).
// No host callback, engine operation, or input transition occurs here.
std::int32_t decode(std::uint32_t operation, const BibEngineBytesV1& payload,
    Input& output) noexcept;

} // namespace bib::provider_candidate::codec
