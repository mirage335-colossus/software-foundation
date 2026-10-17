#include "foundation/appended/module.hpp"
#include "foundation/appended/providers.hpp"

#include <algorithm>
#include <array>
#include <fstream>
#include <functional>
#include <iostream>
#include <iterator>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>

using namespace foundation::appended;
namespace {
void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
struct OwnedField { std::uint16_t id; FieldType type; Bytes bytes; };
Bytes record(std::initializer_list<OwnedField> fields) {
    std::vector<FieldView> views;
    for (const auto& item : fields) views.push_back({item.id, item.type, true, item.bytes});
    Bytes bytes;
    require(encode_record(views, bytes) == CodecStatus::ok, "fixture record encoding");
    return bytes;
}
Bytes text(std::string_view value) { return {value.begin(), value.end()}; }
const SchemaId& contract_schema() {
    // SHA-256 of provider_fixtures/contract.txt, shared by real C/C++/Rust fixtures.
    static constexpr SchemaId value{0x3f,0xe7,0xab,0x0d,0x3f,0x8f,0x76,0x49,
        0x9f,0x05,0x4c,0xa6,0xf2,0x9f,0x68,0xde,0xee,0x28,0x62,0x76,0x81,0xf7,
        0x92,0x31,0xaf,0x3b,0x09,0x5b,0x06,0x35,0xb2,0x46};
    return value;
}
std::uint32_t u32(std::span<const std::uint8_t> bytes) {
    require(bytes.size() == 4, "expected four-byte integer");
    return std::uint32_t(bytes[0]) | (std::uint32_t(bytes[1]) << 8) |
        (std::uint32_t(bytes[2]) << 16) | (std::uint32_t(bytes[3]) << 24);
}
void increment_result(const ProviderOutcome& value, std::uint32_t result, std::uint32_t count) {
    require(value.status == ServiceStatus::ok && value.payload.size() == 8, "increment response status/size");
    require(u32(std::span<const std::uint8_t>(value.payload).first(4)) == result &&
        u32(std::span<const std::uint8_t>(value.payload).subspan(4)) == count,
        "increment response value/count");
}
Bytes envelope(std::uint64_t sequence, std::uint64_t handle, std::uint32_t operation,
               const Bytes& payload = {}, std::uint64_t generation = 7) {
    Envelope header; header.generation = generation; header.sequence = sequence;
    header.interface_handle = handle; header.operation = operation;
    Bytes bytes;
    require(encode_envelope(header, payload, bytes) == CodecStatus::ok, "fixture envelope encoding");
    return bytes;
}
struct Exchange { TransportStatus transport; ServiceStatus status; Bytes payload; };
Exchange exchange(Registry& registry, std::uint64_t sequence, std::uint64_t handle,
                  std::uint32_t operation, const Bytes& payload = {}, std::uint64_t generation = 7) {
    const auto request = envelope(sequence, handle, operation, payload, generation);
    Bytes memory(4096);
    std::copy(request.begin(), request.end(), memory.begin());
    const auto transport = registry.call(memory, 0, static_cast<std::uint32_t>(request.size()), 2048, 1024);
    if (transport != TransportStatus::ok) return {transport, ServiceStatus::internal_error, {}};
    const auto size = u32(std::span<const std::uint8_t>(memory).subspan(2048, 4));
    require(size <= 1024, "gateway reply exceeded capacity");
    Envelope reply; std::span<const std::uint8_t> bytes;
    require(decode_envelope(std::span<const std::uint8_t>(memory).subspan(2048, size), reply, bytes) == CodecStatus::ok,
        "gateway emitted invalid envelope");
    return {transport, static_cast<ServiceStatus>(reply.service_status), {bytes.begin(), bytes.end()}};
}
Bytes registration(std::string_view name = "org.example.increment", std::uint32_t major = 1,
                   std::uint32_t minor = 0, SchemaId schema = contract_schema(),
                   std::uint32_t request_bytes = 4, std::uint32_t reply_bytes = 8) {
    return record({{1,FieldType::utf8,text(name)}, {2,FieldType::u32,encode_u32(major)},
        {3,FieldType::u32,encode_u32(minor)}, {4,FieldType::bytes,Bytes(schema.begin(), schema.end())},
        {5,FieldType::u32,encode_u32(request_bytes)}, {6,FieldType::u32,encode_u32(reply_bytes)}});
}
Bytes discovery(std::string_view name = "org.example.increment", std::uint32_t minimum = 0,
                std::uint32_t maximum = 0) {
    return record({{1,FieldType::utf8,text(name)}, {2,FieldType::u32,encode_u32(1)},
        {3,FieldType::u32,encode_u32(minimum)}, {4,FieldType::u32,encode_u32(maximum)}});
}

// This assembler emits a real foundation-guest-v1 module. Its only import is
// the real gateway; registration, nested native work and responses execute in
// the interpreter. No native stand-in implements a guest export.
void uleb(Bytes& bytes, std::uint32_t value) {
    do {
        const auto next = static_cast<std::uint8_t>(value & 127u); value >>= 7;
        bytes.push_back(static_cast<std::uint8_t>(next | (value ? 128u : 0u)));
    } while (value);
}
void constant(Bytes& bytes, std::int32_t value) {
    bytes.push_back(0x41);
    bool more;
    do {
        const auto next = static_cast<std::uint8_t>(value & 127); value >>= 7;
        more = !((value == 0 && !(next & 64)) || (value == -1 && (next & 64)));
        bytes.push_back(static_cast<std::uint8_t>(next | (more ? 128u : 0u)));
    } while (more);
}
void append(Bytes& to, const Bytes& from) { to.insert(to.end(), from.begin(), from.end()); }
void name(Bytes& bytes, std::string_view value) {
    uleb(bytes, static_cast<std::uint32_t>(value.size())); bytes.insert(bytes.end(), value.begin(), value.end());
}
void section(Bytes& bytes, std::uint8_t id, const Bytes& content) {
    bytes.push_back(id); uleb(bytes, static_cast<std::uint32_t>(content.size())); append(bytes, content);
}
void load32(Bytes& code, std::uint32_t address) {
    constant(code, static_cast<std::int32_t>(address)); append(code, {0x28,2,0});
}
void store32(Bytes& code, std::uint32_t address, std::uint32_t value) {
    constant(code, static_cast<std::int32_t>(address)); constant(code, static_cast<std::int32_t>(value));
    append(code, {0x36,2,0});
}
void copy64(Bytes& code, std::uint32_t destination, std::uint32_t source) {
    constant(code, static_cast<std::int32_t>(destination)); constant(code, static_cast<std::int32_t>(source));
    append(code, {0x29,3,0,0x37,3,0});
}
void event64(Bytes& code, std::uint32_t destination, std::uint32_t offset) {
    constant(code, static_cast<std::int32_t>(destination)); append(code, {0x20,0,0x29,3});
    uleb(code, offset); append(code, {0x37,3,0});
}
void trap_if(Bytes& code) { append(code, {0x04,0x40,0x00,0x0b}); }
constexpr std::uint32_t sequence_address = 128, count_address = 136, free_armed = 144, last_event_address = 160;
constexpr std::uint32_t control_address = 152, response_address = 2048, error_address = 2176;
constexpr std::uint32_t native_address = 2304, ack_address = 2560, reply_address = 8192;
void next_sequence(Bytes& code, std::uint32_t packet) {
    constant(code, sequence_address); constant(code, sequence_address);
    append(code, {0x29,3,0,0x42,1,0x7c,0x37,3,0});
    copy64(code, packet + FOUNDATION_APPENDED_OFFSET_SEQUENCE, sequence_address);
}
void gateway(Bytes& code, std::uint32_t packet, std::size_t bytes, int expected = 0,
             bool new_sequence = true) {
    if (new_sequence) next_sequence(code, packet);
    constant(code, static_cast<std::int32_t>(packet)); constant(code, static_cast<std::int32_t>(bytes));
    constant(code, reply_address); constant(code, 512); append(code, {0x10,0}); trap_if(code);
    if (expected >= 0) {
        load32(code, reply_address + FOUNDATION_APPENDED_OFFSET_STATUS); constant(code, expected);
        code.push_back(0x47); trap_if(code);
    }
}
void acknowledge_gateway(Bytes& code, std::size_t bytes) {
    copy64(code, ack_address + 72, sequence_address);
    gateway(code, ack_address, bytes);
}
enum class Behavior { normal, missing, duplicate, retry, wrong_token, wrong_provider,
    response_trap, dispatch_failure, free_trap, oversized, error_payload, result_available, malformed_response };
struct Registration { Bytes payload{registration()}; ServiceStatus expected{ServiceStatus::ok}; };
struct Options {
    Behavior behavior{Behavior::normal};
    std::vector<Registration> registrations{{}};
    std::uint64_t native_handle{0};
    bool step_native{false};
};
Bytes fixture(const Options& options = {}) {
    const auto find_control = envelope(1, 0, FOUNDATION_APPENDED_CONTROL_DISCOVER,
        discovery(FOUNDATION_PROVIDER_SERVICE_NAME));
    const auto ack = envelope(1, 0, FOUNDATION_APPENDED_CONTROL_ACKNOWLEDGE,
        record({{1,FieldType::u64,encode_u64(1)}}));
    const auto response = [&](ServiceStatus status, std::size_t bytes) {
        return envelope(1, 1, FOUNDATION_PROVIDER_RESPOND, record({
            {1,FieldType::u64,encode_u64(1)}, {2,FieldType::u64,encode_u64(1)},
            {3,FieldType::u32,encode_u32(static_cast<std::uint32_t>(status))},
            {4,FieldType::bytes,Bytes(bytes)}}));
    };
    const auto response_bytes = response(ServiceStatus::ok, options.behavior == Behavior::oversized ? 9 : 8);
    const auto error_bytes = response(ServiceStatus::unknown_operation, 0);
    const auto native = envelope(1, options.native_handle, 1);
    std::vector<std::pair<std::uint32_t,Bytes>> data{{256,find_control}, {response_address,response_bytes},
        {error_address,error_bytes}, {native_address,native}, {ack_address,ack}};
    std::array<Bytes,7> code;
    constant(code[0], FOUNDATION_APPENDED_ABI_VERSION);
    constant(code[1], 16384);
    if (options.behavior == Behavior::free_trap) { load32(code[2], free_armed); trap_if(code[2]); }
    gateway(code[3], 256, find_control.size());
    copy64(code[3], control_address, reply_address + 72);
    acknowledge_gateway(code[3], ack.size());
    for (std::size_t n = 0; n < options.registrations.size(); ++n) {
        const auto address = 4096 + static_cast<std::uint32_t>(n * 256);
        auto packet = envelope(1, 1, FOUNDATION_PROVIDER_REGISTER, options.registrations[n].payload);
        copy64(code[3], address + FOUNDATION_APPENDED_OFFSET_INTERFACE, control_address);
        gateway(code[3], address, packet.size(), static_cast<int>(options.registrations[n].expected));
        acknowledge_gateway(code[3], ack.size());
        data.emplace_back(address, std::move(packet));
    }
    constant(code[3], 0);
    auto& dispatch = code[4];
    // Empty ordinary dispatch is independent of provider dispatch.
    append(dispatch, {0x20,1}); constant(dispatch, 100); append(dispatch, {0x49,0x04,0x40});
    constant(dispatch, 0); append(dispatch, {0x0f,0x0b});
    for (const auto& [offset, value] : std::array<std::pair<std::uint32_t,std::uint32_t>,3>{{
            {FOUNDATION_APPENDED_OFFSET_KIND,FOUNDATION_APPENDED_MESSAGE_EVENT},
            {FOUNDATION_APPENDED_OFFSET_OPERATION,FOUNDATION_PROVIDER_EVENT_CALL},
            {FOUNDATION_APPENDED_OFFSET_GENERATION,7}}}) {
        append(dispatch, {0x20,0,0x28,2}); uleb(dispatch,offset); constant(dispatch,static_cast<std::int32_t>(value));
        dispatch.push_back(0x47); trap_if(dispatch);
    }
    append(dispatch, {0x20,0,0x29,3,FOUNDATION_APPENDED_OFFSET_INTERFACE});
    constant(dispatch,control_address); append(dispatch,{0x29,3,0,0x52}); trap_if(dispatch);
    append(dispatch,{0x20,0,0x29,3,FOUNDATION_APPENDED_OFFSET_CORRELATION,0x50}); trap_if(dispatch);
    append(dispatch,{0x20,0,0x29,3,FOUNDATION_APPENDED_OFFSET_SEQUENCE});
    constant(dispatch,last_event_address); append(dispatch,{0x29,3,0,0x58}); trap_if(dispatch);
    event64(dispatch,last_event_address,FOUNDATION_APPENDED_OFFSET_SEQUENCE);
    copy64(dispatch, response_address + FOUNDATION_APPENDED_OFFSET_INTERFACE, control_address);
    copy64(dispatch, error_address + FOUNDATION_APPENDED_OFFSET_INTERFACE, control_address);
    event64(dispatch, response_address + 72, FOUNDATION_APPENDED_OFFSET_CORRELATION);
    event64(dispatch, response_address + 88, 72);
    event64(dispatch, error_address + 72, FOUNDATION_APPENDED_OFFSET_CORRELATION);
    event64(dispatch, error_address + 88, 72);
    append(dispatch, {0x20,0,0x28,2,88}); constant(dispatch, 1); append(dispatch, {0x47,0x04,0x40});
    gateway(dispatch, error_address, error_bytes.size()); acknowledge_gateway(dispatch, ack.size());
    constant(dispatch, 0); append(dispatch, {0x0f,0x0b});
    constant(dispatch, count_address); load32(dispatch, count_address); constant(dispatch, 1);
    append(dispatch, {0x6a,0x36,2,0});
    if (options.native_handle) {
        gateway(dispatch, native_address, native.size()); acknowledge_gateway(dispatch, ack.size());
    }
    constant(dispatch, response_address + 116); append(dispatch, {0x20,0,0x28,2,100});
    constant(dispatch, 1); append(dispatch, {0x6a,0x36,2,0});
    constant(dispatch, response_address + 120); load32(dispatch, count_address); append(dispatch, {0x36,2,0});
    if (options.behavior == Behavior::wrong_token || options.behavior == Behavior::wrong_provider) {
        const auto address = response_address + (options.behavior == Behavior::wrong_token ? 72 : 88);
        constant(dispatch, static_cast<std::int32_t>(address)); constant(dispatch, static_cast<std::int32_t>(address));
        append(dispatch, {0x29,3,0,0x42,1,0x7c,0x37,3,0});
        gateway(dispatch, response_address, response_bytes.size(), static_cast<int>(ServiceStatus::invalid_handle));
        acknowledge_gateway(dispatch, ack.size());
        event64(dispatch, address, options.behavior == Behavior::wrong_token ? FOUNDATION_APPENDED_OFFSET_CORRELATION : 72);
    }
    if (options.behavior == Behavior::error_payload)
        store32(dispatch, response_address + 104, static_cast<std::uint32_t>(ServiceStatus::invalid_request));
    if (options.behavior == Behavior::result_available)
        store32(dispatch, response_address + 104, static_cast<std::uint32_t>(ServiceStatus::result_available));
    if (options.behavior == Behavior::malformed_response) store32(dispatch, response_address + 64, 0);
    if (options.behavior != Behavior::missing) {
        const bool invalid = options.behavior == Behavior::oversized || options.behavior == Behavior::error_payload ||
            options.behavior == Behavior::result_available || options.behavior == Behavior::malformed_response;
        gateway(dispatch, response_address, response_bytes.size(), invalid ? -1 : 0);
        if (options.behavior == Behavior::retry)
            gateway(dispatch, response_address, response_bytes.size(), 0, false);
        acknowledge_gateway(dispatch, ack.size());
        if (options.behavior == Behavior::duplicate)
            gateway(dispatch, response_address, response_bytes.size(), -1);
    }
    if (options.behavior == Behavior::response_trap) dispatch.push_back(0x00);
    if (options.behavior == Behavior::free_trap) store32(dispatch, free_armed, 1);
    constant(dispatch, options.behavior == Behavior::dispatch_failure ? 1 : 0);
    if (options.step_native) { gateway(code[5], native_address, native.size()); acknowledge_gateway(code[5], ack.size()); }
    constant(code[5], 0);
    Bytes module{0,97,115,109,1,0,0,0};
    section(module, 1, {6,0x60,4,0x7f,0x7f,0x7f,0x7f,1,0x7f,
        0x60,0,1,0x7f,0x60,1,0x7f,1,0x7f,0x60,2,0x7f,0x7f,0,
        0x60,2,0x7f,0x7f,1,0x7f,0x60,1,0x7f,0});
    Bytes imports{1}; name(imports, FOUNDATION_APPENDED_IMPORT_MODULE);
    name(imports, FOUNDATION_APPENDED_IMPORT_NAME); append(imports, {0,0}); section(module, 2, imports);
    section(module, 3, {7,1,2,3,4,4,2,5}); section(module, 5, {1,1,1,1});
    Bytes exports{8}; name(exports, "memory"); append(exports, {2,0});
    constexpr std::array names{"foundation_app_abi_v1","foundation_app_alloc_v1","foundation_app_free_v1",
        "foundation_app_init_v1","foundation_app_dispatch_v1","foundation_app_step_v1","foundation_app_shutdown_v1"};
    for (std::size_t n = 0; n < names.size(); ++n) { name(exports,names[n]); exports.push_back(0); uleb(exports,static_cast<std::uint32_t>(n + 1)); }
    section(module, 7, exports);
    Bytes bodies{7};
    for (auto& instructions : code) {
        Bytes body{0}; append(body,instructions); body.push_back(0x0b);
        uleb(bodies,static_cast<std::uint32_t>(body.size())); append(bodies,body);
    }
    section(module, 10, bodies);
    Bytes segments; uleb(segments,static_cast<std::uint32_t>(data.size()));
    for (const auto& [address, bytes] : data) {
        segments.push_back(0); constant(segments,static_cast<std::int32_t>(address)); segments.push_back(0x0b);
        uleb(segments,static_cast<std::uint32_t>(bytes.size())); append(segments,bytes);
    }
    section(module, 11, segments); return module;
}
struct Harness {
    Registry registry{7};
    unsigned effects{0};
    std::uint64_t native_handle{0};
    std::function<void()> callback;
    std::unique_ptr<Module> module;
    std::unique_ptr<ModuleProviders> providers;
    explicit Harness(Options options = {}, ProviderLimits limits = {}, ModuleProviders::EventSequence events = {},
                     Limits registry_limits = {}) : registry(7,registry_limits) {
        const auto native = registry.register_service({"org.example.effects",1,0,contract_schema(),0},
            [this](auto, auto, auto) {
                ++effects; if (callback) callback(); return ServiceReply{};
            });
        require(native.status == ServiceStatus::ok, "native fixture registration");
        native_handle = native.handle; options.native_handle = native.handle;
        module = std::make_unique<Module>(fixture(options),registry);
        providers = std::make_unique<ModuleProviders>(*module,registry,std::move(events),limits);
    }
    void start() {
        require(!module->initialized() && !module->initializing() && !module->invocation_active(), "module initial state");
        require(module->initialize() == 0, "provider guest initialization");
        require(module->initialized() && !module->initializing() && !module->invocation_active(), "module ready state");
        require(providers->activate() == ServiceStatus::ok, "provider activation");
    }
    ProviderDiscovery find() const {
        return providers->discover({"org.example.increment",1,0,0,contract_schema()});
    }
    ProviderRequest request(std::uint64_t sequence = 1, std::uint32_t operand = 41) const {
        const auto provider = find(); require(provider.status == ServiceStatus::ok && provider.handle != 0, "provider discovery");
        return {7,sequence,provider.handle,1,encode_u32(operand)};
    }
};
void success_and_replay() {
    Harness h; h.start();
    require(h.providers->provider_count() == 1 && h.module->uses_registry(h.registry), "provider ownership/count");
    require(h.module->dispatch({}) == 0, "ordinary empty dispatch");
    const auto request = h.request();
    increment_result(h.providers->invoke(request),42,1);
    increment_result(h.providers->invoke(request),42,1);
    require(h.effects == 1 && h.providers->retained_call_count() == 1, "identical host retry repeated guest effect");
    auto conflict = request; conflict.payload = encode_u32(99);
    require(h.providers->invoke(conflict).status == ServiceStatus::conflict && h.effects == 1, "conflicting host retry ran guest");
    increment_result(h.providers->invoke(h.request(3,99)),100,2);
    auto skipped = request; skipped.sequence = 2;
    require(h.providers->invoke(skipped).status == ServiceStatus::expired && h.effects == 2, "skipped old host id executed");
    require(h.providers->acknowledge(4) == ServiceStatus::invalid_request, "ACK crossed admitted calls");
    require(h.providers->acknowledge(3) == ServiceStatus::ok && h.providers->retained_call_count() == 0, "host ACK did not retire calls");
    require(h.providers->invoke(request).status == ServiceStatus::expired && h.effects == 2, "ACKed call executed again");
    auto unknown = h.request(4); unknown.operation = 999;
    const auto error = h.providers->invoke(unknown);
    require(error.status == ServiceStatus::unknown_operation && error.payload.empty() && h.effects == 2 && !h.providers->closed(),
        "explicit provider error closed bridge or caused effect");
    auto stale = h.request(5); stale.generation = 8;
    require(h.providers->invoke(stale).status != ServiceStatus::ok && h.effects == 2, "stale generation invoked guest");
    stale = h.request(5); ++stale.provider;
    require(h.providers->invoke(stale).status == ServiceStatus::invalid_handle && h.effects == 2, "stale provider handle invoked guest");
    auto oversized = h.request(5); oversized.payload.push_back(0);
    require(h.providers->invoke(oversized).status != ServiceStatus::ok && h.effects == 2, "oversized request had effects");
    const auto last = h.request(5);
    increment_result(h.providers->invoke(last),42,3);
    h.providers->close();
    require(h.providers->closed() && h.providers->provider_count() == 0, "close retained routes");
    increment_result(h.providers->invoke(last),42,3);
}
void registration_and_discovery() {
    Options options; options.registrations.clear();
    auto other = contract_schema(); other[0] ^= 1;
    auto optional = registration("org.example.optional");
    const FieldView unknown_optional{7,FieldType::bytes,false,{}};
    Bytes tail; require(encode_record(std::span(&unknown_optional,1),tail) == CodecStatus::ok,"optional fixture field");
    append(optional,tail);
    auto required = registration("org.example.required"); tail[3] = 1; append(required,tail);
    auto flags = registration("org.example.flags"); flags[3] = 0;
    auto missing = registration("org.example.missing"); missing.resize(missing.size() - 12);
    options.registrations = {{registration("foundation.private"),ServiceStatus::invalid_request},
        {registration("unnamespaced"),ServiceStatus::invalid_request},
        {registration("org.example.zero",0),ServiceStatus::invalid_request},
        {registration("org.example.version",65536),ServiceStatus::invalid_request},
        {registration("org.example.schema",1,0,SchemaId{}),ServiceStatus::invalid_request},
        {registration("org.example.too.large",1,0,contract_schema(),FOUNDATION_PROVIDER_MAX_PAYLOAD_BYTES + 1),ServiceStatus::limit_exceeded},
        {std::move(flags),ServiceStatus::invalid_request}, {std::move(missing),ServiceStatus::invalid_request},
        {std::move(required),ServiceStatus::invalid_request}, {std::move(optional),ServiceStatus::ok},
        {registration("org.example.effects"),ServiceStatus::conflict},
        {registration(),ServiceStatus::ok}, {registration(),ServiceStatus::conflict},
        {registration("org.example.increment",1,2,other),ServiceStatus::ok}};
    Harness h(options); h.start();
    require(h.providers->provider_count() == 3, "invalid/duplicate registration changed catalog");
    auto found = h.providers->discover({"org.example.increment",1,0,2,{}});
    require(found.status == ServiceStatus::ok && found.descriptor.contract.minor == 2 &&
        found.descriptor.contract.schema == other, "highest explicit provider minor");
    found = h.providers->discover({"org.example.increment",1,0,2,contract_schema()});
    require(found.status == ServiceStatus::ok && found.descriptor.contract.minor == 0 &&
        found.descriptor.max_request_bytes == 4 && found.descriptor.contract.max_reply_bytes == 8,
        "old explicit provider schema/bounds");
    other[1] ^= 1;
    require(h.providers->discover({"org.example.increment",1,0,2,other}).status == ServiceStatus::schema_mismatch,
        "provider schema mismatch not distinguished");
    require(h.providers->discover({"org.example.increment",2,0,2,{}}).status == ServiceStatus::unsupported_version,
        "provider major mismatch not distinguished");
    require(h.providers->discover({"org.example.absent",1,0,0,{}}).status == ServiceStatus::not_found, "absent provider discovered");
    const auto wire = exchange(h.registry,1000,h.providers->service_handle(),FOUNDATION_PROVIDER_DISCOVER,discovery("org.example.increment",0,2));
    std::vector<FieldView> fields; std::uint32_t minor = 0;
    require(wire.transport == TransportStatus::ok && wire.status == ServiceStatus::ok &&
        decode_record(wire.payload,fields) == CodecStatus::ok && fields.size() == 7 && read_u32(fields[3],minor) && minor == 2,
        "wire provider discovery disagrees with host catalog");
    const auto late = exchange(h.registry,1001,h.providers->service_handle(),FOUNDATION_PROVIDER_REGISTER,registration("org.example.late"));
    require(late.transport == TransportStatus::ok && late.status == ServiceStatus::invalid_request && h.providers->provider_count() == 3,
        "late registration admitted");
    const auto reply = record({{1,FieldType::u64,encode_u64(1)}, {2,FieldType::u64,encode_u64(found.handle)},
        {3,FieldType::u32,encode_u32(0)}, {4,FieldType::bytes,{}}});
    require(exchange(h.registry,1002,h.providers->service_handle(),FOUNDATION_PROVIDER_RESPOND,reply).status != ServiceStatus::ok,
        "response outside active provider invocation admitted");
}
void response_lifecycle() {
    for (const auto behavior : {Behavior::retry,Behavior::wrong_token,Behavior::wrong_provider}) {
        Options options; options.behavior = behavior; Harness h(options); h.start();
        increment_result(h.providers->invoke(h.request()),42,1);
        require(h.effects == 1 && !h.providers->closed(), "recoverable response rejection poisoned valid response");
    }
    for (const auto behavior : {Behavior::missing,Behavior::duplicate,Behavior::response_trap,
            Behavior::dispatch_failure,Behavior::free_trap,Behavior::oversized,Behavior::error_payload,
            Behavior::result_available,Behavior::malformed_response}) {
        Options options; options.behavior = behavior; Harness h(options); h.start();
        const auto request = h.request(); const auto result = h.providers->invoke(request);
        require(result.status == ServiceStatus::uncertain && result.payload.empty(), "provisional/invalid guest response exposed success");
        require(h.providers->closed() && h.module->closed() && h.registry.closed() && h.effects == 1,
            "terminal provider failure retained live state");
        require(h.providers->invoke(request).status == ServiceStatus::uncertain && h.effects == 1,
            "terminal invocation replay entered guest");
        require(h.providers->acknowledge(1) == ServiceStatus::ok && h.providers->retained_call_count() == 0,
            "terminal retained result could not be acknowledged");
    }
}
void bounded_admission() {
    Limits message_limits; message_limits.max_message_bytes = 320;
    Options registration_limits;
    registration_limits.registrations = {
        {registration("org.example.request.bound",1,0,contract_schema(),221,0),ServiceStatus::limit_exceeded},
        {registration("org.example.reply.bound",1,0,contract_schema(),0,205),ServiceStatus::limit_exceeded},
        {registration(),ServiceStatus::ok}};
    Harness message_bound(registration_limits,{}, {},message_limits); message_bound.start();
    require(message_bound.providers->provider_count() == 1,"registration exceeded gateway message budget");
    ProviderLimits limits; limits.max_retained_calls = 1;
    Harness h({},limits); h.start(); const auto one = h.request();
    increment_result(h.providers->invoke(one),42,1);
    const auto two = h.request(2);
    require(h.providers->invoke(two).status == ServiceStatus::limit_exceeded && h.effects == 1, "full call ledger caused effect");
    increment_result(h.providers->invoke(one),42,1);
    require(h.providers->acknowledge(1) == ServiceStatus::ok, "bounded ACK");
    increment_result(h.providers->invoke(two),42,2);
    limits.max_retained_calls = 64; limits.max_retained_bytes = 12;
    Harness bytes({},limits); bytes.start(); increment_result(bytes.providers->invoke(bytes.request()),42,1);
    require(bytes.providers->invoke(bytes.request(2)).status == ServiceStatus::limit_exceeded && bytes.effects == 1,
        "retained byte budget caused effect before reservation");
    require(bytes.providers->acknowledge(1) == ServiceStatus::ok, "byte reservation ACK");
    increment_result(bytes.providers->invoke(bytes.request(2)),42,2);
}
void invocation_guards_and_shutdown() {
    Options options; options.step_native = true; Harness h(options); h.start();
    const auto request = h.request(); unsigned callbacks = 0;
    h.callback = [&] {
        ++callbacks;
        require(h.module->invocation_active() && h.registry.invocation_active(), "active guest/registry state hidden");
        require(h.providers->invoke(request).status == ServiceStatus::unavailable && h.providers->retained_call_count() == 0,
            "nested provider invocation admitted");
        const auto rejects_recursive_entry = [&](auto entry) {
            bool rejected = false;
            try { entry(); } catch (const std::runtime_error&) { rejected = true; }
            require(rejected && h.module->invocation_active() && !h.module->closed() && !h.registry.closed(),
                "nested public Module rejection destroyed active interpreter");
        };
        rejects_recursive_entry([&] { h.module->initialize(); });
        rejects_recursive_entry([&] { h.module->dispatch({}); });
        rejects_recursive_entry([&] { h.module->step(1); });
    };
    require(h.module->step(1) == 0 && callbacks == 1, "active guest guard fixture");
    h.callback = {};
    increment_result(h.providers->invoke(request),42,1);
    Harness native; native.start(); const auto native_request = native.request();
    native.callback = [&] {
        require(native.registry.invocation_active() && !native.module->invocation_active(), "native callback active state");
        require(native.providers->invoke(native_request).status == ServiceStatus::unavailable &&
            native.providers->retained_call_count() == 0, "Registry callback recursively entered guest");
    };
    require(exchange(native.registry,1000,native.native_handle,1).status == ServiceStatus::ok && native.effects == 1,
        "native callback guard fixture");
    Harness shutting_down; shutting_down.start(); const auto doomed = shutting_down.request();
    shutting_down.callback = [&] { shutting_down.module->shutdown(); };
    require(shutting_down.providers->invoke(doomed).status == ServiceStatus::uncertain &&
        shutting_down.module->closed() && shutting_down.registry.closed() && shutting_down.providers->closed(),
        "nested shutdown left successful/live provider state");
    require(shutting_down.providers->invoke(doomed).status == ServiceStatus::uncertain && shutting_down.effects == 1,
        "nested shutdown replay executed guest");
}
void ownership_and_event_sequences() {
    Harness before;
    require(before.providers->activate() != ServiceStatus::ok, "activation before initialization accepted");
    Registry owner(7), foreign(7);
    Module module(fixture(),owner);
    bool refused = false;
    try {
        ModuleProviders wrong(module,foreign);
        refused = wrong.activate() != ServiceStatus::ok;
    } catch (const std::invalid_argument&) { refused = true; }
    require(refused, "same generation substituted for exact Registry identity");
    Harness collision;
    require(collision.module->initialize() == 0,"late collision initialization");
    require(collision.registry.register_service({"org.example.increment",1,0,contract_schema(),0},
        [](auto,auto,auto) { return ServiceReply{}; }).status == ServiceStatus::ok,"late native collision fixture");
    require(collision.providers->activate() == ServiceStatus::conflict && collision.providers->closed() &&
        collision.module->closed() && collision.registry.closed(),"activation allowed native/module route collision");
    std::uint64_t sequence = 40; unsigned issued = 0;
    Harness ordered({}, {}, [&]() -> std::optional<std::uint64_t> { ++issued; return ++sequence; });
    ordered.start(); const auto request = ordered.request();
    increment_result(ordered.providers->invoke(request),42,1);
    increment_result(ordered.providers->invoke(request),42,1);
    increment_result(ordered.providers->invoke(ordered.request(2)),42,2);
    require(sequence == 42 && issued == 2, "shared outbound event sequence reused or consumed on host retry");
    for (const auto second_sequence : {10u,9u}) {
        unsigned attempts = 0;
        Harness monotone({}, {}, [&]() -> std::optional<std::uint64_t> {
            return attempts++ == 0 ? 10 : second_sequence;
        });
        monotone.start(); const auto first = monotone.request();
        increment_result(monotone.providers->invoke(first),42,1);
        const auto second = monotone.request(2);
        require(monotone.providers->invoke(second).status == ServiceStatus::limit_exceeded && monotone.effects == 1 &&
            monotone.providers->closed() && monotone.module->closed() && monotone.registry.closed() &&
            monotone.providers->retained_call_count() == 1,
            "repeated/decreasing event sequence dispatched or retained new guest work");
        increment_result(monotone.providers->invoke(first),42,1);
        require(monotone.effects == 1 && attempts == 2,"event sequence failure lost cached host result");
    }
    Harness* callback_owner = nullptr;
    Harness reentrant({}, {}, [&]() -> std::optional<std::uint64_t> {
        require(callback_owner != nullptr,"event sequence callback ran during construction");
        require(callback_owner->providers->invoke(callback_owner->request()).status == ServiceStatus::unavailable &&
            callback_owner->providers->acknowledge(0) == ServiceStatus::unavailable &&
            callback_owner->providers->retained_call_count() == 0,
            "event sequence callback reentered provider admission/ACK");
        return 17;
    });
    callback_owner = &reentrant; reentrant.start();
    increment_result(reentrant.providers->invoke(reentrant.request()),42,1);
    require(reentrant.effects == 1 && reentrant.providers->acknowledge(1) == ServiceStatus::ok,
        "event sequence callback guard persisted beyond invocation");
    Harness* closing_owner = nullptr;
    Harness closing({}, {}, [&]() -> std::optional<std::uint64_t> {
        require(closing_owner != nullptr,"closing event callback ran during construction");
        closing_owner->providers->close(); return 23;
    });
    closing_owner = &closing; closing.start(); const auto cancelled = closing.request();
    require(closing.providers->invoke(cancelled).status == ServiceStatus::closed && closing.effects == 0 &&
        closing.providers->retained_call_count() == 0 && closing.providers->closed(),
        "event sequence callback close admitted or dispatched guest work");
    ProviderRequest mutable_request;
    Harness frozen({}, {}, [&]() -> std::optional<std::uint64_t> {
        mutable_request.generation = 8; mutable_request.sequence = 99; mutable_request.provider = 999;
        mutable_request.operation = 999; mutable_request.payload = encode_u32(99); return 31;
    });
    frozen.start(); mutable_request = frozen.request(); const auto original = mutable_request;
    increment_result(frozen.providers->invoke(mutable_request),42,1);
    increment_result(frozen.providers->invoke(original),42,1);
    require(frozen.effects == 1 && frozen.providers->retained_call_count() == 1 &&
        frozen.providers->acknowledge(1) == ServiceStatus::ok &&
        frozen.providers->acknowledge(99) == ServiceStatus::invalid_request,
        "event sequence callback mutated frozen invocation identity/bytes");
    Harness exhausted({}, {}, []() -> std::optional<std::uint64_t> { return {}; }); exhausted.start();
    require(exhausted.providers->invoke(exhausted.request()).status != ServiceStatus::ok && exhausted.effects == 0,
        "exhausted event source entered guest");
    Harness lifetime; lifetime.start(); const auto service = lifetime.providers->service_handle();
    lifetime.providers.reset();
    const auto result = exchange(lifetime.registry,1000,service,FOUNDATION_PROVIDER_DISCOVER,discovery());
    require(result.transport == TransportStatus::ok && result.status == ServiceStatus::closed,
        "Registry callback outlived bridge state unsafely");
    lifetime.module->shutdown();
    require(lifetime.module->closed() && lifetime.registry.closed(), "shutdown after bridge destruction");
    Harness end; end.start(); auto last = end.request(std::numeric_limits<std::uint64_t>::max());
    increment_result(end.providers->invoke(last),42,1); increment_result(end.providers->invoke(last),42,1);
    --last.sequence;
    require(end.providers->invoke(last).status == ServiceStatus::expired && end.effects == 1, "host sequence wrapped after maximum");
}
void external(const char* path) {
    std::ifstream input(path,std::ios::binary); require(bool(input), "cannot read external provider fixture");
    const Bytes bytes{std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
    Registry registry(7); Module module(bytes,registry); ModuleProviders providers(module,registry);
    require(module.initialize() == 0 && providers.activate() == ServiceStatus::ok, "external provider initialization");
    const auto found = providers.discover({"org.example.increment",1,0,0,contract_schema()});
    require(found.status == ServiceStatus::ok && found.descriptor.max_request_bytes == 4 &&
        found.descriptor.contract.max_reply_bytes == 8, "external provider contract discovery");
    ProviderRequest request{7,1,found.handle,1,encode_u32(41)};
    increment_result(providers.invoke(request),42,1); increment_result(providers.invoke(request),42,1);
    request.payload = encode_u32(99);
    require(providers.invoke(request).status == ServiceStatus::conflict, "external conflicting retry");
    request.sequence = 2; increment_result(providers.invoke(request),100,2);
    request.sequence = 3; request.operation = 999;
    const auto error = providers.invoke(request);
    require(error.status == ServiceStatus::unknown_operation && error.payload.empty() && !providers.closed(), "external unknown operation");
    require(providers.acknowledge(3) == ServiceStatus::ok, "external ACK");
    request.sequence = 1; request.operation = 1; request.payload = encode_u32(41);
    require(providers.invoke(request).status == ServiceStatus::expired, "external retired invocation replay");
    module.shutdown();
}
} // namespace
int main(int argc, char** argv) {
    try {
        if (argc == 3 && std::string_view(argv[1]) == "--external") {
            external(argv[2]); std::cout << "external appended provider execution passed\n"; return 0;
        }
        require(argc == 1, "usage: providers_test [--external MODULE]");
        success_and_replay(); registration_and_discovery(); response_lifecycle(); bounded_admission();
        invocation_guards_and_shutdown(); ownership_and_event_sequences();
        std::cout << "appended module provider contract passed\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
