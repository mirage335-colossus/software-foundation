// SPDX-License-Identifier: CC0-1.0
// New private guard/helper only. No real engine binding or qualification exists.
#include "EnginePrivate.hpp"
#include <algorithm>
#include <atomic>
#include <climits>
#include <cstring>
#include <limits>
#include <new>
#include <string_view>
#include <thread>
#include <vector>

namespace bib::provider_candidate {
namespace {
constexpr std::uint32_t hard_bytes = 16u * 1024u * 1024u;
constexpr std::uint32_t service_unavailable = 2, service_uncertain = 14;
constexpr std::size_t maximum_operations = 16;

bool nonzero(const std::uint8_t* bytes, std::size_t count) {
    return std::any_of(bytes, bytes + count, [](auto byte) { return byte != 0; });
}
bool span_valid(const BibEngineBytesV1& bytes, std::uint32_t bound) {
    return !bytes.reserved && bytes.length <= bound && (!bytes.length || bytes.data)
        && bytes.length <= UINTPTR_MAX - reinterpret_cast<std::uintptr_t>(bytes.data);
}
std::int32_t transport(std::int32_t status) { return status <= 0 && status >= BIB_ENGINE_PROCESS_EXIT_REQUIRED ? status : BIB_ENGINE_INVALID; }
bool same(const BibEngineDocumentV1& left, const BibEngineDocumentV1& right) {
    return left.application_instance == right.application_instance && left.document_sequence == right.document_sequence
        && left.service_generation == right.service_generation;
}
bool overlaps(const void* a, std::size_t na, const void* b, std::size_t nb) {
    const auto x = reinterpret_cast<std::uintptr_t>(a), y = reinterpret_cast<std::uintptr_t>(b);
    if ((!a && na) || (!b && nb) || na > UINTPTR_MAX - x || nb > UINTPTR_MAX - y) return true;
    return na && nb && x < y + nb && y < x + na;
}
bool limits_valid(const BibEngineLimitsV1& value) {
    return value.size == sizeof(value) && !value.reserved && value.maximum_command_bytes && value.maximum_query_bytes
        && value.maximum_reply_bytes && value.maximum_service_message_bytes && value.maximum_retired_documents
        && value.maximum_inflight_resources && value.maximum_command_bytes <= hard_bytes
        && value.maximum_query_bytes <= hard_bytes && value.maximum_reply_bytes <= hard_bytes
        && value.maximum_service_message_bytes <= 1048576u && value.maximum_retired_documents <= 64u
        && value.maximum_inflight_resources <= 4096u && value.maximum_resource_response_bytes
        && value.maximum_resource_response_bytes <= SIZE_MAX && value.maximum_retained_resource_bytes <= SIZE_MAX
        && value.maximum_retained_resource_bytes >= value.maximum_resource_response_bytes;
}
bool limits_within(const BibEngineLimitsV1& a, const BibEngineLimitsV1& b) {
    return a.maximum_command_bytes <= b.maximum_command_bytes && a.maximum_query_bytes <= b.maximum_query_bytes
        && a.maximum_reply_bytes <= b.maximum_reply_bytes && a.maximum_service_message_bytes <= b.maximum_service_message_bytes
        && a.maximum_retired_documents <= b.maximum_retired_documents && a.maximum_inflight_resources <= b.maximum_inflight_resources
        && a.maximum_resource_response_bytes <= b.maximum_resource_response_bytes
        && a.maximum_retained_resource_bytes <= b.maximum_retained_resource_bytes;
}
bool target_valid(const BibEngineBuildV1& b) {
    if (b.size != sizeof(b) || b.layout_revision != BIB_ENGINE_LAYOUT_V1 || b.reserved || b.pointer_bits != sizeof(void*) * CHAR_BIT
        || b.lifetime != BIB_ENGINE_LIFETIME_PROCESS || b.maximum_starts != 1
        || (b.capabilities & ~known_capabilities) || std::memcmp(b.contract_header_sha256, contract_header_sha256.data(), 32)
        || !nonzero(b.build_identity_sha256, 32) || !nonzero(b.source_recipe_sha256, 32)) return false;
#if defined(__EMSCRIPTEN__)
    return b.target_system == BIB_ENGINE_TARGET_BROWSER_WASM && b.target_processor == BIB_ENGINE_CPU_WASM32 && b.pointer_bits == 32;
#elif defined(_WIN32) && (defined(_M_X64) || defined(__x86_64__))
    return b.target_system == BIB_ENGINE_TARGET_WINDOWS && b.target_processor == BIB_ENGINE_CPU_X86_64 && b.pointer_bits == 64;
#elif defined(__linux__) && defined(__x86_64__)
    return b.target_system == BIB_ENGINE_TARGET_LINUX && b.target_processor == BIB_ENGINE_CPU_X86_64 && b.pointer_bits == 64;
#elif defined(__linux__) && defined(__aarch64__)
    return b.target_system == BIB_ENGINE_TARGET_LINUX && b.target_processor == BIB_ENGINE_CPU_AARCH64 && b.pointer_bits == 64;
#else
    return false;
#endif
}
bool entry_shape_valid(const BibEngineStartV1& config) {
    const auto* bytes = config.entry_url.data;
    const auto size = config.entry_url.length;
    if (size < 76 || std::memcmp(bytes, "app://", 6) || std::memcmp(bytes + 70, "/web/", 5)) return false;
    constexpr char hex[] = "0123456789abcdef";
    for (std::uint32_t i = 0; i < 32; ++i)
        if (bytes[6 + i*2] != hex[config.application_package_sha256[i] >> 4]
            || bytes[7 + i*2] != hex[config.application_package_sha256[i] & 15]) return false;
    const auto path = std::string_view(reinterpret_cast<const char*>(bytes + 75), size - 75);
    for (auto c : path) if (static_cast<unsigned char>(c) < 0x21 || static_cast<unsigned char>(c) >= 0x7f || c == '\\' || c == '?' || c == '#') return false;
    std::size_t offset = 0;
    while (offset <= path.size()) {
        auto slash = path.find('/', offset); if (slash == std::string_view::npos) slash = path.size();
        auto segment = path.substr(offset, slash - offset);
        if (segment.empty() || segment == "." || segment == "..") return false;
        if (slash == path.size()) break;
        offset = slash + 1;
    }
    return true; // Full canonical decoding/exact immutable entry is private preflight's obligation.
}
std::uint64_t operation_cap(std::uint32_t kind, bool query) {
    if (query) {
        if (kind == BIB_ENGINE_QUERY_SEMANTIC_SNAPSHOT) return BIB_ENGINE_CAP_SEMANTIC_SNAPSHOT_V1;
        if (kind == BIB_ENGINE_QUERY_EDITOR_FLAGS) return BIB_ENGINE_CAP_COMPOSITION_V1;
    } else {
        switch (kind) {
        case BIB_ENGINE_COMMAND_KEY: return BIB_ENGINE_CAP_KEY_V1;
        case BIB_ENGINE_COMMAND_COMPOSITION: return BIB_ENGINE_CAP_COMPOSITION_V1;
        case BIB_ENGINE_COMMAND_FOCUS: return BIB_ENGINE_CAP_FOCUS_V1;
        case BIB_ENGINE_COMMAND_SEMANTIC_ACTION: return BIB_ENGINE_CAP_SEMANTIC_ACTION_V1;
        case BIB_ENGINE_COMMAND_POINTER: return BIB_ENGINE_CAP_POINTER_V1;
        }
    }
    return 0;
}

class Runtime {
public:
    std::atomic_flag busy = ATOMIC_FLAG_INIT;
    std::atomic<std::uint32_t> phase {BIB_ENGINE_START_NOT_RETAINED};
    std::thread::id owner;
    bool bound = false, ready = false, poisoned = false;
    EnginePrivateV1 backend{};
    std::array<Operation, maximum_operations> commands{}, queries{};
    BibEngineHostV1 host{};
    BibEngineStartV1 start_config{};
    std::vector<std::uint8_t> entry, persistence;
    std::uint64_t last_sequence = 0;

