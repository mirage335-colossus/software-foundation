// SPDX-License-Identifier: CC0-1.0
// Source candidate only. Exact canonical facts are metadata, not runtime proof.
#ifndef BIB_ENGINE_COPIED_DOCUMENT_FACTS_H
#define BIB_ENGINE_COPIED_DOCUMENT_FACTS_H
#include <foundation/appended/engine_provider_document_v2.h>
#include "engine_editor_protocol.h"
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string_view>

namespace bib::copied {
// The generated metadata/constructor selects this explicitly. Capability bits
// are checked against it and never choose the profile on their own.
enum class DocumentCopiedProfile : std::uint32_t { pixel=1, physical=2, editor=3 };
inline constexpr std::size_t documentCopiedFactsCapacity = 4096;
inline constexpr std::uint64_t documentCopiedCapabilities = UINT64_C(1795);
inline constexpr std::uint64_t documentCopiedPhysicalCapabilities = UINT64_C(2003);
inline constexpr std::uint64_t documentCopiedEditorCapabilities = BIB_ENGINE_EDITOR_CAPABILITIES;
inline constexpr std::string_view documentCopiedProfile = "foundation-engine-copied1795-ndv2-v1";
inline constexpr std::string_view documentCopiedPhysicalProfile = "foundation-engine-copied2003-ndv2-v1";
inline constexpr std::string_view documentCopiedEditorProfile = "foundation-engine-copied2035-ndv2-editor-v1";
inline constexpr std::string_view documentCopiedEditorHeader = "bdd9bf16765513be402481ab85dd596263fd4ac66a0dfc1dcc7ba5314ec85034";
inline constexpr std::string_view documentCopiedEditorContract = "0d43707e404979a38e0e8d7a7bc47042be95ae54216ed118a4de3314302b8c9c";
inline constexpr std::string_view documentCopiedEditorCatalog = "34fadacf563a00918255e4dc94b196bf0dc5c8ed57c7165e3da1e5fdd4d06bb8";
inline constexpr std::string_view documentCopiedEditorSchema = "f2a6202056bd7fb6872539ba1e8806296ae6f6409ab2a21b9b581f19a4c7d4b1";
inline constexpr std::string_view documentCopiedPhysicalCatalog = "d244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b";
inline constexpr std::string_view documentCopiedBaseHeader = "a8e89da85d34b29a4d1bc454495791fa604b81e3477e48ce8ca902e4333a9c0d";
inline constexpr std::string_view documentCopiedExtensionHeader = "7b047bae4d0072ef156ea94ba637566d563fea3a95d43c4c6314afc919b1d626";
inline constexpr std::string_view documentCopiedContract = "aba7800e6aab1898f3614f0b1ac53e59b9f622bf1e9d3a413f50d672a3662298";
inline constexpr std::string_view documentCopiedCatalog = "6e555d4c3bb71fbc965e1ca49671fab64d744913e18f45b9ba273505e0c6bcf5";

namespace document_facts_detail {
inline bool nonzero(const std::uint8_t (&hash)[32]) noexcept {
    for (auto byte : hash) if (byte) return true;
    return false;
}
inline bool hashMatches(const std::uint8_t (&hash)[32],std::string_view hex) noexcept {
    if (hex.size()!=64) return false;
    constexpr char digits[]="0123456789abcdef";
    for (std::size_t i=0;i<32;++i)
        if (hex[2*i]!=digits[hash[i]>>4] || hex[2*i+1]!=digits[hash[i]&15]) return false;
    return true;
}
// A fixed stack buffer emits the ONE allowed spelling, with no allocation,
// permissive parser, duplicate-key policy, locale or side effect.
struct Canonical {
    std::array<char,documentCopiedFactsCapacity> bytes{};
    std::size_t used{0};
    bool valid{true};
    void text(std::string_view value) noexcept {
        if (!valid || value.size()>bytes.size()-used) { valid=false; return; }
        if (!value.empty()) std::memcpy(bytes.data()+used,value.data(),value.size());
        used+=value.size();
    }
    void hash(const std::uint8_t (&value)[32]) noexcept {
        constexpr char digits[]="0123456789abcdef";
        for (auto byte:value) {
            const char pair[]{digits[byte>>4],digits[byte&15]}; text({pair,2});
        }
    }
};
} // namespace document_facts_detail

// Metadata selection is explicit; the backend flag is a separate opt-in.
inline constexpr bool documentCopiedProfileEnabled(DocumentCopiedProfile profile,bool editor_enabled) noexcept {
    return profile==DocumentCopiedProfile::pixel || profile==DocumentCopiedProfile::physical
        || (profile==DocumentCopiedProfile::editor && editor_enabled);
}

inline bool documentCopiedLimitsMatch(const BibEngineLimitsV1& value,
                                     DocumentCopiedProfile profile=DocumentCopiedProfile::pixel) noexcept {
    if (profile!=DocumentCopiedProfile::pixel && profile!=DocumentCopiedProfile::physical
        && profile!=DocumentCopiedProfile::editor) return false;
    const bool editor=profile==DocumentCopiedProfile::editor;
    return value.size==sizeof(BibEngineLimitsV1)
        && value.maximum_command_bytes==(editor ? BIB_ENGINE_EDITOR_MAX_WIRE_BYTES : 6246u)
        && value.maximum_query_bytes==(editor ? BIB_ENGINE_EDITOR_MAX_QUERY_BYTES : 48u)
        && value.maximum_reply_bytes==(editor ? BIB_ENGINE_EDITOR_REPLY_CAPACITY : 1048576u)
        && value.maximum_service_message_bytes==1048576 && value.maximum_retired_documents==8
        && value.maximum_inflight_resources==64 && value.reserved==0
        && value.maximum_resource_response_bytes==UINT64_C(67108864)
        && value.maximum_retained_resource_bytes==UINT64_C(134217728);
}
inline bool documentCopiedBuildValid(const BibEngineBuildV1& value,
                                    DocumentCopiedProfile profile=DocumentCopiedProfile::pixel) noexcept {
    if (profile!=DocumentCopiedProfile::pixel && profile!=DocumentCopiedProfile::physical
        && profile!=DocumentCopiedProfile::editor) return false;
    const bool editor=profile==DocumentCopiedProfile::editor;
    const auto required=editor ? documentCopiedEditorCapabilities
        : profile==DocumentCopiedProfile::physical ? documentCopiedPhysicalCapabilities : documentCopiedCapabilities;
    return value.size==sizeof(BibEngineBuildV1) && value.layout_revision==BIB_ENGINE_LAYOUT_V1
        && value.target_system==BIB_ENGINE_TARGET_BROWSER_WASM && value.target_processor==BIB_ENGINE_CPU_WASM32
        && value.pointer_bits==32 && value.lifetime==BIB_ENGINE_LIFETIME_PROCESS && value.maximum_starts==1
        && value.reserved==0 && value.fixed_viewport_width==800 && value.fixed_viewport_height==600
        && value.capabilities==required
        && document_facts_detail::hashMatches(value.contract_header_sha256,editor ? documentCopiedEditorContract : documentCopiedContract)
        && document_facts_detail::nonzero(value.build_identity_sha256)
        && document_facts_detail::nonzero(value.source_recipe_sha256);
}
inline bool documentCopiedBuildMatches(const BibEngineBuildV1& value,const BibEngineBuildV1& expected,
                                      DocumentCopiedProfile profile=DocumentCopiedProfile::pixel) noexcept {
    return documentCopiedBuildValid(value,profile) && documentCopiedBuildValid(expected,profile)
        && !std::memcmp(value.build_identity_sha256,expected.build_identity_sha256,32)
        && !std::memcmp(value.source_recipe_sha256,expected.source_recipe_sha256,32);
}

// Canonical JSON is the public consumer's EXACT 24-field pixel,30-field physical
// or38-field editor profile: sorted-key compact ASCII JSON, no newline.
// C limits are checked separately, not as extra JSON fields. The explicit
// profile must match capabilities; neither the facts nor bits select it.
// Missing/extra/duplicate/reordered/noncanonical keys fail byte comparison.
inline bool documentCopiedFactsMatch(std::string_view facts,const BibEngineBuildV1& build,
                                    const BibEngineLimitsV1& limits,
                                    DocumentCopiedProfile profile=DocumentCopiedProfile::pixel) noexcept {
    if (facts.empty() || facts.size()>documentCopiedFactsCapacity || !documentCopiedBuildValid(build,profile)
        || !documentCopiedLimitsMatch(limits,profile)) return false;
    if (profile==DocumentCopiedProfile::editor) {
        document_facts_detail::Canonical out;
        out.text("{\"action_ack_schema_sha256\":\""); out.text(BIB_ENGINE_DOCUMENT_V2_ACK_SCHEMA_SHA256_HEX);
        out.text("\",\"base_header_sha256\":\""); out.text(documentCopiedBaseHeader);
        out.text("\",\"binding\":\"copied-owner-bridge/direct-worker-editor-v1\",\"bridge_abi\":65536,\"build_sha256\":\"");
        out.hash(build.build_identity_sha256);
        out.text("\",\"capabilities\":\"2035\",\"contract_sha256\":\""); out.text(documentCopiedEditorContract);
        out.text("\",\"display_scale\":1,\"document_catalog_sha256\":\""); out.text(documentCopiedCatalog);
        out.text("\",\"document_contract_sha256\":\""); out.text(documentCopiedContract);
        out.text("\",\"document_header_sha256\":\""); out.text(documentCopiedExtensionHeader);
        out.text("\",\"document_schema_sha256\":\""); out.text(BIB_ENGINE_DOCUMENT_V2_SCHEMA_SHA256_HEX);
        out.text("\",\"editor_catalog_sha256\":\""); out.text(documentCopiedEditorCatalog);
        out.text("\",\"editor_command_max_bytes\":1048576,\"editor_header_sha256\":\""); out.text(documentCopiedEditorHeader);
        out.text("\",\"editor_profile\":\""); out.text(documentCopiedEditorProfile);
        out.text("\",\"editor_protocol_version\":1,\"editor_query_max_bytes\":236,\"editor_reply_capacity\":1048576,\"editor_schema_sha256\":\"");
        out.text(documentCopiedEditorSchema);
        out.text("\",\"host_abi_major\":1,\"host_abi_minor\":0,\"key_mapping_version\":1,\"kind\":\"foundation-copied-engine-editor-v1\",\"mouse_input_version\":1,\"physical_catalog_sha256\":\"");
        out.text(documentCopiedPhysicalCatalog);
        out.text("\",\"pointer_bits\":32,\"provider_abi_major\":1,\"provider_abi_minor\":1,\"pthread\":false,\"schema_version\":1,\"shared_memory\":false,\"source_recipe_sha256\":\"");
        out.hash(build.source_recipe_sha256);
        out.text("\",\"surface_capabilities\":\"8255\",\"surface_protocol_version\":2,\"target\":\"browser-wasm32\",\"viewport_height\":600,\"viewport_width\":800}");
        return out.valid && facts==std::string_view(out.bytes.data(),out.used);
    }
    const bool physical=profile==DocumentCopiedProfile::physical;
    document_facts_detail::Canonical out;
    out.text("{\"action_ack_schema_sha256\":\"");
    out.text(BIB_ENGINE_DOCUMENT_V2_ACK_SCHEMA_SHA256_HEX);
    out.text("\",\"base_header_sha256\":\""); out.text(documentCopiedBaseHeader);
    out.text("\",\"binding\":\"copied-owner-bridge/direct-worker-document-v2\",\"bridge_abi\":65536,\"build_sha256\":\"");
    out.hash(build.build_identity_sha256);
    out.text("\",\"capabilities\":\""); out.text(physical ? "2003" : "1795");
    if (physical) { out.text("\",\"command_catalog_sha256\":\""); out.text(documentCopiedPhysicalCatalog); }
    out.text("\",\"contract_sha256\":\""); out.text(documentCopiedContract);
    out.text(physical ? "\",\"display_scale\":1,\"document_catalog_sha256\":\"" : "\",\"document_catalog_sha256\":\"");
    out.text(documentCopiedCatalog);
    out.text("\",\"document_profile\":\""); out.text(physical ? documentCopiedPhysicalProfile : documentCopiedProfile);
    out.text("\",\"document_schema_sha256\":\"");
    out.text(BIB_ENGINE_DOCUMENT_V2_SCHEMA_SHA256_HEX);
    out.text("\",\"extension_header_sha256\":\""); out.text(documentCopiedExtensionHeader);
    out.text("\",\"host_abi_major\":1,\"host_abi_minor\":0");
    if (physical) out.text(",\"key_mapping_version\":1");
    out.text(",\"kind\":\"foundation-copied-engine-document-v2\"");
    if (physical) out.text(",\"mouse_input_version\":1");
    out.text(",\"pointer_bits\":32,\"provider_abi_major\":1,\"provider_abi_minor\":1,\"pthread\":false,\"schema_version\":1");
    out.text(",\"shared_memory\":false,\"source_recipe_sha256\":\""); out.hash(build.source_recipe_sha256);
    out.text("\"");
    if (physical) out.text(",\"surface_capabilities\":\"8225\",\"surface_protocol_version\":1");
    out.text(",\"target\":\"browser-wasm32\",\"viewport_height\":600,\"viewport_width\":800}");
    return out.valid && facts==std::string_view(out.bytes.data(),out.used);
}
} // namespace bib::copied
#endif
