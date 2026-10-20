// SPDX-License-Identifier: CC0-1.0
#pragma once
#include "browser_surface_codec.hpp"
#include "browser_surface_editor_codec.hpp"
#include "browser_document_codec.hpp"
#include <foundation/gui/surface_editor.hpp>
#include <exception>
#include <functional>
#include <memory>
#include <mutex>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>

namespace foundation::host {
class BrowserSurfaceSession;
// The getter is called only by owner-thread application access. Terminal
// notification retains only its trusted context, never an App or access gate.
// Holding the mutex through notify lets detach join a foreign notification.
class BrowserDocumentTerminalBinding {
    std::mutex mutex_;
    ::foundation::gui_document::TerminalHook hook_;
    bool detached_{},notified_{};
public:
    void bind(::foundation::gui_document::TerminalHook hook){
        if(!hook.notify)throw std::invalid_argument("Document terminal hook is absent");
        std::lock_guard guard(mutex_);
        if(detached_)throw std::logic_error("Document terminal binding is detached");
        if(hook_.notify&&(hook_.notify!=hook.notify||hook_.context!=hook.context))
            throw std::invalid_argument("Document terminal hook changed");
        hook_=hook;
    }
    void notify()noexcept{
        std::lock_guard guard(mutex_);
        if(detached_||notified_||!hook_.notify)return;
        notified_=true;hook_.notify(hook_.context);
    }
    void detach()noexcept{std::lock_guard guard(mutex_);detached_=true;hook_={};}
};
struct BrowserDocumentEndpoint {
    std::function<::foundation::gui_document::Submission(::foundation::gui_document::Intent)> submit;
    std::function<std::optional<::foundation::gui_document::Completion>(::foundation::gui_document::Ticket)> take;
    std::function<::foundation::gui_document::State()> state;
    ::foundation::gui_document::TerminalHook terminal;
    std::shared_ptr<BrowserDocumentTerminalBinding> terminal_binding;
    std::function<void()> activate_terminal;
    bool bound()const noexcept{return submit&&take&&state&&terminal.notify;}
    bool empty()const noexcept{return !submit&&!take&&!state&&!terminal.notify;}
};
struct BrowserEditorEndpoint {
    using Editor=::foundation::gui_editor::Packet;
    std::string profile="editor_v1";
    std::uint32_t protocol=surface_web::editor_protocol_version;
    gui_surface::Features capabilities=surface_web::editor_supported;
    std::function<std::optional<std::uint64_t>(Editor)> submit;
    std::function<std::optional<std::uint64_t>(::foundation::gui_editor::Revocation)> revoke;
    std::function<std::optional<::foundation::gui_editor::EditorCompletion>(std::uint64_t)> take;
    std::function<void()> resync;
    ::foundation::gui_editor::EditorTerminalHook terminal;
    bool bound()const noexcept {
        constexpr auto core=surface_web::editor_supported&~gui_surface::feature(gui_surface::Feature::mouse_input);
        return profile=="editor_v1"&&protocol==surface_web::editor_protocol_version&&
            !(capabilities&~surface_web::editor_supported)&&(capabilities&core)==core&&submit&&revoke&&take&&resync&&terminal.notify;
    }
};

// A serialized generic facade. The underlying WebAdapter and mutable Policy do
// not escape. All callbacks must enqueue owned work; they must not enter an
// engine synchronously. Ordinary handle callbacks may publish a successor.
// Like gui::Adapter, every operation belongs to its creating UI thread.
class BrowserSurfaceAdapter final : public ::gui::Adapter {
public:
    using Revoked = std::function<void(gui_surface::Revocation)>;
    explicit BrowserSurfaceAdapter(std::uint64_t generation, ::gui::EventSink legacy_sink = {}, Revoked revoked = {},
                                   gui_surface::Features ceiling = surface_web::basic_supported,
                                   surface_web::Profile profile = surface_web::Profile::legacy,
                                   BrowserEditorEndpoint editor = {},BrowserDocumentEndpoint document = {})
        : editor_endpoint_(std::move(editor)), document_endpoint_(std::move(document)), legacy_([this](const ::gui::Event& event) { legacy_event(event); }),
          policy_(std::make_unique<gui_surface::Policy>(gui_surface::Capabilities{}, generation)),
          generation_(generation), ceiling_(ceiling), profile_(profile), legacy_sink_(std::move(legacy_sink)), revoked_(std::move(revoked)) {
        const auto allowed = profile == surface_web::Profile::legacy ? surface_web::basic_supported :
            profile == surface_web::Profile::mouse_v1 ? surface_web::successor_supported :
            profile == surface_web::Profile::editor_v1 ? surface_web::editor_supported : 0;
        if (!allowed || (ceiling & ~allowed)) throw std::invalid_argument("Unsupported physical surface ceiling/profile");
        constexpr auto editor_core=surface_web::editor_supported&~gui_surface::feature(gui_surface::Feature::mouse_input);
        if(profile==surface_web::Profile::editor_v1&&(ceiling&editor_core)!=editor_core)
            throw std::invalid_argument("Editor ceiling requires the complete editor core");
        if((profile==surface_web::Profile::editor_v1)!=editor_endpoint_.bound())
            throw std::invalid_argument("Editor profile requires its exact explicit native endpoint");
        if(!document_endpoint_.empty()&&!document_endpoint_.bound())
            throw std::invalid_argument("Document capability requires all owned hooks and terminal notification");
        cache_pair(pair(nullptr));
    }
    BrowserSurfaceAdapter(const BrowserSurfaceAdapter&) = delete;
    BrowserSurfaceAdapter& operator=(const BrowserSurfaceAdapter&) = delete;

