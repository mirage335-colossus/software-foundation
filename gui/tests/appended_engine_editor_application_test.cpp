// SPDX-License-Identifier: CC0-1.0
// Actual App/Owner/Registry/copied endpoint and Surface Policy. Provider replies
// are synthetic values; no engine, SDK, browser, Backend or native IME is loaded.
#include "shared/appended_engine_application.hpp"
#include "shared/appended_engine_abi.h"
#include "shared/appended_engine_input_codec.hpp"
#include "shared/native_editor_codec.hpp"
#include "../../src/appended/sha256.hpp"

#include <gui/retained_adapter.hpp>
#include <algorithm>
#include <array>
#include <functional>
#include <iostream>
#include <memory>
#include <optional>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace {
using namespace foundation;
using namespace appended;
namespace input = appended::engine_input;
namespace document = appended::engine_document;
namespace profile = appended::engine_editor;
namespace ne = ui::native_editor;
namespace codec = ne::codec;
using Span = std::span<const std::uint8_t>;
constexpr std::uint64_t large = UINT64_C(9007199254740993);
std::size_t assertions{}, groups{};

void check(bool value, const char* message) {
    ++assertions;
    if (!value) throw std::runtime_error(message);
}
template<class F> void rejects(F action, const char* message) {
    bool rejected = false;
    try { action(); } catch (const std::invalid_argument&) { rejected = true; }
    check(rejected, message);
}
Span bytes(std::string_view text) { return {reinterpret_cast<const std::uint8_t*>(text.data()), text.size()}; }
void put(std::span<std::uint8_t> output, std::size_t offset, std::uint64_t value, unsigned width) {
    check(offset <= output.size() && width <= output.size() - offset, "fixture write escaped its record");
    for (unsigned index = 0; index < width; ++index) output[offset + index] = static_cast<std::uint8_t>(value >> (index * 8));
}
std::uint64_t get(Span value, std::size_t offset, unsigned width) {
    check(offset <= value.size() && width <= value.size() - offset, "fixture read escaped its record");
    std::uint64_t result{};
    for (unsigned index = 0; index < width; ++index) result |= std::uint64_t(value[offset + index]) << (index * 8);
    return result;
}
EngineIdentity identity(EngineEditorTarget value) {
    return {value.worker_epoch, value.application_instance, value.document_sequence, value.service_generation};
}
codec::WireTarget wire_target(const EngineEditorWork& work) {
    return {work.target.worker_epoch, work.target.application_instance, work.target.document_sequence,
            work.target.service_generation, work.request_sequence};
}
Bytes request(std::uint32_t operation, EngineIdentity target, Span body = {}, std::uint64_t transfer = 0) {
    Bytes result(FOUNDATION_ENGINE_HEADER_BYTES + body.size());
    std::copy_n("FKB1", 4, result.begin());
    put(result, 4, FOUNDATION_ENGINE_RECORD_VERSION, 2); put(result, 6, operation, 2); put(result, 8, result.size(), 4);
    put(result, 16, target.worker_epoch, 8); put(result, 24, target.application_instance, 8);
    put(result, 32, target.document_sequence, 8); put(result, 40, target.service_generation, 8);
    put(result, 48, transfer, 8); put(result, 64, body.size(), 4);
    std::copy(body.begin(), body.end(), result.begin() + FOUNDATION_ENGINE_HEADER_BYTES);
    return result;
}
struct Reply {
    EngineIdentity target;
    std::uint64_t transfer{};
    std::uint32_t control{}, service{};
    Bytes record;
    Span body() const { return Span(record).subspan(FOUNDATION_ENGINE_RECEIPT_BYTES); }
};
Reply call(EngineOwner& owner, std::uint32_t operation, EngineIdentity target,
           Span body = {}, std::uint64_t transfer = 0) {
    const auto input = request(operation, target, body, transfer);
    Bytes output(FOUNDATION_ENGINE_RECEIPT_BYTES + FOUNDATION_ENGINE_EDITOR_MAX_RESULT_BODY_BYTES, 0xa5);
    const auto count = owner.dispatch(operation, input, output);
    check(count >= static_cast<std::int32_t>(FOUNDATION_ENGINE_RECEIPT_BYTES) && static_cast<std::size_t>(count) <= output.size(),
          "Owner omitted a complete copied response");
    output.resize(static_cast<std::size_t>(count));
    check(get(output, 6, 2) == (operation | FOUNDATION_ENGINE_REPLY_KIND) && get(output, 8, 4) == output.size() &&
          get(output, 64, 4) == output.size() - FOUNDATION_ENGINE_HEADER_BYTES,
          "copied response framing changed");
    return {{get(output,16,8),get(output,24,8),get(output,32,8),get(output,40,8)},get(output,48,8),
            static_cast<std::uint32_t>(get(output,72,4)),static_cast<std::uint32_t>(get(output,76,4)),std::move(output)};
}
void ok(const Reply& reply) {
    if (reply.control != FOUNDATION_ENGINE_OK || reply.service != 0)
        throw std::runtime_error("Owner refused fixture operation " + std::to_string(get(reply.record,6,2)) +
                                 ": control=" + std::to_string(reply.control) + " service=" + std::to_string(reply.service));
    check(true, "complete copied operation");
}
Package package() {
    const std::string startup = "{\"kind\":\"foundation-appended-startup\",\"primary\":\"web\",\"schema_version\":1}";
    const std::string html = "<!doctype html><title>Editor App fixture</title><input value='A😀B'>";
    const auto file = [](std::string_view path, std::string_view mime, std::size_t offset, std::string_view text) {
        return "{\"component\":\"web\",\"length\":" + std::to_string(text.size()) + ",\"media_type\":\"" + std::string(mime) +
            "\",\"offset\":" + std::to_string(offset) + ",\"path\":\"" + std::string(path) + "\",\"sha256\":\"" +
            detail::hex_digest(detail::sha256(bytes(text))) + "\"}";
    };
    const auto index = "{\"application\":{\"id\":\"org.example.editor-app\",\"name\":\"Editor App fixture\",\"version\":\"1.0.0\"},"
        "\"components\":{\"binary\":{\"entry\":null,\"present\":false,\"profile\":null},\"web\":{\"entry\":\"web/index.html\",\"present\":true}},"
        "\"files\":[" + file("web/.foundation/startup-v1.json","application/json",0,startup) + "," +
        file("web/index.html","text/html",startup.size(),html) + "],\"identities\":{},\"kind\":\"foundation-appended-package\","
        "\"requires\":{\"abi\":{\"major\":1,\"minor\":0},\"capabilities\":[\"foundation.startup.v1\"],\"services\":[]},\"schema_version\":1}";
    Bytes data(startup.begin(),startup.end()); data.insert(data.end(),html.begin(),html.end());
    const auto offset = data.size(); data.insert(data.end(),index.begin(),index.end());
    return read_package(data,offset,index.size());
}
profile::EngineEditorProfileFacts editor_facts() {
    profile::EngineEditorProfileFacts value;
    value.enabled=true; value.kind=profile::ProfileKind::editor; value.name=profile::kProfileName;
    value.provider_abi_major=BIB_ENGINE_DOCUMENT_V2_ABI_MAJOR; value.provider_abi_minor=BIB_ENGINE_DOCUMENT_V2_ABI_MINOR;
    value.host_abi_major=BIB_ENGINE_DOCUMENT_V2_HOST_ABI_MAJOR; value.host_abi_minor=BIB_ENGINE_DOCUMENT_V2_HOST_ABI_MINOR;
    value.target_system=BIB_ENGINE_TARGET_LINUX; value.target_processor=BIB_ENGINE_CPU_X86_64; value.pointer_bits=64;
    value.lifetime=BIB_ENGINE_LIFETIME_PROCESS; value.maximum_starts=1; value.viewport_width=800; value.viewport_height=600;
    value.provider_capabilities=profile::kProviderCapabilities; value.surface_capabilities=profile::kSurfaceCapabilities;
    value.surface_protocol_version=BIB_ENGINE_EDITOR_SURFACE_PROTOCOL_VERSION; value.editor_protocol_version=BIB_ENGINE_EDITOR_PROTOCOL_VERSION;
    value.base_header_sha256=document::kBaseHeaderSha256; value.document_header_sha256=document::kExtensionHeaderSha256;
    value.document_contract_sha256=document::kContractSha256; value.document_catalog_sha256=document::kCatalogSha256;
    value.physical_catalog_sha256=document::kPhysicalCatalogSha256; value.editor_header_sha256=profile::kHeaderSha256;
    value.contract_sha256=profile::kContractSha256; value.catalog_sha256=profile::kCatalogSha256; value.schema_sha256=profile::kSchema;
    value.build_sha256.fill(0x31); value.source_recipe_sha256.fill(0x42); // Test-only pins; no retained engine is represented.
    value.queries=profile::kQueries; value.commands=profile::kCommands; value.query_count=2; value.command_count=7;
    check(profile::editor_profile_valid(value), "editor fixture facts are malformed");
    return value;
}
Bytes frame(std::uint64_t base) {
    Bytes result(48 + 800 * 600 * 4);
    put(result,0,1,4); put(result,4,800,4); put(result,8,600,4); put(result,12,3200,4);
    put(result,24,800,4); put(result,28,600,4); put(result,32,base,8); put(result,40,base+1,8);
    for (std::size_t index=48;index<result.size();index+=4) { result[index]=0x29; result[index+3]=255; }
    return result;
}
struct TestAdapter final : gui::RetainedAdapter {
    bool paired=false;
    bool throw_before_next=false, throw_after_next=false;
    unsigned publication_faults{};
    std::function<void(std::uint64_t)> legacy;
    void present(gui::Snapshot value) override {
        if (std::exchange(throw_before_next,false)) {
            ++publication_faults; throw std::runtime_error("injected editor publication failure before install");
        }
        const auto revision=value.revision;
        gui::RetainedAdapter::present(std::move(value));
        if (std::exchange(throw_after_next,false)) {
            ++publication_faults; throw std::runtime_error("injected editor publication failure after install");
        }
        if (!paired && legacy) legacy(revision);
    }
};
struct PolicyPort final : ui::EngineEditorPort {
    struct Commit {
        std::uint64_t revision{};
        std::optional<gui_surface::Presentation> surface;
        std::optional<ne::EditorPublication> editor;
        std::optional<ne::CompositionFact> composition;
    };
    TestAdapter& adapter;
    gui_surface::Capabilities negotiated, offered;
    gui_surface::Policy policy;
    Commit committed;
    std::vector<Commit> commits;
    std::function<void(const Commit&)> during_publication;
    std::function<void(gui_surface::Revocation)> revoked;
    bool publishing=false, service=false;
    static constexpr std::uint64_t native_generation=large+73;
    static gui_surface::Capabilities selected() {
        gui_surface::Capabilities value; value.supported=profile::kSurfaceCapabilities; value.mouse_input_version=1; return value;
    }
    explicit PolicyPort(TestAdapter& value, bool preconnect=true)
        : adapter(value), negotiated(selected()), offered(preconnect?gui_surface::Capabilities{}:negotiated),
          policy(negotiated,native_generation) {
        adapter.legacy=[this](std::uint64_t revision) {
            auto result=policy.legacy_present(revision);
            committed={revision,{},{},{}};
            if (revoked && result.revoked.identity) revoked(std::move(result.revoked));
        };
    }
    ~PolicyPort() override { adapter.legacy={}; }
    const gui_surface::Capabilities& capabilities() const noexcept override { return offered; }
    std::uint64_t generation() const noexcept override { return native_generation; }
    bool available() const { return committed.surface && committed.surface->available && !service; }
    bool editable() const { return available() && committed.editor && committed.editor->basis; }
    void connect() { offered=negotiated; }
    void install(gui::Snapshot snapshot, const Commit& candidate) {
        check(!publishing, "paired publication reentered the test port");
        publishing=true; adapter.paired=true;
        try {
            adapter.present(std::move(snapshot));
            if (during_publication) during_publication(candidate);
        } catch (...) { adapter.paired=false; publishing=false; throw; }
        adapter.paired=false; publishing=false;
    }
    gui_surface::CommitResult present_pair(gui::Snapshot snapshot,const gui_surface::Presentation& surface) override {
        return present_editor_pair(std::move(snapshot),surface,{},{});
    }
    gui_surface::CommitResult present_editor_pair(gui::Snapshot snapshot,const gui_surface::Presentation& surface,
            std::optional<ne::EditorPublication> publication,std::optional<ne::CompositionFact> composition) override {
        check(snapshot.revision==surface.identity.presentation_revision,"snapshot and Surface revisions split");
        check(snapshot.widgets.size()==1 && snapshot.widgets.front().spec.key.id==surface.identity.owner.id &&
              snapshot.widgets.front().spec.key.generation==surface.identity.owner.generation,"Surface does not own the actual bitmap widget");
        check(surface.bounds==gui_surface::Rect{0,0,800,600} && surface.clip==surface.bounds && surface.display_scale==1,
              "editor pair changed fixed physical geometry");
        if (publication && publication->basis) {
            const auto& basis=*publication->basis;
            auto alias=basis.identity; alias.presentation_revision=surface.identity.presentation_revision;
            check(surface.editor && alias==surface.identity && basis.editor_revision==surface.editor->revision &&
                  basis.surrounding==surface.editor->surrounding && basis.selection==surface.editor->selection &&
                  basis.backward==surface.editor->selection_backward && basis.composition==surface.editor->composition_transaction &&
                  !publication->retirement,"public editor and checked private Basis disagree");
        } else check(!surface.editor,"Surface fabricated an editor without checked Basis");
        check(!publication || publication->composition==composition,"logical composition split from editor publication");
        auto physical=surface;
        physical.editor.reset();
        constexpr auto editor_bits=gui_surface::feature(gui_surface::Feature::committed_text) |
            gui_surface::feature(gui_surface::Feature::composition) | gui_surface::feature(gui_surface::Feature::surrounding_text) |
            gui_surface::feature(gui_surface::Feature::selection);
        physical.required&=~editor_bits;
        auto prepared=policy.prepare(physical);
        if (prepared.status!=gui_surface::Status::ok) return {prepared.status,{}};
        Commit candidate{snapshot.revision,surface,std::move(publication),std::move(composition)};
        install(std::move(snapshot),candidate);
        auto result=policy.commit(std::move(prepared.prepared),candidate.revision);
        if (result.status==gui_surface::Status::ok) { committed=std::move(candidate); commits.push_back(committed); }
        return result;
    }
    gui_surface::CommitResult present_editor_retirement(gui::Snapshot snapshot,ne::EditorPublication publication) override {
        check(snapshot.widgets.empty() && !publication.basis && publication.retirement && publication.retirement->readback_attested &&
              publication.retirement->observation_revision,"empty editor retirement lacks checked readback");
        Commit candidate{snapshot.revision,{},std::move(publication),{}};
        install(std::move(snapshot),candidate);
        auto result=policy.legacy_present(candidate.revision);
        if (result.status==gui_surface::Status::ok) { committed=std::move(candidate); commits.push_back(committed); }
        return result;
    }
    void set_owned_service_active(bool active) override {
        service=active;
        if (active && policy.accepted()) {
            auto result=policy.legacy_present(adapter.snapshot().revision);
            committed.surface.reset(); committed.editor.reset(); committed.composition.reset();
            if (revoked && result.revoked.identity) revoked(std::move(result.revoked));
        }
    }
};
struct Fixture {
    TestAdapter adapter;
    profile::EngineEditorProfileFacts facts=editor_facts();
    std::shared_ptr<EngineOwner> owner;
    PolicyPort* port{};
    std::unique_ptr<ui::AppendedEngineApplication> app;
    std::optional<ne::NativeProjection> live;
    std::uint64_t input_sequence{}, sample=large+101, next_native_token=large+501;
    std::uint64_t last_retired_context{}, held_ticket{};
    std::optional<ne::NativeRetireMaterial> last_retired_material;
    unsigned native_effects{}, native_retirements{};
    bool hold_on_entry=false;
    static constexpr std::string_view service_name="org.example.editor-app.native";
    explicit Fixture(bool create=true,bool native_service=false) {
        EngineOwnerConfiguration config; config.worker_epoch=large+11; config.editor_profile=facts;
        if (native_service) config.native_services.push_back({{std::string(service_name),1,0,SchemaId{7},4},
            [this](std::uint32_t operation,Span value,std::span<std::uint8_t> output)->ServiceReply {
                const auto effect=owner->native_effect();
                check(operation==1 && value.size()==4 && output.size()>=4 && effect && effect->entered &&
                      effect->target==owner->identity() && effect->input_context==last_retired_context && native_retirements &&
                      last_retired_material && last_retired_material->input_context==effect->input_context &&
                      port && port->service && !port->available() && !port->editable() && adapter.snapshot().widgets.empty() &&
                      port->committed.revision==adapter.snapshot().revision,
                      "actual Registry handler entered before checked editor9/physical retirement and safe redaction");
                if (hold_on_entry) {
                    check(owner->hold_native_effect(effect->ticket),"actual native handler could not retain its UI hold");
                    held_ticket=effect->ticket;
                }
                ++native_effects; std::copy(value.begin(),value.end(),output.begin()); return {ServiceStatus::ok,4};
            }});
        owner=std::make_shared<EngineOwner>(package(),std::move(config));
        ok(call(*owner,FOUNDATION_ENGINE_CONFIGURE,{large+11,0,0,0}));
        ok(call(*owner,FOUNDATION_ENGINE_TURN_ENTER,{large+11,0,0,0}));
        ok(call(*owner,FOUNDATION_ENGINE_BEGIN_DOCUMENT,{large+11,large+19,1,0}));
        ok(call(*owner,FOUNDATION_ENGINE_TURN_LEAVE,{large+11,0,0,0}));
        ok(call(*owner,FOUNDATION_ENGINE_FRAME_COMMIT,owner->identity(),frame(0)));
        if (create) construct();
    }
    void construct() {
        auto owned=std::make_unique<PolicyPort>(adapter); port=owned.get();
        app=std::make_unique<ui::AppendedEngineApplication>(adapter,owner,facts,ui::BoundEngineEditorPort{std::move(owned)});
        port->revoked=[this](gui_surface::Revocation value) { app->surface_revoked(std::move(value)); };
    }
    void connect() {
        port->connect(); app->surface_connected(port->capabilities()); app->tick();
    }
    std::optional<input::Command> peek_physical() {
        const auto result=call(*owner,FOUNDATION_ENGINE_PEEK_INPUT,owner->identity());
        if (result.control==FOUNDATION_ENGINE_EMPTY) return {};
        ok(result);
        input::Command command;
        check(input::decode_command(result.body(),command)==input::Status::ok,"invalid physical mailbox body");
        return command;
    }
    input::Command consume_physical(std::int32_t provider_status=0,std::uint32_t disposition=1) {
        const auto pending=call(*owner,FOUNDATION_ENGINE_PEEK_INPUT,owner->identity()); ok(pending);
        check(pending.record==call(*owner,FOUNDATION_ENGINE_PEEK_INPUT,owner->identity()).record,"physical PEEK changed immutable work");
        input::Command command;
        check(input::decode_command(pending.body(),command)==input::Status::ok,"invalid physical command");
        ok(call(*owner,FOUNDATION_ENGINE_TURN_ENTER,pending.target,{},pending.transfer));
        ok(call(*owner,FOUNDATION_ENGINE_TURN_LEAVE,pending.target,{},pending.transfer));
        Bytes result;
        check(input::encode_command_result({provider_status,disposition,command.request_sequence,0,0},result)==input::Status::ok,"invalid physical receipt");
        ok(call(*owner,FOUNDATION_ENGINE_COMMAND_RESULT,pending.target,result,pending.transfer));
        if (command.operation==3) {
            input::Focus focus;
            check(input::decode_focus(command.payload,focus)==input::Status::ok,"malformed staged FOCUS");
            if (focus.action==2) last_retired_context=focus.expected_context;
        }
        return command;
    }
    std::optional<EngineEditorDispatch> peek_editor() {
        const auto result=call(*owner,FOUNDATION_ENGINE_PEEK_EDITOR_WORK,owner->identity());
        if (result.control==FOUNDATION_ENGINE_EMPTY) return {};
        ok(result);
        check(result.transfer && result.body().size()>=FOUNDATION_ENGINE_EDITOR_WORK_PREFIX_BYTES,"editor PEEK omitted complete header");
        EngineEditorDispatch dispatch;
        dispatch.transfer=result.transfer;
        dispatch.work.target={result.target.worker_epoch,result.target.application_instance,result.target.document_sequence,result.target.service_generation};
        dispatch.work.kind=static_cast<EngineEditorWorkKind>(get(result.body(),0,4));
        dispatch.work.operation=static_cast<std::uint32_t>(get(result.body(),4,4));
        dispatch.work.request_sequence=get(result.body(),8,8);
        std::copy_n(result.body().begin()+16,32,dispatch.work.schema_sha256.begin());
        dispatch.work.required_reply_capacity=static_cast<std::uint32_t>(get(result.body(),48,4));
        check(get(result.body(),52,4)==result.body().size()-FOUNDATION_ENGINE_EDITOR_WORK_PREFIX_BYTES,"editor PEEK length mismatch");
        dispatch.work.payload.assign(result.body().begin()+FOUNDATION_ENGINE_EDITOR_WORK_PREFIX_BYTES,result.body().end());
        check(valid_engine_editor_work_join(dispatch.work),"App staged malformed editor work");
        check(result.record==call(*owner,FOUNDATION_ENGINE_PEEK_EDITOR_WORK,owner->identity()).record,"editor PEEK reminted work");
        return dispatch;
    }
    EngineEditorDispatch query() {
        const auto work=peek_editor();
        check(work && work->work.kind==EngineEditorWorkKind::projection_query && work->work.operation==BIB_ENGINE_QUERY_EDITOR_PROJECTION_V1,
              "expected actual App projection query4");
        return *work;
    }
    void finish_editor(const EngineEditorDispatch& dispatch,Span encoded,std::uint32_t disposition,std::uint64_t revision=0,
                       std::int32_t provider_status=0,bool handled=false) {
        Bytes claim(FOUNDATION_ENGINE_EDITOR_BEGIN_BYTES);
        put(claim,0,static_cast<std::uint32_t>(dispatch.work.kind),4); put(claim,8,dispatch.work.request_sequence,8);
        const auto target=identity(dispatch.work.target);
        ok(call(*owner,FOUNDATION_ENGINE_BEGIN_EDITOR_WORK,target,claim,dispatch.transfer));
        ok(call(*owner,FOUNDATION_ENGINE_TURN_ENTER,target,{},dispatch.transfer));
        ok(call(*owner,FOUNDATION_ENGINE_TURN_LEAVE,target,{},dispatch.transfer));
        Bytes result(FOUNDATION_ENGINE_EDITOR_RESULT_PREFIX_BYTES+encoded.size());
        put(result,0,static_cast<std::uint32_t>(dispatch.work.kind),4); put(result,8,dispatch.work.request_sequence,8);
        put(result,16,static_cast<std::uint32_t>(provider_status),4); put(result,20,disposition,4);
        put(result,24,encoded.size(),4); put(result,28,handled?1:0,4); put(result,32,revision,8);
        std::copy(encoded.begin(),encoded.end(),result.begin()+FOUNDATION_ENGINE_EDITOR_RESULT_PREFIX_BYTES);
        ok(call(*owner,FOUNDATION_ENGINE_EDITOR_WORK_RESULT,target,result,dispatch.transfer));
    }
    ne::NativeProjection finish_query(const EngineEditorDispatch& dispatch,bool available) {
        codec::ProjectionQuery query;
        check(codec::decode_projection_query(dispatch.work.payload,query) && query.target==wire_target(dispatch.work),"projection query target changed");
        codec::ProjectionReply reply;
        reply.target=query.target; reply.identity=query.identity; reply.observation_revision=++sample; reply.readback_attested=true;
        ne::NativeProjection projection;
        if (available) {
            if (live && live->identity.context==query.identity.context) projection=*live;
            else {
                projection.editor_revision=large+201; projection.surrounding="A😀B"; projection.selection={1,5};
                projection.mapping_id=large+301; projection.frame_id=large+401; projection.readback_attested=true;
                projection.caret={12,24,1,18}; projection.editable=true; projection.input_purpose="text";
                projection.retire=ne::NativeRetireMaterial{next_native_token++,projection.mapping_id,query.identity.context,0};
            }
            projection.identity=query.identity;
            check(!query.mapping_id || query.mapping_id==projection.mapping_id,"head query changed native mapping");
            reply.state=codec::ProjectionReply::State::available; reply.projection=projection; live=projection;
        } else reply.state=codec::ProjectionReply::State::noneditable;
        Bytes encoded;
        check(codec::encode_projection_reply(reply,encoded),"fixture projection reply is invalid");
        finish_editor(dispatch,encoded,0,reply.observation_revision);
        return projection;
    }
    void finish_revoke(const EngineEditorDispatch& dispatch) {
        codec::RevocationEnvelope request;
        check(dispatch.work.kind==EngineEditorWorkKind::revoke && dispatch.work.operation==BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1 &&
              codec::decode_revocation(dispatch.work.payload,request) && live && request.request.material==*live->retire,
              "native9 did not preserve the latest actual provider-issued material");
        ne::NativeResult result;
        result.outcome=ne::Outcome::applied; result.continuity=ne::Continuity::replaced;
        result.availability=ne::NativeAvailability::unavailable; result.observation_revision=++sample;
        result.readback_identity=request.request.identity; result.readback_attested=true; result.retired=request.request.material;
        Bytes encoded;
        check(codec::encode_native_result({request.target,result},encoded),"fixture native9 closure is malformed");
        finish_editor(dispatch,encoded,1); ++native_retirements; last_retired_material=request.request.material;
        live.reset(); // The next actual projection needs fresh provider-issued authority, even in the same context.
    }
    std::uint64_t bind() {
        connect();
        check(!port->available() && !peek_editor(),"editor work or admission preceded physical bind consumption");
        const auto command=consume_physical(); input::Focus focus;
        check(command.operation==3 && input::decode_focus(command.payload,focus)==input::Status::ok && focus.action==1 && focus.input_context,
              "first command was not exact bind metadata");
        app->tick();
        check(!port->available() && !peek_physical(),"bind alone opened editor or body-key admission");
        const auto pending=query(); codec::ProjectionQuery projection;
        check(codec::decode_projection_query(pending.work.payload,projection) && projection.identity.context==focus.input_context &&
              projection.identity.generation==port->generation() && projection.mapping_id==0,
              "initial query4 did not use the successfully bound physical context");
        return focus.input_context;
    }
    void activate(bool available=true) { bind(); finish_query(query(),available); app->tick(); }
    gui_surface::Status send(gui_surface::Input value) {
        if (!policy_identity()) return gui_surface::Status::unavailable;
        auto accepted=port->policy.accept({*policy_identity(),++input_sequence,std::move(value)});
        const auto status=accepted.status;
        if (accepted.accepted) app->surface_input(std::move(*accepted.accepted));
        return status;
    }
    std::optional<gui_surface::Identity> policy_identity() const {
        if (const auto* current=port->policy.accepted()) return current->identity;
        return {};
    }
    void focus_null() {
        check(send(gui_surface::FocusChange{true,true,gui_surface::FocusCause::direct})==gui_surface::Status::ok,"null fallback could not accept real focus");
        app->tick(); const auto command=consume_physical();
        check(command.operation==3,"focus normalization did not use physical FOCUS3");
        app->tick(); finish_query(query(),false); app->tick();
        check(port->available() && port->policy.focused(),"focused checked-null fallback did not become current");
    }
    ne::Basis basis() const {
        check(port->committed.editor && port->committed.editor->basis,"fixture lacks actually published checked Basis");
        return *port->committed.editor->basis;
    }
};
ne::Packet text_packet(ne::Basis basis) {
    ne::Packet result;
    result.session=large+601; result.basis=std::move(basis);
    auto& observation=result.observation;
    observation.id=large+701; observation.kind=ne::Kind::text; observation.authority=ne::Authority::range;
    observation.before={"A😀B",1,3,ne::Direction::forward,{1,5},6};
    observation.after=ne::TextObservation{"AXB",2,2,ne::Direction::none,{2,2},3};
    observation.data=ne::TextData{"insertText","X",{1,5},{}};
    check(ne::valid_observation(observation),"fixture text observation is malformed");
    return result;
}
void typed_admission_and_old_constructor_rejection() {
    Fixture f(false);
    const auto unchanged=f.adapter.snapshot().revision;
    rejects([&] { ui::AppendedEngineApplication old(f.adapter,f.owner); },"editor2035 entered bitmap-only constructor");
    rejects([&] { ui::AppendedEngineApplication old(f.adapter,f.owner,std::unique_ptr<ui::EngineSurfacePort>{},input::EngineSurfaceProfileFacts{}); },
            "editor2035 entered legacy physical constructor");
    rejects([&] { ui::AppendedEngineApplication old(f.adapter,f.owner,document::EngineDocumentProfileFacts{}); },
            "editor2035 entered old document constructor");
    rejects([&] { ui::AppendedEngineApplication invalid(f.adapter,f.owner,f.facts,ui::BoundEngineEditorPort{}); },"editor2035 admitted null bound port");
    auto mismatched=f.facts; mismatched.build_sha256[0]^=1;
    rejects([&] { ui::AppendedEngineApplication invalid(f.adapter,f.owner,mismatched,
                ui::BoundEngineEditorPort{std::make_unique<PolicyPort>(f.adapter)}); },"editor App ignored exact Owner profile agreement");
    for (unsigned bad=0;bad<3;++bad) {
        auto port=std::make_unique<PolicyPort>(f.adapter,false);
        if (bad==0) port->offered.supported=input::kSurfaceCapabilities;
        if (bad==1) port->offered.version=2; // Typed Policy version stays1; browser editor wire is2.
        if (bad==2) port->offered.mouse_input_version=0;
        rejects([&] { ui::AppendedEngineApplication invalid(f.adapter,f.owner,f.facts,ui::BoundEngineEditorPort{std::move(port)}); },
                "editor App accepted partial or incompatible port facts");
    }
    check(f.adapter.snapshot().revision==unchanged && !f.owner->closed() && !f.owner->native_effect(),"failed editor admission published or entered native work");
    f.construct();
    check(f.port->capabilities().supported==0 && !f.port->available(),"pre-CONNECT editor port fabricated physical support");
    f.connect(); check(f.port->capabilities().supported==profile::kSurfaceCapabilities,"exact editor8255 negotiation lost capabilities");
}
void bind_then_query_uses_committed_context() {
    Fixture f; const auto context=f.bind(); const auto work=f.query();
    check(f.owner->frame() && f.owner->frame()->frame_revision==1,"editor bind fabricated a frame");
    const auto actual=f.finish_query(work,true);
    check(!f.port->editable(),"copied query result published before the later App owner task");
    f.app->tick();
    const auto basis=f.basis();
    check(f.port->editable() && basis.identity.context==context && basis.identity.owner.id=="engine.frame" &&
          basis.editor_revision==actual.editor_revision && basis.surrounding=="A😀B" && basis.selection==gui_surface::ByteRange{1,5} &&
          f.port->committed.surface->editor->caret==actual.caret && !f.peek_editor() && !f.peek_physical(),
          "checked projection did not atomically open exact frame/editor authority");
}
void checked_null_mouse_focus_requires_fresh_query() {
    Fixture f; f.activate(false); f.focus_null();
    const auto before=f.owner->frame()->frame_revision;
    const auto old=f.port->committed.surface->identity;
    gui_surface::MouseTransition mouse;
    mouse.phase=gui_surface::MousePhase::down; mouse.capture_token=large+809; mouse.buttons=1; mouse.x=18.25; mouse.y=29.5;
    check(f.send(mouse)==gui_surface::Status::ok,"focused checked-null page did not accept mouse press");
    check(!f.peek_physical() && !f.peek_editor(),"physical callback staged native work synchronously");
    f.app->tick();
    check(!f.peek_editor(),"projection query overtook an unconsumed mouse focus effect");
    const auto physical=f.consume_physical(); input::Mouse decoded;
    check(physical.operation==5 && input::decode_mouse(physical.payload,decoded)==input::Status::ok &&
          decoded.capture_token==mouse.capture_token && decoded.input_context==old.context,"mouse normalization lost exact authority");
    f.app->tick(); const auto refresh=f.query();
    check(f.port->policy.focused() && !f.peek_physical() && f.owner->frame()->frame_revision==before,
          "unchanged frame kept stale checked-null body-key authority after mouse focus");
    const auto key=f.send(gui_surface::KeyTransition{gui_surface::KeyPhase::down,"x","KeyX"});
    check(key!=gui_surface::Status::not_focused,"body-key guard falsely passed by discarding existing native focus");
    f.app->tick();
    check(!f.peek_physical() && f.query().work.payload==refresh.work.payload,"blocked body key replaced or overtook projection work");
    f.finish_query(refresh,true); f.app->tick();
    check(f.port->editable() && f.basis().identity.context==old.context && f.owner->frame()->frame_revision==before && !f.peek_physical(),
          "fresh editor projection rebased context, replayed body key or fabricated render");
    const auto unchanged_basis=f.basis(); const auto unchanged_material=f.live->retire;
    const auto retirements=f.native_retirements;
    mouse.phase=gui_surface::MousePhase::up; mouse.buttons=0;
    check(f.send(mouse)==gui_surface::Status::ok,"editor readback refresh lost existing physical mouse capture");
    f.app->tick(); const auto release=f.consume_physical();
    check(release.operation==5 && input::decode_mouse(release.payload,decoded)==input::Status::ok &&
          decoded.capture_token==mouse.capture_token && decoded.input_context==old.context && decoded.phase==2,
          "post-refresh mouse release changed exact held physical authority");
    f.app->tick();
    f.finish_query(f.query(),true); f.app->tick();
    check(f.basis().token==unchanged_basis.token && f.live->retire==unchanged_material &&
          f.native_retirements==retirements,"inert mouse readback retired or reminted an unchanged editor basis");
}
void accepted_head_resolves_then_publishes_before_take() {
    Fixture f; f.activate();
    const auto bitmap=[](const gui::Snapshot& value,std::uint64_t revision,std::uint8_t red) {
        check(value.widgets.size()==1 && value.widgets.front().state.bitmap.revision==revision,
              "checked editor head used the wrong actual bitmap frame");
        std::array<std::uint8_t,3> pixel{}; bool painted=false;
        value.widgets.front().state.bitmap.source.paint({800,600,{0,0,1,1},gui::PixelFormat::rgb24},
            [&](unsigned x,unsigned y,gui::PixelBlock block) {
                check(x==0 && y==0 && block.bytes.size()>=3,"editor frame paint changed its copied damage origin");
                std::copy_n(block.bytes.begin(),3,pixel.begin()); painted=true;
            });
        check(painted && pixel==std::array<std::uint8_t,3>{red,0,0},"editor bitmap did not retain its actual copied frame pixels");
    };
    auto packet=text_packet(f.basis()); const auto captured=packet;
    ok(call(*f.owner,FOUNDATION_ENGINE_TURN_ENTER,f.owner->identity()));
    const auto head=f.app->editor_submit(packet);
    check(head && !f.app->editor_take(*head),"accepted editor head fabricated an immediate completion");
    packet.basis.surrounding="caller mutation";
    std::get<ne::TextData>(packet.observation.data).text="caller mutation";
    f.app->tick();
    check(f.owner->callback_depth()==1,"editor ingress changed active native turn depth");
    ok(call(*f.owner,FOUNDATION_ENGINE_TURN_LEAVE,f.owner->identity()));
    check(!f.peek_editor() && !f.peek_physical(),"editor callback staged work inside active native turn");
    const auto reservation=f.owner->reserve_document_sequence();
    check(reservation.has_value(),"fixture could not hold actual shared Owner reservation");
    f.app->tick();
    check(!f.peek_editor() && !f.peek_physical() && !f.app->editor_take(*head),"busy shared Owner fabricated work or a completion");
    check(f.owner->cancel_document_sequence(*reservation),"fixture could not release its exact Owner reservation");
    f.app->tick(); const auto query=f.query();
    codec::ProjectionQuery resolved;
    check(codec::decode_projection_query(query.work.payload,resolved) && f.live && resolved.mapping_id==f.live->mapping_id,
          "accepted editor head skipped checked mapping-resolution query4");
    f.finish_query(query,true); f.app->tick();
    const auto pending=f.peek_editor();
    check(pending && pending->work.kind==EngineEditorWorkKind::observation && pending->work.operation==BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1,
          "resolved accepted head did not stage native observation8");
    codec::NativeRequestEnvelope request;
    check(codec::decode_native_request(pending->work.payload,request) && request.request.packet==captured && request.target==wire_target(pending->work),
          "App borrowed or restamped captured editor Packet");
    auto projection=request.request.resolved;
    ++projection.editor_revision; projection.surrounding="AXB"; projection.selection={2,2}; projection.caret={40,24,1,18};
    ne::NativeResult result;
    result.outcome=ne::Outcome::applied; result.continuity=ne::Continuity::same; result.availability=ne::NativeAvailability::available;
    result.observation_revision=++f.sample; result.readback_identity=projection.identity; result.readback_attested=true;
    result.retire=projection.retire; result.projection=projection;
    Bytes encoded;
    check(codec::encode_native_result({request.target,result},encoded),"fixture native8 readback is malformed");
    auto frame2=frame(1); frame2[48]=0x52;
    ok(call(*f.owner,FOUNDATION_ENGINE_FRAME_COMMIT,f.owner->identity(),frame2));
    check(f.owner->frame() && f.owner->frame()->frame_revision==2,"native8 fixture did not commit actual Frame2");
    bitmap(f.app->view(),1,0x29); bitmap(f.adapter.snapshot(),1,0x29);
    f.finish_editor(*pending,encoded,1);
    f.live=projection;
    check(!f.app->editor_take(*head),"copied native8 result escaped before checked App publication");
    const ne::Settlement settlement{captured.session,captured.observation.id,captured.basis.token,captured.observation.predecessor};
    bool saw_settlement=false, completion_escaped=false, work_escaped=false;
    f.port->during_publication=[&](const PolicyPort::Commit& candidate) {
        if (!candidate.editor || !candidate.editor->settlement) return;
        check(candidate.editor->settlement==std::optional{settlement} && candidate.editor->basis &&
              candidate.editor->basis->surrounding=="AXB" && candidate.revision==f.adapter.snapshot().revision,
              "native8 publication lost the exact completed head settlement");
        bitmap(f.adapter.snapshot(),2,0x52);
        saw_settlement=true;
        completion_escaped=f.app->editor_take(*head).has_value();
        f.app->tick();
        work_escaped=f.peek_editor().has_value() || f.peek_physical().has_value();
    };
    f.app->tick(); f.port->during_publication={};
    check(saw_settlement && !completion_escaped && !work_escaped,"completion or native entry escaped inside atomic editor publication");
    bitmap(f.app->view(),2,0x52); bitmap(f.adapter.snapshot(),2,0x52);
    const auto completed_pair=f.port->committed; const auto completed_basis=f.basis();
    const auto commit_count=f.port->commits.size();
    auto frame3=frame(2); frame3[48]=0x73;
    ok(call(*f.owner,FOUNDATION_ENGINE_FRAME_COMMIT,f.owner->identity(),frame3));
    check(f.owner->frame() && f.owner->frame()->frame_revision==3,"completed head fixture did not commit actual Frame3");
    ne::Packet following;
    following.session=captured.session; following.basis=completed_basis;
    following.observation.id=captured.observation.id+1; following.observation.predecessor=captured.observation.id;
    following.observation.kind=ne::Kind::text; following.observation.authority=ne::Authority::range;
    following.observation.before={"AXB",2,2,ne::Direction::none,{2,2},3};
    following.observation.after=ne::TextObservation{"AXZB",3,3,ne::Direction::none,{3,3},4};
    following.observation.data=ne::TextData{"insertText","Z",{2,2},{}};
    check(ne::valid_observation(following.observation),"completed head fixture queued an invalid successor observation");
    const auto next_head=f.app->editor_submit(following);
    check(next_head && *next_head!=*head && !f.app->editor_take(*next_head),"completed head rejected or completed its queued successor inline");
    gui_surface::MouseTransition mouse;
    mouse.phase=gui_surface::MousePhase::down; mouse.capture_token=large+819; mouse.buttons=1; mouse.x=20; mouse.y=30;
    check(f.send(mouse)==gui_surface::Status::ok,"completed head fixture could not queue actual physical mouse ingress");
    const auto unchanged_head=[&] {
        check(f.port->committed.revision==completed_pair.revision && f.port->committed.surface==completed_pair.surface &&
              f.port->committed.editor==completed_pair.editor && f.port->committed.composition==completed_pair.composition &&
              f.port->commits.size()==commit_count && f.basis()==completed_basis &&
              f.app->view().revision==completed_pair.revision && f.adapter.snapshot().revision==completed_pair.revision &&
              !f.peek_editor() && !f.peek_physical() && !f.app->editor_take(*next_head),
              "untaken completed head lost its exact publication or allowed successor editor/physical entry");
        bitmap(f.app->view(),2,0x52); bitmap(f.adapter.snapshot(),2,0x52);
    };
    for (unsigned retry=0;retry<2;++retry) { f.app->retry_presentation(); unchanged_head(); }
    const auto completion=f.app->editor_take(*head);
    check(completion && completion->ticket==*head && completion->result.admission==ne::Admission::completed && completion->result.receipt,
          "checked publication did not release exact accepted completion");
    const auto& receipt=*completion->result.receipt;
    check(receipt.session==captured.session && receipt.id==captured.observation.id && receipt.submitted_token==captured.basis.token &&
          receipt.predecessor==captured.observation.predecessor && receipt.outcome==ne::Outcome::applied && receipt.basis &&
          *receipt.basis==completed_basis && receipt.basis->surrounding=="AXB" && receipt.basis->selection==gui_surface::ByteRange{2,2} &&
          f.port->committed.editor && f.port->committed.editor->settlement==std::optional{settlement} &&
          f.basis().token==receipt.basis->token && !f.app->editor_take(*head) && !f.peek_editor() && !f.peek_physical(),
          "editor receipt lost causal settlement or became repeatable native work");
    unchanged_head(); // Taking metadata itself cannot collect the later actual frame.
    f.app->tick();
    bitmap(f.app->view(),3,0x73); bitmap(f.adapter.snapshot(),3,0x73);
}
void callbacks_resync_and_revocation_only_queue() {
    Fixture f; f.activate();
    ok(call(*f.owner,FOUNDATION_ENGINE_TURN_ENTER,f.owner->identity()));
    f.app->editor_resync();
    f.app->tick();
    check(f.owner->callback_depth()==1,"resync callback changed actual native turn depth");
    ok(call(*f.owner,FOUNDATION_ENGINE_TURN_LEAVE,f.owner->identity()));
    check(!f.peek_editor() && !f.peek_physical(),"resync callback staged Owner work before return");
    f.app->tick();
    const auto resync_cleanup=f.peek_editor();
    check(resync_cleanup && resync_cleanup->work.kind==EngineEditorWorkKind::revoke,
          "resync discarded known provider authority instead of retiring it before rediscovery");
    f.finish_revoke(*resync_cleanup); f.app->tick();
    f.finish_query(f.query(),true); f.app->tick();
    ne::Revocation revoke; revoke.basis=f.basis(); revoke.incarnation=large+901; revoke.reason="fixture focus owner retired";
    ok(call(*f.owner,FOUNDATION_ENGINE_TURN_ENTER,f.owner->identity()));
    const auto head=f.app->editor_revoke(std::move(revoke));
    check(head && !f.app->editor_take(*head),"revocation ingress fabricated a receipt");
    f.app->tick();
    check(f.owner->callback_depth()==1,"resync/revocation entered or left native turn");
    ok(call(*f.owner,FOUNDATION_ENGINE_TURN_LEAVE,f.owner->identity()));
    check(!f.peek_editor() && !f.peek_physical(),"resync/revocation callback staged Owner work before return");
    f.app->tick(); const auto query=f.query();
    f.finish_query(query,true); f.app->tick();
    const auto pending=f.peek_editor();
    check(pending && pending->work.kind==EngineEditorWorkKind::revoke && pending->work.operation==BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1,
          "checked revocation did not stage native9 after its query");
    f.finish_revoke(*pending); f.app->tick();
    const auto completion=f.app->editor_take(*head);
    check(completion && completion->result.admission==ne::Admission::completed && !completion->result.receipt &&
          !f.port->editable() && !f.app->editor_take(*head),"native9 invented observation Receipt or retained old editor authority");
}
Bytes service_request(EngineIdentity target,std::uint64_t sequence,std::uint64_t handle,std::uint32_t operation,Span payload) {
    Envelope header; header.generation=target.service_generation; header.sequence=sequence;
    header.interface_handle=handle; header.operation=operation;
    Bytes result;
    check(encode_envelope(header,payload,result)==CodecStatus::ok,"fixture service envelope is invalid");
    return result;
}
Bytes collect_service(Fixture& f,std::uint64_t sequence) {
    const auto target=f.owner->identity();
    const auto delivery=call(*f.owner,FOUNDATION_ENGINE_PEEK_DELIVERY,target); ok(delivery);
    Envelope header; Span payload;
    check(decode_envelope(delivery.body(),header,payload)==CodecStatus::ok && header.sequence==sequence && header.service_status==0,
          "actual Registry completion changed service correlation/status");
    Bytes result(payload.begin(),payload.end());
    const auto accepted=encode_u32(FOUNDATION_ENGINE_ACCEPTED);
    ok(call(*f.owner,FOUNDATION_ENGINE_DELIVERY_RESULT,target,accepted,delivery.transfer));
    const auto staged=call(*f.owner,FOUNDATION_ENGINE_STAGE_ACK,target,encode_u64(sequence));
    check(staged.control==FOUNDATION_ENGINE_OK && staged.service==static_cast<std::uint32_t>(ServiceStatus::unavailable),
          "actual Registry ACK did not stage its owned barrier");
    ok(call(*f.owner,FOUNDATION_ENGINE_PUMP_ONE,target));
    const auto receipt=call(*f.owner,FOUNDATION_ENGINE_PEEK_ACK_RECEIPT,target); ok(receipt);
    check(get(receipt.body(),0,8)==sequence,"actual Registry ACK receipt changed prefix");
    ok(call(*f.owner,FOUNDATION_ENGINE_ACK_RECEIPT_RESULT,target,accepted,receipt.transfer));
    return result;
}
Bytes native_effect_cycle(Fixture& f,std::uint64_t sequence,std::uint64_t handle,std::uint32_t operation,Span payload) {
    const auto target=f.owner->identity();
    const auto old=f.basis();
    const auto prior_effects=f.native_effects, prior_retirements=f.native_retirements;
    ok(call(*f.owner,FOUNDATION_ENGINE_SUBMIT,target,service_request(target,sequence,handle,operation,payload)));
    const auto gate=call(*f.owner,FOUNDATION_ENGINE_PUMP_ONE,target);
    check(gate.control==FOUNDATION_ENGINE_CONFLICT && gate.service==static_cast<std::uint32_t>(ServiceStatus::unavailable) &&
          f.owner->native_effect() && f.native_effects==prior_effects,"native Registry effect bypassed editor redaction gate");
    f.app->tick();
    check(f.port->service && !f.port->editable() && !f.port->available() && f.adapter.snapshot().widgets.empty() && !f.peek_physical(),
          "native suspension retained pixels, editor admission or premature physical retirement");
    const auto cleanup=f.peek_editor();
    check(cleanup && cleanup->work.kind==EngineEditorWorkKind::revoke,"native effect failed to retain actual editor9 cleanup");
    f.finish_revoke(*cleanup);
    check(f.native_retirements==prior_retirements+1 && f.last_retired_material && f.last_retired_material->input_context==old.identity.context,
          "native effect retired unrelated editor material");
    check(call(*f.owner,FOUNDATION_ENGINE_PUMP_ONE,target).control==FOUNDATION_ENGINE_CONFLICT && f.native_effects==prior_effects,
          "unpublished native9 result acknowledged actual native effect");
    f.app->tick();
    const auto retire=f.consume_physical(); input::Focus retired;
    check(retire.operation==3 && input::decode_focus(retire.payload,retired)==input::Status::ok && retired.action==2 &&
          retired.expected_context==old.identity.context,"physical authority retired before or apart from exact editor9");
    check(f.native_effects==prior_effects,"physical retirement collection synchronously invoked Registry");
    f.app->tick();
    ok(call(*f.owner,FOUNDATION_ENGINE_PUMP_ONE,target));
    const auto result=collect_service(f,sequence);
    f.app->tick();
    if (f.hold_on_entry) {
        check(f.held_ticket && f.owner->native_effect() && f.port->service && !f.port->available() && !f.peek_editor() && !f.peek_physical(),
              "known native reply released its independent UI hold");
        // A real frame during the hold cannot become the post-release rearm frame.
        ok(call(*f.owner,FOUNDATION_ENGINE_FRAME_COMMIT,target,frame(f.owner->frame()->frame_revision)));
        f.app->tick();
        check(f.adapter.snapshot().widgets.empty() && !f.port->available(),"held native UI exposed an in-hold actual frame");
        check(f.owner->release_native_effect(f.held_ticket),"trusted UI release lost its exact held native ticket");
        f.app->tick();
    }
    const auto floor=f.owner->frame()->frame_revision;
    f.app->tick();
    check(!f.port->available() && f.adapter.snapshot().widgets.empty() && !f.peek_editor() && !f.peek_physical(),
          "release reused the old actual frame or invented a bind/editor query");
    ok(call(*f.owner,FOUNDATION_ENGINE_FRAME_COMMIT,target,frame(floor)));
    f.app->tick();
    const auto bind=f.consume_physical(); input::Focus context;
    check(bind.operation==3 && input::decode_focus(bind.payload,context)==input::Status::ok && context.action==1 &&
          context.input_context>old.identity.context,"post-effect frame reused retired physical context");
    f.app->tick();
    check(!f.port->available(),"post-effect bind opened authority before fresh q4");
    f.finish_query(f.query(),true); f.app->tick();
    check(f.port->editable() && f.basis().identity.context==context.input_context && f.basis().token!=old.token &&
          f.owner->frame()->frame_revision==floor+1,"fresh rearm lost its actual frame/context/editor join");
    return result;
}
void actual_registry_effect_retires_editor_before_physical_context() {
    Fixture f(true,true); f.activate();
    const auto major=encode_u32(1),minor=encode_u32(0);
    const std::array<FieldView,4> fields{{{1,FieldType::utf8,true,bytes(Fixture::service_name)},
        {2,FieldType::u32,true,major},{3,FieldType::u32,true,minor},{4,FieldType::u32,true,minor}}};
    Bytes query;
    check(encode_record(fields,query)==CodecStatus::ok,"actual Registry discovery payload is malformed");
    const auto descriptor=native_effect_cycle(f,1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER,query);
    std::vector<FieldView> decoded; std::uint64_t handle{};
    check(decode_record(descriptor,decoded)==CodecStatus::ok && !decoded.empty() && read_u64(decoded.front(),handle) && handle &&
          f.native_effects==0,"actual Registry discovery did not produce its opaque service handle");
    f.hold_on_entry=true;
    const auto value=encode_u32(73);
    check(native_effect_cycle(f,2,handle,1,value)==value && f.native_effects==1 && f.native_retirements==2,
          "actual Registry handler was replayed or lacked exact editor retirement");
}
// The private Owner ticket is deliberately absent from copied PEEK30. Probe only
// this fixture's bounded issued space, then join all captured transport fields;
// request_sequence/transfer are never reinterpreted as an Owner ticket.
std::shared_ptr<const EngineEditorCompletion> owner_completion(Fixture& f,const EngineEditorDispatch& dispatch) {
    std::shared_ptr<const EngineEditorCompletion> result;
    for (EngineEditorTicket ticket=1;ticket<=64;++ticket) {
        const auto candidate=f.owner->editor_outcome(ticket);
        if (!candidate || candidate->ticket!=ticket || candidate->target!=dispatch.work.target ||
            candidate->transfer!=dispatch.transfer || candidate->request_sequence!=dispatch.work.request_sequence ||
            candidate->kind!=dispatch.work.kind) continue;
        check(!result,"multiple Owner outcomes matched one exact copied editor transfer");
        result=candidate;
    }
    check(result!=nullptr,"copied editor transfer has no uniquely correlated retained Owner outcome");
    return result;
}
struct ObservationHead {
    std::uint64_t head{};
    ne::Packet packet;
    EngineEditorDispatch dispatch;
    codec::NativeRequestEnvelope request;
};
ObservationHead prepare_observation(Fixture& f) {
    ObservationHead result;
    result.packet=text_packet(f.basis());
    const auto head=f.app->editor_submit(result.packet);
    check(head.has_value(),"terminal fixture could not retain its actual editor head"); result.head=*head;
    f.app->tick(); f.finish_query(f.query(),true); f.app->tick();
    const auto pending=f.peek_editor();
    check(pending && pending->work.kind==EngineEditorWorkKind::observation &&
          pending->work.operation==BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1,
          "terminal fixture did not resolve its actual native8 work");
    result.dispatch=*pending;
    check(codec::decode_native_request(result.dispatch.work.payload,result.request) && result.request.request.packet==result.packet,
          "terminal fixture lost its original accepted Packet");
    return result;
}
Bytes applied_observation_reply(Fixture& f,const ObservationHead& head) {
    auto projection=head.request.request.resolved;
    ++projection.editor_revision; projection.surrounding="AXB"; projection.selection={2,2}; projection.caret={40,24,1,18};
    ne::NativeResult result;
    result.outcome=ne::Outcome::applied; result.continuity=ne::Continuity::same;
    result.availability=ne::NativeAvailability::available; result.observation_revision=++f.sample;
    result.readback_identity=projection.identity; result.readback_attested=true;
    result.retire=projection.retire; result.projection=projection;
    Bytes encoded;
    check(codec::encode_native_result({head.request.target,result},encoded),"terminal fixture native8 reply is malformed");
    return encoded;
}
void terminal_redaction_is_observable(Fixture& f,std::optional<std::uint64_t> head={}) {
    check(!f.owner->editor_enabled() && !f.owner->input_enabled() && f.owner->callback_depth()==0 &&
          f.app->view().widgets.empty() && f.adapter.snapshot().widgets.empty() && f.adapter.closed() &&
          !f.app->presentation_pending() && !f.port->available() && !f.port->editable() &&
          f.native_effects==0 && f.native_retirements==0,
          "terminal editor App retained pixels/admission/presentation debt or attempted native cleanup");
    if (head) {
        const auto completion=f.app->editor_take(*head);
        check(!completion || (completion->result.admission==ne::Admission::terminal &&
              (!completion->result.receipt || completion->result.receipt->outcome==ne::Outcome::unknown)),
              "terminal editor App released a known successful frontend receipt");
    }
    const auto target=f.owner->identity();
    check(call(*f.owner,FOUNDATION_ENGINE_PEEK_EDITOR_WORK,target).control==FOUNDATION_ENGINE_CLOSED &&
          call(*f.owner,FOUNDATION_ENGINE_PEEK_INPUT,target).control==FOUNDATION_ENGINE_CLOSED,
          "terminal App admitted editor9 or physical replay work");
    f.app->editor_resync(); f.app->tick(); f.app->retry_presentation();
    check(f.app->view().widgets.empty() && f.adapter.snapshot().widgets.empty() && !f.app->presentation_pending() &&
          f.native_effects==0 && f.native_retirements==0,"later terminal callbacks reopened or repumped editor authority");
}
void actual_unknown_observation_retains_opaque_owner_evidence() {
    Fixture f; f.activate(); const auto head=prepare_observation(f);
    const Bytes forensic{0xff,0,0x91,0x80,0x45}; // Opaque provider bytes, deliberately not an editor semantic record.
    f.finish_editor(head.dispatch,forensic,2,0,0,true);
    const auto retained=owner_completion(f,head.dispatch);
    check(retained->outcome==EngineEditorOutcome::unknown && retained->provider_status==0 &&
          retained->provider_disposition==2 && retained->handled && retained->semantic_revision==0 && retained->bytes==forensic,
          "actual unknown native8 changed its original opaque provider outcome");
    f.app->tick(); terminal_redaction_is_observable(f,head.head);
    check(f.owner->editor_outcome(retained->ticket)==retained && retained->bytes==forensic &&
          !f.owner->consume_editor_outcome(retained->ticket),"terminal App decoded, discarded or collected unknown Owner forensics");
}
void consumed_observation_publication_throw_is_terminal(bool after_install) {
    Fixture f; f.activate(); const auto head=prepare_observation(f);
    const auto encoded=applied_observation_reply(f,head);
    f.finish_editor(head.dispatch,encoded,1);
    const auto retained=owner_completion(f,head.dispatch);
    check(retained->outcome==EngineEditorOutcome::consumed && retained->provider_status==0 &&
          retained->provider_disposition==1 && retained->bytes==encoded,"publication fault fixture lacks consumed native8 proof");
    f.adapter.throw_before_next=!after_install; f.adapter.throw_after_next=after_install;
    f.app->tick();
    check(f.adapter.publication_faults==1,"consumed native8 publication fault was not exercised exactly once");
    terminal_redaction_is_observable(f,head.head);
    check(f.owner->editor_outcome(retained->ticket)==retained && retained->outcome==EngineEditorOutcome::consumed &&
          retained->bytes==encoded,"publication failure rewrote or lost the actual consumed Owner evidence");
}
void explicit_owner_terminal_notification_redacts_and_stops() {
    Fixture f; f.activate();
    check(f.port->editable() && !f.adapter.snapshot().widgets.empty(),"terminal notification fixture has no actual editor publication");
    const auto packet=text_packet(f.basis());
    // This atomic terminal notification is the actual trigger. Ordinary close
    // would request a different, gracefully draining native retirement protocol.
    f.owner->notify_document_terminal();
    f.app->tick(); terminal_redaction_is_observable(f);
    check(!f.app->editor_submit(packet),"terminal Owner notification admitted a new editor head");
}
void unclaimed_head_query_cancellation_settles_native9_before_effect() {
    Fixture f(true,true); f.activate();
    const auto major=encode_u32(1),minor=encode_u32(0);
    const std::array<FieldView,4> fields{{{1,FieldType::utf8,true,bytes(Fixture::service_name)},
        {2,FieldType::u32,true,major},{3,FieldType::u32,true,minor},{4,FieldType::u32,true,minor}}};
    Bytes discovery;
    check(encode_record(fields,discovery)==CodecStatus::ok,"cancellation fixture discovery is malformed");
    const auto descriptor=native_effect_cycle(f,1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER,discovery);
    std::vector<FieldView> decoded; std::uint64_t handle{};
    check(decode_record(descriptor,decoded)==CodecStatus::ok && !decoded.empty() && read_u64(decoded.front(),handle) && handle,
          "cancellation fixture did not discover its actual Registry handle");
    const auto old=f.basis(); const auto old_projection=*f.live;
    const auto packet=text_packet(old); const auto head=f.app->editor_submit(packet);
    check(head.has_value(),"cancellation fixture could not retain its browser head");
    f.app->tick(); const auto cancelled=f.query(); // PEEK only: no BEGIN, TURN, RESULT or synthesized native cancellation.
    const auto baseline=f.native_retirements;
    const auto target=f.owner->identity(); const auto value=encode_u32(83);
    ok(call(*f.owner,FOUNDATION_ENGINE_SUBMIT,target,service_request(target,2,handle,1,value)));
    const auto gate=call(*f.owner,FOUNDATION_ENGINE_PUMP_ONE,target);
    check(gate.control==FOUNDATION_ENGINE_CONFLICT && gate.service==static_cast<std::uint32_t>(ServiceStatus::unavailable) &&
          f.owner->native_effect() && !f.owner->native_effect()->entered && f.native_effects==0 && !f.app->editor_take(*head),
          "actual PUMP did not defer native service behind unclaimed head cancellation");
    const auto cancelled_outcome=owner_completion(f,cancelled);
    check(cancelled_outcome->outcome==EngineEditorOutcome::cancelled && cancelled_outcome->provider_status==0 &&
          cancelled_outcome->provider_disposition==0 && !cancelled_outcome->handled && cancelled_outcome->semantic_revision==0 &&
          cancelled_outcome->bytes.empty(),"Owner cancellation fabricated a provider q4 return");
    f.app->tick();
    check(f.adapter.snapshot().widgets.empty() && !f.port->available() && !f.peek_physical() && !f.app->editor_take(*head),
          "cancel_unentered released the frontend head or physical authority before native cleanup");
    const auto cleanup=f.peek_editor(); codec::RevocationEnvelope revoke;
    check(cleanup && cleanup->work.kind==EngineEditorWorkKind::revoke && cleanup->transfer!=cancelled.transfer &&
          cleanup->work.request_sequence>cancelled.work.request_sequence &&
          codec::decode_revocation(cleanup->work.payload,revoke) && revoke.request.material==*old_projection.retire &&
          revoke.request.identity==old_projection.identity,"cancelled q4 substituted its uncommitted identity for actual old retirement authority");
    f.finish_revoke(*cleanup);
    check(!f.app->editor_take(*head) && call(*f.owner,FOUNDATION_ENGINE_PUMP_ONE,target).control==FOUNDATION_ENGINE_CONFLICT,
          "native9 result released cancellation/effect before checked publication");
    bool published=false, escaped=false;
    f.port->during_publication=[&](const PolicyPort::Commit& candidate) {
        if (!candidate.editor || !candidate.editor->settlement) return;
        const ne::Settlement exact{packet.session,packet.observation.id,packet.basis.token,packet.observation.predecessor};
        if (candidate.editor->settlement==std::optional{exact} && !candidate.editor->basis && candidate.editor->retirement &&
            candidate.editor->retirement->authority_retired) published=true;
        escaped=f.app->editor_take(*head).has_value();
    };
    f.app->tick(); f.port->during_publication={};
    check(published && !escaped,"cancelled Receipt escaped its checked native9 settlement publication");
    const auto physical=f.consume_physical(); input::Focus focus;
    check(physical.operation==3 && input::decode_focus(physical.payload,focus)==input::Status::ok && focus.action==2 &&
          focus.expected_context==old.identity.context && f.native_retirements==baseline+1,
          "cancelled head did not settle exact editor9 before physical retirement");
    f.app->tick();
    ok(call(*f.owner,FOUNDATION_ENGINE_PUMP_ONE,target));
    check(f.native_effects==1,"native effect ACK incorrectly waited for frontend completion take");
    check(collect_service(f,2)==value,"actual cancellation-following Registry handler lost its service outcome");
    const auto completion=f.app->editor_take(*head);
    check(completion && completion->result.admission==ne::Admission::completed && completion->result.receipt,
          "checked cancelled editor head lost its one completion");
    const auto& receipt=*completion->result.receipt;
    check(receipt.session==packet.session && receipt.id==packet.observation.id && receipt.submitted_token==packet.basis.token &&
          receipt.predecessor==packet.observation.predecessor && receipt.outcome==ne::Outcome::cancelled &&
          receipt.continuity==ne::Continuity::replaced && !receipt.basis && !receipt.default_token && receipt.retirement &&
          receipt.retirement->authority_retired && receipt.retirement->readback_attested && !f.app->editor_take(*head),
          "cancelled q4 manufactured success or lost exact native9 retirement proof");
}
void consumed_body_key_owns_only_its_real_matching_release() {
    Fixture f; f.activate(false); f.focus_null();
    const auto target=f.owner->identity(); const auto context=f.port->committed.surface->identity.context;
    const gui_surface::KeyTransition down{gui_surface::KeyPhase::down,"A","KeyA",0,1,false};
    auto up=down; up.phase=gui_surface::KeyPhase::up; up.key="a"; up.modifiers=0;
    const auto frame_revision=f.owner->frame()->frame_revision;
    const auto reservation=f.owner->reserve_editor_sequence();
    check(reservation.has_value(),"checked body fixture could not hold the actual Owner editor reservation");
    check(f.send(down)==gui_surface::Status::ok,"checked body fallback rejected actual keydown");
    check(f.send(up)==gui_surface::Status::ok,"actual UP could not queue behind its busy retained DOWN");
    for (unsigned retry=0;retry<2;++retry) {
        f.app->tick();
        const auto blocked_input=call(*f.owner,FOUNDATION_ENGINE_PEEK_INPUT,target);
        const auto blocked_editor=call(*f.owner,FOUNDATION_ENGINE_PEEK_EDITOR_WORK,target);
        check(blocked_input.control==FOUNDATION_ENGINE_EMPTY && blocked_editor.control==FOUNDATION_ENGINE_EMPTY &&
              f.owner->callback_depth()==0 && f.owner->identity()==target && f.owner->frame() &&
              f.owner->frame()->frame_revision==frame_revision && f.owner->input_enabled() && f.owner->editor_enabled() &&
              f.port->available() && !f.port->editable() && f.port->policy.focused() && !f.native_effects && !f.native_retirements,
              "busy Owner reservation admitted input/editor work or invalidated the checked body before retry");
    }
    check(f.owner->cancel_editor_sequence(*reservation),"busy probe could not cancel its exact held editor sequence");
    f.app->tick();
    const auto pending_down=call(*f.owner,FOUNDATION_ENGINE_PEEK_INPUT,target); ok(pending_down);
    input::Command down_command; input::Key down_value;
    const input::Key exact_down{0,down.location,down.modifiers,down.repeat?1u:0u,context,down.key,down.code};
    check(input::decode_command(pending_down.body(),down_command)==input::Status::ok && down_command.operation==1 &&
          down_command.schema_sha256==input::kKeySchema && down_command.request_sequence>*reservation &&
          input::decode_key(down_command.payload,down_value)==input::Status::ok && down_value==exact_down &&
          pending_down.target==target,"busy retry lost the original body DOWN or exact full transport/context");
    f.app->tick();
    check(call(*f.owner,FOUNDATION_ENGINE_PEEK_INPUT,target).record==pending_down.record && !f.peek_editor(),
          "queued body UP overtook or replaced its unconsumed DOWN");
    f.consume_physical(); f.app->tick(); const auto refresh=f.query();
    check(!f.peek_physical(),"body UP entered before its DOWN outcome and pending q4 settled");
    const gui_surface::KeyTransition blocked_down{gui_surface::KeyPhase::down,"b","KeyB",0,0,false};
    check(f.send(blocked_down)==gui_surface::Status::ok,"physical guard lost focus instead of testing pending body admission");
    f.app->tick();
    check(!f.peek_physical() && f.query().work.payload==refresh.work.payload,"new body DOWN entered during inert projection refresh");
    const auto projected=f.finish_query(refresh,true); const auto commit_begin=f.port->commits.size();
    std::optional<PolicyPort::Commit> discovered;
    std::optional<ne::NativeRetireMaterial> material;
    f.port->during_publication=[&](const PolicyPort::Commit& candidate) {
        if (!candidate.editor || !candidate.editor->basis) return;
        check(!discovered,"one inert body query published multiple editor discoveries");
        const auto& basis=*candidate.editor->basis;
        check(candidate.surface && candidate.surface->available && candidate.surface->editor && ne::valid_basis(basis) &&
              basis.identity==projected.identity && basis.identity.context==context && basis.editor_revision==projected.editor_revision &&
              basis.surrounding==projected.surrounding && basis.selection==projected.selection && basis.backward==projected.backward &&
              basis.composition==projected.composition && candidate.surface->editor->caret==projected.caret && projected.retire &&
              f.live && f.live->retire==projected.retire && f.owner->identity()==target && !f.peek_physical() && !f.peek_editor(),
              "body DOWN did not publish exact checked editor discovery before its real owned UP could stage");
        discovered=candidate; material=f.live->retire;
    };
    f.app->tick(); f.port->during_publication={};
    check(discovered && material,"body DOWN focus effect did not discover the actual editor");
    std::size_t committed_discoveries{};
    for (std::size_t index=commit_begin;index<f.port->commits.size();++index) {
        const auto& committed=f.port->commits[index];
        if (committed.revision==discovered->revision && committed.surface==discovered->surface &&
            committed.editor==discovered->editor && committed.composition==discovered->composition) ++committed_discoveries;
    }
    check(committed_discoveries==1 && f.port->committed.revision>discovered->revision &&
          f.port->available() && f.port->policy.focused() && !f.port->editable() && !f.port->committed.editor &&
          f.port->committed.surface && f.port->committed.surface->identity.context==context &&
          !f.port->committed.surface->editor && !f.peek_editor(),
          "real owned UP did not retain the focused physical context behind its checked discovery and pending editor refresh");
    const auto basis=*discovered->editor->basis;
    const auto pending_up=call(*f.owner,FOUNDATION_ENGINE_PEEK_INPUT,target); ok(pending_up);
    input::Command up_command; input::Key up_value;
    const input::Key exact_up{1,up.location,up.modifiers,up.repeat?1u:0u,context,up.key,up.code};
    check(input::decode_command(pending_up.body(),up_command)==input::Status::ok && up_command.operation==1 &&
          up_command.schema_sha256==input::kKeySchema &&
          input::decode_key(up_command.payload,up_value)==input::Status::ok && up_value==exact_up &&
          pending_up.target==target && pending_up.transfer!=pending_down.transfer &&
          up_command.request_sequence>down_command.request_sequence,
          "editor activation lost physical-code ownership or restamped the actual key UP value/modifiers");
    auto unmatched_up=blocked_down; unmatched_up.phase=gui_surface::KeyPhase::up;
    check(f.send(unmatched_up)==gui_surface::Status::ok,"unmatched native UP did not reach the App ownership backstop");
    const gui_surface::KeyTransition editor_down{gui_surface::KeyPhase::down,"c","KeyC",0,0,false};
    auto editor_up=editor_down; editor_up.phase=gui_surface::KeyPhase::up;
    check(f.send(editor_down)==gui_surface::Status::ok && f.send(editor_up)==gui_surface::Status::ok,
          "editor-state physical key controls did not reach the App backstop");
    f.app->tick();
    check(call(*f.owner,FOUNDATION_ENGINE_PEEK_INPUT,target).record==pending_up.record && !f.peek_editor(),
          "unowned UP or new editor-state DOWN replaced the sole owned real UP");
    f.consume_physical(); f.app->tick();
    check(!f.peek_physical(),"matching body UP replayed instead of entering exactly once");
    f.finish_query(f.query(),true); f.app->tick();
    check(f.port->editable() && f.basis().token==basis.token && f.live->retire==material && f.native_retirements==0 && !f.peek_physical(),
          "real body UP caused native9 or reminted an unchanged editor authority");
    check(f.send(up)!=gui_surface::Status::ok,"duplicate native UP resurrected released physical ownership");
    f.app->tick(); check(!f.peek_physical(),"duplicate native UP entered the raw body route again");

    // Return to a genuinely checked noneditable body without abandoning the
    // editor lease. This is an explicit resync, not an inert physical refresh.
    f.app->editor_resync(); f.app->tick();
    const auto editor_cleanup=f.peek_editor();
    check(editor_cleanup && editor_cleanup->work.kind==EngineEditorWorkKind::revoke,
          "body replacement fixture discarded its live native editor lease");
    f.finish_revoke(*editor_cleanup); f.app->tick(); f.finish_query(f.query(),false); f.app->tick(); f.focus_null();
    const auto original_identity=f.policy_identity(); const auto alias_target=f.owner->identity();
    const auto alias_retirements=f.native_retirements;
    check(original_identity.has_value(),"delayed real UP fixture lacks its original physical DOWN identity");
    const gui_surface::KeyTransition delayed_down{gui_surface::KeyPhase::down,"L","KeyL",0,1,false};
    auto delayed_up=delayed_down; delayed_up.phase=gui_surface::KeyPhase::up; delayed_up.key="l"; delayed_up.modifiers=0;
    check(f.send(delayed_down)==gui_surface::Status::ok && !f.peek_physical() && !f.peek_editor(),
          "delayed DOWN callback failed actual Policy admission or entered the provider synchronously");
    f.app->tick();
    const auto delayed_down_envelope=call(*f.owner,FOUNDATION_ENGINE_PEEK_INPUT,alias_target); ok(delayed_down_envelope);
    const auto delayed_command=f.consume_physical(); input::Key delayed_value;
    const input::Key exact_delayed_down{0,delayed_down.location,delayed_down.modifiers,0,original_identity->context,delayed_down.key,delayed_down.code};
    check(delayed_down_envelope.target==alias_target && delayed_command.operation==1 && delayed_command.schema_sha256==input::kKeySchema &&
          input::decode_key(delayed_command.payload,delayed_value)==input::Status::ok && delayed_value==exact_delayed_down,
          "delayed real UP fixture did not actually consume its exact original full-target/context DOWN");
    f.app->tick(); f.finish_query(f.query(),false); f.app->tick();
    const auto current_identity=f.policy_identity();
    check(current_identity && current_identity->presentation_revision>original_identity->presentation_revision &&
          current_identity->owner==original_identity->owner && current_identity->generation==original_identity->generation &&
          current_identity->epoch==original_identity->epoch && current_identity->context==original_identity->context &&
          f.port->available() && !f.port->editable() && f.port->policy.focused() && !f.peek_editor() && !f.peek_physical(),
          "delayed real UP fixture did not produce an actual pRevision-only checked-null repaint");
    // Match the trusted Surface adapter: Policy consumes the real held-code UP
    // against its current pair, then App receives the unchanged supplied identity.
    auto accepted_up=f.port->policy.accept({*current_identity,++f.input_sequence,delayed_up});
    check(accepted_up.status==gui_surface::Status::ok && accepted_up.accepted &&
          accepted_up.accepted->event.identity==*current_identity &&
          std::get<gui_surface::KeyTransition>(accepted_up.accepted->event.input)==delayed_up,
          "actual current Policy did not accept the original held code's real delayed UP");
    accepted_up.accepted->event.identity=*original_identity;
    f.app->surface_input(std::move(*accepted_up.accepted));
    check(!f.peek_physical() && !f.peek_editor(),"delayed original-identity UP callback entered the provider synchronously");
    f.app->tick();
    const auto delayed_up_envelope=call(*f.owner,FOUNDATION_ENGINE_PEEK_INPUT,alias_target); ok(delayed_up_envelope);
    input::Command delayed_release; input::Key delayed_release_value;
    const input::Key exact_delayed_up{1,delayed_up.location,delayed_up.modifiers,0,original_identity->context,delayed_up.key,delayed_up.code};
    check(delayed_up_envelope.target==alias_target && delayed_up_envelope.transfer!=delayed_down_envelope.transfer &&
          input::decode_command(delayed_up_envelope.body(),delayed_release)==input::Status::ok && delayed_release.operation==1 &&
          delayed_release.schema_sha256==input::kKeySchema && delayed_release.request_sequence>delayed_command.request_sequence &&
          input::decode_key(delayed_release.payload,delayed_release_value)==input::Status::ok && delayed_release_value==exact_delayed_up,
          "pRevision-only delayed UP lost consumed-DOWN ownership, retargeted context or restamped the real key/modifiers");
    f.app->tick();
    check(call(*f.owner,FOUNDATION_ENGINE_PEEK_INPUT,alias_target).record==delayed_up_envelope.record && !f.peek_editor(),
          "delayed original-identity UP replayed or changed while its one actual command was pending");
    check(f.consume_physical()==delayed_release,"delayed real UP consumption replaced its original immutable command");
    f.app->tick(); f.finish_query(f.query(),false); f.app->tick();
    check(f.owner->identity()==alias_target && f.port->available() && !f.port->editable() && f.port->policy.focused() &&
          f.port->committed.surface->identity.context==original_identity->context && f.native_retirements==alias_retirements &&
          !f.peek_physical() && !f.peek_editor(),"delayed real UP remapped physical ownership or invented native9");
    check(f.send(delayed_up)!=gui_surface::Status::ok,"duplicate delayed real UP resurrected its released physical ownership");
    f.app->tick(); check(!f.peek_physical() && !f.peek_editor(),"duplicate delayed real UP entered a second provider command");
    const gui_surface::KeyTransition replaced_down{gui_surface::KeyPhase::down,"m","KeyM",0,0,false};
    auto replaced_up=replaced_down; replaced_up.phase=gui_surface::KeyPhase::up;
    check(f.send(replaced_down)==gui_surface::Status::ok,"replacement fixture could not accept its body DOWN");
    f.app->tick(); const auto known_down=f.consume_physical();
    check(known_down.operation==1,"replacement fixture did not actually consume body DOWN");
    f.app->tick(); f.finish_query(f.query(),false); f.app->tick();
    const auto prior_target=f.owner->identity(); const auto prior_context=f.port->committed.surface->identity.context;
    auto next=prior_target; ++next.document_sequence; next.service_generation=0;
    const auto begun=call(*f.owner,FOUNDATION_ENGINE_BEGIN_DOCUMENT,next); ok(begun);
    check(f.send(replaced_up)==gui_surface::Status::ok,
          "old Policy did not deliver the real held UP at the document replacement edge");
    f.app->tick();
    check(!f.peek_physical(),"old full-target/context UP was retargeted into a replacement document");
    ok(call(*f.owner,FOUNDATION_ENGINE_FRAME_COMMIT,begun.target,frame(0))); f.app->tick();
    const auto next_bind_envelope=call(*f.owner,FOUNDATION_ENGINE_PEEK_INPUT,begun.target); ok(next_bind_envelope);
    const auto next_bind=f.consume_physical(); input::Focus rebound;
    check(next_bind_envelope.target==begun.target && next_bind.operation==3 &&
          input::decode_focus(next_bind.payload,rebound)==input::Status::ok && rebound.action==1 && rebound.input_context>prior_context,
          "old body UP replaced the new document's fresh physical bind");
    f.app->tick(); f.finish_query(f.query(),false); f.app->tick(); f.focus_null();
    check(!f.peek_physical(),"retired body UP replayed after the new full target/context became available");

    // Finish this process with a known, not-entered rejected DOWN. Its already
    // queued real UP supplies no consumed-DOWN ownership and must be discarded.
    const auto retirements=f.native_retirements;
    const gui_surface::KeyTransition rejected_down{gui_surface::KeyPhase::down,"r","KeyR",0,0,false};
    auto rejected_up=rejected_down; rejected_up.phase=gui_surface::KeyPhase::up;
    check(f.send(rejected_down)==gui_surface::Status::ok && f.send(rejected_up)==gui_surface::Status::ok,
          "known rejection fixture could not queue its real DOWN/UP pair");
    f.app->tick(); const auto rejected=f.consume_physical(-5,0); input::Key rejected_value;
    check(rejected.operation==1 && input::decode_key(rejected.payload,rejected_value)==input::Status::ok &&
          rejected_value.phase==0 && rejected_value.key==rejected_down.key,"known rejection was not the original body DOWN");
    f.app->tick(); f.app->tick();
    const auto after_rejection=call(*f.owner,FOUNDATION_ENGINE_PEEK_INPUT,f.owner->identity());
    check(after_rejection.control!=FOUNDATION_ENGINE_OK && !f.owner->input_enabled() && f.native_retirements==retirements,
          "rejected body DOWN granted ownership for a queued native UP or fabricated cleanup");
}
void navigation_retires_exact_historical_editor_before_new_frame() {
    Fixture f; f.activate();
    const auto old_target=f.owner->identity(); const auto old_basis=f.basis(); const auto old_projection=*f.live;
    auto prospective=old_target; ++prospective.document_sequence; prospective.service_generation=0;
    const auto begun=call(*f.owner,FOUNDATION_ENGINE_BEGIN_DOCUMENT,prospective); ok(begun);
    const auto next_target=begun.target;
    check(f.owner->identity()==next_target && next_target.worker_epoch==old_target.worker_epoch &&
          next_target.application_instance==old_target.application_instance && next_target.document_sequence==prospective.document_sequence &&
          next_target.service_generation && next_target.service_generation!=old_target.service_generation && !f.owner->frame(),
          "actual BEGIN did not issue a fresh authoritative document identity and clear the old frame");
    f.app->tick();
    check(f.app->view().widgets.empty() && f.adapter.snapshot().widgets.empty() && !f.port->available() && !f.port->editable() &&
          !f.peek_physical(),"navigation exposed a successor before retiring its old checked native material");
    const auto cleanup=f.peek_editor(); codec::RevocationEnvelope historical;
    check(cleanup && cleanup->work.kind==EngineEditorWorkKind::revoke && cleanup->work.operation==BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1 &&
          identity(cleanup->work.target)==old_target && codec::decode_revocation(cleanup->work.payload,historical) &&
          historical.target==wire_target(cleanup->work) && historical.request.identity==old_projection.identity &&
          historical.request.material==*old_projection.retire,"historical native9 was rebased to the new target/context/material");
    ok(call(*f.owner,FOUNDATION_ENGINE_FRAME_COMMIT,next_target,frame(0)));
    f.app->tick(); f.app->tick();
    const auto still_pending=f.peek_editor();
    check(f.owner->frame() && f.owner->frame()->identity==next_target && f.owner->frame()->frame_revision==1 &&
          f.app->view().widgets.empty() && f.adapter.snapshot().widgets.empty() && !f.peek_physical() && still_pending &&
          still_pending->transfer==cleanup->transfer && still_pending->work.payload==cleanup->work.payload,
          "precommitted successor frame leaked while historical native9 was pending");
    Bytes wrong_claim(FOUNDATION_ENGINE_EDITOR_BEGIN_BYTES);
    put(wrong_claim,0,static_cast<std::uint32_t>(cleanup->work.kind),4); put(wrong_claim,8,cleanup->work.request_sequence,8);
    check(call(*f.owner,FOUNDATION_ENGINE_BEGIN_EDITOR_WORK,next_target,wrong_claim,cleanup->transfer).control!=FOUNDATION_ENGINE_OK &&
          f.owner->callback_depth()==0,"current document identity claimed the old document's native9 transfer");
    f.finish_revoke(*cleanup); // Claim, TURN_ENTER, TURN_LEAVE and RESULT all preserve OLD full target/transfer.
    check(f.owner->callback_depth()==0 && f.app->view().widgets.empty() && f.adapter.snapshot().widgets.empty() && !f.peek_physical(),
          "historical native9 provider return published a successor before its checked App collection");
    f.app->tick();
    const auto pending=call(*f.owner,FOUNDATION_ENGINE_PEEK_INPUT,next_target); ok(pending);
    const auto bind=f.consume_physical(); input::Focus context;
    check(pending.target==next_target && bind.operation==3 && input::decode_focus(bind.payload,context)==input::Status::ok &&
          context.action==1 && context.input_context>old_basis.identity.context && !f.port->available(),
          "checked historical cleanup did not stage a fresh current-document bind");
    f.app->tick(); const auto query=f.query(); codec::ProjectionQuery discovery;
    check(identity(query.work.target)==next_target && codec::decode_projection_query(query.work.payload,discovery) &&
          discovery.identity.context==context.input_context && discovery.mapping_id==0 &&
          !f.adapter.snapshot().widgets.empty() &&
          discovery.identity.owner.id==f.adapter.snapshot().widgets.front().spec.key.id &&
          discovery.identity.owner.generation==f.adapter.snapshot().widgets.front().spec.key.generation,
          "post-navigation query4 lost its new full target/bitmap/context join");
    f.finish_query(query,true); f.app->tick();
    check(f.port->editable() && f.basis().identity.context==context.input_context && f.basis().token!=old_basis.token && f.live &&
          f.live->retire && f.live->retire->token!=old_projection.retire->token && f.native_retirements==1 &&
          f.owner->frame()->identity==next_target && f.owner->frame()->frame_revision==1,
          "navigation reused old editor authority or required a synthesized extra successor frame");
}
void applied_null_retirement_survives_trusted_redaction() {
    Fixture f; f.activate();
    const auto head=prepare_observation(f);
    const auto old_target=identity(head.dispatch.work.target);
    const auto old_projection=head.request.request.resolved;
    check(old_projection.retire && f.live && f.live->retire==old_projection.retire,
          "applied-null fixture lacks the exact learned native retirement material");
    ne::NativeResult result;
    result.outcome=ne::Outcome::applied; result.continuity=ne::Continuity::replaced;
    result.availability=ne::NativeAvailability::unavailable; result.observation_revision=++f.sample;
    result.readback_identity=old_projection.identity; result.readback_attested=true; result.retired=old_projection.retire;
    Bytes encoded;
    check(codec::encode_native_result({head.request.target,result},encoded),"known applied-null native8 retirement proof was rejected");
    Bytes claim(FOUNDATION_ENGINE_EDITOR_BEGIN_BYTES);
    put(claim,0,static_cast<std::uint32_t>(head.dispatch.work.kind),4); put(claim,8,head.dispatch.work.request_sequence,8);
    ok(call(*f.owner,FOUNDATION_ENGINE_BEGIN_EDITOR_WORK,old_target,claim,head.dispatch.transfer));
    ok(call(*f.owner,FOUNDATION_ENGINE_TURN_ENTER,old_target,{},head.dispatch.transfer));
    auto prospective=old_target; ++prospective.document_sequence; prospective.service_generation=0;
    const auto begun=call(*f.owner,FOUNDATION_ENGINE_BEGIN_DOCUMENT,prospective); ok(begun);
    ok(call(*f.owner,FOUNDATION_ENGINE_FRAME_COMMIT,begun.target,frame(0)));
    check(f.owner->callback_depth()==1 && f.owner->identity()==begun.target && f.owner->frame() &&
          f.owner->frame()->identity==begun.target && f.owner->frame()->frame_revision==1,
          "native8 did not perform actual successor navigation/frame commit inside its original turn");
    ok(call(*f.owner,FOUNDATION_ENGINE_TURN_LEAVE,old_target,{},head.dispatch.transfer));
    Bytes returned(FOUNDATION_ENGINE_EDITOR_RESULT_PREFIX_BYTES+encoded.size());
    put(returned,0,static_cast<std::uint32_t>(head.dispatch.work.kind),4);
    put(returned,8,head.dispatch.work.request_sequence,8); put(returned,20,1,4); put(returned,24,encoded.size(),4);
    std::copy(encoded.begin(),encoded.end(),returned.begin()+FOUNDATION_ENGINE_EDITOR_RESULT_PREFIX_BYTES);
    ok(call(*f.owner,FOUNDATION_ENGINE_EDITOR_WORK_RESULT,old_target,returned,head.dispatch.transfer));
    const auto retained=owner_completion(f,head.dispatch);
    check(retained->outcome==EngineEditorOutcome::consumed && retained->provider_status==0 && retained->provider_disposition==1 &&
          !retained->handled && !retained->semantic_revision && retained->bytes==encoded && f.owner->callback_depth()==0 &&
          !f.app->editor_take(head.head),"actual old-target native8 completion lost its known applied-null proof");
    f.live.reset(); // The actual native8 result already retired this provider authority.
    f.app->set_owned_service_active(true);
    check(f.port->service && !f.port->editable() && !f.peek_editor() && !f.peek_physical(),
          "trusted redaction entered another native operation before collecting actual retired native8 proof");
    const ne::Settlement settlement{head.packet.session,head.packet.observation.id,head.packet.basis.token,head.packet.observation.predecessor};
    const ne::RetirementReadback proof{ne::NativeAvailability::unavailable,old_projection.identity,result.observation_revision,true,true};
    bool checked=false, escaped=false;
    f.port->during_publication=[&](const PolicyPort::Commit& candidate) {
        if (!candidate.editor || candidate.editor->settlement!=std::optional{settlement}) return;
        check(!candidate.surface && !candidate.editor->basis && candidate.editor->retirement==std::optional{proof} &&
              f.adapter.snapshot().widgets.empty() && candidate.revision==f.adapter.snapshot().revision,
              "trusted redaction changed the actual applied-null identity/readback or omitted its checked settlement");
        checked=true; escaped=f.app->editor_take(head.head).has_value();
        f.app->tick();
        check(!f.peek_editor() && !f.peek_physical(),"applied-null settlement publication replayed native8/9 or bound its successor");
    };
    f.app->tick(); f.port->during_publication={};
    check(checked && !escaped && f.app->view().widgets.empty() && f.adapter.snapshot().widgets.empty() &&
          !f.adapter.closed() && f.owner->editor_enabled() && f.owner->input_enabled() && !f.native_retirements && !f.native_effects,
          "known applied-null retirement became terminal, replayed native9 or exposed the successor while held");
    const auto completed_pair=f.port->committed; const auto commit_count=f.port->commits.size();
    for (unsigned retry=0;retry<2;++retry) {
        f.app->retry_presentation();
        check(f.port->committed.revision==completed_pair.revision && f.port->committed.surface==completed_pair.surface &&
              f.port->committed.editor==completed_pair.editor && f.port->committed.composition==completed_pair.composition &&
              f.port->commits.size()==commit_count && f.app->view().widgets.empty() && f.adapter.snapshot().widgets.empty() &&
              !f.peek_editor() && !f.peek_physical() && !f.native_retirements && f.owner->callback_depth()==0,
              "held applied-null completion lost its exact head publication or attempted native cleanup/rebind");
    }
    check(!completed_pair.surface && completed_pair.editor && !completed_pair.editor->basis &&
          completed_pair.editor->settlement==std::optional{settlement} && completed_pair.editor->retirement==std::optional{proof},
          "normal close fixture lacks its original checked applied-null head publication");
    f.app->shutdown(); f.app->tick();
    check(!f.adapter.closed() && !f.owner->closed() && f.owner->callback_depth()==0 &&
          f.port->committed.revision==completed_pair.revision && f.port->committed.surface==completed_pair.surface &&
          f.port->committed.editor==completed_pair.editor && f.port->committed.composition==completed_pair.composition &&
          f.port->commits.size()==commit_count && f.app->view().revision==completed_pair.revision &&
          f.adapter.snapshot().revision==completed_pair.revision && f.app->view().widgets.empty() && f.adapter.snapshot().widgets.empty() &&
          !f.peek_editor() && !f.peek_physical() && !f.native_retirements,
          "normal close erased the untaken known applied-null receipt or its exact checked settlement/proof");
    const auto completion=f.app->editor_take(head.head);
    check(completion && completion->ticket==head.head && completion->result.admission==ne::Admission::completed && completion->result.receipt,
          "trusted retirement withheld or replaced the known applied-null completion");
    const auto& receipt=*completion->result.receipt;
    check(receipt.session==settlement.session && receipt.id==settlement.id && receipt.submitted_token==settlement.submitted_token &&
          receipt.predecessor==settlement.predecessor && receipt.outcome==ne::Outcome::applied &&
          receipt.continuity==ne::Continuity::replaced && !receipt.basis && !receipt.default_token && receipt.retirement==std::optional{proof} &&
          f.port->committed.editor && f.port->committed.editor->settlement==std::optional{settlement} &&
          f.port->committed.editor->retirement==receipt.retirement && !f.app->editor_take(head.head) &&
          retained->outcome==EngineEditorOutcome::consumed && retained->bytes==encoded && !f.peek_editor() && !f.peek_physical() &&
          !f.native_retirements && f.app->view().widgets.empty() && f.adapter.snapshot().widgets.empty(),
          "trusted redaction rewrote the original applied outcome, readback proof or exact causal settlement");
    check(!f.adapter.closed() && !f.owner->closed(),"metadata take closed the normal presenter before its next owner task");
    f.app->tick();
    check(f.adapter.closed() && f.owner->closed() && !f.app->presentation_pending() && f.owner->callback_depth()==0 &&
          !f.native_retirements && !f.app->editor_take(head.head),
          "normal close did not finish honestly after taking its original known applied-null completion");
}
} // namespace

