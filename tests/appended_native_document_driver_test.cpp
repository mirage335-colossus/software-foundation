// SPDX-License-Identifier: CC0-1.0
// Fresh-process C-table fixtures using the real EngineOwner and native driver.
// No engine, SDK, loader, artifact qualification or GUI semantics are supplied.
#include "../gui/shared/native_engine_driver.hpp"
#include "../gui/shared/appended_engine_abi.h"
#include "../gui/shared/appended_engine_input_codec.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <functional>
#include <iostream>
#include <limits>
#include <memory>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <utility>
#include <vector>

namespace {
using namespace foundation::appended;
namespace doc = engine_document;
namespace input = engine_input;
using Span = std::span<const std::uint8_t>;
using Clock = std::chrono::steady_clock;
using namespace std::chrono_literals;
constexpr std::uint64_t instance = UINT64_C(0x8000000000000044);
constexpr std::uint64_t first_document = UINT64_C(0x8000000000000001);
constexpr std::uint64_t query_nonce = UINT64_C(0xf123456789abcdef);
std::size_t assertions{};

void check(bool value, const char* message) {
    ++assertions;
    if (!value) throw std::runtime_error(message);
}
void put(std::span<std::uint8_t> out, std::size_t offset, std::uint64_t value, unsigned width) {
    check(width <= 8 && offset <= out.size() && width <= out.size() - offset, "fixture write extent");
    for (unsigned i = 0; i < width; ++i) out[offset + i] = static_cast<std::uint8_t>(value >> (8 * i));
}
std::uint64_t get(Span bytes, std::size_t offset, unsigned width) {
    check(width <= 8 && offset <= bytes.size() && width <= bytes.size() - offset, "fixture read extent");
    std::uint64_t result{};
    for (unsigned i = 0; i < width; ++i) result |= std::uint64_t(bytes[offset + i]) << (8 * i);
    return result;
}
EngineDocumentTarget target(EngineIdentity id) {
    return {id.worker_epoch, id.application_instance, id.document_sequence, id.service_generation};
}
EngineDocumentTarget target(BibEngineDocumentV1 id, std::uint64_t epoch) {
    return {epoch, id.application_instance, id.document_sequence, id.service_generation};
}
bool same(BibEngineDocumentV1 a, BibEngineDocumentV1 b) {
    return a.application_instance == b.application_instance && a.document_sequence == b.document_sequence &&
        a.service_generation == b.service_generation;
}

Package package() {
    // Deliberately constructed unit-test values, not a verified container.
    Package result;
    result.application = {"org.example.document-driver", "Document driver fixture", "1.0.0"};
    result.web = {true, "web/index.html", {}};
    result.capabilities = {"foundation.startup.v1"};
    result.package_sha256 = result.payload_id = result.kernel_sha256 = std::string(64, '1');
    const std::string startup = "{\"kind\":\"foundation-appended-startup\",\"primary\":\"web\",\"schema_version\":1}";
    result.files = {{"web/.foundation/startup-v1.json", "web", "application/json", std::string(64, '2'),
        Bytes(startup.begin(), startup.end())}, {"web/index.html", "web", "text/html", std::string(64, '3'), {}}};
    return result;
}

doc::EngineDocumentProfileFacts profile(bool physical = false) {
    doc::EngineDocumentProfileFacts f;
    f.enabled = true; f.kind = physical ? doc::ProfileKind::physical : doc::ProfileKind::pixel;
    f.name = physical ? doc::kPhysicalProfileName : doc::kPixelProfileName;
    f.provider_abi_major = 1; f.provider_abi_minor = 1; f.host_abi_major = 1; f.host_abi_minor = 0;
#if defined(_WIN32) && (defined(_M_X64) || defined(__x86_64__))
    f.target_system = BIB_ENGINE_TARGET_WINDOWS; f.target_processor = BIB_ENGINE_CPU_X86_64;
#elif defined(__linux__) && defined(__aarch64__)
    f.target_system = BIB_ENGINE_TARGET_LINUX; f.target_processor = BIB_ENGINE_CPU_AARCH64;
#elif defined(__linux__) && defined(__x86_64__)
    f.target_system = BIB_ENGINE_TARGET_LINUX; f.target_processor = BIB_ENGINE_CPU_X86_64;
#else
    throw std::runtime_error("document driver fixture requires a supported native 64-bit target");
#endif
    f.pointer_bits = sizeof(void*) * 8;
    f.lifetime = BIB_ENGINE_LIFETIME_PROCESS; f.maximum_starts = 1;
    f.viewport_width = 800; f.viewport_height = 600;
    f.provider_capabilities = physical ? doc::kPhysicalCapabilities : doc::kPixelCapabilities;
    f.base_header_sha256 = doc::kBaseHeaderSha256; f.extension_header_sha256 = doc::kExtensionHeaderSha256;
    f.contract_sha256 = doc::kContractSha256; f.catalog_sha256 = doc::kCatalogSha256;
    // Synthetic matching pins, explicitly not retained artifact/runtime facts.
    f.build_sha256.fill(0x51); f.source_recipe_sha256.fill(0x73);
    if (physical) f.physical_catalog_sha256 = doc::kPhysicalCatalogSha256;
    f.queries = doc::kQueries; f.commands = doc::kCommands; f.query_count = 1; f.command_count = 2;
    return f;
}
std::shared_ptr<EngineOwner> owner_for(doc::EngineDocumentProfileFacts facts) {
    EngineOwnerConfiguration config;
    config.worker_epoch = UINT64_C(0x8000000000000017);
    config.abandon_closed_document_outcomes = true;
    config.document_profile = std::move(facts);
    return std::make_shared<EngineOwner>(package(), std::move(config));
}

struct ModuleCounts {
    unsigned factories{}, bindings{}, service_tables{}, callbacks{}, closes{}, destroyed{};
};
class CountedBinding final : public EngineModuleBinding {
    std::shared_ptr<ModuleCounts> counts_;
    std::uint64_t generation_;
public:
    CountedBinding(std::shared_ptr<ModuleCounts> counts, std::uint64_t generation)
        : counts_(std::move(counts)), generation_(generation) { ++counts_->bindings; }
    ~CountedBinding() override { ++counts_->destroyed; }
    WebModuleServices services() override {
        ++counts_->service_tables;
        return {generation_,
            [counts = counts_](const DiscoveryQuery&) { ++counts->callbacks; return ProviderDiscovery{}; },
            [counts = counts_](const ProviderRequest&) { ++counts->callbacks; return ProviderOutcome{}; },
            [counts = counts_](std::uint64_t) { ++counts->callbacks; return ServiceStatus::ok; },
            [counts = counts_, next = std::uint64_t{1}]() mutable -> std::optional<std::uint64_t> {
                ++counts->callbacks; return next++;
            }};
    }
    void close() noexcept override { ++counts_->closes; }
};
std::unique_ptr<EngineOwner> counted_owner(const std::shared_ptr<ModuleCounts>& counts) {
    auto payload = package();
    payload.binary = {true, "binary/application.wasm", "foundation-guest-v1"};
    // Deliberate module bytes are never parsed or executed. The real Owner
    // invokes only this counted value-interface factory; no VM leaf is linked.
    payload.files.insert(payload.files.begin(), {"binary/application.wasm", "binary", "application/wasm",
        std::string(64, '4'), {0}});
    EngineOwnerConfiguration config;
    config.worker_epoch = UINT64_C(0x8100000000000017); config.module_generation = 31;
    config.document_profile = profile();
    config.module_factory = [counts](Span bytes, std::span<const NativeServiceRegistration> services,
            std::uint64_t generation) -> std::unique_ptr<EngineModuleBinding> {
        ++counts->factories;
        check(bytes.size() == 1 && !bytes[0] && services.empty() && generation == 31,
            "counted real-Owner module factory received changed immutable inputs");
        return std::make_unique<CountedBinding>(counts, generation);
    };
    return std::make_unique<EngineOwner>(std::move(payload), std::move(config));
}
std::uint32_t configure_owner(EngineOwner& owner) {
    const auto id = owner.identity();
    std::array<std::uint8_t, FOUNDATION_ENGINE_HEADER_BYTES> request{};
    std::copy_n("FKB1", 4, request.begin());
    put(request, 4, FOUNDATION_ENGINE_RECORD_VERSION, 2); put(request, 6, FOUNDATION_ENGINE_CONFIGURE, 2);
    put(request, 8, request.size(), 4); put(request, 16, id.worker_epoch, 8);
    put(request, 24, id.application_instance, 8); put(request, 32, id.document_sequence, 8); put(request, 40, id.service_generation, 8);
    std::array<std::uint8_t, FOUNDATION_ENGINE_RECEIPT_BYTES> reply{};
    check(owner.dispatch(FOUNDATION_ENGINE_CONFIGURE, request, reply) == static_cast<std::int32_t>(reply.size()) &&
        get(reply, 6, 2) == (FOUNDATION_ENGINE_CONFIGURE | FOUNDATION_ENGINE_REPLY_KIND) &&
        get(reply, 8, 4) == reply.size(), "real counted Owner did not return a complete CONFIGURE receipt");
    return static_cast<std::uint32_t>(get(reply, FOUNDATION_ENGINE_HEADER_BYTES, 4));
}
class TerminalPublicationProbe {
    const std::shared_ptr<ModuleCounts> idle_counts_ = std::make_shared<ModuleCounts>();
    const std::shared_ptr<ModuleCounts> fresh_counts_ = std::make_shared<ModuleCounts>();
    const std::unique_ptr<EngineOwner> idle_ = counted_owner(idle_counts_);
public:
    TerminalPublicationProbe() {
        check(!idle_->configured() && !idle_counts_->factories && !idle_counts_->bindings,
            "pre-existing idle Owner invoked its counted factory before CONFIGURE");
        // Discriminate a real admission barrier from an unusable factory: this
        // equivalent real Owner configures successfully BEFORE Driver failure.
        const auto positive_counts = std::make_shared<ModuleCounts>();
        auto positive = counted_owner(positive_counts);
        check(configure_owner(*positive) == FOUNDATION_ENGINE_OK && positive->configured() && positive->has_module() &&
            positive_counts->factories == 1 && positive_counts->bindings == 1 &&
            !positive_counts->callbacks, "counted module positive control did not reach the real Owner factory before failure");
        positive->close(); positive.reset();
    }
    void verify() const {
        check(configure_owner(*idle_) == FOUNDATION_ENGINE_CLOSED && !idle_->configured() &&
            !idle_counts_->factories && !idle_counts_->bindings && !idle_counts_->callbacks,
            "Driver terminal failure was local: a pre-existing idle Owner configured or invoked its factory");
        bool rejected = false;
        try { (void)counted_owner(fresh_counts_); }
        catch (const std::exception&) { rejected = true; }
        check(rejected && !fresh_counts_->factories && !fresh_counts_->bindings && !fresh_counts_->callbacks,
            "Driver terminal failure was not published before a new enabled Owner/factory could be constructed");
    }
};

// Independent fixed-header wire fixtures. The 52-byte form rejection is a
// canonical no-readback NDV2 completion. The padded query checks only the Owner
// transport join/capacity; it is deliberately NOT a deep semantic publication.
Bytes ndv2(EngineDocumentTarget id, std::uint64_t sequence, unsigned kind,
        std::uint64_t nested, std::size_t length) {
    Bytes bytes(length);
    check(length >= 48, "fixture NDV2 prefix extent");
    std::copy_n("NDV2", 4, bytes.begin()); bytes[4] = 2; bytes[6] = static_cast<std::uint8_t>(kind);
    put(bytes, 8, id.application_instance, 8); put(bytes, 16, id.service_generation, 8);
    put(bytes, 24, id.document_sequence, 8); put(bytes, 32, sequence, 8); put(bytes, 40, nested, 8);
    return bytes;
}
EngineDocumentWork work(EngineDocumentTarget id, std::uint64_t sequence, bool form) {
    EngineDocumentWork value;
    value.target = id; value.request_sequence = sequence;
    value.kind = form ? EngineDocumentWorkKind::form_action : EngineDocumentWorkKind::snapshot_query;
    value.operation = form ? BIB_ENGINE_COMMAND_FORM_ACTION_V2 : BIB_ENGINE_QUERY_DOCUMENT_FORMS_V2;
    value.required_reply_capacity = BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY; value.schema_sha256 = doc::kSchema;
    value.payload = ndv2(id, sequence, form ? 2 : 1, form ? 0 : query_nonce, form ? 81 : 48);
    if (form) {
        // BeginFormControl(version(instance,generation,revision1), node1).
        put(value.payload, 49, id.application_instance, 8); put(value.payload, 57, id.service_generation, 8);
        put(value.payload, 65, 1, 8); put(value.payload, 73, 1, 8);
    }
    return value;
}

struct Fixture;
Fixture* active{};
enum class Behavior { ordinary, rejected, rejected_preentry, success_noenter, unknown_noenter, negative_unknown_noenter,
    unknown_status, unknown_disposition, throw_entered, unbalanced };
struct Fixture {
    std::shared_ptr<EngineOwner> owner;
    NativeEngineDriver* driver{};
    BibEngineProviderV1 table{};
    NativeEngineExpectation expected{};
    BibEngineHostV1 host{};
    BibEngineDocumentV1 document{instance, first_document, 0};
    Clock::time_point now{1000s};
    std::vector<EngineDocumentWork> submitted;
    std::vector<std::uint32_t> operations;
    std::vector<std::uint64_t> sequences;
    std::vector<BibEngineDocumentV1> command_targets;
    Bytes last_response;
    Behavior query_behavior{Behavior::ordinary}, form_behavior{Behavior::ordinary}, physical_behavior{Behavior::ordinary};
    unsigned starts{}, advances{}, provider_calls{}, queries{}, forms{}, physicals{}, acks{}, disposals{}, enters{}, leaves{};
    unsigned recursive_rejections{}, ack_code{};
    bool inside_provider{}, navigate_on_form{}, ack_callback{}, ack_foreign_callback{}, ack_enter_callback{}, ack_reenter{}, ack_unknown{}, malformed_query_buffer{};

