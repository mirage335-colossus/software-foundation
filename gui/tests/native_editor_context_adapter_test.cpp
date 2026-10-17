// SPDX-License-Identifier: CC0-1.0
// Pure mailbox/Controller integration. No engine, browser or native input runs.
#include "native_editor_context_adapter.hpp"

#include <atomic>
#include <cstddef>
#include <functional>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <thread>
#include <utility>
#include <vector>

using namespace foundation::ui::native_editor;

namespace {
std::size_t checks{};
void check(bool condition, const char* detail) {
    ++checks;
    if (!condition) throw std::runtime_error(detail);
}
NativeProjection initial() {
    NativeProjection result;
    result.identity = {{"editor", 3}, 11, 4, 5, 6};
    result.editor_revision = 9007199254740993ull;
    result.surrounding = "abc";
    result.selection = {3, 3};
    result.mapping_id = 1;
    result.frame_id = 2;
    result.readback_attested = true;
    result.caret = {12, 24, 1, 18};
    return result;
}
TextObservation observed(const std::string& value, ByteRange selection) {
    return {value, selection.begin, selection.end, Direction::none, selection, value.size()};
}
Packet text_packet(const Basis& basis, std::uint64_t id = 1,
                   std::optional<std::uint64_t> predecessor = {}) {
    Packet packet;
    packet.session = 8;
    packet.basis = basis;
    auto& observation = packet.observation;
    observation.id = id;
    observation.predecessor = predecessor;
    observation.kind = Kind::text;
    observation.authority = Authority::range;
    observation.before = observed(basis.surrounding, basis.selection);
    auto proxy_value = basis.surrounding;
    proxy_value.replace(basis.selection.begin, basis.selection.end - basis.selection.begin, "X");
    const auto cursor = basis.selection.begin + 1;
    observation.after = observed(proxy_value, {cursor, cursor});
    TextData data;
    data.input_type = "insertText";
    data.text = "X";
    data.replacement = basis.selection;
    observation.data = std::move(data);
    return packet;
}
Packet key_packet(const Basis& basis, std::uint64_t id = 1) {
    Packet packet;
    packet.session = 8;
    packet.basis = basis;
    auto& observation = packet.observation;
    observation.id = id;
    observation.kind = Kind::key;
    observation.authority = Authority::native;
    observation.group = 9;
    observation.before = observed(basis.surrounding, basis.selection);
    observation.after = observation.before;
    KeyData key;
    key.transition.key = "a";
    key.transition.code = "KeyA";
    observation.data = std::move(key);
    return packet;
}
NativeResult applied(const NativeProjection& projection) {
    NativeResult result;
    result.outcome = Outcome::applied;
    result.projection = projection;
    return result;
}
NativeResult unavailable(const NativeProjection& previous, Outcome outcome = Outcome::cancelled) {
    NativeResult result;
    result.outcome = outcome;
    result.continuity = Continuity::replaced;
    result.availability = NativeAvailability::unavailable;
    result.observation_revision = 71;
    result.readback_identity = previous.identity;
    result.readback_attested = true;
    return result;
}
struct TerminalCounter {
    std::atomic<unsigned> calls{};
    static void notify(void* context) noexcept {
        static_cast<TerminalCounter*>(context)->calls.fetch_add(1, std::memory_order_relaxed);
    }
    EditorTerminalHook hook() noexcept { return {this, notify}; }
};
struct AsyncFixture {
    TerminalCounter terminal;
    NativeProjection live = initial();
    std::vector<EditorPublication> delivered;
    std::function<bool(const EditorPublication&)> on_publish;
    unsigned publication_attempts{};
    NativeEditorContextAdapter adapter;

    AsyncFixture()
        : adapter([this](const EditorPublication& value) {
            ++publication_attempts;
            if (on_publish && !on_publish(value)) return false;
            delivered.push_back(value);
            return true;
        }, terminal.hook()) { }
    ContextRequest next() {
        auto request = adapter.prepare();
        check(request.has_value(), "Expected an offered native transport stage");
        return std::move(*request);
    }
    void activate() {
        check(adapter.request_projection(), "Initial projection poll was not queued");
        const auto request = next();
        check(request.kind == ContextRequest::Kind::projection && request.ticket && !request.head_ticket &&
              !request.mapping_id && !request.request && !request.revocation && !request.retirement,
              "Detached activation did not request a fresh idle projection");
        check(!adapter.prepare(), "One initial projection poll was offered twice");
        check(adapter.supply_projection(request.ticket, live), "Initial native projection was rejected");
        check(adapter.available() && adapter.publication() && adapter.publication()->basis &&
              adapter.projection() && *adapter.projection() == live && !adapter.publication()->settlement &&
              !adapter.publication()->retirement && !adapter.pending(),
              "Checked initial projection did not activate the published editor");
    }
    Basis basis() const {
        const auto* publication = adapter.publication();
        check(publication && publication->basis, "Fixture has no published editor basis");
        return *publication->basis;
    }
    Packet packet(std::uint64_t id = 1, std::optional<std::uint64_t> predecessor = {}) const {
        return text_packet(basis(), id, predecessor);
    }
    ContextRequest observation(std::uint64_t head) {
        const auto projection = next();
        check(projection.kind == ContextRequest::Kind::projection && projection.head_ticket == head &&
              projection.mapping_id == live.mapping_id && !projection.request,
              "Observation did not resolve its retained head mapping first");
        check(adapter.supply_projection(projection.ticket, live), "Actual head projection was rejected");
        auto effect = next();
        check(effect.kind == ContextRequest::Kind::observation && effect.head_ticket == head &&
              effect.ticket != projection.ticket && effect.request && !effect.revocation && !effect.retirement,
              "Projection did not produce one distinct observation stage");
        return effect;
    }
    EditorCompletion completion(std::uint64_t head) {
        auto result = adapter.take_completion(head);
        check(result.has_value() && result->ticket == head, "Expected the correlated browser-head completion");
        check(!adapter.take_completion(head), "A browser completion was released twice");
        return std::move(*result);
    }
};
struct FakeBackend final : Backend {
    NativeProjection live = initial();
    unsigned projects{}, effects{}, revocations{};
    std::optional<NativeProjection> project(std::uint64_t mapping) override {
        ++projects;
        check(mapping == live.mapping_id, "Synchronous adapter passed another native mapping");
        return live;
    }
    NativeResult apply(const NativeRequest& request) override {
        ++effects;
        check(request.resolved == live && request.packet.observation.id == 1,
              "Synchronous adapter changed the owned native request");
        live.surrounding = "native author result";
        live.selection = {0, 0};
        live.editor_revision = 3;
        return applied(live);
    }
    NativeResult revoke(const Revocation&) override {
        ++revocations;
        auto result = applied(live);
        result.composition_readback_attested = true;
        return result;
    }
};
}

