// SPDX-License-Identifier: CC0-1.0
// Explicit editor2035 C-table guard fixtures with an inert private backend.
// The shared binary codec supplies positive wire values; no WebCore, retained
// SDK, browser, native-input facility or production runtime is exercised.
#include "EnginePrivate.hpp"
#include "engine_editor_pins.hpp"
#include "native_editor_codec.hpp"

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
namespace native = foundation::ui::native_editor;
namespace wire = native::codec;
namespace pins = foundation::appended::engine_editor;

namespace {
unsigned assertions{};
// Guard deliberately catches backend exceptions. Persist a failed fixture
// assertion so an expected terminal return cannot hide the assertion that
// produced it. The next outer CHECK, and main's final check, report it again.
std::string first_assertion_failure;
#define CHECK(x) do { ++assertions; if (!(x) && first_assertion_failure.empty()) first_assertion_failure = std::string("failed: ") + #x + " line " + std::to_string(__LINE__); if (!first_assertion_failure.empty()) throw std::runtime_error(first_assertion_failure); } while (false)
using Bytes = std::vector<std::uint8_t>;
using Digest = std::array<std::uint8_t, 32>;
constexpr std::uint64_t worker_epoch = 55;
constexpr std::uint64_t maximum_ordinary = UINT64_MAX - UINT64_C(1);
constexpr std::uint32_t reply_capacity = BIB_ENGINE_EDITOR_REPLY_CAPACITY;
BibEngineProviderV1 provider{};
bool untouched(const Bytes& bytes) {
    return std::all_of(bytes.begin(),bytes.end(),[](std::uint8_t byte) { return byte == 0xa5; });
}

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
constexpr auto document_schema = digest(BIB_ENGINE_DOCUMENT_V2_SCHEMA_SHA256_HEX);
constexpr auto ack_schema = digest(BIB_ENGINE_DOCUMENT_V2_ACK_SCHEMA_SHA256_HEX);
constexpr auto document_extension = digest("7b047bae4d0072ef156ea94ba637566d563fea3a95d43c4c6314afc919b1d626");
constexpr auto document_contract = digest("aba7800e6aab1898f3614f0b1ac53e59b9f622bf1e9d3a413f50d672a3662298");
constexpr auto document_catalog = digest("6e555d4c3bb71fbc965e1ca49671fab64d744913e18f45b9ba273505e0c6bcf5");
constexpr auto physical_catalog = digest("d244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b");
constexpr std::array<Operation, 3> physical_operations{{
    {1,160,16,16,digest("86b7baad1c95bfb8de3e6b7a9a7c433b528278bbcf84199ca0b2b4ee6134dbc9")},
    {3,32,16,64,digest("eef60cda2aa7b791641b0e5082d551ec37c10b8d92ca4cc71f13be0af45321d9")},
    {5,80,16,128,digest("6a15d0e2f814564ce263824dd782335bb327b886e982aefec32476a29b0fd4a3")},
}};

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
wire::WireTarget target(BibEngineDocumentV1 document, std::uint64_t sequence) {
    return {worker_epoch,document.application_instance,document.document_sequence,document.service_generation,sequence};
}
void check_target(const wire::WireTarget& value, BibEngineDocumentV1 document, std::uint64_t sequence) {
    CHECK(value == target(document,sequence));
}
native::NativeProjection projection() {
    native::NativeProjection result;
    result.identity = {{"editor",3},11,4,5,6}; result.editor_revision = UINT64_C(9007199254740993);
    result.surrounding = "abc"; result.selection = {3,3}; result.mapping_id = 1; result.frame_id = 2;
    result.readback_attested = true; result.caret = {1,2,3,4}; result.input_purpose = "text";
    result.retire = native::NativeRetireMaterial{71,1,6,0}; return result;
}
native::Basis basis() {
    const auto p = projection();
    return {31,p.identity,p.editor_revision,p.surrounding,p.selection,p.backward,p.composition};
}
Bytes observation(BibEngineDocumentV1 document, std::uint64_t sequence) {
    native::NativeRequest request; request.resolved = projection();
    request.packet.session = 8; request.packet.basis = basis();
    auto& observed = request.packet.observation;
    observed.id = 1; observed.kind = native::Kind::key; observed.authority = native::Authority::native;
    observed.group = 1; observed.before = {"abc",3,3,native::Direction::none,{3,3},3};
    observed.after = observed.before; native::KeyData key;
    key.transition.key = "a"; key.transition.code = "KeyA"; observed.data = key;
    Bytes result; CHECK(wire::encode_native_request({target(document,sequence),request},result)); return result;
}
Bytes revocation(BibEngineDocumentV1 document, std::uint64_t sequence, bool observed = false) {
    native::NativeRevocationRequest request; request.material = *projection().retire; request.identity = projection().identity;
    if (observed) {
        native::Revocation value; value.basis = basis(); value.incarnation = 23; value.reason = "trusted owner retirement";
        native::KeyData key; key.transition.key = "a"; key.transition.code = "KeyA"; value.held_keys.push_back(key);
        request.observed = value;
    }
    Bytes result; CHECK(wire::encode_revocation({target(document,sequence),request},result)); return result;
}
Bytes projection_query(BibEngineDocumentV1 document, std::uint64_t sequence) {
    Bytes result; CHECK(wire::encode_projection_query({target(document,sequence),projection().identity,1},result)); return result;
}
Bytes projection_reply(BibEngineDocumentV1 document, std::uint64_t sequence, std::uint64_t revision,
                       wire::ProjectionReply::State state = wire::ProjectionReply::State::available) {
    wire::ProjectionReply reply; reply.state = state; reply.observation_revision = revision;
    reply.target = target(document,sequence); reply.identity = projection().identity; reply.readback_attested = true;
    if (state == wire::ProjectionReply::State::available) reply.projection = projection();
    Bytes result; CHECK(wire::encode_projection_reply(reply,result)); return result;
}
Bytes native_result(BibEngineDocumentV1 document, std::uint64_t sequence, bool revoke, bool unknown = false) {
    native::NativeResult result;
    if (!unknown) {
        result.outcome = native::Outcome::applied; result.projection = projection();
        result.observation_revision = 93; result.readback_identity = projection().identity; result.readback_attested = true;
        result.retire = projection().retire;
        if (revoke) result.retired = projection().retire;
        else result.key_dispatch_attested = true;
    }
    Bytes bytes; CHECK(wire::encode_native_result({target(document,sequence),result},bytes)); return bytes;
}
Bytes document_envelope(unsigned kind, BibEngineDocumentV1 document, std::uint64_t sequence, std::uint64_t nested) {
    Bytes bytes{'N','D','V','2',2,0,static_cast<std::uint8_t>(kind),0};
    put(bytes,document.application_instance,8); put(bytes,document.service_generation,8); put(bytes,document.document_sequence,8);
    put(bytes,sequence,8); put(bytes,nested,8); return bytes;
}
Bytes form_action(BibEngineDocumentV1 document, std::uint64_t sequence) {
    auto bytes = document_envelope(2,document,sequence,0); put(bytes,0,1);
    put(bytes,document.application_instance,8); put(bytes,document.service_generation,8); put(bytes,9,8); put(bytes,3,8);
    CHECK(bytes.size() == 81); return bytes;
}
Bytes form_result(BibEngineDocumentV1 document, std::uint64_t sequence) {
    auto bytes = document_envelope(5,document,sequence,0);
    put(bytes,1,1); put(bytes,6,1); put(bytes,0,1); put(bytes,0,1); return bytes;
}
Bytes document_publication(BibEngineDocumentV1 document, std::uint64_t sequence, std::uint64_t nested) {
    auto bytes = document_envelope(4,document,sequence,nested);
    put(bytes,document.application_instance,8); put(bytes,document.service_generation,8); put(bytes,document.document_sequence,8);
    put(bytes,document.application_instance,8); put(bytes,document.service_generation,8); put(bytes,9,8);
    put(bytes,0,1); put(bytes,1,8); put(bytes,0,8);
    put(bytes,0,4); put(bytes,0,4); put(bytes,0,4); put(bytes,0,4); put(bytes,0,4); put(bytes,0,1);
    CHECK(bytes.size() == 134); return bytes;
}

struct Counts {
    int enters{}, leaves{}, currents{}, old_commands{}, old_queries{}, document_admits{}, document_replies{}, retirements{};
    int form_preflights{}, form_in_turn{};
    int admits{}, reply_validations{}, projects{}, applies{}, revocations{}, advances{}, services{}, collections{}, disposals{};
    bool operator==(const Counts&) const = default;
};
// A separately exercised provider-owned lease. Its authority originates in a
// checked projection reply and keeps its original document after navigation.
struct HistoricalLease {
    wire::WireTarget source;
    native::NativeRetireMaterial material;
    native::Identity identity;
    bool active = true;
};
struct Fake {
    Counts counts;
    std::optional<HistoricalLease> historical_lease;
    BibEngineDocumentV1 document{44,11,7};
    std::uint32_t enter_status{};
    int admit_status{}, effect_status{}, reply_status{};
    std::uint64_t query_revision{93};
    wire::ProjectionReply::State query_state{wire::ProjectionReply::State::available};
    bool in_turn{}, pending_native{}, throw_effect{}, throw_admit{}, throw_admit_second{}, throw_reply{}, throw_leave{}, navigate_query{}, unknown{};
    bool invalidate_on_enter{};
    int admit_preflights{}, admit_in_turn{};
    bool wrong_document{}, wrong_sequence{}, wrong_revision{}, malformed_header{}, malformed_target{}, malformed_body{}, bad_size{}, overflow_reply{}, bad_handled{};
    bool reenter{};
    std::uint8_t* mutate{};
    std::uint8_t observed_first{};
    int nested_enter{99}, nested_leave{99}, nested_admit{99}, nested_reply{99}, nested_effect{99}, threaded{99};
    Bytes retained_form;
    static int nested() { BibEngineDocumentV1 d{}; return provider.current_document(44,&d); }
    static void BIB_ENGINE_CALL wake(void*) {}
    static void BIB_ENGINE_CALL timer(void*,double,std::uint32_t) {}
    static void BIB_ENGINE_CALL damage(void*,const BibEngineDamageV1*) {}
    static void BIB_ENGINE_CALL persistence(void*,const BibEngineBytesV1*) {}
    static std::uint32_t BIB_ENGINE_CALL enter(void* context) {
        auto& f = *static_cast<Fake*>(context); ++f.counts.enters;
        CHECK(!f.in_turn);
        if (f.mutate) *f.mutate = 91;
        if (f.invalidate_on_enter) f.admit_status = BIB_ENGINE_STALE;
        if (f.reenter) f.nested_enter = nested();
        if (!f.enter_status) f.in_turn = true;
        return f.enter_status;
    }
    static void BIB_ENGINE_CALL leave(void* context) {
        auto& f = *static_cast<Fake*>(context); ++f.counts.leaves;
        CHECK(f.in_turn); f.in_turn = false;
        if (f.reenter) f.nested_leave = nested();
        if (f.throw_leave) throw std::runtime_error("uncertain leave");
    }
    static std::uint64_t BIB_ENGINE_CALL begin_service(void*,const BibEngineDocumentV1*) { return 7; }
    static void BIB_ENGINE_CALL close_service(void*,std::uint64_t) {}
    static std::uint32_t BIB_ENGINE_CALL submit(void*,std::uint64_t,const BibEngineBytesV1*,std::uint32_t) { return 0; }
    static std::uint32_t BIB_ENGINE_CALL cancel(void*,std::uint64_t,std::uint64_t) { return 0; }
    static std::uint32_t BIB_ENGINE_CALL stage(void*,std::uint64_t,std::uint64_t) { return 0; }
    static std::int32_t BIB_ENGINE_CALL resource(void*,const BibEngineDocumentV1*,BibEngineResourceEpochV1*) { return BIB_ENGINE_UNSUPPORTED; }
    static void BIB_ENGINE_CALL retire_resource(void*,std::uint64_t) {}
    static std::int32_t preflight(void*,const BibEngineStartV1*) { return 0; }
    static std::int32_t install(void* context,const BibEngineHostV1*,const BibEngineStartV1*,std::uint64_t) {
        CHECK(static_cast<Fake*>(context)->in_turn); return 0;
    }
    static std::int32_t start(void* context,const BibEngineHostV1*,const BibEngineStartV1*,std::uint64_t instance) {
        auto& f = *static_cast<Fake*>(context); CHECK(f.in_turn && instance == f.document.application_instance); return 0;
    }
    static std::int32_t advance(void* context,const BibEngineAdvanceV1*) {
        ++static_cast<Fake*>(context)->counts.advances; return 0;
    }
    static std::int32_t current(void* context,std::uint64_t,BibEngineDocumentV1* value) {
        auto& f = *static_cast<Fake*>(context); ++f.counts.currents; *value = f.document; return 0;
    }
    static std::int32_t deliver(void* context,const BibEngineDocumentV1*,const BibEngineBytesV1*) {
        ++static_cast<Fake*>(context)->counts.services; return 0;
    }
    static std::uint32_t collect(void* context,const BibEngineDocumentV1*) {
        ++static_cast<Fake*>(context)->counts.collections; return 0;
    }
    static std::int32_t dispose(void* context,std::uint64_t,std::uint64_t) {
        ++static_cast<Fake*>(context)->counts.disposals; return 0;
    }
    static std::int32_t document_admit(void* context,std::uint64_t worker,const BibEngineDocumentV1*,std::uint32_t domain,
                                     std::uint32_t operation,std::uint64_t,const BibEngineBytesV1*) {
        auto& f = *static_cast<Fake*>(context); CHECK(worker == worker_epoch);
        if (domain == 0 && operation == BIB_ENGINE_COMMAND_FORM_ACTION_V2) {
            if (f.in_turn) ++f.counts.form_in_turn;
            else ++f.counts.form_preflights;
        } else CHECK(f.in_turn);
        ++f.counts.document_admits;
        CHECK((domain == 0 && (operation == 1 || operation == 3 || operation == 5 || operation == 6))
            || (domain == 1 && operation == 3)); return 0;
    }
    static std::int32_t document_reply(void* context,std::uint64_t worker,const BibEngineDocumentV1*,std::uint32_t,
                                     std::uint32_t,std::uint64_t,const BibEngineBytesV1*,const BibEngineBytesV1*) {
        auto& f = *static_cast<Fake*>(context); CHECK(f.in_turn && worker == worker_epoch); ++f.counts.document_replies; return 0;
    }
    static std::int32_t retire_form(void* context,std::uint64_t worker,const BibEngineCommandV1* action) {
        auto& f = *static_cast<Fake*>(context); CHECK(!f.in_turn && worker == worker_epoch && action && action->operation == 6);
        CHECK(action->payload.length == f.retained_form.size()
            && std::equal(f.retained_form.begin(),f.retained_form.end(),action->payload.data));
        ++f.counts.retirements; f.retained_form.clear(); return 0;
    }
    static std::int32_t old_command(void* context,const BibEngineCommandV1* request,BibEngineReplyBufferV1* buffer,
                                    BibEngineCommandResultV1* result) {
        auto& f = *static_cast<Fake*>(context); CHECK(f.in_turn); ++f.counts.old_commands;
        if (request->operation != 6) { CHECK(request->operation == 1 || request->operation == 3 || request->operation == 5); return 0; }
        CHECK(f.counts.form_preflights == 1 && f.counts.form_in_turn == 1);
        f.retained_form.assign(request->payload.data,request->payload.data+request->payload.length);
        const auto bytes = form_result(request->expected,request->request_sequence);
        CHECK(bytes.size() <= buffer->capacity); std::copy(bytes.begin(),bytes.end(),buffer->bytes);
        result->bytes_written = static_cast<std::uint32_t>(bytes.size()); return 0;
    }
    static std::int32_t old_query(void* context,const BibEngineQueryV1* request,BibEngineReplyBufferV1* buffer,
                                 BibEngineQueryResultV1* result) {
        auto& f = *static_cast<Fake*>(context); CHECK(f.in_turn && request->kind == 3); ++f.counts.old_queries;
        const auto bytes = document_publication(request->expected,get(request->payload.data+32,8),get(request->payload.data+40,8));
        CHECK(bytes.size() <= buffer->capacity); std::copy(bytes.begin(),bytes.end(),buffer->bytes);
        result->bytes_written = static_cast<std::uint32_t>(bytes.size()); result->document = f.document; result->semantic_revision = 9; return 0;
    }
    static std::int32_t admit(void* context,std::uint64_t worker,const BibEngineDocumentV1* expected,std::uint32_t domain,
                             std::uint32_t operation,std::uint64_t sequence,const BibEngineBytesV1* payload) {
        auto& f = *static_cast<Fake*>(context); CHECK(worker == worker_epoch && expected && payload && !payload->reserved);
        ++f.counts.admits;
        if (f.in_turn) ++f.admit_in_turn;
        else { ++f.admit_preflights; CHECK(domain == 0 && operation == 8); }
        f.observed_first = payload->data[0];
        if (f.reenter) f.nested_admit = nested();
        if (f.throw_admit || (f.throw_admit_second && f.counts.admits==2)) throw std::runtime_error("uncertain inert admission");
        if (f.admit_status) return f.admit_status;
        const std::span<const std::uint8_t> bytes(payload->data,payload->length);
        if (domain == 1) {
            CHECK(operation == 4); wire::ProjectionQuery query;
            if (!wire::decode_projection_query(bytes,query)) return BIB_ENGINE_INVALID;
            check_target(query.target,*expected,sequence);
            if (query.identity != projection().identity || query.mapping_id != 1) return BIB_ENGINE_STALE;
        } else if (operation == 8) {
            CHECK(domain == 0);
            wire::NativeRequestEnvelope request;
            if (!wire::decode_native_request(bytes,request)) return BIB_ENGINE_INVALID;
            check_target(request.target,*expected,sequence);
            if (request.request.resolved != projection() || request.request.packet.basis != basis()) return BIB_ENGINE_STALE;
        } else {
            CHECK(domain == 0 && operation == 9); wire::RevocationEnvelope request;
            if (!wire::decode_revocation(bytes,request)) return BIB_ENGINE_INVALID;
            check_target(request.target,*expected,sequence);
            if (request.request.material != *projection().retire || request.request.identity != projection().identity) return BIB_ENGINE_STALE;
        }
        if (f.pending_native && operation != 9) return BIB_ENGINE_LIMIT;
        return 0;
    }
    static std::int32_t validate_reply(void* context,std::uint64_t worker,const BibEngineDocumentV1* expected,std::uint32_t domain,
                                      std::uint32_t operation,std::uint64_t sequence,const BibEngineBytesV1* payload,const BibEngineBytesV1* reply) {
        auto& f = *static_cast<Fake*>(context); CHECK(f.in_turn && worker == worker_epoch && expected && payload && reply && !reply->reserved);
        ++f.counts.reply_validations;
        if (f.reenter) f.nested_reply = nested();
        if (f.throw_reply) throw std::runtime_error("uncertain deep reply validation");
        const std::span<const std::uint8_t> bytes(reply->data,reply->length);
        if (domain == 1) {
            CHECK(operation == 4); wire::ProjectionReply value;
            if (!wire::decode_projection_reply(bytes,value)) return BIB_ENGINE_INVALID;
            check_target(value.target,*expected,sequence);
            CHECK(value.readback_attested && value.observation_revision == f.query_revision);
        } else {
            CHECK(domain == 0 && (operation == 8 || operation == 9)); wire::NativeResultEnvelope value;
            if (!wire::decode_native_result(bytes,value)) return BIB_ENGINE_INVALID;
            check_target(value.target,*expected,sequence);
            // A structurally valid native unknown is still terminal. Unlike the
            // NDV2 form lane, it cannot be accepted as a normal inner result.
            if (value.result.outcome == native::Outcome::unknown) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
            CHECK(value.result.readback_attested && value.result.observation_revision == 93);
            if (operation == 9) CHECK(value.result.retired == projection().retire);
        }
        return f.reply_status;
    }
    static void corrupt(Fake& f,Bytes& bytes,bool query) {
        if (f.malformed_header) bytes[0] ^= 1;
        if (f.malformed_target) bytes[query ? 24 : 16] ^= 1;
        if (f.malformed_body) { bytes.push_back(0); overwrite(bytes,12,bytes.size(),4); }
    }
    static std::int32_t project(void* context,std::uint64_t worker,const BibEngineQueryV1* request,
                                BibEngineReplyBufferV1* buffer,BibEngineQueryResultV1* result) {
        auto& f = *static_cast<Fake*>(context); CHECK(f.in_turn && worker == worker_epoch && request->kind == 4); ++f.counts.projects;
        if (f.reenter) f.nested_effect = nested();
        if (f.throw_effect) throw std::runtime_error("uncertain projection");
        const auto revision = f.query_revision ? f.query_revision : 93;
        auto bytes = projection_reply(request->expected,get(request->payload.data+48,8),revision,f.query_state); corrupt(f,bytes,true);
        CHECK(bytes.size() <= buffer->capacity); std::copy(bytes.begin(),bytes.end(),buffer->bytes);
        result->bytes_written = f.overflow_reply ? buffer->capacity+1 : static_cast<std::uint32_t>(bytes.size());
        result->document = f.document; if (f.wrong_document) ++result->document.document_sequence;
        result->semantic_revision = f.query_revision; if (f.wrong_revision) ++result->semantic_revision;
        if (f.bad_size) --result->size;
        if (f.navigate_query) ++f.document.document_sequence;
        return f.effect_status;
    }
    static std::int32_t effect(void* context,std::uint64_t worker,const BibEngineCommandV1* request,
                               BibEngineReplyBufferV1* buffer,BibEngineCommandResultV1* result,bool revoke) {
        auto& f = *static_cast<Fake*>(context); CHECK(f.in_turn && worker == worker_epoch && request->operation == (revoke ? 9u : 8u));
        if (revoke) ++f.counts.revocations; else ++f.counts.applies;
        if (f.reenter) {
            f.nested_effect = nested();
            std::thread wrong([&] { f.threaded = nested(); }); wrong.join();
        }
        if (f.throw_effect) throw std::runtime_error("uncertain native effect");
        auto bytes = native_result(request->expected,request->request_sequence,revoke,f.unknown); corrupt(f,bytes,false);
        CHECK(bytes.size() <= buffer->capacity); std::copy(bytes.begin(),bytes.end(),buffer->bytes);
        result->bytes_written = f.overflow_reply ? buffer->capacity+1 : static_cast<std::uint32_t>(bytes.size());
        if (f.wrong_sequence) ++result->request_sequence;
        if (f.bad_size) --result->size;
        if (f.bad_handled) result->handled = 2;
        return f.effect_status;
    }
    static std::int32_t apply(void* c,std::uint64_t w,const BibEngineCommandV1* q,BibEngineReplyBufferV1* b,BibEngineCommandResultV1* r) {
        return effect(c,w,q,b,r,false);
    }
    static std::int32_t revoke(void* c,std::uint64_t w,const BibEngineCommandV1* q,BibEngineReplyBufferV1* b,BibEngineCommandResultV1* r) {
        return effect(c,w,q,b,r,true);
    }
};

struct Fixture {
    Fake fake;
    std::array<Operation,7> commands{{physical_operations[0],physical_operations[1],physical_operations[2],
        {6,6246,reply_capacity,1024,document_schema},{7,8,16,1024,ack_schema},
        {8,BIB_ENGINE_EDITOR_MAX_WIRE_BYTES,reply_capacity,BIB_ENGINE_CAP_COMPOSITION_V1,pins::kSchema},
        {9,BIB_ENGINE_EDITOR_MAX_WIRE_BYTES,reply_capacity,BIB_ENGINE_CAP_COMPOSITION_V1,pins::kSchema}}};
    std::array<Operation,2> queries{{{3,48,reply_capacity,512,document_schema},
        {4,BIB_ENGINE_EDITOR_MAX_QUERY_BYTES,reply_capacity,BIB_ENGINE_CAP_COMPOSITION_V1,pins::kSchema}}};
    EnginePrivateV1 backend{};
    EngineDocumentPrivateV1 document_backend{};
    EngineEditorPrivateV1 editor_backend{};
    BibEngineHostV1 host{};
    BibEngineStartV1 config{};
    std::string url = "app://"+std::string(64,'a')+"/web/index.html";
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
        backend.build.fixed_viewport_width = 800; backend.build.fixed_viewport_height = 600;
        backend.build.capabilities = BIB_ENGINE_EDITOR_CAPABILITIES;
        std::copy(pins::kContractSha256.begin(),pins::kContractSha256.end(),backend.build.contract_header_sha256);
        backend.build.build_identity_sha256[0] = 1; backend.build.source_recipe_sha256[0] = 2;
        backend.limits = {sizeof(BibEngineLimitsV1),BIB_ENGINE_EDITOR_MAX_WIRE_BYTES,BIB_ENGINE_EDITOR_MAX_QUERY_BYTES,
            reply_capacity,1048576,4,8,0,1048576,4194304};
        backend.context = &fake; backend.commands = commands.data(); backend.command_count = commands.size();
        backend.queries = queries.data(); backend.query_count = queries.size();
        backend.preflight = Fake::preflight; backend.start = Fake::start; backend.advance = Fake::advance;
        backend.current_document = Fake::current; backend.command = Fake::old_command; backend.query = Fake::old_query;
        backend.deliver_services = Fake::deliver; backend.collect_service_ack = Fake::collect;
        backend.dispose_retired_service_document = Fake::dispose; backend.install_resources = Fake::install;
        document_backend.size = sizeof(document_backend); document_backend.version = document_private_interface_version;
        document_backend.profile = document_physical_profile; document_backend.worker_epoch = worker_epoch;
        document_backend.base_header_sha256 = contract_header_sha256;
        document_backend.extension_header_sha256 = document_extension; document_backend.contract_sha256 = document_contract;
        document_backend.catalog_sha256 = document_catalog; document_backend.physical_catalog_sha256 = physical_catalog;
        document_backend.validate_request = Fake::document_admit; document_backend.validate_reply = Fake::document_reply;
        document_backend.retire_action_metadata = Fake::retire_form;
        editor_backend.size = sizeof(editor_backend); editor_backend.version = editor_private_interface_version;
        editor_backend.worker_epoch = worker_epoch; editor_backend.editor_header_sha256 = pins::kHeaderSha256;
        editor_backend.contract_sha256 = pins::kContractSha256; editor_backend.catalog_sha256 = pins::kCatalogSha256;
        editor_backend.schema_sha256 = pins::kSchema; editor_backend.admit_request = Fake::admit;
        editor_backend.validate_reply = Fake::validate_reply; editor_backend.project = Fake::project;
        editor_backend.apply = Fake::apply; editor_backend.revoke = Fake::revoke;
        host.size = sizeof(host); host.abi_major = 1; host.context = &fake; host.wake = Fake::wake; host.replace_timer_ms = Fake::timer;
        host.damage = Fake::damage; host.persistence = Fake::persistence; host.enter_engine = Fake::enter; host.leave_engine = Fake::leave;
        host.begin_service_document = Fake::begin_service; host.close_service_document = Fake::close_service;
        host.submit_service = Fake::submit; host.cancel_service = Fake::cancel; host.stage_service_ack = Fake::stage;
        host.begin_resource_epoch = Fake::resource; host.retire_resource_epoch = Fake::retire_resource;
        config.size = sizeof(config); config.required_capabilities = backend.build.capabilities; config.limits = backend.limits;
        config.entry_url = {reinterpret_cast<const std::uint8_t*>(url.data()),static_cast<std::uint32_t>(url.size()),0};
        std::fill(std::begin(config.application_package_sha256),std::end(config.application_package_sha256),0xaa);
    }
    int bind_status() { return bind_engine_editor_private(backend,document_backend,editor_backend); }
    void bind() {
        CHECK(bind_status() == BIB_ENGINE_OK); CHECK(bib_engine_get_provider_v1(1,1,sizeof(provider),&provider) == BIB_ENGINE_OK);
        CHECK(provider.abi_minor == 1 && provider.build.capabilities == BIB_ENGINE_EDITOR_CAPABILITIES);
    }
    void start() {
        BibEngineStartResultV1 result{sizeof(result),99,99}; CHECK(provider.start(&host,&config,&result) == BIB_ENGINE_OK);
        CHECK(result.phase == BIB_ENGINE_START_READY && result.application_instance == backend.application_instance);
        CHECK(fake.counts.enters == 1 && fake.counts.leaves == 1 && !fake.in_turn);
    }
};
struct Command {
    Bytes payload;
    Bytes output = Bytes(reply_capacity,0xa5);
    BibEngineCommandV1 request{};
    BibEngineReplyBufferV1 buffer{};
    BibEngineCommandResultV1 result{};
    Command(BibEngineDocumentV1 document,std::uint64_t sequence = 1,std::uint32_t operation = 8)
        : payload(operation == 9 ? revocation(document,sequence) : observation(document,sequence)) {
        request.size = sizeof(request); request.operation = operation; request.expected = document; request.request_sequence = sequence;
        std::copy(pins::kSchema.begin(),pins::kSchema.end(),request.schema_sha256); buffer = {sizeof(buffer),reply_capacity,output.data()};
    }
    void form() { request.operation = 6; payload = form_action(request.expected,request.request_sequence);
        std::copy(document_schema.begin(),document_schema.end(),request.schema_sha256); }
    void ack(std::uint64_t original) { request.operation = 7; payload.clear(); put(payload,original,8); buffer.capacity = 16;
        std::copy(ack_schema.begin(),ack_schema.end(),request.schema_sha256); }
    void physical(std::size_t index) {
        const auto& operation = physical_operations[index]; request.operation = operation.kind;
        payload.assign(operation.maximum_input_bytes,0); payload[0] = static_cast<std::uint8_t>(operation.kind); buffer.capacity = 16;
        std::copy(operation.schema.begin(),operation.schema.end(),request.schema_sha256);
    }
    int run() {
        request.payload = {payload.data(),static_cast<std::uint32_t>(payload.size()),request.payload.reserved};
        result = {sizeof(result),99,99,99,99}; return provider.command(&request,&buffer,&result);
    }
    void completed() const {
        CHECK(result.disposition == 1 && result.request_sequence == request.request_sequence && result.handled == 0);
        wire::NativeResultEnvelope value;
        CHECK(wire::decode_native_result(std::span<const std::uint8_t>(output.data(),result.bytes_written),value));
        check_target(value.target,request.expected,request.request_sequence); CHECK(value.result.outcome == native::Outcome::applied);
    }
    void rejected() const { CHECK(result.disposition == 0 && result.bytes_written == 0 && result.handled == 0 && untouched(output)); }
    void unknown() const { CHECK(result.disposition == 2 && result.bytes_written == 0 && result.handled == 0
        && result.request_sequence == request.request_sequence && untouched(output)); }
};
struct Query {
    Bytes payload;
    Bytes output = Bytes(reply_capacity,0xa5);
    BibEngineQueryV1 request{};
    BibEngineReplyBufferV1 buffer{};
    BibEngineQueryResultV1 result{};
    Query(BibEngineDocumentV1 document,std::uint64_t sequence = 1) : payload(projection_query(document,sequence)) {
        request.size = sizeof(request); request.kind = 4; request.expected = document;
        std::copy(pins::kSchema.begin(),pins::kSchema.end(),request.schema_sha256); buffer = {sizeof(buffer),reply_capacity,output.data()};
    }
    int run() {
        request.payload = {payload.data(),static_cast<std::uint32_t>(payload.size()),request.payload.reserved};
        result = {sizeof(result),99,{91,92,93},99}; return provider.query(&request,&buffer,&result);
    }
    void completed(wire::ProjectionReply::State state = wire::ProjectionReply::State::available) const {
        CHECK(same(result.document,request.expected) && result.semantic_revision == 93);
        wire::ProjectionReply value;
        CHECK(wire::decode_projection_reply(std::span<const std::uint8_t>(output.data(),result.bytes_written),value));
        check_target(value.target,request.expected,get(payload.data()+48,8)); CHECK(value.state == state && value.readback_attested);
    }
    void rejected() const { CHECK(result.bytes_written == 0 && result.semantic_revision == 0
        && same(result.document,{}) && untouched(output)); }
};

