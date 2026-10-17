#include "shared/appended_application.hpp"

#include <gui/memory_adapter.hpp>
#include <gui/retained_adapter.hpp>
#include <algorithm>
#include <array>
#include <bit>
#include <fstream>
#include <functional>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

using namespace foundation::appended;
using foundation::ui::AppendedApplication;

namespace {
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

const gui::Widget& widget(const gui::Snapshot& snapshot, std::string_view id) {
    for (const auto& value : snapshot.widgets) if (value.spec.key.id == id) return value;
    throw std::runtime_error("fixture widget is missing");
}

void transactions_events_services() {
    Script script;
    std::uint64_t sequence = 1;
    ViewState initial; initial.unknown_optional = true;
    const auto first = call(sequence++, 1, replacement(0, initial), ServiceStatus::ok, 1);
    script.initialize.push_back(first); script.initialize.push_back(first); // Live retry cannot repeat a mutation.
    auto bad = initial; bad.title = "must not commit"; bad.duplicate = true;
    script.initialize.push_back(call(sequence++, 1, replacement(1, bad), ServiceStatus::invalid_request));
    bad = initial; bad.read_only = true;
    script.initialize.push_back(call(sequence++, 1, replacement(1, bad), ServiceStatus::invalid_request));
    bad = initial; bad.command_scope = true;
    script.initialize.push_back(call(sequence++, 1, replacement(1, bad), ServiceStatus::invalid_request));
    bad = initial; bad.pixels[0] = 200;
    script.initialize.push_back(call(sequence++, 1, replacement(1, bad), ServiceStatus::invalid_request));
    bad = initial; bad.huge_bitmap = true;
    script.initialize.push_back(call(sequence++, 1, replacement(1, bad), ServiceStatus::invalid_request));
    bad = initial; bad.unknown_required = true;
    script.initialize.push_back(call(sequence++, 1, replacement(1, bad), ServiceStatus::invalid_request));
    script.initialize.push_back(call(sequence++, 1, replacement(0, initial), ServiceStatus::conflict));
    script.initialize.push_back(call(sequence++, 2, service_request()));
    script.initialize.push_back(call(sequence++, 2, service_request(), ServiceStatus::conflict));

    ViewState activated; activated.title = "activated"; activated.editor = "beta";
    activated.button_generation = 2; activated.bitmap_revision = 2; activated.pixels = {7, 8, 9, 10, 11, 12};
    Dispatch action{input_event(1, 1, "apply", 1, 1), {}};
    action.calls.push_back(call(sequence++, 1, replacement(1, activated), ServiceStatus::ok, 2));
    bad = activated; bad.button_generation = 1;
    action.calls.push_back(call(sequence++, 1, replacement(2, bad), ServiceStatus::invalid_request));
    auto removed = activated; removed.button = false;
    action.calls.push_back(call(sequence++, 1, replacement(2, removed), ServiceStatus::ok, 3));
    action.calls.push_back(call(sequence++, 1, replacement(3, activated), ServiceStatus::invalid_request));
    activated.button_generation = 3;
    action.calls.push_back(call(sequence++, 1, replacement(3, activated), ServiceStatus::ok, 4));
    script.dispatch.push_back(std::move(action));
    auto edited = activated; edited.title = "edited"; edited.editor = "gamma";
    script.dispatch.push_back({input_event(2, 4, "editor", 1, 3, "gamma", "beta"),
        {call(sequence++, 1, replacement(4, edited), ServiceStatus::ok, 5)}});
    auto completed = edited; completed.title = "complete";
    script.dispatch.push_back({completion_event(3), {call(sequence++, 1, replacement(5, completed), ServiceStatus::ok, 6)}});

    AppendedApplication* current = nullptr;
    gui::MemoryAdapter adapter([&](const gui::Event& event) { if (current) current->handle(event); });
    auto source = wasm(script);
    AppendedApplication application(adapter, source, 7); current = &application;
    std::fill(source.begin(), source.end(), 0xff); // Runtime and bitmap contents must own their data.
    check(application.view().revision == 1 && application.view().title == "initial", "invalid/replayed replacement changed authoritative view");
    check(application.input_epoch() == 2 && !application.presentation_pending(), "rejected transaction changed input epoch or presentation");
    check(adapter.snapshot().revision == 1 && widget(adapter.snapshot(), "editor").state.text == "alpha", "initial guest view was not presented");
    check(adapter.repaint({"image", 1}) && adapter.image({"image", 1}).pixels() == initial.pixels, "initial owned bitmap was not rendered");
    unsigned qualification = 0; application.qualify([&] { ++qualification; });
    check(qualification == 1, "generic qualification did not call host presentation");
    const auto service = application.next_service();
    check(service && service->id == 99 && service->kind == gui::ServiceKind::prompt && service->title == "A generic prompt" &&
        service->value == "seed" && service->byte_limit == 8, "guest host service was not translated");
    check(!application.next_service() && !application.complete_service({100, gui::ServiceStatus::success, "hello", {}}), "service accepted a duplicate launch or wrong completion");

    const auto epoch = application.input_epoch();
    application.handle(gui::WidgetEvent{{"apply", 99}, gui::Activate{}});
    application.handle(gui::WidgetEvent{{"editor", 1}, gui::EditText{"wrong", "stale base"}});
    application.handle(gui::WidgetEvent{{"invoke", 1}, gui::Activate{gui::WidgetKey{"editor", 1}}});
    check(adapter.focus(gui::WidgetKey{"editor", 1}), "cannot focus generic editor");
    application.handle(gui::WidgetEvent{{"invoke", 1}, gui::Activate{gui::WidgetKey{"apply", 1}}});
    check(application.input_epoch() == epoch && application.view().revision == 1, "stale input or false command focus reached the guest");
    check(adapter.send(gui::WidgetEvent{{"apply", 1}, gui::Activate{}}) == gui::Delivery::delivered, "generic activation was not delivered");
    check(application.view().revision == 4 && application.view().title == "activated" &&
        widget(adapter.snapshot(), "apply").spec.key.generation == 3, "guest event did not mutate the same instance or preserve lifetime history");
    check(adapter.repaint({"image", 1}) && adapter.image({"image", 1}).pixels() == activated.pixels, "new bitmap revision retained old pixels");
    application.handle(gui::WidgetEvent{{"apply", 2}, gui::Activate{}});
    application.handle(gui::WidgetEvent{{"editor", 1}, gui::EditText{"wrong", "alpha"}});
    check(application.view().revision == 4, "replacement accepted stale generation or editor base");
    check(adapter.send(gui::WidgetEvent{{"editor", 1}, gui::EditText{"gamma", "beta"}}) == gui::Delivery::delivered,
        "current editor event was not delivered");
    check(application.view().revision == 5 && widget(adapter.snapshot(), "editor").state.text == "gamma", "guest edit handler did not publish text");
    check(application.complete_service({99, gui::ServiceStatus::success, "hello", {}}), "matching host completion was rejected");
    check(application.view().revision == 6 && adapter.snapshot().title == "complete", "host completion did not return through guest dispatch");
    check(!application.complete_service({99, gui::ServiceStatus::success, "hello", {}}), "host completion was repeated");
    application.tick();
    application.handle(gui::CloseEvent{}); application.tick();
    check(adapter.closed() && !application.next_service() &&
        !application.complete_service({99, gui::ServiceStatus::success, "late", {}}), "closed instance retained services");
}

class FailingAdapter final : public gui::RetainedAdapter {
public:
    bool fail_next = false;
    void present(gui::Snapshot snapshot) override {
        if (std::exchange(fail_next, false)) throw std::runtime_error("injected presentation failure");
        gui::RetainedAdapter::present(std::move(snapshot));
    }
};
void presentation_retry() {
    ViewState initial, activated; activated.title = "accepted"; activated.editor = "beta";
    auto edited = activated; edited.title = "recovered"; edited.editor = "gamma";
    Script script{{call(1, 1, replacement(0, initial), ServiceStatus::ok, 1)}, {
        {input_event(1, 1, "apply", 1, 1), {call(2, 1, replacement(1, activated), ServiceStatus::ok, 2)}},
        {input_event(2, 2, "editor", 1, 3, "gamma", "beta"), {call(3, 1, replacement(2, edited), ServiceStatus::ok, 3)}}}};
    FailingAdapter adapter;
    AppendedApplication application(adapter, wasm(script), 7);
    adapter.fail_next = true;
    bool failed = false;
    try { application.handle(gui::WidgetEvent{{"apply", 1}, gui::Activate{}}); }
    catch (const std::runtime_error&) { failed = true; }
    check(failed && application.presentation_pending() && application.view().revision == 2 && adapter.snapshot().revision == 1,
        "failed presentation lost accepted authoritative state or pending retry");
    const auto epoch = application.input_epoch();
    application.handle(gui::WidgetEvent{{"apply", 1}, gui::Activate{}});
    check(application.input_epoch() == epoch, "old painted input reached guest while presentation was pending");
    application.retry_presentation();
    check(!application.presentation_pending() && adapter.snapshot().revision == 2 && adapter.snapshot().title == "accepted",
        "presentation retry did not recover accepted view");
    application.handle(gui::WidgetEvent{{"editor", 1}, gui::EditText{"wrong", "alpha"}});
    application.handle(gui::WidgetEvent{{"editor", 1}, gui::EditText{"gamma", "beta"}});
    check(application.view().revision == 3 && adapter.snapshot().title == "recovered", "presentation retry repeated guest work or lost dispatch state");
}

class CallbackAdapter final : public gui::RetainedAdapter {
public:
    std::function<void()> during_present;
    void present(gui::Snapshot snapshot) override {
        if (during_present) during_present();
        gui::RetainedAdapter::present(std::move(snapshot));
    }
};
void providers_compose_with_views() {
    ViewState initial, provided, activated, completed, provided_again;
    provided.title = "provider invoked";
    activated.title = "view input";
    completed.title = "service completed";
    provided_again.title = "provider invoked again";
    Script script{{
        call(1, FOUNDATION_PROVIDER_REGISTER, provider_registration(), ServiceStatus::ok, 1, 2),
        call(2, 1, replacement(0, initial), ServiceStatus::ok, 1),
        call(3, 2, service_request())}, {
        {provider_event(1, 10, 41), {provider_response(4, 10, 42, 1),
            call(5, 1, replacement(1, provided), ServiceStatus::ok, 2)}},
        {input_event(2, 2, "apply", 1, 1), {call(6, 1, replacement(2, activated), ServiceStatus::ok, 3)}},
        {completion_event(3), {call(7, 1, replacement(3, completed), ServiceStatus::ok, 4)}},
        {provider_event(4, 11, 99), {provider_response(8, 11, 100, 2),
            call(9, 1, replacement(4, provided_again), ServiceStatus::ok, 5)}}}};
    CallbackAdapter adapter;
    AppendedApplication application(adapter, wasm(script), 7);
    check(application.generation() == 7 && application.view().revision == 1 && adapter.snapshot().title == "initial",
        "provider registration prevented initial view publication");
    const auto found = application.discover_provider(provider_query());
    check(found.status == ServiceStatus::ok && found.handle == 1 &&
        found.descriptor.contract.name == "org.example.increment" && found.descriptor.contract.major == 1 &&
        found.descriptor.contract.minor == 0 && found.descriptor.contract.schema == provider_schema() &&
        found.descriptor.max_request_bytes == 4 && found.descriptor.contract.max_reply_bytes == 8,
        "module provider was not registered and activated during initialization");
    auto mismatch = provider_query(); (*mismatch.schema)[0] ^= 1;
    check(application.discover_provider(mismatch).status == ServiceStatus::schema_mismatch,
        "host discovery ignored the requested provider schema");
    auto absent = provider_query(); absent.name = "org.example.absent";
    check(application.discover_provider(absent).status == ServiceStatus::not_found,
        "host discovery exposed an unregistered provider");
    ProviderRequest request{application.generation(), 10, found.handle, 1, encode_u32(41)};
    auto invalid = request; invalid.generation = 8;
    check(application.invoke_provider(invalid).status == ServiceStatus::invalid_handle,
        "host provider invocation accepted a stale module generation");
    invalid = request; ++invalid.provider;
    check(application.invoke_provider(invalid).status == ServiceStatus::invalid_handle,
        "host provider invocation accepted an unknown route");
    const auto service = application.next_service();
    check(service && service->id == 99, "provider initialization lost the generic host service");
    unsigned callbacks = 0;
    adapter.during_present = [&] {
        ++callbacks;
        auto nested = request; nested.sequence = 11;
        check(application.invoke_provider(nested).status == ServiceStatus::unavailable &&
            application.discover_provider(provider_query()).status == ServiceStatus::unavailable &&
            application.acknowledge_provider(0) == ServiceStatus::unavailable,
            "presentation callback reentered the guest provider bridge");
    };
    check_provider_result(application.invoke_provider(request), 42, 1);
    adapter.during_present = {};
    check(callbacks == 1 && application.view().revision == 2 && adapter.snapshot().title == "provider invoked",
        "provider guest view mutation was not presented after dispatch");
    check_provider_result(application.invoke_provider(request), 42, 1);
    check(application.view().revision == 2, "identical host provider retry repeated a guest view mutation");
    auto conflict = request; conflict.payload = encode_u32(99);
    check(application.invoke_provider(conflict).status == ServiceStatus::conflict,
        "conflicting host provider retry reached the guest");
    check(application.acknowledge_provider(11) == ServiceStatus::invalid_request &&
        application.acknowledge_provider(10) == ServiceStatus::ok &&
        application.invoke_provider(request).status == ServiceStatus::expired,
        "host provider acknowledgement did not retire only admitted calls");
    application.handle(gui::WidgetEvent{{"apply", 1}, gui::Activate{}});
    check(application.view().revision == 3 && adapter.snapshot().title == "view input",
        "view input did not share the provider event sequence");
    check(application.complete_service({99, gui::ServiceStatus::success, "hello", {}}) &&
        application.view().revision == 4 && adapter.snapshot().title == "service completed",
        "host completion did not share the provider event sequence");
    request.sequence = 11; request.payload = encode_u32(99);
    check_provider_result(application.invoke_provider(request), 100, 2);
    check(application.view().revision == 5 && adapter.snapshot().title == "provider invoked again" &&
        application.acknowledge_provider(11) == ServiceStatus::ok,
        "provider did not resume after view and host-service dispatches");
    application.handle(gui::CloseEvent{});
    ++request.sequence;
    check(adapter.closed() && application.discover_provider(provider_query()).status == ServiceStatus::closed &&
        application.invoke_provider(request).status == ServiceStatus::closed &&
        application.acknowledge_provider(11) == ServiceStatus::closed,
        "closed application retained an available provider bridge");
}

void provider_presentation_retry() {
    ViewState initial, provided, activated;
    provided.title = "accepted provider view"; activated.title = "recovered provider view";
    Script script{{
        call(1, FOUNDATION_PROVIDER_REGISTER, provider_registration(), ServiceStatus::ok, 1, 2),
        call(2, 1, replacement(0, initial), ServiceStatus::ok, 1)}, {
        {provider_event(1, 1, 41), {provider_response(3, 1, 42, 1),
            call(4, 1, replacement(1, provided), ServiceStatus::ok, 2)}},
        {input_event(2, 2, "apply", 1, 1), {call(5, 1, replacement(2, activated), ServiceStatus::ok, 3)}}}};
    FailingAdapter adapter;
    AppendedApplication application(adapter, wasm(script), 7);
    const auto found = application.discover_provider(provider_query());
    check(found.status == ServiceStatus::ok, "retry fixture provider discovery");
    const ProviderRequest request{application.generation(), 1, found.handle, 1, encode_u32(41)};
    adapter.fail_next = true;
    bool failed = false;
    try { (void)application.invoke_provider(request); }
    catch (const std::runtime_error&) { failed = true; }
    check(failed && application.presentation_pending() && application.view().revision == 2 && adapter.snapshot().revision == 1,
        "provider presentation failure lost accepted guest view state");
    check(application.invoke_provider(request).status == ServiceStatus::unavailable &&
        application.discover_provider(provider_query()).status == ServiceStatus::unavailable,
        "pending provider presentation allowed another host invocation");
    application.retry_presentation();
    check_provider_result(application.invoke_provider(request), 42, 1);
    check(!application.presentation_pending() && adapter.snapshot().title == "accepted provider view",
        "provider result replay did not survive presentation recovery");
    application.handle(gui::WidgetEvent{{"apply", 1}, gui::Activate{}});
    check(application.view().revision == 3 && adapter.snapshot().title == "recovered provider view" &&
        application.acknowledge_provider(1) == ServiceStatus::ok,
        "provider presentation retry repeated guest work or consumed an event sequence");
}

void provider_failure_stops_host() {
    Script script{{
        call(1, FOUNDATION_PROVIDER_REGISTER, provider_registration(), ServiceStatus::ok, 1, 2),
        call(2, 1, replacement(0, {}), ServiceStatus::ok, 1)}, {{provider_event(1, 1, 41), {}}}};
    gui::RetainedAdapter adapter;
    AppendedApplication application(adapter, wasm(script), 7);
    const auto found = application.discover_provider(provider_query());
    check(found.status == ServiceStatus::ok, "failure fixture provider discovery");
    ProviderRequest request{application.generation(), 1, found.handle, 1, encode_u32(41)};
    const auto outcome = application.invoke_provider(request);
    check(outcome.status == ServiceStatus::uncertain && outcome.payload.empty(),
        "missing guest provider response became a successful host result");
    ++request.sequence;
    check(application.discover_provider(provider_query()).status == ServiceStatus::closed &&
        application.invoke_provider(request).status == ServiceStatus::closed &&
        application.acknowledge_provider(1) == ServiceStatus::closed && application.view().revision == 1,
        "terminal provider failure left the enclosing application available");
}

class ClosedQueryAdapter final : public gui::RetainedAdapter {
public:
    bool fail_closed_query = false;
    bool closed() const override {
        if (fail_closed_query) throw std::runtime_error("injected adapter query failure");
        return gui::RetainedAdapter::closed();
    }
};
void provider_adapter_guards() {
    Script script{{
        call(1, FOUNDATION_PROVIDER_REGISTER, provider_registration(), ServiceStatus::ok, 1, 2),
        call(2, 1, replacement(0, {}), ServiceStatus::ok, 1)}, {
        {provider_event(1, 1, 41), {provider_response(3, 1, 42, 1)}}}};
    {
        gui::RetainedAdapter adapter;
        AppendedApplication application(adapter, wasm(script), 7);
        const auto found = application.discover_provider(provider_query());
        check(found.status == ServiceStatus::ok, "closed adapter fixture provider discovery");
        const ProviderRequest request{application.generation(), 1, found.handle, 1, encode_u32(41)};
        adapter.close();
        check(application.discover_provider(provider_query()).status == ServiceStatus::closed &&
            application.invoke_provider(request).status == ServiceStatus::closed &&
            application.acknowledge_provider(0) == ServiceStatus::closed,
            "externally closed adapter retained an available provider bridge before the next tick");
    }
    {
        ClosedQueryAdapter adapter;
        AppendedApplication application(adapter, wasm(script), 7);
        const auto found = application.discover_provider(provider_query());
        check(found.status == ServiceStatus::ok, "throwing adapter fixture provider discovery");
        const ProviderRequest request{application.generation(), 1, found.handle, 1, encode_u32(41)};
        check_provider_result(application.invoke_provider(request), 42, 1);
        adapter.fail_closed_query = true;
        const auto acknowledgement = application.acknowledge_provider(1);
        adapter.fail_closed_query = false;
        check(acknowledgement == ServiceStatus::internal_error,
            "throwing adapter query escaped noexcept provider acknowledgement");
        check_provider_result(application.invoke_provider(request), 42, 1);
        check(application.acknowledge_provider(1) == ServiceStatus::ok &&
            application.invoke_provider(request).status == ServiceStatus::expired,
            "failed adapter query retired a provider result or prevented subsequent acknowledgement");
    }
}

void compiled_view_calculator(const char* path) {
    std::ifstream input(path, std::ios::binary | std::ios::ate);
    check(bool(input), "cannot open compiled view calculator module");
    const auto length = input.tellg();
    check(length > 0 && length <= 4 * 1024 * 1024, "compiled view module exceeds the supported byte limit");
    Bytes bytes(static_cast<std::size_t>(length)); input.seekg(0);
    input.read(reinterpret_cast<char*>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
    check(bool(input), "cannot read complete compiled view module");
    AppendedApplication* current = nullptr;
    gui::MemoryAdapter adapter([&](const gui::Event& event) { if (current) current->handle(event); });
    AppendedApplication application(adapter, bytes); current = &application;
    std::fill(bytes.begin(), bytes.end(), 0xff);
    check(application.view().revision == 1 && application.view().title == "Portable calculator" &&
        widget(adapter.snapshot(), "lhs").state.text == "0" && widget(adapter.snapshot(), "rhs").state.text == "0" &&
        widget(adapter.snapshot(), "result").state.text == "Press Sum", "compiled module did not publish its initial generic view");
    const auto initial_epoch = application.input_epoch();
    application.handle(gui::WidgetEvent{{"lhs", 2}, gui::EditText{"7", "0"}});
    application.handle(gui::WidgetEvent{{"lhs", 1}, gui::EditText{"7", "stale"}});
    application.handle(gui::WidgetEvent{{"lhs", 1}, gui::EditText{"12345678901", "0"}});
    check(application.view().revision == 1 && application.input_epoch() == initial_epoch,
        "compiled module received stale or oversized editor input");
    const auto edit = [&](const char* id, std::string value) {
        const auto base = widget(application.view(), id).state.text;
        check(adapter.send(gui::WidgetEvent{{id, 1}, gui::EditText{std::move(value), base}}) == gui::Delivery::delivered,
            "compiled module editor event was not delivered");
    };
    edit("lhs", "7"); edit("rhs", "35");
    check(adapter.send(gui::WidgetEvent{{"sum", 1}, gui::Activate{}}) == gui::Delivery::delivered,
        "compiled module sum action was not delivered");
    check(application.view().revision == 4 && widget(adapter.snapshot(), "result").state.text == "42",
        "compiled module did not calculate 7 plus 35 through the generic view service");
    // More than 64 total gateway calls proves the SDK retires view outcomes
    // instead of silently filling the registry's retained-request ledger.
    for (unsigned n = 0; n < 40; ++n) edit("lhs", n % 2 ? "7" : "8");
    check(application.view().revision == 44 && widget(adapter.snapshot(), "lhs").state.text == "7",
        "compiled module did not acknowledge completed view transactions");
    application.tick(); application.handle(gui::CloseEvent{});
    check(adapter.closed(), "compiled module did not close its generic adapter");
}
} // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 3 && std::string_view(argv[1]) == "--module") {
            compiled_view_calculator(argv[2]);
            std::cout << "compiled C view calculator: generic edits, sum and acknowledged transactions passed\n";
            return 0;
        }
        if (argc != 1) { std::cerr << "Usage: " << argv[0] << " [--module PATH]\n"; return 2; }
        transactions_events_services(); presentation_retry(); providers_compose_with_views();
        provider_presentation_retry(); provider_failure_stops_host(); provider_adapter_guards();
        std::cout << "appended generic GUI transactions, events, services, providers and retry passed\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n'; return 1;
    }
}
