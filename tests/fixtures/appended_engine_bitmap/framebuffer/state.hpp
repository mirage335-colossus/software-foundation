// SPDX-License-Identifier: CC0-1.0
#pragma once
#include "../state.hpp"
#include "host/native_surface_composition.hpp"
#include <gui/framebuffer.hpp>
#include <memory>
#include <string_view>

namespace bitmap_framebuffer_fixture {
inline std::string_view scenario;
inline unsigned outputs{}, artifacts{}, sessions{}, shutdowns{}, ticks{};
inline bool closing{};
inline void require(bool value, const char* message) { bitmap_entry_fixture::require(value,message); }
struct Application {
    void request_frame() { require(!closing,"frame requested after shutdown"); }
    bool frame_ready() const { return ticks!=0; }
    void shutdown() { ++shutdowns;closing=true; }
};
struct Adapter {
    gui::Frame frame() const {
        gui::Frame value;value.width=1;value.height=1;value.stride_bytes=3;value.revision=41;
        value.pixels=std::make_shared<const std::vector<std::uint8_t>>(std::vector<std::uint8_t>{1,2,3});
        return value;
    }
};
struct Surface {
    gui::Snapshot snapshot() const { gui::Snapshot value;value.revision=73;return value; }
};
struct Session {
    Application application;
    Adapter adapter;
    Surface surface_;
    template<class Factory> explicit Session(Factory factory) {
        ++sessions;
        require(factory.mode==foundation::host::NativeSurfaceMode::none&&bool(factory.prepare_peer),
            "framebuffer root did not select its staged view-only peer");
    }
    void drawable_pixels(std::int64_t width,std::int64_t height) { require(width==800&&height==600,"root changed fixed drawable"); }
    void foreground(bool value) { require(value,"root did not activate output"); }
    void tick() { ++ticks;require(!closing,"completed fake close must not require another turn"); }
    foundation::host::RunnerState runner_state() const {
        if(closing)return {true,true,scenario=="error-detached"?1:0,{}};
        return {false,false,scenario=="error-frame"?1:0,{}};
    }
    Surface& surface() { return surface_; }
};
}
