#include "../gui/shared/appended_engine_abi.h"
#include "../gui/shared/appended_engine_owner.hpp"

#include <algorithm>
#include <array>
#include <functional>
#include <initializer_list>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

using namespace foundation::appended;

namespace {
constexpr std::uint64_t worker_epoch = 17, application_instance = 23, module_generation = 31;
constexpr std::size_t header_bytes = 72, receipt_bytes = 80;
constexpr std::string_view native_name = "org.example.engine.counter";
constexpr std::string_view module_name = "org.example.engine.provider";
constexpr SchemaId native_schema{1, 7, 3};

static_assert(FOUNDATION_ENGINE_HEADER_BYTES == header_bytes);
static_assert(FOUNDATION_ENGINE_RECEIPT_BYTES == receipt_bytes);
static_assert(FOUNDATION_ENGINE_BRIDGE_VERSION == UINT32_C(0x00010000));

void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

void put(Bytes& bytes, std::size_t offset, std::uint64_t value, std::size_t count) {
    require(offset <= bytes.size() && count <= bytes.size() - offset, "fixture integer write range");
    for (std::size_t i = 0; i != count; ++i)
        bytes[offset + i] = static_cast<std::uint8_t>(value >> (8 * i));
}

std::uint64_t get(std::span<const std::uint8_t> bytes, std::size_t offset, std::size_t count) {
    require(count <= 8 && offset <= bytes.size() && count <= bytes.size() - offset,
        "fixture integer read range");
    std::uint64_t value = 0;
    for (std::size_t i = 0; i != count; ++i) value |= std::uint64_t(bytes[offset + i]) << (8 * i);
    return value;
}

Bytes scalar(std::uint64_t value, std::size_t count) {
    Bytes result(count);
    put(result, 0, value, count);
    return result;
}

Bytes bridge_record(std::uint32_t operation, EngineIdentity identity, const Bytes& payload = {},
                    std::uint64_t transfer = 0, std::uint32_t source = 0) {
    Bytes result(header_bytes + payload.size(), 0);
    result[0] = 'F'; result[1] = 'K'; result[2] = 'B'; result[3] = '1';
    put(result, 4, FOUNDATION_ENGINE_RECORD_VERSION, 2);
    put(result, 6, operation, 2);
    put(result, 8, result.size(), 4);
    put(result, 16, identity.worker_epoch, 8);
    put(result, 24, identity.application_instance, 8);
    put(result, 32, identity.document_sequence, 8);
    put(result, 40, identity.service_generation, 8);
    put(result, 48, transfer, 8);
    put(result, 56, source, 4);
    put(result, 64, payload.size(), 4);
    std::copy(payload.begin(), payload.end(), result.begin() + header_bytes);
    return result;
}

struct Reply {
    std::int32_t transport = 0;
    Bytes bytes;
    std::uint32_t control = FOUNDATION_ENGINE_INTERNAL;
    ServiceStatus service = ServiceStatus::internal_error;
    EngineIdentity identity;
    std::uint64_t transfer = 0;

    bool ok() const {
        return transport >= static_cast<std::int32_t>(receipt_bytes) &&
            control == FOUNDATION_ENGINE_OK && service == ServiceStatus::ok;
    }
    Bytes data() const {
        require(bytes.size() >= receipt_bytes, "missing receipt payload");
        return Bytes(bytes.begin() + receipt_bytes, bytes.end());
    }
};

Reply dispatch(EngineOwner& owner, std::uint32_t operation, const Bytes& input,
               std::size_t capacity = FOUNDATION_ENGINE_MAX_BODY_BYTES + receipt_bytes) {
    Bytes output(capacity, 0xa5);
    Reply result;
    result.transport = owner.dispatch(operation, input, output);
    if (result.transport < 0) return result;
    require(static_cast<std::size_t>(result.transport) <= output.size(), "reply exceeds caller capacity");
    output.resize(static_cast<std::size_t>(result.transport));
    require(output.size() >= receipt_bytes && output[0] == 'F' && output[1] == 'K' &&
        output[2] == 'B' && output[3] == '1', "reply lacks the exact private header");
    require(get(output, 4, 2) == FOUNDATION_ENGINE_RECORD_VERSION &&
        get(output, 6, 2) == (operation | FOUNDATION_ENGINE_REPLY_KIND) &&
        get(output, 8, 4) == output.size() && get(output, 12, 4) == 0 &&
        get(output, 60, 4) == 0 && get(output, 64, 4) == output.size() - header_bytes &&
        get(output, 68, 4) == 0, "reply is not an exact canonical bridge record");
    result.identity = {get(output, 16, 8), get(output, 24, 8), get(output, 32, 8), get(output, 40, 8)};
    result.transfer = get(output, 48, 8);
    result.control = static_cast<std::uint32_t>(get(output, 72, 4));
    result.service = static_cast<ServiceStatus>(get(output, 76, 4));
    require(result.control <= FOUNDATION_ENGINE_INTERNAL &&
        static_cast<std::uint32_t>(result.service) <= FOUNDATION_APPENDED_SERVICE_UNCERTAIN,
        "reply mixes transport, control and service status domains");
    result.bytes = std::move(output);
    return result;
}

Package trusted_package() {
    // The owner API takes the common reader's already verified Package. The
    // fixture exercises owner behavior, not package hashing or container parsing.
    Package package;
    package.application = {"org.example.engine-owner", "Engine owner fixture", "0.1.0"};
    package.web.present = true;
    package.web.entry = "web/index.html";
    package.capabilities = {"foundation.startup.v1"};
    package.payload_id = package.package_sha256 = package.kernel_sha256 = std::string(64, '1');
    const std::string startup =
        "{\"kind\":\"foundation-appended-startup\",\"primary\":\"web\",\"schema_version\":1}";
    const std::string html = "<!doctype html><title>Owner fixture</title>";
    package.files.push_back({"web/.foundation/startup-v1.json", "web", "application/json",
        std::string(64, '2'), Bytes(startup.begin(), startup.end())});
    package.files.push_back({"web/index.html", "web", "text/html", std::string(64, '3'),
        Bytes(html.begin(), html.end())});
    return package;
}

struct OwnedField { std::uint16_t id; FieldType type; Bytes bytes; };

Bytes service_record(std::initializer_list<OwnedField> fields) {
    std::vector<FieldView> views;
    for (const auto& field : fields) views.push_back({field.id, field.type, true, field.bytes});
    Bytes result;
    require(encode_record(views, result) == CodecStatus::ok, "fixture service record encoding");
    return result;
}

Bytes discovery(std::string_view name = native_name, std::uint32_t maximum_minor = 0) {
    return service_record({{1, FieldType::utf8, Bytes(name.begin(), name.end())},
        {2, FieldType::u32, encode_u32(1)}, {3, FieldType::u32, encode_u32(0)},
        {4, FieldType::u32, encode_u32(maximum_minor)},
        {5, FieldType::bytes, Bytes(native_schema.begin(), native_schema.end())}});
}

Bytes service_request(EngineIdentity identity, std::uint64_t sequence, std::uint64_t handle,
                      std::uint32_t operation, const Bytes& payload) {
    Envelope header;
    header.generation = identity.service_generation;
    header.sequence = sequence;
    header.interface_handle = handle;
    header.operation = operation;
    Bytes result;
    require(encode_envelope(header, payload, result) == CodecStatus::ok, "fixture service envelope encoding");
    return result;
}

struct Completion { Envelope header; Bytes payload; };

Completion completion(const Reply& reply) {
    require(reply.ok() && reply.transfer != 0, "missing retained delivery");
    const auto bytes = reply.data();
    Completion result;
    std::span<const std::uint8_t> payload;
    require(decode_envelope(bytes, result.header, payload) == CodecStatus::ok &&
        result.header.kind == FOUNDATION_APPENDED_MESSAGE_COMPLETION && result.header.correlation == 0,
        "delivery did not retain a canonical service completion");
    result.payload.assign(payload.begin(), payload.end());
    return result;
}

// Assemble the same foundation-guest-v1 provider shape used by the actual
// WebServices interpreter tests. No guest compiler or runtime stub is involved.
void append(Bytes& to, const Bytes& from) { to.insert(to.end(), from.begin(), from.end()); }
void uleb(Bytes& bytes, std::uint32_t value) {
    do {
        const auto next = static_cast<std::uint8_t>(value & 127u);
        value >>= 7;
        bytes.push_back(static_cast<std::uint8_t>(next | (value ? 128u : 0u)));
    } while (value);
}
void constant(Bytes& bytes, std::int32_t value) {
    bytes.push_back(0x41);
    bool more;
    do {
        const auto next = static_cast<std::uint8_t>(value & 127);
        value >>= 7;
        more = !((value == 0 && !(next & 64)) || (value == -1 && (next & 64)));
        bytes.push_back(static_cast<std::uint8_t>(next | (more ? 128u : 0u)));
    } while (more);
}
void wasm_name(Bytes& bytes, std::string_view value) {
    uleb(bytes, static_cast<std::uint32_t>(value.size()));
    bytes.insert(bytes.end(), value.begin(), value.end());
}
void section(Bytes& bytes, std::uint8_t id, const Bytes& content) {
    bytes.push_back(id);
    uleb(bytes, static_cast<std::uint32_t>(content.size()));
    append(bytes, content);
}
void load32(Bytes& code, std::uint32_t address) {
    constant(code, static_cast<std::int32_t>(address));
    append(code, {0x28, 2, 0});
}
void copy64(Bytes& code, std::uint32_t destination, std::uint32_t source) {
    constant(code, static_cast<std::int32_t>(destination));
    constant(code, static_cast<std::int32_t>(source));
    append(code, {0x29, 3, 0, 0x37, 3, 0});
}
void event64(Bytes& code, std::uint32_t destination, std::uint32_t offset) {
    constant(code, static_cast<std::int32_t>(destination));
    append(code, {0x20, 0, 0x29, 3});
    uleb(code, offset);
    append(code, {0x37, 3, 0});
}
void trap_if(Bytes& code) { append(code, {0x04, 0x40, 0x00, 0x0b}); }
constexpr std::uint32_t sequence_address = 128, count_address = 136, control_address = 144;
constexpr std::uint32_t response_address = 2048, native_address = 2304, ack_address = 2560, reply_address = 8192;
void gateway(Bytes& code, std::uint32_t packet, std::size_t bytes) {
    constant(code, sequence_address); constant(code, sequence_address);
    append(code, {0x29, 3, 0, 0x42, 1, 0x7c, 0x37, 3, 0});
    copy64(code, packet + FOUNDATION_APPENDED_OFFSET_SEQUENCE, sequence_address);
    constant(code, static_cast<std::int32_t>(packet)); constant(code, static_cast<std::int32_t>(bytes));
    constant(code, reply_address); constant(code, 512); append(code, {0x10, 0}); trap_if(code);
    load32(code, reply_address + FOUNDATION_APPENDED_OFFSET_STATUS); trap_if(code);
}
void acknowledge_gateway(Bytes& code, std::size_t bytes) {
    copy64(code, ack_address + 72, sequence_address);
    gateway(code, ack_address, bytes);
}
Bytes provider_fixture(std::uint64_t native_handle, bool trap_after_response = false) {
    const EngineIdentity guest{0, 0, 0, module_generation};
    // Provider bootstrap discovery omits the application's exact schema filter.
    const auto query = service_record({
        {1, FieldType::utf8, Bytes(FOUNDATION_PROVIDER_SERVICE_NAME,
            FOUNDATION_PROVIDER_SERVICE_NAME + std::char_traits<char>::length(FOUNDATION_PROVIDER_SERVICE_NAME))},
        {2, FieldType::u32, encode_u32(1)}, {3, FieldType::u32, encode_u32(0)},
        {4, FieldType::u32, encode_u32(0)}});
    const auto discover = service_request(guest, 1, 0, FOUNDATION_APPENDED_CONTROL_DISCOVER, query);
    const auto registration = service_record({{1, FieldType::utf8, Bytes(module_name.begin(), module_name.end())},
        {2, FieldType::u32, encode_u32(1)}, {3, FieldType::u32, encode_u32(2)},
        {4, FieldType::bytes, Bytes(native_schema.begin(), native_schema.end())},
        {5, FieldType::u32, encode_u32(4)}, {6, FieldType::u32, encode_u32(8)}});
    const auto register_packet = service_request(guest, 1, 1, FOUNDATION_PROVIDER_REGISTER, registration);
    const auto response = service_request(guest, 1, 1, FOUNDATION_PROVIDER_RESPOND, service_record({
        {1, FieldType::u64, encode_u64(1)}, {2, FieldType::u64, encode_u64(1)},
        {3, FieldType::u32, encode_u32(0)}, {4, FieldType::bytes, Bytes(8)}}));
    const auto native = service_request(guest, 1, native_handle, 1, encode_u32(0));
    const auto ack = service_request(guest, 1, 0, FOUNDATION_APPENDED_CONTROL_ACKNOWLEDGE,
        service_record({{1, FieldType::u64, encode_u64(1)}}));
    const std::array<std::pair<std::uint32_t, Bytes>, 5> data{{{256, discover}, {512, register_packet},
        {response_address, response}, {native_address, native}, {ack_address, ack}}};
    std::array<Bytes, 7> code;
    constant(code[0], FOUNDATION_APPENDED_ABI_VERSION); constant(code[1], 16384);
    gateway(code[3], 256, discover.size()); copy64(code[3], control_address, reply_address + 72);
    acknowledge_gateway(code[3], ack.size());
    copy64(code[3], 512 + FOUNDATION_APPENDED_OFFSET_INTERFACE, control_address);
    gateway(code[3], 512, register_packet.size()); acknowledge_gateway(code[3], ack.size()); constant(code[3], 0);
    auto& dispatch = code[4];
    gateway(dispatch, native_address, native.size()); acknowledge_gateway(dispatch, ack.size());
    constant(dispatch, count_address); load32(dispatch, count_address); constant(dispatch, 1);
    append(dispatch, {0x6a, 0x36, 2, 0});
    copy64(dispatch, response_address + FOUNDATION_APPENDED_OFFSET_INTERFACE, control_address);
    event64(dispatch, response_address + 72, FOUNDATION_APPENDED_OFFSET_CORRELATION);
    event64(dispatch, response_address + 88, 72);
    constant(dispatch, response_address + 116); append(dispatch, {0x20, 0, 0x28, 2, 100});
    constant(dispatch, 1); append(dispatch, {0x6a, 0x36, 2, 0});
    constant(dispatch, response_address + 120); load32(dispatch, count_address); append(dispatch, {0x36, 2, 0});
    gateway(dispatch, response_address, response.size()); acknowledge_gateway(dispatch, ack.size());
    if (trap_after_response) dispatch.push_back(0x00);
    constant(dispatch, 0); constant(code[5], 0);
    Bytes module{0, 97, 115, 109, 1, 0, 0, 0};
    section(module, 1, {6, 0x60, 4, 0x7f, 0x7f, 0x7f, 0x7f, 1, 0x7f,
        0x60, 0, 1, 0x7f, 0x60, 1, 0x7f, 1, 0x7f, 0x60, 2, 0x7f, 0x7f, 0,
        0x60, 2, 0x7f, 0x7f, 1, 0x7f, 0x60, 1, 0x7f, 0});
    Bytes imports{1}; wasm_name(imports, FOUNDATION_APPENDED_IMPORT_MODULE); wasm_name(imports, FOUNDATION_APPENDED_IMPORT_NAME);
    append(imports, {0, 0}); section(module, 2, imports); section(module, 3, {7, 1, 2, 3, 4, 4, 2, 5});
    section(module, 5, {1, 1, 1, 1});
    Bytes exports{8}; wasm_name(exports, "memory"); append(exports, {2, 0});
    constexpr std::array names{"foundation_app_abi_v1", "foundation_app_alloc_v1", "foundation_app_free_v1",
        "foundation_app_init_v1", "foundation_app_dispatch_v1", "foundation_app_step_v1", "foundation_app_shutdown_v1"};
    for (std::size_t i = 0; i != names.size(); ++i) {
        wasm_name(exports, names[i]); exports.push_back(0); uleb(exports, static_cast<std::uint32_t>(i + 1));
    }
    section(module, 7, exports);
    Bytes bodies{7};
    for (const auto& instructions : code) {
        Bytes body{0}; append(body, instructions); body.push_back(0x0b);
        uleb(bodies, static_cast<std::uint32_t>(body.size())); append(bodies, body);
    }
    section(module, 10, bodies);
    Bytes segments; uleb(segments, static_cast<std::uint32_t>(data.size()));
    for (const auto& [address, bytes] : data) {
        segments.push_back(0); constant(segments, static_cast<std::int32_t>(address)); segments.push_back(0x0b);
        uleb(segments, static_cast<std::uint32_t>(bytes.size())); append(segments, bytes);
    }
    section(module, 11, segments);
    return module;
}

struct Fixture {
    unsigned effects = 0;
    std::function<void()> on_effect;
    std::unique_ptr<EngineOwner> owner;
    EngineIdentity current{worker_epoch, application_instance, 0, 0};
    bool binary;