    explicit Fixture(bool physical = false) {
        check(!active, "one fixture per fresh process"); active = this;
        expected.document_profile = profile(physical);
        const auto& facts = expected.document_profile;
        expected.target_system = facts.target_system; expected.target_processor = facts.target_processor;
        expected.pointer_bits = facts.pointer_bits; expected.contract_header_sha256 = facts.contract_sha256;
        expected.build_identity_sha256 = facts.build_sha256; expected.source_recipe_sha256 = facts.source_recipe_sha256;
        table.size = sizeof(table); table.abi_major = 1; table.abi_minor = 1;
        auto& build = table.build;
        build.size = sizeof(build); build.layout_revision = BIB_ENGINE_LAYOUT_V1;
        build.target_system = facts.target_system; build.target_processor = facts.target_processor; build.pointer_bits = facts.pointer_bits;
        build.lifetime = BIB_ENGINE_LIFETIME_PROCESS; build.maximum_starts = 1;
        build.fixed_viewport_width = 800; build.fixed_viewport_height = 600; build.capabilities = facts.provider_capabilities;
        std::copy(facts.contract_sha256.begin(), facts.contract_sha256.end(), build.contract_header_sha256);
        std::copy(facts.build_sha256.begin(), facts.build_sha256.end(), build.build_identity_sha256);
        std::copy(facts.source_recipe_sha256.begin(), facts.source_recipe_sha256.end(), build.source_recipe_sha256);
        table.limits = options().limits;
        table.start = start; table.advance = advance; table.current_document = current;
        table.query = query; table.command = command; table.deliver_services = deliver;
        table.collect_service_ack = collect; table.dispose_retired_service_document = dispose;
        owner = owner_for(facts);
    }
    static NativeEngineOptions options() {
        NativeEngineOptions options;
        options.limits.maximum_reply_bytes = BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY;
        options.maximum_steps_per_tick = 8;
        return options;
    }
    void bind() { driver = &NativeEngineDriver::bind_once(NativeEngineProvider::checked(table, expected), owner, options()); }
    void start_ready() {
        bind(); driver->start_once(now);
        check(driver->state() == NativeEngineState::ready && starts == 1 && owner->document_enabled() &&
            owner->document_profile() == expected.document_profile && !owner->has_module(), "document startup did not use the real web-only owner");
        check(owner->input_enabled() == (expected.document_profile.kind == doc::ProfileKind::physical),
            "document profile silently changed physical admission");
        tick(); // Settle the startup advance before counting document work.
        healthy();
    }
    void healthy() const {
        check(driver && driver->state() == NativeEngineState::ready && owner->callback_depth() == 0 && !inside_provider,
            "balanced fixture unexpectedly lost driver/owner readiness");
    }
    void tick() { driver->tick(now += 1ms); }
    template<class Predicate> void until(Predicate done, const char* message) {
        for (unsigned i = 0; i < 16 && !done(); ++i) tick();
        check(done(), message);
    }
    template<class Function> std::int32_t turn(Function function) {
        ++provider_calls;
        check(!inside_provider && owner->callback_depth() == 0, "provider entered recursively or outside complete turn boundary");
        inside_provider = true;
        check(host.enter_engine(host.context) == FOUNDATION_APPENDED_SERVICE_OK, "real owner rejected provider entry");
        ++enters;
        check(owner->callback_depth() == 1, "real Owner TURN was not held");
        // No catch/cleanup: an actual uncertain unwind must not fabricate LEAVE.
        const auto result = function();
        host.leave_engine(host.context); ++leaves;
        check(owner->callback_depth() == 1, "native leave prematurely released outer provider-call barrier");
        inside_provider = false;
        return result;
    }
    void begin_document() {
        BibEngineResourceEpochV1 epoch{}; epoch.size = sizeof(epoch);
        check(!document.service_generation && host.begin_resource_epoch(host.context, &document, &epoch) == BIB_ENGINE_OK &&
            epoch.resource_epoch && epoch.context && epoch.resolve && epoch.release, "prospective resource epoch was not bound");
        document.service_generation = host.begin_service_document(host.context, &document);
        check(document.service_generation && target(document, owner->identity().worker_epoch) == target(owner->identity()),
            "service document did not retain full native identity");
    }
    EngineDocumentWork next(bool form = false) {
        const auto sequence = owner->reserve_document_sequence(); check(bool(sequence), "document sequence unavailable");
        return work(target(owner->identity()), *sequence, form);
    }
    EngineDocumentAdmission stage(EngineDocumentWork value) {
        submitted.push_back(value);
        const auto admission = owner->stage_document_work(std::move(value));
        check(admission.code == EngineDocumentAdmissionCode::admitted && admission.ticket, "valid real-owner work rejected");
        return admission;
    }
    std::shared_ptr<const EngineDocumentCompletion> complete(EngineDocumentAdmission admission) {
        until([&] { return bool(owner->document_outcome(admission.ticket)); }, "driver did not publish owned completion");
        return owner->document_outcome(admission.ticket);
    }
    EngineDocumentAdmission stage_ack(const EngineDocumentWork& action) {
        const auto admission = owner->stage_document_action_ack(action.target, action.request_sequence);
        check(admission.code == EngineDocumentAdmissionCode::admitted && admission.ticket, "exact retained action ACK rejected");
        return admission;
    }
    const EngineDocumentWork& submitted_work(std::uint64_t sequence) const {
        const auto it = std::find_if(submitted.begin(), submitted.end(), [=](const auto& value) { return value.request_sequence == sequence; });
        check(it != submitted.end(), "provider received an unsubmitted sequence"); return *it;
    }
    void copy_reply(BibEngineReplyBufferV1* buffer, const Bytes& bytes) {
        check(buffer && buffer->size == sizeof(*buffer) && buffer->bytes && buffer->capacity >= bytes.size(),
            "provider was not given complete owned reply capacity");
        std::copy(bytes.begin(), bytes.end(), buffer->bytes); last_response = bytes;
    }
    void record_command(const BibEngineCommandV1* request) {
        check(request && request->size == sizeof(*request) && request->request_sequence && !request->payload.reserved,
            "malformed provider command record");
        operations.push_back(request->operation); sequences.push_back(request->request_sequence); command_targets.push_back(request->expected);
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
            check(host.enter_engine(host.context) == FOUNDATION_APPENDED_SERVICE_OK, "unbalanced fixture entry rejected"); ++enters;
            fill(); inside_provider = false; return BIB_ENGINE_OK; // Intentionally omits native leave.
        }
        return turn([&] {
            if (behavior == Behavior::throw_entered) { inside_provider = false; throw std::runtime_error("deliberate native unwind"); }
            if (behavior == Behavior::rejected) return BIB_ENGINE_STALE;
            if (behavior == Behavior::unknown_status) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
            fill(); return BIB_ENGINE_OK;
        });
    }
    static std::int32_t BIB_ENGINE_CALL start(const BibEngineHostV1* callbacks, const BibEngineStartV1* config,
            BibEngineStartResultV1* result) {
        auto& f = *active; ++f.starts;
        check(callbacks && callbacks->size == sizeof(*callbacks) && callbacks->abi_major == 1 && callbacks->abi_minor == 0 &&
            config && result && result->size == sizeof(*result), "startup C table mismatch");
        f.host = *callbacks;
        check(config->required_capabilities == f.expected.document_profile.provider_capabilities && config->raster_output == 1 &&
            config->limits.maximum_reply_bytes == BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY, "startup silently changed selected document profile/limits");
        const auto status = f.turn([&] { f.begin_document(); return BIB_ENGINE_OK; });
        *result = {sizeof(*result), BIB_ENGINE_START_READY, instance}; return status;
    }
    static std::int32_t BIB_ENGINE_CALL advance(const BibEngineAdvanceV1* request) {
        auto& f = *active; ++f.advances;
        check(request && request->application_instance == instance, "advance changed application identity");
        return f.turn([] { return BIB_ENGINE_OK; });
    }
    static std::int32_t BIB_ENGINE_CALL current(std::uint64_t application, BibEngineDocumentV1* result) {
        auto& f = *active; check(application == instance && result, "current-document identity mismatch");
        return f.turn([&] { *result = f.document; return BIB_ENGINE_OK; });
    }
    static std::int32_t BIB_ENGINE_CALL query(const BibEngineQueryV1* request, BibEngineReplyBufferV1* buffer,
            BibEngineQueryResultV1* result) {
        auto& f = *active; ++f.queries;
        check(request && request->size == sizeof(*request) && request->kind == BIB_ENGINE_QUERY_DOCUMENT_FORMS_V2 &&
            request->payload.length == 48 && request->payload.data && !request->payload.reserved && result && result->size == sizeof(*result),
            "query C record mismatch");
        const Span payload(request->payload.data, request->payload.length);
        const auto sequence = get(payload, 32, 8); const auto& original = f.submitted_work(sequence);
        check(original.kind == EngineDocumentWorkKind::snapshot_query && payload.size() == original.payload.size() &&
            std::equal(payload.begin(), payload.end(), original.payload.begin()) &&
            target(request->expected, original.target.worker_epoch) == original.target &&
            std::equal(doc::kSchema.begin(), doc::kSchema.end(), request->schema_sha256) &&
            buffer && buffer->capacity == BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY, "query lost owned bytes, full target, schema or full reply capacity");
        f.operations.push_back(request->kind); f.sequences.push_back(sequence);
        return f.response_turn(f.query_behavior, [&] {
            auto bytes = ndv2(original.target, sequence, 4, query_nonce, BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY);
            bytes.back() = 0xa7; f.copy_reply(buffer, bytes);
            *result = {sizeof(*result), static_cast<std::uint32_t>(bytes.size()), request->expected, UINT64_C(0x8123456789abcdef)};
            if (f.malformed_query_buffer) buffer->bytes = nullptr; // Tamper metadata after the owned write, never dereference it.
        });
    }
    static std::int32_t BIB_ENGINE_CALL command(const BibEngineCommandV1* request, BibEngineReplyBufferV1* buffer,
            BibEngineCommandResultV1* result) {
        auto& f = *active; f.record_command(request);
        check(result && result->size == sizeof(*result), "command result extent changed");
        *result = {sizeof(*result), 0, request->request_sequence, 0, 0};
        if (request->operation == BIB_ENGINE_COMMAND_ACK_FORM_ACTION_V2) {
            ++f.acks; ++f.provider_calls;
            check(!f.inside_provider && f.owner->callback_depth() == 0 && buffer && buffer->capacity == 16 &&
                request->payload.length == 8 && request->payload.data &&
                std::equal(doc::kAckSchema.begin(), doc::kAckSchema.end(), request->schema_sha256), "ACK entered a native turn or changed catalog/capacity");
            const auto original_sequence = get({request->payload.data, request->payload.length}, 0, 8);
            const auto& original = f.submitted_work(original_sequence);
            check(original.kind == EngineDocumentWorkKind::form_action && request->request_sequence > original_sequence &&
                target(request->expected, original.target.worker_epoch) == original.target, "ACK rebased original target or sequence");
            if (f.ack_reenter) {
                const auto before = f.provider_calls; bool rejected = false;
                try { f.driver->tick(f.now); } catch (const std::logic_error&) { rejected = true; }
                check(rejected && before == f.provider_calls && !f.owner->callback_depth(), "recursive ACK tick entered native/provider code");
                ++f.recursive_rejections;
            }
            // Even schedule-only WAKE and a refused native entry are forbidden.
            if (f.ack_callback) {
                if (f.ack_foreign_callback) {
                    std::thread worker([&f] { f.host.wake(f.host.context); });
                    worker.join(); // Publication must be visible after the foreign callback returns.
                } else f.host.wake(f.host.context);
            }
            if (f.ack_enter_callback) check(f.host.enter_engine(f.host.context) != FOUNDATION_APPENDED_SERVICE_OK,
                "metadata ACK admitted Host engine entry");
            if (f.ack_unknown) {
                // Opaque forensic bytes, deliberately not a canonical ACK
                // retirement proof. Metadata unknown never opens a Host TURN.
                const Bytes bytes(16, 0xd7); f.copy_reply(buffer, bytes);
                *result = {sizeof(*result), 2, request->request_sequence, 16, 1};
                check(!f.owner->callback_depth(), "unknown metadata ACK acquired an Owner TURN"); return BIB_ENGINE_OK;
            }
            Bytes bytes(16); put(bytes, 0, original_sequence, 8); put(bytes, 8, f.ack_code, 4); f.copy_reply(buffer, bytes);
            *result = {sizeof(*result), 1, request->request_sequence, 16, 0};
            check(!f.owner->callback_depth(), "metadata ACK acquired an Owner TURN"); return BIB_ENGINE_OK;
        }
        if (request->operation == BIB_ENGINE_COMMAND_FORM_ACTION_V2) {
            ++f.forms;
            const auto& original = f.submitted_work(request->request_sequence);
            check(original.kind == EngineDocumentWorkKind::form_action && request->payload.length == original.payload.size() &&
                request->payload.data && std::equal(original.payload.begin(), original.payload.end(), request->payload.data) &&
                target(request->expected, original.target.worker_epoch) == original.target &&
                std::equal(doc::kSchema.begin(), doc::kSchema.end(), request->schema_sha256) &&
                buffer && buffer->capacity == BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY, "form changed original work or complete capacity");
            if (f.form_behavior == Behavior::unknown_status || f.form_behavior == Behavior::unknown_disposition ||
                    f.form_behavior == Behavior::negative_unknown_noenter) result->disposition = 2;
            return f.response_turn(f.form_behavior, [&] {
                auto bytes = ndv2(original.target, request->request_sequence, 5, 0, 52);
                // Inner semantic rejected/unsupported before effects. Native
                // transport disposition/handled are separate provider values;
                // consumed-unknown must preserve even these opaque raw bytes.
                bytes[48] = 1; bytes[49] = 6;
                f.copy_reply(buffer, bytes);
                *result = {sizeof(*result), f.form_behavior == Behavior::unknown_disposition ? 2U : 1U,
                    request->request_sequence, static_cast<std::uint32_t>(bytes.size()),
                    f.form_behavior == Behavior::unknown_disposition ? 1U : 0U};
                if (f.navigate_on_form) {
                    f.navigate_on_form = false;
                    f.document = {instance, f.document.document_sequence + 1, 0};
                    f.begin_document(); // Lifecycle callback inside the original action's matching TURN.
                }
            });
        }
        ++f.physicals;
        check(f.expected.document_profile.kind == doc::ProfileKind::physical && request->operation == 3 &&
            request->payload.length == input::kFocusBytes && buffer && buffer->capacity == 16 &&
            same(request->expected, f.document) && std::equal(input::kFocusSchema.begin(), input::kFocusSchema.end(), request->schema_sha256),
            "physical route changed profile, catalog, target or fixed reply capacity");
        if (f.physical_behavior == Behavior::unknown_status) result->disposition = 2;
        return f.response_turn(f.physical_behavior, [&] {
            *result = {sizeof(*result), 1, request->request_sequence, 0, 1};
        });
    }
    static std::int32_t BIB_ENGINE_CALL deliver(const BibEngineDocumentV1*, const BibEngineBytesV1*) {
        throw std::runtime_error("document-only fixture unexpectedly delivered a service result");
    }
    static std::uint32_t BIB_ENGINE_CALL collect(const BibEngineDocumentV1*) {
        throw std::runtime_error("document-only fixture unexpectedly collected service ACK");
    }
    static std::int32_t BIB_ENGINE_CALL dispose(std::uint64_t application, std::uint64_t generation) {
        auto& f = *active; ++f.disposals;
        return f.turn([&] { check(application == instance && generation, "retired disposal lost identity"); return BIB_ENGINE_OK; });
    }
};

