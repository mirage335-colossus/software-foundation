// SPDX-License-Identifier: CC0-1.0
#include "shared/native_editor_projection.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace {
using foundation::gui_surface::ByteRange;
using foundation::ui::native_editor::NativeTextProjection;
using foundation::ui::native_editor::NativeUnitRange;
std::size_t assertions{};

void check(bool value, const char* reason) {
    ++assertions;
    if (!value) throw std::runtime_error(reason);
}
NativeTextProjection project(std::u16string_view text, std::uint32_t maximum = 65536) {
    auto value = NativeTextProjection::create(text, maximum);
    check(bool(value), "valid native passage did not project");
    return std::move(*value);
}
struct Boundary { std::size_t byte; std::uint32_t unit; };
constexpr std::array<Boundary, 12> boundaries{{
    {0,0}, {1,1}, {2,3}, {3,4}, {4,5}, {5,6}, {6,7}, {7,8},
    {11,10}, {13,11}, {16,12}, {17,13},
}};
constexpr std::u16string_view mixed_native = u"A\r\nB\rC\nD\U0001f642\u00e9\u20acZ";
constexpr std::string_view mixed_utf8 = "A\nB\nC\nD\xf0\x9f\x99\x82\xc3\xa9\xe2\x82\xac" "Z";

void normalization_and_exact_boundaries() {
    const auto value = project(mixed_native);
    check(value.native() == mixed_native && value.utf8() == mixed_utf8,
        "CRLF/CR normalization changed native bytes or UTF-8 scalar encoding");
    check(value.native().size() == 13 && value.utf8().size() == 17, "independent mixed fixture extents changed");
    for (std::size_t first = 0; first < boundaries.size(); ++first) {
        for (std::size_t last = first; last < boundaries.size(); ++last) {
            const ByteRange bytes{boundaries[first].byte, boundaries[last].byte};
            const NativeUnitRange units{boundaries[first].unit, boundaries[last].unit};
            check(value.native_range(bytes) == units, "projected range did not map to exact original UTF-16 boundaries");
            check(value.projected_range(units) == bytes, "native range did not map to exact projected scalar boundaries");
        }
    }
    check(value.native_range({1,2}) == NativeUnitRange{1,3}, "projected LF did not select both original CRLF units");
    check(value.native_range({3,4}) == NativeUnitRange{4,5}, "projected LF did not retain original lone CR extent");
    check(value.native_range({5,6}) == NativeUnitRange{6,7}, "original LF extent changed during normalization");
}

void all_interior_endpoints_reject() {
    const auto value = project(mixed_native);
    for (std::size_t byte = 0; byte <= value.utf8().size(); ++byte) {
        const bool valid = std::any_of(boundaries.begin(), boundaries.end(), [=](Boundary b) { return b.byte == byte; });
        check(bool(value.native_range({byte,byte})) == valid, "UTF-8 interior caret was accepted or scalar caret rejected");
        check(bool(value.native_range({0,byte})) == valid, "UTF-8 interior range end was accepted");
        check(bool(value.native_range({byte,value.utf8().size()})) == valid, "UTF-8 interior range begin was accepted");
    }
    for (std::uint32_t unit = 0; unit <= value.native().size(); ++unit) {
        const bool valid = std::any_of(boundaries.begin(), boundaries.end(), [=](Boundary b) { return b.unit == unit; });
        check(bool(value.projected_range({unit,unit})) == valid, "UTF-16 half-scalar/CRLF interior caret was accepted");
        check(bool(value.projected_range({0,unit})) == valid, "UTF-16 half-scalar/CRLF interior range end was accepted");
        check(bool(value.projected_range({unit,static_cast<std::uint32_t>(value.native().size())})) == valid,
            "UTF-16 half-scalar/CRLF interior range begin was accepted");
    }
    check(!value.projected_range({2,2}) && !value.projected_range({9,9}),
        "original CRLF interior or astral surrogate midpoint acquired a mapping");
}

