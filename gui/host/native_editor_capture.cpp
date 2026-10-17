// SPDX-License-Identifier: CC0-1.0
#include "native_editor_capture.hpp"

#include <algorithm>
#include <atomic>
#include <deque>
#include <limits>
#include <map>
#include <stdexcept>
#include <string_view>
#include <thread>
#include <type_traits>
#include <utility>

namespace foundation::host {
namespace E=gui_editor;
namespace S=gui_surface;
namespace {
constexpr auto maximum=std::numeric_limits<std::uint64_t>::max();
template<class Visit>
void each_scalar(const std::string& value,std::size_t limit,Visit visit) {
    if (value.size()>limit) throw std::invalid_argument("Native editor text limit");
    std::size_t byte=0,unit=0;
    for (;;) {
        visit(byte,unit);
        if (byte==value.size()) return;
        const auto lead=static_cast<unsigned char>(value[byte]);
        std::size_t count; std::uint32_t point,minimum;
        if (lead && lead<0x80) { count=1; point=lead; minimum=0; }
        else if (lead>=0xc2 && lead<=0xdf) { count=2; point=lead&31u; minimum=0x80; }
        else if (lead>=0xe0 && lead<=0xef) { count=3; point=lead&15u; minimum=0x800; }
        else if (lead>=0xf0 && lead<=0xf4) { count=4; point=lead&7u; minimum=0x10000; }
        else throw std::invalid_argument("Invalid native editor UTF-8");
        if (count>value.size()-byte) throw std::invalid_argument("Truncated native editor UTF-8");
        for (std::size_t index=1;index<count;++index) {
            const auto next=static_cast<unsigned char>(value[byte+index]);
            if ((next&0xc0u)!=0x80u) throw std::invalid_argument("Invalid native editor UTF-8 continuation");
            point=(point<<6u)|(next&63u);
        }
        if (point<minimum || point>0x10ffff || (point>=0xd800 && point<=0xdfff))
            throw std::invalid_argument("Invalid native editor Unicode scalar");
        byte+=count; unit+=point>0xffff?2:1;
    }
}
void require(bool condition,const char* message) { if (!condition) throw std::invalid_argument(message); }
bool direction(E::Direction value) {
    return value==E::Direction::none || value==E::Direction::forward || value==E::Direction::backward;
}
bool boundary(const std::string& value,std::size_t offset) {
    return offset<=value.size() && (offset==value.size() || (static_cast<unsigned char>(value[offset])&0xc0u)!=0x80u);
}
bool range(const std::string& value,S::ByteRange value_range) {
    return value_range.begin<=value_range.end && boundary(value,value_range.begin) && boundary(value,value_range.end);
}
void text(const std::string& value,std::size_t limit=NativeEditorCapture::max_text_bytes) {
    each_scalar(value,limit,[](std::size_t,std::size_t){});
}
void identity(const S::Identity& value) {
    text(value.owner.id,128);
    require(!value.owner.id.empty() && value.owner.generation && value.presentation_revision && value.generation && value.epoch && value.context,
        "Invalid native editor identity");
}
bool same_context(const S::Identity& a,const S::Identity& b) {
    return a.owner==b.owner && a.generation==b.generation && a.epoch==b.epoch && a.context==b.context;
}
bool same_owner(const S::Identity& a,const S::Identity& b) {
    return a.owner==b.owner && a.generation==b.generation && a.epoch==b.epoch;
}
bool same_basis(const E::Basis& a,const E::Basis& b) {
    return a.token==b.token && same_context(a.identity,b.identity) && a.editor_revision==b.editor_revision &&
        a.surrounding==b.surrounding && a.selection==b.selection && a.backward==b.backward && a.composition==b.composition;
}
bool same_basis(const std::optional<E::Basis>& a,const std::optional<E::Basis>& b) {
    return bool(a)==bool(b) && (!a || same_basis(*a,*b));
}
void validate_basis(const E::Basis& value) {
    identity(value.identity); text(value.surrounding);
    require(value.token && value.editor_revision && range(value.surrounding,value.selection),"Invalid native editor basis");
}
void observed_text(const E::TextObservation& value) {
    const auto checked=capture_native_editor_text(value.value,value.selection_start,value.selection_end,value.selection_direction);
    require(checked==value,"Native editor UTF-16/UTF-8 observation differs");
}
E::TextObservation projection(const E::Basis& value) {
    return capture_native_editor_text(value.surrounding,value.selection,value.backward?E::Direction::backward:E::Direction::forward);
}
bool same_text(const E::TextObservation& a,const E::TextObservation& b) {
    return a.value==b.value && a.selection==b.selection &&
        (a.selection_direction==E::Direction::backward)==(b.selection_direction==E::Direction::backward);
}
void key(const E::KeyData& value) {
    const auto& v=value.transition; text(v.key,64);
    require(!v.key.empty() && v.code.size()<=64 && std::all_of(v.code.begin(),v.code.end(),[](unsigned char c){return c>=0x21 && c<=0x7e;}) &&
        v.location<=3 && !(v.modifiers&~S::known_modifiers) &&
        (v.phase==S::KeyPhase::down || v.phase==S::KeyPhase::up) && !(v.phase==S::KeyPhase::up && v.repeat),
        "Invalid native editor key");
}
bool same_key(const E::KeyData& a,const E::KeyData& b) {
    return a.transition.location==b.transition.location &&
        (a.transition.code.empty() && b.transition.code.empty()?a.transition.key==b.transition.key:
            !a.transition.code.empty() && a.transition.code==b.transition.code);
}
const std::vector<std::uint64_t>& groups(const E::Observation& value) {
    static const std::vector<std::uint64_t> empty;
    if (const auto* data=std::get_if<E::TextData>(&value.data)) return data->source_groups;
    if (const auto* data=std::get_if<E::CompositionData>(&value.data)) return data->source_groups;
    return empty;
}
void observation(const E::Observation& value) {
    require(value.id && (!value.predecessor || *value.predecessor) && (!value.group || *value.group),"Invalid native editor observation identity");
    observed_text(value.before); if (value.after) observed_text(*value.after);
    require(value.kind==E::Kind::composition?value.transaction!=0:value.transaction==0,"Invalid native editor transaction");
    const auto& dependencies=groups(value);
    require(dependencies.size()<=8,"Native editor source group limit");
    for (std::size_t i=0;i<dependencies.size();++i)
        require(dependencies[i] && std::find(dependencies.begin(),dependencies.begin()+i,dependencies[i])==dependencies.begin()+i,
            "Invalid native editor source group");
    if (value.authority==E::Authority::default_action)
        require(value.group && (dependencies.empty() || dependencies.back()==*value.group),"Missing native editor default source");
    else require(dependencies.empty(),"Unexpected native editor default source");
    if (value.kind==E::Kind::key) {
        const auto* data=std::get_if<E::KeyData>(&value.data);
        require(data && value.authority==E::Authority::native && (!value.after || *value.after==value.before),"Invalid native editor key observation");
        key(*data); return;
    }
    if (value.kind==E::Kind::selection) {
        const auto* data=std::get_if<E::SelectionData>(&value.data);
        require(data && value.authority==E::Authority::range && value.after && value.after->value==value.before.value &&
            data->selection==value.after->selection && data->backward==(value.after->selection_direction==E::Direction::backward),
            "Invalid native editor selection observation");
        return;
    }
    if (value.kind==E::Kind::text) {
        const auto* data=std::get_if<E::TextData>(&value.data);
        require(data && value.after && (value.authority==E::Authority::range || value.authority==E::Authority::default_action),
            "Invalid native editor text authority");
        text(data->input_type,64); text(data->text);
        require(!data->input_type.empty() && data->replacement==value.before.selection &&
            value.after->value==value.before.value.substr(0,data->replacement.begin)+data->text+value.before.value.substr(data->replacement.end),
            "Unproved native editor replacement");
        return;
    }
    require(value.kind==E::Kind::composition,"Invalid native editor observation kind");
    const auto* data=std::get_if<E::CompositionData>(&value.data);
    require(data && value.after,"Native editor composition lacks actual draft readback");
    text(data->text); require(range(data->text,data->selection),"Invalid native editor preedit selection");
    if (data->operation==S::CompositionOperation::begin) {
        require((value.authority==E::Authority::range || value.authority==E::Authority::default_action) &&
            data->replacement==value.before.selection,"Invalid native editor composition begin");
    } else {
        require(value.authority==E::Authority::composition && !data->replacement &&
            (data->operation==S::CompositionOperation::update || data->operation==S::CompositionOperation::commit || data->operation==S::CompositionOperation::cancel),
            "Invalid native editor composition phase");
        if (data->operation==S::CompositionOperation::cancel)
            require(data->text.empty() && data->selection==S::ByteRange{},"Invalid native editor composition cancellation");
    }
}
void retirement(const E::RetirementReadback& value) {
    identity(value.identity);
    require(value.observation_revision && value.readback_attested &&
        (value.availability==E::NativeAvailability::noneditable || value.availability==E::NativeAvailability::unavailable ||
         (value.availability==E::NativeAvailability::available && value.authority_retired)),"Invalid native editor retirement");
}
void validate_composition(const E::CompositionFact& value) {
    require(value.transaction && (value.state==E::CompositionState::pending || value.state==E::CompositionState::live || value.state==E::CompositionState::ended),
        "Invalid native editor composition fact");
}
void publication(const E::EditorPublication& value,const std::optional<S::Identity>& pair) {
    if (pair) identity(*pair);
    require(!(value.basis && value.retirement),"Native editor publication has competing authorities");
    if (value.basis) {
        validate_basis(*value.basis);
        require(pair && same_context(value.basis->identity,*pair),"Native editor basis has no actual rendered pair");
    }
    if (value.retirement) {
        retirement(*value.retirement);
        require(!pair || same_context(value.retirement->identity,*pair),"Native editor retirement has a different actual pair");
    }
    if (value.settlement) require(value.settlement->session && value.settlement->id && value.settlement->submitted_token &&
        (!value.settlement->predecessor || *value.settlement->predecessor) && (value.basis || value.retirement),"Invalid native editor settlement");
    if (value.composition) {
        validate_composition(*value.composition);
        require(value.composition->state==E::CompositionState::ended?
            ((value.basis && !value.basis->composition) || value.retirement):
            (value.basis && (value.composition->state==E::CompositionState::live?
                value.basis->composition==value.composition->transaction:value.basis->composition==0)),
            "Native editor publication composition differs");
    } else require(!value.basis || !value.basis->composition,"Native editor publication lacks composition attestation");
}
E::Settlement tag(const E::Packet& packet) {
    return {packet.session,packet.observation.id,packet.basis.token,packet.observation.predecessor};
}
std::size_t text_bytes(const E::TextObservation& value) { return value.value.capacity(); }
std::size_t observation_bytes(const E::Observation& value) {
    std::size_t total=sizeof(value)+text_bytes(value.before)+(value.after?text_bytes(*value.after):0);
    std::visit([&](const auto& data) {
        using T=std::decay_t<decltype(data)>;
        if constexpr (std::is_same_v<T,E::KeyData>) total+=data.transition.key.capacity()+data.transition.code.capacity();
        else if constexpr (std::is_same_v<T,E::TextData>) total+=data.input_type.capacity()+data.text.capacity()+data.source_groups.capacity()*sizeof(std::uint64_t);
        else if constexpr (std::is_same_v<T,E::CompositionData>) total+=data.text.capacity()+data.source_groups.capacity()*sizeof(std::uint64_t);
    },value.data);
    return total;
}
} // namespace

E::TextObservation capture_native_editor_text(std::string value,std::size_t start,std::size_t end,E::Direction flow) {
    require(direction(flow) && start<=end,"Invalid native editor selection direction or order");
    std::optional<std::size_t> first,last;
    each_scalar(value,NativeEditorCapture::max_text_bytes,[&](std::size_t byte,std::size_t unit) {
        if (unit==start) first=byte;
        if (unit==end) last=byte;
    });
    require(first && last,"Native editor UTF-16 selection splits a scalar");
    const auto bytes=value.size();
    std::string compact(value.data(),value.size());
    return {std::move(compact),start,end,flow,{*first,*last},bytes};
}
E::TextObservation capture_native_editor_text(std::string value,S::ByteRange selection,E::Direction flow) {
    require(direction(flow) && selection.begin<=selection.end,"Invalid native editor byte selection direction or order");
    std::optional<std::size_t> first,last;
    each_scalar(value,NativeEditorCapture::max_text_bytes,[&](std::size_t byte,std::size_t unit) {
        if (byte==selection.begin) first=unit;
        if (byte==selection.end) last=unit;
    });
    require(first && last,"Native editor byte selection splits a scalar");
    const auto bytes=value.size();
    std::string compact(value.data(),value.size());
    return {std::move(compact),*first,*last,flow,selection,bytes};
}

struct NativeEditorCapture::Impl {
    struct Entry { E::Observation observation; S::Identity context; std::size_t bytes; };
    struct Head {
        E::Packet packet;
        std::size_t bytes;
        std::optional<std::uint64_t> ticket;
        std::optional<E::EditorCompletion> completion;
        std::optional<E::CompositionFact> previous_composition;
    };
    NativeEditorEndpoint endpoint;
    const std::thread::id owner{std::this_thread::get_id()};
    std::atomic<bool> terminal_flag{false};
    E::State state{E::State::detached};
    std::optional<E::Basis> current,retired;
    std::optional<E::TextObservation> draft;
    std::optional<E::EditorPublication> published;
    std::optional<S::Identity> actual_pair;
    std::deque<Entry> queue;
    std::optional<Head> head;
    std::optional<E::Revocation> revoke;
    std::optional<std::uint64_t> revoke_ticket;
    std::optional<E::EditorCompletion> revoke_completion;
    std::optional<E::CompositionFact> native_composition;
    std::optional<E::TextObservation> composition_root;
    std::optional<std::uint64_t> admitted_composition,predecessor;
    std::optional<E::Settlement> last_settlement;
    std::map<std::uint64_t,std::uint64_t> defaults;
    std::vector<E::KeyData> held,frontend_held;
    std::uint64_t session{0},serial{0},passage{0},incarnation{0},last_ticket{0};
    std::size_t bytes{0};
    bool paused{false},manual_pause{false},ticking{false},resync_due{false},retiring{false};
    std::string retire_reason;

