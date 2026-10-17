// SPDX-License-Identifier: CC0-1.0
#pragma once

#include "appended_document_v2_codec.hpp"
#include <foundation/appended/engine_provider_document_actions_v1.h>
#include <array>
#include <variant>

namespace foundation::ui {

// Logical values only. Serialize named fields, never C++ object layouts.
struct DocumentActionV1Key {
    std::uint64_t worker_epoch{}, application_instance{}, document_sequence{}, service_generation{};
    std::uint64_t request_sequence{}, nested_request_id{};
    bool operator==(const DocumentActionV1Key&) const = default;
};
enum class DocumentActionV1Kind : std::uint8_t { focus, activate, select, choose_single_option };
struct DocumentActionV1Focus { std::uint64_t node{}; bool operator==(const DocumentActionV1Focus&) const = default; };
struct DocumentActionV1Activate { std::uint64_t node{}; bool operator==(const DocumentActionV1Activate&) const = default; };
struct DocumentActionV1Select { DocumentNativeSelection selection; bool operator==(const DocumentActionV1Select&) const = default; };
struct DocumentActionV1ChooseSingleOption {
    std::uint64_t node{}, option{};
    bool operator==(const DocumentActionV1ChooseSingleOption&) const = default;
};
using DocumentActionV1 = std::variant<DocumentActionV1Focus, DocumentActionV1Activate,
    DocumentActionV1Select, DocumentActionV1ChooseSingleOption>;
struct DocumentActionV1Request {
    DocumentActionV1Key key;
    DocumentVersion expected;
    DocumentActionV1 action;
    std::array<std::uint8_t, BIB_ENGINE_DOCUMENT_ACTIONS_V1_REQUEST_BYTES> bytes{};
};
// These result/code enums belong to this extension. Never cast a form outcome,
// provider status, transport outcome or unknown outer entry into these domains.
enum class DocumentActionV1Result : std::uint8_t {
    completed, completed_needs_current_observation, rejected, indeterminate
};
enum class DocumentActionV1Code : std::uint8_t {
    ok, busy, unavailable, stale_document, stale_control, invalid_action,
    unsupported, limit, readback_failed, context_replaced
};
struct DocumentActionV1Reply {
    DocumentActionV1Key key;
    DocumentActionV1Result result{DocumentActionV1Result::rejected};
    DocumentActionV1Code code{DocumentActionV1Code::unavailable};
    bool effects_entered{};
    std::optional<DocumentV2Publication> publication;
    // Retain the exact payload: the consumer view discards native child counts.
    std::vector<std::uint8_t> publication_record;
};
inline constexpr std::size_t max_document_action_v1_reply_bytes = BIB_ENGINE_DOCUMENT_ACTIONS_V1_MAX_REPLY_BYTES;

// Pure bounded owned codecs. All unused bytes must be zero. Selection offsets
// have consumer bounds here; native admission must resolve the actual published
// node/kind and check scalar boundaries against its current text/child buffer.
// The Controller currently produces text endpoints only; element wire support
// does not imply a terminal range gesture. Invalid input throws invalid_argument.
DocumentActionV1Request encode_document_action_v1(DocumentActionV1Key, DocumentVersion, const DocumentActionV1&);
DocumentActionV1Request decode_document_action_v1_request(std::span<const std::uint8_t>);
DocumentActionV1Reply decode_document_action_v1_reply(std::span<const std::uint8_t>, const DocumentActionV1Request&);
std::vector<std::uint8_t> encode_document_action_v1_reply(const DocumentActionV1Request&,
    DocumentActionV1Result, DocumentActionV1Code, bool effects_entered,
    std::span<const std::uint8_t> publication_record = {});

// Separate ACK11 payload domain. Transport must additionally bind command11,
// its schema/capability, original full target/family, and a fresh global sequence
// strictly greater than the original. These helpers change no retained state.
enum class DocumentActionV1AckCode : std::uint32_t { retired, already_retired, stale };
struct DocumentActionV1Ack {
    std::uint64_t original_action_sequence{};
    DocumentActionV1AckCode code{DocumentActionV1AckCode::stale};
    bool operator==(const DocumentActionV1Ack&) const = default;
};
std::optional<std::array<std::uint8_t, 8>> encode_document_action_v1_ack(std::uint64_t) noexcept;
std::optional<DocumentActionV1Ack> decode_document_action_v1_ack(std::span<const std::uint8_t>) noexcept;

} // namespace foundation::ui
