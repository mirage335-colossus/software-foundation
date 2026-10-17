// SPDX-License-Identifier: CC0-1.0
// PRIVATE DISABLED CANDIDATE. Source-reviewed against the pinned JSC/WebCore;
// this translation unit has not been compiled or executed against the engine.
#include "config.h"
#include "BibFoundationServiceBridge.h"

#if BIB_FOUNDATION_SERVICES

#include "BibFoundationServiceHost.h"
#include "BibFoundationServicesBootstrap.h"
#include "DOMWrapperWorld.h"
#include "Document.h"
#include "ExceptionDetails.h"
#include "JSDOMGlobalObject.h"
#include "JSExecState.h"
#include "JSWindowProxy.h"
#include "LocalFrame.h"
#include "LocalFrameInlines.h"
#include "ScriptController.h"
#include "WindowProxy.h"
#include <JavaScriptCore/CallFrameInlines.h>
#include <JavaScriptCore/JSCInlines.h>
#include <JavaScriptCore/JSFunction.h>
#include <JavaScriptCore/JSLock.h>
#include <JavaScriptCore/StrongInlines.h>
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <limits>
#include <memory>
#include <new>
#include <span>
#include <thread>
#include <wtf/Assertions.h>
#include <wtf/NeverDestroyed.h>
#include <wtf/Ref.h>
#include <wtf/RefPtr.h>
#include <wtf/WeakPtr.h>
#include <wtf/text/WTFString.h>

namespace BIB {
namespace {

// Private copies of the stable numeric statuses; no foundation C++ types cross
// the no-exception engine boundary. The host validates the complete envelopes.
constexpr uint32_t serviceOK = 0;
constexpr uint32_t serviceInvalidRequest = 1;
constexpr uint32_t serviceUnavailable = 2;
constexpr uint32_t serviceConflict = 6;
constexpr uint32_t serviceClosed = 10;
constexpr uint32_t serviceUncertain = 14;
constexpr uint32_t maximumRetiredDocuments = 64;

enum class NativeMethod { enqueue, cancel, acknowledge };

struct Epoch {
    Epoch(JSC::VM& machine, WebCore::Document& currentDocument, uint64_t currentGeneration)
        : vm(machine)
        , document(&currentDocument)
        , generation(currentGeneration)
    {
    }

    ~Epoch()
    {
        // Strong's default destructor does not acquire the API lock. In normal
        // use disposeRetired clears these first, still inside its engine guard.
        JSC::JSLockHolder lock(vm.get());
        clearRoots();
    }

    void clearRoots()
    {
        receive.clear();
        acknowledge.clear();
        dispose.clear();
        controller.clear();
        enqueueFunction.clear();
        cancelFunction.clear();
        acknowledgeFunction.clear();
        global.clear();
    }

