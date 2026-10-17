// SPDX-License-Identifier: CC0-1.0
#pragma once

#include "engine_document_work.hpp"
#include <cstdint>
#include <optional>
#include <span>
#include <vector>

namespace foundation::appended::engine_document {

// One sequence domain shared by document work and physical input. An ordinary
// reservation blocks all issuance until its exact sequence is committed or
// cancelled. Cancellation burns the reserved sequence. UINT64_MAX is ACK-only.
class SequenceAllocator {
public:
    explicit SequenceAllocator(std::uint64_t first = 1);
    std::optional<std::uint64_t> reserve();
    bool commit(std::uint64_t sequence) noexcept;
    bool cancel(std::uint64_t sequence) noexcept;
    std::optional<std::uint64_t> issue_physical();
    std::optional<std::uint64_t> issue_ack();
    bool has_reservation() const noexcept;
    bool ordinary_exhausted() const noexcept;

private:
    std::uint64_t next_;
    std::optional<std::uint64_t> reserved_;
    bool final_ack_issued_{};
};

// Shape and identity joins only. These functions do not decode document
// semantics, establish live authority or permit native effects.
bool valid_work_join(const EngineDocumentWork& work) noexcept;
bool valid_reply_join(const EngineDocumentWork& work,
                      std::span<const std::uint8_t> reply) noexcept;

// Caller validates the work shape before encoding this owned mailbox payload.
std::vector<std::uint8_t> encode_work(const EngineDocumentWork& work);

} // namespace foundation::appended::engine_document
