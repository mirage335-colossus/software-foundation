// SPDX-License-Identifier: CC0-1.0
#include "native_sdl_surface_peer.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <string_view>
#include <utility>
#include <vector>

namespace foundation::host {
namespace S = gui_surface;
namespace E = gui_editor;
namespace {
void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(std::string(message) + ": " + SDL_GetError());
}
std::string scalar(std::uint32_t value) {
    if (!value || value > 0x10ffff || (value >= 0xd800 && value <= 0xdfff)) return "Unidentified";
    std::string result;
    if (value < 0x80) result += static_cast<char>(value);
    else if (value < 0x800) {
        result += static_cast<char>(0xc0 | (value >> 6)); result += static_cast<char>(0x80 | (value & 63));
    } else if (value < 0x10000) {
        result += static_cast<char>(0xe0 | (value >> 12)); result += static_cast<char>(0x80 | ((value >> 6) & 63));
        result += static_cast<char>(0x80 | (value & 63));
    } else {
        result += static_cast<char>(0xf0 | (value >> 18)); result += static_cast<char>(0x80 | ((value >> 12) & 63));
        result += static_cast<char>(0x80 | ((value >> 6) & 63)); result += static_cast<char>(0x80 | (value & 63));
    }
    return result;
}
std::string code(SDL_Scancode value) {
    if (value >= SDL_SCANCODE_A && value <= SDL_SCANCODE_Z) return "Key" + std::string(1, char('A' + value - SDL_SCANCODE_A));
    if (value >= SDL_SCANCODE_1 && value <= SDL_SCANCODE_9) return "Digit" + std::string(1, char('1' + value - SDL_SCANCODE_1));
    if (value >= SDL_SCANCODE_F1 && value <= SDL_SCANCODE_F12) return "F" + std::to_string(1 + value - SDL_SCANCODE_F1);
    if (value >= SDL_SCANCODE_F13 && value <= SDL_SCANCODE_F24) return "F" + std::to_string(13 + value - SDL_SCANCODE_F13);
    if (value >= SDL_SCANCODE_KP_1 && value <= SDL_SCANCODE_KP_9) return "Numpad" + std::to_string(1 + value - SDL_SCANCODE_KP_1);
#define BIB_SDL_CODE(sdl, name) case SDL_SCANCODE_##sdl: return name
    switch (value) {
    BIB_SDL_CODE(0,"Digit0"); BIB_SDL_CODE(RETURN,"Enter"); BIB_SDL_CODE(ESCAPE,"Escape");
    BIB_SDL_CODE(BACKSPACE,"Backspace"); BIB_SDL_CODE(TAB,"Tab"); BIB_SDL_CODE(SPACE,"Space");
    BIB_SDL_CODE(MINUS,"Minus"); BIB_SDL_CODE(EQUALS,"Equal"); BIB_SDL_CODE(LEFTBRACKET,"BracketLeft");
    BIB_SDL_CODE(RIGHTBRACKET,"BracketRight"); BIB_SDL_CODE(BACKSLASH,"Backslash");
    BIB_SDL_CODE(SEMICOLON,"Semicolon"); BIB_SDL_CODE(APOSTROPHE,"Quote"); BIB_SDL_CODE(GRAVE,"Backquote");
    BIB_SDL_CODE(COMMA,"Comma"); BIB_SDL_CODE(PERIOD,"Period"); BIB_SDL_CODE(SLASH,"Slash");
    BIB_SDL_CODE(CAPSLOCK,"CapsLock"); BIB_SDL_CODE(PRINTSCREEN,"PrintScreen"); BIB_SDL_CODE(SCROLLLOCK,"ScrollLock");
    BIB_SDL_CODE(PAUSE,"Pause"); BIB_SDL_CODE(INSERT,"Insert"); BIB_SDL_CODE(HOME,"Home");
    BIB_SDL_CODE(PAGEUP,"PageUp"); BIB_SDL_CODE(DELETE,"Delete"); BIB_SDL_CODE(END,"End");
    BIB_SDL_CODE(PAGEDOWN,"PageDown"); BIB_SDL_CODE(RIGHT,"ArrowRight"); BIB_SDL_CODE(LEFT,"ArrowLeft");
    BIB_SDL_CODE(DOWN,"ArrowDown"); BIB_SDL_CODE(UP,"ArrowUp"); BIB_SDL_CODE(NUMLOCKCLEAR,"NumLock");
    BIB_SDL_CODE(KP_DIVIDE,"NumpadDivide"); BIB_SDL_CODE(KP_MULTIPLY,"NumpadMultiply");
    BIB_SDL_CODE(KP_MINUS,"NumpadSubtract"); BIB_SDL_CODE(KP_PLUS,"NumpadAdd"); BIB_SDL_CODE(KP_ENTER,"NumpadEnter");
    BIB_SDL_CODE(KP_0,"Numpad0"); BIB_SDL_CODE(KP_PERIOD,"NumpadDecimal"); BIB_SDL_CODE(KP_EQUALS,"NumpadEqual");
    BIB_SDL_CODE(NONUSBACKSLASH,"IntlBackslash"); BIB_SDL_CODE(APPLICATION,"ContextMenu");
    BIB_SDL_CODE(LCTRL,"ControlLeft"); BIB_SDL_CODE(RCTRL,"ControlRight");
    BIB_SDL_CODE(LSHIFT,"ShiftLeft"); BIB_SDL_CODE(RSHIFT,"ShiftRight"); BIB_SDL_CODE(LALT,"AltLeft");
    BIB_SDL_CODE(RALT,"AltRight"); BIB_SDL_CODE(LGUI,"MetaLeft"); BIB_SDL_CODE(RGUI,"MetaRight");
    BIB_SDL_CODE(MUTE,"AudioVolumeMute"); BIB_SDL_CODE(VOLUMEUP,"AudioVolumeUp"); BIB_SDL_CODE(VOLUMEDOWN,"AudioVolumeDown");
    default: return {};
    }
#undef BIB_SDL_CODE
}
std::string key(SDL_Keycode value) {
    if (value >= SDLK_F1 && value <= SDLK_F12) return "F" + std::to_string(1 + value - SDLK_F1);
    if (value >= SDLK_F13 && value <= SDLK_F24) return "F" + std::to_string(13 + value - SDLK_F13);
#define BIB_SDL_KEY(sdl, name) case SDLK_##sdl: return name
    switch (value) {
    BIB_SDL_KEY(RETURN,"Enter"); BIB_SDL_KEY(KP_ENTER,"Enter"); BIB_SDL_KEY(ESCAPE,"Escape");
    BIB_SDL_KEY(BACKSPACE,"Backspace"); BIB_SDL_KEY(TAB,"Tab"); BIB_SDL_KEY(DELETE,"Delete");
    BIB_SDL_KEY(LEFT,"ArrowLeft"); BIB_SDL_KEY(RIGHT,"ArrowRight"); BIB_SDL_KEY(UP,"ArrowUp"); BIB_SDL_KEY(DOWN,"ArrowDown");
    BIB_SDL_KEY(HOME,"Home"); BIB_SDL_KEY(END,"End"); BIB_SDL_KEY(PAGEUP,"PageUp"); BIB_SDL_KEY(PAGEDOWN,"PageDown");
    BIB_SDL_KEY(INSERT,"Insert"); BIB_SDL_KEY(APPLICATION,"ContextMenu"); BIB_SDL_KEY(MENU,"ContextMenu");
    BIB_SDL_KEY(LCTRL,"Control"); BIB_SDL_KEY(RCTRL,"Control"); BIB_SDL_KEY(LSHIFT,"Shift"); BIB_SDL_KEY(RSHIFT,"Shift");
    BIB_SDL_KEY(LALT,"Alt"); BIB_SDL_KEY(RALT,"Alt"); BIB_SDL_KEY(LGUI,"Meta"); BIB_SDL_KEY(RGUI,"Meta");
    BIB_SDL_KEY(MODE,"AltGraph"); BIB_SDL_KEY(CAPSLOCK,"CapsLock"); BIB_SDL_KEY(NUMLOCKCLEAR,"NumLock");
    BIB_SDL_KEY(SCROLLLOCK,"ScrollLock"); BIB_SDL_KEY(PRINTSCREEN,"PrintScreen"); BIB_SDL_KEY(PAUSE,"Pause");
    BIB_SDL_KEY(MUTE,"AudioVolumeMute"); BIB_SDL_KEY(AUDIOMUTE,"AudioVolumeMute");
    BIB_SDL_KEY(VOLUMEUP,"AudioVolumeUp"); BIB_SDL_KEY(VOLUMEDOWN,"AudioVolumeDown");
    BIB_SDL_KEY(KP_0,"0"); BIB_SDL_KEY(KP_1,"1"); BIB_SDL_KEY(KP_2,"2"); BIB_SDL_KEY(KP_3,"3");
    BIB_SDL_KEY(KP_4,"4"); BIB_SDL_KEY(KP_5,"5"); BIB_SDL_KEY(KP_6,"6"); BIB_SDL_KEY(KP_7,"7");
    BIB_SDL_KEY(KP_8,"8"); BIB_SDL_KEY(KP_9,"9"); BIB_SDL_KEY(KP_PERIOD,"."); BIB_SDL_KEY(KP_EQUALS,"=");
    BIB_SDL_KEY(KP_DIVIDE,"/"); BIB_SDL_KEY(KP_MULTIPLY,"*"); BIB_SDL_KEY(KP_MINUS,"-"); BIB_SDL_KEY(KP_PLUS,"+");
    default: return value > 0 && !(value & SDLK_SCANCODE_MASK) ? scalar(static_cast<std::uint32_t>(value)) : "Unidentified";
    }
#undef BIB_SDL_KEY
}
bool bounded_text(const std::string& text) { return text.size() <= NativeEditorCapture::max_text_bytes && S::valid_text(text); }
std::optional<std::string> fixed_text(const char* text, std::size_t capacity) {
    std::size_t length=0;
    while (length<capacity && text[length]) ++length;
    if (length==capacity) return {};
    std::string result(text,length);
    return bounded_text(result) ? std::optional<std::string>(std::move(result)) : std::nullopt;
}
E::TextObservation observed(std::string text, S::ByteRange selection) {
    return capture_native_editor_text(std::move(text),selection,
        selection.begin==selection.end ? E::Direction::none : E::Direction::forward);
}
}

