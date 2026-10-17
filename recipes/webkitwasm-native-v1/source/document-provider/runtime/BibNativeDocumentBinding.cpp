// SPDX-License-Identifier: CC0-1.0
// Native pixel1795 binding source. Native WebCore compile/runtime remains unqualified.
#include "config.h"
#include "BibNativeProviderBootstrap.hpp"
#include "BibNativeProviderOnce.hpp"
#include "EnginePrivate.hpp"
#include "LegacyHostAdapters.hpp"
#include BIB_NATIVE_PROVIDER_METADATA_HEADER
#include "BibCopiedDocumentCatalog.hpp"
#include "BibEngineProviderPreflight.h"
#include "BibEngineProviderRuntime.h"
#include "BibEngineProviderLifecycleHooks.h"
#include "BibEngineProviderDocumentProjection.h"
#include "BibAppResources.h"
#include "BibFoundationServiceBridge.h"
#include "NativeDocumentV2Publisher.hpp"
#include "CommonVM.h"
#include "LocalFrame.h"
#include "LocalFrameInlines.h"
#include <JavaScriptCore/JSLock.h>
#include <algorithm>
#include <atomic>
#include <cstring>
#include <memory>
#include <new>
#include <optional>
#include <span>
#include <thread>

#if defined(__EMSCRIPTEN__) || defined(__EMSCRIPTEN_PTHREADS__) || !BIB_ENGINE_PROVIDER_NATIVE || !BIB_ENGINE_PROVIDER_NEUTRAL || !BIB_ENGINE_PROVIDER_DOCUMENT_V2
#error "Native document binding requires the explicit native64 neutral pixel1795 composition"
#endif
static_assert(sizeof(void*) == 8);
namespace M = foundation::appended::native_provider_metadata;
static_assert(M::metadataValid());

