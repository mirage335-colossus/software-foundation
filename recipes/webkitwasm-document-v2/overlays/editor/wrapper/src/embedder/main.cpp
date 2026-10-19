// Private source-only provider runtime extraction. Unparsed against WebCore.
// Frozen combined main preimage: ad3f96ed082e2ad227103572f16ab8460aa140642707ce5e8fc3749b0a1fd795.
#if defined(BIB_ENGINE_PROVIDER_NEUTRAL) && BIB_ENGINE_PROVIDER_NEUTRAL
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

#if !defined(__EMSCRIPTEN__) || defined(__EMSCRIPTEN_PTHREADS__)
#error "Provider runtime supports only the reviewed non-pthread Emscripten CPU profile"
#endif
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

#else // Original diagnostic embedder, unchanged frozen preimage follows.
// BrowserInBrowser embedder.
// Builds a WebCore::Page against internal headers (no public embedding API
// exists outside Cocoa — decision-001), loads a fixed HTML string, lays it
// out, and paints through a Skia raster surface.
//
// Two modes, decided at runtime by Module.bibInteractive:
//  - gate mode (node, tools/run-embedder.cjs): one paint → PPM dump in the
//    wasm FS + region-pixel assertions → exit. The Phase 2 gate, unchanged.
//  - interactive mode (browser host page, web/browser.html): main() sets the
//    page up, signals Module.onEngineReady, then keeps the runtime alive.
//    The host drives bib_tick()/bib_render() from requestAnimationFrame and
//    blits the returned RGBA buffer to a <canvas> via putImageData.
//
// Construction sequence is cribbed from SVGImage::dataChanged() — the one
// in-tree user of pageConfigurationWithEmptyClients() that paints.

#include "config.h"

#include "BibIDBServer.h"
#include "BibMediaPlayer.h" // g_mediaEnabled boot flag
#include "BibPageClients.h"
#include "BibFoundationServiceBridge.h"
#include "BibSocketProvider.h"
#include "BibAppResources.h"
#include "BibStorage.h"
#include "CommonAtomStrings.h"
#include "CookieJar.h"
#include "CurlContext.h"
#include "CurlRequestScheduler.h" // bib_pump_network -> scheduler().hostPump()
#include "Document.h"
#include "DocumentLoader.h"
#include "DocumentView.h" // inline LocalFrame::view() lives here, not in LocalFrame.h
#include "DocumentWriter.h"
#include "EmptyClients.h"
#include "EventHandler.h"
#include "FocusController.h"
#include "FrameLoadRequest.h"
#include "FrameLoader.h"
#include "GLContext.h" // presentGPU: makeContextCurrent on the shared display's context
#include "GraphicsContextSkia.h"
#include "HandleUserInputEventResult.h"
#include "LocalFrame.h"
#include "LocalFrameInlines.h"
#include "LocalFrameView.h"
#include "MemoryCache.h"
#include "CommonVM.h" // #77/OOM probe: commonVM().heap.size() for the JS-heap gauge
#include "NetworkStorageSession.h" // persistence: cookieDatabase() dump/seed
#include "Page.h"
#include "PageConfiguration.h"
#include "PlatformDisplay.h"
#include "PlatformDisplayEmscripten.h"
#include "PlatformKeyboardEvent.h"
#include "PlatformMouseEvent.h"
#include "PlatformWheelEvent.h"
#include "RenderTreeAsText.h"
#include "ResourceRequest.h"
#include "ScriptController.h"
#include "ScrollAnimator.h"
#include "ScrollingCoordinatorTypes.h" // WheelEventProcessingSteps
#include "SecurityContext.h"
#include "Settings.h"
#include "SharedBuffer.h"
#include "StorageSessionProvider.h"
#include "DOMWrapperWorld.h"
#include "JSDOMGlobalObject.h"
#include <JavaScriptCore/InitializeThreading.h>
#include <JavaScriptCore/JSCInlines.h>
#include <JavaScriptCore/JSFunction.h>
#include <atomic>
#include <emscripten.h>
#include <emscripten/heap.h> // emscripten_get_heap_size(): total wasm linear memory (4GB ceiling gauge)
#ifdef __EMSCRIPTEN_PTHREADS__
#include <emscripten/proxying.h>
#endif
#include <emscripten/threading.h>
#include <pal/SessionID.h>
#include <wtf/JSONValues.h>
#include <wtf/MainThread.h>
#include <wtf/Assertions.h> // WTFLogAlways — perf-log breakdown from the engine thread
#include <wtf/MonotonicTime.h>
#include <wtf/NeverDestroyed.h>
#include <wtf/ProcessPrivilege.h>
#include <wtf/RunLoop.h>
#include <wtf/WallTime.h>

WTF_IGNORE_WARNINGS_IN_THIRD_PARTY_CODE_BEGIN
#include <skia/core/SkCanvas.h>
#include <skia/core/SkImageInfo.h>
#include <skia/core/SkPixmap.h>
#include <skia/core/SkSurface.h>
#include <skia/gpu/ganesh/GrBackendSurface.h>
#include <skia/gpu/ganesh/GrDirectContext.h>
#include <skia/gpu/ganesh/SkSurfaceGanesh.h>
#include <skia/gpu/ganesh/gl/GrGLBackendSurface.h>
WTF_IGNORE_WARNINGS_IN_THIRD_PARTY_CODE_END

#include <cstdio>
#include <cstdlib>
#include <utility> // std::exchange

#if BIB_FOUNDATION_SERVICES
extern "C" int bib_foundation_service_candidate_initialize() noexcept;
extern "C" uint32_t bib_foundation_service_candidate_owner_turn() noexcept;
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

#ifdef __EMSCRIPTEN_PTHREADS__
// W-B2: runtime-decided OffscreenCanvas transfer for the proxied-main
// (engine) thread. crt1_proxy_main marks its pthread_create with a
// (char*)-1 sentinel meaning "use the -sOFFSCREENCANVASES_TO_PTHREAD link
// list". We deliberately don't link that list: it is compile-time-fixed
// and a canvas missing at spawn fails pthread_create outright — node gates
// have no DOM at all, and raster mode must keep #screen page-owned for its
// 2d context. Intercept the sentinel (-Wl,--wrap=pthread_create,
// embedder.cmake) and substitute the real decision: transfer #screen only
// when the page committed to GPU mode. This also keeps the sentinel away
// from UTF8ToString((char*)-1), which the stock JS would otherwise hit
// with no link list configured.
//
// Runs on the SPAWNING thread — the page main thread for proxied main, so
// EM_ASM reads the page Module directly (node: bibGPU undefined → no
// transfer). All other pthread_creates (thread pool, WTF threads) carry a
// null/zero canvas list and pass through untouched.
extern "C" int __real_pthread_create(pthread_t*, const pthread_attr_t*, void* (*)(void*), void*);
extern "C" int __wrap_pthread_create(pthread_t* thread, const pthread_attr_t* attr, void* (*startRoutine)(void*), void* arg)
{
    if (attr) {
        const char* canvases = nullptr;
        emscripten_pthread_attr_gettransferredcanvases(attr, &canvases);
        if (canvases == reinterpret_cast<const char*>(-1)) {
            // W-B2 v2 (commit-starvation fix): NEVER transfer #screen. The old
            // path transferred #screen to this engine thread as an
            // OffscreenCanvas and presented through its placeholder — but the
            // placeholder commit is starved under PROXY_TO_PTHREAD (engine
            // paints ~47fps, screen saw ~0.2fps). GPU now renders into a
            // worker-PRIVATE OffscreenCanvas (registered as "#bibgpu" at GPU
            // boot) and delivers frames to the host #screen via the SAME
            // readback+putImageData path raster uses (host owns #screen's 2d
            // context). So the transfer list is always empty; the sentinel is
            // just neutralized (keeps it away from UTF8ToString((char*)-1)).
            pthread_attr_t patched = *attr;
            emscripten_pthread_attr_settransferredcanvases(&patched, "");
            return __real_pthread_create(thread, &patched, startRoutine, arg);
        }
    }
    return __real_pthread_create(thread, attr, startRoutine, arg);
}
#endif

static constexpr int kWidth = 800;
static constexpr int kHeight = 600;

static const char* kTestHTML =
    "<!DOCTYPE html>"
    "<html><head><title>gate</title></head>"
    "<body style='background:#ffffff; margin:0'>"
    "<h1 style='color:#cc0000; font-size:48px; margin:20px'>hello</h1>"
    "<div style='width:200px; height:100px; background:#0066cc'></div>"
    "</body></html>";

// Engine state outlives main() in interactive mode. Intentionally leaked:
// destruction order of WebCore globals at process exit is not a supported
// path in this embedder, and in gate mode the process exits anyway.
struct Engine {
    RefPtr<WebCore::Page> page;
    RefPtr<WebCore::LocalFrame> mainFrame;
    sk_sp<SkSurface> surface;
};
static Engine* g_engine;

// The main frame's CURRENT view. Never cache a LocalFrameView: every
// committed navigation replaces it (BibFrameLoaderClient::
// transitionToCommittedForNewPage), so a stored pointer would be the boot
// view forever — painting a detached view renders nothing.
static WebCore::LocalFrameView* mainFrameView()
{
    return g_engine ? g_engine->mainFrame->view() : nullptr;
}

// bib_render() hands this buffer to JS. Unpremultiplied RGBA as ImageData
// expects; for this engine's output (opaque pixels) conversion is identity.
static uint8_t g_blitPixels[kWidth * kHeight * 4];

// Skia GPU (decision-005 G2, opt-in via Module.bibGPU): the backing
// SkSurface in g_engine becomes a Ganesh TEXTURE target, paints stay
// dirty-rect-clipped, and presenting = drawing the backing texture onto a
// wrap of the canvas WebGL2 context's framebuffer 0 (GPU-GPU quad). The
// host page never sees pixels: bib_render returns null and the canvas is
// live. When the flag is unset every byte of the CPU path is unchanged.
static bool g_gpu = false;
static sk_sp<SkSurface> g_fbo0Surface; // present target, GPU mode only
// G4 (W-B2): set by the webglcontextlost handler, cleared after the Ganesh
// world is rebuilt on restore. Atomic: read by bib_render on the engine
// thread, written by canvas event handlers (same thread under pthreads —
// the OffscreenCanvas lives with the engine — but atomic keeps the
// single-threaded build's main-thread handlers honest too).
static std::atomic<bool> g_gpuLost { false };

// ?perflog=1 (read once in main, host-page URL): accumulate per-phase
// engine-thread timing and WTFLogAlways a one-line breakdown once a second.
// The whole point of this investigation is to stop GUESSING whether Discord's
// near-frozen render is a spin loop, heavy guest JS, layout, paint, or GPU
// present — this measures it. Off by default; when off it costs a handful of
// branch checks per tick. All fields are engine-thread-only (no atomics
// needed — bib_tick/bib_render run on the engine thread).
static bool g_perfLog = false;
// Rendering-update throttle. On JS-saturated pages WebCore's "update the
// rendering" pass (guest rAF/React callbacks + the style/layout they dirty)
// eats most of the engine thread (measured: 700-890ms/s on Discord) and starves
// paint -> freeze. We cap how often that pass runs. DYNAMIC by default: the cap
// is DERIVED from the measured per-pass cost (EMA) so the pass takes at most
// kRcapUpdateBudget of the thread -> heavy pages throttle (Discord ~8ms/pass ->
// ~31/s), light pages run full rate (~1ms/pass -> ~250/s = uncapped). No
// hardcoded fps. ?rcap=0 disables; ?rcap=N forces a fixed N/s (manual override).
// Deferred, not dropped: g_renderingUpdateRequested stays set until an eligible
// tick runs it.
static bool   g_rcapDynamic   = false;  // dynamic cap (default when interactive)
static double g_rcapFixedMs   = 0.0;    // >0 = fixed min-interval (manual override)
static double g_dynUpdEmaMs   = 0.0;    // EMA of updateRendering cost (ms)
static double g_dynIntervalMs = 0.0;    // derived min-interval (ms); ~0 = uncapped
static double g_lastRenderUpdateMs = 0.0;
static constexpr double kRcapUpdateBudget   = 0.33;  // updateRendering's max thread share
                                                     // (~1/3; leaves 2/3 for paint+timers.
                                                     // higher = more updates/fps, less paint
                                                     // headroom. 0.33 targets ~30/s on Discord
                                                     // where throttled passes batch to ~10ms.)
static constexpr double kRcapMaxIntervalMs  = 33.0;  // 30/s floor: never throttle below the
                                                     // empirically-good rate (rcap=30 beat 20).
                                                     // bounds the cost-inflation feedback so the
                                                     // dynamic cap floats 30-60/s, not down to a
                                                     // choppy crawl. (timer/microtask JS in
                                                     // bib_pump is a separate, un-throttled load.)
static constexpr double kRcapEmaAlpha       = 0.2;   // EMA weight for new cost samples
namespace {
struct PerfAccum {
    double windowStart = 0;  // MonotonicTime ms at window open (0 = not yet)
    double runloop = 0;      // RunLoop::cycle — guest JS, timers, microtasks
    double renderUpdate = 0; // updateRendering + finalizeRenderingUpdate (rAF/style/IO)
    double layout = 0;       // updateLayoutIgnorePendingStylesheets
    double paint = 0;        // paintFrameRect loop + CPU readback
    double present = 0;      // presentGPU (GPU mode only)
    double pushTotal = 0;    // whole bibPushFrameIfDirty (render + memcpy + dispatch)
    double persist = 0;      // bibMaybePersist
    int ticks = 0;           // bib_tick bodies run this window
    int painted = 0;         // frames that actually painted >=1 rect
    // #77 burst-shape probe: bib_pump / bib_pump_network RunLoop::cycle costs.
    // These run OUTSIDE bib_tick (no paint), so their total ~= the page-side
    // "pumpGap". max/count tell us the SHAPE: one giant cycle (max~=total ->
    // pacing between pumps useless, need mid-cycle break) vs many small cycles
    // (max<<total -> interleaving a paint per N pumps works).
    double pumpCycle = 0;    // sum of bib_pump RunLoop::cycle ms
    double pumpMax = 0;      // largest single bib_pump cycle ms (the decider)
    int pumps = 0;           // bib_pump cycles this window
    double netCycle = 0;     // sum of bib_pump_network (hostPump+cycle) ms
    double netMax = 0;       // largest single net cycle ms
    int nets = 0;            // bib_pump_network cycles this window
};
PerfAccum g_perf;
}
static inline double bibNowMs() { return MonotonicTime::now().secondsSinceEpoch().milliseconds(); }