    explicit Fixture(bool with_binary = false, bool abandon = false, bool trap = false) : binary(with_binary) {
        EngineOwnerConfiguration config;
        config.worker_epoch = worker_epoch;
        config.application_instance = application_instance;
        config.module_generation = module_generation;
        config.abandon_closed_document_outcomes = abandon;
        config.native_services.push_back({{std::string(native_name), 1, 0, native_schema, 4},
            [this](std::uint32_t operation, std::span<const std::uint8_t> input,
                   std::span<std::uint8_t> output) -> ServiceReply {
                if (operation != 1) return {ServiceStatus::unknown_operation, 0};
                if (input.size() != 4) return {ServiceStatus::invalid_request, 0};
                require(output.size() >= 4, "actual native owner reply was not reserved");
                ++effects;
                if (on_effect) on_effect();
                const auto result = encode_u32(static_cast<std::uint32_t>(get(input, 0, 4)) + 1);
                std::copy(result.begin(), result.end(), output.begin());
                return {ServiceStatus::ok, 4};
            }});
        auto package = trusted_package();
        if (binary) {
            config.module_factory = make_engine_module_binding;
            Registry probe(module_generation);
            require(install_native_services(probe, config.native_services) == ServiceStatus::ok,
                "fixture could not determine the actual native registration handle");
            const auto native = probe.discover({native_name, 1, 0, 0, native_schema});
            require(native.status == ServiceStatus::ok && native.handle != 0,
                "fixture native Registry probe could not discover its actual registration");
            package.binary = {true, "binary/application.wasm", "foundation-guest-v1"};
            package.services = {"foundation.providers", std::string(native_name)};
            package.capabilities = {"foundation.providers.v1", "foundation.startup.v1"};
            package.files.insert(package.files.begin(), {"binary/application.wasm", "binary", "application/wasm",
                std::string(64, '4'), provider_fixture(native.handle, trap)});
        }
        owner = std::make_unique<EngineOwner>(std::move(package), std::move(config));
    }

    Reply call(std::uint32_t operation, const Bytes& payload = {}, std::uint64_t transfer = 0,
               std::size_t capacity = FOUNDATION_ENGINE_MAX_BODY_BYTES + receipt_bytes) {
        return call_as(operation, current, payload, transfer, capacity);
    }

    Reply call_as(std::uint32_t operation, EngineIdentity identity, const Bytes& payload = {},
                  std::uint64_t transfer = 0,
                  std::size_t capacity = FOUNDATION_ENGINE_MAX_BODY_BYTES + receipt_bytes) {
        return dispatch(*owner, operation, bridge_record(operation, identity, payload, transfer), capacity);
    }

    void boot() {
        require(call(FOUNDATION_ENGINE_CONFIGURE).ok() && owner->configured() && owner->has_module() == binary,
            "owner configuration did not honor actual web-only/provider-only Module presence");
        begin(1);
    }

    void begin(std::uint64_t document) {
        auto prospective = current;
        prospective.document_sequence = document;
        prospective.service_generation = 0;
        const auto reply = call_as(FOUNDATION_ENGINE_BEGIN_DOCUMENT, prospective);
        require(reply.ok() && reply.identity.worker_epoch == worker_epoch &&
            reply.identity.application_instance == application_instance &&
            reply.identity.document_sequence == document && reply.identity.service_generation != 0,
            "document did not receive a real nonzero service generation");
        current = reply.identity;
        require(owner->identity() == current, "issued document identity differs from actual owner");
    }