void metadata(Fixture& f) {
    const auto reject = [&](const std::function<void(BibEngineProviderV1&, NativeEngineExpectation&)>& mutate) {
        auto table = f.table; auto expected = f.expected; mutate(table, expected); bool rejected = false;
        try { (void)NativeEngineProvider::checked(table, expected); } catch (const std::invalid_argument&) { rejected = true; }
        check(rejected && !f.starts && !f.provider_calls && !f.owner->configured(), "invalid metadata entered provider/owner or was accepted");
    };
    reject([](auto& t, auto&) { t.abi_minor = 0; });
    reject([](auto& t, auto&) { t.abi_minor = 2; });
    reject([](auto& t, auto&) { t.build.capabilities = 259; });
    reject([](auto& t, auto&) { t.build.capabilities = 467; });
    reject([](auto& t, auto&) { t.build.capabilities = doc::kPhysicalCapabilities; });
    reject([](auto& t, auto&) { t.build.capabilities |= UINT64_C(1) << 30; });
    reject([](auto& t, auto&) { std::copy(doc::kBaseHeaderSha256.begin(), doc::kBaseHeaderSha256.end(), t.build.contract_header_sha256); });
    reject([](auto& t, auto&) { --t.limits.maximum_reply_bytes; });
    reject([](auto& t, auto&) { t.limits.maximum_query_bytes = 47; });
    reject([](auto& t, auto&) { t.limits.maximum_command_bytes = BIB_ENGINE_DOCUMENT_V2_MAX_ACTION_BYTES - 1; });
    reject([](auto&, auto& e) { e.document_profile = {}; });
    reject([](auto&, auto& e) { e.document_profile.provider_abi_minor = 0; });
    reject([](auto&, auto& e) { e.document_profile.extension_header_sha256[0] ^= 1; });
    reject([](auto&, auto& e) { e.document_profile.catalog_sha256[0] ^= 1; });
    reject([](auto&, auto& e) { e.document_profile.queries[0].required_reply_capacity = 65536; });
    reject([](auto&, auto& e) { e.document_profile.commands[1].schema_sha256[0] ^= 1; });
    reject([](auto&, auto& e) { e.document_profile.build_sha256[0] ^= 1; });
    reject([](auto&, auto& e) { e.document_profile.host_abi_minor = 1; });
    reject([](auto&, auto& e) { e.document_profile.physical_catalog_sha256 = doc::kPhysicalCatalogSha256; });
    reject([](auto& t, auto&) { t.query = nullptr; });
    (void)NativeEngineProvider::checked(f.table, f.expected);
    check(!f.provider_calls && !f.owner->configured(), "valid metadata inspection performed effects");
}

