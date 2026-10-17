// SPDX-License-Identifier: CC0-1.0
#include "native_surface.hpp"

namespace foundation::host::native_surface_detail {
inline constexpr gui_surface::Features mouse_features=8225, editor_features=8255;
inline constexpr auto editor_only=gui_surface::feature(gui_surface::Feature::committed_text)|
    gui_surface::feature(gui_surface::Feature::composition)|gui_surface::feature(gui_surface::Feature::surrounding_text)|
    gui_surface::feature(gui_surface::Feature::selection);
inline bool same_context(const gui_surface::Identity& a,const gui_surface::Identity& b) noexcept {
    return a.owner==b.owner && a.generation==b.generation && a.epoch==b.epoch && a.context==b.context;
}
inline bool valid_identity(const gui_surface::Identity& v) noexcept {
    return !v.owner.id.empty() && v.owner.id.size()<=128 && gui_surface::valid_text(v.owner.id) &&
        v.owner.generation && v.generation && v.epoch && v.context && v.presentation_revision;
}
inline bool same_basis(const gui_editor::Basis& a,const gui_editor::Basis& b) noexcept {
    return a.token==b.token && same_context(a.identity,b.identity) && a.editor_revision==b.editor_revision &&
        a.surrounding==b.surrounding && a.selection==b.selection && a.backward==b.backward && a.composition==b.composition;
}
inline bool valid_basis(const gui_editor::Basis& v) noexcept {
    return v.token && v.editor_revision && valid_identity(v.identity) && v.surrounding.size()<=65536 &&
        gui_surface::valid_text(v.surrounding) && gui_surface::valid_range(v.surrounding,v.selection);
}
inline bool valid_publication(const gui_editor::EditorPublication& p) noexcept {
    namespace E=gui_editor;
    if (p.basis && (!valid_basis(*p.basis) || p.retirement)) return false;
    if (p.settlement && (!p.settlement->session || !p.settlement->id || !p.settlement->submitted_token ||
        (p.settlement->predecessor && !*p.settlement->predecessor))) return false;
    if (p.composition) {
        const auto& c=*p.composition;
        if (!c.transaction || (c.state!=E::CompositionState::pending && c.state!=E::CompositionState::live && c.state!=E::CompositionState::ended)) return false;
        if (!p.basis && (c.state!=E::CompositionState::ended || !p.retirement)) return false;
        if (p.basis && (c.state==E::CompositionState::live ? p.basis->composition!=c.transaction : p.basis->composition!=0)) return false;
    } else if (p.basis && p.basis->composition) return false;
    if (p.retirement) {
        const auto& r=*p.retirement;
        if (!valid_identity(r.identity) || !r.readback_attested || !r.observation_revision ||
            (r.availability!=E::NativeAvailability::noneditable && r.availability!=E::NativeAvailability::unavailable &&
             !(r.availability==E::NativeAvailability::available && r.authority_retired))) return false;
    }
    return true; // An explicitly pending empty record carries no authority.
}
struct Flag { bool& value; explicit Flag(bool& v):value(v){value=true;} ~Flag(){value=false;} };
}