    Ref<JSC::VM> vm; // Strong handles alone do not keep their VM alive.
    RefPtr<WebCore::Document> document;
    uint64_t generation { 0 };
    JSC::Strong<JSC::JSGlobalObject> global;
    JSC::Strong<JSC::JSFunction> enqueueFunction;
    JSC::Strong<JSC::JSFunction> cancelFunction;
    JSC::Strong<JSC::JSFunction> acknowledgeFunction;
    JSC::Strong<JSC::JSObject> controller;
    JSC::Strong<JSC::JSObject> receive;
    JSC::Strong<JSC::JSObject> acknowledge;
    JSC::Strong<JSC::JSObject> dispose;
    uint32_t unconfirmedLength { 0 };
    bool ready { false };
    bool closed { false };
    bool unconfirmedDelivery { false };
};

struct BridgeState {
    // This process-lifetime holder is intentional: VM-bound roots are released
    // explicitly on the owner, never by static destruction after engine exit.
    std::atomic<bool> installed { false };
    BibFoundationServiceHostV1 hooks { };
    std::thread::id owner;
    WeakPtr<WebCore::LocalFrame> selectedFrame;
    RefPtr<WebCore::Document> selectedDocument;
    std::unique_ptr<Epoch> active;
    std::unique_ptr<std::unique_ptr<Epoch>[]> retired;
    std::unique_ptr<uint8_t[]> decodeBytes;
    std::unique_ptr<uint8_t[]> unconfirmedBytes;
    std::unique_ptr<Latin1Character[]> hexCharacters;
    uint32_t retiredCount { 0 };
    uint32_t engineDepth { 0 };
    uint32_t hostCallbackDepth { 0 };
    uint32_t nativeCallbackDepth { 0 };
    bool selectionAttempted { false };
    bool disposing { false };
    bool shuttingDown { false };
};

BridgeState& bridge()
{
    static NeverDestroyed<BridgeState> state;
    return state.get();
}

bool installed()
{
    return bridge().installed.load(std::memory_order_acquire);
}

bool onOwner()
{
    return installed() && bridge().owner == std::this_thread::get_id();
}

class HostCallback final {
public:
    HostCallback() { ++bridge().hostCallbackDepth; }
    ~HostCallback() { --bridge().hostCallbackDepth; }
};

class NativeCallback final {
public:
    NativeCallback() { ++bridge().nativeCallbackDepth; }
    ~NativeCallback() { --bridge().nativeCallbackDepth; }
};

uint32_t checkedStatus(uint32_t value)
{
    return value <= serviceUncertain ? value : serviceUncertain;
}

void scheduleOwner()
{
    HostCallback callback;
    auto& state = bridge();
    state.hooks.schedule_owner(state.hooks.context);
}

void closeHost(uint64_t generation)
{
    HostCallback callback;
    auto& state = bridge();
    state.hooks.close_document(state.hooks.context, generation);
}

// Active state owns one reserved future retirement slot. No loader mutation
// allocates, executes JavaScript, or destroys roots while transferring it.
void retireActive()
{
    auto& state = bridge();
    if (!state.active)
        return;
    state.active->closed = true;
    state.active->ready = false;
    const auto generation = state.active->generation;
    uint32_t slot = 0;
    while (slot < state.hooks.max_retired_documents && state.retired[slot])
        ++slot;
    RELEASE_ASSERT(slot < state.hooks.max_retired_documents);
    state.retired[slot] = std::move(state.active);
    ++state.retiredCount;
    closeHost(generation);
    scheduleOwner();
}

bool currentDocumentMatches(const Epoch& epoch)
{
    auto& state = bridge();
    if (epoch.closed || state.shuttingDown || state.active.get() != &epoch)
        return false;
    auto* frame = state.selectedFrame.get();
    if (!frame || !frame->isMainFrame() || state.selectedDocument.get() != epoch.document.get()
        || frame->document() != epoch.document.get() || !epoch.global)
        return false;
    auto& world = WebCore::mainThreadNormalWorldSingleton();
    auto* proxy = frame->windowProxy().existingJSWindowProxy(world);
    if (!proxy || proxy->window() != epoch.global.get())
        return false;
    // A reused DOMWindow may already observe a successor Document before the
    // frame's setDocument callback. Never infer document identity from global.
    auto* global = static_cast<WebCore::JSDOMGlobalObject*>(epoch.global.get());
    return global->scriptExecutionContext() == epoch.document.get();
}

Epoch* activeEpoch(uint64_t generation)
{
    auto& state = bridge();
    auto* epoch = state.active.get();
    if (!epoch || state.shuttingDown || epoch->closed || !epoch->ready
        || epoch->generation != generation || !currentDocumentMatches(*epoch))
        return nullptr;
    return epoch;
}

Epoch* nativeEpoch(JSC::JSGlobalObject* global, JSC::CallFrame* frame, NativeMethod method)
{
    if (!onOwner())
        return nullptr;
    auto& state = bridge();
    if (!state.engineDepth || state.hostCallbackDepth || !state.active)
        return nullptr;
    auto* epoch = activeEpoch(state.active->generation);
    if (!epoch || epoch->global.get() != global)
        return nullptr;
    JSC::JSFunction* expected = method == NativeMethod::enqueue ? epoch->enqueueFunction.get()
        : method == NativeMethod::cancel ? epoch->cancelFunction.get() : epoch->acknowledgeFunction.get();
    // JSNativeStdFunction uses the same jsCallee() API. Comparing the actual
    // rooted function also rejects an old native function on a reused global.
    return frame->jsCallee() == expected ? epoch : nullptr;
}

JSC::EncodedJSValue statusValue(uint32_t status)
{
    return JSC::JSValue::encode(JSC::jsNumber(status));
}

int hexDigit(char16_t character)
{
    if (character >= '0' && character <= '9')
        return character - '0';
    if (character >= 'a' && character <= 'f')
        return character - 'a' + 10;
    return -1;
}

bool validHex(const String& text)
{
    for (unsigned index = 0; index < text.length(); ++index) {
        if (hexDigit(text[index]) < 0)
            return false;
    }
    return true;
}

bool readControl(const String& text, uint64_t& output)
{
    if (text.length() != 16 || !validHex(text))
        return false;
    uint64_t value = 0;
    for (unsigned index = 0; index < 16; ++index)
        value = (value << 4) | static_cast<uint64_t>(hexDigit(text[index]));
    if (!value)
        return false;
    output = value;
    return true;
}

String generationHex(uint64_t generation)
{
    constexpr char digits[] = "0123456789abcdef";
    Latin1Character text[16];
    for (unsigned index = 0; index < 16; ++index)
        text[index] = digits[(generation >> ((15 - index) * 4)) & 15];
    return String { std::span<const Latin1Character>(text) };
}

JSC_DEFINE_HOST_FUNCTION(enqueueHex, (JSC::JSGlobalObject* global, JSC::CallFrame* frame))
{
    auto& vm = global->vm();
    auto scope = DECLARE_THROW_SCOPE(vm);
    auto* epoch = nativeEpoch(global, frame, NativeMethod::enqueue);
    if (!epoch)
        return statusValue(serviceClosed);
    auto& state = bridge();
    if (state.nativeCallbackDepth)
        return statusValue(serviceConflict);
    NativeCallback nativeCallback;
    if (frame->argumentCount() != 2 || !frame->argument(0).isString() || !frame->argument(1).isNumber())
        return statusValue(serviceInvalidRequest);
    auto* input = JSC::asString(frame->argument(0));
    const auto characters = input->length();
    const double sourceNumber = frame->argument(1).asNumber();
    if (characters < 128 || (characters & 1) || characters > state.hooks.max_message_bytes * 2
        || !std::isfinite(sourceNumber) || sourceNumber != std::trunc(sourceNumber)
        || sourceNumber < 0 || sourceNumber > 2)
        return statusValue(serviceInvalidRequest);
    // Check the rope's length before flattening. Keep the GC-owned data scope
    // alive, and never decode/enter the host with a pending allocation exception.
    auto text = input->value(global);
    RETURN_IF_EXCEPTION(scope, { });
    if (!validHex(text.data))
        return statusValue(serviceInvalidRequest);
    const auto length = characters / 2;
    for (unsigned index = 0; index < length; ++index)
        state.decodeBytes[index] = static_cast<uint8_t>((hexDigit(text[index * 2]) << 4) | hexDigit(text[index * 2 + 1]));
    uint32_t status;
    {
        HostCallback callback;
        status = checkedStatus(state.hooks.submit(state.hooks.context, epoch->generation,
            state.decodeBytes.get(), length, static_cast<uint32_t>(sourceNumber)));
    }
    if (status == serviceOK || status == serviceUncertain)
        scheduleOwner();
    return statusValue(status);
}

JSC::EncodedJSValue controlHex(JSC::JSGlobalObject* global, JSC::CallFrame* frame, NativeMethod method)
{
    auto& vm = global->vm();
    auto scope = DECLARE_THROW_SCOPE(vm);
    auto* epoch = nativeEpoch(global, frame, method);
    if (!epoch)
        return statusValue(serviceClosed);
    auto& state = bridge();
    if (state.nativeCallbackDepth)
        return statusValue(serviceConflict);
    NativeCallback nativeCallback;
    if (frame->argumentCount() != 2 || !frame->argument(0).isString() || !frame->argument(1).isString())
        return statusValue(serviceInvalidRequest);
    auto* generationInput = JSC::asString(frame->argument(0));
    auto* sequenceInput = JSC::asString(frame->argument(1));
    if (generationInput->length() != 16 || sequenceInput->length() != 16)
        return statusValue(serviceInvalidRequest);
    auto generationText = generationInput->value(global);
    RETURN_IF_EXCEPTION(scope, { });
    auto sequenceText = sequenceInput->value(global);
    RETURN_IF_EXCEPTION(scope, { });
    uint64_t generation = 0;
    uint64_t sequence = 0;
    if (!readControl(generationText.data, generation) || !readControl(sequenceText.data, sequence))
        return statusValue(serviceInvalidRequest);
    if (generation != epoch->generation)
        return statusValue(serviceClosed);
    uint32_t status;
    {
        HostCallback callback;
        status = checkedStatus(method == NativeMethod::cancel
            ? state.hooks.cancel(state.hooks.context, generation, sequence)
            : state.hooks.acknowledge(state.hooks.context, generation, sequence));
    }
    if (status == serviceOK || status == serviceUnavailable || status == serviceUncertain)
        scheduleOwner();
    return statusValue(status);
}

JSC_DEFINE_HOST_FUNCTION(cancelHex, (JSC::JSGlobalObject* global, JSC::CallFrame* frame))
{
    return controlHex(global, frame, NativeMethod::cancel);
}

JSC_DEFINE_HOST_FUNCTION(acknowledgeHex, (JSC::JSGlobalObject* global, JSC::CallFrame* frame))
{
    return controlHex(global, frame, NativeMethod::acknowledge);
}

// Called only under an outer engine guard and the epoch's VM lock. The returned
// exception overload clears its caught exception; no unrooted CallData survives.
bool invoke(Epoch& epoch, JSC::JSObject* function, const JSC::MarkedArgumentBuffer& arguments, JSC::JSValue& result)
{
    auto data = JSC::getCallData(function);
    if (data.type == JSC::CallData::Type::None)
        return false;
    NakedPtr<JSC::Exception> exception;
    result = WebCore::JSExecState::call(epoch.global.get(), function, data,
        JSC::jsUndefined(), JSC::ArgList(arguments), exception);
    return !exception && !!result;
}

bool rootMethod(Epoch& epoch, ASCIILiteral name, JSC::Strong<JSC::JSObject>& root)
{
    if (!currentDocumentMatches(epoch))
        return false;
    auto& vm = epoch.vm.get();
    auto scope = DECLARE_CATCH_SCOPE(vm);
    auto value = epoch.controller->get(epoch.global.get(), JSC::Identifier::fromString(vm, name));
    if (scope.exception()) {
        scope.clearException();
        return false;
    }
    if (!value.isObject() || JSC::getCallData(value).type == JSC::CallData::Type::None || !currentDocumentMatches(epoch))
        return false;
    root.set(vm, value.getObject());
    return true;
}

bool initializeEpoch(Epoch& epoch, WebCore::LocalFrame& frame, WebCore::DOMWrapperWorld& world)
{
    auto& vm = epoch.vm.get();
    auto scope = DECLARE_CATCH_SCOPE(vm);
    auto* global = epoch.global.get();
    epoch.enqueueFunction.set(vm, JSC::JSFunction::create(vm, global, 2, "foundation.enqueueHex"_s,
        enqueueHex, JSC::ImplementationVisibility::Public));
    if (scope.exception()) { scope.clearException(); return false; }
    epoch.cancelFunction.set(vm, JSC::JSFunction::create(vm, global, 2, "foundation.cancelHex"_s,
        cancelHex, JSC::ImplementationVisibility::Public));
    if (scope.exception()) { scope.clearException(); return false; }
    epoch.acknowledgeFunction.set(vm, JSC::JSFunction::create(vm, global, 2, "foundation.acknowledgeHex"_s,
        acknowledgeHex, JSC::ImplementationVisibility::Public));
    if (scope.exception()) { scope.clearException(); return false; }

    auto bootstrap = frame.script().executeUserAgentScriptInWorld(world,
        String::fromUTF8(kBibFoundationServicesBootstrap), false);
    if (!bootstrap || !bootstrap.value().isObject() || !currentDocumentMatches(epoch))
        return false;
    JSC::Strong<JSC::JSObject> factory(vm, bootstrap.value().getObject());
    JSC::MarkedArgumentBuffer arguments;
    arguments.append(epoch.enqueueFunction.get());
    arguments.append(epoch.cancelFunction.get());
    arguments.append(epoch.acknowledgeFunction.get());
    arguments.append(JSC::jsString(vm, generationHex(epoch.generation)));
    auto& state = bridge();
    arguments.append(JSC::jsNumber(state.hooks.max_message_bytes));
    arguments.append(JSC::jsNumber(state.hooks.max_retained_calls));
    arguments.append(JSC::jsNumber(state.hooks.max_retained_bytes));
    if (scope.exception()) { scope.clearException(); return false; }
    if (arguments.hasOverflowed())
        return false;
    JSC::JSValue controller;
    if (!invoke(epoch, factory.get(), arguments, controller) || !controller.isObject() || !currentDocumentMatches(epoch))
        return false;
    epoch.controller.set(vm, controller.getObject());
    if (!rootMethod(epoch, "receiveHex"_s, epoch.receive)
        || !rootMethod(epoch, "acknowledge"_s, epoch.acknowledge)
        || !rootMethod(epoch, "dispose"_s, epoch.dispose))
        return false;
    auto publicAPI = epoch.controller->get(global, JSC::Identifier::fromString(vm, "publicApi"_s));
    if (scope.exception()) { scope.clearException(); return false; }
    if (!publicAPI.isObject() || !currentDocumentMatches(epoch))
        return false;
    // Configurable permits reinjection on a reused global; the closed native
    // function identities, not this public property, form the epoch boundary.
    global->putDirect(vm, JSC::Identifier::fromString(vm, "foundation"_s), publicAPI,
        static_cast<unsigned>(JSC::PropertyAttribute::ReadOnly | JSC::PropertyAttribute::DontEnum));
    if (scope.exception()) { scope.clearException(); return false; }
    if (!currentDocumentMatches(epoch))
        return false;
    epoch.ready = true;
    return true;
}

int disposeRetired(uint64_t generation)
{
    auto& state = bridge();
    if (state.disposing)
        return BIB_FOUNDATION_SERVICE_DELIVERY_REJECTED;
    uint32_t slot = 0;
    while (slot < state.hooks.max_retired_documents
        && (!state.retired[slot] || state.retired[slot]->generation != generation))
        ++slot;
    if (slot == state.hooks.max_retired_documents)
        return BIB_FOUNDATION_SERVICE_DELIVERY_STALE;
    state.disposing = true; // Also reserves this root slot during JS reactions.
    auto epoch = std::move(state.retired[slot]);
    --state.retiredCount;
    bool accepted = true;
    {
        JSC::JSLockHolder lock(epoch->vm.get());
        auto scope = DECLARE_CATCH_SCOPE(epoch->vm.get());
        if (epoch->dispose) {
            JSC::MarkedArgumentBuffer arguments;
            if (arguments.hasOverflowed())
                accepted = false;
            else {
                JSC::JSValue result;
                // A saved retired controller is deliberately independent of
                // active-document checks. Keeping Document alive does not
                // freeze a reused DOMWindow's context or revive stopped jobs.
                accepted = invoke(*epoch, epoch->dispose.get(), arguments, result) && result.isUndefined();
            }
        }
        if (scope.exception()) {
            scope.clearException();
            accepted = false;
        }
        // Even a disposal exception cannot pin unbounded retired native roots.
        // The returned failure remains visible; no effects are replayed.
        epoch->clearRoots();
        epoch.reset();
    }
    state.disposing = false;
    return accepted ? BIB_FOUNDATION_SERVICE_DELIVERY_ACCEPTED : BIB_FOUNDATION_SERVICE_DELIVERY_REJECTED;
}

} // namespace

FoundationServiceEngineCall::FoundationServiceEngineCall()
{
    // Compiled-in but uninstalled services must not change ordinary engine use.
    if (!installed())
        return;
    m_entered = false;
    if (!onOwner())
        return;
    auto& state = bridge();
    if (state.hostCallbackDepth || state.engineDepth == std::numeric_limits<uint32_t>::max())
        return;
    uint32_t status;
    {
        HostCallback callback;
        status = checkedStatus(state.hooks.enter_engine(state.hooks.context));
    }
    if (status != serviceOK)
        return;
    ++state.engineDepth;
    m_hostEntered = true;
    m_entered = true;
}

FoundationServiceEngineCall::~FoundationServiceEngineCall()
{
    finish();
}

void FoundationServiceEngineCall::finish()
{
    if (!m_hostEntered)
        return;
    m_hostEntered = false;
    auto& state = bridge();
    RELEASE_ASSERT(state.engineDepth);
    --state.engineDepth;
    // This guard must outlive all locks: their destructors can run microtasks.
    HostCallback callback;
    state.hooks.leave_engine(state.hooks.context);
}

void foundationServicesSelectApplicationDocument(WebCore::LocalFrame& frame)
{
    if (!onOwner() || !frame.isMainFrame() || !frame.document() || bridge().shuttingDown)
        return;
    FoundationServiceEngineCall call;
    if (!call)
        return;
    auto& state = bridge();
    if (state.active && state.selectedFrame.get() == &frame
        && state.selectedDocument.get() == frame.document() && state.active->ready)
        return;
    retireActive();
    state.selectedFrame = frame;
    state.selectedDocument = frame.document();
    state.selectionAttempted = false;
    foundationServicesDidClearWindowObject(frame, WebCore::mainThreadNormalWorldSingleton());
}

void foundationServicesDidClearWindowObject(WebCore::LocalFrame& frame, WebCore::DOMWrapperWorld& world)
{
    if (!onOwner() || &world != &WebCore::mainThreadNormalWorldSingleton())
        return;
    auto& state = bridge();
    if (state.shuttingDown || !frame.isMainFrame() || state.selectedFrame.get() != &frame
        || !state.selectedDocument || state.selectedDocument.get() != frame.document())
        return;
    if (state.active && state.active->ready) {
        if (currentDocumentMatches(*state.active))
            return;
        retireActive();
        state.selectionAttempted = false;
    }
    if (state.selectionAttempted)
        return;
    FoundationServiceEngineCall call;
    if (!call)
        return;
    state.selectionAttempted = true; // globalObject() may recursively issue this hook.
    if (state.retiredCount + static_cast<uint32_t>(state.disposing) >= state.hooks.max_retired_documents)
        return; // Preserve room to retire the prospective active epoch.
    auto* global = frame.script().globalObject(world);
    if (!global || state.selectedDocument.get() != frame.document()
        || global->scriptExecutionContext() != frame.document())
        return;
    JSC::JSLockHolder lock(global->vm());
    uint64_t generation;
    {
        HostCallback callback;
        generation = state.hooks.begin_document(state.hooks.context);
    }
    if (!generation)
        return;
    for (uint32_t slot = 0; slot < state.hooks.max_retired_documents; ++slot) {
        if (state.retired[slot] && state.retired[slot]->generation == generation) {
            closeHost(generation);
            return;
        }
    }
    auto epoch = std::unique_ptr<Epoch>(new (std::nothrow) Epoch(global->vm(), *frame.document(), generation));
    if (!epoch) {
        closeHost(generation);
        return;
    }
    epoch->global.set(global->vm(), global);
    state.active = std::move(epoch);
    auto* initializing = state.active.get();
    const bool initialized = initializeEpoch(*initializing, frame, world);
    // A checkpoint may retire this epoch and install a successor. Never close
    // that successor or dereference active as though it were the original.
    if (state.active.get() == initializing && (!initialized || !currentDocumentMatches(*initializing)))
        retireActive();
}

void foundationServicesWillChangeMainDocument(WebCore::LocalFrame& frame)
{
    if (!onOwner() || bridge().selectedFrame.get() != &frame)
        return;
    // setDocument can call this for nullptr and again for the successor. Neither
    // callback creates authority for that successor, and neither executes JS.
    retireActive();
    bridge().selectedDocument = nullptr;
    bridge().selectionAttempted = true;
}

void foundationServicesDidExplicitOpen(WebCore::LocalFrame& frame)
{
    if (!onOwner() || bridge().shuttingDown || bridge().selectedFrame.get() != &frame
        || !frame.document() || bridge().selectedDocument.get() != frame.document())
        return;
    // Explicit open is a new epoch of the selected document despite preserving
    // its Document and global identities. Loader mutation only retires here;
    // injection below is at the post-implicitOpen callback, before author data.
    retireActive();
    bridge().selectionAttempted = false;
    foundationServicesDidClearWindowObject(frame, WebCore::mainThreadNormalWorldSingleton());
}

void foundationServicesWillDestroyEngine()
{
    if (!onOwner())
        return;
    auto& state = bridge();
    state.shuttingDown = true;
    retireActive();
    state.selectedDocument = nullptr;
    state.selectedFrame = nullptr;
    state.selectionAttempted = true;
}

uint64_t foundationServicesReadyGeneration(WebCore::LocalFrame& frame, const WebCore::Document& document)
{
    if (!onOwner() || !installed() || bridge().shuttingDown || !frame.isMainFrame()
        || frame.document() != &document || bridge().selectedFrame.get() != &frame
        || bridge().selectedDocument.get() != &document || !bridge().active
        || !bridge().active->ready || !currentDocumentMatches(*bridge().active))
        return 0;
    return bridge().active->generation;
}

uint64_t foundationServicesSelectApplicationDocumentChecked(WebCore::LocalFrame& frame, WebCore::Document& document)
{
    if (frame.document() != &document)
        return 0;
    foundationServicesSelectApplicationDocument(frame);
    // The selector's locks and EngineCall have already gone out of scope.
    // A destructor checkpoint may have changed document/global/generation.
    return foundationServicesReadyGeneration(frame, document);
}

uint64_t foundationServicesResetApplicationDocumentChecked(WebCore::LocalFrame& frame, WebCore::Document& document)
{
    if (frame.document() != &document)
        return 0;
    const auto previous = foundationServicesReadyGeneration(frame, document);
    foundationServicesDidExplicitOpen(frame);
    const auto next = foundationServicesReadyGeneration(frame, document);
    return next && next != previous ? next : 0;
}

void foundationServicesRetireCompositionDocument(WebCore::LocalFrame& frame, const WebCore::Document& document, uint64_t expectedGeneration)
{
    if (!onOwner() || bridge().selectedFrame.get() != &frame || bridge().selectedDocument.get() != &document)
        return;
    if (expectedGeneration && (!bridge().active || bridge().active->generation != expectedGeneration))
        return;
    retireActive();
    bridge().selectedDocument = nullptr;
    bridge().selectionAttempted = true;
}

} // namespace BIB