    void enter(std::uint64_t transfer = 0) {
        require(call(FOUNDATION_ENGINE_TURN_ENTER, {}, transfer).ok(), "engine turn admission");
    }
    void leave(std::uint64_t transfer = 0) {
        require(call(FOUNDATION_ENGINE_TURN_LEAVE, {}, transfer).ok(), "engine turn exit");
    }

    Reply submit(std::uint64_t sequence, std::uint64_t handle, std::uint32_t operation,
                 const Bytes& payload) {
        return call(FOUNDATION_ENGINE_SUBMIT, service_request(current, sequence, handle, operation, payload));
    }

    void result(std::uint32_t operation, const Reply& pending, std::uint32_t disposition) {
        require(call_as(operation, pending.identity, scalar(disposition, 4), pending.transfer).ok(),
            "retained transfer result was not accepted");
    }

    void accept_delivery(const Reply& pending) {
        require(call_as(FOUNDATION_ENGINE_TURN_ENTER, pending.identity, {}, pending.transfer).ok(),
            "matching delivery could not enter its guarded turn");
        require(call_as(FOUNDATION_ENGINE_TURN_LEAVE, pending.identity, {}, pending.transfer).ok(),
            "matching delivery turn did not leave");
        result(FOUNDATION_ENGINE_DELIVERY_RESULT, pending, FOUNDATION_ENGINE_ACCEPTED);
    }

    void collect_ack(const Reply& pending) {
        require(call_as(FOUNDATION_ENGINE_TURN_ENTER, pending.identity, {}, pending.transfer).ok(),
            "matching ACK receipt could not enter its guarded turn");
        require(call_as(FOUNDATION_ENGINE_TURN_LEAVE, pending.identity, {}, pending.transfer).ok(),
            "matching ACK receipt turn did not leave");
        result(FOUNDATION_ENGINE_ACK_RECEIPT_RESULT, pending, FOUNDATION_ENGINE_ACCEPTED);
    }

    Reply apply_ack(EngineIdentity identity, std::uint64_t through) {
        const auto staged = call_as(FOUNDATION_ENGINE_STAGE_ACK, identity, scalar(through, 8));
        require(staged.control == FOUNDATION_ENGINE_OK && staged.service == ServiceStatus::unavailable,
            "ACK intent claimed to have retired actual queue outcomes synchronously");
        require(call(FOUNDATION_ENGINE_PUMP_ONE).ok(), "owner failed to apply staged actual ACK");
        const auto receipt = call(FOUNDATION_ENGINE_PEEK_ACK_RECEIPT);
        require(receipt.ok() && receipt.identity == identity && receipt.transfer != 0 &&
            receipt.data().size() == 12 && get(receipt.data(), 0, 8) == through &&
            get(receipt.data(), 8, 4) == FOUNDATION_APPENDED_SERVICE_OK,
            "actual ACK receipt lost its original identity, prefix or status");
        return receipt;
    }

    std::uint64_t discover_service(std::string_view name, std::uint32_t maximum_minor) {
        require(submit(1, 0, FOUNDATION_APPENDED_CONTROL_DISCOVER, discovery(name, maximum_minor)).ok(),
            "service discovery admission");
        require(call(FOUNDATION_ENGINE_PUMP_ONE).ok(), "service discovery pump");
        const auto pending = call(FOUNDATION_ENGINE_PEEK_DELIVERY);
        const auto value = completion(pending);
        require(value.header.service_status == FOUNDATION_APPENDED_SERVICE_OK &&
            value.header.generation == current.service_generation && value.header.sequence == 1,
            "service discovery completion identity/status");
        std::vector<FieldView> fields;
        std::uint64_t handle = 0;
        require(decode_record(value.payload, fields) == CodecStatus::ok && fields.size() == 6 &&
            read_u64(fields[0], handle) && handle != 0 && fields[1].type == FieldType::utf8 &&
            Bytes(fields[1].value.begin(), fields[1].value.end()) == Bytes(name.begin(), name.end()),
            "service discovery did not issue the requested opaque route");
        accept_delivery(pending);
        const auto ack = apply_ack(current, 1);
        collect_ack(ack);
        return handle;
    }

