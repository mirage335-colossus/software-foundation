// SPDX-License-Identifier: CC0-1.0
// Private scalar copied endpoint. Pointers belong to this engine memory only.
#ifndef BIB_ENGINE_COPIED_WASM_SHIM_V1_H
#define BIB_ENGINE_COPIED_WASM_SHIM_V1_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
uint32_t bib_engine_wasm_bridge_v1(void);
int32_t bib_engine_wasm_dispatch_v1(uint32_t operation, const uint8_t* input,
    uint32_t input_length, uint8_t* output, uint32_t output_capacity);
#ifdef __cplusplus
}
#endif
#endif
