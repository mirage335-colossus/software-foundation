// SPDX-License-Identifier: CC0-1.0
// Isolated-process mock C providers exercising the real owner and Registry.
// These fixtures establish no native engine, loader, SDK or artifact eligibility.
#include "../gui/shared/native_engine_driver.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstring>
#include <functional>
#include <initializer_list>
#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <utility>
#include <vector>

using namespace foundation::appended;
namespace {
using Clock = std::chrono::steady_clock;
using namespace std::chrono_literals;
constexpr std::uint64_t instance = 44;
constexpr std::uint64_t pixel_capabilities = BIB_ENGINE_CAP_SERVICE_QUEUE |
    BIB_ENGINE_CAP_APP_BUNDLE | BIB_ENGINE_CAP_DIRTY_RGBA8;
constexpr std::string_view service_name = "org.example.native-driver.counter";
constexpr std::string_view html = "<!doctype html><title>Native driver fixture</title>";
constexpr std::array<std::uint8_t, 32> header_sha256{
    0xa8,0xe8,0x9d,0xa8,0x5d,0x34,0xb2,0x9a,0x4d,0x1b,0xc4,0x54,0x49,0x57,0x91,0xfa,
    0x60,0x4b,0x81,0xe3,0x47,0x7e,0x48,0xce,0x8c,0xa9,0x02,0xe4,0x33,0x3a,0x9c,0x0d};

void require(bool condition, const char* reason) {
    if (!condition) throw std::runtime_error(reason);
}
std::uint64_t little(std::span<const std::uint8_t> bytes, std::size_t offset, unsigned width) {
    require(width <= 8 && offset <= bytes.size() && width <= bytes.size() - offset,
        "fixture integer extent");
    std::uint64_t result{};
    for (unsigned n = 0; n < width; ++n) result |= std::uint64_t(bytes[offset + n]) << (8 * n);
    return result;
}
bool same(BibEngineDocumentV1 a, BibEngineDocumentV1 b) {
    return a.application_instance == b.application_instance &&
        a.document_sequence == b.document_sequence && a.service_generation == b.service_generation;
}
BibEngineBytesV1 borrowed(std::string_view text) {
    return {reinterpret_cast<const std::uint8_t*>(text.data()), static_cast<std::uint32_t>(text.size()), 0};
}
BibEngineBytesV1 borrowed(const Bytes& bytes) {
    return {bytes.data(), static_cast<std::uint32_t>(bytes.size()), 0};
}
Package fake_package() {
    // Deliberately constructed values, as in the owner unit tests. This is not
    // a container verification fixture and the hashes are not artifact proofs.
    Package result;
    result.application = {"org.example.native-driver", "Native driver fixture", "1.0.0"};
    result.web = {true, "web/index.html", {}};
    result.capabilities = {"foundation.startup.v1"};
    result.services = {std::string(service_name)};
    result.package_sha256 = result.payload_id = result.kernel_sha256 = std::string(64, '1');
    const std::string startup =
        "{\"kind\":\"foundation-appended-startup\",\"primary\":\"web\",\"schema_version\":1}";
    result.files = {{"web/.foundation/startup-v1.json", "web", "application/json", std::string(64, '2'),
        Bytes(startup.begin(), startup.end())}, {"web/index.html", "web", "text/html", std::string(64, '3'),
        Bytes(html.begin(), html.end())}};
    return result;
}
Bytes discovery(std::string_view name = service_name, std::uint32_t maximum_minor = 0) {
    const auto major = encode_u32(1), minor = encode_u32(0), maximum = encode_u32(maximum_minor);
    const std::array<FieldView, 4> fields{{
        {1, FieldType::utf8, true, {reinterpret_cast<const std::uint8_t*>(name.data()), name.size()}},
        {2, FieldType::u32, true, major}, {3, FieldType::u32, true, minor}, {4, FieldType::u32, true, maximum}}};
    Bytes result;
    require(encode_record(fields, result) == CodecStatus::ok, "fixture discovery encoding");
    return result;
}
Bytes request(BibEngineDocumentV1 document, std::uint64_t sequence, std::uint64_t handle,
              std::uint32_t operation, const Bytes& payload) {
    Envelope envelope;
    envelope.generation = document.service_generation; envelope.sequence = sequence;
    envelope.interface_handle = handle; envelope.operation = operation;
    Bytes result;
    require(encode_envelope(envelope, payload, result) == CodecStatus::ok, "fixture request encoding");
    return result;
}

#if defined(FOUNDATION_NATIVE_ENGINE_TEST_MODULE) && FOUNDATION_NATIVE_ENGINE_TEST_MODULE
namespace module_fixture {
constexpr std::uint64_t generation = 31;
constexpr std::string_view name = "org.example.native-driver.module";
constexpr std::uint32_t sequence_address = 128, count_address = 136, control_address = 144;
constexpr std::uint32_t response_address = 2048, native_address = 2304, ack_address = 2560, reply_address = 8192;

// Same deliberately assembled provider shape as appended_engine_owner_test.cpp.
// It runs in the real retained interpreter; no compiler or SDK producer is used.
void append(Bytes& into, const Bytes& bytes) { into.insert(into.end(), bytes.begin(), bytes.end()); }
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
void wasm_name(Bytes& bytes, std::string_view text) {
    uleb(bytes, static_cast<std::uint32_t>(text.size())); bytes.insert(bytes.end(), text.begin(), text.end());
}
void section(Bytes& module, std::uint8_t id, const Bytes& content) {
    module.push_back(id); uleb(module, static_cast<std::uint32_t>(content.size())); append(module, content);
}
void load32(Bytes& code, std::uint32_t address) { constant(code, static_cast<std::int32_t>(address)); append(code, {0x28, 2, 0}); }
void copy64(Bytes& code, std::uint32_t destination, std::uint32_t source) {
    constant(code, static_cast<std::int32_t>(destination)); constant(code, static_cast<std::int32_t>(source));
    append(code, {0x29, 3, 0, 0x37, 3, 0});
}
void event64(Bytes& code, std::uint32_t destination, std::uint32_t offset) {
    constant(code, static_cast<std::int32_t>(destination)); append(code, {0x20, 0, 0x29, 3});
    uleb(code, offset); append(code, {0x37, 3, 0});
}
void trap_if(Bytes& code) { append(code, {0x04, 0x40, 0x00, 0x0b}); }
void gateway(Bytes& code, std::uint32_t packet, std::size_t bytes) {
    constant(code, sequence_address); constant(code, sequence_address);
    append(code, {0x29, 3, 0, 0x42, 1, 0x7c, 0x37, 3, 0});
    copy64(code, packet + FOUNDATION_APPENDED_OFFSET_SEQUENCE, sequence_address);
    constant(code, static_cast<std::int32_t>(packet)); constant(code, static_cast<std::int32_t>(bytes));
    constant(code, reply_address); constant(code, 512); append(code, {0x10, 0}); trap_if(code);
    load32(code, reply_address + FOUNDATION_APPENDED_OFFSET_STATUS); trap_if(code);
}
void acknowledge(Bytes& code, std::size_t bytes) {
    copy64(code, ack_address + 72, sequence_address); gateway(code, ack_address, bytes);
}
struct Field { std::uint16_t id; FieldType type; Bytes bytes; };
Bytes record(std::initializer_list<Field> fields) {
    std::vector<FieldView> views;
    for (const auto& field : fields) views.push_back({field.id, field.type, true, field.bytes});
    Bytes result; require(encode_record(views, result) == CodecStatus::ok, "module fixture record encoding"); return result;
}
Bytes bytes(std::uint64_t native_handle) {
    const BibEngineDocumentV1 guest{0, 0, generation};
    const SchemaId schema{1};
    const auto discover = request(guest, 1, 0, FOUNDATION_APPENDED_CONTROL_DISCOVER,
        discovery(FOUNDATION_PROVIDER_SERVICE_NAME));
    const auto registration = record({{1, FieldType::utf8, Bytes(name.begin(), name.end())},
        {2, FieldType::u32, encode_u32(1)}, {3, FieldType::u32, encode_u32(2)},
        {4, FieldType::bytes, Bytes(schema.begin(), schema.end())},
        {5, FieldType::u32, encode_u32(4)}, {6, FieldType::u32, encode_u32(8)}});
    const auto register_packet = request(guest, 1, 1, FOUNDATION_PROVIDER_REGISTER, registration);
    const auto response = request(guest, 1, 1, FOUNDATION_PROVIDER_RESPOND, record({
        {1, FieldType::u64, encode_u64(1)}, {2, FieldType::u64, encode_u64(1)},
        {3, FieldType::u32, encode_u32(0)}, {4, FieldType::bytes, Bytes(8)}}));
    const auto native = request(guest, 1, native_handle, 1, encode_u32(0));
    const auto ack = request(guest, 1, 0, FOUNDATION_APPENDED_CONTROL_ACKNOWLEDGE,
        record({{1, FieldType::u64, encode_u64(1)}}));
    const std::array<std::pair<std::uint32_t, Bytes>, 5> data{{{256, discover}, {512, register_packet},
        {response_address, response}, {native_address, native}, {ack_address, ack}}};
    std::array<Bytes, 7> code;
    constant(code[0], FOUNDATION_APPENDED_ABI_VERSION); constant(code[1], 16384);
    gateway(code[3], 256, discover.size()); copy64(code[3], control_address, reply_address + 72);
    acknowledge(code[3], ack.size()); copy64(code[3], 512 + FOUNDATION_APPENDED_OFFSET_INTERFACE, control_address);
    gateway(code[3], 512, register_packet.size()); acknowledge(code[3], ack.size()); constant(code[3], 0);
    auto& dispatch = code[4]; gateway(dispatch, native_address, native.size()); acknowledge(dispatch, ack.size());
    constant(dispatch, count_address); load32(dispatch, count_address); constant(dispatch, 1); append(dispatch, {0x6a, 0x36, 2, 0});
    copy64(dispatch, response_address + FOUNDATION_APPENDED_OFFSET_INTERFACE, control_address);
    event64(dispatch, response_address + 72, FOUNDATION_APPENDED_OFFSET_CORRELATION); event64(dispatch, response_address + 88, 72);
    constant(dispatch, response_address + 116); append(dispatch, {0x20, 0, 0x28, 2, 100});
    constant(dispatch, 1); append(dispatch, {0x6a, 0x36, 2, 0});
    constant(dispatch, response_address + 120); load32(dispatch, count_address); append(dispatch, {0x36, 2, 0});
    gateway(dispatch, response_address, response.size()); acknowledge(dispatch, ack.size()); constant(dispatch, 0); constant(code[5], 0);
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
    for (std::size_t n = 0; n < names.size(); ++n) {
        wasm_name(exports, names[n]); exports.push_back(0); uleb(exports, static_cast<std::uint32_t>(n + 1));
    }
    section(module, 7, exports); Bytes bodies{7};
    for (const auto& instructions : code) {
        Bytes body{0}; append(body, instructions); body.push_back(0x0b);
        uleb(bodies, static_cast<std::uint32_t>(body.size())); append(bodies, body);
    }
    section(module, 10, bodies); Bytes segments; uleb(segments, static_cast<std::uint32_t>(data.size()));
    for (const auto& [address, content] : data) {
        segments.push_back(0); constant(segments, static_cast<std::int32_t>(address)); segments.push_back(0x0b);
        uleb(segments, static_cast<std::uint32_t>(content.size())); append(segments, content);
    }
    section(module, 11, segments); return module;
}
} // namespace module_fixture
#endif

struct Fixture;
Fixture* active{}; // One mock provider and one driver per test process.

struct Fixture {
    std::shared_ptr<EngineOwner> owner;
    NativeEngineDriver* driver{};
    BibEngineProviderV1 table{};
    NativeEngineExpectation expectation{};
    BibEngineHostV1 host{};
    BibEngineDocumentV1 document{instance, 1, 0};
    BibEngineResourceEpochV1 resource{};
    Clock::time_point now{1000s};
    std::atomic<unsigned> posted_wakes{};
    unsigned provider_calls{}, starts{}, advances{}, currents{}, deliveries{}, collectors{}, disposals{};
    unsigned effects{}, acknowledged{}, command_calls{}, query_calls{};
    unsigned module_effects{}, module_completions{};
    std::uint32_t module_input{41};
    bool module_mode{}, submit_successor_discovery{};
    std::string requested_service{service_name};
    std::uint64_t handle{}, pending_sequence{}, pending_generation{};
    bool inside_provider{}, submit_discovery{}, submit_invocation{}, nested_start{}, waiting{}, fail_advance{};
    bool close_from_current{};
    bool initial_collector_due{};
    bool use_resources{}, emit_frames{}, invalid_frame{}, arm_timer{}, disarm_timer{}, navigate_on_delivery{};
    bool fail_delivery{}, reenter_audit{}, inside_observer{}, keep_resource_lease{}, exercise_epochs{};
    unsigned observer_calls{}, recursive_tick_rejections{}, dispose_resource_retirements{};
    BibEngineResourceResponseV1 held_resource{};
    std::string callback_failure;
    std::vector<std::uint32_t> ack_statuses;
    std::vector<Bytes> completions, audits;
    std::vector<std::uint64_t> disposed_generations;

