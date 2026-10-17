#pragma once
#include "host/native_session.hpp"
#include "host/qualification.hpp"
#include "host/native_rev_surface_peer.hpp"
#include "adapter.hpp"
#include <chrono>
#include <algorithm>
#include <iostream>
#include <thread>

namespace foundation::host {
template<Application App> int run_rev(int argc, char** argv) {
    try {
        const bool smoke = smoke_requested(argc, argv);
        if (argc != 1 && !smoke) throw std::invalid_argument("Usage: foundation-gui-rev [--smoke-test|--self-check]");
        NativeSession<App, gui::rev::Adapter> session;
        session.adapter.show();
        if (smoke) {
            session.application.qualify([&] {
                session.tick(); session.adapter.pump(); session.tick();
                if (!session.adapter.error().empty()) throw std::runtime_error(session.adapter.error());
            });
            const auto pixels = session.adapter.capture();
            if (!pixels.width() || !pixels.height()) throw std::runtime_error("Native capture failed");
            return finish_smoke(session.application, session.adapter);
        }
        while (!session.adapter.closed()) {
            session.tick(); if (!session.adapter.pump()) break;
            std::this_thread::sleep_for(std::chrono::milliseconds(4));
        }
        if (!session.adapter.error().empty()) throw std::runtime_error(session.adapter.error());
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
    return 0;
}

namespace rev_surface_runner_detail {
// State hooks are copied only on the normal owner. A native close request keeps
// the peer renderer/Surface endpoint alive while real application work retires.
// Clock/wait injection permits display-free lifecycle checks, without fake ACKs.
template<class Session,class Peer,class Now,class Wait>
int loop(Session& session,Peer& peer,Now now,Wait wait,bool request_close=false) {
    using Clock=std::chrono::steady_clock;
    std::optional<Clock::time_point> close_limit;
    auto request=[&] {
        if(close_limit)return;
        close_limit=now()+std::chrono::seconds(10);
        session.application.shutdown();
    };
    for(;;) {
        auto state=session.runner_state();
        if(state.exit_code)return state.exit_code;
        if(state.close_complete)return 0;
        if(!close_limit && (request_close || state.close_requested || session.adapter.closed() || peer.close_requested() || peer.closed())) {request_close=false;request();continue;}
        request_close=false;
        if(close_limit && now()>=*close_limit)return 1;
        session.tick();
        state=session.runner_state();
        if(state.exit_code)return state.exit_code;
        if(state.close_complete)return 0;
        if(!close_limit && (state.close_requested || session.adapter.closed() || peer.close_requested() || peer.closed())) {request();continue;}
        if(!peer.closed()) {
            if(!peer.pump() && !close_limit)request();
        } else if(!close_limit)request();
        if(!peer.error().empty())throw std::runtime_error(peer.error());
        state=session.runner_state();
        if(state.exit_code)return state.exit_code;
        if(state.close_complete)return 0;
        if(!close_limit && (state.close_requested || session.adapter.closed() || peer.close_requested() || peer.closed())) {request();continue;}
        const auto current=now();
        if(close_limit && current>=*close_limit)return 1;
        auto until=current+std::chrono::milliseconds(4);
        if(state.deadline)until=std::min(until,*state.deadline);
        if(until<=current)until=current+std::chrono::milliseconds(1);
        if(close_limit)until=std::min(until,*close_limit);
        wait(until);
    }
}
}

// Opt-in staged native surface. The ordinary two-argument runner above remains
// the original native widget session. This path rasterizes generic Snapshots;
// the peer owns their actual Rev window, texture upload and native input hooks.
template<NativeSurfaceApplication App>
int run_rev(int argc,char** argv,NativeSurfaceSessionFactory<App> factory) {
    try {
        const bool smoke=smoke_requested(argc,argv);
        if(argc!=1 && !smoke)throw std::invalid_argument("Usage: foundation-gui-rev [--smoke-test|--self-check]");
        std::unique_ptr<NativeRevSurfacePeer> peer;
        const auto mode=factory.mode;
        factory.prepare_peer=[&peer,mode](gui::Adapter& adapter,const NativeSurfaceWindow& window,NativeSurfaceIngress ingress) {
            auto* canvas=dynamic_cast<gui::FramebufferAdapter*>(&adapter);
            if(!canvas)throw std::invalid_argument("Rev surface requires its generic framebuffer canvas");
            peer=std::make_unique<NativeRevSurfacePeer>(*canvas,window,std::move(ingress),mode);
            return peer->peer();
        };
        NativeSession<App,gui::FramebufferAdapter,NativeSurfaceSessionFactory<App>> session(std::move(factory));
        if(!peer)throw std::runtime_error("Rev native surface was not staged before App construction");
        if(smoke) {
            session.application.qualify([&] {
                session.tick();if(!peer->pump())throw std::runtime_error("Rev surface closed during qualification");session.tick();
                if(!peer->error().empty())throw std::runtime_error(peer->error());
            });
        }
        const auto result=rev_surface_runner_detail::loop(session,*peer,
            []{return std::chrono::steady_clock::now();},
            [](auto until){std::this_thread::sleep_until(until);},smoke);
        if(!result && smoke)std::cout<<"software-foundation gui smoke: ok\n";
        return result;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
    return 0;
}
}
