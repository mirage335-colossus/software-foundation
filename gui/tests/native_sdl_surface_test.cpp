// SPDX-License-Identifier: CC0-1.0
#include "host/native_sdl_surface_peer.hpp"

#include <algorithm>
#include <cstring>
#include <functional>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
namespace H = foundation::host;
namespace S = foundation::gui_surface;
namespace E = foundation::gui_editor;
std::size_t assertions = 0;
void check(bool condition, const char* message) {
    ++assertions;
    if (!condition) throw std::runtime_error(message);
}

SDL_Event key(Uint32 phase, SDL_Keycode symbol, SDL_Scancode code, SDL_Keymod modifiers = KMOD_NONE,
              bool repeat = false) {
    SDL_Event result{};
    result.type = phase;
    result.key.keysym.sym = symbol;
    result.key.keysym.scancode = code;
    result.key.keysym.mod = modifiers;
    result.key.state = phase == SDL_KEYDOWN ? SDL_PRESSED : SDL_RELEASED;
    result.key.repeat = repeat;
    return result;
}
SDL_Event button(Uint32 phase, Uint8 value, int x = 12, int y = 34, Uint8 clicks = 1) {
    SDL_Event result{};
    result.type = phase;
    result.button.button = value;
    result.button.state = phase == SDL_MOUSEBUTTONDOWN ? SDL_PRESSED : SDL_RELEASED;
    result.button.x = x;
    result.button.y = y;
    result.button.clicks = clicks;
    return result;
}
SDL_Event window(Uint8 event) {
    SDL_Event result{};
    result.type = SDL_WINDOWEVENT;
    result.window.event = event;
    return result;
}
SDL_Event text(const std::string& value) {
    SDL_Event result{};
    result.type = SDL_TEXTINPUT;
    check(value.size() < sizeof(result.text.text), "Fixture text exceeds the SDL event buffer");
    std::memcpy(result.text.text, value.c_str(), value.size() + 1);
    return result;
}
SDL_Event preedit(const std::string& value, int start, int length) {
    SDL_Event result{};
    result.type = SDL_TEXTEDITING;
    check(value.size() < sizeof(result.edit.text), "Fixture preedit exceeds the SDL event buffer");
    std::memcpy(result.edit.text, value.c_str(), value.size() + 1);
    result.edit.start = start;
    result.edit.length = length;
    return result;
}

struct Fixture {
    std::vector<S::Input> inputs;
    std::vector<H::NativeEditorObservation> observations;
    std::vector<S::RevocationReason> invalidations;
    std::vector<bool> captures, text_input;
    std::vector<std::pair<std::int64_t,std::int64_t>> drawable;
    std::vector<bool> foreground;
    std::vector<S::Rect> carets;
    unsigned clears{};
    bool capture_ok{true}, editor_ok{true};
    SDL_Keymod modifiers{KMOD_NONE};
    S::Status input_status{S::Status::ok};
    std::uint64_t next_observation{1};
    std::function<gui::Point(gui::Point)> transform;
    std::function<void()> capture_callback,caret_callback;
    std::function<void(std::int64_t,std::int64_t)> drawable_callback;
    std::function<std::optional<std::uint64_t>(H::NativeEditorObservation)> collector;
    H::NativeSdlSurfaceInput input;

    explicit Fixture(H::NativeSurfaceMode mode = H::NativeSurfaceMode::mouse_v1)
        : input(ingress(), mode, hooks()) {}
    H::NativeSurfaceIngress ingress() {
        return {
            [this](S::Input value) {
                inputs.push_back(std::move(value));
                // Successful mapper admission does not require a Policy receipt.
                return S::AcceptResult{input_status, {}};
            },
            [this](H::NativeEditorObservation value) -> std::optional<std::uint64_t> {
                observations.push_back(std::move(value));
                if (collector) return collector(observations.back());
                if (!editor_ok) return {};
                return next_observation++;
            },
            {},
            [this](S::RevocationReason reason) { invalidations.push_back(reason); },
            [this](std::int64_t width,std::int64_t height) {
                drawable.emplace_back(width,height);
                if (drawable_callback) drawable_callback(width,height);
            },
            [this](bool active) { foreground.push_back(active); }
        };
    }
    H::NativeSdlSurfaceInput::Hooks hooks() {
        return {
            [this](bool value) { captures.push_back(value);if(value&&capture_callback)capture_callback();return !value || capture_ok; },
            [this] { return modifiers; },
            [this](bool value) { text_input.push_back(value); },
            [this](S::Rect value) { carets.push_back(value);if(caret_callback)caret_callback(); },
            [this] { ++clears; },
            [this](gui::Point value) { return transform ? transform(value) : value; }
        };
    }
    const S::MouseTransition& mouse(S::MousePhase phase) const {
        for (auto it = inputs.rbegin(); it != inputs.rend(); ++it)
            if (const auto* value = std::get_if<S::MouseTransition>(&*it); value && value->phase == phase)
                return *value;
        throw std::runtime_error("Expected mouse transition was not delivered");
    }
    std::size_t mouse_count(S::MousePhase phase) const {
        return std::count_if(inputs.begin(), inputs.end(), [phase](const S::Input& value) {
            const auto* mouse = std::get_if<S::MouseTransition>(&value);
            return mouse && mouse->phase == phase;
        });
    }
    const H::NativeEditorObservation& composition(S::CompositionOperation operation) const {
        for (auto it = observations.rbegin(); it != observations.rend(); ++it)
            if (const auto* value = std::get_if<E::CompositionData>(&it->data); value && value->operation == operation)
                return *it;
        throw std::runtime_error("Expected composition observation was not delivered");
    }
};

