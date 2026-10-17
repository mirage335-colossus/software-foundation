#include "foundation/appended/module.hpp"
#include "foundation/appended/web_services.hpp"

#include <algorithm>
#include <array>
#include <functional>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>

using namespace foundation::appended;
namespace {
constexpr std::uint64_t document_generation = 29, module_generation = 7;
constexpr std::string_view native_name = "org.example.web.native";
constexpr std::string_view module_name = "org.example.web.module";

void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
struct OwnedField { std::uint16_t id; FieldType type; Bytes bytes; };
Bytes record(std::initializer_list<OwnedField> fields) {
    std::vector<FieldView> views;
    for (const auto& item : fields) views.push_back({item.id,item.type,true,item.bytes});
    Bytes bytes;
    require(encode_record(views,bytes) == CodecStatus::ok,"fixture record encoding");
    return bytes;
}
Bytes text(std::string_view value) { return {value.begin(),value.end()}; }
const SchemaId& schema() {
    static constexpr SchemaId value{0x3f,0xe7,0xab,0x0d,0x3f,0x8f,0x76,0x49,
        0x9f,0x05,0x4c,0xa6,0xf2,0x9f,0x68,0xde,0xee,0x28,0x62,0x76,0x81,0xf7,
        0x92,0x31,0xaf,0x3b,0x09,0x5b,0x06,0x35,0xb2,0x46};
    return value;
}
std::uint32_t u32(std::span<const std::uint8_t> bytes) {
    require(bytes.size() == 4,"expected four-byte result");
    return std::uint32_t(bytes[0]) | (std::uint32_t(bytes[1]) << 8) |
        (std::uint32_t(bytes[2]) << 16) | (std::uint32_t(bytes[3]) << 24);
}
Bytes request(std::uint64_t sequence, std::uint64_t handle, std::uint32_t operation,
              const Bytes& payload = {}, std::uint64_t generation = document_generation) {
    Envelope header; header.generation = generation; header.sequence = sequence;
    header.interface_handle = handle; header.operation = operation;
    Bytes bytes;
    require(encode_envelope(header,payload,bytes) == CodecStatus::ok,"fixture envelope encoding");
    return bytes;
}
Bytes discovery(std::string_view service, std::uint32_t minimum = 0, std::uint32_t maximum = 0,
                const std::optional<SchemaId>& expected = {}) {
    std::vector<OwnedField> fields{{1,FieldType::utf8,text(service)},
        {2,FieldType::u32,encode_u32(1)}, {3,FieldType::u32,encode_u32(minimum)},
        {4,FieldType::u32,encode_u32(maximum)}};
    if (expected) fields.push_back({5,FieldType::bytes,Bytes(expected->begin(),expected->end())});
    std::vector<FieldView> views;
    for (const auto& item : fields) views.push_back({item.id,item.type,true,item.bytes});
    Bytes bytes;
    require(encode_record(views,bytes) == CodecStatus::ok,"discovery record encoding");
    return bytes;
}
struct Outcome { Envelope header; Bytes payload; };
Outcome outcome(const Bytes& bytes) {
    Outcome value; std::span<const std::uint8_t> payload;
    require(decode_envelope(bytes,value.header,payload) == CodecStatus::ok,"invalid owned completion envelope");
    require(value.header.kind == FOUNDATION_APPENDED_MESSAGE_COMPLETION && value.header.correlation == 0,
        "completion kind/correlation does not follow queue contract");
    value.payload.assign(payload.begin(),payload.end()); return value;
}
Bytes take(WebServices& services, std::uint64_t sequence, ServiceStatus status = ServiceStatus::ok) {
    auto bytes = services.take_completion(); require(bool(bytes),"missing web completion");
    const auto value = outcome(*bytes);
    require(value.header.generation == services.generation() && value.header.sequence == sequence &&
        value.header.service_status == static_cast<std::uint32_t>(status),"web completion identity/status");
    if (status != ServiceStatus::ok) require(value.payload.empty(),"error completion exposes payload");
    return std::move(*bytes);
}
Bytes run(WebServices& services, const Bytes& packet, std::uint64_t sequence,
          ServiceStatus status = ServiceStatus::ok,
          WebServiceSource source = WebServiceSource::automatic) {
    require(services.submit(packet,source) == ServiceStatus::ok,"web request admission");
    require(services.pump() == ServiceStatus::ok,"web request pump");
    auto bytes = take(services,sequence,status);
    Envelope submitted; std::span<const std::uint8_t> payload;
    require(decode_envelope(packet,submitted,payload) == CodecStatus::ok,"run fixture request decoding");
    const auto completed = outcome(bytes);
    require(completed.header.interface_handle == submitted.interface_handle &&
        completed.header.operation == submitted.operation,"completion changed opaque handle/operation");
    return bytes;
}
struct Found { std::uint64_t handle; std::uint32_t minor, maximum_reply; };
Found found(const Bytes& completion, std::string_view expected_name) {
    const auto value = outcome(completion); std::vector<FieldView> fields;
    require(decode_record(value.payload,fields) == CodecStatus::ok && fields.size() == 6,
        "discovery changed canonical bootstrap reply schema");
    Found result{}; std::uint32_t major = 0;
    for (std::size_t i = 0; i != fields.size(); ++i)
        require(fields[i].id == i + 1 && fields[i].must_understand,"bootstrap descriptor field identity/flags");
    require(read_u64(fields[0],result.handle) && result.handle != 0 &&
        fields[1].type == FieldType::utf8 &&
        std::string_view(reinterpret_cast<const char*>(fields[1].value.data()),fields[1].value.size()) == expected_name &&
        read_u32(fields[2],major) && major == 1 && read_u32(fields[3],result.minor) &&
        fields[4].type == FieldType::bytes && fields[4].value.size() == schema().size() &&
        std::equal(fields[4].value.begin(),fields[4].value.end(),schema().begin()) &&
        read_u32(fields[5],result.maximum_reply),"bootstrap descriptor values");
    return result;
}
Found find(WebServices& services, std::uint64_t sequence, std::string_view service = native_name,
           std::uint32_t minimum = 0, std::uint32_t maximum = 0,
           WebServiceSource source = WebServiceSource::automatic) {
    return found(run(services,request(sequence,0,FOUNDATION_APPENDED_CONTROL_DISCOVER,
        discovery(service,minimum,maximum)),sequence,ServiceStatus::ok,source),service);
}
void result(const Bytes& completion, std::uint32_t number, std::uint32_t effects) {
    const auto value = outcome(completion);
    require(value.payload.size() == 8 && u32(std::span(value.payload).first(4)) == number &&
        u32(std::span(value.payload).subspan(4)) == effects,"owned service result value/count");
}
struct Native {
    unsigned effects{0}; std::function<void()> callback;
    NativeServiceRegistration registration(std::string_view service = native_name,
                                           std::uint16_t minor = 0, std::uint32_t maximum_reply = 8) {
        return {{std::string(service),1,minor,schema(),maximum_reply},
            [this](std::uint32_t operation, auto input, auto output) -> ServiceReply {
                if (operation != 1 && operation != 2 && operation != 3) return {ServiceStatus::unknown_operation,0};
                ++effects;
                if (callback) callback();
                if (operation == 2) throw std::runtime_error("deliberate failure after native effect");
                if (operation == 3) return {ServiceStatus::ok,static_cast<std::uint32_t>(output.size() + 1)};
                const auto operand = input.empty() ? 0 : u32(input);
                const auto first = encode_u32(operand + 10), second = encode_u32(effects);
                require(output.size() >= 8,"native wrapper reply was not reserved");
                std::copy(first.begin(),first.end(),output.begin());
                std::copy(second.begin(),second.end(),output.begin() + 4);
                return {ServiceStatus::ok,8};
            }};
    }
};

void native_copy_replay_and_callback_boundaries() {
    Native native; const std::array registrations{native.registration()};
    Registry guest(module_generation);
    require(install_native_services(guest,registrations) == ServiceStatus::ok,"install deliberate native wrappers");
    const auto raw = guest.discover({native_name,1,0,0,schema()});
    require(raw.status == ServiceStatus::ok,"installed native wrapper discoverability");
    require(install_native_services(guest,registrations) == ServiceStatus::conflict,
        "duplicate wrapper startup did not report conflict");
    WebServices web(document_generation,registrations);
    require(web.generation() == document_generation && !web.closed(),"web document generation/startup");
    auto discover = request(1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER,discovery(native_name));
    {
        WebServices::CallbackScope outer(web);
        require(web.submit(discover) == ServiceStatus::ok,"callback discovery submission");
        require(web.submit(request(2,UINT64_C(0x8000000000000000),1,encode_u32(41))) == ServiceStatus::invalid_handle && native.effects == 0,
            "queued discovery admitted a guessed handle without maximum reply reservation");
        {
            WebServices::CallbackScope inner(web);
            require(web.pump() == ServiceStatus::unavailable && !web.take_completion() &&
                web.acknowledge(document_generation,1) == ServiceStatus::unavailable,
                "nested engine callback allowed execution/delivery/ACK");
        }
        require(web.pump() == ServiceStatus::unavailable,"inner callback destruction released outer guard");
    }
    require(web.pump() == ServiceStatus::ok,"post-callback discovery pump");
    const auto handle = found(take(web,1),native_name).handle;
    require(handle != raw.handle,"web handle borrowed native Registry namespace");
    require(web.acknowledge(document_generation,1) == ServiceStatus::ok,"discovery ACK");
    auto packet = request(2,handle,1,encode_u32(41)); const auto original = packet;
    native.callback = [&] {
        require(web.pump() == ServiceStatus::unavailable && !web.take_completion() &&
            web.acknowledge(document_generation,2) == ServiceStatus::unavailable,
            "native callback recursively pumped/delivered/retired web work");
        require(web.cancel(document_generation,2) != ServiceStatus::ok,"active native call cancelled");
        bool rejected = false;
        try { WebServices::CallbackScope illegal_engine_entry(web); }
        catch (const std::logic_error&) { rejected = true; }
        require(rejected,"native invocation permitted synchronous engine callback scope");
    };
    {
        WebServices::CallbackScope callback(web);
        require(web.submit(packet) == ServiceStatus::ok && native.effects == 0,"submit invoked native wrapper");
        std::fill(packet.begin(),packet.end(),0); packet.clear();
        require(web.pump() == ServiceStatus::unavailable && native.effects == 0,"callback pump caused native effect");
    }
    require(web.retained_call_count() == 1 && web.retained_bytes() >= original.size() + 64 + 8,
        "request and maximum completion were not reserved at admission");
    require(web.pump() == ServiceStatus::ok && native.effects == 1,"deferred native effect count");
    {
        WebServices::CallbackScope callback(web);
        require(!web.take_completion() && web.acknowledge(document_generation,2) == ServiceStatus::unavailable,
            "ready completion escaped into active engine callback");
    }
    auto owned = take(web,2); result(owned,51,1);
    require(!web.take_completion(),"completion delivered twice without replay submission");
    require(web.submit(original) == ServiceStatus::ok,"identical retained web retry");
    require(take(web,2) == owned && native.effects == 1,"retained retry repeated native work/changed reply");
    auto changed = request(2,handle,1,encode_u32(99));
    require(web.submit(changed) == ServiceStatus::conflict &&
        web.submit(original,WebServiceSource::native) == ServiceStatus::conflict && native.effects == 1,
        "changed bytes/source replay invoked native service");
    require(web.acknowledge(document_generation + 1,2) != ServiceStatus::ok &&
        web.acknowledge(document_generation,3) != ServiceStatus::ok,"stale/future ACK accepted");
    require(web.acknowledge(document_generation,2) == ServiceStatus::ok &&
        web.retained_call_count() == 0 && web.retained_bytes() == 0,"ACK retained web request/reply storage");
    result(owned,51,1);
    require(web.submit(original) == ServiceStatus::expired && native.effects == 1,"retired native work repeated");
    native.callback = {};
    result(run(web,request(4,handle,1,encode_u32(7)),4),17,2);
    require(web.submit(request(3,handle,1,encode_u32(7))) == ServiceStatus::expired && native.effects == 2,
        "unused lower web sequence admitted after higher work");
    require(web.acknowledge(document_generation,4) == ServiceStatus::ok,"ACK did not close lower sequence gap");
}

void bounded_queue_cancellation_and_generations() {
    Native native; const std::array registrations{native.registration()};
    WebServiceLimits limits; limits.max_retained_calls = 1;
    WebServices web(document_generation,registrations,{},limits);
    const auto handle = find(web,1).handle;
    require(web.acknowledge(document_generation,1) == ServiceStatus::ok,"bounded discovery ACK");
    const auto first = request(2,handle,1,encode_u32(1)), second = request(3,handle,1,encode_u32(2));
    require(web.submit(first) == ServiceStatus::ok && web.submit(second) == ServiceStatus::limit_exceeded &&
        native.effects == 0 && web.retained_call_count() == 1,"full queued ledger admitted native effects");
    require(web.acknowledge(document_generation,2) != ServiceStatus::ok,"ACK crossed unfinished request");
    require(web.cancel(document_generation + 1,2) != ServiceStatus::ok &&
        web.cancel(document_generation,99) != ServiceStatus::ok,"stale/unknown cancellation succeeded");
    require(web.cancel(document_generation,2) == ServiceStatus::ok,"queued cancellation");
    const auto cancelled = take(web,2,ServiceStatus::closed);
    require(web.pump() == ServiceStatus::ok && native.effects == 0,"cancelled request entered native wrapper");
    require(web.submit(first) == ServiceStatus::ok && take(web,2,ServiceStatus::closed) == cancelled,
        "cancelled result was not retained for replay");
    require(web.acknowledge(document_generation,2) == ServiceStatus::ok,"cancelled request ACK");
    result(run(web,second,3),12,1);
    require(web.cancel(document_generation,3) != ServiceStatus::ok,"completed effect cancelled");
    require(web.submit(request(4,handle,1,encode_u32(1),document_generation + 1)) != ServiceStatus::ok &&
        native.effects == 1,"foreign document generation entered service");
    WebServices replacement(document_generation + 1,registrations);
    require(replacement.submit(first) != ServiceStatus::ok && native.effects == 1,
        "replacement document accepted predecessor envelope");
    bool zero_rejected = false;
    try { WebServices invalid(0,registrations); } catch (const std::invalid_argument&) { zero_rejected = true; }
    require(zero_rejected,"zero document generation accepted");

    const std::array large_registration{native.registration(native_name,0,600)};
    WebServiceLimits byte_limits; byte_limits.max_message_bytes = 1024; byte_limits.max_retained_bytes = 600;
    WebServices bounded(document_generation,large_registration,{},byte_limits);
    const auto large_handle = find(bounded,1).handle;
    require(bounded.acknowledge(document_generation,1) == ServiceStatus::ok,"byte-bounded discovery ACK");
    require(bounded.submit(request(2,large_handle,1,encode_u32(1))) == ServiceStatus::limit_exceeded &&
        bounded.retained_call_count() == 0 && native.effects == 1,
        "maximum reply storage was not reserved before native effect");
}

void completed_prefix_and_pump_limit() {
    Native native; const std::array registrations{native.registration()}; WebServices web(document_generation,registrations);
    const auto handle = find(web,1).handle;
    require(web.acknowledge(document_generation,1) == ServiceStatus::ok,"prefix fixture discovery ACK");
    const auto three = request(3,handle,1,encode_u32(3)), five = request(5,handle,1,encode_u32(5));
    require(web.submit(three) == ServiceStatus::ok && web.submit(five) == ServiceStatus::ok,
        "gapped queued prefix fixture");
    require(web.cancel(document_generation,3) == ServiceStatus::ok &&
        web.acknowledge(document_generation,5) != ServiceStatus::ok && web.retained_call_count() == 2,
        "ACK partially retired prefix before rejecting queued work");
    require(web.acknowledge(document_generation,4) == ServiceStatus::ok && web.retained_call_count() == 1 &&
        web.submit(three) == ServiceStatus::expired && web.submit(request(4,handle,1)) == ServiceStatus::expired,
        "completed prefix ACK did not retire unused lower gap");
    require(web.pump(0) == ServiceStatus::ok && native.effects == 0 && !web.take_completion(),
        "zero-call pump executed pending work");
    require(web.pump(1) == ServiceStatus::ok && native.effects == 1,"one-call pump missed pending work");
    result(take(web,5),15,1);
    require(web.acknowledge(document_generation,5) == ServiceStatus::ok,"completed gapped prefix ACK");
    require(web.submit(request(6,handle,1,encode_u32(6))) == ServiceStatus::ok &&
        web.submit(request(7,handle,1,encode_u32(7))) == ServiceStatus::ok,"pump maximum fixture");
    require(web.pump(1) == ServiceStatus::ok && native.effects == 2,"pump exceeded requested maximum");
    result(take(web,6),16,2); require(!web.take_completion(),"unpumped request already completed");
    require(web.pump(1) == ServiceStatus::ok && native.effects == 3,"second bounded pump");
    result(take(web,7),17,3);
}

void failures_and_recursive_close() {
    for (const auto operation : {2u,3u}) {
        Native native; const std::array registrations{native.registration()}; WebServices web(document_generation,registrations);
        const auto handle = find(web,1).handle;
        const auto packet = request(2,handle,operation);
        const auto status = operation == 2 ? ServiceStatus::uncertain : ServiceStatus::internal_error;
        const auto failed = run(web,packet,2,status);
        require(native.effects == 1 && web.submit(packet) == ServiceStatus::ok && take(web,2,status) == failed &&
            native.effects == 1,"failed/uncertain native effect was retried");
    }
    Native native; const std::array registrations{native.registration()}; WebServices web(document_generation,registrations);
    const auto handle = find(web,1).handle;
    const auto active = request(2,handle,1,encode_u32(5)), queued = request(3,handle,1,encode_u32(6));
    require(web.submit(active) == ServiceStatus::ok && web.submit(queued) == ServiceStatus::ok,"close fixture admission");
    native.callback = [&] {
        web.close(); web.close();
        require(web.pump() == ServiceStatus::unavailable && !web.take_completion(),
            "recursive close destroyed active queue invocation guard");
    };
    require(web.pump() == ServiceStatus::ok && web.closed() && native.effects == 1,"recursive close repeated/lost native effect");
    const auto first = web.take_completion(), second = web.take_completion();
    require(bool(first) && bool(second),"recursive close lost active/queued outcomes");
    const auto active_result = outcome(*first).header.sequence == 2 ? first : second;
    const auto queued_result = outcome(*first).header.sequence == 3 ? *first : *second;
    require(outcome(*active_result).header.sequence == 2 && outcome(queued_result).header.sequence == 3 &&
        outcome(queued_result).header.service_status == FOUNDATION_APPENDED_SERVICE_CLOSED,
        "recursive close changed active/queued outcome identities");
    require(web.submit(active) == ServiceStatus::ok && web.take_completion() == active_result && native.effects == 1,
        "closed queue repeated an already completed effect");
    require(web.submit(queued) == ServiceStatus::ok && take(web,3,ServiceStatus::closed) == queued_result && native.effects == 1,
        "close did not retain queued cancellation outcome");
    require(web.submit(request(4,handle,1)) == ServiceStatus::closed,"closed queue admitted fresh service work");
    require(web.acknowledge(document_generation,3) == ServiceStatus::ok && web.retained_call_count() == 0,
        "closed queue prevented completed prefix retirement");
}

// A standalone foundation-guest-v1 module assembled here exercises the actual
// wasm3 interpreter, ModuleProviders registration/dispatch/respond, and imported
// native gateway. Its counter and response bytes live in guest linear memory.
void append(Bytes& to, const Bytes& from) { to.insert(to.end(),from.begin(),from.end()); }
void uleb(Bytes& bytes, std::uint32_t value) {
    do {
        const auto next = static_cast<std::uint8_t>(value & 127u); value >>= 7;
        bytes.push_back(static_cast<std::uint8_t>(next | (value ? 128u : 0u)));
    } while (value);
}
void constant(Bytes& bytes, std::int32_t value) {
    bytes.push_back(0x41); bool more;
    do {
        const auto next = static_cast<std::uint8_t>(value & 127); value >>= 7;
        more = !((value == 0 && !(next & 64)) || (value == -1 && (next & 64)));
        bytes.push_back(static_cast<std::uint8_t>(next | (more ? 128u : 0u)));
    } while (more);
}
void name(Bytes& bytes, std::string_view value) {
    uleb(bytes,static_cast<std::uint32_t>(value.size())); bytes.insert(bytes.end(),value.begin(),value.end());
}
void section(Bytes& bytes, std::uint8_t id, const Bytes& content) {
    bytes.push_back(id); uleb(bytes,static_cast<std::uint32_t>(content.size())); append(bytes,content);
}
void load32(Bytes& code, std::uint32_t address) {
    constant(code,static_cast<std::int32_t>(address)); append(code,{0x28,2,0});
}
void copy64(Bytes& code, std::uint32_t destination, std::uint32_t source) {
    constant(code,static_cast<std::int32_t>(destination)); constant(code,static_cast<std::int32_t>(source));
    append(code,{0x29,3,0,0x37,3,0});
}
void event64(Bytes& code, std::uint32_t destination, std::uint32_t offset) {
    constant(code,static_cast<std::int32_t>(destination)); append(code,{0x20,0,0x29,3});
    uleb(code,offset); append(code,{0x37,3,0});
}
void trap_if(Bytes& code) { append(code,{0x04,0x40,0x00,0x0b}); }
constexpr std::uint32_t sequence_address = 128, count_address = 136, control_address = 144;
constexpr std::uint32_t response_address = 2048, native_address = 2304, ack_address = 2560, reply_address = 8192;
void gateway(Bytes& code, std::uint32_t packet, std::size_t bytes) {
    constant(code,sequence_address); constant(code,sequence_address);
    append(code,{0x29,3,0,0x42,1,0x7c,0x37,3,0});
    copy64(code,packet + FOUNDATION_APPENDED_OFFSET_SEQUENCE,sequence_address);
    constant(code,static_cast<std::int32_t>(packet)); constant(code,static_cast<std::int32_t>(bytes));
    constant(code,reply_address); constant(code,512); append(code,{0x10,0}); trap_if(code);
    load32(code,reply_address + FOUNDATION_APPENDED_OFFSET_STATUS); trap_if(code);
}
void acknowledge_gateway(Bytes& code, std::size_t bytes) {
    copy64(code,ack_address + 72,sequence_address); gateway(code,ack_address,bytes);
}
Bytes provider_fixture(std::uint64_t native_handle, std::uint16_t minor = 2, bool trap_after_response = false) {
    const auto discover = request(1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER,
        discovery(FOUNDATION_PROVIDER_SERVICE_NAME),module_generation);
    const auto registration = record({{1,FieldType::utf8,text(module_name)}, {2,FieldType::u32,encode_u32(1)},
        {3,FieldType::u32,encode_u32(minor)}, {4,FieldType::bytes,Bytes(schema().begin(),schema().end())},
        {5,FieldType::u32,encode_u32(4)}, {6,FieldType::u32,encode_u32(8)}});
    const auto register_packet = request(1,1,FOUNDATION_PROVIDER_REGISTER,registration,module_generation);
    const auto response = request(1,1,FOUNDATION_PROVIDER_RESPOND,record({
        {1,FieldType::u64,encode_u64(1)}, {2,FieldType::u64,encode_u64(1)},
        {3,FieldType::u32,encode_u32(0)}, {4,FieldType::bytes,Bytes(8)}}),module_generation);
    const auto native = request(1,native_handle,1,{},module_generation);
    const auto ack = request(1,0,FOUNDATION_APPENDED_CONTROL_ACKNOWLEDGE,
        record({{1,FieldType::u64,encode_u64(1)}}),module_generation);
    const std::array<std::pair<std::uint32_t,Bytes>,5> data{{{256,discover},{512,register_packet},
        {response_address,response},{native_address,native},{ack_address,ack}}};
    std::array<Bytes,7> code;
    constant(code[0],FOUNDATION_APPENDED_ABI_VERSION); constant(code[1],16384);
    gateway(code[3],256,discover.size()); copy64(code[3],control_address,reply_address + 72);
    acknowledge_gateway(code[3],ack.size());
    copy64(code[3],512 + FOUNDATION_APPENDED_OFFSET_INTERFACE,control_address);
    gateway(code[3],512,register_packet.size()); acknowledge_gateway(code[3],ack.size()); constant(code[3],0);
    auto& dispatch = code[4];
    gateway(dispatch,native_address,native.size()); acknowledge_gateway(dispatch,ack.size());
    constant(dispatch,count_address); load32(dispatch,count_address); constant(dispatch,1); append(dispatch,{0x6a,0x36,2,0});
    copy64(dispatch,response_address + FOUNDATION_APPENDED_OFFSET_INTERFACE,control_address);
    event64(dispatch,response_address + 72,FOUNDATION_APPENDED_OFFSET_CORRELATION);
    event64(dispatch,response_address + 88,72);
    constant(dispatch,response_address + 116); append(dispatch,{0x20,0,0x28,2,100}); constant(dispatch,1);
    append(dispatch,{0x6a,0x36,2,0});
    constant(dispatch,response_address + 120); load32(dispatch,count_address); append(dispatch,{0x36,2,0});
    gateway(dispatch,response_address,response.size()); acknowledge_gateway(dispatch,ack.size());
    if (trap_after_response) dispatch.push_back(0x00);
    constant(dispatch,0); constant(code[5],0);
    Bytes module{0,97,115,109,1,0,0,0};
    section(module,1,{6,0x60,4,0x7f,0x7f,0x7f,0x7f,1,0x7f,
        0x60,0,1,0x7f,0x60,1,0x7f,1,0x7f,0x60,2,0x7f,0x7f,0,
        0x60,2,0x7f,0x7f,1,0x7f,0x60,1,0x7f,0});
    Bytes imports{1}; name(imports,FOUNDATION_APPENDED_IMPORT_MODULE); name(imports,FOUNDATION_APPENDED_IMPORT_NAME);
    append(imports,{0,0}); section(module,2,imports); section(module,3,{7,1,2,3,4,4,2,5}); section(module,5,{1,1,1,1});
    Bytes exports{8}; name(exports,"memory"); append(exports,{2,0});
    constexpr std::array names{"foundation_app_abi_v1","foundation_app_alloc_v1","foundation_app_free_v1",
        "foundation_app_init_v1","foundation_app_dispatch_v1","foundation_app_step_v1","foundation_app_shutdown_v1"};
    for (std::size_t i = 0; i < names.size(); ++i) {
        name(exports,names[i]); exports.push_back(0); uleb(exports,static_cast<std::uint32_t>(i + 1));
    }
    section(module,7,exports); Bytes bodies{7};
    for (const auto& instructions : code) {
        Bytes body{0}; append(body,instructions); body.push_back(0x0b);
        uleb(bodies,static_cast<std::uint32_t>(body.size())); append(bodies,body);
    }
    section(module,10,bodies); Bytes segments; uleb(segments,static_cast<std::uint32_t>(data.size()));
    for (const auto& [address,bytes] : data) {
        segments.push_back(0); constant(segments,static_cast<std::int32_t>(address)); segments.push_back(0x0b);
        uleb(segments,static_cast<std::uint32_t>(bytes.size())); append(segments,bytes);
    }
    section(module,11,segments); return module;
}
struct ModuleHarness {
    Native native;
    Registry registry{module_generation};
    std::uint64_t native_handle{0}, event_sequence{100}, host_sequence{40};
    unsigned events_issued{0}, hosts_issued{0};
    std::vector<std::uint64_t> copied_outcomes;
    std::unique_ptr<Module> module;
    std::unique_ptr<ModuleProviders> providers;
    explicit ModuleHarness(bool trap_after_response = false) {
        const std::array registrations{native.registration()};
        require(install_native_services(registry,registrations) == ServiceStatus::ok,"guest native wrapper installation");
        native_handle = registry.discover({native_name,1,0,0,schema()}).handle;
        module = std::make_unique<Module>(provider_fixture(native_handle,2,trap_after_response),registry);
        providers = std::make_unique<ModuleProviders>(*module,registry,[this]() -> std::optional<std::uint64_t> {
            ++events_issued; return ++event_sequence;
        });
        require(module->initialize() == 0 && providers->activate() == ServiceStatus::ok,"real wasm provider startup");
    }
    WebModuleServices services(bool shared = true) {
        WebModuleServices binding;
        binding.generation = module_generation;
        binding.discover = [this](const DiscoveryQuery& query) { return providers->discover(query); };
        binding.invoke = [this](const ProviderRequest& packet) { return providers->invoke(packet); };
        binding.acknowledge = [this,shared](std::uint64_t sequence) {
            copied_outcomes.push_back(sequence);
            // A shared composition owner may defer prefix retirement while an
            // unrelated caller still owns an earlier outcome.
            return shared ? ServiceStatus::unavailable : providers->acknowledge(sequence);
        };
        if (shared) binding.sequence = [this]() -> std::optional<std::uint64_t> { ++hosts_issued; return ++host_sequence; };
        return binding;
    }
};

void real_module_routing_and_separate_sequence_domains() {
    ModuleHarness h;
    const auto raw_provider = h.providers->discover({module_name,1,0,2,schema()});
    require(raw_provider.status == ServiceStatus::ok && raw_provider.handle == h.native_handle,
        "fixture did not exercise colliding raw native/provider handles");
    const auto external = h.providers->invoke({module_generation,40,raw_provider.handle,1,encode_u32(8)});
    require(external.status == ServiceStatus::ok && external.payload.size() == 8 && h.native.effects == 1 &&
        u32(std::span(external.payload).first(4)) == 9 && h.events_issued == 1,"direct provider host-domain fixture");
    const std::array registrations{h.native.registration()};
    WebServices web(document_generation,registrations,h.services());
    const auto module_handle = find(web,1,module_name,0,2).handle, native_handle = find(web,2).handle;
    require(module_handle != native_handle && module_handle != raw_provider.handle &&
        native_handle != h.native_handle,"opaque web handles aliased native/provider namespaces");
    require(h.hosts_issued == 0 && h.events_issued == 1,"discovery consumed provider invocation/event sequences");
    unsigned nested = 0;
    h.native.callback = [&] {
        ++nested;
        require(h.registry.invocation_active() && h.module->invocation_active(),"provider bypassed real guest native gateway");
        require(web.pump() == ServiceStatus::unavailable && !web.take_completion() &&
            web.acknowledge(document_generation,3) == ServiceStatus::unavailable,"guest native callback reentered web queue");
    };
    const auto packet = request(3,module_handle,1,encode_u32(41));
    {
        WebServices::CallbackScope callback(web);
        require(web.submit(packet) == ServiceStatus::ok && h.native.effects == 1 && h.hosts_issued == 0,
            "engine callback synchronously entered provider");
        require(web.pump() == ServiceStatus::unavailable && h.native.effects == 1,"engine callback pumped guest");
    }
    require(web.pump() == ServiceStatus::ok && nested == 1,"real wasm provider pump");
    const auto owned = take(web,3); result(owned,42,2);
    require(h.native.effects == 2 && h.host_sequence == 41 && h.hosts_issued == 1 && h.event_sequence == 102 &&
        h.events_issued == 2,"web/provider/event/gateway sequence domains collided");
    require(h.copied_outcomes == std::vector<std::uint64_t>{41} &&
        h.providers->invoke({module_generation,40,raw_provider.handle,1,encode_u32(8)}).payload == external.payload &&
        h.native.effects == 2,"web copied-outcome notification retired another provider caller's result");
    require(web.submit(packet) == ServiceStatus::ok && take(web,3) == owned && h.native.effects == 2 &&
        h.hosts_issued == 1 && h.events_issued == 2,"web replay consumed backend sequence or repeated guest effect");
    h.native.callback = {};
    result(run(web,request(4,native_handle,1,encode_u32(5)),4),15,3);
    require(h.hosts_issued == 1 && h.events_issued == 2,"web native call consumed module counters");
    require(web.acknowledge(document_generation,4) == ServiceStatus::ok,"mixed provider/native web ACK");
    result(run(web,request(5,module_handle,1,encode_u32(9)),5),10,3);
    require(h.native.effects == 4 && h.host_sequence == 42 && h.event_sequence == 103,"post-ACK real module execution");
    result(owned,42,2);
    require(web.retained_call_count() == 1,"web ACK failed to retire mixed-source outcomes");
}

void automatic_discovery_and_source_independent_calls() {
    ModuleHarness h;
    const std::array registrations{h.native.registration(module_name,1)};
    WebServices web(document_generation,registrations,h.services());
    const auto automatic = find(web,1,module_name,0,2);
    const auto explicit_module = find(web,2,module_name,0,2,WebServiceSource::module);
    const auto explicit_native = find(web,3,module_name,0,2,WebServiceSource::native);
    const auto older = find(web,4,module_name,0,1);
    require(automatic.minor == 2 && explicit_module.minor == 2 && explicit_native.minor == 1 && older.minor == 1 &&
        automatic.maximum_reply == 8 && explicit_native.maximum_reply == 8,"highest compatible cross-source minor selection");
    // Ordinary page requests contain only the discovered opaque handle. The same
    // request format reaches either source without a page-side routing branch.
    result(run(web,request(5,automatic.handle,1,encode_u32(41)),5),42,1);
    result(run(web,request(6,explicit_native.handle,1,encode_u32(41)),6),51,2);
    result(run(web,request(7,older.handle,1,encode_u32(41)),7),51,3);
    const std::array tied{h.native.registration(module_name,2)};
    WebServices conflict(document_generation,tied,h.services());
    run(conflict,request(1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER,discovery(module_name,0,2)),1,ServiceStatus::conflict);
    const auto selected_native = find(conflict,2,module_name,0,2,WebServiceSource::native);
    const auto selected_module = find(conflict,3,module_name,0,2,WebServiceSource::module);
    require(selected_native.handle != selected_module.handle && selected_native.minor == 2 && selected_module.minor == 2,
        "explicit equal-version source selection shared opaque route");
    result(run(conflict,request(4,selected_module.handle,1,encode_u32(1)),4),2,2);
}

void real_module_uncertain_replay_and_exhaustion() {
    ModuleHarness h(true); WebServices web(document_generation,{},h.services(false));
    const auto handle = find(web,1,module_name,0,2).handle;
    const auto packet = request(2,handle,1,encode_u32(41));
    const auto failed = run(web,packet,2,ServiceStatus::uncertain);
    require(h.native.effects == 1 && h.providers->closed() && h.module->closed() && h.registry.closed(),
        "guest trap after response exposed success/live backend");
    require(web.submit(packet) == ServiceStatus::ok && take(web,2,ServiceStatus::uncertain) == failed &&
        h.native.effects == 1 && h.events_issued == 1,"uncertain guest effect repeated on web retry");
    require(web.acknowledge(document_generation,2) == ServiceStatus::ok,"uncertain web result ACK");
    ModuleHarness exhausted;
    auto services = exhausted.services(); services.sequence = []() -> std::optional<std::uint64_t> { return {}; };
    WebServices no_sequence(document_generation,{},std::move(services));
    const auto exhausted_handle = find(no_sequence,1,module_name,0,2).handle;
    require(no_sequence.submit(request(2,exhausted_handle,1,encode_u32(1))) == ServiceStatus::ok,
        "provider sequence exhaustion should be checked outside engine callback");
    require(no_sequence.pump() == ServiceStatus::ok,"exhausted provider sequence completion pump");
    const auto completion = no_sequence.take_completion(); require(bool(completion),"provider exhaustion lost completion");
    require(outcome(*completion).header.service_status != FOUNDATION_APPENDED_SERVICE_OK &&
        exhausted.native.effects == 0 && exhausted.events_issued == 0,"exhausted host sequence dispatched guest");
}

void module_hook_boundaries_and_owned_lifetime() {
    ModuleHarness excessive;
    auto excessive_services = excessive.services();
    excessive_services.discover = [&](const DiscoveryQuery& query) {
        auto descriptor = excessive.providers->discover(query);
        if (descriptor.status == ServiceStatus::ok) descriptor.descriptor.contract.max_reply_bytes = 321;
        return descriptor;
    };
    WebServiceLimits small; small.max_message_bytes = 384;
    WebServices bounded(document_generation,{},std::move(excessive_services),small);
    run(bounded,request(1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER,discovery(module_name,0,2)),1,ServiceStatus::limit_exceeded);
    require(excessive.native.effects == 0 && excessive.events_issued == 0,
        "oversized module reply contract dispatched guest before rejection");

    ModuleHarness retirement;
    auto throwing_services = retirement.services(false);
    throwing_services.acknowledge = [](std::uint64_t) -> ServiceStatus {
        throw std::runtime_error("retirement notification failed after known response");
    };
    Bytes owned;
    {
        WebServices web(document_generation,{},std::move(throwing_services));
        const auto handle = find(web,1,module_name,0,2).handle;
        const auto packet = request(2,handle,1,encode_u32(41));
        owned = run(web,packet,2);
        result(owned,42,1);
        require(web.closed() && retirement.native.effects == 1 &&
            web.submit(packet) == ServiceStatus::ok && take(web,2) == owned && retirement.native.effects == 1,
            "retirement hook failure replaced known result or repeated its effect");
    }
    retirement.module->shutdown(); result(owned,42,1);

    ModuleHarness closing;
    auto closing_services = closing.services(); WebServices* callback_owner = nullptr;
    closing_services.sequence = [&]() -> std::optional<std::uint64_t> {
        require(callback_owner != nullptr,"sequence hook ran during construction");
        require(callback_owner->pump() == ServiceStatus::unavailable && !callback_owner->take_completion() &&
            callback_owner->acknowledge(document_generation,2) == ServiceStatus::unavailable,
            "sequence hook reentered queue execution/delivery/ACK");
        callback_owner->close(); return 1;
    };
    WebServices web(document_generation,{},std::move(closing_services)); callback_owner = &web;
    const auto handle = find(web,1,module_name,0,2).handle;
    const auto packet = request(2,handle,1,encode_u32(1));
    const auto closed = run(web,packet,2,ServiceStatus::closed);
    require(web.closed() && closing.native.effects == 0 && closing.events_issued == 0 &&
        web.submit(packet) == ServiceStatus::ok && take(web,2,ServiceStatus::closed) == closed,
        "sequence hook close entered guest or lost cancelled result");
}
} // namespace

int main() {
    try {
        native_copy_replay_and_callback_boundaries(); bounded_queue_cancellation_and_generations();
        completed_prefix_and_pump_limit(); failures_and_recursive_close(); real_module_routing_and_separate_sequence_domains();
        automatic_discovery_and_source_independent_calls(); real_module_uncertain_replay_and_exhaustion();
        module_hook_boundaries_and_owned_lifetime();
        std::cout << "appended web service queue contract passed\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
