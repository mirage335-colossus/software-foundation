// SPDX-License-Identifier: CC0-1.0
// Actual bitmap App/Owner/Registry/copied endpoint and sole presenter. Provider
// replies are synthetic; no native engine, browser, SDK, OS backend or IME runs.
// Fixture mechanics are retained from appended_engine_editor_application_test.cpp;
// this standalone source includes no production or test implementation .cpp.
#include "shared/appended_engine_application.hpp"
#include "shared/appended_engine_abi.h"
#include "shared/appended_engine_input_codec.hpp"
#include "shared/native_editor_codec.hpp"
#include <foundation/gui/document_endpoint.hpp>
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

namespace D = foundation::gui_document;
EngineDocumentTarget document_target(EngineIdentity value) {
    return {value.worker_epoch,value.application_instance,value.document_sequence,value.service_generation};
}
EngineIdentity document_identity(EngineDocumentTarget value) {
    return {value.worker_epoch,value.application_instance,value.document_sequence,value.service_generation};
}
struct DocumentWire {
    Bytes bytes;
    void integer(std::uint64_t value, unsigned width) {
        const auto at=bytes.size(); bytes.resize(at+width); put(bytes,at,value,width);
    }
    void text(std::string_view value) { integer(value.size(),4); bytes.insert(bytes.end(),value.begin(),value.end()); }
    void id(EngineDocumentTarget value) {
        integer(value.application_instance,8); integer(value.service_generation,8); integer(value.document_sequence,8);
    }
    void version(EngineDocumentTarget value, std::uint64_t revision) {
        integer(value.application_instance,8); integer(value.service_generation,8); integer(revision,8);
    }
    void header(unsigned kind, const EngineDocumentDispatch& request) {
        integer(0x3256444e,4); integer(2,2); integer(kind,1); integer(0,1);
        id(request.work.target); integer(request.work.request_sequence,8);
        integer(kind==4 ? get(request.work.payload,40,8) : 0,8);
    }
    void node(std::uint64_t value, std::uint64_t parent, unsigned kind, unsigned children,
              std::string_view tag, std::string_view text_value={},
              std::string_view name={}, std::string_view value_text={}, std::string_view href={}) {
        integer(value,8); integer(parent,8); integer(kind,1); integer(0,1); integer(children,4);
        text(tag); text(text_value); text(name); text(value_text); text(href);
    }
    void publication(EngineDocumentTarget value, std::uint64_t revision,
                     std::string_view native_value, std::uint64_t lease=0) {
        id(value); version(value,revision); integer(0,1);
        integer(revision,8); integer(10,8); integer(0,4); integer(0,4);
        integer(6,4); integer(0,4); integer(1,4); integer(0,1);
        node(1,0,1,3,"body");
        node(10,1,1,0,"input",{},"First field",native_value);
        node(70,1,1,1,"a",{},"Ordinary project link",{},"guide.html");
        node(71,70,2,0,{},"Ordinary project link");
        node(80,1,1,1,"p"); node(81,80,2,0,{},"Paired body observation");
        integer(10,8); integer(0,1); integer(4|8|32,1); integer(1|16,4); integer(1,1); integer(lease!=0,1);
        text("text"); text("First field");
        if (lease) { version(value,revision); integer(10,8); integer(lease,8); }
        text(native_value); text(native_value); integer(1,1);
        integer(0,4); integer(0,4); integer(0,1); // An actual native caret, valid for ASCII and multibyte fixtures.
    }
};
Bytes query_reply(const EngineDocumentDispatch& request, std::uint64_t revision, std::string_view value) {
    DocumentWire wire; wire.header(4,request); wire.publication(request.work.target,revision,value); return wire.bytes;
}
Bytes form_reply(const EngineDocumentDispatch& request, std::uint64_t revision,
                 std::string_view value, std::uint64_t lease, unsigned outcome=0, unsigned code=0) {
    DocumentWire wire; wire.header(5,request); wire.integer(outcome,1); wire.integer(code,1);
    wire.integer(outcome==1 ? 0 : 1,1); wire.integer(outcome==0,1);
    if (outcome==0) wire.publication(request.work.target,revision,value,lease);
    return wire.bytes;
}
Bytes ack_reply(std::uint64_t sequence, unsigned code=0) {
    Bytes bytes(16); put(bytes,0,sequence,8); put(bytes,8,code,4); return bytes;
}

