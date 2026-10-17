// SPDX-License-Identifier: CC0-1.0
#include "../gui/shared/appended_engine_abi.h"
#include "../gui/shared/appended_engine_input_codec.hpp"
#include "../gui/shared/appended_engine_owner.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <memory>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

using namespace foundation::appended;
namespace input = foundation::appended::engine_input;
namespace {
std::size_t assertions{};
void require(bool value, const char* reason) {
    ++assertions;
    if (!value) throw std::runtime_error(reason);
}
void put(Bytes& bytes, std::size_t offset, std::uint64_t value, unsigned count) {
    require(offset <= bytes.size() && count <= bytes.size() - offset, "fixture output range");
    for (unsigned i = 0; i < count; ++i) bytes[offset + i] = static_cast<std::uint8_t>(value >> (8 * i));
}
std::uint64_t get(std::span<const std::uint8_t> bytes, std::size_t offset, unsigned count) {
    require(offset <= bytes.size() && count <= bytes.size() - offset, "fixture input range");
    std::uint64_t value{};
    for (unsigned i = 0; i < count; ++i) value |= std::uint64_t(bytes[offset + i]) << (8 * i);
    return value;
}
Bytes record(std::uint32_t operation, EngineIdentity target, const Bytes& payload = {}, std::uint64_t transfer = 0) {
    Bytes bytes(FOUNDATION_ENGINE_HEADER_BYTES + payload.size());
    bytes[0] = 'F'; bytes[1] = 'K'; bytes[2] = 'B'; bytes[3] = '1';
    put(bytes, 4, 1, 2); put(bytes, 6, operation, 2); put(bytes, 8, bytes.size(), 4);
    put(bytes, 16, target.worker_epoch, 8); put(bytes, 24, target.application_instance, 8);
    put(bytes, 32, target.document_sequence, 8); put(bytes, 40, target.service_generation, 8);
    put(bytes, 48, transfer, 8); put(bytes, 64, payload.size(), 4);
    std::copy(payload.begin(), payload.end(), bytes.begin() + FOUNDATION_ENGINE_HEADER_BYTES);
    return bytes;
}
struct Reply {
    EngineIdentity target;
    std::uint64_t transfer{};
    std::uint32_t control{}, service{};
    Bytes bytes;
    std::span<const std::uint8_t> body() const { return std::span(bytes).subspan(FOUNDATION_ENGINE_RECEIPT_BYTES); }
};
Reply call(EngineOwner& owner, std::uint32_t operation, EngineIdentity target,
           const Bytes& payload = {}, std::uint64_t transfer = 0, std::size_t capacity = 8192) {
    const auto bytes = record(operation, target, payload, transfer);
    Bytes output(capacity, 0xa5);
    const auto written = owner.dispatch(operation, bytes, output);
    require(written >= static_cast<std::int32_t>(FOUNDATION_ENGINE_RECEIPT_BYTES) &&
        static_cast<std::size_t>(written) <= output.size(), "copied owner did not return a complete receipt");
    output.resize(static_cast<std::size_t>(written));
    require(output[0] == 'F' && output[1] == 'K' && output[2] == 'B' && output[3] == '1' &&
        get(output, 4, 2) == 1 && get(output, 6, 2) == (operation | FOUNDATION_ENGINE_REPLY_KIND) &&
        get(output, 8, 4) == output.size() && get(output, 64, 4) == output.size() - FOUNDATION_ENGINE_HEADER_BYTES,
        "copied owner receipt identity/length was malformed");
    Reply result{{get(output, 16, 8), get(output, 24, 8), get(output, 32, 8), get(output, 40, 8)},
        get(output, 48, 8), static_cast<std::uint32_t>(get(output, 72, 4)),
        static_cast<std::uint32_t>(get(output, 76, 4)), std::move(output)};
    return result;
}
void ok(const Reply& reply, const char* reason) {
    require(reply.control == FOUNDATION_ENGINE_OK && reply.service == FOUNDATION_APPENDED_SERVICE_OK, reason);
}
void short_reply(EngineOwner& owner, std::uint32_t operation, EngineIdentity target,
                 const Bytes& payload, std::uint64_t transfer, std::size_t capacity) {
    const auto bytes = record(operation, target, payload, transfer);
    Bytes output(capacity, 0xa5);
    require(owner.dispatch(operation, bytes, output) == FOUNDATION_ENGINE_REPLY_TOO_SMALL &&
        std::all_of(output.begin(), output.end(), [](auto byte) { return byte == 0xa5; }),
        "short complete receipt mutated output or was accepted");
}
Package package() {
    Package value;
    value.application = {"org.example.input-owner", "Copied input owner fixture", "1.0.0"};
    value.web = {true, "web/index.html", {}};
    value.capabilities = {"foundation.startup.v1"};
    value.package_sha256 = std::string(64, '1');
    const std::string startup = "{\"kind\":\"foundation-appended-startup\",\"primary\":\"web\",\"schema_version\":1}";
    value.files = {{"web/.foundation/startup-v1.json", "web", "application/json", std::string(64, '2'),
        Bytes(startup.begin(), startup.end())}, {"web/index.html", "web", "text/html", std::string(64, '3'), {}}};
    return value;
}
input::EngineSurfaceProfileFacts facts() {
    // Synthetic build/source pins with the exact catalog; no retained runtime evidence.
    input::EngineSurfaceProfileFacts value;
    value.enabled = true; value.name = input::kInputProfileName;
    value.contract_sha256 = input::kProviderContractSha256;
    value.build_sha256.fill(0x11); value.source_recipe_sha256.fill(0x22); value.catalog_sha256 = input::kInputCatalogSha256;
    value.provider_capabilities = input::kProviderCapabilities; value.surface_capabilities = input::kSurfaceCapabilities;
    value.surface_protocol_version = input::kSurfaceProtocolVersion; value.mouse_input_version = input::kMouseInputVersion;
    value.raw_key_mapping_revision = input::kRawKeyMappingRevision;
    value.viewport_width = 800; value.viewport_height = 600; value.display_scale = 1; value.commands = input::kCommands;
    require(input::input_profile_valid(value), "synthetic exact input profile was invalid");
    return value;
}
Bytes focus(std::uint64_t context, unsigned action = 1) {
    input::Focus value = action == 2 ? input::Focus{2, 0, 0, 3, 0, context} :
        action == 1 ? input::Focus{1, 0, 0, 0, context, 0} : input::Focus{0, 1, 1, 0, context, context};
    Bytes bytes; require(input::encode_focus(value, bytes) == input::Status::ok, "fixture FOCUS encoding"); return bytes;
}
Bytes key(std::uint64_t context) {
    Bytes bytes;
    require(input::encode_key({0, 0, 0, 0, context, "a", "KeyA"}, bytes) == input::Status::ok,
        "fixture KEY encoding");
    return bytes;
}
Bytes result_bytes(std::uint64_t ticket, std::uint32_t disposition = 1, bool handled = false, std::int32_t status = 0) {
    Bytes bytes;
    require(input::encode_command_result({status, disposition, ticket, 0, handled ? 1u : 0u}, bytes) == input::Status::ok,
        "fixture actual provider result encoding");
    return bytes;
}
void turn(EngineOwner& owner, const Reply& input_reply) {
    ok(call(owner, FOUNDATION_ENGINE_TURN_ENTER, input_reply.target, {}, input_reply.transfer), "input TURN_ENTER failed");
    ok(call(owner, FOUNDATION_ENGINE_TURN_LEAVE, input_reply.target, {}, input_reply.transfer), "input TURN_LEAVE failed");
}
void settle(EngineOwner& owner, const Reply& pending, std::uint64_t ticket,
            std::uint32_t disposition = 1, bool handled = false, std::int32_t status = 0) {
    turn(owner, pending);
    ok(call(owner, FOUNDATION_ENGINE_COMMAND_RESULT, pending.target,
        result_bytes(ticket, disposition, handled, status), pending.transfer, 104), "actual command result did not settle");
}
void accept(EngineOwner& owner, const Reply& delivery, std::uint32_t operation = FOUNDATION_ENGINE_DELIVERY_RESULT) {
    turn(owner, delivery);
    ok(call(owner, operation, delivery.target, encode_u32(FOUNDATION_ENGINE_ACCEPTED), delivery.transfer),
        "actual copied outcome did not settle");
}
struct Completion { Envelope envelope; Bytes payload; };
Completion completion(const Reply& value) {
    Completion output; std::span<const std::uint8_t> payload;
    require(decode_envelope(value.body(), output.envelope, payload) == CodecStatus::ok &&
        output.envelope.kind == FOUNDATION_APPENDED_MESSAGE_COMPLETION, "actual WebServices completion was malformed");
    output.payload.assign(payload.begin(), payload.end()); return output;
}
struct Fixture {
    static constexpr std::string_view service_name = "org.example.input-owner.native";
    std::unique_ptr<EngineOwner> owner;
    EngineIdentity target{17, 23, 0, 0};
    std::uint64_t context{}, expected_effect_context{}, handle{}, held_ticket{};
    unsigned effects{};
    bool app_admission{}, retirement_consumed{true}, hold_on_entry{}, close_on_entry{}, throw_on_entry{};

