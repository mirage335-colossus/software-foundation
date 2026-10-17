// SPDX-License-Identifier: CC0-1.0
#include "host/fltk_runner.hpp"
#include <algorithm>
#include <array>
#include <chrono>
#include <iostream>
#include <stdexcept>
#include <string_view>
#include <utility>
#include <vector>

// Exercise the actual FLTK runner helper with owned fake scheduling values.
// No native window/platform, engine, SDK or display is constructed.
namespace {
using foundation::host::RunnerState;
namespace Runner=foundation::host::fltk_runner_detail;
using Time=std::chrono::steady_clock::time_point;
using Milliseconds=std::chrono::milliseconds;
std::size_t assertions{};
void check(bool value,const char* reason) {++assertions;if(!value)throw std::runtime_error(reason);}
struct InjectedFailure final:std::runtime_error {
    int token;
    explicit InjectedFailure(int value):std::runtime_error("original runner fixture failure"),token(value) {}
};
struct Trace {
    bool callback{},destructing{},renderer_alive{},endpoint_alive{},application_alive{};
    bool renderer_destroyed{},endpoint_destroyed{},application_destroyed{},lifetime_violation{};
    bool never_complete{},complete_on_shutdown{},throw_poll{},throw_tick{};
    int exit_on_shutdown{};
    Milliseconds shutdown_elapsed{};
    Time* clock{};
    unsigned ticks{},healthy_ticks{},drain_ticks{},shutdowns{},takes{},completed_takes{};
    unsigned ticks_at_app_destruction{},ticks_at_endpoint_destruction{},ticks_at_renderer_destruction{};
    unsigned fail_at_drain{};
    int failure_code{19};
    std::vector<std::string_view> order;
};
struct Renderer {
    Trace& trace;
    explicit Renderer(Trace& value):trace(value) {trace.renderer_alive=true;}
    ~Renderer() {
        trace.lifetime_violation|=trace.application_alive||trace.endpoint_alive||trace.callback;
        trace.renderer_alive=false;trace.renderer_destroyed=true;trace.ticks_at_renderer_destruction=trace.ticks;
    }
};
struct Endpoint {
    Trace& trace;
    explicit Endpoint(Trace& value):trace(value) {trace.endpoint_alive=true;}
    bool take() {
        check(trace.renderer_alive&&trace.endpoint_alive&&trace.application_alive&&!trace.callback&&!trace.destructing,
              "metadata take ran after dependency destruction or inside a native callback");
        ++trace.takes;trace.order.push_back("take");
        const bool completed=!trace.never_complete&&trace.drain_ticks>=3;
        if(completed)++trace.completed_takes;
        return completed;
    }
    ~Endpoint() {
        trace.lifetime_violation|=trace.application_alive||!trace.renderer_alive||trace.callback;
        trace.endpoint_alive=false;trace.endpoint_destroyed=true;trace.ticks_at_endpoint_destruction=trace.ticks;
    }
};
struct Adapter {
    bool requested{};
    bool closed() const {return requested;}
};
struct App {
    Trace& trace;
    Adapter& adapter;
    RunnerState state;
    explicit App(Trace& value,Adapter& native):trace(value),adapter(native) {trace.application_alive=true;}
    void shutdown() {
        check(!trace.callback&&!trace.destructing&&trace.renderer_alive&&trace.endpoint_alive,
              "shutdown recursively entered a native callback or outlived the endpoint");
        ++trace.shutdowns;trace.order.push_back("shutdown");state.close_requested=true;
        adapter.requested=true; // Requested native closure deliberately precedes settlement.
        if(trace.clock)*trace.clock+=trace.shutdown_elapsed;
        if(trace.exit_on_shutdown)state.exit_code=trace.exit_on_shutdown;
        if(trace.complete_on_shutdown)state.close_complete=true;
    }
    ~App() {
        trace.lifetime_violation|=!trace.renderer_alive||!trace.endpoint_alive||trace.callback;
        trace.application_alive=false;trace.application_destroyed=true;trace.ticks_at_app_destruction=trace.ticks;
    }
};
struct Session {
    Trace& trace;
    Renderer renderer;
    Endpoint endpoint;
    Adapter adapter;
    App application;
    explicit Session(Trace& value):trace(value),renderer(value),endpoint(value),application(value,adapter) {}
    ~Session() {trace.destructing=true;}
    RunnerState runner_state() const {return application.state;}
    void tick() {
        check(!trace.callback&&!trace.destructing&&trace.renderer_alive&&trace.endpoint_alive&&trace.application_alive,
              "runner tick occurred inside callback/destructor or after renderer/endpoint destruction");
        check(trace.ticks<20000,"runner advanced without a bounded clock wait");
        ++trace.ticks;trace.order.push_back("tick");
        if(trace.throw_tick)throw InjectedFailure(71);
        if(!application.state.close_requested) {++trace.healthy_ticks;return;}
        ++trace.drain_ticks;
        if(trace.fail_at_drain&&trace.drain_ticks==trace.fail_at_drain) {
            application.state.exit_code=trace.failure_code;return;
        }
        // The third ordinary close tick obtains the mock's delayed metadata.
        // No runner callback/destructor, synthetic ACK or forced completion exists.
        if(endpoint.take())application.state.close_complete=true;
    }
};
struct Host {
    Session& session;
    Trace& trace;
    Time time{};
    enum class Action {request,adapter_close,none};
    Action action{Action::request};
    unsigned close_at_poll{1},polls{},waits{};
    unsigned healthy_at_request{},ticks_at_request{};
    std::vector<int> timeouts;
    explicit Host(Session& value):session(value),trace(value.trace) {trace.clock=&time;}
    Time now() const {return time;}
    void poll() {
        check(!trace.callback&&!trace.destructing,"native poll reentered itself or a destructor");
        check(!trace.shutdowns&&!session.application.state.close_requested,
              "runner admitted fresh native input during close drain");
        ++polls;trace.order.push_back("poll");
        if(trace.throw_poll)throw InjectedFailure(83);
        const auto before=trace.ticks;const auto shutdowns=trace.shutdowns;
        trace.callback=true;
        if(polls==close_at_poll&&action!=Action::none) {
            healthy_at_request=trace.healthy_ticks;ticks_at_request=trace.ticks;
            trace.order.push_back("request");
            if(action==Action::request)session.application.state.close_requested=true;
            else session.adapter.requested=true;
        }
        trace.callback=false;
        check(trace.ticks==before&&trace.shutdowns==shutdowns,
              "native callback synchronously ticked or shut down the application");
    }
    void wait(int milliseconds) {
        check(!trace.callback&&!trace.destructing,"native wait recursively entered lifecycle work");
        check(milliseconds>=1&&milliseconds<=20,"native wait exceeded 1..20ms or busy-looped");
        check(waits<10001,"unresolved close exceeded the bounded clock budget");
        ++waits;timeouts.push_back(milliseconds);trace.order.push_back("wait");time+=Milliseconds(milliseconds);
    }
};
template<class Function> void scenario(Trace& trace,Function operation) {
    unsigned returned_ticks{};
    {
        Session session(trace);Host host(session);
        operation(session,host);
        returned_ticks=trace.ticks;
        check(trace.renderer_alive&&trace.endpoint_alive&&trace.application_alive,
              "runner destroyed its renderer/endpoint/application before returning");
    }
    check(trace.application_destroyed&&trace.endpoint_destroyed&&trace.renderer_destroyed,
          "fixture dependencies did not reach normal destruction");
    check(!trace.lifetime_violation,"application/endpoint destructor lost a live dependency");
    check(trace.ticks==returned_ticks&&trace.ticks_at_app_destruction==returned_ticks&&
          trace.ticks_at_endpoint_destruction==returned_ticks&&trace.ticks_at_renderer_destruction==returned_ticks,
          "destruction advanced lifecycle work instead of using ordinary drain ticks");
}
void requested_close_drains_with_live_dependencies() {
    for(const bool already_closed:{false,true}) {
        Trace trace;scenario(trace,[&](Session& session,Host& host) {
            session.application.state.close_requested=!already_closed;session.adapter.requested=already_closed;
            check(Runner::run(session,host)==0,"requested/adapter close failed to complete");
            check(trace.shutdowns==1&&trace.drain_ticks==3&&trace.healthy_ticks==0,
                  "requested close skipped the three ordinary drain ticks or repeated shutdown");
            check(host.polls==0&&host.waits==2,"runner polled new input or skipped bounded drain yields");
            check(trace.takes==3&&trace.completed_takes==1&&session.application.state.close_complete,
                  "adapter.closed was treated as completion before delayed metadata take");
            check(session.adapter.closed(),"fixture did not expose early adapter closure");
        });
    }
}
void normal_work_then_poll_request() {
    for(const auto action:{Host::Action::request,Host::Action::adapter_close}) {
        Trace trace;scenario(trace,[&](Session& session,Host& host) {
            host.action=action;host.close_at_poll=2;
            check(Runner::run(session,host)==0,"native poll request failed to drain");
            check(host.polls==2&&host.healthy_at_request>=1&&trace.shutdowns==1,
                  "healthy loop shut down before an actual close request or repolled during drain");
            check(trace.healthy_ticks==host.healthy_at_request&&trace.ticks==host.ticks_at_request+3,
                  "poll close request admitted normal work before shutdown/drain");
            const auto request=std::find(trace.order.begin(),trace.order.end(),"request");
            check(request!=trace.order.end()&&request+1!=trace.order.end()&&*(request+1)=="shutdown",
                  "close raised in poll was not queued before advancing another tick");
            check(trace.drain_ticks==3&&trace.completed_takes==1,"poll close lost delayed endpoint metadata");
        });
    }
}
void immediate_failure_preserves_code_without_work() {
    for(const bool complete:{false,true}) {
        Trace trace;scenario(trace,[&](Session& session,Host& host) {
            session.application.state={true,complete,37,{}};
            check(Runner::run(session,host)==37,"initial terminal result code was rewritten or lost to completion");
            check(!trace.ticks&&!trace.shutdowns&&!trace.takes&&!host.polls&&!host.waits,
                  "initial nonzero result entered close work or native input");
            check(session.application.state.close_complete==complete,"terminal result changed actual close completion");
        });
    }
}
void failure_during_drain_stops_further_work() {
    Trace trace;trace.fail_at_drain=2;trace.failure_code=23;
    scenario(trace,[&](Session& session,Host& host) {
        session.application.state.close_requested=true;
        check(Runner::run(session,host)==23,"drain terminal result code was rewritten");
        check(trace.shutdowns==1&&trace.drain_ticks==2&&trace.ticks==2&&host.polls==0&&host.waits==1,
              "terminal drain failure performed another tick/poll/wait or skipped shutdown");
        check(trace.takes==1&&!trace.completed_takes&&!session.application.state.close_complete,
              "failure forged a final metadata receipt or successful closure");
    });
}
void true_completion_does_no_new_work() {
    for(const bool adapter_closed:{false,true}) {
        Trace trace;scenario(trace,[&](Session& session,Host& host) {
            session.application.state={true,true,0,{}};session.adapter.requested=adapter_closed;
            check(Runner::run(session,host)==0,"actual completed state did not finish");
            check(!trace.ticks&&!trace.shutdowns&&!trace.takes&&!host.polls&&!host.waits,
                  "completed state repeated shutdown, native input or application work");
        });
    }
}
void incomplete_close_has_actual_ten_second_cap() {
    Trace trace;trace.never_complete=true;
    scenario(trace,[&](Session& session,Host& host) {
        session.application.state.close_requested=true;
        check(Runner::run(session,host)==1,"unresolved closure falsely succeeded");
        check(trace.shutdowns==1&&host.polls==0&&trace.healthy_ticks==0&&trace.drain_ticks>1,
              "deadline cap repeated shutdown, native input or normal work");
        check(!session.application.state.close_complete&&!trace.completed_takes&&trace.takes==trace.drain_ticks,
              "ten-second cap fabricated metadata, ACK or close completion");
        check(host.time>=Time{}+std::chrono::seconds(10)&&host.time<Time{}+std::chrono::seconds(10)+Milliseconds(20),
              "close cap did not use the actual host clock's ten-second bound");
        check(host.waits>1&&!session.application.state.deadline,"fixture did not exercise fallback without an App deadline");
    });
}
void shutdown_result_and_elapsed_clock_are_observed() {
    for(const bool complete:{false,true}) {
        Trace trace;trace.complete_on_shutdown=complete;trace.exit_on_shutdown=complete?0:41;
        scenario(trace,[&](Session& session,Host& host) {
            session.adapter.requested=true;
            check(Runner::run(session,host)==(complete?0:41),"synchronous shutdown result was not reread");
            check(trace.shutdowns==1&&!trace.ticks&&!trace.takes&&!host.polls&&!host.waits,
                  "shutdown completion/failure entered another owner tick or native wait");
            check(session.application.state.close_complete==complete,"shutdown result fabricated or lost completion");
        });
    }
    Trace trace;trace.shutdown_elapsed=std::chrono::seconds(10);
    scenario(trace,[&](Session& session,Host& host) {
        session.application.state.close_requested=true;
        check(Runner::run(session,host)==1,"shutdown time incorrectly restarted the ten-second budget");
        check(trace.shutdowns==1&&!trace.ticks&&!trace.takes&&!host.polls&&!host.waits,
              "expired shutdown budget entered an additional tick/poll/wait");
        check(host.time==Time{}+std::chrono::seconds(10)&&!session.application.state.close_complete,
              "elapsed shutdown budget fabricated completion or did not use the actual host clock");
    });
}
void deadline_values_are_bounded_and_not_busy() {
    const Time now{};
    check(Runner::wait_timeout({},now)==20,"ordinary FLTK wait quantum changed");
    RunnerState state;state.deadline=now+Milliseconds(7);
    check(Runner::wait_timeout(state,now)==7,"earlier App deadline was ignored");
    check(Runner::wait_timeout(state,now,now+Milliseconds(2))==2,"earlier close deadline was ignored");
    state.deadline=now+std::chrono::microseconds(500);
    check(Runner::wait_timeout(state,now)==1,"submillisecond deadline selected a zero-time busy loop");
    state.deadline=now-std::chrono::seconds(1);
    check(Runner::wait_timeout(state,now)==1,"expired App deadline selected a zero-time busy loop");
    check(Runner::wait_timeout({},now,now-std::chrono::seconds(1))==1,"expired close deadline selected a busy loop");
    state.deadline=now+std::chrono::hours(48);
    check(Runner::wait_timeout(state,now)==20,"remote App deadline exceeded the native quantum");
    check(Runner::wait_timeout(state,now,now+Milliseconds(3))==3,"close scheduling lost to a remote App deadline");
}
void exceptions_preserve_original_failure_without_more_work() {
    for(const bool in_poll:{false,true}) {
        Trace trace;trace.throw_poll=in_poll;trace.throw_tick=!in_poll;
        scenario(trace,[&](Session& session,Host& host) {
            host.action=Host::Action::none;
            bool propagated=false;
            try {(void)Runner::run(session,host);}
            catch(const InjectedFailure& error) {propagated=error.token==(in_poll?83:71);}
            check(propagated,"runner swallowed or replaced the original poll/tick exception");
            check(host.polls==1&&trace.ticks==(in_poll?0u:1u)&&!host.waits&&!trace.shutdowns&&!trace.takes,
                  "exception performed later owner/native/close work");
            check(!session.application.state.close_requested&&!session.application.state.close_complete,
                  "exception fabricated a close request or successful completion");
        });
    }
}
void ordinary_loop_honors_app_deadline() {
    Trace trace;scenario(trace,[&](Session& session,Host& host) {
        session.application.state.deadline=host.now()+Milliseconds(7);host.close_at_poll=2;
        check(Runner::run(session,host)==0,"scheduled ordinary loop failed to close");
        check(!host.timeouts.empty()&&host.timeouts.front()==7,"ordinary loop did not schedule the actual App deadline");
        check(trace.shutdowns==1&&trace.drain_ticks==3&&trace.completed_takes==1,
              "App deadline bypassed normal close settlement");
        for(const auto timeout:host.timeouts)check(timeout>=1&&timeout<=20,"deadline scheduling stopped yielding bounded waits");
    });
}
}
int main() {
    try {
        using Test=std::pair<std::string_view,void(*)()>;
        const std::array<Test,10> tests{{
            {"requested close keeps renderer and metadata endpoint alive",requested_close_drains_with_live_dependencies},
            {"healthy work and close raised inside native poll",normal_work_then_poll_request},
            {"initial nonzero result enters no work",immediate_failure_preserves_code_without_work},
            {"nonzero result during drain stops immediately",failure_during_drain_stops_further_work},
            {"actual completed closure enters no work",true_completion_does_no_new_work},
            {"incomplete close has a real ten-second cap",incomplete_close_has_actual_ten_second_cap},
            {"shutdown boundary preserves result and clock",shutdown_result_and_elapsed_clock_are_observed},
            {"deadline values remain bounded",deadline_values_are_bounded_and_not_busy},
            {"original poll and tick exceptions propagate",exceptions_preserve_original_failure_without_more_work},
            {"ordinary loop uses App scheduling deadline",ordinary_loop_honors_app_deadline}}};
        for(const auto& [name,test]:tests) {test();std::cout<<"PASS "<<name<<'\n';}
        std::cout<<tests.size()<<" FLTK surface runner groups, "<<assertions<<" assertions passed; no display/OS/engine qualification\n";
    } catch(const std::exception& error) {
        std::cerr<<"FAIL FLTK surface runner after "<<assertions<<" assertions: "<<error.what()<<'\n';return 1;
    }
}