H::NativeEditorPresentation publication(std::string value = "A\xC3\xA9\xF0\x9F\x98\x80Z",
                                        S::ByteRange selection = {1, 7}) {
    E::Basis basis{71, {{"surface", 3}, 8, 10, 11, 12}, 90, std::move(value), selection, false, 0};
    S::EditorContext context;
    context.revision = basis.editor_revision;
    context.surrounding = basis.surrounding;
    context.selection = basis.selection;
    context.caret = {5, 7, 1, 14};
    context.editable = true;
    S::Presentation surface;
    surface.identity = basis.identity;
    surface.bounds = {10, 20, 200, 100};
    surface.clip = surface.bounds;
    surface.display_scale = 2;
    surface.editor = context;
    H::NativeEditorPresentation result;
    result.publication = E::EditorPublication{basis, {}, {}, {}};
    result.surface = surface;
    result.context = context;
    result.draft = H::capture_native_editor_text(basis.surrounding, basis.selection, E::Direction::none);
    result.admission = H::NativeEditorAdmission::active;
    return result;
}
void activate(Fixture& fixture, const H::NativeEditorPresentation& value = publication()) {
    fixture.input.editor(value);
    fixture.input.activate(true, true); // Explicit fixture focus facts after its fresh paired publication.
    check(fixture.input.draft() && value.draft && *fixture.input.draft() == *value.draft,
          "Checked frontend basis did not seed the owned SDL editor draft");
    check(!fixture.text_input.empty() && fixture.text_input.back(), "Editor publication did not enable SDL text input");
}

void raw_keys_have_independent_identity_and_no_text_default() {
    const auto named = H::sdl_surface_key(key(SDL_KEYDOWN, SDLK_LEFT, SDL_SCANCODE_LEFT).key);
    check(named == S::KeyTransition{S::KeyPhase::down, "ArrowLeft", "ArrowLeft", 0, 0, false},
          "Named SDL key did not retain its independent physical code");
    const auto right = H::sdl_surface_key(key(SDL_KEYUP, SDLK_RSHIFT, SDL_SCANCODE_RSHIFT, KMOD_RSHIFT).key);
    check(right.phase == S::KeyPhase::up && right.key == "Shift" && right.code == "ShiftRight" &&
          right.location == 2 && right.modifiers == S::shift, "Right modifier identity/location was lost");
    const auto keypad = H::sdl_surface_key(key(SDL_KEYDOWN, SDLK_KP_ENTER, SDL_SCANCODE_KP_ENTER).key);
    check(keypad.key == "Enter" && keypad.code == "NumpadEnter" && keypad.location == 3,
          "Keypad Enter was confused with standard Enter");
    const auto printable = H::sdl_surface_key(key(SDL_KEYDOWN, SDLK_a, SDL_SCANCODE_A, KMOD_SHIFT, true).key);
    check(printable.key == "a" && printable.code == "KeyA" && printable.repeat && printable.modifiers == S::shift,
          "SDL's unmodified symbol was converted into an invented committed character");
    const auto modes = static_cast<SDL_Keymod>(KMOD_LSHIFT | KMOD_RCTRL | KMOD_RALT | KMOD_LGUI | KMOD_MODE);
    check(H::sdl_surface_modifiers(modes) == (S::shift | S::control | S::alt | S::meta | S::alt_graph),
          "Explicit SDL modifier facts or AltGraph were dropped");
    const auto alt_graph = H::sdl_surface_key(key(SDL_KEYDOWN, SDLK_RALT, SDL_SCANCODE_RALT,
        static_cast<SDL_Keymod>(KMOD_RALT | KMOD_MODE)).key);
    check(alt_graph.key == "AltGraph" && alt_graph.code == "AltRight" && alt_graph.location == 2,
          "AltGraph lost its physical right-alt identity");

    Fixture mouse;
    check(mouse.input.event(key(SDL_KEYDOWN, SDLK_a, SDL_SCANCODE_A)) &&
          mouse.input.event(key(SDL_KEYUP, SDLK_a, SDL_SCANCODE_A)), "Raw key phases were not consumed");
    check(mouse.inputs.size() == 2 && std::get<S::KeyTransition>(mouse.inputs[0]).phase == S::KeyPhase::down &&
          std::get<S::KeyTransition>(mouse.inputs[1]).phase == S::KeyPhase::up,
          "Raw key-up was lost or keydown produced a text commit");
    mouse.input.event(text("a"));
    check(mouse.inputs.size() == 2 && mouse.observations.empty() && !mouse.input.draft(),
          "Mouse-only mode acquired editor state or emitted a text commit");

    Fixture unseeded(H::NativeSurfaceMode::editor_v1);
    unseeded.input.event(key(SDL_KEYDOWN, SDLK_LEFT, SDL_SCANCODE_LEFT));
    check(unseeded.inputs.size() == 1 && std::holds_alternative<S::KeyTransition>(unseeded.inputs.front()) &&
          unseeded.observations.empty() && !unseeded.input.draft(),
          "Editor mode fabricated a frontend basis before a checked publication");

    Fixture editor(H::NativeSurfaceMode::editor_v1);
    activate(editor);
    const auto before = *editor.input.draft();
    editor.inputs.clear();
    check(editor.input.event(key(SDL_KEYDOWN, SDLK_x, SDL_SCANCODE_X)) &&
          editor.input.event(key(SDL_KEYUP, SDLK_x, SDL_SCANCODE_X)), "Editor raw-key phases were lost");
    check(editor.inputs.empty() && editor.observations.size() == 2 && *editor.input.draft() == before,
          "Editor raw keys bypassed capture or guessed a text mutation");
    for (std::size_t i = 0; i != editor.observations.size(); ++i) {
        const auto& observed = editor.observations[i];
        const auto* data = std::get_if<E::KeyData>(&observed.data);
        check(observed.kind == E::Kind::key && data && data->transition.code == "KeyX" &&
              data->transition.phase == (i ? S::KeyPhase::up : S::KeyPhase::down) &&
              observed.before == before && observed.after == before,
              "Editor callback did not contain the actual unchanged raw-key observation");
    }
}

