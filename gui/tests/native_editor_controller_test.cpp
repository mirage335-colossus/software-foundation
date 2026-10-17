// SPDX-License-Identifier: CC0-1.0
// Pure owner admission model. No WebCore, browser, platform input or engine runs.
#include "native_editor_controller.hpp"
#include <functional>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <utility>

using namespace foundation::ui::native_editor;
using foundation::gui_surface::CompositionOperation;
using foundation::gui_surface::KeyPhase;

namespace {
void check(bool condition, const char* detail) { if (!condition) throw std::runtime_error(detail); }
NativeProjection initial() {
    NativeProjection result;
    result.identity = {{"editor", 3}, 11, 4, 5, 6};
    result.editor_revision = 9007199254740993ull;
    result.surrounding = "abc"; result.selection = {3, 3};
    result.mapping_id = 1; result.frame_id = 2; result.readback_attested = true;
    return result;
}
TextObservation observed(std::string value = "abc", std::size_t begin = 3, std::size_t end = 3,
                         Direction direction = Direction::none) {
    const auto size = value.size();
    return {std::move(value), begin, end, direction, {begin, end}, size};
}
Observation key_observation(std::uint64_t group = 1, std::string key = "a", std::string code = "KeyA") {
    Observation result;
    result.kind = Kind::key; result.authority = Authority::native; result.group = group;
    result.before = observed(); result.after = result.before; // Actual conduit shape.
    KeyData data; data.transition.key = std::move(key); data.transition.code = std::move(code);
    result.data = std::move(data);
    return result;
}
Observation text_observation() {
    Observation result;
    result.kind = Kind::text; result.authority = Authority::range;
    result.before = observed(); result.after = observed("abcX", 4, 4);
    TextData data; data.input_type = "insertText"; data.text = "X"; data.replacement = {3, 3};
    result.data = std::move(data);
    return result;
}
Observation composition_observation(CompositionOperation operation, std::string text = "") {
    Observation result;
    result.kind = Kind::composition; result.transaction = 77;
    result.authority = operation == CompositionOperation::begin ? Authority::range : Authority::composition;
    result.before = observed();
    CompositionData data; data.operation = operation; data.text = std::move(text);
    data.selection = {0, 0};
    if (operation == CompositionOperation::begin) data.replacement = ByteRange{3, 3};
    result.data = std::move(data);
    return result;
}
struct Fake final : Backend {
    NativeProjection live = initial();
    unsigned projects = 0, effects = 0, revocations = 0;
    std::function<NativeResult(const NativeRequest&)> effect;
    std::function<NativeResult(const Revocation&)> revoke_effect;
    std::function<void()> on_project;
    NativeResult applied() const {
        NativeResult result; result.outcome = Outcome::applied; result.projection = live;
        return result;
    }
    std::optional<NativeProjection> project(std::uint64_t mapping) override {
        ++projects; if (on_project) on_project();
        check(mapping == live.mapping_id, "Owner passed wrong private mapping"); return live;
    }
    NativeResult apply(const NativeRequest& request) override {
        ++effects;
        auto result = effect ? effect(request) : applied();
        if (result.projection) live = *result.projection;
        return result;
    }
    NativeResult revoke(const Revocation& request) override {
        ++revocations;
        auto result = revoke_effect ? revoke_effect(request) : applied();
        if (result.projection) live = *result.projection;
        return result;
    }
};
struct Fixture {
    Fake native;
    Controller owner{native};
    std::uint64_t serial = 0;
    Fixture() { check(bool(owner.activate(native.live)), "Initial activation failed"); }
    Packet packet(Observation observation) {
        check(owner.current_basis() != nullptr, "No usable basis for fixture packet");
        Packet result; result.session = 8; result.basis = *owner.current_basis();
        observation.id = ++serial;
        if (const auto* previous = owner.last_receipt()) observation.predecessor = previous->id;
        result.observation = std::move(observation);
        return result;
    }
    Receipt complete(Observation observation) {
        auto result = owner.process(packet(std::move(observation)));
        if (result.admission != Admission::completed || !result.receipt)
            throw std::runtime_error("Expected completed native receipt: " + result.detail);
        return *result.receipt;
    }
    Receipt grant(std::uint64_t group = 1, std::string logical = "a", std::string code = "KeyA") {
        native.effect = [&](const NativeRequest&) {
            auto result = native.applied(); result.key_dispatch_attested = true; result.allow_default = true; return result;
        };
        auto result = complete(key_observation(group, std::move(logical), std::move(code)));
        check(bool(result.default_token), "Native keydown did not grant default");
        native.effect = {};
        return result;
    }
    Packet default_packet(const std::vector<DefaultDependency>& dependencies) {
        auto observation = text_observation(); observation.authority = Authority::default_action;
        observation.group = dependencies.back().group; observation.group_end = true;
        auto& data = std::get<TextData>(observation.data);
        for (auto dependency : dependencies) data.source_groups.push_back(dependency.group);
        auto result = packet(std::move(observation)); result.default_dependencies = dependencies;
        result.default_token = dependencies.back().token;
        return result;
    }
};
struct AsyncFixture {
    Controller owner;
    NativeProjection live = initial();
    std::uint64_t serial = 0;
    AsyncFixture() { check(bool(owner.activate(live)), "Async activation failed"); }
    Packet packet(Observation observation = text_observation()) {
        check(owner.current_basis() != nullptr, "No async fixture basis");
        Packet result; result.session = 8; result.basis = *owner.current_basis();
        observation.id = ++serial;
        if (const auto* previous = owner.last_receipt()) observation.predecessor = previous->id;
        result.observation = std::move(observation); return result;
    }
    NativeResult applied() const {
        NativeResult result; result.outcome = Outcome::applied; result.projection = live; return result;
    }
    PreparedDispatch prepare(Packet packet) {
        const auto head = owner.begin(std::move(packet));
        check(head.admission == Admission::awaiting_projection && head.ticket && !head.request && !head.revocation,
              "Async head did not wait for projection");
        auto result = owner.supply_projection(head.ticket, live);
        check(result.admission == Admission::prepared, "Async projection did not prepare effect"); return result;
    }
};
NativeResult retirement_proof(const NativeProjection& owned) {
    NativeResult result; result.outcome = Outcome::applied; result.continuity = Continuity::replaced;
    result.availability = NativeAvailability::unavailable; result.observation_revision = 99;
    result.readback_identity = owned.identity; result.readback_attested = true; result.retired = owned.retire;
    return result;
}
}

