// SPDX-License-Identifier: CC0-1.0
#include "engine_document_broker.hpp"
#include <algorithm>
#include <atomic>
#include <limits>
#include <map>
#include <stdexcept>
#include <thread>
#include <type_traits>
#include <utility>

namespace foundation::ui {
namespace A = appended;
namespace D = gui_document;
namespace {
A::EngineDocumentTarget document_target(A::EngineIdentity value) {
    return {value.worker_epoch,value.application_instance,value.document_sequence,value.service_generation};
}
DocumentV2Identity native_identity(A::EngineDocumentTarget value) {
    return {value.application_instance,value.service_generation,value.document_sequence};
}
bool ready_target(A::EngineDocumentTarget value) {
    return value.worker_epoch && value.application_instance && value.document_sequence && value.service_generation;
}
bool body_request(const DocumentFormsRequest& value) {
    const auto* request=std::get_if<DocumentEngineRequest>(&value.action);
    return (request && request->intent) || std::holds_alternative<ChooseSingleDocumentOption>(value.action) ||
        std::holds_alternative<ActivateDocumentControl>(value.action);
}
bool editable_control(const A::FormControl& value) {
    return value.complete && !value.omitted && !value.disabled && !value.read_only && value.focusable &&
        ((value.kind==A::FormKind::text || value.kind==A::FormKind::number || value.kind==A::FormKind::textarea) ?
            A::form_has(value.capabilities,A::FormCapability::replace_text) :
         value.kind==A::FormKind::checkbox ? A::form_has(value.capabilities,A::FormCapability::set_checked) :
         value.kind==A::FormKind::select_many && A::form_has(value.capabilities,A::FormCapability::set_option));
}
}

struct EngineDocumentBroker::Impl {
    struct Reservation { std::uint64_t sequence{},barrier{}; A::EngineDocumentTarget target; };
    struct Work {
        DocumentFormsRequest source;
        A::EngineDocumentWork native;
        std::optional<DocumentV2Request> request;
        std::optional<DocumentActionV1Request> body;
        std::uint64_t barrier{};
        bool fresh{}, local_rejected{}, delivered{}, published{};
        std::uint64_t publication_version{};
        std::optional<A::EngineDocumentTicket> ticket,ack;
        std::shared_ptr<const A::EngineDocumentCompletion> result;
        std::optional<DocumentV2Reply> decoded;
        std::optional<DocumentBodyCompletion> body_decoded;
    };
    std::shared_ptr<A::EngineOwner> owner;
    const std::thread::id thread{std::this_thread::get_id()};
    const bool legacy;
    LegacyBindings bindings;
    std::optional<Reservation> held;
    std::optional<DocumentFormsRequest> returned;
    bool returned_rejected{};
    std::optional<Work> work;
    A::EngineDocumentTarget current;
    std::uint64_t barrier{1}, next_ticket{}, next_observation{}, next_draft{}, next_candidate{}, draft_generation{}, content_version{}, candidate_version{};
    std::optional<D::Ticket> head;
    std::optional<D::Intent> intent;
    std::optional<D::Completion> completion;
    std::unique_ptr<EngineDocumentDraftSession> draft;
    std::optional<D::Draft> draft_id;
    std::optional<A::FormUpdate> fresh_update;
    std::optional<A::FormDraftView> draft_snapshot, recovery_saved;
    std::optional<A::FormDraftRequest> drained_request;
    enum class RecoveryStep { none, query, begin, local };
    RecoveryStep recovery_step{RecoveryStep::none};
    std::shared_ptr<const Publication> candidate;
    std::optional<D::State> successor;
    D::State accepted;
    std::optional<D::Observation> observed;
    std::shared_ptr<const NativeFormsDocumentObservation> document;
    std::map<std::uint64_t,A::FormLease> leases;
    AppendedDocument retained_body;
    std::optional<A::FormUpdate> native_readback;
    std::atomic<bool> poisoned{false};
    bool stopped{}, ticking{}, mutating{}, suspended{}, form_ready{}, observation_usable{}, finishing{};
    bool local_action{}, needs_refresh{}, content_redacted{};
    D::Outcome head_outcome{D::Outcome::completed};
    std::string detail;