void same_content(const D::State& actual,const D::State& expected,const char* message) {
    check(actual.publication_revision==expected.publication_revision && actual.observation==expected.observation &&
          actual.document==expected.document && actual.draft.has_value()==expected.draft.has_value(),message);
    if (actual.draft) {
        const auto& a=*actual.draft; const auto& b=*expected.draft;
        check(a.id==b.id && a.kind==b.kind && a.phase==b.phase && a.text==b.text &&
              a.selection==b.selection && a.checked==b.checked && a.dirty==b.dirty &&
              a.apply_queued==b.apply_queued && !a.option && !b.option,message);
    }
}
struct BitmapFixture : Fixture {
    unsigned native_entries{},ack_entries{};
    std::uint64_t revision{13},lease{9001};
    std::string native_value{"Actual copied fixture readback"};
    std::optional<EngineDocumentDispatch> peek_document() {
        const auto value=call(*owner,FOUNDATION_ENGINE_PEEK_DOCUMENT_WORK,owner->identity());
        if (value.control==FOUNDATION_ENGINE_EMPTY || value.control==FOUNDATION_ENGINE_CLOSED) return {};
        ok(value); check(value.transfer && value.body().size()>=56,"document PEEK omitted copied header");
        EngineDocumentDispatch result;result.transfer=value.transfer;
        auto& work=result.work;work.target=document_target(value.target);
        work.kind=static_cast<EngineDocumentWorkKind>(get(value.body(),0,4));
        work.operation=static_cast<std::uint32_t>(get(value.body(),4,4));
        work.request_sequence=get(value.body(),8,8);
        std::copy_n(value.body().begin()+16,32,work.schema_sha256.begin());
        work.required_reply_capacity=static_cast<std::uint32_t>(get(value.body(),48,4));
        check(get(value.body(),52,4)==value.body().size()-56,"document PEEK copied length mismatch");
        work.payload.assign(value.body().begin()+56,value.body().end());
        return result;
    }
    EngineDocumentDispatch work() {
        for(unsigned n=0;n<12;++n) {
            app->tick();if(auto value=peek_document())return *value;
        }
        throw std::runtime_error("bitmap App did not stage document Owner work");
    }
    D::Ticket submit(D::Intent value) {
        const auto before=native_entries+ack_entries;
        const auto result=app->document_submit(std::move(value));
        check(result.admission==D::Admission::accepted && result.ticket && result.ticket->value,
              "bitmap App refused valid typed document intent");
        check(native_entries+ack_entries==before && owner->callback_depth()==0,
              "document ingress synchronously entered synthetic provider");
        return *result.ticket;
    }
    void finish(const EngineDocumentDispatch& value,Span raw,unsigned disposition,
                bool handled=false,std::uint64_t semantic_revision=0) {
        Bytes begin(16);put(begin,0,static_cast<unsigned>(value.work.kind),4);
        put(begin,8,value.work.request_sequence,8);
        const auto id=document_identity(value.work.target);
        ok(call(*owner,FOUNDATION_ENGINE_BEGIN_DOCUMENT_WORK,id,begin,value.transfer));
        if(value.work.kind==EngineDocumentWorkKind::action_ack)++ack_entries;
        else {
            ok(call(*owner,FOUNDATION_ENGINE_TURN_ENTER,id,{},value.transfer));
            ok(call(*owner,FOUNDATION_ENGINE_TURN_LEAVE,id,{},value.transfer));++native_entries;
        }
        Bytes result(40+raw.size());put(result,0,static_cast<unsigned>(value.work.kind),4);
        put(result,8,value.work.request_sequence,8);put(result,20,disposition,4);
        put(result,24,raw.size(),4);put(result,28,handled,4);put(result,32,semantic_revision,8);
        std::copy(raw.begin(),raw.end(),result.begin()+40);
        ok(call(*owner,FOUNDATION_ENGINE_DOCUMENT_WORK_RESULT,id,result,value.transfer));
    }
    void finish_document_query(const EngineDocumentDispatch& value) {
        check(value.work.kind==EngineDocumentWorkKind::snapshot_query && value.work.operation==3 &&
              value.work.schema_sha256==document::kSchema && value.work.required_reply_capacity==document::kReplyCapacity &&
              value.work.target==document_target(owner->identity()) && value.work.payload.size()==48 &&
              get(value.work.payload,0,4)==0x3256444e && get(value.work.payload,8,8)==owner->identity().application_instance &&
              get(value.work.payload,16,8)==owner->identity().service_generation &&
              get(value.work.payload,24,8)==owner->identity().document_sequence &&
              get(value.work.payload,32,8)==value.work.request_sequence && get(value.work.payload,40,8),
              "Observe lost Owner-issued query3 identity/catalog/token");
        finish(value,query_reply(value,revision,native_value),0,false,revision);
    }
    D::Completion take(D::Ticket ticket) {
        const auto value=app->document_take(ticket);
        check(value && value->ticket==ticket,"known document completion unavailable after exact publication/ACK");
        check(!app->document_take(ticket),"duplicate document Take fabricated another completion");
        return *value;
    }
    D::Observation observe() {
        const auto ticket=submit(D::Observe{});const auto value=work();finish_document_query(value);
        app->tick();const auto published=app->document_state();
        const auto presenter_revision=adapter.snapshot().revision;
        app->tick();same_content(app->document_state(),published,"query metadata settlement changed accepted content");
        check(adapter.snapshot().revision==presenter_revision,"query metadata settlement republished GUI");
        const auto result=take(ticket);
        check(result.outcome==D::Outcome::completed && result.observation && app->document_state().document,
              "Observe did not publish actual decoded query3 content");
        return *result.observation;
    }
    EngineDocumentDispatch retire_before_begin(D::Observation observation,D::Ticket& ticket) {
        const auto old=basis();const auto before=native_retirements;
        ticket=submit(D::Begin{observation,10});app->tick();
        check(!peek_document() && !peek_physical(),"form6/physical3 preceded actual editor9 retirement");
        const auto retire=peek_editor();
        check(retire && retire->work.kind==EngineEditorWorkKind::revoke && retire->work.operation==9,
              "Begin did not stage actual editor9");
        finish_revoke(*retire);
        check(!peek_document() && !peek_physical(),"native9 result alone bypassed checked retirement publication");
        app->tick();
        check(native_retirements==before+1 && !port->editable() && !peek_document(),
              "Begin published draft or form6 before physical retirement");
        const auto physical=consume_physical();input::Focus focus;
        check(physical.operation==3 && input::decode_focus(physical.payload,focus)==input::Status::ok &&
              focus.action==2 && focus.expected_context==old.identity.context,
              "Begin did not retire exact physical3 context after native9");
        const auto value=work();
        check(value.work.kind==EngineDocumentWorkKind::form_action && value.work.operation==6 &&
              value.work.schema_sha256==document::kSchema && value.work.required_reply_capacity==document::kReplyCapacity &&
              value.work.target==document_target(owner->identity()) && value.work.payload.size()>=81 &&
              get(value.work.payload,48,1)==0 && get(value.work.payload,49,8)==owner->identity().application_instance &&
              get(value.work.payload,57,8)==owner->identity().service_generation &&
              get(value.work.payload,65,8)==revision && get(value.work.payload,73,8)==10,
              "Begin lost observed document identity/node or exact form6 catalog");
        check(!app->document_take(ticket),"Begin completion escaped before native form6");
        return value;
    }
    void finish_form(const EngineDocumentDispatch& value) {
        ++revision;++lease;finish(value,form_reply(value,revision,native_value,lease),1,true);
    }
    EngineDocumentDispatch ack(const EngineDocumentDispatch& action) {
        const auto value=work();
        check(value.work.kind==EngineDocumentWorkKind::action_ack && value.work.operation==7 &&
              value.work.target==action.work.target && value.work.request_sequence>action.work.request_sequence &&
              value.work.payload==encode_u64(action.work.request_sequence) &&
              value.work.schema_sha256==document::kAckSchema && value.work.required_reply_capacity==16,
              "ACK7 lost original action/target or Owner-owned sequence/catalog");
        const auto before=native_entries;finish(value,ack_reply(action.work.request_sequence),1);
        check(native_entries==before,"ACK7 entered another native TURN");return value;
    }
};