int main() {
    unsigned cases = 0, failed = 0;
    auto run = [&](const char* name, const std::function<void()>& body) {
        ++cases;
        try { body(); }
        catch (const std::exception& error) { ++failed; std::cerr << name << ": " << error.what() << '\n'; }
    };
    run("Activation owns full-width projection without callbacks", [] {
        Fixture f; auto input = f.native.live;
        check(f.native.projects == 0 && f.native.effects == 0, "Activation entered backend");
        const auto token = f.owner.current_basis()->token;
        input.identity.presentation_revision = 99;
        check(f.owner.activate(input)->token == token, "Metadata refresh spent native authority");
        input.surrounding = "foreign";
        check(f.owner.current_basis()->surrounding == "abc", "Projection was not owned");
        check(f.owner.current_basis()->editor_revision == 9007199254740993ull, "Revision narrowed");
    });
    run("Malformed native projections never activate", [] {
        for (unsigned variant = 0; variant < 7; ++variant) {
            Fake native; Controller owner(native); auto value = native.live;
            if (variant == 0) value.mapping_id = 0;
            if (variant == 1) value.frame_id = 0;
            if (variant == 2) value.readback_attested = false;
            if (variant == 3) value.editor_revision = 0;
            if (variant == 4) value.surrounding = std::string("bad\0text", 8);
            if (variant == 5) { value.surrounding = "é"; value.selection = {1, 1}; }
            if (variant == 6) value.identity.owner.id.clear();
            check(!owner.activate(value), "Invalid projection was admitted");
            check(native.effects == 0 && native.projects == 0, "Validation called backend");
        }
    });
    run("Actual outcome and opaque decreasing native revision win over proxy after", [] {
        Fixture f;
        f.native.effect = [&](const NativeRequest& request) {
            check(request.resolved.mapping_id == 1, "Wrong resolved mapping");
            auto result = f.native.applied(); result.projection->surrounding = "author script";
            result.projection->selection = {0, 0}; result.projection->editor_revision = 3;
            result.projection->mapping_id = 10; return result;
        };
        const auto receipt = f.complete(text_observation());
        check(receipt.basis->surrounding == "author script" && receipt.basis->editor_revision == 3,
              "Controller guessed post-state from UA text");
    });
    run("Foreign basis fields reject before effects with known correlated receipt", [] {
        for (unsigned variant = 0; variant < 5; ++variant) {
            Fixture f; auto packet = f.packet(text_observation());
            if (variant == 0) ++packet.basis.token;
            if (variant == 1) ++packet.basis.editor_revision;
            if (variant == 2) packet.basis.backward = true;
            if (variant == 3) ++packet.basis.identity.context;
            if (variant == 4) packet.basis.surrounding = "same-sized foreign text";
            const auto result = f.owner.process(packet);
            check(result.admission == Admission::rejected && result.receipt && result.receipt->outcome == Outcome::rejected,
                  "Known rejection became uncertain effect");
            check(result.receipt->submitted_token == packet.basis.token && f.native.effects == 0, "Rejection correlation/effects changed");
        }
    });
    run("Causal predecessor allows gaps but rejects foreign joins", [] {
        Fixture f; auto first = f.packet(text_observation()); first.observation.id = 7;
        check(f.owner.process(first).admission == Admission::completed, "Initial observation gap rejected");
        auto next = f.packet(text_observation()); next.observation.id = 19;
        check(f.owner.process(next).admission == Admission::completed, "Causal gap rejected");
        auto stale = f.packet(text_observation()); stale.observation.id = 21; stale.observation.predecessor = 7;
        check(f.owner.process(stale).admission == Admission::rejected && f.native.effects == 2, "Foreign predecessor entered backend");
    });
    run("Exact before projection and direction protect range edits", [] {
        Fixture f; auto packet = f.packet(text_observation()); packet.observation.before.selection_direction = Direction::backward;
        check(f.owner.process(packet).admission == Admission::rejected && f.native.effects == 0, "Range silently rebased direction");
    });
    run("Independent UTF16 and scalar byte ranges are checked", [] {
        Fixture f; auto packet = f.packet(text_observation());
        packet.observation.before = {"aé😀z", 1, 4, Direction::backward, {1, 7}, 8};
        packet.observation.before.selection.end = 3;
        check(f.owner.process(packet).admission == Admission::rejected && f.native.projects == 0, "Forged scalar join accepted");
    });
    run("Text cannot change outside captured replacement flanks", [] {
        Fixture f; auto packet = f.packet(text_observation()); packet.observation.after->value = "Xabc";
        check(f.owner.process(packet).admission == Admission::rejected && f.native.projects == 0, "Coincident text granted range");
    });
    run("Physical key identity survives logical modifier changes", [] {
        Fixture f; f.complete(key_observation(1, "A", "KeyA"));
        auto repeat = key_observation(2, "a", "KeyA"); std::get<KeyData>(repeat.data).transition.repeat = true;
        f.complete(repeat);
        auto up = key_observation(2, "a", "KeyA"); up.group_end = true;
        std::get<KeyData>(up.data).transition.phase = KeyPhase::up;
        f.complete(up); check(f.native.effects == 3, "Physical key ownership was lost");
    });
    run("Unknown physical key release and repeat are rejected", [] {
        for (bool repeat : {false, true}) {
            Fixture f; auto key = key_observation();
            std::get<KeyData>(key.data).transition.repeat = repeat;
            if (!repeat) std::get<KeyData>(key.data).transition.phase = KeyPhase::up;
            check(f.owner.process(f.packet(key)).admission == Admission::rejected && f.native.effects == 0,
                  "Unowned physical transition entered backend");
        }
    });
    run("Native cancellation/default handling/frame change never grants text", [] {
        for (unsigned variant = 0; variant < 4; ++variant) {
            Fixture f; f.native.effect = [&](const NativeRequest&) {
                auto result = f.native.applied(); result.allow_default = true; result.key_dispatch_attested = variant != 3;
                result.default_prevented = variant == 0; result.default_handled = variant == 1;
                result.changed_focused_frame = variant == 2; return result;
            };
            check(!f.complete(key_observation()).default_token && f.owner.default_groups() == 0, "Cancelled native default leaked authority");
        }
    });
    run("Default uses actual post-key mapping rather than old UA range", [] {
        Fixture f; f.native.effect = [&](const NativeRequest&) {
            auto result = f.native.applied(); result.projection->selection = {0, 0}; result.projection->mapping_id = 9;
            result.key_dispatch_attested = result.allow_default = true; return result;
        };
        const auto key = f.complete(key_observation());
        f.native.effect = [&](const NativeRequest& request) {
            check(request.resolved.mapping_id == 9 && request.resolved.selection == ByteRange{0, 0}, "Default reused proxy native range");
            check(f.owner.current_basis() == nullptr && f.owner.default_groups() == 0, "Authority survived effect boundary");
            return f.native.applied();
        };
        auto packet = f.default_packet({*key.default_token});
        check(f.owner.process(packet).admission == Admission::completed, "Valid default rejected old proxy range");
    });
    run("Dead-prefix default joins every ordered owner token", [] {
        Fixture f; const auto dead = f.grant(10, "Dead", "Quote"), base = f.grant(20);
        auto packet = f.default_packet({*dead.default_token, *base.default_token});
        check(f.owner.process(packet).admission == Admission::completed && f.owner.default_groups() == 0,
              "Matched default dependencies were not spent together");
    });
    run("Missing duplicate unordered or forged default dependencies reject", [] {
        for (unsigned variant = 0; variant < 4; ++variant) {
            Fixture f; const auto dead = f.grant(10, "Dead", "Quote"), base = f.grant(20);
            auto packet = f.default_packet({*dead.default_token, *base.default_token});
            if (variant == 0) packet.default_dependencies.erase(packet.default_dependencies.begin());
            if (variant == 1) packet.default_dependencies[0] = packet.default_dependencies[1];
            if (variant == 2) { std::swap(packet.default_dependencies[0], packet.default_dependencies[1]); packet.default_token = packet.default_dependencies.back().token; }
            if (variant == 3) ++packet.default_dependencies[0].token;
            check(f.owner.process(packet).admission == Admission::rejected && f.native.effects == 2, "Invalid default source reached native effect");
        }
    });
    run("Display-only refresh retains exact token and native default chain", [] {
        Fixture f; const auto grant = f.grant(); auto packet = f.default_packet({*grant.default_token});
        auto refresh = f.native.live; ++refresh.identity.presentation_revision;
        const auto token = f.owner.current_basis()->token;
        check(f.owner.activate(refresh)->token == token, "Display refresh spent native token");
        f.native.live = refresh;
        check(f.owner.process(packet).admission == Admission::completed, "Exact older display alias lost native authority");
    });
    run("Same-frame retarget needs actual native attestation", [] {
        for (bool attested : {false, true}) {
            Fixture f; f.native.effect = [&](const NativeRequest&) {
                auto result = f.native.applied(); ++result.projection->identity.context; ++result.projection->mapping_id;
                result.continuity = Continuity::key_retarget;
                result.key_dispatch_attested = true; result.key_retarget_attested = attested; return result;
            };
            const auto result = f.owner.process(f.packet(key_observation()));
            check((result.admission == Admission::completed) == attested, "Retarget attestation ignored");
            if (!attested) check(f.owner.terminal(), "Unattested consumed outcome stayed live");
        }
    });
    run("Native unknown and thrown effects cannot replay or reactivate", [] {
        for (bool throws : {false, true}) {
            Fixture f; auto packet = f.packet(text_observation());
            f.native.effect = [&](const NativeRequest&) -> NativeResult {
                if (throws) throw std::runtime_error("unknown native effect");
                return {};
            };
            const auto result = f.owner.process(packet);
            check(result.admission == Admission::terminal && f.owner.terminal() && *f.owner.unresolved() == packet, "Unknown evidence lost");
            check(!f.owner.activate(f.native.live), "Unknown effect reactivated");
            f.owner.process(packet); check(f.native.effects == 1, "Unknown effect replayed");
        }
    });
    run("Reentrant callbacks see consumed authority and cannot dispatch", [] {
        Fixture f; const auto packet = f.packet(text_observation());
        f.native.effect = [&](const NativeRequest&) {
            check(f.owner.processing() && !f.owner.current_basis(), "Effect saw reusable current token");
            check(f.owner.process(packet).admission == Admission::busy, "Reentrant effect was admitted");
            return f.native.applied();
        };
        check(f.owner.process(packet).admission == Admission::completed && f.native.effects == 1, "Reentry duplicated effect");
    });
    run("Composition pending/live/empty/pending/live/end uses native facts", [] {
        Fixture f;
        auto apply = [&](Observation observation, CompositionState state) {
            f.native.effect = [&](const NativeRequest& request) {
                if (std::get<CompositionData>(request.packet.observation.data).operation == CompositionOperation::update &&
                    std::get<CompositionData>(request.packet.observation.data).text == "é😀")
                    check(std::get<CompositionData>(request.packet.observation.data).selection == ByteRange{2, 2}, "Preedit selection was guessed");
                auto result = f.native.applied(); result.projection->composition = state == CompositionState::live ? 77 : 0;
                result.composition = CompositionFact{77, state}; result.composition_readback_attested = true; return result;
            };
            f.complete(std::move(observation));
        };
        apply(composition_observation(CompositionOperation::begin), CompositionState::pending);
        auto unicode = composition_observation(CompositionOperation::update, "é😀");
        std::get<CompositionData>(unicode.data).selection = {2, 2};
        apply(unicode, CompositionState::live);
        apply(composition_observation(CompositionOperation::update), CompositionState::pending);
        apply(unicode, CompositionState::live);
        apply(composition_observation(CompositionOperation::commit, "é😀"), CompositionState::ended);
        check(f.owner.current_basis()->composition == 0 && f.native.effects == 5, "Native composition did not end once");
    });
    run("Void composition calls require actual transaction readback", [] {
        for (unsigned variant = 0; variant < 4; ++variant) {
            Fixture f; f.native.effect = [&](const NativeRequest&) {
                auto result = f.native.applied(); result.projection->composition = 77;
                result.composition = CompositionFact{variant == 1 ? 88u : 77u, CompositionState::live};
                result.composition_readback_attested = variant != 0;
                if (variant == 2) result.composition.reset();
                if (variant == 3) result.projection->composition = 0;
                return result;
            };
            check(f.owner.process(f.packet(composition_observation(CompositionOperation::begin))).admission == Admission::terminal,
                  "Unattested composition result published");
        }
    });
    run("Publication failure retains consumed applied outcome and stops exports", [] {
        Fixture f; const auto packet = f.packet(text_observation()); f.owner.process(packet);
        const auto receipt = *f.owner.last_receipt(); f.owner.notify_publication_failure();
        check(f.owner.terminal() && *f.owner.last_receipt() == receipt && *f.owner.unresolved() == packet, "Publication failure discarded native evidence");
        check(!f.owner.activate(f.native.live), "Publication failure rearmed controller");
        f.owner.process(packet); check(f.native.effects == 1, "Publication failure replayed native edit");
    });
    run("Known native rejection suspends rather than reporting unknown", [] {
        Fixture f; f.native.effect = [&](const NativeRequest&) { auto result = f.native.applied(); result.outcome = Outcome::cancelled; return result; };
        const auto receipt = f.complete(text_observation());
        check(receipt.outcome == Outcome::cancelled && f.owner.state() == State::suspended && !f.owner.terminal(), "Known native rejection became uncertain");
    });
    run("Revoke requires exact owned held keys and native readback", [] {
        Fixture f; f.complete(key_observation(1, "A", "KeyA"));
        Revocation revoke; revoke.basis = *f.owner.current_basis(); revoke.incarnation = 99; revoke.reason = "focus";
        auto held = std::get<KeyData>(key_observation(1, "a", "KeyA").data); revoke.held_keys = {held};
        f.native.revoke_effect = [&](const Revocation& request) {
            check(request.held_keys.size() == 1, "Native modifier ownership missing");
            auto result = f.native.applied(); result.composition_readback_attested = true; return result;
        };
        f.owner.revoke();
        check(f.owner.process_revocation(revoke).admission == Admission::completed && f.native.revocations == 1, "Checked native revoke failed");
        check(f.owner.process_revocation(revoke).admission == Admission::rejected && f.native.revocations == 1, "Native cancellation replayed");
        check(f.owner.activate(f.native.live).has_value(), "Known native closure could not reactivate");
    });
    run("Pending transport transaction revokes at native attestation zero", [] {
        Fixture f; f.native.effect = [&](const NativeRequest&) {
            auto result = f.native.applied(); result.composition = CompositionFact{77, CompositionState::pending};
            result.composition_readback_attested = true; return result;
        };
        const auto receipt = f.complete(composition_observation(CompositionOperation::begin));
        Revocation revoke; revoke.basis = *receipt.basis; revoke.incarnation = 7; revoke.composition = 77;
        f.native.revoke_effect = [&](const Revocation& request) {
            check(request.composition == 77 && request.basis.composition == 0, "Pending and native transaction conflated");
            auto result = f.native.applied(); result.composition_readback_attested = true; return result;
        };
        check(f.owner.process_revocation(revoke).admission == Admission::completed, "Pending transaction could not close");
    });
    run("Unknown revoke is terminal and retains exact native cleanup evidence", [] {
        Fixture f; Revocation revoke; revoke.basis = *f.owner.current_basis(); revoke.incarnation = 7;
        f.native.revoke_effect = [](const Revocation&) -> NativeResult { throw std::runtime_error("unknown cancel"); };
        check(f.owner.process_revocation(revoke).admission == Admission::terminal && f.owner.terminal(), "Unknown cleanup remained reusable");
        check(*f.owner.last_revocation() == revoke, "Native cleanup evidence lost");
        f.owner.process_revocation(revoke); check(f.native.revocations == 1, "Unknown native cleanup replayed");
    });
    run("Projection callbacks cannot resurrect closed or terminal owners", [] {
        for (bool close : {false, true}) {
            for (bool revoke : {false, true}) {
                Fixture f; const auto packet = f.packet(text_observation());
                Revocation cancellation; cancellation.basis = *f.owner.current_basis(); cancellation.incarnation = 7;
                f.native.on_project = [&] { if (close) f.owner.close(); else f.owner.notify_publication_failure(); };
                const auto result = revoke ? f.owner.process_revocation(cancellation) : f.owner.process(packet);
                check(result.admission == Admission::terminal && f.owner.terminal(), "Projection resurrected native lifecycle");
                check(f.native.effects == 0 && f.native.revocations == 0, "Closed owner entered native effect");
                check(!f.owner.activate(f.native.live), "Terminal owner reactivated after query");
            }
        }
    });
    run("Checked drift rejection retains consistent fresh resynchronization basis", [] {
        Fixture f; const auto packet = f.packet(text_observation());
        f.native.live.surrounding = "changed"; f.native.live.selection = {0, 0}; f.native.live.editor_revision = 3;
        const auto result = f.owner.process(packet);
        check(result.admission == Admission::rejected && result.receipt && result.receipt->basis->surrounding == "changed",
              "Known native drift did not return actual readback");
        check(f.owner.current_projection()->surrounding == "changed", "Rejected basis was never retained");
        check(f.owner.activate(f.native.live).has_value() && f.native.effects == 0, "Fresh checked basis could not resynchronize");
    });
    run("Pending transport composition survives display-only metadata refresh", [] {
        Fixture f; f.native.effect = [&](const NativeRequest&) {
            auto result = f.native.applied(); result.composition = CompositionFact{77, CompositionState::pending};
            result.composition_readback_attested = true; return result;
        };
        f.complete(composition_observation(CompositionOperation::begin));
        auto refresh = f.native.live; ++refresh.identity.presentation_revision;
        const auto token = f.owner.current_basis()->token;
        check(f.owner.activate(refresh)->token == token && f.owner.current_composition()->transaction == 77 &&
              f.owner.current_basis()->composition == 0, "Display metadata cancelled pending native ownership");
    });
    run("Native revocation cannot invent same-context or key-retarget continuity", [] {
        for (bool retarget : {false, true}) {
            Fixture f; Revocation revoke; revoke.basis = *f.owner.current_basis(); revoke.incarnation = 7;
            f.native.revoke_effect = [&](const Revocation&) {
                auto result = f.native.applied(); result.composition_readback_attested = true;
                if (retarget) result.continuity = Continuity::key_retarget;
                else ++result.projection->identity.context;
                return result;
            };
            check(f.owner.process_revocation(revoke).admission == Admission::terminal && f.owner.terminal(),
                  "Unattested revocation continuity stayed usable");
        }
    });
    run("Unmatched maximum scalar offsets reject before querying native state", [] {
        for (bool key : {false, true}) {
            Fixture f; auto observation = key ? key_observation() : text_observation();
            observation.before.selection_start = observation.before.selection_end = std::numeric_limits<std::size_t>::max();
            observation.before.selection = {std::numeric_limits<std::size_t>::max(), std::numeric_limits<std::size_t>::max()};
            if (key) observation.after = observation.before;
            const auto result = f.owner.process(f.packet(observation));
            check(result.admission == Admission::rejected && !f.owner.terminal() && f.native.projects == 0 && f.native.effects == 0,
                  "Unmatched scalar boundary entered native state or became uncertain");
        }
    });
    run("Native changes never receive a display-only token alias", [] {
        for (unsigned variant = 0; variant < 6; ++variant) {
            Fixture f; const auto token = f.owner.current_basis()->token; auto next = f.native.live;
            if (variant == 0) ++next.mapping_id;
            if (variant == 1) ++next.frame_id;
            if (variant == 2) ++next.editor_revision;
            if (variant == 3) next.selection = {0, 0};
            if (variant == 4) next.backward = true;
            if (variant == 5) ++next.identity.context;
            const auto activated = f.owner.activate(next);
            check(activated && activated->token != token, "Native authority change retained old token");
        }
    });
    run("Bounded default groups and dependency lists fail closed", [] {
        Fixture f;
        for (std::uint64_t group = 1; group <= Controller::max_default_groups; ++group)
            f.grant(group, "a", "Key" + std::to_string(group));
        check(f.owner.default_groups() == Controller::max_default_groups, "Default fact bound changed");
        check(f.owner.process(f.packet(key_observation(65, "a", "Key65"))).admission == Admission::rejected &&
              f.native.effects == Controller::max_default_groups, "Default fact limit allowed another native effect");
        Fixture excess; auto observation = text_observation(); observation.authority = Authority::default_action; observation.group = 9;
        std::get<TextData>(observation.data).source_groups = {1, 2, 3, 4, 5, 6, 7, 8, 9};
        check(excess.owner.process(excess.packet(observation)).admission == Admission::rejected && excess.native.projects == 0,
              "Oversized dependency list entered native query");
    });
    run("Async owner prepares owned records and completes only actual readback", [] {
        AsyncFixture f; auto packet = f.packet(); const auto original = packet;
        const auto head = f.owner.begin(packet); packet.observation.id = 999;
        check(head.admission == Admission::awaiting_projection && f.owner.awaiting_projection() &&
              f.owner.processing() && !f.owner.current_basis() && *f.owner.unresolved() == original,
              "Projection phase exposed authority or borrowed caller packet");
        check(f.owner.begin(original).admission == Admission::busy && !f.owner.activate(f.live),
              "Another head or activation entered active projection");
        auto prepared = f.owner.supply_projection(head.ticket, f.live);
        check(prepared.admission == Admission::prepared && prepared.ticket == head.ticket && prepared.request &&
              !prepared.revocation && prepared.request->packet == original && prepared.request->resolved == f.live &&
              f.owner.awaiting_result() && !f.owner.current_basis(), "Prepared request lost canonical ownership");
        prepared.request->packet.observation.id = 998; prepared.request->resolved.surrounding = "mutated";
        auto result = f.applied(); result.projection->surrounding = "actual"; result.projection->selection = {6, 6};
        const auto completed = f.owner.complete(head.ticket, result);
        check(completed.admission == Admission::completed && completed.receipt && completed.receipt->id == original.observation.id &&
              completed.receipt->basis->surrounding == "actual" && !f.owner.processing() && f.owner.current_basis(),
              "Completion used proxy or mutable returned request");
        check(f.owner.process(f.packet()).admission == Admission::unavailable, "Async owner fabricated a synchronous backend");
    });
    run("Async methods never invoke even an installed synchronous backend", [] {
        Fixture f; const auto packet = f.packet(text_observation());
        const auto head = f.owner.begin(packet); const auto prepared = f.owner.supply_projection(head.ticket, f.native.live);
        const auto result = f.owner.complete(prepared.ticket, f.native.applied());
        check(result.admission == Admission::completed && f.native.projects == 0 && f.native.effects == 0 && f.native.revocations == 0,
              "Async split entered Backend callbacks");
    });
    run("Async and synchronous paths share admission and default issuance", [] {
        Fixture sync; AsyncFixture async;
        const auto packet = sync.packet(key_observation());
        sync.native.effect = [&](const NativeRequest&) {
            auto result = sync.native.applied(); result.key_dispatch_attested = result.allow_default = true; return result;
        };
        const auto synchronous = sync.owner.process(packet);
        const auto prepared = async.prepare(packet); auto actual = async.applied();
        actual.key_dispatch_attested = actual.allow_default = true;
        const auto split = async.owner.complete(prepared.ticket, actual);
        check(synchronous.admission == split.admission && synchronous.receipt == split.receipt &&
              *sync.owner.current_basis() == *async.owner.current_basis() && async.owner.default_groups() == 1,
              "Split path changed native admission or owner-issued defaults");
    });
    run("Wrong duplicate and delayed tickets preserve a newer active head", [] {
        AsyncFixture f; const auto first = f.prepare(f.packet());
        check(f.owner.supply_projection(first.ticket, f.live).admission == Admission::rejected && f.owner.awaiting_result(),
              "Duplicate projection consumed prepared head");
        check(f.owner.complete(first.ticket + 1, f.applied()).admission == Admission::rejected && f.owner.awaiting_result(),
              "Foreign completion consumed prepared head");
        check(f.owner.complete(first.ticket, f.applied()).admission == Admission::completed, "First completion failed");
        const auto packet = f.packet(); const auto second = f.owner.begin(packet);
        check(second.ticket > first.ticket && f.owner.supply_projection(first.ticket, f.live).admission == Admission::rejected &&
              f.owner.awaiting_projection() && *f.owner.unresolved() == packet, "Late projection affected later head");
        const auto prepared = f.owner.supply_projection(second.ticket, f.live);
        check(f.owner.complete(first.ticket, f.applied()).admission == Admission::rejected && f.owner.awaiting_result(),
              "Late completion affected later effect");
        check(f.owner.complete(prepared.ticket, f.applied()).admission == Admission::completed &&
              f.owner.complete(prepared.ticket, f.applied()).admission == Admission::rejected,
              "New head failed or replayed after completion");
    });
    run("Async projection rejection is known and enters no effect phase", [] {
        AsyncFixture f; const auto packet = f.packet(); const auto head = f.owner.begin(packet);
        auto changed = f.live; changed.surrounding = "fresh"; changed.selection = {5, 5}; ++changed.mapping_id;
        const auto denied = f.owner.supply_projection(head.ticket, changed);
        check(denied.admission == Admission::rejected && denied.receipt && denied.receipt->outcome == Outcome::rejected &&
              denied.receipt->id == packet.observation.id && denied.receipt->basis->surrounding == "fresh" &&
              !denied.request && !denied.revocation && !f.owner.processing() && !f.owner.terminal(),
              "Known projection drift fabricated effects or unknown outcome");
        AsyncFixture missing; const auto pending = missing.owner.begin(missing.packet());
        check(missing.owner.supply_projection(pending.ticket, std::nullopt).admission == Admission::rejected &&
              !missing.owner.awaiting_result(), "Missing projection entered effect phase");
    });
    run("Async defaults are spent before returning one effect request", [] {
        AsyncFixture f; const auto key_packet = f.packet(key_observation());
        auto prepared = f.prepare(key_packet); auto actual = f.applied();
        actual.key_dispatch_attested = actual.allow_default = true;
        const auto key_result = f.owner.complete(prepared.ticket, actual);
        const auto dependency = *key_result.receipt->default_token;
        auto observation = text_observation(); observation.authority = Authority::default_action;
        observation.group = dependency.group; observation.group_end = true;
        std::get<TextData>(observation.data).source_groups = {dependency.group};
        auto packet = f.packet(observation); packet.default_token = dependency.token; packet.default_dependencies = {dependency};
        prepared = f.prepare(packet);
        check(f.owner.default_groups() == 0 && !f.owner.current_basis() &&
              f.owner.begin(packet).admission == Admission::busy, "Prepared native effect retained spendable default authority");
        f.owner.notify_transport_failure();
        check(f.owner.terminal() && f.owner.last_receipt() && f.owner.last_receipt()->outcome == Outcome::unknown &&
              !f.owner.last_receipt()->basis && *f.owner.unresolved() == packet &&
              f.owner.complete(prepared.ticket, actual).admission == Admission::terminal,
              "Unknown transport made a default replayable");
    });
    run("Dropped async projection and effect preserve canonical terminal evidence", [] {
        for (bool effect : {false, true}) {
            AsyncFixture f; const auto packet = f.packet(); const auto head = f.owner.begin(packet);
            if (effect) check(f.owner.supply_projection(head.ticket, f.live).admission == Admission::prepared, "Preparation failed");
            f.owner.notify_transport_failure();
            check(f.owner.terminal() && !f.owner.processing() && !f.owner.current_basis() && !f.owner.activate(f.live) &&
                  f.owner.last_receipt() && f.owner.last_receipt()->id == packet.observation.id &&
                  f.owner.last_receipt()->outcome == Outcome::unknown && !f.owner.last_receipt()->basis &&
                  *f.owner.unresolved() == packet && f.owner.begin(packet).admission == Admission::terminal,
                  "Dropped active transport lost immutable evidence or allowed replay");
        }
    });
    run("Async publication failure preserves actual completed outcome", [] {
        AsyncFixture f; const auto prepared = f.prepare(f.packet());
        const auto completed = f.owner.complete(prepared.ticket, f.applied());
        f.owner.notify_publication_failure();
        check(f.owner.terminal() && f.owner.last_receipt() && *f.owner.last_receipt() == *completed.receipt &&
              f.owner.last_receipt()->outcome == Outcome::applied && !f.owner.current_basis(),
              "Publication fault replaced actual outcome or exposed successor");
    });
    run("Async lifecycle changes cannot resurrect either pending phase", [] {
        for (bool effect : {false, true}) for (unsigned action = 0; action < 3; ++action) {
            AsyncFixture f; const auto head = f.owner.begin(f.packet());
            if (effect) check(f.owner.supply_projection(head.ticket, f.live).admission == Admission::prepared, "Preparation failed");
            if (action == 0) f.owner.close();
            if (action == 1) f.owner.notify_publication_failure();
            if (action == 2) f.owner.revoke();
            if (effect) {
                check(f.owner.complete(head.ticket, f.applied()).admission == Admission::terminal && f.owner.terminal(),
                      "Lifecycle change after effect returned reusable authority");
            } else {
                const auto result = f.owner.supply_projection(head.ticket, f.live);
                check(result.admission == (action == 2 ? Admission::rejected : Admission::terminal) && !result.request &&
                      !f.owner.awaiting_result(), "Lifecycle change during query entered native effect");
            }
        }
    });
    run("Async revocation resolves exact ownership and never returns observation effect", [] {
        AsyncFixture f; const auto press = f.packet(key_observation());
        auto prepared = f.prepare(press); check(f.owner.complete(prepared.ticket, f.applied()).admission == Admission::completed,
                                               "Async press failed");
        Revocation revoke; revoke.basis = *f.owner.current_basis(); revoke.incarnation = 987;
        revoke.reason = "retired"; revoke.held_keys = {std::get<KeyData>(press.observation.data)};
        const auto head = f.owner.begin_revocation(revoke);
        check(head.admission == Admission::awaiting_projection && f.owner.last_revocation() &&
              *f.owner.last_revocation() == revoke, "Revocation head was not retained");
        prepared = f.owner.supply_projection(head.ticket, f.live);
        check(prepared.admission == Admission::prepared && prepared.revocation && *prepared.revocation == revoke &&
              !prepared.request && !f.owner.current_basis(), "Revocation prepared wrong effect or retained authority");
        auto result = f.applied(); result.composition_readback_attested = true;
        const auto completed = f.owner.complete(prepared.ticket, result);
        check(completed.admission == Admission::completed && !completed.receipt && !f.owner.current_basis() &&
              f.owner.begin_revocation(revoke).admission == Admission::rejected, "Revocation replayed or invented observation receipt");
        check(bool(f.owner.activate(f.live)), "Known native closure could not activate fresh basis");
        auto fresh = f.packet(); fresh.observation.predecessor.reset(); // New activation starts a new causal chain.
        const auto next = f.owner.begin(fresh);
        check(next.ticket > head.ticket && f.owner.complete(head.ticket, result).admission == Admission::rejected &&
              f.owner.awaiting_projection(), "Revocation ticket was reused after resync");
    });
    run("Unknown async revocation retains cleanup without fake observation receipt", [] {
        AsyncFixture f; Revocation revoke; revoke.basis = *f.owner.current_basis(); revoke.incarnation = 9;
        const auto head = f.owner.begin_revocation(revoke);
        check(f.owner.supply_projection(head.ticket, f.live).revocation.has_value(), "Revocation did not prepare");
        check(f.owner.complete(head.ticket, NativeResult{}).admission == Admission::terminal &&
              f.owner.terminal() && f.owner.last_revocation() && *f.owner.last_revocation() == revoke && !f.owner.last_receipt() &&
              f.owner.begin_revocation(revoke).admission == Admission::terminal, "Unknown cleanup invented receipt or replayed");
    });
    run("Known preentry revocation rejection preserves the prior owned lifecycle", [] {
        AsyncFixture f; const auto prepared = f.prepare(f.packet(key_observation()));
        check(f.owner.complete(prepared.ticket, f.applied()).admission == Admission::completed, "Press failed");
        const auto before = *f.owner.current_basis();
        Revocation revoke; revoke.basis = before; revoke.incarnation = 9;
        revoke.held_keys = {std::get<KeyData>(key_observation().data)};
        const auto head = f.owner.begin_revocation(revoke);
        const auto denied = f.owner.supply_projection(head.ticket, std::nullopt);
        check(denied.admission == Admission::rejected && !denied.request && !denied.revocation && !denied.receipt &&
              f.owner.state() == State::ready && f.owner.current_basis() && *f.owner.current_basis() == before,
              "Known preentry cleanup rejection changed prior native authority");
        const auto retry = f.owner.begin_revocation(revoke);
        check(retry.ticket > head.ticket && f.owner.supply_projection(retry.ticket, f.live).revocation.has_value(),
              "Preentry rejection erased exact native held-key ownership");
        auto actual = f.applied(); actual.composition_readback_attested = true;
        check(f.owner.complete(retry.ticket, actual).admission == Admission::completed, "Checked cleanup failed");
    });
    run("Async composition requires actual pending and native transaction readback", [] {
        AsyncFixture f; const auto prepared = f.prepare(f.packet(composition_observation(CompositionOperation::begin)));
        auto result = f.applied(); result.composition = CompositionFact{77, CompositionState::pending};
        result.composition_readback_attested = true;
        check(!f.owner.current_composition() && f.owner.complete(prepared.ticket, result).admission == Admission::completed &&
              f.owner.current_composition()->transaction == 77 && f.owner.current_basis()->composition == 0,
              "Prepared request guessed composition or lost attested pending transaction");
        Revocation revoke; revoke.basis = *f.owner.current_basis(); revoke.incarnation = 10; revoke.composition = 77;
        const auto head = f.owner.begin_revocation(revoke);
        check(f.owner.supply_projection(head.ticket, f.live).revocation.has_value(), "Pending transport transaction could not revoke");
        result = f.applied(); result.composition_readback_attested = true;
        check(f.owner.complete(head.ticket, result).admission == Admission::completed && !f.owner.current_composition(),
              "Checked async revocation failed to close pending transaction");
    });
    run("Native geometry and purpose are bounded actual projection facts", [] {
        for (unsigned variant = 0; variant < 8; ++variant) {
            auto value = initial();
            if (variant == 0) value.caret.x = std::numeric_limits<double>::infinity();
            if (variant == 1) value.caret.y = std::numeric_limits<double>::quiet_NaN();
            if (variant == 2) value.caret.width = -1;
            if (variant == 3) value.caret.height = 1000001;
            if (variant == 4) value.caret.x = -1000001;
            if (variant == 5) value.input_purpose.assign(129, 'x');
            if (variant == 6) value.input_purpose = std::string("x\0y", 3);
            if (variant == 7) value.input_purpose = "\xc0\xaf";
            Controller owner; check(!valid_projection(value) && !owner.activate(value), "Invalid native geometry or purpose activated");
        }
        auto value = initial(); value.caret = {-1000000, 1000000, 1000000, 0}; value.input_purpose = "native-purpose";
        check(valid_projection(value), "Valid bounded native geometry rejected");
    });
    run("Projection metadata aliases include geometry editability and native purpose", [] {
        for (unsigned variant = 0; variant < 3; ++variant) {
            AsyncFixture f; const auto old = f.owner.current_basis()->token; auto next = f.live;
            ++next.identity.presentation_revision;
            if (variant == 0) next.caret.x = 1;
            if (variant == 1) next.editable = false;
            if (variant == 2) next.input_purpose = "email";
            const auto fresh = f.owner.activate(next);
            check(fresh && fresh->token != old && *f.owner.current_projection() == next,
                  "Native geometry/editability/purpose change retained display-only token alias");
        }
    });
    run("Provider retirement material is bound to the exact native projection", [] {
        auto value = initial(); value.retire = NativeRetireMaterial{42, value.mapping_id, value.identity.context, value.composition};
        check(valid_retire_material(*value.retire) && valid_projection(value), "Valid provider material rejected");
        for (unsigned variant = 0; variant < 6; ++variant) {
            auto invalid = value;
            if (variant == 0) invalid.retire->token = 0;
            if (variant == 1) invalid.retire->mapping_id = 0;
            if (variant == 2) invalid.retire->input_context = 0;
            if (variant == 3) ++invalid.retire->mapping_id;
            if (variant == 4) ++invalid.retire->input_context;
            if (variant == 5) ++invalid.retire->composition;
            check(!valid_projection(invalid), "Unbound provider retirement material accepted");
        }
        Controller owner; const auto first = owner.activate(value); ++value.identity.presentation_revision;
        check(owner.activate(value)->token == first->token, "Display refresh changed exact provider material");
        ++value.retire->token;
        check(owner.activate(value)->token != first->token, "Changed provider authority received a display-only alias");
    });
    run("Known native retirement suspends with null basis and no invented successor", [] {
        for (const auto availability : {NativeAvailability::noneditable, NativeAvailability::unavailable})
        for (const auto outcome : {Outcome::cancelled, Outcome::rejected}) {
            AsyncFixture f; auto prepared = f.prepare(f.packet(key_observation())); auto actual = f.applied();
            actual.key_dispatch_attested = actual.allow_default = true;
            check(f.owner.complete(prepared.ticket, actual).receipt->default_token.has_value(), "Default fixture did not grant");
            const auto packet = f.packet(); prepared = f.prepare(packet);
            NativeResult retired; retired.outcome = outcome; retired.continuity = Continuity::replaced;
            retired.availability = availability; retired.observation_revision = 90;
            retired.readback_identity = f.live.identity; ++retired.readback_identity.context; retired.readback_attested = true;
            retired.retire = NativeRetireMaterial{98, 100, retired.readback_identity.context, 0};
            const auto result = f.owner.complete(prepared.ticket, retired);
            check(result.admission == Admission::completed && result.receipt && result.receipt->outcome == outcome &&
                  result.receipt->continuity == Continuity::replaced && !result.receipt->basis && !result.receipt->default_token &&
                  !result.receipt->composition && result.receipt->retirement ==
                      std::optional<RetirementReadback>{{availability, retired.readback_identity, 90, true}} &&
                  f.owner.state() == State::suspended && !f.owner.current_basis() &&
                  !f.owner.current_projection() && !f.owner.current_composition() && f.owner.default_groups() == 0 &&
                  !f.owner.terminal() && f.owner.begin(packet).admission == Admission::unavailable &&
                  f.owner.complete(prepared.ticket, retired).admission == Admission::rejected,
                  "Known retirement fabricated a basis, continued authority or became unknown");
            check(bool(f.owner.activate(f.live)), "Known retirement did not release stale held-key metadata");
        }
    });
    run("Projectionless native results require exact explicit retirement attestation", [] {
        for (unsigned variant = 0; variant < 15; ++variant) {
            AsyncFixture f; const auto prepared = f.prepare(f.packet());
            NativeResult result; result.outcome = Outcome::cancelled; result.continuity = Continuity::replaced;
            result.availability = NativeAvailability::unavailable; result.observation_revision = 90;
            result.readback_identity = f.live.identity; result.readback_attested = true;
            if (variant == 0) result.readback_attested = false;
            if (variant == 1) result.observation_revision = 0;
            if (variant == 2) result.readback_identity.owner.id = "foreign";
            if (variant == 3) ++result.readback_identity.owner.generation;
            if (variant == 4) ++result.readback_identity.generation;
            if (variant == 5) ++result.readback_identity.epoch;
            if (variant == 6) result.readback_identity.context = 0;
            if (variant == 7) result.outcome = Outcome::applied;
            if (variant == 8) result.continuity = Continuity::same;
            if (variant == 9) result.availability = NativeAvailability::available;
            if (variant == 10) result.projection = f.live;
            if (variant == 11) result.composition = CompositionFact{77, CompositionState::pending};
            if (variant == 12) result.allow_default = true;
            if (variant == 13) result.retire = NativeRetireMaterial{42, 1, f.live.identity.context + 1, 0};
            if (variant == 14) result.availability = static_cast<NativeAvailability>(99);
            const auto completed = f.owner.complete(prepared.ticket, result);
            check(completed.admission == Admission::terminal && f.owner.terminal() && f.owner.last_receipt() &&
                  f.owner.last_receipt()->outcome == Outcome::unknown && !f.owner.last_receipt()->basis,
                  "Unattested native retirement published a guessed basis or known receipt");
        }
    });
    run("Explicit available readback metadata cannot contradict the actual projection", [] {
        for (unsigned variant = 0; variant < 6; ++variant) {
            AsyncFixture f; const auto prepared = f.prepare(f.packet()); auto result = f.applied();
            result.observation_revision = 90; result.readback_identity = f.live.identity; result.readback_attested = true;
            if (variant == 0) result.readback_attested = false;
            if (variant == 1) result.observation_revision = 0;
            if (variant == 2) ++result.readback_identity.context;
            if (variant == 3) result.retire = NativeRetireMaterial{0, 1, f.live.identity.context, 0};
            if (variant == 4) result.retire = NativeRetireMaterial{42, 2, f.live.identity.context, 0};
            if (variant == 5) {
                result.projection->retire = NativeRetireMaterial{42, 1, f.live.identity.context, 0};
                result.retire = NativeRetireMaterial{43, 1, f.live.identity.context, 0};
            }
            check(f.owner.complete(prepared.ticket, result).admission == Admission::terminal,
                  "Contradictory explicit native readback metadata accepted");
        }
        AsyncFixture valid; const auto prepared = valid.prepare(valid.packet()); auto result = valid.applied();
        result.observation_revision = 90; result.readback_identity = valid.live.identity; result.readback_attested = true;
        result.projection->retire = NativeRetireMaterial{42, 1, valid.live.identity.context, 0}; result.retire = result.projection->retire;
        check(valid.owner.complete(prepared.ticket, result).admission == Admission::completed &&
              valid.owner.current_projection()->retire == result.retire, "Checked provider material was not retained exactly");
    });
    run("Synchronous wrapper preserves known projectionless native retirement", [] {
        Fixture f; f.native.effect = [&](const NativeRequest&) {
            NativeResult result; result.outcome = Outcome::rejected; result.continuity = Continuity::replaced;
            result.availability = NativeAvailability::noneditable; result.observation_revision = 3;
            result.readback_attested = true; result.readback_identity = f.native.live.identity; return result;
        };
        const auto result = f.owner.process(f.packet(text_observation()));
        check(result.admission == Admission::completed && result.receipt && !result.receipt->basis &&
              result.receipt->outcome == Outcome::rejected && !f.owner.terminal() &&
              f.native.projects == 1 && f.native.effects == 1, "Synchronous wrapper changed known retirement behavior");
    });
    run("Provider material returned only on available result remains owned", [] {
        for (bool revoke : {false, true}) {
            AsyncFixture f; PreparedDispatch prepared;
            if (revoke) {
                Revocation request; request.basis = *f.owner.current_basis(); request.incarnation = 9;
                const auto head = f.owner.begin_revocation(request);
                prepared = f.owner.supply_projection(head.ticket, f.live);
            } else prepared = f.prepare(f.packet());
            auto result = f.applied(); result.retire = NativeRetireMaterial{42, f.live.mapping_id, f.live.identity.context, 0};
            result.composition_readback_attested = true;
            check(f.owner.complete(prepared.ticket, result).admission == Admission::completed &&
                  f.owner.current_projection() && f.owner.current_projection()->retire == result.retire,
                  "Result-only provider material disappeared from owned native projection");
        }
    });
    run("Projectionless owned revocation requires exact provider retirement proof", [] {
        for (const auto availability : {NativeAvailability::noneditable, NativeAvailability::unavailable}) {
            AsyncFixture f; f.live.retire = NativeRetireMaterial{42, f.live.mapping_id, f.live.identity.context, 0};
            check(bool(f.owner.activate(f.live)), "Provider authority fixture did not activate");
            Revocation request; request.basis = *f.owner.current_basis(); request.incarnation = 9;
            const auto head = f.owner.begin_revocation(request);
            const auto prepared = f.owner.supply_projection(head.ticket, f.live);
            NativeResult result; result.outcome = Outcome::applied; result.continuity = Continuity::replaced;
            result.availability = availability; result.observation_revision = 7;
            result.readback_identity = f.live.identity; ++result.readback_identity.context; result.readback_attested = true;
            result.retired = f.live.retire; result.retire = NativeRetireMaterial{43, 2, result.readback_identity.context, 0};
            const auto completed = f.owner.complete(prepared.ticket, result);
            check(completed.admission == Admission::completed && !completed.receipt && !f.owner.current_basis() &&
                  !f.owner.current_projection() && !f.owner.current_composition() && f.owner.state() == State::suspended &&
                  !f.owner.terminal() && *f.owner.last_revocation() == request && !f.owner.last_receipt() &&
                  f.owner.complete(prepared.ticket, result).admission == Admission::rejected,
                  "Actual provider retirement proof invented editable projection or observation receipt");
            check(bool(f.owner.activate(initial())), "Checked provider closure did not release native lifecycle");
        }
    });
    run("Unknown or mismatched provider retirement proof never closes ownership", [] {
        for (unsigned variant = 0; variant < 16; ++variant) {
            AsyncFixture f; f.live.retire = NativeRetireMaterial{42, f.live.mapping_id, f.live.identity.context, 0};
            check(bool(f.owner.activate(f.live)), "Provider authority fixture did not activate");
            Revocation request; request.basis = *f.owner.current_basis(); request.incarnation = 9;
            const auto head = f.owner.begin_revocation(request);
            check(f.owner.supply_projection(head.ticket, f.live).revocation.has_value(), "Revocation preparation failed");
            NativeResult result; result.outcome = Outcome::applied; result.continuity = Continuity::replaced;
            result.availability = NativeAvailability::unavailable; result.observation_revision = 7;
            result.readback_identity = f.live.identity; result.readback_attested = true; result.retired = f.live.retire;
            if (variant == 0) result.retired.reset();
            if (variant == 1) ++result.retired->token;
            if (variant == 2) ++result.retired->mapping_id;
            if (variant == 3) ++result.retired->input_context;
            if (variant == 4) ++result.retired->composition;
            if (variant == 5) result.readback_attested = false;
            if (variant == 6) result.observation_revision = 0;
            if (variant == 7) result.readback_identity.owner.id = "foreign";
            if (variant == 8) ++result.readback_identity.generation;
            if (variant == 9) ++result.readback_identity.epoch;
            if (variant == 10) result.outcome = Outcome::cancelled;
            if (variant == 11) result.availability = NativeAvailability::available;
            if (variant == 12) result.continuity = Continuity::same;
            if (variant == 13) result.composition = CompositionFact{77, CompositionState::live};
            if (variant == 14) result.allow_default = true;
            if (variant == 15) result.projection = f.live;
            check(f.owner.complete(head.ticket, result).admission == Admission::terminal && f.owner.terminal() &&
                  f.owner.last_revocation() && *f.owner.last_revocation() == request && !f.owner.last_receipt() &&
                  !f.owner.current_basis() && !f.owner.activate(f.live), "Invalid retirement proof forged native closure");
        }
    });
    run("Editor effects cannot claim provider cleanup without an owned revoke", [] {
        AsyncFixture f; const auto prepared = f.prepare(f.packet()); auto result = f.applied();
        result.retired = NativeRetireMaterial{42, f.live.mapping_id, f.live.identity.context, 0};
        check(f.owner.complete(prepared.ticket, result).admission == Admission::terminal && f.owner.last_receipt() &&
              f.owner.last_receipt()->outcome == Outcome::unknown, "Observation manufactured provider cleanup proof");
    });
    run("Known retirement can attest the requested composition begin ended", [] {
        for (bool forged : {false, true}) {
            AsyncFixture f; const auto prepared = f.prepare(f.packet(composition_observation(CompositionOperation::begin)));
            NativeResult result; result.outcome = Outcome::cancelled; result.continuity = Continuity::replaced;
            result.availability = NativeAvailability::unavailable; result.observation_revision = 7;
            result.readback_identity = f.live.identity; result.readback_attested = true;
            result.composition = CompositionFact{forged ? 78u : 77u, CompositionState::ended};
            result.composition_readback_attested = true;
            const auto completed = f.owner.complete(prepared.ticket, result);
            check(completed.admission == (forged ? Admission::terminal : Admission::completed),
                  "Retirement lost requested composition correlation");
            if (!forged) check(completed.receipt && !completed.receipt->basis && !completed.receipt->composition &&
                               completed.receipt->retirement && !f.owner.current_composition(),
                               "Known ended composition invented a continued native basis");
        }
    });
    run("Native key retarget transfers exact old provider ownership to a new token", [] {
        for (const auto continuity : {Continuity::key_retarget, Continuity::replaced}) {
            AsyncFixture f; f.live.retire = NativeRetireMaterial{42, 1, f.live.identity.context, 0};
            check(bool(f.owner.activate(f.live)), "Provider fixture activation failed");
            const auto prepared = f.prepare(f.packet(key_observation())); auto result = f.applied();
            result.continuity = continuity; result.key_dispatch_attested = result.key_retarget_attested = true;
            result.allow_default = true; result.retired = f.live.retire;
            ++result.projection->mapping_id; ++result.projection->identity.context;
            result.projection->retire = NativeRetireMaterial{43, result.projection->mapping_id,
                result.projection->identity.context, 0};
            result.retire = result.projection->retire;
            const auto completed = f.owner.complete(prepared.ticket, result);
            check(completed.admission == Admission::completed && completed.receipt && completed.receipt->basis &&
                  !completed.receipt->retirement && f.owner.current_projection()->retire == result.retire &&
                  (continuity == Continuity::key_retarget ? completed.receipt->default_token.has_value() :
                      !completed.receipt->default_token.has_value()), "Checked native ownership transfer lost actual successor");
        }
    });
    run("Forged or missing native ownership transfer proof is terminal", [] {
        for (unsigned variant = 0; variant < 12; ++variant) {
            AsyncFixture f; f.live.retire = NativeRetireMaterial{42, 1, f.live.identity.context, 0};
            check(bool(f.owner.activate(f.live)), "Provider fixture activation failed");
            const auto prepared = f.prepare(f.packet(key_observation())); auto result = f.applied();
            result.continuity = Continuity::key_retarget; result.key_dispatch_attested = result.key_retarget_attested = true;
            result.retired = f.live.retire; ++result.projection->mapping_id;
            result.projection->retire = NativeRetireMaterial{43, result.projection->mapping_id, f.live.identity.context, 0};
            if (variant == 0) ++result.retired->token;
            if (variant == 1) ++result.retired->mapping_id;
            if (variant == 2) ++result.retired->input_context;
            if (variant == 3) ++result.retired->composition;
            if (variant == 4) result.projection->retire->token = 42;
            if (variant == 5) result.projection->retire.reset();
            if (variant == 6) ++result.projection->retire->input_context;
            if (variant == 7) result.continuity = Continuity::same;
            if (variant == 8) result.availability = NativeAvailability::unavailable;
            if (variant == 9) result.projection.reset();
            if (variant == 10) result.retired.reset();
            if (variant == 11) { result.retired.reset(); result.projection->retire.reset(); }
            check(f.owner.complete(prepared.ticket, result).admission == Admission::terminal && f.owner.terminal() &&
                  !f.owner.current_basis(), "Unproven provider ownership transfer escaped as a known result");
        }
    });
    run("Same provider token may refresh actual mapping revision and native composition", [] {
        AsyncFixture f; f.live.retire = NativeRetireMaterial{42, 1, f.live.identity.context, 0};
        check(bool(f.owner.activate(f.live)), "Provider fixture activation failed");
        const auto prepared = f.prepare(f.packet(composition_observation(CompositionOperation::begin)));
        auto result = f.applied(); ++result.projection->mapping_id; ++result.projection->editor_revision;
        result.projection->composition = 77;
        result.projection->retire = NativeRetireMaterial{42, result.projection->mapping_id, f.live.identity.context, 77};
        result.composition = CompositionFact{77, CompositionState::live}; result.composition_readback_attested = true;
        const auto completed = f.owner.complete(prepared.ticket, result);
        check(completed.admission == Admission::completed && f.owner.current_projection()->retire == result.projection->retire &&
              f.owner.current_composition()->transaction == 77 && !result.retired,
              "Same-owner native metadata refresh was mistaken for retirement transfer");
    });
    run("Projected native revocation cannot drop provider ownership without exact proof", [] {
        for (unsigned variant = 0; variant < 5; ++variant) {
            AsyncFixture f; f.live.retire = NativeRetireMaterial{42, 1, f.live.identity.context, 0};
            check(bool(f.owner.activate(f.live)), "Provider fixture activation failed");
            Revocation request; request.basis = *f.owner.current_basis(); request.incarnation = 9;
            const auto head = f.owner.begin_revocation(request);
            check(f.owner.supply_projection(head.ticket, f.live).revocation.has_value(), "Revocation did not prepare");
            auto result = f.applied(); result.composition_readback_attested = true;
            if (variant == 0) result.projection->retire.reset();
            if (variant == 1 || variant == 3) result.projection->retire->token = 43;
            if (variant == 2) { result.retired = f.live.retire; ++result.retired->token; }
            if (variant == 3 || variant == 4) result.retired = f.live.retire;
            const auto completed = f.owner.complete(head.ticket, result);
            check(completed.admission == (variant == 3 ? Admission::completed : Admission::terminal) &&
                  !completed.receipt && f.owner.last_revocation() && *f.owner.last_revocation() == request,
                  "Projected cleanup accepted missing or forged provider retirement proof");
        }
    });
    run("Projectionless observation accepts only exact actual provider closure proof", [] {
        for (unsigned variant = 0; variant < 3; ++variant) {
            AsyncFixture f; f.live.retire = NativeRetireMaterial{42, 1, f.live.identity.context, 0};
            check(bool(f.owner.activate(f.live)), "Provider fixture activation failed");
            const auto prepared = f.prepare(f.packet());
            NativeResult result; result.outcome = Outcome::cancelled; result.continuity = Continuity::replaced;
            result.availability = NativeAvailability::unavailable; result.observation_revision = 7;
            result.readback_identity = f.live.identity; result.readback_attested = true; result.retired = f.live.retire;
            if (variant == 1) ++result.retired->token;
            if (variant == 2) result.retire = NativeRetireMaterial{43, 2, f.live.identity.context, 0};
            const auto completed = f.owner.complete(prepared.ticket, result);
            check(completed.admission == (variant == 0 ? Admission::completed : Admission::terminal),
                  "Natural native closure accepted forged proof or rejected exact provider closure");
            if (variant == 0) check(completed.receipt && !completed.receipt->basis && completed.receipt->retirement &&
                                   !f.owner.current_projection() && !f.owner.current_composition() && !f.owner.terminal(),
                                   "Actual native lifecycle closure fabricated an editable successor");
        }
    });
    run("External actual retirement clears owned held defaults and pending or live composition", [] {
        for (bool live : {false, true}) {
            AsyncFixture f; f.live.retire = NativeRetireMaterial{42, 1, f.live.identity.context, 0};
            check(bool(f.owner.activate(f.live)), "Provider fixture did not activate");
            auto prepared = f.prepare(f.packet(key_observation())); auto result = f.applied();
            result.key_dispatch_attested = result.allow_default = true;
            check(f.owner.complete(prepared.ticket, result).receipt->default_token.has_value(), "Default fixture did not grant");
            const auto packet = f.packet(composition_observation(CompositionOperation::begin)); prepared = f.prepare(packet);
            result = f.applied(); result.composition = CompositionFact{77, live ? CompositionState::live : CompositionState::pending};
            result.composition_readback_attested = true;
            if (live) { result.projection->composition = 77; result.projection->retire->composition = 77; }
            const auto completed = f.owner.complete(prepared.ticket, result);
            const auto owned = *f.owner.current_projection(); const auto expected = *owned.retire;
            check(completed.admission == Admission::completed && f.owner.default_groups() == 1 && f.owner.current_composition(),
                  "Native lifecycle fixture did not retain owned facts");
            auto checked = retirement_proof(owned); checked.composition = CompositionFact{77, CompositionState::ended};
            checked.composition_readback_attested = true;
            check(f.owner.complete_external_retirement(expected, checked) && !f.owner.current_basis() &&
                  !f.owner.current_projection() && !f.owner.current_composition() && f.owner.default_groups() == 0 &&
                  f.owner.state() == State::suspended && !f.owner.terminal() && *f.owner.last_receipt() == *completed.receipt &&
                  *f.owner.unresolved() == packet, "Actual external retirement lost original outcome or retained native authority");
            const auto* proof = f.owner.external_retirement();
            check(proof && *proof == RetirementReadback{checked.availability, checked.readback_identity, 99, true, true},
                  "External retirement did not expose its exact actual checked proof");
            check(!f.owner.complete_external_retirement(expected, checked), "External retirement replayed");
            auto fresh = initial(); check(!f.owner.activate(fresh), "Unowned projection reactivated after actual retirement");
            fresh.retire = NativeRetireMaterial{42, fresh.mapping_id, fresh.identity.context, 0};
            check(!f.owner.activate(fresh), "Retired provider token was rearmed");
            fresh.retire->token = 43; check(bool(f.owner.activate(fresh)), "New actual provider token could not reactivate");
            f.live = fresh; auto next = f.packet(key_observation()); next.observation.predecessor.reset();
            prepared = f.prepare(next);
            check(f.owner.complete(prepared.ticket, f.applied()).admission == Admission::completed,
                  "External retirement retained a phantom physical key press");
        }
    });
    run("External malformed or unknown retirement proof never destructively clears owner facts", [] {
        for (unsigned variant = 0; variant < 26; ++variant) {
            Fixture f; f.native.live.retire = NativeRetireMaterial{42, 1, f.native.live.identity.context, 0};
            check(bool(f.owner.activate(f.native.live)), "Provider fixture did not activate"); f.grant();
            const auto basis = *f.owner.current_basis(); const auto owned = *f.owner.current_projection();
            const auto receipt = *f.owner.last_receipt(); const auto packet = *f.owner.unresolved();
            auto expected = *owned.retire; auto checked = retirement_proof(owned);
            if (variant == 0) ++expected.token;
            if (variant == 1) ++expected.mapping_id;
            if (variant == 2) ++expected.input_context;
            if (variant == 3) ++expected.composition;
            if (variant == 4) checked.outcome = Outcome::unknown;
            if (variant == 5) checked.outcome = Outcome::cancelled;
            if (variant == 6) checked.outcome = Outcome::rejected;
            if (variant == 7) checked.retired.reset();
            if (variant == 8) ++checked.retired->token;
            if (variant == 9) checked.readback_attested = false;
            if (variant == 10) checked.observation_revision = 0;
            if (variant == 11) checked.readback_identity.owner.id = "foreign";
            if (variant == 12) ++checked.readback_identity.owner.generation;
            if (variant == 13) ++checked.readback_identity.generation;
            if (variant == 14) ++checked.readback_identity.epoch;
            if (variant == 15) checked.readback_identity.context = 0;
            if (variant == 16) checked.continuity = Continuity::key_retarget;
            if (variant == 17) checked.allow_default = true;
            if (variant == 18) checked.composition = CompositionFact{77, CompositionState::live};
            if (variant == 19) checked.availability = NativeAvailability::available;
            if (variant == 20) checked.availability = static_cast<NativeAvailability>(99);
            if (variant == 21) checked.projection = owned;
            if (variant == 22) { checked.continuity = Continuity::same; ++checked.readback_identity.context; }
            if (variant == 23) checked.retire = owned.retire;
            if (variant == 24) checked.retire = NativeRetireMaterial{43, 2, owned.identity.context + 1, 0};
            if (variant == 25) {
                checked.availability = NativeAvailability::available; checked.projection = owned;
                checked.projection->retire->token = 43; ++checked.projection->identity.context;
            }
            const auto projects = f.native.projects, effects = f.native.effects, revokes = f.native.revocations;
            check(!f.owner.complete_external_retirement(expected, checked) && f.owner.current_basis() &&
                  *f.owner.current_basis() == basis && *f.owner.current_projection() == owned &&
                  *f.owner.last_receipt() == receipt && *f.owner.unresolved() == packet && f.owner.default_groups() == 1 &&
                  !f.owner.external_retirement() && !f.owner.terminal() && f.native.projects == projects &&
                  f.native.effects == effects && f.native.revocations == revokes,
                  "Invalid external proof mutated state, consumed evidence or entered a native callback");
            check(f.owner.complete_external_retirement(*owned.retire, retirement_proof(owned)),
                  "Invalid external proof consumed the still-owned retirement anchor");
        }
    });
    run("External retirement resolves an exact retained projectionless observation obligation", [] {
        AsyncFixture f; f.live.retire = NativeRetireMaterial{42, 1, f.live.identity.context, 0};
        check(bool(f.owner.activate(f.live)), "Provider fixture did not activate");
        const auto owned = *f.owner.current_projection(); const auto prepared = f.prepare(f.packet());
        auto result = retirement_proof(owned); result.outcome = Outcome::cancelled; result.retired.reset();
        const auto completed = f.owner.complete(prepared.ticket, result);
        check(completed.admission == Admission::completed && completed.receipt && completed.receipt->retirement &&
              !completed.receipt->retirement->authority_retired && !f.owner.current_projection() &&
              !f.owner.external_retirement(), "Ordinary native retirement falsely attested provider cleanup");
        auto fresh = initial(); fresh.retire = NativeRetireMaterial{43, 1, fresh.identity.context, 0};
        check(!f.owner.activate(fresh), "Pending external retirement admitted a new editor context");
        auto wrong = *owned.retire; ++wrong.mapping_id;
        check(!f.owner.complete_external_retirement(wrong, retirement_proof(owned)) && !f.owner.activate(fresh),
              "Foreign material erased the retained obligation");
        check(f.owner.complete_external_retirement(*owned.retire, retirement_proof(owned)) &&
              f.owner.external_retirement()->authority_retired && *f.owner.last_receipt() == *completed.receipt &&
              !f.owner.last_receipt()->retirement->authority_retired && bool(f.owner.activate(fresh)),
              "Checked external cleanup could not settle retained obligation without rewriting original receipt");
    });
    run("External retirement cannot disturb active or terminal observation phases", [] {
        for (bool effect : {false, true}) {
            AsyncFixture f; f.live.retire = NativeRetireMaterial{42, 1, f.live.identity.context, 0};
            check(bool(f.owner.activate(f.live)), "Provider fixture did not activate");
            const auto owned = *f.owner.current_projection(); const auto packet = f.packet(); const auto head = f.owner.begin(packet);
            if (effect) check(f.owner.supply_projection(head.ticket, f.live).request.has_value(), "Effect preparation failed");
            check(!f.owner.complete_external_retirement(*owned.retire, retirement_proof(owned)) &&
                  *f.owner.unresolved() == packet && f.owner.processing() && !f.owner.external_retirement(),
                  "External cleanup interrupted an active observation");
            if (!effect) check(f.owner.supply_projection(head.ticket, f.live).request.has_value(), "Projection did not survive rejected cleanup");
            const auto completed = f.owner.complete(head.ticket, f.applied());
            check(completed.admission == Admission::completed, "Rejected external cleanup damaged active completion");
            f.owner.notify_publication_failure();
            check(!f.owner.complete_external_retirement(*owned.retire, retirement_proof(owned)) && f.owner.terminal() &&
                  *f.owner.last_receipt() == *completed.receipt && !f.owner.external_retirement(),
                  "External cleanup revived a terminal owner or rewrote known outcome");
        }
    });
    run("External available readback attests retirement without admitting renewed input", [] {
        AsyncFixture f; f.live.retire = NativeRetireMaterial{42, 1, f.live.identity.context, 0};
        check(bool(f.owner.activate(f.live)), "Provider fixture did not activate");
        const auto owned = *f.owner.current_projection(); auto checked = retirement_proof(owned);
        checked.availability = NativeAvailability::available; checked.projection = owned;
        check(!f.owner.complete_external_retirement(*owned.retire, checked) && f.owner.current_basis(),
              "External cleanup rearmed the retired provider token");
        checked.projection->retire->token = 43;
        check(f.owner.complete_external_retirement(*owned.retire, checked) && !f.owner.current_basis() &&
              !f.owner.current_projection() && f.owner.state() == State::suspended &&
              f.owner.external_retirement()->availability == NativeAvailability::available &&
              f.owner.external_retirement()->authority_retired && !f.owner.last_receipt(),
              "Checked available retirement synthesized an input basis or observation receipt");
        check(bool(f.owner.activate(*checked.projection)), "Explicit fresh provider projection could not activate after cleanup");
    });
    run("Retained external composition cleanup joins the original transport transaction", [] {
        AsyncFixture f; f.live.retire = NativeRetireMaterial{42, 1, f.live.identity.context, 0};
        check(bool(f.owner.activate(f.live)), "Provider fixture did not activate");
        auto prepared = f.prepare(f.packet(composition_observation(CompositionOperation::begin)));
        auto result = f.applied(); result.composition = CompositionFact{77, CompositionState::pending};
        result.composition_readback_attested = true;
        check(f.owner.complete(prepared.ticket, result).admission == Admission::completed, "Pending composition failed");
        const auto owned = *f.owner.current_projection();
        prepared = f.prepare(f.packet(composition_observation(CompositionOperation::update)));
        result = retirement_proof(owned); result.outcome = Outcome::cancelled; result.retired.reset();
        const auto completed = f.owner.complete(prepared.ticket, result);
        check(completed.admission == Admission::completed && !f.owner.current_composition(), "Known unavailable composition did not suspend");
        auto checked = retirement_proof(owned); checked.composition_readback_attested = true;
        checked.composition = CompositionFact{78, CompositionState::ended};
        check(!f.owner.complete_external_retirement(*owned.retire, checked) && *f.owner.last_receipt() == *completed.receipt,
              "Foreign transport transaction consumed retained composition obligation");
        checked.composition->transaction = 77;
        check(f.owner.complete_external_retirement(*owned.retire, checked) && f.owner.external_retirement()->authority_retired &&
              *f.owner.last_receipt() == *completed.receipt, "Original pending transport transaction could not close from actual readback");
    });
    run("Checked unentered cancellation retains actual native lifecycle until owned cleanup", [] {
        for (bool prepared_effect : {false, true}) {
            AsyncFixture f; f.live.retire = NativeRetireMaterial{42, 1, f.live.identity.context, 0};
            check(bool(f.owner.activate(f.live)), "Provider fixture did not activate");
            auto prepared = f.prepare(f.packet(key_observation())); auto result = f.applied();
            result.key_dispatch_attested = result.allow_default = true;
            check(f.owner.complete(prepared.ticket, result).receipt->default_token.has_value(), "Default fixture did not grant");
            prepared = f.prepare(f.packet(composition_observation(CompositionOperation::begin)));
            result = f.applied(); result.composition = CompositionFact{77, CompositionState::pending};
            result.composition_readback_attested = true;
            check(f.owner.complete(prepared.ticket, result).admission == Admission::completed, "Composition fixture failed");
            const auto owned = *f.owner.current_projection(); auto up = key_observation(2);
            std::get<KeyData>(up.data).transition.phase = KeyPhase::up; up.group_end = true;
            const auto packet = f.packet(up); const auto head = f.owner.begin(packet);
            if (prepared_effect) check(f.owner.supply_projection(head.ticket, f.live).request.has_value(), "Keyup did not prepare");
            // The trusted fixture supplies the real not-entered precondition;
            // Controller alone cannot inspect an external transport's entry.
            const auto cancelled = f.owner.cancel_unentered(head.ticket);
            check(cancelled.admission == Admission::completed && cancelled.receipt &&
                  cancelled.receipt->outcome == Outcome::cancelled && cancelled.receipt->id == packet.observation.id &&
                  cancelled.receipt->submitted_token == packet.basis.token && !cancelled.receipt->basis &&
                  cancelled.receipt->continuity == Continuity::replaced && !cancelled.receipt->retirement &&
                  !cancelled.receipt->default_token && !cancelled.receipt->composition && !f.owner.processing() &&
                  !f.owner.current_basis() && *f.owner.current_projection() == owned &&
                  f.owner.current_composition()->transaction == 77 && f.owner.default_groups() == 0 &&
                  *f.owner.unresolved() == packet && !f.owner.external_retirement(),
                  "Known unentered cancellation invented cleanup or lost owned native evidence");
            auto fresh = initial(); fresh.retire = NativeRetireMaterial{43, 1, fresh.identity.context, 0};
            check(!f.owner.activate(fresh), "Unentered cancellation bypassed outstanding native cleanup");
            auto checked = retirement_proof(owned); checked.composition = CompositionFact{77, CompositionState::ended};
            checked.composition_readback_attested = true;
            check(f.owner.complete_external_retirement(*owned.retire, checked) &&
                  *f.owner.last_receipt() == *cancelled.receipt && bool(f.owner.activate(fresh)),
                  "Actual owned cleanup did not settle known unentered cancellation");
            f.live = fresh; auto press = f.packet(key_observation()); press.observation.predecessor.reset();
            prepared = f.prepare(press);
            check(f.owner.complete(prepared.ticket, f.applied()).admission == Admission::completed,
                  "Known unentered keyup fabricated native release or retained phantom press after actual cleanup");
        }
    });
    run("Unentered cancellation rejects wrong duplicate and stale tickets without disturbing a later head", [] {
        AsyncFixture f; f.live.retire = NativeRetireMaterial{42, 1, f.live.identity.context, 0};
        check(bool(f.owner.activate(f.live)), "Provider fixture did not activate");
        const auto owned = *f.owner.current_projection(); const auto packet = f.packet(); const auto head = f.owner.begin(packet);
        check(f.owner.cancel_unentered(0).admission == Admission::rejected &&
              f.owner.cancel_unentered(head.ticket + 1).admission == Admission::rejected && f.owner.awaiting_projection() &&
              *f.owner.unresolved() == packet && *f.owner.current_projection() == owned,
              "Foreign cancellation consumed an active head");
        const auto cancelled = f.owner.cancel_unentered(head.ticket);
        check(cancelled.admission == Admission::completed &&
              f.owner.cancel_unentered(head.ticket).admission == Admission::rejected &&
              f.owner.supply_projection(head.ticket, f.live).admission == Admission::rejected &&
              *f.owner.last_receipt() == *cancelled.receipt, "Cancelled head replayed or lost canonical receipt");
        check(f.owner.complete_external_retirement(*owned.retire, retirement_proof(owned)), "Owned cleanup failed");
        f.live.retire->token = 43; check(bool(f.owner.activate(f.live)) && !f.owner.external_retirement(), "Fresh activation retained a stale proof getter");
        auto fresh = f.packet(); fresh.observation.predecessor.reset(); const auto later = f.owner.begin(fresh);
        check(later.ticket > head.ticket && f.owner.cancel_unentered(head.ticket).admission == Admission::rejected &&
              f.owner.awaiting_projection() && *f.owner.unresolved() == fresh, "Late cancellation damaged a later head");
        check(f.owner.supply_projection(later.ticket, f.live).request.has_value() &&
              f.owner.complete(later.ticket, f.applied()).admission == Admission::completed,
              "Later head could not finish after rejected stale cancellation");
    });
    run("Known unentered revocation retains cleanup material without an observation receipt", [] {
        for (bool prepared_effect : {false, true}) {
            AsyncFixture f; f.live.retire = NativeRetireMaterial{42, 1, f.live.identity.context, 0};
            check(bool(f.owner.activate(f.live)), "Provider fixture did not activate");
            const auto owned = *f.owner.current_projection(); Revocation revoke;
            revoke.basis = *f.owner.current_basis(); revoke.incarnation = 9;
            const auto head = f.owner.begin_revocation(revoke);
            if (prepared_effect) check(f.owner.supply_projection(head.ticket, f.live).revocation.has_value(), "Revocation did not prepare");
            const auto cancelled = f.owner.cancel_unentered(head.ticket);
            check(cancelled.admission == Admission::completed && !cancelled.receipt && !f.owner.last_receipt() &&
                  *f.owner.last_revocation() == revoke && *f.owner.current_projection() == owned &&
                  !f.owner.current_basis() && !f.owner.terminal() && !f.owner.external_retirement(),
                  "Known unentered revoke invented an observation outcome or provider closure");
            check(f.owner.complete_external_retirement(*owned.retire, retirement_proof(owned)) &&
                  f.owner.external_retirement()->authority_retired && !f.owner.last_receipt(),
                  "Exact later actual cleanup could not settle unentered revocation");
        }
    });
    run("Known applied null readback closes only exact old provider authority", [] {
        for (const auto availability : {NativeAvailability::noneditable, NativeAvailability::unavailable})
        for (unsigned lifecycle = 0; lifecycle < 4; ++lifecycle) {
            AsyncFixture f; f.live.retire = NativeRetireMaterial{42, 1, f.live.identity.context, 0};
            check(bool(f.owner.activate(f.live)), "Provider fixture did not activate");
            auto prepared = f.prepare(f.packet(key_observation())); auto actual = f.applied();
            actual.key_dispatch_attested = actual.allow_default = true;
            check(f.owner.complete(prepared.ticket, actual).receipt->default_token.has_value(), "Default fixture did not grant");
            if (lifecycle >= 2) {
                prepared = f.prepare(f.packet(composition_observation(CompositionOperation::begin)));
                actual = f.applied(); actual.composition = CompositionFact{77,
                    lifecycle == 2 ? CompositionState::pending : CompositionState::live};
                actual.composition_readback_attested = true;
                if (lifecycle == 3) { actual.projection->composition = 77; actual.projection->retire->composition = 77; }
                check(f.owner.complete(prepared.ticket, actual).admission == Admission::completed, "Composition fixture failed");
                f.live = *f.owner.current_projection();
            }
            auto observation = lifecycle == 1 ? composition_observation(CompositionOperation::begin) : text_observation();
            if (lifecycle >= 2) {
                observation = key_observation(); std::get<KeyData>(observation.data).transition.phase = KeyPhase::up;
                observation.group_end = true;
            }
            const auto owned = *f.owner.current_projection(); const auto packet = f.packet(observation); prepared = f.prepare(packet);
            actual = retirement_proof(owned); actual.availability = availability;
            if (lifecycle) { actual.composition = CompositionFact{77, CompositionState::ended}; actual.composition_readback_attested = true; }
            const auto completed = f.owner.complete(prepared.ticket, actual);
            check(completed.admission == Admission::completed && completed.receipt &&
                  completed.receipt->outcome == Outcome::applied && completed.receipt->session == packet.session &&
                  completed.receipt->id == packet.observation.id && completed.receipt->submitted_token == packet.basis.token &&
                  completed.receipt->predecessor == packet.observation.predecessor &&
                  completed.receipt->continuity == Continuity::replaced && !completed.receipt->basis &&
                  !completed.receipt->default_token && completed.receipt->composition == actual.composition &&
                  completed.receipt->retirement == std::optional<RetirementReadback>{{availability, actual.readback_identity, 99, true, true}} &&
                  f.owner.state() == State::suspended && !f.owner.terminal() && !f.owner.processing() &&
                  !f.owner.current_basis() && !f.owner.current_projection() && !f.owner.current_composition() &&
                  !f.owner.default_groups() && *f.owner.last_receipt() == *completed.receipt && *f.owner.unresolved() == packet,
                  "Checked old closure lost applied outcome, actual ended fact or authority retirement");
            check(f.owner.complete(prepared.ticket, actual).admission == Admission::rejected &&
                  f.owner.begin(packet).admission == Admission::unavailable, "Closed old head was replayed");
            auto missing = owned; missing.retire.reset();
            check(!f.owner.activate(owned) && !f.owner.activate(missing), "Retired old token or missing material rearmed authority");
            auto fresh = owned; fresh.composition = 0; ++fresh.retire->token; fresh.retire->composition = 0;
            check(bool(f.owner.activate(fresh)), "Explicit distinct checked provider material could not activate after closure");
            f.live = fresh; auto next = f.packet(key_observation()); next.observation.predecessor.reset();
            prepared = f.prepare(next);
            check(f.owner.complete(prepared.ticket, f.applied()).admission == Admission::completed,
                  "Exact old closure retained a phantom held press or composition in fresh context");
        }
    });
    run("Applied null readback without exact old closure never becomes a known receipt", [] {
        for (unsigned variant = 0; variant < 24; ++variant) {
            AsyncFixture f; f.live.retire = NativeRetireMaterial{42, 1, f.live.identity.context, 0};
            if (variant == 5) f.live.retire.reset();
            check(bool(f.owner.activate(f.live)), "Provider fixture did not activate");
            const auto owned = *f.owner.current_projection(); const auto packet = f.packet(); const auto prepared = f.prepare(packet);
            auto actual = retirement_proof(owned);
            if (variant == 0) actual.retired.reset();
            if (variant == 1) ++actual.retired->token;
            if (variant == 2) ++actual.retired->mapping_id;
            if (variant == 3) ++actual.retired->input_context;
            if (variant == 4) ++actual.retired->composition;
            if (variant == 6) actual.retire = NativeRetireMaterial{43, 2, f.live.identity.context, 0};
            if (variant == 7) actual.projection = owned;
            if (variant == 8) actual.availability = NativeAvailability::available;
            if (variant == 9) actual.availability = static_cast<NativeAvailability>(99);
            if (variant == 10) actual.continuity = Continuity::same;
            if (variant == 11) actual.continuity = Continuity::key_retarget;
            if (variant == 12) actual.readback_attested = false;
            if (variant == 13) actual.observation_revision = 0;
            if (variant == 14) actual.readback_identity.owner.id = "foreign";
            if (variant == 15) ++actual.readback_identity.owner.generation;
            if (variant == 16) ++actual.readback_identity.generation;
            if (variant == 17) ++actual.readback_identity.epoch;
            if (variant == 18) actual.readback_identity.context = 0;
            if (variant == 19) actual.allow_default = true;
            if (variant == 20) actual.composition = CompositionFact{77, CompositionState::ended};
            if (variant == 21) actual.outcome = Outcome::unknown;
            if (variant == 22) actual.outcome = static_cast<Outcome>(99);
            if (variant == 23) actual.readback_identity.presentation_revision = 0;
            const auto completed = f.owner.complete(prepared.ticket, actual);
            check(completed.admission == Admission::terminal && f.owner.terminal() && completed.receipt &&
                  completed.receipt->outcome == Outcome::unknown && !completed.receipt->basis &&
                  !completed.receipt->retirement && *f.owner.unresolved() == packet &&
                  *f.owner.current_projection() == owned && !f.owner.current_basis() &&
                  f.owner.begin(packet).admission == Admission::terminal,
                  "Applied/null or mismatched proof fabricated known closure or discarded retained evidence");
        }
    });
    run("Exact old closure distinguishes actual native composition from logical transactions", [] {
        for (const auto outcome : {Outcome::applied, Outcome::cancelled, Outcome::rejected})
        for (unsigned lifecycle = 0; lifecycle < 3; ++lifecycle)
        for (unsigned variant = 0; variant < 5; ++variant) {
            AsyncFixture f; f.live.retire = NativeRetireMaterial{42, 1, f.live.identity.context, 0};
            check(bool(f.owner.activate(f.live)), "Provider fixture did not activate");
            if (lifecycle) {
                const auto prepared = f.prepare(f.packet(composition_observation(CompositionOperation::begin)));
                auto actual = f.applied(); actual.composition = CompositionFact{77,
                    lifecycle == 1 ? CompositionState::pending : CompositionState::live};
                actual.composition_readback_attested = true;
                if (lifecycle == 2) { actual.projection->composition = 77; actual.projection->retire->composition = 77; }
                check(f.owner.complete(prepared.ticket, actual).admission == Admission::completed, "Composition fixture failed");
                f.live = *f.owner.current_projection();
            }
            const auto owned = *f.owner.current_projection();
            const auto packet = f.packet(composition_observation(lifecycle ? CompositionOperation::update : CompositionOperation::begin));
            const auto prepared = f.prepare(packet); auto actual = retirement_proof(owned); actual.outcome = outcome;
            actual.composition = CompositionFact{77, CompositionState::ended}; actual.composition_readback_attested = true;
            if (variant == 0) actual.composition.reset();
            if (variant == 1) actual.composition_readback_attested = false;
            if (variant == 2) ++actual.composition->transaction;
            if (variant == 3) actual.composition->state = CompositionState::pending;
            if (variant == 4) actual.composition->state = CompositionState::live;
            const auto completed = f.owner.complete(prepared.ticket, actual);
            if (variant == 0 && lifecycle < 2) {
                check(completed.admission == Admission::completed && completed.receipt &&
                      completed.receipt->outcome == outcome && !completed.receipt->composition &&
                      completed.receipt->retirement && completed.receipt->retirement->authority_retired &&
                      !f.owner.current_projection() && !f.owner.current_composition() && !f.owner.terminal(),
                      "Exact native-zero closure invented a composition fact or retained a logical transaction");
                continue;
            }
            check(completed.admission == Admission::terminal && f.owner.terminal() && completed.receipt &&
                  completed.receipt->outcome == Outcome::unknown && !completed.receipt->retirement &&
                  *f.owner.unresolved() == packet && *f.owner.current_projection() == owned &&
                  (lifecycle ? f.owner.current_composition().has_value() : !f.owner.current_composition()),
                  "Unattested or absent composition closure consumed an applied old-authority obligation");
        }
    });
    run("All known exact old closure outcomes publish their actual ended fact", [] {
        for (const auto outcome : {Outcome::applied, Outcome::cancelled, Outcome::rejected}) {
            AsyncFixture f; f.live.composition = 77;
            f.live.retire = NativeRetireMaterial{42, 1, f.live.identity.context, 77};
            check(bool(f.owner.activate(f.live)), "Live provider fixture did not activate");
            const auto owned = *f.owner.current_projection(); const auto packet = f.packet(key_observation());
            const auto prepared = f.prepare(packet); auto actual = retirement_proof(owned); actual.outcome = outcome;
            actual.composition = CompositionFact{77, CompositionState::ended}; actual.composition_readback_attested = true;
            const auto completed = f.owner.complete(prepared.ticket, actual);
            check(completed.admission == Admission::completed && completed.receipt && completed.receipt->outcome == outcome &&
                  completed.receipt->composition == actual.composition && completed.receipt->retirement &&
                  completed.receipt->retirement->authority_retired && !completed.receipt->basis &&
                  !f.owner.current_projection() && !f.owner.current_composition() && !f.owner.activate(owned),
                  "Exact old closure changed known outcome, dropped ended fact or rearmed old provider authority");
        }
    });
    run("Physical key closure of native zero clears pending logical composition without invented ended fact", [] {
        for (const auto outcome : {Outcome::applied, Outcome::cancelled, Outcome::rejected})
        for (const auto availability : {NativeAvailability::noneditable, NativeAvailability::unavailable}) {
            AsyncFixture f; f.live.retire = NativeRetireMaterial{42, 1, f.live.identity.context, 0};
            check(bool(f.owner.activate(f.live)), "Provider fixture did not activate");
            auto prepared = f.prepare(f.packet(composition_observation(CompositionOperation::begin)));
            auto actual = f.applied(); actual.composition = CompositionFact{77, CompositionState::pending};
            actual.composition_readback_attested = true;
            check(f.owner.complete(prepared.ticket, actual).admission == Admission::completed &&
                  f.owner.current_composition()->transaction == 77 && !f.owner.current_projection()->retire->composition,
                  "Pending fixture acquired nonexistent native composition");
            const auto owned = *f.owner.current_projection(); const auto packet = f.packet(key_observation());
            prepared = f.prepare(packet); actual = retirement_proof(owned); actual.outcome = outcome; actual.availability = availability;
            const auto completed = f.owner.complete(prepared.ticket, actual);
            check(completed.admission == Admission::completed && completed.receipt && completed.receipt->outcome == outcome &&
                  completed.receipt->id == packet.observation.id && !completed.receipt->basis && !completed.receipt->composition &&
                  !completed.receipt->default_token && completed.receipt->retirement && completed.receipt->retirement->authority_retired &&
                  completed.receipt->retirement->availability == availability && !f.owner.current_projection() &&
                  !f.owner.current_composition() && !f.owner.current_basis() && !f.owner.default_groups() &&
                  !f.owner.terminal() && !f.owner.activate(owned),
                  "Exact native-zero key closure demanded or fabricated a native-ended fact for pending logical composition");
        }
    });
    std::cout << cases << " native editor owner cases; " << failed << " failed; no engine/browser qualification\n";
    return failed ? 1 : 0;
}