void terminal_no_exports(Fixture& f) {
    const auto counts = f.fake.counts;
    Command command(f.fake.document,20); CHECK(command.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED);
    CHECK(command.result.disposition == 99 && command.result.bytes_written == 99 && untouched(command.output));
    Command revoke(f.fake.document,21,9); CHECK(revoke.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED);
    CHECK(revoke.result.disposition == 99 && revoke.result.bytes_written == 99 && untouched(revoke.output));
    Command form(f.fake.document,22); form.form(); CHECK(form.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED);
    CHECK(form.result.disposition == 99 && untouched(form.output));
    Command ack(f.fake.document,23); ack.ack(22); CHECK(ack.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED);
    CHECK(ack.result.disposition == 99 && untouched(ack.output));
    Query query(f.fake.document,24); CHECK(query.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED);
    CHECK(query.result.bytes_written == 99 && query.result.semantic_revision == 99 && untouched(query.output));
    BibEngineProviderV1 untouched{}; untouched.size = 17;
    CHECK(bib_engine_get_provider_v1(1,1,sizeof(untouched),&untouched) == BIB_ENGINE_PROCESS_EXIT_REQUIRED && untouched.size == 17);
    BibEngineDocumentV1 value{91,92,93}; CHECK(provider.current_document(f.fake.document.application_instance,&value) == BIB_ENGINE_PROCESS_EXIT_REQUIRED);
    CHECK(same(value,{91,92,93}));
    BibEngineAdvanceV1 advance{sizeof(advance),0,f.fake.document.application_instance}; CHECK(provider.advance(&advance) == BIB_ENGINE_PROCESS_EXIT_REQUIRED);
    const BibEngineBytesV1 services{}; CHECK(provider.deliver_services(&f.fake.document,&services) == BIB_ENGINE_PROCESS_EXIT_REQUIRED);
    CHECK(provider.collect_service_ack(&f.fake.document) == 2);
    CHECK(provider.dispose_retired_service_document(f.fake.document.application_instance,f.fake.document.service_generation) == BIB_ENGINE_PROCESS_EXIT_REQUIRED);
    CHECK(f.fake.counts == counts && !f.fake.in_turn && f.fake.counts.retirements == 0);
}