void admission(Fixture& f) {
    const auto rejects = [&](std::shared_ptr<EngineOwner> owner, NativeEngineOptions options) {
        bool rejected = false;
        try { (void)NativeEngineDriver::bind_once(NativeEngineProvider::checked(f.table, f.expected), owner, options); }
        catch (const std::invalid_argument&) { rejected = true; }
        check(rejected && !owner->configured() && !f.starts && !f.provider_calls, "mismatched Owner/profile/selected limits reached binding effects");
    };
    rejects(owner_for({}), Fixture::options());
    auto different = f.expected.document_profile; different.build_sha256[0] ^= 1;
    rejects(owner_for(different), Fixture::options());
    rejects(owner_for(profile(true)), Fixture::options());
    rejects(f.owner, NativeEngineOptions{}); // No implicit widening from the legacy 64KiB selection.
    auto options = Fixture::options(); options.limits.maximum_reply_bytes = BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY - 1;
    rejects(f.owner, options);
    options = Fixture::options(); options.limits.maximum_query_bytes = 47; rejects(f.owner, options);
    options = Fixture::options(); options.limits.maximum_command_bytes = BIB_ENGINE_DOCUMENT_V2_MAX_ACTION_BYTES - 1;
    rejects(f.owner, options);
    f.start_ready();
}