void observe_query_sole_publication_and_take() {
    BitmapFixture f;f.activate();const auto before=f.app->document_state();
    const auto publications=f.port->commits.size();const auto ticket=f.submit(D::Observe{});
    check(!f.peek_document() && !f.app->document_take(ticket),"Observe ingress staged work or invented completion");
    const auto query=f.work();f.finish_document_query(query);
    same_content(f.app->document_state(),before,"query result escaped sole-presentation fence");
    bool paired=false;
    f.port->during_publication=[&](const PolicyPort::Commit& candidate) {
        paired=true;check(candidate.revision==f.adapter.snapshot().revision,"candidate differs from actual presenter revision");
        same_content(f.app->document_state(),before,"accepted document changed inside uncommitted presenter callback");
        check(!f.app->document_take(ticket),"Take escaped an active GUI publication");
    };
    f.app->tick();f.port->during_publication={};
    const auto accepted=f.app->document_state();
    check(paired && f.port->commits.size()==publications+1 && accepted.document && accepted.observation &&
          accepted.publication_revision==f.adapter.snapshot().revision &&
          accepted.publication_revision==f.port->committed.revision,
          "query3 content lacks its exact single actual GUI publication");
    const auto entries=f.native_entries;const auto count=f.port->commits.size();
    const auto revision=f.adapter.snapshot().revision;
    f.app->tick();same_content(f.app->document_state(),accepted,"query settlement replaced accepted content");
    check(f.app->document_state().phase==D::Phase::waiting_take &&
          f.adapter.snapshot().revision==revision && f.port->commits.size()==count && f.native_entries==entries,
          "query completion settlement republished or reentered native provider");
    const auto done=f.take(ticket);same_content(f.app->document_state(),accepted,"query Take replaced accepted content");
    check(done.outcome==D::Outcome::completed && done.observation==accepted.observation &&
          f.app->document_state().phase==D::Phase::idle && !f.app->document_state().pending &&
          f.native_entries==entries && f.port->commits.size()==count && !f.peek_document(),
          "query Take published, reentered or retained local pending state");
}
void begin_retires_editor_then_physical_before_form() {
    BitmapFixture f;f.activate();const auto observation=f.observe();D::Ticket ticket;
    const auto form=f.retire_before_begin(observation,ticket);
    check(f.native_entries==1 && !f.peek_editor() && !f.peek_physical() && !f.app->document_state().draft,
          "Begin native form effect entered before the caller consumed staged form6");
    f.finish_form(form);f.app->tick();
    check(f.app->document_state().draft && !f.app->document_take(ticket),
          "Begin did not publish native readback or ignored required ACK7");
    f.ack(form);f.app->tick();check(f.take(ticket).outcome==D::Outcome::completed,"Begin failed after exact ACK7");
}
void query_publication_failure_preserves_state() {
    BitmapFixture f;f.activate();f.observe();const auto before=f.app->document_state();
    const auto ticket=f.submit(D::Observe{});const auto query=f.work();++f.revision;f.native_value="New query candidate";
    f.finish_document_query(query);const auto committed=f.port->commits.size();
    const auto presenter_before=f.adapter.snapshot().revision;
    f.adapter.throw_after_next=true;bool threw=false;try{f.app->tick();}catch(const std::runtime_error&){threw=true;}
    check(threw && f.adapter.publication_faults==1 && f.adapter.snapshot().revision>presenter_before &&
          f.port->commits.size()==committed,"after-install query publication fault did not discriminate checked commit");
    const auto pending=f.app->document_state();same_content(pending,before,"failed query publication replaced last accepted State");
    check(pending.phase==D::Phase::waiting_publication && pending.pending==ticket && f.app->presentation_pending() &&
          !f.app->document_take(ticket) && !f.peek_document() && !f.ack_entries,
          "failed query lost pending candidate or invented ACK/completion");
}
void form_publication_failure_withholds_ack() {
    BitmapFixture f;f.activate();const auto observation=f.observe();D::Ticket ticket;
    const auto form=f.retire_before_begin(observation,ticket);const auto before=f.app->document_state();
    const auto presenter_before=f.adapter.snapshot().revision;
    f.finish_form(form);f.adapter.throw_before_next=true;bool threw=false;
    try{f.app->tick();}catch(const std::runtime_error&){threw=true;}
    check(threw && f.adapter.publication_faults==1 && f.adapter.snapshot().revision==presenter_before,
          "before-install form publication fault changed actual committed revision");
    const auto pending=f.app->document_state();same_content(pending,before,"failed form publication exposed uncommitted draft/readback");
    check(pending.phase==D::Phase::waiting_publication && pending.pending==ticket && !f.app->document_take(ticket) &&
          !f.peek_document() && !f.ack_entries && f.native_entries==2 && f.app->presentation_pending(),
          "failed form presentation replayed native6, staged ACK7 or discarded candidate");
}
void ack_and_take_preserve_accepted_content() {
    BitmapFixture f;f.activate();const auto observation=f.observe();D::Ticket ticket;
    const auto form=f.retire_before_begin(observation,ticket);f.finish_form(form);f.app->tick();
    const auto accepted=f.app->document_state();const auto count=f.port->commits.size();
    check(accepted.document && accepted.observation && accepted.draft && accepted.pending==ticket &&
          accepted.publication_revision==f.adapter.snapshot().revision && !f.app->document_take(ticket),
          "native6 content not accepted by actual sole presenter before ACK");
    f.ack(form);f.app->tick();const auto acknowledged=f.app->document_state();
    same_content(acknowledged,accepted,"ACK7 rewrote accepted observation/draft/document/revision");
    check(acknowledged.phase==D::Phase::waiting_take && acknowledged.pending==ticket,
          "actual ACK7 did not change only live completion phase");
    const auto native=f.native_entries,acks=f.ack_entries;const auto revision=f.adapter.snapshot().revision;
    const auto done=f.take(ticket);const auto taken=f.app->document_state();
    same_content(taken,accepted,"metadata Take rewrote accepted observation/draft/document/revision");
    check(done.outcome==D::Outcome::completed && done.draft && done.draft->id==accepted.draft->id &&
          taken.phase==D::Phase::idle && !taken.pending && f.native_entries==native && f.ack_entries==acks &&
          f.adapter.snapshot().revision==revision && f.port->commits.size()==count && !f.peek_document(),
          "Take republished, retried ACK/provider or left live pending metadata");
}
void terminal_candidate_redacts_without_semantic_commit() {
    BitmapFixture f;f.activate();f.observe();const auto accepted=f.app->document_state();
    const auto ticket=f.submit(D::Observe{});const auto query=f.work();
    ++f.revision;f.native_value="Never accepted terminal candidate";f.finish_document_query(query);
    f.adapter.throw_before_next=true;bool failed=false;
    try { f.app->tick(); } catch(const std::runtime_error&) { failed=true; }
    check(failed && f.app->document_state().phase==D::Phase::waiting_publication,
          "terminal candidate fixture lacks an actual failed publication");
    same_content(f.app->document_state(),accepted,"failed candidate escaped before terminal transition");
    const auto entries=f.native_entries,acks=f.ack_entries;
    const auto hook=f.app->document_terminal();hook.notify(hook.context);
    // Safe GUI redaction is still required. The retained semantic candidate
    // cannot become accepted after native authority has become terminal.
    f.app->tick();const auto terminal=f.app->document_state();
    same_content(terminal,accepted,"terminal redaction accepted the forensic semantic candidate");
    check(terminal.phase==D::Phase::terminal && !terminal.available && terminal.pending==ticket &&
          f.adapter.snapshot().widgets.empty() && f.adapter.closed() &&
          !f.app->presentation_pending() && !f.app->shutdown_complete() && !f.app->document_take(ticket),
          "terminal candidate prevented safe GUI close or fabricated clean semantic completion");
    f.app->tick();
    check(f.native_entries==entries && f.ack_entries==acks && !acks && !f.peek_document(),
          "terminal redaction replayed or ACKed the unaccepted candidate");
}
void document_terminal_is_metadata_only() {
    BitmapFixture f;f.activate();const auto before=f.adapter.snapshot().revision;
    const auto hook=f.app->document_terminal();check(hook.context && hook.notify,"document terminal hook is partial");
    const auto entries=f.native_entries;hook.notify(hook.context);
    check(f.native_entries==entries && !f.ack_entries && f.adapter.snapshot().revision==before,
          "terminal metadata hook entered provider or synchronously published");
    f.app->tick();const auto state=f.app->document_state();
    check(state.phase==D::Phase::terminal && !state.available && f.adapter.snapshot().widgets.empty() &&
          !f.app->document_submit(D::Observe{}).ticket && !f.peek_document() && !f.ack_entries,
          "terminal notification left document ingress/pixels/native replay available");
}
} // namespace

