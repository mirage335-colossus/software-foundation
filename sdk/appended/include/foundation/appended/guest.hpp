#pragma once
#include <foundation/appended/guest.h>

namespace foundation { namespace appended { namespace guest {
struct Bytes { const uint8_t *data; uint32_t size; };
struct MutableBytes { uint8_t *data; uint32_t size; };
using Envelope = foundation_guest_envelope;
using Context = foundation_guest_init_context;
inline bool decode(Bytes bytes, Envelope& value) {
    return foundation_guest_decode_envelope(bytes.data, bytes.size, &value) != 0;
}
inline bool encode(MutableBytes bytes, const Envelope& value, uint32_t payload_bytes) {
    return foundation_guest_encode_envelope(bytes.data, bytes.size, &value, payload_bytes) != 0;
}
inline uint32_t call(Bytes request, MutableBytes reply) {
    return foundation_guest_call(request.data, request.size, reply.data, reply.size);
}
inline const Context *context() { return foundation_guest_context(); }
inline uint64_t next_sequence() { return foundation_guest_next_sequence(); }
/* Move-only storage uses the same pre-initialization allocator as the host. */
class Buffer {
    uint32_t offset_, bytes_;
public:
    explicit Buffer(uint32_t bytes) : offset_(foundation_app_alloc_v1(bytes)), bytes_(bytes) {}
    ~Buffer() { if (offset_) foundation_app_free_v1(offset_, bytes_); }
    Buffer(const Buffer&) = delete;
    Buffer& operator=(const Buffer&) = delete;
    Buffer(Buffer&& other) : offset_(other.offset_), bytes_(other.bytes_) { other.offset_ = 0; }
    uint8_t *data() { return reinterpret_cast<uint8_t *>(static_cast<uintptr_t>(offset_)); }
    uint32_t size() const { return offset_ ? bytes_ : 0; }
    explicit operator bool() const { return offset_ != 0; }
};
}}}