    struct Gate {
        Runtime& runtime;
        bool locked = false;
        std::int32_t status = BIB_ENGINE_OK;
        Gate(Runtime& value, bool require_owner) : runtime(value) {
            if (require_owner && value.phase.load(std::memory_order_acquire) != BIB_ENGINE_START_NOT_RETAINED
                && value.owner != std::this_thread::get_id()) { status = BIB_ENGINE_WRONG_THREAD; return; }
            locked = !value.busy.test_and_set(std::memory_order_acquire);
            if (!locked) status = BIB_ENGINE_REENTRANT;
        }
        ~Gate() { if (locked) runtime.busy.clear(std::memory_order_release); }
        explicit operator bool() const { return locked; }
    };
    struct Turn {
        Runtime& runtime;
        bool entered = false;
        explicit Turn(Runtime& r) : runtime(r) {
            try {
                const auto status = r.host.enter_engine(r.host.context);
                entered = status == 0;
                if (status > service_uncertain) r.poisoned = true;
            }
            catch (...) { r.poisoned = true; }
        }
        void finish() {
            if (!entered) return;
            entered = false;
            try { runtime.host.leave_engine(runtime.host.context); }
            catch (...) { runtime.poisoned = true; }
        }
        ~Turn() { finish(); }
    };

    const Operation* find(std::uint32_t kind, bool query) const {
        const auto& list = query ? queries : commands;
        const auto count = query ? backend.query_count : backend.command_count;
        for (std::uint32_t i = 0; i < count; ++i) if (list[i].kind == kind) return &list[i];
        return nullptr;
    }
    bool catalog_valid(const Operation* data, std::uint32_t count, bool query) const {
        if (count > maximum_operations || (count && !data)) return false;
        for (std::uint32_t i = 0; i < count; ++i) {
            auto cap = operation_cap(data[i].kind, query);
            if (!cap || data[i].capability != cap || !(backend.build.capabilities & cap)
                || !data[i].required_reply_capacity || data[i].required_reply_capacity > backend.limits.maximum_reply_bytes
                || data[i].maximum_input_bytes > (query ? backend.limits.maximum_query_bytes : backend.limits.maximum_command_bytes)
                || !nonzero(data[i].schema.data(), data[i].schema.size())) return false;
            for (std::uint32_t j = 0; j < i; ++j) if (data[j].kind == data[i].kind) return false;
        }
        return true;
    }
    std::int32_t bind(const EnginePrivateV1& value) {
        Gate gate(*this, false); if (!gate) return gate.status;
        if (bound || phase.load() != BIB_ENGINE_START_NOT_RETAINED) return BIB_ENGINE_CLOSED;
        if (value.size < sizeof(value) || value.version != private_interface_version || !value.application_instance
            || !target_valid(value.build) || !limits_valid(value.limits) || !value.preflight || !value.start
            || !value.advance || !value.current_document) return BIB_ENGINE_INVALID;
        backend = value; // Not published/usable until every complete validation passes.
        backend.size = sizeof(backend);
        if (!catalog_valid(value.commands, value.command_count, false) || !catalog_valid(value.queries, value.query_count, true)) {
            backend = {}; return BIB_ENGINE_INVALID;
        }
        if ((value.command_count && !value.command) || (value.query_count && !value.query)
            || ((value.build.capabilities & BIB_ENGINE_CAP_SERVICE_QUEUE)
                && (!value.deliver_services || !value.collect_service_ack || !value.dispose_retired_service_document))
            || ((value.build.capabilities & BIB_ENGINE_CAP_APP_BUNDLE) && !value.install_resources)
            || ((value.build.capabilities & BIB_ENGINE_CAP_DIRTY_RGBA8)
                && (value.build.fixed_viewport_width != 800 || value.build.fixed_viewport_height != 600))) { backend = {}; return BIB_ENGINE_INVALID; }
        for (std::uint32_t kind = 1; kind <= BIB_ENGINE_COMMAND_POINTER; ++kind) {
            auto cap = operation_cap(kind, false);
            if ((value.build.capabilities & cap) && (!value.command_count || !std::any_of(value.commands, value.commands + value.command_count,
                    [kind](const auto& op) { return op.kind == kind; }))) { backend = {}; return BIB_ENGINE_INVALID; }
        }
        if ((value.build.capabilities & BIB_ENGINE_CAP_SEMANTIC_SNAPSHOT_V1)
            && (!value.query_count || !std::any_of(value.queries, value.queries + value.query_count,
                [](const auto& op) { return op.kind == BIB_ENGINE_QUERY_SEMANTIC_SNAPSHOT; }))) { backend = {}; return BIB_ENGINE_INVALID; }
        if (value.command_count) std::copy_n(value.commands, value.command_count, commands.begin());
        if (value.query_count) std::copy_n(value.queries, value.query_count, queries.begin());
        backend.commands = commands.data(); backend.queries = queries.data(); bound = true;
        return BIB_ENGINE_OK;
    }
    std::int32_t usable() const {
        if (poisoned) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
        return ready ? BIB_ENGINE_OK : BIB_ENGINE_CLOSED;
    }
    template<class F> std::int32_t turn(F&& function) {
        Turn scope(*this);
        if (!scope.entered) return poisoned ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : BIB_ENGINE_REENTRANT;
        std::int32_t status;
        try { status = transport(function()); } catch (...) { status = BIB_ENGINE_PROCESS_EXIT_REQUIRED; poisoned = true; }
        if (status == BIB_ENGINE_PROCESS_EXIT_REQUIRED) poisoned = true;
        scope.finish();
        return poisoned ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : status;
    }
    bool document_valid(const BibEngineDocumentV1& document) const {
        return document.application_instance == backend.application_instance && document.document_sequence
            && (!(start_config.required_capabilities & BIB_ENGINE_CAP_SERVICE_QUEUE) || document.service_generation);
    }
    std::int32_t check_document(const BibEngineDocumentV1& expected) {
        BibEngineDocumentV1 current{};
        if (!document_valid(expected)) return BIB_ENGINE_STALE;
        auto status = backend.current_document(backend.context, backend.application_instance, &current);
        return status ? status : (document_valid(current) && same(current, expected) ? BIB_ENGINE_OK : BIB_ENGINE_STALE);
    }
    bool enabled(std::uint64_t cap) const { return (start_config.required_capabilities & cap) == cap; }

