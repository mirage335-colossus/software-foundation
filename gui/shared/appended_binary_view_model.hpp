#pragma once

#include <foundation/appended/registry.hpp>
#include <gui/contract.hpp>
#include <gui/runtime.hpp>
#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <functional>
#include <limits>
#include <map>
#include <stdexcept>
#include <type_traits>
#include <utility>
#include <vector>

namespace foundation::appended {
namespace binary_view_detail {
using Span = std::span<const std::uint8_t>;
constexpr std::size_t max_widgets = 256, max_commands = 128, max_identities = 4096;
constexpr std::size_t max_bitmap_bytes = 262144, max_raster_bytes = 16777216;
constexpr std::size_t max_host_services = 64;
constexpr std::array widget_kinds{gui::Kind::group, gui::Kind::label, gui::Kind::button, gui::Kind::toggle,
    gui::Kind::choice, gui::Kind::text, gui::Kind::list, gui::Kind::bitmap, gui::Kind::menu};
constexpr std::array pixel_formats{gui::PixelFormat::mono1, gui::PixelFormat::gray8, gui::PixelFormat::rgb24};
constexpr std::array text_tones{gui::Tone::normal, gui::Tone::muted, gui::Tone::accent, gui::Tone::error};
constexpr std::array submit_keys{gui::SubmitKey::none, gui::SubmitKey::enter, gui::SubmitKey::control_enter};
constexpr std::array shortcut_keys{gui::ShortcutKey::escape, gui::ShortcutKey::enter, gui::ShortcutKey::f1,
    gui::ShortcutKey::f2, gui::ShortcutKey::f3, gui::ShortcutKey::f4, gui::ShortcutKey::f5, gui::ShortcutKey::f6,
    gui::ShortcutKey::f7, gui::ShortcutKey::f8, gui::ShortcutKey::f9, gui::ShortcutKey::f10, gui::ShortcutKey::f11,
    gui::ShortcutKey::f12, gui::ShortcutKey::z, gui::ShortcutKey::y};
constexpr std::array host_service_kinds{gui::ServiceKind::open_file, gui::ServiceKind::save_file, gui::ServiceKind::prompt,
    gui::ServiceKind::clipboard_write, gui::ServiceKind::open_location, gui::ServiceKind::read_text, gui::ServiceKind::write_text};
constexpr std::array pointer_kinds{gui::PointerKind::click, gui::PointerKind::double_click, gui::PointerKind::move,
    gui::PointerKind::wheel, gui::PointerKind::press, gui::PointerKind::release, gui::PointerKind::cancel,
    gui::PointerKind::context_menu};
constexpr std::array host_service_statuses{gui::ServiceStatus::success, gui::ServiceStatus::cancelled, gui::ServiceStatus::error};

template<class T, std::size_t N> std::uint32_t wire_value(const std::array<T, N>& values, T value) {
    const auto found = std::find(values.begin(), values.end(), value);
    if (found == values.end()) throw std::logic_error("Unsupported public GUI enum value");
    return static_cast<std::uint32_t>(found - values.begin()) + 1;
}
static_assert(std::is_nothrow_move_assignable_v<gui::Snapshot>);


struct InvalidView {};
inline void require(bool condition) { if (!condition) throw InvalidView{}; }

// Views borrow their request only while decoding. All retained GUI values own
// their strings, records and image storage before the handler returns.
class RecordReader {
    std::vector<FieldView> fields_;
public:
    RecordReader(Span bytes, std::uint16_t last) {
        require(decode_record(bytes, fields_) == CodecStatus::ok);
        for (const auto& field : fields_) require(field.id <= last || !field.must_understand);
    }
    const FieldView* find(std::uint16_t id) const {
        for (const auto& field : fields_) if (field.id == id) return &field;
        return nullptr;
    }
    Span bytes(std::uint16_t id, FieldType type, bool needed = false) const {
        const auto* field = find(id);
        require(field || !needed);
        if (!field) return {};
        require(field->type == type);
        return field->value;
    }
    std::uint64_t u64(std::uint16_t id, std::uint64_t fallback = 0, bool needed = false) const {
        const auto* field = find(id); require(field || !needed);
        if (!field) return fallback;
        std::uint64_t value = 0; require(read_u64(*field, value)); return value;
    }
    std::uint32_t u32(std::uint16_t id, std::uint32_t fallback = 0, bool needed = false) const {
        const auto* field = find(id); require(field || !needed);
        if (!field) return fallback;
        std::uint32_t value = 0; require(read_u32(*field, value)); return value;
    }
    double number(std::uint16_t id, double fallback = 0, bool needed = false) const {
        const auto* field = find(id); require(field || !needed);
        if (!field) return fallback;
        require(field->type == FieldType::f64 && field->value.size() == 8);
        std::uint64_t bits = 0;
        for (unsigned n = 0; n < 8; ++n) bits |= std::uint64_t(field->value[n]) << (n * 8);
        const auto value = std::bit_cast<double>(bits);
        require(std::isfinite(value)); return value;
    }
    bool boolean(std::uint16_t id, bool fallback = false) const {
        const auto* field = find(id); if (!field) return fallback;
        require(field->type == FieldType::boolean && field->value.size() == 1 && field->value[0] <= 1);
        return field->value[0] != 0;
    }
    std::string text(std::uint16_t id, bool needed = false, bool identifier = false) const {
        const auto value = bytes(id, FieldType::utf8, needed);
        require(value.size() <= (identifier ? 128u : 65536u));
        return std::string(value.begin(), value.end());
    }
    template<class Function> void list(std::uint16_t id, std::size_t limit, Function function,
                                       bool needed = false) const {
        const auto value = bytes(id, FieldType::record_list, needed);
        if (!find(id)) return;
        require(value.size() >= 4);
        const auto scalar = [](Span input) {
            return std::uint32_t(input[0]) | (std::uint32_t(input[1]) << 8) |
                (std::uint32_t(input[2]) << 16) | (std::uint32_t(input[3]) << 24);
        };
        const auto count = scalar(value.first(4)); require(count <= limit);
        std::size_t offset = 4;
        for (std::uint32_t n = 0; n < count; ++n) {
            require(value.size() - offset >= 4);
            const auto length = scalar(value.subspan(offset, 4)); offset += 4;
            require(length <= value.size() - offset);
            function(value.subspan(offset, length)); offset += length;
        }
        require(offset == value.size());
    }
};

inline gui::WidgetKey key(Span bytes) {
    RecordReader r(bytes, 2); gui::WidgetKey value{r.text(1, true, true), r.u64(2, 0, true)};
    require(!value.id.empty() && value.generation != 0); return value;
}
inline gui::Rect rect(Span bytes) {
    RecordReader r(bytes, 4);
    return {r.number(1, 0, true), r.number(2, 0, true), r.number(3, 0, true), r.number(4, 0, true)};
}
inline gui::Size size(Span bytes) {
    RecordReader r(bytes, 2); return {r.number(1, 0, true), r.number(2, 0, true)};
}
inline gui::Font font(Span bytes) {
    RecordReader r(bytes, 3); gui::Font value; value.size = r.number(1, 14); value.bold = r.boolean(2);
    const auto tone = r.u32(3, 1); require(tone >= 1 && tone <= 4);
    value.tone = text_tones[tone - 1]; return value;
}
inline gui::TextWrap wrap(std::uint32_t value) {
    require(value == 1 || value == 2); return value == 1 ? gui::TextWrap::none : gui::TextWrap::word;
}
inline gui::Option option(Span bytes) {
    RecordReader r(bytes, 4); return {r.text(1, true, true), r.text(2), r.text(3), r.boolean(4, true)};
}
inline gui::Cell cell(Span bytes) {
    RecordReader r(bytes, 4); gui::Cell value; value.text = r.text(1);
    if (r.find(2)) value.bounds = rect(r.bytes(2, FieldType::record));
    if (r.find(3)) value.font = font(r.bytes(3, FieldType::record));
    value.wrap = wrap(r.u32(4, 1)); return value;
}
inline gui::Record row(Span bytes) {
    RecordReader r(bytes, 5); gui::Record value;
    value.id = r.text(1, true, true); value.accessible_text = r.text(2);
    r.list(3, 64, [&](Span entry) { value.cells.push_back(cell(entry)); });
    value.enabled = r.boolean(4, true); value.activatable = r.boolean(5); return value;
}

struct Resource {
    std::uint64_t revision = 0;
    std::uint32_t width = 0, height = 0, format = 0;
    Bytes pixels;
    bool operator==(const Resource&) const = default;
};
using Resources = std::map<std::string, Resource, std::less<>>;
struct Decoded {
    gui::Snapshot view;
    Resources resources;
    std::size_t bitmap_bytes = 0, records = 0;
};

inline gui::BitmapView bitmap(Span bytes, Decoded& decoded) {
    RecordReader r(bytes, 6); gui::BitmapView value;
    value.source_id = r.text(1, true, true);
    Resource resource; resource.revision = r.u64(2, 0, true);
    resource.width = r.u32(3, 0, true); resource.height = r.u32(4, 0, true);
    resource.format = r.u32(5, 0, true);
    require(!value.source_id.empty() && resource.revision && resource.width && resource.height &&
        resource.width <= 4096 && resource.height <= 4096 && resource.format >= 1 && resource.format <= 3);
    const auto format = pixel_formats[resource.format - 1];
    const auto stride = gui::pixel_row_bytes(resource.width, format);
    const auto pixels = r.bytes(6, FieldType::bytes, true);
    require(stride <= max_bitmap_bytes / resource.height && pixels.size() == stride * resource.height &&
        pixels.size() <= max_bitmap_bytes - decoded.bitmap_bytes);
    decoded.bitmap_bytes += pixels.size(); resource.pixels.assign(pixels.begin(), pixels.end());
    auto [entry, inserted] = decoded.resources.emplace(value.source_id, resource);
    require(inserted || entry->second == resource);
    gui::BitmapImage image(resource.width, resource.height, format);
    image.blit(0, 0, {resource.width, resource.height, stride, format, resource.pixels});
    value.revision = resource.revision; value.source = gui::image_bitmap(std::move(image)); return value;
}

inline gui::Widget widget(Span bytes, Decoded& decoded) {
    RecordReader r(bytes, 36); gui::Widget value;
    auto& s = value.spec; auto& v = value.state;
    s.key = {r.text(1, true, true), r.u64(2, 0, true)};
    const auto kind = r.u32(3, 0, true); require(kind >= 1 && kind <= 9);
    s.kind = widget_kinds[kind - 1]; v.bounds = rect(r.bytes(4, FieldType::record, true));
    s.parent = r.text(5, false, true); s.page = r.text(6, false, true);
    v.text = r.text(7); v.label = r.text(8); v.placeholder = r.text(9); v.help = r.text(10);
    v.accessible_name = r.text(11); v.enabled = r.boolean(12, true); v.visible = r.boolean(13, true);
    v.checked = r.boolean(14);
    if (r.find(15)) { auto selected = r.text(15, false, true); if (!selected.empty()) v.selected = std::move(selected); }
    s.text_policy.multiline = r.boolean(16); s.text_policy.read_only = r.boolean(17);
    s.text_policy.max_bytes = r.u32(18, 1048576); require(s.text_policy.max_bytes <= 1048576);
    const auto submit = r.u32(19, 1); require(submit >= 1 && submit <= 3);
    s.text_policy.submit = submit_keys[submit - 1]; v.wrap = wrap(r.u32(20, 1));
    if (r.find(21)) v.font = font(r.bytes(21, FieldType::record));
    r.list(22, 1024, [&](Span entry) { v.options.push_back(option(entry)); });
    r.list(23, 1024, [&](Span entry) {
        require(decoded.records < 1024); ++decoded.records; v.records.push_back(row(entry));
    });
    if (r.find(24)) v.content_size = size(r.bytes(24, FieldType::record));
    if (r.find(25)) v.content_clip = rect(r.bytes(25, FieldType::record));
    s.row_height = r.number(26, 28); s.activate_on_select = r.boolean(27);
    s.follow_tail = r.boolean(28); s.pointer_input = r.boolean(29); s.binding = r.text(30, false, true);
    v.display_text = r.text(31);
    if (r.find(32)) { require(s.kind == gui::Kind::bitmap); v.bitmap = bitmap(r.bytes(32, FieldType::record), decoded); }
    r.list(33, 1024, [&](Span entry) { v.actions.push_back(option(entry)); });
    s.text_policy.masked = r.boolean(34); v.text_frame = r.boolean(35, true); s.context_input = r.boolean(36);
    return value;
}

inline Decoded decode_view(Span bytes, const gui::Snapshot& current) {
    RecordReader r(bytes, 12);
    require(r.u64(1, 0, true) == current.revision && current.revision != std::numeric_limits<std::uint64_t>::max());
    Decoded value; auto& view = value.view; view.revision = current.revision + 1;
    view.title = r.text(2); view.client_size = {r.number(3, current.client_size.width), r.number(4, current.client_size.height)};
    view.display_scale = r.number(5, current.display_scale);
    r.list(6, max_widgets, [&](Span entry) { view.widgets.push_back(widget(entry, value)); }, true);
    r.list(7, max_commands, [&](Span entry) {
        RecordReader c(entry, 4); gui::Command command;
        command.key = {c.text(1, true, true), c.u64(2, 0, true)}; command.enabled = c.boolean(3, true);
        if (c.find(4)) command.scope = key(c.bytes(4, FieldType::record));
        view.commands.push_back(std::move(command));
    });
    r.list(8, 64, [&](Span entry) {
        RecordReader p(entry, 4); view.pages.push_back({p.text(1, true, true), p.text(2), p.boolean(3, true), p.boolean(4, true)});
    });
    if (r.find(9)) { auto page = r.text(9, false, true); if (!page.empty()) view.active_page = std::move(page); }
    if (r.find(10)) view.modal_root = key(r.bytes(10, FieldType::record));
    r.list(11, 128, [&](Span entry) {
        RecordReader b(entry, 6); gui::KeyBinding binding; const auto stroke = b.u32(1, 0, true);
        require(stroke >= 1 && stroke <= 16); binding.key = shortcut_keys[stroke - 1];
        binding.target = key(b.bytes(2, FieldType::record, true));
        binding.control = b.boolean(3); binding.shift = b.boolean(4); binding.alt = b.boolean(5);
        if (b.find(6)) binding.focus = key(b.bytes(6, FieldType::record));
        view.key_bindings.push_back(std::move(binding));
    });
    if (r.find(12)) view.page_bar = rect(r.bytes(12, FieldType::record));
    gui::validate_snapshot(view);
    std::size_t raster_bytes = 0;
    for (const auto& w : view.widgets) if (w.spec.kind == gui::Kind::bitmap) {
        const auto pixels = gui::device_rect({0, 0, w.state.bounds.width, w.state.bounds.height}, view.display_scale);
        const auto stride = gui::pixel_row_bytes(static_cast<unsigned>(pixels.width), view.bitmap_format);
        require(!pixels.height || stride <= (max_raster_bytes - raster_bytes) / static_cast<unsigned>(pixels.height));
        raster_bytes += stride * static_cast<unsigned>(pixels.height);
    }
    return value;
}

class Writer {
    struct Field { std::uint16_t id; FieldType type; Bytes bytes; };
    std::vector<Field> fields_;
public:
    void field(std::uint16_t id, FieldType type, Bytes bytes) { fields_.push_back({id, type, std::move(bytes)}); }
    void u32(std::uint16_t id, std::uint32_t value) { field(id, FieldType::u32, encode_u32(value)); }
    void u64(std::uint16_t id, std::uint64_t value) { field(id, FieldType::u64, encode_u64(value)); }
    void text(std::uint16_t id, std::string_view value) { field(id, FieldType::utf8, Bytes(value.begin(), value.end())); }
    void boolean(std::uint16_t id, bool value) { field(id, FieldType::boolean, {static_cast<std::uint8_t>(value)}); }
    void number(std::uint16_t id, double value) { field(id, FieldType::f64, encode_u64(std::bit_cast<std::uint64_t>(value))); }
    void record(std::uint16_t id, Bytes value) { field(id, FieldType::record, std::move(value)); }
    Bytes finish() {
        std::sort(fields_.begin(), fields_.end(), [](const Field& a, const Field& b) { return a.id < b.id; });
        std::vector<FieldView> views;
        for (const auto& f : fields_) views.push_back({f.id, f.type, false, f.bytes});
        Bytes result;
        if (encode_record(views, result) != CodecStatus::ok) throw std::runtime_error("Cannot encode binary view event");
        return result;
    }
};
inline Bytes encode_key(const gui::WidgetKey& value) { Writer w; w.text(1, value.id); w.u64(2, value.generation); return w.finish(); }
inline Bytes encode_event(const gui::Event& event, std::uint64_t revision) {
    Writer w; w.u64(1, revision);
    std::visit([&](const auto& value) {
        using T = std::decay_t<decltype(value)>;
        if constexpr (std::is_same_v<T, gui::WidgetEvent>) {
            w.u32(2, 1); w.record(3, encode_key(value.target));
            std::visit([&](const auto& input) {
                using I = std::decay_t<decltype(input)>;
                if constexpr (std::is_same_v<I, gui::Activate>) {
                    w.u32(4, 1); if (input.source) w.record(8, encode_key(*input.source));
                } else if constexpr (std::is_same_v<I, gui::SetChecked>) { w.u32(4, 2); w.boolean(7, input.value); }
                else if constexpr (std::is_same_v<I, gui::EditText>) { w.u32(4, 3); w.text(5, input.value); w.text(6, input.base_text); }
                else if constexpr (std::is_same_v<I, gui::ChooseOption>) { w.u32(4, 4); w.text(5, input.id); }
                else if constexpr (std::is_same_v<I, gui::SelectRecord>) { w.u32(4, 5); w.text(5, input.id); }
                else if constexpr (std::is_same_v<I, gui::ActivateRecord>) { w.u32(4, 6); w.text(5, input.id); }
                else if constexpr (std::is_same_v<I, gui::SubmitText>) w.u32(4, 7);
                else if constexpr (std::is_same_v<I, gui::InvokeAction>) { w.u32(4, 8); w.text(5, input.id); }
                else {
                    w.u32(4, 9); Writer p;
                    p.u32(1, wire_value(pointer_kinds, input.kind)); p.number(2, input.position.x); p.number(3, input.position.y);
                    p.number(4, input.wheel_x); p.number(5, input.wheel_y);
                    p.u32(6, (input.control ? 1u : 0u) | (input.shift ? 2u : 0u) | (input.alt ? 4u : 0u));
                    p.u64(7, input.pointer_id); p.u32(8, input.clicks); w.record(9, p.finish());
                }
            }, value.input);
        } else if constexpr (std::is_same_v<T, gui::PageEvent>) { w.u32(2, 2); w.text(10, value.id); }
        else if constexpr (std::is_same_v<T, gui::ResizeEvent>) {
            w.u32(2, 3); w.number(11, value.client_size.width); w.number(12, value.client_size.height); w.number(13, value.display_scale);
        } else throw std::logic_error("Unsupported unnormalized binary view event");
    }, event);
    return w.finish();
}

} // namespace binary_view_detail

// Defined only on the GUI side of the boundary; neutral binding headers may
// forward-declare this wrapper and retain an immutable owning shared_ptr.
struct EngineModuleServiceRequest { gui::ServiceRequest request; };

// One owned implementation of the foundation.view/v1 value contract. Registry
// callbacks decode/copy values only; no adapter, guest, controller or loop lives
// here. A presentation owner must acknowledge only its actual published revision.
class EngineModuleView {
public:
    using Span = std::span<const std::uint8_t>;
    struct EventFacts {
        std::optional<gui::WidgetKey> focused;
        std::vector<std::pair<gui::WidgetKey, gui::Point>> scroll_offsets;
    };

