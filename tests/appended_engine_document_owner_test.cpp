#include "../gui/shared/appended_engine_owner.hpp"
#include "../gui/shared/appended_engine_abi.h"
#include "../gui/shared/appended_engine_input_codec.hpp"
#include "../gui/shared/engine_document_mailbox.hpp"

#include <algorithm>
#include <array>
#include <cstdlib>
#include <new>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <thread>
#include <type_traits>
#include <utility>

// Count C++ allocation attempts only inside the explicitly armed destructor
// interval. All reporting/assertion allocations happen after disarming.
namespace allocation_probe { thread_local bool armed=false;thread_local std::size_t calls=0; }
void* operator new(std::size_t size){
    if(allocation_probe::armed)++allocation_probe::calls;
    if(void* pointer=std::malloc(size?size:1))return pointer;
    throw std::bad_alloc();
}
void* operator new[](std::size_t size){return ::operator new(size);}
void operator delete(void* pointer)noexcept{std::free(pointer);}
void operator delete[](void* pointer)noexcept{std::free(pointer);}
void operator delete(void* pointer,std::size_t)noexcept{std::free(pointer);}
void operator delete[](void* pointer,std::size_t)noexcept{std::free(pointer);}
void* operator new(std::size_t size,const std::nothrow_t&)noexcept{try{return ::operator new(size);}catch(...){return nullptr;}}
void* operator new[](std::size_t size,const std::nothrow_t&)noexcept{try{return ::operator new(size);}catch(...){return nullptr;}}
void operator delete(void* pointer,const std::nothrow_t&)noexcept{std::free(pointer);}
void operator delete[](void* pointer,const std::nothrow_t&)noexcept{std::free(pointer);}
void* operator new(std::size_t size,std::align_val_t alignment){
    if(allocation_probe::armed)++allocation_probe::calls;
    const auto align=static_cast<std::size_t>(alignment),extra=align-1+sizeof(void*);
    if(size>std::numeric_limits<std::size_t>::max()-extra)throw std::bad_alloc();
    void* raw=std::malloc((size?size:1)+extra);if(!raw)throw std::bad_alloc();
    const auto start=reinterpret_cast<std::uintptr_t>(raw)+sizeof(void*);
    const auto address=(start+align-1)&~(static_cast<std::uintptr_t>(align)-1);
    auto* pointer=reinterpret_cast<void*>(address);reinterpret_cast<void**>(pointer)[-1]=raw;return pointer;
}
void* operator new[](std::size_t size,std::align_val_t alignment){return ::operator new(size,alignment);}
void operator delete(void* pointer,std::align_val_t)noexcept{if(pointer)std::free(reinterpret_cast<void**>(pointer)[-1]);}
void operator delete[](void* pointer,std::align_val_t alignment)noexcept{::operator delete(pointer,alignment);}
void operator delete(void* pointer,std::size_t,std::align_val_t alignment)noexcept{::operator delete(pointer,alignment);}
void operator delete[](void* pointer,std::size_t,std::align_val_t alignment)noexcept{::operator delete(pointer,alignment);}
void* operator new(std::size_t size,std::align_val_t alignment,const std::nothrow_t&)noexcept{try{return ::operator new(size,alignment);}catch(...){return nullptr;}}
void* operator new[](std::size_t size,std::align_val_t alignment,const std::nothrow_t&)noexcept{try{return ::operator new(size,alignment);}catch(...){return nullptr;}}
void operator delete(void* pointer,std::align_val_t alignment,const std::nothrow_t&)noexcept{::operator delete(pointer,alignment);}
void operator delete[](void* pointer,std::align_val_t alignment,const std::nothrow_t&)noexcept{::operator delete(pointer,alignment);}

