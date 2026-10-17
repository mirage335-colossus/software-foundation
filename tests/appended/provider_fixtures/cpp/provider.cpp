#include <foundation/appended/providers.hpp>

namespace {
namespace guest = foundation::appended::guest;
namespace providers = guest::providers;

const uint8_t name[] = "org.example.increment";
/* SHA256 of ../contract.txt, shared by the C, C++ and Rust providers. */
const uint8_t schema[32] = {
    0x3f,0xe7,0xab,0x0d,0x3f,0x8f,0x76,0x49,0x9f,0x05,0x4c,0xa6,0xf2,0x9f,0x68,0xde,
    0xee,0x28,0x62,0x76,0x81,0xf7,0x92,0x31,0xaf,0x3b,0x09,0x5b,0x06,0x35,0xb2,0x46
};
uint64_t service, provider;
uint32_t invocation_count;
uint8_t request_buffer[512], reply_buffer[512];
const guest::MutableBytes request = {request_buffer, sizeof(request_buffer)};
const guest::MutableBytes reply = {reply_buffer, sizeof(reply_buffer)};
}

extern "C" uint32_t foundation_guest_initialize(const uint8_t *, uint32_t) {
    uint32_t status = providers::discover_service(service, request, reply);
    if (status != FOUNDATION_APPENDED_APP_OK) return status;
    const providers::Descriptor descriptor = {
        name, sizeof(name) - 1, 1, 0, schema, 4, 8
    };
    status = providers::register_provider(service, descriptor, provider, request, reply);
    if (status != FOUNDATION_APPENDED_APP_OK) return status;
    const providers::Query query = {name, sizeof(name) - 1, 1, 0, 0, schema};
    providers::Discovery discovered = {};
    status = providers::discover(service, query, discovered, request, reply);
    if (status != FOUNDATION_APPENDED_APP_OK) return status;
    if (discovered.provider != provider || discovered.major != 1 || discovered.minor != 0 ||
        discovered.maximum_request_bytes != 4 || discovered.maximum_reply_bytes != 8)
        return FOUNDATION_APPENDED_APP_FAILED;
    return FOUNDATION_APPENDED_APP_OK;
}

extern "C" uint32_t foundation_guest_dispatch(const uint8_t *message, uint32_t bytes) {
    providers::Invocation invocation = {};
    if (!providers::decode_call({message, bytes}, service, invocation) ||
        invocation.provider != provider) return FOUNDATION_APPENDED_APP_INVALID_INPUT;
    if (invocation.operation != 1) {
        return providers::respond(service, invocation, FOUNDATION_APPENDED_SERVICE_UNKNOWN_OPERATION,
                                  {nullptr, 0}, request, reply);
    }
    if (invocation.payload_bytes != 4) {
        return providers::respond(service, invocation, FOUNDATION_APPENDED_SERVICE_INVALID_REQUEST,
                                  {nullptr, 0}, request, reply);
    }
    uint8_t result[8];
    foundation_guest_write_u32(result, foundation_guest_read_u32(invocation.payload) + 1u);
    foundation_guest_write_u32(result + 4, ++invocation_count);
    return providers::respond(service, invocation, FOUNDATION_APPENDED_SERVICE_OK,
                              {result, sizeof(result)}, request, reply);
}

extern "C" uint32_t foundation_guest_step(uint32_t) { return FOUNDATION_APPENDED_STEP_IDLE; }
extern "C" void foundation_guest_shutdown(uint32_t) {}