    explicit Impl(NativeEditorEndpoint value):endpoint(std::move(value)) {
        if (!endpoint.bound()) throw std::invalid_argument("Native editor capture requires a complete endpoint");
    }
    void terminal() noexcept {
        if (!terminal_flag.exchange(true,std::memory_order_acq_rel)) endpoint.terminal.notify(endpoint.terminal.context);
    }
    bool active() {
        if (std::this_thread::get_id()!=owner) { terminal(); return false; }
        return state!=E::State::closed && !terminal_flag.load(std::memory_order_acquire);
    }
    bool advance(std::uint64_t& value) {
        if (value==maximum) { terminal(); return false; }
        ++value; return true;
    }
    void discard() {
        queue.clear(); bytes=head?head->bytes:0;
        defaults.clear(); admitted_composition.reset(); frontend_held.clear();
        composition_root.reset();
    }
    void suspend(std::string_view reason,bool cleanup=true) noexcept {
        if (!active()) return;
        paused=manual_pause=false; state=E::State::suspended; resync_due=true;
        try {
            if (current) retired=current;
            discard();
            if (cleanup && current) { retiring=true; retire_reason=reason; }
        } catch (...) { terminal(); }
    }
    bool install(E::EditorPublication value,std::optional<S::Identity> pair) {
        if (!active() || ticking) return false;
        try {
            publication(value,pair);
            // Compact caller-owned spare capacities before retaining private
            // publication/basis values. Length validation alone is insufficient
            // for a by-value string carrying a large unrelated reservation.
            auto owned=value;
            std::swap(value,owned);
            auto compact_pair=pair;
            published=value; actual_pair=std::move(compact_pair);
            if (!value.basis && !value.retirement) { paused=true; return true; }
            if (head) {
                if (!value.basis && value.retirement) {
                    discard(); state=E::State::suspended; paused=true;
                }
                if (!value.settlement || *value.settlement!=tag(head->packet)) {
                    if (!value.basis || !same_basis(*value.basis,head->packet.basis)) suspend("Native editor head lost its current publication");
                    // An unaccepted busy head has entered no native endpoint.
                    // Exact unchanged publication may resume that same owned
                    // packet after an inert pause; accepted heads still wait.
                    else paused=head->ticket ? true : manual_pause;
                }
                return true; // Receipt and this complete publication must join in tick.
            }
            if (!value.basis) {
                if (current) retired=current;
                current.reset(); draft.reset(); discard(); native_composition.reset(); held.clear();
                state=E::State::suspended; paused=false; return true;
            }
            if (revoke_ticket || retiring) { paused=true; return true; }
            if (value.settlement) {
                require(last_settlement==value.settlement && current && same_basis(*current,*value.basis),
                    "Unmatched native editor settlement publication");
                paused=manual_pause;
                return true;
            }
            if (current && same_basis(*current,*value.basis) && state==E::State::ready) {
                paused=manual_pause; return true; // Keep the exact original native presentation alias.
            }
            if (head || !queue.empty() || !held.empty() || native_composition) {
                suspend("Native editor publication replaced active frontend ownership"); return true;
            }
            require(!retired || !same_basis(*retired,*value.basis),"Retired native editor authority cannot be resumed");
            require(!value.basis->composition && !value.composition,"Unowned native editor composition");
            if (!advance(session) || !advance(incarnation)) return false;
            current=std::move(value.basis); draft=projection(*current); predecessor.reset(); last_settlement.reset();
            defaults.clear(); admitted_composition.reset(); frontend_held.clear();
            state=E::State::ready; paused=manual_pause=false; return true;
        } catch (...) { terminal(); return false; }
    }
    std::optional<std::uint64_t> observe(NativeEditorObservation value,bool during_pause=false) {
        if (!active() || ticking || (during_pause ? !paused : paused) || state!=E::State::ready || !current) return {};
        if (serial==maximum) { terminal(); return {}; }
        try {
            E::Observation observed{serial+1,queue.empty()?(head?std::optional{head->packet.observation.id}:predecessor):
                std::optional{queue.back().observation.id},value.kind,value.authority,value.group,value.group_end,value.transaction,
                std::move(value.before),std::move(value.after),std::move(value.data)};
            observation(observed);
            require(!draft || same_text(observed.before,*draft),"Native editor frontend predecessor changed");
            if (observed.kind==E::Kind::composition) {
                const auto& data=std::get<E::CompositionData>(observed.data);
                require(data.operation==S::CompositionOperation::begin?!admitted_composition:admitted_composition==observed.transaction,
                    "Native editor frontend composition order differs");
                const auto& root=data.operation==S::CompositionOperation::begin?observed.before:
                    composition_root?*composition_root:observed.before;
                require(data.operation==S::CompositionOperation::begin || composition_root,
                    "Native editor composition lost its root draft");
                if (data.operation==S::CompositionOperation::cancel)
                    require(observed.after->value==root.value,"Unproved native editor composition cancellation");
                else if (!(data.operation==S::CompositionOperation::begin && data.text.empty() && *observed.after==observed.before)) {
                    require(observed.after->value==root.value.substr(0,root.selection.begin)+data.text+root.value.substr(root.selection.end) &&
                        observed.after->selection==S::ByteRange{root.selection.begin+data.selection.begin,root.selection.begin+data.selection.end},
                        "Unproved native editor preedit passage");
                }
            } else require(!admitted_composition || observed.kind==E::Kind::key,"Native composition owns frontend editing");
            auto next_held=frontend_held;
            if (const auto* data=std::get_if<E::KeyData>(&observed.data)) {
                const auto found=std::find_if(next_held.begin(),next_held.end(),[&](const auto& held_key){return same_key(*data,held_key);});
                if (data->transition.phase==S::KeyPhase::down) {
                    require((found==next_held.end())!=data->transition.repeat,"Native editor held-key sequence differs");
                    if (found==next_held.end()) { require(next_held.size()<64,"Native editor held-key limit"); next_held.push_back(*data); }
                    else *found=*data;
                } else {
                    require(found!=next_held.end(),"Native editor key-up has no owned down"); next_held.erase(found);
                }
            }
            const auto charge=observation_bytes(observed)+sizeof(Entry)+current->surrounding.capacity()+current->identity.owner.id.capacity()+sizeof(E::Basis);
            if (queue.size()+(head?1:0)>=max_pending || charge>max_bytes || bytes>max_bytes-charge) {
                suspend("Native editor observation queue exhausted"); return {};
            }
            auto next_draft=observed.after?observed.after:std::optional{observed.before};
            queue.push_back({std::move(observed),current->identity,charge}); bytes+=charge; ++serial;
            frontend_held=std::move(next_held); draft=std::move(next_draft);
            if (value.kind==E::Kind::composition) {
                const auto operation=std::get<E::CompositionData>(queue.back().observation.data).operation;
                if (operation==S::CompositionOperation::begin) composition_root=queue.back().observation.before;
                admitted_composition=(operation==S::CompositionOperation::commit || operation==S::CompositionOperation::cancel)?
                    std::nullopt:std::optional{value.transaction};
                if (!admitted_composition) composition_root.reset();
            }
            return serial;
        } catch (...) { suspend("Malformed or discontinuous native editor observation"); return {}; }
    }
    void check_receipt(const E::Receipt& receipt) {
        const auto& packet=head->packet;
        require(receipt.session==packet.session && receipt.id==packet.observation.id && receipt.predecessor==packet.observation.predecessor &&
            receipt.submitted_token==packet.basis.token,"Mismatched native editor receipt");
        require(receipt.outcome==E::Outcome::applied || receipt.outcome==E::Outcome::cancelled || receipt.outcome==E::Outcome::rejected ||
            receipt.outcome==E::Outcome::unknown,"Invalid native editor outcome");
        if (receipt.outcome==E::Outcome::unknown) return;
        const auto expected=packet.observation.kind==E::Kind::composition?packet.observation.transaction:
            head->previous_composition?head->previous_composition->transaction:0;
        if (!receipt.basis) {
            require(receipt.continuity==E::Continuity::replaced && !receipt.default_token && receipt.retirement,
                "Native editor receipt lacks checked retirement");
            retirement(*receipt.retirement);
            require(same_owner(receipt.retirement->identity,packet.basis.identity),"Native editor receipt retired a foreign owner");
            if (receipt.composition) require(receipt.composition->state==E::CompositionState::ended && expected &&
                receipt.composition->transaction==expected,"Native editor receipt retired a foreign composition");
            return;
        }
        validate_basis(*receipt.basis); require(!receipt.retirement,"Unexpected native editor retirement");
        require(receipt.continuity==E::Continuity::same || receipt.continuity==E::Continuity::key_retarget || receipt.continuity==E::Continuity::replaced,
            "Invalid native editor continuity");
        if (receipt.continuity==E::Continuity::same)
            require(same_context(receipt.basis->identity,packet.basis.identity),"Unattested native editor context replacement");
        if (receipt.continuity==E::Continuity::key_retarget)
            require(packet.observation.authority==E::Authority::native || packet.observation.authority==E::Authority::default_action,
                "Unattested native editor key retarget");
        if (receipt.default_token) {
            const auto* data=std::get_if<E::KeyData>(&packet.observation.data);
            require(data && data->transition.phase==S::KeyPhase::down && packet.observation.group==receipt.default_token->group &&
                receipt.default_token->group && receipt.default_token->token,"Invalid native editor default authorization");
        }
        if (receipt.composition) {
            const auto fact=*receipt.composition; validate_composition(fact);
            require(expected && fact.transaction==expected,"Native editor composition receipt transaction differs");
            require(fact.state==E::CompositionState::live?receipt.basis->composition==fact.transaction:receipt.basis->composition==0,
                "Native editor composition receipt lacks checked native readback");
            if (fact.state==E::CompositionState::pending && head->previous_composition && head->previous_composition->state==E::CompositionState::live) {
                const auto* data=std::get_if<E::CompositionData>(&packet.observation.data);
                require(data && data->operation==S::CompositionOperation::update && data->text.empty(),"Unexpected pending native composition");
            }
        } else require(!receipt.basis->composition && !head->previous_composition &&
            !(packet.observation.kind==E::Kind::composition && receipt.outcome==E::Outcome::applied),"Missing native editor composition continuity");
        if (packet.observation.kind==E::Kind::composition && receipt.outcome==E::Outcome::applied) {
            const auto operation=std::get<E::CompositionData>(packet.observation.data).operation;
            const bool ending=operation==S::CompositionOperation::commit || operation==S::CompositionOperation::cancel;
            require(receipt.composition && (receipt.composition->state==E::CompositionState::ended)==ending,
                "Native editor composition phase did not settle");
        }
    }
    bool joined(const E::Receipt& receipt) const {
        return published && published->settlement==std::optional{tag(head->packet)} &&
            same_basis(published->basis,receipt.basis) && published->composition==receipt.composition && published->retirement==receipt.retirement &&
            (!receipt.basis || (actual_pair && same_context(receipt.basis->identity,*actual_pair)));
    }
    void settle() {
        if (!head || !head->completion) return;
        const auto& result=head->completion->result;
        require(result.admission==E::Admission::completed || result.admission==E::Admission::rejected,
            "Native editor completion is not a settled receipt");
        require(bool(result.receipt),"Native editor completion lacks its correlated receipt");
        const auto receipt=*result.receipt;
        if (!joined(receipt)) {
            require(!published || published->settlement!=std::optional{tag(head->packet)},
                "Native editor completion conflicts with its tagged current publication");
            return; // Keep the exact completion and old head until a current pair joins.
        }
        const auto observed=head->packet.observation;
        const bool was_retiring=retiring || state==E::State::suspended;
        // A completed native key dispatch owns its down/up even when its
        // default was cancelled/rejected. A pre-entry rejected admission did
        // not dispatch that key and must not manufacture held ownership.
        if (receipt.basis && result.admission==E::Admission::completed) {
            if (const auto* data=std::get_if<E::KeyData>(&observed.data)) {
                const auto found=std::find_if(held.begin(),held.end(),[&](const auto& held_key){return same_key(*data,held_key);});
                if (data->transition.phase==S::KeyPhase::down) { if (found==held.end()) held.push_back(*data); else *found=*data; }
                else if (found!=held.end()) held.erase(found);
            }
        }
        bytes-=head->bytes; head.reset(); predecessor=observed.id; last_settlement=E::Settlement{receipt.session,receipt.id,receipt.submitted_token,receipt.predecessor};
        current=receipt.basis;
        if (!current) {
            draft.reset(); discard(); held.clear(); native_composition.reset(); retiring=false; revoke.reset();
            state=E::State::suspended; paused=false; return;
        }
        native_composition=receipt.composition && receipt.composition->state!=E::CompositionState::ended?receipt.composition:std::nullopt;
        if (receipt.outcome!=E::Outcome::applied || receipt.continuity==E::Continuity::replaced || was_retiring) {
            suspend("Native editor outcome requires resynchronization"); draft=projection(*current); return;
        }
        if (receipt.default_token) {
            require(defaults.contains(receipt.default_token->group) || defaults.size()<max_pending,"Native editor default authorization limit");
            defaults[receipt.default_token->group]=receipt.default_token->token;
        }
        if ((observed.authority==E::Authority::default_action || observed.kind==E::Kind::key) && observed.group_end) {
            if (groups(observed).empty()) { if (observed.group) defaults.erase(*observed.group); }
            else for (auto group:groups(observed)) defaults.erase(group);
        }
        if (queue.empty()) { draft=projection(*current); frontend_held=held; admitted_composition=native_composition?
            std::optional{native_composition->transaction}:std::nullopt; }
        state=E::State::ready; paused=manual_pause;
    }
    void prepare_head() {
        if (head || revoke_ticket || retiring || state!=E::State::ready || paused || queue.empty() || !current) return;
        const auto& next=queue.front(); const auto& observed=next.observation;
        if (observed.authority==E::Authority::range &&
            (!same_context(next.context,current->identity) || !same_text(observed.before,projection(*current)))) {
            suspend("Native editor predecessor projection changed"); return;
        }
        if (observed.authority==E::Authority::composition &&
            (!native_composition || native_composition->transaction!=observed.transaction)) {
            suspend("Native editor composition predecessor changed"); return;
        }
        E::Packet packet{session,*current,{},{},observed};
        if (observed.authority==E::Authority::default_action) {
            auto sources=groups(observed); if (sources.empty()) sources.push_back(*observed.group);
            for (auto group:sources) {
                const auto found=defaults.find(group);
                if (found==defaults.end()) { suspend("Native keyboard default was not authorized"); return; }
                packet.default_dependencies.push_back({group,found->second});
            }
            packet.default_token=packet.default_dependencies.back().token;
        }
        const auto charge=observation_bytes(packet.observation)+sizeof(Entry)+sizeof(E::Basis)+
            packet.basis.surrounding.capacity()+packet.basis.identity.owner.id.capacity()+
            packet.default_dependencies.capacity()*sizeof(E::DefaultDependency);
        if (charge>max_bytes || bytes-next.bytes>max_bytes-charge) {
            suspend("Native editor packet exceeds retained byte limit"); return;
        }
        bytes=bytes-next.bytes+charge;
        head=Head{std::move(packet),charge,{},{},native_composition}; queue.pop_front();
    }
    void tick() {
        if (!active() || ticking) return;
        ticking=true;
        struct Guard { bool& flag; ~Guard(){flag=false;} } guard{ticking};
        try {
            // Cleanup uses the last checked native token. Discovering a new
            // token first would make that exact revocation stale. A sent head
            // settles before cleanup; unknown heads never reach either path.
            if (resync_due && !retiring && !revoke_ticket && !head) {
                resync_due=false; endpoint.resync(); if (!active()) return;
            }
            prepare_head();
            if (head) {
                if (!head->ticket) {
                    if (retiring || state!=E::State::ready) { bytes-=head->bytes; head.reset(); }
                    else if (!paused) {
                        if (last_ticket==maximum) { terminal(); return; }
                        auto copy=head->packet;
                        const auto ticket=endpoint.submit(std::move(copy));
                        if (ticket) head->ticket=*ticket; // Retain a known handle even if callback Close revoked ingress.
                        if (!active()) return;
                        if (!ticket) return;
                        require(*ticket>last_ticket,"Native editor endpoint ticket did not increase");
                        last_ticket=*ticket;
                    }
                }
                if (head && head->ticket && !head->completion) {
                    auto result=endpoint.take(*head->ticket);
                    if (result) {
                        require(result->ticket==*head->ticket,"Foreign native editor completion ticket");
                        text(result->result.detail,4096);
                        if (result->result.receipt) {
                            if (result->result.receipt->basis) validate_basis(*result->result.receipt->basis);
                            if (result->result.receipt->retirement) retirement(*result->result.receipt->retirement);
                            if (result->result.receipt->composition) validate_composition(*result->result.receipt->composition);
                            check_receipt(*result->result.receipt);
                        }
                        auto owned=*result;
                        head->completion=std::move(owned);
                        if (!active()) return;
                        if (head->completion->result.admission==E::Admission::terminal) { terminal(); return; }
                        if (head->completion->result.receipt) {
                            if (head->completion->result.receipt->outcome==E::Outcome::unknown) { terminal(); return; }
                        }
                    }
                }
                settle();
                if (head) return;
            }
            if (revoke_ticket) {
                if (!revoke_completion) {
                    const auto result=endpoint.take(*revoke_ticket);
                    if (result) {
                        require(result->ticket==*revoke_ticket,"Foreign native editor revocation completion ticket");
                        text(result->result.detail,4096);
                        require(!result->result.receipt,"Unexpected native editor observation receipt for revocation");
                        revoke_completion=*result;
                    }
                }
                if (!active() || !revoke_completion) return;
                text(revoke_completion->result.detail,4096);
                require(revoke_completion->ticket==*revoke_ticket && revoke_completion->result.admission==E::Admission::completed &&
                    !revoke_completion->result.receipt,"Native editor revocation did not complete certainly");
                if (!published || published->basis || !published->retirement) return;
                require(revoke && published->retirement->authority_retired && same_owner(published->retirement->identity,revoke->basis.identity),
                    "Native editor revocation lacks its checked owned retirement");
                revoke_ticket.reset(); revoke_completion.reset(); revoke.reset(); retiring=false; current.reset(); draft.reset();
                held.clear(); native_composition.reset(); state=E::State::suspended;
            }
            if (retiring) {
                if (!current || (published && !published->basis && published->retirement)) {
                    retiring=false; revoke.reset(); current.reset(); draft.reset(); held.clear(); native_composition.reset(); return;
                }
                if (!revoke) revoke=E::Revocation{*current,incarnation,native_composition?native_composition->transaction:0,held,retire_reason};
                if (last_ticket==maximum) { terminal(); return; }
                auto copy=*revoke; auto ticket=endpoint.revoke(std::move(copy));
                if (ticket) revoke_ticket=*ticket;
                if (!active() || !ticket) return;
                require(*ticket>last_ticket,"Native editor revocation ticket did not increase");
                last_ticket=*ticket; return;
            }
        } catch (...) { terminal(); }
    }
};

NativeEditorCapture::NativeEditorCapture(NativeEditorEndpoint endpoint):impl_(std::make_unique<Impl>(std::move(endpoint))) {}
NativeEditorCapture::~NativeEditorCapture() { close(); }
bool NativeEditorCapture::install(E::EditorPublication value,std::optional<S::Identity> pair) { return impl_->install(std::move(value),std::move(pair)); }
std::optional<std::uint64_t> NativeEditorCapture::observe(NativeEditorObservation value) { return impl_->observe(std::move(value)); }
std::optional<std::uint64_t> NativeEditorCapture::observe_paused(NativeEditorObservation value) { return impl_->observe(std::move(value),true); }
std::optional<std::uint64_t> NativeEditorCapture::next_passage() {
    if (!impl_->active() || impl_->ticking || impl_->paused || impl_->state!=E::State::ready || !impl_->advance(impl_->passage)) return {};
    return impl_->passage;
}
void NativeEditorCapture::pause() { if (impl_->active()) impl_->paused=impl_->manual_pause=true; }
void NativeEditorCapture::pause_pending() { if (impl_->active()) impl_->paused=true; }
bool NativeEditorCapture::resume(const E::Basis& value) {
    if (!impl_->active() || impl_->ticking || impl_->state!=E::State::ready || !impl_->current || value!=*impl_->current ||
        !impl_->published || !impl_->published->basis || !same_basis(*impl_->published->basis,value) ||
        !impl_->actual_pair || !same_context(value.identity,*impl_->actual_pair)) return false;
    impl_->paused=impl_->manual_pause=false; return true;
}
void NativeEditorCapture::retire(std::string reason) {
    if (!impl_->active()) return;
    try { text(reason,512); impl_->suspend(std::move(reason)); } catch (...) { impl_->terminal(); }
}
void NativeEditorCapture::tick() { impl_->tick(); }
void NativeEditorCapture::close() noexcept {
    if (!impl_ || !impl_->active()) return;
    if (!impl_->ticking && impl_->head && !impl_->head->ticket) impl_->head.reset();
    impl_->state=E::State::closed; impl_->paused=impl_->manual_pause=false; impl_->discard();
    impl_->resync_due=false; impl_->retiring=false;
    if (!impl_->ticking && !impl_->revoke_ticket) impl_->revoke.reset();
}
E::State NativeEditorCapture::state() const noexcept {
    return impl_->terminal_flag.load(std::memory_order_acquire)?E::State::terminal_unknown:impl_->state;
}
bool NativeEditorCapture::paused() const noexcept { return impl_->paused; }
const E::CompositionFact* NativeEditorCapture::composition() const noexcept { return impl_->native_composition?&*impl_->native_composition:nullptr; }
const E::Basis* NativeEditorCapture::basis() const noexcept { return impl_->current?&*impl_->current:nullptr; }
const E::TextObservation* NativeEditorCapture::draft() const noexcept { return impl_->draft?&*impl_->draft:nullptr; }
std::size_t NativeEditorCapture::pending() const noexcept {
    return impl_->queue.size()+(impl_->head?1:0)+(impl_->revoke_ticket?1:0)+
        (!impl_->head && !impl_->revoke_ticket && (impl_->retiring || impl_->resync_due)?1:0);
}
std::size_t NativeEditorCapture::pending_bytes() const noexcept { return impl_->bytes; }
const E::Packet* NativeEditorCapture::unresolved() const noexcept { return impl_->head?&impl_->head->packet:nullptr; }

} // namespace foundation::host