void bind_validation(Fixture& f) {
    const auto editor = f.editor_backend; const auto base = f.backend; const auto document = f.document_backend;
    auto reject = [&] { CHECK(f.bind_status() == BIB_ENGINE_INVALID); CHECK(f.fake.counts == Counts{}); };
    f.editor_backend.size = 0; reject(); f.editor_backend = editor;
    ++f.editor_backend.version; reject(); f.editor_backend = editor;
    f.editor_backend.reserved0 = 1; reject(); f.editor_backend = editor;
    f.editor_backend.reserved1 = 1; reject(); f.editor_backend = editor;
    f.editor_backend.worker_epoch = 0; reject(); f.editor_backend = editor;
    ++f.editor_backend.worker_epoch; reject(); f.editor_backend = editor;
    f.editor_backend.editor_header_sha256[0] ^= 1; reject(); f.editor_backend = editor;
    f.editor_backend.contract_sha256[0] ^= 1; reject(); f.editor_backend = editor;
    f.editor_backend.catalog_sha256[0] ^= 1; reject(); f.editor_backend = editor;
    f.editor_backend.schema_sha256[0] ^= 1; reject(); f.editor_backend = editor;
    f.editor_backend.admit_request = nullptr; reject(); f.editor_backend = editor;
    f.editor_backend.validate_reply = nullptr; reject(); f.editor_backend = editor;
    f.editor_backend.project = nullptr; reject(); f.editor_backend = editor;
    f.editor_backend.apply = nullptr; reject(); f.editor_backend = editor;
    f.editor_backend.revoke = nullptr; reject(); f.editor_backend = editor;
    f.document_backend.profile = document_pixel_profile; reject(); f.document_backend = document;
    f.document_backend.worker_epoch = 0; reject(); f.document_backend = document;
    f.document_backend.physical_catalog_sha256[0] ^= 1; reject(); f.document_backend = document;
    f.backend.build.capabilities = 2003; reject(); f.backend = base;
    f.backend.build.capabilities |= UINT64_C(1)<<12; reject(); f.backend = base;
    std::copy(document_contract.begin(),document_contract.end(),f.backend.build.contract_header_sha256); reject(); f.backend = base;
    f.backend.command_count = 6; reject(); f.backend = base;
    f.backend.query_count = 1; reject(); f.backend = base;
    f.backend.limits.maximum_command_bytes--; reject(); f.backend = base;
    f.backend.limits.maximum_query_bytes--; reject(); f.backend = base;
    f.backend.limits.maximum_reply_bytes--; reject(); f.backend = base;
    for (std::size_t index : {std::size_t(5),std::size_t(6)}) {
        const auto good = f.commands[index];
        --f.commands[index].maximum_input_bytes; reject(); f.commands[index] = good;
        --f.commands[index].required_reply_capacity; reject(); f.commands[index] = good;
        f.commands[index].schema[0] ^= 1; reject(); f.commands[index] = good;
        f.commands[index].capability = BIB_ENGINE_CAP_KEY_V1; reject(); f.commands[index] = good;
    }
    const auto query = f.queries[1];
    --f.queries[1].maximum_input_bytes; reject(); f.queries[1] = query;
    f.queries[1].schema[0] ^= 1; reject(); f.queries[1] = query;
    CHECK(bind_engine_private(f.backend) == BIB_ENGINE_INVALID);
    CHECK(bind_engine_document_private(f.backend,f.document_backend) == BIB_ENGINE_INVALID);
    f.bind(); CHECK(f.bind_status() == BIB_ENGINE_CLOSED);
}