void all_five_buttons_keep_one_chord_and_fresh_capture() {
    check(H::sdl_surface_button(SDL_BUTTON_LEFT) == 0 && H::sdl_surface_button(SDL_BUTTON_MIDDLE) == 1 &&
          H::sdl_surface_button(SDL_BUTTON_RIGHT) == 2 && H::sdl_surface_button(SDL_BUTTON_X1) == 3 &&
          H::sdl_surface_button(SDL_BUTTON_X2) == 4 && !H::sdl_surface_button(0) && !H::sdl_surface_button(6),
          "SDL button indices did not map to the five semantic buttons");
    check(H::sdl_surface_buttons(SDL_BUTTON_MMASK) == 4 && H::sdl_surface_buttons(SDL_BUTTON_RMASK) == 2 &&
          H::sdl_surface_buttons(SDL_BUTTON_LMASK | SDL_BUTTON_MMASK | SDL_BUTTON_RMASK | SDL_BUTTON_X1MASK | SDL_BUTTON_X2MASK) == 31,
          "SDL middle/right button masks were copied without semantic remapping");
    Fixture fixture;
    fixture.modifiers = static_cast<SDL_Keymod>(KMOD_CTRL | KMOD_GUI);
    constexpr Uint8 buttons[]{SDL_BUTTON_LEFT, SDL_BUTTON_MIDDLE, SDL_BUTTON_RIGHT, SDL_BUTTON_X1, SDL_BUTTON_X2};
    constexpr unsigned chords[]{1, 5, 7, 15, 31};
    std::uint64_t token{};
    for (unsigned i = 0; i != 5; ++i) {
        check(fixture.input.event(button(SDL_MOUSEBUTTONDOWN, buttons[i])), "A five-button down edge was dropped");
        const auto value = fixture.mouse(S::MousePhase::down);
        if (!i) token = value.capture_token;
        check(token && value.capture_token == token && value.button == i && value.buttons == chords[i] &&
              value.modifiers == (S::control | S::meta) && fixture.input.held_buttons() == chords[i],
              "Button chord lost an edge, token or modifier");
    }
    check(fixture.captures == std::vector<bool>{true}, "A button chord reacquired capture for each button");
    SDL_Event motion{};
    motion.type = SDL_MOUSEMOTION;
    motion.motion.state = SDL_BUTTON_LMASK | SDL_BUTTON_MMASK | SDL_BUTTON_RMASK | SDL_BUTTON_X1MASK | SDL_BUTTON_X2MASK;
    motion.motion.x = -40;
    motion.motion.y = 900;
    check(fixture.input.event(motion), "Captured outside motion was not delivered");
    check(fixture.mouse(S::MousePhase::move).capture_token == token && fixture.mouse(S::MousePhase::move).buttons == 31 &&
          fixture.mouse(S::MousePhase::move).x == -40 && fixture.mouse(S::MousePhase::move).y == 900,
          "Captured motion was clamped or lost its full chord");
    unsigned remaining = 31;
    constexpr unsigned bits[]{1, 4, 2, 8, 16};
    for (unsigned i = 0; i != 5; ++i) {
        remaining &= ~bits[i];
        check(fixture.input.event(button(SDL_MOUSEBUTTONUP, buttons[i], -40, 900)), "A button-up edge was dropped");
        const auto value = fixture.mouse(S::MousePhase::up);
        check(value.capture_token == token && value.button == i && value.buttons == remaining &&
              fixture.input.held_buttons() == remaining, "Release lost the surviving chord or original capture token");
    }
    check(!fixture.input.capture_token() && fixture.captures == std::vector<bool>({true, false}),
          "Final button release retained physical capture");
    fixture.input.event(button(SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT));
    check(fixture.input.capture_token() > token, "A fresh drag reused the retired capture token");
    fixture.input.event(button(SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT));
}

void capture_failure_focus_loss_and_suspension_cancel() {
    Fixture failed;
    failed.capture_ok = false;
    failed.input.event(button(SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT));
    check(!failed.input.held_buttons() && !failed.input.capture_token() && !failed.captures.empty() && failed.captures.front(),
          "Failed native capture retained a live drag");
    check(!failed.mouse_count(S::MousePhase::down) && !failed.mouse_count(S::MousePhase::cancel) &&
          !failed.invalidations.empty() && !failed.captures.back(),
          "Capture failure fabricated an admitted press/cancel or retained native capture");

    Fixture fixture;
    fixture.input.event(button(SDL_MOUSEBUTTONDOWN, SDL_BUTTON_X2));
    const auto token = fixture.input.capture_token();
    fixture.input.event(window(SDL_WINDOWEVENT_FOCUS_LOST));
    check(token && !fixture.input.held_buttons() && !fixture.input.capture_token() &&
          fixture.mouse(S::MousePhase::cancel).capture_token == token &&
          !fixture.captures.empty() && !fixture.captures.back(), "Focus loss did not cancel/release the whole drag");
    const auto count = fixture.inputs.size();
    fixture.input.event(button(SDL_MOUSEBUTTONUP, SDL_BUTTON_X2));
    fixture.input.event(key(SDL_KEYDOWN, SDLK_a, SDL_SCANCODE_A));
    check(fixture.inputs.size() == count, "Stale input crossed a suspended focus context");
    fixture.input.event(window(SDL_WINDOWEVENT_FOCUS_GAINED));
    check(std::any_of(fixture.inputs.begin(), fixture.inputs.end(), [](const S::Input& value) {
        const auto* focus = std::get_if<S::FocusChange>(&value); return focus && focus->focused;
    }), "Actual SDL focus gain was not delivered");
    const auto gained = fixture.inputs.size();
    fixture.input.event(button(SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT));
    check(fixture.inputs.size() == gained, "Focus gain silently restored a retired presentation");
    H::NativeEditorPresentation rearm;
    rearm.surface = S::Presentation{};
    fixture.input.editor(rearm);
    fixture.input.activate(true, true);
    fixture.input.event(button(SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT));
    check(fixture.input.capture_token() > token, "Fresh available presentation did not rearm with a new token");
    fixture.input.suspend();
    check(!fixture.input.held_buttons() && !fixture.input.capture_token(), "Explicit suspend retained a live chord");
}

