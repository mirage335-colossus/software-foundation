// SPDX-License-Identifier: CC0-1.0
#include "host/browser_surface.hpp"
#include "host/browser_surface_composition.hpp"
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
using namespace foundation;
using host::BrowserSurfaceAdapter;
using host::BrowserSurfaceSession;
using Json=host::surface_web::Json;
namespace {
void check(bool value,const char* message){if(!value)throw std::runtime_error(message);}
template<class F>void throws(F&& operation,const char* message){try{operation();}catch(const std::exception&){return;}throw std::runtime_error(message);}
gui::Snapshot snapshot(std::uint64_t revision=1){
    gui::Snapshot value;value.revision=revision;value.client_size={100,100};
    gui::Widget widget;widget.spec.key={"surface",1};widget.spec.kind=gui::Kind::button;widget.state.bounds={0,0,100,100};
    value.widgets.push_back(widget);return value;
}
gui_surface::Presentation surface(std::uint64_t revision=1,std::uint64_t context=1){
    gui_surface::Presentation value;value.identity={{"surface",1},revision,7,1,context};
    value.required=host::surface_web::basic_supported;value.bounds={0,0,100,100};value.clip=value.bounds;
    value.keys.fallback=gui_surface::Capture::capture;return value;
}
Json parse(const std::string& value){return gui::web_detail::Parser(value).parse();}
Json send(BrowserSurfaceSession& session,std::uint64_t sequence,Json operation){return parse(session.receive(gui::web_detail::encode(Json::Object{{"epoch","epoch"},{"seq",std::to_string(sequence)},{"operation",std::move(operation)}})));}
Json input(const gui_surface::Presentation& p,std::uint64_t sequence,Json value){return Json::Object{{"type","surfaceInput"},{"identity",host::surface_web::json_presentation(p).at("identity")},{"sequence",std::to_string(sequence)},{"input",std::move(value)}};}
Json focus(bool value=true){return Json::Object{{"kind","focus"},{"focused",value},{"active",true},{"cause","direct"}};}
Json key(){return Json::Object{{"kind","key"},{"phase","down"},{"key","F5"},{"code","F5"},{"location",0},{"modifiers",0},{"repeat",false}};}
void connect(BrowserSurfaceSession& session,const char* supported="97"){
    const auto response=send(session,1,Json::Object{{"type","surfaceConnect"},{"version",1},{"supported",supported}});
    check(response.at("error").str().empty(),"Connection rejected");
}
void basic_and_callbacks(){
    std::vector<gui_surface::AcceptedEvent> work;int legacy=0,connected=0;BrowserSurfaceAdapter* owner=nullptr;BrowserSurfaceSession* live=nullptr;
    BrowserSurfaceAdapter adapter(7,[&](const gui::Event&){++legacy;});owner=&adapter;
    BrowserSurfaceSession session(adapter,"epoch",[&](gui_surface::AcceptedEvent event){
        work.push_back(std::move(event));
        check(owner->accept({surface().identity,90,gui_surface::FocusChange{true,true,{}}}).status==gui_surface::Status::busy,"Input reentered its sink");
        throws([&]{live->receive("{}");},"Session reentered its sink");
        const auto result=owner->present_pair(snapshot(2),surface(2));
        check(result.status==gui_surface::Status::ok,"Normal handle could not publish");
    },[&](const gui_surface::Capabilities& value){++connected;check(value.supported==97,"Wrong intersection");});live=&session;
    check(adapter.capabilities().supported==0,"Capabilities before physical acceptance");
    check(adapter.present_pair(snapshot(),surface()).status==gui_surface::Status::unsupported,"Published before physical acceptance");
    const auto initial=parse(session.initial());check(std::holds_alternative<std::nullptr_t>(initial.at("surface").value),"Initial surface not absent");
    connect(session);check(connected==1&&adapter.capabilities().supported==97,"Connection not accepted");
    check(adapter.present_pair(snapshot(),surface()).status==gui_surface::Status::ok,"Pair publication failed");
    const auto response=send(session,2,input(surface(),1,focus()));
    check(work.size()==1&&legacy==0,"Typed input reached wrong sink");
    check(response.at("snapshot").at("revision").str()=="2"&&response.at("surface").at("presentation").at("identity").at("presentationRevision").str()=="2","Publication pair split");
    check(adapter.surface_focused(),"Focus lost on same-context publication");
    const auto stale=send(session,3,input(surface(),2,key()));check(!stale.at("error").str().empty()&&work.size()==1,"Stale event rebased");
}
void legacy_revisions_and_close(){
    int actions=0;BrowserSurfaceAdapter* live=nullptr;
    BrowserSurfaceAdapter adapter(7,[&](const gui::Event& event){if(std::holds_alternative<gui::CloseEvent>(event))live->close();else ++actions;});live=&adapter;
    BrowserSurfaceSession session(adapter,"epoch");connect(session);
    check(adapter.present_pair(snapshot(5),surface(5)).status==gui_surface::Status::ok,"Initial pair");
    adapter.present(snapshot(0));check(!adapter.accepted()&&adapter.capabilities().supported==0,"Zero legacy revision retained companion");
    adapter.present(snapshot(3));adapter.present(snapshot(1));
    auto response=send(session,2,Json::Object{{"type","activate"},{"key",gui::web_detail::key({"surface",1})}});
    check(actions==1&&response.at("snapshot").at("revision").str()=="1","Legacy revision compatibility changed");
    response=send(session,3,Json::Object{{"type","close"}});
    check(adapter.closed()&&response.at("snapshot").at("closed").boolean(),"Ordinary close callback rejected");
}
void serialization_failure_and_reentrancy(){
    int actions=0,attempts=0;BrowserSurfaceAdapter adapter(7,[&](const gui::Event&){++actions;});BrowserSurfaceSession session(adapter,"epoch");connect(session);
    check(adapter.present_pair(snapshot(),surface()).status==gui_surface::Status::ok,"Initial pair");
    auto value=snapshot(2);value.widgets[0].spec.key={"pixels",1};value.widgets[0].spec.kind=gui::Kind::bitmap;
    value.widgets[0].state.bitmap={"frame",1,gui::BitmapSource([&](const gui::BitmapRequest&,const gui::BitmapSink&){
        ++attempts;
        check(adapter.accept({surface().identity,20,gui_surface::FocusChange{true,true,{}}}).status==gui_surface::Status::busy,"Reentrant typed input admitted");
        throws([&]{adapter.focus(gui::WidgetKey{"surface",1});},"Reentrant legacy focus admitted");
        throws([&]{adapter.close();},"Reentrant close admitted");
        throws([&]{session.receive("{}");},"Reentrant receive admitted");
        throw std::runtime_error("paint failed");
    })};
    auto next=surface(2,2);next.identity.owner={"pixels",1};
    throws([&]{adapter.present_pair(value,next);},"Serialization failure missing");
    check(attempts==1&&adapter.failed()&&adapter.closed()&&!adapter.accepted()&&adapter.capabilities().supported==0,"Uncertain publication retained authority");
    throws([&]{session.receive("{}");},"Failed session received legacy input");
    check(!session.complete_host_service({1,gui::ServiceStatus::success,{},{}})&&!session.pending_service(),"Failed session completed native service");
    check(actions==0,"Legacy input after failure");
}
void service_lifecycle(){
    bool offer=false;int queried=0,completed=0,revoked=0;std::vector<gui_surface::AcceptedEvent> events;BrowserSurfaceSession* live=nullptr;
    BrowserSurfaceAdapter adapter(7,{},[&](gui_surface::Revocation value){revoked+=int(value.held_keys.size());});
    BrowserSurfaceSession session(adapter,"epoch",[&](gui_surface::AcceptedEvent event){events.push_back(std::move(event));},{},
        [&]()->std::optional<gui::ServiceRequest>{++queried;throws([&]{live->receive("{}");},"Service acquisition reentered input");if(!offer)return{};offer=false;return gui::ServiceRequest{8,gui::ServiceKind::prompt,"Prompt",{},64};},
        [&](gui::ServiceResult){++completed;throws([&]{live->receive("{}");},"Native completion reentered input");return true;});live=&session;
    connect(session);check(adapter.present_pair(snapshot(),surface()).status==gui_surface::Status::ok,"Service pair");
    (void)send(session,2,input(surface(),1,focus()));(void)send(session,3,input(surface(),2,key()));check(events.size()==2,"Key setup failed");
    check(!session.complete_host_service({99,gui::ServiceStatus::cancelled,{},{}})&&revoked==0,"Stale native completion revoked current interaction");
    offer=true;auto response=send(session,4,Json::Object{{"type","poll"}});
    check(revoked==1&&response.at("surface").at("serviceActive").boolean()&&session.pending_service(),"Service did not suspend/revoke first");
    (void)send(session,5,input(surface(),4,key()));check(events.size()==2,"Modal service leaked input");
    check(session.complete_host_service({8,gui::ServiceStatus::cancelled,{},{}})&&completed==1,"Native service completion failed");
    response=parse(session.initial());check(!response.at("surface").at("serviceActive").boolean(),"Service suspension persisted");
    const int before=queried;
    throws([&]{send(session,6,Json::Object{{"type","surfaceUnknown"}});},"Unknown reserved operation survived");
    check(adapter.failed()&&queried==before,"Failure called application service query");
}
void pointer_ownership(){
    int retired=0;BrowserSurfaceAdapter adapter(7,{},[&](gui_surface::Revocation value){if(value.identity)++retired;});BrowserSurfaceSession session(adapter,"epoch");connect(session);
    check(adapter.present_pair(snapshot(),surface()).status==gui_surface::Status::ok,"Pointer pair");
    auto pointer=gui_surface::PointerTransition{};pointer.phase=gui_surface::PointerPhase::up;pointer.pointer=1;
    check(adapter.accept({surface().identity,1,pointer}).status==gui_surface::Status::stale_identity,"Unowned release admitted");
    pointer.phase=gui_surface::PointerPhase::down;
    check(adapter.accept({surface().identity,1,pointer}).status==gui_surface::Status::ok,"Pointer press rejected");
    check(adapter.accept({surface().identity,2,pointer}).status==gui_surface::Status::stale_identity,"Pointer token reused");
    pointer.phase=gui_surface::PointerPhase::move;pointer.pointer=2;
    check(adapter.accept({surface().identity,2,pointer}).status==gui_surface::Status::stale_identity,"Foreign captured movement admitted");
    pointer.phase=gui_surface::PointerPhase::up;pointer.pointer=1;
    check(adapter.accept({surface().identity,2,pointer}).status==gui_surface::Status::ok,"Owned release rejected");
    pointer.phase=gui_surface::PointerPhase::down;pointer.pointer=2;
    check(adapter.accept({surface().identity,3,pointer}).status==gui_surface::Status::ok,"Fresh token rejected");
    adapter.present(snapshot(2));check(retired==1,"Pointer-only legacy retirement was hidden by empty key revocation");
}
void failed_connection_terminal(){
    int queries=0;BrowserSurfaceAdapter adapter(7);
    BrowserSurfaceSession session(adapter,"epoch",{},[&](const gui_surface::Capabilities&){
        auto value=snapshot();value.widgets[0].spec.kind=gui::Kind::bitmap;
        value.widgets[0].state.bitmap={"broken",1,gui::BitmapSource([](const gui::BitmapRequest&,const gui::BitmapSink&){throw std::runtime_error("paint failed");})};
        (void)adapter.present_pair(value,surface());
    },[&]()->std::optional<gui::ServiceRequest>{++queries;return gui::ServiceRequest{1,gui::ServiceKind::prompt,"Must not run",{},64};});
    const auto response=send(session,1,Json::Object{{"type","surfaceConnect"},{"version",1},{"supported","97"}});
    check(adapter.failed()&&queries==0,"Failed extension response invoked service callback");
    check(response.at("snapshot").at("closed").boolean()&&std::holds_alternative<std::nullptr_t>(response.at("surface").value),"Repeated failure erased inert fallback");
    check(std::holds_alternative<std::nullptr_t>(response.at("service").value)&&std::holds_alternative<std::nullptr_t>(response.at("transfer").value),"Terminal response retained service authority");
}
void malformed_and_zero_subset(){
    int queries=0,retired=0;bool offer=false;
    BrowserSurfaceAdapter adapter(7,{},[&](gui_surface::Revocation value){if(value.identity)++retired;});
    BrowserSurfaceSession session(adapter,"epoch",{},{},[&]()->std::optional<gui::ServiceRequest>{++queries;if(!offer)return{};offer=false;return gui::ServiceRequest{3,gui::ServiceKind::prompt,"Pointer-only service",{},64};});
    connect(session,"64");auto p=surface();p.required=64;p.keys.fallback=gui_surface::Capture::pass;
    check(adapter.present_pair(snapshot(),p).status==gui_surface::Status::ok,"Pointer-only pairing failed");
    offer=true;const auto modal=parse(session.initial());
    check(!adapter.failed()&&modal.at("surface").at("serviceActive").boolean()&&retired==1,"Optional focus was required for pointer-only service retirement");
    const auto before=queries;
    auto invalid=input(p,1,focus());std::get<Json::Object>(invalid.value).emplace("forged",true);
    throws([&]{send(session,2,std::move(invalid));},"Malformed reserved operation survived");
    check(adapter.failed()&&queries==before,"Malformed input performed service work");
}
void owned_service_and_profiles(){
    int revoked=0;std::size_t held=0;BrowserSurfaceAdapter* live=nullptr;
    BrowserSurfaceAdapter adapter(7,{},[&](gui_surface::Revocation value){
        if(value.identity)++revoked;
        held+=value.held_keys.size();
        check(live->accept({surface().identity,90,gui_surface::FocusChange{true,true,{}}}).status==gui_surface::Status::busy,"Native service callback admitted nested input");
        throws([&]{live->set_owned_service_active(false);},"Native service callback could clear its outer suspension");
    });live=&adapter;
    BrowserSurfaceSession session(adapter,"epoch");connect(session);
    check(adapter.generation()==7,"Native generation accessor changed");
    check(adapter.present_pair(snapshot(),surface()).status==gui_surface::Status::ok,"Owned service pair");
    (void)send(session,2,input(surface(),1,focus()));(void)send(session,3,input(surface(),2,key()));
    adapter.set_owned_service_active(true);check(revoked==1&&held==1,"Native service did not revoke held keys first");
    auto state=parse(session.initial());check(state.at("surface").at("serviceActive").boolean()&&std::holds_alternative<std::nullptr_t>(state.at("service").value),"Native service needs no legacy descriptor");
    check(!session.pending_service()&&parse(session.initial()).at("surface").at("serviceActive").boolean(),"Legacy false publication cleared native suspension");
    check(adapter.accept({surface().identity,3,gui_surface::FocusChange{true,true,{}}}).status==gui_surface::Status::unavailable,"Native service admitted input");
    const bool focused=adapter.surface_focused();adapter.set_owned_service_active(false);
    check(adapter.surface_focused()==focused&&!parse(session.initial()).at("surface").at("serviceActive").boolean(),"Ending service manufactured focus authority");
    throws([&]{BrowserSurfaceAdapter invalid(7,{},{},8192);},"Mouse ceiling silently opted legacy into successor");
    throws([&]{BrowserSurfaceAdapter invalid(7,{},{},64,host::surface_web::Profile::mouse_v1);},"Successor silently advertised old raw pointer");
}
void mouse_profile_and_service_retirement(){
    using host::surface_web::Profile;
    int revoked=0;BrowserSurfaceAdapter adapter(7,{},[&](gui_surface::Revocation value){if(value.identity)++revoked;},8192,Profile::mouse_v1);
    BrowserSurfaceSession session(adapter,"epoch");
    auto response=send(session,1,Json::Object{{"type","surfaceConnect"},{"version",1},{"supported","8192"},{"mouseInputVersion",1}});
    check(response.at("surface").at("capabilities").at("mouseInputVersion").number()==1,"Successor marker not published");
    auto p=surface();p.required=8192;p.keys={};
    check(adapter.present_pair(snapshot(),p).status==gui_surface::Status::ok,"Mouse-only pair rejected");
    gui_surface::MouseTransition down;down.phase=gui_surface::MousePhase::down;down.capture_token=9007199254740993ull;down.buttons=1;
    check(!adapter.surface_focused(),"Mouse-only setup manufactured Focus authority");
    check(adapter.accept({p.identity,1,down}).status==gui_surface::Status::ok,"Fresh mouse-only press rejected without Focus capability or lost token precision");
    gui_surface::MouseTransition cancel;cancel.phase=gui_surface::MousePhase::cancel;cancel.capture_token=down.capture_token;
    check(adapter.accept({p.identity,2,cancel}).status==gui_surface::Status::ok,"Canonical mouse-only blur cancellation rejected without Focus capability");
    check(adapter.accept({p.identity,3,down}).status!=gui_surface::Status::ok,"Blur cancellation allowed its retired mouse token to resurrect");
    down.capture_token++;check(adapter.accept({p.identity,3,down}).status==gui_surface::Status::ok,"Fresh mouse-only press after blur cancellation rejected");
    adapter.set_owned_service_active(true);check(revoked==1&&!adapter.accepted(),"Mouse-only service did not retire capture/presentation");
    adapter.set_owned_service_active(false);check(!adapter.accepted(),"Service end restored mouse presentation");
    p.identity.presentation_revision=2;p.identity.context=2;
    check(adapter.present_pair(snapshot(2),p).status==gui_surface::Status::ok,"Fresh mouse pair after service");
    check(adapter.accept({p.identity,4,down}).status!=gui_surface::Status::ok,"Service allowed an old mouse token to resurrect");
    down.capture_token++;check(adapter.accept({p.identity,4,down}).status==gui_surface::Status::ok,"Fresh post-service mouse token rejected");
    check(!adapter.failed(),"Mouse profile failed during trusted service retirement");
}
struct CallbackApp {
    BrowserSurfaceAdapter& adapter;
    std::function<void()> on_tick;
    bool in_tick=false,throw_notification=false;
    int notifications=0;std::size_t revoked_keys=0;
    explicit CallbackApp(gui::Adapter& target):adapter(dynamic_cast<BrowserSurfaceAdapter&>(target)){adapter.present(snapshot());}
    void handle(const gui::Event&){}
    void tick(){struct Scope{bool& flag;explicit Scope(bool& value):flag(value){flag=true;}~Scope(){flag=false;}}scope(in_tick);if(on_tick)on_tick();}
    void shutdown(){}
    void retry_presentation(){}
    std::optional<gui::ServiceRequest> next_service(){return{};}
    bool complete_service(gui::ServiceResult){return false;}
    void qualify(std::function<void()> present){present();}
    void surface_revoked(gui_surface::Revocation value){
        check(!in_tick,"Owned retirement notification reentered App.tick");++notifications;revoked_keys+=value.held_keys.size();
        throws([&]{adapter.set_owned_service_active(true);},"Retirement notification reentered native ownership");
        if(throw_notification)throw std::runtime_error("notification failure");
    }
};
void deferred_native_retirement(){
    for(const auto mode: {"pulse","throw","close","close-throw","overflow","notification"}){
        host::Browser<CallbackApp,host::BrowserSurfaceComposition> browser("epoch",host::BrowserSurfaceComposition(97));
        connect(browser.session);auto p=surface();p.identity.generation=browser.adapter.generation();
        check(browser.adapter.present_pair(snapshot(),p).status==gui_surface::Status::ok,"Actual App callback pair");
        (void)send(browser.session,2,input(p,1,focus()));(void)send(browser.session,3,input(p,2,key()));
        auto& app=browser.app();app.throw_notification=std::string_view(mode)=="notification";
        app.on_tick=[&]{
            browser.adapter.set_owned_service_active(true);
            check(!browser.adapter.accepted()&&app.notifications==0,"Native gate/context not retired before callback return");
            if(std::string_view(mode)=="throw")throw std::runtime_error("tick failure");
            if(std::string_view(mode)=="close"){browser.adapter.close();return;}
            if(std::string_view(mode)=="close-throw"){browser.adapter.close();throw std::runtime_error("closed tick failure");}
            browser.adapter.set_owned_service_active(false);
            if(std::string_view(mode)=="overflow"){
                auto next=p;next.identity.context=2;next.identity.presentation_revision=2;
                check(browser.adapter.present_pair(snapshot(2),next).status==gui_surface::Status::ok,"New context staged inside callback");
                browser.adapter.set_owned_service_active(true);
            }
        };
        const auto response=parse(browser.receive(gui::web_detail::encode(Json::Object{{"epoch","epoch"},{"seq","4"},{"operation",Json::Object{{"type","poll"}}}})));
        if(std::string_view(mode)=="close-throw")check(response.at("snapshot").at("closed").boolean(),"Unwinding a closed callback erased terminal publication");
        check(std::holds_alternative<std::nullptr_t>(response.at("surface").value)||std::holds_alternative<std::nullptr_t>(response.at("surface").at("presentation").value),"Coalesced native service pulse retained old companion authority");
        if(std::string_view(mode)=="pulse"){
            check(!browser.adapter.failed()&&app.notifications==1&&app.revoked_keys==1,"Deferred App retirement not delivered after guard exit");
            check(!browser.adapter.accepted(),"Native false pulse restored old presentation");
            check(browser.adapter.present_pair(snapshot(),p).status!=gui_surface::Status::ok,"Retired native context resurrected");
            p.identity.presentation_revision=2;p.identity.context=2;
            check(browser.adapter.present_pair(snapshot(2),p).status==gui_surface::Status::ok,"Fresh native context publication failed");
        }else if(std::string_view(mode)=="close")check(browser.adapter.closed()&&app.notifications==0,"Close delivered a late App retirement callback");
        else check(browser.adapter.failed()&&app.notifications==(std::string_view(mode)=="notification"?1:0),"Callback uncertainty did not fail closed");
    }
}
}
int main(){try{basic_and_callbacks();legacy_revisions_and_close();serialization_failure_and_reentrancy();service_lifecycle();pointer_ownership();failed_connection_terminal();malformed_and_zero_subset();owned_service_and_profiles();mouse_profile_and_service_retirement();deferred_native_retirement();std::cout<<"browser surface: ten groups passed\n";return 0;}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
