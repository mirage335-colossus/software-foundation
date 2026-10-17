#include "../gui/shared/appended_engine_owner.hpp"
#include "../gui/shared/appended_engine_abi.h"
#include "../gui/shared/appended_engine_input_codec.hpp"
#include "../gui/shared/engine_document_mailbox.hpp"
#include "../gui/shared/native_editor_codec.hpp"

#include <algorithm>
#include <array>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <memory>
#include <new>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <type_traits>
#include <utility>

// Synthetic owner/codec tests only. No retained provider, DOM, backend, SDK or
// actual engine is loaded. Each process-terminal scenario runs in a fresh process.
namespace allocation_probe {
thread_local bool armed = false;
thread_local std::size_t calls = 0;
thread_local std::size_t fail_after = std::numeric_limits<std::size_t>::max();
void before_allocate() {
    if (!armed) return;
    if (calls++ == fail_after) throw std::bad_alloc();
}
}
void* operator new(std::size_t size) {
    allocation_probe::before_allocate();
    if (auto* result = std::malloc(size ? size : 1)) return result;
    throw std::bad_alloc();
}
void* operator new[](std::size_t size) { return ::operator new(size); }
void operator delete(void* pointer) noexcept { std::free(pointer); }
void operator delete[](void* pointer) noexcept { std::free(pointer); }
void operator delete(void* pointer, std::size_t) noexcept { std::free(pointer); }
void operator delete[](void* pointer, std::size_t) noexcept { std::free(pointer); }
void* operator new(std::size_t size, const std::nothrow_t&) noexcept { try { return ::operator new(size); } catch (...) { return nullptr; } }
void* operator new[](std::size_t size, const std::nothrow_t&) noexcept { try { return ::operator new[](size); } catch (...) { return nullptr; } }
void operator delete(void* pointer, const std::nothrow_t&) noexcept { std::free(pointer); }
void operator delete[](void* pointer, const std::nothrow_t&) noexcept { std::free(pointer); }
void* operator new(std::size_t size, std::align_val_t alignment) {
    allocation_probe::before_allocate();
    const auto align = static_cast<std::size_t>(alignment), extra = align - 1 + sizeof(void*);
    if (size > std::numeric_limits<std::size_t>::max() - extra) throw std::bad_alloc();
    void* raw = std::malloc((size ? size : 1) + extra);
    if (!raw) throw std::bad_alloc();
    const auto start = reinterpret_cast<std::uintptr_t>(raw) + sizeof(void*);
    const auto address = (start + align - 1) & ~(static_cast<std::uintptr_t>(align) - 1);
    auto* result = reinterpret_cast<void*>(address);
    reinterpret_cast<void**>(result)[-1] = raw;
    return result;
}
void* operator new[](std::size_t size, std::align_val_t alignment) { return ::operator new(size, alignment); }
void operator delete(void* pointer, std::align_val_t) noexcept { if (pointer) std::free(reinterpret_cast<void**>(pointer)[-1]); }
void operator delete[](void* pointer, std::align_val_t alignment) noexcept { ::operator delete(pointer, alignment); }
void operator delete(void* pointer, std::size_t, std::align_val_t alignment) noexcept { ::operator delete(pointer, alignment); }
void operator delete[](void* pointer, std::size_t, std::align_val_t alignment) noexcept { ::operator delete(pointer, alignment); }
void* operator new(std::size_t size, std::align_val_t alignment, const std::nothrow_t&) noexcept { try { return ::operator new(size, alignment); } catch (...) { return nullptr; } }
void* operator new[](std::size_t size, std::align_val_t alignment, const std::nothrow_t&) noexcept { try { return ::operator new[](size, alignment); } catch (...) { return nullptr; } }
void operator delete(void* pointer, std::align_val_t alignment, const std::nothrow_t&) noexcept { ::operator delete(pointer, alignment); }
void operator delete[](void* pointer, std::align_val_t alignment, const std::nothrow_t&) noexcept { ::operator delete(pointer, alignment); }

