// SPDX-License-Identifier: CC0-1.0
// Fresh-process C-table fixtures using the real EngineOwner and native driver.
// These synthetic values supply no engine, SDK, loader or native GUI evidence.
#include "../gui/shared/native_engine_driver.hpp"
#include "../gui/shared/appended_engine_abi.h"
#include "../gui/shared/appended_engine_input_codec.hpp"
#include "../gui/shared/native_editor_codec.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <functional>
#include <iostream>
#include <memory>
#include <optional>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace {
using namespace foundation::appended;
namespace editor = engine_editor;
namespace input = engine_input;
namespace native = foundation::ui::native_editor;
namespace codec = native::codec;
using Span = std::span<const std::uint8_t>;
using Clock = std::chrono::steady_clock;
using namespace std::chrono_literals;
constexpr std::uint64_t instance = UINT64_C(0x8000000000000044);
constexpr std::uint64_t first_document = UINT64_C(0x8000000000000001);
constexpr std::string_view service_name = "org.example.editor-driver.counter";
constexpr std::uint64_t observation_revision = UINT64_C(0x8123456789abcdef);
std::size_t assertions{};

void check(bool value, const char* message) {
    ++assertions;
    if (!value) throw std::runtime_error(message);
}
void put(std::span<std::uint8_t> out, std::size_t offset, std::uint64_t value, unsigned width) {
    check(width <= 8 && offset <= out.size() && width <= out.size() - offset, "fixture write extent");
    for (unsigned index = 0; index < width; ++index)
        out[offset + index] = static_cast<std::uint8_t>(value >> (8 * index));
}
std::uint64_t get(Span bytes, std::size_t offset, unsigned width) {
    check(width <= 8 && offset <= bytes.size() && width <= bytes.size() - offset, "fixture read extent");
    std::uint64_t result{};
    for (unsigned index = 0; index < width; ++index)
        result |= std::uint64_t(bytes[offset + index]) << (8 * index);
    return result;
}
EngineEditorTarget target(EngineIdentity identity) {
    return {identity.worker_epoch, identity.application_instance, identity.document_sequence, identity.service_generation};
}
EngineEditorTarget target(BibEngineDocumentV1 identity, std::uint64_t worker_epoch) {
    return {worker_epoch, identity.application_instance, identity.document_sequence, identity.service_generation};
}
codec::WireTarget wire_target(EngineEditorTarget identity, std::uint64_t sequence) {
    return {identity.worker_epoch, identity.application_instance, identity.document_sequence,
        identity.service_generation, sequence};
}
native::Identity surface_identity(EngineEditorTarget identity) {
    return {{"editor-driver", UINT64_C(0x8000000000000007)}, UINT64_C(0x8000000000000009),
        identity.service_generation, identity.worker_epoch, UINT64_C(0x800000000000000b)};
}
EngineEditorWork query_work(EngineEditorTarget identity, std::uint64_t sequence) {
    EngineEditorWork result;
    result.target = identity; result.request_sequence = sequence;
    result.kind = EngineEditorWorkKind::projection_query;
    result.operation = BIB_ENGINE_QUERY_EDITOR_PROJECTION_V1;
    result.required_reply_capacity = editor::kReplyCapacity; result.schema_sha256 = editor::kSchema;
    codec::ProjectionQuery query;
    query.target = wire_target(identity, sequence); query.identity = surface_identity(identity);
    check(codec::encode_projection_query(query, result.payload), "fixture projection query is not canonical binary");
    return result;
}
codec::ProjectionReply projection_reply(const codec::ProjectionQuery& query, bool available) {
    codec::ProjectionReply result;
    result.target = query.target; result.identity = query.identity;
    result.observation_revision = observation_revision; result.readback_attested = true;
    result.state = available ? codec::ProjectionReply::State::available : codec::ProjectionReply::State::unavailable;
    if (available) {
        native::NativeProjection projection;
        projection.identity = query.identity; projection.editor_revision = 3;
        projection.surrounding = std::string(BIB_ENGINE_EDITOR_MAX_TEXT_BYTES, 'x');
        projection.selection = {projection.surrounding.size(), projection.surrounding.size()};
        projection.mapping_id = UINT64_C(0x8000000000000011);
        projection.frame_id = UINT64_C(0x8000000000000013);
        projection.readback_attested = true; projection.caret = {12, 34, 1, 20};
        projection.input_purpose = "text";
        projection.retire = native::NativeRetireMaterial{UINT64_C(0x800000000000001d), projection.mapping_id,
            projection.identity.context, projection.composition};
        result.projection = std::move(projection);
    }
    return result;
}
codec::NativeRequestEnvelope observation_request(EngineEditorTarget identity, std::uint64_t sequence) {
    codec::NativeRequestEnvelope result;
    result.target = wire_target(identity, sequence);
    auto& projection = result.request.resolved;
    projection.identity = surface_identity(identity); projection.editor_revision = 3;
    projection.surrounding = "before"; projection.selection = {6, 6};
    projection.mapping_id = UINT64_C(0x8000000000000011); projection.frame_id = UINT64_C(0x8000000000000013);
    projection.readback_attested = true; projection.caret = {12, 34, 1, 20}; projection.input_purpose = "text";
    projection.retire = native::NativeRetireMaterial{UINT64_C(0x800000000000001d), projection.mapping_id,
        projection.identity.context, projection.composition};
    auto& packet = result.request.packet;
    packet.session = UINT64_C(0x8000000000000015);
    packet.basis = {UINT64_C(0x8000000000000019), projection.identity, projection.editor_revision,
        projection.surrounding, projection.selection, false, 0};
    auto& observation = packet.observation;
    observation.id = UINT64_C(0x800000000000001b); observation.kind = native::Kind::selection;
    observation.authority = native::Authority::range;
    observation.before = {projection.surrounding, 6, 6, native::Direction::none, {6, 6}, 6};
    observation.data = native::SelectionData{{0, 0}, false};
    return result;
}
EngineEditorWork observation_work(EngineEditorTarget identity, std::uint64_t sequence) {
    EngineEditorWork result;
    result.target = identity; result.request_sequence = sequence; result.kind = EngineEditorWorkKind::observation;
    result.operation = BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1;
    result.required_reply_capacity = editor::kReplyCapacity; result.schema_sha256 = editor::kSchema;
    check(codec::encode_native_request(observation_request(identity, sequence), result.payload),
        "fixture observation request is not canonical binary");
    return result;
}
codec::NativeResultEnvelope observation_reply(const codec::NativeRequestEnvelope& request) {
    codec::NativeResultEnvelope result;
    result.target = request.target;
    result.result.outcome = native::Outcome::applied;
    result.result.projection = request.request.resolved;
    result.result.projection->selection = {0, 0}; ++result.result.projection->editor_revision;
    result.result.availability = native::NativeAvailability::available;
    result.result.observation_revision = observation_revision;
    result.result.readback_identity = request.request.resolved.identity;
    result.result.readback_attested = true;
    result.result.retire = result.result.projection->retire;
    return result;
}
EngineEditorWork revocation_work(EngineEditorTarget identity, std::uint64_t sequence,
        native::NativeRetireMaterial material, native::Identity observed_identity) {
    EngineEditorWork result;
    result.target = identity; result.request_sequence = sequence; result.kind = EngineEditorWorkKind::revoke;
    result.operation = BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1;
    result.required_reply_capacity = editor::kReplyCapacity; result.schema_sha256 = editor::kSchema;
    codec::RevocationEnvelope request;
    request.target = wire_target(identity, sequence);
    request.request.material = material; request.request.identity = std::move(observed_identity);
    check(codec::encode_revocation(request, result.payload), "fixture revocation request is not canonical binary");
    return result;
}
codec::NativeResultEnvelope revocation_reply(const codec::RevocationEnvelope& request) {
    codec::NativeResultEnvelope result;
    result.target = request.target; result.result.outcome = native::Outcome::applied;
    result.result.availability = native::NativeAvailability::unavailable;
    result.result.observation_revision = observation_revision + 1;
    result.result.readback_identity = request.request.identity; result.result.readback_attested = true;
    result.result.retired = request.request.material;
    return result;
}
Bytes ndv2(EngineDocumentTarget identity, std::uint64_t sequence, unsigned kind, std::size_t length) {
    // Canonical header join only; this mock does not publish a semantic form tree.
    Bytes bytes(length);
    check(length >= 48, "fixture NDV2 prefix extent");
    std::copy_n("NDV2", 4, bytes.begin()); bytes[4] = 2; bytes[6] = static_cast<std::uint8_t>(kind);
    put(bytes, 8, identity.application_instance, 8); put(bytes, 16, identity.service_generation, 8);
    put(bytes, 24, identity.document_sequence, 8); put(bytes, 32, sequence, 8);
    return bytes;
}
EngineDocumentWork document_work(EngineIdentity identity, std::uint64_t sequence, bool form) {
    EngineDocumentWork value;
    value.target = {identity.worker_epoch, identity.application_instance, identity.document_sequence, identity.service_generation};
    value.request_sequence = sequence;
    value.kind = form ? EngineDocumentWorkKind::form_action : EngineDocumentWorkKind::snapshot_query;
    value.operation = form ? BIB_ENGINE_COMMAND_FORM_ACTION_V2 : BIB_ENGINE_QUERY_DOCUMENT_FORMS_V2;
    value.required_reply_capacity = BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY; value.schema_sha256 = engine_document::kSchema;
    value.payload = ndv2(value.target, sequence, form ? 2 : 1, form ? 81 : 48);
    if (form) {
        put(value.payload, 49, identity.application_instance, 8); put(value.payload, 57, identity.service_generation, 8);
        put(value.payload, 65, 1, 8); put(value.payload, 73, 1, 8);
    } else put(value.payload, 40, UINT64_C(0xf123456789abcdef), 8);
    return value;
}

Package package() {
    Package result;
    result.application = {"org.example.editor-driver", "Editor driver fixture", "1.0.0"};
    result.web = {true, "web/index.html", {}};
    result.capabilities = {"foundation.startup.v1"};
    result.package_sha256 = result.payload_id = result.kernel_sha256 = std::string(64, '1');
    const std::string startup = "{\"kind\":\"foundation-appended-startup\",\"primary\":\"web\",\"schema_version\":1}";
    result.files = {{"web/.foundation/startup-v1.json", "web", "application/json", std::string(64, '2'),
        Bytes(startup.begin(), startup.end())}, {"web/index.html", "web", "text/html", std::string(64, '3'), {}}};
    return result;
}