void owned_query(Fixture& f) {
    f.start_ready(); auto value = f.next(); const auto original = value;
    const auto admission = f.stage(value); std::fill(value.payload.begin(), value.payload.end(), 0xee);
    const auto completion = f.complete(admission);
    check(f.queries == 1 && !f.forms && !f.acks && completion->outcome == EngineDocumentOutcome::consumed &&
        completion->target == original.target && completion->request_sequence == original.request_sequence && completion->transfer &&
        completion->provider_status == 0 && !completion->provider_disposition && !completion->handled &&
        completion->semantic_revision == UINT64_C(0x8123456789abcdef) && completion->bytes.size() == BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY &&
        get(completion->bytes, 40, 8) == query_nonce && completion->bytes.back() == 0xa7,
        "query result did not preserve owned raw bytes/full identities/revision/transport outcome");
    std::fill(f.last_response.begin(), f.last_response.end(), 0);
    const auto advances = f.advances;
    for (unsigned i = 0; i < 3; ++i) {
        f.driver->request_advance(); f.tick();
        check(completion == f.owner->document_outcome(admission.ticket) && f.queries == 1 && completion->bytes.back() == 0xa7 &&
            f.advances == advances && f.driver->state() == NativeEngineState::ready,
            "uncollected result redelivery replayed query, advanced engine or poisoned temporary Owner barrier");
    }
    check(f.owner->consume_document_outcome(admission.ticket) && completion == f.owner->document_outcome(admission.ticket),
        "query retirement lost the latest immutable completion cache");
    check(f.owner->consume_document_outcome(admission.ticket) && completion == f.owner->document_outcome(admission.ticket) && f.queries == 1,
        "idempotent query retirement replaced its cache or repeated provider work");
    f.driver->request_advance(); f.until([&] { return f.advances > advances; }, "collected query did not release pending ordinary advance");
    const auto reservation = f.owner->reserve_document_sequence(); check(bool(reservation), "post-query sequence reservation unavailable");
    const auto held_advances = f.advances; f.driver->request_advance(); f.tick();
    check(f.advances == held_advances && f.driver->state() == NativeEngineState::ready, "held document reservation did not suppress ordinary engine advance");
    check(f.owner->cancel_document_sequence(*reservation), "held sequence cancellation rejected");
    f.until([&] { return f.advances > held_advances; }, "cancelled reservation consumed/lost queued advance request");
    check(completion == f.owner->document_outcome(admission.ticket) && f.queries == 1 && completion->bytes.back() == 0xa7,
        "released work barrier destroyed cached query identity or replayed provider capture"); f.healthy();
}

