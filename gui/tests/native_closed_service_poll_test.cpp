// SPDX-License-Identifier: CC0-1.0
// Source-only neutral fixture. No engine, native window or file worker runs.
#include "host/native_surface_composition.hpp"
#include <gui/retained_adapter.hpp>
#include <functional>
#include <optional>
#include <stdexcept>
#include <utility>

namespace {
namespace H=foundation::host;
void check(bool value,const char* message){if(!value)throw std::runtime_error(message);}
struct State {
    unsigned offers{},queries{},polls{},completions{},stops{},ticks{};
    bool active{},closing{};
    std::optional<gui::ServiceResult> result;
    std::function<void(gui::ServiceResult)> callback;
};
State* selected=nullptr;
struct Backend:gui::RetainedAdapter {
    explicit Backend(gui::EventSink sink):gui::RetainedAdapter(std::move(sink)){}
    std::optional<int> prompt()const{return{};}
};
struct Services {
    State& state=*selected;
    template<class Adapter,class Reply>void service(Adapter&,gui::ServiceRequest request,Reply reply){
        check(request.id==71,"Unknown neutral request");++state.offers;state.active=true;state.callback=std::move(reply);
    }
    bool active()const noexcept{return state.active;}
    std::optional<gui::ServiceResult> poll(){
        ++state.polls;
        if(!state.result)return{};
        state.active=false;
        return std::exchange(state.result,{});
    }
    void shutdown(){++state.stops;state.active=false;}
};
struct App {
    gui::Adapter& adapter;State& state;
    App(H::NativeSurfaceAdapter& target,State& seen):adapter(target),state(seen){}
    void handle(gui::Event){}
    void tick(){++state.ticks;}
    void shutdown()noexcept{state.closing=true;adapter.close();}
    void retry_presentation(){}
    void qualify(const std::function<void()>& present){if(present)present();}
    std::optional<gui::ServiceRequest> next_service(){
        ++state.queries;if(state.closing||state.offers)return{};
        return gui::ServiceRequest{71,gui::ServiceKind::prompt,"Owned",{},64};
    }
    bool complete_service(gui::ServiceResult value){
        if(value.id!=71||!state.offers||state.completions)return false;
        ++state.completions;return true;
    }
    H::RunnerState runner_state()const{return{state.closing,state.closing&&state.completions==1,0,{}};}
};
H::NativeSurfaceSessionFactory<App> factory(State& state){
    H::NativeSurfaceSessionFactory<App> value;
    value.mode=H::NativeSurfaceMode::none;
    value.application=[&](H::NativeSurfaceAdapter& adapter){return std::make_unique<App>(adapter,state);};
    value.prepare_peer=[](gui::Adapter& adapter,const H::NativeSurfaceWindow&,H::NativeSurfaceIngress){
        H::NativeSurfacePeer peer;peer.ready=[]{return true;};
        peer.present=[&adapter](gui::Snapshot snapshot){const auto revision=snapshot.revision;adapter.present(std::move(snapshot));return H::NativeRenderReceipt{revision};};
        peer.close=[&adapter]{adapter.close();};return peer;
    };return value;
}
void polled_close_debt(){
    State state;selected=&state;
    {
        H::NativeSurfaceSession<App,Backend,Services> session(factory(state));
        session.tick();check(state.offers==1&&state.active,"Service was not genuinely offered");
        session.application.shutdown();const auto queries=state.queries;
        check(session.adapter.closed()&&!session.runner_state().close_complete,"Closed backend fabricated service completion");
        session.tick();check(state.stops==0&&state.completions==0,"Backend closure stopped unresolved active work");
        state.result=gui::ServiceResult{71,gui::ServiceStatus::success,"known",{}};
        session.tick();check(state.completions==1&&session.runner_state().close_complete,"Matching polled metadata did not drain after close");
        check(state.queries==queries&&state.offers==1,"Closed session offered successor work");
        session.shutdown();check(state.stops==1,"Session teardown did not stop Services");
    }
    state.callback({71,gui::ServiceStatus::success,"late",{}});
    check(state.completions==1,"Expired callback reached destroyed App");
}
}
int main(){polled_close_debt();}
