// SPDX-License-Identifier: CC0-1.0
// Private source candidate; no public WTF header/class/virtual changes.
#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif
// Defined by the narrow RunLoopGeneric.cpp overlay. One installation on the
// initialized engine main thread, before Page construction. No reset/unload.
// Callback/context remain valid until process exit. Called under the RunLoop
// mutex: copy/replace a monotonic deadline only; never enter/pump the engine.
// armed=0 disarms. Delay is bounded to [0, INT32_MAX] milliseconds.
int bib_engine_provider_set_timer_scheduler_v1(void* context,
    void (*replace_timer_ms)(void*, double delay_ms, uint32_t armed));
#ifdef __cplusplus
}
#endif
