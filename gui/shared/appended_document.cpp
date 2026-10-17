#include "appended_document.hpp"

#include <algorithm>
#include <cmath>
#include <iterator>
#include <tuple>
#include <map>
#include <stdexcept>
#include <unordered_map>
#include <utility>

namespace foundation::ui {
namespace {
constexpr std::uint64_t safe_integer = 9007199254740991ULL;
void require(bool condition, const char* error) {
    if (!condition) throw std::invalid_argument(error);
}
struct Scalar { std::size_t bytes; std::uint32_t units; };
Scalar scalar(std::string_view text, std::size_t offset) {
    const auto first = static_cast<unsigned char>(text[offset]);
    if (first < 0x80) return {1, 1};
    if (first < 0xe0) return {2, 1};
    if (first < 0xf0) return {3, 1};
    return {4, 2};
}
std::size_t units(std::string_view text) {
    std::size_t result = 0;
    for (std::size_t at = 0; at < text.size();) {
        const auto part = scalar(text, at); at += part.bytes; result += part.units;
    }
    return result;
}
bool boundary(std::string_view text, std::uint32_t offset) {
    std::size_t count = 0;
    for (std::size_t at = 0; at < text.size();) {
        if (count == offset) return true;
        const auto part = scalar(text, at); at += part.bytes; count += part.units;
    }
    return count == offset;
}
struct Index {
    const DocumentSnapshot& snapshot;
    std::unordered_map<std::uint64_t, std::size_t> positions;
    std::vector<std::vector<std::size_t>> children;
    std::vector<bool> hidden, concealed, disabled;
    explicit Index(const DocumentSnapshot& source) : snapshot(source), children(source.nodes.size()),
        hidden(source.nodes.size()), concealed(source.nodes.size()), disabled(source.nodes.size()) {
        for (std::size_t n = 0; n < source.nodes.size(); ++n) {
            const auto& node = source.nodes[n]; positions.emplace(node.id, n);
            const auto parent = positions.find(node.parent);
            const bool has_parent = node.parent && parent != positions.end();
            if (has_parent) children[parent->second].push_back(n);
            const bool inert_markup = node.kind == DocumentNodeKind::element &&
                (node.tag == "script" || node.tag == "style" || node.tag == "template" || node.tag == "noscript");
            hidden[n] = node.omitted || inert_markup || (has_parent && (hidden[parent->second] || concealed[parent->second]));
            concealed[n] = node.masked || (has_parent && concealed[parent->second]);
            disabled[n] = node.disabled || (has_parent && disabled[parent->second]);
        }
    }
    std::optional<std::size_t> find(std::uint64_t id) const {
        const auto found = positions.find(id);
        return found == positions.end() ? std::nullopt : std::optional{found->second};
    }
    bool point(DocumentPoint point, bool visible) const {
        const auto at = find(point.node);
        return at && snapshot.nodes[*at].kind == DocumentNodeKind::text &&
            (!visible || (!hidden[*at] && !concealed[*at])) &&
            boundary(snapshot.nodes[*at].text, point.utf16_offset);
    }
    bool selection(DocumentSelection selection, bool visible) const {
        return point(selection.anchor, visible) && point(selection.focus, visible);
    }
};
bool activate(const DocumentNode& node) {
    return node.kind == DocumentNodeKind::element && (node.tag == "a" || node.tag == "button");
}
bool block(std::string_view tag) {
    constexpr std::string_view tags[]{"address", "article", "aside", "blockquote", "body", "dd", "details",
        "div", "dl", "dt", "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3",
        "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre", "section",
        "table", "tbody", "tfoot", "thead", "tr", "ul"};
    return std::find(std::begin(tags), std::end(tags), tag) != std::end(tags);
}
bool form(std::string_view tag) { return tag == "input" || tag == "textarea" || tag == "select"; }
bool white(char byte) { return byte == ' ' || byte == '\t' || byte == '\n' || byte == '\r' || byte == '\f'; }
struct Glyph {
    std::string text;
    std::optional<DocumentSelection> source;
    bool space = false;
};

class Reflow {
    const DocumentSnapshot& document_;
    const Index& index_;
    const gui::TextMeasure& measure_;
    double width_;
    std::size_t line_bytes_ = 0, measured_bytes_ = 0;
    std::vector<Glyph> line_;
    std::optional<DocumentSelection> pending_space_;
    std::map<std::string, std::size_t> row_ids_;
    std::uint64_t anchor_ = 0;
    bool stopped_ = false, trailing_hard_break_ = false;

