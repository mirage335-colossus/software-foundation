#pragma once
#include "host/contract.hpp"
#include <gui/web.hpp>
#include <functional>
#include <memory>
#include <stdexcept>
#include <utility>

namespace foundation::host {
template<Application App, class Composition> class Browser;

// All policy callbacks pass through this lifetime gate. A policy can enqueue
// typed application work without retaining an App pointer or changing the
// runner's application contract. This object outlives the adapter and session.
template<Application App> class BrowserApplicationAccess {
    template<Application, class> friend class Browser;
    App* current_ = nullptr;
    bool armed_ = false;
    std::size_t callback_depth_ = 0;
    struct Callback {
        BrowserApplicationAccess& owner;
        explicit Callback(BrowserApplicationAccess& value) : owner(value) { ++owner.callback_depth_; }
        ~Callback() { --owner.callback_depth_; }
    };
    template<class Result, class F> Result query(F&& function, Result fallback) {
        if (!armed_ || !current_) return fallback;
        Callback guard(*this);
        return std::invoke(std::forward<F>(function), *current_);
    }
public:
    BrowserApplicationAccess() = default;
    BrowserApplicationAccess(const BrowserApplicationAccess&) = delete;
    BrowserApplicationAccess& operator=(const BrowserApplicationAccess&) = delete;
    template<class F> void notify(F&& function) {
        if (!armed_ || !current_) return;
        Callback guard(*this);
        std::invoke(std::forward<F>(function), *current_);
    }
    void handle(const gui::Event& event) { notify([&](App& app) { app.handle(event); }); }
    void tick() { notify([](App& app) { app.tick(); }); }
    std::optional<gui::ServiceRequest> next_service() {
        return query([](App& app) { return app.next_service(); }, std::optional<gui::ServiceRequest>{});
    }
    bool complete_service(gui::ServiceResult result) {
        return query([&](App& app) { return app.complete_service(std::move(result)); }, false);
    }
};

// The default graph remains the original adapter/session types and vocabulary.
// Alternative policies return direct prvalues so neither owner needs to move.
struct WebBrowserComposition {
    using Adapter = gui::WebAdapter;
    using Session = gui::WebSession;
    template<Application App> Adapter make_adapter(BrowserApplicationAccess<App>& access) const {
        return Adapter([&access](const gui::Event& event) { access.handle(event); });
    }
    template<Application App> Session make_session(Adapter& adapter, std::string epoch,
                                                   BrowserApplicationAccess<App>& access) const {
        return Session(adapter, std::move(epoch), [&access] { return access.next_service(); },
            [&access](gui::ServiceResult result) { return access.complete_service(std::move(result)); },
            [&access] { access.tick(); });
    }
};

// Both browser transports instantiate this runtime. Application meaning remains
// in App; WebSession owns framing, identity, validation and service completion.
template<Application App, class Composition = WebBrowserComposition> class Browser {
    BrowserApplicationAccess<App> access_;
    Composition composition_;
    bool receiving_ = false;
public:
    typename Composition::Adapter adapter;
private:
    std::unique_ptr<App> application_;
    struct Cleanup {
        BrowserApplicationAccess<App>& access;
        App& application;
        typename Composition::Adapter& adapter;
        Cleanup(BrowserApplicationAccess<App>& gate, App& app, typename Composition::Adapter& target) noexcept
            : access(gate), application(app), adapter(target) { access.current_ = &application; }
        ~Cleanup() {
            access.armed_ = false;
            access.current_ = nullptr;
            // Shutdown is not required to be noexcept by Application. Always
            // attempt both cleanup steps, including session-constructor unwind.
            try { application.shutdown(); } catch (...) {}
            try { adapter.close(); } catch (...) {}
        }
    } cleanup_;
    struct Receiving {
        Browser& owner;
        explicit Receiving(Browser& value) : owner(value) {
            if (!owner.access_.armed_ || owner.receiving_ || owner.access_.callback_depth_)
                throw std::logic_error("Browser entry is unavailable or reentrant");
            owner.receiving_ = true;
        }
        ~Receiving() { owner.receiving_ = false; }
    };
public:
    typename Composition::Session session;
    explicit Browser(std::string epoch) requires std::default_initializable<Composition>
        : Browser(std::move(epoch), Composition{}) {}
    Browser(std::string epoch, Composition composition)
        : composition_(std::move(composition)), adapter(composition_.make_adapter(access_)),
          application_(std::make_unique<App>(adapter)), cleanup_(access_, *application_, adapter),
          session(composition_.make_session(adapter, std::move(epoch), access_)) {
        access_.armed_ = true;
        if constexpr (requires { composition_.activate(adapter, access_); })
            composition_.activate(adapter, access_);
    }
    ~Browser() { access_.armed_ = false; }
    Browser(const Browser&) = delete;
    Browser& operator=(const Browser&) = delete;
    Browser(Browser&&) = delete;
    Browser& operator=(Browser&&) = delete;
    App& application() { return *application_; }
    const App& application() const { return *application_; }
    App& app() { return application(); }
    const App& app() const { return application(); }
    // These guards cover Browser entry points. Public direct session access
    // retains the concrete session's own admission contract.
    std::string initial() {
        Receiving guard(*this);
        application_->retry_presentation(); return session.initial();
    }
    std::string receive(std::string_view message) {
        Receiving guard(*this);
        // A session can require admission against the presentation already
        // shown to the caller. Metadata and wakeups retain retry progress.
        if constexpr (requires { { session.retry_presentation_before_receive(message) } -> std::same_as<bool>; }) {
            if (session.retry_presentation_before_receive(message)) application_->retry_presentation();
        } else application_->retry_presentation();
        return session.receive(message);
    }
};
}
