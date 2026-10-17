// SPDX-License-Identifier: CC0-1.0
// PRIVATE SOURCE OVERLAY. Real WebCore APIs below remain uncompiled/unexecuted.
#include "config.h"
#include "BibEngineProviderBinding.h"
#include "BibEngineProviderCatalog.h"
#include "BibEngineProviderCodec.h"
#include "BibEngineProviderInputState.h"
#include "BibEngineProviderPreflight.h"
#include "BibEngineProviderRuntime.h"
#include "BibEngineProviderLifecycleHooks.h"
#include "BibAppResources.h"
#include "BibFoundationServiceBridge.h"
#include "CommonVM.h"
#include "Editor.h"
#include "EventHandler.h"
#include "FocusController.h"
#include "HandleUserInputEventResult.h"
#include "LocalFrame.h"
#include "LocalFrameInlines.h"
#include "LocalFrameView.h"
#include "Page.h"
#include "PlatformKeyboardEvent.h"
#include "PlatformMouseEvent.h"
#include "PlatformWheelEvent.h"
#include "PointerCaptureController.h"
#include "PointerID.h"
#include "TextEventInputType.h"
#include "BibEngineProviderDocumentProjection.h"
#include <JavaScriptCore/JSLock.h>
#include <atomic>
#include <climits>
#include <cstring>
#include <memory>
#include <new>
#include <wtf/MonotonicTime.h>
#include <wtf/text/WTFString.h>

#if !defined(__EMSCRIPTEN__) || !BIB_ENGINE_PROVIDER_NEUTRAL || BIB_PTHREAD
#error "Actual binding v1 is only the explicit direct-owner browser CPU profile"
#endif