int main(int argc,char** argv) {
    const std::array<std::pair<std::string_view,void(*)()>,7> tests{{
        {"Observe query3 sole publication and metadata Take",observe_query_sole_publication_and_take},
        {"Begin retires editor9 then physical3 before form6",begin_retires_editor_then_physical_before_form},
        {"query publication failure preserves accepted State and pending candidate",query_publication_failure_preserves_state},
        {"form publication failure preserves State and withholds ACK7",form_publication_failure_withholds_ack},
        {"ACK7 and Take preserve accepted content and publication revision",ack_and_take_preserve_accepted_content},
        {"document terminal notification stays metadata only",document_terminal_is_metadata_only},
        {"terminal candidate redacts without semantic commit",terminal_candidate_redacts_without_semantic_commit}
    }};
    if(argc==2 && std::string_view(argv[1])=="--list") {
        for(const auto& [name,test]:tests){(void)test;std::cout<<name<<'\n';}return 0;
    }
    if(argc!=3 || std::string_view(argv[1])!="--case") {
        std::cerr<<"Use --list or --case NAME; each case requires a fresh process\n";return 2;
    }
    const auto selected=std::find_if(tests.begin(),tests.end(),[&](const auto& value){return value.first==argv[2];});
    if(selected==tests.end()){std::cerr<<"Unknown bitmap document case: "<<argv[2]<<'\n';return 2;}
    try{
        selected->second();++groups;
        std::cout<<"PASS "<<selected->first<<": "<<groups<<" cases, "<<assertions
                 <<" assertions, 0 skipped; actual App/Owner/Registry/copied endpoint/presenter, synthetic provider\n";
        return 0;
    }catch(const std::exception& error){std::cerr<<selected->first<<": "<<error.what()<<'\n';return 1;}
}
