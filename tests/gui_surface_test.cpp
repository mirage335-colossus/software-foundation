// SPDX-License-Identifier: CC0-1.0
#include <foundation/gui/surface.hpp>

#include <array>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <new>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>

// A commit must install already-owned state without allocating. The gate is
// enabled only around that operation, after all fixtures and preparations exist.
namespace allocation_test { bool fail = false; }
void* operator new(std::size_t size) {
    if (allocation_test::fail) throw std::bad_alloc();
    if (void* memory = std::malloc(size ? size : 1)) return memory;
    throw std::bad_alloc();
}
void* operator new[](std::size_t size) { return ::operator new(size); }
void operator delete(void* memory) noexcept { std::free(memory); }
void operator delete[](void* memory) noexcept { std::free(memory); }
void operator delete(void* memory, std::size_t) noexcept { std::free(memory); }
void operator delete[](void* memory, std::size_t) noexcept { std::free(memory); }

namespace {
namespace surface = foundation::gui_surface;
using namespace surface;
constexpr std::uint64_t generation = 7;
constexpr auto maximum = std::numeric_limits<std::uint64_t>::max();
static_assert(noexcept(std::declval<Policy&>().commit(std::declval<PreparedPresentation&&>(), 1)));
static_assert(!std::is_copy_constructible_v<PreparedPresentation>);
static_assert(std::is_nothrow_move_constructible_v<PreparedPresentation>);
static_assert(!std::is_move_constructible_v<Policy>);

void check(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
void expect(Status value, Status wanted, const char* message) {
    if (value != wanted)
        throw std::runtime_error(std::string(message) + ": expected " + status_name(wanted) + ", got " + status_name(value));
}
template<class F> void invalid_argument(F action, const char* message) {
    bool rejected = false;
    try { action(); } catch (const std::invalid_argument&) { rejected = true; }
    check(rejected, message);
}
Capabilities capabilities() {
    Capabilities result;
    // This is a fake policy harness, not an assertion that any backend supplies
    // these physical streams. Real adapters must negotiate independently.
    result.supported = known_features;
    result.mouse_input_version = mouse_input_version;
    return result;
}
std::string unicode_text() { return "A\xc3\xa9\xf0\x9f\x94\x92" "e\xcc\x81Z"; }
Presentation presentation() {
    Presentation result;
    result.identity = {{"viewer", 3}, 1, generation, 1, 1};
    result.bounds = {0, 0, 640, 480};
    result.clip = {10, 20, 600, 400};
    result.display_scale = 1.25;
    EditorContext editor;
    editor.revision = 1;
    editor.surrounding = unicode_text();
    editor.selection = {1, 7};
    editor.caret = {40, 50, 1, 20};
    editor.editable = true;
    editor.input_purpose = "text";
    result.editor = std::move(editor);
    return result;
}
PopupItem item(PopupItemId id, std::string label, bool enabled = true) {
    PopupItem result;
    result.id = id;
    result.label = std::move(label);
    result.enabled = enabled;
    return result;
}
Popup popup(const Presentation& owner, std::uint64_t instance = 1, std::uint64_t revision = 1) {
    Popup result;
    result.token = {owner.identity.generation, owner.identity.epoch, instance, revision};
    result.anchor = {20, 60, 100, 24};
    auto group = item(10, "Group", false); group.kind = PopupItemKind::group_label;
    auto selected = item(11, "Duplicate"); selected.selected = true;
    auto separator = item(13, "", false); separator.kind = PopupItemKind::separator;
    result.items = {group, selected, item(12, "Duplicate", false), separator, item(14, "Duplicate")};
    result.selected = 11;
    return result;
}
KeyTransition key(std::string value = "a", std::string code = "KeyA", KeyPhase phase = KeyPhase::down) {
    KeyTransition result;
    result.key = std::move(value); result.code = std::move(code); result.phase = phase;
    return result;
}
CompositionEdit composition(CompositionOperation operation, std::uint64_t transaction,
                            std::uint64_t revision = 1, std::string text = {}, ByteRange selection = {}) {
    return {operation, transaction, revision, std::move(text), selection, std::nullopt};
}
MouseTransition mouse(MousePhase phase = MousePhase::move, std::uint64_t token = 0,
                      unsigned button = 0, unsigned buttons = 0, double x = 25.5, double y = 60.25) {
    MouseTransition result;
    result.phase = phase; result.capture_token = token; result.button = button; result.buttons = buttons;
    result.x = x; result.y = y;
    return result;
}
struct Observation {
    std::optional<Presentation> accepted;
    bool focused, active;
    std::optional<std::uint64_t> composition;
    std::uint64_t sequence;
    bool operator==(const Observation&) const = default;
};
Observation observe(const Policy& policy) {
    return {policy.accepted() ? std::optional<Presentation>{*policy.accepted()} : std::nullopt,
            policy.focused(), policy.active(), policy.composition(), policy.last_sequence()};
}
CommitResult publish(Policy& policy, const Presentation& view) {
    auto prepared = policy.prepare(view);
    expect(prepared.status, Status::ok, "Valid presentation preparation");
    check(bool(prepared.prepared), "Successful preparation has no token");
    auto committed = policy.commit(std::move(prepared.prepared), view.identity.presentation_revision);
    expect(committed.status, Status::ok, "Valid publication commit");
    check(!prepared.prepared, "Committed token remained live");
    return committed;
}
struct Fixture {
    Policy policy;
    std::uint64_t next = 1;
    explicit Fixture(Capabilities caps = capabilities(), Presentation view = presentation(), bool focus = true)
        : policy(std::move(caps), generation) {
        publish(policy, view);
        if (focus) accepted(FocusChange{true, true, FocusCause::direct});
    }
    Presentation current() const { return *policy.accepted(); }
    Event event(Input input) { return {policy.accepted()->identity, next++, std::move(input)}; }
    AcceptedEvent accepted(Input input) {
        auto result = policy.accept(event(std::move(input)));
        expect(result.status, Status::ok, "Valid surface event");
        check(result.accepted.has_value(), "Accepted status has no owned event");
        return std::move(*result.accepted);
    }
    void rejected(Input input, Status wanted) {
        const auto before = observe(policy);
        auto result = policy.accept(event(std::move(input)));
        expect(result.status, wanted, "Rejected surface event");
        check(!result.accepted, "Rejected event returned dispatchable work");
        check(observe(policy) == before, "Rejected event changed accepted state");
    }
    void rejected_presentation(const Presentation& view, Status wanted) {
        const auto before = observe(policy);
        auto result = policy.prepare(view);
        expect(result.status, wanted, "Rejected presentation");
        check(!result.prepared, "Rejected presentation returned a token");
        check(observe(policy) == before, "Rejected preparation changed accepted state");
    }
};

void capability_and_text_contract() {
    Capabilities absent;
    check(absent.supported == 0, "Default capabilities claim physical support");
    expect(validate_capabilities(absent), Status::ok, "Default capability shape");
    check(absent.mouse_input_version == 0, "Default capabilities select the optional mouse reader");
    expect(negotiate(absent, feature(Feature::raw_keys)), Status::unsupported, "Missing capability");
    auto caps = capabilities();
    expect(negotiate(caps, known_features), Status::ok, "All explicitly supplied fake capabilities");
    expect(negotiate(caps, 1ull << 63), Status::unsupported, "Unknown required capability");
    auto unknown = caps; unknown.supported |= 1ull << 63;
    expect(validate_capabilities(unknown), Status::unsupported, "Unknown supported capability");
    auto version = caps; ++version.version;
    expect(validate_capabilities(version), Status::unsupported, "Unknown protocol version");
    invalid_argument([&] { Policy invalid(caps, 0); }, "Zero session generation accepted");
    invalid_argument([&] { Policy invalid(version, generation); }, "Invalid capabilities constructed a policy");
    auto missing_mouse_version = caps; missing_mouse_version.mouse_input_version = 0;
    expect(validate_capabilities(missing_mouse_version), Status::unsupported, "Mouse bit without its version accepted");
    auto unknown_mouse_version = caps; ++unknown_mouse_version.mouse_input_version;
    expect(validate_capabilities(unknown_mouse_version), Status::unsupported, "Unknown mouse version accepted");
    auto unselected_mouse = caps; unselected_mouse.supported &= ~feature(Feature::mouse_input);
    expect(validate_capabilities(unselected_mouse), Status::unsupported, "Mouse version without its bit accepted");
    unselected_mouse.mouse_input_version = 0;
    expect(validate_capabilities(unselected_mouse), Status::ok, "Original capability vocabulary rejected");
    expect(negotiate(unselected_mouse, feature(Feature::mouse_input)), Status::unsupported, "Mouse feature inferred from legacy pointer support");
    static_assert(feature(Feature::raw_pointer) == 64 && feature(Feature::mouse_input) == 8192);
    static_assert(mouse_button_bit(0) == 1 && mouse_button_bit(1) == 4 && mouse_button_bit(2) == 2 &&
                  mouse_button_bit(3) == 8 && mouse_button_bit(4) == 16 && mouse_button_bit(5) == 0);
    static_assert(static_cast<unsigned>(MousePhase::cancel) == 4 && static_cast<unsigned>(MousePhase::wheel) == 3);

    constexpr std::array<std::size_t Limits::*, 6> fields{
        &Limits::text_bytes, &Limits::clipboard_bytes, &Limits::popup_items,
        &Limits::popup_text_bytes, &Limits::capture_rules, &Limits::held_keys};
    for (auto field : fields) {
        auto bounded = caps;
        expect(validate_capabilities(bounded), Status::ok, "Hard ceiling must be usable");
        bounded.limits.*field = 0;
        expect(validate_capabilities(bounded), Status::limit_exceeded, "Zero negotiated limit accepted");
        bounded = caps; ++(bounded.limits.*field);
        expect(validate_capabilities(bounded), Status::limit_exceeded, "Negotiated limit exceeded hard ceiling");
        invalid_argument([&] { Policy invalid(bounded, generation); }, "Over-ceiling capabilities constructed a policy");
    }
    auto depth = caps; depth.limits.popup_depth = 0;
    expect(validate_capabilities(depth), Status::limit_exceeded, "Zero popup depth accepted");
    depth.limits.popup_depth = caps.limits.popup_depth + 1;
    expect(validate_capabilities(depth), Status::limit_exceeded, "Popup depth exceeded hard ceiling");
    invalid_argument([&] { Policy invalid(depth, generation); }, "Over-ceiling popup depth constructed a policy");

    const auto text = unicode_text();
    check(text.size() == 11 && valid_text(text), "Unicode fixture is not valid UTF-8");
    for (std::size_t boundary : {0u, 1u, 3u, 7u, 8u, 10u, 11u})
        check(text_boundary(text, boundary), "Valid scalar byte boundary rejected");
    for (std::size_t middle : {2u, 4u, 5u, 6u, 9u, 12u})
        check(!text_boundary(text, middle), "Interior or out-of-bounds byte accepted");
    check(valid_range(text, {8, 10}), "Codepoint-only contract incorrectly claims grapheme validation");
    check(!valid_range(text, {7, 3}) && !valid_range(text, {0, std::numeric_limits<std::size_t>::max()}),
          "Reversed/overflowing byte range accepted");
    const std::string joined = "\xf0\x9f\x91\xa9\xe2\x80\x8d\xf0\x9f\x92\xbb";
    check(valid_range(joined, {4, 7}), "ZWJ scalar boundary was treated as a promised grapheme boundary");
    const std::array<std::string, 8> invalid{
        std::string("\0", 1), "\x80", "\xc0\x80", "\xe2\x82", "\xed\xa0\x80",
        "\xf4\x90\x80\x80", "\xf5\x80\x80\x80", "\xc3("};
    for (const auto& bad : invalid)
        check(!valid_text(bad) && !text_boundary(bad, 0) && !valid_range(bad, {0, 0}), "Malformed UTF-8 accepted");
    check(valid_text("") && valid_range("", {0, 0}), "Empty scalar text/range rejected");
}

void preparation_transactions() {
    Fixture fixture;
    auto& policy = fixture.policy;
    const auto original = fixture.current();
    auto candidate = original; ++candidate.identity.presentation_revision; ++candidate.identity.context;
    {
        auto staged = policy.prepare(candidate);
        expect(staged.status, Status::ok, "Prepare successor");
        check(fixture.current() == original, "Preparation exposed successor before publication");
        auto busy = policy.prepare(candidate);
        expect(busy.status, Status::busy, "Multiple outstanding preparations accepted");
        auto premature = policy.accept({candidate.identity, fixture.next++, SelectionChange{1, {1, 3}, true}});
        expect(premature.status, Status::stale_identity, "Uncommitted context accepted input");
        check(fixture.current() == original, "Premature event changed accepted presentation");
    }
    auto retry = policy.prepare(candidate);
    expect(retry.status, Status::ok, "Abandoned preparation remained busy");
    auto moved = std::move(retry.prepared);
    check(!retry.prepared && moved, "Move did not transfer preparation ownership");
    auto wrong = policy.commit(std::move(moved), candidate.identity.presentation_revision + 1);
    expect(wrong.status, Status::stale_revision, "Wrong published revision committed");
    check(!moved && fixture.current() == original, "Failed commit changed accepted state or retained token");

    auto inert = policy.prepare(candidate);
    expect(inert.status, Status::ok, "Retry after rejected publication");
    const auto owned_candidate = candidate;
    candidate.identity.owner.id = "caller-mutated";
    candidate.editor->surrounding = "caller-mutated";
    auto installed = policy.commit(std::move(inert.prepared), owned_candidate.identity.presentation_revision);
    expect(installed.status, Status::ok, "Install copied successor");
    check(fixture.current() == owned_candidate, "Preparation borrowed caller-owned data");
    expect(policy.commit(std::move(inert.prepared), owned_candidate.identity.presentation_revision).status,
           Status::stale_preparation, "Duplicate commit accepted");

    auto later = fixture.current(); ++later.identity.presentation_revision;
    auto stale = policy.prepare(later);
    expect(stale.status, Status::ok, "Prepare before input");
    fixture.accepted(SelectionChange{1, {1, 3}, true});
    check(!stale.prepared, "Accepted input did not invalidate preparation");
    expect(policy.commit(std::move(stale.prepared), later.identity.presentation_revision).status,
           Status::stale_preparation, "Input-raced publication committed");
    publish(policy, later);

    Policy foreign(capabilities(), generation);
    auto foreign_candidate = later; ++foreign_candidate.identity.presentation_revision;
    auto token = policy.prepare(foreign_candidate);
    expect(token.status, Status::ok, "Prepare foreign-token fixture");
    expect(foreign.commit(std::move(token.prepared), foreign_candidate.identity.presentation_revision).status,
           Status::stale_preparation, "Foreign policy accepted token");
    check(fixture.current() == later && !foreign.accepted(), "Foreign token mutated either accepted presentation");
    publish(policy, foreign_candidate);

    PreparedPresentation orphan;
    {
        Policy temporary(capabilities(), generation);
        auto stage = temporary.prepare(presentation());
        expect(stage.status, Status::ok, "Prepare token lifetime fixture");
        orphan = std::move(stage.prepared);
    }
    check(!orphan, "Token outlived closed owner as live preparation");
    orphan = PreparedPresentation{};
}

void identities_capture_and_keys() {
    Fixture fixture;
    const auto before = observe(fixture.policy);
    for (unsigned field = 0; field != 6; ++field) {
        auto identity = fixture.current().identity;
        if (field == 0) identity.owner.id = "another";
        if (field == 1) ++identity.owner.generation;
        if (field == 2) ++identity.presentation_revision;
        if (field == 3) ++identity.generation;
        if (field == 4) ++identity.epoch;
        if (field == 5) ++identity.context;
        auto rejected = fixture.policy.accept({identity, fixture.next++, SelectionChange{1, {1, 3}, false}});
        expect(rejected.status, Status::stale_identity, "Independently stale identity accepted");
        check(!rejected.accepted && observe(fixture.policy) == before, "Stale identity consumed work/state");
    }
    auto selected = fixture.accepted(SelectionChange{1, {1, 3}, true});
    check(std::get<SelectionChange>(selected.event.input).backward, "Selection direction was lost");

    KeyCapturePolicy capture;
    capture.fallback = Capture::capture;
    capture.rules = {{"z", "KeyZ", control, shift, true, false, Capture::pass},
                     {"", "", 0, 0, true, true, Capture::capture}};
    auto stroke = key("z", "KeyZ"); stroke.modifiers = control;
    check(capture_key(capture, stroke) == Capture::pass, "First matching capture rule did not win");
    stroke.modifiers |= shift;
    check(capture_key(capture, stroke) == Capture::capture, "Forbidden modifier was ignored");
    stroke.phase = KeyPhase::up; stroke.modifiers = control;
    check(capture_key(capture, stroke) == Capture::capture, "Phase-limited capture rule matched key-up");
    for (unsigned bad = 0; bad != 4; ++bad) {
        auto malformed = capture;
        auto& rule = malformed.rules.back();
        if (bad == 0) rule.disposition = static_cast<Capture>(99);
        if (bad == 1) rule.required_modifiers = rule.forbidden_modifiers = control;
        if (bad == 2) rule.required_modifiers = 1u << 31;
        if (bad == 3) rule.down = rule.up = false;
        check(capture_key(malformed, key()) == Capture::pass, "Malformed standalone capture policy captured input");
    }
    auto updated = fixture.current(); ++updated.identity.presentation_revision;
    updated.keys.fallback = Capture::capture;
    publish(fixture.policy, updated);
    auto down = key(" ", "Space"); down.location = 3; down.modifiers = meta | alt_graph;
    auto owned = fixture.accepted(down);
    check(std::holds_alternative<KeyTransition>(owned.event.input) && owned.capture == Capture::capture &&
          std::get<KeyTransition>(owned.event.input) == down, "Physical key was flattened or lost metadata");
    fixture.rejected(down, Status::duplicate);
    auto repeat = down; repeat.repeat = true;
    fixture.accepted(repeat);
    auto up = down; up.phase = KeyPhase::up; up.repeat = true;
    fixture.rejected(up, Status::invalid_value);
    up.repeat = false; up.key = "Space";
    fixture.accepted(up);
    fixture.rejected(up, Status::duplicate);
    fixture.rejected(repeat, Status::invalid_transaction);
    auto invalid = key(); invalid.modifiers = 1u << 31;
    fixture.rejected(invalid, Status::invalid_value);

    auto no_keys = capabilities(); no_keys.supported &= ~feature(Feature::raw_keys);
    Fixture unsupported(no_keys);
    unsupported.rejected(key(), Status::unsupported);
    auto required = unsupported.current(); ++required.identity.presentation_revision;
    required.required = feature(Feature::raw_keys);
    unsupported.rejected_presentation(required, Status::unsupported);
    required.required = 0; required.keys.fallback = Capture::capture;
    unsupported.rejected_presentation(required, Status::unsupported);
}

void text_and_composition_transactions() {
    Fixture text;
    text.rejected(TextCommit{1, 1, "x", ByteRange{2, 3}}, Status::invalid_value);
    text.rejected(SelectionChange{1, {1, 2}, true}, Status::invalid_value);
    auto insertion = text.accepted(TextCommit{1, 1, "\xc3\xa9", ByteRange{1, 3}});
    check(std::get<TextCommit>(insertion.event.input).text == "\xc3\xa9", "Committed UTF-8 text changed");
    text.rejected(TextCommit{1, 1, "again", std::nullopt}, Status::duplicate);
    text.accepted(TextCommit{2, 1, "", ByteRange{1, 3}});
    text.rejected(TextCommit{3, 1, "", ByteRange{3, 3}}, Status::invalid_value);
    text.accepted(SelectionChange{1, {8, 10}, true});
    auto changed = text.current(); ++changed.identity.presentation_revision;
    changed.editor->surrounding = "native edit"; changed.editor->selection = {0, 0};
    text.rejected_presentation(changed, Status::stale_revision);
    ++changed.editor->revision; publish(text.policy, changed);
    text.rejected(TextCommit{3, 1, "old context", std::nullopt}, Status::stale_revision);
    text.accepted(TextCommit{3, 2, "current", std::nullopt});

    Fixture ime;
    auto begin = composition(CompositionOperation::begin, 11, 1, "\xc3\xa9", {0, 2});
    begin.replacement = ByteRange{1, 7};
    ime.accepted(begin);
    check(ime.policy.composition() == 11, "Composition begin did not retain transaction");
    ime.rejected(composition(CompositionOperation::begin, 12), Status::invalid_transaction);
    ime.rejected(composition(CompositionOperation::update, 12), Status::invalid_transaction);
    ime.rejected(composition(CompositionOperation::update, 11, 1, "\xc3\xa9", {1, 2}), Status::invalid_value);
    ime.rejected(TextCommit{12, 1, "duplicate platform input", std::nullopt}, Status::invalid_transaction);
    ime.accepted(composition(CompositionOperation::update, 11, 1, "\xf0\x9f\x94\x92", {0, 4}));
    auto attested = ime.current(); ++attested.identity.presentation_revision;
    ++attested.editor->revision; attested.editor->composition_transaction = 11;
    auto retained = publish(ime.policy, attested);
    check(!retained.revoked.composition && ime.policy.composition() == 11, "Native composition attestation was discarded");
    auto readonly = ime.current(); ++readonly.identity.presentation_revision;
    ++readonly.editor->revision; readonly.editor->editable = false;
    ime.rejected_presentation(readonly, Status::invalid_value);
    readonly.editor->composition_transaction = 0;
    auto revoked = publish(ime.policy, readonly);
    check(revoked.revoked.composition == 11 && !ime.policy.composition(), "Readonly transition did not revoke composition");
    ime.rejected(composition(CompositionOperation::commit, 11, 3, "late", {0, 4}), Status::unavailable);
    auto editable = ime.current(); ++editable.identity.presentation_revision; ++editable.editor->revision;
    editable.editor->editable = true; publish(ime.policy, editable);
    ime.rejected(composition(CompositionOperation::begin, 11, 4), Status::duplicate);
    ime.accepted(composition(CompositionOperation::begin, 12, 4));
    auto absent = ime.current(); ++absent.identity.presentation_revision;
    auto absent_result = publish(ime.policy, absent);
    check(absent_result.revoked.composition == 12 && !ime.policy.composition(), "Absent native composition did not revoke pending preedit");
    ime.rejected(composition(CompositionOperation::commit, 12, 4), Status::duplicate);
    ime.accepted(composition(CompositionOperation::begin, 13, 4));
    ime.rejected(composition(CompositionOperation::cancel, 13, 4, "not empty", {0, 0}), Status::invalid_value);
    ime.accepted(composition(CompositionOperation::commit, 13, 4, "\xc3\xa9", {2, 2}));
    check(!ime.policy.composition(), "Commit left composition active");
    ime.rejected(composition(CompositionOperation::commit, 13, 4, "\xc3\xa9", {2, 2}), Status::duplicate);
    ime.rejected(TextCommit{13, 4, "same platform commit", std::nullopt}, Status::duplicate);
    ime.accepted(composition(CompositionOperation::begin, 14, 4));
    ime.accepted(composition(CompositionOperation::cancel, 14, 4));
    check(!ime.policy.composition(), "Cancel left composition active");
    ime.rejected(composition(CompositionOperation::update, 14, 4), Status::duplicate);

    Fixture unknown;
    auto false_attestation = unknown.current(); ++false_attestation.identity.presentation_revision;
    ++false_attestation.editor->revision; false_attestation.editor->composition_transaction = 99;
    unknown.rejected_presentation(false_attestation, Status::invalid_transaction);
    unknown.accepted(composition(CompositionOperation::begin, 1));
    auto replacement = unknown.current(); ++replacement.identity.presentation_revision; ++replacement.identity.context;
    auto retired = publish(unknown.policy, replacement);
    check(retired.revoked.composition == 1, "Context replacement lost composition cleanup");
    unknown.rejected(composition(CompositionOperation::update, 1), Status::invalid_transaction);
}

void popup_lifetimes_and_focus() {
    Fixture fixture;
    fixture.accepted(key());
    auto opened = fixture.current(); ++opened.identity.presentation_revision; opened.popup = popup(opened);
    auto preparation = fixture.policy.prepare(opened);
    expect(preparation.status, Status::ok, "Prepare automatic surface popup");
    check(!fixture.current().popup, "Prepared popup became active before commit");
    auto commit = fixture.policy.commit(std::move(preparation.prepared), opened.identity.presentation_revision);
    expect(commit.status, Status::ok, "Open automatic surface popup");
    check(commit.revoked.held_keys.size() == 1 && commit.revoked.held_keys[0].code == "KeyA",
          "Opening popup stranded engine-held opener key");
    fixture.rejected(key("a", "KeyA", KeyPhase::up), Status::popup_active);
    fixture.rejected(TextCommit{1, 1, "background", std::nullopt}, Status::popup_active);
    fixture.accepted(FocusChange{false, false, FocusCause::owned_popup});
    check(fixture.policy.focused() && fixture.policy.active(), "Owned popup focus blurred its document");
    const auto first = opened.popup->token;
    for (PopupItemId id : {10u, 12u, 13u, 999u})
        fixture.rejected(PopupReply{first, PopupOperation::accept, id}, Status::unavailable);
    auto chosen = fixture.accepted(PopupReply{first, PopupOperation::accept, 14});
    check(std::get<PopupReply>(chosen.event.input).item == 14 && !fixture.current().popup,
          "Popup acceptance rebound duplicate labels or failed to consume invocation");
    fixture.accepted(key());
    fixture.accepted(key("a", "KeyA", KeyPhase::up));
    fixture.rejected(PopupReply{first, PopupOperation::cancel, std::nullopt}, Status::stale_identity);
    auto resurrected = fixture.current(); ++resurrected.identity.presentation_revision;
    resurrected.popup = popup(resurrected, first.instance);
    fixture.rejected_presentation(resurrected, Status::stale_identity);

    auto second = fixture.current(); ++second.identity.presentation_revision; second.popup = popup(second, 2);
    publish(fixture.policy, second);
    auto unchanged = fixture.current(); ++unchanged.identity.presentation_revision;
    auto preserved = publish(fixture.policy, unchanged);
    check(!preserved.revoked.popup && fixture.current().popup->token == second.popup->token,
          "Unrelated presentation replaced unchanged live popup");
    auto changed = fixture.current(); ++changed.identity.presentation_revision;
    std::swap(changed.popup->items[1], changed.popup->items[4]);
    fixture.rejected_presentation(changed, Status::stale_revision);
    ++changed.popup->token.revision;
    publish(fixture.policy, changed);
    fixture.rejected(PopupReply{second.popup->token, PopupOperation::accept, 11}, Status::stale_identity);
    auto cancelled = fixture.accepted(PopupReply{changed.popup->token, PopupOperation::cancel, std::nullopt});
    check(std::get<PopupReply>(cancelled.event.input).operation == PopupOperation::cancel && !fixture.current().popup,
          "User cancellation did not consume popup");

    // Engine dispatch happens after accept returned. A callback may publish a
    // successor without old completion cleanup closing that successor.
    auto successor = fixture.current(); ++successor.identity.presentation_revision; successor.popup = popup(successor, 3);
    publish(fixture.policy, successor);
    fixture.rejected(PopupReply{changed.popup->token, PopupOperation::cancel, std::nullopt}, Status::stale_identity);
    check(fixture.current().popup->token == successor.popup->token, "Old cancellation affected callback-created successor");
    auto withdrawn = fixture.current(); ++withdrawn.identity.presentation_revision; withdrawn.popup.reset();
    const auto before_sequence = fixture.policy.last_sequence();
    auto withdrawal = publish(fixture.policy, withdrawn);
    check(withdrawal.revoked.popup == successor.popup->token && fixture.policy.last_sequence() == before_sequence,
          "Programmatic withdrawal fabricated input or lost cleanup");
    fixture.rejected(PopupReply{successor.popup->token, PopupOperation::accept, 11}, Status::stale_identity);

    auto external = fixture.current(); ++external.identity.presentation_revision; external.popup = popup(external, 4);
    publish(fixture.policy, external);
    auto loss = fixture.accepted(FocusChange{false, false, FocusCause::external});
    check(loss.revoked.popup == external.popup->token && loss.revoked.reason == RevocationReason::focus_loss &&
          !fixture.policy.focused() && !fixture.policy.active() && !fixture.current().popup,
          "External deactivation did not revoke popup ownership");
    fixture.accepted(FocusChange{true, true, FocusCause::direct});
    fixture.accepted(composition(CompositionOperation::begin, 1));
    auto service = fixture.accepted(FocusChange{false, true, FocusCause::owned_service});
    check(service.revoked.composition == 1 && service.revoked.reason == RevocationReason::service && !fixture.policy.composition(),
          "Owned service did not cancel composition");

    Fixture nested;
    auto menu = nested.current(); ++menu.identity.presentation_revision; menu.popup = popup(menu);
    menu.popup->kind = PopupKind::action_menu; menu.popup->selected.reset();
    auto parent = item(20, "Submenu", false); parent.kind = PopupItemKind::submenu;
    parent.children = {item(21, "Action")}; menu.popup->items = {parent};
    publish(nested.policy, menu);
    nested.rejected(PopupReply{menu.popup->token, PopupOperation::accept, 21}, Status::unavailable);
    auto enabled = nested.current(); ++enabled.identity.presentation_revision; ++enabled.popup->token.revision;
    enabled.popup->items[0].enabled = true; publish(nested.policy, enabled);
    nested.accepted(PopupReply{enabled.popup->token, PopupOperation::accept, 21});
    auto duplicate = nested.current(); ++duplicate.identity.presentation_revision; duplicate.popup = popup(duplicate, 2);
    duplicate.popup->items.back().id = duplicate.popup->items[1].id;
    nested.rejected_presentation(duplicate, Status::invalid_value);
}

void clipboard_pointer_and_owned_results() {
    Fixture fixture;
    auto view = fixture.current(); ++view.identity.presentation_revision;
    view.clipboard = ClipboardOffer{1, 1, {{"text/plain", "selection"}, {"text/html", "<b>selection</b>"}}};
    publish(fixture.policy, view);
    auto copy = fixture.accepted(ClipboardInput{ClipboardOperation::copy, 1, 1, 1, TransferStatus::accepted, {}});
    check(!copy.permits_cut() && fixture.current().clipboard, "Copy authorized cut or consumed its offer");
    auto failed = fixture.accepted(ClipboardInput{ClipboardOperation::cut, 2, 1, 1, TransferStatus::error, {}});
    check(!failed.permits_cut() && fixture.current().clipboard, "Failed write authorized destructive cut");
    auto cut = fixture.accepted(ClipboardInput{ClipboardOperation::cut, 3, 1, 1, TransferStatus::accepted, {}});
    check(cut.permits_cut() && !fixture.current().clipboard, "Accepted cut did not consume offer");
    fixture.rejected(ClipboardInput{ClipboardOperation::cut, 3, 1, 1, TransferStatus::accepted, {}}, Status::duplicate);
    auto old_offer = fixture.current(); ++old_offer.identity.presentation_revision; old_offer.clipboard = view.clipboard;
    fixture.rejected_presentation(old_offer, Status::stale_identity);
    old_offer.clipboard->id = 2; publish(fixture.policy, old_offer);
    fixture.rejected(ClipboardInput{ClipboardOperation::copy, 4, 2, 2, TransferStatus::accepted, {}}, Status::stale_revision);
    fixture.rejected(ClipboardInput{ClipboardOperation::paste, 4, 0, 1, TransferStatus::accepted,
        {{"text/plain", "x"}, {"text/plain", "y"}}}, Status::invalid_value);
    fixture.rejected(ClipboardInput{ClipboardOperation::paste, 4, 0, 1, TransferStatus::accepted,
        {{"application/javascript", "text"}}}, Status::unsupported);
    auto pasted = fixture.accepted(ClipboardInput{ClipboardOperation::paste, 4, 0, 1, TransferStatus::accepted,
        {{"text/plain", "\xc3\xa9"}, {"text/html", "<b>data</b>"}}});
    check(!pasted.permits_cut() && std::get<ClipboardInput>(pasted.event.input).formats[1].text == "<b>data</b>",
          "Paste was mislabeled as a cut or flattened rich data");
    fixture.accepted(ClipboardInput{ClipboardOperation::paste, 5, 0, 1, TransferStatus::unavailable, {}});
    fixture.rejected(ClipboardInput{ClipboardOperation::paste, 6, 0, 1, TransferStatus::accepted, {}}, Status::invalid_value);

    PointerTransition pointer;
    pointer.phase = PointerPhase::down; pointer.pointer = 9; pointer.button = 2; pointer.buttons = 4;
    pointer.x = 21.25; pointer.y = 60.5; pointer.modifiers = meta | alt_graph;
    auto raw = fixture.accepted(pointer);
    check(std::get<PointerTransition>(raw.event.input) == pointer, "Raw pointer metadata changed");
    auto bad = pointer; bad.pointer = 0; fixture.rejected(bad, Status::invalid_value);
    bad = pointer; bad.wheel_y = 1; fixture.rejected(bad, Status::invalid_value);
    bad = pointer; bad.x = std::numeric_limits<double>::infinity(); fixture.rejected(bad, Status::invalid_value);
    bad = pointer; bad.phase = PointerPhase::wheel; bad.pointer = 0; bad.wheel_x = -2; bad.wheel_y = 3;
    fixture.accepted(bad);
    fixture.accepted(FocusChange{false, true, FocusCause::direct});
    fixture.accepted(PointerTransition{}); // Hover does not require editor focus.
    fixture.rejected(TextCommit{1, 1, "no focus", std::nullopt}, Status::not_focused);

    Fixture owned;
    auto source = owned.event(TextCommit{1, 1, "owned bytes", std::nullopt});
    auto result = owned.policy.accept(source);
    expect(result.status, Status::ok, "Accept owned dispatch result");
    source.identity.owner.id = "mutated"; std::get<TextCommit>(source.input).text = "mutated";
    check(result.accepted && std::get<TextCommit>(result.accepted->event.input).text == "owned bytes",
          "Accepted event borrowed caller storage");
    unsigned effects = 0;
    try { ++effects; throw std::runtime_error("engine dispatch failed after an effect"); }
    catch (const std::runtime_error&) {}
    const auto duplicate = owned.policy.accept(result.accepted->event);
    expect(duplicate.status, Status::duplicate, "Throw after accepted dispatch made input replayable");
    check(!duplicate.accepted && effects == 1, "Duplicate returned work after unknown engine outcome");
}

void mouse_values_chords_context_and_exhaustion() {
    constexpr std::uint64_t token = (std::uint64_t{1} << 63) + 17;
    Fixture fixture;
    fixture.accepted(mouse());
    auto press = mouse(MousePhase::down, token, 2, 2);
    press.modifiers = shift | alt_graph;
    auto owned = fixture.accepted(press);
    check(std::get<MouseTransition>(owned.event.input) == press, "Mouse fields or high u64 token changed");
    auto wrong = mouse(MousePhase::down, token + 1, 1, 6);
    fixture.rejected(wrong, Status::invalid_transaction);
    wrong.capture_token = token; wrong.buttons = 4;
    fixture.rejected(wrong, Status::invalid_value);
    fixture.accepted(mouse(MousePhase::down, token, 1, 6));
    fixture.accepted(mouse(MousePhase::down, token, 0, 7));
    fixture.accepted(mouse(MousePhase::down, token, 3, 15));
    fixture.accepted(mouse(MousePhase::down, token, 4, 31));
    fixture.rejected(mouse(), Status::invalid_transaction);
    fixture.rejected(mouse(MousePhase::down, token, 2, 31), Status::invalid_value);
    fixture.rejected(mouse(MousePhase::up, token + 1, 2, 29), Status::invalid_transaction);
    fixture.rejected(mouse(MousePhase::up, token, 2, 30), Status::invalid_value);
    fixture.accepted(mouse(MousePhase::move, token, 0, 31, -100, 900)); // Captured moves may leave the clip.
    auto wheel = mouse(MousePhase::wheel, token, 0, 31);
    wheel.wheel_x = -1.5; wheel.wheel_y = 2.25;
    fixture.accepted(wheel);
    auto context = mouse(MousePhase::context, token, 0, 31, 34.25, 71.5);
    context.modifiers = meta;
    fixture.accepted(context);
    auto keyboard = mouse(MousePhase::context, token, 0, 31, 0, 0);
    keyboard.context_origin = ContextOrigin::keyboard;
    const auto accepted_keyboard = fixture.accepted(keyboard);
    check(std::get<MouseTransition>(accepted_keyboard.event.input) == keyboard,
          "Keyboard context invented physical point/modifiers or changed held capture");
    auto invalid_keyboard = keyboard; invalid_keyboard.x = 1;
    fixture.rejected(invalid_keyboard, Status::invalid_value);
    invalid_keyboard = keyboard; invalid_keyboard.modifiers = shift;
    fixture.rejected(invalid_keyboard, Status::invalid_value);
    auto dropped_context = context; dropped_context.capture_token = 0; dropped_context.buttons = 0;
    fixture.rejected(dropped_context, Status::invalid_transaction);
    // Context and wheel preserve every chord edge, including the full u64 token.
    unsigned buttons = 31;
    for (unsigned button : {2u, 1u, 0u, 3u, 4u}) {
        buttons &= ~mouse_button_bit(button);
        auto release = mouse(MousePhase::up, token, button, buttons);
        release.clicks = button % 4;
        fixture.accepted(release);
        if (buttons) fixture.accepted(mouse(MousePhase::move, token, 0, buttons));
    }
    fixture.accepted(mouse());
    fixture.rejected(mouse(MousePhase::down, token, 0, 1), Status::duplicate);
    fixture.accepted(mouse(MousePhase::down, token + 1, 0, 1));
    auto cancel = mouse(MousePhase::cancel, token + 1, 0, 0, 0, 0);
    auto invalid_cancel = cancel; invalid_cancel.buttons = 1;
    fixture.rejected(invalid_cancel, Status::invalid_value);
    invalid_cancel = cancel; invalid_cancel.capture_token = token;
    fixture.rejected(invalid_cancel, Status::invalid_transaction);
    invalid_cancel = cancel; invalid_cancel.y = 1;
    fixture.rejected(invalid_cancel, Status::invalid_value);
    const auto accepted_cancel = fixture.accepted(cancel);
    check(std::get<MouseTransition>(accepted_cancel.event.input) == cancel,
          "Canonical cancel was rewritten as an up or a physical point");
    fixture.rejected(cancel, Status::invalid_transaction);
    fixture.rejected(mouse(MousePhase::down, token + 1, 0, 1), Status::duplicate);
    fixture.accepted(mouse(MousePhase::down, maximum, 4, 16));
    fixture.accepted(mouse(MousePhase::down, maximum, 3, 24));
    fixture.accepted(mouse(MousePhase::up, maximum, 4, 8));
    fixture.accepted(mouse(MousePhase::cancel, maximum, 0, 0, 0, 0));
    fixture.rejected(mouse(MousePhase::down, 1, 0, 1), Status::duplicate);
    fixture.rejected(mouse(MousePhase::down, maximum, 0, 1), Status::duplicate);
    fixture.accepted(mouse()); // Exhaustion affects fresh capture, not idle input.
    Policy fresh(capabilities(), generation + 1);
    auto fresh_view = presentation(); fresh_view.identity.generation = generation + 1;
    publish(fresh, fresh_view);
    expect(fresh.accept({fresh_view.identity, 1, mouse(MousePhase::down, 1, 0, 1)}).status,
           Status::ok, "Fresh Policy could not restart exhausted mouse-token stream");
}

void mouse_validation_and_legacy_pointer_contract() {
    auto legacy = capabilities(); legacy.supported &= ~feature(Feature::mouse_input); legacy.mouse_input_version = 0;
    Fixture old(legacy);
    old.rejected(mouse(), Status::unsupported);
    PointerTransition pointer;
    pointer.phase = PointerPhase::down; pointer.pointer = maximum; pointer.button = 4; pointer.buttons = 16;
    old.accepted(pointer);
    pointer.phase = PointerPhase::context; pointer.pointer = 0; pointer.buttons = 0; pointer.clicks = 3;
    old.accepted(pointer); // Original pointer context remains permissive and stateless.
    pointer.phase = PointerPhase::up; pointer.pointer = 1; pointer.buttons = 7;
    old.accepted(pointer); // Mouse chord rules must not narrow the old pointer vocabulary.

    Fixture fixture(capabilities(), presentation(), false);
    fixture.accepted(mouse()); // Mouse input requires activity, not editor focus.
    auto wheel = mouse(MousePhase::wheel); wheel.wheel_y = 0.5;
    fixture.accepted(wheel);
    auto invalid = wheel; invalid.wheel_y = 0;
    fixture.rejected(invalid, Status::invalid_value);
    invalid = wheel; invalid.wheel_y = 0.1;
    fixture.rejected(invalid, Status::invalid_value);
    wheel.wheel_y = static_cast<double>(static_cast<float>(0.1));
    fixture.accepted(wheel);
    for (unsigned failure = 0; failure != 13; ++failure) {
        auto malformed = mouse();
        if (failure == 0) malformed.x = std::numeric_limits<double>::infinity();
        if (failure == 1) malformed.y = std::numeric_limits<double>::quiet_NaN();
        if (failure == 2) malformed.x = 1000001;
        if (failure == 3) malformed.wheel_x = 1;
        if (failure == 4) malformed.button = 1;
        if (failure == 5) malformed.buttons = 32;
        if (failure == 6) malformed.clicks = 1;
        if (failure == 7) malformed.modifiers = 32;
        if (failure == 8) malformed.phase = static_cast<MousePhase>(9);
        if (failure == 9) malformed.context_origin = static_cast<ContextOrigin>(2);
        if (failure == 10) malformed.context_origin = ContextOrigin::keyboard;
        if (failure == 11) { malformed.phase = MousePhase::down; malformed.capture_token = 1; malformed.buttons = 1; malformed.clicks = 4; }
        if (failure == 12) { malformed.phase = MousePhase::down; malformed.buttons = 1; }
        fixture.rejected(malformed, Status::invalid_value);
    }
    auto unknown = mouse(); ++unknown.version;
    fixture.rejected(unknown, Status::unsupported);
    fixture.accepted(mouse(MousePhase::down, 1, 1, 4));
    fixture.accepted(mouse(MousePhase::up, 1, 1, 0));
    fixture.accepted(FocusChange{false, false, FocusCause::external});
    fixture.rejected(mouse(), Status::not_focused);
}

void mouse_publication_and_lifecycle_retirement() {
    Fixture pixels;
    pixels.accepted(mouse(MousePhase::down, 10, 0, 1));
    auto update = pixels.current(); ++update.identity.presentation_revision;
    const auto unchanged = publish(pixels.policy, update);
    check(!unchanged.revoked.identity, "Pixel-only revision retired mouse capture");
    pixels.accepted(mouse(MousePhase::move, 10, 0, 1));

    for (unsigned change = 0; change != 10; ++change) {
        Fixture fixture;
        fixture.accepted(mouse(MousePhase::down, 10, 0, 1));
        const auto old_identity = fixture.current().identity;
        Revocation revoked;
        if (change < 7) {
            auto next = fixture.current(); ++next.identity.presentation_revision;
            if (change == 0) ++next.identity.context;
            if (change == 1) ++next.identity.epoch;
            if (change == 2) { ++next.identity.owner.generation; ++next.identity.context; }
            if (change == 3) next.bounds.width += 1;
            if (change == 4) next.clip.width -= 1;
            if (change == 5) next.display_scale = 2;
            if (change == 6) next.popup = popup(next);
            auto staged = fixture.policy.prepare(next);
            expect(staged.status, Status::ok, "Prepare mouse retirement");
            allocation_test::fail = true;
            auto committed = fixture.policy.commit(std::move(staged.prepared), next.identity.presentation_revision);
            allocation_test::fail = false;
            expect(committed.status, Status::ok, "Mouse retirement commit allocated or failed");
            revoked = std::move(committed.revoked);
            if (next.popup) fixture.accepted(PopupReply{next.popup->token, PopupOperation::cancel, std::nullopt});
        } else if (change == 7) {
            revoked = fixture.accepted(FocusChange{false, true, FocusCause::owned_service}).revoked;
        } else if (change == 8) {
            revoked = fixture.accepted(FocusChange{false, false, FocusCause::external}).revoked;
        } else {
            auto next = fixture.current(); ++next.identity.presentation_revision; next.available = false;
            revoked = publish(fixture.policy, next).revoked;
            ++next.identity.presentation_revision; next.available = true; publish(fixture.policy, next);
        }
        check(revoked.identity == old_identity && revoked.empty(), "Identity-only mouse retirement lost authority identity or fabricated work");
        fixture.accepted(FocusChange{true, true, FocusCause::direct});
        fixture.rejected(mouse(MousePhase::move, 10, 0, 1), Status::invalid_transaction);
        fixture.rejected(mouse(MousePhase::down, 10, 0, 1), Status::duplicate);
        fixture.accepted(mouse(MousePhase::down, 11, 0, 1));
    }
    Fixture legacy;
    legacy.accepted(mouse(MousePhase::down, 10, 0, 1));
    auto successor = legacy.current(); ++successor.identity.presentation_revision;
    auto retired = legacy.policy.legacy_present(successor.identity.presentation_revision);
    check(retired.revoked.identity && retired.revoked.empty(), "Legacy mouse retirement omitted identity-only cancellation");
    ++successor.identity.context; ++successor.identity.presentation_revision; publish(legacy.policy, successor);
    legacy.rejected(mouse(MousePhase::down, 10, 0, 1), Status::duplicate);
    legacy.accepted(mouse(MousePhase::down, 11, 0, 1));
    const auto closed_identity = legacy.current().identity;
    const auto closed = legacy.policy.close();
    check(closed.identity == closed_identity && closed.empty(), "Close lost identity-only mouse cancellation");
    expect(legacy.policy.accept({closed_identity, legacy.next++, mouse(MousePhase::move, 11, 0, 1)}).status,
           Status::closed, "Closed Policy retained mouse authority");
}

void negotiated_payload_limits_and_geometry() {
    auto caps = capabilities(); caps.limits.text_bytes = 4; caps.limits.clipboard_bytes = 4;
    caps.limits.popup_items = 2; caps.limits.popup_text_bytes = 4;
    caps.limits.capture_rules = 1; caps.limits.held_keys = 1; caps.limits.popup_depth = 2;
    auto base = presentation(); base.editor->surrounding = "a\xc3\xa9"; base.editor->selection = {1, 3};
    Fixture fixture(caps, base);
    fixture.accepted(TextCommit{1, 1, "\xc3\xa9\xc3\xa9", std::nullopt});
    fixture.rejected(TextCommit{2, 1, "\xc3\xa9\xc3\xa9" "a", std::nullopt}, Status::limit_exceeded);
    auto over = fixture.current(); ++over.identity.presentation_revision; over.editor->surrounding = "12345";
    ++over.editor->revision; fixture.rejected_presentation(over, Status::limit_exceeded);
    fixture.accepted(composition(CompositionOperation::begin, 2, 1, "1234", {0, 4}));
    fixture.rejected(composition(CompositionOperation::update, 2, 1, "12345", {0, 5}), Status::limit_exceeded);
    fixture.accepted(composition(CompositionOperation::cancel, 2));
    fixture.accepted(ClipboardInput{ClipboardOperation::paste, 1, 0, 1, TransferStatus::accepted,
        {{"text/plain", "\xc3\xa9"}, {"text/html", "\xc3\xa9"}}});
    fixture.rejected(ClipboardInput{ClipboardOperation::paste, 2, 0, 1, TransferStatus::accepted,
        {{"text/plain", "\xc3\xa9"}, {"text/html", "\xc3\xa9" "a"}}}, Status::limit_exceeded);
    fixture.accepted(key()); fixture.rejected(key("b", "KeyB"), Status::limit_exceeded);
    fixture.accepted(key("a", "KeyA", KeyPhase::up)); fixture.accepted(key("b", "KeyB"));
    fixture.accepted(key("b", "KeyB", KeyPhase::up));

    auto rules = fixture.current(); ++rules.identity.presentation_revision;
    rules.keys.rules = {CaptureRule{}}; publish(fixture.policy, rules);
    auto too_many_rules = rules; ++too_many_rules.identity.presentation_revision;
    too_many_rules.keys.rules.push_back(CaptureRule{});
    fixture.rejected_presentation(too_many_rules, Status::limit_exceeded);
    auto choice = fixture.current(); ++choice.identity.presentation_revision; choice.popup = popup(choice);
    choice.popup->items = {item(1, "a"), item(2, "b")}; choice.popup->selected = 1;
    auto too_many_items = choice; too_many_items.popup->items.push_back(item(3, "c"));
    fixture.rejected_presentation(too_many_items, Status::limit_exceeded);
    choice.popup->items = {item(1, "\xc3\xa9")}; choice.popup->items[0].accessible_name = "\xc3\xa9";
    auto too_much_text = choice; too_much_text.popup->items[0].accessible_name += 'a';
    fixture.rejected_presentation(too_much_text, Status::limit_exceeded);
    publish(fixture.policy, choice);
    fixture.accepted(PopupReply{choice.popup->token, PopupOperation::cancel, std::nullopt});

    auto menu = fixture.current(); ++menu.identity.presentation_revision; menu.popup = popup(menu, 2);
    menu.popup->kind = PopupKind::action_menu; menu.popup->selected.reset();
    auto branch = item(1, "a"); branch.kind = PopupItemKind::submenu; branch.children = {item(2, "b")};
    menu.popup->items = {branch}; publish(fixture.policy, menu);
    fixture.accepted(PopupReply{menu.popup->token, PopupOperation::cancel, std::nullopt});
    auto deep_caps = caps; deep_caps.limits.popup_items = 8; deep_caps.limits.popup_text_bytes = 16;
    Fixture depth(deep_caps, base);
    auto deep = depth.current(); ++deep.identity.presentation_revision; deep.popup = popup(deep);
    deep.popup->kind = PopupKind::action_menu; deep.popup->selected.reset();
    auto inner = item(2, "b"); inner.kind = PopupItemKind::submenu; inner.children = {item(3, "c")};
    branch.children = {inner}; deep.popup->items = {branch};
    depth.rejected_presentation(deep, Status::limit_exceeded);

    Fixture geometry;
    const auto original = geometry.current();
    for (unsigned failure = 0; failure != 5; ++failure) {
        auto invalid = original; ++invalid.identity.presentation_revision;
        if (failure == 0) invalid.display_scale = 0;
        if (failure == 1) invalid.display_scale = 16.01;
        if (failure == 2) invalid.clip.x = -1;
        if (failure == 3) invalid.bounds.width = -1;
        if (failure == 4) invalid.editor->caret.x = std::numeric_limits<double>::quiet_NaN();
        geometry.rejected_presentation(invalid, Status::invalid_value);
    }
    auto scaled = original; ++scaled.identity.presentation_revision; scaled.display_scale = 16;
    publish(geometry.policy, scaled);
    auto unavailable = geometry.current(); ++unavailable.identity.presentation_revision; unavailable.available = false;
    publish(geometry.policy, unavailable);
    check(!geometry.policy.focused(), "Unavailable presentation retained focus");
    geometry.rejected(PointerTransition{}, Status::unavailable);
}

void revocation_noallocation_and_exhaustion() {
    Fixture fixture;
    fixture.accepted(key()); fixture.accepted(composition(CompositionOperation::begin, 1));
    auto next = fixture.current(); ++next.identity.presentation_revision; ++next.identity.context;
    next.popup = popup(next);
    auto staged = fixture.policy.prepare(next);
    expect(staged.status, Status::ok, "Prepare cleanup before allocation gate");
    CommitResult committed;
    allocation_test::fail = true;
    committed = fixture.policy.commit(std::move(staged.prepared), next.identity.presentation_revision);
    allocation_test::fail = false;
    expect(committed.status, Status::ok, "Allocation-free commit failed");
    check(committed.revoked.composition == 1 && committed.revoked.held_keys.size() == 1 && !fixture.policy.composition(),
          "Allocation-free commit lost owned cleanup");
    const auto retired = fixture.current();
    auto legacy = fixture.policy.legacy_present(retired.identity.presentation_revision + 1);
    expect(legacy.status, Status::ok, "Legacy publication failed");
    check(legacy.revoked.popup == retired.popup->token && !fixture.policy.accepted(), "Legacy publication failed to revoke popup/context");
    auto revive = retired; revive.identity.presentation_revision += 2; revive.popup.reset();
    auto stale = fixture.policy.prepare(revive);
    expect(stale.status, Status::stale_identity, "Legacy-retired context resurrected");
    ++revive.identity.context; publish(fixture.policy, revive);
    auto pending = fixture.policy.prepare([&] { auto view = revive; ++view.identity.presentation_revision; return view; }());
    expect(pending.status, Status::ok, "Prepare before close");
    fixture.policy.close();
    check(!pending.prepared && !fixture.policy.accepted() && !fixture.policy.active() && !fixture.policy.focused(),
          "Close did not revoke accepted/prepared ownership");
    expect(fixture.policy.commit(std::move(pending.prepared), revive.identity.presentation_revision + 1).status,
           Status::closed, "Closed policy committed preparation");
    expect(fixture.policy.prepare(revive).status, Status::closed, "Closed policy prepared input context");
    expect(fixture.policy.accept({revive.identity, fixture.next++, FocusChange{}}).status,
           Status::closed, "Closed policy accepted input");
    check(fixture.policy.close().empty(), "Repeated close returned duplicate cleanup");

    Fixture sequence;
    auto last = sequence.policy.accept({sequence.current().identity, maximum, FocusChange{true, true, FocusCause::direct}});
    expect(last.status, Status::ok, "Maximum input sequence rejected before exhaustion");
    check(sequence.policy.last_sequence() == maximum, "Maximum sequence was not retained exactly");
    for (auto value : {std::uint64_t{1}, maximum}) {
        auto result = sequence.policy.accept({sequence.current().identity, value, FocusChange{true, true, FocusCause::direct}});
        expect(result.status, Status::duplicate, "Exhausted sequence stream replayed/wrapped");
        check(!result.accepted, "Exhausted stream returned work");
    }
    expect(sequence.policy.accept({sequence.current().identity, 0, FocusChange{}}).status,
           Status::invalid_value, "Sequence zero wrapped exhausted stream");
    Policy fresh(capabilities(), generation + 1);
    auto fresh_view = presentation(); fresh_view.identity.generation = generation + 1;
    publish(fresh, fresh_view);
    expect(fresh.accept({fresh_view.identity, 1, FocusChange{true, true, FocusCause::direct}}).status,
           Status::ok, "Fresh session could not restart sequence stream");
}
} // namespace

int main() {
    try {
        capability_and_text_contract();
        preparation_transactions();
        identities_capture_and_keys();
        text_and_composition_transactions();
        popup_lifetimes_and_focus();
        clipboard_pointer_and_owned_results();
        mouse_values_chords_context_and_exhaustion();
        mouse_validation_and_legacy_pointer_contract();
        mouse_publication_and_lifecycle_retirement();
        negotiated_payload_limits_and_geometry();
        revocation_noallocation_and_exhaustion();
        std::cout << "Generic surface policy transactions, identities, input, composition, popup, clipboard, mouse and limits passed\n";
    } catch (const std::exception& error) {
        allocation_test::fail = false;
        std::cerr << error.what() << '\n';
        return 1;
    }
}