std::uint32_t sdl_surface_modifiers(SDL_Keymod value) noexcept {
    return ((value&KMOD_SHIFT) ? S::shift : 0u) | ((value&KMOD_CTRL) ? S::control : 0u) |
        ((value&KMOD_ALT) ? S::alt : 0u) | ((value&KMOD_GUI) ? S::meta : 0u) | ((value&KMOD_MODE) ? S::alt_graph : 0u);
}
S::KeyTransition sdl_surface_key(const SDL_KeyboardEvent& event) {
    const auto scancode=event.keysym.scancode;
    unsigned location=0;
    if (scancode==SDL_SCANCODE_LSHIFT || scancode==SDL_SCANCODE_LCTRL || scancode==SDL_SCANCODE_LALT || scancode==SDL_SCANCODE_LGUI) location=1;
    else if (scancode==SDL_SCANCODE_RSHIFT || scancode==SDL_SCANCODE_RCTRL || scancode==SDL_SCANCODE_RALT || scancode==SDL_SCANCODE_RGUI) location=2;
    else if ((scancode>=SDL_SCANCODE_KP_DIVIDE && scancode<=SDL_SCANCODE_KP_PERIOD) || scancode==SDL_SCANCODE_KP_EQUALS) location=3;
    const auto modifiers=static_cast<SDL_Keymod>(event.keysym.mod);
    return {event.type==SDL_KEYUP ? S::KeyPhase::up : S::KeyPhase::down,
        scancode==SDL_SCANCODE_RALT && (modifiers&KMOD_MODE) ? "AltGraph" : key(event.keysym.sym),
        code(scancode),location,sdl_surface_modifiers(modifiers),event.repeat!=0};
}
std::optional<unsigned> sdl_surface_button(Uint8 value) noexcept {
    switch (value) {
    case SDL_BUTTON_LEFT: return 0; case SDL_BUTTON_MIDDLE: return 1; case SDL_BUTTON_RIGHT: return 2;
    case SDL_BUTTON_X1: return 3; case SDL_BUTTON_X2: return 4; default: return {};
    }
}
unsigned sdl_surface_buttons(Uint32 value) noexcept {
    unsigned result=0;
    for (const auto native : {SDL_BUTTON_LEFT,SDL_BUTTON_MIDDLE,SDL_BUTTON_RIGHT,SDL_BUTTON_X1,SDL_BUTTON_X2})
        if (value&SDL_BUTTON(native)) result|=S::mouse_button_bit(*sdl_surface_button(static_cast<Uint8>(native)));
    return result;
}