void precise_wheel_context_and_synthetic_mouse_filter() {
    Fixture fixture;
    fixture.modifiers = KMOD_ALT;
    fixture.input.event(button(SDL_MOUSEBUTTONDOWN, SDL_BUTTON_RIGHT, 17, 29, 2));
    const auto token = fixture.input.capture_token();
    const auto context = fixture.mouse(S::MousePhase::context);
    check(context.context_origin == S::ContextOrigin::pointer && context.x == 17 && context.y == 29 &&
          context.capture_token == token && context.buttons == 2 && context.modifiers == S::alt,
          "Pointer context lost its actual coordinates or held right-button chord");
    SDL_Event wheel{};
    wheel.type = SDL_MOUSEWHEEL;
    wheel.wheel.x = 7;
    wheel.wheel.y = 8;
    wheel.wheel.preciseX = 1.25f;
    wheel.wheel.preciseY = -2.5f;
    wheel.wheel.direction = SDL_MOUSEWHEEL_FLIPPED;
    wheel.wheel.mouseX = 43;
    wheel.wheel.mouseY = -9;
    check(fixture.input.event(wheel), "A captured wheel event was dropped");
    const auto value = fixture.mouse(S::MousePhase::wheel);
    check(value.wheel_x == -1.25 && value.wheel_y == 2.5 && value.x == 43 && value.y == -9 &&
          value.capture_token == token && value.buttons == 2, "Precise wheel used integer deltas, later cursor state or double flip");
    fixture.input.event(key(SDL_KEYDOWN, SDLK_APPLICATION, SDL_SCANCODE_APPLICATION));
    const auto keyboard = fixture.mouse(S::MousePhase::context);
    check(keyboard.context_origin == S::ContextOrigin::keyboard && keyboard.x == 0 && keyboard.y == 0 &&
          keyboard.modifiers == 0 && keyboard.capture_token == token && keyboard.buttons == 2,
          "Keyboard context invented physical coordinates/modifiers or erased held capture");
    const auto count = fixture.inputs.size();
    auto synthetic = button(SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT);
    synthetic.button.which = SDL_TOUCH_MOUSEID;
    fixture.input.event(synthetic);
    wheel.wheel.which = SDL_TOUCH_MOUSEID;
    fixture.input.event(wheel);
    check(fixture.inputs.size() == count && fixture.input.held_buttons() == 2,
          "Touch-synthetic mouse events duplicated a real mouse stream");
    fixture.input.event(button(SDL_MOUSEBUTTONUP, SDL_BUTTON_RIGHT));
}

void input_coordinates_follow_the_committed_transform() {
    Fixture fixture;
    fixture.transform = [](gui::Point value) { return gui::Point{100 + value.x / 2, -20 + value.y / 2}; };
    fixture.input.activate(true, true);
    check(!fixture.inputs.empty() && std::holds_alternative<S::FocusChange>(fixture.inputs.back()) &&
          std::get<S::FocusChange>(fixture.inputs.back()).focused && std::get<S::FocusChange>(fixture.inputs.back()).active,
          "Activation did not deliver the supplied actual focus/activity facts");
    fixture.input.event(button(SDL_MOUSEBUTTONDOWN, SDL_BUTTON_RIGHT, 18, 30));
    const auto down = fixture.mouse(S::MousePhase::down);
    const auto context = fixture.mouse(S::MousePhase::context);
    check(down.x == 109 && down.y == -5 && context.x == 109 && context.y == -5,
          "Mouse/button context ignored the committed snapshot transform");
    SDL_Event move{};
    move.type = SDL_MOUSEMOTION;
    move.motion.state = SDL_BUTTON_RMASK;
    move.motion.x = -10;
    move.motion.y = 40;
    fixture.input.event(move);
    check(fixture.mouse(S::MousePhase::move).x == 95 && fixture.mouse(S::MousePhase::move).y == 0,
          "Mouse motion used an obsolete or unclipped window transform");
    fixture.input.event(key(SDL_KEYDOWN, SDLK_APPLICATION, SDL_SCANCODE_APPLICATION));
    const auto keyboard = fixture.mouse(S::MousePhase::context);
    check(keyboard.context_origin == S::ContextOrigin::keyboard && keyboard.x == 0 && keyboard.y == 0,
          "Coordinate transform invented a physical point for keyboard context");
    fixture.input.event(window(SDL_WINDOWEVENT_FOCUS_LOST));
    const auto canceled = fixture.mouse(S::MousePhase::cancel);
    check(canceled.x == 0 && canceled.y == 0 && canceled.buttons == 0,
          "Coordinate transform rewrote canonical capture cancellation");
}

void rejected_ingress_does_not_advance_local_authority() {
    Fixture denied;
    denied.input_status = S::Status::unavailable;
    denied.input.event(button(SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT));
    check(!denied.input.held_buttons() && !denied.input.capture_token() &&
          !denied.captures.empty() && denied.captures.front() && !denied.captures.back() &&
          !denied.invalidations.empty(),
          "Rejected surface ingress retained the provisional OS capture or local drag");
    Fixture chord;
    chord.input.event(button(SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT));
    const auto token = chord.input.capture_token();
    chord.input_status = S::Status::busy;
    chord.input.event(button(SDL_MOUSEBUTTONDOWN, SDL_BUTTON_MIDDLE));
    check(!(chord.input.held_buttons() & 4) && (!chord.input.capture_token() || chord.input.capture_token() == token),
          "Rejected chord edge advanced local button/capture ownership");
    check(chord.input.held_buttons() || (!chord.captures.empty() && !chord.captures.back()),
          "Rejected chord cleanup dropped local state but retained native capture");

    Fixture editor(H::NativeSurfaceMode::editor_v1);
    activate(editor);
    const auto before = *editor.input.draft();
    editor.editor_ok = false;
    editor.input.event(text("x"));
    check(editor.observations.size() == 1 && (!editor.input.draft() || *editor.input.draft() == before),
          "Rejected editor observation advanced the owned provisional draft");
}

void frontend_text_replacement_uses_owned_utf8_selection() {
    Fixture fixture(H::NativeSurfaceMode::editor_v1);
    auto seed = publication();
    activate(fixture, seed);
    check(!fixture.carets.empty(), "Authoritative editor caret was not supplied to the injected SDL hook");
    const auto before = *fixture.input.draft();
    fixture.input.event(text("\xC3\xB8"));
    check(fixture.observations.size() == 1, "TEXTINPUT did not make one factual text observation");
    const auto& observed = fixture.observations.back();
    const auto* data = std::get_if<E::TextData>(&observed.data);
    check(observed.kind == E::Kind::text && data && data->text == "\xC3\xB8" && data->replacement == S::ByteRange{1, 7} &&
          observed.before == before && observed.after && observed.after->value == "A\xC3\xB8Z" &&
          observed.after->selection == S::ByteRange{3, 3} && observed.after->selection_start == 2 &&
          observed.after->selection_end == 2 && *fixture.input.draft() == *observed.after,
          "TEXTINPUT confused scalar/UTF-16/UTF-8 replacement bounds");
    seed.draft->value = "mutated caller storage";
    seed.publication->basis->surrounding = "mutated native basis copy";
    check(fixture.input.draft()->value == "A\xC3\xB8Z", "SDL editor borrowed publication storage");
}

