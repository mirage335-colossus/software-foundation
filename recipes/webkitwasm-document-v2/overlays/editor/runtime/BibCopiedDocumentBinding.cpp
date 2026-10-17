// SPDX-License-Identifier: CC0-1.0
// NEW explicit1795/2003/2035 overlay. Actual WebCore source is unparsed/unqualified.
#include "config.h"
#include "BibCopiedDocumentBinding.hpp"
#include "BibCopiedDocumentCatalog.hpp"
#include "BibDocumentPhysicalProvider.hpp"
#ifndef BIB_ENGINE_PROVIDER_EDITOR_V1
#define BIB_ENGINE_PROVIDER_EDITOR_V1 0
#endif
#if (BIB_ENGINE_PROVIDER_EDITOR_V1) != 0 && (BIB_ENGINE_PROVIDER_EDITOR_V1) != 1
#error "BIB_ENGINE_PROVIDER_EDITOR_V1 must evaluate to0 or1"
#endif
#if (BIB_ENGINE_PROVIDER_EDITOR_V1)
#include "BibNativeEditorBackend.hpp"
#include "BibNativeEditorWireAdapter.hpp"
#endif
#include "BibEngineProviderPreflight.h"
#include "BibEngineProviderRuntime.h"
#include "BibEngineProviderLifecycleHooks.h"
#include "BibEngineProviderDocumentProjection.h"
#include "BibAppResources.h"
#include "BibFoundationServiceBridge.h"
#include "ui/BibEngineUiOwner.hpp"
#include "popup/BibNativePopupOwner.hpp"
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

#if !defined(__EMSCRIPTEN__) || !BIB_ENGINE_PROVIDER_NEUTRAL || BIB_PTHREAD || !BIB_ENGINE_PROVIDER_DOCUMENT_V2
#error "Document binding requires an explicit non-pthread copied document composition"
#endif

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
    DocumentBindingProfile profile{DocumentBindingProfile::pixel};
    std::atomic<bool> binding_fault{};
    BibEngineHostV1 host{};
    std::unique_ptr<LegacyHostAdapters> adapters;
    BibFoundationServiceHostV1 services{};
    BibAppResourceBundleHostV1 resources{};
    std::unique_ptr<C::Session> session;
    std::unique_ptr<C::Publisher> publisher;
    std::unique_ptr<ModernDocumentPhysicalProvider> physical;
    NativeDocumentPhysicalCallbacks physical_callbacks{};
#if (BIB_ENGINE_PROVIDER_EDITOR_V1)
    std::unique_ptr<NativeEditorBackend> editor;
    std::unique_ptr<NativeEditorWireAdapter> editor_wire;
