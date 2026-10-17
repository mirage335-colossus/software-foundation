// SPDX-License-Identifier: CC0-1.0
// Explicit compiled document-profile composition; no engine runtime proof implied.
#include "BibEngineDocumentWasmShim.h"
#include "BibEngineCopiedHost.h"
#include "BibEngineCopiedDocumentDispatch.hpp"
#include "BibEngineCopiedDocumentFacts.h"
#include "BibCopiedDocumentBinding.hpp"
#include "BibCopiedDocumentMetadata.generated.h"
#include <atomic>
#include <climits>
#include <cstring>
#include <new>
#include <string_view>
#include <thread>

#ifndef BIB_ENGINE_PROVIDER_EDITOR_V1
#define BIB_ENGINE_PROVIDER_EDITOR_V1 0
#endif
#if (BIB_ENGINE_PROVIDER_EDITOR_V1) != 0 && (BIB_ENGINE_PROVIDER_EDITOR_V1) != 1
#error "BIB_ENGINE_PROVIDER_EDITOR_V1 must be exactly zero or one"
#endif

#if !defined(__EMSCRIPTEN__) || defined(__EMSCRIPTEN_PTHREADS__) || BIB_PTHREAD || !BIB_ENGINE_PROVIDER_NEUTRAL
#error "The document copied shim requires the explicit non-pthread browser CPU provider"
#endif
static_assert(sizeof(void*)==4 && CHAR_BIT==8);

extern "C" int32_t bib_engine_copied_host_v1(uint32_t,const uint8_t*,uint32_t,uint8_t*,uint32_t);
namespace {
using bib::copied::CopiedDocumentDispatch;
using bib::copied::CopiedHost;
enum class Phase : unsigned char { unconfigured, configuring, configured, failed, poisoned };
std::atomic<Phase> phase{Phase::unconfigured};
// This metadata-only initialization records the module's owner thread. It binds
// no provider and invokes no Page, VM, Host, resources or Registry operation.
const std::thread::id owner=std::this_thread::get_id();
CopiedHost* copiedHost;
CopiedDocumentDispatch* copiedDispatch;

[[noreturn]] void fatal(void*,const char*) noexcept {
    phase.store(Phase::poisoned,std::memory_order_relaxed);
    __builtin_trap();
}
int32_t imported(void*,uint32_t operation,const uint8_t* input,uint32_t length,
                 uint8_t* output,uint32_t capacity) {
    if (phase.load(std::memory_order_relaxed)!=Phase::configured)
        fatal(nullptr,"Document bootstrap import outside configured dispatch");
    return bib_engine_copied_host_v1(operation,input,length,output,capacity);
}
bool localSpan(const void* pointer,uint32_t size) noexcept {
    const auto begin=static_cast<uint64_t>(reinterpret_cast<uintptr_t>(pointer));
    const auto bytes=static_cast<uint64_t>(__builtin_wasm_memory_size(0))*UINT64_C(65536);
    return (!size || pointer) && begin<=bytes && static_cast<uint64_t>(size)<=bytes-begin;
}
bool providerComplete(const BibEngineProviderV1& provider) noexcept {
    return provider.size==sizeof(provider) && provider.abi_major==1 && provider.abi_minor==1 && !provider.reserved
        && provider.start && provider.advance && provider.current_document && provider.command && provider.query
        && provider.deliver_services && provider.collect_service_ack && provider.dispose_retired_service_document;
}
int32_t failed(int32_t status) noexcept {
    phase.store(status==BIB_ENGINE_PROCESS_EXIT_REQUIRED ? Phase::poisoned : Phase::failed,std::memory_order_relaxed);
    return status;
}
constexpr bool compiledProfileEnabled() noexcept {
    using namespace foundation::appended::document_copied_metadata;
    // The editor backend is a separate explicit build opt-in. Document-v2
    // support, capability bits and other profile flags cannot enable it.
    return bib::copied::documentCopiedProfileEnabled(compiled_profile,
        (BIB_ENGINE_PROVIDER_EDITOR_V1)==1);
}
constexpr bool matchesExport(bool editor_export) noexcept {
    using namespace foundation::appended::document_copied_metadata;
    return (compiled_profile==bib::copied::DocumentCopiedProfile::editor)==editor_export;
}

int32_t copyFacts(bool editor_export,uint8_t* output,uint32_t capacity) {
    using namespace foundation::appended::document_copied_metadata;
    // No metadata C getter or allocator is consulted once this endpoint fails
    // or poisons. The only actions then available are host evidence/termination.
    const auto current=phase.load(std::memory_order_relaxed);
    if (current==Phase::poisoned) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    if (current==Phase::failed) return BIB_ENGINE_CLOSED;
    if (current==Phase::configuring) return BIB_ENGINE_REENTRANT;
    if (!matchesExport(editor_export) || !compiledProfileEnabled()) return BIB_ENGINE_UNSUPPORTED;
    if (!metadataValid()) return BIB_ENGINE_INVALID;
    constexpr std::size_t length=sizeof(profile_json)-1;
    static_assert(length<=bib::copied::documentCopiedFactsCapacity);
    if (capacity<length) return BIB_ENGINE_LIMIT;
    if (!localSpan(output,capacity)) return BIB_ENGINE_INVALID;
    std::memcpy(output,profile_json,length);
    return static_cast<int32_t>(length);
}

int32_t configureWorker(bool editor_export,uint32_t worker_lo,uint32_t worker_hi) {
    using namespace foundation::appended::document_copied_metadata;
    Phase expected=Phase::unconfigured;
    // Burn the only attempt BEFORE checking its inputs, binding or allocating.
    // Reentry/partial binding cannot turn into a second configure path.
    if (!phase.compare_exchange_strong(expected,Phase::configuring,std::memory_order_relaxed))
        return expected==Phase::poisoned ? BIB_ENGINE_PROCESS_EXIT_REQUIRED
            : expected==Phase::configuring ? BIB_ENGINE_REENTRANT : BIB_ENGINE_CLOSED;
    if (std::this_thread::get_id()!=owner) return failed(BIB_ENGINE_WRONG_THREAD);
    const uint64_t worker=uint64_t(worker_lo) | (uint64_t(worker_hi)<<32);
    if (!matchesExport(editor_export) || !compiledProfileEnabled()) return failed(BIB_ENGINE_UNSUPPORTED);
    if (!worker || !metadataValid()) return failed(BIB_ENGINE_INVALID);
    // Generated metadata chooses the profile. Capability bits and input JSON
    // only prove agreement; neither can change this selection or downgrade it.
    auto binding_profile=bib::provider_candidate::DocumentBindingProfile::pixel;
    auto wire_profile=bib::copied::DocumentWireProfile::pixel;
    switch (compiled_profile) {
    case bib::copied::DocumentCopiedProfile::pixel: break;
    case bib::copied::DocumentCopiedProfile::physical:
        binding_profile=bib::provider_candidate::DocumentBindingProfile::physical;
        wire_profile=bib::copied::DocumentWireProfile::physical;
        break;
    case bib::copied::DocumentCopiedProfile::editor:
#if BIB_ENGINE_PROVIDER_EDITOR_V1
        binding_profile=bib::provider_candidate::DocumentBindingProfile::editor;
        wire_profile=bib::copied::DocumentWireProfile::editor;
        break;
#else
        return failed(BIB_ENGINE_UNSUPPORTED);
#endif
    default: return failed(BIB_ENGINE_INVALID);
    }
    const auto limits=bib::copied::documentCopiedLimits(wire_profile);
    const std::string_view facts(profile_json,sizeof(profile_json)-1);
    if (!bib::copied::documentCopiedFactsMatch(facts,build,limits,compiled_profile)) return failed(BIB_ENGINE_INVALID);
    try {
        const auto status=bib::provider_candidate::bindActualWebCoreDocumentProvider(build,limits,{64,4194304},worker,
            binding_profile);
        if (status!=BIB_ENGINE_OK) return failed(status);
        BibEngineProviderV1 provider{};
        const auto get=bib_engine_get_provider_v1(1,1,sizeof(provider),&provider);
        if (get!=BIB_ENGINE_OK) return failed(get);
        if (!providerComplete(provider) || !bib::copied::documentCopiedBuildMatches(provider.build,build,compiled_profile)
            || !bib::copied::documentCopiedFactsMatch(facts,provider.build,provider.limits,compiled_profile))
            return failed(BIB_ENGINE_INVALID);
        // Process-lived objects are never deleted/reset, including failed
        // construction after provider binding. There is no cleanup retry path.
        copiedHost=new(std::nothrow) CopiedHost(imported,fatal,nullptr);
        if (!copiedHost) return failed(BIB_ENGINE_LIMIT);
        copiedDispatch=new(std::nothrow) CopiedDocumentDispatch(provider,*copiedHost,facts,worker,
            wire_profile);
        if (!copiedDispatch) return failed(BIB_ENGINE_LIMIT);
        if (copiedDispatch->marker()!=65536u) return failed(BIB_ENGINE_INVALID);
        phase.store(Phase::configured,std::memory_order_relaxed);
        return BIB_ENGINE_OK;
    } catch (...) {
        // Metadata composition has uncertain partial retention. Keep all
        // process-lived storage and reject every later native/export attempt.
        return failed(BIB_ENGINE_PROCESS_EXIT_REQUIRED);
    }
}
} // namespace

