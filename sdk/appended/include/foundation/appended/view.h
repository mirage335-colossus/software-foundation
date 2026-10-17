#ifndef FOUNDATION_APPENDED_GUEST_VIEW_H
#define FOUNDATION_APPENDED_GUEST_VIEW_H
#include <foundation/appended/guest.h>

/* Generated identity of abi/appended/view/v1.json. The binding conformance test
 * compares this value with the exact authoritative schema bytes. */
#define FOUNDATION_GUEST_VIEW_SCHEMA_SHA256 "7345dda570c5c338f41785c88ebea3f7ba78eff7da07786a0ced43fe4dc411b7"
#define FOUNDATION_GUEST_VIEW_SCHEMA_BYTES \
    0x73,0x45,0xdd,0xa5,0x70,0xc5,0xc3,0x38,0xf4,0x17,0x85,0xc8,0x8e,0xbe,0xa3,0xf7, \
    0xba,0x78,0xef,0xf7,0xda,0x07,0x78,0x6a,0x0c,0xed,0x43,0xfe,0x4d,0xc4,0x11,0xb7
#define FOUNDATION_GUEST_VIEW_NAME "foundation.view"
#define FOUNDATION_GUEST_VIEW_REPLACE 1u
#define FOUNDATION_GUEST_VIEW_HOST_SERVICE 2u
#define FOUNDATION_GUEST_VIEW_GROUP 1u
#define FOUNDATION_GUEST_VIEW_LABEL 2u
#define FOUNDATION_GUEST_VIEW_BUTTON 3u
#define FOUNDATION_GUEST_VIEW_TEXT 6u

/* Allocation-free canonical record/list builders. Any failure poisons the
 * builder; length returns UINT32_MAX and its bytes must not be submitted. */
typedef struct foundation_guest_builder {
    uint8_t *data;
    uint32_t capacity, bytes;
} foundation_guest_builder;
static inline void foundation_guest_builder_begin(foundation_guest_builder *b, uint8_t *data, uint32_t capacity) {
    b->data = data; b->capacity = capacity; b->bytes = 0;
}
static inline void foundation_guest_builder_field(foundation_guest_builder *b, uint16_t id, uint8_t type,
                                                  const uint8_t *data, uint32_t bytes) {
    b->bytes = foundation_guest_field_write(b->data, b->capacity, b->bytes, id, type, 1, data, bytes);
}
static inline void foundation_guest_builder_u32(foundation_guest_builder *b, uint16_t id, uint32_t value) {
    uint8_t scalar[4]; foundation_guest_write_u32(scalar, value);
    foundation_guest_builder_field(b, id, FOUNDATION_APPENDED_FIELD_U32, scalar, 4);
}
static inline void foundation_guest_builder_u64(foundation_guest_builder *b, uint16_t id, uint64_t value) {
    uint8_t scalar[8]; foundation_guest_write_u64(scalar, value);
    foundation_guest_builder_field(b, id, FOUNDATION_APPENDED_FIELD_U64, scalar, 8);
}
static inline void foundation_guest_builder_number(foundation_guest_builder *b, uint16_t id, double value) {
    uint64_t bits; uint8_t scalar[8]; __builtin_memcpy(&bits, &value, 8);
    foundation_guest_write_u64(scalar, bits);
    foundation_guest_builder_field(b, id, FOUNDATION_APPENDED_FIELD_F64, scalar, 8);
}
static inline double foundation_guest_field_number(const foundation_guest_field *field) {
    uint64_t bits = foundation_guest_read_u64(field->data); double value;
    __builtin_memcpy(&value, &bits, 8); return value;
}
static inline void foundation_guest_builder_text(foundation_guest_builder *b, uint16_t id, const char *text) {
    uint32_t bytes = 0; while (text[bytes]) ++bytes;
    foundation_guest_builder_field(b, id, FOUNDATION_APPENDED_FIELD_UTF8, (const uint8_t *)text, bytes);
}
static inline void foundation_guest_builder_record(foundation_guest_builder *b, uint16_t id, const foundation_guest_builder *record) {
    foundation_guest_builder_field(b, id, FOUNDATION_APPENDED_FIELD_RECORD, record->data, record->bytes);
}
static inline void foundation_guest_builder_list_begin(foundation_guest_builder *b, uint8_t *data, uint32_t capacity) {
    foundation_guest_builder_begin(b, data, capacity);
    if (capacity < 4) b->bytes = UINT32_MAX;
    else { foundation_guest_write_u32(data, 0); b->bytes = 4; }
}
static inline void foundation_guest_builder_list_append(foundation_guest_builder *b, const foundation_guest_builder *record) {
    if (b->bytes > b->capacity || b->capacity - b->bytes < 4 || record->bytes > b->capacity - b->bytes - 4 ||
        foundation_guest_read_u32(b->data) == 1024) { b->bytes = UINT32_MAX; return; }
    foundation_guest_write_u32(b->data + b->bytes, record->bytes); b->bytes += 4;
    for (uint32_t i = 0; i != record->bytes; ++i) b->data[b->bytes + i] = record->data[i];
    b->bytes += record->bytes; foundation_guest_write_u32(b->data, foundation_guest_read_u32(b->data) + 1);
}
static inline void foundation_guest_builder_list(foundation_guest_builder *b, uint16_t id, const foundation_guest_builder *list) {
    foundation_guest_builder_field(b, id, FOUNDATION_APPENDED_FIELD_RECORD_LIST, list->data, list->bytes);
}
static inline void foundation_guest_view_rect(foundation_guest_builder *b, uint8_t *data, uint32_t capacity,
                                             double x, double y, double width, double height) {
    foundation_guest_builder_begin(b, data, capacity);
    foundation_guest_builder_number(b, 1, x); foundation_guest_builder_number(b, 2, y);
    foundation_guest_builder_number(b, 3, width); foundation_guest_builder_number(b, 4, height);
}
static inline void foundation_guest_view_widget(foundation_guest_builder *b, uint8_t *data, uint32_t capacity,
                                                const char *id, uint64_t generation, uint32_t kind,
                                                const foundation_guest_builder *bounds) {
    foundation_guest_builder_begin(b, data, capacity);
    foundation_guest_builder_text(b, 1, id); foundation_guest_builder_u64(b, 2, generation);
    foundation_guest_builder_u32(b, 3, kind); foundation_guest_builder_record(b, 4, bounds);
}
#endif
