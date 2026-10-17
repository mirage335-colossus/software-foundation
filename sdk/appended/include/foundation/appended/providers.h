#ifndef FOUNDATION_APPENDED_GUEST_PROVIDERS_H
#define FOUNDATION_APPENDED_GUEST_PROVIDERS_H
#include <foundation/appended/guest.h>
#include <foundation/appended/provider_abi.h>

/* These local values never cross the wire as native structures. Providers are
 * registered from foundation_guest_initialize. Existing dispatch hooks decode
 * calls and send one explicit response before returning APP_OK. No extra export
 * or implicit handler is installed by this header. All scratch belongs to the
 * caller and request/reply storage must not overlap. Helpers use the runtime's
 * common sequence source, acknowledge completed requests, and return APP_*.
 * A nonzero helper result is terminal for the application invocation. */
typedef struct foundation_guest_provider_descriptor {
    const uint8_t *name;
    uint32_t name_bytes;
    uint32_t major, minor;
    const uint8_t *schema;
    uint32_t maximum_request_bytes, maximum_reply_bytes;
} foundation_guest_provider_descriptor;

typedef struct foundation_guest_provider_call {
    uint64_t invocation, provider;
    uint32_t operation;
    const uint8_t *payload;
    uint32_t payload_bytes;
} foundation_guest_provider_call;

/* Internal helpers are inline so no separately linked SDK object is required. */
static inline int foundation_guest_provider_equal_(const uint8_t *a, const uint8_t *b, uint32_t n) {
    for (uint32_t i = 0; i != n; ++i) if (a[i] != b[i]) return 0;
    return 1;
}
static inline int foundation_guest_provider_name_(const uint8_t *name, uint32_t bytes) {
    if (!name || !bytes || bytes > FOUNDATION_PROVIDER_MAX_NAME_BYTES) return 0;
    int first = 1, namespaced = 0;
    for (uint32_t i = 0; i != bytes; ++i) {
        uint8_t c = name[i];
        if (c == '.') { if (first) return 0; first = 1; namespaced = 1; }
        else if (c >= 'a' && c <= 'z') first = 0;
        else if (first || !((c >= '0' && c <= '9') || c == '-' || c == '_')) return 0;
    }
    return namespaced && !first;
}
static inline int foundation_guest_provider_schema_(const uint8_t *schema) {
    if (!schema) return 0;
    for (uint32_t i = 0; i != 32; ++i) if (schema[i]) return 1;
    return 0;
}
static inline uint32_t foundation_guest_provider_u32_(uint8_t *out, uint32_t capacity,
                                                     uint32_t bytes, uint16_t id, uint32_t value) {
    uint8_t scalar[4]; foundation_guest_write_u32(scalar, value);
    return foundation_guest_field_write(out, capacity, bytes, id, FOUNDATION_APPENDED_FIELD_U32, 1, scalar, 4);
}
static inline uint32_t foundation_guest_provider_u64_(uint8_t *out, uint32_t capacity,
                                                     uint32_t bytes, uint16_t id, uint64_t value) {
    uint8_t scalar[8]; foundation_guest_write_u64(scalar, value);
    return foundation_guest_field_write(out, capacity, bytes, id, FOUNDATION_APPENDED_FIELD_U64, 1, scalar, 8);
}

/* Encodes a registration record without allocating or calling the host. Failure
 * returns UINT32_MAX; never submit a failed builder's partial bytes. */