namespace foundation::host {
struct NativeSurfaceAdapter::Impl {
    struct Lifetime {
        const std::thread::id thread{std::this_thread::get_id()};
        NativeSurfaceAdapter* adapter{};
        bool alive{true};
        NativeSurfaceAdapter* get() const noexcept {
            return std::this_thread::get_id()==thread && alive ? adapter : nullptr;
        }
    };
    gui::Adapter& concrete;
    NativeSurfacePeer peer;
    const NativeSurfaceMode mode;
    const std::uint64_t generation;
    const std::thread::id thread{std::this_thread::get_id()};
    std::shared_ptr<Lifetime> lifetime{std::make_shared<Lifetime>()};
    std::unique_ptr<gui_surface::Policy> policy;
    std::unique_ptr<NativeEditorCapture> capture;
    NativeEditorEndpoint endpoint;
    gui_surface::Capabilities absent;
    gui::EventSink legacy;
    InputSink sink;
    Connected connected;
    Revoked revoked;
    gui::Snapshot snapshot;
    std::optional<gui_surface::Presentation> pair;
    std::optional<gui_editor::EditorPublication> publication,inert;
    std::optional<gui_editor::CompositionFact> composition;
    std::optional<gui_surface::Identity> retired_identity;
    bool armed{}, disarmed{}, stopped{}, failed{}, publishing{}, callback{}, notifying{}, service{}, activation_due{};
    Impl(gui::Adapter& value,std::uint64_t epoch,NativeSurfacePeer supplied,NativeSurfaceMode selected,NativeEditorEndpoint editor,
            gui::EventSink events,Revoked revocation)
        : concrete(value),peer(std::move(supplied)),mode(selected),generation(epoch),endpoint(std::move(editor)),legacy(std::move(events)),revoked(std::move(revocation)) {
        const auto expected=mode==NativeSurfaceMode::none ? 0 : mode==NativeSurfaceMode::mouse_v1 ?
            native_surface_detail::mouse_features : mode==NativeSurfaceMode::editor_v1 ? native_surface_detail::editor_features : UINT64_MAX;
        if (!generation || !peer.ready || !peer.present || !peer.ready() ||
            gui_surface::validate_capabilities(peer.capabilities)!=gui_surface::Status::ok || peer.capabilities.supported!=expected ||
            (expected && (!peer.suspend || peer.capabilities.mouse_input_version!=1)) ||
            (mode==NativeSurfaceMode::editor_v1 && (!peer.editor || !endpoint.bound())) ||
            (mode!=NativeSurfaceMode::editor_v1 && endpoint.bound()))
            throw std::invalid_argument("Native surface needs its actual complete peer capabilities and ready renderer");
        auto physical=peer.capabilities;
        if (mode==NativeSurfaceMode::editor_v1) physical.supported&=~native_surface_detail::editor_only;
        policy=std::make_unique<gui_surface::Policy>(physical,generation);
        if (mode==NativeSurfaceMode::editor_v1) capture=std::make_unique<NativeEditorCapture>(endpoint);
    }
    void owner() const { if (std::this_thread::get_id()!=thread) throw std::logic_error("Native surface requires its serialized owner"); }
    bool base_ingress() const noexcept { return armed && !disarmed && !stopped && !failed && !publishing && !callback && !notifying; }
    NativeEditorAdmission editor_admission() const noexcept {
        if (!capture || service || failed || stopped || disarmed || capture->state()!=gui_editor::State::ready || !capture->basis())
            return NativeEditorAdmission::withdrawn;
        if (capture->paused() || !pair || !pair->available || !pair->editor || !publication || !publication->basis)
            return NativeEditorAdmission::paused;
        return NativeEditorAdmission::active;
    }
    bool admitted() const noexcept { return mode!=NativeSurfaceMode::none && base_ingress() && !service && editor_admission()!=NativeEditorAdmission::paused; }
    void expire() noexcept { armed=false; disarmed=true; lifetime->alive=false; lifetime->adapter=nullptr; }
    void fail() noexcept {
        if (failed) return;
        failed=true; armed=false; lifetime->alive=false;
        if (policy) (void)policy->close();
        pair.reset(); publication.reset(); composition.reset();
        if (capture) capture->close();
        if (endpoint.terminal.notify) endpoint.terminal.notify(endpoint.terminal.context);
        try { if (peer.suspend) peer.suspend(); } catch (...) {}
    }
    bool owner_matches(const gui::Snapshot& value,const gui_surface::Presentation& p) const {
        const gui::WidgetKey key{p.identity.owner.id,p.identity.owner.generation};
        if (!gui::find_widget(value,key) || p.display_scale!=value.display_scale) return false;
        const auto a=concrete.resolved_availability(key);
        const auto equal=[](const auto& x,const auto& y){return x.x==y.x&&x.y==y.y&&x.width==y.width&&x.height==y.height;};
        return !p.available || (a.visible && a.enabled && equal(a.bounds,p.bounds) && equal(a.clip,p.clip));
    }
    void render(gui::Snapshot value) {
        const auto expected=value.revision;
        if (!expected || !peer.ready()) throw std::invalid_argument("Native renderer is not ready");
        const auto receipt=peer.present(std::move(value));
        if (receipt.snapshot_revision!=expected || concrete.closed()) throw std::runtime_error("Native renderer did not acknowledge the exact installed revision");
    }
    NativeEditorPresentation editor_view() const {
        NativeEditorPresentation result;
        result.publication=publication; result.surface=pair; result.composition=composition;
        if (pair) result.context=pair->editor;
        if (capture) {
            result.admission=editor_admission();
            if (result.admission!=NativeEditorAdmission::withdrawn) {
                if (const auto* value=capture->draft()) result.draft=*value;
                result.passage_basis=*capture->basis();
                if (const auto* value=capture->composition()) result.passage_composition=*value;
                result.preserve_passage=result.admission==NativeEditorAdmission::paused || capture->pending()!=0 ||
                    (publication && publication->basis && publication->basis->composition);
            } else result.context.reset();
        }
        return result;
    }
    void capture_gate() {
        if (capture && (!pair || !pair->available || !pair->editor || !publication || !publication->basis || service))
            capture->pause_pending();
    }
    void notify(gui_surface::Revocation value) {
        if (!armed || !revoked || (!value.identity && value.empty())) return;
        native_surface_detail::Flag notifying_guard(notifying);
        native_surface_detail::Flag callback_guard(callback);
        try { revoked(std::move(value)); } catch (...) { fail(); throw; }
    }
    gui_surface::CommitResult publish(gui::Snapshot value,const gui_surface::Presentation& supplied,
            std::optional<gui_editor::EditorPublication> editor,std::optional<gui_editor::CompositionFact> fact) {
        using S=gui_surface::Status;
        owner();
        if (failed || stopped || disarmed) return {S::closed,{}};
        if (publishing || callback || notifying) return {S::busy,{}};
        if (mode==NativeSurfaceMode::none) return {S::unsupported,{}};
        if (value.revision!=supplied.identity.presentation_revision) return {S::stale_revision,{}};
        if (service && supplied.available) return {S::unavailable,{}};
        gui::validate_snapshot(value);
        auto retained=std::optional{supplied};
        auto next_inert=editor ? std::optional<gui_editor::EditorPublication>{} : (publication ? publication : inert);
        auto physical=supplied;
        if (mode==NativeSurfaceMode::editor_v1) {
            namespace E=gui_editor;
            // Native editor composition is not physical Policy composition.
            // Validate its full declaration independently, then prepare only
            // the physical companion in the live Policy.
            auto validation=supplied;
            if (validation.editor) validation.editor->composition_transaction=0;
            gui_surface::Policy check(peer.capabilities,generation);
            const auto checked=check.prepare(validation);
            if (checked.status!=S::ok) return {checked.status,{}};
            if (supplied.editor && supplied.editor->editable && supplied.available && (!editor || !editor->basis)) return {S::unsupported,{}};
            if (editor) {
                if (!native_surface_detail::valid_publication(*editor) || editor->composition!=fact) return {S::invalid_value,{}};
                if (editor->basis) {
                    const auto& b=*editor->basis;
                    if (!supplied.editor || !native_surface_detail::same_context(b.identity,supplied.identity) ||
                        b.editor_revision!=supplied.editor->revision || b.surrounding!=supplied.editor->surrounding ||
                        b.selection!=supplied.editor->selection || b.backward!=supplied.editor->selection_backward ||
                        b.composition!=supplied.editor->composition_transaction) return {S::stale_identity,{}};
                    const auto& prior=inert ? inert : publication;
                    if (prior && prior->basis && prior->basis->token==b.token &&
                        (!native_surface_detail::same_basis(*prior->basis,b) || (prior->composition!=editor->composition &&
                         (!editor->settlement || prior->settlement==editor->settlement)))) return {S::stale_identity,{}};
                }
                if (editor->retirement) {
                    const auto& r=*editor->retirement;
                    if (r.identity.owner!=supplied.identity.owner || r.identity.generation!=supplied.identity.generation ||
                        r.identity.epoch!=supplied.identity.epoch || supplied.editor ||
                        (r.availability==E::NativeAvailability::unavailable && supplied.available)) return {S::stale_identity,{}};
                }
            }
            if (fact && (!editor || !editor->composition)) return {S::invalid_value,{}};
            physical.editor.reset(); physical.required&=~native_surface_detail::editor_only;
        } else if (editor || fact || supplied.editor) return {S::unsupported,{}};
        auto preparation=policy->prepare(physical);
        if (preparation.status!=S::ok) return {preparation.status,{}};
        // Complete owned copies and fallback metadata before the first peer
        // call. A peer may synchronously attempt input; publication gates it.
        auto committed_snapshot=value;
        native_surface_detail::Flag guard(publishing);
        try {
            render(std::move(value));
            if (!owner_matches(committed_snapshot,supplied)) { fail(); return {S::stale_revision,{}}; }
            auto result=policy->commit(std::move(preparation.prepared),committed_snapshot.revision);
            if (result.status!=S::ok) { fail(); return result; }
            snapshot=std::move(committed_snapshot); pair=std::move(retained); publication=std::move(editor);
            composition=std::move(fact); inert=std::move(next_inert); retired_identity=supplied.identity;
            if (capture) {
                if (publication) {
                    if (!capture->install(*publication,supplied.identity)) { fail(); return {S::stale_identity,{}}; }
                } else capture->pause_pending();
                capture_gate();
            }
            // Optional for mouse peers: carries exact accepted context so
            // activation can distinguish a repaint from a new input context.
            if (peer.editor) peer.editor(editor_view());
            if (failed || stopped || disarmed || concrete.closed()) { fail(); return {S::closed,{}}; }
            activation_due=true;
            return result;
        } catch (...) { fail(); throw; }
    }
};

NativeSurfaceAdapter::NativeSurfaceAdapter(gui::Adapter& concrete,std::uint64_t generation,
        NativeSurfacePeer peer,NativeSurfaceMode mode,NativeEditorEndpoint endpoint,gui::EventSink legacy,Revoked revoked)
    : impl_(std::make_unique<Impl>(concrete,generation,std::move(peer),mode,std::move(endpoint),std::move(legacy),std::move(revoked))) {
    impl_->lifetime->adapter=this;
}
NativeSurfaceAdapter::~NativeSurfaceAdapter() { disarm(); try { close(); } catch (...) {} }
void NativeSurfaceAdapter::arm(InputSink sink,Connected connected,Revoked revoked) {
    impl_->owner();
    if (impl_->disarmed || impl_->failed || impl_->stopped || impl_->armed || impl_->publishing || impl_->callback)
        throw std::logic_error("Native surface cannot arm this lifetime");
    if (impl_->mode!=NativeSurfaceMode::none && (!sink || !connected)) throw std::invalid_argument("Native surface needs complete input callbacks");
    impl_->sink=std::move(sink); impl_->connected=std::move(connected);
    if (revoked) impl_->revoked=std::move(revoked);
    impl_->armed=true;
    if (impl_->connected) {
        native_surface_detail::Flag guard(impl_->callback);
        try { impl_->connected(impl_->peer.capabilities); } catch (...) { impl_->fail(); throw; }
    }
    if (impl_->failed || impl_->stopped || impl_->disarmed) throw std::logic_error("Native surface closed while arming");
    if (impl_->peer.activate) {
        try { impl_->peer.activate(); } catch (...) { impl_->fail(); throw; }
    }
}
void NativeSurfaceAdapter::disarm() noexcept { if (impl_) impl_->expire(); }
bool NativeSurfaceAdapter::failed() const noexcept { return impl_->failed; }
bool NativeSurfaceAdapter::input_admitted() const noexcept { return impl_->admitted(); }
bool NativeSurfaceAdapter::editor_endpoint_bound() const noexcept { return impl_->capture!=nullptr; }
const gui_surface::Capabilities& NativeSurfaceAdapter::capabilities() const noexcept { return impl_->failed || impl_->stopped || impl_->disarmed ? impl_->absent : impl_->peer.capabilities; }
std::uint64_t NativeSurfaceAdapter::generation() const noexcept { return impl_->generation; }
const gui_surface::Presentation* NativeSurfaceAdapter::accepted() const noexcept { return !impl_->publishing && !impl_->failed && !impl_->stopped && impl_->pair ? &*impl_->pair : nullptr; }
const gui_editor::EditorPublication* NativeSurfaceAdapter::editor_publication() const noexcept { return !impl_->publishing && !impl_->failed && !impl_->stopped && impl_->publication ? &*impl_->publication : nullptr; }
const gui::Snapshot& NativeSurfaceAdapter::snapshot() const noexcept { return impl_->snapshot; }
NativeEditorCapture* NativeSurfaceAdapter::editor_capture() noexcept { return impl_->capture.get(); }
gui_surface::CommitResult NativeSurfaceAdapter::present_pair(gui::Snapshot value,const gui_surface::Presentation& pair) {
    if (impl_->mode==NativeSurfaceMode::editor_v1) return {gui_surface::Status::unsupported,{}};
    return impl_->publish(std::move(value),pair,{},{});
}
gui_surface::CommitResult NativeSurfaceAdapter::present_editor_pair(gui::Snapshot value,const gui_surface::Presentation& pair,
        std::optional<gui_editor::EditorPublication> publication,std::optional<gui_editor::CompositionFact> composition) {
    if (impl_->mode!=NativeSurfaceMode::editor_v1) return {gui_surface::Status::unsupported,{}};
    return impl_->publish(std::move(value),pair,std::move(publication),std::move(composition));
}
gui_surface::CommitResult NativeSurfaceAdapter::present_editor_retirement(gui::Snapshot value,gui_editor::EditorPublication publication) {
    using S=gui_surface::Status; impl_->owner();
    if (!impl_->capture) return {S::unsupported,{}};
    if (impl_->failed || impl_->stopped || impl_->disarmed) return {S::closed,{}};
    if (impl_->publishing || impl_->callback || impl_->notifying) return {S::busy,{}};
    if (publication.basis || !publication.retirement || !native_surface_detail::valid_publication(publication)) return {S::invalid_value,{}};
    const auto& proof=publication.retirement->identity;
    if (proof.generation!=impl_->generation || (impl_->retired_identity && (proof.owner!=impl_->retired_identity->owner ||
        proof.generation!=impl_->retired_identity->generation || proof.epoch!=impl_->retired_identity->epoch))) return {S::stale_identity,{}};
    gui::validate_snapshot(value); auto retained=value;
    native_surface_detail::Flag guard(impl_->publishing);
    try {
        impl_->render(std::move(value));
        auto result=impl_->policy->legacy_present(retained.revision);
        if (result.status!=S::ok) { impl_->fail(); return result; }
        impl_->snapshot=std::move(retained); impl_->pair.reset(); impl_->publication=std::move(publication); impl_->composition=impl_->publication->composition;
        if (!impl_->capture->install(*impl_->publication,{})) { impl_->fail(); return {S::stale_identity,{}}; }
        impl_->peer.editor(impl_->editor_view());
        if (impl_->failed || impl_->stopped || impl_->disarmed || impl_->concrete.closed()) { impl_->fail(); return {S::closed,{}}; }
        return result;
    } catch (...) { impl_->fail(); throw; }
}
void NativeSurfaceAdapter::present(gui::Snapshot value) {
    impl_->owner(); if (impl_->failed || impl_->stopped || impl_->disarmed) throw std::logic_error("Native surface is closed");
    if (impl_->publishing || impl_->callback || impl_->notifying) throw std::logic_error("Reentrant native publication");
    gui::validate_snapshot(value); auto retained=value;
    native_surface_detail::Flag guard(impl_->publishing);
    try {
        impl_->render(std::move(value));
        auto result=impl_->policy->legacy_present(retained.revision);
        if (result.status!=gui_surface::Status::ok) { impl_->fail(); throw std::invalid_argument("Stale native legacy publication"); }
        impl_->snapshot=std::move(retained); impl_->pair.reset();
        if (impl_->publication) impl_->inert=impl_->publication;
        impl_->publication.reset(); impl_->composition.reset();
        if (impl_->capture) impl_->capture->pause_pending();
        if (impl_->peer.editor) impl_->peer.editor(impl_->editor_view());
        if (impl_->failed || impl_->stopped || impl_->disarmed || impl_->concrete.closed()) {
            impl_->fail(); throw std::logic_error("Native surface closed during publication");
        }
    } catch (...) { impl_->fail(); throw; }
}
void NativeSurfaceAdapter::invalidate(gui_surface::RevocationReason reason) {
    impl_->owner(); if (impl_->failed || impl_->stopped || impl_->disarmed) return;
    if (impl_->publishing || impl_->callback || impl_->notifying) { impl_->fail(); return; }
    gui_surface::Revocation revoked;
    if (impl_->snapshot.revision) {
        auto result=impl_->policy->legacy_present(impl_->snapshot.revision);
        if (result.status!=gui_surface::Status::ok) { impl_->fail(); return; }
        revoked=std::move(result.revoked); revoked.reason=reason;
    }
    if (impl_->pair) impl_->retired_identity=impl_->pair->identity;
    impl_->pair.reset();
    if (impl_->publication) impl_->inert=impl_->publication;
    impl_->publication.reset(); impl_->composition.reset();
    try {
        if (impl_->capture) impl_->capture->retire("Native frontend context invalidated");
        if (impl_->peer.suspend) impl_->peer.suspend();
        impl_->notify(std::move(revoked));
    } catch (...) { impl_->fail(); throw; }
}
void NativeSurfaceAdapter::set_owned_service_active(bool value) {
    impl_->owner(); if (impl_->failed || impl_->stopped || impl_->disarmed) throw std::logic_error("Native surface service endpoint is closed");
    if (impl_->service==value) return;
    if (impl_->publishing || impl_->callback || impl_->notifying) throw std::logic_error("Native service suspension needs a normal owner turn");
    impl_->service=value;
    if (!value) return; // Ending a service never reconstructs old authority.
    invalidate(gui_surface::RevocationReason::service);
    if (!impl_->snapshot.revision || impl_->failed) return;
    auto safe=impl_->snapshot;
    safe.title.clear(); safe.modal_root.reset(); safe.key_bindings.clear();
    for (auto& widget:safe.widgets) {
        const auto bounds=widget.state.bounds; const auto extent=widget.state.content_size;
        widget.state={}; widget.state.bounds=bounds; widget.state.content_size=extent;
        widget.state.visible=false; widget.state.enabled=false;
    }
    for (auto& command:safe.commands) command.enabled=false;
    for (auto& page:safe.pages) { page.label.clear(); page.enabled=false; page.visible=false; }
    // This same-revision frontend redaction is never an App effect receipt.
    // The App must still publish its fresh safe origin before releasing work.
    present(std::move(safe));
}
gui_surface::AcceptResult NativeSurfaceAdapter::input(gui_surface::Event event) {
    using S=gui_surface::Status; impl_->owner();
    const auto* focus=std::get_if<gui_surface::FocusChange>(&event.input);
    const auto* release=std::get_if<gui_surface::KeyTransition>(&event.input);
    // A real loss and an already-owned body key UP may retire ownership during
    // an inert edit pause. Policy still checks their exact identity/ownership.
    const bool cleanup=impl_->base_ingress() && !impl_->service && impl_->editor_admission()==NativeEditorAdmission::paused &&
        ((focus && (!focus->focused || !focus->active)) || (release && release->phase==gui_surface::KeyPhase::up));
    if ((!impl_->admitted() && !cleanup) || !impl_->pair) return {impl_->failed || impl_->stopped || impl_->disarmed ? S::closed : S::busy,{}};
    if (!std::holds_alternative<gui_surface::KeyTransition>(event.input) &&
        !std::holds_alternative<gui_surface::MouseTransition>(event.input) &&
        !std::holds_alternative<gui_surface::FocusChange>(event.input)) return {S::unsupported,{}};
    if (const auto* key=std::get_if<gui_surface::KeyTransition>(&event.input); key &&
        (key->key.size()>128 || key->code.size()>128)) return {S::limit_exceeded,{}};
    if (impl_->mode==NativeSurfaceMode::editor_v1) {
        if (std::holds_alternative<gui_surface::TextCommit>(event.input) || std::holds_alternative<gui_surface::CompositionEdit>(event.input) ||
            std::holds_alternative<gui_surface::SelectionChange>(event.input)) return {S::unsupported,{}};
        if (const auto* key=std::get_if<gui_surface::KeyTransition>(&event.input); key && key->phase==gui_surface::KeyPhase::down &&
            (!impl_->publication || impl_->publication->basis || !impl_->publication->retirement || impl_->publication->retirement->authority_retired ||
             impl_->publication->retirement->availability!=gui_editor::NativeAvailability::noneditable)) return {S::unavailable,{}};
    }
    try {
        // Copy into fresh bounded storage before retaining a caller's spare
        // string capacities. Event length limits alone do not bound capacity.
        auto compact=event;
        auto result=impl_->policy->accept(std::move(compact));
        if (!result.accepted) return result;
        if (result.accepted->revoked.identity && impl_->capture) impl_->capture->retire("Native focus or capture revoked");
        if (impl_->sink) {
            auto owned=*result.accepted;
            native_surface_detail::Flag guard(impl_->callback);
            impl_->sink(std::move(owned));
        }
        return result;
    } catch (...) { impl_->fail(); throw; }
}
gui_surface::AcceptResult NativeSurfaceAdapter::dispatch_input(gui_surface::Input input) {
    impl_->owner();
    if (!impl_->base_ingress() || impl_->service || !impl_->pair) return {gui_surface::Status::unavailable,{}};
    if (impl_->policy->last_sequence()==UINT64_MAX) { impl_->fail(); return {gui_surface::Status::limit_exceeded,{}}; }
    return this->input({impl_->pair->identity,impl_->policy->last_sequence()+1,std::move(input)});
}
std::optional<std::uint64_t> NativeSurfaceAdapter::observe_editor(NativeEditorObservation observation) {
    impl_->owner();
    if (!impl_->base_ingress() || impl_->service || !impl_->capture) return {};
    // The actual focus/lifecycle peer must invalidate immediately on real loss,
    // including while paused. A purely inert GUI gate is not focus loss.
    if (impl_->editor_admission()==NativeEditorAdmission::paused) return impl_->capture->observe_paused(std::move(observation));
    if (!impl_->admitted() || !impl_->pair || !impl_->pair->available || !impl_->publication ||
        !impl_->publication->basis || !impl_->policy->focused()) return {};
    return impl_->capture->observe(std::move(observation));
}
void NativeSurfaceAdapter::legacy_event(gui::Event event) {
    impl_->owner();
    if (!impl_->base_ingress() || !impl_->legacy || (impl_->service && !std::holds_alternative<gui::CloseEvent>(event))) return;
    native_surface_detail::Flag guard(impl_->callback);
    try { impl_->legacy(event); } catch (...) { impl_->fail(); throw; }
}
void NativeSurfaceAdapter::tick() {
    impl_->owner(); if (impl_->failed || impl_->stopped || impl_->disarmed || impl_->publishing || impl_->callback || impl_->notifying) return;
    if (impl_->capture) {
        try {
            impl_->capture_gate();
            impl_->capture->tick();
            impl_->capture_gate();
            if (impl_->capture->state()==gui_editor::State::terminal_unknown) { impl_->fail(); return; }
            native_surface_detail::Flag guard(impl_->publishing);
            impl_->peer.editor(impl_->editor_view());
        } catch (...) { impl_->fail(); throw; }
    }
    if (impl_->failed || impl_->stopped || impl_->disarmed) return;
    if (impl_->activation_due && impl_->armed && !impl_->service && impl_->peer.activate) {
        impl_->activation_due=false;
        try { impl_->peer.activate(); } catch (...) { impl_->fail(); throw; }
    }
}
NativeSurfacePublisher NativeSurfaceAdapter::publisher() {
    impl_->owner();
    const std::weak_ptr<Impl::Lifetime> weak=impl_->lifetime;
    NativeSurfacePublisher result; result.capabilities=impl_->peer.capabilities; result.generation=impl_->generation;
    result.present_pair=[weak](gui::Snapshot value,const gui_surface::Presentation& pair) {
        if (const auto state=weak.lock(); state) if (auto* adapter=state->get()) return adapter->present_pair(std::move(value),pair);
        return gui_surface::CommitResult{gui_surface::Status::closed,{}};
    };
    result.present_editor_pair=[weak](gui::Snapshot value,const gui_surface::Presentation& pair,std::optional<gui_editor::EditorPublication> publication,std::optional<gui_editor::CompositionFact> fact) {
        if (const auto state=weak.lock(); state) if (auto* adapter=state->get()) return adapter->present_editor_pair(std::move(value),pair,std::move(publication),std::move(fact));
        return gui_surface::CommitResult{gui_surface::Status::closed,{}};
    };
    result.present_editor_retirement=[weak](gui::Snapshot value,gui_editor::EditorPublication publication) {
        if (const auto state=weak.lock(); state) if (auto* adapter=state->get()) return adapter->present_editor_retirement(std::move(value),std::move(publication));
        return gui_surface::CommitResult{gui_surface::Status::closed,{}};
    };
    result.set_owned_service_active=[weak](bool value) {
        if (const auto state=weak.lock(); state) if (auto* adapter=state->get()) { adapter->set_owned_service_active(value); return true; }
        return false;
    };
    return result;
}
gui::Size NativeSurfaceAdapter::measure_text(const gui::TextMeasureRequest& v) const { impl_->owner(); return impl_->concrete.measure_text(v); }
gui::Availability NativeSurfaceAdapter::resolved_availability(const gui::WidgetKey& v) const { impl_->owner(); return impl_->concrete.resolved_availability(v); }
std::optional<gui::WidgetKey> NativeSurfaceAdapter::focused() const { impl_->owner(); return impl_->concrete.focused(); }
bool NativeSurfaceAdapter::focus(std::optional<gui::WidgetKey> v) { impl_->owner(); return impl_->concrete.focus(std::move(v)); }
bool NativeSurfaceAdapter::focus_next(bool v) { impl_->owner(); return impl_->concrete.focus_next(v); }
void NativeSurfaceAdapter::scroll(const gui::WidgetKey& v,gui::Point p) { impl_->owner(); impl_->concrete.scroll(v,p); }
gui::Point NativeSurfaceAdapter::scroll_offset(const gui::WidgetKey& v) const { impl_->owner(); return impl_->concrete.scroll_offset(v); }
gui::TextSelection NativeSurfaceAdapter::text_selection(const gui::WidgetKey& v) const { impl_->owner(); return impl_->concrete.text_selection(v); }
void NativeSurfaceAdapter::text_selection(const gui::WidgetKey& v,gui::TextSelection p) { impl_->owner(); impl_->concrete.text_selection(v,p); }
bool NativeSurfaceAdapter::open_popup(const gui::WidgetKey& v) { impl_->owner(); return impl_->concrete.open_popup(v); }
void NativeSurfaceAdapter::close_popup(const gui::WidgetKey& v) { impl_->owner(); impl_->concrete.close_popup(v); }
void NativeSurfaceAdapter::invalidate(const gui::WidgetKey& v,gui::PixelRect p) { impl_->owner(); impl_->concrete.invalidate(v,p); }
bool NativeSurfaceAdapter::closed() const { impl_->owner(); return impl_->stopped || impl_->failed || impl_->concrete.closed(); }
void NativeSurfaceAdapter::close() {
    impl_->owner(); if (impl_->stopped) return;
    impl_->expire(); impl_->stopped=true; (void)impl_->policy->close();
    if (impl_->capture) impl_->capture->close();
    impl_->pair.reset(); impl_->publication.reset(); impl_->composition.reset();
    std::exception_ptr error;
    try { if (impl_->peer.suspend) impl_->peer.suspend(); } catch (...) { error=std::current_exception(); }
    try { if (impl_->peer.close) impl_->peer.close(); } catch (...) { if (!error) error=std::current_exception(); }
    try { impl_->concrete.close(); } catch (...) { if (!error) error=std::current_exception(); }
    if (error) std::rethrow_exception(error);
}
} // namespace foundation::host
