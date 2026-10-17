// SPDX-License-Identifier: CC0-1.0
// PRIVATE SOURCE CANDIDATE. WebCore/JSC integration is uncompiled.
#ifndef BIB_FOUNDATION_SERVICE_HOST_H
#define BIB_FOUNDATION_SERVICE_HOST_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
    BIB_FOUNDATION_SERVICE_HOST_VERSION = 1,
    BIB_FOUNDATION_SERVICE_MAX_MESSAGE = 1048576,
    BIB_FOUNDATION_SERVICE_MAX_HEX = 2097152,
    BIB_FOUNDATION_SERVICE_DELIVERY_REJECTED = 0,
    BIB_FOUNDATION_SERVICE_DELIVERY_ACCEPTED = 1,
    BIB_FOUNDATION_SERVICE_DELIVERY_STALE = -1,
    BIB_FOUNDATION_SERVICE_DELIVERY_WRONG_THREAD = -2
};

// One serialized owner. This is a private host ABI, not a portable guest SDK.
// Callbacks must not throw or synchronously enter/pump the engine. All spans
// are borrowed only until return and must be copied before reporting admission.
// u64 values cross C directly; page JavaScript never receives memory addresses.
// All status callbacks return the existing numeric ServiceStatus 0..14.
typedef struct BibFoundationServiceHostV1 {
    uint32_t size;
    uint32_t version;
    uint32_t max_message_bytes;
    uint32_t max_retained_calls;
    uint32_t max_retained_bytes;
    uint32_t max_retired_documents;
    void* context;
    // Reject engine entry while pumping; nested ordinary engine turns may nest.
    // leave_engine must run after JSC lock/microtask destructors complete.
    uint32_t (*enter_engine)(void* context);
    void (*leave_engine)(void* context);
    // Composition has selected this built-in application document. This is
    // lifecycle setup, never service invocation or a security permission UI.
    // Return a fresh nonzero generation, or zero to leave services disabled.
    uint64_t (*begin_document)(void* context);
    void (*close_document)(void* context, uint64_t generation);
    uint32_t (*submit)(void* context, uint64_t generation,
        const uint8_t* bytes, uint32_t length, uint32_t source);
    uint32_t (*cancel)(void* context, uint64_t generation, uint64_t sequence);
    // Stage one exact ACK intent and return UNAVAILABLE until the owner has
    // performed actual ACK outside the engine. Then return its cached receipt.
    // Never calls WebServices::acknowledge while entered into the engine.
    uint32_t (*acknowledge)(void* context, uint64_t generation, uint64_t through);
    void (*schedule_owner)(void* context);
} BibFoundationServiceHostV1;

// Engine-side entry points proposed for this private diagnostic. Installation
// copies hooks before Page creation and is disabled unless explicitly enabled.
// install returns zero on success, a negative value on failure; on failure the
// host may destroy its proposed owner because no live hook table is retained.
int bib_foundation_services_install(const BibFoundationServiceHostV1* hooks);
int bib_foundation_services_deliver(uint64_t generation,
    const uint8_t* completion, uint32_t length);
uint32_t bib_foundation_services_collect_ack(uint64_t generation);
// Owner-requested closure may first retire the matching active generation;
// then this runs its saved controller. It never grants/adopts a new epoch.
int bib_foundation_services_dispose_retired(uint64_t generation);

#ifdef __cplusplus
}
#endif
#endif
