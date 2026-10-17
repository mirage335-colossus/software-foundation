// SPDX-License-Identifier: CC0-1.0
// Private source candidate. This is not the portable guest ABI.
#ifndef BIB_APP_RESOURCE_HOST_H
#define BIB_APP_RESOURCE_HOST_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
enum { BIB_APP_RESOURCE_HOST_VERSION = 1, BIB_APP_RESOURCE_BUNDLE_HOST_VERSION = 1 };
typedef struct BibAppResourceRequestV1 {
    uint32_t size;
    uint32_t version;
    uint64_t document_epoch;
    const uint8_t* method;
    uint32_t method_length;
    const uint8_t* resolved_url;
    uint32_t resolved_url_length;
} BibAppResourceRequestV1;
typedef struct BibAppResourceResponseV1 {
    uint32_t size;
    uint32_t version;
    uint32_t status;
    uint32_t mime_length;
    const uint8_t* mime;
    const uint8_t* body;
    uint64_t body_length;
    uint64_t content_length;
    uint64_t lease;
} BibAppResourceResponseV1;
typedef struct BibAppResourceHostV1 {
    uint32_t size;
    uint32_t version;
    uint64_t document_epoch;
    uint64_t max_response_bytes;
    uint32_t max_inflight;
    uint32_t reserved;
    uint64_t max_retained_bytes;
    void* context;
    // Serialized owner thread only. Callbacks must not throw, execute author
    // script, pump/enter the engine or use filesystem/network fallback.
    // Every nonzero lease, including a rejected/malformed response, is released
    // exactly once. Immutable MIME/body spans remain valid until that release.
    // The engine copies them before release and before parser callbacks.
    int32_t (*resolve)(void*, const BibAppResourceRequestV1*, BibAppResourceResponseV1*);
    void (*release)(void*, uint64_t lease);
} BibAppResourceHostV1;
// Install one bundle for one engine session. The engine constructs ONE internal
// body/inflight budget from these limits and shares it across all epoch queues,
// including after old queues close/die. No STL object crosses this C boundary.
// All callbacks run on the installation/owner thread without engine reentry.
typedef struct BibAppResourceBundleHostV1 {
    uint32_t size;
    uint32_t version;
    uint64_t max_response_bytes;
    uint32_t max_inflight;
    uint32_t reserved;
    uint64_t max_retained_bytes;
    void* context;
    // Allocates a fresh nonzero epoch, never reusing a prior value. Metadata
    // only: no host Registry/Module invocation, package copy or engine call.
    // Returns 0 and a complete per-epoch table, negative on refusal. At most
    // two contexts (active/pending, including unreleased retired leases) exist.
    int32_t (*begin_epoch)(void*, BibAppResourceHostV1* out);
    // Idempotent for stale epochs. Call only after synchronous resolve/copy/
    // release returns and after cancelling its queue tasks. Outstanding raw C
    // leases keep the retired context/spans alive until their explicit release.
    void (*retire_epoch)(void*, uint64_t document_epoch);
} BibAppResourceBundleHostV1;
// The bundle context outlives the engine, its callbacks and all raw host leases.
// Provider-retained copied bodies need only the engine's shared budget, never a
// raw host context. Closing an epoch never resets that budget or strict policy.
#ifdef __cplusplus
}
#endif
#endif