extern "C" int bib_foundation_services_install(const BibFoundationServiceHostV1* hooks)
{
    if (!hooks || BIB::installed() || hooks->size < sizeof(BibFoundationServiceHostV1)
        || hooks->version != BIB_FOUNDATION_SERVICE_HOST_VERSION
        || hooks->max_message_bytes < 384 || hooks->max_message_bytes > BIB_FOUNDATION_SERVICE_MAX_MESSAGE
        || !hooks->max_retained_calls || hooks->max_retained_bytes < 64
        || !hooks->max_retired_documents || hooks->max_retired_documents > BIB::maximumRetiredDocuments
        || !hooks->enter_engine || !hooks->leave_engine || !hooks->begin_document
        || !hooks->close_document || !hooks->submit || !hooks->cancel || !hooks->acknowledge || !hooks->schedule_owner)
        return -1;
    auto retired = std::unique_ptr<std::unique_ptr<BIB::Epoch>[]>(new (std::nothrow) std::unique_ptr<BIB::Epoch>[hooks->max_retired_documents]);
    auto decode = std::unique_ptr<uint8_t[]>(new (std::nothrow) uint8_t[hooks->max_message_bytes]);
    auto unconfirmed = std::unique_ptr<uint8_t[]>(new (std::nothrow) uint8_t[hooks->max_message_bytes]);
    auto hex = std::unique_ptr<Latin1Character[]>(new (std::nothrow) Latin1Character[hooks->max_message_bytes * 2]);
    if (!retired || !decode || !unconfirmed || !hex)
        return -1;
    auto& state = BIB::bridge();
    state.hooks = *hooks;
    state.owner = std::this_thread::get_id();
    state.retired = std::move(retired);
    state.decodeBytes = std::move(decode);
    state.unconfirmedBytes = std::move(unconfirmed);
    state.hexCharacters = std::move(hex);
    state.installed.store(true, std::memory_order_release);
    return 0;
}