    explicit Fixture(bool abandon = false) {
        EngineOwnerConfiguration config;
        config.worker_epoch = target.worker_epoch; config.application_instance = target.application_instance;
        config.input_profile = facts(); config.abandon_closed_document_outcomes = abandon;
        config.native_services.push_back({{std::string(service_name), 1, 0, SchemaId{1}, 4},
            [&](std::uint32_t operation, auto bytes, auto output) -> ServiceReply {
                require(owner && operation == 1 && bytes.size() == 4 && output.size() >= 4,
                    "actual native Registry invocation fixture");
                const auto effect = owner->native_effect();
                require(effect && effect->entered && effect->target == target &&
                    effect->input_context == expected_effect_context && !app_admission && retirement_consumed,
                    "native handler entered before trusted app admission closed and exact context retirement settled");
                require(owner->input_suspended() && !owner->stage_command(target, expected_effect_context,
                    1, input::kKeySchema, key(expected_effect_context ? expected_effect_context : 1)),
                    "actual native handler admitted physical input recursively");
                if (hold_on_entry) {
                    require(owner->hold_native_effect(effect->ticket), "actual handler could not retain a UI hold");
                    held_ticket = effect->ticket;
                }
                ++effects;
                if (throw_on_entry) throw std::runtime_error("deliberate actual native effect failure");
                if (close_on_entry) owner->close();
                const auto value = encode_u32(static_cast<std::uint32_t>(get(bytes, 0, 4)) + 1);
                std::copy(value.begin(), value.end(), output.begin());
                return {ServiceStatus::ok, 4};
            }});
        owner = std::make_unique<EngineOwner>(package(), std::move(config));
        ok(call(*owner, FOUNDATION_ENGINE_CONFIGURE, target), "input owner CONFIGURE failed");
        target.document_sequence = 1;
        target = call(*owner, FOUNDATION_ENGINE_BEGIN_DOCUMENT, target).target;
        require(target.service_generation && owner->input_enabled() && !owner->has_module(), "VM-free input owner was not ready");
    }
    Reply peek() { return call(*owner, FOUNDATION_ENGINE_PEEK_INPUT, target); }
    std::uint64_t stage(std::uint64_t value, std::uint32_t operation, const input::Digest& schema,
                        Bytes payload, bool lifecycle = false) {
        const auto ticket = owner->stage_command(target, value, operation, schema, std::move(payload), lifecycle);
        require(bool(ticket), "valid input command was not staged"); return *ticket;
    }
    std::uint64_t bind(std::uint64_t value) {
        const auto ticket = stage(value, 3, input::kFocusSchema, focus(value), true);
        const auto pending = peek(); ok(pending, "BIND was not exposed"); settle(*owner, pending, ticket);
        const auto outcome = owner->command_outcome(ticket);
        require(outcome && outcome->status == EngineInputCommandStatus::consumed && !outcome->handled,
            "BIND did not consume its actual unhandled result");
        context = value; app_admission = true; retirement_consumed = false; return ticket;
    }
    Bytes request(std::uint64_t sequence, std::uint64_t service_handle, std::uint32_t operation, const Bytes& payload) {
        Envelope envelope; envelope.generation = target.service_generation; envelope.sequence = sequence;
        envelope.interface_handle = service_handle; envelope.operation = operation;
        Bytes bytes; require(encode_envelope(envelope, payload, bytes) == CodecStatus::ok, "native request fixture encoding");
        return bytes;
    }
    void submit(const Bytes& bytes) { ok(call(*owner, FOUNDATION_ENGINE_SUBMIT, target, bytes), "native request admission failed"); }
    void submit(std::uint64_t sequence) { submit(request(sequence, handle, 1, encode_u32(41))); }
    std::uint64_t prepare_effect() {
        const auto before = effects;
        const auto gate = call(*owner, FOUNDATION_ENGINE_PUMP_ONE, target);
        require(gate.control == FOUNDATION_ENGINE_CONFLICT && gate.service == FOUNDATION_APPENDED_SERVICE_UNAVAILABLE &&
            effects == before, "native handler ran before trusted effect acknowledgment");
        const auto effect = owner->native_effect();
        require(effect && !effect->entered && effect->target == target && effect->input_context == context &&
            owner->input_suspended(), "queued native request did not publish its exact context barrier");
        require(!owner->hold_native_effect(effect->ticket) && !owner->release_native_effect(effect->ticket) &&
            !owner->acknowledge_native_effect(effect->ticket + 1), "unentered or foreign effect gained hold/ACK authority");
        expected_effect_context = context;
        app_admission = false;
        if (context) {
            require(!owner->acknowledge_native_effect(effect->ticket), "effect ACK skipped actual context retirement");
            const auto ticket = stage(context, 3, input::kFocusSchema, focus(context, 2), true);
            const auto pending = peek(); ok(pending, "effect context retirement was not exposed");
            turn(*owner, pending);
            require(!owner->acknowledge_native_effect(effect->ticket), "returned retirement TURN skipped actual result settlement");
            ok(call(*owner, FOUNDATION_ENGINE_COMMAND_RESULT, pending.target, result_bytes(ticket), pending.transfer, 104),
                "effect context retirement result failed");
            const auto outcome = owner->command_outcome(ticket);
            require(outcome && outcome->status == EngineInputCommandStatus::consumed,
                "native effect retirement did not consume actual provider result");
            context = 0;
        }
        retirement_consumed = true;
        require(owner->acknowledge_native_effect(effect->ticket), "trusted exact native effect ACK was refused");
        require(!owner->stage_command(target, expected_effect_context + 1,
            3, input::kFocusSchema, focus(expected_effect_context + 1), true), "acknowledged native effect admitted a fresh context");
        return effect->ticket;
    }
    Reply execute_effect() {
        prepare_effect();
        const auto pumped = call(*owner, FOUNDATION_ENGINE_PUMP_ONE, target);
        ok(pumped, "known exact native effect did not complete normally"); return pumped;
    }
    Reply delivery(std::uint64_t sequence, std::uint32_t status = FOUNDATION_APPENDED_SERVICE_OK) {
        const auto value = call(*owner, FOUNDATION_ENGINE_PEEK_DELIVERY, target); ok(value, "actual native delivery missing");
        const auto decoded = completion(value);
        require(decoded.envelope.sequence == sequence && decoded.envelope.generation == target.service_generation &&
            decoded.envelope.service_status == status, "native delivery changed exact generation/sequence/status");
        require(call(*owner, FOUNDATION_ENGINE_PEEK_DELIVERY, target).bytes == value.bytes, "native delivery peek was destructive");
        return value;
    }
    void acknowledge(std::uint64_t through) {
        const auto staged = call(*owner, FOUNDATION_ENGINE_STAGE_ACK, target, encode_u64(through));
        require(staged.control == FOUNDATION_ENGINE_OK && staged.service == FOUNDATION_APPENDED_SERVICE_UNAVAILABLE,
            "native ACK was not staged");
        ok(call(*owner, FOUNDATION_ENGINE_PUMP_ONE, target), "actual native ACK failed");
        const auto receipt = call(*owner, FOUNDATION_ENGINE_PEEK_ACK_RECEIPT, target); ok(receipt, "actual ACK receipt missing");
        require(receipt.body().size() == 12 && get(receipt.body(), 0, 8) == through, "actual ACK prefix changed");
        accept(*owner, receipt, FOUNDATION_ENGINE_ACK_RECEIPT_RESULT);
    }
    void discover(bool retire = true) {
        const auto major = encode_u32(1), minor = encode_u32(0);
        const std::array<FieldView, 4> fields{{{1, FieldType::utf8, true,
            {reinterpret_cast<const std::uint8_t*>(service_name.data()), service_name.size()}},
            {2, FieldType::u32, true, major}, {3, FieldType::u32, true, minor}, {4, FieldType::u32, true, minor}}};
        Bytes query; require(encode_record(fields, query) == CodecStatus::ok, "native discovery fixture encoding");
        submit(request(1, 0, FOUNDATION_APPENDED_CONTROL_DISCOVER, query));
        execute_effect();
        require(!owner->native_effect() && !owner->input_suspended() && effects == 0,
            "known discovery completion retained an effect hold or ran a service");
        const auto value = delivery(1); const auto decoded = completion(value);
        std::vector<FieldView> descriptor;
        require(decode_record(decoded.payload, descriptor) == CodecStatus::ok && descriptor.size() == 6 &&
            read_u64(descriptor[0], handle) && handle, "actual native Registry discovery did not issue a route");
        accept(*owner, value); if (retire) acknowledge(1);
    }
};

void mailbox_reservation_and_exact_results() {
    Fixture fixture; auto& owner = *fixture.owner;
    require(call(owner, FOUNDATION_ENGINE_PEEK_INPUT, fixture.target).control == FOUNDATION_ENGINE_EMPTY,
        "fresh input mailbox was not empty");
    auto payload = focus(7); const auto original = payload;
    const auto ticket = fixture.stage(7, 3, input::kFocusSchema, payload, true);
    std::fill(payload.begin(), payload.end(), 0);
    require(!owner.stage_command(fixture.target, 8, 3, input::kFocusSchema, focus(8), true), "one-slot mailbox admitted a second command");
    for (std::size_t capacity : {std::size_t(80), std::size_t(167)})
        short_reply(owner, FOUNDATION_ENGINE_PEEK_INPUT, fixture.target, {}, 0, capacity);
    require(call(owner, FOUNDATION_ENGINE_TURN_ENTER, fixture.target, {}, 1).control == FOUNDATION_ENGINE_CONFLICT,
        "short PEEK exposed a command before its complete bytes fit");
    const auto pending = call(owner, FOUNDATION_ENGINE_PEEK_INPUT, fixture.target, {}, 0, 168); ok(pending, "complete BIND PEEK failed");
    input::Command command;
    require(pending.target == fixture.target && pending.transfer && input::decode_command(pending.body(), command) == input::Status::ok &&
        command.operation == 3 && command.request_sequence == ticket && command.schema_sha256 == input::kFocusSchema &&
        command.payload == original, "immutable copied BIND mailbox lost its exact command identity or bytes");
    require(fixture.peek().bytes == pending.bytes && fixture.peek().bytes == pending.bytes,
        "repeated PEEK changed or consumed the immutable command");
    require(call(owner, FOUNDATION_ENGINE_COMMAND_RESULT, pending.target, result_bytes(ticket), pending.transfer, 104).control ==
        FOUNDATION_ENGINE_STALE, "command settled without an actual TURN");
    ok(call(owner, FOUNDATION_ENGINE_TURN_ENTER, pending.target, {}, pending.transfer), "BIND actual TURN failed");
    require(call(owner, FOUNDATION_ENGINE_COMMAND_RESULT, pending.target, result_bytes(ticket), pending.transfer, 104).control ==
        FOUNDATION_ENGINE_CONFLICT, "command result settled during native TURN");
    ok(call(owner, FOUNDATION_ENGINE_TURN_LEAVE, pending.target, {}, pending.transfer), "BIND native TURN failed to leave");
    require(call(owner, FOUNDATION_ENGINE_TURN_ENTER, pending.target, {}, pending.transfer).control == FOUNDATION_ENGINE_CONFLICT,
        "already entered command allowed a second native TURN");
    const auto actual = result_bytes(ticket);
    for (std::size_t capacity : {std::size_t(80), std::size_t(103)}) {
        short_reply(owner, FOUNDATION_ENGINE_COMMAND_RESULT, pending.target, actual, pending.transfer, capacity);
        const auto outcome = owner.command_outcome(ticket);
        require(outcome && outcome->status == EngineInputCommandStatus::pending, "short RESULT104 settled a command");
    }
    ok(call(owner, FOUNDATION_ENGINE_COMMAND_RESULT, pending.target, actual, pending.transfer, 104), "complete RESULT104 did not settle BIND");
    const auto outcome = owner.command_outcome(ticket);
    require(outcome && outcome->status == EngineInputCommandStatus::consumed && outcome->provider_status == 0 && !outcome->handled,
        "consumed/unhandled BIND was confused with rejection");
    ok(call(owner, FOUNDATION_ENGINE_COMMAND_RESULT, pending.target, actual, pending.transfer, 104), "exact duplicate result was not idempotent");
    require(call(owner, FOUNDATION_ENGINE_COMMAND_RESULT, pending.target, result_bytes(ticket, 1, true), pending.transfer, 104).control ==
        FOUNDATION_ENGINE_CONFLICT, "conflicting duplicate actual result was accepted");
    require(fixture.peek().control == FOUNDATION_ENGINE_EMPTY &&
        call(owner, FOUNDATION_ENGINE_TURN_ENTER, pending.target, {}, pending.transfer).control != FOUNDATION_ENGINE_OK,
        "consumed/unhandled command was replayed");
    Bytes maximum;
    require(input::encode_key({0, 0, 0, 0, 7, std::string(64, 'a'), std::string(64, 'K')}, maximum) == input::Status::ok &&
        maximum.size() == 160, "maximum mailbox KEY fixture encoding");
    const auto key_ticket = fixture.stage(7, 1, input::kKeySchema, maximum);
    require(key_ticket > ticket, "owner input ticket was reused");
    short_reply(owner, FOUNDATION_ENGINE_PEEK_INPUT, fixture.target, {}, 0, 295);
    const auto key_pending = call(owner, FOUNDATION_ENGINE_PEEK_INPUT, fixture.target, {}, 0, 296);
    ok(key_pending, "BIND result did not establish exact input context");
    require(key_pending.bytes.size() == 296 && fixture.peek().bytes == key_pending.bytes,
        "maximum216 command did not fit exactly in its full296 mailbox receipt");
    settle(owner, key_pending, key_ticket, 1, true);
}

void strict_target_context_and_schema() {
    Fixture fixture; auto& owner = *fixture.owner; fixture.bind(11);
    for (unsigned component = 0; component < 4; ++component) {
        auto stale = fixture.target;
        switch (component) {
        case 0: ++stale.worker_epoch; break; case 1: ++stale.application_instance; break;
        case 2: ++stale.document_sequence; break; case 3: ++stale.service_generation; break;
        }
        require(!owner.stage_command(stale, 11, 1, input::kKeySchema, key(11)), "input accepted a substituted target component");
    }
    auto wrong_hash = input::kKeySchema; wrong_hash[0] ^= 1;
    require(!owner.stage_command(fixture.target, 11, 1, wrong_hash, key(11)) &&
        !owner.stage_command(fixture.target, 12, 1, input::kKeySchema, key(11)) &&
        !owner.stage_command(fixture.target, 11, 1, input::kKeySchema, key(12)) &&
        !owner.stage_command(fixture.target, 11, 1, input::kKeySchema, key(11), true) &&
        !owner.stage_command(fixture.target, 11, 2, input::kKeySchema, key(11)),
        "input schema, outer/payload context, lifecycle or catalog substitution was accepted");
    const auto ticket = fixture.stage(11, 1, input::kKeySchema, key(11)); const auto pending = fixture.peek();
    turn(owner, pending);
    for (unsigned component = 0; component < 4; ++component) {
        auto stale = pending.target;
        switch (component) {
        case 0: ++stale.worker_epoch; break; case 1: ++stale.application_instance; break;
        case 2: ++stale.document_sequence; break; case 3: ++stale.service_generation; break;
        }
        require(call(owner, FOUNDATION_ENGINE_COMMAND_RESULT, stale, result_bytes(ticket), pending.transfer, 104).control !=
            FOUNDATION_ENGINE_OK, "command result accepted a substituted target component");
    }
    require(call(owner, FOUNDATION_ENGINE_COMMAND_RESULT, pending.target, result_bytes(ticket + 1), pending.transfer, 104).control ==
        FOUNDATION_ENGINE_STALE && call(owner, FOUNDATION_ENGINE_COMMAND_RESULT, pending.target,
        result_bytes(ticket), pending.transfer + 1, 104).control == FOUNDATION_ENGINE_STALE,
        "command result accepted a foreign ticket or transfer");
    const auto outcome = owner.command_outcome(ticket);
    require(outcome && outcome->status == EngineInputCommandStatus::pending, "invalid result changed the pending input outcome");
    for (unsigned malformed = 0; malformed < 5; ++malformed) {
        auto bytes = result_bytes(ticket);
        switch (malformed) {
        case 0: bytes.pop_back(); break;
        case 1: bytes.push_back(0); break;
        case 2: put(bytes, 20, 2, 4); break;
        case 3: put(bytes, 16, 1, 4); break;
        case 4: put(bytes, 4, 0, 4); break;
        }
        const auto malformed_result = call(owner, FOUNDATION_ENGINE_COMMAND_RESULT, pending.target, bytes, pending.transfer, 104);
        const auto still_pending = owner.command_outcome(ticket);
        require(malformed_result.control == FOUNDATION_ENGINE_INVALID && still_pending &&
            still_pending->status == EngineInputCommandStatus::pending,
            "malformed actual result settled or erased the pending command");
    }
    ok(call(owner, FOUNDATION_ENGINE_COMMAND_RESULT, pending.target, result_bytes(ticket), pending.transfer, 104),
        "invalid result attempts damaged the original exact command");
}

void close_and_navigation_keep_actual_entered_results() {
    {
        Fixture fixture; auto& owner = *fixture.owner;
        const auto ticket = fixture.stage(17, 3, input::kFocusSchema, focus(17), true); const auto pending = fixture.peek();
        owner.close(); const auto outcome = owner.command_outcome(ticket);
        require(owner.closed() && outcome && outcome->status == EngineInputCommandStatus::cancelled &&
            call(owner, FOUNDATION_ENGINE_TURN_ENTER, pending.target, {}, pending.transfer).control == FOUNDATION_ENGINE_CLOSED,
            "close did not cancel a command before actual entry");
    }
    {
        Fixture fixture; auto& owner = *fixture.owner;
        const auto ticket = fixture.stage(17, 3, input::kFocusSchema, focus(17), true); const auto pending = fixture.peek();
        ok(call(owner, FOUNDATION_ENGINE_TURN_ENTER, pending.target, {}, pending.transfer), "close fixture actual entry failed");
        owner.close(); owner.cancel_input_context(pending.target, 17);
        auto outcome = owner.command_outcome(ticket);
        require(!owner.closed() && outcome && outcome->status == EngineInputCommandStatus::pending,
            "close/cancel erased an already entered command");
        ok(call(owner, FOUNDATION_ENGINE_TURN_LEAVE, pending.target, {}, pending.transfer), "old entered command could not leave after close");
        require(!owner.closed(), "owner finished close before entered actual result settled");
        ok(call(owner, FOUNDATION_ENGINE_COMMAND_RESULT, pending.target, result_bytes(ticket, 1, true), pending.transfer, 104),
            "close discarded the entered actual result");
        outcome = owner.command_outcome(ticket);
        require(owner.closed() && outcome && outcome->status == EngineInputCommandStatus::consumed && outcome->handled,
            "entered actual outcome did not survive close");
        ok(call(owner, FOUNDATION_ENGINE_COMMAND_RESULT, pending.target, result_bytes(ticket, 1, true), pending.transfer, 104),
            "closed exact result duplicate lost idempotence");
    }
    for (std::uint32_t disposition : {1u, 0u}) {
        Fixture fixture; auto& owner = *fixture.owner;
        const auto first = fixture.bind(19);
        const auto ticket = fixture.stage(19, 1, input::kKeySchema, key(19)); const auto pending = fixture.peek();
        ok(call(owner, FOUNDATION_ENGINE_TURN_ENTER, pending.target, {}, pending.transfer), "navigation command did not enter");
        auto successor = pending.target; ++successor.document_sequence; successor.service_generation = 0;
        const auto begun = call(owner, FOUNDATION_ENGINE_BEGIN_DOCUMENT, successor); ok(begun, "entered input could not navigate");
        fixture.target = begun.target;
        require(fixture.target != pending.target && fixture.target.service_generation != pending.target.service_generation,
            "navigation reused old exact document target");
        ok(call(owner, FOUNDATION_ENGINE_TURN_LEAVE, pending.target, {}, pending.transfer), "old target TURN_LEAVE lost navigation identity");
        ok(call(owner, FOUNDATION_ENGINE_COMMAND_RESULT, pending.target,
            result_bytes(ticket, disposition, disposition == 1, disposition == 1 ? 0 : -5), pending.transfer, 104),
            "navigation discarded an entered old-target result");
        const auto outcome = owner.command_outcome(ticket);
        require(outcome && outcome->status == (disposition == 1 ? EngineInputCommandStatus::consumed : EngineInputCommandStatus::rejected) &&
            outcome->handled == (disposition == 1) && outcome->provider_status == (disposition == 1 ? 0 : -5) && owner.input_enabled() &&
            !owner.stage_command(fixture.target, 19, 1, input::kKeySchema, key(19)) &&
            !owner.stage_command(fixture.target, 19, 3, input::kFocusSchema, focus(19), true),
            "old-target result resurrected retired context in successor document");
        const auto next = fixture.bind(20);
        require(next > ticket && ticket > first, "owner ticket high water reset across navigation");
    }
}

void rejected_and_unknown_commands_never_retry() {
    for (std::uint32_t disposition : {0u, 2u}) {
        Fixture fixture; auto& owner = *fixture.owner;
        const auto ticket = fixture.stage(23, 3, input::kFocusSchema, focus(23), true); const auto pending = fixture.peek();
        settle(owner, pending, ticket, disposition, false, -5);
        const auto outcome = owner.command_outcome(ticket);
        require(outcome && outcome->status == (disposition == 2 ? EngineInputCommandStatus::unknown : EngineInputCommandStatus::rejected) &&
            outcome->provider_status == -5 && !outcome->handled && !owner.input_enabled() && owner.input_suspended(),
            "actual rejection/unknown result did not permanently close input admission");
        require(!owner.stage_command(fixture.target, 24, 3, input::kFocusSchema, focus(24), true) &&
            fixture.peek().control != FOUNDATION_ENGINE_OK &&
            call(owner, FOUNDATION_ENGINE_TURN_ENTER, pending.target, {}, pending.transfer).control != FOUNDATION_ENGINE_OK,
            "rejected/unknown command retried actual engine entry");
        ok(call(owner, FOUNDATION_ENGINE_COMMAND_RESULT, pending.target, result_bytes(ticket, disposition, false, -5), pending.transfer, 104),
            "exact rejected/unknown duplicate lost idempotence");
        require(disposition != 2 || owner.closed(), "unknown disposition did not finish owner close");
    }
}

void native_effect_barrier_hold_and_empty_pump() {
    Fixture fixture; auto& owner = *fixture.owner; fixture.discover(); fixture.bind(31);
    const auto pending_ticket = fixture.stage(31, 1, input::kKeySchema, key(31));
    fixture.submit(7);
    const auto gated = call(owner, FOUNDATION_ENGINE_PUMP_ONE, fixture.target);
    const auto cancelled = owner.command_outcome(pending_ticket);
    require(gated.control == FOUNDATION_ENGINE_CONFLICT && cancelled &&
        cancelled->status == EngineInputCommandStatus::cancelled && fixture.effects == 0,
        "native service barrier did not cancel input which had not entered");
    const auto effect_ticket = fixture.prepare_effect();
    ok(call(owner, FOUNDATION_ENGINE_PUMP_ONE, fixture.target), "normal known native completion failed");
    require(fixture.effects == 1 && !owner.native_effect() && !owner.input_suspended() &&
        !owner.hold_native_effect(effect_ticket) && !owner.release_native_effect(effect_ticket),
        "normal known native completion did not automatically release input admission");
    const auto value = fixture.delivery(7); require(completion(value).payload == encode_u32(42), "actual native result changed");
    accept(owner, value); fixture.acknowledge(7);
    fixture.bind(32);
    for (unsigned i = 0; i < 3; ++i) {
        ok(call(owner, FOUNDATION_ENGINE_PUMP_ONE, fixture.target), "empty native queue pump failed");
        require(!owner.native_effect() && !owner.input_suspended() && fixture.effects == 1,
            "empty native pump invented an effect or churned context admission");
    }
    const auto ticket = fixture.stage(32, 1, input::kKeySchema, key(32)); settle(owner, fixture.peek(), ticket);
    fixture.hold_on_entry = true; fixture.submit(13); const auto held = fixture.prepare_effect();
    ok(call(owner, FOUNDATION_ENGINE_PUMP_ONE, fixture.target), "UI-owning native effect failed");
    require(fixture.effects == 2 && fixture.held_ticket == held && owner.native_effect() && owner.native_effect()->entered &&
        owner.input_suspended() && !owner.stage_command(fixture.target, 33, 3, input::kFocusSchema, focus(33), true),
        "actual handler's UI hold did not survive known service completion");
    require(!owner.release_native_effect(held + 1) && owner.input_suspended() && owner.release_native_effect(held) &&
        !owner.native_effect() && !owner.input_suspended() && !owner.release_native_effect(held),
        "only the exact trusted UI release should clear an actual handler hold");
    accept(owner, fixture.delivery(13));
    fixture.bind(33);
}

void exact_queue_sequence_resumes_only_new_effect() {
    {
        Fixture fixture; auto& owner = *fixture.owner; fixture.discover(); fixture.bind(41);
        fixture.submit(3); fixture.submit(9);
        ok(call(owner, FOUNDATION_ENGINE_CANCEL, fixture.target, encode_u64(3)), "lower native cancellation failed");
        ok(call(owner, FOUNDATION_ENGINE_PUMP_ONE, fixture.target), "lower canceled ready completion was not collected");
        require(!owner.native_effect() && !owner.input_suspended() && fixture.effects == 0,
            "lower canceled ready completion fabricated an entered native effect");
        accept(owner, fixture.delivery(3, FOUNDATION_APPENDED_SERVICE_CLOSED));
        fixture.execute_effect();
        require(fixture.effects == 1 && !owner.native_effect() && !owner.input_suspended() && owner.input_enabled(),
            "gapped new native sequence did not resume after exact newly completed result");
        accept(owner, fixture.delivery(9));
    }
    {
        Fixture fixture; auto& owner = *fixture.owner; fixture.discover(false); fixture.bind(51);
        const auto original = fixture.request(5, fixture.handle, 1, encode_u32(41)); fixture.submit(original);
        fixture.execute_effect();
        const auto value = fixture.delivery(5); accept(owner, value);
        require(fixture.effects == 1 && !owner.native_effect() && owner.input_enabled(),
            "lower delivered but ACK-retained call stole the later native effect's completion identity");
        fixture.bind(52); fixture.submit(original);
        ok(call(owner, FOUNDATION_ENGINE_PUMP_ONE, fixture.target), "identical retained call replay was not redelivered");
        require(fixture.effects == 1 && !owner.native_effect() && !owner.input_suspended(),
            "identical replay redelivery entered another effect or retired an active input context");
        require(completion(fixture.delivery(5)).payload == completion(value).payload, "identical replay changed actual retained result");
        accept(owner, fixture.delivery(5));
        ok(call(owner, FOUNDATION_ENGINE_PUMP_ONE, fixture.target), "empty post-replay pump failed");
        const auto key_ticket = fixture.stage(52, 1, input::kKeySchema, key(52)); settle(owner, fixture.peek(), key_ticket);
        fixture.submit(17); fixture.execute_effect();
        require(fixture.effects == 2 && !owner.native_effect() && !owner.input_suspended() && owner.input_enabled(),
            "previous exact replay completion resumed or poisoned a different new effect sequence");
        accept(owner, fixture.delivery(17)); fixture.acknowledge(17);
    }
}

void handler_close_retains_exact_new_and_later_closed_outcomes() {
    Fixture fixture(true); auto& owner = *fixture.owner; fixture.discover(); fixture.bind(61);
    fixture.close_on_entry = true; fixture.submit(4); fixture.submit(12);
    fixture.execute_effect();
    require(fixture.effects == 1 && !owner.native_effect() && !owner.input_enabled(),
        "handler close lost exact known effect completion or ran later queued native work");
    for (std::uint64_t sequence : {UINT64_C(4), UINT64_C(12)}) {
        const auto audit = call(owner, FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT, fixture.target); ok(audit, "closed handler outcome audit missing");
        const auto value = completion(audit);
        require(audit.target == fixture.target && value.envelope.generation == fixture.target.service_generation &&
            value.envelope.sequence == sequence && value.envelope.service_status ==
                (sequence == 4 ? FOUNDATION_APPENDED_SERVICE_OK : FOUNDATION_APPENDED_SERVICE_CLOSED) &&
            value.payload == (sequence == 4 ? encode_u32(42) : Bytes{}) && fixture.effects == 1,
            "handler-triggered close changed its actual result or a later queued CLOSED outcome");
        ok(call(owner, FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT, audit.target, encode_u32(FOUNDATION_ENGINE_ABANDONED), audit.transfer),
            "exact closed outcome audit did not retire its own prefix");
    }
    require(call(owner, FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT, fixture.target).control == FOUNDATION_ENGINE_EMPTY &&
        fixture.effects == 1, "closed queue replayed a service or invented a further outcome");
}

void uncertain_actual_native_effect_stays_suspended() {
    Fixture fixture; auto& owner = *fixture.owner; fixture.discover(); fixture.bind(71);
    fixture.throw_on_entry = true;
    const auto original = fixture.request(5, fixture.handle, 1, encode_u32(41)); fixture.submit(original); fixture.submit(11);
    const auto ticket = fixture.prepare_effect();
    const auto pumped = call(owner, FOUNDATION_ENGINE_PUMP_ONE, fixture.target);
    const auto effect = owner.native_effect();
    require(pumped.control == FOUNDATION_ENGINE_INTERNAL && pumped.service == FOUNDATION_APPENDED_SERVICE_UNCERTAIN &&
        effect && effect->ticket == ticket && effect->entered && owner.input_suspended() && !owner.input_enabled() &&
        fixture.effects == 1, "actual throwing native handler did not retain its uncertain effect barrier");
    require(!owner.hold_native_effect(ticket) && !owner.release_native_effect(ticket) &&
        !owner.acknowledge_native_effect(ticket) && !owner.stage_command(fixture.target, 72,
            3, input::kFocusSchema, focus(72), true) &&
        call(owner, FOUNDATION_ENGINE_TURN_ENTER, fixture.target).control != FOUNDATION_ENGINE_OK,
        "unknown actual native effect was released or admitted another engine turn");
    const auto pending = fixture.delivery(5, FOUNDATION_APPENDED_SERVICE_UNCERTAIN);
    require(completion(pending).payload.empty(), "uncertain actual native result fabricated success bytes");
    fixture.submit(original);
    require(call(owner, FOUNDATION_ENGINE_PUMP_ONE, fixture.target).control == FOUNDATION_ENGINE_CONFLICT &&
        fixture.effects == 1 && owner.native_effect() && owner.native_effect()->ticket == ticket && owner.input_suspended(),
        "uncertain handler replay or a later queued call repeated a native effect");
    owner.close();
    require(owner.input_suspended() && !owner.release_native_effect(ticket) && fixture.effects == 1,
        "close converted uncertain native work into a releasable UI hold");
}
} // namespace