namespace {
using namespace foundation::appended;
namespace doc = engine_document;
namespace input = engine_input;
using Span = std::span<const std::uint8_t>;
static_assert(noexcept(std::declval<EngineOwner&>().notify_document_terminal()));
static_assert(std::is_same_v<decltype(std::declval<EngineOwner&>().notify_document_terminal()),void>);
std::size_t assertions{};
void check(bool value, const char* message) { ++assertions; if (!value) throw std::runtime_error(message); }
void put(std::span<std::uint8_t> out, std::size_t offset, std::uint64_t value, unsigned count) {
    check(offset<=out.size() && count<=out.size()-offset,"fixture write bounds");
    for (unsigned i=0;i<count;++i) out[offset+i]=static_cast<std::uint8_t>(value>>(i*8));
}
std::uint64_t get(Span bytes, std::size_t offset, unsigned count) {
    check(offset<=bytes.size() && count<=bytes.size()-offset,"fixture read bounds");
    std::uint64_t value{}; for (unsigned i=0;i<count;++i) value|=std::uint64_t(bytes[offset+i])<<(i*8); return value;
}
EngineDocumentTarget target(EngineIdentity id) { return {id.worker_epoch,id.application_instance,id.document_sequence,id.service_generation}; }
EngineIdentity identity(EngineDocumentTarget id) { return {id.worker_epoch,id.application_instance,id.document_sequence,id.service_generation}; }
Bytes record(std::uint32_t operation, EngineIdentity id, Span body={}, std::uint64_t transfer=0) {
    Bytes out(72+body.size()); std::copy_n("FKB1",4,out.begin()); put(out,4,1,2); put(out,6,operation,2); put(out,8,out.size(),4);
    put(out,16,id.worker_epoch,8); put(out,24,id.application_instance,8); put(out,32,id.document_sequence,8);
    put(out,40,id.service_generation,8); put(out,48,transfer,8); put(out,64,body.size(),4);
    std::copy(body.begin(),body.end(),out.begin()+72); return out;
}
struct Reply { EngineIdentity id; std::uint64_t transfer{}; std::uint32_t control{},service{}; Bytes bytes;
    Span body() const { return Span(bytes).subspan(80); } };
Reply call(EngineOwner& owner,std::uint32_t operation,EngineIdentity id,Span body={},std::uint64_t transfer=0,std::size_t capacity=1048800) {
    const auto request=record(operation,id,body,transfer); Bytes out(capacity,0xa5);
    const auto result=owner.dispatch(operation,request,out);
    check(result>=80 && static_cast<std::size_t>(result)<=out.size(),"owner did not return complete copied receipt");
    out.resize(static_cast<std::size_t>(result));
    check(get(out,6,2)==(operation|0x8000) && get(out,8,4)==out.size() && get(out,64,4)==out.size()-72,"copied reply framing changed");
    return {{get(out,16,8),get(out,24,8),get(out,32,8),get(out,40,8)},get(out,48,8),
        static_cast<std::uint32_t>(get(out,72,4)),static_cast<std::uint32_t>(get(out,76,4)),std::move(out)};
}
std::size_t reset_without_allocation(std::unique_ptr<EngineOwner>& owner) noexcept{
    allocation_probe::calls=0;allocation_probe::armed=true;owner.reset();allocation_probe::armed=false;return allocation_probe::calls;
}
std::size_t notify_without_allocation(EngineOwner& owner) noexcept{
    allocation_probe::calls=0;allocation_probe::armed=true;
    owner.notify_document_terminal();owner.notify_document_terminal();
    allocation_probe::armed=false;return allocation_probe::calls;
}
void ok(const Reply& result,const char* message="owner rejected expected operation") { check(result.control==0 && result.service==0,message); }
void short_reply(EngineOwner& owner,std::uint32_t operation,EngineIdentity id,Span body,std::uint64_t transfer,std::size_t capacity) {
    const auto request=record(operation,id,body,transfer); Bytes out(capacity,0xa5);
    check(owner.dispatch(operation,request,out)==FOUNDATION_ENGINE_REPLY_TOO_SMALL &&
        std::all_of(out.begin(),out.end(),[](auto byte){return byte==0xa5;}),"short output admitted or changed copied state");
}
Package package() {
    Package p; p.application={"org.example.document-owner","Document mailbox fixture","1.0.0"};
    p.web.present=true; p.web.entry="web/index.html"; p.capabilities={"foundation.startup.v1"}; p.package_sha256=std::string(64,'1');
    const std::string startup="{\"kind\":\"foundation-appended-startup\",\"primary\":\"web\",\"schema_version\":1}";
    p.files={{"web/.foundation/startup-v1.json","web","application/json",std::string(64,'2'),Bytes(startup.begin(),startup.end())},
        {"web/index.html","web","text/html",std::string(64,'3'),{}}}; return p;
}
doc::EngineDocumentProfileFacts facts(bool physical=false) {
    doc::EngineDocumentProfileFacts f; f.enabled=true; f.kind=physical?doc::ProfileKind::physical:doc::ProfileKind::pixel;
    f.name=physical?doc::kPhysicalProfileName:doc::kPixelProfileName; f.provider_abi_major=1; f.provider_abi_minor=1; f.host_abi_major=1;
    f.target_system=BIB_ENGINE_TARGET_LINUX; f.target_processor=BIB_ENGINE_CPU_X86_64; f.pointer_bits=64;
    f.lifetime=BIB_ENGINE_LIFETIME_PROCESS; f.maximum_starts=1; f.viewport_width=800; f.viewport_height=600;
    f.provider_capabilities=physical?2003:1795; f.base_header_sha256=doc::kBaseHeaderSha256;
    f.extension_header_sha256=doc::kExtensionHeaderSha256; f.contract_sha256=doc::kContractSha256; f.catalog_sha256=doc::kCatalogSha256;
    // Explicit synthetic fixture pins: no retained provider/runtime is represented.
    f.build_sha256[0]=1; f.source_recipe_sha256[0]=2;
    if(physical)f.physical_catalog_sha256=doc::kPhysicalCatalogSha256;
    f.queries=doc::kQueries; f.commands=doc::kCommands; f.query_count=1; f.command_count=2; return f;
}
Bytes ndv2(EngineDocumentTarget id,std::uint64_t sequence,unsigned kind,std::uint64_t nested=0,std::size_t length=48) {
    Bytes out(length); out[0]='N';out[1]='D';out[2]='V';out[3]='2';out[4]=2;out[6]=static_cast<std::uint8_t>(kind);
    put(out,8,id.application_instance,8);put(out,16,id.service_generation,8);put(out,24,id.document_sequence,8);
    put(out,32,sequence,8);put(out,40,nested,8);return out;
}
EngineDocumentWork work(EngineDocumentTarget id,std::uint64_t sequence,bool form=false) {
    EngineDocumentWork w;w.target=id;w.request_sequence=sequence;w.kind=form?EngineDocumentWorkKind::form_action:EngineDocumentWorkKind::snapshot_query;
    w.operation=form?6:3;w.required_reply_capacity=1048576;w.schema_sha256=doc::kSchema;
    w.payload=ndv2(id,sequence,form?2:1,form?0:73,form?81:48);
    if(form){put(w.payload,49,id.application_instance,8);put(w.payload,57,id.service_generation,8);put(w.payload,65,1,8);put(w.payload,73,1,8);}return w;
}
Bytes claim_bytes(EngineDocumentWorkKind kind,std::uint64_t sequence) {Bytes out(16);put(out,0,static_cast<std::uint32_t>(kind),4);put(out,8,sequence,8);return out;}
Bytes result_bytes(const EngineDocumentDispatch& d,Span raw,std::int32_t status=0,std::uint32_t disposition=0,std::uint32_t handled=0,std::uint64_t revision=0) {
    Bytes out(40+raw.size());put(out,0,static_cast<std::uint32_t>(d.work.kind),4);put(out,8,d.work.request_sequence,8);
    put(out,16,static_cast<std::uint32_t>(status),4);put(out,20,disposition,4);put(out,24,raw.size(),4);put(out,28,handled,4);put(out,32,revision,8);
    std::copy(raw.begin(),raw.end(),out.begin()+40);return out;
}
Bytes success_bytes(const EngineDocumentDispatch& d) {
    const bool form=d.work.kind==EngineDocumentWorkKind::form_action;
    auto raw=ndv2(d.work.target,d.work.request_sequence,form?5:4,form?0:73,form?52:48);
    if(form){raw[48]=1;raw[49]=6;} // Fixed-header Owner join only; no valid deep NDV2/runtime claim.
    return result_bytes(d,raw,0,form?1:0,0,form?0:17);
}
Bytes ack_raw(std::uint64_t original,unsigned code=0) {Bytes out(16);put(out,0,original,8);put(out,8,code,4);return out;}
struct ModuleCounters { unsigned factories{},constructed{},close_calls{},destroyed{},callbacks{}; };
class CountedModule final : public EngineModuleBinding {
    std::shared_ptr<ModuleCounters> counters_;std::uint64_t generation_;
public:
    CountedModule(std::shared_ptr<ModuleCounters> counters,std::uint64_t generation):counters_(std::move(counters)),generation_(generation){++counters_->constructed;}
    ~CountedModule() override{++counters_->destroyed;}
    WebModuleServices services() override{
        return {generation_,[counts=counters_](const DiscoveryQuery&){++counts->callbacks;return ProviderDiscovery{};},
            [counts=counters_](const ProviderRequest&){++counts->callbacks;return ProviderOutcome{};},
            [counts=counters_](std::uint64_t){++counts->callbacks;return ServiceStatus::ok;},
            [counts=counters_,next=std::uint64_t{1}]()mutable->std::optional<std::uint64_t>{++counts->callbacks;return next++;}};
    }
    void close() noexcept override{++counters_->close_calls;}
};
struct Fixture {
    static constexpr std::string_view service_name="org.example.document-owner.native";
    EngineIdentity id{17,UINT64_C(0x8000000000000023),0,0};
    std::unique_ptr<EngineOwner> owner;
    unsigned effects{};bool safe_publication{},hold_on_entry{};std::uint64_t held{};
    std::shared_ptr<ModuleCounters> module_counters;
    explicit Fixture(bool physical=false,bool native=false,bool abandon=false,
                     std::shared_ptr<ModuleCounters> counters={},bool configure=true):module_counters(std::move(counters)) {
        EngineOwnerConfiguration c;c.worker_epoch=id.worker_epoch;c.application_instance=id.application_instance;c.document_profile=facts(physical);
        c.abandon_closed_document_outcomes=abandon;
        if(native)c.native_services.push_back({{std::string(service_name),1,0,SchemaId{7},4},[this](std::uint32_t op,Span bytes,std::span<std::uint8_t> out)->ServiceReply{
            const auto effect=owner->native_effect();check(op==1&&bytes.size()==4&&out.size()>=4&&effect&&effect->entered&&safe_publication,
                "actual Registry handler entered before safe document publication");
            if(hold_on_entry){check(owner->hold_native_effect(effect->ticket),"native UI hold rejected");held=effect->ticket;}
            ++effects;std::copy(bytes.begin(),bytes.end(),out.begin());return{ServiceStatus::ok,4};}});
        auto payload=package();
        if(module_counters){payload.binary={true,"binary/application.wasm","foundation-guest-v1"};
            // Package::find_file requires the verified file table's path order.
            payload.files.insert(payload.files.begin(),{"binary/application.wasm","binary","application/wasm",std::string(64,'4'),{0}});
            c.module_factory=[counts=module_counters](auto,auto,std::uint64_t generation)->std::unique_ptr<EngineModuleBinding>{
                ++counts->factories;return std::make_unique<CountedModule>(counts,generation);};}
        owner=std::make_unique<EngineOwner>(std::move(payload),std::move(c));if(!configure)return;
        ok(call(*owner,1,id));
        id.document_sequence=UINT64_C(0x8000000000000001);const auto begun=call(*owner,4,id);ok(begun);id=begun.id;
    }
    EngineDocumentWork next(bool form=false){const auto s=owner->reserve_document_sequence();check(bool(s),"ordinary sequence reservation unavailable");return work(target(id),*s,form);}
    EngineDocumentAdmission stage(EngineDocumentWork w){auto a=owner->stage_document_work(std::move(w));check(a.code==EngineDocumentAdmissionCode::admitted&&a.ticket,"valid document work rejected");return a;}
    Reply peek_raw(){return call(*owner,FOUNDATION_ENGINE_PEEK_DOCUMENT_WORK,id);}
    EngineDocumentDispatch peek(){const auto r=peek_raw();ok(r);check(r.transfer&&r.body().size()>=56,"document peek body missing");EngineDocumentDispatch d;
        d.transfer=r.transfer;d.work.target=target(r.id);d.work.kind=static_cast<EngineDocumentWorkKind>(get(r.body(),0,4));d.work.operation=static_cast<std::uint32_t>(get(r.body(),4,4));
        d.work.request_sequence=get(r.body(),8,8);std::copy_n(r.body().begin()+16,32,d.work.schema_sha256.begin());d.work.required_reply_capacity=static_cast<std::uint32_t>(get(r.body(),48,4));
        check(get(r.body(),52,4)==r.body().size()-56,"document peek length changed");d.work.payload.assign(r.body().begin()+56,r.body().end());return d;}
    void claim(const EngineDocumentDispatch& d){ok(call(*owner,29,identity(d.work.target),claim_bytes(d.work.kind,d.work.request_sequence),d.transfer));}
    void turn(const EngineDocumentDispatch& d){ok(call(*owner,2,identity(d.work.target),{},d.transfer));ok(call(*owner,3,identity(d.work.target),{},d.transfer));}
    void settle(const EngineDocumentDispatch& d,Bytes result){ok(call(*owner,28,identity(d.work.target),result,d.transfer));}
    std::shared_ptr<const EngineDocumentCompletion> finish(EngineDocumentAdmission a,bool form=false){auto d=peek();claim(d);if(d.work.kind!=EngineDocumentWorkKind::action_ack)turn(d);
        auto result=form?success_bytes(d):success_bytes(d);settle(d,result);auto value=owner->document_outcome(a.ticket);check(bool(value),"document result not retained");return value;}
    EngineDocumentAdmission ack(EngineDocumentTarget t,std::uint64_t original){auto a=owner->stage_document_action_ack(t,original);check(a.code==EngineDocumentAdmissionCode::admitted&&a.ticket,"valid action ACK rejected");return a;}
    void finish_ack(EngineDocumentAdmission a,std::uint64_t original,unsigned code=0){const auto d=peek();const auto payload=encode_engine_document_action_ack(original);check(payload&&d.work.kind==EngineDocumentWorkKind::action_ack&&d.work.payload==Bytes(payload->begin(),payload->end()),"ACK did not retain original sequence");claim(d);
        settle(d,result_bytes(d,ack_raw(original,code),0,1));check(bool(owner->document_outcome(a.ticket)),"ACK result missing");}
};
void profile_gates_and_frozen_admission(){
    Fixture pixel;check(pixel.owner->document_enabled()&&!pixel.owner->input_enabled(),"pixel1795 acquired physical capability");
    Fixture physical(true);check(physical.owner->document_enabled()&&physical.owner->input_enabled(),"physical2003 omitted shared input route");
    check(pixel.owner->document_profile()==facts()&&physical.owner->document_profile()==facts(true),"read-only compiled document facts changed");
    EngineOwnerConfiguration disabled;disabled.worker_epoch=17;disabled.application_instance=23;EngineOwner old(package(),disabled);
    ok(call(old,1,{17,23,0,0}));const auto id=call(old,4,{17,23,1,0}).id;
    check(notify_without_allocation(old)==0&&old.configured()&&!old.closed()&&old.identity()==id&&old.callback_depth()==0,
          "legacy terminal notification allocated or changed its ordinary route");
    Fixture after_legacy_notification;check(after_legacy_notification.owner->document_enabled(),
          "legacy no-op notification poisoned later document-profile construction");
    for(auto op:{27u,28u,29u}){const auto r=record(op,id);Bytes out(80);check(old.dispatch(op,r,out)==FOUNDATION_ENGINE_BAD_OPERATION,"legacy profile admitted document mailbox operation");}
    check(!old.document_enabled()&&!old.reserve_document_sequence(),"legacy profile allocated document sequence");
    auto invalid=facts();invalid.provider_abi_minor=0;EngineOwnerConfiguration c;c.document_profile=invalid;bool rejected=false;
    try{EngineOwner bad(package(),c);}catch(const std::invalid_argument&){rejected=true;}check(rejected,"invalid document profile reached initialized owner");
}
void reservation_burn_and_global_physical_order(){
    Fixture f(true);const auto burned=f.owner->reserve_document_sequence();check(burned&&*burned==1,"first global sequence changed");
    check(!f.owner->cancel_document_sequence(*burned+1)&&!f.owner->reserve_document_sequence(),"foreign cancellation released reservation");
    Bytes focus;check(input::encode_focus({1,0,0,0,7,0},focus)==input::Status::ok,"focus fixture invalid");
    check(!f.owner->stage_command(f.id,7,3,input::kFocusSchema,focus,true),"physical command overtook held ordinary reservation");
    check(f.owner->cancel_document_sequence(*burned)&&!f.owner->cancel_document_sequence(*burned),"cancellation did not burn exact reservation once");
    const auto physical=f.owner->stage_command(f.id,7,3,input::kFocusSchema,focus,true);check(physical&&*physical>*burned,"physical sequence rewound cancelled reservation");
    auto r=call(*f.owner,15,f.id);ok(r);input::Command command;check(input::decode_command(r.body(),command)==input::Status::ok&&command.request_sequence==*physical,"physical ticket lost global sequence");
    ok(call(*f.owner,2,r.id,{},r.transfer));ok(call(*f.owner,3,r.id,{},r.transfer));Bytes outcome;check(input::encode_command_result({0,1,*physical,0,0},outcome)==input::Status::ok,"physical result invalid");ok(call(*f.owner,19,r.id,outcome,r.transfer));
    auto query=f.next();check(query.request_sequence>*physical,"query did not share physical sequence allocator");auto qa=f.stage(query);f.finish(qa);check(f.owner->consume_document_outcome(qa.ticket),"query local consumption rejected");
    auto form=f.next(true);check(form.request_sequence>query.request_sequence,"form sequence did not follow query");auto fa=f.stage(form);f.finish(fa,true);
    const auto aa=f.ack(form.target,form.request_sequence);const auto d=f.peek();check(d.work.request_sequence>form.request_sequence,"ACK sequence collided with form sequence");f.finish_ack(aa,form.request_sequence);
    check(f.owner->consume_document_outcome(aa.ticket)&&f.owner->consume_document_outcome(fa.ticket),"checked ACK did not release local form debt");
    const auto next=f.owner->reserve_document_sequence();check(next&&*next>d.work.request_sequence,"global allocator reset after ACK");
    Fixture navigation;const auto reserved=navigation.owner->reserve_document_sequence();check(bool(reserved),"navigation cancellation fixture could not reserve");
    auto successor=navigation.id;++successor.document_sequence;successor.service_generation=0;const auto begun=call(*navigation.owner,4,successor);ok(begun);navigation.id=begun.id;
    check(!navigation.owner->cancel_document_sequence(*reserved),"navigation did not cancel/burn held ordinary reservation");
    const auto after=navigation.owner->reserve_document_sequence();check(after&&*after>*reserved&&navigation.owner->cancel_document_sequence(*after),
        "navigation retained/resurrected old reservation instead of issuing fresh sequence");
}
void stage_validation_and_owned_bounds(){
    Fixture f;const auto idle=f.peek_raw();check(idle.control==FOUNDATION_ENGINE_EMPTY&&idle.service==0,"idle document mailbox did not permit ordinary advancement");
    auto valid=f.next();const auto reserved=f.peek_raw();check(reserved.control==FOUNDATION_ENGINE_EMPTY&&reserved.service==static_cast<std::uint32_t>(ServiceStatus::unavailable),
        "held ordinary reservation did not report an entry barrier");
    for(unsigned field=0;field<4;++field){auto wrong=valid;auto* value=field==0?&wrong.target.worker_epoch:field==1?&wrong.target.application_instance:field==2?&wrong.target.document_sequence:&wrong.target.service_generation;++*value;
        check(f.owner->stage_document_work(std::move(wrong)).code!=EngineDocumentAdmissionCode::admitted,"crossed target field admitted");}
    for(unsigned kind=0;kind<6;++kind){auto wrong=valid;if(kind==0)wrong.operation=1;if(kind==1)wrong.required_reply_capacity=1048575;if(kind==2)wrong.schema_sha256[0]^=1;
        if(kind==3)wrong.payload[8]^=1;
        if(kind==4)wrong.payload.push_back(0);
        if(kind==5)put(wrong.payload,40,0,8);
        check(f.owner->stage_document_work(std::move(wrong)).code!=EngineDocumentAdmissionCode::admitted,"malformed catalog/header work admitted");}
    const auto unreserved=work(valid.target,valid.request_sequence+1);
    check(f.owner->stage_document_work(unreserved).code!=EngineDocumentAdmissionCode::admitted,
          "empty ordinary slot admitted shape-valid unreserved sequence");
    const auto saved=valid;auto a=f.stage(valid);std::fill(valid.payload.begin(),valid.payload.end(),0);const auto first=f.peek_raw();ok(first);
    check(first.bytes==f.peek_raw().bytes&&f.peek().work.payload==saved.payload,"staged work borrowed or reminted request bytes");
    auto another=work(target(f.id),saved.request_sequence+1);check(f.owner->stage_document_work(another).code!=EngineDocumentAdmissionCode::admitted,"bounded ordinary slot admitted second work");
    f.finish(a);const auto retained=f.peek_raw();check(retained.control==FOUNDATION_ENGINE_EMPTY&&retained.service==static_cast<std::uint32_t>(ServiceStatus::unavailable),
        "retained local document result did not report an entry barrier");
    check(f.owner->consume_document_outcome(a.ticket),"owned query result did not release");
    const auto resumed=f.peek_raw();check(resumed.control==FOUNDATION_ENGINE_EMPTY&&resumed.service==0,"collected document work retained a false entry barrier");
}
void explicit_claim_turn_and_exact_local_replay(){
    Fixture f;const auto w=f.next();const auto a=f.stage(w);
    short_reply(*f.owner,27,f.id,{},0,80+56+w.payload.size()-1);
    const auto guessed=claim_bytes(w.kind,w.request_sequence);check(call(*f.owner,29,f.id,guessed,1).control!=0,"claim preceded complete peek");
    auto d=f.peek();const auto raw=ndv2(d.work.target,d.work.request_sequence,4,73,1048576);
    const auto good=result_bytes(d,raw,0,0,0,17);
    check(call(*f.owner,28,identity(d.work.target),good,d.transfer).control!=0,"unclaimed result settled");
    short_reply(*f.owner,29,identity(d.work.target),guessed,d.transfer,79);f.claim(d);
    check(call(*f.owner,29,identity(d.work.target),guessed,d.transfer).control!=0,"second claim authorized replay");
    check(call(*f.owner,28,identity(d.work.target),good,d.transfer).control!=0,"successful query settled without matching outer TURN");
    ok(call(*f.owner,2,identity(d.work.target),{},d.transfer));check(call(*f.owner,28,identity(d.work.target),good,d.transfer).control!=0,"result settled inside native turn");
    ok(call(*f.owner,3,identity(d.work.target),{},d.transfer));check(call(*f.owner,2,identity(d.work.target),{},d.transfer).control!=0,"claimed work entered a second outer turn");
    short_reply(*f.owner,28,identity(d.work.target),good,d.transfer,79);
    for(const auto status:{1,42,-9}){auto invalid=good;put(invalid,16,static_cast<std::uint32_t>(status),4);
        check(call(*f.owner,28,identity(d.work.target),invalid,d.transfer).control!=0&&!f.owner->document_outcome(a.ticket),
              "invalid provider status became consumed completion");}
    for(const auto disposition:{3u,UINT32_MAX}){auto invalid=good;put(invalid,20,disposition,4);
        check(call(*f.owner,28,identity(d.work.target),invalid,d.transfer).control!=0&&!f.owner->document_outcome(a.ticket),
              "invalid provider disposition became consumed completion");}
    f.settle(d,good);
    const auto one=f.owner->document_outcome(a.ticket);check(one&&one->outcome==EngineDocumentOutcome::consumed&&one->provider_disposition==0&&one->semantic_revision==17,"query disposition0 became a command rejection");
    check(one==f.owner->document_outcome(a.ticket),"local redelivery allocated/replaced immutable completion");f.settle(d,good);
    for(unsigned field=0;field<5;++field){auto changed=good;if(field==0)changed.back()^=1;if(field==1)put(changed,32,18,8);if(field==2)put(changed,16,static_cast<std::uint32_t>(-5),4);if(field==3)put(changed,28,1,4);if(field==4)put(changed,20,1,4);
        check(call(*f.owner,28,identity(d.work.target),changed,d.transfer).control!=0&&one==f.owner->document_outcome(a.ticket),"changed exact-result duplicate replaced/replayed completion");}
    for(unsigned field=0;field<7;++field){auto id=identity(d.work.target);auto transfer=d.transfer;auto changed=good;
        if(field<4){auto* member=field==0?&id.worker_epoch:field==1?&id.application_instance:field==2?&id.document_sequence:&id.service_generation;++*member;}
        if(field==4)++transfer;
        if(field==5)put(changed,0,2,4);
        if(field==6)put(changed,8,d.work.request_sequence+1,8);
        check(call(*f.owner,28,id,changed,transfer).control!=0&&one==f.owner->document_outcome(a.ticket),"changed result authority replaced retained completion");}
    check(one->bytes.size()==1048576&&f.peek_raw().control==FOUNDATION_ENGINE_EMPTY&&f.owner->consume_document_outcome(a.ticket),"full-size query ingress or immutable replay changed");
    const auto second=f.stage(f.next());const auto later=f.peek();f.claim(later);f.turn(later);const auto later_result=success_bytes(later);f.settle(later,later_result);
    check(call(*f.owner,28,identity(d.work.target),good,d.transfer).control!=0,"expired exact receipt reconstructed old success");f.settle(later,later_result);
    check(f.owner->consume_document_outcome(second.ticket),"latest query completion did not collect");
    const auto rejected=f.stage(f.next());const auto preentry=f.peek();f.claim(preentry);
    check(call(*f.owner,28,identity(preentry.work.target),result_bytes(preentry,{},-8),preentry.transfer).control!=0,
        "unentered trap fabricated balanced native result");
    f.settle(preentry,result_bytes(preentry,{},-5));const auto refusal=f.owner->document_outcome(rejected.ticket);
    check(refusal&&refusal->outcome==EngineDocumentOutcome::rejected&&refusal->provider_status==-5&&
          f.owner->consume_document_outcome(rejected.ticket),"known pre-entry query rejection required or fabricated native entry");
    const Bytes unrelated(1048577);check(call(*f.owner,FOUNDATION_ENGINE_SUBMIT,f.id,unrelated).control==FOUNDATION_ENGINE_LIMIT,
        "document result ingress widened unrelated service body limit");
}
void retained_form_ack_raw16_and_navigation(){
    Fixture f(false,false,true);const auto w=f.next(true);const auto action=f.stage(w);auto d=f.peek();f.claim(d);f.turn(d);
    const Bytes too_short(16,0x42);check(call(*f.owner,28,identity(d.work.target),result_bytes(d,too_short,0,1),d.transfer).control!=0,"form result omitted fixed exact prefix");
    f.settle(d,success_bytes(d));const auto original=f.owner->document_outcome(action.ticket);const auto original_bytes=original?original->bytes:Bytes{};
    check(original&&original->outcome==EngineDocumentOutcome::consumed&&!original->handled&&original->bytes.size()==52&&!f.owner->consume_document_outcome(action.ticket),"unhandled form lost retained raw completion/action debt");
    const auto old=f.id;auto next=old;++next.document_sequence;next.service_generation=0;const auto begun=call(*f.owner,4,next);ok(begun);f.id=begun.id;
    check(f.owner->stage_document_work(work(target(old),w.request_sequence+1)).code!=EngineDocumentAdmissionCode::admitted,"old document gained ordinary work");
    check(call(*f.owner,23,f.id).control!=FOUNDATION_ENGINE_OK,"old document became disposable before action ACK/local collection");
    const auto stale=f.ack(w.target,w.request_sequence);const auto same=f.ack(w.target,w.request_sequence);
    check(same.ticket==stale.ticket,"pending exact ACK intent minted another attempt");const auto stale_dispatch=f.peek();
    f.finish_ack(stale,w.request_sequence,2);check(!f.owner->consume_document_outcome(action.ticket),"ACK stale2 released another retained action");
    check(f.owner->consume_document_outcome(stale.ticket),"metadata stale ACK was not locally collectable");
    const auto ack=f.ack(w.target,w.request_sequence);auto ad=f.peek();check(ad.work.target==w.target&&ad.work.payload.size()==8&&ad.work.required_reply_capacity==16&&
        ad.work.request_sequence>stale_dispatch.work.request_sequence,"explicit fresh ACK after collected stale2 was rebased or reused old metadata attempt");f.claim(ad);
    check(call(*f.owner,2,identity(ad.work.target),{},ad.transfer).control!=0,"metadata ACK opened host/engine turn");
    const auto good=result_bytes(ad,ack_raw(w.request_sequence),0,1);
    for(unsigned field=0;field<6;++field){auto bad=good;if(field==0)put(bad,40,w.request_sequence+1,8);if(field==1)put(bad,52,1,4);if(field==2)put(bad,28,1,4);if(field==3)put(bad,20,0,4);if(field==4)put(bad,16,static_cast<std::uint32_t>(-1),4);if(field==5)bad.pop_back();
        check(call(*f.owner,28,identity(ad.work.target),bad,ad.transfer).control!=0&&!f.owner->consume_document_outcome(action.ticket),"malformed ACK released retained action");}
    f.settle(ad,good);const auto exact=f.owner->document_outcome(ack.ticket);check(exact&&exact->bytes==ack_raw(w.request_sequence)&&exact->target==w.target,"ACK raw16/full target lost");
    f.settle(ad,good);check(call(*f.owner,23,f.id).control!=FOUNDATION_ENGINE_OK,"old document disposed before local raw result collection");
    check(f.owner->consume_document_outcome(ack.ticket)&&f.owner->consume_document_outcome(action.ticket),"checked old-document ACK0 did not settle local debt");
    const auto retired=call(*f.owner,23,f.id);ok(retired);check(retired.id==old&&retired.transfer,"eligible old disposal lost original identity");
    ok(call(*f.owner,2,retired.id,{},retired.transfer));ok(call(*f.owner,3,retired.id,{},retired.transfer));
    const auto accepted=encode_u32(1);ok(call(*f.owner,24,retired.id,accepted,retired.transfer));ok(call(*f.owner,24,retired.id,accepted,retired.transfer));
    check(f.owner->identity()==f.id&&original->bytes==original_bytes,"old cleanup reset successor or mutated captured immutable raw result");
    const auto successor=f.owner->reserve_document_sequence();check(successor&&*successor>ad.work.request_sequence,"global document sequence reset after navigation/disposal");
    Fixture repeated;const auto retry_work=repeated.next(true);const auto retry_action=repeated.stage(retry_work);repeated.finish(retry_action,true);
    const auto retry_ack=repeated.ack(retry_work.target,retry_work.request_sequence);repeated.finish_ack(retry_ack,retry_work.request_sequence,1);
    check(repeated.owner->consume_document_outcome(retry_ack.ticket)&&repeated.owner->consume_document_outcome(retry_action.ticket),
          "checked exact already-retired ACK1 did not release retained action");
}
void known_unclaimed_close(){
    Fixture f;auto w=f.next();auto a=f.stage(w);f.owner->close();const auto cancelled=f.owner->document_outcome(a.ticket);
    check(cancelled&&cancelled->outcome==EngineDocumentOutcome::cancelled,"close did not cancel known-not-entered work");
}
void terminal_unknown(unsigned variant){
    const bool form=variant!=0;const auto status=variant==2?0:BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    Fixture f;auto a=f.stage(f.next(form));auto d=f.peek();f.claim(d);f.turn(d);
    // A balanced unknown command may return opaque forensic bytes. They are
    // deliberately not an NDV2 reply and must never become semantic success.
    const Bytes raw=variant==1?Bytes{0xde,0xad,0x7f}:Bytes{};
    const auto recorded=result_bytes(d,raw,status,form?2:0,variant==1?1:0);
    f.settle(d,recorded);const auto value=f.owner->document_outcome(a.ticket);
    check(value&&value->outcome==EngineDocumentOutcome::unknown&&value->provider_status==status,"native status lost unknown outcome or signed value");
    check(value->bytes==raw&&value->handled==(variant==1),"unknown command lost its exact opaque bytes/handled forensic record");
    f.settle(d,recorded);
    auto changed=recorded;put(changed,28,variant==1?0:1,4);
    check(call(*f.owner,28,identity(d.work.target),changed,d.transfer).control!=FOUNDATION_ENGINE_OK&&
          value==f.owner->document_outcome(a.ticket)&&value->bytes==raw,
          "changed unknown completion duplicate replaced immutable forensic evidence");
    check(value==f.owner->document_outcome(a.ticket)&&!f.owner->consume_document_outcome(a.ticket),"unknown completion was replaced or terminal debt consumed");
    check(call(*f.owner,29,identity(d.work.target),claim_bytes(d.work.kind,d.work.request_sequence),d.transfer).control!=0,"unknown work became retryable claim");
    if(form)check(f.owner->stage_document_action_ack(d.work.target,d.work.request_sequence).code!=EngineDocumentAdmissionCode::admitted,
                  "unknown form forensic bytes authorized a fresh native ACK export");
    check(!f.owner->reserve_document_sequence(),"closed/unknown route allocated new work");
    check(f.peek_raw().control==FOUNDATION_ENGINE_CLOSED,"poisoned document mailbox advertised idle or retained work");
}
void terminal_close_claimed(bool enter){
    Fixture f;const auto a=f.stage(f.next());const auto d=f.peek();f.claim(d);
    if(enter)ok(call(*f.owner,2,identity(d.work.target),{},d.transfer));
    f.owner->close();
    check(!f.owner->document_outcome(a.ticket),"close fabricated unobserved claimed completion");
    if(enter){check(f.owner->callback_depth()==1&&call(*f.owner,28,identity(d.work.target),result_bytes(d,{},-8),d.transfer).control!=0,
        "active close fabricated trap result or destroyed turn ownership");ok(call(*f.owner,3,identity(d.work.target),{},d.transfer));}
    check(!f.owner->document_outcome(a.ticket)&&call(*f.owner,2,identity(d.work.target),{},d.transfer).control!=0,
          "unobserved closed claim became synthetic completion or cleanup entry");
}
void counted_module_normal_cleanup(){
    auto counters=std::make_shared<ModuleCounters>();Fixture f(false,false,false,counters);
    check(counters->factories==1&&counters->constructed==1&&f.owner->has_module(),"counted optional binding not initialized");
    f.owner->close();f.owner->close();f.owner.reset();
    check(counters->close_calls==1&&counters->destroyed==1,"known-safe document binding did not close/destroy exactly once");
}
void terminal_counted_module(bool unknown){
    auto counters=std::make_shared<ModuleCounters>();auto blocked=std::make_shared<ModuleCounters>();
    Fixture f(false,false,false,counters);const auto a=f.stage(f.next());const auto d=f.peek();f.claim(d);
    if(unknown){f.turn(d);f.settle(d,result_bytes(d,{},-8));check(bool(f.owner->document_outcome(a.ticket)),"unknown module outcome missing");}
    else f.owner->close();
    check(reset_without_allocation(f.owner)==0,"terminal claimed/unknown quarantine allocated destructor state");
    check(counters->close_calls==0&&counters->destroyed==0,"terminal claimed/unknown binding performed cleanup during quarantine");
    bool rejected=false;try{Fixture later(false,false,false,blocked);}catch(const std::exception&){rejected=true;}
    check(rejected&&!blocked->factories&&!blocked->constructed,"terminal process constructed a later enabled binding");
}
void terminal_unbalanced_module_turn(){
    auto counters=std::make_shared<ModuleCounters>(),blocked=std::make_shared<ModuleCounters>();
    Fixture f(false,false,false,counters);ok(call(*f.owner,2,f.id));
    check(f.owner->callback_depth()==1,"unbalanced TURN fixture did not retain native depth");
    // dispatch() returned: no Owner method or native engine call is still on
    // this C++ stack. Only the observed unmatched native TURN remains.
    check(reset_without_allocation(f.owner)==0,"unbalanced TURN quarantine allocated destructor state");
    check(!counters->close_calls&&!counters->destroyed,"unbalanced native TURN performed optional-module cleanup");
    bool rejected=false;try{Fixture later(false,false,false,blocked);}catch(const std::exception&){rejected=true;}
    check(rejected&&!blocked->factories,"unbalanced TURN quarantine did not close later provider admission");
}

void terminal_unacked_form_module(){
    auto counters=std::make_shared<ModuleCounters>(),blocked=std::make_shared<ModuleCounters>();
    Fixture f(false,false,false,counters);const auto a=f.stage(f.next(true));f.finish(a,true);
    check(!f.owner->consume_document_outcome(a.ticket),"unACKed consumed form debt was locally released");
    check(reset_without_allocation(f.owner)==0,"unACKed form quarantine allocated destructor state");
    check(!counters->close_calls&&!counters->destroyed,"unACKed consumed form ran optional-module cleanup");
    bool rejected=false;try{Fixture later(false,false,false,blocked);}catch(const std::exception&){rejected=true;}
    check(rejected&&!blocked->factories,"unACKed form quarantine admitted a later binding");
}
void terminal_unknown_ack_raw(){
    auto counters=std::make_shared<ModuleCounters>(),blocked=std::make_shared<ModuleCounters>();
    Fixture f(false,false,false,counters);const auto w=f.next(true);const auto action=f.stage(w);f.finish(action,true);
    const auto ack=f.ack(w.target,w.request_sequence);const auto d=f.peek();f.claim(d);
    // Malformed as a known ACK receipt, but bounded opaque evidence for the
    // native unknown disposition. No TURN or semantic ACK proof is involved.
    const Bytes raw(16,0xa5);const auto recorded=result_bytes(d,raw,0,2,1);f.settle(d,recorded);
    const auto unknown=f.owner->document_outcome(ack.ticket);
    check(unknown&&unknown->outcome==EngineDocumentOutcome::unknown&&unknown->provider_status==0&&
          unknown->provider_disposition==2&&unknown->handled&&unknown->bytes==raw,
          "unknown metadata ACK lost bounded opaque raw16 evidence or became known proof");
    f.settle(d,recorded);auto changed=recorded;changed.back()^=1;
    check(call(*f.owner,28,identity(d.work.target),changed,d.transfer).control!=FOUNDATION_ENGINE_OK&&
          unknown==f.owner->document_outcome(ack.ticket)&&unknown->bytes==raw,
          "changed unknown metadata ACK duplicate replaced retained forensic bytes");
    check(!f.owner->consume_document_outcome(ack.ticket)&&!f.owner->consume_document_outcome(action.ticket)&&
          !f.owner->reserve_document_sequence()&&f.owner->callback_depth()==0&&
          f.owner->stage_document_action_ack(w.target,w.request_sequence).code!=EngineDocumentAdmissionCode::admitted&&
          call(*f.owner,2,identity(d.work.target),{},d.transfer).control!=FOUNDATION_ENGINE_OK,
          "unknown metadata ACK released action debt or admitted native retry/entry");
    f.owner->close();check(!counters->close_calls&&!counters->destroyed,"unknown metadata ACK close ran module cleanup");
    check(reset_without_allocation(f.owner)==0&&!counters->close_calls&&!counters->destroyed,
          "unknown metadata ACK quarantine allocated state or ran module cleanup");
    bool rejected=false;try{Fixture later(false,false,false,blocked);}catch(const std::exception&){rejected=true;}
    check(rejected&&!blocked->factories,"unknown metadata ACK admitted a later enabled binding");
}

void terminal_multiple_preexisting_modules(){
    auto first_count=std::make_shared<ModuleCounters>(),second_count=std::make_shared<ModuleCounters>(),
        idle_count=std::make_shared<ModuleCounters>(),safe_count=std::make_shared<ModuleCounters>(),
        debt_count=std::make_shared<ModuleCounters>(),late_count=std::make_shared<ModuleCounters>();
    Fixture first(false,false,false,first_count),second(false,false,false,second_count),
        idle(false,false,false,idle_count,false),safe(false,false,false,safe_count),debt(false,false,false,debt_count);
    const auto a=first.stage(first.next());const auto d=first.peek();first.claim(d);first.turn(d);
    const auto other=second.stage(second.next());const auto od=second.peek();second.claim(od);
    const auto retained_work=debt.next(true);const auto retained=debt.stage(retained_work);debt.finish(retained,true);
    const auto retained_proof=debt.owner->document_outcome(retained.ticket);
    const auto local=safe.stage(safe.next());const auto local_dispatch=safe.peek();safe.claim(local_dispatch);safe.turn(local_dispatch);
    const auto local_result=success_bytes(local_dispatch);safe.settle(local_dispatch,local_result);const auto local_proof=safe.owner->document_outcome(local.ticket);
    const auto major=encode_u32(1),minor=encode_u32(0);constexpr std::string_view name="org.example.counted.module";
    const Span name_bytes{reinterpret_cast<const std::uint8_t*>(name.data()),name.size()};
    const std::array<FieldView,4> fields{{{1,FieldType::utf8,true,name_bytes},{2,FieldType::u32,true,major},{3,FieldType::u32,true,minor},{4,FieldType::u32,true,minor}}};
    Bytes query,packet;check(encode_record(fields,query)==CodecStatus::ok,"preexisting module queue fixture invalid");
    Envelope service;service.generation=safe.id.service_generation;service.sequence=1;service.operation=FOUNDATION_APPENDED_CONTROL_DISCOVER;
    check(encode_envelope(service,query,packet)==CodecStatus::ok,"preexisting module envelope invalid");ok(call(*safe.owner,6,safe.id,packet));
    first.settle(d,result_bytes(d,{},-8));check(bool(first.owner->document_outcome(a.ticket))&&!second.owner->document_outcome(other.ticket),"preexisting terminal claims lost their own outcomes");
    check(call(*idle.owner,1,idle.id).control!=FOUNDATION_ENGINE_OK&&!idle_count->factories,"preexisting unconfigured owner bound after process poison");
    bool rejected=false;try{Fixture later(false,false,false,late_count);}catch(const std::exception&){rejected=true;}
    check(rejected&&!late_count->factories,"new owner bound after first process poison");
    check(!safe.owner->reserve_document_sequence()&&safe.owner->stage_document_work(work(target(safe.id),100)).code!=EngineDocumentAdmissionCode::admitted&&
          safe.owner->stage_document_action_ack(target(safe.id),1).code!=EngineDocumentAdmissionCode::admitted,
          "preexisting owner admitted fresh provider work after process terminal flag");
    check(call(*second.owner,2,identity(od.work.target),{},od.transfer).control!=FOUNDATION_ENGINE_OK&&
          call(*safe.owner,12,safe.id).control!=FOUNDATION_ENGINE_OK&&!safe_count->callbacks&&!second_count->callbacks,
          "preexisting owner entered native TURN/module callback after process poison");
    check(retained_proof&&retained_proof==debt.owner->document_outcome(retained.ticket)&&!debt.owner->consume_document_outcome(retained.ticket)&&
          debt.owner->stage_document_action_ack(retained_work.target,retained_work.request_sequence).code!=EngineDocumentAdmissionCode::admitted,
          "process poison discarded retained form debt or admitted a fresh native ACK export");
    check(local_proof&&local_proof==safe.owner->document_outcome(local.ticket)&&safe.owner->consume_document_outcome(local.ticket),
          "process poison prevented known local result collection");safe.settle(local_dispatch,local_result);
    check(reset_without_allocation(first.owner)==0&&reset_without_allocation(second.owner)==0&&reset_without_allocation(debt.owner)==0,
          "multiple preexisting quarantines allocated destructor state");idle.owner.reset();safe.owner.reset();
    check(first_count->close_calls==0&&first_count->destroyed==0&&second_count->close_calls==0&&second_count->destroyed==0,
          "multiple preexisting terminal bindings escaped process-lived quarantine");
    check(!debt_count->close_calls&&!debt_count->destroyed,"preexisting consumed/unACKed form debt escaped terminal quarantine");
    check(safe_count->close_calls==1&&safe_count->destroyed==1&&!idle_count->constructed,
          "known-safe preexisting binding lost normal cleanup or idle binding gained effects");
}

Bytes service_request(EngineIdentity id,std::uint64_t sequence,std::uint64_t handle,std::uint32_t operation,Span payload){
    Envelope envelope;envelope.generation=id.service_generation;envelope.sequence=sequence;envelope.interface_handle=handle;envelope.operation=operation;
    Bytes out;check(encode_envelope(envelope,payload,out)==CodecStatus::ok,"service fixture invalid");return out;
}
Bytes collect_service(Fixture& f,std::uint64_t sequence){
    const auto r=call(*f.owner,13,f.id);ok(r);Envelope envelope;Span raw;check(decode_envelope(r.body(),envelope,raw)==CodecStatus::ok&&envelope.sequence==sequence&&envelope.service_status==0,"actual service completion changed");
    Bytes result(raw.begin(),raw.end());const auto accepted=encode_u32(1);ok(call(*f.owner,16,r.id,accepted,r.transfer));
    const auto ack=call(*f.owner,8,f.id,encode_u64(sequence));check(ack.control==0&&ack.service==static_cast<std::uint32_t>(ServiceStatus::unavailable),"service ACK staging failed");ok(call(*f.owner,12,f.id));
    const auto receipt=call(*f.owner,14,f.id);ok(receipt);ok(call(*f.owner,17,receipt.id,accepted,receipt.transfer));return result;
}
void terminal_notification_direct(){
    auto notified_count=std::make_shared<ModuleCounters>(),idle_count=std::make_shared<ModuleCounters>(),
        late_count=std::make_shared<ModuleCounters>();
    Fixture notified(false,true,false,notified_count),idle(false,false,false,idle_count,false),reserved,physical(true),debt;
    const auto reserved_work=reserved.next();
    const auto action_work=debt.next(true);const auto action=debt.stage(action_work);debt.finish(action,true);
    const auto retained=debt.owner->document_outcome(action.ticket);
    Bytes bind;check(input::encode_focus({1,0,0,0,7,0},bind)==input::Status::ok,"notification physical bind fixture invalid");
    const auto major=encode_u32(1),minor=encode_u32(0);
    const Span name{reinterpret_cast<const std::uint8_t*>(Fixture::service_name.data()),Fixture::service_name.size()};
    const std::array<FieldView,4> fields{{{1,FieldType::utf8,true,name},{2,FieldType::u32,true,major},
        {3,FieldType::u32,true,minor},{4,FieldType::u32,true,minor}}};
    Bytes discovery;check(encode_record(fields,discovery)==CodecStatus::ok,"notification service fixture invalid");
    ok(call(*notified.owner,6,notified.id,service_request(notified.id,1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER,discovery)));
    check(notify_without_allocation(*notified.owner)==0,"idempotent terminal notification allocated state");
    check(notified.owner->identity()==notified.id&&notified.owner->callback_depth()==0&&!notified.owner->native_effect()&&
          !notified_count->callbacks&&!notified_count->close_calls&&!notified_count->destroyed,
          "terminal notification changed depth/identity, entered an export/effect, or cleaned up a module");
    check(!notified.owner->document_enabled()&&!physical.owner->document_enabled()&&!physical.owner->input_enabled(),
          "terminal notification did not close existing document and physical admission");
    check(call(*idle.owner,1,idle.id).control==FOUNDATION_ENGINE_CLOSED&&!idle_count->factories,
          "notification admitted preexisting unconfigured owner/factory");
    bool rejected=false;try{Fixture later(false,false,false,late_count);}catch(const std::exception&){rejected=true;}
    check(rejected&&!late_count->factories&&!late_count->constructed,"notification constructed a later enabled binding");
    check(reserved.owner->stage_document_work(reserved_work).code==EngineDocumentAdmissionCode::closed&&
          !physical.owner->reserve_document_sequence()&&
          !physical.owner->stage_command(physical.id,7,3,input::kFocusSchema,bind,true),
          "notification admitted reserved document work or a new physical bind");
    check(debt.owner->stage_document_action_ack(action_work.target,action_work.request_sequence).code==EngineDocumentAdmissionCode::closed&&
          retained==debt.owner->document_outcome(action.ticket)&&!debt.owner->consume_document_outcome(action.ticket),
          "notification invented action retirement or discarded retained action proof");
    check(call(*notified.owner,2,notified.id).control!=FOUNDATION_ENGINE_OK&&
          call(*notified.owner,12,notified.id).control==FOUNDATION_ENGINE_CLOSED&&
          !notified.owner->native_effect()&&!notified.effects&&!notified_count->callbacks,
          "notification admitted a fresh native TURN/PUMP/effect");
    notified.owner->close();check(!notified_count->close_calls&&!notified_count->destroyed,
          "explicit notification allowed direct module cleanup");
    check(reset_without_allocation(notified.owner)==0&&!notified_count->close_calls&&!notified_count->destroyed,
          "explicit notification failed allocation-free quarantine of its otherwise clean module");
}
void terminal_notification_foreign_thread(){
    auto counters=std::make_shared<ModuleCounters>(),blocked=std::make_shared<ModuleCounters>();
    Fixture f(false,false,false,counters);const auto original=f.owner->identity();
    std::size_t allocations=std::numeric_limits<std::size_t>::max();
    // The owning unique_ptr remains untouched until join. Only the new atomic
    // notification API is called off-thread; no ordinary Owner API crosses it.
    std::thread notifier([&]{allocations=notify_without_allocation(*f.owner);});notifier.join();
    check(allocations==0&&f.owner->identity()==original&&f.owner->callback_depth()==0&&
          !f.owner->document_enabled()&&!f.owner->reserve_document_sequence()&&
          !counters->callbacks&&!counters->close_calls&&!counters->destroyed,
          "foreign-thread notification was refused, allocated, entered callbacks, or changed owner metadata");
    bool rejected=false;try{Fixture later(false,false,false,blocked);}catch(const std::exception&){rejected=true;}
    check(rejected&&!blocked->factories,"foreign-thread notification did not publish process-terminal admission");
    check(reset_without_allocation(f.owner)==0&&!counters->close_calls&&!counters->destroyed,
          "foreign-thread notification did not quarantine its own module without allocation");
}
void terminal_notification_claimed(){
    auto counters=std::make_shared<ModuleCounters>();Fixture f(false,false,false,counters);
    const auto a=f.stage(f.next());const auto d=f.peek();f.claim(d);
    check(notify_without_allocation(*f.owner)==0&&!f.owner->document_outcome(a.ticket)&&f.owner->callback_depth()==0,
          "notification synthesized a result/LEAVE for a claimed but unentered slot");
    check(call(*f.owner,28,identity(d.work.target),success_bytes(d),d.transfer).control==FOUNDATION_ENGINE_CONFLICT&&
          !f.owner->document_outcome(a.ticket)&&!f.owner->consume_document_outcome(a.ticket),
          "notification erased its exact claimed slot or accepted an unentered fabricated result");
    check(call(*f.owner,2,identity(d.work.target),{},d.transfer).control!=FOUNDATION_ENGINE_OK&&
          !counters->callbacks&&!counters->close_calls&&!counters->destroyed,
          "notification let its preserved claim enter or clean up");
    check(reset_without_allocation(f.owner)==0&&!counters->close_calls&&!counters->destroyed,
          "notified claimed slot escaped allocation-free quarantine");
}
void terminal_notification_natural_return(){
    auto counters=std::make_shared<ModuleCounters>();Fixture f(false,false,false,counters);
    const auto a=f.stage(f.next());const auto d=f.peek();f.claim(d);ok(call(*f.owner,2,identity(d.work.target),{},d.transfer));
    check(notify_without_allocation(*f.owner)==0&&f.owner->callback_depth()==1&&!f.owner->document_outcome(a.ticket),
          "notification fabricated the admitted native TURN's return/result");
    check(call(*f.owner,28,identity(d.work.target),success_bytes(d),d.transfer).control==FOUNDATION_ENGINE_CONFLICT&&
          !f.owner->document_outcome(a.ticket),"notification accepted a result before its natural LEAVE");
    check(call(*f.owner,3,identity(d.work.target),{},d.transfer+1).control!=FOUNDATION_ENGINE_OK&&f.owner->callback_depth()==1,
          "foreign LEAVE consumed the admitted native TURN after notification");
    ok(call(*f.owner,3,identity(d.work.target),{},d.transfer));const auto recorded=success_bytes(d);f.settle(d,recorded);
    const auto value=f.owner->document_outcome(a.ticket);
    check(value&&value->outcome==EngineDocumentOutcome::consumed&&f.owner->callback_depth()==0,
          "notification prevented the already-admitted matching natural return/result");
    f.settle(d,recorded);check(value==f.owner->document_outcome(a.ticket)&&f.owner->consume_document_outcome(a.ticket),
          "notification prevented retained known local proof collection/replay");
    check(!f.owner->reserve_document_sequence()&&call(*f.owner,2,f.id).control!=FOUNDATION_ENGINE_OK&&
          !counters->callbacks&&!counters->close_calls&&!counters->destroyed,
          "natural return reopened independent native admission or cleaned up its notified module");
    check(reset_without_allocation(f.owner)==0&&!counters->close_calls&&!counters->destroyed,
          "naturally returned notified owner did not retain allocation-free terminal quarantine");
}
void counted_native_ui_close(bool abandon){
    auto counters=std::make_shared<ModuleCounters>(),blocked=std::make_shared<ModuleCounters>();
    Fixture f(false,true,false,counters);std::uint64_t publication=1;
    auto execute=[&](std::uint64_t sequence,std::uint64_t handle,std::uint32_t operation,const Bytes& payload){
        f.safe_publication=false;ok(call(*f.owner,6,f.id,service_request(f.id,sequence,handle,operation,payload)));
        const auto gate=call(*f.owner,12,f.id);const auto effect=f.owner->native_effect();
        check(gate.control==FOUNDATION_ENGINE_CONFLICT&&effect&&!effect->entered,
              "counted native UI fixture bypassed the safe publication gate");
        f.safe_publication=true;
        check(f.owner->acknowledge_document_native_effect(effect->ticket,target(f.id),publication++),
              "counted native UI fixture could not publish readiness");
        ok(call(*f.owner,12,f.id));return collect_service(f,sequence);
    };
    const auto major=encode_u32(1),minor=encode_u32(0);
    const Span name{reinterpret_cast<const std::uint8_t*>(Fixture::service_name.data()),Fixture::service_name.size()};
    const std::array<FieldView,4> fields{{{1,FieldType::utf8,true,name},{2,FieldType::u32,true,major},
        {3,FieldType::u32,true,minor},{4,FieldType::u32,true,minor}}};
    Bytes discovery;check(encode_record(fields,discovery)==CodecStatus::ok,"counted native UI discovery fixture invalid");
    const auto bytes=execute(1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER,discovery);
    std::vector<FieldView> descriptor;std::uint64_t handle{};
    check(decode_record(bytes,descriptor)==CodecStatus::ok&&!descriptor.empty()&&read_u64(descriptor.front(),handle)&&handle,
          "counted native UI fixture did not discover the actual Registry route");
    f.hold_on_entry=true;
    check(execute(2,handle,1,encode_u32(41))==encode_u32(41)&&f.effects==1&&f.held&&
          f.owner->native_effect()&&f.owner->native_effect()->entered&&f.owner->callback_depth()==0,
          "counted native UI fixture did not retain only the entered UI hold");
    // No document work has been staged in this Owner. The held native effect
    // alone must prevent both C++ close and copied CLOSE from running cleanup.
    f.owner->close();
    check(!counters->close_calls&&!counters->destroyed&&f.owner->native_effect(),
          "C++ close cleaned up an optional module while native UI remained held");
    const auto closing=call(*f.owner,FOUNDATION_ENGINE_CLOSE,f.id);
    check(closing.control==FOUNDATION_ENGINE_OK&&closing.service==static_cast<std::uint32_t>(ServiceStatus::unavailable)&&
          !counters->close_calls&&!counters->destroyed&&f.owner->native_effect()&&f.effects==1,
          "copied CLOSE cleaned up or reentered an optional module while native UI remained held");
    if(!abandon){
        check(f.owner->release_native_effect(f.held),"trusted UI closure could not drain a requested close");
        f.owner->close();f.owner.reset();
        check(counters->close_calls==1&&counters->destroyed==1,
              "known trusted UI closure did not permit exactly one normal module cleanup");
        return;
    }
    check(reset_without_allocation(f.owner)==0,"held native UI quarantine allocated destructor state");
    check(!counters->close_calls&&!counters->destroyed,"held native UI quarantine ran optional-module cleanup");
    bool rejected=false;try{Fixture later(false,false,false,blocked);}catch(const std::exception&){rejected=true;}
    check(rejected&&!blocked->factories&&!blocked->constructed,
          "abandoned native UI quarantine admitted a later enabled binding");
}
void claimed_ack_rejects_host_callbacks(){
    Fixture f(false,true);
    const auto major=encode_u32(1),minor=encode_u32(0);const Span name{reinterpret_cast<const std::uint8_t*>(Fixture::service_name.data()),Fixture::service_name.size()};
    const std::array<FieldView,4> fields{{{1,FieldType::utf8,true,name},{2,FieldType::u32,true,major},{3,FieldType::u32,true,minor},{4,FieldType::u32,true,minor}}};
    Bytes discovery;check(encode_record(fields,discovery)==CodecStatus::ok,"callback-isolation discovery fixture invalid");
    ok(call(*f.owner,6,f.id,service_request(f.id,1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER,discovery)));
    check(call(*f.owner,12,f.id).control==FOUNDATION_ENGINE_CONFLICT,"discovery skipped document effect gate");
    const auto effect=f.owner->native_effect();check(effect&&f.owner->acknowledge_document_native_effect(effect->ticket,target(f.id),1),"discovery publication readiness failed");
    ok(call(*f.owner,12,f.id));(void)collect_service(f,1);
    auto resource_id=f.id;resource_id.service_generation=0;
    const auto resource=call(*f.owner,21,resource_id);ok(resource);const auto epoch=get(resource.body(),0,8);
    const auto url="app://"+f.owner->package().package_sha256+"/web/index.html";
    Bytes resolve(16+url.size());put(resolve,0,epoch,8);put(resolve,12,url.size(),4);std::copy(url.begin(),url.end(),resolve.begin()+16);
    const auto resolved=call(*f.owner,9,resource_id,resolve);ok(resolved);const auto lease=get(resolved.body(),24,8);
    Bytes read(20);put(read,0,lease,8);const auto release=encode_u64(lease),retire=encode_u64(epoch);
    ok(call(*f.owner,10,resource_id,read));
    const auto w=f.next(true);const auto action=f.stage(w);f.finish(action,true);const auto original=f.owner->document_outcome(action.ticket);
    const auto ack=f.ack(w.target,w.request_sequence);const auto d=f.peek();f.claim(d);
    for(const auto transfer:{std::uint64_t{0},d.transfer}){
        for(const auto& operation:std::array<std::pair<std::uint32_t,Bytes>,6>{{{9,resolve},{10,read},{11,release},{8,encode_u64(1)},{21,{}},{22,retire}}})
            check(call(*f.owner,operation.first,operation.first==8?f.id:resource_id,operation.second,transfer).control!=FOUNDATION_ENGINE_OK,
                  "claimed metadata ACK admitted a callback-like host operation");
    }
    auto successor=f.id;++successor.document_sequence;successor.service_generation=0;
    check(call(*f.owner,4,successor).control!=FOUNDATION_ENGINE_OK&&f.owner->identity()==f.id&&f.owner->document_outcome(action.ticket)==original,
          "claimed metadata ACK admitted navigation or changed retained state");
    f.settle(d,result_bytes(d,ack_raw(w.request_sequence),0,1));
    check(f.owner->consume_document_outcome(ack.ticket)&&f.owner->consume_document_outcome(action.ticket),"isolated metadata ACK could not settle");
    ok(call(*f.owner,10,resource_id,read),"blocked resource release destroyed a real lease");ok(call(*f.owner,11,resource_id,release));ok(call(*f.owner,22,resource_id,retire));
    check(f.effects==0&&f.owner->callback_depth()==0,"metadata ACK entered Registry/Host callbacks");
}

void native_effect_safe_publication_and_ui_hold(){
    Fixture f(false,true);std::uint64_t publication=1;
    auto execute=[&](std::uint64_t sequence,std::uint64_t handle,std::uint32_t operation,const Bytes& payload){
        f.safe_publication=false;
        EngineDocumentAdmission debt;std::optional<std::uint64_t> reserved;EngineDocumentWork retained_work;
        if(sequence==3){reserved=f.owner->reserve_document_sequence();check(bool(reserved),"effect cancellation fixture could not reserve");}
        else{retained_work=f.next(sequence==4);debt=f.stage(retained_work);f.finish(debt,sequence==4);}
        ok(call(*f.owner,6,f.id,service_request(f.id,sequence,handle,operation,payload)));
        const auto gate=call(*f.owner,12,f.id);check(gate.control==FOUNDATION_ENGINE_CONFLICT&&gate.service==static_cast<std::uint32_t>(ServiceStatus::unavailable),"native request bypassed document gate");
        const auto effect=f.owner->native_effect();check(effect&&!effect->entered&&!effect->input_context,"pixel document effect fabricated physical context");
        if(reserved)check(!f.owner->cancel_document_sequence(*reserved),"native effect creation retained an old ordinary reservation");
        check(!f.owner->acknowledge_native_effect(effect->ticket),"legacy native ACK bypassed document publication gate");
        auto wrong=target(f.id);++wrong.document_sequence;
        check(!f.owner->acknowledge_document_native_effect(effect->ticket,wrong,publication)&&
              !f.owner->acknowledge_document_native_effect(effect->ticket,target(f.id),0),"wrong/zero safe publication admitted handler");
        if(debt.ticket){check(!f.owner->acknowledge_document_native_effect(effect->ticket,target(f.id),publication),"local result/action debt did not block native handler readiness");
            if(sequence==4){
                check(!f.owner->consume_document_outcome(debt.ticket),"queued native service released unACKed form debt");
                const auto action_ack=f.ack(retained_work.target,retained_work.request_sequence);const auto pending=f.peek();
                check(pending.work.kind==EngineDocumentWorkKind::action_ack,"queued service/effect starved required form ACK work");
                f.finish_ack(action_ack,retained_work.request_sequence);
                check(f.owner->consume_document_outcome(action_ack.ticket),"native service gate could not collect action ACK");
            }
            check(f.owner->consume_document_outcome(debt.ticket),"native gate could not collect settled local result/action debt");}
        if(publication>1)check(!f.owner->acknowledge_document_native_effect(effect->ticket,target(f.id),publication-1),"previous safe publication resumed a later effect");
        f.safe_publication=true;check(f.owner->acknowledge_document_native_effect(effect->ticket,target(f.id),publication++),"exact fresh safe publication rejected");
        ok(call(*f.owner,12,f.id));auto result=collect_service(f,sequence);
        if(f.hold_on_entry){check(f.held&&f.owner->native_effect()&&f.owner->input_suspended()&&!f.owner->reserve_document_sequence(),"native UI hold admitted later work");
            check(!f.owner->release_native_effect(f.held+1)&&f.owner->release_native_effect(f.held),"UI hold released with wrong ticket or refused trusted closure");}
        check(!f.owner->native_effect(),"known native completion retained effect suspension");
        const auto resumed=f.owner->reserve_document_sequence();check(resumed&&(!reserved||*resumed>*reserved)&&f.owner->cancel_document_sequence(*resumed),
            "known native completion did not resume a fresh ordinary document reservation");return result;
    };
    const auto major=encode_u32(1),minor=encode_u32(0);const Span name{reinterpret_cast<const std::uint8_t*>(Fixture::service_name.data()),Fixture::service_name.size()};
    const std::array<FieldView,4> fields{{{1,FieldType::utf8,true,name},{2,FieldType::u32,true,major},{3,FieldType::u32,true,minor},{4,FieldType::u32,true,minor}}};
    Bytes query;check(encode_record(fields,query)==CodecStatus::ok,"native discovery fixture invalid");auto bytes=execute(1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER,query);
    std::vector<FieldView> descriptor;std::uint64_t handle{};check(decode_record(bytes,descriptor)==CodecStatus::ok&&!descriptor.empty()&&read_u64(descriptor.front(),handle)&&handle,"actual native Registry route missing");
    check(execute(2,handle,1,encode_u32(41))==encode_u32(41)&&f.effects==1,"ordinary known Registry completion did not release suspension");
    f.hold_on_entry=true;check(execute(3,handle,1,encode_u32(42))==encode_u32(42)&&f.effects==2,"held Registry handler repeated or lost result");
    f.hold_on_entry=false;check(execute(4,handle,1,encode_u32(43))==encode_u32(43)&&f.effects==3,
        "queued actual Registry request deadlocked or repeated across required form ACK cleanup");
    auto next=f.next();auto a=f.stage(next);f.finish(a);check(f.owner->consume_document_outcome(a.ticket),"fresh work after trusted UI closure failed");
}
void final_ack_sequence_headroom(){
    constexpr auto maximum=std::numeric_limits<std::uint64_t>::max();doc::SequenceAllocator sequence(maximum-1);
    const auto reserved=sequence.reserve();check(reserved&&*reserved==maximum-1&&sequence.has_reservation(),"final ordinary sequence unavailable");
    check(!sequence.issue_physical()&&!sequence.issue_ack(),"held final ordinary reservation was overtaken");
    check(!sequence.cancel(maximum)&&sequence.cancel(maximum-1)&&sequence.ordinary_exhausted(),"final cancellation did not burn ordinary headroom");
    bool exhausted=false;try{(void)sequence.reserve();}catch(const std::overflow_error&){exhausted=true;}check(exhausted,"ordinary exhaustion failed to stop before ACKMAX");
    const auto ack=sequence.issue_ack();check(ack&&*ack==maximum,"final ACKMAX lost reserved headroom");
    exhausted=false;try{(void)sequence.issue_ack();}catch(const std::overflow_error&){exhausted=true;}check(exhausted,"ACKMAX wrapped/reused sequence");
    doc::SequenceAllocator commit(maximum-1);check(commit.reserve()==maximum-1&&commit.commit(maximum-1),"final ordinary commit failed");check(commit.issue_ack()==maximum,"committed final action could not receive ACKMAX");
}
}
int main(int argc,char** argv){
    try{
        allocation_probe::calls=0;allocation_probe::armed=true;
        void* scalar=::operator new(16);void* array=::operator new[](16);void* aligned=::operator new(64,std::align_val_t{64});
        allocation_probe::armed=false;const auto counted=allocation_probe::calls;
        ::operator delete(scalar);::operator delete[](array);::operator delete(aligned,std::align_val_t{64});
        check(counted==3,"allocation probe failed its scalar/array/aligned positive control");
        const std::array<std::pair<std::string_view,void(*)()>,16> terminal{{
            {"unknown-query",+[]{terminal_unknown(0);}},
            {"unknown-form",+[]{terminal_unknown(1);}},
            {"unknown-form-zero",+[]{terminal_unknown(2);}},
            {"close-claimed",+[]{terminal_close_claimed(false);}},
            {"close-active",+[]{terminal_close_claimed(true);}},
            {"module-unknown",+[]{terminal_counted_module(true);}},
            {"module-claimed",+[]{terminal_counted_module(false);}},
            {"module-unbalanced-turn",terminal_unbalanced_module_turn},
            {"module-unacked-form",terminal_unacked_form_module},
            {"unknown-ack-raw",terminal_unknown_ack_raw},
            {"module-held-ui",+[]{counted_native_ui_close(true);}},
            {"notify-direct",terminal_notification_direct},
            {"notify-foreign-thread",terminal_notification_foreign_thread},
            {"notify-claimed",terminal_notification_claimed},
            {"notify-natural-return",terminal_notification_natural_return},
            {"module-multiple",terminal_multiple_preexisting_modules}}};
        if(argc==3&&std::string_view(argv[1])=="--case"){
            for(const auto& [name,test]:terminal)if(name==argv[2]){test();std::cout<<"PASS terminal "<<name<<", "<<assertions<<" assertions\n";return 0;}
            throw std::invalid_argument("unknown isolated terminal case");
        }
        if(argc!=1)throw std::invalid_argument("run normal groups without arguments or one terminal scenario with --case NAME");
        const std::array<std::pair<const char*,void(*)()>,10> cases{{
            {"profile gates",profile_gates_and_frozen_admission},
            {"reservation and global physical order",reservation_burn_and_global_physical_order},
            {"owned staging bounds",stage_validation_and_owned_bounds},
            {"claim turn and local replay",explicit_claim_turn_and_exact_local_replay},
            {"retained form ACK16/navigation",retained_form_ack_raw16_and_navigation},
            {"known unclaimed close",known_unclaimed_close},
            {"claimed ACK callback isolation",claimed_ack_rejects_host_callbacks},
            {"native effect/publication/UI hold",native_effect_safe_publication_and_ui_hold},
            {"normal counted module cleanup",+[]{counted_module_normal_cleanup();counted_native_ui_close(false);}},
            {"final ACKMAX headroom",final_ack_sequence_headroom}}};
        for(const auto& [name,test]:cases){test();std::cout<<"PASS "<<name<<'\n';}
        std::cout<<cases.size()<<" normal document owner groups, "<<assertions<<" assertions passed; terminal cases require separate --case processes\n";
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
