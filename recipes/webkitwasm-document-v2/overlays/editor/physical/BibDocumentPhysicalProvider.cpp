// SPDX-License-Identifier: CC0-1.0
// NEW actual-WebCore source overlay. Header syntax/object/link/runtime UNRUN.
#include "config.h"
#include "BibDocumentPhysicalProvider.hpp"
#include "PhysicalState.hpp"
#include "NativeRawKeyDispatch.hpp"
#include "BibNativeKeyEventOutcome.hpp"
#include "HTMLSelectElement.h"
#include "KeyboardEvent.h"
#include "Node.h"
#include "NodeDocument.h"
#include "PlatformKeyboardEvent.h"
#include "Quirks.h"
#include "RenderMenuList.h"
#include "Settings.h"
#include "UserGestureIndicator.h"
#include "UserTypingGestureIndicator.h"
#include "WindowsKeyboardCodes.h"
#include "BibEngineProviderRuntime.h"
#include "BibEngineProviderDocumentProjection.h"
#include "BibFoundationServiceBridge.h"
#include "BibAppResources.h"
#include "ui/BibEngineUiOwner.hpp"
#include "popup/BibNativePopupOwner.hpp"
#include "CommonVM.h"
#include "ContainerNodeInlines.h"
#include "Document.h"
#include "DocumentQuirks.h"
#include "DocumentPage.h"
#include "DocumentView.h"
#include "EventHandler.h"
#include "FocusController.h"
#include "FrameDestructionObserverInlines.h"
#include "HandleUserInputEventResult.h"
#include "LocalFrame.h"
#include "LocalFrameInlines.h"
#include "LocalFrameView.h"
#include "MouseEventTypes.h"
#include "Page.h"
#include "PlatformMouseEvent.h"
#include "PlatformWheelEvent.h"
#include "PointerCaptureController.h"
#include "PointerID.h"
#include "ScrollingCoordinatorTypes.h"
#include <JavaScriptCore/JSLock.h>
#include <atomic>
#include <cmath>
#include <new>
#include <stdexcept>
#include <span>
#include <wtf/Assertions.h>
#include <wtf/MonotonicTime.h>

