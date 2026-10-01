#include "application.hpp"

#include <gui/layout.hpp>
#include <algorithm>
#include <limits>
#include <type_traits>

namespace foundation::ui {

Application::Application(gui::Adapter& adapter) : adapter_(adapter) {
    view_.title = "Entry list";
    for (const auto& definition : view_definition)
        if (!definition.remove_extension) add(definition);
    get("entries.editor").spec.text_policy = {false, false, foundation::Store::max_text_bytes, gui::SubmitKey::enter};
    get("entries.options").state.options = {{"clear", "Clear entries", "", true},
                                           {"heading", "Change heading", "", true}};
    auto& entries = get("entries.list");
    entries.spec.row_height = 32;
    entries.spec.follow_tail = true;
    publish();
}

gui::Widget& Application::add(const ViewDefinition& definition) {
    gui::Widget widget;
    widget.spec.key.id = definition.id;
    widget.spec.kind = definition.kind;
    if (definition.id != view_definition.front().id) widget.spec.parent = view_definition.front().id;
    widget.state.text = definition.text;
    widget.state.label = definition.label;
    widget.state.placeholder = definition.placeholder;
    widget.state.font.bold = definition.bold;
    widget.state.wrap = definition.wrap;
    view_.widgets.push_back(std::move(widget));
    return view_.widgets.back();
}

gui::Widget& Application::lookup(gui::Snapshot& view, std::string_view id) {
    for (auto& widget : view.widgets)
        if (widget.spec.key.id == id) return widget;
    throw std::logic_error("Missing application widget");
}

void Application::append_entry() {
    const auto& text = get("entries.editor").state.text;
    try {
        // Core owns collection validation, capacity, identity and mutation.
        entries_.add(text);
        get("entries.editor").state.text.clear();
        status_ = "Entry added";
        status_error_ = false;
    } catch (const std::invalid_argument& error) {
        status_ = error.what();
        status_error_ = true;
    } catch (const std::length_error& error) {
        status_ = error.what();
        status_error_ = true;
    }
}

void Application::handle(gui::Event event) {
    if (adapter_.closed()) return;
    // Closing must remain possible even if measurement or painting fails.
    if (std::holds_alternative<gui::CloseEvent>(event)) {
        services_.shutdown();
        presentation_pending_ = false;
        adapter_.close();
        return;
    }
    // Reject queued stale edits against authoritative state, not old pixels.
    if (!gui::normalize_event(view_, event, [this](const gui::WidgetKey& key) {
            return adapter_.scroll_offset(key);
        })) return;
    if (const auto* resize = std::get_if<gui::ResizeEvent>(&event)) {
        view_.client_size = resize->client_size;
        view_.display_scale = resize->display_scale;
    } else if (const auto* widget = std::get_if<gui::WidgetEvent>(&event)) {
        auto& current = get(widget->target.id);
        std::visit([&](const auto& input) {
            using T = std::decay_t<decltype(input)>;
            if constexpr (std::is_same_v<T, gui::EditText>) {
                current.state.text = input.value;
                status_ = "Ready";
                status_error_ = false;
            } else if constexpr (std::is_same_v<T, gui::Activate>) {
                if (widget->target.id == "entries.add") append_entry();
                else if (widget->target.id == "entries.remove") {
                    auto& list = get("entries.list").state;
                    for (const auto& record : entries_.snapshot())
                        if (list.selected == std::to_string(record.id)) entries_.erase(record.id);
                    list.selected.reset();
                    status_ = "Entry removed";
                    status_error_ = false;
                }
            } else if constexpr (std::is_same_v<T, gui::SubmitText>) {
                append_entry();
            } else if constexpr (std::is_same_v<T, gui::ChooseOption>) {
                if (input.id == "clear") {
                    for (const auto& record : entries_.snapshot()) entries_.erase(record.id);
                    get("entries.list").state.selected.reset();
                    status_ = "Entries cleared";
                    status_error_ = false;
                } else if (input.id == "heading") {
                    if (next_service_ == std::numeric_limits<std::uint64_t>::max())
                        throw std::overflow_error("Service identity exhausted");
                    gui::ServiceRequest request;
                    request.id = next_service_;
                    request.kind = gui::ServiceKind::prompt;
                    request.title = "Change heading";
                    request.value = get("entries.heading").state.text;
                    request.byte_limit = 80;
                    if (!services_.enqueue(std::move(request)))
                        throw std::logic_error("Service request rejected");
                    ++next_service_;
                }
            } else if constexpr (std::is_same_v<T, gui::SelectRecord>) {
                for (const auto& record : entries_.snapshot())
                    if (input.id == std::to_string(record.id)) current.state.selected = input.id;
            }
        }, widget->input);
    }
    publish();
}

void Application::enable_remove_feature() {
    if (remove_feature_ || adapter_.closed()) return;
    for (const auto& definition : view_definition)
        if (definition.remove_extension) add(definition);
    remove_feature_ = true;
    publish();
}

void Application::qualify(const std::function<void()>& present) {
    const auto require = [](bool condition, const char* message) {
        if (!condition) throw std::runtime_error(message);
    };
    require(entries_.snapshot().empty(), "Qualification requires a fresh application");
    const auto step = [&] {
        present();
        require(!adapter_.closed() && !presentation_pending_, "Qualification presentation failed");
    };
    const auto edit = [&](std::string text) {
        handle(gui::WidgetEvent{{"entries.editor", 1},
            gui::EditText{std::move(text), get("entries.editor").state.text}});
        step();
    };
    const auto activate = [&](std::string id) {
        handle(gui::WidgetEvent{{std::move(id), 1}, gui::Activate{}});
        step();
    };
    step();
    edit("Rejected \xc3\xa9"); activate("entries.add");
    require(entries_.snapshot().empty() && get("entries.status").state.font.tone == gui::Tone::error,
            "Qualification lost core validation");
    edit("First entry"); activate("entries.add");
    edit("Second entry"); activate("entries.add");
    require(get("entries.list").state.records.size() == 2, "Qualification lost submitted entries");
    enable_remove_feature(); step();
    handle(gui::WidgetEvent{{"entries.list", 1},
        gui::SelectRecord{get("entries.list").state.records.front().id}}); step();
    activate("entries.remove");
    const auto records = entries_.snapshot();
    require(records.size() == 1 && records.front().text == "Second entry", "Qualification removed the wrong entry");
    require(get("entries.editor").state.text.empty() && !get("entries.remove").state.enabled,
            "Qualification left inconsistent controls");
    handle(gui::ResizeEvent{{800, 640}, 1}); step();
    require(get("entries.editor").state.bounds.width > 0, "Qualification lost shared layout");
}

std::optional<gui::ServiceRequest> Application::next_service() {
    return services_.begin_next();
}

bool Application::complete_service(gui::ServiceResult result) {
    if (!services_.complete(result)) return false;
    if (result.status == gui::ServiceStatus::success)
        get("entries.heading").state.text = std::move(result.value);
    else if (result.status == gui::ServiceStatus::error)
        get("entries.heading").state.text = std::move(result.error);
    publish();
    return true;
}

void Application::retry_presentation() {
    if (presentation_pending_ && !adapter_.closed()) publish();
}

void Application::publish() {
    presentation_pending_ = true;
    auto next = view_;
    auto& list = lookup(next, "entries.list").state;
    list.records.clear();
    for (const auto& entry : entries_.snapshot()) {
        gui::Record record;
        record.id = std::to_string(entry.id);
        record.accessible_text = entry.text;
        record.cells = {{entry.text, {}, {}}};
        list.records.push_back(std::move(record));
    }
    if (list.selected && std::none_of(list.records.begin(), list.records.end(),
        [&](const gui::Record& row) { return list.selected == row.id; })) list.selected.reset();
    lookup(next, "entries.count").state.text = std::to_string(list.records.size()) + " entries";
    lookup(next, "entries.status").state.text = status_;
    lookup(next, "entries.status").state.font.tone = status_error_ ? gui::Tone::error : gui::Tone::muted;
    gui::LayoutNode panel;
    panel.id = "entries.form";
    panel.kind = gui::LayoutKind::column;
    panel.padding = {8, 8, 8, 8};
    panel.gap = 8;
    const auto child = [&](const std::string& id, double height) {
        gui::LayoutNode node;
        node.id = id;
        node.height = height;
        panel.children.push_back(std::move(node));
    };
    for (const auto& definition : view_definition)
        if (definition.id != panel.id && (!definition.remove_extension || remove_feature_))
            child(std::string(definition.id), definition.height);
    const auto width = std::max(0.0, next.client_size.width - 32);
    const auto height = std::max(0.0, next.client_size.height - 32);
    const auto boxes = gui::compose_layout(panel, {16, 16, width, height},
        [&](std::string_view id, double available) {
            const auto& widget = lookup(next, id);
            if (widget.spec.kind != gui::Kind::label) return gui::Size{available, 0};
            return adapter_.measure_text({widget.state.text, widget.state.font,
                available, next.display_scale, widget.state.wrap});
        });
    for (const auto& box : gui::flatten_layout(boxes))
        lookup(next, box.id).state.bounds = box.bounds;
    auto& group = lookup(next, "entries.form").state;
    group.content_size = {boxes.content.width, boxes.content.height};
    group.bounds.height = std::min(height, boxes.bounds.height);
    group.content_clip = gui::Rect{8, 8, std::max(0.0, width - 16),
                                  std::max(0.0, group.bounds.height - 16)};
    list.content_size.width = list.bounds.width;
    for (auto& record : list.records)
        record.cells.front().bounds = {4, 0, std::max(0.0, list.bounds.width - 8), 32};
    lookup(next, "entries.add").state.enabled =
        !lookup(next, "entries.editor").state.text.empty() && list.records.size() < entry_limit_;
    if (remove_feature_) lookup(next, "entries.remove").state.enabled = list.selected.has_value();
    ++next.revision;
    adapter_.present(next);
    view_ = std::move(next);
    presentation_pending_ = false;
}

} // namespace foundation::ui