namespace bib::provider_candidate {
namespace {
namespace D = document_catalog;
namespace N = BIB::NativeDocumentV2;
namespace C = BIB::FormsV2Combined;
struct State final {
    BibEngineBuildV1 build{};
    BibEngineLimitsV1 limits{};
    ServiceRetentionLimits retention{};
    const std::thread::id owner{std::this_thread::get_id()};
    std::uint64_t worker{}, instance{};
    BibEngineHostV1 host{};
    std::unique_ptr<LegacyHostAdapters> adapters;
    BibFoundationServiceHostV1 services{};
    BibAppResourceBundleHostV1 resources{};
    std::unique_ptr<C::Session> session;
    std::unique_ptr<C::Publisher> publisher;
    bool installed{}, started{};
};
// Process lifetime. No reset/unload/destructor cleanup export is provided.
State* state;
constinit NativeProviderOnce bindingOnce;
constinit std::atomic<std::uint64_t> nextRuntimeIdentity{1};
std::uint64_t reserveRuntimeIdentity() noexcept
{
    auto value = nextRuntimeIdentity.load(std::memory_order_relaxed);
    do { if (!value || value == UINT64_MAX) return 0; }
    while (!nextRuntimeIdentity.compare_exchange_weak(value, value + 1, std::memory_order_relaxed));
    return value;
}
bool owner(const State& s) noexcept { return s.owner == std::this_thread::get_id(); }
bool faulted(const State& s) noexcept { return s.adapters && s.adapters->callback_faulted(); }
bool identity(const BibEngineDocumentV1& d) noexcept {
    return d.application_instance && d.document_sequence && d.service_generation;
}
N::Identity nativeIdentity(const BibEngineDocumentV1& d) noexcept {
    return {d.application_instance,d.service_generation,d.document_sequence};
}
std::span<const std::uint8_t> bytes(const BibEngineBytesV1& b) noexcept { return {b.data,b.length}; }
bool validBytes(const BibEngineBytesV1* b, std::uint32_t maximum) noexcept {
    return b && !b->reserved && b->length <= maximum && (!b->length || b->data);
}
std::int32_t cachedStatus(C::CachedRequestStatus value) noexcept {
    switch (value) {
    case C::CachedRequestStatus::ok: return BIB_ENGINE_OK;
    case C::CachedRequestStatus::invalid: return BIB_ENGINE_INVALID;
    case C::CachedRequestStatus::stale: return BIB_ENGINE_STALE;
    case C::CachedRequestStatus::busy: return BIB_ENGINE_REENTRANT;
    case C::CachedRequestStatus::unsupported: return BIB_ENGINE_UNSUPPORTED;
    case C::CachedRequestStatus::limit: return BIB_ENGINE_LIMIT;
    }
    return BIB_ENGINE_INVALID;
}
// Immutable cached admission. Deliberately NO current/frame/Document/getter,
// Bridge, lock, phase guard, publication/lease mutation or callback here.
std::optional<N::Query> decodedRequest(const State& s, std::uint64_t worker,
    const BibEngineDocumentV1* expected, std::uint32_t query, std::uint32_t operation,
    std::uint64_t sequence, const BibEngineBytesV1* input, std::optional<N::ActionRequest>& action)
{
    if (!owner(s) || !worker || worker != s.worker || !expected || !identity(*expected)
        || expected->application_instance != s.instance || !sequence
        || sequence > BIB_ENGINE_DOCUMENT_V2_MAX_ORDINARY_SEQUENCE || query > 1 || !s.publisher)
        return std::nullopt;
    N::Query request;
    if (query == 1) {
        if (operation != BIB_ENGINE_QUERY_DOCUMENT_FORMS_V2
            || !validBytes(input,BIB_ENGINE_DOCUMENT_V2_QUERY_BYTES)
            || input->length != BIB_ENGINE_DOCUMENT_V2_QUERY_BYTES) return std::nullopt;
        request = N::decodeQuery(bytes(*input));
    } else {
        if (operation != BIB_ENGINE_COMMAND_FORM_ACTION_V2
            || !validBytes(input,BIB_ENGINE_DOCUMENT_V2_MAX_ACTION_BYTES)) return std::nullopt;
        action = N::decodeAction(bytes(*input));
        request = action->request;
    }
    if (request.identity != nativeIdentity(*expected) || request.outer_sequence != sequence
        || (query ? !request.document_request_id : request.document_request_id != 0)) return std::nullopt;
    return request;
}
std::int32_t validateRequest(void* raw, std::uint64_t worker, const BibEngineDocumentV1* expected,
    std::uint32_t query, std::uint32_t operation, std::uint64_t sequence, const BibEngineBytesV1* input)
{
    auto& s=*static_cast<State*>(raw);
    if (!owner(s)) return BIB_ENGINE_WRONG_THREAD;
    try {
        std::optional<N::ActionRequest> action;
        auto request=decodedRequest(s,worker,expected,query,operation,sequence,input,action);
        return request ? cachedStatus(s.publisher->inspectCachedRequest(*request,action)) : BIB_ENGINE_INVALID;
    } catch (const std::bad_alloc&) { return BIB_ENGINE_LIMIT; }
    catch (...) { return BIB_ENGINE_INVALID; }
}
std::int32_t validateReply(void* raw, std::uint64_t worker, const BibEngineDocumentV1* expected,
    std::uint32_t query, std::uint32_t operation, std::uint64_t sequence,
    const BibEngineBytesV1* input, const BibEngineBytesV1* reply)
{
    auto& s=*static_cast<State*>(raw);
    if (!owner(s)) return BIB_ENGINE_WRONG_THREAD;
    try {
        std::optional<N::ActionRequest> action;
        auto request=decodedRequest(s,worker,expected,query,operation,sequence,input,action);
        return request && validBytes(reply,BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY)
            && s.publisher->matchesOwnedReply(*request,bytes(*reply)) ? BIB_ENGINE_OK : BIB_ENGINE_INVALID;
    } catch (...) { return BIB_ENGINE_INVALID; }
}
std::int32_t retireMetadata(void* raw, std::uint64_t worker, const BibEngineCommandV1* original)
{
    auto& s=*static_cast<State*>(raw);
    // No decode/allocation/Session.thread/live getter/Host/Bridge here. The guard
    // supplies its exact OWNED original action, not an untrusted ACK echo.
    if (!owner(s) || worker != s.worker || !worker || !s.publisher || !original
        || original->size != sizeof(*original) || original->operation != BIB_ENGINE_COMMAND_FORM_ACTION_V2
        || !identity(original->expected) || original->expected.application_instance != s.instance
        || !original->request_sequence || original->request_sequence > BIB_ENGINE_DOCUMENT_V2_MAX_ORDINARY_SEQUENCE
        || std::memcmp(original->schema_sha256,D::schema.data(),32)
        || !validBytes(&original->payload,BIB_ENGINE_DOCUMENT_V2_MAX_ACTION_BYTES)) return BIB_ENGINE_INVALID;
    return s.publisher->retireActionMetadata(nativeIdentity(original->expected),original->request_sequence,
        bytes(original->payload)) ? BIB_ENGINE_OK : BIB_ENGINE_INVALID;
}
std::int32_t preflight(void* raw, const BibEngineStartV1* start) noexcept
{
    if (!raw) return BIB_ENGINE_INVALID;
    // Guard calls this while NOT_RETAINED, before Host/config/owner commitment.
    // The first eligible getter chose this immutable native binding owner.
    if (!owner(*static_cast<const State*>(raw))) return BIB_ENGINE_WRONG_THREAD;
    return start ? validateActualStart(*start) : BIB_ENGINE_INVALID;
}
std::int32_t install(void* raw, const BibEngineHostV1* host, const BibEngineStartV1* start, std::uint64_t instance)
{
    auto& s=*static_cast<State*>(raw);
    if (!owner(s) || !host || !start || s.installed || instance != s.instance) return BIB_ENGINE_INVALID;
    s.host=*host;
    s.adapters=std::make_unique<LegacyHostAdapters>(*host,start->limits,s.retention);
    if (!s.adapters->valid() || !s.adapters->supports_resources() || !s.adapters->supports_services()) return BIB_ENGINE_INVALID;
    s.services=s.adapters->service_hooks(); s.resources=s.adapters->resource_bundle_hooks();
    if (bib_app_resources_install_bundle(&s.resources,start->entry_url.data,start->entry_url.length,instance))
        return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    s.installed=true;
    return BIB_ENGINE_OK;
}
std::int32_t start(void* raw, const BibEngineHostV1*, const BibEngineStartV1* config, std::uint64_t instance)
{
    auto& s=*static_cast<State*>(raw);
    if (!owner(s) || !config || !s.installed || s.started || instance != s.instance || faulted(s)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    if (bib_foundation_services_install(&s.services)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    s.started=true;
    const BIB::ProviderRuntimeConfig runtime{&s.host,instance,config->persist_seed,config->raster_output};
    const auto result=BIB::bibProviderCreatePage(runtime);
    return faulted(s) ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : result;
}
std::int32_t advance(void* raw, const BibEngineAdvanceV1* request)
{
    auto& s=*static_cast<State*>(raw);
    if (!owner(s) || !request || faulted(s)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    const auto result=BIB::bibProviderDocumentAdvance(request->render);
    return faulted(s) ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : result;
}
std::int32_t current(void* raw, std::uint64_t instance, BibEngineDocumentV1* output)
{
    auto& s=*static_cast<State*>(raw);
    if (!owner(s)) return BIB_ENGINE_WRONG_THREAD;
    if (!output || instance != s.instance) return BIB_ENGINE_INVALID;
    if (faulted(s)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    BibAppDocumentIdentityV1 id{}; id.size=sizeof(id); id.version=BIB_APP_DOCUMENT_IDENTITY_VERSION;
    const auto result=bib_app_resources_current_identity(&id);
    if (result != 1) return result ? BIB_ENGINE_WRONG_THREAD : BIB_ENGINE_STALE;
    if (id.application_instance != instance || !id.document_sequence || !id.service_generation) return BIB_ENGINE_STALE;
    *output=BIB::bibProviderProjectDocument(id); // Resource epoch is a separate private checkpoint fence.
    return BIB_ENGINE_OK;
}
std::int32_t query(void* raw, const BibEngineQueryV1* request, BibEngineReplyBufferV1* destination,
    BibEngineQueryResultV1* output)
{
    auto& s=*static_cast<State*>(raw);
    if (!owner(s) || !request || !destination || !output || faulted(s)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    if (request->kind != BIB_ENGINE_QUERY_DOCUMENT_FORMS_V2 || !destination->bytes
        || destination->capacity < N::maxReplyBytes || !validBytes(&request->payload,BIB_ENGINE_DOCUMENT_V2_QUERY_BYTES)) return BIB_ENGINE_INVALID;
    // ProviderGuard owns the whole Host turn. Bridge precedes JSLock so its
    // final unlock and native checkpoints settle before Bridge.leave.
    BIB::FoundationServiceEngineCall bridge;
    if (!bridge) return BIB_ENGINE_REENTRANT;
    {
        JSC::JSLockHolder lock(WebCore::commonVM());
        auto reply=s.publisher->queryPacket(bytes(request->payload),destination->capacity);
        const auto packet=reply->bytes();
        auto decoded=N::decodeReply(packet);
        std::memcpy(destination->bytes,packet.data(),packet.size());
        output->bytes_written=static_cast<std::uint32_t>(packet.size());
        output->semantic_revision=decoded.publication.version.revision;
        output->document=request->expected;
    }
    bridge.finish();
    return faulted(s) ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : BIB_ENGINE_OK;
}
std::int32_t command(void* raw, const BibEngineCommandV1* request, BibEngineReplyBufferV1* destination,
    BibEngineCommandResultV1* output)
{
    auto& s=*static_cast<State*>(raw);
    if (!owner(s) || !request || !destination || !output || faulted(s)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    // ACK7 is exclusively Guard metadata; physical commands unsupported1795.
    if (request->operation != BIB_ENGINE_COMMAND_FORM_ACTION_V2 || !destination->bytes
        || destination->capacity < N::maxReplyBytes || !validBytes(&request->payload,BIB_ENGINE_DOCUMENT_V2_MAX_ACTION_BYTES)) return BIB_ENGINE_UNSUPPORTED;
    BIB::FoundationServiceEngineCall bridge;
    if (!bridge) return BIB_ENGINE_REENTRANT;
    {
        JSC::JSLockHolder lock(WebCore::commonVM());
        auto reply=s.publisher->executePacket(bytes(request->payload),destination->capacity);
        const auto packet=reply->bytes();
        // Producer schema offset50 is effects/popup flags. Deep semantic decode
        // and exact owned comparison run in validateReply after this return.
        if (packet.size()<52) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
        std::memcpy(destination->bytes,packet.data(),packet.size());
        output->bytes_written=static_cast<std::uint32_t>(packet.size());
        output->handled=(packet[50]&1u) ? 1u : 0u;
    }
    bridge.finish();
    return faulted(s) ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : BIB_ENGINE_OK;
}
std::int32_t deliveryStatus(int value) {
    switch (value) {
    case BIB_FOUNDATION_SERVICE_DELIVERY_ACCEPTED: return BIB_ENGINE_OK;
    case BIB_FOUNDATION_SERVICE_DELIVERY_STALE: return BIB_ENGINE_STALE;
    case BIB_FOUNDATION_SERVICE_DELIVERY_WRONG_THREAD: return BIB_ENGINE_WRONG_THREAD;
    default: return BIB_ENGINE_INVALID;
    }
}
std::int32_t deliver(void* raw, const BibEngineDocumentV1* document, const BibEngineBytesV1* input)
{
    auto& s=*static_cast<State*>(raw);
    if (!owner(s) || !document || !input || faulted(s)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    // Existing service export owns its Bridge/VM scope; don't add a second one.
    auto result=deliveryStatus(bib_foundation_services_deliver(document->service_generation,input->data,input->length));
    if (!faulted(s)) s.host.wake(s.host.context);
    return faulted(s) ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : result;
}
std::uint32_t collect(void* raw, const BibEngineDocumentV1* document)
{
    auto& s=*static_cast<State*>(raw);
    if (!owner(s) || faulted(s)) return 14u;
    const auto result=document ? bib_foundation_services_collect_ack(document->service_generation) : 2u;
    if (!faulted(s)) s.host.wake(s.host.context);
    return faulted(s) ? 14u : result;
}
std::int32_t dispose(void* raw, std::uint64_t instance, std::uint64_t generation)
{
    auto& s=*static_cast<State*>(raw);
    if (!owner(s) || instance != s.instance || !generation) return BIB_ENGINE_INVALID;
    if (faulted(s)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    auto result=deliveryStatus(bib_foundation_services_dispose_retired(generation));
    if (!faulted(s)) s.host.wake(s.host.context);
    return faulted(s) ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : result;
}
} // namespace

namespace {
// Not exposed separately: ONLY bindingOnce's winning metadata-only factory may
// install the actual State. No caller can bypass the one-shot owner policy.
std::int32_t bindNativeDocumentProvider()
{
    const auto& build = M::build;
    const auto& limits = M::limits;
    const auto retention = M::retention;
    if (state || !M::metadataValid()
        || build.target_system != BIB_ENGINE_TARGET_LINUX
        || (build.target_processor != BIB_ENGINE_CPU_X86_64 && build.target_processor != BIB_ENGINE_CPU_AARCH64)
        || build.pointer_bits != 64 || build.fixed_viewport_width != 800 || build.fixed_viewport_height != 600
        || build.capabilities != D::capabilities || std::memcmp(build.contract_header_sha256,D::contract.data(),32)
        || retention.max_retained_calls != 64 || retention.max_retained_bytes != 4194304 || !actualResourceLimits(limits)
        || limits.maximum_command_bytes != 65536 || limits.maximum_query_bytes != 65536
        || limits.maximum_reply_bytes != N::maxReplyBytes || limits.maximum_service_message_bytes != 1048576)
        return BIB_ENGINE_UNSUPPORTED;
    // Fresh runtime-local descriptor identities, never author/resource-selected
    // and never emitted in compile-time metadata. No cross-process uniqueness claim.
    const auto instance = reserveRuntimeIdentity();
    const auto worker = reserveRuntimeIdentity();
    if (!instance || !worker) return BIB_ENGINE_LIMIT;
    try {
        auto candidate=std::make_unique<State>();
        candidate->build=build; candidate->limits=limits; candidate->retention=retention;
        candidate->worker=worker; candidate->instance=instance;
        auto* retained=candidate.get();
        C::Hooks nativeHooks;
        nativeHooks.onEngineThread=[retained] { return owner(*retained); };
        nativeHooks.foreground=[] {
            auto frame=BIB::bibProviderDocumentMainFrame();
            return frame && frame->document() && BIB::bibProviderDocumentForeground(*frame->document());
        };
        nativeHooks.inputMethodEnabled=[]() -> std::optional<bool> {
            auto frame=BIB::bibProviderDocumentMainFrame();
            return frame && frame->document() ? BIB::bibProviderDocumentInputMethodState(*frame->document()) : std::nullopt;
        };
        // No native popup owner: Publisher explicitly strips select-one authority.
        candidate->session=std::make_unique<C::Session>(std::move(nativeHooks));
        C::PublisherHooks hooks;
        hooks.currentFrame=[] { return BIB::bibProviderDocumentMainFrame(); };
        hooks.captureCheckpoint=[](const C::Context& exact) {
            return exact.frame && exact.document && BIB::bibProviderDocumentCheckpoint(*exact.frame,*exact.document,
                exact.version.generation,exact.documentSequence,exact.version.epoch,exact.resourceEpoch);
        };
        candidate->publisher=std::make_unique<C::Publisher>(*candidate->session,std::move(hooks));
        EnginePrivateV1 engine{sizeof(EnginePrivateV1),private_interface_version,build,limits,instance,candidate.get(),
            D::commands.data(),static_cast<std::uint32_t>(D::commands.size()),
            D::queries.data(),static_cast<std::uint32_t>(D::queries.size()),
            preflight,start,advance,current,command,query,deliver,collect,dispose,install};
        EngineDocumentPrivateV1 document{sizeof(EngineDocumentPrivateV1),document_private_interface_version,
            document_pixel_profile,0,worker,D::base_header,D::extension_header,D::contract,D::catalog,{},
            validateRequest,validateReply,retireMetadata};
        auto status=bind_engine_document_private(engine,document);
        if (status) return status;
        state=candidate.release();
        return BIB_ENGINE_OK;
    } catch (const std::bad_alloc&) { return BIB_ENGINE_LIMIT; }
    catch (...) { return BIB_ENGINE_PROCESS_EXIT_REQUIRED; }
}
} // namespace

std::int32_t ensureNativeDocumentProviderBound() noexcept
{
    return bindingOnce.ensure([] { return bindNativeDocumentProvider(); },
        []() noexcept { return state && owner(*state); });
}
} // namespace bib::provider_candidate

namespace BIB {
bool bibProviderSetProspectiveDocument(std::uint64_t sequence) noexcept
{
    using namespace bib::provider_candidate;
    return state && owner(*state) && state->adapters && sequence && !faulted(*state)
        && state->adapters->set_prospective_document({state->instance,sequence,0}) == BIB_ENGINE_OK;
}
void bibProviderDocumentAuthorityWillChange() noexcept
{
    using namespace bib::provider_candidate;
    // Wrapper notifies only its serialized actual owner before authority moves.
    // No native lookup or Host callback occurs; preserve retained completion.
    if (state && owner(*state) && state->publisher) state->publisher->invalidateAuthority();
}
} // namespace BIB
