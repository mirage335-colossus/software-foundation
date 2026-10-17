// SPDX-License-Identifier: CC0-1.0
// Pure bounded binary-value tests. No native editor, browser or engine runs.
#include "native_editor_codec.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <cstdint>
#include <cstdlib>
#include <functional>
#include <iostream>
#include <limits>
#include <map>
#include <new>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

// Only ordinary string/vector allocations are observed. Arm after fixture and
// sentinel construction, so failure injection belongs to the codec operation.
namespace allocation_test {
thread_local bool armed = false;
thread_local std::size_t calls = 0;
thread_local std::size_t fail_after = std::numeric_limits<std::size_t>::max();
}
void* operator new(std::size_t size) {
    if (allocation_test::armed && allocation_test::calls++ == allocation_test::fail_after) throw std::bad_alloc();
    if (auto* memory = std::malloc(size ? size : 1)) return memory;
    throw std::bad_alloc();
}
void* operator new[](std::size_t size) { return ::operator new(size); }
void operator delete(void* memory) noexcept { std::free(memory); }
void operator delete[](void* memory) noexcept { std::free(memory); }
void operator delete(void* memory, std::size_t) noexcept { std::free(memory); }
void operator delete[](void* memory, std::size_t) noexcept { std::free(memory); }

namespace {
using namespace foundation::ui::native_editor;
namespace C = foundation::ui::native_editor::codec;
using foundation::gui_surface::CompositionOperation;
using foundation::gui_surface::KeyPhase;
using C::Bytes;
constexpr auto wide = std::numeric_limits<std::uint64_t>::max();
std::size_t checks = 0;

void check(bool condition, const char* detail) {
    ++checks;
    if (!condition) throw std::runtime_error(detail);
}
bool equal(const NativeRequest& a, const NativeRequest& b) {
    return a.resolved == b.resolved && a.packet == b.packet;
}
bool equal(const NativeResult& a, const NativeResult& b) {
    return a.outcome == b.outcome && a.continuity == b.continuity && a.projection == b.projection &&
        a.key_dispatch_attested == b.key_dispatch_attested && a.default_prevented == b.default_prevented &&
        a.default_handled == b.default_handled && a.changed_focused_frame == b.changed_focused_frame &&
        a.allow_default == b.allow_default && a.key_retarget_attested == b.key_retarget_attested &&
        a.composition_readback_attested == b.composition_readback_attested && a.composition == b.composition &&
        a.availability == b.availability && a.observation_revision == b.observation_revision &&
        a.readback_identity == b.readback_identity && a.readback_attested == b.readback_attested &&
        a.retire == b.retire && a.retired == b.retired;
}
bool equal(const C::NativeRequestEnvelope& a, const C::NativeRequestEnvelope& b) {
    return a.target == b.target && equal(a.request, b.request);
}
bool equal(const C::NativeResultEnvelope& a, const C::NativeResultEnvelope& b) {
    return a.target == b.target && equal(a.result, b.result);
}
bool equal(const C::RevocationEnvelope& a, const C::RevocationEnvelope& b) {
    return a.target == b.target && a.request.material == b.request.material &&
        a.request.identity == b.request.identity && a.request.observed == b.request.observed;
}
template<class T> bool equal(const T& a, const T& b) { return a == b; }

Identity identity() { return {{"native-owner", wide}, wide - 1, wide - 2, wide - 3, wide - 4}; }
C::WireTarget target() { return {wide - 20, wide - 21, wide - 22, wide - 23, wide - 24}; }
bool encode_request(const NativeRequest& value, Bytes& bytes) {
    return C::encode_native_request({target(), value}, bytes);
}
bool decode_request(std::span<const std::uint8_t> bytes, NativeRequest& value) {
    C::NativeRequestEnvelope decoded{target(), value};
    if (!C::decode_native_request(bytes, decoded)) return false;
    value = std::move(decoded.request); return true;
}
bool encode_result(const NativeResult& value, Bytes& bytes) {
    return C::encode_native_result({target(), value}, bytes);
}
bool decode_result(std::span<const std::uint8_t> bytes, NativeResult& value) {
    C::NativeResultEnvelope decoded{target(), value};
    if (!C::decode_native_result(bytes, decoded)) return false;
    value = std::move(decoded.result); return true;
}
NativeProjection projection() {
    NativeProjection result;
    result.identity = identity(); result.editor_revision = wide - 5;
    result.surrounding = "ab\xf0\x9f\x99\x82" "c"; result.selection = {2, 6}; result.backward = true;
    result.mapping_id = wide - 6; result.frame_id = wide - 7; result.readback_attested = true;
    result.caret = {-17.5, 9.25, 1.5, 20.125}; result.input_purpose = "text";
    result.retire = NativeRetireMaterial{wide - 25, result.mapping_id, result.identity.context, result.composition};
    return result;
}
Basis basis(const NativeProjection& value) {
    return {wide - 8, value.identity, value.editor_revision, value.surrounding,
            value.selection, value.backward, value.composition};
}
TextObservation before() {
    return {"ab\xf0\x9f\x99\x82" "c", 2, 4, Direction::backward, {2, 6}, 7};
}
Observation key_observation() {
    Observation result;
    result.id = wide - 10; result.predecessor = wide - 11;
    result.kind = Kind::key; result.authority = Authority::native; result.group = wide - 12;
    result.group_end = true; result.before = before(); result.after = result.before;
    KeyData key; key.transition = {KeyPhase::down, "\xc3\xa9", "KeyE", 2, 31, true};
    key.is_composing = true; result.data = std::move(key); return result;
}
Observation text_observation() {
    auto result = key_observation(); result.kind = Kind::text; result.authority = Authority::range;
    result.group.reset(); result.group_end = false;
    result.after = TextObservation{"ab\xc3\xa9" "c", 3, 3, Direction::none, {4, 4}, 5};
    result.data = TextData{"insertText", "\xc3\xa9", {2, 6}, {}}; return result;
}
Observation selection_observation() {
    auto result = key_observation(); result.kind = Kind::selection; result.authority = Authority::range;
    result.group.reset(); result.group_end = false;
    result.after = TextObservation{result.before.value, 0, 2, Direction::forward, {0, 2}, 7};
    result.data = SelectionData{{0, 2}, false}; return result;
}
Observation composition_observation(CompositionOperation operation) {
    auto result = key_observation(); result.kind = Kind::composition;
    result.authority = operation == CompositionOperation::begin ? Authority::range : Authority::composition;
    result.group.reset(); result.group_end = false; result.transaction = wide - 13; result.after.reset();
    CompositionData data; data.operation = operation; data.text = "\xf0\x9f\x99\x82\xc3\xa9";
    data.selection = {4, 6};
    if (operation == CompositionOperation::begin) data.replacement = result.before.selection;
    result.data = std::move(data); return result;
}
NativeRequest request(Observation observation = key_observation()) {
    NativeRequest result; result.resolved = projection(); result.packet.session = wide - 9;
    if (observation.kind == Kind::composition &&
        std::get<CompositionData>(observation.data).operation != CompositionOperation::begin)
        result.resolved.composition = observation.transaction;
    result.resolved.retire->composition = result.resolved.composition;
    result.packet.basis = basis(result.resolved); result.packet.observation = std::move(observation);
    return result;
}
NativeResult native_result() {
    NativeResult result; result.outcome = Outcome::applied; result.projection = projection();
    result.observation_revision = wide - 14; result.readback_identity = identity(); result.readback_attested = true;
    result.retire = result.projection->retire; return result;
}
C::ProjectionReply reply() {
    return {C::ProjectionReply::State::available, wide - 14, target(), projection(), identity(), true};
}
C::RevocationEnvelope revocation(bool observed = true) {
    C::RevocationEnvelope result;
    result.target = target(); result.request.identity = identity(); result.request.material = *projection().retire;
    if (observed) {
        Revocation observation; observation.basis = basis(projection()); observation.incarnation = wide - 30;
        observation.held_keys = {std::get<KeyData>(key_observation().data)}; observation.reason = "native retirement";
        result.request.observed = std::move(observation);
    }
    return result;
}

// Independent schema fixtures also record locations for adversarial field edits.
// Their expected ordering and widths do not use the production encoder/parser.
struct Wire {
    Bytes bytes{'B', 'I', 'B', 'E', 'D', 'V', '1', 0};
    std::map<std::string, std::size_t> fields;
    explicit Wire(unsigned kind) { put(kind, 2); put(0, 2); put(0, 4); }
    void mark(const std::string& name) { check(fields.emplace(name, bytes.size()).second, "Duplicate fixture field"); }
    void put(std::uint64_t value, std::size_t count) {
        for (std::size_t i = 0; i < count; ++i) bytes.push_back(static_cast<std::uint8_t>(value >> (8 * i)));
    }
    void scalar(const std::string& name, std::uint64_t value, std::size_t count) { mark(name); put(value, count); }
    void string(const std::string& name, std::string_view value) {
        scalar(name, value.size(), 4); bytes.insert(bytes.end(), value.begin(), value.end());
    }
    void boolean(const std::string& name, bool value) { scalar(name, value, 1); }
    void range(const std::string& name, ByteRange value) {
        scalar(name + ".begin", value.begin, 4); scalar(name + ".end", value.end, 4);
    }
    void identity(const std::string& name, const Identity& value) {
        string(name + ".owner", value.owner.id); scalar(name + ".owner_generation", value.owner.generation, 8);
        scalar(name + ".presentation", value.presentation_revision, 8); scalar(name + ".generation", value.generation, 8);
        scalar(name + ".epoch", value.epoch, 8); scalar(name + ".context", value.context, 8);
    }
    void target(const C::WireTarget& value) {
        scalar("target.worker_epoch", value.worker_epoch, 8); scalar("target.application_instance", value.application_instance, 8);
        scalar("target.document_sequence", value.document_sequence, 8); scalar("target.service_generation", value.service_generation, 8);
        scalar("target.request_sequence", value.request_sequence, 8);
    }
    void material(const std::string& name, const NativeRetireMaterial& value) {
        scalar(name + ".token", value.token, 8); scalar(name + ".mapping", value.mapping_id, 8);
        scalar(name + ".context", value.input_context, 8); scalar(name + ".composition", value.composition, 8);
    }
    void basis(const std::string& name, const Basis& value) {
        scalar(name + ".token", value.token, 8); identity(name + ".identity", value.identity);
        scalar(name + ".revision", value.editor_revision, 8); string(name + ".text", value.surrounding);
        range(name + ".selection", value.selection); boolean(name + ".backward", value.backward);
        scalar(name + ".composition", value.composition, 8);
    }
    void projection(const std::string& name, const NativeProjection& value) {
        identity(name + ".identity", value.identity); scalar(name + ".revision", value.editor_revision, 8);
        string(name + ".text", value.surrounding); range(name + ".selection", value.selection);
        boolean(name + ".backward", value.backward); scalar(name + ".composition", value.composition, 8);
        scalar(name + ".mapping", value.mapping_id, 8); scalar(name + ".frame", value.frame_id, 8);
        boolean(name + ".readback", value.readback_attested);
        scalar(name + ".caret.x", std::bit_cast<std::uint64_t>(value.caret.x), 8);
        scalar(name + ".caret.y", std::bit_cast<std::uint64_t>(value.caret.y), 8);
        scalar(name + ".caret.width", std::bit_cast<std::uint64_t>(value.caret.width), 8);
        scalar(name + ".caret.height", std::bit_cast<std::uint64_t>(value.caret.height), 8);
        boolean(name + ".editable", value.editable); string(name + ".purpose", value.input_purpose);
        boolean(name + ".retire.present", bool(value.retire)); if (value.retire) material(name + ".retire", *value.retire);
    }
    void optional_u64(const std::string& name, std::optional<std::uint64_t> value) {
        boolean(name + ".present", bool(value)); if (value) scalar(name, *value, 8);
    }
    void text(const std::string& name, const TextObservation& value) {
        string(name + ".value", value.value); scalar(name + ".utf16_start", value.selection_start, 4);
        scalar(name + ".utf16_end", value.selection_end, 4);
        scalar(name + ".direction", static_cast<unsigned>(value.selection_direction), 4);
        range(name + ".selection", value.selection); scalar(name + ".byte_length", value.byte_length, 4);
    }
    void key(const std::string& name, const KeyData& value) {
        scalar(name + ".phase", static_cast<unsigned>(value.transition.phase), 4);
        string(name + ".logical", value.transition.key); string(name + ".code", value.transition.code);
        scalar(name + ".location", value.transition.location, 4); scalar(name + ".modifiers", value.transition.modifiers, 4);
        boolean(name + ".repeat", value.transition.repeat); boolean(name + ".composing", value.is_composing);
    }
    void groups(const std::string& name, const std::vector<std::uint64_t>& values) {
        scalar(name + ".count", values.size(), 4); for (auto value : values) put(value, 8);
    }
    void observation(const Observation& value) {
        const std::string name = "observation";
        scalar(name + ".id", value.id, 8); optional_u64(name + ".predecessor", value.predecessor);
        scalar(name + ".kind", static_cast<unsigned>(value.kind), 4);
        scalar(name + ".authority", static_cast<unsigned>(value.authority), 4);
        optional_u64(name + ".group", value.group); boolean(name + ".group_end", value.group_end);
        scalar(name + ".transaction", value.transaction, 8); text(name + ".before", value.before);
        boolean(name + ".after.present", bool(value.after)); if (value.after) text(name + ".after", *value.after);
        if (const auto* value_key = std::get_if<KeyData>(&value.data)) key("key", *value_key);
        else if (const auto* value_text = std::get_if<TextData>(&value.data)) {
            string("text.input_type", value_text->input_type); string("text.value", value_text->text);
            range("text.replacement", value_text->replacement); groups("text.groups", value_text->source_groups);
        } else if (const auto* value_selection = std::get_if<SelectionData>(&value.data)) {
            range("selection.range", value_selection->selection); boolean("selection.backward", value_selection->backward);
        } else {
            const auto& value_composition = std::get<CompositionData>(value.data);
            scalar("composition.operation", static_cast<unsigned>(value_composition.operation), 4);
            string("composition.text", value_composition.text); range("composition.selection", value_composition.selection);
            boolean("composition.replacement.present", bool(value_composition.replacement));
            if (value_composition.replacement) range("composition.replacement", *value_composition.replacement);
            groups("composition.groups", value_composition.source_groups);
        }
    }
    void packet(const Packet& value) {
        scalar("packet.session", value.session, 8); basis("basis", value.basis);
        optional_u64("packet.default", value.default_token); scalar("packet.dependencies.count", value.default_dependencies.size(), 4);
        for (const auto& dependency : value.default_dependencies) { put(dependency.group, 8); put(dependency.token, 8); }
        observation(value.observation);
    }
    void result(const NativeResult& value) {
        scalar("result.outcome", static_cast<unsigned>(value.outcome), 4);
        scalar("result.continuity", static_cast<unsigned>(value.continuity), 4);
        boolean("result.projection.present", bool(value.projection)); if (value.projection) projection("projection", *value.projection);
        boolean("result.key_dispatch", value.key_dispatch_attested); boolean("result.prevented", value.default_prevented);
        boolean("result.handled", value.default_handled); boolean("result.changed_frame", value.changed_focused_frame);
        boolean("result.allow_default", value.allow_default); boolean("result.key_retarget", value.key_retarget_attested);
        boolean("result.composition_readback", value.composition_readback_attested);
        boolean("result.composition.present", bool(value.composition));
        if (value.composition) {
            scalar("result.composition.transaction", value.composition->transaction, 8);
            scalar("result.composition.state", static_cast<unsigned>(value.composition->state), 4);
        }
        scalar("result.availability", static_cast<unsigned>(value.availability), 4);
        scalar("result.observation_revision", value.observation_revision, 8);
        identity("result.identity", value.readback_identity); boolean("result.readback", value.readback_attested);
        boolean("result.retire.present", bool(value.retire)); if (value.retire) material("result.retire", *value.retire);
        boolean("result.retired.present", bool(value.retired)); if (value.retired) material("result.retired", *value.retired);
    }
    void revocation(const NativeRevocationRequest& value) {
        material("retire", value.material); identity("retire.identity", value.identity);
        boolean("retire.observed.present", bool(value.observed));
        if (!value.observed) return;
        basis("retire.observed.basis", value.observed->basis);
        scalar("retire.observed.incarnation", value.observed->incarnation, 8);
        scalar("retire.observed.composition", value.observed->composition, 8);
        scalar("retire.observed.keys.count", value.observed->held_keys.size(), 4);
        for (std::size_t i = 0; i < value.observed->held_keys.size(); ++i)
            key("retire.observed.key." + std::to_string(i), value.observed->held_keys[i]);
        string("retire.observed.reason", value.observed->reason);
    }
    Bytes finish() {
        for (unsigned i = 0; i < 4; ++i) bytes[12 + i] = static_cast<std::uint8_t>(bytes.size() >> (8 * i));
        return bytes;
    }
};
Wire query_wire(const C::ProjectionQuery& value) {
    Wire wire(1); wire.target(value.target); wire.identity("identity", value.identity);
    wire.scalar("mapping", value.mapping_id, 8); wire.finish(); return wire;
}
Wire reply_wire(const C::ProjectionReply& value) {
    Wire wire(2); wire.scalar("reply.revision", value.observation_revision, 8);
    wire.target(value.target);
    wire.scalar("reply.state", static_cast<unsigned>(value.state), 4); wire.identity("reply.identity", value.identity);
    wire.boolean("reply.readback", value.readback_attested); wire.boolean("reply.projection.present", bool(value.projection));
    if (value.projection) wire.projection("projection", *value.projection);
    wire.finish(); return wire;
}
Wire request_wire(const NativeRequest& value) {
    Wire wire(3); wire.target(target()); wire.projection("resolved", value.resolved); wire.packet(value.packet); wire.finish(); return wire;
}
Wire result_wire(const NativeResult& value) {
    Wire wire(4); wire.target(target()); wire.result(value); wire.finish(); return wire;
}
Wire revocation_wire(const C::RevocationEnvelope& value) {
    Wire wire(5); wire.target(value.target); wire.revocation(value.request); wire.finish(); return wire;
}

void overwrite(Bytes& bytes, std::size_t position, std::uint64_t value, std::size_t count) {
    check(position <= bytes.size() && count <= bytes.size() - position, "Fixture mutation exceeds wire");
    for (std::size_t i = 0; i < count; ++i) bytes[position + i] = static_cast<std::uint8_t>(value >> (8 * i));
}
void mutate(Wire& wire, const std::string& name, std::uint64_t value, std::size_t count) {
    overwrite(wire.bytes, wire.fields.at(name), value, count);
}
template<class T, class Encode, class Decode>
void round_trip(const T& value, Encode encode, Decode decode) {
    Bytes wire{0xc1, 0xc2, 0xc3}; check(encode(value, wire), "Valid typed value did not encode");
    T decoded{}; check(decode(wire, decoded), "Encoded value did not decode");
    check(equal(value, decoded), "Round trip changed a typed field");
    Bytes repeated; check(encode(decoded, repeated) && repeated == wire, "Reencoding changed exact binary values");
}
template<class T, class Decode>
void rejects_wire(std::span<const std::uint8_t> wire, const T& sentinel, Decode decode) {
    auto output = sentinel;
    check(!decode(wire, output), "Malformed wire decoded successfully");
    check(equal(output, sentinel), "Rejected decode modified caller output");
}
template<class T, class Encode>
void rejects_value(const T& value, Encode encode) {
    Bytes output{0xc1, 0xc2, 0xc3}; const auto sentinel = output;
    check(!encode(value, output), "Malformed typed value encoded successfully");
    check(output == sentinel, "Rejected encode modified caller output");
}
template<class T, class Encode, class Decode>
void rejects_all_truncations(const T& value, Encode encode, Decode decode) {
    Bytes wire; check(encode(value, wire), "Truncation fixture did not encode");
    for (std::size_t size = 0; size < wire.size(); ++size)
        rejects_wire(std::span<const std::uint8_t>(wire).first(size), value, decode);
    auto trailing = wire; trailing.push_back(0); rejects_wire(trailing, value, decode);
    overwrite(trailing, 12, trailing.size(), 4); rejects_wire(trailing, value, decode);
}
template<class T, class Encode, class Decode>
void allocation_failures(const T& value, Encode encode, Decode decode);

void query_golden_and_full_width_identity() {
    const C::ProjectionQuery value{target(), identity(), 0}; auto expected = query_wire(value);
    Bytes encoded; check(C::encode_projection_query(value, encoded) && encoded == expected.bytes,
                         "Query differs from independent manual little-endian schema");
    check(encoded.size() == 120 && encoded[8] == 1 && encoded[9] == 0 && encoded[12] == 120,
          "Query header has wrong explicit size or kind");
    round_trip(value, C::encode_projection_query, C::decode_projection_query);
    auto mapped = value; mapped.mapping_id = wide;
    round_trip(mapped, C::encode_projection_query, C::decode_projection_query);
    mapped.identity.owner.id.assign(128, 'o');
    check(C::encode_projection_query(mapped, encoded) && encoded.size() == BIB_ENGINE_EDITOR_MAX_QUERY_BYTES,
          "Exact maximum query/owner bound rejected");
    mapped.identity.owner.id.push_back('o'); rejects_value(mapped, C::encode_projection_query);
}
void projection_reply_states_and_metadata() {
    const auto available = reply(); const auto expected = reply_wire(available); Bytes encoded;
    check(C::encode_projection_reply(available, encoded) && encoded == expected.bytes,
          "Projection reply differs from independent manual schema");
    round_trip(available, C::encode_projection_reply, C::decode_projection_reply);
    for (auto state : {C::ProjectionReply::State::noneditable, C::ProjectionReply::State::unavailable}) {
        auto value = available; value.state = state; value.projection.reset();
        round_trip(value, C::encode_projection_reply, C::decode_projection_reply);
    }
    auto bounded = available; bounded.projection->caret = {-1000000, 1000000, 1000000, 0};
    bounded.projection->input_purpose.assign(128, 'p');
    round_trip(bounded, C::encode_projection_reply, C::decode_projection_reply);
    for (unsigned field = 0; field < 5; ++field) {
        auto invalid = available;
        if (field == 0) invalid.observation_revision = 0;
        if (field == 1) invalid.readback_attested = false;
        if (field == 2) invalid.projection.reset();
        if (field == 3) invalid.projection->identity.context--;
        if (field == 4) invalid.state = static_cast<C::ProjectionReply::State>(3);
        rejects_value(invalid, C::encode_projection_reply);
    }
}
void every_typed_observation_round_trip() {
    std::vector<Observation> observations{key_observation(), text_observation(), selection_observation()};
    auto release = key_observation(); auto& transition = std::get<KeyData>(release.data).transition;
    transition.phase = KeyPhase::up; transition.repeat = false; transition.code.clear(); release.after.reset();
    observations.push_back(release);
    for (auto operation : {CompositionOperation::begin, CompositionOperation::update,
                           CompositionOperation::commit, CompositionOperation::cancel})
        observations.push_back(composition_observation(operation));
    for (const auto& observation : observations) {
        const auto value = request(observation); const auto expected = request_wire(value); Bytes encoded;
        check(encode_request(value, encoded) && encoded == expected.bytes,
              "Observation request differs from independent schema");
        round_trip(value, encode_request, decode_request);
    }
    auto plain = request(); plain.packet.observation.predecessor.reset(); plain.packet.observation.group.reset();
    plain.packet.observation.group_end = false; std::get<KeyData>(plain.packet.observation.data).is_composing = false;
    round_trip(plain, encode_request, decode_request);
}
void exact_dependency_bounds_and_default_authority() {
    for (bool composition : {false, true}) {
        auto value = request(composition ? composition_observation(CompositionOperation::begin) : text_observation());
        value.packet.observation.authority = Authority::default_action;
        value.packet.observation.group = 8; value.packet.observation.group_end = true; value.packet.default_token = 108;
        auto& groups = composition ? std::get<CompositionData>(value.packet.observation.data).source_groups :
                                     std::get<TextData>(value.packet.observation.data).source_groups;
        for (std::uint64_t i = 1; i <= 8; ++i) { groups.push_back(i); value.packet.default_dependencies.push_back({i, i + 100}); }
        round_trip(value, encode_request, decode_request);
        auto invalid = value;
        auto& excess = composition ? std::get<CompositionData>(invalid.packet.observation.data).source_groups :
                                     std::get<TextData>(invalid.packet.observation.data).source_groups;
        excess.push_back(9); rejects_value(invalid, encode_request);
        invalid = value; invalid.packet.default_dependencies.push_back({9, 109});
        rejects_value(invalid, encode_request);
        for (const auto count : {65535u, std::numeric_limits<std::uint32_t>::max()}) {
            auto wire = request_wire(value); mutate(wire, "packet.dependencies.count", count, 4);
            rejects_wire(wire.bytes, value, decode_request);
            wire = request_wire(value); mutate(wire, composition ? "composition.groups.count" : "text.groups.count", count, 4);
            rejects_wire(wire.bytes, value, decode_request);
        }
    }
}
void all_positions_truncated_and_trailing() {
    rejects_all_truncations(C::ProjectionQuery{target(), identity(), 0}, C::encode_projection_query, C::decode_projection_query);
    rejects_all_truncations(reply(), C::encode_projection_reply, C::decode_projection_reply);
    auto missing = reply(); missing.state = C::ProjectionReply::State::unavailable; missing.projection.reset();
    rejects_all_truncations(missing, C::encode_projection_reply, C::decode_projection_reply);
    for (const auto& observation : {key_observation(), text_observation(), selection_observation(),
                                  composition_observation(CompositionOperation::begin),
                                  composition_observation(CompositionOperation::update)})
        rejects_all_truncations(C::NativeRequestEnvelope{target(), request(observation)},
                                C::encode_native_request, C::decode_native_request);
    rejects_all_truncations(C::NativeResultEnvelope{target(), native_result()},
                            C::encode_native_result, C::decode_native_result);
}
void malformed_header_and_cross_kind_rejection() {
    const C::ProjectionQuery value{target(), identity(), 0}; const auto original = query_wire(value).bytes;
    for (std::size_t i = 0; i < 8; ++i) { auto bad = original; bad[i] ^= 0xff; rejects_wire(bad, value, C::decode_projection_query); }
    for (const auto kind : {0u, 2u, 3u, 4u, 5u, 65535u}) {
        auto bad = original; overwrite(bad, 8, kind, 2); rejects_wire(bad, value, C::decode_projection_query);
    }
    for (const auto flags : {1u, 256u, 65535u}) {
        auto bad = original; overwrite(bad, 10, flags, 2); rejects_wire(bad, value, C::decode_projection_query);
    }
    for (const auto total : {0u, 15u, 119u, 121u, 1048577u, std::numeric_limits<std::uint32_t>::max()}) {
        auto bad = original; overwrite(bad, 12, total, 4); rejects_wire(bad, value, C::decode_projection_query);
    }
    Bytes oversized(C::maximum_wire_bytes + 1, 0); rejects_wire(oversized, value, C::decode_projection_query);
    rejects_wire(original, reply(), C::decode_projection_reply);
    rejects_wire(original, request(), decode_request);
    rejects_wire(original, native_result(), decode_result);
    const auto native = request_wire(request()).bytes;
    rejects_wire(native, value, C::decode_projection_query); rejects_wire(native, reply(), C::decode_projection_reply);
    rejects_wire(native, native_result(), decode_result);
}
void strict_boolean_and_enum_fields() {
    const auto source = request();
    for (const auto& name : {"resolved.backward", "resolved.readback", "resolved.editable", "basis.backward",
                             "packet.default.present", "observation.predecessor.present", "observation.group.present",
                             "observation.group_end", "observation.after.present", "key.repeat", "key.composing"}) {
        auto wire = request_wire(source); mutate(wire, name, 2, 1); rejects_wire(wire.bytes, source, decode_request);
    }
    for (const auto& [name, invalid] : std::array<std::pair<const char*, unsigned>, 7>{{
            {"observation.kind", 4}, {"observation.authority", 4}, {"observation.before.direction", 3},
            {"observation.after.direction", 3}, {"key.phase", 2}, {"key.location", 4}, {"key.modifiers", 32}}}) {
        auto wire = request_wire(source); mutate(wire, name, invalid, 4); rejects_wire(wire.bytes, source, decode_request);
    }
    auto composition = request(composition_observation(CompositionOperation::begin));
    auto wire = request_wire(composition); mutate(wire, "composition.operation", 4, 4);
    rejects_wire(wire.bytes, composition, decode_request);
    wire = request_wire(composition); mutate(wire, "composition.replacement.present", 2, 1);
    rejects_wire(wire.bytes, composition, decode_request);
    auto selection = request(selection_observation()); wire = request_wire(selection);
    mutate(wire, "selection.backward", 2, 1); rejects_wire(wire.bytes, selection, decode_request);
    const auto projected = reply();
    for (const auto& name : {"reply.readback", "reply.projection.present"}) {
        auto bad = reply_wire(projected); mutate(bad, name, 2, 1); rejects_wire(bad.bytes, projected, C::decode_projection_reply);
    }
    auto bad = reply_wire(projected); mutate(bad, "reply.state", 3, 4); rejects_wire(bad.bytes, projected, C::decode_projection_reply);
}
void utf8_strings_and_length_preflight() {
    const auto source = request(text_observation());
    for (const auto& name : {"resolved.identity.owner", "resolved.text", "resolved.purpose", "basis.identity.owner",
                             "basis.text", "observation.before.value", "observation.after.value", "text.input_type", "text.value"}) {
        for (const auto byte : {0u, 0x80u, 0xc0u, 0xffu}) {
            auto wire = request_wire(source); overwrite(wire.bytes, wire.fields.at(name) + 4, byte, 1);
            rejects_wire(wire.bytes, source, decode_request);
        }
        auto wire = request_wire(source); mutate(wire, name, std::numeric_limits<std::uint32_t>::max(), 4);
        rejects_wire(wire.bytes, source, decode_request);
    }
    for (const auto& invalid : {std::string("x\0y", 3), std::string("\xc0\x80", 2), std::string("\xed\xa0\x80", 3),
                                std::string("\xf4\x90\x80\x80", 4), std::string("\xf0\x9f", 2)}) {
        auto value = C::ProjectionQuery{target(), identity(), 0}; value.identity.owner.id = invalid;
        rejects_value(value, C::encode_projection_query);
        rejects_wire(query_wire(value).bytes, C::ProjectionQuery{target(), identity(), 0}, C::decode_projection_query);
    }
    auto key = request();
    for (const auto byte : {0x20u, 0x7fu, 0x80u}) {
        auto wire = request_wire(key); overwrite(wire.bytes, wire.fields.at("key.code") + 4, byte, 1);
        rejects_wire(wire.bytes, key, decode_request);
    }
}
void independent_utf16_utf8_ranges() {
    const auto source = request();
    for (const auto& [name, invalid] : std::array<std::pair<const char*, unsigned>, 10>{{
            {"observation.before.utf16_start", 3}, {"observation.before.utf16_end", 3},
            {"observation.before.selection.begin", 3}, {"observation.before.selection.end", 5},
            {"observation.before.byte_length", 6}, {"observation.before.utf16_end", 99},
            {"resolved.selection.begin", 3}, {"resolved.selection.end", 99},
            {"basis.selection.begin", 3}, {"basis.selection.end", 99}}}) {
        auto wire = request_wire(source); mutate(wire, name, invalid, 4); rejects_wire(wire.bytes, source, decode_request);
    }
    auto invalid = source; invalid.packet.observation.before.selection_start = std::numeric_limits<std::size_t>::max();
    rejects_value(invalid, encode_request);
    invalid = source; invalid.resolved.selection.begin = std::numeric_limits<std::size_t>::max();
    rejects_value(invalid, encode_request);
    invalid = source; invalid.packet.observation.before.byte_length++;
    rejects_value(invalid, encode_request);
    auto composition = request(composition_observation(CompositionOperation::begin));
    auto wire = request_wire(composition); mutate(wire, "composition.selection.begin", 1, 4);
    rejects_wire(wire.bytes, composition, decode_request);
}
void exact_text_and_key_bounds() {
    auto value = request(); value.resolved.surrounding.assign(65536, 'x'); value.resolved.selection = {65536, 65536};
    value.resolved.backward = false; value.packet.basis = basis(value.resolved);
    value.packet.observation.before = {value.resolved.surrounding, 65536, 65536, Direction::none, {65536, 65536}, 65536};
    value.packet.observation.after = value.packet.observation.before;
    round_trip(value, encode_request, decode_request);
    auto invalid = value; invalid.resolved.surrounding.push_back('x'); rejects_value(invalid, encode_request);
    invalid = value; invalid.packet.basis.surrounding.push_back('x'); rejects_value(invalid, encode_request);
    invalid = value; invalid.packet.observation.before.value.push_back('x'); rejects_value(invalid, encode_request);
    value = request(); auto& key = std::get<KeyData>(value.packet.observation.data);
    key.transition.key.assign(64, 'k'); key.transition.code.assign(64, 'C');
    round_trip(value, encode_request, decode_request);
    invalid = value; std::get<KeyData>(invalid.packet.observation.data).transition.key.push_back('k');
    rejects_value(invalid, encode_request);
    invalid = value; std::get<KeyData>(invalid.packet.observation.data).transition.code.push_back('C');
    rejects_value(invalid, encode_request);
    invalid = value; std::get<KeyData>(invalid.packet.observation.data).transition.key.clear();
    rejects_value(invalid, encode_request);
}
void native_geometry_is_finite_and_bounded() {
    const auto source = reply();
    for (const auto& [name, number] : std::array<std::pair<const char*, double>, 6>{{
            {"projection.caret.x", std::numeric_limits<double>::infinity()},
            {"projection.caret.y", std::numeric_limits<double>::quiet_NaN()},
            {"projection.caret.width", -1}, {"projection.caret.height", 1000001},
            {"projection.caret.x", -1000001}, {"projection.caret.y", 1000001}}}) {
        auto wire = reply_wire(source); mutate(wire, name, std::bit_cast<std::uint64_t>(number), 8);
        rejects_wire(wire.bytes, source, C::decode_projection_reply);
    }
    auto invalid = source; invalid.projection->input_purpose.assign(129, 'p');
    rejects_value(invalid, C::encode_projection_reply);
    invalid = source; invalid.projection->readback_attested = false; rejects_value(invalid, C::encode_projection_reply);
    invalid = source; invalid.projection->mapping_id = 0; rejects_value(invalid, C::encode_projection_reply);
    invalid = source; invalid.projection->frame_id = 0; rejects_value(invalid, C::encode_projection_reply);
}
void exact_targets_and_envelope_output_preservation() {
    const C::NativeRequestEnvelope observed{target(), request()};
    const C::NativeResultEnvelope completed{target(), native_result()};
    round_trip(observed, C::encode_native_request, C::decode_native_request);
    round_trip(completed, C::encode_native_result, C::decode_native_result);
    const C::ProjectionQuery queried{target(), identity(), 0};
    const auto projected = reply();
    for (const auto& name : {"target.worker_epoch", "target.application_instance", "target.document_sequence",
                             "target.service_generation", "target.request_sequence"}) {
        auto wire = query_wire(queried); mutate(wire, name, 0, 8);
        rejects_wire(wire.bytes, queried, C::decode_projection_query);
        wire = reply_wire(projected); mutate(wire, name, 0, 8);
        rejects_wire(wire.bytes, projected, C::decode_projection_reply);
        wire = request_wire(observed.request); mutate(wire, name, 0, 8);
        rejects_wire(wire.bytes, observed, C::decode_native_request);
    }
    for (unsigned field = 0; field < 5; ++field) {
        auto invalid = observed;
        if (field == 0) invalid.target.worker_epoch = 0;
        if (field == 1) invalid.target.application_instance = 0;
        if (field == 2) invalid.target.document_sequence = 0;
        if (field == 3) invalid.target.service_generation = 0;
        if (field == 4) invalid.target.request_sequence = 0;
        rejects_value(invalid, C::encode_native_request);
        rejects_value(C::NativeResultEnvelope{invalid.target, completed.result}, C::encode_native_result);
        rejects_value(C::ProjectionQuery{invalid.target, identity(), 0}, C::encode_projection_query);
        auto invalid_reply = projected; invalid_reply.target = invalid.target;
        rejects_value(invalid_reply, C::encode_projection_reply);
    }
    auto truncated = request_wire(observed.request).bytes; truncated.pop_back();
    rejects_wire(truncated, observed, C::decode_native_request);
}
void result_flags_outcomes_and_native_composition() {
    const auto original = native_result(); const auto expected = result_wire(original); Bytes encoded;
    check(encode_result(original, encoded) && encoded == expected.bytes, "Result differs from independent wire schema");
    for (auto outcome : {Outcome::applied, Outcome::cancelled, Outcome::rejected})
        for (auto continuity : {Continuity::same, Continuity::key_retarget, Continuity::replaced}) {
            auto value = original; value.outcome = outcome; value.continuity = continuity;
            round_trip(value, encode_result, decode_result);
        }
    // These are transport bits. Controller separately judges their causality.
    for (unsigned mask = 0; mask < 128; ++mask) {
        auto value = original;
        value.key_dispatch_attested = (mask & 1) != 0; value.default_prevented = (mask & 2) != 0;
        value.default_handled = (mask & 4) != 0; value.changed_focused_frame = (mask & 8) != 0;
        value.allow_default = (mask & 16) != 0; value.key_retarget_attested = (mask & 32) != 0;
        value.composition_readback_attested = (mask & 64) != 0;
        round_trip(value, encode_result, decode_result);
    }
    for (auto state : {CompositionState::pending, CompositionState::live, CompositionState::ended}) {
        auto value = original; value.composition = CompositionFact{wide - 31, state};
        value.composition_readback_attested = true;
        value.projection->composition = state == CompositionState::live ? value.composition->transaction : 0;
        value.projection->retire->composition = value.projection->composition; value.retire = value.projection->retire;
        round_trip(value, encode_result, decode_result);
        const auto golden = result_wire(value); check(encode_result(value, encoded) && encoded == golden.bytes,
                                                     "Composition result differs from independent schema");
    }
    auto material = original; material.retired = NativeRetireMaterial{wide - 32, wide - 33, identity().context, wide - 34};
    round_trip(material, encode_result, decode_result);
    // A successful cleanup can retire the old mapping after native author code
    // has replaced the focused context. Its proof describes the old request.
    for (auto availability : {NativeAvailability::available, NativeAvailability::unavailable}) {
        auto replaced = original; replaced.continuity = Continuity::replaced; replaced.availability = availability;
        replaced.retired = NativeRetireMaterial{wide - 36, wide - 37, wide - 38, wide - 39};
        check(replaced.retired->input_context != replaced.readback_identity.context &&
              replaced.retired->mapping_id != original.projection->mapping_id, "Old retirement fixture reused current identity");
        if (availability == NativeAvailability::unavailable) { replaced.projection.reset(); replaced.retire.reset(); }
        round_trip(replaced, encode_result, decode_result);
        const auto golden = result_wire(replaced);
        check(encode_result(replaced, encoded) && encoded == golden.bytes, "Replaced-context retirement changed old proof");
    }
    for (auto availability : {NativeAvailability::noneditable, NativeAvailability::unavailable}) {
        auto value = original; value.availability = availability; value.projection.reset();
        round_trip(value, encode_result, decode_result);
        value.composition = CompositionFact{wide - 35, CompositionState::ended}; value.composition_readback_attested = true;
        round_trip(value, encode_result, decode_result);
        rejects_all_truncations(C::NativeResultEnvelope{target(), value}, C::encode_native_result, C::decode_native_result);
    }
    NativeResult unknown;
    round_trip(unknown, encode_result, decode_result);
    rejects_all_truncations(C::NativeResultEnvelope{target(), unknown}, C::encode_native_result, C::decode_native_result);
    unknown.projection = projection(); unknown.projection->retire.reset(); unknown.projection->readback_attested = false;
    round_trip(unknown, encode_result, decode_result);
    for (unsigned field = 0; field < 4; ++field) {
        auto invalid = NativeResult{};
        if (field == 0) invalid.allow_default = true;
        if (field == 1) invalid.key_retarget_attested = true;
        if (field == 2) invalid.composition_readback_attested = true;
        if (field == 3) invalid.composition = CompositionFact{1, CompositionState::pending};
        rejects_value(invalid, encode_result);
    }
}
void malformed_result_fields_and_checked_nulls() {
    auto value = native_result(); value.composition = CompositionFact{wide - 31, CompositionState::pending};
    value.composition_readback_attested = true;
    value.retired = NativeRetireMaterial{wide - 32, wide - 33, identity().context, wide - 34};
    for (const auto& name : {"result.projection.present", "projection.backward", "projection.readback", "projection.editable",
                             "projection.retire.present", "result.key_dispatch", "result.prevented", "result.handled",
                             "result.changed_frame", "result.allow_default", "result.key_retarget", "result.composition_readback",
                             "result.composition.present", "result.readback", "result.retire.present", "result.retired.present"})
        for (auto byte : {2u, 255u}) {
            auto wire = result_wire(value); mutate(wire, name, byte, 1);
            rejects_wire(wire.bytes, C::NativeResultEnvelope{target(), value}, C::decode_native_result);
        }
    for (const auto& [name, invalid] : std::array<std::pair<const char*, unsigned>, 4>{{
            {"result.outcome", 4}, {"result.continuity", 3}, {"result.composition.state", 3}, {"result.availability", 3}}}) {
        auto wire = result_wire(value); mutate(wire, name, invalid, 4);
        rejects_wire(wire.bytes, C::NativeResultEnvelope{target(), value}, C::decode_native_result);
    }
    for (const auto& name : {"result.observation_revision", "result.composition.transaction", "result.retire.token",
                             "result.retire.mapping", "result.retire.context", "result.retired.token"}) {
        auto wire = result_wire(value); mutate(wire, name, 0, 8);
        rejects_wire(wire.bytes, C::NativeResultEnvelope{target(), value}, C::decode_native_result);
    }
    for (unsigned field = 0; field < 6; ++field) {
        auto invalid = native_result();
        if (field == 0) invalid.observation_revision = 0;
        if (field == 1) invalid.readback_attested = false;
        if (field == 2) invalid.readback_identity.context--;
        if (field == 3) invalid.projection->retire.reset();
        if (field == 4) invalid.retire->mapping_id--;
        if (field == 5) { invalid.availability = NativeAvailability::unavailable; invalid.projection.reset(); invalid.allow_default = true; }
        rejects_value(invalid, encode_result);
    }
    for (const auto availability : {NativeAvailability::noneditable, NativeAvailability::unavailable}) {
        auto invalid = native_result(); invalid.availability = availability;
        rejects_value(invalid, encode_result); // A checked null state cannot include an editable projection.
        invalid.projection.reset(); invalid.observation_revision = 0; rejects_value(invalid, encode_result);
        invalid.observation_revision = wide; invalid.readback_attested = false; rejects_value(invalid, encode_result);
    }
}
void retirement_authority_and_exact_bounds() {
    for (bool observed : {false, true}) {
        const auto value = revocation(observed); const auto golden = revocation_wire(value); Bytes encoded;
        check(C::encode_revocation(value, encoded) && encoded == golden.bytes,
              "Retirement request differs from independent schema");
        round_trip(value, C::encode_revocation, C::decode_revocation);
        rejects_all_truncations(value, C::encode_revocation, C::decode_revocation);
        allocation_failures(value, C::encode_revocation, C::decode_revocation);
    }
    auto value = revocation(); value.request.material.composition = wide - 35;
    value.request.observed->composition = value.request.material.composition;
    value.request.observed->basis.composition = value.request.material.composition;
    value.request.observed->held_keys.clear(); value.request.observed->reason.assign(512, 'r');
    for (unsigned index = 0; index < 64; ++index) {
        auto held = std::get<KeyData>(key_observation().data); held.transition.code = "Key" + std::to_string(index);
        value.request.observed->held_keys.push_back(std::move(held));
    }
    round_trip(value, C::encode_revocation, C::decode_revocation);
    auto invalid = value; invalid.request.observed->held_keys.push_back(invalid.request.observed->held_keys.front());
    rejects_value(invalid, C::encode_revocation);
    invalid = value; invalid.request.observed->reason.push_back('r'); rejects_value(invalid, C::encode_revocation);
    invalid = value; invalid.request.observed->held_keys.front().transition.phase = KeyPhase::up;
    invalid.request.observed->held_keys.front().transition.repeat = false; rejects_value(invalid, C::encode_revocation);
    invalid = value; invalid.request.observed->basis.identity.context--; rejects_value(invalid, C::encode_revocation);
    invalid = value; invalid.request.observed->composition--; rejects_value(invalid, C::encode_revocation);
    invalid = value; invalid.request.material.input_context--; rejects_value(invalid, C::encode_revocation);
    for (const auto count : {65u, 65535u, std::numeric_limits<std::uint32_t>::max()}) {
        auto wire = revocation_wire(value); mutate(wire, "retire.observed.keys.count", count, 4);
        rejects_wire(wire.bytes, value, C::decode_revocation);
    }
    for (const auto& name : {"retire.token", "retire.mapping", "retire.context", "retire.observed.incarnation"}) {
        auto wire = revocation_wire(value); mutate(wire, name, 0, 8); rejects_wire(wire.bytes, value, C::decode_revocation);
    }
    auto wire = revocation_wire(value); mutate(wire, "retire.observed.present", 2, 1);
    rejects_wire(wire.bytes, value, C::decode_revocation);
    wire = revocation_wire(value); overwrite(wire.bytes, wire.fields.at("retire.observed.reason") + 4, 0, 1);
    rejects_wire(wire.bytes, value, C::decode_revocation);
}
template<class Function>
std::pair<bool, std::size_t> with_allocations(std::size_t fail_after, Function body) {
    allocation_test::calls = 0; allocation_test::fail_after = fail_after; allocation_test::armed = true;
    const bool result = body(); allocation_test::armed = false;
    return {result, allocation_test::calls};
}
template<class T, class Encode, class Decode>
void allocation_failures(const T& value, Encode encode, Decode decode) {
    Bytes wire;
    const auto encoded = with_allocations(std::numeric_limits<std::size_t>::max(), [&] { return encode(value, wire); });
    check(encoded.first && encoded.second > 0, "Allocation fixture encoded without expected storage allocation");
    for (std::size_t index = 0; index < encoded.second; ++index) {
        Bytes output{0xc1, 0xc2, 0xc3}; const auto sentinel = output;
        const auto failed = with_allocations(index, [&] { return encode(value, output); });
        check(!failed.first && output == sentinel, "Encode allocation failure escaped or changed caller bytes");
    }
    T output{};
    const auto decoded = with_allocations(std::numeric_limits<std::size_t>::max(), [&] { return decode(wire, output); });
    check(decoded.first && equal(output, value), "Allocation fixture did not decode");
    for (std::size_t index = 0; index < decoded.second; ++index) {
        output = value;
        const auto failed = with_allocations(index, [&] { return decode(wire, output); });
        check(!failed.first && equal(output, value), "Decode allocation failure escaped or changed caller record");
    }
}
void allocation_failures_and_unallocated_preflight() {
    auto queried = C::ProjectionQuery{target(), identity(), 0}; queried.identity.owner.id.assign(128, 'o');
    allocation_failures(queried, C::encode_projection_query, C::decode_projection_query);
    allocation_failures(reply(), C::encode_projection_reply, C::decode_projection_reply);
    const C::NativeRequestEnvelope observed{target(), request(text_observation())};
    allocation_failures(observed, C::encode_native_request, C::decode_native_request);
    allocation_failures(C::NativeResultEnvelope{target(), native_result()}, C::encode_native_result, C::decode_native_result);
    for (const auto& field : {"packet.dependencies.count", "text.groups.count", "observation.before.byte_length"}) {
        auto wire = request_wire(observed.request); mutate(wire, field, 65535, 4);
        auto output = observed;
        const auto preflight = with_allocations(std::numeric_limits<std::size_t>::max(),
                                               [&] { return C::decode_native_request(wire.bytes, output); });
        check(!preflight.first && preflight.second == 0 && equal(output, observed),
              "Malformed request allocated owning storage before complete preflight");
    }
}

static_assert(noexcept(C::encode_projection_query(std::declval<const C::ProjectionQuery&>(), std::declval<Bytes&>())));
static_assert(noexcept(C::decode_projection_query(std::declval<std::span<const std::uint8_t>>(), std::declval<C::ProjectionQuery&>())));
static_assert(noexcept(C::encode_projection_reply(std::declval<const C::ProjectionReply&>(), std::declval<Bytes&>())));
static_assert(noexcept(C::decode_projection_reply(std::declval<std::span<const std::uint8_t>>(), std::declval<C::ProjectionReply&>())));
static_assert(noexcept(C::encode_native_request(std::declval<const C::NativeRequestEnvelope&>(), std::declval<Bytes&>())));
static_assert(noexcept(C::decode_native_request(std::declval<std::span<const std::uint8_t>>(), std::declval<C::NativeRequestEnvelope&>())));
static_assert(noexcept(C::encode_native_result(std::declval<const C::NativeResultEnvelope&>(), std::declval<Bytes&>())));
static_assert(noexcept(C::decode_native_result(std::declval<std::span<const std::uint8_t>>(), std::declval<C::NativeResultEnvelope&>())));
static_assert(noexcept(C::encode_revocation(std::declval<const C::RevocationEnvelope&>(), std::declval<Bytes&>())));
static_assert(noexcept(C::decode_revocation(std::declval<std::span<const std::uint8_t>>(), std::declval<C::RevocationEnvelope&>())));
} // namespace

