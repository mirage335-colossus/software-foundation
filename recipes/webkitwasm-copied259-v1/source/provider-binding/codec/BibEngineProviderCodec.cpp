// SPDX-License-Identifier: CC0-1.0
#include "BibEngineProviderCodec.h"

#include <bit>
#include <cmath>
#include <cstddef>
#include <limits>
#include <new>
#include <type_traits>
#include <utility>

namespace bib::provider_candidate::codec {
namespace {

static_assert(sizeof(double) == 8 && std::numeric_limits<double>::is_iec559
    && std::numeric_limits<double>::radix == 2
    && std::numeric_limits<double>::digits == 53
    && std::numeric_limits<double>::max_exponent == 1024,
    "The scalar input wire format requires IEEE 754 binary64");
static_assert(std::is_nothrow_move_assignable_v<Input>,
    "Publishing a fully decoded input must not throw");

class Reader {
public:
    explicit Reader(const std::uint8_t* bytes) : m_bytes(bytes) { }

    std::uint32_t u32() noexcept
    {
        std::uint32_t result = 0;
        for (unsigned i = 0; i < 4; ++i)
            result |= static_cast<std::uint32_t>(*m_bytes++) << (8 * i);
        return result;
    }

    std::uint64_t u64() noexcept
    {
        std::uint64_t result = 0;
        for (unsigned i = 0; i < 8; ++i)
            result |= static_cast<std::uint64_t>(*m_bytes++) << (8 * i);
        return result;
    }

    double f64() noexcept { return std::bit_cast<double>(u64()); }