    std::uint64_t discover_native() { return discover_service(native_name, 0); }
};

void exact_abi_and_capacity_before_effects() {
    Fixture f;
    const auto configured = f.call(FOUNDATION_ENGINE_CONFIGURE, {}, 0, receipt_bytes - 1);
    require(configured.transport == FOUNDATION_ENGINE_REPLY_TOO_SMALL && !f.owner->configured(),
        "short configuration reply capacity admitted startup effects");
    f.boot();
    const auto handle = f.discover_native();
    const auto input = bridge_record(FOUNDATION_ENGINE_SUBMIT, f.current,
        service_request(f.current, 2, handle, 1, encode_u32(41)));
    require(dispatch(*f.owner, FOUNDATION_ENGINE_SUBMIT, input, receipt_bytes - 1).transport ==
        FOUNDATION_ENGINE_REPLY_TOO_SMALL && f.effects == 0, "short submit reply admitted a native call");
    require(dispatch(*f.owner, FOUNDATION_ENGINE_SUBMIT, input).ok(), "retry after unadmitted short submit");
    auto unready = f.current;
    unready.service_generation = 0;
    require(!f.call_as(FOUNDATION_ENGINE_PUMP_ONE, unready).ok() && f.effects == 0 &&
        !f.call_as(FOUNDATION_ENGINE_PEEK_DELIVERY, unready).ok(),
        "generation-zero lifecycle metadata could execute or collect an actual service");
    require(f.call(FOUNDATION_ENGINE_PUMP_ONE, {}, 0, receipt_bytes - 1).transport ==
        FOUNDATION_ENGINE_REPLY_TOO_SMALL && f.effects == 0, "short pump reply executed a native effect");
    require(f.call(FOUNDATION_ENGINE_PUMP_ONE).ok() && f.effects == 1, "valid pump did not run exactly one native effect");
    const auto pending = f.call(FOUNDATION_ENGINE_PEEK_DELIVERY);
    const auto decoded = completion(pending);
    require(decoded.header.sequence == 2 && decoded.payload == encode_u32(42), "actual native result was not copied");
    require(f.call(FOUNDATION_ENGINE_PEEK_DELIVERY, {}, 0, pending.bytes.size() - 1).transport ==
        FOUNDATION_ENGINE_REPLY_TOO_SMALL && f.call(FOUNDATION_ENGINE_PEEK_DELIVERY).bytes == pending.bytes && f.effects == 1,
        "short delivery copy consumed or altered the retained completion");
    auto malformed = bridge_record(FOUNDATION_ENGINE_PUMP_ONE, f.current);
    put(malformed, 60, 1, 4);
    require(dispatch(*f.owner, FOUNDATION_ENGINE_PUMP_ONE, malformed).transport == FOUNDATION_ENGINE_BAD_RECORD &&
        f.effects == 1, "reserved bridge header bits admitted work");
}

void callback_depth_and_native_reentry() {
    Fixture f;
    f.boot();
    const auto handle = f.discover_native();
    f.enter();
    f.enter();
    require(f.owner->callback_depth() == 2, "nested native callback depth was not retained");
    require(f.submit(2, handle, 1, encode_u32(8)).ok() && f.effects == 0, "callback admission executed native owner work");
    require(!f.call(FOUNDATION_ENGINE_PUMP_ONE).ok() && !f.call(FOUNDATION_ENGINE_PEEK_DELIVERY).ok() && f.effects == 0,
        "active engine callback allowed pump or delivery collection");
    f.leave();
    require(f.owner->callback_depth() == 1 && !f.call(FOUNDATION_ENGINE_PUMP_ONE).ok(),
        "nested leave prematurely removed the callback barrier");
    f.leave();
    require(f.owner->callback_depth() == 0, "complete native turn did not leave its callback scope");
    unsigned reentry_checks = 0;
    f.on_effect = [&] {
        ++reentry_checks;
        require(f.owner->callback_depth() == 0, "actual handler ran inside the engine callback");
        require(!f.call(FOUNDATION_ENGINE_PUMP_ONE).ok() && !f.call(FOUNDATION_ENGINE_TURN_ENTER).ok() &&
            !f.call(FOUNDATION_ENGINE_PEEK_DELIVERY).ok() && !f.call(FOUNDATION_ENGINE_PEEK_ACK_RECEIPT).ok(),
            "native handler reentered a pump, engine turn or completion delivery");
    };
    require(f.call(FOUNDATION_ENGINE_PUMP_ONE).ok() && f.effects == 1 && reentry_checks == 1,
        "serialized native handler pump did not complete exactly once");
    const auto pending = f.call(FOUNDATION_ENGINE_PEEK_DELIVERY);
    require(completion(pending).payload == encode_u32(9), "reentry guard lost the actual native result");
}

void retained_delivery_rejection_retry_and_stale_tokens() {
    Fixture f;
    f.boot();
    const auto handle = f.discover_native();
    require(f.submit(2, handle, 1, encode_u32(41)).ok() && f.call(FOUNDATION_ENGINE_PUMP_ONE).ok(),
        "delivery fixture native call");
    const auto pending = f.call(FOUNDATION_ENGINE_PEEK_DELIVERY);
    require(completion(pending).payload == encode_u32(42) && f.effects == 1 &&
        f.call(FOUNDATION_ENGINE_PEEK_DELIVERY).bytes == pending.bytes, "peek did not retain exact copied native outcome");
    require(!f.call(FOUNDATION_ENGINE_TURN_ENTER).ok() && !f.call(FOUNDATION_ENGINE_PUMP_ONE).ok(),
        "normal engine work passed an unresolved delivery barrier");
    require(!f.call(FOUNDATION_ENGINE_DELIVERY_RESULT, scalar(FOUNDATION_ENGINE_ACCEPTED, 4), pending.transfer + 1).ok() &&
        f.call(FOUNDATION_ENGINE_PEEK_DELIVERY).bytes == pending.bytes, "stale delivery token cleared a live mailbox");
    f.result(FOUNDATION_ENGINE_DELIVERY_RESULT, pending, FOUNDATION_ENGINE_REJECTED);
    require(!f.call(FOUNDATION_ENGINE_TURN_ENTER, {}, pending.transfer).ok() &&
        !f.call(FOUNDATION_ENGINE_PUMP_ONE).ok() && f.call(FOUNDATION_ENGINE_PEEK_DELIVERY).bytes == pending.bytes,
        "rejected completion was retried implicitly or lost its exact bytes");
    f.result(FOUNDATION_ENGINE_DELIVERY_RESULT, pending, FOUNDATION_ENGINE_RETRY);
    require(f.call(FOUNDATION_ENGINE_PEEK_DELIVERY).bytes == pending.bytes && f.effects == 1,
        "explicit delivery retry reconstructed or reran the service effect");
    f.accept_delivery(pending);
    require(f.call(FOUNDATION_ENGINE_PEEK_DELIVERY).control == FOUNDATION_ENGINE_EMPTY &&
        !f.call(FOUNDATION_ENGINE_DELIVERY_RESULT, scalar(FOUNDATION_ENGINE_ACCEPTED, 4), pending.transfer).ok(),
        "accepted delivery stayed live or an old result token affected a later transfer");
    require(f.submit(2, handle, 1, encode_u32(41)).ok() && f.call(FOUNDATION_ENGINE_PUMP_ONE).ok(),
        "explicit identical service replay admission");
    const auto replay = f.call(FOUNDATION_ENGINE_PEEK_DELIVERY);
    require(replay.transfer != pending.transfer && replay.data() == pending.data() && f.effects == 1,
        "service replay repeated its effect or reused transport authority");
}

void staged_ack_barrier_and_receipt_retention() {
    Fixture f;
    f.boot();
    const auto handle = f.discover_native();
    require(f.submit(2, handle, 1, encode_u32(6)).ok() && f.call(FOUNDATION_ENGINE_PUMP_ONE).ok(),
        "ACK fixture native call");
    const auto pending = f.call(FOUNDATION_ENGINE_PEEK_DELIVERY);
    f.enter(pending.transfer);
    const auto staged = f.call(FOUNDATION_ENGINE_STAGE_ACK, scalar(2, 8));
    require(staged.control == FOUNDATION_ENGINE_OK && staged.service == ServiceStatus::unavailable &&
        !f.call(FOUNDATION_ENGINE_PUMP_ONE).ok() && !f.call(FOUNDATION_ENGINE_PEEK_ACK_RECEIPT).ok(),
        "callback ACK intent applied or exposed actual retirement synchronously");
    const auto duplicate_intent = f.call(FOUNDATION_ENGINE_STAGE_ACK, scalar(2, 8));
    require(duplicate_intent.bytes == staged.bytes && !f.call(FOUNDATION_ENGINE_STAGE_ACK, scalar(1, 8)).ok(),
        "identical ACK intent changed its transaction or another intent replaced it");
    f.leave(pending.transfer);
    require(!f.call(FOUNDATION_ENGINE_PUMP_ONE).ok() &&
        f.call(FOUNDATION_ENGINE_PEEK_DELIVERY).bytes == pending.bytes,
        "staged ACK retired a ready completion before delivery acceptance");
    f.result(FOUNDATION_ENGINE_DELIVERY_RESULT, pending, FOUNDATION_ENGINE_ACCEPTED);
    require(f.call(FOUNDATION_ENGINE_PEEK_ACK_RECEIPT).control == FOUNDATION_ENGINE_EMPTY,
        "staged ACK fabricated a receipt before actual queue retirement");
    require(f.call(FOUNDATION_ENGINE_PUMP_ONE, {}, 0, receipt_bytes - 1).transport ==
        FOUNDATION_ENGINE_REPLY_TOO_SMALL, "short pump reply applied a staged ACK");
    require(f.call(FOUNDATION_ENGINE_PEEK_ACK_RECEIPT).control == FOUNDATION_ENGINE_EMPTY &&
        f.call(FOUNDATION_ENGINE_PUMP_ONE).ok(), "valid owner task failed to apply the staged ACK");
    const auto receipt = f.call(FOUNDATION_ENGINE_PEEK_ACK_RECEIPT);
    require(receipt.ok() && receipt.transfer != 0 && receipt.identity == f.current && receipt.data().size() == 12 &&
        get(receipt.data(), 0, 8) == 2 && get(receipt.data(), 8, 4) == FOUNDATION_APPENDED_SERVICE_OK,
        "retained ACK receipt does not record actual WebServices outcome");
    require(f.call(FOUNDATION_ENGINE_STAGE_ACK, scalar(2, 8)).ok() &&
        f.call(FOUNDATION_ENGINE_PEEK_ACK_RECEIPT).bytes == receipt.bytes &&
        !f.call(FOUNDATION_ENGINE_STAGE_ACK, scalar(1, 8)).ok(),
        "repeated applied ACK did not return its cached actual status or changed the retained receipt");
    auto foreign_ack = f.current;
    ++foreign_ack.document_sequence;
    require(!f.call_as(FOUNDATION_ENGINE_STAGE_ACK, foreign_ack, scalar(2, 8)).ok() &&
        f.call(FOUNDATION_ENGINE_PEEK_ACK_RECEIPT).bytes == receipt.bytes,
        "foreign ACK identity collected or replaced the retained actual receipt");
    require(!f.call(FOUNDATION_ENGINE_PUMP_ONE).ok() && !f.call(FOUNDATION_ENGINE_TURN_ENTER).ok(),
        "normal work passed an uncollected actual ACK receipt");
    require(f.call(FOUNDATION_ENGINE_PEEK_ACK_RECEIPT, {}, 0, receipt.bytes.size() - 1).transport ==
        FOUNDATION_ENGINE_REPLY_TOO_SMALL && f.call(FOUNDATION_ENGINE_PEEK_ACK_RECEIPT).bytes == receipt.bytes,
        "short receipt copy consumed the actual ACK outcome");
    f.result(FOUNDATION_ENGINE_ACK_RECEIPT_RESULT, receipt, FOUNDATION_ENGINE_REJECTED);
    require(!f.call(FOUNDATION_ENGINE_TURN_ENTER, {}, receipt.transfer).ok() &&
        f.call(FOUNDATION_ENGINE_PEEK_ACK_RECEIPT).bytes == receipt.bytes && f.effects == 1,
        "rejected ACK collection reapplied work or lost the original receipt");
    require(!f.call(FOUNDATION_ENGINE_ACK_RECEIPT_RESULT, scalar(FOUNDATION_ENGINE_ACCEPTED, 4), receipt.transfer + 1).ok(),
        "stale ACK receipt token collected an unrelated transaction");
    f.result(FOUNDATION_ENGINE_ACK_RECEIPT_RESULT, receipt, FOUNDATION_ENGINE_RETRY);
    f.collect_ack(receipt);
    require(f.call(FOUNDATION_ENGINE_PEEK_ACK_RECEIPT).control == FOUNDATION_ENGINE_EMPTY &&
        f.submit(2, handle, 1, encode_u32(6)).service == ServiceStatus::expired && f.effects == 1,
        "actual ACK was not applied once or service replay survived completed retirement");
}

void actual_module_provider_survives_document_navigation() {
    Fixture f(true);
    f.boot();
    require(f.owner->has_module() && f.effects == 0,
        "provider-only binary was absent or startup executed the application provider");
    const auto first_document = f.current;
    const auto first_handle = f.discover_service(module_name, 2);
    f.enter();
    require(f.submit(2, first_handle, 1, encode_u32(41)).ok() && f.effects == 0,
        "engine callback synchronously invoked the actual Module provider/native gateway");
    f.leave();
    require(f.call(FOUNDATION_ENGINE_PUMP_ONE).ok() && f.effects == 1,
        "owner task did not dispatch the actual Module provider and captured native service once");
    const auto first = f.call(FOUNDATION_ENGINE_PEEK_DELIVERY);
    const auto value = completion(first);
    require(value.header.service_status == FOUNDATION_APPENDED_SERVICE_OK && value.payload.size() == 8 &&
        get(value.payload, 0, 4) == 42 && get(value.payload, 4, 4) == 1,
        "real Module provider did not return its computed result and persistent guest counter");
    f.accept_delivery(first);
    const auto first_ack = f.apply_ack(f.current, 2);
    f.collect_ack(first_ack);
    f.begin(2);
    require(f.current.service_generation != first_document.service_generation && f.owner->has_module(),
        "navigation replaced service identity without retaining the actual provider-only Module");
    const auto second_handle = f.discover_service(module_name, 2);
    require(f.submit(2, second_handle, 1, encode_u32(8)).ok() && f.call(FOUNDATION_ENGINE_PUMP_ONE).ok() && f.effects == 2,
        "successor document reset the Module host-call/event/gateway sequence or lost the captured native owner");
    const auto second = f.call(FOUNDATION_ENGINE_PEEK_DELIVERY);
    const auto successor = completion(second);
    require(successor.header.generation == f.current.service_generation && successor.payload.size() == 8 &&
        successor.header.service_status == FOUNDATION_APPENDED_SERVICE_OK &&
        get(successor.payload, 0, 4) == 9 && get(successor.payload, 4, 4) == 2,
        "second actual provider invocation failed or recreated guest state after navigation");
    f.accept_delivery(second);
    const auto second_ack = f.apply_ack(f.current, 2);
    f.collect_ack(second_ack);
    const auto native_handle = [&] {
        require(f.submit(3, 0, FOUNDATION_APPENDED_CONTROL_DISCOVER, discovery()).ok() &&
            f.call(FOUNDATION_ENGINE_PUMP_ONE).ok(), "website native registration was not retained beside Module provider");
        const auto pending = f.call(FOUNDATION_ENGINE_PEEK_DELIVERY);
        const auto result = completion(pending);
        std::vector<FieldView> fields;
        std::uint64_t handle = 0;
        require(result.header.service_status == FOUNDATION_APPENDED_SERVICE_OK &&
            decode_record(result.payload, fields) == CodecStatus::ok && fields.size() == 6 && read_u64(fields[0], handle),
            "website Registry did not expose its independent actual native wrapper");
        f.accept_delivery(pending);
        return handle;
    }();
    require(native_handle != second_handle && f.submit(4, native_handle, 1, encode_u32(10)).ok() &&
        f.call(FOUNDATION_ENGINE_PUMP_ONE).ok() && f.effects == 3,
        "web/native and module/provider opaque routes shared a handle or lost their common captured counter owner");
    require(completion(f.call(FOUNDATION_ENGINE_PEEK_DELIVERY)).payload == encode_u32(11),
        "independent website native registration did not return the actual owner result");
}

Reply expect_retirement_completion(Fixture& f, EngineIdentity old, std::uint64_t sequence,
                                   std::uint64_t handle, ServiceStatus status, const Bytes& payload = {}) {
    const auto audit = f.call(FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT);
    const auto outcome = completion(audit);
    require(audit.identity == old && outcome.header.generation == old.service_generation &&
        outcome.header.sequence == sequence && outcome.header.interface_handle == handle &&
        outcome.header.operation == 1 && outcome.header.service_status == static_cast<std::uint32_t>(status) &&
        outcome.payload == payload, "retirement audit changed the actual canonical outcome or old identity");
    return audit;
}

Reply finish_retired_document(Fixture& f, EngineIdentity old) {
    const auto retired = f.call(FOUNDATION_ENGINE_PEEK_RETIRED_DOCUMENT);
    require(retired.ok() && retired.identity == old && retired.identity.service_generation != 0 &&
        retired.transfer != 0 && retired.data().empty(), "settled old document did not receive disposal authority");
    require(f.call_as(FOUNDATION_ENGINE_TURN_ENTER, old, {}, retired.transfer).ok() &&
        f.call_as(FOUNDATION_ENGINE_TURN_LEAVE, old, {}, retired.transfer).ok(),
        "old document disposal did not run under a fresh matching native guard");
    f.result(FOUNDATION_ENGINE_RETIRED_DOCUMENT_RESULT, retired, FOUNDATION_ENGINE_ACCEPTED);
    return retired;
}

void retired_outcomes_require_exact_owner_audit_before_document_disposal() {
    Fixture f(false, true);
    f.boot();
    const auto handle = f.discover_native();
    const auto old = f.current;
    require(f.submit(2, handle, 1, encode_u32(41)).ok() && f.call(FOUNDATION_ENGINE_PUMP_ONE).ok(),
        "terminalization completed native fixture");
    const auto delivered = f.call(FOUNDATION_ENGINE_PEEK_DELIVERY);
    f.accept_delivery(delivered); // The disposed page never supplies its web ACK.
    require(f.submit(7, handle, 1, encode_u32(8)).ok(), "terminalization queued native fixture");
    f.begin(2);
    require(f.effects == 1 && f.call(FOUNDATION_ENGINE_PEEK_DELIVERY).control == FOUNDATION_ENGINE_EMPTY &&
        f.call(FOUNDATION_ENGINE_PEEK_RETIRED_DOCUMENT).control == FOUNDATION_ENGINE_EMPTY,
        "retirement delivered to the disposed page or disposed a queue with unaudited outcomes");
    require(f.call(FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT, {}, 0, receipt_bytes + delivered.data().size() - 1).transport ==
        FOUNDATION_ENGINE_REPLY_TOO_SMALL && f.effects == 1,
        "short audit output retired an outcome or repeated the native effect");
    const auto audit = expect_retirement_completion(f, old, 2, handle, ServiceStatus::ok, encode_u32(42));
    require(audit.data() == delivered.data() && audit.transfer != delivered.transfer &&
        f.call(FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT).bytes == audit.bytes,
        "retirement did not retain byte-identical actual completion under new transport authority");
    auto foreign = f.current;
    ++foreign.document_sequence;
    require(!f.call_as(FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT, foreign).ok() &&
        !f.call_as(FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT, old,
            scalar(FOUNDATION_ENGINE_ABANDONED, 4), audit.transfer + 1).ok(),
        "foreign metadata or stale result token gained terminalization authority");
    for (const auto disposition : {0u, 1u, 2u, 3u, 5u})
        require(!f.call_as(FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT, old,
            scalar(disposition, 4), audit.transfer).ok() &&
            f.call(FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT).bytes == audit.bytes,
            "non-abandonment disposition mutated a retirement audit");
    require(f.call_as(FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT, old, scalar(FOUNDATION_ENGINE_ABANDONED, 4),
        audit.transfer, receipt_bytes - 1).transport == FOUNDATION_ENGINE_REPLY_TOO_SMALL &&
        f.call(FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT).bytes == audit.bytes && f.effects == 1,
        "short abandonment receipt applied actual queue ACK before its response was reserved");
    f.result(FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT, audit, FOUNDATION_ENGINE_ABANDONED);
    const auto queued = expect_retirement_completion(f, old, 7, handle, ServiceStatus::closed);
    require(queued.transfer != audit.transfer && f.effects == 1,
        "queued retirement ran its handler or reused a live audit token");
    f.result(FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT, audit, FOUNDATION_ENGINE_ABANDONED);
    require(f.call(FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT).bytes == queued.bytes &&
        f.call(FOUNDATION_ENGINE_PEEK_RETIRED_DOCUMENT).control == FOUNDATION_ENGINE_EMPTY,
        "latest exact duplicate abandonment cleared the next audit or prematurely disposed its owner");
    f.result(FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT, queued, FOUNDATION_ENGINE_ABANDONED);
    const auto retired = f.call(FOUNDATION_ENGINE_PEEK_RETIRED_DOCUMENT);
    require(retired.ok() && retired.identity == old && retired.data().empty() && retired.transfer != 0 &&
        retired.transfer != queued.transfer && retired.transfer != audit.transfer &&
        f.call(FOUNDATION_ENGINE_PEEK_RETIRED_DOCUMENT).bytes == retired.bytes,
        "settled retirement failed to retain unique exact disposal authority");
    require(!f.call_as(FOUNDATION_ENGINE_RETIRED_DOCUMENT_RESULT, old, scalar(FOUNDATION_ENGINE_ACCEPTED, 4),
        retired.transfer + 1).ok() &&
        f.call_as(FOUNDATION_ENGINE_RETIRED_DOCUMENT_RESULT, old, scalar(FOUNDATION_ENGINE_ACCEPTED, 4),
            retired.transfer, receipt_bytes - 1).transport == FOUNDATION_ENGINE_REPLY_TOO_SMALL,
        "stale disposal result or short response space erased the retained document");
    require(f.call_as(FOUNDATION_ENGINE_TURN_ENTER, old, {}, retired.transfer).ok() &&
        f.call_as(FOUNDATION_ENGINE_TURN_LEAVE, old, {}, retired.transfer).ok(),
        "exact old retirement identity could not enter and leave its disposal guard");
    f.result(FOUNDATION_ENGINE_RETIRED_DOCUMENT_RESULT, retired, FOUNDATION_ENGINE_ACCEPTED);
    f.result(FOUNDATION_ENGINE_RETIRED_DOCUMENT_RESULT, retired, FOUNDATION_ENGINE_ACCEPTED);
    auto wrong_worker = old;
    ++wrong_worker.worker_epoch;
    require(!f.call_as(FOUNDATION_ENGINE_RETIRED_DOCUMENT_RESULT, wrong_worker,
        scalar(FOUNDATION_ENGINE_ACCEPTED, 4), retired.transfer).ok() &&
        f.call(FOUNDATION_ENGINE_PEEK_RETIRED_DOCUMENT).control == FOUNDATION_ENGINE_EMPTY &&
        f.call(FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT).control == FOUNDATION_ENGINE_EMPTY && f.effects == 1,
        "duplicate disposal crossed Worker authority or resurrected old outcomes");
}

void retirement_drain_remains_bounded_across_many_navigations() {
    Fixture f(false, true);
    f.boot();
    for (std::uint64_t document = 1; document <= 12; ++document) {
        const auto old = f.current;
        require(old.document_sequence == document &&
            f.submit(1, 0, FOUNDATION_APPENDED_CONTROL_DISCOVER, discovery()).ok(),
            "repeated navigation could not admit its queued discovery");
        f.begin(document + 1);
        require(f.call(FOUNDATION_ENGINE_PEEK_DELIVERY).control == FOUNDATION_ENGINE_EMPTY,
            "disposed repeated-navigation page was asked to accept a completion");
        const auto audit = f.call(FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT);
        const auto outcome = completion(audit);
        require(audit.identity == old && outcome.header.sequence == 1 && outcome.header.interface_handle == 0 &&
            outcome.header.operation == FOUNDATION_APPENDED_CONTROL_DISCOVER &&
            outcome.header.service_status == FOUNDATION_APPENDED_SERVICE_CLOSED && outcome.payload.empty(),
            "repeated navigation changed its queued closed outcome");
        f.result(FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT, audit, FOUNDATION_ENGINE_ABANDONED);
        const auto retired = finish_retired_document(f, old);
        require(retired.transfer != audit.transfer && f.effects == 0 &&
            f.call(FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT).control == FOUNDATION_ENGINE_EMPTY &&
            f.call(FOUNDATION_ENGINE_PEEK_RETIRED_DOCUMENT).control == FOUNDATION_ENGINE_EMPTY,
            "repeated retirement accumulated an old queue, audit or document");
    }
}

void pending_page_transactions_convert_to_owner_audit() {
    Fixture f(false, true);
    f.boot();
    const auto handle = f.discover_native();
    const auto old = f.current;
    require(f.submit(2, handle, 1, encode_u32(41)).ok() && f.call(FOUNDATION_ENGINE_PUMP_ONE).ok(),
        "pending delivery retirement fixture");
    const auto pending = f.call(FOUNDATION_ENGINE_PEEK_DELIVERY);
    f.enter(pending.transfer);
    const auto staged = f.call(FOUNDATION_ENGINE_STAGE_ACK, scalar(2, 8));
    require(staged.control == FOUNDATION_ENGINE_OK && staged.service == ServiceStatus::unavailable &&
        f.call(FOUNDATION_ENGINE_CLOSE_DOCUMENT).ok(), "pending delivery could not stage ACK and retire its document");
    f.begin(2);
    require(f.call_as(FOUNDATION_ENGINE_TURN_LEAVE, old, {}, pending.transfer).ok() && f.owner->callback_depth() == 0,
        "navigation could not leave the exact old delivery guard after adopting its successor");
    const auto audit = expect_retirement_completion(f, old, 2, handle, ServiceStatus::ok, encode_u32(42));
    require(audit.data() == pending.data() && audit.transfer != pending.transfer &&
        !f.call_as(FOUNDATION_ENGINE_DELIVERY_RESULT, old, scalar(FOUNDATION_ENGINE_ACCEPTED, 4), pending.transfer).ok() &&
        f.call(FOUNDATION_ENGINE_PEEK_ACK_RECEIPT).control == FOUNDATION_ENGINE_EMPTY,
        "retirement conversion kept an old page delivery or unresolved staged ACK alive");
    f.result(FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT, audit, FOUNDATION_ENGINE_ABANDONED);
    finish_retired_document(f, old);
    require(f.effects == 1, "pending page retirement replayed the actual native effect");

    Fixture applied(false, true);
    applied.boot();
    const auto actual_handle = applied.discover_native();
    const auto original = applied.current;
    require(applied.submit(2, actual_handle, 1, encode_u32(6)).ok() &&
        applied.call(FOUNDATION_ENGINE_PUMP_ONE).ok(), "applied ACK retirement fixture");
    const auto delivered = applied.call(FOUNDATION_ENGINE_PEEK_DELIVERY);
    applied.accept_delivery(delivered);
    const auto receipt = applied.apply_ack(original, 2);
    applied.enter(receipt.transfer);
    require(applied.call(FOUNDATION_ENGINE_CLOSE_DOCUMENT).ok(), "applied ACK document retirement");
    applied.begin(2);
    require(applied.call_as(FOUNDATION_ENGINE_TURN_LEAVE, original, {}, receipt.transfer).ok(),
        "retirement lost the raw identity of its original ACK collection guard");
    const auto copied = applied.call(FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT);
    const auto inner = copied.data();
    require(copied.ok() && copied.identity == original && copied.transfer != receipt.transfer &&
        inner == receipt.bytes && inner.size() == 92 &&
        get(inner, 6, 2) == (FOUNDATION_ENGINE_PEEK_ACK_RECEIPT | FOUNDATION_ENGINE_REPLY_KIND) &&
        applied.call(FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT).bytes == copied.bytes,
        "already-applied ACK was reinterpreted rather than copied as its exact FKB1 receipt");
    applied.result(FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT, copied, FOUNDATION_ENGINE_ABANDONED);
    applied.result(FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT, copied, FOUNDATION_ENGINE_ABANDONED);
    finish_retired_document(applied, original);
    require(applied.effects == 1 && applied.call(FOUNDATION_ENGINE_PEEK_ACK_RECEIPT).control == FOUNDATION_ENGINE_EMPTY,
        "abandoning an applied ACK receipt repeated an effect or retained the old page transaction");
}

void actual_module_outcome_abandonment_preserves_provider_owner() {
    Fixture f(true, true);
    f.boot();
    const auto handle = f.discover_service(module_name, 2);
    const auto old = f.current;
    require(f.submit(2, handle, 1, encode_u32(41)).ok() && f.call(FOUNDATION_ENGINE_PUMP_ONE).ok(),
        "actual provider retirement fixture");
    const auto actual = f.call(FOUNDATION_ENGINE_PEEK_DELIVERY);
    const auto value = completion(actual);
    require(value.header.service_status == FOUNDATION_APPENDED_SERVICE_OK && value.payload.size() == 8 &&
        get(value.payload, 0, 4) == 42 && get(value.payload, 4, 4) == 1 && f.effects == 1,
        "actual provider retirement fixture did not execute its retained guest/native owners");
    f.accept_delivery(actual);
    require(f.submit(7, handle, 1, encode_u32(9)).ok(), "queued provider retirement fixture");
    f.begin(2);
    const auto first = expect_retirement_completion(f, old, 2, handle, ServiceStatus::ok, value.payload);
    require(first.data() == actual.data(), "retirement changed an already-accepted actual provider result");
    f.result(FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT, first, FOUNDATION_ENGINE_ABANDONED);
    const auto queued = expect_retirement_completion(f, old, 7, handle, ServiceStatus::closed);
    f.result(FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT, queued, FOUNDATION_ENGINE_ABANDONED);
    finish_retired_document(f, old);
    require(f.effects == 1 && f.owner->has_module(), "queued provider abandonment ran or replaced the actual Module");
    const auto next = f.discover_service(module_name, 2);
    require(f.submit(2, next, 1, encode_u32(8)).ok() && f.call(FOUNDATION_ENGINE_PUMP_ONE).ok() && f.effects == 2,
        "terminalization reset the retained provider sequence/ACK broker or actual native owner");
    const auto successor = completion(f.call(FOUNDATION_ENGINE_PEEK_DELIVERY));
    require(successor.header.service_status == FOUNDATION_APPENDED_SERVICE_OK && successor.payload.size() == 8 &&
        get(successor.payload, 0, 4) == 9 && get(successor.payload, 4, 4) == 2,
        "successor provider lost persistent guest state after trusted outcome abandonment");
}

void retirement_clears_empty_ack_intents_and_audits_lowest_retained_sequence() {
    for (const bool globally_closing : {false, true}) {
        Fixture empty(false, true);
        empty.boot();
        empty.discover_native(); // Actual ACK1 and ACK-result consumption leave no retained calls.
        const auto old = empty.current;
        const auto staged = empty.call(FOUNDATION_ENGINE_STAGE_ACK, scalar(1, 8));
        require(staged.control == FOUNDATION_ENGINE_OK && staged.service == ServiceStatus::unavailable,
            "empty-prefix ACK-intent fixture was not admitted");
        const auto closing = empty.call(globally_closing ? FOUNDATION_ENGINE_CLOSE : FOUNDATION_ENGINE_CLOSE_DOCUMENT);
        require(closing.control == FOUNDATION_ENGINE_OK, "empty-prefix ACK intent could not retire its document");
        const auto metadata = empty.owner->identity();
        if (!globally_closing)
            require(metadata.document_sequence == 0 && metadata.service_generation == 0,
                "closed document fabricated ready service authority for owner metadata");
        require(empty.call_as(FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT, metadata).control == FOUNDATION_ENGINE_EMPTY &&
            empty.call_as(FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT, old).control == FOUNDATION_ENGINE_EMPTY,
            "retired empty queue retained an unapplied ACK intent or rejected exact known metadata authority");
        finish_retired_document(empty, old);
        require(empty.effects == 0 && (!globally_closing || empty.owner->closed()),
            "empty retired ACK intent blocked final document/owner disposal or executed an effect");
    }

    Fixture ordered(false, true);
    ordered.boot();
    const auto handle = ordered.discover_native();
    const auto old = ordered.current;
    require(ordered.submit(2, handle, 1, encode_u32(41)).ok() &&
        ordered.call(FOUNDATION_ENGINE_PUMP_ONE).ok(), "ordered retirement first native call");
    const auto lower = ordered.call(FOUNDATION_ENGINE_PEEK_DELIVERY);
    ordered.accept_delivery(lower);
    require(ordered.submit(7, handle, 1, encode_u32(8)).ok() &&
        ordered.call(FOUNDATION_ENGINE_PUMP_ONE).ok() && ordered.effects == 2,
        "ordered retirement second actual native call");
    const auto later_delivery = ordered.call(FOUNDATION_ENGINE_PEEK_DELIVERY);
    ordered.enter(later_delivery.transfer);
    require(ordered.call(FOUNDATION_ENGINE_CLOSE_DOCUMENT).ok(), "ordered retirement close inside pending delivery guard");
    ordered.begin(2);
    require(ordered.call_as(FOUNDATION_ENGINE_TURN_LEAVE, old, {}, later_delivery.transfer).ok(),
        "ordered retirement could not leave its old pending-delivery guard");
    const auto first = expect_retirement_completion(ordered, old, 2, handle, ServiceStatus::ok, encode_u32(42));
    require(first.data() == lower.data(), "later pending delivery skipped the lower retained unACKed actual result");
    ordered.result(FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT, first, FOUNDATION_ENGINE_ABANDONED);
    const auto second = expect_retirement_completion(ordered, old, 7, handle, ServiceStatus::ok, encode_u32(9));
    require(second.data() == later_delivery.data() && ordered.effects == 2,
        "lower-prefix abandonment erased, changed or reexecuted the higher pending actual result");
    ordered.result(FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT, second, FOUNDATION_ENGINE_ABANDONED);
    finish_retired_document(ordered, old);
    require(ordered.effects == 2 && ordered.call(FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT).control == FOUNDATION_ENGINE_EMPTY,
        "ordered retirement retained a stale page-delivery attempt after auditing every actual result");
}

void actual_module_uncertain_outcome_is_audited_without_reexecution() {
    Fixture f(true, true, true);
    f.boot();
    const auto handle = f.discover_service(module_name, 2);
    const auto old = f.current;
    require(f.submit(2, handle, 1, encode_u32(41)).ok() && f.call(FOUNDATION_ENGINE_PUMP_ONE).ok() && f.effects == 1,
        "trapping provider fixture failed before its actual external effect");
    const auto pending = f.call(FOUNDATION_ENGINE_PEEK_DELIVERY);
    const auto uncertain = completion(pending);
    require(uncertain.header.service_status == FOUNDATION_APPENDED_SERVICE_UNCERTAIN && uncertain.payload.empty(),
        "trap after actual provider response was exposed as success");
    f.accept_delivery(pending);
    f.begin(2);
    const auto audit = expect_retirement_completion(f, old, 2, handle, ServiceStatus::uncertain);
    require(audit.data() == pending.data() && f.call(FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT).bytes == audit.bytes &&
        f.effects == 1, "uncertain actual effect was rewritten or replayed while being audited");
    f.result(FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT, audit, FOUNDATION_ENGINE_ABANDONED);
    f.result(FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT, audit, FOUNDATION_ENGINE_ABANDONED);
    finish_retired_document(f, old);
    require(f.effects == 1 && f.call(FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT).control == FOUNDATION_ENGINE_EMPTY,
        "uncertain actual provider effect was repeated by abandonment or document disposal");
}

void navigation_retires_queue_and_rejects_stale_authority() {
    Fixture f;
    f.boot();
    const auto handle = f.discover_native();
    const auto old = f.current;
    require(f.submit(2, handle, 1, encode_u32(19)).ok() && f.effects == 0, "navigation queued-call fixture");
    f.begin(2);
    require(f.current.service_generation != old.service_generation, "navigation inherited an old service generation");
    const auto old_submit = f.call_as(FOUNDATION_ENGINE_SUBMIT, old,
        service_request(old, 3, handle, 1, encode_u32(20)));
    require(!old_submit.ok() && !f.call_as(FOUNDATION_ENGINE_TURN_ENTER, old).ok() && f.effects == 0,
        "retired document retained ordinary service or engine-turn authority");
    auto crossed = f.current;
    crossed.service_generation = old.service_generation;
    require(!f.call_as(FOUNDATION_ENGINE_SUBMIT, crossed,
        service_request(crossed, 1, handle, 1, encode_u32(21))).ok(),
        "new document accepted an old generation or service handle");
    require(f.call(FOUNDATION_ENGINE_PUMP_ONE).ok(), "retired closed-queue completion pump");
    const auto pending = f.call(FOUNDATION_ENGINE_PEEK_DELIVERY);
    const auto value = completion(pending);
    require(pending.identity == old && value.header.generation == old.service_generation && value.header.sequence == 2 &&
        value.header.service_status == FOUNDATION_APPENDED_SERVICE_CLOSED && value.payload.empty() && f.effects == 0,
        "navigation executed old queued work or changed its closed completion identity");
    f.accept_delivery(pending);
    const auto receipt = f.apply_ack(old, 2);
    f.collect_ack(receipt);
    require(f.owner->identity() == f.current && f.effects == 0,
        "retired delivery or ACK collection replaced the current document");
    require(f.submit(1, 0, FOUNDATION_APPENDED_CONTROL_DISCOVER, discovery()).ok() &&
        f.call(FOUNDATION_ENGINE_PUMP_ONE).ok(), "successor document could not discover its independent native route");
    const auto fresh = f.call(FOUNDATION_ENGINE_PEEK_DELIVERY);
    require(completion(fresh).header.generation == f.current.service_generation && fresh.identity == f.current &&
        fresh.transfer != pending.transfer && fresh.transfer != receipt.transfer, "successor reused old transport authority");
}

void resource_epochs_copied_reads_and_close_retirement() {
    Fixture f;
    require(f.call(FOUNDATION_ENGINE_CONFIGURE).ok(), "resource owner configuration");
    auto initial = f.current;
    initial.document_sequence = 1;
    const auto first = f.call_as(FOUNDATION_ENGINE_BEGIN_RESOURCE_EPOCH, initial);
    require(first.ok() && first.data().size() == 8 && get(first.data(), 0, 8) != 0,
        "prospective resource epoch was not independently issued");
    const auto old_epoch = get(first.data(), 0, 8);
    f.begin(1);
    const auto old = f.current;
    auto prospective = old;
    prospective.document_sequence = 2;
    prospective.service_generation = 0;
    const auto next = f.call_as(FOUNDATION_ENGINE_BEGIN_RESOURCE_EPOCH, prospective);
    require(next.ok() && next.identity == prospective && next.data().size() == 8 &&
        get(next.data(), 0, 8) != 0 && get(next.data(), 0, 8) != old_epoch && f.owner->identity() == old,
        "prospective resource setup replaced the active service document or reused its epoch");
    const auto next_epoch = get(next.data(), 0, 8);
    require(f.call_as(FOUNDATION_ENGINE_TURN_ENTER, prospective).ok() &&
        f.call_as(FOUNDATION_ENGINE_TURN_LEAVE, prospective).ok() && f.owner->identity() == old,
        "an exact admitted prospective resource context could not resume without acquiring service authority");
    auto third = prospective;
    third.document_sequence = 3;
    require(f.call_as(FOUNDATION_ENGINE_BEGIN_RESOURCE_EPOCH, third).control == FOUNDATION_ENGINE_LIMIT,
        "resource owner accepted more than two pending/active contexts");
    require(f.call_as(FOUNDATION_ENGINE_SUBMIT, prospective,
        service_request(old, 1, 0, FOUNDATION_APPENDED_CONTROL_DISCOVER, discovery())).control == FOUNDATION_ENGINE_STALE,
        "prospective resource identity granted service authority");

    const auto* file = f.owner->package().find_file("web/index.html");
    require(file, "resource fixture has no actual Package entry");
    const auto url = "app://" + f.owner->package().package_sha256 + "/web/index.html";
    const auto resolve_payload = [](std::uint64_t epoch, std::uint32_t method, std::string_view value) {
        Bytes bytes(16 + value.size());
        put(bytes, 0, epoch, 8); put(bytes, 8, method, 4); put(bytes, 12, value.size(), 4);
        std::copy(value.begin(), value.end(), bytes.begin() + 16);
        return bytes;
    };
    const auto read_payload = [](std::uint64_t lease, std::uint64_t offset, std::uint32_t count) {
        Bytes bytes(20);
        put(bytes, 0, lease, 8); put(bytes, 8, offset, 8); put(bytes, 16, count, 4);
        return bytes;
    };
    const auto resolve = [&](EngineIdentity identity, std::uint64_t epoch, std::uint32_t method,
                             std::string_view value) {
        return f.call_as(FOUNDATION_ENGINE_RESOURCE_RESOLVE, identity, resolve_payload(epoch, method, value));
    };
    const auto check_metadata = [&](const Reply& response, std::uint64_t body_bytes) {
        const auto metadata = response.data();
        require(response.ok() && metadata.size() == 32 + file->media_type.size() && get(metadata, 0, 4) == 200 &&
            get(metadata, 4, 4) == file->media_type.size() && get(metadata, 8, 8) == body_bytes &&
            get(metadata, 16, 8) == file->data.size() && get(metadata, 24, 8) != 0 &&
            Bytes(metadata.begin() + 32, metadata.end()) == Bytes(file->media_type.begin(), file->media_type.end()),
            "copied resource metadata lost actual MIME, body extent, content length or opaque lease");
        return get(metadata, 24, 8);
    };
    require(f.call_as(FOUNDATION_ENGINE_RESOURCE_RESOLVE, prospective,
        resolve_payload(next_epoch, 0, url), 0, receipt_bytes + 32 + 126).transport == FOUNDATION_ENGINE_REPLY_TOO_SMALL,
        "resource resolve issued a lease without complete copied metadata space");
    const auto old_lease = check_metadata(resolve(old, old_epoch, 0, url), file->data.size());
    const auto lease = check_metadata(resolve(prospective, next_epoch, 0, url), file->data.size());
    require(lease != old_lease, "different resource contexts reused a live lease");
    require(f.call_as(FOUNDATION_ENGINE_RESOURCE_READ, prospective,
        read_payload(lease, 0, static_cast<std::uint32_t>(file->data.size())), 0,
        receipt_bytes + file->data.size() - 1).transport == FOUNDATION_ENGINE_REPLY_TOO_SMALL,
        "resource read partially copied into insufficient complete reply space");
    const auto whole = f.call_as(FOUNDATION_ENGINE_RESOURCE_READ, prospective,
        read_payload(lease, 0, static_cast<std::uint32_t>(file->data.size())));
    const auto prefix = f.call_as(FOUNDATION_ENGINE_RESOURCE_READ, prospective, read_payload(lease, 0, 7));
    const auto suffix = f.call_as(FOUNDATION_ENGINE_RESOURCE_READ, prospective,
        read_payload(lease, 7, static_cast<std::uint32_t>(file->data.size() - 7)));
    auto chunks = prefix.data();
    append(chunks, suffix.data());
    require(whole.ok() && whole.data() == file->data && prefix.ok() && suffix.ok() && chunks == file->data,
        "resource read did not copy exact immutable Package bytes in bounded chunks");
    require(f.call_as(FOUNDATION_ENGINE_RESOURCE_READ, prospective,
        read_payload(lease, 0, FOUNDATION_ENGINE_MAX_BODY_BYTES + 1)).control == FOUNDATION_ENGINE_LIMIT &&
        !f.call_as(FOUNDATION_ENGINE_RESOURCE_READ, prospective, read_payload(lease, file->data.size(), 1)).ok(),
        "resource read accepted an oversized chunk or a range beyond its leased body");
    const auto head_lease = check_metadata(resolve(prospective, next_epoch, 1, url), 0);
    require(f.call_as(FOUNDATION_ENGINE_RESOURCE_READ, prospective, read_payload(head_lease, 0, 0)).ok() &&
        !f.call_as(FOUNDATION_ENGINE_RESOURCE_READ, prospective, read_payload(head_lease, 0, 1)).ok() &&
        f.call_as(FOUNDATION_ENGINE_RESOURCE_RELEASE, prospective, scalar(head_lease, 8)).ok(),
        "HEAD lease exposed a body or could not be released");
    const auto query_lease = check_metadata(resolve(prospective, next_epoch, 0, url + "?cache=1#section"), file->data.size());
    require(f.call_as(FOUNDATION_ENGINE_RESOURCE_RELEASE, prospective, scalar(query_lease, 8)).ok(),
        "canonical query/fragment lookup lease could not be released");
    for (const auto& rejected : std::vector<std::string>{"https://example.invalid/web/index.html",
            "app://" + std::string(64, '2') + "/web/index.html",
            "app://" + f.owner->package().package_sha256 + "/web%2findex.html"}) {
        const auto refused = resolve(prospective, next_epoch, 0, rejected).data();
        require(get(refused, 0, 4) == 403 && get(refused, 8, 8) == 0 && get(refused, 24, 8) == 0,
            "resource owner accepted an external/foreign origin or encoded path separator");
    }
    require(f.call_as(FOUNDATION_ENGINE_RETIRE_RESOURCE_EPOCH, old, scalar(old_epoch, 8)).ok() &&
        get(resolve(old, old_epoch, 0, url).data(), 0, 4) == 410 &&
        f.call_as(FOUNDATION_ENGINE_RESOURCE_READ, old, read_payload(old_lease, 0, 7)).data() ==
            Bytes(file->data.begin(), file->data.begin() + 7),
        "retiring a resource epoch admitted new resolves or invalidated an outstanding lease");
    f.begin(2);
    require(f.call_as(FOUNDATION_ENGINE_CLOSE_DOCUMENT, old).control == FOUNDATION_ENGINE_STALE &&
        f.call_as(FOUNDATION_ENGINE_RESOURCE_READ, old, read_payload(old_lease, 0, 7)).ok() &&
        f.call_as(FOUNDATION_ENGINE_RESOURCE_RELEASE, old, scalar(old_lease, 8)).ok() &&
        !f.call_as(FOUNDATION_ENGINE_RESOURCE_RELEASE, old, scalar(old_lease, 8)).ok(),
        "service-document pruning lost an old resource lease or allowed duplicate release");
    const auto reclaimed = f.call_as(FOUNDATION_ENGINE_BEGIN_RESOURCE_EPOCH, third);
    require(reclaimed.ok() && f.call_as(FOUNDATION_ENGINE_RETIRE_RESOURCE_EPOCH, third,
        scalar(get(reclaimed.data(), 0, 8), 8)).ok(), "last old lease release did not reclaim its resource context");
    const auto closing = f.call(FOUNDATION_ENGINE_CLOSE);
    require(closing.control == FOUNDATION_ENGINE_OK && closing.service == ServiceStatus::unavailable && !f.owner->closed(),
        "close claimed completion while a copied resource lease remained live");
    require(f.call_as(FOUNDATION_ENGINE_RESOURCE_RELEASE, f.current, scalar(lease, 8)).ok() && f.owner->closed(),
        "final resource release after close could not finish the owner lifecycle");
}

void resource_adoption_requires_initial_native_turn() {
    EngineOwnerConfiguration config;
    config.worker_epoch = worker_epoch;
    EngineOwner owner(trusted_package(), config);
    const EngineIdentity initial{worker_epoch, 0, 0, 0};
    const EngineIdentity prospective{worker_epoch, 42, 1, 0};
    const auto call = [&](std::uint32_t operation, EngineIdentity identity, const Bytes& payload = {}) {
        return dispatch(owner, operation, bridge_record(operation, identity, payload));
    };
    require(call(FOUNDATION_ENGINE_CONFIGURE, initial).ok(), "zero-instance owner configuration");
    require(call(FOUNDATION_ENGINE_TURN_ENTER, prospective).control == FOUNDATION_ENGINE_STALE &&
        call(FOUNDATION_ENGINE_BEGIN_RESOURCE_EPOCH, prospective).control == FOUNDATION_ENGINE_STALE &&
        owner.identity() == initial, "outer caller adopted an application outside an initial native callback");
    require(call(FOUNDATION_ENGINE_TURN_ENTER, initial).ok() && owner.callback_depth() == 1,
        "initial native callback guard could not enter before application adoption");
    const auto resource = call(FOUNDATION_ENGINE_BEGIN_RESOURCE_EPOCH, prospective);
    require(resource.ok() && resource.identity == prospective && get(resource.data(), 0, 8) != 0 &&
        owner.identity().application_instance == prospective.application_instance &&
        owner.identity().document_sequence == 0 && owner.identity().service_generation == 0,
        "resource adoption fabricated a ready service document");
    auto foreign = prospective;
    ++foreign.application_instance;
    auto envelope_identity = prospective;
    envelope_identity.service_generation = 1; // v1 envelopes themselves forbid generation zero.
    require(call(FOUNDATION_ENGINE_BEGIN_RESOURCE_EPOCH, foreign).control == FOUNDATION_ENGINE_STALE &&
        call(FOUNDATION_ENGINE_SUBMIT, prospective,
            service_request(envelope_identity, 1, 0, FOUNDATION_APPENDED_CONTROL_DISCOVER, discovery())).control == FOUNDATION_ENGINE_STALE,
        "resource adoption allowed a different application or granted generation-zero service authority");
    require(call(FOUNDATION_ENGINE_TURN_LEAVE, initial).ok() && owner.callback_depth() == 0 &&
        call(FOUNDATION_ENGINE_TURN_ENTER, prospective).ok() && owner.callback_depth() == 1,
        "an admitted prospective resource context could not resume its asynchronous startup turn");
    const auto ready = call(FOUNDATION_ENGINE_BEGIN_DOCUMENT, prospective);
    require(ready.ok() && ready.identity.application_instance == prospective.application_instance &&
        ready.identity.document_sequence == prospective.document_sequence && ready.identity.service_generation != 0,
        "adopted native document did not receive an actual service generation");
    require(call(FOUNDATION_ENGINE_TURN_LEAVE, prospective).ok() && owner.callback_depth() == 0 &&
        owner.identity() == ready.identity, "initial native guard could not leave using its exact pre-adoption identity");
}

Bytes frame_payload(std::uint64_t base, std::uint64_t revision, bool opaque = true) {
    constexpr std::uint32_t width = 800, height = 600, stride = width * 4;
    Bytes result(48 + std::size_t(stride) * height, 0);
    put(result, 0, 1, 4); put(result, 4, width, 4); put(result, 8, height, 4);
    put(result, 12, stride, 4); put(result, 24, width, 4); put(result, 28, height, 4);
    put(result, 32, base, 8); put(result, 40, revision, 8);
    for (std::size_t offset = 48; offset != result.size(); offset += 4) {
        result[offset] = 7; result[offset + 1] = 11; result[offset + 2] = 13;
        result[offset + 3] = 255;
    }
    if (!opaque) result.back() = 254;
    return result;
}

void opaque_frame_revision_and_document_guards() {
    Fixture f;
    f.boot();
    f.enter();
    require(!f.call(FOUNDATION_ENGINE_FRAME_COMMIT, frame_payload(0, 1, false)).ok() && !f.owner->frame(),
        "transparent RGBA frame was silently accepted by the RGB output route");
    require(!f.call(FOUNDATION_ENGINE_FRAME_COMMIT, frame_payload(9, 1)).ok() && !f.owner->frame(),
        "initial frame accepted an unknown base revision");
    require(f.call(FOUNDATION_ENGINE_FRAME_COMMIT, frame_payload(0, 1)).ok(),
        "complete opaque fixed-viewport frame was not staged in its native callback");
    f.leave();
    require(f.owner->frame() && f.owner->frame()->identity == f.current && f.owner->frame()->width == 800 &&
        f.owner->frame()->height == 600 && f.owner->frame()->stride == 3200 &&
        f.owner->frame()->frame_revision == 1 && f.owner->frame()->rgba.size() == 800 * 600 * 4 &&
        f.owner->frame()->rgba.front() == 7 && f.owner->frame()->rgba.back() == 255,
        "accepted owned frame lost its complete raster or document identity");
    require(!f.call(FOUNDATION_ENGINE_FRAME_COMMIT, frame_payload(7, 2)).ok() &&
        f.owner->frame()->frame_revision == 1, "mismatched delta base replaced the accepted frame");
    Bytes delta(52);
    put(delta, 0, 1, 4); put(delta, 4, 800, 4); put(delta, 8, 600, 4); put(delta, 12, 4, 4);
    put(delta, 16, 1, 4); put(delta, 20, 2, 4); put(delta, 24, 1, 4); put(delta, 28, 1, 4);
    put(delta, 32, 1, 8); put(delta, 40, 2, 8);
    delta[48] = 31; delta[49] = 37; delta[50] = 41; delta[51] = 255;
    require(f.call(FOUNDATION_ENGINE_FRAME_COMMIT, delta).ok() && f.owner->frame()->frame_revision == 2 &&
        f.owner->frame()->rgba[(2 * 800 + 1) * 4] == 31 && f.owner->frame()->rgba.front() == 7,
        "accepted damage did not update its exact rectangle in the retained complete raster");
    const auto old = f.current;
    f.begin(2);
    require(!f.owner->frame() && !f.call_as(FOUNDATION_ENGINE_FRAME_COMMIT, old, frame_payload(0, 2)).ok(),
        "navigation preserved an old raster or accepted a stale document frame");
}

void startup_policy_precedes_optional_module_initialization() {
    auto package = trusted_package();
    package.binary = {true, "binary/application.wasm", "foundation-guest-v1"};
    // Deliberately invalid module bytes: every policy rejection must occur
    // before construction/initialization of the actual optional interpreter.
    package.files.insert(package.files.begin(), {"binary/application.wasm", "binary", "application/wasm",
        std::string(64, '4'), Bytes{1, 2, 3}});
    auto rejects = [&](Package candidate, EngineOwnerConfiguration config, std::string_view diagnostic) {
        try { EngineOwner owner(std::move(candidate), std::move(config)); }
        catch (const std::invalid_argument& error) {
            require(std::string_view(error.what()).find(diagnostic) != std::string_view::npos,
                "startup policy failed after or outside its expected admission check");
            return;
        }
        throw std::runtime_error("invalid rich startup reached optional Module initialization");
    };
    for (const auto name : {"foundation.view", "foundation.view.v1"}) {
        auto candidate = package;
        candidate.services.emplace_back(name);
        rejects(candidate, {}, "foundation.view");
        candidate = package;
        candidate.capabilities.emplace_back(name);
        rejects(candidate, {}, "foundation.view");
    }
    auto candidate = package;
    candidate.files.push_back({"web/.FOUNDATION/extra.json", "web", "application/json", std::string(64, '5'), {}});
    std::sort(candidate.files.begin(), candidate.files.end(), [](const auto& a, const auto& b) { return a.path < b.path; });
    rejects(candidate, {}, "reserved");
    EngineOwnerConfiguration invalid_limits;
    invalid_limits.services.max_retained_calls = 0;
    rejects(package, invalid_limits, "limits");
    invalid_limits = {};
    invalid_limits.services.max_message_bytes = FOUNDATION_APPENDED_ENVELOPE_BYTES;
    rejects(package, invalid_limits, "limits");
}
} // namespace

int main() {
    try {
        exact_abi_and_capacity_before_effects();
        callback_depth_and_native_reentry();
        retained_delivery_rejection_retry_and_stale_tokens();
        staged_ack_barrier_and_receipt_retention();
        actual_module_provider_survives_document_navigation();
        retired_outcomes_require_exact_owner_audit_before_document_disposal();
        retirement_drain_remains_bounded_across_many_navigations();
        pending_page_transactions_convert_to_owner_audit();
        actual_module_outcome_abandonment_preserves_provider_owner();
        retirement_clears_empty_ack_intents_and_audits_lowest_retained_sequence();
        actual_module_uncertain_outcome_is_audited_without_reexecution();
        navigation_retires_queue_and_rejects_stale_authority();
        resource_epochs_copied_reads_and_close_retirement();
        resource_adoption_requires_initial_native_turn();
        opaque_frame_revision_and_document_guards();
        startup_policy_precedes_optional_module_initialization();
        std::cout << "Appended engine owner checks passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Appended engine owner check failed: " << error.what() << '\n';
        return 1;
    }
}