namespace bib::provider_candidate {
namespace {
namespace P=document_physical;
namespace I=foundation::appended::engine_input;
namespace K=foundation::appended::ndv2_physical;
auto modifiers(std::uint32_t bits) {
    using M=WebCore::PlatformEvent::Modifier;
    WTF::OptionSet<M> result;
    if (bits&1) result.add(M::ShiftKey);
    if (bits&2) result.add(M::ControlKey);
    if (bits&4) result.add(M::AltKey);
    if (bits&8) result.add(M::MetaKey);
    if (bits&16) result.add(M::AltGraphKey);
    return result;
}
WebCore::MouseButton nativeButton(std::int32_t ordinal) {
    constexpr WebCore::MouseButton buttons[]{WebCore::MouseButton::Left,WebCore::MouseButton::Middle,
        WebCore::MouseButton::Right,WebCore::MouseButton::Back,WebCore::MouseButton::Forward};
    return ordinal>=0 && ordinal<5 ? buttons[ordinal] : WebCore::MouseButton::None;
}
WebCore::IntPoint floorPoint(double x,double y) {
    return {static_cast<int>(std::floor(x)),static_cast<int>(std::floor(y))};
}
class MouseEvent final : public WebCore::PlatformMouseEvent {
public:
    MouseEvent(const I::Mouse& value,WebCore::MouseButton button,WebCore::PlatformEvent::Type type)
        : PlatformMouseEvent({value.x,value.y},{value.x,value.y},button,type,
            static_cast<int>((value.phase==1 || value.phase==2) && !value.clicks ? 1 : value.clicks),
            ::bib::provider_candidate::modifiers(value.modifiers),WTF::MonotonicTime::now(),0,WebCore::SyntheticClickType::NoTap,WebCore::mousePointerID) {
        m_buttons=static_cast<unsigned short>(value.buttons);
    }
};
class WheelEvent final : public WebCore::PlatformWheelEvent {
public:
    explicit WheelEvent(const I::Mouse& value)
        : PlatformWheelEvent(floorPoint(value.x,value.y),floorPoint(value.x,value.y),
            static_cast<float>(-value.wheel_x),static_cast<float>(-value.wheel_y),
            static_cast<float>(-value.wheel_x/120),static_cast<float>(-value.wheel_y/120),
            WebCore::PlatformWheelEventGranularity::ScrollByPixelWheelEvent,
            value.modifiers&1,value.modifiers&2,value.modifiers&4,value.modifiers&8) {
        m_modifiers=::bib::provider_candidate::modifiers(value.modifiers);
    }
};
}
struct ModernDocumentPhysicalProvider::Impl {
    struct KeyFence {
        Impl& provider;
        WebCore::LocalFrame& main;
        WebCore::Document& main_document;
        WebCore::LocalFrame& target;
        WebCore::Document& target_document;
        BibEngineDocumentV1 expected;
        std::uint64_t resource_epoch;
    };
    const std::uint64_t worker,instance;
    const DocumentPhysicalHooks hooks;
    P::PhysicalState state;
    std::atomic<bool> poisoned{};
    Impl(std::uint64_t epoch,std::uint64_t application,DocumentPhysicalHooks callbacks)
        : worker(epoch),instance(application),hooks(callbacks) {
        if (!worker || !instance || !hooks.on_owner || !hooks.callback_faulted || !hooks.queue_wake ||
            !hooks.invalidate_form_authority || !hooks.on_owner(hooks.context))
            throw std::invalid_argument("modern physical provider requires exact retained owner hooks/identity");
    }
    bool owner() const noexcept { return hooks.on_owner(hooks.context); }
    bool faulted() const noexcept { return poisoned.load(std::memory_order_acquire) || BIB::EngineUI::faulted() || hooks.callback_faulted(hooks.context); }
    static std::int32_t validate(void* raw,std::uint64_t worker,const BibEngineCommandV1* request) noexcept {
        auto& s=*static_cast<Impl*>(raw);
        if (!s.owner()) return BIB_ENGINE_WRONG_THREAD;
        if (s.faulted()) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
        if (worker!=s.worker || !request) return BIB_ENGINE_INVALID;
        try { P::Prepared prepared; return s.state.prepare(*request,s.instance,16,prepared); }
        catch (const std::bad_alloc&) { return BIB_ENGINE_LIMIT; }
        catch (...) { return BIB_ENGINE_INVALID; }
    }
    static std::int32_t reply(void* raw,std::uint64_t worker,const BibEngineCommandV1* request,const BibEngineBytesV1* bytes) noexcept {
        auto& s=*static_cast<Impl*>(raw);
        if (!s.owner()) return BIB_ENGINE_WRONG_THREAD;
        if (s.faulted()) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
        return worker==s.worker && request && bytes && s.state.reply_matches(*request,*bytes) ? BIB_ENGINE_OK : BIB_ENGINE_INVALID;
    }
    static void invalidate(void* raw) noexcept {
        auto& s=*static_cast<Impl*>(raw);
        if (!s.owner()) { s.poisoned.store(true,std::memory_order_release); return; }
        s.state.invalidate(); K::clearRawKeyModifiers();
    }
    bool current(const BibEngineDocumentV1& expected, WebCore::LocalFrame& main,WebCore::Document& document,
        std::uint64_t resource_epoch) const noexcept {
        BibAppDocumentIdentityV1 id{}; id.size=sizeof(id); id.version=BIB_APP_DOCUMENT_IDENTITY_VERSION;
        return owner() && !faulted() && bib_app_resources_current_identity(&id)==1 && id.resource_epoch==resource_epoch &&
            P::same(BIB::bibProviderProjectDocument(id),expected) && main.document()==&document &&
            BIB::bibProviderDocumentMainFrame().get()==&main && main.page()==BIB::bibProviderPage();
    }
    static bool keyAuthority(void* raw,const WebCore::LocalFrame& frame,const BibEngineDocumentV1& expected,
        std::uint64_t context,std::uint64_t sequence) noexcept {
        auto& fence=*static_cast<KeyFence*>(raw);
        auto& s=fence.provider;
        if (!s.owner() || s.faulted() || s.state.latest.sequence!=sequence ||
            !P::same(s.state.latest.document,expected) || !P::same(fence.expected,expected) ||
            s.state.input.active_context!=context || &frame!=&fence.target ||
            frame.document()!=&fence.target_document || frame.page()!=fence.main.page()) return false;
        return s.current(expected,fence.main,fence.main_document,fence.resource_epoch);
    }
    static bool selectPopupKey(const I::Key& key) noexcept {
        // A control activation, never an editor committed-text observation.
        return key.phase==0 && !key.repeat && key.key==" " && key.code=="Space"
            && key.location==0 && !(key.modifiers&30u);
    }
    static bool selectPopupRawReturned(const WebCore::KeyEventDispatchOutcome& outcome,bool handled) noexcept {
        using O=WebCore::KeyEventDispatchOutcome;
        return !handled && outcome.complete && !outcome.normalHandled
            && outcome.exit==O::Exit::RawKeyDownReturned
            && outcome.keydown.route==O::Route::DOMDispatch
            && outcome.keydown.defaultPrevented==O::Flag::No
            && outcome.keydown.defaultHandled==O::Flag::No
            && outcome.keydown.frame==O::Frame::SameFrameAndDocument
            && outcome.keydown.target==O::Target::OriginalTarget
            && outcome.keydown.focus==O::Focus::Unchanged;
    }
    bool selectPopupKeyCurrent(KeyFence& fence,WebCore::HTMLSelectElement& select,
        const BIB::EngineUI::Snapshot& snapshot,std::uint64_t physical_version,
        const I::Key& key,std::uint64_t sequence) const noexcept {
        return selectPopupKey(key) && state.version==physical_version
            && keyAuthority(&fence,fence.target,fence.expected,key.input_context,sequence)
            && BIB::EngineUI::matches(snapshot) && snapshot.owner==BIB::EngineUI::identity()
            && snapshot.owner.worker==worker && snapshot.owner.application==instance
            && snapshot.chrome==BIB::EngineUI::registeredChrome()
            && snapshot.page==fence.main.page() && snapshot.main_frame==&fence.main
            && snapshot.document==&fence.main_document
            && snapshot.document_sequence==fence.expected.document_sequence
            && snapshot.service_generation==fence.expected.service_generation
            && snapshot.resource_epoch==fence.resource_epoch && snapshot.input_context==key.input_context
            && snapshot.raster && !snapshot.modal && !BIB::EnginePopup::token()
            && fence.target.page()==snapshot.page && fence.target.document()==&fence.target_document
            && fence.target_document.frame()==&fence.target
            && fence.target_document.windowProxy()==&fence.target.windowProxy()
            && snapshot.page->focusController().focusedOrMainFrame()==&fence.target
            && &select.document()==&fence.target_document && select.isConnected()
            && fence.target_document.focusedElement()==&select && select.focused()
            && !select.multiple() && select.usesMenuList()
            && !fence.target_document.settings().spatialNavigationEnabled()
            && select.renderer() && is<WebCore::RenderMenuList>(select.renderer())
            // The select's disabled path delegates before checking defaultHandled.
            // Keep this final: no callback may intervene before virtual entry.
            && !select.isDisabledFormControl();
    }
    bool selectPopupPublished(KeyFence& fence,WebCore::HTMLSelectElement& select,
        std::uint64_t physical_version,const I::Key& key,std::uint64_t sequence,
        BIB::EnginePopup::Policy::PopupToken before) const noexcept {
        const auto opened=BIB::EnginePopup::token();
        BIB::EngineUI::Snapshot now;
        return opened && opened!=before && state.version==physical_version
            && keyAuthority(&fence,fence.target,fence.expected,key.input_context,sequence)
            && BIB::EngineUI::borrowCurrent(now) && now.owner==BIB::EngineUI::identity()
            && now.owner.worker==worker && now.owner.application==instance
            && now.chrome==BIB::EngineUI::registeredChrome()
            && now.page==fence.main.page() && now.main_frame==&fence.main
            && now.document==&fence.main_document && now.document_sequence==fence.expected.document_sequence
            && now.service_generation==fence.expected.service_generation
            && now.resource_epoch==fence.resource_epoch && now.input_context==key.input_context
            && now.raster && now.modal && now.modal_epoch==opened.epoch
            && &select.document()==&fence.target_document && select.isConnected() && select.popupIsVisible();
    }
    bool dispatchSelectPopupKeypress(KeyFence& fence,WebCore::HTMLSelectElement& select,
        const BIB::EngineUI::Snapshot& snapshot,std::uint64_t physical_version,
        const I::Key& key,std::uint64_t sequence,BIB::EnginePopup::Policy::PopupToken before) {
        if (!selectPopupKeyCurrent(fence,select,snapshot,physical_version,key,sequence)) return false;
        const auto text=WTF::String::fromUTF8(std::span<const char>(key.key.data(),key.key.size()));
        const auto code=WTF::String::fromUTF8(std::span<const char>(key.code.data(),key.code.size()));
        RELEASE_ASSERT(!text.isNull() && !code.isNull());
        WebCore::PlatformKeyboardEvent platform(WebCore::PlatformEvent::Type::Char,text,text,text,code,
            WTF::String(),VK_SPACE,false,false,false,modifiers(key.modifiers),WTF::MonotonicTime::now());
        auto event=WebCore::KeyboardEvent::create(platform,&fence.target.windowProxy());
        // Match EventHandler's native Char scopes without another activation or
        // any editor TextData ticket. The original raw call already returned.
        const auto paste=fence.target_document.quirks().needsDisableDOMPasteAccessQuirk()
            ? WebCore::CanRequestDOMPaste::No : WebCore::CanRequestDOMPaste::Yes;
        WebCore::UserGestureIndicator gesture(WebCore::IsProcessingUserGesture::Yes,&fence.target_document,
            WebCore::UserGestureType::Other,WebCore::UserGestureIndicator::ProcessInteractionStyle::Delayed,
            platform.authorizationToken(),paste);
        WebCore::UserTypingGestureIndicator typing(fence.target);
        if (event->isComposing()
            || !selectPopupKeyCurrent(fence,select,snapshot,physical_version,key,sequence)) return false;
        event->setIsDefaultEventHandlerIgnored();
        // Preserve Element::dispatchKeyEvent's native accessibility propagation
        // policy while retaining this exact event with automatic defaults off.
        if (fence.target.eventHandler().accessibilityPreventsEventPropagation(event)) event->stopPropagation();
        if (!selectPopupKeyCurrent(fence,select,snapshot,physical_version,key,sequence)) return false;
        select.dispatchEvent(event);
        if (event->defaultPrevented()) return true; // Actual author cancellation.
        if (event->target()!=&select
            || !selectPopupKeyCurrent(fence,select,snapshot,physical_version,key,sequence)) return false;
        // resetBeforeDispatch erased any earlier handled marker. Seal only now;
        // this is a fallback barrier, NEVER a physical handled/success receipt.
        event->setDefaultHandled();
        static_cast<WebCore::Node&>(select).defaultEventHandler(event);
        // showPopup may run script. Borrow fresh ownership; never trust the seal.
        return selectPopupPublished(fence,select,physical_version,key,sequence,before);
    }
    void cancel(WebCore::Page& page,WebCore::LocalFrame& main,WebCore::Document& current_document,
        const BibEngineDocumentV1& expected,std::uint64_t resource_epoch,const I::State& previous) {
        if (!previous.capture_token || !previous.has_last_point) return;
        const auto window=floorPoint(previous.last_x,previous.last_y);
        const auto document=main.view() ? main.view()->windowToContents(window) : window;
        auto& capture=page.pointerCaptureController();
        capture.cancelPointer(WebCore::mousePointerID,document);
        // pointercancel/out/leave/lostcapture can run author code. Never clear
        // a replacement document's state using this old document checkpoint.
        if (!current(expected,main,current_document,resource_epoch)) return;
        capture.clearUnmatchedMouseDown(WebCore::mousePointerID);
        main.eventHandler().clear();
        if (!current(expected,main,current_document,resource_epoch)) return;
        // Real cancellation/retirement only, never a context intent. This
        // explicit profile has one mouse and no touch/pen provider owners.
        capture.reset();
    }
    static BIB::EnginePopup::Policy::PointerState pointerState(const I::State& value) noexcept {
        return {value.active_context,value.capture_token,value.buttons};
    }
    bool handoffMatches(const BIB::EnginePopup::Handoff& handoff,WebCore::Page& page,
        WebCore::LocalFrame& main,WebCore::Document& document,
        const BibEngineDocumentV1& expected,std::uint64_t resource_epoch) const noexcept {
        if (!current(expected,main,document,resource_epoch) || state.version!=handoff.physical_version
            || state.latest.sequence!=handoff.sequence || !P::same(state.latest.document,expected)
            || pointerState(state.input)!=handoff.pointer || !BIB::EnginePopup::handoffCurrent(handoff)) return false;
        BIB::EngineUI::Snapshot snapshot;
        if (!BIB::EngineUI::borrowCurrent(snapshot)) return false;
        const auto& key=handoff.key;
        return snapshot.page==&page && snapshot.main_frame==&main && snapshot.document==&document
            && snapshot.owner.runtime_generation==key.runtime && snapshot.owner.worker==key.worker
            && snapshot.owner.application==key.application && key.application==expected.application_instance
            && snapshot.document_sequence==key.document && key.document==expected.document_sequence
            && snapshot.service_generation==key.service && key.service==expected.service_generation
            && snapshot.resource_epoch==key.resource && key.resource==resource_epoch
            && snapshot.input_context==key.input_context && key.input_context==state.input.active_context;
    }
    void afterPageInput(BIB::EnginePopup::Policy::PopupToken before,const I::Key* key,const I::Mouse* mouse,
        WebCore::Page& page,WebCore::LocalFrame& main,WebCore::Document& document,
        const BibEngineDocumentV1& expected,std::uint64_t resource_epoch,
        std::uint64_t physical_version,std::uint64_t sequence) {
        // The original native EventHandler has already returned. Never replay it
        // or alter committed portable capture/buttons to perform this handoff.
        if (!current(expected,main,document,resource_epoch) || state.version!=physical_version
            || state.latest.sequence!=sequence) return;
        const auto handoff=BIB::EnginePopup::afterPageInput(before,key,mouse,pointerState(state.input),
            state.input.last_x,state.input.last_y,state.input.has_last_point,physical_version,sequence);
        if (!handoff) return;
        BIB::EngineUI::Snapshot pinned;
        const bool have_snapshot=BIB::EngineUI::borrowCurrent(pinned);
        auto matches=[&] { return have_snapshot && BIB::EngineUI::matches(pinned)
            && handoffMatches(*handoff,page,main,document,expected,resource_epoch); };
        bool completed=matches();
        bool native_effects_started=false;
        if (completed && handoff->pointer.capture_token) {
            completed=state.input.has_last_point;
            if (completed) {
                const auto window=floorPoint(state.input.last_x,state.input.last_y);
                RefPtr view=main.view();
                const auto point=view ? view->windowToContents(window) : window;
                completed=matches();
                if (completed) {
                    auto& capture=page.pointerCaptureController();
                    native_effects_started=true; // Exact first potentially author-calling native effect.
                    capture.cancelPointer(WebCore::mousePointerID,point);
                    completed=matches();
                    if (completed) {
                        capture.clearUnmatchedMouseDown(WebCore::mousePointerID);
                        completed=matches();
                    }
                    if (completed) {
                        main.eventHandler().clear();
                        completed=matches();
                    }
                    if (completed) {
                        capture.reset();
                        completed=matches();
                    }
                }
            }
        }
        BIB::EnginePopup::finishHandoff(*handoff,completed,native_effects_started);
    }
    static std::int32_t command(void* raw,const BibEngineCommandV1* request,BibEngineReplyBufferV1* buffer,
        BibEngineCommandResultV1* result) noexcept {
        auto& s=*static_cast<Impl*>(raw);
        if (!s.owner()) return BIB_ENGINE_WRONG_THREAD;
        if (s.faulted()) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
        if (!request || !buffer || buffer->size!=sizeof(*buffer) || !buffer->bytes || buffer->capacity<16 ||
            !result || result->size!=sizeof(*result)) return BIB_ENGINE_INVALID;
        bool consumed=false;
        try {
            P::Prepared prepared;
            if (auto status=s.state.prepare(*request,s.instance,buffer->capacity,prepared)) return status;
            const auto* focus=std::get_if<I::Focus>(&prepared.input);
            if (focus && focus->action==1) {
                // Metadata bind: no Frame/Page/getter/Bridge/JSC/Host callback.
                if (!s.state.commit(prepared) || !s.state.finish(prepared.key)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
                if (!BIB::EngineUI::setInputContext(s.state.input.active_context)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
                result->bytes_written=0; result->handled=0; return BIB_ENGINE_OK;
            }
            BIB::FoundationServiceEngineCall bridge;
            if (!bridge) return BIB_ENGINE_REENTRANT;
            bool handled=false;
            {
                JSC::JSLockHolder lock(WebCore::commonVM());
                RefPtr main=BIB::bibProviderDocumentMainFrame();
                auto* page=BIB::bibProviderPage();
                RefPtr document=main ? main->document() : nullptr;
                BibAppDocumentIdentityV1 id{}; id.size=sizeof(id); id.version=BIB_APP_DOCUMENT_IDENTITY_VERSION;
                if (!page || !main || !document || main->page()!=page ||
                    bib_app_resources_current_identity(&id)!=1 || !id.resource_epoch ||
                    !P::same(BIB::bibProviderProjectDocument(id),request->expected))
                    return BIB_ENGINE_STALE;
                BIB::EnginePopup::reconcile();
                if (s.faulted()) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
                if (!s.current(request->expected,*main,*document,id.resource_epoch)) return BIB_ENGINE_STALE;
                RefPtr frame=page->focusController().focusedOrMainFrame();
                if (!frame || frame->page()!=page || !frame->document()) return BIB_ENGINE_STALE;
                if (!s.state.commit(prepared)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
                consumed=true;
                const auto physical_version=s.state.version;
                if (!BIB::EngineUI::setInputContext(s.state.input.active_context)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
                s.hooks.invalidate_form_authority(s.hooks.context);
                if (auto* key=std::get_if<I::Key>(&prepared.input)) {
                    K::updateRawKeyModifiers(key->modifiers);
                    const auto before=BIB::EnginePopup::token();
                    const auto routed=BIB::EnginePopup::routeKey(*key);
                    if (s.faulted()) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
                    if (routed.claimed) handled=routed.handled;
                    else {
                        if (!s.current(request->expected,*main,*document,id.resource_epoch)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
                        RefPtr target_document=frame->document();
                        if (!target_document || frame->page()!=page) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
                        KeyFence fence{s,*main,*document,*frame,*target_document,request->expected,id.resource_epoch};
                        RefPtr<WebCore::HTMLSelectElement> select;
                        BIB::EngineUI::Snapshot key_snapshot;
                        bool select_key=false;
                        if (selectPopupKey(*key) && !before) {
                            select=dynamicDowncast<WebCore::HTMLSelectElement>(target_document->focusedElement());
                            select_key=select && BIB::EngineUI::borrowCurrent(key_snapshot)
                                && s.selectPopupKeyCurrent(fence,*select,key_snapshot,physical_version,*key,request->request_sequence);
                        }
                        if (select_key) {
                            WebCore::KeyEventDispatchOutcome outcome;
                            handled=K::dispatchKeyWithOutcome(*frame,*key,request->expected,request->request_sequence,keyAuthority,&fence,outcome);
                            if (selectPopupRawReturned(outcome,handled))
                                handled=s.dispatchSelectPopupKeypress(fence,*select,key_snapshot,physical_version,*key,
                                    request->request_sequence,before) || handled;
                        } else
                            handled=K::dispatchKey(*frame,*key,request->expected,request->request_sequence,keyAuthority,&fence);
                        s.afterPageInput(before,key,nullptr,*page,*main,*document,request->expected,id.resource_epoch,
                            physical_version,request->request_sequence);
                    }
                }
                else if (focus) {
                    BIB::EnginePopup::observeFocus(pointerState(prepared.previous),pointerState(s.state.input),
                        s.state.input.focused,s.state.input.active);
                    if (s.faulted()) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
                    if (focus->action==2 || !focus->focused || !focus->active) {
                        K::clearRawKeyModifiers(); s.cancel(*page,*main,*document,request->expected,id.resource_epoch,prepared.previous);
                    }
                    if (s.current(request->expected,*main,*document,id.resource_epoch)) {
                        page->focusController().setActive(focus->active!=0);
                        if (s.current(request->expected,*main,*document,id.resource_epoch))
                            page->focusController().setFocused(focus->focused!=0);
                    }
                    // Native focus/cancel APIs return void; no fabricated handled verdict.
                } else {
                    const auto& mouse=std::get<I::Mouse>(prepared.input);
                    K::updateRawKeyModifiers(mouse.modifiers);
                    const auto before=BIB::EnginePopup::token();
                    const auto routed=BIB::EnginePopup::routePointer(mouse,pointerState(prepared.previous),pointerState(s.state.input));
                    if (s.faulted()) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
                    if (routed.claimed) handled=routed.handled;
                    else {
                        if (!s.current(request->expected,*main,*document,id.resource_epoch)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
                        if (mouse.phase==4) s.cancel(*page,*main,*document,request->expected,id.resource_epoch,prepared.previous);
                        else if (mouse.phase==3) {
                            WheelEvent event(mouse);
                            handled=main->eventHandler().handleWheelEvent(event,{WebCore::WheelEventProcessingSteps::SynchronousScrolling,
                                WebCore::WheelEventProcessingSteps::BlockingDOMEventDispatch}).first.wasHandled();
                        } else if (mouse.phase==5) {
                            if (mouse.context_origin==1) handled=frame->eventHandler().sendContextMenuEventForKey();
                            else handled=main->eventHandler().sendContextMenuEvent(MouseEvent(mouse,WebCore::MouseButton::Right,WebCore::PlatformEvent::Type::MousePressed));
                            // Preserve exact portable/native capture through normal context route.
                        } else {
                            using T=WebCore::PlatformEvent::Type;
                            const auto type=mouse.phase==0 ? T::MouseMoved : mouse.phase==1 ? T::MousePressed : T::MouseReleased;
                            MouseEvent event(mouse,nativeButton(mouse.phase==0 ? I::native_move_button(mouse.buttons) : static_cast<std::int32_t>(mouse.button)),type);
                            if (mouse.phase==0) handled=main->eventHandler().mouseMoved(event).wasHandled();
                            else if (mouse.phase==1) handled=main->eventHandler().handleMousePressEvent(event).wasHandled();
                            else handled=main->eventHandler().handleMouseReleaseEvent(event).wasHandled();
                        }
                        s.afterPageInput(before,nullptr,&mouse,*page,*main,*document,request->expected,id.resource_epoch,
                            physical_version,request->request_sequence);
                    }
                }
            }
            bridge.finish(); // Final VM unlock/checkpoints preceded this leave.
            if (s.faulted() || !s.state.finish(prepared.key)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
            result->bytes_written=0; result->handled=handled?1u:0u;
            s.hooks.queue_wake(s.hooks.context); // Schedule only, after native turn.
            return s.faulted() ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : BIB_ENGINE_OK;
        } catch (const std::bad_alloc&) {
            if (!consumed) return BIB_ENGINE_LIMIT;
        } catch (...) {}
        s.poisoned.store(true,std::memory_order_release);
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    }
};
ModernDocumentPhysicalProvider::ModernDocumentPhysicalProvider(std::uint64_t worker,std::uint64_t instance,DocumentPhysicalHooks hooks)
    : impl_(std::make_unique<Impl>(worker,instance,hooks)) {}
ModernDocumentPhysicalProvider::~ModernDocumentPhysicalProvider()=default;
bool ModernDocumentPhysicalProvider::editor_authority(const BibEngineDocumentV1& expected, std::uint64_t& context) const noexcept {
    const auto& s=*impl_;
    if(!s.owner()||s.faulted()||!P::same(s.state.document,expected)||!s.state.input.active_context)return false;
    context=s.state.input.active_context;return true;
}
NativeDocumentPhysicalCallbacks ModernDocumentPhysicalProvider::callbacks() noexcept {
    return {sizeof(NativeDocumentPhysicalCallbacks),document_physical_callbacks_version,impl_.get(),
        Impl::validate,Impl::reply,Impl::command,Impl::invalidate};
}
} // namespace bib::provider_candidate