extern "C" int32_t bib_engine_wasm_document_facts_v1(uint8_t* output,uint32_t capacity) {
    return copyFacts(false,output,capacity);
}
extern "C" int32_t bib_engine_wasm_document_configure_v1(uint32_t worker_lo,uint32_t worker_hi) {
    return configureWorker(false,worker_lo,worker_hi);
}
extern "C" int32_t bib_engine_wasm_editor_facts_v1(uint8_t* output,uint32_t capacity) {
    return copyFacts(true,output,capacity);
}
extern "C" int32_t bib_engine_wasm_editor_configure_v1(uint32_t worker_lo,uint32_t worker_hi) {
    return configureWorker(true,worker_lo,worker_hi);
}

extern "C" uint32_t bib_engine_wasm_bridge_v1(void) {
    if (phase.load(std::memory_order_relaxed)!=Phase::configured || std::this_thread::get_id()!=owner) return 0;
    if (copiedHost->poisoned()) { phase.store(Phase::poisoned,std::memory_order_relaxed); return 0; }
    return copiedDispatch->marker();
}
extern "C" int32_t bib_engine_wasm_dispatch_v1(uint32_t operation,const uint8_t* input,
    uint32_t length,uint8_t* output,uint32_t capacity) {
    const auto current=phase.load(std::memory_order_relaxed);
    if (current==Phase::poisoned) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    if (current!=Phase::configured) return current==Phase::configuring ? BIB_ENGINE_REENTRANT : BIB_ENGINE_CLOSED;
    if (std::this_thread::get_id()!=owner) return BIB_ENGINE_WRONG_THREAD;
    if (copiedHost->poisoned()) return failed(BIB_ENGINE_PROCESS_EXIT_REQUIRED);
    if (!localSpan(input,length) || !localSpan(output,capacity)) return BIB_ENGINE_INVALID;
    const auto status=copiedDispatch->dispatch(operation,{input,length},{output,capacity});
    if (copiedHost->poisoned()) phase.store(Phase::poisoned,std::memory_order_relaxed);
    return status;
}
