// SPDX-License-Identifier: CC0-1.0
// PRIVATE COMBINED SOURCE CANDIDATE. No WebCore compilation/execution claim.
#include "config.h"
#include "BibAppResources.h"
#include "BibFoundationServiceBridge.h"
#include "AppDocumentLifecycle.hpp"
#if BIB_ENGINE_PROVIDER_NEUTRAL
#include "BibEngineProviderLifecycleHooks.h"
#endif
#include "AppResourceQueue.hpp"
#include "resource_url.hpp"
#include "BackForwardCache.h"
#include "CachedResource.h"
#include "Document.h"
#include "DocumentLoader.h"
#include "DOMWrapperWorld.h"
#include "FrameLoadRequest.h"
#include "FrameLoader.h"
#include "HTTPHeaderNames.h"
#include "LegacySchemeRegistry.h"
#include "LocalFrame.h"
#include "LocalFrameInlines.h"
#include "NetworkLoadMetrics.h"
#include "ResourceError.h"
#include "ResourceLoader.h"
#include "ResourceRequest.h"
#include "ResourceResponse.h"
#include "SharedBuffer.h"
#include "SubresourceLoader.h"
#include <map>
#include <memory>
#include <thread>
#include <wtf/NeverDestroyed.h>
#include <wtf/RunLoop.h>
#include <wtf/text/CString.h>
#include <wtf/text/WTFString.h>

