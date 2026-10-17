#pragma once
// Exact unchanged helper-prefix projection from the independently maintained
// appended_application_test.cpp. This is a fixture, never a guest compiler.
#include <foundation/appended/providers.hpp>
#include <algorithm>
#include <array>
#include <bit>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>
namespace foundation::appended::binding_fixture {
void check(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
void append(Bytes& output, const Bytes& input) { output.insert(output.end(), input.begin(), input.end()); }
void uleb(Bytes& output, std::uint32_t value) {
    do {
        const auto byte = static_cast<std::uint8_t>(value & 127u);
        value >>= 7;
        output.push_back(static_cast<std::uint8_t>(byte | (value ? 128u : 0u)));
    } while (value);
}
void constant(Bytes& output, std::int32_t value) {
    output.push_back(0x41);
    bool more;
    do {
        const auto byte = static_cast<std::uint8_t>(value & 127);
        value >>= 7;
        more = !((value == 0 && !(byte & 64)) || (value == -1 && (byte & 64)));
        output.push_back(static_cast<std::uint8_t>(byte | (more ? 128u : 0u)));
    } while (more);
}
void name(Bytes& output, std::string_view value) {
    uleb(output, static_cast<std::uint32_t>(value.size()));
    output.insert(output.end(), value.begin(), value.end());
}
void section(Bytes& module, std::uint8_t kind, const Bytes& value) {
    module.push_back(kind); uleb(module, static_cast<std::uint32_t>(value.size())); append(module, value);
}

struct Field {
    std::uint16_t id;
    FieldType type;
    Bytes value;
    bool required = true;
};
Field integer(std::uint16_t id, std::uint64_t value) { return {id, FieldType::u64, encode_u64(value)}; }
Field enumeration(std::uint16_t id, std::uint32_t value) { return {id, FieldType::u32, encode_u32(value)}; }
Field text(std::uint16_t id, std::string_view value) { return {id, FieldType::utf8, Bytes(value.begin(), value.end())}; }
Field number(std::uint16_t id, double value) { return {id, FieldType::f64, encode_u64(std::bit_cast<std::uint64_t>(value))}; }
Field boolean(std::uint16_t id, bool value) { return {id, FieldType::boolean, {static_cast<std::uint8_t>(value)}}; }
Field nested(std::uint16_t id, Bytes value) { return {id, FieldType::record, std::move(value)}; }
Field list(std::uint16_t id, const std::vector<Bytes>& values) {
    auto result = encode_u32(static_cast<std::uint32_t>(values.size()));
    for (const auto& value : values) {
        append(result, encode_u32(static_cast<std::uint32_t>(value.size()))); append(result, value);
    }
    return {id, FieldType::record_list, std::move(result)};
}
Bytes record(std::vector<Field> fields, bool event = false) {
    std::sort(fields.begin(), fields.end(), [](const auto& a, const auto& b) { return a.id < b.id; });
    std::vector<FieldView> views;
    for (const auto& field : fields) views.push_back({field.id, field.type, !event && field.required, field.value});
    Bytes result;
    check(encode_record(views, result) == CodecStatus::ok, "cannot encode view fixture record");
    return result;
}
Bytes key(std::string_view id, std::uint64_t generation, bool event = false) {
    return record({text(1, id), integer(2, generation)}, event);
}
Bytes rectangle(double x, double y, double width, double height) {
    return record({number(1, x), number(2, y), number(3, width), number(4, height)});
}

struct ViewState {
    std::string title = "initial", editor = "alpha";
    std::uint64_t button_generation = 1, bitmap_revision = 1;
    bool button = true, duplicate = false, read_only = false, command_scope = false;
    bool huge_bitmap = false, unknown_required = false, unknown_optional = false;
    Bytes pixels{1, 2, 3, 4, 5, 6};
};
Bytes replacement(std::uint64_t revision, const ViewState& state) {
    std::vector<Bytes> widgets;
    widgets.push_back(record({text(1, "editor"), integer(2, 1), enumeration(3, 6),
        nested(4, rectangle(10, 10, 100, 24)), text(7, state.editor), boolean(17, state.read_only)}));
    if (state.button) widgets.push_back(record({text(1, "apply"), integer(2, state.button_generation), enumeration(3, 3),
        nested(4, rectangle(10, 40, 100, 24)), text(8, "Apply")}));
    const auto bitmap = record({text(1, "pixels"), integer(2, state.bitmap_revision), enumeration(3, 2),
        enumeration(4, 1), enumeration(5, 3), {6, FieldType::bytes, state.pixels}});
    const auto extent = state.huge_bitmap ? 20000.0 : 2.0;
    widgets.push_back(record({text(1, "image"), integer(2, 1), enumeration(3, 8),
        nested(4, rectangle(10, 80, extent, state.huge_bitmap ? extent : 1.0)), nested(32, bitmap)}));
    if (state.duplicate) widgets.push_back(widgets.front());
    std::vector<Field> command{text(1, "invoke"), integer(2, 1)};
    if (state.command_scope) command.push_back(nested(4, key("editor", 1)));
    std::vector<Field> fields{integer(1, revision), text(2, state.title), list(6, widgets),
        list(7, {record(std::move(command))})};
    if (state.unknown_required || state.unknown_optional) {
        auto unknown = enumeration(13, 123); unknown.required = state.unknown_required; fields.push_back(std::move(unknown));
    }
    return record(std::move(fields));
}
Bytes service_request() {
    return record({integer(1, 99), enumeration(2, 3), text(3, "A generic prompt"), text(4, "seed"), enumeration(5, 8)});
}
Bytes envelope(std::uint32_t kind, std::uint64_t sequence, std::uint32_t operation, const Bytes& payload,
               std::uint64_t handle = 1, std::uint64_t correlation = 0) {
    Envelope header; header.kind = kind; header.generation = 7; header.sequence = sequence;
    header.interface_handle = handle; header.operation = operation; header.correlation = correlation;
    Bytes result;
    check(encode_envelope(header, payload, result) == CodecStatus::ok, "cannot encode view fixture envelope");
    return result;
}
struct Call {
    Bytes request;
    ServiceStatus status = ServiceStatus::ok;
    std::optional<std::uint64_t> revision;
};
Call call(std::uint64_t sequence, std::uint32_t operation, const Bytes& payload,
          ServiceStatus status = ServiceStatus::ok, std::optional<std::uint64_t> revision = {},
          std::uint64_t handle = 1) {
    return {envelope(FOUNDATION_APPENDED_MESSAGE_REQUEST, sequence, operation, payload, handle), status, revision};
}
Bytes input_event(std::uint64_t sequence, std::uint64_t revision, std::string_view target,
                  std::uint64_t generation, std::uint32_t input,
                  std::string_view value = {}, std::string_view base = {}) {
    std::vector<Field> fields{integer(1, revision), enumeration(2, 1), nested(3, key(target, generation, true)),
        enumeration(4, input)};
    if (input == 3) { fields.push_back(text(5, value)); fields.push_back(text(6, base)); }
    return envelope(FOUNDATION_APPENDED_MESSAGE_EVENT, sequence, 1, record(std::move(fields), true));
}
Bytes completion_event(std::uint64_t sequence) {
    return envelope(FOUNDATION_APPENDED_MESSAGE_EVENT, sequence, 2,
        record({integer(1, 99), enumeration(2, 1), text(3, "hello"), text(4, "")}, true));
}
const SchemaId& provider_schema() {
    static constexpr SchemaId schema{0x3f,0xe7,0xab,0x0d,0x3f,0x8f,0x76,0x49,
        0x9f,0x05,0x4c,0xa6,0xf2,0x9f,0x68,0xde,0xee,0x28,0x62,0x76,0x81,0xf7,
        0x92,0x31,0xaf,0x3b,0x09,0x5b,0x06,0x35,0xb2,0x46};
    return schema;
}
Bytes provider_registration() {
    const auto& schema = provider_schema();
    return record({text(1, "org.example.increment"), enumeration(2, 1), enumeration(3, 0),
        {4, FieldType::bytes, Bytes(schema.begin(), schema.end())}, enumeration(5, 4), enumeration(6, 8)});
}
Bytes provider_result(std::uint32_t result, std::uint32_t effects) {
    auto bytes = encode_u32(result); append(bytes, encode_u32(effects)); return bytes;
}
Bytes provider_event(std::uint64_t sequence, std::uint64_t invocation, std::uint32_t operand) {
    return envelope(FOUNDATION_APPENDED_MESSAGE_EVENT, sequence, FOUNDATION_PROVIDER_EVENT_CALL,
        record({integer(1, 1), enumeration(2, 1), {3, FieldType::bytes, encode_u32(operand)}}), 2, invocation);
}
Call provider_response(std::uint64_t gateway_sequence, std::uint64_t invocation,
                       std::uint32_t result, std::uint32_t effects) {
    return call(gateway_sequence, FOUNDATION_PROVIDER_RESPOND,
        record({integer(1, invocation), integer(2, 1), enumeration(3, 0),
            {4, FieldType::bytes, provider_result(result, effects)}}), ServiceStatus::ok, {}, 2);
}
DiscoveryQuery provider_query() { return {"org.example.increment", 1, 0, 0, provider_schema()}; }
void check_provider_result(const ProviderOutcome& outcome, std::uint32_t result, std::uint32_t effects) {
    check(outcome.status == ServiceStatus::ok && outcome.payload == provider_result(result, effects),
        "host provider result did not contain the guest response");
}
struct Dispatch {
    Bytes event;
    std::vector<Call> calls;
};
struct Script {
    std::vector<Call> initialize;
    std::vector<Dispatch> dispatch;
};

// Assertions execute inside the actual Wasm guest. An unexpected transport,
// service outcome or event byte traps instead of impersonating guest behavior.
void expect_equal(Bytes& code, std::uint32_t expected) {
    constant(code, std::bit_cast<std::int32_t>(expected));
    code.insert(code.end(), {0x47, 0x04, 0x40, 0x00, 0x0b}); // ne; if; unreachable; end
}
void load_word(Bytes& code, std::uint32_t address) {
    constant(code, static_cast<std::int32_t>(address)); code.insert(code.end(), {0x28, 0, 0});
}
Bytes wasm(const Script& script) {
    constexpr std::uint32_t data_address = 1024, input_address = 32768, reply_address = 65536;
    Bytes data;
    auto emit_calls = [&](Bytes& code, const std::vector<Call>& calls) {
        for (const auto& request : calls) {
            const auto address = data_address + static_cast<std::uint32_t>(data.size());
            append(data, request.request);
            check(data_address + data.size() < input_address, "view fixture static data overlaps allocator");
            constant(code, static_cast<std::int32_t>(address)); constant(code, static_cast<std::int32_t>(request.request.size()));
            constant(code, static_cast<std::int32_t>(reply_address)); constant(code, 256);
            code.insert(code.end(), {0x10, 0}); expect_equal(code, FOUNDATION_APPENDED_TRANSPORT_OK);
            load_word(code, reply_address + 48); expect_equal(code, static_cast<std::uint32_t>(request.status));
            if (request.revision) {
                load_word(code, reply_address + 44); expect_equal(code, 16);
                load_word(code, reply_address + 72); expect_equal(code, static_cast<std::uint32_t>(*request.revision));
                load_word(code, reply_address + 76); expect_equal(code, static_cast<std::uint32_t>(*request.revision >> 32));
            }
        }
    };
    std::array<Bytes, 7> code;
    constant(code[0], FOUNDATION_APPENDED_ABI_VERSION);
    constant(code[1], static_cast<std::int32_t>(input_address));
    emit_calls(code[3], script.initialize); constant(code[3], FOUNDATION_APPENDED_APP_OK);
    for (std::size_t n = 0; n < script.dispatch.size(); ++n) {
        const auto& dispatch = script.dispatch[n];
        auto& body = code[4];
        body.insert(body.end(), {0x23, 0}); constant(body, static_cast<std::int32_t>(n));
        body.insert(body.end(), {0x46, 0x04, 0x40}); // global stage == n; if
        body.insert(body.end(), {0x20, 1}); expect_equal(body, static_cast<std::uint32_t>(dispatch.event.size()));
        for (std::size_t offset = 0; offset < dispatch.event.size();) {
            const bool word = dispatch.event.size() - offset >= 4;
            body.insert(body.end(), {0x20, 0}); // input parameter, supplied by the runtime allocator
            body.push_back(word ? 0x28 : 0x2d); body.push_back(0); uleb(body, static_cast<std::uint32_t>(offset));
            std::uint32_t expected = dispatch.event[offset];
            if (word) for (unsigned byte = 1; byte < 4; ++byte)
                expected |= std::uint32_t(dispatch.event[offset + byte]) << (8 * byte);
            expect_equal(body, expected); offset += word ? 4u : 1u;
        }
        emit_calls(body, dispatch.calls);
        constant(body, static_cast<std::int32_t>(n + 1)); body.insert(body.end(), {0x24, 0});
        constant(body, FOUNDATION_APPENDED_APP_OK); body.insert(body.end(), {0x0f, 0x0b});
    }
    code[4].push_back(0x00); // Any unexpected callback is a test failure.
    constant(code[5], FOUNDATION_APPENDED_STEP_IDLE);

    Bytes module{0, 97, 115, 109, 1, 0, 0, 0};
    section(module, 1, {6, 0x60, 4, 0x7f, 0x7f, 0x7f, 0x7f, 1, 0x7f,
        0x60, 0, 1, 0x7f, 0x60, 1, 0x7f, 1, 0x7f, 0x60, 2, 0x7f, 0x7f, 0,
        0x60, 2, 0x7f, 0x7f, 1, 0x7f, 0x60, 1, 0x7f, 0});
    Bytes imports{1}; name(imports, FOUNDATION_APPENDED_IMPORT_MODULE); name(imports, FOUNDATION_APPENDED_IMPORT_NAME);
    imports.insert(imports.end(), {0, 0}); section(module, 2, imports);
    section(module, 3, {7, 1, 2, 3, 4, 4, 2, 5});
    section(module, 5, {1, 1, 2, 4}); // Two initial pages, four maximum; reply is in page two.
    section(module, 6, {1, 0x7f, 1, 0x41, 0, 0x0b});
    Bytes exports{8}; name(exports, "memory"); exports.insert(exports.end(), {2, 0});
    constexpr std::array names{"foundation_app_abi_v1", "foundation_app_alloc_v1", "foundation_app_free_v1",
        "foundation_app_init_v1", "foundation_app_dispatch_v1", "foundation_app_step_v1", "foundation_app_shutdown_v1"};
    for (std::size_t n = 0; n < names.size(); ++n) {
        name(exports, names[n]); exports.push_back(0); uleb(exports, static_cast<std::uint32_t>(n + 1));
    }
    section(module, 7, exports);
    Bytes bodies{7};
    for (auto& body : code) {
        body.insert(body.begin(), 0); body.push_back(0x0b);
        uleb(bodies, static_cast<std::uint32_t>(body.size())); append(bodies, body);
    }
    section(module, 10, bodies);
    Bytes segment{1, 0}; constant(segment, static_cast<std::int32_t>(data_address));
    segment.push_back(0x0b); // End the active segment's offset constant expression.
    uleb(segment, static_cast<std::uint32_t>(data.size())); append(segment, data); section(module, 11, segment);
    return module;
}

} // namespace foundation::appended::binding_fixture
