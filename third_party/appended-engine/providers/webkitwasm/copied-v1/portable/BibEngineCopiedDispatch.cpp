// SPDX-License-Identifier: CC0-1.0
#include "BibEngineCopiedDispatch.h"
#include <algorithm>
#include <array>
#include <climits>
#include <cstring>
#include <limits>
#include <vector>

namespace bib::copied {
namespace {
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
bool nonzero(const std::uint8_t* p) noexcept {
    return std::any_of(p,p+32,[](auto c){return c!=0;});
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

BibEngineLimitsV1 copiedLimits() noexcept {
    return {sizeof(BibEngineLimitsV1),33120,1,16,1048576,8,64,0,67108864,134217728};
}
CopiedDispatch::CopiedDispatch(const BibEngineProviderV1& p,CopiedHost& h,std::string_view profile) noexcept
    :provider_(p),host_(h),profile_(profile) {
    const auto& b=p.build;
    valid_=p.size==sizeof(p) && p.abi_major==1 && p.abi_minor==0 && !p.reserved
        && b.size==sizeof(b) && b.layout_revision==1 && b.target_system==BIB_ENGINE_TARGET_BROWSER_WASM
        && b.target_processor==BIB_ENGINE_CPU_WASM32 && b.pointer_bits==32 && b.lifetime==1
        && b.maximum_starts==1 && !b.reserved && b.fixed_viewport_width==800 && b.fixed_viewport_height==600
        && b.capabilities==259 && nonzero(b.contract_header_sha256) && nonzero(b.build_identity_sha256)
        && nonzero(b.source_recipe_sha256) && p.start && p.advance && p.current_document && p.deliver_services
        && p.collect_service_ack && p.dispose_retired_service_document && !profile.empty() && profile.size()<=1024
        && h.table().persistence==nullptr;
    const auto fixed=copiedLimits();
    const auto& l=p.limits;
    valid_=valid_ && l.size==sizeof(l) && !l.reserved
        && l.maximum_command_bytes>=fixed.maximum_command_bytes && l.maximum_query_bytes>=fixed.maximum_query_bytes
        && l.maximum_reply_bytes>=fixed.maximum_reply_bytes && l.maximum_service_message_bytes>=fixed.maximum_service_message_bytes
        && l.maximum_retired_documents>=fixed.maximum_retired_documents && l.maximum_inflight_resources>=fixed.maximum_inflight_resources
        && l.maximum_resource_response_bytes>=fixed.maximum_resource_response_bytes
        && l.maximum_retained_resource_bytes>=fixed.maximum_retained_resource_bytes;
}

std::int32_t CopiedDispatch::dispatch(std::uint32_t op,std::span<const std::uint8_t> input,
    std::span<std::uint8_t> output) noexcept {
    // Reject complete-capacity/shape/aliasing errors before retaining/calling.
    const auto required=requiredEngineReplyBytes(op);
    if(!required) return -3;
    if(output.size()<required) return -2;
    if(input.size()>maxBodyBytes+headerBytes || overlap(input,output)) return -1;
    Record request;
    if(readRecord(op,input,request)!=Status::ok || !validEngineRequest(request)) return -1;
    if(!valid_) return -3;
    if(owner_!=std::this_thread::get_id() || active_ || host_.poisoned()) return -4;
    if(worker_ && worker_!=request.worker) return -1;
    auto reply=[&](Record r,std::uint32_t status,std::span<const std::uint8_t> body={}) noexcept {
        std::size_t written=0;
        if(writeReply(r,status,body,output,written)!=Status::ok || written>INT32_MAX)
            host_.fail("Prepared complete copied reply could not be written");
        return static_cast<std::int32_t>(written);
    };
    if(op==0) return reply(request,0,{reinterpret_cast<const std::uint8_t*>(profile_.data()),profile_.size()});
    // Known-but-unadvertised operations have no allocations or provider turns.
    if(op==4 || op==5) return reply(request,7);
    if(op==1 && attempted_) return reply(request,6);
    if(op!=1 && (!started_ || request.instance!=instance_)) return reply(request,6);
    if(op==1 && (request.instance || request.document || request.generation)) return -1;
    if(op!=1 && op!=6 && op!=7 && op!=8 && !same(identity(request),host_.current_identity())) return -1;

    std::vector<std::uint8_t> retained;
    Start config;
    try { retained.assign(input.begin(),input.end()); } catch(...) { return reply(request,4); }
    Record captured;
    if(readRecord(op,retained,captured)!=Status::ok) return -1;
    if(op==1) {
        const auto parsed=decodeStart(captured.body,config);
        if(parsed==Status::invalid) return -1;
        if(parsed!=Status::ok) return reply(request,4);
    }
    if(!host_.begin_dispatch(captured)) return -4;
    active_=true; worker_=captured.worker;
    DispatchScope dispatchScope{host_,active_};
    auto resultRecord=captured;
    std::array<std::uint8_t,8> body{};
    switch(op) {
    case 1: {
        attempted_=true;
        BibEngineStartV1 start{};
        start.size=sizeof(start); start.raster_output=1; start.required_capabilities=259; start.limits=copiedLimits();
        start.entry_url={reinterpret_cast<const std::uint8_t*>(config.entry.data()),static_cast<std::uint32_t>(config.entry.size()),0};
        std::copy(config.packageSHA.begin(),config.packageSHA.end(),start.application_package_sha256);
        BibEngineStartResultV1 result{}; result.size=sizeof(result);
        const auto code=actual([&]{return provider_.start(&host_.table(),&start,&result);},host_);
        if(code>0 || code<-8 || result.size!=sizeof(result) || result.phase>2)
            host_.fail("Malformed actual START result");
        put32(body,static_cast<std::uint32_t>(code)); put32(std::span(body).subspan(4),result.phase);
        const auto adopted=host_.current_identity();
        if(code==0) {
            if(result.phase!=2 || !result.application_instance || adopted.application_instance!=result.application_instance)
                host_.fail("START did not retain the actual adopted application instance");
            started_=true; instance_=result.application_instance; useIdentity(resultRecord,adopted);
        } else if(result.phase>=1) useIdentity(resultRecord,{result.application_instance,adopted.document_sequence,adopted.service_generation});
        return reply(resultRecord,0,body);
    }
    case 2: {
        const BibEngineAdvanceV1 advance{sizeof(advance),first_ready_?1u:0u,instance_};
        const auto code=actual([&]{return provider_.advance(&advance);},host_);
        useIdentity(resultRecord,host_.current_identity());
        return reply(resultRecord,control(code,host_));
    }
    case 3: {
        BibEngineDocumentV1 current{};
        const auto code=actual([&]{return provider_.current_document(instance_,&current);},host_);
        if(code==0) {
            if(!current.document_sequence || !current.service_generation || current.application_instance!=instance_)
                host_.fail("CURRENT did not return an actual nonzero ready identity");
            first_ready_=true; useIdentity(resultRecord,current);
        }
        return reply(resultRecord,control(code,host_));
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
