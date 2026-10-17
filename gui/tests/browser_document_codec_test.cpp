// SPDX-License-Identifier: CC0-1.0
// Generic owned values only; no engine/provider or retained runtime is used.
#include "host/browser_document_codec.hpp"
#include <functional>
#include <iostream>
#include <limits>
#include <stdexcept>
namespace {
namespace W=foundation::host::document_web;
namespace D=foundation::gui_document;
namespace A=foundation::appended;
namespace U=foundation::ui;
using Json=W::Json;
std::size_t assertions{};
void check(bool value,const char* message){++assertions;if(!value)throw std::runtime_error(message);}
template<class F>void rejected(F&& f,const char* message){++assertions;try{f();}catch(const std::invalid_argument&){return;}throw std::runtime_error(message);}
Json::Object& object(Json& v){return std::get<Json::Object>(v.value);}
Json submit(Json intent){return Json::Object{{"type","documentSubmit"},{"version",1},{"intent",std::move(intent)}};}
void inputs(){
    check(std::holds_alternative<D::Observe>(W::parse_submit(submit(Json::Object{{"kind","observe"}}))),"Observe did not retain its typed alternative");
    const auto wide=std::numeric_limits<std::uint64_t>::max();
    const auto begin=W::parse_submit(submit(Json::Object{{"kind","begin"},{"observation",std::to_string(wide)},{"node","7"}}));
    check(std::get<D::Begin>(begin).observation.value==wide&&std::get<D::Begin>(begin).node==7,"Begin lost full native observation/node spelling");
    auto edit=W::parse_submit(submit(Json::Object{{"kind","editText"},{"draft","21"},{"baseText","A\xf0\x9f\x98\x80"},{"text","\xce\xb2"}}));
    check(std::get<D::EditText>(edit).text=="\xce\xb2","Owned text intent changed");
    check(std::get<D::SelectText>(W::parse_submit(submit(Json::Object{{"kind","selectText"},{"draft","21"},{"anchor",1},{"caret",5}}))).selection==A::FormByteSelection{1,5},"Source byte selection changed");
    check(std::get<D::SetChecked>(W::parse_submit(submit(Json::Object{{"kind","setChecked"},{"draft","21"},{"checked",true}}))).checked,"Checked intent changed");
    check(std::get<D::SetOption>(W::parse_submit(submit(Json::Object{{"kind","setOption"},{"draft","21"},{"node","9"},{"selected",false}}))).node==9,"Actual option node changed");
    std::size_t index=6;
    for(const char* kind:{"apply","reload","reapply","cancel","finish"})check(W::parse_submit(submit(Json::Object{{"kind",kind},{"draft","21"}})).index()==index++,"Closed draft intent variant changed");
    check(W::parse_take(Json::Object{{"type","documentTake"},{"version",1},{"ticket",std::to_string(wide)}}).value==wide,"Take ticket lost precision");
    for(const Json& ticket:{Json{"0"},Json{"01"},Json{"+1"},Json{"-1"},Json{"1.0"},Json{"1e3"},Json{"18446744073709551616"},Json{1},Json{true}})
        rejected([&]{W::parse_take(Json::Object{{"type","documentTake"},{"version",1},{"ticket",ticket}});},"Invalid ticket accepted");
    for(const char* field:{"nativeLease","nativeTarget","workerEpoch","requestSequence","payload","nativeOpcode","nativeAck","nativeReplay","documentPublicationAck"})
        rejected([&]{W::parse_submit(submit(Json::Object{{"kind","observe"},{field,"1"}}));},"Native authority field accepted");
    for(const char* kind:{"focusBody","activateBody","selectBody","chooseSelectOne","nativeReplay"})
        rejected([&]{W::parse_submit(submit(Json::Object{{"kind",kind},{"draft","1"}}));},"Unadmitted operation accepted");
    for(const auto& text:std::vector<std::string>{std::string("a\0b",3),"\xed\xa0\x80",std::string(2049,'x')})
        rejected([&]{W::parse_submit(submit(Json::Object{{"kind","editText"},{"draft","1"},{"baseText",""},{"text",text}}));},"Invalid scalar/bounded text accepted");
    rejected([&]{W::parse_submit(submit(Json::Object{{"kind","selectText"},{"draft","1"},{"anchor",1.5},{"caret",5}}));},"Fractional byte offset accepted");
    rejected([&]{gui::web_detail::Parser("{\"type\":\"documentTake\",\"version\":1,\"ticket\":\"1\",\"ticket\":\"2\"}").parse();},"Duplicate input key accepted before owner reservation");
}
D::State state(){
    D::State value;value.publication_revision=101;value.available=true;value.observation=D::Observation{17};
    auto native=std::make_shared<U::NativeFormsDocumentObservation>();native->publication={7,11,13};native->forms.version=native->publication;
    native->body.request_id=17;native->body.epoch=11;native->body.snapshot=U::DocumentSnapshot{{7,11,13},{},{},{},false};
    U::DocumentNode node;node.id=4;node.kind=U::DocumentNodeKind::text;node.text="A\xf0\x9f\x98\x80\xc3\xa9";native->body.snapshot->nodes.push_back(node);
    native->body.original_selection=U::DocumentWireSelection{{{4,1,U::DocumentNativeOffsetKind::element_child_index},{4,3,U::DocumentNativeOffsetKind::text_utf16}},{0.25,-1,1.5,17}};
    native->body.degraded.element_selection=true;
    A::FormControl control;control.node=4;control.kind=A::FormKind::textarea;control.native_type="textarea";control.label="Native field";control.focusable=true;control.focused=true;control.complete=true;control.capabilities=17;
    control.state=A::FormTextState{node.text,node.text,A::FormControlRange{1,3,A::FormDirection::forward}};control.lease=A::FormLease{native->publication,4,std::numeric_limits<std::uint64_t>::max()};native->forms.controls.push_back(control);
    value.document=std::move(native);D::DraftView draft;draft.id={21};draft.kind=A::FormKind::textarea;draft.phase=A::FormDraftPhase::editing;draft.text=node.text;draft.selection={1,5};value.draft=std::move(draft);return value;
}
void outputs(){
    check(W::detail::rect(gui::Rect{-1e100,1e100,1e90,1e80}).at("x").number()==-1e100,"Readonly native geometry was narrowed");
    rejected([&]{W::detail::rect(gui::Rect{0,0,-1,1});},"Negative native rectangle width accepted");
    const auto source=state();const auto output=W::json_state(source);
    check(output.at("publicationRevision").str()=="101"&&output.at("observation").str()=="17","Actual accepted publication identity changed");
    check(output.at("document").at("forms").at("controls").array()[0].at("lease").at("id").str()=="18446744073709551615","Readonly native lease lost precision");
    check(output.at("document").at("body").at("originalSelection").at("endpoints").at("anchor").at("kind").str()=="element_child_index","Native selection offset kind was normalized");
    auto live=source;live.phase=D::Phase::waiting_ack;live.pending=D::Ticket{53};live.available=false;const auto changed=W::json_state(live);
    check(gui::web_detail::encode(changed.at("document"))==gui::web_detail::encode(output.at("document"))&&changed.at("publicationRevision").str()=="101","Live metadata rewrote accepted content");
    D::Completion completion{{53},D::Outcome::completed,source.observation,source.draft,""};
    check(W::json_reply(7,true,D::Admission::accepted,D::Ticket{53},completion).at("completion").at("ticket").str()=="53","Completion correlation changed");
    rejected([&]{W::json_reply(7,true,D::Admission::accepted,D::Ticket{54},completion);},"Crossed completion ticket accepted");
    rejected([&]{W::json_reply(7,false,D::Admission::accepted,{});},"Accepted request without broker ticket accepted");
    rejected([&]{W::json_reply(7,false,D::Admission::busy,D::Ticket{53});},"Refusal invented broker authority");
    auto bad=source;bad.publication_revision=0;rejected([&]{W::json_state(bad);},"Unaccepted content was serialized");
    bad=source;bad.observation.reset();rejected([&]{W::json_state(bad);},"Observation/document mismatch accepted");
    bad=source;bad.draft->selection={2,3};rejected([&]{W::json_state(bad);},"Draft selection split a UTF-8 scalar");
    bad=source;bad.phase=static_cast<D::Phase>(99);rejected([&]{W::json_state(bad);},"Unknown phase was coerced");
}
}
int main(){try{inputs();outputs();std::cout<<assertions<<" generic document codec assertions passed\n";return 0;}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