    bool failed() const noexcept { return failed_; }
    std::uint64_t generation() const noexcept { return generation_; }
    bool input_admitted() const noexcept { return !failed_ && !closed_ && !publishing_ && !callback_; }
    bool editor_endpoint_bound()const noexcept{return profile_==surface_web::Profile::editor_v1&&editor_endpoint_.bound();}
    bool document_endpoint_bound()const noexcept{return document_endpoint_.bound();}
    void activate_document_endpoint(){if(!document_endpoint_bound()||!document_endpoint_.activate_terminal)return;require_input();Callback guard(*this,false,__LINE__);document_endpoint_.activate_terminal();}
    ::foundation::gui_document::Submission document_submit(::foundation::gui_document::Intent value){
        namespace D=::foundation::gui_document;
        if(!document_endpoint_bound()||!input_admitted())return {closed()?D::Admission::closed:D::Admission::unavailable,{}};
        Callback guard(*this,false,__LINE__);return document_endpoint_.submit(std::move(value));
    }
    std::optional<::foundation::gui_document::Completion> document_take(::foundation::gui_document::Ticket ticket){
        if(!document_endpoint_bound()||!input_admitted()||!ticket.value)return {};
        std::optional<::foundation::gui_document::Completion> result;
        {Callback guard(*this,false,__LINE__);result=document_endpoint_.take(ticket);}
        if(result){
            if(result->ticket!=ticket){fail(__LINE__);throw std::invalid_argument("Mismatched document completion ticket");}
            (void)document_web::json_completion(*result);
            if(result->outcome==::foundation::gui_document::Outcome::unknown)fail(__LINE__);
        }
        return result;
    }
    ::foundation::gui_document::State document_state(){
        if(!document_endpoint_bound()||!input_admitted())throw std::logic_error("Document endpoint state is unavailable");
        Callback guard(*this,false,__LINE__);return document_endpoint_.state();
    }
    const gui_surface::Capabilities& capabilities() const noexcept {
        return connected_ && policy_ && !failed_ ? (profile_==surface_web::Profile::editor_v1?editor_capabilities_:policy_->capabilities()) : absent_;
    }
    const gui_surface::Presentation* accepted() const noexcept {
        return policy_ && !publishing_ && !failed_ ?
            (profile_==surface_web::Profile::editor_v1?(editor_presentation_?&*editor_presentation_:nullptr):policy_->accepted()) : nullptr;
    }
    bool surface_focused() const noexcept { return policy_ && !publishing_ && !failed_ && policy_->focused(); }
    bool active() const noexcept { return policy_ && !publishing_ && !failed_ && policy_->active(); }
    // Trusted native ownership only. Renderer input cannot invoke this setter.
    // Ending a native service never reconstructs retired key/pointer authority.
    void set_owned_service_active(bool active) {
        if (failed_ || closed_ || owned_service_ == active) return;
        require_publication();
        if(notifying_)throw std::logic_error("Native service notification is active");
        owned_service_ = active;
        try {
            if(!active){set_service(legacy_service_);return;}
            service_=true; // Close admission before retiring or notifying.
            pointers_.clear();clear_editor();
            if(policy_&&policy_->accepted()){
                auto result=policy_->legacy_present(policy_->accepted()->identity.presentation_revision);
                if(result.status!=gui_surface::Status::ok){fail(__LINE__);return;}
                result.revoked.reason=gui_surface::RevocationReason::service;
                notify(std::move(result.revoked),true);
            }
        }
        catch (...) { fail(__LINE__); throw; }
    }

