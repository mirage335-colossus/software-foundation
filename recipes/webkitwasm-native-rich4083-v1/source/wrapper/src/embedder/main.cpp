// Private native rich4083 source composition. WebCore compile/runtime unqualified.
// Frozen combined main preimage: ad3f96ed082e2ad227103572f16ab8460aa140642707ce5e8fc3749b0a1fd795.
#include "config.h"
#include "BibEngineProviderRuntime.h"
#include "BibEngineProviderLifecycleHooks.h"
#include "BibEngineProviderTimerHooks.h"
#include "BibAppResources.h"
#include "BibFoundationServiceBridge.h"
#include "BibIDBServer.h"
#include "BibMediaPlayer.h"
#include "BibPageClients.h"
#include "BibEngineProviderCompositionUndo.h"
#include "BibSocketProvider.h"
#include "BibStorage.h"
#include "CommonAtomStrings.h"
#include "CommonVM.h"
#include "CookieJar.h"
#include "Document.h"
#include "DocumentLoader.h"
#include "DocumentView.h"
#include "EmptyClients.h"
#include "FocusController.h"
#include "FrameLoader.h"
#include "GraphicsContextSkia.h"
#include "LocalFrame.h"
#include "LocalFrameInlines.h"
#include "LocalFrameView.h"
#if BIB_ENGINE_PROVIDER_DOCUMENT_V2
#include "ui/BibEngineUiOwner.hpp"
#include "popup/BibNativePopupOwner.hpp"
#include "LocalFrameViewLayoutContext.h"
#endif
#include "MemoryCache.h"
#include "NetworkStorageSession.h"
#include "Page.h"
#include "PageConfiguration.h"
#include "Settings.h"
#include "StorageSessionProvider.h"
#include <JavaScriptCore/InitializeThreading.h>
#include <JavaScriptCore/JSLock.h>
#include <pal/SessionID.h>
#include <wtf/JSONValues.h>
#include <wtf/MainThread.h>
#include <wtf/MonotonicTime.h>
#include <wtf/NeverDestroyed.h>
#include <wtf/ProcessPrivilege.h>
#include <wtf/RunLoop.h>
#include <wtf/WallTime.h>
#include <wtf/text/CString.h>
#include <array>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <limits>
#include <span>
#include <thread>
#include <utility>
WTF_IGNORE_WARNINGS_IN_THIRD_PARTY_CODE_BEGIN
#include <skia/core/SkCanvas.h>
#include <skia/core/SkImageInfo.h>
#include <skia/core/SkPixmap.h>
#include <skia/core/SkSurface.h>
WTF_IGNORE_WARNINGS_IN_THIRD_PARTY_CODE_END

#if !defined(BIB_ENGINE_PROVIDER_NATIVE) || BIB_ENGINE_PROVIDER_NATIVE != 1 || !BIB_ENGINE_PROVIDER_NEUTRAL
#error "Native rich provider runtime requires the explicit native neutral CPU composition"
#endif
#if defined(__EMSCRIPTEN__) || defined(__EMSCRIPTEN_PTHREADS__)
#error "Native rich provider runtime cannot use an Emscripten target"
#endif
static_assert(sizeof(void*) == 8, "Native rich document provider requires a 64-bit target");
#if !BIB_APP_RESOURCES || !BIB_FOUNDATION_SERVICES
#error "Provider runtime requires the actual combined resource and service adapters"
#endif

namespace BIB {
void installEmbedderStrategies(); // EmbedderStrategies.cpp
void setRequestBlocklistEnabled(bool); // EmbedderStrategies.cpp
Ref<WebCore::StorageSessionProvider> createEmbedderStorageSessionProvider(); // EmbedderStrategies.cpp
WebCore::NetworkStorageSession& embedderStorageSession(); // EmbedderStrategies.cpp

// Persistence registries declared in BibStorage.h — engine-thread only.
HashMap<String, RefPtr<BibStorageArea>>& bibLocalAreaRegistry()
{
    static NeverDestroyed<HashMap<String, RefPtr<BibStorageArea>>> registry;
    return registry;
}
HashMap<String, HashMap<String, String>>& bibPendingStorageImport()
{
    static NeverDestroyed<HashMap<String, HashMap<String, String>>> pending;
    return pending;
}
}