void preedit_is_separate_and_uses_only_frontend_owned_cursor() {
    Fixture fixture(H::NativeSurfaceMode::editor_v1);
    activate(fixture);
    const std::string provisional = "\xF0\x9F\x98\x80" "e\xCC\x81";
    fixture.input.event(preedit(provisional, 1, 1));
    const auto begin = fixture.composition(S::CompositionOperation::begin);
    const auto& data = std::get<E::CompositionData>(begin.data);
    check(begin.transaction && begin.kind == E::Kind::composition && data.text == provisional &&
          data.selection == S::ByteRange{7, 7} && begin.after && begin.after->value == "A" + provisional + "Z" &&
          begin.after->selection == S::ByteRange{8, 8} && begin.after->selection_start == 5 && begin.after->selection_end == 5,
          "Initial preedit lost its complete Unicode text or guessed SDL selection units");
    const auto draft = *fixture.input.draft();
    fixture.input.event(preedit(provisional, std::numeric_limits<int>::min(), std::numeric_limits<int>::max()));
    const auto update=fixture.composition(S::CompositionOperation::update);
    check(update.transaction==begin.transaction && std::get<E::CompositionData>(update.data).text==provisional &&
          update.after && *update.after==draft && *fixture.input.draft()==draft,
          "Actual preedit update lost its passage or reinterpreted undocumented SDL selection offsets");
    auto pending = publication();
    pending.draft = draft;
    pending.composition = E::CompositionFact{begin.transaction, E::CompositionState::pending};
    pending.publication->composition = pending.composition;
    pending.preserve_passage = false;
    fixture.input.editor(pending);
    check(fixture.input.draft() && *fixture.input.draft() == draft,
          "Pending composition publication discarded the retained provisional passage");
    const auto count = fixture.observations.size();
    fixture.input.event(preedit("", 0, 0));
    check(fixture.input.draft() && fixture.input.draft()->value == "AZ" && fixture.input.draft()->selection == S::ByteRange{1, 1},
          "Empty preedit failed to retain its provisional replacement bounds");
    check(std::none_of(fixture.observations.begin() + count, fixture.observations.end(), [](const auto& value) {
        const auto* composition = std::get_if<E::CompositionData>(&value.data);
        return composition && (composition->operation == S::CompositionOperation::cancel ||
                               composition->operation == S::CompositionOperation::commit);
    }), "Empty preedit was misreported as a native cancellation or commit");
    fixture.input.event(text("\xC3\x9F"));
    const auto commit = fixture.composition(S::CompositionOperation::commit);
    check(commit.transaction == begin.transaction && std::get<E::CompositionData>(commit.data).text == "\xC3\x9F" &&
          commit.after && commit.after->value == "A\xC3\x9FZ" && commit.after->selection == S::ByteRange{3, 3} &&
          *fixture.input.draft() == *commit.after, "Actual TEXTINPUT did not commit the retained provisional passage");
    fixture.input.event(text("!"));
    check(std::holds_alternative<E::TextData>(fixture.observations.back().data) &&
          fixture.input.draft()->value == "A\xC3\x9F!Z", "Finished composition leaked into the next independent text insertion");
}

void extended_preedit_is_not_truncated_and_blocked_text_stays_retired() {
    Fixture fixture(H::NativeSurfaceMode::editor_v1);
    activate(fixture);
    std::string value;
    for (unsigned i = 0; i != 24; ++i) value += "\xC3\xA9";
    value += "\xF0\x9F\x98\x80";
    auto dispatch = [&](Fixture& target) {
        SDL_Event extended{};
        extended.type = SDL_TEXTEDITING_EXT;
        extended.editExt.text = static_cast<char*>(SDL_malloc(value.size() + 1));
        check(extended.editExt.text, "Cannot allocate owned extended SDL preedit fixture");
        std::memcpy(extended.editExt.text, value.c_str(), value.size() + 1);
        extended.editExt.start = -50;
        extended.editExt.length = 99999;
        // The mapper owns this allocation on accepted and blocked paths.
        target.input.event(extended);
    };
    dispatch(fixture);
    const auto begin = fixture.composition(S::CompositionOperation::begin);
    const auto& data = std::get<E::CompositionData>(begin.data);
    check(begin.transaction && data.text == value && data.selection == S::ByteRange{52, 52} && begin.after &&
          begin.after->value == "A" + value + "Z" && begin.after->selection == S::ByteRange{53, 53} &&
          begin.after->selection_start == 27 && begin.after->selection_end == 27,
          "Extended SDL preedit was truncated or its undocumented offsets became selection authority");
    const auto count = fixture.observations.size();
    fixture.input.suspend();
    dispatch(fixture);
    check(fixture.observations.size() == count && !fixture.input.draft(),
          "Owned extended preedit reentered a suspended editor context");
}

