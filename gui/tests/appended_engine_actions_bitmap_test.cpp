// SPDX-License-Identifier: CC0-1.0
// Canonical copied-transport/Policy helpers copied without modification from
// appended_engine_editor_application_test.cpp SHA-256 5e953959c3a9554e909eeb2083fd15d746cd710cfed49b2cfbe98a5ca20398de.
// The Actions fixture below independently configures only exact4083 facts.
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
#include <thread>
#include <utility>
#include <vector>

#include "../../tests/appended_document_actions_fixture.hpp"

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
namespace actions = appended::engine_document_actions;
struct ActionsFixture {
    TestAdapter adapter;
    actions::EngineDocumentActionsProfileFacts facts=document_actions_fixture::profile();
    std::shared_ptr<EngineOwner> owner;
    PolicyPort* port{};
    std::unique_ptr<ui::AppendedEngineApplication> app;
    std::optional<ne::NativeProjection> live;
    std::uint64_t input_sequence{}, sample=large+101, next_native_token=large+501;
    std::uint64_t last_retired_context{}, held_ticket{};
    std::optional<ne::NativeRetireMaterial> last_retired_material;
    unsigned native_effects{}, native_retirements{};
    bool interactive{}, hold_on_entry=false;
    static constexpr std::string_view service_name="org.example.actions-bitmap.native";
    explicit ActionsFixture(bool input=true,bool create=true,bool native_service=false):interactive(input) {
        check(actions::document_actions_profile_valid(facts) && facts.provider_capabilities==4083,
              "actions fixture did not supply independent exact4083 facts");
        EngineOwnerConfiguration config; config.worker_epoch=large+11; config.document_actions_profile=facts;
        if (native_service) config.native_services.push_back({{std::string(service_name),1,0,SchemaId{7},4},
            [this](std::uint32_t operation,Span value,std::span<std::uint8_t> output)->ServiceReply {
                const auto effect=owner->native_effect();
                check(operation==1 && value.size()==4 && output.size()>=4 && effect && effect->entered &&
                      effect->target==owner->identity() && adapter.snapshot().widgets.empty() && app->view().widgets.empty() &&
                      !app->presentation_pending(),"actual actions Registry handler preceded successfully checked bitmap redaction");
                if (interactive) {
                    check(effect->input_context==last_retired_context && native_retirements && last_retired_material &&
                          last_retired_material->input_context==effect->input_context && port && port->service &&
                          !port->available() && !port->editable() && port->committed.revision==adapter.snapshot().revision,
                          "interactive actions handler preceded exact native9 and physical retirement");
                } else check(!port && !effect->input_context && !native_retirements,
                             "view-only actions handler acquired physical/editor authority");
                if (hold_on_entry) {
                    check(owner->hold_native_effect(effect->ticket),"actual actions handler could not retain its UI hold");
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
        check(owner->document_actions_profile()==facts && !owner->editor_profile().enabled && !owner->document_profile().enabled &&
              owner->document_actions_enabled() && !owner->has_module(),"actions Owner fell through old profile or Module admission");
        if (create) construct();
    }
    void construct() {
        if (interactive) {
            auto owned=std::make_unique<PolicyPort>(adapter); port=owned.get();
            app=std::make_unique<ui::AppendedEngineApplication>(adapter,owner,facts,ui::BoundEngineEditorPort{std::move(owned)});
            port->revoked=[this](gui_surface::Revocation value) { app->surface_revoked(std::move(value)); };
            check(app->view().title==owner->package().application.name && adapter.snapshot().title==app->view().title,
                  "interactive actions title acquired a view-only marker");
        } else app=std::make_unique<ui::AppendedEngineApplication>(adapter,owner,facts,ui::ReadOnlyEngineBitmap{});
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
void actions_mailboxes_empty(ActionsFixture& f) {
    check(!f.peek_physical() && !f.peek_editor() &&
          call(*f.owner,FOUNDATION_ENGINE_PEEK_DOCUMENT_WORK,f.owner->identity()).control==FOUNDATION_ENGINE_EMPTY,
          "bitmap composition staged physical/editor or semantic document actions");
}
void actions_bitmap(const gui::Snapshot& value,std::uint64_t revision,std::uint8_t red) {
    check(value.widgets.size()==1 && value.widgets.front().spec.kind==gui::Kind::bitmap &&
          value.widgets.front().state.bitmap.revision==revision && value.widgets.front().state.bounds==gui::Rect{0,0,800,600},
          "actions App did not publish its actual immutable bitmap frame");
    std::array<std::uint8_t,3> pixel{}; bool painted=false;
    value.widgets.front().state.bitmap.source.paint({800,600,{0,0,1,1},gui::PixelFormat::rgb24},
        [&](unsigned x,unsigned y,gui::PixelBlock block) {
            check(!x && !y && block.bytes.size()>=3,"actions copied frame changed its damage origin");
            std::copy_n(block.bytes.begin(),3,pixel.begin()); painted=true;
        });
    check(painted && pixel==std::array<std::uint8_t,3>{red,0,0},"actions App painted stale or borrowed frame pixels");
}
input::EngineSurfaceProfileFacts actions_legacy_input() {
    input::EngineSurfaceProfileFacts value;
    value.enabled=true; value.name=input::kInputProfileName; value.contract_sha256=input::kProviderContractSha256;
    value.build_sha256.fill(1); value.source_recipe_sha256.fill(2); value.catalog_sha256=input::kInputCatalogSha256;
    value.provider_capabilities=input::kProviderCapabilities; value.surface_capabilities=input::kSurfaceCapabilities;
    value.surface_protocol_version=1; value.mouse_input_version=1; value.raw_key_mapping_revision=1;
    value.viewport_width=800; value.viewport_height=600; value.display_scale=1; value.commands=input::kCommands;
    check(input::input_profile_valid(value),"enabled legacy counterfactual facts are not independently valid"); return value;
}
void actions_exact_admission() {
    ActionsFixture f(true,false);
    const auto revision=f.adapter.snapshot().revision;
    rejects([&] { ui::AppendedEngineApplication old(f.adapter,f.owner); },"actions Owner entered old bitmap constructor");
    rejects([&] { ui::AppendedEngineApplication old(f.adapter,f.owner,std::unique_ptr<ui::EngineSurfacePort>{},input::EngineSurfaceProfileFacts{}); },
            "actions Owner entered disabled legacy constructor");
    const auto legacy=actions_legacy_input();
    rejects([&] { ui::AppendedEngineApplication old(f.adapter,f.owner,std::make_unique<PolicyPort>(f.adapter),legacy); },
            "actions Owner entered genuine enabled legacy467 constructor");
    rejects([&] { ui::AppendedEngineApplication old(f.adapter,f.owner,document_actions_fixture::legacy_profile(),
                std::make_unique<PolicyPort>(f.adapter)); },"actions Owner entered old document2003 constructor");
    rejects([&] { ui::AppendedEngineApplication old(f.adapter,f.owner,editor_facts(),
                ui::BoundEngineEditorPort{std::make_unique<PolicyPort>(f.adapter)}); },"actions Owner entered old editor2035 constructor");
    rejects([&] { ui::AppendedEngineApplication invalid(f.adapter,f.owner,f.facts,ui::BoundEngineEditorPort{}); },
            "interactive actions App accepted null bound editor port");
    for (unsigned mismatch=0;mismatch<2;++mismatch) {
        auto facts=f.facts;
        if (mismatch) facts.source_recipe_sha256[0]^=1; else facts.build_sha256[0]^=1;
        check(actions::document_actions_profile_valid(facts),"mismatch fixture stopped testing exact valid facts agreement");
        rejects([&] { ui::AppendedEngineApplication invalid(f.adapter,f.owner,facts,
                    ui::BoundEngineEditorPort{std::make_unique<PolicyPort>(f.adapter)}); },"interactive actions App ignored exact Owner facts");
        rejects([&] { ui::AppendedEngineApplication invalid(f.adapter,f.owner,facts,ui::ReadOnlyEngineBitmap{}); },
                "view-only actions App ignored exact Owner facts");
    }
    for (unsigned bad=0;bad<3;++bad) {
        auto port=std::make_unique<PolicyPort>(f.adapter,false);
        if (!bad) port->offered.supported=input::kSurfaceCapabilities;
        if (bad==1) port->offered.version=2;
        if (bad==2) port->offered.mouse_input_version=0;
        rejects([&] { ui::AppendedEngineApplication invalid(f.adapter,f.owner,f.facts,ui::BoundEngineEditorPort{std::move(port)}); },
                "interactive actions App accepted partial or incompatible port capabilities");
    }
    check(f.adapter.snapshot().revision==revision && !f.owner->closed() && !f.owner->native_effect(),
          "rejected actions constructors published or entered native effects");
    actions_mailboxes_empty(f); f.construct();
    check(f.port->capabilities().supported==0 && !f.peek_editor() && !f.peek_physical(),"unconnected actions port acquired authority");
    f.connect();
    check(f.port->capabilities().supported==8255 && f.port->capabilities().version==1 &&
          f.port->capabilities().mouse_input_version==1 && f.peek_physical() && !f.peek_editor(),
          "actions port failed exact zero-to8255 negotiation and bind-before-query ordering");
}
void actions_read_only_frames() {
    ActionsFixture f(false);
    const auto title=f.owner->package().application.name+" (view only)";
    check(!f.port && f.app->view().title==title && f.adapter.snapshot().title==title,
          "read-only actions composition lacks its visible view-only marker");
    actions_bitmap(f.app->view(),1,0x29); actions_bitmap(f.adapter.snapshot(),1,0x29); actions_mailboxes_empty(f);
    check(!f.app->editor_submit({}) && !f.app->editor_revoke({}) && !f.app->editor_take(1),
          "read-only actions composition created an editor Controller/head");
    f.app->surface_connected(PolicyPort::selected()); f.app->editor_resync(); f.app->tick(); actions_mailboxes_empty(f);
    auto next=frame(1); next[48]=0x71;
    ok(call(*f.owner,FOUNDATION_ENGINE_FRAME_COMMIT,f.owner->identity(),next));
    actions_bitmap(f.adapter.snapshot(),1,0x29); f.app->tick();
    actions_bitmap(f.adapter.snapshot(),2,0x71); actions_bitmap(f.app->view(),2,0x71); actions_mailboxes_empty(f);
    check(f.adapter.snapshot().title==title && f.owner->document_actions_profile()==f.facts,
          "view-only frame refresh changed its marker or independently admitted actions facts");
    f.app->shutdown(); f.app->tick();
    check(f.adapter.closed() && f.owner->closed() && !f.app->presentation_pending(),"read-only actions close invented pending native debt");
}
Bytes service_request(EngineIdentity target,std::uint64_t sequence,std::uint64_t handle,std::uint32_t operation,Span payload) {
    Envelope header; header.generation=target.service_generation; header.sequence=sequence;
    header.interface_handle=handle; header.operation=operation;
    Bytes result;
    check(encode_envelope(header,payload,result)==CodecStatus::ok,"fixture service envelope is invalid");
    return result;
}
Bytes collect_actions_service(ActionsFixture& f,std::uint64_t sequence) {
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
Bytes interactive_actions_effect_cycle(ActionsFixture& f,std::uint64_t sequence,std::uint64_t handle,std::uint32_t operation,Span payload) {
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
    const auto result=collect_actions_service(f,sequence);
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

Bytes read_only_actions_effect_cycle(ActionsFixture& f,std::uint64_t sequence,std::uint64_t handle,std::uint32_t operation,Span payload) {
    const auto target=f.owner->identity(); const auto effects=f.native_effects;
    ok(call(*f.owner,FOUNDATION_ENGINE_SUBMIT,target,service_request(target,sequence,handle,operation,payload)));
    const auto gate=call(*f.owner,FOUNDATION_ENGINE_PUMP_ONE,target);
    check(gate.control==FOUNDATION_ENGINE_CONFLICT && gate.service==static_cast<std::uint32_t>(ServiceStatus::unavailable) &&
          f.owner->native_effect() && f.native_effects==effects,"view-only Registry effect bypassed checked redaction");
    f.app->tick();
    check(f.adapter.snapshot().widgets.empty() && f.app->view().widgets.empty() && !f.app->presentation_pending(),
          "view-only actions App acknowledged native effect before empty publication");
    actions_mailboxes_empty(f); ok(call(*f.owner,FOUNDATION_ENGINE_PUMP_ONE,target));
    const auto result=collect_actions_service(f,sequence); f.app->tick();
    if (f.hold_on_entry) {
        check(f.held_ticket && f.owner->native_effect(),"view-only known reply released its independent native UI hold");
        ok(call(*f.owner,FOUNDATION_ENGINE_FRAME_COMMIT,target,frame(f.owner->frame()->frame_revision)));
        f.app->tick(); check(f.adapter.snapshot().widgets.empty(),"view-only held native UI exposed an in-hold frame");
        check(f.owner->release_native_effect(f.held_ticket),"view-only trusted UI release lost its exact held ticket");
        f.app->tick();
    }
    const auto floor=f.owner->frame()->frame_revision;
    f.app->tick(); check(f.adapter.snapshot().widgets.empty(),"view-only release reused a pre-release frame");
    actions_mailboxes_empty(f);
    ok(call(*f.owner,FOUNDATION_ENGINE_FRAME_COMMIT,target,frame(floor))); f.app->tick();
    actions_bitmap(f.adapter.snapshot(),floor+1,0x29); actions_mailboxes_empty(f);
    check(!f.port && !f.native_retirements,"view-only native effect invented physical/editor cleanup"); return result;
}
void actions_registry_effect(bool interactive) {
    ActionsFixture f(interactive,true,true); if (interactive) f.activate();
    const auto major=encode_u32(1), minor=encode_u32(0);
    const std::array<FieldView,4> fields{{{1,FieldType::utf8,true,bytes(ActionsFixture::service_name)},
        {2,FieldType::u32,true,major},{3,FieldType::u32,true,minor},{4,FieldType::u32,true,minor}}};
    Bytes query; check(encode_record(fields,query)==CodecStatus::ok,"actions Registry discovery request is malformed");
    const auto cycle=[&](std::uint64_t sequence,std::uint64_t handle,std::uint32_t operation,Span payload) {
        return interactive?interactive_actions_effect_cycle(f,sequence,handle,operation,payload):
                           read_only_actions_effect_cycle(f,sequence,handle,operation,payload);
    };
    const auto descriptor=cycle(1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER,query);
    std::vector<FieldView> decoded; std::uint64_t handle{};
    check(decode_record(descriptor,decoded)==CodecStatus::ok && !decoded.empty() && read_u64(decoded.front(),handle) && handle &&
          !f.native_effects,"actual actions Registry discovery lost its opaque handle");
    f.hold_on_entry=true; const auto value=encode_u32(73);
    check(cycle(2,handle,1,value)==value && f.native_effects==1 && f.native_retirements==(interactive?2u:0u),
          "actions native effect lacked exact cleanup or replayed its actual Registry handler");
}
void actions_interactive_checked_head() {
    ActionsFixture f; f.activate();
    actions_bitmap(f.adapter.snapshot(),1,0x29);
    const auto packet=text_packet(f.basis());
    const auto head=f.app->editor_submit(packet);
    check(head && !f.app->editor_take(*head) && !f.peek_editor() && !f.peek_physical(),"actions editor callback entered native work or fabricated completion");
    f.app->tick(); const auto query=f.query();
    check(identity(query.work.target)==f.owner->identity(),"actions head query lost its full native target");
    f.finish_query(query,true); f.app->tick(); const auto pending=f.peek_editor();
    codec::NativeRequestEnvelope request;
    check(pending && pending->work.kind==EngineEditorWorkKind::observation &&
          pending->work.operation==BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1 &&
          codec::decode_native_request(pending->work.payload,request) && request.request.packet==packet &&
          request.target==wire_target(pending->work),"actions neutral editor path did not preserve the accepted Packet/native8 join");
    auto projection=request.request.resolved;
    ++projection.editor_revision; projection.surrounding="AXB"; projection.selection={2,2}; projection.caret={40,24,1,18};
    ne::NativeResult result; result.outcome=ne::Outcome::applied; result.continuity=ne::Continuity::same;
    result.availability=ne::NativeAvailability::available; result.observation_revision=++f.sample;
    result.readback_identity=projection.identity; result.readback_attested=true; result.retire=projection.retire; result.projection=projection;
    Bytes encoded; check(codec::encode_native_result({request.target,result},encoded),"actions native8 reply malformed");
    f.finish_editor(*pending,encoded,1); check(!f.app->editor_take(*head),"actions native8 receipt escaped before checked publication");
    const ne::Settlement settlement{packet.session,packet.observation.id,packet.basis.token,packet.observation.predecessor};
    bool checked=false,escaped=false;
    f.port->during_publication=[&](const PolicyPort::Commit& candidate) {
        if (!candidate.editor || candidate.editor->settlement!=std::optional{settlement}) return;
        check(candidate.editor->basis && candidate.editor->basis->surrounding=="AXB" &&
              candidate.editor->basis->selection==gui_surface::ByteRange{2,2} && candidate.revision==f.adapter.snapshot().revision,
              "actions native8 split its bitmap/Basis/settlement pair");
        actions_bitmap(f.adapter.snapshot(),1,0x29); checked=true; escaped=f.app->editor_take(*head).has_value();
        f.app->tick(); check(!f.peek_editor() && !f.peek_physical(),"actions native publication reentered copied work");
    };
    f.app->tick(); f.port->during_publication={};
    check(checked && !escaped,"actions neutral editor did not publish before metadata Take");
    const auto published=f.port->committed;
    f.app->retry_presentation(); f.app->retry_presentation();
    check(f.port->committed.revision==published.revision && f.port->committed.editor==published.editor &&
          f.port->committed.surface==published.surface,"actions pending Take lost the exact checked pair");
    const auto completion=f.app->editor_take(*head);
    check(completion && completion->ticket==*head && completion->result.admission==ne::Admission::completed && completion->result.receipt &&
          completion->result.receipt->outcome==ne::Outcome::applied && completion->result.receipt->basis==published.editor->basis &&
          completion->result.receipt->session==packet.session && completion->result.receipt->id==packet.observation.id &&
          completion->result.receipt->submitted_token==packet.basis.token && !f.app->editor_take(*head) &&
          !f.peek_editor() && !f.peek_physical(),"actions accepted head lost its original one-time checked receipt");
}
void actions_historical_retirement() {
    ActionsFixture f; f.activate();
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
void actions_close_after_owner_retirement() {
    ActionsFixture f; f.activate();
    const auto target=f.owner->identity();
    const auto old=f.basis();
    const auto material=*f.live->retire;
    f.app->shutdown(); f.app->tick();
    const auto cleanup=f.peek_editor(); codec::RevocationEnvelope request;
    check(cleanup && cleanup->work.kind==EngineEditorWorkKind::revoke &&
          identity(cleanup->work.target)==target && codec::decode_revocation(cleanup->work.payload,request) &&
          request.request.identity==old.identity && request.request.material==material,
          "normal close did not retain its exact old native9 target/material");
    check(!f.port->policy.accepted() && !f.adapter.closed() && !f.owner->closed() && !f.port->available(),
          "close did not retire public physical authority before its known native9 settlement");
    // Actual NativeEngineDriver sends CLOSE before returning the retained
    // native9 result. Exercise that Owner metadata ordering without a Driver
    // or provider: the original claimed work must still settle under OLD target.
    f.owner->close();
    check(!f.owner->closed() && f.owner->editor_enabled() &&
          !f.owner->identity().document_sequence && !f.owner->identity().service_generation,
          "Owner close prematurely completed or preserved live document admission");
    bool checked=false;
    f.port->during_publication=[&](const PolicyPort::Commit& candidate) {
        if (!candidate.editor || !candidate.editor->retirement) return;
        const auto& proof=*candidate.editor->retirement;
        check(!candidate.surface && !candidate.editor->basis && proof.authority_retired &&
              proof.readback_attested && proof.identity==request.request.identity &&
              f.adapter.snapshot().widgets.empty() && f.app->view().widgets.empty() &&
              !f.port->policy.accepted() && !f.owner->closed(),
              "known native9 close reintroduced a retired physical context or skipped actual empty publication");
        checked=true;
    };
    f.finish_revoke(*cleanup);
    check(!checked && f.native_retirements==1 && !f.owner->closed(),
          "provider return published or cleaned up before App checked native9 settlement");
    f.app->tick();
    check(checked && f.owner->closed() && !f.owner->editor_enabled() && f.adapter.closed() &&
          f.adapter.snapshot().widgets.empty() && f.app->view().widgets.empty() &&
          !f.port->policy.accepted() && !f.app->presentation_pending() && f.native_retirements==1,
          "normal close failed after actual checked retirement or retried native9");
    const auto published=f.adapter.snapshot().revision;
    f.app->tick(); f.app->shutdown();
    check(f.native_retirements==1 && f.adapter.snapshot().revision==published,
          "completed close replayed native work or republished old pixels");
}
void actions_known_head_close() {
    {
    ActionsFixture f; f.activate();
    actions_bitmap(f.adapter.snapshot(),1,0x29);
    const auto packet=text_packet(f.basis());
    const auto head=f.app->editor_submit(packet);
    check(head && !f.app->editor_take(*head) && !f.peek_editor() && !f.peek_physical(),"actions editor callback entered native work or fabricated completion");
    f.app->tick(); const auto query=f.query();
    check(identity(query.work.target)==f.owner->identity(),"actions head query lost its full native target");
    f.finish_query(query,true); f.app->tick(); const auto pending=f.peek_editor();
    codec::NativeRequestEnvelope request;
    check(pending && pending->work.kind==EngineEditorWorkKind::observation &&
          pending->work.operation==BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1 &&
          codec::decode_native_request(pending->work.payload,request) && request.request.packet==packet &&
          request.target==wire_target(pending->work),"actions neutral editor path did not preserve the accepted Packet/native8 join");
    auto projection=request.request.resolved;
    ++projection.editor_revision; projection.surrounding="AXB"; projection.selection={2,2}; projection.caret={40,24,1,18};
    ne::NativeResult result; result.outcome=ne::Outcome::applied; result.continuity=ne::Continuity::same;
    result.availability=ne::NativeAvailability::available; result.observation_revision=++f.sample;
    result.readback_identity=projection.identity; result.readback_attested=true; result.retire=projection.retire; result.projection=projection;
    Bytes encoded; check(codec::encode_native_result({request.target,result},encoded),"actions native8 reply malformed");
    f.finish_editor(*pending,encoded,1); check(!f.app->editor_take(*head),"actions native8 receipt escaped before checked publication");
    const ne::Settlement settlement{packet.session,packet.observation.id,packet.basis.token,packet.observation.predecessor};
    bool checked=false,escaped=false;
    f.port->during_publication=[&](const PolicyPort::Commit& candidate) {
        if (!candidate.editor || candidate.editor->settlement!=std::optional{settlement}) return;
        check(candidate.editor->basis && candidate.editor->basis->surrounding=="AXB" &&
              candidate.editor->basis->selection==gui_surface::ByteRange{2,2} && candidate.revision==f.adapter.snapshot().revision,
              "actions native8 split its bitmap/Basis/settlement pair");
        actions_bitmap(f.adapter.snapshot(),1,0x29); checked=true; escaped=f.app->editor_take(*head).has_value();
        f.app->tick(); check(!f.peek_editor() && !f.peek_physical(),"actions native publication reentered copied work");
    };
    f.app->tick(); f.port->during_publication={};
    check(checked && !escaped,"actions neutral editor did not publish before metadata Take");
    const auto published=f.port->committed;
    f.app->retry_presentation(); f.app->retry_presentation();
    check(f.port->committed.revision==published.revision && f.port->committed.editor==published.editor &&
          f.port->committed.surface==published.surface,"actions pending Take lost the exact checked pair");
    f.live=projection;
    check(!f.app->shutdown_complete(),"live App reported completed close");
    f.app->shutdown(); f.app->tick(); const auto cleanup=f.peek_editor();
    check(cleanup && cleanup->work.kind==EngineEditorWorkKind::revoke && !f.app->shutdown_complete(),
          "known head close omitted native9 or completed before actual retirement");
    codec::RevocationEnvelope retirement;
    check(codec::decode_revocation(cleanup->work.payload,retirement) && retirement.request.material==*projection.retire,
          "known head close changed actual provider-issued retirement material");
    f.owner->close(); f.finish_revoke(*cleanup); f.app->tick();
    const auto closed_pair=f.port->committed;
    check(f.owner->closed() && !f.adapter.closed() && !f.app->shutdown_complete() && f.native_retirements==1 &&
          closed_pair.editor && closed_pair.editor->settlement==std::optional{settlement} &&
          !closed_pair.surface && !closed_pair.editor->basis && closed_pair.editor->retirement &&
          closed_pair.editor->retirement->authority_retired && closed_pair.editor->retirement->readback_attested &&
          closed_pair.editor->retirement->identity==retirement.request.identity && f.adapter.snapshot().widgets.empty(),
          "Owner closure erased the known head's actual checked retirement or completed App close before Take");
    const auto publication_count=f.port->commits.size();
    auto following=packet; ++following.observation.id;
    ne::Revocation revoked; revoked.basis=packet.basis; revoked.incarnation=packet.session; revoked.reason="normal close";
    check(!f.app->editor_submit(following) && !f.app->editor_revoke(revoked),
          "closing App admitted a new editor head after provider detachment");
    f.app->editor_resync();
    for (unsigned turn=0;turn<3;++turn) {
        f.app->set_owned_service_active(true); f.app->set_owned_service_active(false);
        f.app->retry_presentation(); f.app->tick(); f.app->shutdown();
        check(!f.app->shutdown_complete() && !f.adapter.closed() && !f.port->service && f.owner->callback_depth()==0 &&
              f.port->commits.size()==publication_count && f.port->committed.revision==closed_pair.revision &&
              f.port->committed.editor==closed_pair.editor && f.port->committed.surface==closed_pair.surface &&
              f.native_retirements==1,"detached metadata wait republished, entered native work or erased its checked head");
    }
    const auto completion=f.app->editor_take(*head);
    check(completion && completion->ticket==*head && completion->result.admission==ne::Admission::completed &&
          completion->result.receipt && completion->result.receipt->outcome==ne::Outcome::applied &&
          completion->result.receipt->session==packet.session && completion->result.receipt->id==packet.observation.id &&
          completion->result.receipt->submitted_token==packet.basis.token &&
          !completion->result.receipt->basis && !completion->result.receipt->default_token &&
          completion->result.receipt->retirement==closed_pair.editor->retirement &&
          !f.app->editor_take(*head) && !f.app->shutdown_complete() && !f.adapter.closed(),
          "normal close lost or fabricated its original one-time known receipt");
    f.app->tick();
    check(f.app->shutdown_complete() && f.adapter.closed() && f.owner->closed() &&
          f.native_retirements==1 && f.port->commits.size()==publication_count,
          "post-Take local turn failed to finish close or entered/replayed native work");
    }
    // Terminal evidence stays a close barrier. This is the final fixture in
    // its fresh process; no later enabled Owner is constructed after poison.
    {
    ActionsFixture f; f.activate(); f.app->shutdown(); f.app->tick();
    const auto cleanup=f.peek_editor();
    check(cleanup && cleanup->work.kind==EngineEditorWorkKind::revoke,"terminal close omitted its actual native9 work");
    const Bytes forensic{0xf0,0x9f,0x97,0x83};
    f.finish_editor(*cleanup,forensic,2,0,0,true);
    f.app->tick(); f.app->shutdown(); f.app->tick();
    check(!f.owner->closed() && !f.app->shutdown_complete() && f.app->view().widgets.empty(),
          "unknown native retirement was reported as completed App closure");
    }
}
void actions_foreign_close_callback() {
    ActionsFixture f; f.activate();
    const auto packet=text_packet(f.basis());
    ne::Revocation revoked; revoked.basis=packet.basis; revoked.incarnation=packet.session; revoked.reason="foreign close";
    f.app->shutdown(); f.app->tick(); const auto cleanup=f.peek_editor();
    check(cleanup && cleanup->work.kind==EngineEditorWorkKind::revoke && f.owner->editor_enabled() &&
          !f.owner->closed() && !f.adapter.closed() && !f.app->shutdown_complete() && !f.native_retirements,
          "foreign callback fixture did not preserve its open publisher and unentered close retirement");
    const auto revision=f.adapter.snapshot().revision; const auto publications=f.port->commits.size();
    bool observed_terminal=false, submitted=false, revoked_head=false;
    std::thread foreign([&] {
        f.app->editor_resync();
        observed_terminal=!f.owner->editor_enabled();
        submitted=f.app->editor_submit(packet).has_value();
        revoked_head=f.app->editor_revoke(revoked).has_value();
    });
    foreign.join();
    check(observed_terminal && !submitted && !revoked_head && !f.owner->editor_enabled() &&
          !f.owner->closed() && f.owner->callback_depth()==0 && !f.native_retirements &&
          f.adapter.snapshot().revision==revision && f.app->view().revision==revision &&
          f.port->commits.size()==publications && !f.app->shutdown_complete(),
          "closing App ignored foreign editor callbacks or performed native/renderer work from their thread");
    f.app->tick(); f.app->shutdown(); f.app->tick();
    check(!f.owner->closed() && !f.app->shutdown_complete() && f.app->view().widgets.empty() && !f.native_retirements,
          "foreign editor callback invented native retirement or completed uncertain closure");
}
} // namespace

int main(int argc,char** argv) {
    const std::array<std::pair<std::string_view,void(*)()>,9> tests{{
        {"exact4083 admission",actions_exact_admission},
        {"view-only actual frames",actions_read_only_frames},
        {"view-only Registry redaction",+[] { actions_registry_effect(false); }},
        {"interactive checked editor head",actions_interactive_checked_head},
        {"interactive Registry editor9",+[] { actions_registry_effect(true); }},
        {"historical full-target editor9",actions_historical_retirement},
        {"normal close after Owner retirement",actions_close_after_owner_retirement},
        {"known head metadata close",actions_known_head_close},
        {"foreign editor close callback",actions_foreign_close_callback}
    }};
    if (argc==2 && std::string_view(argv[1])=="--list") {
        for (const auto& [name,test]:tests) { (void)test; std::cout << name << '\n'; } return 0;
    }
    if (argc!=3 || std::string_view(argv[1])!="--case") {
        std::cerr << "Use --list or --case NAME; each case requires a fresh process\n"; return 2;
    }
    const auto selected=std::find_if(tests.begin(),tests.end(),[&](const auto& value) { return value.first==argv[2]; });
    if (selected==tests.end()) { std::cerr << "Unknown actions bitmap case: " << argv[2] << '\n'; return 2; }
    try {
        selected->second(); ++groups;
        std::cout << "PASS " << selected->first << ": " << groups << " cases, " << assertions
                  << " assertions, 0 skipped; real4083 Owner/Registry/Policy, synthetic provider replies\n";
    } catch (const std::exception& error) { std::cerr << selected->first << ": " << error.what() << '\n'; return 1; }
    return 0;
}
