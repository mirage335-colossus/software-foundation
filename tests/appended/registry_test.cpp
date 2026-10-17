#include "foundation/appended/registry.hpp"

#include <algorithm>
#include <array>
#include <iostream>
#include <limits>
#include <stdexcept>

using namespace foundation::appended;
namespace {
void require(bool ok, const char* message) { if (!ok) throw std::runtime_error(message); }
struct OwnedField { std::uint16_t id; FieldType type; Bytes bytes; };
Bytes record(std::initializer_list<OwnedField> fields) {
    std::vector<FieldView> views;
    for (const auto& f : fields) views.push_back({f.id, f.type, true, f.bytes});
    Bytes out; require(encode_record(views, out) == CodecStatus::ok, "fixture record"); return out;
}
SchemaId schema(unsigned n) { SchemaId result{}; result[0] = static_cast<std::uint8_t>(n); return result; }
struct Exchange {
    TransportStatus transport{TransportStatus::internal_error};
    Envelope header;
    Bytes payload;
};
struct Fixture {
    Registry registry;
    Bytes memory = Bytes(8192, 0xcc);
    explicit Fixture(Limits bounds = {}) : registry(7, bounds) {}
    Bytes request(std::uint64_t sequence, std::uint64_t handle, std::uint32_t operation, const Bytes& payload = {}) {
        Envelope header; header.generation = 7; header.sequence = sequence;
        header.interface_handle = handle; header.operation = operation;
        Bytes output; require(encode_envelope(header, payload, output) == CodecStatus::ok, "fixture envelope"); return output;
    }
    Exchange exchange(std::uint64_t sequence, std::uint64_t handle, std::uint32_t operation,
                      const Bytes& payload = {}, std::uint32_t capacity = 1024) {
        const auto req = request(sequence, handle, operation, payload);
        std::fill(memory.begin(), memory.end(), 0xcc);
        std::copy(req.begin(), req.end(), memory.begin());
        Exchange output;
        output.transport = registry.call(memory, 0, static_cast<std::uint32_t>(req.size()), 4096, capacity);
        if (output.transport != TransportStatus::ok) return output;
        const std::uint32_t size = memory[4096] | (static_cast<std::uint32_t>(memory[4097]) << 8) |
            (static_cast<std::uint32_t>(memory[4098]) << 16) | (static_cast<std::uint32_t>(memory[4099]) << 24);
        require(size <= capacity, "reply exceeded capacity");
        std::span<const std::uint8_t> data;
        require(decode_envelope(std::span<const std::uint8_t>(memory).subspan(4096, size), output.header, data) == CodecStatus::ok,
            "registry emitted invalid reply");
        output.payload.assign(data.begin(), data.end()); return output;
    }
};
ServiceStatus status(const Exchange& value) { require(value.transport == TransportStatus::ok, "unexpected transport failure"); return static_cast<ServiceStatus>(value.header.service_status); }
}
int main() {
    try {
        Fixture fixture;
        unsigned effects = 0;
        const auto handler = [&](std::uint32_t operation, std::span<const std::uint8_t>, std::span<std::uint8_t> response) {
            if (operation != 1) return ServiceReply{ServiceStatus::unknown_operation, 0};
            ++effects;
            for (std::size_t i = 0; i < 96; ++i) response[i] = static_cast<std::uint8_t>(i);
            return ServiceReply{ServiceStatus::ok, 96};
        };
        const auto first = fixture.registry.register_service({"org.example.counter", 1, 0, schema(1), 96}, handler);
        require(first.status == ServiceStatus::ok && first.handle != 0, "registration failed");
        require(fixture.registry.register_service({"org.example.counter", 1, 0, schema(2), 96}, handler).status == ServiceStatus::conflict,
            "conflicting schema/provider accepted");
        const auto newer = fixture.registry.register_service({"org.example.counter", 1, 2, schema(2), 96}, handler);
        require(newer.status == ServiceStatus::ok, "explicit newer contract rejected");
        auto discovery = fixture.registry.discover({"org.example.counter", 1, 0, 2, {}});
        require(discovery.status == ServiceStatus::ok && discovery.handle == newer.handle, "highest minor negotiation");
        discovery = fixture.registry.discover({"org.example.counter", 1, 0, 2, schema(1)});
        require(discovery.status == ServiceStatus::ok && discovery.handle == first.handle, "old schema rejected by new provider");
        require(fixture.registry.discover({"org.example.counter", 1, 0, 2, schema(3)}).status == ServiceStatus::schema_mismatch,
            "schema mismatch not distinguished");
        require(fixture.registry.discover({"org.example.counter", 2, 0, 0, {}}).status == ServiceStatus::unsupported_version,
            "wrong major not distinguished");
        require(fixture.registry.discover({"org.example.missing", 1, 0, 0, {}}).status == ServiceStatus::not_found, "missing service");
        require(fixture.registry.register_service({"bad", 1, 0, schema(1), 96}, handler).status == ServiceStatus::invalid_request,
            "unnamespaced service accepted");
        require(fixture.registry.register_service({"foundation.kernel.private", 1, 0, schema(1), 96}, handler).status == ServiceStatus::invalid_request,
            "reserved kernel namespace accepted");
        const auto req = fixture.request(1, first.handle, 1);
        std::copy(req.begin(), req.end(), fixture.memory.begin());
        const auto unchanged = fixture.memory;
        for (unsigned capacity = 0; capacity < 64; ++capacity)
            require(fixture.registry.call(fixture.memory, 0, 64, 4096, capacity) == TransportStatus::reply_too_small &&
                fixture.memory == unchanged && effects == 0, "short reply buffer caused effects/writes");
        require(fixture.registry.call(fixture.memory, UINT32_MAX, 64, 4096, 64) == TransportStatus::invalid_range,
            "overflowed request range accepted");
        require(fixture.registry.call(fixture.memory, 0, 64, UINT32_MAX, 64) == TransportStatus::invalid_range,
            "overflowed reply range accepted");
        require(fixture.registry.call(fixture.memory, 0, 64, 32, 64) == TransportStatus::overlap && effects == 0,
            "overlap caused effects");
        fixture.memory[16] = 8;
        require(fixture.registry.call(fixture.memory, 0, 64, 4096, 64) == TransportStatus::stale_generation && effects == 0,
            "stale generation accepted");
        const auto large = fixture.exchange(1, first.handle, 1, {}, 64);
        require(status(large) == ServiceStatus::result_available && large.header.correlation != 0 && effects == 1,
            "header-only output repeated/lost effect");
        const auto result_handle = large.header.correlation;
        auto replay = fixture.exchange(1, first.handle, 1);
        require(status(replay) == ServiceStatus::ok && replay.payload.size() == 96 && replay.payload[95] == 95 && effects == 1,
            "identical retry ran provider");
        require(fixture.exchange(1, first.handle, 1, Bytes{1}).transport == TransportStatus::replay && effects == 1,
            "different bytes reused sequence");
        auto read = record({{1, FieldType::u64, encode_u64(result_handle)}, {2, FieldType::u32, encode_u32(90)}, {3, FieldType::u32, encode_u32(6)}});
        auto range = fixture.exchange(2, 0, FOUNDATION_APPENDED_CONTROL_RESULT_READ, read, 70);
        require(status(range) == ServiceStatus::ok && range.payload == Bytes({90,91,92,93,94,95}), "retained result read");
        require(status(fixture.exchange(2, 0, FOUNDATION_APPENDED_CONTROL_RESULT_READ, read, 64)) == ServiceStatus::invalid_request,
            "result-read replay nested a handle");
        auto release = record({{1, FieldType::u64, encode_u64(result_handle)}});
        require(status(fixture.exchange(3, 0, FOUNDATION_APPENDED_CONTROL_RESULT_RELEASE, release)) == ServiceStatus::ok,
            "result release failed");
        require(status(fixture.exchange(1, first.handle, 1)) == ServiceStatus::expired && effects == 1, "released result replay resurrected");
        require(status(fixture.exchange(4, 0, FOUNDATION_APPENDED_CONTROL_RESULT_READ, read)) == ServiceStatus::invalid_handle,
            "released result remained readable");
        auto ack = record({{1, FieldType::u64, encode_u64(4)}});
        require(status(fixture.exchange(5, 0, FOUNDATION_APPENDED_CONTROL_ACKNOWLEDGE, ack)) == ServiceStatus::ok,
            "acknowledgement failed");
        require(status(fixture.exchange(1, first.handle, 1)) == ServiceStatus::expired && effects == 1, "retired request ran again");
        ack = record({{1, FieldType::u64, encode_u64(99)}});
        require(status(fixture.exchange(6, 0, FOUNDATION_APPENDED_CONTROL_ACKNOWLEDGE, ack)) == ServiceStatus::invalid_request,
            "acknowledgement crossed unadmitted range");
        const Bytes name{'o','r','g','.','e','x','a','m','p','l','e','.','c','o','u','n','t','e','r'};
        const auto expected_schema = schema(1);
        auto query = record({{1, FieldType::utf8, name}, {2, FieldType::u32, encode_u32(1)},
            {3, FieldType::u32, encode_u32(0)}, {4, FieldType::u32, encode_u32(0)},
            {5, FieldType::bytes, Bytes(expected_schema.begin(), expected_schema.end())}});
        const auto found = fixture.exchange(7, 0, FOUNDATION_APPENDED_CONTROL_DISCOVER, query);
        std::vector<FieldView> fields;
        require(status(found) == ServiceStatus::ok && decode_record(found.payload, fields) == CodecStatus::ok, "wire discovery failed");
        std::uint64_t handle = 0;
        require(read_u64(fields[0], handle) && handle == first.handle, "wire discovery selected wrong handle");
        auto bad_query = query; bad_query[3] = 2;
        require(status(fixture.exchange(8, 0, FOUNDATION_APPENDED_CONTROL_DISCOVER, bad_query)) == ServiceStatus::invalid_request,
            "malformed discovery accepted");
        bad_query = query; bad_query[3] = 0;
        require(status(fixture.exchange(9, 0, FOUNDATION_APPENDED_CONTROL_DISCOVER, bad_query)) == ServiceStatus::invalid_request,
            "defined discovery field omitted must-understand bit");
        require(status(fixture.exchange(10, first.handle, 99)) == ServiceStatus::unknown_operation && effects == 1,
            "unknown operation reached mutation");
        require(status(fixture.exchange(11, result_handle, 1)) == ServiceStatus::invalid_handle, "result handle used as interface");

        Limits tight; tight.max_retained_requests = 2; tight.max_retained_results = 1; tight.max_retained_bytes = 96;
        Fixture bounded(tight);
        unsigned bounded_effects = 0;
        const auto bounded_service = bounded.registry.register_service({"org.example.bound",1,0,schema(1),96},
            [&](std::uint32_t, std::span<const std::uint8_t>, std::span<std::uint8_t> response) {
                ++bounded_effects; std::fill(response.begin(), response.end(), 42); return ServiceReply{ServiceStatus::ok, 96};
            });
        const auto retained = bounded.exchange(1, bounded_service.handle, 1, {}, 64);
        require(status(retained) == ServiceStatus::result_available && bounded_effects == 1, "bounded first call");
        require(status(bounded.exchange(2, bounded_service.handle, 1, {}, 64)) == ServiceStatus::limit_exceeded && bounded_effects == 1,
            "retention overflow ran mutation");
        require(status(bounded.exchange(1, bounded_service.handle, 1, {}, 64)) == ServiceStatus::result_available && bounded_effects == 1,
            "full retention broke live retry");
        ack = record({{1, FieldType::u64, encode_u64(1)}});
        require(status(bounded.exchange(3, 0, FOUNDATION_APPENDED_CONTROL_ACKNOWLEDGE, ack)) == ServiceStatus::ok,
            "ack under result pressure failed");
        read = record({{1, FieldType::u64, encode_u64(retained.header.correlation)}, {2, FieldType::u32, encode_u32(0)}, {3, FieldType::u32, encode_u32(96)}});
        require(status(bounded.exchange(4, 0, FOUNDATION_APPENDED_CONTROL_RESULT_READ, read, 160)) == ServiceStatus::ok,
            "result not readable with full byte reservation");
        ack = record({{1, FieldType::u64, encode_u64(4)}});
        require(status(bounded.exchange(5, 0, FOUNDATION_APPENDED_CONTROL_ACKNOWLEDGE, ack)) == ServiceStatus::ok,
            "full ledger could not acknowledge");
        release = record({{1, FieldType::u64, encode_u64(retained.header.correlation)}});
        require(status(bounded.exchange(6, 0, FOUNDATION_APPENDED_CONTROL_RESULT_RELEASE, release)) == ServiceStatus::ok,
            "bounded release failed");
        ack = record({{1, FieldType::u64, encode_u64(6)}});
        require(status(bounded.exchange(7, 0, FOUNDATION_APPENDED_CONTROL_ACKNOWLEDGE, ack)) == ServiceStatus::ok,
            "bounded release acknowledgement failed");
        require(status(bounded.exchange(8, bounded_service.handle, 1, {}, 64)) == ServiceStatus::result_available && bounded_effects == 2,
            "released reservation not recovered");

        Fixture exceptions;
        const auto throws = exceptions.registry.register_service({"org.example.throws", 1, 0, schema(1), 0},
            [&](auto, auto, auto) -> ServiceReply { ++effects; throw std::runtime_error("external ambiguity"); });
        const auto before = effects;
        require(status(exceptions.exchange(1, throws.handle, 1)) == ServiceStatus::uncertain &&
            status(exceptions.exchange(1, throws.handle, 1)) == ServiceStatus::uncertain && effects == before + 1,
            "uncertain external effect was retried");
        Fixture sequence_end;
        const auto terminal = sequence_end.registry.register_service({"org.example.end", 1, 0, schema(1), 0},
            [](auto, auto, auto) { return ServiceReply{}; });
        require(status(sequence_end.exchange(UINT64_MAX, terminal.handle, 1)) == ServiceStatus::ok &&
            status(sequence_end.exchange(UINT64_MAX, terminal.handle, 1)) == ServiceStatus::ok &&
            status(sequence_end.exchange(UINT64_MAX - 1, terminal.handle, 1)) == ServiceStatus::expired,
            "sequence exhaustion wrapped or lost retry");
        fixture.registry.close();
        require(status(fixture.exchange(12, first.handle, 1)) == ServiceStatus::closed && fixture.registry.retained_result_count() == 0,
            "close retained callable state");
        std::cout << "appended registry contract passed\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
