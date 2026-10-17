// SPDX-License-Identifier: CC0-1.0
// Private source candidate; no WebCore implementation is supplied here.
#pragma once
#include <foundation/appended/engine_provider.h>
#include <foundation/appended/engine_provider_document_v2.h>
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

// Separate opt-in descriptor: EnginePrivateV1 and its existing copied bindings
// retain their original layout and minor0 behavior. No actual engine supplies
// this descriptor yet. A profile cannot be enabled by capability inference.
inline constexpr std::uint32_t document_private_interface_version = 1;
inline constexpr std::uint32_t document_pixel_profile = 1, document_physical_profile = 2;
struct EngineDocumentPrivateV1 {
    std::uint32_t size;
    std::uint32_t version;
    std::uint32_t profile;
    std::uint32_t reserved;
    std::uint64_t worker_epoch; // Fresh nonzero composition-issued, process-lived.
    std::array<std::uint8_t, 32> base_header_sha256;
    std::array<std::uint8_t, 32> extension_header_sha256;
    std::array<std::uint8_t, 32> contract_sha256;
    std::array<std::uint8_t, 32> catalog_sha256;
    std::array<std::uint8_t, 32> physical_catalog_sha256; // Zero for pixel.
    // These callbacks execute inside the complete engine guard. They perform
    // bounded, inert validation only: no host/Registry callback, JS, retention,
    // mutation or nested entry. Request validation checks the exact packet,
    // binding identity and already-owned immutable publication/lease metadata
    // only; cached old-buffer scalar checks do NOT establish live authority.
    // The dispatched native query/action MUST perform its actual checkpoint
    // and live Document/control/lease/current-buffer validation inside this
    // SAME complete engine turn before any author effect. Stale live state may
    // produce a known inner rejected completion, retained until checked ACK;
    // it must not be mislabeled an inert transport rejection after dispatch.
    // Reply validation must deep-decode the whole exact NDV2 publication and
    // paired readback, including native joins/redaction/bounds. The outer guard
    // independently validates canonical request bytes and fixed reply joins.
    // Neither callback is ever called for ACK7, cached action or cached receipt.
    // query is exactly 0 for commands or 1 for queries: their kind spaces overlap.
    // A known request-validation rejection is inert and does not burn sequence.
    // Any uncertainty after dispatch of a new-profile command/query is terminal
    // at the outer layer; a checked NDV2 inner unknown outcome is still distinct.
    std::int32_t (*validate_request)(void*, std::uint64_t, const BibEngineDocumentV1*,
        std::uint32_t query, std::uint32_t operation, std::uint64_t, const BibEngineBytesV1*);
    std::int32_t (*validate_reply)(void*, std::uint64_t, const BibEngineDocumentV1*,
        std::uint32_t query, std::uint32_t operation, std::uint64_t, const BibEngineBytesV1*, const BibEngineBytesV1*);
    // Called only for the first fresh matching ACK, outside engine entry. The
    // exact owned original action is still retained. Release only its native
    // metadata/reservation: no allocation, host/DOM/JSC/Registry access, nested
    // entry or effect replay. Return zero only after retirement is complete.
    // Any nonzero return or exception permanently poisons this process guard;
    // the guard retains its original unknown action and performs no retry.
    std::int32_t (*retire_action_metadata)(void*, std::uint64_t, const BibEngineCommandV1*);
};
std::int32_t bind_engine_document_private(const EnginePrivateV1&, const EngineDocumentPrivateV1&) noexcept;

// A separate opt-in table for the explicit editor2035 contract. Neither of the
// preceding private table layouts changes, and COMPOSITION_V1 alone never
// selects this binding. The three tables are validated and installed together
// before any public table can be obtained or a start can retain callbacks.
inline constexpr std::uint32_t editor_private_interface_version = 1;
struct EngineEditorPrivateV1 {
    std::uint32_t size;
    std::uint32_t version;
    std::uint32_t reserved0;
    std::uint32_t reserved1;
    std::uint64_t worker_epoch; // Must equal the paired document binding.
    std::array<std::uint8_t, 32> editor_header_sha256;
    std::array<std::uint8_t, 32> contract_sha256;
    std::array<std::uint8_t, 32> catalog_sha256;
    std::array<std::uint8_t, 32> schema_sha256;
    // Inert admission against the already-owned owner/native facts only: no
    // DOM/JSC/host callback, retention, mutation, native execution or nested
    // entry. Domain is exactly0 for commands or1 for queries. Known rejection
    // happens before sequence consumption; the outer guard also enforces the
    // pending-form barrier. Read-only projection must be explicitly admitted.
    std::int32_t (*admit_request)(void*, std::uint64_t, const BibEngineDocumentV1*,
        std::uint32_t domain, std::uint32_t operation, std::uint64_t, const BibEngineBytesV1*);
    // Deep validation of the complete checked binary projection/receipt and
    // native joins, without effects, callbacks or retained state. A
    // native editor unknown outcome is never a normal checked completion.
    std::int32_t (*validate_reply)(void*, std::uint64_t, const BibEngineDocumentV1*,
        std::uint32_t domain, std::uint32_t operation, std::uint64_t, const BibEngineBytesV1*, const BibEngineBytesV1*);
    // Invoked only inside the same complete Host enter/leave turn, after owned
    // input/output reservation and admission. Commands are non-replayable;
    // any entered uncertainty permanently poisons the process guard. These
    // callbacks must implement actual native projection, observation and
    // revocation, rather than forwarding editor values through legacy op2.
    std::int32_t (*project)(void*, std::uint64_t, const BibEngineQueryV1*, BibEngineReplyBufferV1*, BibEngineQueryResultV1*);
    std::int32_t (*apply)(void*, std::uint64_t, const BibEngineCommandV1*, BibEngineReplyBufferV1*, BibEngineCommandResultV1*);
    std::int32_t (*revoke)(void*, std::uint64_t, const BibEngineCommandV1*, BibEngineReplyBufferV1*, BibEngineCommandResultV1*);
};
std::int32_t bind_engine_editor_private(const EnginePrivateV1&, const EngineDocumentPrivateV1&,
    const EngineEditorPrivateV1&) noexcept;
} // namespace bib::provider_candidate
