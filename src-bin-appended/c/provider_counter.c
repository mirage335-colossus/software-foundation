#include <foundation/appended/providers.h>

static uint64_t provider_service, provider_handle;
static uint32_t invocation_count;
static uint8_t request[512], reply[512];

/* org.example.increment 1.0: four input bytes; eight response bytes.
 * The operand plus one and execution count are little-endian u32 values,
 * with unsigned arithmetic modulo 2^32. Invalid calls have no effects. */
static const uint8_t schema[32] = {
    0x3f,0xe7,0xab,0x0d,0x3f,0x8f,0x76,0x49,0x9f,0x05,0x4c,0xa6,0xf2,0x9f,0x68,0xde,
    0xee,0x28,0x62,0x76,0x81,0xf7,0x92,0x31,0xaf,0x3b,0x09,0x5b,0x06,0x35,0xb2,0x46
};

uint32_t foundation_guest_initialize(const uint8_t *context, uint32_t bytes) {
    static const uint8_t name[] = "org.example.increment";
    const foundation_guest_provider_descriptor descriptor = {
        name, sizeof(name) - 1, 1, 0, schema, 4, 8
    };
    (void)context; (void)bytes;
    uint32_t status = foundation_guest_provider_discover_service(&provider_service,
        request, sizeof(request), reply, sizeof(reply));
    if (status) return status;
    return foundation_guest_provider_register(provider_service, &descriptor, &provider_handle,
        request, sizeof(request), reply, sizeof(reply));
}

uint32_t foundation_guest_dispatch(const uint8_t *message, uint32_t bytes) {
    foundation_guest_provider_call call;
    if (!foundation_guest_provider_decode_call(message, bytes, provider_service, &call) ||
        call.provider != provider_handle) return FOUNDATION_APPENDED_APP_INVALID_INPUT;

    uint8_t result[8];
    uint32_t status = FOUNDATION_APPENDED_SERVICE_UNKNOWN_OPERATION, result_bytes = 0;
    if (call.operation == 1) {
        if (call.payload_bytes != 4) status = FOUNDATION_APPENDED_SERVICE_INVALID_REQUEST;
        else {
            ++invocation_count;
            foundation_guest_write_u32(result, foundation_guest_read_u32(call.payload) + 1u);
            foundation_guest_write_u32(result + 4, invocation_count);
            status = FOUNDATION_APPENDED_SERVICE_OK; result_bytes = sizeof(result);
        }
    }
    return foundation_guest_provider_respond(provider_service, &call, status, result, result_bytes,
        request, sizeof(request), reply, sizeof(reply));
}
