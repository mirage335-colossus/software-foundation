// SPDX-License-Identifier: CC0-1.0
// Shared actual-WebCore source. Real selected-header/object/runtime checks pending.
#include "config.h"
#include "BibNativePopupOwner.hpp"
#include "BibNativePopupHooks.hpp"
#include "BibEngineUiOwner.hpp"
#include "SharedNativeControlGuard.hpp"
#include "NativeRawKeyDispatch.hpp"
#include "Document.h"
#include "DocumentInlines.h"
#include "DocumentPage.h"
#include "DocumentView.h"
#include "Element.h"
#include "ElementInlines.h"
#include "FrameDestructionObserverInlines.h"
#include "GraphicsContext.h"
#include "HTMLNames.h"
#include "HTMLOptionElement.h"
#include "HTMLSelectElement.h"
#include "LocalFrame.h"
#include "LocalFrameInlines.h"
#include "LocalFrameView.h"
#include "NodeDocument.h"
#include "NodeInlines.h"
#include "PopupMenu.h"
#include "PopupMenuClient.h"
#include "PopupMenuStyle.h"
#include "RenderMenuList.h"
#include "Text.h"
#include "TextRun.h"
#include "UserGestureIndicator.h"
#include <wtf/CanMakeWeakPtr.h>
#include <wtf/RefPtr.h>
#include <wtf/WeakPtr.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <new>
#include <vector>

