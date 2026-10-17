// SPDX-License-Identifier: CC0-1.0
#pragma once

#include "native_fltk_surface_platform.hpp"
#include <FL/Fl.H>
#include <FL/Fl_Window.H>
#include <FL/x.H>
#include <X11/XKBlib.h>
#include <X11/keysym.h>
#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <limits>
#include <new>
#include <locale.h>
#include <langinfo.h>
#include <stdexcept>
#include <string_view>
#include <thread>
#include <utility>

// Xlib's legacy macro must not rewrite the neutral Status enum in consumers.
#ifdef Status
#undef Status
#endif

namespace foundation::host {
namespace fltk_x11_detail {

inline std::u32string scalars(std::string_view text) {
    if (text.size()>fltk_native_max_text_bytes) throw std::invalid_argument("X11 text byte limit");
    std::u32string result;
    for (std::size_t i=0;i<text.size();) {
        const auto first=static_cast<unsigned char>(text[i++]);
        char32_t value{}; unsigned remaining{};
        if (first<0x80) value=first;
        else if (first>=0xc2 && first<=0xdf) { value=first&31; remaining=1; }
        else if (first>=0xe0 && first<=0xef) { value=first&15; remaining=2; }
        else if (first>=0xf0 && first<=0xf4) { value=first&7; remaining=3; }
        else throw std::invalid_argument("Invalid X11 UTF-8 lead");
        const auto width=remaining+1;
        if (remaining>text.size()-i) throw std::invalid_argument("Incomplete X11 UTF-8");
        while (remaining--) {
            const auto next=static_cast<unsigned char>(text[i++]);
            if ((next&0xc0)!=0x80) throw std::invalid_argument("Invalid X11 UTF-8 continuation");
            value=(value<<6)|(next&63);
        }
        if (!value || value>0x10ffff || (value>=0xd800 && value<=0xdfff) ||
            (width==2 && value<0x80) || (width==3 && value<0x800) || (width==4 && value<0x10000))
            throw std::invalid_argument("Invalid X11 Unicode scalar");
        result.push_back(value);
    }
    return result;
}
inline std::string utf8(std::u32string_view text) {
    std::string result;
    for (const auto value:text) {
        if (!value || value>0x10ffff || (value>=0xd800 && value<=0xdfff)) throw std::invalid_argument("Invalid X11 wide scalar");
        if (value<0x80) result.push_back(static_cast<char>(value));
        else if (value<0x800) { result.push_back(static_cast<char>(0xc0|(value>>6))); result.push_back(static_cast<char>(0x80|(value&63))); }
        else if (value<0x10000) { result.push_back(static_cast<char>(0xe0|(value>>12))); result.push_back(static_cast<char>(0x80|((value>>6)&63))); result.push_back(static_cast<char>(0x80|(value&63))); }
        else { result.push_back(static_cast<char>(0xf0|(value>>18))); result.push_back(static_cast<char>(0x80|((value>>12)&63))); result.push_back(static_cast<char>(0x80|((value>>6)&63))); result.push_back(static_cast<char>(0x80|(value&63))); }
        if (result.size()>fltk_native_max_text_bytes) throw std::invalid_argument("X11 text byte limit");
    }
    return result;
}
inline bool command_control(std::u32string_view text) noexcept {
    return text.size()==1 && (text.front()<0x20 || text.front()==0x7f);
}
inline std::size_t utf16(std::u32string_view text,std::size_t position) {
    if (position>text.size()) throw std::invalid_argument("X11 scalar position outside text");
    std::size_t result{}; for (std::size_t i=0;i<position;++i) result+=text[i]>=0x10000 ? 2 : 1; return result;
}
inline std::size_t scalar_position(std::u32string_view text,std::size_t position) {
    std::size_t units{};
    for (std::size_t i=0;i<=text.size();++i) {
        if (units==position) return i;
        if (i<text.size()) units+=text[i]>=0x10000 ? 2 : 1;
        if (units>position) break;
    }
    throw std::invalid_argument("X11 selection splits a UTF-16 scalar");
}
inline gui_editor::TextObservation observation(std::u32string_view text,std::size_t start,std::size_t end,bool backward=false) {
    if (start>end || end>text.size()) throw std::invalid_argument("Invalid X11 native selection");
    gui_editor::TextObservation result;
    result.value=utf8(text); result.selection_start=utf16(text,start); result.selection_end=utf16(text,end);
    result.selection_direction=start==end ? gui_editor::Direction::none : backward ? gui_editor::Direction::backward : gui_editor::Direction::forward;
    result.selection={utf8(text.substr(0,start)).size(),utf8(text.substr(0,end)).size()}; result.byte_length=result.value.size(); return result;
}
inline void validate(const gui_editor::TextObservation& text) {
    const auto value=scalars(text.value);
    const auto start=scalar_position(value,text.selection_start),end=scalar_position(value,text.selection_end);
    if (text.selection_direction!=gui_editor::Direction::none && text.selection_direction!=gui_editor::Direction::forward &&
        text.selection_direction!=gui_editor::Direction::backward) throw std::invalid_argument("Invalid X11 selection direction");
    auto actual=observation(value,start,end,text.selection_direction==gui_editor::Direction::backward);
    actual.selection_direction=text.selection_direction;
    if (actual!=text) throw std::invalid_argument("X11 frontend text/selection disagreement");
}
struct PhysicalKey { std::string code; unsigned location{}; };
inline PhysicalKey physical(std::string_view name) {
    static constexpr std::array<std::string_view,10> digits{"Digit1","Digit2","Digit3","Digit4","Digit5","Digit6","Digit7","Digit8","Digit9","Digit0"};
    static constexpr std::array<std::string_view,12> upper{"KeyQ","KeyW","KeyE","KeyR","KeyT","KeyY","KeyU","KeyI","KeyO","KeyP","BracketLeft","BracketRight"};
    static constexpr std::array<std::string_view,11> middle{"KeyA","KeyS","KeyD","KeyF","KeyG","KeyH","KeyJ","KeyK","KeyL","Semicolon","Quote"};
    static constexpr std::array<std::string_view,10> lower{"KeyZ","KeyX","KeyC","KeyV","KeyB","KeyN","KeyM","Comma","Period","Slash"};
    const auto number=[&](std::string_view prefix)->unsigned {
        if (name.size()!=4 || name.substr(0,2)!=prefix || name[2]<'0' || name[2]>'9' || name[3]<'0' || name[3]>'9') return 0;
        return static_cast<unsigned>((name[2]-'0')*10+name[3]-'0');
    };
    if (const auto n=number("AE");n && n<=10) return {std::string(digits[n-1]),0};
    if (const auto n=number("AD");n && n<=upper.size()) return {std::string(upper[n-1]),0};
    if (const auto n=number("AC");n && n<=middle.size()) return {std::string(middle[n-1]),0};
    if (const auto n=number("AB");n && n<=lower.size()) return {std::string(lower[n-1]),0};
    if (const auto n=number("FK");n && n<=35) return {"F"+std::to_string(n),0};
    if (name.size()==3 && name.substr(0,2)=="KP" && name[2]>='0' && name[2]<='9') return {"Numpad"+std::string(1,name[2]),3};
    struct Entry { std::string_view name,code; unsigned location; };
    static constexpr Entry entries[]{
        {"AE11","Minus",0},{"AE12","Equal",0},{"TLDE","Backquote",0},{"BKSL","Backslash",0},{"LSGT","IntlBackslash",0},
        {"SPCE","Space",0},{"ESC","Escape",0},{"TAB","Tab",0},{"BKSP","Backspace",0},{"RTRN","Enter",0},
        {"DELE","Delete",0},{"INS","Insert",0},{"HOME","Home",0},{"END","End",0},{"PGUP","PageUp",0},{"PGDN","PageDown",0},
        {"LEFT","ArrowLeft",0},{"RGHT","ArrowRight",0},{"UP","ArrowUp",0},{"DOWN","ArrowDown",0},
        {"LFSH","ShiftLeft",1},{"RTSH","ShiftRight",2},{"LCTL","ControlLeft",1},{"RCTL","ControlRight",2},
        {"LALT","AltLeft",1},{"RALT","AltRight",2},{"LWIN","MetaLeft",1},{"RWIN","MetaRight",2},{"MENU","ContextMenu",0},
        {"CAPS","CapsLock",0},{"NMLK","NumLock",3},{"SCLK","ScrollLock",0},{"PRSC","PrintScreen",0},{"PAUS","Pause",0},
        {"KPEN","NumpadEnter",3},{"KPDL","NumpadDecimal",3},{"KPDC","NumpadDecimal",3},{"KPPT","NumpadComma",3},
        {"KPAD","NumpadAdd",3},{"KPSU","NumpadSubtract",3},{"KPMU","NumpadMultiply",3},{"KPDV","NumpadDivide",3},{"KPEQ","NumpadEqual",3}};
    for (const auto& entry:entries) if (entry.name==name) return {std::string(entry.code),entry.location};
    return {}; // An unknown real XKB name does not become a guessed code.
}
inline std::string logical(KeySym symbol) {
    struct Entry { KeySym symbol; std::string_view key; };
    static constexpr Entry entries[]{
        {XK_BackSpace,"Backspace"},{XK_Tab,"Tab"},{XK_ISO_Left_Tab,"Tab"},{XK_Return,"Enter"},{XK_KP_Enter,"Enter"},{XK_Escape,"Escape"},
        {XK_Delete,"Delete"},{XK_KP_Delete,"Delete"},{XK_Insert,"Insert"},{XK_KP_Insert,"Insert"},
        {XK_Home,"Home"},{XK_KP_Home,"Home"},{XK_End,"End"},{XK_KP_End,"End"},{XK_Page_Up,"PageUp"},{XK_KP_Page_Up,"PageUp"},
        {XK_Page_Down,"PageDown"},{XK_KP_Page_Down,"PageDown"},{XK_Left,"ArrowLeft"},{XK_KP_Left,"ArrowLeft"},
        {XK_Right,"ArrowRight"},{XK_KP_Right,"ArrowRight"},{XK_Up,"ArrowUp"},{XK_KP_Up,"ArrowUp"},{XK_Down,"ArrowDown"},{XK_KP_Down,"ArrowDown"},
        {XK_Shift_L,"Shift"},{XK_Shift_R,"Shift"},{XK_Control_L,"Control"},{XK_Control_R,"Control"},{XK_Alt_L,"Alt"},{XK_Alt_R,"Alt"},
        {XK_Meta_L,"Meta"},{XK_Meta_R,"Meta"},{XK_Super_L,"Meta"},{XK_Super_R,"Meta"},{XK_ISO_Level3_Shift,"AltGraph"},{XK_Mode_switch,"AltGraph"},
        {XK_Caps_Lock,"CapsLock"},{XK_Num_Lock,"NumLock"},{XK_Scroll_Lock,"ScrollLock"},{XK_Menu,"ContextMenu"},{XK_Print,"PrintScreen"},{XK_Pause,"Pause"},
        {XK_KP_Add,"+"},{XK_KP_Subtract,"-"},{XK_KP_Multiply,"*"},{XK_KP_Divide,"/"},{XK_KP_Decimal,"."},{XK_KP_Separator,","}};
    for (const auto& entry:entries) if (entry.symbol==symbol) return std::string(entry.key);
    if (symbol>=XK_F1 && symbol<=XK_F35) return "F"+std::to_string(symbol-XK_F1+1);
    if (symbol>=XK_KP_0 && symbol<=XK_KP_9) return std::string(1,static_cast<char>('0'+symbol-XK_KP_0));
    if ((symbol>=0x20 && symbol<=0x7e) || (symbol>=0xa0 && symbol<=0xff)) return utf8(std::u32string(1,static_cast<char32_t>(symbol)));
    if ((symbol&0xff000000)==0x01000000) return utf8(std::u32string(1,static_cast<char32_t>(symbol&0x00ffffff)));
    if (symbol>=XK_dead_grave && symbol<=XK_dead_currency) return "Dead";
    return "Unidentified";
}
} // namespace fltk_x11_detail

// Owns one XIC and one actual native window. No global locale, IM enable state,
// keyboard-repeat setting, keyboard grab or foreign pointer grab is changed.
class FltkNativePlatform final {
    Fl_Window& window_;
    FltkNativePlatformCallbacks callbacks_;
    const std::thread::id thread_{std::this_thread::get_id()};
    Display* display_{};
    ::Window xid_{};
    XIM im_{};
    XIC ic_{};
    bool registered_{},xim_supported_{},ic_focused_{},foreground_{true},failed_{},closing_{},polling_{},capture_{},resetting_{},suspended_{};
    bool preedit_done_{};
    std::array<fltk_x11_detail::PhysicalKey,256> physical_;
    std::array<fltk_x11_detail::PhysicalKey,256> held_physical_;
    std::array<bool,256> held_{};
    std::array<bool,256> native_down_{};
    std::array<unsigned,256> native_modifiers_{};
    unsigned minimum_keycode_{8},maximum_keycode_{255};
    unsigned alt_mask_{},meta_mask_{},alt_graph_mask_{};
    std::optional<FltkNativeEditorConfiguration> configuration_;
    std::u32string draft_,preedit_;
    std::size_t selection_start_{},selection_end_{},preedit_caret_{},queued_bytes_{},passage_bytes_{};
    bool selection_backward_{};
    std::uint64_t transaction_{},next_transaction_{1};
    std::deque<FltkNativePassage> pending_;
    std::optional<FltkNativePassage> passage_;
    std::optional<std::string> failure_;
    bool failure_without_storage_{};
    XIMStringConversionText conversion_{};
    // FLTK unregisters by function, not (function,data). One shared dispatcher
    // stays installed until its last owned window has explicitly left.
    inline static std::array<FltkNativePlatform*,64> windows_{};
    inline static FltkNativePlatform* capture_owner_{};

