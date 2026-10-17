// SPDX-License-Identifier: CC0-1.0
#pragma once
#include <foundation/gui/surface.hpp>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace foundation::ui::native_editor {
struct NativeUnitRange {
    std::uint32_t begin{}, end{};
    bool operator==(const NativeUnitRange&) const = default;
};
// One exact native UTF-16 passage and its textarea-compatible projection. Only
// scalar boundaries are mapped. CRLF is one projected LF; its interior has no
// mapping. Replacements use returned original offsets, never normalized flanks.
class NativeTextProjection final {
public:
    static std::optional<NativeTextProjection> create(std::u16string_view, std::uint32_t maximum_bytes = 65536);
    const std::u16string& native() const noexcept { return native_; }
    const std::string& utf8() const noexcept { return utf8_; }
    std::optional<NativeUnitRange> native_range(gui_surface::ByteRange) const noexcept;
    std::optional<gui_surface::ByteRange> projected_range(NativeUnitRange) const noexcept;
    bool operator==(const NativeTextProjection&) const = default;
private:
    struct Boundary {
        std::uint32_t byte{}, unit{};
        bool operator==(const Boundary&) const = default;
    };
    std::u16string native_;
    std::string utf8_;
    std::vector<Boundary> boundaries_;
};
}