#endif
    bool installed{}, started{};
};
// Process lifetime. No reset/unload/destructor cleanup export is provided.
State* state;
std::atomic<std::uint64_t> next_instance{1};
bool owner(const State& s) noexcept { return s.owner == std::this_thread::get_id(); }
bool faulted(const State& s) noexcept {
    return BIB::EngineUI::faulted() || s.binding_fault.load(std::memory_order_acquire)
        || (s.adapters && s.adapters->callback_faulted());
}
bool physicalProfile(DocumentBindingProfile value) noexcept {
    return value==DocumentBindingProfile::physical || value==DocumentBindingProfile::editor;
}
bool physicalOwner(void* raw) noexcept { return raw && owner(*static_cast<State*>(raw)); }
void uiOwnerFault(void* raw) noexcept {
    if (raw) static_cast<State*>(raw)->binding_fault.store(true,std::memory_order_release);
}
#if (BIB_ENGINE_PROVIDER_EDITOR_V1)
void uiOwnerModalChanged(void* raw) noexcept {
    if (!raw) { BIB::EngineUI::fault(); return; }
    auto& s=*static_cast<State*>(raw);
    if (!owner(s)) { BIB::EngineUI::fault(); return; }
    // Preserve the trusted popup action's Publisher serial and retained ACKs.
    // The wire adapter delegates exactly once to the backend.
    if (s.editor_wire) s.editor_wire->invalidate_metadata();
    else if (s.editor) s.editor->invalidate_metadata();
    else BIB::EngineUI::fault();
}
#endif
bool physicalFaulted(void* raw) noexcept { return !raw || faulted(*static_cast<State*>(raw)); }
void physicalWake(void* raw) noexcept {
    auto& s=*static_cast<State*>(raw);
    if (!owner(s) || faulted(s) || !s.host.wake) { s.binding_fault.store(true,std::memory_order_release); return; }
    // The callback table has no error result. Keep a sticky authority fault on
    // natural C++ failure; never let noexcept manufacture a successful action.
    try { s.host.wake(s.host.context); }
    catch (...) { s.binding_fault.store(true,std::memory_order_release); }
}
void editorInvalidateForms(void* raw) noexcept {
    auto& s=*static_cast<State*>(raw);
    if (!owner(s) || !s.publisher) { s.binding_fault.store(true,std::memory_order_release); return; }
    s.publisher->invalidateAuthority(); // Editor effects revoke forms, never themselves recursively.
}
void physicalInvalidateForms(void* raw) noexcept {
    auto& s=*static_cast<State*>(raw);
    editorInvalidateForms(raw);
    if (!owner(s)) return;
#if (BIB_ENGINE_PROVIDER_EDITOR_V1)
    // Preserve native retirement material. The adapter delegates exactly one
    // metadata invalidation to its backend; no DOM cancellation occurs here.
    if (s.editor_wire) s.editor_wire->invalidate_metadata();
    else if (s.editor) s.editor->invalidate_metadata();
#endif
}
#if (BIB_ENGINE_PROVIDER_EDITOR_V1)
bool editorPhysicalAuthority(void* raw, const BibEngineDocumentV1* expected,
    std::uint64_t* context) noexcept
{
    if (!raw || !expected || !context) return false;
    auto& s=*static_cast<State*>(raw);
    return owner(s) && !faulted(s) && s.physical && s.physical->editor_authority(*expected,*context);
}
std::int32_t editorAdmit(void* raw, std::uint64_t worker, const BibEngineDocumentV1* expected,
    std::uint32_t domain, std::uint32_t operation, std::uint64_t sequence, const BibEngineBytesV1* input)
{
    auto& s=*static_cast<State*>(raw);
    if (!owner(s)) return BIB_ENGINE_WRONG_THREAD;
    return s.editor_wire && !faulted(s)
        ? s.editor_wire->admit_request(worker,expected,domain,operation,sequence,input)
        : BIB_ENGINE_PROCESS_EXIT_REQUIRED;
}
std::int32_t editorValidate(void* raw, std::uint64_t worker, const BibEngineDocumentV1* expected,
    std::uint32_t domain, std::uint32_t operation, std::uint64_t sequence,
    const BibEngineBytesV1* input, const BibEngineBytesV1* reply)
{
    auto& s=*static_cast<State*>(raw);
    if (!owner(s)) return BIB_ENGINE_WRONG_THREAD;
    return s.editor_wire && !faulted(s)
        ? s.editor_wire->validate_reply(worker,expected,domain,operation,sequence,input,reply)
        : BIB_ENGINE_PROCESS_EXIT_REQUIRED;
}
std::int32_t editorProject(void* raw, std::uint64_t worker, const BibEngineQueryV1* request,
    BibEngineReplyBufferV1* destination, BibEngineQueryResultV1* output)
{
    auto& s=*static_cast<State*>(raw);
    if (!owner(s) || !s.editor_wire || faulted(s)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    const auto status=s.editor_wire->project(worker,request,destination,output);
    return faulted(s) ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : status;
}
std::int32_t editorApply(void* raw, std::uint64_t worker, const BibEngineCommandV1* request,
    BibEngineReplyBufferV1* destination, BibEngineCommandResultV1* output)
{
    auto& s=*static_cast<State*>(raw);
    if (!owner(s) || !s.editor_wire || faulted(s)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    const auto status=s.editor_wire->apply(worker,request,destination,output);
    return faulted(s) ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : status;
}
std::int32_t editorRevoke(void* raw, std::uint64_t worker, const BibEngineCommandV1* request,
    BibEngineReplyBufferV1* destination, BibEngineCommandResultV1* output)
{
    auto& s=*static_cast<State*>(raw);
    if (!owner(s) || !s.editor_wire || faulted(s)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    const auto status=s.editor_wire->revoke(worker,request,destination,output);
    return faulted(s) ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : status;
}
#endif
bool physicalOperation(std::uint32_t operation) noexcept { return operation==1 || operation==3 || operation==5; }
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
// Build an exact OWNED-input view for the private modern validator. Guard has
// already checked schema/catalog shape; the selected catalog supplies the same
// immutable schema rather than allowing focus3 to alias semantic query3.
std::optional<BibEngineCommandV1> physicalRequest(const State& s, std::uint64_t worker,
    const BibEngineDocumentV1* expected, std::uint32_t operation, std::uint64_t sequence,
    const BibEngineBytesV1* input)
{
    if (!owner(s) || !physicalProfile(s.profile) || worker!=s.worker || !worker
        || !expected || !identity(*expected) || expected->application_instance!=s.instance
        || !sequence || sequence>BIB_ENGINE_DOCUMENT_V2_MAX_ORDINARY_SEQUENCE || !s.physical
        || !physicalOperation(operation)) return std::nullopt;
    const auto found=std::find_if(D::physical_inputs.begin(),D::physical_inputs.end(),
        [operation](const auto& facts) { return facts.kind==operation; });
    if (found==D::physical_inputs.end() || !validBytes(input,found->maximum_input_bytes)) return std::nullopt;
    BibEngineCommandV1 command{}; command.size=sizeof(command); command.operation=operation;
    command.expected=*expected; command.request_sequence=sequence;
    std::copy(found->schema.begin(),found->schema.end(),command.schema_sha256); command.payload=*input;
    return command;
}
std::int32_t validateRequest(void* raw, std::uint64_t worker, const BibEngineDocumentV1* expected,
    std::uint32_t query, std::uint32_t operation, std::uint64_t sequence, const BibEngineBytesV1* input)
{
    auto& s=*static_cast<State*>(raw);
    if (!owner(s)) return BIB_ENGINE_WRONG_THREAD;
    if (!query && physicalOperation(operation)) {
        auto command=physicalRequest(s,worker,expected,operation,sequence,input);
        return command ? s.physical_callbacks.validate_cached_request(s.physical_callbacks.context,worker,&*command)
            : BIB_ENGINE_INVALID;
    }
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
    if (!query && physicalOperation(operation)) {
        auto command=physicalRequest(s,worker,expected,operation,sequence,input);
        return command && validBytes(reply,16) && !reply->length
            ? s.physical_callbacks.validate_cached_reply(s.physical_callbacks.context,worker,&*command,reply)
            : BIB_ENGINE_INVALID;
    }
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
std::int32_t preflight(void*, const BibEngineStartV1* start) {
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
    // Bind the retained actual owner only at START, before Page/Chrome creation.
    BIB::EngineUI::OwnerHooks uiHooks{&s,physicalOwner,uiOwnerFault,nullptr};
#if (BIB_ENGINE_PROVIDER_EDITOR_V1)
    if (s.profile==DocumentBindingProfile::editor) uiHooks.modal_changed=uiOwnerModalChanged;
#endif
    if (!BIB::EngineUI::bindOwner({s.worker,s.worker,s.instance},uiHooks)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
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
    if (physicalOperation(request->operation)) {
        if (!physicalProfile(s.profile) || !s.physical) return BIB_ENGINE_UNSUPPORTED;
        // The modern object owns its Bridge-before-JSLock and live native
        // fences. No second Bridge, decode-as-NDV2 or replay is added here.
        const auto status=s.physical_callbacks.command(s.physical_callbacks.context,request,destination,output);
        return faulted(s) ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : status;
    }
    // ACK7 remains exclusively Guard metadata. Pixel1795 has no physical catalog.
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

std::int32_t bindActualWebCoreDocumentProvider(const BibEngineBuildV1& build, const BibEngineLimitsV1& limits,
    ServiceRetentionLimits retention, std::uint64_t worker, DocumentBindingProfile profile) noexcept
{
    const bool editor=profile==DocumentBindingProfile::editor;
    const bool physical=physicalProfile(profile);
#if !(BIB_ENGINE_PROVIDER_EDITOR_V1)
    if (editor) return BIB_ENGINE_UNSUPPORTED;
#endif
    if (state || (profile!=DocumentBindingProfile::pixel && !physical) || !worker
        || build.target_system != BIB_ENGINE_TARGET_BROWSER_WASM || build.target_processor != BIB_ENGINE_CPU_WASM32
        || build.pointer_bits != 32 || build.fixed_viewport_width != 800 || build.fixed_viewport_height != 600
        || build.capabilities != (editor ? D::editor_capabilities : physical ? D::physical_capabilities : D::capabilities)
        || std::memcmp(build.contract_header_sha256,(editor ? D::editor_contract : D::contract).data(),32)
        || !retention.max_retained_calls || retention.max_retained_bytes < 64 || !actualResourceLimits(limits)
        || limits.maximum_command_bytes < (editor ? BIB_ENGINE_EDITOR_MAX_WIRE_BYTES : BIB_ENGINE_DOCUMENT_V2_MAX_ACTION_BYTES)
        || limits.maximum_query_bytes < (editor ? BIB_ENGINE_EDITOR_MAX_QUERY_BYTES : BIB_ENGINE_DOCUMENT_V2_QUERY_BYTES) || limits.maximum_reply_bytes < N::maxReplyBytes
        || limits.maximum_service_message_bytes < 384) return BIB_ENGINE_UNSUPPORTED;
    auto instance=next_instance.load(std::memory_order_relaxed);
    do { if (!instance || instance == UINT64_MAX) return BIB_ENGINE_LIMIT; }
    while (!next_instance.compare_exchange_weak(instance,instance+1,std::memory_order_relaxed));
    try {
        auto candidate=std::make_unique<State>();
        candidate->build=build; candidate->limits=limits; candidate->retention=retention;
        candidate->worker=worker; candidate->instance=instance; candidate->profile=profile;
        auto* retained=candidate.get();
        C::Hooks nativeHooks;
        nativeHooks.onEngineThread=[retained] { return owner(*retained) && !faulted(*retained); };
        nativeHooks.foreground=[] {
            auto frame=BIB::bibProviderDocumentMainFrame();
            return frame && frame->document() && BIB::bibProviderDocumentForeground(*frame->document());
        };
        nativeHooks.inputMethodEnabled=[]() -> std::optional<bool> {
            auto frame=BIB::bibProviderDocumentMainFrame();
            return frame && frame->document() ? BIB::bibProviderDocumentInputMethodState(*frame->document()) : std::nullopt;
        };
        nativeHooks.openNativeUserPopup=BIB::EnginePopup::openUserPopup;
        candidate->session=std::make_unique<C::Session>(std::move(nativeHooks));
        C::PublisherHooks hooks;
        hooks.currentFrame=[] { return BIB::bibProviderDocumentMainFrame(); };
        hooks.captureCheckpoint=[](const C::Context& exact) {
            return exact.frame && exact.document && BIB::bibProviderDocumentCheckpoint(*exact.frame,*exact.document,
                exact.version.generation,exact.documentSequence,exact.version.epoch,exact.resourceEpoch);
        };
        candidate->publisher=std::make_unique<C::Publisher>(*candidate->session,std::move(hooks));
        if (physical) {
            const DocumentPhysicalHooks physicalHooks{retained,physicalOwner,physicalFaulted,physicalWake,physicalInvalidateForms};
            candidate->physical=std::make_unique<ModernDocumentPhysicalProvider>(worker,instance,physicalHooks);
            candidate->physical_callbacks=candidate->physical->callbacks();
            const auto& callbacks=candidate->physical_callbacks;
            if (callbacks.size!=sizeof(callbacks) || callbacks.version!=document_physical_callbacks_version
                || !callbacks.context || !callbacks.validate_cached_request || !callbacks.validate_cached_reply
                || !callbacks.command || !callbacks.invalidate_authority) return BIB_ENGINE_UNSUPPORTED;
        }
#if (BIB_ENGINE_PROVIDER_EDITOR_V1)
        if (editor) {
            NativeEditorHooks editorHooks;
            editorHooks.context=retained;
            editorHooks.on_owner=physicalOwner;
            editorHooks.callback_faulted=physicalFaulted;
            editorHooks.queue_wake=physicalWake;
            editorHooks.invalidate_form_authority=editorInvalidateForms;
            editorHooks.physical_authority=editorPhysicalAuthority;
            editorHooks.surface_identity=[retained](std::uint64_t native_context)
                -> std::optional<foundation::gui_surface::Identity> {
                if (!owner(*retained) || faulted(*retained) || !retained->editor_wire) return std::nullopt;
                return retained->editor_wire->entered_surface_identity(native_context);
            };
            // Both constructors are inert. The identity hook is unavailable
            // until the adapter enters an exact owned decoded operation.
            candidate->editor=std::make_unique<NativeEditorBackend>(worker,instance,std::move(editorHooks));
            candidate->editor_wire=std::make_unique<NativeEditorWireAdapter>(worker,instance,*candidate->editor);
        }
#endif
        EnginePrivateV1 engine{sizeof(EnginePrivateV1),private_interface_version,build,limits,instance,candidate.get(),
            editor ? D::editor_commands.data() : physical ? D::physical_commands.data() : D::commands.data(),
            static_cast<std::uint32_t>(editor ? D::editor_commands.size() : physical ? D::physical_commands.size() : D::commands.size()),
            editor ? D::editor_queries.data() : D::queries.data(),
            static_cast<std::uint32_t>(editor ? D::editor_queries.size() : D::queries.size()),
            preflight,start,advance,current,command,query,deliver,collect,dispose,install};
        EngineDocumentPrivateV1 document{sizeof(EngineDocumentPrivateV1),document_private_interface_version,
            physical ? document_physical_profile : document_pixel_profile,0,worker,
            D::base_header,D::extension_header,D::contract,D::catalog,physical ? D::physical_catalog : std::array<std::uint8_t,32>{},
            validateRequest,validateReply,retireMetadata};
        std::int32_t status;
#if (BIB_ENGINE_PROVIDER_EDITOR_V1)
        if (editor) {
            EngineEditorPrivateV1 edit{sizeof(EngineEditorPrivateV1),editor_private_interface_version,0,0,worker,
                D::editor_header,D::editor_contract,D::editor_catalog,D::editor_schema,
                editorAdmit,editorValidate,editorProject,editorApply,editorRevoke};
            status=bind_engine_editor_private(engine,document,edit);
        } else
#endif
            status=bind_engine_document_private(engine,document);
        if (status) return status;
        state=candidate.release();
        return BIB_ENGINE_OK;
    } catch (...) { return BIB_ENGINE_LIMIT; }
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
    // Retire popup authority before shared and cached document authority.
    if (!state) return;
    if (!owner(*state)) { state->binding_fault.store(true,std::memory_order_release); return; }
    BIB::EnginePopup::retireAuthority();
    BIB::EngineUI::retireDocumentAuthority();
    if (state->publisher) state->publisher->invalidateAuthority();
#if (BIB_ENGINE_PROVIDER_EDITOR_V1)
    // Revoke editor metadata before portable physical context retirement.
    // Actual native navigation retirement attestation belongs to the backend,
    // never a fabricated success from this metadata notification.
    if (state->editor_wire) state->editor_wire->invalidate_metadata();
    else if (state->editor) state->editor->invalidate_metadata();
#endif
    if (state->physical) state->physical_callbacks.invalidate_authority(state->physical_callbacks.context);
}
} // namespace BIB
