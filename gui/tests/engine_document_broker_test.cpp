// SPDX-License-Identifier: CC0-1.0
#include "shared/engine_document_broker.hpp"
#include "shared/appended_engine_abi.h"

#include <algorithm>
#include <array>
#include <cstdint>
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

// A synthetic provider fixture, not an engine implementation or runtime gate.
// The real Owner, broker, native-v2 decoder and FormDraft run against independently
// assembled complete wire replies. No SDK, browser or engine is entered.
namespace foundation::ui {
struct EngineDocumentBrokerTestAccess {
    static auto candidate(const EngineDocumentBroker& value) { return value.publication_candidate(); }
    static bool commit(EngineDocumentBroker& value,
                       std::shared_ptr<const EngineDocumentBroker::Publication> publication,
                       std::uint64_t revision,
                       EngineDocumentBroker::CommitKind kind = EngineDocumentBroker::CommitKind::normal) {
        return value.publication_committed(std::move(publication),revision,kind);
    }
    static void ready(EngineDocumentBroker& value, bool ready) { value.form_admission_ready(ready); }
    static void suspend(EngineDocumentBroker& value, EngineDocumentBroker::Suspension reason) { value.suspend(reason); }
    static bool quiescent(const EngineDocumentBroker& value) { return value.native_effect_quiescent(); }
    static bool form_gate(const EngineDocumentBroker& value) { return value.form_gate_required(); }
    static std::optional<std::uint64_t> reserve_legacy(EngineDocumentBroker& value) { return value.reserve_legacy(); }
    static bool legacy_pending(const EngineDocumentBroker& value) { return value.legacy_pending(); }
    static std::unique_ptr<EngineDocumentBroker> legacy(std::shared_ptr<appended::EngineOwner> owner,
        std::function<std::optional<DocumentFormsRequest>()> next,
        std::function<bool(DocumentFormsRequestToken,DocumentFormsCompletion)> complete,
        std::function<bool(DocumentFormsRequestToken,DocumentRequestFailure)> fail,
        std::function<bool()> presentation_pending,std::function<void(const char*)> failure) {
        EngineDocumentBroker::LegacyBindings bindings;
        bindings.next=std::move(next); bindings.complete=std::move(complete); bindings.fail=std::move(fail);
        bindings.progress=[]{}; bindings.presentation_pending=std::move(presentation_pending);
        bindings.can_stage=[]{return true;}; bindings.fresh_query=[]{return false;}; bindings.barrier=[]{return 1;};
        bindings.query_delivered=[](DocumentFormsRequestToken,appended::EngineDocumentTarget,std::uint64_t,bool){};
        bindings.failure=std::move(failure);
        return std::unique_ptr<EngineDocumentBroker>(new EngineDocumentBroker(std::move(owner),std::move(bindings)));
    }
};
}

namespace {
using namespace foundation::appended;
namespace D = foundation::gui_document;
namespace U = foundation::ui;
namespace profile = foundation::appended::engine_editor;
namespace document = foundation::appended::engine_document;
using Broker = U::EngineDocumentBroker;
using Access = U::EngineDocumentBrokerTestAccess;
using Span = std::span<const std::uint8_t>;
std::size_t assertions{};
void check(bool value, const char* reason) {
    ++assertions;
    if (!value) throw std::runtime_error(reason);
}
void put(std::span<std::uint8_t> bytes, std::size_t at, std::uint64_t value, unsigned width) {
    if (at > bytes.size() || width > bytes.size()-at) throw std::logic_error("fixture write bounds");
    for (unsigned n=0;n<width;++n) bytes[at+n]=static_cast<std::uint8_t>(value>>(8*n));
}
std::uint64_t get(Span bytes, std::size_t at, unsigned width) {
    if (at > bytes.size() || width > bytes.size()-at) throw std::logic_error("fixture read bounds");
    std::uint64_t value{};
    for (unsigned n=0;n<width;++n) value|=std::uint64_t(bytes[at+n])<<(8*n);
    return value;
}
EngineDocumentTarget target(EngineIdentity value) {
    return {value.worker_epoch,value.application_instance,value.document_sequence,value.service_generation};
}
EngineIdentity identity(EngineDocumentTarget value) {
    return {value.worker_epoch,value.application_instance,value.document_sequence,value.service_generation};
}
struct Wire {
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
                     std::string_view native_value, std::uint64_t lease=0, std::uint64_t control_node=10) {
        id(value); version(value,revision); integer(0,1);
        integer(revision,8); integer(control_node,8); integer(0,4); integer(0,4);
        integer(6,4); integer(0,4); integer(1,4); integer(0,1);
        node(1,0,1,3,"body");
        node(control_node,1,1,0,"input",{},"First field",native_value);
        node(70,1,1,1,"a",{},"Ordinary project link",{},"guide.html");
        node(71,70,2,0,{},"Ordinary project link");
        node(80,1,1,1,"p"); node(81,80,2,0,{},"Paired body observation");
        integer(control_node,8); integer(0,1); integer(4|8|32,1); integer(1|16,4); integer(1,1); integer(lease!=0,1);
        text("text"); text("First field");
        if (lease) { version(value,revision); integer(control_node,8); integer(lease,8); }
        text(native_value); text(native_value); integer(1,1);
        integer(0,4); integer(0,4); integer(0,1); // An actual native caret, valid for ASCII and multibyte fixtures.
    }
};
Bytes query_reply(const EngineDocumentDispatch& request, std::uint64_t revision, std::string_view value,
                  std::uint64_t control_node=10, std::uint64_t lease=0) {
    Wire wire; wire.header(4,request); wire.publication(request.work.target,revision,value,lease,control_node); return wire.bytes;
}
Bytes form_reply(const EngineDocumentDispatch& request, std::uint64_t revision,
                 std::string_view value, std::uint64_t lease, unsigned outcome=0, unsigned code=0) {
    Wire wire; wire.header(5,request); wire.integer(outcome,1); wire.integer(code,1);
    wire.integer(outcome==1 ? 0 : 1,1); wire.integer(outcome==0,1);
    if (outcome==0) wire.publication(request.work.target,revision,value,lease,get(request.work.payload,73,8));
    return wire.bytes;
}
Bytes ack_reply(std::uint64_t sequence, unsigned code=0) {
    Bytes bytes(16); put(bytes,0,sequence,8); put(bytes,8,code,4); return bytes;
}
Package package() {
    Package value;
    value.application={"org.example.document-broker","Document broker fixture","1.0.0"};
    value.web.present=true; value.web.entry="web/index.html";
    value.capabilities={"foundation.startup.v1"}; value.package_sha256=std::string(64,'1');
    const std::string startup="{\"kind\":\"foundation-appended-startup\",\"primary\":\"web\",\"schema_version\":1}";
    value.files={{"web/.foundation/startup-v1.json","web","application/json",std::string(64,'2'),Bytes(startup.begin(),startup.end())},
        {"web/index.html","web","text/html",std::string(64,'3'),{}}};
    return value;
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
    value.build_sha256.fill(0x31); value.source_recipe_sha256.fill(0x42); // Synthetic, never retained engine provenance.
    value.queries=profile::kQueries; value.commands=profile::kCommands; value.query_count=2; value.command_count=7;
    check(profile::editor_profile_valid(value),"fixture2035 facts failed exact validation"); return value;
}
struct Reply {
    EngineIdentity id;
    std::uint64_t transfer{};
    std::uint32_t control{},service{};
    Bytes bytes;
    Span body() const { return Span(bytes).subspan(80); }
};
Reply call(EngineOwner& owner, std::uint32_t operation, EngineIdentity id, Span body={}, std::uint64_t transfer=0) {
    Bytes input(72+body.size()); std::copy_n("FKB1",4,input.begin());
    put(input,4,1,2); put(input,6,operation,2); put(input,8,input.size(),4);
    put(input,16,id.worker_epoch,8); put(input,24,id.application_instance,8);
    put(input,32,id.document_sequence,8); put(input,40,id.service_generation,8); put(input,48,transfer,8);
    put(input,64,body.size(),4); std::copy(body.begin(),body.end(),input.begin()+72);
    Bytes output(80+FOUNDATION_ENGINE_DOCUMENT_MAX_RESULT_BODY_BYTES);
    const auto count=owner.dispatch(operation,input,output);
    check(count>=80 && static_cast<std::size_t>(count)<=output.size(),"Owner omitted complete copied receipt");
    output.resize(static_cast<std::size_t>(count));
    check(get(output,6,2)==(operation|0x8000) && get(output,8,4)==output.size() && get(output,64,4)==output.size()-72,
        "Owner copied framing changed");
    return {{get(output,16,8),get(output,24,8),get(output,32,8),get(output,40,8)},get(output,48,8),
        static_cast<std::uint32_t>(get(output,72,4)),static_cast<std::uint32_t>(get(output,76,4)),std::move(output)};
}
void ok(const Reply& value) { check(value.control==FOUNDATION_ENGINE_OK && !value.service,"Owner rejected expected fixture operation"); }

