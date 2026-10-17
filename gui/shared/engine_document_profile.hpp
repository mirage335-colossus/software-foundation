// SPDX-License-Identifier: CC0-1.0
#pragma once

#include <foundation/appended/engine_provider_document_v2.h>
#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>

namespace foundation::appended::engine_document {
using Digest = std::array<std::uint8_t, 32>;
namespace detail {
consteval Digest digest(std::string_view text) {
    if (text.size() != 64) throw "Invalid SHA256 constant";
    Digest result{};
    for (std::size_t i = 0; i < result.size(); ++i) {
        auto digit = [](char c) consteval -> unsigned {
            if (c >= '0' && c <= '9') return static_cast<unsigned>(c - '0');
            if (c >= 'a' && c <= 'f') return static_cast<unsigned>(c - 'a' + 10);
            throw "Invalid SHA256 digit";
        };
        result[i] = static_cast<std::uint8_t>((digit(text[2 * i]) << 4) | digit(text[2 * i + 1]));
    }
    return result;
}
} // namespace detail

inline constexpr auto kSchema = detail::digest(BIB_ENGINE_DOCUMENT_V2_SCHEMA_SHA256_HEX);
inline constexpr auto kAckSchema = detail::digest(BIB_ENGINE_DOCUMENT_V2_ACK_SCHEMA_SHA256_HEX);
inline constexpr auto kBaseHeaderSha256 = detail::digest(BIB_ENGINE_DOCUMENT_V2_BASE_HEADER_SHA256_HEX);
inline constexpr auto kExtensionHeaderSha256 = detail::digest("7b047bae4d0072ef156ea94ba637566d563fea3a95d43c4c6314afc919b1d626");
// SHA256 of exact canonical contract.json; never the extension file hash alone.
inline constexpr auto kContractSha256 = detail::digest("aba7800e6aab1898f3614f0b1ac53e59b9f622bf1e9d3a413f50d672a3662298");
inline constexpr auto kCatalogSha256 = detail::digest("6e555d4c3bb71fbc965e1ca49671fab64d744913e18f45b9ba273505e0c6bcf5");
inline constexpr auto kPhysicalCatalogSha256 = detail::digest("d244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b");
inline constexpr std::string_view kPixelProfileName = "foundation-engine-copied1795-ndv2-v1";
inline constexpr std::string_view kPhysicalProfileName = "foundation-engine-copied2003-ndv2-v1";
inline constexpr std::uint64_t kPixelCapabilities = 1795, kPhysicalCapabilities = 2003;
inline constexpr std::uint32_t kReplyCapacity = BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY;
inline constexpr std::uint32_t kQueryCopiedReplyCapacity = 80 + 16 + kReplyCapacity;
inline constexpr std::uint32_t kFormCopiedReplyCapacity = 80 + 24 + kReplyCapacity;
inline constexpr std::uint32_t kAckCopiedReplyCapacity = 80 + 24 + BIB_ENGINE_DOCUMENT_V2_ACK_RESULT_BYTES;

enum class ProfileKind : std::uint32_t { disabled = 0, pixel = 1, physical = 2 };
struct OperationFacts {
    std::uint32_t operation{}, maximum_input_bytes{}, required_reply_capacity{};
    std::uint64_t capability{};
    Digest schema_sha256{};
    bool operator==(const OperationFacts&) const = default;
};
inline constexpr std::array<OperationFacts, 1> kQueries{{
    {BIB_ENGINE_QUERY_DOCUMENT_FORMS_V2, BIB_ENGINE_DOCUMENT_V2_QUERY_BYTES,
     kReplyCapacity, BIB_ENGINE_CAP_SEMANTIC_SNAPSHOT_V2, kSchema},
}};
inline constexpr std::array<OperationFacts, 2> kCommands{{
    {BIB_ENGINE_COMMAND_FORM_ACTION_V2, BIB_ENGINE_DOCUMENT_V2_MAX_ACTION_BYTES,
     kReplyCapacity, BIB_ENGINE_CAP_FORM_ACTION_V2, kSchema},
    {BIB_ENGINE_COMMAND_ACK_FORM_ACTION_V2, BIB_ENGINE_DOCUMENT_V2_ACK_REQUEST_BYTES,
     BIB_ENGINE_DOCUMENT_V2_ACK_REPLY_CAPACITY, BIB_ENGINE_CAP_FORM_ACTION_V2, kAckSchema},
}};

// Source contract facts, NOT an enabled instance, provider, artifact or runtime
// proof. The composition must supply actual reviewed build/source/target facts.
// Legacy259/467 profiles and their base-header pins are never accepted here.
struct EngineDocumentProfileFacts {
    bool enabled{};
    ProfileKind kind{ProfileKind::disabled};
    std::string name;
    std::uint32_t provider_abi_major{}, provider_abi_minor{}, host_abi_major{}, host_abi_minor{};
    std::uint32_t target_system{}, target_processor{}, pointer_bits{}, lifetime{}, maximum_starts{};
    std::uint32_t viewport_width{}, viewport_height{};
    std::uint64_t provider_capabilities{};
    Digest base_header_sha256{}, extension_header_sha256{}, contract_sha256{}, catalog_sha256{};
    Digest build_sha256{}, source_recipe_sha256{}, physical_catalog_sha256{};
    std::array<OperationFacts, 1> queries{};
    std::array<OperationFacts, 2> commands{};
    std::uint32_t query_count{}, command_count{};
    bool operator==(const EngineDocumentProfileFacts&) const = default;
};
inline bool document_profile_valid(const EngineDocumentProfileFacts& facts) noexcept {
    const auto nonzero = [](const Digest& digest) {
        for (auto byte : digest) if (byte) return true;
        return false;
    };
    const bool target = (facts.target_system == BIB_ENGINE_TARGET_LINUX && facts.pointer_bits == 64 &&
            (facts.target_processor == BIB_ENGINE_CPU_X86_64 || facts.target_processor == BIB_ENGINE_CPU_AARCH64)) ||
        (facts.target_system == BIB_ENGINE_TARGET_WINDOWS && facts.target_processor == BIB_ENGINE_CPU_X86_64 && facts.pointer_bits == 64) ||
        (facts.target_system == BIB_ENGINE_TARGET_BROWSER_WASM && facts.target_processor == BIB_ENGINE_CPU_WASM32 && facts.pointer_bits == 32);
    const bool profile = facts.kind == ProfileKind::pixel ?
        facts.name == kPixelProfileName && facts.provider_capabilities == kPixelCapabilities && !nonzero(facts.physical_catalog_sha256) :
        facts.kind == ProfileKind::physical && facts.name == kPhysicalProfileName &&
            facts.provider_capabilities == kPhysicalCapabilities && facts.physical_catalog_sha256 == kPhysicalCatalogSha256;
    return facts.enabled && target && profile &&
        facts.provider_abi_major == BIB_ENGINE_DOCUMENT_V2_ABI_MAJOR && facts.provider_abi_minor == BIB_ENGINE_DOCUMENT_V2_ABI_MINOR &&
        facts.host_abi_major == BIB_ENGINE_DOCUMENT_V2_HOST_ABI_MAJOR && facts.host_abi_minor == BIB_ENGINE_DOCUMENT_V2_HOST_ABI_MINOR &&
        facts.lifetime == BIB_ENGINE_LIFETIME_PROCESS && facts.maximum_starts == 1 && facts.viewport_width == 800 && facts.viewport_height == 600 &&
        facts.base_header_sha256 == kBaseHeaderSha256 && facts.extension_header_sha256 == kExtensionHeaderSha256 &&
        facts.contract_sha256 == kContractSha256 && facts.catalog_sha256 == kCatalogSha256 &&
        nonzero(facts.build_sha256) && nonzero(facts.source_recipe_sha256) &&
        facts.queries == kQueries && facts.commands == kCommands && facts.query_count == kQueries.size() && facts.command_count == kCommands.size();
}
inline bool document_profile_agrees(const EngineDocumentProfileFacts& actual, const EngineDocumentProfileFacts& expected) noexcept {
    return document_profile_valid(actual) && document_profile_valid(expected) && actual == expected;
}
} // namespace foundation::appended::engine_document
