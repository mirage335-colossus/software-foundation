// SPDX-License-Identifier: CC0-1.0
#include "engine_document_mailbox.hpp"

#include <algorithm>
#include <cstddef>
#include <limits>
#include <stdexcept>

namespace foundation::appended::engine_document {
namespace {
constexpr auto final_ack_sequence = std::numeric_limits<std::uint64_t>::max();
constexpr std::size_t work_prefix_bytes = 56;

std::uint64_t read_u64(std::span<const std::uint8_t> bytes, std::size_t offset) noexcept {
    std::uint64_t result{};
    for (unsigned i = 0; i < 8; ++i)
        result |= std::uint64_t(bytes[offset + i]) << (8 * i);
    return result;
}

void write_integer(std::span<std::uint8_t> bytes, std::size_t offset,
                   std::uint64_t value, unsigned width) noexcept {
    for (unsigned i = 0; i < width; ++i)
        bytes[offset + i] = static_cast<std::uint8_t>(value >> (8 * i));
}

bool ndv2_join(std::span<const std::uint8_t> bytes, std::uint8_t kind,
               const EngineDocumentWork& work) noexcept {
    return bytes.size() >= 48 && bytes[0] == 'N' && bytes[1] == 'D' &&
        bytes[2] == 'V' && bytes[3] == '2' && bytes[4] == 2 && bytes[5] == 0 &&
        bytes[6] == kind && bytes[7] == 0 &&
        read_u64(bytes, 8) == work.target.application_instance &&
        read_u64(bytes, 16) == work.target.service_generation &&
        read_u64(bytes, 24) == work.target.document_sequence &&
        read_u64(bytes, 32) == work.request_sequence;
}
bool action_v1_join(std::span<const std::uint8_t> bytes, std::uint8_t kind,
                    const EngineDocumentWork& work) noexcept {
    return bytes.size() >= BIB_ENGINE_DOCUMENT_ACTIONS_V1_COMPLETION_PREFIX_BYTES &&
        bytes[0] == 'D' && bytes[1] == 'A' && bytes[2] == 'V' && bytes[3] == '1' &&
        bytes[4] == 1 && bytes[5] == 0 && bytes[6] == kind && bytes[7] == 0 &&
        (read_u64(bytes, 8) & UINT64_C(0xffffffff)) == bytes.size() &&
        (read_u64(bytes, 8) >> 32) == 0 &&
        read_u64(bytes, 16) == work.target.worker_epoch &&
        read_u64(bytes, 24) == work.target.application_instance &&
        read_u64(bytes, 32) == work.target.document_sequence &&
        read_u64(bytes, 40) == work.target.service_generation &&
        read_u64(bytes, 48) == work.request_sequence;
}
} // namespace

SequenceAllocator::SequenceAllocator(std::uint64_t first) : next_(first) {
    if (!first) throw std::invalid_argument("Zero document sequence");
}

std::optional<std::uint64_t> SequenceAllocator::reserve() {
    if (reserved_) return std::nullopt;
    if (ordinary_exhausted()) throw std::overflow_error("Ordinary document sequences exhausted");
    reserved_ = next_++;
    return reserved_;
}

bool SequenceAllocator::commit(std::uint64_t sequence) noexcept {
    if (!reserved_ || *reserved_ != sequence) return false;
    reserved_.reset();
    return true;
}

bool SequenceAllocator::cancel(std::uint64_t sequence) noexcept {
    return commit(sequence);
}

std::optional<std::uint64_t> SequenceAllocator::issue_physical() {
    if (reserved_) return std::nullopt;
    if (ordinary_exhausted()) throw std::overflow_error("Ordinary document sequences exhausted");
    return next_++;
}

std::optional<std::uint64_t> SequenceAllocator::issue_ack() {
    if (reserved_) return std::nullopt;
    if (final_ack_issued_) throw std::overflow_error("Document sequences exhausted");
    const auto sequence = next_;
    if (sequence == final_ack_sequence) final_ack_issued_ = true;
    else ++next_;
    return sequence;
}

bool SequenceAllocator::has_reservation() const noexcept {
    return reserved_.has_value();
}

bool SequenceAllocator::ordinary_exhausted() const noexcept {
    return next_ == final_ack_sequence;
}

bool valid_work_join(const EngineDocumentWork& work) noexcept {
    if (!valid_engine_document_work_shape(work)) return false;
    switch (work.kind) {
    case EngineDocumentWorkKind::snapshot_query:
        return ndv2_join(work.payload, 1, work) && read_u64(work.payload, 40) != 0;
    case EngineDocumentWorkKind::form_action:
        return ndv2_join(work.payload, 2, work) && read_u64(work.payload, 40) == 0;
    case EngineDocumentWorkKind::body_action:
        return action_v1_join(work.payload, 1, work);
    case EngineDocumentWorkKind::action_ack:
    case EngineDocumentWorkKind::body_action_ack:
        return true;
    }
    return false;
}

bool valid_reply_join(const EngineDocumentWork& work,
                      std::span<const std::uint8_t> reply) noexcept {
    if (!valid_work_join(work) || reply.size() > work.required_reply_capacity) return false;
    switch (work.kind) {
    case EngineDocumentWorkKind::snapshot_query:
        return ndv2_join(reply, 4, work) &&
            read_u64(reply, 40) == read_u64(work.payload, 40);
    case EngineDocumentWorkKind::form_action:
        return reply.size() >= 52 && ndv2_join(reply, 5, work) && read_u64(reply, 40) == 0;
    case EngineDocumentWorkKind::body_action:
        return reply.size() >= BIB_ENGINE_DOCUMENT_ACTIONS_V1_COMPLETION_PREFIX_BYTES &&
            reply.size() <= BIB_ENGINE_DOCUMENT_ACTIONS_V1_MAX_REPLY_BYTES &&
            action_v1_join(reply, 2, work) && read_u64(reply, 56) == read_u64(work.payload, 56);
    case EngineDocumentWorkKind::action_ack:
    case EngineDocumentWorkKind::body_action_ack: {
        const auto ack = decode_engine_document_action_ack(reply);
        return ack && ack->original_action_sequence == read_u64(work.payload, 0);
    }
    }
    return false;
}

std::vector<std::uint8_t> encode_work(const EngineDocumentWork& work) {
    std::vector<std::uint8_t> bytes(work_prefix_bytes + work.payload.size());
    write_integer(bytes, 0, static_cast<std::uint32_t>(work.kind), 4);
    write_integer(bytes, 4, work.operation, 4);
    write_integer(bytes, 8, work.request_sequence, 8);
    std::copy(work.schema_sha256.begin(), work.schema_sha256.end(), bytes.begin() + 16);
    write_integer(bytes, 48, work.required_reply_capacity, 4);
    write_integer(bytes, 52, static_cast<std::uint32_t>(work.payload.size()), 4);
    std::copy(work.payload.begin(), work.payload.end(), bytes.begin() + work_prefix_bytes);
    return bytes;
}

} // namespace foundation::appended::engine_document
