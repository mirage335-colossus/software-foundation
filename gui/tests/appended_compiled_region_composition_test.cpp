// SPDX-License-Identifier: CC0-1.0
// SOURCE-ONLY private successor fixture. Not compiled or executed in this task.
// Uses actual canonical reader/Owner/App; synthetic RGBA is a copied-transport
// fixture, never evidence of an engine, browser, OS, SDK or binary qualification.
#include "shared/engine_primary_region_application.hpp"
#include "shared/compiled_primary_region_application.hpp"
#include "shared/appended_engine_abi.h"
#include "host/contract.hpp"
#include "../../src/appended/sha256.hpp"
#include <gui/retained_adapter.hpp>
#include <algorithm>
#include <array>
#include <iostream>
#include <stdexcept>
#include <utility>

namespace {
using namespace foundation::appended;
using namespace foundation::ui;
using Span = std::span<const std::uint8_t>;
std::size_t assertions{};
void check(bool condition,const char* message) { ++assertions; if (!condition) throw std::runtime_error(message); }
template<class F> void rejects(F action,const char* message) {
    bool rejected=false; try { action(); } catch(const std::invalid_argument&) { rejected=true; }
    check(rejected,message);
}
void put(std::span<std::uint8_t> bytes, std::size_t offset, std::uint64_t value, std::size_t width) {
    for (std::size_t n = 0; n < width; ++n) bytes[offset + n] = static_cast<std::uint8_t>(value >> (8 * n));
}
std::uint64_t get(Span bytes, std::size_t offset, std::size_t width) {
    std::uint64_t value = 0;
    for (std::size_t n = 0; n < width; ++n) value |= std::uint64_t(bytes[offset + n]) << (8 * n);
    return value;
}
Span span(std::string_view text) { return {reinterpret_cast<const std::uint8_t*>(text.data()), text.size()}; }
Bytes request(std::uint32_t operation, EngineIdentity identity, Span body = {}) {
    Bytes bytes(FOUNDATION_ENGINE_HEADER_BYTES + body.size());
    bytes[0] = 'F'; bytes[1] = 'K'; bytes[2] = 'B'; bytes[3] = '1';
    put(bytes, 4, 1, 2); put(bytes, 6, operation, 2); put(bytes, 8, bytes.size(), 4);
    put(bytes, 16, identity.worker_epoch, 8); put(bytes, 24, identity.application_instance, 8);
    put(bytes, 32, identity.document_sequence, 8); put(bytes, 40, identity.service_generation, 8);
    put(bytes, 64, body.size(), 4);
    std::copy(body.begin(), body.end(), bytes.begin() + FOUNDATION_ENGINE_HEADER_BYTES);
    return bytes;
}
Bytes invoke(EngineOwner& owner, std::uint32_t operation, EngineIdentity identity, Span body = {}) {
    const auto input = request(operation, identity, body);
    Bytes output(FOUNDATION_ENGINE_RECEIPT_BYTES);
    const auto count = owner.dispatch(operation, input, output);
    check(count == FOUNDATION_ENGINE_RECEIPT_BYTES, "actual owner did not return a complete receipt");
    return output;
}
void accepted(EngineOwner& owner, std::uint32_t operation, EngineIdentity identity, Span body = {}) {
    const auto reply = invoke(owner, operation, identity, body);
    check(get(reply, 72, 4) == FOUNDATION_ENGINE_OK && get(reply, 76, 4) == 0,
          "actual owner rejected an expected accepted operation");
}

Package package(std::string_view primary="compiled") {
    const bool binary=primary=="binary",composition=primary!="web";
    const auto startup_path=composition ? "web/.foundation/startup-v2.json" : "web/.foundation/startup-v1.json";
    const std::string startup="{\"kind\":\"foundation-appended-startup\",\"primary\":\""+std::string(primary)+
        "\",\"schema_version\":"+(composition ? "2}" : "1}");
    const std::string html="<!doctype html><title>Region fixture</title><input value='owned'>";
    const std::string module=binary ? std::string("\0asm\1\0\0\0",8) : std::string{};
    const auto file=[](std::string_view component,std::string_view path,std::string_view mime,std::size_t offset,std::string_view text) {
        return "{\"component\":\""+std::string(component)+"\",\"length\":"+std::to_string(text.size())+",\"media_type\":\""+std::string(mime)+
            "\",\"offset\":"+std::to_string(offset)+",\"path\":\""+std::string(path)+"\",\"sha256\":\""+
            detail::hex_digest(detail::sha256(span(text)))+"\"}";
    };
    const std::string binary_component=binary ? "{\"entry\":\"binary/application.wasm\",\"present\":true,\"profile\":\"foundation-guest-v1\"}" :
        "{\"entry\":null,\"present\":false,\"profile\":null}";
    const std::string capabilities=binary ? "[\"foundation.gui-composition.v1\",\"foundation.startup.v1\",\"foundation.view.v1\"]" :
        composition ? "[\"foundation.gui-composition.v1\",\"foundation.startup.v1\"]" : "[\"foundation.startup.v1\"]";
    const std::string files=(binary ? file("binary","binary/application.wasm","application/wasm",0,module)+"," : "")+
        file("web",startup_path,"application/json",module.size(),startup)+","+
        file("web","web/index.html","text/html",module.size()+startup.size(),html);
    const auto index="{\"application\":{\"id\":\"org.example.region\",\"name\":\"Region fixture\",\"version\":\"1.0.0\"},"
        "\"components\":{\"binary\":"+binary_component+",\"web\":{\"entry\":\"web/index.html\",\"present\":true}},\"files\":["+files+
        "],\"identities\":{},\"kind\":\"foundation-appended-package\",\"requires\":{\"abi\":{\"major\":1,\"minor\":0},\"capabilities\":"+
        capabilities+",\"services\":"+(binary ? "[\"foundation.view\"]" : "[]")+"},\"schema_version\":1}";
    Bytes data(module.begin(),module.end());data.insert(data.end(),startup.begin(),startup.end());data.insert(data.end(),html.begin(),html.end());
    const auto offset=data.size();data.insert(data.end(),index.begin(),index.end());return read_package(data,offset,index.size());
}
Bytes full_frame(std::uint64_t base, std::uint8_t red) {
    Bytes body(48 + 800 * 600 * 4);
    put(body, 0, 1, 4); put(body, 4, 800, 4); put(body, 8, 600, 4); put(body, 12, 3200, 4);
    put(body, 24, 800, 4); put(body, 28, 600, 4); put(body, 32, base, 8); put(body, 40, base + 1, 8);
    for (std::size_t n = 48; n < body.size(); n += 4) {
        body[n] = red; body[n + 1] = 23; body[n + 2] = 45; body[n + 3] = 255;
    }
    return body;
}

class FailingAdapter final : public gui::RetainedAdapter {
public:
    bool fail_next{};
    std::size_t publications{};
    void present(gui::Snapshot value) override {
        if (std::exchange(fail_next,false)) throw std::runtime_error("injected publication failure");
        gui::RetainedAdapter::present(std::move(value)); ++publications;
    }
};
std::shared_ptr<EngineOwner> owner(EngineStartupPrimary primary=EngineStartupPrimary::compiled) {
    EngineOwnerConfiguration config; config.worker_epoch=11;
    config.startup_primary=primary;
    auto value=std::make_shared<EngineOwner>(package(primary==EngineStartupPrimary::web ? "web" : "compiled"),config);
    accepted(*value,FOUNDATION_ENGINE_CONFIGURE,{11,0,0,0});
    accepted(*value,FOUNDATION_ENGINE_TURN_ENTER,{11,0,0,0});
    accepted(*value,FOUNDATION_ENGINE_BEGIN_DOCUMENT,{11,17,1,0});
    accepted(*value,FOUNDATION_ENGINE_TURN_LEAVE,{11,0,0,0});
    return value;
}
const gui::Widget& bitmap(const gui::Snapshot& view) {
    for (const auto& widget:view.widgets) if(widget.spec.key.id==EngineRegionComposition::engine_id) return widget;
    throw std::runtime_error("No actual frame widget");
}
void geometry_and_owned_ids() {
    const auto region=CompiledPrimaryRegionApplication::make_region(1,0);
    check(region.surface_bounds()==foundation::gui_surface::Rect{220,20,800,600},"Pane changed actual viewport or scale");
    check(region.caret_to_root({3,4,2,18})==foundation::gui_surface::Rect{223,24,2,18},"Caret was not translated once");
    foundation::gui_surface::AcceptedEvent input;
    foundation::gui_surface::MouseTransition mouse; mouse.x=230;mouse.y=32;
    input.event.input=mouse;
    check(region.input_to_engine(input),"Mouse normalization rejected finite input");
    check(std::get<foundation::gui_surface::MouseTransition>(input.event.input).x==10 &&
        std::get<foundation::gui_surface::MouseTransition>(input.event.input).y==12,"Mouse did not reach engine local coordinates");
    mouse.x=200;mouse.y=-4;input.event.input=mouse;region.input_to_engine(input);
    check(std::get<foundation::gui_surface::MouseTransition>(input.event.input).x==-20,"Captured continuation was clipped or rebased");
    mouse.phase=foundation::gui_surface::MousePhase::cancel;mouse.x=0;mouse.y=0;input.event.input=mouse;region.input_to_engine(input);
    check(std::get<foundation::gui_surface::MouseTransition>(input.event.input).x==0,"Cancel placeholder was translated");
    mouse.phase=foundation::gui_surface::MousePhase::context;mouse.context_origin=foundation::gui_surface::ContextOrigin::keyboard;
    input.event.input=mouse;region.input_to_engine(input);
    check(std::get<foundation::gui_surface::MouseTransition>(input.event.input).y==0,"Keyboard context placeholder was translated");
    auto bad=region.compiled();bad.widgets.front().spec.key.id="engine.frame";
    rejects([&]{EngineRegionComposition collision(bad,region.pane());},"Shared identity collision accepted");
    bad=region.compiled();bad.widgets.front().state.bounds={230,30,10,10};
    rejects([&]{EngineRegionComposition overlap(bad,region.pane());},"Compiled input could occlude engine pane");
    rejects([&]{EngineRegionComposition scaled(region.compiled(),{220,20,799,600});},"Unsupported engine scaling accepted");
    bad=region.compiled();bad.title.reserve(1024*1024);
    check(bad.title.capacity()>=1024*1024,"Oversized retained-capacity fixture was not prepared");
    rejects([&]{EngineRegionComposition huge(std::move(bad),region.pane());},"Oversized retained capacity accepted");
    bad=region.compiled();bad.widgets.front().spec.kind=gui::Kind::bitmap;
    rejects([&]{EngineRegionComposition opaque(bad,region.pane());},"Uncharged compiled bitmap callback admitted");
    bad=region.compiled();bad.pages.push_back({"compiled.page","Page"});bad.active_page="compiled.page";
    bad.page_bar={220,20,100,28};
    rejects([&]{EngineRegionComposition overlap(bad,region.pane());},"Page chrome overlaps rich input region");
    auto redacted=region.compiled();
    gui::Widget group;group.spec.key={"compiled.modal",1};group.spec.kind=gui::Kind::group;
    group.state.bounds={0,0,210,640};redacted.widgets.insert(redacted.widgets.begin(),group);
    redacted.modal_root=group.spec.key;
    redacted.commands.push_back({{"compiled.command",1},true,group.spec.key});
    gui::KeyBinding shortcut;shortcut.target={"compiled.increment",1};shortcut.focus=shortcut.target;
    redacted.key_bindings.push_back(shortcut);gui::validate_snapshot(redacted);
    EngineRegionComposition::clear_content(redacted);gui::validate_snapshot(redacted);
    check(redacted.widgets.empty()&&redacted.commands.empty()&&redacted.key_bindings.empty()&&!redacted.modal_root,
        "Redaction retained references to removed widgets");
    check(region.caret_to_root({-4,590,10,24})==foundation::gui_surface::Rect{220,610,6,10},"Caret escaped pane clip");
    auto raw_shell=region.compiled();gui::KeyBinding binding;binding.target={"compiled.increment",1};
    raw_shell.key_bindings.push_back(binding);
    auto capture_owner=owner();FailingAdapter capture_adapter;
    AppendedEngineApplication capture(capture_adapter,capture_owner,EngineRegionComposition(std::move(raw_shell),region.pane()));
    capture.handle(gui::ShortcutEvent{});const auto retained=capture.take_compiled_event();
    check(retained && std::holds_alternative<gui::WidgetEvent>(retained->event) &&
        std::holds_alternative<gui::ShortcutEvent>(retained->raw_event),"Composed admission overwrote the original boundary event");
    check(retained->retained_bytes>=compiled_region_event_charge(retained->event)+compiled_region_event_charge(retained->raw_event),
        "Raw and normalized owning events escaped the shared retained budget");
}
void primary_admission() {
    rejects([&]{ EngineOwner wrong(package(),EngineOwnerConfiguration{}); },"Legacy web-primary Owner accepted compiled startup");
    auto config=EngineOwnerConfiguration{};config.startup_primary=EngineStartupPrimary::compiled;
    auto value=std::make_shared<EngineOwner>(package(),config);
    check(value->startup_primary()==EngineStartupPrimary::compiled,"Immutable root primary lost");
    auto binary_config=EngineOwnerConfiguration{};binary_config.startup_primary=EngineStartupPrimary::binary;
    binary_config.module_factory=[](Span,std::span<const NativeServiceRegistration>,std::uint64_t)->std::unique_ptr<EngineModuleBinding>{
        throw std::logic_error("Admission must reject before any factory entry");};
    auto service_only=package("binary");std::erase(service_only.capabilities,std::string("foundation.view.v1"));
    rejects([&]{EngineOwner rejected(service_only,binary_config);},"Binary primary admitted service without capability");
    auto capability_only=package("binary");std::erase(capability_only.services,std::string("foundation.view"));
    rejects([&]{EngineOwner rejected(capability_only,binary_config);},"Binary primary admitted capability without service");
    auto old_with_composition=package("web");old_with_composition.capabilities.push_back("foundation.gui-composition.v1");
    rejects([&]{EngineOwner rejected(old_with_composition,EngineOwnerConfiguration{});},"Startup-v1 silently selected composition semantics");
    unsigned entered=0;
    binary_config.module_factory=[&](Span,std::span<const NativeServiceRegistration>,std::uint64_t)->std::unique_ptr<EngineModuleBinding>{
        ++entered;throw std::runtime_error("Fixture failure after an admitted initializer entry");};
    EngineOwner failed(package("binary"),binary_config);
    const auto first=invoke(failed,FOUNDATION_ENGINE_CONFIGURE,{1,0,0,0});
    const auto again=invoke(failed,FOUNDATION_ENGINE_CONFIGURE,{1,0,0,0});
    check(get(first,72,4)==FOUNDATION_ENGINE_INTERNAL && get(again,72,4)==FOUNDATION_ENGINE_CLOSED && entered==1,
        "Failed admitted initializer was replayed by CONFIGURE");
}
bool counter(const gui::Snapshot& view,std::uint64_t value) {
    const auto* label=gui::find_widget(view,{"compiled.count",1});
    return label && label->state.text=="Count: "+std::to_string(value);
}
void compiled_feature_and_actual_frame() {
    auto kernel=owner(); const auto identity=kernel->identity();
    accepted(*kernel,FOUNDATION_ENGINE_FRAME_COMMIT,identity,full_frame(0,61));
    FailingAdapter adapter;
    EnginePrimaryRegionApplication app(adapter,kernel);
    check(app.view().widgets.size()==3 && app.view().client_size==gui::Size{1040,640},"Compiled shell and rich region were not composed");
    check(bitmap(app.view()).state.bounds==gui::Rect{220,20,800,600},"Actual engine bitmap did not move to its pane");
    check(!bitmap(app.view()).spec.pointer_input && !bitmap(app.view()).spec.context_input &&
        app.physical_surface_capabilities()==0,"Observation-only composition invented physical capabilities");
    app.handle(gui::WidgetEvent{{"compiled.increment",1},gui::Activate{}});
    check(counter(app.view(),0),"Compiled feature ran from callback");
    app.tick();
    check(counter(app.view(),1) && app.compiled_region_published_revision()==2,"Normal owner turn did not publish compiled feature");
    check(kernel->identity()==identity && kernel->frame()->frame_revision==1,"Compiled feature reran engine work or replaced its Owner");
    app.handle(gui::WidgetEvent{{"compiled.increment",2},gui::Activate{}});app.tick();
    check(counter(app.view(),1),"Stale compiled widget generation was reinterpreted");
    app.handle(gui::WidgetEvent{{"compiled.increment",1},gui::Activate{}});
    adapter.fail_next=true;bool failed=false;try{app.tick();}catch(const std::runtime_error&){failed=true;}
    check(failed && app.presentation_pending() && app.compiled_region_published_revision()==2,"Failed candidate was falsely acknowledged");
    const auto candidate=app.view().revision;
    app.retry_presentation();
    check(app.compiled_region_published_revision()==3 && app.view().revision==candidate &&
        kernel->frame()->frame_revision==1 && counter(app.view(),2),"Presentation retry replayed compiled or engine effects");
    const auto before=adapter.publications;
    accepted(*kernel,FOUNDATION_ENGINE_TURN_ENTER,identity);
    accepted(*kernel,FOUNDATION_ENGINE_FRAME_COMMIT,identity,full_frame(1,71));
    app.tick();check(adapter.publications==before,"Adapter was entered from native callback");
    accepted(*kernel,FOUNDATION_ENGINE_TURN_LEAVE,identity);app.tick();
    check(bitmap(app.view()).state.bitmap.revision==2 && counter(app.view(),2),"Fresh actual frame lost compiled state");
    auto layout=CompiledPrimaryRegionApplication::make_region(4,2);
    auto shell=layout.compiled();shell.client_size={1100,640};
    check(!app.queue_compiled_region(EngineRegionComposition(std::move(shell),{220,20,800,600})),"Live layout change bypassed input retirement");
    app.shutdown();check(app.shutdown_complete() && adapter.closed(),"Compiled wrapper changed local close ownership");
}
// Closed metadata-only binding fixture. It does not claim actual guest/VM
// coverage; the separate Module leaf fixture owns that qualification.
Bytes list(std::initializer_list<Bytes> records) {
    Bytes output(4);put(output,0,records.size(),4);
    for(const auto& record:records){const auto start=output.size();output.resize(start+4);put(output,start,record.size(),4);output.insert(output.end(),record.begin(),record.end());}
    return output;
}
Bytes rectangle(double x,double y,double width,double height) {
    binary_view_detail::Writer value;value.number(1,x);value.number(2,y);value.number(3,width);value.number(4,height);return value.finish();
}
struct BindingProbe {unsigned factories=0,event_exports=0,service_exports=0,closed=0;};
class ClosedBinding final : public EngineModuleBinding {
public:
    std::shared_ptr<EngineModuleView> model=std::make_shared<EngineModuleView>();
    BindingProbe& probe;
    std::uint64_t generation,hosts=0,count=0;
    std::optional<Bytes> event;
    std::optional<gui::ServiceResult> result;
    std::shared_ptr<const EngineModuleServiceRequest> service;
    bool stopped=false;
    ClosedBinding(BindingProbe& state,std::uint64_t value):probe(state),generation(value){++probe.factories;publish();}
    void publish(){
        binary_view_detail::Writer button;button.text(1,"binary.increment");button.u64(2,1);button.u32(3,3);
        button.record(4,rectangle(20,20,160,32));button.text(7,"Count: "+std::to_string(count));
        binary_view_detail::Writer image;image.text(1,"binary.thumbnail");image.u64(2,1);image.u32(3,8);
        image.record(4,rectangle(20,80,40,40));
        binary_view_detail::Writer resource;resource.text(1,"thumbnail");resource.u64(2,1);resource.u32(3,1);resource.u32(4,1);resource.u32(5,3);
        resource.field(6,FieldType::bytes,{9,10,11});image.record(32,resource.finish());
        binary_view_detail::Writer view;view.u64(1,model->snapshot().revision);view.text(2,"Binary compiled region");view.number(3,200);view.number(4,200);
        view.field(6,FieldType::record_list,list({button.finish(),image.finish()}));
        std::array<std::uint8_t,64> output{};check(model->publish(view.finish(),output).status==ServiceStatus::ok,"Actual view model rejected closed fixture");
    }
    WebModuleServices services()override{
        return {generation,[](const DiscoveryQuery&){return ProviderDiscovery{};},[](const ProviderRequest&){return ProviderOutcome{};},
            [](std::uint64_t){return ServiceStatus::ok;},[this]()->std::optional<std::uint64_t>{return ++hosts;}};
    }
    bool supports_view()const noexcept override{return true;}
    std::shared_ptr<const EngineModuleView> view()const noexcept override{return model;}
    bool acknowledge_view(std::uint64_t revision)noexcept override{return model->acknowledge_published(revision);}
    bool stage_view_event(std::uint64_t revision,Span bytes)override{
        if(stopped||event||model->pending()||revision!=model->snapshot().revision||bytes.empty()||bytes.size()>1024*1024)return false;
        event=Bytes(bytes.begin(),bytes.end());return true;
    }
    void ask_service(std::uint64_t id=91){binary_view_detail::Writer request;request.u64(1,id);request.u32(2,3);request.text(3,"Prompt");request.u32(5,64);
        std::array<std::uint8_t,64> output{};check(model->call(2,request.finish(),output).status==ServiceStatus::ok,"Service request decode failed");}
    std::shared_ptr<const EngineModuleServiceRequest> begin_view_service()override{
        if(stopped)return{};
        auto next=model->next_service();
        if(!next)return{};
        service=std::make_shared<const EngineModuleServiceRequest>(EngineModuleServiceRequest{*next});return service;
    }
    std::shared_ptr<const EngineModuleServiceRequest> current_view_service()const noexcept override{return service;}
    bool stage_view_service_result(Span bytes)override{
        if(stopped||result||!service)return false;
        auto decoded=EngineModuleView::decode_service_result(bytes);if(decoded.id!=service->request.id)return false;
        result=std::move(decoded);return true;
    }
    void tick_view()override{
        if(stopped)return;
        if(event){event.reset();++probe.event_exports;++count;model->advance_epoch();publish();}
        if(result){check(model->complete_service(*result),"Matching service result was lost");result.reset();service.reset();++probe.service_exports;model->advance_epoch();}
    }
    void close()noexcept override{if(stopped)return;stopped=true;++probe.closed;model->shutdown();}
};
void selected_binary_root(){
    BindingProbe probe;ClosedBinding* binding=nullptr;
    EngineOwnerConfiguration config;config.worker_epoch=11;config.startup_primary=EngineStartupPrimary::binary;
    config.module_factory=[&](Span,std::span<const NativeServiceRegistration>,std::uint64_t generation){
        auto value=std::make_unique<ClosedBinding>(probe,generation);binding=value.get();return value;};
    auto kernel=std::make_shared<EngineOwner>(package("binary"),config);
    check(read_engine_startup_primary(kernel->package())==EngineStartupPrimary::binary,"Actual startup reader did not select binary");
    accepted(*kernel,FOUNDATION_ENGINE_CONFIGURE,{11,0,0,0});
    accepted(*kernel,FOUNDATION_ENGINE_TURN_ENTER,{11,0,0,0});accepted(*kernel,FOUNDATION_ENGINE_BEGIN_DOCUMENT,{11,17,1,0});
    accepted(*kernel,FOUNDATION_ENGINE_TURN_LEAVE,{11,0,0,0});const auto target=kernel->identity();
    accepted(*kernel,FOUNDATION_ENGINE_FRAME_COMMIT,target,full_frame(0,63));
    FailingAdapter adapter;EnginePrimaryRegionApplication app(adapter,kernel);
    check(probe.factories==1&&app.view().client_size==gui::Size{1000,600}&&bitmap(app.view()).state.bounds==gui::Rect{200,0,800,600},
        "Binary primary did not embed the actual rich frame alongside its one view");
    const auto* thumbnail=gui::find_widget(app.view(),{"binary.thumbnail",1});
    check(thumbnail&&thumbnail->spec.kind==gui::Kind::bitmap,"Typed decoded binary bitmap was lost");
    const auto clipped=gui::availability(app.view(),{"binary.increment",1});
    check(clipped.clip.x+clipped.clip.width<=200&&clipped.clip.y+clipped.clip.height<=200,"Expanded canvas escaped original binary clip");
    app.tick();check(!binding->model->pending()&&app.compiled_region_published_revision()==1,"Actual published binary candidate was not acknowledged");
    app.handle(gui::WidgetEvent{{"binary.increment",1},gui::Activate{}});
    check(probe.event_exports==0,"Binary guest was entered from callback");
    adapter.fail_next=true;bool failed=false;try{app.tick();}catch(const std::runtime_error&){failed=true;}
    check(failed&&probe.event_exports==1&&binding->model->pending()&&app.compiled_region_published_revision()==1,
        "Binary effect/candidate acknowledgment ignored failed presentation");
    app.retry_presentation();app.tick();
    check(probe.event_exports==1&&!binding->model->pending()&&app.compiled_region_published_revision()==2&&kernel->frame()->frame_revision==1,
        "Binary presentation retry replayed view or engine work");
    binding->ask_service();const auto service=app.next_service();
    check(service&&service->id==91&&kernel->current_binary_view_service(),"One-shot service was not retained");
    check(app.complete_service({91,gui::ServiceStatus::success,"owned",{}})&&probe.service_exports==0,"Service callback entered guest");
    check(!app.complete_service({91,gui::ServiceStatus::success,"owned",{}}),"Duplicate service result accepted");
    app.tick();check(probe.service_exports==1&&!kernel->current_binary_view_service()&&probe.factories==1,
        "Service completion did not drain through the same single binding");
    binding->ask_service(92);check(bool(app.next_service()),"Successor service was not offered");
    check(app.complete_service({92,gui::ServiceStatus::cancelled,"ignored","ignored"}) && binding->result &&
        binding->result->value.empty() && binding->result->error.empty(),"Cancelled host result retained payload bytes");
    app.tick();
    binding->ask_service(93);check(bool(app.next_service()),"Oversize result service was not offered");
    check(app.complete_service({93,gui::ServiceStatus::success,std::string(65537,'x'),{}}) && binding->result &&
        binding->result->status==gui::ServiceStatus::error && binding->result->value.empty() &&
        binding->result->error=="Host service result exceeds the 64 KiB view limit","Host result bypassed old view limit");
    app.tick();
    binding->ask_service(94);check(bool(app.next_service()),"Close-debt service was not offered");
    const auto exports=probe.service_exports;
    app.shutdown();check(!app.shutdown_complete()&&probe.closed==1,"Offered external service was mistaken for completed close");
    check(!app.next_service() && !app.complete_service({95,gui::ServiceStatus::cancelled,{},{}}),"Closing root accepted unmatched metadata or new offer");
    check(app.complete_service({94,gui::ServiceStatus::cancelled,{},{}}),"Matching known UI completion did not drain after Owner close");
    app.tick();check(app.shutdown_complete() && probe.service_exports==exports && probe.factories==1,
        "Local completion after close entered guest or fabricated another Owner");
}
class CheckedEntry final : public EnginePrimaryRegionApplication {
public:
    explicit CheckedEntry(gui::Adapter& adapter) : EnginePrimaryRegionApplication(adapter,owner()) {}
};
static_assert(foundation::host::Application<CheckedEntry>);
void old_web_primary_unchanged() {
    auto kernel=owner(EngineStartupPrimary::web);FailingAdapter adapter;
    EnginePrimaryRegionApplication app(adapter,kernel);
    check(app.view().widgets.empty() && app.view().client_size==gui::Size{800,600},"Web primary acquired compiled chrome");
    accepted(*kernel,FOUNDATION_ENGINE_FRAME_COMMIT,kernel->identity(),full_frame(0,62));app.tick();
    check(app.view().widgets.size()==1 && bitmap(app.view()).state.bounds==gui::Rect{0,0,800,600} &&
        app.compiled_region_published_revision()==0,"Web primary changed its old full-client bitmap route");
}
}
int main(){
    try { geometry_and_owned_ids();primary_admission();compiled_feature_and_actual_frame();old_web_primary_unchanged();selected_binary_root();
        std::cout<<"5 groups, "<<assertions<<" assertions\n";return 0;
    } catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
