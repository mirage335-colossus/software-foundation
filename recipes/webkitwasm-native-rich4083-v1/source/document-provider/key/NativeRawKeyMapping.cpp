// SPDX-License-Identifier: CC0-1.0
#include "NativeRawKeyMapping.hpp"
#include <array>
#include <string_view>

namespace foundation::appended::ndv2_physical {
namespace {
unsigned functionNumber(std::string_view key) noexcept {
    if (key.size() < 2 || key.size() > 3 || key[0] != 'F'
        || key[1] < '1' || key[1] > '9') return 0;
    unsigned number = static_cast<unsigned>(key[1] - '0');
    if (key.size() == 3) {
        if (key[2] < '0' || key[2] > '9') return 0;
        number = number * 10 + static_cast<unsigned>(key[2] - '0');
    }
    return number <= 24 ? number : 0;
}
std::uint16_t virtualKey(std::string_view key, std::uint32_t location) noexcept {
    if (key == "Shift") return location == 1 ? 0xa0 : location == 2 ? 0xa1 : 0x10;
    if (key == "Control") return location == 1 ? 0xa2 : location == 2 ? 0xa3 : 0x11;
    if (key == "Alt" || key == "AltGraph") return location == 1 ? 0xa4 : location == 2 ? 0xa5 : 0x12;
    if (key == "Meta") return location == 2 ? 0x5c : 0x5b;
    if (location == 3 && key.size() == 1) {
        const auto c = key[0];
        if (c >= '0' && c <= '9') return static_cast<std::uint16_t>(0x60 + c - '0');
        switch (c) {
        case '*': return 0x6a; case '+': return 0x6b; case '-': return 0x6d;
        case '.': return 0x6e; case '/': return 0x6f;
        default: break;
        }
    }
    struct Named { std::string_view name; std::uint16_t value; };
    constexpr Named named[]{
        {"Backspace",8},{"Tab",9},{"Clear",12},{"Enter",13},{"Pause",19},{"CapsLock",20},
        {"Escape",27},{"PageUp",33},{"PageDown",34},{"End",35},{"Home",36},
        {"ArrowLeft",37},{"ArrowUp",38},{"ArrowRight",39},{"ArrowDown",40},
        {"PrintScreen",44},{"Insert",45},{"Delete",46},{"Help",47},{"ContextMenu",93},
        {"NumLock",144},{"ScrollLock",145},
    };
    for (const auto& entry : named) if (key == entry.name) return entry.value;
    if (const auto number = functionNumber(key)) return static_cast<std::uint16_t>(0x70 + number - 1);
    if (key.size() != 1) return 0;
    const auto c = static_cast<unsigned char>(key[0]);
    if (c >= 'a' && c <= 'z') return static_cast<std::uint16_t>(c - 'a' + 'A');
    if ((c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9')) return c;
    switch (c) {
    case ' ': return 0x20;
    case ';': case ':': return 0xba;
    case '=': case '+': return 0xbb;
    case ',': case '<': return 0xbc;
    case '-': case '_': return 0xbd;
    case '.': case '>': return 0xbe;
    case '/': case '?': return 0xbf;
    case '`': case '~': return 0xc0;
    case '[': case '{': return 0xdb;
    case '\\': case '|': return 0xdc;
    case ']': case '}': return 0xdd;
    case '\'': case '"': return 0xde;
    case '!': return '1'; case '@': return '2'; case '#': return '3';
    case '$': return '4'; case '%': return '5'; case '^': return '6';
    case '&': return '7'; case '*': return '8'; case '(': return '9'; case ')': return '0';
    default: return 0;
    }
}
std::string identifier(std::string_view key) {
    if (key == "Escape") return "U+001B";
    if (key == "Backspace") return "U+0008";
    if (key == "Tab") return "U+0009";
    if (key == "Delete") return "U+007F";
    if (key == "ArrowLeft") return "Left";
    if (key == "ArrowRight") return "Right";
    if (key == "ArrowUp") return "Up";
    if (key == "ArrowDown") return "Down";
    constexpr std::string_view retained[]{"Enter","PageUp","PageDown","Home","End",
        "Shift","Control","Alt","AltGraph","Meta","CapsLock","NumLock","ScrollLock"};
    for (auto name : retained) if (key == name) return std::string(key);
    if (functionNumber(key)) return std::string(key);
    if (key.size() == 1) {
        auto c = static_cast<unsigned char>(key[0]);
        if (c >= 0x20 && c <= 0x7e) {
            if (c >= 'a' && c <= 'z') c = static_cast<unsigned char>(c - 'a' + 'A');
            constexpr char hex[] = "0123456789ABCDEF";
            std::string result = "U+0000";
            result[4] = hex[c >> 4]; result[5] = hex[c & 15];
            return result;
        }
    }
    return "Unidentified";
}
} // namespace

std::optional<CompatibilityKey> mapCompatibilityKey(const engine_input::Key& key) {
    if (engine_input::validate_key(key) != engine_input::Status::ok) return std::nullopt;
    return CompatibilityKey{virtualKey(key.key, key.location), identifier(key.key), key.location == 3};
}
} // namespace foundation::appended::ndv2_physical
