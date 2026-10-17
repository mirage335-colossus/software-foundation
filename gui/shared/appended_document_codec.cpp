#include "appended_document_codec.hpp"

#include <algorithm>
#include <charconv>
#include <cmath>
#include <initializer_list>
#include <limits>
#include <map>
#include <set>
#include <stdexcept>
#include <utility>
#include <variant>

namespace foundation::ui {
namespace {
constexpr std::uint64_t safe_integer = 9007199254740991ULL;
constexpr std::size_t max_string_bytes = 8192;
void require(bool condition, const char* error) {
    if (!condition) throw std::invalid_argument(error);
}
void append_utf8(std::string& output, std::uint32_t value) {
    if (value < 0x80) output += static_cast<char>(value);
    else if (value < 0x800) {
        output += static_cast<char>(0xc0 | (value >> 6));
        output += static_cast<char>(0x80 | (value & 63));
    } else if (value < 0x10000) {
        output += static_cast<char>(0xe0 | (value >> 12));
        output += static_cast<char>(0x80 | ((value >> 6) & 63));
        output += static_cast<char>(0x80 | (value & 63));
    } else {
        output += static_cast<char>(0xf0 | (value >> 18));
        output += static_cast<char>(0x80 | ((value >> 12) & 63));
        output += static_cast<char>(0x80 | ((value >> 6) & 63));
        output += static_cast<char>(0x80 | (value & 63));
    }
}
struct Number { std::string_view text; };
struct Json {
    using Array = std::vector<Json>;
    using Object = std::vector<std::pair<std::string, Json>>;
    std::variant<std::nullptr_t, bool, Number, std::string, Array, Object> value;
};

// The retained package parser is private and deliberately accepts a canonical,
// integer-only dialect. Semantic replies use normal unordered JSON and finite
// fractional geometry, so this bounded reader keeps that package contract intact.
class Parser {
public:
    explicit Parser(std::string_view input) : input_(input) {}
    Json parse() {
        auto result = value(0); space();
        require(position_ == input_.size(), "Trailing semantic JSON bytes");
        return result;
    }
private:
    std::string_view input_;
    std::size_t position_ = 0, values_ = 0;
    void space() {
        while (position_ < input_.size()) {
            const auto byte = input_[position_];
            if (byte != ' ' && byte != '\t' && byte != '\r' && byte != '\n') break;
            ++position_;
        }
    }
    char take() {
        require(position_ < input_.size(), "Truncated semantic JSON");
        return input_[position_++];
    }
    bool consume(char byte) {
        if (position_ < input_.size() && input_[position_] == byte) { ++position_; return true; }
        return false;
    }
    void literal(std::string_view expected) {
        require(input_.substr(position_, expected.size()) == expected, "Invalid semantic JSON literal");
        position_ += expected.size();
    }
    unsigned hex4() {
        unsigned result = 0;
        for (unsigned n = 0; n < 4; ++n) {
            const auto byte = take(); unsigned digit = 0;
            if (byte >= '0' && byte <= '9') digit = static_cast<unsigned>(byte - '0');
            else if (byte >= 'a' && byte <= 'f') digit = static_cast<unsigned>(byte - 'a' + 10);
            else if (byte >= 'A' && byte <= 'F') digit = static_cast<unsigned>(byte - 'A' + 10);
            else require(false, "Invalid semantic JSON escape");
            result = (result << 4) | digit;
        }
        return result;
    }
    std::string string() {
        require(take() == '"', "Expected semantic JSON string");
        std::string output;
        for (;;) {
            const auto byte = take();
            if (byte == '"') break;
            require(static_cast<unsigned char>(byte) >= 32, "Control byte in semantic JSON string");
            if (byte != '\\') output += byte;
            else switch (take()) {
                case '"': output += '"'; break;
                case '\\': output += '\\'; break;
                case '/': output += '/'; break;
                case 'b': output += '\b'; break;
                case 'f': output += '\f'; break;
                case 'n': output += '\n'; break;
                case 'r': output += '\r'; break;
                case 't': output += '\t'; break;
                case 'u': {
                    auto codepoint = hex4();
                    if (codepoint >= 0xd800 && codepoint <= 0xdbff) {
                        require(take() == '\\' && take() == 'u', "Unpaired semantic JSON surrogate");
                        const auto low = hex4();
                        require(low >= 0xdc00 && low <= 0xdfff, "Unpaired semantic JSON surrogate");
                        codepoint = 0x10000 + ((codepoint - 0xd800) << 10) + low - 0xdc00;
                    } else require(codepoint < 0xdc00 || codepoint > 0xdfff, "Unpaired semantic JSON surrogate");
                    append_utf8(output, codepoint); break;
                }
                default: require(false, "Invalid semantic JSON escape");
            }
            require(output.size() <= max_string_bytes, "Semantic JSON string limit exceeded");
        }
        require(gui::valid_utf8(output), "Semantic JSON string is not scalar UTF-8 without zero bytes");
        return output;
    }
    Number number() {
        const auto start = position_;
        consume('-');
        if (!consume('0')) {
            require(position_ < input_.size() && input_[position_] >= '1' && input_[position_] <= '9',
                "Invalid semantic JSON number");
            while (position_ < input_.size() && input_[position_] >= '0' && input_[position_] <= '9') ++position_;
        }
        if (consume('.')) {
            const auto digits = position_;
            while (position_ < input_.size() && input_[position_] >= '0' && input_[position_] <= '9') ++position_;
            require(position_ != digits, "Invalid semantic JSON fraction");
        }
        if (consume('e') || consume('E')) {
            if (!consume('+')) consume('-');
            const auto digits = position_;
            while (position_ < input_.size() && input_[position_] >= '0' && input_[position_] <= '9') ++position_;
            require(position_ != digits, "Invalid semantic JSON exponent");
        }
        require(position_ - start <= 128, "Semantic JSON number limit exceeded");
        return {input_.substr(start, position_ - start)};
    }
    Json value(std::size_t depth) {
        require(depth <= max_document_semantic_json_depth, "Semantic JSON depth limit exceeded");
        require(++values_ <= max_document_semantic_json_values, "Semantic JSON value limit exceeded");
        space(); require(position_ < input_.size(), "Truncated semantic JSON value");
        switch (input_[position_]) {
            case 'n': literal("null"); return Json{nullptr};
            case 't': literal("true"); return Json{true};
            case 'f': literal("false"); return Json{false};
            case '"': return Json{string()};
            case '[': {
                ++position_; space(); Json::Array array;
                if (consume(']')) return Json{std::move(array)};
                for (;;) {
                    array.push_back(value(depth + 1)); space();
                    if (consume(']')) break;
                    require(consume(','), "Invalid semantic JSON array");
                }
                return Json{std::move(array)};
            }
            case '{': {
                ++position_; space(); Json::Object object; std::set<std::string> keys;
                if (consume('}')) return Json{std::move(object)};
                for (;;) {
                    space(); auto key = string();
                    require(keys.insert(key).second, "Duplicate semantic JSON key");
                    space(); require(consume(':'), "Invalid semantic JSON object");
                    object.emplace_back(std::move(key), value(depth + 1)); space();
                    if (consume('}')) break;
                    require(consume(','), "Invalid semantic JSON object");
                }
                return Json{std::move(object)};
            }
            default: return Json{number()};
        }
    }
};
template<class T> const T& as(const Json& value) {
    const auto* result = std::get_if<T>(&value.value);
    require(result != nullptr, "Unexpected semantic JSON field type"); return *result;
}
bool is_null(const Json& value) { return std::holds_alternative<std::nullptr_t>(value.value); }
const Json& field(const Json& value, std::string_view key) {
    const auto& object = as<Json::Object>(value);
    const auto found = std::find_if(object.begin(), object.end(), [&](const auto& item) { return item.first == key; });
    require(found != object.end(), "Missing semantic JSON field"); return found->second;
}
void fields(const Json& value, std::initializer_list<std::string_view> expected) {
    const auto& object = as<Json::Object>(value);
    require(object.size() == expected.size(), "Unknown or missing semantic JSON fields");
    for (const auto key : expected) (void)field(value, key);
}
std::uint64_t integer(const Json& value, std::uint64_t maximum = safe_integer, std::uint64_t minimum = 1) {
    const auto text = as<Number>(value).text;
    require(!text.empty(), "Invalid semantic JSON integer");
    std::uint64_t result = 0;
    for (const char byte : text) {
        require(byte >= '0' && byte <= '9', "Semantic JSON integer must use unsigned decimal digits");
        const auto digit = static_cast<unsigned>(byte - '0');
        require(result <= (maximum - digit) / 10, "Semantic JSON integer exceeds range");
        result = result * 10 + digit;
    }
    require(result >= minimum && result <= maximum, "Semantic JSON integer exceeds range"); return result;
}
double number(const Json& value) {
    const auto text = as<Number>(value).text;
    double result = 0;
    const auto parsed = std::from_chars(text.data(), text.data() + text.size(), result, std::chars_format::general);
    require(parsed.ec == std::errc{} && parsed.ptr == text.data() + text.size() && std::isfinite(result),
        "Semantic JSON geometry must be finite");
    return result;
}
std::size_t utf16_units(std::string_view value) {
    std::size_t result = 0;
    for (std::size_t at = 0; at < value.size();) {
        const auto first = static_cast<unsigned char>(value[at]);
        const std::size_t bytes = first < 0x80 ? 1 : first < 0xe0 ? 2 : first < 0xf0 ? 3 : 4;
        result += bytes == 4 ? 2 : 1; at += bytes;
    }
    return result;
}
bool text_boundary(std::string_view value, std::uint32_t offset) {
    std::size_t units = 0;
    for (std::size_t at = 0; at < value.size();) {
        if (units == offset) return true;
        const auto first = static_cast<unsigned char>(value[at]);
        const std::size_t bytes = first < 0x80 ? 1 : first < 0xe0 ? 2 : first < 0xf0 ? 3 : 4;
        units += bytes == 4 ? 2 : 1; at += bytes;
    }
    return units == offset;
}
DocumentWhiteSpace whitespace(std::string_view value, bool& degraded) {
    if (value == "normal") return DocumentWhiteSpace::normal;
    if (value == "pre") return DocumentWhiteSpace::pre;
    if (value == "pre-wrap") return DocumentWhiteSpace::pre_wrap;
    degraded = true;
    return value == "break-spaces" ? DocumentWhiteSpace::pre_wrap : DocumentWhiteSpace::normal;
}
DocumentNativePoint point(const Json& value, std::string_view node, std::string_view offset) {
    return {integer(field(value, node)), static_cast<std::uint32_t>(integer(field(value, offset),
        std::numeric_limits<std::uint32_t>::max(), 0))};
}
gui::Rect rectangle(const Json& value) {
    fields(value, {"x", "y", "width", "height"});
    gui::Rect result{number(field(value, "x")), number(field(value, "y")),
        number(field(value, "width")), number(field(value, "height"))};
    require(result.width >= 0 && result.height >= 0, "Negative semantic selection extent"); return result;
}
} // namespace

DocumentSemanticReply decode_appended_document(std::string_view json,
    std::uint64_t generation, std::uint64_t expected_request_id) {
    require(generation && expected_request_id && expected_request_id <= safe_integer, "Invalid semantic decoder context");
    require(!json.empty() && json.size() <= max_document_semantic_json_bytes, "Semantic JSON byte limit exceeded");
    require(gui::valid_utf8(json), "Semantic JSON input must be valid UTF-8 without zero bytes");
    const auto root = Parser(json).parse();
    const bool ok = as<bool>(field(root, "ok"));
    if (ok) fields(root, {"requestId", "ok", "epoch", "revision", "editorState", "truncated", "activeNode", "selection", "nodes"});
    else fields(root, {"requestId", "ok", "code", "epoch"});
    DocumentSemanticReply result;
    result.request_id = integer(field(root, "requestId"));
    require(result.request_id == expected_request_id, "Mismatched semantic request identity");
    result.epoch = integer(field(root, "epoch"), std::numeric_limits<std::uint32_t>::max());
    if (!ok) {
        result.error_code = as<std::string>(field(root, "code"));
        require(!result.error_code.empty() && utf16_units(result.error_code) <= AppendedDocument::max_field_units,
            "Invalid semantic producer error code");
        return result;
    }
    const auto& editor = field(root, "editorState"); fields(editor, {"revision", "flags"});
    result.editor_state = DocumentEditorState{
        static_cast<std::uint32_t>(integer(field(editor, "revision"), static_cast<std::uint64_t>(std::numeric_limits<std::int32_t>::max()))),
        static_cast<std::uint32_t>(integer(field(editor, "flags"), 31, 0))};
    DocumentSnapshot snapshot;
    snapshot.version = {generation, result.epoch, integer(field(root, "revision"))};
    snapshot.truncated = as<bool>(field(root, "truncated"));
    const auto& active = field(root, "activeNode");
    if (!is_null(active)) snapshot.active_node = integer(active);
    const auto& nodes = as<Json::Array>(field(root, "nodes"));
    require(nodes.size() <= AppendedDocument::max_nodes, "Semantic node limit exceeded");
    snapshot.nodes.reserve(nodes.size()); result.metadata.reserve(nodes.size());
    std::map<std::uint64_t, std::size_t> identities;
    std::size_t wire_text_units = 0;
    const auto text = [&](const Json& object, std::string_view key, bool budget = true) {
        const auto& value = as<std::string>(field(object, key));
        const auto count = utf16_units(value);
        require(count <= AppendedDocument::max_field_units, "Semantic field text limit exceeded");
        if (budget) {
            require(count <= AppendedDocument::max_text_units - wire_text_units, "Semantic aggregate text limit exceeded");
            wire_text_units += count;
        }
        return value;
    };
    for (const auto& entry : nodes) {
        const auto& type = as<std::string>(field(entry, "type"));
        DocumentNode node; node.id = integer(field(entry, "id"));
        require(identities.emplace(node.id, snapshot.nodes.size()).second, "Duplicate semantic node identity");
        const auto& parent = field(entry, "parent");
        if (!is_null(parent)) node.parent = integer(parent);
        if (type == "text") {
            fields(entry, {"id", "parent", "type", "text"});
            node.kind = DocumentNodeKind::text; node.text = text(entry, "text");
        } else {
            require(type == "element", "Unknown semantic node type");
            fields(entry, {"id", "parent", "type", "tag", "role", "name", "display", "whiteSpace",
                "editable", "disabled", "readonly", "masked", "value", "checked", "href"});
            node.tag = text(entry, "tag", false);
            require(!node.tag.empty(), "Empty semantic element tag");
            node.name = text(entry, "name");
            node.value = text(entry, "value"); node.href = text(entry, "href");
            node.editable = as<bool>(field(entry, "editable")); node.disabled = as<bool>(field(entry, "disabled"));
            node.masked = as<bool>(field(entry, "masked"));
            require(!node.masked || node.value.empty(), "Masked semantic control exposes a value");
            DocumentNodeMetadata metadata;
            metadata.node = node.id; metadata.role = text(entry, "role"); metadata.display = text(entry, "display");
            metadata.white_space = text(entry, "whiteSpace");
            metadata.read_only = as<bool>(field(entry, "readonly")); metadata.checked = as<bool>(field(entry, "checked"));
            node.white_space = whitespace(metadata.white_space, result.degraded.whitespace);
            result.metadata.push_back(std::move(metadata));
        }
        snapshot.nodes.push_back(std::move(node));
    }
    const auto& selected = field(root, "selection");
    if (!is_null(selected)) {
        fields(selected, {"anchorNode", "anchorOffset", "focusNode", "focusOffset", "focusRect"});
        DocumentWireSelection selection{{point(selected, "anchorNode", "anchorOffset"),
            point(selected, "focusNode", "focusOffset")}, rectangle(field(selected, "focusRect"))};
        for (auto* endpoint : {&selection.endpoints.anchor, &selection.endpoints.focus}) {
            const auto found = identities.find(endpoint->node);
            require(found != identities.end(), "Semantic selection names an absent node");
            const auto& node = snapshot.nodes[found->second];
            if (node.kind == DocumentNodeKind::element) {
                endpoint->kind = DocumentNativeOffsetKind::element_child_index;
                result.degraded.element_selection = true;
            } else if (endpoint->offset > utf16_units(node.text))
                require(snapshot.truncated, "Semantic selection exceeds exported text");
            else require(text_boundary(node.text, endpoint->offset), "Semantic selection splits a surrogate pair");
        }
        result.degraded.truncated_selection = snapshot.truncated;
        if (!result.degraded.element_selection && !result.degraded.truncated_selection)
            snapshot.selection = DocumentSelection{
                {selection.endpoints.anchor.node, selection.endpoints.anchor.offset},
                {selection.endpoints.focus.node, selection.endpoints.focus.offset}};
        result.original_selection = selection;
    }
    // Reuse the utility's structural/identity/UTF-8 invariants without mutating
    // any caller-owned document. Schema and all omitted metadata were validated
    // above, including the producer's aggregate UTF-16 text budget.
    AppendedDocument validator; validator.accept(snapshot);
    result.snapshot = std::move(snapshot);
    return result;
}

} // namespace foundation::ui