    void check(bool condition, const char* message) {
        if (!condition) {
            if (callback_failure.empty()) callback_failure = message;
            throw std::runtime_error(message);
        }
    }
    template<class Function> std::int32_t turn(Function function) {
        ++provider_calls;
        check(!inside_provider, "mock provider unexpectedly reentered");
        inside_provider = true;
        const auto status = host.enter_engine(host.context);
        if (status != FOUNDATION_APPENDED_SERVICE_OK) {
            inside_provider = false;
            return BIB_ENGINE_REENTRANT;
        }
        check(owner->callback_depth() == 1, "owner physical turn was not entered exactly once");
        bool native_left = false;
        try {
            const auto result = function();
            host.leave_engine(host.context);
            native_left = true;
            check(owner->callback_depth() == 1, "native leave released the complete provider-call barrier early");
            inside_provider = false;
            return result;
        } catch (...) {
            if (!native_left) host.leave_engine(host.context);
            inside_provider = false;
            throw;
        }
    }
    void begin_epoch() {
        check(!document.service_generation, "prospective document already has service authority");
        resource = {}; resource.size = sizeof(resource);
        check(host.begin_resource_epoch(host.context, &document, &resource) == BIB_ENGINE_OK &&
            resource.size == sizeof(resource) && resource.resource_epoch && resource.context &&
            resource.resolve && resource.release, "actual owner resource epoch was not bound");
    }
    void begin_document() {
        begin_epoch();
        document.service_generation = host.begin_service_document(host.context, &document);
        check(document.service_generation != 0 && owner->identity().application_instance == instance &&
            owner->identity().document_sequence == document.document_sequence &&
            owner->identity().service_generation == document.service_generation,
            "startup did not adopt the actual native instance/document/generation");
    }
    void submit(std::uint64_t sequence, std::uint64_t route, std::uint32_t operation, const Bytes& payload) {
        const auto before_effects = effects, before_module_effects = module_effects;
        auto bytes = request(document, sequence, route, operation, payload);
        const auto input = borrowed(bytes);
        check(host.submit_service(host.context, document.service_generation, &input, module_mode ? 2U : 1U) == FOUNDATION_APPENDED_SERVICE_OK,
            "actual owner rejected native service submission");
        check(effects == before_effects && module_effects == before_module_effects,
            "native effect ran synchronously inside provider submission");
        std::fill(bytes.begin(), bytes.end(), 0xee); // Admission must have copied it.
    }
    void resources() {
        const std::string url = "app://" + std::string(64, '1') + "/web/index.html";
        auto resolve = [&](std::string_view method, const std::string& target) {
            BibEngineResourceRequestV1 input{sizeof(input), 0, resource.resource_epoch,
                borrowed(method), borrowed(target)};
            BibEngineResourceResponseV1 output{}; output.size = sizeof(output);
            check(resource.resolve(resource.context, &input, &output) == BIB_ENGINE_OK,
                "resource adapter failed a complete immutable lookup");
            return output;
        };
        const auto get = resolve("GET", url);
        check(get.status == 200 && get.lease && get.body_length == html.size() &&
            get.content_length == html.size() && get.body &&
            std::string_view(reinterpret_cast<const char*>(get.mime.data), get.mime.length) == "text/html" &&
            std::string_view(reinterpret_cast<const char*>(get.body), std::size_t(get.body_length)) == html,
            "GET did not preserve owned body, MIME, lease and lengths");
        const auto head = resolve("HEAD", url);
        check(head.status == 200 && head.lease && head.lease != get.lease &&
            head.body_length == 0 && head.content_length == html.size(), "HEAD did not preserve the body-free length");
        check(std::string_view(reinterpret_cast<const char*>(get.body), std::size_t(get.body_length)) == html,
            "a second resource lookup invalidated a live local lease");
        const auto denied = resolve("GET", "https://example.invalid/escape");
        check(denied.status == 403 && !denied.lease && !denied.body_length,
            "resource adapter admitted an external resource or invented a lease");
        resource.release(resource.context, head.lease);
        if (keep_resource_lease) held_resource = get;
        else resource.release(resource.context, get.lease);
    }
    void prospective_epochs() {
        const auto old = resource;
        const BibEngineDocumentV1 future{instance, 3, 0};
        BibEngineResourceEpochV1 staged{}; staged.size = sizeof(staged);
        check(host.begin_resource_epoch(host.context, &future, &staged) == BIB_ENGINE_OK &&
            staged.resource_epoch != old.resource_epoch && staged.context != old.context,
            "prospective resource authority was not kept separate");
        document = {instance, 2, 0};
        document.service_generation = host.begin_service_document(host.context, &document);
        check(document.service_generation && owner->identity().document_sequence == 2,
            "intervening document adoption did not succeed");
        host.retire_resource_epoch(host.context, old.resource_epoch);
        check(driver->state() != NativeEngineState::process_exit_required,
            "late explicit retirement failed after owner auto-pruned its old epoch");
        const BibEngineDocumentV1 current_prospective{instance, 2, 0};
        BibEngineResourceEpochV1 next{}; next.size = sizeof(next);
        check(host.begin_resource_epoch(host.context, &current_prospective, &next) == BIB_ENGINE_OK &&
            next.resource_epoch != old.resource_epoch && next.resource_epoch != staged.resource_epoch &&
            next.context == old.context && next.context != staged.context,
            "adoption displaced the staged epoch or reused an unretired provider context");
        const BibEngineDocumentV1 overflow{instance, 4, 0};
        BibEngineResourceEpochV1 refused{}; refused.size = sizeof(refused);
        check(host.begin_resource_epoch(host.context, &overflow, &refused) == BIB_ENGINE_LIMIT &&
            driver->state() != NativeEngineState::process_exit_required,
            "two retained resource contexts did not enforce their negotiated bound");
        const std::string url = "app://" + std::string(64, '1') + "/web/index.html";
        BibEngineResourceRequestV1 input{sizeof(input), 0, staged.resource_epoch, borrowed("GET"), borrowed(url)};
        BibEngineResourceResponseV1 output{}; output.size = sizeof(output);
        check(staged.resolve(staged.context, &input, &output) == BIB_ENGINE_OK && output.status == 200 &&
            output.lease && output.body_length == html.size() && output.body &&
            std::string_view(reinterpret_cast<const char*>(output.body), std::size_t(output.body_length)) == html,
            "intervening adoption retired or rebound an unrelated prospective resource epoch");
        staged.release(staged.context, output.lease);
        host.retire_resource_epoch(host.context, staged.resource_epoch);
        resource = next;
    }
    void frames() {
        Bytes pixels(800 * 600 * 4, 0);
        for (std::size_t n = 3; n < pixels.size(); n += 4) pixels[n] = 255;
        pixels[0] = 12; pixels[1] = 34; pixels[2] = 56;
        if (invalid_frame) pixels[3] = 0;
        BibEngineDamageV1 full{sizeof(full), 1, document, 19, 0, 0, 800, 600, 3200,
            static_cast<std::uint32_t>(pixels.size()), pixels.data()};
        host.damage(host.context, &full);
        std::fill(pixels.begin(), pixels.end(), 0); // The owner cannot borrow it.
        if (invalid_frame) return;
        check(owner->frame() && owner->frame()->frame_revision == 1 && owner->frame()->rgba[0] == 12,
            "initial native global frame revision was not copied/projected to the document");
        const std::array<std::uint8_t, 8> patch{71, 72, 73, 255, 81, 82, 83, 255};
        BibEngineDamageV1 delta{sizeof(delta), 1, document, 23, 7, 9, 2, 1, 8,
            static_cast<std::uint32_t>(patch.size()), patch.data()};
        host.damage(host.context, &delta);
        check(owner->frame() && owner->frame()->frame_revision == 2 &&
            owner->frame()->rgba[(9 * 800 + 7) * 4] == 71 && owner->frame()->rgba[0] == 12,
            "native damage did not preserve its base frame and per-document revision");
    }
    static void post(void* context) noexcept {
        static_cast<Fixture*>(context)->posted_wakes.fetch_add(1, std::memory_order_relaxed);
    }
    static std::int32_t BIB_ENGINE_CALL start(const BibEngineHostV1* callbacks,
            const BibEngineStartV1* config, BibEngineStartResultV1* result) {
        auto& f = *active; ++f.starts;
        f.check(callbacks && config && result && result->size >= sizeof(*result), "missing startup C records");
        f.host = *callbacks;
        f.check(config->raster_output == 1 && config->required_capabilities == pixel_capabilities &&
            config->persist_seed.length == 0 && config->entry_url.length > 0,
            "pixel profile startup silently widened capabilities or persistence");
        const auto code = f.turn([&] {
            if (f.nested_start) {
                f.check(f.host.enter_engine(f.host.context) == FOUNDATION_APPENDED_SERVICE_OK &&
                    f.owner->callback_depth() == 1, "nested native enter was not locally coalesced");
                f.host.leave_engine(f.host.context);
                f.check(f.owner->callback_depth() == 1, "nested native leave dropped the physical barrier");
            }
            if (f.waiting) f.begin_epoch();
            else f.begin_document();
            if (f.submit_discovery) f.submit(1, 0, FOUNDATION_APPENDED_CONTROL_DISCOVER,
                discovery(f.requested_service, f.module_mode ? 2 : 0));
            return BIB_ENGINE_OK;
        });
        *result = {sizeof(*result), BIB_ENGINE_START_READY, instance};
        return code;
    }
    static std::int32_t BIB_ENGINE_CALL advance(const BibEngineAdvanceV1* input) {
        auto& f = *active; ++f.advances;
        f.check(input && input->application_instance == instance && input->render <= 1, "wrong advance identity");
        return f.turn([&] {
            if (f.fail_advance) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
            if (f.use_resources) { f.use_resources = false; f.resources(); }
            if (f.exercise_epochs) { f.exercise_epochs = false; f.prospective_epochs(); }
            if (f.emit_frames) { f.emit_frames = false; f.frames(); }
            if (f.arm_timer) { f.arm_timer = false; f.host.replace_timer_ms(f.host.context, 25, 1); }
            if (f.disarm_timer) { f.disarm_timer = false; f.host.replace_timer_ms(f.host.context, 0, 0); }
            if (f.submit_successor_discovery) {
                f.submit_successor_discovery = false;
                f.submit(1, 0, FOUNDATION_APPENDED_CONTROL_DISCOVER, discovery(f.requested_service, f.module_mode ? 2 : 0));
            }
            if (f.submit_invocation) {
                f.submit_invocation = false; f.submit(2, f.handle, 1, encode_u32(f.module_mode ? f.module_input : 41));
            }
            return BIB_ENGINE_OK;
        });
    }
    static std::int32_t BIB_ENGINE_CALL current(std::uint64_t target, BibEngineDocumentV1* output) {
        auto& f = *active; ++f.currents;
        f.check(target == instance && output, "wrong current-document target");
        return f.turn([&] {
            if (f.waiting) {
                if (f.close_from_current) { f.close_from_current = false; f.driver->request_close(); }
                return BIB_ENGINE_STALE;
            }
            *output = f.document;
            return BIB_ENGINE_OK;
        });
    }
    static std::int32_t BIB_ENGINE_CALL command(const BibEngineCommandV1*, BibEngineReplyBufferV1*, BibEngineCommandResultV1*) {
        ++active->command_calls; return BIB_ENGINE_UNSUPPORTED;
    }
    static std::int32_t BIB_ENGINE_CALL query(const BibEngineQueryV1*, BibEngineReplyBufferV1*, BibEngineQueryResultV1*) {
        ++active->query_calls; return BIB_ENGINE_UNSUPPORTED;
    }
    static std::int32_t BIB_ENGINE_CALL deliver(const BibEngineDocumentV1* target, const BibEngineBytesV1* input) {
        auto& f = *active; ++f.deliveries;
        return f.turn([&] {
            if (f.fail_delivery) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
            f.check(target && same(*target, f.document) && input && input->data && !input->reserved,
                "delivery lost its exact actual document identity");
            Bytes copied(input->data, input->data + input->length);
            Envelope envelope; std::span<const std::uint8_t> payload;
            const auto decoded = decode_envelope(copied, envelope, payload);
            const bool valid = decoded == CodecStatus::ok &&
                envelope.kind == FOUNDATION_APPENDED_MESSAGE_COMPLETION && envelope.generation == target->service_generation &&
                envelope.service_status == FOUNDATION_APPENDED_SERVICE_OK;
            if (!valid) {
                const auto diagnostic = "actual Registry completion failed: codec=" + std::to_string(static_cast<unsigned>(decoded)) +
                    " kind=" + std::to_string(envelope.kind) + " generation=" + std::to_string(envelope.generation) +
                    " expected=" + std::to_string(target->service_generation) + " sequence=" + std::to_string(envelope.sequence) +
                    " operation=" + std::to_string(envelope.operation) + " status=" + std::to_string(envelope.service_status);
                f.check(false, diagnostic.c_str());
            }
            if (envelope.sequence == 1) {
                std::vector<FieldView> fields;
                f.check(decode_record(payload, fields) == CodecStatus::ok && fields.size() == 6 &&
                    read_u64(fields.front(), f.handle) && f.handle, "actual discovery did not issue an opaque route");
                f.check(fields[1].type == FieldType::utf8 &&
                    std::string_view(reinterpret_cast<const char*>(fields[1].value.data()), fields[1].value.size()) == f.requested_service,
                    "discovery returned a different native/module service");
            } else {
                if (f.module_mode) {
                    f.check(envelope.sequence == 2 && payload.size() == 8 && little(payload, 0, 4) == f.module_input + 1 &&
                        little(payload, 4, 4) == f.module_completions + 1 && f.module_effects == f.module_completions + 1,
                        "actual Module lost its persistent state or deliberate native registration");
                    ++f.module_completions;
                } else {
                    f.check(envelope.sequence == 2 && payload.size() == 4 && little(payload, 0, 4) == 42 && f.effects == 1,
                        "actual native completion was not the one bounded effect");
                }
            }
            f.completions.push_back(std::move(copied));
            f.pending_sequence = envelope.sequence; f.pending_generation = target->service_generation;
            f.initial_collector_due = true;
            if (f.navigate_on_delivery && envelope.sequence == 2) {
                f.navigate_on_delivery = false;
                f.host.close_service_document(f.host.context, f.document.service_generation);
                f.host.retire_resource_epoch(f.host.context, f.resource.resource_epoch);
                f.document = {instance, 2, 0}; f.begin_document();
                f.pending_sequence = f.pending_generation = 0;
            }
            return BIB_ENGINE_OK;
        });
    }
    static std::uint32_t BIB_ENGINE_CALL collect(const BibEngineDocumentV1* target) {
        auto& f = *active; ++f.collectors;
        if (f.initial_collector_due) {
            f.check(f.owner->callback_depth() == 1,
                "delivery and its initial collector did not share one complete physical turn");
            f.initial_collector_due = false;
        }
        std::uint32_t actual = FOUNDATION_APPENDED_SERVICE_UNAVAILABLE;
        const auto result = f.turn([&] {
            if (!target || !same(*target, f.document) || !f.pending_sequence) return BIB_ENGINE_OK;
            f.check(f.pending_generation == target->service_generation, "collector substituted a successor generation");
            actual = f.host.stage_service_ack(f.host.context, target->service_generation, f.pending_sequence);
            f.ack_statuses.push_back(actual);
            if (actual == FOUNDATION_APPENDED_SERVICE_OK) {
                ++f.acknowledged; f.pending_sequence = f.pending_generation = 0;
            }
            return BIB_ENGINE_OK;
        });
        return result == BIB_ENGINE_OK ? actual : FOUNDATION_APPENDED_SERVICE_UNAVAILABLE;
    }
    static std::int32_t BIB_ENGINE_CALL dispose(std::uint64_t target, std::uint64_t generation) {
        auto& f = *active; ++f.disposals;
        return f.turn([&] {
            f.check(target == instance && generation, "retired disposal lost its original authority");
            f.check(std::find(f.disposed_generations.begin(), f.disposed_generations.end(), generation) ==
                f.disposed_generations.end(), "retired engine document disposal was replayed");
            if (generation == f.document.service_generation && f.resource.resource_epoch) {
                // Global owner CLOSE may already have pruned the epoch. The
                // provider's later explicit retirement remains a valid notice.
                f.host.retire_resource_epoch(f.host.context, f.resource.resource_epoch);
                ++f.dispose_resource_retirements;
                f.check(f.driver->state() != NativeEngineState::process_exit_required,
                    "global close rejected the provider's late explicit epoch retirement");
            }
            f.disposed_generations.push_back(generation);
            return BIB_ENGINE_OK;
        });
    }
    explicit Fixture(bool with_module = false, bool abandonment_policy = true) : module_mode(with_module) {
        require(!active, "one mock provider per process"); active = this;
        expectation.pointer_bits = sizeof(void*) * 8;
#if defined(_WIN32) && (defined(_M_X64) || defined(__x86_64__))
        expectation.target_system = BIB_ENGINE_TARGET_WINDOWS; expectation.target_processor = BIB_ENGINE_CPU_X86_64;
#elif defined(__linux__) && defined(__aarch64__)
        expectation.target_system = BIB_ENGINE_TARGET_LINUX; expectation.target_processor = BIB_ENGINE_CPU_AARCH64;
#elif defined(__linux__) && defined(__x86_64__)
        expectation.target_system = BIB_ENGINE_TARGET_LINUX; expectation.target_processor = BIB_ENGINE_CPU_X86_64;
#else
        throw std::runtime_error("native driver fixture needs a supported native 64-bit target");
#endif
        expectation.contract_header_sha256 = header_sha256;
        expectation.build_identity_sha256.fill(0x51); expectation.source_recipe_sha256.fill(0x73);
        table.size = sizeof(table); table.abi_major = BIB_ENGINE_ABI_MAJOR; table.abi_minor = BIB_ENGINE_ABI_MINOR;
        auto& build = table.build; build.size = sizeof(build); build.layout_revision = BIB_ENGINE_LAYOUT_V1;
        build.target_system = expectation.target_system; build.target_processor = expectation.target_processor;
        build.pointer_bits = expectation.pointer_bits; build.lifetime = BIB_ENGINE_LIFETIME_PROCESS; build.maximum_starts = 1;
        build.fixed_viewport_width = 800; build.fixed_viewport_height = 600; build.capabilities = pixel_capabilities;
        std::copy(header_sha256.begin(), header_sha256.end(), build.contract_header_sha256);
        std::copy(expectation.build_identity_sha256.begin(), expectation.build_identity_sha256.end(), build.build_identity_sha256);
        std::copy(expectation.source_recipe_sha256.begin(), expectation.source_recipe_sha256.end(), build.source_recipe_sha256);
        table.limits = NativeEngineOptions{}.limits;
        table.start = start; table.advance = advance; table.current_document = current;
        table.command = command; table.query = query; table.deliver_services = deliver;
        table.collect_service_ack = collect; table.dispose_retired_service_document = dispose;
        EngineOwnerConfiguration config;
        config.worker_epoch = 17; config.application_instance = 0;
        config.abandon_closed_document_outcomes = abandonment_policy;
        config.native_services.push_back({{std::string(service_name), 1, 0, SchemaId{1}, 4},
            [this](std::uint32_t operation, auto input, auto output) -> ServiceReply {
                check(!inside_provider && owner->callback_depth() == 0, "native effect ran before the complete engine turn ended");
                check(operation == 1 && input.size() == 4 && output.size() >= 4,
                    "native handler received changed or unbounded input");
                const auto number = little(input, 0, 4);
                if (module_mode) { check(number == 0, "Module changed its deliberate native input"); ++module_effects; }
                else { check(number == 41, "native handler received changed input"); ++effects; }
                const auto value = encode_u32(static_cast<std::uint32_t>(number) + 1);
                std::copy(value.begin(), value.end(), output.begin());
                return {ServiceStatus::ok, 4};
            }});
        auto package = fake_package();
#if defined(FOUNDATION_NATIVE_ENGINE_TEST_MODULE) && FOUNDATION_NATIVE_ENGINE_TEST_MODULE
        if (with_module) {
            config.module_generation = module_fixture::generation;
            config.module_factory = make_engine_module_binding;
            Registry probe(module_fixture::generation);
            require(install_native_services(probe, config.native_services) == ServiceStatus::ok,
                "module fixture could not install the deliberate actual native registrations");
            const auto native = probe.discover({service_name, 1, 0, 0, SchemaId{1}});
            require(native.status == ServiceStatus::ok && native.handle,
                "module fixture could not determine the deliberate native route");
            package.binary = {true, "binary/application.wasm", "foundation-guest-v1"};
            package.services.push_back("foundation.providers"); package.capabilities.push_back("foundation.providers.v1");
            package.files.insert(package.files.begin(), {"binary/application.wasm", "binary", "application/wasm",
                std::string(64, '4'), module_fixture::bytes(native.handle)});
            requested_service = module_fixture::name;
        }
#else
        require(!with_module, "optional Module fixture was not selected at compilation");
#endif
        owner = std::make_shared<EngineOwner>(std::move(package), std::move(config));
    }
    void bind(NativeEngineOptions options = {}) {
        options.observe_retirement = [this](const NativeEngineAudit& audit) {
            ++observer_calls;
            check(!inside_observer, "retirement observer was entered recursively");
            check(!inside_provider && owner->callback_depth() == 0 && audit.transfer &&
                audit.identity.application_instance == instance && !audit.original.empty(),
                "retirement audit was synthetic or delivered inside the engine");
            if (reenter_audit) {
                inside_observer = true;
                const auto calls = provider_calls, observations = observer_calls;
                bool rejected = false;
                try { driver->tick(now); } catch (const std::logic_error&) { rejected = true; }
                inside_observer = false;
                check(rejected && provider_calls == calls && observer_calls == observations,
                    "recursive tick entered native code or the observer before refusing");
                ++recursive_tick_rejections;
            }
            audits.emplace_back(audit.original.begin(), audit.original.end()); return true;
        };
        driver = &NativeEngineDriver::bind_once(NativeEngineProvider::checked(table, expectation), owner,
            std::move(options), {this, post});
    }
    void healthy() const {
        require(callback_failure.empty(), callback_failure.c_str());
        require(owner->callback_depth() == 0 && !inside_provider, "complete driver call retained a native turn");
        require(command_calls == 0 && query_calls == 0, "pixel259 dispatched unnegotiated command/query operations");
    }
    template<class Predicate> void until(Predicate done, const char* message, unsigned maximum = 64) {
        for (unsigned n = 0; n < maximum && !done(); ++n) {
            now += 1ms; driver->tick(now); healthy();
            require(driver->state() != NativeEngineState::process_exit_required, "unexpected terminal driver failure");
        }
        require(done(), message);
    }
    void ready(NativeEngineOptions options = {}) {
        bind(std::move(options)); driver->start_once(now); healthy();
        until([&] { return driver->state() == NativeEngineState::ready; }, "native document never became ready");
        require(starts == 1 && owner->identity().application_instance == instance &&
            owner->identity().service_generation, "native startup identity not adopted");
    }
    void discovered() {
        submit_discovery = true; ready();
        until([&] { return acknowledged == 1; }, "discovery completion/actual ACK did not settle");
        require(handle && effects == 0 && completions.size() == 1, "discovery unexpectedly executed a native effect");
    }
};

void metadata(Fixture& f) {
    auto rejects = [&](auto mutate) {
        auto changed = f.table; auto expected = f.expectation; mutate(changed, expected);
        bool rejected = false;
        try { (void)NativeEngineProvider::checked(changed, expected); }
        catch (const std::exception&) { rejected = true; }
        require(rejected, "invalid C provider metadata was accepted");
        require(!f.starts && !f.provider_calls && !f.owner->configured(), "metadata inspection executed startup or an owner effect");
    };
    rejects([](auto& t, auto&) { t.abi_major = 2; });
    rejects([](auto& t, auto&) { t.reserved = 1; });
    rejects([](auto& t, auto&) { t.build.target_processor = BIB_ENGINE_CPU_WASM32; });
    rejects([](auto& t, auto&) { t.build.pointer_bits = 32; });
    rejects([](auto& t, auto&) { t.build.layout_revision = 2; });
    rejects([](auto& t, auto&) { t.build.maximum_starts = 2; });
    rejects([](auto& t, auto&) { t.build.fixed_viewport_width = 801; });
    rejects([](auto& t, auto&) { t.build.capabilities |= BIB_ENGINE_CAP_KEY_V1; });
    rejects([](auto& t, auto&) { t.build.contract_header_sha256[0] ^= 1; });
    rejects([](auto& t, auto&) { t.build.build_identity_sha256[0] ^= 1; });
    rejects([](auto& t, auto&) { t.build.source_recipe_sha256[0] ^= 1; });
    rejects([](auto&, auto& e) { e.contract_header_sha256[0] ^= 1; });
    rejects([](auto& t, auto&) { t.deliver_services = nullptr; });
    rejects([](auto& t, auto&) { t.limits.maximum_service_message_bytes = 0; });
    (void)NativeEngineProvider::checked(f.table, f.expectation);
    require(!f.provider_calls, "valid metadata checking entered a mock provider");
}
void run(std::string_view name) {
    // The production driver deliberately has no reset/destructor. Every named
    // scenario has a fresh process; its owners/callback context live until exit.
    bool with_module = false;
#if defined(FOUNDATION_NATIVE_ENGINE_TEST_MODULE) && FOUNDATION_NATIVE_ENGINE_TEST_MODULE
    with_module = name == "both";
#endif
    auto& f = *new Fixture(with_module, name != "owner-policy");
#if defined(FOUNDATION_NATIVE_ENGINE_TEST_MODULE) && FOUNDATION_NATIVE_ENGINE_TEST_MODULE
    if (name == "both") {
        f.discovered();
        require(f.owner->has_module() && !f.module_effects && !f.effects,
            "both startup did not initialize the actual Module without an application effect");
        f.navigate_on_delivery = true; f.submit_invocation = true; f.driver->request_advance();
        f.until([&] { return f.module_completions == 1 && f.disposals == 1; },
            "both first Module outcome did not survive replacement/retirement");
        require(f.owner->has_module() && f.module_effects == 1 && f.owner->identity().document_sequence == 2 &&
            f.audits.size() == 1 && f.audits.front() == f.completions.back(),
            "both replacement lost its exact original Module outcome or persistent binding");
        f.submit_successor_discovery = true; f.driver->request_advance();
        f.until([&] { return f.acknowledged == 2; }, "successor document could not discover/ACK the retained Module provider");
        f.module_input = 7; f.submit_invocation = true; f.driver->request_advance();
        f.until([&] { return f.module_completions == 2 && f.acknowledged == 3; },
            "retained Module did not complete/ACK a second document call");
        require(f.module_effects == 2 && !f.effects && f.completions.size() == 4,
            "Module state/native registrations were reset or an effect replayed after replacement");
        f.driver->request_close();
        f.until([&] { return f.driver->state() == NativeEngineState::detached; }, "both close did not finish actual owner retirement");
        require(f.owner->closed() && f.disposals == 2 && f.dispose_resource_retirements == 1,
            "both close retained a document or repeated a native disposal/resource retirement");
        f.healthy(); return;
    }
#endif
    if (name == "metadata") { metadata(f); return; }
    if (name == "bound-wake-close") {
        f.bind(); const auto before = f.posted_wakes.load();
        f.driver->request_advance();
        require(f.posted_wakes.load() > before, "bound advance did not post its owner wake");
        f.driver->tick(f.now);
        require(f.driver->state() == NativeEngineState::bound && !f.starts && !f.provider_calls && !f.owner->configured(),
            "bound wake consumption entered startup or provider execution");
        const auto consumed = f.posted_wakes.load(); f.driver->request_close();
        require(f.posted_wakes.load() > consumed, "consumed bound wake suppressed a later close notification");
        f.driver->tick(f.now += 1ms);
        require(f.driver->state() == NativeEngineState::detached && !f.starts && !f.provider_calls &&
            !f.owner->configured() && f.owner->closed(), "bound close did not detach without native START");
        return;
    }
    if (name == "waiting-close") {
        f.waiting = true; f.bind(); f.driver->start_once(f.now); f.healthy();
        require(f.driver->state() == NativeEngineState::waiting_document,
            "waiting-close fixture failed before its stale readiness query");
        const auto before = f.advances, current = f.currents; f.close_from_current = true;
        f.driver->tick(f.now += 1ms); f.healthy();
        require(f.currents == current + 1 && f.advances == before && !f.close_from_current,
            "close requested by stale CURRENT admitted a later provider ADVANCE");
        f.until([&] { return f.driver->state() == NativeEngineState::detached; },
            "stale readiness close did not finish actual owner retirement");
        require(f.owner->closed() && f.starts == 1 && f.advances == before,
            "waiting close failed to retire the owner or resumed native work");
        return;
    }
    if (name == "prestart-close") {
        f.bind(); f.driver->request_close();
        require(!f.starts && !f.provider_calls && !f.owner->configured(),
            "prestart close synchronously configured/entered the provider");
        f.driver->start_once(f.now);
        require(f.driver->state() == NativeEngineState::detached && !f.starts && !f.provider_calls &&
            !f.owner->configured() && !f.effects && !f.module_effects,
            "prestart close admitted startup/configuration effects");
        f.driver->tick(f.now += 1ms);
        require(!f.starts && !f.provider_calls, "detached prestart close later entered a provider");
        return;
    }
    if (name == "owner-policy") {
        f.bind(); f.driver->start_once(f.now);
        require(f.driver->state() == NativeEngineState::process_exit_required && !f.starts && !f.provider_calls && !f.effects,
            "mismatched immutable owner abandonment policy reached native START");
        f.driver->request_advance(); f.driver->tick(f.now += 1ms);
        require(!f.starts && !f.provider_calls, "policy rejection later admitted native execution");
        return;
    }
    if (name == "wrong-thread") {
        f.ready(); const auto before = f.provider_calls;
        std::thread worker([&] { f.host.replace_timer_ms(f.host.context, 1, 1); }); worker.join();
        require(f.driver->state() == NativeEngineState::process_exit_required && f.provider_calls == before,
            "non-wake worker callback did not fail closed without entering native code");
        f.driver->request_advance(); f.driver->request_close(); f.driver->tick(f.now += 1ms);
        require(f.provider_calls == before, "wrong-thread callback failure allowed later native work");
        return;
    }
    if (name == "startup") {
        f.nested_start = true; f.ready();
        const auto before = f.provider_calls;
        try { f.driver->start_once(f.now); } catch (const std::exception&) {}
        require(f.starts == 1 && f.provider_calls == before, "a second START entered the C provider");
        bool refused = false;
        try { (void)NativeEngineDriver::bind_once(NativeEngineProvider::checked(f.table, f.expectation), f.owner); }
        catch (const std::exception&) { refused = true; }
        require(refused && f.starts == 1, "a second process owner was bound");
        return;
    }
    if (name == "wake-progress") {
        f.submit_discovery = true; NativeEngineOptions options; options.maximum_steps_per_tick = 1;
        f.bind(options);
        auto consumed = f.posted_wakes.load();
        f.driver->start_once(f.now); f.healthy();
        auto drain = [&] {
            for (unsigned n = 0; n < 64; ++n) {
                const auto posted = f.posted_wakes.load();
                if (posted == consumed) return;
                consumed = posted; f.driver->tick(f.now += 1ms); f.healthy();
                require(f.driver->state() != NativeEngineState::process_exit_required,
                    "wake-driven progression entered a fatal provider state");
            }
            throw std::runtime_error("settled owner continuation kept posting work");
        };
        drain();
        require(f.acknowledged == 1 && f.handle && !f.effects,
            "startup discovery stalled without an unrelated polling tick/wake");
        const auto before = f.advances;
        f.submit_invocation = true; f.driver->request_advance(); drain();
        require(f.effects == 1 && f.acknowledged == 2 && f.deliveries == 2,
            "advance-submitted native work did not deliver/ACK using owner continuations alone");
        require(f.advances == before + 1 && f.posted_wakes.load() == consumed,
            "service continuation caused extra engine advances or an idle wake spin");
        return;
    }
    if (name == "fatal-delivery") {
        f.discovered(); const auto collectors = f.collectors;
        f.fail_delivery = true; f.submit_invocation = true; f.driver->request_advance();
        for (unsigned n = 0; n < 64 && f.driver->state() != NativeEngineState::process_exit_required; ++n)
            f.driver->tick(f.now += 1ms);
        require(f.callback_failure.empty(), f.callback_failure.c_str());
        require(f.driver->state() == NativeEngineState::process_exit_required && f.effects == 1 &&
            f.deliveries == 2 && f.collectors == collectors && !f.disposals,
            "fatal delivery continued collection/disposal or obscured its actual native effect");
        const auto calls = f.provider_calls; f.driver->request_close(); f.driver->tick(f.now += 1ms);
        require(f.provider_calls == calls && !f.disposals,
            "fatal delivery permitted provider disposal during a later close");
        return;
    }
    if (name == "services" || name == "replacement-close" || name == "audit-reentry") {
        f.discovered(); f.navigate_on_delivery = name != "services"; f.reenter_audit = name == "audit-reentry";
        f.submit_invocation = true; f.driver->request_advance();
        f.until([&] { return f.effects == 1 && (name == "services" ? f.acknowledged == 2 : f.disposals == 1); },
            "native effect/completion/ACK or retired disposal did not finish");
        require(f.completions.size() == 2 && f.effects == 1, "native service effect was lost or replayed");
        require(std::count(f.ack_statuses.begin(), f.ack_statuses.end(), FOUNDATION_APPENDED_SERVICE_UNAVAILABLE) >= 1 &&
            std::count(f.ack_statuses.begin(), f.ack_statuses.end(), FOUNDATION_APPENDED_SERVICE_OK) >= 1,
            "collector bypassed actual staged ACK and its later receipt");
        if (name == "services") {
            for (unsigned n = 0; n < 4; ++n) f.driver->tick(f.now += 1ms);
            require(f.effects == 1 && f.deliveries == 2 && f.acknowledged == 2,
                "settled service work was automatically replayed");
        } else {
            require(f.owner->identity().document_sequence == 2 && f.audits.size() == 1 &&
                f.audits.front() == f.completions.back(), "retirement did not preserve the original old-page outcome");
            if (f.reenter_audit) require(f.recursive_tick_rejections == 1 && f.observer_calls == 1,
                "retirement observer did not recover after refusing its recursive tick");
            const auto old_generation = f.disposed_generations.front();
            require(old_generation != f.document.service_generation, "retired disposal substituted the current page");
            const auto before = f.provider_calls; f.driver->request_close();
            require(f.provider_calls == before, "request_close entered the engine synchronously");
            f.until([&] { return f.driver->state() == NativeEngineState::detached; }, "native close did not settle retirement");
            require(f.owner->closed() && f.disposals == 2 && f.dispose_resource_retirements == 1,
                "close leaked a real owner document or replayed disposal/resource retirement");
            const auto after = f.provider_calls; f.host.wake(f.host.context); f.driver->tick(f.now += 1ms);
            require(f.provider_calls == after, "detached late wake reentered the permanent provider");
        }
        f.healthy(); return;
    }
    if (name == "held-resource-close") {
        f.ready(); f.use_resources = f.keep_resource_lease = true; f.driver->request_advance();
        f.until([&] { return !f.use_resources; }, "provider did not retain the actual resource lease");
        require(f.held_resource.lease && f.held_resource.body &&
            std::string_view(reinterpret_cast<const char*>(f.held_resource.body), std::size_t(f.held_resource.body_length)) == html,
            "provider-held span was not retained before close");
        f.driver->request_close();
        for (unsigned n = 0; n < 64 && f.driver->state() != NativeEngineState::process_exit_required; ++n)
            f.driver->tick(f.now += 1ms);
        require(f.callback_failure.empty(), f.callback_failure.c_str());
        require(f.driver->state() == NativeEngineState::process_exit_required && f.disposals == 1 &&
            f.dispose_resource_retirements == 1 && !f.owner->closed(),
            "unreleased provider spans left close pending indefinitely or were silently reclaimed");
        const auto calls = f.provider_calls; f.driver->tick(f.now += 1ms);
        require(f.provider_calls == calls, "provider-held-span failure resumed native execution");
        return;
    }
    if (name == "prospective-epoch") {
        f.ready(); f.exercise_epochs = true; f.driver->request_advance();
        f.until([&] { return !f.exercise_epochs; }, "prospective resource epoch regression did not execute");
        require(f.driver->state() == NativeEngineState::ready && f.owner->identity().document_sequence == 2,
            "prospective resource epoch checks disturbed actual service authority");
        f.driver->request_close();
        f.until([&] { return f.driver->state() == NativeEngineState::detached; }, "prospective resource epochs prevented ordinary close");
        require(f.owner->closed() && f.disposals == 2 && f.dispose_resource_retirements == 1,
            "intervening document/prospective resource cleanup did not finish");
        return;
    }
    if (name == "resources") {
        f.ready(); f.use_resources = true; f.driver->request_advance();
        f.until([&] { return !f.use_resources; }, "native resource callbacks were not driven");
        f.driver->request_close();
        f.until([&] { return f.driver->state() == NativeEngineState::detached; }, "released resource leases prevented close");
        require(f.owner->closed() && f.dispose_resource_retirements == 1,
            "GET/HEAD local leases or late provider epoch retirement did not finish");
        return;
    }
    if (name == "frames-scheduling") {
        f.ready(); f.emit_frames = f.arm_timer = true; f.driver->request_advance();
        f.until([&] { return !f.emit_frames && !f.arm_timer; }, "native frame/timer callbacks were not driven");
        require(f.owner->frame() && f.owner->frame()->frame_revision == 2, "copied native frame was not retained");
        const auto deadline = f.driver->deadline();
        require(deadline && *deadline > f.now, "native timer did not retain a future steady-clock deadline");
        const auto before = f.advances; f.driver->tick(*deadline - 1ms);
        require(f.advances == before, "native deadline fired before its scheduled time");
        f.now = *deadline; f.driver->tick(f.now);
        require(f.advances > before, "native deadline did not schedule an outer advance");
        const auto calls = f.provider_calls;
        const auto wakes_before = f.posted_wakes.load();
        std::thread worker([&] { f.host.wake(f.host.context); }); worker.join();
        require(f.posted_wakes.load() > wakes_before && f.provider_calls == calls, "worker wake entered owner/provider work");
        f.disarm_timer = true; f.driver->tick(f.now += 1ms);
        require(!f.disarm_timer && !f.driver->deadline(), "owner wake/disarm did not remain deferred and serialized");
        f.healthy(); return;
    }
    if (name == "fatal-provider" || name == "fatal-frame") {
        f.ready();
        if (name == "fatal-provider") f.fail_advance = true;
        else { f.emit_frames = true; f.invalid_frame = true; }
        f.driver->request_advance(); f.driver->tick(f.now += 1ms);
        require(f.driver->state() == NativeEngineState::process_exit_required,
            "uncertain provider/invalid frame did not require process exit");
        require(f.callback_failure.empty(), f.callback_failure.c_str());
        const auto calls = f.provider_calls;
        f.driver->request_advance(); f.host.wake(f.host.context); f.driver->request_close();
        f.driver->tick(f.now += 1ms);
        require(f.provider_calls == calls, "terminal failure permitted a later provider call or cleanup replay");
        if (name == "fatal-frame") require(!f.owner->frame(), "rejected alpha frame partially committed pixels");
        return;
    }
    if (name == "ready-timeout") {
        f.waiting = true; NativeEngineOptions options; options.ready_timeout = 5ms;
        f.bind(options); f.driver->start_once(f.now);
        f.healthy();
        require(f.driver->state() == NativeEngineState::waiting_document &&
            f.owner->identity().application_instance == instance && !f.owner->identity().service_generation,
            "timeout fixture failed startup instead of waiting for actual document readiness");
        f.driver->tick(f.now += 4ms); f.healthy();
        require(f.driver->state() == NativeEngineState::waiting_document,
            "native readiness timeout fired before its deadline");
        f.driver->tick(f.now += 2ms);
        require(f.driver->state() == NativeEngineState::process_exit_required && f.starts == 1,
            "missing ready document did not end the one-shot startup at its deadline");
        const auto calls = f.provider_calls; f.driver->tick(f.now += 1ms);
        require(f.provider_calls == calls, "timed-out startup retried provider work");
        require(f.callback_failure.empty(), f.callback_failure.c_str()); return;
    }
    throw std::runtime_error("unknown native driver scenario");
}
} // namespace

int main(int argc, char** argv) {
    try {
        require(argc == 2, "Usage: appended-native-engine-driver-test SCENARIO (fresh process per scenario)");
        run(argv[1]); std::cout << "native driver mock scenario passed: " << argv[1] << '\n'; return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
