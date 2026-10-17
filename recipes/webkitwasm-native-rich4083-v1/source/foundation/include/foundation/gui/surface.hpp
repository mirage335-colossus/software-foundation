// SPDX-License-Identifier: CC0-1.0
#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>
#include <string>
#include <variant>
#include <vector>

// An optional generic companion to the existing GUI contract. This header does
// not include, extend or change any existing gui type or portable guest ABI.
// Backend implementations must report only physical capabilities they provide.
namespace foundation::gui_surface {

inline constexpr std::uint32_t protocol_version = 1;
inline constexpr std::uint32_t mouse_input_version = 1;

enum class Status {
    ok, invalid_value, limit_exceeded, unsupported, busy, closed,
    stale_identity, stale_revision, stale_preparation, duplicate,
    not_focused, unavailable, popup_active, invalid_transaction
};
const char* status_name(Status) noexcept;

enum class Feature : std::uint64_t {
    raw_keys = 1ull << 0,
    committed_text = 1ull << 1,
    composition = 1ull << 2,
    surrounding_text = 1ull << 3,
    selection = 1ull << 4,
    focus = 1ull << 5,
    raw_pointer = 1ull << 6,
    clipboard_text = 1ull << 7,
    clipboard_html = 1ull << 8,
    choice_popup = 1ull << 9,
    action_popup = 1ull << 10,
    search_popup = 1ull << 11,
    popup_submenus = 1ull << 12,
    mouse_input = 1ull << 13
};
using Features = std::uint64_t;
constexpr Features feature(Feature value) noexcept { return static_cast<Features>(value); }
constexpr Features operator|(Feature a, Feature b) noexcept { return feature(a) | feature(b); }
inline constexpr Features known_features = (1ull << 14) - 1;

// Positive negotiated limits cannot exceed these default hard ceilings.
struct Limits {
    std::size_t text_bytes = 65536;
    std::size_t clipboard_bytes = 65536;
    std::size_t popup_items = 1024;
    std::size_t popup_text_bytes = 65536;
    std::size_t capture_rules = 64;
    std::size_t held_keys = 64;
    unsigned popup_depth = 8;
    bool operator==(const Limits&) const = default;
};
struct Capabilities {
    std::uint32_t version = protocol_version;
    Features supported = 0; // No physical support by default.
    Limits limits;
    // Zero when absent; mouse_input requires the explicitly selected version1.
    std::uint32_t mouse_input_version = 0;
    bool operator==(const Capabilities&) const = default;
};
Status validate_capabilities(const Capabilities&) noexcept;
Status negotiate(const Capabilities&, Features required) noexcept;

struct OwnerKey {
    std::string id;
    std::uint64_t generation = 0;
    bool operator==(const OwnerKey&) const = default;
};
struct Identity {
    OwnerKey owner;
    std::uint64_t presentation_revision = 0;
    std::uint64_t generation = 0; // Native/document-session generation.
    std::uint64_t epoch = 0;
    std::uint64_t context = 0; // Fresh when the target/replacement basis retires.
    bool operator==(const Identity&) const = default;
};
struct Rect {
    double x = 0, y = 0, width = 0, height = 0;
    bool operator==(const Rect&) const = default;
};
struct ByteRange {
    std::size_t begin = 0, end = 0;
    bool operator==(const ByteRange&) const = default;
};
// Text excludes NUL. Boundaries are Unicode scalar/codepoint boundaries in
// UTF-8, not grapheme boundaries. The engine owns checked UTF-16/node mapping.
bool valid_text(const std::string&) noexcept;
bool text_boundary(const std::string&, std::size_t) noexcept;
bool valid_range(const std::string&, ByteRange) noexcept;

enum Modifier : std::uint32_t { shift = 1, control = 2, alt = 4, meta = 8, alt_graph = 16 };
inline constexpr std::uint32_t known_modifiers = 31;
enum class KeyPhase { down, up };
struct KeyTransition {
    KeyPhase phase = KeyPhase::down;
    std::string key, code; // Logical key; physical code may be unknown/empty.
    unsigned location = 0; // 0 unknown/standard, 1 left, 2 right, 3 keypad.
    std::uint32_t modifiers = 0;
    bool repeat = false;
    bool operator==(const KeyTransition&) const = default;
};
enum class Capture { pass, capture };
struct CaptureRule {
    std::string key, code; // Empty means wildcard. First matching rule wins.
    std::uint32_t required_modifiers = 0, forbidden_modifiers = 0;
    bool down = true, up = true;
    Capture disposition = Capture::capture;
    bool operator==(const CaptureRule&) const = default;
};
struct KeyCapturePolicy {
    Capture fallback = Capture::pass;
    std::vector<CaptureRule> rules;
    bool operator==(const KeyCapturePolicy&) const = default;
};
Capture capture_key(const KeyCapturePolicy&, const KeyTransition&) noexcept;

struct EditorContext {
    std::uint64_t revision = 0;
    // Native publication attests the live host transaction. Zero means none;
    // strings alone cannot prove a composition survived native selection edits.
    std::uint64_t composition_transaction = 0;
    std::string surrounding;
    ByteRange selection;
    bool selection_backward = false;
    Rect caret;
    bool editable = false;
    std::string input_purpose;
    bool operator==(const EditorContext&) const = default;
};
struct TextCommit {
    std::uint64_t transaction = 0, editor_revision = 0;
    std::string text;
    std::optional<ByteRange> replacement;
    bool operator==(const TextCommit&) const = default;
};
enum class CompositionOperation { begin, update, commit, cancel };
struct CompositionEdit {
    CompositionOperation operation = CompositionOperation::begin;
    std::uint64_t transaction = 0, editor_revision = 0;
    std::string text;
    ByteRange selection; // Byte offsets within preedit/commit text.
    std::optional<ByteRange> replacement; // Begin only, in surrounding text.
    bool operator==(const CompositionEdit&) const = default;
};
struct SelectionChange {
    std::uint64_t editor_revision = 0;
    ByteRange selection;
    bool backward = false;
    bool operator==(const SelectionChange&) const = default;
};
enum class FocusCause { direct, owned_popup, owned_service, external };
struct FocusChange {
    bool focused = false, active = true;
    FocusCause cause = FocusCause::direct;
    bool operator==(const FocusChange&) const = default;
};

enum class PointerPhase { move, down, up, cancel, wheel, context };
struct PointerTransition {
    PointerPhase phase = PointerPhase::move;
    std::uint64_t pointer = 0;
    double x = 0, y = 0, wheel_x = 0, wheel_y = 0;
    unsigned button = 0, buttons = 0, clicks = 1;
    std::uint32_t modifiers = 0;
    bool operator==(const PointerTransition&) const = default;
};

// A separate optional single-mouse stream. It does not narrow raw_pointer's
// multi-contact contract. The u64 capture token is never a native pointer ID.
enum class MousePhase { move = 0, down = 1, up = 2, wheel = 3, cancel = 4, context = 5 };
enum class ContextOrigin { pointer = 0, keyboard = 1 };
constexpr std::uint32_t mouse_button_bit(unsigned button) noexcept {
    constexpr std::uint32_t bits[]{1, 4, 2, 8, 16};
    return button < 5 ? bits[button] : 0;
}
struct MouseTransition {
    std::uint32_t version = gui_surface::mouse_input_version;
    MousePhase phase = MousePhase::move;
    std::uint64_t capture_token = 0;
    double x = 0, y = 0, wheel_x = 0, wheel_y = 0;
    unsigned button = 0, buttons = 0, clicks = 0; // Zero means unknown click count.
    std::uint32_t modifiers = 0;
    ContextOrigin context_origin = ContextOrigin::pointer;
    bool operator==(const MouseTransition&) const = default;
};

struct MimeText {
    // Only text/plain and text/html. Validation does not sanitize markup; the
    // engine must insert clipboard HTML as bounded data without executing it.
    std::string type, text;
    bool operator==(const MimeText&) const = default;
};
struct ClipboardOffer {
    std::uint64_t id = 0, editor_revision = 0;
    std::vector<MimeText> formats;
    bool operator==(const ClipboardOffer&) const = default;
};
enum class ClipboardOperation { copy, cut, paste };
enum class TransferStatus { accepted, unavailable, cancelled, error };
struct ClipboardInput {
    ClipboardOperation operation = ClipboardOperation::paste;
    std::uint64_t transfer = 0, offer = 0, editor_revision = 0;
    TransferStatus status = TransferStatus::accepted;
    std::vector<MimeText> formats; // Paste only; copy/cut use the published offer.
    bool operator==(const ClipboardInput&) const = default;
};

struct PopupToken {
    std::uint64_t generation = 0, epoch = 0, instance = 0, revision = 0;
    bool operator==(const PopupToken&) const = default;
};
using PopupItemId = std::uint64_t;
enum class PopupKind { single_choice, action_menu, search_results };
enum class PopupItemKind { item, group_label, separator, submenu };
enum class Direction { left_to_right, right_to_left };
struct PopupItem {
    PopupItemId id = 0;
    std::string label, accessible_name;
    PopupItemKind kind = PopupItemKind::item;
    bool enabled = true, selected = false, checkable = false, checked = false;
    std::vector<PopupItem> children;
    bool operator==(const PopupItem&) const = default;
};
struct Popup {
    PopupToken token;
    PopupKind kind = PopupKind::single_choice;
    Rect anchor;
    Direction direction = Direction::left_to_right;
    std::vector<PopupItem> items;
    std::optional<PopupItemId> selected;
    bool operator==(const Popup&) const = default;
};
enum class PopupOperation { accept, cancel };
struct PopupReply {
    PopupToken token;
    PopupOperation operation = PopupOperation::cancel;
    std::optional<PopupItemId> item;
    bool operator==(const PopupReply&) const = default;
};

struct Presentation {
    Identity identity;
    Features required = 0;
    Rect bounds, clip;
    double display_scale = 1;
    bool available = true;
    KeyCapturePolicy keys;
    std::optional<EditorContext> editor;
    std::optional<ClipboardOffer> clipboard;
    std::optional<Popup> popup;
    bool operator==(const Presentation&) const = default;
};
using Input = std::variant<KeyTransition, TextCommit, CompositionEdit, SelectionChange,
                           FocusChange, PointerTransition, ClipboardInput, PopupReply, MouseTransition>;
struct Event {
    Identity identity;
    // Monotonically increasing; gaps are permitted. UINT64_MAX exhausts this
    // policy's stream. Resume requires a fresh session generation/Policy.
    std::uint64_t sequence = 0;
    Input input;
    bool operator==(const Event&) const = default;
};
enum class RevocationReason { replaced, unavailable, legacy_presentation, focus_loss, service, closed };
struct Revocation {
    std::optional<Identity> identity;
    RevocationReason reason = RevocationReason::replaced;
    std::optional<std::uint64_t> composition;
    std::optional<PopupToken> popup;
    std::vector<KeyTransition> held_keys;
    bool empty() const noexcept { return !composition && !popup && held_keys.empty(); }
};
struct AcceptedEvent {
    Event event;
    Capture capture = Capture::pass;
    Revocation revoked;
    // A cut is authorized only for an accepted clipboard transfer. Policy
    // acceptance itself never establishes that an OS/browser write succeeded.
    bool permits_cut() const noexcept;
};
struct AcceptResult {
    Status status = Status::invalid_value;
    std::optional<AcceptedEvent> accepted;
};

namespace detail { struct PolicyState; }
class PreparedPresentation {
public:
    PreparedPresentation() noexcept;
    ~PreparedPresentation();
    PreparedPresentation(PreparedPresentation&&) noexcept;
    PreparedPresentation& operator=(PreparedPresentation&&) noexcept;
    PreparedPresentation(const PreparedPresentation&) = delete;
    PreparedPresentation& operator=(const PreparedPresentation&) = delete;
    explicit operator bool() const noexcept;
private:
    friend class Policy;
    std::shared_ptr<detail::PolicyState> state_;
    std::uint64_t token_ = 0;
    PreparedPresentation(std::shared_ptr<detail::PolicyState>, std::uint64_t) noexcept;
    void abandon() noexcept;
};
struct Preparation {
    Status status = Status::invalid_value;
    PreparedPresentation prepared;
};
struct CommitResult {
    Status status = Status::invalid_value;
    Revocation revoked;
};

// One serialized owner and one surface per Policy. No callback is invoked here.
// accept() returns owned work only after consuming its identity/sequence; invoke
// the engine afterward. A callback can install a successor; a throw or unknown
// engine outcome never makes the accepted event replayable.
class Policy {
public:
    // generation is a fresh nonzero session identity, never reused after close.
    explicit Policy(Capabilities, std::uint64_t generation);
    ~Policy();
    Policy(const Policy&) = delete;
    Policy& operator=(const Policy&) = delete;
    Policy(Policy&&) = delete;
    Policy& operator=(Policy&&) = delete;