struct NativeSdlSurfaceInput::Impl {
    struct HeldKey { S::KeyTransition identity; bool editor{}; };
    NativeSurfaceIngress ingress;
    NativeSurfaceMode mode;
    Hooks hooks;
    bool blocked{}, entering{};
    unsigned buttons{};
    std::uint64_t token{}, next_token{1}, next_transaction{1}, transaction{}, mutation{};
    double x{}, y{};
    std::optional<E::TextObservation> value, composition_before;
    S::ByteRange composition_range;
    std::vector<HeldKey> held;
    std::optional<S::Identity> context;
    std::optional<std::pair<bool,bool>> focus;
    std::optional<std::pair<std::int64_t,std::int64_t>> drawable;
    std::optional<bool> foreground;
    std::uint64_t facts_serial{};
    bool focus_due{true},suspending{};
    NativeEditorAdmission admission{NativeEditorAdmission::withdrawn};
    bool raw_available{true};
    Impl(NativeSurfaceIngress i, NativeSurfaceMode m, Hooks h) : ingress(std::move(i)),mode(m),hooks(std::move(h)) {
        if (!ingress.input || !ingress.invalidate || !hooks.capture || !hooks.modifiers ||
            (m==NativeSurfaceMode::editor_v1 && (!ingress.editor || !hooks.text_input || !hooks.caret || !hooks.clear_composition)))
            throw std::invalid_argument("Incomplete SDL Surface hooks");
        held.reserve(64);
    }
    std::uint32_t modifiers() const { return sdl_surface_modifiers(hooks.modifiers()); }
    bool send(S::Input input) { return ingress.input(std::move(input)).status==S::Status::ok; }
    gui::Point point(double px,double py) const {
        const auto result=hooks.point ? hooks.point({px,py}) : gui::Point{px,py};
        if (!std::isfinite(result.x)||!std::isfinite(result.y)) throw std::invalid_argument("Invalid SDL input transform");
        return result;
    }
    void release() noexcept {
        buttons=0;token=0;
        try { hooks.capture(false); } catch (...) {}
    }
    void suspend() noexcept {
        ++mutation;blocked=true;admission=NativeEditorAdmission::withdrawn;
        if (suspending) return;
        suspending=true;
        held.clear();value.reset();composition_before.reset();transaction=0;composition_range={};release();
        try { if (hooks.text_input) hooks.text_input(false); } catch (...) {}
        try { if (hooks.clear_composition) hooks.clear_composition(); } catch (...) {}
        suspending=false;
    }
    void invalidate(S::RevocationReason reason) {
        suspend();ingress.invalidate(reason);
    }
    bool mouse(S::MouseTransition input) {
        const auto before=mutation;
        if (!send(std::move(input))) { invalidate(S::RevocationReason::unavailable); return false; }
        return before==mutation;
    }
    void cancel() {
        if (token) { S::MouseTransition input;input.phase=S::MousePhase::cancel;input.capture_token=token;(void)send(input); }
        release();
    }
    void emit_focus(bool focused,bool active) {
        if (!focus_due && focus==std::pair{focused,active}) return;
        const auto before=context;
        if (send(S::FocusChange{focused,active,S::FocusCause::external})) {
            focus=std::pair{focused,active};
            if (bool(before)==bool(context) && (!before || (before->owner==context->owner && before->generation==context->generation &&
                before->epoch==context->epoch && before->context==context->context))) focus_due=false;
        }
    }
    bool observe(NativeEditorObservation input) {
        const auto before=mutation;
        const auto after=input.after;
        if (!ingress.editor(std::move(input))) { invalidate(S::RevocationReason::unavailable);return false; }
        if (before!=mutation) return false;
        if (after) value=*after;
        return true;
    }
    bool text(std::string text, bool preedit) {
        if (!value || blocked) return true;
        if (!bounded_text(text)) { invalidate(S::RevocationReason::unavailable);return true; }
        const bool begin=preedit&&!transaction;
        if (begin && !next_transaction) { invalidate(S::RevocationReason::unavailable);return true; }
        const auto replacement=transaction ? composition_range : value->selection;
        if (!S::valid_range(value->value,replacement) || text.size()>NativeEditorCapture::max_text_bytes-(value->value.size()-(replacement.end-replacement.begin))) {
            invalidate(S::RevocationReason::unavailable);return true;
        }
        auto full=value->value.substr(0,replacement.begin)+text+value->value.substr(replacement.end);
        auto after=observed(std::move(full),{replacement.begin+text.size(),replacement.begin+text.size()});
        NativeEditorObservation input;
        input.before=*value;input.after=after;
        if (preedit || transaction) {
            const auto selected_transaction=begin ? next_transaction : transaction;
            input.kind=E::Kind::composition;input.transaction=selected_transaction;
            input.authority=begin ? E::Authority::range : E::Authority::composition;
            E::CompositionData data;
            data.operation=begin ? S::CompositionOperation::begin : preedit ? S::CompositionOperation::update : S::CompositionOperation::commit;
            data.text=std::move(text);data.selection={data.text.size(),data.text.size()};
            if (begin) data.replacement=value->selection;
            input.data=std::move(data);
            const auto original=*value;
            if (observe(std::move(input))) {
                if (begin) { composition_before=original;transaction=next_transaction;next_transaction=next_transaction==UINT64_MAX ? 0 : next_transaction+1; }
                composition_range={replacement.begin,after.selection.end};
                if (!preedit) { transaction=0;composition_before.reset();composition_range={}; }
            }
        } else {
            input.kind=E::Kind::text;input.authority=E::Authority::range;
            input.data=E::TextData{"insertText",std::move(text),value->selection,{}};
            (void)observe(std::move(input));
        }
        return true;
    }
};

