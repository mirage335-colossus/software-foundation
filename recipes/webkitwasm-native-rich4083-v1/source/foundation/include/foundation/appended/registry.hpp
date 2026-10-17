#pragma once

#include "foundation/appended/abi.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <memory>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace foundation::appended {
using Bytes = std::vector<std::uint8_t>;
using SchemaId = std::array<std::uint8_t, 32>;

enum class TransportStatus : std::uint32_t {
    ok = FOUNDATION_APPENDED_TRANSPORT_OK,
    invalid_range = FOUNDATION_APPENDED_TRANSPORT_INVALID_RANGE,
    reply_too_small = FOUNDATION_APPENDED_TRANSPORT_REPLY_TOO_SMALL,
    overlap = FOUNDATION_APPENDED_TRANSPORT_OVERLAP,
    invalid_envelope = FOUNDATION_APPENDED_TRANSPORT_INVALID_ENVELOPE,
    unsupported_envelope = FOUNDATION_APPENDED_TRANSPORT_UNSUPPORTED_ENVELOPE,
    stale_generation = FOUNDATION_APPENDED_TRANSPORT_STALE_GENERATION,
    replay = FOUNDATION_APPENDED_TRANSPORT_REPLAY,
    exhausted = FOUNDATION_APPENDED_TRANSPORT_EXHAUSTED,
    internal_error = FOUNDATION_APPENDED_TRANSPORT_INTERNAL_ERROR
};
enum class ServiceStatus : std::uint32_t {
    ok = FOUNDATION_APPENDED_SERVICE_OK,
    invalid_request = FOUNDATION_APPENDED_SERVICE_INVALID_REQUEST,
    unavailable = FOUNDATION_APPENDED_SERVICE_UNAVAILABLE,
    not_found = FOUNDATION_APPENDED_SERVICE_NOT_FOUND,
    unsupported_version = FOUNDATION_APPENDED_SERVICE_UNSUPPORTED_VERSION,
    schema_mismatch = FOUNDATION_APPENDED_SERVICE_SCHEMA_MISMATCH,
    conflict = FOUNDATION_APPENDED_SERVICE_CONFLICT,
    invalid_handle = FOUNDATION_APPENDED_SERVICE_INVALID_HANDLE,
    limit_exceeded = FOUNDATION_APPENDED_SERVICE_LIMIT_EXCEEDED,
    unknown_operation = FOUNDATION_APPENDED_SERVICE_UNKNOWN_OPERATION,
    closed = FOUNDATION_APPENDED_SERVICE_CLOSED,
    internal_error = FOUNDATION_APPENDED_SERVICE_INTERNAL_ERROR,
    result_available = FOUNDATION_APPENDED_SERVICE_RESULT_AVAILABLE,
    expired = FOUNDATION_APPENDED_SERVICE_EXPIRED,
    uncertain = FOUNDATION_APPENDED_SERVICE_UNCERTAIN
};
enum class CodecStatus {
    ok, truncated, limit_exceeded, invalid_value, unsupported_version,
    unknown_required_field
};

/* Host values only: use the codec, never memcpy this object onto the wire. */
struct Envelope {
    std::uint16_t major{1}, minor{0};
    std::uint32_t kind{FOUNDATION_APPENDED_MESSAGE_REQUEST}, flags{0};
    std::uint64_t generation{0}, sequence{0}, interface_handle{0};
    std::uint32_t operation{0}, service_status{0};
    std::uint64_t correlation{0};
};
CodecStatus encode_envelope(const Envelope&, std::span<const std::uint8_t> payload,
                            Bytes& output);
/* On failure, both output values are unchanged; payload borrows input bytes. */
CodecStatus decode_envelope(std::span<const std::uint8_t> input, Envelope& output,
                            std::span<const std::uint8_t>& payload) noexcept;

/* Field flags describe must-understand, not whether a schema requires presence.
 * Required presence belongs to the individual operation schema. */
