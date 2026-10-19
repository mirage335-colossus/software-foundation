// SPDX-License-Identifier: CC0-1.0
// New private guard/helper only. No real engine binding or qualification exists.
#include "EnginePrivate.hpp"
#include "engine_editor_protocol.h"
#include "engine_editor_pins.hpp"
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
using Digest = std::array<std::uint8_t, 32>;
consteval Digest digest(std::string_view text) {
    Digest result{};
    for (std::size_t i = 0; i < result.size(); ++i) {
        auto digit = [](char c) { return c <= '9' ? c - '0' : c - 'a' + 10; };
        result[i] = static_cast<std::uint8_t>((digit(text[2*i]) << 4) | digit(text[2*i+1]));
    }
    return result;
}
constexpr auto document_schema = digest(BIB_ENGINE_DOCUMENT_V2_SCHEMA_SHA256_HEX);
constexpr auto document_ack_schema = digest(BIB_ENGINE_DOCUMENT_V2_ACK_SCHEMA_SHA256_HEX);
constexpr auto document_extension = digest("7b047bae4d0072ef156ea94ba637566d563fea3a95d43c4c6314afc919b1d626");
constexpr auto document_contract = digest("aba7800e6aab1898f3614f0b1ac53e59b9f622bf1e9d3a413f50d672a3662298");
constexpr auto document_catalog = digest("6e555d4c3bb71fbc965e1ca49671fab64d744913e18f45b9ba273505e0c6bcf5");
constexpr auto physical_catalog = digest("d244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b");
constexpr std::array<Operation, 3> physical_operations{{
    {1,160,16,16,digest("86b7baad1c95bfb8de3e6b7a9a7c433b528278bbcf84199ca0b2b4ee6134dbc9")},
    {3,32,16,64,digest("eef60cda2aa7b791641b0e5082d551ec37c10b8d92ca4cc71f13be0af45321d9")},
    {5,80,16,128,digest("6a15d0e2f814564ce263824dd782335bb327b886e982aefec32476a29b0fd4a3")},
}};
constexpr std::array<Operation, 2> document_commands{{
    {6,6246,1048576,1024,document_schema}, {7,8,16,1024,document_ack_schema},
}};
constexpr Operation document_query_operation{3,48,1048576,512,document_schema};
namespace editor_contract_facts = foundation::appended::engine_editor;
constexpr std::array<Operation,2> editor_commands{{
    {BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1,BIB_ENGINE_EDITOR_MAX_WIRE_BYTES,BIB_ENGINE_EDITOR_REPLY_CAPACITY,
        BIB_ENGINE_CAP_COMPOSITION_V1,editor_contract_facts::kSchema},
    {BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1,BIB_ENGINE_EDITOR_MAX_WIRE_BYTES,BIB_ENGINE_EDITOR_REPLY_CAPACITY,
        BIB_ENGINE_CAP_COMPOSITION_V1,editor_contract_facts::kSchema},
}};
constexpr Operation editor_query_operation{BIB_ENGINE_QUERY_EDITOR_PROJECTION_V1,BIB_ENGINE_EDITOR_MAX_QUERY_BYTES,
    BIB_ENGINE_EDITOR_REPLY_CAPACITY,BIB_ENGINE_CAP_COMPOSITION_V1,editor_contract_facts::kSchema};

