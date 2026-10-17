// SPDX-License-Identifier: CC0-1.0
#include "host/native_editor_capture.hpp"

#include <atomic>
#include <functional>
#include <iostream>
#include <limits>
#include <map>
#include <stdexcept>
#include <thread>
#include <vector>

namespace {
namespace E=foundation::gui_editor;
namespace S=foundation::gui_surface;
using foundation::host::NativeEditorCapture;
using foundation::host::NativeEditorEndpoint;
using foundation::host::NativeEditorObservation;
using foundation::host::capture_native_editor_text;
std::size_t assertions=0;
void check(bool condition,const char* message) { ++assertions; if (!condition) throw std::runtime_error(message); }
template<class Function> void invalid(Function function) {
    bool rejected=false;
    try { function(); } catch (const std::invalid_argument&) { rejected=true; }
    check(rejected,"Malformed native text was accepted");
}
E::Basis initial(std::string value="ab",S::ByteRange selection={1,1}) {
    return {71,{{"surface",3},8,10,11,12},90,std::move(value),selection,false,0};
}
E::Basis changed(E::Basis value,const E::TextObservation& observed) {
    ++value.token; ++value.editor_revision; ++value.identity.presentation_revision;
    value.surrounding=observed.value; value.selection=observed.selection;
    value.backward=observed.selection_direction==E::Direction::backward;
    return value;
}
NativeEditorObservation insert(const E::TextObservation& before,std::string value,E::Authority authority=E::Authority::range,
                               std::optional<std::uint64_t> group={}) {
    const auto end=before.selection.begin+value.size();
    auto after=capture_native_editor_text(before.value.substr(0,before.selection.begin)+value+before.value.substr(before.selection.end),
        S::ByteRange{end,end},E::Direction::none);
    return {E::Kind::text,authority,group,true,0,before,std::move(after),E::TextData{"insertText",std::move(value),before.selection,{}}};
}
E::KeyData key(S::KeyPhase phase,bool repeat=false) { return {{phase,"x","KeyX",0,0,repeat},false}; }
struct Fixture {
    std::atomic<unsigned> terminal{0};
    unsigned resyncs{0},takes{0};
    bool busy{false},throw_submit{false};
    std::uint64_t ticket{100};
    std::vector<E::Packet> attempts,submitted;
    std::vector<E::Revocation> revoked;
    std::map<std::uint64_t,E::EditorCompletion> completions;
    std::function<void()> during_submit,during_take,during_revoke;
    NativeEditorCapture capture;
    Fixture():capture(endpoint()) {}
    NativeEditorEndpoint endpoint() {
        return {
            [this](E::Packet packet)->std::optional<std::uint64_t> {
                attempts.push_back(packet);
                if (during_submit) during_submit();
                if (throw_submit) throw std::runtime_error("unknown endpoint entry");
                if (busy) return {};
                submitted.push_back(std::move(packet)); return ticket++;
            },
            [this](E::Revocation record)->std::optional<std::uint64_t> {
                revoked.push_back(std::move(record)); if (during_revoke) during_revoke(); return ticket++;
            },
            [this](std::uint64_t value)->std::optional<E::EditorCompletion> {
                ++takes; if (during_take) during_take();
                const auto found=completions.find(value); if (found==completions.end()) return {};
                auto result=std::move(found->second); completions.erase(found); return result;
            },
            [this] { ++resyncs; },
            {&terminal,[](void* value) noexcept { ++*static_cast<std::atomic<unsigned>*>(value); }}
        };
    }
    void activate(E::Basis value=initial()) {
        const auto pair=value.identity;
        check(capture.install({std::move(value),{},{},{}},pair),"Checked initial editor publication was rejected");
        check(capture.state()==E::State::ready && capture.basis() && capture.draft(),"Checked initial publication did not activate capture");
    }
    E::Receipt receipt(E::Basis next,E::Outcome outcome=E::Outcome::applied) {
        const auto& packet=submitted.back();
        return {packet.session,packet.observation.id,packet.basis.token,packet.observation.predecessor,outcome,std::move(next),
            E::Continuity::same,{},{},{}};
    }
    void offer(E::Receipt value,std::uint64_t head_ticket=100) {
        completions[head_ticket]={head_ticket,{E::Admission::completed,std::move(value),{}}};
    }
    void publish(const E::Receipt& value) {
        std::optional<S::Identity> pair=value.basis?std::optional{value.basis->identity}:
            value.retirement?std::optional{value.retirement->identity}:std::nullopt;
        check(capture.install({value.basis,E::Settlement{value.session,value.id,value.submitted_token,value.predecessor},
            value.composition,value.retirement},pair),"Exact checked settlement publication was rejected");
    }
};

void unicode_scalar_join_and_owned_bytes() {
    const std::string value="A\xF0\x9F\x98\x80" "e\xCC\x81Z";
    const auto observed=capture_native_editor_text(value,1,5,E::Direction::backward);
    check(observed.selection==S::ByteRange{1,8} && observed.byte_length==9 && observed.value==value,
        "UTF-16 observation was confused with UTF-8 bytes or graphemes");
    check(capture_native_editor_text(value,S::ByteRange{1,8},E::Direction::backward)==observed,
        "Byte-based frontend observation did not independently join UTF-16 scalar boundaries");
    invalid([&]{(void)capture_native_editor_text(value,2,3,E::Direction::none);});
    invalid([&]{(void)capture_native_editor_text(value,S::ByteRange{2,5},E::Direction::none);});
    invalid([]{(void)capture_native_editor_text(std::string("a\0b",3),0,0,E::Direction::none);});
    invalid([]{(void)capture_native_editor_text("\xC0\x80",0,0,E::Direction::none);});
    invalid([]{(void)capture_native_editor_text("\xED\xA0\x80",0,0,E::Direction::none);});
    invalid([]{(void)capture_native_editor_text("\xF4\x90\x80\x80",0,0,E::Direction::none);});
    invalid([]{(void)capture_native_editor_text("\xE2\x82",0,0,E::Direction::none);});
    invalid([]{(void)capture_native_editor_text("x",0,0,static_cast<E::Direction>(9));});
    invalid([]{(void)capture_native_editor_text(std::string(65537,'x'),0,0,E::Direction::none);});
}
void detached_binding_and_publication_only_authority() {
    invalid([]{ NativeEditorCapture capture({}); });
    Fixture f;
    check(f.capture.state()==E::State::detached && !f.capture.basis() && !f.capture.next_passage(),"Capture minted initial authority");
    const auto before=capture_native_editor_text("ab",1,1,E::Direction::none);
    check(!f.capture.observe(insert(before,"x")) && f.submitted.empty(),"Detached capture admitted raw frontend facts");
    f.activate();
    auto alias=initial().identity; alias.presentation_revision=1000;
    check(f.capture.install({initial(),{},{},{}},alias) && f.capture.basis()->identity.presentation_revision==8,
        "Presentation-only alias manufactured a replacement provider basis revision");
    check(f.capture.next_passage()==1 && f.capture.next_passage()==2 && f.attempts.empty(),
        "Local passage IDs entered the endpoint or failed to increase");
    check(f.capture.install({},{}) && !f.capture.observe(insert(*f.capture.draft(),"x")) && !f.capture.resume(*f.capture.basis()),
        "Missing/pending metadata could be resumed using an old frontend string");
    check(f.capture.install({initial(),{},{},{}},alias),"Unchanged checked publication could not restore pending capture");
    f.capture.pause();
    check(f.capture.install({initial(),{},{},{}},alias) && !f.capture.observe(insert(*f.capture.draft(),"x")) &&
        f.capture.resume(initial()),"An ordinary publication silently released an explicit frontend admission pause");
}
void inert_pause_collects_without_delivery_or_retargeting() {
    Fixture f;f.activate();f.busy=true;
    check(f.capture.observe(insert(*f.capture.draft(),"x"))==1,"initial busy passage failed");f.capture.tick();
    check(f.attempts.size()==1 && f.submitted.empty() && f.capture.unresolved(),"fixture did not retain unaccepted head");
    const auto exact=*f.capture.unresolved();
    check(f.capture.install({},{}) && f.capture.paused(),"pending publication did not pause admission");
    check(f.capture.observe_paused(insert(*f.capture.draft(),"y"))==2 && f.capture.pending()==2,"inert pause lost actual bounded continuation");
    f.capture.tick();check(f.attempts.size()==1 && f.capture.unresolved() && *f.capture.unresolved()==exact,"paused tick entered endpoint or discarded its unaccepted exact head");
    check(f.capture.install({initial(),{},{},{}},initial().identity) && !f.capture.paused(),"unchanged checked Basis did not resume inert pause");
    f.busy=false;f.capture.tick();check(f.submitted.size()==1 && f.submitted.front()==exact,"resumed busy head was rebased or repeated before admission");
    Fixture replaced;replaced.activate();check(replaced.capture.install({},{}),"replacement pause failed");
    check(replaced.capture.observe_paused(insert(*replaced.capture.draft(),"x"))==1,"replacement fixture did not retain continuation");
    auto other=initial();++other.token;++other.editor_revision;other.surrounding="changed";other.selection={0,0};
    check(replaced.capture.install({other,{},{},{}},other.identity) && replaced.capture.state()==E::State::suspended &&
        !replaced.capture.observe_paused(insert(*replaced.capture.draft(),"z")),"different Basis retargeted paused facts");
    replaced.capture.tick();check(replaced.submitted.empty() && replaced.capture.pending_bytes()==0,"changed Basis submitted or retained discarded tail");
    f.capture.retire("actual focus loss");
    check(!f.capture.observe_paused(insert(*f.capture.draft(),"z")),"retirement left paused collector admitted");
}
void ingress_is_pure_and_busy_retry_preserves_exact_head() {
    Fixture f; f.activate(); f.busy=true;
    auto value=insert(*f.capture.draft(),"\xF0\x9F\x98\x80");
    check(f.capture.observe(value)==1 && f.attempts.empty() && f.capture.pending()==1 && f.capture.pending_bytes()<=NativeEditorCapture::max_bytes,
        "Ingress entered native endpoint or failed to own bounded observation");
    value.before.value="changed caller storage";
    f.capture.tick(); f.capture.tick();
    check(f.attempts.size()==2 && f.attempts[0]==f.attempts[1] && f.attempts[0].observation.before.value=="ab" && f.capture.pending()==1,
        "Busy submission retried a different head or borrowed caller bytes");
    f.busy=false; f.capture.tick(); f.capture.tick();
    check(f.submitted.size()==1 && f.attempts.size()==3 && f.capture.unresolved() && f.capture.unresolved()->observation.id==1,
        "Accepted head was replayed or lost before its completion");
}
void completion_waits_for_exact_published_settlement_and_current_pair() {
    Fixture f; f.activate(); const auto observed=insert(*f.capture.draft(),"x");
    check(f.capture.observe(observed)==1,"Valid native text observation was rejected"); f.capture.tick();
    auto result=f.receipt(changed(initial(),*observed.after)); f.offer(result);
    const auto takes=f.takes; f.capture.tick();
    check(f.completions.empty() && f.takes==takes+1 && f.capture.pending()==1 && f.capture.basis()->token==71,
        "Early metadata take exposed an unpublished completion or failed to retain it");
    f.capture.tick();
    check(f.takes==takes+1 && f.capture.pending()==1,"Owned completion was taken twice before its publication joined");
    f.publish(result); f.capture.tick();
    check(f.capture.pending()==0 && !f.capture.unresolved() &&
        *f.capture.basis()==*result.basis && f.capture.draft()->value=="axb" && f.capture.state()==E::State::ready,
        "Exact published settlement failed to release its retained head and actual native basis");
    check(f.submitted.size()==1 && f.terminal==0,"Publication joining replayed native work or signaled terminal failure");
}
void queued_ranges_revalidate_actual_predecessor_not_provisional_draft() {
    for (const bool changed_by_author:{false,true}) {
        Fixture f; f.activate(); auto one=insert(*f.capture.draft(),"x");
        check(f.capture.observe(one)==1,"First local draft failed");
        auto two=insert(*f.capture.draft(),"y"); check(f.capture.observe(two)==2,"Second provisional draft failed");
        f.capture.tick();
        auto next=changed(initial(),*one.after);
        if (changed_by_author) { next.surrounding="author"; next.selection={6,6}; }
        auto result=f.receipt(next); f.offer(result); f.publish(result); f.capture.tick(); f.capture.tick();
        if (changed_by_author) check(f.submitted.size()==1 && f.capture.state()==E::State::suspended && !f.capture.unresolved() && f.capture.pending()<=1,
            "A queued range was rebased onto actual author-mutated native text");
        else check(f.submitted.size()==2 && f.submitted.back().basis==next &&
            f.submitted.back().observation.predecessor==1 && f.submitted.back().observation.before==*one.after,
            "Queued draft lost its causal predecessor or exact checked native basis");
    }
}
void native_default_requires_receipt_token_and_keeps_raw_key_identity() {
    Fixture f; f.activate(); const auto group=f.capture.next_passage(); const auto before=*f.capture.draft();
    NativeEditorObservation down{E::Kind::key,E::Authority::native,group,false,0,before,before,key(S::KeyPhase::down)};
    check(f.capture.observe(down)==1,"Raw native key-down failed");
    auto text=insert(before,"x",E::Authority::default_action,group);
    std::get<E::TextData>(text.data).source_groups={*group};
    check(f.capture.observe(text)==2,"Default text passage failed");
    f.capture.tick(); auto result=f.receipt(initial()); result.default_token=E::DefaultDependency{*group,900};
    f.offer(result); f.publish(result); f.capture.tick(); f.capture.tick();
    check(f.submitted.size()==2 && f.submitted[0].observation.data==E::Data{key(S::KeyPhase::down)} &&
        f.submitted[1].default_token==900 && f.submitted[1].default_dependencies==std::vector<E::DefaultDependency>{{*group,900}},
        "Frontend guessed text from a key or minted native default authorization");
    Fixture missing; missing.activate(); const auto source=missing.capture.next_passage();
    check(missing.capture.observe(insert(*missing.capture.draft(),"x",E::Authority::default_action,source))==1,
        "Explicit default facts were rejected before their predecessor could settle");
    missing.capture.tick();
    check(missing.submitted.empty() && missing.capture.state()==E::State::suspended,
        "A keyboard default without an actual receipt authorization reached submit");
}
void composition_owns_preedit_and_needs_actual_native_continuity() {
    Fixture f; f.activate(); const auto transaction=*f.capture.next_passage();
    const auto root=*f.capture.draft();
    NativeEditorObservation begin{E::Kind::composition,E::Authority::range,{},false,transaction,root,root,
        E::CompositionData{S::CompositionOperation::begin,"",{0,0},root.selection,{}}};
    check(f.capture.observe(begin)==1,"Native composition begin failed");
    const auto preedit=capture_native_editor_text("a\xF0\x9F\x98\x80" "b",S::ByteRange{5,5},E::Direction::none);
    NativeEditorObservation update{E::Kind::composition,E::Authority::composition,{},false,transaction,root,preedit,
        E::CompositionData{S::CompositionOperation::update,"\xF0\x9F\x98\x80",{4,4},{},{}}};
    check(f.capture.observe(update)==2,"Actual scalar preedit update failed");
    NativeEditorObservation commit{E::Kind::composition,E::Authority::composition,{},true,transaction,preedit,preedit,
        E::CompositionData{S::CompositionOperation::commit,"\xF0\x9F\x98\x80",{4,4},{},{}}};
    check(f.capture.observe(commit)==3 && f.submitted.empty(),"Composition commit entered native code from ingress");
    f.capture.tick(); auto begun=f.receipt(initial()); begun.composition=E::CompositionFact{transaction,E::CompositionState::pending};
    f.offer(begun); f.publish(begun); f.capture.tick(); f.capture.tick();
    auto live=f.receipt(changed(initial(),preedit)); live.basis->composition=transaction;
    live.composition=E::CompositionFact{transaction,E::CompositionState::live};
    f.offer(live,101); f.publish(live); f.capture.tick(); f.capture.tick();
    auto ended=f.receipt(changed(*live.basis,preedit)); ended.basis->composition=0;
    ended.composition=E::CompositionFact{transaction,E::CompositionState::ended};
    f.offer(ended,102); f.publish(ended); f.capture.tick();
    check(f.submitted.size()==3 && f.capture.pending()==0 && f.capture.basis()->composition==0 && f.capture.draft()->value==preedit.value && f.terminal==0,
        "Native composition phases were restamped, replayed or released without checked actual continuity");
    Fixture bad; bad.activate(); auto malformed=begin; malformed.after=capture_native_editor_text("wrong",5,5,E::Direction::none);
    check(!bad.capture.observe(malformed) && bad.submitted.empty() && bad.capture.state()==E::State::suspended,
        "A claimed composition passage without actual matching draft readback was accepted");
}
void unknown_and_foreign_completions_are_terminal_without_replay() {
    for (unsigned mode=0;mode<4;++mode) {
        Fixture f; f.activate(); check(f.capture.observe(insert(*f.capture.draft(),"x"))==1,"Unknown fixture admission failed");
        f.capture.tick(); auto result=f.receipt(initial());
        if (mode==0) result.outcome=E::Outcome::unknown;
        if (mode==1) ++result.submitted_token;
        if (mode==2) ++result.id;
        f.offer(result);
        if (mode==3) f.completions[100].result.admission=E::Admission::terminal;
        f.capture.tick(); f.capture.tick();
        check(f.capture.state()==E::State::terminal_unknown && f.terminal==1 && f.submitted.size()==1 && f.capture.unresolved() &&
            f.capture.pending()==1 && !f.capture.install({initial(),{},{},{}},initial().identity),
            "Unknown/foreign completion was retried, discarded, or revived by a new publication");
    }
    Fixture entered; entered.activate(); entered.throw_submit=true;
    check(entered.capture.observe(insert(*entered.capture.draft(),"x"))==1,"Throw fixture admission failed");
    entered.capture.tick(); entered.capture.tick();
    check(entered.capture.state()==E::State::terminal_unknown && entered.attempts.size()==1 && entered.capture.unresolved(),
        "An uncertain submit exception lost the owned head or replayed native entry");
}
void conflicting_tagged_publication_is_terminal_and_aliases_are_explicit() {
    Fixture f; f.activate(); auto observed=insert(*f.capture.draft(),"x");
    check(f.capture.observe(observed)==1,"Conflict fixture admission failed"); f.capture.tick();
    auto actual=f.receipt(changed(initial(),*observed.after)); f.offer(actual);
    auto foreign=actual; foreign.basis->surrounding="other"; foreign.basis->selection={5,5};
    f.publish(foreign); f.capture.tick();
    check(f.capture.state()==E::State::terminal_unknown && f.capture.unresolved() && f.submitted.size()==1,
        "A tagged publication conflicting with actual completion was treated as safe settlement");
    Fixture mismatched; auto pair=initial().identity; ++pair.context;
    check(!mismatched.capture.install({initial(),{},{},{}},pair) && mismatched.terminal==1,
        "A frontend pair with a foreign native context granted an editor basis");
}
void retirement_redacts_ingress_before_receipt_and_keeps_exact_head() {
    Fixture f; f.activate(); check(f.capture.observe(insert(*f.capture.draft(),"x"))==1,"Retirement fixture admission failed");
    f.capture.tick(); auto result=f.receipt(initial()); result.basis.reset(); result.continuity=E::Continuity::replaced;
    result.retirement=E::RetirementReadback{E::NativeAvailability::noneditable,initial().identity,91,true,false};
    f.publish(result);
    check(!f.capture.observe(insert(*f.capture.draft(),"y")) && f.capture.unresolved() && f.capture.state()==E::State::suspended,
        "Checked retirement publication left old frontend editor ingress enabled");
    f.offer(result); f.capture.tick();
    check(!f.capture.basis() && !f.capture.draft() && f.capture.pending()==0 && f.capture.state()==E::State::suspended && f.terminal==0,
        "Actual checked retirement failed to settle its preserved old action head");
}
void retire_and_close_never_enter_endpoint_from_callbacks_or_lose_sent_debt() {
    Fixture f; f.activate(); f.capture.retire("native focus loss");
    check(f.revoked.empty() && f.resyncs==0 && f.capture.state()==E::State::suspended,
        "Frontend retirement synchronously called native owner callbacks");
    f.capture.tick();
    check(f.resyncs==0 && f.revoked.size()==1 && f.revoked[0].basis==initial() && f.revoked[0].reason=="native focus loss" && f.revoked[0].incarnation,
        "Owner tick failed to stage exact bounded native revocation material");
    f.completions[100]={100,{E::Admission::completed,{},{}}}; f.capture.tick();
    const auto takes=f.takes; f.capture.tick();
    check(f.capture.pending()==1 && f.capture.basis() && f.terminal==0 && f.takes==takes,
        "Early revocation metadata was released/repolled before current checked retirement");
    const E::RetirementReadback retired{E::NativeAvailability::unavailable,initial().identity,91,true,true};
    check(f.capture.install({{},{},{},retired},initial().identity),"Revocation retirement publication failed");
    f.capture.tick();
    check(f.capture.pending()==1 && !f.capture.basis() && f.terminal==0,"Known revocation did not retain its deferred fresh discovery");
    f.capture.tick(); check(f.resyncs==1 && f.capture.pending()==0,"Fresh discovery ran before cleanup or was lost after checked retirement");
    Fixture sent; sent.activate(); check(sent.capture.observe(insert(*sent.capture.draft(),"x"))==1,"Close fixture admission failed");
    sent.capture.tick(); const auto retained=*sent.capture.unresolved(); sent.capture.close(); sent.capture.tick();
    check(sent.capture.state()==E::State::closed && sent.capture.unresolved() && *sent.capture.unresolved()==retained && sent.submitted.size()==1,
        "Close replayed or discarded an already submitted editor effect");
}
void bounded_queue_invalid_observations_and_foreign_thread_fail_closed() {
    Fixture f; f.activate(); const auto before=*f.capture.draft();
    NativeEditorObservation selection{E::Kind::selection,E::Authority::range,{},false,0,before,before,E::SelectionData{before.selection,false}};
    for (unsigned i=0;i<64;++i) check(f.capture.observe(selection)==i+1,"Bounded queue rejected a valid causal observation early");
    check(f.capture.pending()==64 && f.capture.pending_bytes()<=1048576 && f.submitted.empty(),"Queue accounting exceeded its bounded ingress budget");
    check(!f.capture.observe(selection) && f.capture.state()==E::State::suspended && f.capture.pending()<=1 && !f.capture.unresolved() && f.submitted.empty(),
        "Observation count exhaustion wrapped or submitted native work from ingress");
    Fixture bytes; bytes.activate(initial(std::string(65536,'x'),{0,0})); const auto large=*bytes.capture.draft();
    auto large_selection=selection; large_selection.before=large; large_selection.after=large;
    std::get<E::SelectionData>(large_selection.data).selection={0,0};
    unsigned accepted=0;
    while (bytes.capture.observe(large_selection)) { ++accepted; check(bytes.capture.pending_bytes()<=1048576,"Retained native capture bytes exceeded 1MiB"); }
    check(accepted>0 && accepted<64 && bytes.capture.state()==E::State::suspended && bytes.submitted.empty(),
        "Retained byte exhaustion did not fail before the count limit");
    Fixture malformed; malformed.activate(); auto bad=insert(*malformed.capture.draft(),"x"); bad.after->selection_start=99;
    check(!malformed.capture.observe(bad) && malformed.capture.state()==E::State::suspended && malformed.submitted.empty(),
        "Independent UTF-16 fields were trusted instead of rechecked");
    Fixture foreign; foreign.activate(); std::thread worker([&]{foreign.capture.pause();}); worker.join();
    check(foreign.capture.state()==E::State::terminal_unknown && foreign.terminal==1 && foreign.submitted.empty(),
        "Foreign thread accessed the capture owner or entered its endpoint");
}
void endpoint_reentry_cannot_pump_or_recapture_and_final_ticket_never_wraps() {
    Fixture f; f.activate(); const auto value=insert(*f.capture.draft(),"x");
    f.during_submit=[&] { f.capture.tick(); check(!f.capture.observe(value),"Endpoint callback reentered raw capture"); };
    check(f.capture.observe(value)==1,"Reentry fixture admission failed"); f.capture.tick();
    check(f.submitted.size()==1 && f.attempts.size()==1,"Endpoint callback recursively pumped another native submit");
    Fixture final; final.activate(); final.ticket=std::numeric_limits<std::uint64_t>::max();
    auto first=insert(*final.capture.draft(),"x"); check(final.capture.observe(first)==1,"Final ticket fixture first admission failed");
    final.capture.tick(); auto done=final.receipt(changed(initial(),*first.after)); final.offer(done,std::numeric_limits<std::uint64_t>::max());
    final.publish(done); final.capture.tick();
    check(final.capture.observe(insert(*final.capture.draft(),"y"))==2,"Last completed head broke independent frontend observation IDs");
    final.capture.tick();
    check(final.capture.state()==E::State::terminal_unknown && final.submitted.size()==1 && final.capture.unresolved(),
        "Endpoint ticket exhaustion wrapped or called submit after its final identity");
}
void callback_close_keeps_the_returned_ticket_and_owned_completion() {
    for (const bool during_submission:{false,true}) {
        Fixture f; f.activate(); const auto value=insert(*f.capture.draft(),"x");
        check(f.capture.observe(value)==1,"Callback-close fixture ingress failed");
        if (during_submission) f.during_submit=[&]{ f.capture.close(); };
        f.capture.tick();
        if (!during_submission) {
            f.offer(f.receipt(changed(initial(),*value.after)));
            f.during_take=[&]{ f.capture.close(); };
            f.capture.tick();
            check(f.completions.empty(),"Callback Close lost a completion already taken from the endpoint");
        }
        const auto takes=f.takes; f.capture.tick();
        check(f.capture.state()==E::State::closed && f.capture.pending()==1 && f.capture.unresolved() &&
            f.capture.unresolved()->observation.id==1 && f.submitted.size()==1 && f.takes==takes,
            "Callback Close erased/replayed its submitted head or continued endpoint polling");
    }
    Fixture revoke; revoke.activate(); revoke.capture.retire("native capture loss");
    revoke.during_revoke=[&]{ revoke.capture.close(); }; revoke.capture.tick();
    const auto takes=revoke.takes; revoke.capture.tick();
    check(revoke.capture.state()==E::State::closed && revoke.capture.pending()==1 && revoke.revoked.size()==1 && revoke.takes==takes,
        "Callback Close lost a submitted revocation or continued metadata polling");
}
void retained_capacity_and_publication_shapes_are_checked() {
    std::string reserved_text="x"; reserved_text.reserve(2*1048576);
    const auto captured=capture_native_editor_text(std::move(reserved_text),1,1,E::Direction::none);
    check(captured.value.capacity()<=NativeEditorCapture::max_text_bytes,
        "Text conversion retained a caller's unrelated large string reservation");
    Fixture compact; auto value=initial(); value.surrounding.reserve(2*1048576);
    compact.activate(std::move(value));
    check(compact.capture.basis()->surrounding.capacity()<=NativeEditorCapture::max_text_bytes,
        "Capture retained an unrelated large reservation carried by a checked small string");
    auto oversized=insert(*compact.capture.draft(),"x");
    std::get<E::TextData>(oversized.data).text.reserve(2*1048576);
    check(!compact.capture.observe(std::move(oversized)) && compact.capture.pending_bytes()<=1048576 && compact.submitted.empty(),
        "Observation byte accounting ignored owned string capacity");
    Fixture empty_settlement;
    check(!empty_settlement.capture.install({{},E::Settlement{1,1,71,{}},{},{}},initial().identity) && empty_settlement.terminal==1,
        "A head settlement without checked basis/retirement granted publication authority");
    Fixture unowned_end;
    check(!unowned_end.capture.install({{},{},E::CompositionFact{9,E::CompositionState::ended},{}},initial().identity) && unowned_end.terminal==1,
        "An ended composition without checked basis/retirement granted publication authority");
}
void completed_cancelled_keys_preserve_native_cleanup_ownership() {
    for (unsigned mode=0;mode<3;++mode) {
        Fixture f; f.activate(); const auto before=*f.capture.draft();
        NativeEditorObservation down{E::Kind::key,E::Authority::native,{},false,0,before,before,key(S::KeyPhase::down)};
        check(f.capture.observe(down)==1,"Cancelled-key fixture ingress failed"); f.capture.tick();
        auto receipt=f.receipt(initial(),mode==0?E::Outcome::cancelled:E::Outcome::rejected); f.offer(receipt);
        if (mode==2) f.completions[100].result.admission=E::Admission::rejected; // Explicitly never dispatched.
        f.publish(receipt); f.capture.tick();
        check(f.revoked.size()==1 && f.capture.state()==E::State::suspended &&
            (mode==2?f.revoked.front().held_keys.empty():f.revoked.front().held_keys==std::vector<E::KeyData>{key(S::KeyPhase::down)}),
            "Known native key dispatch/default cancellation was confused with pre-entry held-key ownership");
    }
}
} // namespace

