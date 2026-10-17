// SPDX-License-Identifier: CC0-1.0
#pragma once

#include "browser.hpp"
#include "browser_surface.hpp"
#include <atomic>
#include <concepts>
#include <cstdint>
#include <limits>
#include <optional>
#include <stdexcept>
#include <utility>

namespace foundation::host {
namespace browser_surface_detail {

// Zero permanently poisons an exhausted counter. The successful CAS is the
// allocation point, including the last UINT64_MAX allocation before poison.
inline std::uint64_t next_generation(std::atomic<std::uint64_t>& counter) noexcept {
    auto value = counter.load(std::memory_order_relaxed);
    while (value) {
        const auto successor = value == std::numeric_limits<std::uint64_t>::max() ? 0 : value + 1;
        if (counter.compare_exchange_weak(value, successor, std::memory_order_relaxed,
                                          std::memory_order_relaxed)) return value;
    }
    return 0;
}
inline std::uint64_t allocate_generation() noexcept {
    static std::atomic<std::uint64_t> counter{1};
    return next_generation(counter);
}

template<class App> concept ExactInputHook = requires {
    static_cast<void (App::*)(gui_surface::AcceptedEvent)>(&App::surface_input);
};
template<class App> concept InputHookCandidate =
    requires(App& app, gui_surface::AcceptedEvent value) { app.surface_input(value); } ||
    requires(App& app, gui_surface::AcceptedEvent value) { app.surface_input(std::move(value)); };
template<class App> concept ExactConnectedHook = requires {
    static_cast<void (App::*)(gui_surface::Capabilities)>(&App::surface_connected);
};
template<class App> concept ConnectedHookCandidate =
    requires(App& app, gui_surface::Capabilities value) { app.surface_connected(value); } ||
    requires(App& app, gui_surface::Capabilities value) { app.surface_connected(std::move(value)); };
template<class App> concept ExactRevokedHook = requires {
    static_cast<void (App::*)(gui_surface::Revocation)>(&App::surface_revoked);
};
template<class App> concept RevokedHookCandidate =
    requires(App& app, gui_surface::Revocation value) { app.surface_revoked(value); } ||
    requires(App& app, gui_surface::Revocation value) { app.surface_revoked(std::move(value)); };

template<class App> concept ExactEditorHooks = requires {
    static_cast<std::optional<std::uint64_t> (App::*)(::foundation::gui_editor::Packet)>(&App::editor_submit);
    static_cast<std::optional<std::uint64_t> (App::*)(::foundation::gui_editor::Revocation)>(&App::editor_revoke);
    static_cast<std::optional<::foundation::gui_editor::EditorCompletion> (App::*)(std::uint64_t)>(&App::editor_take);
    static_cast<void (App::*)()>(&App::editor_resync);
};
template<class App> concept ExactDocumentHooks = requires {
    static_cast<::foundation::gui_document::Submission (App::*)(::foundation::gui_document::Intent)>(&App::document_submit);
    static_cast<std::optional<::foundation::gui_document::Completion> (App::*)(::foundation::gui_document::Ticket)>(&App::document_take);
    static_cast<::foundation::gui_document::State (App::*)() const>(&App::document_state);
    static_cast<::foundation::gui_document::TerminalHook (App::*)() noexcept>(&App::document_terminal);
    requires noexcept(std::declval<App&>().document_terminal());
};
template<class App> concept DocumentHookCandidate =
    requires{&App::document_submit;} || requires{&App::document_take;} ||
    requires{&App::document_state;} || requires{&App::document_terminal;} ||
    requires(App& app,::foundation::gui_document::Intent i){app.document_submit(std::move(i));} ||
    requires(App& app,::foundation::gui_document::Ticket t){app.document_take(t);} ||
    requires(App& app){app.document_state();} || requires(App& app){app.document_terminal();};

} // namespace browser_surface_detail

// Each optional hook is independent. If it accepts its corresponding value, it
// must provide the exact owned-by-value void member; a borrowed or wrong-return
// overload cannot silently discard surface work. An exact overload may coexist
// with others, and forwarding invokes that selected member explicitly.
template<class App> concept BrowserSurfaceApplication = Application<App> &&
    (browser_surface_detail::ExactInputHook<App> || !browser_surface_detail::InputHookCandidate<App>) &&
    (browser_surface_detail::ExactConnectedHook<App> || !browser_surface_detail::ConnectedHookCandidate<App>) &&
    (browser_surface_detail::ExactRevokedHook<App> || !browser_surface_detail::RevokedHookCandidate<App>) &&
    (browser_surface_detail::ExactDocumentHooks<App> || !browser_surface_detail::DocumentHookCandidate<App>);

// Optional generic composition only. No engine, guest or application feature
// meaning belongs here. Factories are serialized on their native owner; each
// composition spends one fresh generation on one adapter/session construction.
class BrowserSurfaceComposition {
public:
    using Adapter = BrowserSurfaceAdapter;
    using Session = BrowserSurfaceSession;