namespace {
using namespace foundation::appended;
namespace document = engine_document;
namespace editor = engine_editor;
namespace input = engine_input;
namespace native = foundation::ui::native_editor;
namespace codec = native::codec;
using Span = std::span<const std::uint8_t>;
std::size_t assertions = 0;
void check(bool value, const char* reason) {
    ++assertions;
    if (!value) throw std::runtime_error(reason);
}
void put(std::span<std::uint8_t> bytes, std::size_t offset, std::uint64_t value, unsigned count) {
    check(offset <= bytes.size() && count <= bytes.size() - offset, "synthetic write escaped bytes");
    for (unsigned index = 0; index < count; ++index) bytes[offset + index] = static_cast<std::uint8_t>(value >> (index * 8));
}
std::uint64_t get(Span bytes, std::size_t offset, unsigned count) {
    check(offset <= bytes.size() && count <= bytes.size() - offset, "synthetic read escaped bytes");
    std::uint64_t result = 0;
    for (unsigned index = 0; index < count; ++index) result |= std::uint64_t(bytes[offset + index]) << (index * 8);
    return result;
}
EngineEditorTarget editor_target(EngineIdentity id) { return {id.worker_epoch, id.application_instance, id.document_sequence, id.service_generation}; }
EngineIdentity identity(EngineEditorTarget id) { return {id.worker_epoch, id.application_instance, id.document_sequence, id.service_generation}; }
EngineDocumentTarget document_target(EngineIdentity id) { return {id.worker_epoch, id.application_instance, id.document_sequence, id.service_generation}; }
Bytes record(std::uint32_t operation, EngineIdentity id, Span body = {}, std::uint64_t transfer = 0) {
    Bytes result(FOUNDATION_ENGINE_HEADER_BYTES + body.size());
    std::copy_n("FKB1", 4, result.begin());
    put(result, 4, FOUNDATION_ENGINE_RECORD_VERSION, 2); put(result, 6, operation, 2); put(result, 8, result.size(), 4);
    put(result, 16, id.worker_epoch, 8); put(result, 24, id.application_instance, 8);
    put(result, 32, id.document_sequence, 8); put(result, 40, id.service_generation, 8);
    put(result, 48, transfer, 8); put(result, 64, body.size(), 4);
    std::copy(body.begin(), body.end(), result.begin() + FOUNDATION_ENGINE_HEADER_BYTES);
    return result;
}
struct Reply {
    EngineIdentity target;
    std::uint64_t transfer = 0;
    std::uint32_t control = 0, service = 0;
    Bytes bytes;
    Span body() const { return Span(bytes).subspan(FOUNDATION_ENGINE_RECEIPT_BYTES); }
};
Reply call(EngineOwner& owner, std::uint32_t operation, EngineIdentity id, Span body = {},
           std::uint64_t transfer = 0, std::size_t capacity = FOUNDATION_ENGINE_RECEIPT_BYTES + FOUNDATION_ENGINE_EDITOR_MAX_RESULT_BODY_BYTES) {
    const auto request = record(operation, id, body, transfer);
    Bytes output(capacity, 0xa5);
    const auto written = owner.dispatch(operation, request, output);
    check(written >= FOUNDATION_ENGINE_RECEIPT_BYTES && static_cast<std::size_t>(written) <= output.size(), "owner omitted a complete copied receipt");
    output.resize(static_cast<std::size_t>(written));
    check(get(output, 6, 2) == (operation | FOUNDATION_ENGINE_REPLY_KIND) && get(output, 8, 4) == output.size() &&
        get(output, 64, 4) == output.size() - FOUNDATION_ENGINE_HEADER_BYTES, "copied receipt framing changed");
    return {{get(output, 16, 8), get(output, 24, 8), get(output, 32, 8), get(output, 40, 8)}, get(output, 48, 8),
        static_cast<std::uint32_t>(get(output, 72, 4)), static_cast<std::uint32_t>(get(output, 76, 4)), std::move(output)};
}
void ok(const Reply& result, const char* reason = "owner refused expected copied operation") { check(result.control == FOUNDATION_ENGINE_OK && result.service == 0, reason); }
void short_reply(EngineOwner& owner, std::uint32_t operation, EngineIdentity id, Span body,
                 std::uint64_t transfer, std::size_t capacity) {
    const auto request = record(operation, id, body, transfer);
    Bytes output(capacity, 0xa5);
    check(owner.dispatch(operation, request, output) == FOUNDATION_ENGINE_REPLY_TOO_SMALL &&
        std::all_of(output.begin(), output.end(), [](auto byte) { return byte == 0xa5; }), "short receipt mutated output or admitted work");
}
Bytes claim_bytes(std::uint32_t kind, std::uint64_t sequence) {
    Bytes result(FOUNDATION_ENGINE_EDITOR_BEGIN_BYTES);
    put(result, 0, kind, 4); put(result, 8, sequence, 8);
    return result;
}
Bytes result_bytes(std::uint32_t kind, std::uint64_t sequence, Span raw,
                   std::int32_t status = 0, std::uint32_t disposition = 0,
                   bool handled = false, std::uint64_t revision = 0) {
    Bytes result(FOUNDATION_ENGINE_EDITOR_RESULT_PREFIX_BYTES + raw.size());
    put(result, 0, kind, 4); put(result, 8, sequence, 8);
    put(result, 16, static_cast<std::uint32_t>(status), 4); put(result, 20, disposition, 4);
    put(result, 24, raw.size(), 4); put(result, 28, handled ? 1 : 0, 4); put(result, 32, revision, 8);
    std::copy(raw.begin(), raw.end(), result.begin() + FOUNDATION_ENGINE_EDITOR_RESULT_PREFIX_BYTES);
    return result;
}
Bytes result_bytes(const EngineEditorDispatch& dispatch, Span raw,
                   std::int32_t status = 0, std::uint32_t disposition = 0,
                   bool handled = false, std::uint64_t revision = 0) {
    return result_bytes(static_cast<std::uint32_t>(dispatch.work.kind), dispatch.work.request_sequence,
        raw, status, disposition, handled, revision);
}
Bytes document_bytes(EngineDocumentTarget target, std::uint64_t sequence, unsigned kind,
                     std::uint64_t nested = 0, std::size_t size = 48) {
    Bytes result(size);
    std::copy_n("NDV2", 4, result.begin()); result[4] = 2; result[6] = static_cast<std::uint8_t>(kind);
    put(result, 8, target.application_instance, 8); put(result, 16, target.service_generation, 8);
    put(result, 24, target.document_sequence, 8); put(result, 32, sequence, 8); put(result, 40, nested, 8);
    return result;
}
EngineDocumentWork form_work(EngineIdentity target, std::uint64_t sequence) {
    EngineDocumentWork result;
    result.target = document_target(target); result.request_sequence = sequence; result.kind = EngineDocumentWorkKind::form_action;
    result.operation = BIB_ENGINE_COMMAND_FORM_ACTION_V2; result.required_reply_capacity = BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY;
    result.schema_sha256 = document::kSchema; result.payload = document_bytes(result.target, sequence, 2, 0, 81);
    put(result.payload, 49, target.application_instance, 8); put(result.payload, 57, target.service_generation, 8);
    put(result.payload, 65, 1, 8); put(result.payload, 73, 1, 8);
    return result;
}
Package package() {
    Package result;
    result.application = {"org.example.editor-owner", "Synthetic editor owner", "1.0.0"};
    result.web.present = true; result.web.entry = "web/index.html";
    result.capabilities = {"foundation.startup.v1"}; result.package_sha256 = std::string(64, '1');
    const std::string startup = "{\"kind\":\"foundation-appended-startup\",\"primary\":\"web\",\"schema_version\":1}";
    result.files = {{"web/.foundation/startup-v1.json", "web", "application/json", std::string(64, '2'), Bytes(startup.begin(), startup.end())},
        {"web/index.html", "web", "text/html", std::string(64, '3'), {}}};
    return result;
}
document::EngineDocumentProfileFacts document_facts(bool physical = false) {
    document::EngineDocumentProfileFacts facts;
    facts.enabled = true; facts.kind = physical ? document::ProfileKind::physical : document::ProfileKind::pixel;
    facts.name = physical ? document::kPhysicalProfileName : document::kPixelProfileName;
    facts.provider_abi_major = 1; facts.provider_abi_minor = 1; facts.host_abi_major = 1;
    facts.target_system = BIB_ENGINE_TARGET_LINUX; facts.target_processor = BIB_ENGINE_CPU_X86_64; facts.pointer_bits = 64;
    facts.lifetime = BIB_ENGINE_LIFETIME_PROCESS; facts.maximum_starts = 1; facts.viewport_width = 800; facts.viewport_height = 600;
    facts.provider_capabilities = physical ? 2003 : 1795; facts.base_header_sha256 = document::kBaseHeaderSha256;
    facts.extension_header_sha256 = document::kExtensionHeaderSha256; facts.contract_sha256 = document::kContractSha256;
    facts.catalog_sha256 = document::kCatalogSha256; facts.queries = document::kQueries; facts.commands = document::kCommands;
    facts.query_count = 1; facts.command_count = 2;
    facts.build_sha256[0] = 1; facts.source_recipe_sha256[0] = 2; // Synthetic; no retained engine/runtime is represented.
    if (physical) facts.physical_catalog_sha256 = document::kPhysicalCatalogSha256;
    return facts;
}
editor::EngineEditorProfileFacts editor_facts() {
    editor::EngineEditorProfileFacts facts;
    facts.enabled = true; facts.kind = editor::ProfileKind::editor; facts.name = editor::kProfileName;
    facts.provider_abi_major = BIB_ENGINE_DOCUMENT_V2_ABI_MAJOR; facts.provider_abi_minor = BIB_ENGINE_DOCUMENT_V2_ABI_MINOR;
    facts.host_abi_major = BIB_ENGINE_DOCUMENT_V2_HOST_ABI_MAJOR; facts.host_abi_minor = BIB_ENGINE_DOCUMENT_V2_HOST_ABI_MINOR;
    facts.target_system = BIB_ENGINE_TARGET_LINUX; facts.target_processor = BIB_ENGINE_CPU_X86_64; facts.pointer_bits = 64;
    facts.lifetime = BIB_ENGINE_LIFETIME_PROCESS; facts.maximum_starts = 1; facts.viewport_width = 800; facts.viewport_height = 600;
    facts.provider_capabilities = editor::kProviderCapabilities; facts.surface_capabilities = editor::kSurfaceCapabilities;
    facts.surface_protocol_version = BIB_ENGINE_EDITOR_SURFACE_PROTOCOL_VERSION; facts.editor_protocol_version = BIB_ENGINE_EDITOR_PROTOCOL_VERSION;
    facts.base_header_sha256 = document::kBaseHeaderSha256; facts.document_header_sha256 = document::kExtensionHeaderSha256;
    facts.document_contract_sha256 = document::kContractSha256; facts.document_catalog_sha256 = document::kCatalogSha256;
    facts.physical_catalog_sha256 = document::kPhysicalCatalogSha256; facts.editor_header_sha256 = editor::kHeaderSha256;
    facts.contract_sha256 = editor::kContractSha256; facts.catalog_sha256 = editor::kCatalogSha256; facts.schema_sha256 = editor::kSchema;
    facts.build_sha256[0] = 3; facts.source_recipe_sha256[0] = 4; // Explicit synthetic source/build pins only.
    facts.queries = editor::kQueries; facts.commands = editor::kCommands; facts.query_count = 2; facts.command_count = 7;
    return facts;
}
enum class Profile { legacy, pixel, physical, editor };
struct ModuleCounters { unsigned factories = 0, constructed = 0, close_calls = 0, destroyed = 0; };
class CountedModule final : public EngineModuleBinding {
    std::shared_ptr<ModuleCounters> counters_;
    std::uint64_t generation_;
public:
    CountedModule(std::shared_ptr<ModuleCounters> counters, std::uint64_t generation)
        : counters_(std::move(counters)), generation_(generation) { ++counters_->constructed; }
    ~CountedModule() override { ++counters_->destroyed; }
    WebModuleServices services() override {
        return {generation_, [](const DiscoveryQuery&) { return ProviderDiscovery{}; },
            [](const ProviderRequest&) { return ProviderOutcome{}; },
            [](std::uint64_t) { return ServiceStatus::ok; },
            [next = std::uint64_t{1}]() mutable -> std::optional<std::uint64_t> { return next++; }};
    }
    void close() noexcept override { ++counters_->close_calls; }
};
struct Fixture {
    static constexpr std::string_view service_name = "org.example.editor-owner.native";
    EngineIdentity id{UINT64_C(0x8000000000000011), UINT64_C(0x8000000000000023), 0, 0};
    std::unique_ptr<EngineOwner> owner;
    unsigned native_effects = 0;
    bool safe_publication = false;
    explicit Fixture(Profile selected = Profile::editor, bool configure = true, std::shared_ptr<ModuleCounters> counters = {}, bool native_services = false) {
        EngineOwnerConfiguration configuration;
        configuration.worker_epoch = id.worker_epoch; configuration.application_instance = id.application_instance;
        if (selected == Profile::pixel || selected == Profile::physical) configuration.document_profile = document_facts(selected == Profile::physical);
        if (selected == Profile::editor) configuration.editor_profile = editor_facts();
        if (native_services) configuration.native_services.push_back({{std::string(service_name), 1, 0, SchemaId{7}, 4},
            [this](std::uint32_t operation, Span bytes, std::span<std::uint8_t> output) -> ServiceReply {
                const auto effect = owner->native_effect();
                check(operation == 1 && bytes.size() == 4 && output.size() >= 4 && effect && effect->entered && safe_publication,
                    "native fixture handler entered before safe publication and exact retirement");
                ++native_effects; std::copy(bytes.begin(), bytes.end(), output.begin()); return {ServiceStatus::ok, 4};
            }});
        auto payload = package();
        if (counters) {
            payload.binary = {true, "binary/application.wasm", "foundation-guest-v1"};
            payload.files.insert(payload.files.begin(), {"binary/application.wasm", "binary", "application/wasm", std::string(64, '4'), {0}});
            configuration.module_factory = [counters](auto, auto, std::uint64_t generation) -> std::unique_ptr<EngineModuleBinding> {
                ++counters->factories; return std::make_unique<CountedModule>(counters, generation);
            };
        }
        owner = std::make_unique<EngineOwner>(std::move(payload), std::move(configuration));
        if (!configure) return;
        ok(call(*owner, FOUNDATION_ENGINE_CONFIGURE, id));
        id.document_sequence = UINT64_C(0x8000000000000001);
        const auto begun = call(*owner, FOUNDATION_ENGINE_BEGIN_DOCUMENT, id); ok(begun); id = begun.target;
    }
    EngineEditorDispatch peek() {
        const auto response = call(*owner, FOUNDATION_ENGINE_PEEK_EDITOR_WORK, id); ok(response);
        check(response.transfer && response.body().size() >= FOUNDATION_ENGINE_EDITOR_WORK_PREFIX_BYTES, "editor work envelope is incomplete");
        EngineEditorDispatch dispatch;
        dispatch.transfer = response.transfer; dispatch.work.target = editor_target(response.target);
        dispatch.work.kind = static_cast<EngineEditorWorkKind>(get(response.body(), 0, 4));
        dispatch.work.operation = static_cast<std::uint32_t>(get(response.body(), 4, 4));
        dispatch.work.request_sequence = get(response.body(), 8, 8);
        std::copy_n(response.body().begin() + 16, 32, dispatch.work.schema_sha256.begin());
        dispatch.work.required_reply_capacity = static_cast<std::uint32_t>(get(response.body(), 48, 4));
        check(get(response.body(), 52, 4) == response.body().size() - FOUNDATION_ENGINE_EDITOR_WORK_PREFIX_BYTES, "editor work envelope length differs");
        dispatch.work.payload.assign(response.body().begin() + FOUNDATION_ENGINE_EDITOR_WORK_PREFIX_BYTES, response.body().end());
        return dispatch;
    }
    EngineEditorAdmission stage(EngineEditorWork work) {
        const auto result = owner->stage_editor_work(std::move(work));
        check(result.code == EngineEditorAdmissionCode::admitted && result.ticket, "valid owned editor work was not admitted");
        return result;
    }
    void claim(const EngineEditorDispatch& dispatch) {
        ok(call(*owner, FOUNDATION_ENGINE_BEGIN_EDITOR_WORK, identity(dispatch.work.target),
            claim_bytes(static_cast<std::uint32_t>(dispatch.work.kind), dispatch.work.request_sequence), dispatch.transfer));
    }
    void turn(const EngineEditorDispatch& dispatch) {
        ok(call(*owner, FOUNDATION_ENGINE_TURN_ENTER, identity(dispatch.work.target), {}, dispatch.transfer));
        ok(call(*owner, FOUNDATION_ENGINE_TURN_LEAVE, identity(dispatch.work.target), {}, dispatch.transfer));
    }
    void settle(const EngineEditorDispatch& dispatch, Span raw, std::int32_t status = 0,
                std::uint32_t disposition = 0, bool handled = false, std::uint64_t revision = 0) {
        ok(call(*owner, FOUNDATION_ENGINE_EDITOR_WORK_RESULT, identity(dispatch.work.target),
            result_bytes(dispatch, raw, status, disposition, handled, revision), dispatch.transfer));
    }
    EngineInputTicket bind_context(std::uint64_t context = 7) {
        Bytes focus;
        check(input::encode_focus({1, 0, 0, 0, context, 0}, focus) == input::Status::ok, "synthetic physical context could not encode");
        const auto ticket = owner->stage_command(id, context, 3, input::kFocusSchema, focus, true);
        check(bool(ticket), "synthetic physical context was not admitted");
        const auto pending = call(*owner, FOUNDATION_ENGINE_PEEK_INPUT, id); ok(pending);
        ok(call(*owner, FOUNDATION_ENGINE_TURN_ENTER, pending.target, {}, pending.transfer));
        ok(call(*owner, FOUNDATION_ENGINE_TURN_LEAVE, pending.target, {}, pending.transfer));
        Bytes completed;
        check(input::encode_command_result({0, 1, *ticket, 0, 0}, completed) == input::Status::ok, "synthetic physical result could not encode");
        ok(call(*owner, FOUNDATION_ENGINE_COMMAND_RESULT, pending.target, completed, pending.transfer));
        const auto outcome = owner->command_outcome(*ticket);
        check(outcome && outcome->status == EngineInputCommandStatus::consumed, "physical input_context was not actually committed in Owner");
        return *ticket;
    }
};

codec::WireTarget wire_target(EngineEditorTarget target, std::uint64_t sequence) {
    return {target.worker_epoch, target.application_instance, target.document_sequence, target.service_generation, sequence};
}
codec::WireTarget wire_target(const EngineEditorWork& work) { return wire_target(work.target, work.request_sequence); }
native::Identity surface_identity(EngineIdentity target, std::uint64_t context = 7) {
    return {{"synthetic-editor-owner", 1}, 1, target.service_generation, 1, context};
}
native::NativeProjection projection(native::Identity id, std::uint64_t mapping = 11,
                                    std::uint64_t token = UINT64_C(0x8000000000000077)) {
    native::NativeProjection result;
    result.identity = std::move(id); result.editor_revision = 17; result.surrounding = "abc"; result.selection = {1, 1};
    result.mapping_id = mapping; result.frame_id = 29; result.readback_attested = true; result.caret = {0, 0, 1, 1};
    result.editable = true; result.input_purpose = "text";
    // Synthetic provider reply data. Only a checked Owner completion may make
    // this material eligible for a later request in these tests.
    result.retire = native::NativeRetireMaterial{token, mapping, result.identity.context, result.composition};
    return result;
}
EngineEditorWork query_work(EngineIdentity target, std::uint64_t sequence, native::Identity id, std::uint64_t mapping = 0) {
    EngineEditorWork result;
    result.target = editor_target(target); result.request_sequence = sequence; result.kind = EngineEditorWorkKind::projection_query;
    result.operation = BIB_ENGINE_QUERY_EDITOR_PROJECTION_V1; result.required_reply_capacity = editor::kReplyCapacity; result.schema_sha256 = editor::kSchema;
    check(codec::encode_projection_query({wire_target(result), std::move(id), mapping}, result.payload), "typed query fixture could not encode");
    return result;
}
EngineEditorWork next_query(Fixture& fixture, std::uint64_t context = 7) {
    const auto sequence = fixture.owner->reserve_editor_sequence();
    check(bool(sequence), "editor query sequence could not reserve");
    return query_work(fixture.id, *sequence, surface_identity(fixture.id, context));
}
Bytes query_reply(const EngineEditorWork& work, native::NativeProjection value, std::uint64_t revision = 31) {
    codec::ProjectionReply result;
    result.state = codec::ProjectionReply::State::available; result.observation_revision = revision;
    result.target = wire_target(work); result.identity = value.identity; result.readback_attested = true; result.projection = std::move(value);
    Bytes raw; check(codec::encode_projection_reply(result, raw), "typed projection reply could not encode"); return raw;
}
Bytes unavailable_reply(const EngineEditorWork& work, native::Identity id, std::uint64_t revision = 31) {
    codec::ProjectionReply result;
    result.state = codec::ProjectionReply::State::unavailable; result.observation_revision = revision;
    result.target = wire_target(work); result.identity = std::move(id); result.readback_attested = true;
    Bytes raw; check(codec::encode_projection_reply(result, raw), "typed checked-null reply could not encode"); return raw;
}
native::NativeProjection complete_query(Fixture& fixture) {
    const auto work = next_query(fixture); const auto admission = fixture.stage(work); const auto dispatch = fixture.peek();
    fixture.claim(dispatch); fixture.turn(dispatch);
    const auto raw = query_reply(work, projection(surface_identity(fixture.id)));
    fixture.settle(dispatch, raw, 0, 0, false, 31);
    const auto completion = fixture.owner->editor_outcome(admission.ticket);
    codec::ProjectionReply checked;
    check(completion && completion->outcome == EngineEditorOutcome::consumed && codec::decode_projection_reply(completion->bytes, checked) &&
        checked.projection && checked.projection->retire, "query did not retain a checked provider retirement material");
    check(fixture.owner->consume_editor_outcome(admission.ticket), "checked query completion could not collect locally");
    return *checked.projection;
}
EngineEditorWork observation_work(EngineIdentity target, std::uint64_t sequence, const native::NativeProjection& checked) {
    EngineEditorWork result;
    result.target = editor_target(target); result.request_sequence = sequence; result.kind = EngineEditorWorkKind::observation;
    result.operation = BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1; result.required_reply_capacity = editor::kReplyCapacity; result.schema_sha256 = editor::kSchema;
    codec::NativeRequestEnvelope envelope;
    envelope.target = wire_target(result); envelope.request.resolved = checked;
    auto& packet = envelope.request.packet;
    packet.session = 1; packet.basis = {37, checked.identity, checked.editor_revision, checked.surrounding, checked.selection, checked.backward, checked.composition};
    packet.observation.id = 1; packet.observation.kind = native::Kind::selection; packet.observation.authority = native::Authority::range;
    packet.observation.before = {checked.surrounding, 1, 1, native::Direction::none, checked.selection, checked.surrounding.size()};
    packet.observation.data = native::SelectionData{{2, 2}, false};
    check(codec::encode_native_request(envelope, result.payload), "typed observation fixture could not encode");
    return result;
}
EngineEditorWork revoke_work(EngineIdentity target, std::uint64_t sequence, const native::NativeProjection& checked) {
    check(bool(checked.retire), "revoke fixture lacks checked prior provider material");
    EngineEditorWork result;
    result.target = editor_target(target); result.request_sequence = sequence; result.kind = EngineEditorWorkKind::revoke;
    result.operation = BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1; result.required_reply_capacity = editor::kReplyCapacity; result.schema_sha256 = editor::kSchema;
    codec::RevocationEnvelope envelope{wire_target(result), {*checked.retire, checked.identity, std::nullopt}};
    check(codec::encode_revocation(envelope, result.payload), "typed revoke fixture could not encode");
    return result;
}
Bytes native_reply(const EngineEditorWork& work, native::NativeResult result) {
    Bytes raw;
    check(codec::encode_native_result({wire_target(work), std::move(result)}, raw), "typed native result fixture could not encode");
    return raw;
}
native::NativeResult observed_result(native::NativeProjection checked, std::uint64_t revision = 32) {
    native::NativeResult result;
    result.outcome = native::Outcome::applied; result.continuity = native::Continuity::same;
    result.availability = native::NativeAvailability::available; result.observation_revision = revision;
    result.readback_identity = checked.identity; result.readback_attested = true; result.retire = checked.retire;
    result.projection = std::move(checked); return result;
}
native::NativeResult revoked_result(const native::NativeProjection& checked, std::uint64_t revision = 1000) {
    native::NativeResult result;
    result.outcome = native::Outcome::applied; result.continuity = native::Continuity::same;
    result.availability = native::NativeAvailability::unavailable; result.observation_revision = revision;
    result.readback_identity = checked.identity; result.readback_attested = true; result.retired = checked.retire;
    return result;
}
void retire_projection(Fixture& fixture, const native::NativeProjection& checked) {
    const auto sequence = fixture.owner->reserve_editor_sequence(); check(bool(sequence), "retirement sequence could not reserve");
    const auto work = revoke_work(fixture.id, *sequence, checked); const auto admission = fixture.stage(work);
    const auto dispatch = fixture.peek(); fixture.claim(dispatch); fixture.turn(dispatch);
    fixture.settle(dispatch, native_reply(work, revoked_result(checked)), 0, 1);
    const auto completion = fixture.owner->editor_outcome(admission.ticket);
    check(completion && completion->outcome == EngineEditorOutcome::consumed && fixture.owner->consume_editor_outcome(admission.ticket),
        "exact checked native9 retirement could not collect locally");
}

void disabled_and_frozen_profiles_refuse_editor_mailbox() {
    for (const auto selected : {Profile::legacy, Profile::pixel, Profile::physical}) {
        Fixture fixture(selected);
        check(!fixture.owner->editor_enabled() && !fixture.owner->reserve_editor_sequence() &&
            !fixture.owner->cancel_editor_sequence(1), "frozen profile acquired editor sequence authority");
        check(fixture.owner->stage_editor_work({}).code != EngineEditorAdmissionCode::admitted &&
            !fixture.owner->editor_outcome(1) && !fixture.owner->consume_editor_outcome(1), "frozen profile acquired editor work authority");
        for (const auto operation : {FOUNDATION_ENGINE_PEEK_EDITOR_WORK, FOUNDATION_ENGINE_EDITOR_WORK_RESULT, FOUNDATION_ENGINE_BEGIN_EDITOR_WORK}) {
            const auto request = record(operation, fixture.id);
            Bytes output(FOUNDATION_ENGINE_RECEIPT_BYTES, 0xa5);
            check(fixture.owner->dispatch(operation, request, output) == FOUNDATION_ENGINE_BAD_OPERATION &&
                std::all_of(output.begin(), output.end(), [](auto byte) { return byte == 0xa5; }), "frozen profile exposed new editor operation");
        }
    }
}
void independent_editor_profile_facts() {
    Fixture fixture;
    check(editor::editor_profile_valid(editor_facts()) && fixture.owner->editor_enabled(), "exact synthetic editor profile was not selected");
    check(fixture.owner->editor_profile() == editor_facts(), "Owner changed immutable compiled editor facts");
    for (unsigned variant = 0; variant != 6; ++variant) {
        EngineOwnerConfiguration configuration;
        configuration.worker_epoch = 17; configuration.application_instance = 23; configuration.editor_profile = editor_facts();
        if (variant == 0) configuration.document_profile = document_facts();
        if (variant == 1) configuration.document_profile = document_facts(true);
        if (variant == 2) configuration.editor_profile.provider_capabilities = 2003;
        if (variant == 3) configuration.editor_profile.provider_abi_minor = 0;
        if (variant == 4) configuration.editor_profile.schema_sha256[0] ^= 1;
        if (variant == 5) configuration.editor_profile.commands[6].operation = 7;
        bool rejected = false;
        try { EngineOwner invalid(package(), std::move(configuration)); } catch (const std::invalid_argument&) { rejected = true; }
        check(rejected, "invalid/crossed editor facts reached configured Owner");
    }
}
void shared_reservation_burns_before_later_physical_and_document_work() {
    Fixture fixture;
    const auto reserved = fixture.owner->reserve_editor_sequence();
    check(reserved && *reserved == 1, "first editor ordinary sequence changed");
    check(!fixture.owner->reserve_editor_sequence() && !fixture.owner->reserve_document_sequence(), "held editor reservation permitted another ordinary reservation");
    Bytes focus;
    check(input::encode_focus({1, 0, 0, 0, 7, 0}, focus) == input::Status::ok, "reservation focus fixture could not encode");
    check(!fixture.owner->stage_command(fixture.id, 7, 3, input::kFocusSchema, focus, true), "physical input overtook the held editor sequence");
    check(fixture.owner->stage_editor_work({}).code != EngineEditorAdmissionCode::admitted &&
        !fixture.owner->cancel_editor_sequence(*reserved + 1) && !fixture.owner->reserve_document_sequence(), "invalid work or wrong cancellation released the editor reservation");
    check(fixture.owner->cancel_editor_sequence(*reserved) && !fixture.owner->cancel_editor_sequence(*reserved), "exact editor cancellation did not burn its sequence once");
    const auto physical = fixture.bind_context();
    check(physical > *reserved, "physical focus reused a cancelled editor sequence");
    const auto ordinary = fixture.owner->reserve_document_sequence();
    check(ordinary && *ordinary > physical && !fixture.owner->reserve_editor_sequence(), "document work did not share editor/physical order");
    check(fixture.owner->cancel_document_sequence(*ordinary), "exact document reservation could not cancel");
    const auto next = fixture.owner->reserve_editor_sequence();
    check(next && *next > *ordinary && fixture.owner->cancel_editor_sequence(*next), "editor sequence reset after document cancellation");
}
void foreign_thread_cannot_acquire_or_cancel_editor_reservation() {
    Fixture fixture;
    const auto reserved = fixture.owner->reserve_editor_sequence();
    check(bool(reserved), "owner could not reserve before foreign-thread check");
    bool refused = false;
    std::thread other([&] {
        try {
            refused = !fixture.owner->reserve_editor_sequence() && !fixture.owner->cancel_editor_sequence(*reserved) &&
                fixture.owner->stage_editor_work({}).code != EngineEditorAdmissionCode::admitted &&
                !fixture.owner->editor_outcome(1) && !fixture.owner->consume_editor_outcome(1);
        } catch (...) { refused = false; }
    });
    other.join();
    check(refused && !fixture.owner->reserve_document_sequence() && fixture.owner->cancel_editor_sequence(*reserved),
        "foreign-thread editor operation changed the serialized reservation");
}
void query_work_is_owned_and_joins_full_identity_catalog_and_reservation() {
    Fixture fixture; fixture.bind_context(); const auto work = next_query(fixture);
    for (unsigned variant = 0; variant != 11; ++variant) {
        auto changed = work;
        if (variant == 0) ++changed.target.worker_epoch;
        if (variant == 1) ++changed.target.application_instance;
        if (variant == 2) ++changed.target.document_sequence;
        if (variant == 3) ++changed.target.service_generation;
        if (variant == 4) ++changed.request_sequence;
        if (variant == 5) changed.operation = BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1;
        if (variant == 6) --changed.required_reply_capacity;
        if (variant == 7) changed.schema_sha256[0] ^= 1;
        if (variant == 8) changed.payload[16] ^= 1;
        if (variant == 9) changed.payload.push_back(0);
        if (variant == 10) changed.payload.resize(BIB_ENGINE_EDITOR_MAX_QUERY_BYTES + 1);
        check(fixture.owner->stage_editor_work(std::move(changed)).code != EngineEditorAdmissionCode::admitted &&
            !fixture.owner->reserve_document_sequence(), "invalid editor shape/identity released or bypassed exact reservation");
    }
    auto source = work; const auto admission = fixture.stage(source); std::fill(source.payload.begin(), source.payload.end(), 0);
    const auto pending = call(*fixture.owner, FOUNDATION_ENGINE_PEEK_EDITOR_WORK, fixture.id);
    ok(pending); check(pending.bytes == call(*fixture.owner, FOUNDATION_ENGINE_PEEK_EDITOR_WORK, fixture.id).bytes,
        "editor peek consumed/reminted immutable work");
    const auto dispatch = fixture.peek();
    check(dispatch.work.payload == work.payload && dispatch.work.request_sequence == work.request_sequence && dispatch.work.target == work.target,
        "staged editor work borrowed caller bytes or truncated u64 authority");
    fixture.claim(dispatch); fixture.turn(dispatch);
    fixture.settle(dispatch, unavailable_reply(work, surface_identity(fixture.id)), 0, 0, false, 31);
    check(fixture.owner->consume_editor_outcome(admission.ticket), "checked null projection was not locally collectable");
}
void complete_claim_and_one_balanced_turn_precede_exact_query_completion() {
    Fixture fixture; fixture.bind_context(); const auto work = next_query(fixture); const auto admission = fixture.stage(work);
    short_reply(*fixture.owner, FOUNDATION_ENGINE_PEEK_EDITOR_WORK, fixture.id, {}, 0,
        FOUNDATION_ENGINE_RECEIPT_BYTES + FOUNDATION_ENGINE_EDITOR_WORK_PREFIX_BYTES + work.payload.size() - 1);
    const auto dispatch = fixture.peek(); const auto claim = claim_bytes(static_cast<std::uint32_t>(work.kind), work.request_sequence);
    const auto checked = projection(surface_identity(fixture.id)); const auto raw = query_reply(work, checked);
    const auto good = result_bytes(dispatch, raw, 0, 0, false, 31);
    check(call(*fixture.owner, FOUNDATION_ENGINE_EDITOR_WORK_RESULT, fixture.id, good, dispatch.transfer).control != 0, "unclaimed editor query result settled");
    short_reply(*fixture.owner, FOUNDATION_ENGINE_BEGIN_EDITOR_WORK, fixture.id, claim, dispatch.transfer, FOUNDATION_ENGINE_RECEIPT_BYTES - 1);
    fixture.claim(dispatch);
    check(call(*fixture.owner, FOUNDATION_ENGINE_BEGIN_EDITOR_WORK, fixture.id, claim, dispatch.transfer).control != 0, "second editor claim authorized replay");
    check(call(*fixture.owner, FOUNDATION_ENGINE_EDITOR_WORK_RESULT, fixture.id, good, dispatch.transfer).control != 0, "successful editor query settled without a TURN");
    ok(call(*fixture.owner, FOUNDATION_ENGINE_TURN_ENTER, fixture.id, {}, dispatch.transfer));
    check(call(*fixture.owner, FOUNDATION_ENGINE_EDITOR_WORK_RESULT, fixture.id, good, dispatch.transfer).control != 0, "editor query result settled inside native TURN");
    ok(call(*fixture.owner, FOUNDATION_ENGINE_TURN_LEAVE, fixture.id, {}, dispatch.transfer));
    check(call(*fixture.owner, FOUNDATION_ENGINE_TURN_ENTER, fixture.id, {}, dispatch.transfer).control != 0, "editor work entered a second outer TURN");
    short_reply(*fixture.owner, FOUNDATION_ENGINE_EDITOR_WORK_RESULT, fixture.id, good, dispatch.transfer, FOUNDATION_ENGINE_RECEIPT_BYTES - 1);
    for (unsigned field = 0; field != 5; ++field) {
        auto id = fixture.id; auto transfer = dispatch.transfer; auto changed = good;
        if (field == 0) ++id.worker_epoch;
        if (field == 1) ++id.application_instance;
        if (field == 2) ++id.document_sequence;
        if (field == 3) ++id.service_generation;
        if (field == 4) ++transfer;
        check(call(*fixture.owner, FOUNDATION_ENGINE_EDITOR_WORK_RESULT, id, changed, transfer).control != 0 &&
            !fixture.owner->editor_outcome(admission.ticket), "crossed editor result identity published a completion");
    }
    ok(call(*fixture.owner, FOUNDATION_ENGINE_EDITOR_WORK_RESULT, fixture.id, good, dispatch.transfer));
    const auto retained = fixture.owner->editor_outcome(admission.ticket);
    check(retained && retained->outcome == EngineEditorOutcome::consumed && retained->bytes == raw && retained->semantic_revision == 31,
        "checked editor query lost immutable original bytes/current-read proof");
    ok(call(*fixture.owner, FOUNDATION_ENGINE_EDITOR_WORK_RESULT, fixture.id, good, dispatch.transfer));
    auto changed = good; changed.back() ^= 1;
    check(call(*fixture.owner, FOUNDATION_ENGINE_EDITOR_WORK_RESULT, fixture.id, changed, dispatch.transfer).control != 0 &&
        retained == fixture.owner->editor_outcome(admission.ticket), "changed local redelivery replaced original editor proof");
    check(fixture.owner->consume_editor_outcome(admission.ticket), "editor query local debt did not collect");
    retire_projection(fixture, checked);
}
void known_not_entered_and_checked_unavailable_queries_are_distinct() {
    Fixture fixture; fixture.bind_context(); const auto work = next_query(fixture); const auto admission = fixture.stage(work);
    const auto dispatch = fixture.peek(); fixture.claim(dispatch);
    check(call(*fixture.owner, FOUNDATION_ENGINE_EDITOR_WORK_RESULT, fixture.id,
        result_bytes(dispatch, {}, BIB_ENGINE_PROCESS_EXIT_REQUIRED), dispatch.transfer).control != 0,
        "unentered query fabricated a naturally returned trap result");
    fixture.settle(dispatch, {}, BIB_ENGINE_STALE);
    const auto rejected = fixture.owner->editor_outcome(admission.ticket);
    check(rejected && rejected->outcome == EngineEditorOutcome::rejected && rejected->bytes.empty() &&
        fixture.owner->consume_editor_outcome(admission.ticket), "known-not-entered query did not defer without a TURN");
    const auto next = next_query(fixture); const auto null_admission = fixture.stage(next); const auto read = fixture.peek();
    fixture.claim(read); fixture.turn(read);
    fixture.settle(read, unavailable_reply(next, surface_identity(fixture.id), 42), 0, 0, false, 42);
    const auto unavailable = fixture.owner->editor_outcome(null_admission.ticket);
    check(unavailable && unavailable->outcome == EngineEditorOutcome::consumed && unavailable->semantic_revision == 42 &&
        fixture.owner->consume_editor_outcome(null_admission.ticket) && fixture.owner->editor_enabled(),
        "checked unavailable readback became no-entry, unknown, or native authority");
}
void observation_and_revoke_use_latest_checked_material_without_native_replay() {
    Fixture fixture; fixture.bind_context(); const auto old = complete_query(fixture);
    const auto sequence = fixture.owner->reserve_editor_sequence(); check(bool(sequence), "observation sequence unavailable");
    const auto work = observation_work(fixture.id, *sequence, old); const auto admission = fixture.stage(work); const auto dispatch = fixture.peek();
    fixture.claim(dispatch); fixture.turn(dispatch);
    auto refreshed = old; ++refreshed.mapping_id; ++refreshed.editor_revision;
    refreshed.retire->mapping_id = refreshed.mapping_id;
    const auto raw = native_reply(work, observed_result(refreshed)); fixture.settle(dispatch, raw, 0, 1, true);
    const auto retained = fixture.owner->editor_outcome(admission.ticket);
    codec::NativeResultEnvelope checked;
    check(retained && retained->outcome == EngineEditorOutcome::consumed && retained->handled && codec::decode_native_result(retained->bytes, checked) &&
        checked.result.projection && checked.result.projection->retire && checked.result.projection->retire->token == old.retire->token,
        "same-context observation did not retain checked refreshed material under the stable token");
    fixture.settle(dispatch, raw, 0, 1, true);
    check(call(*fixture.owner, FOUNDATION_ENGINE_BEGIN_EDITOR_WORK, fixture.id,
        claim_bytes(static_cast<std::uint32_t>(work.kind), work.request_sequence), dispatch.transfer).control != 0,
        "consumed editor8 local redelivery authorized a second native attempt");
    check(fixture.owner->consume_editor_outcome(admission.ticket) && fixture.owner->stage_editor_work(work).code != EngineEditorAdmissionCode::admitted,
        "consumed editor8 became restageable without a new global sequence");
    const auto revoke_sequence = fixture.owner->reserve_editor_sequence(); check(bool(revoke_sequence), "revoke sequence unavailable");
    const auto stale = revoke_work(fixture.id, *revoke_sequence, old);
    check(fixture.owner->stage_editor_work(stale).code != EngineEditorAdmissionCode::admitted, "native9 accepted stale mapping metadata under the old stable token");
    const auto revoke = revoke_work(fixture.id, *revoke_sequence, *checked.result.projection); const auto revoked = fixture.stage(revoke);
    const auto pending = fixture.peek(); fixture.claim(pending);
    const auto correct = native_reply(revoke, revoked_result(*checked.result.projection));
    check(call(*fixture.owner, FOUNDATION_ENGINE_EDITOR_WORK_RESULT, fixture.id,
        result_bytes(pending, correct, 0, 1), pending.transfer).control != 0, "native9 took a metadata-only shortcut around full TURN");
    fixture.turn(pending);
    fixture.settle(pending, correct, 0, 1);
    check(fixture.owner->consume_editor_outcome(revoked.ticket), "exact native9 proof failed local collection");
}
void revoke_cannot_use_synthetic_material_before_a_checked_query_result() {
    Fixture fixture; fixture.bind_context(); const auto sequence = fixture.owner->reserve_editor_sequence(); check(bool(sequence), "unlearned revoke sequence unavailable");
    const auto unlearned = projection(surface_identity(fixture.id));
    check(fixture.owner->stage_editor_work(revoke_work(fixture.id, *sequence, unlearned)).code != EngineEditorAdmissionCode::admitted &&
        fixture.owner->cancel_editor_sequence(*sequence), "native9 accepted unlearned renderer-shaped retirement material");
}
void new_retirement_token_requires_exact_old_proof_in_the_same_completion() {
    Fixture fixture; fixture.bind_context(); const auto old = complete_query(fixture);
    auto replacement = old; ++replacement.mapping_id; ++replacement.frame_id; ++replacement.retire->token; replacement.retire->mapping_id = replacement.mapping_id;
    const auto sequence = fixture.owner->reserve_editor_sequence(); check(bool(sequence), "replacement observation sequence unavailable");
    const auto observation = observation_work(fixture.id, *sequence, old); const auto observed = fixture.stage(observation);
    const auto pending = fixture.peek(); fixture.claim(pending); fixture.turn(pending);
    auto result = observed_result(replacement, 45); result.continuity = native::Continuity::replaced;
    result.retired = old.retire;
    fixture.settle(pending, native_reply(observation, result), 0, 1);
    const auto completion = fixture.owner->editor_outcome(observed.ticket); codec::NativeResultEnvelope checked;
    check(completion && codec::decode_native_result(completion->bytes, checked) && checked.result.retired == old.retire &&
        checked.result.projection && fixture.owner->consume_editor_outcome(observed.ticket), "same checked native8 completion lost old retirement/new token join");
    retire_projection(fixture, *checked.result.projection);
}
void consumed_form_debt_blocks_fresh_editor_work_but_not_existing_ack7() {
    Fixture fixture; fixture.bind_context(); const auto checked = complete_query(fixture);
    const auto sequence = fixture.owner->reserve_document_sequence(); check(bool(sequence), "form barrier sequence unavailable");
    const auto form = form_work(fixture.id, *sequence); const auto admitted = fixture.owner->stage_document_work(form);
    check(admitted.code == EngineDocumentAdmissionCode::admitted && admitted.ticket, "synthetic form barrier was not admitted");
    const auto pending = call(*fixture.owner, FOUNDATION_ENGINE_PEEK_DOCUMENT_WORK, fixture.id); ok(pending);
    ok(call(*fixture.owner, FOUNDATION_ENGINE_BEGIN_DOCUMENT_WORK, fixture.id, claim_bytes(2, *sequence), pending.transfer));
    ok(call(*fixture.owner, FOUNDATION_ENGINE_TURN_ENTER, fixture.id, {}, pending.transfer));
    ok(call(*fixture.owner, FOUNDATION_ENGINE_TURN_LEAVE, fixture.id, {}, pending.transfer));
    auto form_raw = document_bytes(form.target, *sequence, 5, 0, 52); form_raw[48] = 1; form_raw[49] = 6;
    ok(call(*fixture.owner, FOUNDATION_ENGINE_DOCUMENT_WORK_RESULT, fixture.id,
        result_bytes(2, *sequence, form_raw, 0, 1), pending.transfer));
    check(!fixture.owner->consume_document_outcome(admitted.ticket) && !fixture.owner->reserve_editor_sequence(), "consumed form debt permitted fresh editor sequence or local retirement");
    const auto ack = fixture.owner->stage_document_action_ack(form.target, *sequence);
    check(ack.code == EngineDocumentAdmissionCode::admitted && ack.ticket, "deferred native9/form debt starved existing form ACK7");
    const auto metadata = call(*fixture.owner, FOUNDATION_ENGINE_PEEK_DOCUMENT_WORK, fixture.id); ok(metadata);
    check(get(metadata.body(), 0, 4) == 3, "form ACK7 did not retain metadata priority");
    const auto ack_sequence = get(metadata.body(), 8, 8);
    ok(call(*fixture.owner, FOUNDATION_ENGINE_BEGIN_DOCUMENT_WORK, fixture.id, claim_bytes(3, ack_sequence), metadata.transfer));
    Bytes receipt(16); put(receipt, 0, *sequence, 8);
    ok(call(*fixture.owner, FOUNDATION_ENGINE_DOCUMENT_WORK_RESULT, fixture.id,
        result_bytes(3, ack_sequence, receipt, 0, 1), metadata.transfer));
    check(!fixture.owner->reserve_editor_sequence(), "ACK7 native result bypassed uncollected local form/ACK debt");
    check(fixture.owner->consume_document_outcome(ack.ticket) && fixture.owner->consume_document_outcome(admitted.ticket), "checked ACK7 did not release exact form debt");
    retire_projection(fixture, checked);
}
void staged_allocation_failures_keep_exact_editor_reservation_cancellable() {
    bool reached_admission = false; unsigned failed_points = 0;
    for (std::size_t failure = 0; failure != 64 && !reached_admission; ++failure) {
        Fixture fixture; fixture.bind_context(); const auto work = next_query(fixture); auto attempted = work;
        allocation_probe::calls = 0; allocation_probe::fail_after = failure; allocation_probe::armed = true;
        const auto admission = fixture.owner->stage_editor_work(std::move(attempted));
        allocation_probe::armed = false;
        if (admission.code != EngineEditorAdmissionCode::admitted) {
            ++failed_points;
            check(!fixture.owner->editor_outcome(admission.ticket) && !fixture.owner->reserve_document_sequence() &&
                fixture.owner->cancel_editor_sequence(work.request_sequence), "allocation failure exposed work, lost reservation or permitted overtaking");
            const auto empty = call(*fixture.owner, FOUNDATION_ENGINE_PEEK_EDITOR_WORK, fixture.id);
            check(empty.control == FOUNDATION_ENGINE_EMPTY, "allocation failure left an exposed partial editor slot");
        } else {
            reached_admission = true; const auto dispatch = fixture.peek(); fixture.claim(dispatch); fixture.settle(dispatch, {}, BIB_ENGINE_STALE);
            check(fixture.owner->consume_editor_outcome(admission.ticket), "success after allocation probes did not settle known-not-entered work");
        }
    }
    allocation_probe::fail_after = std::numeric_limits<std::size_t>::max();
    check(reached_admission && failed_points >= 3, "bounded allocation sweep did not cover completion/capacity setup before admission");
}
void other_mailbox_lanes_cannot_claim_or_settle_editor_authority() {
    Fixture fixture; fixture.bind_context(); const auto work = next_query(fixture); const auto admission = fixture.stage(work);
    const auto dispatch = fixture.peek(); const auto claim = claim_bytes(1, work.request_sequence);
    check(call(*fixture.owner, FOUNDATION_ENGINE_BEGIN_DOCUMENT_WORK, fixture.id, claim, dispatch.transfer).control != 0,
        "document mailbox claimed an editor transfer");
    check(call(*fixture.owner, FOUNDATION_ENGINE_PEEK_DOCUMENT_WORK, fixture.id).control == FOUNDATION_ENGINE_EMPTY &&
        call(*fixture.owner, FOUNDATION_ENGINE_PEEK_INPUT, fixture.id).control == FOUNDATION_ENGINE_EMPTY,
        "another mailbox exposed work over pending editor authority");
    fixture.claim(dispatch); fixture.turn(dispatch);
    const auto raw = unavailable_reply(work, surface_identity(fixture.id));
    check(call(*fixture.owner, FOUNDATION_ENGINE_DOCUMENT_WORK_RESULT, fixture.id,
        result_bytes(dispatch, raw, 0, 0, false, 31), dispatch.transfer).control != 0,
        "document mailbox settled an editor completion");
    Bytes physical;
    check(input::encode_command_result({0, 1, work.request_sequence, 0, 0}, physical) == input::Status::ok, "cross-lane physical fixture could not encode");
    check(call(*fixture.owner, FOUNDATION_ENGINE_COMMAND_RESULT, fixture.id, physical, dispatch.transfer).control != 0 &&
        !fixture.owner->editor_outcome(admission.ticket), "physical mailbox discharged editor authority");
    fixture.settle(dispatch, raw, 0, 0, false, 31);
    check(fixture.owner->consume_editor_outcome(admission.ticket), "cross-lane refusals changed rightful editor completion");
}
void navigation_and_known_close_cancel_only_unclaimed_editor_work() {
    for (const bool close : {false, true}) {
        Fixture fixture; fixture.bind_context(); const auto old = fixture.id; const auto work = next_query(fixture); const auto admission = fixture.stage(work);
        if (close) fixture.owner->close();
        else {
            auto successor = old; ++successor.document_sequence; successor.service_generation = 0;
            const auto begun = call(*fixture.owner, FOUNDATION_ENGINE_BEGIN_DOCUMENT, successor); ok(begun); fixture.id = begun.target;
        }
        const auto cancelled = fixture.owner->editor_outcome(admission.ticket);
        check(cancelled && cancelled->outcome == EngineEditorOutcome::cancelled && cancelled->target == editor_target(old) && cancelled->bytes.empty(),
            "navigation/close synthesized execution or erased known-unclaimed editor result");
        check(fixture.owner->consume_editor_outcome(admission.ticket), "cancelled editor result failed local collection");
        if (close) check(fixture.owner->closed(), "known editor cancellation did not finish orderly close");
        else {
            const auto next = fixture.owner->reserve_editor_sequence();
            check(next && *next > work.request_sequence && fixture.owner->cancel_editor_sequence(*next), "navigation reset/reused editor ordinary sequence");
        }
    }
}
Bytes service_request(EngineIdentity target, std::uint64_t sequence, std::uint64_t handle, std::uint32_t operation, Span payload) {
    Envelope envelope; envelope.generation = target.service_generation; envelope.sequence = sequence;
    envelope.interface_handle = handle; envelope.operation = operation;
    Bytes result; check(encode_envelope(envelope, payload, result) == CodecStatus::ok, "native service fixture could not encode"); return result;
}
void old_target_revoke_drains_before_a_successor_native_effect() {
    Fixture fixture(Profile::editor, true, {}, true); fixture.bind_context(); const auto checked = complete_query(fixture); const auto old = fixture.id;
    auto successor = old; ++successor.document_sequence; successor.service_generation = 0;
    const auto begun = call(*fixture.owner, FOUNDATION_ENGINE_BEGIN_DOCUMENT, successor); ok(begun); fixture.id = begun.target;
    const auto major = encode_u32(1), minor = encode_u32(0);
    const Span name{reinterpret_cast<const std::uint8_t*>(Fixture::service_name.data()), Fixture::service_name.size()};
    const std::array<FieldView, 4> fields{{{1, FieldType::utf8, true, name}, {2, FieldType::u32, true, major},
        {3, FieldType::u32, true, minor}, {4, FieldType::u32, true, minor}}};
    Bytes query; check(encode_record(fields, query) == CodecStatus::ok, "native discovery fixture could not encode");
    ok(call(*fixture.owner, FOUNDATION_ENGINE_SUBMIT, fixture.id,
        service_request(fixture.id, 1, 0, FOUNDATION_APPENDED_CONTROL_DISCOVER, query)));
    const auto gated = call(*fixture.owner, FOUNDATION_ENGINE_PUMP_ONE, fixture.id);
    const auto effect = fixture.owner->native_effect();
    check(gated.control == FOUNDATION_ENGINE_CONFLICT && effect && effect->target == fixture.id && !effect->entered && !fixture.native_effects,
        "successor service did not retain an unentered native-effect barrier");
    const auto sequence = fixture.owner->reserve_editor_sequence(); check(bool(sequence), "old retirement could not reserve behind successor effect");
    const auto work = revoke_work(old, *sequence, checked); const auto admission = fixture.stage(work); const auto pending = fixture.peek();
    check(pending.work.target == editor_target(old), "old native9 was rewritten onto successor identity");
    fixture.claim(pending); fixture.turn(pending);
    // Explicit synthetic provider already-retired attestation after a full
    // old-target TURN. A stale status or successor rewrite is never proof.
    fixture.settle(pending, native_reply(work, revoked_result(checked)), 0, 1);
    check(fixture.owner->consume_editor_outcome(admission.ticket) && fixture.owner->identity() == fixture.id,
        "checked old native9 changed successor identity or retained local debt");
    fixture.safe_publication = true;
    check(fixture.owner->acknowledge_document_native_effect(effect->ticket, document_target(fixture.id), 1),
        "settled old retirement did not release successor safe-publication gate");
    ok(call(*fixture.owner, FOUNDATION_ENGINE_PUMP_ONE, fixture.id));
    const auto delivery = call(*fixture.owner, FOUNDATION_ENGINE_PEEK_DELIVERY, fixture.id); ok(delivery);
    Envelope completed; Span descriptor;
    check(decode_envelope(delivery.body(), completed, descriptor) == CodecStatus::ok && completed.sequence == 1 && !completed.service_status && !descriptor.empty(),
        "successor native discovery did not complete after exact old retirement");
    const auto accepted = encode_u32(FOUNDATION_ENGINE_ACCEPTED);
    ok(call(*fixture.owner, FOUNDATION_ENGINE_DELIVERY_RESULT, delivery.target, accepted, delivery.transfer));
    const auto ack = call(*fixture.owner, FOUNDATION_ENGINE_STAGE_ACK, fixture.id, encode_u64(1));
    check(ack.control == FOUNDATION_ENGINE_OK && ack.service == static_cast<std::uint32_t>(ServiceStatus::unavailable), "successor service ACK was not staged");
    ok(call(*fixture.owner, FOUNDATION_ENGINE_PUMP_ONE, fixture.id));
    const auto receipt = call(*fixture.owner, FOUNDATION_ENGINE_PEEK_ACK_RECEIPT, fixture.id); ok(receipt);
    ok(call(*fixture.owner, FOUNDATION_ENGINE_ACK_RECEIPT_RESULT, receipt.target, accepted, receipt.transfer));
    check(!fixture.owner->native_effect(), "known successor service retained or replayed an effect after old9 drained");
}
std::size_t reset_without_allocation(std::unique_ptr<EngineOwner>& owner) noexcept {
    allocation_probe::calls = 0; allocation_probe::fail_after = std::numeric_limits<std::size_t>::max();
    allocation_probe::armed = true; owner.reset(); allocation_probe::armed = false;
    return allocation_probe::calls;
}
void later_editor_factory_is_blocked() {
    const auto counters = std::make_shared<ModuleCounters>(); bool refused = false;
    try { Fixture later(Profile::editor, true, counters); } catch (const std::runtime_error&) { refused = true; }
    check(refused && !counters->factories && !counters->constructed, "terminal process admitted a later editor binding/factory");
}
void terminal_unknown(unsigned operation) {
    const auto counters = std::make_shared<ModuleCounters>(); Fixture fixture(Profile::editor, true, counters); fixture.bind_context();
    EngineEditorWork work;
    if (operation == BIB_ENGINE_QUERY_EDITOR_PROJECTION_V1) work = next_query(fixture);
    else {
        const auto checked = complete_query(fixture); const auto sequence = fixture.owner->reserve_editor_sequence(); check(bool(sequence), "unknown command sequence unavailable");
        work = operation == BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1 ? observation_work(fixture.id, *sequence, checked) : revoke_work(fixture.id, *sequence, checked);
    }
    const auto admission = fixture.stage(work); const auto dispatch = fixture.peek(); fixture.claim(dispatch); fixture.turn(dispatch);
    const bool query = operation == BIB_ENGINE_QUERY_EDITOR_PROJECTION_V1;
    const Bytes forensic = query ? Bytes{} : Bytes{0xff, 0, 0x91, 0x80};
    const auto raw = result_bytes(dispatch, forensic, query ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : 0, query ? 0 : 2, !query);
    ok(call(*fixture.owner, FOUNDATION_ENGINE_EDITOR_WORK_RESULT, fixture.id, raw, dispatch.transfer));
    const auto retained = fixture.owner->editor_outcome(admission.ticket);
    check(retained && retained->outcome == EngineEditorOutcome::unknown && retained->bytes == forensic && retained->handled == !query,
        "outer unknown editor result lost bounded original forensic evidence");
    ok(call(*fixture.owner, FOUNDATION_ENGINE_EDITOR_WORK_RESULT, fixture.id, raw, dispatch.transfer));
    auto changed = raw;
    if (query) put(changed, 16, static_cast<std::uint32_t>(BIB_ENGINE_STALE), 4); else changed.back() ^= 1;
    check(call(*fixture.owner, FOUNDATION_ENGINE_EDITOR_WORK_RESULT, fixture.id, changed, dispatch.transfer).control != 0 &&
        retained == fixture.owner->editor_outcome(admission.ticket), "unknown editor redelivery changed immutable evidence");
    check(!fixture.owner->consume_editor_outcome(admission.ticket) && !fixture.owner->editor_enabled() && !fixture.owner->input_enabled() &&
        !fixture.owner->reserve_editor_sequence() && !fixture.owner->reserve_document_sequence() &&
        fixture.owner->stage_editor_work(work).code != EngineEditorAdmissionCode::admitted,
        "outer unknown editor authority became collectable/replayable or admitted fresh work");
    fixture.owner->close();
    check(!counters->close_calls && !counters->destroyed && reset_without_allocation(fixture.owner) == 0 &&
        !counters->close_calls && !counters->destroyed, "unknown editor teardown allocated or cleaned up a live binding");
    later_editor_factory_is_blocked();
}
void terminal_close_claimed(bool enter) {
    const auto counters = std::make_shared<ModuleCounters>(); Fixture fixture(Profile::editor, true, counters); fixture.bind_context();
    const auto work = next_query(fixture); const auto admission = fixture.stage(work); const auto dispatch = fixture.peek(); fixture.claim(dispatch);
    if (enter) ok(call(*fixture.owner, FOUNDATION_ENGINE_TURN_ENTER, fixture.id, {}, dispatch.transfer));
    fixture.owner->close();
    check(!fixture.owner->editor_outcome(admission.ticket) && !fixture.owner->closed() &&
        fixture.owner->callback_depth() == (enter ? 1u : 0u) && !counters->close_calls, "close fabricated result/LEAVE or cleaned up an editor claim");
    check(reset_without_allocation(fixture.owner) == 0 && !counters->close_calls && !counters->destroyed,
        "claimed/entered editor destruction escaped allocation-free quarantine");
    later_editor_factory_is_blocked();
}
void terminal_notification_claimed_or_natural_return(bool entered) {
    const auto counters = std::make_shared<ModuleCounters>(); Fixture fixture(Profile::editor, true, counters); fixture.bind_context();
    const auto work = next_query(fixture); const auto admission = fixture.stage(work); const auto dispatch = fixture.peek(); fixture.claim(dispatch);
    if (entered) ok(call(*fixture.owner, FOUNDATION_ENGINE_TURN_ENTER, fixture.id, {}, dispatch.transfer));
    std::thread notification([&] { fixture.owner->notify_document_terminal(); fixture.owner->notify_document_terminal(); }); notification.join();
    check(fixture.owner->callback_depth() == (entered ? 1u : 0u) && !fixture.owner->editor_outcome(admission.ticket) &&
        !counters->close_calls && !fixture.owner->reserve_editor_sequence(), "terminal publication preempted/fabricated editor return or performed cleanup");
    if (entered) {
        ok(call(*fixture.owner, FOUNDATION_ENGINE_TURN_LEAVE, fixture.id, {}, dispatch.transfer));
        fixture.settle(dispatch, unavailable_reply(work, surface_identity(fixture.id)), 0, 0, false, 31);
        const auto proof = fixture.owner->editor_outcome(admission.ticket);
        check(proof && proof->outcome == EngineEditorOutcome::consumed && fixture.owner->consume_editor_outcome(admission.ticket),
            "admitted exact editor turn could not finish naturally after terminal publication");
    } else {
        check(call(*fixture.owner, FOUNDATION_ENGINE_TURN_ENTER, fixture.id, {}, dispatch.transfer).control != 0 &&
            !fixture.owner->editor_outcome(admission.ticket), "unentered editor claim acquired post-terminal native entry/result");
    }
    check(reset_without_allocation(fixture.owner) == 0 && !counters->close_calls && !counters->destroyed,
        "notified editor owner cleaned up or allocated quarantine state");
    later_editor_factory_is_blocked();
}
void terminal_idle_preexisting_sibling_does_not_cleanup() {
    const auto first_counts = std::make_shared<ModuleCounters>(), idle_counts = std::make_shared<ModuleCounters>();
    Fixture first(Profile::editor, true, first_counts), idle(Profile::editor, true, idle_counts);
    check(idle_counts->constructed == 1 && !idle.owner->native_effect() && !idle.owner->editor_outcome(1), "idle sibling was not constructed without pending work");
    first.owner->notify_document_terminal();
    check(!idle.owner->editor_enabled() && reset_without_allocation(idle.owner) == 0 && !idle_counts->close_calls && !idle_counts->destroyed,
        "idle preexisting sibling cleaned up its binding after global terminal publication");
    check(reset_without_allocation(first.owner) == 0 && !first_counts->close_calls && !first_counts->destroyed,
        "notifying owner escaped terminal quarantine while idle sibling was retained");
    later_editor_factory_is_blocked();
}
void terminal_matched_malformed_result(unsigned variant) {
    const auto counters = std::make_shared<ModuleCounters>(); Fixture fixture(Profile::editor, true, counters); fixture.bind_context();
    std::optional<native::NativeProjection> prior;
    if (variant >= 2) prior = complete_query(fixture);
    const auto sequence = fixture.owner->reserve_editor_sequence(); check(bool(sequence), "malformed result sequence unavailable");
    EngineEditorWork work;
    auto query_identity = surface_identity(fixture.id);
    if (variant == 7) query_identity.owner.id = "substituted-editor-owner";
    if (variant <= 2 || variant >= 7) work = query_work(fixture.id, *sequence, query_identity);
    else if (variant == 3 || variant == 5) work = observation_work(fixture.id, *sequence, *prior);
    else work = revoke_work(fixture.id, *sequence, *prior);
    const auto admission = fixture.stage(work); const auto dispatch = fixture.peek(); fixture.claim(dispatch); fixture.turn(dispatch);
    Bytes malformed, corrected;
    if (variant <= 2 || variant >= 7) {
        corrected = result_bytes(dispatch, unavailable_reply(work, query_identity, 44), 0, 0, false, 44);
        malformed = corrected;
        if (variant == 0) put(malformed, 32, 45, 8);
        if (variant == 1) malformed[FOUNDATION_ENGINE_EDITOR_RESULT_PREFIX_BYTES + 24] ^= 1;
        if (variant == 2) {
            auto replacement = *prior; ++replacement.retire->token; ++replacement.frame_id;
            malformed = result_bytes(dispatch, query_reply(work, replacement, 44), 0, 0, false, 44);
        }
        if (variant == 7) {
            auto rebound = *prior; rebound.identity = query_identity;
            malformed = result_bytes(dispatch, query_reply(work, rebound, 44), 0, 0, false, 44);
        }
        if (variant == 8) put(malformed, 8, work.request_sequence + 1, 8);
        if (variant == 9) put(malformed, 0, static_cast<std::uint32_t>(EngineEditorWorkKind::observation), 4);
        if (variant == 10) put(malformed, 4, 1, 4);
        if (variant == 11) malformed.resize(FOUNDATION_ENGINE_EDITOR_RESULT_PREFIX_BYTES - 1);
    } else if (variant == 3) {
        auto replacement = *prior; ++replacement.retire->token; ++replacement.frame_id;
        auto result = observed_result(replacement, 45); result.continuity = native::Continuity::replaced;
        malformed = result_bytes(dispatch, native_reply(work, result), 0, 1);
        result.retired = prior->retire; corrected = result_bytes(dispatch, native_reply(work, result), 0, 1);
    } else if (variant == 4) {
        auto result = revoked_result(*prior); ++result.retired->mapping_id;
        malformed = result_bytes(dispatch, native_reply(work, result), 0, 1);
        corrected = result_bytes(dispatch, native_reply(work, revoked_result(*prior)), 0, 1);
    } else {
        native::NativeResult unknown;
        malformed = result_bytes(dispatch, native_reply(work, unknown), 0, 1, true);
        corrected = result_bytes(dispatch, native_reply(work,
            variant == 5 ? observed_result(*prior) : revoked_result(*prior)), 0, 1);
    }
    const auto receipt = call(*fixture.owner, FOUNDATION_ENGINE_EDITOR_WORK_RESULT, fixture.id, malformed, dispatch.transfer);
    const bool semantic_unknown = variant == 5 || variant == 6;
    if (semantic_unknown) {
        ok(receipt);
        const auto completion = fixture.owner->editor_outcome(admission.ticket);
        const Span original = Span(malformed).subspan(FOUNDATION_ENGINE_EDITOR_RESULT_PREFIX_BYTES);
        check(completion && completion->outcome == EngineEditorOutcome::unknown && completion->provider_status == 0 &&
            completion->provider_disposition == 1 && completion->handled && completion->bytes == Bytes(original.begin(), original.end()),
            "inner unknown was lost, rewritten as outer disposition2, or accepted as editor success");
    } else {
        const bool refused = variant >= 10 ? receipt.control == FOUNDATION_ENGINE_INVALID :
            receipt.control == FOUNDATION_ENGINE_INVALID || receipt.control == FOUNDATION_ENGINE_CONFLICT;
        check(refused &&
            !fixture.owner->editor_outcome(admission.ticket), "matched malformed natural return fabricated a completion or remained repairable");
    }
    check(!fixture.owner->editor_enabled() && !fixture.owner->input_enabled() && !fixture.owner->reserve_editor_sequence() &&
        !fixture.owner->consume_editor_outcome(admission.ticket) && fixture.owner->callback_depth() == 0,
        "matched malformed/unknown native receipt kept admission or synthesized native turn state");
    const auto repair = call(*fixture.owner, FOUNDATION_ENGINE_EDITOR_WORK_RESULT, fixture.id, corrected, dispatch.transfer);
    check(semantic_unknown ? repair.control != FOUNDATION_ENGINE_OK : repair.control == FOUNDATION_ENGINE_CLOSED,
        "matched malformed/unknown receipt accepted a corrected result instead of terminal quarantine");
    if (!semantic_unknown) check(!fixture.owner->editor_outcome(admission.ticket), "faulted result slot published a manufactured outcome after correction");
    fixture.owner->close();
    check(reset_without_allocation(fixture.owner) == 0 && !counters->close_calls && !counters->destroyed,
        "malformed/inner-unknown result performed cleanup or allocated terminal quarantine");
    later_editor_factory_is_blocked();
}

}

