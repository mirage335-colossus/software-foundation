// SPDX-License-Identifier: CC0-1.0
// Actual source composition; not compiled or runtime-qualified by helper tests.
#include "BibEngineWasmShim.h"
#include "BibEngineCopiedHost.h"
#include "../portable/BibEngineCopiedDispatch.h"
#include "BibEngineProviderBinding.h"
#include "BibCopiedMetadata.generated.h"
#include <algorithm>
#include <climits>
#include <cstring>
#include <new>

#if !defined(__EMSCRIPTEN__) || defined(__EMSCRIPTEN_PTHREADS__) || BIB_PTHREAD || !BIB_ENGINE_PROVIDER_NEUTRAL
#error "The copied shim requires the explicit non-pthread browser CPU provider"
#endif
static_assert(sizeof(void*)==4 && CHAR_BIT==8);

extern "C" int32_t bib_engine_copied_host_v1(uint32_t,const uint8_t*,uint32_t,uint8_t*,uint32_t);
namespace {
using bib::copied::CopiedDispatch;
using bib::copied::CopiedHost;
CopiedHost* copiedHost;
CopiedDispatch* copiedDispatch;

[[noreturn]] void fatal(void*,const char*) noexcept { __builtin_trap(); }
int32_t imported(void*,uint32_t op,const uint8_t* in,uint32_t length,uint8_t* out,uint32_t capacity) {
    return bib_engine_copied_host_v1(op,in,length,out,capacity);
}
bool matchingBuild(const BibEngineBuildV1& b,const BibEngineBuildV1& expected) noexcept {
    return b.size==expected.size && b.layout_revision==expected.layout_revision
        && b.target_system==expected.target_system && b.target_processor==expected.target_processor
        && b.pointer_bits==expected.pointer_bits && b.lifetime==expected.lifetime
        && b.maximum_starts==expected.maximum_starts && b.reserved==0
        && b.fixed_viewport_width==expected.fixed_viewport_width && b.fixed_viewport_height==expected.fixed_viewport_height
        && b.capabilities==expected.capabilities
        && !std::memcmp(b.contract_header_sha256,expected.contract_header_sha256,32)
        && !std::memcmp(b.build_identity_sha256,expected.build_identity_sha256,32)
        && !std::memcmp(b.source_recipe_sha256,expected.source_recipe_sha256,32);
}
// Metadata-only runtime composition. No Page/JSC/Package or host call occurs.
// All retained objects intentionally live for the Wasm instance's entire life.
__attribute__((constructor)) void composeCopiedProvider() noexcept {
    using namespace foundation::appended::copied_metadata;
    if(copiedDispatch || !metadataValid()) return;
    try {
        const auto limits=bib::copied::copiedLimits();
        const auto status=bib::provider_candidate::bindActualWebCoreProvider(build,limits,{64,4194304});
        if(status!=BIB_ENGINE_OK) return;
        BibEngineProviderV1 provider{};
        if(bib_engine_get_provider_v1(1,0,sizeof(provider),&provider)!=BIB_ENGINE_OK
            || !matchingBuild(provider.build,build)) return;
        copiedHost=new(std::nothrow) CopiedHost(imported,fatal,nullptr);
        if(!copiedHost) return;
        copiedDispatch=new(std::nothrow) CopiedDispatch(provider,*copiedHost,profile_json);
        // A failed composition never publishes a valid marker or retry path.
    } catch(...) { copiedDispatch=nullptr; }
}
bool localSpan(const void* pointer,uint32_t size) noexcept {
    const auto begin=static_cast<uint64_t>(reinterpret_cast<uintptr_t>(pointer));
    const auto bytes=static_cast<uint64_t>(__builtin_wasm_memory_size(0))*UINT64_C(65536);
    return (!size || pointer) && begin<=bytes && static_cast<uint64_t>(size)<=bytes-begin;
}
}
extern "C" uint32_t bib_engine_wasm_bridge_v1(void) {
    return copiedDispatch?copiedDispatch->marker():0;
}
extern "C" int32_t bib_engine_wasm_dispatch_v1(uint32_t op,const uint8_t* input,
    uint32_t length,uint8_t* output,uint32_t capacity) {
    if(!copiedDispatch || !localSpan(input,length) || !localSpan(output,capacity)) return -1;
    return copiedDispatch->dispatch(op,{input,length},{output,capacity});
}