void form_and_ack(Fixture& f, unsigned code, bool navigate, bool reenter = false) {
    f.start_ready(); f.ack_code = code; f.ack_reenter = reenter; f.navigate_on_form = navigate;
    const auto action = f.next(true); const auto admission = f.stage(action); const auto completion = f.complete(admission);
    check(f.forms == 1 && completion->outcome == EngineDocumentOutcome::consumed && completion->provider_status == 0 &&
        completion->provider_disposition == 1 && !completion->handled && completion->bytes.size() == 52 &&
        completion->bytes[48] == 1 && completion->bytes[49] == 6 && !completion->bytes[50] &&
        !f.owner->consume_document_outcome(admission.ticket), "native consumed transport was confused with inner semantic rejection or lost retained action debt");
    if (navigate) {
        check(f.owner->identity().document_sequence == first_document + 1 && !f.navigate_on_form && !f.disposals &&
            completion->target == action.target && completion->request_sequence == action.request_sequence &&
            get(completion->bytes, 24, 8) == action.target.document_sequence &&
            target(f.command_targets.front(), action.target.worker_epoch) == action.target,
            "action-turn navigation rewrote original request/result authority or retired the old document early");
    }
    const auto advances = f.advances; f.driver->request_advance(); f.tick();
    check(f.advances == advances && f.forms == 1 && f.driver->state() == NativeEngineState::ready,
        "retained form/local-result debt allowed generic engine advance or action replay");
    auto ack = f.stage_ack(action); const auto same_ack = f.stage_ack(action);
    check(ack.ticket == same_ack.ticket, "identical pending ACK intent minted a second provider attempt");
    auto receipt = f.complete(ack);
    const auto decoded = decode_engine_document_action_ack(receipt->bytes);
    check(decoded && decoded->original_action_sequence == action.request_sequence && static_cast<unsigned>(decoded->code) == code &&
        receipt->target == action.target && receipt->request_sequence > action.request_sequence && receipt->provider_disposition == 1 &&
        !receipt->handled && f.acks == 1 && !f.owner->callback_depth(), "ACK result lost raw16, old target, sequence or metadata-only scope");
    for (unsigned i = 0; i < 3; ++i) f.tick();
    check(f.acks == 1 && receipt == f.owner->document_outcome(ack.ticket) && completion == f.owner->document_outcome(admission.ticket),
        "retained action/ACK redelivery repeated native attempt");
    check(f.owner->consume_document_outcome(ack.ticket), "metadata ACK completion did not collect");
    if (code == BIB_ENGINE_DOCUMENT_V2_ACK_STALE) {
        check(!f.owner->consume_document_outcome(admission.ticket), "STALE2 ACK cleared retained action");
        f.ack_code = 0; const auto replacement = f.stage_ack(action); receipt = f.complete(replacement);
        check(f.acks == 2 && receipt->request_sequence > f.sequences[f.sequences.size() - 2] && receipt->target == action.target,
            "fresh checked ACK after STALE2 reused sequence or rebased target");
        check(f.owner->consume_document_outcome(replacement.ticket), "replacement ACK did not collect");
    }
    check(f.owner->consume_document_outcome(admission.ticket), "checked ACK0/1 did not release retained action");
    if (navigate) f.until([&] { return f.disposals == 1; }, "old document was not disposed after local action collection");
    check(f.forms == 1 && f.recursive_rejections == (reenter ? 1U : 0U), "form/ACK was reentered or expected recursion guard not observed");
    f.healthy();
}

void rejected_form(Fixture& f) {
    f.start_ready(); f.form_behavior = Behavior::rejected;
    const auto admission = f.stage(f.next(true)); const auto completion = f.complete(admission);
    check(f.forms == 1 && completion->outcome == EngineDocumentOutcome::rejected && completion->provider_status == BIB_ENGINE_STALE &&
        !completion->provider_disposition && !completion->handled && completion->bytes.empty() && f.owner->consume_document_outcome(admission.ticket),
        "known provider rejection acquired raw semantic success or retained native action debt");
    for (unsigned i = 0; i < 3; ++i) f.tick();
    check(f.forms == 1 && !f.acks, "known rejection was retried or ACKed"); f.healthy();
}

void rejected_preentry(Fixture& f, bool form) {
    f.start_ready();
    if (form) f.form_behavior = Behavior::rejected_preentry;
    else f.query_behavior = Behavior::rejected_preentry;
    const auto value = f.next(form); const auto admission = f.stage(value);
    const auto enters = f.enters, leaves = f.leaves, calls = f.provider_calls;
    const auto completion = f.complete(admission);
    check(completion->outcome == EngineDocumentOutcome::rejected && completion->target == value.target &&
        completion->ticket == admission.ticket && completion->request_sequence == value.request_sequence && completion->transfer &&
        completion->provider_status == BIB_ENGINE_STALE && !completion->provider_disposition && !completion->handled &&
        !completion->semantic_revision && completion->bytes.empty() && f.provider_calls == calls + 1 &&
        f.enters == enters && f.leaves == leaves && !f.owner->callback_depth() && !f.acks,
        "safe known pre-entry rejection required/fabricated a native turn or lost its owned exact result");
    for (unsigned i = 0; i < 3; ++i) {
        f.driver->request_advance(); f.tick();
        check(completion == f.owner->document_outcome(admission.ticket) && f.provider_calls == calls + 1 &&
            f.enters == enters && f.leaves == leaves && !f.acks,
            "retained pre-entry rejection replayed provider or synthesized a turn/ACK");
    }
    check(f.owner->consume_document_outcome(admission.ticket), "known pre-entry rejection could not collect locally");
    if (form) f.form_behavior = Behavior::ordinary;
    else f.query_behavior = Behavior::ordinary;
    const auto following = f.next(form); const auto following_admission = f.stage(following);
    const auto resumed = f.complete(following_admission);
    check(following.request_sequence > value.request_sequence && resumed->outcome == EngineDocumentOutcome::consumed &&
        resumed->target == following.target && resumed->request_sequence == following.request_sequence &&
        f.enters == enters + 1 && f.leaves == leaves + 1 && (form ? f.forms == 2 : f.queries == 2),
        "collected pre-entry rejection prevented a later ordinary balanced request");
    if (form) {
        const auto ack = f.stage_ack(following); f.complete(ack);
        check(f.owner->consume_document_outcome(ack.ticket), "resumed form ACK could not collect");
    }
    check(f.owner->consume_document_outcome(following_admission.ticket), "resumed result could not collect"); f.healthy();
}

void invalid_query(Fixture& f, Behavior behavior, bool malformed) {
    f.start_ready(); f.query_behavior = behavior; f.malformed_query_buffer = malformed;
    const TerminalPublicationProbe terminal_publication;
    const auto admission = f.stage(f.next());
    const auto enters = f.enters, leaves = f.leaves, calls = f.provider_calls;
    f.tick();
    const auto expected_turns = malformed ? 1U : 0U;
    check(f.queries == 1 && f.provider_calls == calls + 1 && f.enters == enters + expected_turns &&
        f.leaves == leaves + expected_turns && !f.owner->callback_depth() &&
        f.driver->state() == NativeEngineState::process_exit_required && !f.owner->document_outcome(admission.ticket),
        "success/unknown without native turn or malformed owned buffer fabricated a result/turn instead of terminating");
    const auto stopped_calls = f.provider_calls;
    for (unsigned i = 0; i < 3; ++i) { f.driver->request_advance(); f.tick(); }
    check(f.provider_calls == stopped_calls && !f.owner->document_outcome(admission.ticket),
        "invalid claimed query was retried or settled synthetically");
    terminal_publication.verify();
}

