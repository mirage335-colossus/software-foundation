// SPDX-License-Identifier: CC0-1.0
#include "appended_document_actions_fixture.hpp"
#include "../gui/shared/appended_engine_input_codec.hpp"

namespace {
using namespace document_actions_fixture;
static_assert(static_cast<unsigned>(EngineDocumentWorkKind::body_action) == 4);
static_assert(static_cast<unsigned>(EngineDocumentWorkKind::body_action_ack) == 5);

void explicit_profile() {
    OwnerFixture f;
    check(f.owner->document_actions_enabled() && f.owner->document_enabled() && f.owner->input_enabled() &&
        !f.owner->document_profile().enabled && f.owner->document_actions_profile() == profile(),
        "explicit4083 profile did not retain independent frozen facts");
    auto legacy = configuration(); legacy.document_actions_profile = {}; legacy.document_profile = legacy_profile();
    OwnerFixture old(legacy);
    check(old.owner->document_enabled() && !old.owner->document_actions_enabled(), "legacy2003 inferred body action admission");
    const auto reserved = old.owner->reserve_document_sequence(); check(bool(reserved), "legacy fixture reservation unavailable");
    check(old.owner->stage_document_work(work(target(old.id), *reserved)).code != EngineDocumentAdmissionCode::admitted &&
        old.owner->cancel_document_sequence(*reserved), "legacy profile admitted operation10 or lost rejected reservation");
    auto both = configuration(); both.document_profile = legacy_profile(); bool rejected = false;
    try { EngineOwner invalid(package(), both); } catch (const std::invalid_argument&) { rejected = true; }
    check(rejected, "two independently enabled profiles were admitted");
    for (unsigned field = 0; field < 6; ++field) {
        auto invalid = configuration(); auto& p = invalid.document_actions_profile;
        if (field == 0) p.provider_capabilities = 2035;
        if (field == 1) p.contract_sha256 = doc::kContractSha256;
        if (field == 2) p.actions_header_sha256[0] ^= 1;
        if (field == 3) p.commands[8].schema_sha256 = doc::kAckSchema;
        if (field == 4) p.commands[7].required_reply_capacity = 65536;
        if (field == 5) p.build_sha256 = {};
        rejected = false;
        try { EngineOwner bad(package(), invalid); } catch (const std::invalid_argument&) { rejected = true; }
        check(rejected, "incomplete or widened old profile acquired body action admission");
    }
}

void owned_body_and_join() {
    OwnerFixture f; auto value = f.next();
    const auto idle = call(*f.owner, 27, f.id);
    check(idle.control == FOUNDATION_ENGINE_EMPTY && idle.service == static_cast<unsigned>(ServiceStatus::unavailable) &&
        !f.owner->reserve_document_sequence(), "held reservation was not a busy barrier");
    for (unsigned field = 0; field < 15; ++field) {
        auto bad = value;
        if (field == 0) bad.operation = 6;
        if (field == 1) bad.schema_sha256 = doc::kSchema;
        if (field == 2) --bad.required_reply_capacity;
        if (field == 3) bad.payload.push_back(0);
        if (field == 4) bad.payload[0] ^= 1;
        if (field == 5) bad.payload[4] = 2;
        if (field == 6) bad.payload[6] = 2;
        if (field == 7) bad.payload[7] = 1;
        if (field == 8) put(bad.payload, 8, 127, 4);
        if (field >= 9 && field <= 13) bad.payload[16 + 8 * (field - 9)] ^= 1;
        if (field == 14) ++bad.target.worker_epoch;
        check(f.owner->stage_document_work(std::move(bad)).code != EngineDocumentAdmissionCode::admitted,
            "body request crossed catalog, canonical header or full target/sequence");
    }
    const auto saved = value; const auto admitted = f.stage(value);
    std::fill(value.payload.begin(), value.payload.end(), 0);
    const auto d = f.peek();
    check(d.work.payload == saved.payload && d.work.target == saved.target && d.work.schema_sha256 == actions::kSchema,
        "body mailbox borrowed caller bytes or changed full target/schema");
    f.claim(d); const auto good = result_bytes(d, completion(d.work));
    check(call(*f.owner, 28, identity(d.work.target), good, d.transfer).control != 0,
        "consumed body action settled without a matching outer TURN");
    f.turn(d);
    for (unsigned field = 0; field < 15; ++field) {
        auto bad = good;
        if (field < 6) bad[40 + 16 + 8 * field] ^= 1;
        if (field == 6) bad[40] = 'N';
        if (field == 7) bad[44] = 2;
        if (field == 8) bad[46] = 1;
        if (field == 9) bad[47] = 1;
        if (field == 10) put(bad, 48, 73, 4);
        if (field == 11) bad[52] = 1;
        if (field == 12) bad.pop_back();
        if (field == 13) put(bad, 0, static_cast<unsigned>(EngineDocumentWorkKind::form_action), 4);
        if (field == 14) put(bad, 32, 1, 8);
        check(call(*f.owner, 28, identity(d.work.target), bad, d.transfer).control != 0 &&
            !f.owner->document_outcome(admitted.ticket), "body completion lost exact DAV1 key/header authority");
    }
    for (unsigned kind : {4u, 5u, 6u, 7u}) {
        const auto invalid = ndv2(d.work.target, d.work.request_sequence, kind, 73, 72);
        check(call(*f.owner, 28, identity(d.work.target), result_bytes(d, invalid), d.transfer).control != 0,
            "body completion acquired an NDV2 packet kind");
    }
    f.settle(d, good); const auto held = f.owner->document_outcome(admitted.ticket);
    check(held && held->kind == EngineDocumentWorkKind::body_action && held->bytes == completion(saved) &&
        held->target == saved.target && held->outcome == EngineDocumentOutcome::consumed &&
        !held->semantic_revision && !held->handled && !f.owner->consume_document_outcome(admitted.ticket),
        "consumed semantic rejection failed to retain exact native body debt");
    f.settle(d, good);
    auto changed = good; changed.back() ^= 1;
    check(call(*f.owner, 28, identity(d.work.target), changed, d.transfer).control != 0 &&
        held == f.owner->document_outcome(admitted.ticket), "changed exact duplicate replaced retained body completion");
    const auto ack = f.ack(saved, true); f.finish_ack(ack, saved, true);
    check(f.owner->consume_document_outcome(ack.ticket) && f.owner->consume_document_outcome(admitted.ticket),
        "checked body ACK did not permit owned result collection");
}

void global_debt_and_cross_family(bool body) {
    OwnerFixture f; const auto original = f.next(body); const auto admission = f.stage(original); f.finish(admission);
    const auto retained = f.owner->document_outcome(admission.ticket);
    check(!f.owner->reserve_document_sequence() && !f.owner->consume_document_outcome(admission.ticket),
        "retained action debt admitted another ordinary reservation");
    for (bool other_body : {false, true}) {
        const auto denied = f.owner->stage_document_work(work(target(f.id), original.request_sequence + 1, other_body));
        check(denied.code == EngineDocumentAdmissionCode::busy && !denied.ticket,
            "global form/body debt admitted a second family action");
    }
    Bytes focus;
    check(engine_input::encode_focus({1, 0, 0, 0, 7, 0}, focus) == engine_input::Status::ok &&
        !f.owner->stage_command(f.id, 7, 3, engine_input::kFocusSchema, focus, true),
        "physical input overtook retained form/body action debt");
    const auto wrong = f.ack(original, !body); const auto wd = f.peek(); f.claim(wd);
    for (unsigned code : {0u, 1u}) {
        check(call(*f.owner, 28, identity(wd.work.target), result_bytes(wd, ack_raw(original.request_sequence, code)), wd.transfer).control != 0 &&
            !f.owner->document_outcome(wrong.ticket) && !f.owner->consume_document_outcome(admission.ticket),
            "cross-family nonstale ACK released another family's action debt");
    }
    f.settle(wd, result_bytes(wd, ack_raw(original.request_sequence, 2)));
    check(f.owner->document_outcome(wrong.ticket)->bytes == ack_raw(original.request_sequence, 2) &&
        f.owner->consume_document_outcome(wrong.ticket) && retained == f.owner->document_outcome(admission.ticket) &&
        !f.owner->consume_document_outcome(admission.ticket) && !f.owner->reserve_document_sequence(),
        "cross-family stale ACK cleared or replaced original native debt");
    const auto correct = f.ack(original, body); f.finish_ack(correct, original, body);
    check(f.owner->consume_document_outcome(correct.ticket) && f.owner->consume_document_outcome(admission.ticket),
        "correct-family ACK after cross-family stale failed to collect");
    const auto next = f.next(!body); check(next.request_sequence > wd.work.request_sequence, "family switch reset global sequence");
    check(f.owner->cancel_document_sequence(next.request_sequence), "post-ACK reservation did not cancel");
}

void old_target(unsigned code) {
    OwnerFixture f; const auto original = f.next(); const auto admission = f.stage(original); f.finish(admission);
    const auto held = f.owner->document_outcome(admission.ticket); const auto old = f.id;
    ++f.id.document_sequence; f.id.service_generation = 0;
    const auto begun = call(*f.owner, 4, f.id); ok(begun); f.id = begun.id;
    check(call(*f.owner, 23, f.id).control != 0, "retired body target became disposable before exact ACK");
    const auto stale = f.ack(original, true); f.finish_ack(stale, original, true, 2);
    check(f.owner->consume_document_outcome(stale.ticket) && !f.owner->consume_document_outcome(admission.ticket),
        "old-target stale2 released retained body debt");
    auto crossed = original; crossed.target = target(f.id);
    const auto foreign = f.ack(crossed, true); f.finish_ack(foreign, crossed, true, 2);
    check(f.owner->consume_document_outcome(foreign.ticket) && !f.owner->consume_document_outcome(admission.ticket),
        "successor-target stale ACK released predecessor's body retirement");
    const auto ack = f.ack(original, true); f.finish_ack(ack, original, true, code);
    check(call(*f.owner, 23, f.id).control != 0, "old target disposed before local result collection");
    check(f.owner->consume_document_outcome(ack.ticket) && f.owner->consume_document_outcome(admission.ticket),
        "checked old-target body ACK0/1 did not release native debt");
    const auto retired = call(*f.owner, 23, f.id); ok(retired);
    check(retired.id == old && retired.transfer && held->bytes == completion(original),
        "old-target disposal lost original authority or mutated owned body bytes");
    ok(call(*f.owner, 2, retired.id, {}, retired.transfer)); ok(call(*f.owner, 3, retired.id, {}, retired.transfer));
    const auto accepted = encode_u32(1); ok(call(*f.owner, 24, retired.id, accepted, retired.transfer));
    check(f.owner->identity() == f.id, "old-target body retirement reset successor identity");
}

void collected_cross_family_proof(bool body) {
    OwnerFixture f; const auto original = f.next(body); const auto admission = f.stage(original); f.finish(admission);
    const auto correct = f.ack(original, body); f.finish_ack(correct, original, body);
    const auto proof = f.owner->document_outcome(correct.ticket); const auto proof_bytes = proof->bytes;
    check(f.owner->consume_document_outcome(correct.ticket) && f.owner->consume_document_outcome(admission.ticket),
        "proof fixture did not collect original successful native debt");
    const auto wrong = f.ack(original, !body); const auto d = f.peek(); f.claim(d);
    for (unsigned code : {0u, 1u}) {
        check(call(*f.owner, 28, identity(d.work.target), result_bytes(d, ack_raw(original.request_sequence, code)), d.transfer).control != 0 &&
            !f.owner->document_outcome(wrong.ticket) && proof == f.owner->document_outcome(correct.ticket) && proof->bytes == proof_bytes,
            "post-collection foreign-family ACK rewrote successful original proof");
    }
    f.settle(d, result_bytes(d, ack_raw(original.request_sequence, 2)));
    check(f.owner->consume_document_outcome(wrong.ticket) && proof == f.owner->document_outcome(correct.ticket) &&
        proof->bytes == ack_raw(original.request_sequence), "post-collection stale2 lost exact original ACK0 tombstone bytes");
    const auto replay = f.ack(original, body);
    check(replay.ticket == correct.ticket && proof == f.owner->document_outcome(replay.ticket),
        "exact original-family proof replay minted another metadata attempt after foreign stale2");
    const auto next = f.next(!body);
    check(next.request_sequence > d.work.request_sequence && f.owner->cancel_document_sequence(next.request_sequence),
        "collected proof/cross-family stale changed ordinary sequence ordering");
}

void headroom() {
    // Leaf allocator/join coverage only; the public Owner has no sequence seed.
    // This is explicitly not a native Driver-at-MAX execution claim.
    doc::SequenceAllocator sequences(UINT64_MAX - 1);
    const auto ordinary = sequences.reserve();
    check(ordinary && *ordinary == UINT64_MAX - 1 && !sequences.issue_ack() && sequences.commit(*ordinary),
        "last ordinary reservation lost metadata ACK headroom/order");
    const EngineDocumentTarget id{17, UINT64_C(0x8000000000000044), UINT64_C(0x8000000000000001), 31};
    for (const auto sequence : {UINT64_C(0x8000000000000001), UINT64_MAX - 1}) {
        const auto w = work(id, sequence);
        check(doc::valid_work_join(w) && get(w.payload, 48, 8) == sequence && doc::valid_reply_join(w, completion(w)),
            "body join truncated a full-u64 ordinary sequence");
    }
    bool exhausted = false;
    try { (void)sequences.reserve(); } catch (const std::overflow_error&) { exhausted = true; }
    check(!doc::valid_work_join(work(id, UINT64_MAX)) && exhausted, "body ordinary admitted ACK-only final sequence");
    const auto final = sequences.issue_ack();
    exhausted = false;
    try { (void)sequences.issue_ack(); } catch (const std::overflow_error&) { exhausted = true; }
    check(final && *final == UINT64_MAX && exhausted, "final metadata ACK headroom was lost/reused");
    EngineDocumentWork ack;
    ack.target = id; ack.kind = EngineDocumentWorkKind::body_action_ack; ack.operation = 11;
    ack.request_sequence = *final; ack.required_reply_capacity = 16; ack.schema_sha256 = actions::kAckSchema;
    ack.payload.resize(8); put(ack.payload, 0, UINT64_MAX - 1, 8);
    check(doc::valid_work_join(ack) && doc::valid_reply_join(ack, ack_raw(UINT64_MAX - 1)),
        "body final ACK join truncated originalMAX-1 or outerMAX");
}
} // namespace

int main() {
    try {
        explicit_profile(); owned_body_and_join(); global_debt_and_cross_family(false); global_debt_and_cross_family(true);
        old_target(0); old_target(1); collected_cross_family_proof(false); collected_cross_family_proof(true); headroom();
        std::cout << "document-actions Owner mock passed (" << assertions << " checks)\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "document-actions Owner mock: " << error.what() << '\n'; return 1;
    }
}
