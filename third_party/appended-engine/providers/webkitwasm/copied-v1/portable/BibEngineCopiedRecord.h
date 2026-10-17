// SPDX-License-Identifier: CC0-1.0
// Source-only copied bridge codec. No engine objects, callbacks or initialization.
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <string_view>

namespace bib::copied {

inline constexpr std::size_t headerBytes = 72;
inline constexpr std::size_t receiptBytes = 80;
inline constexpr std::size_t maxBodyBytes = 1048576;
inline constexpr std::size_t maxEntryBytes = 4096;

enum class Status : std::uint32_t { ok = 0, invalid = 2, limit = 4 };

// Logical scalar values only; this structure is never serialized by layout.
// readRecord/readReceipt borrow their body from the caller's input span.
struct Record {
    std::uint32_t op{};
    std::uint64_t worker{};
    std::uint64_t instance{};
    std::uint64_t document{};
    std::uint64_t generation{};
    std::uint64_t transfer{};
    std::uint32_t source{};
    std::span<const std::uint8_t> body;
};

struct Start {
    std::string entry;
    std::array<std::uint8_t, 32> packageSHA{};
};

// Generic FKB1 records permit source 0..2 and any exact 16-bit operation.
// Operation-specific limits and live authority belong to their respective
// caller. No parser mutates its output arguments on failure.
[[nodiscard]] Status readRecord(std::uint32_t expectedOp,
    std::span<const std::uint8_t> input, Record& output) noexcept;
[[nodiscard]] Status readReceipt(std::uint32_t requestOp,
    std::span<const std::uint8_t> input, Record& output,
    std::uint32_t& control, std::uint32_t& service) noexcept;

// Static copied-engine request policy. The shim additionally validates the
// exact live worker/instance/document/generation and transaction authority.
// COLLECT status14 is structurally known but must poison in the dispatcher.
[[nodiscard]] bool validEngineRequest(const Record&) noexcept;
// Reserve this complete maximum BEFORE any provider/host effect. Zero is an
// unknown operation. DESCRIBE includes its entire <=1024-byte JSON allowance.
[[nodiscard]] std::size_t requiredEngineReplyBytes(std::uint32_t op) noexcept;

// All writes are allocation-free, explicit little endian and all-or-nothing.
// Input body/output overlap is rejected; the shim separately rejects caller
// input/output overlap before retaining an input snapshot. written is unchanged
// on failure. LIMIT means the complete selected record does not fit.
[[nodiscard]] Status writeRecord(const Record&,
    std::span<std::uint8_t> output, std::size_t& written) noexcept;
[[nodiscard]] Status writeReceipt(const Record&, std::uint32_t control,
    std::uint32_t service, std::span<const std::uint8_t> body,
    std::span<std::uint8_t> output, std::size_t& written) noexcept;
[[nodiscard]] Status writeReply(const Record&, std::uint32_t control,
    std::span<const std::uint8_t> body, std::span<std::uint8_t> output,
    std::size_t& written) noexcept;

// Strict scalar UTF-8 and the inert, canonical package resource URL policy.
// URL policy mirrors the current package resource normalizer, additionally
// forbidding query/fragment in START. Neither helper allocates.
[[nodiscard]] bool validUTF8(std::span<const std::uint8_t>) noexcept;
[[nodiscard]] bool validEntryURL(std::string_view entry,
    std::string_view packageSHA) noexcept;

// Exact seven-field JSON. Numeric viewport fields are lexical JSON integers
// (800 and 600); no fractional/exponent coercion, bool/string conversion or
// unknown fields. Escaped keys compare after decoding. Strings own their
// decoded UTF-8 bytes. All allocation/other exceptions become LIMIT and leave
// output unchanged. The 1MiB body and 4096-byte decoded entry limits apply.
[[nodiscard]] Status decodeStart(std::span<const std::uint8_t>, Start&) noexcept;

} // namespace bib::copied