struct Fixture {
    EngineIdentity id{17,UINT64_C(0x8000000000000023),0,0};
    const profile::EngineEditorProfileFacts facts=editor_facts();
    std::shared_ptr<EngineOwner> owner;
    std::unique_ptr<Broker> broker;
    std::uint64_t revision{13}, snapshot_revision{1000}, lease{9001};
    unsigned claims{},turns{},results{};
    std::string native_value{"Native original"};
    Fixture() {
        EngineOwnerConfiguration config;
        config.worker_epoch=id.worker_epoch; config.application_instance=id.application_instance;
        config.editor_profile=facts; config.abandon_closed_document_outcomes=true;
        owner=std::make_shared<EngineOwner>(package(),std::move(config));
        ok(call(*owner,FOUNDATION_ENGINE_CONFIGURE,id)); id.document_sequence=UINT64_C(0x8000000000000001);
        const auto begun=call(*owner,FOUNDATION_ENGINE_BEGIN_DOCUMENT,id); ok(begun); id=begun.id;
        broker=std::make_unique<Broker>(owner,facts); Access::ready(*broker,true);
        check(owner->editor_enabled() && owner->document_enabled(),"exact2035 did not expose existing document lane");
    }
    std::optional<EngineDocumentDispatch> peek() {
        const auto reply=call(*owner,FOUNDATION_ENGINE_PEEK_DOCUMENT_WORK,owner->identity());
        if (reply.control==FOUNDATION_ENGINE_EMPTY || reply.control==FOUNDATION_ENGINE_CLOSED) return {};
        ok(reply); check(reply.transfer && reply.body().size()>=56,"Owner omitted owned document work");
        EngineDocumentDispatch result; result.transfer=reply.transfer; auto& work=result.work;
        work.target=target(reply.id); work.kind=static_cast<EngineDocumentWorkKind>(get(reply.body(),0,4));
        work.operation=static_cast<std::uint32_t>(get(reply.body(),4,4)); work.request_sequence=get(reply.body(),8,8);
        std::copy_n(reply.body().begin()+16,32,work.schema_sha256.begin());
        work.required_reply_capacity=static_cast<std::uint32_t>(get(reply.body(),48,4));
        check(get(reply.body(),52,4)==reply.body().size()-56,"Owner copied work length changed");
        work.payload.assign(reply.body().begin()+56,reply.body().end()); return result;
    }
    EngineDocumentDispatch work(bool publish_preentry=false) {
        for (unsigned n=0;n<8;++n) {
            broker->tick();
            // This option is used only BEFORE the fixture supplies any native
            // result. It accepts FormDraft's local pending-state publication.
            if (publish_preentry) if (const auto publication=Access::candidate(*broker))
                check(Access::commit(*broker,publication,++snapshot_revision),"pre-entry publication commit failed");
            if (auto value=peek()) return *value;
        }
        throw std::runtime_error("broker failed to stage expected Owner work");
    }
    void claim(const EngineDocumentDispatch& request, bool enter=true) {
        Bytes body(16); put(body,0,static_cast<unsigned>(request.work.kind),4); put(body,8,request.work.request_sequence,8);
        ok(call(*owner,FOUNDATION_ENGINE_BEGIN_DOCUMENT_WORK,identity(request.work.target),body,request.transfer)); ++claims;
        if (enter) {
            check(request.work.kind!=EngineDocumentWorkKind::action_ack,"ACK fixture attempted native TURN");
            ok(call(*owner,FOUNDATION_ENGINE_TURN_ENTER,identity(request.work.target),{},request.transfer));
            ok(call(*owner,FOUNDATION_ENGINE_TURN_LEAVE,identity(request.work.target),{},request.transfer)); ++turns;
        }
    }
    void result(const EngineDocumentDispatch& request, Span raw, unsigned disposition,
                bool handled=false, std::uint64_t semantic_revision=0, std::int32_t status=0) {
        Bytes body(40+raw.size()); put(body,0,static_cast<unsigned>(request.work.kind),4);
        put(body,8,request.work.request_sequence,8); put(body,16,static_cast<std::uint32_t>(status),4);
        put(body,20,disposition,4); put(body,24,raw.size(),4); put(body,28,handled,4); put(body,32,semantic_revision,8);
        std::copy(raw.begin(),raw.end(),body.begin()+40);
        ok(call(*owner,FOUNDATION_ENGINE_DOCUMENT_WORK_RESULT,identity(request.work.target),body,request.transfer)); ++results;
    }
    D::Ticket submit(D::Intent intent) {
        const auto value=broker->submit(std::move(intent));
        check(value.admission==D::Admission::accepted && value.ticket && value.ticket->value,"public intent not admitted");
        return *value.ticket;
    }
    void finish_query(const EngineDocumentDispatch& request, std::uint64_t control_node=10, std::uint64_t query_lease=0) {
        check(request.work.kind==EngineDocumentWorkKind::snapshot_query && request.work.operation==3 &&
            request.work.schema_sha256==document::kSchema && request.work.required_reply_capacity==document::kReplyCapacity,
            "broker lost exact query3 catalog");
        check(request.work.target==target(id) && request.work.payload.size()==48 && get(request.work.payload,0,4)==0x3256444e &&
            get(request.work.payload,8,8)==id.application_instance && get(request.work.payload,16,8)==id.service_generation &&
            get(request.work.payload,24,8)==id.document_sequence && get(request.work.payload,32,8)==request.work.request_sequence &&
            get(request.work.payload,40,8),"broker remapped full query identity or nested token");
        claim(request); result(request,query_reply(request,revision,native_value,control_node,query_lease),0,false,revision);
    }
    void finish_form(const EngineDocumentDispatch& request, unsigned outcome=0, unsigned code=0,
                     bool explicit_finish_successor=false) {
        check(request.work.kind==EngineDocumentWorkKind::form_action && request.work.operation==6 &&
            request.work.schema_sha256==document::kSchema && request.work.required_reply_capacity==document::kReplyCapacity,
            "broker lost exact form6 catalog");
        check(request.work.target==target(id) && request.work.payload.size()>=81 && get(request.work.payload,0,4)==0x3256444e &&
            get(request.work.payload,4,4)==0x00020002 && get(request.work.payload,8,8)==id.application_instance &&
            get(request.work.payload,16,8)==id.service_generation && get(request.work.payload,24,8)==id.document_sequence &&
            get(request.work.payload,32,8)==request.work.request_sequence && !get(request.work.payload,40,8),
            "broker changed native form identity, sequence or reserved bytes");
        claim(request); ++revision;
        const bool finish=get(request.work.payload,48,1)==5;
        if (!finish || explicit_finish_successor) ++lease;
        // The selected Publisher's accepted Finish has no successor. Keep an
        // explicit variant to prove an unexpected owned successor is retained.
        result(request,form_reply(request,revision,native_value,finish&&!explicit_finish_successor?0:lease,outcome,code),1,true);
    }
    auto candidate() {
        for (unsigned n=0;n<8;++n) { broker->tick(); if (auto value=Access::candidate(*broker)) return value; }
        throw std::runtime_error("broker omitted candidate publication");
    }
    auto commit_candidate() {
        const auto value=candidate();
        check(Access::commit(*broker,value,++snapshot_revision),"exact publication commit refused");
        broker->tick(); return value;
    }
    D::Completion take(D::Ticket ticket) {
        for (unsigned n=0;n<8;++n) { broker->tick(); if (auto value=broker->take(ticket)) {
            check(value->ticket==ticket,"local take changed endpoint ticket");
            check(!broker->take(ticket),"local metadata take was not exactly once"); return *value;
        } }
        throw std::runtime_error("known completion remained unavailable after publication/ACK");
    }
    EngineDocumentDispatch ack(const EngineDocumentDispatch& action, unsigned code=0) {
        const auto request=work();
        check(request.work.kind==EngineDocumentWorkKind::action_ack && request.work.operation==7 &&
            request.work.target==action.work.target && request.work.request_sequence>action.work.request_sequence &&
            request.work.payload==encode_u64(action.work.request_sequence) && request.work.schema_sha256==document::kAckSchema &&
            request.work.required_reply_capacity==16,"ACK7 changed original target/action or independent sequence/catalog");
        const auto before=turns; claim(request,false); result(request,ack_reply(action.work.request_sequence,code),1);
        check(turns==before,"ACK7 entered a native TURN"); broker->tick(); return request;
    }
    D::Observation observe() {
        const auto ticket=submit(D::Observe{}); const auto query=work(); finish_query(query);
        const auto publication=commit_candidate(); const auto completion=take(ticket);
        check(completion.outcome==D::Outcome::completed && completion.observation &&
            publication->state.document && broker->state().document && broker->state().observation==completion.observation,
            "actual paired query did not publish an endpoint observation"); return *completion.observation;
    }
    D::Draft begin() {
        const auto observation=observe(); const auto ticket=submit(D::Begin{observation,10});
        const auto request=work(); check(get(request.work.payload,48,1)==0,"Begin selected another native action");
        finish_form(request); commit_candidate(); ack(request); const auto completion=take(ticket);
        check(completion.outcome==D::Outcome::completed && completion.draft && broker->state().draft &&
            completion.draft->id==broker->state().draft->id && completion.draft->text==native_value,
            "native Begin readback failed to establish public draft"); return completion.draft->id;
    }
    D::Completion local(D::Intent intent) {
        const auto before=claims; const auto ticket=submit(std::move(intent)); commit_candidate();
        const auto completion=take(ticket);
        check(claims==before && !peek(),"local draft intent staged a native provider request"); return completion;
    }
    D::Ticket queue_apply(D::Draft draft) {
        const auto ticket=submit(D::Apply{draft}); const auto publication=candidate();
        check(publication->state.draft && publication->state.draft->apply_queued && !peek(),
            "Apply staged native work before its local queued-state publication");
        check(Access::commit(*broker,publication,++snapshot_revision),"Apply queued-state publication commit failed");
        return ticket;
    }
};