void malformed_commands(Fixture& f,std::uint32_t operation) {
    Command command(f.fake.document,1,operation); const auto bytes = command.payload; const auto request = command.request;
    const auto buffer = command.buffer; const auto counts = f.fake.counts;
    auto reject = [&] { CHECK(command.run() == BIB_ENGINE_INVALID); command.rejected(); CHECK(f.fake.counts == counts);
        command.payload = bytes; command.request = request; command.buffer = buffer; };
    command.payload[0] ^= 1; reject(); command.payload[7] = 1; reject(); overwrite(command.payload,8,2,2); reject();
    overwrite(command.payload,10,1,2); reject(); overwrite(command.payload,12,0,4); reject();
    for (const auto offset : {16u,24u,32u,40u,48u}) { command.payload[offset] ^= 1; reject(); }
    command.payload.pop_back(); reject(); command.payload.push_back(0); reject();
    command.payload.resize(55); overwrite(command.payload,12,55,4); reject();
    command.request.request_sequence = 0; reject(); command.request.request_sequence = UINT64_MAX; reject();
    command.request.expected.document_sequence = 0; reject(); command.request.schema_sha256[0] ^= 1; reject();
    command.request.payload.reserved = 1; reject(); command.request.size = 4; reject(); command.buffer.size = 4; reject();
    command.buffer.capacity = reply_capacity-1; reject();
    // An invalid output range may alias result metadata. Preserve the complete
    // metadata sentinel as well as every byte of the actual allocated buffer.
    command.buffer.bytes = nullptr; CHECK(command.run() == BIB_ENGINE_INVALID);
    CHECK(command.result.size == sizeof(command.result) && command.result.disposition == 99
        && command.result.request_sequence == 99 && command.result.bytes_written == 99 && command.result.handled == 99);
    CHECK(untouched(command.output) && f.fake.counts == counts); command.buffer = buffer;
    command.payload.assign(BIB_ENGINE_EDITOR_MAX_WIRE_BYTES+1,0); reject();
    CHECK(command.run() == 0); command.completed();
}
void malformed_query(Fixture& f) {
    Query query(f.fake.document); const auto bytes = query.payload; const auto request = query.request;
    const auto buffer = query.buffer; const auto counts = f.fake.counts;
    auto reject = [&] { CHECK(query.run() == BIB_ENGINE_INVALID); query.rejected(); CHECK(f.fake.counts == counts);
        query.payload = bytes; query.request = request; query.buffer = buffer; };
    query.payload[0] ^= 1; reject(); overwrite(query.payload,8,3,2); reject(); overwrite(query.payload,10,1,2); reject();
    overwrite(query.payload,12,0,4); reject();
    for (const auto offset : {16u,24u,32u,40u}) { query.payload[offset] ^= 1; reject(); }
    overwrite(query.payload,48,0,8); reject(); overwrite(query.payload,48,UINT64_MAX,8); reject();
    query.payload.pop_back(); reject(); query.payload.push_back(0); reject(); query.payload.resize(55); overwrite(query.payload,12,55,4); reject();
    query.payload.assign(BIB_ENGINE_EDITOR_MAX_QUERY_BYTES+1,0); reject();
    query.request.expected.application_instance = 0; reject(); query.request.schema_sha256[0] ^= 1; reject();
    query.request.payload.reserved = 1; reject(); query.request.size = 4; reject(); query.buffer.size = 4; reject();
    query.buffer.capacity = reply_capacity-1; reject();
    query.buffer.bytes = nullptr; CHECK(query.run() == BIB_ENGINE_INVALID);
    CHECK(query.result.size == sizeof(query.result) && query.result.bytes_written == 99
        && query.result.semantic_revision == 99 && same(query.result.document,{91,92,93}));
    CHECK(untouched(query.output) && f.fake.counts == counts); query.buffer = buffer;
    CHECK(query.run() == 0); query.completed();
}

