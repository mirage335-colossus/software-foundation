// SPDX-License-Identifier: CC0-1.0
#include "host/native_fltk_surface_peer.hpp"
#include <iostream>
#include <stdexcept>
#include <string>
using namespace foundation;
namespace H=foundation::host;
namespace E=foundation::gui_editor;
namespace S=foundation::gui_surface;
namespace {
int checks=0;
void check(bool value,const char* message){++checks;if(!value)throw std::runtime_error(message);}
template<class F> void rejects(F operation,const char* message){bool caught=false;try{operation();}catch(const std::exception&){caught=true;}check(caught,message);}
E::TextObservation text(std::string value,std::size_t first,std::size_t last){return H::capture_native_editor_text(std::move(value),first,last,E::Direction::forward);}
H::FltkNativeEdit edit(H::FltkNativeEditKind kind,std::string value,std::size_t first,std::size_t last,std::uint64_t transaction=0){return {kind,std::move(value),first,last,false,transaction};}
S::KeyTransition key(S::KeyPhase phase=S::KeyPhase::down){return {phase,"a","KeyA",0,0,false};}
void mouse(){
    check(H::fltk_native_mouse_button(1)==0,"left button");check(H::fltk_native_mouse_button(2)==1,"middle button");
    check(H::fltk_native_mouse_button(3)==2,"right button");check(H::fltk_native_mouse_button(4)==3,"back button");check(H::fltk_native_mouse_button(5)==4,"forward button");
    check(!H::fltk_native_mouse_button(0)&&!H::fltk_native_mouse_button(6),"unknown button not invented");
    check(H::fltk_native_mouse_buttons(FL_BUTTON1|FL_BUTTON2|FL_BUTTON3|FL_BUTTON4|FL_BUTTON5)==31,"five held buttons");
    check(H::fltk_native_mouse_buttons(FL_BUTTON2)==4,"middle held mask");check(H::fltk_native_mouse_buttons(FL_BUTTON3)==2,"right held mask");
}
void viewport(){
    const auto view=H::FltkNativeViewport::make(800,600,1000,600);
    check(view.x==100&&view.y==0&&view.scale==1,"actual window letterbox");
    check(view.logical(100,0)==std::pair{0.0,0.0},"mouse inverse");
    check(view.logical(900,600)==std::pair{800.0,600.0},"mouse bottom inverse");
    auto caret=view.caret({10,20,2,10},{0,0,800,600});check(caret==S::Rect{110,20,2,10},"caret shares canvas transform");
    caret=view.caret({-2,20,4,10},{0,0,800,600});check(caret==S::Rect{100,20,2,10},"caret clipped before mapping");
    rejects([&]{view.caret({900,20,1,1},{0,0,800,600});},"invisible caret not fabricated");
    rejects([]{H::FltkNativeViewport::make(0,600,100,100);},"empty canvas rejected");
    rejects([]{H::FltkNativeViewport::make(800,600,0,100);},"hidden drawable rejected");
    const auto quantized=H::FltkNativeViewport::make(7,3,10,10);
    check(quantized.image_width==10&&quantized.image_height==4&&quantized.y==3,"actual integer image rectangle");
    check(quantized.logical(10,7)==std::pair{7.0,3.0},"rounded native image inverse exact");
}
void keys(){
    H::FltkNativeFrontend frontend;frontend.install(text("ab",1,1),false);
    auto observations=frontend.observe({key(),{}});
    check(observations.size()==1&&observations[0].kind==E::Kind::key,"actual raw key copied");
    check(!observations[0].group&&!observations[0].after,"key has no fabricated text/default passage");
    check(frontend.draft()->value=="ab","key cannot edit text");
    auto malformed=text("ab",1,1);malformed.byte_length=1;
    rejects([&]{frontend.install(malformed,false);},"publication lengths cannot be normalized into facts");
    check(std::get<E::KeyData>(observations[0].data).transition.code=="KeyA","physical code preserved");
    observations=frontend.observe({key(S::KeyPhase::up),{}});check(observations.size()==1,"actual keyup copied");
}
void committed(){
    H::FltkNativeFrontend frontend;frontend.install(text("ab",1,1),false);
    auto result=frontend.observe({key(),{edit(H::FltkNativeEditKind::text,"\xF0\x9F\x98\x80",2,2)}});
    check(result.size()==2,"actual key and commit stay one passage");
    check(result[0].group&&result[0].group==result[1].group,"default group exact");
    check(!result[0].group_end&&result[1].group_end,"last dependent closes group");
    check(result[1].authority==E::Authority::default_action,"actual same-passage commit default authority");
    check(result[1].after->value=="a\xF0\x9F\x98\x80" "b"&&result[1].after->selection==S::ByteRange{5,5},"UTF16 commit preserves actual scalar caret");
    const auto& data=std::get<E::TextData>(result[1].data);check(data.replacement==S::ByteRange{1,1}&&data.source_groups==std::vector<std::uint64_t>{*result[1].group},"exact original replacement and causal group");
    rejects([&]{frontend.observe({{}, {edit(H::FltkNativeEditKind::text,"\xF0\x9F\x98\x80",1,1)}});},"split surrogate rejected");
    rejects([&]{frontend.observe({key(),{edit(H::FltkNativeEditKind::selection,"",0,0),edit(H::FltkNativeEditKind::text,"x",1,1)}});},"mixed selection/default cannot bypass key receipt");
}
void independent(){
    H::FltkNativeFrontend frontend;frontend.install(text("abc",1,2),false);
    auto result=frontend.observe({{}, {edit(H::FltkNativeEditKind::text,"XY",2,2)}});
    check(result.size()==1&&!result[0].group&&result[0].authority==E::Authority::range,"independent actual commit has range authority");
    check(result[0].after->value=="aXYc","actual commit replaces original native selection");
}
void preedit(){
    H::FltkNativeFrontend frontend;frontend.install(text("abc",1,2),false);
    auto result=frontend.observe({key(),{edit(H::FltkNativeEditKind::composition_begin,"",0,0,7)}});
    check(frontend.composing()&&result.size()==2,"actual composition begins");
    check(result[1].after==result[1].before,"empty native preedit-start does not invent deletion of the native selection");
    check(std::get<E::CompositionData>(result[1].data).replacement==S::ByteRange{1,2},"begin replacement exact");
    result=frontend.observe({{}, {edit(H::FltkNativeEditKind::composition_update,"xy",1,1,7)}});
    check(result[0].after->value=="axyc"&&result[0].after->selection==S::ByteRange{2,2},"actual preedit update");
    frontend.install(frontend.draft(),true);check(frontend.composing(),"checked-head publication preserves provisional preedit");
    frontend.install(frontend.draft(),false);check(frontend.composing(),"identical draft does not implicitly cancel native preedit");
    rejects([&]{frontend.install(text("changed",0,0),true);},"outstanding draft not overwritten");
    rejects([&]{frontend.install(text("changed",0,0),false);},"live preedit cannot be rebased");
    rejects([&]{frontend.observe({{}, {edit(H::FltkNativeEditKind::composition_update,"x",1,1,8)}});},"foreign transaction rejected");
    result=frontend.observe({{}, {edit(H::FltkNativeEditKind::composition_commit,"Z",1,1,7)}});
    check(!frontend.composing()&&result[0].after->value=="aZc","actual preedit commit");
}
void cancelled(){
    H::FltkNativeFrontend frontend;frontend.install(text("abc",1,2),false);
    frontend.observe({{}, {edit(H::FltkNativeEditKind::composition_begin,"x",1,1,4)}});
    auto result=frontend.observe({{}, {edit(H::FltkNativeEditKind::composition_cancel,"",0,0,4)}});
    check(result[0].after->value=="abc"&&result[0].after->selection==S::ByteRange{1,2},"actual cancellation restores original frontend range");
    check(!frontend.composing(),"native cancellation closes transaction");
}
void selection(){
    H::FltkNativeFrontend frontend;frontend.install(text("A\xF0\x9F\x98\x80" "B",1,1),false);
    auto change=edit(H::FltkNativeEditKind::selection,"",1,3);change.backward=true;
    auto result=frontend.observe({{}, {change}});check(result[0].after->selection==S::ByteRange{1,5},"actual native selection UTF16->UTF8");
    check(std::get<E::SelectionData>(result[0].data).backward,"actual selection direction retained");
}
void dead_keys(){
    H::FltkNativeFrontend frontend;frontend.install(text("",0,0),false);
    auto dead=key();dead.key="Dead";dead.code="Quote";
    auto first=frontend.observe({dead,{}});
    check(first[0].group&&!first[0].group_end,"actual Dead fact retains its conditional source");
    auto result=frontend.observe({key(),{edit(H::FltkNativeEditKind::text,"a",1,1)}});
    const auto& groups=std::get<E::TextData>(result[1].data).source_groups;
    check(groups.size()==2&&groups[0]==*first[0].group&&groups[1]==*result[0].group,"actual later commit retains both causal defaults");
    check(result[1].group_end,"actual commit retires the complete source chain");
}
void paused_capture(){
    int submissions=0;H::NativeEditorEndpoint endpoint;
    endpoint.submit=[&](E::Packet)->std::optional<std::uint64_t>{++submissions;return 1;};
    endpoint.revoke=[](E::Revocation)->std::optional<std::uint64_t>{return 2;};endpoint.take=[](std::uint64_t)->std::optional<E::EditorCompletion>{return {};};endpoint.resync=[]{};
    endpoint.terminal.notify=+[](void*)noexcept{};
    H::NativeEditorCapture collector(std::move(endpoint));
    const S::Identity identity{{"native",1},1,1,1,1};
    E::EditorPublication publication;publication.basis=E::Basis{1,identity,1,"ab",{1,1},false,0};
    check(collector.install(publication,identity),"paused fixture checked publication");
    H::FltkNativeFrontend frontend;frontend.install(text("ab",1,1),false);
    collector.pause();check(collector.paused(),"actual collector is inertly paused");
    auto values=frontend.observe({key(),{edit(H::FltkNativeEditKind::text,"x",1,1)}});
    for(auto& value:values)check(collector.observe_paused(std::move(value)).has_value(),"same collector owns actual paused native passage");
    check(collector.pending()==2&&collector.draft()&&*collector.draft()==*frontend.draft(),"one bounded collector and frontend keep exact provisional value");
    collector.tick();check(submissions==0,"paused native callbacks cannot submit provider work");
    check(collector.resume(*publication.basis),"only exact checked basis resumes");
    collector.tick();check(submissions==1,"resumed owner phase sends one original head");
    collector.tick();check(submissions==1,"resumed head is never replayed");
}
void capture(){
    int submissions=0;H::NativeEditorEndpoint endpoint;
    endpoint.submit=[&](E::Packet)->std::optional<std::uint64_t>{++submissions;return 1;};
    endpoint.revoke=[](E::Revocation)->std::optional<std::uint64_t>{return 2;};endpoint.take=[](std::uint64_t)->std::optional<E::EditorCompletion>{return {};};endpoint.resync=[]{};
    endpoint.terminal.notify=+[](void*)noexcept{};
    H::NativeEditorCapture collector(std::move(endpoint));
    const S::Identity identity{{"native",1},1,1,1,1};
    E::EditorPublication publication;publication.basis=E::Basis{1,identity,1,"ab",{1,1},false,0};
    check(collector.install(publication,identity),"real generic Capture accepts checked publication");
    H::FltkNativeFrontend frontend;frontend.install(text("ab",1,1),false);
    auto values=frontend.observe({key(),{edit(H::FltkNativeEditKind::text,"x",1,1)}});
    for(auto& value:values)check(collector.observe(std::move(value)).has_value(),"real Capture accepts actual grouped native value");
    check(submissions==0&&collector.pending()==2,"ingress never enters endpoint");
    collector.tick();check(submissions==1,"normal owner phase submits once");collector.tick();check(submissions==1,"pending native head never replayed");
}
}
int main(int argc,char** argv){try{
    const std::string which=argc==2?argv[1]:"all";
    const std::pair<const char*,void(*)()> cases[]={{"mouse",mouse},{"viewport",viewport},{"keys",keys},{"committed",committed},{"independent",independent},{"preedit",preedit},{"cancelled",cancelled},{"selection",selection},{"dead-keys",dead_keys},{"capture",capture},{"paused-capture",paused_capture}};
    unsigned ran=0;for(auto [name,run]:cases)if(which=="all"||which==name){run();++ran;}
    if(!ran)throw std::runtime_error("Unknown FLTK surface fixture");
    std::cout<<"native-fltk-surface cases="<<ran<<" checks="<<checks<<" failed=0 skipped=0\n";
}catch(const std::exception& error){std::cerr<<"FAIL: "<<error.what()<<'\n';return 1;}}