namespace bib::provider_candidate {
namespace {
constexpr std::uint64_t actual_caps=BIB_ENGINE_CAP_SERVICE_QUEUE|BIB_ENGINE_CAP_APP_BUNDLE
    |BIB_ENGINE_CAP_KEY_V1|BIB_ENGINE_CAP_FOCUS_V1|BIB_ENGINE_CAP_POINTER_V1|BIB_ENGINE_CAP_DIRTY_RGBA8;
struct State final {
    BibEngineBuildV1 build{};
    BibEngineLimitsV1 limits{};
    ServiceRetentionLimits retention{};
    std::uint64_t instance{};
    BibEngineHostV1 host{};
    std::unique_ptr<LegacyHostAdapters> adapters;
    BibFoundationServiceHostV1 services{};
    BibAppResourceBundleHostV1 resources{};
    BibEngineDocumentV1 input_document{};
    MouseState mouse;
    bool installed{}, started{};
};
// Process lifetime by contract: never reset, delete or unload after retention.
State* state=nullptr;
std::atomic<std::uint64_t> next_instance{1};
bool same(const BibEngineDocumentV1& a,const BibEngineDocumentV1& b) noexcept {
    return a.application_instance==b.application_instance && a.document_sequence==b.document_sequence
        && a.service_generation==b.service_generation;
}
bool faulted(const State& s) noexcept { return s.adapters && s.adapters->callback_faulted(); }
std::int32_t preflight(void*,const BibEngineStartV1* start) {
    return start ? validateActualStart(*start) : BIB_ENGINE_INVALID;
}
std::int32_t install(void* raw,const BibEngineHostV1* host,const BibEngineStartV1* start,std::uint64_t instance) {
    auto& s=*static_cast<State*>(raw);
    if (!host || !start || s.installed || instance!=s.instance) return BIB_ENGINE_INVALID;
    s.host=*host;
    // May fail after PROCESS_COMMITTED. The provider guard catches allocation
    // failure and poisons; the process-lived shell is deliberately retained.
    s.adapters=std::make_unique<LegacyHostAdapters>(*host,start->limits,s.retention);
    if (!s.adapters->valid() || !s.adapters->supports_resources() || !s.adapters->supports_services()) return BIB_ENGINE_INVALID;
    s.services=s.adapters->service_hooks(); s.resources=s.adapters->resource_bundle_hooks();
    const auto status=bib_app_resources_install_bundle(&s.resources,start->entry_url.data,start->entry_url.length,instance);
    if (status) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    s.installed=true;
    return BIB_ENGINE_OK;
}
std::int32_t start(void* raw,const BibEngineHostV1*,const BibEngineStartV1* config,std::uint64_t instance) {
    auto& s=*static_cast<State*>(raw);
    if (!config || !s.installed || s.started || instance!=s.instance || faulted(s)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    // Retain before Page/load can run author code; no diagnostic Registry exists.
    if (bib_foundation_services_install(&s.services)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    s.started=true;
    const BIB::ProviderRuntimeConfig runtime{&s.host,instance,config->persist_seed,config->raster_output};
    const auto result=BIB::bibProviderCreatePage(runtime);
    return faulted(s) ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : result;
}
std::int32_t advance(void* raw,const BibEngineAdvanceV1* request) {
    auto& s=*static_cast<State*>(raw);
    if (!request || faulted(s)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    const auto result=BIB::bibProviderStep(request->render);
    return faulted(s) ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : result;
}
std::int32_t current(void* raw,std::uint64_t instance,BibEngineDocumentV1* output) {
    auto& s=*static_cast<State*>(raw);
    if (!output || instance!=s.instance) return BIB_ENGINE_INVALID;
    if (faulted(s)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    BibAppDocumentIdentityV1 identity{}; identity.size=sizeof(identity); identity.version=BIB_APP_DOCUMENT_IDENTITY_VERSION;
    const auto result=bib_app_resources_current_identity(&identity);
    if (result!=1) return result ? BIB_ENGINE_WRONG_THREAD : BIB_ENGINE_STALE;
    if (identity.application_instance!=instance || !identity.document_sequence || !identity.service_generation) return BIB_ENGINE_STALE;
    // Explicit projection: the fourth private resource field is not authority.
    *output=BIB::bibProviderProjectDocument(identity);
    return BIB_ENGINE_OK;
}
WTF::OptionSet<WebCore::PlatformEvent::Modifier> modifiers(std::uint32_t bits) {
    using Modifier=WebCore::PlatformEvent::Modifier;
    WTF::OptionSet<Modifier> result;
    if (bits&1u) result.add(Modifier::ShiftKey);
    if (bits&2u) result.add(Modifier::ControlKey);
    if (bits&4u) result.add(Modifier::AltKey);
    if (bits&8u) result.add(Modifier::MetaKey);
    return result;
}
class MouseEvent final : public WebCore::PlatformMouseEvent {
public:
    MouseEvent(const codec::MouseInput& input,WebCore::MouseButton button,WebCore::PlatformEvent::Type type)
        : PlatformMouseEvent({input.x,input.y},{input.x,input.y},button,type,static_cast<int>(input.clicks),
            modifiers(input.modifiers),WTF::MonotonicTime::now(),0,WebCore::SyntheticClickType::NoTap,WebCore::mousePointerID) {
        // Pinned generic constructor leaves m_buttons=0. No WebCore edit needed.
        m_buttons=static_cast<unsigned short>(input.buttons);
    }
};
void cancelMouse(State& s,WebCore::Page& page,WebCore::LocalFrame& frame) {
    // Consume local state before pointercancel can invoke author JS. No fake
    // release event is sent: focus loss/cancel must never synthesize a click.
    s.mouse.clear();
    auto& capture=page.pointerCaptureController();
    const WebCore::IntPoint windowPoint{static_cast<int>(s.mouse.x()),static_cast<int>(s.mouse.y())};
    const auto documentPoint=frame.view() ? frame.view()->windowToContents(windowPoint) : windowPoint;
    capture.cancelPointer(WebCore::mousePointerID,documentPoint);
    capture.clearUnmatchedMouseDown(WebCore::mousePointerID);
    frame.eventHandler().clear();
    // First profile has exactly one mouse and no touch/pen owners. Reset the
    // cancelled controller state so the next physical press is a fresh stream.
    capture.reset();
}
std::int32_t command(void* raw,const BibEngineCommandV1* request,BibEngineReplyBufferV1*,BibEngineCommandResultV1* output) {
    auto& s=*static_cast<State*>(raw);
    if (!request || !output || faulted(s)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    codec::Input input;
    if (const auto status=codec::decode(request->operation,request->payload,input)) return status;
    const auto entered=[&]() -> std::int32_t {
    auto* page=BIB::bibProviderPage();
    if (!page) return BIB_ENGINE_CLOSED;
    // The outer ProviderGuard already holds the entire host engine turn. This
    // inner guard supplies the real Bridge's engineDepth for injected callbacks.
    // It is declared before JSLock: the final unlock/checkpoint runs first.
    BIB::FoundationServiceEngineCall bridge_turn;
    if (!bridge_turn) return BIB_ENGINE_REENTRANT;
    bool handled=false;
    {
        JSC::JSLockHolder lock(WebCore::commonVM());
        BibEngineDocumentV1 now{};
        if (const auto status=current(raw,s.instance,&now)) return status;
        if (!same(now,request->expected)) return BIB_ENGINE_STALE;
        if (!same(s.input_document,now)) { s.mouse.clear(); s.input_document=now; }
        RefPtr frame=page->focusController().focusedOrMainFrame();
        RefPtr main=page->localMainFrame();
        if (!frame || !main) return BIB_ENGINE_CLOSED;
        if (auto* key=std::get_if<codec::KeyInput>(&input)) {
            if (key->phase==codec::KeyPhase::committed_text) {
                // Actual editing/textinput path; keydown never inserts chars.
                handled=frame->editor().insertText(WTF::String::fromUTF8(key->text.c_str()),nullptr,WebCore::TextEventInputKeyboard);
            } else {
                const auto type=key->phase==codec::KeyPhase::down ? WebCore::PlatformEvent::Type::RawKeyDown : WebCore::PlatformEvent::Type::KeyUp;
                WebCore::PlatformKeyboardEvent event(type,WTF::String(),WTF::String(),WTF::String::fromUTF8(key->key.c_str()),
                    WTF::String::fromUTF8(key->code.c_str()),WTF::emptyString(),static_cast<int>(key->virtual_key),key->repeat,
                    false,false,modifiers(key->modifiers),WTF::MonotonicTime::now());
                handled=frame->eventHandler().keyEvent(event);
            }
        } else if (auto* focus=std::get_if<codec::FocusInput>(&input)) {
            if (!focus->focused || !focus->active) {
                cancelMouse(s,*page,*main);
                // No composition capability is negotiated. Defensively remove
                // an engine-created preedit, with no restoration claim.
                if (frame->editor().hasComposition()) frame->editor().setComposition(WTF::emptyString(),{},{},{},0,0);
            }
            page->focusController().setActive(focus->active);
            page->focusController().setFocused(focus->focused);
            handled=true;
        } else {
            const auto& mouse=std::get<codec::MouseInput>(input);
            if (!s.mouse.accepts(mouse)) return BIB_ENGINE_INVALID;
            s.mouse.consume(mouse);
            using codec::MousePhase;
            if (mouse.phase==MousePhase::cancel) { cancelMouse(s,*page,*main); handled=true; }
            else if (mouse.phase==MousePhase::wheel) {
                const auto mods=modifiers(mouse.modifiers);
                WebCore::PlatformWheelEvent event({static_cast<int>(mouse.x),static_cast<int>(mouse.y)},
                    {static_cast<int>(mouse.x),static_cast<int>(mouse.y)},static_cast<float>(-mouse.wheel_x),static_cast<float>(-mouse.wheel_y),
                    static_cast<float>(-mouse.wheel_x/120.0),static_cast<float>(-mouse.wheel_y/120.0),
                    WebCore::PlatformWheelEventGranularity::ScrollByPixelWheelEvent,
                    mods.contains(WebCore::PlatformEvent::Modifier::ShiftKey),mods.contains(WebCore::PlatformEvent::Modifier::ControlKey),
                    mods.contains(WebCore::PlatformEvent::Modifier::AltKey),mods.contains(WebCore::PlatformEvent::Modifier::MetaKey));
                handled=main->eventHandler().handleWheelEvent(event,{WebCore::WheelEventProcessingSteps::SynchronousScrolling,
                    WebCore::WheelEventProcessingSteps::BlockingDOMEventDispatch}).first.wasHandled();
            } else {
                constexpr WebCore::MouseButton buttons[]{WebCore::MouseButton::Left,WebCore::MouseButton::Middle,WebCore::MouseButton::Right};
                const auto type=mouse.phase==MousePhase::move ? WebCore::PlatformEvent::Type::MouseMoved
                    : mouse.phase==MousePhase::down ? WebCore::PlatformEvent::Type::MousePressed : WebCore::PlatformEvent::Type::MouseReleased;
                MouseEvent event(mouse,mouse.phase==MousePhase::move ? WebCore::MouseButton::None : buttons[mouse.button],type);
                if (mouse.phase==MousePhase::move) handled=main->eventHandler().mouseMoved(event).wasHandled();
                else if (mouse.phase==MousePhase::down) handled=main->eventHandler().handleMousePressEvent(event).wasHandled();
                else handled=main->eventHandler().handleMouseReleaseEvent(event).wasHandled();
            }
        }
    }
    output->bytes_written=0; output->handled=handled ? 1u : 0u;
    // ChromeClient suppresses its fallback scheduler. Input/JS may schedule
    // rAF or damage even when default handling reports false; wake only queues.
    s.host.wake(s.host.context);
    bridge_turn.finish(); // Nested leave may latch a host callback failure.
    return BIB_ENGINE_OK;
    };
    const auto result=entered(); // All inner returns destroy locks/Bridge guard.
    return faulted(s) ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : result;
}
std::int32_t query(void*,const BibEngineQueryV1*,BibEngineReplyBufferV1*,BibEngineQueryResultV1*) { return BIB_ENGINE_UNSUPPORTED; }
std::int32_t deliveryStatus(int value) {
    switch (value) {
    case BIB_FOUNDATION_SERVICE_DELIVERY_ACCEPTED: return BIB_ENGINE_OK;
    case BIB_FOUNDATION_SERVICE_DELIVERY_STALE: return BIB_ENGINE_STALE;
    case BIB_FOUNDATION_SERVICE_DELIVERY_WRONG_THREAD: return BIB_ENGINE_WRONG_THREAD;
    default: return BIB_ENGINE_INVALID;
    }
}
std::int32_t deliver(void* raw,const BibEngineDocumentV1* document,const BibEngineBytesV1* bytes) {
    auto& s=*static_cast<State*>(raw);
    if (!document || !bytes) return BIB_ENGINE_INVALID;
    if (faulted(s)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    // Export supplies its own Bridge guard/VM lock. Adding a Bridge guard here
    // would make its engineDepth check reject every delivery.
    const auto result=deliveryStatus(bib_foundation_services_deliver(document->service_generation,bytes->data,bytes->length));
    // Promise reactions/checkpoints can request rAF or damage without a timer.
    // Queue another owner turn after the complete existing bridge export.
    if (!faulted(s)) s.host.wake(s.host.context);
    return faulted(s) ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : result;
}
std::uint32_t collect(void* raw,const BibEngineDocumentV1* document) {
    auto& s=*static_cast<State*>(raw);
    if (faulted(s)) return 14u;
    const auto result=document ? bib_foundation_services_collect_ack(document->service_generation) : 2u;
    if (!faulted(s)) s.host.wake(s.host.context);
    // This callback's unsigned ServiceStatus cannot carry provider -8. Fault
    // remains sticky; report UNCERTAIN now, and current/advance/other entries
    // return PROCESS_EXIT_REQUIRED before any subsequent WebCore effect.
    return faulted(s) ? 14u : result;
}
std::int32_t dispose(void* raw,std::uint64_t instance,std::uint64_t generation) {
    auto& s=*static_cast<State*>(raw);
    if (instance!=s.instance || !generation) return BIB_ENGINE_INVALID;
    if (faulted(s)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    const auto result=deliveryStatus(bib_foundation_services_dispose_retired(generation));
    if (!faulted(s)) s.host.wake(s.host.context);
    return faulted(s) ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : result;
}
}

std::int32_t bindActualWebCoreProvider(const BibEngineBuildV1& build,const BibEngineLimitsV1& limits,
    ServiceRetentionLimits retention) noexcept {
    if (state || build.target_system!=BIB_ENGINE_TARGET_BROWSER_WASM || build.target_processor!=BIB_ENGINE_CPU_WASM32
        || build.pointer_bits!=32 || build.fixed_viewport_width!=800 || build.fixed_viewport_height!=600
        || build.capabilities!=actual_caps || !retention.max_retained_calls || retention.max_retained_bytes<64
        || !actualResourceLimits(limits) || limits.maximum_command_bytes<codec::maximum_key_bytes
        || limits.maximum_reply_bytes<codec::required_reply_capacity || limits.maximum_service_message_bytes<384)
        return BIB_ENGINE_UNSUPPORTED;
    auto instance=next_instance.load(std::memory_order_relaxed);
    do { if (!instance || instance==UINT64_MAX) return BIB_ENGINE_LIMIT; }
    while (!next_instance.compare_exchange_weak(instance,instance+1,std::memory_order_relaxed));
    auto candidate=std::unique_ptr<State>(new(std::nothrow) State);
    if (!candidate) return BIB_ENGINE_LIMIT;
    candidate->build=build; candidate->limits=limits; candidate->retention=retention; candidate->instance=instance;
    EnginePrivateV1 engine{sizeof(EnginePrivateV1),private_interface_version,build,limits,instance,candidate.get(),
        command_catalog.data(),static_cast<std::uint32_t>(command_catalog.size()),nullptr,0,preflight,start,advance,current,
        command,query,deliver,collect,dispose,install};
    const auto status=bind_engine_private(engine);
    if (status) return status;
    state=candidate.release(); // Process-lived after binding; never a host object.
    return BIB_ENGINE_OK;
}
}

namespace BIB {
bool bibProviderSetProspectiveDocument(std::uint64_t sequence) noexcept {
    using namespace bib::provider_candidate;
    if (!state || !state->adapters || !sequence || faulted(*state)) return false;
    return state->adapters->set_prospective_document({state->instance,sequence,0})==BIB_ENGINE_OK;
}
}
