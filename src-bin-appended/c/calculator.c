#include <foundation/appended/guest.h>

static uint64_t diagnostics;
static uint8_t request[512], reply[512];

static uint32_t invoke(uint64_t handle, uint32_t operation, uint32_t payload) {
    foundation_guest_envelope e = {FOUNDATION_APPENDED_MESSAGE_REQUEST, 0,
        foundation_guest_generation(), foundation_guest_next_sequence(), handle, operation, 0, 0};
    if (!e.sequence || !foundation_guest_encode_envelope(request, sizeof(request), &e, payload)) return FOUNDATION_APPENDED_APP_EXHAUSTED;
    if (foundation_guest_call(request, 64 + payload, reply, sizeof(reply)) != FOUNDATION_APPENDED_TRANSPORT_OK) return FOUNDATION_APPENDED_APP_FAILED;
    foundation_guest_envelope result;
    if (foundation_guest_read_u32(reply) > sizeof(reply) ||
        !foundation_guest_decode_envelope(reply, foundation_guest_read_u32(reply), &result) || result.status != FOUNDATION_APPENDED_SERVICE_OK ||
        result.kind != FOUNDATION_APPENDED_MESSAGE_REPLY || result.generation != e.generation || result.sequence != e.sequence ||
        result.interface_handle != handle || result.operation != operation)
        return FOUNDATION_APPENDED_APP_FAILED;
    return FOUNDATION_APPENDED_APP_OK;
}
/* Acknowledge completed outcomes so repeated input stays within host limits. */
static uint32_t acknowledge(uint64_t through) {
    uint8_t value[8]; foundation_guest_write_u64(value, through);
    uint32_t n = foundation_guest_field_write(request + 64, sizeof(request) - 64, 0, 1, FOUNDATION_APPENDED_FIELD_U64, 1, value, 8);
    return invoke(0, FOUNDATION_APPENDED_CONTROL_ACKNOWLEDGE, n);
}
uint32_t foundation_guest_initialize(const uint8_t *context, uint32_t bytes) {
    (void)context; (void)bytes;
    static const uint8_t name[] = "foundation.diagnostics";
    uint32_t n = foundation_guest_discovery(request + 64, sizeof(request) - 64, name, sizeof(name) - 1, 1, 0, 0, 0);
    uint32_t status = invoke(0, FOUNDATION_APPENDED_CONTROL_DISCOVER, n);
    if (status || !foundation_guest_discovery_handle(reply + 64, foundation_guest_read_u32(reply) - 64, &diagnostics)) return FOUNDATION_APPENDED_APP_FAILED;
    return acknowledge(foundation_guest_read_u64(reply + 24));
}
uint32_t foundation_guest_dispatch(const uint8_t *message, uint32_t bytes) {
    foundation_guest_envelope e; foundation_guest_record r; foundation_guest_field field;
    if (!foundation_guest_decode_envelope(message, bytes, &e) || e.operation != 1 ||
        (e.kind != FOUNDATION_APPENDED_MESSAGE_REQUEST && e.kind != FOUNDATION_APPENDED_MESSAGE_EVENT)) return FOUNDATION_APPENDED_APP_INVALID_INPUT;
    foundation_guest_record_begin(&r, message + 64, bytes - 64);
    uint32_t operands[2];
    for (uint16_t id = 1; id <= 2; ++id) {
        if (foundation_guest_record_next(&r, &field) != 1 || field.id != id || field.type != FOUNDATION_APPENDED_FIELD_U32)
            return FOUNDATION_APPENDED_APP_INVALID_INPUT;
        operands[id - 1] = foundation_guest_read_u32(field.data);
    }
    if (foundation_guest_record_next(&r, &field) != 0) return FOUNDATION_APPENDED_APP_INVALID_INPUT;
    uint32_t sum = operands[0] + operands[1]; uint8_t value[4], overflow = sum < operands[0];
    if (overflow) sum = 0;
    foundation_guest_write_u32(value, sum);
    uint32_t n = foundation_guest_field_write(request + 64, sizeof(request) - 64, 0, 1, FOUNDATION_APPENDED_FIELD_U32, 1, value, 4);
    n = foundation_guest_field_write(request + 64, sizeof(request) - 64, n, 2, FOUNDATION_APPENDED_FIELD_BOOL, 1, &overflow, 1);
    uint32_t status = invoke(diagnostics, 1, n);
    if (status) return status;
    if (foundation_guest_read_u32(reply) != 64 + n) return FOUNDATION_APPENDED_APP_FAILED;
    for (uint32_t i = 0; i != n; ++i) if (request[64 + i] != reply[64 + i]) return FOUNDATION_APPENDED_APP_FAILED;
    return acknowledge(foundation_guest_read_u64(reply + 24));
}
