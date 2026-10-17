#include "foundation/appended/web_services.hpp"
#include "../../gui/shared/appended_demo_services.hpp"

#include <algorithm>
#include <array>
#include <initializer_list>
#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

using namespace foundation::appended;
namespace {
constexpr std::uint64_t generation = 29;
constexpr std::string_view service_name = "org.example.web.native";
constexpr SchemaId schema{1};

void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
struct OwnedField { std::uint16_t id; FieldType type; Bytes bytes; };
Bytes record(std::initializer_list<OwnedField> fields) {
    std::vector<FieldView> views;
    for (const auto& field : fields) views.push_back({field.id,field.type,true,field.bytes});
    Bytes bytes;
    require(encode_record(views,bytes) == CodecStatus::ok,"fixture record encoding");
    return bytes;
}
Bytes request(std::uint64_t sequence, std::uint64_t handle, std::uint32_t operation,
              const Bytes& payload) {
    Envelope header; header.generation = generation; header.sequence = sequence;
    header.interface_handle = handle; header.operation = operation;
    Bytes bytes;
    require(encode_envelope(header,payload,bytes) == CodecStatus::ok,"fixture request encoding");
    return bytes;
}
struct Outcome { Envelope header; Bytes payload; };
Outcome decode(const Bytes& bytes) {
    Outcome result; std::span<const std::uint8_t> payload;
    require(decode_envelope(bytes,result.header,payload) == CodecStatus::ok,"invalid service envelope");
    result.payload.assign(payload.begin(),payload.end());
    return result;
}
Bytes take(WebServices& web, std::uint64_t sequence, std::uint64_t handle, std::uint32_t operation,
        ServiceStatus expected = ServiceStatus::ok) {
    auto bytes = web.take_completion();
    require(bool(bytes),"missing web completion");
    const auto result = decode(*bytes);
    require(result.header.kind == FOUNDATION_APPENDED_MESSAGE_COMPLETION &&
        result.header.generation == generation && result.header.sequence == sequence &&
        result.header.interface_handle == handle && result.header.operation == operation &&
        result.header.service_status == static_cast<std::uint32_t>(expected) && result.header.correlation == 0,
        "web completion identity/status");
    return std::move(*bytes);
}
Bytes gateway_exchange(Registry& guest, const Bytes& packet,
        std::uint32_t capacity = FOUNDATION_APPENDED_ENVELOPE_BYTES + 4) {
    const auto offset = static_cast<std::uint32_t>(packet.size());
    Bytes memory(packet); memory.resize(offset + capacity);
    require(guest.call(memory,0,offset,offset,capacity) == TransportStatus::ok,"guest gateway transport");
    const auto output = std::span<const std::uint8_t>(memory).subspan(offset);
    const auto size = std::uint32_t(output[0]) | (std::uint32_t(output[1]) << 8) |
        (std::uint32_t(output[2]) << 16) | (std::uint32_t(output[3]) << 24);
    require(size >= FOUNDATION_APPENDED_ENVELOPE_BYTES && size <= capacity,"guest reply size");
    return Bytes(output.begin(),output.begin() + size);
}

void demo_echo_catalog_contract() {
    constexpr std::string_view name = "demo.echo";
    constexpr SchemaId expected_schema{
        1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,
        17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32};
    const auto registrations = foundation::ui::demo_native_services();
    require(registrations.size() == 1,"demo catalog has unexpected registrations");
    const auto& descriptor = registrations.front().descriptor;
    require(descriptor.name == name && descriptor.major == 1 && descriptor.minor == 0 &&
        descriptor.schema == expected_schema && descriptor.max_reply_bytes == 1024,
        "demo echo descriptor differs from the application contract");

    // Exercise the defensive handler contract that normal Registry reservation
    // cannot reach: neither an unknown operation nor a short span may write.
    std::array<std::uint8_t,5> guarded{0xa5,0xa5,0xa5,0xa5,0xa5};
    const auto untouched = guarded;
    const Bytes binary{0x00,0xff,0x80,0x41,0x00};
    auto direct = registrations.front().handler(1,binary,std::span(guarded).subspan(1,3));
    require(direct.status == ServiceStatus::limit_exceeded && direct.bytes == 0 && guarded == untouched,
        "demo echo short output wrote bytes or returned a partial result");
    direct = registrations.front().handler(0,binary,guarded);
    require(direct.status == ServiceStatus::unknown_operation && direct.bytes == 0 && guarded == untouched,
        "demo echo unknown operation wrote bytes");
    const Bytes oversized(1025,0x6d);
    Bytes oversized_output(1025,0xa5);
    direct = registrations.front().handler(1,oversized,oversized_output);
    require(direct.status == ServiceStatus::limit_exceeded && direct.bytes == 0 &&
        std::all_of(oversized_output.begin(),oversized_output.end(),[](auto byte) { return byte == 0xa5; }),
        "demo echo oversized request wrote into a larger output span");

    // Both transports admit 1025-byte requests, so the larger-request check
    // below discriminates the handler's 1024-byte contract from transport caps.
    Limits guest_limits; guest_limits.max_message_bytes = 4096;
    WebServiceLimits web_limits; web_limits.max_message_bytes = 4096;
    Registry guest(generation,guest_limits);
    require(install_native_services(guest,registrations) == ServiceStatus::ok,"demo guest catalog installation");
    const auto native = guest.discover({name,1,0,0,expected_schema});
    require(native.status == ServiceStatus::ok && native.handle != 0 &&
        native.descriptor.name == name && native.descriptor.major == 1 && native.descriptor.minor == 0 &&
        native.descriptor.schema == expected_schema && native.descriptor.max_reply_bytes == 1024,
        "demo guest discovery descriptor");
    auto wrong_schema = expected_schema; wrong_schema.back() ^= 0xff;
    require(guest.discover({name,1,0,0,wrong_schema}).status == ServiceStatus::schema_mismatch &&
        guest.discover({name,2,0,0,expected_schema}).status == ServiceStatus::unsupported_version &&
        guest.discover({name,1,1,1,expected_schema}).status == ServiceStatus::unsupported_version,
        "demo echo accepted an incompatible discovery contract");
    WebServices web(generation,registrations,{},web_limits);
    const auto query = record({{1,FieldType::utf8,Bytes(name.begin(),name.end())},
        {2,FieldType::u32,encode_u32(1)}, {3,FieldType::u32,encode_u32(0)},
        {4,FieldType::u32,encode_u32(0)}, {5,FieldType::bytes,Bytes(expected_schema.begin(),expected_schema.end())}});
    require(web.submit(request(1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER,query)) == ServiceStatus::ok &&
        web.pump() == ServiceStatus::ok,"demo web discovery admission/pump");
    const auto discovered = decode(take(web,1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER));
    std::vector<FieldView> fields;
    require(decode_record(discovered.payload,fields) == CodecStatus::ok && fields.size() == 6,
        "demo web discovery descriptor fields");
    for (std::size_t index = 0; index != fields.size(); ++index)
        require(fields[index].id == index + 1 && fields[index].must_understand,"demo descriptor field identity");
    std::uint64_t handle = 0; std::uint32_t major = 0, minor = 0, max_reply = 0;
    require(read_u64(fields[0],handle) && (handle & UINT64_C(0x8000000000000000)) && handle != native.handle &&
        fields[1].type == FieldType::utf8 && Bytes(fields[1].value.begin(),fields[1].value.end()) == Bytes(name.begin(),name.end()) &&
        read_u32(fields[2],major) && major == 1 && read_u32(fields[3],minor) && minor == 0 &&
        fields[4].type == FieldType::bytes && fields[4].value.size() == expected_schema.size() &&
        std::equal(fields[4].value.begin(),fields[4].value.end(),expected_schema.begin()) &&
        read_u32(fields[5],max_reply) && max_reply == 1024 && web.acknowledge(generation,1) == ServiceStatus::ok,
        "demo web handle/descriptor or discovery ACK");

    constexpr std::uint32_t reply_capacity = FOUNDATION_APPENDED_ENVELOPE_BYTES + 1024;
    const auto guest_call = [&](std::uint64_t sequence, std::uint32_t operation, const Bytes& payload,
            ServiceStatus expected) {
        const auto result = decode(gateway_exchange(guest,request(sequence,native.handle,operation,payload),reply_capacity));
        require(result.header.kind == FOUNDATION_APPENDED_MESSAGE_REPLY && result.header.generation == generation &&
            result.header.sequence == sequence && result.header.interface_handle == native.handle &&
            result.header.operation == operation && result.header.service_status == static_cast<std::uint32_t>(expected) &&
            result.header.correlation == 0,"demo guest reply identity/status");
        return result.payload;
    };
    const auto web_call = [&](std::uint64_t sequence, std::uint32_t operation, const Bytes& payload,
            ServiceStatus expected) {
        require(web.submit(request(sequence,handle,operation,payload)) == ServiceStatus::ok &&
            web.pump() == ServiceStatus::ok,"demo web request admission/pump");
        auto result = decode(take(web,sequence,handle,operation,expected));
        require(web.acknowledge(generation,sequence) == ServiceStatus::ok,"demo web call ACK");
        return result.payload;
    };
    std::vector<Bytes> payloads{{},binary,Bytes(1023),Bytes(1024)};
    for (std::size_t index = 2; index != payloads.size(); ++index)
        for (std::size_t offset = 0; offset != payloads[index].size(); ++offset)
            payloads[index][offset] = static_cast<std::uint8_t>(offset * 37 + 17);
    std::uint64_t sequence = 2;
    for (const auto& payload : payloads) {
        require(guest_call(sequence,1,payload,ServiceStatus::ok) == payload &&
            web_call(sequence,1,payload,ServiceStatus::ok) == payload,"demo echo changed binary payload bytes");
        ++sequence;
    }
    for (const auto operation : std::array<std::uint32_t,2>{2,UINT32_MAX}) {
        require(guest_call(sequence,operation,binary,ServiceStatus::unknown_operation).empty() &&
            web_call(sequence,operation,binary,ServiceStatus::unknown_operation).empty(),
            "demo echo unknown operation returned payload bytes");
        ++sequence;
    }
    require(guest_call(sequence,1,oversized,ServiceStatus::limit_exceeded).empty() &&
        web_call(sequence,1,oversized,ServiceStatus::limit_exceeded).empty(),
        "demo echo accepted a request larger than its reply contract");
    ++sequence;

    const auto guest_packet = request(sequence,native.handle,1,binary);
    const auto guest_reply = gateway_exchange(guest,guest_packet,reply_capacity);
    require(decode(guest_reply).payload == binary,"demo guest isolation fixture");
    const auto original = request(sequence,handle,1,binary);
    auto submitted = original;
    {
        WebServices::CallbackScope callback(web);
        require(web.submit(submitted) == ServiceStatus::ok,"demo copied request admission");
        std::fill(submitted.begin(),submitted.end(),0);
        require(web.pump() == ServiceStatus::unavailable && !web.take_completion() &&
            web.acknowledge(generation,sequence) == ServiceStatus::unavailable,
            "demo callback scope entered the service queue");
    }
    require(web.pump() == ServiceStatus::ok,"demo deferred request pump");
    auto owned = take(web,sequence,handle,1);
    const auto saved = owned;
    require(decode(owned).payload == binary,"demo queue borrowed submitted request bytes");
    std::fill(owned.begin(),owned.end(),0);
    require(web.submit(original) == ServiceStatus::ok && take(web,sequence,handle,1) == saved,
        "demo replay borrowed delivered completion bytes");
    auto changed = original; changed.back() ^= 0xff;
    require(web.submit(changed) == ServiceStatus::conflict,"demo replay accepted changed payload bytes");
    require(web.acknowledge(generation,sequence) == ServiceStatus::ok && web.retained_call_count() == 0 &&
        web.retained_bytes() == 0 && web.submit(original) == ServiceStatus::expired &&
        gateway_exchange(guest,guest_packet,reply_capacity) == guest_reply,
        "demo web ACK retained calls or retired the independent guest ledger");
}

void native_consumer() {
    unsigned effects = 0;
    const std::array registrations{NativeServiceRegistration{
        {std::string(service_name),1,0,schema,4},
        [&](std::uint32_t operation, std::span<const std::uint8_t> input,
            std::span<std::uint8_t> output) -> ServiceReply {
            if (operation != 1) return {ServiceStatus::unknown_operation,0};
            if (input.size() != 4 || !std::equal(input.begin(),input.end(),encode_u32(41).begin()))
                return {ServiceStatus::invalid_request,0};
            require(output.size() >= 4,"native response was not reserved");
            ++effects;
            const auto result = encode_u32(51);
            std::copy(result.begin(),result.end(),output.begin());
            return {ServiceStatus::ok,4};
        }}};
    // The same deliberate catalog, with independent request and ACK ledgers.
    Registry guest(generation);
    require(install_native_services(guest,registrations) == ServiceStatus::ok,"guest catalog installation");
    const auto native = guest.discover({service_name,1,0,0,schema});
    require(native.status == ServiceStatus::ok && native.handle != 0,"guest catalog discovery");
    WebServices web(generation,registrations);
    const auto query = record({{1,FieldType::utf8,Bytes(service_name.begin(),service_name.end())},
        {2,FieldType::u32,encode_u32(1)}, {3,FieldType::u32,encode_u32(0)},
        {4,FieldType::u32,encode_u32(0)}, {5,FieldType::bytes,Bytes(schema.begin(),schema.end())}});
    {
        WebServices::CallbackScope callback(web);
        require(web.submit(request(1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER,query)) == ServiceStatus::ok,
            "automatic bootstrap discovery admission");
        require(web.pump() == ServiceStatus::unavailable && !web.take_completion() &&
            web.acknowledge(generation,1) == ServiceStatus::unavailable && effects == 0,
            "callback allowed pumping, completion delivery or ACK");
    }
    require(web.pump() == ServiceStatus::ok,"post-callback discovery pump");
    const auto discovered = decode(take(web,1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER));
    std::vector<FieldView> fields;
    require(decode_record(discovered.payload,fields) == CodecStatus::ok && fields.size() == 6,
        "bootstrap discovery descriptor schema");
    for (std::size_t i = 0; i != fields.size(); ++i)
        require(fields[i].id == i + 1 && fields[i].must_understand,"bootstrap descriptor fields");
    std::uint64_t handle = 0; std::uint32_t major = 0, minor = 0, max_reply = 0;
    require(read_u64(fields[0],handle) && (handle & UINT64_C(0x8000000000000000)) &&
        handle != native.handle && fields[1].type == FieldType::utf8 &&
        Bytes(fields[1].value.begin(),fields[1].value.end()) == Bytes(service_name.begin(),service_name.end()) &&
        read_u32(fields[2],major) && major == 1 && read_u32(fields[3],minor) && minor == 0 &&
        fields[4].type == FieldType::bytes && fields[4].value.size() == schema.size() &&
        std::equal(fields[4].value.begin(),fields[4].value.end(),schema.begin()) &&
        read_u32(fields[5],max_reply) && max_reply == 4,"opaque web handle/descriptor");
    require(web.acknowledge(generation,1) == ServiceStatus::ok,"discovery ACK");

    const auto guest_request = request(2,native.handle,1,encode_u32(41));
    const auto guest_reply = gateway_exchange(guest,guest_request);
    const auto guest_result = decode(guest_reply);
    require(guest_result.header.kind == FOUNDATION_APPENDED_MESSAGE_REPLY &&
        guest_result.header.generation == generation && guest_result.header.sequence == 2 &&
        guest_result.header.interface_handle == native.handle && guest_result.header.operation == 1 &&
        guest_result.header.service_status == FOUNDATION_APPENDED_SERVICE_OK &&
        guest_result.payload == encode_u32(51) && effects == 1,"guest native invocation");
    const auto original = request(2,handle,1,encode_u32(41));
    auto submitted = original;
    {
        WebServices::CallbackScope callback(web);
        require(web.submit(submitted) == ServiceStatus::ok && effects == 1,"submit executed a native effect");
        std::fill(submitted.begin(),submitted.end(),0);
        require(web.pump() == ServiceStatus::unavailable && effects == 1,"callback executed queued work");
    }
    require(web.pump() == ServiceStatus::ok && effects == 2,"independent native request ledger");
    auto owned = take(web,2,handle,1);
    const auto saved = owned;
    require(decode(owned).payload == encode_u32(51) && !web.take_completion(),"owned native completion");
    std::fill(owned.begin(),owned.end(),0);
    require(web.submit(original) == ServiceStatus::ok && take(web,2,handle,1) == saved && effects == 2,
        "web replay borrowed delivered bytes or repeated the effect");
    require(web.acknowledge(generation,2) == ServiceStatus::ok && web.retained_call_count() == 0 &&
        web.retained_bytes() == 0 && web.submit(original) == ServiceStatus::expired,"web ACK retirement");
    require(gateway_exchange(guest,guest_request) == guest_reply && effects == 2,
        "web ACK retired the independent guest outcome");
    const auto ack = record({{1,FieldType::u64,encode_u64(2)}});
    require(decode(gateway_exchange(guest,request(3,0,FOUNDATION_APPENDED_CONTROL_ACKNOWLEDGE,ack))).header.service_status ==
        FOUNDATION_APPENDED_SERVICE_OK,"guest ACK retirement");
    require(decode(gateway_exchange(guest,guest_request)).header.service_status == FOUNDATION_APPENDED_SERVICE_EXPIRED &&
        decode(saved).payload == encode_u32(51) && effects == 2,"owned completion changed after retirement");
}

void queued_calls_follow_actual_native_lifecycle() {
    unsigned effects = 0;
    WebServices* actual = nullptr;
    const std::array registrations{NativeServiceRegistration{
        {std::string(service_name),1,0,schema,4},
        [&](std::uint32_t operation, std::span<const std::uint8_t> input,
            std::span<std::uint8_t> output) -> ServiceReply {
            require(actual && operation == 1 && input.size() == 4 && output.size() >= 4,
                "queued-call actual native fixture");
            require(!actual->has_queued_calls() && actual->retained_call_count() == 1,
                "running native call was reported as queued");
            ++effects;
            const auto value = encode_u32(51);
            std::copy(value.begin(),value.end(),output.begin());
            return {ServiceStatus::ok,4};
        }}};
    WebServices web(generation,registrations);
    actual = &web;
    const WebServices& observed = web;
    static_assert(noexcept(observed.has_queued_calls()));
    require(!observed.has_queued_calls(),"fresh queue reported queued work");
    const auto query = record({{1,FieldType::utf8,Bytes(service_name.begin(),service_name.end())},
        {2,FieldType::u32,encode_u32(1)}, {3,FieldType::u32,encode_u32(0)},
        {4,FieldType::u32,encode_u32(0)}, {5,FieldType::bytes,Bytes(schema.begin(),schema.end())}});
    require(web.submit(request(1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER,query)) == ServiceStatus::ok &&
        observed.has_queued_calls() && observed.has_queued_calls() && effects == 0,
        "queued discovery was hidden or inspection changed it");
    require(web.pump() == ServiceStatus::ok && !observed.has_queued_calls() &&
        web.retained_call_count() == 1,"ready discovery was reported as queued");
    const auto discovered = decode(take(web,1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER));
    std::vector<FieldView> fields;
    std::uint64_t handle = 0;
    require(decode_record(discovered.payload,fields) == CodecStatus::ok && fields.size() == 6 &&
        read_u64(fields[0],handle) && handle && !observed.has_queued_calls() &&
        web.acknowledge(generation,1) == ServiceStatus::ok,"queued-call native handle fixture");

    {
        WebServices::CallbackScope callback(web);
        require(web.submit(request(2,handle,1,encode_u32(41))) == ServiceStatus::ok &&
            observed.has_queued_calls() && effects == 0,
            "callback scope hid queued native work or inspection executed it");
        require(web.pump() == ServiceStatus::unavailable && observed.has_queued_calls() && effects == 0,
            "blocked callback pump changed queued native work");
    }
    require(observed.has_queued_calls() && web.pump() == ServiceStatus::ok && effects == 1 &&
        !observed.has_queued_calls() && web.retained_call_count() == 1,
        "ready native completion was reported as queued");
    require(decode(take(web,2,handle,1)).payload == encode_u32(51) &&
        !observed.has_queued_calls() && web.retained_call_count() == 1,
        "delivered native completion was reported as queued");

    require(web.submit(request(3,handle,1,encode_u32(41))) == ServiceStatus::ok &&
        web.submit(request(4,handle,1,encode_u32(41))) == ServiceStatus::ok &&
        observed.has_queued_calls() && web.cancel(generation,3) == ServiceStatus::ok &&
        observed.has_queued_calls(),"cancellation hid a different queued native call");
    require(web.cancel(generation,4) == ServiceStatus::ok && !observed.has_queued_calls() &&
        web.retained_call_count() == 3 && effects == 1,
        "canceled native calls were reported as queued or executed");
    require(web.submit(request(5,handle,1,encode_u32(41))) == ServiceStatus::ok &&
        observed.has_queued_calls(),"retained native completions hid new queued work");
    web.close();
    require(web.closed() && !observed.has_queued_calls() && web.retained_call_count() == 4 &&
        web.pump() == ServiceStatus::closed && effects == 1,
        "closed native queue reported queued work or executed canceled work");
}

void closed_completion_copy_preserves_actual_outcomes_and_retention() {
    unsigned effects = 0;
    WebServices* actual = nullptr;
    std::array<std::uint8_t,512> output;
    output.fill(0xa5);
    std::uint64_t sequence = 811;
    std::uint32_t written = 919;
    const auto untouched = [&] {
        return sequence == 811 && written == 919 &&
            std::all_of(output.begin(),output.end(),[](auto byte) { return byte == 0xa5; });
    };
    const std::array registrations{NativeServiceRegistration{
        {std::string(service_name),1,0,schema,4},
        [&](std::uint32_t operation, std::span<const std::uint8_t> input,
            std::span<std::uint8_t> reply) -> ServiceReply {
            if (operation != 1 || input.size() != 4) return {ServiceStatus::invalid_request,0};
            require(reply.size() >= 4 && actual,"closed-copy actual native fixture");
            ++effects;
            // A recursive retirement request closes admission immediately. The
            // running effect still owns its real result until the pump unwinds.
            actual->close();
            require(actual->copy_closed_completion(output,sequence,written) == ServiceStatus::unavailable &&
                untouched() && actual->acknowledge(generation,3) == ServiceStatus::unavailable,
                "inflight retirement copied or acknowledged an unfinished actual native effect");
            const auto value = encode_u32(51);
            std::copy(value.begin(),value.end(),reply.begin());
            return {ServiceStatus::ok,4};
        }}};
    WebServices web(generation,registrations);
    actual = &web;
    require(web.copy_closed_completion(output,sequence,written) == ServiceStatus::conflict && untouched(),
        "active queue exposed a retirement completion or changed caller output");
    const auto query = record({{1,FieldType::utf8,Bytes(service_name.begin(),service_name.end())},
        {2,FieldType::u32,encode_u32(1)}, {3,FieldType::u32,encode_u32(0)},
        {4,FieldType::u32,encode_u32(0)}, {5,FieldType::bytes,Bytes(schema.begin(),schema.end())}});
    require(web.submit(request(1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER,query)) == ServiceStatus::ok &&
        web.pump() == ServiceStatus::ok,"closed-copy discovery fixture");
    const auto discovered = decode(take(web,1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER));
    std::vector<FieldView> fields;
    std::uint64_t handle = 0;
    require(decode_record(discovered.payload,fields) == CodecStatus::ok && fields.size() == 6 &&
        read_u64(fields[0],handle) && handle && web.acknowledge(generation,1) == ServiceStatus::ok,
        "closed-copy native handle fixture");

    // Gaps are deliberate: retirement must inspect actual retained calls,
    // rather than inventing completions for missing integer sequences.
    require(web.submit(request(3,handle,1,encode_u32(41))) == ServiceStatus::ok &&
        web.submit(request(7,handle,1,encode_u32(42))) == ServiceStatus::ok &&
        web.pump(1) == ServiceStatus::ok && web.closed() && effects == 1,
        "recursive close ran queued work or lost the running native effect");
    const auto delivered = take(web,3,handle,1);
    require(decode(delivered).payload == encode_u32(51) && web.retained_call_count() == 2,
        "running native result was rewritten or delivered without retention");
    const auto retained = web.retained_bytes();
    {
        WebServices::CallbackScope outer(web);
        {
            WebServices::CallbackScope inner(web);
            require(web.copy_closed_completion(output,sequence,written) == ServiceStatus::unavailable &&
                untouched() && web.acknowledge(generation,3) == ServiceStatus::unavailable,
                "nested callback copied or acknowledged closed-queue outcomes");
        }
        require(web.copy_closed_completion(output,sequence,written) == ServiceStatus::unavailable && untouched(),
            "inner callback exit released the closed-copy outer callback barrier");
    }
    require(web.copy_closed_completion(std::span(output).first(delivered.size()-1),sequence,written) ==
        ServiceStatus::limit_exceeded && untouched() && web.retained_call_count() == 2 &&
        web.retained_bytes() == retained && effects == 1,
        "short retirement copy changed caller output, retention or native effects");

    require(web.copy_closed_completion(output,sequence,written) == ServiceStatus::ok && sequence == 3 &&
        written == delivered.size() && Bytes(output.begin(),output.begin()+written) == delivered &&
        web.retained_call_count() == 2 && web.retained_bytes() == retained && effects == 1,
        "closed copy failed to preserve an already-delivered exact native completion");
    std::fill(output.begin(),output.end(),0);
    require(web.copy_closed_completion(output,sequence,written) == ServiceStatus::ok && sequence == 3 &&
        Bytes(output.begin(),output.begin()+written) == delivered && effects == 1,
        "repeat retirement copy borrowed caller bytes or repeated the native effect");
    require(web.acknowledge(generation,3) == ServiceStatus::ok && web.retained_call_count() == 1,
        "actual retirement ACK did not retire only the copied lower prefix");

    require(web.copy_closed_completion(output,sequence,written) == ServiceStatus::ok && sequence == 7,
        "actual lower-prefix ACK did not expose the next retained call");
    const auto queued = Bytes(output.begin(),output.begin()+written);
    const auto closed = decode(queued);
    require(closed.header.kind == FOUNDATION_APPENDED_MESSAGE_COMPLETION && closed.header.generation == generation &&
        closed.header.sequence == 7 && closed.header.interface_handle == handle && closed.header.operation == 1 &&
        closed.header.service_status == FOUNDATION_APPENDED_SERVICE_CLOSED && closed.header.correlation == 0 &&
        closed.payload.empty() && effects == 1,
        "queued retirement fabricated success, ran the handler or changed canonical completion identity");
    const auto normally_delivered = web.take_completion();
    require(normally_delivered && *normally_delivered == queued && !web.take_completion(),
        "read-only retirement copy mutated normal completion delivery state");
    require(web.copy_closed_completion(output,sequence,written) == ServiceStatus::ok && sequence == 7 &&
        Bytes(output.begin(),output.begin()+written) == queued && effects == 1,
        "normal delivery hid or changed the exact retained closed completion");
    require(web.acknowledge(generation,7) == ServiceStatus::ok && web.retained_call_count() == 0 &&
        web.retained_bytes() == 0,"actual closed-queue ACK did not release retained storage");
    output.fill(0xa5); sequence = 811; written = 919;
    require(web.copy_closed_completion(output,sequence,written) == ServiceStatus::not_found && untouched() &&
        web.pump() == ServiceStatus::closed && effects == 1,
        "empty closed queue exposed an outcome, changed output or executed another effect");
}
} // namespace

int main() {
    try {
        demo_echo_catalog_contract();
        native_consumer();
        queued_calls_follow_actual_native_lifecycle();
        closed_completion_copy_preserves_actual_outcomes_and_retention();
        std::cout << "appended native web service consumer passed\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
