// SPDX-License-Identifier: CC0-1.0
// Generic endpoint/actual WebAdapter+WebSession fixture; no engine or Controller.
#include "host/browser_surface.hpp"
#include <atomic>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>
namespace {
using namespace foundation;
namespace H=host;
namespace E=gui_editor;
namespace C=host::surface_editor_web;
using Json=host::surface_web::Json;
std::size_t assertions{},groups{};
void check(bool value,const char* reason){++assertions;if(!value)throw std::runtime_error(reason);}
template<class F>void rejects(F action,const char* reason){bool caught=false;try{action();}catch(const std::exception&){caught=true;}check(caught,reason);}
Json parse(std::string_view value){return gui::web_detail::Parser(value).parse();}
Json::Object& object(Json& value){return std::get<Json::Object>(value.value);}
constexpr auto large=UINT64_C(9007199254740993);
gui::Snapshot snapshot(std::uint64_t revision=1){gui::Snapshot s;s.revision=revision;s.client_size={100,100};gui::Widget w;w.spec.key={"surface",1};w.spec.kind=gui::Kind::button;w.state.bounds={0,0,100,100};s.widgets.push_back(w);return s;}
E::Basis basis(std::uint64_t revision=1){return {large,{{"surface",1},revision,7,1,1},large+1,"A😀B",{1,5},false,0};}
gui_surface::Presentation presentation(const E::Basis& b){gui_surface::Presentation p;p.identity=b.identity;p.required=63;p.bounds={0,0,100,100};p.clip=p.bounds;p.keys.fallback=gui_surface::Capture::capture;gui_surface::EditorContext e;e.revision=b.editor_revision;e.surrounding=b.surrounding;e.selection=b.selection;e.selection_backward=b.backward;e.composition_transaction=b.composition;e.editable=true;p.editor=e;return p;}
Json text(){return Json::Object{{"value","A😀B"},{"selectionStart",1},{"selectionEnd",3},{"selectionDirection","forward"},{"selection",Json::Array{1,5}},{"byteLength",6}};}
Json packet(){return Json::Object{{"type","editorObservation"},{"session",std::to_string(large+2)},{"basis",C::json_basis(basis())},{"defaultToken",nullptr},{"defaultDependencies",Json::Array{}},
    {"observation",Json::Object{{"id",std::to_string(large+3)},{"predecessor",nullptr},{"kind","text"},{"authority","range"},{"group",std::to_string(large+4)},{"groupEnd",true},{"transaction","0"},{"before",text()},{"after",nullptr},
    {"data",Json::Object{{"inputType","insertText"},{"text","x"},{"replacement",Json::Array{1,5}}}}}}};}
E::Receipt receipt(E::Basis b=basis()){E::Receipt r;r.session=large+2;r.id=large+3;r.submitted_token=large;r.outcome=E::Outcome::applied;r.basis=std::move(b);return r;}
E::EditorPublication noneditable(){return {{},{},{},E::RetirementReadback{E::NativeAvailability::noneditable,basis().identity,large,true}};}
struct Fixture {
    std::atomic<unsigned> terminals{};
    unsigned submits{},revokes{},takes{},resyncs{},notifications{};
    bool throw_hook{},offer_service{};
    std::optional<E::EditorCompletion> completion;
    H::BrowserSurfaceAdapter adapter;
    H::BrowserSurfaceSession session;
    std::uint64_t wire{};
    std::function<void()> tick;
    H::BrowserEditorEndpoint endpoint(){H::BrowserEditorEndpoint e;
        e.submit=[this](E::Packet p)->std::optional<std::uint64_t>{++submits;check(p==C::parse_packet(packet()),"owned packet lost Unicode/u64 values");if(throw_hook)throw std::runtime_error("endpoint callback failure");return large+10;};
        e.revoke=[this](E::Revocation)->std::optional<std::uint64_t>{++revokes;return large+11;};
        e.take=[this](std::uint64_t)->std::optional<E::EditorCompletion>{++takes;auto result=std::move(completion);completion.reset();return result;};
        e.resync=[this]{++resyncs;};e.terminal={this,[](void* p)noexcept{static_cast<Fixture*>(p)->terminals.fetch_add(1);}};return e;}
    Fixture():adapter(7,{},[this](gui_surface::Revocation){++notifications;},8255,H::surface_web::Profile::editor_v1,endpoint()),
        session(adapter,"epoch",{},{},[this]()->std::optional<gui::ServiceRequest>{if(!std::exchange(offer_service,false))return {};return gui::ServiceRequest{42,gui::ServiceKind::prompt,"Prompt",{},64};},{},[this]{if(tick)tick();}){}
    Json send(Json op){return parse(session.receive(gui::web_detail::encode(Json::Object{{"epoch","epoch"},{"seq",std::to_string(++wire)},{"operation",std::move(op)}})));}
    void connect(){auto r=send(Json::Object{{"type","surfaceConnect"},{"version",2},{"profile","editor_v1"},{"supported","8255"},{"mouseInputVersion",1}});check(r.at("error").str().empty()&&adapter.capabilities().supported==8255,"exact editor negotiation failed");}
    void publish(E::EditorPublication pub={basis(),{},{},{}},std::uint64_t rev=1){auto b=pub.basis.value_or(basis(rev));auto p=presentation(b);check(adapter.present_editor_pair(snapshot(rev),p,std::move(pub),{}).status==gui_surface::Status::ok,"atomic editor pair rejected");}
    void focus(){check(adapter.accept({basis().identity,1,gui_surface::FocusChange{true,true,{}}}).status==gui_surface::Status::ok,"physical focus failed");}
    void ready(){connect();publish();focus();}
};
void codec(){
    auto p=packet();auto decoded=C::parse_packet(p);check(decoded.basis.surrounding=="A😀B"&&decoded.basis.token==large&&decoded.observation.before.selection_end==3,"canonical editor packet changed");
    auto bad=p;object(bad).emplace("extra",true);rejects([&]{C::parse_packet(bad);},"unknown packet field admitted");
    bad=p;object(object(bad).at("basis")).at("token")="01";rejects([&]{C::parse_packet(bad);},"noncanonical u64 admitted");
    bad=p;object(object(object(bad).at("observation")).at("before")).at("selectionEnd")=2;rejects([&]{C::parse_packet(bad);},"UTF16 surrogate interior admitted");
    bad=p;object(object(object(bad).at("observation")).at("data")).at("replacement")=Json::Array{2,5};rejects([&]{C::parse_packet(bad);},"UTF8 replacement interior admitted");
    bad=p;object(bad).at("defaultDependencies")=Json::Array{Json::Object{{"group","1"},{"token","2"}},Json::Object{{"group","1"},{"token","3"}}};rejects([&]{C::parse_packet(bad);},"duplicate dependency group admitted");
    auto b=basis();b.token=std::numeric_limits<std::uint64_t>::max();check(C::parse_basis(C::json_basis(b))==b,"UINT64_MAX lost precision");
    auto r=receipt();r.basis.reset();r.outcome=E::Outcome::cancelled;r.continuity=E::Continuity::replaced;r.retirement=E::RetirementReadback{E::NativeAvailability::noneditable,b.identity,large,true};
    auto encoded=C::json_receipt(r);check(encoded.at("retirement").at("observationRevision").str()==std::to_string(large)&&encoded.at("retirement").at("readbackAttested").boolean(),"checked retirement omitted from receipt");
    r.retirement->readback_attested=false;rejects([&]{C::json_receipt(r);},"unattested null retirement serialized");
    r.retirement->readback_attested=true;r.retirement->availability=E::NativeAvailability::available;
    rejects([&]{C::json_receipt(r);},"available null retirement lacked checked authority proof");
    r.retirement->authority_retired=true;
    check(C::json_receipt(r).at("retirement").at("authorityRetired").boolean(),"checked authority retirement extension missing");
    r.outcome=E::Outcome::applied;
    check(C::json_receipt(r).at("outcome").str()=="applied","actual applied outcome rewritten/lost during checked retirement");
    r.retirement->authority_retired=false;r.retirement->availability=E::NativeAvailability::noneditable;
    check(C::json_receipt(r).at("outcome").str()=="applied","original checked noneditable retirement lost known applied outcome");
    r.retirement->readback_attested=false;rejects([&]{C::json_receipt(r);},"applied null receipt lacked actual checked readback");
    r=receipt();r.outcome=static_cast<E::Outcome>(99);rejects([&]{C::json_receipt(r);},"unknown outcome converted to valid enum");
    ++groups;
}
void admission(){
    Fixture f;auto e=f.endpoint();e.terminal={};rejects([&]{H::BrowserSurfaceAdapter bad(7,{},{},8255,H::surface_web::Profile::editor_v1,e);},"missing atomic terminal hook admitted");
    e=f.endpoint();rejects([&]{H::BrowserSurfaceAdapter bad(7,{},{},8225,H::surface_web::Profile::editor_v1,e);},"partial editor core ceiling admitted");
    e.protocol=1;rejects([&]{H::BrowserSurfaceAdapter bad(7,{},{},8255,H::surface_web::Profile::editor_v1,e);},"wrong editor protocol admitted");
    f.connect();check(!f.adapter.editor_submit(C::parse_packet(packet()))&&!f.submits,"unpublished editor admitted observation");f.publish();check(!f.adapter.editor_submit(C::parse_packet(packet()))&&!f.submits,"unfocused editor admitted observation");f.focus();
    auto result=f.send(Json::Object{{"type","editorSubmit"},{"packet",packet()}});check(f.submits==1&&result.at("editorReply").at("ticket").str()==std::to_string(large+10)&&result.at("editorReply").at("sequence").str()=="2","actual receive did not queue exactly one owned observation");
    (void)f.session.receive(gui::web_detail::encode(Json::Object{{"epoch","epoch"},{"seq","2"},{"operation",Json::Object{{"type","editorSubmit"},{"packet",packet()}}}}));check(f.submits==1,"duplicate receive replayed endpoint observation");
    check(f.adapter.accept({basis().identity,2,gui_surface::KeyTransition{}}).status==gui_surface::Status::unsupported,"public editor retained legacy raw key path");
    ++groups;
}
void paired_tick_and_completion(){
    Fixture f;f.ready();auto old=basis();auto next=old;next.identity.presentation_revision=2;
    auto r=receipt(old);E::Settlement tag{r.session,r.id,r.submitted_token,r.predecessor};
    f.tick=[&]{check(f.adapter.present_editor_pair(snapshot(2),presentation(next),E::EditorPublication{next,tag,{},{}},{}).status==gui_surface::Status::ok,"ordinary Session tick could not publish editor pair");};
    auto reply=f.send(Json::Object{{"type","poll"}});f.tick={};
    check(reply.at("snapshot").at("revision").str()=="2"&&reply.at("surface").at("version").number()==2&&
        reply.at("surface").at("profile").str()=="editor_v1"&&reply.at("editor").at("basis").at("identity").at("presentationRevision").str()=="2","paired editor metadata split from actual frame");
    f.completion=E::EditorCompletion{large+10,{E::Admission::completed,r,{}}};reply=f.send(Json::Object{{"type","editorTake"},{"ticket",std::to_string(large+10)}});
    check(reply.at("editorReply").at("completion").at("receipt").at("basis").at("identity").at("presentationRevision").str()=="1"&&f.takes==1&&!f.adapter.failed(),"valid pRevision-only receipt alias rejected/restamped");
    reply=f.send(Json::Object{{"type","editorTake"},{"ticket",std::to_string(large+10)}});check(C::null(reply.at("editorReply").at("completion"))&&f.takes==2,"metadata take replayed consumed completion");
    ++groups;
}
void pointer_and_private_mismatch(){
    Fixture f;f.ready();gui_surface::MouseTransition mouse;mouse.phase=gui_surface::MousePhase::down;mouse.capture_token=large;mouse.buttons=1;
    check(f.adapter.accept({basis().identity,2,mouse}).status==gui_surface::Status::ok,"editor physical mouse setup failed");
    auto b=basis(2);f.publish({b,{},{},{}},2);mouse.phase=gui_surface::MousePhase::up;mouse.buttons=0;
    check(f.adapter.accept({b.identity,3,mouse}).status==gui_surface::Status::ok,"metadata repaint lost actual mouse capture");
    auto shown=b;shown.identity.presentation_revision=3;auto wrong=shown;wrong.editor_revision++;check(f.adapter.present_editor_pair(snapshot(3),presentation(shown),E::EditorPublication{wrong,{},{},{}},{}).status==gui_surface::Status::stale_identity,"public/private editor mismatch admitted");
    auto r=receipt();f.completion=E::EditorCompletion{large+10,{E::Admission::completed,r,{}}};rejects([&]{f.session.editor_take_json(large+10);},"completion escaped before head-tagged publication");
    check(f.terminals==1&&f.adapter.failed()&&!f.adapter.editor_publication(),"completion uncertainty did not notify atomic terminal once");
    ++groups;
}
void checked_retirement_modal_take(){
    Fixture f;f.ready();auto r=receipt();r.basis.reset();r.outcome=E::Outcome::cancelled;r.continuity=E::Continuity::replaced;r.retirement=E::RetirementReadback{E::NativeAvailability::noneditable,basis().identity,large,true};
    E::EditorPublication pub{{},E::Settlement{r.session,r.id,r.submitted_token,r.predecessor},{},r.retirement};
    pub.retirement->identity.context=99;r.retirement=pub.retirement;
    pub.composition=E::CompositionFact{large+20,E::CompositionState::ended};r.composition=pub.composition;
    gui::Snapshot redacted;redacted.revision=2;f.adapter.present(redacted);
    check(!f.adapter.accepted()&&!f.adapter.editor_publication(),"redaction retained editor authority");
    gui::Snapshot empty;empty.revision=3;
    check(f.adapter.present_editor_retirement(empty,pub).status==gui_surface::Status::ok,"actual empty snapshot could not publish checked null retirement");
    auto response=parse(f.session.initial());check(C::null(response.at("surface").at("presentation"))&&C::null(response.at("editor").at("basis"))&&response.at("editor").at("retirement").at("availability").str()=="noneditable","null retirement fabricated physical widget/presentation");
    f.offer_service=true;(void)f.session.initial();f.completion=E::EditorCompletion{large+10,{E::Admission::completed,r,{}}};
    response=f.send(Json::Object{{"type","editorTake"},{"ticket",std::to_string(large+10)}});
    check(f.takes==1&&response.at("editorReply").at("completion").at("receipt").at("retirement").at("readbackAttested").boolean(),"modal legacy service suppressed owned retirement metadata take");
    response=f.send(Json::Object{{"type","editorSubmit"},{"packet",packet()}});check(C::null(response.at("editorReply").at("ticket"))&&!f.submits,"modal/null retirement admitted new editor action");
    ++groups;
}
void failure_and_reentry(){
    Fixture f;f.ready();auto next=basis(2);next.identity.owner.generation=2;next.identity.context=2;auto s=snapshot(2);s.widgets[0].spec.key.generation=2;s.widgets[0].spec.kind=gui::Kind::bitmap;unsigned paints{};
    s.widgets[0].state.bitmap={"failing",1,gui::BitmapSource([&](const gui::BitmapRequest&,const gui::BitmapSink&){
        ++paints;
        check(!f.adapter.editor_submit(C::parse_packet(packet())),"bitmap callback admitted endpoint observation");
        check(f.adapter.present_editor_pair(snapshot(3),presentation(basis(3)),E::EditorPublication{basis(3),{},{},{}},{}).status==gui_surface::Status::busy,"paired publication reentered bitmap serialization");
        rejects([&]{f.session.editor_resync();},"bitmap callback reentered Session endpoint");throw std::runtime_error("paint");})};
    rejects([&]{f.adapter.present_editor_pair(s,presentation(next),E::EditorPublication{next,{},{},{}},{});},"actual serializer failure disappeared");
    check(paints==1&&f.terminals==1&&f.adapter.failed()&&!f.adapter.accepted()&&!f.adapter.editor_publication(),"failed public pair skipped actual paint or retained private authority/missed terminal hook");
    ++groups;
}
void malformed_and_throwing_hook(){
    Fixture f;f.ready();f.throw_hook=true;auto response=f.send(Json::Object{{"type","editorSubmit"},{"packet",packet()}});
    check(f.terminals==1&&f.adapter.failed()&&response.at("snapshot").at("closed").boolean()&&C::null(response.at("editor"))&&C::null(response.at("editorReply")),"throwing queue hook produced fake reply or reopened authority");
    Fixture bad;bad.ready();bad.offer_service=true;(void)bad.session.initial();auto p=packet();object(p).emplace("forged",true);
    rejects([&]{bad.send(Json::Object{{"type","editorSubmit"},{"packet",p}});},"modal service hid malformed reserved editor packet");check(bad.terminals==1&&!bad.submits,"malformed modal editor packet entered endpoint");
    H::BrowserSurfaceAdapter old(7);H::BrowserSurfaceSession legacy(old,"epoch");
    rejects([&]{legacy.receive(gui::web_detail::encode(Json::Object{{"epoch","epoch"},{"seq","1"},{"operation",Json::Object{{"type","editorResync"}}}}));},"old profile admitted editor endpoint opcode");
    ++groups;
}
void response_service_race(){
    Fixture f;f.ready();auto r=receipt();E::Settlement tag{r.session,r.id,r.submitted_token,r.predecessor};
    f.publish({r.basis,tag,{},{}},1);f.completion=E::EditorCompletion{large+10,{E::Admission::completed,r,{}}};f.offer_service=true;
    const auto response=f.send(Json::Object{{"type","editorTake"},{"ticket",std::to_string(large+10)}});
    check(f.takes==1&&f.terminals==1&&f.adapter.failed()&&response.at("snapshot").at("closed").boolean()&&
        C::null(response.at("editorReply"))&&C::null(response.at("editor"))&&C::null(response.at("service"))&&C::null(response.at("transfer")),
        "response service acquisition exposed completion after its paired publication retired");
    ++groups;
}
void large_state_and_terminal(){
    Fixture f;f.ready();auto b=basis(2);b.identity.owner.generation=2;b.identity.context=2;auto s=snapshot(2);s.widgets[0].spec.key.generation=2;s.client_size={600,600};s.widgets[0].state.bounds={0,0,600,600};s.widgets[0].spec.kind=gui::Kind::bitmap;
    s.widgets[0].state.bitmap={"large",1,gui::solid_bitmap(17,33,99)};auto p=presentation(b);p.bounds={0,0,600,600};p.clip=p.bounds;
    check(f.adapter.present_editor_pair(s,p,E::EditorPublication{b,{},{},{}},{}).status==gui_surface::Status::ok,"legal large editor bitmap pair rejected");
    const auto response=f.session.initial();check(response.size()>1048576&&!f.adapter.failed()&&response.find("\"error\":\"\"")!=std::string::npos&&
        response.find("\"editor\":{")!=std::string::npos&&response.find("\"editorReply\":null")!=std::string::npos,
        "legal outbound bitmap hit incoming-operation parser size limit");
    auto r=receipt();r.outcome=E::Outcome::unknown;f.completion=E::EditorCompletion{large+10,{E::Admission::terminal,r,{}}};
    (void)f.adapter.editor_take(large+10);check(f.terminals==1&&!f.adapter.input_admitted()&&!f.adapter.editor_submit(C::parse_packet(packet())),
        "terminal unknown endpoint completion retained input admission");
    ++groups;
}
void owned_key_release(){
    Fixture f;f.connect();auto raw=presentation(basis());raw.editor.reset();raw.required=33;
    check(f.adapter.present_editor_pair(snapshot(),raw,noneditable(),{}).status==gui_surface::Status::ok,"body physical setup failed");f.focus();
    gui_surface::KeyTransition down{gui_surface::KeyPhase::down,"F5","F5"};
    check(f.adapter.accept({raw.identity,2,down}).status==gui_surface::Status::ok,"actual body keydown refused");
    auto pending=raw;pending.identity.presentation_revision=2;
    check(f.adapter.present_editor_pair(snapshot(2),pending,{},{}).status==gui_surface::Status::ok,"pending query metadata retired physical key continuation");
    check(f.adapter.accept({pending.identity,3,down}).status==gui_surface::Status::unsupported,"pending query admitted new body down without noneditable proof");
    auto next=basis(3);const auto original=basis();
    check(f.adapter.present_editor_pair(snapshot(3),presentation(next),E::EditorPublication{original,{},{},{}},{}).status==gui_surface::Status::ok,
        "explicit presentation-only native basis alias rejected");
    check(f.adapter.editor_publication()->basis->identity.presentation_revision==3&&original.identity.presentation_revision==1,
        "publication alias mutated original native basis or failed current public join");
    check(f.adapter.accept({next.identity,3,down}).status==gui_surface::Status::unsupported,"new keydown bypassed public editor gate");
    auto up=down;up.phase=gui_surface::KeyPhase::up;
    const auto result=f.adapter.accept({raw.identity,3,up});
    check(result.status==gui_surface::Status::ok&&result.accepted->event.identity==raw.identity,
        "real owned release lost held continuation or original pRevision identity");
    check(f.adapter.accept({raw.identity,4,up}).status!=gui_surface::Status::ok,"owned physical release replayed");
    ++groups;
}
void physical_retirement_continuation(){
    Fixture f;f.connect();auto raw=presentation(basis());raw.editor.reset();raw.required=33;
    check(f.adapter.present_editor_pair(snapshot(),raw,noneditable(),{}).status==gui_surface::Status::ok,"physical retirement setup failed");f.focus();
    gui_surface::KeyTransition down{gui_surface::KeyPhase::down,"F5","F5"};
    check(f.adapter.accept({raw.identity,2,down}).status==gui_surface::Status::ok,"owned down setup failed");
    auto next=raw;next.identity.presentation_revision=2;
    E::RetirementReadback proof{E::NativeAvailability::available,raw.identity,large,true,true};
    check(f.adapter.present_editor_pair(snapshot(2),next,E::EditorPublication{{},{},{},proof},{}).status==gui_surface::Status::ok,
        "checked editor authority retirement destroyed independent physical pair");
    check(f.adapter.accept({next.identity,3,gui_surface::FocusChange{true,true,{}}}).status==gui_surface::Status::ok,
        "editor authority retirement blocked valid physical focus");
    gui_surface::MouseTransition mouse;mouse.phase=gui_surface::MousePhase::down;mouse.buttons=1;mouse.capture_token=large;
    check(f.adapter.accept({next.identity,4,mouse}).status==gui_surface::Status::ok,"editor authority retirement blocked physical mouse");
    check(f.adapter.accept({next.identity,5,down}).status==gui_surface::Status::unsupported,"retired editor proof admitted new body keydown");
    auto up=down;up.phase=gui_surface::KeyPhase::up;
    const auto released=f.adapter.accept({raw.identity,5,up});
    check(released.status==gui_surface::Status::ok&&released.accepted->event.identity==raw.identity,
        "editor authority retirement dropped real owned physical release");
    next.identity.presentation_revision=3;proof.authority_retired=false;proof.availability=E::NativeAvailability::noneditable;
    check(f.adapter.present_editor_pair(snapshot(3),next,E::EditorPublication{{},{},{},proof},{}).status==gui_surface::Status::ok&&
        f.adapter.accept({next.identity,6,down}).status==gui_surface::Status::ok,"checked noneditable body raw path unavailable");
    next.identity.presentation_revision=4;proof.identity.context=99;
    check(f.adapter.present_editor_pair(snapshot(4),next,E::EditorPublication{{},{},{},proof},{}).status==gui_surface::Status::ok&&
        f.adapter.accept({next.identity,7,down}).status==gui_surface::Status::unsupported,
        "historical noneditable readback activated unrelated current physical context");
    ++groups;
}
void pending_basis_restore(){
    Fixture f;f.ready();const E::CompositionFact logical{large+20,E::CompositionState::pending};
    check(f.adapter.present_editor_pair(snapshot(2),presentation(basis(2)),E::EditorPublication{basis(),{},logical,{}},logical).status==gui_surface::Status::ok,
        "actual logical pending composition setup failed");
    auto pending=presentation(basis(3));pending.editor.reset();pending.required=33;
    check(f.adapter.present_editor_pair(snapshot(3),pending,{},{}).status==gui_surface::Status::ok&&!f.adapter.editor_publication(),
        "pending query retained public editor authority");
    auto changed=basis(4);changed.editor_revision++;
    check(f.adapter.present_editor_pair(snapshot(4),presentation(changed),E::EditorPublication{changed,{},logical,{}},logical).status==gui_surface::Status::stale_identity,
        "pending same-token restore altered native editor facts");
    auto original=basis();auto next=basis(4);
    check(f.adapter.present_editor_pair(snapshot(4),presentation(next),E::EditorPublication{original,{},{},{}},{}).status==gui_surface::Status::stale_identity,
        "untagged inert restore cleared logical pending composition");
    const E::CompositionFact changed_logical{large+21,E::CompositionState::pending};
    check(f.adapter.present_editor_pair(snapshot(4),presentation(next),E::EditorPublication{original,{},changed_logical,{}},changed_logical).status==gui_surface::Status::stale_identity,
        "untagged inert restore changed logical transaction");
    check(f.adapter.present_editor_pair(snapshot(4),presentation(next),E::EditorPublication{original,{},logical,{}},logical).status==gui_surface::Status::ok&&
        f.adapter.editor_publication()->basis->token==original.token,"unchanged inert query could not restore exact native token");
    ++groups;
}
} // namespace
int main(){try{codec();admission();paired_tick_and_completion();pointer_and_private_mismatch();checked_retirement_modal_take();failure_and_reentry();malformed_and_throwing_hook();response_service_race();large_state_and_terminal();owned_key_release();physical_retirement_continuation();pending_basis_restore();std::cout<<"browser editor: "<<groups<<" groups, "<<assertions<<" assertions passed; actual generic WebAdapter/Session, no engine/Controller\n";return 0;}catch(const std::exception& e){std::cerr<<e.what()<<" (completed groups="<<groups<<", assertions="<<assertions<<")\n";return 1;}}