static inline uint32_t foundation_guest_provider_registration(const foundation_guest_provider_descriptor *d,
                                                              uint8_t *out, uint32_t capacity) {
    static const uint8_t reserved[] = "foundation.";
    if (!d || !foundation_guest_provider_name_(d->name, d->name_bytes) || !foundation_guest_provider_schema_(d->schema) ||
        !d->major || d->major > 65535 || d->minor > 65535 ||
        d->maximum_request_bytes > FOUNDATION_PROVIDER_MAX_PAYLOAD_BYTES ||
        d->maximum_reply_bytes > FOUNDATION_PROVIDER_MAX_PAYLOAD_BYTES ||
        (d->name_bytes >= sizeof(reserved) - 1 &&
         foundation_guest_provider_equal_(d->name, reserved, sizeof(reserved) - 1))) return UINT32_MAX;
    uint32_t n = foundation_guest_field_write(out, capacity, 0, 1, FOUNDATION_APPENDED_FIELD_UTF8, 1, d->name, d->name_bytes);
    n = foundation_guest_provider_u32_(out, capacity, n, 2, d->major);
    n = foundation_guest_provider_u32_(out, capacity, n, 3, d->minor);
    n = foundation_guest_field_write(out, capacity, n, 4, FOUNDATION_APPENDED_FIELD_BYTES, 1, d->schema, 32);
    n = foundation_guest_provider_u32_(out, capacity, n, 5, d->maximum_request_bytes);
    return foundation_guest_provider_u32_(out, capacity, n, 6, d->maximum_reply_bytes);
}

/* The request payload has already been built at request + ENVELOPE_BYTES. */
static inline uint32_t foundation_guest_provider_invoke_(uint64_t service, uint32_t operation,
        uint32_t payload_bytes, uint8_t *request, uint32_t request_capacity,
        uint8_t *reply, uint32_t reply_capacity, foundation_guest_envelope *received) {
    uint32_t maximum = foundation_guest_maximum_message();
    if (!request || !reply || !received || maximum < FOUNDATION_APPENDED_ENVELOPE_BYTES ||
        request_capacity < FOUNDATION_APPENDED_ENVELOPE_BYTES || reply_capacity < FOUNDATION_APPENDED_ENVELOPE_BYTES ||
        payload_bytes > request_capacity - FOUNDATION_APPENDED_ENVELOPE_BYTES ||
        payload_bytes > maximum - FOUNDATION_APPENDED_ENVELOPE_BYTES) return FOUNDATION_APPENDED_APP_INVALID_INPUT;
    foundation_guest_envelope sent = {FOUNDATION_APPENDED_MESSAGE_REQUEST, 0,
        foundation_guest_generation(), foundation_guest_next_sequence(), service, operation, 0, 0};
    if (!sent.sequence) return FOUNDATION_APPENDED_APP_EXHAUSTED;
    if (!foundation_guest_encode_envelope(request, request_capacity, &sent, payload_bytes)) return FOUNDATION_APPENDED_APP_INVALID_INPUT;
    if (reply_capacity > maximum) reply_capacity = maximum;
    if (foundation_guest_call(request, FOUNDATION_APPENDED_ENVELOPE_BYTES + payload_bytes, reply, reply_capacity)
        != FOUNDATION_APPENDED_TRANSPORT_OK) return FOUNDATION_APPENDED_APP_FAILED;
    uint32_t total = foundation_guest_read_u32(reply);
    if (total > reply_capacity || !foundation_guest_decode_envelope(reply, total, received) ||
        received->kind != FOUNDATION_APPENDED_MESSAGE_REPLY || received->generation != sent.generation ||
        received->sequence != sent.sequence || received->interface_handle != service || received->operation != operation ||
        received->status == FOUNDATION_APPENDED_SERVICE_RESULT_AVAILABLE ||
        (received->status != FOUNDATION_APPENDED_SERVICE_OK && total != FOUNDATION_APPENDED_ENVELOPE_BYTES))
        return FOUNDATION_APPENDED_APP_FAILED;
    return FOUNDATION_APPENDED_APP_OK;
}
static inline uint32_t foundation_guest_provider_ack_(uint64_t through, uint8_t *request,
        uint32_t request_capacity, uint8_t *reply, uint32_t reply_capacity) {
    if (!request || request_capacity < FOUNDATION_APPENDED_ENVELOPE_BYTES) return FOUNDATION_APPENDED_APP_INVALID_INPUT;
    uint32_t n = foundation_guest_provider_u64_(request + FOUNDATION_APPENDED_ENVELOPE_BYTES,
        request_capacity - FOUNDATION_APPENDED_ENVELOPE_BYTES, 0, 1, through);
    foundation_guest_envelope received;
    uint32_t result = foundation_guest_provider_invoke_(0, FOUNDATION_APPENDED_CONTROL_ACKNOWLEDGE,
        n, request, request_capacity, reply, reply_capacity, &received);
    if (result) return result;
    return received.status == FOUNDATION_APPENDED_SERVICE_OK &&
        foundation_guest_read_u32(reply) == FOUNDATION_APPENDED_ENVELOPE_BYTES ?
        FOUNDATION_APPENDED_APP_OK : FOUNDATION_APPENDED_APP_FAILED;
}
static inline uint32_t foundation_guest_provider_complete_(const foundation_guest_envelope *completed,
        uint8_t *request, uint32_t request_capacity, uint8_t *reply, uint32_t reply_capacity) {
    uint32_t service_status = completed->status;
    uint32_t result = foundation_guest_provider_ack_(completed->sequence, request, request_capacity, reply, reply_capacity);
    return result ? result : service_status == FOUNDATION_APPENDED_SERVICE_OK ?
        FOUNDATION_APPENDED_APP_OK : FOUNDATION_APPENDED_APP_FAILED;
}