extern "C" int bib_foundation_services_deliver(uint64_t generation, const uint8_t* completion, uint32_t length)
{
    if (!BIB::onOwner())
        return BIB_FOUNDATION_SERVICE_DELIVERY_WRONG_THREAD;
    if (BIB::bridge().engineDepth)
        return BIB_FOUNDATION_SERVICE_DELIVERY_REJECTED;
    BIB::FoundationServiceEngineCall call;
    if (!call)
        return BIB_FOUNDATION_SERVICE_DELIVERY_REJECTED;
    auto* epoch = BIB::activeEpoch(generation);
    if (!epoch)
        return BIB_FOUNDATION_SERVICE_DELIVERY_STALE;
    auto& state = BIB::bridge();
    if (!completion || length < 64 || length > state.hooks.max_message_bytes)
        return BIB_FOUNDATION_SERVICE_DELIVERY_REJECTED;
    if (epoch->unconfirmedDelivery && (epoch->unconfirmedLength != length
        || !std::equal(completion, completion + length, state.unconfirmedBytes.get())))
        return BIB_FOUNDATION_SERVICE_DELIVERY_REJECTED;
    std::copy(completion, completion + length, state.unconfirmedBytes.get());
    epoch->unconfirmedDelivery = true;
    epoch->unconfirmedLength = length;
    constexpr char digits[] = "0123456789abcdef";
    for (uint32_t index = 0; index < length; ++index) {
        state.hexCharacters[index * 2] = digits[completion[index] >> 4];
        state.hexCharacters[index * 2 + 1] = digits[completion[index] & 15];
    }
    bool accepted = false;
    {
        JSC::JSLockHolder lock(epoch->vm.get());
        auto scope = DECLARE_CATCH_SCOPE(epoch->vm.get());
        JSC::MarkedArgumentBuffer arguments;
        arguments.append(JSC::jsString(epoch->vm.get(), String { std::span<const Latin1Character>(state.hexCharacters.get(), length * 2) }));
        const bool overflowed = arguments.hasOverflowed();
        if (!scope.exception() && !overflowed) {
            JSC::JSValue result;
            accepted = BIB::invoke(*epoch, epoch->receive.get(), arguments, result)
                && result.isBoolean() && result.asBoolean();
        }
        if (scope.exception()) {
            scope.clearException();
            accepted = false;
        }
    }
    // The final API-lock release can run additional jobs and replace the
    // document. Retired roots stay alive until the complete engine turn exits.
    if (epoch->closed || BIB::activeEpoch(generation) != epoch)
        return BIB_FOUNDATION_SERVICE_DELIVERY_STALE;
    if (!accepted)
        return BIB_FOUNDATION_SERVICE_DELIVERY_REJECTED;
    epoch->unconfirmedDelivery = false;
    epoch->unconfirmedLength = 0;
    return BIB_FOUNDATION_SERVICE_DELIVERY_ACCEPTED;
}

