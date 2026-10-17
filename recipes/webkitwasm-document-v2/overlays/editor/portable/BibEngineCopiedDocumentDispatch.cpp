// SPDX-License-Identifier: CC0-1.0
#include "BibEngineCopiedDocumentDispatch.hpp"
#include "BibEngineCopiedDocumentFacts.h"
#include "engine_editor_protocol.h"
#include "native_editor_codec.hpp"
#include <algorithm>
#include <array>
#include <climits>
#include <cstring>
#include <limits>
#include <vector>

namespace bib::copied {
namespace {
namespace Editor=foundation::ui::native_editor;
namespace EditorCodec=Editor::codec;
bool editorOperation(const DocumentWireOperation& op) noexcept {
    return op.query?op.operation==BIB_ENGINE_QUERY_EDITOR_PROJECTION_V1:
        op.operation==BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1 || op.operation==BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1;
}
bool historicalEditorRetirement(DocumentWireProfile profile,const DocumentWireOperation& op) noexcept {
    // This grants no native authority. The actual Guard must prove the exact
    // original full target and one still-owned issued material in inert admit.
    return profile==DocumentWireProfile::editor && !op.query && op.operation==BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1;
}
EditorCodec::WireTarget editorTarget(const Record& r,std::uint64_t sequence) noexcept {
    return {r.worker,r.instance,r.document,r.generation,sequence};
}
bool editorRequestValid(const DocumentWireOperation& op,const Record& r) noexcept {
    const auto target=editorTarget(r,op.sequence);
    if (op.query) {
        EditorCodec::ProjectionQuery decoded;
        return EditorCodec::decode_projection_query(op.payload,decoded) && decoded.target==target;
    }
    if (op.operation==BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1) {
        EditorCodec::NativeRequestEnvelope decoded;
        return EditorCodec::decode_native_request(op.payload,decoded) && decoded.target==target;
    }
    EditorCodec::RevocationEnvelope decoded;
    return EditorCodec::decode_revocation(op.payload,decoded) && decoded.target==target;
}
bool editorCommandReplyValid(std::span<const std::uint8_t> bytes,const Record& r,std::uint64_t sequence) noexcept {
    EditorCodec::NativeResultEnvelope decoded;
    return EditorCodec::decode_native_result(bytes,decoded) && decoded.target==editorTarget(r,sequence)
        && decoded.result.outcome!=Editor::Outcome::unknown;
}
bool editorQueryReplyValid(std::span<const std::uint8_t> bytes,const Record& r,
    std::uint64_t sequence,std::uint64_t revision) noexcept {
    EditorCodec::ProjectionReply decoded;
    return EditorCodec::decode_projection_reply(bytes,decoded) && decoded.target==editorTarget(r,sequence)
        && decoded.observation_revision==revision;
}
bool same(const BibEngineDocumentV1& a,const BibEngineDocumentV1& b) noexcept {
    return a.application_instance==b.application_instance && a.document_sequence==b.document_sequence
        && a.service_generation==b.service_generation;
}
BibEngineDocumentV1 identity(const Record& r) noexcept { return {r.instance,r.document,r.generation}; }
void useIdentity(Record& r,const BibEngineDocumentV1& d) noexcept {
    r.instance=d.application_instance; r.document=d.document_sequence; r.generation=d.service_generation;
}
std::uint64_t get64(std::span<const std::uint8_t> v) noexcept {
    std::uint64_t out=0; for(unsigned i=0;i<8;++i) out|=std::uint64_t(v[i])<<(i*8); return out;
}
std::uint32_t get32(std::span<const std::uint8_t> v) noexcept {
    std::uint32_t out=0; for(unsigned i=0;i<4;++i) out|=std::uint32_t(v[i])<<(i*8); return out;
}
void put32(std::span<std::uint8_t> out,std::uint32_t value) noexcept {
    for(unsigned i=0;i<4;++i) out[i]=static_cast<std::uint8_t>(value>>(i*8));
}
bool overlap(std::span<const std::uint8_t> in,std::span<std::uint8_t> out) noexcept {
    const auto a=reinterpret_cast<std::uintptr_t>(in.data()),b=reinterpret_cast<std::uintptr_t>(out.data());
    return (in.size()>UINTPTR_MAX-a || out.size()>UINTPTR_MAX-b)
        || (!in.empty() && !out.empty() && a<b+out.size() && b<a+in.size());
}
std::uint32_t control(std::int32_t status,CopiedHost& host) noexcept {
    switch(status) {
    case BIB_ENGINE_OK:return 0;
    case BIB_ENGINE_INVALID:return 2;
    case BIB_ENGINE_UNSUPPORTED:return 7;
    case BIB_ENGINE_WRONG_THREAD:case BIB_ENGINE_REENTRANT:return 5;
    case BIB_ENGINE_STALE:return 3;
    case BIB_ENGINE_LIMIT:return 4;
    case BIB_ENGINE_CLOSED:return 6;
    default:host.fail("Unknown or terminal provider result");
    }
}
template<class F> auto actual(F&& f,CopiedHost& host) noexcept -> decltype(f()) {
    try { return f(); } catch(...) { host.fail("Exception crossed private provider C ABI"); }
}
struct DispatchScope {
    CopiedHost& host;
    bool& active;
    ~DispatchScope() { host.end_dispatch(); active=false; }
};
struct AllocationScope {
    bool& active;
    explicit AllocationScope(bool& value):active(value) { active=true; }
    ~AllocationScope() { active=false; }
};
struct PairTurn {
    CopiedHost& host;
    bool entered{};
    explicit PairTurn(CopiedHost& value):host(value) {
        if(host.enter_engine()!=0) host.fail("Delivery outer native turn was not admitted");
        entered=true;
    }
    ~PairTurn() { if(entered) host.leave_engine(); }
};
}

BibEngineLimitsV1 documentCopiedLimits() noexcept {
    return documentCopiedLimits(DocumentWireProfile::pixel);
}
BibEngineLimitsV1 documentCopiedLimits(DocumentWireProfile profile) noexcept {
    if (profile==DocumentWireProfile::editor)
        return {sizeof(BibEngineLimitsV1),BIB_ENGINE_EDITOR_MAX_WIRE_BYTES,BIB_ENGINE_EDITOR_MAX_QUERY_BYTES,
            BIB_ENGINE_EDITOR_REPLY_CAPACITY,1048576,8,64,0,67108864,134217728};
    if (profile!=DocumentWireProfile::pixel && profile!=DocumentWireProfile::physical) return {};
    return {sizeof(BibEngineLimitsV1),6246,48,1048576,1048576,8,64,0,67108864,134217728};
}
CopiedDocumentDispatch::CopiedDocumentDispatch(const BibEngineProviderV1& provider,CopiedHost& host,
    std::string_view facts,std::uint64_t worker,DocumentWireProfile profile) noexcept
    :provider_(provider),host_(host),worker_(worker),profile_(profile) {
    valid_=worker && (profile==DocumentWireProfile::pixel || profile==DocumentWireProfile::physical || profile==DocumentWireProfile::editor) && provider.size==sizeof(provider)
        && provider.abi_major==1 && provider.abi_minor==1 && !provider.reserved
        && provider.start && provider.advance && provider.current_document && provider.command && provider.query
        && provider.deliver_services && provider.collect_service_ack && provider.dispose_retired_service_document
        && host.table().persistence==nullptr
        && documentCopiedFactsMatch(facts,provider.build,provider.limits,profile==DocumentWireProfile::editor?
            DocumentCopiedProfile::editor:profile==DocumentWireProfile::physical?DocumentCopiedProfile::physical:DocumentCopiedProfile::pixel);
    if (!valid_) return;
    try { facts_.assign(facts); }
    catch (...) { valid_=false; }
}

std::int32_t CopiedDocumentDispatch::dispatch(std::uint32_t op,std::span<const std::uint8_t> input,
    std::span<std::uint8_t> output) noexcept {
    // No provider/allocator/metadata access can recover a terminal dispatcher.
    if (host_.poisoned()) return -4;
    if (owner_!=std::this_thread::get_id() || active_) return -4;
    if (op>8) return -3;
    const auto requestLimit=profile_==DocumentWireProfile::editor && op==4?BIB_ENGINE_EDITOR_COPIED_COMMAND_MAX_BYTES:
        profile_==DocumentWireProfile::editor && op==5?BIB_ENGINE_EDITOR_COPIED_QUERY_MAX_BYTES:maxBodyBytes;
    if (input.size()>headerBytes+requestLimit || (!output.empty() && !output.data()) || overlap(input,output)) return -1;
    Record request;
    if (readRecord(op,input,request)!=Status::ok || !validDocumentEngineRequest(request,profile_)
        || request.worker!=worker_) return -1;
    const auto required=requiredDocumentEngineReplyBytes(request,profile_);
    if (!required) return -1;
    if (output.size()<required) return -2;
    if (!valid_) return -3;
    const auto reply=[&](Record record,std::uint32_t status,std::span<const std::uint8_t> body={},bool terminal=false) noexcept {
        std::size_t written=0;
        if (writeReply(record,status,body,output,written)!=Status::ok || written>INT32_MAX)
            host_.fail("Prepared complete document copied reply could not be written");
        if (terminal) host_.poison_after_result();
        return static_cast<std::int32_t>(written);
    };
    if (op==0) return reply(request,0,{reinterpret_cast<const std::uint8_t*>(facts_.data()),facts_.size()});
    if (op==1 && attempted_) return reply(request,6);
    if (op!=1 && (!started_ || request.instance!=instance_)) return reply(request,6);
    // Exact form replays and ACKs MUST reach ProviderGuard before checking the
    // current document. Guard alone owns retained old-document outcomes.
    DocumentWireOperation operation;
    if ((op==4 || op==5) && decodeDocumentOperation(request,operation,profile_)!=Status::ok) return -1;
    if (op!=1 && ((op!=4 && op!=6 && op!=7 && op!=8) || operation.physical ||
        (editorOperation(operation) && !historicalEditorRetirement(profile_,operation))) &&
        !same(identity(request),host_.current_identity())) return -1;
    DocumentStart config;
    AllocationScope allocationScope{active_};
    try { input_.assign(input.begin(),input.end()); }
    catch (...) { return reply(request,4); }
    Record captured;
    if (readRecord(op,input_,captured)!=Status::ok || !validDocumentEngineRequest(captured,profile_) ||
        captured.worker!=worker_ || captured.worker!=request.worker || captured.instance!=request.instance ||
        captured.document!=request.document || captured.generation!=request.generation ||
        captured.transfer!=request.transfer || captured.source!=request.source) return -1;
    if (op==1) {
        const auto parsed=decodeDocumentStart(captured.body,config,profile_);
        if (parsed==Status::invalid) return -1;
        if (parsed!=Status::ok) return reply(captured,4);
    }
    if ((op==4 || op==5) && decodeDocumentOperation(captured,operation,profile_)!=Status::ok) return -1;
    if (requiredDocumentEngineReplyBytes(captured,profile_)>output.size()) return -2;
    if (op!=1 && ((op!=4 && op!=6 && op!=7 && op!=8) || operation.physical ||
        (editorOperation(operation) && !historicalEditorRetirement(profile_,operation))) &&
        !same(identity(captured),host_.current_identity())) return -1;
    try { result_.assign(op==4||op==5?(operation.query?16u:24u)+operation.capacity:0u,0); }
    catch (...) { return reply(captured,4); }
    const bool editor=(op==4 || op==5) && editorOperation(operation);
    if (editor && !editorRequestValid(operation,captured)) return -1;
    const bool metadata=op==4 && operation.metadata_ack;
    if (!(metadata?host_.begin_metadata_dispatch(captured):host_.begin_dispatch(captured))) return -4;
    DispatchScope scope{host_,active_};
    auto resultRecord=captured;
    std::array<std::uint8_t,8> body{};
    switch (op) {
    case 1: {
        attempted_=true;
        BibEngineStartV1 start{}; start.size=sizeof(start); start.raster_output=config.raster_output;
        start.required_capabilities=profile_==DocumentWireProfile::editor?BIB_ENGINE_EDITOR_CAPABILITIES:
            profile_==DocumentWireProfile::physical?2003:1795; start.limits=documentCopiedLimits(profile_);
        start.entry_url={reinterpret_cast<const std::uint8_t*>(config.entry.data()),static_cast<std::uint32_t>(config.entry.size()),0};
        std::copy(config.packageSHA.begin(),config.packageSHA.end(),start.application_package_sha256);
        BibEngineStartResultV1 result{}; result.size=sizeof(result);
        const auto status=actual([&]{return provider_.start(&host_.table(),&start,&result);},host_);
        if (host_.local_depth() || status>0 || status<-8 || result.size!=sizeof(result) || result.phase>2)
            host_.fail("Malformed document START result");
        put32(body,static_cast<std::uint32_t>(status)); put32(std::span(body).subspan(4),result.phase);
        const auto adopted=host_.current_identity();
        if (status==0) {
            if (result.phase!=2 || !result.application_instance || adopted.application_instance!=result.application_instance)
                host_.fail("Document START did not adopt actual application identity");
            started_=true; instance_=result.application_instance; raster_output_=config.raster_output;
            useIdentity(resultRecord,adopted);
        } else if (result.phase>=1)
            useIdentity(resultRecord,{result.application_instance,adopted.document_sequence,adopted.service_generation});
        return reply(resultRecord,0,body,status==BIB_ENGINE_PROCESS_EXIT_REQUIRED);
    }
    case 2: {
        const BibEngineAdvanceV1 advance{sizeof(advance),first_ready_&&raster_output_?1u:0u,instance_};
        const auto status=actual([&]{return provider_.advance(&advance);},host_);
        useIdentity(resultRecord,host_.current_identity()); return reply(resultRecord,control(status,host_));
    }
    case 3: {
        BibEngineDocumentV1 current{};
        const auto status=actual([&]{return provider_.current_document(instance_,&current);},host_);
        if (!status) {
            if (!current.document_sequence || !current.service_generation || current.application_instance!=instance_)
                host_.fail("CURRENT did not return actual ready document identity");
            first_ready_=true; useIdentity(resultRecord,current);
        }
        return reply(resultRecord,control(status,host_));
    }
    case 4: {
        BibEngineCommandV1 command{}; command.size=sizeof(command); command.operation=operation.operation;
        command.expected=identity(captured); command.request_sequence=operation.sequence;
        std::copy(operation.schema.begin(),operation.schema.end(),command.schema_sha256);
        command.payload={operation.payload.data(),static_cast<std::uint32_t>(operation.payload.size()),0};
        BibEngineReplyBufferV1 buffer{sizeof(buffer),operation.capacity,result_.data()+24};
        BibEngineCommandResultV1 result{}; result.size=sizeof(result);
        const auto status=actual([&]{return provider_.command(&command,&buffer,&result);},host_);
        if (host_.local_depth() || buffer.size!=sizeof(buffer) || buffer.capacity!=operation.capacity ||
            buffer.bytes!=result_.data()+24 || result.size!=sizeof(result) || status>0 || status<-8 ||
            result.disposition>2 || result.handled>1 || result.bytes_written>operation.capacity ||
            result.request_sequence!=operation.sequence ||
            (result.disposition==1 && status!=0) ||
            (result.disposition==0 && (status==0 || result.handled || result.bytes_written)))
            host_.fail("Malformed or unbalanced document command result");
        const bool uncertain=status==BIB_ENGINE_PROCESS_EXIT_REQUIRED || result.disposition==2;
        const auto bytes=std::span<const std::uint8_t>(result_).subspan(24,result.bytes_written);
        // Physical commands have no reply payload, including uncertain returns.
        // Their native scratch reservation16 is separate from copied receipt104.
        if (operation.physical && (result.bytes_written ||
            (result.disposition!=1 && result.handled) || (result.disposition==2 && status==0)))
            host_.fail("Malformed physical command result");
        // Uncertain document/editor bytes and handled remain opaque forensic
        // evidence. Decode only a known successful result, never invent replay.
        if (!operation.physical && !uncertain && result.disposition==1) {
            if (editor) {
                if (!editorCommandReplyValid(bytes,captured,operation.sequence))
                    host_.fail("Editor command result changed full native key/known result grammar");
            } else if (metadata) {
                if (bytes.size()!=16 || result.handled || get64(bytes)!=get64(operation.payload) ||
                    get32(bytes.subspan(8))>2 || get32(bytes.subspan(12)))
                    host_.fail("Malformed document metadata ACK result");
            } else if (bytes.size()<52 || get32(bytes)!=0x3256444e || bytes[4]!=2 || bytes[5] ||
                bytes[6]!=5 || bytes[7] || get64(bytes.subspan(8))!=captured.instance ||
                get64(bytes.subspan(16))!=captured.generation || get64(bytes.subspan(24))!=captured.document ||
                get64(bytes.subspan(32))!=operation.sequence || get64(bytes.subspan(40)))
                host_.fail("Document command result changed native fixed joins");
        }
        put32(result_,static_cast<std::uint32_t>(status)); put32(std::span(result_).subspan(4),result.disposition);
        for (unsigned i=0;i<8;++i) result_[8+i]=static_cast<std::uint8_t>(operation.sequence>>(i*8));
        put32(std::span(result_).subspan(16),result.bytes_written); put32(std::span(result_).subspan(20),result.handled);
        return reply(resultRecord,0,std::span<const std::uint8_t>(result_).first(24+result.bytes_written),uncertain);
    }
    case 5: {
        BibEngineQueryV1 query{}; query.size=sizeof(query); query.kind=operation.operation; query.expected=identity(captured);
        std::copy(operation.schema.begin(),operation.schema.end(),query.schema_sha256);
        query.payload={operation.payload.data(),static_cast<std::uint32_t>(operation.payload.size()),0};
        BibEngineReplyBufferV1 buffer{sizeof(buffer),operation.capacity,result_.data()+16};
        BibEngineQueryResultV1 result{}; result.size=sizeof(result);
        const auto status=actual([&]{return provider_.query(&query,&buffer,&result);},host_);
        if (host_.local_depth() || buffer.size!=sizeof(buffer) || buffer.capacity!=operation.capacity ||
            buffer.bytes!=result_.data()+16 || result.size!=sizeof(result) || status>0 || status<-8 ||
            result.bytes_written>operation.capacity || (status && (!editor || status!=BIB_ENGINE_PROCESS_EXIT_REQUIRED) &&
                (result.bytes_written || result.semantic_revision)))
            host_.fail("Malformed or unbalanced document query result");
        const auto bytes=std::span<const std::uint8_t>(result_).subspan(16,result.bytes_written);
        // Only explicit editor status-8 may carry bounded opaque query evidence.
        // It is copied once with its raw revision, then poisons the route. The
        // actual Guard normally exports zero here; no semantic decode/retry is
        // inferred from a naturally returned transport-unknown record.
        if (!status) {
            if (!same(result.document,query.expected) || !result.semantic_revision)
                host_.fail("Query result changed original document/revision");
            if (editor) {
                if (!editorQueryReplyValid(bytes,captured,operation.sequence,result.semantic_revision))
                    host_.fail("Editor query result changed full native key/observation revision");
            } else if (bytes.size()<134 || get32(bytes)!=0x3256444e || bytes[4]!=2 || bytes[5] || bytes[6]!=4 || bytes[7] ||
                get64(bytes.subspan(8))!=captured.instance || get64(bytes.subspan(16))!=captured.generation ||
                get64(bytes.subspan(24))!=captured.document || get64(bytes.subspan(32))!=operation.sequence ||
                get64(bytes.subspan(40))!=get64(operation.payload.subspan(40)) ||
                get64(bytes.subspan(88))!=result.semantic_revision)
                host_.fail("Document query result changed original native joins/revision");
        }
        put32(result_,static_cast<std::uint32_t>(status)); put32(std::span(result_).subspan(4),result.bytes_written);
        for (unsigned i=0;i<8;++i) result_[8+i]=static_cast<std::uint8_t>(result.semantic_revision>>(i*8));
        return reply(resultRecord,0,std::span<const std::uint8_t>(result_).first(16+result.bytes_written),
            status==BIB_ENGINE_PROCESS_EXIT_REQUIRED);
    }
    case 6: {
        const auto doc=identity(captured);
        const BibEngineBytesV1 completion{captured.body.data(),static_cast<std::uint32_t>(captured.body.size()),0};
        std::uint32_t disposition=2;
        {
            PairTurn turn(host_);
            const auto code=actual([&]{return provider_.deliver_services(&doc,&completion);},host_);
            if(code==0) {
                host_.clear_ack_observation();
                const auto status=actual([&]{return provider_.collect_service_ack(&doc);},host_);
                const auto observed=host_.ack_observation();
                if(status>13 || observed.count>1 || (!observed.count && status!=0 && status!=2) || (observed.count &&
                    (!same(observed.document,doc) || !observed.through || observed.control!=0 || status!=2 || observed.status!=status)))
                    host_.fail("Initial ACK staging returned malformed or uncertain result");
                // A navigation/close may make the guarded collector return2
                // without callback. Accept real delivery; never claim an ACK.
                disposition=1;
            } else if(code!=-1 && code!=-5 && code!=-6) host_.fail("Terminal actual completion delivery result");
        }
        put32(body,disposition); return reply(resultRecord,0,std::span(body).first(4));
    }
    case 7: {
        const auto doc=identity(captured); const auto through=get64(captured.body);
        const auto expected=get32(captured.body.subspan(8));
        if(expected>13) host_.fail("Uncertain ACK receipt supplied for collection");
        host_.clear_ack_observation();
        const auto status=actual([&]{return provider_.collect_service_ack(&doc);},host_);
        const auto observed=host_.ack_observation();
        if(observed.count!=1 || observed.control!=0 || !same(observed.document,doc) || observed.through!=through
            || observed.status!=expected || status!=expected)
            host_.fail("ACK collection did not read the exact cached actual receipt");
        put32(body,status==0?1u:2u); return reply(resultRecord,0,std::span(body).first(4));
    }
    case 8: {
        const auto doc=identity(captured);
        const auto code=actual([&]{return provider_.dispose_retired_service_document(instance_,doc.service_generation);},host_);
        if(code!=0) host_.fail("Actual retired controller disposal failed; retry forbidden");
        if(!host_.forget_disposed_document(doc)) host_.fail("Disposed document was not the exact retained callback identity");
        put32(body,0); return reply(resultRecord,0,std::span(body).first(4));
    }
    default:host_.fail("Unreachable copied operation");
    }
}
} // namespace bib::copied