namespace BIB {
using namespace WebCore;
using namespace foundation::appended::candidate;
static std::uintptr_t physical(const void* p) { return reinterpret_cast<std::uintptr_t>(p); }
static ResourceError appError(const URL& url, const String& message)
{ return ResourceError("FoundationAppResource"_s, 1, url, message, ResourceError::Type::Cancellation); }
static ResourceResponse appResponse(const URL& url, const AppResourceReply& reply)
{
    ResourceResponse response(URL { url }, String::fromUTF8(reply.mime.c_str()), reply.content_length, String());
    response.setHTTPStatusCode(reply.status);
    response.setHTTPHeaderField(HTTPHeaderName::ContentType, String::fromUTF8(reply.mime.c_str()));
    response.setHTTPHeaderField(HTTPHeaderName::ContentLength, String::number(reply.content_length));
    response.setHTTPHeaderField(HTTPHeaderName::XContentTypeOptions, "nosniff"_s);
    return response;
}

class AppLoad;
class AppResourceContext final {
public:
    BibAppResourceBundleHostV1 bundle { };
    BibAppResourceHostV1 hooks { };
    std::unique_ptr<AppResourceQueue> queue;
    WeakPtr<LocalFrame> frame;
    RefPtr<DocumentLoader> loader;
    RefPtr<Document> document;
    uint64_t token { 0 };
    bool closed { false }, explicitOpen { false }, isInitial { false }, initialEntryConfirmed { false };
    ~AppResourceContext()
    {
        // All host spans were copied/released synchronously. Cache Providers
        // retain only immutable replies + the shared engine budget, not this.
        queue = nullptr;
        if (hooks.document_epoch) bundle.retire_epoch(bundle.context, hooks.document_epoch);
    }
};
struct AppState {
    BibAppResourceBundleHostV1 bundle { };
    std::shared_ptr<AppResourceBudget> budget;
    std::unique_ptr<AppDocumentLifecycle> lifecycle;
    std::shared_ptr<AppResourceContext> active, pending;
    std::weak_ptr<AppResourceContext> initialContext;
    uint64_t initialToken { 0 };
    std::map<ResourceLoader*, std::shared_ptr<AppLoad>> loads;
    WeakPtr<LocalFrame> selectedFrame;
    std::string entry, authority;
    std::thread::id owner;
    bool strict { false }, started { false }, initialIntent { false }, closed { false };
    bool initialSelected { false }, initialFailed { false };
};
static AppState& appState() { static NeverDestroyed<AppState> state; return state; }
static bool onOwner() { return appState().strict && std::this_thread::get_id() == appState().owner; }
static bool pendingMatches(const std::shared_ptr<AppResourceContext>& context)
{
    auto& state = appState();
    const auto* pending = state.lifecycle ? state.lifecycle->pending() : nullptr;
    return context && !context->closed && state.pending == context && pending
        && context->hooks.document_epoch && pending->resource_epoch
        && pending->token == context->token && pending->resource_epoch == context->hooks.document_epoch;
}
static bool exactActive(LocalFrame& frame, const Document& document)
{
    auto& state = appState();
    auto context = state.active;
    if (!onOwner() || state.closed || !context || context->closed || state.selectedFrame.get() != &frame
        || frame.document() != &document || context->frame.get() != &frame || context->document.get() != &document
        || !context->loader || frame.loader().documentLoader() != context->loader.get()) return false;
    const auto generation = foundationServicesReadyGeneration(frame, document);
    return state.lifecycle->active_matches(physical(&frame), physical(context->loader.get()), physical(&document), generation);
}
static bool exactUnselectedInitial(const std::shared_ptr<AppResourceContext>& context)
{
    auto& state = appState();
    return !state.initialSelected && context && context->isInitial
        && context->token == state.initialToken && state.initialContext.lock() == context
        && pendingMatches(context);
}
std::int32_t bibProviderInitialLoadStatus() noexcept
{
    if (!onOwner()) return -1; // Private owner-only query; fail closed on misuse.
    const auto& state = appState();
    if (state.initialSelected) return 1; // A later navigation is a normal load.
    return state.initialFailed || state.closed ? -1 : 0;
}

bool bibProviderInitialEntryConfirmed() noexcept
{
    // Exact current-context entry proof for response/selection diagnostics.
    // Initialization does not require this asynchronous seam to be reached.
    // InitialLoadStatus separately preserves successful initial selection.
    if (!onOwner()) return false;
    auto& state = appState();
    if (state.closed || !state.started || !state.initialToken || state.initialFailed) return false;
    try {
        auto context = state.initialContext.lock();
        RefPtr frame = state.selectedFrame.get();
        RefPtr loader = context ? context->loader : nullptr;
        if (!context || context->closed || !context->isInitial || !context->initialEntryConfirmed
            || context->token != state.initialToken || !context->hooks.document_epoch
            || !frame || context->frame.get() != frame.get() || !loader
            || !loader->mainDocumentError().isNull() || loader->isStopping()) return false;
        RefPtr provisional = frame->loader().provisionalDocumentLoader();
        if (provisional && provisional.get() != loader.get()) return false;
        if (pendingMatches(context))
            return provisional.get() == loader.get()
                && frame->loader().activeDocumentLoader() == loader.get();
        const auto identity = state.lifecycle->active_identity();
        // An old active initial document can coexist with a later navigation.
        // Such a successor must never inherit or preserve startup confirmation.
        return !state.pending && !state.lifecycle->pending_identity()
            && state.active == context && identity && identity->token == state.initialToken
            && frame->document() && context->document.get() == frame->document()
            && exactActive(*frame, *frame->document());
    } catch (...) { return false; }
}

static bool canonicalURL(const URL& url)
{
    try {
        const auto text = url.string().utf8();
        return !!normalize_app_resource_url({text.data(), text.length()}, appState().authority);
    } catch (...) { return false; }
}
static void retireContext(const std::shared_ptr<AppResourceContext>&);
static void failPending(const std::shared_ptr<AppResourceContext>&, const String&);

class AppLoad final : public AppResourceSink, public std::enable_shared_from_this<AppLoad> {
public:
    AppLoad(ResourceLoader& loader, std::shared_ptr<AppResourceContext> context, uint64_t ticket, bool initialEntryPrepared)
        : m_loader(&loader), m_context(std::move(context)), m_ticket(ticket), m_initialEntryPrepared(initialEntryPrepared), m_defers(loader.defersLoading()) { }
    const std::shared_ptr<AppResourceContext>& context() const { return m_context; }
    void scheduleStart()
    {
        if (m_scheduled || !m_loader) return;
        m_scheduled = true;
        WTF::RunLoop::mainSingleton().dispatch([weak = weak_from_this()] {
            auto self = weak.lock();
            if (!self) return;
            self->m_scheduled = false;
            if (!self->m_loader || self->m_defers) return;
            if (self->m_context->closed || self->m_loader->reachedTerminalState()) { self->abort(); return; }
            if (!self->m_ticket) { self->abort(); return; }
            if (self->m_bodyReady) self->continueBody();
            else if (!self->m_headersSent) self->m_context->queue->begin(self->m_ticket, *self);
        });
    }
    void setDefers(bool value) { m_defers = value; if (!value) scheduleStart(); }
    void cancel()
    {
        if (m_ticket) m_context->queue->cancel(m_ticket);
        m_ticket = 0;
        m_loader = nullptr;
    }
    void abort()
    {
        RefPtr loader = m_loader;
        cancel();
        if (loader) appState().loads.erase(loader.get());
        if (loader && !loader->reachedTerminalState()) loader->didFail(appError(loader->request().url(), "App resource context closed or unavailable"_s));
        if (pendingMatches(m_context)) failPending(m_context,"App main resource aborted before selection"_s);
    }
    void response(uint64_t ticket, const AppResourceReply& reply) final
    {
        if (!live()) return;
        RefPtr loader = m_loader;
        auto& state = appState();
        if (!state.initialSelected) {
            const bool currentInitial = exactUnselectedInitial(m_context);
            bool proven = false;
            try {
                RefPtr frame = m_context->frame.get();
                const auto method = loader->request().httpMethod().utf8();
                const auto url = loader->request().url().string().utf8();
                // Scheduling precedes CachedResource's loader assignment. This
                // dispatched response runs after completion installs that exact
                // loader, before didReceiveResponse can invoke response policy.
                proven = currentInitial && m_initialEntryPrepared && ticket && ticket == m_ticket
                    && !state.initialFailed && !state.closed && frame && state.selectedFrame.get() == frame.get()
                    && m_context->loader && loader->documentLoader() == m_context->loader.get()
                    && m_context->loader->mainResourceLoader() == loader.get()
                    && frame->loader().provisionalDocumentLoader() == m_context->loader.get()
                    && frame->loader().activeDocumentLoader() == m_context->loader.get()
                    && std::string_view(method.data(), method.length()) == "GET"
                    && std::string_view(url.data(), url.length()) == state.entry
                    && m_context->loader->request().httpMethod() == "GET"_s
                    && m_context->loader->request().url() == loader->request().url()
                    && reply.status == 200 && reply.mime == "text/html";
            } catch (...) { }
            if (!proven) {
                if (currentInitial) failPending(m_context, "Initial app response loader or copied entry rejected"_s);
                else abort(); // Only this stale captured load; preserve any successor.
                return;
            }
            m_context->initialEntryConfirmed = true;
        }
        m_headersSent = true;
        loader->didReceiveResponse(appResponse(loader->request().url(), reply), [weak = weak_from_this()] {
            if (auto self = weak.lock()) {
                self->m_bodyReady = true;
                if (!self->m_defers) self->continueBody();
            }
        });
    }
    void data(uint64_t ticket, std::span<const uint8_t>) final
    {
        if (!live()) return;
        auto reply = m_context->queue->retain_reply(ticket);
        if (!reply) return;
        const auto length = reply->body.size();
        auto buffer = SharedBuffer::create(DataSegment::Provider { [reply = std::move(reply)]() -> std::span<const uint8_t> { return reply->body; } });
        m_loader->didReceiveBuffer(buffer.get(), length, DataPayloadBytes);
    }
    void finished(uint64_t) final
    {
        RefPtr loader = m_loader;
        m_ticket = 0; m_loader = nullptr;
        if (loader) appState().loads.erase(loader.get());
        if (loader && !loader->reachedTerminalState()) loader->didFinishLoading({ });
    }
private:
    bool live()
    {
        if (!m_loader) return false;
        if (m_context->closed || m_loader->reachedTerminalState()) { abort(); return false; }
        return true;
    }
    void continueBody()
    {
        if (!live()) return;
        m_bodyReady = false;
        m_context->queue->continue_response(m_ticket, *this);
    }
    RefPtr<ResourceLoader> m_loader;
    const std::shared_ptr<AppResourceContext> m_context; // Never re-resolve a global epoch.
    uint64_t m_ticket { 0 };
    const bool m_initialEntryPrepared;
    bool m_defers { false }, m_scheduled { false }, m_headersSent { false }, m_bodyReady { false };
};

static void retireContext(const std::shared_ptr<AppResourceContext>& context)
{
    if (!context || context->closed) return;
    context->closed = true;
    if (context->queue) context->queue->close(context->hooks.document_epoch);
    // Extract nodes before callbacks; abort/didFail may reenter remove/close.
    std::map<ResourceLoader*, std::shared_ptr<AppLoad>> retired;
    auto& loads = appState().loads;
    for (auto it = loads.begin(); it != loads.end();) {
        if (it->second->context() == context) retired.insert(loads.extract(it++));
        else ++it;
    }
    for (auto& [loader, load] : retired) load->abort();
    context->document = nullptr;
    context->loader = nullptr;
}
static void discardPending()
{
    auto& state = appState();
    if (exactUnselectedInitial(state.pending)) state.initialFailed = true;
    auto previous = std::move(state.pending);
    if (!previous) return;
    (void)state.lifecycle->discard_pending(previous->token);
    retireContext(previous);
}
static void failPending(const std::shared_ptr<AppResourceContext>& context, const String& message)
{
    auto& state = appState();
    // A reentrant successor can occupy pending with the same URL or even same
    // physical Document. Only the captured one-use token authorizes cleanup.
    if (!pendingMatches(context)) {
        // Stale selection cleanup may still own its captured host epoch. Close
        // only that context; never cancel a replacement loader or native lease.
        if (context) {
            (void)state.lifecycle->discard_pending(context->token);
            retireContext(context);
        }
        return;
    }
    if (exactUnselectedInitial(context)) state.initialFailed = true;
    RefPtr loader = context->loader;
    RefPtr document = context->document;
    RefPtr frame = context->frame.get();
    (void)state.lifecycle->discard_pending(context->token);
    state.pending = nullptr;
    if (frame && document) foundationServicesRetireCompositionDocument(*frame, *document, 0);
    retireContext(context);
    if (loader && loader->mainDocumentError().isNull()) loader->cancelMainResourceLoad(appError(loader->request().url(), message));
}
static std::shared_ptr<AppResourceContext> newContext(LocalFrame& frame, DocumentLoader& loader, const URL& url, bool explicitOpen)
{
    auto& state = appState();
    const bool initialAttempt = state.initialIntent && !state.active && !explicitOpen && !state.initialToken;
    BibAppResourceHostV1 hooks { };
    std::shared_ptr<AppResourceContext> context;
    uint64_t token = 0;
    auto fail = [&]() -> std::shared_ptr<AppResourceContext> {
        // The reserved sequence stays consumed, including admission refusal or
        // throw. Exact-token cleanup cannot discard a reentrant replacement.
        const auto pending = state.lifecycle->pending_identity();
        if (initialAttempt && !state.initialSelected
            && (!state.initialToken || state.initialToken == token)
            && (!pending || (token && pending->token == token))) state.initialFailed = true;
        if (token) (void)state.lifecycle->discard_pending(token);
        if (context) {
            context->hooks = hooks; // Adopt even a partial admitted host epoch.
            retireContext(context); // Queue may not have been allocated yet.
        }
        return {};
    };
    try {
        // Finish URL/context allocation before reserving canonical metadata or
        // entering the external host. The context owns every admitted nonzero
        // epoch thereafter, including attachment and queue-allocation failures.
        const auto expected = url.string().utf8();
        context = std::make_shared<AppResourceContext>();
        context->bundle = state.bundle;
        context->frame = frame;
        context->loader = &loader;
        context->explicitOpen = explicitOpen;
        context->isInitial = initialAttempt;
        token = state.lifecycle->reserve_pending(physical(&frame), physical(&loader),
            physical(frame.document()), {expected.data(), expected.length()});
        if (!token) return fail();
        context->token = token;
#if BIB_ENGINE_PROVIDER_NEUTRAL
        if (!bibProviderSetProspectiveDocument(token)) return fail();
#endif
        if (context->bundle.begin_epoch(context->bundle.context, &hooks)) return fail();
        context->hooks = hooks;
        if (state.closed || !onOwner()
            || hooks.max_response_bytes != context->bundle.max_response_bytes || hooks.max_inflight != context->bundle.max_inflight
            || hooks.max_retained_bytes != context->bundle.max_retained_bytes
            || !state.lifecycle->attach_resource_epoch(token, hooks.document_epoch)) return fail();
        context->queue = std::make_unique<AppResourceQueue>(hooks, state.budget);
        if (context->isInitial) {
            // The canonical sequence is published only after exact attachment;
            // failed admission cannot manufacture initial-entry proof.
            state.initialToken = token;
            state.initialContext = context;
        }
        return context;
    } catch (...) {
        return fail();
    }
}

static void documentCreated(std::weak_ptr<AppResourceContext> weak, Document* document)
{
    auto context = weak.lock();
    if (!pendingMatches(context)) return;
    auto& state = appState();
    RefPtr frame = context->frame.get();
    RefPtr loader = context->loader;
    if (!frame || !loader || !document || frame->document() != document || frame->loader().documentLoader() != loader.get()
        || !loader->mainDocumentError().isNull() || loader->isStopping()) { failPending(context, "App document creation canceled"_s); return; }
    if (!state.initialSelected && (!exactUnselectedInitial(context)
        || state.initialFailed || !context->initialEntryConfirmed)) {
        failPending(context, "Initial app document has no confirmed copied entry"_s); return;
    }
    RefPtr protectedDocument = document; // Selection/checkpoints may detach its last engine owner.
    context->document = document;
    if (!state.lifecycle->begin_selection(context->token, physical(frame.get()), physical(loader.get()), physical(document))) {
        failPending(context, "App document selection was already consumed"_s); return;
    }
#if BIB_ENGINE_PROVIDER_NEUTRAL
    if (!bibProviderSetProspectiveDocument(context->token) || !pendingMatches(context)) {
        failPending(context, "App prospective service identity changed"_s); return;
    }
#endif
    uint64_t generation = 0;
    try { generation = foundationServicesSelectApplicationDocumentChecked(*frame, *protectedDocument); }
    catch (...) { failPending(context, "App service selection failed after execution"_s); return; }
    // Selector destructors may run checkpoints. Re-read both metadata and live
    // engine ownership; no stale ready state may authorize an old writer.
    if (!pendingMatches(context) || frame->document() != document || frame->loader().documentLoader() != loader.get()
        || loader->isStopping() || !loader->mainDocumentError().isNull() || !generation
        || generation != foundationServicesReadyGeneration(*frame, *document)
        || !state.lifecycle->activate(context->token, physical(frame.get()), physical(loader.get()), physical(document), generation)) {
        // Checked selection observes readiness after checkpoints; a returned
        // generation may already belong to a reentrant successor. Stale cleanup
        // therefore retires only this captured resource context, never that
        // unproven native generation or a replacement at the same address.
        failPending(context, "App composition did not become ready before author bytes"_s); return;
    }
    state.active = context;
    state.pending = nullptr;
    if (context->isInitial && context->token == state.initialToken && context->initialEntryConfirmed)
        state.initialSelected = true;
    state.initialIntent = false;
}

bool appResourcesStrict() { return appState().strict; }
void appResourcesInitializeScheme()
{
    if (!appResourcesStrict()) return;
    LegacySchemeRegistry::registerURLSchemeAsSecure("app"_s);
    LegacySchemeRegistry::registerURLSchemeAsCORSEnabled("app"_s);
    LegacySchemeRegistry::registerURLSchemeAsHandledBySchemeHandler("app"_s);
    LegacySchemeRegistry::setDomainRelaxationForbiddenForURLScheme(true, "app"_s);
}
bool appResourcesStartApplicationLoad(LocalFrame& frame)
{
    auto& state = appState();
    if (!onOwner() || state.closed || state.started || !frame.isMainFrame() || !frame.document()) return false;
    state.started = true; state.initialIntent = true; state.selectedFrame = frame;
    FrameLoadRequest request { frame, ResourceRequest { URL { String::fromUTF8(state.entry.c_str()) } } };
    frame.loader().load(WTF::move(request));
    return !state.closed;
}
bool appResourcesNavigationAllowed(LocalFrame& frame, const ResourceRequest& request)
{
    auto& state = appState();
    if (!appResourcesStrict()) return true;
    if (!onOwner() || state.closed || state.selectedFrame.get() != &frame || !frame.isMainFrame()) return false;
    if (request.httpMethod() != "GET"_s || !canonicalURL(request.url())) return false;
    if (pendingMatches(state.pending) && state.pending->loader
        && frame.loader().provisionalDocumentLoader() == state.pending->loader.get()
        && request.url() == state.pending->loader->request().url()) return true;
    if (state.initialIntent && !state.active) return request.url().string() == String::fromUTF8(state.entry.c_str());
    return frame.document() && exactActive(frame, *frame.document());
}
AppResourceBinding appResourcesBind(LocalFrame& frame, bool mainResource, const ResourceRequest& request)
{
    auto& state = appState();
    if (!onOwner() || state.closed || state.selectedFrame.get() != &frame) return {};
    if (!mainResource) {
        // Capture current Document BEFORE asynchronous SubresourceLoader::create.
        // ResourceLoader::documentLoader alone may already point at provisional
        // while this old document is still executing during navigation.
        return frame.document() && exactActive(frame, *frame.document()) ? state.active : nullptr;
    }
    if (!appResourcesNavigationAllowed(frame, request)) return {};
    RefPtr loader = frame.loader().provisionalDocumentLoader();
    if (!loader || frame.loader().activeDocumentLoader() != loader.get() || loader->request().url() != request.url()) return {};
    if (state.pending && state.pending->loader == loader && !state.pending->closed) return state.pending;
    discardPending();
    auto context = newContext(frame, *loader, request.url(), false);
    // Admission/retirement callbacks may install a successor. A failed local
    // attempt must not overwrite that independently captured pending context.
    if (!context) return {};
    state.pending = context;
    state.initialIntent = false; // One exact initial loader.
    return context;
}
bool appResourcesCheckResponse(LocalFrame& frame, const ResourceResponse& response, const ResourceRequest& request)
{
    if (!appResourcesStrict()) return true;
    auto& state = appState();
    auto context = state.pending;
    RefPtr loader = context ? context->loader : nullptr;
    // A late policy callback from an older loader must not retire the new
    // pending record, even if URLs match. WebCore passes its stored m_response
    // by reference here; require ownership before any destructive failure.
    if (!loader || &loader->response() != &response) return false;
    if (!onOwner() || state.closed || !pendingMatches(context) || !loader || context->explicitOpen
        || context->frame.get() != &frame || frame.loader().provisionalDocumentLoader() != loader.get()
        || frame.loader().activeDocumentLoader() != loader.get() || loader->request().url() != request.url()
        || loader->response().url() != response.url() || request.url() != response.url()
        || request.httpMethod() != "GET"_s || !canonicalURL(request.url()) || response.httpStatusCode() != 200
        || response.mimeType() != "text/html"_s || loader->isCommitted() || response.isMultipart()
        || (!state.initialSelected && (!exactUnselectedInitial(context)
            || state.initialFailed || !context->initialEntryConfirmed))
        || !state.lifecycle->register_callback(context->token, physical(loader.get()))) {
        if (context) failPending(context, "App main response or loader identity rejected"_s);
        return false;
    }
    try { loader->whenDocumentIsCreated([weak = std::weak_ptr<AppResourceContext>(context)](Document* document) { documentCreated(weak, document); }); }
    catch (...) { failPending(context, "App document callback registration failed"_s); return false; }
    return pendingMatches(context);
}
void appResourcesSchedule(ResourceLoader& loader, AppResourceBinding context)
{
    appResourcesRemove(&loader);
    uint64_t ticket = 0;
    try {
        if (!context || context->closed) {
            loader.didFail(appError(loader.request().url(), "Resource has no selected application context"_s)); return;
        }
        const auto method = loader.request().httpMethod().utf8();
        const auto url = loader.request().url().string().utf8();
        ticket = context->queue->prepare(context->hooks.document_epoch, {method.data(),method.length()}, {url.data(),url.length()});
        auto& state = appState();
        bool initialReply = false;
        // Inspect the already-copied held reply. This takes only a temporary
        // shared reference: no second resolve, lease, body copy or resource load.
        if (exactUnselectedInitial(context)) {
            auto reply = context->queue->retain_reply(ticket);
            if (!ticket || !reply || reply->status != 200 || reply->mime != "text/html") {
                failPending(context, "Initial app entry resource was rejected"_s); return;
            }
            initialReply = onOwner() && !state.closed && !state.initialFailed
                && context->frame.get() == state.selectedFrame.get()
                && context->loader && loader.documentLoader() == context->loader.get()
                && std::string_view(method.data(), method.length()) == "GET"
                && std::string_view(url.data(), url.length()) == state.entry
                && context->loader->request().httpMethod() == "GET"_s
                && context->loader->request().url() == loader.request().url();
        }
        // Only a prepared candidate is captured here. The main-resource loader
        // does not exist in CachedResource until creation's completion callback.
        auto load = std::make_shared<AppLoad>(loader, context, ticket, initialReply);
        state.loads.insert_or_assign(&loader, load);
        load->scheduleStart();
    } catch (...) {
        if (ticket && context) context->queue->cancel(ticket);
        appResourcesRemove(&loader);
        if (exactUnselectedInitial(context)) {
            failPending(context, "Initial app resource scheduling failed"_s); return;
        }
        if (!loader.reachedTerminalState()) loader.didFail(appError(loader.request().url(), "App resource scheduling failed"_s));
    }
}
bool appResourcesRemove(ResourceLoader* loader)
{
    auto& loads = appState().loads;
    const auto it = loads.find(loader);
    if (it == loads.end()) return false;
    auto load = std::move(it->second); loads.erase(it); load->cancel(); return true;
}
void appResourcesCreationFailed(AppResourceBinding context)
{
    if (pendingMatches(context)) failPending(context,"App main ResourceLoader creation failed"_s);
}
bool appResourcesContains(ResourceLoader* loader) { return appState().loads.contains(loader); }
void appResourcesSetDefersLoading(ResourceLoader& loader, bool value)
{ const auto it = appState().loads.find(&loader); if (it != appState().loads.end()) it->second->setDefers(value); }
void appResourcesLoadSynchronously(FrameLoader& frameLoader, const ResourceRequest& request, ResourceError& error, ResourceResponse& response, Vector<uint8_t>& data)
{
    Ref frame = frameLoader.frame();
    auto context = frame->document() && exactActive(frame.get(), *frame->document()) ? appState().active : nullptr;
    uint64_t ticket = 0;
    try {
        if (context && !context->closed) {
            const auto method = request.httpMethod().utf8(); const auto url = request.url().string().utf8();
            ticket = context->queue->prepare(context->hooks.document_epoch,{method.data(),method.length()},{url.data(),url.length()});
            if (auto reply = context->queue->retain_reply(ticket)) {
                response = appResponse(request.url(),*reply); data.append(std::span<const uint8_t>(reply->body));
                context->queue->cancel(ticket); return;
            }
        }
    } catch (...) { }
    if (ticket && context) context->queue->cancel(ticket);
    error = appError(request.url(),"Synchronous resource has no live app context"_s);
}
void appResourcesWillChangeMainDocument(LocalFrame& frame)
{
    auto& state = appState();
    if (!onOwner() || state.selectedFrame.get() != &frame || !state.active) return;
    const auto* active = state.lifecycle->active();
    if (!active || !frame.document() || active->document != physical(frame.document())) return;
#if BIB_ENGINE_PROVIDER_DOCUMENT_V2
    bibProviderDocumentAuthorityWillChange();
#endif
    (void)state.lifecycle->retire_active(*active);
    auto old = std::move(state.active);
    retireContext(old); // Pending main epoch remains distinct and live.
}
void appResourcesDidExplicitOpen(LocalFrame& frame)
{
    auto& state = appState(); auto context = state.pending;
    if (!onOwner() || !pendingMatches(context) || !context->explicitOpen || context->frame.get() != &frame) return;
    if (!frame.document() || frame.document() != context->document.get() || !context->loader
        || frame.loader().documentLoader() != context->loader.get()) {
        failPending(context,"Explicit-open document or loader changed before selection"_s); return;
    }
    RefPtr document = context->document; RefPtr loader = context->loader;
    if (!state.lifecycle->register_callback(context->token,physical(loader.get()))
        || !state.lifecycle->begin_selection(context->token,physical(&frame),physical(loader.get()),physical(document.get()))) {
        failPending(context,"Explicit-open selection already consumed"_s); return;
    }
#if BIB_ENGINE_PROVIDER_NEUTRAL
    if (!bibProviderSetProspectiveDocument(context->token) || !pendingMatches(context)) {
        failPending(context,"Explicit-open prospective service identity changed"_s); return;
    }
#endif
    uint64_t generation = 0;
    try { generation = foundationServicesResetApplicationDocumentChecked(frame,*document); }
    catch (...) { failPending(context,"Explicit-open service selection failed after execution"_s); return; }
    if (!pendingMatches(context) || frame.document()!=document.get() || frame.loader().documentLoader()!=loader.get()
        || !generation || generation!=foundationServicesReadyGeneration(frame,*document)
        || !state.lifecycle->activate(context->token,physical(&frame),physical(loader.get()),physical(document.get()),generation)) {
        failPending(context,"Explicit-open composition not ready"_s); return;
    }
    state.active=context; state.pending=nullptr;
}
void appResourcesWillDestroyEngine() { (void)bib_app_resources_close_all(); }
void appResourcesDidClearWindowObject(LocalFrame& frame, DOMWrapperWorld& world)
{
    auto& state=appState();
    if (!onOwner() || &world!=&mainThreadNormalWorldSingleton() || !state.active
        || state.active->frame.get()!=&frame || !state.active->document) return;
    if (exactActive(frame,*state.active->document)) return;
    auto snapshot=state.lifecycle->active_identity();
    if (!snapshot) return;
#if BIB_ENGINE_PROVIDER_DOCUMENT_V2
    bibProviderDocumentAuthorityWillChange();
#endif
    if (!state.lifecycle->retire_active(*snapshot)) return;
    auto old=std::move(state.active); RefPtr document=old->document;
    const auto generation=frame.document()==document.get() ? foundationServicesReadyGeneration(frame,*document) : 0;
    if (frame.document()==document.get()) foundationServicesRetireCompositionDocument(frame,*document,generation);
    retireContext(old);
}
bool appResourcesDocumentIdentity(LocalFrame& frame, const Document& document, BibAppDocumentIdentityV1& out)
{
    if (!appState().initialSelected || !exactActive(frame,document)) return false;
    const auto identity=appState().lifecycle->active_identity();
    out={sizeof(out),BIB_APP_DOCUMENT_IDENTITY_VERSION,identity->app_instance,identity->token,identity->resource_epoch,identity->service_generation};
    return true;
}
}