void negative_unknown_noenter(Fixture& f) {
    f.start_ready(); f.form_behavior = Behavior::negative_unknown_noenter;
    const auto admission = f.stage(f.next(true));
    const auto enters = f.enters, leaves = f.leaves, calls = f.provider_calls;
    f.tick();
    check(f.forms == 1 && !f.acks && f.provider_calls == calls + 1 && f.enters == enters && f.leaves == leaves &&
        !f.owner->callback_depth() && f.driver->state() == NativeEngineState::process_exit_required &&
        !f.owner->document_outcome(admission.ticket),
        "negative consumed-unknown form took the known pre-entry rejection exception or fabricated a turn/result");
    const auto stopped_calls = f.provider_calls;
    for (unsigned i = 0; i < 3; ++i) { f.driver->request_advance(); f.tick(); }
    check(f.provider_calls == stopped_calls && !f.acks && !f.owner->document_outcome(admission.ticket),
        "no-turn negative consumed-unknown form replayed, ACKed or settled synthetically");
}

void unknown(Fixture& f, bool form, bool disposition) {
    f.start_ready();
    if (form) f.form_behavior = disposition ? Behavior::unknown_disposition : Behavior::unknown_status;
    else f.query_behavior = Behavior::unknown_status;
    const auto original = f.next(form); const auto admission = f.stage(original); const auto completion = f.complete(admission);
    check(completion->outcome == EngineDocumentOutcome::unknown && completion->provider_status == (disposition ? 0 : BIB_ENGINE_PROCESS_EXIT_REQUIRED) &&
        completion->provider_disposition == (form ? 2U : 0U) && f.driver->state() == NativeEngineState::process_exit_required &&
        !f.owner->callback_depth() && f.enters == f.leaves, "naturally returned unknown was not settled after its complete native turn");
    if (disposition) {
        check(completion->handled && completion->bytes.size() == 52 && completion->bytes == f.last_response &&
            completion->target == original.target && completion->request_sequence == original.request_sequence &&
            get(completion->bytes, 8, 8) == original.target.application_instance &&
            get(completion->bytes, 16, 8) == original.target.service_generation &&
            get(completion->bytes, 24, 8) == original.target.document_sequence &&
            get(completion->bytes, 32, 8) == original.request_sequence && !f.acks,
            "naturally balanced consumed-unknown lost exact raw52, handled1 or original header/completion authority");
    } else check(completion->bytes.empty() && !completion->handled, "status -8 zero-payload fixture acquired semantic bytes or handled claim");
    const auto calls = f.provider_calls;
    for (unsigned i = 0; i < 3; ++i) { f.driver->request_advance(); f.tick(); }
    check(calls == f.provider_calls && completion == f.owner->document_outcome(admission.ticket) && !f.acks && !f.owner->reserve_document_sequence(),
        "unknown terminal completion replayed provider or reopened ordinary work");
    if (form) check(!f.owner->consume_document_outcome(admission.ticket), "unknown native form debt was silently released");
}

void uncertain_unwind(Fixture& f, bool unbalanced) {
    f.start_ready(); f.query_behavior = unbalanced ? Behavior::unbalanced : Behavior::throw_entered;
    const TerminalPublicationProbe terminal_publication;
    const auto admission = f.stage(f.next()); const auto before_leaves = f.leaves;
    f.tick();
    check(f.queries == 1 && f.driver->state() == NativeEngineState::process_exit_required && f.owner->callback_depth() == 1 &&
        f.leaves == before_leaves && !f.owner->document_outcome(admission.ticket), "uncertain native call fabricated LEAVE or owned result");
    const auto calls = f.provider_calls;
    for (unsigned i = 0; i < 3; ++i) f.tick();
    check(f.provider_calls == calls && !f.owner->document_outcome(admission.ticket), "uncertain claimed slot was retried or settled synthetically");
    terminal_publication.verify();
}

void ack_callback(Fixture& f, bool enter, bool foreign = false) {
    f.start_ready(); const auto action = f.next(true); const auto admission = f.stage(action); const auto completion = f.complete(admission);
    const TerminalPublicationProbe terminal_publication;
    f.ack_callback = !enter; f.ack_foreign_callback = foreign; f.ack_enter_callback = enter; const auto ack = f.stage_ack(action); f.tick();
    check(f.acks == 1 && f.driver->state() == NativeEngineState::process_exit_required && !f.owner->callback_depth() &&
        !f.owner->document_outcome(ack.ticket) && completion == f.owner->document_outcome(admission.ticket) &&
        !f.owner->consume_document_outcome(admission.ticket), "ACK Host callback acquired TURN, fabricated result or cleared native action debt");
    const auto calls = f.provider_calls; f.tick(); check(calls == f.provider_calls, "faulted metadata ACK was retried");
    terminal_publication.verify();
}

void unknown_ack(Fixture& f) {
    f.start_ready(); const auto action = f.next(true); const auto action_admission = f.stage(action);
    const auto action_completion = f.complete(action_admission);
    check(action_completion->outcome == EngineDocumentOutcome::consumed &&
        !f.owner->consume_document_outcome(action_admission.ticket), "ACK-unknown fixture did not retain the original consumed action");
    f.ack_unknown = true; const auto admission = f.stage_ack(action);
    const auto enters = f.enters, leaves = f.leaves, calls = f.provider_calls;
    const auto completion = f.complete(admission);
    check(completion->kind == EngineDocumentWorkKind::action_ack && completion->outcome == EngineDocumentOutcome::unknown &&
        completion->provider_status == 0 && completion->provider_disposition == 2 && completion->handled &&
        completion->ticket == admission.ticket && completion->target == action.target &&
        completion->request_sequence > action.request_sequence && completion->request_sequence == f.sequences.back() &&
        completion->bytes == Bytes(16, 0xd7) && !decode_engine_document_action_ack(completion->bytes) &&
        f.acks == 1 && f.provider_calls == calls + 1 && f.enters == enters && f.leaves == leaves && !f.owner->callback_depth() &&
        f.driver->state() == NativeEngineState::process_exit_required,
        "metadata ACK unknown lost bounded forensic raw16/handled/authority or fabricated a host turn/retirement proof");
    check(action_completion == f.owner->document_outcome(action_admission.ticket) &&
        !f.owner->consume_document_outcome(action_admission.ticket) && !f.owner->consume_document_outcome(admission.ticket),
        "unknown ACK raw bytes cleared action debt or became a collectable checked retirement proof");
    const auto stopped_calls = f.provider_calls;
    for (unsigned i = 0; i < 3; ++i) { f.driver->request_advance(); f.tick(); }
    check(f.provider_calls == stopped_calls && f.acks == 1 && completion == f.owner->document_outcome(admission.ticket) &&
        action_completion == f.owner->document_outcome(action_admission.ticket),
        "terminal ACK unknown replayed provider/ACK or replaced owned action/forensic completion");
}

