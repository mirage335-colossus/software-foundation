#include <foundation/appended/providers.hpp>

namespace {
namespace guest = foundation::appended::guest;
namespace providers = guest::providers;

constexpr uint32_t QUOTE_ADJUSTMENT = 1u;
const uint8_t name[] = "org.example.quote.total";
const uint8_t schema[32] = {
    0xba,0xa7,0xae,0x88,0xe0,0x6a,0x98,0x59,
    0x99,0x0d,0x80,0xf9,0x9f,0x23,0x86,0xe0,
    0x19,0xde,0x22,0x3c,0x9b,0xb8,0xe5,0xa8,
    0x9f,0x4d,0x8f,0xd0,0xab,0x45,0x65,0x3f
};
uint64_t service, provider;
uint32_t invocation_count;
uint8_t request_buffer[512], reply_buffer[512];
const providers::MutableBytes request = {request_buffer, sizeof(request_buffer)};
const providers::MutableBytes reply = {reply_buffer, sizeof(reply_buffer)};

}

extern "C" uint32_t foundation_guest_initialize(const uint8_t *, uint32_t) {
    uint32_t status = providers::discover_service(service, request, reply);
    if (status != FOUNDATION_APPENDED_APP_OK) return status;

    const providers::Descriptor descriptor = {
        name, sizeof(name) - 1, 1, 0, schema, 8, 12
    };
    status = providers::register_provider(service, descriptor, provider, request, reply);
    if (status != FOUNDATION_APPENDED_APP_OK) return status;
    return FOUNDATION_APPENDED_APP_OK;
}

extern "C" uint32_t foundation_guest_dispatch(const uint8_t *message, uint32_t bytes) {
    providers::Invocation call = {};
    if (!providers::decode_call({message, bytes}, service, call) || call.provider != provider) {
        return FOUNDATION_APPENDED_APP_INVALID_INPUT;
    }

    uint32_t status = FOUNDATION_APPENDED_SERVICE_UNKNOWN_OPERATION;
    uint8_t result[12] = {};
    uint32_t result_bytes = 0;
    if (call.operation == 1) {
        status = FOUNDATION_APPENDED_SERVICE_INVALID_REQUEST;
        if (call.payload_bytes == 8) {
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
            status = FOUNDATION_APPENDED_SERVICE_OK;
            result_bytes = sizeof(result);
        }
    }

    return providers::respond(service, call, status, {result, result_bytes}, request, reply);
}

extern "C" uint32_t foundation_guest_step(uint32_t) {
    return FOUNDATION_APPENDED_STEP_IDLE;
}

extern "C" void foundation_guest_shutdown(uint32_t) {}
