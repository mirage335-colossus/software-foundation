// SPDX-License-Identifier: CC0-1.0
#pragma once

#if !defined(_WIN32)
#error "The FLTK Win32 surface leaf requires native Windows"
#endif

#include "native_fltk_surface_platform.hpp"
#include <FL/Fl_Window.H>
#include <FL/x.H>
#include <windows.h>
#include <imm.h>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <deque>
#include <limits>
#include <map>
#include <stdexcept>
#include <string_view>
#include <utility>

namespace foundation::host {
namespace fltk_surface_win32_detail {
static_assert(sizeof(wchar_t)==2,"Win32 native frontend uses UTF-16 WCHAR units");

// Set-1 scan positions, including the actual E0 bit from the native message.
// Virtual keys are deliberately not used to decide keypad or left/right code.
inline std::pair<std::string,unsigned> physical(unsigned scan,bool extended) {
    if (extended) {
        switch (scan) {
        case 0x1c:return {"NumpadEnter",3}; case 0x1d:return {"ControlRight",2};
        case 0x35:return {"NumpadDivide",3}; case 0x37:return {"PrintScreen",0};
        case 0x38:return {"AltRight",2}; case 0x47:return {"Home",0};
        case 0x45:return {"NumLock",0};
        case 0x48:return {"ArrowUp",0}; case 0x49:return {"PageUp",0};
        case 0x4b:return {"ArrowLeft",0}; case 0x4d:return {"ArrowRight",0};
        case 0x4f:return {"End",0}; case 0x50:return {"ArrowDown",0};
        case 0x51:return {"PageDown",0}; case 0x52:return {"Insert",0};
        case 0x53:return {"Delete",0}; case 0x5b:return {"MetaLeft",1};
        case 0x5c:return {"MetaRight",2}; case 0x5d:return {"ContextMenu",0};
        default:return {};
        }
    }
    switch (scan) {
    case 0x01:return {"Escape",0}; case 0x02:return {"Digit1",0};
    case 0x03:return {"Digit2",0}; case 0x04:return {"Digit3",0};
    case 0x05:return {"Digit4",0}; case 0x06:return {"Digit5",0};
    case 0x07:return {"Digit6",0}; case 0x08:return {"Digit7",0};
    case 0x09:return {"Digit8",0}; case 0x0a:return {"Digit9",0};
    case 0x0b:return {"Digit0",0}; case 0x0c:return {"Minus",0};
    case 0x0d:return {"Equal",0}; case 0x0e:return {"Backspace",0};
    case 0x0f:return {"Tab",0}; case 0x10:return {"KeyQ",0};
    case 0x11:return {"KeyW",0}; case 0x12:return {"KeyE",0};
    case 0x13:return {"KeyR",0}; case 0x14:return {"KeyT",0};
    case 0x15:return {"KeyY",0}; case 0x16:return {"KeyU",0};
    case 0x17:return {"KeyI",0}; case 0x18:return {"KeyO",0};
    case 0x19:return {"KeyP",0}; case 0x1a:return {"BracketLeft",0};
    case 0x1b:return {"BracketRight",0}; case 0x1c:return {"Enter",0};
    case 0x1d:return {"ControlLeft",1}; case 0x1e:return {"KeyA",0};
    case 0x1f:return {"KeyS",0}; case 0x20:return {"KeyD",0};
    case 0x21:return {"KeyF",0}; case 0x22:return {"KeyG",0};
    case 0x23:return {"KeyH",0}; case 0x24:return {"KeyJ",0};
    case 0x25:return {"KeyK",0}; case 0x26:return {"KeyL",0};
    case 0x27:return {"Semicolon",0}; case 0x28:return {"Quote",0};
    case 0x29:return {"Backquote",0}; case 0x2a:return {"ShiftLeft",1};
    case 0x2b:return {"Backslash",0}; case 0x2c:return {"KeyZ",0};
    case 0x2d:return {"KeyX",0}; case 0x2e:return {"KeyC",0};
    case 0x2f:return {"KeyV",0}; case 0x30:return {"KeyB",0};
    case 0x31:return {"KeyN",0}; case 0x32:return {"KeyM",0};
    case 0x33:return {"Comma",0}; case 0x34:return {"Period",0};
    case 0x35:return {"Slash",0}; case 0x36:return {"ShiftRight",2};
    case 0x37:return {"NumpadMultiply",3}; case 0x38:return {"AltLeft",1};
    case 0x39:return {"Space",0}; case 0x3a:return {"CapsLock",0};
    // Non-E0 0x45 is ambiguous with the E1 Pause sequence: leave it unknown.
    case 0x46:return {"ScrollLock",0};
    case 0x47:return {"Numpad7",3}; case 0x48:return {"Numpad8",3};
    case 0x49:return {"Numpad9",3}; case 0x4a:return {"NumpadSubtract",3};
    case 0x4b:return {"Numpad4",3}; case 0x4c:return {"Numpad5",3};
    case 0x4d:return {"Numpad6",3}; case 0x4e:return {"NumpadAdd",3};
    case 0x4f:return {"Numpad1",3}; case 0x50:return {"Numpad2",3};
    case 0x51:return {"Numpad3",3}; case 0x52:return {"Numpad0",3};
    case 0x53:return {"NumpadDecimal",3}; case 0x56:return {"IntlBackslash",0};
    case 0x57:return {"F11",0}; case 0x58:return {"F12",0};
    case 0x73:return {"IntlRo",0}; case 0x7d:return {"IntlYen",0};
    default:
        if (scan>=0x3b&&scan<=0x44) return {"F"+std::to_string(scan-0x3a),0};
        if (scan>=0x64&&scan<=0x6e) return {"F"+std::to_string(scan-0x57),0};
        if (scan==0x76) return {"F24",0};
        return {};
    }
}

inline std::string logical(WPARAM value) {
    if (value>=VK_F1&&value<=VK_F24) return "F"+std::to_string(value-VK_F1+1);
    switch (value) {
    case VK_BACK:return "Backspace"; case VK_TAB:return "Tab";
    case VK_RETURN:return "Enter"; case VK_ESCAPE:return "Escape";
    case VK_SHIFT:case VK_LSHIFT:case VK_RSHIFT:return "Shift";
    case VK_CONTROL:case VK_LCONTROL:case VK_RCONTROL:return "Control";
    case VK_MENU:case VK_LMENU:case VK_RMENU:return "Alt";
    case VK_LWIN:case VK_RWIN:return "Meta"; case VK_APPS:return "ContextMenu";
    case VK_PAUSE:return "Pause"; case VK_CAPITAL:return "CapsLock";
    case VK_PRIOR:return "PageUp"; case VK_NEXT:return "PageDown";
    case VK_END:return "End"; case VK_HOME:return "Home";
    case VK_LEFT:return "ArrowLeft"; case VK_UP:return "ArrowUp";
    case VK_RIGHT:return "ArrowRight"; case VK_DOWN:return "ArrowDown";
    case VK_SNAPSHOT:return "PrintScreen"; case VK_INSERT:return "Insert";
    case VK_DELETE:return "Delete"; case VK_NUMLOCK:return "NumLock";
    case VK_SCROLL:return "ScrollLock"; case VK_VOLUME_MUTE:return "AudioVolumeMute";
    case VK_VOLUME_DOWN:return "AudioVolumeDown"; case VK_VOLUME_UP:return "AudioVolumeUp";
    default:return "Unidentified";
    }
}
inline std::uint32_t modifiers() noexcept {
    auto down=[](int key) { return (GetKeyState(key)&0x8000)!=0; };
    // Right Alt and Ctrl+Alt are not evidence of AltGraph.
    return (down(VK_SHIFT)?gui_surface::shift:0u) |
        (down(VK_CONTROL)?gui_surface::control:0u) |
        (down(VK_MENU)?gui_surface::alt:0u) |
        ((down(VK_LWIN)||down(VK_RWIN))?gui_surface::meta:0u);
}
inline bool boundary(std::wstring_view text,std::size_t at) noexcept {
    return at<=text.size() && !(at&&at<text.size()&&text[at]>=0xdc00&&
        text[at]<=0xdfff&&text[at-1]>=0xd800&&text[at-1]<=0xdbff);
}
inline std::string utf8(std::wstring_view text) {
    if (text.size()>fltk_native_max_text_bytes || text.find(L'\0')!=text.npos)
        throw std::runtime_error("Invalid Win32 native UTF-16 length/NUL");
    if (text.empty()) return {};
    const auto count=static_cast<int>(text.size());
    const int bytes=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,text.data(),count,nullptr,0,nullptr,nullptr);
    if (bytes<=0||static_cast<std::size_t>(bytes)>fltk_native_max_text_bytes)
        throw std::runtime_error("Invalid or oversized Win32 native UTF-16");
    std::string result(static_cast<std::size_t>(bytes),'\0');
    if (WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,text.data(),count,result.data(),bytes,nullptr,nullptr)!=bytes)
        throw std::runtime_error("Win32 UTF-16 conversion changed");
    return result;
}
inline std::wstring utf16(const std::string& text) {
    if (text.size()>fltk_native_max_text_bytes||text.find('\0')!=text.npos)
        throw std::runtime_error("Invalid Win32 surrounding text length/NUL");
    if (text.empty()) return {};
    const auto bytes=static_cast<int>(text.size());
    const int count=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,text.data(),bytes,nullptr,0);
    if (count<=0) throw std::runtime_error("Invalid Win32 surrounding UTF-8");
    std::wstring result(static_cast<std::size_t>(count),L'\0');
    if (MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,text.data(),bytes,result.data(),count)!=count)
        throw std::runtime_error("Win32 UTF-8 conversion changed");
    return result;
}
inline std::wstring checked(const gui_editor::TextObservation& text) {
    auto result=utf16(text.value);
    if (text.byte_length!=text.value.size()||text.selection_start>text.selection_end||
        !boundary(result,text.selection_start)||!boundary(result,text.selection_end)||
        utf8(std::wstring_view(result).substr(0,text.selection_start)).size()!=text.selection.begin||
        utf8(std::wstring_view(result).substr(0,text.selection_end)).size()!=text.selection.end||
        (text.selection_direction!=gui_editor::Direction::none&&
         text.selection_direction!=gui_editor::Direction::forward&&text.selection_direction!=gui_editor::Direction::backward))
        throw std::runtime_error("Inconsistent Win32 surrounding observation");
    return result;
}
inline bool caret_valid(gui_surface::Rect value) noexcept {
    return std::isfinite(value.x)&&std::isfinite(value.y)&&std::isfinite(value.width)&&std::isfinite(value.height)&&
        std::abs(value.x)<=1000000&&std::abs(value.y)<=1000000&&value.width>=0&&value.width<=1000000&&
        value.height>=0&&value.height<=1000000;
}
} // namespace fltk_surface_win32_detail

