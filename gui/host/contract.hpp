#pragma once
#include <gui/contract.hpp>
#include <gui/runtime.hpp>
#include <concepts>
#include <chrono>
#include <cstdint>
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

// Only physical-key presentation needs authoritative semantic freshness. An
// ordinary embedding/runner remains compatible with the original contract.
template<class T> concept BezelApplication = Application<T> && requires(const T& app) {
    { app.input_epoch() } -> std::same_as<std::uint64_t>;
    { app.presentation_pending() } -> std::same_as<bool>;
};

// Optional native-loop values. Queries and lifecycle facts only copy/queue
// state; they never advance application work inside an adapter callback.
struct RunnerState {
    bool close_requested{};
    bool close_complete{};
    int exit_code{};
    std::optional<std::chrono::steady_clock::time_point> deadline;
};
namespace runner_detail {
template<class T> concept StateHook = requires {
    static_cast<RunnerState (T::*)() const>(&T::runner_state);
};
template<class T> concept StateCandidate = requires(T& app) { app.runner_state(); };
template<class T> concept CellsHook = requires {
    static_cast<void (T::*)(std::int64_t, std::int64_t)>(&T::drawable_cells);
};
template<class T> concept CellsCandidate = requires(T& app) { app.drawable_cells(std::int64_t{}, std::int64_t{}); };
template<class T> concept ForegroundHook = requires { static_cast<void (T::*)(bool)>(&T::foreground); };
template<class T> concept ForegroundCandidate = requires(T& app) { app.foreground(false); };
}
template<class T> concept RunnerApplication = Application<T> && runner_detail::StateHook<T>;

// Generic event loops need no filesystem or native threading headers. A host
// may inject additional content services without naming application features.
struct AdapterServices {
    bool active() const noexcept { return false; }
    std::optional<gui::ServiceResult> poll() { return std::nullopt; }
    void shutdown() noexcept {}
    template<class Adapter, class Reply> void service(Adapter& adapter, gui::ServiceRequest request, Reply reply) {
        adapter.service(std::move(request), std::move(reply));
    }
};
template<Application App, class Adapter, class Services = AdapterServices> class Session {
    static_assert(runner_detail::StateHook<App> || !runner_detail::StateCandidate<App>, "Invalid optional runner_state hook");
    static_assert(runner_detail::CellsHook<App> || !runner_detail::CellsCandidate<App>, "Invalid optional drawable_cells hook");
    static_assert(runner_detail::ForegroundHook<App> || !runner_detail::ForegroundCandidate<App>, "Invalid optional foreground hook");
    App* current_ = nullptr;
    Services files_;
public:
    Adapter adapter;
    App application;
    Session() : adapter([this](const gui::Event& event) {
        if (current_) { current_->handle(event); services(); }
    }), application(adapter) { current_ = &application; }
    ~Session() { files_.shutdown(); application.shutdown(); adapter.close(); current_ = nullptr; }
    void drawable_cells(std::int64_t columns, std::int64_t rows) {
        if constexpr (runner_detail::CellsHook<App>)
            (application.*static_cast<void (App::*)(std::int64_t, std::int64_t)>(&App::drawable_cells))(columns, rows);
    }
    void foreground(bool value) {
        if constexpr (runner_detail::ForegroundHook<App>)
            (application.*static_cast<void (App::*)(bool)>(&App::foreground))(value);
    }
    RunnerState runner_state() const {
        if constexpr (runner_detail::StateHook<App>)
            return (application.*static_cast<RunnerState (App::*)() const>(&App::runner_state))();
        else { const bool closed = adapter.closed(); return {closed, closed, 0, {}}; }
    }
    void services() {
        if (adapter.closed()) { files_.shutdown(); return; }
        if (auto result = files_.poll()) current_->complete_service(std::move(*result));
        if (files_.active()) return;
        const bool active = [&] {
            if constexpr (requires { adapter.service_active(); }) return adapter.service_active();
            else return bool(adapter.prompt());
        }();
        if (!adapter.closed() && !active) if (auto request = application.next_service())
            files_.service(adapter, std::move(*request), [this](gui::ServiceResult result) {
                if (current_ && !adapter.closed()) current_->complete_service(std::move(result));
            });
    }
    void tick() {
        application.tick();
        if constexpr (requires { adapter.sync(); }) adapter.sync();
        services();
    }
};
} // namespace foundation::host