/* Bootstrap discovery pins the exact version and schema, and validates the
 * returned descriptor before exposing a handle. Output is unchanged on failure. */
static inline uint32_t foundation_guest_provider_discover_service(uint64_t *service,
        uint8_t *request, uint32_t request_capacity, uint8_t *reply, uint32_t reply_capacity) {
    static const uint8_t name[] = FOUNDATION_PROVIDER_SERVICE_NAME;
    static const uint8_t schema[] = {FOUNDATION_PROVIDER_SCHEMA_BYTES};
    if (!service || !request || request_capacity < FOUNDATION_APPENDED_ENVELOPE_BYTES) return FOUNDATION_APPENDED_APP_INVALID_INPUT;
    uint32_t n = foundation_guest_discovery(request + FOUNDATION_APPENDED_ENVELOPE_BYTES,
        request_capacity - FOUNDATION_APPENDED_ENVELOPE_BYTES, name, sizeof(name) - 1,
        FOUNDATION_PROVIDER_MAJOR, FOUNDATION_PROVIDER_MINOR, FOUNDATION_PROVIDER_MINOR, schema);
    foundation_guest_envelope completed;
    uint32_t result = foundation_guest_provider_invoke_(0, FOUNDATION_APPENDED_CONTROL_DISCOVER,
        n, request, request_capacity, reply, reply_capacity, &completed);
    if (result) return result;
    uint64_t handle = 0;
    if (completed.status == FOUNDATION_APPENDED_SERVICE_OK) {
        foundation_guest_record record; foundation_guest_field field; uint32_t found = 0; int next;
        foundation_guest_record_begin(&record, reply + FOUNDATION_APPENDED_ENVELOPE_BYTES,
            foundation_guest_read_u32(reply) - FOUNDATION_APPENDED_ENVELOPE_BYTES);
        while ((next = foundation_guest_record_next(&record, &field)) == 1) {
            if (field.id <= 6) {
                uint8_t type = field.id == 1 ? FOUNDATION_APPENDED_FIELD_U64 : field.id == 2 ? FOUNDATION_APPENDED_FIELD_UTF8 :
                    field.id == 5 ? FOUNDATION_APPENDED_FIELD_BYTES : FOUNDATION_APPENDED_FIELD_U32;
                if (field.flags != 1 || field.type != type ||
                    (field.id == 2 && (field.bytes != sizeof(name) - 1 || !foundation_guest_provider_equal_(field.data, name, field.bytes))) ||
                    (field.id == 3 && foundation_guest_read_u32(field.data) != FOUNDATION_PROVIDER_MAJOR) ||
                    (field.id == 4 && foundation_guest_read_u32(field.data) != FOUNDATION_PROVIDER_MINOR) ||
                    (field.id == 5 && (field.bytes != 32 || !foundation_guest_provider_equal_(field.data, schema, 32))) ||
                    (field.id == 6 && foundation_guest_read_u32(field.data) > FOUNDATION_APPENDED_MAX_MESSAGE_BYTES - FOUNDATION_APPENDED_ENVELOPE_BYTES))
                    return FOUNDATION_APPENDED_APP_FAILED;
                if (field.id == 1) handle = foundation_guest_read_u64(field.data);
                found |= 1u << (field.id - 1);
            } else if (field.flags) return FOUNDATION_APPENDED_APP_FAILED;
        }
        if (next < 0 || found != 63 || !handle) return FOUNDATION_APPENDED_APP_FAILED;
    }
    result = foundation_guest_provider_complete_(&completed, request, request_capacity, reply, reply_capacity);
    if (!result) *service = handle;
    return result;
}