NativeSdlSurfaceInput::NativeSdlSurfaceInput(NativeSurfaceIngress input,NativeSurfaceMode mode,Hooks hooks)
    : impl_(std::make_unique<Impl>(std::move(input),mode,std::move(hooks))) {}
NativeSdlSurfaceInput::~NativeSdlSurfaceInput() { impl_->suspend(); }
void NativeSdlSurfaceInput::suspend() noexcept { impl_->suspend(); }
void NativeSdlSurfaceInput::invalidate(S::RevocationReason reason) { impl_->invalidate(reason); }
void NativeSdlSurfaceInput::activate(bool focused,bool active) {
    auto& self=*impl_;
    if (self.mode==NativeSurfaceMode::none || self.suspending) return;
    if (self.admission==NativeEditorAdmission::paused) {
        if (!focused || !active) self.invalidate(focused ? S::RevocationReason::unavailable : S::RevocationReason::focus_loss);
        return;
    }
    self.blocked=false;
    self.emit_focus(focused,active);
    if (!focused || !active) self.suspend();
}
void NativeSdlSurfaceInput::platform_facts(std::int64_t width,std::int64_t height,bool foreground) {
    auto& self=*impl_;
    if (width<0 || height<0) throw std::invalid_argument("Negative actual SDL drawable extent");
    if (self.facts_serial==UINT64_MAX) throw std::overflow_error("SDL platform fact serial exhausted");
    const auto serial=++self.facts_serial;
    const auto entry=self.mutation;
    const auto extent=std::pair{width,height};
    if (self.drawable!=extent) {
        self.drawable=extent;
        if (self.ingress.drawable_pixels) self.ingress.drawable_pixels(width,height);
        if (entry!=self.mutation || serial!=self.facts_serial) return;
    }
    if (self.foreground!=foreground) {
        self.foreground=foreground;
        if (self.ingress.foreground) self.ingress.foreground(foreground);
    }
}
unsigned NativeSdlSurfaceInput::held_buttons() const noexcept { return impl_->buttons; }
std::uint64_t NativeSdlSurfaceInput::capture_token() const noexcept { return impl_->token; }
const E::TextObservation* NativeSdlSurfaceInput::draft() const noexcept { return impl_->value ? &*impl_->value : nullptr; }

void NativeSdlSurfaceInput::editor(const NativeEditorPresentation& presentation) {
    auto& self=*impl_;
    if (self.suspending) return;
    const auto entry=++self.mutation;
    if (presentation.surface) {
        const auto& next=presentation.surface->identity;
        if (!self.context || self.context->owner!=next.owner || self.context->generation!=next.generation ||
            self.context->epoch!=next.epoch || self.context->context!=next.context) self.focus_due=true;
        self.context=next;
    }
    self.raw_available=presentation.surface && presentation.surface->available;
    if (self.mode==NativeSurfaceMode::editor_v1 && presentation.admission==NativeEditorAdmission::paused) {
        self.admission=NativeEditorAdmission::paused;
        // Capture owns the only causal queue and its already-owned Basis.
        // This is correlation, not a publication or permission to enter native.
        if (presentation.draft) {
            const auto& draft=*presentation.draft;
            if (!bounded_text(draft.value) || capture_native_editor_text(draft.value,draft.selection_start,
                    draft.selection_end,draft.selection_direction)!=draft) {
                self.invalidate(S::RevocationReason::unavailable);return;
            }
            self.value=draft;
        }
        if (!self.raw_available) {
            self.release();
            self.focus_due=true; // The unavailable pair retired Policy's local focus.
        }
        if (entry==self.mutation) self.blocked=false;
        return; // Never stop/restart IME, move its caret or replace its passage.
    }
    self.admission=presentation.admission;
    if (!self.raw_available) { self.suspend();return; }
    self.blocked=false;
    if (self.mode!=NativeSurfaceMode::editor_v1) return;
    const auto* basis=presentation.publication && presentation.publication->basis ? &*presentation.publication->basis : nullptr;
    if (presentation.admission!=NativeEditorAdmission::active || !basis || !presentation.context ||
        !presentation.context->editable || !bounded_text(basis->surrounding)) {
        self.value.reset();self.composition_before.reset();self.transaction=0;
        self.hooks.text_input(false);
        if (entry==self.mutation) self.hooks.clear_composition();
        return;
    }
    if (presentation.draft) {
        const auto& supplied=*presentation.draft;
        if (!bounded_text(supplied.value) || capture_native_editor_text(supplied.value,supplied.selection_start,
                supplied.selection_end,supplied.selection_direction)!=supplied) {
            self.invalidate(S::RevocationReason::unavailable);return;
        }
        self.value=supplied;
    }
    else self.value=capture_native_editor_text(basis->surrounding,basis->selection,
        basis->backward ? E::Direction::backward : basis->selection.begin==basis->selection.end ? E::Direction::none : E::Direction::forward);
    const bool ongoing=presentation.composition && presentation.composition->state!=E::CompositionState::ended;
    if ((!presentation.preserve_passage && !ongoing) ||
        (presentation.composition && presentation.composition->state==E::CompositionState::ended)) {
        self.transaction=0;self.composition_before.reset();self.composition_range={};
    }
    auto caret=presentation.context->caret;
    const auto& clip=presentation.surface->clip;
    const auto right=std::min(caret.x+caret.width,clip.x+clip.width);
    const auto bottom=std::min(caret.y+caret.height,clip.y+clip.height);
    caret.x=std::clamp(caret.x,clip.x,clip.x+clip.width);
    caret.y=std::clamp(caret.y,clip.y,clip.y+clip.height);
    caret.width=std::max(0.0,right-caret.x);caret.height=std::max(0.0,bottom-caret.y);
    self.hooks.caret(caret);
    if (entry==self.mutation && !self.blocked && self.value) self.hooks.text_input(true);
}

