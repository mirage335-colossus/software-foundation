#include <foundation/appended/guest.hpp>
#include <stddef.h>

namespace {
/* This constructor demonstrates explicit SDK startup. */
unsigned constructed;
uint64_t constructor_generation;
foundation::appended::guest::Buffer startup_buffer(32);
int *null_pointer = NULL;
struct Startup { Startup() { ++constructed; constructor_generation = foundation_guest_generation(); } } startup;
}

/* Keep behavior shared with the C fixture while exercising C++ construction and
 * wrappers. Each example is compiled separately, never linked together. */
#define foundation_guest_initialize calculator_c_initialize
#include "../c/calculator.c"
#undef foundation_guest_initialize

extern "C" uint32_t foundation_guest_initialize(const uint8_t *context, uint32_t bytes) {
    if (constructed != 1 || !constructor_generation || !startup_buffer || null_pointer ||
        !foundation::appended::guest::context()) return FOUNDATION_APPENDED_APP_FAILED;
    return calculator_c_initialize(context, bytes);
}