static inline uint32_t foundation_guest_provider_register(uint64_t service,
        const foundation_guest_provider_descriptor *descriptor, uint64_t *provider,
        uint8_t *request, uint32_t request_capacity, uint8_t *reply, uint32_t reply_capacity) {
    if (!service || !provider || !request || request_capacity < FOUNDATION_APPENDED_ENVELOPE_BYTES)
        return FOUNDATION_APPENDED_APP_INVALID_INPUT;
    uint32_t n = foundation_guest_provider_registration(descriptor, request + FOUNDATION_APPENDED_ENVELOPE_BYTES,
        request_capacity - FOUNDATION_APPENDED_ENVELOPE_BYTES);
    foundation_guest_envelope completed;
    uint32_t result = foundation_guest_provider_invoke_(service, FOUNDATION_PROVIDER_REGISTER, n,
        request, request_capacity, reply, reply_capacity, &completed);
    if (result) return result;
    uint64_t handle = 0;
    if (completed.status == FOUNDATION_APPENDED_SERVICE_OK) {
        foundation_guest_record record; foundation_guest_field field; uint32_t found = 0; int next;
        foundation_guest_record_begin(&record, reply + FOUNDATION_APPENDED_ENVELOPE_BYTES,
            foundation_guest_read_u32(reply) - FOUNDATION_APPENDED_ENVELOPE_BYTES);
        while ((next = foundation_guest_record_next(&record, &field)) == 1) {
            if (field.id == 1) {
                if (field.flags != 1 || field.type != FOUNDATION_APPENDED_FIELD_U64) return FOUNDATION_APPENDED_APP_FAILED;
                handle = foundation_guest_read_u64(field.data); found = 1;
            } else if (field.flags) return FOUNDATION_APPENDED_APP_FAILED;
        }
        if (next < 0 || !found || !handle) return FOUNDATION_APPENDED_APP_FAILED;
    }
    result = foundation_guest_provider_complete_(&completed, request, request_capacity, reply, reply_capacity);
    if (!result) *provider = handle;
    return result;
}

/* A provider discovery result owns its scalar values and schema. The returned
 * name is checked against the caller's query, so no reply-buffer borrow escapes. */
typedef struct foundation_guest_provider_query {
    const uint8_t *name;
    uint32_t name_bytes, major, minimum_minor, maximum_minor;
    const uint8_t *schema; /* optional exact 32-byte pin */
} foundation_guest_provider_query;
typedef struct foundation_guest_provider_discovery {
    uint64_t provider;
    uint32_t major, minor;
    uint8_t schema[32];
    uint32_t maximum_request_bytes, maximum_reply_bytes;
} foundation_guest_provider_discovery;