void run(const std::string& name) {
    Fixture f;
    if (name == "bind-validation") { bind_validation(f); return; }
    if (name == "full-width") {
        f.fake.document = {UINT64_MAX-7,UINT64_MAX-5,UINT64_MAX-3}; f.backend.application_instance = f.fake.document.application_instance;
        f.bind(); f.start(); Query query(f.fake.document,UINT64_MAX-10); CHECK(query.run() == 0); query.completed();
        Command command(f.fake.document,UINT64_MAX-9); CHECK(command.run() == 0); command.completed();
        Command revoke(f.fake.document,UINT64_MAX-8,9); CHECK(revoke.run() == 0); revoke.completed(); return;
    }
    f.bind();
    if (name == "minor-optin") {
        BibEngineProviderV1 untouched{}; untouched.size = 17;
        CHECK(bib_engine_get_provider_v1(1,0,sizeof(untouched),&untouched) == BIB_ENGINE_UNSUPPORTED && untouched.size == 17);
        CHECK(bib_engine_get_provider_v1(1,99,sizeof(untouched),&untouched) == 0 && untouched.abi_minor == 1);
        CHECK(untouched.build.capabilities == 2035
            && std::equal(pins::kContractSha256.begin(),pins::kContractSha256.end(),untouched.build.contract_header_sha256)); return;
    }
    f.start();
    if (name == "project" || name == "project-noneditable" || name == "project-unavailable") {
        if (name == "project-noneditable") f.fake.query_state = wire::ProjectionReply::State::noneditable;
        if (name == "project-unavailable") f.fake.query_state = wire::ProjectionReply::State::unavailable;
        const auto before = f.fake.counts; Query query(f.fake.document); CHECK(query.run() == 0); query.completed(f.fake.query_state);
        auto expected = before; ++expected.enters; ++expected.leaves; expected.currents += 2;
        ++expected.admits; ++expected.projects; ++expected.reply_validations; CHECK(f.fake.counts == expected); return;
    }
    if (name == "apply" || name == "revoke" || name == "revoke-observed") {
        const bool revoke = name != "apply"; Command command(f.fake.document,1,revoke ? 9 : 8);
        if (name == "revoke-observed") command.payload = revocation(f.fake.document,1,true);
        const auto before = f.fake.counts; CHECK(command.run() == 0); command.completed();
        auto expected = before; ++expected.enters; ++expected.leaves; ++expected.currents; ++expected.admits; ++expected.reply_validations;
        if (!revoke) ++expected.admits;
        if (revoke) ++expected.revocations; else ++expected.applies;
        CHECK(f.fake.counts == expected); return;
    }
    if (name == "malformed-observation" || name == "malformed-revocation") { malformed_commands(f,name == "malformed-revocation" ? 9 : 8); return; }
    if (name == "malformed-query") { malformed_query(f); return; }
    if (name == "deep-request-rejection") {
        Command command(f.fake.document); command.payload.push_back(0); overwrite(command.payload,12,command.payload.size(),4);
        CHECK(command.run() == BIB_ENGINE_INVALID); command.rejected();
        CHECK(f.fake.counts.admits == 1 && f.fake.admit_preflights == 1 && f.fake.admit_in_turn == 0
            && f.fake.counts.applies == 0 && f.fake.counts.enters == 1 && f.fake.counts.leaves == 1);
        command.payload = observation(f.fake.document,1); CHECK(command.run() == 0); command.completed(); return;
    }
    if (name == "retire-authority") {
        Command revoke(f.fake.document,1,9); wire::RevocationEnvelope forged;
        CHECK(wire::decode_revocation(revoke.payload,forged)); ++forged.request.material.token;
        CHECK(wire::encode_revocation(forged,revoke.payload)); CHECK(revoke.run() == BIB_ENGINE_STALE); revoke.rejected();
        CHECK(f.fake.counts.revocations == 0 && f.fake.counts.admits == 1);
        revoke.payload = revocation(f.fake.document,1); CHECK(revoke.run() == 0); revoke.completed(); return;
    }
    if (name == "admission-rejected") {
        f.fake.admit_status = BIB_ENGINE_STALE; Command command(f.fake.document); const auto before = f.fake.counts;
        CHECK(command.run() == BIB_ENGINE_STALE); command.rejected();
        CHECK(f.fake.counts.enters == before.enters && f.fake.counts.leaves == before.leaves
            && f.fake.counts.currents == before.currents && f.fake.admit_preflights == 1 && f.fake.admit_in_turn == 0
            && f.fake.counts.applies == 0 && f.fake.counts.reply_validations == 0);
        f.fake.admit_status = 0; CHECK(command.run() == 0); command.completed();
        CHECK(f.fake.admit_preflights == 2 && f.fake.admit_in_turn == 1); return;
    }
    if (name == "admission-enter-invalidation") {
        Command command(f.fake.document); const auto original = f.fake.document; const auto before = f.fake.counts;
        f.fake.invalidate_on_enter = true; CHECK(command.run() == BIB_ENGINE_STALE); command.rejected();
        CHECK(f.fake.counts.enters == before.enters+1 && f.fake.counts.leaves == before.leaves+1
            && f.fake.counts.currents == before.currents+1 && f.fake.admit_preflights == 1 && f.fake.admit_in_turn == 1
            && f.fake.counts.applies == 0 && f.fake.counts.revocations == 0);
        CHECK(same(f.fake.document, original));
        f.fake.invalidate_on_enter = false; f.fake.admit_status = 0;
        CHECK(command.run() == 0); command.completed();
        CHECK(f.fake.admit_preflights == 2 && f.fake.admit_in_turn == 2 && f.fake.counts.applies == 1); return;
    }
    if (name == "admit-preflight-throw") {
        f.fake.throw_admit = true; const auto before = f.fake.counts; Command command(f.fake.document);
        CHECK(command.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED); command.rejected();
        CHECK(f.fake.counts.admits == before.admits+1 && f.fake.admit_preflights == 1 && f.fake.admit_in_turn == 0
            && f.fake.counts.enters == before.enters && f.fake.counts.leaves == before.leaves
            && f.fake.counts.applies == 0);
        terminal_no_exports(f); return;
    }
    if (name == "native-pending") {
        f.fake.pending_native = true; Query query(f.fake.document); CHECK(query.run() == BIB_ENGINE_LIMIT); query.rejected();
        Command command(f.fake.document); CHECK(command.run() == BIB_ENGINE_LIMIT); command.rejected();
        CHECK(f.fake.counts.projects == 0 && f.fake.counts.applies == 0 && f.fake.counts.admits == 2);
        Command revoke(f.fake.document,1,9); CHECK(revoke.run() == 0); revoke.completed();
        CHECK(f.fake.counts.revocations == 1); return;
    }
    if (name == "form-backpressure") {
        Command form(f.fake.document,1); form.form(); CHECK(form.run() == 0 && form.result.disposition == 1);
        const auto before = f.fake.counts; Command command(f.fake.document,2); Command revoke(f.fake.document,2,9);
        CHECK(command.run() == BIB_ENGINE_LIMIT); command.rejected(); CHECK(revoke.run() == BIB_ENGINE_LIMIT); revoke.rejected();
        CHECK(f.fake.counts == before);
        Query query(f.fake.document,2); CHECK(query.run() == 0); query.completed();
        Command ack(f.fake.document,3); ack.ack(1); CHECK(ack.run() == 0 && ack.result.disposition == 1 && ack.result.bytes_written == 16);
        CHECK(get(ack.output.data(),8) == 1 && get(ack.output.data()+8,4) == 0 && f.fake.counts.retirements == 1);
        Command next(f.fake.document,4); CHECK(next.run() == 0); next.completed();
        Command next_revoke(f.fake.document,5,9); CHECK(next_revoke.run() == 0); next_revoke.completed(); return;
    }
    if (name == "shared-sequence") {
        Query query(f.fake.document,1); CHECK(query.run() == 0); query.completed();
        Command command(f.fake.document,2); CHECK(command.run() == 0); command.completed();
        Command revoke(f.fake.document,3,9); CHECK(revoke.run() == 0); revoke.completed();
        Command form(f.fake.document,4); form.form(); CHECK(form.run() == 0);
        Command ack(f.fake.document,5); ack.ack(4); CHECK(ack.run() == 0);
        Command physical(f.fake.document,6); physical.physical(0); CHECK(physical.run() == 0 && physical.result.bytes_written == 0);
        Query old(f.fake.document,7); old.request.kind = 3; old.payload = document_envelope(1,f.fake.document,7,3);
        std::copy(document_schema.begin(),document_schema.end(),old.request.schema_sha256); CHECK(old.run() == 0 && old.result.bytes_written == 134);
        const auto counts = f.fake.counts; Command stale(f.fake.document,7); CHECK(stale.run() == BIB_ENGINE_STALE); stale.rejected();
        Query stale_query(f.fake.document,6); CHECK(stale_query.run() == BIB_ENGINE_STALE); stale_query.rejected(); CHECK(f.fake.counts == counts);
        Command no_legacy_editor(f.fake.document,8); no_legacy_editor.request.operation = 2;
        CHECK(no_legacy_editor.run() == BIB_ENGINE_UNSUPPORTED); no_legacy_editor.rejected(); CHECK(f.fake.counts == counts); return;
    }
    if (name == "stale-no-replay") {
        Command command(f.fake.document,1); CHECK(command.run() == 0); command.completed();
        const auto after_command = f.fake.counts; std::fill(command.output.begin(),command.output.end(),0xa5);
        CHECK(command.run() == BIB_ENGINE_STALE); command.rejected(); CHECK(f.fake.counts == after_command);
        Command revoke(f.fake.document,2,9); CHECK(revoke.run() == 0); revoke.completed();
        const auto after_revoke = f.fake.counts; std::fill(revoke.output.begin(),revoke.output.end(),0xa5);
        CHECK(revoke.run() == BIB_ENGINE_STALE); revoke.rejected(); CHECK(f.fake.counts == after_revoke);
        Query query(f.fake.document,3); CHECK(query.run() == 0); query.completed();
        const auto after_query = f.fake.counts; std::fill(query.output.begin(),query.output.end(),0xa5);
        CHECK(query.run() == BIB_ENGINE_STALE); query.rejected(); CHECK(f.fake.counts == after_query);
        Command ack(f.fake.document,4); ack.ack(1); CHECK(ack.run() == 0 && get(ack.output.data()+8,4) == 2);
        CHECK(f.fake.counts.retirements == 0); return;
    }
    if (name == "sequence-max") {
        Command invalid(f.fake.document,UINT64_MAX); CHECK(invalid.run() == BIB_ENGINE_INVALID); invalid.rejected();
        Command maximum(f.fake.document,maximum_ordinary); CHECK(maximum.run() == 0); maximum.completed();
        const auto before = f.fake.counts; Query stale(f.fake.document,maximum_ordinary); CHECK(stale.run() == BIB_ENGINE_STALE); stale.rejected();
        Command revoke(f.fake.document,maximum_ordinary-1,9); CHECK(revoke.run() == BIB_ENGINE_STALE); revoke.rejected();
        CHECK(f.fake.counts == before); return;
    }
    if (name == "owned-observation" || name == "owned-revocation" || name == "owned-query") {
        if (name == "owned-query") {
            Query query(f.fake.document); f.fake.mutate = query.payload.data(); CHECK(query.run() == 0); query.completed();
            CHECK(query.payload[0] == 91 && f.fake.observed_first == 'B');
        } else {
            Command command(f.fake.document,1,name == "owned-revocation" ? 9 : 8); f.fake.mutate = command.payload.data();
            CHECK(command.run() == 0); command.completed(); CHECK(command.payload[0] == 91 && f.fake.observed_first == 'B');
        }
        return;
    }
    if (name == "owned-bindings") {
        f.editor_backend = {}; f.document_backend = {}; f.commands = {}; f.queries = {}; f.backend = {};
        Query query(f.fake.document,1); CHECK(query.run() == 0); query.completed();
        Command command(f.fake.document,2); CHECK(command.run() == 0); command.completed();
        Command revoke(f.fake.document,3,9); CHECK(revoke.run() == 0); revoke.completed(); return;
    }
    if (name == "enter-rejection") {
        f.fake.enter_status = 2; Command command(f.fake.document); CHECK(command.run() == BIB_ENGINE_REENTRANT); command.rejected();
        CHECK(f.fake.counts.admits == 1 && f.fake.admit_preflights == 1 && f.fake.admit_in_turn == 0
            && f.fake.counts.applies == 0 && f.fake.counts.leaves == 1);
        f.fake.enter_status = 0; CHECK(command.run() == 0); command.completed(); return;
    }
    if (name == "reentry" || name == "query-reentry" || name == "revoke-reentry") {
        f.fake.reenter = true;
        if (name == "query-reentry") { Query query(f.fake.document); CHECK(query.run() == 0); query.completed(); }
        else { Command command(f.fake.document,1,name == "revoke-reentry" ? 9 : 8); CHECK(command.run() == 0); command.completed();
            CHECK(f.fake.threaded == BIB_ENGINE_WRONG_THREAD); }
        CHECK(f.fake.nested_enter == BIB_ENGINE_REENTRANT && f.fake.nested_leave == BIB_ENGINE_REENTRANT
            && f.fake.nested_admit == BIB_ENGINE_REENTRANT && f.fake.nested_reply == BIB_ENGINE_REENTRANT
            && f.fake.nested_effect == BIB_ENGINE_REENTRANT); return;
    }
    if (name == "wrong-thread") {
        const auto before = f.fake.counts; int command_status{}, query_status{};
        std::thread wrong([&] { Command command(f.fake.document); command_status = command.run();
            Query query(f.fake.document); query_status = query.run(); }); wrong.join();
        CHECK(command_status == BIB_ENGINE_WRONG_THREAD && query_status == BIB_ENGINE_WRONG_THREAD && f.fake.counts == before); return;
    }
    const bool query_fault = name.starts_with("query-");
    const bool revoke_fault = name.starts_with("revoke-");
    const auto fault = query_fault ? name.substr(6) : revoke_fault ? name.substr(7) : name;
    bool known = true;
    if (fault == "error") f.fake.effect_status = BIB_ENGINE_INVALID;
    else if (fault == "throw") f.fake.throw_effect = true;
    else if (fault == "unknown") f.fake.unknown = true;
    else if (fault == "malformed-header") f.fake.malformed_header = true;
    else if (fault == "malformed-target") f.fake.malformed_target = true;
    else if (fault == "malformed-body") f.fake.malformed_body = true;
    else if (fault == "reply-rejected") f.fake.reply_status = BIB_ENGINE_INVALID;
    else if (fault == "reply-throw") f.fake.throw_reply = true;
    else if (fault == "leave-throw") f.fake.throw_leave = true;
    else if (fault == "size") f.fake.bad_size = true;
    else if (fault == "overflow") f.fake.overflow_reply = true;
    else if (fault == "handled") f.fake.bad_handled = true;
    else if (fault == "sequence") f.fake.wrong_sequence = true;
    else if (fault == "zero-revision") f.fake.query_revision = 0;
    else if (fault == "wrong-revision") f.fake.wrong_revision = true;
    else if (fault == "wrong-document") f.fake.wrong_document = true;
    else if (fault == "navigation") f.fake.navigate_query = true;
    else if (fault == "admit-throw") {
        if (!query_fault && !revoke_fault) f.fake.throw_admit_second = true;
        else f.fake.throw_admit = true;
    }
    else known = false;
    CHECK(known);
    if (query_fault) { Query query(f.fake.document); CHECK(query.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED); query.rejected(); }
    else { Command command(f.fake.document,1,revoke_fault ? 9 : 8); CHECK(command.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED);
        if (fault == "admit-throw") command.rejected(); else command.unknown(); }
    terminal_no_exports(f);
}

