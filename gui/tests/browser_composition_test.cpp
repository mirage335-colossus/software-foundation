// SPDX-License-Identifier: CC0-1.0
// Header-only browser composition/lifetime checks and the real generic surface
// policy. No HTML engine, browser process, kernel, portable module or SDK runs.
#include "host/browser_surface_composition.hpp"
#include <atomic>
#include <functional>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

using namespace foundation;
using Json = gui::web_detail::Json;
namespace {
void check(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
template<class F> void throws(F&& function, const char* message) {
    try { function(); } catch (const std::exception&) { return; }
    throw std::runtime_error(message);
}
gui::Snapshot snapshot(std::uint64_t revision = 1) {
    gui::Snapshot value; value.revision = revision; value.title = "Composition fixture"; value.client_size = {100, 100};
    gui::Widget button; button.spec.key = {"generic.button", 1}; button.spec.kind = gui::Kind::button;
    button.state.bounds = {0, 0, 100, 100}; value.widgets.push_back(std::move(button)); return value;
}
gui::Event activation() { return gui::WidgetEvent{{"generic.button", 1}, gui::Activate{}}; }
struct Probe {
    std::vector<std::string> trace;
    std::vector<std::pair<bool, bool>> queries;
    std::vector<gui_surface::AcceptedEvent> inputs;
    std::vector<gui_surface::Capabilities> connections;
    std::vector<gui_surface::Revocation> revocations;
    std::function<void()> exercise, emit, during_retry, during_callback, during_shutdown;
    int handles = 0, ticks = 0, nexts = 0, completions = 0, notifications = 0, retries = 0, shutdowns = 0;
    bool offer = false, throw_app = false, throw_session = false, throw_retry = false;
    bool throw_session_entry = false, throw_shutdown = false, throw_close = false, throw_notify = false;
    int callbacks() const { return handles + ticks + nexts + completions + notifications; }
};
Probe* current = nullptr;
struct Context {
    Probe& probe;
    explicit Context(Probe& value) : probe(value) { check(!current, "Overlapping fixture context"); current = &probe; }
    ~Context() { current = nullptr; }
};
struct LegacyApp {
    Probe& probe;
    explicit LegacyApp(gui::Adapter& adapter) : probe(*current) {
        probe.trace.emplace_back("app.construct");
        if (probe.exercise) probe.exercise();
        if (probe.throw_app) throw std::runtime_error("fixture app constructor");
        adapter.present(snapshot());
    }
    ~LegacyApp() { probe.trace.emplace_back("app.destroy"); if (probe.exercise) probe.exercise(); }
    void handle(const gui::Event&) { ++probe.handles; if (probe.during_callback) probe.during_callback(); }
    void tick() { ++probe.ticks; if (probe.during_callback) probe.during_callback(); }
    void shutdown() {
        ++probe.shutdowns; probe.trace.emplace_back("app.shutdown");
        if (probe.exercise) probe.exercise();
        if (probe.during_shutdown) probe.during_shutdown();
        if (probe.throw_shutdown) throw std::runtime_error("fixture app shutdown");
    }
    void retry_presentation() {
        ++probe.retries; if (probe.during_retry) probe.during_retry();
        if (probe.throw_retry) throw std::runtime_error("fixture presentation retry");
    }
    std::optional<gui::ServiceRequest> next_service() {
        ++probe.nexts; if (probe.during_callback) probe.during_callback();
        if (probe.offer) return gui::ServiceRequest{71, gui::ServiceKind::prompt, "Generic prompt", {}, 64};
        return {};
    }
    bool complete_service(gui::ServiceResult) { ++probe.completions; if (probe.during_callback) probe.during_callback(); return true; }
    void qualify(std::function<void()> present) { present(); }
};
static_assert(host::Application<LegacyApp>);
static_assert(std::same_as<decltype(std::declval<host::Browser<LegacyApp>&>().adapter), gui::WebAdapter>);
static_assert(std::same_as<decltype(std::declval<host::Browser<LegacyApp>&>().session), gui::WebSession>);
static_assert(!std::is_copy_constructible_v<host::Browser<LegacyApp>> && !std::is_move_constructible_v<host::Browser<LegacyApp>>);

class TracedAdapter : public gui::RetainedAdapter {
    gui::EventSink sink_;
    Probe& probe_;
public:
    TracedAdapter(gui::EventSink sink, Probe& probe) : gui::RetainedAdapter(sink), sink_(std::move(sink)), probe_(probe) {
        probe_.trace.emplace_back("adapter.construct");
        probe_.emit = [this] { sink_(activation()); };
        probe_.exercise(); probe_.emit();
    }
    TracedAdapter(const TracedAdapter&) = delete;
    TracedAdapter(TracedAdapter&&) = delete;
    ~TracedAdapter() override { probe_.trace.emplace_back("adapter.destroy"); probe_.exercise(); probe_.emit(); }
    void close() override {
        probe_.trace.emplace_back("adapter.close"); probe_.exercise(); probe_.emit();
        if (probe_.throw_close) throw std::runtime_error("fixture adapter close");
        gui::RetainedAdapter::close();
    }
};
class TracedSession {
    Probe& probe_;
    std::function<void()> callbacks_;
public:
    TracedSession(TracedAdapter&, std::string, Probe& probe, std::function<void()> callbacks)
        : probe_(probe), callbacks_(std::move(callbacks)) {
        probe_.trace.emplace_back("session.construct"); callbacks_(); probe_.emit();
        if (probe_.throw_session) throw std::runtime_error("fixture session constructor");
    }
    TracedSession(const TracedSession&) = delete;
    TracedSession(TracedSession&&) = delete;
    ~TracedSession() { probe_.trace.emplace_back("session.destroy"); callbacks_(); probe_.emit(); }
    void fire() { callbacks_(); }
    std::string initial() {
        if (probe_.throw_session_entry) throw std::runtime_error("fixture session entry");
        fire(); return "traced initial";
    }
    std::string receive(std::string_view) {
        if (probe_.throw_session_entry) throw std::runtime_error("fixture session entry");
        fire(); return "traced response";
    }
};
struct TracedComposition {
    using Adapter = TracedAdapter;
    using Session = TracedSession;
    Probe* probe;
    explicit TracedComposition(Probe& value) : probe(&value) {}
    TracedComposition(const TracedComposition&) = delete;
    TracedComposition(TracedComposition&&) = default;
    template<host::Application App> Adapter make_adapter(host::BrowserApplicationAccess<App>& access) const {
        probe->exercise = [&access, state = probe] {
            access.handle(activation()); access.tick();
            const bool pending = bool(access.next_service());
            const bool completed = access.complete_service({71, gui::ServiceStatus::cancelled, {}, {}});
            access.notify([state](App&) {
                ++state->notifications;
                if (state->throw_notify) throw std::runtime_error("fixture notification");
                if (state->during_callback) state->during_callback();
            });
            state->queries.emplace_back(pending, completed);
        };
        return Adapter([&access](const gui::Event& event) { access.handle(event); }, *probe);
    }
    template<host::Application App> Session make_session(Adapter& adapter, std::string epoch,
                                                        host::BrowserApplicationAccess<App>&) const {
        return Session(adapter, std::move(epoch), *probe, probe->exercise);
    }
};
using TracedBrowser = host::Browser<LegacyApp, TracedComposition>;

void legacy_graph() {
    Probe probe; Context context(probe);
    {
        host::Browser<LegacyApp> browser("legacy");
        check(&browser.application() == &browser.app(), "Application aliases differ");
        const auto& constant = browser;
        check(&constant.application() == &constant.app(), "Const application aliases differ");
        const auto parsed = gui::web_detail::Parser(browser.initial()).parse();
        const auto& object = std::get<Json::Object>(parsed.value);
        check(!object.contains("surface") && object.size() == 6, "Default Browser changed the legacy wire vocabulary");
        const auto message = gui::web_detail::encode(Json::Object{{"epoch", "legacy"}, {"seq", "1"},
            {"operation", Json::Object{{"type", "activate"}, {"key", gui::web_detail::key({"generic.button", 1})}}}});
        (void)browser.receive(message); check(probe.handles == 1, "Legacy activation did not reach the unchanged App");
    }
    check(probe.shutdowns == 1 && probe.trace.back() == "app.destroy", "Legacy App cleanup did not finish once");
}
void lifetime_and_arm() {
    Probe probe; probe.offer = true; Context context(probe); int callbacks = 0;
    {
        TracedBrowser browser("trace", TracedComposition(probe));
        check(probe.trace == std::vector<std::string>{"adapter.construct", "app.construct", "session.construct"}, "Construction graph changed");
        check(probe.callbacks() == 0, "Construction callbacks reached a partially constructed Browser");
        for (const auto& result : probe.queries) check(!result.first && !result.second, "Unarmed query did not use its safe fallback");
        check(browser.initial() == "traced initial", "Direct-prvalue policy session was not used");
        check(probe.handles == 1 && probe.ticks == 1 && probe.nexts == 1 && probe.completions == 1 && probe.notifications == 1,
              "The complete Browser did not arm all independent callback routes");
        check(probe.queries.back() == std::pair{true, true}, "Armed query lost its owned return value"); callbacks = probe.callbacks();
        probe.during_shutdown = [&] {
            throws([&] { (void)browser.initial(); }, "Shutdown reentered a destroyed session");
            throws([&] { (void)browser.receive("{}"); }, "Shutdown receive was admitted");
        };
    }
    const std::vector<std::string> expected{"adapter.construct", "app.construct", "session.construct", "session.destroy",
        "app.shutdown", "adapter.close", "app.destroy", "adapter.destroy"};
    check(probe.trace == expected, "Session, cleanup, App and adapter destruction order changed");
    check(probe.callbacks() == callbacks && probe.shutdowns == 1, "Destruction callbacks entered an unarmed or destroyed App");
}
void construction_failure_and_cleanup() {
    for (const bool app_failure : {true, false}) {
        Probe probe; Context context(probe); probe.offer = true;
        probe.throw_app = app_failure; probe.throw_session = !app_failure;
        throws([&] { TracedBrowser browser("failure", TracedComposition(probe)); }, "Fixture construction unexpectedly succeeded");
        const auto expected = app_failure ? std::vector<std::string>{"adapter.construct", "app.construct", "adapter.destroy"} :
            std::vector<std::string>{"adapter.construct", "app.construct", "session.construct", "app.shutdown", "adapter.close", "app.destroy", "adapter.destroy"};
        check(probe.trace == expected, "Constructor failure destroyed owners in the wrong order");
        check(probe.callbacks() == 0 && probe.shutdowns == int(!app_failure), "Constructor failure armed callbacks or missed cleanup");
    }
    for (const auto& [shutdown_failure, close_failure] : {std::pair{true, false}, std::pair{false, true}, std::pair{true, true}}) {
        Probe probe; Context context(probe); probe.throw_shutdown = shutdown_failure; probe.throw_close = close_failure;
        { TracedBrowser browser("cleanup", TracedComposition(probe)); }
        check(probe.shutdowns == 1 && probe.trace == std::vector<std::string>{"adapter.construct", "app.construct", "session.construct",
            "session.destroy", "app.shutdown", "adapter.close", "app.destroy", "adapter.destroy"},
            "A throwing cleanup step prevented the other owners from cleaning up");
    }
}
void entry_and_callback_guards() {
    Probe probe; Context context(probe); TracedBrowser browser("entry", TracedComposition(probe));
    bool nested_retry = false;
    probe.during_retry = [&] {
        if (nested_retry) return;
        nested_retry = true;
        throws([&] { (void)browser.initial(); }, "Presentation retry reentered initial");
        throws([&] { (void)browser.receive("nested"); }, "Presentation retry reentered receive");
        nested_retry = false;
    };
    (void)browser.initial(); check(probe.retries == 1, "Nested entry ran presentation before rejection");
    probe.during_retry = {};
    probe.throw_retry = true; throws([&] { (void)browser.receive("retry"); }, "Presentation exception was swallowed");
    probe.throw_retry = false; check(browser.receive("after retry") == "traced response", "Presentation exception stranded entry admission");
    probe.throw_session_entry = true; throws([&] { (void)browser.initial(); }, "Session exception was swallowed");
    probe.throw_session_entry = false; check(browser.initial() == "traced initial", "Session exception stranded entry admission");
    const auto retries = probe.retries;
    probe.during_callback = [&] {
        throws([&] { (void)browser.initial(); }, "Application callback reentered initial");
        throws([&] { (void)browser.receive("nested"); }, "Application callback reentered receive");
    };
    browser.session.fire(); check(probe.retries == retries, "Callback reentry ran presentation before rejection");
    probe.during_callback = {}; probe.throw_notify = true;
    throws([&] { browser.session.fire(); }, "Owned notification exception was swallowed");
    probe.throw_notify = false; check(browser.initial() == "traced initial", "Notification exception stranded callback depth");
}

struct InputOnly : LegacyApp {
    using LegacyApp::LegacyApp;
    void surface_input(gui_surface::AcceptedEvent value) { probe.inputs.push_back(std::move(value)); }
};
struct ConnectedOnly : LegacyApp {
    using LegacyApp::LegacyApp;
    void surface_connected(gui_surface::Capabilities value) { probe.connections.push_back(std::move(value)); }
};
struct RevokedOnly : LegacyApp {
    using LegacyApp::LegacyApp;
    void surface_revoked(gui_surface::Revocation value) { probe.revocations.push_back(std::move(value)); }
};
struct AllHooks : InputOnly {
    using InputOnly::InputOnly;
    void surface_connected(gui_surface::Capabilities value) { probe.connections.push_back(std::move(value)); }
    void surface_revoked(gui_surface::Revocation value) { probe.revocations.push_back(std::move(value)); }
};
struct BorrowedInput : LegacyApp { using LegacyApp::LegacyApp; void surface_input(gui_surface::AcceptedEvent&) {} };
struct ConstBorrowedInput : LegacyApp { using LegacyApp::LegacyApp; void surface_input(const gui_surface::AcceptedEvent&) {} };
struct RvalueConnected : LegacyApp { using LegacyApp::LegacyApp; void surface_connected(gui_surface::Capabilities&&) {} };
struct WrongReturnRevoked : LegacyApp { using LegacyApp::LegacyApp; bool surface_revoked(gui_surface::Revocation) { return true; } };
struct ExactOverloads : LegacyApp {
    using LegacyApp::LegacyApp;
    void surface_input(gui_surface::AcceptedEvent value) { probe.inputs.push_back(std::move(value)); }
    void surface_input(const gui_surface::AcceptedEvent&) { throw std::runtime_error("Borrowed overload selected"); }
};
struct NoexceptConnected : LegacyApp { using LegacyApp::LegacyApp; void surface_connected(gui_surface::Capabilities) noexcept {} };
static_assert(host::BrowserSurfaceApplication<LegacyApp> && host::BrowserSurfaceApplication<InputOnly> &&
    host::BrowserSurfaceApplication<ConnectedOnly> && host::BrowserSurfaceApplication<RevokedOnly> &&
    host::BrowserSurfaceApplication<AllHooks> && host::BrowserSurfaceApplication<ExactOverloads> &&
    host::BrowserSurfaceApplication<NoexceptConnected>);
static_assert(!host::BrowserSurfaceApplication<BorrowedInput> && !host::BrowserSurfaceApplication<ConstBorrowedInput> &&
    !host::BrowserSurfaceApplication<RvalueConnected> && !host::BrowserSurfaceApplication<WrongReturnRevoked>);
template<class App> concept SurfaceFactory = requires(const host::BrowserSurfaceComposition& policy,
                                                     host::BrowserApplicationAccess<App>& access) { policy.make_adapter(access); };
static_assert(!SurfaceFactory<BorrowedInput> && !SurfaceFactory<WrongReturnRevoked>);
static_assert(std::same_as<decltype(std::declval<host::Browser<LegacyApp, host::BrowserSurfaceComposition>&>().adapter), host::BrowserSurfaceAdapter>);
static_assert(std::same_as<decltype(std::declval<host::Browser<LegacyApp, host::BrowserSurfaceComposition>&>().session), host::BrowserSurfaceSession>);

gui_surface::Presentation presentation(std::uint64_t generation) {
    gui_surface::Presentation value; value.identity = {{"generic.button", 1}, 2, generation, 1, 1};
    value.required = host::surface_web::basic_supported; value.bounds = {0, 0, 100, 100}; value.clip = value.bounds;
    value.keys.fallback = gui_surface::Capture::capture; return value;
}
template<class Browser> Json send(Browser& browser, std::uint64_t sequence, Json operation) {
    return gui::web_detail::Parser(browser.receive(gui::web_detail::encode(Json::Object{{"epoch", "surface"},
        {"seq", std::to_string(sequence)}, {"operation", std::move(operation)}}))).parse();
}
template<class Browser> void connect(Browser& browser) {
    const auto response = send(browser, 1, Json::Object{{"type", "surfaceConnect"}, {"version", 1}, {"supported", "97"}});
    check(response.at("error").str().empty(), "Surface composition connection failed");
}
Json surface_input(const gui_surface::Presentation& value) {
    return Json::Object{{"type", "surfaceInput"}, {"identity", host::surface_web::json_presentation(value).at("identity")},
        {"sequence", "1"}, {"input", Json::Object{{"kind", "focus"}, {"focused", true}, {"active", true}, {"cause", "direct"}}}};
}
template<class App> void surface_routes() {
    Probe probe; Context context(probe); host::BrowserSurfaceComposition policy(host::surface_web::basic_supported);
    const auto generation = policy.generation(); host::Browser<App, host::BrowserSurfaceComposition> browser("surface", std::move(policy));
    connect(browser); check(browser.adapter.capabilities().supported == 97, "Explicit physical ceiling was not negotiated");
    const auto value = presentation(generation);
    check(browser.adapter.present_pair(snapshot(2), value).status == gui_surface::Status::ok, "Surface composition could not publish its own generation");
    check(send(browser, 2, surface_input(value)).at("error").str().empty(), "Surface composition rejected typed input");
    browser.adapter.present(snapshot(3));
    constexpr bool input = std::is_base_of_v<InputOnly, App> || std::same_as<App, ExactOverloads>;
    constexpr bool connected = std::same_as<App, ConnectedOnly> || std::same_as<App, AllHooks>;
    constexpr bool revoked = std::same_as<App, RevokedOnly> || std::same_as<App, AllHooks>;
    check(probe.inputs.size() == std::size_t(input) && probe.connections.size() == std::size_t(connected) &&
        probe.revocations.size() == std::size_t(revoked), "Independent optional hook was lost or fabricated");
    if constexpr (input) check(probe.inputs[0].event.identity == value.identity && probe.inputs[0].event.sequence == 1 &&
        std::holds_alternative<gui_surface::FocusChange>(probe.inputs[0].event.input), "Owned typed event changed in the hook");
    if constexpr (connected) check(probe.connections[0].supported == 97, "Owned physical capability intersection changed");
    if constexpr (revoked) check(probe.revocations[0].identity == value.identity && probe.revocations[0].held_keys.empty(),
        "Identity-only revocation was dropped or changed");
    check(probe.handles == 0, "Typed surface work was also delivered as a legacy widget event");
}
void continuing_retry_preserves_shown_ingress() {
    Probe probe; Context context(probe); host::BrowserSurfaceComposition policy(host::surface_web::basic_supported);
    const auto generation = policy.generation();
    host::Browser<InputOnly, host::BrowserSurfaceComposition> browser("surface", std::move(policy));
    connect(browser);
    auto shown = presentation(generation);
    check(browser.adapter.present_pair(snapshot(2), shown).status == gui_surface::Status::ok,
        "Surface composition could not publish the ingress basis");
    const auto retries_before_input = probe.retries;
    bool publish_newer = true;
    probe.during_retry = [&] {
        throws([&] { (void)browser.receive("{}"); }, "Retry callback reentered Browser receive");
        if (!publish_newer) return;
        publish_newer = false;
        auto newer = presentation(generation);
        newer.identity.presentation_revision = 3;
        check(browser.adapter.present_pair(snapshot(3), newer).status == gui_surface::Status::ok,
            "Metadata retry could not publish the next presentation");
    };

    const auto fresh = send(browser, 2, surface_input(shown));
    check(fresh.at("error").str().empty() && probe.inputs.size() == 1 && probe.retries == retries_before_input,
        "A current shown focus was retried into staleness before surface admission");

    const auto key = send(browser, 3, Json::Object{{"type", "surfaceInput"},
        {"identity", host::surface_web::json_presentation(shown).at("identity")}, {"sequence", "2"},
        {"input", Json::Object{{"kind", "key"}, {"phase", "down"}, {"key", "a"}, {"code", "KeyA"},
            {"location", 0}, {"modifiers", 0}, {"repeat", false}}}});
    check(key.at("error").str().empty() && probe.inputs.size() == 2 && probe.retries == retries_before_input &&
        std::holds_alternative<gui_surface::KeyTransition>(probe.inputs.back().event.input),
        "A physical key lost the focus/presentation just admitted to the caller");

    const auto progressed = send(browser, 4, Json::Object{{"type", "poll"}});
    check(progressed.at("error").str().empty() && probe.retries == retries_before_input + 1,
        "Metadata poll stopped advancing presentation retry work");
    const auto old = send(browser, 5, surface_input(shown));
    check(!old.at("error").str().empty() && old.at("error").str().find("stale_identity") != std::string::npos,
        "A genuinely old surface identity was accepted after metadata publication");

    probe.during_retry = [] {};
    const auto retries_before_malformed = probe.retries;
    throws([&] {
        (void)browser.receive(R"({"epoch":"surface","epoch":"surface","seq":"6","operation":{"type":"poll"}})");
    }, "Duplicate envelope property bypassed ordinary receive validation");
    check(probe.retries == retries_before_malformed + 1,
        "Malformed envelope classification suppressed the established retry path");
}
void retry_preserves_shown_widget_generation() {
    Probe probe; Context context(probe);
    host::Browser<LegacyApp, host::BrowserSurfaceComposition> browser("surface");
    connect(browser);
    const auto retries = probe.retries;
    probe.during_retry = [&] {
        auto next = snapshot(2); next.widgets.front().spec.key.generation = 2;
        browser.adapter.present(std::move(next));
    };
    const auto activate = [](std::uint64_t generation) {
        return Json::Object{{"type", "activate"}, {"key", gui::web_detail::key({"generic.button", generation})}};
    };
    check(send(browser, 2, activate(1)).at("error").str().empty() && probe.handles == 1 && probe.retries == retries,
        "Retry replaced the shown widget generation before ordinary activation");
    check(send(browser, 3, Json::Object{{"type", "poll"}}).at("error").str().empty() && probe.retries == retries + 1,
        "Widget-generation fixture did not publish through ordinary polling");
    probe.during_retry = {};
    const auto old = send(browser, 4, activate(1));
    check(old.at("error").str() == "Stale widget generation" && probe.handles == 1,
        "An actually retired widget generation reached the application");
    check(send(browser, 5, activate(2)).at("error").str().empty() && probe.handles == 2 && probe.retries == retries + 1,
        "Newly shown widget generation could not use the ordinary route");
}
void zero_surface_and_generation() {
    Probe probe; Context context(probe);
    { host::Browser<LegacyApp, host::BrowserSurfaceComposition> browser("surface"); connect(browser);
      check(browser.adapter.capabilities().supported == 0, "Default surface composition claimed physical support"); }
    host::BrowserSurfaceComposition first, second;
    check(first.generation() != 0 && second.generation() > first.generation(), "Native surface generation was zero or reused");
    const auto original = first.generation(); host::BrowserSurfaceComposition moved(std::move(first));
    check(first.generation() == 0 && moved.generation() == original, "Move duplicated or changed the native generation");
    host::BrowserApplicationAccess<LegacyApp> access;
    throws([&] { (void)first.make_adapter(access); }, "Moved-from composition constructed an adapter");
    auto adapter = moved.make_adapter(access);
    throws([&] { (void)moved.make_adapter(access); }, "Composition reused an adapter generation");
    throws([&] { (void)second.make_session(adapter, "surface", access); }, "Session construction preceded its adapter");
    auto session = moved.make_session(adapter, "surface", access);
    throws([&] { (void)moved.make_session(adapter, "surface", access); }, "Composition constructed a second session");
    check(!session.initial().empty(), "Unarmed standalone factory session could not serialize safely");
    throws([] { host::BrowserSurfaceComposition unsupported(gui_surface::feature(gui_surface::Feature::committed_text)); },
        "Composition accepted an unimplemented physical capability");
    std::atomic<std::uint64_t> counter{std::numeric_limits<std::uint64_t>::max() - 1};
    check(host::browser_surface_detail::next_generation(counter) == std::numeric_limits<std::uint64_t>::max() - 1 &&
        host::browser_surface_detail::next_generation(counter) == std::numeric_limits<std::uint64_t>::max() && counter.load() == 0,
        "Final native generations wrapped or were skipped");
    check(host::browser_surface_detail::next_generation(counter) == 0 && counter.load() == 0,
        "Exhausted native generation counter recovered or wrapped");
}
} // namespace
int main() {
    try {
        legacy_graph(); lifetime_and_arm(); construction_failure_and_cleanup(); entry_and_callback_guards();
        surface_routes<LegacyApp>(); surface_routes<InputOnly>(); surface_routes<ConnectedOnly>();
        surface_routes<RevokedOnly>(); surface_routes<AllHooks>(); surface_routes<ExactOverloads>();
        continuing_retry_preserves_shown_ingress(); retry_preserves_shown_widget_generation(); zero_surface_and_generation();
        std::cout << "browser composition: twelve groups passed\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
