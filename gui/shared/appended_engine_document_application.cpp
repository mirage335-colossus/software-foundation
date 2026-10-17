#include "appended_engine_document_application.hpp"
#include "appended_document_v2_codec.hpp"
#include "document_action_v1_codec.hpp"
#include "appended_engine_owner.hpp"
#include "engine_document_broker.hpp"

#include <limits>
#include <stdexcept>
#include <thread>
#include <utility>

namespace foundation::ui {
namespace {
namespace A = appended;
struct Guard { bool& value; explicit Guard(bool& flag) : value(flag) { value=true; } ~Guard() { value=false; } };
A::EngineDocumentTarget target(A::EngineIdentity value) {
    return {value.worker_epoch,value.application_instance,value.document_sequence,value.service_generation};
}
bool ready(A::EngineDocumentTarget value) {
    return value.worker_epoch && value.application_instance && value.document_sequence && value.service_generation;
}
bool same_effect(const A::EngineNativeEffect& a,const A::EngineNativeEffect& b) {
    return a.ticket==b.ticket && a.target==b.target;
}
gui::Snapshot redacted(gui::Snapshot value) {
    value.title="Appended document suspended";
    for (auto& widget:value.widgets) {
        const auto bounds=widget.state.bounds;
        const auto extent=widget.state.content_size;
        const auto clip=widget.state.content_clip;
        widget.state={}; widget.state.bounds=bounds; widget.state.content_size=extent;
        widget.state.content_clip=clip; widget.state.visible=false; widget.state.enabled=false;
    }
    for (auto& page:value.pages) { page.label.clear(); page.enabled=false; page.visible=false; }
    for (auto& command:value.commands) command.enabled=false;
    value.active_page.reset(); value.modal_root.reset(); value.key_bindings.clear();
    return value;
}
} // namespace

struct AppendedEngineDocumentApplication::Impl {
    struct Proxy final : gui::Adapter {
        Impl& app;
        explicit Proxy(Impl& owner) : app(owner) {}
        void present(gui::Snapshot value) override { app.present(std::move(value)); }
        gui::Size measure_text(const gui::TextMeasureRequest& value) const override {
            app.watch();
            if (!app.masked() || value.text=="M") return app.actual.measure_text(value);
            auto safe=value; safe.text.clear(); return app.actual.measure_text(safe);
        }
        gui::Availability resolved_availability(const gui::WidgetKey& k) const override { return app.actual.resolved_availability(k); }
        std::optional<gui::WidgetKey> focused() const override { return app.actual.focused(); }
        bool focus(std::optional<gui::WidgetKey> k) override { return app.actual.focus(std::move(k)); }
        bool focus_next(bool reverse) override { return app.actual.focus_next(reverse); }
        void scroll(const gui::WidgetKey& k,gui::Point p) override { app.actual.scroll(k,p); }
        gui::Point scroll_offset(const gui::WidgetKey& k) const override { return app.actual.scroll_offset(k); }
        gui::TextSelection text_selection(const gui::WidgetKey& k) const override { return app.actual.text_selection(k); }
        void text_selection(const gui::WidgetKey& k,gui::TextSelection value) override { app.actual.text_selection(k,value); }
        bool open_popup(const gui::WidgetKey& k) override { return app.actual.open_popup(k); }
        void close_popup(const gui::WidgetKey& k) override { app.actual.close_popup(k); }
        void invalidate(const gui::WidgetKey& k,gui::PixelRect r) override { app.actual.invalidate(k,r); }
        bool closed() const override { return app.stopped || app.actual.closed(); }
        void close() override { app.stop_requested=true; }
    };
    struct Release { DocumentFormsRequestToken token; A::EngineDocumentTarget target; std::uint64_t barrier,after_revision; };
    struct SafeProof { A::EngineNativeEffect effect; std::uint64_t revision; };

    gui::Adapter& actual;
    std::shared_ptr<A::EngineOwner> owner;
    const std::thread::id thread{std::this_thread::get_id()};
    const std::uint64_t application;
    Proxy proxy;
    EngineDocumentBroker broker;
    AppendedDocumentForms forms;
    A::EngineDocumentTarget current;
    std::optional<A::EngineNativeEffect> effect;
    std::optional<SafeProof> safe_proof;
    std::optional<Release> release;
    std::optional<DocumentViewport> queued_viewport;
    gui::Snapshot candidate,safe_view;
    std::uint64_t origin{},origin_barrier{},barrier{1},epoch{1},forms_epoch{1};
    std::optional<A::EngineNativeEffect> origin_effect;
    bool candidate_success{},candidate_redacted{},gate{true},cover{true},suspend_requested{},suspension_frame_requested{};
    bool desired_foreground{true},forms_foreground{true},effect_acknowledged{},owned_service_active{};
    bool handling{},ticking{},publishing{},stop_requested{},stopped{};
    std::string error;

