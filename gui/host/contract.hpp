#pragma once
#include <gui/contract.hpp>
#include <gui/runtime.hpp>
#include <concepts>
#include <functional>

namespace foundation::host {
// The only application contract a platform runner requires. No control IDs,
// product commands, layout policy or core operations belong to a runner.
template<class T> concept Application = requires(T& app, gui::Event event, gui::ServiceResult result,
                                                std::function<void()> present) {
    T{std::declval<gui::Adapter&>()};
    { app.handle(event) } -> std::same_as<void>;
    { app.tick() } -> std::same_as<void>;
    { app.shutdown() } -> std::same_as<void>;
    { app.retry_presentation() } -> std::same_as<void>;
    { app.next_service() } -> std::same_as<std::optional<gui::ServiceRequest>>;
    { app.complete_service(result) } -> std::same_as<bool>;
    { app.qualify(present) } -> std::same_as<void>;
};

template<Application App, class Adapter> class Session {
    App* current_ = nullptr;
public:
    Adapter adapter;
    App application;
    Session() : adapter([this](const gui::Event& event) {
        if (current_) { current_->handle(event); services(); }
    }), application(adapter) { current_ = &application; }
    ~Session() { application.shutdown(); adapter.close(); current_ = nullptr; }
    void services() {
        const bool active = [&] {
            if constexpr (requires { adapter.service_active(); }) return adapter.service_active();
            else return bool(adapter.prompt());
        }();
        if (!adapter.closed() && !active) if (auto request = application.next_service())
            adapter.service(std::move(*request), [this](gui::ServiceResult result) {
                if (current_) current_->complete_service(std::move(result));
            });
    }
    void tick() {
        application.tick();
        if constexpr (requires { adapter.sync(); }) adapter.sync();
        services();
    }
};
} // namespace foundation::host