// W-B2 v2: there is no presentGPU() anymore. GPU frames are NOT presented
// through the (starved) OffscreenCanvas placeholder; instead bib_render reads
// the painted Ganesh surface back to CPU and the host puts it on #screen via
// Module.bibBlit (same path as raster). g_fbo0Surface is retained only for the
// boot software-detection bench (it draws+flushes there directly).

// Dump RGBA pixels as a binary PPM (P6, alpha dropped) into the wasm FS.
// The node runner extracts it afterwards.
static bool writePPM(const char* path, const SkPixmap& pixmap)
{
    FILE* f = fopen(path, "wb");
    if (!f)
        return false;
    bool ok = fprintf(f, "P6\n%d %d\n255\n", pixmap.width(), pixmap.height()) > 0;
    for (int y = 0; ok && y < pixmap.height(); ++y) {
        const uint8_t* row = static_cast<const uint8_t*>(pixmap.addr(0, y));
        for (int x = 0; x < pixmap.width(); ++x) {
            // kRGBA_8888 byte order is R,G,B,A regardless of endianness.
            if (fwrite(row + x * 4, 1, 3, f) != 3) {
                ok = false;
                break;
            }
        }
    }
    ok = ok && !ferror(f);
    if (fclose(f) != 0)
        ok = false;
    return ok;
}

// True while view->paint runs (paintFrameRect). A scroll callback arriving
// MID-PAINT would shift pixels under the painter and slip past the frame's
// snapshotted upload box — bibScrollBlit falls back to plain damage instead
// (Codex hypothesis, 2026-06-11).
static bool g_inPaint = false;