void malformed_and_oversize_text_never_reaches_editor_ingress() {
    for (const std::string& malformed : {std::string("\xC0\x80"), std::string("\xED\xA0\x80"), std::string("\xE2\x82")}) {
        for (const bool editing : {false, true}) {
            Fixture fixture(H::NativeSurfaceMode::editor_v1);
            activate(fixture);
            fixture.input.event(editing ? preedit(malformed, 0, 0) : text(malformed));
            check(fixture.observations.empty(), "Malformed UTF-8 SDL text reached causal editor capture");
        }
    }
    for (const bool editing : {false, true}) {
        Fixture fixture(H::NativeSurfaceMode::editor_v1);
        activate(fixture);
        SDL_Event unterminated{};
        unterminated.type = editing ? SDL_TEXTEDITING : SDL_TEXTINPUT;
        if (editing) std::memset(unterminated.edit.text, 'x', sizeof(unterminated.edit.text));
        else std::memset(unterminated.text.text, 'x', sizeof(unterminated.text.text));
        fixture.input.event(unterminated);
        check(fixture.observations.empty(), "Unterminated fixed-size SDL text escaped bounded decoding");
    }
    Fixture full(H::NativeSurfaceMode::editor_v1);
    activate(full, publication(std::string(65536, 'x'), {65536, 65536}));
    full.input.event(text("x"));
    check(full.observations.empty(), "Editor insertion exceeded the retained 64KiB text bound");
    for (const std::string& value : {std::string("\xC0\x80"), std::string(65537, 'x')}) {
        Fixture extended(H::NativeSurfaceMode::editor_v1);
        activate(extended);
        SDL_Event event{};
        event.type = SDL_TEXTEDITING_EXT;
        event.editExt.text = static_cast<char*>(SDL_malloc(value.size() + 1));
        check(event.editExt.text, "Cannot allocate invalid extended SDL preedit fixture");
        std::memcpy(event.editExt.text, value.c_str(), value.size() + 1);
        extended.input.event(event);
        check(extended.observations.empty(), "Malformed/oversized extended preedit reached editor capture");
    }

    for (const bool focus_loss : {false, true}) {
        Fixture blocked(H::NativeSurfaceMode::editor_v1);
        activate(blocked);
        blocked.input.event(preedit("draft", 0, 1));
        const auto count = blocked.observations.size();
        if (focus_loss) blocked.input.event(window(SDL_WINDOWEVENT_FOCUS_LOST));
        else blocked.input.suspend();
        check(!blocked.input.draft() && !blocked.text_input.empty() && !blocked.text_input.back() && blocked.clears,
              "Suspend/focus loss did not retire frontend text, text input and composition");
        blocked.input.event(text("late"));
        blocked.input.event(preedit("late", 0, 1));
        check(blocked.observations.size() == count, "Late text entered a retired editor context");
    }
}

void platform_callback_retirement_cannot_restore_ime_or_leak_extended_text() {
    Fixture fixture(H::NativeSurfaceMode::editor_v1);
    fixture.caret_callback=[&] { fixture.input.suspend(); };
    fixture.input.editor(publication());
    check(!fixture.input.draft() && !fixture.text_input.empty() && !fixture.text_input.back() &&
          std::find(fixture.text_input.begin(),fixture.text_input.end(),true)==fixture.text_input.end(),
          "Reentrant caret suspension was followed by stale text-input activation");

    Fixture nested;
    const int before=SDL_GetNumAllocations();
    nested.capture_callback=[&] {
        SDL_Event event{};event.type=SDL_TEXTEDITING_EXT;
        event.editExt.text=SDL_strdup("owned preedit");
        check(event.editExt.text,"Cannot allocate reentrant SDL preedit");
        nested.input.event(event);
    };
    nested.input.event(button(SDL_MOUSEBUTTONDOWN,SDL_BUTTON_LEFT));
    check(SDL_GetNumAllocations()==before && !nested.input.capture_token(),
          "Reentrant EXT rejection leaked its SDL-owned payload or retained capture");
    Fixture disabled(H::NativeSurfaceMode::none);
    SDL_Event event{};event.type=SDL_TEXTEDITING_EXT;event.editExt.text=SDL_strdup("disabled preedit");
    check(event.editExt.text,"Cannot allocate disabled SDL preedit");
    check(disabled.input.event(event) && SDL_GetNumAllocations()==before,
          "Disabled Surface failed to consume/free an allocated EXT payload");
}

void focus_publications_are_deduplicated_and_key_releases_keep_their_channel() {
    Fixture focus;
    auto first=publication();
    focus.input.editor(first);focus.input.activate(true,true);
    const auto count=focus.inputs.size();
    ++first.surface->identity.presentation_revision;
    focus.input.editor(first);focus.input.activate(true,true);
    check(focus.inputs.size()==count,"Presentation-only repaint repeated an unchanged native focus effect");
    ++first.surface->identity.context;
    focus.input.editor(first);focus.input.activate(true,true);
    check(focus.inputs.size()==count+1,"Fresh Surface context did not announce its actual focus once");
    focus.input.event(window(SDL_WINDOWEVENT_FOCUS_LOST));
    const auto lost=focus.inputs.size();
    focus.input.activate(false,true);
    check(focus.inputs.size()==lost,"Unchanged inactive focus publication repeated its native effect");

    Fixture routes(H::NativeSurfaceMode::editor_v1);
    auto body=publication();body.publication.reset();body.context.reset();body.draft.reset();body.surface->editor.reset();
    body.admission=H::NativeEditorAdmission::withdrawn;
    routes.input.editor(body);routes.input.activate(true,true);
    routes.input.event(key(SDL_KEYDOWN,SDLK_a,SDL_SCANCODE_A));
    routes.input.editor(publication());
    routes.input.event(key(SDL_KEYDOWN,SDLK_a,SDL_SCANCODE_A,KMOD_NONE,true));
    routes.input.event(key(SDL_KEYUP,SDLK_a,SDL_SCANCODE_A));
    check(routes.observations.empty() && std::get<S::KeyTransition>(routes.inputs.back()).phase==S::KeyPhase::up,
          "Body-owned key repeat/release was retargeted into a newly published editor");
    const auto body_events=routes.inputs.size();
    routes.input.event(key(SDL_KEYDOWN,SDLK_x,SDL_SCANCODE_X));
    check(routes.observations.size()==1,"Editor key press did not enter the causal editor path");
    routes.input.editor(body);
    routes.input.event(key(SDL_KEYUP,SDLK_x,SDL_SCANCODE_X));
    check(routes.inputs.size()==body_events && routes.observations.size()==1,
          "Retired editor key release became an unowned body key event");
}