bool NativeSdlSurfaceInput::event(const SDL_Event& event) {
    auto& self=*impl_;
    // Own allocated SDL payloads before every rejection, including reentry and
    // mode-none. SDL's event union itself does not release this pointer.
    std::unique_ptr<char,decltype(&SDL_free)> extended(event.type==SDL_TEXTEDITING_EXT ? event.editExt.text : nullptr,SDL_free);
    if (self.mode==NativeSurfaceMode::none) return event.type==SDL_TEXTEDITING_EXT;
    if (self.entering) { self.invalidate(S::RevocationReason::unavailable);return true; }
    struct Enter { bool& value; explicit Enter(bool& v):value(v){value=true;} ~Enter(){value=false;} } turn(self.entering);
    if (event.type==SDL_WINDOWEVENT) {
        if (event.window.event==SDL_WINDOWEVENT_FOCUS_LOST) {
            if (self.admission==NativeEditorAdmission::paused) { self.invalidate(S::RevocationReason::focus_loss);return true; }
            self.cancel();self.emit_focus(false,true);self.suspend();return true;
        }
        if (event.window.event==SDL_WINDOWEVENT_FOCUS_GAINED) {
            if (self.admission==NativeEditorAdmission::paused) { self.focus_due=true;return true; }
            self.emit_focus(true,true);return true;
        }
        if (event.window.event==SDL_WINDOWEVENT_HIDDEN || event.window.event==SDL_WINDOWEVENT_MINIMIZED) {
            if (self.admission==NativeEditorAdmission::paused) { self.invalidate(S::RevocationReason::unavailable);return true; }
            self.cancel();self.emit_focus(false,false);self.suspend();return true;
        }
        return false;
    }
    if (event.type==SDL_TEXTEDITING_EXT) {
        // SDL owns an allocated pointer even when ingress is suspended.
        if (self.blocked || self.mode!=NativeSurfaceMode::editor_v1) return true;
        if (!extended) { self.invalidate(S::RevocationReason::unavailable);return true; }
        auto text=fixed_text(extended.get(),NativeEditorCapture::max_text_bytes+1);
        if (!text) { self.invalidate(S::RevocationReason::unavailable);return true; }
        return self.text(std::move(*text),true);
    }
    if (self.blocked) return event.type==SDL_KEYDOWN || event.type==SDL_KEYUP || event.type==SDL_TEXTINPUT || event.type==SDL_TEXTEDITING ||
        event.type==SDL_MOUSEBUTTONDOWN || event.type==SDL_MOUSEBUTTONUP || event.type==SDL_MOUSEMOTION || event.type==SDL_MOUSEWHEEL;
    if (event.type==SDL_KEYDOWN || event.type==SDL_KEYUP) {
        auto key_event=sdl_surface_key(event.key);
        const auto found=std::find_if(self.held.begin(),self.held.end(),[&](const Impl::HeldKey& item) {
            return item.identity.location==key_event.location &&
                (item.identity.code.empty() && key_event.code.empty() ? item.identity.key==key_event.key :
                    !item.identity.code.empty() && item.identity.code==key_event.code);
        });
        const bool existing=found!=self.held.end(),up=event.type==SDL_KEYUP;
        if ((up || key_event.repeat) && !existing) return true;
        if (!existing && self.held.size()==64) { self.invalidate(S::RevocationReason::unavailable);return true; }
        const auto slot=existing ? static_cast<std::size_t>(found-self.held.begin()) : self.held.size();
        const bool editor=existing ? found->editor : self.mode==NativeSurfaceMode::editor_v1 && self.value.has_value();
        if (up && existing && !editor && !self.raw_available) {
            // The unavailable pair already retired Policy's body ownership.
            // Its native cleanup belongs to App; preserve the paused IME passage.
            self.held.erase(self.held.begin()+static_cast<std::ptrdiff_t>(slot));
            return true;
        }
        Impl::HeldKey retained{key_event,editor}; // All fallible copies precede ingress admission.
        const auto mutation=self.mutation;
        const bool context=event.type==SDL_KEYDOWN && !event.key.repeat &&
            (key_event.key=="ContextMenu" || (key_event.key=="F10" && (key_event.modifiers&S::shift)));
        bool accepted=false;
        if (editor && self.value) {
            NativeEditorObservation input;input.kind=E::Kind::key;input.authority=E::Authority::native;input.before=*self.value;input.after=input.before;
            input.data=E::KeyData{std::move(key_event),self.transaction!=0};accepted=self.observe(std::move(input));
        } else if (!editor) accepted=self.send(std::move(key_event));
        // A retired editor's native cleanup belongs to Capture. Its late UP
        // must never become a fresh body event under another mapping.
        if (mutation==self.mutation) {
            if (up && existing && !accepted && !editor) self.invalidate(S::RevocationReason::unavailable);
            else if (up && existing) self.held.erase(self.held.begin()+static_cast<std::ptrdiff_t>(slot));
            else if (accepted && !existing) self.held.push_back(std::move(retained));
        }
        if (context && !self.blocked && self.raw_available) { S::MouseTransition input;input.phase=S::MousePhase::context;
            input.context_origin=S::ContextOrigin::keyboard;input.capture_token=self.token;input.buttons=self.buttons;(void)self.mouse(input); }
        return true;
    }
    if (event.type==SDL_TEXTINPUT || event.type==SDL_TEXTEDITING) {
        if (self.mode!=NativeSurfaceMode::editor_v1) return true;
        auto text=event.type==SDL_TEXTINPUT ? fixed_text(event.text.text,sizeof event.text.text) : fixed_text(event.edit.text,sizeof event.edit.text);
        if (!text) { self.invalidate(S::RevocationReason::unavailable);return true; }
        // An empty preedit is an actual provisional update, not evidence that
        // native composition was cancelled. TEXTINPUT explicitly commits it.
        return self.text(std::move(*text),event.type==SDL_TEXTEDITING);
    }
    if (event.type==SDL_FINGERDOWN || event.type==SDL_FINGERMOTION || event.type==SDL_FINGERUP) return true; // No raw_pointer capability.
    if (!self.raw_available && (event.type==SDL_MOUSEBUTTONDOWN || event.type==SDL_MOUSEBUTTONUP ||
        event.type==SDL_MOUSEMOTION || event.type==SDL_MOUSEWHEEL)) return true;
    if (event.type==SDL_MOUSEBUTTONDOWN || event.type==SDL_MOUSEBUTTONUP) {
        if (event.button.which==SDL_TOUCH_MOUSEID) return true;
        const auto button=sdl_surface_button(event.button.button);if (!button) return true;
        const bool down=event.type==SDL_MOUSEBUTTONDOWN;
        const auto bit=S::mouse_button_bit(*button);
        if (down ? bool(self.buttons&bit) : !bool(self.buttons&bit)) return true;
        const auto mutation=self.mutation;
        std::uint64_t token=self.token;
        if (down&&!self.buttons) {
            if (!self.next_token) { self.invalidate(S::RevocationReason::unavailable);return true; }
            token=self.next_token;self.next_token=token==UINT64_MAX ? 0 : token+1;
            if (!self.hooks.capture(true) || mutation!=self.mutation) { self.invalidate(S::RevocationReason::unavailable);return true; }
        }
        S::MouseTransition input;input.phase=down ? S::MousePhase::down : S::MousePhase::up;
        input.capture_token=token;input.button=*button;input.buttons=down ? self.buttons|bit : self.buttons&~bit;
        const auto point=self.point(event.button.x,event.button.y);
        input.x=point.x;input.y=point.y;input.clicks=event.button.clicks<=3 ? event.button.clicks : 0;
        input.modifiers=self.modifiers();
        const auto next=input.buttons;
        if (!self.mouse(input)) return true;
        self.token=next ? token : 0;self.buttons=next;self.x=input.x;self.y=input.y;
        if (!next && !self.hooks.capture(false)) { self.invalidate(S::RevocationReason::unavailable);return true; }
        if (down&&*button==2) { input.phase=S::MousePhase::context;input.button=0;input.clicks=0;
            input.capture_token=self.token;input.buttons=self.buttons;(void)self.mouse(input); }
        return true;
    }
    if (event.type==SDL_MOUSEMOTION) {
        if (event.motion.which==SDL_TOUCH_MOUSEID) return true;
        if (sdl_surface_buttons(event.motion.state)!=self.buttons) { self.invalidate(S::RevocationReason::unavailable);return true; }
        S::MouseTransition input;input.phase=S::MousePhase::move;input.capture_token=self.token;input.buttons=self.buttons;
        const auto point=self.point(event.motion.x,event.motion.y);
        input.x=point.x;input.y=point.y;input.modifiers=self.modifiers();
        if (self.mouse(input)) { self.x=input.x;self.y=input.y; }
        return true;
    }
    if (event.type==SDL_MOUSEWHEEL) {
        if (event.wheel.which==SDL_TOUCH_MOUSEID) return true;
        S::MouseTransition input;input.phase=S::MousePhase::wheel;input.capture_token=self.token;input.buttons=self.buttons;
#if SDL_VERSION_ATLEAST(2,26,0)
        const auto point=self.point(event.wheel.mouseX,event.wheel.mouseY);
        input.x=point.x;input.y=point.y;
#else
        input.x=self.x;input.y=self.y;
#endif
        const float direction=event.wheel.direction==SDL_MOUSEWHEEL_FLIPPED ? -1.0f : 1.0f;
#if SDL_VERSION_ATLEAST(2,0,18)
        input.wheel_x=event.wheel.preciseX*direction;input.wheel_y=event.wheel.preciseY*direction;
#else
        input.wheel_x=static_cast<float>(event.wheel.x)*direction;input.wheel_y=static_cast<float>(event.wheel.y)*direction;
#endif
        input.modifiers=self.modifiers();
        if (input.wheel_x || input.wheel_y) (void)self.mouse(input);
        return true;
    }
    return false;
}

