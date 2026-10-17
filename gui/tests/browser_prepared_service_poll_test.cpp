// SPDX-License-Identifier: CC0-1.0
// Source-only neutral fixture; authored but not compiled or executed here.
#include "host/browser_surface_composition.hpp"
#include <stdexcept>

namespace {
using namespace foundation;
using Json=gui::web_detail::Json;
void check(bool value,const char* message){if(!value)throw std::runtime_error(message);}
struct State { bool ready=false,started=false,offered=false;unsigned queries=0,inputs=0,completions=0; };
State* selected=nullptr;
class PreparedServiceApp {
    host::BrowserSurfaceAdapter& adapter_;
    State& state_;
public:
    explicit PreparedServiceApp(gui::Adapter& adapter)
        :adapter_(dynamic_cast<host::BrowserSurfaceAdapter&>(adapter)),state_(*selected) {
        gui::Snapshot snapshot;snapshot.revision=1;snapshot.client_size={100,100};
        gui::Widget button;button.spec.key={"generic.button",1};button.spec.kind=gui::Kind::button;
        button.state.bounds={0,0,100,100};snapshot.widgets.push_back(std::move(button));adapter_.present(std::move(snapshot));
    }
    void handle(gui::Event){++state_.inputs;}
    void tick(){}
    void shutdown(){adapter_.close();}
    void retry_presentation(){}
    void qualify(const std::function<void()>& present){if(present)present();}
    std::optional<gui::ServiceRequest> next_service(){
        ++state_.queries;
        if(!state_.started){state_.started=true;adapter_.set_owned_service_active(true);}
        if(!state_.ready||state_.offered)return{};
        state_.offered=true;return gui::ServiceRequest{71,gui::ServiceKind::prompt,"Prepared",{},64};
    }
    bool complete_service(gui::ServiceResult result){
        if(result.id!=71)return false;
        ++state_.completions;adapter_.set_owned_service_active(false);return true;
    }
};
void scenario(bool opt_in){
    State state;selected=&state;
    host::Browser<PreparedServiceApp,host::BrowserSurfaceComposition> browser("prepared",
        host::BrowserSurfaceComposition(0,host::surface_web::Profile::legacy,{},{},false,opt_in));
    (void)browser.initial();check(state.started&&!browser.session.pending_service(),"Preparation was not separate from dispatch");
    const auto before=state.queries;state.ready=true;
    const auto poll=gui::web_detail::encode(Json::Object{{"epoch","prepared"},{"seq","1"},{"operation",Json::Object{{"type","poll"}}}});
    (void)browser.receive(poll);
    check(bool(browser.session.pending_service())==opt_in,"Prepared polling opt-in/default changed");
    check(opt_in ? state.queries>before : state.queries==before,"Owned query gate ignored its explicit policy");
    const auto click=gui::web_detail::encode(Json::Object{{"epoch","prepared"},{"seq","2"},{"operation",Json::Object{
        {"type","activate"},{"key",gui::web_detail::key({"generic.button",1})}}}});
    (void)browser.receive(click);check(state.inputs==0,"Prepared service polling reopened ordinary input");
    if(opt_in)check(browser.session.complete_host_service({71,gui::ServiceStatus::cancelled,{},{}})&&state.completions==1,"Prepared completion did not keep its normal guarded path");
    const auto queries=state.queries;browser.adapter.close();
    try{(void)browser.initial();}catch(const std::exception&){}
    check(state.queries==queries,"Closed owner still queried prepared service work");
}
}
int main(){scenario(false);scenario(true);}