    explicit BrowserSurfaceComposition(gui_surface::Features ceiling = 0,
                                       surface_web::Profile profile = surface_web::Profile::legacy,
                                       BrowserEditorEndpoint editor = {},BrowserDocumentEndpoint document = {},bool bind_document_hooks = false,bool poll_prepared_services = false)
        : ceiling_(checked_ceiling(ceiling,profile)), profile_(profile), editor_(std::move(editor)),document_(std::move(document)),bind_document_hooks_(bind_document_hooks),poll_prepared_services_(poll_prepared_services),
          generation_(browser_surface_detail::allocate_generation()) {
        if (!generation_) throw std::overflow_error("Browser surface generations exhausted");
    }
    BrowserSurfaceComposition(const BrowserSurfaceComposition&) = delete;
    BrowserSurfaceComposition& operator=(const BrowserSurfaceComposition&) = delete;
    BrowserSurfaceComposition(BrowserSurfaceComposition&& other) noexcept
        : ceiling_(std::exchange(other.ceiling_, 0)), profile_(other.profile_), editor_(std::move(other.editor_)),document_(std::move(other.document_)),bind_document_hooks_(std::exchange(other.bind_document_hooks_,false)),poll_prepared_services_(std::exchange(other.poll_prepared_services_,false)),
          generation_(std::exchange(other.generation_, 0)),
          adapter_created_(std::exchange(other.adapter_created_, false)),
          session_created_(std::exchange(other.session_created_, false)) {}
    BrowserSurfaceComposition& operator=(BrowserSurfaceComposition&& other) noexcept {
        if (this != &other) {
            ceiling_ = std::exchange(other.ceiling_, 0);
            profile_ = other.profile_;
            editor_ = std::move(other.editor_);
            document_ = std::move(other.document_);
            bind_document_hooks_ = std::exchange(other.bind_document_hooks_,false);
            poll_prepared_services_ = std::exchange(other.poll_prepared_services_,false);
            generation_ = std::exchange(other.generation_, 0);
            adapter_created_ = std::exchange(other.adapter_created_, false);
            session_created_ = std::exchange(other.session_created_, false);
        }
        return *this;
    }
    std::uint64_t generation() const noexcept { return generation_; }

