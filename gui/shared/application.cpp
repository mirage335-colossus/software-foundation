#include "application.hpp"

#include <gui/layout.hpp>
#include <algorithm>
#include <limits>
#include <type_traits>

namespace foundation::ui {

Application::Application(gui::Adapter& adapter) : adapter_(adapter) {
    view_.title = "Entry list";
    add("entries.form", gui::Kind::group);
    auto& heading = add("entries.heading", gui::Kind::label, "entries.form");
    heading.state.text = "Entry list";
    heading.state.font.bold = true;
    auto& editor = add("entries.editor", gui::Kind::text, "entries.form");
    editor.state.label = "New entry";
    editor.state.placeholder = "Type an entry";
    editor.spec.text_policy = {false, false, foundation::Store::max_text_bytes, gui::SubmitKey::enter};
    add("entries.add", gui::Kind::button, "entries.form").state.label = "Add entry";
    auto& options = add("entries.options", gui::Kind::menu, "entries.form");
    options.state.label = "Actions";
    options.state.options = {{"clear", "Clear entries", "", true},
                             {"heading", "Change heading", "", true}};
    auto& entries = add("entries.list", gui::Kind::list, "entries.form");
    entries.state.label = "Entries";
    entries.state.placeholder = "No entries";
    entries.spec.row_height = 32;
    entries.spec.follow_tail = true;
    add("entries.count", gui::Kind::label, "entries.form");
    add("entries.status", gui::Kind::label, "entries.form").state.wrap = gui::TextWrap::word;
    publish();
}

gui::Widget& Application::add(std::string id, gui::Kind kind, std::string parent) {
    gui::Widget widget;
    widget.spec.key.id = std::move(id);
    widget.spec.kind = kind;
    widget.spec.parent = std::move(parent);
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
    add("entries.remove", gui::Kind::button, "entries.form").state.label = "Remove selected";
    remove_feature_ = true;
    publish();
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
    child("entries.heading", 32);
    child("entries.editor", 32);
    child("entries.add", 32);
    child("entries.options", 32);
    child("entries.list", 128);
    child("entries.count", 32);
    child("entries.status", 32);
    if (remove_feature_) child("entries.remove", 32);
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
