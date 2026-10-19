// SPDX-License-Identifier: CC0-1.0
// Generic C-table guard tests with an inert private backend. These fixtures
// provide no actual engine, retained SDK, native-port or runtime qualification.
#include "EnginePrivate.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <vector>

using namespace bib::provider_candidate;
namespace {
// Preserve fixture assertion failures across the Guard's expected exception
// boundary, so a terminal return cannot disguise a failed callback assertion.
std::string first_assertion_failure;
#define CHECK(x) do { if (!(x) && first_assertion_failure.empty()) first_assertion_failure = std::string("failed: ") + #x + " line " + std::to_string(__LINE__); if (!first_assertion_failure.empty()) throw std::runtime_error(first_assertion_failure); } while (false)
using Bytes = std::vector<std::uint8_t>;
using Digest = std::array<std::uint8_t, 32>;
constexpr std::uint64_t worker_epoch = 55;
constexpr std::uint64_t maximum_ordinary = UINT64_MAX - UINT64_C(1);
constexpr std::uint32_t reply_capacity = BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY;
BibEngineProviderV1 provider{};

consteval Digest digest(std::string_view text) {
    if (text.size() != 64) throw "Invalid fixture digest";
    Digest value{};
    for (std::size_t i = 0; i < value.size(); ++i) {
        auto digit = [](char c) consteval -> unsigned {
            if (c >= '0' && c <= '9') return static_cast<unsigned>(c - '0');
            if (c >= 'a' && c <= 'f') return static_cast<unsigned>(c - 'a' + 10);
            throw "Invalid fixture hex";
        };
        value[i] = static_cast<std::uint8_t>((digit(text[2*i]) << 4) | digit(text[2*i+1]));
    }
    return value;
}
constexpr auto schema = digest(BIB_ENGINE_DOCUMENT_V2_SCHEMA_SHA256_HEX);
constexpr auto ack_schema = digest(BIB_ENGINE_DOCUMENT_V2_ACK_SCHEMA_SHA256_HEX);
constexpr auto base_header = digest(BIB_ENGINE_DOCUMENT_V2_BASE_HEADER_SHA256_HEX);
constexpr auto extension_header = digest("7b047bae4d0072ef156ea94ba637566d563fea3a95d43c4c6314afc919b1d626");
constexpr auto contract = digest("aba7800e6aab1898f3614f0b1ac53e59b9f622bf1e9d3a413f50d672a3662298");
constexpr auto catalog = digest("6e555d4c3bb71fbc965e1ca49671fab64d744913e18f45b9ba273505e0c6bcf5");
constexpr auto physical_catalog = digest("d244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b");

void put(Bytes& bytes, std::uint64_t value, unsigned width) {
    for (unsigned i = 0; i < width; ++i) bytes.push_back(static_cast<std::uint8_t>(value >> (8*i)));
}
void overwrite(Bytes& bytes, std::size_t offset, std::uint64_t value, unsigned width) {
    CHECK(offset <= bytes.size() && width <= bytes.size() - offset);
    for (unsigned i = 0; i < width; ++i) bytes[offset+i] = static_cast<std::uint8_t>(value >> (8*i));
}
std::uint64_t get(const std::uint8_t* bytes, unsigned width) {
    std::uint64_t value = 0;
    for (unsigned i = 0; i < width; ++i) value |= std::uint64_t(bytes[i]) << (8*i);
    return value;
}
bool same(BibEngineDocumentV1 a, BibEngineDocumentV1 b) {
    return a.application_instance == b.application_instance && a.document_sequence == b.document_sequence
        && a.service_generation == b.service_generation;
}
void identity(Bytes& bytes, BibEngineDocumentV1 document) {
    put(bytes, document.application_instance, 8);
    put(bytes, document.service_generation, 8);
    put(bytes, document.document_sequence, 8);
}
Bytes envelope(unsigned kind, BibEngineDocumentV1 document, std::uint64_t sequence, std::uint64_t nested) {
    Bytes bytes{'N','D','V','2',2,0,static_cast<std::uint8_t>(kind),0};
    identity(bytes, document); put(bytes, sequence, 8); put(bytes, nested, 8); return bytes;
}
Bytes begin_action(BibEngineDocumentV1 document, std::uint64_t sequence, std::uint64_t node = 3) {
    auto bytes = envelope(2, document, sequence, 0);
    put(bytes, 0, 1); // BeginFormControl, exact version followed by node.
    put(bytes, document.application_instance, 8); put(bytes, document.service_generation, 8);
    put(bytes, 9, 8); put(bytes, node, 8); CHECK(bytes.size() == 81); return bytes;
}
Bytes form_action(BibEngineDocumentV1 document, std::uint64_t sequence, unsigned kind) {
    auto bytes = begin_action(document,sequence); bytes[48] = static_cast<std::uint8_t>(kind);
    if (kind == 0 || kind == 4) return bytes;
    put(bytes,77,8); // Exact opaque lease ID.
    if (kind == 1) { put(bytes,0,4); put(bytes,0,4); put(bytes,0,1); put(bytes,1,4); put(bytes,'x',1); }
    if (kind == 2) put(bytes,1,1);
    if (kind == 3) { put(bytes,4,8); put(bytes,1,1); }
    return bytes;
}
Bytes query_request(BibEngineDocumentV1 document, std::uint64_t sequence, std::uint64_t nested = 3) {
    return envelope(1, document, sequence, nested);
}
Bytes rejected_completion(BibEngineDocumentV1 document, std::uint64_t sequence) {
    auto bytes = envelope(5, document, sequence, 0);
    put(bytes, 1, 1); // Rejected inner form outcome; transport consumption is separate.
    put(bytes, 6, 1); // Unsupported, no effects, no paired publication.
    put(bytes, 0, 1); put(bytes, 0, 1); CHECK(bytes.size() == 52); return bytes;
}
Bytes unknown_completion(BibEngineDocumentV1 document, std::uint64_t sequence) {
    auto bytes = envelope(5,document,sequence,0);
    put(bytes,2,1); put(bytes,8,1); put(bytes,1,1); put(bytes,0,1); return bytes;
}
Bytes empty_publication(BibEngineDocumentV1 document, std::uint64_t sequence, std::uint64_t nested) {
    auto bytes = envelope(4, document, sequence, nested);
    identity(bytes, document);
    put(bytes, document.application_instance, 8); put(bytes, document.service_generation, 8); put(bytes, 9, 8);
    put(bytes, 0, 1); put(bytes, 1, 8); put(bytes, 0, 8); // Complete, editor revision, focused node.
    put(bytes, 0, 4); put(bytes, 0, 4); // Editor flags, native degradation.
    put(bytes, 0, 4); put(bytes, 0, 4); put(bytes, 0, 4); put(bytes, 0, 1);
    CHECK(bytes.size() == 134); return bytes;
}

struct Counts {
    int enters{}, leaves{}, currents{}, effects{}, queries{}, request_validations{}, reply_validations{}, retirements{};
    bool operator==(const Counts&) const = default;
};
void check_counts(const Counts& actual, const Counts& expected) {
    if (actual == expected) return;
    auto show = [](const Counts& counts) {
        return "enters=" + std::to_string(counts.enters) + " leaves=" + std::to_string(counts.leaves)
            + " currents=" + std::to_string(counts.currents) + " effects=" + std::to_string(counts.effects)
            + " queries=" + std::to_string(counts.queries) + " request_validations=" + std::to_string(counts.request_validations)
            + " reply_validations=" + std::to_string(counts.reply_validations) + " retirements=" + std::to_string(counts.retirements);
    };
    throw std::runtime_error("counter mismatch: actual {" + show(actual) + "}; expected {" + show(expected) + "}");
}
struct Fake {
    Counts counts;
    std::array<int,3> physical_requests{}, physical_replies{}, physical_effects{};
    int starts{}, installs{};
    int request_status{}, reply_status{}, command_status{}, query_status{}, retire_status{};
    std::uint32_t enter_status{}, physical_reply_bytes{};
    bool throw_command{}, throw_retire{}, throw_leave{}, throw_request{}, reject_retired_identity{}, navigate_enter{}, reject_request_on_enter{}, reenter{}, malformed_reply{}, navigate_query{}, inner_unknown{}, permit_nonzero_physical_reply{};
    std::uint64_t query_revision{9};
    int nested_enter{99}, nested_request{99}, nested_command{99}, nested_leave{99}, nested_retire{99}, threaded{99};
    BibEngineDocumentV1 document{44,11,7};
    std::uint8_t* mutate{};
    std::uint8_t captured_node{};
    Bytes retained_action;
    std::uint64_t retired_sequence{};

