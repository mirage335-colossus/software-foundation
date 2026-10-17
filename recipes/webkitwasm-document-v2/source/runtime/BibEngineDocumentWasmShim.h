// SPDX-License-Identifier: CC0-1.0
// Explicit document-profile bootstrap. These private exports are not installed.
#ifndef BIB_ENGINE_DOCUMENT_WASM_SHIM_V1_H
#define BIB_ENGINE_DOCUMENT_WASM_SHIM_V1_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
// Pure metadata copy, <=4096 bytes, no trailing NUL. Returns copied byte count
// or a negative BibEngine status; a short/invalid output is left unchanged.
// Facts are readable before configure and remain source facts, not SDK proof.
int32_t bib_engine_wasm_document_facts_v1(uint8_t* output, uint32_t capacity);
// Exactly one attempt per instance, including failure. Worker is the actual
// immutable Worker epoch: uint64(worker_lo) | (uint64(worker_hi) << 32).
// No implicit/default Worker and no bind during a C++ constructor.
int32_t bib_engine_wasm_document_configure_v1(uint32_t worker_lo, uint32_t worker_hi);
// Marker remains zero until explicit configure has fully validated the table.
uint32_t bib_engine_wasm_bridge_v1(void);
int32_t bib_engine_wasm_dispatch_v1(uint32_t operation, const uint8_t* input,
    uint32_t input_length, uint8_t* output, uint32_t output_capacity);
#ifdef __cplusplus
}
#endif
#endif
