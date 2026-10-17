// SPDX-License-Identifier: CC0-1.0
#include "native_rev_surface_peer.hpp"
#include "WinEvent.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <vector>
#include <stdexcept>
#include <utility>

namespace foundation::host {
namespace S=gui_surface;
namespace E=gui_editor;
namespace {
E::TextObservation text(std::string value,S::ByteRange selected,bool backward=false) {
    return capture_native_editor_text(std::move(value),selected,
        backward?E::Direction::backward:selected.begin==selected.end?E::Direction::none:E::Direction::forward);
}
bool bounded(const std::string& value) {return value.size()<=NativeEditorCapture::max_text_bytes && S::valid_text(value);}
bool same_basis(E::Basis a,E::Basis b) {
    a.identity.presentation_revision=b.identity.presentation_revision=0;return a==b;
}
std::optional<gui::Key> prompt_key(const std::string& name,unsigned modifiers) {
    if((modifiers&S::control) && (name=="a" || name=="A"))return gui::Key::select_all;
    if(name=="Enter")return gui::Key::enter;
    if(name=="Escape")return gui::Key::escape;
    if(name=="Tab")return gui::Key::tab;
    if(name=="ArrowLeft")return gui::Key::left;
    if(name=="ArrowRight")return gui::Key::right;
    if(name=="ArrowUp")return gui::Key::up;
    if(name=="ArrowDown")return gui::Key::down;
    if(name=="Home")return gui::Key::home;
    if(name=="End")return gui::Key::end;
    if(name=="Backspace")return gui::Key::backspace;
    if(name=="Delete")return gui::Key::delete_key;
    return {};
}
std::string held_key(const S::KeyTransition& value) {
    return value.code.empty()?"key:"+value.key+":"+std::to_string(value.location):"code:"+value.code;
}
}

struct NativeRevSurfacePeer::Impl {
    gui::FramebufferAdapter& canvas;
    NativeSurfaceWindow config;
    NativeSurfaceIngress ingress;
    NativeSurfaceMode mode;
    gui::rev::Adapter window;
    gui::Frame frame;
    gui::Snapshot snapshot;
    RevSurfaceFacts facts;
    std::optional<RevSurfaceFacts> reported;
    std::optional<S::Identity> context_identity,reported_context;
    std::optional<S::Presentation> surface;
    std::optional<E::TextObservation> value,composition_before;
    std::optional<E::Basis> passage_basis;
    S::ByteRange composition_range;
    std::optional<S::EditorContext> editor_context;
    struct HeldKey {std::string identity;bool editor;std::optional<S::Identity> context;bool retired{};};
    std::vector<HeldKey> held;
    std::uint64_t transaction{},token{},next_token{1},mutation{};
    unsigned buttons{};
    double x{},y{},origin_x{},origin_y{},scale_x{1},scale_y{1};
    bool live{true},blocked{true},paused{},body_keys{},activated{},presenting{},entering{},refresh_focus{},prompt_active{},prompt_dirty{},closing_request{},release_capture{};
    std::uint64_t prompt_transaction{};
    std::string failure;
    Impl(gui::FramebufferAdapter& adapter,NativeSurfaceWindow window_config,
            NativeSurfaceIngress input,NativeSurfaceMode selected)
        :canvas(adapter),config(std::move(window_config)),ingress(std::move(input)),mode(selected) {
        if(!ingress.input || !ingress.invalidate || !ingress.drawable_pixels || !ingress.foreground ||
            (mode==NativeSurfaceMode::editor_v1 && !ingress.editor))
            throw std::invalid_argument("Incomplete Rev native surface ingress");
        if(!std::isfinite(config.width)||!std::isfinite(config.height)||!std::isfinite(config.scale)||
            config.width<=0||config.height<=0||config.width>16384||config.height>16384||config.scale<=0)
            throw std::invalid_argument("Invalid Rev surface window");
    }
    ~Impl(){close();}
    void fail(const std::string& message) {
        if(failure.empty())failure=message;
        suspend();ingress.invalidate(S::RevocationReason::unavailable);
    }
    void suspend() noexcept {
        ++mutation;blocked=true;paused=false;body_keys=false;buttons=0;token=0;
        for(auto& key:held)key.retired=true;
        passage_basis.reset();
        value.reset();composition_before.reset();composition_range={};transaction=0;
        try{window.native_surface_suspend(true);}catch(...){}
        release_capture=true;
    }
    void close() noexcept {
        if(!live)return;
        suspend();live=false;
        try{(void)window.native_surface_capture(false);window.native_surface({},false);window.close();}catch(...){}
    }
    bool send(S::Input input) {return ingress.input(std::move(input)).status==S::Status::ok;}
    bool observe(NativeEditorObservation observation) {
        const auto before=mutation;
        const auto after=observation.after;
        if(!ingress.editor(std::move(observation))) {fail("Rev native editor passage was rejected");return false;}
        if(before!=mutation)return false;
        if(after)value=*after;
        return true;
    }
    void native_context(bool preserve=false) {
        RevSurfaceContext context;
        context.enabled=value.has_value() && !blocked;
        context.editable=context.enabled;
        context.preserve_passage=preserve;
        if(value) {
            context.surrounding=value->value;context.selection_start=value->selection_start;
            context.selection_end=value->selection_end;context.backward=value->selection_direction==E::Direction::backward;
        }
        if(editor_context && surface) {
            auto caret=editor_context->caret;
            const auto& clip=surface->clip;
            const auto right=std::min(caret.x+caret.width,clip.x+clip.width);
            const auto bottom=std::min(caret.y+caret.height,clip.y+clip.height);
            caret.x=std::clamp(caret.x,clip.x,clip.x+clip.width);
            caret.y=std::clamp(caret.y,clip.y,clip.y+clip.height);
            caret.width=std::max(0.0,right-caret.x);caret.height=std::max(0.0,bottom-caret.y);
            const auto checked=[](double number) {
                if(!std::isfinite(number)||std::abs(number)>1000000)throw std::invalid_argument("Invalid Rev caret transform");
                return int(std::floor(number));
            };
            context.caret_x=checked(origin_x+caret.x*scale_x);
            context.caret_y=checked(origin_y+caret.y*scale_y);
            context.caret_width=std::max(1,checked(std::ceil(caret.width*scale_x)));
            context.caret_height=std::max(1,checked(std::ceil(caret.height*scale_y)));
        }
        window.native_surface_context(context);
    }
    void editor(const NativeEditorPresentation& presentation) {
        ++mutation;
        if(presentation.admission==NativeEditorAdmission::paused) {
            if(!passage_basis || !presentation.passage_basis || !same_basis(*passage_basis,*presentation.passage_basis)) {
                fail("Rev paused frontend does not join its previously checked Basis");return;
            }
            paused=true;body_keys=false;
            return; // Capture owns all passages; do not reset native IME or queue copies.
        }
        refresh_focus=refresh_focus || paused;
        paused=false;surface=presentation.surface;editor_context=presentation.context;
        if(!surface || !surface->available) {suspend();return;}
        auto identity=surface->identity;identity.presentation_revision=0;context_identity=std::move(identity);
        blocked=false;
        if(mode!=NativeSurfaceMode::editor_v1)return;
        const auto* publication=presentation.publication?&*presentation.publication:nullptr;
        const auto* basis=publication && publication->basis?&*publication->basis:nullptr;
        body_keys=publication && publication->retirement && !publication->retirement->authority_retired &&
            publication->retirement->availability==E::NativeAvailability::noneditable;
        if(!basis || !presentation.context || !presentation.context->editable) {
            for(auto& key:held)if(key.editor)key.retired=true;
            passage_basis.reset();
            value.reset();composition_before.reset();composition_range={};transaction=0;
            window.native_surface_suspend();return;
        }
        if(presentation.draft) {
            const auto& draft=*presentation.draft;
            if(!bounded(draft.value) || capture_native_editor_text(draft.value,draft.selection_start,
                    draft.selection_end,draft.selection_direction)!=draft) {fail("Invalid Rev accepted frontend draft");return;}
            value=draft;
        } else value=text(basis->surrounding,basis->selection,basis->backward);
        if(!bounded(value->value)) {fail("Rev frontend text exceeds its negotiated bound");return;}
        passage_basis=*basis;
        const bool ended=presentation.composition && presentation.composition->state==E::CompositionState::ended;
        if((!presentation.preserve_passage && !basis->composition) || ended) {
            window.native_surface_suspend();
            transaction=0;composition_before.reset();composition_range={};
        }
        try{native_context(presentation.preserve_passage);}catch(const std::exception& error){fail(error.what());}
    }
    bool key(const RevSurfaceEvent& raw) {
        S::KeyTransition key{raw.down?S::KeyPhase::down:S::KeyPhase::up,raw.key,raw.code,raw.location,raw.modifiers,raw.repeat};
        const auto identity=held_key(key);
        auto previous=std::find_if(held.begin(),held.end(),[&](const HeldKey& item){return item.identity==identity;});
        if(raw.down && !raw.repeat && previous!=held.end() && previous->retired) {
            held.erase(previous);previous=held.end();
        }
        const bool existing=previous!=held.end();
        if((!raw.down || raw.repeat) && !existing)return true;
        if(raw.down && !existing && held.size()==64){fail("Rev held-key limit exceeded");return true;}
        const auto slot=existing?std::size_t(previous-held.begin()):held.size();
        const bool editor=existing?previous->editor:mode==NativeSurfaceMode::editor_v1 && value.has_value();
        const auto key_context=existing?previous->context:context_identity;
        bool accepted=false,captured=false;
        const auto before=mutation;
        if(editor && !blocked && value && key_context==context_identity && (!existing || !previous->retired)) {
            NativeEditorObservation observation;
            observation.kind=E::Kind::key;observation.authority=E::Authority::native;
            observation.group_end=true;observation.before=*value;
            observation.data=E::KeyData{key,transaction!=0};
            accepted=observe(std::move(observation));
            captured=surface && S::capture_key(surface->keys,key)==S::Capture::capture;
        } else if(!editor && ((!blocked && (mode!=NativeSurfaceMode::editor_v1 || body_keys)) || (!raw.down && existing))) {
            const auto result=ingress.input(key);accepted=result.status==S::Status::ok;
            captured=result.accepted && result.accepted->capture==S::Capture::capture;
        }
        if(before==mutation) {
            if(!raw.down && existing)held.erase(held.begin()+std::ptrdiff_t(slot));
            else if(accepted && !existing)held.push_back({identity,editor,context_identity});
        }
        const bool context=raw.down && !raw.repeat && accepted &&
            (raw.key=="ContextMenu" || (raw.key=="F10" && (raw.modifiers&S::shift)));
        if(context && !blocked) {
            RevSurfaceEvent request;request.kind=RevSurfaceEvent::Kind::mouse;request.mouse_phase=5;
            request.keyboard_context=true;request.buttons=buttons;(void)mouse(request);
            return true;
        }
        return accepted?captured:true;
    }
    bool edit(const RevSurfaceEvent& raw) {
        if(blocked || mode!=NativeSurfaceMode::editor_v1 || !value)return true;
        if(!bounded(raw.text)) {fail("Invalid or oversized Rev native text");return true;}
        NativeEditorObservation observation;
        observation.before=*value;
        if(raw.kind==RevSurfaceEvent::Kind::selection) {
            try {
                auto after=capture_native_editor_text(value->value,raw.selection_start,raw.selection_end,
                    raw.backward?E::Direction::backward:raw.selection_start==raw.selection_end?E::Direction::none:E::Direction::forward);
                observation.kind=E::Kind::selection;observation.authority=E::Authority::range;
                observation.after=after;observation.data=E::SelectionData{after.selection,raw.backward};
                (void)observe(std::move(observation));native_context(true);
            }catch(const std::exception& error){fail(error.what());}
            return true;
        }
        const bool begin=raw.kind==RevSurfaceEvent::Kind::preedit_begin;
        const bool update=raw.kind==RevSurfaceEvent::Kind::preedit_update;
        const bool commit=raw.kind==RevSurfaceEvent::Kind::preedit_commit;
        const bool cancel=raw.kind==RevSurfaceEvent::Kind::preedit_cancel;
        if(begin && (!raw.transaction || transaction)) {fail("Invalid Rev native composition start");return true;}
        if((update||commit||cancel) && (!transaction || raw.transaction!=transaction)) {fail("Unjoined Rev native composition passage");return true;}
        if(raw.kind==RevSurfaceEvent::Kind::commit && transaction) {fail("Unjoined Rev commit during preedit");return true;}
        try {
            const auto original=*value;
            const auto replacement=transaction?composition_range:value->selection;
            if(!S::valid_range(value->value,replacement))throw std::invalid_argument("Invalid Rev frontend replacement");
            if(cancel) {
                if(!composition_before)throw std::invalid_argument("Missing Rev native composition baseline");
                observation.after=*composition_before;
            } else {
                const auto current_size=value->value.size()-(replacement.end-replacement.begin);
                if(raw.text.size()>NativeEditorCapture::max_text_bytes-current_size)throw std::length_error("Rev provisional text exceeds bound");
                const auto inserted=capture_native_editor_text(raw.text,raw.selection_start,raw.selection_end,
                    raw.backward?E::Direction::backward:raw.selection_start==raw.selection_end?E::Direction::none:E::Direction::forward);
                auto full=value->value.substr(0,replacement.begin)+raw.text+value->value.substr(replacement.end);
                auto selected=S::ByteRange{replacement.begin+inserted.selection.begin,replacement.begin+inserted.selection.end};
                if(raw.kind==RevSurfaceEvent::Kind::commit)selected={replacement.begin+raw.text.size(),replacement.begin+raw.text.size()};
                observation.after=text(std::move(full),selected,raw.backward);
            }
            if(begin||update||commit||cancel) {
                observation.kind=E::Kind::composition;observation.transaction=raw.transaction;
                observation.authority=begin?E::Authority::range:E::Authority::composition;
                observation.group_end=commit||cancel;
                E::CompositionData data;
                data.operation=begin?S::CompositionOperation::begin:update?S::CompositionOperation::update:commit?S::CompositionOperation::commit:S::CompositionOperation::cancel;
                data.text=raw.text;
                const auto selected=capture_native_editor_text(raw.text,raw.selection_start,raw.selection_end,E::Direction::none);
                data.selection=selected.selection;
                if(begin)data.replacement=value->selection;
                observation.data=std::move(data);
                if(observe(std::move(observation))) {
                    if(begin){transaction=raw.transaction;composition_before=original;}
                    composition_range={replacement.begin,replacement.begin+raw.text.size()};
                    if(commit||cancel){transaction=0;composition_before.reset();composition_range={};}
                }
            } else {
                observation.kind=E::Kind::text;observation.authority=E::Authority::range;
                observation.data=E::TextData{"insertText",raw.text,value->selection,{}};
                (void)observe(std::move(observation));
            }
            if(!blocked)native_context(true);
        }catch(const std::exception& error){fail(error.what());}
        return true;
    }
    bool mouse(const RevSurfaceEvent& raw) {
        if(blocked)return true;
        if(paused && (!token || raw.mouse_phase==1 || raw.mouse_phase==3 || raw.mouse_phase==5))return true;
        S::MouseTransition input;
        input.phase=static_cast<S::MousePhase>(raw.mouse_phase);
        input.x=(raw.x*facts.scale-origin_x)/scale_x;
        input.y=(raw.y*facts.scale-origin_y)/scale_y;
        input.button=raw.button;input.buttons=raw.buttons;input.clicks=raw.clicks;input.modifiers=raw.modifiers;
        input.wheel_x=raw.wheel_x;input.wheel_y=raw.wheel_y;
        input.context_origin=raw.keyboard_context?S::ContextOrigin::keyboard:S::ContextOrigin::pointer;
        if(raw.keyboard_context){input.x=input.y=0;input.modifiers=0;}
        if(!std::isfinite(input.x)||!std::isfinite(input.y)) {fail("Invalid Rev mouse transform");return true;}
        const auto bit=S::mouse_button_bit(raw.button);
        if(input.phase==S::MousePhase::up && (!token || !(buttons&bit)))return true;
        if(input.phase==S::MousePhase::down && ((buttons&bit) || raw.buttons!=(buttons|bit)))return true;
        if((input.phase==S::MousePhase::move || input.phase==S::MousePhase::wheel || input.phase==S::MousePhase::context) && raw.buttons!=buttons)return true;
        if(input.phase==S::MousePhase::down && !buttons) {
            if(!next_token){fail("Rev mouse capture token exhausted");return true;}
            if(input.x<0||input.y<0||input.x>=snapshot.client_size.width||input.y>=snapshot.client_size.height)return true;
            token=next_token;next_token=next_token==UINT64_MAX?0:next_token+1;
            if(!window.native_surface_capture(true)){fail("Rev native mouse capture failed");return true;}
            release_capture=false; // A new owned gesture supersedes an older deferred release.
        }
        input.capture_token=token;
        if(input.phase==S::MousePhase::cancel) {
            input={};input.phase=S::MousePhase::cancel;input.capture_token=token;
            if(!token)return true;
        }
        const auto before=mutation;
        const auto accepted=ingress.input(input);
        if(accepted.status!=S::Status::ok) {fail("Rev mouse passage was rejected");return true;}
        if(before!=mutation)return true;
        buttons=raw.buttons;x=input.x;y=input.y;
        if((input.phase==S::MousePhase::up && !buttons)||input.phase==S::MousePhase::cancel) {
            buttons=0;token=0;release_capture=true;
        }
        return true;
    }
    void flush_capture_release() {
        if(!release_capture)return;
        release_capture=false;
        if(!window.native_surface_capture(false))fail("Rev native mouse release failed");
    }
    void prompt_context() {
        if(!canvas.prompt())return;
        const auto& prompt=*canvas.prompt();const auto selected=canvas.prompt_selection();
        auto observed=text(prompt.value,{std::min(selected.anchor,selected.caret),std::max(selected.anchor,selected.caret)},selected.caret<selected.anchor);
        RevSurfaceContext context;context.enabled=context.editable=true;context.preserve_passage=true;
        context.surrounding=prompt.value;context.selection_start=observed.selection_start;context.selection_end=observed.selection_end;context.backward=selected.caret<selected.anchor;
        const auto area=gui::prompt_field_bounds(snapshot.client_size);
        const auto advance=canvas.measure_text({prompt.value.substr(0,selected.caret),{14},1000000,snapshot.display_scale,gui::TextWrap::none});
        context.caret_x=int(std::floor(origin_x+(area.x+4+std::min(advance.width,std::max(0.0,area.width-8)))*scale_x));
        context.caret_y=int(std::floor(origin_y+area.y*scale_y));
        context.caret_width=1;context.caret_height=std::max(1,int(std::ceil(area.height*scale_y)));
        window.native_surface_context(context);
    }
    bool prompt_event(const RevSurfaceEvent& raw) {
        // The existing generic interaction engine owns service layout and edits.
        // Actual IME preedit is retained by the OS; only its result inserts text.
        prompt_dirty=true;
        if(raw.kind==RevSurfaceEvent::Kind::key) {
            if(raw.down && !prompt_transaction)if(auto key=prompt_key(raw.key,raw.modifiers))canvas.key(*key,raw.modifiers&S::control,raw.modifiers&S::shift,raw.modifiers&S::alt);
        } else if(raw.kind==RevSurfaceEvent::Kind::commit || raw.kind==RevSurfaceEvent::Kind::preedit_commit) {
            if(!bounded(raw.text) || (raw.kind==RevSurfaceEvent::Kind::preedit_commit && raw.transaction!=prompt_transaction)) {fail("Unjoined Rev service text passage");return true;}
            canvas.text(raw.text);prompt_transaction=0;
        } else if(raw.kind==RevSurfaceEvent::Kind::preedit_begin) {
            if(!raw.transaction || prompt_transaction){fail("Invalid Rev service composition start");return true;}
            prompt_transaction=raw.transaction;
        } else if(raw.kind==RevSurfaceEvent::Kind::preedit_update || raw.kind==RevSurfaceEvent::Kind::preedit_cancel) {
            if(!prompt_transaction || raw.transaction!=prompt_transaction || !bounded(raw.text)){fail("Unjoined Rev service preedit");return true;}
            if(raw.kind==RevSurfaceEvent::Kind::preedit_cancel)prompt_transaction=0;
        } else if(raw.kind==RevSurfaceEvent::Kind::mouse && raw.mouse_phase==1 && raw.button==0) {
            gui::PointerInput input;input.position={(raw.x*facts.scale-origin_x)/scale_x,(raw.y*facts.scale-origin_y)/scale_y};
            input.control=raw.modifiers&S::control;input.shift=raw.modifiers&S::shift;input.alt=raw.modifiers&S::alt;canvas.pointer(input);
        }
        if(canvas.prompt())prompt_context();
        return true;
    }
    void refresh_prompt() {
        if(bool(canvas.prompt())!=prompt_active) {
            prompt_active=bool(canvas.prompt());prompt_dirty=true;prompt_transaction=0;
            window.native_surface_suspend();
            if(prompt_active){suspend();prompt_context();}
        }
        if(prompt_dirty && snapshot.revision && !canvas.closed()) {
            prompt_dirty=false;(void)paint(canvas.snapshot());
            if(canvas.prompt())prompt_context();
        }
    }
    bool event(const RevSurfaceEvent& raw) {
        if(!live)return false;
        if(entering){fail("Reentrant Rev native input");return true;}
        struct Enter {bool& value;explicit Enter(bool& v):value(v){value=true;}~Enter(){value=false;}} turn(entering);
        if(raw.kind==RevSurfaceEvent::Kind::unavailable){fail(raw.text.empty()?"Rev native frontend became unavailable":raw.text);return true;}
        if(raw.kind==RevSurfaceEvent::Kind::close) {closing_request=true;suspend();ingress.invalidate(S::RevocationReason::closed);return true;}
        if(closing_request)return true;
        if(canvas.prompt())return prompt_event(raw);
        if(mode==NativeSurfaceMode::none)return false;
        if(raw.kind==RevSurfaceEvent::Kind::key)return key(raw);
        if(raw.kind==RevSurfaceEvent::Kind::mouse)return mouse(raw);
        return edit(raw);
    }
    void emit_facts() {
        if(!activated || !live)return;
        if(!reported || facts.width!=reported->width || facts.height!=reported->height)ingress.drawable_pixels(facts.width,facts.height);
        if(!reported || facts.active!=reported->active)ingress.foreground(facts.active);
        if(mode!=NativeSurfaceMode::none && (!reported || facts.focused!=reported->focused || facts.active!=reported->active || (!paused && (refresh_focus || context_identity!=reported_context)))) {
            (void)send(S::FocusChange{facts.focused,facts.active,S::FocusCause::external});
            reported_context=context_identity;refresh_focus=false;
        }
        reported=facts;
    }
    void lifecycle(const RevSurfaceFacts& next,bool changed) {
        if(!live)return;
        if(changed || (facts.focused && !next.focused) || (facts.active && !next.active)) {
            suspend();ingress.invalidate(changed?S::RevocationReason::replaced:S::RevocationReason::focus_loss);
        }
        facts=next;emit_facts();
    }
    void stage_renderer() {
        // Prepare the real renderer without mutating the App-facing canvas.
        gui::Snapshot blank;blank.revision=1;blank.title=config.title;
        blank.client_size={facts.render_width/facts.scale,facts.render_height/facts.scale};blank.display_scale=facts.scale;
        if(!facts.ready || facts.render_width<=0 || facts.render_height<=0 || !std::isfinite(facts.scale) || facts.scale<=0)
            throw std::runtime_error("Rev staged renderer has no actual drawable");
        window.present(std::move(blank));const auto captured=window.capture();
        if(!window.error().empty() || captured.width()!=std::uint64_t(facts.render_width) ||
            captured.height()!=std::uint64_t(facts.render_height))
            throw std::runtime_error("Rev staged renderer failed its actual readback");
    }
    NativeRenderReceipt paint(gui::Snapshot next) {
        if(!live || window.closed() || presenting)throw std::logic_error("Rev surface renderer is unavailable or reentrant");
        struct Paint {bool& value;explicit Paint(bool& v):value(v){value=true;}~Paint(){value=false;}} turn(presenting);
        next=prepare_native_blank_canvas(std::move(next),config);
        const auto revision=next.revision;
        canvas.present(std::move(next));snapshot=canvas.snapshot();
        frame=canvas.frame();
        facts=window.native_surface_facts();
        if(!frame.width||!frame.height||!frame.pixels||facts.render_width<=0||facts.render_height<=0||facts.scale<=0)
            throw std::runtime_error("Rev surface has no complete drawable frame");
        const auto fit=std::min(double(facts.render_width)/frame.width,double(facts.render_height)/frame.height);
        const auto width=std::max(std::int64_t{1},std::int64_t(std::floor(frame.width*fit)));
        const auto height=std::max(std::int64_t{1},std::int64_t(std::floor(frame.height*fit)));
        origin_x=std::floor((facts.render_width-width)/2.0);origin_y=std::floor((facts.render_height-height)/2.0);
        scale_x=double(width)/snapshot.client_size.width;scale_y=double(height)/snapshot.client_size.height;
        gui::Snapshot native;
        native.revision=revision;native.title=config.title;
        native.client_size={facts.render_width/facts.scale,facts.render_height/facts.scale};native.display_scale=facts.scale;
        gui::Widget bitmap;
        bitmap.spec.key={"rev-native-canvas",1};bitmap.spec.kind=gui::Kind::bitmap;
        bitmap.state.bounds={origin_x/facts.scale,origin_y/facts.scale,width/facts.scale,height/facts.scale};
        gui::BitmapImage image(frame.width,frame.height,gui::PixelFormat::rgb24);image.blit(0,0,frame.block());
        bitmap.state.bitmap={"rev-native-canvas",frame.revision,gui::image_bitmap(std::move(image))};
        native.widgets.push_back(std::move(bitmap));
        window.present(std::move(native));
        const auto captured=window.capture();
        if(!window.error().empty() || window.snapshot().revision!=revision || canvas.snapshot().revision!=revision ||
            captured.width()!=std::uint64_t(facts.render_width) || captured.height()!=std::uint64_t(facts.render_height))
            throw std::runtime_error("Rev actual render/readback does not join the selected Snapshot and drawable");
        return {revision};
    }
};

NativeRevSurfacePeer::NativeRevSurfacePeer(gui::FramebufferAdapter& adapter,const NativeSurfaceWindow& config,
        NativeSurfaceIngress ingress,NativeSurfaceMode mode)
    :impl_(std::make_shared<Impl>(adapter,config,std::move(ingress),mode)) {
    const std::weak_ptr<Impl> weak=impl_;
    auto hooks=std::make_shared<gui::rev::NativeSurfaceHooks>();
    hooks->event=[weak](const RevSurfaceEvent& event) {if(auto state=weak.lock();state&&state->live)return state->event(event);return false;};
    hooks->lifecycle=[weak](const RevSurfaceFacts& facts,bool changed) {if(auto state=weak.lock();state&&state->live)state->lifecycle(facts,changed);};
    // Host-owned generic prompts need actual IME passages in every App mode.
    // App capabilities below remain limited to the explicitly selected mode.
    impl_->window.native_surface(std::move(hooks),true);
    impl_->window.native_surface_window(config.title,int(std::ceil(config.width)),int(std::ceil(config.height)));
    impl_->window.show();impl_->facts=impl_->window.native_surface_facts();
    if(!impl_->facts.ready)throw std::runtime_error("Actual Rev native raw/editor hooks are unavailable");
    // The actual renderer and input callbacks exist before App construction.
    impl_->stage_renderer();
}
NativeRevSurfacePeer::~NativeRevSurfacePeer(){if(impl_)impl_->close();}
NativeSurfacePeer NativeRevSurfacePeer::peer() const {
    NativeSurfacePeer result;
    result.capabilities.supported=S::feature(S::Feature::raw_keys)|S::feature(S::Feature::focus)|S::feature(S::Feature::mouse_input);
    if(impl_->mode==NativeSurfaceMode::editor_v1)result.capabilities.supported|=S::feature(S::Feature::committed_text)|
        S::feature(S::Feature::composition)|S::feature(S::Feature::surrounding_text)|S::feature(S::Feature::selection);
    result.capabilities.mouse_input_version=S::mouse_input_version;
    if(impl_->mode==NativeSurfaceMode::none){result.capabilities.supported=0;result.capabilities.mouse_input_version=0;}
    const std::weak_ptr<Impl> weak=impl_;
    result.ready=[weak]{auto state=weak.lock();return state&&state->live&&!state->window.closed();};
    result.present=[weak](gui::Snapshot snapshot) {auto state=weak.lock();if(!state||!state->live)throw std::logic_error("Expired Rev surface renderer");return state->paint(std::move(snapshot));};
    result.editor=[weak](const NativeEditorPresentation& presentation){if(auto state=weak.lock();state&&state->live)state->editor(presentation);};
    result.suspend=[weak]{if(auto state=weak.lock();state&&state->live)state->suspend();};
    result.activate=[weak]{if(auto state=weak.lock();state&&state->live){state->activated=true;state->facts=state->window.native_surface_facts();state->emit_facts();}};
    result.close=[weak]{if(auto state=weak.lock())state->close();};
    return result;
}
bool NativeRevSurfacePeer::pump(){
    if(!impl_||!impl_->live)return false;
    try {impl_->flush_capture_release();impl_->refresh_prompt();const bool open=impl_->window.pump();impl_->flush_capture_release();impl_->refresh_prompt();return open;}
    catch(const std::exception& error){impl_->fail(error.what());return false;}
}
bool NativeRevSurfacePeer::closed() const{return !impl_||!impl_->live||impl_->window.closed();}
bool NativeRevSurfacePeer::close_requested() const{return !impl_||impl_->closing_request;}
const std::string& NativeRevSurfacePeer::error() const{return impl_->failure.empty()?impl_->window.error():impl_->failure;}

} // namespace foundation::host
