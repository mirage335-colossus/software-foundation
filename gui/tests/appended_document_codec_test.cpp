#include "shared/appended_document_codec.hpp"

#include <algorithm>
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
constexpr std::uint64_t request_id = 41;
constexpr std::uint64_t generation = std::numeric_limits<std::uint64_t>::max() - 1;

void check(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
template<class Function> void rejects(Function function, const char* message) {
    bool rejected = false;
    try { function(); } catch (const std::invalid_argument&) { rejected = true; }
    check(rejected, message);
}
std::string quoted(std::string_view value) {
    constexpr char hex[] = "0123456789abcdef";
    std::string result = "\"";
    for (const char character : value) {
        const auto byte = static_cast<unsigned char>(character);
        if (byte == '"' || byte == '\\') { result += '\\'; result += static_cast<char>(byte); }
        else if (byte < 32) { result += "\\u00"; result += hex[byte >> 4]; result += hex[byte & 15]; }
        else result += static_cast<char>(byte);
    }
    return result + '"';
}
const char* boolean(bool value) { return value ? "true" : "false"; }
std::string replace(std::string value, std::string_view from, std::string_view to) {
    const auto at = value.find(from);
    check(at != std::string::npos && value.find(from, at + from.size()) == std::string::npos,
          "Codec fixture replacement was absent or ambiguous");
    value.replace(at, from.size(), to);
    return value;
}

// Fixture builders emit exactly the producer's two node shapes, without a
// parser or a substitute semantic extractor. Parent IDs are JSON null at root.
struct Element {
    std::uint64_t id = 1;
    std::string parent = "null", tag = "html", role, name, display = "block", white_space = "normal";
    bool editable = false, disabled = false, read_only = false, masked = false, checked = false;
    std::string value, href;
    std::string json() const {
        return "{\"id\":" + std::to_string(id) + ",\"parent\":" + parent +
            ",\"type\":\"element\",\"tag\":" + quoted(tag) + ",\"role\":" + quoted(role) +
            ",\"name\":" + quoted(name) + ",\"display\":" + quoted(display) +
            ",\"whiteSpace\":" + quoted(white_space) + ",\"editable\":" + boolean(editable) +
            ",\"disabled\":" + boolean(disabled) + ",\"readonly\":" + boolean(read_only) +
            ",\"masked\":" + boolean(masked) + ",\"value\":" + quoted(value) +
            ",\"checked\":" + boolean(checked) + ",\"href\":" + quoted(href) + "}";
    }
};
std::string text(std::uint64_t id, std::string_view value, std::string_view parent = "1") {
    return "{\"id\":" + std::to_string(id) + ",\"parent\":" + std::string(parent) +
        ",\"type\":\"text\",\"text\":" + quoted(value) + "}";
}
std::string nodes(const std::vector<std::string>& values) {
    std::string result = "[";
    for (const auto& value : values) { if (result.size() > 1) result += ','; result += value; }
    return result + ']';
}
std::string selection(std::string_view anchor = "2", std::string_view anchor_offset = "0",
                      std::string_view focus = "2", std::string_view focus_offset = "1") {
    return "{\"anchorNode\":" + std::string(anchor) + ",\"anchorOffset\":" + std::string(anchor_offset) +
        ",\"focusNode\":" + std::string(focus) + ",\"focusOffset\":" + std::string(focus_offset) +
        ",\"focusRect\":{\"x\":12.5,\"y\":-3,\"width\":0,\"height\":16}}";
}
std::string success(std::string_view node_list, std::string_view selected = "null", bool truncated = false,
                    std::string_view active = "1") {
    return "{\"requestId\":41,\"ok\":true,\"epoch\":17,\"revision\":23,"
        "\"editorState\":{\"revision\":7,\"flags\":29},\"truncated\":" + std::string(boolean(truncated)) +
        ",\"activeNode\":" + std::string(active) + ",\"selection\":" + std::string(selected) +
        ",\"nodes\":" + std::string(node_list) + "}";
}
std::string simple() { return success(nodes({Element{}.json(), text(2, "plain")})); }
DocumentSemanticReply decode(std::string_view json) { return decode_appended_document(json, generation, request_id); }
void malformed(std::string_view json) {
    rejects([&] { (void)decode(json); }, "Malformed or unsupported semantic JSON was accepted");
}
void rejects_with_budget(std::string_view json, std::string_view budget) {
    try { (void)decode(json); }
    catch (const std::invalid_argument& error) {
        check(std::string_view(error.what()).find(budget) != std::string_view::npos,
              "Excessive semantic JSON reached schema validation instead of its parser resource limit");
        return;
    }
    throw std::runtime_error("Semantic JSON parser resource limit was not enforced");
}
const DocumentNode& node(const DocumentSemanticReply& reply, std::uint64_t id) {
    check(reply.snapshot.has_value(), "Successful semantic reply lost its document snapshot");
    const auto found = std::find_if(reply.snapshot->nodes.begin(), reply.snapshot->nodes.end(),
        [id](const auto& value) { return value.id == id; });
    check(found != reply.snapshot->nodes.end(), "Decoded document node is missing");
    return *found;
}
const DocumentNodeMetadata& metadata(const DocumentSemanticReply& reply, std::uint64_t id) {
    const auto found = std::find_if(reply.metadata.begin(), reply.metadata.end(),
        [id](const auto& value) { return value.node == id; });
    check(found != reply.metadata.end(), "Observed element metadata was discarded");
    return *found;
}

void producer_shape_and_observed_metadata() {
    Element control;
    control.id = 2; control.parent = "1"; control.tag = "input"; control.role = "checkbox";
    control.name = "Receive updates"; control.display = "inline-block"; control.white_space = "pre-wrap";
    control.editable = true; control.disabled = true; control.read_only = true; control.checked = true;
    control.value = "observed value"; control.href = "";
    auto json = success(nodes({Element{}.json(), control.json(), text(3, "child", "2")}), "null", false, "999");
    const auto result = decode(json);
    check(result.request_id == request_id && result.epoch == 17 && result.error_code.empty(),
          "Successful producer request identity or status changed during decoding");
    check(result.snapshot && result.snapshot->version == DocumentVersion{generation, 17, 23},
          "Engine-session generation or semantic version lost integer precision");
    check(result.editor_state && result.editor_state->revision == 7 && result.editor_state->flags == 29,
          "Native editor revision and flags were lost or confused with semantic revision");
    const auto& decoded = node(result, 2);
    check(decoded.parent == 1 && decoded.kind == DocumentNodeKind::element && decoded.tag == "input" &&
          decoded.name == control.name && decoded.value == control.value && decoded.editable && decoded.disabled &&
          !decoded.masked && !decoded.omitted && decoded.white_space == DocumentWhiteSpace::pre_wrap,
          "Observed element state changed or acquired invented omission/edit capabilities");
    const auto& observed = metadata(result, 2);
    check(observed.role == "checkbox" && observed.display == "inline-block" && observed.white_space == "pre-wrap" &&
          observed.read_only && observed.checked, "Codec discarded readonly/checked or computed presentation metadata");
    check(result.snapshot->active_node == 999 && !result.snapshot->selection && !result.original_selection &&
          !result.degraded.whitespace && !result.degraded.element_selection && !result.degraded.truncated_selection,
          "Unknown safe active node or absent selection was normalized into invented state");
    check(node(result, 1).parent == 0 && node(result, 3).text == "child", "Root-null parent or text node shape was changed");
    check(decode(success(nodes({Element{}.json(), text(2, "plain")}), "null", false, "null")).snapshot->active_node == std::nullopt,
          "Null activeNode became a synthetic DOM focus");
    auto masked = control; masked.masked = true; masked.value.clear();
    check(node(decode(success(nodes({Element{}.json(), masked.json()}))), 2).masked,
          "Empty masked producer value was rejected or unmasked");
    masked.value = "secret";
    malformed(success(nodes({Element{}.json(), masked.json()})));
    json = replace(json, "\"flags\":29", "\"flags\":31");
    json = replace(json, "\"revision\":7", "\"revision\":2147483647");
    const auto largest_editor = decode(json);
    check(largest_editor.editor_state->flags == 31 && largest_editor.editor_state->revision == 2147483647u,
          "Valid native editor flag/revision boundaries were not retained");
    const auto no_flags = decode(replace(replace(simple(), "\"flags\":29", "\"flags\":0"),
        "\"revision\":7", "\"revision\":1"));
    check(no_flags.editor_state->flags == 0 && no_flags.editor_state->revision == 1,
          "Initial native editor revision or valid zero flags was rejected");
    auto disposable_wire = simple();
    const auto owned = decode(disposable_wire); disposable_wire.assign(disposable_wire.size(), 'x');
    check(node(owned, 2).text == "plain" && metadata(owned, 1).display == "block" && owned.snapshot->version.revision == 23,
          "Decoded semantic state borrowed the caller's disposable JSON storage");
}

void producer_errors_and_request_identity() {
    const std::string error = "{\"requestId\":41,\"ok\":false,\"code\":\"stale-view\",\"epoch\":17}";
    const auto result = decode(error);
    check(result.request_id == 41 && result.epoch == 17 && result.error_code == "stale-view" &&
          !result.snapshot && !result.editor_state && result.metadata.empty() && !result.original_selection,
          "Producer rejection became an empty successful snapshot or invented editor state");
    check(decode(replace(error, "stale-view", "future-error")).error_code == "future-error",
          "Unknown nonempty producer error code was silently replaced");
    malformed(replace(error, "stale-view", ""));
    malformed(replace(error, "\"epoch\":17", "\"epoch\":17,\"nodes\":[]"));
    rejects([&] { (void)decode_appended_document(simple(), generation, 42); }, "A reply for a different request was accepted");
    rejects([&] { (void)decode_appended_document(error, generation, 42); }, "A mismatched producer error reply was accepted");
    rejects([&] { (void)decode_appended_document(simple(), 0, request_id); }, "Zero engine-session generation was accepted");
    rejects([&] { (void)decode_appended_document(simple(), generation, 0); }, "Zero expected request identity was accepted");
}

void utf8_and_utf16_selection_metadata() {
    const std::string unicode = "A\xc3\xa9\xf0\x9f\x99\x82Z";
    const auto chosen = selection("2", "2", "2", "4");
    const auto json = success(nodes({Element{}.json(), text(2, unicode)}), chosen);
    const auto result = decode(json);
    const DocumentSelection expected{{2, 2}, {2, 4}};
    check(node(result, 2).text == unicode && result.snapshot->selection == expected && result.original_selection &&
          result.original_selection->endpoints.anchor.node == 2 && result.original_selection->endpoints.anchor.offset == 2 &&
          result.original_selection->endpoints.anchor.kind == DocumentNativeOffsetKind::text_utf16 &&
          result.original_selection->endpoints.focus.node == 2 && result.original_selection->endpoints.focus.offset == 4 &&
          result.original_selection->endpoints.focus.kind == DocumentNativeOffsetKind::text_utf16,
          "UTF-8 bytes or valid DOM UTF-16 selection offsets changed in transit");
    check(result.original_selection->focus_rect == gui::Rect{12.5, -3, 0, 16},
          "Caret geometry was dropped or changed during selection decoding");
    auto escaped = replace(success(nodes({Element{}.json(), text(2, "plain")})), "\"text\":\"plain\"",
        "\"text\":\"A\\u00e9\\ud83d\\ude42Z\"");
    check(node(decode(escaped), 2).text == unicode, "JSON escaped Unicode did not decode to the producer's UTF-8 text");
    const std::string controls = "quote\" slash\\ newline\n tab\t";
    check(node(decode(success(nodes({Element{}.json(), text(2, controls)}))), 2).text == controls,
          "Legal JSON string escapes changed observed document text");
    const auto backwards = decode(success(nodes({Element{}.json(), text(2, unicode)}), selection("2", "4", "2", "2")));
    check(backwards.snapshot->selection == DocumentSelection{{2, 4}, {2, 2}}, "Backward DOM selection lost its direction");
    malformed(success(nodes({Element{}.json(), text(2, unicode)}), selection("2", "3", "2", "4")));
    malformed(success(nodes({Element{}.json(), text(2, unicode)}), selection("2", "0", "2", "6")));
    malformed(success(nodes({Element{}.json(), text(2, unicode)}), selection("999", "0", "2", "1"), true));
    malformed(success(nodes({Element{}.json(), text(2, unicode)}), selection("2", "3", "2", "4"), true));
    malformed(success(nodes({Element{}.json(), text(2, unicode)}), selection("2", "0", "2", "4294967296"), true));

    const auto element = decode(success(nodes({Element{}.json(), text(2, unicode)}), selection("1", "1", "2", "4")));
    check(element.original_selection && element.original_selection->endpoints.anchor.node == 1 &&
          element.original_selection->endpoints.anchor.offset == 1 &&
          element.original_selection->endpoints.anchor.kind == DocumentNativeOffsetKind::element_child_index &&
          element.original_selection->endpoints.focus.node == 2 && element.original_selection->endpoints.focus.offset == 4 &&
          element.original_selection->endpoints.focus.kind == DocumentNativeOffsetKind::text_utf16 &&
          !element.snapshot->selection && element.degraded.element_selection && !element.degraded.truncated_selection,
          "Element child offset was rejected, clamped or invented as a text-node caret");
    const auto truncated = decode(success(nodes({Element{}.json(), text(2, unicode)}), selection("2", "0", "2", "2000"), true));
    check(truncated.snapshot->truncated && !truncated.snapshot->selection && truncated.original_selection &&
          truncated.original_selection->endpoints.focus.offset == 2000 &&
          truncated.original_selection->endpoints.focus.kind == DocumentNativeOffsetKind::text_utf16 && truncated.degraded.truncated_selection,
          "Global truncation lost original selection metadata or invented an exported-prefix caret");
    const auto truncated_valid = decode(success(nodes({Element{}.json(), text(2, unicode)}), chosen, true));
    check(truncated_valid.degraded.truncated_selection && !truncated_valid.snapshot->selection &&
          truncated_valid.original_selection->focus_rect == gui::Rect{12.5, -3, 0, 16},
          "Even in-range selection was authorized after global producer truncation");
    const auto largest_offset = decode(success(nodes({Element{}.json(), text(2, unicode)}),
        selection("2", "0", "2", "4294967295"), true));
    check(largest_offset.original_selection->endpoints.focus.offset == std::numeric_limits<std::uint32_t>::max(),
          "Truncated selection offset lost precision at the wire uint32 boundary");
}

void whitespace_degradation_is_explicit() {
    for (const auto& mode : {std::string("normal"), std::string("pre"), std::string("pre-wrap"), std::string("nowrap"),
                             std::string("pre-line"), std::string("break-spaces"), std::string("future-white-space")}) {
        Element root; root.white_space = mode;
        const auto reply = decode(success(nodes({root.json(), text(2, "  text\n  remains")})));
        const auto expected = mode == "pre" ? DocumentWhiteSpace::pre :
            (mode == "pre-wrap" || mode == "break-spaces" ? DocumentWhiteSpace::pre_wrap : DocumentWhiteSpace::normal);
        check(node(reply, 1).white_space == expected && metadata(reply, 1).white_space == mode,
              "Computed whitespace fallback lost its raw producer value or selected the wrong policy");
        check(reply.degraded.whitespace == (mode != "normal" && mode != "pre" && mode != "pre-wrap"),
              "Unsupported computed whitespace was silently claimed as exact");
        check(node(reply, 2).text == "  text\n  remains", "Codec performed text reflow or whitespace collapse");
    }
}

void exact_shapes_unicode_and_json_numbers() {
    const auto valid = simple();
    for (const auto& bad : {
        replace(valid, "\"epoch\":17", "\"epoch\":17,\"extra\":false"),
        replace(valid, "\"epoch\":17", "\"epoch\":17,\"epoch\":17"),
        replace(valid, "\"epoch\":17", "\"epoch\":17,\"\\u0065poch\":17"),
        replace(valid, "\"flags\":29", "\"flags\":29,\"extra\":0"),
        replace(valid, "\"flags\":29", "\"flags\":29,\"flags\":29"),
        replace(valid, "\"role\":\"\"", "\"role\":\"\",\"omitted\":true"),
        replace(valid, "\"text\":\"plain\"", "\"text\":\"plain\",\"role\":\"text\""),
        replace(valid, ",\"checked\":false", ""),
        replace(valid, "\"readonly\":false", "\"readonly\":0"),
        replace(valid, "\"type\":\"text\"", "\"type\":\"comment\""),
        replace(valid, "\"text\":\"plain\"", "\"text\":\"\\ud800\""),
        replace(valid, "\"text\":\"plain\"", "\"text\":\"\\udc00\""),
        replace(valid, "\"text\":\"plain\"", "\"text\":\"\\ud800A\""),
        replace(valid, "\"text\":\"plain\"", "\"text\":\"\\u0000\""),
        replace(valid, "\"text\":\"plain\"", "\"text\":\"\\x20\""),
        replace(valid, "\"text\":\"plain\"", "\"text\":\"\\u00q0\""),
        replace(valid, "\"text\":\"plain\"", "\"text\":\"raw\nnewline\"")}) malformed(bad);
    for (const auto& bytes : {std::string("\xc0\xaf"), std::string("\xed\xa0\x80"), std::string("\xf4\x90\x80\x80"), std::string("\xe2\x82")})
        malformed(success(nodes({Element{}.json(), text(2, bytes)})));
    malformed(valid + "false"); malformed(valid.substr(0, valid.size() - 1));
    malformed("[" + valid + "]"); malformed("null");
    malformed(replace(valid, "\"nodes\":[", "\"nodes\":[,"));
    malformed(valid.substr(0, valid.size() - 1) + ",}");
    for (const auto* number : {"+17", "017", "0x11", ".17", "17.", "1e", "1e+", "--1", "NaN", "Infinity",
                              "0", "-1", "17.0", "17e0", "9007199254740992", "18446744073709551616"})
        malformed(replace(valid, "\"epoch\":17", std::string("\"epoch\":") + number));
    malformed(replace(valid, "\"flags\":29", "\"flags\":32"));
    malformed(replace(valid, "\"flags\":29", "\"flags\":-1"));
    malformed(replace(valid, "\"revision\":7", "\"revision\":0"));
    malformed(replace(valid, "\"revision\":7", "\"revision\":2147483648"));
    malformed(replace(valid, "\"revision\":7", "\"revision\":4294967296"));
    const auto chosen = success(nodes({Element{}.json(), text(2, "plain")}), selection());
    for (const auto& bad : {replace(chosen, "\"width\":0", "\"width\":-1"),
        replace(chosen, "\"height\":16", "\"height\":1e400"),
        replace(chosen, "\"focusOffset\":1", "\"focusOffset\":-1"),
        replace(chosen, "\"height\":16", "\"height\":16,\"extra\":false"),
        replace(chosen, "\"focusNode\":2", "\"focusNode\":2,\"focusNode\":2")}) malformed(bad);
    const auto fractional = decode(replace(chosen, "\"x\":12.5", "\"x\":1.25e-2"));
    check(fractional.original_selection->focus_rect.x == 0.0125, "Valid finite JSON exponent geometry was rejected or rounded incorrectly");
    const auto distant = decode(replace(chosen, "\"x\":12.5", "\"x\":1000001"));
    check(distant.original_selection->focus_rect.x == 1000001,
          "Finite engine caret metadata was incorrectly clamped to GUI presentation coordinates");
    const auto large_node = decode(replace(valid, "\"id\":2", "\"id\":9007199254740991"));
    check(node(large_node, 9007199254740991ULL).text == "plain", "Safe DOM node identity lost integer precision");
    const auto large_revision = decode(replace(valid, "\"revision\":23", "\"revision\":9007199254740991"));
    check(large_revision.snapshot->version.revision == 9007199254740991ULL,
          "Safe semantic revision lost integer precision");
    const auto large_request = replace(valid, "\"requestId\":41", "\"requestId\":9007199254740991");
    check(decode_appended_document(large_request, generation, 9007199254740991ULL).request_id == 9007199254740991ULL,
          "Safe expected request identity lost integer precision");
}

void hierarchy_and_bounded_inputs() {
    const auto valid = simple();
    malformed(success(nodes({Element{}.json(), text(2, "plain", "null")})));
    malformed(replace(valid, "\"id\":2", "\"id\":1"));
    malformed(replace(valid, "\"id\":2", "\"id\":0"));
    malformed(replace(valid, "\"id\":2", "\"id\":9007199254740992"));
    malformed(success(nodes({Element{}.json(), text(2, "plain", "999")})));
    malformed(success(nodes({Element{}.json(), text(2, "plain", "2")})));
    Element child; child.id = 3; child.parent = "2";
    malformed(success(nodes({Element{}.json(), text(2, "plain"), child.json()})));
    malformed(success(nodes({Element{}.json(), text(2, "plain", "0")})));
    malformed(success(nodes({Element{}.json(), text(2, "plain", "3"), child.json()})));
    malformed(replace(valid, "\"activeNode\":1", "\"activeNode\":0"));
    malformed(replace(valid, "\"activeNode\":1", "\"activeNode\":9007199254740992"));
    malformed(success(nodes({Element{}.json(), text(2, std::string(AppendedDocument::max_field_units + 1, 'x'))})));
    Element too_long; too_long.name.assign(AppendedDocument::max_field_units + 1, 'n');
    malformed(success(nodes({too_long.json()})));
    Element empty_tag; empty_tag.tag.clear(); malformed(success(nodes({empty_tag.json()})));
    std::string supplementary;
    for (unsigned count = 0; count < 1024; ++count) supplementary += "\xf0\x9f\x99\x82";
    check(node(decode(success(nodes({Element{}.json(), text(2, supplementary)}))), 2).text == supplementary,
          "A valid 2048-unit field was counted by UTF-8 bytes instead of UTF-16 units");
    supplementary += "\xf0\x9f\x99\x82";
    malformed(success(nodes({Element{}.json(), text(2, supplementary)})));
    std::vector<std::string> too_many{Element{}.json()};
    for (std::size_t count = 0; count < AppendedDocument::max_nodes; ++count) too_many.push_back(text(count + 2, ""));
    malformed(success(nodes(too_many)));
    std::vector<std::string> too_much_text{Element{}.json()};
    for (std::uint64_t id = 2; id < 37; ++id) too_much_text.push_back(text(id, std::string(2000, 'x')));
    malformed(success(nodes(too_much_text)));
    std::string padded = valid;
    padded.append(max_document_semantic_json_bytes - padded.size(), ' ');
    check(decode(padded).snapshot.has_value(), "Valid JSON at the byte budget was rejected");
    padded += ' '; malformed(padded);
    const auto nested = std::string(max_document_semantic_json_depth + 1, '[') + "0" +
        std::string(max_document_semantic_json_depth + 1, ']');
    rejects_with_budget(replace(valid, "\"epoch\":17", "\"epoch\":17,\"extra\":" + nested), "depth limit");
    std::string many_values = "[0";
    for (std::size_t count = 0; count < max_document_semantic_json_values; ++count) many_values += ",0";
    many_values += ']';
    rejects_with_budget(replace(valid, "\"nodes\":", "\"extra\":" + many_values + ",\"nodes\":"), "value limit");
    check(decode(valid).snapshot.has_value(), "Malformed-input rejection contaminated a later independent successful decode");
}

gui::Size ascii_measure(const gui::TextMeasureRequest& request) {
    gui::validate_measure_request(request);
    return {double(request.text.size()) * 8, 16};
}
void producer_filtered_empty_and_forest_exports() {
    // Omitted roots and hidden ancestors have already been filtered by the
    // actual producer; its wire format adds neither omit fields nor fake roots.
    const auto empty = decode(success("[]", "null", false, "777"));
    check(empty.snapshot && empty.snapshot->nodes.empty() && empty.snapshot->active_node == 777 &&
          empty.metadata.empty() && !empty.original_selection && empty.error_code.empty() && empty.editor_state,
          "Successful root-omitted producer reply became an error or acquired invented DOM metadata");
    const auto truncated_empty = decode(success("[]", "null", true, "777"));
    check(truncated_empty.snapshot && truncated_empty.snapshot->truncated && truncated_empty.snapshot->nodes.empty(),
          "Truncated empty export was rejected or replaced with synthetic nodes");
    malformed(success("[]", selection("777", "0", "777", "0"), false, "777"));
    malformed(success("[]", selection("777", "0", "777", "0"), true, "777"));

    Element first; first.id = 10; first.tag = "p";
    Element action; action.id = 20; action.tag = "button"; action.name = "Visible forest action";
    Element last; last.id = 30; last.tag = "section"; last.role = "region";
    Element readonly; readonly.id = 40; readonly.parent = "30"; readonly.tag = "input";
    readonly.read_only = true; readonly.checked = true; readonly.name = "Observed readonly"; readonly.value = "unchanged value";
    const auto exported = nodes({first.json(), text(11, "First visible root", "10"), action.json(), last.json(),
        text(31, "Last visible root", "30"), readonly.json()});
    const auto wire = replace(success(exported, selection("11", "1", "31", "4"), false, "40"),
        "\"revision\":23", "\"revision\":24");
    const auto forest = decode(wire);
    const std::vector<std::uint64_t> ids{10, 11, 20, 30, 31, 40}, parents{0, 10, 0, 0, 30, 30};
    check(forest.snapshot->nodes.size() == ids.size() && forest.metadata.size() == 4,
          "Flattened producer forest acquired a containing DOM node or lost observed metadata");
    for (std::size_t index = 0; index < ids.size(); ++index)
        check(forest.snapshot->nodes[index].id == ids[index] && forest.snapshot->nodes[index].parent == parents[index] &&
              !forest.snapshot->nodes[index].omitted, "Codec changed sparse producer IDs, forest order or already-filtered omission state");
    check(metadata(forest, 40).read_only && metadata(forest, 40).checked && node(forest, 40).value == "unchanged value" &&
          !node(forest, 40).editable && forest.snapshot->selection == DocumentSelection{{11, 1}, {31, 4}},
          "Forest decoding lost readonly observations or same-document cross-root selection");
    AppendedDocument current; current.accept(*empty.snapshot); current.accept(*forest.snapshot);
    const auto projection = current.project(80, 12, ascii_measure);
    const auto row = std::find_if(projection.rows.begin(), projection.rows.end(), [](const auto& value) { return value.node == 20; });
    check(row != projection.rows.end(), "Decoded root action disappeared from the shared projection");
    const auto intent = current.intent(projection, row->id, DocumentAction::activate);
    check(intent && current.current(*intent), "Decoded forest action did not preserve its producer identity");
    const auto emptied = decode(replace(success("[]", "null", false, "20"), "\"revision\":23", "\"revision\":25"));
    current.accept(*emptied.snapshot);
    check(!current.current(*intent) && !current.select(projection, {{11, 1}, {31, 4}}),
          "Decoded forest-to-empty transition retained an obsolete action or selection");
    const auto populated = decode(replace(success(nodes({action.json()}), "null", false, "20"),
        "\"revision\":23", "\"revision\":26"));
    current.accept(*populated.snapshot);
    check(!current.current(*intent) && current.snapshot()->nodes.size() == 1 && current.snapshot()->nodes.front().id == 20,
          "Empty-to-populated producer transition invented a root or revived a prior same-ID intent");
    malformed(success(nodes({text(11, "invalid root", "null"), action.json()})));
    malformed(success(nodes({first.json(), action.json(), text(31, "invalid text root", "null")})));
}

void full_exporter_budget_excludes_unbounded_tag_metadata() {
    // Exact producer budget: html's display/whiteSpace use 11 units, twenty
    // blockquote elements use 8 each, and 65365 text units consume the rest.
    Element root;
    Element block; block.id = 2; block.parent = "1"; block.tag = "blockquote"; block.white_space = "pre";
    std::vector<std::string> exported{root.json(), block.json()};
    for (std::uint64_t id = 100; id < 132; ++id)
        exported.push_back(text(id, std::string(id == 131 ? 1877 : 2048, 'x'), "2"));
    for (std::uint64_t id = 3; id <= 21; ++id) { block.id = id; exported.push_back(block.json()); }
    const auto exact = decode(success(nodes(exported)));
    check(exact.snapshot && !exact.snapshot->truncated && exact.snapshot->nodes.size() == 53 && exact.metadata.size() == 21,
          "An exact-budget producer reply was rejected or falsely marked truncated");
    AppendedDocument current; current.accept(*exact.snapshot);
    const auto projection = current.project(500, 12, ascii_measure);
    std::size_t source_bytes = 0;
    for (const auto& row : projection.rows) for (const auto& span : row.sources) source_bytes += span.end - span.begin;
    check(!projection.incomplete && source_bytes == 65365,
          "Tag metadata consumed the producer text allowance or lost source data during projection");
    exported[33] = text(131, std::string(1878, 'x'), "2");
    malformed(success(nodes(exported)));
}
} // namespace

int main() {
    try {
        producer_shape_and_observed_metadata(); producer_errors_and_request_identity();
        utf8_and_utf16_selection_metadata(); whitespace_degradation_is_explicit();
        exact_shapes_unicode_and_json_numbers(); hierarchy_and_bounded_inputs();
        producer_filtered_empty_and_forest_exports(); full_exporter_budget_excludes_unbounded_tag_metadata();
        std::cout << "Prototype semantic JSON preserves observed state and rejects malformed, stale or excessive replies\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
