#ifndef FOUNDATION_APPENDED_GUEST_H
#define FOUNDATION_APPENDED_GUEST_H
#ifndef FOUNDATION_APPENDED_GUEST
#define FOUNDATION_APPENDED_GUEST 1
#endif
#include <foundation/appended/abi.h>

#if defined(__cplusplus)
extern "C" {
#endif

/* These are local decoded values. They are never copied to the wire. */
typedef struct foundation_guest_envelope {
    uint32_t kind, flags;
    uint64_t generation, sequence, interface_handle;
    uint32_t operation, status;
    uint64_t correlation;
} foundation_guest_envelope;
typedef struct foundation_guest_field {
    uint16_t id;
    uint8_t type, flags;
    const uint8_t *data;
    uint32_t bytes;
} foundation_guest_field;
typedef struct foundation_guest_record {
    const uint8_t *data;
    uint32_t bytes, offset, count;
    uint16_t previous;
} foundation_guest_record;
typedef struct foundation_guest_init_context {
    uint64_t generation;
    uint32_t maximum_message_bytes;
    uint8_t bootstrap_schema[32];
    uint32_t maximum_retained_requests, maximum_retained_results, maximum_retained_bytes;
} foundation_guest_init_context;

uint16_t foundation_guest_read_u16(const uint8_t *);
uint32_t foundation_guest_read_u32(const uint8_t *);
uint64_t foundation_guest_read_u64(const uint8_t *);
void foundation_guest_write_u16(uint8_t *, uint16_t);
void foundation_guest_write_u32(uint8_t *, uint32_t);
void foundation_guest_write_u64(uint8_t *, uint64_t);
int foundation_guest_utf8(const uint8_t *, uint32_t);
/* Returns 1 on success, 0 on malformed input. No partial output on failure. */
int foundation_guest_decode_envelope(const uint8_t *, uint32_t, foundation_guest_envelope *);
int foundation_guest_encode_envelope(uint8_t *, uint32_t, const foundation_guest_envelope *, uint32_t);
void foundation_guest_record_begin(foundation_guest_record *, const uint8_t *, uint32_t);
/* Returns 1 for a field, 0 at end, -1 for malformed canonical record. */
int foundation_guest_record_next(foundation_guest_record *, foundation_guest_field *);
/* Appends one canonical field; returns new length, or UINT32_MAX on failure. */
uint32_t foundation_guest_field_write(uint8_t *, uint32_t, uint32_t, uint16_t,
                                    uint8_t, uint8_t, const uint8_t *, uint32_t);
int foundation_guest_decode_context(const uint8_t *, uint32_t, foundation_guest_init_context *);
const foundation_guest_init_context *foundation_guest_context(void);
uint64_t foundation_guest_generation(void);
uint32_t foundation_guest_maximum_message(void);
/* Returns 0 on exhaustion. Sequences never wrap; retry using saved request bytes. */
uint64_t foundation_guest_next_sequence(void);
/* Encode the bootstrap discovery record (without an envelope). */
uint32_t foundation_guest_discovery(uint8_t *, uint32_t, const uint8_t *, uint32_t,
                                   uint32_t, uint32_t, uint32_t, const uint8_t *);
/* Decode a successful discovery reply's canonical record. */
int foundation_guest_discovery_handle(const uint8_t *, uint32_t, uint64_t *);
/* Typed scalar gateway; buffers remain borrowed only for this call. */
uint32_t foundation_guest_call(const uint8_t *, uint32_t, uint8_t *, uint32_t);

/* Application hooks. The SDK supplies weak defaults. Override as needed. The
 * context and message bytes are borrowed for the duration of the hook only. */
uint32_t foundation_guest_initialize(const uint8_t *, uint32_t);
uint32_t foundation_guest_dispatch(const uint8_t *, uint32_t);
uint32_t foundation_guest_step(uint32_t);
void foundation_guest_shutdown(uint32_t);

#if defined(__cplusplus)
}
#endif
#endif
