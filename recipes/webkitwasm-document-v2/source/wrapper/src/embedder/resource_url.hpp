#pragma once

#include <cstddef>
#include <string>
#include <string_view>

namespace foundation::appended::candidate {

inline constexpr std::size_t max_resource_url_bytes = 4096;
inline constexpr std::size_t max_resource_path_bytes = 240;
inline constexpr std::size_t max_resource_path_segments = 16;

enum class ResourceUrlError {
    none,
    invalid_url,
    invalid_authority,
    origin_mismatch,
    invalid_path,
    invalid_encoding,
    limit_exceeded,
};

struct ResourceUrl {
    ResourceUrlError error{ResourceUrlError::invalid_url};
    std::string path;

    explicit operator bool() const noexcept { return error == ResourceUrlError::none; }
};

// Accept a serialized, absolute URL already resolved by the engine's URL parser:
// app://<exact lowercase SHA-256>/web/<resource>. exact_authority is that pinned
// SHA-256 text, not an arbitrary hostname. No userinfo, port or authority aliases
// are accepted. The case-sensitive result includes "web/" and owns its bytes.
//
// Query and fragment never enter the resource key. Percent escapes are decoded
// exactly once; encoded path separators, percent and ASCII unreserved characters
// are rejected. Spaces in the serialized path must be escaped. Valid UTF-8 is
// preserved without case folding or Unicode normalization. Current SFAPND01
// packages permit ASCII keys only: an accepted Unicode key is an exact lookup
// miss with such a package, not an expansion of that package format.
//
// This is not a parser for raw HTML/CSS/JS URL spellings or relative references.
// WTF resolution may already have consumed dot segments (including escaped
// dots). This helper rejects residual dot segments and enforces the final /web/
// namespace; it cannot recover or certify the source spelling's traversal.
// Normal relative ../ resolution within /web/ belongs to WTF before this call.
// Methods, response MIME, lifetime, byte lookup and transport are separate.
// Allocation failures propagate as standard C++ exceptions.
[[nodiscard]] ResourceUrl normalize_app_resource_url(
    std::string_view resolved_url, std::string_view exact_authority);

} // namespace foundation::appended::candidate