// This test-only legacy compositor ledger supplies typed actions through the
// existing private binding. Real Broker reservation/staging, Owner, decoder and
// publication/ACK fences run against synthetic provider replies; no actual
// engine, GUI adapter, SDK, native lease issuer or retention-count hook is used.
struct LegacyLeaseFixture {
    Fixture native;
    std::optional<U::DocumentFormsRequest> queued;
    std::optional<U::DocumentFormsRequestToken> pending_token;
    std::optional<U::DocumentFormsCompletion> delivered;
    bool presentation_pending{}, reject_completion_once{}, terminal{};
    unsigned completed{}, failed{}, completion_attempts{};
    std::uint64_t nested{};
    LegacyLeaseFixture() {
        native.broker.reset();
        native.broker=Access::legacy(native.owner,[this] {
            auto value=std::move(queued); queued.reset(); return value;
        },[this](auto token,auto value) {
            check(pending_token && token==*pending_token,"legacy delivery changed the actual reserved token");
            ++completion_attempts; delivered=std::move(value);
            if (reject_completion_once) { reject_completion_once=false; return false; }
            pending_token.reset(); presentation_pending=true; ++completed; return true;
        },[this](auto token,auto failure) {
            check(pending_token && token==*pending_token && failure==U::DocumentRequestFailure::known_rejected,
                "lease capacity did not use exact known local rejection");
            pending_token.reset(); ++failed; return true;
        },[this]{return presentation_pending;},[this](const char*){terminal=true;});
    }
    void queue(U::DocumentFormsAction action) {
        check(!queued && !pending_token && !presentation_pending && !Access::legacy_pending(*native.broker),
            "legacy fixture attempted overlapping typed work");
        const auto sequence=Access::reserve_legacy(*native.broker);
        check(sequence.has_value(),"legacy typed request lost the actual Owner reservation");
        pending_token=U::DocumentFormsRequestToken{native.id.application_instance,*sequence};
        queued=U::DocumentFormsRequest{*pending_token,std::move(action)};
    }
    void settle(const EngineDocumentDispatch& request) {
        native.broker->tick();
        if (pending_token) { // exact completion delivery retry, not native replay
            check(!presentation_pending && !native.peek(),"failed delivery staged ACK before exact retry");
            native.broker->tick();
        }
        check(!pending_token && presentation_pending && !native.peek() && Access::legacy_pending(*native.broker),
            "typed result escaped its actual pending publication fence");
        const auto claims=native.claims, turns=native.turns, results=native.results;
        native.broker->tick();
        check(native.claims==claims && native.turns==turns && native.results==results && !native.peek(),
            "pending publication replayed the entered native action");
        presentation_pending=false;
        if (request.work.kind==EngineDocumentWorkKind::form_action) native.ack(request);
        else native.broker->tick();
        check(!Access::legacy_pending(*native.broker) && !native.peek() && !terminal && !native.broker->terminal(),
            "actual typed result/ACK remained pending or became terminal");
    }
    FormLease begin(std::uint64_t node) {
        queue(BeginFormControl{{native.id.application_instance,native.id.service_generation,native.revision},node});
        const auto request=native.work();
        check(get(request.work.payload,48,1)==0 && get(request.work.payload,73,8)==node,
            "legacy Begin changed its actual typed target");
        native.finish_form(request); settle(request);
        const auto* value=delivered?std::get_if<U::DocumentFormsControlReply>(&*delivered):nullptr;
        check(value && value->outcome==FormDraftOutcome::accepted && value->update && value->update->control.lease,
            "typed Begin did not return its actual decoded selected lease");
        const auto lease=*value->update->control.lease;
        check(lease.node==node && lease.id==native.lease,"typed Begin lease was reminted by the fixture");
        return lease;
    }
    void query(std::uint64_t node,std::uint64_t advertised_lease=0) {
        queue(U::DocumentEngineRequest{{native.id.application_instance,++nested},{}});
        const auto request=native.work(); ++native.revision;
        native.finish_query(request,node,advertised_lease); settle(request);
        check(delivered && std::holds_alternative<U::NativeFormsDocumentObservation>(*delivered),
            "readonly query failed instead of preserving its actual owned observation");
    }
    std::optional<FormLease> finish(FormLease expected,unsigned outcome=0,unsigned code=0,
                                   bool successor=false,bool retry=false) {
        queue(FinishFormControl{expected}); const auto request=native.work();
        check(get(request.work.payload,48,1)==5 && get(request.work.payload,73,8)==expected.node &&
            get(request.work.payload,81,8)==expected.id && get(request.work.payload,49,8)==expected.captured.generation &&
            get(request.work.payload,57,8)==expected.captured.epoch && get(request.work.payload,65,8)==expected.captured.revision,
            "Finish lost its exact typed captured native lease");
        const auto before=completion_attempts; reject_completion_once=retry;
        native.finish_form(request,outcome,code,successor); settle(request);
        check(completion_attempts==before+(retry?2:1),"Finish completion retry count differs");
        const auto* value=delivered?std::get_if<U::DocumentFormsControlReply>(&*delivered):nullptr;
        check(value && value->outcome==static_cast<FormDraftOutcome>(outcome),"Finish changed its known decoded outcome");
        return value->update?value->update->control.lease:std::nullopt;
    }
    void refuse_begin(std::uint64_t node) {
        const auto claims=native.claims, turns=native.turns, results=native.results, rejects=failed;
        queue(BeginFormControl{{native.id.application_instance,native.id.service_generation,native.revision},node});
        for (unsigned n=0;n<3;++n) native.broker->tick();
        check(!queued && !pending_token && !presentation_pending && failed==rejects+1 && !native.peek() &&
            native.claims==claims && native.turns==turns && native.results==results &&
            !Access::legacy_pending(*native.broker) && !terminal && !native.broker->terminal(),
            "full lease ledger admitted native work, ACK, eviction or terminal poison");
    }
};