// Historical tests decorate only the new callbacks. All predecessor test and
// callback bodies use the same current-lane admission and TURN rules; no
// current-lane behavior is faked for the narrow operation9 admission rule.
struct HistoricalCallbacks {
    static std::int32_t project(void* context,std::uint64_t worker,const BibEngineQueryV1* request,
                                BibEngineReplyBufferV1* buffer,BibEngineQueryResultV1* result) {
        const auto status = Fake::project(context,worker,request,buffer,result);
        if (status) return status;
        auto& f = *static_cast<Fake*>(context); wire::ProjectionReply reply;
        CHECK(wire::decode_projection_reply(std::span<const std::uint8_t>(buffer->bytes,result->bytes_written),reply));
        CHECK(reply.state == wire::ProjectionReply::State::available && reply.projection && reply.projection->retire);
        f.historical_lease = HistoricalLease{reply.target,*reply.projection->retire,reply.identity,true};
        return 0;
    }
    static std::int32_t admit(void* context,std::uint64_t worker,const BibEngineDocumentV1* expected,
                             std::uint32_t domain,std::uint32_t operation,std::uint64_t sequence,const BibEngineBytesV1* payload) {
        if (domain != 0 || operation != 9) return Fake::admit(context,worker,expected,domain,operation,sequence,payload);
        auto& f = *static_cast<Fake*>(context);
        CHECK(f.in_turn && expected && payload && !payload->reserved); ++f.counts.admits;
        if (f.admit_status) return f.admit_status;
        wire::RevocationEnvelope request;
        if (!wire::decode_revocation(std::span<const std::uint8_t>(payload->data,payload->length),request)) return BIB_ENGINE_INVALID;
        if (!f.historical_lease || !f.historical_lease->active) return BIB_ENGINE_STALE;
        const auto& lease = *f.historical_lease;
        // Bad authority is a known inert rejection, not a fixture exception or
        // an assertion that could accidentally poison this still-usable guard.
        if (worker != lease.source.worker_epoch || expected->application_instance != lease.source.application_instance
            || expected->document_sequence != lease.source.document_sequence || expected->service_generation != lease.source.service_generation
            || request.target != target(*expected,sequence) || request.request.material != lease.material
            || request.request.identity != lease.identity) return BIB_ENGINE_STALE;
        return 0;
    }
    static native::Identity replacement_identity(const Fake& f) {
        CHECK(f.historical_lease.has_value()); auto identity = f.historical_lease->identity;
        ++identity.epoch; ++identity.context; return identity;
    }
    static std::int32_t revoke(void* context,std::uint64_t worker,const BibEngineCommandV1* request,
                               BibEngineReplyBufferV1* buffer,BibEngineCommandResultV1* result) {
        auto& f = *static_cast<Fake*>(context);
        CHECK(f.in_turn && worker == worker_epoch && request->operation == 9 && f.historical_lease && f.historical_lease->active);
        ++f.counts.revocations;
        native::NativeResult value;
        if (!f.unknown) {
            value.outcome = native::Outcome::applied; value.availability = native::NativeAvailability::unavailable;
            value.observation_revision = 94; value.readback_identity = replacement_identity(f); value.readback_attested = true;
            value.retired = f.historical_lease->material;
        }
        Bytes bytes; CHECK(wire::encode_native_result({target(request->expected,request->request_sequence),value},bytes));
        CHECK(bytes.size() <= buffer->capacity); std::copy(bytes.begin(),bytes.end(),buffer->bytes);
        result->bytes_written = static_cast<std::uint32_t>(bytes.size());
        if (!f.unknown) f.historical_lease->active = false;
        return 0;
    }
    static std::int32_t validate_reply(void* context,std::uint64_t worker,const BibEngineDocumentV1* expected,
                                      std::uint32_t domain,std::uint32_t operation,std::uint64_t sequence,
                                      const BibEngineBytesV1* payload,const BibEngineBytesV1* reply) {
        if (domain != 0 || operation != 9) return Fake::validate_reply(context,worker,expected,domain,operation,sequence,payload,reply);
        auto& f = *static_cast<Fake*>(context); CHECK(f.in_turn && worker == worker_epoch && expected && payload && reply);
        ++f.counts.reply_validations; wire::NativeResultEnvelope value;
        if (!wire::decode_native_result(std::span<const std::uint8_t>(reply->data,reply->length),value)) return BIB_ENGINE_INVALID;
        if (value.result.outcome == native::Outcome::unknown) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
        CHECK(f.historical_lease && !f.historical_lease->active); check_target(value.target,*expected,sequence);
        CHECK(value.result.outcome == native::Outcome::applied && value.result.availability == native::NativeAvailability::unavailable
            && !value.result.projection && value.result.observation_revision == 94 && value.result.readback_attested
            && value.result.readback_identity == replacement_identity(f) && value.result.retired == f.historical_lease->material
            && !value.result.retire);
        return 0;
    }
};

