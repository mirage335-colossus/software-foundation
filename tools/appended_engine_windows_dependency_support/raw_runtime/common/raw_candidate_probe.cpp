#include "raw_candidate_probe.hpp"
#include "appended_demo_services.hpp"
#include "native_engine_document_composition.hpp"
#include "sha256.hpp"
#include <gui/terminal.hpp>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <memory>
#include <ostream>
#include <stdexcept>
#include <thread>
#include <utility>

namespace foundation::appended::raw_candidate {
namespace {
using Clock = std::chrono::steady_clock;
constexpr std::string_view echo_payload = "foundation-raw-candidate-echo-v1";
constexpr std::string_view marker = "RAW_RUNTIME_ECHO_OK";
void require(bool condition, const char* message) { if (!condition) throw std::runtime_error(message); }
std::string hex(const engine_document::Digest& bytes) {
    constexpr char digits[] = "0123456789abcdef";
    std::string result; result.reserve(64);
    for (auto byte : bytes) { result += digits[byte >> 4]; result += digits[byte & 15]; }
    return result;
}
std::string hash(std::span<const std::uint8_t> bytes) { detail::Sha256 value; value.update(bytes); return hex(value.finish()); }
struct State;
State* active{}; // One actual process-lived Driver/provider; never reset/reused.
struct State {
    RawCandidateRuntimeObservations out;
    BibEngineProviderV1 original{};
    BibEngineHostV1 host{}, forwarded_host{};
    std::uint64_t depth{};
    std::atomic<bool> violation{};
    const std::thread::id thread{std::this_thread::get_id()};
    std::shared_ptr<EngineOwner> owner;
    NativeEngineDriver* driver{};
    foundation::ui::NativeEngineDocumentComposition* composition{};
    gui::TerminalAdapter terminal;
    State() : terminal([this](gui::Event event) { if (composition) composition->handle(std::move(event)); }) {}
    bool owner_thread() noexcept {
        if (std::this_thread::get_id() == thread) return true;
        violation.store(true, std::memory_order_release); return false;
    }
    struct Entry {
        State& state;
        Entry() : state(*active) {
            require(state.owner_thread(), "raw candidate provider entry crossed its owner thread");
            if (state.depth) state.violation.store(true, std::memory_order_release);
            ++state.depth; ++state.out.provider_entries;
            state.out.maximum_provider_depth = std::max(state.out.maximum_provider_depth, state.depth);
        }
        ~Entry() { --state.depth; }
    };
    static std::uint32_t BIB_ENGINE_CALL enter(void* context) {
        auto& s = *active; if (!s.owner_thread()) return 14;
        if (context != s.host.context || !s.depth) s.violation.store(true, std::memory_order_release);
        const auto status = s.host.enter_engine(context); if (!status) ++s.out.enter_calls; return status;
    }
    static void BIB_ENGINE_CALL leave(void* context) {
        auto& s = *active; if (!s.owner_thread()) return;
        if (context != s.host.context || !s.depth) s.violation.store(true, std::memory_order_release);
        s.host.leave_engine(context); ++s.out.leave_calls;
    }
    static void BIB_ENGINE_CALL damage(void* context, const BibEngineDamageV1* value) {
        auto& s = *active; if (!s.owner_thread()) return;
        if (context != s.host.context || !s.depth) s.violation.store(true, std::memory_order_release);
        s.host.damage(context, value); ++s.out.damage_callbacks;
    }
    static std::uint32_t BIB_ENGINE_CALL stage_ack(void* context, std::uint64_t generation, std::uint64_t through) {
        auto& s = *active; if (!s.owner_thread()) return 14;
        if (context != s.host.context || !s.depth) s.violation.store(true, std::memory_order_release);
        const auto status = s.host.stage_service_ack(context, generation, through);
        if (!status) s.out.service_ack_through = std::max(s.out.service_ack_through, through);
        return status;
    }
    static std::int32_t BIB_ENGINE_CALL start(const BibEngineHostV1* host, const BibEngineStartV1* input, BibEngineStartResultV1* result) {
        Entry entry; auto& s = entry.state; ++s.out.starts;
        require(host && s.out.starts == 1, "raw candidate START was absent or replayed");
        s.host = *host; s.forwarded_host = *host;
        s.forwarded_host.enter_engine = enter; s.forwarded_host.leave_engine = leave;
        s.forwarded_host.damage = damage; s.forwarded_host.stage_service_ack = stage_ack;
        return s.original.start(&s.forwarded_host, input, result);
    }
    static std::int32_t BIB_ENGINE_CALL advance(const BibEngineAdvanceV1* value) { Entry e; return e.state.original.advance(value); }
    static std::int32_t BIB_ENGINE_CALL current(std::uint64_t instance, BibEngineDocumentV1* value) { Entry e; return e.state.original.current_document(instance, value); }
    static std::int32_t BIB_ENGINE_CALL command(const BibEngineCommandV1* input, BibEngineReplyBufferV1* output, BibEngineCommandResultV1* result) { Entry e; return e.state.original.command(input, output, result); }
    static std::int32_t BIB_ENGINE_CALL query(const BibEngineQueryV1* input, BibEngineReplyBufferV1* output, BibEngineQueryResultV1* result) {
        Entry e; auto& s = e.state; const auto status = s.original.query(input, output, result);
        if (input && input->kind == BIB_ENGINE_QUERY_DOCUMENT_FORMS_V2 && status == BIB_ENGINE_OK) {
            require(output && result && output->bytes && result->bytes_written <= output->capacity,
                "raw candidate query returned invalid owned reply bounds");
            ++s.out.query3_calls; s.out.query3_reply_bytes = result->bytes_written;
            s.out.semantic_revision = result->semantic_revision;
            s.out.query3_sha256 = hash({output->bytes, result->bytes_written});
        }
        return status;
    }
    static std::int32_t BIB_ENGINE_CALL deliver(const BibEngineDocumentV1* document, const BibEngineBytesV1* bytes) { Entry e; ++e.state.out.deliveries; return e.state.original.deliver_services(document, bytes); }
    static std::uint32_t BIB_ENGINE_CALL ack(const BibEngineDocumentV1* document) { Entry e; return e.state.original.collect_service_ack(document); }
    static std::int32_t BIB_ENGINE_CALL dispose(std::uint64_t instance, std::uint64_t generation) { Entry e; return e.state.original.dispose_retired_service_document(instance, generation); }
    void outside() {
        require(std::this_thread::get_id() == thread && !depth && owner && !owner->callback_depth() &&
            !violation.load(std::memory_order_acquire),
            "raw candidate retained a provider/Host turn outside the owner pump");
        ++out.outside_owner_samples;
        const auto value = driver->state();
        require(value != NativeEngineState::blocked && value != NativeEngineState::process_exit_required,
            "raw candidate reached a blocked or process-terminal driver state");
    }
    void tick(Clock::time_point deadline) {
        require(Clock::now() < deadline, "raw candidate fixed runtime deadline expired");
        composition->tick(); outside();
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
};
}

NativeEngineExpectation document_actions_expectation(std::uint32_t system, std::uint32_t processor,
        const engine_document::Digest& recipe, const engine_document::Digest& build) {
    namespace actions = engine_document_actions; namespace doc = engine_document; namespace editor = engine_editor;
    actions::EngineDocumentActionsProfileFacts p;
    p.enabled = true; p.kind = actions::ProfileKind::document_actions; p.name = actions::kProfileName;
    p.provider_abi_major = 1; p.provider_abi_minor = 1; p.host_abi_major = 1; p.host_abi_minor = 0;
    p.target_system = system; p.target_processor = processor; p.pointer_bits = 64;
    p.lifetime = BIB_ENGINE_LIFETIME_PROCESS; p.maximum_starts = 1; p.viewport_width = 800; p.viewport_height = 600;
    p.provider_capabilities = actions::kProviderCapabilities; p.surface_capabilities = actions::kSurfaceCapabilities;
    p.surface_protocol_version = 2; p.editor_protocol_version = BIB_ENGINE_EDITOR_PROTOCOL_VERSION;
    p.base_header_sha256 = doc::kBaseHeaderSha256; p.document_header_sha256 = doc::kExtensionHeaderSha256;
    p.document_contract_sha256 = doc::kContractSha256; p.document_catalog_sha256 = doc::kCatalogSha256;
    p.physical_catalog_sha256 = doc::kPhysicalCatalogSha256; p.editor_header_sha256 = editor::kHeaderSha256;
    p.editor_contract_sha256 = editor::kContractSha256; p.editor_catalog_sha256 = editor::kCatalogSha256;
    p.editor_schema_sha256 = editor::kSchema; p.actions_header_sha256 = actions::kHeaderSha256;
    p.contract_sha256 = actions::kContractSha256; p.catalog_sha256 = actions::kCatalogSha256;
    p.schema_sha256 = actions::kSchema; p.ack_schema_sha256 = actions::kAckSchema;
    p.build_sha256 = build; p.source_recipe_sha256 = recipe;
    p.queries = actions::kQueries; p.commands = actions::kCommands;
    p.query_count = static_cast<std::uint32_t>(p.queries.size()); p.command_count = static_cast<std::uint32_t>(p.commands.size());
    require(actions::document_actions_profile_valid(p), "raw candidate requires exact independently selected4083 facts");
    return {system, processor, 64, p.contract_sha256, build, recipe, {}, {}, std::move(p)};
}

RawCandidateRuntimeObservations run_raw_candidate_offscreen_probe(Factory factory,
        const NativeEngineExpectation& expected, std::span<const std::uint8_t> bytes, const PackageInput& input) {
    require(!active && factory, "one raw candidate runtime is permitted per process");
    require(bytes.size() <= 4 * 1024 * 1024 && hash(bytes) == input.sha256,
        "raw candidate package differs from its independent bounded pin");
    auto package = read_package(bytes, input.index_offset, input.index_length);
    require(package.package_sha256 == input.sha256 && package.web.entry == "web/index.html" && !package.binary.present &&
        package.files.size() == 2,
        "raw candidate requires the independently pinned web-only runtime fixture Package");
    const auto* entry = package.find_file("web/index.html");
    constexpr std::string_view fixture_sha256 = "944b2ec5efa3a08d51429a1df36062b926478153103bd480a716f83780f48951";
    require(entry && entry->sha256 == fixture_sha256 && hash(entry->data) == fixture_sha256,
        "raw candidate Package HTML differs from the exact reviewed shared runtime fixture source");
    auto& s = *(active = new State); // Process-lived even after exceptions.
    ++s.out.getter_calls;
    require(factory(1, 1, sizeof(s.original), &s.original) == BIB_ENGINE_OK,
        "raw candidate getter rejected the exact public ABI1.1 request");
    (void)NativeEngineProvider::checked(s.original, expected); // Actual table BEFORE START.
    require(!s.out.starts && !s.out.enter_calls && !s.out.damage_callbacks,
        "raw candidate getter entered a supplied Host callback before START");
    auto proxy = s.original; proxy.start = State::start; proxy.advance = State::advance;
    proxy.current_document = State::current; proxy.command = State::command; proxy.query = State::query;
    proxy.deliver_services = State::deliver; proxy.collect_service_ack = State::ack;
    proxy.dispose_retired_service_document = State::dispose;
    EngineOwnerConfiguration configuration; configuration.document_actions_profile = expected.document_actions_profile;
    configuration.abandon_closed_document_outcomes = true;
    configuration.native_services = foundation::ui::demo_native_services();
    require(configuration.native_services.size() == 1 && configuration.native_services[0].descriptor.name == "demo.echo",
        "raw candidate shared demo.echo catalogue differs");
    auto original_echo = configuration.native_services[0].handler;
    configuration.native_services[0].handler = [&s, original_echo](std::uint32_t operation, auto request, auto response) {
        require(s.owner_thread() && s.owner && !s.depth && !s.owner->callback_depth(),
            "raw candidate native service ran inside a provider/Host callback");
        require(operation == 1 && request.size() == echo_payload.size() &&
            std::equal(request.begin(), request.end(), echo_payload.begin()), "raw candidate echo request differs");
        ++s.out.echo_calls; s.out.echo_request_bytes = request.size();
        const auto result = original_echo(operation, request, response);
        require(result.status == ServiceStatus::ok && result.bytes == request.size() &&
            std::equal(request.begin(), request.end(), response.begin()), "actual shared demo.echo result differs");
        s.out.echo_reply_bytes = result.bytes; return result;
    };
    s.owner = std::make_shared<EngineOwner>(std::move(package), std::move(configuration));
    NativeEngineOptions options; options.limits.maximum_command_bytes = BIB_ENGINE_EDITOR_MAX_WIRE_BYTES;
    options.limits.maximum_query_bytes = engine_editor::kQueryRequestMaximum;
    options.limits.maximum_reply_bytes = engine_document_actions::kReplyCapacity;
    options.ready_timeout = std::chrono::seconds(20); options.maximum_steps_per_tick = 8;
    s.driver = &NativeEngineDriver::bind_once(NativeEngineProvider::checked(proxy, expected), s.owner, options);
    s.driver->start_once(); s.outside();
    try { s.driver->start_once(); } catch (const std::logic_error&) { ++s.out.rejected_second_starts; }
    require(s.out.starts == 1 && s.out.rejected_second_starts == 1, "raw candidate repeated START reached the provider");
    s.composition = new foundation::ui::NativeEngineDocumentComposition(s.terminal, s.owner, *s.driver);
    s.terminal.terminal_size(100, 41); s.composition->drawable_cells(100, 40); s.composition->foreground(true);
    const auto deadline = Clock::now() + std::chrono::seconds(30);
    for (std::uint32_t ticks = 0; ticks != 30000; ++ticks) {
        s.tick(deadline);
        std::string displayed; for (const auto& line : s.terminal.render()) { displayed += line; displayed += '\n'; }
        if (s.composition->body_ready() && displayed.find(marker) != std::string::npos) {
            ++s.out.marker_observations; s.out.snapshot_revision = s.composition->view().revision;
            if (s.owner->frame() && s.out.echo_calls == 1 && s.out.service_ack_through >= 2) break;
        }
    }
    require(s.composition->body_ready() && s.composition->last_error().empty() && s.out.marker_observations &&
        s.out.echo_calls == 1 && s.out.service_ack_through >= 2 && s.out.query3_calls && s.out.semantic_revision,
        "raw candidate actual document/service/ACK probes did not complete");
    const auto& frame = s.owner->frame();
    require(frame && frame->width == 800 && frame->height == 600 && frame->stride == 3200 &&
        frame->rgba.size() == 1920000 && frame->frame_revision, "raw candidate has no actual full800x600 RGBA frame");
    s.out.frame_revision = frame->frame_revision; s.out.frame_sha256 = hash(frame->rgba);
    for (std::size_t at = 0; at < frame->rgba.size(); at += 4) {
        s.out.opaque_pixels += frame->rgba[at + 3] == 255;
        s.out.differing_pixels += !std::equal(frame->rgba.begin() + at, frame->rgba.begin() + at + 3, frame->rgba.begin());
    }
    require(s.out.opaque_pixels == 480000 && s.out.differing_pixels, "raw candidate frame is transparent or uniform");
    const auto identity = s.owner->identity(); s.out.application_instance = identity.application_instance;
    s.out.document_sequence = identity.document_sequence; s.out.service_generation = identity.service_generation;
    require(identity.application_instance && identity.document_sequence && identity.service_generation,
        "raw candidate actual document identity is incomplete");
    s.composition->shutdown();
    for (std::uint32_t ticks = 0; ticks != 10000 && s.driver->state() != NativeEngineState::detached; ++ticks) s.tick(deadline);
    s.out.final_state = static_cast<std::uint64_t>(s.driver->state());
    require(s.driver->state() == NativeEngineState::detached && s.composition->closed() && s.owner->closed() &&
        s.out.enter_calls && s.out.enter_calls == s.out.leave_calls && !s.violation.load(std::memory_order_acquire),
        "raw candidate did not close through the common composition/Driver owner turns");
    // State, Driver, Host shell and acquired OS handle remain process-lived.
    return s.out;
}

void write_observations_json(std::ostream& out, const RawCandidateRuntimeObservations& v) {
    out << '{';
#define RAW_NUMBER(name) out << "\"" #name "\":" << v.name << ','
    RAW_NUMBER(getter_calls); RAW_NUMBER(starts); RAW_NUMBER(rejected_second_starts); RAW_NUMBER(provider_entries);
    RAW_NUMBER(maximum_provider_depth); RAW_NUMBER(enter_calls); RAW_NUMBER(leave_calls); RAW_NUMBER(outside_owner_samples);
    RAW_NUMBER(query3_calls); RAW_NUMBER(query3_reply_bytes); RAW_NUMBER(semantic_revision); RAW_NUMBER(echo_calls);
    RAW_NUMBER(echo_request_bytes); RAW_NUMBER(echo_reply_bytes); RAW_NUMBER(service_ack_through); RAW_NUMBER(deliveries);
    RAW_NUMBER(damage_callbacks); RAW_NUMBER(frame_revision); RAW_NUMBER(opaque_pixels); RAW_NUMBER(differing_pixels);
    RAW_NUMBER(application_instance); RAW_NUMBER(document_sequence); RAW_NUMBER(service_generation);
    RAW_NUMBER(snapshot_revision); RAW_NUMBER(marker_observations); RAW_NUMBER(final_state);
#undef RAW_NUMBER
    out << "\"frame_sha256\":\"" << v.frame_sha256 << "\",\"query3_sha256\":\"" << v.query3_sha256 << "\"}";
}
} // namespace foundation::appended::raw_candidate