static inline uint32_t foundation_guest_provider_discover(uint64_t service,
        const foundation_guest_provider_query *query, foundation_guest_provider_discovery *discovery,
        uint8_t *request, uint32_t request_capacity, uint8_t *reply, uint32_t reply_capacity) {
    if (!service || !query || !discovery || !foundation_guest_provider_name_(query->name, query->name_bytes) ||
        (query->schema && !foundation_guest_provider_schema_(query->schema)) || !request || request_capacity < FOUNDATION_APPENDED_ENVELOPE_BYTES)
        return FOUNDATION_APPENDED_APP_INVALID_INPUT;
    uint32_t n = foundation_guest_discovery(request + FOUNDATION_APPENDED_ENVELOPE_BYTES,
        request_capacity - FOUNDATION_APPENDED_ENVELOPE_BYTES, query->name, query->name_bytes,
        query->major, query->minimum_minor, query->maximum_minor, query->schema);
    foundation_guest_envelope completed;
    uint32_t result = foundation_guest_provider_invoke_(service, FOUNDATION_PROVIDER_DISCOVER, n,
        request, request_capacity, reply, reply_capacity, &completed);
    if (result) return result;
    foundation_guest_provider_discovery value = {0, 0, 0, {0}, 0, 0};
    if (completed.status == FOUNDATION_APPENDED_SERVICE_OK) {
        foundation_guest_record record; foundation_guest_field field; uint32_t found = 0; int next;
        foundation_guest_record_begin(&record, reply + FOUNDATION_APPENDED_ENVELOPE_BYTES,
            foundation_guest_read_u32(reply) - FOUNDATION_APPENDED_ENVELOPE_BYTES);
        while ((next = foundation_guest_record_next(&record, &field)) == 1) {
            if (field.id <= 7) {
                uint8_t type = field.id == 1 ? FOUNDATION_APPENDED_FIELD_U64 : field.id == 2 ? FOUNDATION_APPENDED_FIELD_UTF8 :
                    field.id == 5 ? FOUNDATION_APPENDED_FIELD_BYTES : FOUNDATION_APPENDED_FIELD_U32;
                if (field.type != type || field.flags != 1 ||
                    (field.id == 2 && (field.bytes != query->name_bytes || !foundation_guest_provider_equal_(field.data, query->name, field.bytes))) ||
                    (field.id == 5 && (field.bytes != 32 || (query->schema && !foundation_guest_provider_equal_(field.data, query->schema, 32)))))
                    return FOUNDATION_APPENDED_APP_FAILED;
                if (field.id == 1) value.provider = foundation_guest_read_u64(field.data);
                if (field.id == 3) value.major = foundation_guest_read_u32(field.data);
                if (field.id == 4) value.minor = foundation_guest_read_u32(field.data);
                if (field.id == 5) for (uint32_t i = 0; i != 32; ++i) value.schema[i] = field.data[i];
                if (field.id == 6) value.maximum_request_bytes = foundation_guest_read_u32(field.data);
                if (field.id == 7) value.maximum_reply_bytes = foundation_guest_read_u32(field.data);
                found |= 1u << (field.id - 1);
            } else if (field.flags) return FOUNDATION_APPENDED_APP_FAILED;
        }
        if (next < 0 || found != 127 || !value.provider || value.major != query->major ||
            value.minor < query->minimum_minor || value.minor > query->maximum_minor ||
            value.maximum_request_bytes > FOUNDATION_PROVIDER_MAX_PAYLOAD_BYTES ||
            value.maximum_reply_bytes > FOUNDATION_PROVIDER_MAX_PAYLOAD_BYTES) return FOUNDATION_APPENDED_APP_FAILED;
    }
    result = foundation_guest_provider_complete_(&completed, request, request_capacity, reply, reply_capacity);
    if (!result) *discovery = value;
    return result;
}

/* Returned payload borrows message only until the enclosing dispatch returns.
 * Unknown optional fields skip; defined fields must use must-understand. */
