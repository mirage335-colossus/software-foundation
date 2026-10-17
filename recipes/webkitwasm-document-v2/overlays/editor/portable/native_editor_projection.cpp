// SPDX-License-Identifier: CC0-1.0
#include "native_editor_projection.hpp"
#include <algorithm>

namespace foundation::ui::native_editor {
std::optional<NativeTextProjection> NativeTextProjection::create(std::u16string_view text, std::uint32_t maximum) {
    if (!maximum || maximum > 65536 || text.size() > std::size_t(maximum) * 2) return {};
    NativeTextProjection result;
    result.native_ = text;
    result.boundaries_.push_back({0, 0});
    for (std::uint32_t i = 0; i < text.size();) {
        std::uint32_t scalar = text[i++];
        if (!scalar) return {};
        if (scalar == '\r') {
            if (i < text.size() && text[i] == '\n') ++i;
            scalar = '\n';
        } else if (scalar >= 0xd800 && scalar <= 0xdbff) {
            if (i == text.size() || text[i] < 0xdc00 || text[i] > 0xdfff) return {};
            scalar = 0x10000 + ((scalar - 0xd800) << 10) + text[i++] - 0xdc00;
        } else if (scalar >= 0xdc00 && scalar <= 0xdfff) return {};
        const unsigned count = scalar < 0x80 ? 1 : scalar < 0x800 ? 2 : scalar < 0x10000 ? 3 : 4;
        if (result.utf8_.size() + count > maximum) return {};
        if (count == 1) result.utf8_.push_back(static_cast<char>(scalar));
        else {
            result.utf8_.push_back(static_cast<char>((count == 2 ? 0xc0 : count == 3 ? 0xe0 : 0xf0) | (scalar >> (6 * (count - 1)))));
            for (unsigned j = count - 1; j; --j)
                result.utf8_.push_back(static_cast<char>(0x80 | ((scalar >> (6 * (j - 1))) & 0x3f)));
        }
        result.boundaries_.push_back({static_cast<std::uint32_t>(result.utf8_.size()), i});
    }
    return result;
}
std::optional<NativeUnitRange> NativeTextProjection::native_range(gui_surface::ByteRange value) const noexcept {
    if (value.begin > value.end || value.end > utf8_.size()) return {};
    auto find = [&](std::uint32_t byte) -> std::optional<std::uint32_t> {
        auto it = std::lower_bound(boundaries_.begin(), boundaries_.end(), byte, [](const Boundary& b, auto v) { return b.byte < v; });
        if (it == boundaries_.end() || it->byte != byte) return {};
        return it->unit;
    };
    auto begin = find(static_cast<std::uint32_t>(value.begin)), end = find(static_cast<std::uint32_t>(value.end));
    if (!begin || !end) return {};
    return NativeUnitRange{*begin, *end};
}
std::optional<gui_surface::ByteRange> NativeTextProjection::projected_range(NativeUnitRange value) const noexcept {
    if (value.begin > value.end) return {};
    auto find = [&](std::uint32_t unit) -> std::optional<std::uint32_t> {
        auto it = std::lower_bound(boundaries_.begin(), boundaries_.end(), unit, [](const Boundary& b, auto v) { return b.unit < v; });
        if (it == boundaries_.end() || it->unit != unit) return {};
        return it->byte;
    };
    auto begin = find(value.begin), end = find(value.end);
    if (!begin || !end) return {};
    return gui_surface::ByteRange{*begin, *end};
}
}