bool run_historical(const std::string& name) {
    if (!name.starts_with("historical-")) return false;
    Fixture f;
    f.editor_backend.project = HistoricalCallbacks::project; f.editor_backend.admit_request = HistoricalCallbacks::admit;
    f.editor_backend.revoke = HistoricalCallbacks::revoke; f.editor_backend.validate_reply = HistoricalCallbacks::validate_reply;
    f.bind(); f.start();
    const auto original = f.fake.document;
    Query issued(original,1); CHECK(issued.run() == 0); issued.completed();
    CHECK(f.fake.historical_lease && f.fake.historical_lease->active && f.fake.historical_lease->source == target(original,1));
    if (name == "historical-revoke-form-barrier") {
        Command form(original,2); form.form(); CHECK(form.run() == 0 && form.result.disposition == 1);
    }
    ++f.fake.document.document_sequence; ++f.fake.document.service_generation;
    CHECK(!same(f.fake.document,original));
    auto completed = [&](Command& command) {
        CHECK(command.run() == 0); command.completed();
        CHECK(f.fake.historical_lease && !f.fake.historical_lease->active && f.fake.counts.revocations == 1);
        wire::NativeResultEnvelope value;
        CHECK(wire::decode_native_result(std::span<const std::uint8_t>(command.output.data(),command.result.bytes_written),value));
        CHECK(value.result.retired == f.fake.historical_lease->material && !value.result.projection
            && value.result.readback_identity == HistoricalCallbacks::replacement_identity(f.fake));
    };
    if (name == "historical-revoke-once") {
        const auto before = f.fake.counts; Command revoke(original,2,9); completed(revoke);
        auto expected = before; ++expected.enters; ++expected.leaves; ++expected.currents; ++expected.admits;
        ++expected.revocations; ++expected.reply_validations; CHECK(f.fake.counts == expected);
        Command duplicate(original,2,9); CHECK(duplicate.run() == BIB_ENGINE_STALE); duplicate.rejected(); CHECK(f.fake.counts == expected);
        Command newer(original,3,9); CHECK(newer.run() == BIB_ENGINE_STALE); newer.rejected();
        CHECK(f.fake.counts.revocations == 1 && f.fake.counts.admits == expected.admits+1 && f.fake.counts.currents == expected.currents+1);
        return true;
    }
    if (name == "historical-revoke-bad-material") {
        for (unsigned part = 0; part < 4; ++part) {
            Command forged(original,2,9); wire::RevocationEnvelope request; CHECK(wire::decode_revocation(forged.payload,request));
            if (part == 0) ++request.request.material.token;
            if (part == 1) ++request.request.material.mapping_id;
            if (part == 2) { ++request.request.material.input_context; ++request.request.identity.context; }
            if (part == 3) ++request.request.material.composition;
            CHECK(wire::encode_revocation(request,forged.payload)); const auto before = f.fake.counts;
            CHECK(forged.run() == BIB_ENGINE_STALE); forged.rejected();
            auto expected = before; ++expected.enters; ++expected.leaves; ++expected.currents; ++expected.admits;
            CHECK(f.fake.counts == expected && f.fake.historical_lease->active);
        }
        Command exact(original,2,9); completed(exact); return true;
    }
    if (name == "historical-revoke-full-target") {
        for (unsigned part = 0; part < 3; ++part) {
            auto wrong = original;
            if (part == 0) ++wrong.application_instance;
            if (part == 1) ++wrong.document_sequence;
            if (part == 2) ++wrong.service_generation;
            Command forged(wrong,2,9); const auto before = f.fake.counts;
            CHECK(forged.run() == BIB_ENGINE_STALE); forged.rejected();
            auto expected = before; ++expected.enters; ++expected.leaves;
            if (part != 0) { ++expected.currents; ++expected.admits; }
            CHECK(f.fake.counts == expected && f.fake.historical_lease->active);
        }
        for (const auto offset : {16u,48u}) {
            Command forged(original,2,9); forged.payload[offset] ^= 1; const auto before = f.fake.counts;
            CHECK(forged.run() == BIB_ENGINE_INVALID); forged.rejected(); CHECK(f.fake.counts == before);
        }
        Command exact(original,2,9); completed(exact); return true;
    }
    if (name == "historical-current-lanes") {
        const auto before = f.fake.counts;
        Command old_edit(original,2); CHECK(old_edit.run() == BIB_ENGINE_STALE); old_edit.rejected();
        // The fake retains the same native metadata after document navigation.
        // Preflight passes, then the in-TURN document check rejects this C8.
        auto expected = before; ++expected.admits; ++expected.enters; ++expected.leaves; ++expected.currents;
        CHECK(f.fake.counts == expected && f.fake.historical_lease->active);
        Query old_projection(original,2); CHECK(old_projection.run() == BIB_ENGINE_STALE); old_projection.rejected();
        ++expected.enters; ++expected.leaves; ++expected.currents;
        CHECK(f.fake.counts == expected && f.fake.historical_lease->active);
        Command revoke(original,2,9); completed(revoke); return true;
    }
    if (name == "historical-revoke-admit-reject") {
        f.fake.admit_status = BIB_ENGINE_LIMIT; Command revoke(original,2,9); const auto before = f.fake.counts;
        CHECK(revoke.run() == BIB_ENGINE_LIMIT); revoke.rejected();
        auto expected = before; ++expected.enters; ++expected.leaves; ++expected.currents; ++expected.admits;
        CHECK(f.fake.counts == expected && f.fake.historical_lease->active);
        f.fake.admit_status = 0; completed(revoke); return true;
    }
    if (name == "historical-revoke-enter-reject") {
        f.fake.enter_status = 2; Command revoke(original,2,9); const auto before = f.fake.counts;
        CHECK(revoke.run() == BIB_ENGINE_REENTRANT); revoke.rejected();
        auto expected = before; ++expected.enters; CHECK(f.fake.counts == expected && f.fake.historical_lease->active);
        f.fake.enter_status = 0; completed(revoke); return true;
    }
    if (name == "historical-revoke-form-barrier") {
        Command revoke(original,3,9); const auto before = f.fake.counts;
        CHECK(revoke.run() == BIB_ENGINE_LIMIT); revoke.rejected(); CHECK(f.fake.counts == before && f.fake.historical_lease->active);
        Command ack(original,3); ack.ack(2); CHECK(ack.run() == 0 && ack.result.disposition == 1 && ack.result.bytes_written == 16);
        CHECK(get(ack.output.data(),8) == 2 && get(ack.output.data()+8,4) == 0 && f.fake.counts.retirements == 1);
        Command next(original,4,9); completed(next); return true;
    }
    if (name == "historical-revoke-unknown") {
        f.fake.unknown = true; Command revoke(original,2,9);
        CHECK(revoke.run() == BIB_ENGINE_PROCESS_EXIT_REQUIRED); revoke.unknown();
        CHECK(f.fake.counts.revocations == 1 && f.fake.historical_lease->active);
        terminal_no_exports(f); return true;
    }
    CHECK(false); return true;
}
} // namespace

int main(int argc,char** argv) {
    try { CHECK(argc == 2); if (!run_historical(argv[1])) run(argv[1]); CHECK(first_assertion_failure.empty());
        std::cout << "PASS " << argv[1] << " (" << assertions << " assertions)\n"; return 0; }
    catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
