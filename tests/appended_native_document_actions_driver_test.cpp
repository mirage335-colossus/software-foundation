// SPDX-License-Identifier: CC0-1.0
// Each scenario runs in a fresh process: native binding/terminal state is lived
// for the process. C-table mocks establish transport behavior only.
#include "appended_document_actions_fixture.hpp"
#include "../gui/shared/native_engine_driver.hpp"

#include <chrono>
#include <functional>
#include <string_view>
#include <thread>
#include <vector>

namespace {
using namespace document_actions_fixture;
using Clock = std::chrono::steady_clock;
using namespace std::chrono_literals;
constexpr std::uint64_t instance = UINT64_C(0x8000000000000044);
constexpr std::uint64_t first_document = UINT64_C(0x8000000000000001);
struct Fixture;
Fixture* active{};
enum class Behavior { ordinary, rejected_preentry, consumed_no_turn, unknown_no_turn, unknown_status, unknown_disposition,
    malformed_buffer, throw_entered, unbalanced };
struct Fixture {
    std::shared_ptr<EngineOwner> owner = std::make_shared<EngineOwner>(package(), configuration());
    NativeEngineDriver* driver{};
    BibEngineProviderV1 table{};
    NativeEngineExpectation expected{};
    BibEngineHostV1 host{};
    BibEngineDocumentV1 document{instance, first_document, 0};
    Clock::time_point now{1000s};
    std::vector<EngineDocumentWork> submitted;
    std::vector<std::uint32_t> operations;
    std::vector<std::uint64_t> sequences;
    unsigned calls{}, body_calls{}, form_calls{}, ack_calls{}, enters{}, leaves{}, starts{};
    bool inside{}, navigate{}, ack_wake{}, ack_foreign_wake{}, ack_enter{}, ack_unknown{}, ack_reenter{};
    unsigned ack_code{};
    Behavior behavior{Behavior::ordinary};
    Bytes last_response;

