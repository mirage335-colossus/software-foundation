// SPDX-License-Identifier: CC0-1.0
// Actual DOM/Editor calls; source-only. No engine header parse or runtime proof.
#include "config.h"
#include "BibNativeEditorBackend.hpp"
#include "ui/BibEngineUiOwner.hpp"
#include "native_editor_projection.hpp"
#include "NativeRawKeyDispatch.hpp"
#include "BibNativeKeyEventOutcome.hpp"
#include "BibEngineProviderRuntime.h"
#include "BibEngineProviderDocumentProjection.h"
#include "BibFoundationServiceBridge.h"
#include "BibAppResources.h"
#include "CommonVM.h"
#include "Document.h"
#include "DocumentPage.h"
#include "DocumentView.h"
#include "Editor.h"
#include "Element.h"
#include "ElementInlines.h"
#include "EventHandler.h"
#include "FocusController.h"
#include "FrameSelection.h"
#include "FrameTree.h"
#include "HTMLInputElement.h"
#include "HTMLNames.h"
#include "HTMLTextFormControlElement.h"
#include "LocalFrame.h"
#include "LocalFrameInlines.h"
#include "LocalFrameView.h"
#include "LocalFrameViewLayoutContext.h"
#include "Page.h"
#include "Position.h"
#include "PlatformKeyboardEvent.h"
#include "SimpleRange.h"
#include "Text.h"
#include "TextControlInnerElements.h"
#include "TextIterator.h"
#include "VisibleSelection.h"
#include <JavaScriptCore/JSLock.h>
#include <limits>
#include <span>
#include <stdexcept>
#include <vector>
#include <wtf/text/WTFString.h>