std::uint64_t integer(const std::uint8_t* bytes, std::size_t width) {
    std::uint64_t result=0;
    for (std::size_t i=0; i<width; ++i) result |= std::uint64_t(bytes[i]) << (8*i);
    return result;
}
void put_integer(std::uint8_t* bytes, std::uint64_t value, std::size_t width) {
    for (std::size_t i=0; i<width; ++i) bytes[i]=static_cast<std::uint8_t>(value >> (8*i));
}
bool editor_header_valid(const std::vector<std::uint8_t>& bytes, std::uint32_t kind, std::uint32_t bound) {
    constexpr std::array<std::uint8_t,8> magic{'B','I','B','E','D','V','1',0};
    return bytes.size()>=BIB_ENGINE_EDITOR_WIRE_HEADER_BYTES && bytes.size()<=bound
        && std::equal(magic.begin(),magic.end(),bytes.begin()) && integer(bytes.data()+8,2)==kind
        && !integer(bytes.data()+10,2) && integer(bytes.data()+12,4)==bytes.size();
}
bool editor_target_join(const std::vector<std::uint8_t>& bytes, std::size_t offset,
                        const BibEngineDocumentV1& expected, std::uint64_t worker, std::uint64_t sequence) {
    return bytes.size()>=offset+40 && worker && sequence && sequence<=BIB_ENGINE_DOCUMENT_V2_MAX_ORDINARY_SEQUENCE
        && integer(bytes.data()+offset,8)==worker
        && integer(bytes.data()+offset+8,8)==expected.application_instance
        && integer(bytes.data()+offset+16,8)==expected.document_sequence
        && integer(bytes.data()+offset+24,8)==expected.service_generation
        && integer(bytes.data()+offset+32,8)==sequence;
}
bool editor_request_valid(const std::vector<std::uint8_t>& bytes, const BibEngineDocumentV1& expected,
                          std::uint64_t worker, std::uint64_t sequence, std::uint32_t operation, bool query) {
    const auto kind=query?BIB_ENGINE_EDITOR_WIRE_PROJECTION_QUERY:
        operation==BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1?BIB_ENGINE_EDITOR_WIRE_NATIVE_REQUEST:BIB_ENGINE_EDITOR_WIRE_REVOCATION;
    return editor_header_valid(bytes,kind,query?BIB_ENGINE_EDITOR_MAX_QUERY_BYTES:BIB_ENGINE_EDITOR_MAX_WIRE_BYTES)
        && editor_target_join(bytes,16,expected,worker,sequence);
}
bool editor_reply_valid(const std::vector<std::uint8_t>& bytes, const BibEngineDocumentV1& expected,
                        std::uint64_t worker, std::uint64_t sequence, bool query, std::uint64_t revision=0) {
    return editor_header_valid(bytes,query?BIB_ENGINE_EDITOR_WIRE_PROJECTION_REPLY:BIB_ENGINE_EDITOR_WIRE_NATIVE_RESULT,
            BIB_ENGINE_EDITOR_REPLY_CAPACITY)
        && editor_target_join(bytes,query?24:16,expected,worker,sequence)
        // Closed LEu32 states/outcomes are the first native body field. The
        // NativeResult unknown value3 is terminal even if a private validator
        // accidentally admits it; the complete grammar is still mandatory.
        && (query ? (bytes.size()>=68 && revision && integer(bytes.data()+16,8)==revision
                && integer(bytes.data()+64,4)<=2)
            : (bytes.size()>=60 && integer(bytes.data()+56,4)<=2));
}
bool full_identity(const BibEngineDocumentV1& document) {
    return document.application_instance && document.document_sequence && document.service_generation;
}
bool packet_join(const std::vector<std::uint8_t>& bytes, const BibEngineDocumentV1& expected,
                 std::uint64_t sequence, unsigned kind, std::uint64_t nested) {
    return bytes.size() >= 48 && integer(bytes.data(),4)==0x3256444e && integer(bytes.data()+4,2)==2
        && bytes[6]==kind && !bytes[7] && full_identity(expected)
        && integer(bytes.data()+8,8)==expected.application_instance
        && integer(bytes.data()+16,8)==expected.service_generation
        && integer(bytes.data()+24,8)==expected.document_sequence
        && integer(bytes.data()+32,8)==sequence && integer(bytes.data()+40,8)==nested;
}
// Validate every byte of the canonical bounded request grammar. Live version,
// lease and old-buffer authority is additionally checked by the opt-in binding.
bool document_request_valid(const std::vector<std::uint8_t>& bytes, const BibEngineDocumentV1& expected,
                            std::uint64_t sequence, bool query) {
    if (!sequence || sequence > BIB_ENGINE_DOCUMENT_V2_MAX_ORDINARY_SEQUENCE) return false;
    if (query) return bytes.size()==48 && packet_join(bytes,expected,sequence,1,integer(bytes.data()+40,8))
        && integer(bytes.data()+40,8);
    if (bytes.size()<81 || !packet_join(bytes,expected,sequence,2,0)) return false;
    const auto action=bytes[48];
    if (action>5 || integer(bytes.data()+49,8)!=expected.application_instance
        || integer(bytes.data()+57,8)!=expected.service_generation || !integer(bytes.data()+65,8)
        || !integer(bytes.data()+73,8)) return false;
    if (action==0 || action==4) return bytes.size()==81;
    if (bytes.size()<89 || !integer(bytes.data()+81,8)) return false;
    if (action==5) return bytes.size()==89;
    if (action==2) return bytes.size()==90 && bytes[89]<=1;
    if (action==3) return bytes.size()==98 && integer(bytes.data()+89,8) && bytes[97]<=1;
    if (bytes.size()<102 || integer(bytes.data()+89,4)>integer(bytes.data()+93,4)
        || integer(bytes.data()+93,4)>2048 || bytes[97]>2
        || integer(bytes.data()+98,4)!=bytes.size()-102) return false;
    std::size_t units=0;
    for (std::size_t at=102; at<bytes.size();) {
        const auto lead=bytes[at++]; std::uint32_t scalar=lead; unsigned continuation=0;
        if (lead && lead<0x80) {}
        else if (lead>=0xc2 && lead<=0xdf) { scalar=lead&31; continuation=1; }
        else if (lead>=0xe0 && lead<=0xef) { scalar=lead&15; continuation=2; }
        else if (lead>=0xf0 && lead<=0xf4) { scalar=lead&7; continuation=3; }
        else return false;
        if (continuation>bytes.size()-at) return false;
        for (unsigned i=0; i<continuation; ++i) {
            const auto byte=bytes[at++]; if ((byte&0xc0)!=0x80) return false;
            scalar=(scalar<<6)|(byte&63);
        }
        if ((continuation==1 && scalar<0x80) || (continuation==2 && scalar<0x800)
            || (continuation==3 && scalar<0x10000) || scalar>0x10ffff || (scalar>=0xd800 && scalar<=0xdfff)) return false;
        units += scalar>=0x10000 ? 2 : 1;
        if (units>2048) return false;
    }
    return true;
}

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
bool target_valid(const BibEngineBuildV1& b, bool document = false, bool editor = false) {
    if (b.size != sizeof(b) || b.layout_revision != BIB_ENGINE_LAYOUT_V1 || b.reserved || b.pointer_bits != sizeof(void*) * CHAR_BIT
        || b.lifetime != BIB_ENGINE_LIFETIME_PROCESS || b.maximum_starts != 1
        || (editor ? b.capabilities!=BIB_ENGINE_EDITOR_CAPABILITIES:
            document ? (b.capabilities != 1795 && b.capabilities != 2003) : (b.capabilities & ~known_capabilities))
        || std::memcmp(b.contract_header_sha256, editor?editor_contract_facts::kContractSha256.data():
            document ? document_contract.data() : contract_header_sha256.data(), 32)
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
    bool document_mode = false, editor_mode = false;
    EnginePrivateV1 backend{};
    EngineDocumentPrivateV1 document_backend{};
    EngineEditorPrivateV1 editor_backend{};
    std::array<Operation, maximum_operations> commands{}, queries{};
    BibEngineHostV1 host{};
    BibEngineStartV1 start_config{};
    std::vector<std::uint8_t> entry, persistence;
    std::uint64_t last_sequence = 0;
    struct RequestKey {
        BibEngineDocumentV1 expected{};
        std::uint64_t worker_epoch{}, sequence{};
        std::uint32_t operation{};
        Digest schema{};
        std::vector<std::uint8_t> payload;
        bool matches(const RequestKey& other) const {
            return worker_epoch==other.worker_epoch && same(expected,other.expected) && sequence==other.sequence
                && operation==other.operation && schema==other.schema && payload==other.payload;
        }
    };
    struct RetainedAction {
        bool present=false;
        RequestKey key;
        BibEngineCommandResultV1 result{};
        std::int32_t status=BIB_ENGINE_OK;
        std::vector<std::uint8_t> bytes;
    } action;
    // Terminal editor evidence is owned process-wide, never exported or used
    // as a retry cache. Moving already-reserved buffers here runs no provider
    // cleanup and keeps the uncertain input/output intact after a callback trap.
    struct EditorForensics {
        bool present=false, query=false;
        RequestKey key;
        std::vector<std::uint8_t> bytes;
    } editor_unknown;
    struct AckReceipt {
        bool present=false;
        RequestKey key;
        std::array<std::uint8_t,16> bytes{};
    } latest_ack, retirement;

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
    bool document_catalog_valid(const EnginePrivateV1& value, const EngineDocumentPrivateV1& document,
                                const EngineEditorPrivateV1* editor) const {
        const bool physical=document.profile==document_physical_profile;
        if (document.size!=sizeof(document) || document.version!=document_private_interface_version || document.reserved
            || !document.worker_epoch || (!physical && document.profile!=document_pixel_profile)
            || value.build.capabilities!=(editor?BIB_ENGINE_EDITOR_CAPABILITIES:physical?2003u:1795u)
            || document.base_header_sha256!=contract_header_sha256 || document.extension_header_sha256!=document_extension
            || document.contract_sha256!=document_contract || document.catalog_sha256!=document_catalog
            || (physical ? document.physical_catalog_sha256!=physical_catalog : nonzero(document.physical_catalog_sha256.data(),32))
            || !document.validate_request || !document.validate_reply || !document.retire_action_metadata
            || value.command_count!=(editor?7u:physical?5u:2u) || value.query_count!=(editor?2u:1u) || !value.commands || !value.queries) return false;
        if (editor && (!physical || editor->size!=sizeof(*editor) || editor->version!=editor_private_interface_version
            || editor->reserved0 || editor->reserved1 || editor->worker_epoch!=document.worker_epoch
            || editor->editor_header_sha256!=editor_contract_facts::kHeaderSha256
            || editor->contract_sha256!=editor_contract_facts::kContractSha256
            || editor->catalog_sha256!=editor_contract_facts::kCatalogSha256 || editor->schema_sha256!=editor_contract_facts::kSchema
            || !editor->admit_request || !editor->validate_reply || !editor->project || !editor->apply || !editor->revoke)) return false;
        const auto equal=[](const Operation& a,const Operation& b) {
            return a.kind==b.kind && a.maximum_input_bytes==b.maximum_input_bytes
                && a.required_reply_capacity==b.required_reply_capacity && a.capability==b.capability && a.schema==b.schema;
        };
        if (!equal(value.queries[0],document_query_operation)) return false;
        if (editor && (!equal(value.queries[1],editor_query_operation)
            || value.limits.maximum_query_bytes<editor_query_operation.maximum_input_bytes)) return false;
        for (std::uint32_t i=0; i<value.command_count; ++i) {
            const auto& op=value.commands[i]; const Operation* expected=nullptr;
            for (const auto& candidate:document_commands) if (candidate.kind==op.kind) expected=&candidate;
            if (physical) for (const auto& candidate:physical_operations) if (candidate.kind==op.kind) expected=&candidate;
            if (editor) for (const auto& candidate:editor_commands) if (candidate.kind==op.kind) expected=&candidate;
            if (!expected || !equal(op,*expected) || op.maximum_input_bytes>value.limits.maximum_command_bytes
                || op.required_reply_capacity>value.limits.maximum_reply_bytes) return false;
            for (std::uint32_t j=0; j<i; ++j) if (value.commands[j].kind==op.kind) return false;
        }
        return value.limits.maximum_query_bytes>=48 && value.limits.maximum_reply_bytes>=1048576;
    }
    std::int32_t bind(const EnginePrivateV1& value, const EngineDocumentPrivateV1* document = nullptr,
                      const EngineEditorPrivateV1* editor = nullptr) {
        Gate gate(*this, false); if (!gate) return gate.status;
        if (bound || phase.load() != BIB_ENGINE_START_NOT_RETAINED) return BIB_ENGINE_CLOSED;
        if (value.size < sizeof(value) || value.version != private_interface_version || !value.application_instance
            || (editor && !document) || !target_valid(value.build,document!=nullptr,editor!=nullptr)
            || !limits_valid(value.limits) || !value.preflight || !value.start
            || !value.advance || !value.current_document) return BIB_ENGINE_INVALID;
        if (document && !document_catalog_valid(value,*document,editor)) return BIB_ENGINE_INVALID;
        backend = value; // Not published/usable until every complete validation passes.
        backend.size = sizeof(backend);
        if (!document && (!catalog_valid(value.commands, value.command_count, false) || !catalog_valid(value.queries, value.query_count, true))) {
            backend = {}; return BIB_ENGINE_INVALID;
        }
        if ((value.command_count && !value.command) || (value.query_count && !value.query)
            || ((value.build.capabilities & BIB_ENGINE_CAP_SERVICE_QUEUE)
                && (!value.deliver_services || !value.collect_service_ack || !value.dispose_retired_service_document))
            || ((value.build.capabilities & BIB_ENGINE_CAP_APP_BUNDLE) && !value.install_resources)
            || ((value.build.capabilities & BIB_ENGINE_CAP_DIRTY_RGBA8)
                && (value.build.fixed_viewport_width != 800 || value.build.fixed_viewport_height != 600))) { backend = {}; return BIB_ENGINE_INVALID; }
        for (std::uint32_t kind = 1; kind <= BIB_ENGINE_COMMAND_POINTER; ++kind) {
            if (editor && kind==BIB_ENGINE_COMMAND_COMPOSITION) continue;
            auto cap = operation_cap(kind, false);
            if ((value.build.capabilities & cap) && (!value.command_count || !std::any_of(value.commands, value.commands + value.command_count,
                    [kind](const auto& op) { return op.kind == kind; }))) { backend = {}; return BIB_ENGINE_INVALID; }
        }
        if ((value.build.capabilities & BIB_ENGINE_CAP_SEMANTIC_SNAPSHOT_V1)
            && (!value.query_count || !std::any_of(value.queries, value.queries + value.query_count,
                [](const auto& op) { return op.kind == BIB_ENGINE_QUERY_SEMANTIC_SNAPSHOT; }))) { backend = {}; return BIB_ENGINE_INVALID; }
        if (value.command_count) std::copy_n(value.commands, value.command_count, commands.begin());
        if (value.query_count) std::copy_n(value.queries, value.query_count, queries.begin());
        backend.commands = commands.data(); backend.queries = queries.data();
        if (document) { document_backend=*document; document_mode=true; }
        if (editor) { editor_backend=*editor; editor_mode=true; }
        bound = true;
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
            || (document_mode ? config.required_capabilities!=backend.build.capabilities : (config.required_capabilities & ~known_capabilities))
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
    RequestKey key(const BibEngineCommandV1& request, std::vector<std::uint8_t> payload) const {
        RequestKey value;
        value.expected=request.expected; value.worker_epoch=document_backend.worker_epoch;
        value.sequence=request.request_sequence; value.operation=request.operation;
        std::copy_n(request.schema_sha256,32,value.schema.begin()); value.payload=std::move(payload);
        return value;
    }
    std::int32_t metadata_ack(const BibEngineCommandV1& request, RequestKey request_key,
                              const BibEngineReplyBufferV1& buffer, BibEngineCommandResultV1& response) {
        const auto original=integer(request_key.payload.data(),8);
        // Exact receipts precede sequence admission and any live-document read.
        const AckReceipt* cached=latest_ack.present && latest_ack.key.matches(request_key)?&latest_ack:
            retirement.present && retirement.key.matches(request_key)?&retirement:nullptr;
        if (cached) {
            std::memcpy(buffer.bytes,cached->bytes.data(),cached->bytes.size());
            response.disposition=1; response.bytes_written=16; return BIB_ENGINE_OK;
        }
        if (request.request_sequence<=last_sequence) return BIB_ENGINE_STALE;
        AckReceipt receipt; receipt.present=true; receipt.key=std::move(request_key);
        // Prepare every owned key before either sequence admission or cleanup.
        AckReceipt proof;
        const bool matches_action=action.present && same(action.key.expected,request.expected)
            && action.key.worker_epoch==document_backend.worker_epoch && action.key.sequence==original;
        const bool matches_proof=retirement.present && same(retirement.key.expected,request.expected)
            && retirement.key.worker_epoch==document_backend.worker_epoch
            && integer(retirement.bytes.data(),8)==original;
        if (matches_action) {
            try { proof.present=true; proof.key=receipt.key; } catch (...) { return BIB_ENGINE_LIMIT; }
        }
        const auto code=matches_action?0u:matches_proof?1u:2u;
        put_integer(receipt.bytes.data(),original,8); put_integer(receipt.bytes.data()+8,code,4);
        last_sequence=request.request_sequence; response.disposition=2;
        if (matches_action) {
            BibEngineCommandV1 original_request{}; original_request.size=sizeof(original_request);
            original_request.expected=action.key.expected; original_request.operation=action.key.operation;
            original_request.request_sequence=action.key.sequence;
            std::copy_n(action.key.schema.begin(),32,original_request.schema_sha256);
            original_request.payload={action.key.payload.data(),static_cast<std::uint32_t>(action.key.payload.size()),0};
            std::int32_t retired;
            try { retired=document_backend.retire_action_metadata(backend.context,document_backend.worker_epoch,&original_request); }
            catch (...) { retired=BIB_ENGINE_PROCESS_EXIT_REQUIRED; }
            if (retired) { poisoned=true; return BIB_ENGINE_PROCESS_EXIT_REQUIRED; }
            // All operations below are allocation-free commits. A failed hook
            // leaves original action and previous proof untouched forever.
            proof.bytes=receipt.bytes; retirement=std::move(proof); action=RetainedAction{};
        }
        latest_ack=std::move(receipt);
        std::memcpy(buffer.bytes,latest_ack.bytes.data(),latest_ack.bytes.size());
        response.disposition=1; response.bytes_written=16; return BIB_ENGINE_OK;
    }
    std::int32_t document_command(const BibEngineCommandV1* input, BibEngineReplyBufferV1* output,
                                   BibEngineCommandResultV1* result) {
        Gate gate(*this,true); if (!gate) return gate.status;
        if (auto status=usable()) return status;
        if (!result || result->size<sizeof(*result)) return BIB_ENGINE_INVALID;
        BibEngineCommandResultV1 response{}; response.size=sizeof(response);
        auto reject=[&](std::int32_t code) { *result=response; return code; };
        if (!input || input->size<sizeof(*input) || !output || output->size<sizeof(*output)) return reject(BIB_ENGINE_INVALID);
        auto request=*input; request.size=sizeof(request); const auto buffer=*output;
        response.request_sequence=request.request_sequence;
        if (overlaps(buffer.bytes,buffer.capacity,result,sizeof(*result))) return BIB_ENGINE_INVALID;
        const auto* operation=find(request.operation,false);
        if (!operation || !enabled(operation->capability)) return reject(BIB_ENGINE_UNSUPPORTED);
        if (std::memcmp(request.schema_sha256,operation->schema.data(),32)
            || !span_valid(request.payload,operation->maximum_input_bytes)
            || request.payload.length>start_config.limits.maximum_command_bytes
            || !buffer.bytes || buffer.capacity<operation->required_reply_capacity || !full_identity(request.expected)
            || !request.request_sequence) return reject(BIB_ENGINE_INVALID);
        std::vector<std::uint8_t> payload;
        try { if (request.payload.length) payload.assign(request.payload.data,request.payload.data+request.payload.length); }
        catch (...) { return reject(BIB_ENGINE_LIMIT); }
        request.payload.data=payload.empty()?nullptr:payload.data();
        if (request.operation==BIB_ENGINE_COMMAND_ACK_FORM_ACTION_V2) {
            if (payload.size()!=8 || !integer(payload.data(),8)
                || integer(payload.data(),8)>BIB_ENGINE_DOCUMENT_V2_MAX_ORDINARY_SEQUENCE
                || request.request_sequence<=integer(payload.data(),8)) return reject(BIB_ENGINE_INVALID);
            return reject(metadata_ack(request,key(request,std::move(payload)),buffer,response));
        }
        if (request.request_sequence>BIB_ENGINE_DOCUMENT_V2_MAX_ORDINARY_SEQUENCE) return reject(BIB_ENGINE_INVALID);
        const bool form=request.operation==BIB_ENGINE_COMMAND_FORM_ACTION_V2;
        if (form && !document_request_valid(payload,request.expected,request.request_sequence,false)) return reject(BIB_ENGINE_INVALID);
        auto request_key=key(request,std::move(payload));
        request.payload.data=request_key.payload.empty()?nullptr:request_key.payload.data();
        if (form && action.present && action.key.matches(request_key)) {
            response=action.result;
            if (response.bytes_written) std::memcpy(buffer.bytes,action.bytes.data(),response.bytes_written);
            return reject(action.status);
        }
        if (request.request_sequence<=last_sequence) return reject(BIB_ENGINE_STALE);
        if (action.present) return reject(BIB_ENGINE_LIMIT);
        std::vector<std::uint8_t> scratch;
        try { scratch.resize(operation->required_reply_capacity); }
        catch (...) { return reject(BIB_ENGINE_LIMIT); }
        // Form request identity is inert metadata. Let the publisher reject a
        // retired cached identity before entering the host turn, while keeping
        // the in-turn validation below to cover navigation during host entry.
        if (form) {
            std::int32_t checked{};
            try {
                checked=transport(document_backend.validate_request(backend.context,document_backend.worker_epoch,
                    &request.expected,0,request.operation,request.request_sequence,&request.payload));
            } catch (...) {
                poisoned=true;
                return reject(BIB_ENGINE_PROCESS_EXIT_REQUIRED);
            }
            if (checked) {
                if (checked==BIB_ENGINE_PROCESS_EXIT_REQUIRED) poisoned=true;
                return reject(checked);
            }
        }
        BibEngineReplyBufferV1 scratch_buffer{sizeof(scratch_buffer),static_cast<std::uint32_t>(scratch.size()),scratch.data()};
        bool command_entered=false;
        auto status=turn([&] {
            auto checked=check_document(request.expected); if (checked) return checked;
            checked=transport(document_backend.validate_request(backend.context,document_backend.worker_epoch,
                &request.expected,0,request.operation,request.request_sequence,&request.payload));
            if (checked) return checked;
            // Key and full completion storage already exist before consumption.
            last_sequence=request.request_sequence; response.disposition=2;
            if (form) { action.present=true; action.key=std::move(request_key); }
            command_entered=true;
            auto code=backend.command(backend.context,&request,&scratch_buffer,&response);
            if (code || response.size!=sizeof(response) || response.bytes_written>scratch.size()
                || response.handled>1 || response.request_sequence!=request.request_sequence
                // Physical1/3/5 reserve16 bytes but return metadata only. Their
                // copied receipt remains80+24=104 bytes in the explicit2003 profile.
                || (!form && response.bytes_written))
                return code?code:BIB_ENGINE_INVALID;
            if (form) {
                scratch.resize(response.bytes_written);
                if (!packet_join(scratch,request.expected,request.request_sequence,5,0) || scratch.size()<52
                    || scratch[48]>2 || scratch[49]>8 || (scratch[50]&~3u) || scratch[51]>1
                    || ((scratch[50]&1u) && scratch[48]==1) || ((scratch[50]&2u) && !(scratch[50]&1u))
                    || (scratch[48]==0 && (!scratch[51] || scratch[49]!=0))
                    || (!scratch[51] && scratch.size()!=52)) return BIB_ENGINE_INVALID;
            }
            const BibEngineBytesV1 reply{scratch.data(),response.bytes_written,0};
            code=transport(document_backend.validate_reply(backend.context,document_backend.worker_epoch,
                &request.expected,0,request.operation,request.request_sequence,&request.payload,&reply));
            if (code) return code;
            response.disposition=1; return BIB_ENGINE_OK;
        });
        if (status) {
            response.bytes_written=0; response.handled=0;
            if (command_entered) {
                response.disposition=2;
                poisoned=true; status=BIB_ENGINE_PROCESS_EXIT_REQUIRED;
            }
        }
        response.size=sizeof(response); response.request_sequence=request.request_sequence;
        if (form && action.present && action.key.sequence==request.request_sequence) {
            action.result=response; action.status=status; action.bytes=std::move(scratch);
        }
        if (!status && response.bytes_written) std::memcpy(buffer.bytes,form?action.bytes.data():scratch.data(),response.bytes_written);
        return reject(status);
    }
    std::int32_t document_query(const BibEngineQueryV1* input, BibEngineReplyBufferV1* output,
                                 BibEngineQueryResultV1* result) {
        Gate gate(*this,true); if (!gate) return gate.status;
        if (auto status=usable()) return status;
        if (!result || result->size<sizeof(*result)) return BIB_ENGINE_INVALID;
        BibEngineQueryResultV1 response{}; response.size=sizeof(response);
        auto reject=[&](std::int32_t code) { *result=response; return code; };
        if (!input || input->size<sizeof(*input) || !output || output->size<sizeof(*output)) return reject(BIB_ENGINE_INVALID);
        auto request=*input; request.size=sizeof(request); const auto buffer=*output;
        if (overlaps(buffer.bytes,buffer.capacity,result,sizeof(*result))) return BIB_ENGINE_INVALID;
        const auto* operation=find(request.kind,true);
        if (!operation || !enabled(operation->capability)) return reject(BIB_ENGINE_UNSUPPORTED);
        if (std::memcmp(request.schema_sha256,operation->schema.data(),32) || !span_valid(request.payload,48)
            || request.payload.length!=48 || !buffer.bytes || buffer.capacity<operation->required_reply_capacity)
            return reject(BIB_ENGINE_INVALID);
        std::vector<std::uint8_t> payload,scratch;
        try { payload.assign(request.payload.data,request.payload.data+request.payload.length); }
        catch (...) { return reject(BIB_ENGINE_LIMIT); }
        const auto sequence=integer(payload.data()+32,8), nested=integer(payload.data()+40,8);
        if (!document_request_valid(payload,request.expected,sequence,true)) return reject(BIB_ENGINE_INVALID);
        if (sequence<=last_sequence) return reject(BIB_ENGINE_STALE);
        try { scratch.resize(operation->required_reply_capacity); } catch (...) { return reject(BIB_ENGINE_LIMIT); }
        request.payload.data=payload.data();
        BibEngineReplyBufferV1 scratch_buffer{sizeof(scratch_buffer),static_cast<std::uint32_t>(scratch.size()),scratch.data()};
        bool query_entered=false;
        auto status=turn([&] {
            auto checked=check_document(request.expected); if (checked) return checked;
            checked=transport(document_backend.validate_request(backend.context,document_backend.worker_epoch,
                &request.expected,1,request.kind,sequence,&request.payload));
            if (checked) return checked;
            last_sequence=sequence;
            query_entered=true;
            auto code=backend.query(backend.context,&request,&scratch_buffer,&response);
            if (code || response.size!=sizeof(response) || response.bytes_written>scratch.size()
                || !same(response.document,request.expected)) return code?code:BIB_ENGINE_INVALID;
            scratch.resize(response.bytes_written);
            if (!packet_join(scratch,request.expected,sequence,4,nested) || scratch.size()<96
                || !response.semantic_revision || response.semantic_revision!=integer(scratch.data()+88,8)) return BIB_ENGINE_INVALID;
            const BibEngineBytesV1 reply{scratch.data(),response.bytes_written,0};
            code=transport(document_backend.validate_reply(backend.context,document_backend.worker_epoch,
                &request.expected,1,request.kind,sequence,&request.payload,&reply));
            return code?code:check_document(request.expected);
        });
        if (status) {
            response.bytes_written=0; response.semantic_revision=0; response.document={};
            if (query_entered) { poisoned=true; status=BIB_ENGINE_PROCESS_EXIT_REQUIRED; }
        }
        else if (response.bytes_written) std::memcpy(buffer.bytes,scratch.data(),response.bytes_written);
        response.size=sizeof(response); return reject(status);
    }
    std::int32_t editor_command(const BibEngineCommandV1* input, BibEngineReplyBufferV1* output,
                                BibEngineCommandResultV1* result) {
        Gate gate(*this,true); if (!gate) return gate.status;
        if (auto status=usable()) return status;
        if (!result || result->size<sizeof(*result)) return BIB_ENGINE_INVALID;
        BibEngineCommandResultV1 response{}; response.size=sizeof(response);
        auto reject=[&](std::int32_t code) { *result=response; return code; };
        if (!editor_mode || !input || input->size<sizeof(*input) || !output || output->size<sizeof(*output)) return reject(BIB_ENGINE_INVALID);
        auto request=*input; request.size=sizeof(request); const auto buffer=*output;
        response.request_sequence=request.request_sequence;
        if (overlaps(buffer.bytes,buffer.capacity,result,sizeof(*result))) return BIB_ENGINE_INVALID;
        const auto* operation=find(request.operation,false);
        if (!operation || (request.operation!=BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1
            && request.operation!=BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1) || !enabled(operation->capability)) return reject(BIB_ENGINE_UNSUPPORTED);
        if (std::memcmp(request.schema_sha256,operation->schema.data(),32)
            || !span_valid(request.payload,operation->maximum_input_bytes)
            || request.payload.length>start_config.limits.maximum_command_bytes || !full_identity(request.expected)
            || !request.request_sequence || request.request_sequence>BIB_ENGINE_DOCUMENT_V2_MAX_ORDINARY_SEQUENCE
            || !buffer.bytes || buffer.capacity<operation->required_reply_capacity) return reject(BIB_ENGINE_INVALID);
        std::vector<std::uint8_t> payload,scratch;
        try { if (request.payload.length) payload.assign(request.payload.data,request.payload.data+request.payload.length); }
        catch (...) { return reject(BIB_ENGINE_LIMIT); }
        if (!editor_request_valid(payload,request.expected,editor_backend.worker_epoch,request.request_sequence,request.operation,false))
            return reject(BIB_ENGINE_INVALID);
        if (request.request_sequence<=last_sequence) return reject(BIB_ENGINE_STALE);
        // Forms metadata owns its action until ACK7. Revocation is deferred by
        // the serialized owner; it never bypasses this existing effect barrier.
        if (action.present) return reject(BIB_ENGINE_LIMIT);
        try { scratch.resize(operation->required_reply_capacity); } catch (...) { return reject(BIB_ENGINE_LIMIT); }
        request.payload.data=payload.data();
        // C8 carries inert command metadata: reject a request before asking the
        // host to enter the editor turn. The Gate remains held, and the owned
        // payload stays alive through both this preflight and the in-turn recheck.
        if (request.operation==BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1) {
            std::int32_t preflight_status{};
            try {
                preflight_status=transport(editor_backend.admit_request(backend.context,editor_backend.worker_epoch,
                    &request.expected,0,request.operation,request.request_sequence,&request.payload));
            } catch (...) {
                poisoned=true;
                return reject(BIB_ENGINE_PROCESS_EXIT_REQUIRED);
            }
            if (preflight_status) {
                if (preflight_status==BIB_ENGINE_PROCESS_EXIT_REQUIRED) poisoned=true;
                return reject(preflight_status);
            }
        }
        BibEngineReplyBufferV1 scratch_buffer{sizeof(scratch_buffer),static_cast<std::uint32_t>(scratch.size()),scratch.data()};
        bool editor_entered=false;
        auto status=turn([&] {
            auto checked=check_document(request.expected);
            // Only revoke9 may present an older same-provider document. STALE
            // grants no cleanup authority: the mandatory inert admission must
            // prove its exact previously issued, still-owned retirement target
            // and material before sequence consumption or native effect entry.
            if (checked && (request.operation!=BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1
                || checked!=BIB_ENGINE_STALE || !document_valid(request.expected))) return checked;
            checked=transport(editor_backend.admit_request(backend.context,editor_backend.worker_epoch,
                &request.expected,0,request.operation,request.request_sequence,&request.payload));
            if (checked) return checked;
            last_sequence=request.request_sequence; response.disposition=2; editor_entered=true;
            auto callback=request.operation==BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1?editor_backend.apply:editor_backend.revoke;
            auto code=callback(backend.context,editor_backend.worker_epoch,&request,&scratch_buffer,&response);
            if (code || response.size!=sizeof(response) || response.bytes_written>scratch.size()
                || response.handled>1 || response.request_sequence!=request.request_sequence) return code?code:BIB_ENGINE_INVALID;
            scratch.resize(response.bytes_written);
            if (!editor_reply_valid(scratch,request.expected,editor_backend.worker_epoch,request.request_sequence,false)) return BIB_ENGINE_INVALID;
            const BibEngineBytesV1 reply{scratch.data(),response.bytes_written,0};
            code=transport(editor_backend.validate_reply(backend.context,editor_backend.worker_epoch,
                &request.expected,0,request.operation,request.request_sequence,&request.payload,&reply));
            if (code) return code;
            response.disposition=1; return BIB_ENGINE_OK;
        });
        if (status) {
            response.bytes_written=0; response.handled=0;
            if (editor_entered) { response.disposition=2; poisoned=true; status=BIB_ENGINE_PROCESS_EXIT_REQUIRED; }
            if (poisoned) {
                editor_unknown.present=true; editor_unknown.query=false;
                editor_unknown.key=key(request,std::move(payload)); editor_unknown.bytes=std::move(scratch);
            }
        } else if (response.bytes_written) std::memcpy(buffer.bytes,scratch.data(),response.bytes_written);
        response.size=sizeof(response); response.request_sequence=request.request_sequence;
        return reject(status);
    }
    std::int32_t editor_query(const BibEngineQueryV1* input, BibEngineReplyBufferV1* output,
                              BibEngineQueryResultV1* result) {
        Gate gate(*this,true); if (!gate) return gate.status;
        if (auto status=usable()) return status;
        if (!result || result->size<sizeof(*result)) return BIB_ENGINE_INVALID;
        BibEngineQueryResultV1 response{}; response.size=sizeof(response);
        auto reject=[&](std::int32_t code) { *result=response; return code; };
        if (!editor_mode || !input || input->size<sizeof(*input) || !output || output->size<sizeof(*output)) return reject(BIB_ENGINE_INVALID);
        auto request=*input; request.size=sizeof(request); const auto buffer=*output;
        if (overlaps(buffer.bytes,buffer.capacity,result,sizeof(*result))) return BIB_ENGINE_INVALID;
        const auto* operation=find(request.kind,true);
        if (!operation || request.kind!=BIB_ENGINE_QUERY_EDITOR_PROJECTION_V1 || !enabled(operation->capability)) return reject(BIB_ENGINE_UNSUPPORTED);
        if (std::memcmp(request.schema_sha256,operation->schema.data(),32) || !span_valid(request.payload,operation->maximum_input_bytes)
            || request.payload.length>start_config.limits.maximum_query_bytes || !full_identity(request.expected)
            || !buffer.bytes || buffer.capacity<operation->required_reply_capacity) return reject(BIB_ENGINE_INVALID);
        std::vector<std::uint8_t> payload,scratch;
        try { if (request.payload.length) payload.assign(request.payload.data,request.payload.data+request.payload.length); }
        catch (...) { return reject(BIB_ENGINE_LIMIT); }
        if (payload.size()<56) return reject(BIB_ENGINE_INVALID);
        const auto sequence=integer(payload.data()+48,8);
        if (!editor_request_valid(payload,request.expected,editor_backend.worker_epoch,sequence,request.kind,true)) return reject(BIB_ENGINE_INVALID);
        if (sequence<=last_sequence) return reject(BIB_ENGINE_STALE);
        try { scratch.resize(operation->required_reply_capacity); } catch (...) { return reject(BIB_ENGINE_LIMIT); }
        request.payload.data=payload.data();
        BibEngineReplyBufferV1 scratch_buffer{sizeof(scratch_buffer),static_cast<std::uint32_t>(scratch.size()),scratch.data()};
        bool editor_entered=false;
        auto status=turn([&] {
            auto checked=check_document(request.expected); if (checked) return checked;
            checked=transport(editor_backend.admit_request(backend.context,editor_backend.worker_epoch,
                &request.expected,1,request.kind,sequence,&request.payload));
            if (checked) return checked;
            last_sequence=sequence; editor_entered=true;
            auto code=editor_backend.project(backend.context,editor_backend.worker_epoch,&request,&scratch_buffer,&response);
            if (code || response.size!=sizeof(response) || response.bytes_written>scratch.size()
                || !same(response.document,request.expected)) return code?code:BIB_ENGINE_INVALID;
            scratch.resize(response.bytes_written);
            if (!editor_reply_valid(scratch,request.expected,editor_backend.worker_epoch,sequence,true,response.semantic_revision)) return BIB_ENGINE_INVALID;
            const BibEngineBytesV1 reply{scratch.data(),response.bytes_written,0};
            code=transport(editor_backend.validate_reply(backend.context,editor_backend.worker_epoch,
                &request.expected,1,request.kind,sequence,&request.payload,&reply));
            return code?code:check_document(request.expected);
        });
        if (status) {
            response.bytes_written=0; response.semantic_revision=0; response.document={};
            if (editor_entered) { poisoned=true; status=BIB_ENGINE_PROCESS_EXIT_REQUIRED; }
            if (poisoned) {
                editor_unknown.present=true; editor_unknown.query=true;
                editor_unknown.key.expected=request.expected; editor_unknown.key.worker_epoch=editor_backend.worker_epoch;
                editor_unknown.key.sequence=sequence; editor_unknown.key.operation=request.kind;
                std::copy_n(request.schema_sha256,32,editor_unknown.key.schema.begin());
                editor_unknown.key.payload=std::move(payload); editor_unknown.bytes=std::move(scratch);
            }
        } else if (response.bytes_written) std::memcpy(buffer.bytes,scratch.data(),response.bytes_written);
        response.size=sizeof(response); return reject(status);
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
int32_t BIB_ENGINE_CALL command(const BibEngineCommandV1* q, BibEngineReplyBufferV1* b, BibEngineCommandResultV1* r) {
    auto* p=runtime(); if (!p) return BIB_ENGINE_LIMIT;
    if (p->editor_mode && q && q->size>=sizeof(*q) && (q->operation==BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1
        || q->operation==BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1)) return p->editor_command(q,b,r);
    return p->document_mode?p->document_command(q,b,r):p->dispatch(q,b,r,false);
}
int32_t BIB_ENGINE_CALL query(const BibEngineQueryV1* q, BibEngineReplyBufferV1* b, BibEngineQueryResultV1* r) {
    auto* p=runtime(); if (!p) return BIB_ENGINE_LIMIT;
    if (p->editor_mode && q && q->size>=sizeof(*q) && q->kind==BIB_ENGINE_QUERY_EDITOR_PROJECTION_V1) return p->editor_query(q,b,r);
    return p->document_mode?p->document_query(q,b,r):p->dispatch(q,b,r,true);
}
int32_t BIB_ENGINE_CALL deliver(const BibEngineDocumentV1* d, const BibEngineBytesV1* b) { auto* p=runtime(); return p ? p->deliver(d,b) : BIB_ENGINE_LIMIT; }
uint32_t BIB_ENGINE_CALL ack(const BibEngineDocumentV1* d) { auto* p=runtime(); return p ? p->ack(d) : service_unavailable; }
int32_t BIB_ENGINE_CALL dispose(uint64_t a, uint64_t g) { auto* p=runtime(); return p ? p->dispose(a,g) : BIB_ENGINE_LIMIT; }
} // namespace

std::int32_t bind_engine_private(const EnginePrivateV1& binding) noexcept {
    auto* p = runtime(); if (!p) return BIB_ENGINE_LIMIT;
    try { return p->bind(binding); } catch (...) { return BIB_ENGINE_INVALID; }
}
std::int32_t bind_engine_document_private(const EnginePrivateV1& binding, const EngineDocumentPrivateV1& document) noexcept {
    auto* p=runtime(); if (!p) return BIB_ENGINE_LIMIT;
    try { return p->bind(binding,&document); } catch (...) { return BIB_ENGINE_INVALID; }
}
std::int32_t bind_engine_editor_private(const EnginePrivateV1& binding, const EngineDocumentPrivateV1& document,
                                       const EngineEditorPrivateV1& editor) noexcept {
    auto* p=runtime(); if (!p) return BIB_ENGINE_LIMIT;
    try { return p->bind(binding,&document,&editor); } catch (...) { return BIB_ENGINE_INVALID; }
}
} // namespace bib::provider_candidate

extern "C" BIB_ENGINE_EXPORT int32_t BIB_ENGINE_CALL bib_engine_get_provider_v1(uint32_t major, uint32_t minor,
    uint32_t capacity, BibEngineProviderV1* output) {
    using namespace bib::provider_candidate;
    if (!output || major != BIB_ENGINE_ABI_MAJOR || capacity < sizeof(BibEngineProviderV1)) return BIB_ENGINE_INVALID;
    auto* p = runtime(); if (!p) return BIB_ENGINE_LIMIT;
    Runtime::Gate gate(*p, false); if (!gate) return gate.status;
    if (!p->bound) return BIB_ENGINE_UNSUPPORTED;
    if (p->document_mode && p->poisoned) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    if (p->document_mode && minor<BIB_ENGINE_DOCUMENT_V2_ABI_MINOR) return BIB_ENGINE_UNSUPPORTED;
    BibEngineProviderV1 table{}; table.size=sizeof(table); table.abi_major=BIB_ENGINE_ABI_MAJOR;
    table.abi_minor=p->document_mode?BIB_ENGINE_DOCUMENT_V2_ABI_MINOR:0;
    table.build=p->backend.build; table.limits=p->backend.limits;
    table.start=start; table.advance=advance; table.current_document=current; table.command=command; table.query=query;
    table.deliver_services=deliver; table.collect_service_ack=ack; table.dispose_retired_service_document=dispose;
    *output=table;
    return BIB_ENGINE_OK;
}
