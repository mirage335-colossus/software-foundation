// SPDX-License-Identifier: CC0-1.0
#include "terminal_runner.hpp"
#include <array>
#include <iostream>
#include <stdexcept>
#include <vector>

// Actual generated runner, shared Session and retained TerminalAdapter, with
// fake native scheduling/clock values. No engine, SDK, TTY or provider is used.
namespace {
using namespace foundation::host;
using Time = std::chrono::steady_clock::time_point;
using Size = std::optional<std::pair<unsigned,unsigned>>;
std::size_t assertions{};
void check(bool value,const char* reason) {++assertions;if(!value)throw std::runtime_error(reason);}
struct Trace {
    bool callback{},alive{},destroyed{},adapter_closed_before_destruction{},resize_before_facts{},foreground_before_key{};
    bool foreground{}; unsigned ticks{},entries{},shutdowns{},close_events{},drain_ticks{},close_after{3};
    bool close_adapter{true},never_complete{};
    std::vector<std::pair<std::int64_t,std::int64_t>> cells;
    std::vector<bool> foregrounds;
    std::vector<std::string> order;
};
Trace* constructing{};
class Legacy {
protected:
    gui::Adapter& adapter_;
public:
    explicit Legacy(gui::Adapter& adapter):adapter_(adapter) {
        gui::Snapshot view;view.title="Runner fixture";view.revision=1;view.client_size={640,480};adapter_.present(std::move(view));
    }
    void handle(gui::Event) {}
    void tick() {}
    void shutdown() {}
    void retry_presentation() {}
    std::optional<gui::ServiceRequest> next_service() {return {};}
    bool complete_service(gui::ServiceResult) {return false;}
    void qualify(const std::function<void()>& present) {if(present)present();}
};
class App:public Legacy {
public:
    Trace& trace;
    RunnerState state;
    explicit App(gui::Adapter& adapter):Legacy(adapter),trace(*constructing) {trace.alive=true;}
    ~App() {trace.adapter_closed_before_destruction=adapter_.closed();trace.alive=false;trace.destroyed=true;}
    void handle(gui::Event event) {
        check(trace.alive,"callback outlived its application");
        if(std::holds_alternative<gui::ResizeEvent>(event)) {
            trace.order.push_back("resize");
            if(trace.cells.empty()||trace.foregrounds.empty())trace.resize_before_facts=true;
        }
        if(std::holds_alternative<gui::CloseEvent>(event)) {++trace.close_events;state.close_requested=true;}
    }
    void drawable_cells(std::int64_t columns,std::int64_t rows) {
        trace.cells.emplace_back(columns,rows);trace.order.push_back("cells");
    }
    void foreground(bool value) {trace.foreground=value;trace.foregrounds.push_back(value);trace.order.push_back("foreground");}
    RunnerState runner_state() const {return state;}
    void shutdown() {++trace.shutdowns;state.close_requested=true;}
    void tick() {
        check(!trace.callback,"lifecycle/input callback synchronously pumped an application tick");
        ++trace.ticks;
        if(state.close_requested) {
            ++trace.drain_ticks;
            if(trace.close_adapter)adapter_.close();
            if(!trace.never_complete&&trace.drain_ticks>=trace.close_after)state.close_complete=true;
        } else if(trace.foreground&&!trace.cells.empty()&&trace.cells.back().first&&trace.cells.back().second)++trace.entries;
    }
    bool closed() const {return state.close_requested;} // Intentionally true before close is complete.
};
struct WrongState:Legacy {using Legacy::Legacy;int runner_state() const {return 0;}};
struct WrongMutableState:Legacy {using Legacy::Legacy;RunnerState runner_state() {return {};}};
struct WrongCells:Legacy {using Legacy::Legacy;int drawable_cells(std::int64_t,std::int64_t) {return 0;}};
struct WrongForeground:Legacy {using Legacy::Legacy;bool foreground(bool) {return false;}};
static_assert(Application<Legacy> && !RunnerApplication<Legacy>);
static_assert(RunnerApplication<App> && !RunnerApplication<WrongState>);
static_assert(runner_detail::StateCandidate<WrongState> && !runner_detail::StateHook<WrongState>);
static_assert(runner_detail::StateCandidate<WrongMutableState> && !runner_detail::StateHook<WrongMutableState> &&
              !RunnerApplication<WrongMutableState>);
static_assert(runner_detail::CellsCandidate<WrongCells> && !runner_detail::CellsHook<WrongCells>);
static_assert(runner_detail::ForegroundCandidate<WrongForeground> && !runner_detail::ForegroundHook<WrongForeground>);

struct Host {
    App& app;
    Trace& trace;
    Time time{};
    std::vector<Size> sizes{std::pair{80u,24u}};
    unsigned reads{},waits{},stop_after{1};
    enum class Close {signal,event,adapter,none} close{Close::event};
    bool active{true},stop{},flip_focus{};
    std::vector<int> timeouts;
    explicit Host(App& value):app(value),trace(value.trace) {}
    Time now() const {return time;}
    Size measured_size() const {return sizes[std::min<std::size_t>(reads,sizes.size()-1)];}
    bool foreground() const {return active;}
    bool stopped() const {return stop;}
    void draw(const std::vector<std::string>& rows) {check(!rows.empty(),"actual retained terminal adapter rendered no rows");}
    void poll(gui::TerminalAdapter& adapter,int timeout,const std::function<void(bool)>& foreground) {
        check(timeout>=1&&timeout<=30,"runner selected an unbounded or busy poll");
        timeouts.push_back(timeout);time+=std::chrono::milliseconds(timeout);++reads;
        const auto before=trace.ticks;trace.callback=true;
        if(flip_focus&&reads==1) {
            active=false;foreground(false);
            trace.foreground_before_key=!trace.foreground;
            check(trace.ticks==before,"native foreground callback pumped work before the next native key");
        }
        if(reads==stop_after) {
            if(close==Close::signal)stop=true;
            else if(close==Close::event)adapter.key(gui::Key::quit);
            else if(close==Close::adapter)adapter.close();
        }
        trace.callback=false;
        check(trace.ticks==before,"native input callback recursively advanced application work");
    }
    void wait(int timeout) {
        check(timeout>=1&&timeout<=30,"close drain did not yield within the bounded native quantum");
        ++waits;timeouts.push_back(timeout);time+=std::chrono::milliseconds(timeout);
    }
};
template<class F> void scenario(Trace& trace,F action) {
    constructing=&trace;
    {Session<App,gui::TerminalAdapter> session;Host host(session.application);action(session,host);}
    check(trace.destroyed&&!trace.alive,"Session did not destroy its application while dependencies remained valid");
    check(trace.adapter_closed_before_destruction,"Session destroyed application before closing its still-live adapter");
    constructing=nullptr;
}
void legacy_contract_and_lifetime() {
    Session<Legacy,gui::TerminalAdapter> session;
    session.drawable_cells(0,0);session.foreground(false);
    auto state=session.runner_state();
    check(!state.close_requested&&!state.close_complete&&!state.exit_code&&!state.deadline,
          "legacy opt-out synthesized lifecycle or application-specific work");
    session.adapter.close();state=session.runner_state();
    check(state.close_requested&&state.close_complete&&!state.exit_code,
          "legacy fallback did not preserve immediate adapter closure");
    char name[]="runner-fixture",help[]="--help";char* args[]{name,help};
    check(run_terminal<Legacy>(2,args)==0,"public opt-out runner failed its side-effect-free help path");
    Trace trace;scenario(trace,[&](auto& owned,Host& host) {
        check(terminal_runner_detail::run(owned,host)==0,"ordinary close did not finish");
        check(trace.close_events==1&&trace.shutdowns==1&&trace.drain_ticks==3&&host.reads==1&&host.waits==2,
              "CloseEvent/closed adapter skipped normal close ticks or repeated input/shutdown");
        check(owned.application.closed()&&owned.application.state.close_complete,
              "requested-close flag was confused with completed closure");
    });
}
void measured_cells_and_fact_order() {
    Trace trace;scenario(trace,[&](auto& session,Host& host) {
        host.sizes={std::pair{80u,24u},std::pair{1u,1u},std::pair{900u,900u},{},std::pair{40u,6u}};
        host.stop_after=5;check(terminal_runner_detail::run(session,host)==0,"geometry scenario failed to close");
        const std::vector<std::pair<std::int64_t,std::int64_t>> expected{{80,23},{1,0},{500,199},{0,0},{40,5}};
        check(trace.cells==expected,"actual cells used a logical minimum, invented a drawable row or included final-row chrome");
        check(!trace.resize_before_facts,"synchronous minimum-canvas ResizeEvent preceded authoritative lifecycle facts");
        check(trace.entries==3,"invalid/unavailable geometry admitted work or valid physical dimensions were lost");
    });
}
void foreground_before_same_batch_key() {
    Trace trace;scenario(trace,[&](auto& session,Host& host) {
        host.flip_focus=true;
        check(terminal_runner_detail::run(session,host)==0&&trace.foreground_before_key,
              "native foreground loss did not gate a later key in the same batch");
        check(trace.foregrounds==std::vector<bool>{true,false},"foreground state was invented/restored during close or repeatedly dispatched");
        check(trace.entries==1,"background/closing owner admitted new application work");
    });
}
void signal_and_adapter_close() {
    for(const auto reason:{Host::Close::signal,Host::Close::adapter}) {
        Trace trace;scenario(trace,[&](auto& session,Host& host) {
            host.close=reason;
            check(terminal_runner_detail::run(session,host)==0,"native stop/adapter closure bypassed orderly close");
            check(trace.shutdowns==1&&trace.drain_ticks==3&&host.reads==1,
                  "native close did not queue shutdown once and drain after adapter closure");
            check(trace.close_events==0,"native stop invented another input command while closing");
        });
    }
}
void terminal_failure_is_not_completion() {
    Trace trace;scenario(trace,[&](auto& session,Host& host) {
        session.application.state={true,false,7,{}};
        check(terminal_runner_detail::run(session,host)==7&&trace.ticks==0&&host.reads==0&&host.waits==0,
              "terminal failure entered work or waited as though cleanup were possible");
        check(!session.application.state.close_complete&&trace.shutdowns==0,
              "terminal failure was converted into synthetic successful closure");
    });
}
void close_drain_has_a_hard_cap() {
    Trace trace;trace.never_complete=true;scenario(trace,[&](auto& session,Host& host) {
        host.close=Host::Close::signal;
        check(terminal_runner_detail::run(session,host)==1,"unresolved close falsely succeeded");
        check(!session.application.state.close_complete&&trace.shutdowns==1&&host.reads==1&&trace.entries==1,
              "timed-out close fabricated completion, replayed input or admitted new work");
        check(host.time>=Time{}+std::chrono::seconds(10)&&host.time<Time{}+std::chrono::seconds(10)+std::chrono::milliseconds(60),
              "close drain was unbounded or bypassed its actual clock deadline");
        check(trace.drain_ticks>1&&host.waits>1,"close deadline fixture did not actually drain normal bounded ticks");
    });
}
void deadlines_bound_the_next_native_wait() {
    const Time now{};
    check(terminal_runner_detail::wait_timeout({},now)==30,"ordinary native wait budget changed");
    RunnerState state;state.deadline=now+std::chrono::milliseconds(7);
    check(terminal_runner_detail::wait_timeout(state,now)==7,"earlier application deadline was not scheduled");
    check(terminal_runner_detail::wait_timeout(state,now,now+std::chrono::milliseconds(2))==2,
          "close deadline did not precede application deadline");
    state.deadline=now-std::chrono::seconds(1);
    check(terminal_runner_detail::wait_timeout(state,now)==1,"expired producer deadline selected an unbounded busy loop");
    Trace trace;scenario(trace,[&](auto& session,Host& host) {
        session.application.state.deadline=now+std::chrono::milliseconds(7);
        check(terminal_runner_detail::run(session,host)==0&&host.timeouts.front()==7,
              "real opt-in loop ignored its value-only scheduling deadline");
    });
}
}
int main() {
    try {
        using Test = std::pair<std::string_view,void(*)()>;
        const std::array<Test,7> tests{{{"legacy contract and Session lifetime",legacy_contract_and_lifetime},
            {"measured cells and fact ordering",measured_cells_and_fact_order},
            {"foreground before same-batch key",foreground_before_same_batch_key},
            {"signal and adapter close",signal_and_adapter_close},
            {"terminal failure is not completion",terminal_failure_is_not_completion},
            {"bounded close drain",close_drain_has_a_hard_cap},
            {"deadline scheduling",deadlines_bound_the_next_native_wait}}};
        for(const auto& [name,test]:tests) {test();std::cout<<"PASS "<<name<<'\n';}
        std::cout<<tests.size()<<" terminal runner groups, "<<assertions<<" assertions passed\n";
    } catch(const std::exception& error) {std::cerr<<"Terminal runner failure after "<<assertions<<" assertions: "<<error.what()<<'\n';return 1;}
}
