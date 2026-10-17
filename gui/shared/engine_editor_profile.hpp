// SPDX-License-Identifier: CC0-1.0
#pragma once
#include "engine_document_profile.hpp"
#include "appended_engine_input_profile.hpp"
#include "engine_editor_protocol.h"
#include "engine_editor_pins.hpp"

namespace foundation::appended::engine_editor {
using Digest=engine_document::Digest;
using OperationFacts=engine_document::OperationFacts;
enum class ProfileKind : std::uint32_t { disabled=0, editor=3 };
inline constexpr std::string_view kProfileName="foundation-engine-copied2035-ndv2-editor-v1";
inline constexpr std::uint64_t kProviderCapabilities=BIB_ENGINE_EDITOR_CAPABILITIES;
inline constexpr std::uint64_t kSurfaceCapabilities=BIB_ENGINE_EDITOR_SURFACE_CAPABILITIES;
inline constexpr std::uint32_t kReplyCapacity=BIB_ENGINE_EDITOR_REPLY_CAPACITY;
inline constexpr std::uint32_t kQueryRequestMaximum=BIB_ENGINE_EDITOR_MAX_QUERY_BYTES;
inline constexpr std::array<OperationFacts,2> kQueries{{engine_document::kQueries[0],
    {BIB_ENGINE_QUERY_EDITOR_PROJECTION_V1,kQueryRequestMaximum,kReplyCapacity,BIB_ENGINE_CAP_COMPOSITION_V1,kSchema}}};
inline constexpr std::array<OperationFacts,7> kCommands{{
    {1,160,16,BIB_ENGINE_CAP_KEY_V1,engine_input::kKeySchema},
    {3,32,16,BIB_ENGINE_CAP_FOCUS_V1,engine_input::kFocusSchema},
    {5,80,16,BIB_ENGINE_CAP_POINTER_V1,engine_input::kMouseSchema},
    engine_document::kCommands[0],engine_document::kCommands[1],
    {BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1,BIB_ENGINE_EDITOR_MAX_WIRE_BYTES,kReplyCapacity,BIB_ENGINE_CAP_COMPOSITION_V1,kSchema},
    {BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1,BIB_ENGINE_EDITOR_MAX_WIRE_BYTES,kReplyCapacity,BIB_ENGINE_CAP_COMPOSITION_V1,kSchema}}};
// Independent explicit descriptor facts. No2035 value is cast to or accepted
// by the frozen1795/2003 validators. These declarations are not qualification.
struct EngineEditorProfileFacts {
    bool enabled{};
    ProfileKind kind{ProfileKind::disabled};
    std::string name;
    std::uint32_t provider_abi_major{},provider_abi_minor{},host_abi_major{},host_abi_minor{};
    std::uint32_t target_system{},target_processor{},pointer_bits{},lifetime{},maximum_starts{};
    std::uint32_t viewport_width{},viewport_height{};
    std::uint64_t provider_capabilities{},surface_capabilities{};
    std::uint32_t surface_protocol_version{},editor_protocol_version{};
    Digest base_header_sha256{},document_header_sha256{},document_contract_sha256{},document_catalog_sha256{},physical_catalog_sha256{};
    Digest editor_header_sha256{},contract_sha256{},catalog_sha256{},schema_sha256{},build_sha256{},source_recipe_sha256{};
    std::array<OperationFacts,2> queries{};
    std::array<OperationFacts,7> commands{};
    std::uint32_t query_count{},command_count{};
    bool operator==(const EngineEditorProfileFacts&)const=default;
};
inline bool editor_profile_valid(const EngineEditorProfileFacts& f)noexcept{
    auto nonzero=[](const Digest& d){for(auto b:d)if(b)return true;return false;};
    const bool target=(f.target_system==BIB_ENGINE_TARGET_LINUX&&f.pointer_bits==64&&
        (f.target_processor==BIB_ENGINE_CPU_X86_64||f.target_processor==BIB_ENGINE_CPU_AARCH64))||
        (f.target_system==BIB_ENGINE_TARGET_WINDOWS&&f.target_processor==BIB_ENGINE_CPU_X86_64&&f.pointer_bits==64)||
        (f.target_system==BIB_ENGINE_TARGET_BROWSER_WASM&&f.target_processor==BIB_ENGINE_CPU_WASM32&&f.pointer_bits==32);
    return f.enabled&&f.kind==ProfileKind::editor&&f.name==kProfileName&&target&&
        f.provider_abi_major==BIB_ENGINE_DOCUMENT_V2_ABI_MAJOR&&f.provider_abi_minor==BIB_ENGINE_DOCUMENT_V2_ABI_MINOR&&
        f.host_abi_major==BIB_ENGINE_DOCUMENT_V2_HOST_ABI_MAJOR&&f.host_abi_minor==BIB_ENGINE_DOCUMENT_V2_HOST_ABI_MINOR&&
        f.lifetime==BIB_ENGINE_LIFETIME_PROCESS&&f.maximum_starts==1&&f.viewport_width==800&&f.viewport_height==600&&
        f.provider_capabilities==kProviderCapabilities&&f.surface_capabilities==kSurfaceCapabilities&&
        f.surface_protocol_version==2&&f.editor_protocol_version==BIB_ENGINE_EDITOR_PROTOCOL_VERSION&&
        f.base_header_sha256==engine_document::kBaseHeaderSha256&&f.document_header_sha256==engine_document::kExtensionHeaderSha256&&
        f.document_contract_sha256==engine_document::kContractSha256&&f.document_catalog_sha256==engine_document::kCatalogSha256&&
        f.physical_catalog_sha256==engine_document::kPhysicalCatalogSha256&&f.editor_header_sha256==kHeaderSha256&&
        f.contract_sha256==kContractSha256&&f.catalog_sha256==kCatalogSha256&&f.schema_sha256==kSchema&&
        nonzero(f.build_sha256)&&nonzero(f.source_recipe_sha256)&&f.queries==kQueries&&f.commands==kCommands&&
        f.query_count==2&&f.command_count==7;
}
inline bool editor_profile_agrees(const EngineEditorProfileFacts& a,const EngineEditorProfileFacts& b)noexcept{
    return editor_profile_valid(a)&&editor_profile_valid(b)&&a==b;
}
}
