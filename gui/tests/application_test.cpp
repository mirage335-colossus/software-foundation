#include "shared/application.hpp"
#include <gui/framebuffer.hpp>
#include <gui/memory_adapter.hpp>
#include <gui/terminal.hpp>

#include <iostream>
#include <type_traits>

namespace {
void check(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

const gui::Widget& widget(const gui::Snapshot& view, std::string id) {
    const auto* found = gui::find_widget(view, {std::move(id), 1});
    if (!found) throw std::runtime_error("Missing fixture control");
    return *found;
}

template<class Adapter> void edit(Adapter& adapter, const std::string& text) {
    check(adapter.focus(gui::WidgetKey{"entries.editor", 1}), "Editor cannot receive focus");
    adapter.key(gui::Key::select_all);
    if constexpr (std::is_same_v<Adapter, gui::TerminalAdapter>)
        adapter.input("\x1b[200~" + text + "\x1b[201~");
    else adapter.text(text);
}

template<class Adapter> void activate(Adapter& adapter, std::string id) {
    const gui::WidgetKey key{std::move(id), 1};
    if constexpr (std::is_same_v<Adapter, gui::TerminalAdapter>) {
        check(adapter.focus(key), "Button cannot receive focus");
        adapter.input("\r");
    } else {
        const auto area = adapter.resolved_availability(key).bounds;
        adapter.pointer({gui::PointerKind::click,
            {area.x + area.width / 2, area.y + area.height / 2}});
    }
}

template<class Adapter> gui::Snapshot scenario() {
    foundation::ui::Application* current = nullptr;
    Adapter adapter([&](const gui::Event& event) { if (current) current->handle(event); });
    foundation::ui::Application app(adapter);
    current = &app;
    check(!widget(app.view(), "entries.add").state.enabled, "Empty entry accepted");
    edit(adapter, "\xc3\xa9");
    activate(adapter, "entries.add");
    check(widget(app.view(), "entries.list").state.records.empty(), "Invalid core input changed collection");
    check(widget(app.view(), "entries.editor").state.text == "\xc3\xa9", "Rejected input was lost");
    check(widget(app.view(), "entries.status").state.text == "text must contain printable ASCII only",
          "Core validation error did not reach the shared status label");
    check(widget(app.view(), "entries.status").state.font.tone == gui::Tone::error, "Validation error is not marked");
    edit(adapter, std::string(foundation::Store::max_text_bytes + 1, 'x'));
    check(widget(app.view(), "entries.editor").state.text == "\xc3\xa9", "Oversized native replacement changed editor");
    edit(adapter, "First entry");
    activate(adapter, "entries.add");
    check(widget(app.view(), "entries.list").state.records.size() == 1, "Entry missing");
    check(widget(app.view(), "entries.editor").state.text.empty(), "Editor did not clear");
    check(widget(app.view(), "entries.status").state.text == "Entry added", "Validation did not recover");
    edit(adapter, "Second entry");
    // A stale queued full replacement must not overwrite the newer value.
    app.handle(gui::WidgetEvent{{"entries.editor", 1}, gui::EditText{"Obsolete", "First entry"}});
    check(widget(app.view(), "entries.editor").state.text == "Second entry", "Stale edit accepted");
    activate(adapter, "entries.add");
    // This adds a real control, meaning and layout solely in shared code.
    app.enable_remove_feature();
    adapter.focus(gui::WidgetKey{"entries.list", 1});
    adapter.key(gui::Key::down);
    check(widget(app.view(), "entries.remove").state.enabled, "New feature not enabled");
    activate(adapter, "entries.remove");
    check(widget(app.view(), "entries.list").state.records.size() == 1, "New feature failed");
    check(widget(app.view(), "entries.list").state.records.front().accessible_text == "Second entry",
          "New feature removed the wrong stable record");
    app.handle(gui::WidgetEvent{{"entries.remove", 0}, gui::Activate{}});
    check(widget(app.view(), "entries.list").state.records.size() == 1, "Stale generation accepted");

    check(adapter.open_popup({"entries.options", 1}), "Menu did not open");
    adapter.key(gui::Key::down);
    adapter.key(gui::Key::enter);
    auto request = app.next_service();
    check(request.has_value(), "Generic service request missing");
    check(app.complete_service({request->id, gui::ServiceStatus::success, "Updated heading", {}}),
          "Service completion rejected");
    check(!app.complete_service({request->id, gui::ServiceStatus::success, "Repeated", {}}),
          "Service completion repeated");
    check(widget(app.view(), "entries.heading").state.text == "Updated heading", "Heading not updated");

    adapter.resize({800, 640}, 1.25);
    check(app.view().display_scale == 1.25, "Resize scale lost");
    if constexpr (std::is_same_v<Adapter, gui::TerminalAdapter>) {
        check(!adapter.render().empty(), "Terminal produced no cells");
    } else {
        const auto retained = adapter.frame();
        check(retained.width == 1000 && retained.height == 800 && retained.pixels,
              "Framebuffer failed to render scaled geometry");
        adapter.resize({640, 480});
        check(retained.pixels->size() == 1000u * 800u * 3u, "Frame ownership was not retained");
        adapter.resize({800, 640}, 1.25);
    }
    const auto result = app.view();
    // Small and zero-size views preserve state and recover through shared layout.
    adapter.resize({80, 64});
    adapter.resize({0, 0});
    adapter.resize({800, 640}, 1.25);
    app.handle(gui::CloseEvent{});
    app.handle(gui::WidgetEvent{{"entries.add", 1}, gui::Activate{}});
    check(adapter.closed() && !app.presentation_pending(), "Close did not finish");
    return result;
}

class FailingAdapter final : public gui::RetainedAdapter {
public:
    FailingAdapter() : gui::RetainedAdapter({}, [](const gui::TextMeasureRequest& request) {
        return gui::Size{request.available_width, 16};
    }) {}
    bool fail = false;
    void present(gui::Snapshot view) override {
        if (fail) throw std::runtime_error("Injected presentation failure");
        gui::RetainedAdapter::present(std::move(view));
    }
};

void recovery() {
    FailingAdapter adapter;
    foundation::ui::Application app(adapter);
    adapter.fail = true;
    try {
        app.handle(gui::WidgetEvent{{"entries.editor", 1}, gui::EditText{"Accepted value", ""}});
        throw std::logic_error("Expected presentation failure");
    } catch (const std::runtime_error&) {}
    check(app.presentation_pending(), "Presentation debt disappeared");
    check(widget(app.view(), "entries.editor").state.text == "Accepted value", "Accepted edit rolled back");
    adapter.fail = false;
    app.retry_presentation();
    check(!app.presentation_pending(), "Presentation did not recover");
    check(widget(adapter.snapshot(), "entries.editor").state.text == "Accepted value", "Retry lost edit");
    adapter.fail = true;
    try {
        app.handle(gui::WidgetEvent{{"entries.add", 1}, gui::Activate{}});
        throw std::logic_error("Expected presentation failure after core mutation");
    } catch (const std::runtime_error&) {}
    check(app.presentation_pending(), "Core mutation lost presentation debt");
    adapter.fail = false;
    app.retry_presentation();
    app.retry_presentation();
    check(widget(app.view(), "entries.list").state.records.size() == 1,
          "Presentation retry lost or repeated core mutation");
    adapter.fail = true;
    app.handle(gui::CloseEvent{});
    check(adapter.closed(), "Painting failure blocked shutdown");
}
} // namespace

int main() {
    try {
        const auto terminal = scenario<gui::TerminalAdapter>();
        const auto framebuffer = scenario<gui::FramebufferAdapter>();
        check(terminal.widgets.size() == framebuffer.widgets.size(), "Backend changed widget inventory");
        for (std::size_t i = 0; i < terminal.widgets.size(); ++i) {
            check(terminal.widgets[i].spec == framebuffer.widgets[i].spec, "Backend changed feature declaration");
            check(terminal.widgets[i].state.bounds == framebuffer.widgets[i].state.bounds, "Backend changed layout");
            check(terminal.widgets[i].state.text == framebuffer.widgets[i].state.text, "Backend changed values");
            check(terminal.widgets[i].state.records == framebuffer.widgets[i].state.records, "Backend changed rows");
        }
        recovery();
        std::cout << "Shared feature, real input boundaries, layout, lifecycle and retry checks passed\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