enum class FieldType : std::uint8_t {
    u32 = FOUNDATION_APPENDED_FIELD_U32, u64 = FOUNDATION_APPENDED_FIELD_U64,
    i64 = FOUNDATION_APPENDED_FIELD_I64, f64 = FOUNDATION_APPENDED_FIELD_F64,
    boolean = FOUNDATION_APPENDED_FIELD_BOOL, utf8 = FOUNDATION_APPENDED_FIELD_UTF8,
    bytes = FOUNDATION_APPENDED_FIELD_BYTES, record = FOUNDATION_APPENDED_FIELD_RECORD,
    record_list = FOUNDATION_APPENDED_FIELD_RECORD_LIST
};
struct FieldView {
    std::uint16_t id;
    FieldType type;
    bool must_understand;
    std::span<const std::uint8_t> value;
};
/* Canonical records have strictly increasing nonzero field IDs, <=64 fields,
 * <=8 nested record levels, <=1024 records per list, and <=1 MiB encoded bytes.
 * Decoding preserves unknown optional field types; schema readers must reject
 * unknown must-understand field IDs. Output is unchanged on failure. */
CodecStatus encode_record(std::span<const FieldView>, Bytes& output);
CodecStatus decode_record(std::span<const std::uint8_t>, std::vector<FieldView>& output);
/* Validates recursively without allocating or borrowing retained output. */
CodecStatus validate_record_bytes(std::span<const std::uint8_t>) noexcept;
bool valid_utf8(std::span<const std::uint8_t>) noexcept;
bool read_u32(const FieldView&, std::uint32_t&) noexcept;
bool read_u64(const FieldView&, std::uint64_t&) noexcept;
Bytes encode_u32(std::uint32_t);
Bytes encode_u64(std::uint64_t);

struct Limits {
    std::uint32_t max_message_bytes{FOUNDATION_APPENDED_MAX_MESSAGE_BYTES};
    std::uint32_t max_services{256};
    std::uint32_t max_retained_requests{64};
    std::uint32_t max_retained_results{64};
    std::uint32_t max_retained_bytes{FOUNDATION_APPENDED_MAX_MESSAGE_BYTES};
};
struct ServiceDescriptor {
    std::string name;
    std::uint16_t major{1}, minor{0};
    SchemaId schema{};
    /* Reserve this many result bytes before calling the handler. */
    std::uint32_t max_reply_bytes{0};
};
struct DiscoveryQuery {
    std::string_view name;
    std::uint16_t major{1}, minimum_minor{0}, maximum_minor{0};
    std::optional<SchemaId> schema;
};
struct DiscoveryResult {
    ServiceStatus status{ServiceStatus::not_found};
    std::uint64_t handle{0};
    ServiceDescriptor descriptor;
};
struct ServiceReply {
    ServiceStatus status{ServiceStatus::ok};
    std::uint32_t bytes{0};
};
/* Request and response storage are borrowed only during this synchronous call.
 * Handlers write only into response, return its initialized length, and must not
 * call Registry recursively, throw after an effect, or change guest memory.
 * Exceptions/invalid replies become terminal internal errors; never retry them. */
using ServiceHandler = std::function<ServiceReply(std::uint32_t operation,
    std::span<const std::uint8_t> request, std::span<std::uint8_t> response)>;

/* Single-thread/session owner. Runtime adapters must reacquire current linear
 * memory before calling; the memory lease remains stable until call returns.
 * No Wasm runtime or native function pointer crosses the public wire boundary. */
class Registry {
public:
    explicit Registry(std::uint64_t generation, Limits limits = {});
    ~Registry();
    Registry(Registry&&) noexcept;
    Registry& operator=(Registry&&) noexcept;
    Registry(const Registry&) = delete;
    Registry& operator=(const Registry&) = delete;

    DiscoveryResult register_service(ServiceDescriptor descriptor, ServiceHandler handler);
    DiscoveryResult discover(const DiscoveryQuery&) const;
    TransportStatus call(std::span<std::uint8_t> memory,
                         std::uint32_t request_offset, std::uint32_t request_bytes,
                         std::uint32_t reply_offset, std::uint32_t reply_capacity) noexcept;
    std::uint64_t generation() const noexcept;
    const Limits& limits() const noexcept;
    std::size_t retained_result_count() const noexcept;
    void close() noexcept;
    bool closed() const noexcept;
    bool invocation_active() const noexcept;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

/* One source per scheduling domain. The last uint64_t value may be issued once;
 * the next request returns nullopt, without wrapping into a valid generation. */
class GenerationSource {
public:
    explicit GenerationSource(std::uint64_t first = 1);
    std::optional<std::uint64_t> next() noexcept;
private:
    std::uint64_t next_;
    bool exhausted_{false};
};
const SchemaId& bootstrap_schema() noexcept;
/* Encoded TLV initialization context, supplied before any guest discovery call. */
CodecStatus encode_init_context(std::uint64_t generation, const Limits&, Bytes& output);
} // namespace foundation::appended
