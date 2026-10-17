// SPDX-License-Identifier: CC0-1.0
#pragma once

#include "contract.hpp"
#include "native_surface.hpp"
#include <atomic>
#include <cmath>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>

namespace foundation::host {

template<class App> concept NativeSurfaceApplication = requires(App& app, gui::Event event,
        gui::ServiceResult result, std::function<void()> present) {
    { app.handle(event) } -> std::same_as<void>;
    { app.tick() } -> std::same_as<void>;
    { app.shutdown() } -> std::same_as<void>;
    { app.retry_presentation() } -> std::same_as<void>;
    { app.next_service() } -> std::same_as<std::optional<gui::ServiceRequest>>;
    { app.complete_service(result) } -> std::same_as<bool>;
    { app.qualify(present) } -> std::same_as<void>;
};
namespace native_surface_detail {
inline std::uint64_t next_generation(std::atomic<std::uint64_t>& counter) noexcept {
    auto value=counter.load(std::memory_order_relaxed);
    while (value) {
        const auto next=value==UINT64_MAX ? 0 : value+1;
        if (counter.compare_exchange_weak(value,next,std::memory_order_relaxed)) return value;
    }
    return 0;
}
inline std::atomic<std::uint64_t> generations{1};
}

struct NativeSurfaceWindow {
    std::string title;
    double width{800}, height{600}, scale{1};
};
// A strictly empty public view clears the actual prepared canvas. Populated
// views keep their declared geometry and remain subject to peer validation.
inline gui::Snapshot prepare_native_blank_canvas(gui::Snapshot value,const NativeSurfaceWindow& window) {
    gui::validate_snapshot(value);
    if (!std::isfinite(window.width) || !std::isfinite(window.height) || !std::isfinite(window.scale) ||
        window.width<=0 || window.height<=0 || window.scale<=0) throw std::invalid_argument("Invalid native canvas");
    if (value.widgets.empty() && value.pages.empty() && value.commands.empty() && value.key_bindings.empty() && !value.modal_root) {
        value.client_size={window.width,window.height}; value.display_scale=window.scale;
        gui::validate_snapshot(value);
    }
    return value;
}
struct NativeSurfaceIngress {
    std::function<gui_surface::AcceptResult(gui_surface::Input)> input;
    std::function<std::optional<std::uint64_t>(NativeEditorObservation)> editor;
    std::function<void(gui::Event)> legacy;
    std::function<void(gui_surface::RevocationReason)> invalidate;
    std::function<void(std::int64_t, std::int64_t)> drawable_pixels;
    std::function<void(bool)> foreground;
};
template<NativeSurfaceApplication App, class Backend, class Services> class NativeSurfaceSession;

// The composition supplies neutral window values, mode and App construction.
// The concrete runner binds prepare_peer using its own window/renderer APIs.
// editor supplies the atomic terminal hook; the session fills all App callbacks
// through its unarmed lifetime gate before constructing the Surface proxy.
template<NativeSurfaceApplication App> struct NativeSurfaceSessionFactory {
    NativeSurfaceWindow window;
    NativeSurfaceMode mode{NativeSurfaceMode::none};
    NativeEditorEndpoint editor;
    std::function<std::unique_ptr<App>(NativeSurfaceAdapter&)> application;
    std::function<NativeSurfacePeer(gui::Adapter&, const NativeSurfaceWindow&, NativeSurfaceIngress)> prepare_peer;
    template<NativeSurfaceApplication SelectedApp, class Backend, class Services>
    using Session = NativeSurfaceSession<SelectedApp, Backend, Services>;
};

template<NativeSurfaceApplication App, class Backend, class Services = AdapterServices>
class NativeSurfaceSession {
    struct Gate {
        const std::thread::id thread{std::this_thread::get_id()};
        App* application{};
        NativeSurfaceAdapter* surface{};
        bool armed{}, stopped{}, entering{};
        bool owner() const noexcept { return std::this_thread::get_id()==thread; }
        bool ingress() const noexcept { return owner() && armed && !stopped && application && surface; }
        void disarm() noexcept { armed=false; application=nullptr; surface=nullptr; stopped=true; }
    };
    // Constructed before Backend and destroyed after every possible callback.
    std::shared_ptr<Gate> gate_{std::make_shared<Gate>()};
    Services files_;
    NativeSurfaceSessionFactory<App> factory_;
public:
    Backend adapter;
private:
    std::unique_ptr<NativeSurfaceAdapter> surface_;
    std::unique_ptr<App> application_;
    static std::uint64_t next_generation() {
        if (const auto value=native_surface_detail::next_generation(native_surface_detail::generations)) return value;
        throw std::overflow_error("Native surface generation exhausted");
    }
    static NativeSurfaceIngress ingress(const std::shared_ptr<Gate>& gate) {
        const std::weak_ptr<Gate> weak=gate;
        return {
            [weak](gui_surface::Input input) {
                if (const auto state=weak.lock(); state && state->ingress())
                    return state->surface->dispatch_input(std::move(input));
                return gui_surface::AcceptResult{gui_surface::Status::closed,{}};
            },
            [weak](NativeEditorObservation observation)->std::optional<std::uint64_t> {
                if (const auto state=weak.lock(); state && state->ingress())
                    return state->surface->observe_editor(std::move(observation));
                return {};
            },
            [weak](gui::Event event) {
                if (const auto state=weak.lock(); state && state->ingress())
                    state->surface->legacy_event(std::move(event));
            },
            [weak](gui_surface::RevocationReason reason) {
                if (const auto state=weak.lock(); state && state->ingress()) state->surface->invalidate(reason);
            },
            [weak](std::int64_t width,std::int64_t height) {
                if (const auto state=weak.lock(); state && state->ingress()) {
                    if constexpr (requires(App& app) { app.drawable_pixels(width,height); }) state->application->drawable_pixels(width,height);
                }
            },
            [weak](bool foreground) {
                if (const auto state=weak.lock(); state && state->ingress()) {
                    if (!foreground) state->surface->invalidate(gui_surface::RevocationReason::unavailable);
                    if constexpr (runner_detail::ForegroundHook<App>) state->application->foreground(foreground);
                }
            }};
    }
    NativeEditorEndpoint endpoint() {
        if (factory_.mode!=NativeSurfaceMode::editor_v1) return {};
        if constexpr (requires(App& app, gui_editor::Packet packet, gui_editor::Revocation revoke, std::uint64_t ticket) {
            { app.editor_submit(std::move(packet)) } -> std::same_as<std::optional<std::uint64_t>>;
            { app.editor_revoke(std::move(revoke)) } -> std::same_as<std::optional<std::uint64_t>>;
            { app.editor_take(ticket) } -> std::same_as<std::optional<gui_editor::EditorCompletion>>;
            { app.editor_resync() } -> std::same_as<void>;
        }) {
            const std::weak_ptr<Gate> weak=gate_;
            auto result=factory_.editor;
            result.submit=[weak](gui_editor::Packet packet)->std::optional<std::uint64_t> {
                if (const auto state=weak.lock(); state && state->ingress()) return state->application->editor_submit(std::move(packet));
                return {};
            };
            result.revoke=[weak](gui_editor::Revocation value)->std::optional<std::uint64_t> {
                if (const auto state=weak.lock(); state && state->ingress()) return state->application->editor_revoke(std::move(value));
                return {};
            };
            result.take=[weak](std::uint64_t ticket)->std::optional<gui_editor::EditorCompletion> {
                if (const auto state=weak.lock(); state && state->ingress()) return state->application->editor_take(ticket);
                return {};
            };
            result.resync=[weak] { if (const auto state=weak.lock(); state && state->ingress()) state->application->editor_resync(); };
            return result;
        } else throw std::invalid_argument("Native editor mode requires its complete neutral App endpoint");
    }
    std::unique_ptr<NativeSurfaceAdapter> make_surface() {
        if (!factory_.prepare_peer || !factory_.application)
            throw std::invalid_argument("Native surface factory needs staged peer and App construction");
        auto peer=factory_.prepare_peer(adapter,factory_.window,ingress(gate_));
        if (!peer.ready || !peer.ready()) throw std::invalid_argument("Native window and renderer are not ready");
        const std::weak_ptr<Gate> weak=gate_;
        auto result=std::make_unique<NativeSurfaceAdapter>(adapter,next_generation(),std::move(peer),factory_.mode,endpoint(),
            [weak](const gui::Event& event) {
                if (const auto state=weak.lock(); state && state->ingress()) state->application->handle(event);
            });
        gate_->surface=result.get();
        return result;
    }
    std::unique_ptr<App> make_application() {
        auto result=factory_.application(*surface_);
        if (!result) throw std::invalid_argument("Native App factory returned no application");
        return result;
    }
    void owner() const {
        if (!gate_->owner()) throw std::logic_error("Native surface session requires its serialized owner");
    }
public:
    App& application;
    explicit NativeSurfaceSession(NativeSurfaceSessionFactory<App> factory)
        : factory_(std::move(factory)), adapter([weak=std::weak_ptr<Gate>(gate_)](const gui::Event& event) {
              if (const auto state=weak.lock(); state && state->ingress()) state->surface->legacy_event(event);
          }), surface_(make_surface()), application_(make_application()), application(*application_) {
        try {
            gate_->application=application_.get(); gate_->armed=true;
            if constexpr (requires(App& app, gui_surface::AcceptedEvent event, gui_surface::Capabilities caps, gui_surface::Revocation revoke) {
                app.surface_input(std::move(event)); app.surface_connected(std::move(caps)); app.surface_revoked(std::move(revoke));
            }) {
                const std::weak_ptr<Gate> weak=gate_;
                surface_->arm(
                    [weak](gui_surface::AcceptedEvent event) { if (const auto state=weak.lock(); state && state->ingress()) state->application->surface_input(std::move(event)); },
                    [weak](gui_surface::Capabilities caps) { if (const auto state=weak.lock(); state && state->ingress()) state->application->surface_connected(std::move(caps)); },
                    [weak](gui_surface::Revocation revoke) { if (const auto state=weak.lock(); state && state->ingress()) state->application->surface_revoked(std::move(revoke)); });
            } else {
                if (factory_.mode!=NativeSurfaceMode::none) throw std::invalid_argument("Native surface App lacks neutral input hooks");
                surface_->arm({},{});
            }
        } catch (...) { shutdown(); throw; }
    }
    ~NativeSurfaceSession() { shutdown(); }
    NativeSurfaceSession(const NativeSurfaceSession&)=delete;
    NativeSurfaceSession& operator=(const NativeSurfaceSession&)=delete;
    NativeSurfaceAdapter& surface() noexcept { return *surface_; }
    const NativeSurfaceAdapter& surface() const noexcept { return *surface_; }
    void shutdown() noexcept {
        if (!gate_ || !gate_->owner() || gate_->stopped) return;
        // Callback lifetime closes before App shutdown and every destructor.
        gate_->disarm();
        if (surface_) surface_->disarm();
        try { files_.shutdown(); } catch (...) {}
        try { if (application_) application_->shutdown(); } catch (...) {}
        try { if (surface_) surface_->close(); } catch (...) {}
        try { adapter.close(); } catch (...) {}
    }
    void drawable_cells(std::int64_t columns,std::int64_t rows) {
        owner(); if (gate_->stopped) return;
        if constexpr (runner_detail::CellsHook<App>) application.drawable_cells(columns,rows);
    }
    void drawable_pixels(std::int64_t width,std::int64_t height) {
        owner(); if (gate_->stopped) return;
        if constexpr (requires(App& app) { app.drawable_pixels(width,height); }) application.drawable_pixels(width,height);
    }
    void foreground(bool value) {
        owner(); if (gate_->stopped) return;
        if (!value) surface_->invalidate(gui_surface::RevocationReason::unavailable);
        if constexpr (runner_detail::ForegroundHook<App>) application.foreground(value);
    }
    RunnerState runner_state() const {
        owner();
        if constexpr (runner_detail::StateHook<App>) return application.runner_state();
        else { const bool closed=adapter.closed(); return {closed,closed,0,{}}; }
    }
    void services() {
        owner(); if (gate_->stopped) { files_.shutdown(); return; }
        // An already-offered asynchronous UI request remains real close debt.
        // Drain its known metadata after backend closure while this Session's
        // callback lifetime is armed. Closing admits no successor request;
        // shutdown() still disarms callbacks and stops Services exactly once.
        if (auto result=files_.poll()) application.complete_service(std::move(*result));
        if (adapter.closed() || files_.active()) return;
        const bool active=[&] { if constexpr (requires { adapter.service_active(); }) return adapter.service_active(); else return bool(adapter.prompt()); }();
        if (!active) if (auto request=application.next_service()) {
            const std::weak_ptr<Gate> weak=gate_;
            files_.service(adapter,std::move(*request),[weak](gui::ServiceResult result) {
                if (const auto state=weak.lock(); state && state->ingress()) state->application->complete_service(std::move(result));
            });
        }
    }
    void tick() {
        owner(); if (gate_->stopped || gate_->entering) return;
        struct Turn { bool& value; explicit Turn(bool& v):value(v){value=true;} ~Turn(){value=false;} } turn(gate_->entering);
        surface_->tick(); application.tick(); surface_->tick();
        if constexpr (requires { adapter.sync(); }) adapter.sync();
        services();
    }
};

} // namespace foundation::host