namespace bib::provider_candidate {
namespace {
namespace E=foundation::ui::native_editor;
namespace C=E::codec;
namespace gui_surface=foundation::gui_surface;
namespace I=foundation::appended::engine_input;
namespace K=foundation::appended::ndv2_physical;
bool same(BibEngineDocumentV1 a,BibEngineDocumentV1 b) {
    return a.application_instance==b.application_instance&&a.document_sequence==b.document_sequence&&a.service_generation==b.service_generation;
}
std::u16string units(const WTF::String& value) {
    if(value.length()>131072)throw std::length_error("Native text exceeds bounded projection");
    std::u16string result;result.reserve(value.length());
    for(unsigned i=0;i<value.length();++i)result.push_back(value[i]);return result;
}
WTF::String string(const std::string& value) {return WTF::String::fromUTF8(std::span<const char>(value.data(),value.size()));}
constexpr auto text_behavior=WebCore::TextIteratorBehavior::EmitsOriginalText;
std::optional<std::u16string> bounded_text(const WebCore::SimpleRange& scope) {
    std::u16string result;
    for(WebCore::TextIterator iterator(scope,{text_behavior});!iterator.atEnd();iterator.advance()) {
        const auto chunk=iterator.text();
        if(chunk.length()>131072-result.size())return {};
        for(unsigned i=0;i<chunk.length();++i)result.push_back(chunk[i]);
    }
    return result;
}
E::NativeResult unknown(){return {};}
}
struct NativeEditorBackend::Impl {
    struct GeometryAncestor {
        RefPtr<WebCore::LocalFrame> frame;
        RefPtr<WebCore::Document> document;
        RefPtr<WebCore::LocalFrameView> view;
        WebCore::Frame* parent{};
        const WebCore::ScrollView* parent_view{};
        std::uint64_t tree{},style_count{},layout_count{};
    };
    struct Snapshot {
        RefPtr<WebCore::Page> page;
        RefPtr<WebCore::LocalFrame> main,frame;
        RefPtr<WebCore::Document> main_document,document;
        RefPtr<WebCore::LocalFrameView> view;
        RefPtr<WebCore::Element> root;
        RefPtr<WebCore::HTMLTextFormControlElement> control;
        RefPtr<WebCore::Element> focused;
        WebCore::SimpleRange scope;
        WebCore::SimpleRange selected;
        E::NativeTextProjection text;
        E::NativeUnitRange selection;
        bool backward{};
        std::optional<WebCore::SimpleRange> composition;
        RefPtr<WebCore::Text> composition_node;
        std::uint64_t main_tree{},tree{},resource_epoch{};
        BibEngineDocumentV1 expected{};
        gui_surface::Rect caret;
        WebCore::IntRect native_caret;
        std::uint64_t style_count{},main_style_count{},layout_count{},main_layout_count{};
        std::vector<GeometryAncestor> ancestors;
    };
    struct NullSnapshot {
        RefPtr<WebCore::Page> page;
        RefPtr<WebCore::LocalFrame> main,frame;
        RefPtr<WebCore::Document> main_document,document;
        RefPtr<WebCore::LocalFrameView> view;
        RefPtr<WebCore::Element> focused;
        std::uint64_t resource_epoch{},main_tree{},tree{};
        BibEngineDocumentV1 expected{};
        bool active{},focused_window{};
        std::optional<WebCore::SimpleRange> selected,composition;
        RefPtr<WebCore::Text> composition_node;
        RefPtr<WebCore::HTMLTextFormControlElement> control;
        WTF::String control_value;
        std::uint32_t selection_begin{},selection_end{};
        bool backward{};
        std::uint64_t style_count{},main_style_count{};
    };
    struct Mapping {std::uint64_t id{},context{},frame_id{},revision{};Snapshot native;E::NativeProjection value;};
    struct Authority {Impl& owner;Mapping& mapping;std::uint64_t sequence;};
    const std::uint64_t worker,application;
    const NativeEditorHooks hooks;
    std::optional<Mapping> live;
    std::uint64_t next_mapping=1,next_frame=1,next_revision=1,next_retire=1;
    std::uint64_t transport_composition{};
    bool poisoned{},applying{},projecting{},invalidated{};
    struct Applying { Impl& owner; explicit Applying(Impl& value):owner(value){owner.applying=true;} ~Applying(){owner.applying=false;} };
    struct Projecting { Impl& owner; explicit Projecting(Impl& value):owner(value){owner.projecting=true;} ~Projecting(){owner.projecting=false;} };
    Impl(std::uint64_t w,std::uint64_t a,NativeEditorHooks h):worker(w),application(a),hooks(std::move(h)){
        if(!worker||!application||!hooks.on_owner||!hooks.callback_faulted||!hooks.queue_wake||
            !hooks.invalidate_form_authority||!hooks.physical_authority||!hooks.surface_identity||!hooks.on_owner(hooks.context))
            throw std::invalid_argument("Native editor requires one retained owner and exact projection hooks");
    }
    bool ready()const noexcept{return hooks.on_owner(hooks.context)&&!poisoned&&!hooks.callback_faulted(hooks.context)&&!BIB::EngineUI::faulted();}
    static std::uint64_t spend(std::uint64_t& next){
        if(!next)throw std::overflow_error("Native editor identity exhausted");
        auto value=next;next=next==UINT64_MAX?0:next+1;return value;
    }
    bool fence(const Snapshot& s)const noexcept{
        if(!ready()||BIB::EngineUI::modal())return false;
        BibAppDocumentIdentityV1 id{};id.size=sizeof(id);id.version=BIB_APP_DOCUMENT_IDENTITY_VERSION;
        return bib_app_resources_current_identity(&id)==1&&id.resource_epoch==s.resource_epoch&&
            same(BIB::bibProviderProjectDocument(id),s.expected)&&s.expected.application_instance==application&&
            BIB::bibProviderPage()==s.page.get()&&BIB::bibProviderDocumentMainFrame().get()==s.main.get()&&
            s.main->document()==s.main_document.get()&&s.frame->page()==s.page.get()&&s.frame->document()==s.document.get()&&
            s.frame->view()==s.view.get()&&s.root->isConnected()&&s.document->focusedElement()==s.focused.get()&&s.page->focusController().focusedOrMainFrame()==s.frame.get();
    }
    // Pure retained state checks after natural JSLock/Bridge unwind. No layout,
    // author dispatch or replacement target is fetched to repair a moved range.
    bool stable_after_unwind(const Snapshot& s)const{
        if(!fence(s)||s.main_document->domTreeVersion()!=s.main_tree||s.document->domTreeVersion()!=s.tree)return false;
        if((!s.control&&s.frame->selection().selection().range()!=std::optional{s.selected})||
           s.frame->editor().compositionRange()!=s.composition||s.frame->editor().compositionNode()!=s.composition_node.get())return false;
        if(s.control){
            if(units(s.control->value().get())!=s.text.native()||s.control->selectionStart()!=s.selection.begin||
               s.control->selectionEnd()!=s.selection.end||
               (s.control->selectionDirection()=="backward"_s)!=s.backward)return false;
        }else if(s.frame->selection().selection().rootEditableElement()!=s.root.get()||
            (!s.frame->selection().selection().isBaseFirst())!=s.backward)return false;
        // No layout/style/selection update is invoked after the final natural
        // Bridge unwind. Recheck the versions and pure cached coordinate map.
        auto* main_view=s.main->view();
        if(!main_view||s.document->needsStyleRecalc()||s.main_document->needsStyleRecalc()||s.view->needsLayout()||main_view->needsLayout()||
            s.document->styleRecalcCount()!=s.style_count||s.main_document->styleRecalcCount()!=s.main_style_count||
            s.view->layoutContext().layoutUpdateCount()!=s.layout_count||main_view->layoutContext().layoutUpdateCount()!=s.main_layout_count)return false;
        if(!stable_ancestors(s))return false;
        const auto caret=s.view->contentsToRootView(s.native_caret);
        return s.caret==gui_surface::Rect{static_cast<double>(caret.x()),static_cast<double>(caret.y()),static_cast<double>(caret.width()),static_cast<double>(caret.height())};
    }
    bool retain_ancestors(Snapshot& snapshot) {
        // contentsToRootView follows every intermediate iframe renderer/view.
        // Retain that exact chain; an unknown/remote/cyclic or oversized chain
        // is unavailable, never silently validated by only its two endpoints.
        RefPtr current=snapshot.frame;
        for(unsigned depth=0;depth<32&&current;++depth){
            RefPtr document=current->document();RefPtr view=current->view();
            if(!document||!view||current->page()!=snapshot.page.get()||document->needsStyleRecalc()||view->needsLayout())return false;
            auto* parent=current->tree().parent();
            snapshot.ancestors.push_back({current,document,view,parent,view->parent(),document->domTreeVersion(),
                document->styleRecalcCount(),view->layoutContext().layoutUpdateCount()});
            if(current==snapshot.main)return !parent&&!view->parent();
            auto* parent_frame=parent?dynamicDowncast<WebCore::LocalFrame>(*parent):nullptr;
            // The geometry conversion follows Widget parents, which may differ
            // from FrameTree during hierarchy-update suspension. Never read an
            // unretained intermediate ScrollView through that mismatch.
            if(!parent_frame||view->parent()!=parent_frame->view())return false;
            current=parent_frame;
        }
        return false;
    }
    bool stable_ancestors(const Snapshot& snapshot)const noexcept {
        if(snapshot.ancestors.empty()||snapshot.ancestors.front().frame!=snapshot.frame||snapshot.ancestors.back().frame!=snapshot.main)return false;
        for(const auto& item:snapshot.ancestors){
            if(item.frame->document()!=item.document.get()||item.frame->view()!=item.view.get()||item.frame->page()!=snapshot.page.get()||
                item.frame->tree().parent()!=item.parent||item.view->parent()!=item.parent_view||
                item.document->domTreeVersion()!=item.tree||item.document->needsStyleRecalc()||item.view->needsLayout()||
                item.document->styleRecalcCount()!=item.style_count||item.view->layoutContext().layoutUpdateCount()!=item.layout_count)return false;
        }
        return true;
    }
    std::optional<Snapshot> capture_locked(E::NativeAvailability* null_state=nullptr,bool* checked=nullptr,std::optional<NullSnapshot>* null_sample=nullptr){
        if(checked)*checked=false;
        if(null_state)*null_state=E::NativeAvailability::unavailable;
        if(!ready())return {};
        RefPtr page=BIB::bibProviderPage();RefPtr main=BIB::bibProviderDocumentMainFrame();
        RefPtr main_document=main?main->document():nullptr;
        RefPtr frame=page?page->focusController().focusedOrMainFrame():nullptr;
        RefPtr document=frame?frame->document():nullptr;RefPtr view=frame?frame->view():nullptr;
        BibAppDocumentIdentityV1 id{};id.size=sizeof(id);id.version=BIB_APP_DOCUMENT_IDENTITY_VERSION;
        if(!page||!main||!main_document||main->page()!=page||!frame||!document||!view||frame->page()!=page||
           bib_app_resources_current_identity(&id)!=1||!id.resource_epoch||id.application_instance!=application)return {};
        if(null_sample)*null_sample=NullSnapshot{page,main,frame,main_document,document,view,document->focusedElement(),
            id.resource_epoch,main_document->domTreeVersion(),document->domTreeVersion(),BIB::bibProviderProjectDocument(id),
            page->focusController().isActive(),page->focusController().isFocused()};
        if(null_sample&&*null_sample){(**null_sample).style_count=document->styleRecalcCount();(**null_sample).main_style_count=main_document->styleRecalcCount();}
        if(checked)*checked=true;
        if(null_state)*null_state=E::NativeAvailability::noneditable;
        const auto& selection=frame->selection().selection();auto selected=selection.range();
        if(null_sample&&*null_sample){
            auto& witness=**null_sample;witness.selected=selected;witness.backward=!selection.isBaseFirst();
            witness.composition=frame->editor().compositionRange();witness.composition_node=frame->editor().compositionNode();
        }
        // Keep the full original null witness; modal UI changes no native focus or composition.
        if(BIB::EngineUI::modal()){if(null_state)*null_state=E::NativeAvailability::unavailable;return {};}
        if(!page->focusController().isActive()||!page->focusController().isFocused()||selection.isInPasswordField())return {};
        RefPtr focused=document->focusedElement();
        RefPtr control=focused?dynamicDowncast<WebCore::HTMLTextFormControlElement>(*focused):nullptr;
        RefPtr<WebCore::Element> root;
        std::u16string raw;
        E::NativeUnitRange native_selection;
        bool backward=!selection.isBaseFirst();
        if(control){
            if(control->isDisabledFormControl()||control->hasAttributeWithoutSynchronization(WebCore::HTMLNames::readonlyAttr)||!control->isInnerTextElementEditable())return {};
            if(auto* input=dynamicDowncast<WebCore::HTMLInputElement>(*control);input&&(!input->isTextField()||input->isSecureField()))return {};
            root=control->innerTextElement();if(!root)return {};
            WTF::String value=control->value().get();
            if(null_sample&&*null_sample){
                auto& witness=**null_sample;witness.control=control;witness.control_value=value;
                witness.selection_begin=control->selectionStart();witness.selection_end=control->selectionEnd();
                witness.backward=control->selectionDirection()=="backward"_s;
            }
            if(value.length()>131072){if(null_state)*null_state=E::NativeAvailability::unavailable;return {};}
            raw=units(value);native_selection={control->selectionStart(),control->selectionEnd()};
            backward=control->selectionDirection()=="backward"_s;
        }else{
            root=selection.protectedRootEditableElement();if(!root||!selection.hasEditableStyle())return {};
        }
        auto scope=WebCore::makeRangeSelectingNodeContents(*root);
        if(control)selected=WebCore::resolveCharacterRange(scope,{native_selection.begin,native_selection.end-native_selection.begin},{text_behavior});
        if(!selected||!WebCore::contains(scope,*selected))return {};
        if(!control){
            auto extracted=bounded_text(scope);if(!extracted){if(null_state)*null_state=E::NativeAvailability::unavailable;return {};}raw=std::move(*extracted);
            const auto range=WebCore::characterRange(scope,*selected,{text_behavior});
            if(range.location>UINT32_MAX||range.length>UINT32_MAX-range.location)return {};
            native_selection={static_cast<std::uint32_t>(range.location),static_cast<std::uint32_t>(range.location+range.length)};
        }
        auto text=E::NativeTextProjection::create(raw);if(!text||!text->projected_range(native_selection)){if(null_state)*null_state=E::NativeAvailability::unavailable;return {};}
        auto composition=frame->editor().compositionRange();
        if(composition&&(!transport_composition||!WebCore::contains(scope,*composition))){if(null_state)*null_state=E::NativeAvailability::unavailable;return {};}
        Snapshot result{page,main,frame,main_document,document,view,root,control,focused,scope,*selected,std::move(*text),native_selection,backward,
            composition,frame->editor().compositionNode(),main_document->domTreeVersion(),document->domTreeVersion(),id.resource_epoch,BIB::bibProviderProjectDocument(id)};
        // absoluteCaretBounds can update layout/style. It belongs exclusively to
        // this Bridge-before-JSLock admitted read, never post-unwind validation.
        result.native_caret=frame->selection().absoluteCaretBounds();
        const auto caret=view->contentsToRootView(result.native_caret);
        result.style_count=document->styleRecalcCount();result.main_style_count=main_document->styleRecalcCount();
        result.layout_count=view->layoutContext().layoutUpdateCount();
        if(!main->view())return {};
        result.main_layout_count=main->view()->layoutContext().layoutUpdateCount();
        if(!retain_ancestors(result)){if(checked)*checked=false;return {};}
        result.caret={static_cast<double>(caret.x()),static_cast<double>(caret.y()),static_cast<double>(caret.width()),static_cast<double>(caret.height())};
        if(!fence(result))return {};return result;
    }
    bool stable_null(const NullSnapshot& s)const noexcept {
        if(!ready())return false;
        BibAppDocumentIdentityV1 id{};id.size=sizeof(id);id.version=BIB_APP_DOCUMENT_IDENTITY_VERSION;
        // LocalFrame::selection() dereferences its CURRENT document. Validate
        // the original frame/document identity before any such getter.
        if(bib_app_resources_current_identity(&id)!=1||id.resource_epoch!=s.resource_epoch||!same(BIB::bibProviderProjectDocument(id),s.expected)||
            BIB::bibProviderPage()!=s.page.get()||BIB::bibProviderDocumentMainFrame().get()!=s.main.get()||
            s.main->document()!=s.main_document.get()||s.frame->document()!=s.document.get()||s.frame->page()!=s.page.get()||
            s.frame->view()!=s.view.get()||s.document->focusedElement()!=s.focused.get()||
            s.main_document->domTreeVersion()!=s.main_tree||s.document->domTreeVersion()!=s.tree||
            s.page->focusController().focusedOrMainFrame()!=s.frame.get()||
            s.page->focusController().isActive()!=s.active||s.page->focusController().isFocused()!=s.focused_window||
            s.document->needsStyleRecalc()||s.main_document->needsStyleRecalc()||
            s.document->styleRecalcCount()!=s.style_count||s.main_document->styleRecalcCount()!=s.main_style_count)return false;
        if(s.frame->selection().selection().range()!=s.selected||s.frame->editor().compositionRange()!=s.composition||
            s.frame->editor().compositionNode()!=s.composition_node.get())return false;
        if(s.control){
            // WTF::String retains the existing DOM value without serializing an
            // oversized control. Replaced equal values fail conservatively.
            if(s.control->value().get().impl()!=s.control_value.impl()||s.control->selectionStart()!=s.selection_begin||
                s.control->selectionEnd()!=s.selection_end||(s.control->selectionDirection()=="backward"_s)!=s.backward)return false;
        }else if((!s.frame->selection().selection().isBaseFirst())!=s.backward)return false;
        return true;
    }
    std::optional<Snapshot> capture(E::NativeAvailability* null_state=nullptr,bool* checked=nullptr){
        const auto modal_epoch=BIB::EngineUI::modalEpoch();
        const bool modal=BIB::EngineUI::modal();
        BIB::FoundationServiceEngineCall bridge;if(!bridge)return {};
        std::optional<Snapshot> result;std::optional<NullSnapshot> null_sample;
        {JSC::JSLockHolder lock(WebCore::commonVM());result=capture_locked(null_state,checked,&null_sample);}
        bridge.finish();
        // An open/close cycle also invalidates this read, even if the final state is equal.
        if(!ready()||BIB::EngineUI::modalEpoch()!=modal_epoch||BIB::EngineUI::modal()!=modal){if(checked)*checked=false;return {};}
        if(!result){if(checked&&(!null_sample||!stable_null(*null_sample)))*checked=false;return {};}
        if(!stable_after_unwind(*result)){if(checked)*checked=false;return {};}return result;
    }
    static bool same_native(const Snapshot& a,const Snapshot& b){
        return a.page==b.page&&a.main==b.main&&a.main_document==b.main_document&&a.frame==b.frame&&a.document==b.document&&
            a.view==b.view&&a.root==b.root&&a.control==b.control&&a.focused==b.focused&&a.caret==b.caret&&a.scope==b.scope&&a.selected==b.selected&&
            a.text==b.text&&a.selection==b.selection&&a.backward==b.backward&&a.composition==b.composition&&
            a.composition_node==b.composition_node&&a.main_tree==b.main_tree&&a.tree==b.tree&&
            a.resource_epoch==b.resource_epoch&&same(a.expected,b.expected);
    }
    std::optional<E::NativeProjection> accept(Snapshot snapshot,std::uint64_t retained_frame=0){
        if(!ready()||BIB::EngineUI::modal())return {};
        const bool same_target=live&&live->native.frame==snapshot.frame&&live->native.document==snapshot.document&&
            live->native.root==snapshot.root&&live->native.resource_epoch==snapshot.resource_epoch&&same(live->native.expected,snapshot.expected);
        const bool identical=live&&same_native(live->native,snapshot);
        std::uint64_t context{};
        if(!hooks.physical_authority(hooks.context,&snapshot.expected,&context)||!context)return {};
        // A new root cannot silently replace an unretired provider lease.
        if(live&&(!same_target||invalidated||live->context!=context))return {};
        auto identity=hooks.surface_identity(context);if(!identity||identity->context!=context)return {};
        auto selection=snapshot.text.projected_range(snapshot.selection);if(!selection)return {};
        E::NativeProjection value{*identity,identical?live->revision:spend(next_revision),snapshot.text.utf8(),*selection,snapshot.backward,
            snapshot.composition?transport_composition:0,identical?live->id:spend(next_mapping),
            retained_frame?retained_frame:(live&&live->native.frame==snapshot.frame?live->frame_id:spend(next_frame)),true};
        value.caret=snapshot.caret;value.editable=true;
        value.retire=E::NativeRetireMaterial{live?live->value.retire->token:spend(next_retire),value.mapping_id,context,value.composition};
        if(!C::valid_native_projection_shape(value))return {};
        live=Mapping{value.mapping_id,context,value.frame_id,value.editor_revision,std::move(snapshot),value};invalidated=false;return value;
    }
    std::optional<E::NativeProjection> project(std::uint64_t mapping){
        if(!ready()||applying||projecting||invalidated)return {};
        Projecting activity(*this);
        auto snapshot=capture();if(!snapshot)return {};
        if(mapping&&(!live||mapping!=live->id||!same_native(live->native,*snapshot)))return {};
        return accept(std::move(*snapshot));
    }
    bool target(const C::WireTarget& value,const BibEngineDocumentV1& expected)const noexcept {
        return ready()&&value.worker_epoch==worker&&value.application_instance==application&&
            value.document_sequence==expected.document_sequence&&value.service_generation==expected.service_generation&&
            value.request_sequence&&value.request_sequence!=UINT64_MAX;
    }
    bool retirement_absent(const Mapping& mapping)const {
        const auto& s=mapping.native;
        // These are actual retained native objects, never a replacement frame.
        // A replaced original document no longer owns this frame editor. A merely
        // detached node is insufficient: otherwise require actual composition absence.
        if(s.frame->document()!=s.document.get())return true;
        return !s.frame->editor().hasComposition()&&!s.frame->editor().compositionRange();
    }
    static bool same_surface_context(const E::Identity& a,const E::Identity& b)noexcept {
        return a.owner==b.owner&&a.generation==b.generation&&a.epoch==b.epoch&&a.context==b.context;
    }
    bool admit(const C::ProjectionQuery& request)const noexcept {
        const BibEngineDocumentV1 expected{application,request.target.document_sequence,request.target.service_generation};
        std::uint64_t context{};
        return target(request.target,expected)&&C::valid_projection_query_shape(request)&&
            hooks.physical_authority(hooks.context,&expected,&context)&&context==request.identity.context&&
            (!request.mapping_id||(live&&!invalidated&&live->id==request.mapping_id));
    }
    bool admit(const C::NativeRequestEnvelope& request)const noexcept {
        if(!live||invalidated||!target(request.target,live->native.expected)||BIB::EngineUI::modal()||!C::valid_native_request_shape(request))return false;
        std::uint64_t context{};
        return request.request.resolved==live->value&&hooks.physical_authority(hooks.context,&live->native.expected,&context)&&context==live->context;
    }
    bool admit(const C::RevocationEnvelope& request)const noexcept {
        return live&&target(request.target,live->native.expected)&&C::valid_revocation_shape(request)&&
            live->value.retire&&request.request.material==*live->value.retire&&same_surface_context(request.request.identity,live->value.identity);
    }
    C::ProjectionReply query(const C::ProjectionQuery& request) {
        C::ProjectionReply reply;reply.target=request.target;reply.identity=request.identity;
        if(!admit(request)||applying||projecting)return reply;
        Projecting activity(*this);
        E::NativeAvailability availability{};bool checked=false;
        auto snapshot=capture(&availability,&checked);
        if(!checked||!admit(request))return reply;
        if(snapshot&&!invalidated&&(!request.mapping_id||(live&&same_native(live->native,*snapshot))))reply.projection=accept(std::move(*snapshot));
        reply.state=reply.projection?C::ProjectionReply::State::available:
            availability==E::NativeAvailability::noneditable&&!snapshot?C::ProjectionReply::State::noneditable:C::ProjectionReply::State::unavailable;
        reply.observation_revision=spend(next_revision);reply.readback_attested=true;
        if(reply.projection)reply.identity=reply.projection->identity;
        return reply;
    }
    static bool authority(void* raw,const WebCore::LocalFrame& frame,const BibEngineDocumentV1& expected,std::uint64_t context,std::uint64_t sequence)noexcept{
        auto& a=*static_cast<Authority*>(raw);std::uint64_t physical{};
        return a.owner.ready()&&!BIB::EngineUI::modal()&&!a.owner.invalidated&&a.owner.hooks.physical_authority(a.owner.hooks.context,&expected,&physical)&&physical==context&&a.sequence==sequence&&a.mapping.context==context&&
            a.mapping.native.frame.get()==&frame&&same(a.mapping.native.expected,expected)&&a.owner.fence(a.mapping.native);
    }
    bool set_selection(Mapping& mapping,gui_surface::ByteRange bytes,bool backward){
        auto range=mapping.native.text.native_range(bytes);if(!range)return false;
        auto& s=mapping.native;if(!fence(s))return false;
        std::optional<WebCore::SimpleRange> expected_range;
        const bool unchanged=bytes==mapping.value.selection&&backward==s.backward;
        if(s.control){
            if(!unchanged)s.control->setSelectionRange(range->begin,range->end,backward?WebCore::SelectionHasBackwardDirection:WebCore::SelectionHasForwardDirection);
        }else{
            // An unchanged projected caret can denote different DOM insertion
            // sides/styles at adjacent text runs. Preserve its exact owned
            // native boundary; resolve only a genuinely new selection intent.
            if(unchanged)expected_range=s.selected; // Preserve original caret affinity, insertion side and directionality.
            else {
                auto resolved=WebCore::resolveCharacterRange(s.scope,{range->begin,range->end-range->begin},{text_behavior});
                if(WebCore::characterRange(s.scope,resolved,{text_behavior})!=WebCore::CharacterRange{range->begin,range->end-range->begin})return false;
                auto begin=WebCore::makeContainerOffsetPosition(resolved.start),end=WebCore::makeContainerOffsetPosition(resolved.end);
                WebCore::VisibleSelection selection(backward?end:begin,backward?begin:end,WebCore::Affinity::Downstream,WebCore::Directionality::Strong);
                expected_range=resolved;s.frame->selection().setSelection(selection);
            }
        }
        if(!fence(s)||s.document->domTreeVersion()!=s.tree||s.main_document->domTreeVersion()!=s.main_tree||
            s.frame->editor().compositionRange()!=s.composition||s.frame->editor().compositionNode()!=s.composition_node.get())return false;
        if(s.control)return s.document->focusedElement()==s.control.get()&&units(s.control->value().get())==s.text.native()&&
            s.control->selectionStart()==range->begin&&s.control->selectionEnd()==range->end&&
            (s.control->selectionDirection()=="backward"_s)==backward;
        auto actual=s.frame->selection().selection().range();
        return actual==expected_range&&s.frame->selection().selection().rootEditableElement()==s.root.get()&&
            (!s.frame->selection().selection().isBaseFirst())==backward;
    }
    static std::uint32_t actual_modifiers() {
        using M=WebCore::PlatformEvent::Modifier;
        const auto state=WebCore::PlatformKeyboardEvent::currentStateOfModifierKeys();
        return (state.contains(M::ShiftKey)?1u:0u)|(state.contains(M::ControlKey)?2u:0u)|
            (state.contains(M::AltKey)?4u:0u)|(state.contains(M::MetaKey)?8u:0u)|(state.contains(M::AltGraphKey)?16u:0u);
    }
    E::NativeResult apply(const E::NativeRequest& request,std::uint64_t provider_sequence){
        if(!ready()||BIB::EngineUI::modal()||applying||projecting||invalidated||!provider_sequence||provider_sequence==UINT64_MAX||!live||request.resolved!=live->value)return unknown();
        // No native Char exists for empty insertion. Reject it with a checked
        // actual projection before effects, rather than relabeling Delete as
        // insertReplacementText or entering a Char precondition assertion.
        if(auto* data=std::get_if<E::TextData>(&request.packet.observation.data);data&&data->text.empty()&&data->replacement.begin==data->replacement.end){
            auto checked=project(request.resolved.mapping_id);E::NativeResult result;
            result.outcome=checked?E::Outcome::rejected:E::Outcome::unknown;result.projection=std::move(checked);
            if(result.projection){result.retire=result.projection->retire;result.observation_revision=result.projection->editor_revision;result.readback_identity=result.projection->identity;result.readback_attested=true;}
            return result;
        }
        Applying activity(*this);
        try{
            auto& mapping=*live;const auto before_frame=mapping.native.frame;const auto before_root=mapping.native.root;
            const auto original_material=*mapping.value.retire;const auto original_identity=mapping.value.identity;
            const auto before_frame_id=mapping.frame_id;
            WebCore::KeyEventDispatchOutcome key_outcome;
            bool key=false,text=false,composition=false,known_cancelled=false;
            const auto& observation=request.packet.observation;
            {
                BIB::FoundationServiceEngineCall bridge;if(!bridge){return unknown();}
                {
                    JSC::JSLockHolder lock(WebCore::commonVM());auto current=capture_locked();
                    if(!current||!same_native(mapping.native,*current)){return unknown();}
                    hooks.invalidate_form_authority(hooks.context);
                    if(!ready()||BIB::EngineUI::modal()){poisoned=true;return unknown();}
                    if(auto* data=std::get_if<E::KeyData>(&observation.data)){
                        key=true;const auto& k=data->transition;
                        I::Key input;input.phase=k.phase==gui_surface::KeyPhase::up;input.location=k.location;
                        input.modifiers=k.modifiers;input.repeat=k.repeat;input.input_context=mapping.context;input.key=k.key;input.code=k.code;
                        Authority guard{*this,mapping,provider_sequence};
                        (void)K::dispatchKeyWithOutcome(*mapping.native.frame,input,mapping.native.expected,provider_sequence,authority,&guard,key_outcome);
                    }else if(auto* data=std::get_if<E::SelectionData>(&observation.data)){
                        if(!set_selection(mapping,data->selection,data->backward)){poisoned=true;return unknown();}
                    }else if(auto* data=std::get_if<E::TextData>(&observation.data)){
                        text=!data->text.empty();const auto replacement=observation.authority==E::Authority::default_action?request.resolved.selection:data->replacement;
                        if(!set_selection(mapping,replacement,request.resolved.backward)){poisoned=true;return unknown();}
                        if(data->text.empty())mapping.native.frame->editor().deleteSelectionWithSmartDelete(false);
                        else {
                            Authority guard{*this,mapping,provider_sequence};K::NativeTextInput input{data->text,mapping.context,actual_modifiers()};
                            (void)K::dispatchTextWithOutcome(*mapping.native.frame,input,mapping.native.expected,provider_sequence,authority,&guard,key_outcome);
                        }
                    }else{
                        composition=true;const auto& composition_data=std::get<E::CompositionData>(observation.data);auto& editor=mapping.native.frame->editor();
                        auto native_text=string(composition_data.text);auto text_map=E::NativeTextProjection::create(units(native_text));
                        auto selection=text_map?text_map->native_range(composition_data.selection):std::nullopt;
                        if(!text_map||!selection){poisoned=true;return unknown();}
                        if(composition_data.operation==gui_surface::CompositionOperation::begin){
                            if(transport_composition||editor.hasComposition()){poisoned=true;return unknown();}
                            const auto replacement=observation.authority==E::Authority::default_action?request.resolved.selection:composition_data.replacement.value_or(request.resolved.selection);
                            if(!set_selection(mapping,replacement,request.resolved.backward)){poisoned=true;return unknown();}
                            transport_composition=observation.transaction;
                            // Empty begin is real pending metadata, not native setComposition(empty),
                            // which would delete the currently selected native text.
                            if(!composition_data.text.empty())editor.setComposition(native_text,{},{},{},selection->begin,selection->end);
                        }else{
                            if(transport_composition!=observation.transaction){poisoned=true;return unknown();}
                            if(composition_data.operation==gui_surface::CompositionOperation::update)
                                editor.setComposition(native_text,{},{},{},selection->begin,selection->end);
                            else if(composition_data.operation==gui_surface::CompositionOperation::cancel){
                                if(editor.hasComposition())editor.cancelComposition();
                                transport_composition=0;
                            }else{
                                // Native confirmComposition handles a genuinely
                                // pending/no-native-composition commit directly.
                                // Never seed author-visible composition then run
                                // a second default after that seed was cancelled.
                                editor.confirmComposition(native_text);transport_composition=0;
                            }
                        }
                    }
                }
                bridge.finish(); // Final native microtasks precede readback.
            }
            if(!ready()){poisoned=true;return unknown();}
            E::NativeAvailability null_state{};bool checked=false;
            auto after=capture(&null_state,&checked);
            if(!after){
                if(!checked){poisoned=true;return unknown();}
                E::NativeResult result;result.outcome=E::Outcome::cancelled;result.continuity=E::Continuity::replaced;
                result.availability=null_state;result.observation_revision=spend(next_revision);result.readback_identity=original_identity;result.readback_attested=true;
                // Only direct actual absence of the original native composition
                // proves its lease already retired; otherwise retain it for 9.
                if(retirement_absent(mapping)){result.retired=original_material;live.reset();transport_composition=0;K::clearRawKeyModifiers();}
                else invalidated=true;
                if(result.retired==original_material&&original_material.composition){
                    result.composition_readback_attested=true;
                    result.composition=E::CompositionFact{original_material.composition,E::CompositionState::ended};
                }else if(composition){result.composition_readback_attested=true;result.composition=E::CompositionFact{observation.transaction,E::CompositionState::ended};}
                hooks.queue_wake(hooks.context);return ready()?result:unknown();
            }
            if(composition&&transport_composition&&!after->composition){
                const auto& data=std::get<E::CompositionData>(observation.data);
                if(!data.text.empty())known_cancelled=true;
            }
            const bool same_frame=after->frame==before_frame;
            const bool retarget=after->root!=before_root||after->frame!=before_frame;
            std::optional<E::NativeRetireMaterial> retired;
            if(retarget){
                if(!retirement_absent(mapping)){poisoned=true;return unknown();}
                retired=original_material;live.reset();transport_composition=0;K::clearRawKeyModifiers();
            }
            auto projection=accept(std::move(*after),same_frame?before_frame_id:0);
            if(!projection){
                if(!retired){poisoned=true;return unknown();}
                // Navigation can retire the exact old authority while a new
                // physical context is not committed yet. No replacement intent
                // or range is manufactured for the new document.
                E::NativeResult result;result.outcome=E::Outcome::cancelled;result.continuity=E::Continuity::replaced;
                result.availability=E::NativeAvailability::unavailable;result.observation_revision=spend(next_revision);
                result.readback_identity=original_identity;result.readback_attested=true;result.retired=retired;
                if(result.retired==original_material&&original_material.composition){
                    result.composition_readback_attested=true;
                    result.composition=E::CompositionFact{original_material.composition,E::CompositionState::ended};
                }else if(composition){result.composition_readback_attested=true;result.composition=E::CompositionFact{observation.transaction,E::CompositionState::ended};}
                hooks.queue_wake(hooks.context);return ready()?result:unknown();
            }
            E::NativeResult result;result.outcome=known_cancelled?E::Outcome::cancelled:E::Outcome::applied;result.projection=*projection;result.retire=projection->retire;result.retired=retired;
            result.observation_revision=projection->editor_revision;result.readback_identity=projection->identity;result.readback_attested=true;
            if(key||text){
                const auto& stage=key?(std::get<E::KeyData>(observation.data).transition.phase==gui_surface::KeyPhase::down?key_outcome.keydown:key_outcome.standalone):key_outcome.standalone;
                using O=WebCore::KeyEventDispatchOutcome;
                result.key_dispatch_attested=key_outcome.complete&&stage.defaultPrevented!=O::Flag::Unobserved&&stage.defaultHandled!=O::Flag::Unobserved;
                result.default_prevented=stage.defaultPrevented==O::Flag::Yes;result.default_handled=stage.defaultHandled==O::Flag::Yes;
                result.changed_focused_frame=!same_frame||stage.frame!=O::Frame::SameFrameAndDocument;
                if(!result.key_dispatch_attested){poisoned=true;return unknown();}
                if(result.default_prevented)result.outcome=E::Outcome::cancelled;
                result.allow_default=key&&std::get<E::KeyData>(observation.data).transition.phase==gui_surface::KeyPhase::down&&
                    !result.default_prevented&&!result.default_handled&&!result.changed_focused_frame&&!key_outcome.inputMethodHandled;
                result.key_retarget_attested=retarget&&same_frame&&result.allow_default;
            }
            result.continuity=retarget?(result.key_retarget_attested?E::Continuity::key_retarget:E::Continuity::replaced):E::Continuity::same;
            if(composition){
                const auto transaction=observation.transaction;
                result.composition_readback_attested=true;
                result.composition=E::CompositionFact{transaction,transport_composition?(projection->composition?E::CompositionState::live:E::CompositionState::pending):E::CompositionState::ended};
            }
            hooks.queue_wake(hooks.context);
            return ready()?result:unknown();
        }catch(...){poisoned=true;return unknown();}
    }
    E::NativeResult revoke_owned(const E::NativeRevocationRequest& request,std::uint64_t provider_sequence){
        if(!ready()||applying||projecting||!provider_sequence||provider_sequence==UINT64_MAX||!live||
            !live->value.retire||request.material!=*live->value.retire||!same_surface_context(request.identity,live->value.identity))return unknown();
        Applying activity(*this);
        const auto material=request.material;const auto original_identity=request.identity;
        try{
            auto& mapping=*live;
            {
                BIB::FoundationServiceEngineCall bridge;if(!bridge)return unknown();
                {
                    JSC::JSLockHolder lock(WebCore::commonVM());
                    // Retirement may operate after physical focus is lost, but
                    // exclusively on the retained original native editor.
                    auto& s=mapping.native;
                    BibAppDocumentIdentityV1 current{};current.size=sizeof(current);current.version=BIB_APP_DOCUMENT_IDENTITY_VERSION;
                    const bool original_is_current=bib_app_resources_current_identity(&current)==1&&same(BIB::bibProviderProjectDocument(current),s.expected);
                    if(original_is_current)hooks.invalidate_form_authority(hooks.context);
                    if(!ready()){poisoned=true;return unknown();}
                    if(!retirement_absent(mapping)){
                        if(!material.composition||s.frame->document()!=s.document.get()||
                            s.frame->editor().compositionRange()!=s.composition||
                            s.frame->editor().compositionNode()!=s.composition_node.get()){poisoned=true;return unknown();}
                        s.frame->editor().cancelComposition();
                        // compositionend may replace the Document synchronously. Never
                        // consult a replacement Editor through the old frame.
                        if(!retirement_absent(mapping)){poisoned=true;return unknown();}
                    }
                    transport_composition=0;
                    std::uint64_t physical_context{};
                    if(hooks.physical_authority(hooks.context,&s.expected,&physical_context)&&physical_context==material.input_context)
                        K::clearRawKeyModifiers();
                }
                bridge.finish();
            }
            if(!ready()||!retirement_absent(mapping)){poisoned=true;return unknown();}
            // Close only this exact original native authority. In particular a
            // historical9 must not capture, lay out, select or query the new DOM.
            // Even a still-editable original document receives no replacement
            // lease here: a later separately admitted query4 can discover it.
            live.reset();invalidated=false;
            E::NativeResult result;result.outcome=E::Outcome::applied;result.continuity=E::Continuity::replaced;
            result.retired=material;result.availability=E::NativeAvailability::unavailable;
            // unavailable describes the now-closed OLD authority, not the
            // replacement document's editability. This is actual post-unwind
            // old-frame/composition readback, never metadata invalidation alone.
            result.observation_revision=spend(next_revision);result.readback_identity=original_identity;result.readback_attested=true;
            result.composition_readback_attested=true;
            if(material.composition)result.composition=E::CompositionFact{material.composition,E::CompositionState::ended};
            hooks.queue_wake(hooks.context);return ready()?result:unknown();
        }catch(...){poisoned=true;return unknown();}
    }
    E::NativeResult revoke(const E::Revocation& request){
        if(!live||!live->value.retire)return unknown();
        return revoke_owned(E::NativeRevocationRequest{*live->value.retire,request.basis.identity,request},request.incarnation);
    }
    void invalidate_metadata()noexcept{invalidated=live.has_value();}

};
NativeEditorBackend::NativeEditorBackend(std::uint64_t worker,std::uint64_t app,NativeEditorHooks hooks):impl_(std::make_unique<Impl>(worker,app,std::move(hooks))){}
NativeEditorBackend::~NativeEditorBackend()=default;
std::optional<E::NativeProjection> NativeEditorBackend::project(std::uint64_t id){return impl_->project(id);}
E::NativeResult NativeEditorBackend::apply(const E::NativeRequest& request){return impl_->apply(request,request.packet.observation.id);}
E::NativeResult NativeEditorBackend::revoke(const E::Revocation& request){return impl_->revoke(request);}
C::ProjectionReply NativeEditorBackend::query(const C::ProjectionQuery& request){return impl_->query(request);}
E::NativeResult NativeEditorBackend::apply_owned(const E::NativeRequest& request,std::uint64_t sequence){return impl_->apply(request,sequence);}
E::NativeResult NativeEditorBackend::revoke_owned(const E::NativeRevocationRequest& request,std::uint64_t sequence){return impl_->revoke_owned(request,sequence);}
bool NativeEditorBackend::admit_metadata(const C::ProjectionQuery& request)const noexcept{return impl_->admit(request);}
bool NativeEditorBackend::admit_metadata(const C::NativeRequestEnvelope& request)const noexcept{return impl_->admit(request);}
bool NativeEditorBackend::admit_metadata(const C::RevocationEnvelope& request)const noexcept{return impl_->admit(request);}
void NativeEditorBackend::invalidate_metadata()noexcept{impl_->invalidate_metadata();}
}