editor::EngineEditorProfileFacts profile() {
    editor::EngineEditorProfileFacts facts;
    facts.enabled = true; facts.kind = editor::ProfileKind::editor; facts.name = editor::kProfileName;
    facts.provider_abi_major = BIB_ENGINE_DOCUMENT_V2_ABI_MAJOR; facts.provider_abi_minor = BIB_ENGINE_DOCUMENT_V2_ABI_MINOR;
    facts.host_abi_major = BIB_ENGINE_DOCUMENT_V2_HOST_ABI_MAJOR; facts.host_abi_minor = BIB_ENGINE_DOCUMENT_V2_HOST_ABI_MINOR;
#if defined(_WIN32) && (defined(_M_X64) || defined(__x86_64__))
    facts.target_system = BIB_ENGINE_TARGET_WINDOWS; facts.target_processor = BIB_ENGINE_CPU_X86_64;
#elif defined(__linux__) && defined(__aarch64__)
    facts.target_system = BIB_ENGINE_TARGET_LINUX; facts.target_processor = BIB_ENGINE_CPU_AARCH64;
#elif defined(__linux__) && defined(__x86_64__)
    facts.target_system = BIB_ENGINE_TARGET_LINUX; facts.target_processor = BIB_ENGINE_CPU_X86_64;
#else
    throw std::runtime_error("editor driver fixture requires a supported native 64-bit target");
#endif
    facts.pointer_bits = sizeof(void*) * 8;
    facts.lifetime = BIB_ENGINE_LIFETIME_PROCESS; facts.maximum_starts = 1;
    facts.viewport_width = 800; facts.viewport_height = 600;
    facts.provider_capabilities = editor::kProviderCapabilities;
    facts.surface_capabilities = editor::kSurfaceCapabilities;
    facts.surface_protocol_version = BIB_ENGINE_EDITOR_SURFACE_PROTOCOL_VERSION;
    facts.editor_protocol_version = BIB_ENGINE_EDITOR_PROTOCOL_VERSION;
    facts.base_header_sha256 = engine_document::kBaseHeaderSha256;
    facts.document_header_sha256 = engine_document::kExtensionHeaderSha256;
    facts.document_contract_sha256 = engine_document::kContractSha256;
    facts.document_catalog_sha256 = engine_document::kCatalogSha256;
    facts.physical_catalog_sha256 = engine_document::kPhysicalCatalogSha256;
    facts.editor_header_sha256 = editor::kHeaderSha256;
    facts.contract_sha256 = editor::kContractSha256;
    facts.catalog_sha256 = editor::kCatalogSha256; facts.schema_sha256 = editor::kSchema;
    // Matching synthetic pins are not retained artifact or runtime facts.
    facts.build_sha256.fill(0x51); facts.source_recipe_sha256.fill(0x73);
    facts.queries = editor::kQueries; facts.commands = editor::kCommands;
    facts.query_count = 2; facts.command_count = 7;
    return facts;
}
using NativeHandler = std::function<ServiceReply(std::uint32_t, Span, std::span<std::uint8_t>)>;
std::shared_ptr<EngineOwner> owner_for(editor::EngineEditorProfileFacts facts, NativeHandler handler = {}) {
    EngineOwnerConfiguration config;
    config.worker_epoch = UINT64_C(0x8000000000000017);
    config.abandon_closed_document_outcomes = true;
    config.editor_profile = std::move(facts);
    auto payload = package();
    if (handler) {
        payload.services = {std::string(service_name)};
        config.native_services.push_back({{std::string(service_name), 1, 0, SchemaId{1}, 4}, std::move(handler)});
    }
    return std::make_shared<EngineOwner>(std::move(payload), std::move(config));
}
Bytes discover_service() {
    const auto major = encode_u32(1), minor = encode_u32(0);
    const std::array<FieldView, 4> fields{{
        {1, FieldType::utf8, true, {reinterpret_cast<const std::uint8_t*>(service_name.data()), service_name.size()}},
        {2, FieldType::u32, true, major}, {3, FieldType::u32, true, minor}, {4, FieldType::u32, true, minor}}};
    Bytes result; check(encode_record(fields, result) == CodecStatus::ok, "service discovery did not encode"); return result;
}

class TerminalPublicationProbe {
    const std::shared_ptr<EngineOwner> idle_ = owner_for(profile());
public:
    TerminalPublicationProbe() {
        const auto positive = owner_for(profile());
        check(configure(*positive) == FOUNDATION_ENGINE_OK && positive->configured(),
            "terminal admission probe has no usable pre-failure Owner control");
        positive->close();
    }
    void verify() const {
        check(configure(*idle_) == FOUNDATION_ENGINE_CLOSED && !idle_->configured(),
            "terminal Driver did not close a pre-existing idle editor Owner admission");
        bool refused = false;
        try { (void)owner_for(profile()); } catch (const std::exception&) { refused = true; }
        check(refused, "terminal Driver admitted a fresh enabled editor Owner");
    }
private:
    static std::uint32_t configure(EngineOwner& owner) {
        const auto identity = owner.identity();
        std::array<std::uint8_t, FOUNDATION_ENGINE_HEADER_BYTES> request{};
        std::copy_n("FKB1", 4, request.begin()); put(request, 4, FOUNDATION_ENGINE_RECORD_VERSION, 2);
        put(request, 6, FOUNDATION_ENGINE_CONFIGURE, 2); put(request, 8, request.size(), 4);
        put(request, 16, identity.worker_epoch, 8); put(request, 24, identity.application_instance, 8);
        put(request, 32, identity.document_sequence, 8); put(request, 40, identity.service_generation, 8);
        std::array<std::uint8_t, FOUNDATION_ENGINE_RECEIPT_BYTES> reply{};
        check(owner.dispatch(FOUNDATION_ENGINE_CONFIGURE, request, reply) == static_cast<std::int32_t>(reply.size()) &&
            get(reply, 6, 2) == (FOUNDATION_ENGINE_CONFIGURE | FOUNDATION_ENGINE_REPLY_KIND) &&
            get(reply, 8, 4) == reply.size(), "real Owner did not return a complete CONFIGURE receipt");
        return static_cast<std::uint32_t>(get(reply, FOUNDATION_ENGINE_HEADER_BYTES, 4));
    }
};

struct Fixture;
Fixture* active{};
enum class Behavior { ordinary, rejected, rejected_preentry, success_noenter,
    unknown_noenter, negative_unknown_noenter, unknown_status, unknown_zero, unknown_opaque, unknown_disposition, semantic_unknown, throw_entered, unbalanced };
struct Fixture {
    using QueryHandler = std::function<std::int32_t(const BibEngineQueryV1*, BibEngineReplyBufferV1*, BibEngineQueryResultV1*)>;
    using CommandHandler = std::function<std::int32_t(const BibEngineCommandV1*, BibEngineReplyBufferV1*, BibEngineCommandResultV1*)>;
    std::shared_ptr<EngineOwner> owner;
    NativeEngineDriver* driver{};
    BibEngineProviderV1 table{};
    NativeEngineExpectation expected{};
    BibEngineHostV1 host{};
    BibEngineDocumentV1 document{instance, first_document, 0};
    Clock::time_point now{1000s};
    std::vector<EngineEditorWork> submitted;
    std::vector<std::uint32_t> operations;
    std::vector<std::uint64_t> sequences;
    std::vector<BibEngineDocumentV1> command_targets;
    Bytes last_response;
    Behavior query_behavior{Behavior::ordinary};
    bool query_available{true}, malformed_query_buffer{}, wrong_query_target{}, wrong_query_revision{}, wrong_query_document{};
    Behavior command_behavior{Behavior::ordinary};
    bool malformed_command_buffer{}, wrong_command_target{}, wrong_command_sequence{}, malformed_command_reply{}, navigate_on_command{}, wrong_retired_material{};
    std::optional<native::NativeRetireMaterial> retirement;
    native::Identity retirement_identity;
    EngineEditorTarget retirement_target;
    QueryHandler query_handler;
    CommandHandler command_handler;
    unsigned starts{}, advances{}, provider_calls{}, queries{}, commands{}, physical_commands{}, disposals{}, enters{}, leaves{};
    unsigned native_effects{}, deliveries{}, service_acks{};
    std::uint64_t service_handle{}, service_pending{}, submit_service_sequence{}, pending_ack{};
    bool service_mode{}, navigate_on_advance{};
    bool inside_provider{}, context_committing{}, context_committed{};

