// SPDX-License-Identifier: CC0-1.0
// C ABI for optional retained-engine providers. Generic guards/adapters exist;
// the actual WebCore binding and target/runtime qualification remain unfinished.
// Private retained-engine host contract; never a portable application guest SDK.
#ifndef FOUNDATION_APPENDED_ENGINE_PROVIDER_H
#define FOUNDATION_APPENDED_ENGINE_PROVIDER_H
#include <stdint.h>

#if defined(_WIN32)
#define BIB_ENGINE_CALL __cdecl
#else
#define BIB_ENGINE_CALL
#endif
#if defined(BIB_ENGINE_BUILD_DLL) && defined(BIB_ENGINE_USE_DLL)
#error "Choose only one provider DLL role"
#endif
#if defined(_WIN32) && defined(BIB_ENGINE_BUILD_DLL)
#define BIB_ENGINE_EXPORT __declspec(dllexport)
#elif defined(_WIN32) && defined(BIB_ENGINE_USE_DLL)
#define BIB_ENGINE_EXPORT __declspec(dllimport)
#elif defined(__GNUC__)
#define BIB_ENGINE_EXPORT __attribute__((visibility("default")))
#else
#define BIB_ENGINE_EXPORT
#endif
#ifdef __cplusplus
extern "C" {
#endif

// Stored statuses/flags are fixed-width integers, never C enum ABI values.
// Unknown flags and nonzero reserved fields reject before retaining anything.
#define BIB_ENGINE_ABI_MAJOR 1u
#define BIB_ENGINE_ABI_MINOR 0u
#define BIB_ENGINE_OK 0
#define BIB_ENGINE_INVALID -1
#define BIB_ENGINE_UNSUPPORTED -2
#define BIB_ENGINE_WRONG_THREAD -3
#define BIB_ENGINE_REENTRANT -4
#define BIB_ENGINE_STALE -5
#define BIB_ENGINE_LIMIT -6
#define BIB_ENGINE_CLOSED -7
#define BIB_ENGINE_PROCESS_EXIT_REQUIRED -8

#define BIB_ENGINE_LIFETIME_PROCESS 1u
#define BIB_ENGINE_LAYOUT_V1 1u
#define BIB_ENGINE_TARGET_LINUX 1u
#define BIB_ENGINE_TARGET_WINDOWS 2u
#define BIB_ENGINE_TARGET_BROWSER_WASM 3u
#define BIB_ENGINE_CPU_X86_64 1u
#define BIB_ENGINE_CPU_AARCH64 2u
#define BIB_ENGINE_CPU_WASM32 3u
#define BIB_ENGINE_START_NOT_RETAINED 0u
#define BIB_ENGINE_START_PROCESS_COMMITTED 1u
#define BIB_ENGINE_START_READY 2u
#define BIB_ENGINE_CAP_SERVICE_QUEUE (UINT64_C(1) << 0)
#define BIB_ENGINE_CAP_APP_BUNDLE (UINT64_C(1) << 1)
#define BIB_ENGINE_CAP_SEMANTIC_SNAPSHOT_V1 (UINT64_C(1) << 2)
#define BIB_ENGINE_CAP_SEMANTIC_ACTION_V1 (UINT64_C(1) << 3)
#define BIB_ENGINE_CAP_KEY_V1 (UINT64_C(1) << 4)
#define BIB_ENGINE_CAP_COMPOSITION_V1 (UINT64_C(1) << 5)
#define BIB_ENGINE_CAP_FOCUS_V1 (UINT64_C(1) << 6)
#define BIB_ENGINE_CAP_POINTER_V1 (UINT64_C(1) << 7)
#define BIB_ENGINE_CAP_DIRTY_RGBA8 (UINT64_C(1) << 8)
// Surface/form/popup schemas have no assigned bits until their contracts freeze.
#define BIB_ENGINE_COMMAND_KEY 1u
#define BIB_ENGINE_COMMAND_COMPOSITION 2u
#define BIB_ENGINE_COMMAND_FOCUS 3u
#define BIB_ENGINE_COMMAND_SEMANTIC_ACTION 4u
#define BIB_ENGINE_COMMAND_POINTER 5u
#define BIB_ENGINE_QUERY_SEMANTIC_SNAPSHOT 1u
#define BIB_ENGINE_QUERY_EDITOR_FLAGS 2u

typedef struct BibEngineBytesV1 {
    const uint8_t* data;
    uint32_t length;
    uint32_t reserved;
} BibEngineBytesV1;

typedef struct BibEngineDocumentV1 {
    uint64_t application_instance;
    uint64_t document_sequence;
    uint64_t service_generation;
} BibEngineDocumentV1;

typedef struct BibEngineBuildV1 {
    uint32_t size;
    uint32_t layout_revision;
    uint32_t target_system;       // Assigned target IDs, exact SDK manifest match.
    uint32_t target_processor;
    uint32_t pointer_bits;
    uint32_t lifetime;            // PROCESS only in this first implementation.
    uint32_t maximum_starts;      // Exactly 1; neither reset nor unload exists.
    uint32_t reserved;
    uint32_t fixed_viewport_width;  // Current candidate 800; no resize promise.
    uint32_t fixed_viewport_height; // Current candidate 600.
    uint64_t capabilities;
    uint8_t contract_header_sha256[32];
    uint8_t build_identity_sha256[32]; // Noncircular provider-build.json identity.
    uint8_t source_recipe_sha256[32];
} BibEngineBuildV1;

typedef struct BibEngineLimitsV1 {
    uint32_t size;
    uint32_t maximum_command_bytes;
    uint32_t maximum_query_bytes;
    uint32_t maximum_reply_bytes;
    uint32_t maximum_service_message_bytes;
    uint32_t maximum_retired_documents;
    uint32_t maximum_inflight_resources;
    uint32_t reserved;
    uint64_t maximum_resource_response_bytes;
    uint64_t maximum_retained_resource_bytes;
} BibEngineLimitsV1;

typedef struct BibEngineDamageV1 {
    uint32_t size;
    uint32_t format;              // 1 = packed unpremultiplied RGBA8.
    BibEngineDocumentV1 document;
    uint64_t frame_revision;
    int32_t x, y, width, height;
    uint32_t stride_bytes;
    uint32_t length;
    const uint8_t* bytes;         // Borrowed until callback returns; copy only.
} BibEngineDamageV1;

// Resource epoch is private resource authority; it never substitutes for the
// service_generation, FormVersion, popup token or accepted surface context.
typedef struct BibEngineResourceRequestV1 {
    uint32_t size;
    uint32_t reserved;
    uint64_t resource_epoch;
    BibEngineBytesV1 method;
    BibEngineBytesV1 resolved_url;
} BibEngineResourceRequestV1;

typedef struct BibEngineResourceResponseV1 {
    uint32_t size;
    uint32_t status;
    uint64_t lease;
    BibEngineBytesV1 mime;
    const uint8_t* body;
    uint64_t body_length;
    uint64_t content_length;
} BibEngineResourceResponseV1;

typedef struct BibEngineResourceEpochV1 {
    uint32_t size;
    uint32_t reserved;
    uint64_t resource_epoch;
    void* context;
    int32_t (BIB_ENGINE_CALL *resolve)(void*, const BibEngineResourceRequestV1*, BibEngineResourceResponseV1*);
    void (BIB_ENGINE_CALL *release)(void*, uint64_t lease);
} BibEngineResourceEpochV1;

// This is ONE copied host table. Every callback except wake is owner-thread
// only. All callbacks contain exceptions. They cannot enter/pump the engine or
// invoke Registry/Module services synchronously. The immutable resource lookup
// and bounded lifecycle/queue operations are the only synchronous callbacks.
typedef struct BibEngineHostV1 {
    uint32_t size;
    uint32_t abi_major;
    uint32_t abi_minor;
    uint32_t reserved;
    void* context;
    void (BIB_ENGINE_CALL *wake)(void*); // May originate from an engine worker.
    void (BIB_ENGINE_CALL *replace_timer_ms)(void*, double delay, uint32_t armed);
    void (BIB_ENGINE_CALL *damage)(void*, const BibEngineDamageV1*);
    void (BIB_ENGINE_CALL *persistence)(void*, const BibEngineBytesV1*);
    // Existing ServiceStatus domain 0..14: 0 (OK) admits engine entry; every
    // nonzero status rejects. This is NOT a boolean-returning callback.
    uint32_t (BIB_ENGINE_CALL *enter_engine)(void*);
    void (BIB_ENGINE_CALL *leave_engine)(void*);
    // Prospective identity has nonzero instance/sequence and generation zero;
    // the returned fresh generation completes it only after successful binding.
    uint64_t (BIB_ENGINE_CALL *begin_service_document)(void*, const BibEngineDocumentV1* prospective);
    void (BIB_ENGINE_CALL *close_service_document)(void*, uint64_t generation);
    // Service callbacks retain the existing ServiceStatus 0..14 domain; these
    // unsigned values are not the provider's negative transport statuses.
    uint32_t (BIB_ENGINE_CALL *submit_service)(void*, uint64_t generation, const BibEngineBytesV1*, uint32_t source);
    uint32_t (BIB_ENGINE_CALL *cancel_service)(void*, uint64_t generation, uint64_t sequence);
    uint32_t (BIB_ENGINE_CALL *stage_service_ack)(void*, uint64_t generation, uint64_t through);
    int32_t (BIB_ENGINE_CALL *begin_resource_epoch)(void*, const BibEngineDocumentV1* prospective, BibEngineResourceEpochV1*);
    void (BIB_ENGINE_CALL *retire_resource_epoch)(void*, uint64_t resource_epoch);
} BibEngineHostV1;

typedef struct BibEngineStartV1 {
    uint32_t size;
    uint32_t raster_output;       // 0 semantic-only; 1 damage callbacks enabled.
    uint32_t reserved0;
    uint32_t reserved1;
    uint64_t required_capabilities;
    BibEngineLimitsV1 limits;
    BibEngineBytesV1 entry_url;    // app://<packageSHA>/web/path, canonical UTF-8.
    BibEngineBytesV1 persist_seed;
    uint8_t application_package_sha256[32];
} BibEngineStartV1;

typedef struct BibEngineStartResultV1 {
    uint32_t size;
    uint32_t phase;               // NOT_RETAINED / PROCESS_COMMITTED / READY.
    uint64_t application_instance;
} BibEngineStartResultV1;

typedef struct BibEngineAdvanceV1 {
    uint32_t size;
    uint32_t render;              // 0 run-loop only, 1 also update/render.
    uint64_t application_instance;
} BibEngineAdvanceV1;

// A command has potential effects. The operation/schema pair is explicitly
// negotiated. The engine validates the complete input, live document/context
// authority and FULL reply capacity before executing. No size-probe/retry path.
typedef struct BibEngineCommandV1 {
    uint32_t size;
    uint32_t operation;
    BibEngineDocumentV1 expected;
    uint64_t request_sequence;
    uint8_t schema_sha256[32];
    BibEngineBytesV1 payload;
} BibEngineCommandV1;

typedef struct BibEngineReplyBufferV1 {
    uint32_t size;
    uint32_t capacity;
    uint8_t* bytes;               // Caller allocated; provider never frees it.
} BibEngineReplyBufferV1;

typedef struct BibEngineCommandResultV1 {
    uint32_t size;
    uint32_t disposition;         // 0 rejected, 1 consumed, 2 consumed-unknown.
    uint64_t request_sequence;
    uint32_t bytes_written;
    uint32_t handled;             // Boolean integer; distinct from disposition.
} BibEngineCommandResultV1;

// Query is read-only snapshot work. Its single call must have the advertised
// maximum reply capacity before capture; there is no mutable two-call probe.
typedef struct BibEngineQueryV1 {
    uint32_t size;
    uint32_t kind;
    BibEngineDocumentV1 expected;
    uint8_t schema_sha256[32];
    BibEngineBytesV1 payload;
} BibEngineQueryV1;

typedef struct BibEngineQueryResultV1 {
    uint32_t size;
    uint32_t bytes_written;
    BibEngineDocumentV1 document;
    uint64_t semantic_revision;
} BibEngineQueryResultV1;

typedef struct BibEngineProviderV1 {
    uint32_t size;                // Initialized complete prefix in caller buffer.
    uint32_t abi_major;
    uint32_t abi_minor;
    uint32_t reserved;
    BibEngineBuildV1 build;
    BibEngineLimitsV1 limits;
    int32_t (BIB_ENGINE_CALL *start)(const BibEngineHostV1*, const BibEngineStartV1*, BibEngineStartResultV1*);
    int32_t (BIB_ENGINE_CALL *advance)(const BibEngineAdvanceV1*);
    int32_t (BIB_ENGINE_CALL *current_document)(uint64_t application_instance, BibEngineDocumentV1*);
    int32_t (BIB_ENGINE_CALL *command)(const BibEngineCommandV1*, BibEngineReplyBufferV1*, BibEngineCommandResultV1*);
    int32_t (BIB_ENGINE_CALL *query)(const BibEngineQueryV1*, BibEngineReplyBufferV1*, BibEngineQueryResultV1*);
    int32_t (BIB_ENGINE_CALL *deliver_services)(const BibEngineDocumentV1*, const BibEngineBytesV1*);
    uint32_t (BIB_ENGINE_CALL *collect_service_ack)(const BibEngineDocumentV1*);
    int32_t (BIB_ENGINE_CALL *dispose_retired_service_document)(uint64_t application_instance, uint64_t generation);
    // No destroy/reset/unload method. A future qualified lifetime is a new
    // explicitly negotiated contract, not inferred from document disposal.
} BibEngineProviderV1;

// One native DSO/DLL entry; proposed spelling, not an existing exported symbol.
// Caller zeroes its buffer, provides capacity; provider writes a bounded prefix.
// Minor tails are optional, size+capability-gated; incompatible major rejects.
// Each supported target must freeze actual C/C++ offsets/alignment/call ABI.
BIB_ENGINE_EXPORT int32_t BIB_ENGINE_CALL bib_engine_get_provider_v1(uint32_t requested_major,
    uint32_t maximum_minor, uint32_t caller_capacity, BibEngineProviderV1* output);

#ifdef __cplusplus
}
#endif
#endif
