// SPDX-License-Identifier: CC0-1.0
#pragma once

#include "native_surface_composition.hpp"
#include <gui/framebuffer.hpp>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <thread>
#include <utility>

namespace foundation::host {

// The output owns its device/window/file and must complete presentation before
// returning the exact Snapshot revision. Enqueueing a redraw is not completion.
// It may retain Frame's immutable pixels, but must not mutate the adapter or
// enter the application. A missing/wrong receipt fails the peer closed.
struct NativeFramebufferOutput {
    std::function<bool()> ready;
    std::function<NativeRenderReceipt(const gui::Frame&, std::uint64_t)> present;
    // Irreversible output cleanup, invoked only by peer.close/destruction.
    std::function<void()> suspend;
};

namespace native_framebuffer_detail {
inline void validate_frame(const gui::Frame& frame) {
    const auto maximum=std::numeric_limits<std::size_t>::max();
    if (!frame.pixels || !frame.width || !frame.height || !frame.revision
        || frame.width>maximum/3 || frame.stride_bytes!=std::size_t(frame.width)*3
        || frame.height>maximum/frame.stride_bytes
        || frame.pixels->size()!=frame.stride_bytes*frame.height
        || frame.stride_bytes>static_cast<std::size_t>(std::numeric_limits<std::streamsize>::max()))
        throw std::invalid_argument("Invalid complete framebuffer output");
}
struct PeerState {
    const std::thread::id owner{std::this_thread::get_id()};
    gui::FramebufferAdapter* adapter;
    NativeFramebufferOutput output;
    std::function<void(std::int64_t,std::int64_t)> drawable;
    std::function<void(bool)> foreground;
    NativeSurfaceWindow window;
    std::int64_t width{},height{};
    bool stopped{}, failed{}, presenting{};
    PeerState(gui::FramebufferAdapter& value, NativeFramebufferOutput target, NativeSurfaceWindow prepared, gui::DeviceRect canvas,
        NativeSurfaceIngress ingress)
        :adapter(&value),output(std::move(target)),drawable(std::move(ingress.drawable_pixels)),
         foreground(std::move(ingress.foreground)),window(std::move(prepared)),width(canvas.width),height(canvas.height) {}
    ~PeerState() { try { stop(); } catch (...) {} }
    bool ready() const {
        return std::this_thread::get_id()==owner && !stopped && !failed && !presenting
            && adapter && !adapter->closed() && output.ready && output.ready();
    }
    void activate() {
        if (std::this_thread::get_id()!=owner) throw std::logic_error("Framebuffer output requires its serialized owner");
        if (!ready()) return;
        // This configured output canvas exists before App creation; these are
        // output activity/extent facts, not invented OS focus or physical input.
        if (drawable) drawable(width,height);
        if (foreground) foreground(true);
    }
    void stop() {
        if (std::this_thread::get_id()!=owner) throw std::logic_error("Framebuffer output requires its serialized owner");
        if (stopped) return;
        stopped=true; adapter=nullptr;
        if (output.suspend) output.suspend();
    }
    NativeRenderReceipt present(gui::Snapshot snapshot) {
        if (!ready()) throw std::logic_error("Framebuffer output is not ready");
        if (!snapshot.revision) throw std::invalid_argument("Framebuffer snapshot revision is zero");
        const auto revision=snapshot.revision;
        struct Presenting { bool& flag; explicit Presenting(bool& value):flag(value){flag=true;} ~Presenting(){flag=false;} } turn(presenting);
        try {
            auto* concrete=adapter;
            snapshot=prepare_native_blank_canvas(std::move(snapshot),window);
            const auto requested=gui::device_rect({0,0,snapshot.client_size.width,snapshot.client_size.height},snapshot.display_scale);
            if (requested.width!=width || requested.height!=height)
                throw std::invalid_argument("Framebuffer snapshot does not match its configured output canvas");
            concrete->present(std::move(snapshot));
            const auto& installed=concrete->snapshot();
            if (concrete->closed() || installed.revision!=revision)
                throw std::runtime_error("Framebuffer snapshot installation did not complete");
            const auto grid=gui::device_rect({0,0,installed.client_size.width,installed.client_size.height},installed.display_scale);
            const auto frame=concrete->frame();
            validate_frame(frame);
            if (frame.width!=grid.width || frame.height!=grid.height)
                throw std::runtime_error("Framebuffer rendering changed the installed extent");
            NativeRenderReceipt receipt;
            // Use the actual adapter's renderer mutation guard while the output
            // consumes its immutable frame. The output cannot replace/close the
            // installed snapshot or recursively render it while issuing a receipt.
            concrete->policy().paint_ui([&] { receipt=output.present(frame,revision); });
            if (stopped || adapter!=concrete || concrete->closed()
                || concrete->snapshot().revision!=revision || receipt.snapshot_revision!=revision)
                throw std::runtime_error("Framebuffer output did not complete the exact snapshot");
            return receipt; // Snapshot revision, never the pixel-change counter.
        } catch (...) { failed=true; throw; }
    }
};
struct PpmState {
    const std::thread::id owner{std::this_thread::get_id()};
    std::filesystem::path path;
    std::ofstream stream;
    bool stopped{}, failed{};
    explicit PpmState(std::filesystem::path value):path(std::move(value)) {
        if (path.empty()) throw std::invalid_argument("Framebuffer output path is empty");
        stream.open(path,std::ios::binary|std::ios::trunc);
        if (!stream) throw std::runtime_error("Cannot prepare framebuffer output");
    }
    bool ready() const noexcept { return std::this_thread::get_id()==owner && !stopped && !failed; }
    NativeRenderReceipt present(const gui::Frame& frame,std::uint64_t revision) {
        if (!ready()) throw std::logic_error("Framebuffer PPM output is not ready");
        if (!revision) throw std::invalid_argument("Framebuffer snapshot revision is zero");
        validate_frame(frame);
        try {
            if (!stream.is_open()) { stream.clear(); stream.open(path,std::ios::binary|std::ios::trunc); }
            if (!stream) throw std::runtime_error("Cannot open framebuffer output");
            stream << "P6\n" << frame.width << ' ' << frame.height << "\n255\n";
            for (unsigned row=0; row<frame.height; ++row)
                stream.write(reinterpret_cast<const char*>(frame.pixels->data()+std::size_t(row)*frame.stride_bytes),
                    static_cast<std::streamsize>(frame.stride_bytes));
            stream.flush();
            if (!stream) throw std::runtime_error("Cannot write framebuffer output");
            stream.close();
            if (!stream) throw std::runtime_error("Cannot close framebuffer output");
            return {revision};
        } catch (...) { failed=true; throw; }
    }
    void stop() {
        if (std::this_thread::get_id()!=owner) throw std::logic_error("Framebuffer output requires its serialized owner");
        if (stopped) return;
        stopped=true;
        if (stream.is_open()) stream.close();
    }
};
} // namespace native_framebuffer_detail

// Opens the real output before App construction. Every receipt follows complete
// PPM header/pixels, flush and close. This is a visible file presentation, with no
// window, pointer, keyboard, clipboard, editor or focus capability advertised.
inline NativeFramebufferOutput native_framebuffer_ppm_output(std::filesystem::path path) {
    auto state=std::make_shared<native_framebuffer_detail::PpmState>(std::move(path));
    return {[state] { return state->ready(); },
        [state](const gui::Frame& frame,std::uint64_t revision) { return state->present(frame,revision); },
        [state] { state->stop(); }};
}

// Intended for NativeSurfaceSessionFactory::prepare_peer. The real final
// FramebufferAdapter already exists before this hook and must outlive the peer;
// session close closes the peer before destroying that concrete adapter.
// Its explicit configured output canvas is fixed until a new peer is prepared.
// A strictly empty public view clears this canvas without changing its title or
// revision; populated scenes must already describe that exact output extent.
// Only output extent/activity ingress is used; physical/editor/legacy ingress
// remains unbound for this view-only framebuffer. The
// builder has no application/HTML/engine concepts and constructs no Controller.
inline NativeSurfacePeer prepare_native_framebuffer_surface_peer(gui::Adapter& concrete,
        const NativeSurfaceWindow& window, NativeSurfaceIngress ingress, NativeFramebufferOutput output) {
    auto* framebuffer=dynamic_cast<gui::FramebufferAdapter*>(&concrete);
    if (!framebuffer) throw std::invalid_argument("Framebuffer peer requires the actual FramebufferAdapter");
    if (!std::isfinite(window.width) || !std::isfinite(window.height) || !std::isfinite(window.scale)
        || window.width<=0 || window.height<=0 || window.scale<=0 || !output.ready || !output.present)
        throw std::invalid_argument("Framebuffer peer needs a staged extent and synchronous output");
    const auto canvas=gui::device_rect({0,0,window.width,window.height},window.scale);
    if (!canvas.width || !canvas.height) throw std::invalid_argument("Framebuffer output canvas is empty");
    auto state=std::make_shared<native_framebuffer_detail::PeerState>(*framebuffer,std::move(output),window,canvas,std::move(ingress));
    if (!state->ready()) throw std::invalid_argument("Framebuffer output is not ready before App construction");
    NativeSurfacePeer peer;
    peer.capabilities={};
    peer.ready=[state] { return state->ready(); };
    peer.present=[state](gui::Snapshot snapshot) { return state->present(std::move(snapshot)); };
    peer.suspend=[] {}; // No input/IME/capture; keep rendering available for safe redaction.
    peer.activate=[state] { state->activate(); };
    peer.close=[state] { state->stop(); };
    return peer;
}

} // namespace foundation::host