    static std::uint64_t checked_owner(const std::shared_ptr<A::EngineOwner>& value) {
        if (!value || !value->configured() || value->closed() ||
            (!A::engine_document::document_profile_valid(value->document_profile()) && !value->document_actions_enabled()) ||
            !value->identity().application_instance)
            throw std::invalid_argument("No configured native document-profile owner");
        return value->identity().application_instance;
    }
    Impl(gui::Adapter& adapter,std::shared_ptr<A::EngineOwner> engine,DocumentViewport viewport)
        : actual(adapter),owner(std::move(engine)),application(checked_owner(owner)),proxy(*this),
          broker(owner,make_bindings()),
          forms(proxy,application,viewport,[this]{return reserve();}),current(target(owner->identity())) {
        forms.document_actions_available(owner->document_actions_enabled());
        candidate.client_size={0,0}; safe_view=redacted(candidate);
    }
    void check_thread() const {
        if (thread!=std::this_thread::get_id()) throw std::logic_error("Document application requires its serialized owner");
    }
    bool quiet() const { return !handling && !ticking && !publishing; }
    bool masked() const { return cover || suspend_requested || stop_requested; }
    void advance(std::uint64_t& value) {
        if (value==std::numeric_limits<std::uint64_t>::max()) {
            stop_requested=true; throw std::overflow_error("Document application identity exhausted");
        }
        ++value;
    }
    void suspend() {
        advance(barrier); advance(epoch); gate=true; suspend_requested=true; suspension_frame_requested=false; release.reset();
    }
    void watch() {
        if (forms_epoch!=forms.input_epoch()) { forms_epoch=forms.input_epoch(); advance(epoch); }
        const auto latest=target(owner->identity());
        if (latest!=current) { current=latest; suspend(); }
        const auto pending=owner->native_effect();
        if (pending && (!effect || !same_effect(*effect,*pending))) {
            effect=*pending; safe_proof.reset(); effect_acknowledged=false; suspend();
        } else if (!pending && effect) {
            effect.reset(); safe_proof.reset(); effect_acknowledged=false; suspend();
        } else if (pending) effect=*pending;
        if (current.application_instance!=application) {
            error="Engine application instance changed"; stop_requested=true;
        }
        if (!owner->document_enabled()) {
            error="Native document endpoint is unavailable"; stop_requested=true;
        }
        if (owner->closed() || actual.closed() || forms.closed()) stop_requested=true;
        if (stop_requested) { gate=true; cover=true; }
    }
    void present(gui::Snapshot value) {
        watch();
        if (!value.revision) throw std::invalid_argument("Zero document presentation revision");
        if (value.revision!=origin) {
            if (value.revision<origin) throw std::invalid_argument("Document presentation revision went backwards");
            auto safe=redacted(value);
            if (!error.empty()) { safe.title=error; value.title=error; }
            auto next=masked() ? safe : std::move(value);
            safe_view=std::move(safe); candidate=std::move(next);
            origin=candidate.revision; origin_barrier=barrier; origin_effect=effect;
            candidate_redacted=masked(); candidate_success=false;
        }
        // An already-attempted origin is immutable, including after a throwing
        // actual present. A newer barrier waits for that exact retry to finish.
        Guard guard(publishing);
        actual.present(candidate);
        candidate_success=true;
        if (candidate_redacted && origin_effect) safe_proof=SafeProof{*origin_effect,origin};
        watch();
    }
    std::optional<std::uint64_t> reserve() {
        watch();
        if (stop_requested || suspend_requested || effect || owned_service_active || !desired_foreground || !forms_foreground ||
            !ready(current) || owner->callback_depth() || !owner->document_enabled()) return {};
        return broker.reserve_legacy();
    }
    void retire_unadmitted() {
        // Foreground loss has now retired any reservation hidden behind a
        // never-returned Forms publication; returned unadmitted work is likewise
        // proven not entered. No admitted ticket is cancelled here.
        broker.retire_legacy_unadmitted();
    }
    void finish_stop() noexcept {
        if (stopped || !quiet() || owner->callback_depth()) return;
        forms.shutdown(); broker.shutdown(); owner->close(); stopped=true;
        try { actual.close(); } catch (...) {}
    }
    void poison(const char* reason) {
        error=reason; gate=true; cover=true; stop_requested=true;
        // Owner retains the original claimed/result evidence. A terminal
        // transport uncertainty is never repaired with ACK or another export.
        owner->close();
    }
    void apply_suspension() {
        if (!suspend_requested) return;
        const auto applying=barrier;
        if (forms.presentation_pending()) forms.retry_presentation();
        if (forms.presentation_pending() || stop_requested) return;
        cover=true;
        if (!suspension_frame_requested) {
            suspension_frame_requested=true;
            if (forms_foreground) {
                forms_foreground=false;
                try { forms.foreground(false); }
                catch (...) { retire_unadmitted(); throw; }
            } else forms.request_presentation();
        }
        retire_unadmitted();
        if (barrier!=applying) return;
        suspend_requested=false;
        forms.tick();
    }
    std::optional<DocumentActionV1Request> encode_body(const DocumentFormsRequest& source,
            A::EngineDocumentTarget id,std::uint64_t sequence) {
        const auto* document=std::get_if<DocumentEngineRequest>(&source.action);
        const auto* choice=std::get_if<ChooseSingleDocumentOption>(&source.action);
        const auto* control=std::get_if<ActivateDocumentControl>(&source.action);
        if (!(document && document->intent) && !choice && !control) return {};
        if (!owner->document_actions_enabled())
            throw std::invalid_argument("Missing document-actions-v1 profile4083");
        // Local input-button actions have no Controller token. Their actual
        // globally reserved sequence supplies the nested correlation unchanged.
        const DocumentActionV1Key key{id.worker_epoch,id.application_instance,id.document_sequence,id.service_generation,
            sequence,document ? document->token.id : control ? sequence : 0};
        DocumentActionV1 action;
        DocumentVersion version;
        if (choice) { version=choice->expected; action=DocumentActionV1ChooseSingleOption{choice->node,choice->option}; }
        else if (control) { version=control->expected; action=DocumentActionV1Activate{control->node}; }
        else {
            if (document->token.generation!=application) throw std::invalid_argument("Foreign document action generation");
            const auto& intent=*document->intent; version=intent.version;
            switch (intent.action) {
            case DocumentAction::focus: action=DocumentActionV1Focus{intent.node}; break;
            case DocumentAction::activate: action=DocumentActionV1Activate{intent.node}; break;
            case DocumentAction::select:
                if (!intent.selection) throw std::invalid_argument("Missing document selection");
                action=DocumentActionV1Select{{{intent.selection->anchor.node,intent.selection->anchor.utf16_offset,DocumentNativeOffsetKind::text_utf16},
                    {intent.selection->focus.node,intent.selection->focus.utf16_offset,DocumentNativeOffsetKind::text_utf16}}}; break;
            }
        }
        return encode_document_action_v1(key,version,action);
    }
    DocumentBodyCompletion decode_body(std::span<const std::uint8_t> bytes,const DocumentActionV1Request& request) {
        const auto decoded=decode_document_action_v1_reply(bytes,request);
        DocumentBodyCompletion completion;
        switch (decoded.result) {
        case DocumentActionV1Result::completed: completion.outcome=DocumentBodyOutcome::completed; break;
        case DocumentActionV1Result::completed_needs_current_observation: completion.outcome=DocumentBodyOutcome::needs_current_observation; break;
        case DocumentActionV1Result::rejected: completion.outcome=DocumentBodyOutcome::rejected; break;
        case DocumentActionV1Result::indeterminate: completion.outcome=DocumentBodyOutcome::indeterminate; break;
        }
        if (decoded.publication) completion.publication=decoded.publication->observation;
        // Consumed body work cannot rearm the old publication. Only a new paired
        // query and actual presentation release this existing application gate.
        gate=true; cover=true; release.reset();
        return completion;
    }
    EngineDocumentBroker::LegacyBindings make_bindings() {
        // Construction captures only. Broker does not invoke these callbacks
        // until after its following Forms member has completed construction.
        EngineDocumentBroker::LegacyBindings bindings;
        bindings.next=[this] {
            auto request=forms.next_request();
            watch();
            return request;
        };
        bindings.complete=[this](DocumentFormsRequestToken token,DocumentFormsCompletion completion) {
            return forms.complete(token,std::move(completion));
        };
        bindings.fail=[this](DocumentFormsRequestToken token,DocumentRequestFailure failure) {
            return forms.fail(token,failure);
        };
        bindings.progress=[this]{forms.tick();};
        bindings.presentation_pending=[this] {
            return forms.presentation_pending() || suspend_requested || stop_requested;
        };
        bindings.can_stage=[this] {
            return !stopped && !stop_requested && !suspend_requested && !effect &&
                desired_foreground && forms_foreground && !owned_service_active;
        };
        bindings.fresh_query=[this]{return gate;};
        bindings.barrier=[this]{return barrier;};
        bindings.query_delivered=[this](DocumentFormsRequestToken token,A::EngineDocumentTarget native_target,
                std::uint64_t native_barrier,bool fresh) {
            if (forms.accepted_query()==token) error.clear();
            else if (fresh) {
                error="Native observation rejected; document remains suspended";
                forms.request_presentation();
            }
            if (fresh && native_barrier==barrier && native_target==current &&
                !effect && desired_foreground && forms.accepted_query()==token) {
                release=Release{token,current,barrier,origin}; cover=false;
            }
        };
        bindings.failure=[this](const char* reason){poison(reason);};
        bindings.rejection=[this](const char* reason){error=reason;};
        bindings.encode_body=[this](const DocumentFormsRequest& request,A::EngineDocumentTarget native_target,
                std::uint64_t sequence) {
            return encode_body(request,native_target,sequence);
        };
        bindings.decode_body=[this](std::span<const std::uint8_t> bytes,const DocumentActionV1Request& request) {
            return decode_body(bytes,request);
        };
        bindings.body_ack=[](std::span<const std::uint8_t> bytes,std::uint64_t original) {
            const auto decoded=decode_document_action_v1_ack(bytes);
            return decoded && decoded->original_action_sequence==original && decoded->code!=DocumentActionV1AckCode::stale;
        };
        return bindings;
    }
    void maybe_release() {
        if (!release || suspend_requested || effect || !desired_foreground || forms.presentation_pending() || !candidate_success) return;
        if (release->barrier!=barrier || release->target!=current || forms.accepted_query()!=release->token) {
            release.reset(); return;
        }
        if (candidate_redacted || origin<=release->after_revision || origin_barrier!=barrier) return;
        gate=false; release.reset(); advance(epoch);
    }
    void tick() {
        check_thread(); if (!quiet() || stopped || owner->callback_depth()) return;
        if (stop_requested) { finish_stop(); return; }
        {
            Guard guard(ticking);
            watch();
            if (!stop_requested) {
                apply_suspension();
                if (queued_viewport && !forms.presentation_pending()) {
                    forms.viewport(*queued_viewport); queued_viewport.reset();
                }
                broker.settle_legacy();
                if (!stop_requested && !suspend_requested) {
                    forms.tick();
                    if (!forms.presentation_pending() && !broker.legacy_has_work()) {
                        if (effect) {
                            if (!broker.legacy_pending() && !effect_acknowledged && safe_proof && same_effect(safe_proof->effect,*effect))
                                effect_acknowledged=owner->acknowledge_document_native_effect(effect->ticket,target(effect->target),safe_proof->revision);
                        } else if (desired_foreground && !owned_service_active) {
                            if (!forms_foreground) {
                                forms_foreground=true; forms.foreground(true);
                            }
                            broker.stage_legacy();
                        }
                    } else if (broker.legacy_unadmitted()) broker.stage_legacy();
                    maybe_release();
                }
            }
        }
        if (stop_requested) finish_stop();
    }
};

AppendedEngineDocumentApplication::AppendedEngineDocumentApplication(gui::Adapter& adapter,
        std::shared_ptr<appended::EngineOwner> owner,DocumentViewport viewport)
    : impl_(std::make_unique<Impl>(adapter,std::move(owner),viewport)) {}
AppendedEngineDocumentApplication::~AppendedEngineDocumentApplication() { shutdown(); }
const gui::Snapshot& AppendedEngineDocumentApplication::view() const noexcept { return impl_->gate ? impl_->safe_view : impl_->candidate; }
void AppendedEngineDocumentApplication::handle(gui::Event event) {
    impl_->check_thread();
    if (std::holds_alternative<gui::CloseEvent>(event)) { shutdown(); return; }
    if (!impl_->quiet() || impl_->stopped || impl_->stop_requested || impl_->owner->callback_depth()) return;
    impl_->watch();
    if (impl_->stop_requested || impl_->gate || impl_->owned_service_active || !impl_->desired_foreground || impl_->queued_viewport) return;
    Guard guard(impl_->handling); impl_->forms.handle(std::move(event)); impl_->watch();
}
bool AppendedEngineDocumentApplication::queue_selection(DocumentSelection selection) {
    impl_->check_thread();
    if (!impl_->quiet() || impl_->stopped || impl_->stop_requested || impl_->owner->callback_depth()) return false;
    impl_->watch();
    if (impl_->stop_requested || impl_->gate || impl_->owned_service_active || !impl_->desired_foreground || impl_->queued_viewport) return false;
    const bool queued=impl_->forms.queue_selection(std::move(selection)); impl_->watch(); return queued;
}
void AppendedEngineDocumentApplication::tick() { impl_->tick(); }
void AppendedEngineDocumentApplication::retry_presentation() {
    impl_->check_thread(); if (!impl_->quiet() || impl_->stopped || impl_->owner->callback_depth()) return;
    if (impl_->stop_requested) { impl_->tick(); return; }
    { Guard guard(impl_->ticking); impl_->forms.retry_presentation(); }
    impl_->tick();
}
void AppendedEngineDocumentApplication::viewport(DocumentViewport value) {
    impl_->check_thread();
    if (!value.columns || value.columns>500 || !value.drawable_rows || value.drawable_rows>200) throw std::invalid_argument("Invalid document application viewport");
    if (!impl_->stopped) { impl_->queued_viewport=value; impl_->advance(impl_->epoch); }
}
void AppendedEngineDocumentApplication::foreground(bool value) {
    impl_->check_thread();
    if (impl_->stopped || impl_->desired_foreground==value) return;
    impl_->desired_foreground=value; impl_->suspend();
}
void AppendedEngineDocumentApplication::set_owned_service_active(bool value) {
    impl_->check_thread();
    if (impl_->stopped || impl_->owned_service_active==value) return;
    impl_->owned_service_active=value; impl_->suspend();
}
bool AppendedEngineDocumentApplication::owned_service_ready() const noexcept {
    const auto& s=*impl_;
    return s.thread==std::this_thread::get_id() && s.owned_service_active && s.quiet() &&
        !s.stopped && !s.stop_requested && s.desired_foreground && !s.forms_foreground &&
        !s.suspend_requested && !s.queued_viewport && !s.effect && !s.release &&
        !s.forms.presentation_pending() && s.broker.native_effect_quiescent() && !s.owner->callback_depth();
}
void AppendedEngineDocumentApplication::request_observation() {
    impl_->check_thread(); if (!impl_->stopped && !impl_->stop_requested) impl_->forms.request_observation();
}
void AppendedEngineDocumentApplication::shutdown() noexcept {
    if (!impl_) return;
    impl_->stop_requested=true; impl_->gate=true; impl_->cover=true; impl_->finish_stop();
}
bool AppendedEngineDocumentApplication::presentation_pending() const noexcept {
    return !impl_->stopped && (impl_->forms.presentation_pending() || impl_->suspend_requested || impl_->queued_viewport ||
        impl_->release || (impl_->origin && !impl_->candidate_success));
}
bool AppendedEngineDocumentApplication::closed() const noexcept { return impl_->stopped || impl_->stop_requested; }
bool AppendedEngineDocumentApplication::body_ready() const noexcept { return !impl_->gate && !impl_->stop_requested && !impl_->queued_viewport && impl_->forms.body_ready(); }
bool AppendedEngineDocumentApplication::modal_open() const noexcept { return !impl_->gate && impl_->forms.modal_open(); }
std::uint64_t AppendedEngineDocumentApplication::input_epoch() const noexcept { return impl_->epoch; }
const std::string& AppendedEngineDocumentApplication::last_error() const noexcept { return impl_->error.empty() ? impl_->forms.last_error() : impl_->error; }
gui_document::TerminalHook AppendedEngineDocumentApplication::document_terminal() noexcept {
    return {impl_->owner.get(),[](void* context) noexcept {
        static_cast<A::EngineOwner*>(context)->notify_document_terminal();
    }};
}
std::optional<gui::ServiceRequest> AppendedEngineDocumentApplication::next_service() { return {}; }
bool AppendedEngineDocumentApplication::complete_service(gui::ServiceResult) { return false; }
void AppendedEngineDocumentApplication::qualify(const std::function<void()>& present) { retry_presentation(); if (present) present(); }

} // namespace foundation::ui