void scalar_extremes_and_combining_boundaries() {
    const auto extremes = project(u"\U00010000\U0010ffff");
    check(extremes.utf8() == "\xf0\x90\x80\x80\xf4\x8f\xbf\xbf", "minimum/maximum astral scalar UTF-8 bytes changed");
    check(extremes.native_range({0,4}) == NativeUnitRange{0,2} &&
        extremes.native_range({4,8}) == NativeUnitRange{2,4}, "astral native ranges lost their two-unit extents");
    check(!extremes.projected_range({1,2}) && !extremes.projected_range({2,3}), "astral half range was accepted");
    const auto bmp = project(u"\u007f\u0080\u07ff\u0800\ud7ff\ue000\uffff");
    check(bmp.utf8() == "\x7f\xc2\x80\xdf\xbf\xe0\xa0\x80\xed\x9f\xbf\xee\x80\x80\xef\xbf\xbf",
        "BMP UTF-8 width transitions or scalars adjacent to surrogate space changed");
    const auto combining = project(u"e\u0301");
    check(combining.utf8() == "e\xcc\x81" && combining.native_range({1,3}) == NativeUnitRange{1,2} &&
        combining.projected_range({1,1}) == ByteRange{1,1}, "scalar boundaries were incorrectly treated as grapheme boundaries");
    const auto unchanged = project(u"\t\n\u0085\u2028\u2029");
    check(unchanged.utf8() == "\t\n\xc2\x85\xe2\x80\xa8\xe2\x80\xa9",
        "normalization altered non-CR line separators or tab");
}

void malformed_utf16_and_nul_reject() {
    const std::vector<std::u16string> malformed{
        {char16_t{0xd800}}, {char16_t{0xdbff}}, {char16_t{0xdc00}}, {char16_t{0xdfff}},
        {char16_t{0xd800},u'x'}, {char16_t{0xd800},char16_t{0xdbff}},
        {char16_t{0xdc00},char16_t{0xd800}}, {u'x',char16_t{0xdc00}},
        {char16_t{0xd800},u'\r',u'\n'},
        {char16_t{0xd800},char16_t{0xdc00},char16_t{0xdc00}},
        {u'\r',u'\n',char16_t{0xdbff}},
    };
    for (const auto& text : malformed) check(!NativeTextProjection::create(text), "malformed UTF-16 was accepted");
    for (const auto& text : {std::u16string(1,u'\0'), std::u16string(u"A\0B",3),
            std::u16string(u"\r\0\n",3), std::u16string(u"\U0001f642\0",3)})
        check(!NativeTextProjection::create(text), "embedded original NUL was accepted");
}

void empty_reversed_and_wide_ranges() {
    const auto empty = project(u"");
    check(empty.native().empty() && empty.utf8().empty() && empty.native_range({0,0}) == NativeUnitRange{0,0} &&
        empty.projected_range({0,0}) == ByteRange{0,0}, "empty passage lost its sole valid boundary");
    check(!empty.native_range({0,1}) && !empty.projected_range({0,1}), "empty passage accepted an out-of-range endpoint");
    const auto value = project(u"x\r\n\U0001f642");
    const auto size_max = std::numeric_limits<std::size_t>::max();
    const auto units_max = std::numeric_limits<std::uint32_t>::max();
    for (const ByteRange bytes : {ByteRange{1,0}, ByteRange{value.utf8().size(),0},
            ByteRange{0,value.utf8().size()+1}, ByteRange{size_max,size_max}, ByteRange{0,size_max}, ByteRange{size_max,0}})
        check(!value.native_range(bytes), "reversed/oversized/SIZE_MAX byte range was narrowed or accepted");
    for (const NativeUnitRange units : {NativeUnitRange{1,0}, NativeUnitRange{5,0},
            NativeUnitRange{0,6}, NativeUnitRange{units_max,units_max}, NativeUnitRange{0,units_max}, NativeUnitRange{units_max,0}})
        check(!value.projected_range(units), "reversed/oversized/UINT32_MAX native range was accepted");
    check(value.native_range({value.utf8().size(),value.utf8().size()}) == NativeUnitRange{5,5} &&
        value.projected_range({5,5}) == ByteRange{value.utf8().size(),value.utf8().size()}, "final caret boundary was rejected");
}

