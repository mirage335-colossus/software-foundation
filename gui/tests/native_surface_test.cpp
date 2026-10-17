// SPDX-License-Identifier: CC0-1.0
#include "host/native_surface.hpp"
#include <gui/memory_adapter.hpp>
#include <atomic>
#include <functional>
#include <iostream>
#include <limits>
#include <stdexcept>

namespace {
namespace H=foundation::host;
namespace S=foundation::gui_surface;
namespace E=foundation::gui_editor;
std::size_t checks{},groups{};
void check(bool v,const char* why) { ++checks; if(!v) throw std::runtime_error(why); }
template<class F> void throws(F f) { bool caught=false;try{f();}catch(const std::exception&){caught=true;}check(caught,"expected checked failure"); }
gui::Snapshot frame(std::uint64_t revision=1) {
    gui::Snapshot value;value.revision=revision;value.title="private frame";value.client_size={80,60};
    gui::Widget widget;widget.spec.key={"surface",7};widget.spec.kind=gui::Kind::bitmap;
    widget.state.bounds={0,0,80,60};value.widgets.push_back(std::move(widget));return value;
}
S::Presentation pair(std::uint64_t revision=1,std::uint64_t context=1) {
    S::Presentation value;value.identity={{"surface",7},revision,8,1,context};value.bounds=value.clip={0,0,80,60};
    value.keys.fallback=S::Capture::capture;return value;
}
struct Fixture {
    gui::MemoryAdapter backend;
    unsigned renders{},suspends{},closed{},inputs{},activations{};
    std::atomic<unsigned> terminal{};
    std::function<void()> during_render;
    std::function<void()> during_editor;
    bool before{},after{},wrong{};
    std::vector<H::NativeEditorPresentation> editor;
    std::vector<E::Packet> submitted;
    std::uint64_t next_ticket{1};
    std::optional<E::EditorCompletion> completion;
    H::NativeSurfacePeer peer(bool edit=false) {
        H::NativeSurfacePeer p;p.capabilities.supported=edit?8255:8225;p.capabilities.mouse_input_version=1;
        p.ready=[] {return true;};
        p.present=[this](gui::Snapshot value) {
            if(before)throw std::runtime_error("before renderer install");
            const auto revision=value.revision;backend.present(std::move(value));++renders;
            if(during_render)during_render();
            if(after)throw std::runtime_error("after renderer install");
            return H::NativeRenderReceipt{wrong?revision+1:revision};
        };
        p.editor=[this](const H::NativeEditorPresentation& v){editor.push_back(v);if(during_editor)during_editor();};
        p.suspend=[this]{++suspends;};p.activate=[this]{++activations;};p.close=[this]{++closed;};return p;
    }
    H::NativeEditorEndpoint endpoint() {
        return {[this](E::Packet p)->std::optional<std::uint64_t>{submitted.push_back(std::move(p));return next_ticket++;},
            [this](E::Revocation)->std::optional<std::uint64_t>{return next_ticket++;},
            [this](std::uint64_t)->std::optional<E::EditorCompletion>{auto v=completion;completion.reset();return v;},
            []{}, {&terminal,[](void* v)noexcept{++*static_cast<std::atomic<unsigned>*>(v);}}};
    }
    void arm(H::NativeSurfaceAdapter& surface) {
        surface.arm([this](S::AcceptedEvent){++inputs;},[](S::Capabilities c){check(c.version==1,"capabilities version widened");});
    }
};
void render_and_input() {
    Fixture f;H::NativeSurfaceAdapter surface(f.backend,8,f.peer(),H::NativeSurfaceMode::mouse_v1);f.arm(surface);
    check(f.activations==1,"actual state activation did not follow arm");
    f.during_render=[&]{check(!surface.input_admitted(),"publication admitted synchronous input");
        check(!surface.dispatch_input(S::FocusChange{true,true,S::FocusCause::direct}).accepted,"render callback delivered raw input");
        check(surface.present_pair(frame(2),pair(2)).status==S::Status::busy,"reentrant pair entered renderer");};
    check(surface.present_pair(frame(),pair()).status==S::Status::ok,"real exact renderer receipt failed");f.during_render={};
    check(f.editor.size()==1 && f.editor.back().surface && f.editor.back().surface->identity==pair().identity && !f.editor.back().context,"mouse peer did not receive exact context metadata");
    surface.tick();check(f.activations==2,"new pair did not request actual state activation");
    check(surface.dispatch_input(S::FocusChange{true,true,S::FocusCause::direct}).accepted.has_value(),"real focus rejected");
    check(surface.dispatch_input(S::KeyTransition{S::KeyPhase::down,"a","KeyA",0,0,false}).accepted.has_value(),"raw DOWN rejected");
    check(surface.present_pair(frame(2),pair(2)).status==S::Status::ok,"same native context repaint failed");
    check(f.editor.back().surface && f.editor.back().surface->identity.presentation_revision==2 && f.editor.back().surface->identity.context==1,"repaint was not distinguishable from native context replacement");
    check(surface.dispatch_input(S::KeyTransition{S::KeyPhase::up,"a","KeyA",0,0,false}).accepted.has_value(),"owned UP lost on repaint");
    auto foreign=pair(2).identity;++foreign.context;
    check(surface.input({foreign,50,S::FocusChange{true,true,S::FocusCause::direct}}).status==S::Status::stale_identity,"foreign full identity accepted");
    auto invalid=pair(3,2);invalid.identity.owner.id="foreign";
    const auto before=f.renders;check(surface.present_pair(frame(3),invalid).status!=S::Status::ok,"missing actual owner accepted");
    check(f.renders==before+1 && surface.failed(),"post-render owner mismatch did not close admission");
}
void faults_capabilities_and_lifetime() {
    for(unsigned mode=0;mode<3;++mode) {
        Fixture f;f.before=mode==0;f.after=mode==1;f.wrong=mode==2;
        H::NativeSurfaceAdapter surface(f.backend,8,f.peer(),H::NativeSurfaceMode::mouse_v1);f.arm(surface);
        throws([&]{(void)surface.present_pair(frame(),pair());});
        check(surface.failed() && !surface.accepted() && !surface.input_admitted(),"unproven renderer result kept authority");
        check(f.renders==(mode==0?0:1),"failure fixture did not cross intended install boundary");
    }
    Fixture f;auto bad=f.peer();bad.capabilities.supported=8255;
    throws([&]{H::NativeSurfaceAdapter surface(f.backend,8,bad,H::NativeSurfaceMode::mouse_v1);});
    bad=f.peer(true);bad.editor={};throws([&]{H::NativeSurfaceAdapter surface(f.backend,8,bad,H::NativeSurfaceMode::editor_v1,f.endpoint());});
    bad=f.peer();bad.ready=[] {return false;};throws([&]{H::NativeSurfaceAdapter surface(f.backend,8,bad,H::NativeSurfaceMode::mouse_v1);});
    H::NativeSurfacePublisher saved;
    {
        H::NativeSurfaceAdapter surface(f.backend,8,f.peer(),H::NativeSurfaceMode::mouse_v1);saved=surface.publisher();
        check(saved.bound() && saved.present_pair(frame(),pair()).status==S::Status::ok,"constructor-time weak publisher unavailable");
        surface.disarm();check(saved.present_pair(frame(2),pair(2)).status==S::Status::closed,"disarm failed to expire publisher");
        check(!saved.set_owned_service_active(true),"expired service setter touched peer");
    }
    const auto count=f.renders;check(saved.present_pair(frame(3),pair(3)).status==S::Status::closed && f.renders==count,"expired publisher reached dead backend");
    check(f.closed==1,"actual peer close repeated");
}
void service_and_transform_retirement() {
    Fixture f;H::NativeSurfaceAdapter surface(f.backend,8,f.peer(),H::NativeSurfaceMode::mouse_v1);f.arm(surface);
    check(surface.present_pair(frame(),pair()).status==S::Status::ok,"initial pair failed");
    surface.set_owned_service_active(true);
    check(!surface.accepted() && !surface.input_admitted() && f.backend.snapshot().title.empty(),"service did not actually redact and revoke");
    check(!f.editor.back().surface,"legacy redaction left mouse peer context armed");
    for(const auto& w:f.backend.snapshot().widgets)check(!w.state.visible&&!w.state.enabled,"actual renderer retained live service widget");
    surface.set_owned_service_active(false);check(!surface.accepted(),"service release resurrected old pair");
    check(surface.present_pair(frame(2),pair(2,2)).status==S::Status::ok,"service renderer was permanently stopped");
    surface.invalidate(S::RevocationReason::replaced);check(!surface.accepted(),"transform change preserved old coordinate authority");
    check(surface.present_pair(frame(3),pair(3,3)).status==S::Status::ok,"fresh transform context failed");
    check(surface.input({pair(3,3).identity,UINT64_MAX,S::FocusChange{true,true,S::FocusCause::direct}}).accepted.has_value(),"final input sequence was lost");
    check(surface.dispatch_input(S::FocusChange{}).status==S::Status::limit_exceeded && surface.failed(),"input sequence wrapped");
}
void editor_head_and_actual_pair() {
    Fixture f;H::NativeSurfaceAdapter surface(f.backend,8,f.peer(true),H::NativeSurfaceMode::editor_v1,f.endpoint());f.arm(surface);
    auto p=pair();E::Basis basis{70,p.identity,90,"ab",{1,1},false,0};
    p.editor=S::EditorContext{90,0,"ab",{1,1},false,{1,2,1,10},true,"text"};
    E::EditorPublication pub{basis,{},{},{}};
    check(surface.present_editor_pair(frame(),p,pub,{}).status==S::Status::ok,"checked editable actual pair failed");
    check(surface.dispatch_input(S::FocusChange{true,true,S::FocusCause::direct}).accepted.has_value(),"editor focus failed");
    check(surface.dispatch_input(S::KeyTransition{S::KeyPhase::down,"x","KeyX",0,0,false}).status==S::Status::unavailable,"editable key dispatched twice through physical path");
    auto before=H::capture_native_editor_text("ab",S::ByteRange{1,1},E::Direction::none);
    auto after=H::capture_native_editor_text("axb",S::ByteRange{2,2},E::Direction::none);
    check(surface.observe_editor({E::Kind::text,E::Authority::range,{},true,0,before,after,E::TextData{"insertText","x",{1,1},{}}}).has_value(),"actual editor observation rejected");
    surface.tick();check(f.submitted.size()==1 && surface.editor_capture()->pending()==1,"editor head did not stage exactly once");
    const auto packet=f.submitted.front();auto next=basis;++next.token;++next.editor_revision;next.surrounding="axb";next.selection={2,2};
    E::Receipt receipt{packet.session,packet.observation.id,basis.token,packet.observation.predecessor,E::Outcome::applied,next,E::Continuity::same,{},{},{}};
    f.completion=E::EditorCompletion{1,{E::Admission::completed,receipt,{}}};surface.tick();
    check(surface.editor_capture()->pending()==1,"metadata take released before exact current publication");
    p.identity.presentation_revision=2;p.editor->revision=next.editor_revision;p.editor->surrounding=next.surrounding;p.editor->selection=next.selection;
    pub={next,E::Settlement{receipt.session,receipt.id,receipt.submitted_token,receipt.predecessor},{},{}};
    check(surface.present_editor_pair(frame(2),p,pub,{}).status==S::Status::ok,"exact head settlement pair failed");
    surface.tick();check(surface.editor_capture()->pending()==0 && surface.editor_capture()->draft()->value=="axb","current paired head did not settle");
    auto corrupt=pub;corrupt.basis->surrounding="changed under same token";
    p.identity.presentation_revision=3;p.editor->surrounding=corrupt.basis->surrounding;
    check(surface.present_editor_pair(frame(3),p,corrupt,{}).status!=S::Status::ok,"changed native token basis accepted");
    surface.editor_capture()->retire("actual frontend discontinuity");surface.tick();
    check(!f.editor.back().context && !f.editor.back().draft && !f.editor.back().preserve_passage &&
        f.editor.back().publication && f.editor.back().publication->basis,"suspended frontend displayed unresolved Basis as live editability");
}
void editor_publication_faults_and_cleanup() {
    for (bool throws_after:{false,true}) {
        Fixture f;H::NativeSurfaceAdapter surface(f.backend,8,f.peer(true),H::NativeSurfaceMode::editor_v1,f.endpoint());f.arm(surface);
        auto p=pair();E::Basis basis{70,p.identity,90,"ab",{1,1},false,0};
        p.editor=S::EditorContext{90,0,"ab",{1,1},false,{1,2,1,10},true,"text"};
        f.during_editor=[&]{
            check(!surface.input_admitted(),"native editor callback escaped publication gate");
            if(throws_after)throw std::runtime_error("native editor installation fault");
            surface.close();
        };
        if(throws_after) throws([&]{(void)surface.present_editor_pair(frame(),p,E::EditorPublication{basis,{},{},{}},{});});
        else check(surface.present_editor_pair(frame(),p,E::EditorPublication{basis,{},{},{}},{}).status==S::Status::closed,"reentrant close returned an effect receipt");
        check(f.renders==1 && !surface.accepted() && !surface.input_admitted(),"post-render native editor fault retained authority");
    }
    Fixture f;auto peer=f.peer();peer.suspend=[] {throw std::runtime_error("suspend fault");};
    H::NativeSurfaceAdapter surface(f.backend,8,std::move(peer),H::NativeSurfaceMode::mouse_v1);
    auto saved=surface.publisher();throws([&]{surface.close();});
    check(f.closed==1 && f.backend.closed() && !saved.set_owned_service_active(true),"throwing suspension prevented irreversible cleanup or left publisher live");
    surface.close();check(f.closed==1,"failed cleanup repeated permanent close");
}
void inert_editor_pause_preserves_live_passage() {
    Fixture f;H::NativeSurfaceAdapter surface(f.backend,8,f.peer(true),H::NativeSurfaceMode::editor_v1,f.endpoint());f.arm(surface);
    auto p=pair();E::Basis basis{70,p.identity,90,"ab",{1,1},false,0};
    p.editor=S::EditorContext{90,0,"ab",{1,1},false,{1,2,1,10},true,"text"};
    E::EditorPublication current{basis,{},{},{}};
    check(surface.present_editor_pair(frame(),p,current,{}).status==S::Status::ok,"pause fixture initial publication failed");
    check(surface.dispatch_input(S::FocusChange{true,true,S::FocusCause::direct}).accepted.has_value(),"pause fixture actual focus failed");
    const auto root=H::capture_native_editor_text("ab",S::ByteRange{1,1},E::Direction::none);
    const auto preedit=H::capture_native_editor_text("axb",S::ByteRange{2,2},E::Direction::none);
    const std::uint64_t transaction=1;
    check(surface.observe_editor({E::Kind::composition,E::Authority::range,{},false,transaction,root,root,
        E::CompositionData{S::CompositionOperation::begin,"",{0,0},root.selection,{}}}).has_value(),"actual begin passage rejected");
    auto settle=[&](std::uint64_t ticket,E::Basis next,E::CompositionFact fact,std::uint64_t revision) {
        const auto packet=f.submitted.back();E::Receipt receipt{packet.session,packet.observation.id,packet.basis.token,
            packet.observation.predecessor,E::Outcome::applied,next,E::Continuity::same,{},fact,{}};
        f.completion=E::EditorCompletion{ticket,{E::Admission::completed,receipt,{}}};surface.tick();
        p.identity.presentation_revision=revision;p.editor=S::EditorContext{next.editor_revision,next.composition,next.surrounding,
            next.selection,next.backward,{1,2,1,10},true,"text"};
        current={next,E::Settlement{receipt.session,receipt.id,receipt.submitted_token,receipt.predecessor},fact,{}};
        check(surface.present_editor_pair(frame(revision),p,current,fact).status==S::Status::ok,"composition exact settlement failed");surface.tick();
    };
    surface.tick();settle(1,basis,{transaction,E::CompositionState::pending},2);
    check(surface.observe_editor({E::Kind::composition,E::Authority::composition,{},false,transaction,root,preedit,
        E::CompositionData{S::CompositionOperation::update,"x",{1,1},{},{}}}).has_value(),"actual preedit update rejected");
    surface.tick();++basis.token;++basis.editor_revision;basis.surrounding="axb";basis.selection={2,2};basis.composition=transaction;
    settle(2,basis,{transaction,E::CompositionState::live},3);
    check(surface.editor_capture()->pending()==0 && surface.editor_capture()->composition() &&
        surface.editor_capture()->composition()->state==E::CompositionState::live,"fixture lacks live composition with no queued head");
    auto pending=p;pending.identity.presentation_revision=4;pending.editor.reset();pending.available=false;
    check(surface.present_editor_pair(frame(4),pending,E::EditorPublication{},{}).status==S::Status::ok,"inert pending publication failed");
    const auto& paused=f.editor.back();
    check(paused.admission==H::NativeEditorAdmission::paused && paused.preserve_passage && paused.draft &&
        paused.draft->value=="axb" && paused.passage_basis==std::optional{basis} && paused.passage_composition==current.composition &&
        paused.publication && !paused.publication->basis && !surface.input_admitted(),"inert pause destroyed frontend passage or minted publication authority");
    check(!surface.dispatch_input(S::KeyTransition{S::KeyPhase::down,"z","KeyZ",0,0,false}).accepted,"paused context delivered fresh physical input");
    check(surface.observe_editor({E::Kind::composition,E::Authority::composition,{},true,transaction,preedit,preedit,
        E::CompositionData{S::CompositionOperation::commit,"x",{1,1},{},{}}}).has_value(),"paused collector lost actual native continuation");
    surface.tick();check(f.submitted.size()==2 && surface.editor_capture()->pending()==1,"paused collector entered endpoint");
    p.identity.presentation_revision=5;
    check(surface.present_editor_pair(frame(5),p,current,current.composition).status==S::Status::ok &&
        f.editor.back().admission==H::NativeEditorAdmission::active,"same checked Basis did not resume actual passage");
    check(surface.dispatch_input(S::FocusChange{true,true,S::FocusCause::direct}).accepted.has_value(),"actual focus requery after unavailable gate failed");
    surface.tick();check(f.submitted.size()==3 && f.submitted.back().basis==basis,"paused continuation was rebased or discarded");
    surface.invalidate(S::RevocationReason::focus_loss);surface.tick();
    check(f.editor.back().admission==H::NativeEditorAdmission::withdrawn && !f.editor.back().passage_basis &&
        !f.editor.back().passage_composition && !f.editor.back().draft && !f.editor.back().preserve_passage &&
        !surface.observe_editor({}),"real withdrawal kept paused frontend authority");
}
}
int main() {
    try {
        for(const auto& test:{render_and_input,faults_capabilities_and_lifetime,service_and_transform_retirement,editor_head_and_actual_pair,editor_publication_faults_and_cleanup,inert_editor_pause_preserves_live_passage}){test();++groups;}
        std::cout<<groups<<" groups, "<<checks<<" checks, 0 skipped\n";return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<" after "<<groups<<" groups / "<<checks<<" checks\n";return 1;}
}
