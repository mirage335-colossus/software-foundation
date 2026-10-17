// SPDX-License-Identifier: CC0-1.0
// A mock C provider plus the real TerminalAdapter, Owner, Driver and one existing
// document presenter. This fixture supplies no engine, loader or retained SDK.
#include "shared/semantic_primary_document_application.hpp"
#include "../src/appended/sha256.hpp"
#include "shared/appended_engine_abi.h"
#include "shared/document_action_v1_codec.hpp"
#include <gui/terminal.hpp>
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <functional>
#include <iostream>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <utility>
#include <vector>

namespace {
using namespace foundation::appended;
using NativeEngineDocumentComposition = foundation::ui::SemanticPrimaryDocumentApplication;
namespace document = foundation::appended::engine_document;
using Span = std::span<const std::uint8_t>;
using Clock = std::chrono::steady_clock;
using namespace std::chrono_literals;
std::size_t assertions{};
void check(bool value, const char* reason) { ++assertions; if (!value) throw std::runtime_error(reason); }
void put(std::span<std::uint8_t> bytes, std::size_t at, std::uint64_t value, unsigned width) {
    if (at > bytes.size() || width > bytes.size() - at) throw std::logic_error("fixture write bounds");
    for (unsigned n = 0; n < width; ++n) bytes[at+n] = static_cast<std::uint8_t>(value >> (8*n));
}
std::uint64_t get(Span bytes, std::size_t at, unsigned width) {
    if (at > bytes.size() || width > bytes.size() - at) throw std::logic_error("fixture read bounds");
    std::uint64_t value{};
    for (unsigned n = 0; n < width; ++n) value |= std::uint64_t(bytes[at+n]) << (8*n);
    return value;
}
struct Wire {
    Bytes bytes;
    void integer(std::uint64_t value, unsigned width) {
        const auto at = bytes.size(); bytes.resize(at+width); put(bytes,at,value,width);
    }
    void text(std::string_view value) {
        integer(value.size(),4); bytes.insert(bytes.end(),value.begin(),value.end());
    }
    void id(EngineDocumentTarget value) {
        integer(value.application_instance,8); integer(value.service_generation,8); integer(value.document_sequence,8);
    }
    void version(EngineDocumentTarget value, std::uint64_t revision) {
        integer(value.application_instance,8); integer(value.service_generation,8); integer(revision,8);
    }
    void header(unsigned kind, const EngineDocumentDispatch& request) {
        integer(0x3256444e,4); integer(2,2); integer(kind,1); integer(0,1);
        id(request.work.target); integer(request.work.request_sequence,8);
        integer(kind == 4 ? get(request.work.payload,40,8) : 0,8);
    }
    void node(std::uint64_t value, std::uint64_t parent, unsigned kind, unsigned children,
              std::string_view tag, std::string_view text_value = {},
              std::string_view name = {}, std::string_view value_text = {}, std::string_view href = {}) {
        integer(value,8); integer(parent,8); integer(kind,1); integer(0,1); integer(children,4);
        text(tag); text(text_value); text(name); text(value_text); text(href);
    }
    void publication(EngineDocumentTarget value, std::uint64_t revision,
                     std::string_view native_value, std::uint64_t lease = 0) {
        id(value); version(value,revision); integer(0,1); // complete paired publication
        integer(revision,8); integer(10,8); integer(0,4); integer(0,4);
        integer(6,4); integer(0,4); integer(1,4); integer(0,1);
        node(1,0,1,3,"body");
        node(10,1,1,0,"input",{},"First field",native_value);
        node(70,1,1,1,"a",{},"Ordinary project link",{},"guide.html");
        node(71,70,2,0,{},"Ordinary project link");
        node(80,1,1,1,"p"); node(81,80,2,0,{},"Paired body observation");
        integer(10,8); integer(0,1); integer(4|8|32,1); // text, focusable/focused/complete
        integer(1|16,4); integer(1,1); integer(lease != 0,1);
        text("text"); text("First field");
        if (lease) { version(value,revision); integer(10,8); integer(lease,8); }
        text(native_value); text(native_value); integer(1,1);
        integer(native_value.size(),4); integer(native_value.size(),4); integer(0,1);
    }
};
Bytes query_reply(const EngineDocumentDispatch& request, std::uint64_t revision, std::string_view value = {}) {
    Wire wire; wire.header(4,request); wire.publication(request.work.target,revision,value); return wire.bytes;
}
Bytes form_reply(const EngineDocumentDispatch& request, unsigned outcome, unsigned code,
                 std::optional<std::uint64_t> revision = {}, std::string_view value = {}, std::uint64_t lease = 0) {
    Wire wire; wire.header(5,request); wire.integer(outcome,1); wire.integer(code,1);
    wire.integer(outcome == 1 ? 0 : 1,1); wire.integer(revision.has_value(),1);
    if (revision) wire.publication(request.work.target,*revision,value,lease);
    return wire.bytes;
}
Bytes ack_reply(std::uint64_t action_sequence, unsigned code = 0) {
    Bytes bytes(16); put(bytes,0,action_sequence,8); put(bytes,8,code,4); return bytes;
}
Span span(std::string_view value) { return {reinterpret_cast<const std::uint8_t*>(value.data()),value.size()}; }
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

document::EngineDocumentProfileFacts profile() {
    document::EngineDocumentProfileFacts result;
    result.enabled = true; result.kind = document::ProfileKind::pixel; result.name = document::kPixelProfileName;
    result.provider_abi_major = BIB_ENGINE_DOCUMENT_V2_ABI_MAJOR;
    result.provider_abi_minor = BIB_ENGINE_DOCUMENT_V2_ABI_MINOR;
    result.host_abi_major = BIB_ENGINE_DOCUMENT_V2_HOST_ABI_MAJOR;
    result.host_abi_minor = BIB_ENGINE_DOCUMENT_V2_HOST_ABI_MINOR;
    #if defined(_WIN32)
    result.target_system = BIB_ENGINE_TARGET_WINDOWS;
#else
    result.target_system = BIB_ENGINE_TARGET_LINUX;
#endif
#if defined(__aarch64__) || defined(_M_ARM64)
    result.target_processor = BIB_ENGINE_CPU_AARCH64;
#else
    result.target_processor = BIB_ENGINE_CPU_X86_64;
#endif
    result.pointer_bits = 64; result.lifetime = BIB_ENGINE_LIFETIME_PROCESS; result.maximum_starts = 1;
    result.viewport_width = 800; result.viewport_height = 600;
    result.provider_capabilities = document::kPixelCapabilities;
    result.base_header_sha256 = document::kBaseHeaderSha256;
    result.extension_header_sha256 = document::kExtensionHeaderSha256;
    result.contract_sha256 = document::kContractSha256; result.catalog_sha256 = document::kCatalogSha256;
    // Explicit synthetic fixture pins only: no retained build/source/runtime is represented.
    result.build_sha256[0] = 0x71; result.source_recipe_sha256[0] = 0x93;
    result.queries = document::kQueries; result.commands = document::kCommands;
    result.query_count = static_cast<std::uint32_t>(result.queries.size());
    result.command_count = static_cast<std::uint32_t>(result.commands.size());
    check(document::document_profile_valid(result),"fixture failed exact common document-profile validation");
    return result;
}
std::string exported_text(const gui::Snapshot& snapshot) {
    std::string result = snapshot.title;
    for (const auto& page : snapshot.pages) result += page.id + page.label;
    for (const auto& widget : snapshot.widgets) {
        const auto& state = widget.state;
        result += state.text + state.label + state.help + state.accessible_name + state.placeholder + state.display_text;
        for (const auto& option : state.options) result += option.id + option.label + option.value;
        for (const auto& option : state.actions) result += option.id + option.label + option.value;
        for (const auto& record : state.records) {
            result += record.id + record.accessible_text;
            for (const auto& cell : record.cells) result += cell.text;
        }
    }
    return result;
}
const gui::Widget& body_list(const gui::Snapshot& snapshot) {
    const auto found = std::find_if(snapshot.widgets.begin(),snapshot.widgets.end(),[&](const auto& value) {
        return value.spec.kind == gui::Kind::list && (!snapshot.modal_root || !gui::in_modal_scope(snapshot,value.spec.key));
    });
    check(found != snapshot.widgets.end(),"application lost its actual generic body list"); return *found;
}
const gui::Widget& editor(const gui::Snapshot& snapshot) {
    const auto found = std::find_if(snapshot.widgets.begin(),snapshot.widgets.end(),[](const auto& value) {
        return value.spec.kind == gui::Kind::text && !value.spec.text_policy.read_only;
    });
    check(found != snapshot.widgets.end(),"leased native field did not expose its real terminal editor"); return *found;
}
gui::WidgetKey button(const gui::Snapshot& snapshot, std::string_view name) {
    const auto found = std::find_if(snapshot.widgets.begin(),snapshot.widgets.end(),[&](const auto& value) {
        return value.spec.kind == gui::Kind::button && (value.state.label == name || value.state.text == name);
    });
    check(found != snapshot.widgets.end(),"expected real form button missing"); return found->spec.key;
}
bool button_enabled(const gui::Snapshot& snapshot, std::string_view name) {
    return gui::find_widget(snapshot,button(snapshot,name))->state.enabled;
}
std::string row(const gui::Snapshot& snapshot, std::string_view text) {
    const auto& records = body_list(snapshot).state.records;
    const auto found = std::find_if(records.begin(),records.end(),[&](const auto& value) {
        return value.accessible_text.find(text) != std::string::npos;
    });
    check(found != records.end(),"independent paired publication lost a native row"); return found->id;
}
std::string terminal_text(gui::TerminalAdapter& terminal) {
    std::string result; for (const auto& line : terminal.render()) result += line+'\n'; return result;
}
void redacted(const gui::Snapshot& snapshot, std::string_view secret) {
    check(snapshot.revision && !snapshot.modal_root && snapshot.key_bindings.empty(),"safe actual frame retained modal input authority");
    check(secret.empty() || exported_text(snapshot).find(secret) == std::string::npos,"safe actual frame leaked an old draft/body string");
    for (const auto& value : snapshot.widgets) {
        check(!value.state.visible && !value.state.enabled,"safe actual frame left an enabled/visible widget");
        check(value.state.text.empty() && value.state.label.empty() && value.state.help.empty() &&
            value.state.accessible_name.empty() && value.state.placeholder.empty() && value.state.display_text.empty() &&
            value.state.records.empty() && value.state.options.empty() && value.state.actions.empty(),
            "hidden safe widget retained old native strings");
    }
    for (const auto& command : snapshot.commands) check(!command.enabled,"safe actual frame retained a live command");
    for (const auto& page : snapshot.pages) check(!page.enabled && !page.visible && page.label.empty(),"safe actual frame retained a native page label");
}

class RecordingAdapter final : public gui::Adapter {
public:
    gui::TerminalAdapter terminal;
    std::vector<gui::Snapshot> attempts;
    mutable std::vector<std::string> measurements;
    std::function<void()> during_present;
    mutable std::function<void()> during_measure;
    bool fail_before{}, fail_after{};
    unsigned failures{};
    explicit RecordingAdapter(gui::EventSink sink) : terminal(std::move(sink)) {}
    void present(gui::Snapshot snapshot) override {
        attempts.push_back(snapshot);
        if (during_present) during_present();
        if (std::exchange(fail_before,false)) { ++failures; throw std::runtime_error("injected before actual install"); }
        terminal.present(std::move(snapshot));
        if (std::exchange(fail_after,false)) { ++failures; throw std::runtime_error("injected after actual install"); }
    }
    gui::Size measure_text(const gui::TextMeasureRequest& request) const override {
        measurements.push_back(request.text); if (during_measure) during_measure(); return terminal.measure_text(request);
    }
    gui::Availability resolved_availability(const gui::WidgetKey& key) const override { return terminal.resolved_availability(key); }
    std::optional<gui::WidgetKey> focused() const override { return terminal.focused(); }
    bool focus(std::optional<gui::WidgetKey> key) override { return terminal.focus(std::move(key)); }
    bool focus_next(bool reverse = false) override { return terminal.focus_next(reverse); }
    void scroll(const gui::WidgetKey& key, gui::Point offset) override { terminal.scroll(key,offset); }
    gui::Point scroll_offset(const gui::WidgetKey& key) const override { return terminal.scroll_offset(key); }
    gui::TextSelection text_selection(const gui::WidgetKey& key) const override { return terminal.text_selection(key); }
    void text_selection(const gui::WidgetKey& key, gui::TextSelection selected) override { terminal.text_selection(key,selected); }
    bool open_popup(const gui::WidgetKey& key) override { return terminal.open_popup(key); }
    void close_popup(const gui::WidgetKey& key) override { terminal.close_popup(key); }
    void invalidate(const gui::WidgetKey& key, gui::PixelRect damage) override { terminal.invalidate(key,damage); }
    bool closed() const override { return terminal.closed(); }
    void close() override { terminal.close(); }
};

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
    bool stopped=false, low=false;
    ClosedBinding(BindingProbe& state,std::uint64_t value,bool low_control=false):probe(state),generation(value),low(low_control){++probe.factories;publish();}
    void publish(){
        binary_view_detail::Writer button;button.text(1,"binary.increment");button.u64(2,1);button.u32(3,3);
        button.record(4,rectangle(20,low?600:20,160,32));button.text(7,"Count: "+std::to_string(count));
        button.text(8,"Count: "+std::to_string(count));
        binary_view_detail::Writer image;image.text(1,"binary.thumbnail");image.u64(2,1);image.u32(3,8);
        image.record(4,rectangle(20,80,40,40));
        binary_view_detail::Writer resource;resource.text(1,"thumbnail");resource.u64(2,1);resource.u32(3,1);resource.u32(4,1);resource.u32(5,3);
        resource.field(6,FieldType::bytes,{9,10,11});image.record(32,resource.finish());
        binary_view_detail::Writer view;view.u64(1,model->snapshot().revision);view.text(2,"Binary compiled region");view.number(3,200);view.number(4,low?680:200);
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
        if(stopped)return{};auto next=model->next_service();if(!next)return{};
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
struct Fixture;
Fixture* active{};
struct Fixture {
    static constexpr std::uint64_t instance = UINT64_C(0x8000000000000023);
    static constexpr std::string_view service_name = "org.example.composition.native";
    std::shared_ptr<EngineOwner> owner;
    BindingProbe binding_probe; ClosedBinding* binary_binding{};
    NativeEngineDriver* driver{};
    std::unique_ptr<NativeEngineDocumentComposition> app;
    std::shared_ptr<int> wake_capture{std::make_shared<int>(1)};
    RecordingAdapter adapter;
    BibEngineHostV1 host{};
    BibEngineDocumentV1 current{instance, UINT64_C(0x8000000000000001), 0};
    Clock::time_point now{1000s};
    std::uint64_t revision{13}, last_action{}, last_ack{}, service_ack{}, route{};
    unsigned calls{}, queries{}, forms{}, acks{}, advances{}, enters{}, leaves{}, disposals{}, effects{}, deliveries{}, callbacks{}, posts{};
    bool in_callback{}, inside{}, synchronous_post{}, query_trap{}, navigate{}, arm_timer{}, fail_publication_after_form{};
    std::string native_value;
    std::optional<Bytes> outgoing;

    explicit Fixture(bool show = true,EngineStartupPrimary primary=EngineStartupPrimary::web,bool low=false) : adapter([this](const gui::Event& event) {
        ++callbacks; in_callback = true;
        try { if (app) app->handle(event); } catch (...) { in_callback = false; throw; }
        in_callback = false;
    }) {
        check(!active,"one C-table composition per fresh process"); active = this;
        EngineOwnerConfiguration config; config.worker_epoch = 17; config.application_instance = instance;
        config.startup_primary=primary;
        if(primary==EngineStartupPrimary::binary)config.module_factory=[this,low](Span,std::span<const NativeServiceRegistration>,std::uint64_t generation){
            auto value=std::make_unique<ClosedBinding>(binding_probe,generation,low);binary_binding=value.get();return value;};
        config.document_profile = profile(); config.abandon_closed_document_outcomes = true;
        config.native_services.push_back({{std::string(service_name),1,0,SchemaId{7},4},
            [this](std::uint32_t operation, Span input, std::span<std::uint8_t> output) -> ServiceReply {
                const auto effect = owner->native_effect();
                check(!in_callback && !inside && effect && effect->entered && operation == 1 && input.size() == 4,
                    "real Registry handler escaped serialized Driver/native-effect gate");
                auto safe=adapter.terminal.snapshot();
                safe.widgets.erase(std::remove_if(safe.widgets.begin(),safe.widgets.end(),[](const auto& widget){
                    return widget.spec.key.id.starts_with("foundation.semantic.");}),safe.widgets.end());
                redacted(safe,"PRIVATE_COMPOSITION_DRAFT");
                check(terminal_text(adapter.terminal).find("PRIVATE_COMPOSITION_DRAFT") == std::string::npos,
                    "real native handler saw private terminal draft before redaction");
                ++effects; std::copy(input.begin(),input.end(),output.begin()); return {ServiceStatus::ok,4};
            }});
        owner = std::make_shared<EngineOwner>(package(primary==EngineStartupPrimary::web?"web":primary==EngineStartupPrimary::compiled?"compiled":"binary"),std::move(config));
        const auto facts = owner->document_profile(); NativeEngineExpectation expected;
        expected.target_system = facts.target_system; expected.target_processor = facts.target_processor;
        expected.pointer_bits = facts.pointer_bits; expected.contract_header_sha256 = facts.contract_sha256;
        expected.build_identity_sha256 = facts.build_sha256; expected.source_recipe_sha256 = facts.source_recipe_sha256;
        expected.document_profile = facts;
        NativeEngineOptions options; options.limits.maximum_reply_bytes = BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY;
        options.maximum_steps_per_tick = 8;
        BibEngineProviderV1 table{}; table.size = sizeof(table); table.abi_major = 1; table.abi_minor = 1;
        auto& build = table.build; build.size = sizeof(build); build.layout_revision = BIB_ENGINE_LAYOUT_V1;
        build.target_system = facts.target_system; build.target_processor = facts.target_processor; build.pointer_bits = facts.pointer_bits;
        build.lifetime = BIB_ENGINE_LIFETIME_PROCESS; build.maximum_starts = 1;
        build.fixed_viewport_width = 800; build.fixed_viewport_height = 600; build.capabilities = facts.provider_capabilities;
        std::copy(facts.contract_sha256.begin(),facts.contract_sha256.end(),build.contract_header_sha256);
        std::copy(facts.build_sha256.begin(),facts.build_sha256.end(),build.build_identity_sha256);
        std::copy(facts.source_recipe_sha256.begin(),facts.source_recipe_sha256.end(),build.source_recipe_sha256);
        table.limits = options.limits; table.start = start; table.advance = advance; table.current_document = current_document;
        table.query = query; table.command = command; table.deliver_services = deliver; table.collect_service_ack = collect;
        table.dispose_retired_service_document = dispose;
        driver = &NativeEngineDriver::bind_once(NativeEngineProvider::checked(table,expected),owner,options,
            {this,[](void* p) noexcept { auto& f = *static_cast<Fixture*>(p); if (f.app) f.app->wake(); }});
        driver->start_once(now); driver->tick(now += 1ms);
        check(driver->state() == NativeEngineState::ready && owner->configured() && owner->has_module()==(primary==EngineStartupPrimary::binary),
            "fixture did not start actual VM-free Owner/Driver");
        app = std::make_unique<NativeEngineDocumentComposition>(adapter,owner,*driver,[this, retained = wake_capture] {
            (void)retained;
            ++posts;
            if (synchronous_post && app) app->tick(now); // Deliberately violate schedule-only contract: must refuse entry.
        });
        adapter.terminal.terminal_size(56,17);
        if (show) { app->drawable_cells(56,16); until([&]{
            if(primary==EngineStartupPrimary::web)return app->body_ready();
            const auto* control=gui::find_widget(app->view(),{primary==EngineStartupPrimary::binary?"binary.increment":"compiled.increment",1});
            return control&&control->state.visible&&control->state.enabled;
        },"initial actual semantic primary publication failed"); }
    }
    ~Fixture() { app.reset(); active = nullptr; }
    void tick() { app->tick(now += 1ms); }
    template<class Done> void until(Done done, const char* reason) {
        for (unsigned i = 0; i != 24 && !done(); ++i) tick();
        if (!done()) std::cerr << "diagnostic: state=" << static_cast<unsigned>(driver->state())
            << " closed=" << app->closed() << " pending=" << app->presentation_pending()
            << " modal=" << app->modal_open() << " queries=" << queries << " forms=" << forms
            << " acks=" << acks << " deliveries=" << deliveries << " effects=" << effects
            << " last-service=" << driver->last_service_status() << " error=" << app->last_error() << '\n';
        check(done(),reason);
    }
    template<class Fn> std::int32_t turn(Fn fn, bool delivery_collector = false) {
        ++calls; check(!in_callback && !inside && (!owner->callback_depth() ||
            (delivery_collector && owner->callback_depth() == 1)),"provider entered from Adapter callback or recursively");
        inside = true; check(host.enter_engine(host.context) == FOUNDATION_APPENDED_SERVICE_OK,"mock native TURN refused"); ++enters;
        const auto status = fn();
        host.leave_engine(host.context); ++leaves; inside = false; return status;
    }
    void begin_document() {
        BibEngineResourceEpochV1 epoch{}; epoch.size = sizeof(epoch);
        check(!current.service_generation && host.begin_resource_epoch(host.context,&current,&epoch) == BIB_ENGINE_OK &&
            epoch.resource_epoch,"mock native resource epoch refused");
        current.service_generation = host.begin_service_document(host.context,&current);
        check(current.service_generation && owner->identity().service_generation == current.service_generation,
            "mock provider lost same real Owner service generation");
    }
    static std::int32_t BIB_ENGINE_CALL start(const BibEngineHostV1* host, const BibEngineStartV1* config,
            BibEngineStartResultV1* result) {
        auto& f = *active; f.host = *host;
        check(config && config->raster_output == 1 && config->required_capabilities == document::kPixelCapabilities,
            "composition fixture changed actual pixel1795/raster contract");
        const auto status = f.turn([&]{ f.begin_document(); return BIB_ENGINE_OK; });
        *result = {sizeof(*result),BIB_ENGINE_START_READY,instance}; return status;
    }
    static std::int32_t BIB_ENGINE_CALL advance(const BibEngineAdvanceV1*) {
        auto& f = *active; ++f.advances;
        return f.turn([&] {
            if (f.navigate) { f.navigate = false; ++f.current.document_sequence; f.current.service_generation = 0; f.begin_document(); }
            if (std::exchange(f.arm_timer,false)) f.host.replace_timer_ms(f.host.context,25,1);
            if (f.outgoing) {
                const BibEngineBytesV1 bytes{f.outgoing->data(),static_cast<std::uint32_t>(f.outgoing->size()),0};
                check(f.host.submit_service(f.host.context,f.current.service_generation,&bytes,0) == FOUNDATION_APPENDED_SERVICE_OK,
                    "mock provider failed real Registry submission"); f.outgoing.reset();
            }
            return BIB_ENGINE_OK;
        });
    }
    static std::int32_t BIB_ENGINE_CALL current_document(std::uint64_t application, BibEngineDocumentV1* value) {
        auto& f = *active; return f.turn([&] { check(application == instance,"current application identity changed"); *value = f.current; return BIB_ENGINE_OK; });
    }
    EngineDocumentDispatch request(const BibEngineDocumentV1& expected, std::uint64_t sequence, Span bytes,
            EngineDocumentWorkKind kind) {
        check(expected.application_instance == instance && expected.service_generation && sequence,
            "provider request lost actual native document identity");
        EngineDocumentDispatch result;
        result.work.target = {owner->identity().worker_epoch,expected.application_instance,expected.document_sequence,expected.service_generation};
        result.work.request_sequence = sequence; result.work.kind = kind; result.work.payload.assign(bytes.begin(),bytes.end());
        return result;
    }
    static void copy(BibEngineReplyBufferV1* buffer, const Bytes& bytes) {
        check(buffer && buffer->bytes && bytes.size() <= buffer->capacity,"mock provider reply capacity changed");
        std::copy(bytes.begin(),bytes.end(),buffer->bytes);
    }
    static std::int32_t BIB_ENGINE_CALL query(const BibEngineQueryV1* query, BibEngineReplyBufferV1* buffer,
            BibEngineQueryResultV1* result) {
        auto& f = *active; ++f.queries;
        check(query && query->kind == BIB_ENGINE_QUERY_DOCUMENT_FORMS_V2 && query->payload.length == 48,
            "composition changed paired query catalog");
        const Span raw(query->payload.data,query->payload.length);
        auto request = f.request(query->expected,get(raw,32,8),raw,EngineDocumentWorkKind::snapshot_query);
        return f.turn([&] {
            if (f.query_trap) throw std::runtime_error("injected uncertain native provider unwind");
            const auto bytes = query_reply(request,f.revision,f.native_value); copy(buffer,bytes);
            *result = {sizeof(*result),static_cast<std::uint32_t>(bytes.size()),query->expected,f.revision}; return BIB_ENGINE_OK;
        });
    }
    static std::int32_t BIB_ENGINE_CALL command(const BibEngineCommandV1* command, BibEngineReplyBufferV1* buffer,
            BibEngineCommandResultV1* result) {
        auto& f = *active;
        check(!f.in_callback && command && command->request_sequence,"command entered GUI callback or lost sequence");
        if (command->operation == BIB_ENGINE_COMMAND_ACK_FORM_ACTION_V2) {
            ++f.acks; ++f.calls;
            check(!f.inside && !f.owner->callback_depth() && command->payload.length == 8 &&
                get({command->payload.data,command->payload.length},0,8) == f.last_action &&
                command->request_sequence > f.last_action && command->expected.service_generation == f.current.service_generation,
                "metadata ACK acquired TURN or changed exact action identity");
            const auto bytes = ack_reply(f.last_action); copy(buffer,bytes); f.last_ack = f.last_action;
            *result = {sizeof(*result),1,command->request_sequence,static_cast<std::uint32_t>(bytes.size()),0}; return BIB_ENGINE_OK;
        }
        check(command->operation == BIB_ENGINE_COMMAND_FORM_ACTION_V2,"unexpected non-form native command"); ++f.forms;
        const Span raw(command->payload.data,command->payload.length);
        auto request = f.request(command->expected,command->request_sequence,raw,EngineDocumentWorkKind::form_action);
        return f.turn([&] {
            f.last_action = command->request_sequence;
            if (get(raw,48,1) == 1) {
                check(raw.size() >= 102 && get(raw,98,4) == raw.size()-102,"Apply lost exact copied UTF8 value");
                f.native_value.assign(raw.begin()+102,raw.end());
            }
            ++f.revision; const auto bytes = form_reply(request,0,0,f.revision,f.native_value,f.revision+87);
            copy(buffer,bytes); *result = {sizeof(*result),1,command->request_sequence,static_cast<std::uint32_t>(bytes.size()),1};
            if (std::exchange(f.fail_publication_after_form,false)) f.adapter.fail_after = true;
            return BIB_ENGINE_OK;
        });
    }
    static std::int32_t BIB_ENGINE_CALL deliver(const BibEngineDocumentV1* expected, const BibEngineBytesV1* bytes) {
        auto& f = *active;
        return f.turn([&] {
            check(expected && expected->service_generation == f.current.service_generation && bytes,"service delivery changed actual Owner domain");
            Envelope envelope; Span raw;
            check(decode_envelope({bytes->data,bytes->length},envelope,raw) == CodecStatus::ok && !envelope.service_status,
                "actual Registry delivery framing/status changed");
            f.service_ack = envelope.sequence; ++f.deliveries;
            if (envelope.sequence == 1) {
                std::vector<FieldView> fields;
                check(decode_record(raw,fields) == CodecStatus::ok && fields.size() == 6 && read_u64(fields.front(),f.route) && f.route,
                    "real Registry discovery omitted opaque route");
            } else {
                const auto expected_reply = encode_u32(41);
                check(std::equal(raw.begin(),raw.end(),expected_reply.begin(),expected_reply.end()),"real native effect reply changed");
            }
            return BIB_ENGINE_OK;
        });
    }
    static std::uint32_t BIB_ENGINE_CALL collect(const BibEngineDocumentV1* expected) {
        auto& f = *active;
        check(!f.in_callback && expected && expected->service_generation == f.current.service_generation,"service ACK changed actual generation");
        std::uint32_t status = FOUNDATION_APPENDED_SERVICE_UNAVAILABLE;
        (void)f.turn([&] {
            if (f.service_ack) {
                status = f.host.stage_service_ack(f.host.context,expected->service_generation,f.service_ack);
                if (status == FOUNDATION_APPENDED_SERVICE_OK) f.service_ack = 0;
            }
            return BIB_ENGINE_OK;
        },true);
        return status;
    }
    static std::int32_t BIB_ENGINE_CALL dispose(std::uint64_t application, std::uint64_t generation) {
        auto& f = *active; ++f.disposals;
        return f.turn([&]{ check(application == instance && generation,"retirement identity changed"); return BIB_ENGINE_OK; });
    }
    void activate_field() {
        const auto key = body_list(app->view()).spec.key; const auto record = row(app->view(),"First field");
        const auto before = calls; app->handle(gui::WidgetEvent{key,gui::ActivateRecord{record}});
        check(calls == before,"body Adapter event entered native provider");
    }
    void open() {
        activate_field(); until([&]{ return app->modal_open() && acks && last_ack == last_action; },"Begin/form ACK did not settle");
        for (unsigned i = 0; i != 3; ++i) tick();
        check(adapter.terminal.focus(editor(app->view()).spec.key),"real terminal editor focus failed");
    }
    void apply(std::string_view text) {
        const auto before = calls; adapter.terminal.input("\x01\x1b[200~"+std::string(text)+"\x1b[201~");
        check(editor(app->view()).state.text == text && button_enabled(app->view(),"Apply"),
            "real terminal edit did not produce an enabled shared draft Apply");
        adapter.terminal.input("\x13");
        check(calls == before,"terminal edit/Apply Adapter callback entered provider");
    }
    void send(std::uint64_t sequence, std::uint64_t handle, std::uint32_t operation, Span raw) {
        Envelope envelope; envelope.generation = current.service_generation; envelope.sequence = sequence;
        envelope.interface_handle = handle; envelope.operation = operation; Bytes bytes;
        check(encode_envelope(envelope,raw,bytes) == CodecStatus::ok,"service envelope fixture encoding failed");
        outgoing = std::move(bytes); driver->request_advance();
    }
    void discover() {
        const auto major = encode_u32(1), minor = encode_u32(0);
        const Span name{reinterpret_cast<const std::uint8_t*>(service_name.data()),service_name.size()};
        const std::array<FieldView,4> fields{{{1,FieldType::utf8,true,name},{2,FieldType::u32,true,major},
            {3,FieldType::u32,true,minor},{4,FieldType::u32,true,minor}}}; Bytes bytes;
        check(encode_record(fields,bytes) == CodecStatus::ok,"discovery fixture encoding failed");
        send(1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER,bytes);
        until([&]{ return route != 0; },"real Driver/Owner Registry discovery failed");
        until([&]{ return app->body_ready(); },"real Registry completion did not restore fresh paired document");
    }
};

} // namespace