struct NativeSdlSurfacePeer::Impl {
    gui::FramebufferAdapter& adapter;
    std::unique_ptr<SDL_Window,decltype(&SDL_DestroyWindow)> window{nullptr,SDL_DestroyWindow};
    std::unique_ptr<SDL_Renderer,decltype(&SDL_DestroyRenderer)> renderer{nullptr,SDL_DestroyRenderer};
    std::unique_ptr<SDL_Texture,decltype(&SDL_DestroyTexture)> texture{nullptr,SDL_DestroyTexture};
    unsigned texture_width{},texture_height{};
    std::uint64_t displayed{};
    gui::Frame frame;
    bool alive{true},presenting{};
    NativeSurfaceMode mode;
    std::unique_ptr<NativeSdlSurfaceInput> input;
    double origin_x{},origin_y{},scale_x{1},scale_y{1};
    Impl(gui::FramebufferAdapter& a,const NativeSurfaceWindow& config,NativeSurfaceIngress ingress,NativeSurfaceMode selected,bool hidden)
        : adapter(a),mode(selected) {
        if (!std::isfinite(config.width)||!std::isfinite(config.height)||config.width<=0||config.height<=0||
            config.width>16384||config.height>16384||!std::isfinite(config.scale)||config.scale<=0)
            throw std::invalid_argument("Invalid SDL Surface window");
        window.reset(SDL_CreateWindow(config.title.c_str(),SDL_WINDOWPOS_CENTERED,SDL_WINDOWPOS_CENTERED,
            static_cast<int>(config.width),static_cast<int>(config.height),SDL_WINDOW_RESIZABLE|SDL_WINDOW_ALLOW_HIGHDPI|(hidden?SDL_WINDOW_HIDDEN:0)));
        require(bool(window),"Window creation failed");
        renderer.reset(SDL_CreateRenderer(window.get(),-1,SDL_RENDERER_SOFTWARE));require(bool(renderer),"Renderer creation failed");
        int width=0,height=0,physical_width=0,physical_height=0;
        SDL_GetWindowSize(window.get(),&width,&height);
        require(SDL_GetRendererOutputSize(renderer.get(),&physical_width,&physical_height)==0,"Cannot query initial renderer size");
        if (width>0 && height>0 && physical_width>0 && physical_height>0)
            adapter.resize({double(width),double(height)},double(physical_width)/width);
        if (selected==NativeSurfaceMode::editor_v1) {
            // Every long preedit must remain owned and complete. Default SDL2
            // fixed-size editing events may truncate; the opt-in is mandatory.
            require(SDL_SetHint(SDL_HINT_IME_SUPPORT_EXTENDED_TEXT,"1")==SDL_TRUE,"Extended IME text unavailable");
            require(SDL_SetHint(SDL_HINT_IME_INTERNAL_EDITING,"0")==SDL_TRUE,"External IME editing unavailable");
            (void)SDL_SetHint(SDL_HINT_IME_SHOW_UI,"1");
        }
        NativeSdlSurfaceInput::Hooks hooks;
        hooks.capture=[](bool capture) { return SDL_CaptureMouse(capture?SDL_TRUE:SDL_FALSE)==0; };
        hooks.modifiers=[] { return SDL_GetModState(); };
        hooks.text_input=[](bool active) { if (active) SDL_StartTextInput();else SDL_StopTextInput(); };
        hooks.clear_composition=[] { SDL_ClearComposition(); };
        hooks.caret=[this](S::Rect value) {
            if (!std::isfinite(value.x)||!std::isfinite(value.y)||!std::isfinite(value.width)||!std::isfinite(value.height)||
                std::abs(value.x)>1000000||std::abs(value.y)>1000000||value.width<0||value.height<0||value.width>1000000||value.height>1000000)
                throw std::invalid_argument("Invalid SDL editor caret");
            const double left=std::floor(origin_x+value.x*scale_x),top=std::floor(origin_y+value.y*scale_y);
            const double width=std::max(1.0,std::ceil(value.width*scale_x)),height=std::max(1.0,std::ceil(value.height*scale_y));
            const double maximum=std::numeric_limits<int>::max();
            if (!std::isfinite(left)||!std::isfinite(top)||!std::isfinite(width)||!std::isfinite(height)||
                std::abs(left)>maximum||std::abs(top)>maximum||width>maximum||height>maximum)
                throw std::invalid_argument("SDL editor caret transform exceeds native bounds");
            const SDL_Rect caret{static_cast<int>(left),static_cast<int>(top),static_cast<int>(width),static_cast<int>(height)};
            SDL_SetTextInputRect(&caret);
        };
        hooks.point=[this](gui::Point value) { return gui::Point{(value.x-origin_x)/scale_x,(value.y-origin_y)/scale_y}; };
        input=std::make_unique<NativeSdlSurfaceInput>(std::move(ingress),selected,std::move(hooks));
        SDL_StopTextInput();
    }
    ~Impl() { alive=false;if(input)input->suspend(); }
    std::pair<bool,bool> platform_facts() {
        int width=0,height=0;
        require(SDL_GetRendererOutputSize(renderer.get(),&width,&height)==0,"Cannot query actual SDL drawable extent");
        const auto flags=SDL_GetWindowFlags(window.get());
        const bool active=(flags&SDL_WINDOW_SHOWN) && !(flags&SDL_WINDOW_MINIMIZED);
        const bool focused=active && (flags&SDL_WINDOW_INPUT_FOCUS);
        input->platform_facts(width,height,focused);
        return {focused,active};
    }
    void paint() {
        if (!alive || !window || !renderer || presenting) throw std::logic_error("SDL Surface renderer is unavailable or reentrant");
        struct Paint { bool& value;explicit Paint(bool& v):value(v){value=true;}~Paint(){value=false;} } turn(presenting);
        auto next=adapter.frame(displayed);
        if (!next.width || !next.height || !next.pixels || next.width>static_cast<unsigned>(std::numeric_limits<int>::max()) ||
            next.height>static_cast<unsigned>(std::numeric_limits<int>::max()) || next.stride_bytes>static_cast<std::size_t>(std::numeric_limits<int>::max()))
            throw std::invalid_argument("SDL Surface frame is incomplete");
        if (!texture || texture_width!=next.width || texture_height!=next.height) {
            texture.reset(SDL_CreateTexture(renderer.get(),SDL_PIXELFORMAT_RGB24,SDL_TEXTUREACCESS_STREAMING,static_cast<int>(next.width),static_cast<int>(next.height)));
            require(bool(texture),"Texture creation failed");texture_width=next.width;texture_height=next.height;displayed=0;
        }
        if (!displayed) require(SDL_UpdateTexture(texture.get(),nullptr,next.pixels->data(),static_cast<int>(next.stride_bytes))==0,"Texture upload failed");
        else if (next.damage.width && next.damage.height) {
            if (next.damage.x>next.width || next.damage.y>next.height ||
                next.damage.width>next.width-next.damage.x || next.damage.height>next.height-next.damage.y)
                throw std::invalid_argument("SDL Surface damage exceeds its frame");
            const SDL_Rect damage{static_cast<int>(next.damage.x),static_cast<int>(next.damage.y),
                static_cast<int>(next.damage.width),static_cast<int>(next.damage.height)};
            require(SDL_UpdateTexture(texture.get(),&damage,next.pixels->data()+static_cast<std::size_t>(next.damage.y)*next.stride_bytes+static_cast<std::size_t>(next.damage.x)*3,
                static_cast<int>(next.stride_bytes))==0,"Damage upload failed");
        }
        int width=0,height=0,output_width=0,output_height=0;
        SDL_GetWindowSize(window.get(),&width,&height);
        require(SDL_GetRendererOutputSize(renderer.get(),&output_width,&output_height)==0,"Cannot query renderer extent");
        const auto canvas=adapter.snapshot().client_size;
        if (width<=0 || height<=0 || output_width<=0 || output_height<=0 || canvas.width<=0 || canvas.height<=0)
            throw std::invalid_argument("SDL Surface has no drawable extent");
        const double fit=std::min(double(output_width)/next.width,double(output_height)/next.height);
        const int target_width=std::max(1,static_cast<int>(std::floor(next.width*fit)));
        const int target_height=std::max(1,static_cast<int>(std::floor(next.height*fit)));
        const SDL_Rect target{(output_width-target_width)/2,(output_height-target_height)/2,target_width,target_height};
        require(SDL_SetRenderDrawColor(renderer.get(),0,0,0,255)==0,"Renderer background failed");
        require(SDL_RenderClear(renderer.get())==0,"Renderer clear failed");
        require(SDL_RenderCopy(renderer.get(),texture.get(),nullptr,&target)==0,"Frame presentation failed");
        SDL_RenderPresent(renderer.get());
        const double pixel_x=double(output_width)/width,pixel_y=double(output_height)/height;
        origin_x=target.x/pixel_x;origin_y=target.y/pixel_y;
        scale_x=target.w/(pixel_x*canvas.width);scale_y=target.h/(pixel_y*canvas.height);
        displayed=next.revision;frame=std::move(next);
    }
};