    // Queue returned revocation after return, including an identity with no held
    // keys: retiring native ownership also cancels raw pointer capture.
    gui_surface::CommitResult present_pair(::gui::Snapshot next, const gui_surface::Presentation& surface) {
        using gui_surface::Status;
        if(profile_==surface_web::Profile::editor_v1)return {Status::unsupported,{}};
        if (failed_ || closed_ || !policy_) return {Status::closed,{}};
        if (publishing_) return {Status::busy,{}};
        if (!connected_) return {Status::unsupported,{}};
        if (next.revision != surface.identity.presentation_revision) return {Status::stale_revision,{}};
        const auto* previous=policy_->accepted();
        const bool retain_pointers=previous&&surface.available&&previous->identity.owner==surface.identity.owner&&
            previous->identity.generation==surface.identity.generation&&previous->identity.epoch==surface.identity.epoch&&previous->identity.context==surface.identity.context;
        Publishing guard(*this);
        auto preparation = policy_->prepare(surface);
        if (preparation.status != Status::ok) return {preparation.status,{}};
        // Complete companion allocations before legacy mutation where possible.
        auto declaration = surface_web::json_presentation(surface,profile_);
        try {
            legacy_.present(std::move(next));
            if (legacy_.snapshot().revision != surface.identity.presentation_revision || !owner_matches(surface)) {
                fail(__LINE__); return {Status::stale_revision,{}};
            }
            auto candidate = pair(&declaration);
            auto terminal = terminal_pair(candidate);
            auto committed = policy_->commit(std::move(preparation.prepared), legacy_.snapshot().revision);
            if (committed.status != Status::ok) { fail(__LINE__); return committed; }
            // Existing boolean slots are changed without allocation after commit.
            auto& state = object(object(candidate).at("surface"));
            state.at("focused").value = policy_->focused();
            state.at("active").value = policy_->active();
            publication_ = std::move(candidate); terminal_ = std::move(terminal);
            if(!retain_pointers){pointers_.clear();editor_held_.clear();}
            return committed;
        } catch (...) { fail(__LINE__); throw; }
    }
    gui_surface::CommitResult present_editor_pair(::gui::Snapshot next,const gui_surface::Presentation& surface,
        std::optional<::foundation::gui_editor::EditorPublication> publication,
        std::optional<::foundation::gui_editor::CompositionFact> composition) {
        namespace E=::foundation::gui_editor;
        using gui_surface::Status;
        if(!editor_endpoint_bound())return {Status::unsupported,{}};
        if(failed_||closed_||!policy_)return {Status::closed,{}};
        if(publishing_||notifying_)return {Status::busy,{}};
        if(!connected_)return {Status::unsupported,{}};
        if(next.revision!=surface.identity.presentation_revision)return {Status::stale_revision,{}};
        if(composition)(void)surface_editor_web::json_composition(*composition);
        const auto* previous=policy_->accepted();
        const bool retain_keys=previous&&surface.available&&previous->identity.owner==surface.identity.owner&&
            previous->identity.generation==surface.identity.generation&&previous->identity.epoch==surface.identity.epoch&&
            previous->identity.context==surface.identity.context;
        const bool retain_pointers=retain_keys&&same_rect(previous->bounds,surface.bounds)&&same_rect(previous->clip,surface.clip)&&
            previous->display_scale==surface.display_scale;
        const auto transaction=composition&&composition->state!=E::CompositionState::ended?
            std::optional{composition->transaction}:std::nullopt;
        try{
            surface_web::detail::validate_presentation(surface,editor_capabilities_,profile_,transaction);
            const auto core=surface_web::editor_supported&~surface_web::successor_supported;
            const bool eligible=surface.available&&surface.editor&&surface.editor->editable;
            if(eligible&&((editor_capabilities_.supported&surface_web::editor_supported&~gui_surface::feature(gui_surface::Feature::mouse_input))!=
                (surface_web::editor_supported&~gui_surface::feature(gui_surface::Feature::mouse_input))||!publication||!publication->basis))
                return {Status::unsupported,{}};
            if(publication&&publication->basis){
                const auto& basis=*publication->basis;
                if(!surface.editor||surface_editor_web::parse_basis(surface_editor_web::json_basis(basis))!=basis||!same_context(basis.identity,surface.identity)||
                    basis.editor_revision!=surface.editor->revision||basis.surrounding!=surface.editor->surrounding||
                    basis.selection!=surface.editor->selection||basis.backward!=surface.editor->selection_backward||
                    basis.composition!=surface.editor->composition_transaction||publication->retirement)
                    return {Status::stale_identity,{}};
            }
            if(publication&&publication->retirement){
                const auto& r=*publication->retirement;
                if(publication->basis||!r.readback_attested||!r.observation_revision||(r.identity.owner!=surface.identity.owner||r.identity.generation!=surface.identity.generation||r.identity.epoch!=surface.identity.epoch)||surface.editor||
                    (r.availability!=E::NativeAvailability::noneditable&&r.availability!=E::NativeAvailability::unavailable&&
                     !(r.availability==E::NativeAvailability::available&&r.authority_retired))||
                    (r.availability==E::NativeAvailability::unavailable&&surface.available))return {Status::stale_identity,{}};
            }
            if(publication&&publication->basis)
                publication->basis->identity.presentation_revision=surface.identity.presentation_revision; // Explicit GUI-only alias.
            if(publication&&publication->basis&&editor_inert_publication_&&editor_inert_publication_->basis&&
                publication->basis->token==editor_inert_publication_->basis->token&&
                (!same_basis(publication->basis,editor_inert_publication_->basis)||
                 (publication->composition!=editor_inert_publication_->composition&&
                  (!publication->settlement||publication->settlement==editor_inert_publication_->settlement))))
                return {Status::stale_identity,{}};
            if(publication&&publication->composition!=composition)return {Status::stale_identity,{}};
            if(publication)(void)surface_editor_web::json_publication(*publication);
            if(composition&&(!publication||
                (composition->state!=E::CompositionState::ended&&!publication->basis)||
                (publication->basis&&(composition->state==E::CompositionState::live?
                    publication->basis->composition!=composition->transaction:publication->basis->composition!=0))))
                return {Status::stale_identity,{}};
            auto physical=surface;physical.editor.reset();physical.required&=~core;
            auto preparation=policy_->prepare(physical);if(preparation.status!=Status::ok)return {preparation.status,{}};
            // Prepare complete public/private companions before mutating legacy
            // state. No engine callback runs during paired GUI publication.
            (void)surface_web::json_presentation(surface,profile_,transaction);
            auto retained=std::optional{surface};
            auto inert=publication?std::optional<::foundation::gui_editor::EditorPublication>{}:
                (editor_publication_?editor_publication_:editor_inert_publication_);
            Publishing guard(*this);
            legacy_.present(std::move(next));
            if(legacy_.snapshot().revision!=surface.identity.presentation_revision||!owner_matches(surface)){
                fail(__LINE__);return {Status::stale_revision,{}};
            }
            Json candidate=Json::Object{{"snapshot",legacy_.presentation()},
                {"surface",surface_web::json_state(editor_capabilities_,&surface,policy_->focused(),policy_->active(),transaction,
                    policy_->last_sequence(),service_,profile_)},
                {"editor",publication?surface_editor_web::json_publication(*publication):Json{}}};
            auto terminal=terminal_pair(candidate);
            auto committed=policy_->commit(std::move(preparation.prepared),legacy_.snapshot().revision);
            if(committed.status!=Status::ok){fail(__LINE__);return committed;}
            auto& state=object(object(candidate).at("surface"));state.at("focused").value=policy_->focused();state.at("active").value=policy_->active();
            editor_presentation_=std::move(retained);editor_publication_=std::move(publication);editor_composition_=std::move(composition);
            editor_inert_publication_=std::move(inert);
            publication_=std::move(candidate);terminal_=std::move(terminal);
            if(!retain_pointers)pointers_.clear();
            if(!retain_keys)editor_held_.clear();
            return committed;
        }catch(...){fail(__LINE__);throw;}
    }
    // A checked null editor readback can follow an already redacted empty
    // widget Snapshot. It retires authority; it never invents an owner widget or
    // constructs a replacement physical presentation merely to carry a proof.
    gui_surface::CommitResult present_editor_retirement(::gui::Snapshot next,::foundation::gui_editor::EditorPublication publication){
        using gui_surface::Status;
        if(!editor_endpoint_bound())return {Status::unsupported,{}};
        if(failed_||closed_||!policy_)return {Status::closed,{}};
        if(publishing_||notifying_)return {Status::busy,{}};
        if(!connected_)return {Status::unsupported,{}};
        if(publication.basis||!publication.retirement||
            (publication.composition&&publication.composition->state!=::foundation::gui_editor::CompositionState::ended))
            return {Status::invalid_value,{}};
        try {
            auto metadata=surface_editor_web::json_publication(publication);
            const auto& proof=*publication.retirement;
            const auto* prior=editor_presentation_?&editor_presentation_->identity:
                (editor_retired_identity_?&*editor_retired_identity_:nullptr);
            if(proof.identity.generation!=generation_||(prior&&(proof.identity.owner!=prior->owner||proof.identity.generation!=prior->generation||proof.identity.epoch!=prior->epoch)))return {Status::stale_identity,{}};
            Publishing guard(*this);
            legacy_.present(std::move(next));
            Json candidate=Json::Object{{"snapshot",legacy_.presentation()},
                {"surface",surface_web::json_state(editor_capabilities_,nullptr,false,policy_->active(),std::nullopt,
                    policy_->last_sequence(),service_,profile_)},{"editor",std::move(metadata)}};
            auto terminal=terminal_pair(candidate);
            auto retired=policy_->legacy_present(legacy_.snapshot().revision);
            if(retired.status!=Status::ok){fail(__LINE__);return retired;}
            clear_editor();editor_publication_=std::move(publication);pointers_.clear();
            publication_=std::move(candidate);terminal_=std::move(terminal);
            return retired;
        }catch(...){fail(__LINE__);throw;}
    }
    const ::foundation::gui_editor::EditorPublication* editor_publication()const noexcept{
        return editor_endpoint_bound()&&!failed_&&!closed_&&!publishing_&&editor_publication_?&*editor_publication_:nullptr;
    }
    std::optional<std::uint64_t> editor_submit(::foundation::gui_editor::Packet packet){
        if(!editor_endpoint_bound()||!input_admitted()||service_||!editor_publication_||!editor_publication_->basis||
            !editor_presentation_||!editor_presentation_->available||!editor_presentation_->editor||!editor_presentation_->editor->editable||
            !policy_->accepted()||!policy_->focused()||!policy_->active())return {};
        std::optional<std::uint64_t> result;
        { Callback guard(*this,false,__LINE__);result=editor_endpoint_.submit(std::move(packet)); }
        if(failed_)return {};
        return result;
    }
    std::optional<std::uint64_t> editor_revoke(::foundation::gui_editor::Revocation record){
        if(!editor_endpoint_bound()||!input_admitted())return {};
        std::optional<std::uint64_t> result;
        { Callback guard(*this,false,__LINE__);result=editor_endpoint_.revoke(std::move(record)); }
        if(failed_)return {};
        return result;
    }
    std::optional<::foundation::gui_editor::EditorCompletion> editor_take(std::uint64_t ticket){
        if(!editor_endpoint_bound()||failed_||closed_||publishing_||callback_||!ticket)return {};
        std::optional<::foundation::gui_editor::EditorCompletion> result;
        { Callback guard(*this,false,__LINE__);result=editor_endpoint_.take(ticket); }
        if(failed_||!result)return {};
        try {
            (void)surface_editor_web::json_completion(*result);
            if(result->ticket!=ticket)throw std::invalid_argument("Mismatched editor completion ticket");
            check_completion(*result);
            if(result->result.admission==::foundation::gui_editor::Admission::terminal||
                (result->result.receipt&&result->result.receipt->outcome==::foundation::gui_editor::Outcome::unknown))fail(__LINE__);
        }catch(...){fail(__LINE__);throw;}
        return result;
    }
    void editor_resync(){
        if(!editor_endpoint_bound()||!input_admitted())return;
        Callback guard(*this,false,__LINE__);editor_endpoint_.resync();
    }
    gui_surface::AcceptResult accept(gui_surface::Event event) {
        using gui_surface::Status;
        if (failed_ || closed_ || !policy_) return {Status::closed,{}};
        if (!input_admitted()) return {Status::busy,{}};
        if (service_) return {Status::unavailable,{}};
        const auto* key=std::get_if<gui_surface::KeyTransition>(&event.input);
        const auto held=key?std::find_if(editor_held_.begin(),editor_held_.end(),[&](const auto& value){
            return value.key.location==key->location&&((!value.key.code.empty()&&!key->code.empty())?
                value.key.code==key->code:value.key.code==key->code&&value.key.key==key->key)&&
                same_context(value.identity,event.identity);
        }):editor_held_.end();
        const bool owned_release=profile_==surface_web::Profile::editor_v1&&key&&key->phase==gui_surface::KeyPhase::up&&
            held!=editor_held_.end()&&policy_->accepted()&&same_context(policy_->accepted()->identity,event.identity);
        const bool body_keys=editor_publication_&&editor_publication_->retirement&&
            editor_publication_->retirement->availability==::foundation::gui_editor::NativeAvailability::noneditable&&
            !editor_publication_->retirement->authority_retired&&policy_->accepted()&&
            same_context(editor_publication_->retirement->identity,policy_->accepted()->identity);
        if(profile_==surface_web::Profile::editor_v1&&
            (std::holds_alternative<gui_surface::TextCommit>(event.input)||std::holds_alternative<gui_surface::CompositionEdit>(event.input)||
             std::holds_alternative<gui_surface::SelectionChange>(event.input)||
             (key&&!owned_release&&!body_keys)))
            return {Status::unsupported,{}};
        // Stage physical ownership before Policy consumes the event. A failing
        // allocation or rejected input cannot install half a pointer transition.
        auto pointers=pointers_;auto highest=highest_pointer_;
        auto keys=editor_held_;
        if(profile_==surface_web::Profile::editor_v1&&key){
            if(owned_release)keys.erase(keys.begin()+std::distance(editor_held_.begin(),held));
            else if(key->phase==gui_surface::KeyPhase::down&&!key->repeat){
                if(keys.size()>=64)return {Status::limit_exceeded,{}};
                keys.push_back({event.identity,*key});
            }
        }
        std::optional<gui_surface::Identity> original;
        if(owned_release&&event.identity!=policy_->accepted()->identity){
            original=event.identity;event.identity=policy_->accepted()->identity;
        }
        if(const auto* pointer=std::get_if<gui_surface::PointerTransition>(&event.input)){
            const auto found=pointers.find(pointer->pointer);
            if(pointer->phase==gui_surface::PointerPhase::down){
                if(!pointer->pointer||pointer->pointer<=highest)return {Status::stale_identity,{}};
                if(pointers.size()>=64)return {Status::limit_exceeded,{}};
                pointers.insert(pointer->pointer);highest=pointer->pointer;
            }else if(pointer->phase==gui_surface::PointerPhase::up||pointer->phase==gui_surface::PointerPhase::cancel){
                if(found==pointers.end())return {Status::stale_identity,{}};
                pointers.erase(found);
            }else if(pointer->phase==gui_surface::PointerPhase::move&&pointer->pointer&&found==pointers.end())return {Status::stale_identity,{}};
            else if(pointer->phase==gui_surface::PointerPhase::context&&!pointers.empty())return {Status::busy,{}};
        }else if(const auto* focus=std::get_if<gui_surface::FocusChange>(&event.input)){
            if(!focus->focused||!focus->active){pointers.clear();keys.clear();}
        }
        auto result=policy_->accept(std::move(event));
        if(result.status==Status::ok){
            pointers_=std::move(pointers);highest_pointer_=highest;editor_held_=std::move(keys);
            if(original)result.accepted->event.identity=std::move(*original); // Preserve the real supplied release identity.
        }
        return result;
    }
    void present(::gui::Snapshot next) override {
        require_publication(); Publishing guard(*this);
        try {
            legacy_.present(std::move(next));
            retire_companion();
            cache_pair(pair(nullptr));
        } catch (...) { fail(__LINE__); throw; }
    }
    ::gui::Size measure_text(const ::gui::TextMeasureRequest& request) const override { require_access(); return legacy_.measure_text(request); }
    ::gui::Availability resolved_availability(const ::gui::WidgetKey& key) const override { require_access(); return legacy_.resolved_availability(key); }
    std::optional<::gui::WidgetKey> focused_legacy() const { require_access(); return legacy_.focused(); }
    // Adapter::focused is the existing widget focus, distinct from surface focus.
    std::optional<::gui::WidgetKey> focused() const override { require_access(); return legacy_.focused(); }
    bool focus(std::optional<::gui::WidgetKey> key) override { require_input(); return legacy_.focus(std::move(key)); }
    bool focus_next(bool reverse=false) override { require_input(); return legacy_.focus_next(reverse); }
    void scroll(const ::gui::WidgetKey& key, ::gui::Point point) override { require_input(); legacy_.scroll(key,point); }
    ::gui::Point scroll_offset(const ::gui::WidgetKey& key) const override { require_access(); return legacy_.scroll_offset(key); }
    ::gui::TextSelection text_selection(const ::gui::WidgetKey& key) const override { require_access(); return legacy_.text_selection(key); }
    void text_selection(const ::gui::WidgetKey& key, ::gui::TextSelection value) override { require_input(); legacy_.text_selection(key,value); }
    bool open_popup(const ::gui::WidgetKey& key) override { require_input(); return legacy_.open_popup(key); }
    void close_popup(const ::gui::WidgetKey& key) override { require_input(); legacy_.close_popup(key); }
    void invalidate(const ::gui::WidgetKey& key, ::gui::PixelRect rect) override { require_input(); legacy_.invalidate(key,rect); }
    bool closed() const override { return closed_ || failed_ || legacy_.closed(); }
    void close() override {
        if (failed_ || closed_) {detach_document();return;}
        require_publication(); first_close_line_=__LINE__; closed_=true;
        // Admission closes first; cleanup cannot reopen this owner.
        try{policy_.reset(); connected_=false;deferred_revocation_.reset(); clear_editor();publication_=std::move(terminal_); legacy_.close();}
        catch(...){fail(__LINE__);detach_document();throw;}
        detach_document(); // Detach and join before the owning App can be destroyed.
    }
private:
    friend class BrowserSurfaceSession;
    void detach_document()noexcept{if(document_endpoint_.terminal_binding)document_endpoint_.terminal_binding->detach();document_endpoint_={};}
    using Json = surface_web::Json;
    static Json::Object& object(Json& value) { return std::get<Json::Object>(value.value); }
    static const Json::Object& object(const Json& value) { return std::get<Json::Object>(value.value); }
    struct Publishing { BrowserSurfaceAdapter& owner; explicit Publishing(BrowserSurfaceAdapter& value):owner(value){owner.publishing_=true;} ~Publishing(){owner.publishing_=false;} };
    struct Callback {
        BrowserSurfaceAdapter& owner;unsigned diagnostic_line;int exceptions=std::uncaught_exceptions();
        explicit Callback(BrowserSurfaceAdapter& value,bool notification,unsigned line):owner(value),diagnostic_line(line){
            if(owner.callback_)throw std::logic_error("Reentrant surface callback");
            owner.callback_=true;owner.notifying_=notification;
        }
        ~Callback() noexcept {
            owner.callback_=false;owner.notifying_=false;
            if(std::uncaught_exceptions()>exceptions){owner.fail(__LINE__,diagnostic_line);return;}
            owner.deliver_deferred();
        }
    };
    BrowserEditorEndpoint editor_endpoint_;
    BrowserDocumentEndpoint document_endpoint_;
    gui_surface::Capabilities editor_capabilities_;
    std::optional<gui_surface::Presentation> editor_presentation_;
    std::optional<::foundation::gui_editor::EditorPublication> editor_publication_;
    std::optional<::foundation::gui_editor::EditorPublication> editor_inert_publication_;
    std::optional<gui_surface::Identity> editor_retired_identity_;
    std::optional<::foundation::gui_editor::CompositionFact> editor_composition_;
    ::gui::WebAdapter legacy_;
    std::unique_ptr<gui_surface::Policy> policy_;
    std::uint64_t generation_;
    gui_surface::Features ceiling_;
    surface_web::Profile profile_;
    ::gui::EventSink legacy_sink_;
    Revoked revoked_;
    gui_surface::Capabilities absent_;
    Json publication_,terminal_;
    std::optional<gui_surface::Revocation> deferred_revocation_;
    std::set<std::uint64_t> pointers_;
    struct HeldEditorKey { gui_surface::Identity identity;gui_surface::KeyTransition key; };
    std::vector<HeldEditorKey> editor_held_;
    std::uint64_t highest_pointer_=0;
    bool publishing_=false,callback_=false,notifying_=false,failed_=false,closed_=false,connected_=false,retired_=false,service_=false,legacy_service_=false,owned_service_=false;
    // Diagnostic scalars never participate in admission or lifecycle decisions.
    unsigned first_failure_line_=0,first_failure_flags_=0,first_close_line_=0,first_failure_callback_line_=0;
    void require_access() const { if(failed_||closed_||publishing_)throw std::logic_error("Surface owner is unavailable"); }
    void require_input() const { if(!input_admitted())throw std::logic_error("Surface input is unavailable"); }
    void require_publication() const { if(failed_||closed_||publishing_)throw std::logic_error("Surface publication is unavailable"); }
    void fail(unsigned diagnostic_line,unsigned diagnostic_callback_line=0) noexcept {
        static_assert(std::is_nothrow_move_assignable_v<Json>);
        if(failed_)return;
        first_failure_line_=diagnostic_line;first_failure_callback_line_=diagnostic_callback_line;
        first_failure_flags_=(closed_?1u:0u)|(publishing_?2u:0u)|(callback_?4u:0u)|(notifying_?8u:0u)|
            (connected_?16u:0u)|(service_?32u:0u)|(owned_service_?64u:0u);
        failed_=true;connected_=false; // Never depend on fallible cleanup to close admission.
        if(document_endpoint_.terminal.notify)
            document_endpoint_.terminal.notify(document_endpoint_.terminal.context);
        if(profile_==surface_web::Profile::editor_v1&&editor_endpoint_.terminal.notify)
            editor_endpoint_.terminal.notify(editor_endpoint_.terminal.context);
        clear_editor();
        policy_.reset();pointers_.clear();deferred_revocation_.reset();
        if(!closed_)publication_=std::move(terminal_); // close() already owns the terminal pair.
    }
    bool owner_matches(const gui_surface::Presentation& p) const {
        const ::gui::WidgetKey key{p.identity.owner.id,p.identity.owner.generation};
        if(!::gui::find_widget(legacy_.snapshot(),key))return false;
        const auto a=legacy_.resolved_availability(key);
        const auto equal=[](const auto& x,const auto& y){return x.x==y.x&&x.y==y.y&&x.width==y.width&&x.height==y.height;};
        return p.display_scale==legacy_.snapshot().display_scale && (!p.available || (a.visible&&a.enabled&&equal(p.bounds,a.bounds)&&equal(p.clip,a.clip)));
    }
    static bool same_rect(const gui_surface::Rect& a,const gui_surface::Rect& b) noexcept {
        return a.x==b.x&&a.y==b.y&&a.width==b.width&&a.height==b.height;
    }
    static bool same_context(const gui_surface::Identity& a,const gui_surface::Identity& b) noexcept {
        return a.owner==b.owner&&a.generation==b.generation&&a.epoch==b.epoch&&a.context==b.context;
    }
    static bool same_basis(const std::optional<::foundation::gui_editor::Basis>& a,
                           const std::optional<::foundation::gui_editor::Basis>& b) {
        if(!a||!b)return a.has_value()==b.has_value();
        // A GUI-only repaint may update only presentation_revision. The actual
        // native token, context, editor revision, bytes and ranges stay exact.
        return a->token==b->token&&same_context(a->identity,b->identity)&&a->editor_revision==b->editor_revision&&
            a->surrounding==b->surrounding&&a->selection==b->selection&&a->backward==b->backward&&a->composition==b->composition;
    }
    void check_completion(const ::foundation::gui_editor::EditorCompletion& result) const {
        const auto& receipt=result.result.receipt;
        if(receipt&&receipt->outcome!=::foundation::gui_editor::Outcome::unknown){
            const ::foundation::gui_editor::Settlement tag{receipt->session,receipt->id,receipt->submitted_token,receipt->predecessor};
            if(!editor_publication_||editor_publication_->settlement!=std::optional{tag}||
                !same_basis(editor_publication_->basis,receipt->basis)||editor_publication_->composition!=receipt->composition||
                editor_publication_->retirement!=receipt->retirement)
                throw std::invalid_argument("Editor completion precedes its exact paired publication");
        }
    }
    void clear_editor() noexcept {
        static_assert(std::is_nothrow_move_assignable_v<std::optional<gui_surface::Identity>>);
        editor_held_.clear();
        if(editor_presentation_)editor_retired_identity_=std::move(editor_presentation_->identity);
        editor_presentation_.reset();editor_publication_.reset();editor_inert_publication_.reset();editor_composition_.reset();
    }
    Json pair(const Json* declaration) {
        Json surface;
        if(connected_&&policy_){
            if(profile_==surface_web::Profile::editor_v1){
                const auto composition=editor_composition_&&editor_composition_->state!=::foundation::gui_editor::CompositionState::ended?
                    std::optional{editor_composition_->transaction}:std::nullopt;
                surface=surface_web::json_state(editor_capabilities_,editor_presentation_?&*editor_presentation_:nullptr,
                    policy_->focused(),policy_->active(),composition,policy_->last_sequence(),service_,profile_);
            }else surface=Json::Object{{"version",1},{"capabilities",surface_web::json_capabilities(policy_->capabilities(),profile_)},
                {"presentation",declaration?*declaration:Json{}},{"focused",policy_->focused()},{"active",policy_->active()},
                {"composition",Json{}},{"lastSequence",std::to_string(policy_->last_sequence())},{"serviceActive",service_}};
        }
        Json result=Json::Object{{"snapshot",legacy_.presentation()},{"surface",std::move(surface)}};
        if(profile_==surface_web::Profile::editor_v1)object(result).emplace("editor",editor_publication_?surface_editor_web::json_publication(*editor_publication_):Json{});
        return result;
    }
    static Json terminal_pair(const Json& value) {
        Json result=value;object(object(result).at("snapshot")).at("closed").value=true;
        object(result).at("surface")=Json{};if(object(result).contains("editor"))object(result).at("editor")=Json{};return result;
    }
    void cache_pair(Json value) { auto terminal=terminal_pair(value);publication_=std::move(value);terminal_=std::move(terminal); }
    Json publication(const std::optional<::gui::ServiceRequest>& request) {
        if(failed_||closed_)return publication_;
        if(publishing_)throw std::logic_error("Reentrant surface publication");
        try {
            set_legacy_service(bool(request));
            Publishing guard(*this);
            const auto* current=profile_==surface_web::Profile::editor_v1?
                (editor_presentation_?&*editor_presentation_:nullptr):(policy_?policy_->accepted():nullptr);
            if(current && (legacy_.snapshot().revision!=current->identity.presentation_revision||!owner_matches(*current))){fail(__LINE__);return publication_;}
            auto declaration=current&&profile_!=surface_web::Profile::editor_v1?
                std::optional<Json>{surface_web::json_presentation(*current,profile_)}:std::nullopt;
            cache_pair(pair(declaration?&*declaration:nullptr));return publication_;
        } catch (...) { fail(__LINE__); throw; }
    }
    gui_surface::Status connect(gui_surface::Capabilities offered) {
        using gui_surface::Status;
        if(!input_admitted()||retired_)return Status::closed;
        if(connected_)return Status::duplicate;
        offered.supported &= ceiling_;
        if(!(offered.supported & gui_surface::feature(gui_surface::Feature::mouse_input)))offered.mouse_input_version=0;
        if(!(offered.supported & gui_surface::feature(gui_surface::Feature::focus)))offered.supported &= ~gui_surface::feature(gui_surface::Feature::raw_keys);
        if(profile_==surface_web::Profile::editor_v1){
            offered.supported&=editor_endpoint_.capabilities;
            constexpr auto core=surface_web::editor_supported&~gui_surface::feature(gui_surface::Feature::mouse_input);
            if((offered.supported&core)!=core)return Status::unsupported;
            editor_capabilities_=offered;
            offered.supported&=surface_web::successor_supported;
        }
        auto policy=std::make_unique<gui_surface::Policy>(offered,generation_);
        policy_=std::move(policy);connected_=true;return Status::ok;
    }
    void notify(gui_surface::Revocation value,bool defer=false) {
        if(!value.identity||!revoked_||failed_||closed_)return;
        if(callback_&&defer){
            if(deferred_revocation_){
                const auto& old=*deferred_revocation_;
                if(old.identity==value.identity&&old.reason==value.reason&&old.composition==value.composition&&old.popup==value.popup&&old.held_keys==value.held_keys)return;
                fail(__LINE__);throw std::logic_error("Deferred surface retirement is full");
            }
            deferred_revocation_.emplace(std::move(value));return;
        }
        Callback guard(*this,true,__LINE__);revoked_(std::move(value));
    }
    void deliver_deferred() noexcept {
        if(failed_||closed_||!deferred_revocation_)return;
        auto value=std::move(*deferred_revocation_);deferred_revocation_.reset();
        try{notify(std::move(value));}catch(...){fail(__LINE__);}
    }
    void retire_companion() {
        clear_editor();
        if(!policy_||!policy_->accepted())return;
        try {
            pointers_.clear();
            auto result=policy_->legacy_present(legacy_.snapshot().revision);
            if(result.status!=gui_surface::Status::ok){policy_.reset();connected_=false;retired_=true;return;}
            notify(std::move(result.revoked));
        }catch(...){fail(__LINE__);throw;}
    }
    void legacy_event(const ::gui::Event& event) {
        if(!input_admitted()||owned_service_||!legacy_sink_)return;
        Callback guard(*this,false,__LINE__);legacy_sink_(event);
    }
    void set_service(bool pending) {
        if(service_==pending)return;
        service_=pending; // Suspend before a callback or native service can reenter.
        if(!pending||!policy_||!policy_->accepted())return;
        clear_editor();
        try {
            pointers_.clear();
            if(!(policy_->capabilities().supported&gui_surface::feature(gui_surface::Feature::focus))){
                if(policy_->capabilities().supported&gui_surface::feature(gui_surface::Feature::mouse_input)){
                    auto result=policy_->legacy_present(policy_->accepted()->identity.presentation_revision);
                    if(result.status!=gui_surface::Status::ok){fail(__LINE__);return;}
                    result.revoked.reason=gui_surface::RevocationReason::service;notify(std::move(result.revoked));return;
                }
                gui_surface::Revocation revoke;revoke.identity=policy_->accepted()->identity;revoke.reason=gui_surface::RevocationReason::service;
                notify(std::move(revoke));return;
            }
            if(policy_->last_sequence()==std::numeric_limits<std::uint64_t>::max()){fail(__LINE__);return;}
            auto result=policy_->accept({policy_->accepted()->identity,policy_->last_sequence()+1,gui_surface::FocusChange{false,true,gui_surface::FocusCause::owned_service}});
            if(result.status!=gui_surface::Status::ok){fail(__LINE__);return;}
            notify(std::move(result.accepted->revoked));
        } catch(...) {fail(__LINE__);throw;}
    }
    void set_legacy_service(bool pending) {
        legacy_service_=pending;set_service(legacy_service_||owned_service_);
    }
};

// The supplier patch adds only optional generic dispatcher/publication callbacks.
// This owner supplies their semantics and keeps the raw legacy session private.
class BrowserSurfaceSession {
public:
    using InputSink=std::function<void(gui_surface::AcceptedEvent)>;
    using Connected=std::function<void(gui_surface::Capabilities)>;
    BrowserSurfaceSession(BrowserSurfaceAdapter& adapter,std::string epoch,InputSink input={},Connected connected={},
        ::gui::WebSession::NextService next={},::gui::WebSession::CompleteService complete={},::gui::WebSession::Tick tick={},bool poll_prepared_services=false)
        :adapter_(adapter),input_(std::move(input)),connected_(std::move(connected)),document_enabled_(adapter.document_endpoint_bound()) {
        session_=std::make_unique<::gui::WebSession>(adapter_.legacy_,std::move(epoch),
            [this,next=std::move(next),poll_prepared_services]{if(!adapter_.input_admitted()||(adapter_.owned_service_&&!poll_prepared_services))return std::optional<::gui::ServiceRequest>{};BrowserSurfaceAdapter::Callback guard(adapter_,false,__LINE__);return next?next():std::optional<::gui::ServiceRequest>{};},
            [this,complete=std::move(complete)](::gui::ServiceResult result){if(!adapter_.input_admitted())return false;adapter_.set_legacy_service(true);BrowserSurfaceAdapter::Callback guard(adapter_,false,__LINE__);return complete&&complete(std::move(result));},
            [this,tick=std::move(tick)]{if(!adapter_.input_admitted())return;BrowserSurfaceAdapter::Callback guard(adapter_,false,__LINE__);if(tick)tick();},
            [this](const surface_web::Json& operation){return dispatch(operation);},
            [this](const std::optional<::gui::ServiceRequest>& service){return adapter_.publication(service);},
            [this]{return adapter_.input_admitted();});
    }
    std::string initial() { return run([this]{return session_->initial();}); }
    std::string receive(std::string_view message) { return run([this,message]{
        // Validate the reserved vocabulary even while a modal service suppresses
        // its dispatch. Unknown/malformed surface operations never fall through.
        try { const auto parsed=::gui::web_detail::Parser(message).parse();const auto& op=parsed.at("operation");const auto& type=op.at("type").str();
            if(type=="surfaceInput")(void)surface_web::parse_event(op,adapter_.profile_);
            else if(type=="surfaceConnect")(void)surface_web::parse_connect(op,adapter_.profile_);
            else if(type.starts_with("editor"))validate_editor_operation(op);
            else if(type.starts_with("document"))validate_document_operation(op);
            else if(type.starts_with("surface"))throw std::invalid_argument("Unknown surface operation");
        } catch(...) {adapter_.fail(__LINE__);throw;}
        if(adapter_.profile_!=surface_web::Profile::editor_v1&&!document_enabled_)return session_->receive(message);
        const auto envelope=::gui::web_detail::Parser(message).parse();
        current_sequence_=surface_web::detail::decimal(envelope.at("seq"),true);
        const bool fresh=current_sequence_>observed_sequence_;
        editor_dispatched_=false;
        document_dispatched_=false;
        // Exact original bytes already passed supplier envelope validation.
        // A healthy retry must not re-run service/publication callbacks. Failure
        // before this point wins through run's closed-admission guard.
        if(!fresh&&current_sequence_==observed_sequence_&&message==cached_request_&&!cached_response_.empty()){
            replay_response_=true;return cached_response_;
        }
        auto response=session_->receive(message);
        const auto parsed=surface_editor_web::response_metadata(response);
        observed_sequence_=surface_web::detail::decimal(parsed.at("ack"));
        if(fresh&&observed_sequence_==current_sequence_&&parsed.at("error").str().empty()){
            cache_response_=true;current_request_=std::string(message);
        }
        const auto& operation=envelope.at("operation");
        if(fresh&&observed_sequence_==current_sequence_&&parsed.at("error").str().empty()&&
            operation.at("type").str().starts_with("editor")&&!editor_dispatched_&&!adapter_.failed_)
            (void)dispatch(operation); // Modal services suppress supplier dispatch; these routes only queue/read owned values.
        if(fresh&&observed_sequence_==current_sequence_&&parsed.at("error").str().empty()&&
            operation.at("type").str().starts_with("document")&&!document_dispatched_&&!adapter_.failed_)
            (void)dispatch(operation); // Generic broker intent/Take only; no native entry or public publication ACK.
        return response;
    }); }
    const std::optional<::gui::ServiceRequest>& pending_service() {
        if(!admitted())return none_;
        adapter_.set_legacy_service(bool(session_->pending_service()));return session_->pending_service();
    }
    bool complete_host_service(::gui::ServiceResult result) {
        if(!admitted())return false;
        const auto& request=session_->pending_service();
        if(!request||request->id!=result.id)return false;
        Receiving guard(*this);adapter_.set_legacy_service(true);
        try{const bool done=session_->complete_host_service(std::move(result));adapter_.set_legacy_service(bool(session_->pending_service()));return done;}
        catch(...){adapter_.fail(__LINE__);throw;}
    }
    std::optional<std::uint64_t> editor_submit(::foundation::gui_editor::Packet packet){
        return editor_call([&]{return adapter_.editor_submit(std::move(packet));});
    }
    std::optional<std::uint64_t> editor_submit(const surface_web::Json& packet){
        return editor_call([&]{return adapter_.editor_submit(surface_editor_web::parse_packet(packet));});
    }
    std::optional<std::uint64_t> editor_revoke(::foundation::gui_editor::Revocation record){
        return editor_call([&]{return adapter_.editor_revoke(std::move(record));});
    }
    std::optional<std::uint64_t> editor_revoke(const surface_web::Json& record){
        return editor_call([&]{return adapter_.editor_revoke(surface_editor_web::parse_revocation(record));});
    }
    std::optional<::foundation::gui_editor::EditorCompletion> editor_take(std::uint64_t ticket){
        return editor_call([&]{return adapter_.editor_take(ticket);});
    }
    surface_web::Json editor_take_json(std::uint64_t ticket){
        return editor_call([&]{auto value=adapter_.editor_take(ticket);return value?surface_editor_web::json_completion(*value):surface_web::Json{};});
    }
    surface_web::Json editor_publication_json(){
        return editor_call([&]{const auto* value=adapter_.editor_publication();return value?surface_editor_web::json_publication(*value):surface_web::Json{};});
    }
    void editor_resync(){editor_call([&]{adapter_.editor_resync();});}
    bool failed() const noexcept { return adapter_.failed(); }
private:
    BrowserSurfaceAdapter& adapter_;
    InputSink input_;
    Connected connected_;
    std::unique_ptr<::gui::WebSession> session_;
    std::optional<::gui::ServiceRequest> none_;
    bool receiving_=false;
    std::uint64_t current_sequence_{},observed_sequence_{};
    bool editor_dispatched_{};
    bool document_enabled_{},document_dispatched_{};
    surface_web::Json editor_reply_;
    surface_web::Json document_reply_,document_state_;
    std::optional<::foundation::gui_document::Ticket> validated_document_ticket_;
    std::string validated_document_completion_;
    std::string current_request_,cached_request_,cached_response_;
    bool cache_response_{},replay_response_{};
    std::optional<::foundation::gui_editor::EditorCompletion> fresh_completion_;
    struct Receiving {BrowserSurfaceSession& owner;explicit Receiving(BrowserSurfaceSession& value):owner(value){owner.receiving_=true;}~Receiving(){owner.receiving_=false;}};
    bool admitted() const noexcept {return !receiving_&&adapter_.input_admitted();}
    template<class F>std::string run(F&& operation){
        if(!admitted())throw std::logic_error(std::string("Surface session admission is closed")+
            " [receiving="+std::to_string(receiving_)+",failed="+std::to_string(adapter_.failed_)+
            ",closed="+std::to_string(adapter_.closed_)+",publishing="+std::to_string(adapter_.publishing_)+
            ",callback="+std::to_string(adapter_.callback_)+",notifying="+std::to_string(adapter_.notifying_)+
            ",first_fail="+std::to_string(adapter_.first_failure_line_)+",fail_flags="+std::to_string(adapter_.first_failure_flags_)+
            ",first_close="+std::to_string(adapter_.first_close_line_)+",first_callback="+std::to_string(adapter_.first_failure_callback_line_)+"]");
        Receiving guard(*this);
        fresh_completion_.reset();document_reply_=surface_web::Json{};cache_response_=false;replay_response_=false;
        try{
            auto response=operation();
            if(replay_response_)return response;
            if(adapter_.profile_==surface_web::Profile::editor_v1||document_enabled_){
                auto value=surface_editor_web::response_metadata(response);
                if(fresh_completion_&&!adapter_.failed_){
                    try{adapter_.check_completion(*fresh_completion_);}
                    catch(...){adapter_.fail(__LINE__);BrowserSurfaceAdapter::object(value).at("error")="Editor completion lost its paired publication";}
                }
                BrowserSurfaceAdapter::object(value).at("snapshot")=adapter_.publication_.at("snapshot");
                BrowserSurfaceAdapter::object(value).at("surface")=adapter_.publication_.at("surface");
                if(adapter_.profile_==surface_web::Profile::editor_v1){
                    BrowserSurfaceAdapter::object(value).emplace("editor",adapter_.publication_.at("editor"));
                    BrowserSurfaceAdapter::object(value).emplace("editorReply",adapter_.closed()?surface_web::Json{}:editor_reply_);
                }
                if(document_enabled_){
                    if(!adapter_.closed()){
                        const auto state=adapter_.document_state();
                        if(state.publication_revision>adapter_.legacy_.snapshot().revision)
                            throw std::invalid_argument("Document state precedes its accepted GUI publication");
                        document_state_=document_web::json_state(state);
                    }else{
                        if(std::holds_alternative<std::nullptr_t>(document_state_.value))document_state_=document_web::json_state(::foundation::gui_document::State{});
                        auto& terminal=BrowserSurfaceAdapter::object(document_state_);terminal.at("available")=false;terminal.at("phase")="terminal";
                    }
                    BrowserSurfaceAdapter::object(value).emplace("document",document_state_);
                    BrowserSurfaceAdapter::object(value).emplace("documentReply",adapter_.closed()?surface_web::Json{}:document_reply_);
                }
                if(adapter_.publication_.at("snapshot").at("closed").boolean()){
                    BrowserSurfaceAdapter::object(value).at("service")=surface_web::Json{};
                    BrowserSurfaceAdapter::object(value).at("transfer")=surface_web::Json{};
                }
                response=::gui::web_detail::encode(value);
                if(document_enabled_&&response.size()>document_web::max_response_bytes)
                    throw std::invalid_argument("Combined document GUI response exceeds its byte limit");
            }
            if(cache_response_){cached_request_=std::move(current_request_);cached_response_=response;}
            return response;
        }catch(...){adapter_.fail(__LINE__);throw;}
    }
    template<class F>auto editor_call(F&& operation)->decltype(operation()) {
        if(!admitted()||!adapter_.editor_endpoint_bound())throw std::logic_error("Editor endpoint admission is closed");
        Receiving guard(*this);
        try{return operation();}catch(...){adapter_.fail(__LINE__);throw;}
    }
    void validate_editor_operation(const surface_web::Json& operation) const {
        using namespace surface_web;
        if(adapter_.profile_!=Profile::editor_v1)throw std::invalid_argument("Editor endpoint profile is absent");
        const auto& type=operation.at("type").str();
        if(type=="editorSubmit"){require_shape(operation,{"type","packet"});(void)surface_editor_web::parse_packet(operation.at("packet"));}
        else if(type=="editorRevoke"){require_shape(operation,{"type","record"});(void)surface_editor_web::parse_revocation(operation.at("record"));}
        else if(type=="editorTake"){require_shape(operation,{"type","ticket"});(void)detail::decimal(operation.at("ticket"),true);}
        else if(type=="editorResync")require_shape(operation,{"type"});
        else throw std::invalid_argument("Unknown editor endpoint operation");
    }
    void validate_document_operation(const surface_web::Json& operation) const {
        if(!document_enabled_)throw std::invalid_argument("Document endpoint capability is absent");
        const auto& type=operation.at("type").str();
        if(type=="documentSubmit")(void)document_web::parse_submit(operation);
        else if(type=="documentTake")(void)document_web::parse_take(operation);
        else throw std::invalid_argument("Unknown document endpoint operation");
    }
    bool dispatch(const surface_web::Json& operation) {
        const auto& type=operation.at("type").str();
        if(type.starts_with("document")){
          try{
            namespace D=::foundation::gui_document;
            validate_document_operation(operation);document_dispatched_=true;
            if(type=="documentSubmit"){
                const auto result=adapter_.document_submit(document_web::parse_submit(operation));
                document_reply_=document_web::json_reply(current_sequence_,false,result.admission,result.ticket);
            }else{
                const auto ticket=document_web::parse_take(operation);
                auto completion=adapter_.document_take(ticket);
                if(adapter_.closed())return true; // Genuine unknown closes admission; no synthetic known Take.
                const auto state=adapter_.document_state();
                const auto admission=completion||state.pending==std::optional{ticket}?D::Admission::accepted:
                    state.phase==D::Phase::terminal?D::Admission::closed:D::Admission::stale;
                if(completion&&completion->outcome!=D::Outcome::unknown){
                    const auto publication=document_web::json_state(state),result=document_web::json_completion(*completion);
                    const auto immutable=gui::web_detail::encode(result);
                    if(validated_document_ticket_==std::optional{ticket}){
                        if(immutable!=validated_document_completion_)
                            throw std::invalid_argument("Document completion changed for its validated ticket");
                    }else{
                        if(gui::web_detail::encode(publication.at("observation"))!=gui::web_detail::encode(result.at("observation"))||
                            gui::web_detail::encode(publication.at("draft"))!=gui::web_detail::encode(result.at("draft")))
                            throw std::invalid_argument("Document completion lost its accepted publication");
                        // One previously validated immutable result may be delivered
                        // again with newer State. It never supplies State content.
                        validated_document_ticket_=ticket;validated_document_completion_=immutable;
                    }
                }
                document_reply_=document_web::json_reply(current_sequence_,true,admission,
                    admission==D::Admission::accepted?std::optional{ticket}:std::nullopt,std::move(completion));
            }
            return true;
          }catch(...){adapter_.fail(__LINE__);throw;}
        }
        if(type.starts_with("editor")){
            validate_editor_operation(operation);
            editor_dispatched_=true;
            using surface_web::Json;
            Json reply=Json::Object{{"type",type},{"sequence",std::to_string(current_sequence_)}};
            if(type=="editorSubmit"||type=="editorRevoke"){
                const auto ticket=type=="editorSubmit"?adapter_.editor_submit(surface_editor_web::parse_packet(operation.at("packet"))):
                    adapter_.editor_revoke(surface_editor_web::parse_revocation(operation.at("record")));
                if(ticket&&!*ticket)throw std::invalid_argument("Invalid editor endpoint ticket");
                BrowserSurfaceAdapter::object(reply).emplace("ticket",surface_editor_web::nullable(ticket));
            }else if(type=="editorTake"){
                const auto ticket=surface_web::detail::decimal(operation.at("ticket"),true);
                fresh_completion_=adapter_.editor_take(ticket);
                const auto& completion=fresh_completion_;
                BrowserSurfaceAdapter::object(reply).emplace("ticket",std::to_string(ticket));
                BrowserSurfaceAdapter::object(reply).emplace("completion",completion?surface_editor_web::json_completion(*completion):Json{});
            }else adapter_.editor_resync();
            editor_reply_=std::move(reply);return true;
        }
        if(type=="surfaceConnect"){
            try{
                auto caps=surface_web::parse_connect(operation,adapter_.profile_);
                const auto status=adapter_.connect(std::move(caps));
                if(status!=gui_surface::Status::ok)throw std::invalid_argument(gui_surface::status_name(status));
                if(connected_){BrowserSurfaceAdapter::Callback guard(adapter_,false,__LINE__);connected_(adapter_.capabilities());}
                return true;
            }catch(...){adapter_.fail(__LINE__);throw;}
        }
        if(type=="surfaceInput"){
            gui_surface::Event event;
            try{event=surface_web::parse_event(operation,adapter_.profile_);}catch(...){adapter_.fail(__LINE__);throw;}
            auto result=adapter_.accept(std::move(event));
            if(result.status!=gui_surface::Status::ok)throw std::invalid_argument(gui_surface::status_name(result.status));
            if(input_){BrowserSurfaceAdapter::Callback guard(adapter_,false,__LINE__);input_(std::move(*result.accepted));}
            return true;
        }
        if(type.starts_with("surface")){adapter_.fail(__LINE__);throw std::invalid_argument("Unknown surface operation");}
        if(adapter_.owned_service_)throw std::invalid_argument("A native service owns input");
        // A legacy route cannot retain companion authority accidentally. Ordinary
        // legacy behavior then proceeds through the unchanged supplier dispatcher.
        adapter_.retire_companion();return false;
    }
};
} // namespace foundation::host
