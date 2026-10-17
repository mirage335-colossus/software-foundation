#pragma once

#include <foundation/gui/document_values.hpp>

#include "appended_document.hpp"
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace foundation::ui {

inline constexpr std::size_t max_document_semantic_json_bytes = 1024 * 1024;
inline constexpr std::size_t max_document_semantic_json_depth = 16;
inline constexpr std::size_t max_document_semantic_json_values = 65536;

// Decode the EXACT source-prototype-v1 semantic reply shape. Generation belongs
// to the calling engine-session owner; it is not present in the producer JSON.
// Expected request identity is mandatory. Unknown/duplicate fields, malformed
// Unicode/numbers, excessive budgets, invalid node structure and stale request
// identity throw std::invalid_argument. Producer ok:false returns error_code.
//
// Omitted/hidden nodes are already filtered by the producer: there is no JSON
// omission field. Empty exports and element-rooted forests preserve actual IDs
// without an invented root. Forms remain readonly in AppendedDocument; their observed
// readonly/checked flags are retained as metadata, not converted to edit powers.
// The producer aggregate also includes retained role/display/whiteSpace values;
// tag names have their separate per-field limit and do not consume that budget.
// Unsupported whitespace modes retain their raw value and set degradation.
// Global truncation or element endpoints retain original selection metadata,
// while snapshot.selection remains absent. This is a codec, not an engine host.
DocumentSemanticReply decode_appended_document(std::string_view json,
    std::uint64_t generation, std::uint64_t expected_request_id);

} // namespace foundation::ui
