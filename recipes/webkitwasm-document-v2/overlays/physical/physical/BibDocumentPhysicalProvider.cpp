// SPDX-License-Identifier: CC0-1.0
// NEW actual-WebCore source overlay. Header syntax/object/link/runtime UNRUN.
#include "config.h"
#include "BibDocumentPhysicalProvider.hpp"
#include "PhysicalState.hpp"
#include "NativeRawKeyDispatch.hpp"
#include "BibEngineProviderRuntime.h"
#include "BibEngineProviderDocumentProjection.h"
#include "BibFoundationServiceBridge.h"
#include "BibAppResources.h"
#include "ui/BibEngineUiOwner.hpp"
#include "popup/BibNativePopupOwner.hpp"
#include "CommonVM.h"
#include "Document.h"
#include "DocumentPage.h"
#include "DocumentView.h"
#include "EventHandler.h"
#include "FocusController.h"
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
NativeDocumentPhysicalCallbacks ModernDocumentPhysicalProvider::callbacks() noexcept {
    return {sizeof(NativeDocumentPhysicalCallbacks),document_physical_callbacks_version,impl_.get(),
        Impl::validate,Impl::reply,Impl::command,Impl::invalidate};
}
} // namespace bib::provider_candidate
