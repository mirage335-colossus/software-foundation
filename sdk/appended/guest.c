#include <foundation/appended/guest.h>
#include <stddef.h>

#ifndef FOUNDATION_GUEST_HEAP_BYTES
#define FOUNDATION_GUEST_HEAP_BYTES 65536u
#endif
#if FOUNDATION_GUEST_HEAP_BYTES < 1024 || FOUNDATION_GUEST_HEAP_BYTES > 8388608
#error guest heap must contain between 1024 and 8388608 bytes
#endif

uint16_t foundation_guest_read_u16(const uint8_t *p) { return (uint16_t)(p[0] | (uint16_t)p[1] << 8); }
uint32_t foundation_guest_read_u32(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}
uint64_t foundation_guest_read_u64(const uint8_t *p) {
    return (uint64_t)foundation_guest_read_u32(p) | (uint64_t)foundation_guest_read_u32(p + 4) << 32;
}
void foundation_guest_write_u16(uint8_t *p, uint16_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
void foundation_guest_write_u32(uint8_t *p, uint32_t v) {
    for (uint32_t i = 0; i != 4; ++i) p[i] = (uint8_t)(v >> (8 * i));
}
void foundation_guest_write_u64(uint8_t *p, uint64_t v) {
    for (uint32_t i = 0; i != 8; ++i) p[i] = (uint8_t)(v >> (8 * i));
}
/* Constant-width builtins lower to unaligned Wasm loads/stores. The temporary
 * avoids C alignment and effective-type assumptions, including overlapping moves. */
static void copy_forward(uint8_t *d, const uint8_t *s, size_t n) {
    while (n >= 8) {
        uint64_t word; __builtin_memcpy(&word, s, 8); __builtin_memcpy(d, &word, 8);
        d += 8; s += 8; n -= 8;
    }
    while (n) { *d++ = *s++; --n; }
}
void *memcpy(void *to, const void *from, size_t n) {
    copy_forward((uint8_t *)to, (const uint8_t *)from, n);
    return to;
}
void *memmove(void *to, const void *from, size_t n) {
    uint8_t *d = (uint8_t *)to; const uint8_t *s = (const uint8_t *)from;
    if ((uintptr_t)d <= (uintptr_t)s) { copy_forward(d, s, n); return to; }
    d += n; s += n;
    while (n >= 8) {
        uint64_t word; d -= 8; s -= 8; n -= 8;
        __builtin_memcpy(&word, s, 8); __builtin_memcpy(d, &word, 8);
    }
    while (n) { --n; *--d = *--s; }
    return to;
}
void *memset(void *to, int value, size_t n) {
    uint8_t *d = (uint8_t *)to;
    uint64_t word = (uint64_t)(uint8_t)value * UINT64_C(0x0101010101010101);
    while (n >= 8) { __builtin_memcpy(d, &word, 8); d += 8; n -= 8; }
    while (n) { *d++ = (uint8_t)value; --n; }
    return to;
}
int memcmp(const void *a, const void *b, size_t n) {
    const uint8_t *x = (const uint8_t *)a, *y = (const uint8_t *)b;
    for (size_t i = 0; i != n; ++i) if (x[i] != y[i]) return x[i] < y[i] ? -1 : 1;
    return 0;
}
int foundation_guest_utf8(const uint8_t *p, uint32_t n) {
    uint32_t i = 0;
    while (i < n) {
        uint32_t c = p[i++], count, minimum;
        if (c < 0x80) continue;
        if (c >= 0xc2 && c <= 0xdf) { c &= 31; count = 1; minimum = 0x80; }
        else if (c >= 0xe0 && c <= 0xef) { c &= 15; count = 2; minimum = 0x800; }
        else if (c >= 0xf0 && c <= 0xf4) { c &= 7; count = 3; minimum = 0x10000; }
        else return 0;
        if (count > n - i) return 0;
        while (count--) { uint32_t next = p[i++]; if ((next & 0xc0) != 0x80) return 0; c = c << 6 | (next & 63); }
        if (c < minimum || c > 0x10ffff || (c >= 0xd800 && c <= 0xdfff)) return 0;
    }
    return 1;
}
int foundation_guest_decode_envelope(const uint8_t *p, uint32_t n, foundation_guest_envelope *out) {
    if (!p || !out || n < FOUNDATION_APPENDED_ENVELOPE_BYTES || n > FOUNDATION_APPENDED_MAX_MESSAGE_BYTES ||
        foundation_guest_read_u32(p) != n || foundation_guest_read_u16(p + 4) != FOUNDATION_APPENDED_ABI_MAJOR ||
        foundation_guest_read_u16(p + 6) != FOUNDATION_APPENDED_ABI_MINOR || foundation_guest_read_u32(p + 12) ||
        foundation_guest_read_u32(p + 44) != n - FOUNDATION_APPENDED_ENVELOPE_BYTES || foundation_guest_read_u32(p + 52)) return 0;
    foundation_guest_envelope value;
    value.kind = foundation_guest_read_u32(p + 8); value.flags = 0;
    if (value.kind < FOUNDATION_APPENDED_MESSAGE_REQUEST || value.kind > FOUNDATION_APPENDED_MESSAGE_COMPLETION) return 0;
    value.generation = foundation_guest_read_u64(p + 16); value.sequence = foundation_guest_read_u64(p + 24);
    value.interface_handle = foundation_guest_read_u64(p + 32); value.operation = foundation_guest_read_u32(p + 40);
    value.status = foundation_guest_read_u32(p + 48); value.correlation = foundation_guest_read_u64(p + 56);
    if (!value.generation || !value.sequence || value.status > FOUNDATION_APPENDED_SERVICE_UNCERTAIN ||
        (value.kind == FOUNDATION_APPENDED_MESSAGE_REQUEST && (value.status || value.correlation)) ||
        (value.kind == FOUNDATION_APPENDED_MESSAGE_REPLY && (value.status == FOUNDATION_APPENDED_SERVICE_RESULT_AVAILABLE ?
            (!value.correlation || n != FOUNDATION_APPENDED_ENVELOPE_BYTES) : value.correlation != 0))) return 0;
    *out = value; return 1;
}
int foundation_guest_encode_envelope(uint8_t *p, uint32_t capacity, const foundation_guest_envelope *e, uint32_t n) {
    if (!p || !e || n > FOUNDATION_APPENDED_MAX_MESSAGE_BYTES - FOUNDATION_APPENDED_ENVELOPE_BYTES ||
        capacity < FOUNDATION_APPENDED_ENVELOPE_BYTES || n > capacity - FOUNDATION_APPENDED_ENVELOPE_BYTES ||
        e->flags || !e->generation || !e->sequence || e->kind < FOUNDATION_APPENDED_MESSAGE_REQUEST ||
        e->kind > FOUNDATION_APPENDED_MESSAGE_COMPLETION || e->status > FOUNDATION_APPENDED_SERVICE_UNCERTAIN ||
        (e->kind == FOUNDATION_APPENDED_MESSAGE_REQUEST && (e->status || e->correlation)) ||
        (e->kind == FOUNDATION_APPENDED_MESSAGE_REPLY && (e->status == FOUNDATION_APPENDED_SERVICE_RESULT_AVAILABLE ?
            (!e->correlation || n != 0) : e->correlation != 0))) return 0;
    foundation_guest_write_u32(p, FOUNDATION_APPENDED_ENVELOPE_BYTES + n);
    foundation_guest_write_u16(p + 4, FOUNDATION_APPENDED_ABI_MAJOR); foundation_guest_write_u16(p + 6, FOUNDATION_APPENDED_ABI_MINOR);
    foundation_guest_write_u32(p + 8, e->kind); foundation_guest_write_u32(p + 12, 0);
    foundation_guest_write_u64(p + 16, e->generation); foundation_guest_write_u64(p + 24, e->sequence);
    foundation_guest_write_u64(p + 32, e->interface_handle); foundation_guest_write_u32(p + 40, e->operation);
    foundation_guest_write_u32(p + 44, n); foundation_guest_write_u32(p + 48, e->status);
    foundation_guest_write_u32(p + 52, 0); foundation_guest_write_u64(p + 56, e->correlation); return 1;
}
void foundation_guest_record_begin(foundation_guest_record *r, const uint8_t *p, uint32_t n) {
    r->data = p; r->bytes = n; r->offset = r->count = r->previous = 0;
}
static int record_valid(const uint8_t *, uint32_t, uint32_t);
static int field_valid(uint8_t type, uint8_t flags, const uint8_t *p, uint32_t n, uint32_t depth) {
    if (type == FOUNDATION_APPENDED_FIELD_U32) return n == 4;
    if (type == FOUNDATION_APPENDED_FIELD_U64 || type == FOUNDATION_APPENDED_FIELD_I64) return n == 8;
    if (type == FOUNDATION_APPENDED_FIELD_F64) {
        if (n != 8) return 0;
        uint64_t bits = foundation_guest_read_u64(p);
        return (bits & UINT64_C(0x7ff0000000000000)) != UINT64_C(0x7ff0000000000000) ||
            !(bits & UINT64_C(0x000fffffffffffff)) || bits == UINT64_C(0x7ff8000000000000);
    }
    if (type == FOUNDATION_APPENDED_FIELD_BOOL) return n == 1 && p[0] <= 1;
    if (type == FOUNDATION_APPENDED_FIELD_UTF8) return foundation_guest_utf8(p, n);
    if (type == FOUNDATION_APPENDED_FIELD_BYTES) return 1;
    if (type == FOUNDATION_APPENDED_FIELD_RECORD) return record_valid(p, n, depth + 1);
    if (type == FOUNDATION_APPENDED_FIELD_RECORD_LIST) {
        if (n < 4) return 0;
        uint32_t count = foundation_guest_read_u32(p), offset = 4;
        if (count > 1024) return 0;
        while (count--) {
            if (n - offset < 4) return 0;
            uint32_t bytes = foundation_guest_read_u32(p + offset); offset += 4;
            if (bytes > n - offset || !record_valid(p + offset, bytes, depth + 1)) return 0;
            offset += bytes;
        }
        return offset == n;
    }
    return !flags;
}
static int record_valid(const uint8_t *p, uint32_t n, uint32_t depth) {
    if (depth > 8 || n > FOUNDATION_APPENDED_MAX_MESSAGE_BYTES) return 0;
    uint32_t offset = 0, count = 0; uint16_t previous = 0;
    while (offset < n) {
        if (n - offset < 8 || count++ == 64) return 0;
        uint16_t id = foundation_guest_read_u16(p + offset); uint8_t type = p[offset + 2], flags = p[offset + 3];
        uint32_t bytes = foundation_guest_read_u32(p + offset + 4);
        if (id <= previous || flags > 1 || bytes > n - offset - 8 ||
            !field_valid(type, flags, p + offset + 8, bytes, depth)) return 0;
        previous = id; offset += bytes + 8;
    }
    return 1;
}
int foundation_guest_record_next(foundation_guest_record *r, foundation_guest_field *out) {
    if (r->offset == r->bytes) return 0;
    if (!r->data || r->offset > r->bytes || r->bytes > FOUNDATION_APPENDED_MAX_MESSAGE_BYTES ||
        r->bytes - r->offset < 8 || r->count == 64) return -1;
    const uint8_t *p = r->data + r->offset;
    foundation_guest_field v = {foundation_guest_read_u16(p), p[2], p[3], p + 8, foundation_guest_read_u32(p + 4)};
    if (v.id <= r->previous || v.flags > 1 || v.bytes > r->bytes - r->offset - 8) return -1;
    if (!field_valid(v.type, v.flags, v.data, v.bytes, 1)) return -1;
    r->offset += 8 + v.bytes; r->previous = v.id; ++r->count; *out = v; return 1;
}
uint32_t foundation_guest_field_write(uint8_t *p, uint32_t capacity, uint32_t n, uint16_t id,
                                    uint8_t type, uint8_t flags, const uint8_t *data, uint32_t bytes) {
    if (!p || !id || flags > 1 || n > capacity || capacity - n < 8 || bytes > capacity - n - 8 ||
        (bytes && !data) || n > FOUNDATION_APPENDED_MAX_MESSAGE_BYTES - 8 ||
        bytes > FOUNDATION_APPENDED_MAX_MESSAGE_BYTES - n - 8 || !field_valid(type, flags, data, bytes, 1)) return UINT32_MAX;
    foundation_guest_record r; foundation_guest_field previous; int next;
    foundation_guest_record_begin(&r, p, n);
    while ((next = foundation_guest_record_next(&r, &previous)) == 1) {}
    if (next < 0 || id <= r.previous || r.count >= 64) return UINT32_MAX;
    foundation_guest_write_u16(p + n, id); p[n + 2] = type; p[n + 3] = flags;
    foundation_guest_write_u32(p + n + 4, bytes); memcpy(p + n + 8, data, bytes); return n + 8 + bytes;
}
int foundation_guest_decode_context(const uint8_t *p, uint32_t n, foundation_guest_init_context *out) {
    foundation_guest_record r; foundation_guest_field f; foundation_guest_init_context value;
    foundation_guest_record_begin(&r, p, n);
    for (uint32_t id = 1; id != 9; ++id) {
        if (foundation_guest_record_next(&r, &f) != 1 || f.id != id || f.flags != 1) return 0;
        uint8_t type = id == 1 ? FOUNDATION_APPENDED_FIELD_U64 : id == 5 ? FOUNDATION_APPENDED_FIELD_BYTES : FOUNDATION_APPENDED_FIELD_U32;
        uint32_t bytes = id == 1 ? 8 : id == 5 ? 32 : 4;
        if (f.type != type || f.bytes != bytes) return 0;
        if (id == 1) value.generation = foundation_guest_read_u64(f.data);
        if (id == 2 && foundation_guest_read_u32(f.data) != FOUNDATION_APPENDED_ABI_VERSION) return 0;
        if (id == 3 && foundation_guest_read_u32(f.data) != FOUNDATION_APPENDED_ENVELOPE_BYTES) return 0;
        if (id == 4) value.maximum_message_bytes = foundation_guest_read_u32(f.data);
        if (id == 5) {
            static const uint8_t schema[32] = {FOUNDATION_APPENDED_BOOTSTRAP_SCHEMA_BYTES};
            if (memcmp(schema, f.data, 32)) return 0;
            memcpy(value.bootstrap_schema, f.data, 32);
        }
        if (id == 6) value.maximum_retained_requests = foundation_guest_read_u32(f.data);
        if (id == 7) value.maximum_retained_results = foundation_guest_read_u32(f.data);
        if (id == 8) value.maximum_retained_bytes = foundation_guest_read_u32(f.data);
    }
    int next;
    while ((next = foundation_guest_record_next(&r, &f)) == 1) if (f.flags) return 0;
    if (next < 0 || !value.generation || value.maximum_message_bytes < 64 ||
        value.maximum_message_bytes > FOUNDATION_APPENDED_MAX_MESSAGE_BYTES || value.maximum_retained_requests < 2 ||
        !value.maximum_retained_results || !value.maximum_retained_bytes) return 0;
    *out = value; return 1;
}
uint32_t foundation_guest_discovery(uint8_t *p, uint32_t capacity, const uint8_t *name, uint32_t bytes,
                                   uint32_t major, uint32_t low, uint32_t high, const uint8_t *schema) {
    uint8_t scalar[4]; uint32_t n;
    if (!bytes || !foundation_guest_utf8(name, bytes) || !major || low > high || major > 65535 || high > 65535) return UINT32_MAX;
    n = foundation_guest_field_write(p, capacity, 0, 1, FOUNDATION_APPENDED_FIELD_UTF8, 1, name, bytes);
    foundation_guest_write_u32(scalar, major); n = foundation_guest_field_write(p, capacity, n, 2, FOUNDATION_APPENDED_FIELD_U32, 1, scalar, 4);
    foundation_guest_write_u32(scalar, low); n = foundation_guest_field_write(p, capacity, n, 3, FOUNDATION_APPENDED_FIELD_U32, 1, scalar, 4);
    foundation_guest_write_u32(scalar, high); n = foundation_guest_field_write(p, capacity, n, 4, FOUNDATION_APPENDED_FIELD_U32, 1, scalar, 4);
    if (schema) n = foundation_guest_field_write(p, capacity, n, 5, FOUNDATION_APPENDED_FIELD_BYTES, 1, schema, 32);
    return n;
}
int foundation_guest_discovery_handle(const uint8_t *p, uint32_t n, uint64_t *out) {
    foundation_guest_record r; foundation_guest_field f; uint64_t handle = 0; uint32_t found = 0; int next;
    foundation_guest_record_begin(&r, p, n);
    while ((next = foundation_guest_record_next(&r, &f)) == 1) {
        if (f.id >= 1 && f.id <= 6) {
            uint8_t type = f.id == 1 ? FOUNDATION_APPENDED_FIELD_U64 : f.id == 2 ? FOUNDATION_APPENDED_FIELD_UTF8 :
                f.id == 5 ? FOUNDATION_APPENDED_FIELD_BYTES : FOUNDATION_APPENDED_FIELD_U32;
            if (f.type != type || f.flags != 1 || (f.id == 2 && !f.bytes) || (f.id == 5 && f.bytes != 32)) return 0;
            if (f.id == 1) handle = foundation_guest_read_u64(f.data);
            if (f.id == 3 && (!foundation_guest_read_u32(f.data) || foundation_guest_read_u32(f.data) > 65535)) return 0;
            if (f.id == 4 && foundation_guest_read_u32(f.data) > 65535) return 0;
            found |= 1u << (f.id - 1);
        }
        else if (f.flags) return 0;
    }
    if (next < 0 || found != 63) return 0;
    *out = handle; return 1;
}

typedef struct guest_block { uint32_t capacity, requested, used, reserved; } guest_block;
static _Alignas(16) uint8_t guest_heap[FOUNDATION_GUEST_HEAP_BYTES];
static int heap_ready;
static uint32_t lifecycle;
static foundation_guest_init_context bound_context;
static uint64_t next_sequence = 1;
typedef struct guest_destructor { void (*call)(void *); void *argument; } guest_destructor;
static guest_destructor destructors[32];
static uint32_t destructor_count;
static int destructor_exhausted;
int __cxa_atexit(void (*call)(void *), void *argument, void *dso) {
    (void)dso;
    if (!call || lifecycle == 3 || lifecycle == 5) return -1;
    if (destructor_count == 32) { destructor_exhausted = 1; return -1; }
    destructors[destructor_count].call = call; destructors[destructor_count++].argument = argument;
    return 0;
}
void __cxa_pure_virtual(void) { __builtin_trap(); }
void __cxa_deleted_virtual(void) { __builtin_trap(); }
uint32_t foundation_app_abi_v1(void) { return FOUNDATION_APPENDED_ABI_VERSION; }
uint32_t foundation_app_alloc_v1(uint32_t bytes) {
    if (!bytes || bytes > FOUNDATION_GUEST_HEAP_BYTES - sizeof(guest_block) || lifecycle == 3) return 0;
    if (!heap_ready) { ((guest_block *)guest_heap)->capacity = FOUNDATION_GUEST_HEAP_BYTES - sizeof(guest_block); heap_ready = 1; }
    uint32_t needed = (bytes + 15u) & ~15u, offset = 0;
    while (offset < FOUNDATION_GUEST_HEAP_BYTES) {
        guest_block *block = (guest_block *)(guest_heap + offset);
        if (!block->used && block->capacity >= needed) {
            if (block->capacity - needed >= 16 + sizeof(guest_block)) {
                guest_block *tail = (guest_block *)(guest_heap + offset + sizeof(guest_block) + needed);
                tail->capacity = block->capacity - needed - sizeof(guest_block); tail->requested = tail->used = tail->reserved = 0;
                block->capacity = needed;
            }
            block->requested = bytes; block->used = 1;
            return (uint32_t)(uintptr_t)(guest_heap + offset + sizeof(guest_block));
        }
        offset += sizeof(guest_block) + block->capacity;
    }
    return 0;
}
void foundation_app_free_v1(uint32_t address, uint32_t bytes) {
    if (!heap_ready || !address) return;
    uint32_t offset = 0;
    while (offset < FOUNDATION_GUEST_HEAP_BYTES) {
        guest_block *b = (guest_block *)(guest_heap + offset);
        if ((uint32_t)(uintptr_t)(guest_heap + offset + sizeof(guest_block)) == address && b->used && b->requested == bytes) {
            b->used = b->requested = 0; break;
        }
        offset += sizeof(guest_block) + b->capacity;
    }
    offset = 0;
    while (offset < FOUNDATION_GUEST_HEAP_BYTES) {
        guest_block *b = (guest_block *)(guest_heap + offset); uint32_t next = offset + sizeof(guest_block) + b->capacity;
        if (next >= FOUNDATION_GUEST_HEAP_BYTES) break;
        guest_block *after = (guest_block *)(guest_heap + next);
        if (!b->used && !after->used) b->capacity += sizeof(guest_block) + after->capacity;
        else offset = next;
    }
}
static int memory_range(uint32_t offset, uint32_t bytes) {
    uint64_t capacity = (uint64_t)__builtin_wasm_memory_size(0) * 65536;
    return offset != 0 && offset <= capacity && bytes <= capacity - offset;
}
const foundation_guest_init_context *foundation_guest_context(void) { return lifecycle == 1 || lifecycle == 2 || lifecycle == 4 ? &bound_context : 0; }
uint64_t foundation_guest_generation(void) { return foundation_guest_context() ? bound_context.generation : 0; }
uint32_t foundation_guest_maximum_message(void) { return foundation_guest_context() ? bound_context.maximum_message_bytes : 0; }
uint64_t foundation_guest_next_sequence(void) {
    if (lifecycle != 1 && lifecycle != 2) return 0;
    uint64_t result = next_sequence;
    if (next_sequence) ++next_sequence;
    return result;
}
uint32_t foundation_guest_call(const uint8_t *request, uint32_t bytes, uint8_t *reply, uint32_t capacity) {
    if ((lifecycle != 1 && lifecycle != 2) || bytes > bound_context.maximum_message_bytes || capacity < 64)
        return FOUNDATION_APPENDED_TRANSPORT_INTERNAL_ERROR;
    return foundation_kernel_call_v1((uint32_t)(uintptr_t)request, bytes, (uint32_t)(uintptr_t)reply, capacity);
}
extern void __wasm_call_ctors(void);
/* Archive-based applications must supply real hooks: weak defaults would
 * satisfy their references and prevent the linker from extracting the app. */
#ifndef FOUNDATION_GUEST_REQUIRE_HOOKS
__attribute__((weak)) uint32_t foundation_guest_initialize(const uint8_t *p, uint32_t n) { (void)p; (void)n; return 0; }
__attribute__((weak)) uint32_t foundation_guest_dispatch(const uint8_t *p, uint32_t n) { (void)p; (void)n; return 0; }
__attribute__((weak)) uint32_t foundation_guest_step(uint32_t n) { (void)n; return FOUNDATION_APPENDED_STEP_IDLE; }
__attribute__((weak)) void foundation_guest_shutdown(uint32_t reason) { (void)reason; }
#endif
uint32_t foundation_app_init_v1(uint32_t offset, uint32_t bytes) {
    if (lifecycle) return FOUNDATION_APPENDED_APP_FAILED;
    lifecycle = 3; /* One attempt, including malformed contexts. */
    if (!memory_range(offset, bytes) || !foundation_guest_decode_context((const uint8_t *)(uintptr_t)offset, bytes, &bound_context))
        return FOUNDATION_APPENDED_APP_INVALID_INPUT;
    lifecycle = 4; /* Constructors may inspect context, but cannot call services. */
    __wasm_call_ctors();
    if (destructor_exhausted) { lifecycle = 3; return FOUNDATION_APPENDED_APP_EXHAUSTED; }
    lifecycle = 1;
    uint32_t result = foundation_guest_initialize((const uint8_t *)(uintptr_t)offset, bytes);
    if (result > FOUNDATION_APPENDED_APP_EXHAUSTED) result = FOUNDATION_APPENDED_APP_FAILED;
    lifecycle = result ? 3 : 2; return result;
}
uint32_t foundation_app_dispatch_v1(uint32_t offset, uint32_t bytes) {
    foundation_guest_envelope e;
    if (lifecycle != 2) return FOUNDATION_APPENDED_APP_FAILED;
    if (!memory_range(offset, bytes) || bytes > bound_context.maximum_message_bytes ||
        !foundation_guest_decode_envelope((const uint8_t *)(uintptr_t)offset, bytes, &e) || e.generation != bound_context.generation) {
        lifecycle = 3; return FOUNDATION_APPENDED_APP_INVALID_INPUT;
    }
    uint32_t result = foundation_guest_dispatch((const uint8_t *)(uintptr_t)offset, bytes);
    if (result > FOUNDATION_APPENDED_APP_EXHAUSTED) result = FOUNDATION_APPENDED_APP_FAILED;
    if (result) lifecycle = 3;
    return result;
}
uint32_t foundation_app_step_v1(uint32_t budget) {
    if (lifecycle != 2) return FOUNDATION_APPENDED_STEP_FAILED;
    if (!budget) return FOUNDATION_APPENDED_STEP_IDLE;
    uint32_t result = foundation_guest_step(budget);
    if (result > FOUNDATION_APPENDED_STEP_EXHAUSTED) result = FOUNDATION_APPENDED_STEP_FAILED;
    if (result >= FOUNDATION_APPENDED_STEP_FAILED) lifecycle = 3;
    return result;
}
void foundation_app_shutdown_v1(uint32_t reason) {
    if (lifecycle != 2) return;
    lifecycle = 1; foundation_guest_shutdown(reason); lifecycle = 5;
    while (destructor_count) {
        guest_destructor d = destructors[--destructor_count]; d.call(d.argument);
    }
    lifecycle = 3;
}
