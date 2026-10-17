#include "shared/appended_engine_application.hpp"
#include "shared/appended_engine_abi.h"
#include "shared/appended_engine_input_codec.hpp"
#include <gui/retained_adapter.hpp>
#include <algorithm>
#include <array>
#include <functional>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

// Real bitmap App, Owner, Registry and Surface Policy; independently assembled
// copied endpoint fixtures only. Synthetic profile pins qualify no engine/SDK.
namespace {
using namespace foundation;
using namespace appended;
namespace doc = engine_document;
namespace input = engine_input;
using Span = std::span<const std::uint8_t>;
std::size_t assertions{};
void check(bool value,const char* reason){++assertions;if(!value)throw std::runtime_error(reason);}
void put(std::span<std::uint8_t> out,std::size_t at,std::uint64_t value,unsigned width){
    if(at>out.size()||width>out.size()-at)throw std::logic_error("fixture write bounds");
    for(unsigned n=0;n<width;++n)out[at+n]=static_cast<std::uint8_t>(value>>(n*8));
}
std::uint64_t get(Span in,std::size_t at,unsigned width){
    if(at>in.size()||width>in.size()-at)throw std::logic_error("fixture read bounds");
    std::uint64_t value{};for(unsigned n=0;n<width;++n)value|=std::uint64_t(in[at+n])<<(n*8);return value;
}
EngineDocumentTarget target(EngineIdentity id){return{id.worker_epoch,id.application_instance,id.document_sequence,id.service_generation};}
Bytes record(std::uint32_t op,EngineIdentity id,Span body={},std::uint64_t transfer=0){
    Bytes out(72+body.size());std::copy_n("FKB1",4,out.begin());put(out,4,1,2);put(out,6,op,2);put(out,8,out.size(),4);
    put(out,16,id.worker_epoch,8);put(out,24,id.application_instance,8);put(out,32,id.document_sequence,8);
    put(out,40,id.service_generation,8);put(out,48,transfer,8);put(out,64,body.size(),4);
    std::copy(body.begin(),body.end(),out.begin()+72);return out;
}
struct Reply{EngineIdentity id;std::uint64_t transfer{};std::uint32_t control{},service{};Bytes bytes;Span body()const{return Span(bytes).subspan(80);}};
Reply call(EngineOwner& owner,std::uint32_t op,EngineIdentity id,Span body={},std::uint64_t transfer=0){
    Bytes out(8192);const auto request=record(op,id,body,transfer);const auto n=owner.dispatch(op,request,out);
    check(n>=80&&static_cast<std::size_t>(n)<=out.size(),"copied Owner receipt missing/oversized");out.resize(static_cast<std::size_t>(n));
    check(get(out,6,2)==(op|0x8000)&&get(out,8,4)==out.size()&&get(out,64,4)==out.size()-72,"copied Owner framing changed");
    return{{get(out,16,8),get(out,24,8),get(out,32,8),get(out,40,8)},get(out,48,8),
        static_cast<std::uint32_t>(get(out,72,4)),static_cast<std::uint32_t>(get(out,76,4)),std::move(out)};
}
void ok(const Reply& r){if(r.control||r.service)throw std::runtime_error("fixture Owner rejected op="+std::to_string(get(r.bytes,6,2)&0x7fff)+
    " transfer="+std::to_string(r.transfer)+" control="+std::to_string(r.control)+" service="+std::to_string(r.service));}
Package package(){
    Package p;p.application={"org.example.bitmap-document","Bitmap document fixture","1.0.0"};
    p.web.present=true;p.web.entry="web/index.html";p.capabilities={"foundation.startup.v1"};p.package_sha256=std::string(64,'1');
    const std::string startup="{\"kind\":\"foundation-appended-startup\",\"primary\":\"web\",\"schema_version\":1}";
    p.files={{"web/.foundation/startup-v1.json","web","application/json",std::string(64,'2'),Bytes(startup.begin(),startup.end())},
        {"web/index.html","web","text/html",std::string(64,'3'),{}}};return p;
}
doc::EngineDocumentProfileFacts profile(bool physical=false){
    doc::EngineDocumentProfileFacts f;f.enabled=true;f.kind=physical?doc::ProfileKind::physical:doc::ProfileKind::pixel;
    f.name=physical?doc::kPhysicalProfileName:doc::kPixelProfileName;f.provider_abi_major=1;f.provider_abi_minor=1;f.host_abi_major=1;
    f.target_system=BIB_ENGINE_TARGET_LINUX;f.target_processor=BIB_ENGINE_CPU_X86_64;f.pointer_bits=64;
    f.lifetime=BIB_ENGINE_LIFETIME_PROCESS;f.maximum_starts=1;f.viewport_width=800;f.viewport_height=600;
    f.provider_capabilities=physical?2003:1795;f.base_header_sha256=doc::kBaseHeaderSha256;f.extension_header_sha256=doc::kExtensionHeaderSha256;
    f.contract_sha256=doc::kContractSha256;f.catalog_sha256=doc::kCatalogSha256;f.build_sha256.fill(1);f.source_recipe_sha256.fill(2);
    if(physical)f.physical_catalog_sha256=doc::kPhysicalCatalogSha256;
    f.queries=doc::kQueries;f.commands=doc::kCommands;f.query_count=1;f.command_count=2;return f;
}
input::EngineSurfaceProfileFacts legacy_profile(){
    input::EngineSurfaceProfileFacts f;f.enabled=true;f.name=input::kInputProfileName;f.contract_sha256=input::kProviderContractSha256;
    f.build_sha256.fill(1);f.source_recipe_sha256.fill(2);f.catalog_sha256=input::kInputCatalogSha256;
    f.provider_capabilities=467;f.surface_capabilities=8225;f.surface_protocol_version=1;f.mouse_input_version=1;f.raw_key_mapping_revision=1;
    f.viewport_width=800;f.viewport_height=600;f.display_scale=1;f.commands=input::kCommands;return f;
}
Bytes frame(std::uint64_t base){
    Bytes out(48+800*600*4);put(out,0,1,4);put(out,4,800,4);put(out,8,600,4);put(out,12,3200,4);
    put(out,24,800,4);put(out,28,600,4);put(out,32,base,8);put(out,40,base+1,8);
    for(std::size_t at=48;at<out.size();at+=4){out[at]=static_cast<std::uint8_t>((base+1)%251);out[at+3]=255;}return out;
}
void safe(const gui::Snapshot& view){
    check(view.widgets.empty()&&view.pages.empty()&&view.commands.empty()&&view.key_bindings.empty()&&!view.modal_root,
          "redacted bitmap publication retained visual page/widget bytes or input declarations");
}
void bitmap(const gui::Snapshot& view,std::uint64_t revision){
    check(view.widgets.size()==1&&view.widgets.front().spec.kind==gui::Kind::bitmap&&
          view.widgets.front().state.bitmap.revision==revision&&view.widgets.front().state.bounds==gui::Rect{0,0,800,600},
          "actual native bitmap frame was missing, stale or replaced by a semantic projection");
}
struct Adapter final:gui::RetainedAdapter{
    bool paired{},fail_before{},fail_after{};std::vector<gui::Snapshot> attempts;std::function<void(std::uint64_t)> legacy;
    std::function<void()> during_present;
    void present(gui::Snapshot next)override{
        const auto revision=next.revision;attempts.push_back(next);if(during_present)during_present();
        if(std::exchange(fail_before,false))throw std::runtime_error("injected before publication");
        gui::RetainedAdapter::present(std::move(next));if(!paired&&legacy)legacy(revision);
        if(std::exchange(fail_after,false))throw std::runtime_error("injected after publication");
    }
};
struct Port final:ui::EngineSurfacePort{
    Adapter& adapter;gui_surface::Capabilities caps;gui_surface::Policy policy;std::vector<gui_surface::Presentation> publications;
    std::uint64_t reported_generation{77};bool service{},fail_service_once{};unsigned service_attempts{};
    static gui_surface::Capabilities offered(){gui_surface::Capabilities c;c.supported=8225;c.mouse_input_version=1;return c;}
    explicit Port(Adapter& a):adapter(a),caps(offered()),policy(caps,77){
        adapter.legacy=[this](std::uint64_t revision){if(policy.accepted())(void)policy.legacy_present(revision);};
    }
    ~Port()override{adapter.legacy={};}
    bool available()const{return !service&&policy.accepted()&&policy.accepted()->available;}
    const gui_surface::Capabilities& capabilities()const noexcept override{return caps;}
    std::uint64_t generation()const noexcept override{return reported_generation;}
    gui_surface::CommitResult present_pair(gui::Snapshot view,const gui_surface::Presentation& p)override{
        check(view.revision==p.identity.presentation_revision&&view.widgets.size()==1&&
              view.widgets.front().spec.key.id==p.identity.owner.id&&view.widgets.front().spec.key.generation==p.identity.owner.generation,
              "paired publication did not name the exact live bitmap/revision");
        check(p.bounds==gui_surface::Rect{0,0,800,600}&&p.clip==p.bounds&&p.display_scale==1,"paired bitmap geometry changed");
        auto prepared=policy.prepare(p);if(prepared.status!=gui_surface::Status::ok)return{prepared.status,{}};
        adapter.paired=true;try{adapter.present(std::move(view));}catch(...){adapter.paired=false;throw;}adapter.paired=false;
        auto committed=policy.commit(std::move(prepared.prepared),p.identity.presentation_revision);
        if(committed.status==gui_surface::Status::ok)publications.push_back(p);
        return committed;
    }
    void set_owned_service_active(bool active)override{
        ++service_attempts;
        if(active&&std::exchange(fail_service_once,false))throw std::runtime_error("injected before physical service gate");
        service=active;if(active&&policy.accepted())(void)policy.legacy_present(adapter.snapshot().revision);
    }
};
struct ModuleCounts{unsigned close{},destroyed{},callbacks{};};
struct Module final:EngineModuleBinding{
    std::shared_ptr<ModuleCounts> counts;std::uint64_t generation;
    Module(std::shared_ptr<ModuleCounts> c,std::uint64_t g):counts(std::move(c)),generation(g){}
    ~Module()override{++counts->destroyed;}
    void close()noexcept override{++counts->close;}
    WebModuleServices services()override{
        return{generation,[c=counts](const DiscoveryQuery&){++c->callbacks;return ProviderDiscovery{};},
            [c=counts](const ProviderRequest&){++c->callbacks;return ProviderOutcome{};},
            [c=counts](std::uint64_t){++c->callbacks;return ServiceStatus::ok;},
            [c=counts,n=std::uint64_t{1}]()mutable->std::optional<std::uint64_t>{++c->callbacks;return n++;}};
    }
};
struct Fixture{
    static constexpr std::string_view service_name="org.example.bitmap-document.native";
    doc::EngineDocumentProfileFacts facts;Adapter adapter;std::shared_ptr<EngineOwner> owner;Port* port{};
    std::unique_ptr<ui::AppendedEngineApplication> app;std::uint64_t input_sequence{},service_sequence{},route{},held{};
    unsigned effects{},provider_entries{};bool hold{},uncertain{};std::shared_ptr<ModuleCounts> module;
    explicit Fixture(bool physical=false,bool with_port=false,bool initialize=true,std::shared_ptr<ModuleCounts> counted={})
        :facts(profile(physical)),module(std::move(counted)){
        EngineOwnerConfiguration c;c.worker_epoch=11;c.application_instance=17;c.document_profile=facts;c.abandon_closed_document_outcomes=true;
        c.native_services.push_back({{std::string(service_name),1,0,SchemaId{7},4},
            [this](std::uint32_t op,Span value,std::span<std::uint8_t> out)->ServiceReply{
                const auto effect=owner->native_effect();check(op==1&&value.size()==4&&out.size()>=4&&effect&&effect->entered&&effect->target==owner->identity(),
                    "actual Registry handler lost its exact entered effect/target");
                safe(adapter.snapshot());check(app&&!app->presentation_pending(),"native handler entered before successful safe bitmap publication");
                if(port)check(port->service&&!port->available(),"native handler entered before physical service suspension");
                if(hold){check(owner->hold_native_effect(effect->ticket),"actual native UI hold refused");held=effect->ticket;}
                ++effects;if(uncertain)return{ServiceStatus::uncertain,0};
                std::copy(value.begin(),value.end(),out.begin());return{ServiceStatus::ok,4};}});
        auto p=package();if(module){p.binary={true,"binary/application.wasm","foundation-guest-v1"};
            p.files.insert(p.files.begin(),{"binary/application.wasm","binary","application/wasm",std::string(64,'4'),{0}});
            c.module_factory=[counts=module](auto,auto,std::uint64_t generation){return std::make_unique<Module>(counts,generation);};}
        owner=std::make_shared<EngineOwner>(std::move(p),std::move(c));ok(call(*owner,1,{11,17,0,0}));ok(call(*owner,4,{11,17,1,0}));commit();
        if(initialize)build(with_port);
    }
    void build(bool with_port,bool preconnect=false){
        std::unique_ptr<ui::EngineSurfacePort> owned;if(with_port){auto actual=std::make_unique<Port>(adapter);port=actual.get();if(preconnect)port->caps={};owned=std::move(actual);}
        app=std::make_unique<ui::AppendedEngineApplication>(adapter,owner,facts,std::move(owned));
        if(port&&!preconnect){app->surface_connected(port->caps);app->tick();}
    }
    std::uint64_t commit(){const auto& old=owner->frame();const auto base=old&&old->identity==owner->identity()?old->frame_revision:0;
        ok(call(*owner,18,owner->identity(),frame(base)));return base+1;}
    std::optional<input::Command> peek(){const auto r=call(*owner,15,owner->identity());
        if(r.control==FOUNDATION_ENGINE_EMPTY)return{};
        ok(r);input::Command value;
        check(input::decode_command(r.body(),value)==input::Status::ok,"copied physical command malformed");return value;}
    input::Command consume(std::int32_t status=0,unsigned disposition=1){
        const auto r=call(*owner,15,owner->identity());ok(r);input::Command command;
        check(input::decode_command(r.body(),command)==input::Status::ok,"missing physical command fixture");
        check(call(*owner,15,owner->identity()).bytes==r.bytes,"physical command peek reminted its immutable authority");
        ok(call(*owner,2,r.id,{},r.transfer));++provider_entries;ok(call(*owner,3,r.id,{},r.transfer));Bytes result;
        check(input::encode_command_result({status,disposition,command.request_sequence,0,0},result)==input::Status::ok,"physical result fixture invalid");
        ok(call(*owner,19,r.id,result,r.transfer));return command;
    }
    std::uint64_t bind(){check(port&&!port->available(),"input available before exact context bind");const auto command=consume();input::Focus value;
        check(command.operation==3&&input::decode_focus(command.payload,value)==input::Status::ok&&value.action==1,"new authority did not stage context bind");
        app->tick();check(port->available(),"consumed fresh bind did not publish paired authority");return value.input_context;}
    void send(gui_surface::Input value){check(port&&port->available(),"surface fixture sent without actual available declaration");
        const auto accepted=port->policy.accept({port->publications.back().identity,++input_sequence,std::move(value)});
        check(accepted.status==gui_surface::Status::ok&&accepted.accepted.has_value(),"actual Surface Policy rejected fixture input");app->surface_input(*accepted.accepted);}
    Bytes service_request(std::uint64_t sequence,std::uint64_t handle,std::uint32_t op,Span raw){
        Envelope h;h.generation=owner->identity().service_generation;h.sequence=sequence;h.interface_handle=handle;h.operation=op;
        Bytes out;check(encode_envelope(h,raw,out)==CodecStatus::ok,"service fixture envelope invalid");return out;}
    std::uint64_t submit(std::uint64_t handle,std::uint32_t op,Span raw){const auto sequence=++service_sequence;
        ok(call(*owner,6,owner->identity(),service_request(sequence,handle,op,raw)));const auto r=call(*owner,12,owner->identity());
        check(r.control==FOUNDATION_ENGINE_CONFLICT&&r.service==2&&owner->native_effect()&&!owner->native_effect()->entered,"queued service skipped App readiness gate");return sequence;}
    void suspend(){app->tick();safe(app->view());safe(adapter.snapshot());
        if(port){check(port->service&&!port->available(),"pending service left surface authority available");
            if(const auto command=peek()){input::Focus retired;check(command->operation==3&&input::decode_focus(command->payload,retired)==input::Status::ok&&retired.action==2,
                "service did not prioritize exact provider context retirement");consume();app->tick();}}
    }
    Bytes collect(std::uint64_t sequence){const auto id=owner->identity();const auto r=call(*owner,13,id);ok(r);Envelope envelope;Span raw;
        check(decode_envelope(r.body(),envelope,raw)==CodecStatus::ok&&envelope.sequence==sequence&&!envelope.service_status,"actual Registry completion invalid");
        Bytes result(raw.begin(),raw.end());const auto accepted=encode_u32(1);ok(call(*owner,16,r.id,accepted,r.transfer));
        const auto staged=call(*owner,8,id,encode_u64(sequence));check(staged.control==0&&staged.service==2,"native service ACK did not stage");
        ok(call(*owner,12,id));const auto ack=call(*owner,14,id);ok(ack);ok(call(*owner,17,ack.id,accepted,ack.transfer));return result;}
    void rearm(){check(!owner->native_effect(),"rearm fixture still owns a native UI effect");
        const auto observed_floor=commit();app->tick();safe(app->view());safe(adapter.snapshot());
        check(!peek(),"completion-edge frame incorrectly rearmed a physical context");
        const auto fresh=commit();check(fresh>observed_floor,"fresh frame fixture did not advance");app->tick();bitmap(app->view(),fresh);bitmap(adapter.snapshot(),fresh);
        if(port)bind();}
    void discover(){if(port&&!port->available())bind();const auto major=encode_u32(1),minor=encode_u32(0);
        const Span name{reinterpret_cast<const std::uint8_t*>(service_name.data()),service_name.size()};
        const std::array<FieldView,4> fields{{{1,FieldType::utf8,true,name},{2,FieldType::u32,true,major},{3,FieldType::u32,true,minor},{4,FieldType::u32,true,minor}}};
        Bytes query;check(encode_record(fields,query)==CodecStatus::ok,"native discovery fixture invalid");const auto sequence=submit(0,FOUNDATION_APPENDED_CONTROL_DISCOVER,query);
        suspend();ok(call(*owner,12,owner->identity()));const auto raw=collect(sequence);std::vector<FieldView> descriptor;
        check(decode_record(raw,descriptor)==CodecStatus::ok&&!descriptor.empty()&&read_u64(descriptor.front(),route)&&route,"actual Registry did not issue an opaque route");rearm();}
};
void typed_admission_and_bitmap_only(){
    {Fixture pixel;bitmap(pixel.app->view(),1);check(pixel.owner->document_enabled()&&!pixel.owner->input_enabled()&&!pixel.peek(),"pixel1795 invented physical input");}
    {Fixture physical(true);bitmap(physical.app->view(),1);check(physical.owner->input_enabled()&&!physical.peek(),"physical2003 no-port mode invented or disabled Owner capability");
        physical.app->surface_connected(Port::offered());physical.app->tick();check(!physical.peek(),"no-port observation mode staged physical authority");}
    Fixture f(false,false,false);const auto count=f.adapter.attempts.size();
    auto rejects=[&](auto construct){bool rejected=false;try{construct();}catch(const std::invalid_argument&){rejected=true;}check(rejected&&f.adapter.attempts.size()==count,"invalid typed mode/facts reached actual presentation");};
    auto wrong=f.facts;wrong.build_sha256[0]^=1;rejects([&]{ui::AppendedEngineApplication app(f.adapter,f.owner,wrong);});
    rejects([&]{ui::AppendedEngineApplication app(f.adapter,f.owner,profile(true));});
    rejects([&]{ui::AppendedEngineApplication app(f.adapter,f.owner);});
    rejects([&]{ui::AppendedEngineApplication app(f.adapter,f.owner,std::make_unique<Port>(f.adapter),legacy_profile());});
    rejects([&]{ui::AppendedEngineApplication app(f.adapter,f.owner,f.facts,std::make_unique<Port>(f.adapter));});
    Fixture preconnect(true,false,false);preconnect.build(true,true);bitmap(preconnect.app->view(),1);check(!preconnect.peek(),"zero-cap preconnect port staged input");
    preconnect.port->caps=Port::offered();preconnect.app->surface_connected(preconnect.port->caps);preconnect.app->tick();preconnect.bind();
    Fixture zero(true,false,false);auto invalid=std::make_unique<Port>(zero.adapter);invalid->reported_generation=0;bool rejected=false;
    try{ui::AppendedEngineApplication app(zero.adapter,zero.owner,zero.facts,std::move(invalid));}catch(const std::invalid_argument&){rejected=true;}
    check(rejected&&zero.adapter.attempts.empty(),"zero-generation physical port reached publication");
}
void native_service_without_port(){
    for(const bool physical:{false,true}){Fixture f(physical);f.discover();const auto sequence=f.submit(f.route,1,encode_u32(41));f.suspend();
        check(f.effects==0&&!f.owner->acknowledge_native_effect(f.owner->native_effect()->ticket),"App used legacy service gate or executed handler during tick");
        ok(call(*f.owner,12,f.owner->identity()));check(f.collect(sequence)==encode_u32(41)&&f.effects==1,"actual no-port native handler did not run once");f.rearm();}
}
void failed_safe_publication(bool after){
    Fixture f;f.discover();const auto sequence=f.submit(f.route,1,encode_u32(42));f.adapter.fail_before=!after;f.adapter.fail_after=after;
    bool failed=false;try{f.app->tick();}catch(const std::runtime_error&){failed=true;}check(failed&&f.effects==0&&f.app->presentation_pending(),"throwing safe publication armed handler readiness");
    const auto attempted=f.adapter.attempts.back();safe(attempted);const auto refused=call(*f.owner,12,f.owner->identity());check(refused.control==FOUNDATION_ENGINE_CONFLICT&&f.effects==0,"failed safe publication permitted native entry");
    f.commit();f.app->retry_presentation();check(f.adapter.attempts.back().revision==attempted.revision&&f.adapter.attempts.back().title==attempted.title,
        "safe publication retry reminted its candidate/revision after an intervening actual frame");safe(f.adapter.snapshot());
    ok(call(*f.owner,12,f.owner->identity()));f.collect(sequence);check(f.effects==1,"safe retry repeated or lost handler");f.rearm();
}
void held_ui_samples_latest_release_frame(){
    Fixture f;f.discover();f.hold=true;const auto sequence=f.submit(f.route,1,encode_u32(43));f.suspend();ok(call(*f.owner,12,f.owner->identity()));f.collect(sequence);
    check(f.held&&f.owner->native_effect(),"known completion erased trusted native UI hold");f.commit();f.commit();f.app->tick();safe(f.adapter.snapshot());
    f.app->set_owned_service_active(false);f.app->tick();check(f.owner->native_effect().has_value(),"frontend-like false released independently owned native UI");
    check(f.owner->release_native_effect(f.held),"trusted UI release refused");const auto release_floor=f.commit();f.app->tick();safe(f.adapter.snapshot());
    f.app->tick();safe(f.adapter.snapshot());const auto fresh=f.commit();check(fresh>release_floor,"release frame fixture not newer");f.app->tick();bitmap(f.adapter.snapshot(),fresh);check(f.effects==1,"held UI rearm replayed native effect");
}
void replacement_requires_actual_frame(){
    Fixture f;f.discover();const auto sequence=f.submit(f.route,1,encode_u32(44));f.suspend();ok(call(*f.owner,12,f.owner->identity()));f.collect(sequence);f.app->tick();safe(f.adapter.snapshot());
    const auto old=f.owner->identity();auto next=old;++next.document_sequence;next.service_generation=0;ok(call(*f.owner,4,next));f.app->tick();safe(f.adapter.snapshot());
    check(call(*f.owner,18,old,frame(1)).control!=FOUNDATION_ENGINE_OK,"retired document supplied replacement pixels");
    const auto revision=f.commit();f.app->tick();bitmap(f.adapter.snapshot(),revision);
    check(f.app->view().widgets.front().state.bitmap.source_id.find("-"+std::to_string(f.owner->identity().service_generation))!=std::string::npos,
          "replacement bitmap retained retired source identity");
}
Bytes ndv2(EngineDocumentTarget id,std::uint64_t sequence,unsigned kind,std::uint64_t nested,std::size_t size){
    Bytes out(size);std::copy_n("NDV2",4,out.begin());put(out,4,2,2);put(out,6,kind,1);put(out,8,id.application_instance,8);put(out,16,id.service_generation,8);
    put(out,24,id.document_sequence,8);put(out,32,sequence,8);put(out,40,nested,8);return out;
}
struct Debt{EngineDocumentWork work;EngineDocumentAdmission admission;};
Debt retain_work(Fixture& f,bool form){
    const auto sequence=f.owner->reserve_document_sequence();check(sequence.has_value(),"debt fixture reservation failed");EngineDocumentWork w;
    w.target=target(f.owner->identity());w.request_sequence=*sequence;w.kind=form?EngineDocumentWorkKind::form_action:EngineDocumentWorkKind::snapshot_query;
    w.operation=form?6:3;w.required_reply_capacity=1048576;w.schema_sha256=doc::kSchema;w.payload=ndv2(w.target,*sequence,form?2:1,form?0:73,form?81:48);
    if(form){put(w.payload,49,w.target.application_instance,8);put(w.payload,57,w.target.service_generation,8);put(w.payload,65,1,8);put(w.payload,73,1,8);}
    const auto admission=f.owner->stage_document_work(w);check(admission.code==EngineDocumentAdmissionCode::admitted,"debt fixture work rejected");const auto peek=call(*f.owner,27,f.owner->identity());ok(peek);
    Bytes claim(16);put(claim,0,static_cast<unsigned>(w.kind),4);put(claim,8,*sequence,8);ok(call(*f.owner,29,peek.id,claim,peek.transfer));
    ok(call(*f.owner,2,peek.id,{},peek.transfer));ok(call(*f.owner,3,peek.id,{},peek.transfer));
    // Owner-only fixed-header join, deliberately not a valid deep NDV2 provider reply.
    const auto raw=ndv2(w.target,*sequence,form?5:4,form?0:73,form?52:48);Bytes result(40+raw.size());put(result,0,static_cast<unsigned>(w.kind),4);put(result,8,*sequence,8);
    put(result,20,form?1:0,4);put(result,24,raw.size(),4);put(result,32,form?0:17,8);std::copy(raw.begin(),raw.end(),result.begin()+40);ok(call(*f.owner,28,peek.id,result,peek.transfer));return{std::move(w),admission};
}
void settle_action_ack(Fixture& f,const Debt& debt){
    const auto a=f.owner->stage_document_action_ack(debt.work.target,debt.work.request_sequence);check(a.code==EngineDocumentAdmissionCode::admitted,"action ACK debt could not stage");
    const auto peek=call(*f.owner,27,f.owner->identity());ok(peek);check(get(peek.body(),0,4)==3,"queued native effect starved form ACK metadata");const auto sequence=get(peek.body(),8,8);
    Bytes claim(16);put(claim,0,3,4);put(claim,8,sequence,8);ok(call(*f.owner,29,peek.id,claim,peek.transfer));Bytes result(56);put(result,0,3,4);put(result,8,sequence,8);put(result,20,1,4);put(result,24,16,4);put(result,40,debt.work.request_sequence,8);
    ok(call(*f.owner,28,peek.id,result,peek.transfer));check(f.owner->consume_document_outcome(a.ticket),"checked metadata ACK result could not collect");
}
void document_and_form_debts_gate_handler(){
    Fixture f;f.discover();for(const bool form:{false,true}){const auto debt=retain_work(f,form);const auto sequence=f.submit(f.route,1,encode_u32(45));f.suspend();
        check(call(*f.owner,12,f.owner->identity()).control==FOUNDATION_ENGINE_CONFLICT,"local retained document/form debt admitted handler");
        if(form){check(!f.owner->consume_document_outcome(debt.admission.ticket),"unACKed form debt released");settle_action_ack(f,debt);f.app->tick();
            check(call(*f.owner,12,f.owner->identity()).control==FOUNDATION_ENGINE_CONFLICT,"ACK alone discarded retained local form result debt");}
        check(f.owner->consume_document_outcome(debt.admission.ticket),"settled local debt could not collect");f.app->tick();ok(call(*f.owner,12,f.owner->identity()));f.collect(sequence);f.rearm();}
    check(f.effects==2,"document debt settlement repeated or lost native effects");
}
void physical2003_retire_then_fresh_pair(){
    Fixture f(true,true);const auto first=f.bind();f.send(gui_surface::FocusChange{true,true,gui_surface::FocusCause::direct});f.app->tick();f.consume();f.app->tick();
    f.send(gui_surface::KeyTransition{gui_surface::KeyPhase::down,"z","KeyY",0,31,false});f.commit();f.app->tick();const auto key_command=f.consume();input::Key key;
    check(input::decode_key(key_command.payload,key)==input::Status::ok&&key.input_context==first&&key.key=="z"&&key.code=="KeyY"&&key.modifiers==31,"document2003 reused fake legacy facts or lost frozen physical mapping");f.app->tick();
    f.discover();const auto old=f.port->publications.back().identity;const auto sequence=f.submit(f.route,1,encode_u32(46));f.suspend();
    ok(call(*f.owner,12,f.owner->identity()));f.collect(sequence);f.rearm();check(f.port->publications.back().available&&f.port->publications.back().identity.context>old.context&&
        f.port->publications.back().identity.presentation_revision>old.presentation_revision,"document2003 service restored retired physical authority");
    gui_surface::Revocation delayed;delayed.identity=old;f.app->surface_revoked(std::move(delayed));f.app->tick();check(f.port->available()&&!f.peek(),"delayed old revocation retired fresh document context");
}
void fallible_owned_service_gate_retries(){
    {
        Fixture f(true,true);f.discover();const auto sequence=f.submit(f.route,1,encode_u32(48));f.port->fail_service_once=true;
        const auto attempts=f.port->service_attempts;bool failed=false;try{f.app->tick();}catch(const std::runtime_error&){failed=true;}
        check(failed&&f.port->service_attempts==attempts+1&&!f.port->service&&f.app->presentation_pending(),
              "throwing native service gate falsely committed actual suspension");safe(f.app->view());
        check(call(*f.owner,12,f.owner->identity()).control==FOUNDATION_ENGINE_CONFLICT&&!f.effects,
              "failed actual service gate authorized a native handler");
        f.suspend();check(f.port->service_attempts>attempts+1&&f.port->service,"native service gate intent was lost instead of retried");
        ok(call(*f.owner,12,f.owner->identity()));f.collect(sequence);check(f.effects==1,"recovered service gate lost or repeated native handler");f.rearm();
    }
    {
        Fixture f(true,true);f.bind();f.port->fail_service_once=true;const auto attempts=f.port->service_attempts;
        bool failed=false;try{f.app->set_owned_service_active(true);}catch(const std::runtime_error&){failed=true;}
        check(failed&&!f.port->service&&f.app->presentation_pending(),"throwing manual service gate falsely committed suspension");safe(f.app->view());
        f.suspend();check(f.port->service_attempts>attempts+1&&f.port->service&&!f.port->available()&&!f.peek(),
              "manual service gate could not retry and settle exact context retirement");
        const auto held_frame=f.commit();f.app->tick();safe(f.adapter.snapshot());f.app->set_owned_service_active(false);f.app->tick();safe(f.adapter.snapshot());
        const auto fresh=f.commit();check(fresh>held_frame,"manual gate fresh-frame fixture did not advance");f.app->tick();bitmap(f.adapter.snapshot(),fresh);f.bind();
        check(!f.effects,"trusted manual suspension simulated a Registry handler");
    }
}
void terminal_case(unsigned kind){
    auto counts=std::make_shared<ModuleCounts>();Fixture f(kind==1||kind==3,kind==1||kind==3,true,counts);
    if(kind==0){f.owner->notify_document_terminal();}
    else if(kind==1){f.bind();f.send(gui_surface::FocusChange{true,true,gui_surface::FocusCause::direct});f.app->tick();f.consume(-8,2);}
    else if(kind==2){f.discover();f.uncertain=true;const auto sequence=f.submit(f.route,1,encode_u32(47));(void)sequence;f.suspend();
        const auto result=call(*f.owner,12,f.owner->identity());check(result.control==FOUNDATION_ENGINE_INTERNAL&&
            result.service==static_cast<unsigned>(ServiceStatus::uncertain)&&f.effects==1&&!f.owner->document_enabled(),"actual uncertain native reply was not terminal");}
    else{f.bind();f.port->fail_service_once=true;f.owner->notify_document_terminal();const auto attempts=f.port->service_attempts;
        bool failed=false;try{f.app->tick();}catch(const std::runtime_error&){failed=true;}
        check(failed&&f.port->service_attempts==attempts+1&&!f.port->service&&f.app->presentation_pending()&&!counts->close&&!counts->destroyed,
              "throwing terminal gate erased pending redaction or performed uncertain cleanup");safe(f.app->view());}
    const auto entered=f.provider_entries;f.app->tick();safe(f.app->view());safe(f.adapter.snapshot());check(f.adapter.closed()&&!f.owner->document_enabled()&&!f.owner->input_enabled(),"terminal bitmap application retained UI/admission");
    f.app->retry_presentation();f.app->tick();check(f.provider_entries==entered&&f.effects==(kind==2?1u:0u)&&!counts->close&&!counts->destroyed,"terminal UI retried native work or ran module cleanup");
    f.app.reset();f.owner.reset();check(!counts->close&&!counts->destroyed,"terminal bitmap lifetime escaped process-lived module quarantine");
}
void closed_presenter_retains_native_debt(){
    auto counts=std::make_shared<ModuleCounts>();Fixture f(false,false,true,counts);const auto debt=retain_work(f,true);
    const auto retained=f.owner->document_outcome(debt.admission.ticket);const auto attempts=f.adapter.attempts.size();
    const auto entries=f.provider_entries;f.adapter.close();f.app->tick();safe(f.app->view());
    check(f.adapter.closed()&&!f.app->presentation_pending()&&!f.owner->closed()&&
          f.adapter.attempts.size()==attempts&&f.provider_entries==entries&&!f.effects,
          "closed sole presenter kept App live, republished old pixels, entered native work or invented completed shutdown");
    check(retained&&retained==f.owner->document_outcome(debt.admission.ticket)&&
          !f.owner->consume_document_outcome(debt.admission.ticket)&&!counts->close&&!counts->destroyed,
          "closed presenter fabricated action retirement or cleaned up retained native debt");
    f.app->retry_presentation();f.app->tick();f.app->shutdown();
    check(!f.app->presentation_pending()&&f.adapter.attempts.size()==attempts&&f.provider_entries==entries&&
          !counts->close&&!counts->destroyed,"stopped closed-presenter App retried publication/native cleanup");
    f.app.reset();f.owner.reset();check(!counts->close&&!counts->destroyed,
          "closed-presenter action debt escaped terminal module quarantine");
}
}
int main(int argc,char** argv){
    try{
        if(argc==3&&std::string_view(argv[1])=="--case"){
            if(std::string_view(argv[2])=="closed-presenter-debt"){
                closed_presenter_retains_native_debt();std::cout<<"PASS closed-presenter-debt, "<<assertions<<" assertions\n";return 0;
            }
            const std::array<std::pair<std::string_view,unsigned>,4> cases{{{"terminal-notify",0},{"terminal-input",1},{"terminal-native",2},{"terminal-port-gate",3}}};
            for(const auto& [name,kind]:cases)if(name==argv[2]){terminal_case(kind);std::cout<<"PASS "<<name<<", "<<assertions<<" assertions\n";return 0;}
            throw std::invalid_argument("unknown isolated bitmap terminal selector");
        }
        if(argc!=1)throw std::invalid_argument("normal groups take no arguments; terminal cases require --case NAME");
        const std::array<std::pair<const char*,void(*)()>,9> cases{{
            {"typed admission and bitmap-only modes",typed_admission_and_bitmap_only},{"native services without a port",native_service_without_port},
            {"safe publication fails before install",+[]{failed_safe_publication(false);}},{"safe publication fails after install",+[]{failed_safe_publication(true);}},
            {"UI hold samples latest release frame",held_ui_samples_latest_release_frame},{"replacement needs actual full frame",replacement_requires_actual_frame},
            {"document/form ACK debt gates",document_and_form_debts_gate_handler},{"physical2003 retirement and fresh pair",physical2003_retire_then_fresh_pair},
            {"fallible owned service gate retries",fallible_owned_service_gate_retries}}};
        for(const auto& [name,test]:cases){test();std::cout<<"PASS "<<name<<'\n';}
        std::cout<<cases.size()<<" bitmap document groups, "<<assertions<<" assertions; terminal selectors require fresh processes; no engine/browser execution\n";
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