int main(int argc,char** argv) {
    const std::array<std::pair<std::string_view,void(*)()>,14> tests{{
        {"typed admission",typed_admission_and_old_constructor_rejection},
        {"bind before query4",bind_then_query_uses_committed_context},
        {"checked-null mouse refresh",checked_null_mouse_focus_requires_fresh_query},
        {"accepted head and checked publication",accepted_head_resolves_then_publishes_before_take},
        {"callback resync and native9",callbacks_resync_and_revocation_only_queue},
        {"actual Registry editor9 retirement",actual_registry_effect_retires_editor_before_physical_context},
        {"unknown native8 retains opaque evidence",actual_unknown_observation_retains_opaque_owner_evidence},
        {"consumed native8 publication throw before install",+[] { consumed_observation_publication_throw_is_terminal(false); }},
        {"consumed native8 publication throw after install",+[] { consumed_observation_publication_throw_is_terminal(true); }},
        {"explicit Owner terminal notification",explicit_owner_terminal_notification_redacts_and_stops},
        {"unclaimed head q4 native-effect cancellation",unclaimed_head_query_cancellation_settles_native9_before_effect},
        {"consumed body key owns exact real release",consumed_body_key_owns_only_its_real_matching_release},
        {"navigation checks old editor9 before new frame",navigation_retires_exact_historical_editor_before_new_frame},
        {"applied null retirement survives trusted redaction",applied_null_retirement_survives_trusted_redaction}
    }};
    if (argc==2 && std::string_view(argv[1])=="--list") {
        for (const auto& [name,test]:tests) { (void)test; std::cout << name << '\n'; }
        return 0;
    }
    // Successful provider retirement material and any terminal uncertainty have
    // process lifetime. The external harness owns a fresh process per case;
    // this executable never forks or invokes a shell to reset that authority.
    if (argc!=3 || std::string_view(argv[1])!="--case") {
        std::cerr << "Use --list or --case NAME; each case requires a fresh process\n"; return 2;
    }
    const auto selected=std::find_if(tests.begin(),tests.end(),[&](const auto& value) { return value.first==argv[2]; });
    if (selected==tests.end()) { std::cerr << "Unknown editor App case: " << argv[2] << '\n'; return 2; }
    try {
        selected->second(); ++groups;
        std::cout << "PASS " << selected->first << ": " << groups << " cases, " << assertions
                  << " assertions, 0 skipped; real Owner/Registry/copied endpoint/Policy, synthetic provider replies\n";
    } catch (const std::exception& error) { std::cerr << selected->first << ": " << error.what() << '\n'; return 1; }
}