// The zero-area Unicode child is an actual native text/IME frontend. Its private
// HIMC is never installed on RootWindow or on ordinary FLTK controls. All native
// callbacks below only mutate bounded owned data; only poll() calls the owner.
class FltkNativePlatform final {
public:
    FltkNativePlatform(Fl_Window& window,FltkNativePlatformCallbacks callbacks)
        : window_(window),callbacks_(std::move(callbacks)) {
        if (!callbacks_.surrounding||!callbacks_.passage||!callbacks_.failure)
            throw std::invalid_argument("Incomplete FLTK Win32 native callbacks");
        install();
    }
    ~FltkNativePlatform() {
        suspend();
        if (child_&&IsWindow(child_)) {
            destroying_=true;
            ImmAssociateContext(child_,previous_context_);
            DestroyWindow(child_);
        }
        if (context_) ImmDestroyContext(context_);
    }
    FltkNativePlatform(const FltkNativePlatform&)=delete;
    FltkNativePlatform& operator=(const FltkNativePlatform&)=delete;

    bool ready() const noexcept {
        return !failed_&&root_&&child_&&context_&&IsWindow(root_)&&IsWindow(child_)&&root_==fl_xid(&window_);
    }
    bool editor_supported() const noexcept { return ready(); }
    FltkNativeWindowFacts window_facts() const noexcept {
        FltkNativeWindowFacts result;
        result.shown=root_&&IsWindow(root_)&&window_.shown()&&IsWindowVisible(root_);
        if (!result.shown) return result;
        result.drawable_width=window_.w();result.drawable_height=window_.h();
        result.foreground=GetAncestor(GetForegroundWindow(),GA_ROOT)==GetAncestor(root_,GA_ROOT);
        const auto focused=GetFocus();result.focused=focused==root_||focused==child_;
        return result;
    }
    bool mouse_capture(bool acquire) noexcept {
        if (acquire) {
            if (!ready()||!window_facts().foreground) return false;
            const auto held=GetCapture();
            if (held&&held!=root_) return false;
            if (held!=root_) SetCapture(root_);
            capture_owned_=GetCapture()==root_;return capture_owned_;
        }
        if (capture_owned_&&GetCapture()==root_) {
            ReleaseCapture();
            if (GetCapture()==root_) return false;
        }
        capture_owned_=false;return GetCapture()!=root_;
    }
    void editor(std::optional<FltkNativeEditorConfiguration> configuration) {
        if (!configuration) { deactivate_editor();return; }
        if (!ready()) throw std::runtime_error("Win32 native editor is not ready");
        auto value=fltk_surface_win32_detail::checked(configuration->text);
        if (!fltk_surface_win32_detail::caret_valid(configuration->caret))
            throw std::invalid_argument("Invalid Win32 native caret");
        const bool same=value==draft_&&start_==configuration->text.selection_start&&end_==configuration->text.selection_end&&
            backward_==(configuration->text.selection_direction==gui_editor::Direction::backward);
        if (composition_&&!same&&!configuration->preserve_passage)
            throw std::logic_error("Win32 preedit requires explicit retirement before replacement");
        if (!configuration->preserve_passage&&!composition_) {
            cancel_native();clear_pending();
            draft_=std::move(value);start_=configuration->text.selection_start;end_=configuration->text.selection_end;
            backward_=configuration->text.selection_direction==gui_editor::Direction::backward;
        } else if (!editor_) {
            throw std::invalid_argument("Cannot preserve an absent Win32 native editor");
        }
        caret_=configuration->caret;caret_current_=!configuration->preserve_passage||same;editor_=true;
        if (!associate(foreground_?context_:nullptr)) throw std::runtime_error("Win32 native IME association failed");
        if (foreground_&&GetFocus()==child_) position_ime();
    }
    void foreground(bool value) {
        if (suspending_||focusing_) return;
        install();
        if (!value) { suspend();return; }
        if (!ready()) return;
        foreground_=true;
        if (!associate(editor_?context_:nullptr)) throw std::runtime_error("Win32 native IME association failed");
        const auto facts=window_facts();
        // Never take focus from an ordinary native child, dialog or other app.
        if (facts.foreground&&GetFocus()==root_) {
            struct Guard { bool& value;~Guard(){value=false;} } guard{focusing_};focusing_=true;
            SetFocus(child_);
        }
        if (editor_&&GetFocus()==child_) position_ime();
    }
    void suspend() noexcept {
        if (suspending_) return;
        struct Guard { bool& value;~Guard(){value=false;} } guard{suspending_};suspending_=true;
        foreground_=false;
        if (!mouse_capture(false)&&capture_owned_) fault("Cannot release owned Win32 mouse capture");
        cancel_native();clear_pending();held_.clear();
        editor_=false;draft_.clear();start_=end_=0;backward_=false;
        if (child_&&IsWindow(child_)) {
            (void)associate(nullptr);
            if (GetFocus()==child_) { clear_caret();if (root_&&IsWindow(root_)) SetFocus(root_); }
        }
    }
    void poll() {
        if (polling_) throw std::logic_error("Reentrant Win32 native owner poll");
        struct Guard { bool& value;~Guard(){value=false;} } guard{polling_};polling_=true;
        install();
        if (capture_owned_&&GetCapture()!=root_) fault("Owned Win32 mouse capture was lost");
        if (failed_) {
            suspend();
            if (!failure_reported_) { failure_reported_=true;callbacks_.failure(failure_.empty()?"Win32 native input failure":failure_); }
            return;
        }
        if (!ready()) return;
        // Clicking the renderer can transfer keyboard focus to its root HWND.
        // That remains the same active surface; restore its dedicated input
        // child here, outside the native callback. External loss clears the
        // activation flag below and can never take this continuation path.
        if (foreground_&&GetFocus()==root_&&window_facts().foreground) foreground(true);
        while (!pending_.empty()&&pending_.front().sealed&&!failed_) {
            auto passage=std::move(pending_.front().value);
            queued_bytes_-=pending_.front().bytes;pending_.pop_front();
            callbacks_.passage(std::move(passage));
            if (!foreground_) break;
        }
        // Refresh only when no native preedit/queued draft is ahead of owner.
        if (editor_&&pending_.empty()&&!composition_) {
            if (auto current=callbacks_.surrounding()) {
                auto value=fltk_surface_win32_detail::checked(*current);
                draft_=std::move(value);start_=current->selection_start;end_=current->selection_end;
                backward_=current->selection_direction==gui_editor::Direction::backward;
            }
        }
    }

private:
    struct Pending {
        FltkNativePassage value;
        std::uint64_t serial{},anchor{},batch{};
        unsigned scan{};
        wchar_t high{};
        bool sealed{};
        std::size_t bytes{};
    };
    struct Held { std::uint64_t anchor{};std::string key; };
    Fl_Window& window_;
    FltkNativePlatformCallbacks callbacks_;
    HWND root_{},child_{};
    HIMC context_{},previous_context_{};
    bool foreground_{},editor_{},failed_{},failure_reported_{},polling_{},caret_owned_{},caret_current_{},capture_owned_{},cancelling_{},destroying_{};
    bool suspending_{},focusing_{};
    std::string failure_;
    std::deque<Pending> pending_;
    std::map<unsigned,Held> held_;
    std::size_t queued_bytes_{};
    std::uint64_t next_serial_{1},active_dispatch_{},next_transaction_{1},composition_{};
    std::wstring draft_,composition_before_,preedit_;
    std::size_t start_{},end_{},composition_start_{},composition_end_{},before_start_{},before_end_{},cursor_{};
    bool backward_{},before_backward_{};
    gui_surface::Rect caret_;
    static constexpr UINT boundary_message=WM_APP+0x394;
    static constexpr const wchar_t* class_name=L"FoundationFltkNativeSurfaceWin32V1";