void paused_metadata_preserves_actual_passage_until_real_withdrawal() {
    Fixture fixture(H::NativeSurfaceMode::editor_v1);
    auto body=publication();body.publication.reset();body.context.reset();body.draft.reset();body.surface->editor.reset();
    body.admission=H::NativeEditorAdmission::withdrawn;
    fixture.input.editor(body);fixture.input.activate(true,true);
    fixture.input.event(key(SDL_KEYDOWN,SDLK_LEFT,SDL_SCANCODE_LEFT));
    activate(fixture);
    fixture.input.event(preedit("first",0,0));
    const auto transaction=fixture.composition(S::CompositionOperation::begin).transaction;
    const auto before=*fixture.input.draft();
    check(before.value=="AfirstZ" && before.selection_start==6 && before.selection_end==6,
          "Initial actual preedit did not replace the complete selected Unicode text");
    const auto native_switches=fixture.text_input.size();
    const auto clear_count=fixture.clears;
    const auto focus_count=fixture.inputs.size();
    H::NativeEditorPresentation paused;
    paused.admission=H::NativeEditorAdmission::paused;
    paused.passage_basis=publication().publication->basis;
    paused.passage_composition=E::CompositionFact{transaction,E::CompositionState::pending};
    paused.draft=before;
    fixture.input.editor(paused);
    fixture.input.activate(true,true); // Actual window stayed focused; inert metadata grants no new focus effect.
    check(fixture.input.draft() && *fixture.input.draft()==before && fixture.text_input.size()==native_switches &&
          fixture.clears==clear_count && fixture.inputs.size()==focus_count,
          "Metadata pause reset the actual IME/frontend passage or emitted native focus into an inert pair");
    const auto invalidations=fixture.invalidations.size();
    fixture.input.event(key(SDL_KEYUP,SDLK_LEFT,SDL_SCANCODE_LEFT));
    check(fixture.inputs.size()==focus_count && fixture.invalidations.size()==invalidations &&
          fixture.input.draft() && *fixture.input.draft()==before,
          "Late retired body UP entered an unavailable pair or withdrew the retained editor passage");
    fixture.input.event(preedit("next",0,4));
    const auto& update=fixture.composition(S::CompositionOperation::update);
    check(update.transaction==transaction && std::get<E::CompositionData>(update.data).text=="next" &&
          fixture.observations.back().before==before && fixture.observations.back().after &&
          fixture.observations.back().after->value=="AnextZ" &&
          fixture.observations.back().after->selection_start==5 && fixture.observations.back().after->selection_end==5,
          "Metadata pause changed the owned composition or failed to replace its complete preedit range");
    const auto updated=*fixture.input.draft();
    fixture.input.event(text("commit"));
    const auto& committed=fixture.composition(S::CompositionOperation::commit);
    check(committed.transaction==transaction && std::get<E::CompositionData>(committed.data).text=="commit" &&
          fixture.observations.back().before==updated && fixture.observations.back().after &&
          fixture.observations.back().after->value=="AcommitZ" &&
          fixture.observations.back().after->selection_start==7 && fixture.observations.back().after->selection_end==7 &&
          fixture.input.draft() && *fixture.input.draft()==*fixture.observations.back().after,
          "Actual commit during metadata pause lost its owned replacement range/value/selection");
    fixture.input.event(window(SDL_WINDOWEVENT_FOCUS_LOST));
    const auto observations=fixture.observations.size();
    fixture.input.event(text("late"));
    check(!fixture.input.draft() && !fixture.invalidations.empty() && fixture.observations.size()==observations &&
          !fixture.text_input.empty() && !fixture.text_input.back(),
          "Real focus loss failed to withdraw the paused collector and reject late text");
}
void unavailable_pause_restores_actual_focus_once_for_the_same_context() {
    Fixture fixture(H::NativeSurfaceMode::editor_v1);
    auto active=publication();
    fixture.input.editor(active);fixture.input.activate(true,true);
    const auto count=fixture.inputs.size();
    H::NativeEditorPresentation paused;
    paused.admission=H::NativeEditorAdmission::paused;
    paused.passage_basis=active.publication->basis;
    paused.draft=*fixture.input.draft();
    fixture.input.editor(paused);fixture.input.activate(true,true);
    check(fixture.inputs.size()==count,"Unavailable pause emitted focus into an inert pair");
    fixture.input.editor(active);fixture.input.activate(true,true);
    check(fixture.inputs.size()==count+1 && std::get<S::FocusChange>(fixture.inputs.back()).focused,
          "Same-context checked restoration failed to restore the actual native focus once");
    ++active.surface->identity.presentation_revision;
    fixture.input.editor(active);fixture.input.activate(true,true);
    check(fixture.inputs.size()==count+1,"Repaint repeated the focus restoration native effect");
}
void actual_platform_facts_are_value_deduplicated_without_input_authority() {
    Fixture fixture(H::NativeSurfaceMode::editor_v1);
    fixture.input.platform_facts(1600,1200,true);
    fixture.input.platform_facts(1600,1200,true);
    check(fixture.drawable==std::vector{std::pair<std::int64_t,std::int64_t>{1600,1200}} &&
          fixture.foreground==std::vector{true} && fixture.inputs.empty() && fixture.observations.empty(),
          "Actual platform facts were omitted, repeated or fabricated input/editor authority");
    activate(fixture);
    H::NativeEditorPresentation paused;paused.admission=H::NativeEditorAdmission::paused;
    fixture.input.editor(paused);
    const auto paused_inputs=fixture.inputs.size(),paused_observations=fixture.observations.size();
    fixture.input.platform_facts(1920,1080,true);
    fixture.input.platform_facts(1920,1080,false);
    fixture.input.platform_facts(1920,1080,false);
    check(fixture.drawable.size()==2 && fixture.drawable.back()==std::pair<std::int64_t,std::int64_t>{1920,1080} &&
          fixture.foreground==std::vector{true,false} && fixture.inputs.size()==paused_inputs &&
          fixture.observations.size()==paused_observations,
          "Actual size/background change was lost, repeated or granted input during an inert editor pause");
    const auto input_count=fixture.inputs.size();
    fixture.input.platform_facts(1920,1080,true);
    check(fixture.foreground==std::vector{true,false,true} && fixture.inputs.size()==input_count &&
          fixture.observations.size()==paused_observations,
          "Real foreground restoration guessed a Policy focus or editor/native acceptance");
    Fixture nested;
    nested.drawable_callback=[&](std::int64_t width,std::int64_t) {
        if (width==1600) nested.input.platform_facts(1920,1080,false);
    };
    nested.input.platform_facts(1600,1200,true);
    check(nested.drawable==std::vector{std::pair<std::int64_t,std::int64_t>{1600,1200},
          std::pair<std::int64_t,std::int64_t>{1920,1080}} && nested.foreground==std::vector{false},
          "Reentrant newer platform facts were overwritten by a stale outer foreground continuation");
}
void actual_capture_accepts_the_sdl_passage_without_callback_dispatch() {
    unsigned endpoint_calls=0,terminals=0;
    H::NativeEditorEndpoint endpoint{
        [&](E::Packet)->std::optional<std::uint64_t> { ++endpoint_calls;return {}; },
        [&](E::Revocation)->std::optional<std::uint64_t> { ++endpoint_calls;return {}; },
        [&](std::uint64_t)->std::optional<E::EditorCompletion> { ++endpoint_calls;return {}; },
        [&] { ++endpoint_calls; },
        {&terminals,[](void* value) noexcept { ++*static_cast<unsigned*>(value); }}
    };
    H::NativeEditorCapture capture(std::move(endpoint));
    Fixture fixture(H::NativeSurfaceMode::editor_v1);
    fixture.collector=[&](H::NativeEditorObservation value) {
        return capture.paused() ? capture.observe_paused(std::move(value)) : capture.observe(std::move(value));
    };
    auto active=publication();
    check(capture.install(*active.publication,active.surface->identity),"Actual Capture rejected the checked SDL fixture Basis");
    activate(fixture,active);
    fixture.input.event(preedit("first",0,0));
    check(capture.pending()==1 && capture.draft() && capture.draft()->value=="AfirstZ" && endpoint_calls==0,
          "SDL composition begin was rejected by actual Capture or dispatched inside ingress");
    check(capture.install({},{} ) && capture.paused(),"Actual Capture fixture failed to pause without authority withdrawal");
    H::NativeEditorPresentation paused;paused.admission=H::NativeEditorAdmission::paused;
    paused.passage_basis=*capture.basis();paused.draft=*capture.draft();
    fixture.input.editor(paused);
    fixture.input.event(preedit("next",3,1));fixture.input.event(text("commit"));
    capture.tick();
    check(capture.pending()==3 && capture.draft() && capture.draft()->value=="AcommitZ" &&
          capture.draft()->selection==S::ByteRange{7,7} && fixture.invalidations.empty() && endpoint_calls==0 && terminals==0,
          "Actual paused Capture rejected SDL's complete causal passage or entered its endpoint");
    check(capture.install(*active.publication,active.surface->identity) && !capture.paused() &&
          capture.pending()==3 && endpoint_calls==0 && terminals==0,
          "Exact unchanged checked Basis failed to retain the paused SDL observations without replay");
    // Nothing was handed out: close only retires the still-local queued facts.
    capture.close();
    check(endpoint_calls==0 && terminals==0,"Closing never-dispatched SDL facts entered the native endpoint");
}
void actual_runner_loop_propagates_failure_without_settling_owned_work() {
    struct MockSession {
        struct Adapter { bool closed_value{};bool closed() const { return closed_value; } } adapter;
        H::RunnerState state;
        unsigned ticks{};
        std::string retained{"unresolved-original-native-work"};
        std::function<void()> on_tick;
        H::RunnerState runner_state() const { return state; }
        void tick() {
            if (++ticks>4) throw std::runtime_error("Mock SDL runner failed to stop after a terminal outcome");
            if (on_tick) on_tick();
        }
    };
    MockSession before;before.state={true,false,73,{}};
    unsigned pumps=0,paints=0;
    check(H::run_native_sdl_surface_loop(before,[&](int) { ++pumps; },[&] { ++paints; })==73 &&
          !pumps && !before.ticks && !paints && before.retained=="unresolved-original-native-work" &&
          !before.state.close_complete,"Nonzero pre-tick result was ignored or declared unresolved work settled");
    MockSession after;after.on_tick=[&] { after.state={true,false,74,{}}; };
    check(H::run_native_sdl_surface_loop(after,[&](int) { ++pumps; },[&] { ++paints; })==74 &&
          pumps==1 && after.ticks==1 && !paints && after.retained=="unresolved-original-native-work" &&
          !after.state.close_complete,"Nonzero tick result kept pumping/painting or fabricated cleanup success");
    MockSession during_pump;pumps=0;
    check(H::run_native_sdl_surface_loop(during_pump,[&](int) { ++pumps;during_pump.state.exit_code=75; },
          [&] { ++paints; })==75 && pumps==1 && !during_pump.ticks && !paints,
          "Fatal event-pump result entered another owner tick");
    MockSession ordinary;pumps=paints=0;ordinary.state.close_requested=true;
    ordinary.on_tick=[&] { if (ordinary.ticks==2) ordinary.state.close_complete=true; };
    check(H::run_native_sdl_surface_loop(ordinary,[&](int timeout) {
              check(timeout>=0 && timeout<=16,"SDL runner exceeded its bounded event wait");++pumps;
          },[&] { ++paints; })==0 && pumps==2 && ordinary.ticks==2 && paints==1 && ordinary.state.close_complete,
          "Ordinary requested close exited before actual completion or missed clean completion");
    MockSession closed;closed.state={true,true,0,{}};pumps=paints=0;
    check(H::run_native_sdl_surface_loop(closed,[&](int) { ++pumps; },[&] { ++paints; })==0 &&
          !pumps && !closed.ticks && !paints,"Already complete ordinary close still pumped or ticked");
}
} // namespace