int main(int argc, char** argv) {
    try {
        if (argc == 3 && std::string_view(argv[1]) == "--case") {
            const std::array<std::pair<std::string_view, void(*)()>, 20> terminal{{
                {"unknown-query", +[] { terminal_unknown(BIB_ENGINE_QUERY_EDITOR_PROJECTION_V1); }},
                {"unknown-observation", +[] { terminal_unknown(BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1); }},
                {"unknown-revoke", +[] { terminal_unknown(BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1); }},
                {"close-claimed", +[] { terminal_close_claimed(false); }},
                {"close-active", +[] { terminal_close_claimed(true); }},
                {"notify-claimed", +[] { terminal_notification_claimed_or_natural_return(false); }},
                {"notify-natural-return", +[] { terminal_notification_claimed_or_natural_return(true); }},
                {"malformed-query-revision", +[] { terminal_matched_malformed_result(0); }},
                {"malformed-query-key", +[] { terminal_matched_malformed_result(1); }},
                {"unretired-query-token", +[] { terminal_matched_malformed_result(2); }},
                {"unproved-observation-token", +[] { terminal_matched_malformed_result(3); }},
                {"mismatched-revoke-proof", +[] { terminal_matched_malformed_result(4); }},
                {"inner-unknown-observation", +[] { terminal_matched_malformed_result(5); }},
                {"inner-unknown-revoke", +[] { terminal_matched_malformed_result(6); }},
                {"same-token-gui-owner", +[] { terminal_matched_malformed_result(7); }},
                {"matched-wrong-body-sequence", +[] { terminal_matched_malformed_result(8); }},
                {"matched-wrong-body-kind", +[] { terminal_matched_malformed_result(9); }},
                {"global-terminal-idle-sibling", terminal_idle_preexisting_sibling_does_not_cleanup},
                {"malformed-reserved-prefix", +[] { terminal_matched_malformed_result(10); }},
                {"malformed-short-prefix", +[] { terminal_matched_malformed_result(11); }},
            }};
            for (const auto& [name, test] : terminal) if (name == argv[2]) {
                test(); std::cout << "PASS isolated editor " << name << ", " << assertions << " assertions; synthetic Owner only\n"; return 0;
            }
            throw std::invalid_argument("unknown isolated editor terminal case");
        }
        if (argc != 1) throw std::invalid_argument("run normal cases or --case NAME in a fresh process");
        const std::array<std::pair<std::string_view, void(*)()>, 15> cases{{
            {"disabled and frozen profiles", disabled_and_frozen_profiles_refuse_editor_mailbox},
            {"independent editor facts", independent_editor_profile_facts},
            {"shared reservation burn", shared_reservation_burns_before_later_physical_and_document_work},
            {"foreign-thread reservation refusal", foreign_thread_cannot_acquire_or_cancel_editor_reservation},
            {"owned work and exact joins", query_work_is_owned_and_joins_full_identity_catalog_and_reservation},
            {"claim turn and current-read proof", complete_claim_and_one_balanced_turn_precede_exact_query_completion},
            {"known no-entry and checked unavailable", known_not_entered_and_checked_unavailable_queries_are_distinct},
            {"observation and exact revoke", observation_and_revoke_use_latest_checked_material_without_native_replay},
            {"unlearned retirement refusal", revoke_cannot_use_synthetic_material_before_a_checked_query_result},
            {"old retirement and new token proof", new_retirement_token_requires_exact_old_proof_in_the_same_completion},
            {"form debt and metadata ACK7", consumed_form_debt_blocks_fresh_editor_work_but_not_existing_ack7},
            {"allocation failure ordering", staged_allocation_failures_keep_exact_editor_reservation_cancellable},
            {"cross-mailbox authority refusal", other_mailbox_lanes_cannot_claim_or_settle_editor_authority},
            {"unclaimed navigation and close", navigation_and_known_close_cancel_only_unclaimed_editor_work},
            {"old native9 and successor effect", old_target_revoke_drains_before_a_successor_native_effect},
        }};
        for (const auto& [name, test] : cases) { test(); std::cout << "PASS " << name << '\n'; }
        std::cout << cases.size() << " synthetic editor Owner groups, " << assertions << " assertions; no native engine execution\n";
        return 0;
    } catch (const std::exception& error) {
        allocation_probe::armed = false;
        std::cerr << "FAIL editor Owner: " << error.what() << '\n';
        return 1;
    }
}
