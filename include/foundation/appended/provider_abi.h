#ifndef FOUNDATION_APPENDED_PROVIDER_ABI_H
#define FOUNDATION_APPENDED_PROVIDER_ABI_H
#include <foundation/appended/abi.h>

/* Additive service contract; the transport bootstrap and scalar exports do not change. */
#define FOUNDATION_PROVIDER_SERVICE_NAME "foundation.providers"
#define FOUNDATION_PROVIDER_MAJOR 1u
#define FOUNDATION_PROVIDER_MINOR 0u
#define FOUNDATION_PROVIDER_REGISTER 1u
#define FOUNDATION_PROVIDER_RESPOND 2u
#define FOUNDATION_PROVIDER_DISCOVER 3u
#define FOUNDATION_PROVIDER_EVENT_CALL 1u
#define FOUNDATION_PROVIDER_MAX_PROVIDERS 32u
#define FOUNDATION_PROVIDER_MAX_PAYLOAD_BYTES 32768u
#define FOUNDATION_PROVIDER_MAX_RETAINED_CALLS 64u
#define FOUNDATION_PROVIDER_MAX_RETAINED_BYTES 1048576u
#define FOUNDATION_PROVIDER_MAX_NAME_BYTES 128u
/* Fixed envelope plus required control/event fields, excluding payload bytes. */
#define FOUNDATION_PROVIDER_CALL_OVERHEAD_BYTES 100u
#define FOUNDATION_PROVIDER_RESPONSE_OVERHEAD_BYTES 116u
#define FOUNDATION_PROVIDER_SCHEMA_SHA256_HEX "846fd7a2aa16758db702aa30791730ab6de6635a50ba90234995cb06a7ec93de"
#define FOUNDATION_PROVIDER_SCHEMA_BYTES \
    0x84,0x6f,0xd7,0xa2,0xaa,0x16,0x75,0x8d,0xb7,0x02,0xaa,0x30,0x79,0x17,0x30,0xab, \
    0x6d,0xe6,0x63,0x5a,0x50,0xba,0x90,0x23,0x49,0x95,0xcb,0x06,0xa7,0xec,0x93,0xde

/* REGISTER: name, major, minor, schema32, maximum request, maximum reply.
 * RESPOND: invocation token, provider handle, status, payload (even empty).
 * DISCOVER: name, major, minimum minor, maximum minor, optional schema32.
 * CALL event payload: provider handle, application operation, payload bytes.
 * See abi/appended/providers/v1.json for field IDs and exact version identity. */
#endif
