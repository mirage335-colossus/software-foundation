// Focused generic binary view-model regression.
// No Module/Registry instance, adapter, engine, SDK, browser or guest is loaded.
#include "shared/appended_binary_view_model.hpp"
#include <array>
#include <functional>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace foundation::appended;
namespace {
void check(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
void append(Bytes& output, const Bytes& input) { output.insert(output.end(), input.begin(), input.end()); }
struct Field {
    std::uint16_t id;
    FieldType type;
    Bytes value;
    bool required = true;
};
Field integer(std::uint16_t id, std::uint64_t value) { return {id, FieldType::u64, encode_u64(value)}; }
Field enumeration(std::uint16_t id, std::uint32_t value) { return {id, FieldType::u32, encode_u32(value)}; }
Field text(std::uint16_t id, std::string_view value) { return {id, FieldType::utf8, Bytes(value.begin(), value.end())}; }
Field number(std::uint16_t id, double value) { return {id, FieldType::f64, encode_u64(std::bit_cast<std::uint64_t>(value))}; }
Field boolean(std::uint16_t id, bool value) { return {id, FieldType::boolean, {static_cast<std::uint8_t>(value)}}; }
Field nested(std::uint16_t id, Bytes value) { return {id, FieldType::record, std::move(value)}; }
Field list(std::uint16_t id, const std::vector<Bytes>& values) {
    auto result = encode_u32(static_cast<std::uint32_t>(values.size()));
    for (const auto& value : values) {
        append(result, encode_u32(static_cast<std::uint32_t>(value.size()))); append(result, value);
    }
    return {id, FieldType::record_list, std::move(result)};
}
Bytes record(std::vector<Field> fields, bool event = false) {
    std::sort(fields.begin(), fields.end(), [](const auto& a, const auto& b) { return a.id < b.id; });
    std::vector<FieldView> views;
    for (const auto& field : fields) views.push_back({field.id, field.type, !event && field.required, field.value});
    Bytes result;
    check(encode_record(views, result) == CodecStatus::ok, "cannot encode view fixture record");
    return result;
}
Bytes key(std::string_view id, std::uint64_t generation, bool event = false) {
    return record({text(1, id), integer(2, generation)}, event);
}
Bytes rectangle(double x, double y, double width, double height) {
    return record({number(1, x), number(2, y), number(3, width), number(4, height)});
}

struct ViewState {
    std::string title = "initial", editor = "alpha";
    std::uint64_t button_generation = 1, bitmap_revision = 1;
    bool button = true, image = true, duplicate = false, read_only = false, command_scope = false;
    std::uint64_t editor_generation = 1, command_generation = 1, image_generation = 1;
    bool huge_bitmap = false, unknown_required = false, unknown_optional = false;
    Bytes pixels{1, 2, 3, 4, 5, 6};
};
Bytes replacement(std::uint64_t revision, const ViewState& state) {
    std::vector<Bytes> widgets;
    widgets.push_back(record({text(1, "editor"), integer(2, state.editor_generation), enumeration(3, 6),
        nested(4, rectangle(10, 10, 100, 24)), text(7, state.editor), boolean(17, state.read_only)}));
    if (state.button) widgets.push_back(record({text(1, "apply"), integer(2, state.button_generation), enumeration(3, 3),
        nested(4, rectangle(10, 40, 100, 24)), text(8, "Apply")}));
    const auto bitmap = record({text(1, "pixels"), integer(2, state.bitmap_revision), enumeration(3, 2),
        enumeration(4, 1), enumeration(5, 3), {6, FieldType::bytes, state.pixels}});
    const auto extent = state.huge_bitmap ? 20000.0 : 2.0;
    if (state.image) widgets.push_back(record({text(1, "image"), integer(2, state.image_generation), enumeration(3, 8),
        nested(4, rectangle(10, 80, extent, state.huge_bitmap ? extent : 1.0)), nested(32, bitmap)}));
    if (state.duplicate) widgets.push_back(widgets.front());
    std::vector<Field> command{text(1, "invoke"), integer(2, state.command_generation)};
    if (state.command_scope) command.push_back(nested(4, key("editor", state.editor_generation)));
    std::vector<Field> fields{integer(1, revision), text(2, state.title), list(6, widgets),
        list(7, {record(std::move(command))})};
    if (state.unknown_required || state.unknown_optional) {
        auto unknown = enumeration(13, 123); unknown.required = state.unknown_required; fields.push_back(std::move(unknown));
    }
    return record(std::move(fields));
}
Bytes service_request() {
    return record({integer(1, 99), enumeration(2, 3), text(3, "A generic prompt"), text(4, "seed"), enumeration(5, 8)});
}

using Reply = std::array<std::uint8_t, 256>;
ServiceReply publish(EngineModuleView& model, std::uint64_t base, const ViewState& state, Reply& reply) {
    return model.publish(replacement(base, state), reply);
}
void accept(EngineModuleView& model, std::uint64_t base, const ViewState& state = {}) {
    Reply reply{};
    const auto result = publish(model, base, state, reply);
    check(result.status == ServiceStatus::ok && model.snapshot().revision == base + 1, "valid view rejected");
    const auto expected = record({integer(1, base + 1)}, true);
    check(result.bytes == expected.size() && std::equal(expected.begin(), expected.end(), reply.begin()),
          "accepted revision reply bytes changed");
}
void atomic_precommit() {
    EngineModuleView model; Reply reply{}; ViewState state;
    auto request = replacement(0, state);
    const auto small = model.publish(request, std::span<std::uint8_t>{reply}.first(15));
    check(small.status == ServiceStatus::invalid_request && model.snapshot().revision == 0 &&
          model.input_epoch() == 1 && !model.pending(), "small reply mutated authoritative state");
    const auto accepted = model.publish(request, reply);
    check(accepted.status == ServiceStatus::ok && model.pending() && model.input_epoch() == 2, "commit not pending/epoch-bound");
    std::fill(request.begin(), request.end(), 0);
    check(model.snapshot().title == "initial" && gui::find_widget(model.snapshot(), {"editor", 1})->state.text == "alpha",
          "retained snapshot borrows request storage");
}
void revision_and_rejection() {
    EngineModuleView model; accept(model, 0); Reply reply{};
    auto stale = publish(model, 0, {}, reply);
    check(stale.status == ServiceStatus::conflict && model.snapshot().revision == 1 && model.input_epoch() == 2,
          "stale base revision changed state");
    ViewState invalid; invalid.duplicate = true;
    check(publish(model, 1, invalid, reply).status == ServiceStatus::invalid_request && model.snapshot().revision == 1,
          "duplicate widget partially committed");
    invalid = {}; invalid.unknown_required = true;
    check(publish(model, 1, invalid, reply).status == ServiceStatus::invalid_request, "unknown required field accepted");
    invalid = {}; invalid.unknown_optional = true; accept(model, 1, invalid);
}
void identity_tombstones() {
    EngineModuleView model; accept(model, 0); Reply reply{};
    ViewState changed; changed.read_only = true;
    check(publish(model, 1, changed, reply).status == ServiceStatus::invalid_request, "retained spec changed in generation");
    ViewState removed; removed.button = false; accept(model, 1, removed);
    check(publish(model, 2, {}, reply).status == ServiceStatus::invalid_request, "removed widget identity resurrected");
    ViewState renewed; renewed.button_generation = 2; accept(model, 2, renewed);
}
void resource_tombstones() {
    EngineModuleView model; accept(model, 0); Reply reply{};
    ViewState changed; changed.pixels[0] ^= 1;
    check(publish(model, 1, changed, reply).status == ServiceStatus::invalid_request, "same resource revision changed bytes");
    ViewState removed; removed.image = false; accept(model, 1, removed);
    ViewState reintroduced; reintroduced.image_generation = 2;
    check(publish(model, 2, reintroduced, reply).status == ServiceStatus::invalid_request, "removed resource revision resurrected");
    ViewState renewed = reintroduced; renewed.bitmap_revision = 2; accept(model, 2, renewed);
}
void publication_ack_and_owned_snapshot() {
    EngineModuleView model; accept(model, 0);
    const gui::Snapshot owned = model.snapshot();
    gui::Event click = gui::WidgetEvent{{"apply", 1}, gui::Activate{}};
    check(!model.normalize_event(click, EngineModuleView::EventFacts{}), "input accepted before actual publication");
    check(!model.acknowledge_published(0) && model.pending(), "wrong publication revision cleared pending");
    ViewState next; next.title = "next"; accept(model, 1, next);
    check(!model.acknowledge_published(1) && model.pending(), "stale publication cleared a newer candidate");
    check(owned.revision == 1 && owned.title == "initial" && model.snapshot().title == "next", "owned publication snapshot was mutated");
    check(model.acknowledge_published(2) && !model.pending(), "actual current publication did not acknowledge");
    check(!model.acknowledge_published(2), "duplicate publication became a new acknowledgement");
}
void focus_and_retired_generation() {
    EngineModuleView model; ViewState state; state.command_scope = true; accept(model, 0, state);
    check(model.acknowledge_published(1), "fixture publication failed");
    EngineModuleView::EventFacts facts; facts.focused = gui::WidgetKey{"editor", 1};
    gui::Event event = gui::WidgetEvent{{"invoke", 1}, gui::Activate{gui::WidgetKey{"editor", 1}}};
    check(model.normalize_event(event, facts), "current focused command rejected");
    facts.focused = gui::WidgetKey{"apply", 1};
    event = gui::WidgetEvent{{"invoke", 1}, gui::Activate{gui::WidgetKey{"editor", 1}}};
    check(!model.normalize_event(event, facts), "focus switch retained an old command source");
    state.editor_generation = 2; state.command_generation = 2; accept(model, 1, state);
    check(model.acknowledge_published(2), "fixture successor publication failed");
    facts.focused = gui::WidgetKey{"editor", 1};
    event = gui::WidgetEvent{{"invoke", 1}, gui::Activate{gui::WidgetKey{"editor", 1}}};
    check(!model.normalize_event(event, facts), "retired held-event target generation survived replacement");
}
void exact_event_codec() {
    constexpr std::uint64_t local_revision = 7, composed_revision = 9001;
    check(local_revision != composed_revision, "fixture revisions accidentally alias");
    const gui::WidgetKey target{"editor", 3};
    const auto expected = record({integer(1, local_revision), enumeration(2, 1), nested(3, key("editor", 3, true)),
                                  enumeration(4, 3), text(5, "new"), text(6, "old")}, true);
    check(EngineModuleView::encode_event(gui::WidgetEvent{target, gui::EditText{"new", "old"}}, local_revision) == expected,
          "edit codec or module-local revision changed");
    check(EngineModuleView::encode_event(gui::PageEvent{"beta"}, local_revision) ==
          record({integer(1, local_revision), enumeration(2, 2), text(10, "beta")}, true), "page event codec changed");
    check(EngineModuleView::encode_event(gui::ResizeEvent{{640, 480}, 1.25}, local_revision) ==
          record({integer(1, local_revision), enumeration(2, 3), number(11, 640), number(12, 480), number(13, 1.25)}, true),
          "resize event codec changed");
    bool rejected = false;
    try { (void)EngineModuleView::encode_event(gui::CloseEvent{}, local_revision); }
    catch (const std::logic_error&) { rejected = true; }
    check(rejected, "unnormalized close event was encoded");
}
void pointer_codec_keeps_local_coordinates() {
    gui::PointerInput pointer; pointer.kind = gui::PointerKind::press; pointer.position = {13, 17};
    pointer.wheel_x = -1; pointer.wheel_y = 2; pointer.control = true; pointer.alt = true; pointer.pointer_id = 41; pointer.clicks = 2;
    const auto wire = record({enumeration(1, 5), number(2, 13), number(3, 17), number(4, -1), number(5, 2),
                              enumeration(6, 5), integer(7, 41), enumeration(8, 2)}, true);
    const auto expected = record({integer(1, 23), enumeration(2, 1), nested(3, key("canvas", 4, true)),
                                  enumeration(4, 9), nested(9, wire)}, true);
    check(EngineModuleView::encode_event(gui::WidgetEvent{{"canvas", 4}, pointer}, 23) == expected,
          "pointer local origin/modifier/gesture fields changed");
    // The composed App maps its pane/caret origin before staging this local event.
    // This codec deliberately cannot substitute the composed presentation revision.
}
void owned_facts_and_legacy_lazy_queries() {
    EngineModuleView model; accept(model, 0); check(model.acknowledge_published(1), "fixture publication failed");
    EngineModuleView::EventFacts facts;
    facts.scroll_offsets.push_back({{"editor", 1}, {0, 0}});
    facts.scroll_offsets.push_back({{"editor", 1}, {0, 0}});
    gui::Event event = gui::WidgetEvent{{"apply", 1}, gui::Activate{}};
    check(!model.normalize_event(event, facts), "duplicate owned scroll fact accepted");
    int focus_queries = 0;
    event = gui::WidgetEvent{{"apply", 1}, gui::Activate{}};
    check(model.normalize_event(event, [](const auto&) { return gui::Point{}; }, [&] { ++focus_queries; return std::optional<gui::WidgetKey>{}; }),
          "legacy ordinary activation rejected");
    check(focus_queries == 0, "legacy path eagerly queried adapter focus");
}
void host_service_queue_and_codec() {
    EngineModuleView model; Reply reply{};
    check(model.call(2, service_request(), reply).status == ServiceStatus::ok, "host request was not queued");
    check(model.call(2, service_request(), reply).status == ServiceStatus::conflict, "duplicate host request was admitted");
    const auto pending = model.next_service();
    check(pending && pending->id == 99 && pending->kind == gui::ServiceKind::prompt && pending->byte_limit == 8,
          "host request values changed");
    gui::ServiceResult result; result.id = 99; result.status = gui::ServiceStatus::success; result.value = "hello";
    const auto expected = record({integer(1, 99), enumeration(2, 1), text(3, "hello"), text(4, "")}, true);
    check(EngineModuleView::encode_service_result(result) == expected, "host result codec changed");
    const auto decoded = EngineModuleView::decode_service_result(expected);
    check(decoded.id == result.id && decoded.status == result.status && decoded.value == result.value && decoded.error.empty(),
          "host result inverse codec lost values");
    auto wrong = result; wrong.id = 100;
    check(!model.complete_service(wrong) && model.current_service()->id == 99, "foreign host completion consumed current request");
    check(model.complete_service(result) && !model.current_service(), "matching host completion was not consumed");
    bool rejected = false;
    try { (void)EngineModuleView::decode_service_result(record({integer(1, 99), enumeration(2, 4)}, true)); }
    catch (const std::invalid_argument&) { rejected = true; }
    check(rejected, "unknown host result status accepted");
}
void host_service_lifetime_limit() {
    EngineModuleView model; Reply reply{};
    for (std::uint64_t id = 1; id <= 64; ++id) {
        const auto request = record({integer(1, id), enumeration(2, 3)});
        check(model.call(2, request, reply).status == ServiceStatus::ok, "host lifetime budget rejected too early");
        check(model.next_service()->id == id, "host queue order changed");
        gui::ServiceResult result; result.id = id; result.status = gui::ServiceStatus::cancelled;
        check(model.complete_service(result), "host completion failed");
    }
    check(model.call(2, record({integer(1, 65), enumeration(2, 3)}), reply).status == ServiceStatus::limit_exceeded,
          "host lifetime limit reset after completion");
}
void shutdown_and_schema() {
    EngineModuleView model; accept(model, 0); model.shutdown(); const auto epoch = model.input_epoch(); model.shutdown();
    Reply reply{};
    check(model.closed() && !model.pending() && epoch == 3 && model.input_epoch() == epoch && !model.next_service(),
          "model shutdown is not idempotent");
    check(model.publish(replacement(1, {}), reply).status == ServiceStatus::closed, "closed model accepted a publication");
    const SchemaId expected{0x73,0x45,0xdd,0xa5,0x70,0xc5,0xc3,0x38,0xf4,0x17,0x85,0xc8,0x8e,0xbe,0xa3,0xf7,
        0xba,0x78,0xef,0xf7,0xda,0x07,0x78,0x6a,0x0c,0xed,0x43,0xfe,0x4d,0xc4,0x11,0xb7};
    check(EngineModuleView::schema() == expected, "foundation.view schema identity changed");
}
} // namespace
int main() {
    const std::array<std::pair<const char*, void(*)()>, 12> cases{{
        {"atomic_precommit", atomic_precommit}, {"revision_and_rejection", revision_and_rejection},
        {"identity_tombstones", identity_tombstones}, {"resource_tombstones", resource_tombstones},
        {"publication_ack_and_owned_snapshot", publication_ack_and_owned_snapshot},
        {"focus_and_retired_generation", focus_and_retired_generation}, {"exact_event_codec", exact_event_codec},
        {"pointer_codec_keeps_local_coordinates", pointer_codec_keeps_local_coordinates},
        {"owned_facts_and_legacy_lazy_queries", owned_facts_and_legacy_lazy_queries},
        {"host_service_queue_and_codec", host_service_queue_and_codec}, {"host_service_lifetime_limit", host_service_lifetime_limit},
        {"shutdown_and_schema", shutdown_and_schema}
    }};
    try { for (const auto& [name, run] : cases) { run(); std::cout << name << "\n"; } }
    catch (const std::exception& error) { std::cerr << error.what() << "\n"; return 1; }
}
