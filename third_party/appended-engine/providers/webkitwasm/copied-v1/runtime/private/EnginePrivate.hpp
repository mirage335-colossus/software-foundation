// SPDX-License-Identifier: CC0-1.0
// Private source candidate; no WebCore implementation is supplied here.
#pragma once
#include <foundation/appended/engine_provider.h>
#include <array>
#include <cstdint>

namespace bib::provider_candidate {
inline constexpr std::uint64_t known_capabilities = (UINT64_C(1) << 9) - 1;
inline constexpr std::uint32_t private_interface_version = 1;
inline constexpr std::array<std::uint8_t, 32> contract_header_sha256{
    0xa8,0xe8,0x9d,0xa8,0x5d,0x34,0xb2,0x9a,0x4d,0x1b,0xc4,0x54,0x49,0x57,0x91,0xfa,
    0x60,0x4b,0x81,0xe3,0x47,0x7e,0x48,0xce,0x8c,0xa9,0x02,0xe4,0x33,0x3a,0x9c,0x0d};

// All catalog/implementation/context bytes and code are engine-private and
// process-lived. Missing handlers cannot enable a capability. Schema hashes
// identify the exact future catalog; no real catalog or engine binding exists.
struct Operation {
    std::uint32_t kind;
    std::uint32_t maximum_input_bytes;
    std::uint32_t required_reply_capacity;
    std::uint64_t capability;
    std::array<std::uint8_t, 32> schema;
};

struct EnginePrivateV1 {
    std::uint32_t size;
    std::uint32_t version;
    BibEngineBuildV1 build;
    BibEngineLimitsV1 limits;
    std::uint64_t application_instance; // Fresh nonzero composition-issued ID.
    void* context;
    const Operation* commands;
    std::uint32_t command_count;
    const Operation* queries;
    std::uint32_t query_count;
    // Preflight is strictly inert: no callback, retention, engine execution or
    // effect. Its complete copied config and limits are validated before commit.
    // Validate the full canonical resource URL/decoding, package digest and
    // copied profile/limits here, without invoking resource callbacks. The host
    // supplies a verified immutable Package; the real entry response is checked
    // during loading before its Document receives author bytes.
    std::int32_t (*preflight)(void*, const BibEngineStartV1*);
    // Called only after permanent callback/config retention and PROCESS_COMMITTED.
    // The outer guard owns enter_engine/leave_engine around this entire call.
    std::int32_t (*start)(void*, const BibEngineHostV1*, const BibEngineStartV1*, std::uint64_t);
    std::int32_t (*advance)(void*, const BibEngineAdvanceV1*);
    // Exact identity read: no allocation, JS, callback, pump or document adoption.
    std::int32_t (*current_document)(void*, std::uint64_t, BibEngineDocumentV1*);
    // Core burns sequence before dispatch. A nonzero result is consumed-unknown;
    // the backend never decides that an entered effect is safe to retry.
    std::int32_t (*command)(void*, const BibEngineCommandV1*, BibEngineReplyBufferV1*, BibEngineCommandResultV1*);
    std::int32_t (*query)(void*, const BibEngineQueryV1*, BibEngineReplyBufferV1*, BibEngineQueryResultV1*);
    std::int32_t (*deliver_services)(void*, const BibEngineDocumentV1*, const BibEngineBytesV1*);
    std::uint32_t (*collect_service_ack)(void*, const BibEngineDocumentV1*);
    std::int32_t (*dispose_retired_service_document)(void*, std::uint64_t, std::uint64_t);
    // Required explicit private operation for advertised APP_BUNDLE. It receives
    // the copied host table; only a future real resource adapter may provide it.
    std::int32_t (*install_resources)(void*, const BibEngineHostV1*, const BibEngineStartV1*, std::uint64_t);
};

// One private binding, before query/start. This symbol is not part of the public
// table or a Wasm bridge and does not qualify an SDK/provider. A missing binding
// makes the C getter return UNSUPPORTED without populating a callable table.
std::int32_t bind_engine_private(const EnginePrivateV1&) noexcept;
} // namespace bib::provider_candidate