    const gui::Snapshot& snapshot() const noexcept { return view_; }
    bool pending() const noexcept { return pending_; }
    bool closed() const noexcept { return closed_; }
    std::uint64_t input_epoch() const noexcept { return input_epoch_; }
    ServiceReply publish(Span request, std::span<std::uint8_t> reply) { return call(1, request, reply); }
    ServiceReply call(std::uint32_t operation, Span request, std::span<std::uint8_t> reply) {
        if (closed_) return {appended::ServiceStatus::closed, 0};
        using namespace binary_view_detail;
        try {
            if (operation == 1) {
                RecordReader header(request, 12);
                if (header.u64(1, 0, true) != view_.revision) return {appended::ServiceStatus::conflict, 0};
                if (view_.revision == std::numeric_limits<std::uint64_t>::max() ||
                    input_epoch_ == std::numeric_limits<std::uint64_t>::max())
                    return {appended::ServiceStatus::limit_exceeded, 0};
                auto decoded = decode_view(request, view_);
                auto next_identities = identities_;
                for (const auto& w : decoded.view.widgets) {
                    if (const auto* previous = gui::find_widget(view_, w.spec.key)) require(previous->spec == w.spec);
                    else if (const auto old = identities_.find(w.spec.key.id); old != identities_.end()) require(w.spec.key.generation > old->second);
                    next_identities[w.spec.key.id] = w.spec.key.generation;
                }
                for (const auto& command : decoded.view.commands) {
                    if (const auto* previous = gui::find_command(view_, command.key)) require(previous->scope == command.scope);
                    else if (const auto old = identities_.find(command.key.id); old != identities_.end()) require(command.key.generation > old->second);
                    next_identities[command.key.id] = command.key.generation;
                }
                require(next_identities.size() <= max_identities);
                auto next_resources = resource_revisions_;
                for (const auto& [id, resource] : decoded.resources) {
                    if (const auto previous = resources_.find(id); previous != resources_.end() && previous->second.revision == resource.revision)
                        require(previous->second == resource);
                    else if (const auto previous = resource_revisions_.find(id); previous != resource_revisions_.end())
                        require(resource.revision > previous->second);
                    next_resources[id] = resource.revision;
                }
                require(next_resources.size() <= 1024);
                Writer result; result.u64(1, decoded.view.revision); const auto encoded = result.finish();
                require(reply.size() >= encoded.size());
                // All validation and potentially allocating reply work precedes
                // the commit. Adapter callbacks never run from this handler.
                advance_epoch(); identities_.swap(next_identities); resource_revisions_.swap(next_resources);
                resources_.swap(decoded.resources); view_ = std::move(decoded.view); pending_ = true;
                std::copy(encoded.begin(), encoded.end(), reply.begin());
                return {appended::ServiceStatus::ok, static_cast<std::uint32_t>(encoded.size())};
            }
            if (operation == 2) {
                if (host_services_ >= max_host_services) return {appended::ServiceStatus::limit_exceeded, 0};
                RecordReader r(request, 5); gui::ServiceRequest service;
                service.id = r.u64(1, 0, true); const auto kind = r.u32(2, 0, true);
                require(service.id != 0 && kind >= 1 && kind <= 7);
                service.kind = host_service_kinds[kind - 1]; service.title = r.text(3); service.value = r.text(4);
                service.byte_limit = r.u32(5, 32768); require(service.byte_limit <= 65536);
                if (!services_.enqueue(std::move(service))) return {appended::ServiceStatus::conflict, 0};
                ++host_services_; return {appended::ServiceStatus::ok, 0};
            }
            return {appended::ServiceStatus::unknown_operation, 0};
        } catch (const InvalidView&) { return {appended::ServiceStatus::invalid_request, 0}; }
        catch (const std::invalid_argument&) { return {appended::ServiceStatus::invalid_request, 0}; }
        catch (const std::length_error&) { return {appended::ServiceStatus::limit_exceeded, 0}; }
    }