    bool context_matches(HIMC expected) const noexcept {
        const auto current=ImmGetContext(child_);const bool matches=current==expected;
        if (current) ImmReleaseContext(child_,current);
        return matches;
    }
    bool associate(HIMC desired) noexcept {
        ImmAssociateContext(child_,desired);
        if (context_matches(desired)) return true;
        fault("Private Win32 IME context association was lost");return false;
    }

    static LRESULT CALLBACK procedure(HWND hwnd,UINT message,WPARAM wparam,LPARAM lparam) noexcept {
        auto* self=reinterpret_cast<FltkNativePlatform*>(GetWindowLongPtrW(hwnd,GWLP_USERDATA));
        if (message==WM_NCCREATE) {
            const auto* create=reinterpret_cast<const CREATESTRUCTW*>(lparam);
            self=static_cast<FltkNativePlatform*>(create->lpCreateParams);
            SetWindowLongPtrW(hwnd,GWLP_USERDATA,reinterpret_cast<LONG_PTR>(self));
        }
        if (!self) return DefWindowProcW(hwnd,message,wparam,lparam);
        try { return self->message(hwnd,message,wparam,lparam); }
        catch (const std::exception& error) { self->fault(error.what());return 0; }
        catch (...) { self->fault("Unknown Win32 native input exception");return 0; }
    }
    void install() {
        if (failed_||child_||!window_.shown()) return;
        root_=fl_xid(&window_);
        if (!root_||!IsWindow(root_)) return;
        const auto instance=GetModuleHandleW(nullptr);
        WNDCLASSEXW klass{};klass.cbSize=sizeof(klass);klass.hInstance=instance;
        klass.lpfnWndProc=&procedure;klass.lpszClassName=class_name;
        if (!RegisterClassExW(&klass)) {
            WNDCLASSEXW existing{};existing.cbSize=sizeof(existing);
            if (GetLastError()!=ERROR_CLASS_ALREADY_EXISTS||!GetClassInfoExW(instance,class_name,&existing)||
                existing.lpfnWndProc!=&procedure) { fault("Cannot register Win32 native input window");return; }
        }
        context_=ImmCreateContext();
        if (!context_) { fault("Cannot create private Win32 IME context");return; }
        child_=CreateWindowExW(0,class_name,L"",WS_CHILD|WS_VISIBLE,0,0,0,0,root_,nullptr,instance,this);
        if (!child_) { fault("Cannot create Win32 native input child");return; }
        previous_context_=ImmAssociateContext(child_,nullptr);
        // Check the private context can actually be installed, then leave it
        // detached until an explicit checked editor/foreground activation.
        if (associate(context_)) (void)associate(nullptr);
    }
    void fault(const char* reason) noexcept {
        failed_=true;foreground_=false;
        try { if (failure_.empty()) failure_=std::string(reason).substr(0,256); } catch (...) {}
    }
    void clear_pending() noexcept { pending_.clear();queued_bytes_=0;active_dispatch_=0; }
    void clear_caret() noexcept { if (caret_owned_) { DestroyCaret();caret_owned_=false; } }
    void position_ime() {
        if (!editor_||!foreground_||!caret_current_||GetFocus()!=child_) return;
        const int x=static_cast<int>(std::lround(caret_.x)),y=static_cast<int>(std::lround(caret_.y));
        const int height=(std::max)(1,static_cast<int>(std::lround(caret_.height)));
        clear_caret();
        if (!CreateCaret(child_,nullptr,1,height)) { fault("Cannot create Win32 native caret");throw std::runtime_error("Cannot create Win32 native caret"); }
        caret_owned_=true;
        if (!SetCaretPos(x,y)) { fault("Cannot position Win32 native caret");throw std::runtime_error("Cannot position Win32 native caret"); }
        COMPOSITIONFORM composition{};composition.dwStyle=CFS_POINT;composition.ptCurrentPos={x,y};
        CANDIDATEFORM candidate{};candidate.dwStyle=CFS_EXCLUDE;candidate.ptCurrentPos={x,y+height};
        candidate.rcArea={x,y,x+(std::max)(1,static_cast<int>(std::lround(caret_.width))),y+height};
        if (!ImmSetCompositionWindow(context_,&composition)||!ImmSetCandidateWindow(context_,&candidate)) {
            fault("Cannot position private Win32 IME");throw std::runtime_error("Cannot position private Win32 IME");
        }
    }
    void cancel_native() noexcept {
        const bool active=composition_!=0;
        // Block reentrant cancellation callbacks before calling IMM32.
        composition_=0;preedit_.clear();composition_before_.clear();cursor_=0;
        cancelling_=true;
        if (active&&context_) {
            ImmNotifyIME(context_,NI_COMPOSITIONSTR,CPS_CANCEL,0);
            const LONG remaining=ImmGetCompositionStringW(context_,GCS_COMPSTR,nullptr,0);
            if (remaining!=0&&remaining!=IMM_ERROR_NODATA) fault("Win32 IME cancellation did not close native preedit");
        }
        cancelling_=false;
        if (caret_owned_&&GetFocus()==child_) clear_caret();
    }
    void deactivate_editor() noexcept {
        cancel_native();clear_pending();editor_=false;draft_.clear();start_=end_=0;backward_=false;
        if (child_&&IsWindow(child_)) (void)associate(nullptr);
    }
    Pending* find(std::uint64_t serial) noexcept {
        for (auto& item:pending_) if (item.serial==serial) return &item;
        return nullptr;
    }
    std::uint64_t append(bool sealed) {
        if (pending_.size()>=fltk_native_max_passages||!next_serial_)
            throw std::runtime_error("Win32 native passage bound exhausted");
        const auto serial=next_serial_;
        next_serial_=serial==UINT64_MAX?0:serial+1;
        pending_.push_back({});pending_.back().serial=serial;pending_.back().sealed=sealed;return serial;
    }
    void post_boundary(std::uint64_t serial) {
        if (!PostMessageW(child_,boundary_message,static_cast<WPARAM>(serial&0xffffffffu),
                static_cast<LPARAM>(serial>>32))) throw std::runtime_error("Cannot queue Win32 input boundary");
    }
    void add_edit(FltkNativeEdit edit,std::uint64_t target=0) {
        if (edit.text.size()>fltk_native_max_text_bytes-queued_bytes_)
            throw std::runtime_error("Win32 queued native text bound exhausted");
        if (!target) target=active_dispatch_;
        if (!target) target=append(true);
        auto* item=find(target);
        if (!item||item->value.edits.size()>=fltk_native_max_passages)
            throw std::runtime_error("Win32 native edit bound exhausted");
        if (edit.kind==FltkNativeEditKind::text&&!item->value.edits.empty()&&
            item->value.edits.back().kind==FltkNativeEditKind::text) {
            // TranslateMessage can emit an accent plus a noncombining base for
            // one dispatch. Keep its observed fragments in one dependent edit.
            auto& previous=item->value.edits.back();
            previous.text+=edit.text;previous.selection_start+=edit.selection_start;previous.selection_end+=edit.selection_end;
            item->bytes+=edit.text.size();queued_bytes_+=edit.text.size();return;
        }
        item->bytes+=edit.text.size();queued_bytes_+=edit.text.size();item->value.edits.push_back(std::move(edit));
    }
    void replace(std::wstring_view text,std::size_t begin,std::size_t end,std::size_t first,std::size_t last) {
        using namespace fltk_surface_win32_detail;
        if (begin>end||!boundary(draft_,begin)||!boundary(draft_,end)||first>last||
            !boundary(text,first)||!boundary(text,last)) throw std::runtime_error("Invalid Win32 native replacement");
        auto value=draft_.substr(0,begin)+std::wstring(text)+draft_.substr(end);
        (void)utf8(value);draft_=std::move(value);start_=begin+first;end_=begin+last;backward_=false;caret_current_=false;
    }
    void begin_composition() {
        if (composition_) throw std::runtime_error("Nested Win32 IME composition");
        if (!next_transaction_) throw std::runtime_error("Win32 IME transaction exhausted");
        composition_=next_transaction_;next_transaction_=composition_==UINT64_MAX?0:composition_+1;
        composition_before_=draft_;before_start_=start_;before_end_=end_;before_backward_=backward_;
        composition_start_=start_;composition_end_=end_;preedit_.clear();cursor_=0;
        add_edit({FltkNativeEditKind::composition_begin,{},0,0,false,composition_});
        replace({},composition_start_,composition_end_,0,0);composition_end_=composition_start_;
    }
    void cancel_composition() {
        if (!composition_) return;
        add_edit({FltkNativeEditKind::composition_cancel,{},0,0,false,composition_});
        draft_=std::move(composition_before_);start_=before_start_;end_=before_end_;backward_=before_backward_;
        composition_=0;preedit_.clear();cursor_=0;caret_current_=false;
    }
    std::wstring ime_string(DWORD kind) const {
        const LONG bytes=ImmGetCompositionStringW(context_,kind,nullptr,0);
        if (bytes<0||bytes%sizeof(wchar_t)||static_cast<std::size_t>(bytes)>fltk_native_max_text_bytes*2)
            throw std::runtime_error("Invalid Win32 IME string length");
        std::wstring result(static_cast<std::size_t>(bytes)/sizeof(wchar_t),L'\0');
        if (bytes&&ImmGetCompositionStringW(context_,kind,result.data(),static_cast<DWORD>(bytes))!=bytes)
            throw std::runtime_error("Win32 IME string changed during read");
        (void)fltk_surface_win32_detail::utf8(result);return result;
    }
    void ime_composition(LPARAM flags) {
        if (!flags) { cancel_composition();return; }
        if (flags&GCS_RESULTSTR) {
            auto result=ime_string(GCS_RESULTSTR);auto text=fltk_surface_win32_detail::utf8(result);
            if (composition_) {
                const auto transaction=composition_;
                replace(result,composition_start_,composition_end_,result.size(),result.size());
                add_edit({FltkNativeEditKind::composition_commit,std::move(text),result.size(),result.size(),false,transaction});
                composition_=0;composition_before_.clear();preedit_.clear();cursor_=0;
            } else {
                replace(result,start_,end_,result.size(),result.size());
                add_edit({FltkNativeEditKind::text,std::move(text),result.size(),result.size(),false,0});
            }
        }
        if (flags&(GCS_COMPSTR|GCS_CURSORPOS)) {
            if (!composition_) begin_composition();
            auto value=(flags&GCS_COMPSTR)?ime_string(GCS_COMPSTR):preedit_;
            const LONG cursor=ImmGetCompositionStringW(context_,GCS_CURSORPOS,nullptr,0);
            if (cursor<0||!fltk_surface_win32_detail::boundary(value,static_cast<std::size_t>(cursor)))
                throw std::runtime_error("Invalid Win32 IME cursor");
            const auto at=static_cast<std::size_t>(cursor);
            replace(value,composition_start_,composition_end_,at,at);composition_end_=composition_start_+value.size();
            preedit_=std::move(value);cursor_=at;
            add_edit({FltkNativeEditKind::composition_update,fltk_surface_win32_detail::utf8(preedit_),at,at,false,composition_});
        }
        // Legacy insertion flags without a retrievable Unicode composition are
        // not converted from wParam (which can be a DBCS code page character).
        if ((flags&CS_INSERTCHAR)&&!(flags&(GCS_COMPSTR|GCS_RESULTSTR)))
            throw std::runtime_error("Win32 IME supplied no checked Unicode composition");
    }
    static unsigned scan_of(LPARAM flags) noexcept { return static_cast<unsigned>((static_cast<ULONG_PTR>(flags)>>16)&0x1ffu); }
    static unsigned key_id(WPARAM key,LPARAM flags) noexcept {
        const auto scan=scan_of(flags);return scan?scan:(0x10000u|static_cast<unsigned>(key&0xffffu));
    }
    LRESULT key(HWND hwnd,UINT message,WPARAM wparam,LPARAM lparam) {
        using namespace fltk_surface_win32_detail;
        const bool up=message==WM_KEYUP||message==WM_SYSKEYUP;
        const auto native_scan=scan_of(lparam);auto [code,location]=physical(native_scan&255u,(native_scan&256u)!=0);
        const bool repeat=!up&&(static_cast<ULONG_PTR>(lparam)&(ULONG_PTR{1}<<30))!=0;
        const auto id=key_id(wparam,lparam);auto name=logical(wparam);
        auto held=held_.find(id);
        std::uint64_t anchor=held==held_.end()?0:held->second.anchor;
        if (up&&held!=held_.end()&&name=="Unidentified") name=held->second.key;
        const auto count=static_cast<unsigned>(static_cast<ULONG_PTR>(lparam)&0xffffu);
        if (!count||count>fltk_native_max_passages||count>fltk_native_max_passages-pending_.size()||(up&&count!=1))
            throw std::runtime_error("Invalid Win32 native key repeat count");
        // A coalesced native message represents count physical transitions. Its
        // translated WM_CHAR repeats have the same count; each owned passage
        // receives one actual character rather than collapsing key defaults.
        const auto serial=next_serial_;
        for (unsigned index=0;index<count;++index) {
            const auto current=append(false);auto* item=find(current);
            item->scan=native_scan;item->anchor=anchor?anchor:serial;item->batch=serial;
            item->value.key=gui_surface::KeyTransition{up?gui_surface::KeyPhase::up:gui_surface::KeyPhase::down,
                name,code,location,modifiers(),repeat||index!=0};
            post_boundary(current);
        }
        if (up) { if (held!=held_.end()) held_.erase(held); }
        else {
            if (held==held_.end()&&held_.size()>=fltk_native_max_passages)
                throw std::runtime_error("Win32 held key bound exhausted");
            held_[id]={anchor?anchor:serial,std::move(name)};
        }
        const auto previous=active_dispatch_;active_dispatch_=count==1?serial:0;
        // IMM32 can synchronously reenter this child while native defaults run.
        const auto result=DefWindowProcW(hwnd,message,wparam,lparam);
        active_dispatch_=previous;return result;
    }
    Pending* character_passage(LPARAM flags) noexcept {
        const auto scan=scan_of(flags);
        for (auto& item:pending_) {
            if (!item.sealed&&item.scan==scan&&(!item.value.key||item.value.key->phase==gui_surface::KeyPhase::down))
                return &item;
        }
        return nullptr;
    }
    void name_dead(Pending& item) {
        if (!item.value.key) return;
        item.value.key->key="Dead";
        for (auto& [id,value]:held_) { (void)id;if (value.anchor==item.anchor) value.key="Dead"; }
        for (auto& other:pending_)
            if (other.value.key&&(other.batch==item.batch||
                (other.anchor==item.anchor&&other.value.key->phase==gui_surface::KeyPhase::up&&other.value.key->key=="Unidentified")))
                other.value.key->key="Dead";
    }
    void character(WPARAM value,LPARAM flags,bool unicode) {
        auto* target=character_passage(flags);
        if (!target&&!editor_) return;
        if (!target) { const auto serial=append(false);target=find(serial);target->scan=scan_of(flags);post_boundary(serial); }
        std::wstring text;
        if (unicode) {
            if (!value||value>0x10ffff||(value>=0xd800&&value<=0xdfff)||target->high)
                throw std::runtime_error("Invalid Win32 Unicode scalar callback");
            if (value<=0xffff) text+=static_cast<wchar_t>(value);
            else { const auto scalar=static_cast<std::uint32_t>(value)-0x10000;
                text+=static_cast<wchar_t>(0xd800+(scalar>>10));text+=static_cast<wchar_t>(0xdc00+(scalar&1023)); }
        } else {
            if (value>0xffff||!value) throw std::runtime_error("Invalid Win32 character callback");
            const auto unit=static_cast<wchar_t>(value);
            if (unit>=0xd800&&unit<=0xdbff) {
                if (target->high) throw std::runtime_error("Repeated Win32 high surrogate");
                target->high=unit;return;
            }
            if (unit>=0xdc00&&unit<=0xdfff) {
                if (!target->high) throw std::runtime_error("Unpaired Win32 low surrogate");
                text+=target->high;target->high=0;text+=unit;
            } else {
                if (target->high) throw std::runtime_error("Unpaired Win32 high surrogate");
                text+=unit;
            }
        }
        // These are native command characters, not Unicode insertion callbacks.
        // Their actual key default is handled by the checked owner/backend.
        if (text.size()==1&&(text.front()<0x20||text.front()==0x7f)) return;
        const auto encoded=fltk_surface_win32_detail::utf8(text);
        const auto count=static_cast<unsigned>(static_cast<ULONG_PTR>(flags)&0xffffu);
        if (!count||count>fltk_native_max_passages||encoded.size()>fltk_native_max_text_bytes/count)
            throw std::runtime_error("Invalid Win32 native character repeat count");
        if (target->value.key) {
            const auto batch=target->batch;unsigned actual=0;
            for (const auto& item:pending_) if (item.batch==batch) ++actual;
            if (actual!=count) throw std::runtime_error("Win32 character/key repeat count mismatch");
            // A coalesced repeat with several separate Unicode callbacks cannot
            // be reordered into count singular-key passages without inventing
            // their interleaving. Quarantine that unrepresentable source.
            if (count>1) for (const auto& item:pending_)
                if (item.batch==batch&&!item.value.edits.empty())
                    throw std::runtime_error("Ambiguous multicharacter Win32 coalesced repeat");
            for (auto& item:pending_) {
                if (item.batch!=batch) continue;
                if (item.sealed||!item.value.key||item.value.key->phase!=gui_surface::KeyPhase::down)
                    throw std::runtime_error("Invalid Win32 translated character batch");
                if (editor_) {
                    if (composition_) throw std::runtime_error("Uncorrelated Win32 character during IME preedit");
                    replace(text,start_,end_,text.size(),text.size());
                    add_edit({FltkNativeEditKind::text,encoded,text.size(),text.size(),false,0},item.serial);
                }
            }
        } else {
            std::wstring repeated;std::string committed;
            for (unsigned i=0;i<count;++i) { repeated+=text;committed+=encoded; }
            const auto serial=target->serial;
            replace(repeated,start_,end_,repeated.size(),repeated.size());
            add_edit({FltkNativeEditKind::text,std::move(committed),repeated.size(),repeated.size(),false,0},serial);
        }
    }
    LRESULT reconvert(LPARAM parameter,bool document) {
        if (!editor_||(!document&&composition_)) return 0;
        const auto bytes=sizeof(RECONVERTSTRING)+(draft_.size()+1)*sizeof(wchar_t);
        if (!parameter) return static_cast<LRESULT>(bytes);
        auto* output=reinterpret_cast<RECONVERTSTRING*>(parameter);
        if (output->dwSize<bytes||output->dwSize>sizeof(RECONVERTSTRING)+(fltk_native_max_text_bytes+1)*sizeof(wchar_t)) return 0;
        RECONVERTSTRING record{};record.dwSize=static_cast<DWORD>(bytes);record.dwVersion=0;
        record.dwStrLen=static_cast<DWORD>(draft_.size());record.dwStrOffset=sizeof(record);
        record.dwCompStrOffset=static_cast<DWORD>((composition_?composition_start_:start_)*sizeof(wchar_t));
        record.dwCompStrLen=static_cast<DWORD>(composition_?composition_end_-composition_start_:end_-start_);
        record.dwTargetStrOffset=static_cast<DWORD>(start_*sizeof(wchar_t));record.dwTargetStrLen=static_cast<DWORD>(end_-start_);
        std::memcpy(output,&record,sizeof(record));
        std::memcpy(reinterpret_cast<unsigned char*>(output)+record.dwStrOffset,draft_.c_str(),(draft_.size()+1)*sizeof(wchar_t));
        return static_cast<LRESULT>(bytes);
    }
    LRESULT confirm_reconvert(LPARAM parameter) {
        if (!parameter||!editor_||composition_) return FALSE;
        const auto* value=reinterpret_cast<const RECONVERTSTRING*>(parameter);
        const std::size_t size=value->dwSize,offset=value->dwStrOffset;
        if (value->dwVersion||size<sizeof(*value)||size>sizeof(*value)+(fltk_native_max_text_bytes+1)*sizeof(wchar_t)||
            offset<sizeof(*value)||offset%alignof(wchar_t)||offset>size||value->dwStrLen!=draft_.size()||
            (draft_.size()+1)*sizeof(wchar_t)>size-offset) return FALSE;
        const auto* text=reinterpret_cast<const wchar_t*>(reinterpret_cast<const unsigned char*>(value)+offset);
        if (std::memcmp(text,draft_.c_str(),(draft_.size()+1)*sizeof(wchar_t))!=0||
            value->dwCompStrOffset%sizeof(wchar_t)||value->dwTargetStrOffset%sizeof(wchar_t)) return FALSE;
        const std::size_t begin=value->dwCompStrOffset/sizeof(wchar_t),length=value->dwCompStrLen;
        const std::size_t target=value->dwTargetStrOffset/sizeof(wchar_t),target_length=value->dwTargetStrLen;
        if (begin>draft_.size()||length>draft_.size()-begin||target<begin||target>begin+length||target_length>begin+length-target||
            !fltk_surface_win32_detail::boundary(draft_,begin)||!fltk_surface_win32_detail::boundary(draft_,begin+length)||
            !fltk_surface_win32_detail::boundary(draft_,target)||!fltk_surface_win32_detail::boundary(draft_,target+target_length)) return FALSE;
        // This selection came from the checked native reconversion request.
        add_edit({FltkNativeEditKind::selection,{},begin,begin+length,false,0});
        start_=begin;end_=begin+length;backward_=false;caret_current_=false;return TRUE;
    }
    LRESULT query_position(LPARAM parameter) const noexcept {
        if (!parameter||!editor_||!caret_current_||GetFocus()!=child_) return FALSE;
        auto* value=reinterpret_cast<IMECHARPOSITION*>(parameter);
        // We possess an actual caret, not glyph rectangles for arbitrary offsets.
        if (value->dwSize<sizeof(*value)||value->dwCharPos!=(composition_?cursor_:0)) return FALSE;
        POINT point{static_cast<LONG>(std::lround(caret_.x)),static_cast<LONG>(std::lround(caret_.y))};
        RECT document{};
        if (!ClientToScreen(root_,&point)||!GetClientRect(root_,&document)) return FALSE;
        POINT corners[2]{{document.left,document.top},{document.right,document.bottom}};
        if (!ClientToScreen(root_,&corners[0])||!ClientToScreen(root_,&corners[1])) return FALSE;
        value->pt=point;value->cLineHeight=static_cast<UINT>((std::max)(1.0,std::ceil(caret_.height)));
        value->rcDocument={corners[0].x,corners[0].y,corners[1].x,corners[1].y};return TRUE;
    }
    LRESULT message(HWND hwnd,UINT message,WPARAM wparam,LPARAM lparam) {
        if (message==WM_NCDESTROY) {
            clear_caret();SetWindowLongPtrW(hwnd,GWLP_USERDATA,0);child_=nullptr;
            if (!destroying_) fault("Win32 native input child was destroyed");
            return DefWindowProcW(hwnd,message,wparam,lparam);
        }
        if (message==WM_PAINT) { PAINTSTRUCT paint{};BeginPaint(hwnd,&paint);EndPaint(hwnd,&paint);return 0; }
        if (message==WM_ERASEBKGND) return 1;
        if (message==WM_GETDLGCODE) return DLGC_WANTALLKEYS|DLGC_WANTCHARS;
        if (message==WM_KILLFOCUS) {
            clear_caret();
            if (reinterpret_cast<HWND>(wparam)==root_&&foreground_&&!suspending_&&!failed_)
                return DefWindowProcW(hwnd,message,wparam,lparam);
            // Retire only this frontend's queued source. Provider cleanup and
            // focus publication remain the serialized owner's responsibility.
            foreground_=false;cancel_native();clear_pending();held_.clear();
            editor_=false;draft_.clear();start_=end_=0;backward_=false;caret_current_=false;
            (void)associate(nullptr);
            if (!mouse_capture(false)&&capture_owned_) fault("Cannot release Win32 capture on focus loss");
            return DefWindowProcW(hwnd,message,wparam,lparam);
        }
        if (message==WM_SETFOCUS) { if (editor_&&foreground_&&!failed_) position_ime();return 0; }
        if (message==boundary_message) {
            const auto serial=static_cast<std::uint64_t>(static_cast<std::uint32_t>(wparam))|
                (static_cast<std::uint64_t>(static_cast<std::uint32_t>(lparam))<<32);
            if (auto* item=find(serial)) {
                if (item->high) throw std::runtime_error("Incomplete Win32 native surrogate passage");
                item->sealed=true;
            }
            return 0;
        }
        if (message==WM_IME_SETCONTEXT)
            return DefWindowProcW(hwnd,message,wparam,lparam&~static_cast<LPARAM>(ISC_SHOWUICOMPOSITIONWINDOW));
        if (cancelling_&&(message==WM_IME_STARTCOMPOSITION||message==WM_IME_COMPOSITION||
                message==WM_IME_ENDCOMPOSITION||message==WM_IME_CHAR||message==WM_IME_REQUEST||message==WM_CHAR)) return 0;
        if (!foreground_||failed_) return DefWindowProcW(hwnd,message,wparam,lparam);
        if (editor_&&(message==WM_IME_STARTCOMPOSITION||message==WM_IME_COMPOSITION||
            message==WM_IME_ENDCOMPOSITION||message==WM_IME_REQUEST)&&!context_matches(context_))
            throw std::runtime_error("Win32 IME event no longer belongs to private context");
        switch (message) {
        case WM_KEYDOWN:case WM_KEYUP:case WM_SYSKEYDOWN:case WM_SYSKEYUP:
            return key(hwnd,message,wparam,lparam);
        case WM_CHAR:character(wparam,lparam,false);return 0;
        // System/menu characters are not committed editor text. Printable raw
        // logical keys remain Unidentified: WM_CHAR is not a key-name oracle.
        case WM_SYSCHAR:return DefWindowProcW(hwnd,message,wparam,lparam);
        case WM_UNICHAR:
            if (wparam==UNICODE_NOCHAR) return TRUE;
            character(wparam,lparam,true);return 0;
        case WM_DEADCHAR:case WM_SYSDEADCHAR:
            if (auto* item=character_passage(lparam)) {
                if (item->value.key) name_dead(*item);
            }
            return 0;
        case WM_IME_STARTCOMPOSITION:if (editor_) begin_composition();return 0;
        case WM_IME_COMPOSITION:if (editor_) ime_composition(lparam);return 0;
        case WM_IME_ENDCOMPOSITION:if (editor_) cancel_composition();return 0;
        // We consumed GCS_RESULTSTR; DefWindowProc must not manufacture a
        // second WM_CHAR insertion from the same result string.
        case WM_IME_CHAR:return 0;
        case WM_IME_REQUEST:
            if (!editor_) return 0;
            switch (wparam) {
            case IMR_RECONVERTSTRING:return reconvert(lparam,false);
            case IMR_DOCUMENTFEED:return reconvert(lparam,true);
            case IMR_CONFIRMRECONVERTSTRING:return confirm_reconvert(lparam);
            case IMR_QUERYCHARPOSITION:return query_position(lparam);
            default:return 0;
            }
        default:return DefWindowProcW(hwnd,message,wparam,lparam);
        }
    }
};

} // namespace foundation::host