    const std::uint8_t* bytes() const noexcept { return m_bytes; }

private:
    const std::uint8_t* m_bytes;
};

bool valid_utf8_without_nul(const std::uint8_t* bytes, std::uint32_t length) noexcept
{
    for (std::uint32_t offset = 0; offset < length;) {
        const std::uint8_t first = bytes[offset++];
        if (!first)
            return false;
        if (first < 0x80)
            continue;

        std::uint32_t scalar = 0;
        std::uint32_t minimum = 0;
        std::uint32_t remaining = 0;
        if (first >= 0xc2 && first <= 0xdf) {
            scalar = first & 0x1fu;
            minimum = 0x80;
            remaining = 1;
        } else if (first >= 0xe0 && first <= 0xef) {
            scalar = first & 0x0fu;
            minimum = 0x800;
            remaining = 2;
        } else if (first >= 0xf0 && first <= 0xf4) {
            scalar = first & 0x07u;
            minimum = 0x10000;
            remaining = 3;
        } else
            return false;

        if (remaining > length - offset)
            return false;
        for (std::uint32_t i = 0; i < remaining; ++i) {
            const std::uint8_t continuation = bytes[offset++];
            if ((continuation & 0xc0u) != 0x80u)
                return false;
            scalar = (scalar << 6) | (continuation & 0x3fu);
        }
        if (scalar < minimum || scalar > 0x10ffff
            || (scalar >= 0xd800 && scalar <= 0xdfff))
            return false;
    }
    return true;
}

bool decode_key(const BibEngineBytesV1& payload, Input& decoded)
{
    if (payload.length < 32 || payload.length > maximum_key_bytes)
        return false;

    Reader reader(payload.data);
    const auto phase = reader.u32();
    const auto location = reader.u32();
    const auto modifiers = reader.u32();
    const auto repeat = reader.u32();
    const auto virtual_key = reader.u32();
    const auto key_length = reader.u32();
    const auto code_length = reader.u32();
    const auto text_length = reader.u32();
    if (phase > 2 || location || (modifiers & ~15u) || repeat > 1
        || virtual_key > 65535 || key_length > 256 || code_length > 64
        || text_length > 32768)
        return false;
    if (payload.length != 32 + key_length + code_length + text_length)
        return false;
    if (phase != 2 && text_length)
        return false;
    if (phase == 2 && (key_length || code_length || location || repeat
        || virtual_key || modifiers || !text_length))
        return false;

    const auto* key = reader.bytes();
    const auto* code = key + key_length;
    const auto* text = code + code_length;
    if (!valid_utf8_without_nul(key, key_length)
        || !valid_utf8_without_nul(code, code_length)
        || !valid_utf8_without_nul(text, text_length))
        return false;

    KeyInput result;
    result.phase = static_cast<KeyPhase>(phase);
    result.location = location;
    result.modifiers = modifiers;
    result.repeat = repeat != 0;
    result.virtual_key = virtual_key;
    result.key.assign(reinterpret_cast<const char*>(key), key_length);
    result.code.assign(reinterpret_cast<const char*>(code), code_length);
    result.text.assign(reinterpret_cast<const char*>(text), text_length);
    decoded = std::move(result);
    return true;
}

bool decode_focus(const BibEngineBytesV1& payload, Input& decoded) noexcept
{
    if (payload.length != maximum_focus_bytes)
        return false;
    Reader reader(payload.data);
    const auto focused = reader.u32();
    const auto active = reader.u32();
    const auto cause = reader.u32();
    const auto reserved = reader.u32();
    if (focused > 1 || active > 1 || (cause != 0 && cause != 3) || reserved)
        return false;
    decoded = FocusInput { focused != 0, active != 0, static_cast<FocusCause>(cause) };
    return true;
}

bool bounded_f64(double value) noexcept
{
    return std::isfinite(value) && std::abs(value) <= 2147483647.0;
}

bool decode_mouse(const BibEngineBytesV1& payload, Input& decoded) noexcept
{
    if (payload.length != maximum_mouse_bytes)
        return false;
    Reader reader(payload.data);
    const auto phase = reader.u32();
    const auto kind = reader.u32();
    const auto button = reader.u32();
    const auto buttons = reader.u32();
    const auto clicks = reader.u32();
    const auto modifiers = reader.u32();
    const auto reserved0 = reader.u32();
    const auto reserved1 = reader.u32();
    const auto logical_pointer_id = reader.u64();
    const double x = reader.f64();
    const double y = reader.f64();
    const double wheel_x = reader.f64();
    const double wheel_y = reader.f64();
    if (phase > 4 || kind || button > 2 || (buttons & ~7u)
        || (modifiers & ~15u) || reserved0 || reserved1 || logical_pointer_id != 1
        || !bounded_f64(x) || !bounded_f64(y)
        || !bounded_f64(wheel_x) || !bounded_f64(wheel_y))
        return false;
    if (phase == 1 || phase == 2) {
        if (clicks < 1 || clicks > 3)
            return false;
    } else if (button || clicks)
        return false;
    if (phase != 3 && (wheel_x != 0 || wheel_y != 0))
        return false;
    if (phase == 4 && (buttons || modifiers))
        return false;

    decoded = MouseInput { static_cast<MousePhase>(phase), button, buttons,
        clicks, modifiers, logical_pointer_id, x, y, wheel_x, wheel_y };
    return true;
}

} // namespace

std::int32_t decode(std::uint32_t operation, const BibEngineBytesV1& payload,
    Input& output) noexcept
{
    if (operation != BIB_ENGINE_COMMAND_KEY && operation != BIB_ENGINE_COMMAND_FOCUS
        && operation != BIB_ENGINE_COMMAND_POINTER)
        return BIB_ENGINE_UNSUPPORTED;
    if (payload.reserved || (payload.length && !payload.data))
        return BIB_ENGINE_INVALID;
    try {
        Input decoded;
        bool valid = false;
        switch (operation) {
        case BIB_ENGINE_COMMAND_KEY:
            valid = decode_key(payload, decoded);
            break;
        case BIB_ENGINE_COMMAND_FOCUS:
            valid = decode_focus(payload, decoded);
            break;
        case BIB_ENGINE_COMMAND_POINTER:
            valid = decode_mouse(payload, decoded);
            break;
        default:
            return BIB_ENGINE_UNSUPPORTED;
        }
        if (!valid)
            return BIB_ENGINE_INVALID;
        output = std::move(decoded);
        return BIB_ENGINE_OK;
    } catch (const std::bad_alloc&) {
        return BIB_ENGINE_LIMIT;
    } catch (...) {
        return BIB_ENGINE_INVALID;
    }
}

} // namespace bib::provider_candidate::codec