int main() {
    struct Case { const char* name; void (*run)(); };
    const std::array<Case, 8> cases{{
        {"mailbox-reservation", mailbox_reservation_and_exact_results},
        {"strict-command-identity", strict_target_context_and_schema},
        {"close-navigation", close_and_navigation_keep_actual_entered_results},
        {"rejected-unknown", rejected_and_unknown_commands_never_retry},
        {"native-effect-barrier", native_effect_barrier_hold_and_empty_pump},
        {"exact-queue-sequence", exact_queue_sequence_resumes_only_new_effect},
        {"handler-close", handler_close_retains_exact_new_and_later_closed_outcomes},
        {"uncertain-native-effect", uncertain_actual_native_effect_stays_suspended},
    }};
    unsigned failed{};
    for (const auto& test : cases) {
        try { test.run(); }
        catch (const std::exception& error) {
            ++failed; std::cerr << "FAIL " << test.name << ": " << error.what() << '\n';
        }
    }
    if (failed) { std::cerr << failed << "/" << cases.size() << " groups failed; " << assertions << " assertions executed\n"; return 1; }
    std::cout << "PASS: " << cases.size() << " copied physical-input owner groups, " << assertions
        << " assertions; synthetic profile, actual native Registry, no engine/browser execution\n";
    return 0;
}
