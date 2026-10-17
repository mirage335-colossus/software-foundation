// SPDX-License-Identifier: CC0-1.0
#pragma once

#include "engine_editor_profile.hpp"
#include <foundation/appended/engine_provider_document_actions_v1.h>

namespace foundation::appended::engine_document_actions {
using Digest = engine_document::Digest;
using OperationFacts = engine_document::OperationFacts;

enum class ProfileKind : std::uint32_t {
    disabled = 0,
    document_actions = BIB_ENGINE_DOCUMENT_ACTIONS_V1_PROFILE_KIND,
};
inline constexpr std::string_view kProfileName = BIB_ENGINE_DOCUMENT_ACTIONS_V1_PROFILE_NAME;
inline constexpr std::uint64_t kProviderCapabilities = BIB_ENGINE_DOCUMENT_ACTIONS_V1_PROVIDER_CAPABILITIES;
inline constexpr std::uint64_t kSurfaceCapabilities = engine_editor::kSurfaceCapabilities;
inline constexpr std::uint32_t kReplyCapacity = BIB_ENGINE_DOCUMENT_ACTIONS_V1_REPLY_CAPACITY;
inline constexpr std::uint32_t kRequestBytes = BIB_ENGINE_DOCUMENT_ACTIONS_V1_REQUEST_BYTES;
inline constexpr std::uint32_t kAckRequestBytes = BIB_ENGINE_DOCUMENT_ACTIONS_V1_ACK_REQUEST_BYTES;
inline constexpr std::uint32_t kAckResultBytes = BIB_ENGINE_DOCUMENT_ACTIONS_V1_ACK_RESULT_BYTES;
inline constexpr std::uint32_t kAckReplyCapacity = BIB_ENGINE_DOCUMENT_ACTIONS_V1_ACK_REPLY_CAPACITY;
inline constexpr std::uint32_t kCopiedReplyCapacity = 80 + 24 + kReplyCapacity;
inline constexpr std::uint32_t kAckCopiedReplyCapacity = 80 + 24 + kAckResultBytes;
inline constexpr auto kSchema = engine_document::detail::digest(BIB_ENGINE_DOCUMENT_ACTIONS_V1_SCHEMA_SHA256_HEX);
inline constexpr auto kAckSchema = engine_document::detail::digest(BIB_ENGINE_DOCUMENT_ACTIONS_V1_ACK_SCHEMA_SHA256_HEX);
inline constexpr auto kHeaderSha256 = engine_document::detail::digest("e748f399557597c510cbcf457dc96208c7bfd5ebbde3298a7cf3f49e7e05754f");
// BuildV1 binds this exact canonical contract.json, not the extension alone.
inline constexpr auto kContractSha256 = engine_document::detail::digest("33e23c8972497a64956a765b24a61538fe1cfcabe6be80af8e19ceb0e401e221");
inline constexpr auto kCatalogSha256 = engine_document::detail::digest("f220358edc36eb083fd567611f5d0ebb5f607fe3fd90e1c83ccd7a85a5690be5");

inline constexpr std::array<OperationFacts, 2> kQueries = engine_editor::kQueries;
inline constexpr std::array<OperationFacts, 9> kCommands{{
    engine_editor::kCommands[0], engine_editor::kCommands[1], engine_editor::kCommands[2],
    engine_editor::kCommands[3], engine_editor::kCommands[4], engine_editor::kCommands[5],
    engine_editor::kCommands[6],
    {BIB_ENGINE_COMMAND_DOCUMENT_ACTION_V1, kRequestBytes, kReplyCapacity,
     BIB_ENGINE_CAP_DOCUMENT_ACTIONS_V1, kSchema},
    {BIB_ENGINE_COMMAND_ACK_DOCUMENT_ACTION_V1, kAckRequestBytes, kAckReplyCapacity,
     BIB_ENGINE_CAP_DOCUMENT_ACTIONS_V1, kAckSchema},
}};

// Independent explicit source facts. They are never cast to an old admitted
// profile, and do not establish an enabled provider, artifact or runtime proof.
// The composition must supply the actual reviewed build/source/target facts.
struct EngineDocumentActionsProfileFacts {
    bool enabled{};
    ProfileKind kind{ProfileKind::disabled};
    std::string name;
    std::uint32_t provider_abi_major{}, provider_abi_minor{}, host_abi_major{}, host_abi_minor{};
    std::uint32_t target_system{}, target_processor{}, pointer_bits{}, lifetime{}, maximum_starts{};
    std::uint32_t viewport_width{}, viewport_height{};
    std::uint64_t provider_capabilities{}, surface_capabilities{};
    std::uint32_t surface_protocol_version{}, editor_protocol_version{};
    Digest base_header_sha256{}, document_header_sha256{}, document_contract_sha256{}, document_catalog_sha256{}, physical_catalog_sha256{};
    Digest editor_header_sha256{}, editor_contract_sha256{}, editor_catalog_sha256{}, editor_schema_sha256{};
    Digest actions_header_sha256{}, contract_sha256{}, catalog_sha256{}, schema_sha256{}, ack_schema_sha256{};
    Digest build_sha256{}, source_recipe_sha256{};
    std::array<OperationFacts, 2> queries{};
    std::array<OperationFacts, 9> commands{};
    std::uint32_t query_count{}, command_count{};
    bool operator==(const EngineDocumentActionsProfileFacts&) const = default;
};

inline bool document_actions_profile_valid(const EngineDocumentActionsProfileFacts& facts) noexcept {
    const auto nonzero = [](const Digest& digest) {
        for (auto byte : digest) if (byte) return true;
        return false;
    };
    const bool target = (facts.target_system == BIB_ENGINE_TARGET_LINUX && facts.pointer_bits == 64 &&
            (facts.target_processor == BIB_ENGINE_CPU_X86_64 || facts.target_processor == BIB_ENGINE_CPU_AARCH64)) ||
        (facts.target_system == BIB_ENGINE_TARGET_WINDOWS && facts.target_processor == BIB_ENGINE_CPU_X86_64 && facts.pointer_bits == 64) ||
        (facts.target_system == BIB_ENGINE_TARGET_BROWSER_WASM && facts.target_processor == BIB_ENGINE_CPU_WASM32 && facts.pointer_bits == 32);
    return facts.enabled && facts.kind == ProfileKind::document_actions && facts.name == kProfileName && target &&
        facts.provider_abi_major == BIB_ENGINE_DOCUMENT_ACTIONS_V1_ABI_MAJOR &&
        facts.provider_abi_minor == BIB_ENGINE_DOCUMENT_ACTIONS_V1_ABI_MINOR &&
        facts.host_abi_major == BIB_ENGINE_DOCUMENT_ACTIONS_V1_HOST_ABI_MAJOR &&
        facts.host_abi_minor == BIB_ENGINE_DOCUMENT_ACTIONS_V1_HOST_ABI_MINOR &&
        facts.lifetime == BIB_ENGINE_LIFETIME_PROCESS && facts.maximum_starts == 1 &&
        facts.viewport_width == 800 && facts.viewport_height == 600 &&
        facts.provider_capabilities == kProviderCapabilities && facts.surface_capabilities == kSurfaceCapabilities &&
        facts.surface_protocol_version == 2 && facts.editor_protocol_version == BIB_ENGINE_EDITOR_PROTOCOL_VERSION &&
        facts.base_header_sha256 == engine_document::kBaseHeaderSha256 &&
        facts.document_header_sha256 == engine_document::kExtensionHeaderSha256 &&
        facts.document_contract_sha256 == engine_document::kContractSha256 &&
        facts.document_catalog_sha256 == engine_document::kCatalogSha256 &&
        facts.physical_catalog_sha256 == engine_document::kPhysicalCatalogSha256 &&
        facts.editor_header_sha256 == engine_editor::kHeaderSha256 &&
        facts.editor_contract_sha256 == engine_editor::kContractSha256 &&
        facts.editor_catalog_sha256 == engine_editor::kCatalogSha256 &&
        facts.editor_schema_sha256 == engine_editor::kSchema &&
        facts.actions_header_sha256 == kHeaderSha256 && facts.contract_sha256 == kContractSha256 &&
        facts.catalog_sha256 == kCatalogSha256 && facts.schema_sha256 == kSchema && facts.ack_schema_sha256 == kAckSchema &&
        nonzero(facts.build_sha256) && nonzero(facts.source_recipe_sha256) &&
        facts.queries == kQueries && facts.commands == kCommands &&
        facts.query_count == kQueries.size() && facts.command_count == kCommands.size();
}

inline bool document_actions_profile_agrees(const EngineDocumentActionsProfileFacts& actual,
        const EngineDocumentActionsProfileFacts& expected) noexcept {
    return document_actions_profile_valid(actual) && document_actions_profile_valid(expected) && actual == expected;
}
} // namespace foundation::appended::engine_document_actions