int main() {
    const std::array<std::pair<const char*, void(*)()>, 16> cases{{
        {"query golden and full-width identity", query_golden_and_full_width_identity},
        {"projection states and native metadata", projection_reply_states_and_metadata},
        {"all typed observations", every_typed_observation_round_trip},
        {"default dependencies and exact bounds", exact_dependency_bounds_and_default_authority},
        {"every-position truncation and trailing bytes", all_positions_truncated_and_trailing},
        {"closed headers and wire kinds", malformed_header_and_cross_kind_rejection},
        {"strict boolean and enum fields", strict_boolean_and_enum_fields},
        {"UTF8 and bounded string preflight", utf8_strings_and_length_preflight},
        {"independent UTF16 and UTF8 ranges", independent_utf16_utf8_ranges},
        {"exact text and key bounds", exact_text_and_key_bounds},
        {"finite bounded native geometry", native_geometry_is_finite_and_bounded},
        {"exact targets and envelope outputs", exact_targets_and_envelope_output_preservation},
        {"allocation failures and no-allocation preflight", allocation_failures_and_unallocated_preflight},
        {"result flags outcomes and composition", result_flags_outcomes_and_native_composition},
        {"strict result fields and checked nulls", malformed_result_fields_and_checked_nulls},
        {"provider retirement and exact bounds", retirement_authority_and_exact_bounds}
    }};
    unsigned failed = 0;
    for (const auto& [name, body] : cases) {
        try { body(); std::cout << "PASS " << name << '\n'; }
        catch (const std::exception& error) { ++failed; std::cerr << "FAIL " << name << ": " << error.what() << '\n'; }
    }
    std::cout << "SUMMARY cases=" << cases.size() << " failed=" << failed << " checks=" << checks
              << "; pure codec only, no native editor/engine qualification\n";
    return failed ? 1 : 0;
}