void lease_free_query_preserves_typed_authority() {
    Fixture fixture; const auto draft=fixture.begin();
    const auto captured_revision=fixture.revision, lease=fixture.lease;
    ++fixture.revision; fixture.observe(); // explicitly omits the actual retained lease
    const std::string replacement="Lease survives readonly observation";
    fixture.local(D::EditText{draft,fixture.native_value,replacement});
    const auto ticket=fixture.queue_apply(draft); const auto request=fixture.work(true);
    check(get(request.work.payload,48,1)==1 && get(request.work.payload,49,8)==fixture.id.application_instance &&
        get(request.work.payload,57,8)==fixture.id.service_generation && get(request.work.payload,65,8)==captured_revision &&
        get(request.work.payload,73,8)==10 && get(request.work.payload,81,8)==lease,
        "lease-free query revoked, refreshed or fabricated typed Apply authority");
    fixture.native_value=replacement; fixture.finish_form(request); const auto publication=fixture.candidate();
    check(!fixture.broker->take(ticket) && !fixture.peek(),"lease-preserving Apply escaped publication before ACK");
    check(Access::commit(*fixture.broker,publication,++fixture.snapshot_revision),"lease-preserving Apply publication failed");
    fixture.ack(request); const auto done=fixture.take(ticket);
    check(done.outcome==D::Outcome::completed && done.draft && done.draft->text==replacement && !done.draft->dirty,
        "retained lease Apply lost actual readback or exact ACK completion");
}
void typed_lease_capacity_and_finish_release() {
    LegacyLeaseFixture fixture;
    constexpr std::size_t limit=FormLimits{}.controls;
    constexpr std::uint64_t first=1000, blocked=first+limit;
    fixture.query(90000,40001); // query-only hints must not originate ledger authority
    std::vector<FormLease> leases; leases.reserve(limit);
    for (std::size_t n=0;n<limit;++n) leases.push_back(fixture.begin(first+n));
    fixture.refuse_begin(blocked);
    fixture.query(90001,40002); fixture.refuse_begin(blocked);
    const auto renewed=fixture.begin(first);
    check(renewed!=leases.front(),"retained-node renewal at capacity did not return explicit native successor");
    fixture.refuse_begin(blocked);
    fixture.finish(renewed,1,4); // known no-effects rejection must retain its expected authority
    fixture.refuse_begin(blocked);
    const auto successor=fixture.finish(renewed,0,0,true,true);
    check(successor && *successor!=renewed,"explicit Finish successor was not observed in decoded completion");
    fixture.refuse_begin(blocked); // retry must not erase the different newer lease
    check(!fixture.finish(*successor),"normal accepted Finish fixture invented a successor lease");
    const auto admitted=fixture.begin(blocked);
    check(admitted.node==blocked,"exact accepted Finish/ACK did not free one retained slot");
    fixture.refuse_begin(blocked+1);
}
void successive_closed_sessions_do_not_exhaust_capacity() {
    LegacyLeaseFixture fixture;
    constexpr std::size_t sessions=FormLimits{}.controls+1;
    for (std::size_t n=0;n<sessions;++n) {
        const auto lease=fixture.begin(1000+n);
        check(!fixture.finish(lease),"accepted closed session retained an invented Finish successor");
    }
    check(fixture.completed==2*sessions && !fixture.failed && !fixture.terminal,
        "finite lease cap became a lifetime session quota or lost a completion");
}