    static int nested() { BibEngineDocumentV1 d{}; return provider.current_document(44, &d); }
    static void BIB_ENGINE_CALL wake(void*) {}
    static void BIB_ENGINE_CALL timer(void*, double, std::uint32_t) {}
    static void BIB_ENGINE_CALL damage(void*, const BibEngineDamageV1*) {}
    static void BIB_ENGINE_CALL persistence(void*, const BibEngineBytesV1*) {}
    static std::uint32_t BIB_ENGINE_CALL enter(void* context) {
        auto& f = *static_cast<Fake*>(context); ++f.counts.enters;
        if (f.navigate_enter) ++f.document.document_sequence;
        if (f.reject_request_on_enter) f.request_status = BIB_ENGINE_STALE;
        if (f.mutate) *f.mutate = 91;
        if (f.reenter) f.nested_enter = nested();
        return f.enter_status;
    }
    static void BIB_ENGINE_CALL leave(void* context) {
        auto& f = *static_cast<Fake*>(context); ++f.counts.leaves;
        if (f.reenter) f.nested_leave = nested();
        if (f.throw_leave) throw std::runtime_error("uncertain fake host leave");
    }
    static std::uint64_t BIB_ENGINE_CALL begin_service(void*, const BibEngineDocumentV1*) { return 7; }
    static void BIB_ENGINE_CALL close_service(void*, std::uint64_t) {}
    static std::uint32_t BIB_ENGINE_CALL submit(void*, std::uint64_t, const BibEngineBytesV1*, std::uint32_t) { return 0; }
    static std::uint32_t BIB_ENGINE_CALL cancel(void*, std::uint64_t, std::uint64_t) { return 0; }
    static std::uint32_t BIB_ENGINE_CALL stage(void*, std::uint64_t, std::uint64_t) { return 0; }
    static std::int32_t BIB_ENGINE_CALL resource(void*, const BibEngineDocumentV1*, BibEngineResourceEpochV1*) { return BIB_ENGINE_UNSUPPORTED; }
    static void BIB_ENGINE_CALL retire_resource(void*, std::uint64_t) {}
    static std::int32_t preflight(void*, const BibEngineStartV1*) { return 0; }
    static std::int32_t install(void* context, const BibEngineHostV1*, const BibEngineStartV1*, std::uint64_t) {
        ++static_cast<Fake*>(context)->installs; return 0;
    }
    static std::int32_t start(void* context, const BibEngineHostV1*, const BibEngineStartV1*, std::uint64_t instance) {
        auto& f = *static_cast<Fake*>(context); CHECK(instance == f.document.application_instance); ++f.starts; return 0;
    }
    static std::int32_t advance(void*, const BibEngineAdvanceV1*) { return 0; }
    static std::int32_t current(void* context, std::uint64_t, BibEngineDocumentV1* document) {
        auto& f = *static_cast<Fake*>(context); ++f.counts.currents; *document = f.document; return 0;
    }
    static std::int32_t deliver(void*, const BibEngineDocumentV1*, const BibEngineBytesV1*) { return 0; }
    static std::uint32_t collect(void*, const BibEngineDocumentV1*) { return 0; }
    static std::int32_t dispose(void*, std::uint64_t, std::uint64_t) { return 0; }
    static std::int32_t validate_request(void* context, std::uint64_t worker, const BibEngineDocumentV1* expected,
            std::uint32_t is_query, std::uint32_t operation, std::uint64_t sequence, const BibEngineBytesV1* payload) {
        auto& f = *static_cast<Fake*>(context); ++f.counts.request_validations;
        CHECK(worker == worker_epoch && expected && payload && !payload->reserved && sequence);
        CHECK((!is_query && operation == BIB_ENGINE_COMMAND_FORM_ACTION_V2)
            || (is_query == 1 && operation == BIB_ENGINE_QUERY_DOCUMENT_FORMS_V2));
        CHECK(payload->length >= 48 && get(payload->data + 32, 8) == sequence);
        CHECK(get(payload->data + 8, 8) == expected->application_instance);
        CHECK(get(payload->data + 16, 8) == expected->service_generation);
        CHECK(get(payload->data + 24, 8) == expected->document_sequence);
        if (f.throw_request) throw std::runtime_error("uncertain fake request admission");
        if (f.reject_retired_identity && !same(*expected,f.document)) return BIB_ENGINE_STALE;
        if (f.reenter) f.nested_request = nested();
        return f.request_status;
    }
    static std::int32_t validate_reply(void* context, std::uint64_t worker, const BibEngineDocumentV1* expected,
            std::uint32_t is_query, std::uint32_t operation, std::uint64_t sequence, const BibEngineBytesV1* payload, const BibEngineBytesV1* reply) {
        auto& f = *static_cast<Fake*>(context); ++f.counts.reply_validations;
        CHECK(worker == worker_epoch && expected && payload && reply && !reply->reserved);
        CHECK((!is_query && operation == BIB_ENGINE_COMMAND_FORM_ACTION_V2)
            || (is_query == 1 && operation == BIB_ENGINE_QUERY_DOCUMENT_FORMS_V2));
        // The fake produces only these two complete canonical, engine-free values.
        const auto canonical = operation == BIB_ENGINE_COMMAND_FORM_ACTION_V2 ?
            (f.inner_unknown ? unknown_completion(*expected,sequence) : rejected_completion(*expected, sequence))
            : empty_publication(*expected, sequence, get(payload->data + 40, 8));
        if (reply->length != canonical.size() || !std::equal(canonical.begin(), canonical.end(), reply->data)) return BIB_ENGINE_INVALID;
        return f.reply_status;
    }
    static std::int32_t command(void* context, const BibEngineCommandV1* request, BibEngineReplyBufferV1* buffer,
            BibEngineCommandResultV1* result) {
        auto& f = *static_cast<Fake*>(context); ++f.counts.effects;
        CHECK(request->operation == BIB_ENGINE_COMMAND_FORM_ACTION_V2);
        CHECK(request->payload.length >= 81 && buffer->capacity >= reply_capacity);
        f.captured_node = request->payload.data[73];
        f.retained_action.assign(request->payload.data, request->payload.data + request->payload.length);
        if (f.reenter) {
            f.nested_command = nested();
            std::thread wrong([&] { f.threaded = nested(); }); wrong.join();
        }
        if (f.throw_command) throw std::runtime_error("uncertain fake action");
        auto bytes = f.inner_unknown ? unknown_completion(request->expected,request->request_sequence)
            : rejected_completion(request->expected, request->request_sequence);
        if (f.malformed_reply) bytes[6] = 4;
        std::copy(bytes.begin(), bytes.end(), buffer->bytes);
        result->bytes_written = static_cast<std::uint32_t>(bytes.size()); result->handled = 0;
        return f.command_status;
    }
    static std::int32_t query(void* context, const BibEngineQueryV1* request, BibEngineReplyBufferV1* buffer,
            BibEngineQueryResultV1* result) {
        auto& f = *static_cast<Fake*>(context); ++f.counts.queries;
        CHECK(request->kind == BIB_ENGINE_QUERY_DOCUMENT_FORMS_V2 && request->payload.length == 48);
        auto bytes = empty_publication(request->expected, get(request->payload.data + 32, 8), get(request->payload.data + 40, 8));
        if (f.malformed_reply) bytes[6] = 5;
        std::copy(bytes.begin(), bytes.end(), buffer->bytes);
        result->bytes_written = static_cast<std::uint32_t>(bytes.size()); result->document = f.document; result->semantic_revision = f.query_revision;
        if (f.navigate_query) ++f.document.document_sequence;
        return f.query_status;
    }
    static std::int32_t retire_action(void* context, std::uint64_t worker, const BibEngineCommandV1* action) {
        auto& f = *static_cast<Fake*>(context); ++f.counts.retirements;
        CHECK(worker == worker_epoch && action && action->operation == BIB_ENGINE_COMMAND_FORM_ACTION_V2);
        CHECK(action->payload.length == f.retained_action.size());
        CHECK(std::equal(f.retained_action.begin(), f.retained_action.end(), action->payload.data));
        CHECK(get(action->payload.data+8,8) == action->expected.application_instance);
        CHECK(get(action->payload.data+16,8) == action->expected.service_generation);
        CHECK(get(action->payload.data+24,8) == action->expected.document_sequence);
        CHECK(std::equal(schema.begin(),schema.end(),action->schema_sha256));
        f.retired_sequence = action->request_sequence;
        if (f.reenter) f.nested_retire = nested();
        if (f.throw_retire) throw std::runtime_error("uncertain fake metadata retirement");
        return f.retire_status;
    }
};

// This inert physical lane verifies the private callback domain, exact catalog
// schemas and owned transport values. It is not a physical-input implementation.
struct PhysicalLane {
    inline static constexpr std::array<Operation,3> operations{{
        {1,160,16,16,digest("86b7baad1c95bfb8de3e6b7a9a7c433b528278bbcf84199ca0b2b4ee6134dbc9")},
        {3,32,16,64,digest("eef60cda2aa7b791641b0e5082d551ec37c10b8d92ca4cc71f13be0af45321d9")},
        {5,80,16,128,digest("6a15d0e2f814564ce263824dd782335bb327b886e982aefec32476a29b0fd4a3")},
    }};
    static std::size_t slot(std::uint32_t operation) {
        for (std::size_t i = 0; i < operations.size(); ++i) if (operations[i].kind == operation) return i;
        throw std::runtime_error("unexpected physical operation");
    }
    static void shape(const BibEngineBytesV1* payload, std::uint32_t operation) {
        CHECK(payload && !payload->reserved && payload->length == operations[slot(operation)].maximum_input_bytes);
        CHECK(payload->data && payload->data[0] == operation);
        CHECK(std::all_of(payload->data+1,payload->data+payload->length,[](auto byte) { return byte == 0; }));
    }
    static std::int32_t validate_request(void* context, std::uint64_t worker, const BibEngineDocumentV1* expected,
            std::uint32_t is_query, std::uint32_t operation, std::uint64_t sequence, const BibEngineBytesV1* payload) {
        if (is_query || operation == BIB_ENGINE_COMMAND_FORM_ACTION_V2)
            return Fake::validate_request(context,worker,expected,is_query,operation,sequence,payload);
        auto& f = *static_cast<Fake*>(context); ++f.counts.request_validations; ++f.physical_requests[slot(operation)];
        CHECK(is_query == 0 && worker == worker_epoch && sequence && expected && same(*expected,f.document));
        shape(payload,operation); return 0;
    }
    static std::int32_t validate_reply(void* context, std::uint64_t worker, const BibEngineDocumentV1* expected,
            std::uint32_t is_query, std::uint32_t operation, std::uint64_t sequence, const BibEngineBytesV1* payload,
            const BibEngineBytesV1* bytes) {
        if (is_query || operation == BIB_ENGINE_COMMAND_FORM_ACTION_V2)
            return Fake::validate_reply(context,worker,expected,is_query,operation,sequence,payload,bytes);
        auto& f = *static_cast<Fake*>(context); ++f.counts.reply_validations; ++f.physical_replies[slot(operation)];
        CHECK(is_query == 0 && worker == worker_epoch && expected && same(*expected,f.document));
        shape(payload,operation);
        CHECK(bytes && !bytes->reserved && bytes->length <= 16);
        // The negative fixture deliberately admits bounded bytes here, proving
        // the outer fixed-result guard owns the zero-payload physical rule.
        if (!f.permit_nonzero_physical_reply) CHECK(bytes->length == 0);
        return 0;
    }
    static std::int32_t command(void* context, const BibEngineCommandV1* request, BibEngineReplyBufferV1* buffer,
            BibEngineCommandResultV1* result) {
        if (request->operation == BIB_ENGINE_COMMAND_FORM_ACTION_V2) return Fake::command(context,request,buffer,result);
        auto& f = *static_cast<Fake*>(context); const auto index = slot(request->operation);
        ++f.counts.effects; ++f.physical_effects[index]; shape(&request->payload,request->operation);
        CHECK(std::equal(operations[index].schema.begin(),operations[index].schema.end(),request->schema_sha256));
        CHECK(buffer->capacity == 16 && f.physical_reply_bytes <= 16);
        std::fill_n(buffer->bytes,f.physical_reply_bytes,0x7b);
        result->bytes_written = f.physical_reply_bytes; result->handled = 0; return f.command_status;
    }
};

struct Fixture {
    Fake fake;
    std::array<Operation, 2> commands{{
        {BIB_ENGINE_COMMAND_FORM_ACTION_V2, BIB_ENGINE_DOCUMENT_V2_MAX_ACTION_BYTES, reply_capacity, BIB_ENGINE_CAP_FORM_ACTION_V2, schema},
        {BIB_ENGINE_COMMAND_ACK_FORM_ACTION_V2, 8, 16, BIB_ENGINE_CAP_FORM_ACTION_V2, ack_schema},
    }};
    Operation query{BIB_ENGINE_QUERY_DOCUMENT_FORMS_V2, 48, reply_capacity, BIB_ENGINE_CAP_SEMANTIC_SNAPSHOT_V2, schema};
    EnginePrivateV1 backend{};
    EngineDocumentPrivateV1 document_backend{};
    BibEngineHostV1 host{};
    BibEngineStartV1 config{};
    std::string url = "app://" + std::string(64, 'a') + "/web/index.html";
    Fixture() {
        backend.size = sizeof(backend); backend.version = private_interface_version; backend.application_instance = 44;
        backend.build.size = sizeof(backend.build); backend.build.layout_revision = BIB_ENGINE_LAYOUT_V1;
#if defined(__EMSCRIPTEN__)
        backend.build.target_system = BIB_ENGINE_TARGET_BROWSER_WASM; backend.build.target_processor = BIB_ENGINE_CPU_WASM32; backend.build.pointer_bits = 32;
#elif defined(_WIN32)
        backend.build.target_system = BIB_ENGINE_TARGET_WINDOWS; backend.build.target_processor = BIB_ENGINE_CPU_X86_64; backend.build.pointer_bits = 64;
#elif defined(__aarch64__)
        backend.build.target_system = BIB_ENGINE_TARGET_LINUX; backend.build.target_processor = BIB_ENGINE_CPU_AARCH64; backend.build.pointer_bits = 64;
#else
        backend.build.target_system = BIB_ENGINE_TARGET_LINUX; backend.build.target_processor = BIB_ENGINE_CPU_X86_64; backend.build.pointer_bits = 64;
#endif
        backend.build.lifetime = BIB_ENGINE_LIFETIME_PROCESS; backend.build.maximum_starts = 1;
        backend.build.fixed_viewport_width = 800; backend.build.fixed_viewport_height = 600; backend.build.capabilities = 1795;
        std::copy(contract.begin(), contract.end(), backend.build.contract_header_sha256);
        backend.build.build_identity_sha256[0] = 1; backend.build.source_recipe_sha256[0] = 2;
        backend.limits = {sizeof(BibEngineLimitsV1),6246,48,reply_capacity,1048576,4,8,0,1048576,4194304};
        backend.context = &fake; backend.commands = commands.data(); backend.command_count = commands.size();
        backend.queries = &query; backend.query_count = 1;
        backend.preflight = Fake::preflight; backend.start = Fake::start; backend.advance = Fake::advance;
        backend.current_document = Fake::current; backend.command = Fake::command; backend.query = Fake::query;
        backend.deliver_services = Fake::deliver; backend.collect_service_ack = Fake::collect;
        backend.dispose_retired_service_document = Fake::dispose; backend.install_resources = Fake::install;
        document_backend.size = sizeof(document_backend); document_backend.version = document_private_interface_version;
        document_backend.profile = document_pixel_profile; document_backend.worker_epoch = worker_epoch;
        document_backend.base_header_sha256 = base_header; document_backend.extension_header_sha256 = extension_header;
        document_backend.contract_sha256 = contract; document_backend.catalog_sha256 = catalog;
        document_backend.validate_request = Fake::validate_request; document_backend.validate_reply = Fake::validate_reply;
        document_backend.retire_action_metadata = Fake::retire_action;
        host.size = sizeof(host); host.abi_major = 1; host.context = &fake; host.wake = Fake::wake; host.replace_timer_ms = Fake::timer;
        host.damage = Fake::damage; host.persistence = Fake::persistence; host.enter_engine = Fake::enter; host.leave_engine = Fake::leave;
        host.begin_service_document = Fake::begin_service; host.close_service_document = Fake::close_service;
        host.submit_service = Fake::submit; host.cancel_service = Fake::cancel; host.stage_service_ack = Fake::stage;
        host.begin_resource_epoch = Fake::resource; host.retire_resource_epoch = Fake::retire_resource;
        config.size = sizeof(config); config.required_capabilities = backend.build.capabilities; config.limits = backend.limits;
        config.entry_url = {reinterpret_cast<const std::uint8_t*>(url.data()), static_cast<std::uint32_t>(url.size()), 0};
        std::fill(std::begin(config.application_package_sha256), std::end(config.application_package_sha256), 0xaa);
    }
    void bind() {
        CHECK(bind_engine_document_private(backend, document_backend) == 0);
        CHECK(bib_engine_get_provider_v1(1, 1, sizeof(provider), &provider) == 0);
        CHECK(provider.abi_minor == 1);
    }
    void start() {
        BibEngineStartResultV1 result{sizeof(result),99,99};
        CHECK(provider.start(&host, &config, &result) == 0);
        CHECK(result.phase == BIB_ENGINE_START_READY && result.application_instance == backend.application_instance);
        CHECK(fake.starts == 1 && fake.installs == 1);
    }
};

struct Command {
    Bytes payload;
    Bytes output = Bytes(reply_capacity, 0xa5);
    BibEngineCommandV1 request{};
    BibEngineReplyBufferV1 buffer{};
    BibEngineCommandResultV1 result{sizeof(result),99,99,99,99};
    explicit Command(BibEngineDocumentV1 document, std::uint64_t sequence = 1) : payload(begin_action(document, sequence)) {
        request.size = sizeof(request); request.operation = BIB_ENGINE_COMMAND_FORM_ACTION_V2;
        request.expected = document; request.request_sequence = sequence;
        std::copy(schema.begin(), schema.end(), request.schema_sha256);
        buffer = {sizeof(buffer),reply_capacity,output.data()};
    }
    void ack(std::uint64_t original) {
        request.operation = BIB_ENGINE_COMMAND_ACK_FORM_ACTION_V2;
        std::copy(ack_schema.begin(), ack_schema.end(), request.schema_sha256);
        payload.clear(); put(payload, original, 8); buffer.capacity = 16;
    }
    int run() {
        request.payload = {payload.data(),static_cast<std::uint32_t>(payload.size()),request.payload.reserved};
        result = {sizeof(result),99,99,99,99};
        return provider.command(&request, &buffer, &result);
    }
    Bytes bytes() const {
        CHECK(result.bytes_written <= output.size());
        return Bytes(output.begin(),output.begin()+result.bytes_written);
    }
    void consumed(bool unknown = false) const {
        CHECK(result.disposition == 1 && result.request_sequence == request.request_sequence && result.handled == 0);
        if (request.operation == BIB_ENGINE_COMMAND_FORM_ACTION_V2) {
            const auto canonical = unknown ? unknown_completion(request.expected,request.request_sequence)
                : rejected_completion(request.expected,request.request_sequence);
            CHECK(result.bytes_written == canonical.size() && std::equal(canonical.begin(),canonical.end(),output.begin()));
        }
    }
    void rejected() const { CHECK(result.disposition == 0 && result.bytes_written == 0 && result.handled == 0); }
    void receipt(unsigned code, std::uint64_t original) const {
        consumed(); CHECK(result.bytes_written == 16);
        CHECK(get(output.data(),8) == original && get(output.data()+8,4) == code && get(output.data()+12,4) == 0);
    }
};
struct Query {
    Bytes payload;
    Bytes output = Bytes(reply_capacity, 0xa5);
    BibEngineQueryV1 request{};
    BibEngineReplyBufferV1 buffer{};
    BibEngineQueryResultV1 result{sizeof(result),99,{},99};
    explicit Query(BibEngineDocumentV1 document, std::uint64_t sequence = 1) : payload(query_request(document,sequence)) {
        request.size = sizeof(request); request.kind = BIB_ENGINE_QUERY_DOCUMENT_FORMS_V2; request.expected = document;
        std::copy(schema.begin(), schema.end(), request.schema_sha256); buffer = {sizeof(buffer),reply_capacity,output.data()};
    }
    int run() {
        request.payload = {payload.data(),static_cast<std::uint32_t>(payload.size()),request.payload.reserved};
        result = {sizeof(result),99,{},99}; return provider.query(&request,&buffer,&result);
    }
    void completed() const {
        const auto canonical = empty_publication(request.expected,get(payload.data()+32,8),get(payload.data()+40,8));
        CHECK(result.bytes_written == canonical.size() && std::equal(canonical.begin(),canonical.end(),output.begin()));
        CHECK(result.semantic_revision == 9 && same(result.document,request.expected));
    }
};

void bind_validation(Fixture& f) {
    const auto good = f.document_backend;
    auto reject = [&] { CHECK(bind_engine_document_private(f.backend, f.document_backend) == BIB_ENGINE_INVALID); };
    f.document_backend.size = 0; reject(); f.document_backend = good;
    ++f.document_backend.version; reject(); f.document_backend = good;
    f.document_backend.profile = 0; reject(); f.document_backend = good;
    f.document_backend.reserved = 1; reject(); f.document_backend = good;
    f.document_backend.worker_epoch = 0; reject(); f.document_backend = good;
    f.document_backend.base_header_sha256[0] ^= 1; reject(); f.document_backend = good;
    f.document_backend.extension_header_sha256[0] ^= 1; reject(); f.document_backend = good;
    f.document_backend.contract_sha256[0] ^= 1; reject(); f.document_backend = good;
    f.document_backend.catalog_sha256[0] ^= 1; reject(); f.document_backend = good;
    f.document_backend.physical_catalog_sha256[0] = 1; reject(); f.document_backend = good;
    f.document_backend.validate_request = nullptr; reject(); f.document_backend = good;
    f.document_backend.validate_reply = nullptr; reject(); f.document_backend = good;
    f.document_backend.retire_action_metadata = nullptr; reject(); f.document_backend = good;
    const auto build = f.backend.build;
    f.backend.build.capabilities = 259; reject(); f.backend.build = build;
    f.backend.build.capabilities |= UINT64_C(1)<<11; reject(); f.backend.build = build;
    std::copy(base_header.begin(), base_header.end(), f.backend.build.contract_header_sha256); reject(); f.backend.build = build;
    f.backend.build.fixed_viewport_width = 799; reject(); f.backend.build = build;
    f.commands[0].maximum_input_bytes--; reject(); f.commands[0].maximum_input_bytes++;
    f.commands[0].required_reply_capacity--; reject(); f.commands[0].required_reply_capacity++;
    f.commands[0].schema[0] ^= 1; reject(); f.commands[0].schema[0] ^= 1;
    f.commands[1].maximum_input_bytes = 9; reject(); f.commands[1].maximum_input_bytes = 8;
    f.commands[1].required_reply_capacity = 15; reject(); f.commands[1].required_reply_capacity = 16;
    f.query.maximum_input_bytes = 49; reject(); f.query.maximum_input_bytes = 48;
    f.query.schema[0] ^= 1; reject(); f.query.schema[0] ^= 1;
    f.backend.command_count = 1; reject(); f.backend.command_count = 2;
    f.backend.query_count = 0; reject(); f.backend.query_count = 1;
    f.backend.deliver_services = nullptr; reject(); f.backend.deliver_services = Fake::deliver;
    f.backend.install_resources = nullptr; reject(); f.backend.install_resources = Fake::install;
    CHECK(bind_engine_private(f.backend) == BIB_ENGINE_INVALID);
    CHECK(f.fake.counts == Counts{} && f.fake.starts == 0);
    f.bind(); CHECK(bind_engine_document_private(f.backend, good) == BIB_ENGINE_CLOSED);
}

void malformed_command(Fixture& f) {
    Command c(f.fake.document); const auto good = c.payload; const auto counts = f.fake.counts;
    auto reject = [&] { CHECK(c.run() == BIB_ENGINE_INVALID); c.rejected(); CHECK(f.fake.counts == counts); c.payload = good; };
    c.payload[0] ^= 1; reject(); c.payload[4] = 3; reject(); c.payload[6] = 1; reject(); c.payload[7] = 1; reject();
    overwrite(c.payload,8,45,8); reject(); overwrite(c.payload,16,8,8); reject(); overwrite(c.payload,24,12,8); reject();
    overwrite(c.payload,32,2,8); reject(); overwrite(c.payload,40,1,8); reject(); c.payload[48] = 6; reject();
    overwrite(c.payload,49,45,8); reject(); overwrite(c.payload,57,8,8); reject(); overwrite(c.payload,65,0,8); reject();
    overwrite(c.payload,73,0,8); reject(); c.payload.pop_back(); reject(); c.payload.push_back(0); reject();
    c.request.request_sequence = 100; overwrite(c.payload,32,100,8); c.payload[7] = 1; reject();
    c.request.request_sequence = 1; CHECK(c.run() == 0); c.consumed(); CHECK(f.fake.counts.effects == 1);
}
void malformed_query(Fixture& f) {
    Query q(f.fake.document); const auto good = q.payload; const auto counts = f.fake.counts;
    auto reject = [&] { CHECK(q.run() == BIB_ENGINE_INVALID); CHECK(q.result.bytes_written == 0 && f.fake.counts == counts); q.payload = good; };
    q.payload[6] = 2; reject(); q.payload[7] = 1; reject(); overwrite(q.payload,8,0,8); reject();
    overwrite(q.payload,16,8,8); reject(); overwrite(q.payload,24,12,8); reject(); overwrite(q.payload,40,0,8); reject();
    q.payload.pop_back(); reject(); q.payload.push_back(0); reject();
    CHECK(q.run() == 0 && q.result.bytes_written == 134 && same(q.result.document,f.fake.document));
    q.completed();
    CHECK(q.run() == BIB_ENGINE_STALE && f.fake.counts.queries == 1);
}
void malformed_action_shapes(Fixture& f) {
    Command c(f.fake.document); const auto counts = f.fake.counts;
    auto reject = [&] { CHECK(c.run() == BIB_ENGINE_INVALID); c.rejected(); CHECK(f.fake.counts == counts); };
    c.payload = form_action(f.fake.document,1,5); overwrite(c.payload,81,0,8); reject();
    c.payload = form_action(f.fake.document,1,2); c.payload[89] = 2; reject();
    c.payload = form_action(f.fake.document,1,3); c.payload[97] = 2; reject();
    c.payload = form_action(f.fake.document,1,3); overwrite(c.payload,89,0,8); reject();
    c.payload = form_action(f.fake.document,1,1); overwrite(c.payload,89,1,4); reject();
    c.payload = form_action(f.fake.document,1,1); overwrite(c.payload,93,2049,4); reject();
    c.payload = form_action(f.fake.document,1,1); c.payload[97] = 3; reject();
    c.payload = form_action(f.fake.document,1,1); overwrite(c.payload,98,2,4); reject();
    c.payload = form_action(f.fake.document,1,1); c.payload[102] = 0; reject();
    c.payload = form_action(f.fake.document,1,1); c.payload[102] = 0xc0; reject();
    c.payload = form_action(f.fake.document,1,1); c.payload.resize(102);
    c.payload.insert(c.payload.end(),{0xed,0xa0,0x80}); overwrite(c.payload,98,3,4); reject();
    c.payload = form_action(f.fake.document,1,1); c.payload.resize(102);
    c.payload.insert(c.payload.end(),2049,'x'); overwrite(c.payload,98,2049,4); reject();
    // Each canonical form shape can enter once; retirement releases the one slot.
    for (unsigned kind = 0; kind <= 5; ++kind) {
        const auto sequence = std::uint64_t(kind)*2 + 1;
        Command action(f.fake.document,sequence); action.payload = form_action(f.fake.document,sequence,kind);
        CHECK(action.run() == 0); action.consumed();
        Command ack(f.fake.document,sequence+1); ack.ack(sequence); CHECK(ack.run() == 0); ack.receipt(0,sequence);
    }
    CHECK(f.fake.counts.effects == 6 && f.fake.counts.retirements == 6);
}

void run(const std::string& name) {
    Fixture f;
    if (name == "bind-validation") { bind_validation(f); return; }
    if (name == "full-width") {
        // Native wire authority is full-width. Consumer representability is a
        // separate admission decision, never a JavaScript-number truncation here.
        f.fake.document = {UINT64_MAX-7,UINT64_MAX-5,UINT64_MAX-3};
        f.backend.application_instance = f.fake.document.application_instance;
        f.bind(); f.start();
        Query query(f.fake.document,UINT64_MAX-10); overwrite(query.payload,40,UINT64_MAX-20,8);
        CHECK(query.run() == 0 && same(query.result.document,f.fake.document));
        query.completed();
        Command action(f.fake.document,UINT64_MAX-9); action.payload = form_action(f.fake.document,UINT64_MAX-9,3);
        overwrite(action.payload,65,UINT64_MAX-25,8); overwrite(action.payload,73,UINT64_MAX-24,8);
        overwrite(action.payload,81,UINT64_MAX-23,8); overwrite(action.payload,89,UINT64_MAX-22,8);
        CHECK(action.run() == 0); action.consumed(); const auto bytes = action.bytes(); const auto counts = f.fake.counts;
        CHECK(action.run() == 0 && action.bytes() == bytes && f.fake.counts == counts);
        Command ack(f.fake.document,UINT64_MAX-8); ack.ack(UINT64_MAX-9); CHECK(ack.run() == 0); ack.receipt(0,UINT64_MAX-9); return;
    }
    if (name == "physical-profile") {
        std::array<Operation,5> commands{{f.commands[0],f.commands[1],
            {1,160,16,16,digest("86b7baad1c95bfb8de3e6b7a9a7c433b528278bbcf84199ca0b2b4ee6134dbc9")},
            {3,32,16,64,digest("eef60cda2aa7b791641b0e5082d551ec37c10b8d92ca4cc71f13be0af45321d9")},
            {5,80,16,128,digest("6a15d0e2f814564ce263824dd782335bb327b886e982aefec32476a29b0fd4a3")},
        }};
        f.backend.commands = commands.data(); f.backend.command_count = commands.size();
        f.backend.build.capabilities = 2003; f.config.required_capabilities = 2003;
        auto reject = [&] { CHECK(bind_engine_document_private(f.backend,f.document_backend) == BIB_ENGINE_INVALID); };
        reject(); // A pixel descriptor cannot silently acquire physical capabilities.
        f.document_backend.profile = document_physical_profile; reject(); // Missing physical pin.
        f.document_backend.physical_catalog_sha256 = physical_catalog;
        f.document_backend.physical_catalog_sha256[0] ^= 1; reject(); f.document_backend.physical_catalog_sha256 = physical_catalog;
        commands[2].maximum_input_bytes = 159; reject(); commands[2].maximum_input_bytes = 160;
        commands[3].schema[0] ^= 1; reject(); commands[3].schema[0] ^= 1;
        f.bind(); CHECK(provider.build.capabilities == 2003);
        BibEngineProviderV1 untouched{}; untouched.size = 17;
        CHECK(bib_engine_get_provider_v1(1,0,sizeof(untouched),&untouched) == BIB_ENGINE_UNSUPPORTED && untouched.size == 17);
        f.start(); Query query(f.fake.document,1); CHECK(query.run() == 0 && query.result.bytes_written == 134); query.completed();
        Command action(f.fake.document,2); CHECK(action.run() == 0); action.consumed();
        const auto counts = f.fake.counts; Command ack(f.fake.document,3); ack.ack(2); CHECK(ack.run() == 0); ack.receipt(0,2);
        auto expected = counts; ++expected.retirements; CHECK(f.fake.counts == expected); return;
    }
    if (name == "physical-command-lane" || name == "physical-command-unknown" || name == "physical-command-nonzero-reply") {
        std::array<Operation,5> commands{{f.commands[0],f.commands[1],PhysicalLane::operations[0],
            PhysicalLane::operations[1],PhysicalLane::operations[2]}};
        f.backend.commands = commands.data(); f.backend.command_count = commands.size(); f.backend.command = PhysicalLane::command;
        f.backend.build.capabilities = 2003; f.config.required_capabilities = 2003;
        f.document_backend.profile = document_physical_profile; f.document_backend.physical_catalog_sha256 = physical_catalog;
        f.document_backend.validate_request = PhysicalLane::validate_request; f.document_backend.validate_reply = PhysicalLane::validate_reply;
        f.bind(); f.start();
        auto physical = [&](Command& command, std::size_t index) {
            const auto& operation = PhysicalLane::operations[index]; command.request.operation = operation.kind;
            std::copy(operation.schema.begin(),operation.schema.end(),command.request.schema_sha256);
            command.payload.assign(operation.maximum_input_bytes,0); command.payload[0] = static_cast<std::uint8_t>(operation.kind);
            command.buffer.capacity = 16;
        };
        if (name == "physical-command-unknown" || name == "physical-command-nonzero-reply") {
            Command command(f.fake.document,1); physical(command,1);
            const bool nonzero_reply = name == "physical-command-nonzero-reply";
            f.fake.command_status = nonzero_reply ? BIB_ENGINE_OK : BIB_ENGINE_INVALID;
            f.fake.physical_reply_bytes = nonzero_reply ? 1u : 0u;
            f.fake.permit_nonzero_physical_reply = nonzero_reply;
            CHECK(command.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED);
            CHECK(command.result.disposition == 2 && command.result.bytes_written == 0 && command.result.handled == 0
                && command.result.request_sequence == 1 && command.output.front() == 0xa5);
            const std::array<int,3> physical_entries{0,1,0}, no_replies{};
            CHECK(f.fake.physical_requests == physical_entries && f.fake.physical_effects == physical_entries
                && f.fake.physical_replies == no_replies);
            CHECK(f.fake.counts.effects == 1 && f.fake.counts.queries == 0 && f.fake.counts.retirements == 0);
            const auto counts = f.fake.counts; f.fake.command_status = 0;
            CHECK(command.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED);
            CHECK(command.result.disposition == 99 && command.result.bytes_written == 99 && command.result.request_sequence == 99);
            Query query(f.fake.document,2); CHECK(query.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED);
            CHECK(query.result.bytes_written == 99 && query.result.semantic_revision == 99 && query.output.front() == 0xa5);
            Command form(f.fake.document,3); CHECK(form.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED);
            CHECK(form.result.disposition == 99 && form.result.bytes_written == 99 && form.output.front() == 0xa5);
            Command ack(f.fake.document,4); ack.ack(3); CHECK(ack.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED);
            CHECK(ack.result.disposition == 99 && ack.result.bytes_written == 99 && ack.output.front() == 0xa5);
            BibEngineProviderV1 untouched{}; untouched.size = 17;
            CHECK(bib_engine_get_provider_v1(1,1,sizeof(untouched),&untouched) == BIB_ENGINE_PROCESS_EXIT_REQUIRED && untouched.size == 17);
            BibEngineDocumentV1 document{91,92,93}; CHECK(provider.current_document(44,&document) == BIB_ENGINE_PROCESS_EXIT_REQUIRED);
            CHECK(same(document,{91,92,93}) && f.fake.counts == counts);
            CHECK(f.fake.physical_requests == physical_entries && f.fake.physical_effects == physical_entries
                && f.fake.physical_replies == no_replies); return;
        }
        auto completed = [](const Command& command) {
            command.consumed();
            CHECK(command.result.bytes_written == 0 && command.bytes().empty() && command.output.front() == 0xa5);
        };
        for (std::size_t index = 0; index < PhysicalLane::operations.size(); ++index) {
            Command command(f.fake.document,index+1); physical(command,index); CHECK(command.run() == 0); completed(command);
        }
        // Operation3 is focus in the command domain and document snapshot in
        // the query domain. The private request/reply validators see both.
        Query query(f.fake.document,4); CHECK(query.run() == 0); query.completed();
        Command action(f.fake.document,5); CHECK(action.run() == 0); action.consumed();
        Command blocked(f.fake.document,6); physical(blocked,1); const auto counts = f.fake.counts;
        CHECK(blocked.run() == BIB_ENGINE_LIMIT); blocked.rejected(); CHECK(f.fake.counts == counts);
        Command ack(f.fake.document,6); ack.ack(5); CHECK(ack.run() == 0); ack.receipt(0,5);
        auto expected = counts; ++expected.retirements; CHECK(f.fake.counts == expected);
        blocked.request.request_sequence = 7; CHECK(blocked.run() == 0); completed(blocked);
        Command maximum(f.fake.document,UINT64_MAX); physical(maximum,0); const auto before = f.fake.counts;
        CHECK(maximum.run() == BIB_ENGINE_INVALID); maximum.rejected(); CHECK(f.fake.counts == before);
        Command next(f.fake.document,8); physical(next,2); CHECK(next.run() == 0); completed(next);
        const std::array<int,3> observed{1,2,2};
        CHECK(f.fake.physical_requests == observed && f.fake.physical_replies == observed && f.fake.physical_effects == observed);
        CHECK(f.fake.counts.effects == 6 && f.fake.counts.queries == 1 && f.fake.counts.retirements == 1); return;
    }
    f.bind();
    if (name == "minor-optin") {
        BibEngineProviderV1 untouched{}; untouched.size = 17;
        CHECK(bib_engine_get_provider_v1(1,0,sizeof(untouched),&untouched) == BIB_ENGINE_UNSUPPORTED);
        CHECK(untouched.size == 17);
        CHECK(bib_engine_get_provider_v1(1,99,sizeof(untouched),&untouched) == 0);
        CHECK(untouched.abi_minor == 1 && untouched.build.capabilities == 1795);
        CHECK(std::equal(contract.begin(),contract.end(),untouched.build.contract_header_sha256)); return;
    }
    if (name == "startup-validation") {
        BibEngineStartResultV1 result{sizeof(result),99,99};
        f.host.abi_minor = 1; CHECK(provider.start(&f.host,&f.config,&result) == BIB_ENGINE_INVALID); f.host.abi_minor = 0;
        CHECK(result.phase == 0 && f.fake.counts.enters == 0);
        f.config.limits.maximum_reply_bytes = reply_capacity - 1;
        CHECK(provider.start(&f.host,&f.config,&result) == BIB_ENGINE_INVALID);
        CHECK(result.phase == 0 && f.fake.counts.enters == 0);
        f.config.limits.maximum_reply_bytes = reply_capacity; f.start(); return;
    }
    f.start();
    if (name == "malformed-command") { malformed_command(f); return; }
    if (name == "malformed-query") { malformed_query(f); return; }
    if (name == "action-shapes") { malformed_action_shapes(f); return; }
    if (name == "action-replay") {
        Command action(f.fake.document); f.fake.mutate = action.payload.data() + 73;
        CHECK(action.run() == 0); action.consumed(); const auto bytes = action.bytes();
        CHECK(f.fake.captured_node == 3 && action.payload[73] == 91);
        action.payload[73] = 3; f.fake.mutate = nullptr; std::fill(action.output.begin(),action.output.end(),0xcc);
        const auto counts = f.fake.counts; ++f.fake.document.document_sequence; ++f.fake.document.service_generation;
        CHECK(action.run() == 0 && action.bytes() == bytes && f.fake.counts == counts);
        action.payload[73] = 4; CHECK(action.run() != 0); action.rejected(); CHECK(f.fake.counts == counts);
        action.payload[73] = 3; ++action.request.expected.document_sequence;
        overwrite(action.payload,24,action.request.expected.document_sequence,8);
        CHECK(action.run() != 0); action.rejected(); CHECK(f.fake.counts == counts); return;
    }
    if (name == "backpressure") {
        Command first(f.fake.document,1); CHECK(first.run() == 0);
        Command second(f.fake.document,2); const auto counts = f.fake.counts;
        CHECK(second.run() == BIB_ENGINE_LIMIT); second.rejected(); CHECK(f.fake.counts == counts);
        Command ack(f.fake.document,2); ack.ack(1); CHECK(ack.run() == 0); ack.receipt(0,1);
        CHECK(f.fake.counts.retirements == 1);
        second.request.request_sequence = 3; overwrite(second.payload,32,3,8);
        CHECK(second.run() == 0 && f.fake.counts.effects == 2); return;
    }
    if (name == "ack-metadata") {
        Command action(f.fake.document,1); CHECK(action.run() == 0);
        Command ack(f.fake.document,2); ack.ack(1); const auto counts = f.fake.counts;
        CHECK(ack.run() == 0); ack.receipt(0,1);
        auto expected = counts; ++expected.retirements; CHECK(f.fake.counts == expected && f.fake.retired_sequence == 1);
        const auto bytes = ack.bytes(); CHECK(ack.run() == 0 && ack.bytes() == bytes && f.fake.counts == expected);
        ack.request.request_sequence = 3; CHECK(ack.run() == 0); ack.receipt(1,1); CHECK(f.fake.counts == expected); return;
    }
    if (name == "ack-old-document") {
        Command action(f.fake.document,1); CHECK(action.run() == 0); const auto original = action.request.expected;
        ++f.fake.document.document_sequence; ++f.fake.document.service_generation;
        const auto counts = f.fake.counts; CHECK(action.run() == 0 && f.fake.counts == counts);
        std::fill(action.payload.begin(),action.payload.end(),0xcc);
        Command ack(original,2); ack.ack(1); CHECK(ack.run() == 0); ack.receipt(0,1);
        auto expected = counts; ++expected.retirements; CHECK(f.fake.counts == expected);
        Command next(f.fake.document,3); CHECK(next.run() == 0 && f.fake.counts.effects == 2); return;
    }
    if (name == "ack-capacity") {
        Command action(f.fake.document,1); CHECK(action.run() == 0);
        Command ack(f.fake.document,2); ack.ack(1); const auto counts = f.fake.counts;
        ack.buffer.capacity = 15; CHECK(ack.run() == BIB_ENGINE_INVALID); ack.rejected(); CHECK(f.fake.counts == counts);
        ack.buffer.capacity = 16; CHECK(ack.run() == 0); ack.receipt(0,1); const auto after = f.fake.counts;
        ack.buffer.capacity = 15; CHECK(ack.run() == BIB_ENGINE_INVALID); ack.rejected(); CHECK(f.fake.counts == after);
        ack.buffer.capacity = 16; CHECK(ack.run() == 0); ack.receipt(0,1); CHECK(f.fake.counts == after); return;
    }
    if (name == "malformed-ack") {
        Command action(f.fake.document,1); CHECK(action.run() == 0);
        Command ack(f.fake.document,2); ack.ack(1); const auto counts = f.fake.counts;
        auto reject = [&] { CHECK(ack.run() == BIB_ENGINE_INVALID); ack.rejected(); CHECK(f.fake.counts == counts); };
        ack.payload.pop_back(); reject(); ack.ack(1); ack.payload.push_back(0); reject();
        ack.ack(0); reject(); ack.ack(UINT64_MAX); reject(); ack.ack(2); reject();
        ack.request.request_sequence = 1; reject(); ack.request.request_sequence = 2;
        ack.ack(1); ack.request.payload.reserved = 1; reject(); ack.request.payload.reserved = 0;
        ack.request.expected.application_instance = 0; reject(); ack.request.expected = f.fake.document;
        ack.request.expected.document_sequence = 0; reject(); ack.request.expected = f.fake.document;
        ack.request.expected.service_generation = 0; reject(); ack.request.expected = f.fake.document;
        ack.request.schema_sha256[0] ^= 1; reject(); ack.request.schema_sha256[0] ^= 1;
        ack.request.request_sequence = 0; CHECK(ack.run() != 0); ack.rejected(); CHECK(f.fake.counts == counts);
        ack.request.request_sequence = 2; CHECK(ack.run() == 0); ack.receipt(0,1); return;
    }
    if (name == "ack-retained-replies") {
        Command action(f.fake.document,1); CHECK(action.run() == 0);
        Command zero(f.fake.document,2); zero.ack(1); CHECK(zero.run() == 0); zero.receipt(0,1); const auto zero_bytes = zero.bytes();
        Command one(f.fake.document,3); one.ack(1); CHECK(one.run() == 0); one.receipt(1,1); const auto one_bytes = one.bytes();
        auto counts = f.fake.counts; ++f.fake.document.document_sequence;
        CHECK(one.run() == 0 && one.bytes() == one_bytes && f.fake.counts == counts);
        CHECK(zero.run() == 0 && zero.bytes() == zero_bytes && f.fake.counts == counts);
        Command two(zero.request.expected,4); two.ack(2); CHECK(two.run() == 0); two.receipt(2,2); const auto two_bytes = two.bytes();
        CHECK(two.run() == 0 && two.bytes() == two_bytes && f.fake.counts == counts);
        CHECK(zero.run() == 0 && zero.bytes() == zero_bytes && f.fake.counts == counts);
        CHECK(one.run() == BIB_ENGINE_STALE); one.rejected(); CHECK(f.fake.counts == counts);
        Query newer(f.fake.document,5); CHECK(newer.run() == 0); counts = f.fake.counts;
        CHECK(two.run() == 0 && two.bytes() == two_bytes && f.fake.counts == counts);
        CHECK(zero.run() == 0 && zero.bytes() == zero_bytes && f.fake.counts == counts); return;
    }
    if (name == "ack-unmatched") {
        Command first(f.fake.document,1); CHECK(first.run() == 0);
        Command retirement(f.fake.document,2); retirement.ack(1); CHECK(retirement.run() == 0); retirement.receipt(0,1);
        Command pending(f.fake.document,3); CHECK(pending.run() == 0); const auto bytes = pending.bytes();
        Command duplicate(f.fake.document,4); duplicate.ack(1); CHECK(duplicate.run() == 0); duplicate.receipt(1,1);
        Command wrong(f.fake.document,5); wrong.ack(3); ++wrong.request.expected.application_instance;
        const auto counts = f.fake.counts; CHECK(wrong.run() == 0); wrong.receipt(2,3); CHECK(f.fake.counts == counts);
        CHECK(pending.run() == 0 && pending.bytes() == bytes && f.fake.counts == counts);
        CHECK(retirement.run() == 0); retirement.receipt(0,1); CHECK(f.fake.counts == counts);
        Command cleanup(f.fake.document,6); cleanup.ack(3); CHECK(cleanup.run() == 0); cleanup.receipt(0,3);
        CHECK(f.fake.counts.retirements == 2); return;
    }
    if (name == "ack-expired") {
        Command action(f.fake.document,1); CHECK(action.run() == 0);
        Command old(f.fake.document,2); old.ack(1); CHECK(old.run() == 0);
        Command second(f.fake.document,3); CHECK(second.run() == 0);
        Command fresh(f.fake.document,4); fresh.ack(3); CHECK(fresh.run() == 0); const auto counts = f.fake.counts;
        CHECK(old.run() == BIB_ENGINE_STALE); old.rejected(); CHECK(f.fake.counts == counts);
        Command absent(f.fake.document,5); absent.ack(1); CHECK(absent.run() == 0); absent.receipt(2,1);
        CHECK(f.fake.counts == counts); CHECK(fresh.run() == 0); fresh.receipt(0,3); CHECK(f.fake.counts == counts);
        Command third(f.fake.document,6); CHECK(third.run() == 0 && f.fake.counts.effects == 3); return;
    }
    if (name == "shared-query-sequence") {
        Query query(f.fake.document,1); CHECK(query.run() == 0); const auto counts = f.fake.counts;
        Command stale(f.fake.document,1); CHECK(stale.run() == BIB_ENGINE_STALE); stale.rejected(); CHECK(f.fake.counts == counts);
        Command action(f.fake.document,2); CHECK(action.run() == 0);
        Query old(f.fake.document,1); CHECK(old.run() == BIB_ENGINE_STALE && old.result.bytes_written == 0);
        Command ack(f.fake.document,3); ack.ack(2); CHECK(ack.run() == 0); ack.receipt(0,2); return;
    }
    if (name == "sequence-max") {
        Query query(f.fake.document,maximum_ordinary-1); CHECK(query.run() == 0);
        const auto counts = f.fake.counts;
        Command invalid(f.fake.document,UINT64_MAX); CHECK(invalid.run() != 0); invalid.rejected(); CHECK(f.fake.counts == counts);
        Command action(f.fake.document,maximum_ordinary); CHECK(action.run() == 0);
        Command ack(f.fake.document,UINT64_MAX); ack.ack(maximum_ordinary); CHECK(ack.run() == 0); ack.receipt(0,maximum_ordinary);
        const auto after = f.fake.counts; const auto bytes = ack.bytes(); ++f.fake.document.document_sequence;
        CHECK(ack.run() == 0 && ack.bytes() == bytes && f.fake.counts == after);
        Query exhausted(f.fake.document,UINT64_MAX); CHECK(exhausted.run() != 0 && exhausted.result.bytes_written == 0);
        CHECK(f.fake.counts == after); CHECK(action.run() == BIB_ENGINE_STALE); action.rejected(); CHECK(f.fake.counts == after); return;
    }
    if (name == "request-validation") {
        Command action(f.fake.document,1); f.fake.request_status = BIB_ENGINE_STALE;
        CHECK(action.run() == BIB_ENGINE_STALE); action.rejected();
        CHECK(f.fake.counts.effects == 0 && f.fake.counts.request_validations == 1);
        f.fake.request_status = 0; CHECK(action.run() == 0 && f.fake.counts.effects == 1);
        CHECK(f.fake.counts.request_validations == 3); return;
    }
    if (name == "request-preflight") {
        const auto baseline = f.fake.counts;
        Command retired(f.fake.document,1);
        ++f.fake.document.document_sequence; ++f.fake.document.service_generation;
        f.fake.reject_retired_identity = true;
        CHECK(retired.run() == BIB_ENGINE_STALE); retired.rejected();
        CHECK(retired.result.request_sequence == 1 && std::all_of(retired.output.begin(),retired.output.end(),[](auto byte) { return byte == 0xa5; }));
        auto expected = baseline; ++expected.request_validations;
        check_counts(f.fake.counts,expected);
        Command current(f.fake.document,1);
        CHECK(current.run() == BIB_ENGINE_OK); current.consumed();
        expected = baseline; expected.request_validations += 3; ++expected.currents;
        ++expected.enters; ++expected.leaves; ++expected.effects; ++expected.reply_validations;
        check_counts(f.fake.counts,expected);
        return;
    }
    if (name == "request-preflight-throw" || name == "request-preflight-terminal") {
        const auto baseline = f.fake.counts;
        Command action(f.fake.document,1);
        f.fake.throw_request = name == "request-preflight-throw";
        f.fake.request_status = f.fake.throw_request ? 0 : BIB_ENGINE_PROCESS_EXIT_REQUIRED;
        CHECK(action.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED); action.rejected();
        CHECK(std::all_of(action.output.begin(),action.output.end(),[](auto byte) { return byte == 0xa5; }));
        auto expected = baseline; ++expected.request_validations;
        check_counts(f.fake.counts,expected);
        const auto counts = f.fake.counts;
        CHECK(action.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED && f.fake.counts == counts);
        return;
    }
    if (name == "request-enter-invalidation" || name == "request-enter-revalidation") {
        const auto baseline = f.fake.counts;
        Command action(f.fake.document,1);
        f.fake.navigate_enter = name == "request-enter-invalidation";
        f.fake.reject_request_on_enter = name == "request-enter-revalidation";
        CHECK(action.run() == BIB_ENGINE_STALE); action.rejected();
        CHECK(action.result.request_sequence == 1 && std::all_of(action.output.begin(),action.output.end(),[](auto byte) { return byte == 0xa5; }));
        auto expected = baseline; ++expected.enters; ++expected.leaves; ++expected.currents;
        expected.request_validations += f.fake.navigate_enter ? 1 : 2;
        check_counts(f.fake.counts,expected);
        f.fake.navigate_enter = false; f.fake.reject_request_on_enter = false; f.fake.request_status = 0;
        Command current(f.fake.document,1);
        CHECK(current.run() == BIB_ENGINE_OK); current.consumed();
        ++expected.enters; ++expected.leaves; ++expected.currents; ++expected.effects;
        expected.request_validations += 2; ++expected.reply_validations;
        check_counts(f.fake.counts,expected); return;
    }
    if (name == "enter-rejection") {
        Command action(f.fake.document,1); const auto counts = f.fake.counts;
        f.fake.enter_status = 2; CHECK(action.run() == BIB_ENGINE_REENTRANT); action.rejected();
        auto expected = counts; ++expected.enters; ++expected.request_validations; check_counts(f.fake.counts,expected);
        f.fake.enter_status = 14; CHECK(action.run() == BIB_ENGINE_REENTRANT); action.rejected();
        ++expected.enters; ++expected.request_validations; check_counts(f.fake.counts,expected);
        f.fake.enter_status = 0; CHECK(action.run() == 0); action.consumed();
        ++expected.enters; ++expected.leaves; expected.request_validations += 2; ++expected.currents; ++expected.effects; ++expected.reply_validations;
        check_counts(f.fake.counts,expected); return;
    }
    if (name == "reply-validation") {
        Command action(f.fake.document,1); f.fake.reply_status = BIB_ENGINE_INVALID;
        CHECK(action.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED && action.result.disposition == 2 && action.result.bytes_written == 0);
        CHECK(f.fake.counts.effects == 1 && f.fake.counts.reply_validations == 1);
        const auto counts = f.fake.counts; CHECK(action.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED && f.fake.counts == counts);
        Command ack(f.fake.document,2); ack.ack(1); CHECK(ack.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED && f.fake.counts == counts); return;
    }
    if (name == "query-zero-revision" || name == "query-wrong-revision" || name == "query-error"
            || name == "query-navigation" || name == "query-malformed" || name == "query-reply-validator") {
        if (name == "query-zero-revision") f.fake.query_revision = 0;
        if (name == "query-wrong-revision") f.fake.query_revision = 10;
        if (name == "query-error") f.fake.query_status = BIB_ENGINE_INVALID;
        if (name == "query-navigation") f.fake.navigate_query = true;
        if (name == "query-malformed") f.fake.malformed_reply = true;
        if (name == "query-reply-validator") f.fake.reply_status = BIB_ENGINE_INVALID;
        Query query(f.fake.document,1); CHECK(query.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED);
        CHECK(query.result.bytes_written == 0 && query.result.semantic_revision == 0);
        CHECK(query.result.document.application_instance == 0 && query.result.document.document_sequence == 0
            && query.result.document.service_generation == 0 && query.output.front() == 0xa5);
        const auto counts = f.fake.counts; CHECK(query.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED && f.fake.counts == counts);
        CHECK(query.result.bytes_written == 99 && query.result.semantic_revision == 99);
        BibEngineProviderV1 untouched{}; untouched.size = 17;
        CHECK(bib_engine_get_provider_v1(1,1,sizeof(untouched),&untouched) == BIB_ENGINE_PROCESS_EXIT_REQUIRED && untouched.size == 17); return;
    }
    if (name == "inner-unknown") {
        f.fake.inner_unknown = true; Command action(f.fake.document,1); CHECK(action.run() == 0); action.consumed(true);
        CHECK(action.result.bytes_written == 52 && action.output[48] == 2 && action.output[49] == 8 && action.output[50] == 1);
        const auto bytes = action.bytes(); const auto counts = f.fake.counts;
        CHECK(action.run() == 0 && action.bytes() == bytes && f.fake.counts == counts);
        Command ack(f.fake.document,2); ack.ack(1); CHECK(ack.run() == 0); ack.receipt(0,1);
        auto expected = counts; ++expected.retirements; CHECK(f.fake.counts == expected); return;
    }
    if (name == "terminal-unknown" || name == "command-error" || name == "command-malformed" || name == "leave-throw"
            || name == "retire-error" || name == "retire-throw") {
        Command action(f.fake.document,1);
        if (name == "terminal-unknown") f.fake.throw_command = true;
        if (name == "command-error") f.fake.command_status = BIB_ENGINE_INVALID;
        if (name == "command-malformed") f.fake.malformed_reply = true;
        if (name == "leave-throw") f.fake.throw_leave = true;
        const bool unknown_action = name == "terminal-unknown" || name == "command-error" || name == "command-malformed" || name == "leave-throw";
        if (unknown_action) {
            CHECK(action.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED && action.result.disposition == 2 && action.result.bytes_written == 0);
        } else CHECK(action.run() == 0);
        Command ack(f.fake.document,2); ack.ack(1);
        if (name == "retire-error") f.fake.retire_status = BIB_ENGINE_INVALID;
        if (name == "retire-throw") f.fake.throw_retire = true;
        CHECK(ack.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED);
        if (unknown_action) {
            CHECK(ack.result.disposition == 99 && ack.result.bytes_written == 99 && ack.result.request_sequence == 99 && ack.result.handled == 99);
        } else CHECK(ack.result.disposition == 2 && ack.result.bytes_written == 0 && f.fake.counts.retirements == 1);
        const auto counts = f.fake.counts;
        CHECK(action.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED && f.fake.counts == counts);
        CHECK(action.result.disposition == 99 && action.result.bytes_written == 99);
        CHECK(ack.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED && f.fake.counts == counts);
        CHECK(ack.result.disposition == 99 && ack.result.bytes_written == 99);
        BibEngineProviderV1 untouched{}; untouched.size = 17;
        CHECK(bib_engine_get_provider_v1(1,1,sizeof(untouched),&untouched) == BIB_ENGINE_PROCESS_EXIT_REQUIRED && untouched.size == 17); return;
    }
    if (name == "wrong-thread") {
        Command action(f.fake.document,1); Query query(f.fake.document,2); Command ack(f.fake.document,3); ack.ack(1);
        const auto counts = f.fake.counts; int a{}, q{}, r{};
        std::thread wrong([&] { a = action.run(); q = query.run(); r = ack.run(); }); wrong.join();
        CHECK(a == BIB_ENGINE_WRONG_THREAD && q == BIB_ENGINE_WRONG_THREAD && r == BIB_ENGINE_WRONG_THREAD);
        CHECK(f.fake.counts == counts); CHECK(action.run() == 0); return;
    }
    if (name == "reentry") {
        f.fake.reenter = true; Command action(f.fake.document,1); CHECK(action.run() == 0);
        CHECK(f.fake.nested_enter == BIB_ENGINE_REENTRANT && f.fake.nested_request == BIB_ENGINE_REENTRANT);
        CHECK(f.fake.nested_command == BIB_ENGINE_REENTRANT && f.fake.nested_leave == BIB_ENGINE_REENTRANT);
        CHECK(f.fake.threaded == BIB_ENGINE_WRONG_THREAD);
        Command ack(f.fake.document,2); ack.ack(1); CHECK(ack.run() == 0);
        CHECK(f.fake.nested_retire == BIB_ENGINE_REENTRANT); return;
    }
    throw std::runtime_error("unknown test group");
}
} // namespace

int main(int argc, char** argv) {
    try { CHECK(argc == 2); run(argv[1]); CHECK(first_assertion_failure.empty()); std::cout << "PASS " << argv[1] << '\n'; return 0; }
    catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
