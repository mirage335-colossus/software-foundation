// SPDX-License-Identifier: CC0-1.0
// Actual generic Browser composition and neutral editor records only. No engine,
// application implementation, provider, kernel, SDK or browser process is used.
#include "host/browser_surface_composition.hpp"
#include <array>
#include <atomic>
#include <cstdint>
#include <exception>
#include <functional>
#include <iostream>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

using namespace foundation;
using Json = gui::web_detail::Json;
namespace editor = foundation::gui_editor;

namespace {
std::size_t assertions = 0;
void check(bool value, const char* message) {
    ++assertions;
    if (!value) throw std::runtime_error(message);
}
template<class F> void throws(F&& function, const char* message) {
    ++assertions;
    try { function(); } catch (const std::exception&) { return; }
    throw std::runtime_error(message);
}
gui::Snapshot snapshot(std::uint64_t revision = 1) {
    gui::Snapshot value;
    value.revision = revision;
    value.title = "Generic editor composition fixture";
    value.client_size = {100, 100};
    gui::Widget widget;
    widget.spec.key = {"generic.editor", 1};
    widget.spec.kind = gui::Kind::button;
    widget.state.bounds = {0, 0, 100, 100};
    value.widgets.push_back(std::move(widget));
    return value;
}
struct Probe {
    int constructors = 0, shutdowns = 0, handles = 0, ticks = 0;
    int submits = 0, revokes = 0, takes = 0, resyncs = 0;
    std::atomic_uint terminal{0};
    int publications = 0;
    std::string throwing_hook;
    std::vector<editor::Packet> packets;
    std::vector<editor::Revocation> revocations;
    std::vector<gui_surface::Capabilities> connections;
    std::map<std::uint64_t, editor::EditorCompletion> completions;
    std::function<void(host::BrowserSurfaceAdapter&)> during_construct, during_shutdown, during_tick;
    std::exception_ptr shutdown_error;
    std::uint64_t next_ticket = 41;
    int editor_callbacks() const { return submits + revokes + takes + resyncs; }
};
Probe* current = nullptr;
struct Context {
    explicit Context(Probe& value) {
        check(!current, "Overlapping fixture context");
        current = &value;
    }
    ~Context() { current = nullptr; }
};
struct PlainApp {
    Probe& probe;
    gui::Adapter& adapter;
    explicit PlainApp(gui::Adapter& value) : probe(*current), adapter(value) {
        ++probe.constructors;
        if (probe.during_construct) {
            auto* actual = dynamic_cast<host::BrowserSurfaceAdapter*>(&adapter);
            check(actual, "Fake App did not receive the actual surface adapter");
            probe.during_construct(*actual);
        }
        adapter.present(snapshot());
    }
    void handle(gui::Event) { ++probe.handles; }
    void tick() {
        ++probe.ticks;
        if (probe.during_tick) {
            auto* actual = dynamic_cast<host::BrowserSurfaceAdapter*>(&adapter);
            check(actual, "Tick did not retain the actual surface adapter");
            probe.during_tick(*actual);
        }
    }
    void shutdown() {
        ++probe.shutdowns;
        if (probe.during_shutdown) {
            try {
                auto* actual = dynamic_cast<host::BrowserSurfaceAdapter*>(&adapter);
                check(actual, "Shutdown did not retain the actual surface adapter");
                probe.during_shutdown(*actual);
            }
            catch (...) { probe.shutdown_error = std::current_exception(); throw; }
        }
    }
    void retry_presentation() {}
    std::optional<gui::ServiceRequest> next_service() { return {}; }
    bool complete_service(gui::ServiceResult) { return false; }
    void qualify(const std::function<void()>& present) { present(); }
    void surface_connected(gui_surface::Capabilities value) { probe.connections.push_back(std::move(value)); }
};
struct EditorApp : PlainApp {
    using PlainApp::PlainApp;
    std::optional<std::uint64_t> editor_submit(editor::Packet value) {
        ++probe.submits;
        if (probe.throwing_hook == "submit") throw std::runtime_error("Fixture submit failure");
        probe.packets.push_back(std::move(value));
        return probe.next_ticket++;
    }
    std::optional<std::uint64_t> editor_revoke(editor::Revocation value) {
        ++probe.revokes;
        if (probe.throwing_hook == "revoke") throw std::runtime_error("Fixture revoke failure");
        probe.revocations.push_back(std::move(value));
        return probe.next_ticket++;
    }
    std::optional<editor::EditorCompletion> editor_take(std::uint64_t ticket) {
        ++probe.takes;
        if (probe.throwing_hook == "take") throw std::runtime_error("Fixture take failure");
        const auto found = probe.completions.find(ticket);
        if (found == probe.completions.end()) return {};
        auto value = std::move(found->second);
        probe.completions.erase(found);
        return value;
    }
    void editor_resync() {
        ++probe.resyncs;
        if (probe.throwing_hook == "resync") throw std::runtime_error("Fixture resync failure");
    }
};
struct MissingSubmit : EditorApp {
    using EditorApp::EditorApp;
    std::optional<std::uint64_t> editor_submit(editor::Packet) = delete;
};
struct MissingRevoke : EditorApp {
    using EditorApp::EditorApp;
    std::optional<std::uint64_t> editor_revoke(editor::Revocation) = delete;
};
struct MissingTake : EditorApp {
    using EditorApp::EditorApp;
    std::optional<editor::EditorCompletion> editor_take(std::uint64_t) = delete;
};
struct MissingResync : EditorApp {
    using EditorApp::EditorApp;
    void editor_resync() = delete;
};
struct BorrowedSubmit : EditorApp {
    using EditorApp::EditorApp;
    std::optional<std::uint64_t> editor_submit(const editor::Packet&) { return 99; }
};
struct WrongReturnTake : EditorApp {
    using EditorApp::EditorApp;
    bool editor_take(std::uint64_t) { return true; }
};
static_assert(host::Application<PlainApp> && host::Application<EditorApp>);
static_assert(host::browser_surface_detail::ExactEditorHooks<EditorApp>);
static_assert(!host::browser_surface_detail::ExactEditorHooks<PlainApp> &&
    !host::browser_surface_detail::ExactEditorHooks<MissingSubmit> &&
    !host::browser_surface_detail::ExactEditorHooks<MissingRevoke> &&
    !host::browser_surface_detail::ExactEditorHooks<MissingTake> &&
    !host::browser_surface_detail::ExactEditorHooks<MissingResync> &&
    !host::browser_surface_detail::ExactEditorHooks<BorrowedSubmit> &&
    !host::browser_surface_detail::ExactEditorHooks<WrongReturnTake>);
using EditorBrowser = host::Browser<EditorApp, host::BrowserSurfaceComposition>;
static_assert(std::same_as<decltype(std::declval<EditorBrowser&>().adapter), host::BrowserSurfaceAdapter>);
static_assert(std::same_as<decltype(std::declval<EditorBrowser&>().session), host::BrowserSurfaceSession>);

host::BrowserEditorEndpoint endpoint(Probe& probe) {
    host::BrowserEditorEndpoint value;
    value.profile = "editor_v1";
    value.protocol = 2;
    value.capabilities = 8255;
    value.terminal = {&probe, [](void* context) noexcept {
        static_cast<Probe*>(context)->terminal.fetch_add(1, std::memory_order_relaxed);
    }};
    return value;
}
host::BrowserSurfaceComposition composition(Probe& probe) {
    return host::BrowserSurfaceComposition(8255, host::surface_web::Profile::editor_v1, endpoint(probe));
}
template<class App> void rejects_before_app(host::BrowserEditorEndpoint value, Probe& probe,
                                           gui_surface::Features ceiling = 8255) {
    ++assertions;
    try {
        host::Browser<App, host::BrowserSurfaceComposition> browser("editor",
            host::BrowserSurfaceComposition(ceiling, host::surface_web::Profile::editor_v1, std::move(value)));
    } catch (const std::invalid_argument&) {
        check(probe.constructors == 0, "Editor refusal occurred after App construction");
        return;
    }
    throw std::runtime_error("Editor composition admitted an invalid endpoint or hook set");
}
template<class App> void rejects_hook_shape() {
    Probe probe;
    Context context(probe);
    rejects_before_app<App>(endpoint(probe), probe);
}
void required_hook_set() {
    rejects_hook_shape<PlainApp>();
    rejects_hook_shape<MissingSubmit>();
    rejects_hook_shape<MissingRevoke>();
    rejects_hook_shape<MissingTake>();
    rejects_hook_shape<MissingResync>();
    rejects_hook_shape<BorrowedSubmit>();
    rejects_hook_shape<WrongReturnTake>();
}
void endpoint_refusals() {
    for (const auto& mutation : std::vector<std::function<void(host::BrowserEditorEndpoint&)>>{
            [](auto& value) { value.terminal = {}; },
            [](auto& value) { value.profile = "mouse_v1"; },
            [](auto& value) { value.protocol = 1; },
            [](auto& value) { value.capabilities = 8225; },
            [](auto& value) { value.capabilities = 0; }}) {
        Probe probe;
        Context context(probe);
        auto value = endpoint(probe);
        mutation(value);
        rejects_before_app<EditorApp>(std::move(value), probe);
    }
    Probe probe;
    Context context(probe);
    rejects_before_app<EditorApp>(endpoint(probe), probe, 8225);
}

gui_surface::Presentation presentation(std::uint64_t generation, std::uint64_t revision = 2,
                                        const std::string& text = "a") {
    gui_surface::Presentation value;
    value.identity = {{"generic.editor", 1}, revision, generation, 1, 1};
    value.required = 8255;
    value.bounds = {0, 0, 100, 100};
    value.clip = value.bounds;
    value.keys.fallback = gui_surface::Capture::capture;
    gui_surface::EditorContext context;
    context.revision = revision - 1;
    context.surrounding = text;
    context.selection = {text.size(), text.size()};
    context.caret = {10, 10, 1, 12};
    context.editable = true;
    context.input_purpose = "text";
    value.editor = std::move(context);
    return value;
}
editor::Basis basis(const gui_surface::Presentation& value, std::uint64_t token = 101) {
    editor::Basis result;
    result.token = token;
    result.identity = value.identity;
    result.editor_revision = value.editor->revision;
    result.surrounding = value.editor->surrounding;
    result.selection = value.editor->selection;
    return result;
}
editor::Packet packet(const editor::Basis& value) {
    editor::Packet result;
    result.session = 9;
    result.basis = value;
    auto& observation = result.observation;
    observation.id = 1;
    observation.kind = editor::Kind::text;
    observation.authority = editor::Authority::range;
    observation.before = {"a", 1, 1, editor::Direction::none, {1, 1}, 1};
    observation.after = editor::TextObservation{"a\u03b2", 2, 2, editor::Direction::none, {3, 3}, 3};
    observation.data = editor::TextData{"insertText", "\u03b2", {1, 1}, {}};
    return result;
}
editor::Revocation revocation(const editor::Basis& value) {
    editor::Revocation result;
    result.basis = value;
    result.incarnation = 7;
    result.reason = "generic fixture retirement";
    return result;
}
template<class Receiver> Json send(Receiver& receiver, std::uint64_t sequence, Json operation,
                                   const std::string& epoch = "editor") {
    return gui::web_detail::Parser(receiver.receive(gui::web_detail::encode(Json::Object{
        {"epoch", epoch}, {"seq", std::to_string(sequence)}, {"operation", std::move(operation)}}))).parse();
}
template<class Receiver> Json connect_editor(Receiver& receiver) {
    auto response = send(receiver, 1, Json::Object{{"type", "surfaceConnect"}, {"version", 2},
        {"profile", "editor_v1"}, {"supported", "8255"}, {"mouseInputVersion", 1}});
    check(response.at("error").str().empty(), "Editor composition connection failed");
    check(response.at("surface").at("profile").str() == "editor_v1" &&
        response.at("surface").at("capabilities").at("supported").str() == "8255",
        "Editor connection lost its actual profile or capabilities");
    return response;
}
template<class Receiver> void focus_editor(Receiver& receiver, const gui_surface::Presentation& value) {
    const auto declaration = host::surface_web::json_presentation(value, host::surface_web::Profile::editor_v1, {});
    const auto response = send(receiver, 2, Json::Object{{"type", "surfaceInput"},
        {"identity", declaration.at("identity")}, {"sequence", "1"},
        {"input", Json::Object{{"kind", "focus"}, {"focused", true}, {"active", true}, {"cause", "direct"}}}});
    check(response.at("error").str().empty(), "Editor surface could not acquire generic focus");
}
editor::Basis prepare(EditorBrowser& browser) {
    connect_editor(browser);
    check(browser.adapter.capabilities().supported == 8255, "Editor adapter did not negotiate actual 8255");
    const auto surface = presentation(browser.adapter.generation());
    const auto current_basis = basis(surface);
    check(browser.adapter.present_editor_pair(snapshot(2), surface,
        editor::EditorPublication{current_basis, {}, {}, {}}, {}).status == gui_surface::Status::ok,
        "Actual editor adapter rejected the initial atomic publication");
    focus_editor(browser, surface);
    check(browser.adapter.surface_focused() && browser.adapter.active(), "Generic focus did not admit editor input");
    return current_basis;
}
void unarmed_callbacks() {
    Probe probe;
    Context context(probe);
    auto exercise = [&](host::BrowserSurfaceAdapter& adapter) {
        check(adapter.editor_endpoint_bound(), "Editor endpoint was not bound before App construction");
        check(!adapter.editor_submit(editor::Packet{}), "Unarmed submit fabricated a ticket");
        check(!adapter.editor_revoke(editor::Revocation{}), "Unarmed revoke fabricated a ticket");
        check(!adapter.editor_take(41), "Unarmed take fabricated a completion");
        adapter.editor_resync();
        check(probe.editor_callbacks() == 0 && !adapter.failed(), "Unarmed endpoint entered App or failed the owner");
    };
    probe.during_construct = exercise;
    probe.during_shutdown = exercise;
    { EditorBrowser browser("editor", composition(probe)); }
    if (probe.shutdown_error) std::rethrow_exception(probe.shutdown_error);
    check(probe.constructors == 1 && probe.shutdowns == 1, "Editor App lifetime did not finish once");

    // The real factories can negotiate and focus while their access gate has no
    // App at all. This reaches submit's wrapper beyond its ordinary focus gate.
    host::BrowserApplicationAccess<EditorApp> access;
    auto policy = composition(probe);
    auto adapter = policy.make_adapter(access);
    auto session = policy.make_session(adapter, "editor", access);
    connect_editor(session);
    const auto surface = presentation(adapter.generation());
    const auto current_basis = basis(surface);
    check(adapter.present_editor_pair(snapshot(2), surface,
        editor::EditorPublication{current_basis, {}, {}, {}}, {}).status == gui_surface::Status::ok,
        "Unarmed actual factories could not publish a neutral pair");
    focus_editor(session, surface);
    check(!session.editor_submit(packet(current_basis)) && !session.editor_revoke(revocation(current_basis)) &&
        !session.editor_take(41), "Unarmed actual factory callbacks fabricated results");
    session.editor_resync();
    check(probe.editor_callbacks() == 0 && probe.terminal.load() == 0 && !adapter.failed(),
        "Actual unarmed factory callbacks entered App or closed the endpoint");
}
editor::Receipt receipt(const editor::Packet& submitted, const editor::Basis& successor) {
    editor::Receipt value;
    value.session = submitted.session;
    value.id = submitted.observation.id;
    value.submitted_token = submitted.basis.token;
    value.predecessor = submitted.observation.predecessor;
    value.outcome = editor::Outcome::applied;
    value.basis = successor;
    return value;
}
editor::EditorCompletion completion(std::uint64_t ticket, editor::Receipt value) {
    return {ticket, {editor::Admission::completed, std::move(value), {}}};
}
void queue_then_tick_publication() {
    Probe probe;
    Context context(probe);
    EditorBrowser browser("editor", composition(probe));
    const auto initial = prepare(browser);
    check(probe.connections.size() == 1 && probe.connections.front().supported == 8255,
        "Editor connection callback lost its owned capabilities");
    auto submitted = packet(initial);
    const auto expected = submitted;
    const auto ticks_before = probe.ticks;
    const auto ticket = browser.session.editor_submit(submitted);
    check(ticket == std::optional<std::uint64_t>{41}, "Owned submit did not return the App ticket");
    submitted.basis.surrounding = "changed after submission";
    std::get<editor::TextData>(submitted.observation.data).text = "changed after submission";
    check(probe.packets == std::vector{expected}, "Editor callback retained borrowed packet data");
    check(probe.ticks == ticks_before && probe.publications == 0 &&
        browser.adapter.editor_publication()->basis == std::optional{initial},
        "Submit advanced work or presented inside its callback");
    check(!browser.session.editor_take(*ticket), "Queued observation fabricated an early completion");

    const auto surface = presentation(browser.adapter.generation(), 3, "a\u03b2");
    const auto successor = basis(surface, 102);
    const editor::Settlement tag{expected.session, expected.observation.id,
        expected.basis.token, expected.observation.predecessor};
    probe.during_tick = [&](host::BrowserSurfaceAdapter& adapter) {
        if (probe.publications) return;
        check(probe.packets.size() == 1 && probe.packets.front().observation.after.has_value(),
            "Normal Session tick did not retain one owned queued observation");
        const auto queued = std::move(probe.packets.front());
        probe.packets.erase(probe.packets.begin());
        const auto queued_surface = presentation(adapter.generation(), 3, queued.observation.after->value);
        const auto queued_basis = basis(queued_surface, 102);
        const editor::Settlement queued_tag{queued.session, queued.observation.id,
            queued.basis.token, queued.observation.predecessor};
        check(adapter.present_editor_pair(snapshot(3), queued_surface,
            editor::EditorPublication{queued_basis, queued_tag, {}, {}}, {}).status == gui_surface::Status::ok,
            "Normal Session tick could not publish its exact editor pair");
        const auto* published = adapter.editor_publication();
        check(published && published->basis == std::optional{successor} && published->settlement == std::optional{tag},
            "Editor basis and settlement were not visible atomically");
        ++probe.publications;
        probe.completions.emplace(*ticket, completion(*ticket, receipt(queued, queued_basis)));
    };
    const auto response = send(browser, 3, Json::Object{{"type", "poll"}});
    check(response.at("error").str().empty() && probe.ticks == ticks_before + 1 && probe.publications == 1 && probe.packets.empty(),
        "Ordinary Session poll did not advance exactly one queued publication");
    check(response.at("snapshot").at("revision").str() == "3" &&
        response.at("editor").at("basis").at("token").str() == "102" &&
        response.at("editor").at("settlement").at("submittedToken").str() == "101",
        "Snapshot and checked editor metadata did not share one response");
    const auto checked = browser.session.editor_take_json(*ticket);
    check(checked.at("ticket").str() == "41" && checked.at("admission").str() == "completed" &&
        checked.at("receipt").at("basis").at("token").str() == "102",
        "Typed completion lost its ticket or checked receipt");
    check(std::holds_alternative<std::nullptr_t>(browser.session.editor_take_json(*ticket).value),
        "Taken completion was replayed");

    auto retired = revocation(successor);
    const auto expected_retirement = retired;
    const auto retired_ticket = browser.session.editor_revoke(retired);
    retired.reason = "changed after revocation";
    check(retired_ticket == std::optional<std::uint64_t>{42} &&
        probe.revocations == std::vector{expected_retirement} && probe.publications == 1,
        "Revocation was borrowed, lost its ticket, or published synchronously");
    browser.session.editor_resync();
    check(probe.resyncs == 1 && probe.publications == 1, "Resync was lost or published inside its callback");
}
void completion_requires_publication() {
    Probe probe;
    Context context(probe);
    EditorBrowser browser("editor", composition(probe));
    const auto initial = prepare(browser);
    const auto submitted = packet(initial);
    const auto ticket = browser.session.editor_submit(submitted);
    check(ticket.has_value(), "Publication-order fixture did not admit its owned head");
    const auto successor = basis(presentation(browser.adapter.generation(), 3, "a\u03b2"), 102);
    probe.completions.emplace(*ticket, completion(*ticket, receipt(submitted, successor)));
    throws([&] { (void)browser.session.editor_take_json(*ticket); },
        "Completion escaped before its exact paired publication");
    check(browser.adapter.failed() && browser.adapter.closed() && probe.terminal.load() == 1 &&
        !browser.adapter.accepted() && !browser.adapter.editor_publication(),
        "Unpublished completion did not close and retire the actual endpoint");
}
void throwing_hooks_close() {
    for (const std::string hook : {"submit", "revoke", "take", "resync"}) {
        Probe probe;
        Context context(probe);
        EditorBrowser browser("editor", composition(probe));
        const auto current_basis = prepare(browser);
        std::uint64_t ticket = 41;
        if (hook == "take") {
            const auto accepted = browser.session.editor_submit(packet(current_basis));
            check(accepted.has_value(), "Throwing take fixture did not obtain an actual ticket");
            ticket = *accepted;
        }
        const std::array before{probe.submits, probe.revokes, probe.takes, probe.resyncs};
        probe.throwing_hook = hook;
        throws([&] {
            if (hook == "submit") (void)browser.session.editor_submit(packet(current_basis));
            else if (hook == "revoke") (void)browser.session.editor_revoke(revocation(current_basis));
            else if (hook == "take") (void)browser.session.editor_take(ticket);
            else browser.session.editor_resync();
        }, "Throwing editor hook did not fail its actual endpoint call");
        const std::array after{probe.submits, probe.revokes, probe.takes, probe.resyncs};
        const std::array<std::string, 4> names{"submit", "revoke", "take", "resync"};
        for (std::size_t i = 0; i < names.size(); ++i)
            check(after[i] == before[i] + int(hook == names[i]),
                "Throwing fixture failed before the selected hook or entered a second hook");
        check(browser.adapter.failed() && browser.adapter.closed() && probe.terminal.load() == 1 &&
            !browser.adapter.accepted() && !browser.adapter.editor_publication(),
            "Throwing editor hook left input authority or missed terminal notification");
        const auto callbacks = probe.editor_callbacks();
        check(!browser.adapter.editor_submit(packet(current_basis)) &&
            !browser.adapter.editor_revoke(revocation(current_basis)) && !browser.adapter.editor_take(41),
            "Terminal endpoint fabricated a later ticket or completion");
        browser.adapter.editor_resync();
        check(probe.editor_callbacks() == callbacks && probe.terminal.load() == 1,
            "Terminal endpoint reentered App or repeated terminal notification");
    }
}
void legacy_and_mouse_unchanged() {
    {
        Probe probe;
        Context context(probe);
        host::Browser<PlainApp> browser("legacy");
        static_assert(std::same_as<decltype(browser.adapter), gui::WebAdapter>);
        const auto response = gui::web_detail::Parser(browser.initial()).parse();
        const auto& object = std::get<Json::Object>(response.value);
        check(object.size() == 6 && !object.contains("surface") && !object.contains("editor"),
            "Default Browser changed its legacy response vocabulary");
        check(send(browser, 1, Json::Object{{"type", "activate"},
            {"key", gui::web_detail::key({"generic.editor", 1})}}, "legacy").at("error").str().empty() &&
            probe.handles == 1, "Default legacy activation stopped reaching App");
    }
    for (const bool mouse : {false, true}) {
        Probe probe;
        Context context(probe);
        const auto profile = mouse ? host::surface_web::Profile::mouse_v1 : host::surface_web::Profile::legacy;
        const auto features = mouse ? 8225u : 97u;
        host::Browser<PlainApp, host::BrowserSurfaceComposition> browser("editor",
            host::BrowserSurfaceComposition(features, profile));
        Json::Object operation{{"type", "surfaceConnect"}, {"version", 1}, {"supported", std::to_string(features)}};
        if (mouse) operation.emplace("mouseInputVersion", 1);
        const auto response = send(browser, 1, Json{std::move(operation)});
        check(response.at("error").str().empty() && browser.adapter.capabilities().supported == features &&
            !browser.adapter.editor_endpoint_bound(), "Existing generic legacy/mouse composition changed negotiation");
        check(!std::get<Json::Object>(response.value).contains("editor") && probe.editor_callbacks() == 0,
            "Legacy/mouse composition acquired an editor vocabulary or callback");
    }
}
} // namespace
int main() {
    try {
        required_hook_set();
        endpoint_refusals();
        unarmed_callbacks();
        queue_then_tick_publication();
        completion_requires_publication();
        throwing_hooks_close();
        legacy_and_mouse_unchanged();
        std::cout << "browser editor composition: seven groups, " << assertions << " assertions passed\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
