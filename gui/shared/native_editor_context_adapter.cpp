// SPDX-License-Identifier: CC0-1.0
#include "native_editor_context_adapter.hpp"
#include <atomic>
#include <algorithm>
#include <deque>
#include <limits>
#include <stdexcept>
#include <thread>
#include <variant>

namespace foundation::ui::native_editor {
namespace {
struct RetainedBytes {
    std::size_t value=4096;
    void add(std::size_t count,std::size_t width=1) noexcept {
        const auto limit=Controller::max_packet_bytes;
        if(value>limit||count>(limit-value)/width)value=limit+1;
        else value+=count*width;
    }
    void basis(const Basis& basis) noexcept {
        add(basis.surrounding.capacity());add(basis.identity.owner.id.capacity());
    }
    void key(const KeyData& key) noexcept {
        add(key.transition.key.capacity());add(key.transition.code.capacity());
    }
};
std::size_t packet_bytes(const Packet& packet) {
    const auto& o=packet.observation;
    RetainedBytes bytes;bytes.basis(packet.basis);bytes.add(o.before.value.capacity());
    if(o.after)bytes.add(o.after->value.capacity());
    bytes.add(packet.default_dependencies.capacity(),sizeof(DefaultDependency));
    std::visit([&](const auto& data){
        using T=std::decay_t<decltype(data)>;
        if constexpr(std::is_same_v<T,KeyData>)bytes.key(data);
        else if constexpr(std::is_same_v<T,TextData>){bytes.add(data.text.capacity());bytes.add(data.input_type.capacity());bytes.add(data.source_groups.capacity(),sizeof(std::uint64_t));}
        else if constexpr(std::is_same_v<T,CompositionData>){bytes.add(data.text.capacity());bytes.add(data.source_groups.capacity(),sizeof(std::uint64_t));}
    },o.data);
    return bytes.value;
}
bool bounded(const Packet& packet) {
    if(packet.basis.surrounding.size()>Controller::max_text_bytes||packet.basis.identity.owner.id.size()>128||
        packet.observation.before.value.size()>Controller::max_text_bytes||
        (packet.observation.after&&packet.observation.after->value.size()>Controller::max_text_bytes)||
        packet.default_dependencies.size()>Controller::max_dependencies)return false;
    return std::visit([](const auto& data){
        using T=std::decay_t<decltype(data)>;
        if constexpr(std::is_same_v<T,KeyData>)return data.transition.key.size()<=64&&data.transition.code.size()<=64;
        else if constexpr(std::is_same_v<T,TextData>)return data.text.size()<=Controller::max_text_bytes&&data.input_type.size()<=64&&data.source_groups.size()<=Controller::max_dependencies;
        else if constexpr(std::is_same_v<T,CompositionData>)return data.text.size()<=Controller::max_text_bytes&&data.source_groups.size()<=Controller::max_dependencies;
        else return true;
    },packet.observation.data);
}
}
struct NativeEditorContextAdapter::Impl {
    struct Slot {
        std::uint64_t ticket{};
        std::size_t bytes{};
        std::variant<Packet,Revocation> work;
        std::optional<DispatchResult> completion;
    };
    struct Flight {
        ContextRequest transport;
        std::uint64_t controller_ticket{};
        bool offered{},refresh{};
        std::size_t retirements{};
        std::optional<NativeRetireMaterial> material;
        Identity identity;
        std::optional<DispatchResult> withheld;
        std::optional<CompositionFact> composition;
        std::optional<RetirementReadback> retirement;
    };
    Controller controller;
    Backend* backend{};
    const Publish publish;
    const EditorTerminalHook terminal_hook;
    const std::thread::id owner=std::this_thread::get_id();
    std::atomic<bool> stopped{};
    std::optional<EditorPublication> cached;
    std::optional<NativeProjection> checked_projection, staged_projection;
    bool publishing{};
    std::optional<NativeRetireMaterial> debt;
    Identity debt_identity;
    std::optional<Flight> flight;
    std::atomic<std::uint64_t> transport_ticket{};
    std::deque<Slot> slots;
    std::uint64_t next_ticket=1, next_transport=1;
    std::size_t bytes{},callback_depth{};
    bool executing{},closed{},projection_requested{},projection_retired{},refresh_requested{},retirement_requested{};
    Impl(Backend* input,Publish output,EditorTerminalHook terminal):backend(input),publish(std::move(output)),terminal_hook(terminal) {
        if(!publish||!terminal_hook.notify)throw std::invalid_argument("Native editor requires checked publication and terminal owner");
    }
    bool on_owner()const noexcept{return std::this_thread::get_id()==owner;}
    bool admitted()const noexcept{return on_owner()&&!stopped.load(std::memory_order_acquire)&&!closed;}
    void stop()noexcept{
        if(!stopped.exchange(true,std::memory_order_acq_rel))terminal_hook.notify(terminal_hook.context);
        if(on_owner()&&!controller.terminal())controller.notify_publication_failure();
    }
    bool publish_checked(EditorPublication value,std::optional<NativeProjection> projection={}) {
        staged_projection=std::move(projection); publishing=true;
        ++callback_depth;
        bool accepted=false;
        try{accepted=publish(value);}catch(...){--callback_depth;publishing=false;stop();return false;}
        --callback_depth;
        publishing=false;
        if(!accepted||!admitted()){stop();return false;}
        cached=std::move(value);checked_projection=std::move(staged_projection);return true;
    }
    std::optional<std::uint64_t> append(std::variant<Packet,Revocation> work,std::size_t retained_bytes) {
        if(!admitted()||executing||slots.size()>=64||retained_bytes>Controller::max_packet_bytes||
            bytes>Controller::max_packet_bytes-retained_bytes)return {};
        if(!next_ticket){stop();return {};}
        const auto ticket=next_ticket;
        next_ticket=next_ticket==std::numeric_limits<std::uint64_t>::max()?0:next_ticket+1;
        slots.push_back({ticket,retained_bytes,std::move(work),{}});bytes+=retained_bytes;return ticket;
    }
    Slot* head(std::uint64_t ticket) {
        const auto it=std::find_if(slots.begin(),slots.end(),[&](const auto& slot){return slot.ticket==ticket;});
        return it==slots.end()?nullptr:&*it;
    }
    void clear_flight() noexcept { transport_ticket.store(0,std::memory_order_release);flight.reset(); }
    void stage(ContextRequest request) {
        if(!next_transport)throw std::overflow_error("Editor transport tickets exhausted");
        request.ticket=next_transport;
        next_transport=next_transport==std::numeric_limits<std::uint64_t>::max()?0:next_transport+1;
        flight->transport=std::move(request);flight->offered=false;
        transport_ticket.store(flight->transport.ticket,std::memory_order_release);
    }
    void poll(bool refresh) {
        flight.emplace();ContextRequest request;
        if(refresh&&controller.current_projection()){
            const auto& current=*controller.current_projection();flight->refresh=true;
            request.mapping_id=current.mapping_id;flight->material=current.retire;flight->identity=current.identity;
        }
        projection_requested=false;refresh_requested=false;stage(std::move(request));
    }
    void remember(const NativeProjection& projection) {
        debt=projection.retire;debt_identity=projection.identity;
    }
    static bool same_refresh_projection(NativeProjection previous,const NativeProjection& actual) {
        previous.identity.presentation_revision=actual.identity.presentation_revision;return previous==actual;
    }
    void terminal_result(DispatchResult& result) {
        result.admission=Admission::terminal;result.detail="Native editor outcome could not be safely published";
        if(result.receipt){result.receipt->outcome=Outcome::unknown;result.receipt->basis.reset();result.receipt->default_token.reset();}
        stop();
    }
    void abort_flight() {
        if(flight&&flight->transport.head_ticket){
            if(auto* slot=head(flight->transport.head_ticket);slot&&!slot->completion){
                DispatchResult failed=flight->withheld?*flight->withheld:DispatchResult{Admission::terminal,{},"Native editor transport failed"};
                terminal_result(failed);slot->completion=std::move(failed);return;
            }
        }
        stop();
    }
    void settle(DispatchResult result,std::optional<CompositionFact> composition={},
        std::optional<RetirementReadback> retirement={}) {
        const auto ticket=flight->transport.head_ticket;
        auto* slot=head(ticket);
        if(!slot)throw std::logic_error("Editor transport lost its retained head");
        if(controller.terminal()||result.admission==Admission::terminal){slot->completion=std::move(result);stop();clear_flight();return;}
        std::optional<EditorPublication> publication;
        std::optional<NativeProjection> projection;
        if(result.receipt){
            const auto& receipt=*result.receipt;
            publication=EditorPublication{receipt.basis,Settlement{receipt.session,receipt.id,receipt.submitted_token,receipt.predecessor},
                receipt.composition?receipt.composition:composition,retirement?retirement:receipt.retirement};
            if(receipt.basis&&controller.current_projection())projection=*controller.current_projection();
        }else if(result.admission==Admission::completed&&std::holds_alternative<Revocation>(slot->work)){
            publication=EditorPublication{{},{},composition,retirement};
        }
        if(publication&&!publish_checked(std::move(*publication),std::move(projection)))terminal_result(result);
        slot->completion=std::move(result);clear_flight();
    }
    void prepared(PreparedDispatch result) {
        if(result.admission!=Admission::prepared){settle({result.admission,std::move(result.receipt),std::move(result.detail)});return;}
        ContextRequest next;next.head_ticket=flight->transport.head_ticket;
        next.mapping_id=controller.current_projection()?controller.current_projection()->mapping_id:0;
        next.kind=result.request?ContextRequest::Kind::observation:ContextRequest::Kind::revoke;
        next.request=std::move(result.request);next.revocation=std::move(result.revocation);
        if(next.revocation&&flight->material){
            next.retirement=NativeRevocationRequest{*flight->material,flight->identity,{}};
            if(next.revocation->composition==flight->material->composition&&next.revocation->basis.identity==flight->identity)
                next.retirement->observed=next.revocation;
        }
        if(!next.request&&!next.revocation)throw std::logic_error("Editor prepared no native operation");
        stage(std::move(next));
    }
    static bool valid_readback(const RetirementReadback& value) {
        Basis probe;probe.token=1;probe.editor_revision=1;probe.identity=value.identity;
        return (value.availability==NativeAvailability::noneditable||value.availability==NativeAvailability::unavailable)&&
            !value.authority_retired&&value.readback_attested&&value.observation_revision&&valid_basis(probe);
    }
    void cleanup(NativeRetireMaterial material,Identity identity) {
        ContextRequest next;next.kind=ContextRequest::Kind::revoke;next.head_ticket=flight->transport.head_ticket;
        next.mapping_id=material.mapping_id;next.retirement=NativeRevocationRequest{material,identity,{}};
        if(auto* slot=head(next.head_ticket);slot&&std::holds_alternative<Revocation>(slot->work)){
            const auto& observed=std::get<Revocation>(slot->work);
            if(observed.composition==material.composition&&observed.basis.identity==next.retirement->identity)
                next.retirement->observed=observed;
        }
        flight->material=material;flight->identity=std::move(identity);stage(std::move(next));
    }
    static bool cleanup_attested(const NativeResult& result,const Flight& active) {
        if(result.outcome!=Outcome::applied||result.retired!=active.material||!result.retired||
            !result.readback_attested||!result.observation_revision||result.allow_default||
            result.readback_identity.owner!=active.identity.owner||result.readback_identity.generation!=active.identity.generation||
            result.readback_identity.epoch!=active.identity.epoch)return false;
        if(active.material->composition&&(!result.composition_readback_attested||!result.composition||
            result.composition->transaction!=active.material->composition||result.composition->state!=CompositionState::ended))return false;
        if(result.projection)return result.availability==NativeAvailability::available&&valid_projection(*result.projection)&&
            result.projection->identity.owner==result.readback_identity.owner&&
            result.projection->identity.generation==result.readback_identity.generation&&
            result.projection->identity.epoch==result.readback_identity.epoch&&
            result.projection->identity.context==result.readback_identity.context&&
            (!result.projection->retire||result.projection->retire->token!=result.retired->token);
        return result.continuity==Continuity::replaced&&valid_readback({result.availability,result.readback_identity,
            result.observation_revision,result.readback_attested})&&(!result.retire||
            (valid_retire_material(*result.retire)&&result.retire->token!=result.retired->token));
    }
};
namespace {
template<class T> struct Executing { T& state;explicit Executing(T& input):state(input){state.executing=true;}~Executing(){state.executing=false;} };
}
NativeEditorContextAdapter::NativeEditorContextAdapter(Publish publish,EditorTerminalHook hook)
    :impl_(std::make_unique<Impl>(nullptr,std::move(publish),hook)){}
NativeEditorContextAdapter::NativeEditorContextAdapter(Backend& backend,Publish publish,EditorTerminalHook hook)
    :impl_(std::make_unique<Impl>(&backend,std::move(publish),hook)){}
NativeEditorContextAdapter::~NativeEditorContextAdapter(){
    // Uncertain/queued work retains its exact objects. No dependency may be
    // destroyed below this endpoint, as required by the injected lifetime.
    if(impl_&&(impl_->stopped.load(std::memory_order_acquire)||!impl_->slots.empty()||impl_->executing||impl_->callback_depth||impl_->flight||impl_->debt))
        (void)impl_.release();
}
bool NativeEditorContextAdapter::install_projection(NativeProjection projection){
    auto& s=*impl_;if(!s.admitted()||s.executing||s.callback_depth||!s.slots.empty()||s.flight||s.debt)return false;
    Executing guard(s);
    if(!valid_projection(projection))return false;
    auto checked=projection;
    auto basis=s.controller.activate(std::move(projection));
    if(!basis)return false;
    s.remember(checked);return s.publish_checked({std::move(*basis),{},s.controller.current_composition(),{}},std::move(checked));
}
std::optional<std::uint64_t> NativeEditorContextAdapter::submit(Packet packet){
    auto& s=*impl_;if(!s.on_owner()){s.stop();return {};}
    if(!bounded(packet))return {};
    const auto bytes=packet_bytes(packet);return s.append(std::move(packet),bytes);
}
std::optional<std::uint64_t> NativeEditorContextAdapter::queue_revoke(Revocation revoke){
    auto& s=*impl_;if(!s.on_owner()){s.stop();return {};}
    if(revoke.basis.surrounding.size()>Controller::max_text_bytes||revoke.basis.identity.owner.id.size()>128||revoke.reason.size()>512||revoke.held_keys.size()>64)return {};
    RetainedBytes bytes;bytes.basis(revoke.basis);bytes.add(revoke.reason.capacity());bytes.add(revoke.held_keys.capacity(),sizeof(KeyData));
    for(const auto& key:revoke.held_keys)if(key.transition.key.size()>64||key.transition.code.size()>64)return {};
    for(const auto& key:revoke.held_keys)bytes.key(key);
    return s.append(std::move(revoke),bytes.value);
}
bool NativeEditorContextAdapter::request_projection(){
    auto& s=*impl_;if(!s.on_owner()){s.stop();return false;}if(!s.admitted())return false;
    s.refresh_requested=false;
    if(s.flight&&!s.flight->transport.head_ticket&&s.flight->transport.kind==ContextRequest::Kind::projection&&!s.flight->refresh)return true;
    if(!s.projection_requested)s.projection_retired=false;
    s.projection_requested=true;return true;
}
bool NativeEditorContextAdapter::request_refresh(){
    auto& s=*impl_;if(!s.on_owner()){s.stop();return false;}if(!s.admitted())return false;
    if(s.retirement_requested||s.projection_requested||(s.flight&&!s.flight->transport.head_ticket))return true;
    s.refresh_requested=true;return true;
}
bool NativeEditorContextAdapter::request_retirement(){
    auto& s=*impl_;if(!s.on_owner()){s.stop();return false;}if(!s.admitted())return false;
    s.refresh_requested=false;s.projection_requested=false;
    if(!s.flight&&!s.controller.current_projection()&&s.cached&&s.cached->retirement&&s.cached->retirement->authority_retired){
        s.retirement_requested=false;return true;
    }
    if(!s.flight&&!s.debt){
        if(s.checked_projection){s.stop();return false;}
        s.retirement_requested=false;return true;
    }
    s.retirement_requested=true;return true;
}
std::optional<ContextRequest> NativeEditorContextAdapter::prepare(BeforeHead before_head){
    auto& s=*impl_;if(!s.admitted()||s.executing||s.callback_depth)return {};
    Executing guard(s);
    try{
        if(!s.flight){
            // A browser completion must still match its one cached paired
            // publication when taken. Fresh work cannot overwrite that pair.
            if(!s.retirement_requested&&
                std::any_of(s.slots.begin(),s.slots.end(),[](const auto& slot){return slot.completion.has_value();}))return {};
            if((s.retirement_requested||(s.projection_requested&&!s.projection_retired&&s.slots.empty()&&s.controller.current_projection()))&&s.debt){
                s.flight.emplace();
                if(s.retirement_requested){
                    auto it=std::find_if(s.slots.begin(),s.slots.end(),[](const auto& slot){return slot.completion.has_value();});
                    if(it==s.slots.end())it=std::find_if(s.slots.begin(),s.slots.end(),[](const auto& slot){return !slot.completion;});
                    if(it!=s.slots.end()){
                        s.flight->transport.head_ticket=it->ticket;
                        if(it->completion){s.flight->withheld=std::move(*it->completion);it->completion.reset();}
                        else {
                        const auto pending=std::holds_alternative<Packet>(it->work)?s.controller.begin(std::get<Packet>(it->work)):
                            s.controller.begin_revocation(std::get<Revocation>(it->work));
                        if(pending.admission==Admission::awaiting_projection){
                            s.flight->controller_ticket=pending.ticket;
                            s.flight->withheld=s.controller.cancel_unentered(pending.ticket);
                        }else s.flight->withheld=DispatchResult{pending.admission,pending.receipt,pending.detail};
                        }
                        if(s.flight->withheld->admission==Admission::terminal){s.settle(std::move(*s.flight->withheld));return {};}
                    }
                }
                s.cleanup(*s.debt,s.debt_identity);
            }else if(s.projection_requested&&s.projection_retired){s.poll(false);}
            else if(s.refresh_requested&&!s.projection_requested){s.poll(true);}
            else {
            auto it=std::find_if(s.slots.begin(),s.slots.end(),[](const auto& slot){return !slot.completion;});
            if(it!=s.slots.end()){
                if(before_head){++s.callback_depth;bool ready=false;try{ready=before_head();}catch(...){--s.callback_depth;throw;}--s.callback_depth;if(!ready||!s.admitted())return {};}
                const auto projection=s.controller.current_projection()?std::optional<NativeProjection>{*s.controller.current_projection()}:std::nullopt;
                const auto prepared=std::holds_alternative<Packet>(it->work)?s.controller.begin(std::get<Packet>(it->work)):
                    s.controller.begin_revocation(std::get<Revocation>(it->work));
                s.flight.emplace();s.flight->transport.head_ticket=it->ticket;
                if(projection){s.flight->material=projection->retire;s.flight->identity=projection->identity;}
                if(prepared.admission!=Admission::awaiting_projection){s.settle({prepared.admission,prepared.receipt,prepared.detail});return {};}
                s.flight->controller_ticket=prepared.ticket;
                ContextRequest request;request.head_ticket=it->ticket;request.mapping_id=projection?projection->mapping_id:0;s.stage(std::move(request));
            }else if(s.projection_requested&&s.slots.empty()){
                s.poll(false);
            }else return {};
            }
        }
        if(s.flight->offered)return {};
        auto output=s.flight->transport;s.flight->offered=true;return output;
    }catch(...){s.stop();return {};}
}
bool NativeEditorContextAdapter::defer(std::uint64_t ticket){
    auto& s=*impl_;if(!s.admitted()||s.executing||s.callback_depth||!s.flight||!s.flight->offered||s.flight->transport.ticket!=ticket)return false;
    s.flight->offered=false;return true;
}
bool NativeEditorContextAdapter::supply_projection(std::uint64_t ticket,std::optional<NativeProjection> projection,std::optional<RetirementReadback> readback){
    auto& s=*impl_;if(!s.on_owner()){if(s.transport_ticket.load(std::memory_order_acquire)==ticket&&ticket)s.stop();return false;}
    if(!s.admitted()||s.executing||s.callback_depth||!s.flight||!s.flight->offered||s.flight->transport.ticket!=ticket||s.flight->transport.kind!=ContextRequest::Kind::projection)return false;
    Executing guard(s);
    try{
        if(projection&&!valid_projection(*projection)){s.stop();return true;}
        if(projection&&readback){s.stop();return true;}
        if(s.flight->transport.head_ticket){
            if(projection){s.flight->material=projection->retire;s.flight->identity=projection->identity;
                if(s.debt&&projection->retire==s.debt)s.debt_identity=projection->identity;}
            s.prepared(s.controller.supply_projection(s.flight->controller_ticket,std::move(projection)));return true;
        }
        if(s.flight->refresh){
            if(!projection&&(!readback||!Impl::valid_readback(*readback))){s.stop();return true;}
            const auto* previous=s.controller.current_projection();
            const bool unchanged=projection&&previous&&s.controller.state()==State::ready&&
                Impl::same_refresh_projection(*previous,*projection);
            if(!unchanged||s.retirement_requested||s.projection_requested){
                if(!s.flight->material){s.stop();return true;}
                if(projection&&projection->retire==s.flight->material)s.debt_identity=projection->identity;
                s.projection_requested=!s.retirement_requested;s.projection_retired=false;s.refresh_requested=false;
                s.cleanup(*s.flight->material,s.debt_identity);return true;
            }
        }
        if(projection){
            if(s.debt&&projection->retire!=s.debt){s.stop();return true;}
            auto checked=*projection;auto basis=s.controller.activate(std::move(*projection));
            if(!basis){s.stop();return true;}s.remember(checked);
            if(s.retirement_requested){
                if(!s.debt){s.stop();return true;}
                s.cleanup(*s.debt,s.debt_identity);return true;
            }
            s.publish_checked({std::move(*basis),{},s.controller.current_composition(),{}},std::move(checked));s.clear_flight();return true;
        }
        if(!readback||!Impl::valid_readback(*readback)){s.stop();return true;}
        s.flight->retirement=readback;
        if(s.debt){s.cleanup(*s.debt,s.debt_identity);return true;}
        s.controller.revoke();s.retirement_requested=false;
        s.publish_checked({{},{},{},readback});s.clear_flight();return true;
    }catch(...){s.stop();return true;}
}
bool NativeEditorContextAdapter::complete(std::uint64_t ticket,NativeResult result){
    auto& s=*impl_;if(!s.on_owner()){if(s.transport_ticket.load(std::memory_order_acquire)==ticket&&ticket)s.stop();return false;}
    if(!s.admitted()||s.executing||s.callback_depth||!s.flight||!s.flight->offered||s.flight->transport.ticket!=ticket||s.flight->transport.kind==ContextRequest::Kind::projection)return false;
    Executing guard(s);
    try{
        if(s.flight->withheld||!s.flight->transport.head_ticket){
            if(!Impl::cleanup_attested(result,*s.flight)){s.abort_flight();return true;}
            s.debt=result.retire?result.retire:(result.projection?result.projection->retire:std::optional<NativeRetireMaterial>{});s.debt_identity=result.readback_identity;
            if(!s.controller.complete_external_retirement(*s.flight->material,result)){s.abort_flight();return true;}
            const auto* proof=s.controller.external_retirement();
            if(!proof||!proof->authority_retired){s.abort_flight();return true;}
            const auto retired=*proof;
            if(s.debt){
                // Another actual provider lease is still an owned obligation.
                // Anchor only its checked projection privately; publish no
                // renewed editor authority while draining bounded successors.
                if(++s.flight->retirements>=64||!result.projection){s.abort_flight();return true;}
                auto successor=*result.projection;successor.retire=s.debt;
                if(!valid_projection(successor)||!s.controller.activate(std::move(successor))){s.abort_flight();return true;}
                s.cleanup(*s.debt,s.debt_identity);return true;
            }
            s.retirement_requested=false;
            if(!s.flight->transport.head_ticket&&s.projection_requested)s.projection_retired=true;
            if(s.flight->withheld){
                auto held=std::move(*s.flight->withheld);
                if(held.receipt){held.receipt->basis.reset();held.receipt->default_token.reset();held.receipt->continuity=Continuity::replaced;
                    held.receipt->composition=result.composition;held.receipt->retirement=retired;}
                s.settle(std::move(held),result.composition,retired);
            }
            else {s.publish_checked({{},{},result.composition,retired});s.clear_flight();return true;}
            return true;
        }
        const auto old=s.flight->material;
        auto completion=s.controller.complete(s.flight->controller_ticket,result);
        if(completion.admission==Admission::terminal){s.settle(std::move(completion));return true;}
        if(result.projection&&s.controller.current_projection())s.remember(*s.controller.current_projection());
        else if(result.retired==old&&old){s.debt=result.retire;s.debt_identity=result.readback_identity;}
        const bool null_receipt=completion.receipt&&!completion.receipt->basis;
        if(old&&result.retired==old&&(s.flight->transport.kind==ContextRequest::Kind::revoke||
            (null_receipt&&!result.projection&&!s.debt))){
            if(s.debt){
                s.flight->withheld=std::move(completion);s.flight->retirements=1;
                if(!result.projection){s.abort_flight();return true;}
                s.cleanup(*s.debt,s.debt_identity);return true;
            }
            s.retirement_requested=false;
            const RetirementReadback retired{result.availability,result.readback_identity,
                result.observation_revision,result.readback_attested,true};
            if(completion.receipt){completion.receipt->retirement=retired;completion.receipt->composition=result.composition;}
            s.settle(std::move(completion),result.composition,retired);return true;
        }
        if((null_receipt&&old&&result.retired!=old)||s.retirement_requested){
            s.flight->withheld=std::move(completion);s.flight->composition=result.composition;
            if(s.flight->withheld->receipt)s.flight->retirement=s.flight->withheld->receipt->retirement;
            const auto material=s.retirement_requested?s.debt:old;
            if(!material){s.stop();return true;}
            s.cleanup(*material,s.retirement_requested?s.debt_identity:s.flight->identity);return true;
        }
        s.settle(std::move(completion),result.composition);return true;
    }catch(...){s.stop();return true;}
}
bool NativeEditorContextAdapter::cancel_unentered(std::uint64_t ticket){
    auto& s=*impl_;if(!s.on_owner()){if(ticket&&s.transport_ticket.load(std::memory_order_acquire)==ticket)s.stop();return false;}
    if(!s.admitted()||s.executing||s.callback_depth||!s.flight||!s.flight->offered||s.flight->transport.ticket!=ticket)return false;
    Executing guard(s);
    try{
        if(s.flight->withheld||s.flight->transport.retirement){
            // This cleanup never entered: retain its obligation and offer a
            // new correlation, never replay an operation of uncertain entry.
            auto retry=s.flight->transport;s.stage(std::move(retry));return true;
        }
        if(!s.flight->transport.head_ticket){
            if(s.debt){
                if(s.flight->refresh&&!s.retirement_requested){s.projection_requested=true;s.projection_retired=false;}
                s.cleanup(*s.debt,s.debt_identity);
            }else {s.retirement_requested=false;s.clear_flight();}
            return true;
        }
        auto cancelled=s.controller.cancel_unentered(s.flight->controller_ticket);
        if(cancelled.admission==Admission::terminal){s.settle(std::move(cancelled));return true;}
        if(cancelled.admission!=Admission::completed){s.stop();return true;}
        const auto material=s.flight->material?s.flight->material:s.debt;
        if(!material){s.stop();return true;}
        s.flight->withheld=std::move(cancelled);
        s.cleanup(*material,s.flight->identity);return true;
    }catch(...){s.stop();return true;}
}
bool NativeEditorContextAdapter::notify_transport_failure(std::uint64_t ticket)noexcept{
    auto& s=*impl_;if(!ticket||s.transport_ticket.load(std::memory_order_acquire)!=ticket)return false;
    if(s.on_owner())s.controller.notify_transport_failure();
    s.stop();return true;
}
bool NativeEditorContextAdapter::advance(){
    auto& s=*impl_;if(!s.backend)return false;bool progressed=false;
    for(unsigned stage=0;stage!=4;++stage){
        auto request=prepare();if(!request)break;progressed=true;
        try{
            if(request->kind==ContextRequest::Kind::projection){
                ++s.callback_depth;std::optional<NativeProjection> actual;
                try{actual=s.backend->project(request->mapping_id);}catch(...){--s.callback_depth;throw;}--s.callback_depth;
                supply_projection(request->ticket,std::move(actual));
            }
            else if(request->request||request->revocation){
                ++s.callback_depth;NativeResult result;
                try{result=request->request?s.backend->apply(*request->request):s.backend->revoke(*request->revocation);}
                catch(...){--s.callback_depth;throw;}--s.callback_depth;
                complete(request->ticket,std::move(result));
            }
            else {notify_transport_failure(request->ticket);break;}
        }catch(...){notify_transport_failure(request->ticket);break;}
        if(terminal())break;
    }
    return progressed;
}
std::optional<EditorCompletion> NativeEditorContextAdapter::take_completion(std::uint64_t ticket){
    auto& s=*impl_;if(!s.on_owner()){s.stop();return {};}
    if(s.executing||s.callback_depth||(s.retirement_requested&&!s.stopped.load(std::memory_order_acquire)))return {};
    auto it=std::find_if(s.slots.begin(),s.slots.end(),[&](const auto& value){return value.ticket==ticket;});
    if(it==s.slots.end()||!it->completion)return {};
    EditorCompletion result{ticket,std::move(*it->completion)};s.bytes-=it->bytes;s.slots.erase(it);return result;
}
const EditorPublication* NativeEditorContextAdapter::publication()const noexcept{
    const auto& s=*impl_;return s.admitted()&&s.cached?&*s.cached:nullptr;
}
const NativeProjection* NativeEditorContextAdapter::projection()const noexcept{
    const auto& s=*impl_;if(!s.admitted())return nullptr;
    const auto& value=s.publishing?s.staged_projection:s.checked_projection;return value?&*value:nullptr;
}
bool NativeEditorContextAdapter::available()const noexcept{return impl_->admitted()&&!retirement_pending()&&impl_->controller.state()==State::ready&&impl_->controller.current_basis();}
bool NativeEditorContextAdapter::terminal()const noexcept{return impl_->stopped.load(std::memory_order_acquire);}
bool NativeEditorContextAdapter::pending()const noexcept{return impl_->on_owner()&&(!impl_->slots.empty()||impl_->flight||impl_->projection_requested||impl_->refresh_requested);}
bool NativeEditorContextAdapter::retirement_pending()const noexcept{
    const auto& s=*impl_;return s.on_owner()&&(s.retirement_requested||(s.flight&&s.flight->transport.retirement.has_value())||
        (s.projection_requested&&!s.projection_retired&&s.slots.empty()&&s.debt&&s.controller.current_projection()));
}
void NativeEditorContextAdapter::enter_callback(){
    auto& s=*impl_;if(!s.admitted())throw std::logic_error("Native editor endpoint is unavailable");
    if(s.callback_depth==std::numeric_limits<std::size_t>::max()){s.stop();throw std::overflow_error("Native editor callback depth exhausted");}
    ++s.callback_depth;
}
void NativeEditorContextAdapter::leave_callback()noexcept{
    auto& s=*impl_;if(!s.on_owner()||!s.callback_depth){s.stop();return;}--s.callback_depth;
}
void NativeEditorContextAdapter::notify_terminal()noexcept{impl_->stop();}
void NativeEditorContextAdapter::close()noexcept{
    auto& s=*impl_;if(!s.on_owner()){s.stop();return;}s.closed=true;s.cached.reset();
    // Closing is admission metadata. Outstanding native work/cancellation is
    // retained for process exit; close never fabricates a successful cleanup.
    if(!s.slots.empty()||s.executing||s.callback_depth||s.flight||s.debt)s.stop();else s.controller.close();
}
}