EngineInputTicket stage_physical(Fixture& f) {
    Bytes focus;
    check(input::encode_focus({1, 0, 0, 0, 7, 0}, focus) == input::Status::ok, "physical focus fixture invalid");
    const auto ticket = f.owner->stage_command(f.owner->identity(), 7, 3, input::kFocusSchema, focus, true);
    check(bool(ticket), "real physical owner rejected focus command"); return *ticket;
}
void physical_order(Fixture& f, bool fail) {
    f.start_ready(); const auto physical = stage_physical(f);
    if (fail) f.physical_behavior = Behavior::unknown_status;
    // The Owner serializes physical and document admission, not merely their
    // later provider calls. This candidate has not acquired a reservation.
    const auto candidate = work(target(f.owner->identity()), physical + 1, false);
    const auto busy = f.owner->stage_document_work(candidate);
    check(!f.owner->reserve_document_sequence() && busy.code == EngineDocumentAdmissionCode::busy && !busy.ticket &&
        !f.owner->document_outcome(busy.ticket), "pending physical work admitted a document reservation/work/completion");
    if (fail) {
        f.until([&] { return f.driver->state() == NativeEngineState::process_exit_required; }, "physical unknown did not stop driver");
        const auto outcome = f.owner->command_outcome(physical);
        const auto refused = f.owner->stage_document_work(candidate);
        check(outcome && outcome->status == EngineInputCommandStatus::unknown && outcome->provider_status == BIB_ENGINE_PROCESS_EXIT_REQUIRED &&
            f.physicals == 1 && !f.queries && !f.owner->reserve_document_sequence() &&
            refused.code != EngineDocumentAdmissionCode::admitted && !refused.ticket && !f.owner->document_outcome(refused.ticket) &&
            !f.owner->callback_depth(), "physical unknown lost owned outcome, reopened document admission or fabricated query completion");
        const auto calls = f.provider_calls; for (unsigned i = 0; i < 3; ++i) f.tick();
        check(f.provider_calls == calls && f.physicals == 1, "physical unknown was replayed"); return;
    }
    f.until([&] {
        const auto value = f.owner->command_outcome(physical);
        return value && value->status != EngineInputCommandStatus::pending;
    }, "physical command did not complete before later document admission");
    const auto outcome = f.owner->command_outcome(physical);
    check(outcome && outcome->status == EngineInputCommandStatus::consumed && outcome->handled && f.physicals == 1 && !f.queries,
        "physical completion was lost or an unadmitted query entered provider");
    const auto sequence = f.owner->reserve_document_sequence(); check(bool(sequence), "completed physical command retained document admission barrier");
    Bytes focus; check(input::encode_focus({1, 0, 0, 0, 7, 0}, focus) == input::Status::ok, "physical barrier fixture invalid");
    check(!f.owner->stage_command(f.owner->identity(), 7, 3, input::kFocusSchema, focus, true),
        "physical command overtook held document reservation");
    const auto query = work(target(f.owner->identity()), *sequence, false); const auto query_admission = f.stage(query);
    check(!f.owner->stage_command(f.owner->identity(), 7, 3, input::kFocusSchema, focus, true),
        "physical command overtook uncompleted document work");
    const auto query_result = f.complete(query_admission);
    check(f.physicals == 1 && f.queries == 1 &&
        f.sequences.size() == 2 && f.sequences[0] == physical && f.sequences[1] == query.request_sequence && physical < query.request_sequence,
        "physical and query did not use one ordered u64 sequence domain");
    check(query_result->outcome == EngineDocumentOutcome::consumed && f.owner->consume_document_outcome(query_admission.ticket), "physical-following query did not collect");
    const auto action = f.next(true); const auto admission = f.stage(action); f.complete(admission);
    const auto ack = f.stage_ack(action); f.complete(ack);
    check(action.request_sequence > query.request_sequence && f.forms == 1 && f.acks == 1 && f.sequences.size() == 4 &&
        f.sequences[2] == action.request_sequence && f.sequences[3] > action.request_sequence &&
        f.owner->consume_document_outcome(ack.ticket) && f.owner->consume_document_outcome(admission.ticket),
        "physical/query/form/ACK sequence order or retained collection changed"); f.healthy();
}

void ack_wire_boundaries() {
    // Full-width leaf codec coverage only: the real Owner's public allocator has
    // no initial-sequence seam, so this is not a Driver-at-MAX execution claim.
    for (const auto original : {UINT64_C(0x8000000000000001), BIB_ENGINE_DOCUMENT_V2_MAX_ORDINARY_SEQUENCE}) {
        const auto encoded = encode_engine_document_action_ack(original);
        check(encoded && get(*encoded, 0, 8) == original, "ACK input truncated full u64 original action");
        for (unsigned code = 0; code <= 2; ++code) {
            Bytes bytes(16); put(bytes, 0, original, 8); put(bytes, 8, code, 4);
            const auto decoded = decode_engine_document_action_ack(bytes);
            check(decoded && decoded->original_action_sequence == original && static_cast<unsigned>(decoded->code) == code,
                "ACK raw16 decoder truncated full u64 action or changed code domain");
        }
    }
    check(!encode_engine_document_action_ack(0) && !encode_engine_document_action_ack(UINT64_MAX), "ACK original admitted zero/final ACK sequence");
}

void run(std::string_view scenario) {
    if (scenario == "ack-wire-boundaries") { ack_wire_boundaries(); return; }
    // Process-lived callbacks and the single-bind driver are intentionally not
    // destroyed/reset. The test runner must launch each scenario separately.
    auto& f = *new Fixture(scenario == "physical-order" || scenario == "physical-unknown");
    if (scenario == "metadata") { metadata(f); return; }
    if (scenario == "admission") { admission(f); return; }
    if (scenario == "query-owned") { owned_query(f); return; }
    if (scenario == "form-rejected") { rejected_form(f); return; }
    if (scenario == "query-rejected-preentry") { rejected_preentry(f, false); return; }
    if (scenario == "form-rejected-preentry") { rejected_preentry(f, true); return; }
    if (scenario == "query-success-noenter") { invalid_query(f, Behavior::success_noenter, false); return; }
    if (scenario == "query-unknown-noenter") { invalid_query(f, Behavior::unknown_noenter, false); return; }
    if (scenario == "query-malformed-buffer") { invalid_query(f, Behavior::ordinary, true); return; }
    if (scenario == "form-negative-unknown-noenter") { negative_unknown_noenter(f); return; }
    if (scenario == "form-ack0") { form_and_ack(f, 0, false); return; }
    if (scenario == "form-ack1") { form_and_ack(f, 1, false); return; }
    if (scenario == "form-old-ack1") { form_and_ack(f, 1, true); return; }
    if (scenario == "form-old-ack2") { form_and_ack(f, 2, true); return; }
    if (scenario == "ack-reentry") { form_and_ack(f, 0, false, true); return; }
    if (scenario == "ack-host-callback") { ack_callback(f, false); return; }
    if (scenario == "ack-host-enter") { ack_callback(f, true); return; }
    if (scenario == "ack-host-callback-foreign") { ack_callback(f, false, true); return; }
    if (scenario == "ack-unknown") { unknown_ack(f); return; }
    if (scenario == "query-unknown") { unknown(f, false, false); return; }
    if (scenario == "form-unknown-status") { unknown(f, true, false); return; }
    if (scenario == "form-unknown-disposition") { unknown(f, true, true); return; }
    if (scenario == "query-throw") { uncertain_unwind(f, false); return; }
    if (scenario == "query-unbalanced") { uncertain_unwind(f, true); return; }
    if (scenario == "physical-order") { physical_order(f, false); return; }
    if (scenario == "physical-unknown") { physical_order(f, true); return; }
    throw std::runtime_error("unknown document driver scenario");
}
} // namespace

int main(int argc, char** argv) {
    try {
        check(argc == 2, "Usage: appended-native-document-driver-test SCENARIO (fresh process per scenario)");
        run(argv[1]);
        std::cout << "native document driver mock scenario passed: " << argv[1] << " (" << assertions << " checks)\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "native document driver mock fixture: " << error.what() << '\n'; return 1;
    }
}
