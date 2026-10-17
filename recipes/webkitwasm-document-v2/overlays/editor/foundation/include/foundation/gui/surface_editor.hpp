// SPDX-License-Identifier: CC0-1.0
#pragma once

#include <foundation/gui/surface.hpp>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <variant>
#include <vector>

namespace foundation::gui_editor {

using gui_surface::ByteRange;
using gui_surface::Identity;

// Private owner records: these do not extend Policy, Events or a public catalog.
struct Basis {
    std::uint64_t token = 0;
    Identity identity;
    std::uint64_t editor_revision = 0;
    std::string surrounding;
    ByteRange selection;
    bool backward = false;
    std::uint64_t composition = 0;
    bool operator==(const Basis&) const = default;
};
struct NativeRetireMaterial {
    // Issued and checked by the actual provider; never synthesized by Controller.
    std::uint64_t token = 0, mapping_id = 0, input_context = 0, composition = 0;
    bool operator==(const NativeRetireMaterial&) const = default;
};
struct NativeProjection {
    Identity identity;
    std::uint64_t editor_revision = 0;
    std::string surrounding;
    ByteRange selection;
    bool backward = false;
    std::uint64_t composition = 0;
    // Owner-private registry keys, never renderer authority or native pointers.
    std::uint64_t mapping_id = 0, frame_id = 0;
    bool readback_attested = false;
    gui_surface::Rect caret;
    bool editable = true;
    std::string input_purpose;
    std::optional<NativeRetireMaterial> retire;
    bool operator==(const NativeProjection&) const = default;
};
enum class Direction { forward, backward, none };
struct TextObservation {
    std::string value;
    std::size_t selection_start = 0, selection_end = 0; // UTF-16 scalar boundaries.
    Direction selection_direction = Direction::none;
    ByteRange selection; // Independently checked derived UTF-8 offsets.
    std::size_t byte_length = 0;
    bool operator==(const TextObservation&) const = default;
};
enum class Kind { key, text, selection, composition };
enum class Authority { native, range, default_action, composition };
struct KeyData {
    gui_surface::KeyTransition transition;
    bool is_composing = false;
    bool operator==(const KeyData&) const = default;
};
struct TextData {
    std::string input_type, text;
    ByteRange replacement;
    std::vector<std::uint64_t> source_groups;
    bool operator==(const TextData&) const = default;
};
struct SelectionData {
    ByteRange selection;
    bool backward = false;
    bool operator==(const SelectionData&) const = default;
};
struct CompositionData {
    gui_surface::CompositionOperation operation = gui_surface::CompositionOperation::begin;
    std::string text;
    ByteRange selection;
    std::optional<ByteRange> replacement;
    std::vector<std::uint64_t> source_groups;
    bool operator==(const CompositionData&) const = default;
};
using Data = std::variant<KeyData, TextData, SelectionData, CompositionData>;
struct Observation {
    std::uint64_t id = 0;
    std::optional<std::uint64_t> predecessor;
    Kind kind = Kind::key;
    Authority authority = Authority::native;
    std::optional<std::uint64_t> group;
    bool group_end = false;
    std::uint64_t transaction = 0;
    TextObservation before;
    std::optional<TextObservation> after;
    Data data = KeyData{};
    bool operator==(const Observation&) const = default;
};
struct DefaultDependency {
    std::uint64_t group = 0, token = 0;
    bool operator==(const DefaultDependency&) const = default;
};
struct Packet {
    std::uint64_t session = 0;
    Basis basis;
    std::optional<std::uint64_t> default_token;
    std::vector<DefaultDependency> default_dependencies;
    Observation observation;
    bool operator==(const Packet&) const = default;
};
enum class Outcome { applied, cancelled, rejected, unknown };
enum class Continuity { same, key_retarget, replaced };
enum class CompositionState { pending, live, ended };
struct CompositionFact {
    std::uint64_t transaction = 0;
    CompositionState state = CompositionState::pending;
    bool operator==(const CompositionFact&) const = default;
};
struct NativeRequest {
    NativeProjection resolved;
    Packet packet;
};
enum class NativeAvailability { available, noneditable, unavailable };
struct RetirementReadback {
    NativeAvailability availability = NativeAvailability::available;
    Identity identity;
    std::uint64_t observation_revision = 0;
    bool readback_attested = false;
    bool authority_retired = false;
    bool operator==(const RetirementReadback&) const = default;
};
struct NativeResult {
    Outcome outcome = Outcome::unknown;
    Continuity continuity = Continuity::same;
    std::optional<NativeProjection> projection;
    bool key_dispatch_attested = false;
    bool default_prevented = false, default_handled = false, changed_focused_frame = false;
    bool allow_default = false, key_retarget_attested = false;
    // Void native composition calls require actual post-call readback, not a
    // guessed string or a successful function return. The backend attests it.
    bool composition_readback_attested = false;
    std::optional<CompositionFact> composition;
    NativeAvailability availability = NativeAvailability::available;
    std::uint64_t observation_revision = 0;
    Identity readback_identity;
    bool readback_attested = false;
    std::optional<NativeRetireMaterial> retire;
    std::optional<NativeRetireMaterial> retired;
};
struct Revocation {
    Basis basis;
    // Trusted framework correlation only; not proof of a concrete DOM node.
    std::uint64_t incarnation = 0, composition = 0;
    std::vector<KeyData> held_keys;
    std::string reason;
    bool operator==(const Revocation&) const = default;
};
struct NativeRevocationRequest {
    NativeRetireMaterial material;
    Identity identity;
    std::optional<Revocation> observed;
};
struct Receipt {
    std::uint64_t session = 0, id = 0, submitted_token = 0;
    std::optional<std::uint64_t> predecessor;
    Outcome outcome = Outcome::unknown;
    std::optional<Basis> basis;
    Continuity continuity = Continuity::same;
    std::optional<DefaultDependency> default_token;
    std::optional<CompositionFact> composition;
    std::optional<RetirementReadback> retirement;
    bool operator==(const Receipt&) const = default;
};
enum class State { detached, ready, suspended, terminal_unknown, closed };
enum class Admission { completed, rejected, busy, unavailable, terminal, awaiting_projection, prepared };
struct DispatchResult {
    Admission admission = Admission::unavailable;
    std::optional<Receipt> receipt;
    std::string detail;
};
struct PreparedDispatch {
    Admission admission = Admission::unavailable;
    std::uint64_t ticket = 0;
    std::optional<NativeRequest> request;
    std::optional<Revocation> revocation;
    std::optional<Receipt> receipt;
    std::string detail;
};

struct Settlement {
    std::uint64_t session{}, id{}, submitted_token{};
    std::optional<std::uint64_t> predecessor;
    bool operator==(const Settlement&) const = default;
};
struct EditorPublication {
    std::optional<Basis> basis;
    std::optional<Settlement> settlement;
    std::optional<CompositionFact> composition;
    std::optional<RetirementReadback> retirement;
    bool operator==(const EditorPublication&) const = default;
};
struct EditorCompletion {
    std::uint64_t ticket{};
    DispatchResult result;
};
struct EditorTerminalHook {
    void* context{};
    // Trusted atomic notification, including from a foreign-thread failure.
    // No engine exports, allocation, cleanup or synthetic result/leave.
    void (*notify)(void*) noexcept{};
};

} // namespace foundation::gui_editor
