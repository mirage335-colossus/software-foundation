#pragma once
#include <foundation/appended/guest.hpp>
#include <foundation/appended/providers.h>

namespace foundation { namespace appended { namespace guest { namespace providers {
using Bytes = ::foundation::appended::guest::Bytes;
using MutableBytes = ::foundation::appended::guest::MutableBytes;
using Descriptor = foundation_guest_provider_descriptor;
using Query = foundation_guest_provider_query;
using Discovery = foundation_guest_provider_discovery;
using Invocation = foundation_guest_provider_call;

inline uint32_t discover_service(uint64_t& service, MutableBytes request, MutableBytes reply) {
    return foundation_guest_provider_discover_service(
        &service, request.data, request.size, reply.data, reply.size);
}

inline uint32_t register_provider(uint64_t service, const Descriptor& descriptor,
                                  uint64_t& provider, MutableBytes request, MutableBytes reply) {
    return foundation_guest_provider_register(
        service, &descriptor, &provider, request.data, request.size, reply.data, reply.size);
}

inline uint32_t discover(uint64_t service, const Query& query, Discovery& discovery,
                         MutableBytes request, MutableBytes reply) {
    return foundation_guest_provider_discover(
        service, &query, &discovery, request.data, request.size, reply.data, reply.size);
}

inline bool decode_call(Bytes message, uint64_t service, Invocation& invocation) {
    return foundation_guest_provider_decode_call(
        message.data, message.size, service, &invocation) != 0;
}

inline uint32_t respond(uint64_t service, const Invocation& invocation, uint32_t status,
                        Bytes payload, MutableBytes request, MutableBytes reply) {
    return foundation_guest_provider_respond(
        service, &invocation, status, payload.data, payload.size,
        request.data, request.size, reply.data, reply.size);
}
}}}}
