// SPDX-License-Identifier: CC0-1.0
#pragma once

#include "engine_editor_profile.hpp"
#include "native_editor_codec.hpp"
#include <foundation/appended/engine_provider.h>
#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <utility>
#include <variant>
#include <vector>

namespace foundation::appended {

// Owned logical mailbox values only. Convert other identities by named fields;
// never copy or serialize these C++ layouts into the editor binary protocol.
struct EngineEditorTarget {
    std::uint64_t worker_epoch{}, application_instance{}, document_sequence{}, service_generation{};
    bool operator==(const EngineEditorTarget&) const = default;
};
using EngineEditorTicket = std::uint64_t;
enum class EngineEditorWorkKind : std::uint32_t { projection_query = 1, observation = 2, revoke = 3 };
struct EngineEditorWork {
    EngineEditorTarget target;
    std::uint64_t request_sequence{};
    EngineEditorWorkKind kind{EngineEditorWorkKind::projection_query};
    std::uint32_t operation{}, required_reply_capacity{};
    std::array<std::uint8_t, 32> schema_sha256{};
    std::vector<std::uint8_t> payload;
};
struct EngineEditorDispatch {
    EngineEditorTicket ticket{};
    std::uint64_t transfer{};
    EngineEditorWork work;
};

// Admission, native command disposition and the binary receipt's semantic
// outcome are separate domains. A consumed transport never establishes editor
// success without the exact checked receipt for its original target/head.
enum class EngineEditorAdmissionCode : std::uint32_t {
    admitted, busy, unavailable, stale, invalid, limit, closed, exhausted
};
struct EngineEditorAdmission {
    EngineEditorAdmissionCode code{EngineEditorAdmissionCode::unavailable};
    EngineEditorTicket ticket{};
};
enum class EngineEditorOutcome : std::uint32_t { rejected, consumed, unknown, cancelled };
struct EngineEditorCompletion {
    EngineEditorTarget target;
    EngineEditorTicket ticket{};
    std::uint64_t transfer{}, request_sequence{};
    EngineEditorWorkKind kind{EngineEditorWorkKind::projection_query};
    EngineEditorOutcome outcome{EngineEditorOutcome::unknown};
    std::int32_t provider_status{BIB_ENGINE_PROCESS_EXIT_REQUIRED};
    std::uint32_t provider_disposition{};
    bool handled{};
    std::uint64_t semantic_revision{};
    std::vector<std::uint8_t> bytes;
};

struct EngineEditorReadback {
    bool semantic_unknown{}, unavailable{}, noneditable{};
    std::optional<foundation::ui::native_editor::NativeRetireMaterial> retire, retired;
    foundation::ui::native_editor::Identity identity;
};

namespace engine_editor_work_detail {
namespace ne = foundation::ui::native_editor;
namespace codec = ne::codec;
using DecodedWork = std::variant<codec::ProjectionQuery, codec::NativeRequestEnvelope, codec::RevocationEnvelope>;

// GUI epoch/context and the transport target are distinct authority domains.
// Only a publication revision may refresh within the same GUI context.
inline bool same_owner(const ne::Identity& a, const ne::Identity& b) noexcept {
    return a.owner == b.owner && a.generation == b.generation && a.epoch == b.epoch;
}
inline bool same_context(const ne::Identity& a, const ne::Identity& b) noexcept {
    return same_owner(a, b) && a.context == b.context;
}
inline codec::WireTarget wire_target(const EngineEditorWork& work) noexcept {
    return {work.target.worker_epoch, work.target.application_instance, work.target.document_sequence,
        work.target.service_generation, work.request_sequence};
}
inline std::optional<DecodedWork> decode_work(const EngineEditorWork& work) noexcept {
    try {
        if (!work.target.worker_epoch || !work.target.application_instance || !work.target.document_sequence ||
            !work.target.service_generation || !work.request_sequence ||
            work.request_sequence > BIB_ENGINE_DOCUMENT_V2_MAX_ORDINARY_SEQUENCE) return {};
        const engine_editor::OperationFacts* facts{};
        if (work.kind == EngineEditorWorkKind::projection_query && work.operation == BIB_ENGINE_QUERY_EDITOR_PROJECTION_V1) {
            for (const auto& value : engine_editor::kQueries) if (value.operation == work.operation) facts = &value;
        } else if ((work.kind == EngineEditorWorkKind::observation && work.operation == BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1) ||
                   (work.kind == EngineEditorWorkKind::revoke && work.operation == BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1)) {
            for (const auto& value : engine_editor::kCommands) if (value.operation == work.operation) facts = &value;
        }
        if (!facts || work.schema_sha256 != facts->schema_sha256 ||
            work.required_reply_capacity != facts->required_reply_capacity || work.payload.empty() ||
            work.payload.size() > facts->maximum_input_bytes) return {};
        const auto target = wire_target(work);
        if (work.kind == EngineEditorWorkKind::projection_query) {
            codec::ProjectionQuery value;
            if (!codec::decode_projection_query(work.payload, value) || value.target != target) return {};
            return DecodedWork{std::move(value)};
        }
        if (work.kind == EngineEditorWorkKind::observation) {
            codec::NativeRequestEnvelope value;
            if (!codec::decode_native_request(work.payload, value) || value.target != target) return {};
            const auto& projection = value.request.resolved;
            const auto& basis = value.request.packet.basis;
            if (!same_context(projection.identity, basis.identity) || projection.editor_revision != basis.editor_revision ||
                projection.surrounding != basis.surrounding || projection.selection != basis.selection ||
                projection.backward != basis.backward || projection.composition != basis.composition) return {};
            return DecodedWork{std::move(value)};
        }
        codec::RevocationEnvelope value;
        if (!codec::decode_revocation(work.payload, value) || value.target != target) return {};
        return DecodedWork{std::move(value)};
    } catch (...) { return {}; }
}
inline const ne::Identity& identity(const DecodedWork& value) noexcept {
    if (const auto* query = std::get_if<codec::ProjectionQuery>(&value)) return query->identity;
    if (const auto* request = std::get_if<codec::NativeRequestEnvelope>(&value)) return request->request.resolved.identity;
    return std::get<codec::RevocationEnvelope>(value).request.identity;
}
} // namespace engine_editor_work_detail

// Pure bounded shape/target joins only. No helper admits a live context, spends
// a sequence, records an attempt or invokes a Controller/backend/GUI callback.
inline bool valid_engine_editor_work_join(const EngineEditorWork& work) noexcept {
    return engine_editor_work_detail::decode_work(work).has_value();
}
inline std::optional<std::uint64_t> engine_editor_work_context(const EngineEditorWork& work) noexcept {
    const auto decoded = engine_editor_work_detail::decode_work(work);
    if (!decoded) return {};
    return engine_editor_work_detail::identity(*decoded).context;
}

// Use only for status0 query replies or disposition1/status0 command replies.
// Outer -8/disposition2 bytes are opaque evidence and bypass this semantic
// decoder. A valid inner unknown is retained as terminal evidence, with no
// retirement or replacement authority. The Owner still checks its exact latest
// provider-owned obligation before accepting any returned retirement material.
inline std::optional<EngineEditorReadback> checked_engine_editor_reply(const EngineEditorWork& work,
        std::span<const std::uint8_t> bytes, std::uint64_t semantic_revision) noexcept {
    using namespace engine_editor_work_detail;
    try {
        const auto decoded = decode_work(work);
        if (!decoded || bytes.empty() || bytes.size() > work.required_reply_capacity) return {};
        const auto target = wire_target(work);
        EngineEditorReadback checked;
        if (const auto* query = std::get_if<codec::ProjectionQuery>(&*decoded)) {
            codec::ProjectionReply reply;
            if (!codec::decode_projection_reply(bytes, reply) || reply.target != target || reply.identity != query->identity ||
                reply.observation_revision != semantic_revision ||
                (query->mapping_id && reply.projection && reply.projection->mapping_id != query->mapping_id)) return {};
            checked.identity = reply.identity;
            checked.unavailable = reply.state == codec::ProjectionReply::State::unavailable;
            checked.noneditable = reply.state == codec::ProjectionReply::State::noneditable;
            if (reply.projection) checked.retire = reply.projection->retire;
            return checked;
        }
        if (semantic_revision) return {};
        codec::NativeResultEnvelope reply;
        if (!codec::decode_native_result(bytes, reply) || reply.target != target) return {};
        const auto& original = identity(*decoded);
        const auto& result = reply.result;
        if (result.outcome == ne::Outcome::unknown) {
            checked.semantic_unknown = true;
            checked.identity = original;
            return checked;
        }
        const auto old = std::holds_alternative<codec::NativeRequestEnvelope>(*decoded) ?
            std::get<codec::NativeRequestEnvelope>(*decoded).request.resolved.retire :
            std::optional<ne::NativeRetireMaterial>{std::get<codec::RevocationEnvelope>(*decoded).request.material};
        if (result.retired && (!old || result.retired != old)) return {};
        const bool retired = result.outcome == ne::Outcome::applied && result.retired && old && result.retired == old;
        if (!same_owner(result.readback_identity, original) ||
            (!same_context(result.readback_identity, original) &&
                (!retired || result.continuity != ne::Continuity::replaced)) ||
            (work.kind == EngineEditorWorkKind::revoke && result.outcome == ne::Outcome::applied && !retired)) return {};
        const auto next = result.retire ? result.retire :
            (result.projection ? result.projection->retire : std::optional<ne::NativeRetireMaterial>{});
        if (next && (!old || (next->token != old->token && !retired) || (retired && next->token == old->token))) return {};
        checked.identity = result.readback_identity;
        checked.unavailable = result.availability == ne::NativeAvailability::unavailable;
        checked.noneditable = result.availability == ne::NativeAvailability::noneditable;
        checked.retire = next;
        if (retired) checked.retired = result.retired;
        return checked;
    } catch (...) { return {}; }
}

// This encodes the private Owner work envelope, not the provider's editor
// payload. Its caller has already checked the exact catalog/codec and bounds.
inline std::vector<std::uint8_t> encode_engine_editor_work(const EngineEditorWork& work) {
    std::vector<std::uint8_t> bytes(56 + work.payload.size());
    const auto put = [&](std::size_t offset, std::uint64_t value, unsigned count) {
        for (unsigned index = 0; index < count; ++index)
            bytes[offset + index] = static_cast<std::uint8_t>(value >> (index * 8));
    };
    put(0, static_cast<std::uint32_t>(work.kind), 4);
    put(4, work.operation, 4); put(8, work.request_sequence, 8);
    for (std::size_t index = 0; index < work.schema_sha256.size(); ++index)
        bytes[16 + index] = work.schema_sha256[index];
    put(48, work.required_reply_capacity, 4); put(52, work.payload.size(), 4);
    for (std::size_t index = 0; index < work.payload.size(); ++index) bytes[56 + index] = work.payload[index];
    return bytes;
}

} // namespace foundation::appended