    Fixture() {
        check(!active, "one native actions fixture per process"); active = this;
        expected.document_actions_profile = profile(); const auto& p = expected.document_actions_profile;
        expected.target_system = p.target_system; expected.target_processor = p.target_processor; expected.pointer_bits = p.pointer_bits;
        expected.contract_header_sha256 = p.contract_sha256;
        expected.build_identity_sha256 = p.build_sha256; expected.source_recipe_sha256 = p.source_recipe_sha256;
        table.size = sizeof(table); table.abi_major = 1; table.abi_minor = 1;
        auto& build = table.build;
        build.size = sizeof(build); build.layout_revision = BIB_ENGINE_LAYOUT_V1;
        build.target_system = p.target_system; build.target_processor = p.target_processor; build.pointer_bits = p.pointer_bits;
        build.lifetime = BIB_ENGINE_LIFETIME_PROCESS; build.maximum_starts = 1;
        build.fixed_viewport_width = 800; build.fixed_viewport_height = 600; build.capabilities = p.provider_capabilities;
        std::copy(p.contract_sha256.begin(), p.contract_sha256.end(), build.contract_header_sha256);
        std::copy(p.build_sha256.begin(), p.build_sha256.end(), build.build_identity_sha256);
        std::copy(p.source_recipe_sha256.begin(), p.source_recipe_sha256.end(), build.source_recipe_sha256);
        table.limits = options().limits;
        table.start = start; table.advance = advance; table.current_document = current;
        table.query = query; table.command = command; table.deliver_services = deliver;
        table.collect_service_ack = collect; table.dispose_retired_service_document = dispose;
    }
    static NativeEngineOptions options() {
        NativeEngineOptions value;
        value.limits.maximum_command_bytes = BIB_ENGINE_EDITOR_MAX_WIRE_BYTES;
        value.limits.maximum_reply_bytes = actions::kReplyCapacity; value.maximum_steps_per_tick = 8;
        return value;
    }
    void ready() {
        driver = &NativeEngineDriver::bind_once(NativeEngineProvider::checked(table, expected), owner, options());
        driver->start_once(now); tick();
        check(starts == 1 && driver->state() == NativeEngineState::ready && owner->document_actions_enabled() &&
            !owner->document_profile().enabled && owner->document_actions_profile() == expected.document_actions_profile &&
            owner->input_enabled() && !owner->has_module(), "4083 startup did not preserve explicit independent profile");
    }
    void tick() { driver->tick(now += 1ms); }
    void healthy() const {
        check(driver->state() == NativeEngineState::ready && !owner->callback_depth() && !inside,
            "balanced actions fixture lost readiness");
    }
    template<class Function> std::int32_t turn(Function fn) {
        ++calls; check(!inside && !owner->callback_depth(), "recursive native action entry"); inside = true;
        check(host.enter_engine(host.context) == FOUNDATION_APPENDED_SERVICE_OK, "native action Host TURN refused"); ++enters;
        const auto status = fn(); host.leave_engine(host.context); ++leaves;
        check(owner->callback_depth() == 1, "native leave released outer call barrier too early"); inside = false; return status;
    }
    void begin() {
        BibEngineResourceEpochV1 epoch{}; epoch.size = sizeof(epoch);
        check(!document.service_generation && host.begin_resource_epoch(host.context, &document, &epoch) == BIB_ENGINE_OK &&
            epoch.resource_epoch && epoch.context && epoch.resolve && epoch.release, "prospective action resource epoch unavailable");
        document.service_generation = host.begin_service_document(host.context, &document);
        const auto id = owner->identity();
        check(document.service_generation && document.application_instance == id.application_instance &&
            document.document_sequence == id.document_sequence && document.service_generation == id.service_generation,
            "new action document lost full native identity");
    }
    EngineDocumentWork next(bool body = true) {
        const auto sequence = owner->reserve_document_sequence(); check(bool(sequence), "action reservation unavailable");
        return work(target(owner->identity()), *sequence, body);
    }
    EngineDocumentAdmission stage(EngineDocumentWork value) {
        submitted.push_back(value); const auto admission = owner->stage_document_work(std::move(value));
        check(admission.code == EngineDocumentAdmissionCode::admitted && admission.ticket, "driver action work rejected"); return admission;
    }
    std::shared_ptr<const EngineDocumentCompletion> complete(EngineDocumentAdmission a) {
        for (unsigned i = 0; i < 16 && !owner->document_outcome(a.ticket); ++i) tick();
        const auto done = owner->document_outcome(a.ticket); check(bool(done), "driver did not retain action completion"); return done;
    }
    EngineDocumentAdmission ack(const EngineDocumentWork& original, bool body) {
        const auto admission = body ? owner->stage_document_body_action_ack(original.target, original.request_sequence) :
            owner->stage_document_action_ack(original.target, original.request_sequence);
        check(admission.code == EngineDocumentAdmissionCode::admitted && admission.ticket, "driver metadata ACK rejected"); return admission;
    }
    const EngineDocumentWork& original(std::uint64_t sequence) const {
        const auto found = std::find_if(submitted.begin(), submitted.end(), [=](const auto& w) { return w.request_sequence == sequence; });
        check(found != submitted.end(), "provider received unsubmitted action sequence"); return *found;
    }
    void copy(BibEngineReplyBufferV1* buffer, const Bytes& bytes) {
        check(buffer && buffer->size == sizeof(*buffer) && buffer->bytes && buffer->capacity >= bytes.size(), "action reply buffer incomplete");
        std::copy(bytes.begin(), bytes.end(), buffer->bytes); last_response = bytes;
    }
    static std::int32_t BIB_ENGINE_CALL start(const BibEngineHostV1* host, const BibEngineStartV1* options,
            BibEngineStartResultV1* result) {
        auto& f = *active; ++f.starts;
        check(host && host->size == sizeof(*host) && host->abi_major == 1 && host->abi_minor == 0 && options && result &&
            result->size == sizeof(*result) && options->required_capabilities == actions::kProviderCapabilities &&
            options->limits.maximum_reply_bytes == actions::kReplyCapacity, "4083 startup C table/profile mismatch");
        f.host = *host; const auto status = f.turn([&] { f.begin(); return BIB_ENGINE_OK; });
        *result = {sizeof(*result), BIB_ENGINE_START_READY, instance}; return status;
    }
    static std::int32_t BIB_ENGINE_CALL advance(const BibEngineAdvanceV1* request) {
        auto& f = *active; check(request && request->application_instance == instance, "advance changed application");
        return f.turn([] { return BIB_ENGINE_OK; });
    }
    static std::int32_t BIB_ENGINE_CALL current(std::uint64_t application, BibEngineDocumentV1* result) {
        auto& f = *active; check(application == instance && result, "current changed application");
        return f.turn([&] { *result = f.document; return BIB_ENGINE_OK; });
    }
    static std::int32_t BIB_ENGINE_CALL query(const BibEngineQueryV1*, BibEngineReplyBufferV1*, BibEngineQueryResultV1*) {
        throw std::runtime_error("command10/11 route unexpectedly called query");
    }
    static std::int32_t BIB_ENGINE_CALL command(const BibEngineCommandV1* request, BibEngineReplyBufferV1* buffer,
            BibEngineCommandResultV1* result) {
        auto& f = *active;
        check(request && request->size == sizeof(*request) && request->request_sequence && !request->payload.reserved &&
            result && result->size == sizeof(*result), "command10/11 C record changed");
        f.operations.push_back(request->operation); f.sequences.push_back(request->request_sequence);
        *result = {sizeof(*result), 0, request->request_sequence, 0, 0};
        const bool metadata = request->operation == 7 || request->operation == 11;
        const bool body = request->operation == 10 || request->operation == 11;
        if (metadata) {
            ++f.calls; ++f.ack_calls;
            check(!f.inside && !f.owner->callback_depth() && request->payload.data && request->payload.length == 8 &&
                buffer && buffer->capacity == 16 && std::equal((body ? actions::kAckSchema : doc::kAckSchema).begin(),
                (body ? actions::kAckSchema : doc::kAckSchema).end(), request->schema_sha256), "ACK11 changed metadata-only schema/capacity");
            const auto original_sequence = get({request->payload.data, request->payload.length}, 0, 8);
            const auto& w = f.original(original_sequence);
            check(request->request_sequence > w.request_sequence && request->expected.application_instance == w.target.application_instance &&
                request->expected.document_sequence == w.target.document_sequence && request->expected.service_generation == w.target.service_generation,
                "metadata ACK rebased retained action target or sequence");
            if (f.ack_reenter) {
                const auto before = f.calls; bool rejected = false;
                try { f.driver->tick(f.now); } catch (const std::logic_error&) { rejected = true; }
                check(rejected && before == f.calls && !f.owner->callback_depth(), "recursive ACK11 entered provider/native work");
            }
            if (f.ack_wake) f.host.wake(f.host.context);
            if (f.ack_foreign_wake) { std::thread worker([&] { f.host.wake(f.host.context); }); worker.join(); }
            if (f.ack_enter) check(f.host.enter_engine(f.host.context) != FOUNDATION_APPENDED_SERVICE_OK, "ACK11 opened Host turn");
            const auto bytes = f.ack_unknown ? Bytes(16, 0xd7) : ack_raw(original_sequence,
                body == (w.kind == EngineDocumentWorkKind::body_action) ? f.ack_code : 2);
            f.copy(buffer, bytes); *result = {sizeof(*result), f.ack_unknown ? 2U : 1U, request->request_sequence, 16, f.ack_unknown ? 1U : 0U};
            check(!f.owner->callback_depth(), "metadata ACK11 acquired Owner TURN"); return BIB_ENGINE_OK;
        }
        check(request->operation == 10 || request->operation == 6, "body action selected unrelated native command");
        body ? ++f.body_calls : ++f.form_calls;
        const auto& w = f.original(request->request_sequence);
        check(w.kind == (body ? EngineDocumentWorkKind::body_action : EngineDocumentWorkKind::form_action) &&
            request->payload.data && request->payload.length == w.payload.size() &&
            std::equal(w.payload.begin(), w.payload.end(), request->payload.data) &&
            request->expected.application_instance == w.target.application_instance && request->expected.document_sequence == w.target.document_sequence &&
            request->expected.service_generation == w.target.service_generation &&
            std::equal(w.schema_sha256.begin(), w.schema_sha256.end(), request->schema_sha256) &&
            buffer && buffer->capacity == actions::kReplyCapacity, "body command10 lost owned bytes, target, schema or complete capacity");
        const auto fill = [&] {
            auto bytes = completion(w); f.copy(buffer, bytes);
            *result = {sizeof(*result), f.behavior == Behavior::unknown_disposition ? 2U : 1U,
                request->request_sequence, static_cast<std::uint32_t>(bytes.size()), f.behavior == Behavior::unknown_disposition ? 1U : 0U};
            if (f.behavior == Behavior::malformed_buffer) buffer->bytes = nullptr;
            if (f.navigate) { f.navigate = false; f.document = {instance, f.document.document_sequence + 1, 0}; f.begin(); }
        };
        if (f.behavior == Behavior::rejected_preentry || f.behavior == Behavior::consumed_no_turn || f.behavior == Behavior::unknown_no_turn) {
            ++f.calls;
            if (f.behavior == Behavior::rejected_preentry) return BIB_ENGINE_STALE;
            if (f.behavior == Behavior::unknown_no_turn) { result->disposition = 2; return BIB_ENGINE_PROCESS_EXIT_REQUIRED; }
            fill(); return BIB_ENGINE_OK;
        }
        if (f.behavior == Behavior::unbalanced) {
            ++f.calls; check(f.host.enter_engine(f.host.context) == FOUNDATION_APPENDED_SERVICE_OK, "unbalanced body fixture enter rejected");
            ++f.enters; fill(); return BIB_ENGINE_OK; // Intentionally no native LEAVE.
        }
        return f.turn([&] {
            if (f.behavior == Behavior::throw_entered) { f.inside = false; throw std::runtime_error("deliberate native action unwind"); }
            if (f.behavior == Behavior::unknown_status) { result->disposition = 2; return BIB_ENGINE_PROCESS_EXIT_REQUIRED; }
            fill(); return BIB_ENGINE_OK;
        });
    }
    static std::int32_t BIB_ENGINE_CALL deliver(const BibEngineDocumentV1*, const BibEngineBytesV1*) {
        throw std::runtime_error("action transport unexpectedly delivered services");
    }
    static std::uint32_t BIB_ENGINE_CALL collect(const BibEngineDocumentV1*) {
        throw std::runtime_error("action transport unexpectedly collected service ACK");
    }
    static std::int32_t BIB_ENGINE_CALL dispose(std::uint64_t application, std::uint64_t generation) {
        auto& f = *active; return f.turn([&] { check(application == instance && generation, "old disposal lost target"); return BIB_ENGINE_OK; });
    }
};

void metadata(Fixture& f) {
    const auto reject = [&](const std::function<void(BibEngineProviderV1&, NativeEngineExpectation&)>& mutate) {
        auto table = f.table; auto expected = f.expected; mutate(table, expected); bool rejected = false;
        try { (void)NativeEngineProvider::checked(table, expected); } catch (const std::invalid_argument&) { rejected = true; }
        check(rejected && !f.calls && !f.starts && !f.owner->configured(), "4083 metadata inspection admitted invalid profile or ran effects");
    };
    reject([](auto&, auto& e) { e.document_actions_profile = {}; });
    reject([](auto&, auto& e) { e.document_profile = legacy_profile(); });
    reject([](auto& t, auto&) { t.build.capabilities = 2035; });
    reject([](auto& t, auto&) { --t.limits.maximum_reply_bytes; });
    reject([](auto&, auto& e) { e.document_actions_profile.ack_schema_sha256 = doc::kAckSchema; });
    reject([](auto&, auto& e) { e.document_actions_profile.commands[8].operation = 7; });
    reject([](auto&, auto& e) { e.document_actions_profile.build_sha256[0] ^= 1; });
    reject([](auto& t, auto&) { std::copy(doc::kContractSha256.begin(), doc::kContractSha256.end(), t.build.contract_header_sha256); });
    (void)NativeEngineProvider::checked(f.table, f.expected);
    check(!f.calls && !f.starts && !f.owner->configured(), "valid 4083 metadata inspection ran provider effects");
}
void route_and_ack(Fixture& f, unsigned code, bool old, bool reenter) {
    f.ready(); f.navigate = old; f.ack_reenter = reenter; f.ack_code = code;
    const auto w = f.next(); auto source = w; const auto a = f.stage(source); std::fill(source.payload.begin(), source.payload.end(), 0);
    const auto done = f.complete(a); const auto raw = done->bytes;
    check(done->kind == EngineDocumentWorkKind::body_action && done->outcome == EngineDocumentOutcome::consumed &&
        done->target == w.target && done->request_sequence == w.request_sequence && raw == completion(w) &&
        !done->handled && !done->semantic_revision && !f.owner->consume_document_outcome(a.ticket) && !f.owner->reserve_document_sequence(),
        "command10 did not retain exact body result/global native debt");
    const auto before_enters = f.enters, before_leaves = f.leaves, before_calls = f.calls;
    const auto ack = f.ack(w, true); const auto receipt = f.complete(ack);
    check(receipt->kind == EngineDocumentWorkKind::body_action_ack && receipt->outcome == EngineDocumentOutcome::consumed &&
        receipt->bytes == ack_raw(w.request_sequence, code) && receipt->target == w.target && !receipt->handled &&
        !receipt->semantic_revision && f.ack_calls == 1 && f.calls == before_calls + 1 &&
        f.enters == before_enters && f.leaves == before_leaves && !f.owner->callback_depth() &&
        f.operations == std::vector<std::uint32_t>({10, 11}) && f.sequences[1] > f.sequences[0],
        "command11 lost metadata-only routing, original target or fresh global sequence");
    check(f.owner->consume_document_outcome(ack.ticket), "body ACK result did not collect");
    if (code == 2) {
        check(!f.owner->consume_document_outcome(a.ticket) && done == f.owner->document_outcome(a.ticket), "stale body ACK cleared native debt");
        f.ack_code = 0; const auto retry = f.ack(w, true); f.complete(retry);
        check(f.owner->consume_document_outcome(retry.ticket), "fresh body ACK after stale2 did not collect");
    }
    check(f.owner->consume_document_outcome(a.ticket) && done->bytes == raw, "checked body retirement lost immutable result"); f.healthy();
}
void cross_family(Fixture& f, bool body) {
    f.ready(); const auto w = f.next(body); const auto a = f.stage(w); const auto done = f.complete(a);
    const auto wrong = f.ack(w, !body); const auto stale = f.complete(wrong);
    check(stale->bytes == ack_raw(w.request_sequence, 2) && f.owner->consume_document_outcome(wrong.ticket) &&
        done == f.owner->document_outcome(a.ticket) && !f.owner->consume_document_outcome(a.ticket) && !f.owner->reserve_document_sequence(),
        "cross-family provider ACK lost stale2 or cleared native debt");
    const auto right = f.ack(w, body); f.complete(right);
    check(f.owner->consume_document_outcome(right.ticket) && f.owner->consume_document_outcome(a.ticket) &&
        f.operations == std::vector<std::uint32_t>({body ? 10u : 6u, body ? 7u : 11u, body ? 11u : 7u}),
        "correct family following stale ACK did not route through exact catalog"); f.healthy();
}
void rejected(Fixture& f) {
    f.ready(); f.behavior = Behavior::rejected_preentry; const auto w = f.next(); const auto a = f.stage(w);
    const auto enters = f.enters, leaves = f.leaves; const auto done = f.complete(a);
    check(done->outcome == EngineDocumentOutcome::rejected && done->provider_status == BIB_ENGINE_STALE && done->bytes.empty() &&
        !done->provider_disposition && !done->handled && !f.ack_calls && f.enters == enters && f.leaves == leaves &&
        f.owner->consume_document_outcome(a.ticket), "known body pre-entry rejection acquired a turn, raw success or ACK debt"); f.healthy();
}
void unknown(Fixture& f, bool disposition) {
    f.ready(); f.behavior = disposition ? Behavior::unknown_disposition : Behavior::unknown_status;
    const auto w = f.next(); const auto a = f.stage(w); const auto done = f.complete(a);
    check(done->outcome == EngineDocumentOutcome::unknown && done->provider_disposition == 2 &&
        done->target == w.target && done->request_sequence == w.request_sequence &&
        done->bytes == (disposition ? completion(w) : Bytes{}) && done->handled == disposition &&
        f.driver->state() == NativeEngineState::process_exit_required && !f.owner->callback_depth() && f.enters == f.leaves,
        "balanced body unknown lost original forensic result or terminal state");
    const auto calls = f.calls;
    for (unsigned i = 0; i < 3; ++i) { f.driver->request_advance(); f.tick(); }
    check(calls == f.calls && !f.ack_calls && done == f.owner->document_outcome(a.ticket) &&
        !f.owner->consume_document_outcome(a.ticket) && !f.owner->reserve_document_sequence(), "body unknown replayed or reopened native work");
}
void invalid_body(Fixture& f, Behavior behavior) {
    f.ready(); f.behavior = behavior; const auto a = f.stage(f.next()); f.tick();
    check(f.body_calls == 1 && f.driver->state() == NativeEngineState::process_exit_required && !f.owner->document_outcome(a.ticket),
        "unobserved/malformed body return fabricated a complete result");
    const auto calls = f.calls; for (unsigned i = 0; i < 3; ++i) f.tick();
    check(calls == f.calls && !f.ack_calls && !f.owner->document_outcome(a.ticket), "terminal body fault replayed native command/ACK");
}
void invalid_ack(Fixture& f, std::string_view variant) {
    f.ready(); const auto w = f.next(); const auto a = f.stage(w); const auto done = f.complete(a);
    f.ack_wake = variant == "ack-host-callback"; f.ack_foreign_wake = variant == "ack-host-callback-foreign";
    f.ack_enter = variant == "ack-host-enter"; f.ack_unknown = variant == "ack-unknown";
    const auto enters = f.enters, leaves = f.leaves; const auto ack = f.ack(w, true); f.tick();
    const auto receipt = f.owner->document_outcome(ack.ticket);
    check(f.ack_calls == 1 && f.driver->state() == NativeEngineState::process_exit_required && !f.owner->callback_depth() &&
        f.enters == enters && f.leaves == leaves && done == f.owner->document_outcome(a.ticket) &&
        !f.owner->consume_document_outcome(a.ticket), "ACK11 callback/unknown lost metadata-only terminal failure or cleared debt");
    if (f.ack_unknown) check(receipt && receipt->outcome == EngineDocumentOutcome::unknown && receipt->bytes == Bytes(16, 0xd7) &&
        receipt->handled && receipt->provider_disposition == 2 && !f.owner->consume_document_outcome(ack.ticket),
        "unknown ACK11 lost opaque raw16 forensic bytes or fabricated retirement");
    else check(!receipt, "ACK11 Host callback fabricated successful completion");
    const auto calls = f.calls; for (unsigned i = 0; i < 3; ++i) f.tick();
    check(calls == f.calls && f.ack_calls == 1 && done == f.owner->document_outcome(a.ticket), "terminal ACK11 replayed provider or replaced debt");
}
void run(std::string_view scenario) {
    auto& f = *new Fixture; // Process-lived callbacks/binding are intentionally retained.
    if (scenario == "metadata") return metadata(f);
    if (scenario == "body-ack0") return route_and_ack(f, 0, false, false);
    if (scenario == "body-ack1") return route_and_ack(f, 1, false, false);
    if (scenario == "body-old-ack1") return route_and_ack(f, 1, true, false);
    if (scenario == "body-old-ack2") return route_and_ack(f, 2, true, false);
    if (scenario == "ack-reentry") return route_and_ack(f, 0, false, true);
    if (scenario == "form-cross-body-ack") return cross_family(f, false);
    if (scenario == "body-cross-form-ack") return cross_family(f, true);
    if (scenario == "body-rejected-preentry") return rejected(f);
    if (scenario == "body-unknown-status") return unknown(f, false);
    if (scenario == "body-unknown-disposition") return unknown(f, true);
    if (scenario == "body-consumed-no-turn") return invalid_body(f, Behavior::consumed_no_turn);
    if (scenario == "body-unknown-no-turn") return invalid_body(f, Behavior::unknown_no_turn);
    if (scenario == "body-malformed-buffer") return invalid_body(f, Behavior::malformed_buffer);
    if (scenario == "body-throw") return invalid_body(f, Behavior::throw_entered);
    if (scenario == "body-unbalanced") return invalid_body(f, Behavior::unbalanced);
    if (scenario == "ack-host-callback" || scenario == "ack-host-callback-foreign" || scenario == "ack-host-enter" || scenario == "ack-unknown")
        return invalid_ack(f, scenario);
    throw std::runtime_error("unknown document-actions driver scenario");
}
} // namespace

int main(int argc, char** argv) {
    try {
        check(argc == 2, "Usage: appended-native-document-actions-driver-test SCENARIO (fresh process)"); run(argv[1]);
        std::cout << "native document-actions driver mock passed: " << argv[1] << " (" << assertions << " checks)\n"; return 0;
    } catch (const std::exception& error) {
        std::cerr << "native document-actions driver mock: " << error.what() << '\n'; return 1;
    }
}