    explicit Fixture(bool services = false) : service_mode(services) {
        check(!active, "one fixture per fresh process"); active = this;
        expected.editor_profile = profile();
        const auto& facts = expected.editor_profile;
        expected.target_system = facts.target_system; expected.target_processor = facts.target_processor;
        expected.pointer_bits = facts.pointer_bits; expected.contract_header_sha256 = facts.contract_sha256;
        expected.build_identity_sha256 = facts.build_sha256; expected.source_recipe_sha256 = facts.source_recipe_sha256;
        table.size = sizeof(table); table.abi_major = 1; table.abi_minor = 1;
        auto& build = table.build;
        build.size = sizeof(build); build.layout_revision = BIB_ENGINE_LAYOUT_V1;
        build.target_system = facts.target_system; build.target_processor = facts.target_processor;
        build.pointer_bits = facts.pointer_bits; build.lifetime = BIB_ENGINE_LIFETIME_PROCESS; build.maximum_starts = 1;
        build.fixed_viewport_width = 800; build.fixed_viewport_height = 600;
        build.capabilities = facts.provider_capabilities;
        std::copy(facts.contract_sha256.begin(), facts.contract_sha256.end(), build.contract_header_sha256);
        std::copy(facts.build_sha256.begin(), facts.build_sha256.end(), build.build_identity_sha256);
        std::copy(facts.source_recipe_sha256.begin(), facts.source_recipe_sha256.end(), build.source_recipe_sha256);
        table.limits = options().limits;
        table.start = start; table.advance = advance; table.current_document = current;
        table.query = query; table.command = command; table.deliver_services = deliver;
        table.collect_service_ack = collect; table.dispose_retired_service_document = dispose;
        NativeHandler handler;
        if (services) handler = [this](std::uint32_t operation, Span input, std::span<std::uint8_t> output) -> ServiceReply {
            check(!inside_provider && !owner->callback_depth() && operation == 1 && input.size() == 4 &&
                get(input, 0, 4) == 41 && output.size() >= 4, "native service entered early or lost exact request bytes");
            ++native_effects; const auto value = encode_u32(42); std::copy(value.begin(), value.end(), output.begin());
            return {ServiceStatus::ok, 4};
        };
        owner = owner_for(facts, std::move(handler));
    }
    static NativeEngineOptions options() {
        NativeEngineOptions result;
        result.limits.maximum_command_bytes = BIB_ENGINE_EDITOR_MAX_WIRE_BYTES;
        result.limits.maximum_query_bytes = BIB_ENGINE_EDITOR_MAX_QUERY_BYTES;
        result.limits.maximum_reply_bytes = BIB_ENGINE_EDITOR_REPLY_CAPACITY;
        result.maximum_steps_per_tick = 8;
        return result;
    }
    void bind() { driver = &NativeEngineDriver::bind_once(NativeEngineProvider::checked(table, expected), owner, options()); }
    void start_ready() {
        bind(); driver->start_once(now);
        check(driver->state() == NativeEngineState::ready && starts == 1 && owner->editor_enabled() &&
            owner->editor_profile() == expected.editor_profile && !owner->has_module(),
            "editor startup did not use the exact real web-only Owner");
        check(owner->document_profile() == engine_document::EngineDocumentProfileFacts{},
            "editor selection silently populated frozen document facts");
        tick(); healthy();
    }
    void healthy() const {
        check(driver && driver->state() == NativeEngineState::ready && !owner->callback_depth() && !inside_provider,
            "balanced fixture unexpectedly lost Driver/Owner readiness");
    }
    void tick() { driver->tick(now += 1ms); }
    template<class Predicate> void until(Predicate done, const char* message) {
        for (unsigned index = 0; index < 16 && !done(); ++index) tick();
        check(done(), message);
    }
    template<class Function> std::int32_t turn(Function function) {
        ++provider_calls;
        check(!inside_provider && !owner->callback_depth(), "provider entered recursively or outside complete TURN boundary");
        inside_provider = true;
        check(host.enter_engine(host.context) == FOUNDATION_APPENDED_SERVICE_OK, "real Owner rejected provider entry");
        ++enters; check(owner->callback_depth() == 1, "real Owner TURN was not held");
        // Deliberate unwind is left uncertain: never synthesize Host LEAVE.
        const auto result = function();
        host.leave_engine(host.context); ++leaves;
        check(owner->callback_depth() == 1, "Host LEAVE prematurely released outer provider-call barrier");
        inside_provider = false;
        return result;
    }
    std::int32_t response_turn(Behavior behavior, const std::function<void()>& fill) {
        if (behavior == Behavior::rejected_preentry || behavior == Behavior::success_noenter ||
            behavior == Behavior::unknown_noenter || behavior == Behavior::negative_unknown_noenter) {
            ++provider_calls;
            check(!inside_provider && !owner->callback_depth(), "pre-entry fixture entered recursively");
            if (behavior == Behavior::rejected_preentry || behavior == Behavior::negative_unknown_noenter) return BIB_ENGINE_STALE;
            if (behavior == Behavior::unknown_noenter) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
            fill(); return BIB_ENGINE_OK;
        }
        if (behavior == Behavior::unbalanced) {
            ++provider_calls; check(!inside_provider && !owner->callback_depth(), "unbalanced fixture entered recursively");
            inside_provider = true;
            check(host.enter_engine(host.context) == FOUNDATION_APPENDED_SERVICE_OK, "unbalanced fixture entry rejected");
            ++enters; fill(); inside_provider = false; return BIB_ENGINE_OK;
        }
        return turn([&] {
            if (behavior == Behavior::throw_entered) { inside_provider = false; throw std::runtime_error("deliberate native unwind"); }
            if (behavior == Behavior::rejected) return BIB_ENGINE_STALE;
            if (behavior == Behavior::unknown_status || behavior == Behavior::unknown_zero) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
            if (behavior == Behavior::unknown_opaque) { fill(); return BIB_ENGINE_PROCESS_EXIT_REQUIRED; }
            fill(); return BIB_ENGINE_OK;
        });
    }
    void begin_document() {
        BibEngineResourceEpochV1 epoch{}; epoch.size = sizeof(epoch);
        check(!document.service_generation && host.begin_resource_epoch(host.context, &document, &epoch) == BIB_ENGINE_OK &&
            epoch.resource_epoch && epoch.context && epoch.resolve && epoch.release, "prospective resource epoch was not bound");
        document.service_generation = host.begin_service_document(host.context, &document);
        check(document.service_generation && target(document, owner->identity().worker_epoch) == target(owner->identity()),
            "service document did not retain full native identity");
    }
    EngineEditorAdmission stage(EngineEditorWork value) {
        submitted.push_back(value);
        const auto admission = owner->stage_editor_work(std::move(value));
        check(admission.code == EngineEditorAdmissionCode::admitted && admission.ticket, "valid real-Owner editor work rejected");
        return admission;
    }
    EngineEditorWork next_query() {
        commit_context();
        const auto sequence = owner->reserve_editor_sequence(); check(bool(sequence), "editor sequence unavailable");
        return query_work(target(owner->identity()), *sequence);
    }
    EngineEditorWork next_observation() {
        if (!retirement) acquire_retirement();
        const auto sequence = owner->reserve_editor_sequence(); check(bool(sequence), "editor sequence unavailable");
        return observation_work(target(owner->identity()), *sequence);
    }
    void acquire_retirement() {
        respond_to_queries();
        const auto admission = stage(next_query()); const auto completion = complete(admission);
        codec::ProjectionReply reply;
        check(codec::decode_projection_reply(completion->bytes, reply) && reply.projection && reply.projection->retire,
            "revocation fixture has no actual checked provider retirement material");
        retirement = reply.projection->retire; retirement_identity = reply.projection->identity; retirement_target = completion->target;
        check(owner->consume_editor_outcome(admission.ticket), "material acquisition result did not collect");
    }
    EngineEditorWork next_revocation() {
        check(retirement.has_value(), "revocation fixture has no observed retirement material");
        const auto sequence = owner->reserve_editor_sequence(); check(bool(sequence), "revocation sequence unavailable");
        return revocation_work(retirement_target, *sequence, *retirement, retirement_identity);
    }
    void commit_context(bool retire = false) {
        if (context_committed && !retire) return;
        const auto context = surface_identity(target(owner->identity())).context;
        Bytes focus;
        check(input::encode_focus(retire ? input::Focus{2, 0, 0, 1, 0, context} : input::Focus{1, 0, 0, 0, context, 0}, focus) == input::Status::ok,
            "editor prerequisite focus did not encode");
        const auto ticket = owner->stage_command(owner->identity(), context, 3, input::kFocusSchema, std::move(focus), true);
        check(bool(ticket), "editor prerequisite focus was not admitted through the real Owner");
        context_committing = true;
        until([&] { const auto result = owner->command_outcome(*ticket);
            return result && result->status != EngineInputCommandStatus::pending; }, "editor prerequisite focus did not finish");
        context_committing = false;
        const auto result = owner->command_outcome(*ticket);
        check(result && result->status == EngineInputCommandStatus::consumed && result->handled,
            "editor prerequisite focus was not actually committed");
        context_committed = !retire;
    }
    void queue_service(std::uint64_t sequence) {
        check(service_mode && (sequence == 1 || (sequence == 2 && service_handle)), "service fixture lacks an observed discovery handle");
        submit_service_sequence = sequence;
        driver->request_advance(); tick();
        check(!submit_service_sequence, "service request did not run inside a complete provider advance");
    }
    void submit_service() {
        if (!submit_service_sequence) return;
        Envelope envelope;
        envelope.generation = document.service_generation; envelope.sequence = submit_service_sequence;
        envelope.interface_handle = submit_service_sequence == 1 ? 0 : service_handle;
        envelope.operation = submit_service_sequence == 1 ? FOUNDATION_APPENDED_CONTROL_DISCOVER : 1;
        const auto payload = submit_service_sequence == 1 ? discover_service() : encode_u32(41);
        Bytes encoded; check(encode_envelope(envelope, payload, encoded) == CodecStatus::ok, "queued service request did not encode");
        const BibEngineBytesV1 bytes{encoded.data(), static_cast<std::uint32_t>(encoded.size()), 0};
        check(host.submit_service(host.context, document.service_generation, &bytes, 1) == FOUNDATION_APPENDED_SERVICE_OK,
            "actual Host refused queued service request");
        service_pending = submit_service_sequence; submit_service_sequence = 0;
    }
    EngineNativeEffect wait_effect() {
        until([&] { return owner->native_effect().has_value(); }, "queued service did not produce an actual Owner native-effect gate");
        const auto effect = *owner->native_effect();
        check(!effect.entered && !native_effects && !owner->callback_depth(), "native service ran before its publication/retirement gate");
        return effect;
    }
    void discover() {
        queue_service(1); const auto effect = wait_effect();
        const auto id = owner->identity();
        check(owner->acknowledge_document_native_effect(effect.ticket,
            {id.worker_epoch, id.application_instance, id.document_sequence, id.service_generation}, 1),
            "initial service discovery without input/editor debt could not acknowledge its gate");
        until([&] { return service_handle && !service_pending && service_acks; }, "native service discovery/ACK did not settle");
        for (unsigned i = 0; i < 3; ++i) tick();
        healthy();
    }
    void respond_to_queries() {
        query_handler = [this](const BibEngineQueryV1* request, BibEngineReplyBufferV1* buffer, BibEngineQueryResultV1* result) {
            check(request && request->size == sizeof(*request) && request->kind == BIB_ENGINE_QUERY_EDITOR_PROJECTION_V1 &&
                request->payload.data && !request->payload.reserved && result && result->size == sizeof(*result),
                "query C record mismatch");
            const Span payload(request->payload.data, request->payload.length);
            codec::ProjectionQuery query;
            check(codec::decode_projection_query(payload, query), "provider received malformed binary query");
            const auto& original = submitted_work(query.target.request_sequence);
            check(original.kind == EngineEditorWorkKind::projection_query && payload.size() == original.payload.size() &&
                std::equal(payload.begin(), payload.end(), original.payload.begin()) &&
                query.target == wire_target(original.target, original.request_sequence) &&
                target(request->expected, original.target.worker_epoch) == original.target &&
                std::equal(editor::kSchema.begin(), editor::kSchema.end(), request->schema_sha256) &&
                buffer && buffer->capacity == editor::kReplyCapacity,
                "query lost owned request, full target/sequence, schema or complete reply capacity");
            operations.push_back(request->kind); sequences.push_back(query.target.request_sequence);
            return response_turn(query_behavior, [&] {
                if (query_behavior == Behavior::unknown_opaque) {
                    const Bytes bytes(52, 0xd7); copy_reply(buffer, bytes);
                    *result = {sizeof(*result), static_cast<std::uint32_t>(bytes.size()), request->expected, observation_revision};
                    return;
                }
                auto reply = projection_reply(query, query_available);
                if (wrong_query_target) ++reply.target.request_sequence;
                Bytes bytes; check(codec::encode_projection_reply(reply, bytes), "fixture projection reply is not canonical binary");
                copy_reply(buffer, bytes);
                *result = {sizeof(*result), static_cast<std::uint32_t>(bytes.size()), request->expected,
                    wrong_query_revision ? observation_revision + 1 : observation_revision};
                if (wrong_query_document) ++result->document.document_sequence;
                if (malformed_query_buffer) buffer->bytes = nullptr; // Never dereference the tampered pointer.
            });
        };
    }
    void respond_to_commands() {
        command_handler = [this](const BibEngineCommandV1* request, BibEngineReplyBufferV1* buffer, BibEngineCommandResultV1* result) {
            const bool revoke = request->operation == BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1;
            check((request->operation == BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1 || revoke) && request->payload.data &&
                result && result->size == sizeof(*result), "editor command C record mismatch");
            const auto& original = submitted_work(request->request_sequence);
            const Span payload(request->payload.data, request->payload.length);
            codec::NativeRequestEnvelope decoded;
            codec::RevocationEnvelope revoked;
            check((revoke ? (codec::decode_revocation(payload, revoked) && original.kind == EngineEditorWorkKind::revoke &&
                    revoked.target == wire_target(original.target, original.request_sequence) && retirement &&
                    revoked.request.material == *retirement && revoked.request.identity == retirement_identity) :
                    (codec::decode_native_request(payload, decoded) && original.kind == EngineEditorWorkKind::observation &&
                    decoded.target == wire_target(original.target, original.request_sequence))) &&
                target(request->expected, original.target.worker_epoch) == original.target && payload.size() == original.payload.size() &&
                std::equal(payload.begin(), payload.end(), original.payload.begin()) &&
                std::equal(editor::kSchema.begin(), editor::kSchema.end(), request->schema_sha256) &&
                buffer && buffer->capacity == editor::kReplyCapacity,
                "editor command lost owned request, full target/sequence/material, schema or complete reply capacity");
            *result = {sizeof(*result), 0, request->request_sequence, 0, 0};
            if (command_behavior == Behavior::unknown_status || command_behavior == Behavior::negative_unknown_noenter)
                result->disposition = 2;
            return response_turn(command_behavior, [&] {
                auto reply = revoke ? revocation_reply(revoked) : observation_reply(decoded);
                if (wrong_command_target) ++reply.target.request_sequence;
                if (wrong_retired_material && reply.result.retired) ++reply.result.retired->token;
                if (command_behavior == Behavior::semantic_unknown) reply.result.outcome = native::Outcome::unknown;
                Bytes bytes;
                if (command_behavior == Behavior::unknown_disposition) bytes.assign(52, 0xd7);
                else check(codec::encode_native_result(reply, bytes), "fixture observation result is not canonical binary");
                if (malformed_command_reply) bytes.push_back(0); // Complete record length deliberately stays unchanged.
                copy_reply(buffer, bytes);
                *result = {sizeof(*result), command_behavior == Behavior::unknown_disposition ? 2U : 1U,
                    request->request_sequence + (wrong_command_sequence ? 1 : 0), static_cast<std::uint32_t>(bytes.size()), 1};
                if (malformed_command_buffer) buffer->bytes = nullptr;
                if (navigate_on_command) {
                    navigate_on_command = false;
                    document = {instance, document.document_sequence + 1, 0};
                    begin_document(); // Actual lifecycle callback within the original command's TURN.
                }
            });
        };
    }
    std::shared_ptr<const EngineEditorCompletion> complete(EngineEditorAdmission admission) {
        until([&] { return bool(owner->editor_outcome(admission.ticket)); }, "Driver did not publish owned editor completion");
        const auto completion = owner->editor_outcome(admission.ticket);
        if (completion->kind == EngineEditorWorkKind::projection_query && completion->outcome == EngineEditorOutcome::consumed) {
            codec::ProjectionReply reply;
            check(codec::decode_projection_reply(completion->bytes, reply), "checked projection completion did not decode");
            if (reply.projection) {
                retirement = reply.projection->retire; retirement_identity = reply.projection->identity; retirement_target = completion->target;
            }
        }
        return completion;
    }
    const EngineEditorWork& submitted_work(std::uint64_t sequence) const {
        const auto found = std::find_if(submitted.begin(), submitted.end(), [=](const auto& value) {
            return value.request_sequence == sequence;
        });
        check(found != submitted.end(), "provider received an unsubmitted sequence"); return *found;
    }
    void copy_reply(BibEngineReplyBufferV1* buffer, const Bytes& bytes) {
        check(buffer && buffer->size == sizeof(*buffer) && buffer->bytes && buffer->capacity >= bytes.size(),
            "provider was not given complete owned reply capacity");
        std::copy(bytes.begin(), bytes.end(), buffer->bytes); last_response = bytes;
    }
    static std::int32_t BIB_ENGINE_CALL start(const BibEngineHostV1* callbacks, const BibEngineStartV1* config,
            BibEngineStartResultV1* result) {
        auto& fixture = *active; ++fixture.starts;
        const auto& facts = fixture.expected.editor_profile;
        check(callbacks && callbacks->size == sizeof(*callbacks) && callbacks->abi_major == facts.host_abi_major &&
            callbacks->abi_minor == facts.host_abi_minor && config && result && result->size == sizeof(*result),
            "startup C table mismatch");
        fixture.host = *callbacks;
        check(config->required_capabilities == facts.provider_capabilities && config->raster_output == 1 &&
            config->limits.maximum_reply_bytes == BIB_ENGINE_EDITOR_REPLY_CAPACITY,
            "startup changed selected editor profile/limits");
        const auto status = fixture.turn([&] { fixture.begin_document(); return BIB_ENGINE_OK; });
        *result = {sizeof(*result), BIB_ENGINE_START_READY, instance}; return status;
    }
    static std::int32_t BIB_ENGINE_CALL advance(const BibEngineAdvanceV1* request) {
        auto& fixture = *active; ++fixture.advances;
        check(request && request->application_instance == instance, "advance changed application identity");
        return fixture.turn([&] {
            if (fixture.navigate_on_advance) {
                fixture.navigate_on_advance = false; fixture.context_committed = false;
                fixture.document = {instance, fixture.document.document_sequence + 1, 0}; fixture.begin_document();
            }
            fixture.submit_service(); return BIB_ENGINE_OK;
        });
    }
    static std::int32_t BIB_ENGINE_CALL current(std::uint64_t application, BibEngineDocumentV1* result) {
        auto& fixture = *active; check(application == instance && result, "current-document identity mismatch");
        return fixture.turn([&] { *result = fixture.document; return BIB_ENGINE_OK; });
    }
    static std::int32_t BIB_ENGINE_CALL query(const BibEngineQueryV1* request, BibEngineReplyBufferV1* buffer,
            BibEngineQueryResultV1* result) {
        auto& fixture = *active; ++fixture.queries;
        check(bool(fixture.query_handler), "fixture has no checked binary query responder");
        return fixture.query_handler(request, buffer, result);
    }
    static std::int32_t BIB_ENGINE_CALL command(const BibEngineCommandV1* request, BibEngineReplyBufferV1* buffer,
            BibEngineCommandResultV1* result) {
        auto& fixture = *active;
        check(request && request->size == sizeof(*request) && request->request_sequence && !request->payload.reserved,
            "malformed provider command record");
        fixture.operations.push_back(request->operation); fixture.sequences.push_back(request->request_sequence);
        fixture.command_targets.push_back(request->expected);
        if (request->operation == BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1 || request->operation == BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1)
            ++fixture.commands;
        else ++fixture.physical_commands;
        if (fixture.context_committing) {
            check(request->operation == 3 && request->payload.length == input::kFocusBytes && buffer && buffer->capacity == 16 &&
                target(request->expected, fixture.owner->identity().worker_epoch) == target(fixture.owner->identity()) &&
                std::equal(input::kFocusSchema.begin(), input::kFocusSchema.end(), request->schema_sha256),
                "committed editor context did not use exact physical focus authority");
            return fixture.turn([&] { *result = {sizeof(*result), 1, request->request_sequence, 0, 1}; return BIB_ENGINE_OK; });
        }
        check(bool(fixture.command_handler), "fixture has no checked binary command responder");
        return fixture.command_handler(request, buffer, result);
    }
    static std::int32_t BIB_ENGINE_CALL deliver(const BibEngineDocumentV1* target_document, const BibEngineBytesV1* input) {
        auto& fixture = *active;
        check(fixture.service_mode, "editor-only fixture unexpectedly delivered a service result");
        ++fixture.deliveries;
        return fixture.turn([&] {
            check(target_document && target(target_document[0], fixture.owner->identity().worker_epoch) == target(fixture.owner->identity()) &&
                input && input->data && !input->reserved, "service delivery lost its original document");
            Envelope envelope; Span payload;
            check(decode_envelope({input->data, input->length}, envelope, payload) == CodecStatus::ok &&
                envelope.kind == FOUNDATION_APPENDED_MESSAGE_COMPLETION && !envelope.service_status &&
                envelope.generation == target_document->service_generation && envelope.sequence == fixture.service_pending,
                "service delivery changed its exact original completion");
            if (envelope.sequence == 1) {
                std::vector<FieldView> fields;
                check(decode_record(payload, fields) == CodecStatus::ok && fields.size() == 6 &&
                    read_u64(fields[0], fixture.service_handle) && fixture.service_handle,
                    "actual discovery did not supply an opaque service handle");
            } else check(payload.size() == 4 && get(payload, 0, 4) == 42 && fixture.native_effects == 1,
                "native service effect did not produce its checked completion");
            fixture.pending_ack = envelope.sequence; return BIB_ENGINE_OK;
        });
    }
    static std::uint32_t BIB_ENGINE_CALL collect(const BibEngineDocumentV1* target_document) {
        auto& fixture = *active;
        check(fixture.service_mode && target_document, "editor-only fixture unexpectedly collected service ACK");
        ++fixture.provider_calls;
        check(!fixture.inside_provider && fixture.host.enter_engine(fixture.host.context) == FOUNDATION_APPENDED_SERVICE_OK,
            "native service collector could not enter its real logical Host scope");
        ++fixture.enters;
        const auto status = fixture.pending_ack ? fixture.host.stage_service_ack(fixture.host.context,
            target_document->service_generation, fixture.pending_ack) : FOUNDATION_APPENDED_SERVICE_UNAVAILABLE;
        if (fixture.pending_ack && status == FOUNDATION_APPENDED_SERVICE_OK) {
            fixture.pending_ack = fixture.service_pending = 0; ++fixture.service_acks;
        }
        fixture.host.leave_engine(fixture.host.context); ++fixture.leaves;
        return status;
    }
    static std::int32_t BIB_ENGINE_CALL dispose(std::uint64_t application, std::uint64_t generation) {
        auto& fixture = *active; ++fixture.disposals;
        return fixture.turn([&] {
            check(application == instance && generation, "retired disposal lost identity"); return BIB_ENGINE_OK;
        });
    }
};

