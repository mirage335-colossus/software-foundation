// SPDX-License-Identifier: CC0-1.0
// Private source candidate. Not parsed, linked or executed against WebCore.
#pragma once
#include <foundation/appended/engine_provider.h>
#ifndef BIB_ENGINE_PROVIDER_DOCUMENT_V2
#define BIB_ENGINE_PROVIDER_DOCUMENT_V2 0
#endif
#if BIB_ENGINE_PROVIDER_DOCUMENT_V2
#include <optional>
#include <wtf/RefPtr.h>
#endif

namespace WebCore { class Document; class LocalFrame; class Page; }

namespace BIB {

// Binding has already retained the actual service/resource host tables. create
// copies this host table permanently and consumes persist_seed before return.
// The table, callbacks and their context remain alive until process exit.
struct ProviderRuntimeConfig {
    const BibEngineHostV1* host;
    uint64_t application_instance;
    BibEngineBytesV1 persist_seed;
    uint32_t raster_output;
};

// One owner thread, one process lifetime. ProviderGuard owns the outer host turn.
// Executing helpers nest the Bridge guard before their common-VM lock, so JSC
// native service functions observe bridge depth until all locks/checkpoints end.
// Page access is private to Binding, never a C ABI or application capability.
int32_t bibProviderCreatePage(const ProviderRuntimeConfig&);
int32_t bibProviderStep(uint32_t render);
int32_t bibProviderPublishDamage();
WebCore::Page* bibProviderPage();

#if BIB_ENGINE_PROVIDER_DOCUMENT_V2
// Explicit document 1795/2003 ADVANCE: render=1 paints and reads back a complete
// fresh frame even for 1795/no-port bitmap native-effect release and unchanged
// pixels. render=0 delegates ordinary run-loop progress. Pending authority never
// invents a frame; successful owned Host FRAME_COMMIT is delivery evidence.
// Both typed document bindings select this; legacy 259/467 keep ordinary Step.
int32_t bibProviderDocumentAdvance(uint32_t render);
// Native-private same-Page helpers. Thread/current-document failures return no
// authority; resource epochs remain an additional private fence only.
WTF::RefPtr<WebCore::LocalFrame> bibProviderDocumentMainFrame();
std::optional<bool> bibProviderDocumentInputMethodState(const WebCore::Document&);
bool bibProviderDocumentForeground(const WebCore::Document&);
// Effectful capture checkpoint ONLY. Caller already owns the complete outer
// ProviderGuard -> Bridge -> common-VM JSLock scope. No nested turn, RunLoop,
// rendering-update/rAF, host callback, persistence, wake or damage publication.
// Inert cached admission and metadata ACK must never call this helper.
bool bibProviderDocumentCheckpoint(WebCore::LocalFrame&, WebCore::Document&,
    uint64_t application_instance, uint64_t document_sequence,
    uint64_t service_generation, uint64_t resource_epoch);
#endif

} // namespace BIB