void exact_profile_admission() {
    Fixture fixture;
    auto wrong=fixture.facts; wrong.build_sha256[0]^=1;
    bool rejected=false; try { Broker mismatch(fixture.owner,wrong); } catch (const std::invalid_argument&) { rejected=true; }
    check(rejected && !fixture.peek(),"broker accepted different2035 build facts");
    wrong=fixture.facts; wrong.provider_capabilities=2003;
    rejected=false; try { Broker mismatch(fixture.owner,wrong); } catch (const std::invalid_argument&) { rejected=true; }
    check(rejected && !fixture.peek() && !fixture.broker->terminal(),"broker accepted physical2003 or damaged admitted2035 owner");
}
void query_publication_and_take_fence() {
    Fixture fixture; const auto before=fixture.broker->state(); const auto ticket=fixture.submit(D::Observe{});
    check(!fixture.broker->take(ticket) && !fixture.broker->take(D::Ticket{ticket.value+100}) && !fixture.peek(),
        "ingress staged native work or pending/foreign ticket fabricated completion");
    const auto request=fixture.work(); check(request.work.request_sequence==1,"Owner did not issue initial ordinary sequence");
    fixture.finish_query(request); const auto publication=fixture.candidate();
    check(publication->state.document && publication->state.observation,"decoded query omitted candidate content");
    const auto pending=fixture.broker->state();
    check(pending.publication_revision==before.publication_revision && pending.document==before.document &&
        pending.observation==before.observation && !fixture.broker->take(ticket),"uncommitted query escaped publication fence");
    for (unsigned n=0;n<3;++n) fixture.broker->tick();
    check(Access::candidate(*fixture.broker)==publication && fixture.claims==1 && !fixture.peek(),"pending publication replayed native query or replaced candidate");
    check(!Access::commit(*fixture.broker,publication,0),"zero actual presentation revision committed");
    check(Access::commit(*fixture.broker,publication,++fixture.snapshot_revision),"exact query publication commit failed");
    const auto claims=fixture.claims; const auto completion=fixture.take(ticket);
    check(completion.outcome==D::Outcome::completed && completion.observation &&
        fixture.broker->state().publication_revision==fixture.snapshot_revision &&
        fixture.broker->state().document==publication->state.document && fixture.claims==claims && !fixture.peek(),
        "metadata take published, entered provider or lost accepted query");
    check(!Access::commit(*fixture.broker,publication,fixture.snapshot_revision+1),"retired candidate committed a second time");
}
void one_outstanding_ticket() {
    Fixture fixture; const auto ticket=fixture.submit(D::Observe{});
    const auto refused=fixture.broker->submit(D::Observe{});
    check(refused.admission==D::Admission::busy && !refused.ticket,"second live endpoint request bypassed backpressure");
    const auto request=fixture.work(); fixture.finish_query(request); fixture.commit_candidate();
    const auto still=fixture.broker->submit(D::Observe{});
    check(still.admission==D::Admission::busy && !still.ticket,"known but untaken completion lost its endpoint ledger slot");
    fixture.take(ticket); const auto next=fixture.submit(D::Observe{});
    check(next.value!=ticket.value,"endpoint reused a retired local ticket");
    const auto following=fixture.work(); check(following.work.request_sequence>request.work.request_sequence,"native Owner sequence rewound after local take");
    fixture.finish_query(following); fixture.commit_candidate(); fixture.take(next);
}
void begin_requires_publication_then_exact_ack() {
    Fixture fixture; const auto observed=fixture.observe(); const auto before=fixture.broker->state();
    const auto ticket=fixture.submit(D::Begin{observed,10}); const auto request=fixture.work();
    check(get(request.work.payload,48,1)==0 && get(request.work.payload,49,8)==fixture.id.application_instance &&
        get(request.work.payload,57,8)==fixture.id.service_generation && get(request.work.payload,65,8)==fixture.revision &&
        get(request.work.payload,73,8)==10,"Begin changed actual observed version/node");
    fixture.finish_form(request); const auto publication=fixture.candidate();
    check(publication->state.draft && !fixture.broker->state().draft && !fixture.broker->take(ticket) && !fixture.peek(),
        "native Begin issued ACK or exposed draft before presentation");
    check(!Access::quiescent(*fixture.broker),"unpublished native action was reported quiescent");
    check(fixture.broker->state().document==before.document && fixture.broker->state().publication_revision==before.publication_revision,
        "failed/queued Begin presentation replaced accepted content");
    for (unsigned n=0;n<3;++n) fixture.broker->tick();
    check(Access::candidate(*fixture.broker)==publication && fixture.claims==2 && !fixture.peek(),"Begin publication debt repeated form action");
    check(Access::commit(*fixture.broker,publication,++fixture.snapshot_revision),"Begin candidate commit failed");
    const auto ack=fixture.ack(request);
    check(ack.work.request_sequence>request.work.request_sequence && fixture.turns==2,"form ACK minted another native turn");
    const auto completion=fixture.take(ticket);
    check(completion.outcome==D::Outcome::completed && completion.draft && completion.draft->id==publication->state.draft->id &&
        completion.draft->text==fixture.native_value && !fixture.peek(),"Begin local completion lost native readback or replayed");
    check(Access::quiescent(*fixture.broker),"fully published and ACKed local take retained native work");
}
void local_utf8_edit_and_apply() {
    Fixture fixture; const auto draft=fixture.begin(); const std::string edited="A\xc3\xa9\xf0\x9f\x99\x82Z";
    const auto changed=fixture.local(D::EditText{draft,fixture.native_value,edited});
    check(changed.outcome==D::Outcome::completed && fixture.broker->state().draft &&
        fixture.broker->state().draft->text==edited && fixture.broker->state().draft->dirty,"local UTF8 edit lost exact owned bytes");
    fixture.local(D::SelectText{draft,{1,7}});
    check(fixture.broker->state().draft->selection==FormByteSelection{1,7},"source-byte selection became native/display offsets");
    const auto ticket=fixture.queue_apply(draft); const auto request=fixture.work(true); const auto previous=fixture.broker->state();
    check(get(request.work.payload,48,1)==1 && get(request.work.payload,73,8)==10 && get(request.work.payload,81,8)==fixture.lease &&
        get(request.work.payload,89,4)==0 && get(request.work.payload,93,4)==fixture.native_value.size() &&
        get(request.work.payload,98,4)==edited.size() &&
        std::string(request.work.payload.begin()+102,request.work.payload.end())==edited,
        "Apply did not use retained native lease and exact full-buffer replacement");
    fixture.native_value=edited; fixture.finish_form(request); const auto publication=fixture.candidate();
    check(fixture.broker->state().document==previous.document && fixture.broker->state().draft->dirty &&
        !fixture.broker->take(ticket) && !fixture.peek(),"Apply readback/ACK escaped failed publication fence");
    check(Access::commit(*fixture.broker,publication,++fixture.snapshot_revision),"Apply candidate commit failed");
    fixture.ack(request); const auto completion=fixture.take(ticket);
    check(completion.outcome==D::Outcome::completed && completion.draft && completion.draft->text==edited &&
        !completion.draft->dirty,"Apply completion was inferred without native readback");
}
void stale_handles_do_not_stage_work() {
    Fixture fixture; const auto observation=fixture.observe();
    auto refused=fixture.broker->submit(D::Begin{D::Observation{observation.value+123},10});
    check(refused.admission!=D::Admission::accepted && !refused.ticket && !fixture.peek(),"forged observation minted native Begin authority");
    refused=fixture.broker->submit(D::Begin{observation,999});
    check(refused.admission!=D::Admission::accepted && !refused.ticket && !fixture.peek(),"unpublished node minted native Begin authority");
    refused=fixture.broker->submit(D::Apply{D::Draft{9001}});
    check(refused.admission!=D::Admission::accepted && !refused.ticket && !fixture.peek() && !fixture.broker->terminal(),
        "native-looking lease number minted a public draft or poisoned valid endpoint");
}
void form_gate_blocks_begin() {
    Fixture fixture; Access::ready(*fixture.broker,false); const auto observation=fixture.observe();
    const auto submission=fixture.broker->submit(D::Begin{observation,10});
    const auto before=fixture.claims;
    for (unsigned n=0;n<3;++n) fixture.broker->tick();
    check(!fixture.peek() && fixture.claims==before,"Begin bypassed presenter form gate");
    check((submission.admission==D::Admission::accepted)==submission.ticket.has_value(),"form gate returned inconsistent admission/ticket");
    Access::ready(*fixture.broker,true);
    const auto ticket=submission.ticket ? *submission.ticket : fixture.submit(D::Begin{observation,10});
    const auto request=fixture.work(); fixture.finish_form(request); fixture.commit_candidate(); fixture.ack(request); fixture.take(ticket);
}
void foreign_candidate_cannot_commit() {
    Fixture first; Fixture second;
    const auto a=first.submit(D::Observe{}),b=second.submit(D::Observe{});
    const auto qa=first.work(),qb=second.work(); first.finish_query(qa); second.finish_query(qb);
    const auto ca=first.candidate(),cb=second.candidate();
    check(!Access::commit(*first.broker,cb,++first.snapshot_revision) && !first.broker->state().document && !first.broker->take(a),
        "foreign candidate committed by matching serial/local content");
    check(Access::commit(*first.broker,ca,++first.snapshot_revision),"foreign candidate attempt destroyed exact retained candidate");
    first.take(a); check(Access::commit(*second.broker,cb,++second.snapshot_revision),"foreign candidate attempt consumed other broker candidate"); second.take(b);
}
void owner_reservation_defers_without_sequence_remap() {
    Fixture fixture; const auto held=fixture.owner->reserve_document_sequence();
    check(held && *held==1,"fixture failed to hold real first Owner sequence");
    const auto ticket=fixture.submit(D::Observe{});
    for (unsigned n=0;n<3;++n) fixture.broker->tick();
    check(!fixture.peek() && !fixture.broker->take(ticket),"broker bypassed another real Owner reservation");
    check(fixture.owner->cancel_document_sequence(*held),"exact external Owner reservation could not retire");
    const auto request=fixture.work();
    check(request.work.request_sequence>*held && request.work.request_sequence!=ticket.value &&
        get(request.work.payload,32,8)==request.work.request_sequence,
        "broker substituted local ticket for native sequence or rewound burned Owner reservation");
    fixture.finish_query(request); fixture.commit_candidate(); fixture.take(ticket);
}
void earlier_pending_publication_cannot_ack_readback() {
    Fixture fixture; const auto draft=fixture.begin();
    fixture.local(D::EditText{draft,fixture.native_value,"Readback must be published"});
    const auto ticket=fixture.queue_apply(draft);
    std::optional<EngineDocumentDispatch> request;
    // Either the broker withholds native entry until the local pending-state
    // candidate commits, or it must preserve that candidate across completion.
    for (unsigned n=0;n<8 && !request;++n) {
        fixture.broker->tick(); request=fixture.peek();
        if (!request) if (const auto local=Access::candidate(*fixture.broker))
            check(Access::commit(*fixture.broker,local,++fixture.snapshot_revision),"gated pre-entry publication refused");
    }
    check(request.has_value(),"Apply failed to stage after pre-entry publication gates");
    const auto earlier=Access::candidate(*fixture.broker);
    if (earlier) check(earlier->state.draft && earlier->state.draft->phase==FormDraftPhase::pending && earlier->state.draft->dirty,
        "pre-entry candidate misrepresented the outstanding native action");
    fixture.native_value="Readback must be published"; fixture.finish_form(*request); fixture.broker->tick();
    if (earlier) {
        check(Access::candidate(*fixture.broker)==earlier,"completion replaced an uncommitted immutable candidate");
        check(Access::commit(*fixture.broker,earlier,++fixture.snapshot_revision),"earlier exact pending candidate refused");
        fixture.broker->tick();
        check(!fixture.peek() && !fixture.broker->take(ticket),"earlier pending publication acknowledged unpresented native readback");
    }
    const auto readback=fixture.candidate();
    check(readback!=earlier && readback->state.draft && !readback->state.draft->dirty &&
        readback->state.draft->text==fixture.native_value,"native readback lacks its own exact publication candidate");
    check(Access::commit(*fixture.broker,readback,++fixture.snapshot_revision),"native readback publication refused");
    fixture.ack(*request); const auto completion=fixture.take(ticket);
    check(completion.draft && !completion.draft->dirty && completion.draft->text==fixture.native_value,
        "readback completion was released under pre-entry publication");
}
void apply_retains_typed_request_across_owner_busy() {
    Fixture fixture; const auto draft=fixture.begin(); const std::string edited="Retained across busy";
    fixture.local(D::EditText{draft,fixture.native_value,edited}); const auto ticket=fixture.queue_apply(draft);
    const auto pending=fixture.candidate();
    check(pending->state.draft && pending->state.draft->phase==FormDraftPhase::pending &&
        !pending->state.draft->apply_queued && !fixture.peek(),"Apply did not retain its exact pending local publication before entry");
    check(Access::commit(*fixture.broker,pending,++fixture.snapshot_revision),"pending Apply publication refused");
    // Hold the real Owner lane only after both local Apply publications. The
    // drained FormDraft request must survive this unrelated reservation.
    const auto held=fixture.owner->reserve_document_sequence();
    check(held.has_value(),"fixture could not reserve external Owner sequence after local publication");
    const auto claims=fixture.claims,turns=fixture.turns,results=fixture.results;
    for (unsigned n=0;n<5;++n) fixture.broker->tick();
    check(!fixture.peek() && !fixture.broker->take(ticket) && fixture.claims==claims &&
        fixture.broker->state().pending==ticket,"Owner busy lost the drained local request or fabricated completion");
    check(fixture.owner->cancel_document_sequence(*held),"external Owner reservation did not retire exactly");
    const auto request=fixture.work();
    check(request.work.request_sequence>*held && get(request.work.payload,48,1)==1 &&
        get(request.work.payload,73,8)==10 && get(request.work.payload,81,8)==fixture.lease &&
        get(request.work.payload,98,4)==edited.size() && std::string(request.work.payload.begin()+102,request.work.payload.end())==edited,
        "released Owner busy lost or reminted the retained typed Apply");
    const auto redelivered=fixture.peek();
    check(redelivered && redelivered->transfer==request.transfer && redelivered->work.request_sequence==request.work.request_sequence &&
        redelivered->work.payload==request.work.payload,"repeated mailbox read minted another Apply attempt");
    fixture.native_value=edited; fixture.finish_form(request); fixture.commit_candidate(); fixture.ack(request);
    const auto completion=fixture.take(ticket);
    check(completion.outcome==D::Outcome::completed && completion.draft && !completion.draft->dirty &&
        completion.draft->text==edited && fixture.claims==claims+2 && fixture.turns==turns+1 && fixture.results==results+2 && !fixture.peek(),
        "retained Apply failed actual readback/ACK or entered more than once after Owner busy");
}
void clean_apply_is_rejected_without_native_work() {
    Fixture fixture; const auto draft=fixture.begin(); const auto before=fixture.broker->state();
    check(before.draft && !before.draft->dirty,"fixture Begin did not produce a clean draft");
    const auto claims=fixture.claims,turns=fixture.turns; const auto ticket=fixture.submit(D::Apply{draft});
    const auto publication=fixture.candidate();
    check(publication->state.draft && !publication->state.draft->dirty && !publication->state.draft->apply_queued && !fixture.peek(),
        "clean Apply queued a native replacement");
    check(Access::commit(*fixture.broker,publication,++fixture.snapshot_revision),"clean Apply local refusal publication failed");
    const auto completion=fixture.take(ticket);
    check(completion.outcome==D::Outcome::rejected && completion.draft && !completion.draft->dirty &&
        completion.draft->text==before.draft->text && fixture.claims==claims && fixture.turns==turns &&
        !fixture.peek() && !fixture.broker->terminal(),"clean Apply became accepted or issued native work/ACK");
}
void service_safe_redaction_and_explicit_query_restore() {
    Fixture fixture; const auto initial_claims=fixture.claims;
    Access::suspend(*fixture.broker,Broker::Suspension::service);
    check(!Access::candidate(*fixture.broker) && !fixture.broker->pending() &&
        !fixture.broker->state().document && fixture.claims==initial_claims && !fixture.peek(),
        "unused sidecar created lifecycle publication debt or entered native work");
    Access::ready(*fixture.broker,true); // Actual App readiness is restored after the empty service pulse.
    const auto draft=fixture.begin(); const auto old_lease=fixture.lease;
    const std::string saved="Retained unsaved service draft";
    fixture.local(D::EditText{draft,fixture.native_value,saved});
    const auto before=fixture.broker->state(); const auto claims=fixture.claims;
    check(!before.pending && before.observation && before.document && before.draft,"service fixture still had pending work or lacked accepted content");
    Access::suspend(*fixture.broker,Broker::Suspension::service); const auto safe=fixture.candidate();
    check(!safe->state.pending && !safe->state.observation && !safe->state.document && !safe->state.draft && !safe->state.available,
        "headless service suspension failed to offer a complete safe redaction");
    check(fixture.broker->state().publication_revision==before.publication_revision && fixture.broker->state().document==before.document &&
        !fixture.broker->state().available && fixture.claims==claims && !fixture.peek(),"uncommitted safe redaction replaced content or entered provider");
    check(!Access::commit(*fixture.broker,safe,fixture.snapshot_revision+1,Broker::CommitKind::normal),
        "safe redaction accepted an ordinary commit proof");
    check(!Access::commit(*fixture.broker,safe,0,Broker::CommitKind::safe_redaction),"safe redaction accepted zero actual revision");
    check(Access::candidate(*fixture.broker)==safe &&
        Access::commit(*fixture.broker,safe,++fixture.snapshot_revision,Broker::CommitKind::safe_redaction),"exact safe redaction commit refused");
    const auto redacted=fixture.broker->state();
    check(redacted.publication_revision==fixture.snapshot_revision && !redacted.available && !redacted.pending &&
        !redacted.observation && !redacted.document && !redacted.draft && fixture.claims==claims,
        "safe commit retained public authority, fabricated request metadata or entered provider");
    check(!Access::form_gate(*fixture.broker),"saved readonly local buffer blocked ordinary HTML physical rearm");
    Access::suspend(*fixture.broker,Broker::Suspension::service);
    check(!Access::candidate(*fixture.broker) && !fixture.broker->pending() &&
        fixture.broker->state().publication_revision==redacted.publication_revision && fixture.claims==claims && !fixture.peek(),
        "repeated empty redaction created another publication or native obligation");
    // Suspension cleared form readiness. A new explicit readonly query must
    // still traverse the real Owner lane and publish fresh observation content.
    Access::ready(*fixture.broker,false); const auto ticket=fixture.submit(D::Observe{}); const auto query=fixture.work();
    fixture.finish_query(query); const auto restored=fixture.commit_candidate(); const auto completion=fixture.take(ticket);
    check(completion.outcome==D::Outcome::completed && completion.observation && completion.observation!=before.observation &&
        restored->state.document && fixture.broker->state().document==restored->state.document &&
        fixture.broker->state().available && fixture.broker->state().draft &&
        fixture.broker->state().draft->id==draft && fixture.broker->state().draft->text==saved &&
        fixture.broker->state().draft->phase==FormDraftPhase::closed && !Access::form_gate(*fixture.broker) &&
        fixture.claims==claims+1 && !fixture.peek(),
        "explicit query3 did not restore fresh readonly content while form gate remained closed");
    // Recover only through a second actual paired query, fresh Begin and fresh
    // lease. The saved local buffer cannot directly restore native authority.
    Access::ready(*fixture.broker,true); const auto reapply=fixture.submit(D::Reapply{draft});
    const auto recovery_query=fixture.work(); fixture.finish_query(recovery_query); fixture.commit_candidate();
    check(!fixture.broker->take(reapply),"recovery query alone completed Reapply");
    const auto fresh_begin=fixture.work();
    check(get(fresh_begin.work.payload,48,1)==0,"saved service draft skipped actual fresh Begin");
    fixture.finish_form(fresh_begin); fixture.commit_candidate(); fixture.ack(fresh_begin);
    const auto fresh_lease=fixture.lease; const auto replacement=fixture.work(true);
    check(fresh_lease!=old_lease && get(replacement.work.payload,81,8)==fresh_lease &&
        std::string(replacement.work.payload.begin()+102,replacement.work.payload.end())==saved,
        "Reapply reused the pre-service lease or lost the retained unsaved buffer");
    fixture.native_value=saved; fixture.finish_form(replacement); fixture.commit_candidate(); fixture.ack(replacement);
    const auto recovered=fixture.take(reapply);
    check(recovered.outcome==D::Outcome::completed && recovered.draft && recovered.draft->id==draft &&
        recovered.draft->text==saved && !recovered.draft->dirty,"fresh-lease Reapply did not finish with actual native readback");
}
void known_preentry_rejection_has_no_ack() {
    Fixture fixture; const auto observed=fixture.observe(); const auto before=fixture.broker->state();
    const auto ticket=fixture.submit(D::Begin{observed,10}); const auto request=fixture.work();
    const auto turns=fixture.turns; fixture.claim(request,false); fixture.result(request,{},0,false,0,-5);
    fixture.commit_candidate(); const auto completion=fixture.take(ticket);
    check(completion.outcome==D::Outcome::rejected && fixture.turns==turns && !fixture.peek() &&
        fixture.broker->state().document==before.document && !fixture.broker->state().draft,
        "known pre-entry refusal became native acceptance, ACK or replay");
}
void stale_ack_does_not_release_action() {
    Fixture fixture; const auto observation=fixture.observe(); const auto ticket=fixture.submit(D::Begin{observation,10});
    const auto request=fixture.work(); fixture.finish_form(request); fixture.commit_candidate(); fixture.ack(request,2);
    const auto claims=fixture.claims;
    for (unsigned n=0;n<4;++n) fixture.broker->tick();
    check(fixture.broker->terminal() && !fixture.broker->take(ticket) && fixture.claims==claims && !fixture.peek(),
        "stale ACK2 released original action or retried provider retirement");
}
void terminal_unknown_never_acks_or_replays() {
    Fixture fixture; const auto draft=fixture.begin(); fixture.local(D::EditText{draft,fixture.native_value,"Never replay"});
    const auto ticket=fixture.queue_apply(draft); const auto request=fixture.work(true); fixture.claim(request);
    const auto before=fixture.broker->state(); const auto raw=form_reply(request,fixture.revision+1,"FORGED_SUCCESS",fixture.lease+1);
    fixture.result(request,raw,2,true); const auto claims=fixture.claims;
    for (unsigned n=0;n<5;++n) fixture.broker->tick();
    check(fixture.broker->terminal() && fixture.claims==claims && !fixture.peek(),"unknown transport ACKed, replayed or resumed provider work");
    check(fixture.broker->state().document==before.document && fixture.broker->state().publication_revision==before.publication_revision &&
        (!fixture.broker->state().draft || fixture.broker->state().draft->text!="FORGED_SUCCESS"),"unknown bytes became accepted native observation");
    const auto refused=fixture.broker->submit(D::Observe{});
    check(refused.admission!=D::Admission::accepted && !refused.ticket,"terminal uncertainty accepted fresh Observe");
    check(!fixture.broker->take(ticket),"terminal transport fabricated a local completion");
}
void malformed_consumed_reply_is_terminal() {
    Fixture fixture; const auto ticket=fixture.submit(D::Observe{}); const auto request=fixture.work(); fixture.claim(request);
    auto raw=query_reply(request,fixture.revision,fixture.native_value); raw.push_back(0x7f);
    fixture.result(request,raw,0,false,fixture.revision); const auto claims=fixture.claims;
    for (unsigned n=0;n<4;++n) fixture.broker->tick();
    check(fixture.broker->terminal() && fixture.claims==claims && !fixture.peek() && !fixture.broker->state().document,
        "malformed deep native packet published, replayed or ACKed");
    check(!fixture.broker->take(ticket),"malformed packet fabricated a local completion");
}
void terminal_notification_is_metadata_only() {
    Fixture fixture; fixture.observe(); const auto before=fixture.claims;
    fixture.broker->notify_terminal(); fixture.broker->notify_terminal();
    check(fixture.broker->terminal() && fixture.claims==before,"trusted terminal notification entered provider");
    for (unsigned n=0;n<3;++n) fixture.broker->tick();
    const auto refused=fixture.broker->submit(D::Observe{});
    check(refused.admission!=D::Admission::accepted && !refused.ticket && !fixture.peek(),"terminal metadata notification repaired/replayed endpoint");
}
void local_shutdown_does_not_issue_cleanup() {
    Fixture fixture; const auto draft=fixture.begin(); fixture.local(D::EditText{draft,fixture.native_value,"Unsaved"});
    const auto before=fixture.claims; fixture.broker->shutdown(); fixture.broker->shutdown();
    for (unsigned n=0;n<3;++n) fixture.broker->tick();
    const auto refused=fixture.broker->submit(D::Apply{draft});
    check(refused.admission!=D::Admission::accepted && !refused.ticket && fixture.claims==before && !fixture.peek(),
        "shutdown submitted native Finish/Apply/ACK or remained accepting");
}
}