extern "C" int bib_app_resources_install_bundle(const BibAppResourceBundleHostV1* bundle,const uint8_t* entry,uint32_t length,uint64_t instance)
{
    auto& state=BIB::appState();
    if (state.strict || !bundle || !entry || !length || length>4096 || !instance
        || bundle->size!=sizeof(*bundle) || bundle->version!=BIB_APP_RESOURCE_BUNDLE_HOST_VERSION
        || bundle->reserved || !bundle->begin_epoch || !bundle->retire_epoch) return -1;
    try {
        const std::string_view url(reinterpret_cast<const char*>(entry),length);
        if (!url.starts_with("app://") || url.size()<71 || url.find_first_of("?#")!=std::string_view::npos) return -1;
        const auto authority=url.substr(6,64);
        if (!foundation::appended::candidate::normalize_app_resource_url(url,authority)) return -1;
        auto budget=std::make_shared<foundation::appended::candidate::AppResourceBudget>(bundle->max_response_bytes,bundle->max_inflight,bundle->max_retained_bytes);
        auto lifecycle=std::make_unique<foundation::appended::candidate::AppDocumentLifecycle>(instance);
        state.entry=url; state.authority=authority; state.bundle=*bundle;
        state.budget=std::move(budget); state.lifecycle=std::move(lifecycle);
        state.owner=std::this_thread::get_id(); state.strict=true; return 0;
    } catch (...) { return -1; }
}
extern "C" int bib_app_resources_close_all(void)
{
    auto& state=BIB::appState();
    if (!BIB::onOwner()) return -1;
#if BIB_ENGINE_PROVIDER_DOCUMENT_V2
    BIB::bibProviderDocumentAuthorityWillChange();
#endif
    state.closed=true; state.initialIntent=false;
    BIB::foundationServicesWillDestroyEngine();
    (void)state.lifecycle->retire_all();
    auto active=std::move(state.active); auto pending=std::move(state.pending);
    BIB::retireContext(active); BIB::retireContext(pending);
    // Keep the weak selected-frame identity through late callbacks so the
    // document fence still rejects author bytes after closure. It clears when
    // the frame actually dies; captured core liveness checks remain required.
    return 0; // strict + shared retained budget deliberately survive closure.
}
extern "C" int bib_app_resources_current_identity(BibAppDocumentIdentityV1* out)
{
    if (!out || !BIB::onOwner()) return -1;
    auto& state=BIB::appState(); RefPtr frame=state.selectedFrame.get();
    if (!frame || !frame->document() || !BIB::appResourcesDocumentIdentity(*frame,*frame->document(),*out)) return 0;
    return 1;
}
bool BIB::appResourcesRequiresDocumentFence(const void* frame)
{ return BIB::onOwner() && BIB::appState().started && BIB::appState().selectedFrame.get()==frame ? 1:0; }
bool BIB::appResourcesAllowAuthorBytes(const void* loader,const void* document)
{
    auto& state=BIB::appState();
    if (!BIB::onOwner() || state.closed || !state.initialSelected) return 0;
    RefPtr frame=state.selectedFrame.get();
    return frame && frame->document()==document && state.active && state.active->loader.get()==loader
        && frame->document() && BIB::exactActive(*frame,*frame->document()) ? 1:0;
}
bool BIB::appResourcesWillExplicitOpen(const void* framePointer,const void* loaderPointer,const void* documentPointer)
{
    auto& state=BIB::appState(); RefPtr frame=state.selectedFrame.get();
    if (!BIB::onOwner() || state.closed || !frame || frame.get()!=framePointer || frame->document()!=documentPointer
        || frame->loader().documentLoader()!=loaderPointer || !frame->document() || !BIB::exactActive(*frame,*frame->document())) return 0;
    std::shared_ptr<BIB::AppResourceContext> next;
    try {
        BIB::discardPending();
        next=BIB::newContext(*frame,*frame->loader().documentLoader(),frame->document()->url(),true);
        if (!next) return 0; // Allocation/admission failed before changing parser.
        next->document=frame->document(); state.pending=next;
        const auto active=state.lifecycle->active_identity();
        if (!active) { BIB::failPending(next,"Explicit-open predecessor changed"_s); return 0; }
#if BIB_ENGINE_PROVIDER_DOCUMENT_V2
        BIB::bibProviderDocumentAuthorityWillChange();
#endif
        if (!state.lifecycle->retire_active(*active)) { BIB::failPending(next,"Explicit-open predecessor changed"_s); return 0; }
        auto old=std::move(state.active); BIB::retireContext(old);
        return BIB::pendingMatches(next) && frame->document()==documentPointer && frame->loader().documentLoader()==loaderPointer ? 1:0;
    } catch (...) {
        if (BIB::pendingMatches(next)) BIB::failPending(next,"Explicit-open transition failed after execution"_s);
        return 0;
    }
}