void startup(Fixture& fixture) {
    fixture.start_ready();
    check(!fixture.queries && !fixture.commands && fixture.enters == fixture.leaves,
        "startup fabricated editor work or lost complete native TURN balance");
}
void reservation(Fixture& fixture) {
    fixture.start_ready();
    const auto first = fixture.owner->reserve_editor_sequence();
    check(bool(first), "editor ordinary sequence unavailable");
    check(!fixture.owner->reserve_editor_sequence(), "held editor reservation was duplicated");
    const auto advances = fixture.advances;
    fixture.driver->request_advance(); fixture.tick();
    check(fixture.advances == advances && fixture.driver->state() == NativeEngineState::ready,
        "held editor reservation did not suppress provider advance");
    check(!fixture.owner->cancel_editor_sequence(*first + 1) && fixture.owner->cancel_editor_sequence(*first),
        "editor reservation cancellation lost exact sequence authority");
    fixture.until([&] { return fixture.advances > advances; }, "cancelled editor reservation lost queued advance");
    const auto second = fixture.owner->reserve_editor_sequence();
    check(second && *second > *first && fixture.owner->cancel_editor_sequence(*second),
        "cancelled editor sequence was replayed or rewound");
    fixture.healthy();
}
void metadata(Fixture& fixture) {
    const auto reject = [&](const std::function<void(BibEngineProviderV1&, NativeEngineExpectation&)>& mutate) {
        auto table = fixture.table; auto expected = fixture.expected; mutate(table, expected);
        bool refused = false;
        try { (void)NativeEngineProvider::checked(table, expected); } catch (const std::invalid_argument&) { refused = true; }
        check(refused && !fixture.starts && !fixture.provider_calls && !fixture.owner->configured(),
            "invalid editor metadata was accepted or performed effects");
    };
    reject([](auto& table, auto&) { table.abi_minor = 0; });
    reject([](auto& table, auto&) { table.build.capabilities = engine_document::kPixelCapabilities; });
    reject([](auto& table, auto&) { table.build.capabilities = engine_document::kPhysicalCapabilities; });
    reject([](auto& table, auto&) { table.build.capabilities |= UINT64_C(1) << 30; });
    reject([](auto& table, auto&) { table.limits.maximum_command_bytes = BIB_ENGINE_EDITOR_MAX_WIRE_BYTES - 1; });
    reject([](auto& table, auto&) { table.limits.maximum_query_bytes = editor::kQueryRequestMaximum - 1; });
    reject([](auto& table, auto&) { table.limits.maximum_reply_bytes = editor::kReplyCapacity - 1; });
    reject([](auto&, auto& expected) { expected.editor_profile = {}; });
    reject([](auto&, auto& expected) { expected.editor_profile.editor_header_sha256[0] ^= 1; });
    reject([](auto&, auto& expected) { expected.editor_profile.catalog_sha256[0] ^= 1; });
    reject([](auto&, auto& expected) { expected.editor_profile.schema_sha256[0] ^= 1; });
    reject([](auto&, auto& expected) { expected.editor_profile.host_abi_minor ^= 1; });
    reject([](auto&, auto& expected) { expected.editor_profile.queries[1].operation = 2; });
    reject([](auto&, auto& expected) { expected.editor_profile.commands[6].required_reply_capacity = 16; });
    reject([](auto&, auto& expected) { expected.document_profile.enabled = true; });
    reject([](auto& table, auto&) { table.query = nullptr; });
    (void)NativeEngineProvider::checked(fixture.table, fixture.expected);
    check(!fixture.starts && !fixture.provider_calls && !fixture.owner->configured(), "metadata inspection performed native effects");
}
void admission(Fixture& fixture) {
    const auto reject = [&](std::shared_ptr<EngineOwner> owner, NativeEngineOptions options) {
        bool refused = false;
        try { (void)NativeEngineDriver::bind_once(NativeEngineProvider::checked(fixture.table, fixture.expected), owner, options); }
        catch (const std::invalid_argument&) { refused = true; }
        check(refused && !owner->configured() && !fixture.starts && !fixture.provider_calls,
            "mismatched editor Owner/profile/selected limits reached binding effects");
    };
    reject(owner_for({}), Fixture::options());
    auto different = fixture.expected.editor_profile; different.build_sha256[0] ^= 1;
    reject(owner_for(different), Fixture::options());
    reject(fixture.owner, NativeEngineOptions{}); // No implicit widening from legacy 64KiB options.
    auto options = Fixture::options(); options.limits.maximum_command_bytes = BIB_ENGINE_EDITOR_MAX_WIRE_BYTES - 1;
    reject(fixture.owner, options);
    options = Fixture::options(); options.limits.maximum_query_bytes = editor::kQueryRequestMaximum - 1;
    reject(fixture.owner, options);
    options = Fixture::options(); options.limits.maximum_reply_bytes = editor::kReplyCapacity - 1;
    reject(fixture.owner, options);
    fixture.start_ready();
}
void owned_query(Fixture& fixture, bool available) {
    fixture.start_ready(); fixture.respond_to_queries(); fixture.query_available = available;
    auto value = fixture.next_query(); const auto original = value;
    const auto admission = fixture.stage(value); std::fill(value.payload.begin(), value.payload.end(), 0xee);
    const auto completion = fixture.complete(admission);
    codec::ProjectionReply decoded;
    check(fixture.queries == 1 && !fixture.commands && completion->kind == EngineEditorWorkKind::projection_query &&
        completion->outcome == EngineEditorOutcome::consumed && completion->target == original.target &&
        completion->ticket == admission.ticket && completion->transfer && completion->request_sequence == original.request_sequence &&
        !completion->provider_status && !completion->provider_disposition && !completion->handled &&
        completion->semantic_revision == observation_revision && codec::decode_projection_reply(completion->bytes, decoded) &&
        decoded.target == wire_target(original.target, original.request_sequence) &&
        decoded.observation_revision == completion->semantic_revision && decoded.projection.has_value() == available,
        "query completion lost owned binary bytes, exact target/sequence or actual observation revision");
    if (available) check(completion->bytes.size() > 65536 && decoded.projection->editor_revision != completion->semantic_revision,
        "large projection was truncated or its editor revision replaced observation revision");
    const auto original_bytes = completion->bytes;
    std::fill(fixture.last_response.begin(), fixture.last_response.end(), 0);
    const auto calls = fixture.provider_calls, advances = fixture.advances;
    for (unsigned index = 0; index < 3; ++index) { fixture.driver->request_advance(); fixture.tick(); }
    check(completion == fixture.owner->editor_outcome(admission.ticket) && completion->bytes == original_bytes &&
        fixture.provider_calls == calls && fixture.advances == advances && !fixture.owner->reserve_editor_sequence(),
        "retained query redelivery replayed provider, lost owned bytes or released its work barrier");
    check(fixture.owner->consume_editor_outcome(admission.ticket), "checked editor query completion could not collect locally");
    fixture.until([&] { return fixture.advances > advances; }, "collected editor query lost pending ordinary advance");
    fixture.healthy();
}
void rejected_query(Fixture& fixture) {
    fixture.start_ready(); fixture.respond_to_queries(); fixture.query_behavior = Behavior::rejected_preentry;
    const auto original = fixture.next_query(); const auto admission = fixture.stage(original);
    const auto calls = fixture.provider_calls, enters = fixture.enters, leaves = fixture.leaves;
    const auto completion = fixture.complete(admission);
    check(completion->outcome == EngineEditorOutcome::rejected && completion->target == original.target &&
        completion->request_sequence == original.request_sequence && completion->provider_status == BIB_ENGINE_STALE &&
        !completion->provider_disposition && !completion->handled && !completion->semantic_revision && completion->bytes.empty() &&
        fixture.provider_calls == calls + 1 && fixture.enters == enters && fixture.leaves == leaves,
        "known editor pre-entry rejection fabricated a TURN or lost its exact owned result");
    for (unsigned index = 0; index < 3; ++index) fixture.tick();
    check(fixture.provider_calls == calls + 1 && completion == fixture.owner->editor_outcome(admission.ticket),
        "retained known editor rejection replayed its burned claim");
    check(fixture.owner->consume_editor_outcome(admission.ticket), "known editor rejection could not collect");
    const auto replay = fixture.owner->stage_editor_work(original);
    check(replay.code != EngineEditorAdmissionCode::admitted && !replay.ticket,
        "known pre-entry rejection rewound its claimed ordinary sequence");
    fixture.query_behavior = Behavior::ordinary;
    const auto following = fixture.next_query(); const auto following_admission = fixture.stage(following);
    const auto result = fixture.complete(following_admission);
    check(following.request_sequence > original.request_sequence && result->outcome == EngineEditorOutcome::consumed &&
        fixture.enters == enters + 1 && fixture.leaves == leaves + 1,
        "collected pre-entry rejection prevented a later balanced fresh editor query");
    check(fixture.owner->consume_editor_outcome(following_admission.ticket), "following editor query could not collect");
    fixture.healthy();
}
void invalid_query(Fixture& fixture, Behavior behavior, std::string_view corruption = {}) {
    fixture.start_ready(); fixture.respond_to_queries(); fixture.query_behavior = behavior;
    fixture.malformed_query_buffer = corruption == "buffer"; fixture.wrong_query_target = corruption == "target";
    fixture.wrong_query_revision = corruption == "revision"; fixture.wrong_query_document = corruption == "document";
    const TerminalPublicationProbe terminal_publication;
    const auto admission = fixture.stage(fixture.next_query());
    const auto calls = fixture.provider_calls, leaves = fixture.leaves;
    fixture.tick();
    check(fixture.queries == 1 && fixture.provider_calls == calls + 1 &&
        fixture.driver->state() == NativeEngineState::process_exit_required && !fixture.owner->editor_outcome(admission.ticket),
        "invalid claimed editor query fabricated a completion or failed to terminate");
    if (behavior == Behavior::throw_entered || behavior == Behavior::unbalanced)
        check(fixture.owner->callback_depth() == 1 && fixture.leaves == leaves,
            "uncertain editor query fabricated Host LEAVE");
    else check(!fixture.owner->callback_depth(), "balanced/no-entry invalid query retained an invented TURN");
    const auto stopped_calls = fixture.provider_calls;
    for (unsigned index = 0; index < 3; ++index) { fixture.driver->request_advance(); fixture.tick(); }
    fixture.driver->request_close(); fixture.tick();
    check(fixture.provider_calls == stopped_calls && !fixture.owner->editor_outcome(admission.ticket) &&
        !fixture.owner->reserve_editor_sequence(), "terminal editor query replayed, settled synthetically or reopened admission");
    terminal_publication.verify();
}
void unknown_query(Fixture& fixture, bool opaque = false) {
    fixture.start_ready(); fixture.respond_to_queries(); fixture.query_behavior = opaque ? Behavior::unknown_opaque : Behavior::unknown_status;
    const TerminalPublicationProbe terminal_publication;
    const auto original = fixture.next_query(); const auto admission = fixture.stage(original);
    const auto completion = fixture.complete(admission);
    check(completion->outcome == EngineEditorOutcome::unknown && completion->target == original.target &&
        completion->request_sequence == original.request_sequence && completion->provider_status == BIB_ENGINE_PROCESS_EXIT_REQUIRED &&
        completion->semantic_revision == (opaque ? observation_revision : 0) &&
        completion->bytes == (opaque ? Bytes(52, 0xd7) : Bytes{}) && fixture.enters == fixture.leaves &&
        !fixture.owner->callback_depth() && fixture.driver->state() == NativeEngineState::process_exit_required,
        "naturally returned query unknown lost owned evidence or complete TURN before terminal state");
    const auto calls = fixture.provider_calls;
    for (unsigned index = 0; index < 3; ++index) { fixture.driver->request_advance(); fixture.tick(); }
    check(fixture.provider_calls == calls && completion == fixture.owner->editor_outcome(admission.ticket) &&
        !fixture.owner->reserve_editor_sequence(), "query unknown replayed provider or reopened ordinary admission");
    terminal_publication.verify();
}
void owned_observation(Fixture& fixture, bool navigate, bool revoke = false) {
    fixture.start_ready(); fixture.respond_to_commands(); fixture.navigate_on_command = navigate;
    if (revoke) fixture.acquire_retirement();
    auto value = revoke ? fixture.next_revocation() : fixture.next_observation(); const auto original = value;
    const auto admission = fixture.stage(value); std::fill(value.payload.begin(), value.payload.end(), 0xee);
    const auto enters = fixture.enters, leaves = fixture.leaves;
    const auto completion = fixture.complete(admission);
    codec::NativeResultEnvelope decoded;
    check(fixture.commands == 1 && fixture.queries == 1 && completion->kind == original.kind &&
        completion->outcome == EngineEditorOutcome::consumed && completion->target == original.target &&
        completion->ticket == admission.ticket && completion->transfer && completion->request_sequence == original.request_sequence &&
        !completion->provider_status && completion->provider_disposition == 1 && completion->handled &&
        !completion->semantic_revision && codec::decode_native_result(completion->bytes, decoded) &&
        decoded.target == wire_target(original.target, original.request_sequence) && decoded.result.outcome == native::Outcome::applied &&
        fixture.enters == enters + 1 && fixture.leaves == leaves + 1 && !fixture.owner->callback_depth(),
        "observation completion lost owned binary receipt, original target/sequence or complete TURN");
    if (revoke) check(decoded.result.retired == fixture.retirement && !decoded.result.retire,
        "revocation result lost the exact observed provider retirement material");
    if (navigate) check(fixture.owner->identity().document_sequence == original.target.document_sequence + 1 &&
        target(fixture.command_targets.front(), original.target.worker_epoch) == original.target && !fixture.disposals,
        "observation-turn navigation rewrote request authority or retired the original document before result collection");
    const auto original_bytes = completion->bytes;
    const auto calls = fixture.provider_calls, advances = fixture.advances;
    std::fill(fixture.last_response.begin(), fixture.last_response.end(), 0);
    for (unsigned index = 0; index < 3; ++index) { fixture.driver->request_advance(); fixture.tick(); }
    check(fixture.provider_calls == calls && fixture.advances == advances &&
        completion == fixture.owner->editor_outcome(admission.ticket) && completion->bytes == original_bytes &&
        !fixture.owner->reserve_editor_sequence(), "retained observation replayed effects or lost its owned immutable result barrier");
    check(fixture.owner->consume_editor_outcome(admission.ticket), "checked observation completion could not collect locally");
    const auto replay = fixture.owner->stage_editor_work(original);
    check(replay.code != EngineEditorAdmissionCode::admitted && !replay.ticket,
        "collected observation minted a second provider attempt for a burned sequence");
    fixture.healthy();
}
void rejected_observation(Fixture& fixture, bool revoke = false) {
    fixture.start_ready(); fixture.respond_to_commands(); fixture.command_behavior = Behavior::rejected_preentry;
    if (revoke) fixture.acquire_retirement();
    const auto original = revoke ? fixture.next_revocation() : fixture.next_observation(); const auto admission = fixture.stage(original);
    const auto enters = fixture.enters, leaves = fixture.leaves, calls = fixture.provider_calls;
    const auto completion = fixture.complete(admission);
    check(completion->outcome == EngineEditorOutcome::rejected && completion->target == original.target &&
        completion->request_sequence == original.request_sequence && completion->provider_status == BIB_ENGINE_STALE &&
        !completion->provider_disposition && !completion->handled && completion->bytes.empty() &&
        fixture.provider_calls == calls + 1 && fixture.enters == enters && fixture.leaves == leaves,
        "known observation pre-entry rejection fabricated a TURN or lost its exact rejected result");
    for (unsigned index = 0; index < 3; ++index) fixture.tick();
    check(fixture.provider_calls == calls + 1 && completion == fixture.owner->editor_outcome(admission.ticket),
        "known observation rejection automatically retried native work");
    check(fixture.owner->consume_editor_outcome(admission.ticket), "known observation rejection could not collect");
    const auto replay = fixture.owner->stage_editor_work(original);
    check(replay.code != EngineEditorAdmissionCode::admitted && !replay.ticket,
        "known observation rejection restored its burned claim");
    fixture.command_behavior = Behavior::ordinary;
    const auto following = revoke ? fixture.next_revocation() : fixture.next_observation(); const auto following_admission = fixture.stage(following);
    const auto result = fixture.complete(following_admission);
    check(following.request_sequence > original.request_sequence && result->outcome == EngineEditorOutcome::consumed &&
        fixture.enters == enters + 1 && fixture.leaves == leaves + 1,
        "known pre-entry rejection prevented a fresh balanced observation");
    check(fixture.owner->consume_editor_outcome(following_admission.ticket), "following observation could not collect");
    fixture.healthy();
}
void invalid_observation(Fixture& fixture, Behavior behavior, std::string_view corruption = {}, bool revoke = false) {
    fixture.start_ready(); fixture.respond_to_commands(); fixture.command_behavior = behavior;
    if (revoke) fixture.acquire_retirement();
    fixture.malformed_command_buffer = corruption == "buffer"; fixture.wrong_command_target = corruption == "target";
    fixture.wrong_command_sequence = corruption == "sequence"; fixture.malformed_command_reply = corruption == "reply";
    fixture.wrong_retired_material = corruption == "material";
    const TerminalPublicationProbe terminal_publication;
    const auto admission = fixture.stage(revoke ? fixture.next_revocation() : fixture.next_observation());
    const auto calls = fixture.provider_calls, leaves = fixture.leaves;
    fixture.tick();
    check(fixture.commands == 1 && fixture.provider_calls == calls + 1 &&
        fixture.driver->state() == NativeEngineState::process_exit_required && !fixture.owner->editor_outcome(admission.ticket),
        "invalid claimed observation fabricated a completion or failed to terminate");
    if (behavior == Behavior::throw_entered || behavior == Behavior::unbalanced)
        check(fixture.owner->callback_depth() == 1 && fixture.leaves == leaves, "uncertain observation fabricated Host LEAVE");
    else check(!fixture.owner->callback_depth(), "balanced/no-entry invalid observation retained an invented TURN");
    const auto stopped_calls = fixture.provider_calls;
    for (unsigned index = 0; index < 3; ++index) { fixture.driver->request_advance(); fixture.tick(); }
    fixture.driver->request_close(); fixture.tick();
    check(fixture.provider_calls == stopped_calls && !fixture.owner->editor_outcome(admission.ticket) &&
        !fixture.owner->reserve_editor_sequence(), "terminal observation replayed, settled synthetically or reopened admission");
    terminal_publication.verify();
}
void unknown_observation(Fixture& fixture, Behavior behavior, bool revoke = false) {
    fixture.start_ready(); fixture.respond_to_commands(); fixture.command_behavior = behavior;
    if (revoke) fixture.acquire_retirement();
    const TerminalPublicationProbe terminal_publication;
    const auto original = revoke ? fixture.next_revocation() : fixture.next_observation(); const auto admission = fixture.stage(original);
    const auto completion = fixture.complete(admission);
    check(completion->outcome == EngineEditorOutcome::unknown && completion->target == original.target &&
        completion->request_sequence == original.request_sequence &&
        completion->handled == (behavior != Behavior::unknown_status && behavior != Behavior::unknown_zero) &&
        completion->provider_status == ((behavior == Behavior::unknown_status || behavior == Behavior::unknown_zero) ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : BIB_ENGINE_OK) &&
        completion->provider_disposition == (behavior == Behavior::semantic_unknown ? 1U : behavior == Behavior::unknown_zero ? 0U : 2U) &&
        fixture.enters == fixture.leaves && !fixture.owner->callback_depth() &&
        fixture.driver->state() == NativeEngineState::process_exit_required,
        "naturally returned observation unknown lost owned evidence or complete TURN before termination");
    if (behavior == Behavior::unknown_disposition) check(completion->bytes == Bytes(52, 0xd7),
        "native disposition unknown lost bounded opaque forensic bytes");
    if (behavior == Behavior::semantic_unknown) {
        codec::NativeResultEnvelope decoded;
        check(codec::decode_native_result(completion->bytes, decoded) && decoded.result.outcome == native::Outcome::unknown &&
            decoded.target == wire_target(original.target, original.request_sequence),
            "inner semantic unknown lost its exact checked receipt");
    }
    const auto calls = fixture.provider_calls;
    for (unsigned index = 0; index < 3; ++index) { fixture.driver->request_advance(); fixture.tick(); }
    check(fixture.provider_calls == calls && completion == fixture.owner->editor_outcome(admission.ticket) &&
        !fixture.owner->reserve_editor_sequence(), "observation unknown replayed provider or reopened ordinary admission");
    terminal_publication.verify();
}
void legacy_lanes(Fixture& fixture) {
    fixture.start_ready(); fixture.respond_to_queries(); fixture.respond_to_commands();
    check(fixture.owner->document_enabled() && fixture.owner->input_enabled(),
        "editor selection omitted its existing forms or physical lane");
    const auto editor_query = fixture.query_handler;
    const auto editor_command = fixture.command_handler;
    std::vector<EngineDocumentWork> documents;
    const auto original_document = [&](std::uint64_t sequence) -> const EngineDocumentWork& {
        const auto found = std::find_if(documents.begin(), documents.end(), [=](const auto& value) {
            return value.request_sequence == sequence;
        });
        check(found != documents.end(), "provider received unsubmitted legacy document work"); return *found;
    };
    fixture.query_handler = [&](const BibEngineQueryV1* request, BibEngineReplyBufferV1* buffer, BibEngineQueryResultV1* result) {
        if (request && request->kind == BIB_ENGINE_QUERY_EDITOR_PROJECTION_V1) return editor_query(request, buffer, result);
        check(request && request->size == sizeof(*request) && request->kind == BIB_ENGINE_QUERY_DOCUMENT_FORMS_V2 &&
            request->payload.data && request->payload.length == BIB_ENGINE_DOCUMENT_V2_QUERY_BYTES && result &&
            buffer && buffer->capacity == BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY,
            "editor-selected forms query changed the legacy C catalog/capacity");
        const auto sequence = get({request->payload.data, request->payload.length}, 32, 8);
        const auto& original = original_document(sequence);
        check(target(request->expected, original.target.worker_epoch) == EngineEditorTarget{original.target.worker_epoch,
            original.target.application_instance, original.target.document_sequence, original.target.service_generation} &&
            std::equal(original.payload.begin(), original.payload.end(), request->payload.data), "legacy forms query lost original authority");
        fixture.operations.push_back(request->kind); fixture.sequences.push_back(sequence);
        return fixture.turn([&] {
            auto bytes = ndv2(original.target, sequence, 4, 48); put(bytes, 40, UINT64_C(0xf123456789abcdef), 8);
            fixture.copy_reply(buffer, bytes); *result = {sizeof(*result), static_cast<std::uint32_t>(bytes.size()), request->expected, 1};
            return BIB_ENGINE_OK;
        });
    };
    fixture.command_handler = [&](const BibEngineCommandV1* request, BibEngineReplyBufferV1* buffer, BibEngineCommandResultV1* result) {
        if (request->operation == BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1 || request->operation == BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1)
            return editor_command(request, buffer, result);
        check(result && result->size == sizeof(*result), "legacy command result extent changed");
        if (request->operation == BIB_ENGINE_COMMAND_ACK_FORM_ACTION_V2) {
            ++fixture.provider_calls;
            check(!fixture.inside_provider && !fixture.owner->callback_depth() && request->payload.length == 8 &&
                buffer && buffer->capacity == 16, "legacy form ACK lost its existing metadata-only route");
            const auto sequence = get({request->payload.data, request->payload.length}, 0, 8);
            const auto& original = original_document(sequence);
            check(request->request_sequence > sequence && target(request->expected, original.target.worker_epoch) ==
                EngineEditorTarget{original.target.worker_epoch, original.target.application_instance,
                    original.target.document_sequence, original.target.service_generation}, "legacy ACK changed original action target");
            Bytes bytes(16); put(bytes, 0, sequence, 8); fixture.copy_reply(buffer, bytes);
            *result = {sizeof(*result), 1, request->request_sequence, 16, 0}; return BIB_ENGINE_OK;
        }
        if (request->operation == BIB_ENGINE_COMMAND_FORM_ACTION_V2) {
            const auto& original = original_document(request->request_sequence);
            check(request->payload.length == original.payload.size() &&
                std::equal(original.payload.begin(), original.payload.end(), request->payload.data), "legacy action lost owned payload");
            return fixture.turn([&] {
                auto bytes = ndv2(original.target, request->request_sequence, 5, 52); bytes[48] = 1; bytes[49] = 6;
                fixture.copy_reply(buffer, bytes); *result = {sizeof(*result), 1, request->request_sequence, 52, 0}; return BIB_ENGINE_OK;
            });
        }
        check(request->operation == 3 && request->payload.length == input::kFocusBytes && buffer && buffer->capacity == 16 &&
            std::equal(input::kFocusSchema.begin(), input::kFocusSchema.end(), request->schema_sha256),
            "editor-selected physical route changed the exact existing focus catalog");
        return fixture.turn([&] { *result = {sizeof(*result), 1, request->request_sequence, 0, 1}; return BIB_ENGINE_OK; });
    };
    const auto context = surface_identity(target(fixture.owner->identity())).context;
    Bytes focus; check(input::encode_focus({1, 0, 0, 0, context, 0}, focus) == input::Status::ok, "focus fixture invalid");
    const auto held = fixture.owner->reserve_editor_sequence(); check(bool(held), "editor reservation unavailable");
    check(!fixture.owner->reserve_document_sequence() && !fixture.owner->stage_command(fixture.owner->identity(), context, 3,
        input::kFocusSchema, focus, true), "form/physical admission overtook an editor reservation");
    check(fixture.owner->cancel_editor_sequence(*held), "editor reservation did not cancel");
    const auto physical = fixture.owner->stage_command(fixture.owner->identity(), context, 3, input::kFocusSchema, focus, true);
    check(bool(physical) && !fixture.owner->reserve_editor_sequence() && !fixture.owner->reserve_document_sequence(),
        "pending physical work admitted a parallel forms/editor reservation");
    fixture.until([&] { const auto result = fixture.owner->command_outcome(*physical);
        return result && result->status != EngineInputCommandStatus::pending; }, "physical work did not complete under editor selection");
    const auto physical_result = fixture.owner->command_outcome(*physical);
    check(physical_result && physical_result->status == EngineInputCommandStatus::consumed && physical_result->handled,
        "editor-selected physical completion was not retained");
    fixture.context_committed = true;
    const auto query_admission = fixture.stage(fixture.next_query());
    check(!fixture.owner->reserve_document_sequence() && !fixture.owner->stage_command(fixture.owner->identity(), context, 3,
        input::kFocusSchema, focus, true), "physical/forms work overtook pending editor query");
    fixture.complete(query_admission);
    check(!fixture.owner->reserve_document_sequence() && !fixture.owner->stage_command(fixture.owner->identity(), context, 3,
        input::kFocusSchema, focus, true), "retained editor result released its forms/physical barrier early");
    check(fixture.owner->consume_editor_outcome(query_admission.ticket), "editor query barrier did not collect");
    const auto stage_document = [&](bool form) {
        const auto sequence = fixture.owner->reserve_document_sequence(); check(bool(sequence), "legacy document sequence unavailable under editor selection");
        auto value = document_work(fixture.owner->identity(), *sequence, form); documents.push_back(value);
        const auto admission = fixture.owner->stage_document_work(std::move(value));
        check(admission.code == EngineDocumentAdmissionCode::admitted && admission.ticket, "legacy document work rejected under editor selection");
        return admission;
    };
    const auto form_query = stage_document(false);
    check(!fixture.owner->reserve_editor_sequence(), "editor reservation overtook pending forms query");
    fixture.until([&] { return bool(fixture.owner->document_outcome(form_query.ticket)); }, "legacy forms query did not complete");
    check(fixture.owner->consume_document_outcome(form_query.ticket), "legacy forms query did not collect");
    const auto action = stage_document(true); const auto original = documents.back();
    fixture.until([&] { return bool(fixture.owner->document_outcome(action.ticket)); }, "legacy form action did not complete");
    check(!fixture.owner->reserve_editor_sequence() && !fixture.owner->consume_document_outcome(action.ticket),
        "retained action debt admitted editor work before its existing ACK");
    const auto ack = fixture.owner->stage_document_action_ack(original.target, original.request_sequence);
    check(ack.code == EngineDocumentAdmissionCode::admitted && ack.ticket, "legacy ACK did not stage under editor selection");
    fixture.until([&] { return bool(fixture.owner->document_outcome(ack.ticket)); }, "legacy ACK did not complete");
    check(fixture.owner->consume_document_outcome(ack.ticket) && fixture.owner->consume_document_outcome(action.ticket),
        "checked legacy ACK failed to release its original action debt");
    const auto observation = fixture.stage(fixture.next_observation()); fixture.complete(observation);
    check(fixture.owner->consume_editor_outcome(observation.ticket), "forms-following editor observation did not collect");
    check(fixture.sequences.size() == 6 && std::adjacent_find(fixture.sequences.begin(), fixture.sequences.end(),
        [](auto previous, auto next) { return previous >= next; }) == fixture.sequences.end() &&
        fixture.sequences.front() == *physical && fixture.enters == fixture.leaves,
        "physical/query4/query3/form6/ACK7/observation8 did not preserve one ordered sequence domain and required TURN scopes");
    fixture.healthy();
}
void closing_retirement(Fixture& fixture, bool queued, bool unknown) {
    fixture.start_ready(); fixture.respond_to_commands(); fixture.acquire_retirement();
    const auto original_target = fixture.retirement_target;
    EngineEditorAdmission admitted;
    if (unknown) fixture.command_behavior = Behavior::unknown_disposition;
    if (queued) admitted = fixture.stage(fixture.next_revocation());
    fixture.driver->request_close(); fixture.tick();
    if (!queued) {
        check(fixture.driver->state() == NativeEngineState::closing && !fixture.owner->closed() && !fixture.disposals,
            "close disposed a document with unchecked native retirement material");
        admitted = fixture.stage(fixture.next_revocation());
    }
    const auto completion = fixture.complete(admitted);
    check(completion->target == original_target && fixture.commands == 1 && !fixture.disposals && !fixture.owner->closed(),
        "closing revoke was cancelled, retargeted, replayed or allowed early disposal");
    const auto calls = fixture.provider_calls;
    for (unsigned i = 0; i < 3; ++i) fixture.tick();
    check(fixture.provider_calls == calls && !fixture.disposals && completion == fixture.owner->editor_outcome(admitted.ticket),
        "retained closing editor result did not hold its original disposal barrier");
    if (unknown) {
        check(completion->outcome == EngineEditorOutcome::unknown && completion->bytes == Bytes(52, 0xd7) &&
            fixture.driver->state() == NativeEngineState::process_exit_required &&
            !fixture.owner->consume_editor_outcome(admitted.ticket), "closing unknown fabricated native retirement or cleanup");
        return;
    }
    check(completion->outcome == EngineEditorOutcome::consumed && fixture.owner->consume_editor_outcome(admitted.ticket),
        "checked closing retirement could not collect its original owned completion");
    fixture.until([&] { return fixture.driver->state() == NativeEngineState::detached; }, "checked retirement did not finish close");
    check(fixture.owner->closed() && fixture.disposals == 1 && fixture.enters == fixture.leaves && !fixture.owner->callback_depth(),
        "closing retirement did not preserve one balanced native disposal");
}
void effect_retirement(Fixture& fixture, bool form_debt, bool cross_document) {
    fixture.start_ready(); fixture.respond_to_commands();
    if (!cross_document) fixture.discover();
    fixture.acquire_retirement();
    const auto old_target = fixture.retirement_target;
    EngineDocumentAdmission form;
    EngineDocumentWork action;
    auto ordinary_commands = fixture.command_handler;
    if (form_debt) {
        const auto sequence = fixture.owner->reserve_document_sequence(); check(bool(sequence), "effect form sequence unavailable");
        action = document_work(fixture.owner->identity(), *sequence, true);
        fixture.command_handler = [&](const BibEngineCommandV1* request, BibEngineReplyBufferV1* buffer, BibEngineCommandResultV1* result) {
            if (request->operation == BIB_ENGINE_COMMAND_ACK_FORM_ACTION_V2) {
                check(!fixture.owner->callback_depth() && request->request_sequence > action.request_sequence &&
                    request->payload.length == 8 && get({request->payload.data, request->payload.length}, 0, 8) == action.request_sequence,
                    "pending-effect form ACK changed authority or entered a Host TURN");
                Bytes bytes(16); put(bytes, 0, action.request_sequence, 8); fixture.copy_reply(buffer, bytes);
                *result = {sizeof(*result), 1, request->request_sequence, 16, 0}; return BIB_ENGINE_OK;
            }
            if (request->operation != BIB_ENGINE_COMMAND_FORM_ACTION_V2) return ordinary_commands(request, buffer, result);
            check(request->request_sequence == action.request_sequence, "effect form lost its original request head");
            return fixture.turn([&] {
                fixture.submit_service_sequence = 2; fixture.submit_service();
                auto bytes = ndv2(action.target, action.request_sequence, 5, 52); bytes[48] = 1; bytes[49] = 6;
                fixture.copy_reply(buffer, bytes); *result = {sizeof(*result), 1, request->request_sequence, 52, 0}; return BIB_ENGINE_OK;
            });
        };
        form = fixture.owner->stage_document_work(action);
        check(form.code == EngineDocumentAdmissionCode::admitted && form.ticket, "effect form was not admitted");
        fixture.until([&] { return bool(fixture.owner->document_outcome(form.ticket)); }, "effect form did not return its consumed result");
    } else {
        if (cross_document) {
            fixture.navigate_on_advance = true; fixture.driver->request_advance(); fixture.tick();
            check(fixture.owner->identity().document_sequence != old_target.document_sequence && !fixture.disposals,
                "cross-document fixture did not retain the old native obligation across actual navigation");
        }
        fixture.queue_service(cross_document ? 1 : 2);
    }
    const auto effect = fixture.wait_effect();
    const auto current = fixture.owner->identity();
    const EngineDocumentTarget publication_target{current.worker_epoch, current.application_instance, current.document_sequence, current.service_generation};
    check(!fixture.owner->acknowledge_document_native_effect(effect.ticket, publication_target, 2),
        "native effect bypassed outstanding provider-owned editor material");
    if (form_debt) {
        check(!fixture.owner->reserve_editor_sequence(), "fresh native9 overtook consumed form6 debt");
        const auto ack = fixture.owner->stage_document_action_ack(action.target, action.request_sequence);
        check(ack.code == EngineDocumentAdmissionCode::admitted && ack.ticket, "pending effect blocked the exact old form ACK");
        fixture.until([&] { return bool(fixture.owner->document_outcome(ack.ticket)); }, "pending-effect form ACK did not settle");
        check(fixture.owner->consume_document_outcome(ack.ticket) && fixture.owner->consume_document_outcome(form.ticket),
            "checked form ACK did not release its original presentation debt");
    }
    if (!cross_document) fixture.commit_context(true);
    const auto revoke = fixture.stage(fixture.next_revocation());
    const auto completion = fixture.complete(revoke);
    codec::NativeResultEnvelope result;
    check(completion->outcome == EngineEditorOutcome::consumed && completion->target == old_target &&
        codec::decode_native_result(completion->bytes, result) && result.result.retired == fixture.retirement &&
        !fixture.native_effects && !fixture.disposals &&
        !fixture.owner->acknowledge_document_native_effect(effect.ticket, publication_target, 2),
        "effect drain retargeted retirement, inferred cleanup or skipped owned completion presentation");
    const auto calls = fixture.provider_calls;
    fixture.tick();
    check(fixture.provider_calls == calls && !fixture.native_effects && !fixture.disposals,
        "retained native9 completion allowed native entry or disposal before local consumption");
    check(fixture.owner->consume_editor_outcome(revoke.ticket) &&
        fixture.owner->acknowledge_document_native_effect(effect.ticket, publication_target, 2),
        "exact checked native9 completion did not release the native-effect gate");
    fixture.until([&] { return !fixture.service_pending && (cross_document ? bool(fixture.service_handle) : fixture.native_effects == 1); },
        "native service did not settle after checked retirement/publication");
    check(fixture.native_effects == (cross_document ? 0U : 1U), "native service replayed or fabricated a native effect");
    fixture.healthy();
}
void run(std::string_view scenario) {
    // The C table and Driver are process-lived. Never reset/destroy a fixture;
    // each independently registered scenario requires a fresh process.
    auto& fixture = *new Fixture(scenario.starts_with("effect-"));
    if (scenario == "close-queued-revoke") { closing_retirement(fixture, true, false); return; }
    if (scenario == "close-deferred-revoke") { closing_retirement(fixture, false, false); return; }
    if (scenario == "close-unknown-revoke") { closing_retirement(fixture, true, true); return; }
    if (scenario == "effect-retirement-drain") { effect_retirement(fixture, false, false); return; }
    if (scenario == "effect-form-ack-drain") { effect_retirement(fixture, true, false); return; }
    if (scenario == "effect-old-document-drain") { effect_retirement(fixture, false, true); return; }
    if (scenario == "startup") { startup(fixture); return; }
    if (scenario == "reservation") { reservation(fixture); return; }
    if (scenario == "metadata") { metadata(fixture); return; }
    if (scenario == "admission") { admission(fixture); return; }
    if (scenario == "legacy-lanes") { legacy_lanes(fixture); return; }
    if (scenario == "query-owned") { owned_query(fixture, true); return; }
    if (scenario == "query-null") { owned_query(fixture, false); return; }
    if (scenario == "query-rejected-preentry") { rejected_query(fixture); return; }
    if (scenario == "query-success-noenter") { invalid_query(fixture, Behavior::success_noenter); return; }
    if (scenario == "query-unknown-noenter") { invalid_query(fixture, Behavior::unknown_noenter); return; }
    if (scenario == "query-malformed-buffer") { invalid_query(fixture, Behavior::ordinary, "buffer"); return; }
    if (scenario == "query-wrong-target") { invalid_query(fixture, Behavior::ordinary, "target"); return; }
    if (scenario == "query-wrong-revision") { invalid_query(fixture, Behavior::ordinary, "revision"); return; }
    if (scenario == "query-wrong-document") { invalid_query(fixture, Behavior::ordinary, "document"); return; }
    if (scenario == "query-unknown") { unknown_query(fixture); return; }
    if (scenario == "query-unknown-opaque") { unknown_query(fixture, true); return; }
    if (scenario == "query-throw") { invalid_query(fixture, Behavior::throw_entered); return; }
    if (scenario == "query-unbalanced") { invalid_query(fixture, Behavior::unbalanced); return; }
    if (scenario == "observation-owned") { owned_observation(fixture, false); return; }
    if (scenario == "observation-navigation") { owned_observation(fixture, true); return; }
    if (scenario == "observation-rejected-preentry") { rejected_observation(fixture); return; }
    if (scenario == "observation-success-noenter") { invalid_observation(fixture, Behavior::success_noenter); return; }
    if (scenario == "observation-unknown-noenter") { invalid_observation(fixture, Behavior::unknown_noenter); return; }
    if (scenario == "observation-negative-unknown-noenter") { invalid_observation(fixture, Behavior::negative_unknown_noenter); return; }
    if (scenario == "observation-malformed-buffer") { invalid_observation(fixture, Behavior::ordinary, "buffer"); return; }
    if (scenario == "observation-wrong-target") { invalid_observation(fixture, Behavior::ordinary, "target"); return; }
    if (scenario == "observation-wrong-sequence") { invalid_observation(fixture, Behavior::ordinary, "sequence"); return; }
    if (scenario == "observation-malformed-reply") { invalid_observation(fixture, Behavior::ordinary, "reply"); return; }
    if (scenario == "observation-unknown-status") { unknown_observation(fixture, Behavior::unknown_status); return; }
    if (scenario == "observation-unknown-zero") { unknown_observation(fixture, Behavior::unknown_zero); return; }
    if (scenario == "observation-unknown-disposition") { unknown_observation(fixture, Behavior::unknown_disposition); return; }
    if (scenario == "observation-semantic-unknown") { unknown_observation(fixture, Behavior::semantic_unknown); return; }
    if (scenario == "observation-throw") { invalid_observation(fixture, Behavior::throw_entered); return; }
    if (scenario == "observation-unbalanced") { invalid_observation(fixture, Behavior::unbalanced); return; }
    if (scenario == "revoke-owned") { owned_observation(fixture, false, true); return; }
    if (scenario == "revoke-rejected-preentry") { rejected_observation(fixture, true); return; }
    if (scenario == "revoke-success-noenter") { invalid_observation(fixture, Behavior::success_noenter, {}, true); return; }
    if (scenario == "revoke-unknown-noenter") { invalid_observation(fixture, Behavior::unknown_noenter, {}, true); return; }
    if (scenario == "revoke-negative-unknown-noenter") { invalid_observation(fixture, Behavior::negative_unknown_noenter, {}, true); return; }
    if (scenario == "revoke-malformed-buffer") { invalid_observation(fixture, Behavior::ordinary, "buffer", true); return; }
    if (scenario == "revoke-wrong-target") { invalid_observation(fixture, Behavior::ordinary, "target", true); return; }
    if (scenario == "revoke-wrong-sequence") { invalid_observation(fixture, Behavior::ordinary, "sequence", true); return; }
    if (scenario == "revoke-malformed-reply") { invalid_observation(fixture, Behavior::ordinary, "reply", true); return; }
    if (scenario == "revoke-wrong-material") { invalid_observation(fixture, Behavior::ordinary, "material", true); return; }
    if (scenario == "revoke-unknown-status") { unknown_observation(fixture, Behavior::unknown_status, true); return; }
    if (scenario == "revoke-unknown-zero") { unknown_observation(fixture, Behavior::unknown_zero, true); return; }
    if (scenario == "revoke-unknown-disposition") { unknown_observation(fixture, Behavior::unknown_disposition, true); return; }
    if (scenario == "revoke-semantic-unknown") { unknown_observation(fixture, Behavior::semantic_unknown, true); return; }
    if (scenario == "revoke-throw") { invalid_observation(fixture, Behavior::throw_entered, {}, true); return; }
    if (scenario == "revoke-unbalanced") { invalid_observation(fixture, Behavior::unbalanced, {}, true); return; }
    throw std::runtime_error("unknown editor driver scenario");
}
} // namespace

int main(int argc, char** argv) {
    try {
        check(argc == 2, "Usage: appended-native-editor-driver-test SCENARIO (fresh process per scenario)");
        run(argv[1]);
        std::cout << "native editor driver mock scenario passed: " << argv[1] << " (" << assertions << " checks)\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "native editor driver mock failure: " << error.what() << '\n'; return 1;
    }
}