int main() {
    const std::pair<const char*,void(*)()> tests[]={
        {"unicode_scalar_join_and_owned_bytes",unicode_scalar_join_and_owned_bytes},
        {"detached_binding_and_publication_only_authority",detached_binding_and_publication_only_authority},
        {"inert_pause_collects_without_delivery_or_retargeting",inert_pause_collects_without_delivery_or_retargeting},
        {"ingress_is_pure_and_busy_retry_preserves_exact_head",ingress_is_pure_and_busy_retry_preserves_exact_head},
        {"completion_waits_for_exact_published_settlement_and_current_pair",completion_waits_for_exact_published_settlement_and_current_pair},
        {"queued_ranges_revalidate_actual_predecessor_not_provisional_draft",queued_ranges_revalidate_actual_predecessor_not_provisional_draft},
        {"native_default_requires_receipt_token_and_keeps_raw_key_identity",native_default_requires_receipt_token_and_keeps_raw_key_identity},
        {"composition_owns_preedit_and_needs_actual_native_continuity",composition_owns_preedit_and_needs_actual_native_continuity},
        {"unknown_and_foreign_completions_are_terminal_without_replay",unknown_and_foreign_completions_are_terminal_without_replay},
        {"conflicting_tagged_publication_is_terminal_and_aliases_are_explicit",conflicting_tagged_publication_is_terminal_and_aliases_are_explicit},
        {"retirement_redacts_ingress_before_receipt_and_keeps_exact_head",retirement_redacts_ingress_before_receipt_and_keeps_exact_head},
        {"retire_and_close_never_enter_endpoint_from_callbacks_or_lose_sent_debt",retire_and_close_never_enter_endpoint_from_callbacks_or_lose_sent_debt},
        {"bounded_queue_invalid_observations_and_foreign_thread_fail_closed",bounded_queue_invalid_observations_and_foreign_thread_fail_closed},
        {"endpoint_reentry_cannot_pump_or_recapture_and_final_ticket_never_wraps",endpoint_reentry_cannot_pump_or_recapture_and_final_ticket_never_wraps},
        {"callback_close_keeps_the_returned_ticket_and_owned_completion",callback_close_keeps_the_returned_ticket_and_owned_completion},
        {"retained_capacity_and_publication_shapes_are_checked",retained_capacity_and_publication_shapes_are_checked},
        {"completed_cancelled_keys_preserve_native_cleanup_ownership",completed_cancelled_keys_preserve_native_cleanup_ownership}
    };
    const char* current="initialization"; std::size_t passed=0;
    try {
        for (const auto& test:tests) { current=test.first; test.second(); ++passed; std::cout<<"PASS "<<current<<'\n'; }
        std::cout<<"Native editor capture pure mock component passed: "<<passed<<" cases, "<<assertions<<" assertions, zero skips\n";
    } catch (const std::exception& error) { std::cerr<<"FAIL "<<current<<": "<<error.what()<<'\n'; return 1; }
}
