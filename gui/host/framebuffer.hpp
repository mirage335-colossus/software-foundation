#pragma once
#include "contract.hpp"
#include "bezel.hpp"
#include "framebuffer_touch.hpp"
#include "framebuffer_surface.hpp"
#include <gui/framebuffer.hpp>

namespace foundation::host {
// A board/display driver receives immutable RGB24 frames and damage metadata.
// It may retain a frame while DMA or another asynchronous consumer finishes.
// It must copy no borrowed adapter state and must call this host on one thread.
template<class T> concept FramebufferDisplay = requires(T& display,const gui::Frame& frame) {
    { display.present(frame) } -> std::same_as<void>;
};

// No window system, timer thread, device path or allocation policy is imposed.
// The embedding event loop owns timing; input and ticks use the same application
// contract and shared interaction engine as the desktop framebuffer runner.
template<Application App, class Services = AdapterServices> class FramebufferHost {
public:
    explicit FramebufferHost(unsigned bezel_buttons=3) : bezel_(bezel_buttons) {}
    auto bezel_labels() { return bezel_.labels(session_.adapter); }
    bool bezel_button(unsigned number) {
        input_.cancel(session_.adapter);
        const bool accepted=bezel_.activate(session_.adapter,number);
        if(accepted)session_.tick();
        return accepted;
    }
    App& application() noexcept {return session_.application;}
    gui::FramebufferAdapter& adapter() noexcept {return session_.adapter;}
    void resize(gui::Size logical_size,double scale=1) {
        input_.cancel(session_.adapter);session_.adapter.resize(logical_size,scale);session_.tick();
    }
    bool contact(Contact source,ContactPhase phase,gui::Point logical_position) {
        const bool accepted=input_.input(session_.adapter,source,phase,logical_position);
        if(accepted)session_.tick();
        return accepted;
    }
    void cancel() {input_.cancel(session_.adapter);session_.tick();}
    template<FramebufferDisplay Display> bool present(Display& display) {
        if(session_.adapter.closed())return false;
        session_.tick();
        if(session_.adapter.closed())return false;
        const auto frame=session_.adapter.frame(displayed_);
        if(frame.damage.width==0||frame.damage.height==0)return false;
        display.present(frame); // A failing driver must not advance its revision.
        displayed_=frame.revision;return true;
    }
private:
    Session<App,gui::FramebufferAdapter,Services> session_;
    Bezel bezel_;
    FramebufferTouch input_;
    std::uint64_t displayed_=0;
};
} // namespace foundation::host
