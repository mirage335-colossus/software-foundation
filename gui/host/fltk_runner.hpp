#pragma once
#include "host/native_session.hpp"
#include "host/qualification.hpp"
#include "adapter.hpp"
#include "host/native_fltk_surface_peer.hpp"
#include <iostream>
#include <chrono>
#include <thread>

namespace foundation::host {
template<Application App> int run_fltk(int argc, char** argv) {
    try {
        const bool smoke = smoke_requested(argc, argv);
        if (argc != 1 && !smoke) throw std::invalid_argument("Usage: foundation-gui-fltk [--smoke-test|--self-check]");
        NativeSession<App, gui::fltk::Adapter> session;
        if (smoke) {
            session.adapter.show();
            session.application.qualify([&] {
                session.tick(); Fl::check(); Fl::flush();
                if (!session.adapter.error().empty()) throw std::runtime_error(session.adapter.error());
            });
            session.adapter.window().make_current();
            const std::unique_ptr<unsigned char[]> pixels(fl_read_image(nullptr, 0, 0,
                session.adapter.window().w(), session.adapter.window().h()));
            if (!pixels) throw std::runtime_error("Native capture failed");
            return finish_smoke(session.application, session.adapter);
        }
        struct Timer {
            decltype(session)& owner;
            std::exception_ptr failure;
            static void tick(void* data) {
                auto& self = *static_cast<Timer*>(data);
                try {
                    if (self.owner.adapter.closed()) return;
                    self.owner.tick(); Fl::repeat_timeout(.02, tick, data);
                } catch (...) { self.failure = std::current_exception(); self.owner.adapter.close(); }
            }
            ~Timer() { Fl::remove_timeout(tick, this); }
        } timer{session, {}};
        session.adapter.show(); Fl::add_timeout(0, Timer::tick, &timer);
        while (!session.adapter.closed()) Fl::wait(.02);
        if (timer.failure) std::rethrow_exception(timer.failure);
        if (!session.adapter.error().empty()) throw std::runtime_error(session.adapter.error());
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
    return 0;
}

// Explicit generic raw-surface composition. Staging installs the renderer and
// native event/IME peer before the supplied factory can construct its App.
#if defined(_WIN32) || defined(__linux__)
namespace fltk_runner_detail {
using Clock=std::chrono::steady_clock;
inline Clock::time_point close_deadline(Clock::time_point now) {
    constexpr auto budget=std::chrono::seconds(10);
    return now>Clock::time_point::max()-budget?Clock::time_point::max():now+budget;
}
inline int wait_timeout(const RunnerState& state,Clock::time_point now,
                        std::optional<Clock::time_point> close_limit={}) {
    constexpr auto quantum=std::chrono::milliseconds(20);
    auto until=now>Clock::time_point::max()-quantum?Clock::time_point::max():now+quantum;
    if(state.deadline)until=std::min(until,*state.deadline);
    if(close_limit)until=std::min(until,*close_limit);
    // A due value schedules an ordinary owner turn after a bounded yield. It
    // cannot establish completion or cause a recursive callback/busy loop.
    if(until<=now)return 1;
    return static_cast<int>(std::clamp<std::int64_t>(
        std::chrono::ceil<std::chrono::milliseconds>(until-now).count(),1,20));
}
// The toolkit only collects values in callbacks. The caller's real renderer,
// Session and Surface endpoint stay alive throughout this ordinary owner pump.
template<class Session,class Host> int run(Session& session,Host& host) {
    bool closing=false;
    std::optional<Clock::time_point> close_limit;
    for(;;) {
        auto state=session.runner_state();
        if(state.exit_code)return state.exit_code;
        if(state.close_complete)return state.exit_code;
        auto now=host.now();
        if(!closing&&(state.close_requested||session.adapter.closed())) {
            closing=true;close_limit=close_deadline(now);
            // Signal only; never disarm/destroy Session or invent an ACK here.
            session.application.shutdown();
            state=session.runner_state();
            if(state.exit_code)return state.exit_code;
            if(state.close_complete)return state.exit_code;
        }
        now=host.now();
        if(closing&&now>=*close_limit)return 1;
        if(!closing) {
            host.poll();
            state=session.runner_state();
            if(state.exit_code)return state.exit_code;
            if(state.close_complete)return state.exit_code;
            // A native value callback can request closure, but cannot run the
            // next owner phase before the one explicit shutdown signal.
            if(state.close_requested||session.adapter.closed())continue;
        }
        session.tick();
        state=session.runner_state();
        if(state.exit_code)return state.exit_code;
        if(state.close_complete)return state.exit_code;
        if(!closing&&(state.close_requested||session.adapter.closed()))continue;
        now=host.now();
        if(closing&&now>=*close_limit)return 1;
        host.wait(wait_timeout(state,now,close_limit));
    }
}
}
template<NativeSurfaceApplication App>
int run_fltk(int argc,char** argv,NativeSurfaceSessionFactory<App> factory) {
    try {
        if(argc!=1)throw std::invalid_argument("Usage: foundation-gui-fltk");
        (void)argv;
        std::function<void()> poll;
        const auto mode=factory.mode;
        factory.prepare_peer=[&poll,mode](gui::Adapter& concrete,const NativeSurfaceWindow& window,NativeSurfaceIngress ingress) {
            return prepare_fltk_surface_peer(static_cast<gui::fltk::Adapter&>(concrete),window,std::move(ingress),mode,&poll);
        };
        NativeSession<App,gui::fltk::Adapter,NativeSurfaceSessionFactory<App>> session(std::move(factory));
        struct Host {
            std::function<void()>& native_poll;
            fltk_runner_detail::Clock::time_point now() const {return fltk_runner_detail::Clock::now();}
            void poll(){if(native_poll)native_poll();}
            void wait(int milliseconds) {
                const auto until=now()+std::chrono::milliseconds(milliseconds);
                if(Fl::wait(double(milliseconds)/1000)<0)throw std::runtime_error("FLTK event wait failed");
                // A native close can leave no displayed windows while the App
                // still owns a local completion. Keep a real bounded yield.
                if(!Fl::first_window()&&now()<until)std::this_thread::sleep_until(until);
            }
        } host{poll};
        const int result=fltk_runner_detail::run(session,host);
        if(result)return result;
        if(!session.adapter.error().empty())throw std::runtime_error(session.adapter.error());
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
    return 0;
}
#endif
}