    Impl(std::shared_ptr<A::EngineOwner> value,bool old,LegacyBindings callbacks={})
        : owner(std::move(value)),legacy(old),bindings(std::move(callbacks)) {
        if (!owner || !owner->configured() || owner->closed() || !owner->document_enabled() ||
            !owner->identity().application_instance) throw std::invalid_argument("No configured document broker Owner");
        current=document_target(owner->identity());
        if (legacy && (!bindings.next || !bindings.complete || !bindings.fail || !bindings.progress ||
            !bindings.presentation_pending || !bindings.can_stage || !bindings.fresh_query || !bindings.barrier ||
            !bindings.query_delivered || !bindings.failure)) throw std::invalid_argument("Incomplete document compositor binding");
    }
    void check_thread() const {
        if (thread!=std::this_thread::get_id()) throw std::logic_error("Document broker requires its serialized owner");
    }
    std::uint64_t issue(std::uint64_t& counter) {
        if (counter==std::numeric_limits<std::uint64_t>::max()) {
            terminal(); throw std::overflow_error("Document broker local identity exhausted");
        }
        return ++counter;
    }
    bool terminal_state() const noexcept { return poisoned.load(std::memory_order_acquire) || !owner->document_enabled(); }
    void terminal(const char* reason="Native document outcome is unknown") noexcept {
        poisoned.store(true,std::memory_order_release); owner->notify_document_terminal();
        if (legacy) { try { bindings.failure(reason); } catch (...) {} }
    }
    void cancel_held() noexcept {
        if (held) { (void)owner->cancel_document_sequence(held->sequence); held.reset(); }
    }
    bool can_stage() const {
        return !stopped && !terminal_state() && !owner->callback_depth() &&
            (legacy ? bindings.can_stage() : !suspended);
    }
    std::uint64_t current_barrier() const { return legacy ? bindings.barrier() : barrier; }
    void watch() {
        const auto latest=document_target(owner->identity());
        if (latest!=current) {
            current=latest; observation_usable=false; leases.clear(); form_ready=false;
            if (!legacy) {
                issue(barrier); needs_refresh=true; native_readback.reset(); content_redacted=true;
                if (!work || !work->ticket) retire_draft_authority();
                propose();
            }
            retire_unadmitted();
        }
    }
    std::optional<std::uint64_t> reserve() {
        watch();
        if (!can_stage() || held || work || !ready_target(current)) return {};
        const auto value=owner->reserve_document_sequence();
        if (value) held=Reservation{*value,current_barrier(),current};
        return value;
    }
    void retire_unadmitted() noexcept {
        if (returned) returned_rejected=true;
        if (work && !work->ticket) work->local_rejected=true;
        cancel_held();
    }
    void local_rejection() {
        if (returned && returned_rejected && legacy && bindings.fail(returned->token,DocumentRequestFailure::known_rejected)) {
            returned.reset(); returned_rejected=false;
        }
        if (work && work->local_rejected) {
            if (legacy) {
                if (bindings.fail(work->source.token,DocumentRequestFailure::known_rejected)) work.reset();
            } else {
                const auto before=content_version;
                reject_draft(work->source);
                if(draft)draft->cancel_recovery();
                recovery_step=RecoveryStep::none;recovery_saved.reset();
                head_outcome=D::Outcome::rejected; detail="Native document work was not admitted";
                work.reset(); if(content_version==before)propose();
            }
        }
    }
    void reject_draft(const DocumentFormsRequest& source) {
        if (const auto* action=std::get_if<A::FormDraftRequest>(&source.action)) {
            if (content_redacted && (!draft || draft->view().phase==A::FormDraftPhase::closed))
                return; // known unadmitted lifecycle retirement
            if (!draft || !draft->complete(action->token,A::FormDraftOutcome::rejected))
                throw std::invalid_argument("Known refusal lost its retained local draft request");
        }
    }
    static constexpr std::size_t retained_lease_limit=A::FormLimits{}.controls;
    void validate_lease_capacity(const DocumentFormsRequest& source) const {
        const auto check=[&](const auto& action) {
            using T=std::decay_t<decltype(action)>;
            if constexpr (std::is_same_v<T,A::BeginFormControl> || std::is_same_v<T,A::OpenFormPopup>) {
                if (!leases.contains(action.node) && leases.size()>=retained_lease_limit)
                    throw std::invalid_argument("Retained native form lease limit reached");
            }
        };
        if (const auto* begin=std::get_if<A::BeginFormControl>(&source.action)) check(*begin);
        else if (const auto* request=std::get_if<A::FormDraftRequest>(&source.action))
            std::visit(check,request->action);
    }
    void remember_leases(const Work& value,const DocumentV2Reply& reply) {
        if (value.native.kind==A::EngineDocumentWorkKind::snapshot_query) {
            // A query can refresh authority acquired by a typed command, but
            // neither a new hint nor an omitted lease originates/revokes it.
            if (reply.publication) for (const auto& control:reply.publication->observation.forms.controls)
                if (control.lease) if (const auto known=leases.find(control.node); known!=leases.end())
                    known->second=*control.lease;
            return;
        }
        const A::FinishFormControl* finish=std::get_if<A::FinishFormControl>(&value.source.action);
        if (const auto* request=std::get_if<A::FormDraftRequest>(&value.source.action))
            finish=std::get_if<A::FinishFormControl>(&request->action);
        if (finish && reply.control && reply.control->outcome==A::FormDraftOutcome::accepted) {
            const auto known=leases.find(finish->expected.node);
            if (known!=leases.end() && known->second==finish->expected) leases.erase(known);
        }
        // The decoder selects only this typed request's target. Capacity for
        // a new Begin/Open was checked before staging; other actions already
        // require an exact retained lease. Never import unrelated hints after
        // effects. Preserve an explicit successor even for Finish, and never
        // erase that newer lease when delivery of the old result is retried.
        if (reply.control && reply.control->update && reply.control->update->control.lease)
            leases[reply.control->update->control.node]=*reply.control->update->control.lease;
    }
    void validate_lease(const DocumentFormsRequest& source) const {
        const A::FormLease* expected=nullptr;
        if (const auto* request=std::get_if<A::FormDraftRequest>(&source.action)) {
            std::visit([&](const auto& action) {
                using T=std::decay_t<decltype(action)>;
                if constexpr (!std::is_same_v<T,A::BeginFormControl> && !std::is_same_v<T,A::OpenFormPopup>) expected=&action.expected;
            },request->action);
        } else if (const auto* finish=std::get_if<A::FinishFormControl>(&source.action)) expected=&finish->expected;
        if (expected) {
            const auto known=leases.find(expected->node);
            if (known==leases.end() || known->second!=*expected) throw std::invalid_argument("No exact retained native form lease");
        }
    }
    bool prepare(DocumentFormsRequest source) {
        if (!held || source.token.sequence!=held->sequence || source.token.generation!=current.application_instance)
            throw std::invalid_argument("Document request lost its exact Owner reservation");
        Work value; value.source=std::move(source); value.barrier=held->barrier;
        value.native.target=held->target; value.native.request_sequence=held->sequence;
        if (body_request(value.source)) {
            if (!legacy || !owner->document_actions_enabled() || !bindings.encode_body)
                throw std::invalid_argument("Native body action requires document-actions4083");
            value.body=bindings.encode_body(value.source,held->target,held->sequence);
            if (!value.body) throw std::invalid_argument("Invalid typed native body action");
            value.native.kind=A::EngineDocumentWorkKind::body_action;
            value.native.operation=BIB_ENGINE_COMMAND_DOCUMENT_ACTION_V1;
            value.native.schema_sha256=A::engine_document_actions::kSchema;
            value.native.required_reply_capacity=BIB_ENGINE_DOCUMENT_ACTIONS_V1_REPLY_CAPACITY;
            value.native.payload.assign(value.body->bytes.begin(),value.body->bytes.end());
        } else {
            validate_lease(value.source);
            validate_lease_capacity(value.source);
            value.request=encode_appended_document_v2(native_identity(held->target),value.source);
            const bool query=value.request->kind==DocumentV2RequestKind::snapshot_query;
            value.native.kind=query ? A::EngineDocumentWorkKind::snapshot_query : A::EngineDocumentWorkKind::form_action;
            value.native.operation=query ? BIB_ENGINE_QUERY_DOCUMENT_FORMS_V2 : BIB_ENGINE_COMMAND_FORM_ACTION_V2;
            value.native.schema_sha256=A::engine_document::kSchema;
            value.native.required_reply_capacity=BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY;
            value.native.payload=value.request->bytes;
            value.fresh=query && (legacy ? bindings.fresh_query() : needs_refresh);
        }
        work=std::move(value); return true;
    }
    bool decode_reply(Work& value) {
        const auto& result=*value.result;
        try {
            if (value.body) {
                if (!bindings.decode_body || result.semantic_revision || result.bytes.size()>max_document_action_v1_reply_bytes)
                    throw std::invalid_argument("Malformed native body result");
                if (!value.body_decoded) value.body_decoded=bindings.decode_body(result.bytes,*value.body);
            } else {
                if (!value.request || result.bytes.size()>max_document_v2_reply_bytes)
                    throw std::invalid_argument("Malformed native document result");
                if (!value.decoded) value.decoded=decode_appended_document_v2(result.bytes,*value.request);
            }
            return true;
        } catch (const std::invalid_argument&) {
            terminal("Malformed native document packet"); return false;
        }
    }
    void stage() {
        if (!work || work->ticket || work->local_rejected || !can_stage()) return;
        if (!legacy && candidate) return;
        if (!legacy && work->native.kind==A::EngineDocumentWorkKind::form_action && !form_ready) return;
        watch();
        if (work->barrier!=current_barrier() || work->native.target!=current) {
            work->local_rejected=true; cancel_held(); return;
        }
        const auto admitted=owner->stage_document_work(work->native);
        if (admitted.code==A::EngineDocumentAdmissionCode::busy) return;
        if (admitted.code==A::EngineDocumentAdmissionCode::admitted && admitted.ticket) {
            work->ticket=admitted.ticket; held.reset();
            if (work->native.kind!=A::EngineDocumentWorkKind::snapshot_query) observation_usable=false;
        } else {
            work->local_rejected=true; cancel_held();
            if (legacy && bindings.rejection) bindings.rejection("Native document work was not admitted");
        }
    }
    void prepare_legacy() {
        local_rejection();
        if (work || returned_rejected || !can_stage()) return;
        if (!returned) returned=bindings.next();
        if (!returned) return;
        watch();
        if (!held) { terminal("Document request lost its exact Owner reservation"); return; }
        if (held->barrier!=current_barrier() || held->target!=current) {
            returned_rejected=true; cancel_held(); local_rejection(); return;
        }
        try { (void)prepare(*returned); returned.reset(); }
        catch (const std::invalid_argument& error) {
            if(bindings.rejection)bindings.rejection(error.what());
            cancel_held(); returned_rejected=true; local_rejection();
        }
    }
    D::DraftView draft_view() const {
        const auto& value=*draft_snapshot;
        return {*draft_id,value.base.control.kind,value.phase,value.text,value.selection,value.checked,
            value.dirty,value.apply_queued,value.option};
    }
    void expose_successor() {
        if (candidate || !successor) return;
        candidate=std::shared_ptr<const Publication>(new Publication(issue(next_candidate),std::move(*successor)));
        candidate_version=content_version; successor.reset();
    }
    void propose() {
        if (legacy || (!head && !content_redacted) || terminal_state()) return;
        // An unused or already redacted sidecar has no accepted authority to
        // withdraw. Local lifecycle metadata alone must not create presentation
        // debt behind an unrelated exact editor completion.
        if (!head && !work && !held && !returned && !accepted.observation &&
            !accepted.document && !accepted.draft) return;
        D::State value=accepted;
        value.observation=observed; value.document=document;
        value.draft=draft_snapshot && draft_id ? std::optional<D::DraftView>(draft_view()) : std::nullopt;
        if (content_redacted) { value.observation.reset(); value.document.reset(); value.draft.reset(); }
        value.pending=head; value.phase=D::Phase::waiting_publication;
        value.available=!suspended && !stopped && !content_redacted; value.publication_revision=0;
        issue(content_version); successor=std::move(value); expose_successor();
    }
    void draft_published(const A::FormDraftView& value) { draft_snapshot=value; propose(); }
    void close_draft() noexcept {
        if (draft) draft->close();
        draft.reset(); draft_id.reset(); draft_snapshot.reset(); drained_request.reset();
        recovery_saved.reset(); recovery_step=RecoveryStep::none; fresh_update.reset();
    }
    void retire_draft_authority() {
        if (draft) {
            // Preserve only the unsaved local buffer and local handle. Closing
            // FormDraft clears its request and permanently disables this lease;
            // recover() later requires an actual fresh Begin and a new session.
            draft->close(); draft_snapshot=draft->view();
        }
        drained_request.reset(); recovery_saved.reset();
        recovery_step=RecoveryStep::none; fresh_update.reset();
    }
    void validate_query(const NativeFormsDocumentObservation& value) {
        if (document && value.publication==document->publication && value.forms.controls!=document->forms.controls)
            throw std::invalid_argument("Native forms publication reused with different values");
        if (native_readback && value.publication.generation==native_readback->version.generation &&
            value.publication.epoch==native_readback->version.epoch) {
            if (value.publication.revision<native_readback->version.revision)
                throw std::invalid_argument("Paired snapshot predates actual native readback");
            if (value.publication==native_readback->version) {
                const auto found=std::find_if(value.forms.controls.begin(),value.forms.controls.end(),
                    [&](const auto& control){return control.node==native_readback->control.node;});
                if (found==value.forms.controls.end() || !A::form_control_state_matches(*found,native_readback->control))
                    throw std::invalid_argument("Paired snapshot conflicts with actual native readback");
            }
        }
        if (!value.body.snapshot) throw std::invalid_argument("Paired query omitted body snapshot");
        retained_body.accept(*value.body.snapshot);
    }
    bool deliver_endpoint(Work& value,const DocumentV2Reply& reply) {
        const auto before=content_version;
        if (value.native.kind==A::EngineDocumentWorkKind::snapshot_query) {
            if (!reply.publication) return false;
            validate_query(reply.publication->observation);
            auto copied=std::make_shared<const NativeFormsDocumentObservation>(reply.publication->observation);
            document=std::move(copied); observed=D::Observation{issue(next_observation)};
            if (value.native.target==current && value.barrier==current_barrier() && !suspended && !owner->native_effect())
                content_redacted=false;
            observation_usable=value.native.target==current && !suspended && !content_redacted;
            // Readonly query3 does not revoke an actual retained Begin lease.
            // Common delivery refreshes only previously acquired node authority.
            if (draft && draft_id) {
                const auto node=draft->view().base.control.node;
                const auto found=std::find_if(document->forms.controls.begin(),document->forms.controls.end(),
                    [&](const auto& control){return control.node==node;});
                if (found==document->forms.controls.end()) {
                    retire_draft_authority(); head_outcome=D::Outcome::rejected; detail="The native control is no longer present";
                } else {
                    (void)draft->observe({document->publication,*found});
                }
            }
            if (recovery_step==RecoveryStep::query) recovery_step=RecoveryStep::begin;
            needs_refresh=!observation_usable;
            if(content_version==before)propose();
            return true;
        }
        if (!reply.control || !reply.action_status) return false;
        if (reply.control->outcome==A::FormDraftOutcome::unknown) { terminal(); return false; }
        if (reply.control->update && value.native.target==current) native_readback=*reply.control->update;
        if (const auto* begin=std::get_if<A::BeginFormControl>(&value.source.action)) {
            (void)begin;
            if (reply.control->outcome==A::FormDraftOutcome::accepted && reply.control->update && reply.control->update->control.lease) {
                if (recovery_step==RecoveryStep::begin && draft && recovery_saved) {
                    fresh_update=*reply.control->update;
                    const bool reapply=intent && std::holds_alternative<D::Reapply>(*intent);
                    if (!draft->recover(*recovery_saved,*fresh_update,reapply)) {
                        head_outcome=D::Outcome::rejected; detail="Draft recovery requires a compatible fresh native lease";
                        recovery_step=RecoveryStep::none;
                    } else {
                        recovery_step=RecoveryStep::local;
                        (void)draft->recovery_generation(issue(draft_generation));
                        (void)draft->advance_recovery([this]{return !candidate && !suspended && !terminal_state();});
                    }
                } else {
                    draft_id=D::Draft{issue(next_draft)};
                    draft=std::make_unique<EngineDocumentDraftSession>(issue(draft_generation),*reply.control->update,
                        [this](const auto& state){draft_published(state);});
                }
            } else {
                head_outcome=D::Outcome::rejected; detail="Native form Begin rejected";
                recovery_step=RecoveryStep::none; recovery_saved.reset();
            }
        } else if (const auto* action=std::get_if<A::FormDraftRequest>(&value.source.action)) {
            if (!draft || !draft->complete(action->token,reply.control->outcome,reply.control->update)) return false;
        } else if (std::holds_alternative<A::FinishFormControl>(value.source.action)) {
            close_draft(); finishing=false;
            needs_refresh=true;
        }
        if (reply.control->outcome==A::FormDraftOutcome::rejected) head_outcome=D::Outcome::rejected;
        if(content_version==before)propose();
        return true;
    }
    bool deliver(Work& value) {
        const auto& result=*value.result;
        if (result.outcome==A::EngineDocumentOutcome::rejected || result.outcome==A::EngineDocumentOutcome::cancelled) {
            if (legacy) return bindings.fail(value.source.token,DocumentRequestFailure::known_rejected);
            const auto before=content_version;
            reject_draft(value.source);
            if(draft)draft->cancel_recovery();
            recovery_step=RecoveryStep::none;recovery_saved.reset();
            head_outcome=result.outcome==A::EngineDocumentOutcome::cancelled ? D::Outcome::cancelled : D::Outcome::rejected;
            if(content_version==before)propose();
            return true;
        }
        if (result.outcome!=A::EngineDocumentOutcome::consumed) { terminal(); return false; }
        const bool query=value.native.kind==A::EngineDocumentWorkKind::snapshot_query;
        if (result.provider_status || result.provider_disposition!=(query ? 0u : 1u) || (query && result.handled)) {
            terminal("Malformed consumed document result"); return false;
        }
        if (value.body) {
            if (!decode_reply(value)) return false;
            return bindings.complete(value.source.token,*value.body_decoded);
        }
        if (!decode_reply(value)) return false;
        const auto& decoded=*value.decoded;
        if ((query && (!decoded.publication || decoded.control || result.semantic_revision!=decoded.publication->observation.publication.revision)) ||
            (!query && (!decoded.control || !decoded.action_status || result.semantic_revision))) {
            terminal("Malformed native paired document result"); return false;
        }
        if (!legacy && decoded.control && decoded.control->outcome==A::FormDraftOutcome::unknown) { terminal(); return false; }
        remember_leases(value,decoded);
        if (!legacy) {
            try { return deliver_endpoint(value,decoded); }
            catch (const std::invalid_argument&) { terminal("Conflicting native document observation"); return false; }
        }
        if (query) {
            if (!bindings.complete(decoded.token,decoded.publication->observation)) return false;
            bindings.query_delivered(decoded.token,value.native.target,value.barrier,value.fresh);
            return true;
        }
        return bindings.complete(decoded.token,*decoded.control);
    }
    bool retire_ack(Work& value) {
        if (!value.ack) {
            const auto admitted=value.body ? owner->stage_document_body_action_ack(value.native.target,value.native.request_sequence) :
                owner->stage_document_action_ack(value.native.target,value.native.request_sequence);
            if (admitted.code==A::EngineDocumentAdmissionCode::busy) return false;
            if (admitted.code!=A::EngineDocumentAdmissionCode::admitted || !admitted.ticket) { terminal("Native action ACK admission failed"); return false; }
            value.ack=admitted.ticket;
        }
        const auto ack=owner->document_outcome(*value.ack); if (!ack) return false;
        bool receipt=false;
        if (value.body) receipt=bindings.body_ack && bindings.body_ack(ack->bytes,value.native.request_sequence);
        else {
            const auto decoded=A::decode_engine_document_action_ack(ack->bytes);
            receipt=decoded && decoded->original_action_sequence==value.native.request_sequence && decoded->code!=A::EngineDocumentAckCode::stale;
        }
        if (ack->ticket!=*value.ack || ack->target!=value.native.target ||
            ack->kind!=(value.body ? A::EngineDocumentWorkKind::body_action_ack : A::EngineDocumentWorkKind::action_ack) ||
            ack->request_sequence<=value.native.request_sequence || ack->outcome!=A::EngineDocumentOutcome::consumed ||
            ack->provider_status || ack->provider_disposition!=1 || ack->handled || ack->semantic_revision || !receipt) {
            terminal("Native action ACK remains unproven"); return false;
        }
        return owner->consume_document_outcome(*value.ack);
    }
    void settle() {
        local_rejection();
        if (!work || !work->ticket || terminal_state()) return;
        auto& value=*work;
        if (!value.result) value.result=owner->document_outcome(*value.ticket);
        if (!value.result) return;
        const auto& result=*value.result;
        if (result.ticket!=*value.ticket || result.target!=value.native.target || result.request_sequence!=value.native.request_sequence ||
            result.kind!=value.native.kind || !result.transfer || result.outcome==A::EngineDocumentOutcome::unknown) {
            terminal(); return;
        }
        if (!value.delivered) {
            if (!deliver(value)) return;
            value.delivered=true; value.publication_version=content_version;
        }
        if (terminal_state()) return;
        // Presentation exceptions belong to the retained actual GUI candidate;
        // they must propagate without converting it to malformed native data.
        if (legacy) { bindings.progress(); if (bindings.presentation_pending()) return; }
        else if (!value.published || candidate) return;
        if (A::engine_document_action_kind(value.native.kind) && result.outcome==A::EngineDocumentOutcome::consumed)
            if (!retire_ack(value)) return;
        if (!owner->consume_document_outcome(*value.ticket)) return;
        work.reset();
        if (!legacy) {
            if (content_redacted) { retire_draft_authority(); leases.clear(); }
            finish_head();
        }
    }
    void finish_head() {
        if (!head || work || candidate || terminal_state()) return;
        if (drained_request || recovery_step!=RecoveryStep::none || (draft && draft->recovery_pending())) return;
        if (draft && intent && (std::holds_alternative<D::Apply>(*intent) || std::holds_alternative<D::Reapply>(*intent)) &&
            (draft->view().apply_queued || draft->request_pending())) return;
        completion=D::Completion{*head,head_outcome,accepted.observation,accepted.draft,detail};
    }
    void queue_endpoint_work(DocumentFormsAction action) {
        const auto sequence=reserve(); if (!sequence) return;
        DocumentFormsRequest source{{current.application_instance,*sequence},std::move(action)};
        try { (void)prepare(source); }
        catch (const std::invalid_argument& error) {
            cancel_held(); const auto before=content_version;
            reject_draft(source); drained_request.reset(); local_action=true;
            if(draft)draft->cancel_recovery();
            recovery_step=RecoveryStep::none;recovery_saved.reset();
            head_outcome=D::Outcome::rejected; detail=error.what();
            if(content_version==before)propose();
        }
    }
    void process_intent() {
        if (!intent || !head || work || candidate || completion || terminal_state()) return;
        const bool recovering=std::holds_alternative<D::Reload>(*intent) || std::holds_alternative<D::Reapply>(*intent);
        if (recovering && draft) {
            if (!local_action) {
                recovery_saved=draft->view(); recovery_step=RecoveryStep::query; local_action=true;
            }
            if (recovery_step==RecoveryStep::query) {
                queue_endpoint_work(DocumentEngineRequest{{current.application_instance,head->value},{}});
                return;
            }
            if (recovery_step==RecoveryStep::begin) {
                if (!form_ready || !document || !recovery_saved) return;
                const auto node=recovery_saved->base.control.node;
                const auto found=std::find_if(document->forms.controls.begin(),document->forms.controls.end(),
                    [&](const auto& control){return control.node==node;});
                if (found==document->forms.controls.end() || !editable_control(*found)) {
                    recovery_step=RecoveryStep::none; head_outcome=D::Outcome::rejected;
                    detail="A fresh editable native control is required for recovery"; propose(); return;
                }
                queue_endpoint_work(A::BeginFormControl{document->publication,node}); return;
            }
            if (recovery_step==RecoveryStep::local) {
                if (draft->recovery_install_pending()) (void)draft->recovery_generation(issue(draft_generation));
                const auto progress=draft->advance_recovery([this]{return !candidate && !suspended && !terminal_state();});
                if (progress==EngineDocumentDraftSession::RecoveryProgress::blocked) {
                    draft->cancel_recovery(); recovery_step=RecoveryStep::none;
                    head_outcome=D::Outcome::rejected; detail="Saved draft cannot be reapplied"; propose(); return;
                }
                if (progress!=EngineDocumentDraftSession::RecoveryProgress::completed) return;
                recovery_step=RecoveryStep::none; recovery_saved.reset();
            }
            if (candidate) return;
            if (std::holds_alternative<D::Reload>(*intent) || head_outcome!=D::Outcome::completed) { finish_head(); return; }
        }
        if (const auto* begin=std::get_if<D::Begin>(&*intent)) {
            if (local_action) { finish_head(); return; }
            if (!document || !observation_usable || !observed || begin->observation!=*observed) {
                head_outcome=D::Outcome::rejected; detail="Stale document observation"; local_action=true; propose(); return;
            }
            if (!form_ready) return;
            queue_endpoint_work(A::BeginFormControl{document->publication,begin->node});
            if (work) local_action=true;
        } else if (std::holds_alternative<D::Observe>(*intent)) {
            if (local_action) { finish_head(); return; }
            queue_endpoint_work(DocumentEngineRequest{{current.application_instance,head->value},{}});
            if (work) local_action=true;
        } else if (draft && (std::holds_alternative<D::Apply>(*intent) || std::holds_alternative<D::Reapply>(*intent))) {
            if (!local_action) {
                local_action=true;
                if (!draft->handle(A::ApplyFormDraft{})) head_outcome=D::Outcome::rejected;
                if (!candidate) propose();
            }
            if (candidate || !form_ready) return;
            // FormDraft drains once. Preserve that exact typed request while
            // another Owner reservation or its pending publication is busy.
            if (!drained_request) drained_request=draft->next_request();
            if (candidate) return;
            if (drained_request) {
                queue_endpoint_work(*drained_request);
                if (work) drained_request.reset();
            } else finish_head();
        } else if (draft && (std::holds_alternative<D::Finish>(*intent) || std::holds_alternative<D::Cancel>(*intent))) {
            if (local_action) { finish_head(); return; }
            if (!form_ready) return;
            const auto& view=draft->view();
            const auto lease=view.base.control.lease;
            const bool retained=lease && leases.contains(lease->node) && leases.at(lease->node)==*lease;
            if (retained && A::form_has(view.base.control.capabilities,A::FormCapability::finish)) {
                queue_endpoint_work(A::FinishFormControl{*lease}); if (work) local_action=true;
            } else {
                close_draft(); local_action=true; needs_refresh=true; propose();
            }
        } else finish_head();
    }
};

EngineDocumentBroker::EngineDocumentBroker(std::shared_ptr<A::EngineOwner> owner,
    const A::engine_document::EngineDocumentProfileFacts& facts) {
    if (!owner || !A::engine_document::document_profile_agrees(facts,owner->document_profile()) || owner->editor_enabled())
        throw std::invalid_argument("Document broker requires its exact document profile");
    impl_=std::make_unique<Impl>(std::move(owner),false);
}
EngineDocumentBroker::EngineDocumentBroker(std::shared_ptr<A::EngineOwner> owner,
    const A::engine_editor::EngineEditorProfileFacts& facts) {
    if (!owner || !A::engine_editor::editor_profile_agrees(facts,owner->editor_profile()) || owner->document_actions_enabled())
        throw std::invalid_argument("Document broker requires exact editor2035 facts");
    impl_=std::make_unique<Impl>(std::move(owner),false);
}
EngineDocumentBroker::EngineDocumentBroker(std::shared_ptr<A::EngineOwner> owner,LegacyBindings bindings)
    : impl_(std::make_unique<Impl>(std::move(owner),true,std::move(bindings))) {}
EngineDocumentBroker::~EngineDocumentBroker() = default;
D::Submission EngineDocumentBroker::submit(D::Intent intent) {
    auto& s=*impl_; s.check_thread();
    if (s.legacy || s.stopped || s.terminal_state()) return {D::Admission::closed,{}};
    if (s.ticking || s.mutating || s.head || s.work || s.candidate) return {D::Admission::busy,{}};
    if (s.suspended || !ready_target(document_target(s.owner->identity()))) return {D::Admission::unavailable,{}};
    if (const auto* begin=std::get_if<D::Begin>(&intent)) {
        if (s.draft || !s.observation_usable || !s.observed || begin->observation!=*s.observed || !s.document) return {D::Admission::stale,{}};
        const auto found=std::find_if(s.document->forms.controls.begin(),s.document->forms.controls.end(),[&](const auto& c){return c.node==begin->node;});
        if (found==s.document->forms.controls.end() || !editable_control(*found)) return {D::Admission::invalid,{}};
    } else if (!std::holds_alternative<D::Observe>(intent)) {
        const auto id=std::visit([](const auto& value)->std::optional<D::Draft> {
            using T=std::decay_t<decltype(value)>;
            if constexpr (!std::is_same_v<T,D::Observe> && !std::is_same_v<T,D::Begin>) return value.draft;
            else return {};
        },intent);
        if (!s.draft || !s.draft_id || id!=s.draft_id) return {D::Admission::stale,{}};
        if (std::holds_alternative<D::Finish>(intent) && s.draft->view().dirty) return {D::Admission::invalid,{}};
    }
    s.head=D::Ticket{s.issue(s.next_ticket)}; s.intent=std::move(intent); s.local_action=false;
    s.head_outcome=D::Outcome::completed; s.detail.clear(); s.completion.reset();
    // No FormDraft callback or native reservation is invoked inside ingress.
    return {D::Admission::accepted,s.head};
}
std::optional<D::Completion> EngineDocumentBroker::take(D::Ticket ticket) {
    auto& s=*impl_;s.check_thread();
    if (s.terminal_state() || !s.head || *s.head!=ticket || !s.completion || s.work || s.candidate) return {};
    auto result=*s.completion; result.observation=s.accepted.observation;result.draft=s.accepted.draft;
    s.completion.reset();s.head.reset();s.intent.reset();s.local_action=false;return result;
}
D::State EngineDocumentBroker::state() const {
    const auto& s=*impl_;s.check_thread();auto result=s.accepted;
    result.available=!s.stopped && !s.suspended && !s.content_redacted && !s.terminal_state();result.pending=s.head;
    result.phase=s.terminal_state()?D::Phase::terminal:s.candidate?D::Phase::waiting_publication:
        s.work?(s.work->ack?D::Phase::waiting_ack:D::Phase::waiting_native):
        s.completion?D::Phase::waiting_take:s.head?D::Phase::queued:D::Phase::idle;
    return result;
}
void EngineDocumentBroker::tick() {
    auto& s=*impl_;s.check_thread();if(s.legacy){s.settle();s.prepare_legacy();s.stage();return;}
    if(s.ticking || s.mutating || s.stopped || s.terminal_state() || s.owner->callback_depth())return;
    struct Guard{bool& value;Guard(bool& v):value(v){value=true;}~Guard(){value=false;}} guard(s.ticking);
    s.watch();s.settle();if(s.terminal_state())return;
    if(s.intent && !s.local_action && s.draft && !s.work && !s.candidate) {
        bool local=false,accepted=true;
        std::visit([&](const auto& value){using T=std::decay_t<decltype(value)>;
            if constexpr(std::is_same_v<T,D::EditText>){local=true;accepted=s.draft->handle(A::EditFormDraft{value.base_text,value.text});}
            else if constexpr(std::is_same_v<T,D::SelectText>){local=true;accepted=s.draft->selection(value.selection);}
            else if constexpr(std::is_same_v<T,D::SetChecked>){local=true;accepted=s.draft->handle(A::CheckFormDraft{value.checked});}
            else if constexpr(std::is_same_v<T,D::SetOption>){local=true;accepted=s.draft->handle(A::OptionFormDraft{value.node,value.selected});}
        },*s.intent);
        if(local){
            s.local_action=true;
            if(!accepted)s.head_outcome=D::Outcome::rejected;
            // selection() deliberately has no FormDraft publication callback.
            s.draft_snapshot=s.draft->view();
            if(!s.candidate)s.propose();
        }
    }
    s.process_intent();s.stage();
}
void EngineDocumentBroker::shutdown() noexcept {auto& s=*impl_;s.stopped=true;s.retire_unadmitted();if(s.draft)s.draft->close();}
void EngineDocumentBroker::notify_terminal() noexcept {impl_->poisoned.store(true,std::memory_order_release);impl_->owner->notify_document_terminal();}
bool EngineDocumentBroker::pending() const noexcept {const auto& s=*impl_;return s.head || s.held || s.returned || s.work || s.candidate;}
bool EngineDocumentBroker::terminal() const noexcept {return impl_->terminal_state();}
std::shared_ptr<const EngineDocumentBroker::Publication> EngineDocumentBroker::publication_candidate() const {impl_->check_thread();return impl_->candidate;}
bool EngineDocumentBroker::publication_committed(std::shared_ptr<const Publication> value,std::uint64_t revision,CommitKind kind) {
    auto& s=*impl_;s.check_thread();
    if(!value || value!=s.candidate || !revision || revision<=s.accepted.publication_revision || s.terminal_state())return false;
    if(kind==CommitKind::normal && (s.suspended || s.content_redacted || document_target(s.owner->identity())!=s.current))return false;
    const auto version=s.candidate_version;
    auto accepted=value->state;accepted.publication_revision=revision;s.accepted=std::move(accepted);s.candidate.reset();
    if(s.work && s.work->delivered && version>=s.work->publication_version)s.work->published=true;
    s.expose_successor();
    if(s.draft && s.draft->view().publication_pending)s.draft->retry_publication();
    if(!s.work)s.finish_head();
    return true;
}
void EngineDocumentBroker::suspend(Suspension reason) {
    auto& s=*impl_;s.check_thread();s.issue(s.barrier);s.observation_usable=false;s.form_ready=false;s.needs_refresh=true;
    s.content_redacted=true;
    s.retire_unadmitted();
    if(s.head && (!s.work || !s.work->ticket)) {
        s.head_outcome=D::Outcome::cancelled;s.detail="Document authority was suspended before native admission";s.local_action=true;
    }
    // A closing pulse is permanent; other pulses invalidate old authority but
    // allow an explicit new Observe to refresh after the App's lifecycle gate.
    s.suspended=reason==Suspension::closing;
    // An admitted request still owns its actual result and ACK obligation.
    // Retain the private draft until that work settles, but publish no old
    // editable authority. Unadmitted local authority is immediately discarded.
    if(!s.work || !s.work->ticket)s.retire_draft_authority();
    s.leases.clear();s.propose();
}
void EngineDocumentBroker::form_admission_ready(bool value) noexcept {impl_->form_ready=value;}
bool EngineDocumentBroker::native_effect_quiescent() const noexcept {const auto& s=*impl_;return !s.held && !s.work && !s.returned && !s.candidate;}
bool EngineDocumentBroker::form_gate_required() const noexcept {
    const auto& s=*impl_;return (s.draft && s.draft->view().phase!=A::FormDraftPhase::closed) ||
        (s.intent && !std::holds_alternative<D::Observe>(*s.intent));
}
std::optional<std::uint64_t> EngineDocumentBroker::reserve_legacy(){impl_->check_thread();return impl_->reserve();}
void EngineDocumentBroker::cancel_legacy_reservation() noexcept{impl_->cancel_held();}
void EngineDocumentBroker::retire_legacy_unadmitted() noexcept{impl_->retire_unadmitted();}
void EngineDocumentBroker::settle_legacy(){impl_->check_thread();impl_->settle();}
void EngineDocumentBroker::stage_legacy(){impl_->check_thread();impl_->prepare_legacy();impl_->stage();}
bool EngineDocumentBroker::legacy_pending() const noexcept {return impl_->held || impl_->returned || impl_->work;}
bool EngineDocumentBroker::legacy_has_work() const noexcept {return impl_->work.has_value();}
bool EngineDocumentBroker::legacy_unadmitted() const noexcept {return impl_->work && !impl_->work->ticket;}
} // namespace foundation::ui