    template<BrowserSurfaceApplication App>
    Adapter make_adapter(BrowserApplicationAccess<App>& access) const {
        if (!generation_ || adapter_created_) throw std::logic_error("Browser surface adapter construction is unavailable");
        adapter_created_ = true;
        auto editor = editor_;
        auto document=document_;
        if(bind_document_hooks_){
          if constexpr(browser_surface_detail::ExactDocumentHooks<App>){
            namespace D=::foundation::gui_document;
            auto terminal=std::make_shared<BrowserDocumentTerminalBinding>();
            document.terminal_binding=terminal;
            document.activate_terminal=[&access,terminal]{
                bool armed=false;
                access.notify([&](App& app){
                    terminal->bind((app.*static_cast<D::TerminalHook (App::*)() noexcept>(&App::document_terminal))());
                    armed=true;
                });
                if(!armed)throw std::logic_error("Document terminal activation requires an armed application");
            };
            document.submit=[&access,terminal](D::Intent value){
                D::Submission result;
                access.notify([&](App& app){
                    terminal->bind((app.*static_cast<D::TerminalHook (App::*)() noexcept>(&App::document_terminal))());
                    result=(app.*static_cast<D::Submission (App::*)(D::Intent)>(&App::document_submit))(std::move(value));
                });return result;
            };
            document.take=[&access,terminal](D::Ticket ticket){
                std::optional<D::Completion> result;
                access.notify([&](App& app){
                    terminal->bind((app.*static_cast<D::TerminalHook (App::*)() noexcept>(&App::document_terminal))());
                    result=(app.*static_cast<std::optional<D::Completion> (App::*)(D::Ticket)>(&App::document_take))(ticket);
                });return result;
            };
            document.state=[&access,terminal]{
                D::State result;
                access.notify([&](App& app){
                    terminal->bind((app.*static_cast<D::TerminalHook (App::*)() noexcept>(&App::document_terminal))());
                    result=(std::as_const(app).*static_cast<D::State (App::*)() const>(&App::document_state))();
                });return result;
            };
            // No foreign-thread access to the App/lifetime gate. Before the
            // first armed callback this is inert; close detaches and joins it.
            document.terminal={terminal.get(),[](void* context) noexcept{
                static_cast<BrowserDocumentTerminalBinding*>(context)->notify();
            }};
          }else throw std::invalid_argument("Document composition requires complete owned document hooks");
        }
        if (profile_ == surface_web::Profile::editor_v1) {
            if constexpr (browser_surface_detail::ExactEditorHooks<App>) {
                editor.submit = [&access](::foundation::gui_editor::Packet value) {
                    std::optional<std::uint64_t> result;
                    access.notify([&](App& app) {
                        const auto hook = static_cast<std::optional<std::uint64_t> (App::*)(::foundation::gui_editor::Packet)>(&App::editor_submit);
                        result = (app.*hook)(std::move(value));
                    });
                    return result;
                };
                editor.revoke = [&access](::foundation::gui_editor::Revocation value) {
                    std::optional<std::uint64_t> result;
                    access.notify([&](App& app) {
                        const auto hook = static_cast<std::optional<std::uint64_t> (App::*)(::foundation::gui_editor::Revocation)>(&App::editor_revoke);
                        result = (app.*hook)(std::move(value));
                    });
                    return result;
                };
                editor.take = [&access](std::uint64_t ticket) {
                    std::optional<::foundation::gui_editor::EditorCompletion> result;
                    access.notify([&](App& app) {
                        const auto hook = static_cast<std::optional<::foundation::gui_editor::EditorCompletion> (App::*)(std::uint64_t)>(&App::editor_take);
                        result = (app.*hook)(ticket);
                    });
                    return result;
                };
                editor.resync = [&access] {
                    access.notify([](App& app) {
                        const auto hook = static_cast<void (App::*)()>(&App::editor_resync);
                        (app.*hook)();
                    });
                };
            } else throw std::invalid_argument("Browser editor composition requires complete owned editor hooks");
        }
        return Adapter(generation_, [&access](const ::gui::Event& event) { access.handle(event); },
            [&access](gui_surface::Revocation value) {
                access.notify([owned = std::move(value)](App& app) mutable {
                    if constexpr (browser_surface_detail::ExactRevokedHook<App>) {
                        const auto hook = static_cast<void (App::*)(gui_surface::Revocation)>(&App::surface_revoked);
                        (app.*hook)(std::move(owned));
                    }
                });
            }, ceiling_, profile_, std::move(editor),std::move(document));
    }
    // Browser calls this once after App construction and lifetime-gate arming,
    // before presentation retries or any public session parsing can fail.
    template<BrowserSurfaceApplication App>
    void activate(Adapter& adapter,BrowserApplicationAccess<App>&)const{adapter.activate_document_endpoint();}
    template<BrowserSurfaceApplication App>
    Session make_session(Adapter& adapter, std::string epoch, BrowserApplicationAccess<App>& access) const {
        if (!generation_ || !adapter_created_ || session_created_)
            throw std::logic_error("Browser surface session construction is unavailable");
        session_created_ = true;
        return Session(adapter, std::move(epoch),
            [&access](gui_surface::AcceptedEvent value) {
                access.notify([owned = std::move(value)](App& app) mutable {
                    if constexpr (browser_surface_detail::ExactInputHook<App>) {
                        const auto hook = static_cast<void (App::*)(gui_surface::AcceptedEvent)>(&App::surface_input);
                        (app.*hook)(std::move(owned));
                    }
                });
            },
            [&access](gui_surface::Capabilities value) {
                access.notify([owned = std::move(value)](App& app) mutable {
                    if constexpr (browser_surface_detail::ExactConnectedHook<App>) {
                        const auto hook = static_cast<void (App::*)(gui_surface::Capabilities)>(&App::surface_connected);
                        (app.*hook)(std::move(owned));
                    }
                });
            },
            [&access] { return access.next_service(); },
            [&access](::gui::ServiceResult result) { return access.complete_service(std::move(result)); },
            [&access] { access.tick(); },poll_prepared_services_);
    }

private:
    gui_surface::Features ceiling_;
    surface_web::Profile profile_;
    BrowserEditorEndpoint editor_;
    BrowserDocumentEndpoint document_;
    bool bind_document_hooks_{};
    bool poll_prepared_services_{};
    std::uint64_t generation_;
    mutable bool adapter_created_ = false, session_created_ = false;
    static gui_surface::Features checked_ceiling(gui_surface::Features value, surface_web::Profile profile) {
        const auto supported = profile == surface_web::Profile::legacy ? surface_web::basic_supported :
            profile == surface_web::Profile::mouse_v1 ? surface_web::successor_supported :
            profile == surface_web::Profile::editor_v1 ? surface_web::editor_supported : 0;
        if (!supported || (value & ~supported)) throw std::invalid_argument("Unsupported browser surface ceiling/profile");
        return value;
    }
};

} // namespace foundation::host
