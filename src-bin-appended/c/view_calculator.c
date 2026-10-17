#include <foundation/appended/view.h>

static uint64_t view_handle, revision;
static double client_width = 400, client_height = 240, display_scale = 1;
static char lhs[11] = "0", rhs[11] = "0", result[64] = "Press Sum";
static uint8_t request[4096], reply[512];

static uint32_t invoke(uint64_t handle, uint32_t operation, uint32_t payload) {
    foundation_guest_envelope e = {FOUNDATION_APPENDED_MESSAGE_REQUEST, 0, foundation_guest_generation(),
        foundation_guest_next_sequence(), handle, operation, 0, 0}, response;
    if (!e.sequence || !foundation_guest_encode_envelope(request, sizeof(request), &e, payload)) return FOUNDATION_APPENDED_APP_EXHAUSTED;
    if (foundation_guest_call(request, 64 + payload, reply, sizeof(reply)) != FOUNDATION_APPENDED_TRANSPORT_OK ||
        foundation_guest_read_u32(reply) > sizeof(reply) ||
        !foundation_guest_decode_envelope(reply, foundation_guest_read_u32(reply), &response) ||
        response.kind != FOUNDATION_APPENDED_MESSAGE_REPLY || response.generation != e.generation ||
        response.sequence != e.sequence || response.interface_handle != handle || response.operation != operation ||
        response.status != FOUNDATION_APPENDED_SERVICE_OK) return FOUNDATION_APPENDED_APP_FAILED;
    return FOUNDATION_APPENDED_APP_OK;
}
static uint32_t acknowledge(void) {
    uint8_t sequence[8]; foundation_guest_write_u64(sequence, foundation_guest_read_u64(reply + 24));
    uint32_t n = foundation_guest_field_write(request + 64, sizeof(request) - 64, 0, 1,
        FOUNDATION_APPENDED_FIELD_U64, 1, sequence, 8);
    return invoke(0, FOUNDATION_APPENDED_CONTROL_ACKNOWLEDGE, n);
}
static void add_widget(foundation_guest_builder *list, const char *id, uint32_t kind,
                       double y, const char *text, const char *label) {
    uint8_t rect_bytes[64], widget_bytes[512]; foundation_guest_builder rect, widget;
    foundation_guest_view_rect(&rect, rect_bytes, sizeof(rect_bytes), 20, y, 360, 32);
    foundation_guest_view_widget(&widget, widget_bytes, sizeof(widget_bytes), id, 1, kind, &rect);
    foundation_guest_builder_text(&widget, 7, text); foundation_guest_builder_text(&widget, 8, label);
    if (kind == FOUNDATION_GUEST_VIEW_TEXT) {
        foundation_guest_builder_u32(&widget, 18, 10);
        foundation_guest_builder_u32(&widget, 19, 2);
    }
    foundation_guest_builder_list_append(list, &widget);
}
static uint32_t publish(void) {
    uint8_t widgets_bytes[2048]; foundation_guest_builder widgets, view;
    foundation_guest_builder_list_begin(&widgets, widgets_bytes, sizeof(widgets_bytes));
    add_widget(&widgets, "lhs", FOUNDATION_GUEST_VIEW_TEXT, 20, lhs, "Left operand");
    add_widget(&widgets, "rhs", FOUNDATION_GUEST_VIEW_TEXT, 70, rhs, "Right operand");
    add_widget(&widgets, "sum", FOUNDATION_GUEST_VIEW_BUTTON, 120, "", "Sum");
    add_widget(&widgets, "result", FOUNDATION_GUEST_VIEW_LABEL, 170, result, "Result");
    foundation_guest_builder_begin(&view, request + 64, sizeof(request) - 64);
    foundation_guest_builder_u64(&view, 1, revision);
    foundation_guest_builder_text(&view, 2, "Portable calculator");
    foundation_guest_builder_number(&view, 3, client_width);
    foundation_guest_builder_number(&view, 4, client_height);
    foundation_guest_builder_number(&view, 5, display_scale);
    foundation_guest_builder_list(&view, 6, &widgets);
    uint32_t status = invoke(view_handle, FOUNDATION_GUEST_VIEW_REPLACE, view.bytes);
    if (status) return status;
    foundation_guest_record r; foundation_guest_field field;
    foundation_guest_record_begin(&r, reply + 64, foundation_guest_read_u32(reply) - 64);
    if (foundation_guest_record_next(&r, &field) != 1 || field.id != 1 || field.type != FOUNDATION_APPENDED_FIELD_U64 ||
        revision == UINT64_MAX || foundation_guest_read_u64(field.data) != revision + 1 ||
        foundation_guest_record_next(&r, &field) != 0) return FOUNDATION_APPENDED_APP_FAILED;
    ++revision; return acknowledge();
}
uint32_t foundation_guest_initialize(const uint8_t *context, uint32_t bytes) {
    (void)context; (void)bytes;
    static const uint8_t name[] = FOUNDATION_GUEST_VIEW_NAME;
    static const uint8_t schema[32] = {FOUNDATION_GUEST_VIEW_SCHEMA_BYTES};
    uint32_t n = foundation_guest_discovery(request + 64, sizeof(request) - 64, name, sizeof(name) - 1, 1, 0, 0, schema);
    uint32_t status = invoke(0, FOUNDATION_APPENDED_CONTROL_DISCOVER, n);
    if (status || !foundation_guest_discovery_handle(reply + 64, foundation_guest_read_u32(reply) - 64, &view_handle) || !view_handle)
        return FOUNDATION_APPENDED_APP_FAILED;
    status = acknowledge(); return status ? status : publish();
}
static int equal(const uint8_t *data, uint32_t bytes, const char *text) {
    uint32_t i = 0; while (text[i]) { if (i == bytes || data[i] != (uint8_t)text[i]) return 0; ++i; }
    return i == bytes;
}
static int number(const char *text, uint32_t *out) {
    uint32_t value = 0, i = 0;
    while (text[i]) {
        uint32_t digit = (uint8_t)text[i++] - (uint8_t)'0';
        if (digit > 9 || value > (UINT32_MAX - digit) / 10) return 0;
        value = value * 10 + digit;
    }
    if (!i) return 0;
    *out = value; return 1;
}
static void calculate(void) {
    uint32_t a, b;
    const char *error = 0;
    if (!number(lhs, &a) || !number(rhs, &b)) error = "Enter whole numbers from 0 to 4294967295";
    else if (a > UINT32_MAX - b) error = "Overflow";
    if (error) { uint32_t i = 0; do { result[i] = error[i]; } while (error[i++]); return; }
    uint32_t value = a + b, count = 0; char digits[10];
    do { digits[count++] = (char)('0' + value % 10); value /= 10; } while (value);
    for (uint32_t i = 0; i != count; ++i) result[i] = digits[count - i - 1];
    result[count] = 0;
}
uint32_t foundation_guest_dispatch(const uint8_t *message, uint32_t bytes) {
    foundation_guest_envelope e; foundation_guest_record r; foundation_guest_field f, target = {0}, value = {0}, base = {0};
    uint64_t event_revision = 0; uint32_t event_kind = 0, input_kind = 0; int next;
    if (!foundation_guest_decode_envelope(message, bytes, &e) || e.kind != FOUNDATION_APPENDED_MESSAGE_EVENT ||
        e.interface_handle != view_handle || e.operation != 1) return FOUNDATION_APPENDED_APP_INVALID_INPUT;
    foundation_guest_record_begin(&r, message + 64, bytes - 64);
    while ((next = foundation_guest_record_next(&r, &f)) == 1) {
        if (f.id == 1 && f.type == FOUNDATION_APPENDED_FIELD_U64) event_revision = foundation_guest_read_u64(f.data);
        else if (f.id == 2 && f.type == FOUNDATION_APPENDED_FIELD_U32) event_kind = foundation_guest_read_u32(f.data);
        else if (f.id == 3 && f.type == FOUNDATION_APPENDED_FIELD_RECORD) target = f;
        else if (f.id == 4 && f.type == FOUNDATION_APPENDED_FIELD_U32) input_kind = foundation_guest_read_u32(f.data);
        else if (f.id == 5 && f.type == FOUNDATION_APPENDED_FIELD_UTF8) value = f;
        else if (f.id == 6 && f.type == FOUNDATION_APPENDED_FIELD_UTF8) base = f;
        else if (f.id >= 11 && f.id <= 13 && f.type == FOUNDATION_APPENDED_FIELD_F64) {
            double dimension = foundation_guest_field_number(&f);
            if (f.id == 11) client_width = dimension;
            if (f.id == 12) client_height = dimension;
            if (f.id == 13) display_scale = dimension;
        } else if (f.flags) return FOUNDATION_APPENDED_APP_INVALID_INPUT;
    }
    if (next < 0 || event_revision != revision) return FOUNDATION_APPENDED_APP_INVALID_INPUT;
    if (event_kind == 3) return publish();
    if (event_kind != 1 || !target.data) return FOUNDATION_APPENDED_APP_INVALID_INPUT;
    foundation_guest_record_begin(&r, target.data, target.bytes);
    foundation_guest_field id, generation;
    if (foundation_guest_record_next(&r, &id) != 1 || id.id != 1 || id.type != FOUNDATION_APPENDED_FIELD_UTF8 ||
        foundation_guest_record_next(&r, &generation) != 1 || generation.id != 2 || generation.type != FOUNDATION_APPENDED_FIELD_U64 ||
        foundation_guest_read_u64(generation.data) != 1 || foundation_guest_record_next(&r, &f) != 0)
        return FOUNDATION_APPENDED_APP_INVALID_INPUT;
    if (input_kind == 3) {
        char *text = equal(id.data, id.bytes, "lhs") ? lhs : equal(id.data, id.bytes, "rhs") ? rhs : 0;
        if (!text || !value.data || !base.data || value.bytes > 10 || !equal(base.data, base.bytes, text))
            return FOUNDATION_APPENDED_APP_INVALID_INPUT;
        for (uint32_t i = 0; i != value.bytes; ++i) text[i] = (char)value.data[i];
        text[value.bytes] = 0;
    } else if ((input_kind == 1 && equal(id.data, id.bytes, "sum")) ||
               (input_kind == 7 && (equal(id.data, id.bytes, "lhs") || equal(id.data, id.bytes, "rhs")))) calculate();
    else return FOUNDATION_APPENDED_APP_INVALID_INPUT;
    return publish();
}