    const Capabilities& capabilities() const noexcept;
    // Borrowed until the next non-const policy operation. Copy if retained.
    const Presentation* accepted() const noexcept;
    bool focused() const noexcept;
    bool active() const noexcept;
    std::optional<std::uint64_t> composition() const noexcept;
    std::uint64_t last_sequence() const noexcept;

    // At most one outstanding preparation. Preparing B does not suspend A.
    // Allocations can throw; rejection/throws leave accepted state untouched.
    // Destruction of the token discards only its own staged presentation.
    Preparation prepare(const Presentation&);
    // Call only after the corresponding old-GUI snapshot publication succeeds.
    // Consumes the token on every outcome. No allocation/callback occurs here.
    // This policy alone cannot make legacy Adapter::present atomic: its caller
    // must stage/guard native callbacks and input between prepare/publication/
    // commit, or prove an equivalent integration. An intervening accepted event
    // makes this commit stale, even if the caller already published its pixels.
    CommitResult commit(PreparedPresentation&&, std::uint64_t published_revision) noexcept;
    // Legacy publication explicitly revokes the companion. A successor needs a
    // fresh context; old generation/epoch/context identities cannot resurrect.
    CommitResult legacy_present(std::uint64_t published_revision);
    Revocation close();
    AcceptResult accept(Event);
private:
    std::shared_ptr<detail::PolicyState> state_;
};

} // namespace foundation::gui_surface
