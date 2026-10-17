// SPDX-License-Identifier: CC0-1.0
// A mock C provider plus the real TerminalAdapter, Owner, Driver and one existing
// document presenter. This fixture supplies no engine, loader or retained SDK.
#include "../gui/shared/native_engine_document_composition.hpp"
#include "../gui/shared/appended_engine_abi.h"
#include "../gui/shared/document_action_v1_codec.hpp"
#include "appended_document_actions_fixture.hpp"
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
using foundation::ui::NativeEngineDocumentComposition;
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
Package package() {
    Package result;
    result.application = {"org.example.document-application","Document application fixture","1.0.0"};
    result.web.present = true; result.web.entry = "web/index.html";
    result.capabilities = {"foundation.startup.v1"}; result.package_sha256 = std::string(64,'1');
    const std::string startup = "{\"kind\":\"foundation-appended-startup\",\"primary\":\"web\",\"schema_version\":1}";
    result.files = {{"web/.foundation/startup-v1.json","web","application/json",std::string(64,'2'),Bytes(startup.begin(),startup.end())},
        {"web/index.html","web","text/html",std::string(64,'3'),{}}};
    return result;
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

struct Fixture;
Fixture* active{};
struct Fixture {
    static constexpr std::uint64_t instance = UINT64_C(0x8000000000000023);
    static constexpr std::string_view service_name = "org.example.composition.native";
    std::shared_ptr<EngineOwner> owner;
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

    explicit Fixture(bool show = true) : adapter([this](const gui::Event& event) {
        ++callbacks; in_callback = true;
        try { if (app) app->handle(event); } catch (...) { in_callback = false; throw; }
        in_callback = false;
    }) {
        check(!active,"one C-table composition per fresh process"); active = this;
        EngineOwnerConfiguration config; config.worker_epoch = 17; config.application_instance = instance;
        config.document_profile = profile(); config.abandon_closed_document_outcomes = true;
        config.native_services.push_back({{std::string(service_name),1,0,SchemaId{7},4},
            [this](std::uint32_t operation, Span input, std::span<std::uint8_t> output) -> ServiceReply {
                const auto effect = owner->native_effect();
                check(!in_callback && !inside && effect && effect->entered && operation == 1 && input.size() == 4,
                    "real Registry handler escaped serialized Driver/native-effect gate");
                redacted(adapter.terminal.snapshot(),"PRIVATE_COMPOSITION_DRAFT");
                check(terminal_text(adapter.terminal).find("PRIVATE_COMPOSITION_DRAFT") == std::string::npos,
                    "real native handler saw private terminal draft before redaction");
                ++effects; std::copy(input.begin(),input.end(),output.begin()); return {ServiceStatus::ok,4};
            }});
        owner = std::make_shared<EngineOwner>(package(),std::move(config));
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
        check(driver->state() == NativeEngineState::ready && owner->configured() && !owner->has_module(),
            "fixture did not start actual VM-free Owner/Driver");
        app = std::make_unique<NativeEngineDocumentComposition>(adapter,owner,*driver,[this, retained = wake_capture] {
            (void)retained;
            ++posts;
            if (synchronous_post && app) app->tick(now); // Deliberately violate schedule-only contract: must refuse entry.
        });
        adapter.terminal.terminal_size(56,17);
        if (show) { app->drawable_cells(56,16); until([&]{ return app->body_ready(); },"initial real terminal publication failed"); }
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

void query_apply_ack() {
    Fixture f; check(f.app->view().client_size == gui::Size{448,256},"actual56x16 drawable cells lost chrome exclusion");
    f.open();
    const auto old_forms = f.forms, old_acks = f.acks;
    f.apply("Owned terminal composition draft"); f.tick();
    check(f.forms == old_forms+1 && f.acks == old_acks,"new action ACK entered same stage/Driver/settle turn");
    f.until([&]{ return f.acks == old_acks+1 && f.last_ack == f.last_action; },"exact action metadata ACK did not drain on later turn");
    for (unsigned i = 0; i != 4; ++i) f.tick();
    check(f.native_value == "Owned terminal composition draft" && editor(f.app->view()).state.text == f.native_value &&
        f.forms == old_forms+1 && f.acks == old_acks+1 && f.app->modal_open(),"Apply replayed or lost shared presenter readback");
    check(f.owner == f.driver->owner() && !f.owner->has_module() && !f.app->next_service(),"facade substituted Owner/Module/native GUI services");
}
void actual_cells() {
    Fixture f(false); check(!f.app->body_ready() && !f.app->view().revision,"facade invented initial viewport/presentation");
    f.app->drawable_cells(-1,16); f.tick(); check(!f.queries,"negative actual cells started document presenter");
    f.app->drawable_cells(56,16); f.until([&]{ return f.app->body_ready(); },"valid actual cells did not start sole presenter");
    const auto epoch = f.app->input_epoch();
    f.app->handle(gui::ResizeEvent{{900,700}}); f.tick();
    check(f.app->view().client_size == gui::Size{448,256},"logical ResizeEvent replaced actual physical cells");
    f.app->drawable_cells(0,0); check(!f.app->body_ready() && f.app->input_epoch() != epoch,"zero cells did not revoke local input immediately");
    f.tick(); redacted(f.adapter.terminal.snapshot(),"Paired body observation");
    for (const auto& [columns,rows] : std::array<std::pair<int,int>,3>{{{501,16},{40,201},{-9,-1}}}) {
        f.app->drawable_cells(columns,rows); f.tick(); check(!f.app->body_ready(),"out-of-range cells armed document input");
    }
    f.app->drawable_cells(40,9); f.until([&]{ return f.app->body_ready(); },"restored actual cells did not obtain fresh paired observation");
    check(f.app->view().client_size == gui::Size{320,144},"actual resize invented minimum or chrome row");
    f.app->foreground(false); f.tick(); redacted(f.adapter.terminal.snapshot(),"Paired body observation");
    f.app->foreground(true); f.until([&]{ return f.app->body_ready(); },"foreground restoration failed fresh paired publication");
    f.app->drawable_cells(1,1); f.tick();
    check(f.app->view().client_size == gui::Size{8,16} && !f.app->body_ready(),"narrow actual cells invented larger viewport or armed body");
}
void callback_barriers() {
    Fixture f; f.synchronous_post = true;
    const auto before = f.calls; f.app->wake(); check(f.calls == before,"synchronous scheduling callback pumped Driver");
    f.adapter.during_present = [&] { const auto count = f.calls; f.app->tick(f.now); f.app->retry_presentation();
        check(f.calls == count,"Adapter publication callback reentered Driver"); };
    f.adapter.during_measure = [&] { const auto count = f.calls; f.app->tick(f.now); check(f.calls == count,"Adapter measurement callback reentered Driver"); };
    f.app->qualify([&]{ f.app->tick(f.now); }); check(f.calls == before,"qualification callback reentered Driver");
    f.app->drawable_cells(49,12); f.until([&]{ return f.app->body_ready(); },"callback guarded presentation failed");
    std::thread worker([&]{ f.app->wake(); }); worker.join();
    check(f.calls >= before && f.driver->state() == NativeEngineState::ready,"worker schedule damaged live Driver");
    const auto advance = f.advances; f.driver->request_advance(); f.tick();
    check(f.advances == advance+1,"callback barrier lost later requested engine advance");
    f.arm_timer = true; f.driver->request_advance(); f.tick();
    check(f.app->deadline() == f.driver->deadline() && f.app->deadline().has_value(),"facade changed Driver deadline");
    f.adapter.during_present = {}; f.adapter.during_measure = {};
}
void presentation_retry() {
    Fixture f; f.open(); const auto old_forms = f.forms, old_acks = f.acks;
    f.apply("Retained exact action"); f.fail_publication_after_form = true;
    for (unsigned n = 0; n != 8 && !f.adapter.failures; ++n) try { f.tick(); } catch (const std::runtime_error&) {}
    check(f.adapter.failures == 1 && f.forms == old_forms+1 && f.app->presentation_pending(),
        "failed actual publication after consumed action did not retain exact debt");
    const auto attempted = f.adapter.attempts.back().revision;
    const auto entered = f.calls; f.app->retry_presentation();
    check(f.calls == entered && f.adapter.terminal.snapshot().revision == attempted,"presentation retry entered provider or changed immutable candidate");
    f.until([&]{ return f.acks == old_acks+1; },"retained action ACK did not settle after exact presentation retry");
    for (unsigned i = 0; i != 4; ++i) f.tick();
    check(f.forms == old_forms+1 && f.native_value == "Retained exact action","presentation failure replayed native Apply");
}
void callback_facts() {
    Fixture f; const auto before = f.calls;
    bool queued = false;
    f.adapter.during_present = [&] {
        if (!std::exchange(queued,true)) f.app->drawable_cells(33,7);
        f.app->tick(f.now);
        check(f.calls == before,"Adapter queued-cell callback entered Driver before newer safe facts applied");
    };
    f.app->drawable_cells(47,14); f.tick();
    check(queued && f.app->presentation_pending() && !f.app->body_ready() && f.calls == before,
        "newer callback cells were overwritten or let Driver overtake pending facts");
    f.adapter.during_present = {};
    f.until([&]{ return f.app->body_ready(); },"newer callback cells never obtained fresh paired publication");
    check(f.app->view().client_size == gui::Size{264,112},"reentrant cell update was marked applied to older viewport");
}
void callback_close() {
    Fixture f(false); const auto queries = f.queries, forms = f.forms, advances = f.advances;
    f.adapter.during_present = [&] { f.app->handle(gui::CloseEvent{}); f.app->tick(f.now); };
    f.app->drawable_cells(56,16); f.tick();
    check(f.app->closed() && f.queries == queries && f.forms == forms && f.advances == advances,
        "Close during Adapter publication admitted later ordinary query/action/advance");
    f.adapter.during_present = {};
    f.until([&]{ return f.driver->state() == NativeEngineState::detached; },"mid-publication close did not drain bounded normal retirement");
}
void registry_gate() {
    Fixture f; f.discover(); f.open(); f.adapter.terminal.input("PRIVATE_COMPOSITION_DRAFT");
    check(editor(f.app->view()).state.text == "PRIVATE_COMPOSITION_DRAFT","real terminal draft missing before native effect");
    const auto queries_before_effect = f.queries;
    f.adapter.during_present = [&] {
        const auto effect = f.owner->native_effect();
        if (effect && !effect->entered && !f.adapter.failures) f.adapter.fail_before = true;
    };
    f.send(2,f.route,1,encode_u32(41));
    for (unsigned n = 0; n != 12 && !f.adapter.failures; ++n) try { f.tick(); } catch (const std::runtime_error&) {}
    f.adapter.during_present = {};
    check(f.adapter.failures == 1 && f.app->presentation_pending() && !f.effects,
        "failed safe publication admitted actual native Registry callback");
    f.app->retry_presentation(); check(!f.effects,"presentation retry directly ran native service");
    const auto safe_revision = f.adapter.terminal.snapshot().revision;
    f.until([&]{ return f.effects == 1 && f.deliveries == 2; },"Driver failed actual gated Registry effect/completion");
    f.until([&]{ return f.queries > queries_before_effect && f.app->modal_open() &&
        !f.app->presentation_pending() && f.adapter.terminal.snapshot().revision > safe_revision &&
        !button_enabled(f.app->view(),"Apply"); },"second native effect did not restore a fresh paired modal with revoked old Apply lease");
    check(editor(f.app->view()).state.text == "PRIVATE_COMPOSITION_DRAFT",
        "fresh paired restoration discarded the retained same-generation local draft");
    check(f.effects == 1 && f.forms == 1,"native service completion replayed effect/form");
}
void close_held_result() {
    Fixture f; f.open(); const auto old_forms = f.forms, old_acks = f.acks;
    f.apply("Retained action at close"); f.fail_publication_after_form = true;
    for (unsigned n = 0; n != 8 && !f.adapter.failures; ++n) try { f.tick(); } catch (const std::runtime_error&) {}
    check(f.adapter.failures == 1 && f.forms == old_forms+1 && f.acks == old_acks,
        "close fixture did not hold a consumed unpublished action before its ACK");
    std::shared_ptr<const EngineDocumentCompletion> retained;
    for (std::uint64_t ticket = 1; ticket != 64; ++ticket) {
        const auto value = f.owner->document_outcome(ticket);
        if (value && value->request_sequence == f.last_action && value->kind == EngineDocumentWorkKind::form_action)
            retained = value;
    }
    check(retained && retained->outcome == EngineDocumentOutcome::consumed && !retained->bytes.empty(),
        "close fixture lost actual Owner-issued action evidence");
    const auto original = *retained; const std::weak_ptr<int> captures = f.wake_capture;
    f.app->shutdown();
    for (unsigned n = 0; n != 4; ++n) f.tick();
    check(f.driver->state() == NativeEngineState::closing && !f.owner->closed() &&
        f.forms == old_forms+1 && f.acks == old_acks && !f.owner->consume_document_outcome(original.ticket),
        "unsettled close invented ACK, discarded retained action or claimed detached readiness");
    f.app.reset(); f.wake_capture.reset();
    const auto after = f.owner->document_outcome(original.ticket);
    check(!captures.expired() && after == retained && after->bytes == original.bytes && after->target == original.target &&
        after->request_sequence == original.request_sequence,"unsettled close destroyed complete composition/captures or altered original evidence");
}
void navigation_close() {
    Fixture f; const auto old = f.current; f.navigate = true; f.driver->request_advance(); f.tick();
    f.until([&]{ return f.app->body_ready() && f.current.document_sequence != old.document_sequence; },"same Owner navigation did not restore fresh document");
    const auto entered = f.calls; f.app->handle(gui::CloseEvent{});
    check(f.calls == entered && f.app->closed(),"Close Adapter callback exported cleanup synchronously");
    f.until([&]{ return f.driver->state() == NativeEngineState::detached; },"queued close did not drain bounded Driver retirement");
    check(f.disposals && f.enters == f.leaves,"normal close skipped actual retirement or invented TURN");
}
void uncertain_close() {
    Fixture f(false); f.query_trap = true; f.app->drawable_cells(56,16); f.tick();
    check(f.app->native_state() == NativeEngineState::process_exit_required && f.app->closed(),"uncertain provider unwind did not retain process terminal state");
    const auto calls = f.calls, enters = f.enters, leaves = f.leaves, disposals = f.disposals;
    const std::weak_ptr<int> captures = f.wake_capture;
    f.app->shutdown(); f.app->handle(gui::CloseEvent{}); f.app->retry_presentation(); f.app->qualify([&]{ ++f.calls; });
    for (unsigned i = 0; i != 4; ++i) f.tick();
    f.app.reset(); f.wake_capture.reset();
    check(f.calls == calls && f.enters == enters && f.leaves == leaves && f.disposals == disposals && enters == leaves+1,
        "uncertain close/qualification/destruction fabricated cleanup, LEAVE, ACK or new provider export");
    check(!captures.expired(),"uncertain destruction dropped complete retained composition scheduling captures");
}
void owner_agreement() {
    Fixture f(false); EngineOwnerConfiguration config; config.document_profile = profile();
    auto different = std::make_shared<EngineOwner>(package(),config); const auto before = f.calls;
    bool rejected = false; try { NativeEngineDocumentComposition wrong(f.adapter,different,*f.driver); }
    catch (const std::invalid_argument&) { rejected = true; }
    check(rejected && f.calls == before && !different->configured(),"different/unconfigured Owner admitted facade or entered provider");
}
void observation_poll() {
    Fixture f;
    check(!f.driver->deadline() && f.app->deadline().has_value(),"idle live document has no observation deadline");
    const auto due = *f.app->deadline();
    check(due > f.now && due <= f.now+250ms,"initial observation deadline is not a bounded future quarter second");
    const auto queries = f.queries, forms = f.forms, acks = f.acks;
    f.native_value = "Silent native property update"; ++f.revision;
    f.now = due-1ms; f.app->tick(f.now);
    check(f.queries == queries,"readonly polling entered the provider before its deadline");
    f.now = due; f.app->tick(f.now);
    f.until([&] { return f.queries == queries+1 && f.app->body_ready() &&
        exported_text(f.app->view()).find(f.native_value) != std::string::npos; },
        "silent property update never reached the same terminal presenter");
    check(f.forms == forms && f.acks == acks && !f.owner->native_effect(),
        "readonly observation submitted a native form, metadata ACK or effect");
    const auto next = f.app->deadline();
    check(next && *next > f.now && *next <= f.now+250ms,"completed observation did not keep a future bounded deadline");
    f.now = *next; f.app->tick(f.now);
    f.until([&] { return f.queries == queries+2 && f.app->body_ready(); },"unchanged live state stopped periodic observation");
    check(f.forms == forms && f.acks == acks,"unchanged observation acquired action authority");
}
void observation_modal() {
    Fixture f; f.open();
    f.adapter.terminal.input("Unsaved modal draft");
    check(button_enabled(f.app->view(),"Apply"),"modal observation fixture has no real unsaved input");
    const auto draft = editor(f.app->view()).state.text;
    const auto queries = f.queries, forms = f.forms, acks = f.acks;
    for (unsigned n = 0; n != 3; ++n) {
        const auto due = f.app->deadline(); check(due.has_value(),"live modal lost its future observation deadline");
        f.now = *due; f.app->tick(f.now);
        check(f.app->deadline() && *f.app->deadline() > f.now,"deferred modal observation left an expired busy-loop deadline");
    }
    check(f.queries == queries && f.forms == forms && f.acks == acks && f.app->modal_open() &&
        editor(f.app->view()).state.text == draft && button_enabled(f.app->view(),"Apply"),
        "readonly polling entered native code, revoked a lease or damaged the saved draft during its modal");
    const auto entered = f.calls;
    f.app->handle(gui::WidgetEvent{button(f.app->view(),"Cancel"),gui::Activate{}});
    check(f.calls == entered,"Cancel callback entered native work while a poll was deferred");
    f.until([&] { return !f.app->modal_open() && f.app->body_ready(); },"deferred poll blocked ordinary modal cancellation/refresh");
    const auto settled = f.queries;
    for (unsigned n = 0; n != 4; ++n) f.tick();
    check(f.queries == settled,"coalesced modal polling burst into extra native queries after Cancel");
}
void observation_lifecycle() {
    Fixture f;
    f.app->foreground(false);
    check(f.app->deadline() == f.driver->deadline(),"background observation kept an independent deadline");
    f.tick(); const auto queries = f.queries;
    f.now += 1s; f.app->tick(f.now);
    check(f.queries == queries,"background elapsed time started an observation");
    f.app->foreground(true); f.tick();
    f.until([&] { return f.app->body_ready(); },"foreground restoration lost its mandatory fresh publication");
    check(f.app->deadline() && *f.app->deadline() > f.now && *f.app->deadline() <= f.now+250ms,
        "foreground restoration did not arm a fresh future observation deadline");
    f.app->drawable_cells(0,0);
    check(f.app->deadline() == f.driver->deadline(),"invalid cells retained observation scheduling");
    f.tick(); const auto hidden_queries = f.queries;
    f.now += 1s; f.app->tick(f.now);
    check(f.queries == hidden_queries,"invalid cells admitted automatic native observation");
    f.app->drawable_cells(45,12); f.tick();
    f.until([&] { return f.app->body_ready(); },"restored cells did not establish a fresh document");
    check(f.app->deadline() && *f.app->deadline() > f.now,"restored cells retained an expired observation deadline");
    f.app->shutdown();
    check(f.app->deadline() == f.driver->deadline(),"queued close retained automatic observation work");
    f.until([&] { return f.driver->state() == NativeEngineState::detached; },"observation scheduling obstructed ordinary close");
}
void observation_deadline() {
    Fixture f;
    const auto observation = f.app->deadline(); check(observation.has_value(),"observation deadline missing before native timer");
    f.arm_timer = true; f.driver->request_advance(); f.tick();
    const auto native = f.driver->deadline();
    check(native && *native < *observation && f.app->deadline() == native,
        "observation scheduling hid the earlier actual native timer");
    const auto queries = f.queries;
    f.now = *native; f.app->tick(f.now);
    check(f.queries == queries && f.app->deadline() == observation,
        "native timer progress submitted an early query or lost the later observation deadline");
    f.now = Clock::time_point::max()-100ms; f.app->tick(f.now);
    check(f.app->deadline() == f.driver->deadline(),"observation clock exhaustion wrapped or retained an expired deadline");
    const auto at_limit = f.queries; f.app->tick(f.now);
    check(f.queries == at_limit,"exhausted observation clock selected a repeated immediate query");
}
void observation_retry() {
    Fixture f;
    const auto queries = f.queries, forms = f.forms, acks = f.acks;
    f.native_value = "Observed before publication failure"; ++f.revision;
    f.adapter.during_present = [&] {
        if (f.queries > queries && !f.adapter.failures) f.adapter.fail_after = true;
    };
    f.now = *f.app->deadline();
    for (unsigned n = 0; n != 8 && !f.adapter.failures; ++n) {
        try { f.app->tick(f.now); } catch (const std::runtime_error&) {}
        f.now += 1ms;
    }
    f.adapter.during_present = {};
    check(f.adapter.failures == 1 && f.queries == queries+1 && f.app->presentation_pending(),
        "poll fixture did not retain an actual failed query publication");
    const auto attempted = f.adapter.attempts.back();
    const auto same_publication = [&](const gui::Snapshot& actual) {
        const auto& a = body_list(actual); const auto& b = body_list(attempted);
        return actual.revision == attempted.revision && actual.client_size == attempted.client_size &&
            actual.modal_root == attempted.modal_root && actual.active_page == attempted.active_page &&
            actual.pages == attempted.pages && exported_text(actual) == exported_text(attempted) &&
            a.spec == b.spec && a.state.records == b.state.records && a.state.bounds == b.state.bounds &&
            a.state.visible == b.state.visible && a.state.enabled == b.state.enabled && a.state.selected == b.state.selected;
    };
    f.native_value = "Changed while publication awaits retry"; ++f.revision;
    for (unsigned n = 0; n != 3; ++n) {
        const auto due = f.app->deadline(); check(due.has_value(),"publication debt lost periodic observation scheduling");
        f.now = *due;
        // A normal owner tick may retry the exact saved publication. Keep the
        // injected failure armed so this loop exercises retained debt only.
        f.adapter.fail_after = true;
        try { f.app->tick(f.now); } catch (const std::runtime_error&) {}
        check(f.queries == queries+1 && f.app->presentation_pending(),
            "deferred observation bypassed failed publication or repeated a native query");
        check(same_publication(f.adapter.attempts.back()),"polling changed the failed publication's revision, content or input authority");
        check(f.app->deadline() && *f.app->deadline() > f.now,"publication retry retained a past polling deadline");
    }
    f.adapter.fail_after = false;
    const auto entered = f.calls; const auto retry_index = f.adapter.attempts.size();
    f.app->retry_presentation();
    check(f.calls == entered,"explicit poll publication retry entered native code");
    check(f.adapter.attempts.size() > retry_index && same_publication(f.adapter.attempts[retry_index]),
        "first explicit retry changed saved publication content or input authority");
    // After that exact retry commits, the same serialized local turn may
    // publish a successor waiting frame for the coalesced observation. Its
    // native query still waits for a later Driver turn.
    f.until([&] { return f.queries == queries+2 && f.app->body_ready() &&
        exported_text(f.app->view()).find(f.native_value) != std::string::npos; },
        "coalesced observation after exact retry failed to capture current native state");
    for (unsigned n = 0; n != 4; ++n) f.tick();
    check(f.queries == queries+2 && f.forms == forms && f.acks == acks,
        "pending polling hints burst or replayed an action after presentation recovery");
}
// Independent kind4/4083 composition fixture. The old pixel fixture and its
// scenarios above deliberately retain their original setup and assertions.
namespace actions = foundation::appended::engine_document_actions;
using namespace foundation::ui;
struct ActionsWire : Wire {
    void publication(EngineDocumentTarget value, std::uint64_t revision, std::string_view native_value,
            std::uint64_t focused, std::uint64_t selected, std::uint64_t lease,
            const std::optional<DocumentSelection>& selection) {
        id(value); version(value,revision); integer(0,1);
        integer(revision,8); integer(focused,8); integer(0,4); integer(0,4);
        integer(9,4); integer(0,4); integer(2,4); integer(selection.has_value(),1);
        if (selection) {
            for (const auto point : {selection->anchor,selection->focus}) {
                integer(point.node,8); integer(1,1); integer(point.utf16_offset,4);
            }
            integer(0,1);
        }
        node(1,0,1,4,"body");
        node(10,1,1,0,"input",{},"First field",native_value);
        node(20,1,1,2,"select",{},"Native single choice");
        node(101,20,1,0,"option",{},"First choice");
        node(202,20,1,0,"option",{},"Second choice");
        node(70,1,1,1,"a",{},"Ordinary project link",{},"guide.html");
        node(71,70,2,0,{},"Ordinary project link");
        node(80,1,1,1,"p"); node(81,80,2,0,{},"Paired \xf0\x9f\x98\x80 observation");
        integer(10,8); integer(0,1); integer(4|32|(focused == 10 ? 8 : 0),1);
        integer(1|16,4); integer(1,1); integer(lease != 0,1);
        text("text"); text("First field");
        if (lease) { version(value,revision); integer(10,8); integer(lease,8); }
        text(native_value); text(native_value); integer(1,1);
        integer(native_value.size(),4); integer(native_value.size(),4); integer(0,1);
        integer(20,8); integer(4,1); integer(4|32|(focused == 20 ? 8 : 0),1);
        integer(0,4); integer(3,1); integer(0,1); text("select-one"); text("Native single choice");
        integer(2,1); integer(2,4);
        integer(101,8); integer(selected == 101,1); text("First choice");
        integer(202,8); integer(selected == 202,1); text("Second choice");
    }
};
struct ActionsFixture;
ActionsFixture* active_actions{};
struct ActionsFixture {
    static constexpr std::uint64_t instance = UINT64_C(0x8000000000000044);
    std::shared_ptr<EngineOwner> owner;
    NativeEngineDriver* driver{};
    std::unique_ptr<NativeEngineDocumentComposition> app;
    RecordingAdapter adapter;
    BibEngineHostV1 host{};
    BibEngineDocumentV1 current{instance,UINT64_C(0x8000000000000001),0};
    Clock::time_point now{1000s};
    std::uint64_t revision{13}, focused{10}, selected{101}, last_sequence{}, last_action{}, last_ack{};
    std::uint32_t retained_family{};
    unsigned calls{}, starts{}, advances{}, queries{}, bodies{}, forms{}, body_acks{}, form_acks{}, enters{}, leaves{}, posts{};
    bool in_callback{}, inside{}, synchronous_post{}, post_selection_refused{}, fail_after_action{};
    std::string native_value{"Native initial field"};
    std::optional<DocumentSelection> selection;
    std::vector<DocumentActionV1Request> body_requests;
    std::vector<std::uint32_t> operations;
    std::vector<std::uint64_t> sequences;

    explicit ActionsFixture(bool show = true) : adapter([this](const gui::Event& event) {
        in_callback = true;
        try { if (app) app->handle(event); } catch (...) { in_callback = false; throw; }
        in_callback = false;
    }) {
        check(!active_actions && !active,"one native composition fixture per fresh process"); active_actions = this;
        auto config = document_actions_fixture::configuration();
        owner = std::make_shared<EngineOwner>(package(),std::move(config));
        const auto& facts = owner->document_actions_profile();
        check(actions::document_actions_profile_valid(facts) && owner->document_actions_enabled() &&
            !owner->document_profile().enabled && !owner->editor_profile().enabled,
            "4083 fixture inferred a legacy document/editor profile");
        NativeEngineExpectation expected;
        expected.document_actions_profile = facts; expected.target_system = facts.target_system;
        expected.target_processor = facts.target_processor; expected.pointer_bits = facts.pointer_bits;
        expected.contract_header_sha256 = facts.contract_sha256;
        expected.build_identity_sha256 = facts.build_sha256; expected.source_recipe_sha256 = facts.source_recipe_sha256;
        NativeEngineOptions options;
        options.limits.maximum_command_bytes = BIB_ENGINE_EDITOR_MAX_WIRE_BYTES;
        options.limits.maximum_reply_bytes = actions::kReplyCapacity; options.maximum_steps_per_tick = 8;
        BibEngineProviderV1 table{}; table.size = sizeof(table); table.abi_major = 1; table.abi_minor = 1;
        auto& build = table.build; build.size = sizeof(build); build.layout_revision = BIB_ENGINE_LAYOUT_V1;
        build.target_system = facts.target_system; build.target_processor = facts.target_processor; build.pointer_bits = facts.pointer_bits;
        build.lifetime = facts.lifetime; build.maximum_starts = 1;
        build.fixed_viewport_width = 800; build.fixed_viewport_height = 600; build.capabilities = facts.provider_capabilities;
        std::copy(facts.contract_sha256.begin(),facts.contract_sha256.end(),build.contract_header_sha256);
        std::copy(facts.build_sha256.begin(),facts.build_sha256.end(),build.build_identity_sha256);
        std::copy(facts.source_recipe_sha256.begin(),facts.source_recipe_sha256.end(),build.source_recipe_sha256);
        table.limits = options.limits; table.start = start; table.advance = advance; table.current_document = current_document;
        table.query = query; table.command = command; table.deliver_services = deliver;
        table.collect_service_ack = collect; table.dispose_retired_service_document = dispose;
        driver = &NativeEngineDriver::bind_once(NativeEngineProvider::checked(table,expected),owner,options,
            {this,[](void* p) noexcept { auto& f = *static_cast<ActionsFixture*>(p); if (f.app) f.app->wake(); }});
        driver->start_once(now); driver->tick(now += 1ms);
        check(starts == 1 && owner->configured() && driver->state() == NativeEngineState::ready && !owner->has_module(),
            "4083 mock did not start the actual VM-free Owner/Driver");
        const auto before = calls;
        app = std::make_unique<NativeEngineDocumentComposition>(adapter,owner,*driver,[this] {
            ++posts;
            if (synchronous_post && app) {
                post_selection_refused = !app->queue_selection({{81,7},{81,9}});
                app->tick(now);
            }
        });
        check(calls == before && !queries && !app->body_ready() && !app->view().revision,
            "4083 facade constructor entered provider or invented drawable cells");
        adapter.terminal.terminal_size(56,17);
        if (show) { app->drawable_cells(56,16); until([&] { return app->body_ready(); },"4083 initial paired terminal publication failed"); }
    }
    ~ActionsFixture() { app.reset(); active_actions = nullptr; }
    void tick() { app->tick(now += 1ms); }
    template<class Done> void until(Done done, const char* reason) {
        for (unsigned i = 0; i != 32 && !done(); ++i) tick();
        if (!done()) std::cerr << "actions diagnostic: state=" << static_cast<unsigned>(driver->state())
            << " body=" << app->body_ready() << " modal=" << app->modal_open() << " pending=" << app->presentation_pending()
            << " q=" << queries << " body10=" << bodies << " form6=" << forms << " ack11=" << body_acks
            << " ack7=" << form_acks << " error=" << app->last_error() << '\n';
        check(done(),reason);
    }
    template<class Function> std::int32_t turn(Function fn) {
        ++calls;
        check(!in_callback && !inside && !owner->callback_depth(),"4083 provider entered from Adapter/native callback");
        inside = true; check(host.enter_engine(host.context) == FOUNDATION_APPENDED_SERVICE_OK,"4083 Host TURN refused"); ++enters;
        const auto status = fn(); host.leave_engine(host.context); ++leaves; inside = false; return status;
    }
    EngineDocumentTarget target() const {
        const auto id = owner->identity(); return {id.worker_epoch,id.application_instance,id.document_sequence,id.service_generation};
    }
    void begin() {
        BibEngineResourceEpochV1 epoch{}; epoch.size = sizeof(epoch);
        check(host.begin_resource_epoch(host.context,&current,&epoch) == BIB_ENGINE_OK && epoch.resource_epoch,
            "4083 mock resource epoch refused");
        current.service_generation = host.begin_service_document(host.context,&current);
        check(current.service_generation && owner->identity().service_generation == current.service_generation,
            "4083 mock lost actual Owner document identity");
    }
    static std::int32_t BIB_ENGINE_CALL start(const BibEngineHostV1* value, const BibEngineStartV1* config,
            BibEngineStartResultV1* result) {
        auto& f = *active_actions; ++f.starts; f.host = *value;
        check(config && config->raster_output == 1 && config->required_capabilities == actions::kProviderCapabilities &&
            config->limits.maximum_command_bytes == BIB_ENGINE_EDITOR_MAX_WIRE_BYTES &&
            config->limits.maximum_reply_bytes == actions::kReplyCapacity,"START lost explicit4083/1MiB facts");
        const auto status = f.turn([&] { f.begin(); return BIB_ENGINE_OK; });
        *result = {sizeof(*result),BIB_ENGINE_START_READY,instance}; return status;
    }
    static std::int32_t BIB_ENGINE_CALL advance(const BibEngineAdvanceV1*) {
        auto& f = *active_actions; check(!f.retained_family,"advance overtook the global retained action"); ++f.advances;
        return f.turn([] { return BIB_ENGINE_OK; });
    }
    static std::int32_t BIB_ENGINE_CALL current_document(std::uint64_t application, BibEngineDocumentV1* value) {
        auto& f = *active_actions;
        return f.turn([&] { check(application == instance,"4083 current application changed"); *value = f.current; return BIB_ENGINE_OK; });
    }
    static void copy(BibEngineReplyBufferV1* buffer, const Bytes& bytes) {
        check(buffer && buffer->bytes && bytes.size() <= buffer->capacity,"4083 canonical reply exceeded owned buffer");
        std::copy(bytes.begin(),bytes.end(),buffer->bytes);
    }
    void sequence(std::uint64_t value, std::uint32_t operation) {
        check(value > last_sequence,"4083 query/form/body/ACK sequence reset or replayed");
        last_sequence = value; operations.push_back(operation); sequences.push_back(value);
    }
    Bytes publication(std::uint64_t lease = 0) const {
        ActionsWire wire; wire.publication(target(),revision,native_value,focused,selected,lease,selection); return wire.bytes;
    }
    static std::int32_t BIB_ENGINE_CALL query(const BibEngineQueryV1* request, BibEngineReplyBufferV1* buffer,
            BibEngineQueryResultV1* result) {
        auto& f = *active_actions;
        check(!f.retained_family && request && request->kind == BIB_ENGINE_QUERY_DOCUMENT_FORMS_V2 &&
            request->payload.length == 48 && request->expected.application_instance == f.current.application_instance &&
            request->expected.document_sequence == f.current.document_sequence &&
            request->expected.service_generation == f.current.service_generation &&
            std::equal(document::kSchema.begin(),document::kSchema.end(),request->schema_sha256),
            "4083 query overtook retained action or changed paired catalog/target");
        const Span raw(request->payload.data,request->payload.length);
        EngineDocumentDispatch dispatched; dispatched.work.target = f.target();
        dispatched.work.request_sequence = get(raw,32,8); dispatched.work.payload.assign(raw.begin(),raw.end());
        f.sequence(dispatched.work.request_sequence,request->kind); ++f.queries;
        return f.turn([&] {
            Wire wire; wire.header(4,dispatched); const auto record = f.publication();
            wire.bytes.insert(wire.bytes.end(),record.begin(),record.end()); copy(buffer,wire.bytes);
            *result = {sizeof(*result),static_cast<std::uint32_t>(wire.bytes.size()),request->expected,f.revision}; return BIB_ENGINE_OK;
        });
    }
    static std::int32_t BIB_ENGINE_CALL command(const BibEngineCommandV1* request, BibEngineReplyBufferV1* buffer,
            BibEngineCommandResultV1* result) {
        auto& f = *active_actions;
        check(request && request->request_sequence && !f.in_callback &&
            request->expected.application_instance == f.current.application_instance &&
            request->expected.document_sequence == f.current.document_sequence &&
            request->expected.service_generation == f.current.service_generation,"4083 command entered Adapter callback or changed native target");
        f.sequence(request->request_sequence,request->operation);
        const Span raw(request->payload.data,request->payload.length);
        const bool body_ack = request->operation == BIB_ENGINE_COMMAND_ACK_DOCUMENT_ACTION_V1;
        if (body_ack || request->operation == BIB_ENGINE_COMMAND_ACK_FORM_ACTION_V2) {
            ++f.calls;
            const auto& schema = body_ack ? actions::kAckSchema : document::kAckSchema;
            check(!f.inside && !f.owner->callback_depth() && raw.size() == 8 && buffer->capacity == 16 &&
                f.retained_family == (body_ack ? 10u : 6u) && get(raw,0,8) == f.last_action &&
                request->expected.application_instance == f.current.application_instance &&
                request->expected.document_sequence == f.current.document_sequence &&
                request->expected.service_generation == f.current.service_generation &&
                request->request_sequence > f.last_action && std::equal(schema.begin(),schema.end(),request->schema_sha256),
                "4083 metadata ACK changed family/original tuple/schema/sequence or acquired TURN");
            if (body_ack) ++f.body_acks; else ++f.form_acks;
            const auto bytes = ack_reply(f.last_action); copy(buffer,bytes); f.last_ack = f.last_action; f.retained_family = 0;
            *result = {sizeof(*result),1,request->request_sequence,static_cast<std::uint32_t>(bytes.size()),0}; return BIB_ENGINE_OK;
        }
        check(!f.retained_family,"another action overtook global form/body debt");
        if (request->operation == BIB_ENGINE_COMMAND_DOCUMENT_ACTION_V1) {
            check(raw.size() == 128 && buffer->capacity == actions::kReplyCapacity &&
                std::equal(actions::kSchema.begin(),actions::kSchema.end(),request->schema_sha256),"command10 changed exact catalog facts");
            const auto decoded = decode_document_action_v1_request(raw);
            check(decoded.key.worker_epoch == f.owner->identity().worker_epoch && decoded.key.application_instance == instance &&
                decoded.key.document_sequence == f.current.document_sequence && decoded.key.service_generation == f.current.service_generation &&
                decoded.key.request_sequence == request->request_sequence &&
                decoded.expected == DocumentVersion{instance,f.current.service_generation,f.revision},
                "command10 lost displayed version or full owned correlation");
            f.body_requests.push_back(decoded); ++f.bodies;
            return f.turn([&] {
                if (const auto* focus = std::get_if<DocumentActionV1Focus>(&decoded.action)) f.focused = focus->node;
                if (const auto* select = std::get_if<DocumentActionV1Select>(&decoded.action))
                    f.selection = DocumentSelection{{select->selection.anchor.node,select->selection.anchor.offset},
                        {select->selection.focus.node,select->selection.focus.offset}};
                if (const auto* choice = std::get_if<DocumentActionV1ChooseSingleOption>(&decoded.action)) {
                    check(choice->node == 20 && choice->option == 202,"chooser lost actual control/option IDs");
                    f.focused = 20; f.selected = 101; // Actual change handler retained the original option.
                }
                ++f.revision; f.last_action = request->request_sequence; f.retained_family = 10;
                const auto bytes = encode_document_action_v1_reply(decoded,DocumentActionV1Result::completed,
                    DocumentActionV1Code::ok,true,f.publication()); copy(buffer,bytes);
                *result = {sizeof(*result),1,request->request_sequence,static_cast<std::uint32_t>(bytes.size()),1};
                if (std::exchange(f.fail_after_action,false)) f.adapter.fail_after = true;
                return BIB_ENGINE_OK;
            });
        }
        check(request->operation == BIB_ENGINE_COMMAND_FORM_ACTION_V2 && raw.size() >= 81 && buffer->capacity == actions::kReplyCapacity &&
            std::equal(document::kSchema.begin(),document::kSchema.end(),request->schema_sha256),
            "4083 facade changed form catalog or sent an unexpected native operation"); ++f.forms;
        return f.turn([&] {
            if (get(raw,48,1) == 1) {
                check(raw.size() >= 102 && get(raw,98,4) == raw.size()-102,"4083 form Apply lost copied text");
                f.native_value.assign(raw.begin()+102,raw.end());
            }
            f.focused = 10; ++f.revision; f.last_action = request->request_sequence; f.retained_family = 6;
            EngineDocumentDispatch dispatched; dispatched.work.target = f.target(); dispatched.work.request_sequence = request->request_sequence;
            Wire wire; wire.header(5,dispatched); wire.integer(0,1); wire.integer(0,1); wire.integer(1,1); wire.integer(1,1);
            const auto record = f.publication(f.revision+87); wire.bytes.insert(wire.bytes.end(),record.begin(),record.end()); copy(buffer,wire.bytes);
            *result = {sizeof(*result),1,request->request_sequence,static_cast<std::uint32_t>(wire.bytes.size()),1};
            if (std::exchange(f.fail_after_action,false)) f.adapter.fail_after = true;
            return BIB_ENGINE_OK;
        });
    }
    static std::int32_t BIB_ENGINE_CALL deliver(const BibEngineDocumentV1*, const BibEngineBytesV1*) {
        throw std::runtime_error("4083 facade fixture unexpectedly delivered a native service");
    }
    static std::uint32_t BIB_ENGINE_CALL collect(const BibEngineDocumentV1*) { return FOUNDATION_APPENDED_SERVICE_UNAVAILABLE; }
    static std::int32_t BIB_ENGINE_CALL dispose(std::uint64_t, std::uint64_t) { return BIB_ENGINE_OK; }
    void event(gui::Input input) {
        const auto before = calls; app->handle(gui::WidgetEvent{body_list(app->view()).spec.key,std::move(input)});
        check(calls == before,"4083 body Adapter event entered provider before owner tick");
    }
    void activate(std::string_view label) { const auto id = row(app->view(),label); event(gui::ActivateRecord{id}); }
    void settle_body(unsigned expected) {
        until([&] { return bodies == expected && body_acks == expected && app->body_ready(); },"4083 body ACK/fresh query did not restore publication");
        check(last_ack == last_action && !retained_family && enters == leaves && !owner->callback_depth(),
            "4083 body retirement lost balanced exact native debt");
    }
    void assert_debt_blocks(bool body) {
        check(retained_family == (body ? 10u : 6u) && !owner->reserve_document_sequence(),
            "retained action did not block the global ordinary reservation");
        EngineDocumentWork next; next.target = target(); next.request_sequence = last_sequence+1;
        next.required_reply_capacity = actions::kReplyCapacity;
        if (body) {
            next.kind = EngineDocumentWorkKind::form_action; next.operation = BIB_ENGINE_COMMAND_FORM_ACTION_V2;
            next.schema_sha256 = document::kSchema;
            EngineDocumentDispatch dispatched; dispatched.work = next;
            Wire wire; wire.header(2,dispatched); wire.integer(0,1); wire.version(next.target,revision); wire.integer(10,8);
            next.payload = std::move(wire.bytes);
        } else {
            next.kind = EngineDocumentWorkKind::body_action; next.operation = BIB_ENGINE_COMMAND_DOCUMENT_ACTION_V1;
            next.schema_sha256 = actions::kSchema;
            const auto encoded = encode_document_action_v1({next.target.worker_epoch,next.target.application_instance,
                next.target.document_sequence,next.target.service_generation,next.request_sequence,1},
                {instance,current.service_generation,revision},DocumentActionV1Focus{70});
            next.payload.assign(encoded.bytes.begin(),encoded.bytes.end());
        }
        check(valid_engine_document_work_shape(next),"opposite-family probe was not a valid catalog-shaped request");
        const auto denied = owner->stage_document_work(std::move(next));
        check(denied.code == EngineDocumentAdmissionCode::busy && !denied.ticket,
            "retained action admitted the other action family");
    }
};

void actions_start_progress() {
    ActionsFixture f(false);
    f.app->drawable_cells(0,0); f.tick(); check(!f.queries,"4083 presenter invented minimum drawable viewport");
    f.app->drawable_cells(56,16); f.until([&] { return f.app->body_ready(); },"4083 valid cells failed to publish");
    check(f.app->view().client_size == gui::Size{448,256} && f.owner == f.driver->owner() && !f.app->next_service(),
        "4083 facade substituted viewport/Owner/services");
    const auto link = row(f.app->view(),"Ordinary project link");
    f.event(gui::SelectRecord{link}); f.tick();
    check(f.bodies == 1 && !f.body_acks && !f.app->body_ready() &&
        std::get<DocumentActionV1Focus>(f.body_requests.back().action).node == 70 && f.body_requests.back().key.nested_request_id,
        "4083 focus did not stage exact command10 before later ACK11");
    f.settle_body(1);
    const auto queries = f.queries;
    f.activate("Ordinary project link"); f.tick();
    check(f.bodies == 2 && f.body_acks == 1 && std::get<DocumentActionV1Activate>(f.body_requests.back().action).node == 70,
        "4083 link activation did not use typed body action");
    f.settle_body(2); check(f.queries == queries+1,"4083 action readback replaced or duplicated mandatory fresh query");
    const auto before = f.calls; f.activate("Native single choice");
    check(f.app->modal_open() && f.calls == before,"opening local single chooser entered native code");
    const auto choice = std::find_if(f.app->view().widgets.begin(),f.app->view().widgets.end(),[](const auto& widget) {
        return widget.spec.kind == gui::Kind::choice && widget.spec.key.id.ends_with("/single-options");
    });
    check(choice != f.app->view().widgets.end() && choice->state.selected == "101","4083 chooser lost actual initial option");
    f.app->handle(gui::WidgetEvent{choice->spec.key,gui::ChooseOption{"202"}});
    check(f.calls == before,"local chooser draft entered provider");
    f.app->handle(gui::WidgetEvent{button(f.app->view(),"Apply"),gui::Activate{}}); f.tick();
    check(f.bodies == 3 && f.body_acks == 2 && !f.body_requests.back().key.nested_request_id &&
        std::get<DocumentActionV1ChooseSingleOption>(f.body_requests.back().action) == DocumentActionV1ChooseSingleOption{20,202},
        "single chooser lost its distinct zero-nested typed command10");
    f.settle_body(3); f.activate("Native single choice");
    const auto actual = std::find_if(f.app->view().widgets.begin(),f.app->view().widgets.end(),[](const auto& widget) {
        return widget.spec.kind == gui::Kind::choice && widget.spec.key.id.ends_with("/single-options");
    });
    check(actual != f.app->view().widgets.end() && actual->state.selected == "101",
        "4083 chooser displayed requested option instead of actual native fresh readback");
}
void actions_selection() {
    ActionsFixture f;
    const DocumentSelection selected{{81,7},{81,9}};
    bool publication_refused = false, qualify_refused = false;
    f.adapter.during_present = [&] { publication_refused = !f.app->queue_selection(selected); f.app->tick(f.now); };
    f.app->foreground(false); f.tick(); f.adapter.during_present = {};
    check(publication_refused && !f.app->queue_selection(selected),"4083 selection crossed publication/background gate");
    f.app->foreground(true); f.until([&] { return f.app->body_ready(); },"4083 foreground selection fixture did not restore");
    f.app->qualify([&] { qualify_refused = !f.app->queue_selection(selected); });
    check(qualify_refused,"4083 selection crossed qualify reentry guard");
    f.app->drawable_cells(0,0); check(!f.app->queue_selection(selected),"invalid drawable cells retained DOM selection authority");
    f.tick(); f.app->drawable_cells(56,16); f.until([&] { return f.app->body_ready(); },"4083 restored cells failed selection authority");
    bool foreign_refused = false;
    std::thread foreign([&] { try { (void)f.app->queue_selection(selected); } catch (const std::logic_error&) { foreign_refused = true; } }); foreign.join();
    check(foreign_refused && !f.bodies && !f.body_acks,"4083 selection accepted foreign owner or entered effect during gate checks");
    check(!f.app->queue_selection({{81,8},{81,9}}),"4083 selection accepted a UTF16 surrogate interior");
    f.tick(); const auto staged = f.calls, posts = f.posts; f.synchronous_post = true;
    auto queued = selected;
    check(f.app->queue_selection(queued) && f.calls == staged && !f.bodies && f.posts > posts && f.post_selection_refused,
        "host DOM selection or synchronous wake entered Driver before later owner tick");
    queued.anchor = {71,1}; queued.focus = {71,4};
    f.synchronous_post = false; f.tick();
    check(f.bodies == 1 && !f.body_acks && !f.app->body_ready(),"4083 selection lost later-turn action/ACK staging");
    const auto& action = std::get<DocumentActionV1Select>(f.body_requests.back().action);
    check(action.selection.anchor == DocumentNativePoint{81,7,DocumentNativeOffsetKind::text_utf16} &&
        action.selection.focus == DocumentNativePoint{81,9,DocumentNativeOffsetKind::text_utf16},
        "4083 host DOM selection changed explicit native UTF16 endpoints");
    f.settle_body(1);
    check(f.selection == selected && f.queries >= 2,"4083 selection failed actual readback plus distinct fresh paired query");
    const auto closed = f.calls; f.app->shutdown();
    check(!f.app->queue_selection(selected) && f.calls == closed,"queued close admitted selection or entered native cleanup");
}
void actions_ack_barriers() {
    ActionsFixture f;
    f.fail_after_action = true; f.activate("Ordinary project link");
    try { f.tick(); } catch (const std::runtime_error&) {}
    check(f.adapter.failures == 1 && f.bodies == 1 && !f.body_acks && f.app->presentation_pending(),
        "body barrier fixture did not retain actual failed publication");
    f.assert_debt_blocks(true);
    const auto queries = f.queries, advances = f.advances, forms = f.forms, calls = f.calls;
    f.driver->request_advance(); f.app->wake();
    f.app->qualify([&] { check(f.calls == calls,"qualify entered native work through body publication debt"); });
    check(f.calls == calls && f.queries == queries && f.advances == advances && f.forms == forms,
        "local body retry crossed native/global family barrier");
    f.tick();
    check(f.body_acks == 1 && f.last_ack == f.last_action,"later bounded body turn failed exact metadata retirement");
    f.until([&] { return f.app->body_ready(); },"body ACK/fresh query failed before family switch");
    f.activate("First field"); f.tick();
    check(f.forms == 1 && !f.form_acks && f.app->modal_open(),"4083 form6 did not share real presenter/transport");
    f.assert_debt_blocks(false);
    const auto body_count = f.bodies, query_count = f.queries, advance_count = f.advances;
    const auto entered = f.calls;
    check(!f.app->queue_selection({{81,7},{81,9}}) && f.calls == entered,"form modal admitted a body action through global debt");
    f.tick();
    check(f.form_acks == 1 && f.bodies == body_count && f.queries == query_count && f.advances == advance_count &&
        f.last_ack == f.last_action && !f.retained_family && f.enters == f.leaves,
        "form ACK7 acquired TURN or let body/query/advance overtake global debt");
    check(std::find(f.operations.begin(),f.operations.end(),10) != f.operations.end() &&
        std::find(f.operations.begin(),f.operations.end(),11) != f.operations.end() &&
        std::find(f.operations.begin(),f.operations.end(),6) != f.operations.end() &&
        std::find(f.operations.begin(),f.operations.end(),7) != f.operations.end(),"4083 family transition omitted actual commands10/11/6/7");
}
void actions_publication_retry() {
    ActionsFixture f; const auto queries = f.queries;
    f.fail_after_action = true; f.activate("Ordinary project link");
    try { f.tick(); } catch (const std::runtime_error&) {}
    check(f.adapter.failures == 1 && f.bodies == 1 && !f.body_acks && !f.app->body_ready() && f.app->presentation_pending(),
        "command10 reply did not remain retained after actual publication failure");
    const auto failed = f.adapter.attempts.back(); const auto calls = f.calls;
    const auto retry = f.adapter.attempts.size();
    f.app->retry_presentation();
    check(f.calls == calls && f.bodies == 1 && !f.body_acks && f.queries == queries && f.adapter.attempts.size() > retry &&
        f.adapter.attempts[retry].revision == failed.revision && exported_text(f.adapter.attempts[retry]) == exported_text(failed) &&
        f.adapter.attempts[retry].modal_root == failed.modal_root && f.adapter.attempts[retry].client_size == failed.client_size,
        "body publication retry changed saved frame, entered native code or replayed command10");
    check(!f.app->body_ready(),"successful action readback retry manufactured a query receipt");
    f.tick();
    check(f.body_acks == 1 && f.queries == queries && !f.app->body_ready(),"body ACK11 entered early or skipped fresh query barrier");
    f.until([&] { return f.app->body_ready(); },"actual fresh query failed after retained body retry/ACK11");
    check(f.bodies == 1 && f.body_acks == 1 && f.queries == queries+1 && f.enters == f.leaves && !f.owner->callback_depth(),
        "body retry replayed an action/ACK or duplicated fresh observation");
}
void actions_legacy_selection_refused() {
    Fixture f; const auto calls = f.calls, queries = f.queries, forms = f.forms, acks = f.acks;
    check(!f.owner->document_actions_enabled() && !f.app->queue_selection({{71,1},{71,4}}) &&
        f.calls == calls && f.queries == queries && f.forms == forms && f.acks == acks && f.app->body_ready(),
        "legacy pixel1795 borrowed host DOM selection authority from4083");
}
} // namespace
int main(int argc, char** argv) {
    try {
        check(argc == 2,"one fresh-process scenario required"); const std::string_view scenario(argv[1]);
        if (scenario == "query-apply-ack") query_apply_ack();
        else if (scenario == "actual-cells") actual_cells();
        else if (scenario == "callback-barriers") callback_barriers();
        else if (scenario == "presentation-retry") presentation_retry();
        else if (scenario == "callback-facts") callback_facts();
        else if (scenario == "callback-close") callback_close();
        else if (scenario == "close-held-result") close_held_result();
        else if (scenario == "registry-gate") registry_gate();
        else if (scenario == "navigation-close") navigation_close();
        else if (scenario == "uncertain-close") uncertain_close();
        else if (scenario == "owner-agreement") owner_agreement();
        else if (scenario == "observation-poll") observation_poll();
        else if (scenario == "observation-modal") observation_modal();
        else if (scenario == "observation-lifecycle") observation_lifecycle();
        else if (scenario == "observation-deadline") observation_deadline();
        else if (scenario == "observation-retry") observation_retry();
        else if (scenario == "actions-start-progress") actions_start_progress();
        else if (scenario == "actions-selection") actions_selection();
        else if (scenario == "actions-ack-barriers") actions_ack_barriers();
        else if (scenario == "actions-publication-retry") actions_publication_retry();
        else if (scenario == "actions-legacy-selection-refused") actions_legacy_selection_refused();
        else throw std::runtime_error("unknown composition scenario");
        std::cout << "PASS " << scenario << ": " << assertions << " assertions; real TerminalAdapter/Owner/Driver/App, mock C table, no engine/SDK/VM\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << "FAIL: " << error.what() << '\n'; return 1; }
}
