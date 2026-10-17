// SPDX-License-Identifier: CC0-1.0
#pragma once
#include <foundation/gui/surface_editor.hpp>
#include "engine_editor_protocol.h"
#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <vector>

// Preserve the private codec namespace while using the generic public records.
namespace foundation::ui::native_editor { using namespace foundation::gui_editor; }

namespace foundation::ui::native_editor::codec {
using Bytes = std::vector<std::uint8_t>;
inline constexpr std::size_t header_bytes = BIB_ENGINE_EDITOR_WIRE_HEADER_BYTES;
inline constexpr std::size_t maximum_wire_bytes = BIB_ENGINE_EDITOR_MAX_WIRE_BYTES;
// Exact outer transport/document join; no implicit target replacement.
struct WireTarget {
    std::uint64_t worker_epoch = 0, application_instance = 0;
    std::uint64_t document_sequence = 0, service_generation = 0, request_sequence = 0;
    bool operator==(const WireTarget&) const = default;
};
struct ProjectionQuery {
    WireTarget target;
    // context is the committed physical-input context; this codec never mints it.
    Identity identity;
    std::uint64_t mapping_id = 0; // Zero permits initial actual discovery only.
    bool operator==(const ProjectionQuery&) const = default;
};
struct ProjectionReply {
    enum class State { available, noneditable, unavailable };
    State state = State::unavailable;
    // Nonzero completed native readback sample, including checked null replies.
    std::uint64_t observation_revision = 0;
    WireTarget target;
    std::optional<NativeProjection> projection;
    Identity identity;
    bool readback_attested = false;
    bool operator==(const ProjectionReply&) const = default;
};

// Bounded structural validation only. These records carry no native authority:
// Controller and actual backend separately validate causality and live mapping.
bool valid_projection_query_shape(const ProjectionQuery&) noexcept;
bool valid_projection_reply_shape(const ProjectionReply&) noexcept;
bool valid_native_projection_shape(const NativeProjection&) noexcept;
struct NativeRequestEnvelope { WireTarget target; NativeRequest request; };
struct NativeResultEnvelope { WireTarget target; NativeResult result; };
struct RevocationEnvelope { WireTarget target; NativeRevocationRequest request; };
using NativeRevocationEnvelope = RevocationEnvelope;
bool valid_native_request_shape(const NativeRequestEnvelope&) noexcept;
bool valid_native_result_shape(const NativeResultEnvelope&) noexcept;
bool valid_revocation_shape(const RevocationEnvelope&) noexcept;

// Exact closed manual-LE wire format. Each rejection, including allocation
// failure, leaves caller output unchanged. Decode first preflights the complete
// untrusted byte range without owning allocations; no trailing data is admitted.
bool encode_projection_query(const ProjectionQuery&, Bytes&) noexcept;
bool decode_projection_query(std::span<const std::uint8_t>, ProjectionQuery&) noexcept;
bool encode_projection_reply(const ProjectionReply&, Bytes&) noexcept;
bool decode_projection_reply(std::span<const std::uint8_t>, ProjectionReply&) noexcept;
bool encode_native_request(const NativeRequestEnvelope&, Bytes&) noexcept;
bool decode_native_request(std::span<const std::uint8_t>, NativeRequestEnvelope&) noexcept;
bool encode_native_result(const NativeResultEnvelope&, Bytes&) noexcept;
bool decode_native_result(std::span<const std::uint8_t>, NativeResultEnvelope&) noexcept;
// Kind5 always requires provider-owned retirement material. Browser observation
// is optional evidence and can never substitute for that authority.
bool encode_revocation(const RevocationEnvelope&, Bytes&) noexcept;
bool decode_revocation(std::span<const std::uint8_t>, RevocationEnvelope&) noexcept;
} // namespace foundation::ui::native_editor::codec