    std::int32_t start(const BibEngineHostV1* callbacks, const BibEngineStartV1* input, BibEngineStartResultV1* output) {
        Gate gate(*this, true); if (!gate) return gate.status;
        if (!output || output->size < sizeof(*output)) return BIB_ENGINE_INVALID;
        BibEngineStartResultV1 result{sizeof(result), phase.load(), bound ? backend.application_instance : 0};
        if (phase.load() != BIB_ENGINE_START_NOT_RETAINED) { *output = result; return ready && !poisoned ? BIB_ENGINE_CLOSED : BIB_ENGINE_PROCESS_EXIT_REQUIRED; }
        result.application_instance = 0;
        if (!bound) { *output = result; return BIB_ENGINE_UNSUPPORTED; }
        if (!callbacks || callbacks->size < sizeof(*callbacks) || !input || input->size < sizeof(*input)) { *output = result; return BIB_ENGINE_INVALID; }
        const auto captured_host = *callbacks; auto config = *input;
        config.size = sizeof(config);
        if (captured_host.abi_major != BIB_ENGINE_ABI_MAJOR || captured_host.abi_minor != 0 || captured_host.reserved
            || !captured_host.wake || !captured_host.replace_timer_ms || !captured_host.enter_engine || !captured_host.leave_engine
            || config.reserved0 || config.reserved1 || config.raster_output > 1
            || (config.required_capabilities & ~known_capabilities)
            || (config.required_capabilities & backend.build.capabilities) != config.required_capabilities
            || !limits_valid(config.limits) || !limits_within(config.limits, backend.limits)
            || !span_valid(config.entry_url, 8192) || !config.entry_url.length || !span_valid(config.persist_seed, 12u*1024u*1024u)
            || !nonzero(config.application_package_sha256, 32)
            || (config.raster_output && (!(config.required_capabilities & BIB_ENGINE_CAP_DIRTY_RGBA8) || !captured_host.damage))
            || ((config.required_capabilities & BIB_ENGINE_CAP_SERVICE_QUEUE)
                && (!captured_host.begin_service_document || !captured_host.close_service_document || !captured_host.submit_service
                    || !captured_host.cancel_service || !captured_host.stage_service_ack))
            || ((config.required_capabilities & BIB_ENGINE_CAP_APP_BUNDLE)
                && (!captured_host.begin_resource_epoch || !captured_host.retire_resource_epoch))) { *output = result; return BIB_ENGINE_INVALID; }
        for (std::uint32_t i = 0; i < backend.command_count; ++i)
            if ((config.required_capabilities & commands[i].capability)
                && (commands[i].maximum_input_bytes > config.limits.maximum_command_bytes
                    || commands[i].required_reply_capacity > config.limits.maximum_reply_bytes)) { *output = result; return BIB_ENGINE_INVALID; }
        for (std::uint32_t i = 0; i < backend.query_count; ++i)
            if ((config.required_capabilities & queries[i].capability)
                && (queries[i].maximum_input_bytes > config.limits.maximum_query_bytes
                    || queries[i].required_reply_capacity > config.limits.maximum_reply_bytes)) { *output = result; return BIB_ENGINE_INVALID; }
        std::vector<std::uint8_t> copied_entry, copied_persistence;
        try {
            copied_entry.assign(config.entry_url.data, config.entry_url.data + config.entry_url.length);
            if (config.persist_seed.length) copied_persistence.assign(config.persist_seed.data, config.persist_seed.data + config.persist_seed.length);
        } catch (...) { *output = result; return BIB_ENGINE_LIMIT; }
        config.entry_url.data = copied_entry.data(); config.persist_seed.data = copied_persistence.empty() ? nullptr : copied_persistence.data();
        if (!entry_shape_valid(config)) { *output = result; return BIB_ENGINE_INVALID; }
        std::int32_t preflight;
        try { preflight = transport(backend.preflight(backend.context, &config)); } catch (...) { preflight = BIB_ENGINE_INVALID; }
        if (preflight) { *output = result; return preflight; }
        // Everything retained below is a deep copy. Publish commitment BEFORE any callback.
        host = captured_host; host.size = sizeof(host); entry = std::move(copied_entry); persistence = std::move(copied_persistence);
        start_config = config; start_config.entry_url.data = entry.data(); start_config.persist_seed.data = persistence.empty() ? nullptr : persistence.data();
        start_config.size = sizeof(start_config);
        owner = std::this_thread::get_id(); phase.store(BIB_ENGINE_START_PROCESS_COMMITTED, std::memory_order_release);
        result.phase = BIB_ENGINE_START_PROCESS_COMMITTED; result.application_instance = backend.application_instance;
        auto code = turn([&] {
            if (enabled(BIB_ENGINE_CAP_APP_BUNDLE)) {
                auto installed = backend.install_resources(backend.context, &host, &start_config, backend.application_instance);
                if (installed) return installed;
            }
            return backend.start(backend.context, &host, &start_config, backend.application_instance);
        });
        if (!code) { ready = true; phase.store(BIB_ENGINE_START_READY, std::memory_order_release); result.phase = BIB_ENGINE_START_READY; }
        else poisoned = true;
        *output = result;
        return code ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : BIB_ENGINE_OK;
    }
    std::int32_t advance(const BibEngineAdvanceV1* request) {
        Gate gate(*this, true); if (!gate) return gate.status;
        if (auto status = usable()) return status;
        if (!request || request->size < sizeof(*request)) return BIB_ENGINE_INVALID;
        auto copy = *request;
        copy.size = sizeof(copy);
        if (copy.render > 1 || copy.application_instance != backend.application_instance || (copy.render && !start_config.raster_output)) return BIB_ENGINE_INVALID;
        return turn([&] { return backend.advance(backend.context, &copy); });
    }
    std::int32_t current(std::uint64_t instance, BibEngineDocumentV1* output) {
        Gate gate(*this, true); if (!gate) return gate.status;
        if (auto status = usable()) return status;
        if (!output || instance != backend.application_instance) return BIB_ENGINE_INVALID;
        BibEngineDocumentV1 value{};
        auto status = turn([&] { return backend.current_document(backend.context, instance, &value); });
        if (!status && !document_valid(value)) status = BIB_ENGINE_STALE;
        if (!status) *output = value;
        return status;
    }
    template<class Request, class Result> std::int32_t dispatch(const Request* input, BibEngineReplyBufferV1* output, Result* result, bool query) {
        Gate gate(*this, true); if (!gate) return gate.status;
        if (auto status = usable()) return status;
        if (!result || result->size < sizeof(*result)) return BIB_ENGINE_INVALID;
        if (!input || input->size < sizeof(*input) || !output || output->size < sizeof(*output)) {
            Result empty{}; empty.size=sizeof(empty); *result=empty; return BIB_ENGINE_INVALID;
        }
        auto request = *input; const auto buffer = *output;
        request.size = sizeof(request);
        if (overlaps(buffer.bytes, buffer.capacity, result, sizeof(*result))) return BIB_ENGINE_INVALID;
        const std::uint32_t kind = [&] { if constexpr (requires { request.operation; }) return request.operation; else return request.kind; }();
        const auto* operation = find(kind, query);
        Result response{}; response.size = sizeof(response);
        if constexpr (requires { request.request_sequence; }) response.request_sequence = request.request_sequence;
        auto reject = [&](std::int32_t code) { *result = response; return code; };
        if (!operation || !enabled(operation->capability)) return reject(BIB_ENGINE_UNSUPPORTED);
        if (std::memcmp(request.schema_sha256, operation->schema.data(), 32) || !span_valid(request.payload, operation->maximum_input_bytes)
            || request.payload.length > (query ? start_config.limits.maximum_query_bytes : start_config.limits.maximum_command_bytes)
            || buffer.capacity < operation->required_reply_capacity || !buffer.bytes) return reject(BIB_ENGINE_INVALID);
        if constexpr (requires { request.request_sequence; })
            if (!request.request_sequence || request.request_sequence <= last_sequence) return reject(BIB_ENGINE_STALE);
        std::vector<std::uint8_t> payload, scratch;
        try {
            if (request.payload.length) payload.assign(request.payload.data, request.payload.data + request.payload.length);
            scratch.resize(operation->required_reply_capacity);
        } catch (...) { return reject(BIB_ENGINE_LIMIT); }
        request.payload.data = payload.empty() ? nullptr : payload.data();
        BibEngineReplyBufferV1 scratch_buffer{sizeof(scratch_buffer), static_cast<std::uint32_t>(scratch.size()), scratch.data()};
        auto status = turn([&] {
            auto checked = check_document(request.expected); if (checked) return checked;
            if constexpr (requires { request.request_sequence; }) {
                last_sequence = request.request_sequence; response.disposition = 2;
                auto code = backend.command(backend.context, &request, &scratch_buffer, &response);
                if (code || response.size != sizeof(response) || response.bytes_written > scratch.size() || response.handled > 1
                    || response.request_sequence != request.request_sequence) { response.disposition = 2; response.bytes_written = 0; response.handled = 0; return code ? code : BIB_ENGINE_INVALID; }
                response.disposition = 1;
                return BIB_ENGINE_OK;
            } else {
                auto code = backend.query(backend.context, &request, &scratch_buffer, &response);
                if (code || response.size != sizeof(response) || response.bytes_written > scratch.size() || !same(response.document, request.expected)) {
                    response.bytes_written = 0; return code ? code : BIB_ENGINE_INVALID;
                }
                return check_document(request.expected);
            }
        });
        if (status) {
            response.bytes_written = 0;
            if constexpr (requires { response.handled; }) { response.handled = 0; if (last_sequence == request.request_sequence) response.disposition = 2; }
        } else if (response.bytes_written) std::memcpy(buffer.bytes, scratch.data(), response.bytes_written);
        response.size = sizeof(response);
        if constexpr (requires { request.request_sequence; }) response.request_sequence = request.request_sequence;
        *result = response;
        return status;
    }
    std::int32_t deliver(const BibEngineDocumentV1* document, const BibEngineBytesV1* bytes) {
        Gate gate(*this, true); if (!gate) return gate.status;
        if (auto status = usable()) return status;
        if (!enabled(BIB_ENGINE_CAP_SERVICE_QUEUE)) return BIB_ENGINE_UNSUPPORTED;
        if (!document || !bytes || !span_valid(*bytes, start_config.limits.maximum_service_message_bytes)) return BIB_ENGINE_INVALID;
        auto expected = *document; auto copy = *bytes; std::vector<std::uint8_t> owned;
        try { if (copy.length) owned.assign(copy.data, copy.data + copy.length); } catch (...) { return BIB_ENGINE_LIMIT; }
        copy.data = owned.empty() ? nullptr : owned.data();
        return turn([&] { auto status = check_document(expected); return status ? status : backend.deliver_services(backend.context, &expected, &copy); });
    }
    std::uint32_t ack(const BibEngineDocumentV1* document) {
        Gate gate(*this, true); if (!gate || usable() || !enabled(BIB_ENGINE_CAP_SERVICE_QUEUE) || !document) return service_unavailable;
        auto expected = *document; std::uint32_t receipt = service_unavailable;
        const auto status = turn([&] { auto code = check_document(expected); if (!code) receipt = backend.collect_service_ack(backend.context, &expected); return code; });
        return status ? service_unavailable : (receipt <= service_uncertain ? receipt : service_uncertain);
    }
    std::int32_t dispose(std::uint64_t instance, std::uint64_t generation) {
        Gate gate(*this, true); if (!gate) return gate.status;
        if (auto status = usable()) return status;
        if (!enabled(BIB_ENGINE_CAP_SERVICE_QUEUE)) return BIB_ENGINE_UNSUPPORTED;
        if (instance != backend.application_instance || !generation) return BIB_ENGINE_INVALID;
        return turn([&] { return backend.dispose_retired_service_document(backend.context, instance, generation); });
    }
};

Runtime* runtime() { static Runtime* instance = new (std::nothrow) Runtime; return instance; }
int32_t BIB_ENGINE_CALL start(const BibEngineHostV1* h, const BibEngineStartV1* s, BibEngineStartResultV1* r) { auto* p=runtime(); return p ? p->start(h,s,r) : BIB_ENGINE_LIMIT; }
int32_t BIB_ENGINE_CALL advance(const BibEngineAdvanceV1* a) { auto* p=runtime(); return p ? p->advance(a) : BIB_ENGINE_LIMIT; }
int32_t BIB_ENGINE_CALL current(uint64_t a, BibEngineDocumentV1* d) { auto* p=runtime(); return p ? p->current(a,d) : BIB_ENGINE_LIMIT; }
int32_t BIB_ENGINE_CALL command(const BibEngineCommandV1* q, BibEngineReplyBufferV1* b, BibEngineCommandResultV1* r) { auto* p=runtime(); return p ? p->dispatch(q,b,r,false) : BIB_ENGINE_LIMIT; }
int32_t BIB_ENGINE_CALL query(const BibEngineQueryV1* q, BibEngineReplyBufferV1* b, BibEngineQueryResultV1* r) { auto* p=runtime(); return p ? p->dispatch(q,b,r,true) : BIB_ENGINE_LIMIT; }
int32_t BIB_ENGINE_CALL deliver(const BibEngineDocumentV1* d, const BibEngineBytesV1* b) { auto* p=runtime(); return p ? p->deliver(d,b) : BIB_ENGINE_LIMIT; }
uint32_t BIB_ENGINE_CALL ack(const BibEngineDocumentV1* d) { auto* p=runtime(); return p ? p->ack(d) : service_unavailable; }
int32_t BIB_ENGINE_CALL dispose(uint64_t a, uint64_t g) { auto* p=runtime(); return p ? p->dispose(a,g) : BIB_ENGINE_LIMIT; }
} // namespace

std::int32_t bind_engine_private(const EnginePrivateV1& binding) noexcept {
    auto* p = runtime(); if (!p) return BIB_ENGINE_LIMIT;
    try { return p->bind(binding); } catch (...) { return BIB_ENGINE_INVALID; }
}
} // namespace bib::provider_candidate

extern "C" BIB_ENGINE_EXPORT int32_t BIB_ENGINE_CALL bib_engine_get_provider_v1(uint32_t major, uint32_t minor,
    uint32_t capacity, BibEngineProviderV1* output) {
    using namespace bib::provider_candidate;
    (void)minor; // This implementation supplies exactly the v1.0 mandatory prefix.
    if (!output || major != BIB_ENGINE_ABI_MAJOR || capacity < sizeof(BibEngineProviderV1)) return BIB_ENGINE_INVALID;
    auto* p = runtime(); if (!p) return BIB_ENGINE_LIMIT;
    Runtime::Gate gate(*p, false); if (!gate) return gate.status;
    if (!p->bound) return BIB_ENGINE_UNSUPPORTED;
    BibEngineProviderV1 table{}; table.size=sizeof(table); table.abi_major=BIB_ENGINE_ABI_MAJOR;
    table.build=p->backend.build; table.limits=p->backend.limits;
    table.start=start; table.advance=advance; table.current_document=current; table.command=command; table.query=query;
    table.deliver_services=deliver; table.collect_service_ack=ack; table.dispose_retired_service_document=dispose;
    *output=table;
    return BIB_ENGINE_OK;
}
