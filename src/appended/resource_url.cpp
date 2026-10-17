#include <foundation/appended/resource_url.hpp>

// Normalize final engine-resolved app URLs to immutable package resource keys.

#include <algorithm>
#include <cstdint>
#include <utility>

namespace foundation::appended {
namespace {

ResourceUrl failure(ResourceUrlError error) { return {error, {}}; }

bool authority(std::string_view value) noexcept {
    return value.size() == 64 && std::all_of(value.begin(), value.end(), [](char ch) {
        return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
    });
}

int hex(char ch) noexcept {
    if (ch >= '0' && ch <= '9') return ch - '0';
    if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
    if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
    return -1;
}

bool unreserved(unsigned char byte) noexcept {
    return (byte >= 'a' && byte <= 'z') || (byte >= 'A' && byte <= 'Z') ||
           (byte >= '0' && byte <= '9') || byte == '-' || byte == '.' ||
           byte == '_' || byte == '~';
}

ResourceUrlError validate_utf8(std::string_view text) noexcept {
    std::size_t position = 0;
    while (position < text.size()) {
        const auto first = static_cast<unsigned char>(text[position++]);
        std::uint32_t scalar = first;
        if (first >= 0x80) {
            unsigned count = 0;
            std::uint32_t minimum = 0;
            if (first >= 0xc2 && first <= 0xdf) {
                count = 1; scalar = first & 0x1f; minimum = 0x80;
            } else if (first >= 0xe0 && first <= 0xef) {
                count = 2; scalar = first & 0x0f; minimum = 0x800;
            } else if (first >= 0xf0 && first <= 0xf4) {
                count = 3; scalar = first & 0x07; minimum = 0x10000;
            } else return ResourceUrlError::invalid_encoding;
            if (count > text.size() - position) return ResourceUrlError::invalid_encoding;
            for (unsigned n = 0; n < count; ++n) {
                const auto next = static_cast<unsigned char>(text[position++]);
                if ((next & 0xc0) != 0x80) return ResourceUrlError::invalid_encoding;
                scalar = (scalar << 6) | (next & 0x3f);
            }
            if (scalar < minimum || scalar > 0x10ffff ||
                (scalar >= 0xd800 && scalar <= 0xdfff))
                return ResourceUrlError::invalid_encoding;
        }
        // Unicode Cc: C0, DEL and C1. Surrogates were rejected above.
        if (scalar < 0x20 || (scalar >= 0x7f && scalar <= 0x9f))
            return ResourceUrlError::invalid_path;
    }
    return ResourceUrlError::none;
}

bool dos_name(std::string_view segment) {
    const auto end = segment.find('.');
    std::string base(segment.substr(0, end));
    for (auto& ch : base)
        if (ch >= 'A' && ch <= 'Z') ch = static_cast<char>(ch - 'A' + 'a');
    if (base == "con" || base == "prn" || base == "aux" || base == "nul") return true;
    if (!base.starts_with("com") && !base.starts_with("lpt")) return false;
    const auto suffix = std::string_view(base).substr(3);
    // Match the existing project path policy, including Windows' superscript
    // digit aliases. These cannot occur in current ASCII-only package keys.
    return (suffix.size() == 1 && suffix[0] >= '1' && suffix[0] <= '9') ||
           suffix == "\xc2\xb9" || suffix == "\xc2\xb2" || suffix == "\xc2\xb3";
}

ResourceUrlError validate_path(std::string_view path) {
    if (!path.starts_with("web/")) return ResourceUrlError::invalid_path;
    if (path.find_first_of("\\:%?#<>\"|*") != std::string_view::npos)
        return ResourceUrlError::invalid_path;
    const auto encoding = validate_utf8(path);
    if (encoding != ResourceUrlError::none) return encoding;
    std::size_t start = 0, depth = 0;
    while (start <= path.size()) {
        const auto end = path.find('/', start);
        const auto segment = path.substr(start, end == std::string_view::npos ? end : end - start);
        if (segment.empty() || segment == "." || segment == ".." ||
            segment.back() == '.' || segment.back() == ' ' || dos_name(segment))
            return ResourceUrlError::invalid_path;
        if (++depth > max_resource_path_segments) return ResourceUrlError::limit_exceeded;
        if (end == std::string_view::npos) break;
        start = end + 1;
    }
    return ResourceUrlError::none;
}

} // namespace

ResourceUrl normalize_app_resource_url(std::string_view url, std::string_view exact_authority) {
    if (url.size() > max_resource_url_bytes) return failure(ResourceUrlError::limit_exceeded);
    if (!authority(exact_authority)) return failure(ResourceUrlError::invalid_authority);
    if (!url.starts_with("app://") || std::any_of(url.begin(), url.end(), [](unsigned char byte) {
            return byte < 0x20 || byte == 0x7f;
        })) return failure(ResourceUrlError::invalid_url);
    constexpr std::size_t authority_start = 6;
    const auto authority_end = url.find_first_of("/?#", authority_start);
    if (authority_end == std::string_view::npos || url[authority_end] != '/')
        return failure(ResourceUrlError::invalid_url);
    const auto actual_authority = url.substr(authority_start, authority_end - authority_start);
    if (!authority(actual_authority)) return failure(ResourceUrlError::invalid_authority);
    if (actual_authority != exact_authority) return failure(ResourceUrlError::origin_mismatch);
    const auto suffix = url.find_first_of("?#", authority_end);
    const auto encoded = url.substr(authority_end + 1,
        suffix == std::string_view::npos ? suffix : suffix - authority_end - 1);
    std::string path;
    path.reserve(std::min(encoded.size(), max_resource_path_bytes));
    for (std::size_t position = 0; position < encoded.size(); ++position) {
        auto byte = static_cast<unsigned char>(encoded[position]);
        if (byte == '%') {
            if (encoded.size() - position < 3) return failure(ResourceUrlError::invalid_encoding);
            const auto high = hex(encoded[position + 1]), low = hex(encoded[position + 2]);
            if (high < 0 || low < 0) return failure(ResourceUrlError::invalid_encoding);
            byte = static_cast<unsigned char>((high << 4) | low);
            if (byte == '/' || byte == '\\' || byte == '%' || unreserved(byte))
                return failure(ResourceUrlError::invalid_encoding);
            position += 2;
        } else if (byte == ' ') {
            // A serialized engine URL spells a filename space as %20.
            return failure(ResourceUrlError::invalid_url);
        }
        if (path.size() == max_resource_path_bytes) return failure(ResourceUrlError::limit_exceeded);
        path.push_back(static_cast<char>(byte));
    }
    const auto error = validate_path(path);
    if (error != ResourceUrlError::none) return failure(error);
    return {ResourceUrlError::none, std::move(path)};
}

} // namespace foundation::appended