namespace {
constexpr int kWidth = 800;
constexpr int kHeight = 600;
constexpr size_t kFrameBytes = size_t(kWidth) * kHeight * 4;
constexpr bool g_gpu = false;
// Same process-lifetime ownership as the retained embedder. No destroy/reset.
struct Engine {
    RefPtr<WebCore::Page> page;
    RefPtr<WebCore::LocalFrame> mainFrame;
    sk_sp<SkSurface> surface;
};
Engine* g_engine;
BibEngineHostV1 g_providerHost { };
std::thread::id g_providerOwner;
std::atomic<bool> g_providerHostRetained { false };
uint64_t g_providerInstance { 0 };
uint64_t g_providerFrameRevision { 0 };
bool g_providerAttempted { false };
bool g_providerReady { false };
bool g_providerRaster { false };
bool g_providerFirstFrame { true };
bool g_inPaint { false };
WTF::RunLoop::Timer* g_providerPersistenceTimer { nullptr };
BibEngineDocumentV1 g_providerPublishedDocument { };
#if BIB_ENGINE_PROVIDER_DOCUMENT_V2
// Borrowed only from the exact process-lived Page constructed below. Never
// infer authoritative input-method state from the prototype diagnostic mirror.
BIB::BibEditorClient* g_providerEditorClient { nullptr };
BIB::BibChromeClient* g_providerChromeClient { nullptr };
#endif
// Bounded permanent backing/staging storage exists before any dirty snapshot.
// No allocation can fail between clearing damage and packing the callback.
std::array<uint8_t, kFrameBytes> g_providerDamage;
uint8_t g_blitPixels[kFrameBytes];

bool providerUiFaulted()
{
#if BIB_ENGINE_PROVIDER_DOCUMENT_V2
    return BIB::EngineUI::faulted();
#else
    return false;
#endif
}
bool providerOnOwner()
{
    return g_providerHostRetained.load(std::memory_order_acquire)
        && g_providerOwner == std::this_thread::get_id();
}
WebCore::LocalFrameView* mainFrameView()
{
    // Committed navigation replaces the view; never retain a boot view.
    return g_engine ? g_engine->mainFrame->view() : nullptr;
}
bool providerSameDocument(const BibEngineDocumentV1& a, const BibEngineDocumentV1& b)
{
    return a.application_instance == b.application_instance
        && a.document_sequence == b.document_sequence
        && a.service_generation == b.service_generation;
}
bool providerCurrentDocument(BibEngineDocumentV1& document)
{
    BibAppDocumentIdentityV1 identity { };
    if (providerUiFaulted() || bib_app_resources_current_identity(&identity) != 1
        || identity.size != sizeof(identity) || identity.version != BIB_APP_DOCUMENT_IDENTITY_VERSION
        || identity.application_instance != g_providerInstance
        || !identity.document_sequence || !identity.service_generation)
        return false;
    document = { identity.application_instance, identity.document_sequence, identity.service_generation };
    return true;
}
#if BIB_ENGINE_PROVIDER_DOCUMENT_V2
bool providerDocumentFence(WebCore::LocalFrame& frame, const WebCore::Document& document,
    BibAppDocumentIdentityV1& identity)
{
    if (!providerOnOwner() || providerUiFaulted() || !g_providerReady || !g_engine || !g_engine->page
        || g_engine->mainFrame.get() != &frame || g_engine->page->localMainFrame() != &frame
        || frame.document() != &document)
        return false;
    identity = { };
    identity.size = sizeof(identity);
    identity.version = BIB_APP_DOCUMENT_IDENTITY_VERSION;
    return BIB::appResourcesDocumentIdentity(frame, document, identity)
        && identity.size == sizeof(identity) && identity.version == BIB_APP_DOCUMENT_IDENTITY_VERSION
        && identity.application_instance == g_providerInstance && identity.document_sequence
        && identity.service_generation && identity.resource_epoch;
}
bool providerDocumentFenceMatches(WebCore::LocalFrame& frame, const WebCore::Document& document,
    uint64_t application, uint64_t sequence, uint64_t service, uint64_t resource)
{
    BibAppDocumentIdentityV1 identity { };
    return application && sequence && service && resource
        && providerDocumentFence(frame, document, identity)
        && identity.application_instance == application && identity.document_sequence == sequence
        && identity.service_generation == service && identity.resource_epoch == resource;
}
bool providerUiInNativeTurn(void* context) noexcept
{
    // Pending initial/navigation documents still execute inside this same
    // retained Page's existing Bridge turn and actual common-VM API lock.
    return providerOnOwner() && !providerUiFaulted() && context && context == g_engine
        && g_engine->page && g_engine->mainFrame
        && g_engine->page->localMainFrame() == g_engine->mainFrame.get()
        && BIB::foundationServicesInOwnerEngineTurn()
        && WebCore::commonVM().currentThreadIsHoldingAPILock();
}
bool providerUiReadCurrent(void* context, BIB::EngineUI::Snapshot& current) noexcept
{
    if (!providerUiInNativeTurn(context) || !g_providerChromeClient)
        return false;
    RefPtr page = g_engine->page;
    RefPtr frame = g_engine->mainFrame;
    RefPtr document = frame->document();
    BibAppDocumentIdentityV1 identity { };
    if (!document || !providerDocumentFence(*frame, *document, identity))
        return false;
    const auto identifier = page->identifier();
    if (!identifier)
        return false;
    const auto pageIdentifier = identifier->toUInt64();
    if (!pageIdentifier)
        return false;
    current = { };
    current.owner = BIB::EngineUI::identity();
    current.owner.application = identity.application_instance;
    current.chrome = g_providerChromeClient;
    current.page = page.get();
    current.main_frame = frame.get();
    current.document = document.get();
    current.page_identifier = pageIdentifier;
    current.document_sequence = identity.document_sequence;
    current.service_generation = identity.service_generation;
    current.resource_epoch = identity.resource_epoch;
    current.viewport_width = kWidth;
    current.viewport_height = kHeight;
    current.raster = g_providerRaster;
    // Input context, authority revision and modal metadata belong to EngineUI.
    return true;
}
void providerUiDamage(void* context, BIB::EngineUI::Rect rect) noexcept
{
    if (!providerOnOwner() || providerUiFaulted() || !context || context != g_engine)
        return;
    const auto clipped = WebCore::intersection(
        WebCore::IntRect(rect.x, rect.y, rect.width, rect.height),
        WebCore::IntRect(0, 0, kWidth, kHeight));
    if (!clipped.isEmpty())
        BIB::addDamage(clipped); // Local damage only; never enter the Host.
}
#endif
static bool paintFrameRect(const WebCore::IntRect& dirty)
{
    RefPtr view = mainFrameView();
    if (!view || providerUiFaulted())
        return false;
    SkCanvas* canvas = g_engine->surface->getCanvas();
    canvas->save();
    canvas->clipRect(SkRect::MakeXYWH(dirty.x(), dirty.y(), dirty.width(), dirty.height()));
    canvas->drawColor(SK_ColorWHITE);
    // Accelerated mode only changes texture-backed-image handling (no raster
    // copies for shadows) — Canvas-purpose GL gymnastics stay off either way.
    WebCore::GraphicsContextSkia context(*canvas,
        g_gpu ? WebCore::RenderingMode::Accelerated : WebCore::RenderingMode::Unaccelerated,
        WebCore::RenderingPurpose::Unspecified);
    g_inPaint = true;
    view->paint(context, dirty);
#if BIB_ENGINE_PROVIDER_DOCUMENT_V2
    // Compose the owned popup snapshot inside the same saved canvas clip.
    const bool popupPainted = BIB::EnginePopup::paint(context, dirty);
#else
    constexpr bool popupPainted = true;
#endif
    g_inPaint = false;
    canvas->restore();
    return popupPainted && !providerUiFaulted();
}

// Callers snapshot-and-clear the dirty state BEFORE painting: damage
// reported DURING view->paint (paint-triggered invalidations) must
// accumulate for the NEXT frame, not be wiped post-paint (Codex 2026-06-11).
static void clearDamage()
{
    BIB::g_frameDirty = false;
    BIB::g_damageCount = 0;
    BIB::g_uploadRect = { };
}

// Fast-scroll blit (ChromeClient::scroll): shift the already-painted pixels
// by `delta` within the scrolled clip, in BOTH mirrors (g_blitPixels and the
// SkSurface — they must stay identical or later partial paints composite
// over a stale base). WebCore then only repaints the strips the shift
// exposed; the host re-uploads the whole moved region via g_uploadRect.
static void bibScrollBlit(const WebCore::IntSize& delta, const WebCore::IntRect& rectToScroll, const WebCore::IntRect& clipRect)
{
    const WebCore::IntRect frameRect(0, 0, kWidth, kHeight);
    WebCore::IntRect scrollRect = WebCore::intersection(WebCore::intersection(rectToScroll, clipRect), frameRect);
#if BIB_ENGINE_PROVIDER_DOCUMENT_V2
    if (BIB::EnginePopup::blocksScrollBlit()) {
        BIB::addDamage(WebCore::intersection(clipRect, frameRect));
        return; // Composited popup pixels must be repainted, never shifted.
    }
#endif
    if (!g_engine || g_inPaint || scrollRect.isEmpty()) {
        BIB::addDamage(clipRect);
        return;
    }
    const int dx = delta.width(), dy = delta.height();
    WebCore::IntRect dst = scrollRect;
    dst.move(dx, dy);
    dst.intersect(scrollRect);
    if (dst.isEmpty()) { // shifted clean out of the clip — nothing reusable
        BIB::addDamage(scrollRect);
        return;
    }
    WebCore::IntRect src = dst;
    src.move(-dx, -dy);

    // Pending unpainted damage: WebCore invalidates scrollbars/content
    // BEFORE calling ChromeClient::scroll, so bailing out here tripped on
    // EVERY scroll tick and kept blit-shift dormant (2026-06-11 scroll
    // probe: 40/40 full-viewport repaints). Damage tracks the content it
    // marks — translate the part inside the scrolled clip by the delta
    // (the Windows port offsets its backing-store dirty region the same
    // way). Stale pixels can only land where the shift writes (dst);
    // damage shifted beyond dst is overwritten or clipped away with them.
    // Fixed/sticky elements are NOT a smear hazard: scrollContentsFastPath
    // invalidates their old+new rects AFTER this callback returns.
    if (BIB::g_frameDirty) {
        // A pending rect covering the whole scroll region means the blit
        // preserves nothing worth keeping.
        for (size_t i = 0; i < BIB::g_damageCount; ++i) {
            if (BIB::g_damageRects[i].contains(scrollRect)) {
                BIB::addDamage(scrollRect);
                return;
            }
        }
        // Per rect: damage outside the clip stays put; damage straddling
        // the clip edge stays in place in FULL and gains a translated copy
        // (repaints a little extra, never smears); fully-inside damage
        // rides the scroll. Translated copies clip to dst — stale pixels
        // can only land where the shift writes.
        WebCore::IntRect pending[BIB::kMaxDamageRects * 2];
        size_t pendingCount = 0;
        for (size_t i = 0; i < BIB::g_damageCount; ++i) {
            const WebCore::IntRect r = BIB::g_damageRects[i];
            WebCore::IntRect moving = WebCore::intersection(r, scrollRect);
            if (moving.isEmpty()) {
                pending[pendingCount++] = r;
                continue;
            }
            if (moving != r)
                pending[pendingCount++] = r;
            moving.move(dx, dy);
            moving.intersect(dst);
            if (!moving.isEmpty())
                pending[pendingCount++] = moving;
        }
        BIB::g_damageCount = 0;
        BIB::g_frameDirty = false;
        for (size_t i = 0; i < pendingCount; ++i)
            BIB::addDamage(pending[i]); // re-merges + re-arms g_frameDirty
    }

    // Overlap-safe row walk over g_blitPixels (memmove handles x overlap).
    const size_t rowBytes = static_cast<size_t>(dst.width()) * 4;
    if (dy > 0) {
        for (int y = dst.height() - 1; y >= 0; --y)
            memmove(g_blitPixels + ((static_cast<size_t>(dst.y() + y)) * kWidth + dst.x()) * 4,
                g_blitPixels + ((static_cast<size_t>(src.y() + y)) * kWidth + src.x()) * 4, rowBytes);
    } else {
        for (int y = 0; y < dst.height(); ++y)
            memmove(g_blitPixels + ((static_cast<size_t>(dst.y() + y)) * kWidth + dst.x()) * 4,
                g_blitPixels + ((static_cast<size_t>(src.y() + y)) * kWidth + src.x()) * 4, rowBytes);
    }
    // Mirror the shift onto the surface — via the CANVAS writePixels, which
    // (unlike SkSurface::writePixels) reports failure. On failure the two
    // mirrors have DIVERGED (buffer shifted, surface not) — full-frame
    // damage repaints and re-reads everything, resyncing both; never leave
    // it silent (Codex confirmed finding, 2026-06-11).
    auto info = SkImageInfo::Make(dst.width(), dst.height(), kRGBA_8888_SkColorType, kUnpremul_SkAlphaType);
    if (!g_engine->surface->getCanvas()->writePixels(info, g_blitPixels + (static_cast<size_t>(dst.y()) * kWidth + dst.x()) * 4, kWidth * 4, dst.x(), dst.y())) {
        BIB::addDamage(frameRect);
        return;
    }

    // Host re-uploads everything that moved…
    BIB::g_uploadRect.unite(scrollRect);
    // …WebCore repaints only the exposed strips (scrollRect minus dst):
    // a horizontal band (top or bottom) and/or a vertical band (left/right).
    if (dy > 0)
        BIB::addDamage({ scrollRect.x(), scrollRect.y(), scrollRect.width(), dy });
    else if (dy < 0)
        BIB::addDamage({ scrollRect.x(), scrollRect.maxY() + dy, scrollRect.width(), -dy });
    if (dx > 0)
        BIB::addDamage({ scrollRect.x(), scrollRect.y(), dx, scrollRect.height() });
    else if (dx < 0)
        BIB::addDamage({ scrollRect.maxX() + dx, scrollRect.y(), -dx, scrollRect.height() });
}
static String bibBuildPersistJSON()
{
    auto root = JSON::Object::create();
    root->setInteger("v"_s, 1);

    auto cookies = JSON::Array::create();
    for (auto& cookie : BIB::embedderStorageSession().cookieDatabase().getAllCookies()) {
        auto c = JSON::Object::create();
        c->setString("name"_s, cookie.name);
        c->setString("value"_s, cookie.value);
        c->setString("domain"_s, cookie.domain);
        c->setString("path"_s, cookie.path);
        if (cookie.expires)
            c->setDouble("expires"_s, *cookie.expires); // ms since epoch
        c->setBoolean("httpOnly"_s, cookie.httpOnly);
        c->setBoolean("secure"_s, cookie.secure);
        c->setBoolean("session"_s, cookie.session);
        cookies->pushObject(WTF::move(c));
    }
    root->setArray("cookies"_s, WTF::move(cookies));

    auto storage = JSON::Object::create();
    for (auto& [origin, area] : BIB::bibLocalAreaRegistry()) {
        auto items = JSON::Object::create();
        area->forEachItem([&](const String& key, const String& value) {
            items->setString(key, value);
        });
        storage->setObject(origin, WTF::move(items));
    }
    // Origins seeded from a previous session that the guest has not opened
    // yet THIS session still live in the pending map — dropping them here
    // would erase a prior session's data just by not visiting the site.
    for (auto& [origin, pendingItems] : BIB::bibPendingStorageImport()) {
        if (BIB::bibLocalAreaRegistry().contains(origin))
            continue;
        auto items = JSON::Object::create();
        for (auto& [key, value] : pendingItems)
            items->setString(key, value);
        storage->setObject(origin, WTF::move(items));
    }
    root->setObject("localStorage"_s, WTF::move(storage));
    return root->toJSONString();
}

static void bibSeedPersistedState(const String& json)
{
    auto value = JSON::Value::parseJSON(json);
    auto root = value ? value->asObject() : nullptr;
    if (!root) {
        printf("EMBEDDER: persist seed unreadable — starting fresh\n");
        return;
    }

    int cookieCount = 0;
    if (auto cookieArray = root->getArray("cookies"_s)) {
        auto& jar = BIB::embedderStorageSession().cookieDatabase();
        double nowMs = WallTime::now().secondsSinceEpoch().milliseconds();
        for (auto& entry : *cookieArray) {
            auto c = entry->asObject();
            if (!c)
                continue;
            WebCore::Cookie cookie;
            cookie.name = c->getString("name"_s);
            cookie.value = c->getString("value"_s);
            cookie.domain = c->getString("domain"_s);
            cookie.path = c->getString("path"_s);
            cookie.expires = c->getDouble("expires"_s);
            cookie.httpOnly = c->getBoolean("httpOnly"_s).value_or(false);
            cookie.secure = c->getBoolean("secure"_s).value_or(false);
            cookie.session = c->getBoolean("session"_s).value_or(false);
            if (cookie.name.isEmpty() && cookie.value.isEmpty())
                continue;
            if (!cookie.session && cookie.expires && *cookie.expires <= nowMs)
                continue; // expired while we were away
            if (jar.setCookie(cookie))
                cookieCount++;
        }
    }

    int originCount = 0;
    if (auto storage = root->getObject("localStorage"_s)) {
        for (auto& member : *storage) {
            auto items = member.value->asObject();
            if (!items)
                continue;
            HashMap<String, String> map;
            for (auto& item : *items) {
                String itemValue;
                if (item.value->asString(itemValue))
                    map.set(item.key, itemValue);
            }
            BIB::bibPendingStorageImport().set(member.key, WTF::move(map));
            originCount++;
        }
    }
    printf("EMBEDDER: persist seed: %d cookies, %d localStorage origins\n", cookieCount, originCount);
}

// This has no Module/OPFS/event-loop behavior. The callback copies/stages only.
void providerMaybePersist()
{
    static NeverDestroyed<String> lastJSON;
    static MonotonicTime lastCheck;
    if (providerUiFaulted() || !g_providerHost.persistence)
        return;
    const auto now = MonotonicTime::now();
    if (now - lastCheck < Seconds(5))
        return;
    lastCheck = now;
    String json = bibBuildPersistJSON();
    if (json == lastJSON.get())
        return;
    CString utf8 = json.utf8();
    if (utf8.length() > 12 * 1024 * 1024)
        return;
    BibEngineBytesV1 bytes { reinterpret_cast<const uint8_t*>(utf8.data()), static_cast<uint32_t>(utf8.length()), 0 };
    g_providerHost.persistence(g_providerHost.context, &bytes);
    lastJSON.get() = WTF::move(json);
}

// Caller holds the complete Bridge guard and common-VM lock. It must not call
// the diagnostic bib_render/bibPushFrameIfDirty entry points.
int32_t providerPublishDamageLocked()
{
    if (providerUiFaulted())
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    if (!g_providerRaster)
        return BIB_ENGINE_OK;
    BibEngineDocumentV1 document { };
    if (!providerCurrentDocument(document))
        return BIB_ENGINE_OK; // The genuine empty bootstrap is not app output.
    const bool force = g_providerFirstFrame || !providerSameDocument(document, g_providerPublishedDocument);
    if (!force && !BIB::g_frameDirty && BIB::g_uploadRect.isEmpty())
        return BIB_ENGINE_OK;
    if (!g_engine || !g_engine->surface || !mainFrameView())
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    // Exhaustion is detected before consuming any dirty state.
    if (g_providerFrameRevision == std::numeric_limits<uint64_t>::max())
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    RefPtr currentDocument = g_engine->mainFrame->document();
    if (!currentDocument)
        return BIB_ENGINE_OK;
    currentDocument->updateLayoutIgnorePendingStylesheets();
    BibEngineDocumentV1 afterLayout { };
    if (!providerCurrentDocument(afterLayout) || !providerSameDocument(document, afterLayout)) {
        BIB::addDamage({ 0, 0, kWidth, kHeight });
        return BIB_ENGINE_OK;
    }
    const WebCore::IntRect frameRect(0, 0, kWidth, kHeight);
    WebCore::IntRect dirty[BIB::kMaxDamageRects];
    size_t dirtyCount = 0;
    if (force)
        dirty[dirtyCount++] = frameRect;
    else {
        for (size_t i = 0; i < BIB::g_damageCount; ++i) {
            auto rect = WebCore::intersection(BIB::g_damageRects[i], frameRect);
            if (!rect.isEmpty())
                dirty[dirtyCount++] = rect;
        }
    }
    WebCore::IntRect upload = force ? WebCore::IntRect() : WebCore::intersection(BIB::g_uploadRect, frameRect);
    clearDamage(); // Paint-triggered invalidations belong to the next frame.
    if (!dirtyCount && upload.isEmpty())
        return BIB_ENGINE_OK;
    WebCore::IntRect paintedBounds;
    for (size_t i = 0; i < dirtyCount; ++i) {
        const auto& rect = dirty[i];
        bool painted = paintFrameRect(rect);
        bool readBack = false;
        if (painted) {
            auto info = SkImageInfo::Make(rect.width(), rect.height(), kRGBA_8888_SkColorType, kUnpremul_SkAlphaType);
            auto* destination = g_blitPixels + (size_t(rect.y()) * kWidth + rect.x()) * 4;
            readBack = g_engine->surface->readPixels(SkPixmap(info, destination, kWidth * 4), rect.x(), rect.y());
        }
        if (!painted || !readBack) {
            for (size_t j = i; j < dirtyCount; ++j)
                BIB::addDamage(dirty[j]);
            BIB::g_uploadRect.unite(upload);
            BIB::g_uploadRect.unite(paintedBounds);
            return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
        }
        paintedBounds.unite(rect);
    }
    auto box = paintedBounds;
    box.unite(upload);
    BibEngineDocumentV1 afterPaint { };
    if (!providerCurrentDocument(afterPaint) || !providerSameDocument(document, afterPaint)) {
        BIB::addDamage(frameRect);
        g_providerFirstFrame = true;
        return BIB_ENGINE_OK;
    }
    const auto rowBytes = static_cast<uint32_t>(box.width() * 4);
    const auto length = static_cast<uint32_t>(rowBytes * box.height());
    for (int y = 0; y < box.height(); ++y) {
        const auto* row = g_blitPixels + (size_t(box.y() + y) * kWidth + box.x()) * 4;
        std::memcpy(g_providerDamage.data() + size_t(y) * rowBytes, row, rowBytes);
    }
    BibEngineDamageV1 damage { sizeof(BibEngineDamageV1), 1, document,
        ++g_providerFrameRevision, box.x(), box.y(), box.width(), box.height(),
        rowBytes, length, g_providerDamage.data() };
    // Borrowed bytes are stable until return. This callback cannot run author
    // script, publish GUI, pump native services or reenter the provider.
    g_providerHost.damage(g_providerHost.context, &damage);
    g_providerPublishedDocument = document;
    g_providerFirstFrame = false;
    return BIB_ENGINE_OK;
}
} // namespace