// Shared FormDraft and recovery composition, used by both presenters.
#include <stdexcept>
#include <utility>
#include <variant>

namespace foundation::ui {
namespace F = appended;

struct EngineDocumentDraftSession::Impl {
    enum class Step { install, restore, apply, finish, blocked };
    struct Recovery {
        F::FormDraftView saved;
        F::FormUpdate fresh;
        bool reapply{};
        Step step{Step::install};
        std::uint64_t generation{};
    };
    std::uint64_t generation;
    const Publish publish;
    const F::FormLimits limits;
    std::unique_ptr<F::FormDraft> draft;
    std::optional<Recovery> recovery;
    bool busy{}, close_requested{};
    struct Mutation {
        Impl& self;
        explicit Mutation(Impl& value) : self(value) { self.busy=true; }
        ~Mutation() {
            self.busy=false;
            if (self.close_requested) {
                self.recovery.reset();
                if (self.draft) self.draft->close();
            }
        }
    };
    Impl(std::uint64_t id,F::FormUpdate update,Publish sink,F::FormLimits bounds)
        : generation(id),publish(std::move(sink)),limits(bounds) {
        if (!generation || !publish) throw std::invalid_argument("Draft session requires identity and publisher");
        Mutation mutation(*this);
        draft=make_draft(std::move(update));
    }
    std::unique_ptr<F::FormDraft> make_draft(F::FormUpdate update) {
        return std::make_unique<F::FormDraft>(generation,std::move(update),
            publish,limits);
    }
    bool available() const noexcept { return !busy && !close_requested; }
    bool clear(bool external) const noexcept {
        return external && !close_requested && draft && !draft->view().publication_pending;
    }
    RecoveryProgress block() noexcept {
        recovery->step=Step::blocked;
        return RecoveryProgress::blocked;
    }
};

EngineDocumentDraftSession::EngineDocumentDraftSession(std::uint64_t id,F::FormUpdate update,
    Publish publish,F::FormLimits limits)
    : impl_(std::make_unique<Impl>(id,std::move(update),std::move(publish),limits)) {}
EngineDocumentDraftSession::~EngineDocumentDraftSession() = default;
const F::FormDraftView& EngineDocumentDraftSession::view() const noexcept { return impl_->draft->view(); }
std::uint64_t EngineDocumentDraftSession::generation() const noexcept { return impl_->generation; }
bool EngineDocumentDraftSession::handle(F::FormDraftEvent event) {
    auto& s=*impl_; if (!s.available()) return false;
    Impl::Mutation mutation(s); return s.draft->handle(std::move(event));
}
bool EngineDocumentDraftSession::selection(F::FormByteSelection selected) {
    auto& s=*impl_; if (!s.available()) return false;
    Impl::Mutation mutation(s); return s.draft->selection(selected);
}
std::optional<F::FormDraftRequest> EngineDocumentDraftSession::next_request() {
    auto& s=*impl_; if (!s.available() || s.recovery) return {};
    Impl::Mutation mutation(s); return s.draft->next_request();
}
bool EngineDocumentDraftSession::complete(F::FormDraftToken token,F::FormDraftOutcome outcome,
    std::optional<F::FormUpdate> update) {
    auto& s=*impl_; if (!s.available()) return false;
    Impl::Mutation mutation(s); return s.draft->complete(token,outcome,std::move(update));
}
bool EngineDocumentDraftSession::observe(F::FormUpdate update) {
    auto& s=*impl_; if (!s.available()) return false;
    Impl::Mutation mutation(s); return s.draft->observe(std::move(update));
}
void EngineDocumentDraftSession::retry_publication() {
    auto& s=*impl_; if (!s.available()) return;
    Impl::Mutation mutation(s); s.draft->retry_publication();
}
bool EngineDocumentDraftSession::request_pending() const noexcept { return impl_->draft->request_pending(); }
void EngineDocumentDraftSession::close() noexcept {
    auto& s=*impl_; s.close_requested=true;
    // Forward immediately to the existing FormDraft's supported close path.
    // During replacement construction draft still names the old object; the
    // outer mutation also closes the newly installed object after unwinding.
    if (s.draft) s.draft->close();
    if (!s.busy) s.recovery.reset();
}
bool EngineDocumentDraftSession::recover(F::FormDraftView saved,F::FormUpdate fresh,bool reapply) {
    auto& s=*impl_;
    if (s.busy || s.draft->view().publication_pending || s.draft->request_pending()) return false;
    F::validate_form_update(fresh,s.limits);
    // These application/node equalities are already enforced by the original
    // Forms Begin-completion path. Epoch replacement is left to that owner;
    // explicit recovery may adopt its new actual Begin, never an old lease.
    if (!fresh.control.lease || fresh.control.node!=saved.base.control.node ||
        fresh.version.generation!=saved.base.version.generation ||
        (reapply && (saved.base.control.kind!=fresh.control.kind ||
                     saved.base.control.native_type!=fresh.control.native_type))) return false;
    Impl::Mutation mutation(s);
    s.recovery=Impl::Recovery{std::move(saved),std::move(fresh),reapply};
    // Original Forms can explicitly replace a closed draft after foreground
    // loss and a real new Begin. Closing the old local draft is not a permanent
    // ban on this deliberate recovery; no old request/lease is revived.
    s.close_requested=false;
    return true;
}
bool EngineDocumentDraftSession::recovery_generation(std::uint64_t fresh_generation) noexcept {
    auto& s=*impl_;
    if (s.busy || !s.recovery || s.recovery->step!=Impl::Step::install ||
        !fresh_generation || fresh_generation<=s.generation ||
        (s.recovery->generation && s.recovery->generation!=fresh_generation)) return false;
    s.recovery->generation=fresh_generation;
    return true;
}
EngineDocumentDraftSession::RecoveryProgress EngineDocumentDraftSession::advance_recovery(
    const std::function<bool()>& presentation_clear) {
    auto& s=*impl_;
    if (!s.recovery) return RecoveryProgress::idle;
    if (s.recovery->step==Impl::Step::blocked) return RecoveryProgress::blocked;
    if (!s.available()) return RecoveryProgress::pending;
    Impl::Mutation mutation(s);
    if (!presentation_clear || !presentation_clear() || !s.clear(true)) return RecoveryProgress::pending;
    const auto checkpoint=[&] {
        // Re-evaluate actual GUI/lifecycle debt after the synchronous publisher.
        // The phase is already committed, so publication retry cannot replay it.
        (void)presentation_clear();
        return RecoveryProgress::pending;
    };
    switch (s.recovery->step) {
    case Impl::Step::install: {
        if (!s.recovery->generation) return RecoveryProgress::pending;
        s.generation=s.recovery->generation;
        // make_draft keeps synchronous publication failure in FormDraft's exact
        // candidate. Do not retry construction because its publication failed.
        s.draft=s.make_draft(s.recovery->fresh);
        s.recovery->step=s.recovery->reapply ? Impl::Step::restore : Impl::Step::finish;
        return checkpoint();
    }
    case Impl::Step::restore: {
        const auto& saved=s.recovery->saved;
        const auto& current=s.draft->view();
        if (std::holds_alternative<F::FormTextState>(current.base.control.state)) {
            if (current.text!=saved.text) (void)s.draft->handle(F::EditFormDraft{current.text,saved.text});
            if (s.draft->view().text!=saved.text) { (void)presentation_clear(); return s.block(); }
        } else if (current.base.control.kind==F::FormKind::checkbox) {
            if (current.checked!=saved.checked) (void)s.draft->handle(F::CheckFormDraft{saved.checked});
            if (s.draft->view().checked!=saved.checked) { (void)presentation_clear(); return s.block(); }
        } else if (saved.option) {
            (void)s.draft->handle(F::OptionFormDraft{saved.option->node,saved.option->selected});
            if (!s.draft->view().option || s.draft->view().option->node!=saved.option->node ||
                s.draft->view().option->selected!=saved.option->selected) {
                (void)presentation_clear(); return s.block();
            }
        }
        s.recovery->step=Impl::Step::apply;
        return checkpoint();
    }
    case Impl::Step::apply:
        if (s.draft->view().dirty) {
            (void)s.draft->handle(F::ApplyFormDraft{});
            if (!s.draft->view().apply_queued) { (void)presentation_clear(); return s.block(); }
        }
        s.recovery->step=Impl::Step::finish;
        return checkpoint();
    case Impl::Step::finish:
        s.recovery.reset();
        return RecoveryProgress::completed;
    case Impl::Step::blocked:
        return RecoveryProgress::blocked;
    }
    throw std::logic_error("Unknown draft recovery step");
}
void EngineDocumentDraftSession::cancel_recovery() noexcept {
    if (!impl_->busy) impl_->recovery.reset();
}
bool EngineDocumentDraftSession::recovery_pending() const noexcept { return bool(impl_->recovery); }
bool EngineDocumentDraftSession::recovery_install_pending() const noexcept {
    return impl_->recovery && impl_->recovery->step==Impl::Step::install;
}
bool EngineDocumentDraftSession::recovery_blocked() const noexcept {
    return impl_->recovery && impl_->recovery->step==Impl::Step::blocked;
}
const F::FormDraftView* EngineDocumentDraftSession::recovery_saved() const noexcept {
    return impl_->recovery ? &impl_->recovery->saved : nullptr;
}
const F::FormUpdate* EngineDocumentDraftSession::recovery_fresh() const noexcept {
    return impl_->recovery ? &impl_->recovery->fresh : nullptr;
}

} // namespace foundation::ui