std::u16string replace_original(const NativeTextProjection& value, ByteRange range, std::u16string_view replacement) {
    const auto native = value.native_range(range);
    check(bool(native), "replacement fixture did not select exact scalar boundaries");
    auto result = value.native();
    result.replace(native->begin,native->end-native->begin,replacement);
    return result;
}
void replacements_preserve_original_flanks() {
    const auto value = project(u"L\r\nA\rB\U0001f642R\r\nZ");
    check(value.utf8() == "L\nA\nB\xf0\x9f\x99\x82" "R\nZ", "replacement fixture projection changed");
    const auto middle = replace_original(value,{2,5},u"x\n");
    check(middle == u"L\r\nx\n\U0001f642R\r\nZ", "replacement normalized an untouched CRLF/native flank");
    check(project(middle).utf8() == "L\nx\n\xf0\x9f\x99\x82" "R\nZ", "replacement readback did not normalize only its projection");
    check(replace_original(value,{5,9},u"Q") == u"L\r\nA\rBQR\r\nZ", "astral replacement cut a surrogate or normalized a lone CR flank");
    check(replace_original(value,{9,9},u"\r\n") == u"L\r\nA\rB\U0001f642\r\nR\r\nZ",
        "scalar-boundary insertion changed either original flank");
    check(replace_original(value,{1,2},u"") == u"LA\rB\U0001f642R\r\nZ", "deleting projected LF failed to remove exactly the original CRLF");
    check(value.native() == u"L\r\nA\rB\U0001f642R\r\nZ", "consumer replacement mutated the immutable original projection");
}

void owned_native_and_normalized_identity() {
    std::u16string source = u"before\r\n\U0001f642";
    const auto value = project(source); const auto copied = value;
    source.assign(200,u'x'); source.clear();
    check(value.native() == u"before\r\n\U0001f642" && value.utf8() == "before\n\xf0\x9f\x99\x82" && copied == value,
        "projection/copy borrowed the mutable native source");
    const auto crlf = project(u"\r\n"), lf = project(u"\n"), cr = project(u"\r");
    check(crlf.utf8() == lf.utf8() && lf.utf8() == cr.utf8() && crlf != lf && crlf != cr && lf != cr,
        "equal normalized text erased exact original identity/flank mapping");
    check(crlf.native_range({0,1}) == NativeUnitRange{0,2} && lf.native_range({0,1}) == NativeUnitRange{0,1},
        "same normalized LF reused a different original passage's mapping");
}

void bounded_projection_limits() {
    check(!NativeTextProjection::create(u"",0) && !NativeTextProjection::create(u"x",0) &&
        !NativeTextProjection::create(u"",65537) && !NativeTextProjection::create(u"",std::numeric_limits<std::uint32_t>::max()),
        "zero/oversized projection limit was accepted");
    check(project(u"\r\n",1).utf8() == "\n" && !NativeTextProjection::create(u"\r\r",1),
        "byte limit counted original CRLF units or ignored projected bytes");
    check(!NativeTextProjection::create(u"\u00e9",1) && project(u"\u00e9",2).utf8().size() == 2 &&
        !NativeTextProjection::create(u"\u20ac",2) && project(u"\u20ac",3).utf8().size() == 3 &&
        !NativeTextProjection::create(u"\U0001f642",3) && project(u"\U0001f642",4).utf8().size() == 4,
        "UTF-8 byte limit admitted a partial scalar or charged UTF-16 units");
    const std::u16string ascii(65536,u'x');
    check(project(ascii).utf8().size() == 65536 && !NativeTextProjection::create(ascii,65535), "maximum projected byte edge changed");
    std::u16string paired;
    paired.reserve(131072);
    for (unsigned i = 0; i < 65536; ++i) paired += u"\r\n";
    const auto value = project(paired);
    check(value.native().size() == 131072 && value.utf8() == std::string(65536,'\n') &&
        value.native_range({0,65536}) == NativeUnitRange{0,131072} &&
        value.projected_range({0,131072}) == ByteRange{0,65536}, "maximum compressed passage lost original extents");
    paired += u"\r\n";
    check(!NativeTextProjection::create(paired), "over-limit CRLF passage was accepted");
}
} // namespace

int main() {
    const std::array<std::pair<const char*,void(*)()>,8> cases{{
        {"normalization and exact boundaries",normalization_and_exact_boundaries},
        {"interior endpoint rejection",all_interior_endpoints_reject},
        {"scalar extremes and combining boundaries",scalar_extremes_and_combining_boundaries},
        {"malformed UTF16 and NUL",malformed_utf16_and_nul_reject},
        {"empty reversed and wide ranges",empty_reversed_and_wide_ranges},
        {"replacement preserves original flanks",replacements_preserve_original_flanks},
        {"ownership and native identity",owned_native_and_normalized_identity},
        {"projection limits",bounded_projection_limits},
    }};
    std::size_t passed{};
    for (const auto& [name,test] : cases) {
        try { test(); ++passed; std::cout << "PASS " << name << '\n'; }
        catch (const std::exception& error) {
            std::cerr << "FAIL " << name << ": " << error.what() << '\n'; return 1;
        }
    }
    std::cout << passed << " groups passed, " << assertions << " assertions, 0 skips\n";
}