// Paint ONLY `dirty` (root-view coords, pre-clamped to the frame, layout
// already up to date — see bib_render) into the persistent surface. Pixels
// outside the clip keep the previous frame's content; g_blitPixels mirrors
// the surface the same way via partial readbacks, so the two stay in sync.
// drawColor, NOT clear(): SkCanvas::clear ignores the clip.
static bool paintFrameRect(const WebCore::IntRect& dirty)
{
    RefPtr view = mainFrameView();
    if (!view)
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
    g_inPaint = false;
    canvas->restore();
    return true;
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

// Layout + paint the FULL frame (boot/gate path; bib_render drives the
// dirty-rect path itself so it can snapshot damage after layout).
static bool paintFrame()
{
    if (!mainFrameView())
        return false;
    g_engine->mainFrame->protectedDocument()->updateLayoutIgnorePendingStylesheets();
    clearDamage();
    return paintFrameRect(WebCore::IntRect(0, 0, kWidth, kHeight));
}

static OptionSet<WebCore::PlatformEvent::Modifier> modifiersFromBits(int bits)
{
    OptionSet<WebCore::PlatformEvent::Modifier> modifiers;
    if (bits & 1)
        modifiers.add(WebCore::PlatformEvent::Modifier::ShiftKey);
    if (bits & 2)
        modifiers.add(WebCore::PlatformEvent::Modifier::ControlKey);
    if (bits & 4)
        modifiers.add(WebCore::PlatformEvent::Modifier::AltKey);
    if (bits & 8)
        modifiers.add(WebCore::PlatformEvent::Modifier::MetaKey);
    return modifiers;
}

// ---------------------------------------------------------------------------
// W-B1 cross-thread entry marshaling. Under -sPROXY_TO_PTHREAD, main() (and
// all of WebCore/JSC) runs on a dedicated pthread, but the host page still
// calls the bib_* exports from the BROWSER MAIN THREAD — a direct call there
// would race the engine. Every export below self-proxies: called on the
// wrong thread, it queues itself onto the engine thread via the emscripten
// system proxying queue (processed whenever the engine pthread returns to
// its event loop — which the event-driven pump guarantees) and returns.
// High-frequency cadence entries (tick/pump) collapse bursts through an
// atomic pending flag so a pegged engine never accumulates a task backlog.

static pthread_t g_engineThread;
static std::atomic<bool> g_engineThreadReady { false };

static bool bibOnEngineThread()
{
    return g_engineThreadReady.load(std::memory_order_acquire)
        && pthread_equal(pthread_self(), g_engineThread);
}

// Queue a task onto the engine thread; drops silently pre-main() (matches
// the !g_engine early-outs every entry point already has).
// BIB_PTHREAD=OFF build: there is only one thread, so after main() runs
// every caller IS the engine thread (bibOnEngineThread() true — emscripten
// stubs pthread_self/pthread_equal) and this path is unreachable; before
// main() it returns false, matching the pthread build's pre-ready drop.
static bool bibProxyToEngine(void (*task)(void*), void* arg)
{
#ifdef __EMSCRIPTEN_PTHREADS__
    if (!g_engineThreadReady.load(std::memory_order_acquire))
        return false;
    return emscripten_proxy_async(emscripten_proxy_get_system_queue(), g_engineThread, task, arg);
#else
    (void)task;
    (void)arg;
    return false;
#endif
}

// Shared with BibMediaPlayer.cpp's bib_media_event export (BibMediaPlayer.h).
namespace BIB {
bool onEngineThread() { return bibOnEngineThread(); }
bool proxyToEngine(void (*task)(void*), void* arg) { return bibProxyToEngine(task, arg); }
}

// ---------------------------------------------------------------------------
// Engine-state persistence: cookies + guest localStorage round-trip through
// the host page's OPFS (web/browser.html). Seed: main() reads
// Module.bibSeedState (one JSON blob) before the first load — cookies go
// straight into the CookieJarDB, localStorage waits in
// bibPendingStorageImport() until each origin's area materializes
// (BibStorage.h). Dump: bib_tick re-serializes every ~5s and pushes to
// Module.bibPersist ONLY when the blob changed (string compare — there is
// no write hook on the cookie jar, so polling is the change detector).
// Everything here runs on the engine thread.

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

static void bibMaybePersist(bool force)
{
    static NeverDestroyed<String> lastJSON;
    static MonotonicTime lastCheck;
    static bool oversizeWarned = false;

    if (!g_engine)
        return;
    auto now = MonotonicTime::now();
    if (!force && now - lastCheck < Seconds(5))
        return;
    lastCheck = now;

    String json = bibBuildPersistJSON();
    if (json == lastJSON.get())
        return;
    CString utf8 = json.utf8();
    // localStorage quota (5MB/origin) keeps real blobs far below this; the
    // cap only guards the cross-heap string copy from pathological growth.
    if (utf8.length() > 12 * 1024 * 1024) {
        if (!std::exchange(oversizeWarned, true))
            printf("EMBEDDER: persist blob over 12MB — persistence paused\n");
        return;
    }
    lastJSON.get() = json;

    char* copy = static_cast<char*>(malloc(utf8.length() + 1));
    if (!copy)
        return;
    memcpy(copy, utf8.data(), utf8.length() + 1);
    // Same protocol as bibPushFrameIfDirty: malloc'd payload crosses to the
    // main thread, which reads it out of the (possibly grown) shared heap
    // and frees it via the exported _bib_wasm_free.
    // Module guard: pagehide nulls window.Module while a queued push may
    // still be in flight — free-then-drop is the correct outcome there.
    MAIN_THREAD_ASYNC_EM_ASM({
        if (typeof growMemViews === "function")
            growMemViews();
        var json = UTF8ToString($0);
        _bib_wasm_free($0);
        if (typeof Module !== "undefined" && Module && Module.bibPersist)
            Module.bibPersist(json);
    }, copy);
}

extern "C" {

#if BIB_FOUNDATION_SERVICES
// Scheduling entry, not an engine turn: call from an owner macrotask only
// after main()/tick/pump has completely returned. It never proxies optimism.
EMSCRIPTEN_KEEPALIVE uint32_t bib_foundation_service_pump_owner()
{
    if (!bibOnEngineThread())
        return 2; // ServiceStatus::unavailable
    return bib_foundation_service_candidate_owner_turn();
}
#endif

EMSCRIPTEN_KEEPALIVE int bib_frame_width() { return kWidth; }
EMSCRIPTEN_KEEPALIVE int bib_frame_height() { return kHeight; }

// W-B1 push-model rendering: defined after bib_render (which it drives).
static void bibPushFrameIfDirty();

// One non-blocking engine-RunLoop iteration: fires due WebCore timers and
// dispatched main-thread functions (DOM timers, RenderingUpdateScheduler's
// fallback timer, caret blink). Drive from requestAnimationFrame.
// (RunMode::Iterate never sleeps — RunLoopGeneric's Drain-only waitUntil.)
// W-B1: the host rAF still calls this for CADENCE, but the body runs on the
// engine thread; the frame (if any) is PUSHED back via Module.bibBlit.
static std::atomic<bool> g_tickQueued { false };
static void bibRunTick(void*);
EMSCRIPTEN_KEEPALIVE void bib_tick()
{
    if (!bibOnEngineThread()) {
        if (g_tickQueued.exchange(true, std::memory_order_acq_rel))
            return; // one tick already pending — collapse the burst
        if (!bibProxyToEngine(bibRunTick, nullptr))
            g_tickQueued.store(false, std::memory_order_release);
        return;
    }
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return;

    const double _perfT0 = g_perfLog ? bibNowMs() : 0;
    WTF::RunLoop::cycle();
    const double _perfT1 = g_perfLog ? bibNowMs() : 0;
    // Drive WebCore's "update the rendering" steps. This port has no
    // DisplayRefreshMonitor, so nothing else ever runs them — guest
    // requestAnimationFrame callbacks NEVER fired (root cause #16), which
    // silently stalled everything rAF-shaped: CSS/JS animations,
    // IntersectionObserver delivery, and rAF-deferred commits (react-helmet
    // batches <script> head insertions through rAF — 2captcha's reCAPTCHA
    // loader died exactly there). Gated on WebCore actually requesting an
    // update (BibChromeClient::scheduleRenderingUpdate sets the flag and
    // returns true, which also suppresses RenderingUpdateScheduler's
    // fallback timer): one pass per request, max one per host frame, zero
    // on idle pages.
    if (g_engine && BIB::g_renderingUpdateRequested) {
        // Throttle the rendering-update pass (see g_rcapDynamic). Interval is
        // fixed (manual ?rcap=N) or DERIVED from the EMA of the pass cost so it
        // stays <= kRcapUpdateBudget of the thread. Deferred, not dropped: the
        // flag stays set so a later eligible tick runs it. Uncapped (rcap=0 /
        // non-interactive): throttling=false -> equivalent to the old exchange().
        const bool throttling = g_rcapDynamic || g_rcapFixedMs > 0.0;
        bool runNow = true;
        double now = 0.0;
        if (throttling) {
            now = bibNowMs();
            const double interval = g_rcapFixedMs > 0.0 ? g_rcapFixedMs : g_dynIntervalMs;
            if (interval > 0.0 && now - g_lastRenderUpdateMs < interval)
                runNow = false;
        }
        if (runNow) {
            BIB::g_renderingUpdateRequested = false;
            g_engine->page->updateRendering();
            g_engine->page->finalizeRenderingUpdate({ });
            if (throttling) {
                g_lastRenderUpdateMs = now; // start-to-start spacing
                if (g_rcapDynamic) {
                    // Re-derive the cap from this pass's cost: keep
                    // updateRendering <= kRcapUpdateBudget of the thread.
                    const double cost = bibNowMs() - now;
                    g_dynUpdEmaMs = g_dynUpdEmaMs > 0.0
                        ? g_dynUpdEmaMs * (1.0 - kRcapEmaAlpha) + cost * kRcapEmaAlpha
                        : cost;
                    const double iv = g_dynUpdEmaMs / kRcapUpdateBudget;
                    g_dynIntervalMs = iv > kRcapMaxIntervalMs ? kRcapMaxIntervalMs : iv;
                }
            }
        }
    }
    const double _perfT2 = g_perfLog ? bibNowMs() : 0;
    bibPushFrameIfDirty(); // layout/paint/present accumulate inside bib_render
    const double _perfT3 = g_perfLog ? bibNowMs() : 0;
    bibMaybePersist(false);
    if (g_perfLog) {
        const double _perfT4 = bibNowMs();
        g_perf.runloop += _perfT1 - _perfT0;
        g_perf.renderUpdate += _perfT2 - _perfT1;
        g_perf.pushTotal += _perfT3 - _perfT2;
        g_perf.persist += _perfT4 - _perfT3;
        g_perf.ticks++;
        if (!g_perf.windowStart)
            g_perf.windowStart = _perfT0;
        const double elapsed = _perfT4 - g_perf.windowStart;
        if (elapsed >= 1000.0) {
            // pushOther = bibPushFrameIfDirty minus the painted phases =
            // dirty-rect bookkeeping + the malloc/memcpy/cross-thread dispatch.
            double pushOther = g_perf.pushTotal - g_perf.layout - g_perf.paint - g_perf.present;
            if (pushOther < 0)
                pushOther = 0;
            const double busy = g_perf.runloop + g_perf.renderUpdate + g_perf.layout
                + g_perf.paint + g_perf.present + g_perf.persist + pushOther;
            WTFLogAlways("BIBPERF/s ticks=%d painted=%d elapsed=%.0fms busy=%.0f%% heap=%.0fMB jsc=%.0fMB | "
                "runloop(JS)=%.0f renderUpd=%.0f layout=%.0f paint=%.0f present=%.0f pushOther=%.0f persist=%.0f ms | "
                "pump=%.0f(max%.0f n%d) net=%.0f(max%.0f n%d) | "
                "avgPaintedFrame=%.1fms",
                g_perf.ticks, g_perf.painted, elapsed, 100.0 * busy / elapsed,
                emscripten_get_heap_size() / 1048576.0, WebCore::commonVM().heap.size() / 1048576.0,
                g_perf.runloop, g_perf.renderUpdate, g_perf.layout, g_perf.paint,
                g_perf.present, pushOther, g_perf.persist,
                g_perf.pumpCycle, g_perf.pumpMax, g_perf.pumps,
                g_perf.netCycle, g_perf.netMax, g_perf.nets,
                g_perf.painted ? (g_perf.layout + g_perf.paint + g_perf.present) / g_perf.painted : 0.0);
            g_perf = PerfAccum { };
            g_perf.windowStart = _perfT4;
        }
    }
}
static void bibRunTick(void*)
{
    g_tickQueued.store(false, std::memory_order_release);
    bib_tick();
}

// One engine-RunLoop iteration WITHOUT the rendering-update steps. The
// wake-up plumbing (Module.bibWakeUp -> macrotask, Module.bibArmTimer ->
// setTimeout — WORKER-scope under W-B1, see web/engine-pre.js) calls this,
// so engine work runs at event-loop rate while rendering stays on
// bib_tick's rAF cadence.
static std::atomic<bool> g_pumpQueued { false };
static void bibRunPump(void*);
EMSCRIPTEN_KEEPALIVE void bib_pump()
{
    if (!bibOnEngineThread()) {
        if (g_pumpQueued.exchange(true, std::memory_order_acq_rel))
            return;
        if (!bibProxyToEngine(bibRunPump, nullptr))
            g_pumpQueued.store(false, std::memory_order_release);
        return;
    }
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return;

    if (!g_perfLog) {
        WTF::RunLoop::cycle();
        return;
    }
    const double t0 = bibNowMs();
    WTF::RunLoop::cycle();
    const double dt = bibNowMs() - t0;
    g_perf.pumpCycle += dt;
    if (dt > g_perf.pumpMax)
        g_perf.pumpMax = dt;
    g_perf.pumps++;
}
static void bibRunPump(void*)
{
    g_pumpQueued.store(false, std::memory_order_release);
    bib_pump();
}

// Socket-data poke: one curl multi pass right now (the wisp shim calls this
// when WebSocket bytes arrive — SOCKFS can't signal curl), then a RunLoop
// cycle so completions dispatched via callOnMainThread run immediately
// instead of waiting for the next wake-up. The wisp dispatcher lives on the
// browser main thread (W-B0: sockets proxy there), so this entry is ALWAYS
// cross-thread in browser mode.
static std::atomic<bool> g_netPumpQueued { false };
static void bibRunNetPump(void*);
EMSCRIPTEN_KEEPALIVE void bib_pump_network()
{
    if (!bibOnEngineThread()) {
        if (g_netPumpQueued.exchange(true, std::memory_order_acq_rel))
            return;
        if (!bibProxyToEngine(bibRunNetPump, nullptr))
            g_netPumpQueued.store(false, std::memory_order_release);
        return;
    }
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return;

    if (!g_perfLog) {
        WebCore::CurlContext::singleton().scheduler().hostPump();
        WTF::RunLoop::cycle();
        return;
    }
    const double t0 = bibNowMs();
    WebCore::CurlContext::singleton().scheduler().hostPump();
    WTF::RunLoop::cycle();
    const double dt = bibNowMs() - t0;
    g_perf.netCycle += dt;
    if (dt > g_perf.netMax)
        g_perf.netMax = dt;
    g_perf.nets++;
}
static void bibRunNetPump(void*)
{
    g_netPumpQueued.store(false, std::memory_order_release);
    bib_pump_network();
}

// The region bib_render last repainted, as {x, y, w, h} for the host's
// partial putImageData. force=1 and the first frame report the full frame.
static int g_dirtyBox[4] = { 0, 0, kWidth, kHeight };

EMSCRIPTEN_KEEPALIVE const int* bib_dirty_box() { return g_dirtyBox; }

// Returns the RGBA frame buffer (kWidth*kHeight*4) after repainting, or 0.
// force=0: only repaints (and returns the buffer) when the page is dirty —
//          the rAF blit loop skips putImageData on clean frames. Only the
//          accumulated damage union is painted + read back (bib_dirty_box);
//          the rest of g_blitPixels still holds the previous frame, which
//          is exactly what those pixels look like on the surface too.
// force=1: always repaints and returns the FULL frame (pixel probes that
//          sample anywhere in the buffer, first use).
EMSCRIPTEN_KEEPALIVE const uint8_t* bib_render(int force)
{
    // W-B1: engine-thread-only (driven by bib_tick's push; the host no
    // longer pulls frames). A stray main-thread caller gets nullptr.
    if (!bibOnEngineThread())
        return nullptr;
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return nullptr;

    if (!g_engine)
        return nullptr;
    // G4: while the WebGL context is lost the surfaces are dead/dropped —
    // skip BEFORE the damage snapshot below so nothing is wiped; damage
    // keeps accumulating and the restore path queues a full-frame repaint.
    if (g_gpu && g_gpuLost.load(std::memory_order_acquire))
        return nullptr;
    if (!force && !BIB::g_frameDirty && BIB::g_uploadRect.isEmpty())
        return nullptr;
    RefPtr view = mainFrameView();
    if (!view)
        return nullptr;
    // Layout BEFORE snapshotting the damage union — layout itself reports
    // damage through BibChromeClient, and it must land in THIS frame.
    const double _perfL0 = g_perfLog ? bibNowMs() : 0;
    g_engine->mainFrame->protectedDocument()->updateLayoutIgnorePendingStylesheets();
    const double _perfPaint0 = g_perfLog ? bibNowMs() : 0;
    if (g_perfLog)
        g_perf.layout += _perfPaint0 - _perfL0;
    const WebCore::IntRect frameRect(0, 0, kWidth, kHeight);
    // Two regions, two meanings: `dirty` = WebCore repaints + we read back;
    // `upload` = pixels bibScrollBlit already shifted in BOTH mirrors — the
    // host just re-uploads them, nothing repaints (a force frame is both).
    WebCore::IntRect dirty[BIB::kMaxDamageRects];
    size_t dirtyCount = 0;
    if (force)
        dirty[dirtyCount++] = frameRect;
    else {
        for (size_t i = 0; i < BIB::g_damageCount; ++i) {
            WebCore::IntRect r = WebCore::intersection(BIB::g_damageRects[i], frameRect);
            if (!r.isEmpty())
                dirty[dirtyCount++] = r;
        }
    }
    WebCore::IntRect upload = force ? WebCore::IntRect() : WebCore::intersection(BIB::g_uploadRect, frameRect);
    clearDamage(); // BEFORE paint — paint-time damage belongs to the next frame
    if (!dirtyCount && upload.isEmpty()) {
        // All damage was outside the viewport — nothing visible changed.
        return nullptr;
    }
    WebCore::IntRect paintedBounds;
    for (size_t i = 0; i < dirtyCount; ++i) {
        const WebCore::IntRect& r = dirty[i];
        bool painted = paintFrameRect(r);
        bool readBack = painted;
        // W-B2 v2: BOTH modes read the painted rect back into g_blitPixels and
        // deliver it to the host #screen via putImageData (bibPushFrameIfDirty
        // → Module.bibBlit). In GPU mode g_engine->surface is a Ganesh texture
        // surface, so readPixels is a GPU→CPU readback (~few ms) — the price of
        // not relying on the starved OffscreenCanvas placeholder commit. The
        // GPU win is the PAINT (Ganesh ~5ms vs CPU raster ~111ms/full frame);
        // readback delivery is the same proven path raster already uses.
        if (painted) {
            // GPU mode: paintFrameRect only RECORDS Ganesh commands; the GPU
            // hasn't executed them yet. readPixels would read stale/blank
            // pixels (the bug that made the screen look frozen while the engine
            // "painted" 60fps — 2026-06-13). Force the paint onto the GPU
            // before reading it back. Raster has no async GPU stage, so it
            // skips this. (The old presentGPU did this FlushAndSubmit; Approach
            // R dropped presentGPU, so the readback path must do it.)
            if (g_gpu)
                skgpu::ganesh::FlushAndSubmit(g_engine->surface.get());
            auto dstInfo = SkImageInfo::Make(r.width(), r.height(), kRGBA_8888_SkColorType, kUnpremul_SkAlphaType);
            uint8_t* dst = g_blitPixels + (static_cast<size_t>(r.y()) * kWidth + r.x()) * 4;
            readBack = g_engine->surface->readPixels(SkPixmap(dstInfo, dst, kWidth * 4), r.x(), r.y());
        }
        if (!painted || !readBack) {
            // Failed paint/readback: re-dirty THIS rect and every rect not
            // yet painted so the next frame retries instead of losing the
            // damage (Codex 2026-06-11). Re-arm the upload region too: it
            // was snapshot-cleared above. (A failed readback leaves the
            // surface newer than g_blitPixels until the retry lands.)
            for (size_t j = i; j < dirtyCount; ++j)
                BIB::addDamage(dirty[j]);
            BIB::g_uploadRect.unite(upload);
            // Rects painted BEFORE the failure are correct in both mirrors
            // but were never reported — without this the host canvas stays
            // stale there until unrelated damage covers it (Codex).
            BIB::g_uploadRect.unite(paintedBounds);
            return nullptr;
        }
        paintedBounds.unite(r);
    }
    if (g_perfLog) {
        g_perf.paint += bibNowMs() - _perfPaint0;
        g_perf.painted++;
    }
    WebCore::IntRect box = paintedBounds;
    box.unite(upload);
    g_dirtyBox[0] = box.x();
    g_dirtyBox[1] = box.y();
    g_dirtyBox[2] = box.width();
    g_dirtyBox[3] = box.height();
    // W-B2 v2: GPU mode no longer presents through the (starved) OffscreenCanvas
    // placeholder. Both modes now return g_blitPixels (filled by the readback
    // above) and the host puts it on #screen via Module.bibBlit. presentGPU()
    // and g_fbo0Surface are retained only for the boot software-detection
    // bench; they are not on the steady-state path.
    return g_blitPixels;
}

// --- GPU zero-copy present (decision: handoff-2026-06-13-gpu-present-rearchitecture) ---
// Steady-state GPU present no longer reads pixels back to CPU (Approach R was
// flaky/non-deterministic — a cross-thread readback race that left the screen
// near-frozen). Instead:
//   BIB_PTHREAD=ON  : paint dirty rects into the persistent texture surface →
//                     blit texture→FBO 0 → FlushAndSubmit → the worker-private
//                     OffscreenCanvas transferToImageBitmap → postMessage the
//                     ImageBitmap (zero-copy) to the page, which paints it onto
//                     #screen via a bitmaprenderer context.
//   BIB_PTHREAD=OFF : same paint + texture→FBO 0 blit, but FBO 0 IS #screen's
//                     own WebGL drawing buffer — the browser presents it
//                     implicitly when control returns to the event loop. This
//                     is the pre-W-B1 main-thread path (MotionMark 109@144fps).
// The texture surface stays the persistent dirty-rect backing store; FBO 0 is
// rewritten in full every present (it is undefined after composite with
// preserveDrawingBuffer off, so it cannot hold dirty-rect history).

// GPU paint primitive: layout, snapshot+clear damage, paint the dirty rects
// into g_engine->surface (the texture). Mirrors bib_render's damage handling
// but stops BEFORE any readback/present. force => full-frame repaint. Returns
// true iff it painted at least one rect (i.e. a present is warranted). In GPU
// mode g_scrollBlit is null, so g_uploadRect is never armed — no upload mirror.
static bool bibPaintGPUIfDirty(bool force)
{
    if (!g_engine || !g_engine->surface)
        return false;
    if (g_gpuLost.load(std::memory_order_acquire))
        return false;
    if (!force && !BIB::g_frameDirty)
        return false;
    RefPtr view = mainFrameView();
    if (!view)
        return false;

    const double _perfL0 = g_perfLog ? bibNowMs() : 0;
    g_engine->mainFrame->protectedDocument()->updateLayoutIgnorePendingStylesheets();
    const double _perfPaint0 = g_perfLog ? bibNowMs() : 0;
    if (g_perfLog)
        g_perf.layout += _perfPaint0 - _perfL0;

    const WebCore::IntRect frameRect(0, 0, kWidth, kHeight);
    WebCore::IntRect dirty[BIB::kMaxDamageRects];
    size_t dirtyCount = 0;
    if (force)
        dirty[dirtyCount++] = frameRect;
    else {
        for (size_t i = 0; i < BIB::g_damageCount; ++i) {
            WebCore::IntRect r = WebCore::intersection(BIB::g_damageRects[i], frameRect);
            if (!r.isEmpty())
                dirty[dirtyCount++] = r;
        }
    }
    clearDamage(); // BEFORE paint — paint-time damage belongs to the next frame
    if (!dirtyCount)
        return false; // all damage was outside the viewport

    for (size_t i = 0; i < dirtyCount; ++i) {
        if (!paintFrameRect(dirty[i])) {
            // Re-arm this rect + every unpainted one so the next frame retries.
            for (size_t j = i; j < dirtyCount; ++j)
                BIB::addDamage(dirty[j]);
            return false;
        }
    }
    if (g_perfLog) {
        g_perf.paint += bibNowMs() - _perfPaint0;
        g_perf.painted++;
    }
    return true;
}

// Blit the persistent texture surface into FBO 0 and flush. After this the
// canvas default framebuffer (the bibgpu OffscreenCanvas under pthreads, or
// #screen directly otherwise) holds the current frame, ready for
// transferToImageBitmap / implicit present. FBO 0 is cleared and fully
// redrawn every present (it has no stable history under preserveDrawingBuffer
// off — that's why the texture surface, not FBO 0, is the dirty-rect store).
static bool presentGPUToCanvasFBO()
{
    if (!g_gpu || !g_engine || !g_engine->surface || !g_fbo0Surface)
        return false;
    auto* glContext = WebCore::PlatformDisplay::sharedDisplay().skiaGLContext();
    if (!glContext || !glContext->makeContextCurrent())
        return false;
    const double _p0 = g_perfLog ? bibNowMs() : 0;
    SkCanvas* dst = g_fbo0Surface->getCanvas();
    dst->clear(SK_ColorWHITE);
    g_engine->surface->draw(dst, 0, 0);
    // paintFrameRect + draw() only ENQUEUE Ganesh work; force it onto the GPU
    // so the framebuffer is complete before transfer/implicit-present.
    skgpu::ganesh::FlushAndSubmit(g_fbo0Surface.get());
    if (g_perfLog)
        g_perf.present += bibNowMs() - _p0;
    return true;
}

#ifdef __EMSCRIPTEN_PTHREADS__
// One-in-flight backpressure gate: true iff the page has consumed the previous
// ImageBitmap. Checked BEFORE bibPaintGPUIfDirty (which clears damage) so a
// not-ready frame leaves damage armed and coalesces into the next deliverable.
static bool bibBitmapPresentReady()
{
    return EM_ASM_INT({
        return (Module.bibBitmapPresentReady && Module.bibBitmapPresentReady()) ? 1 : 0;
    });
}
// transferToImageBitmap the bibgpu OffscreenCanvas (FBO 0 contents) and post it
// to the page over the dedicated MessagePort. Must run AFTER presentGPUToCanvasFBO.
// Returns true only on a successful post (1); 0/-1/-2 mean not-ready/no-canvas/throw.
static bool bibTransferCurrentFrameBitmap()
{
    return EM_ASM_INT({
        return (Module.bibTransferCurrentFrame && Module.bibTransferCurrentFrame() === 1) ? 1 : 0;
    });
}
#endif

// W-B1 frame push: GPU presents zero-copy (pthread) or implicitly (mainthread);
// raster renders to CPU pixels, packs the dirty box into a tight malloc'd copy
// (decoupled from g_blitPixels reuse — the main thread consumes asynchronously),
// and hands it to the page. The raster receiving EM_ASM runs on the browser
// main thread in module scope: it copies the bytes OUT of the shared heap
// (ImageData rejects SAB-backed views), frees the transfer buffer (dlmalloc is
// thread-safe under -pthread), and calls Module.bibBlit. growMemViews() first —
// views go stale after a cross-thread memory grow (W-B0 finding).
static void bibPushFrameIfDirty()
{
    static bool firstFramePushed = false;

    if (g_gpu) {
        const bool force = !firstFramePushed;
#ifdef __EMSCRIPTEN_PTHREADS__
        // Zero-copy bitmap present. Backpressure FIRST: if the page hasn't
        // consumed the last ImageBitmap, do NOT paint — bibPaintGPUIfDirty
        // clears damage, so painting now would drop the frame. Leaving early
        // keeps damage armed; it coalesces into the next deliverable frame.
        if (!bibBitmapPresentReady())
            return;
        if (!bibPaintGPUIfDirty(force))
            return;
        if (!presentGPUToCanvasFBO()) {
            BIB::addDamage(WebCore::IntRect(0, 0, kWidth, kHeight));
            return;
        }
        if (!bibTransferCurrentFrameBitmap()) {
            // Port not wired yet (pre-handshake) or canvas missing — re-arm a
            // full repaint; the next ready tick retries. The ready gate above
            // means this is rare (transfer was green; the post itself failed).
            BIB::addDamage(WebCore::IntRect(0, 0, kWidth, kHeight));
            return;
        }
        firstFramePushed = true;
        return;
#else
        // BIB_PTHREAD=OFF: the engine owns #screen's WebGL2 context on the
        // browser main thread; the browser presents FBO 0 implicitly when this
        // call stack returns to the event loop (GLContext::swapBuffers is a
        // no-op). No transfer, no readback — the fast path.
        if (!bibPaintGPUIfDirty(force))
            return;
        if (!presentGPUToCanvasFBO()) {
            BIB::addDamage(WebCore::IntRect(0, 0, kWidth, kHeight));
            return;
        }
        firstFramePushed = true;
        return;
#endif
    }

    // Raster path — unchanged from the W-B1 readback-delivery model.
    const uint8_t* pixels = bib_render(firstFramePushed ? 0 : 1);
    if (!pixels)
        return;
    firstFramePushed = true;
    const int x = g_dirtyBox[0], y = g_dirtyBox[1], w = g_dirtyBox[2], h = g_dirtyBox[3];
    if (w <= 0 || h <= 0)
        return;
    uint8_t* copy = static_cast<uint8_t*>(malloc(static_cast<size_t>(w) * h * 4));
    if (!copy)
        return;
    for (int row = 0; row < h; ++row) {
        memcpy(copy + static_cast<size_t>(row) * w * 4,
            pixels + (static_cast<size_t>(y + row) * kWidth + x) * 4,
            static_cast<size_t>(w) * 4);
    }
    MAIN_THREAD_ASYNC_EM_ASM({
        if (typeof growMemViews === "function")
            growMemViews();
        var bytes = HEAPU8.slice($0, $0 + $3 * $4 * 4);
        _bib_wasm_free($0);
        if (Module.bibBlit)
            Module.bibBlit(bytes, $1, $2, $3, $4);
    }, copy, x, y, w, h);
}

// Probe/gate path ONLY (G3, decision-005): force a repaint and return CPU
// pixels in BOTH modes. CPU mode is bib_render(1) verbatim; GPU mode force-
// paints the persistent texture surface (the SAME primitive the present path
// uses) and reads IT back into g_blitPixels — a deliberate GPU sync that must
// never run per-frame (the steady render loop presents zero-copy, no readback).
// Independent of the bitmap present path: reads the texture, not FBO 0 (whose
// content is undefined after composite with preserveDrawingBuffer off), so it
// stays correct without the legacy offscreen-backbuffer preserve attributes.
EMSCRIPTEN_KEEPALIVE const uint8_t* bib_render_readback()
{
    if (!bibOnEngineThread())
        return nullptr;
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return nullptr;
 // W-B1: probes use bib_request_readback instead
    if (!g_gpu)
        return bib_render(1); // raster: unchanged
    if (!g_engine || !g_engine->surface)
        return nullptr;
    if (g_gpuLost.load(std::memory_order_acquire))
        return nullptr;
    // Full-frame repaint into the texture surface, then flush + read it back.
    if (!bibPaintGPUIfDirty(true))
        return nullptr;
    auto* glContext = WebCore::PlatformDisplay::sharedDisplay().skiaGLContext();
    if (!glContext || !glContext->makeContextCurrent())
        return nullptr;
    skgpu::ganesh::FlushAndSubmit(g_engine->surface.get());
    auto dstInfo = SkImageInfo::Make(kWidth, kHeight, kRGBA_8888_SkColorType, kUnpremul_SkAlphaType);
    if (!g_engine->surface->readPixels(SkPixmap(dstInfo, g_blitPixels, kWidth * 4), 0, 0))
        return nullptr;
    return g_blitPixels;
}

// W-B1 async probe readback: the page cannot pull pixels synchronously
// anymore (a blocking main->engine call risks deadlock against the
// engine's proxied syscalls). The page requests; the engine renders and
// pushes the FULL frame to Module.bibReadbackReady as a copied-out
// Uint8Array. Used by __bib.probe / gate harnesses.
static void bibRunReadback(void*)
{
    const uint8_t* pixels = bib_render_readback();
    uint8_t* copy = nullptr;
    const size_t bytes = static_cast<size_t>(kWidth) * kHeight * 4;
    if (pixels) {
        copy = static_cast<uint8_t*>(malloc(bytes));
        if (copy)
            memcpy(copy, pixels, bytes);
    }
    MAIN_THREAD_ASYNC_EM_ASM({
        var data = null;
        if ($0) {
            if (typeof growMemViews === "function")
                growMemViews();
            data = HEAPU8.slice($0, $0 + $1);
            _bib_wasm_free($0);
        }
        if (Module.bibReadbackReady)
            Module.bibReadbackReady(data, $2, $3);
    }, copy, bytes, kWidth, kHeight);
}
// Collapsed like bib_tick: harness predicates poll probe() every ~100ms —
// while the engine is pegged (Discord boot) the requests must not pile up
// as queued forced repaints. One pending readback serves every waiter
// (bibReadbackReady resolves them all with the same frame).
static std::atomic<bool> g_readbackQueued { false };
static void bibRunReadbackCollapsed(void*)
{
    g_readbackQueued.store(false, std::memory_order_release);
    bibRunReadback(nullptr);
}
EMSCRIPTEN_KEEPALIVE void bib_request_readback()
{
    if (!bibOnEngineThread()) {
        if (g_readbackQueued.exchange(true, std::memory_order_acq_rel))
            return;
        if (!bibProxyToEngine(bibRunReadbackCollapsed, nullptr))
            g_readbackQueued.store(false, std::memory_order_release);
        return;
    }
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return;

    bibRunReadback(nullptr);
}

// --- G4: in-place GPU context-loss recovery (W-B2) ----------------------
// The browser can revoke a WebGL context at any time (GPU reset, driver
// restart, resource pressure). G3 recovered by reloading the page; G4
// recovers IN PLACE: the lost handler preventDefault()s (required, or the
// browser never restores) and parks rendering (bib_render's g_gpuLost
// guard); the restored handler rebuilds the Ganesh world over the SAME
// context handle (WebGL restores the same context object, so the GLContext
// facades and the assembled proc table stay valid) and queues a full
// repaint. If restored never fires (some drivers won't), a deadline falls
// back to the G3 protocol: the page reloads (?gpulost=1, second loss
// ?gpu=0). Guest ImageBuffers from accelerated 2D canvases (?canvasgpu)
// are NOT rebuilt — accepted v1 gap, they re-create on guest redraw paths.

extern "C" void bibEnableAllWebGLExtensions(); // EM_JS, PlatformDisplayEmscripten.cpp

static void bibGpuRebuildAfterRestore()
{
    auto& display = WebCore::PlatformDisplay::sharedDisplay();
    // Restoration invalidated every previously enabled extension (WebGL
    // spec) — re-enable BEFORE Skia re-reads caps below, or shaders using
    // advertised extensions fail to compile again. Make the (restored)
    // context current first: the EM_JS helper reads GL.currentContext.
    emscripten_webgl_make_context_current(WebCore::emscriptenSkiaWebGLContext());
    bibEnableAllWebGLExtensions();
    // Documented teardown order for a lost context: abandon the GrContext
    // FIRST (destruction would otherwise drive dead GL), then drop the
    // surfaces that reference it.
    if (auto* grContext = display.skiaGrContext())
        grContext->abandonContext();
    g_fbo0Surface = nullptr;
    if (g_engine)
        g_engine->surface = nullptr;
    // Upstream hook (public wrapper over the private clearSkiaGLContext):
    // clears the thread-local SkiaGLContext; the next skiaGLContext() call
    // builds a fresh GrDirectContext over the restored WebGL handle via
    // GLContext::createOffscreen + the same proc table. Also nulls
    // m_sharingGLContext, which this port never creates — harmless.
    display.clearGLContexts();
    bool ok = display.skiaGLContext() && display.skiaGrContext();
    if (ok && g_engine) {
        // Same surface pair as the boot path in main(): texture-backed
        // store + FBO 0 present wrap (samples=1/stencil=8 match the
        // context attributes).
        auto info = SkImageInfo::Make(kWidth, kHeight, kRGBA_8888_SkColorType, kPremul_SkAlphaType);
        auto* grContext = display.skiaGrContext();
        g_engine->surface = SkSurfaces::RenderTarget(grContext, skgpu::Budgeted::kNo, info, 0, kTopLeft_GrSurfaceOrigin, nullptr);
        if (g_engine->surface) {
            GrGLFramebufferInfo fbInfo;
            fbInfo.fFBOID = 0;
            fbInfo.fFormat = 0x8058; // GL_RGBA8
            auto target = GrBackendRenderTargets::MakeGL(kWidth, kHeight, 1, 8, fbInfo);
            g_fbo0Surface = SkSurfaces::WrapBackendRenderTarget(grContext, target,
                kBottomLeft_GrSurfaceOrigin, kRGBA_8888_SkColorType, nullptr, nullptr);
        }
        ok = g_engine->surface && g_fbo0Surface;
    }
    if (!ok) {
        // Same split-brain hazard as a failed GPU boot: the host has no
        // blit path, so CPU raster would never reach the screen. Reload.
        printf("EMBEDDER: gpu restore REBUILD FAILED — host reload\n");
        MAIN_THREAD_ASYNC_EM_ASM({ if (Module.bibGpuLostReload) Module.bibGpuLostReload(); });
        return;
    }
    g_gpuLost.store(false, std::memory_order_release);
    printf("EMBEDDER: gpu context restored\n");
    // Everything on the old context is gone — full-frame repaint. The next
    // bib_tick's push renders it.
    BIB::addDamage(WebCore::IntRect(0, 0, kWidth, kHeight));
}

extern "C" {
// Called directly from the canvas event handlers below — they run on the
// thread that owns the canvas, which is the engine thread (pthread build:
// the OffscreenCanvas lives here; single-thread build: main IS the engine).
EMSCRIPTEN_KEEPALIVE void bib_gpu_context_lost()
{
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return;

    // No g_gpu guard: the handlers are installed right after context
    // creation, BEFORE the caps stage sets g_gpu (Codex MEDIUM) — a
    // mid-boot loss must still be flagged.
    g_gpuLost.store(true, std::memory_order_release);
    printf("EMBEDDER: gpu context LOST — awaiting restore\n");
}

EMSCRIPTEN_KEEPALIVE void bib_gpu_context_restored()
{
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return;

    if (!g_gpuLost.load(std::memory_order_acquire))
        return;
    if (!g_gpu) {
        // Lost+restored entirely within the boot window: nothing to
        // rebuild yet — boot either succeeded on the restored context or
        // failed into the host raster-reload fallback.
        g_gpuLost.store(false, std::memory_order_release);
        return;
    }
    bibGpuRebuildAfterRestore();
}

EMSCRIPTEN_KEEPALIVE void bib_gpu_restore_timed_out()
{
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return;

    if (!g_gpuLost.load(std::memory_order_acquire))
        return;
    printf("EMBEDDER: gpu restore TIMED OUT — host reload\n");
    MAIN_THREAD_ASYNC_EM_ASM({ if (Module.bibGpuLostReload) Module.bibGpuLostReload(); });
}
}

// Registered from main() after a successful GPU boot. W-B2 v2: the GL context
// is backed by the worker-private "#bibgpu" OffscreenCanvas (created at GPU
// boot, registered in GL.offscreenCanvases) — NOT #screen, which is no longer
// transferred. Attach the loss/restore listeners to that OffscreenCanvas (it
// is an EventTarget firing webglcontextlost/restored). The handlers run
// between engine tasks (worker/main event loop), never mid-paint, so calling
// the exports directly is safe.
static void installGpuContextLossHandlers()
{
#ifdef __EMSCRIPTEN_PTHREADS__
    // pthread build: the GL context is backed by the worker-private "#bibgpu"
    // OffscreenCanvas (it is an EventTarget firing webglcontextlost/restored).
    EM_ASM({
        var entry = typeof GL !== "undefined" && GL.offscreenCanvases && GL.offscreenCanvases["bibgpu"];
        var canvas = entry ? (entry.offscreenCanvas || entry.canvas) : null;
        if (!canvas) {
            out("EMBEDDER: gpu loss handlers NOT installed (no #bibgpu canvas)");
            return;
        }
        var deadline = null;
        canvas.addEventListener("webglcontextlost", function(e) {
            e.preventDefault(); // REQUIRED or the browser never restores
            _bib_gpu_context_lost();
            deadline = setTimeout(function() {
                deadline = null;
                _bib_gpu_restore_timed_out();
            }, 8000);
        });
        canvas.addEventListener("webglcontextrestored", function() {
            if (deadline) {
                clearTimeout(deadline);
                deadline = null;
            }
            _bib_gpu_context_restored();
        });
    });
#else
    // BIB_PTHREAD=OFF: the engine owns #screen's WebGL2 context directly on the
    // browser main thread, so loss/restore fire on the DOM canvas itself.
    EM_ASM({
        var canvas = document.getElementById("screen");
        if (!canvas) {
            out("EMBEDDER: gpu loss handlers NOT installed (no #screen)");
            return;
        }
        var deadline = null;
        canvas.addEventListener("webglcontextlost", function(e) {
            e.preventDefault(); // REQUIRED or the browser never restores
            _bib_gpu_context_lost();
            deadline = setTimeout(function() {
                deadline = null;
                _bib_gpu_restore_timed_out();
            }, 8000);
        });
        canvas.addEventListener("webglcontextrestored", function() {
            if (deadline) {
                clearTimeout(deadline);
                deadline = null;
            }
            _bib_gpu_context_restored();
        });
    });
#endif
}

// Test hook (gate8): lose the live context via WEBGL_lose_context, restore
// it 500ms later — exercises the full G4 path. Self-proxies like every
// page-callable export.
static void bibRunGpuTestLose(void*)
{
    if (!g_gpu || g_gpuLost.load(std::memory_order_acquire))
        return;
    auto* glContext = WebCore::PlatformDisplay::sharedDisplay().skiaGLContext();
    if (!glContext || !glContext->makeContextCurrent())
        return;
    EM_ASM({
        var ext = GL.currentContext && GL.currentContext.GLctx.getExtension("WEBGL_lose_context");
        if (!ext) {
            out("EMBEDDER: WEBGL_lose_context unavailable");
            return;
        }
        ext.loseContext();
        setTimeout(function() { ext.restoreContext(); }, 500);
    });
}

extern "C" EMSCRIPTEN_KEEPALIVE void bib_gpu_test_lose_restore()
{
    if (!bibOnEngineThread()) {
        bibProxyToEngine(bibRunGpuTestLose, nullptr);
        return;
    }
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return;

    bibRunGpuTestLose(nullptr);
}

// --- Input forwarding (canvas events -> WebCore EventHandler) ---
// W-B1: each entry self-proxies with a heap-copied argument pack; events
// run on the engine thread in arrival order (single FIFO proxy queue).

struct BibMouseMoveTask { double x; double y; int mods; };
static void bibRunMouseMove(void*);
EMSCRIPTEN_KEEPALIVE void bib_mouse_move(double x, double y, int modifierBits)
{
    if (!bibOnEngineThread()) {
        auto* task = new BibMouseMoveTask { x, y, modifierBits };
        if (!bibProxyToEngine(bibRunMouseMove, task))
            delete task; // pre-main: drop, matches !g_engine
        return;
    }
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return;

    if (!g_engine)
        return;
    WebCore::PlatformMouseEvent event({ x, y }, { x, y }, WebCore::MouseButton::None,
        WebCore::PlatformEvent::Type::MouseMoved, 0, modifiersFromBits(modifierBits),
        MonotonicTime::now(), 0, WebCore::SyntheticClickType::NoTap);
    g_engine->mainFrame->eventHandler().mouseMoved(event);
}
static void bibRunMouseMove(void* p)
{
    auto* t = static_cast<BibMouseMoveTask*>(p);
    bib_mouse_move(t->x, t->y, t->mods);
    delete t;
}

struct BibMouseButtonTask { int down; int jsButton; double x; double y; int clicks; int mods; };
static void bibRunMouseButton(void*);
EMSCRIPTEN_KEEPALIVE void bib_mouse_button(int down, int jsButton, double x, double y, int clickCount, int modifierBits)
{
    if (!bibOnEngineThread()) {
        auto* task = new BibMouseButtonTask { down, jsButton, x, y, clickCount, modifierBits };
        if (!bibProxyToEngine(bibRunMouseButton, task))
            delete task;
        return;
    }
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return;

    if (!g_engine)
        return;
    auto button = WebCore::MouseButton::Other;
    if (jsButton == 0)
        button = WebCore::MouseButton::Left;
    else if (jsButton == 1)
        button = WebCore::MouseButton::Middle;
    else if (jsButton == 2)
        button = WebCore::MouseButton::Right;
    WebCore::PlatformMouseEvent event({ x, y }, { x, y }, button,
        down ? WebCore::PlatformEvent::Type::MousePressed : WebCore::PlatformEvent::Type::MouseReleased,
        clickCount, modifiersFromBits(modifierBits), MonotonicTime::now(), 0,
        WebCore::SyntheticClickType::NoTap);
    if (down)
        g_engine->mainFrame->eventHandler().handleMousePressEvent(event);
    else
        g_engine->mainFrame->eventHandler().handleMouseReleaseEvent(event);
}
static void bibRunMouseButton(void* p)
{
    auto* t = static_cast<BibMouseButtonTask*>(p);
    bib_mouse_button(t->down, t->jsButton, t->x, t->y, t->clicks, t->mods);
    delete t;
}

struct BibWheelTask { double x; double y; double dx; double dy; int mods; };
static void bibRunWheel(void*);
EMSCRIPTEN_KEEPALIVE void bib_wheel(double x, double y, double deltaX, double deltaY, int modifierBits)
{
    if (!bibOnEngineThread()) {
        auto* task = new BibWheelTask { x, y, deltaX, deltaY, modifierBits };
        if (!bibProxyToEngine(bibRunWheel, task))
            delete task;
        return;
    }
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return;

    if (!g_engine)
        return;
    auto modifiers = modifiersFromBits(modifierBits);
    // DOM wheel deltas are positive-down; PlatformWheelEvent is positive-up.
    WebCore::PlatformWheelEvent event(WebCore::IntPoint(x, y), WebCore::IntPoint(x, y),
        -deltaX, -deltaY, -deltaX / 120.0f, -deltaY / 120.0f,
        WebCore::PlatformWheelEventGranularity::ScrollByPixelWheelEvent,
        modifiers.contains(WebCore::PlatformEvent::Modifier::ShiftKey),
        modifiers.contains(WebCore::PlatformEvent::Modifier::ControlKey),
        modifiers.contains(WebCore::PlatformEvent::Modifier::AltKey),
        modifiers.contains(WebCore::PlatformEvent::Modifier::MetaKey));
    g_engine->mainFrame->eventHandler().handleWheelEvent(event,
        { WebCore::WheelEventProcessingSteps::SynchronousScrolling, WebCore::WheelEventProcessingSteps::BlockingDOMEventDispatch });
}
static void bibRunWheel(void* p)
{
    auto* t = static_cast<BibWheelTask*>(p);
    bib_wheel(t->x, t->y, t->dx, t->dy, t->mods);
    delete t;
}

// Diagnostics: dump script/scroll state to stdout (host console).
static void bibRunDiag(void*);
EMSCRIPTEN_KEEPALIVE void bib_diag()
{
    if (!bibOnEngineThread()) {
        bibProxyToEngine(bibRunDiag, nullptr);
        return;
    }
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return;

    if (!g_engine)
        return;
    auto& frame = *g_engine->mainFrame;
    RefPtr doc = frame.document();
    printf("DIAG: scriptEnabledSetting=%d\n", frame.settings().isScriptEnabled());
    printf("DIAG: canExecuteScripts=%d\n", frame.script().canExecuteScripts(WebCore::ReasonForCallingCanExecuteScripts::NotAboutToExecuteScript));
    printf("DIAG: sandboxedScripts=%d\n", doc && doc->isSandboxed(WebCore::SandboxFlag::Scripts));
    printf("DIAG: docURL=%s\n", doc ? doc->url().string().utf8().data() : "(null)");
    if (RefPtr view = mainFrameView()) {
        auto contents = view->contentsSize();
        printf("DIAG: contentsSize=%dx%d scrollY=%d\n", contents.width(), contents.height(), view->scrollPosition().y());
        printf("DIAG: isScrollableOrRubberbandable=%d canHaveScrollbars=%d vScrollbar=%d scrollAnimatorEnabled=%d\n",
            view->isScrollableOrRubberbandable(),
            view->canHaveScrollbars(),
            !!view->verticalScrollbar(),
            frame.settings().scrollAnimatorEnabled());
    }
    auto result = frame.script().executeScriptIgnoringException("6*7"_s, JSC::SourceTaintedOrigin::Untainted);
    printf("DIAG: executeScript(6*7) isNumber=%d value=%d\n", result && result.isNumber(), result && result.isNumber() ? (int)result.asNumber() : -1);
}
static void bibRunDiag(void*) { bib_diag(); }

// Diagnostics: programmatic scroll, bypassing the wheel-event path.
static void bibRunScrollTo(void*);
EMSCRIPTEN_KEEPALIVE void bib_scroll_to(int y)
{
    if (!bibOnEngineThread()) {
        bibProxyToEngine(bibRunScrollTo, reinterpret_cast<void*>(static_cast<intptr_t>(y)));
        return;
    }
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return;

    if (!g_engine)
        return;
    if (RefPtr view = mainFrameView())
        view->setScrollPosition(WebCore::ScrollPosition(0, y));
}
static void bibRunScrollTo(void* p) { bib_scroll_to(static_cast<int>(reinterpret_cast<intptr_t>(p))); }

// Diagnostic: run a script string in the guest main world. Output channel
// is the guest console (wrap probes in console.log(...) — the forwarder
// puts them on stderr as "BIB: console log: ..."). Returns 0 if the engine
// is not up. Drives DOM/computed-style probes that are otherwise
// impossible from the host side.
// W-B1: proxied cross-thread; the optimistic `1` only means "queued" there
// (results travel via the guest-console forwarder anyway).
static void bibRunEval(void*);
EMSCRIPTEN_KEEPALIVE int bib_eval(const char* source)
{
    if (!bibOnEngineThread()) {
        if (!source)
            return 0;
        char* copy = strdup(source);
        if (!bibProxyToEngine(bibRunEval, copy)) {
            free(copy);
            return 0;
        }
        return 1;
    }
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return 0;

    if (!g_engine || !source)
        return 0;
    g_engine->mainFrame->script().executeScriptIgnoringException(String::fromUTF8(source), JSC::SourceTaintedOrigin::Untainted);
    return 1;
}
static void bibRunEval(void* p)
{
    char* source = static_cast<char*>(p);
    bib_eval(source);
    free(source);
}

// Host-triggered persistence flush (visibilitychange/pagehide): skips the
// 5s throttle but still skips the push when nothing changed.
static void bibRunPersistNow(void*);
EMSCRIPTEN_KEEPALIVE void bib_persist_now()
{
    if (!bibOnEngineThread()) {
        bibProxyToEngine(bibRunPersistNow, nullptr);
        return;
    }
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return;

    bibMaybePersist(true);
}
static void bibRunPersistNow(void*) { bib_persist_now(); }

// ---------------------------------------------------------------------------
// Guest WebAssembly shim (decision-006 S-A). JSC's wasm tiers are all
// unavailable on the CLoop port (IPInt has no cloop lowering — NO-GO), so
// guest pages get a polyfill instead: the host page translates module bytes
// to plain JS with Binaryen's wasm2js and the polyfill evals the result.
// Engine side is two dumb pipes, both installed per new window object by
// BibFrameLoaderClient::dispatchDidClearWindowObjectInWorld:
//   1. __bibWasm2js(payload, mode) — native fn on the guest global; ships a
//      base64 module to Module.bibWasm2js in the host realm (same thread:
//      the whole stack is single-threaded, EM_ASM is a synchronous call into
//      the page realm) and returns the host's string, or null.
//   2. the polyfill source (web/wasm-polyfill.js) — provided by the host as
//      Module.bibWasmPolyfill, evaluated before any author script. Hosts
//      that define neither (node gate runner) keep today's no-wasm behavior.

EMSCRIPTEN_KEEPALIVE char* bib_wasm_alloc(int size)
{
    // EM_ASM blocks below allocate engine-heap buffers for returned strings;
    // malloc itself is not in the JS export set, KEEPALIVE exports are.
    return static_cast<char*>(malloc(size));
}

EMSCRIPTEN_KEEPALIVE void bib_wasm_free(char* ptr)
{
    // W-B1: the frame-push / readback EM_ASM blocks free their transfer
    // buffers FROM THE MAIN THREAD — dlmalloc is thread-safe under -pthread.
    free(ptr);
}

// The JSC host function and the WTF/JSC-typed helpers below need C++
// linkage — step outside the export block (reopened after them).
} // extern "C"

JSC_DEFINE_HOST_FUNCTION(bibWasm2jsHostFunction, (JSC::JSGlobalObject* globalObject, JSC::CallFrame* callFrame))
{
    JSC::VM& vm = globalObject->vm();
    auto scope = DECLARE_THROW_SCOPE(vm);
    String payload = callFrame->argument(0).toWTFString(globalObject);
    RETURN_IF_EXCEPTION(scope, { });
    String mode = callFrame->argument(1).toWTFString(globalObject);
    RETURN_IF_EXCEPTION(scope, { });
    CString payloadUTF8 = payload.utf8();
    CString modeUTF8 = mode.utf8();
    char* out = static_cast<char*>(EM_ASM_PTR({
        let result = null;
        try {
            if (Module.bibWasm2js)
                result = Module.bibWasm2js(UTF8ToString($0), UTF8ToString($1));
        } catch (e) {
            (Module.printErr || console.error)("bibWasm2js host error: " + e);
        }
        if (typeof result !== "string")
            return 0;
        const len = lengthBytesUTF8(result) + 1;
        const buf = _bib_wasm_alloc(len);
        // A large translatable module (Discord ships several MB-scale ones)
        // can produce a multi-MB JS string; under wasm32 heap pressure the
        // alloc can fail. Without this guard stringToUTF8 writes through a
        // null pointer -> "memory access out of bounds" (Codex Rank 2).
        if (!buf)
            return 0;
        stringToUTF8(result, buf, len);
        return buf;
    }, payloadUTF8.data(), modeUTF8.data()));
    if (!out)
        return JSC::JSValue::encode(JSC::jsNull());
    JSC::JSString* result = JSC::jsString(vm, String::fromUTF8(out));
    free(out);
    return JSC::JSValue::encode(result);
}

static const String& wasmPolyfillSource()
{
    static NeverDestroyed<String> source = [] {
        char* text = static_cast<char*>(EM_ASM_PTR({
            const text = Module.bibWasmPolyfill;
            if (typeof text !== "string" || !text.length)
                return 0;
            const len = lengthBytesUTF8(text) + 1;
            const buf = _bib_wasm_alloc(len);
            stringToUTF8(text, buf, len);
            return buf;
        }));
        if (!text)
            return String();
        String result = String::fromUTF8(text);
        free(text);
        return result;
    }();
    return source;
}

void BIB::injectWasmPolyfill(WebCore::LocalFrame& frame, WebCore::DOMWrapperWorld& world)
{
    if (appResourcesStrict()) return; // Same internal JSC; no outer wasm2js behavior.
    if (&world != &WebCore::mainThreadNormalWorldSingleton())
        return;
    const String& polyfill = wasmPolyfillSource();
    if (polyfill.isEmpty())
        return;
    auto* globalObject = frame.script().globalObject(world);
    if (!globalObject)
        return;
    JSC::VM& vm = globalObject->vm();
    JSC::JSLockHolder lock(vm);
    globalObject->putDirect(vm, JSC::Identifier::fromString(vm, "__bibWasm2js"_s),
        JSC::JSFunction::create(vm, globalObject, 2, "__bibWasm2js"_s, bibWasm2jsHostFunction, JSC::ImplementationVisibility::Public),
        static_cast<unsigned>(JSC::PropertyAttribute::DontEnum));
    // The polyfill consumes (and deletes) __bibWasm2js from the global, then
    // defines WebAssembly. Runs before any author script in this document.
    frame.script().executeScriptIgnoringException(String { polyfill }, JSC::SourceTaintedOrigin::Untainted);
}

#include "BibPrototypeBridge.h"

extern "C" {

// Phase 4: real navigation. Drives FrameLoader::load -> DocumentLoader ->
// CachedResourceLoader -> EmbedderLoaderStrategy -> CurlRequest -> Wisp.
static void bibRunLoadUrl(void*);
EMSCRIPTEN_KEEPALIVE void bib_load_url(const char* url)
{
    if (!bibOnEngineThread()) {
        if (!url)
            return;
        char* copy = strdup(url);
        if (!bibProxyToEngine(bibRunLoadUrl, copy))
            free(copy);
        return;
    }
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return;

    if (!g_engine)
        return;
    WebCore::ResourceRequest request { URL { String::fromUTF8(url) } };
    WebCore::FrameLoadRequest frameLoadRequest { *g_engine->mainFrame, WTF::move(request) };
    printf("EMBEDDER: loading %s\n", url);
    g_engine->mainFrame->loader().load(WTF::move(frameLoadRequest));
}
static void bibRunLoadUrl(void* p)
{
    char* url = static_cast<char*>(p);
    bib_load_url(url);
    free(url);
}

// type: 0 = RawKeyDown, 1 = KeyUp, 2 = Char. Strings are UTF-8 (use ccall).
// text is only meaningful for Char events.
// W-B1: cross-thread returns 1 optimistically — the engine-side handled
// verdict isn't knowable without a blocking round-trip (deadlock-prone).
// The host only consumes the return for preventDefault, where over-eager
// handling is the safe direction.
struct BibKeyTask { int type; char* key; char* code; char* text; int vk; int repeat; int mods; };
static void bibRunKey(void*);
EMSCRIPTEN_KEEPALIVE int bib_key(int type, const char* key, const char* code, const char* text, int windowsVirtualKeyCode, int isAutoRepeat, int modifierBits)
{
    if (!bibOnEngineThread()) {
        auto* task = new BibKeyTask { type, strdup(key ? key : ""), strdup(code ? code : ""),
            strdup(text ? text : ""), windowsVirtualKeyCode, isAutoRepeat, modifierBits };
        if (!bibProxyToEngine(bibRunKey, task)) {
            free(task->key);
            free(task->code);
            free(task->text);
            delete task;
            return 0;
        }
        return 1;
    }
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return 0;

    if (!g_engine)
        return 0;
    auto eventType = WebCore::PlatformEvent::Type::RawKeyDown;
    if (type == 1)
        eventType = WebCore::PlatformEvent::Type::KeyUp;
    else if (type == 2)
        eventType = WebCore::PlatformEvent::Type::Char;
    String textString = eventType == WebCore::PlatformEvent::Type::Char ? String::fromUTF8(text) : String();
    WebCore::PlatformKeyboardEvent event(eventType, textString, textString,
        String::fromUTF8(key), String::fromUTF8(code), emptyString(),
        windowsVirtualKeyCode, isAutoRepeat, false, false,
        modifiersFromBits(modifierBits), MonotonicTime::now());
    return g_engine->mainFrame->eventHandler().keyEvent(event);
}
static void bibRunKey(void* p)
{
    auto* t = static_cast<BibKeyTask*>(p);
    bib_key(t->type, t->key, t->code, t->text, t->vk, t->repeat, t->mods);
    free(t->key);
    free(t->code);
    free(t->text);
    delete t;
}

} // extern "C"

int main()
{
    // W-B1: record the engine thread FIRST — every export's self-proxy
    // check needs it, and the host page starts calling exports the moment
    // onEngineReady fires.
    g_engineThread = pthread_self();
    g_engineThreadReady.store(true, std::memory_order_release);

    // Install the worker-scope Module hooks (pump, bibWasmPolyfill,
    // bibWasm2js — web/engine-pre.js) NOW: this EM_ASM runs in the engine
    // pthread's worker scope with Module fully constructed. The pre-js's
    // own eager attempts can fire before the pthread bootstrap builds
    // Module (gate9: empty bibWasmPolyfill got cached for the session).
    EM_ASM({
        if (typeof self !== "undefined" && self.__bibInstallWorkerHooks)
            self.__bibInstallWorkerHooks();
    });
    printf("EMBEDDER: engine thread=%p browser-main=%d\n",
        reinterpret_cast<void*>(g_engineThread), emscripten_is_main_browser_thread());
    // Verbose libcurl tracing (?curldebug=1 on the host page). Set from C
    // because Module.ENV-based getenv proved unreliable here. MUST happen
    // before installEmbedderStrategies(): the cookie-session setup
    // constructs the CurlContext singleton, which reads DEBUG_CURL exactly
    // once in its constructor.
    // W-B1: all boot flags live on the PAGE's Module — the engine pthread's
    // worker Module does not inherit them (W-B0 finding). MAIN_THREAD_EM_ASM
    // blocks this thread briefly while the main thread answers; safe at
    // boot, before the page starts driving us.
    if (MAIN_THREAD_EM_ASM_INT({ return Module.bibCurlDebug ? 1 : 0; }))
        setenv("DEBUG_CURL", "1", 1);
    printf("EMBEDDER: curldebug=%s\n", getenv("DEBUG_CURL") ? "on" : "off");

    // ?perflog=1 on the host page: emit a per-second engine-thread phase
    // breakdown (BIBPERF/s). Read straight from the host URL so no
    // browser.html wiring is needed — purely a diagnostic knob, off by
    // default. See PerfAccum / bib_tick.
    g_perfLog = MAIN_THREAD_EM_ASM_INT({
        try { return new URLSearchParams(location.search).get("perflog") === "1" ? 1 : 0; }
        catch (e) { return 0; }
    });
    printf("EMBEDDER: perflog=%s\n", g_perfLog ? "on" : "off");

    // Rendering-update throttle config (see g_rcapDynamic). ?rcap absent =>
    // DYNAMIC (default, interactive only — gates render once and must stay
    // deterministic). ?rcap=0 => off (uncapped). ?rcap=N (1..240) => fixed N/s.
    {
        int rcap = MAIN_THREAD_EM_ASM_INT({
            try { var s = new URLSearchParams(location.search).get("rcap");
                  if (s === null) return -1;                 // absent => dynamic
                  var v = parseInt(s, 10);
                  return (v >= 0 && v <= 240) ? v : -1; }
            catch (e) { return -1; }
        });
        const bool inter = MAIN_THREAD_EM_ASM_INT({ return Module.bibInteractive ? 1 : 0; });
        if (rcap < 0)       { g_rcapDynamic = inter; g_rcapFixedMs = 0.0; }
        else if (rcap == 0) { g_rcapDynamic = false; g_rcapFixedMs = 0.0; }
        else                { g_rcapDynamic = false; g_rcapFixedMs = 1000.0 / rcap; }
        printf("EMBEDDER: rcap=%s\n",
            g_rcapFixedMs > 0.0 ? "fixed" : g_rcapDynamic ? "dynamic" : "off");
    }

    // Request blocklist (?noblock=1 on the host page disables it): the loader
    // strategy refuses analytics/ads/telemetry subresources before they
    // download — CLoop parses every script byte on the main thread, so those
    // bundles are pure boot cost.
    bool noBlock = MAIN_THREAD_EM_ASM_INT({ return Module.bibNoBlock ? 1 : 0; });
    BIB::setRequestBlocklistEnabled(!noBlock);
    printf("EMBEDDER: request blocklist=%s\n", noBlock ? "off" : "on");
    if (getenv("DEBUG_CURL")) {
        // Constructs the CurlContext singleton NOW (post-setenv) and reports
        // whether the verbose flag actually latched — splits env plumbing
        // from curl-output plumbing when tracing goes missing.
        printf("EMBEDDER: curl verbose=%d\n", WebCore::CurlContext::singleton().isVerbose());
    }

    // ?gclog=1 (host URL): turn on JSC GC pause logging (JSC_logGC=Basic) to
    // confirm whether the periodic ~1fps stutter is GC stop-the-world vs slow
    // CLoop JS. MUST be set BEFORE JSC::initialize() — Options::initialize()
    // reads JSC_-prefixed env once there. setenv from C (Module.ENV getenv is
    // unreliable here, same reason as DEBUG_CURL). Diagnostic, off by default.
    if (MAIN_THREAD_EM_ASM_INT({
        try { return new URLSearchParams(location.search).get("gclog") === "1" ? 1 : 0; }
        catch (e) { return 0; }
    })) {
        setenv("JSC_logGC", "1", 1);
        printf("EMBEDDER: gclog=on (JSC_logGC=1)\n");
    }

    JSC::initialize();
    WTF::initializeMainThread();
#if BIB_FOUNDATION_SERVICES
    // Real C++20 host composition must be installed before Page creation.
    // Its archive is an explicit opt-in input; no fallback host exists.
    if (bib_foundation_service_candidate_initialize()) {
        printf("EMBEDDER: foundation service owner initialization failed\n");
        return 1;
    }
#endif
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return 1;
    WTF::setProcessPrivileges(WTF::allPrivileges());
    WebCore::initializeCommonAtomStrings();
    BIB::installEmbedderStrategies();
    BIB::appResourcesInitializeScheme();

    // Event-driven pump: every main-RunLoop wake-up (dispatch, timer start)
    // pokes the host page, which schedules a macrotask calling bib_pump().
    // Without this the engine only made progress once per host display
    // frame (rAF -> bib_tick), quantizing EVERY async hop — curl passes,
    // callOnMainThread chains, setTimeout(0) — to ~16.7ms each (measured:
    // 13.9ms per setTimeout(0) hop, 93ms for a warm same-origin fetch).
    // The callback fires while the RunLoop lock is held: bibWakeUp must
    // only schedule, never call back into the engine synchronously.
    // W-B1: this EM_ASM executes in the ENGINE pthread's worker scope —
    // Module.bibWakeUp there is installed by web/engine-pre.js (worker-local
    // MessageChannel calling _bib_pump on this same thread), NOT the page's.
    WTF::RunLoop::setWakeUpCallback([] {
        EM_ASM({ if (Module.bibWakeUp) Module.bibWakeUp(); });
    });

    const bool interactive = BIB::appResourcesStrict() || MAIN_THREAD_EM_ASM_INT({ return Module.bibInteractive ? 1 : 0; });

    // M-A media bridge gate (?media=1): must be set before the first
    // MediaPlayer construction — buildMediaEnginesVector runs once and
    // caches for the session.
#if BIB_FOUNDATION_SERVICES
    // This first service overlay excludes the supplier's independent browser
    // media event entry, whose callbacks do not yet carry engine-turn guards.
    BIB::g_mediaEnabled = false;
#else
    BIB::g_mediaEnabled = !BIB::appResourcesStrict() && interactive && MAIN_THREAD_EM_ASM_INT({ return Module.bibMedia ? 1 : 0; });
#endif
    if (BIB::g_mediaEnabled)
        printf("EMBEDDER: media bridge ENABLED (audio-only, wisp-routed fetch)\n");

    // Skia GPU boot (decision-005 G2, opt-in via Module.bibGPU / ?gpu=1).
    // Must run before ANY paint: GraphicsContextSkia consults the shared
    // PlatformDisplay. W-B2: under PROXY_TO_PTHREAD the page's #screen
    // arrives on THIS thread as an OffscreenCanvas (transferred at spawn by
    // __wrap_pthread_create) and emscripten_webgl_create_context("#screen")
    // resolves it through GL.offscreenCanvases; the single-threaded build
    // creates the context on the page canvas directly (pre-W-B1 path).
    // With the flag unset nothing here runs — the CPU path is unchanged.
    if (interactive && MAIN_THREAD_EM_ASM_INT({ return Module.bibGPU ? 1 : 0; })) {
        // W-B2 v2: back the GL context with a worker-PRIVATE OffscreenCanvas
        // (we no longer transfer #screen). Register it in emscripten's
        // GL.offscreenCanvases under "bibgpu" so create_context("#bibgpu")
        // resolves to it: findCanvasEventTarget checks GL.offscreenCanvases
        // first, and create unwraps the `.offscreenCanvas` field
        // (libhtml5_webgl.js). This runs on the engine thread (== this GL's
        // owner). The canvas is NEVER displayed — frames reach #screen via the
        // raster readback+putImageData path.
        // NOTE: no object literal here — a brace-comma ({a: x, b: y}) would be
        // split by the C preprocessor as an EM_ASM macro-arg separator (braces
        // don't group for cpp, only parens do). Build the info object with
        // dotted assignments so the only commas are paren-protected.
#ifdef __EMSCRIPTEN_PTHREADS__
        EM_ASM({
            try {
                var oc = new OffscreenCanvas($0, $1);
                var info = {};
                info.offscreenCanvas = oc;
                info.id = 'bibgpu';
                GL.offscreenCanvases['bibgpu'] = info;
            } catch (e) {
                console.error('EMBEDDER: bibgpu OffscreenCanvas create failed: ' + e);
            }
        }, kWidth, kHeight);
        const char* gpuCanvasSelector = "#bibgpu";
#else
        // BIB_PTHREAD=OFF: the engine runs on the browser main thread and owns
        // #screen's WebGL2 context directly (gpu-implicit present — the host did
        // NOT take a 2d/bitmap context). FBO 0 is the visible drawing buffer, so
        // the browser presents it implicitly; no OffscreenCanvas, no transfer.
        const char* gpuCanvasSelector = "#screen";
#endif
        if (WebCore::initializePlatformDisplayEmscripten(gpuCanvasSelector)) {
            // G4 handlers go on FIRST (Codex MEDIUM): a loss between
            // context creation and handler install would miss
            // preventDefault and be unrestorable. A loss DURING the caps
            // setup below now flags g_gpuLost; the boot then either fails
            // here (GrContext caps against a lost context) → host raster
            // reload, or the restored handler rebuilds post-boot.
            installGpuContextLossHandlers();
            // Force SkiaGLContext creation now; a null GrContext means the
            // interface/caps stage failed — fall back to CPU raster.
            auto& display = WebCore::PlatformDisplay::sharedDisplay();
            g_gpu = display.skiaGLContext() && display.skiaGrContext();
        }
        printf("EMBEDDER: gpu=%s\n", g_gpu ? "on" : "REQUESTED-BUT-UNAVAILABLE (cpu fallback)");
        if (!g_gpu) {
            // The host committed to GPU mode (no 2d context, ignores frame
            // pushes) before the engine could fail — an engine-only
            // fallback would leave the canvas permanently blank (Codex
            // HIGH, G3). Tell the host so it can reload with ?gpu=0.
            MAIN_THREAD_ASYNC_EM_ASM({ if (Module.bibGpuFallback) Module.bibGpuFallback(); });
        }
    }

    printf("EMBEDDER: init OK\n");

    // PageIdentifier: the empty-clients recipe (SVGImage) passes nullopt,
    // but Page::mediaSessionManager() hard-returns null for identifier-less
    // pages — playInternal() then parks every <audio>/<video> play() forever
    // ("returning because of interruption", M-A root cause). Real pages
    // always carry one; generating it also unlocks the default
    // PlatformMediaSessionManager factory.
    auto pageConfiguration = WebCore::pageConfigurationWithEmptyClients(WebCore::PageIdentifier::generate(), PAL::SessionID::defaultSessionID());
    pageConfiguration.chromeClient = makeUniqueRef<BIB::BibChromeClient>();
    pageConfiguration.editorClient = makeUniqueRef<BIB::BibEditorClient>();
    // Real cookie jar over the embedder's in-memory NetworkStorageSession.
    // The empty-clients default wraps EmptyStorageSessionProvider (null
    // session): document.cookie writes vanish, reads return "" — Google
    // serves its "Cookies are disabled" interstitial on exactly that.
    pageConfiguration.cookieJar = WebCore::CookieJar::create(BIB::createEmbedderStorageSessionProvider());
    // Real in-memory localStorage/sessionStorage (root cause #11): the
    // empty-clients provider discards writes, and the WebCore-layer
    // defaults leave both window properties OFF entirely (settings flipped
    // below) — `window.localStorage` was a ReferenceError that modern site
    // bootstraps treat as fatal.
    pageConfiguration.storageNamespaceProvider = BIB::BibStorageNamespaceProvider::create();
    // Real in-process IndexedDB (root cause #13): the empty-clients
    // DatabaseProvider RELEASE_ASSERTs on idbConnectionToServerForSession —
    // any guest JS touching window.indexedDB killed that page's script
    // (discord.com/login went blank exactly there). WebKitLegacy's
    // InProcessIDBServer recipe, in-memory backing store.
    pageConfiguration.databaseProvider = BIB::BibDatabaseProvider::create();
    // Fail-fast WebSocket provider (WS-0): the empty-clients SocketProvider
    // returns a null channel and WebSocket::create RELEASE_ASSERTs on it —
    // any guest `new WebSocket()` aborted the engine (discord.com/login dies
    // on its remote-auth gateway socket). This one fails the connection like
    // an unreachable server (error event + close 1006) instead. WS-1 (real
    // channel over curl-ws) replaces the channel, not this wiring.
    pageConfiguration.socketProvider = BIB::BibSocketProvider::create();

    // pageConfigurationWithEmptyClients hardcodes SandboxFlags::all() on the
    // main frame (it exists for SVGImage, which must never run script) —
    // Document::initSecurityContext copies the frame's flags, silently
    // blocking ALL script regardless of Settings::setScriptEnabled. Clear
    // them for the interactive embedder; gate mode keeps SVG semantics.
    if (interactive) {
        if (auto* localParams = std::get_if<WebCore::PageConfiguration::LocalMainFrameCreationParameters>(&pageConfiguration.mainFrameCreationParameters)) {
            localParams->effectiveSandboxFlags = { };
            // Phase 4: the empty frame client silently kills real loads four
            // ways (dropped policy completions, canHandleRequest=false,
            // canShowMIMEType=false, committedLoad no-op) — install ours.
            localParams->clientCreator = [](auto&, auto& frameLoader) -> UniqueRef<WebCore::LocalFrameLoaderClient> {
                return WTF::makeUniqueRefWithoutRefCountedCheck<BIB::BibFrameLoaderClient>(frameLoader);
            };
        }
    }
    auto page = WebCore::Page::create(WTF::move(pageConfiguration));
    // Script stays OFF in gate mode so the offscreen pixel gate is
    // byte-stable; interactive mode runs JSC (CLoop) inside the page.
    page->settings().setScriptEnabled(interactive);
    page->settings().setAcceleratedCompositingEnabled(false);
    // Raw WebCore defaults this to FALSE (embedders must opt in) —
    // without it CachedResourceLoader silently DEFERS every non-data:
    // image load: no request, no error event, blank <img> (root cause #8,
    // empty-defaults family).
    page->settings().setLoadsImagesAutomatically(true);
    if (BIB::appResourcesStrict()) {
        page->settings().setServiceWorkersEnabled(false);
        // Cached different-document restoration bypasses response/creation
        // selection. Ordinary fragment/history state remains in one document.
        page->settings().setUsesBackForwardCache(false);
    }
    // Raw-WebCore defaults again: LocalStorageEnabled/SessionStorageEnabled
    // are FALSE at this layer (the WebKit wrappers flip them on; we must
    // too). The window properties are IDL-gated behind these settings.
    page->settings().setLocalStorageEnabled(true);
    page->settings().setSessionStorageEnabled(true);
    // requestIdleCallback defaults FALSE at every preferences layer (same
    // family as root cause #11) although WebCore fully implements it.
    // Lazy-hydration/scheduler libraries feature-detect it; a missing
    // global silently strands their deferred work.
    page->settings().setRequestIdleCallbackEnabled(true);
    // Raw-WebCore MemoryCache default is 8MB total — one modern page evicts
    // everything, so every in-engine navigation refetched all subresources
    // over wisp. Still in-memory; sized like a small browser profile.
    WebCore::MemoryCache::singleton().setCapacities(0, 16 * 1024 * 1024, 64 * 1024 * 1024);

    // Persistence seed (cookies + guest localStorage from a previous host
    // session, loaded out of OPFS by browser.html). Must land before the
    // first network request so the initial navigation already attaches the
    // restored cookies. Same SAB string-copy recipe as bibHTML below.
    {
        int seedBytes = MAIN_THREAD_EM_ASM_INT({ return Module.bibSeedState ? lengthBytesUTF8(Module.bibSeedState) + 1 : 0; });
        if (seedBytes > 0) {
            char* seedJSON = static_cast<char*>(malloc(seedBytes));
            if (seedJSON) {
                MAIN_THREAD_EM_ASM({ stringToUTF8(Module.bibSeedState, $0, $1); }, seedJSON, seedBytes);
                bibSeedPersistedState(String::fromUTF8(seedJSON));
                free(seedJSON);
            }
        }
    }

    RefPtr localMainFrame = page->localMainFrame();
    if (!localMainFrame) {
        printf("EMBEDDER: FAIL no localMainFrame\n");
        exit(1); // EXIT_RUNTIME=0: explicit teardown (node gate path)
    }

    localMainFrame->setView(WebCore::LocalFrameView::create(*localMainFrame, WebCore::IntSize(kWidth, kHeight)));
    localMainFrame->init();

    // Re-fetched after init(): the initial-empty-document commit already
    // ran transitionToCommittedForNewPage, which replaced the view above.
    RefPtr frameView = localMainFrame->view();
    frameView->setCanHaveScrollbars(interactive);

    if (interactive) {
        page->focusController().setActive(true);
        page->focusController().setFocused(true);
    }

    Ref loader = localMainFrame->loader();
    RefPtr documentLoader = loader->activeDocumentLoader();
    if (!documentLoader) {
        printf("EMBEDDER: FAIL no activeDocumentLoader\n");
        exit(1); // EXIT_RUNTIME=0: explicit teardown (node gate path)
    }

    // The host page may supply the document via Module.bibHTML (a JS
    // string); without it the built-in gate page loads. Copied out of the
    // JS heap via stringToUTF8 (forced into the runtime by
    // EXPORTED_RUNTIME_METHODS) into a malloc'd UTF-8 buffer.
    char* hostHTML = nullptr;
    int hostHTMLBytes = BIB::appResourcesStrict() ? 0 : MAIN_THREAD_EM_ASM_INT({ return Module.bibHTML ? lengthBytesUTF8(Module.bibHTML) + 1 : 0; });
    if (hostHTMLBytes > 0) {
        hostHTML = static_cast<char*>(malloc(hostHTMLBytes));
        if (hostHTML)
            // Sync proxy: stringToUTF8 runs on the main thread, writing
            // through its view into the SHARED heap — visible here on return.
            MAIN_THREAD_EM_ASM({ stringToUTF8(Module.bibHTML, $0, $1); }, hostHTML, hostHTMLBytes);
        else
            printf("EMBEDDER: bibHTML allocation failed (%d bytes) — using built-in page\n", hostHTMLBytes);
    }
    const char* html = hostHTML ? hostHTML : kTestHTML;

    if (!BIB::appResourcesStrict()) {
        documentLoader->writer().setMIMEType("text/html"_s);
        documentLoader->writer().begin(URL());
        BIB::foundationServicesSelectApplicationDocument(*localMainFrame);
        documentLoader->writer().addData(WebCore::SharedBuffer::create(unsafeMakeSpan(reinterpret_cast<const uint8_t*>(html), strlen(html))));
        documentLoader->writer().end();
    }
    free(hostHTML);

    printf(BIB::appResourcesStrict() ? "EMBEDDER: empty runtime ready; application load is pending\n" : "EMBEDDER: HTML loaded\n");

    // Re-fetch: the writer-driven load above may have replaced the view too.
    frameView = localMainFrame->view();
    frameView->resize(kWidth, kHeight);
    localMainFrame->protectedDocument()->updateLayoutIgnorePendingStylesheets();

    printf("EMBEDDER: layout OK\n");

    // Render-tree dump: verifies parsing+style+layout even if glyph raster
    // fails (missing fonts paint nothing but still produce geometry).
    auto treeDump = WebCore::externalRepresentation(localMainFrame.get());
    printf("RENDER TREE:\n%s\n", treeDump.utf8().data());

    auto info = SkImageInfo::Make(kWidth, kHeight, kRGBA_8888_SkColorType, kPremul_SkAlphaType);
    sk_sp<SkSurface> surface;
    if (g_gpu) {
        // Texture-backed backing store (NOT framebuffer 0 directly: with
        // preserveDrawingBuffer off, FBO 0 is undefined after every
        // composite — dirty-rect painting needs stable pixels). Present
        // wraps FBO 0 once; samples=1/stencil=8 match the context attrs
        // (G1: GL_SAMPLES=0 with antialias:false, stencil honored at 8).
        auto* grContext = WebCore::PlatformDisplay::sharedDisplay().skiaGrContext();
        surface = SkSurfaces::RenderTarget(grContext, skgpu::Budgeted::kNo, info, 0, kTopLeft_GrSurfaceOrigin, nullptr);
        if (surface) {
            GrGLFramebufferInfo fbInfo;
            fbInfo.fFBOID = 0;
            fbInfo.fFormat = 0x8058; // GL_RGBA8
            auto target = GrBackendRenderTargets::MakeGL(kWidth, kHeight, 1, 8, fbInfo);
            g_fbo0Surface = SkSurfaces::WrapBackendRenderTarget(grContext, target,
                kBottomLeft_GrSurfaceOrigin, kRGBA_8888_SkColorType, nullptr, nullptr);
        }
        if (!surface || !g_fbo0Surface) {
            printf("EMBEDDER: gpu surface setup failed — cpu fallback\n");
            g_fbo0Surface = nullptr;
            surface = nullptr;
            g_gpu = false;
            // Same split-brain hazard as the boot-init fallback above: the
            // host is in GPU mode with no blit path — engine CPU raster
            // would never reach the screen (Codex HIGH, G3).
            MAIN_THREAD_ASYNC_EM_ASM({ if (Module.bibGpuFallback) Module.bibGpuFallback(); });
        }
        if (g_gpu) {
            // W-B2 software-renderer guard: shielded/forked browsers can
            // hand a worker OffscreenCanvas a SOFTWARE WebGL device
            // (SwiftShader/llvmpipe) — and the same browsers MASK the
            // renderer string, so don't trust it: MEASURE. Three full
            // presents with a 1x1 readback sync: real GPUs run ~1-3ms per
            // frame (G1: 0.9-1.3ms); software takes tens of ms (live
            // report: ~1 frame/MINUTE on a Chromium fork). Slow → raster,
            // which IS the better engine on that hardware.
            char rendererBuf[128] = { 0 };
            EM_ASM({
                var ctx = GL.currentContext && GL.currentContext.GLctx;
                var s = "";
                if (ctx) {
                    var ext = ctx.getExtension("WEBGL_debug_renderer_info");
                    s = String((ext ? ctx.getParameter(ext.UNMASKED_RENDERER_WEBGL) : ctx.getParameter(ctx.RENDERER)) || "");
                }
                stringToUTF8(s.slice(0, 120), $0, 127);
            }, rendererBuf);
            uint32_t benchPixel = 0;
            auto benchInfo = SkImageInfo::Make(1, 1, kRGBA_8888_SkColorType, kUnpremul_SkAlphaType);
            // WARMUP, not measured: the first frames on a fresh context pay
            // one-time pipeline/shader compiles (G1: frame0 ≈ 100ms on real
            // hardware) — measuring them reads a healthy GPU as "software"
            // (observed: Intel UHD 630 "26.67ms/frame" on first-3-frames).
            // Software renderers stay slow on EVERY frame; that's the
            // discriminator, so bench only post-warmup steady state.
            // 8x overdraw per frame: a single fill+quad is so simple that
            // SwiftShader steady-states at ~5ms (measured) — too close to
            // real GPUs for a safe threshold. Overdraw multiplies software
            // raster cost (~40ms) while hardware barely notices (~1ms).
            for (int i = 0; i < 2; ++i) {
                surface->getCanvas()->drawColor(SK_ColorWHITE);
                for (int j = 0; j < 8; ++j)
                    surface->draw(g_fbo0Surface->getCanvas(), 0, 0);
                skgpu::ganesh::FlushAndSubmit(g_fbo0Surface.get());
            }
            g_fbo0Surface->readPixels(SkPixmap(benchInfo, &benchPixel, 4), 0, 0);
            auto benchStart = MonotonicTime::now();
            for (int i = 0; i < 3; ++i) {
                surface->getCanvas()->drawColor(SK_ColorWHITE);
                for (int j = 0; j < 8; ++j)
                    surface->draw(g_fbo0Surface->getCanvas(), 0, 0);
                skgpu::ganesh::FlushAndSubmit(g_fbo0Surface.get());
            }
            // The readback is the sync: WebGL queues are deep and flush is
            // advisory — readPixels forces completion everywhere.
            g_fbo0Surface->readPixels(SkPixmap(benchInfo, &benchPixel, 4), 0, 0);
            double msPerFrame = (MonotonicTime::now() - benchStart).milliseconds() / 3.0;
            printf("EMBEDDER: gpu renderer \"%s\" present-bench %.2fms/frame\n", rendererBuf, msPerFrame);
            // ?gpubench=0 (gate8): measure but don't enforce — playwright
            // headless IS SwiftShader, where the pipeline is correct but
            // raster is the faster engine.
            bool enforceBench = MAIN_THREAD_EM_ASM_INT({ return Module.bibGpuBench === false ? 0 : 1; });
            if (enforceBench && msPerFrame > 12.0) {
                printf("EMBEDDER: gpu looks SOFTWARE-RENDERED — cpu fallback\n");
                g_fbo0Surface = nullptr;
                surface = nullptr;
                g_gpu = false;
                MAIN_THREAD_ASYNC_EM_ASM({ if (Module.bibGpuFallback) Module.bibGpuFallback(); });
            }
        }
    }
    if (!g_gpu)
        surface = SkSurfaces::Raster(info);
    if (!surface) {
        printf("EMBEDDER: FAIL SkSurface\n");
        exit(1); // EXIT_RUNTIME=0: explicit teardown (node gate path)
    }

    g_engine = new Engine { WTF::move(page), WTF::move(localMainFrame), WTF::move(surface) };
    if (BIB::appResourcesStrict() && !BIB::appResourcesStartApplicationLoad(*g_engine->mainFrame)) {
        fprintf(stderr, "Foundation app: explicit app-URL bootstrap could not start\n");
        exit(1);
    }
    // Fast-scroll shift needs g_engine. GPU mode: the CPU memmove trick is
    // moot (no g_blitPixels mirror) — a null hook makes ChromeClient::scroll
    // fall back to addDamage(clip), i.e. a clipped GPU repaint.
    BIB::g_scrollBlit = g_gpu ? nullptr : bibScrollBlit;

#ifdef __EMSCRIPTEN_PTHREADS__
    // Zero-copy GPU present handshake: tell the page which Emscripten worker is
    // the engine (proxied-main) so it can wire a dedicated MessagePort for
    // ImageBitmap frames. engine-pre.js creates the channel and transfers port2
    // to the page inside this hello (worker→main only — nothing custom crosses
    // Emscripten's worker onmessage). Only in pthread GPU mode: raster delivers
    // via bibBlit, and the BIB_PTHREAD=OFF build presents on #screen directly.
    // The page-side hook (browser.html) ignores this unless presentMode is
    // "gpu-bitmap". Sent now that the bibgpu OffscreenCanvas + both surfaces
    // exist; the first present waits for the page's first {t:"ready"} ack.
    if (g_gpu) {
        EM_ASM({
            if (Module.bibPresentWorkerHello)
                Module.bibPresentWorkerHello($0, $1);
        }, kWidth, kHeight);
    }
#endif

    // G3: guest 2D canvases on Ganesh (host defaults this ON with GPU after
    // the A/B — 600-arc anim 51.97/29.08/18.73 ms per frame cpu/gpu/this,
    // getImageData unregressed; ?canvasgpu=0 escapes).
    // CanvasUsesAcceleratedDrawing defaults FALSE for WebCore-direct
    // embedders, so without this guest canvases paint CPU-raster and
    // re-upload per draw even under GPU. Gated on the SURVIVING g_gpu
    // (after the surface fallback above): texture canvases drawn into a
    // raster window surface would read back on every draw.
    if (g_gpu && MAIN_THREAD_EM_ASM_INT({ return Module.bibCanvasGPU ? 1 : 0; }))
        g_engine->page->settings().setCanvasUsesAcceleratedDrawing(true);

    if (!paintFrame()) {
        printf("EMBEDDER: FAIL paint\n");
        exit(1); // EXIT_RUNTIME=0: explicit teardown (node gate path)
    }
    printf("EMBEDDER: paint OK\n");

    if (interactive) {
        // Browser mode: hand control to the host page's rAF loop. The unwind
        // skips the rest of main and keeps the runtime (and g_engine) alive.
        printf("EMBEDDER: interactive — runtime stays alive\n");
        MAIN_THREAD_ASYNC_EM_ASM({ if (Module.onEngineReady) Module.onEngineReady(); });
        // This Emscripten handoff skips ordinary C++ destruction. All startup
        // JSC locks/checkpoints are complete; release the turn explicitly.
        foundationServiceTurn.finish();
        emscripten_exit_with_live_runtime();
    }

    SkPixmap pixmap;
    if (!g_engine->surface->peekPixels(&pixmap)) {
        printf("EMBEDDER: FAIL peekPixels\n");
        exit(1); // EXIT_RUNTIME=0: explicit teardown (node gate path)
    }
    if (!writePPM("/out.ppm", pixmap)) {
        printf("EMBEDDER: FAIL writePPM\n");
        exit(1); // EXIT_RUNTIME=0: explicit teardown (node gate path)
    }

    // Gate assertions are region-specific so a fontconfig/glyph regression
    // cannot hide behind the div: the blue box and the red heading must BOTH
    // be present, independently (Codex review 2026-06-09).
    int nonWhite = 0;
    int exactBlue = 0; // #0066CC <div>, expected exactly 200x100
    int redGlyph = 0; // antialiased #CC0000 "hello" glyphs in the h1 band
    for (int y = 0; y < kHeight; ++y) {
        const uint8_t* row = static_cast<const uint8_t*>(pixmap.addr(0, y));
        for (int x = 0; x < kWidth; ++x) {
            const uint8_t r = row[x * 4], g = row[x * 4 + 1], b = row[x * 4 + 2];
            if (!(r == 0xFF && g == 0xFF && b == 0xFF))
                ++nonWhite;
            if (r == 0x00 && g == 0x66 && b == 0xCC)
                ++exactBlue;
            if (y < 76 && r > 0x90 && g < 0x60 && b < 0x60)
                ++redGlyph;
        }
    }
    printf("EMBEDDER: nonWhitePixels=%d exactBlue=%d redGlyph=%d\n", nonWhite, exactBlue, redGlyph);
    if (exactBlue != 200 * 100) {
        printf("EMBEDDER: FAIL blue div wrong size (%d != 20000)\n", exactBlue);
        exit(1); // EXIT_RUNTIME=0: explicit teardown (node gate path)
    }
    if (redGlyph < 200) {
        printf("EMBEDDER: FAIL heading glyphs missing (fonts broken?)\n");
        exit(1); // EXIT_RUNTIME=0: explicit teardown (node gate path)
    }
    printf("EMBEDDER: DONE\n");
    exit(0); // EXIT_RUNTIME=0: explicit teardown runs Module.onExit (gate1 reads /out.ppm there)
}

#endif // BIB_ENGINE_PROVIDER_NEUTRAL