int main(int, char**) {
    try {
        raw_keys_have_independent_identity_and_no_text_default();
        all_five_buttons_keep_one_chord_and_fresh_capture();
        capture_failure_focus_loss_and_suspension_cancel();
        precise_wheel_context_and_synthetic_mouse_filter();
        input_coordinates_follow_the_committed_transform();
        rejected_ingress_does_not_advance_local_authority();
        frontend_text_replacement_uses_owned_utf8_selection();
        preedit_is_separate_and_uses_only_frontend_owned_cursor();
        extended_preedit_is_not_truncated_and_blocked_text_stays_retired();
        malformed_and_oversize_text_never_reaches_editor_ingress();
        platform_callback_retirement_cannot_restore_ime_or_leak_extended_text();
        focus_publications_are_deduplicated_and_key_releases_keep_their_channel();
        paused_metadata_preserves_actual_passage_until_real_withdrawal();
        unavailable_pause_restores_actual_focus_once_for_the_same_context();
        actual_platform_facts_are_value_deduplicated_without_input_authority();
        actual_capture_accepts_the_sdl_passage_without_callback_dispatch();
        actual_runner_loop_propagates_failure_without_settling_owned_work();
        std::cout << "SDL native surface injected input: " << assertions << " assertions passed\n";
        return 0;
    } catch (const std::exception& failure) {
        std::cerr << failure.what() << " (after " << assertions << " assertions)\n";
        return 1;
    }
}
