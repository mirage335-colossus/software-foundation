// SPDX-License-Identifier: CC0-1.0
// Private source candidate. Not parsed, linked or executed against WebCore.
#pragma once
#include <foundation/appended/engine_provider.h>

namespace WebCore { class Page; }

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

} // namespace BIB