int main() {
    unsigned cases{}, failures{};
    const auto run = [&](const char* name, const std::function<void()>& body) {
        ++cases;
        try { body(); }
        catch (const std::exception& error) {
            ++failures;
            std::cerr << name << ": " << error.what() << '\n';
        }
    };
    run("Explicit projection polling activates only after checked publication", [] {
        AsyncFixture f;
        check(!f.adapter.available() && !f.adapter.pending() && !f.adapter.publication() &&
              !f.adapter.projection() && !f.adapter.prepare() && !f.publication_attempts,
              "Construction invented native projection or called publication");
        bool inspected_staged_geometry = false;
        f.on_publish = [&](const EditorPublication& value) {
            check(value.basis && value.basis->editor_revision == 9007199254740993ull &&
                  value.basis->surrounding == "abc" && !value.settlement,
                  "Initial publication narrowed revision or invented settlement");
            check(f.adapter.projection() && *f.adapter.projection() == f.live,
                  "Publisher could not inspect the matching checked geometry");
            check(!f.adapter.prepare() && !f.adapter.take_completion(0),
                  "Publication callback entered native work or released completion");
            inspected_staged_geometry = true;
            return true;
        };
        f.activate();
        check(inspected_staged_geometry && f.delivered.size() == 1 && !f.terminal.calls,
              "Initial checked publication did not complete exactly once");
    });
    run("Initial null projection publishes availability without claiming owned retirement", [] {
        AsyncFixture f;
        check(f.adapter.request_projection(), "Initial null-projection poll was not queued");
        const auto poll = f.next();
        RetirementReadback readback;
        readback.availability = NativeAvailability::unavailable;
        readback.identity = f.live.identity;
        readback.observation_revision = 70;
        readback.readback_attested = true;
        check(!readback.authority_retired && f.adapter.supply_projection(poll.ticket, {}, readback),
              "Checked unavailable projection was not accepted");
        check(!f.adapter.available() && !f.adapter.pending() && !f.adapter.terminal() && !f.terminal.calls &&
              f.delivered.size() == 1 && !f.delivered.back().basis && !f.delivered.back().settlement &&
              f.delivered.back().retirement && *f.delivered.back().retirement == readback &&
              !f.delivered.back().retirement->authority_retired && !f.adapter.take_completion(0),
              "An initial availability observation invented native-owned closure or a browser receipt");
    });
    run("Ingress owns packet bytes and callback guards defer owner entry", [] {
        AsyncFixture f;
        f.activate();
        auto packet = f.packet();
        const auto owned = packet;
        unsigned before_head_calls{};
        f.adapter.enter_callback();
        f.adapter.enter_callback();
        const auto head = f.adapter.submit(packet);
        check(head && f.adapter.pending(), "Callback ingress did not retain its packet");
        packet.basis.surrounding = "foreign";
        std::get<TextData>(packet.observation.data).text = "foreign";
        check(!f.adapter.prepare([&] { ++before_head_calls; return true; }) && !before_head_calls &&
              !f.adapter.take_completion(*head), "Nested callback entered or completed native work");
        f.adapter.leave_callback();
        check(!f.adapter.prepare(), "Outer callback guard was released by the nested leave");
        f.adapter.leave_callback();
        check(!f.adapter.prepare([&] { ++before_head_calls; return false; }) &&
              !f.adapter.take_completion(*head) && !f.adapter.terminal(),
              "A busy before-head gate consumed the browser packet");
        const auto projection = f.adapter.prepare([&] { ++before_head_calls; return true; });
        check(projection && projection->head_ticket == *head && before_head_calls == 2,
              "Before-head admission did not retain the same original head");
        f.adapter.enter_callback();
        check(!f.adapter.supply_projection(projection->ticket, f.live),
              "Native projection callback entered an ingress callback");
        f.adapter.leave_callback();
        check(f.adapter.supply_projection(projection->ticket, f.live), "Guard rejection consumed projection stage");
        const auto effect = f.next();
        check(effect.request && effect.request->packet == owned,
              "Queued browser packet borrowed subsequently modified ingress values");
        f.adapter.enter_callback();
        check(!f.adapter.complete(effect.ticket, applied(f.live)),
              "Native effect completion entered an ingress callback");
        f.adapter.leave_callback();
        check(f.adapter.complete(effect.ticket, applied(f.live)), "Guard rejection consumed effect stage");
        check(f.completion(*head).result.admission == Admission::completed && !f.terminal.calls,
              "Guarded work did not finish after the serialized owner turn");
    });
    run("Unsent stage deferral preserves tickets and cannot duplicate an effect", [] {
        AsyncFixture f;
        f.activate();
        const auto packet = f.packet();
        const auto head = f.adapter.submit(packet);
        check(head.has_value(), "Observation ingress failed");
        unsigned begins{};
        const auto projection = f.adapter.prepare([&] { ++begins; return true; });
        check(projection && !f.adapter.prepare() && !f.adapter.defer(projection->ticket + 1000) &&
              !f.adapter.supply_projection(projection->ticket + 1000, f.live),
              "Unrelated transport stage consumed the active projection");
        check(f.adapter.defer(projection->ticket), "Busy projection owner could not defer unsent work");
        const auto retried_projection = f.adapter.prepare([&] { ++begins; return true; });
        check(retried_projection && retried_projection->ticket == projection->ticket &&
              retried_projection->head_ticket == *head && retried_projection->mapping_id == projection->mapping_id && begins == 1,
              "Projection deferral began a second controller head or changed correlation");
        check(f.adapter.supply_projection(retried_projection->ticket, f.live), "Deferred projection was not accepted");
        check(!f.adapter.supply_projection(projection->ticket, f.live), "Duplicate projection callback was accepted");
        const auto effect = f.next();
        check(effect.request && effect.request->packet == packet && !f.adapter.prepare(),
              "Effect stage changed request or was offered more than once");
        check(f.adapter.defer(effect.ticket), "Unsent observation stage could not be deferred");
        const auto retried_effect = f.next();
        check(retried_effect.ticket == effect.ticket && retried_effect.head_ticket == *head &&
              retried_effect.request && retried_effect.request->packet == effect.request->packet &&
              retried_effect.request->resolved == effect.request->resolved,
              "Deferred observation changed native request or stage identity");
        check(f.adapter.complete(retried_effect.ticket, applied(f.live)) &&
              !f.adapter.complete(effect.ticket, applied(f.live)) && !f.adapter.defer(effect.ticket),
              "Completed effect was accepted or rearmed a second time");
        check(f.completion(*head).result.admission == Admission::completed && f.delivered.size() == 2,
              "One retained head did not publish exactly one native completion");
    });
    run("Real controller causality and actual native state determine publication", [] {
        AsyncFixture f;
        f.activate();
        const auto packet = f.packet(7);
        const auto head = f.adapter.submit(packet);
        check(head.has_value(), "First causal packet was not queued");
        const auto effect = f.observation(*head);
        check(effect.request->packet == packet, "Adapter did not retain actual typed controller packet");
        auto actual = f.live;
        actual.surrounding = "author script";
        actual.selection = {0, 0};
        actual.editor_revision = 3;
        actual.mapping_id = 10;
        f.live = actual;
        check(f.adapter.complete(effect.ticket, applied(actual)), "Native result was not accepted");
        const auto completed = f.completion(*head);
        check(completed.result.admission == Admission::completed && completed.result.receipt &&
              completed.result.receipt->basis && completed.result.receipt->basis->surrounding == "author script" &&
              completed.result.receipt->basis->editor_revision == 3 && f.basis() == *completed.result.receipt->basis,
              "UA after-text replaced the actual native projection or opaque revision");
        const Settlement expected{8, 7, packet.basis.token, {}};
        check(f.adapter.publication()->settlement == expected, "Publication lost causal receipt correlation");
        const auto next = f.packet(12, 7);
        const auto next_head = f.adapter.submit(next);
        check(next_head.has_value(), "Gap-preserving causal successor was not queued");
        const auto next_effect = f.observation(*next_head);
        check(next_effect.request->packet == next && f.adapter.complete(next_effect.ticket, applied(f.live)),
              "Actual controller rejected the published causal successor");
        check(f.completion(*next_head).result.admission == Admission::completed, "Causal successor did not finish");
        const auto foreign = f.packet(13, 999);
        const auto foreign_head = f.adapter.submit(foreign);
        check(foreign_head && !f.adapter.prepare(), "Foreign predecessor reached native projection/effect");
        const auto rejected = f.completion(*foreign_head);
        check(rejected.result.admission == Admission::rejected && rejected.result.receipt &&
              rejected.result.receipt->outcome == Outcome::rejected && !f.adapter.terminal(),
              "Known causal rejection was guessed as an effect or terminal failure");
    });
    run("Changed checked projection rejects before native edit and publishes actual basis", [] {
        AsyncFixture f;
        f.activate();
        const auto packet = f.packet();
        const auto head = f.adapter.submit(packet);
        check(head.has_value(), "Changed-mapping fixture ingress failed");
        const auto projection = f.next();
        auto changed = f.live;
        changed.mapping_id = 90;
        changed.editor_revision = 2;
        changed.surrounding = "native replacement";
        changed.selection = {0, 0};
        check(f.adapter.supply_projection(projection.ticket, changed) && !f.adapter.prepare(),
              "Changed checked mapping escaped as a native observation effect");
        const auto completed = f.completion(*head);
        check(completed.result.admission == Admission::rejected && completed.result.receipt &&
              completed.result.receipt->outcome == Outcome::rejected && completed.result.receipt->basis &&
              f.basis().surrounding == changed.surrounding && f.basis().editor_revision == 2 &&
              f.adapter.projection() && *f.adapter.projection() == changed && !f.adapter.terminal(),
              "Changed native mapping lost its known actual readback");
    });
    run("Publication precedes completion and exposes matching staged geometry", [] {
        AsyncFixture f;
        f.activate();
        const auto head = f.adapter.submit(f.packet());
        check(head.has_value(), "Publication-order ingress failed");
        const auto effect = f.observation(*head);
        auto actual = f.live;
        actual.surrounding = "actual edit";
        actual.selection = {1, 1};
        ++actual.editor_revision;
        actual.caret = {50, 60, 2, 20};
        bool publication_seen = false;
        f.on_publish = [&](const EditorPublication& value) {
            check(value.basis && value.basis->surrounding == actual.surrounding && value.settlement &&
                  value.settlement->id == 1 && f.adapter.projection() && *f.adapter.projection() == actual,
                  "Publisher observed unrelated or stale native geometry");
            check(!f.adapter.take_completion(*head) && !f.adapter.prepare(),
                  "Completion/native entry escaped inside strong publication");
            publication_seen = true;
            return true;
        };
        check(!f.adapter.take_completion(*head) && f.adapter.complete(effect.ticket, applied(actual)) && publication_seen,
              "Native completion was released without actual publication");
        check(f.completion(*head).result.admission == Admission::completed && f.basis().surrounding == "actual edit",
              "Accepted strong publication did not release the correlated completion");
    });
    run("Rejected or throwing publication makes consumed native work terminal", [] {
        for (bool throws : {false, true}) {
            AsyncFixture f;
            f.activate();
            const auto packet = f.packet();
            const auto head = f.adapter.submit(packet);
            check(head.has_value(), "Failure fixture ingress failed");
            const auto effect = f.observation(*head);
            bool completion_escaped = false;
            f.on_publish = [&](const EditorPublication&) -> bool {
                // An exception here is intentionally caught by the adapter;
                // retain this observation for an assertion outside that catch.
                completion_escaped = f.adapter.take_completion(*head).has_value();
                if (throws) throw std::runtime_error("deliberate publication rejection");
                return false;
            };
            check(f.adapter.complete(effect.ticket, applied(f.live)), "Owned native result was not correlated");
            const auto completed = f.completion(*head);
            check(!completion_escaped && completed.result.admission == Admission::terminal && completed.result.receipt &&
                  completed.result.receipt->outcome == Outcome::unknown && !completed.result.receipt->default_token &&
                  f.adapter.terminal() && f.terminal.calls == 1 && !f.adapter.publication() && !f.adapter.available() &&
                  f.delivered.size() == 1 && !f.adapter.submit(packet),
                  "Failed publication exposed reusable native authority or a known outcome");
            check(!f.adapter.prepare() && !f.adapter.complete(effect.ticket, applied(f.live)) && f.terminal.calls == 1,
                  "Terminal publication failure replayed the consumed effect");
        }
    });
    run("Malformed native result never becomes a guessed successful publication", [] {
        for (unsigned variant = 0; variant < 4; ++variant) {
            AsyncFixture f;
            f.activate();
            const auto packet = f.packet();
            const auto head = f.adapter.submit(packet);
            check(head.has_value(), "Malformed-result fixture ingress failed");
            const auto effect = f.observation(*head);
            auto result = applied(f.live);
            if (variant == 0) result.projection->readback_attested = false;
            if (variant == 1) result.projection.reset();
            if (variant == 2) result.outcome = Outcome::unknown;
            if (variant == 3) ++result.projection->identity.context;
            check(f.adapter.complete(effect.ticket, result), "Malformed result was not correlated to the active stage");
            const auto completed = f.completion(*head);
            check(completed.result.admission == Admission::terminal && completed.result.receipt &&
                  completed.result.receipt->outcome == Outcome::unknown && !f.adapter.available() &&
                  !f.adapter.publication() && f.adapter.terminal() && f.terminal.calls == 1 && f.delivered.size() == 1,
                  "Malformed result became checked editable state or known completion");
        }
    });
    run("Late and foreign failure tickets cannot terminate a newer native stage", [] {
        AsyncFixture f;
        f.activate();
        const auto first_head = f.adapter.submit(f.packet());
        check(first_head.has_value(), "First failure-correlation head was not queued");
        const auto first_effect = f.observation(*first_head);
        check(f.adapter.complete(first_effect.ticket, applied(f.live)), "First correlated effect did not finish");
        check(f.completion(*first_head).result.admission == Admission::completed, "First completion missing");
        const auto second_head = f.adapter.submit(f.packet(2, 1));
        check(second_head.has_value(), "Second failure-correlation head was not queued");
        const auto second_projection = f.next();
        bool old_failure = true;
        std::thread late([&] { old_failure = f.adapter.notify_transport_failure(first_effect.ticket); });
        late.join();
        check(!old_failure && !f.adapter.terminal() && !f.terminal.calls &&
              !f.adapter.supply_projection(first_effect.ticket, f.live),
              "Late failure/callback terminated or consumed a newer active stage");
        check(f.adapter.supply_projection(second_projection.ticket, f.live), "Late callback damaged current projection");
        const auto second_effect = f.next();
        bool active_failure = false;
        const auto published = f.delivered.size();
        std::thread foreign([&] { active_failure = f.adapter.notify_transport_failure(second_effect.ticket); });
        foreign.join();
        check(active_failure && f.adapter.terminal() && f.terminal.calls == 1 &&
              f.delivered.size() == published && !f.adapter.prepare() &&
              !f.adapter.complete(second_effect.ticket, applied(f.live)),
              "Correlated foreign failure entered publication, replayed native work or missed terminal notification");
    });
    run("Null receipt waits for exact owned native retirement before publication", [] {
        AsyncFixture f;
        f.live.retire = NativeRetireMaterial{42, f.live.mapping_id, f.live.identity.context, 0};
        f.activate();
        const auto packet = f.packet();
        const auto head = f.adapter.submit(packet);
        check(head.has_value(), "Retirement fixture ingress failed");
        const auto effect = f.observation(*head);
        const auto original = *f.live.retire;
        const auto before = f.delivered.size();
        check(f.adapter.complete(effect.ticket, unavailable(f.live)) && !f.adapter.take_completion(*head) &&
              f.delivered.size() == before && !f.adapter.available(),
              "Null-basis receipt escaped before old provider authority was retired");
        const auto cleanup = f.next();
        check(cleanup.kind == ContextRequest::Kind::revoke && cleanup.head_ticket == *head &&
              cleanup.ticket != effect.ticket && cleanup.retirement && cleanup.retirement->material == original &&
              cleanup.retirement->identity == f.live.identity && !cleanup.request,
              "Owned cleanup did not retain the exact original provider token/mapping/context");
        check(!f.adapter.prepare() && !f.adapter.complete(effect.ticket, unavailable(f.live)) &&
              !f.adapter.take_completion(*head), "Duplicate original callback bypassed pending cleanup");
        check(f.adapter.defer(cleanup.ticket), "Busy native retirement owner could not defer unsent owned cleanup");
        const auto retry = f.next();
        check(retry.ticket == cleanup.ticket && retry.retirement && retry.retirement->material == original &&
              retry.retirement->identity == cleanup.retirement->identity,
              "Deferred cleanup lost the original retirement authority");
        auto closed = unavailable(f.live, Outcome::applied);
        closed.observation_revision = 72;
        closed.retired = original;
        check(f.adapter.complete(retry.ticket, closed), "Actual provider closure was not accepted");
        const auto completed = f.completion(*head);
        check(completed.result.admission == Admission::completed && completed.result.receipt &&
              completed.result.receipt->session == packet.session && completed.result.receipt->id == packet.observation.id &&
              completed.result.receipt->submitted_token == packet.basis.token &&
              completed.result.receipt->predecessor == packet.observation.predecessor &&
              completed.result.receipt->outcome == Outcome::cancelled && !completed.result.receipt->basis &&
              completed.result.receipt->retirement && completed.result.receipt->retirement->observation_revision == 72 &&
              completed.result.receipt->retirement->identity == f.live.identity &&
              completed.result.receipt->retirement->authority_retired &&
              f.delivered.size() == before + 1 &&
              !f.delivered.back().basis && f.delivered.back().settlement && f.delivered.back().settlement->id == packet.observation.id &&
              f.delivered.back().retirement && f.delivered.back().retirement->authority_retired &&
              !f.adapter.available() && !f.adapter.terminal() && !f.terminal.calls,
              "Actual closure invented an editable basis or lost the held observation receipt");
    });
    run("Forged owned cleanup cannot release the held null receipt", [] {
        for (unsigned variant = 0; variant < 5; ++variant) {
            AsyncFixture f;
            f.live.retire = NativeRetireMaterial{42, f.live.mapping_id, f.live.identity.context, 0};
            f.activate();
            const auto head = f.adapter.submit(f.packet());
            check(head.has_value(), "Forged-cleanup fixture ingress failed");
            const auto effect = f.observation(*head);
            check(f.adapter.complete(effect.ticket, unavailable(f.live)) && !f.adapter.take_completion(*head),
                  "Forged-cleanup fixture did not retain its original null receipt");
            const auto cleanup = f.next();
            check(cleanup.kind == ContextRequest::Kind::revoke && cleanup.retirement,
                  "Forged-cleanup fixture did not offer owned retirement");
            auto forged = unavailable(f.live, Outcome::applied);
            forged.retired = f.live.retire;
            if (variant == 0) ++forged.retired->token;
            if (variant == 1) ++forged.retired->mapping_id;
            if (variant == 2) ++forged.retired->input_context;
            if (variant == 3) ++forged.retired->composition;
            if (variant == 4) forged.retired.reset();
            check(f.adapter.complete(cleanup.ticket, forged), "Malformed cleanup was not correlated to its stage");
            const auto completed = f.completion(*head);
            check(completed.result.admission == Admission::terminal && f.adapter.terminal() &&
                  f.terminal.calls == 1 && f.delivered.size() == 1 && !f.adapter.publication() &&
                  !f.adapter.available() && !f.adapter.prepare(),
                  "Unproven provider cleanup released the held receipt as a known published result");
        }
    });
    run("Explicit revocation carries owned request and exact provider retirement", [] {
        AsyncFixture f;
        f.live.retire = NativeRetireMaterial{42, f.live.mapping_id, f.live.identity.context, 0};
        f.activate();
        Revocation revoke;
        revoke.basis = f.basis();
        revoke.incarnation = 9;
        revoke.reason = "blur";
        const auto owned = revoke;
        f.adapter.enter_callback();
        const auto head = f.adapter.queue_revoke(revoke);
        revoke.reason = "changed after ingress";
        check(head && !f.adapter.prepare(), "Revocation ingress entered native callback work");
        f.adapter.leave_callback();
        const auto projection = f.next();
        check(projection.kind == ContextRequest::Kind::projection && projection.head_ticket == *head &&
              f.adapter.supply_projection(projection.ticket, f.live), "Revocation did not resolve owned native mapping");
        const auto effect = f.next();
        check(effect.kind == ContextRequest::Kind::revoke && effect.revocation && *effect.revocation == owned &&
              effect.retirement && effect.retirement->material == *f.live.retire &&
              effect.retirement->observed && *effect.retirement->observed == owned,
              "Queued revocation lost its copied observation or exact provider ownership");
        auto closed = unavailable(f.live, Outcome::applied);
        closed.retired = f.live.retire;
        check(f.adapter.complete(effect.ticket, closed), "Owned revocation result was not accepted");
        const auto completed = f.completion(*head);
        check(completed.result.admission == Admission::completed && !completed.result.receipt &&
              !f.adapter.available() && !f.adapter.terminal() && !f.terminal.calls,
              "Owned lifecycle retirement fabricated an observation receipt or editable admission");
    });
    run("Redaction withholds actual applied outcome until owned cleanup without rewriting it", [] {
        AsyncFixture f;
        f.live.retire = NativeRetireMaterial{42, f.live.mapping_id, f.live.identity.context, 0};
        f.activate();
        const auto packet = key_packet(f.basis());
        const auto head = f.adapter.submit(packet);
        check(head.has_value(), "Redaction fixture key was not queued");
        const auto effect = f.observation(*head);
        check(f.adapter.request_retirement(), "Trusted in-flight redaction was not retained");
        auto actual = applied(f.live);
        actual.key_dispatch_attested = true;
        actual.allow_default = true;
        const auto published = f.delivered.size();
        check(f.adapter.complete(effect.ticket, actual) && !f.adapter.take_completion(*head) &&
              f.delivered.size() == published && !f.adapter.available(),
              "Known edit escaped redaction before actual native retirement");
        const auto cleanup = f.next();
        check(cleanup.kind == ContextRequest::Kind::revoke && cleanup.head_ticket == *head &&
              cleanup.ticket != effect.ticket && cleanup.retirement &&
              cleanup.retirement->material == *f.live.retire && cleanup.retirement->identity == f.live.identity,
              "Redaction did not retain the actual completed provider authority");
        auto successor = f.live;
        ++successor.identity.context;
        ++successor.mapping_id;
        successor.retire = NativeRetireMaterial{43, successor.mapping_id, successor.identity.context, 0};
        auto closed = applied(successor);
        closed.continuity = Continuity::replaced;
        closed.retired = f.live.retire;
        closed.projection->retire.reset();
        closed.composition_readback_attested = true;
        closed.observation_revision = 72;
        closed.readback_identity = successor.identity;
        closed.readback_attested = true;
        bool published_after_cleanup = false;
        f.on_publish = [&](const EditorPublication& value) {
            check(!value.basis && value.settlement && value.settlement->id == packet.observation.id &&
                  value.retirement && value.retirement->observation_revision == 72 &&
                  value.retirement->availability == NativeAvailability::available && value.retirement->authority_retired &&
                  value.retirement->identity == successor.identity &&
                  !f.adapter.take_completion(*head),
                  "Redacted completion preceded checked null publication or lost actual cleanup readback");
            published_after_cleanup = true;
            return true;
        };
        check(f.adapter.complete(cleanup.ticket, closed) && published_after_cleanup,
              "Actual redaction cleanup did not publish the withheld native completion");
        const auto completed = f.completion(*head);
        check(completed.result.admission == Admission::completed && completed.result.receipt &&
              completed.result.receipt->outcome == Outcome::applied && !completed.result.receipt->basis &&
              !completed.result.receipt->default_token && completed.result.receipt->continuity == Continuity::replaced &&
              completed.result.receipt->retirement && completed.result.receipt->retirement->observation_revision == 72 &&
              completed.result.receipt->retirement->availability == NativeAvailability::available &&
              completed.result.receipt->retirement->authority_retired &&
              completed.result.receipt->retirement->identity == successor.identity &&
              completed.result.receipt->session == packet.session && completed.result.receipt->id == packet.observation.id &&
              completed.result.receipt->submitted_token == packet.basis.token && !f.adapter.terminal() && !f.terminal.calls,
              "Redaction rewrote actual applied outcome, retained a default token or lost original receipt correlation");
        f.on_publish = {};
        f.live = successor;
        f.activate();
        const auto fresh_head = f.adapter.submit(key_packet(f.basis()));
        check(fresh_head.has_value(), "Fresh native context was not admitted after exact redaction closure");
        const auto fresh_effect = f.observation(*fresh_head);
        auto fresh_result = applied(f.live);
        fresh_result.key_dispatch_attested = true;
        check(f.adapter.complete(fresh_effect.ticket, fresh_result) &&
              f.completion(*fresh_head).result.admission == Admission::completed,
              "External retirement failed to clear old held-key/controller lifecycle authority");
    });
    run("Idle redaction retires actual provider ownership without inventing a browser receipt", [] {
        AsyncFixture f;
        f.live.retire = NativeRetireMaterial{42, f.live.mapping_id, f.live.identity.context, 0};
        f.activate();
        check(f.adapter.request_retirement(), "Idle trusted retirement was not queued");
        const auto cleanup = f.next();
        check(cleanup.kind == ContextRequest::Kind::revoke && !cleanup.head_ticket && cleanup.retirement &&
              cleanup.retirement->material == *f.live.retire && cleanup.retirement->identity == f.live.identity &&
              !cleanup.request && !f.adapter.take_completion(0),
              "Idle retirement invented an observation head or lost exact provider authority");
        auto closed = unavailable(f.live, Outcome::applied);
        closed.retired = f.live.retire;
        check(f.adapter.complete(cleanup.ticket, closed) && !f.adapter.pending() &&
              !f.adapter.take_completion(0) && !f.adapter.available() && !f.adapter.terminal() && !f.terminal.calls,
              "Idle native cleanup fabricated a browser completion or failed lifecycle closure");
        check(f.delivered.size() == 2 && !f.delivered.back().basis && !f.delivered.back().settlement &&
              f.delivered.back().retirement && f.delivered.back().retirement->readback_attested &&
              f.delivered.back().retirement->authority_retired,
              "Idle native closure did not strongly publish actual unavailable readback");
    });
    run("Synchronous compatibility cannot substitute generic revoke for provider-owned cleanup", [] {
        FakeBackend backend;
        backend.live.retire = NativeRetireMaterial{42, backend.live.mapping_id, backend.live.identity.context, 0};
        TerminalCounter terminal;
        unsigned publications{};
        NativeEditorContextAdapter adapter(backend, [&](const EditorPublication&) {
            ++publications;
            return true;
        }, terminal.hook());
        check(adapter.install_projection(backend.live) && adapter.request_retirement(),
              "Synchronous owned-cleanup fixture did not retain native authority");
        (void)adapter.advance();
        check(adapter.terminal() && terminal.calls == 1 && !adapter.available() && !adapter.publication() &&
              !backend.effects && !backend.revocations && publications == 1 && !adapter.take_completion(0),
              "Synchronous mock backend fabricated owned9 cleanup through an unrelated generic export");
    });
    run("Synchronous mock Backend follows the same publication-before-completion path", [] {
        FakeBackend backend;
        TerminalCounter terminal;
        std::vector<EditorPublication> publications;
        NativeEditorContextAdapter* endpoint{};
        std::optional<std::uint64_t> head;
        NativeEditorContextAdapter adapter(backend, [&](const EditorPublication& value) {
            if (head) check(endpoint && !endpoint->take_completion(*head) && !endpoint->advance(),
                            "Synchronous publication callback entered native work or exposed completion");
            publications.push_back(value);
            return true;
        }, terminal.hook());
        endpoint = &adapter;
        check(adapter.install_projection(backend.live) && !backend.projects && !backend.effects,
              "Synchronous activation entered the injected backend");
        head = adapter.submit(text_packet(*adapter.publication()->basis));
        check(head.has_value() && !backend.projects && !backend.effects, "Ingress entered synchronous native backend");
        adapter.enter_callback();
        check(!adapter.advance() && !backend.projects && !backend.effects, "Guarded advance entered mock backend");
        adapter.leave_callback();
        check(adapter.advance() && backend.projects == 1 && backend.effects == 1 && !backend.revocations,
              "Synchronous compatibility duplicated or omitted native stages");
        const auto completed = adapter.take_completion(*head);
        check(completed && completed->result.admission == Admission::completed && completed->result.receipt &&
              completed->result.receipt->basis && completed->result.receipt->basis->surrounding == "native author result" &&
              completed->result.receipt->basis->editor_revision == 3 && publications.size() == 2 &&
              adapter.publication()->basis == completed->result.receipt->basis && !adapter.take_completion(*head) && !terminal.calls,
              "Synchronous wrapper guessed UA text or escaped the checked publication path");
    });
    run("Known unentered cancellation retains each head until actual owned closure", [] {
        for(bool effect_stage:{false,true}) {
            AsyncFixture f; f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,0};f.activate();
            const auto packet=f.packet();const auto head=f.adapter.submit(packet);check(head.has_value(),"Cancellation head missing");
            auto active=f.next();
            if(effect_stage){check(f.adapter.supply_projection(active.ticket,f.live),"Cancellation projection failed");active=f.next();}
            check(!f.adapter.cancel_unentered(active.ticket+100)&&f.adapter.cancel_unentered(active.ticket)&&
                !f.adapter.take_completion(*head)&&f.adapter.retirement_pending()&&f.delivered.size()==1,
                "Known not-entered head escaped actual retirement");
            const auto cleanup=f.next();
            check(cleanup.kind==ContextRequest::Kind::revoke&&cleanup.head_ticket==*head&&cleanup.retirement&&
                cleanup.retirement->material==*f.live.retire&&cleanup.ticket!=active.ticket,
                "Known cancellation lost original retirement material");
            check(!f.adapter.complete(active.ticket,applied(f.live))&&!f.adapter.supply_projection(active.ticket,f.live),
                "Old cancelled transport callback consumed cleanup");
            check(f.adapter.cancel_unentered(cleanup.ticket),"Known unentered cleanup could not retain its obligation");
            const auto retry=f.next();
            check(retry.ticket!=cleanup.ticket&&retry.head_ticket==cleanup.head_ticket&&retry.retirement&&
                retry.retirement->material==cleanup.retirement->material&&!f.adapter.cancel_unentered(cleanup.ticket),
                "Known unentered cleanup reused correlation or changed exact request");
            auto closed=unavailable(f.live,Outcome::applied);closed.retired=f.live.retire;closed.observation_revision=92;
            check(f.adapter.complete(retry.ticket,closed)&&!f.adapter.retirement_pending()&&f.adapter.pending(),
                "Cleanup completion waited for frontend take or released native debt early");
            const auto completed=f.completion(*head);
            check(completed.result.admission==Admission::completed&&completed.result.receipt&&
                completed.result.receipt->outcome==Outcome::cancelled&&!completed.result.receipt->basis&&
                completed.result.receipt->session==packet.session&&completed.result.receipt->id==packet.observation.id&&
                completed.result.receipt->submitted_token==packet.basis.token&&completed.result.receipt->retirement&&
                completed.result.receipt->retirement->observation_revision==92&&completed.result.receipt->retirement->authority_retired&&
                !f.adapter.terminal()&&!f.adapter.pending(),"Known cancellation fabricated outcome or lost receipt correlation");
        }
    });
    run("Initial unentered projection cancellation has no invented native closure", [] {
        AsyncFixture f;check(f.adapter.request_projection(),"Initial cancellation poll missing");const auto poll=f.next();
        check(f.adapter.request_retirement()&&f.adapter.retirement_pending()&&f.adapter.cancel_unentered(poll.ticket)&&
            !f.adapter.pending()&&!f.adapter.retirement_pending()&&!f.adapter.publication()&&f.delivered.empty()&&
            !f.adapter.supply_projection(poll.ticket,f.live)&&!f.adapter.terminal(),
            "No-material cancellation invented proof or left retirement permanently pending");
        f.activate();
    });
    run("Queued unoffered observation retires without issuing projection or native effect", [] {
        AsyncFixture f;f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,0};f.activate();
        const auto packet=f.packet();const auto head=f.adapter.submit(packet);check(head.has_value(),"Queued retirement head missing");
        check(f.adapter.request_retirement()&&f.adapter.retirement_pending(),"Queued retirement not retained");
        unsigned callbacks{};
        const auto cleanup=f.adapter.prepare([&]{++callbacks;return false;});
        check(cleanup&&cleanup->kind==ContextRequest::Kind::revoke&&cleanup->head_ticket==*head&&cleanup->retirement&&
            !cleanup->request&&!callbacks&&!f.adapter.take_completion(*head),"Retired queued head entered before-head/native work");
        auto closed=unavailable(f.live,Outcome::applied);closed.retired=f.live.retire;
        check(f.adapter.complete(cleanup->ticket,closed)&&!f.adapter.retirement_pending(),"Queued retirement proof failed");
        const auto completed=f.completion(*head);
        check(completed.result.receipt&&completed.result.receipt->outcome==Outcome::cancelled&&
            !completed.result.receipt->basis&&completed.result.receipt->retirement&&completed.result.receipt->retirement->authority_retired,
            "Never-submitted observation was not correlated after real cleanup");
    });
    run("Explicit rediscovery retires active material once before fresh projection", [] {
        AsyncFixture f;f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,0};f.activate();
        const auto previous=f.basis();
        check(f.adapter.request_projection()&&f.adapter.request_projection()&&f.adapter.retirement_pending(),"Resync cleanup not pending");
        const auto cleanup=f.next();check(cleanup.kind==ContextRequest::Kind::revoke&&cleanup.retirement&&
            !cleanup.head_ticket&&cleanup.retirement->material==*f.live.retire,"Resync queried before closing old authority");
        check(f.adapter.request_projection()&&!f.adapter.prepare(),"Repeated resync duplicated active cleanup");
        auto closed=unavailable(f.live,Outcome::applied);closed.retired=f.live.retire;
        check(f.adapter.complete(cleanup.ticket,closed)&&!f.adapter.retirement_pending()&&f.adapter.pending()&&
            f.delivered.size()==2&&!f.delivered.back().basis&&f.delivered.back().retirement->authority_retired,
            "Resync did not strongly publish exact old closure first");
        const auto poll=f.next();check(poll.kind==ContextRequest::Kind::projection&&!poll.mapping_id&&
            !poll.head_ticket&&poll.ticket!=cleanup.ticket,"Resync did not offer fresh focused discovery");
        ++f.live.identity.context;++f.live.mapping_id;f.live.retire=NativeRetireMaterial{43,f.live.mapping_id,f.live.identity.context,0};
        check(f.adapter.supply_projection(poll.ticket,f.live)&&f.adapter.available()&&!f.adapter.pending()&&
            f.basis().token>previous.token&&f.basis().identity.context==f.live.identity.context,
            "Resync reused old native authority or editor token");
    });
    run("Redaction during initial query never publishes an active editor", [] {
        AsyncFixture f;f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,0};
        check(f.adapter.request_projection(),"Initial redacted query not queued");const auto poll=f.next();
        check(f.adapter.request_retirement()&&f.adapter.supply_projection(poll.ticket,f.live)&&f.delivered.empty()&&
            !f.adapter.available()&&f.adapter.retirement_pending(),"Initial query bypassed pending redaction");
        const auto cleanup=f.next();auto closed=unavailable(f.live,Outcome::applied);closed.retired=f.live.retire;
        check(cleanup.kind==ContextRequest::Kind::revoke&&cleanup.retirement&&f.adapter.complete(cleanup.ticket,closed)&&
            !f.adapter.retirement_pending()&&!f.adapter.pending()&&f.delivered.size()==1&&!f.delivered.back().basis&&
            f.delivered.back().retirement&&f.delivered.back().retirement->authority_retired&&!f.adapter.take_completion(0),
            "Initial redaction did not wait for real cleanup or invented a browser head");
    });
    run("Pending logical composition never fabricates native composition in owned9", [] {
        AsyncFixture f;f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,0};f.activate();
        auto packet=f.packet();auto& observation=packet.observation;
        observation.kind=Kind::composition;observation.authority=Authority::range;observation.transaction=77;
        observation.after.reset();CompositionData data;data.operation=foundation::gui_surface::CompositionOperation::begin;
        data.replacement=ByteRange{3,3};data.selection={0,0};observation.data=data;
        const auto head=f.adapter.submit(packet);check(head.has_value(),"Pending composition head missing");
        const auto effect=f.observation(*head);auto pending=applied(f.live);pending.composition_readback_attested=true;
        pending.composition=CompositionFact{77,CompositionState::pending};
        check(f.adapter.complete(effect.ticket,pending)&&f.completion(*head).result.admission==Admission::completed,
            "Logical pending composition was not retained");
        Revocation revoke;revoke.basis=f.basis();revoke.incarnation=9;revoke.composition=77;revoke.reason="pending blur";
        const auto revoke_head=f.adapter.queue_revoke(revoke);check(revoke_head.has_value(),"Pending revoke not queued");
        const auto query=f.next();check(f.adapter.supply_projection(query.ticket,f.live),"Pending revoke mapping failed");
        const auto cleanup=f.next();check(cleanup.revocation&&cleanup.revocation->composition==77&&cleanup.retirement&&
            cleanup.retirement->material.composition==0&&!cleanup.retirement->observed,
            "Logical transaction was serialized as a nonexistent native composition");
        auto closed=unavailable(f.live,Outcome::applied);closed.retired=f.live.retire;
        check(f.adapter.complete(cleanup.ticket,closed)&&f.completion(*revoke_head).result.admission==Admission::completed&&
            f.delivered.back().retirement&&f.delivered.back().retirement->authority_retired&&
            !f.delivered.back().composition&&!f.adapter.retirement_pending(),
            "Attested native0 closure did not clear logical pending state without invented composition fact");
    });
    run("Presentation-only alias never serializes stale optional revocation identity", [] {
        AsyncFixture f;f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,0};f.activate();
        Revocation revoke;revoke.basis=f.basis();revoke.incarnation=9;revoke.reason="revision refresh";
        const auto head=f.adapter.queue_revoke(revoke);check(head.has_value(),"Aliased revocation missing");const auto query=f.next();
        ++f.live.identity.presentation_revision;
        check(f.adapter.supply_projection(query.ticket,f.live),"Presentation-only refresh rejected");
        const auto cleanup=f.next();check(cleanup.revocation&&cleanup.revocation->basis.identity==revoke.basis.identity&&
            cleanup.retirement&&cleanup.retirement->identity==f.live.identity&&!cleanup.retirement->observed,
            "Stale publication identity escaped into the exact owned9 optional record");
        auto closed=unavailable(f.live,Outcome::applied);closed.retired=f.live.retire;
        check(f.adapter.complete(cleanup.ticket,closed)&&f.completion(*head).result.admission==Admission::completed,
            "Presentation-only metadata refresh could not close actual provider material");
    });
    run("Projection replies cannot claim an unexecuted owned retirement", [] {
        AsyncFixture f;check(f.adapter.request_projection(),"Forged retirement query missing");const auto poll=f.next();
        RetirementReadback reply{NativeAvailability::noneditable,f.live.identity,4,true,true};
        check(f.adapter.supply_projection(poll.ticket,{},reply)&&f.adapter.terminal()&&f.terminal.calls==1&&f.delivered.empty(),
            "Projection sample claimed a native9 closure it did not execute");
    });
    run("Generic text input types share the 64 byte ingress boundary", [] {
        AsyncFixture f;f.activate();auto too_long=f.packet();
        std::get<TextData>(too_long.observation.data).input_type=std::string(65,'x');
        check(!f.adapter.submit(std::move(too_long))&&!f.adapter.pending()&&!f.adapter.terminal(),
            "Oversized input type entered the mailbox");
        auto maximum=f.packet();std::get<TextData>(maximum.observation.data).input_type=std::string(64,'x');
        const auto head=f.adapter.submit(std::move(maximum));check(head.has_value(),"Generic maximum input type rejected");
        const auto effect=f.observation(*head);check(effect.request&&
            std::get<TextData>(effect.request->packet.observation.data).input_type==std::string(64,'x'),
            "Generic input type changed before native dispatch");
        check(f.adapter.complete(effect.ticket,applied(f.live))&&f.completion(*head).result.admission==Admission::completed,
            "Maximum generic text input type could not complete normally");
    });
    run("Ingress limits account for retained capacities in every nested container", [] {
        constexpr auto reserve=Controller::max_packet_bytes+1;
        for(unsigned field=0;field!=12;++field){
            AsyncFixture f;auto packet=text_packet(Basis{});
            switch(field){
            case 0:packet.basis.surrounding.reserve(reserve);break;
            case 1:packet.basis.identity.owner.id.reserve(reserve);break;
            case 2:packet.observation.before.value.reserve(reserve);break;
            case 3:packet.observation.after->value.reserve(reserve);break;
            case 4:packet.default_dependencies.reserve(reserve/sizeof(DefaultDependency)+1);break;
            case 5:std::get<TextData>(packet.observation.data).text.reserve(reserve);break;
            case 6:std::get<TextData>(packet.observation.data).input_type.reserve(reserve);break;
            case 7:std::get<TextData>(packet.observation.data).source_groups.reserve(reserve/sizeof(std::uint64_t)+1);break;
            case 8:packet.observation.data=CompositionData{};std::get<CompositionData>(packet.observation.data).text.reserve(reserve);break;
            case 9:packet.observation.data=CompositionData{};std::get<CompositionData>(packet.observation.data).source_groups.reserve(reserve/sizeof(std::uint64_t)+1);break;
            case 10:packet.observation.data=KeyData{};std::get<KeyData>(packet.observation.data).transition.key.reserve(reserve);break;
            case 11:packet.observation.data=KeyData{};std::get<KeyData>(packet.observation.data).transition.code.reserve(reserve);break;
            }
            check(!f.adapter.submit(std::move(packet))&&!f.adapter.pending()&&!f.adapter.terminal(),
                "Moved packet retained an uncharged oversized nested allocation");
        }
        for(unsigned field=0;field!=6;++field){
            AsyncFixture f;Revocation revoke;revoke.held_keys.emplace_back();
            switch(field){
            case 0:revoke.basis.surrounding.reserve(reserve);break;
            case 1:revoke.basis.identity.owner.id.reserve(reserve);break;
            case 2:revoke.reason.reserve(reserve);break;
            case 3:revoke.held_keys.reserve(reserve/sizeof(KeyData)+1);break;
            case 4:revoke.held_keys[0].transition.key.reserve(reserve);break;
            case 5:revoke.held_keys[0].transition.code.reserve(reserve);break;
            }
            check(!f.adapter.queue_revoke(std::move(revoke))&&!f.adapter.pending()&&!f.adapter.terminal(),
                "Moved revocation retained an uncharged oversized nested allocation");
        }
    });
    run("Mailbox count and aggregate capacity recover only when completions are taken", [] {
        AsyncFixture f;std::vector<std::uint64_t> heads;
        for(unsigned n=0;n!=64;++n){const auto head=f.adapter.submit(Packet{});check(head.has_value(),"Mailbox filled below 64 slots");heads.push_back(*head);}
        check(!f.adapter.submit(Packet{}),"Mailbox exceeded 64 retained slots");
        for(const auto head:heads){check(!f.adapter.prepare()&&f.adapter.take_completion(head).has_value(),"Rejected metadata head did not release on take");}
        check(!f.adapter.pending()&&!f.adapter.terminal(),"Drained mailbox remained pending");
        auto retained=[] {Packet packet;packet.basis.surrounding.reserve(400000);return packet;};
        const auto first=f.adapter.submit(retained()),second=f.adapter.submit(retained());
        check(first&&second&&!f.adapter.submit(retained()),"Aggregate retained capacity exceeded 1MiB");
        check(!f.adapter.prepare()&&!f.adapter.submit(retained()),"Untaken completion released its retained-byte charge");
        check(f.adapter.take_completion(*first).has_value(),"First retained-capacity completion missing");
        const auto successor=f.adapter.submit(retained());check(successor.has_value(),"Taking completion failed to restore byte budget");
        for(const auto head:{*second,*successor})check(!f.adapter.prepare()&&f.adapter.take_completion(head).has_value(),"Capacity successor did not drain");
        check(!f.adapter.pending()&&!f.adapter.terminal(),"Capacity fixture did not settle cleanly");
    });
    run("Inert refresh preserves causal default and held-key authority across presentation revision", [] {
        AsyncFixture f;f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,0};f.activate();
        const auto down=f.adapter.submit(key_packet(f.basis()));check(down.has_value(),"Refresh key press missing");
        const auto key=f.observation(*down);auto pressed=applied(f.live);pressed.key_dispatch_attested=true;pressed.allow_default=true;
        check(f.adapter.complete(key.ticket,pressed),"Default grant failed");const auto completion=f.completion(*down);
        check(completion.result.receipt&&completion.result.receipt->default_token,"Actual native key granted no default dependency");
        const auto dependency=*completion.result.receipt->default_token;const auto previous=f.basis();
        const auto publications=f.delivered.size();
        check(f.adapter.request_refresh()&&f.adapter.request_refresh()&&f.adapter.pending()&&!f.adapter.retirement_pending(),
            "Inert refresh eagerly retired native authority");
        const auto query=f.next();check(query.kind==ContextRequest::Kind::projection&&!query.head_ticket&&
            query.mapping_id==f.live.mapping_id&&!f.adapter.prepare()&&f.adapter.request_refresh(),
            "Refresh did not coalesce one current-mapping query");
        ++f.live.identity.presentation_revision;
        f.on_publish=[&](const EditorPublication& value){check(value.basis&&value.basis->token==previous.token&&
            value.basis->identity==f.live.identity&&!value.settlement&&!value.retirement&&
            f.adapter.projection()&&*f.adapter.projection()==f.live,"Refresh publication lost token or checked staged geometry");return true;};
        check(f.adapter.supply_projection(query.ticket,f.live)&&!f.adapter.pending()&&!f.adapter.retirement_pending()&&
            f.delivered.size()==publications+1&&!f.adapter.take_completion(0),"Inert refresh invented cleanup or browser completion");
        f.on_publish={};
        auto text=f.packet(2,1);text.observation.authority=Authority::default_action;text.observation.group=9;
        text.observation.group_end=true;text.default_dependencies={dependency};text.default_token=dependency.token;
        std::get<TextData>(text.observation.data).source_groups={9};
        const auto text_head=f.adapter.submit(text);check(text_head.has_value(),"Preserved default successor missing");
        const auto text_effect=f.observation(*text_head);check(f.adapter.complete(text_effect.ticket,applied(f.live))&&
            f.completion(*text_head).result.admission==Admission::completed,"Refresh lost causal predecessor or native default grant");
        auto release=key_packet(f.basis(),3);release.observation.predecessor=2;release.observation.group_end=true;
        std::get<KeyData>(release.observation.data).transition.phase=foundation::gui_surface::KeyPhase::up;
        const auto up=f.adapter.submit(release);check(up.has_value(),"Preserved key release missing");
        const auto release_effect=f.observation(*up);auto released=applied(f.live);released.key_dispatch_attested=true;
        check(f.adapter.complete(release_effect.ticket,released)&&f.completion(*up).result.admission==Admission::completed,
            "Refresh lost actual held-key ownership");
    });
    run("Inert refresh preserves both pending and live composition transactions", [] {
        for(const auto state:{CompositionState::pending,CompositionState::live}){
            AsyncFixture f;f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,0};f.activate();
            auto packet=f.packet();auto& observation=packet.observation;observation.kind=Kind::composition;
            observation.authority=Authority::range;observation.transaction=77;observation.after.reset();
            CompositionData begin;begin.operation=foundation::gui_surface::CompositionOperation::begin;
            begin.replacement=ByteRange{3,3};begin.selection={0,0};observation.data=begin;
            const auto head=f.adapter.submit(packet);check(head.has_value(),"Composition refresh head missing");const auto effect=f.observation(*head);
            if(state==CompositionState::live){f.live.composition=77;f.live.retire->composition=77;}
            auto started=applied(f.live);started.composition_readback_attested=true;started.composition=CompositionFact{77,state};
            check(f.adapter.complete(effect.ticket,started)&&f.completion(*head).result.admission==Admission::completed,
                "Actual composition state was not retained");
            const auto previous=f.basis();check(f.adapter.request_refresh(),"Composition refresh not queued");const auto query=f.next();
            ++f.live.identity.presentation_revision;
            check(query.mapping_id==f.live.mapping_id&&f.adapter.supply_projection(query.ticket,f.live)&&
                f.basis().token==previous.token&&f.adapter.publication()->composition==CompositionFact{77,state}&&
                !f.adapter.pending()&&!f.adapter.retirement_pending(),"Inert refresh cancelled or restarted composition");
            auto update=f.packet(2,1);update.observation.kind=Kind::composition;update.observation.authority=Authority::composition;
            update.observation.transaction=77;update.observation.after.reset();CompositionData data;
            data.operation=foundation::gui_surface::CompositionOperation::update;data.text="Z";data.selection={1,1};update.observation.data=data;
            const auto next=f.adapter.submit(update);check(next.has_value(),"Composition successor missing");const auto update_effect=f.observation(*next);
            auto changed=applied(f.live);changed.composition_readback_attested=true;changed.composition=CompositionFact{77,state};
            check(f.adapter.complete(update_effect.ticket,changed)&&f.completion(*next).result.admission==Admission::completed,
                "Refresh reset the retained logical transaction or causal predecessor");
        }
    });
    run("Changed refresh facts retire the original material before focused replacement", [] {
        for(unsigned field=0;field!=8;++field){
            AsyncFixture f;f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,0};f.activate();
            const auto original=f.live;const auto previous=f.basis();check(f.adapter.request_refresh(),"Changed refresh missing");const auto query=f.next();
            auto actual=f.live;
            switch(field){
            case 0:++actual.editor_revision;break;
            case 1:actual.surrounding="abcd";break;
            case 2:actual.selection={0,0};break;
            case 3:++actual.caret.x;break;
            case 4:actual.input_purpose="search";break;
            case 5:++actual.frame_id;break;
            case 6:++actual.mapping_id;actual.retire->mapping_id=actual.mapping_id;break;
            case 7:++actual.retire->token;break;
            }
            check(f.adapter.supply_projection(query.ticket,actual)&&f.delivered.size()==1&&f.adapter.retirement_pending()&&!f.adapter.available(),
                "Changed read-only projection silently rebased editable authority");
            const auto cleanup=f.next();check(cleanup.kind==ContextRequest::Kind::revoke&&!cleanup.head_ticket&&cleanup.retirement&&
                cleanup.retirement->material==*original.retire&&cleanup.retirement->identity==original.identity&&
                !f.adapter.supply_projection(query.ticket,actual)&&!f.adapter.prepare(),"Refresh cleanup adopted returned candidate authority");
            auto closed=unavailable(original,Outcome::applied);closed.retired=original.retire;
            check(f.adapter.complete(cleanup.ticket,closed)&&!f.adapter.retirement_pending()&&f.adapter.pending()&&
                f.delivered.size()==2&&!f.delivered.back().basis&&f.delivered.back().retirement->authority_retired,
                "Changed refresh did not strongly publish actual old closure first");
            const auto discover=f.next();check(discover.kind==ContextRequest::Kind::projection&&!discover.head_ticket&&
                !discover.mapping_id&&discover.ticket!=query.ticket,"Changed refresh skipped fresh focused discovery");
            ++f.live.identity.context;f.live.retire=NativeRetireMaterial{44,f.live.mapping_id,f.live.identity.context,0};
            check(f.adapter.supply_projection(discover.ticket,f.live)&&f.adapter.available()&&!f.adapter.pending()&&
                f.basis().token>previous.token&&!f.adapter.terminal(),"Fresh discovery did not follow exact old retirement");
        }
    });
    run("Known null refresh rechecks actual availability and retires any prior mapping", [] {
        AsyncFixture f;check(f.adapter.request_refresh(),"Initial refresh not queued");auto query=f.next();
        RetirementReadback noneditable{NativeAvailability::noneditable,f.live.identity,3,true};
        check(!query.mapping_id&&f.adapter.supply_projection(query.ticket,{},noneditable)&&!f.adapter.pending()&&
            f.delivered.size()==1&&f.delivered.back().retirement==noneditable,"Initial refresh invented editor or retirement");
        check(f.adapter.request_refresh(),"Null refresh not requeued");query=f.next();++noneditable.observation_revision;
        check(!query.mapping_id&&f.adapter.supply_projection(query.ticket,{},noneditable)&&f.delivered.size()==2&&
            f.delivered.back().retirement==noneditable&&!f.delivered.back().retirement->authority_retired,
            "Cached null prevented fresh actual readback");
        f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,0};f.activate();
        check(f.adapter.request_refresh(),"Active null refresh not queued");query=f.next();
        RetirementReadback missing{NativeAvailability::unavailable,f.live.identity,5,true};
        check(f.adapter.supply_projection(query.ticket,{},missing)&&f.delivered.size()==3&&f.adapter.retirement_pending(),
            "Unavailable refresh published before exact old cleanup");
        const auto cleanup=f.next();auto closed=unavailable(f.live,Outcome::applied);closed.retired=f.live.retire;
        check(cleanup.retirement&&cleanup.retirement->material==*f.live.retire&&f.adapter.complete(cleanup.ticket,closed),
            "Unavailable refresh lost old cleanup");
        const auto discovery=f.next();check(!discovery.mapping_id&&f.adapter.supply_projection(discovery.ticket,{},missing)&&
            f.delivered.size()==5&&f.delivered.back().retirement==missing&&!f.adapter.pending()&&!f.adapter.available(),
            "Unavailable refresh failed independent focused known-null discovery");
    });
    run("Retirement and explicit resync supersede an in-flight inert refresh", [] {
        for(bool redact:{false,true}){
            AsyncFixture f;f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,0};f.activate();
            check(f.adapter.request_refresh(),"Superseded refresh missing");const auto query=f.next();
            check(redact?f.adapter.request_retirement():f.adapter.request_projection(),"Refresh superseding request failed");
            ++f.live.identity.presentation_revision;
            check(f.adapter.supply_projection(query.ticket,f.live)&&f.delivered.size()==1&&f.adapter.retirement_pending(),
                "Superseded refresh republished active editor before cleanup");
            const auto cleanup=f.next();check(cleanup.retirement&&cleanup.retirement->identity==f.live.identity,
                "Superseded refresh lost latest exact presentation identity");
            auto closed=unavailable(f.live,Outcome::applied);closed.retired=f.live.retire;
            check(f.adapter.complete(cleanup.ticket,closed)&&!f.adapter.retirement_pending(),"Superseded refresh cleanup failed");
            if(redact)check(!f.adapter.pending()&&!f.adapter.prepare(),"Redaction rediscovered authority without request");
            else {const auto poll=f.next();RetirementReadback missing{NativeAvailability::unavailable,f.live.identity,9,true};
                check(!poll.mapping_id&&f.adapter.supply_projection(poll.ticket,{},missing)&&!f.adapter.pending(),
                    "Explicit resync failed to discover after superseded refresh cleanup");}
        }
    });
    run("Head presentation refresh updates exact retirement identity before known cancellation", [] {
        AsyncFixture f;f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,0};f.activate();
        const auto head=f.adapter.submit(f.packet());check(head.has_value(),"Head identity fixture missing");const auto query=f.next();
        ++f.live.identity.presentation_revision;check(f.adapter.supply_projection(query.ticket,f.live),"Head pRev sample failed");
        const auto effect=f.next();check(f.adapter.request_retirement()&&f.adapter.cancel_unentered(effect.ticket),"Head known cancellation failed");
        const auto cleanup=f.next();check(cleanup.retirement&&cleanup.retirement->identity==f.live.identity&&
            cleanup.retirement->material==*f.live.retire,"Known cancellation used stale pre-query retirement identity");
        auto closed=unavailable(f.live,Outcome::applied);closed.retired=f.live.retire;
        check(f.adapter.complete(cleanup.ticket,closed)&&f.completion(*head).result.receipt->outcome==Outcome::cancelled&&
            !f.adapter.retirement_pending(),"Latest-identity cleanup did not settle the original cancelled head");
    });
    run("Queued before-head freshness gates cannot starve inert refresh", [] {
        AsyncFixture f;f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,0};f.activate();
        const auto head=f.adapter.submit(f.packet());check(head.has_value(),"Refresh ordering head missing");
        check(f.adapter.request_refresh(),"Queued-head refresh missing");unsigned before_head{};
        const auto poll=f.adapter.prepare([&]{++before_head;return false;});
        check(poll&&!poll->head_ticket&&poll->mapping_id==f.live.mapping_id&&!before_head&&
            f.adapter.supply_projection(poll->ticket,f.live),"Before-head callback starved requested native freshness");
        const auto query=f.adapter.prepare([&]{++before_head;return true;});
        check(query&&query->head_ticket==*head&&before_head==1&&f.adapter.supply_projection(query->ticket,f.live),
            "Freshness query consumed or duplicated queued browser head");
        const auto effect=f.next();check(f.adapter.complete(effect.ticket,applied(f.live))&&
            f.completion(*head).result.admission==Admission::completed,"Queued head did not resume after inert refresh");
        AsyncFixture g;g.live.retire=NativeRetireMaterial{42,g.live.mapping_id,g.live.identity.context,0};g.activate();
        const auto stale=g.adapter.submit(g.packet());check(stale.has_value()&&g.adapter.request_refresh(),"Changed queued refresh missing");
        unsigned gated{};const auto refresh=g.adapter.prepare([&]{++gated;return false;});auto changed=g.live;++changed.caret.x;
        check(refresh&&!refresh->head_ticket&&!gated&&g.adapter.supply_projection(refresh->ticket,changed),"Changed queued refresh was gated by browser head");
        const auto cleanup=g.next();auto closed=unavailable(g.live,Outcome::applied);closed.retired=g.live.retire;
        check(g.adapter.complete(cleanup.ticket,closed),"Queued refresh cleanup failed");
        const auto discover=g.adapter.prepare([&]{++gated;return false;});
        check(discover&&!discover->head_ticket&&!discover->mapping_id&&!gated,"Queued BeforeHead starved required post-retirement discovery");
        ++g.live.identity.context;g.live.retire=NativeRetireMaterial{43,g.live.mapping_id,g.live.identity.context,0};
        check(g.adapter.supply_projection(discover->ticket,g.live)&&!g.adapter.prepare([&]{++gated;return true;})&&gated==1&&
            g.completion(*stale).result.admission==Admission::rejected,"Old queued browser head reached new native editor effect");
    });
    run("Known-unentered inert query preserves cleanup then focused refresh intent", [] {
        AsyncFixture f;f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,0};f.activate();
        check(f.adapter.request_refresh(),"Cancelled refresh missing");const auto query=f.next();
        check(f.adapter.cancel_unentered(query.ticket)&&f.adapter.retirement_pending()&&!f.adapter.available(),
            "Cancelled refresh abandoned native cleanup");
        const auto cleanup=f.next();auto closed=unavailable(f.live,Outcome::applied);closed.retired=f.live.retire;
        check(cleanup.retirement&&f.adapter.complete(cleanup.ticket,closed)&&f.adapter.pending(),
            "Cancelled refresh dropped focused discovery intent");
        const auto poll=f.next();RetirementReadback missing{NativeAvailability::noneditable,f.live.identity,12,true};
        check(!poll.mapping_id&&f.adapter.supply_projection(poll.ticket,{},missing)&&!f.adapter.pending(),
            "Known-unentered refresh replayed old query instead of focused discovery");
    });
    run("Actual successor leases remain owned until every exact retirement completes", [] {
        for(unsigned kind=0;kind!=3;++kind){
            AsyncFixture f;f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,0};f.activate();
            std::optional<std::uint64_t> head;
            if(kind==1){head=f.adapter.submit(f.packet());check(head.has_value(),"Successor head missing");
                const auto effect=f.observation(*head);check(f.adapter.request_retirement()&&
                    f.adapter.complete(effect.ticket,applied(f.live)),"Successor head did not await retirement");}
            else if(kind==2){Revocation revoke;revoke.basis=f.basis();revoke.incarnation=9;revoke.reason="successor blur";
                head=f.adapter.queue_revoke(revoke);check(head.has_value(),"Explicit successor revocation missing");
                const auto query=f.next();check(f.adapter.supply_projection(query.ticket,f.live),"Explicit successor mapping failed");}
            else check(f.adapter.request_retirement(),"Successor idle retirement missing");
            const auto first=f.next();auto successor=f.live;++successor.identity.context;++successor.mapping_id;
            successor.retire=NativeRetireMaterial{43,successor.mapping_id,successor.identity.context,0};
            auto renewed=applied(successor);renewed.continuity=Continuity::replaced;renewed.retired=f.live.retire;
            renewed.retire=successor.retire;renewed.readback_identity=successor.identity;renewed.readback_attested=true;renewed.observation_revision=20;
            renewed.composition_readback_attested=true;
            check(f.adapter.complete(first.ticket,renewed)&&f.adapter.retirement_pending()&&!f.adapter.available()&&
                f.delivered.size()==1&&(!head||!f.adapter.take_completion(*head)),"Successor provider lease falsely completed native drain");
            const auto second=f.next();check(second.ticket!=first.ticket&&second.retirement&&
                second.retirement->material==*successor.retire&&second.retirement->identity==successor.identity&&
                second.head_ticket==head.value_or(0),"Successor exact retirement lost material, identity or original head");
            auto closed=applied(successor);closed.projection->retire.reset();closed.retired=successor.retire;
            closed.readback_identity=successor.identity;closed.readback_attested=true;closed.observation_revision=21;
            check(f.adapter.complete(second.ticket,closed)&&!f.adapter.retirement_pending()&&!f.adapter.available()&&
                f.delivered.size()==2&&f.delivered.back().retirement&&
                f.delivered.back().retirement->availability==NativeAvailability::available&&
                f.delivered.back().retirement->authority_retired&&!f.delivered.back().basis&&!f.adapter.terminal(),
                "Final exact cleanup coerced actual available readback or retained input authority");
            if(kind==1){const auto complete=f.completion(*head);check(complete.result.receipt&&
                complete.result.receipt->outcome==Outcome::applied&&!complete.result.receipt->basis&&
                complete.result.receipt->retirement->observation_revision==21,"Successor draining rewrote original known observation outcome");}
            else if(head){const auto complete=f.completion(*head);check(complete.result.admission==Admission::completed&&!complete.result.receipt,
                "Explicit successor retirement fabricated observation receipt");}
            check(!f.adapter.pending(),"Final successor drain retained a phantom transport stage");
        }
    });
    run("Unsupported or unbounded successor leases quarantine instead of reporting drained", [] {
        for(bool without_projection:{false,true}){
            AsyncFixture f;f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,0};f.activate();
            check(f.adapter.request_retirement(),"Quarantine retirement missing");auto owned=f.live;
            const unsigned attempts=without_projection?1:64;
            for(unsigned n=0;n!=attempts;++n){
                const auto cleanup=f.next();auto next=owned;++next.retire->token;
                auto renewed=applied(next);renewed.retired=owned.retire;renewed.retire=next.retire;
                renewed.readback_identity=next.identity;renewed.readback_attested=true;renewed.observation_revision=n+1;
                if(without_projection){renewed.projection.reset();renewed.availability=NativeAvailability::unavailable;renewed.continuity=Continuity::replaced;}
                check(f.adapter.complete(cleanup.ticket,renewed),"Correlated successor proof was not consumed");owned=next;
            }
            check(f.adapter.terminal()&&f.terminal.calls==1&&f.adapter.retirement_pending()&&!f.adapter.available()&&
                !f.adapter.prepare()&&f.delivered.size()==1&&!f.adapter.take_completion(0),
                "Successor debt escaped finite quarantine as a successful drain or fake null proof");
        }
    });
    run("Fresh work preserves the exact completed head publication until metadata take", [] {
        for(bool explicit_resync:{false,true}){
            AsyncFixture f;f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,0};f.activate();
            const auto head=f.adapter.submit(f.packet());check(head.has_value(),"Untaken publication head missing");
            const auto effect=f.observation(*head);check(f.adapter.complete(effect.ticket,applied(f.live)),"Untaken native completion failed");
            const auto paired=*f.adapter.publication();check(paired.settlement&&paired.basis,"Completed head lost paired publication");
            check(explicit_resync?f.adapter.request_projection():f.adapter.request_refresh(),"Untaken refresh request failed");
            unsigned callbacks{};check(!f.adapter.prepare([&]{++callbacks;return false;})&&!callbacks&&
                f.adapter.pending()&&*f.adapter.publication()==paired,"Idle query overwrote paired head publication before take");
            const auto completed=f.completion(*head);const auto& receipt=*completed.result.receipt;
            check(paired.settlement==Settlement{receipt.session,receipt.id,receipt.submitted_token,receipt.predecessor}&&
                paired.basis==receipt.basis&&paired.composition==receipt.composition&&paired.retirement==receipt.retirement,
                "Metadata take no longer joined its exact previously published head");
            auto next=f.next();
            if(explicit_resync){check(next.retirement&&next.retirement->material==*f.live.retire,"Deferred resync skipped old cleanup");
                auto closed=unavailable(f.live,Outcome::applied);closed.retired=f.live.retire;
                check(f.adapter.complete(next.ticket,closed),"Deferred resync cleanup failed");next=f.next();
                RetirementReadback missing{NativeAvailability::noneditable,f.live.identity,13,true};
                check(!next.mapping_id&&f.adapter.supply_projection(next.ticket,{},missing)&&!f.adapter.pending(),"Deferred resync intent was lost after take");}
            else {++f.live.identity.presentation_revision;
                check(next.mapping_id==f.live.mapping_id&&f.adapter.supply_projection(next.ticket,f.live)&&
                    f.basis().token==paired.basis->token&&!f.adapter.pending(),"Deferred inert refresh did not preserve actual token after take");}
        }
    });
    run("A queued successor cannot overwrite the previous untaken head publication", [] {
        AsyncFixture f;f.activate();const auto first=f.adapter.submit(f.packet());check(first.has_value(),"First queued publication missing");
        const auto effect=f.observation(*first);check(f.adapter.complete(effect.ticket,applied(f.live)),"First queued completion failed");
        const auto paired=*f.adapter.publication();const auto second=f.adapter.submit(f.packet(2,1));check(second.has_value(),"Queued successor ingress failed");
        unsigned before_head{};check(!f.adapter.prepare([&]{++before_head;return true;})&&!before_head&&
            !f.adapter.take_completion(*second)&&*f.adapter.publication()==paired,"Queued successor overwrote an untaken paired publication");
        check(f.completion(*first).result.receipt->basis==paired.basis,"First completion lost exact publication");
        const auto query=f.adapter.prepare([&]{++before_head;return true;});check(query&&query->head_ticket==*second&&
            before_head==1&&f.adapter.supply_projection(query->ticket,f.live),"Queued successor did not resume after metadata take");
        const auto next=f.next();check(f.adapter.complete(next.ticket,applied(f.live))&&
            f.completion(*second).result.admission==Admission::completed&&!f.adapter.pending(),"Queued causal successor failed after ordered publication barrier");
    });
    run("Trusted retirement withholds an already completed head until checked null publication", [] {
        AsyncFixture f;f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,0};f.activate();
        const auto packet=f.packet();const auto head=f.adapter.submit(packet);check(head.has_value(),"Completed retirement head missing");
        const auto effect=f.observation(*head);check(f.adapter.complete(effect.ticket,applied(f.live)),"Completed retirement native result failed");
        const auto published=f.delivered.size();check(f.adapter.request_retirement()&&!f.adapter.take_completion(*head),
            "Completed head escaped trusted retirement before prepare");
        const auto cleanup=f.next();check(cleanup.head_ticket==*head&&cleanup.retirement&&
            cleanup.retirement->material==*f.live.retire&&!f.adapter.take_completion(*head)&&f.delivered.size()==published,
            "Completed head was replaced by uncorrelated idle retirement");
        auto closed=unavailable(f.live,Outcome::applied);closed.retired=f.live.retire;
        check(f.adapter.complete(cleanup.ticket,closed)&&!f.adapter.retirement_pending(),"Completed-head cleanup did not settle");
        const auto completion=f.completion(*head);check(completion.result.receipt&&completion.result.receipt->outcome==Outcome::applied&&
            !completion.result.receipt->basis&&completion.result.receipt->retirement&&
            completion.result.receipt->retirement->authority_retired&&f.delivered.back().settlement==
                Settlement{packet.session,packet.observation.id,packet.basis.token,packet.observation.predecessor}&&
            !f.delivered.back().basis&&!f.adapter.pending(),"Completed-head redaction lost original known outcome or exact null publication pair");
    });
    run("Actual observation retirement satisfies redaction without redundant owned9", [] {
        for(const auto availability:{NativeAvailability::noneditable,NativeAvailability::unavailable})
        for(const auto outcome:{Outcome::applied,Outcome::cancelled,Outcome::rejected})
        for(bool requested:{false,true}){
            AsyncFixture f;f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,0};f.activate();
            const auto packet=f.packet();const auto head=f.adapter.submit(packet);check(head.has_value(),"Native8 retirement head missing");
            const auto effect=f.observation(*head);if(requested)check(f.adapter.request_retirement(),"Native8 pending redaction failed");
            auto actual=unavailable(f.live,outcome);actual.availability=availability;actual.retired=f.live.retire;actual.observation_revision=101;
            f.on_publish=[&](const EditorPublication& publication){check(!publication.basis&&publication.settlement&&
                publication.settlement->id==packet.observation.id&&publication.retirement&&
                publication.retirement->availability==availability&&publication.retirement->authority_retired&&
                !f.adapter.take_completion(*head),"Actual Native8 retirement preceded or differed from exact null publication");return true;};
            check(f.adapter.complete(effect.ticket,actual)&&!f.adapter.terminal()&&!f.terminal.calls&&
                !f.adapter.retirement_pending()&&!f.adapter.prepare()&&f.delivered.size()==2&&!f.adapter.available(),
                "Exact actual Native8 retirement requested redundant9 or terminalized a known result");
            const auto completed=f.completion(*head);check(completed.result.admission==Admission::completed&&completed.result.receipt&&
                completed.result.receipt->outcome==outcome&&!completed.result.receipt->basis&&!completed.result.receipt->default_token&&
                completed.result.receipt->retirement==f.delivered.back().retirement&&
                completed.result.receipt->retirement->identity==actual.readback_identity&&
                completed.result.receipt->retirement->observation_revision==101&&!f.adapter.pending(),
                "Actual Native8 proof changed original known outcome or failed receipt/publication pairing");
        }
    });
    run("Actual observation retirement preserves checked ended composition in receipt and publication", [] {
        AsyncFixture f;f.live.composition=77;f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,77};f.activate();
        auto packet=key_packet(f.basis());std::get<KeyData>(packet.observation.data).is_composing=true;
        const auto head=f.adapter.submit(packet);check(head.has_value(),"Native8 composition retirement missing");const auto effect=f.observation(*head);
        check(f.adapter.request_retirement(),"Composition native redaction missing");
        auto actual=unavailable(f.live,Outcome::applied);actual.retired=f.live.retire;actual.composition_readback_attested=true;
        actual.composition=CompositionFact{77,CompositionState::ended};
        check(f.adapter.complete(effect.ticket,actual)&&!f.adapter.retirement_pending()&&!f.adapter.prepare()&&!f.adapter.terminal(),
            "Actual ended composition retirement required an invented second cleanup");
        const auto complete=f.completion(*head);check(complete.result.receipt&&complete.result.receipt->outcome==Outcome::applied&&
            complete.result.receipt->composition==actual.composition&&f.delivered.back().composition==actual.composition&&
            complete.result.receipt->retirement==f.delivered.back().retirement&&
            complete.result.receipt->retirement->authority_retired&&!f.adapter.pending(),
            "Actual ended composition fact differed between retained receipt and paired null publication");
    });
    run("Actual native-zero observation retirement clears logical pending without invented composition", [] {
        for(const auto outcome:{Outcome::applied,Outcome::cancelled}){
            AsyncFixture f;f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,0};f.activate();
            auto begin=f.packet();begin.observation.kind=Kind::composition;begin.observation.authority=Authority::range;
            begin.observation.transaction=77;begin.observation.after.reset();CompositionData data;
            data.operation=foundation::gui_surface::CompositionOperation::begin;data.replacement=ByteRange{3,3};data.selection={0,0};begin.observation.data=data;
            const auto first=f.adapter.submit(begin);check(first.has_value(),"Native-zero logical begin missing");const auto initial_effect=f.observation(*first);
            auto pending=applied(f.live);pending.composition_readback_attested=true;pending.composition=CompositionFact{77,CompositionState::pending};
            check(f.adapter.complete(initial_effect.ticket,pending)&&f.completion(*first).result.admission==Admission::completed,
                "Native-zero logical pending state did not complete");
            auto key=key_packet(f.basis(),2);key.observation.predecessor=1;std::get<KeyData>(key.observation.data).is_composing=true;
            const auto head=f.adapter.submit(key);check(head.has_value(),"Native-zero physical key missing");const auto effect=f.observation(*head);
            check(f.adapter.request_retirement(),"Native-zero redaction missing");auto actual=unavailable(f.live,outcome);actual.retired=f.live.retire;
            check(f.adapter.complete(effect.ticket,actual)&&!f.adapter.terminal()&&!f.adapter.retirement_pending()&&!f.adapter.prepare(),
                "Native-zero actual closed proof demanded an invented native composition or redundant9");
            const auto completed=f.completion(*head);check(completed.result.receipt&&completed.result.receipt->outcome==outcome&&
                completed.result.receipt->retirement&&completed.result.receipt->retirement->authority_retired&&
                !completed.result.receipt->composition&&!f.delivered.back().composition&&!f.adapter.pending(),
                "Logical pending retirement fabricated native ended transaction metadata");
        }
    });
    run("Null observation without exact retired proof still requires real owned9", [] {
        AsyncFixture f;f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,0};f.activate();
        const auto head=f.adapter.submit(f.packet());check(head.has_value(),"Unproved Native8 head missing");const auto effect=f.observation(*head);
        check(f.adapter.request_retirement()&&f.adapter.complete(effect.ticket,unavailable(f.live))&&
            f.adapter.retirement_pending()&&!f.adapter.take_completion(*head)&&f.delivered.size()==1,
            "Null Native8 reply alone was treated as actual retirement proof");
        const auto cleanup=f.next();check(cleanup.retirement&&cleanup.retirement->material==*f.live.retire,
            "Unproved Native8 reply lost the exact prior cleanup obligation");
        auto actual=unavailable(f.live,Outcome::applied);actual.retired=f.live.retire;
        check(f.adapter.complete(cleanup.ticket,actual)&&!f.adapter.retirement_pending()&&
            f.completion(*head).result.receipt->outcome==Outcome::cancelled&&!f.adapter.pending(),
            "Real subsequent9 did not preserve original cancelled Native8 outcome");
    });
    run("Malformed observation retirement never satisfies pending redaction", [] {
        for(unsigned field=0;field!=4;++field){
            AsyncFixture f;f.live.retire=NativeRetireMaterial{42,f.live.mapping_id,f.live.identity.context,0};f.activate();
            const auto head=f.adapter.submit(f.packet());check(head.has_value(),"Malformed Native8 head missing");const auto effect=f.observation(*head);
            check(f.adapter.request_retirement(),"Malformed Native8 redaction missing");auto actual=unavailable(f.live,Outcome::applied);actual.retired=f.live.retire;
            if(field==0)++actual.retired->token;
            if(field==1)actual.readback_attested=false;
            if(field==2)actual.observation_revision=0;
            if(field==3)actual.continuity=Continuity::same;
            check(f.adapter.complete(effect.ticket,actual)&&f.adapter.terminal()&&f.terminal.calls==1&&
                f.adapter.retirement_pending()&&f.delivered.size()==1&&!f.adapter.prepare(),
                "Malformed Native8 proof released redaction as successful cleanup");
            const auto failed=f.completion(*head);check(failed.result.admission==Admission::terminal,
                "Malformed Native8 proof produced normal browser completion");
        }
    });
    std::cout << cases << " native editor context adapter cases, " << checks << " assertions; "
              << failures << " failed; no engine/browser/native qualification\n";
    return failures ? 1 : 0;
}
