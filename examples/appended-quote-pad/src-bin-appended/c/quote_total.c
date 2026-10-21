#include <foundation/appended/providers.h>

/* Ordinary payload iteration changes only this checked adjustment: 1 -> 2. */
#define QUOTE_ADJUSTMENT 1u
static uint64_t provider_service, provider_handle;
static uint32_t invocation_count;
static uint8_t request[512], reply[512];
static const uint8_t schema[32] = {
    0xba,0xa7,0xae,0x88,0xe0,0x6a,0x98,0x59,
    0x99,0x0d,0x80,0xf9,0x9f,0x23,0x86,0xe0,
    0x19,0xde,0x22,0x3c,0x9b,0xb8,0xe5,0xa8,
    0x9f,0x4d,0x8f,0xd0,0xab,0x45,0x65,0x3f
};

uint32_t foundation_guest_initialize(const uint8_t *context, uint32_t bytes) {
    static const uint8_t name[] = "org.example.quote.total";
    const foundation_guest_provider_descriptor descriptor = {
        name, sizeof(name) - 1, 1, 0, schema, 8, 12
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

    uint8_t result[12];
    uint32_t status = FOUNDATION_APPENDED_SERVICE_UNKNOWN_OPERATION, result_bytes = 0;
    if (call.operation == 1) {
        if (call.payload_bytes != 8) status = FOUNDATION_APPENDED_SERVICE_INVALID_REQUEST;
        else {
            const uint32_t left = foundation_guest_read_u32(call.payload);
            const uint32_t right = foundation_guest_read_u32(call.payload + 4);
            uint32_t total = 0;
            uint32_t overflow = left > UINT32_MAX - right;
            if (!overflow) {
                total = left + right;
                overflow = total > UINT32_MAX - QUOTE_ADJUSTMENT;
                if (!overflow) total += QUOTE_ADJUSTMENT;
            }
            if (overflow) total = 0;
            ++invocation_count;
            foundation_guest_write_u32(result, total);
            foundation_guest_write_u32(result + 4, overflow);
            foundation_guest_write_u32(result + 8, invocation_count);
            status = FOUNDATION_APPENDED_SERVICE_OK; result_bytes = sizeof(result);
        }
    }
    return foundation_guest_provider_respond(provider_service, &call, status, result, result_bytes,
        request, sizeof(request), reply, sizeof(reply));
}