    double width(std::string_view text) const {
        const auto size = measure_({std::string(text), {}, gui::coordinate_limit, 1, gui::TextWrap::none});
        require(std::isfinite(size.width) && size.width >= 0 && std::isfinite(size.height) && size.height >= 0,
            "Invalid document text measurement");
        return size.width;
    }
    std::string text(std::size_t end) const {
        std::string result;
        for (std::size_t n = 0; n < end; ++n) result += line_[n].text;
        return result;
    }
    void emit(std::size_t count, bool force = false) {
        if (stopped_ || (!count && !force)) return;
        if (output.rows.size() == AppendedDocument::max_rows - 1) { stopped_ = true; output.incomplete = true; return; }
        DocumentRow row;
        for (std::size_t n = 0; n < count; ++n) {
            const auto& glyph = line_[n]; const auto begin = row.text.size(); row.text += glyph.text;
            if (glyph.source) row.sources.push_back({begin, row.text.size(), glyph.source->anchor, glyph.source->focus});
        }
        std::string base;
        if (!row.sources.empty()) base = "text/" + std::to_string(row.sources.front().first.node) + "/" +
            std::to_string(row.sources.front().first.utf16_offset);
        else base = "gap/" + std::to_string(anchor_);
        row.id = base + "/" + std::to_string(row_ids_[base]++);
        line_bytes_ -= row.text.size();
        output.rows.push_back(std::move(row));
        line_.erase(line_.begin(), line_.begin() + static_cast<std::ptrdiff_t>(count));
    }
    std::optional<double> measured_line_width() {
        // Preflight before constructing or copying the line. A valid measure
        // callback can give arbitrarily long combining/joining text zero width;
        // width-based wrapping alone would permit quadratic work.
        if (line_bytes_ > AppendedDocument::max_reflow_measure_bytes - measured_bytes_) {
            output.incomplete = true;
            emit(line_.size()); // Preserve the bounded retained prefix and source ranges.
            stopped_ = true;
            return std::nullopt;
        }
        measured_bytes_ += line_bytes_;
        return width(text(line_.size()));
    }
    void append(Glyph glyph, DocumentWhiteSpace policy) {
        if (stopped_) return;
        line_bytes_ += glyph.text.size();
        line_.push_back(std::move(glyph));
        if (policy == DocumentWhiteSpace::pre || line_.size() < 2) return;
        const auto measured = measured_line_width();
        if (!measured || *measured <= width_) return;
        std::optional<std::size_t> split;
        for (std::size_t n = 0; n + 1 < line_.size(); ++n) if (line_[n].space) split = n;
        if (split && *split) {
            const auto before = *split;
            emit(before);
            if (policy == DocumentWhiteSpace::normal && !line_.empty() && line_.front().space) {
                line_bytes_ -= line_.front().text.size();
                line_.erase(line_.begin());
            }
        } else emit(line_.size() - 1);
        // A single Unicode scalar may have a literal representation wider than
        // a narrow viewport. Retain that scalar and source identity intact.
        while (!stopped_ && line_.size() > 1) {
            const auto remaining = measured_line_width();
            if (!remaining || *remaining <= width_) break;
            emit(line_.size() - 1);
        }
    }
    void flush(bool force = false) { pending_space_.reset(); emit(line_.size(), force); }
    void synthetic(std::string_view value, DocumentWhiteSpace policy = DocumentWhiteSpace::normal) {
        if (!value.empty()) trailing_hard_break_ = false;
        for (char byte : value) append({std::string(1, byte), std::nullopt, byte == ' '}, policy);
    }
    void prose(const DocumentNode& node, DocumentWhiteSpace policy) {
        std::uint32_t offset = 0;
        for (std::size_t at = 0; at < node.text.size() && !stopped_;) {
            const auto part = scalar(node.text, at);
            DocumentSelection source{{node.id, offset}, {node.id, offset + part.units}};
            const auto bytes = node.text.substr(at, part.bytes);
            at += part.bytes; offset += part.units;
            if (policy == DocumentWhiteSpace::normal && part.bytes == 1 && white(bytes[0])) {
                if (pending_space_) pending_space_->focus = source.focus; else pending_space_ = source;
                continue;
            }
            if (policy != DocumentWhiteSpace::normal && (bytes == "\n" || bytes == "\r")) {
                if (bytes == "\r" && at < node.text.size() && node.text[at] == '\n') { ++at; ++offset; }
                flush(true); trailing_hard_break_ = true; continue;
            }
            trailing_hard_break_ = false;
            if (pending_space_) {
                if (!line_.empty()) append({" ", pending_space_, true}, policy);
                pending_space_.reset();
            }
            if (policy != DocumentWhiteSpace::normal && bytes == "\t") {
                // Keep tabs as source text. The public terminal measure/renderer
                // consistently gives them their safe literal representation.
                append({bytes, source, true}, policy);
            } else append({bytes, source, bytes == " "}, policy);
        }
    }
    std::string label(std::size_t root) const {
        const auto& node = document_.nodes[root];
        if (!node.name.empty()) return node.name;
        std::string value;
        std::vector<std::size_t> stack{root};
        while (!stack.empty()) {
            const auto current = stack.back(); stack.pop_back();
            if (index_.hidden[current] || index_.concealed[current]) continue;
            const auto& child = document_.nodes[current];
            if (child.kind == DocumentNodeKind::text) value += child.text;
            for (auto it = index_.children[current].rbegin(); it != index_.children[current].rend(); ++it) stack.push_back(*it);
        }
        std::string result; bool space = false;
        for (const char byte : value) {
            if (white(byte)) { space = !result.empty(); continue; }
            if (space) result += ' ';
            space = false; result += byte;
        }
        if (result.empty()) result = node.tag == "a" ? node.href : "Button";
        return result;
    }
    void control(std::size_t at, std::string value, bool actionable) {
        flush();
        if (stopped_) return;
        if (output.rows.size() == AppendedDocument::max_rows - 1) { stopped_ = true; output.incomplete = true; return; }
        DocumentRow row;
        row.id = "node/" + std::to_string(document_.nodes[at].id);
        row.text = std::move(value); row.node = document_.nodes[at].id;
        row.activatable = actionable && !index_.disabled[at]; output.rows.push_back(std::move(row));
    }
public:
    DocumentProjection output;
    Reflow(const DocumentSnapshot& document, const Index& index, const gui::TextMeasure& measure, double width)
        : document_(document), index_(index), measure_(measure), width_(width) {
        output.version = document.version; output.incomplete = document.truncated;
        if (document.active_node) {
            const auto at = index.find(*document.active_node);
            if (at && !index.hidden[*at] &&
                !(document.nodes[*at].kind == DocumentNodeKind::text && index.concealed[*at])) output.active_node = document.active_node;
        }
        if (!document.truncated && document.selection && index.selection(*document.selection, true)) output.selection = document.selection;
    }
    void run() {
        struct Visit { std::size_t at; DocumentWhiteSpace policy; bool exit, rich; };
        std::vector<Visit> stack;
        for (std::size_t n = document_.nodes.size(); n > 0; --n)
            if (!document_.nodes[n - 1].parent) stack.push_back({n - 1, DocumentWhiteSpace::normal, false, false});
        while (!stack.empty() && !stopped_) {
            const auto visit = stack.back(); stack.pop_back(); const auto& node = document_.nodes[visit.at]; anchor_ = node.id;
            if (index_.hidden[visit.at]) continue;
            if (visit.exit) {
                if (block(node.tag)) { flush(trailing_hard_break_); trailing_hard_break_ = false; }
                continue;
            }
            if (node.kind == DocumentNodeKind::text) {
                if (!index_.concealed[visit.at]) prose(node, visit.policy);
                continue;
            }
            if (node.tag == "script" || node.tag == "style" || node.tag == "template" || node.tag == "noscript") continue;
            if (node.masked) { control(visit.at, "[password: read only]", false); continue; }
            if (activate(node)) {
                control(visit.at, std::string(node.tag == "a" ? "[link] " : "[button] ") + label(visit.at), true); continue;
            }
            if (form(node.tag)) {
                control(visit.at, "[" + node.tag + ": read only] " + (node.name.empty() ? node.value : node.name + ": " + node.value), false); continue;
            }
            if (node.tag == "br") { flush(true); continue; }
            if (node.tag == "img" || node.tag == "canvas" || node.tag == "video" || node.tag == "audio") {
                flush(); synthetic("[" + node.tag + ": unavailable]"); flush();
            }
            if (block(node.tag)) flush();
            if (node.editable && !visit.rich) control(visit.at, "[rich text: read only]" + (node.name.empty() ? "" : " " + node.name), false);
            if (node.tag == "li") synthetic("- ");
            if (node.tag.size() == 2 && node.tag[0] == 'h' && node.tag[1] >= '1' && node.tag[1] <= '6') synthetic("# ");
            if ((node.tag == "td" || node.tag == "th") && !line_.empty()) synthetic(" | ");
            auto policy = node.white_space;
            if (node.tag == "pre" && policy == DocumentWhiteSpace::normal) policy = DocumentWhiteSpace::pre;
            stack.push_back({visit.at, policy, true, visit.rich || node.editable});
            for (auto it = index_.children[visit.at].rbegin(); it != index_.children[visit.at].rend(); ++it)
                stack.push_back({*it, policy, false, visit.rich || node.editable});
        }
        flush();
        if (output.incomplete) {
            output.selection.reset();
            output.rows.push_back({"incomplete", "[document incomplete: content omitted by limits]", {}, std::nullopt, false});
        }
    }
};
} // namespace

void AppendedDocument::accept(DocumentSnapshot snapshot) {
    const auto version = snapshot.version;
    require(version.generation && version.epoch && version.epoch <= safe_integer && version.revision && version.revision <= safe_integer,
        "Invalid document version");
    require(snapshot.nodes.size() <= max_nodes, "Document node limit exceeded");
    std::unordered_map<std::uint64_t, std::size_t> ids;
    std::size_t text_units = 0;
    for (std::size_t n = 0; n < snapshot.nodes.size(); ++n) {
        const auto& node = snapshot.nodes[n];
        require(node.id && node.id <= safe_integer && !ids.contains(node.id), "Invalid or duplicate document node ID");
        require(!node.parent || ids.contains(node.parent), "Document parents must precede children");
        require(node.kind == DocumentNodeKind::element || node.kind == DocumentNodeKind::text, "Unknown document node kind");
        require(node.parent || node.kind == DocumentNodeKind::element, "Document roots must be elements");
        require(node.white_space == DocumentWhiteSpace::normal || node.white_space == DocumentWhiteSpace::pre ||
            node.white_space == DocumentWhiteSpace::pre_wrap, "Unknown document whitespace policy");
        for (const auto* value : {&node.tag, &node.text, &node.name, &node.value, &node.href}) {
            require(gui::valid_utf8(*value), "Document text must be valid UTF-8 without zero bytes");
            const auto count = units(*value);
            require(count <= max_field_units, "Document field text limit exceeded");
            // The exporter bounds presentation data, but emits tag names
            // separately. Keep their per-field cap without charging tags to
            // the text/name/value/href subset of its aggregate budget.
            if (value != &node.tag) {
                require(count <= max_text_units - text_units, "Document text limit exceeded");
                text_units += count;
            }
        }
        if (node.parent) require(snapshot.nodes[ids.at(node.parent)].kind == DocumentNodeKind::element, "Text nodes cannot contain children");
        ids.emplace(node.id, n);
    }
    if (snapshot.active_node) require(*snapshot.active_node && *snapshot.active_node <= safe_integer, "Invalid active node ID");
    const Index index(snapshot);
    if (snapshot.selection) require(index.selection(*snapshot.selection, false), "Invalid document selection");
    if (snapshot_) {
        const auto prior = snapshot_->version;
        const auto freshness = std::tie(version.generation, version.epoch, version.revision);
        const auto previous = std::tie(prior.generation, prior.epoch, prior.revision);
        require(freshness >= previous, "Stale document snapshot");
        require(freshness != previous || snapshot == *snapshot_, "Document version reused with different values");
    }
    snapshot_ = std::move(snapshot);
}
const DocumentSnapshot* AppendedDocument::snapshot() const noexcept { return snapshot_ ? &*snapshot_ : nullptr; }

DocumentProjection AppendedDocument::project(std::size_t columns, std::size_t rows, const gui::TextMeasure& measure) const {
    require(snapshot_.has_value(), "No document snapshot");
    // A measurement callback may publish a new snapshot. Freeze owned input
    // before the first callback so all returned rows share one exact version.
    const DocumentSnapshot document = *snapshot_;
    require(columns >= 2 && columns <= 500 && rows >= 2 && rows <= 200 && bool(measure), "Invalid document viewport");
    const auto cell = measure({"M", {}, gui::coordinate_limit, 1, gui::TextWrap::none});
    require(std::isfinite(cell.width) && cell.width > 0 && std::isfinite(cell.height) && cell.height > 0 &&
        cell.width <= 4096 && cell.height <= 4096, "Invalid document cell measurement");
    const auto content_width = double(columns - 1) * cell.width;
    const Index index(document);
    Reflow reflow(document, index, measure, content_width); reflow.run();
    auto result = std::move(reflow.output);
    result.view.revision = result.version.revision; result.view.title = "Appended document (read only)";
    result.view.client_size = {double(columns) * cell.width, double(rows) * cell.height};
    gui::Widget list; list.spec.key = {"appended/document/" + std::to_string(result.version.epoch), result.version.generation};
    list.spec.kind = gui::Kind::list; list.spec.row_height = cell.height; list.spec.activate_on_select = false;
    list.state.bounds = {0, 0, result.view.client_size.width, result.view.client_size.height};
    list.state.enabled = !document.nodes.empty() && !result.rows.empty();
    double extent = result.view.client_size.width;
    for (const auto& row : result.rows) {
        const auto measured = measure({row.text, {}, gui::coordinate_limit, 1, gui::TextWrap::none});
        require(std::isfinite(measured.width) && measured.width >= 0 && std::isfinite(measured.height) && measured.height >= 0,
            "Invalid document text measurement");
        const auto width = std::max(content_width, measured.width);
        gui::Record record; record.id = row.id; record.accessible_text = row.text; record.activatable = row.activatable;
        record.cells.push_back({row.text, {cell.width, 0, width, cell.height}, {}, gui::TextWrap::none});
        list.state.records.push_back(std::move(record)); extent = std::max(extent, cell.width + width);
        if (result.active_node && row.node == result.active_node) list.state.selected = row.id;
    }
    if (list.state.enabled && !list.state.selected && !result.rows.empty()) list.state.selected = result.rows.front().id;
    list.state.content_size = {extent, double(result.rows.size()) * cell.height};
    result.view.widgets.push_back(std::move(list));
    gui::validate_snapshot(result.view);
    return result;
}
std::optional<DocumentIntent> AppendedDocument::intent(const DocumentProjection& projection,
    std::string_view row, DocumentAction action) const {
    if (!snapshot_ || projection.version != snapshot_->version || action == DocumentAction::select) return std::nullopt;
    const auto found = std::find_if(projection.rows.begin(), projection.rows.end(), [&](const auto& value) { return value.id == row; });
    if (found == projection.rows.end() || !found->node || (action == DocumentAction::activate && !found->activatable)) return std::nullopt;
    DocumentIntent result{projection.version, action, *found->node, std::nullopt};
    return current(result) ? std::optional{result} : std::nullopt;
}
std::optional<DocumentIntent> AppendedDocument::select(const DocumentProjection& projection, DocumentSelection selection) const {
    if (projection.incomplete) return std::nullopt;
    DocumentIntent result{projection.version, DocumentAction::select, 0, selection};
    return current(result) ? std::optional{result} : std::nullopt;
}
bool AppendedDocument::current(const DocumentIntent& intent) const noexcept {
    if (!snapshot_ || intent.version != snapshot_->version) return false;
    try {
        const Index index(*snapshot_);
        if (intent.action == DocumentAction::select)
            return !snapshot_->truncated && !intent.node && intent.selection && index.selection(*intent.selection, true);
        if (intent.selection) return false;
        const auto at = index.find(intent.node);
        if (!at || index.hidden[*at] || index.disabled[*at]) return false;
        const auto& node = snapshot_->nodes[*at];
        if (node.kind != DocumentNodeKind::element) return false;
        if (intent.action == DocumentAction::focus) return true;
        return intent.action == DocumentAction::activate && !node.masked && activate(node);
    } catch (...) { return false; }
}

} // namespace foundation::ui