extern "C" uint32_t bib_foundation_services_collect_ack(uint64_t generation)
{
    if (!BIB::onOwner())
        return BIB::serviceUnavailable;
    if (BIB::bridge().engineDepth)
        return BIB::serviceUnavailable;
    BIB::FoundationServiceEngineCall call;
    if (!call)
        return BIB::serviceUnavailable;
    auto* epoch = BIB::activeEpoch(generation);
    if (!epoch)
        return BIB::serviceClosed;
    if (epoch->unconfirmedDelivery)
        return BIB::serviceConflict;
    uint32_t outcome = BIB::serviceUncertain;
    {
        JSC::JSLockHolder lock(epoch->vm.get());
        auto scope = DECLARE_CATCH_SCOPE(epoch->vm.get());
        JSC::MarkedArgumentBuffer arguments;
        if (!arguments.hasOverflowed()) {
            JSC::JSValue result;
            if (BIB::invoke(*epoch, epoch->acknowledge.get(), arguments, result) && result.isNumber()) {
                const double status = result.asNumber();
                if (std::isfinite(status) && status == std::trunc(status) && status >= 0 && status <= BIB::serviceUncertain)
                    outcome = static_cast<uint32_t>(status);
            }
        }
        if (scope.exception()) {
            scope.clearException();
            outcome = BIB::serviceUncertain;
        }
    }
    if (epoch->closed || BIB::activeEpoch(generation) != epoch)
        return BIB::serviceClosed;
    return outcome;
}

extern "C" int bib_foundation_services_dispose_retired(uint64_t generation)
{
    if (!BIB::onOwner())
        return BIB_FOUNDATION_SERVICE_DELIVERY_WRONG_THREAD;
    if (BIB::bridge().engineDepth)
        return BIB_FOUNDATION_SERVICE_DELIVERY_REJECTED;
    BIB::FoundationServiceEngineCall call;
    if (!call)
        return BIB_FOUNDATION_SERVICE_DELIVERY_REJECTED;
    if (!generation)
        return BIB_FOUNDATION_SERVICE_DELIVERY_STALE;
    auto& state = BIB::bridge();
    if (state.active && state.active->generation == generation) {
        // Explicit owner terminal-close decision, also used after uncertain
        // admission/delivery. Retire the current document without granting a
        // successor or changing the persistent ModuleProviders owner.
        BIB::retireActive();
        state.selectedDocument = nullptr;
        state.selectionAttempted = true;
    }
    return BIB::disposeRetired(generation);
}

#endif // BIB_FOUNDATION_SERVICES
