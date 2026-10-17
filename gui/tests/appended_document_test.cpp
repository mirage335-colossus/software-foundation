#include "shared/appended_document.hpp"

#include <gui/terminal.hpp>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace {
using namespace foundation::ui;

void check(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
template<class Function> void rejects(Function function, const char* message) {
    bool rejected = false;
    try { function(); } catch (const std::invalid_argument&) { rejected = true; }
    check(rejected, message);
}
DocumentNode element(std::uint64_t id, std::uint64_t parent, std::string tag) {
    DocumentNode node;
    node.id = id; node.parent = parent; node.tag = std::move(tag);
    return node;
}
DocumentNode text(std::uint64_t id, std::uint64_t parent, std::string value,
                  DocumentWhiteSpace white_space = DocumentWhiteSpace::normal) {
    DocumentNode node;
    node.id = id; node.parent = parent; node.kind = DocumentNodeKind::text;
    node.text = std::move(value); node.white_space = white_space;
    return node;
}
DocumentSnapshot document(std::vector<DocumentNode> children) {
    DocumentSnapshot value;
    value.version = {7, 11, 13};
    value.nodes.push_back(element(1, 0, "body"));
    for (auto& node : children) value.nodes.push_back(std::move(node));
    return value;
}
gui::TextMeasure measure(gui::TerminalAdapter& terminal) {
    return [&terminal](const gui::TextMeasureRequest& request) {
        return terminal.measure_text(request);
    };
}
std::string row_text(const DocumentProjection& projection) {
    std::string result;
    for (const auto& row : projection.rows) { result += row.text; result += '\n'; }
    return result;
}
std::string cells(gui::TerminalAdapter& terminal) {
    std::string result;
    for (const auto& row : terminal.render()) { result += row; result += '\n'; }
    return result;
}
std::string presentation_text(const gui::Snapshot& view) {
    std::string result = view.title;
    for (const auto& widget : view.widgets) {
        const auto& state = widget.state;
        for (const auto* value : {&state.label, &state.text, &state.help, &state.accessible_name,
                                  &state.placeholder, &state.display_text}) result += *value;
        for (const auto& option : state.options) result += option.label + option.value;
        for (const auto& action : state.actions) result += action.label + action.value;
        for (const auto& record : state.records) {
            result += record.accessible_text;
            for (const auto& cell : record.cells) result += cell.text;
        }
    }
    return result;
}
const DocumentRow& action_row(const DocumentProjection& projection, std::uint64_t node) {
    const auto row = std::find_if(projection.rows.begin(), projection.rows.end(),
        [node](const DocumentRow& value) { return value.node == node && value.activatable; });
    check(row != projection.rows.end(), "An enabled document action has no activatable row");
    return *row;
}
void retained_after_rejection(AppendedDocument& current, DocumentSnapshot candidate) {
    const auto previous = *current.snapshot();
    rejects([&] { current.accept(std::move(candidate)); }, "Malformed document snapshot was accepted");
    check(current.snapshot() && *current.snapshot() == previous,
          "Rejected document snapshot partially replaced authoritative state");
}

void prose_and_preformatted_reflow() {
    gui::TerminalAdapter terminal;
    AppendedDocument current;
    auto pre_wrap = element(8, 1, "p"); pre_wrap.white_space = DocumentWhiteSpace::pre_wrap;
    current.accept(document({element(2, 1, "p"), text(3, 2, "alpha   beta\t gamma delta epsilon"),
        element(4, 1, "p"), text(5, 4, "second paragraph"), element(6, 1, "pre"),
        text(7, 6, "  kept  spaces\n012345678901234567890123456789", DocumentWhiteSpace::pre),
        pre_wrap, text(9, 8, "  wrapped  spaces  stay")}));
    const auto narrow = current.project(20, 12, measure(terminal));
    const auto wide = current.project(80, 12, measure(terminal));
    gui::validate_snapshot(narrow.view); gui::validate_snapshot(wide.view);
    const auto narrow_text = row_text(narrow), wide_text = row_text(wide);
    check(wide_text.find("alpha beta gamma delta epsilon") != std::string::npos,
          "Ordinary document whitespace did not collapse between words");
    check(narrow_text.find("alpha beta gamma delta epsilon") == std::string::npos,
          "Explicit 20-column projection retained an 80-column prose line");
    check(narrow.rows.size() > wide.rows.size(), "Narrow prose projection did not reflow");
    for (const auto& row : narrow.rows) {
        bool ordinary = false;
        for (const auto& source : row.sources) if (source.first.node == 3) ordinary = true;
        if (ordinary) check(terminal.measure_text({row.text, {}, 10000, 1, gui::TextWrap::none}).width <= 19 * 8,
                            "Reflowed prose extends beyond its explicit column budget");
        bool first = false, second = false;
        for (const auto& source : row.sources) { first |= source.first.node == 3; second |= source.first.node == 5; }
        check(!first || !second, "Separate paragraphs were joined into one display row");
    }
    check(narrow_text.find("  kept  spaces\n012345678901234567890123456789") != std::string::npos,
          "Preformatted whitespace, line breaks or horizontal overflow were lost");
    check(wide_text.find("  wrapped  spaces  stay") != std::string::npos,
          "Pre-wrap content collapsed meaningful whitespace");
    terminal.terminal_size(20, 12); terminal.present(narrow.view);
    const auto visible = cells(terminal);
    check(visible.find("alpha beta") != std::string::npos && visible.find("kept  spaces") != std::string::npos,
          "Projected document prose is missing from actual terminal cells");
    AppendedDocument hard_break;
    hard_break.accept(document({element(2, 1, "pre"), text(3, 2, "a\n")}));
    const auto trailing = hard_break.project(20, 12, measure(terminal));
    check(trailing.rows.size() == 2 && trailing.rows[0].text == "a" && trailing.rows[1].text.empty(),
          "A trailing preformatted hard line break lost its final empty line");
}

void unicode_sources_and_cross_node_selection() {
    const std::string unicode = "A\xc3\xa9\xf0\x9f\x99\x82Z";
    gui::TerminalAdapter terminal;
    auto source = document({element(2, 1, "p"), text(3, 2, unicode), text(4, 2, "other"),
        text(5, 2, "e\xcc\x81")});
    source.selection = DocumentSelection{{3, 2}, {3, 4}};
    AppendedDocument current; current.accept(source);
    const auto projection = current.project(20, 10, measure(terminal));
    check(projection.selection == source.selection, "Projection changed DOM UTF-16 selection offsets");
    bool mapped_emoji = false;
    for (const auto& row : projection.rows) for (const auto& span : row.sources) {
        check(span.begin <= span.end && span.end <= row.text.size(), "Source span escaped its displayed row");
        check(span.begin == row.text.size() || (static_cast<unsigned char>(row.text[span.begin]) & 0xc0) != 0x80,
              "Source span starts inside a UTF-8 codepoint");
        check(span.end == row.text.size() || (static_cast<unsigned char>(row.text[span.end]) & 0xc0) != 0x80,
              "Source span ends inside a UTF-8 codepoint");
        if (span.first == DocumentPoint{3, 2} && span.last == DocumentPoint{3, 4}) {
            mapped_emoji = row.text.substr(span.begin, span.end - span.begin) == "\xf0\x9f\x99\x82";
        }
    }
    check(mapped_emoji, "Supplementary Unicode display bytes did not map to the two-unit DOM range");
    const DocumentSelection cross{{3, 1}, {4, 4}}, reverse{{4, 4}, {3, 1}};
    const auto forward = current.select(projection, cross), backward = current.select(projection, reverse);
    check(forward && forward->action == DocumentAction::select && forward->selection == cross && current.current(*forward),
          "Cross-node selection did not produce a current same-document intent");
    check(backward && backward->selection == reverse, "Backward cross-node selection lost its direction");
    check(current.select(projection, {{3, 2}, {3, 4}}).has_value(), "Valid surrogate-pair endpoints were rejected");
    check(!current.select(projection, {{3, 3}, {3, 4}}), "Selection split a UTF-16 surrogate pair");
    check(!current.select(projection, {{3, 0}, {3, 6}}), "Selection extended beyond the DOM UTF-16 text length");
    check(!current.select(projection, {{999, 0}, {3, 0}}), "Selection accepted an absent DOM node");
    check(!current.select(projection, {{2, 0}, {3, 0}}), "Text selection accepted an element child offset");
    check(current.select(projection, {{5, 1}, {5, 2}}).has_value(),
          "A valid DOM codepoint boundary was incorrectly treated as a grapheme boundary");
    auto invalid = source; ++invalid.version.revision; invalid.selection = DocumentSelection{{3, 3}, {4, 0}};
    retained_after_rejection(current, std::move(invalid));
}

void readable_controls_without_hidden_value_leaks() {
    auto readonly = element(2, 1, "input"); readonly.name = "Readonly account"; readonly.value = "public-account";
    auto masked = element(3, 1, "input"); masked.name = "Password"; masked.masked = true;
    masked.editable = true; masked.value = "PASSWORD_NEVER_DISPLAY_9";
    auto omitted = element(5, 1, "section"); omitted.omitted = true;
    auto choice = element(7, 1, "select"); choice.name = "Color"; choice.value = "blue";
    auto masked_text = text(8, 1, "DIRECT_MASKED_TEXT_NEVER_DISPLAY"); masked_text.masked = true;
    auto masked_link = element(9, 1, "a"); masked_link.masked = true;
    masked_link.name = "CONCEALED_LINK_NAME"; masked_link.href = "hidden.html";
    auto source = document({readonly, masked, text(4, 3, "MASKED_CHILD_NEVER_DISPLAY"), omitted,
        text(6, 5, "OMITTED_CHILD_NEVER_DISPLAY"), choice, masked_text, masked_link});
    source.active_node = 6; source.selection = DocumentSelection{{6, 0}, {6, 5}};
    AppendedDocument current; current.accept(source);
    gui::TerminalAdapter terminal; std::vector<std::string> measured;
    const auto projection = current.project(80, 16, [&](const gui::TextMeasureRequest& request) {
        measured.push_back(request.text); return terminal.measure_text(request);
    });
    terminal.present(projection.view);
    const auto output = row_text(projection) + presentation_text(projection.view) + cells(terminal);
    check(output.find("public-account") != std::string::npos && output.find("blue") != std::string::npos,
          "Readonly or choice controls lost their observed readable value");
    check(output.find("password") != std::string::npos && output.find("read only") != std::string::npos,
          "Masked control lost its safe readable type and read-only marker");
    for (const auto secret : {"PASSWORD_NEVER_DISPLAY_9", "MASKED_CHILD_NEVER_DISPLAY", "OMITTED_CHILD_NEVER_DISPLAY",
                              "DIRECT_MASKED_TEXT_NEVER_DISPLAY", "CONCEALED_LINK_NAME"}) {
        check(output.find(secret) == std::string::npos, "Projection or terminal cells exposed masked or omitted content");
        for (const auto& request : measured) check(request.find(secret) == std::string::npos,
                                                  "Measurement callback received masked or omitted content");
    }
    check(!projection.active_node && !projection.selection, "Invisible DOM focus or selection remained in the presentation");
    check(!current.select(projection, {{6, 0}, {6, 5}}), "Omitted text authorized a selection action");
    check(!current.select(projection, {{4, 0}, {4, 5}}), "Masked descendants authorized a selection action");
    check(!current.select(projection, {{8, 0}, {8, 5}}), "Directly masked text authorized a selection action");
    for (const auto& row : projection.rows) if (row.node == 9)
        check(!row.activatable && !current.intent(projection, row.id, DocumentAction::activate),
              "A read-only masked link row authorized activation");
    check(!current.current({projection.version, DocumentAction::activate, 9, std::nullopt}),
          "A forged masked-link intent bypassed the read-only projection");
    check(*current.snapshot() == source, "Presentation hints changed the producer's same-DOM snapshot");
    ++source.version.revision; source.active_node = 999;
    current.accept(source);
    check(!current.project(80, 16, measure(terminal)).active_node,
          "A safe active-node ID outside the exported tree acquired projected focus");
}

void terminal_actions_and_stable_identity() {
    auto link = element(4, 2, "a"); link.name = "Project guide"; link.href = "guide.html";
    auto button = element(6, 1, "button");
    auto disabled = element(7, 1, "button"); disabled.name = "Unavailable"; disabled.disabled = true;
    AppendedDocument current;
    current.accept(document({element(2, 1, "p"), text(3, 2, "Read the guide before running this example."),
        link, text(5, 4, "Project guide"), button, text(8, 6, "Run calculation"),
        element(9, 6, "script"), text(10, 9, "SCRIPT_CODE_NEVER_DISPLAY"), disabled}));
    gui::TerminalAdapter measurement;
    const auto projection = current.project(20, 12, measure(measurement));
    const auto wide = current.project(80, 12, measure(measurement));
    const auto link_id = action_row(projection, 4).id, button_id = action_row(projection, 6).id;
    check(action_row(wide, 4).id == link_id && action_row(wide, 6).id == button_id,
          "Reflow changed a surviving DOM action's row identity");
    check(row_text(projection).find("Run calculation") != std::string::npos &&
          row_text(projection).find("SCRIPT_CODE_NEVER_DISPLAY") == std::string::npos,
          "Action label traversal lost readable text or exposed inert script contents");
    check(!current.select(projection, {{10, 0}, {10, 3}}), "Unpresented script contents authorized a selection action");
    for (const auto node : {4u, 6u}) {
        const auto& row = action_row(projection, node);
        const auto focus = current.intent(projection, row.id, DocumentAction::focus);
        const auto activate = current.intent(projection, row.id, DocumentAction::activate);
        check(focus && focus->node == node && focus->action == DocumentAction::focus && current.current(*focus),
              "Document row did not create a current focus intent for its DOM node");
        check(activate && activate->node == node && activate->action == DocumentAction::activate && current.current(*activate),
              "Document row did not create a current activation intent for its DOM node");
    }
    check(!current.intent(projection, "missing-row", DocumentAction::activate), "Unknown row authorized a DOM action");
    check(!current.intent(projection, link_id, static_cast<DocumentAction>(999)), "Unknown action enum authorized a DOM action");
    check(!current.current({projection.version, DocumentAction::activate, 999, std::nullopt}),
          "A forged current-version intent authorized an absent DOM node");
    for (const auto& row : projection.rows) {
        if (!row.activatable) check(!current.intent(projection, row.id, DocumentAction::activate),
                                    "Inert or disabled document row authorized activation");
    }
    auto scene = projection.view;
    const auto list = std::find_if(scene.widgets.begin(), scene.widgets.end(),
        [](const gui::Widget& widget) { return widget.spec.kind == gui::Kind::list; });
    check(list != scene.widgets.end(), "Document projection supplied no generic navigable list");
    const auto list_index = static_cast<std::size_t>(list - scene.widgets.begin());
    const auto list_key = list->spec.key;
    std::vector<gui::Event> events;
    gui::TerminalAdapter terminal([&](const gui::Event& event) { events.push_back(event); });
    terminal.terminal_size(20, 12); terminal.present(scene); events.clear();
    check(terminal.focus(list_key), "Projected document list cannot receive terminal focus");
    bool reached = false;
    for (std::size_t step = 0; step <= projection.rows.size(); ++step) {
        events.clear(); terminal.input("\x1b[B");
        for (const auto& event : events) if (const auto* widget = std::get_if<gui::WidgetEvent>(&event)) {
            check(!std::holds_alternative<gui::ActivateRecord>(widget->input), "Arrow navigation executed a DOM action");
            if (const auto* selection = std::get_if<gui::SelectRecord>(&widget->input)) {
                scene.widgets[list_index].state.selected = selection->id;
                reached = selection->id == link_id;
            }
        }
        ++scene.revision; terminal.present(scene);
        if (reached) break;
    }
    check(reached, "Terminal arrow navigation could not reach a projected link");
    events.clear(); terminal.input("\r");
    check(events.size() == 1, "One terminal Enter produced multiple document actions");
    const auto* widget = std::get_if<gui::WidgetEvent>(&events.front());
    const auto* activation = widget ? std::get_if<gui::ActivateRecord>(&widget->input) : nullptr;
    check(widget && widget->target == list_key && activation && activation->id == link_id,
          "Terminal Enter did not activate the selected document link through the public list event");
    check(current.intent(projection, activation->id, DocumentAction::activate).has_value(),
          "Actual terminal row activation lost its live-document intent");
}

void version_lifetimes_and_atomic_validation() {
    gui::TerminalAdapter terminal;
    auto link = element(2, 1, "a"); link.name = "Continue"; link.href = "next.html";
    auto source = document({link, text(3, 2, "Continue")});
    source.active_node = 2; source.selection = DocumentSelection{{3, 0}, {3, 3}};
    AppendedDocument current; current.accept(source);
    const auto projection = current.project(80, 12, measure(terminal));
    const auto action = current.intent(projection, action_row(projection, 2).id, DocumentAction::activate);
    check(action && current.current(*action), "Fresh document action was stale before any update");
    current.accept(source);
    check(current.current(*action), "Identical equal-version snapshot invalidated its live action");
    auto changed = source; changed.nodes[2].text = "Changed";
    retained_after_rejection(current, std::move(changed));
    for (unsigned variant = 0; variant < 3; ++variant) {
        auto stale = source;
        if (variant == 0) --stale.version.revision;
        else if (variant == 1) { --stale.version.epoch; stale.version.revision = 999; }
        else { --stale.version.generation; stale.version.epoch = 999; stale.version.revision = 999; }
        retained_after_rejection(current, std::move(stale));
    }
    ++source.version.revision; current.accept(source);
    check(!current.current(*action) && !current.intent(projection, action_row(projection, 2).id, DocumentAction::activate) &&
          !current.select(projection, {{3, 0}, {3, 1}}), "Old projection or intent survived a same-node DOM revision");
    source.version = {7, 12, 1}; current.accept(source);
    source.version = {8, 1, 1}; current.accept(source);
    const auto valid = *current.snapshot();
    const auto malformed = [&](auto mutate) { auto candidate = valid; ++candidate.version.revision; mutate(candidate); retained_after_rejection(current, std::move(candidate)); };
    malformed([](auto& value) { value.nodes[1].id = 0; });
    malformed([](auto& value) { value.nodes[1].id = (std::uint64_t{1} << 53); });
    malformed([](auto& value) { value.nodes[2].id = value.nodes[1].id; });
    malformed([](auto& value) { value.nodes[1].parent = 999; });
    malformed([](auto& value) { value.nodes[1].parent = value.nodes[1].id; });
    malformed([](auto& value) { value.nodes[2].text = "\xc0\xaf"; });
    malformed([](auto& value) { value.nodes[2].text = std::string("a\0b", 3); });
    malformed([](auto& value) { value.nodes[1].name.assign(AppendedDocument::max_field_units + 1, 'n'); });
    malformed([](auto& value) { value.nodes[2].text.assign(AppendedDocument::max_text_units + 1, 't'); });
    malformed([](auto& value) {
        value.nodes.resize(1); value.selection.reset(); value.active_node.reset();
        for (std::uint64_t id = 2; id < 40; ++id) value.nodes.push_back(text(id, 1, std::string(2000, 't')));
    });
    malformed([](auto& value) { value.active_node = 0; });
    malformed([](auto& value) { value.version.revision = 0; });
    malformed([](auto& value) { value.version.epoch = (std::uint64_t{1} << 53); });
    malformed([](auto& value) { value.selection = DocumentSelection{{3, 0}, {3, 1000}}; });
    malformed([](auto& value) {
        for (std::size_t count = value.nodes.size(); count <= AppendedDocument::max_nodes; ++count)
            value.nodes.push_back(element(100 + count, 1, "div"));
    });
    for (const auto& [columns, rows] : {std::pair<std::size_t, std::size_t>{0, 12}, {1, 12}, {501, 12}, {20, 1}, {20, 201}})
        rejects([&] { (void)current.project(columns, rows, measure(terminal)); }, "Invalid explicit terminal viewport was accepted");
    for (const auto size : {gui::Size{0, 16}, gui::Size{8, 0}, gui::Size{-1, 16},
                            gui::Size{std::numeric_limits<double>::quiet_NaN(), 16},
                            gui::Size{8, std::numeric_limits<double>::infinity()}})
        rejects([&] { (void)current.project(20, 12, [size](const auto&) { return size; }); },
                "Invalid public text measurement was accepted");
    rejects([&] { (void)current.project(500, 12, [](const auto&) { return gui::Size{4096, 16}; }); },
            "Finite cell measurements produced a viewport beyond the public GUI coordinate bound");
    rejects([&] { (void)current.project(20, 12, [](const auto& request) {
        return request.text == "M" ? gui::Size{8, 16} : gui::Size{gui::coordinate_limit, 16};
    }); }, "Finite text measurements produced a cell beyond the public GUI coordinate bound");
    check(*current.snapshot() == valid, "Projection failure changed the accepted document");
}

void reentrant_measurement_preserves_entry_snapshot() {
    gui::TerminalAdapter terminal;
    const auto original = document({element(2, 1, "p"), text(3, 2, "Original document text")});
    auto successor = original; ++successor.version.revision;
    successor.nodes[2].text = "Successor document text";
    AppendedDocument current; current.accept(original);
    bool replaced = false;
    const auto projection = current.project(20, 12, [&](const gui::TextMeasureRequest& request) {
        if (!replaced && request.text != "M") { replaced = true; current.accept(successor); }
        return terminal.measure_text(request);
    });
    check(replaced && *current.snapshot() == successor, "Measurement callback did not accept the successor document");
    check(projection.version == original.version && row_text(projection).find("Original document") != std::string::npos &&
          row_text(projection).find("Successor") == std::string::npos,
          "Measurement callback replacement mixed two document revisions in one projection");
    check(!current.select(projection, {{3, 0}, {3, 1}}), "Projection replaced during measurement authorized a stale action");
}

void truncated_document_is_readable_but_not_selectable() {
    gui::TerminalAdapter terminal;
    auto source = document({element(2, 1, "p"), text(3, 2, "Retained readable content")});
    source.selection = DocumentSelection{{3, 0}, {3, 8}};
    AppendedDocument current; current.accept(source);
    const auto complete = current.project(80, 12, measure(terminal));
    ++source.version.revision; source.truncated = true; current.accept(source);
    const auto incomplete = current.project(80, 12, measure(terminal));
    check(incomplete.incomplete && !incomplete.selection, "Truncated document projected a complete selectable document");
    check(row_text(incomplete).find("Retained readable content") != std::string::npos,
          "Truncation discarded the retained readable document");
    bool marker = false;
    for (const auto& row : incomplete.rows) if (!row.text.empty() &&
        std::none_of(complete.rows.begin(), complete.rows.end(), [&](const auto& old) { return old.text == row.text; })) marker = true;
    check(marker, "Truncated projection has no visible incompleteness marker");
    check(!current.select(incomplete, {{3, 0}, {3, 8}}), "Truncated snapshot authorized a DOM selection action");
    check(!current.current(DocumentIntent{source.version, DocumentAction::select, 0, DocumentSelection{{3, 0}, {3, 8}}}),
          "Currentness validation authorized a forged selection for a truncated document");

    auto limited_source = document({element(2, 1, "pre")});
    for (std::uint64_t id = 3; id < 8; ++id) limited_source.nodes.push_back(text(id, 2, std::string(2000, '\n')));
    limited_source.selection = DocumentSelection{{3, 0}, {3, 1}};
    AppendedDocument limited; limited.accept(limited_source);
    const auto capped = limited.project(20, 12, measure(terminal));
    check(capped.incomplete && capped.rows.size() <= AppendedDocument::max_rows && !capped.selection,
          "Output row limit did not preserve a bounded, visibly incomplete projection");
    check(!limited.select(capped, {{3, 0}, {3, 1}}), "Output row truncation authorized a DOM selection action");
}

void zero_width_reflow_has_a_measurement_work_bound() {
    const std::string acute = "\xcc\x81";
    std::string field;
    for (unsigned count = 0; count < 2000; ++count) field += acute;
    auto source = document({});
    for (std::uint64_t id = 2; id < 34; ++id) source.nodes.push_back(text(id, 1, field));
    source.selection = DocumentSelection{{2, 0}, {33, 1000}};
    AppendedDocument current; current.accept(source);
    std::size_t measured_bytes = 0;
    constexpr auto total_allowance = AppendedDocument::max_reflow_measure_bytes + 1024 * 1024;
    const auto projection = current.project(500, 12, [&](const gui::TextMeasureRequest& request) {
        // Fail promptly if the implementation regresses; never measure the
        // unrestricted quadratic workload merely to discover its final size.
        check(request.text.size() <= total_allowance - measured_bytes,
              "Zero-width reflow exceeded its bounded measurement-input allowance");
        measured_bytes += request.text.size();
        return gui::Size{request.text == "M" ? 8.0 : 0.0, 16};
    });
    check(projection.incomplete && !projection.selection,
          "Measurement-work exhaustion did not produce an incomplete nonselectable projection");
    check(!current.select(projection, {{2, 0}, {33, 1000}}),
          "Measurement-work truncation authorized a DOM selection action");
    bool retained_source = false;
    std::size_t retained_bytes = 0;
    for (const auto& row : projection.rows) for (const auto& span : row.sources) {
        retained_source = true; retained_bytes += span.end - span.begin;
        check(span.begin <= span.end && span.end <= row.text.size() &&
              row.text.substr(span.begin, span.end - span.begin) == acute,
              "Measurement-work truncation split or changed a retained Unicode scalar");
        check(span.first.node >= 2 && span.first.node < 34 && span.first.node == span.last.node &&
              span.last.utf16_offset == span.first.utf16_offset + 1 && span.last.utf16_offset <= 2000,
              "Measurement-work truncation corrupted a retained DOM source range");
    }
    check(retained_source && retained_bytes < field.size() * 32,
          "Measurement-work truncation discarded every source span or claimed the entire unmeasured document");
    check(*current.snapshot() == source, "Measurement-work exhaustion changed the accepted DOM snapshot");

    // A wide positive-width document close to the accepted input limit must
    // still fit the work allowance. Three-byte BMP scalars discriminate a
    // byte-budget mistake that a short ASCII fixture would not expose.
    const std::string ideograph = "\xe4\xb8\xad";
    field.clear();
    for (unsigned count = 0; count < 2000; ++count) field += ideograph;
    auto ordinary = document({});
    for (std::uint64_t id = 2; id < 34; ++id) ordinary.nodes.push_back(text(id, 1, field));
    AppendedDocument full_width; full_width.accept(ordinary);
    measured_bytes = 0;
    const auto complete = full_width.project(500, 12, [&](const gui::TextMeasureRequest& request) {
        check(request.text.size() <= total_allowance - measured_bytes,
              "Ordinary wide document exceeded the measurement-input allowance");
        measured_bytes += request.text.size();
        const auto scalars = std::count_if(request.text.begin(), request.text.end(), [](char byte) {
            return (static_cast<unsigned char>(byte) & 0xc0) != 0x80;
        });
        return gui::Size{double(scalars) * 8, 16};
    });
    retained_bytes = 0;
    for (const auto& row : complete.rows) for (const auto& span : row.sources) retained_bytes += span.end - span.begin;
    check(!complete.incomplete && retained_bytes == field.size() * 32,
          "Reflow work bound falsely truncated an ordinary 64000-unit, 500-column document");
}

void empty_forests_and_document_transitions() {
    gui::TerminalAdapter terminal;
    AppendedDocument current;
    DocumentSnapshot empty; empty.version = {7, 11, 13}; empty.active_node = 777;
    current.accept(empty);
    const auto assert_inert = [&](const DocumentProjection& projection) {
        gui::validate_snapshot(projection.view);
        check(!projection.active_node && !projection.selection && projection.view.commands.empty(),
              "Empty document acquired projected focus, selection or commands");
        const auto list = std::find_if(projection.view.widgets.begin(), projection.view.widgets.end(),
            [](const auto& widget) { return widget.spec.kind == gui::Kind::list; });
        check(list != projection.view.widgets.end() && !list->state.enabled && !list->state.selected &&
              list->state.actions.empty() && list->state.options.empty(),
              "Empty document list remained enabled, selected or actionable");
        for (const auto& row : projection.rows) check(!row.node && !row.activatable && row.sources.empty(),
                                                     "Empty export invented a DOM node or source mapping");
        terminal.present(projection.view);
        check(!terminal.focus(list->spec.key) && !terminal.focus_next() && !terminal.focused(),
              "Empty document retained a focusable terminal control");
    };
    const auto first_empty = current.project(80, 12, measure(terminal));
    check(first_empty.rows.empty() && *current.snapshot() == empty && current.snapshot()->nodes.empty(),
          "Empty same-document snapshot was replaced with synthetic DOM content");
    assert_inert(first_empty);
    check(!current.select(first_empty, {{42, 0}, {42, 0}}), "Empty export authorized an absent selection endpoint");
    for (const bool truncated : {false, true}) {
        auto invalid = empty; ++invalid.version.revision; invalid.truncated = truncated;
        invalid.selection = DocumentSelection{{42, 0}, {42, 0}};
        retained_after_rejection(current, std::move(invalid));
    }

    auto button = element(100, 0, "button"); button.name = "Forest action";
    auto readonly = element(902, 900, "input"); readonly.name = "Observed control"; readonly.value = "readonly value";
    auto omitted = element(903, 900, "section"); omitted.omitted = true;
    DocumentSnapshot forest;
    forest.version = {7, 11, 14}; forest.active_node = 100;
    forest.nodes = {element(42, 0, "p"), text(43, 42, "First root"), button,
        element(900, 0, "section"), text(901, 900, "Last root"), readonly, omitted, text(904, 903, "OMITTED_FOREST_SECRET")};
    forest.selection = DocumentSelection{{43, 1}, {901, 4}};
    current.accept(forest);
    const auto projected = current.project(80, 12, measure(terminal));
    check(*current.snapshot() == forest && projected.selection == forest.selection && projected.active_node == 100,
          "Element forest changed original IDs, order, focus or cross-root selection");
    const auto display = row_text(projected);
    check(display.find("First root") < display.find("Forest action") && display.find("Forest action") < display.find("Last root") &&
          display.find("readonly value") != std::string::npos && display.find("OMITTED_FOREST_SECRET") == std::string::npos,
          "Forest projection reordered roots, lost readonly values or exposed omitted descendants");
    for (const auto& row : projected.rows) {
        if (row.node) check(std::any_of(forest.nodes.begin(), forest.nodes.end(), [&](const auto& value) { return value.id == row.node; }),
                            "Forest projection invented an actionable DOM identity");
        for (const auto& span : row.sources)
            check(span.first.node != 1 && span.last.node != 1, "Forest projection invented a containing DOM root");
    }
    const auto& row = action_row(projected, 100);
    const auto action = current.intent(projected, row.id, DocumentAction::activate);
    check(action && current.current(*action), "A root element action could not target its actual DOM identity");
    check(current.select(projected, {{901, 4}, {43, 1}}).has_value(), "Backward selection across forest roots was rejected");
    terminal.present(projected.view);
    const auto list_key = projected.view.widgets.front().spec.key;
    check(terminal.focus(list_key), "An empty-to-forest transition did not re-enable the document list");

    auto next_empty = empty; next_empty.version.revision = 15; next_empty.active_node = 100;
    current.accept(next_empty); const auto cleared = current.project(80, 12, measure(terminal));
    assert_inert(cleared);
    check(!current.current(*action) && !current.intent(projected, row.id, DocumentAction::activate) &&
          !current.select(projected, {{43, 1}, {901, 4}}), "Forest-to-empty transition retained stale actions or selection");
    check(cells(terminal).find("Forest action") == std::string::npos && cells(terminal).find("readonly value") == std::string::npos,
          "Forest-to-empty transition left prior document contents on the terminal");
    auto populated = document({element(100, 1, "button")});
    populated.version.revision = 16; populated.nodes.back().name = "Replacement action";
    current.accept(populated);
    const auto replacement = current.project(80, 12, measure(terminal));
    check(current.intent(replacement, action_row(replacement, 100).id, DocumentAction::activate).has_value() && !current.current(*action),
          "Reappearing DOM node identity either lost its fresh action or revived a stale intent");
    terminal.present(replacement.view);
    check(terminal.focus(list_key), "Empty-to-populated transition changed or stranded the retained list identity");
    auto invalid_root = populated; ++invalid_root.version.revision; invalid_root.nodes.push_back(text(500, 0, "invalid text root"));
    retained_after_rejection(current, std::move(invalid_root));
    auto truncated_empty = empty; truncated_empty.version.revision = 17; truncated_empty.truncated = true;
    current.accept(truncated_empty);
    const auto truncated = current.project(80, 12, measure(terminal));
    check(truncated.incomplete, "Truncated empty export lost its incompleteness status");
    assert_inert(truncated);
}

void tag_names_do_not_consume_the_document_text_budget() {
    gui::TerminalAdapter terminal;
    DocumentSnapshot source; source.version = {7, 11, 13}; source.nodes.push_back(element(1, 0, "pre"));
    for (std::uint64_t id = 2; id < 34; ++id) source.nodes.push_back(text(id, 1, std::string(2048, 'x')));
    AppendedDocument current; current.accept(source);
    const auto projection = current.project(500, 12, measure(terminal));
    std::size_t source_bytes = 0;
    for (const auto& row : projection.rows) for (const auto& span : row.sources) source_bytes += span.end - span.begin;
    check(!projection.incomplete && source_bytes == AppendedDocument::max_text_units && *current.snapshot() == source,
          "Tag names consumed the bounded document text allowance or caused false truncation");
    auto oversized = source; ++oversized.version.revision; oversized.nodes.push_back(text(34, 1, "x"));
    retained_after_rejection(current, std::move(oversized));
}
} // namespace

int main() {
    try {
        prose_and_preformatted_reflow(); unicode_sources_and_cross_node_selection();
        readable_controls_without_hidden_value_leaks(); terminal_actions_and_stable_identity();
        version_lifetimes_and_atomic_validation(); reentrant_measurement_preserves_entry_snapshot();
        truncated_document_is_readable_but_not_selectable();
        zero_width_reflow_has_a_measurement_work_bound();
        empty_forests_and_document_transitions(); tag_names_do_not_consume_the_document_text_budget();
        std::cout << "Same-document projection preserves reflow, source selections, action identity and bounded atomic validation\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
