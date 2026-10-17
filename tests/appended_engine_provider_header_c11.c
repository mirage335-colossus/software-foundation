// SPDX-License-Identifier: CC0-1.0
// Current compiler layout observation, never cross-platform ABI qualification.
#include <foundation/appended/engine_provider.h>
#include <stddef.h>
#include <stdio.h>
_Static_assert(sizeof(uint32_t)==4,"u32");
_Static_assert(sizeof(uint64_t)==8,"u64");
int main(void) {
    printf("{\"provider\":%zu,\"host\":%zu,\"command\":%zu,\"query\":%zu,\"command_payload_length\":%zu,\"query_payload_length\":%zu}\n",
        sizeof(BibEngineProviderV1),sizeof(BibEngineHostV1),sizeof(BibEngineCommandV1),sizeof(BibEngineQueryV1),
        offsetof(BibEngineCommandV1,payload)+offsetof(BibEngineBytesV1,length),
        offsetof(BibEngineQueryV1,payload)+offsetof(BibEngineBytesV1,length));
    return 0;
}