NativeSdlSurfacePeer::NativeSdlSurfacePeer(gui::FramebufferAdapter& adapter,const NativeSurfaceWindow& config,
    NativeSurfaceIngress ingress,NativeSurfaceMode mode,bool hidden)
    : impl_(std::make_shared<Impl>(adapter,config,std::move(ingress),mode,hidden)) {}
NativeSdlSurfacePeer::~NativeSdlSurfacePeer() { if(impl_){impl_->alive=false;impl_->input->suspend();} }
NativeSurfacePeer NativeSdlSurfacePeer::peer() const {
    const std::weak_ptr<Impl> weak=impl_;
    NativeSurfacePeer result;
    if (impl_->mode!=NativeSurfaceMode::none) {
        result.capabilities.supported=S::feature(S::Feature::raw_keys)|S::feature(S::Feature::focus)|S::feature(S::Feature::mouse_input);
        result.capabilities.mouse_input_version=S::mouse_input_version;
        if (impl_->mode==NativeSurfaceMode::editor_v1)
            result.capabilities.supported|=S::feature(S::Feature::committed_text)|S::feature(S::Feature::composition)|
                S::feature(S::Feature::surrounding_text)|S::feature(S::Feature::selection);
    }
    result.ready=[weak] { const auto self=weak.lock();return self&&self->alive&&self->window&&self->renderer; };
    result.present=[weak](gui::Snapshot view) {
        const auto self=weak.lock();if(!self||!self->alive)throw std::logic_error("SDL Surface lifetime ended");
        const auto revision=view.revision;
        try { self->adapter.present(std::move(view));self->paint(); }
        catch (...) { self->input->suspend();throw; }
        return NativeRenderReceipt{revision};
    };
    result.editor=[weak](const NativeEditorPresentation& value) { if(const auto self=weak.lock();self&&self->alive)self->input->editor(value); };
    result.suspend=[weak] { if(const auto self=weak.lock())self->input->suspend(); };
    result.activate=[weak] {
        if(const auto self=weak.lock();self&&self->alive) {
            const auto [focused,active]=self->platform_facts();
            if (self->alive) self->input->activate(focused,active);
        }
    };
    result.close=[weak] { if(const auto self=weak.lock()){self->input->suspend();self->alive=false;} };
    return result;
}
bool NativeSdlSurfacePeer::event(const SDL_Event& event) {
    auto& self=*impl_;
    std::unique_ptr<char,decltype(&SDL_free)> extended(event.type==SDL_TEXTEDITING_EXT ? event.editExt.text : nullptr,SDL_free);
    if (!self.alive) return true;
    const auto id=SDL_GetWindowID(self.window.get());
    if ((event.type==SDL_WINDOWEVENT && event.window.windowID!=id) ||
        ((event.type==SDL_KEYDOWN || event.type==SDL_KEYUP) && event.key.windowID!=id) ||
        (event.type==SDL_TEXTINPUT && event.text.windowID!=id) ||
        (event.type==SDL_TEXTEDITING && event.edit.windowID!=id) ||
        (event.type==SDL_TEXTEDITING_EXT && event.editExt.windowID!=id) ||
        ((event.type==SDL_MOUSEBUTTONDOWN || event.type==SDL_MOUSEBUTTONUP) && event.button.windowID!=id) ||
        (event.type==SDL_MOUSEMOTION && event.motion.windowID!=id) ||
        (event.type==SDL_MOUSEWHEEL && event.wheel.windowID!=id)) {
        return true;
    }
    if (event.type==SDL_WINDOWEVENT && (event.window.event==SDL_WINDOWEVENT_SIZE_CHANGED || event.window.event==SDL_WINDOWEVENT_RESIZED)) {
        self.input->invalidate();
        int width=0,height=0,physical_width=0,physical_height=0;
        SDL_GetWindowSize(self.window.get(),&width,&height);
        require(SDL_GetRendererOutputSize(self.renderer.get(),&physical_width,&physical_height)==0,"Cannot query renderer size");
        if (width>0 && height>0 && physical_width>0 && physical_height>0)
            self.adapter.resize({double(width),double(height)},double(physical_width)/width);
        if (self.alive) (void)self.platform_facts();
        return true;
    }
    extended.release(); // The input translator now owns every EXT exit path.
    const auto consumed=self.input->event(event);
    if (self.alive && event.type==SDL_WINDOWEVENT &&
        (event.window.event==SDL_WINDOWEVENT_FOCUS_LOST || event.window.event==SDL_WINDOWEVENT_FOCUS_GAINED ||
         event.window.event==SDL_WINDOWEVENT_HIDDEN || event.window.event==SDL_WINDOWEVENT_SHOWN ||
         event.window.event==SDL_WINDOWEVENT_MINIMIZED || event.window.event==SDL_WINDOWEVENT_RESTORED))
        (void)self.platform_facts();
    return consumed;
}
void NativeSdlSurfacePeer::redraw() { impl_->paint(); }
SDL_Window* NativeSdlSurfacePeer::window() const noexcept { return impl_->window.get(); }
SDL_Renderer* NativeSdlSurfacePeer::renderer() const noexcept { return impl_->renderer.get(); }
const gui::Frame& NativeSdlSurfacePeer::frame() const noexcept { return impl_->frame; }

} // namespace foundation::host
