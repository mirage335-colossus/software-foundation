// SPDX-License-Identifier: CC0-1.0
#pragma once
#include "appended_engine_input_codec.hpp"
#include <cstdint>
#include <optional>
#include <string>
namespace foundation::appended::ndv2_physical {
struct CompatibilityKey {
    std::uint16_t virtual_key{};
    std::string identifier;
    bool keypad{};
    friend bool operator==(const CompatibilityKey&, const CompatibilityKey&) = default;
};
// Pure deterministic legacy compatibility policy, never original OS metadata.
// No physical-code guessing, text generation, normalization or phase fallback.
// Every valid modern Key maps, including unknown/multiscalar keys and all four
// locations. Invalid records return nullopt. Allocation may throw.
std::optional<CompatibilityKey> mapCompatibilityKey(const engine_input::Key&);
// Numeric image of the pinned WebCore enum, verified by native static_asserts.
// Caller supplies validated portable bits 0..31. All 32 combinations remain
// independent: Shift1->8, Control2->2, Alt4->1, Meta8->4, AltGraph16->32.
constexpr std::uint32_t webCoreModifierBits(std::uint32_t bits) noexcept {
    return ((bits & 1u) << 3) | (bits & 2u) | ((bits & 4u) >> 2)
        | ((bits & 8u) >> 1) | ((bits & 16u) << 1);
}
} // namespace foundation::appended::ndv2_physical