static inline int foundation_guest_provider_decode_call(const uint8_t *message, uint32_t bytes,
        uint64_t service, foundation_guest_provider_call *call) {
    foundation_guest_envelope envelope; foundation_guest_provider_call value = {0, 0, 0, 0, 0};
    if (!call || !service || !foundation_guest_decode_envelope(message, bytes, &envelope) ||
        envelope.kind != FOUNDATION_APPENDED_MESSAGE_EVENT || envelope.interface_handle != service ||
        envelope.generation != foundation_guest_generation() || envelope.operation != FOUNDATION_PROVIDER_EVENT_CALL ||
        envelope.status != FOUNDATION_APPENDED_SERVICE_OK || !envelope.correlation) return 0;
    value.invocation = envelope.correlation;
    foundation_guest_record record; foundation_guest_field field; uint32_t found = 0; int next;
    foundation_guest_record_begin(&record, message + FOUNDATION_APPENDED_ENVELOPE_BYTES,
        bytes - FOUNDATION_APPENDED_ENVELOPE_BYTES);
    while ((next = foundation_guest_record_next(&record, &field)) == 1) {
        if (field.id <= 3) {
            uint8_t type = field.id == 1 ? FOUNDATION_APPENDED_FIELD_U64 : field.id == 2 ?
                FOUNDATION_APPENDED_FIELD_U32 : FOUNDATION_APPENDED_FIELD_BYTES;
            if (field.type != type || field.flags != 1) return 0;
            if (field.id == 1) value.provider = foundation_guest_read_u64(field.data);
            if (field.id == 2) value.operation = foundation_guest_read_u32(field.data);
            if (field.id == 3) {
                if (field.bytes > FOUNDATION_PROVIDER_MAX_PAYLOAD_BYTES) return 0;
                value.payload = field.data; value.payload_bytes = field.bytes;
            }
            found |= 1u << (field.id - 1);
        } else if (field.flags) return 0;
    }
    if (next < 0 || found != 7 || !value.provider) return 0;
    *call = value; return 1;
}

static inline uint32_t foundation_guest_provider_respond(uint64_t service,
        const foundation_guest_provider_call *call, uint32_t status, const uint8_t *payload, uint32_t payload_bytes,
        uint8_t *request, uint32_t request_capacity, uint8_t *reply, uint32_t reply_capacity) {
    if (!service || !call || !call->invocation || !call->provider || !request ||
        request_capacity < FOUNDATION_APPENDED_ENVELOPE_BYTES || status > FOUNDATION_APPENDED_SERVICE_UNCERTAIN ||
        status == FOUNDATION_APPENDED_SERVICE_RESULT_AVAILABLE || payload_bytes > FOUNDATION_PROVIDER_MAX_PAYLOAD_BYTES ||
        (status != FOUNDATION_APPENDED_SERVICE_OK && payload_bytes) || (payload_bytes && !payload))
        return FOUNDATION_APPENDED_APP_INVALID_INPUT;
    uint8_t *out = request + FOUNDATION_APPENDED_ENVELOPE_BYTES;
    uint32_t capacity = request_capacity - FOUNDATION_APPENDED_ENVELOPE_BYTES;
    uint32_t n = foundation_guest_provider_u64_(out, capacity, 0, 1, call->invocation);
    n = foundation_guest_provider_u64_(out, capacity, n, 2, call->provider);
    n = foundation_guest_provider_u32_(out, capacity, n, 3, status);
    n = foundation_guest_field_write(out, capacity, n, 4, FOUNDATION_APPENDED_FIELD_BYTES, 1, payload, payload_bytes);
    foundation_guest_envelope completed;
    uint32_t result = foundation_guest_provider_invoke_(service, FOUNDATION_PROVIDER_RESPOND, n,
        request, request_capacity, reply, reply_capacity, &completed);
    if (result) return result;
    if (completed.status == FOUNDATION_APPENDED_SERVICE_OK && foundation_guest_read_u32(reply) != FOUNDATION_APPENDED_ENVELOPE_BYTES)
        return FOUNDATION_APPENDED_APP_FAILED;
    return foundation_guest_provider_complete_(&completed, request, request_capacity, reply, reply_capacity);
}
#endif
