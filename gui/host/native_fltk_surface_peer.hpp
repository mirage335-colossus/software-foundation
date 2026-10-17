// SPDX-License-Identifier: CC0-1.0
#pragma once

// FLTK/Xlib may precede this opt-in leaf in the ordinary runner.
// Its legacy integer macro must not rewrite the neutral scoped Status enum.
#if defined(__linux__) && defined(Status)
#pragma push_macro("Status")
#undef Status
#define FOUNDATION_FLTK_RESTORE_XLIB_STATUS
#endif

#include "native_surface_composition.hpp"
#include "native_fltk_surface_platform.hpp"
// Restore the actual Xlib macro for any as-yet-unparsed XKB declarations.
// The X11 leaf removes it again after the complete native header set.
#ifdef FOUNDATION_FLTK_RESTORE_XLIB_STATUS
#pragma pop_macro("Status")
#undef FOUNDATION_FLTK_RESTORE_XLIB_STATUS
#endif
#include "adapter.hpp"
#include <FL/Fl_Image_Surface.H>
#include <FL/Fl_RGB_Image.H>
#include <algorithm>
#include <cmath>
#include <limits>
#include <memory>
#include <stdexcept>
#include <utility>
#if defined(_WIN32)
#include "native_fltk_surface_win32.hpp"
#elif defined(__linux__)
#include "native_fltk_surface_x11.hpp"
#endif

