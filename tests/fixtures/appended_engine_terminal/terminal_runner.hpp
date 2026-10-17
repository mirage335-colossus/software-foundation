// TEST ONLY: terminal/TTY boundary, using real GUI types and real main wrapper.
#pragma once
#include "state.hpp"
#include <thread>
namespace foundation::host {
template<Application App> int run_terminal(int argc,char** argv){
    namespace t=terminal_main_fixture;auto& s=t::state;++s.runner;t::event("runner");
    t::require(argc==1&&argv&&argv[0]==s.argv0,"composition leaked root CLI to ordinary runner");
    if(t::is("tty-failure"))throw std::runtime_error("synthetic TTY failure");
    if(t::is("tty-nonstd"))throw 17;
    if(t::is("tty-return-failure"))return 1;
    t::Adapter adapter;App app(adapter);
    static_assert(RunnerApplication<App>);
    if(t::is("runner-hooks")){
        const auto before=s.driver_ticks;app.drawable_cells(81,0);app.foreground(false);app.handle(gui::CloseEvent{});
        app.retry_presentation();bool presented{};app.qualify([&]{presented=true;});
        t::require(presented&&!app.next_service()&&!app.complete_service({}),"wrapper changed generic service/qualification routing");
        t::require(s.driver_ticks==before&&s.facade_ticks==0,"callback hook synchronously entered Driver");
        std::thread wake([&]{s.facade_wake();});wake.join();
        const auto awake=app.runner_state();t::require(awake.deadline&&*awake.deadline<=std::chrono::steady_clock::now(),"wake did not request later owner turn");
        t::require(s.driver_ticks==before&&s.facade_ticks==0,"worker wake pumped application");app.tick();
        const auto quiet=app.runner_state();t::require(quiet.deadline&&*quiet.deadline>std::chrono::steady_clock::now(),"wrapper did not clear wake after tick");
        auto* native=static_cast<appended::NativeEngineDriver*>(s.bound_driver);
        t::require(native->wake.context&&native->wake.post_owner_wake,"main omitted actual Driver wake");
        const auto before_native=s.driver_ticks;
        std::thread native_wake([&]{native->wake.post_owner_wake(native->wake.context);});native_wake.join();
        const auto native_awake=app.runner_state();
        t::require(native_awake.deadline&&*native_awake.deadline<=std::chrono::steady_clock::now()&&s.driver_ticks==before_native,"actual Driver wake did not queue a pure owner turn");
        app.tick();
    }
    auto* driver=static_cast<appended::NativeEngineDriver*>(s.bound_driver);
    if(t::is("runner-terminal")||t::is("runner-blocked")){
        driver->state(t::is("runner-terminal")?appended::NativeEngineState::process_exit_required:appended::NativeEngineState::blocked);
        const auto status=app.runner_state();t::require(status.close_requested&&!status.close_complete&&status.exit_code==1,"terminal state fabricated complete successful close");return status.exit_code;
    }
    app.shutdown();const auto closing=app.runner_state();
    t::require(closing.close_requested&&!closing.close_complete&&closing.deadline&&*closing.deadline<=std::chrono::steady_clock::now()+std::chrono::seconds(10),"wrapper lost close intent/budget");
    if(t::is("unfinished-close")){s.expire_close();return 0;}
    app.tick();const auto done=app.runner_state();
    if(t::is("close-terminal")||t::is("close-blocked"))return 1;
    t::require(done.close_complete&&done.exit_code==0,"detached native driver did not complete close");return 0;
}
}