    bool acknowledge_published(std::uint64_t revision) noexcept {
        if (closed_ || !pending_ || revision != view_.revision) return false;
        pending_ = false;
        return true;
    }
    void advance_epoch() {
        if (input_epoch_ == std::numeric_limits<std::uint64_t>::max())
            throw std::overflow_error("Binary input epoch exhausted");
        ++input_epoch_;
    }
    void shutdown() noexcept {
        if (closed_) return;
        closed_ = true; pending_ = false; services_.shutdown();
        if (input_epoch_ != std::numeric_limits<std::uint64_t>::max()) ++input_epoch_;
    }
    std::optional<gui::ServiceRequest> next_service() { return services_.begin_next(); }
    std::optional<gui::ServiceRequest> current_service() { return services_.current(); }
    bool complete_service(gui::ServiceResult& result) { return services_.complete(result); }

    bool normalize_event(gui::Event& event, const EventFacts& facts) const {
        if (facts.scroll_offsets.size() > binary_view_detail::max_widgets) return false;
        if (facts.focused && (facts.focused->id.empty() || !facts.focused->generation)) return false;
        for (std::size_t i = 0; i < facts.scroll_offsets.size(); ++i) {
            const auto& [key, point] = facts.scroll_offsets[i];
            if (!gui::find_widget(view_, key) || !std::isfinite(point.x) || !std::isfinite(point.y)) return false;
            for (std::size_t j = 0; j < i; ++j) if (facts.scroll_offsets[j].first == key) return false;
        }
        bool missing_scroll = false;
        const auto accepted = normalize_event(event, [&](const gui::WidgetKey& key) {
            for (const auto& [target, point] : facts.scroll_offsets) if (target == key) return point;
            missing_scroll = true;
            return gui::Point{};
        }, [&] { return facts.focused; });
        return accepted && !missing_scroll;
    }
    // Compatibility path for the original binary-only App. These lazy queries
    // run only from its outer handle(), after all Registry callbacks have ended.
    // Compositions use the owning EventFacts overload above.
    bool normalize_event(gui::Event& event, const gui::ScrollLookup& scroll,
                         const std::function<std::optional<gui::WidgetKey>()>& focused) const {
        if (closed_ || pending_) return false;
        if (!gui::normalize_event(view_, event, scroll)) return false;
        if (const auto* widget_event = std::get_if<gui::WidgetEvent>(&event)) {
            if (gui::find_command(view_, widget_event->target)) {
                const auto* activate = std::get_if<gui::Activate>(&widget_event->input);
                if (!activate || !activate->source || !focused || focused() != activate->source) return false;
            }
        }
        return true;
    }
    static Bytes encode_event(const gui::Event& event, std::uint64_t revision) {
        return binary_view_detail::encode_event(event, revision);
    }
    // Preserve the original binary App's allocation boundary: prepare every
    // field, advance its epoch, then finish/dispatch. Other owners may use the
    // ordinary encoder below when their own publication/dispatch policy permits.
    static binary_view_detail::Writer prepare_service_result(const gui::ServiceResult& result) {
        binary_view_detail::Writer w;
        w.u64(1, result.id); w.u32(2, binary_view_detail::wire_value(binary_view_detail::host_service_statuses, result.status));
        w.text(3, result.value); w.text(4, result.error);
        return w;
    }
    static Bytes encode_service_result(const gui::ServiceResult& result) {
        return prepare_service_result(result).finish();
    }
    static gui::ServiceResult decode_service_result(Span bytes) {
        using namespace binary_view_detail;
        try {
            RecordReader r(bytes, 4); gui::ServiceResult result;
            result.id = r.u64(1, 0, true); const auto status = r.u32(2, 0, true);
            require(result.id != 0 && status >= 1 && status <= host_service_statuses.size());
            result.status = host_service_statuses[status - 1];
            result.value = r.text(3); result.error = r.text(4);
            return result;
        } catch (const InvalidView&) {
            throw std::invalid_argument("Invalid binary host service result");
        }
    }
    static const SchemaId& schema() noexcept {
        // SHA-256 of the exact abi/appended/view/v1.json bytes, including final LF.
        static const appended::SchemaId identity{
            0x73, 0x45, 0xdd, 0xa5, 0x70, 0xc5, 0xc3, 0x38, 0xf4, 0x17, 0x85, 0xc8, 0x8e, 0xbe, 0xa3, 0xf7,
            0xba, 0x78, 0xef, 0xf7, 0xda, 0x07, 0x78, 0x6a, 0x0c, 0xed, 0x43, 0xfe, 0x4d, 0xc4, 0x11, 0xb7};
        return identity;
    }

private:
    gui::Snapshot view_;
    gui::ServiceQueue services_;
    binary_view_detail::Resources resources_;
    std::map<std::string, std::uint64_t, std::less<>> identities_, resource_revisions_;
    std::uint64_t input_epoch_ = 1;
    std::size_t host_services_ = 0;
    bool pending_ = false, closed_ = false;
};
} // namespace foundation::appended