namespace foundation::host {

// One neutral logical-canvas transform, shared by output, mouse and native IME.
// Toolkit rendering pixels are queried from the actual window, not its seed.
inline std::optional<unsigned> fltk_native_mouse_button(int native) noexcept {
    if(native<1||native>5)return {};
    return static_cast<unsigned>(native-1); // FLTK L/M/R/back/forward -> DOM 0/1/2/3/4
}
inline unsigned fltk_native_mouse_buttons(int state) noexcept {
    unsigned result=0;
    const int flags[]{FL_BUTTON1,FL_BUTTON2,FL_BUTTON3,FL_BUTTON4,FL_BUTTON5};
    for(unsigned i=0;i<5;++i)if(state&flags[i])result|=gui_surface::mouse_button_bit(i);
    return result;
}
struct FltkNativeViewport {
    double x{},y{},scale{},scale_x{},scale_y{};
    int width{},height{},image_width{},image_height{};
    static FltkNativeViewport make(double logical_width,double logical_height,int width,int height) {
        if (!std::isfinite(logical_width)||!std::isfinite(logical_height)||logical_width<=0||logical_height<=0||width<=0||height<=0)
            throw std::invalid_argument("Native surface has no drawable canvas");
        const auto scale=std::min(double(width)/logical_width,double(height)/logical_height);
        if(!std::isfinite(scale)||scale<=0)throw std::invalid_argument("Native canvas scale is invalid");
        const int image_width=std::max(1,int(std::lround(logical_width*scale))),image_height=std::max(1,int(std::lround(logical_height*scale)));
        return {std::floor((width-image_width)/2.0),std::floor((height-image_height)/2.0),scale,image_width/logical_width,image_height/logical_height,width,height,image_width,image_height};
    }
    std::pair<double,double> logical(double native_x,double native_y) const {
        if (!(scale>0)) throw std::logic_error("Native surface transform is unavailable");
        return {(native_x-x)/scale_x,(native_y-y)/scale_y};
    }
    gui_surface::Rect caret(gui_surface::Rect value,gui_surface::Rect clip) const {
        for(double number:{value.x,value.y,value.width,value.height,clip.x,clip.y,clip.width,clip.height})
            if(!std::isfinite(number))throw std::invalid_argument("Native caret geometry is not finite");
        if(value.width<0||value.height<0||clip.width<0||clip.height<0)throw std::invalid_argument("Native caret geometry is negative");
        const auto left=std::max(value.x,clip.x),top=std::max(value.y,clip.y);
        const auto right=std::min(value.x+value.width,clip.x+clip.width),bottom=std::min(value.y+value.height,clip.y+clip.height);
        if (!(scale>0)||right<left||bottom<top) throw std::invalid_argument("Native editor caret is outside the accepted clip");
        return {x+left*scale_x,y+top*scale_y,(right-left)*scale_x,(bottom-top)*scale_y};
    }
};

// Bounded provisional text model of the dedicated native IME frontend. This is
// not an editor Controller. Only actual native commit/preedit/selection facts
// change it; keys never synthesize text, deletion, arrows or composition.
class FltkNativeFrontend {
    std::optional<gui_editor::TextObservation> draft_,root_;
    std::uint64_t transaction_{},next_group_{1};
    std::vector<std::uint64_t> dead_groups_;
    static gui_editor::Direction direction(bool backward) { return backward?gui_editor::Direction::backward:gui_editor::Direction::forward; }
    static gui_editor::TextObservation replace(const gui_editor::TextObservation& root,const FltkNativeEdit& edit) {
        const auto fragment=capture_native_editor_text(edit.text,edit.selection_start,edit.selection_end,direction(edit.backward));
        auto value=root.value.substr(0,root.selection.begin)+edit.text+root.value.substr(root.selection.end);
        if(value.size()>fltk_native_max_text_bytes)throw std::length_error("Native editor text limit");
        return capture_native_editor_text(std::move(value),gui_surface::ByteRange{root.selection.begin+fragment.selection.begin,root.selection.begin+fragment.selection.end},direction(edit.backward));
    }
public:
    const std::optional<gui_editor::TextObservation>& draft() const noexcept { return draft_; }
    bool composing() const noexcept { return transaction_!=0; }
    void clear() noexcept { draft_.reset();root_.reset();transaction_=0;dead_groups_.clear(); }
    void install(std::optional<gui_editor::TextObservation> value,bool preserve) {
        if(value && *value!=capture_native_editor_text(value->value,value->selection_start,value->selection_end,value->selection_direction))
            throw std::invalid_argument("Native editor publication text fields disagree");
        if(preserve) {
            if(!draft_||!value||*draft_!=*value)throw std::logic_error("Native editor publication would replace an outstanding passage");
            return;
        }
        if(transaction_ && value!=draft_)throw std::logic_error("Native editor preedit requires explicit retirement");
        draft_=std::move(value);
        if(!draft_) {root_.reset();transaction_=0;dead_groups_.clear();}
    }
    std::vector<NativeEditorObservation> observe(FltkNativePassage passage) {
        namespace E=gui_editor; namespace S=gui_surface;
        if(!draft_)return {};
        if(passage.edits.size()>fltk_native_max_passages)throw std::length_error("Native editor passage limit");
        for(const auto& edit:passage.edits)if(edit.kind!=FltkNativeEditKind::text&&edit.kind!=FltkNativeEditKind::selection&&
            edit.kind!=FltkNativeEditKind::composition_begin&&edit.kind!=FltkNativeEditKind::composition_update&&
            edit.kind!=FltkNativeEditKind::composition_commit&&edit.kind!=FltkNativeEditKind::composition_cancel)
            throw std::invalid_argument("Unknown native edit kind");
        if(passage.key && std::any_of(passage.edits.begin(),passage.edits.end(),[](const auto& edit){return edit.kind==FltkNativeEditKind::selection;}) &&
            std::any_of(passage.edits.begin(),passage.edits.end(),[](const auto& edit){return edit.kind!=FltkNativeEditKind::selection;}))
            throw std::logic_error("Mixed key selection/default passage is unsupported");
        std::vector<NativeEditorObservation> out;
        const bool dead=passage.key && passage.key->phase==S::KeyPhase::down && passage.key->key=="Dead";
        const bool dependent=passage.key && passage.key->phase==S::KeyPhase::down && !passage.edits.empty() &&
            (passage.edits.front().kind==FltkNativeEditKind::text || passage.edits.front().kind==FltkNativeEditKind::composition_begin);
        std::optional<std::uint64_t> group;
        if(dependent||dead) {
            if(dead_groups_.size()>=8)throw std::length_error("Native dead-key source limit");
            if(!next_group_||next_group_==UINT64_MAX)throw std::overflow_error("Native source group exhausted");
            group=next_group_++;
        }
        auto sources=dead_groups_;
        if(dependent&&group)sources.push_back(*group);
        if(!dependent && !passage.edits.empty() && !sources.empty())group=sources.back();
        if(passage.key)out.push_back({E::Kind::key,E::Authority::native,group,false,0,*draft_,{},E::KeyData{std::move(*passage.key),composing()}});
        for(const auto& edit:passage.edits) {
            auto before=*draft_;
            NativeEditorObservation observation;observation.before=before;
            if(edit.kind==FltkNativeEditKind::text) {
                if(transaction_)throw std::logic_error("Native text overlaps a preedit");
                auto actual=edit;
                // A native committed fragment's caret is at its actual supplied
                // selection; the platform never derives this fragment from a key.
                auto after=replace(before,actual);
                observation.kind=E::Kind::text;observation.authority=group?E::Authority::default_action:E::Authority::range;
                observation.group=group;observation.after=after;
                observation.data=E::TextData{"insertText",edit.text,before.selection,group?sources:std::vector<std::uint64_t>{}};
                draft_=std::move(after);
            } else if(edit.kind==FltkNativeEditKind::selection) {
                if(transaction_)throw std::logic_error("Native selection overlaps a preedit");
                auto after=capture_native_editor_text(before.value,edit.selection_start,edit.selection_end,direction(edit.backward));
                observation.kind=E::Kind::selection;observation.authority=E::Authority::range;observation.after=after;
                observation.data=E::SelectionData{after.selection,edit.backward};draft_=std::move(after);
            } else {
                const bool begin=edit.kind==FltkNativeEditKind::composition_begin;
                if(!edit.transaction || (begin?transaction_!=0:transaction_!=edit.transaction))throw std::logic_error("Native preedit transaction differs");
                if(begin) {root_=before;transaction_=edit.transaction;}
                if(!root_)throw std::logic_error("Native preedit root is unavailable");
                S::CompositionOperation operation=S::CompositionOperation::begin;
                if(edit.kind==FltkNativeEditKind::composition_update)operation=S::CompositionOperation::update;
                if(edit.kind==FltkNativeEditKind::composition_commit)operation=S::CompositionOperation::commit;
                if(edit.kind==FltkNativeEditKind::composition_cancel)operation=S::CompositionOperation::cancel;
                auto fragment=capture_native_editor_text(edit.text,edit.selection_start,edit.selection_end,direction(edit.backward));
                auto after=operation==S::CompositionOperation::cancel?*root_:
                    (begin&&edit.text.empty()?before:replace(*root_,edit));
                if(operation==S::CompositionOperation::cancel && !edit.text.empty())throw std::logic_error("Native cancellation carries text");
                observation.kind=E::Kind::composition;observation.transaction=transaction_;
                observation.authority=begin?(group?E::Authority::default_action:E::Authority::range):E::Authority::composition;
                if(begin)observation.group=group;
                observation.after=after;
                observation.data=E::CompositionData{operation,edit.text,fragment.selection,begin?std::optional{root_->selection}:std::nullopt,
                    begin&&group?sources:std::vector<std::uint64_t>{}};
                draft_=std::move(after);
                if(operation==S::CompositionOperation::commit||operation==S::CompositionOperation::cancel){root_.reset();transaction_=0;}
            }
            out.push_back(std::move(observation));
        }
        if(dead && group && !dependent)dead_groups_.push_back(*group);
        if(group && !passage.edits.empty()) {
            dead_groups_.clear();
            // The matching actual default group closes on its final dependent
            // observation, never on an unrelated later key/timestamp.
            for(auto it=out.rbegin();it!=out.rend();++it)if(it->group==group){it->group_end=true;break;}
        }
        return out;
    }
};

#if defined(_WIN32) || defined(__linux__)
namespace native_fltk_detail {
class Peer final : public std::enable_shared_from_this<Peer> {
    gui::fltk::Adapter& adapter_;
    NativeSurfaceIngress ingress_;
    std::unique_ptr<FltkNativePlatform> platform_;
    FltkNativeFrontend frontend_;
    std::optional<gui_surface::Presentation> accepted_;
    std::optional<gui_surface::EditorContext> editor_;
    FltkNativeViewport viewport_;
    std::unique_ptr<Fl_Image> installed_image_;
    double logical_width_{},logical_height_{};
    NativeSurfaceWindow window_;
    std::uint64_t capture_{},next_capture_{1};
    unsigned buttons_{};
    bool suspended_{true},closed_{},focused_{},foreground_{},focus_due_{},editor_paused_{};
    std::vector<gui_surface::KeyTransition> body_held_;
    static bool same_key(const gui_surface::KeyTransition& a,const gui_surface::KeyTransition& b) {
        return a.location==b.location && (!a.code.empty()&&!b.code.empty()?a.code==b.code:a.key==b.key);
    }
    std::int64_t width_{},height_{};
    static std::uint32_t modifiers() {
        std::uint32_t result=0;const int state=Fl::event_state();
        if(state&FL_SHIFT)result|=gui_surface::shift;
        if(state&FL_CTRL)result|=gui_surface::control;
        if(state&FL_ALT)result|=gui_surface::alt;
        if(state&FL_META)result|=gui_surface::meta;
        return result;
    }
    static unsigned actual_buttons() { return fltk_native_mouse_buttons(Fl::event_state()); }
    void fail(const std::string& reason) {
        suspend();if(ingress_.invalidate)ingress_.invalidate(gui_surface::RevocationReason::unavailable);
        throw std::runtime_error(reason);
    }
    void mouse_cancel() {
        if(capture_ && ingress_.input)ingress_.input(gui_surface::MouseTransition{1,gui_surface::MousePhase::cancel,capture_});
        buttons_=0;capture_=0;if(platform_)platform_->mouse_capture(false);
    }
    void passage(FltkNativePassage passage) {
        if(closed_||suspended_)return;
        try {
            const auto held=passage.key?std::find_if(body_held_.begin(),body_held_.end(),[&](const auto& old){return same_key(old,*passage.key);}):body_held_.end();
            if(frontend_.draft() && held==body_held_.end()) {
                for(auto& observation:frontend_.observe(std::move(passage))) {
                    if(!ingress_.editor||!ingress_.editor(std::move(observation))) {suspend();return;}
                }
            } else if(passage.key && ingress_.input) {
                const bool context=passage.key->phase==gui_surface::KeyPhase::down &&
                    (passage.key->key=="ContextMenu"||(passage.key->key=="F10"&&(passage.key->modifiers&gui_surface::shift)));
                const auto key=*passage.key;
                const auto result=ingress_.input(key);
                if(result.status==gui_surface::Status::ok) {
                    if(key.phase==gui_surface::KeyPhase::down && held==body_held_.end())body_held_.push_back(key);
                    else if(key.phase==gui_surface::KeyPhase::up && held!=body_held_.end())body_held_.erase(held);
                }
                if(context && result.status==gui_surface::Status::ok)ingress_.input(gui_surface::MouseTransition{1,gui_surface::MousePhase::context,0,0,0,0,0,0,0,0,modifiers(),gui_surface::ContextOrigin::keyboard});
            }
        } catch(const std::exception& error){fail(error.what());}
    }
    void paint(const std::function<void(int,int)>& draw) {
        if(closed_)return;
        if(!adapter_.snapshot().revision){draw(adapter_.window().w(),adapter_.window().h());return;}
        if(logical_width_<=0||logical_height_<=0)throw std::invalid_argument("Native snapshot has no logical canvas");
        if(!std::isfinite(logical_width_)||!std::isfinite(logical_height_)||logical_width_>16384||logical_height_>16384)
            throw std::length_error("Native surface canvas limit");
        const auto width=int(std::ceil(logical_width_)),height=int(std::ceil(logical_height_));
        if(width>16384||height>16384||std::uint64_t(width)*unsigned(height)>67108864)throw std::length_error("Native surface canvas limit");
        const int native_width=adapter_.window().w(),native_height=adapter_.window().h();
        const bool drawable=native_width>0&&native_height>0;
        viewport_=drawable?FltkNativeViewport::make(width,height,native_width,native_height):FltkNativeViewport{};
        std::unique_ptr<Fl_RGB_Image> image;
        auto* prior=Fl_Surface_Device::surface();
        try {
            {Fl_Image_Surface target(width,height);target.set_current();
             const auto color=adapter_.snapshot().palette.background;fl_color(color.red,color.green,color.blue);fl_rectf(0,0,width,height);
             draw(width,height);image.reset(target.image());}
            prior->set_current();
        }catch(...){prior->set_current();throw;}
        if(!image)throw std::runtime_error("Native logical render produced no image");
        std::unique_ptr<Fl_Image> scaled(drawable?image->copy(viewport_.image_width,viewport_.image_height):image.release());
        if(!scaled)throw std::runtime_error("Native logical render could not scale");
        if(drawable) {
            fl_color(FL_BLACK);fl_rectf(0,0,native_width,native_height);
            scaled->draw(int(std::lround(viewport_.x)),int(std::lround(viewport_.y)));
        }
        // Own the completed output even while a real minimized drawable has
        // zero extent. This grants no input transform or visibility assertion.
        installed_image_=std::move(scaled);
    }
    std::optional<int> event(int event) {
        if(closed_)return {};
        if(event==FL_KEYDOWN||event==FL_KEYUP||event==FL_SHORTCUT||event==FL_PASTE)return 1; // native route owns keys/IME
        if(event==FL_FOCUS||event==FL_UNFOCUS||event==FL_SHOW||event==FL_HIDE) {facts();return 1;}
        if(suspended_)return (event==FL_PUSH||event==FL_DRAG||event==FL_RELEASE||event==FL_MOVE||event==FL_MOUSEWHEEL)?std::optional<int>{1}:std::nullopt;
        if(event!=FL_PUSH&&event!=FL_DRAG&&event!=FL_RELEASE&&event!=FL_MOVE&&event!=FL_MOUSEWHEEL)return {};
        if(!(viewport_.scale>0))return 1;
        namespace S=gui_surface;
        auto [x,y]=viewport_.logical(Fl::event_x(),Fl::event_y());
        S::MouseTransition input;input.x=x;input.y=y;input.buttons=actual_buttons();input.modifiers=modifiers();
        input.capture_token=capture_;input.clicks=0;
        if(event==FL_PUSH||event==FL_RELEASE) {
            const auto button=fltk_native_mouse_button(Fl::event_button());
            if(!button)return 1;
            input.button=*button;input.phase=event==FL_PUSH?S::MousePhase::down:S::MousePhase::up;
            const auto bit=S::mouse_button_bit(input.button);
            if(event==FL_PUSH) {
                if(!capture_) {
                    if(!next_capture_||next_capture_==UINT64_MAX||!platform_->mouse_capture(true)){fail("Native pointer capture unavailable");return 1;}
                    capture_=next_capture_++;input.capture_token=capture_;
                }
                input.buttons|=bit;
            }else input.buttons&=~bit;
            input.clicks=Fl::event_clicks()>=0&&Fl::event_clicks()<3?static_cast<unsigned>(Fl::event_clicks()+1):0;
        } else if(event==FL_MOUSEWHEEL) {
            input.phase=S::MousePhase::wheel;input.wheel_x=Fl::event_dx();input.wheel_y=Fl::event_dy();
        }
        const auto result=ingress_.input?ingress_.input(input):S::AcceptResult{};
        buttons_=input.buttons;
        if(result.status!=S::Status::ok && capture_)mouse_cancel();
        else if(event==FL_RELEASE&&!buttons_){capture_=0;platform_->mouse_capture(false);}
        if(result.status==S::Status::ok&&event==FL_PUSH&&input.button==2) {
            input.phase=S::MousePhase::context;input.button=0;input.clicks=0;if(ingress_.input)ingress_.input(input);
        }
        return 1;
    }
public:
    Peer(gui::fltk::Adapter& adapter,NativeSurfaceIngress ingress):adapter_(adapter),ingress_(std::move(ingress)){}
    ~Peer(){close();}
    void stage(const NativeSurfaceWindow& window) {
        if(!std::isfinite(window.width)||!std::isfinite(window.height)||window.width<=0||window.height<=0||window.width>16384||window.height>16384)
            throw std::invalid_argument("Invalid native surface window seed");
        const auto weak=weak_from_this();
        adapter_.native_surface_hooks(
            [weak](int e)->std::optional<int>{if(auto self=weak.lock())return self->event(e);return {};},
            [weak](int,int){if(auto self=weak.lock()){self->suspend();if(self->ingress_.invalidate)self->ingress_.invalidate(gui_surface::RevocationReason::replaced);self->facts();}},
            [weak](const std::function<void(int,int)>& draw){if(auto self=weak.lock())self->paint(draw);});
        window_=window;
        adapter_.prepare_native_surface(window.title,int(std::ceil(window.width)),int(std::ceil(window.height)));
        platform_=std::make_unique<FltkNativePlatform>(adapter_.window(),FltkNativePlatformCallbacks{
            [weak]()->std::optional<gui_editor::TextObservation>{if(auto self=weak.lock())return self->frontend_.draft();return {};},
            [weak](FltkNativePassage value){if(auto self=weak.lock())self->passage(std::move(value));},
            [weak](std::string error){if(auto self=weak.lock())self->fail(error);}});
        if(!platform_->ready())throw std::runtime_error("Native physical keyboard hooks are unavailable");
    }
    bool ready()const noexcept{return !closed_&&platform_&&platform_->ready()&&adapter_.window().shown();}
    bool editor_supported()const noexcept{return platform_&&platform_->editor_supported();}
    NativeRenderReceipt present(gui::Snapshot snapshot) {
        if(!ready())return {};
        snapshot=prepare_native_blank_canvas(std::move(snapshot),window_);
        logical_width_=snapshot.client_size.width;logical_height_=snapshot.client_size.height;
        const auto revision=snapshot.revision;
        adapter_.present(std::move(snapshot));adapter_.sync();adapter_.native_surface_draw_now();Fl::flush();
        if(!adapter_.error().empty())throw std::runtime_error(adapter_.error());
        if(adapter_.native_surface_drawn_revision()!=revision)return {};
        return {revision};
    }
    void editor(const NativeEditorPresentation& view) {
        if(view.surface && (!accepted_ || accepted_->identity.owner!=view.surface->identity.owner ||
            accepted_->identity.generation!=view.surface->identity.generation || accepted_->identity.epoch!=view.surface->identity.epoch ||
            accepted_->identity.context!=view.surface->identity.context))focus_due_=true;
        accepted_=view.surface;editor_=view.context;
        if(view.admission==NativeEditorAdmission::paused) {
            if(!view.passage_basis||!view.draft)throw std::logic_error("Paused native editor has no owned passage correlation");
            frontend_.install(view.draft,true);editor_paused_=true;
            // OS callbacks stay bounded and value-only. Core's sole Capture
            // collector owns them while paused and submits none until an exact
            // unchanged checked basis resumes. Never reset a live XIC/HIMC.
            return;
        }
        if(view.admission==NativeEditorAdmission::withdrawn || !view.publication||!view.publication->basis||!view.context||!view.context->editable||!view.draft) {
            editor_paused_=false;frontend_.clear();platform_->editor({});return;
        }
        if(!accepted_||!(viewport_.scale>0))throw std::logic_error("Native editor has no rendered transform");
        const bool preserve=view.preserve_passage||editor_paused_;
        if(editor_paused_)focus_due_=true; // actual checked restoration, not an active repaint
        frontend_.install(view.draft,preserve);
        platform_->editor(FltkNativeEditorConfiguration{*view.draft,viewport_.caret(view.context->caret,accepted_->clip),preserve});
        editor_paused_=false;
    }
    void facts() {
        if(!platform_)return;
        const auto value=platform_->window_facts();
        if(width_!=value.drawable_width||height_!=value.drawable_height){width_=value.drawable_width;height_=value.drawable_height;if(ingress_.drawable_pixels)ingress_.drawable_pixels(width_,height_);}
        const bool foreground=value.foreground&&value.shown;
        if(foreground_!=foreground){foreground_=foreground;if(ingress_.foreground)ingress_.foreground(foreground);}
        if(editor_paused_ && focused_ && !value.focused && ingress_.invalidate)ingress_.invalidate(gui_surface::RevocationReason::focus_loss);
        if(focused_!=value.focused||focus_due_){focused_=value.focused;if(!editor_paused_){focus_due_=false;if(ingress_.input)ingress_.input(gui_surface::FocusChange{focused_,foreground_,gui_surface::FocusCause::direct});}}
    }
    void activate(){if(closed_||!platform_)return;suspended_=false;facts();platform_->foreground(foreground_);}
    void poll(){if(platform_&&!closed_){facts();platform_->poll();}}
    void suspend(){suspended_=true;editor_paused_=false;frontend_.clear();body_held_.clear();mouse_cancel();if(platform_)platform_->suspend();}
    void close()noexcept {
        if(closed_)return;
        closed_=true;
        try{suspend();adapter_.native_surface_hooks({},{});}catch(...){}
        platform_.reset();frontend_.clear();installed_image_.reset();
    }
};
}
inline NativeSurfacePeer prepare_fltk_surface_peer(gui::fltk::Adapter& adapter,const NativeSurfaceWindow& window,NativeSurfaceIngress ingress,NativeSurfaceMode mode,std::function<void()>* poll=nullptr) {
    auto owner=std::make_shared<native_fltk_detail::Peer>(adapter,std::move(ingress));owner->stage(window);
    NativeSurfacePeer result;
    if(mode!=NativeSurfaceMode::none)result.capabilities.supported=gui_surface::feature(gui_surface::Feature::raw_keys)|gui_surface::feature(gui_surface::Feature::focus)|gui_surface::feature(gui_surface::Feature::mouse_input);
    result.capabilities.mouse_input_version=mode==NativeSurfaceMode::none?0:1;
    if(mode==NativeSurfaceMode::editor_v1 && !owner->editor_supported())throw std::runtime_error("Native editor mode requires installed native IME, surrounding and caret hooks");
    if(mode==NativeSurfaceMode::editor_v1)result.capabilities.supported|=gui_surface::feature(gui_surface::Feature::committed_text)|gui_surface::feature(gui_surface::Feature::composition)|gui_surface::feature(gui_surface::Feature::surrounding_text)|gui_surface::feature(gui_surface::Feature::selection);
    result.ready=[owner]{return owner->ready();};result.present=[owner](gui::Snapshot value){return owner->present(std::move(value));};
    result.editor=[owner](const NativeEditorPresentation& value){owner->editor(value);};result.suspend=[owner]{owner->suspend();};
    // Owner polling is outside toolkit callbacks; no provider is entered here.
    result.activate=[owner]{owner->activate();};result.close=[owner]{owner->close();};
    if(poll)*poll=[weak=std::weak_ptr(owner)]{if(auto state=weak.lock())state->poll();};
    return result;
}
#endif

} // namespace foundation::host
