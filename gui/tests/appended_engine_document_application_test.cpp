#include "shared/appended_engine_document_application.hpp"
#include "shared/appended_engine_owner.hpp"
#include "shared/appended_engine_abi.h"
#include "shared/document_action_v1_codec.hpp"
#include "shared/engine_document_actions_profile.hpp"

#include <gui/terminal.hpp>
#include <algorithm>
#include <array>
#include <cstdint>
#include <functional>
#include <iostream>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

// A copied endpoint fixture, not an engine/provider implementation or runtime
// qualification. Replies are independently assembled from the NDV2 wire format;
// the application, terminal, Owner, mailbox and native Registry are the real ones.
namespace {
using namespace foundation::appended;
using foundation::ui::AppendedEngineDocumentApplication;
namespace document = foundation::appended::engine_document;
using Span = std::span<const std::uint8_t>;
std::size_t assertions{}, cases{};
void check(bool value, const char* reason) {
    ++assertions;
    if (!value) throw std::runtime_error(reason);
}
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
EngineDocumentTarget target(EngineIdentity id) {
    return {id.worker_epoch,id.application_instance,id.document_sequence,id.service_generation};
}
EngineIdentity identity(EngineDocumentTarget id) {
    return {id.worker_epoch,id.application_instance,id.document_sequence,id.service_generation};
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
                     std::string_view native_value, std::uint64_t lease = 0,
                     std::string_view control_type = "text") {
        const bool button=control_type=="button" || control_type=="reset" || control_type=="submit";
        id(value); version(value,revision); integer(0,1); // complete paired publication
        integer(revision,8); integer(10,8); integer(0,4); integer(0,4);
        integer(6,4); integer(0,4); integer(1,4); integer(0,1);
        node(1,0,1,3,"body");
        node(10,1,1,0,"input",{},"First field",button ? std::string_view{} : native_value);
        node(70,1,1,1,"a",{},"Ordinary project link",{},"guide.html");
        node(71,70,2,0,{},"Ordinary project link");
        node(80,1,1,1,"p"); node(81,80,2,0,{},"Paired body observation");
        integer(10,8); integer(button ? 7 : 0,1); integer(4|8|32,1); // actual kind, focusable/focused/complete
        integer(button ? 0 : 1|16,4); integer(button ? 0 : 1,1); integer(lease != 0,1);
        text(control_type); text("First field");
        if (lease) { version(value,revision); integer(10,8); integer(lease,8); }
        if (!button) {
            text(native_value); text(native_value); integer(1,1);
            integer(native_value.size(),4); integer(native_value.size(),4); integer(0,1);
        }
    }
};
Bytes query_reply(const EngineDocumentDispatch& request, std::uint64_t revision, std::string_view value = {},
                  std::string_view control_type = "text") {
    Wire wire; wire.header(4,request); wire.publication(request.work.target,revision,value,0,control_type); return wire.bytes;
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
    result.target_system = BIB_ENGINE_TARGET_LINUX; result.target_processor = BIB_ENGINE_CPU_X86_64;
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
engine_document_actions::EngineDocumentActionsProfileFacts action_profile() {
    namespace actions=engine_document_actions;
    const auto old=profile(); actions::EngineDocumentActionsProfileFacts result;
    result.enabled=true; result.kind=actions::ProfileKind::document_actions; result.name=actions::kProfileName;
    result.provider_abi_major=old.provider_abi_major; result.provider_abi_minor=old.provider_abi_minor;
    result.host_abi_major=old.host_abi_major; result.host_abi_minor=old.host_abi_minor;
    result.target_system=old.target_system; result.target_processor=old.target_processor; result.pointer_bits=old.pointer_bits;
    result.lifetime=old.lifetime; result.maximum_starts=old.maximum_starts;
    result.viewport_width=old.viewport_width; result.viewport_height=old.viewport_height;
    result.provider_capabilities=actions::kProviderCapabilities; result.surface_capabilities=actions::kSurfaceCapabilities;
    result.surface_protocol_version=2; result.editor_protocol_version=BIB_ENGINE_EDITOR_PROTOCOL_VERSION;
    result.base_header_sha256=old.base_header_sha256; result.document_header_sha256=old.extension_header_sha256;
    result.document_contract_sha256=old.contract_sha256; result.document_catalog_sha256=old.catalog_sha256;
    result.physical_catalog_sha256=document::kPhysicalCatalogSha256;
    result.editor_header_sha256=engine_editor::kHeaderSha256; result.editor_contract_sha256=engine_editor::kContractSha256;
    result.editor_catalog_sha256=engine_editor::kCatalogSha256; result.editor_schema_sha256=engine_editor::kSchema;
    result.actions_header_sha256=actions::kHeaderSha256; result.contract_sha256=actions::kContractSha256;
    result.catalog_sha256=actions::kCatalogSha256; result.schema_sha256=actions::kSchema; result.ack_schema_sha256=actions::kAckSchema;
    // Synthetic component facts only; these pins do not identify an engine.
    result.build_sha256[0]=0x71; result.source_recipe_sha256[0]=0x93;
    result.queries=actions::kQueries; result.commands=actions::kCommands;
    result.query_count=static_cast<unsigned>(result.queries.size()); result.command_count=static_cast<unsigned>(result.commands.size());
    check(actions::document_actions_profile_valid(result),"fixture failed explicit4083 profile validation");
    return result;
}
struct Reply {
    EngineIdentity id;
    std::uint64_t transfer{};
    std::uint32_t control{}, service{};
    Bytes bytes;
    Span body() const { return Span(bytes).subspan(80); }
};
Reply call(EngineOwner& owner, std::uint32_t operation, EngineIdentity id, Span body = {}, std::uint64_t transfer = 0) {
    Bytes input(72+body.size()); std::copy_n("FKB1",4,input.begin());
    put(input,4,1,2); put(input,6,operation,2); put(input,8,input.size(),4);
    put(input,16,id.worker_epoch,8); put(input,24,id.application_instance,8);
    put(input,32,id.document_sequence,8); put(input,40,id.service_generation,8); put(input,48,transfer,8);
    put(input,64,body.size(),4); std::copy(body.begin(),body.end(),input.begin()+72);
    Bytes output(80+FOUNDATION_ENGINE_DOCUMENT_MAX_RESULT_BODY_BYTES);
    const auto count = owner.dispatch(operation,input,output);
    check(count >= 80 && static_cast<std::size_t>(count) <= output.size(),"real Owner did not return a complete copied receipt");
    output.resize(static_cast<std::size_t>(count));
    check(get(output,6,2) == (operation|0x8000) && get(output,8,4) == output.size() &&
        get(output,64,4) == output.size()-72,"real Owner copied framing changed");
    return {{get(output,16,8),get(output,24,8),get(output,32,8),get(output,40,8)},get(output,48,8),
        static_cast<std::uint32_t>(get(output,72,4)),static_cast<std::uint32_t>(get(output,76,4)),std::move(output)};
}
void ok(const Reply& reply, const char* reason = "real Owner rejected expected operation") {
    check(reply.control == FOUNDATION_ENGINE_OK && reply.service == 0,reason);
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
    explicit RecordingAdapter(gui::EventSink sink) : terminal(std::move(sink)) {}
    void present(gui::Snapshot snapshot) override {
        attempts.push_back(snapshot);
        if (during_present) during_present();
        if (std::exchange(fail_before,false)) throw std::runtime_error("injected before actual install");
        terminal.present(std::move(snapshot));
        if (std::exchange(fail_after,false)) throw std::runtime_error("injected after actual install");
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

struct Fixture {
    static constexpr std::string_view service_name = "org.example.document-application.native";
    EngineIdentity id{17,UINT64_C(0x8000000000000023),0,0};
    std::shared_ptr<EngineOwner> owner;
    RecordingAdapter adapter;
    std::unique_ptr<AppendedEngineDocumentApplication> app;
    std::uint64_t revision{13}, held{}, route{};
    unsigned callbacks{}, provider_claims{}, effects{};
    bool in_callback{}, hold_on_entry{};
    std::string native_value, forbidden, control_type{"text"};
    explicit Fixture(bool initialize = true, bool native = false, bool actions = false)
        : adapter([this](const gui::Event& event) {
            ++callbacks; in_callback = true;
            try { if (app) app->handle(event); } catch (...) { in_callback = false; throw; }
            in_callback = false;
        }) {
        EngineOwnerConfiguration configuration;
        configuration.worker_epoch = id.worker_epoch; configuration.application_instance = id.application_instance;
        if (actions) configuration.document_actions_profile=action_profile();
        else configuration.document_profile = profile();
        configuration.abandon_closed_document_outcomes = true;
        if (native) configuration.native_services.push_back({{std::string(service_name),1,0,SchemaId{7},4},
            [this](std::uint32_t operation, Span input, std::span<std::uint8_t> output) -> ServiceReply {
                const auto effect = owner->native_effect();
                check(operation == 1 && input.size() == 4 && output.size() >= 4 && effect && effect->entered,
                    "real Registry handler lost its exact native effect/owner turn");
                check(!in_callback && !app->presentation_pending(),"real Registry handler entered during GUI callback or publication debt");
                redacted(adapter.terminal.snapshot(),forbidden);
                check(forbidden.empty() || terminal_text(adapter.terminal).find(forbidden) == std::string::npos,
                    "real terminal cells retained old draft at native handler entry");
                if (hold_on_entry) { check(owner->hold_native_effect(effect->ticket),"real native UI hold refused"); held = effect->ticket; }
                ++effects; std::copy(input.begin(),input.end(),output.begin()); return {ServiceStatus::ok,4};
            }});
        owner = std::make_shared<EngineOwner>(package(),std::move(configuration));
        ok(call(*owner,FOUNDATION_ENGINE_CONFIGURE,id)); id.document_sequence = UINT64_C(0x8000000000000001);
        const auto begun = call(*owner,FOUNDATION_ENGINE_BEGIN_DOCUMENT,id); ok(begun); id = begun.id;
        adapter.terminal.terminal_size(56,17);
        app = std::make_unique<AppendedEngineDocumentApplication>(adapter,owner,foundation::ui::DocumentViewport{56,16});
        if (initialize) {
            const auto query = take(); check(query.work.kind == EngineDocumentWorkKind::snapshot_query,"initial native work was not paired query");
            check(query.work.request_sequence == 1 && get(query.work.payload,40,8) == 1,
                "initial Owner reservation and nested Forms query did not start at their actual first identities");
            finish_query(query); app->tick(); check(app->body_ready() && !app->presentation_pending(),"initial paired query did not arm committed body");
        }
        callbacks = 0;
    }
    std::optional<EngineDocumentDispatch> peek() {
        const auto reply = call(*owner,FOUNDATION_ENGINE_PEEK_DOCUMENT_WORK,owner->identity());
        if (reply.control == FOUNDATION_ENGINE_EMPTY ||
            (reply.control == FOUNDATION_ENGINE_CLOSED && app && app->closed())) return {};
        ok(reply); check(reply.transfer && reply.body().size() >= 56,"real document mailbox omitted owned work");
        EngineDocumentDispatch result; result.transfer = reply.transfer; auto& work = result.work;
        work.target = target(reply.id); work.kind = static_cast<EngineDocumentWorkKind>(get(reply.body(),0,4));
        work.operation = static_cast<std::uint32_t>(get(reply.body(),4,4)); work.request_sequence = get(reply.body(),8,8);
        std::copy_n(reply.body().begin()+16,32,work.schema_sha256.begin());
        work.required_reply_capacity = static_cast<std::uint32_t>(get(reply.body(),48,4));
        check(get(reply.body(),52,4) == reply.body().size()-56,"copied mailbox changed exact payload length");
        work.payload.assign(reply.body().begin()+56,reply.body().end());
        check(work.target.worker_epoch && work.target.application_instance && work.target.document_sequence && work.target.service_generation,
            "application staged an incomplete four-field target");
        return result;
    }
    EngineDocumentDispatch take() {
        for (unsigned turn = 0; turn != 5; ++turn) {
            if (const auto result = peek()) return *result;
            app->tick();
        }
        throw std::runtime_error("application did not stage expected real mailbox work");
    }
    void claim(const EngineDocumentDispatch& request, bool native_turn = true) {
        check(!in_callback && !owner->callback_depth(),"provider fixture entered from callback");
        Bytes body(16); put(body,0,static_cast<unsigned>(request.work.kind),4); put(body,8,request.work.request_sequence,8);
        ok(call(*owner,FOUNDATION_ENGINE_BEGIN_DOCUMENT_WORK,identity(request.work.target),body,request.transfer)); ++provider_claims;
        if (native_turn && request.work.kind != EngineDocumentWorkKind::action_ack && request.work.kind != EngineDocumentWorkKind::body_action_ack) {
            ok(call(*owner,FOUNDATION_ENGINE_TURN_ENTER,identity(request.work.target),{},request.transfer));
            ok(call(*owner,FOUNDATION_ENGINE_TURN_LEAVE,identity(request.work.target),{},request.transfer));
        }
    }
    void result(const EngineDocumentDispatch& request, Span raw, std::int32_t status = 0,
                unsigned disposition = 0, bool handled = false, std::uint64_t semantic_revision = 0) {
        Bytes body(40+raw.size()); put(body,0,static_cast<unsigned>(request.work.kind),4);
        put(body,8,request.work.request_sequence,8); put(body,16,static_cast<std::uint32_t>(status),4);
        put(body,20,disposition,4); put(body,24,raw.size(),4); put(body,28,handled,4); put(body,32,semantic_revision,8);
        std::copy(raw.begin(),raw.end(),body.begin()+40);
        ok(call(*owner,FOUNDATION_ENGINE_DOCUMENT_WORK_RESULT,identity(request.work.target),body,request.transfer));
    }
    void finish_query(const EngineDocumentDispatch& request) {
        check(request.work.kind == EngineDocumentWorkKind::snapshot_query && request.work.operation == 3 &&
            request.work.schema_sha256 == document::kSchema && request.work.required_reply_capacity == document::kReplyCapacity,
            "application lost exact document query catalog facts");
        check(request.work.payload.size() == 48 && get(request.work.payload,0,4) == 0x3256444e &&
            get(request.work.payload,8,8) == request.work.target.application_instance &&
            get(request.work.payload,16,8) == request.work.target.service_generation &&
            get(request.work.payload,24,8) == request.work.target.document_sequence &&
            get(request.work.payload,32,8) == request.work.request_sequence && get(request.work.payload,40,8),
            "query remapped owned sequence, native tuple or nested token");
        claim(request); result(request,query_reply(request,revision,native_value,control_type),0,0,false,revision);
    }
    void finish_form(const EngineDocumentDispatch& request, unsigned outcome = 0, unsigned code = 0) {
        check(request.work.kind == EngineDocumentWorkKind::form_action && request.work.operation == 6 &&
            request.work.schema_sha256 == document::kSchema && request.work.required_reply_capacity == document::kReplyCapacity,
            "application did not stage exact command6 catalog facts");
        check(request.work.payload.size() >= 81 && get(request.work.payload,0,4) == 0x3256444e &&
            get(request.work.payload,4,4) == 0x00020002 &&
            get(request.work.payload,8,8) == request.work.target.application_instance &&
            get(request.work.payload,16,8) == request.work.target.service_generation &&
            get(request.work.payload,24,8) == request.work.target.document_sequence &&
            get(request.work.payload,32,8) == request.work.request_sequence && !get(request.work.payload,40,8),
            "command6 header changed exact native identity, owned sequence or reserved bytes");
        claim(request); ++revision;
        result(request,form_reply(request,outcome,code,outcome == 0 ? std::optional{revision} : std::nullopt,
            native_value,outcome == 0 ? revision+87 : 0),0,1,true);
    }
    EngineDocumentDispatch finish_ack(const EngineDocumentDispatch& action, unsigned code = 0) {
        const auto ack = take();
        check(ack.work.kind == EngineDocumentWorkKind::action_ack && ack.work.operation == 7 &&
            ack.work.target == action.work.target && ack.work.request_sequence > action.work.request_sequence &&
            ack.work.payload == encode_u64(action.work.request_sequence) && ack.work.schema_sha256 == document::kAckSchema &&
            ack.work.required_reply_capacity == 16,"checked action ACK lost exact original target, sequence or catalog");
        claim(ack,false); result(ack,ack_reply(action.work.request_sequence,code),0,1,false);
        app->tick(); return ack;
    }
    foundation::ui::DocumentActionV1Request body_request(const EngineDocumentDispatch& request) {
        check(request.work.kind==EngineDocumentWorkKind::body_action && request.work.operation==10 &&
            request.work.schema_sha256==engine_document_actions::kSchema && request.work.required_reply_capacity==1048576,
            "body action lost its independent exact catalog facts");
        auto decoded=foundation::ui::decode_document_action_v1_request(request.work.payload);
        check(decoded.key.worker_epoch==request.work.target.worker_epoch && decoded.key.application_instance==request.work.target.application_instance &&
            decoded.key.document_sequence==request.work.target.document_sequence && decoded.key.service_generation==request.work.target.service_generation &&
            decoded.key.request_sequence==request.work.request_sequence && decoded.expected==foundation::ui::DocumentVersion{id.application_instance,id.service_generation,revision},
            "body action remapped exact six-field/displayed correlation");
        return decoded;
    }
    void finish_body(const EngineDocumentDispatch& request, foundation::ui::DocumentActionV1Result outcome=foundation::ui::DocumentActionV1Result::completed,
                     foundation::ui::DocumentActionV1Code code=foundation::ui::DocumentActionV1Code::ok) {
        const auto decoded=body_request(request); Wire publication;
        if (outcome==foundation::ui::DocumentActionV1Result::completed) {
            ++revision; publication.publication(request.work.target,revision,native_value,0,control_type);
        }
        const bool entered=outcome!=foundation::ui::DocumentActionV1Result::rejected;
        const auto bytes=foundation::ui::encode_document_action_v1_reply(decoded,outcome,code,entered,publication.bytes);
        claim(request); result(request,bytes,0,1,entered);
    }
    EngineDocumentDispatch finish_body_ack(const EngineDocumentDispatch& action) {
        const auto ack=take();
        check(ack.work.kind==EngineDocumentWorkKind::body_action_ack && ack.work.operation==11 &&
            ack.work.target==action.work.target && ack.work.request_sequence>action.work.request_sequence &&
            ack.work.payload==encode_u64(action.work.request_sequence) && ack.work.schema_sha256==engine_document_actions::kAckSchema &&
            ack.work.required_reply_capacity==16,"body ACK11 lost original target/family/sequence");
        claim(ack,false); result(ack,ack_reply(action.work.request_sequence),0,1,false); app->tick(); return ack;
    }
    void refresh() { const auto query = take(); finish_query(query); app->tick(); }
    void activate(std::string_view name) {
        const auto& snapshot = app->view(); const auto key = body_list(snapshot).spec.key; const auto record = row(snapshot,name);
        app->handle(gui::WidgetEvent{key,gui::ActivateRecord{record}});
    }
    void click(std::string_view name) { app->handle(gui::WidgetEvent{button(app->view(),name),gui::Activate{}}); }
    EngineDocumentDispatch begin() {
        activate("First field"); check(!peek(),"GUI callback staged a native Begin before serialized tick");
        const auto request = take();
        check(request.work.payload.size() == 81 && get(request.work.payload,48,1) == 0 &&
            get(request.work.payload,49,8) == id.application_instance && get(request.work.payload,57,8) == id.service_generation &&
            get(request.work.payload,65,8) == revision && get(request.work.payload,73,8) == 10,
            "Begin did not preserve exact displayed native version/control");
        return request;
    }
    void open() {
        const auto request = begin(); finish_form(request); finish_ack(request); refresh();
        check(app->modal_open() && !app->body_ready(),"native accepted Begin did not retain one local modal");
        check(adapter.terminal.focus(editor(app->view()).spec.key),"real terminal refused native form editor focus");
    }
    EngineDocumentDispatch apply(std::string text) {
        adapter.terminal.input("\x01\x1b[200~"+text+"\x1b[201~");
        check(editor(app->view()).state.text == text && !peek(),"real terminal draft editing entered native mailbox");
        adapter.terminal.input("\x13"); check(!peek(),"Apply callback staged native work synchronously"); return take();
    }
    Bytes service_request(std::uint64_t sequence, std::uint64_t handle, std::uint32_t operation, Span raw) {
        Envelope envelope; envelope.generation = id.service_generation; envelope.sequence = sequence;
        envelope.interface_handle = handle; envelope.operation = operation; Bytes bytes;
        check(encode_envelope(envelope,raw,bytes) == CodecStatus::ok,"native service fixture encoding failed"); return bytes;
    }
    void submit_service(std::uint64_t sequence, std::uint64_t handle, std::uint32_t operation, Span raw) {
        ok(call(*owner,FOUNDATION_ENGINE_SUBMIT,id,service_request(sequence,handle,operation,raw)));
        const auto pending = call(*owner,FOUNDATION_ENGINE_PUMP_ONE,id);
        check(pending.control == FOUNDATION_ENGINE_CONFLICT && owner->native_effect() && !owner->native_effect()->entered,
            "actual Registry bypassed pending safe-publication gate");
    }
    Bytes collect_service(std::uint64_t sequence) {
        const auto delivered = call(*owner,FOUNDATION_ENGINE_PEEK_DELIVERY,id); ok(delivered);
        Envelope envelope; Span raw;
        check(decode_envelope(delivered.body(),envelope,raw) == CodecStatus::ok && envelope.sequence == sequence &&
            envelope.service_status == 0,"real Registry did not retain exact service reply");
        Bytes result(raw.begin(),raw.end()); const auto accepted = encode_u32(FOUNDATION_ENGINE_ACCEPTED);
        ok(call(*owner,FOUNDATION_ENGINE_DELIVERY_RESULT,delivered.id,accepted,delivered.transfer));
        const auto staged = call(*owner,FOUNDATION_ENGINE_STAGE_ACK,id,encode_u64(sequence));
        check(staged.control == 0 && staged.service == static_cast<unsigned>(ServiceStatus::unavailable),"real Registry ACK was not staged");
        ok(call(*owner,FOUNDATION_ENGINE_PUMP_ONE,id)); const auto receipt = call(*owner,FOUNDATION_ENGINE_PEEK_ACK_RECEIPT,id); ok(receipt);
        check(receipt.body().size() == 12 && get(receipt.body(),0,8) == sequence && get(receipt.body(),8,4) == 0,
            "real Registry ACK receipt lost exact sequence/actual status");
        ok(call(*owner,FOUNDATION_ENGINE_ACK_RECEIPT_RESULT,receipt.id,accepted,receipt.transfer)); return result;
    }
    void discover() {
        const auto major = encode_u32(1), minor = encode_u32(0);
        const Span name{reinterpret_cast<const std::uint8_t*>(service_name.data()),service_name.size()};
        const std::array<FieldView,4> fields{{{1,FieldType::utf8,true,name},{2,FieldType::u32,true,major},
            {3,FieldType::u32,true,minor},{4,FieldType::u32,true,minor}}}; Bytes query;
        check(encode_record(fields,query) == CodecStatus::ok,"real Registry discovery record encoding failed");
        submit_service(1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER,query); app->tick();
        ok(call(*owner,FOUNDATION_ENGINE_PUMP_ONE,id)); const auto raw = collect_service(1);
        std::vector<FieldView> descriptor;
        check(decode_record(raw,descriptor) == CodecStatus::ok && descriptor.size() == 6 &&
            read_u64(descriptor.front(),route) && route,"actual Registry failed opaque service discovery");
        refresh();
    }
};

void initial_pair_and_actual_terminal_apply() {
    Fixture fixture;
    check(fixture.owner->document_enabled() && !fixture.owner->input_enabled() && !fixture.owner->has_module(),
        "document application invented physical input or a VM owner");
    check(exported_text(fixture.app->view()).find("Paired body observation") != std::string::npos &&
        terminal_text(fixture.adapter.terminal).find("First field") != std::string::npos,
        "independent NDV2 body/form pair was not observable through actual terminal cells");
    check(!fixture.app->next_service() && !fixture.app->complete_service({}),"application simulated Registry-owned native services");
    fixture.open(); const auto expected_capture = fixture.revision;
    const std::string text = "Owned terminal draft"; const auto request = fixture.apply(text);
    check(request.work.payload.size() == 102+text.size() && get(request.work.payload,48,1) == 1 &&
        get(request.work.payload,49,8) == fixture.id.application_instance && get(request.work.payload,57,8) == fixture.id.service_generation &&
        get(request.work.payload,65,8) == expected_capture && get(request.work.payload,73,8) == 10 &&
        get(request.work.payload,81,8) == expected_capture+87 && get(request.work.payload,89,4) == 0 &&
        get(request.work.payload,93,4) == 0 && get(request.work.payload,97,1) == 0 &&
        get(request.work.payload,98,4) == text.size() &&
        std::string(request.work.payload.begin()+102,request.work.payload.end()) == text,
        "command6 failed exact owned lease/range/UTF8 replacement golden fixture");
    const auto before = fixture.provider_claims; fixture.native_value = text; fixture.finish_form(request);
    fixture.finish_ack(request); fixture.refresh();
    check(fixture.provider_claims == before+3 && fixture.app->modal_open() && !fixture.app->presentation_pending() &&
        editor(fixture.app->view()).state.text == text,"consumed Apply was redelivered/replayed or lost readback");
}

void local_publication_failure(bool after_install) {
    Fixture fixture; fixture.open(); const auto request = fixture.apply("Published exactly once");
    fixture.native_value = "Published exactly once"; fixture.finish_form(request);
    const auto original_claims = fixture.provider_claims;
    const auto prior_revision = fixture.adapter.terminal.snapshot().revision;
    fixture.adapter.fail_before = !after_install; fixture.adapter.fail_after = after_install;
    try { fixture.app->tick(); } catch (const std::runtime_error&) {}
    check(fixture.app->presentation_pending() && !fixture.peek(),"form completion ACK preceded successful actual publication");
    const auto failed = fixture.adapter.attempts.back();
    check(failed.revision > prior_revision && (!after_install || fixture.adapter.terminal.snapshot().revision == failed.revision),
        "fault fixture did not exercise requested actual install boundary");
    try { fixture.app->retry_presentation(); } catch (...) { throw std::runtime_error("exact actual publication retry failed"); }
    check(fixture.adapter.attempts.back().revision == failed.revision &&
        fixture.adapter.terminal.snapshot().revision == failed.revision && fixture.provider_claims == original_claims &&
        exported_text(fixture.adapter.attempts.back()) == exported_text(failed),
        "retry changed owned publication origin or repeated native action");
    fixture.finish_ack(request); fixture.app->tick();
    const auto following = fixture.take();
    check(following.work.kind == EngineDocumentWorkKind::snapshot_query,"form publication retry replayed the replacement");
}

void cancel_after_delivered_apply_keeps_original_cleanup() {
    Fixture fixture; fixture.open(); const auto apply = fixture.apply("Delivered before Cancel");
    fixture.click("Cancel");
    const auto retained = fixture.peek();
    check(!fixture.app->body_ready() && retained && retained->transfer == apply.transfer,
        "Cancel forgot the actual already-delivered native request");
    fixture.native_value = "Actual native result after Cancel"; fixture.finish_form(apply);
    fixture.finish_ack(apply); fixture.refresh();
    check(!fixture.app->modal_open() && fixture.app->body_ready() && !fixture.peek(),
        "Cancel after delivered Apply replayed an edit or resumed before exact original ACK/fresh paired query");
}

void failed_query_retains_one_completion() {
    Fixture fixture(false); const auto query = fixture.take(); fixture.finish_query(query);
    fixture.adapter.fail_after = true;
    try { fixture.app->tick(); } catch (const std::runtime_error&) {}
    check(fixture.app->presentation_pending() && !fixture.app->body_ready() && !fixture.peek(),
        "query armed input or issued fresh work before actual publication acknowledgement");
    const auto failed_revision = fixture.adapter.attempts.back().revision; const auto claims = fixture.provider_claims;
    fixture.app->retry_presentation(); fixture.app->tick();
    check(fixture.app->body_ready() && !fixture.app->presentation_pending() && fixture.provider_claims == claims &&
        fixture.adapter.terminal.snapshot().revision >= failed_revision && !fixture.peek(),
        "retained query redelivery duplicated native capture or failed committed body");
}

void semantic_rejection_and_unknown_are_not_acceptance() {
    for (const unsigned outcome : {1u,2u}) {
        Fixture fixture; fixture.open(); const auto request = fixture.apply("Uncertain local draft");
        fixture.finish_form(request,outcome,outcome == 1 ? 4 : 8); fixture.finish_ack(request);
        check(fixture.app->modal_open() && editor(fixture.app->view()).state.text.empty() &&
            !button_enabled(fixture.app->view(),"Apply") &&
            exported_text(fixture.adapter.terminal.snapshot()).find("Uncertain local draft") == std::string::npos,
            "consumed transport forged native semantic acceptance or exposed unobserved native kind");
        const auto following = fixture.take();
        check(following.work.kind == EngineDocumentWorkKind::snapshot_query,"semantic uncertainty replayed command6 instead of requesting paired observation");
        fixture.finish_query(following); fixture.app->tick();
        check(editor(fixture.app->view()).state.text == "Uncertain local draft" && !button_enabled(fixture.app->view(),"Apply"),
            "fresh compatible paired observation lost saved draft or rearmed a failed native lease");
    }
    Fixture rejected; const auto begin = rejected.begin(); rejected.claim(begin,false);
    rejected.result(begin,{},-5,0); rejected.app->tick();
    check(!rejected.app->body_ready(),"known pre-entry rejection armed old body before fresh paired state");
    const auto query = rejected.take();
    check(query.work.kind == EngineDocumentWorkKind::snapshot_query,"known unconsumed rejection fabricated native action ACK");
    rejected.finish_query(query); rejected.app->tick();
    check(!rejected.app->modal_open() && rejected.app->body_ready(),"known pre-entry rejection fabricated accepted Begin");
}

void endpoint_unknown_stops_without_ack_or_replay() {
    Fixture fixture; fixture.open(); const auto request = fixture.apply("Never replay this action"); fixture.claim(request);
    const std::string forged = "OPAQUE_UNKNOWN_MUST_NOT_BE_ACCEPTED";
    const auto raw = form_reply(request,0,0,std::optional{fixture.revision+1},forged,fixture.revision+88);
    fixture.result(request,raw,0,2,true); const auto claims = fixture.provider_claims;
    fixture.app->tick(); fixture.app->tick();
    check(fixture.app->closed() && fixture.adapter.terminal.closed() && !fixture.app->body_ready() &&
        fixture.provider_claims == claims && !fixture.peek(),
        "endpoint uncertainty resumed input, issued cleanup ACK or replayed native action");
    check(exported_text(fixture.app->view()).find(forged) == std::string::npos &&
        exported_text(fixture.adapter.terminal.snapshot()).find(forged) == std::string::npos,
        "unknown transport payload was decoded or presented as native semantic acceptance");
}

void unsupported_body_action_never_reaches_owner() {
    Fixture fixture; fixture.activate("Ordinary project link");
    check(!fixture.peek(),"body callback staged native work"); fixture.app->tick();
    const auto next = fixture.take();
    check(next.work.kind == EngineDocumentWorkKind::snapshot_query && next.work.operation == 3 && next.work.request_sequence > 2,
        "unsupported body intent became command6 or failed to burn only its held sequence");
    fixture.finish_query(next); fixture.app->tick();
    check(fixture.app->body_ready(),"known unexecuted body intent did not recover fresh paired state");
}

void navigation_preserves_original_action_cleanup() {
    Fixture fixture; fixture.open(); const auto request = fixture.apply("Old document owned draft"); fixture.finish_form(request);
    const auto previous = fixture.id; auto successor = previous; ++successor.document_sequence; successor.service_generation = 0;
    const auto begun = call(*fixture.owner,FOUNDATION_ENGINE_BEGIN_DOCUMENT,successor); ok(begun); fixture.id = begun.id;
    check(fixture.id.application_instance == previous.application_instance && fixture.id.worker_epoch == previous.worker_epoch &&
        fixture.id.document_sequence != previous.document_sequence && fixture.id.service_generation != previous.service_generation,
        "navigation fixture did not replace actual document/service identities");
    fixture.app->tick(); const auto ack = fixture.finish_ack(request);
    check(ack.work.target == target(previous) && fixture.owner->identity() == fixture.id,
        "navigation rebased old action ACK authority onto successor document");
    const auto query = fixture.take();
    check(query.work.target == target(fixture.id) && query.work.request_sequence > ack.work.request_sequence,
        "same application failed fresh four-field successor capture after old cleanup");
    fixture.finish_query(query); fixture.app->tick();
    check(!fixture.app->closed(),"old action cleanup closed valid successor application");
}

void background_keeps_delivered_action_and_requires_fresh_restore_query() {
    Fixture fixture; fixture.open(); const auto action = fixture.apply("Draft retained across background");
    fixture.app->foreground(false); const auto pending = fixture.peek();
    check(pending && pending->transfer == action.transfer,"foreground callback dropped or replaced handed native action");
    fixture.native_value = "Known native background result"; fixture.finish_form(action); fixture.finish_ack(action);
    check(!fixture.peek() && !fixture.app->body_ready(),"background action settlement staged premature ordinary work");
    redacted(fixture.adapter.terminal.snapshot(),"Draft retained across background");
    fixture.app->foreground(true); const auto fresh = fixture.take();
    check(fresh.work.kind == EngineDocumentWorkKind::snapshot_query && fresh.work.target == action.work.target,
        "foreground restoration rebased target or skipped fresh paired capture");
    fixture.finish_query(fresh); fixture.app->tick();
    check(fixture.app->modal_open() && !button_enabled(fixture.app->view(),"Apply"),
        "background restoration rearmed a prior native Apply lease");
}

void native_effect_requires_actual_safe_publication_and_fresh_query(bool after_install) {
    Fixture fixture(true,true); fixture.discover(); fixture.open();
    fixture.forbidden = "PRIVATE_OLD_MODAL_DRAFT_853";
    fixture.adapter.terminal.input(fixture.forbidden);
    check(editor(fixture.app->view()).state.text == fixture.forbidden,"native gate fixture did not retain a real terminal draft");
    const auto old = fixture.app->view(); const auto old_epoch = fixture.app->input_epoch();
    fixture.hold_on_entry = true; fixture.submit_service(2,fixture.route,1,encode_u32(41));
    check(!fixture.owner->acknowledge_native_effect(fixture.owner->native_effect()->ticket),
        "ordinary native ACK bypassed document publication gate");
    fixture.adapter.measurements.clear(); fixture.adapter.fail_before = !after_install; fixture.adapter.fail_after = after_install;
    try { fixture.app->tick(); } catch (const std::runtime_error&) {}
    const auto safe = fixture.adapter.attempts.back(); redacted(safe,fixture.forbidden);
    check(fixture.app->presentation_pending() && !fixture.effects &&
        call(*fixture.owner,FOUNDATION_ENGINE_PUMP_ONE,fixture.id).control == FOUNDATION_ENGINE_CONFLICT,
        "throwing actual safe publication granted Registry handler authority");
    check(safe.widgets.size() == old.widgets.size(),"redaction removed live widget keys");
    for (const auto& value : old.widgets) {
        const auto* retained = gui::find_widget(safe,value.spec.key);
        check(retained && retained->spec == value.spec,"redaction replaced a live WidgetSpec/key lifetime");
    }
    for (const auto& measured : fixture.adapter.measurements)
        check(measured.empty() || measured == "M",
            "redaction forwarded old draft/body strings to actual text measurement");
    fixture.adapter.terminal.input("SHOULD_NOT_EDIT\x13");
    check(!fixture.peek() && fixture.app->input_epoch() != old_epoch,"safe publication left old body/modal input armed");
    fixture.app->retry_presentation(); fixture.app->tick();
    check(fixture.adapter.attempts.back().revision == safe.revision && !fixture.app->presentation_pending(),
        "native safe retry mutated attempted actual publication revision");
    redacted(fixture.app->view(),fixture.forbidden); ok(call(*fixture.owner,FOUNDATION_ENGINE_PUMP_ONE,fixture.id));
    check(fixture.effects == 1 && fixture.held && fixture.owner->native_effect(),"real native handler/hold was skipped or repeated");
    check(fixture.collect_service(2) == encode_u32(41),"real native effect reply changed");
    fixture.app->tick(); redacted(fixture.adapter.terminal.snapshot(),fixture.forbidden);
    check(!fixture.peek(),"native UI hold staged observation before trusted closure");
    check(fixture.owner->release_native_effect(fixture.held),"trusted native UI closure failed");
    const auto query = fixture.take();
    check(query.work.kind == EngineDocumentWorkKind::snapshot_query,"effect release did not obtain a fresh paired query");
    redacted(fixture.app->view(),fixture.forbidden); const auto safe_revision = fixture.adapter.terminal.snapshot().revision;
    fixture.finish_query(query); fixture.app->tick();
    check(fixture.adapter.terminal.snapshot().revision > safe_revision && !fixture.app->presentation_pending() &&
        fixture.app->modal_open() && !button_enabled(fixture.app->view(),"Apply") && fixture.effects == 1,
        "effect release rearmed input without fresh paired receipt/new actual revision or rearmed old Apply");
    check(exported_text(fixture.app->view()).find(fixture.forbidden) != std::string::npos,
        "safe-frame key preservation prevented same-generation draft recovery");
}

void second_effect_requires_a_new_safe_publication_origin() {
    Fixture fixture(true,true); fixture.discover();
    fixture.submit_service(2,fixture.route,1,encode_u32(51)); fixture.app->tick();
    const auto first_safe = fixture.adapter.terminal.snapshot();
    ok(call(*fixture.owner,FOUNDATION_ENGINE_PUMP_ONE,fixture.id)); (void)fixture.collect_service(2);
    // No intervening foreground restoration: Forms remains suspended while a
    // different real Registry effect now needs its own successful safe revision.
    fixture.submit_service(3,fixture.route,1,encode_u32(52)); fixture.adapter.fail_before = true;
    try { fixture.app->tick(); } catch (const std::runtime_error&) {}
    const auto second_safe = fixture.adapter.attempts.back();
    redacted(second_safe,"Paired body observation");
    check(second_safe.revision > first_safe.revision && fixture.app->presentation_pending() && fixture.effects == 1 &&
        call(*fixture.owner,FOUNDATION_ENGINE_PUMP_ONE,fixture.id).control == FOUNDATION_ENGINE_CONFLICT,
        "second effect reused old safe revision or entered after failed new publication");
    fixture.app->retry_presentation(); fixture.app->tick();
    check(fixture.adapter.terminal.snapshot().revision == second_safe.revision,
        "second effect exact retry changed its new local safe origin");
    ok(call(*fixture.owner,FOUNDATION_ENGINE_PUMP_ONE,fixture.id));
    check(fixture.effects == 2,"second effect failed exactly-once Registry entry after new safe publication");
}

void old_inflight_query_cannot_release_effect_gate() {
    Fixture fixture(true,true); fixture.discover(); fixture.app->request_observation();
    const auto old_query = fixture.take(); fixture.finish_query(old_query);
    fixture.submit_service(2,fixture.route,1,encode_u32(42));
    check(!fixture.effects,"pending captured query entered actual native handler"); fixture.app->tick();
    redacted(fixture.app->view(),"Paired body observation");
    ok(call(*fixture.owner,FOUNDATION_ENGINE_PUMP_ONE,fixture.id)); check(fixture.effects == 1,"settled old query blocked actual native turn forever");
    (void)fixture.collect_service(2); const auto fresh = fixture.take();
    check(fresh.work.kind == EngineDocumentWorkKind::snapshot_query && fresh.work.request_sequence > old_query.work.request_sequence,
        "old/in-flight completion supplied post-effect observation authority");
    redacted(fixture.app->view(),"Paired body observation");
    fixture.finish_query(fresh); fixture.app->tick();
    check(fixture.app->body_ready(),"fresh post-effect query did not restore committed body");
}

void rejected_paired_join_cannot_supply_fresh_query_receipt() {
    Fixture fixture(true,true); fixture.discover();
    fixture.submit_service(2,fixture.route,1,encode_u32(44)); fixture.app->tick();
    ok(call(*fixture.owner,FOUNDATION_ENGINE_PUMP_ONE,fixture.id)); (void)fixture.collect_service(2);
    const auto conflict = fixture.take();
    // Full NDV2 with an exact transport join, but conflicting body/forms values
    // under the old publication revision. Forms consumes this request as unknown;
    // its true completion return is not an accepted paired-query receipt.
    fixture.native_value = "Conflicting same revision"; fixture.finish_query(conflict); fixture.app->tick();
    redacted(fixture.app->view(),fixture.native_value);
    check(!fixture.app->body_ready(),"internally rejected paired join released native publication gate");
    fixture.app->request_observation(); const auto fresh = fixture.take();
    ++fixture.revision; fixture.finish_query(fresh); fixture.app->tick();
    check(fixture.app->body_ready() && exported_text(fixture.app->view()).find(fixture.native_value) != std::string::npos,
        "later accepted paired query did not release retained gate");
}

void callbacks_cannot_stage_owner_or_ack_native_effect() {
    Fixture fixture(true,true); fixture.discover();
    bool invoked{}; fixture.adapter.during_present = [&] {
        if (invoked) return;
        invoked = true;
        fixture.app->request_observation(); fixture.app->tick(); fixture.app->retry_presentation();
        check(!fixture.peek(),"reentrant actual presentation callback staged an owner query");
    };
    fixture.app->viewport({55,16}); fixture.app->tick(); fixture.adapter.during_present = {};
    check(invoked,"callback fixture did not enter actual presenter");
    if (const auto pending = fixture.peek()) { fixture.finish_query(*pending); fixture.app->tick(); }
    fixture.submit_service(2,fixture.route,1,encode_u32(43));
    bool reentered{}; fixture.adapter.during_present = [&] {
        reentered = true; fixture.app->tick(); fixture.app->request_observation();
        check(call(*fixture.owner,FOUNDATION_ENGINE_PUMP_ONE,fixture.id).control == FOUNDATION_ENGINE_CONFLICT && !fixture.effects,
            "actual present callback acknowledged native effect before return");
    };
    fixture.app->tick(); fixture.adapter.during_present = {};
    check(reentered,"native effect did not attempt actual safe presentation");
    ok(call(*fixture.owner,FOUNDATION_ENGINE_PUMP_ONE,fixture.id));
    check(fixture.effects == 1,"postcallback native effect did not enter exactly once");
}

void owner_callback_depth_defers_document_admission() {
    Fixture fixture; fixture.activate("First field");
    ok(call(*fixture.owner,FOUNDATION_ENGINE_TURN_ENTER,fixture.id));
    check(fixture.owner->callback_depth() == 1,"actual owner callback fixture failed to enter native turn");
    fixture.app->tick(); fixture.app->request_observation();
    ok(call(*fixture.owner,FOUNDATION_ENGINE_TURN_LEAVE,fixture.id));
    check(!fixture.peek(),"application staged document work before actual owner callback returned");
    const auto begin = fixture.take();
    check(begin.work.kind == EngineDocumentWorkKind::form_action && get(begin.work.payload,48,1) == 0,
        "deferred callback native intent was dropped or replaced");
}

void typed_body_actions_require_family_ack_and_fresh_query() {
    using namespace foundation::ui;
    Fixture fixture(true,false,true);
    for (const auto kind:{DocumentActionV1Kind::focus,DocumentActionV1Kind::activate,DocumentActionV1Kind::select}) {
        if (kind==DocumentActionV1Kind::activate) fixture.activate("Ordinary project link");
        else if (kind==DocumentActionV1Kind::focus) {
            fixture.app->handle(gui::WidgetEvent{body_list(fixture.app->view()).spec.key,
                gui::SelectRecord{row(fixture.app->view(),"Ordinary project link")}});
        } else check(fixture.app->queue_selection({{71,1},{71,4}}),"explicit current text selection was not queued");
        check(!fixture.peek(),"body callback entered native owner before serialized tick");
        const auto request=fixture.take(); const auto decoded=fixture.body_request(request);
        check(decoded.key.nested_request_id && decoded.action.index()==static_cast<unsigned>(kind),"body action lost exact kind/nested request token");
        if (kind==DocumentActionV1Kind::select) {
            const auto& selection=std::get<DocumentActionV1Select>(decoded.action).selection;
            check(selection.anchor==DocumentNativePoint{71,1,DocumentNativeOffsetKind::text_utf16} &&
                selection.focus==DocumentNativePoint{71,4,DocumentNativeOffsetKind::text_utf16},"selection lost native UTF16 text endpoints");
        }
        check(!fixture.app->body_ready(),"returned action left displayed body ready");
        fixture.native_value="Actual paired body readback"; fixture.finish_body(request); fixture.app->tick();
        check(!fixture.app->body_ready(),"body readback manufactured a fresh query receipt");
        fixture.finish_body_ack(request);
        check(!fixture.app->body_ready(),"metadata ACK11 alone restored body input");
        const auto fresh=fixture.take();
        check(fresh.work.kind==EngineDocumentWorkKind::snapshot_query,"body ACK replayed the action or skipped fresh query");
        fixture.finish_query(fresh); fixture.app->tick();
        check(fixture.app->body_ready() && !fixture.peek(),"actual fresh query publication failed to restore body");
    }
    for (const std::string_view type:{"button","reset","submit"}) {
        Fixture control(false,false,true); control.control_type=type;
        control.refresh(); check(control.app->body_ready(),"actual paired input-button publication did not arm body");
        control.activate("First field"); control.activate("First field");
        check(!control.peek(),"input-button callback entered native Owner before serialized tick");
        const auto request=control.take(); const auto decoded=control.body_request(request);
        const auto* action=std::get_if<DocumentActionV1Activate>(&decoded.action);
        check(action && action->node==10 && decoded.key.nested_request_id==request.work.request_sequence &&
            request.work.request_sequence==2,"input button lost exact Activate/node or burned duplicate Owner reservations");
        const auto outcome=type=="reset" ? DocumentActionV1Result::rejected :
            type=="submit" ? DocumentActionV1Result::indeterminate : DocumentActionV1Result::completed;
        const auto code=type=="reset" ? DocumentActionV1Code::stale_document :
            type=="submit" ? DocumentActionV1Code::readback_failed : DocumentActionV1Code::ok;
        control.finish_body(request,outcome,code); control.app->tick();
        check(!control.app->body_ready(),"input-button body readback bypassed fresh-query barrier");
        control.finish_body_ack(request);
        check(!control.app->body_ready(),"input-button ACK11 alone restored input");
        const auto fresh=control.take();
        check(fresh.work.kind==EngineDocumentWorkKind::snapshot_query && fresh.work.request_sequence==4,
            "input-button stale/unknown completion replayed action or skipped exact ACK/query ordering");
        control.finish_query(fresh); control.app->tick();
        check(control.app->body_ready() && !control.peek(),"input button failed to restore after fresh paired observation");
    }
}

void certain_body_semantic_outcomes_consume_without_replay() {
    using namespace foundation::ui;
    for (const auto outcome:{DocumentActionV1Result::rejected,DocumentActionV1Result::indeterminate,
                            DocumentActionV1Result::completed_needs_current_observation}) {
        Fixture fixture(true,false,true); fixture.activate("Ordinary project link"); const auto request=fixture.take();
        const auto code=outcome==DocumentActionV1Result::rejected ? DocumentActionV1Code::stale_document :
            outcome==DocumentActionV1Result::indeterminate ? DocumentActionV1Code::readback_failed : DocumentActionV1Code::context_replaced;
        fixture.finish_body(request,outcome,code); fixture.app->tick();
        check(!fixture.app->body_ready() && !fixture.app->closed(),"certain semantic outcome became replay authority or terminal transport");
        fixture.finish_body_ack(request); const auto fresh=fixture.take();
        check(fresh.work.kind==EngineDocumentWorkKind::snapshot_query,"consumed semantic outcome replayed body request");
        ++fixture.revision; fixture.finish_query(fresh); fixture.app->tick();
        check(fixture.app->body_ready() && !fixture.peek(),"certain semantic outcome did not recover through actual fresh query");
    }
}

void body_navigation_retains_original_ack_target() {
    using namespace foundation::ui;
    Fixture fixture(true,false,true); fixture.activate("Ordinary project link"); const auto request=fixture.take();
    const auto decoded=fixture.body_request(request);
    const auto reply=encode_document_action_v1_reply(decoded,DocumentActionV1Result::completed_needs_current_observation,
        DocumentActionV1Code::context_replaced,true);
    fixture.claim(request,false);
    ok(call(*fixture.owner,FOUNDATION_ENGINE_TURN_ENTER,identity(request.work.target),{},request.transfer));
    auto next=fixture.id; ++next.document_sequence; next.service_generation=0;
    const auto begun=call(*fixture.owner,FOUNDATION_ENGINE_BEGIN_DOCUMENT,next); ok(begun); fixture.id=begun.id;
    ok(call(*fixture.owner,FOUNDATION_ENGINE_TURN_LEAVE,identity(request.work.target),{},request.transfer));
    fixture.result(request,reply,0,1,true); fixture.app->tick();
    check(!fixture.app->body_ready(),"navigation rearmed the replaced old body");
    const auto ack=fixture.finish_body_ack(request);
    check(ack.work.target!=target(fixture.id),"navigation remapped ACK11 to current document");
    const auto fresh=fixture.take(); check(fresh.work.target==target(fixture.id) && fresh.work.kind==EngineDocumentWorkKind::snapshot_query,
        "navigation did not observe the actual current target");
    ++fixture.revision; fixture.finish_query(fresh); fixture.app->tick();
    check(fixture.app->body_ready(),"new target query failed to rearm after exact old action retirement");
}

void body_completion_publication_fault_never_replays(bool after_install) {
    Fixture fixture(true,false,true); fixture.activate("Ordinary project link"); const auto request=fixture.take();
    fixture.finish_body(request); const auto claims=fixture.provider_claims;
    if (after_install) fixture.adapter.fail_after=true; else fixture.adapter.fail_before=true;
    try { fixture.app->tick(); } catch (const std::runtime_error&) {}
    check(fixture.app->presentation_pending() && !fixture.app->body_ready() && !fixture.peek(),"ACK11 crossed failed actual body publication");
    const auto failed=fixture.adapter.attempts.back();
    const auto retry=fixture.adapter.attempts.size();
    fixture.app->retry_presentation();
    check(fixture.provider_claims==claims && fixture.adapter.attempts.size()>retry &&
        fixture.adapter.attempts[retry].revision==failed.revision &&
        exported_text(fixture.adapter.attempts[retry])==exported_text(failed),
        "publication retry changed retained revision/content or repeated body native action");
    fixture.finish_body_ack(request); fixture.refresh();
    check(fixture.app->body_ready(),"publication retry failed to finish ACK11/fresh observation");
}

void malformed_body_transport_has_no_ack_or_replay() {
    using namespace foundation::ui;
    Fixture fixture(true,false,true); fixture.activate("Ordinary project link"); const auto request=fixture.take();
    const auto decoded=fixture.body_request(request);
    auto bytes=encode_document_action_v1_reply(decoded,DocumentActionV1Result::rejected,DocumentActionV1Code::stale_document,false);
    // Preserve the mailbox's exact packet/key join while corrupting a closed
    // semantic enum, so this reaches the App's strict decoder.
    bytes[64]=255;
    fixture.claim(request); fixture.result(request,bytes,0,1,false); fixture.app->tick();
    check(fixture.app->closed() && !fixture.app->body_ready() && !fixture.peek(),"malformed consumed body packet was decoded as success or repaired with ACK");
}

} // namespace
int main(int argc, char** argv) {
    const std::array<std::pair<const char*,std::function<void()>>,24> tests{{
        {"initial paired query and actual terminal Apply",initial_pair_and_actual_terminal_apply},
        {"form publication fault before actual install",[] { local_publication_failure(false); }},
        {"form publication fault after actual install",[] { local_publication_failure(true); }},
        {"Cancel after delivered Apply retains cleanup",cancel_after_delivered_apply_keeps_original_cleanup},
        {"retained query after actual publication fault",failed_query_retains_one_completion},
        {"semantic rejection/unknown versus acceptance",semantic_rejection_and_unknown_are_not_acceptance},
        {"endpoint unknown has no replay/ACK",endpoint_unknown_stops_without_ack_or_replay},
        {"unsupported body action has positive no-entry proof",unsupported_body_action_never_reaches_owner},
        {"navigation retains original four-field cleanup",navigation_preserves_original_action_cleanup},
        {"background retains exact action and fresh restore query",background_keeps_delivered_action_and_requires_fresh_restore_query},
        {"real Registry safe publication before-install fault",[] { native_effect_requires_actual_safe_publication_and_fresh_query(false); }},
        {"real Registry safe publication after-install fault",[] { native_effect_requires_actual_safe_publication_and_fresh_query(true); }},
        {"second effect requires new safe publication origin",second_effect_requires_a_new_safe_publication_origin},
        {"old in-flight query cannot release native gate",old_inflight_query_cannot_release_effect_gate},
        {"rejected paired join cannot release native gate",rejected_paired_join_cannot_supply_fresh_query_receipt},
        {"callback reentry cannot stage or acknowledge",callbacks_cannot_stage_owner_or_ack_native_effect},
        {"actual owner callback depth defers admission",owner_callback_depth_defers_document_admission},
        {"typed body command10 and ACK11 fresh-query barrier",typed_body_actions_require_family_ack_and_fresh_query},
        {"certain body semantic outcomes have no replay",certain_body_semantic_outcomes_consume_without_replay},
        {"body navigation retains exact old ACK11 target",body_navigation_retains_original_ack_target},
        {"body publication fault before actual install",[] { body_completion_publication_fault_never_replays(false); }},
        {"body publication fault after actual install",[] { body_completion_publication_fault_never_replays(true); }},
        {"malformed body packet has no ACK or replay",malformed_body_transport_has_no_ack_or_replay},
        {"shutdown is local and idempotent",[] { Fixture fixture; fixture.app->shutdown(); fixture.app->shutdown();
            check(fixture.app->closed() && !fixture.peek(),"local shutdown staged unexpected native work"); }}
    }};
    // Native endpoint uncertainty quarantines document-profile Owners for the
    // process lifetime. Each named case therefore runs in its own harness-owned
    // process; this executable never forks or starts a shell to reset authority.
    if (argc == 2 && std::string_view(argv[1]) == "--list") {
        for (const auto& [name,test] : tests) { (void)test; std::cout << name << '\n'; }
        return 0;
    }
    if (argc != 3 || std::string_view(argv[1]) != "--case") {
        std::cerr << "Use --list or --case NAME; every case requires a fresh process\n"; return 2;
    }
    const auto selected = std::find_if(tests.begin(),tests.end(),[&](const auto& test) {
        return std::string_view(test.first) == argv[2];
    });
    if (selected == tests.end()) { std::cerr << "Unknown case: " << argv[2] << '\n'; return 2; }
    try {
        selected->second(); ++cases; std::cout << "PASS " << selected->first << '\n';
        std::cout << cases << " cases, " << assertions << " assertions, 0 skipped\n"; return 0;
    } catch (const std::exception& error) {
        std::cerr << selected->first << ": " << error.what() << " (" << cases << " complete cases, " << assertions << " assertions)\n"; return 1;
    }
}
