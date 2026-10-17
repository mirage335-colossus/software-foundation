// SPDX-License-Identifier: CC0-1.0
#include "host/native_surface_composition.hpp"
#include "host/native_session.hpp"
#include <gui/retained_adapter.hpp>
#include <atomic>
#include <iostream>
#include <stdexcept>
#include <type_traits>
#include <vector>

namespace {
namespace H=foundation::host;
namespace S=foundation::gui_surface;
std::size_t checks{},groups{};
void check(bool v,const char* why){++checks;if(!v)throw std::runtime_error(why);}
struct Backend:gui::RetainedAdapter {
    gui::EventSink events;
    explicit Backend(gui::EventSink sink):gui::RetainedAdapter(sink),events(std::move(sink)) {
        if(events)events(gui::CloseEvent{}); // Constructor callback must be inert.
    }
    void emit(gui::Event e){if(events)events(e);}
    std::optional<int> prompt()const{return {};}
    template<class Reply>void service(gui::ServiceRequest,Reply){}
};
struct BasicApp {
    gui::Adapter& adapter;unsigned handled{},ticks{},stops{};
    explicit BasicApp(gui::Adapter& value):adapter(value){}
    void handle(gui::Event){++handled;}
    void tick(){++ticks;}
    void shutdown()noexcept{++stops;}
    void retry_presentation(){}
    std::optional<gui::ServiceRequest>next_service(){return {};}
    bool complete_service(gui::ServiceResult){return false;}
    void qualify(const std::function<void()>& f){if(f)f();}
};
// This regression uses the unchanged default implementation, not a Surface
// instrumented substitute. Its exact specialization remains the original one.
static_assert(std::is_same_v<H::NativeSession<BasicApp,Backend>,H::Session<BasicApp,Backend,H::FileServices>>);
void default_session_regression() {
    H::NativeSession<BasicApp,Backend> session;
    check(session.application.handled==0,"default constructor callback reached an incomplete App");
    session.adapter.emit(gui::CloseEvent{});check(session.application.handled==1,"default concrete Adapter callback changed");
    session.tick();check(session.application.ticks==1,"default normal tick changed");
    check(session.runner_state().close_complete==false,"default runner state changed");
}
struct Observations {
    H::NativeSurfaceIngress ingress;
    H::NativeSurfacePublisher saved;
    std::vector<std::string> order;
    unsigned handles{},shutdowns{},destroyed{},renders{},peer_closes{},extent{},foreground{};
    bool ready{},throw_constructor{},throw_connected{};
};
struct FactoryApp {
    gui::Adapter& adapter;Observations& seen;
    FactoryApp(H::NativeSurfaceAdapter& value,Observations& record):adapter(value),seen(record) {
        check(seen.ready,"App was constructed before actual renderer ready");seen.order.push_back("app");
        seen.ingress.legacy(gui::CloseEvent{});check(seen.handles==0,"App construction callback gate armed early");
        seen.saved=value.publisher();
        gui::Snapshot snapshot;snapshot.revision=1;snapshot.title="initial actual render";value.present(std::move(snapshot));
        if(seen.throw_constructor)throw std::runtime_error("App constructor fault");
    }
    ~FactoryApp(){seen.ingress.legacy(gui::CloseEvent{});++seen.destroyed;}
    void handle(gui::Event){++seen.handles;}
    void tick(){seen.order.push_back("tick");}
    void shutdown()noexcept{seen.ingress.legacy(gui::CloseEvent{});++seen.shutdowns;}
    void retry_presentation(){}
    std::optional<gui::ServiceRequest>next_service(){return {};}
    bool complete_service(gui::ServiceResult){return false;}
    void qualify(const std::function<void()>& f){if(f)f();}
    void drawable_pixels(std::int64_t width,std::int64_t height){check(width==80&&height==60,"actual drawable extent was replaced by window seed");++seen.extent;}
    void foreground(bool value){check(value,"unexpected foreground fact");++seen.foreground;}
    void surface_connected(S::Capabilities){if(seen.throw_connected)throw std::runtime_error("connected fault");}
    void surface_input(S::AcceptedEvent){}
    void surface_revoked(S::Revocation){}
};
static_assert(!H::Application<FactoryApp> && H::NativeSurfaceApplication<FactoryApp>);
H::NativeSurfaceSessionFactory<FactoryApp> factory(Observations& seen) {
    H::NativeSurfaceSessionFactory<FactoryApp> result;result.mode=H::NativeSurfaceMode::none;
    result.window={"neutral title",800,600,1};
    result.application=[&](H::NativeSurfaceAdapter& proxy){return std::make_unique<FactoryApp>(proxy,seen);};
    result.prepare_peer=[&](gui::Adapter& backend,const H::NativeSurfaceWindow& window,H::NativeSurfaceIngress ingress) {
        check(window.title=="neutral title","window seed changed");seen.order.push_back("peer");seen.ingress=std::move(ingress);
        seen.ingress.legacy(gui::CloseEvent{});check(seen.handles==0,"peer setup callback gate armed early");seen.ready=true;
        H::NativeSurfacePeer peer;peer.ready=[&]{return seen.ready;};
        peer.present=[&,target=&backend](gui::Snapshot snapshot){const auto rev=snapshot.revision;target->present(std::move(snapshot));++seen.renders;return H::NativeRenderReceipt{rev};};
        peer.activate=[&]{seen.ingress.drawable_pixels(80,60);seen.ingress.foreground(true);};
        peer.close=[&]{++seen.peer_closes;};return peer;
    };
    return result;
}
void staged_factory_and_expired_callbacks() {
    Observations seen;
    {
        H::NativeSurfaceSession<FactoryApp,Backend> session(factory(seen));
        check(seen.order==std::vector<std::string>{"peer","app"} && seen.renders==1,"staged construction order or actual initial publication changed");
        check(seen.extent==1&&seen.foreground==1,"actual startup facts were not emitted after arming");
        check(!session.surface().input_admitted() && session.surface().capabilities().supported==0,"read-only session advertised input authority");
        session.adapter.emit(gui::CloseEvent{});check(seen.handles==1,"armed legacy lifecycle callback was lost");
        session.tick();check(seen.order.back()=="tick","normal owner session tick did not reach App");
        session.shutdown();session.shutdown();check(seen.shutdowns==1&&seen.handles==1,"shutdown gate reentered App or repeated shutdown");
        check(!seen.saved.set_owned_service_active(true),"retained weak publisher remained live after shutdown");
        seen.ingress.legacy(gui::CloseEvent{});check(seen.handles==1,"disarmed ingress reached App");
    }
    check(seen.destroyed==1&&seen.handles==1&&seen.peer_closes==1,"App destruction callback or peer lifetime was unsafe");
    const auto renders=seen.renders;gui::Snapshot value;value.revision=2;
    check(seen.saved.present_pair(std::move(value),{}).status==S::Status::closed&&seen.renders==renders,"expired root publisher touched dead renderer");
    check(!seen.ingress.input(S::FocusChange{}).accepted,"expired native callback retained input authority");
}
void constructor_unwind_and_generation_exhaustion() {
    for(bool connected:{false,true}) {
        Observations seen;seen.throw_constructor=!connected;seen.throw_connected=connected;
        bool caught=false;try{H::NativeSurfaceSession<FactoryApp,Backend> session(factory(seen));}catch(const std::runtime_error&){caught=true;}
        check(caught&&seen.handles==0,"construction unwind delivered a callback into App");
        seen.ingress.legacy(gui::CloseEvent{});check(seen.handles==0,"unwound callback gate survived");
        check(!seen.saved.set_owned_service_active(true),"constructor unwind kept publication handle alive");
    }
    std::atomic<std::uint64_t> counter{UINT64_MAX};
    check(H::native_surface_detail::next_generation(counter)==UINT64_MAX,"last generation identity lost");
    check(H::native_surface_detail::next_generation(counter)==0&&counter.load()==0,"generation exhaustion wrapped");
    gui::Snapshot empty;empty.revision=9;empty.title="safe blank";
    auto blank=H::prepare_native_blank_canvas(empty,{"configured",800,600,2});
    check(blank.revision==9 && blank.title=="safe blank" && blank.client_size.width==800 && blank.client_size.height==600 && blank.display_scale==2,"strict empty view did not clear actual configured canvas");
    empty.commands.push_back({{"one",1},false,{}});
    auto populated=H::prepare_native_blank_canvas(empty,{"configured",800,600,2});
    check(populated.client_size.width==empty.client_size.width && populated.display_scale==empty.display_scale,"populated view geometry was rewritten");
}
}
int main(){try{for(const auto& test:{default_session_regression,staged_factory_and_expired_callbacks,constructor_unwind_and_generation_exhaustion}){test();++groups;}
    std::cout<<groups<<" groups, "<<checks<<" checks, 0 skipped\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<" after "<<groups<<" groups / "<<checks<<" checks\n";return 1;}}
