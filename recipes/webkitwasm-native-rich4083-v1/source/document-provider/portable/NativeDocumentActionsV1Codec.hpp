// SPDX-License-Identifier: CC0-1.0
// Pure owned values only. Native admission and effects belong to the owner.
#pragma once

#include "NativeDocumentV2Codec.hpp"
#include <foundation/appended/engine_provider_document_actions_v1.h>
#include <array>
#include <variant>

namespace BIB::NativeDocumentActionsV1 {
namespace N = NativeDocumentV2;
namespace F = foundation::appended;
using Bytes = N::Bytes;

struct Key {
    std::uint64_t worker_epoch{}, application_instance{}, document_sequence{}, service_generation{};
    std::uint64_t request_sequence{}, nested_request_id{};
    bool operator==(const Key&) const = default;
};
struct Focus { std::uint64_t node{}; bool operator==(const Focus&) const = default; };
struct Activate { std::uint64_t node{}; bool operator==(const Activate&) const = default; };
struct Select { N::Endpoint anchor, focus; bool operator==(const Select&) const = default; };
struct ChooseSingleOption {
    std::uint64_t node{}, option{};
    bool operator==(const ChooseSingleOption&) const = default;
};
using Action = std::variant<Focus, Activate, Select, ChooseSingleOption>;
struct Request {
    Key key;
    F::FormVersion expected;
    Action action;
    std::array<std::uint8_t, BIB_ENGINE_DOCUMENT_ACTIONS_V1_REQUEST_BYTES> bytes{};
};
// These are DAV1 domains, never form outcomes or outer transport statuses.
enum class Result : std::uint8_t {
    completed, completed_needs_current_observation, rejected, indeterminate
};
enum class Code : std::uint8_t {
    ok, busy, unavailable, stale_document, stale_control, invalid_action,
    unsupported, limit, readback_failed, context_replaced
};
struct Completion {
    Key key;
    Result result{Result::rejected};
    Code code{Code::unavailable};
    bool effects_entered{};
    std::optional<N::OwnedPublication> publication;
};
inline constexpr std::size_t maxReplyBytes = BIB_ENGINE_DOCUMENT_ACTIONS_V1_MAX_REPLY_BYTES;

// Strict bounded codecs throw invalid_argument for malformed/noncanonical input.
// Endpoint bounds here do not establish native node/kind/scalar authority.
Request encodeRequest(Key, F::FormVersion, const Action&);
Request decodeRequest(std::span<const std::uint8_t>);
Bytes encodeCompletion(const Request&, const Completion&);
Completion decodeCompletion(std::span<const std::uint8_t>, const Request&);
N::Identity identity(Key) noexcept;
} // namespace BIB::NativeDocumentActionsV1
