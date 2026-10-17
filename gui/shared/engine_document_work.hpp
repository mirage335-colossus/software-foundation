// SPDX-License-Identifier: CC0-1.0
#pragma once

#include "engine_document_profile.hpp"
#include "engine_document_actions_profile.hpp"
#include <array>
#include <cstdint>
#include <functional>
#include <optional>
#include <span>
#include <vector>

namespace foundation::appended {

// Leaf logical values only. Never serialize these C++ layouts. Convert other
// identity types by NAMED fields: native/NDV2 identity field orders differ.
struct EngineDocumentTarget {
    std::uint64_t worker_epoch{}, application_instance{}, document_sequence{}, service_generation{};
    bool operator==(const EngineDocumentTarget&) const = default;
};
using EngineDocumentTicket = std::uint64_t;
// nullopt is temporary busy. A source may throw for terminal exhaustion. New
// document profiles reserve UINT64_MAX for final ACK; legacy sources are intact.
using EngineDocumentSequenceSource = std::function<std::optional<std::uint64_t>()>;

enum class EngineDocumentWorkKind : std::uint32_t {
    snapshot_query = 1, form_action = 2, action_ack = 3,
    body_action = 4, body_action_ack = 5
};
inline constexpr bool engine_document_action_kind(EngineDocumentWorkKind kind) noexcept {
    return kind == EngineDocumentWorkKind::form_action || kind == EngineDocumentWorkKind::body_action;
}
inline constexpr bool engine_document_ack_kind(EngineDocumentWorkKind kind) noexcept {
    return kind == EngineDocumentWorkKind::action_ack || kind == EngineDocumentWorkKind::body_action_ack;
}
inline constexpr EngineDocumentWorkKind engine_document_ack_action_kind(EngineDocumentWorkKind kind) noexcept {
    return kind == EngineDocumentWorkKind::body_action_ack ? EngineDocumentWorkKind::body_action : EngineDocumentWorkKind::form_action;
}
struct EngineDocumentWork {
    EngineDocumentTarget target;
    std::uint64_t request_sequence{};
    EngineDocumentWorkKind kind{EngineDocumentWorkKind::snapshot_query};
    std::uint32_t operation{}, required_reply_capacity{};
    engine_document::Digest schema_sha256{};
    std::vector<std::uint8_t> payload;
};
struct EngineDocumentDispatch {
    EngineDocumentTicket ticket{};
    std::uint64_t transfer{};
    EngineDocumentWork work;
};

// Owner admission domain, distinct from BIB signed statuses, FKB1 controls and
// portable ServiceStatus. Do not cast between those unrelated status domains.
enum class EngineDocumentAdmissionCode : std::uint32_t {
    admitted, busy, unavailable, stale, invalid, limit, closed, exhausted
};
struct EngineDocumentAdmission {
    EngineDocumentAdmissionCode code{EngineDocumentAdmissionCode::unavailable};
    EngineDocumentTicket ticket{};
};
enum class EngineDocumentOutcome : std::uint32_t { rejected, consumed, unknown, cancelled };
// Consumption is a transport/native-command fact, never FormDraft acceptance.
// A consumed reply may contain an inner NDV2 rejection/unknown outcome or report
// effects_entered. Decode that semantic result before publishing form success.
struct EngineDocumentCompletion {
    EngineDocumentTarget target;
    EngineDocumentTicket ticket{};
    std::uint64_t transfer{}, request_sequence{};
    EngineDocumentWorkKind kind{EngineDocumentWorkKind::snapshot_query};
    EngineDocumentOutcome outcome{EngineDocumentOutcome::unknown};
    std::int32_t provider_status{BIB_ENGINE_PROCESS_EXIT_REQUIRED};
    // Exact C provider command disposition0/1/2. Query has no native command
    // disposition; use0 there and interpret its explicit outcome/status instead.
    std::uint32_t provider_disposition{};
    bool handled{};
    std::uint64_t semantic_revision{};
    std::vector<std::uint8_t> bytes;
};

enum class EngineDocumentAckCode : std::uint32_t {
    retired = BIB_ENGINE_DOCUMENT_V2_ACK_RETIRED,
    already_retired = BIB_ENGINE_DOCUMENT_V2_ACK_ALREADY_RETIRED,
    stale = BIB_ENGINE_DOCUMENT_V2_ACK_STALE
};
struct EngineDocumentActionAck {
    std::uint64_t original_action_sequence{};
    EngineDocumentAckCode code{EngineDocumentAckCode::stale};
    bool operator==(const EngineDocumentActionAck&) const = default;
};

// Pure bounded byte codecs; no ownership/sequence mutation, callback, engine,
// DOM, filesystem or Registry access. Invalid input returns no value. ACKMAX
// may be a fresh command sequence, but never an original action sequence.
inline constexpr std::optional<std::array<std::uint8_t, BIB_ENGINE_DOCUMENT_V2_ACK_REQUEST_BYTES>>
encode_engine_document_action_ack(std::uint64_t original_action_sequence) noexcept {
    if (!original_action_sequence || original_action_sequence > BIB_ENGINE_DOCUMENT_V2_MAX_ORDINARY_SEQUENCE)
        return std::nullopt;
    std::array<std::uint8_t, BIB_ENGINE_DOCUMENT_V2_ACK_REQUEST_BYTES> result{};
    for (unsigned i = 0; i < result.size(); ++i)
        result[i] = static_cast<std::uint8_t>(original_action_sequence >> (8 * i));
    return result;
}
inline constexpr std::optional<EngineDocumentActionAck>
decode_engine_document_action_ack(std::span<const std::uint8_t> bytes) noexcept {
    if (bytes.size() != BIB_ENGINE_DOCUMENT_V2_ACK_RESULT_BYTES) return std::nullopt;
    std::uint64_t original{};
    std::uint32_t code{}, reserved{};
    for (unsigned i = 0; i < 8; ++i) original |= std::uint64_t(bytes[i]) << (8 * i);
    for (unsigned i = 0; i < 4; ++i) {
        code |= std::uint32_t(bytes[BIB_ENGINE_DOCUMENT_V2_ACK_CODE_OFFSET + i]) << (8 * i);
        reserved |= std::uint32_t(bytes[BIB_ENGINE_DOCUMENT_V2_ACK_RESERVED_OFFSET + i]) << (8 * i);
    }
    if (!original || original > BIB_ENGINE_DOCUMENT_V2_MAX_ORDINARY_SEQUENCE || reserved || code > BIB_ENGINE_DOCUMENT_V2_ACK_STALE)
        return std::nullopt;
    return EngineDocumentActionAck{original, static_cast<EngineDocumentAckCode>(code)};
}

// Shape/catalog check ONLY. NDV2 canonical decode and exact live authority must
// still precede native effects. This helper never validates a native registry,
// enables a profile or gives a retained completion permission to replay effects.
inline bool valid_engine_document_work_shape(const EngineDocumentWork& work) noexcept {
    if (!work.target.worker_epoch || !work.target.application_instance || !work.target.document_sequence ||
        !work.target.service_generation || !work.request_sequence) return false;
    switch (work.kind) {
    case EngineDocumentWorkKind::snapshot_query:
        return work.request_sequence <= BIB_ENGINE_DOCUMENT_V2_MAX_ORDINARY_SEQUENCE &&
            work.operation == BIB_ENGINE_QUERY_DOCUMENT_FORMS_V2 && work.schema_sha256 == engine_document::kSchema &&
            work.required_reply_capacity == BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY && work.payload.size() == BIB_ENGINE_DOCUMENT_V2_QUERY_BYTES;
    case EngineDocumentWorkKind::form_action:
        return work.request_sequence <= BIB_ENGINE_DOCUMENT_V2_MAX_ORDINARY_SEQUENCE &&
            work.operation == BIB_ENGINE_COMMAND_FORM_ACTION_V2 && work.schema_sha256 == engine_document::kSchema &&
            work.required_reply_capacity == BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY &&
            work.payload.size() >= 81 && work.payload.size() <= BIB_ENGINE_DOCUMENT_V2_MAX_ACTION_BYTES;
    case EngineDocumentWorkKind::body_action:
        return work.request_sequence <= BIB_ENGINE_DOCUMENT_ACTIONS_V1_MAX_ORDINARY_SEQUENCE &&
            work.operation == BIB_ENGINE_COMMAND_DOCUMENT_ACTION_V1 && work.schema_sha256 == engine_document_actions::kSchema &&
            work.required_reply_capacity == BIB_ENGINE_DOCUMENT_ACTIONS_V1_REPLY_CAPACITY &&
            work.payload.size() == BIB_ENGINE_DOCUMENT_ACTIONS_V1_REQUEST_BYTES;
    case EngineDocumentWorkKind::action_ack:
    case EngineDocumentWorkKind::body_action_ack: {
        const bool body = work.kind == EngineDocumentWorkKind::body_action_ack;
        if (work.operation != (body ? BIB_ENGINE_COMMAND_ACK_DOCUMENT_ACTION_V1 : BIB_ENGINE_COMMAND_ACK_FORM_ACTION_V2) ||
            work.schema_sha256 != (body ? engine_document_actions::kAckSchema : engine_document::kAckSchema) ||
            work.required_reply_capacity != BIB_ENGINE_DOCUMENT_V2_ACK_REPLY_CAPACITY || work.payload.size() != BIB_ENGINE_DOCUMENT_V2_ACK_REQUEST_BYTES)
            return false;
        std::uint64_t original{};
        for (unsigned i = 0; i < 8; ++i) original |= std::uint64_t(work.payload[i]) << (8 * i);
        return original && original <= BIB_ENGINE_DOCUMENT_V2_MAX_ORDINARY_SEQUENCE && work.request_sequence > original;
    }
    }
    return false;
}

} // namespace foundation::appended