namespace BIB::EnginePopup {
namespace {
namespace P=Policy;
namespace UI=EngineUI;
namespace I=foundation::appended::engine_input;
using SelectWeak=WTF::WeakPtr<WebCore::HTMLSelectElement,WebCore::WeakPtrImplWithEventTargetData>;
using ElementWeak=WTF::WeakPtr<WebCore::HTMLElement,WebCore::WeakPtrImplWithEventTargetData>;
using DocumentWeak=WTF::WeakPtr<WebCore::Node,WebCore::WeakPtrImplWithEventTargetData>;
constexpr std::size_t maxRows=P::NativePopupController::maximum_rows;
constexpr std::size_t maxLabel=2048,maxText=65536,maxNodes=8192,maxDepth=64,maxBytes=4*1024*1024;
struct RowData {
    P::Row facts;
    ElementWeak element;
    WTF::String text;
    WebCore::PopupMenuStyle style;
    int height;
    RowData(P::Row f,WebCore::HTMLElement& e,WTF::String t,WebCore::PopupMenuStyle s,int h)
        :facts(f),element(e),text(WTF::move(t)),style(WTF::move(s)),height(h){}
};
P::LifecycleKey key(const UI::Snapshot& s) noexcept {
    return {s.owner.runtime_generation,s.owner.worker,s.owner.application,s.document_sequence,
        s.service_generation,s.resource_epoch,s.input_context};
}
bool sameDocument(const UI::Snapshot& a,const UI::Snapshot& b) noexcept {
    return a.owner==b.owner&&a.page==b.page&&a.main_frame==b.main_frame&&a.document==b.document
        &&a.page_identifier==b.page_identifier&&a.document_sequence==b.document_sequence
        &&a.service_generation==b.service_generation&&a.resource_epoch==b.resource_epoch
        &&a.input_context==b.input_context;
}
class NativePopupMenu;
struct Owner;
constinit Owner* retainedOwner{};
class NativePopupMenu final:public WebCore::PopupMenu,public WTF::CanMakeWeakPtr<NativePopupMenu> {
public:
    explicit NativePopupMenu(WebCore::HTMLSelectElement& select):select_(select),select_document_(select.document()){}
    ~NativePopupMenu() final;
    void show(const WebCore::IntRect&,WebCore::LocalFrameView&,int) final;
    void hide() final;
    void updateFromElement() final;
    void disconnectClient() final;
    bool refresh(bool initial,int selected=-1);
    bool current(UI::Snapshot&) const noexcept;
    bool equalRows(const std::vector<RowData>&) const;
    bool paint(WebCore::GraphicsContext&,const WebCore::IntRect&);
    std::uint64_t hit(double,double) const noexcept;
    void scroll(double);
    void revealHighlight();
    bool commit(const P::Choice&);
    void prepareChoice(const P::Choice&);
    void releaseRows() noexcept;
    void notifyHide();
    void dirty() const noexcept;
    SelectWeak select_;
    DocumentWeak select_document_;
    UI::Snapshot snapshot_{};
    P::PopupToken token_{};
    std::vector<RowData> rows_;
    struct ChoiceWitness {P::Choice choice;ElementWeak element;UI::Snapshot fence;};
    std::optional<ChoiceWitness> choice_;
    std::size_t rowBytes_{};
    WebCore::IntRect anchor_{},box_{};
    int scroll_{};
    bool refresh_needed_{true},visible_{},hide_notified_{};
};
struct Owner {
    P::NativePopupController controller;
    WTF::WeakPtr<NativePopupMenu> active;
    std::array<WTF::RefPtr<NativePopupMenu>,4> pending;
    P::LifecycleKey lastKey{};
    std::uint64_t nextRow{1};
    bool erasePending{};
    std::size_t bytes{sizeof(Owner)};
    std::uint32_t width{},height{};
    bool reserve(std::size_t count) noexcept {if(bytes>maxBytes||count>maxBytes-bytes)return false;bytes+=count;return true;}
    void release(std::size_t count) noexcept {if(count>bytes){UI::fault();return;}bytes-=count;}
};
Owner* owner(bool create=false) noexcept {
    if(!UI::onOwner())return nullptr;
    if(!retainedOwner&&create){try{retainedOwner=new Owner;}catch(...){UI::fault();}}
    return retainedOwner;
}
struct Reservation {
    Owner& owner;std::size_t bytes;bool held;
    Reservation(Owner& o,std::size_t n):owner(o),bytes(n),held(o.reserve(n)){}
    ~Reservation(){if(held)owner.release(bytes);}
    void adopt(std::size_t actual){if(!held||actual>bytes){UI::fault();return;}owner.release(bytes-actual);held=false;}
};
void invalidateFrame() noexcept {
    auto* o=owner();if(!o)return;o->erasePending=true;
    // Metadata retirement must never read Page/Document/native state.
    UI::markDamage({0,0,static_cast<int>(o->width),static_cast<int>(o->height)});
    UI::requestWake();
}
void queueHide(NativePopupMenu& popup) noexcept {
    auto* o=owner();if(!o)return;
    popup.visible_=false;
    popup.releaseRows();
    if(UI::modal()&&UI::modalEpoch()==popup.token_.epoch&&!UI::setModal(popup.token_.epoch,false))UI::fault();
    if(o->active.get()==&popup)o->active=nullptr;
    for(auto& slot:o->pending)if(slot.get()==&popup){invalidateFrame();return;}
    for(auto& slot:o->pending)if(!slot){slot=&popup;invalidateFrame();return;}
    UI::fault(); // Never drop a required hide notice or overwrite a successor.
}
void apply(const P::Result& result) noexcept {
    try {
    auto* o=owner();if(!o)return;
    if(result.route==P::Route::fault){UI::fault();return;}
    WTF::RefPtr<NativePopupMenu> closed;
    if(result.closed){
        closed=o->active.get();
        if(closed&&closed->token_==result.closed){if(result.choice)closed->prepareChoice(result.choice);queueHide(*closed);}
        else closed=nullptr; // This result never retires a callback-created successor.
    }
    if(result.damage)invalidateFrame();
    if(result.wheel&&o->active&&o->active->token_==result.token)o->active->scroll(result.wheel_y);
    if(o->active&&result.damage&&!result.wheel)o->active->revealHighlight();
    if(closed&&result.choice){
        // Retire all old capability before either real client callback.
        if(closed->choice_)UI::borrowCurrent(closed->choice_->fence);
        closed->notifyHide();
        if(!closed->commit(result.choice)){
            // Known stale/disabled replacement is a consumed no-selection result.
            // No old callback or guessed same-index option may be replayed.
        }
    }
    } catch (...) { UI::fault(); }
}
void drainHide() noexcept {
    try {
        auto* o=owner();if(!o||!UI::inNativeTurn())return;
        for(auto& slot:o->pending){auto popup=WTF::move(slot);if(popup)popup->notifyHide();}
    } catch (...) { UI::fault(); }
}
bool rawTextBound(WebCore::HTMLElement& element,std::size_t& nodes,std::size_t& total) {
    const auto& literal=element.attributeWithoutSynchronization(WebCore::HTMLNames::labelAttr);
    if(literal.length()>maxLabel||literal.length()>maxText-total)return false;
    total+=literal.length();
    WebCore::Node* cursor=&element;std::size_t depth=0,local=0;
    while(cursor){
        if(++nodes>maxNodes||depth>maxDepth)return false;
        if(auto* text=dynamicDowncast<WebCore::Text>(*cursor)){
            auto count=text->data().length();
            if(count>maxLabel-local||count>maxText-total)return false;
            local+=count;total+=count;
        }
        if(auto* child=cursor->firstChild()){cursor=child;++depth;continue;}
        while(cursor!=&element&&!cursor->nextSibling()){cursor=cursor->parentNode();if(!cursor||!depth)return false;--depth;}
        if(cursor==&element)break;
        cursor=cursor->nextSibling();
    }
    return true;
}
NativePopupMenu::~NativePopupMenu(){
    releaseRows();
    if(auto* o=owner())o->release(sizeof(NativePopupMenu));
    if(auto* o=owner();o&&o->active.get()==this){
        auto result=o->controller.close(token_);o->active=nullptr;
        if(UI::modal()&&UI::modalEpoch()==token_.epoch)UI::setModal(token_.epoch,false);
        if(result.damage)invalidateFrame();
    }
}
bool NativePopupMenu::current(UI::Snapshot& out) const noexcept {
    if(!UI::borrowCurrent(out)||!sameDocument(snapshot_,out))return false;
    auto* select=select_.get();
    return select&&select->isConnected()&&select_document_.get()==&select->document()
        &&select->document().frame()&&select->document().frame()->document()==&select->document()
        &&select->document().frame()->page()==snapshot_.page;
}
void NativePopupMenu::dirty() const noexcept {invalidateFrame();}
bool NativePopupMenu::equalRows(const std::vector<RowData>& other) const {
    if(rows_.size()!=other.size())return false;
    for(std::size_t i=0;i<rows_.size();++i){const auto& a=rows_[i];const auto& b=other[i];
        if(a.element.get()!=b.element.get()||a.facts.id!=b.facts.id||a.facts.list_index!=b.facts.list_index
            ||a.facts.enabled!=b.facts.enabled||a.facts.label!=b.facts.label||a.facts.separator!=b.facts.separator
            ||a.facts.hidden!=b.facts.hidden||a.text!=b.text||a.height!=b.height
            ||a.style.foregroundColor()!=b.style.foregroundColor()||a.style.backgroundColor()!=b.style.backgroundColor()
            ||a.style.font()!=b.style.font()||a.style.textDirection()!=b.style.textDirection()
            ||a.style.language()!=b.style.language()||a.style.hasTextDirectionOverride()!=b.style.hasTextDirectionOverride())return false;
    }return true;
}
bool NativePopupMenu::refresh(bool initial,int selected){
    auto* o=owner();if(!o)return false;
    UI::Snapshot now{};if(!current(now)||!now.raster||!now.input_context)return false;
    WTF::RefPtr<WebCore::HTMLSelectElement> select=select_.get();
    if(!select||select->multiple()||select->isDisabledFormControl()||!select->usesMenuList()
        ||!dynamicDowncast<WebCore::RenderMenuList>(select->renderer()))return false;
    if(now.viewport_width<24||now.viewport_height<24
        ||now.viewport_width>static_cast<unsigned>(std::numeric_limits<int>::max())
        ||now.viewport_height>static_cast<unsigned>(std::numeric_limits<int>::max()))return false;
    const auto& list=select->listItems();if(list.isEmpty()||list.size()>maxRows)return false;
    Reservation reservation(*o,list.size()*sizeof(RowData)+4*maxText);
    if(!reservation.held)return false;
    std::vector<RowData> staged;staged.reserve(list.size());
    if(staged.capacity()>maxRows)return false;
    if(staged.capacity()>list.size()){
        const auto extra=(staged.capacity()-list.size())*sizeof(RowData);
        if(!o->reserve(extra))return false;
        reservation.bytes+=extra;
    }
    std::array<P::Row,maxRows> facts{};
    std::size_t total=0,nodes=0;std::uint64_t selectedId=0;
    for(std::size_t i=0;i<list.size();++i){
        auto* element=list[i].get();if(!element||!rawTextBound(*element,nodes,total))return false;
        auto label=select->itemText(static_cast<unsigned>(i));
        if(label.length()>maxLabel||label.length()>maxText-total)return false;
        total+=label.length();
        auto style=select->itemStyle(static_cast<unsigned>(i));
        if(style.language().length()>maxLabel||style.language().length()>maxText-total)return false;
        total+=style.language().length();
        const bool separator=select->itemIsSeparator(static_cast<unsigned>(i));
        int height=separator?8:std::clamp(static_cast<int>(std::ceil(style.font().metricsOfPrimaryFont().height()))+8,18,64);
        std::uint64_t id=0;for(const auto& old:rows_)if(old.element.get()==element){id=old.facts.id;break;}
        if(!id){if(o->nextRow==std::numeric_limits<std::uint64_t>::max())return false;id=o->nextRow++;}
        P::Row row{id,static_cast<std::uint32_t>(i),select->itemIsEnabled(static_cast<unsigned>(i)),
            select->itemIsLabel(static_cast<unsigned>(i)),separator,!style.isVisible()||style.isDisplayNone()};
        facts[i]=row;
        if(static_cast<int>(i)==selected||(initial&&selected<0&&select->itemIsSelected(static_cast<unsigned>(i))))selectedId=id;
        staged.emplace_back(row,*element,WTF::move(label),WTF::move(style),height);
    }
    if(staged.capacity()*sizeof(RowData)+total*sizeof(char16_t)>maxBytes||!current(now))return false;
    auto* view=select->document().frame()->view();if(!view)return false;
    auto* renderer=select->renderer();
    auto contents=renderer->absoluteBoundingBoxRectIgnoringTransforms();
    contents.setLocation(WebCore::roundedIntPoint(renderer->localToAbsolute(WebCore::FloatPoint(),WebCore::UseTransforms)));
    const auto anchor=view->contentsToRootView(contents);
    const bool changed=initial||!equalRows(staged);
    if(changed){
        auto result=initial?o->controller.open(key(now),{facts.data(),staged.size()},selectedId,12)
            :o->controller.update(key(now),token_,{facts.data(),staged.size()});
        if(result.status!=P::Status::ok||!result.token){apply(result);return false;}
        releaseRows();
        rowBytes_=staged.capacity()*sizeof(RowData)+total*sizeof(char16_t);
        reservation.adopt(rowBytes_);rows_=WTF::move(staged);token_=result.token;snapshot_=now;o->lastKey=key(now);
        if(result.closed)apply(result);
    }
    o->width=now.viewport_width;o->height=now.viewport_height;
    anchor_=anchor;
    int totalHeight=4;for(const auto& row:rows_)if(!row.facts.hidden)totalHeight+=row.height;
    const int availableWidth=static_cast<int>(now.viewport_width);
    const int availableHeight=static_cast<int>(now.viewport_height);
    const int width=std::clamp(anchor.width(),std::min(120,availableWidth),availableWidth);
    const int height=std::min(totalHeight,availableHeight);
    int x=std::clamp(anchor.x(),0,std::max(0,static_cast<int>(now.viewport_width)-width));
    int y=anchor.maxY();
    if(static_cast<std::int64_t>(y)+height>availableHeight)
        y=static_cast<int>(std::max<std::int64_t>(std::numeric_limits<int>::min(),static_cast<std::int64_t>(anchor.y())-height));
    y=std::clamp(y,0,std::max(0,static_cast<int>(now.viewport_height)-height));
    WebCore::IntRect box{x,y,width,height};const bool geometryChanged=box_!=box;
    if(geometryChanged||changed){box_=box;dirty();revealHighlight();}
    snapshot_=now;refresh_needed_=false;return true;
}
void NativePopupMenu::show(const WebCore::IntRect&,WebCore::LocalFrameView&,int selected){
    if(!UI::onOwner()||!UI::inNativeTurn()){UI::fault();return;}
    try{
        auto* o=owner(true);UI::Snapshot now{};
        if(!o||!UI::borrowCurrent(now)||!now.raster||!now.input_context){notifyHide();return;}
        if(o->active){auto old=o->active.get();apply(o->controller.close(old->token_));drainHide();}
        snapshot_=now;hide_notified_=false;
        if(!refresh(true,selected)){notifyHide();return;}
        visible_=true;o->active=this;
        if(!UI::setModal(token_.epoch,true)){UI::fault();return;}
        UI::borrowCurrent(snapshot_);dirty();
    }catch(...){UI::fault();}
}
void NativePopupMenu::hide(){
    if(!UI::onOwner()){UI::fault();return;}
    try {
        if(auto* o=owner();o&&o->active.get()==this)apply(o->controller.close(token_));
        else if(!hide_notified_)queueHide(*this);
        drainHide();
    } catch (...) { UI::fault(); }
}
void NativePopupMenu::disconnectClient(){hide();select_=nullptr;rows_.clear();}
void NativePopupMenu::updateFromElement(){if(!UI::onOwner()){UI::fault();return;}refresh_needed_=true;dirty();}
void NativePopupMenu::releaseRows() noexcept {
    std::vector<RowData>().swap(rows_);
    if(rowBytes_){if(auto* o=owner())o->release(rowBytes_);rowBytes_=0;}
}
void NativePopupMenu::prepareChoice(const P::Choice& choice){
    choice_.reset();
    auto found=std::find_if(rows_.begin(),rows_.end(),[&](const auto& r){return r.facts.id==choice.row_id;});
    if(found!=rows_.end()&&found->facts.selectable()&&found->facts.list_index==choice.list_index)
        choice_=ChoiceWitness{choice,found->element,{}};
}
void NativePopupMenu::notifyHide(){
    if(hide_notified_)return;
    if(!UI::inNativeTurn()){queueHide(*this);return;}
    hide_notified_=true;releaseRows();
    WTF::RefPtr<WebCore::HTMLSelectElement> select=select_.get();
    if(select)select->popupDidHide();
}
bool NativePopupMenu::commit(const P::Choice& choice){
    auto witness=WTF::move(choice_);choice_.reset();
    if(!witness||!UI::inNativeTurn()||choice.token!=token_||!hide_notified_
        ||witness->choice.token!=choice.token||witness->choice.row_id!=choice.row_id
        ||!UI::matches(witness->fence)||witness->fence.modal)return false;
    auto* o=owner();if(!o||o->controller.active()||o->active)return false;
    UI::Snapshot now{};if(!current(now))return false;
    WTF::RefPtr<WebCore::HTMLSelectElement> select=select_.get();
    WTF::RefPtr<WebCore::HTMLOptionElement> option=dynamicDowncast<WebCore::HTMLOptionElement>(witness->element.get());
    if(!select||!option||select->multiple()||select->isDisabledFormControl()||!select->usesMenuList()
        ||!dynamicDowncast<WebCore::RenderMenuList>(select->renderer()))return false;
    const auto& list=select->listItems();
    if(!option->isConnected()||option->ownerSelectElement()!=select.get()||choice.list_index>=list.size()
        ||list[choice.list_index].get()!=option.get()||!select->itemIsEnabled(choice.list_index)
        ||select->itemIsLabel(choice.list_index)||select->itemIsSeparator(choice.list_index))return false;
    const auto style=select->itemStyle(choice.list_index);
    if(!style.isVisible()||style.isDisplayNone()||!current(now)||!UI::matches(witness->fence)
        ||select->multiple()||select->isDisabledFormControl()||!select->usesMenuList()
        ||!dynamicDowncast<WebCore::RenderMenuList>(select->renderer())
        ||o->controller.active()||o->active)return false;
    WebCore::UserGestureIndicator gesture(WebCore::IsProcessingUserGesture::Yes,&select->document());
    select->valueChanged(choice.list_index,true);return true; // No old tail.
}
std::uint64_t NativePopupMenu::hit(double x,double y) const noexcept {
    if(!visible_||!std::isfinite(x)||!std::isfinite(y)||x<box_.x()||x>=box_.maxX()||y<box_.y()||y>=box_.maxY())return 0;
    int top=box_.y()+2-scroll_;
    for(const auto& row:rows_){if(row.facts.hidden)continue;if(y>=top&&y<top+row.height)return row.facts.id;top+=row.height;}
    return 0;
}
void NativePopupMenu::scroll(double delta){
    int total=4;for(const auto& r:rows_)if(!r.facts.hidden)total+=r.height;
    const auto amount=std::clamp(delta,-512.0,512.0);
    const int next=std::clamp(scroll_+static_cast<int>(std::lround(amount)),0,std::max(0,total-box_.height()));
    if(next!=scroll_){scroll_=next;dirty();}
}
void NativePopupMenu::revealHighlight(){
    auto* o=owner();if(!o)return;int top=2;
    for(const auto& row:rows_){if(row.facts.hidden)continue;
        if(row.facts.id==o->controller.highlightedRow()){
            int next=scroll_;if(top<scroll_)next=top;else if(top+row.height>scroll_+box_.height()-2)next=top+row.height-box_.height()+2;
            if(next!=scroll_){scroll_=std::max(0,next);dirty();}break;
        }top+=row.height;
    }
}
bool NativePopupMenu::paint(WebCore::GraphicsContext& context,const WebCore::IntRect& dirtyRect){
    if(!visible_||!box_.intersects(dirtyRect))return true;
    auto* o=owner();if(!o)return false;
    context.save();context.clip(box_);context.fillRect(box_,WebCore::Color::white);
    int top=box_.y()+2-scroll_;
    for(const auto& row:rows_){if(row.facts.hidden)continue;
        WebCore::FloatRect rect(box_.x()+2,top,box_.width()-4,row.height);
        if(rect.maxY()>box_.y()&&rect.y()<box_.maxY()){
            const bool selected=row.facts.id==o->controller.highlightedRow();
            if(row.facts.separator)context.fillRect({rect.x()+3,rect.y()+3,rect.width()-6,1},WebCore::Color::gray);
            else{
                context.fillRect(rect,selected?WebCore::Color(WebCore::Color::blue):row.style.backgroundColor());
                context.setFillColor(!row.facts.enabled?WebCore::Color(WebCore::Color::gray):selected?WebCore::Color(WebCore::Color::white):row.style.foregroundColor());
                context.save();context.clip(rect);
                WebCore::TextRun run(row.text,0,0,WebCore::ExpansionBehavior::defaultBehavior(),row.style.textDirection(),row.style.hasTextDirectionOverride());
                const float width=row.style.font().width(run);
                const float x=row.style.textDirection()==WebCore::TextDirection::RTL?rect.maxX()-4-width:rect.x()+4;
                context.drawText(row.style.font(),run,{x,rect.y()+4+row.style.font().metricsOfPrimaryFont().ascent()});
                context.restore();
            }
        }top+=row.height;
    }
    context.restore();return true;
}
P::KeyPacket packet(const I::Key& input) noexcept {
    return {input.phase,input.location,input.modifiers,input.repeat!=0,input.code,
        P::NativePopupController::standardCode(input.code)};
}
}
P::PopupToken token() noexcept {auto* o=owner();return o?o->controller.token():P::PopupToken{};}
bool blocksScrollBlit() noexcept {auto* o=owner();return o&&(o->controller.active()||o->erasePending);}
void reconcile() noexcept {
    if(!UI::inNativeTurn())return;
    try{
        drainHide();auto* o=owner();if(!o)return;
        WTF::RefPtr<NativePopupMenu> popup=o->active.get();
        if(popup&&!popup->refresh(false)){apply(o->controller.close(popup->token_));drainHide();}
    }catch(...){UI::fault();}
}
bool paint(WebCore::GraphicsContext& context,const WebCore::IntRect& rect) noexcept {
    if(UI::faulted())return false;
    try{auto* o=owner();if(!o)return true;WTF::RefPtr<NativePopupMenu> popup=o->active.get();
        UI::Snapshot now{};
        // Paint only owned rows/styles. The shared inert root fence reads no
        // select/client or DOM subtree; native ownership is checked by capture.
        if(popup&&(!UI::borrowCurrent(now)||!sameDocument(popup->snapshot_,now)
            ||!now.raster||now.viewport_width!=popup->snapshot_.viewport_width
            ||now.viewport_height!=popup->snapshot_.viewport_height||!now.modal||now.modal_epoch!=popup->token_.epoch
            ||o->controller.token()!=popup->token_||!popup->paint(context,rect)))return false;
        o->erasePending=false;return !UI::faulted();
    }catch(...){UI::fault();return false;}
}
RouteResult routeKey(const I::Key& input) noexcept {
    if(!UI::inNativeTurn()) {UI::fault();return {true,false};}
    try{
        // Preserve the admitted original mask before reconciliation can hide a
        // popup or deliver a client callback, including popup-consumed keyup.
        foundation::appended::ndv2_physical::updateRawKeyModifiers(input.modifiers);
        reconcile();auto* o=owner();UI::Snapshot now{};if(!o)return {};
        if(!UI::borrowCurrent(now)){UI::fault();return {true,false};}
        o->lastKey=key(now);auto result=o->controller.key(o->lastKey,packet(input));
        apply(result);drainHide();return {result.route!=P::Route::page,result.route==P::Route::consumed};
    }catch(...){UI::fault();return {true,false};}
}
RouteResult routePointer(const I::Mouse& input,P::PointerState previous,P::PointerState next) noexcept {
    if(!UI::inNativeTurn()){UI::fault();return {true,false};}
    try{reconcile();auto* o=owner();UI::Snapshot now{};if(!o)return {};
        if(!UI::borrowCurrent(now)){UI::fault();return {true,false};}
        o->lastKey=key(now);std::uint64_t hit=0;if(o->active)hit=o->active->hit(input.x,input.y);
        P::PointerPacket packet{static_cast<P::PointerPhase>(input.phase),input.capture_token,input.button,input.buttons,
            input.modifiers,input.context_origin,input.x,input.y,input.wheel_x,input.wheel_y};
        auto result=o->controller.pointer(o->lastKey,packet,previous,next,hit);apply(result);drainHide();
        return {result.route!=P::Route::page,result.route==P::Route::consumed};
    }catch(...){UI::fault();return {true,false};}
}
std::optional<Handoff> afterPageInput(P::PopupToken before,const I::Key* keyInput,const I::Mouse* mouse,
    P::PointerState committed,double pointerX,double pointerY,bool hasPointerPoint,std::uint64_t version,std::uint64_t sequence) noexcept {
    try{if(keyInput&&mouse){UI::fault();return std::nullopt;}
        auto* o=owner();UI::Snapshot now{};if(!o||!UI::borrowCurrent(now)||!o->controller.active()||o->controller.token()==before)return std::nullopt;
        const auto opened=o->controller.token();o->lastKey=key(now);
        if(keyInput){auto result=o->controller.adoptOpeningKey(o->lastKey,opened,packet(*keyInput));apply(result);drainHide();}
        if(!o->controller.active()||o->controller.token()!=opened)return std::nullopt;
        if(committed.capture_token&&committed.buttons){
            if(!hasPointerPoint||!std::isfinite(pointerX)||!std::isfinite(pointerY)){UI::fault();return std::nullopt;}
            auto result=o->controller.adoptOpeningPointer(o->lastKey,opened,committed,pointerX,pointerY);apply(result);
            if(result.handoff)return Handoff{opened,o->lastKey,committed,version,sequence};
        }return std::nullopt;
    }catch(...){UI::fault();return std::nullopt;}
}
bool handoffCurrent(const Handoff& h) noexcept {
    auto* o=owner();UI::Snapshot now{};
    return o&&UI::borrowCurrent(now)&&key(now)==h.key&&o->controller.token()==h.token
        &&o->controller.pointerDebt().present&&o->controller.pointerDebt().state==h.pointer;
}
void finishHandoff(const Handoff& h,bool completed,bool nativeEffectsStarted) noexcept {
    if(completed)return;
    // The caller sets this witness immediately BEFORE the real cancelPointer.
    // If that callback replaces authority, the old clear/reset tail must stop.
    // No positive completion proof is available for that partial cancellation;
    // contain it even when an author-created successor makes h stale.
    // Before any native effect, a stale owner is ordinary metadata retirement.
    if(nativeEffectsStarted||handoffCurrent(h))UI::fault();
}
void observeFocus(P::PointerState previous,P::PointerState next,bool focused,bool active) noexcept {
    auto* o=owner();if(!o||!o->lastKey.valid())return;
    auto result=o->controller.observeFocus(o->lastKey,previous,next,focused,active);apply(result);
    if(!next.context)o->lastKey={};
}
void retireAuthority() noexcept {
    auto* o=owner();if(!o)return;
    if(o->lastKey.valid())apply(o->controller.retireAuthority(o->lastKey));
    o->lastKey={};
}
bool openUserPopup(WebCore::HTMLSelectElement& select,FormsV2Combined::SharedGuard& guard) noexcept {
    try{auto context=guard.current();UI::Snapshot now{};
        if(!context||!UI::borrowCurrent(now)||!now.raster||!now.input_context||!select.isConnected()
            ||&select.document()!=context->document.get()||&select.document()!=now.document)return false;
        const auto serial=guard.lifetimeSerial();select.showPopup();
        auto* o=owner();return o&&o->active&&o->active->select_.get()==&select&&select.popupIsVisible()
            &&guard.isCurrent(*context,serial)&&!UI::faulted();
    }catch(...){UI::fault();return false;}
}
} // namespace BIB::EnginePopup