    void owner() const { if (thread_!=std::this_thread::get_id()) throw std::logic_error("X11 Surface requires its owner thread"); }
    void fail(std::string_view reason) noexcept {
        failed_=true; xim_supported_=false;
        if (failure_ || failure_without_storage_) return;
        try { failure_=std::string(reason); } catch (...) { failure_without_storage_=true; }
    }
    bool owned_focus(::Window focus) const noexcept {
        if (!focus || focus==PointerRoot) return false;
        for (unsigned n=0;n<64 && focus;++n) {
            if (focus==xid_) return true;
            ::Window root{},parent{}; ::Window* children{}; unsigned count{};
            if (!XQueryTree(display_,focus,&root,&parent,&children,&count)) return false;
            if (children) XFree(children);
            if (!parent || parent==focus || parent==root) return parent==xid_;
            focus=parent;
        }
        return false;
    }
    bool foreign_routing() const noexcept {
        return (Fl::grab() && Fl::grab()!=&window_) || (Fl::pushed() && !window_.contains(Fl::pushed()));
    }
    static int system_event(void* raw,void*) noexcept {
        if (!raw) return 0;
        auto& event=*static_cast<XEvent*>(raw);
        for (auto* value:windows_) if (value && value->display_==event.xany.display) {
            try { if (value->receive(event)) return 1; }
            catch (...) { value->passage_.reset(); value->fail("Exception in owned X11 keyboard/IME passage"); return event.xany.window==value->xid_ ? 1 : 0; }
        }
        return 0;
    }
    void register_window() {
        for (const auto* value:windows_) if (value && (value->thread_!=thread_ || (value->display_==display_ && value->xid_==xid_)))
            throw std::runtime_error("Duplicate or foreign-thread X11 native window registration");
        const auto free=std::find(windows_.begin(),windows_.end(),nullptr);
        if (free==windows_.end()) throw std::runtime_error("X11 native window registration limit");
        const bool first=std::none_of(windows_.begin(),windows_.end(),[](auto* value) { return value!=nullptr; });
        *free=this; registered_=true;
        if (first) Fl::add_system_handler(system_event,nullptr);
    }
    void unregister_window() noexcept {
        for (auto& value:windows_) if (value==this) value=nullptr;
        if (registered_ && std::none_of(windows_.begin(),windows_.end(),[](auto* value) { return value!=nullptr; }))
            Fl::remove_system_handler(system_event);
        registered_=false;
    }
    KeySym keyboard_map(const XKeyEvent* key=nullptr) {
        int opcode{},event{},error{},major=XkbMajorVersion,minor=XkbMinorVersion;
        if (!XkbQueryExtension(display_,&opcode,&event,&error,&major,&minor)) throw std::runtime_error("X11 XKB physical key names unavailable");
        XkbDescPtr map=XkbGetKeyboard(display_,XkbAllComponentsMask,XkbUseCoreKbd);
        if (!map) throw std::runtime_error("X11 XKB keyboard unavailable");
        struct Free { XkbDescPtr value; ~Free() { XkbFreeKeyboard(value,XkbAllComponentsMask,True); } } free{map};
        if (!map->names || !map->names->keys) throw std::runtime_error("X11 XKB key names unavailable");
        minimum_keycode_=map->min_key_code; maximum_keycode_=map->max_key_code;
        for (auto& value:physical_) value={};
        for (unsigned code=map->min_key_code;code<=map->max_key_code;++code) {
            const auto& raw=map->names->keys[code].name;
            std::string name(raw,raw+XkbKeyNameLength); while (!name.empty() && (name.back()=='\0' || name.back()==' ')) name.pop_back();
            physical_[code]=fltk_x11_detail::physical(name);
            if (physical_[code].code.empty() && map->names->key_aliases) {
                for (unsigned n=0;n<map->names->num_key_aliases;++n) {
                    const auto& alias=map->names->key_aliases[n];
                    if (std::memcmp(alias.real,raw,XkbKeyNameLength)==0) {
                        std::string candidate(alias.alias,alias.alias+XkbKeyNameLength);
                        while (!candidate.empty() && (candidate.back()=='\0' || candidate.back()==' ')) candidate.pop_back();
                        physical_[code]=fltk_x11_detail::physical(candidate); if (!physical_[code].code.empty()) break;
                    }
                }
            }
        }
        alt_mask_=XkbKeysymToModifiers(display_,XK_Alt_L)|XkbKeysymToModifiers(display_,XK_Alt_R);
        meta_mask_=XkbKeysymToModifiers(display_,XK_Meta_L)|XkbKeysymToModifiers(display_,XK_Meta_R)|
            XkbKeysymToModifiers(display_,XK_Super_L)|XkbKeysymToModifiers(display_,XK_Super_R);
        alt_graph_mask_=XkbKeysymToModifiers(display_,XK_ISO_Level3_Shift)|XkbKeysymToModifiers(display_,XK_Mode_switch);
        if ((alt_mask_&meta_mask_) || ((alt_mask_|meta_mask_)&(ShiftMask|ControlMask)) ||
            (alt_graph_mask_&(alt_mask_|meta_mask_|ShiftMask|ControlMask)))
            throw std::runtime_error("Ambiguous native X11 Alt/Meta/AltGraph modifier binding");
        native_modifiers_.fill(0);
        auto* modifiers=XGetModifierMapping(display_);
        if (!modifiers || modifiers->max_keypermod<0 || modifiers->max_keypermod>256) {
            if (modifiers) XFreeModifiermap(modifiers);
            throw std::runtime_error("X11 modifier binding unavailable");
        }
        for (unsigned modifier=0;modifier<8;++modifier) for (int n=0;n<modifiers->max_keypermod;++n) {
            const auto code=modifiers->modifiermap[modifier*static_cast<unsigned>(modifiers->max_keypermod)+static_cast<unsigned>(n)];
            if (code) native_modifiers_[code]|=1u<<modifier;
        }
        XFreeModifiermap(modifiers);
        KeySym symbol{}; unsigned consumed{};
        if (key) (void)XkbTranslateKeyCode(map,static_cast<KeyCode>(key->keycode),key->state,&consumed,&symbol);
        return symbol;
    }
    void native_keyboard_state() {
        std::array<char,32> bits{}; XQueryKeymap(display_,bits.data());
        for (std::size_t i=0;i<native_down_.size();++i) native_down_[i]=(static_cast<unsigned char>(bits[i/8])&(1u<<(i%8)))!=0;
    }
    std::uint32_t modifiers(const XKeyEvent& event,bool down) const {
        unsigned state=event.state;
        const auto changed=native_modifiers_[event.keycode];
        if (down) state|=changed;
        else {
            unsigned other{};
            for (std::size_t i=0;i<native_down_.size();++i) if (i!=event.keycode && native_down_[i]) other|=native_modifiers_[i];
            state&=~(changed&~other);
        }
        std::uint32_t result{};
        if (state&ShiftMask) result|=gui_surface::shift;
        if (state&ControlMask) result|=gui_surface::control;
        if (state&alt_mask_) result|=gui_surface::alt;
        if (state&meta_mask_) result|=gui_surface::meta;
        if (state&alt_graph_mask_) result|=gui_surface::alt_graph;
        return result;
    }
    void begin_passage() { if (passage_) throw std::logic_error("Recursive X11 native passage"); passage_.emplace(); passage_bytes_=0; }
    void edit(FltkNativeEdit value) {
        if (!passage_ || passage_->edits.size()>=fltk_native_max_passages ||
            value.text.size()>fltk_native_max_text_bytes-queued_bytes_-passage_bytes_)
            throw std::runtime_error("X11 native edit passage limit");
        const auto bytes=value.text.size(); passage_->edits.push_back(std::move(value)); passage_bytes_+=bytes;
    }
    void finish_passage() {
        if (!passage_) return;
        if (failed_) { passage_.reset(); passage_bytes_=0; return; }
        auto value=std::move(*passage_); passage_.reset(); passage_bytes_=0;
        if (!value.key && value.edits.empty()) return;
        std::size_t bytes{}; for (const auto& item:value.edits) bytes+=item.text.size();
        if (pending_.size()>=fltk_native_max_passages || bytes>fltk_native_max_text_bytes-queued_bytes_)
            throw std::runtime_error("X11 owned passage queue limit");
        pending_.push_back(std::move(value)); queued_bytes_+=bytes;
    }
    void install_text(const gui_editor::TextObservation& text) {
        fltk_x11_detail::validate(text); draft_=fltk_x11_detail::scalars(text.value);
        selection_start_=fltk_x11_detail::scalar_position(draft_,text.selection_start);
        selection_end_=fltk_x11_detail::scalar_position(draft_,text.selection_end);
        selection_backward_=text.selection_direction==gui_editor::Direction::backward;
    }
    void replace_selection(std::u32string_view text) {
        auto next=draft_; next.replace(selection_start_,selection_end_-selection_start_,text);
        (void)fltk_x11_detail::utf8(next);
        draft_=std::move(next); selection_start_+=text.size(); selection_end_=selection_start_; selection_backward_=false;
    }
    static FltkNativePlatform& self(XPointer client) { return *reinterpret_cast<FltkNativePlatform*>(client); }
    template<class Function> static void callback(XPointer client,Function function) noexcept {
        auto& value=self(client); if (value.closing_ || value.failed_ || value.resetting_ || !value.configuration_) return;
        const bool standalone=!value.passage_;
        try {
            if (standalone) value.begin_passage();
            function(value);
            if (standalone) value.finish_passage();
        } catch (...) {
            if (standalone) value.passage_.reset();
            value.fail("Malformed or overflowing native XIM callback");
        }
    }
    static int preedit_start(XIC,XPointer client,XPointer) noexcept {
        int limit{};
        callback(client,[&](auto& value) {
            if (!value.passage_ || !value.next_transaction_) throw std::runtime_error("XIM preedit without owned passage");
            if (value.transaction_) {
                if (!value.preedit_done_) throw std::runtime_error("Overlapping XIM preedit transactions");
                value.edit({FltkNativeEditKind::composition_cancel,{},0,0,false,value.transaction_});
            }
            value.transaction_=value.next_transaction_;
            value.next_transaction_=value.next_transaction_==std::numeric_limits<std::uint64_t>::max() ? 0 : value.next_transaction_+1;
            value.preedit_.clear(); value.preedit_caret_=0; value.preedit_done_=false;
            value.edit({FltkNativeEditKind::composition_begin,{},0,0,false,value.transaction_}); limit=static_cast<int>(fltk_native_max_text_bytes);
        });
        return limit;
    }
    static void preedit_done(XIM,XPointer client,XPointer) noexcept {
        callback(client,[](auto& value) {
            if (!value.passage_ || !value.transaction_) throw std::runtime_error("XIM done without native transaction");
            // Done ends preedit display, not necessarily the later lookup result.
            value.preedit_done_=true;
        });
    }
    static std::u32string xim_text(const XIMText& text) {
        std::u32string result;
        if (text.encoding_is_wchar) {
            if (!text.string.wide_char && text.length) throw std::runtime_error("Missing XIM wide text");
            for (unsigned i=0;i<text.length;++i) result.push_back(static_cast<char32_t>(text.string.wide_char[i]));
            (void)fltk_x11_detail::utf8(result);
        } else {
            if (!text.string.multi_byte && text.length) throw std::runtime_error("Missing XIM multibyte text");
            std::size_t bytes{};
            for (unsigned i=0;i<text.length;++i) {
                const auto first=static_cast<unsigned char>(text.string.multi_byte[bytes]);
                const auto count=first<0x80 ? 1u : first>=0xc2 && first<=0xdf ? 2u : first>=0xe0 && first<=0xef ? 3u : first>=0xf0 && first<=0xf4 ? 4u : 0u;
                if (!count || !first || bytes+count>fltk_native_max_text_bytes) throw std::runtime_error("Invalid XIM UTF-8 character");
                const auto scalar=fltk_x11_detail::scalars(std::string_view(text.string.multi_byte+bytes,count));
                if (scalar.size()!=1) throw std::runtime_error("XIM character count mismatch");
                result.push_back(scalar.front()); bytes+=count;
            }
        }
        return result;
    }
    void preedit_update() {
        const auto cursor=fltk_x11_detail::utf16(preedit_,preedit_caret_);
        edit({FltkNativeEditKind::composition_update,fltk_x11_detail::utf8(preedit_),cursor,cursor,false,transaction_});
    }
    static void preedit_draw(XIM,XPointer client,XPointer raw) noexcept {
        callback(client,[&](auto& value) {
            if (!raw || !value.passage_ || !value.transaction_ || value.preedit_done_) throw std::runtime_error("XIM draw outside transaction");
            const auto& draw=*reinterpret_cast<XIMPreeditDrawCallbackStruct*>(raw);
            if (draw.chg_first<0 || draw.chg_length<0 || draw.caret<0 || static_cast<std::size_t>(draw.chg_first)>value.preedit_.size() ||
                static_cast<std::size_t>(draw.chg_length)>value.preedit_.size()-static_cast<std::size_t>(draw.chg_first)) throw std::runtime_error("Invalid XIM preedit range");
            const bool string=draw.text && (draw.text->encoding_is_wchar ? draw.text->string.wide_char!=nullptr : draw.text->string.multi_byte!=nullptr);
            if (!draw.text || string) {
                const auto addition=draw.text ? xim_text(*draw.text) : std::u32string{};
                auto next=value.preedit_; next.replace(static_cast<std::size_t>(draw.chg_first),static_cast<std::size_t>(draw.chg_length),addition);
                (void)fltk_x11_detail::utf8(next); value.preedit_=std::move(next);
            } // Null string with a nonnull XIMText is feedback-only, not deletion.
            value.preedit_caret_=static_cast<std::size_t>(draw.caret);
            if (value.preedit_caret_>value.preedit_.size()) throw std::runtime_error("XIM preedit caret outside text");
            value.preedit_update();
        });
    }
    static void preedit_caret(XIM,XPointer client,XPointer raw) noexcept {
        callback(client,[&](auto& value) {
            if (!raw || !value.passage_ || !value.transaction_ || value.preedit_done_) throw std::runtime_error("XIM caret outside transaction");
            auto& caret=*reinterpret_cast<XIMPreeditCaretCallbackStruct*>(raw);
            if (caret.direction==XIMAbsolutePosition && caret.position>=0 && static_cast<std::size_t>(caret.position)<=value.preedit_.size()) value.preedit_caret_=static_cast<std::size_t>(caret.position);
            else if (caret.direction==XIMForwardChar && value.preedit_caret_<value.preedit_.size()) ++value.preedit_caret_;
            else if (caret.direction==XIMBackwardChar && value.preedit_caret_) --value.preedit_caret_;
            else if (caret.direction==XIMLineStart) value.preedit_caret_=0;
            else if (caret.direction==XIMLineEnd) value.preedit_caret_=value.preedit_.size();
            else if (caret.direction!=XIMDontChange) throw std::runtime_error("Unsupported native XIM caret direction");
            caret.position=static_cast<int>(value.preedit_caret_); value.preedit_update();
        });
    }
    static void string_conversion(XIM,XPointer client,XPointer raw) noexcept {
        if (raw) reinterpret_cast<XIMStringConversionCallbackStruct*>(raw)->text=nullptr;
        callback(client,[&](auto& value) {
            if (!raw || !value.passage_) return;
            auto& request=*reinterpret_cast<XIMStringConversionCallbackStruct*>(raw);
            if (request.operation!=XIMStringConversionRetrieval && request.operation!=XIMStringConversionSubstitution) return;
            if (request.direction!=XIMForwardChar && request.direction!=XIMBackwardChar) return;
            const auto cursor=value.selection_backward_ ? value.selection_start_ : value.selection_end_;
            const auto offset=std::bit_cast<std::int16_t>(request.position);
            const auto start=static_cast<std::int64_t>(cursor)+offset;
            const auto finish=start+(request.direction==XIMForwardChar ? static_cast<std::int64_t>(request.factor) : -static_cast<std::int64_t>(request.factor));
            if (start<0 || finish<0 || start>static_cast<std::int64_t>(value.draft_.size()) || finish>static_cast<std::int64_t>(value.draft_.size())) return;
            const auto first=static_cast<std::size_t>(std::min(start,finish)),last=static_cast<std::size_t>(std::max(start,finish));
            if (last-first>std::numeric_limits<unsigned short>::max() || (request.operation==XIMStringConversionSubstitution && value.transaction_)) return;
            auto* buffer=static_cast<wchar_t*>(std::malloc((last-first+1)*sizeof(wchar_t)));
            if (!buffer) throw std::bad_alloc();
            for (std::size_t i=first;i<last;++i) buffer[i-first]=static_cast<wchar_t>(value.draft_[i]);
            buffer[last-first]=0;
            value.conversion_={}; value.conversion_.length=static_cast<unsigned short>(last-first);
            value.conversion_.encoding_is_wchar=True; value.conversion_.string.wcs=buffer;
            // Xlib's input method frees string/feedback with XFree after return.
            request.text=&value.conversion_;
            if (request.operation==XIMStringConversionSubstitution) {
                value.edit({FltkNativeEditKind::selection,{},fltk_x11_detail::utf16(value.draft_,first),fltk_x11_detail::utf16(value.draft_,last),false,0});
                value.selection_start_=first; value.selection_end_=last; value.selection_backward_=false;
                value.replace_selection({}); value.edit({FltkNativeEditKind::text,{},0,0,false,0});
            }
        });
    }
    static void im_destroyed(XIM,XPointer client,XPointer) noexcept {
        auto& value=self(client); value.ic_=nullptr; value.im_=nullptr; value.ic_focused_=false; value.xim_supported_=false;
        if (!value.closing_) value.fail("Owned X11 input method disconnected");
    }
    void input_method() {
        const char* codeset=nl_langinfo(CODESET);
        if (!codeset || (std::strcmp(codeset,"UTF-8")!=0 && std::strcmp(codeset,"UTF8")!=0) || !XSupportsLocale()) return;
        im_=XOpenIM(display_,nullptr,nullptr,nullptr); if (!im_) return;
        XIMStyles* styles{}; XIMValuesList* values{};
        if (XGetIMValues(im_,XNQueryInputStyle,&styles,XNQueryICValuesList,&values,nullptr)) {
            if (styles) XFree(styles);
            if (values) XFree(values);
            return;
        }
        XIMStyle chosen{};
        if (styles) for (unsigned i=0;i<styles->count_styles;++i) {
            const auto style=styles->supported_styles[i];
            if (style==(XIMPreeditCallbacks|XIMStatusNothing) || style==(XIMPreeditCallbacks|XIMStatusNone)) { chosen=style; break; }
        }
        bool conversion=false;
        if (values) for (unsigned i=0;i<values->count_values;++i) if (values->supported_values[i] && std::strcmp(values->supported_values[i],XNStringConversionCallback)==0) conversion=true;
        if (styles) XFree(styles);
        if (values) XFree(values);
        if (!chosen || !conversion) return;
        XICCallback start{reinterpret_cast<XPointer>(this),preedit_start};
        XIMCallback done{reinterpret_cast<XPointer>(this),preedit_done},draw{reinterpret_cast<XPointer>(this),preedit_draw},caret{reinterpret_cast<XPointer>(this),preedit_caret};
        XIMCallback convert{reinterpret_cast<XPointer>(this),string_conversion},destroy{reinterpret_cast<XPointer>(this),im_destroyed};
        auto attributes=XVaCreateNestedList(0,XNPreeditStartCallback,&start,XNPreeditDoneCallback,&done,
            XNPreeditDrawCallback,&draw,XNPreeditCaretCallback,&caret,nullptr);
        if (!attributes) return;
        ic_=XCreateIC(im_,XNInputStyle,chosen,XNClientWindow,xid_,XNFocusWindow,xid_,
            XNPreeditAttributes,attributes,XNStringConversionCallback,&convert,nullptr);
        XFree(attributes); if (!ic_) return;
        long required{};
        if (XGetICValues(ic_,XNFilterEvents,&required,nullptr)) return;
        XWindowAttributes window{};
        if (!XGetWindowAttributes(display_,xid_,&window) || (required&~window.your_event_mask)!=0) return;
        if (XSetIMValues(im_,XNDestroyCallback,&destroy,nullptr)) return;
        XPoint spot{}; auto position=XVaCreateNestedList(0,XNSpotLocation,&spot,nullptr);
        if (!position) return;
        const bool positioned=XSetICValues(ic_,XNPreeditAttributes,position,nullptr)==nullptr; XFree(position);
        xim_supported_=positioned;
    }
    void position_caret() {
        if (!configuration_ || !ic_ || !xim_supported_) return;
        const auto& caret=configuration_->caret;
        if (!std::isfinite(caret.x) || !std::isfinite(caret.y) || !std::isfinite(caret.height) || !std::isfinite(caret.width) || caret.width<0 || caret.height<0 ||
            caret.x<std::numeric_limits<short>::min() || caret.x>std::numeric_limits<short>::max() ||
            caret.y+caret.height<std::numeric_limits<short>::min() || caret.y+caret.height>std::numeric_limits<short>::max())
            throw std::invalid_argument("X11 actual caret outside native spot range");
        XPoint point{static_cast<short>(std::lround(caret.x)),static_cast<short>(std::lround(caret.y+caret.height))};
        auto attributes=XVaCreateNestedList(0,XNSpotLocation,&point,nullptr); if (!attributes) throw std::bad_alloc();
        const bool accepted=XSetICValues(ic_,XNPreeditAttributes,attributes,nullptr)==nullptr; XFree(attributes);
        if (!accepted) throw std::runtime_error("X11 input method rejected actual caret position");
    }
    void reset_ic() noexcept {
        if (!ic_) return;
        const auto context=ic_;
        resetting_=true;
        if (ic_focused_) { XUnsetICFocus(context); ic_focused_=false; }
        if (ic_==context) { char* discarded=Xutf8ResetIC(context); if (discarded) XFree(discarded); }
        transaction_=0; preedit_done_=false; preedit_.clear(); preedit_caret_=0;
        resetting_=false;
    }
    void focus_ic() {
        const bool eligible=ic_ && xim_supported_ && configuration_ && foreground_ && !suspended_ && window_facts().focused;
        if (eligible && ic_ && !failed_ && !ic_focused_) { const auto context=ic_; XSetICFocus(context); ic_focused_=ic_==context; }
        else if (!eligible && ic_focused_) reset_ic();
    }
    bool auto_repeat_release(const XKeyEvent& event) const {
        Bool supported=False;
        if (XkbGetDetectableAutoRepeat(display_,&supported) && supported) return false;
        if (!XEventsQueued(display_,QueuedAfterReading)) return false;
        XEvent next{}; XPeekEvent(display_,&next);
        return next.type==KeyPress && next.xkey.display==display_ && next.xkey.window==xid_ &&
            next.xkey.keycode==event.keycode && next.xkey.time==event.time;
    }
    void lookup(XKeyEvent& event) {
        if (!ic_focused_ || !configuration_) return;
        std::array<char,256> small{}; KeySym symbol{}; int status{};
        int length=Xutf8LookupString(ic_,&event,small.data(),static_cast<int>(small.size()),&symbol,&status);
        std::string text;
        if (status==XBufferOverflow) {
            if (length<0 || static_cast<std::size_t>(length)>fltk_native_max_text_bytes) throw std::runtime_error("XIM committed text byte limit");
            text.resize(static_cast<std::size_t>(length));
            length=Xutf8LookupString(ic_,&event,text.data(),length,&symbol,&status);
            if (length<0 || static_cast<std::size_t>(length)>text.size() || status==XBufferOverflow) throw std::runtime_error("XIM lookup changed its owned buffer requirement");
            text.resize(static_cast<std::size_t>(length));
        } else {
            if (length<0 || static_cast<std::size_t>(length)>small.size()) throw std::runtime_error("Invalid XIM committed text extent");
            text.assign(small.data(),static_cast<std::size_t>(length));
        }
        if (status!=XLookupChars && status!=XLookupBoth) return;
        const auto value=fltk_x11_detail::scalars(text);
        // A plain command-control lookup is handled by its actual key path;
        // it is not an additional insertText. Preserve real IME result text.
        if (!transaction_ && fltk_x11_detail::command_control(value)) return;
        if (transaction_) {
            edit({FltkNativeEditKind::composition_commit,std::move(text),fltk_x11_detail::utf16(value,value.size()),
                fltk_x11_detail::utf16(value,value.size()),false,transaction_});
            transaction_=0; preedit_done_=false; preedit_.clear(); preedit_caret_=0;
        } else if (!text.empty()) {
            const auto cursor=fltk_x11_detail::utf16(value,value.size());
            edit({FltkNativeEditKind::text,std::move(text),cursor,cursor,false,0});
        }
        replace_selection(value);
    }
    bool receive(XEvent& event) {
        if (closing_ || failed_) return false;
        if (event.type==MappingNotify) { keyboard_map(); return false; }
        if (event.xany.window!=xid_ || fl_xid(&window_)!=xid_) return false;
        if (event.type==FocusOut) {
            if (event.xfocus.detail!=NotifyInferior) suspend();
            return false;
        }
        if (event.type==FocusIn) { native_keyboard_state(); focus_ic(); return false; }
        const bool keyboard=event.type==KeyPress || event.type==KeyRelease;
        if (keyboard && (!foreground_ || suspended_)) return true;
        if (keyboard && event.xkey.keycode>=held_.size()) throw std::runtime_error("X11 keycode outside owned keyboard map");
        if (keyboard && event.xkey.keycode && (event.xkey.keycode<minimum_keycode_ || event.xkey.keycode>maximum_keycode_))
            throw std::runtime_error("X11 physical keycode outside actual XKB bounds");
        if (event.type==KeyRelease && event.xkey.keycode && auto_repeat_release(event.xkey)) return true;
        KeySym symbol{};
        if (keyboard && event.xkey.keycode) {
            // Read the actual server mapping for this owned event. This avoids
            // leaving a stale key-name/modifier cache when another toolkit owns
            // XKB notification subscriptions on the shared Display connection.
            symbol=keyboard_map(&event.xkey);
        }
        begin_passage();
        if (event.type==KeyPress && event.xkey.keycode && preedit_done_ && transaction_) {
            const auto old=transaction_;
            // A later physical down is not proof that its characters belong to
            // an earlier ended preedit. Resolve that owned XIC by an actual
            // reset before starting the new native passage. A forwarded XIM
            // keycode0 lookup can still deliver its real pending commit.
            reset_ic(); edit({FltkNativeEditKind::composition_cancel,{},0,0,false,old}); finish_passage();
            // The record keeps key separately from edits; a preceding passage
            // is necessary to preserve cancel-before-new-key delivery order.
            focus_ic(); begin_passage();
        }
        if (keyboard && event.xkey.keycode) {
            const bool down=event.type==KeyPress;
            const auto& physical=held_[event.xkey.keycode] ? held_physical_[event.xkey.keycode] : physical_[event.xkey.keycode];
            gui_surface::KeyTransition key; key.phase=down ? gui_surface::KeyPhase::down : gui_surface::KeyPhase::up;
            key.key=fltk_x11_detail::logical(symbol); key.code=physical.code; key.location=physical.location;
            key.modifiers=modifiers(event.xkey,down); key.repeat=down && held_[event.xkey.keycode];
            if (down && !held_[event.xkey.keycode]) held_physical_[event.xkey.keycode]=physical;
            held_[event.xkey.keycode]=down; native_down_[event.xkey.keycode]=down; passage_->key=std::move(key);
        }
        bool filtered=false;
        if (configuration_ && ic_focused_ && !suspended_) filtered=XFilterEvent(&event,xid_)!=False;
        if (event.type==KeyPress && !filtered) lookup(event.xkey);
        const bool has_edits=!passage_->edits.empty(); finish_passage();
        return keyboard || filtered || has_edits;
    }
public:
    FltkNativePlatform(Fl_Window& window,FltkNativePlatformCallbacks callbacks)
        : window_(window),callbacks_(std::move(callbacks)) {
        if (!callbacks_.passage || !callbacks_.surrounding || !callbacks_.failure) throw std::invalid_argument("Incomplete X11 Surface callbacks");
        display_=fl_display; xid_=fl_xid(&window_);
        if (!display_ || !xid_ || !window_.shown()) return;
        try { keyboard_map(); native_keyboard_state(); register_window(); input_method(); }
        catch (...) { unregister_window(); if (ic_) XDestroyIC(ic_); if (im_) XCloseIM(im_); ic_=nullptr; im_=nullptr; throw; }
    }
    ~FltkNativePlatform() {
        closing_=true; unregister_window(); (void)mouse_capture(false);
        if (ic_) { XDestroyIC(ic_); ic_=nullptr; }
        if (im_) { XCloseIM(im_); im_=nullptr; }
    }
    FltkNativePlatform(const FltkNativePlatform&)=delete;
    FltkNativePlatform& operator=(const FltkNativePlatform&)=delete;
    bool ready() const noexcept { return registered_ && !failed_ && display_ && xid_ && fl_xid(&window_)==xid_; }
    bool editor_supported() const noexcept { return ready() && xim_supported_; }
    FltkNativeWindowFacts window_facts() const noexcept {
        FltkNativeWindowFacts result;
        if (!display_ || !xid_ || !window_.shown() || fl_xid(&window_)!=xid_) return result;
        XWindowAttributes attributes{};
        if (!XGetWindowAttributes(display_,xid_,&attributes)) return result;
        result.shown=window_.visible() && attributes.map_state==IsViewable;
        if (result.shown) { result.drawable_width=window_.w(); result.drawable_height=window_.h(); }
        ::Window focused{}; int revert{}; XGetInputFocus(display_,&focused,&revert);
        // OS facts cannot depend on the lifecycle request derived from them.
        result.focused=result.shown && owned_focus(focused); result.foreground=result.focused;
        return result;
    }
    bool mouse_capture(bool acquire) noexcept {
        if (thread_!=std::this_thread::get_id() || !display_ || !xid_) return false;
        if (acquire) {
            if (!ready() || suspended_ || !foreground_ || !window_facts().foreground || foreign_routing() || (capture_owner_ && capture_owner_!=this)) return false;
            if (!ready()) return false;
            if (capture_) return true;
            if (XGrabPointer(display_,xid_,False,ButtonPressMask|ButtonReleaseMask|PointerMotionMask,
                GrabModeAsync,GrabModeAsync,0,0,CurrentTime)!=GrabSuccess) return false;
            capture_=true; capture_owner_=this; return true;
        }
        if (!capture_) return true;
        const bool owned=capture_owner_==this && !foreign_routing();
        capture_=false; if (capture_owner_==this) capture_owner_=nullptr;
        if (!owned) return false; // Never ungrab a foreign same-client popup/window.
        XUngrabPointer(display_,CurrentTime); XFlush(display_); return true;
    }
    void editor(std::optional<FltkNativeEditorConfiguration> configuration) {
        owner();
        if (!configuration) { configuration_.reset(); reset_ic(); return; }
        if (!editor_supported()) throw std::runtime_error("X11 native editor requires UTF-8 XIM preedit/surrounding/caret support");
        fltk_x11_detail::validate(configuration->text);
        if (!configuration->preserve_passage || !configuration_) { reset_ic(); install_text(configuration->text); }
        if (!editor_supported()) throw std::runtime_error("X11 input method disappeared during frontend replacement");
        configuration_=std::move(configuration); position_caret(); focus_ic();
    }
    void foreground(bool foreground) {
        owner(); foreground_=foreground;
        if (!foreground) {
            suspended_=true; configuration_.reset(); reset_ic(); held_.fill(false); native_down_.fill(false); pending_.clear(); passage_.reset(); queued_bytes_=0; passage_bytes_=0;
            (void)mouse_capture(false);
        }
        else if (window_facts().focused) { suspended_=false; focus_ic(); }
    }
    void suspend() noexcept {
        if (thread_!=std::this_thread::get_id()) { fail("Foreign-thread X11 Surface suspension"); return; }
        suspended_=true; configuration_.reset(); reset_ic(); pending_.clear(); passage_.reset(); queued_bytes_=0; passage_bytes_=0; held_.fill(false); native_down_.fill(false);
        (void)mouse_capture(false);
    }
    void poll() {
        owner(); if (polling_ || closing_) return;
        struct Guard { bool& value; explicit Guard(bool& flag):value(flag) { value=true; } ~Guard() { value=false; } } guard(polling_);
        if (failure_ || failure_without_storage_) {
            auto message=failure_ ? std::move(*failure_) : std::string("X11 native input allocation failure");
            failure_.reset(); failure_without_storage_=false; callbacks_.failure(std::move(message)); return;
        }
        if (!ready()) return;
        const auto count=pending_.size();
        for (std::size_t i=0;i<count && !pending_.empty() && !failed_;++i) {
            auto value=std::move(pending_.front()); pending_.pop_front();
            for (const auto& edit:value.edits) queued_bytes_-=edit.text.size();
            try { callbacks_.passage(std::move(value)); } catch (...) { fail("Exception delivering owned X11 native passage"); break; }
        }
        if (!failed_ && configuration_ && pending_.empty() && !transaction_) {
            try {
                if (auto actual=callbacks_.surrounding()) install_text(*actual);
                else { configuration_.reset(); reset_ic(); }
            }
            catch (...) { fail("Invalid current X11 frontend surrounding text"); }
        }
    }
};

} // namespace foundation::host