namespace BIB {
bool onEngineThread() { return providerOnOwner(); }
bool proxyToEngine(void (*)(void*), void*) { return false; }
// Strict app documents execute entirely inside their existing JSC world.
void injectWasmPolyfill(WebCore::LocalFrame&, WebCore::DOMWrapperWorld&) { }

WebCore::Page* bibProviderPage()
{
    return providerOnOwner() && !providerUiFaulted() && g_providerReady && g_engine ? g_engine->page.get() : nullptr;
}

#if BIB_ENGINE_PROVIDER_DOCUMENT_V2
// The edited Document can be an owned subframe. Never substitute the main
// Document or reinterpret a foreign Page's editor client during old9 cleanup.
static BibEditorClient* compositionUndoClient(WebCore::Document& document)
{
    if (!providerOnOwner() || providerUiFaulted() || !g_providerReady || !g_engine || !g_engine->page || !g_providerEditorClient)
        return nullptr;
    auto* frame = document.frame();
    if (!frame || frame->document() != &document || frame->page() != g_engine->page.get()
        || document.page() != g_engine->page.get() || &g_engine->page->editorClient() != g_providerEditorClient)
        return nullptr;
    return g_providerEditorClient;
}
std::uint64_t bibProviderCompositionUndoBegin(WebCore::Document& document)
{
    auto* client = compositionUndoClient(document);
    return client ? client->compositionUndoBegin(document) : 0;
}
bool bibProviderCompositionUndo(WebCore::Document& document, CompositionUndoAction action, std::uint64_t token, const WebCore::UndoStep* step)
{
    // Exact empty historical scopes need no replacement Document/frame/editor
    // access. The client's journal retains borrowed Document identity + token;
    // the backend alone owns the strong original Document reference.
    if (action == CompositionUndoAction::matchEmpty || action == CompositionUndoAction::closeEmpty
        || action == CompositionUndoAction::quarantine) {
        if (providerOnOwner() && !providerUiFaulted() && g_providerReady && g_engine && g_engine->page && g_providerEditorClient
            && &g_engine->page->editorClient() == g_providerEditorClient
            && g_providerEditorClient->compositionUndoOwner(token, document)
            && g_providerEditorClient->compositionUndoMatch(token, nullptr)) {
            if (action == CompositionUndoAction::matchEmpty) return true;
            if (action == CompositionUndoAction::closeEmpty) return g_providerEditorClient->compositionUndoCommit(token, nullptr);
            g_providerEditorClient->compositionUndoQuarantine(token); return true;
        }
        if (action != CompositionUndoAction::quarantine) return false;
    }
    auto* client = compositionUndoClient(document);
    if (!client || !token || !client->compositionUndoOwner(token, document)) return false;
    switch (action) {
    case CompositionUndoAction::matchEmpty:
    case CompositionUndoAction::closeEmpty: return false;
    case CompositionUndoAction::matchPending: return client->compositionUndoMatch(token, step);
    case CompositionUndoAction::commit: return client->compositionUndoCommit(token, step);
    case CompositionUndoAction::detach: return client->compositionUndoDetach(token, step);
    case CompositionUndoAction::matchRollback: return client->compositionUndoRollbackMatch(token, step);
    case CompositionUndoAction::consume: return client->compositionUndoConsume(token, step);
    case CompositionUndoAction::finish: return client->compositionUndoFinish(token, step);
    case CompositionUndoAction::quarantine: client->compositionUndoQuarantine(token); return true;
    }
    return false;
}
WTF::RefPtr<WebCore::LocalFrame> bibProviderDocumentMainFrame()
{
    if (!providerOnOwner() || providerUiFaulted() || !g_providerReady || !g_engine || !g_engine->mainFrame)
        return nullptr;
    RefPtr frame = g_engine->mainFrame;
    RefPtr document = frame->document();
    BibAppDocumentIdentityV1 identity { };
    if (!document || !providerDocumentFence(*frame, *document, identity))
        return nullptr;
    return frame;
}
std::optional<bool> bibProviderDocumentInputMethodState(const WebCore::Document& document)
{
    auto frame = bibProviderDocumentMainFrame();
    if (!frame || frame->document() != &document || !g_providerEditorClient
        || &g_engine->page->editorClient() != g_providerEditorClient)
        return std::nullopt;
    return g_providerEditorClient->documentInputMethodState(document);
}
bool bibProviderDocumentForeground(const WebCore::Document& document)
{
    auto frame = bibProviderDocumentMainFrame();
    if (!frame || frame->document() != &document)
        return false;
    const auto& focus = g_engine->page->focusController();
    // Native Page state only. The App/Owner's trusted host-foreground gate is
    // additional authority, not invented OS focus or a physical input context.
    return focus.isActive() && focus.isFocused();
}
bool bibProviderDocumentCheckpoint(WebCore::LocalFrame& frame, WebCore::Document& document,
    uint64_t application, uint64_t sequence, uint64_t service, uint64_t resource)
{
    // Caller retains the existing complete Host/Bridge/common-VM lock scope.
    // This helper deliberately creates no new execution or scheduling scope.
    if (!providerDocumentFenceMatches(frame, document, application, sequence, service, resource))
        return false;
    RefPtr view = frame.view();
    if (!view || view->layoutContext().isInLayout())
        return false;
    document.updateLayoutIgnorePendingStylesheets();
    // Layout may replace the Document, loader, view or service generation.
    // Its return enum alone is not current-style/current-layout evidence.
    return providerDocumentFenceMatches(frame, document, application, sequence, service, resource)
        && frame.view() == view.get() && !document.needsStyleRecalc()
        && !view->needsLayout() && !view->layoutContext().isInLayout();
}
#endif

int32_t bibProviderCreatePage(const ProviderRuntimeConfig& config)
{
    if (g_providerAttempted || providerUiFaulted())
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    g_providerAttempted = true;
    if (!config.host || config.host->size < sizeof(BibEngineHostV1)
        || config.host->abi_major != BIB_ENGINE_ABI_MAJOR || config.host->abi_minor != BIB_ENGINE_ABI_MINOR
        || config.host->reserved || !config.application_instance || config.raster_output > 1
        || !config.host->wake || !config.host->replace_timer_ms
        || (config.raster_output && !config.host->damage)
        || config.persist_seed.reserved || config.persist_seed.length > 12 * 1024 * 1024
        || (config.persist_seed.length && !config.persist_seed.data) || !appResourcesStrict())
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    g_providerHost = *config.host;
    g_providerHost.size = sizeof(g_providerHost);
    g_providerInstance = config.application_instance;
    g_providerRaster = config.raster_output;
    g_providerOwner = std::this_thread::get_id();
    g_providerHostRetained.store(true, std::memory_order_release);
    // This nested legacy guard gives native JSC functions their required bridge
    // depth. ProviderGuard remains the outer complete host-turn owner.
    FoundationServiceEngineCall bridgeTurn;
    if (!bridgeTurn)
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    JSC::initialize();
    WTF::initializeMainThread();
    WTF::setProcessPrivileges(WTF::allPrivileges());
    WebCore::initializeCommonAtomStrings();
    setRequestBlocklistEnabled(false);
    installEmbedderStrategies();
    appResourcesInitializeScheme();
    WTF::RunLoop::setWakeUpCallback([] {
        if (g_providerHostRetained.load(std::memory_order_acquire) && !providerUiFaulted())
            g_providerHost.wake(g_providerHost.context);
    });
    // Only the copied RunLoopGeneric.cpp gains this private setter. No public
    // RunLoop header, member, virtual or target-wide compile flag changes.
    if (bib_engine_provider_set_timer_scheduler_v1(&g_providerHost, [](void* context, double delay, uint32_t armed) {
        auto& host = *static_cast<BibEngineHostV1*>(context);
        if (!providerUiFaulted())
            host.replace_timer_ms(host.context, delay, armed);
    }))
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    g_mediaEnabled = false;
    auto pageConfiguration = WebCore::pageConfigurationWithEmptyClients(WebCore::PageIdentifier::generate(), PAL::SessionID::defaultSessionID());
#if BIB_ENGINE_PROVIDER_DOCUMENT_V2
    auto chromeClient = makeUniqueRef<BibChromeClient>();
    auto* documentChromeClient = &chromeClient.get();
    pageConfiguration.chromeClient = WTF::move(chromeClient);
#else
    pageConfiguration.chromeClient = makeUniqueRef<BibChromeClient>();
#endif
#if BIB_ENGINE_PROVIDER_DOCUMENT_V2
    auto editorClient = makeUniqueRef<BibEditorClient>();
    auto* documentEditorClient = &editorClient.get();
    pageConfiguration.editorClient = WTF::move(editorClient);
#else
    pageConfiguration.editorClient = makeUniqueRef<BibEditorClient>();
#endif
    pageConfiguration.cookieJar = WebCore::CookieJar::create(createEmbedderStorageSessionProvider());
    pageConfiguration.storageNamespaceProvider = BibStorageNamespaceProvider::create();
    pageConfiguration.databaseProvider = BibDatabaseProvider::create();
    pageConfiguration.socketProvider = BibSocketProvider::create();
    auto* localParameters = std::get_if<WebCore::PageConfiguration::LocalMainFrameCreationParameters>(&pageConfiguration.mainFrameCreationParameters);
    if (!localParameters)
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    localParameters->effectiveSandboxFlags = { };
    localParameters->clientCreator = [](auto&, auto& frameLoader) -> UniqueRef<WebCore::LocalFrameLoaderClient> {
        return WTF::makeUniqueRefWithoutRefCountedCheck<BibFrameLoaderClient>(frameLoader);
    };
    auto page = WebCore::Page::create(WTF::move(pageConfiguration));
    // The pinned Page has no vm() accessor. Its main normal world uses commonVM.
    JSC::JSLockHolder lock(WebCore::commonVM());
    page->settings().setScriptEnabled(true);
    page->settings().setSelectShowPickerEnabled(true);
    page->settings().setAcceleratedCompositingEnabled(false);
    page->settings().setLoadsImagesAutomatically(true);
    page->settings().setServiceWorkersEnabled(false);
    page->settings().setUsesBackForwardCache(false);
    page->settings().setLocalStorageEnabled(true);
    page->settings().setSessionStorageEnabled(true);
    page->settings().setRequestIdleCallbackEnabled(true);
    WebCore::MemoryCache::singleton().setCapacities(0, 16 * 1024 * 1024, 64 * 1024 * 1024);
    if (config.persist_seed.length)
        bibSeedPersistedState(String::fromUTF8(std::span<const char>(reinterpret_cast<const char*>(config.persist_seed.data), config.persist_seed.length)));
    RefPtr frame = page->localMainFrame();
    if (!frame)
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    frame->setView(WebCore::LocalFrameView::create(*frame, WebCore::IntSize(kWidth, kHeight)));
    frame->init(); // Preserve the genuine initial empty Document.
    RefPtr view = frame->view();
    if (!view || !frame->document())
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    view->setCanHaveScrollbars(true);
    page->focusController().setActive(true);
    page->focusController().setFocused(true);
    sk_sp<SkSurface> surface;
    if (g_providerRaster) {
        auto info = SkImageInfo::Make(kWidth, kHeight, kRGBA_8888_SkColorType, kPremul_SkAlphaType);
        surface = SkSurfaces::Raster(info);
        if (!surface)
            return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    }
    g_engine = new Engine { WTF::move(page), WTF::move(frame), WTF::move(surface) };
#if BIB_ENGINE_PROVIDER_DOCUMENT_V2
    g_providerEditorClient = documentEditorClient;
    g_providerChromeClient = documentChromeClient;
    if (!EngineUI::attachRuntime(*g_providerChromeClient,
        { g_engine, providerUiInNativeTurn, providerUiReadCurrent, providerUiDamage }))
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
#endif
    g_scrollBlit = g_providerRaster ? bibScrollBlit : nullptr;
    addDamage({ 0, 0, kWidth, kHeight });
    if (g_providerHost.persistence) {
        // This timer only fires inside the owner's guarded RunLoop cycle. Its
        // deadline uses the typed scheduler, so idle changes eventually persist
        // without the supplier's perpetual browser requestAnimationFrame loop.
        g_providerPersistenceTimer = new WTF::RunLoop::Timer(WTF::RunLoop::mainSingleton(), "BibProviderPersistence"_s, [] {
            providerMaybePersist();
        });
        g_providerPersistenceTimer->startRepeating(5_s);
    }
    // Binding installed actual service/resource host tables before Page creation.
    // No inline author bytes, fallback HTML, demo registry or outer JS executes.
    if (providerUiFaulted())
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    if (!appResourcesStartApplicationLoad(*g_engine->mainFrame) || providerUiFaulted())
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    // READY means runtime initialization and accepted normal load submission.
    // Actual immutable entry proof and exact Document selection complete on
    // later owner steps; current_document stays unavailable until then.
    g_providerReady = true;
    return BIB_ENGINE_OK; // Locals, VM lock, then Bridge guard destruct normally.
}

int32_t bibProviderStep(uint32_t render)
{
    if (!providerOnOwner())
        return BIB_ENGINE_WRONG_THREAD;
    if (providerUiFaulted())
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    if (!g_providerReady || !g_engine)
        return BIB_ENGINE_CLOSED;
    if (render > 1 || (render && !g_providerRaster))
        return BIB_ENGINE_INVALID;
    FoundationServiceEngineCall bridgeTurn;
    if (!bridgeTurn)
        return BIB_ENGINE_REENTRANT;
    JSC::JSLockHolder lock(WebCore::commonVM());
    WTF::RunLoop::cycle();
    // Application rAF/style/observer work is independent of raster publication.
    if (g_renderingUpdateRequested) {
        g_renderingUpdateRequested = false;
        g_engine->page->updateRendering();
        g_engine->page->finalizeRenderingUpdate({ });
    }
    if (RefPtr document = g_engine->mainFrame->document())
        document->updateLayoutIgnorePendingStylesheets();
#if BIB_ENGINE_PROVIDER_DOCUMENT_V2
    BIB::EnginePopup::reconcile();
    if (providerUiFaulted())
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
#endif
    // The initial queue/Document transition may be asynchronous. A pending
    // status needs a later owner turn, never a nested RunLoop startup probe.
    // The owner applies its bounded deadline if readiness never arrives.
    if (bibProviderInitialLoadStatus() < 0)
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
#if BIB_ENGINE_PROVIDER_DOCUMENT_V2
    // Owner-only metadata is drained before any damage publication. It does
    // not require leaving the already admitted Bridge/common-VM turn.
    const bool uiWakeBeforeCapture = EngineUI::takeWakeRequest();
    if (uiWakeBeforeCapture)
        g_providerHost.wake(g_providerHost.context);
    if (providerUiFaulted())
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
#endif
    const auto result = render ? providerPublishDamageLocked() : BIB_ENGINE_OK;
    if (result)
        return result; // A fatal rendering result permits no later callbacks.
    providerMaybePersist();
    if (providerUiFaulted())
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    // A page rAF callback can request its successor without arming a WebCore
    // timer: ChromeClient owns rendering-update scheduling in this port.
    if (g_renderingUpdateRequested)
        g_providerHost.wake(g_providerHost.context);
    return providerUiFaulted() ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : result;
}


#if BIB_ENGINE_PROVIDER_DOCUMENT_V2
// NEW explicit document 1795/2003 raster source proposal. Both typed document
// bindings select this helper because bitmap native-effect release needs a
// fresh actual frame even for 1795/no-port observation. DOCUMENT_V2 alone adds
// no input capability. Ordinary Step for 259/467 and checkpoint remain unchanged.
int32_t bibProviderDocumentAdvance(uint32_t render)
{
    if (!providerOnOwner())
        return BIB_ENGINE_WRONG_THREAD;
    if (providerUiFaulted())
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    if (!g_providerReady || !g_engine)
        return BIB_ENGINE_CLOSED;
    if (render > 1 || (render && !g_providerRaster))
        return BIB_ENGINE_INVALID;
    if (!render)
        return bibProviderStep(0); // Ordinary run-loop progress, no fresh frame.

    FoundationServiceEngineCall bridgeTurn;
    if (!bridgeTurn)
        return BIB_ENGINE_REENTRANT;
    JSC::JSLockHolder lock(WebCore::commonVM());
    WTF::RunLoop::cycle();
    if (g_renderingUpdateRequested) {
        g_renderingUpdateRequested = false;
        g_engine->page->updateRendering();
        g_engine->page->finalizeRenderingUpdate({ });
    }
    if (RefPtr document = g_engine->mainFrame->document())
        document->updateLayoutIgnorePendingStylesheets();
#if BIB_ENGINE_PROVIDER_DOCUMENT_V2
    BIB::EnginePopup::reconcile();
    if (providerUiFaulted())
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
#endif
    if (bibProviderInitialLoadStatus() < 0)
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;

    // Optional persistence/scheduling callbacks precede the final damage
    // callback. There is no damage acknowledgement primitive. The real copied
    // Host terminates on a failed commit; a native Host must independently
    // propagate its sticky failure when the complete outer call returns.
    providerMaybePersist();
    if (providerUiFaulted())
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    const bool uiWakeBeforeCapture = EngineUI::takeWakeRequest();
    const bool wakeBeforeCapture = g_renderingUpdateRequested || uiWakeBeforeCapture;
    if (wakeBeforeCapture)
        g_providerHost.wake(g_providerHost.context);
    if (providerUiFaulted())
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;

    RefPtr page = g_engine->page;
    RefPtr frame = g_engine->mainFrame;
    auto surface = g_engine->surface;
    if (!page || !frame || !surface || page->localMainFrame() != frame.get())
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    RefPtr document = frame->document();
    RefPtr view = frame->view();
    BibAppDocumentIdentityV1 identity { };
    // A genuine initial/pending authority has no app frame to publish. OK here
    // means progress only, never evidence of a fresh frame or permission to
    // rearm. The outer Owner frame remains absent/old until actual commit.
    if (!document || !view || !providerDocumentFence(*frame, *document, identity))
        return BIB_ENGINE_OK;
    if (g_providerFrameRevision == std::numeric_limits<uint64_t>::max())
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    auto sameCapture = [&] {
        return g_engine && g_engine->page.get() == page.get()
            && g_engine->mainFrame.get() == frame.get()
            && g_engine->surface.get() == surface.get()
            && frame->view() == view.get()
            && providerDocumentFenceMatches(*frame, *document,
                identity.application_instance, identity.document_sequence,
                identity.service_generation, identity.resource_epoch);
    };
    if (!sameCapture() || document->needsStyleRecalc() || view->needsLayout()
        || view->layoutContext().isInLayout())
        return BIB_ENGINE_OK; // No capture; never return retained pixels as new.

    const WebCore::IntRect frameRect(0, 0, kWidth, kHeight);
    // This is an explicit complete paint, not a fabricated dirty notification.
    // Snapshot-and-clear BEFORE paint retains paint-triggered invalidations for
    // the next owner step and preserves the existing scroll-buffer convention.
    clearDamage();
    if (!paintFrameRect(frameRect))
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    auto info = SkImageInfo::Make(kWidth, kHeight, kRGBA_8888_SkColorType, kUnpremul_SkAlphaType);
    if (!surface->readPixels(SkPixmap(info, g_blitPixels, kWidth * 4), 0, 0))
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    if (!sameCapture())
        return BIB_ENGINE_OK; // Navigation/resource movement invalidates capture.
    for (size_t i = 3; i < kFrameBytes; i += 4) {
        if (g_blitPixels[i] != 255)
            return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    }
    std::memcpy(g_providerDamage.data(), g_blitPixels, kFrameBytes);
    // Painting may have requested its next rendering update. Schedule it before
    // the final damage callback, without an unconditional self-waking frame loop.
    const bool uiWakeAfterPaint = EngineUI::takeWakeRequest();
    if ((g_renderingUpdateRequested || uiWakeAfterPaint) && !wakeBeforeCapture)
        g_providerHost.wake(g_providerHost.context);
    if (providerUiFaulted())
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    if (!sameCapture())
        return BIB_ENGINE_OK;

    const BibEngineDocumentV1 capturedDocument { identity.application_instance,
        identity.document_sequence, identity.service_generation };
    // A frame revision identifies this completed real paint+readback+owned copy.
    // It is independent of semantic publication revisions and pixel equality;
    // there is no revision advance on the no-frame/failure paths above.
    const auto revision = g_providerFrameRevision + 1;
    BibEngineDamageV1 damage { sizeof(BibEngineDamageV1), 1, capturedDocument,
        revision, 0, 0, kWidth, kHeight, kWidth * 4,
        static_cast<uint32_t>(kFrameBytes), g_providerDamage.data() };
    g_providerFrameRevision = revision;
    g_providerHost.damage(g_providerHost.context, &damage);
    g_providerPublishedDocument = capturedDocument;
    g_providerFirstFrame = false;
    // No later optional Host callback. JSLock then Bridge unwind naturally
    // inside the unchanged outer ProviderGuard turn; there is no cleanup export.
    return providerUiFaulted() ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : BIB_ENGINE_OK;
}
#endif

int32_t bibProviderPublishDamage()
{
    if (!providerOnOwner())
        return BIB_ENGINE_WRONG_THREAD;
    if (providerUiFaulted())
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    if (!g_providerReady || !g_engine)
        return BIB_ENGINE_CLOSED;
    FoundationServiceEngineCall bridgeTurn;
    if (!bridgeTurn)
        return BIB_ENGINE_REENTRANT;
    JSC::JSLockHolder lock(WebCore::commonVM());
    const auto result = providerPublishDamageLocked();
    return providerUiFaulted() ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : result;
}
} // namespace BIB