namespace BIB::NativeHTMLPopup {
namespace {thread_local NativeSelectPopupCreationPermit* currentPermit{};thread_local std::uint64_t permitSerial{};}
NativeSelectPopupCreationPermit::NativeSelectPopupCreationPermit(WebCore::HTMLSelectElement& select) noexcept
    :previous_(currentPermit),select_(&select),client_(static_cast<WebCore::PopupMenuClient*>(&select)) {
    if(permitSerial==std::numeric_limits<std::uint64_t>::max()){EngineUI::fault();return;}
    serial_=++permitSerial;active_=true;currentPermit=this;
}
NativeSelectPopupCreationPermit::~NativeSelectPopupCreationPermit(){
    if(!active_)return;
    if(currentPermit!=this){EngineUI::fault();return;}
    currentPermit=previous_;
}
bool tryCreateNativeSelectPopup(const WebCore::ChromeClient& chrome,WebCore::PopupMenuClient& client,
    WTF::RefPtr<WebCore::PopupMenu>& output) noexcept {
    if(EngineUI::registeredChrome()!=&chrome)return false;
    if(!EngineUI::onOwner()||!EngineUI::inNativeTurn()){EngineUI::fault();return true;}
    auto* permit=currentPermit;
    if(!permit||!permit->active_||permit->client_!=&client)return false;
    try{EngineUI::Snapshot now{};
        if(!EngineUI::borrowCurrent(now)||!now.raster||!now.input_context||!permit->select_->isConnected()
            ||!permit->select_->document().frame()
            ||permit->select_->document().frame()->document()!=&permit->select_->document()
            ||permit->select_->document().frame()->page()!=now.page)return true;
        auto* owner=EnginePopup::owner(true);if(!owner)return true;
        if(!owner->reserve(sizeof(EnginePopup::NativePopupMenu)))return true;
        try{output=adoptRef(*new EnginePopup::NativePopupMenu(*permit->select_));}
        catch(...){owner->release(sizeof(EnginePopup::NativePopupMenu));throw;}
        return true;
    }catch(...){EngineUI::fault();return true;}
}
} // namespace BIB::NativeHTMLPopup