int main(int argc, char** argv) {
    using Test=std::pair<const char*,void(*)()>;
    const std::array<Test,22> tests{{
        {"exact editor2035 profile admission",exact_profile_admission},
        {"query3 publication and metadata take fence",query_publication_and_take_fence},
        {"one outstanding local ticket",one_outstanding_ticket},
        {"form6 publication before exact ACK7",begin_requires_publication_then_exact_ack},
        {"local UTF8 edit selection and native Apply",local_utf8_edit_and_apply},
        {"stale public handles cannot stage work",stale_handles_do_not_stage_work},
        {"form presenter gate blocks Begin",form_gate_blocks_begin},
        {"foreign publication candidate cannot commit",foreign_candidate_cannot_commit},
        {"Owner reservation preserves native sequence",owner_reservation_defers_without_sequence_remap},
        {"earlier pending publication cannot ACK native readback",earlier_pending_publication_cannot_ack_readback},
        {"Apply retains typed request across Owner busy",apply_retains_typed_request_across_owner_busy},
        {"clean Apply is rejected without native work",clean_apply_is_rejected_without_native_work},
        {"service safe redaction and explicit query restore",service_safe_redaction_and_explicit_query_restore},
        {"known pre-entry rejection has no ACK",known_preentry_rejection_has_no_ack},
        {"stale ACK2 cannot release action",stale_ack_does_not_release_action},
        {"unknown transport has no ACK or replay",terminal_unknown_never_acks_or_replays},
        {"malformed native packet is terminal",malformed_consumed_reply_is_terminal},
        {"terminal notification is metadata only",terminal_notification_is_metadata_only},
        {"local shutdown issues no cleanup",local_shutdown_does_not_issue_cleanup},
        {"lease-free query preserves typed native authority",lease_free_query_preserves_typed_authority},
        {"typed native lease capacity rejects before effects and Finish releases it",typed_lease_capacity_and_finish_release},
        {"successive closed native form sessions do not exhaust lease capacity",successive_closed_sessions_do_not_exhaust_capacity}
    }};
    // Owner uncertainty quarantines document profiles for process lifetime.
    // The external test harness gives each named case a fresh process; this
    // fixture never forks, starts a shell or resets terminal authority.
    if (argc==2 && std::string_view(argv[1])=="--list") {
        for (const auto& [name,test]:tests) { (void)test; std::cout<<name<<'\n'; } return 0;
    }
    if (argc!=3 || std::string_view(argv[1])!="--case") {
        std::cerr<<"Use --list or --case NAME; every case requires a fresh process\n"; return 2;
    }
    const auto selected=std::find_if(tests.begin(),tests.end(),[&](const auto& value){return std::string_view(value.first)==argv[2];});
    if (selected==tests.end()) { std::cerr<<"Unknown case: "<<argv[2]<<'\n'; return 2; }
    try {
        selected->second(); std::cout<<"PASS "<<selected->first<<"\n1 cases, "<<assertions<<" assertions, 0 skipped\n"; return 0;
    } catch (const std::exception& error) {
        std::cerr<<selected->first<<": "<<error.what()<<" (0 complete cases, "<<assertions<<" assertions)\n"; return 1;
    }
}
