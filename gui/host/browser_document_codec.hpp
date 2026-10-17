// SPDX-License-Identifier: CC0-1.0
#pragma once
#include "browser_surface_codec.hpp"
#include <foundation/gui/document_endpoint.hpp>
#include <type_traits>

namespace foundation::host::document_web {
namespace D=::foundation::gui_document;
namespace A=::foundation::appended;
namespace U=::foundation::ui;
using Json=surface_web::Json;
inline constexpr std::size_t max_request_bytes=65536,max_response_bytes=32u*1024u*1024u;
inline constexpr std::size_t max_text_bytes=8192;
namespace detail {
[[noreturn]] inline void invalid(){throw std::invalid_argument("Invalid browser document value");}
inline const std::string& text(const Json& value){
    const auto& result=surface_web::detail::text(value,max_text_bytes);
    std::size_t units=0;
    for(std::size_t i=0;i<result.size();){const auto n=static_cast<unsigned char>(result[i]);const auto count=n<0x80?1u:n<0xe0?2u:n<0xf0?3u:4u;i+=count;units+=count==4?2:1;}
    if(units>A::FormLimits{}.field_utf16)invalid();
    return result;
}
inline Json text(const std::string& value){Json result{value};(void)text(result);return result;}
inline std::uint64_t handle(const Json& value){return surface_web::detail::decimal(value,true);}
inline Json handle(std::uint64_t value){if(!value)invalid();return std::to_string(value);}
template<class T>Json optional_handle(const std::optional<T>& value){return value?handle(value->value):Json{};}
inline bool boolean(const Json& value){return surface_web::detail::boolean(value);}
inline unsigned offset(const Json& value){return surface_web::detail::integer(value,max_text_bytes);}
inline Json version(const auto& value){return Json::Object{{"generation",handle(value.generation)},{"epoch",handle(value.epoch)},{"revision",handle(value.revision)}};}
template<class T>const char* enumeration(T value,std::initializer_list<std::pair<T,const char*>> domain){for(auto item:domain)if(item.first==value)return item.second;invalid();}
inline const char* form_kind(A::FormKind v){return enumeration(v,{{A::FormKind::text,"text"},{A::FormKind::number,"number"},{A::FormKind::textarea,"textarea"},{A::FormKind::checkbox,"checkbox"},{A::FormKind::select_one,"select_one"},{A::FormKind::select_many,"select_many"},{A::FormKind::secure_readonly,"secure_readonly"},{A::FormKind::unsupported,"unsupported"}});}
inline const char* draft_phase(A::FormDraftPhase v){return enumeration(v,{{A::FormDraftPhase::editing,"editing"},{A::FormDraftPhase::pending,"pending"},{A::FormDraftPhase::stale,"stale"},{A::FormDraftPhase::unknown,"unknown"},{A::FormDraftPhase::unavailable,"unavailable"},{A::FormDraftPhase::closed,"closed"}});}
inline Json range(const A::FormControlRange& v){return Json::Object{{"start",double(v.start)},{"end",double(v.end)},{"direction",enumeration(v.direction,{{A::FormDirection::none,"none"},{A::FormDirection::forward,"forward"},{A::FormDirection::backward,"backward"}})}};}
inline Json option(const A::FormOption& v){return Json::Object{{"node",handle(v.node)},{"label",text(v.label)},{"selected",v.selected},{"disabled",v.disabled},{"omitted",v.omitted}};}
inline Json control(const A::FormControl& v){
    Json state;
    std::visit([&](const auto& data){using T=std::decay_t<decltype(data)>;
        if constexpr(std::is_same_v<T,A::FormTextState>)state=Json::Object{{"kind","text"},{"value",Json::Object{{"value",text(data.value)},{"editingText",text(data.editing_text)},{"selection",data.selection?range(*data.selection):Json{}}}}};
        else if constexpr(std::is_same_v<T,A::FormCheckState>)state=Json::Object{{"kind","check"},{"value",Json::Object{{"checked",data.checked},{"indeterminate",data.indeterminate}}}};
        else if constexpr(std::is_same_v<T,A::FormSelectState>){if(data.options.size()>A::FormLimits{}.options)invalid();Json::Array values;for(const auto& item:data.options)values.push_back(option(item));state=Json::Object{{"kind","select"},{"value",Json::Object{{"multiple",data.multiple},{"menuList",data.menu_list},{"options",std::move(values)}}}};}
    },v.state);
    Json lease;if(v.lease)lease=Json::Object{{"captured",version(v.lease->captured)},{"node",handle(v.lease->node)},{"id",handle(v.lease->id)}};
    return Json::Object{{"node",handle(v.node)},{"kind",form_kind(v.kind)},{"nativeType",text(v.native_type)},{"label",text(v.label)},{"disabled",v.disabled},{"readOnly",v.read_only},{"focusable",v.focusable},{"focused",v.focused},{"omitted",v.omitted},{"complete",v.complete},{"capabilities",double(v.capabilities)},{"state",std::move(state)},{"lease",std::move(lease)}};
}
inline Json point(const U::DocumentPoint& v){return Json::Object{{"node",handle(v.node)},{"utf16Offset",double(v.utf16_offset)}};}
inline Json selection(const U::DocumentSelection& v){return Json::Object{{"anchor",point(v.anchor)},{"focus",point(v.focus)}};}
inline Json native_point(const U::DocumentNativePoint& v){return Json::Object{{"node",handle(v.node)},{"offset",double(v.offset)},{"kind",enumeration(v.kind,{{U::DocumentNativeOffsetKind::text_utf16,"text_utf16"},{U::DocumentNativeOffsetKind::element_child_index,"element_child_index"}})}};}
inline Json rect(const gui::Rect& v){if(!std::isfinite(v.x)||!std::isfinite(v.y)||!std::isfinite(v.width)||!std::isfinite(v.height)||v.width<0||v.height<0)invalid();return Json::Object{{"x",v.x},{"y",v.y},{"width",v.width},{"height",v.height}};}
inline Json snapshot(const U::DocumentSnapshot& v){
    if(v.nodes.size()>2048)invalid();
    Json::Array nodes;
    for(const auto& n:v.nodes)nodes.push_back(Json::Object{{"id",handle(n.id)},{"parent",std::to_string(n.parent)},{"kind",enumeration(n.kind,{{U::DocumentNodeKind::element,"element"},{U::DocumentNodeKind::text,"text"}})},{"tag",text(n.tag)},{"text",text(n.text)},{"name",text(n.name)},{"value",text(n.value)},{"href",text(n.href)},{"whiteSpace",enumeration(n.white_space,{{U::DocumentWhiteSpace::normal,"normal"},{U::DocumentWhiteSpace::pre,"pre"},{U::DocumentWhiteSpace::pre_wrap,"pre_wrap"}})},{"omitted",n.omitted},{"masked",n.masked},{"disabled",n.disabled},{"editable",n.editable}});
    return Json::Object{{"version",version(v.version)},{"nodes",std::move(nodes)},{"activeNode",v.active_node?handle(*v.active_node):Json{}},{"selection",v.selection?selection(*v.selection):Json{}},{"truncated",v.truncated}};
}
inline Json body(const U::DocumentSemanticReply& v){
    if(v.metadata.size()>2048)invalid();
    Json::Array metadata;
    for(const auto& n:v.metadata)metadata.push_back(Json::Object{{"node",handle(n.node)},{"role",text(n.role)},{"display",text(n.display)},{"whiteSpace",text(n.white_space)},{"readOnly",n.read_only},{"checked",n.checked}});
    Json original;if(v.original_selection)original=Json::Object{{"endpoints",Json::Object{{"anchor",native_point(v.original_selection->endpoints.anchor)},{"focus",native_point(v.original_selection->endpoints.focus)}}},{"focusRect",rect(v.original_selection->focus_rect)}};
    return Json::Object{{"requestId",std::to_string(v.request_id)},{"epoch",std::to_string(v.epoch)},{"errorCode",text(v.error_code)},{"snapshot",v.snapshot?snapshot(*v.snapshot):Json{}},{"editorState",v.editor_state?Json{Json::Object{{"revision",double(v.editor_state->revision)},{"flags",double(v.editor_state->flags)}}}:Json{}},{"metadata",std::move(metadata)},{"originalSelection",std::move(original)},{"degraded",Json::Object{{"whitespace",v.degraded.whitespace},{"elementSelection",v.degraded.element_selection},{"truncatedSelection",v.degraded.truncated_selection}}}};
}
inline Json document(const U::NativeFormsDocumentObservation& v){
    A::validate_document_forms(v.forms);if(v.protocol!=A::document_forms_version)invalid();Json::Array controls;for(const auto& item:v.forms.controls)controls.push_back(control(item));
    return Json::Object{{"protocol",double(v.protocol)},{"publication",version(v.publication)},{"body",body(v.body)},{"forms",Json::Object{{"protocol",double(v.forms.protocol)},{"version",version(v.forms.version)},{"controls",std::move(controls)}}}};
}
inline Json checked(Json value,std::size_t maximum){if(gui::web_detail::encode(value).size()>maximum)invalid();return value;}
}

inline D::Intent parse_intent(const Json& value){
    using surface_web::require_shape;const auto& kind=surface_web::detail::text(value.at("kind"),16,false);
    if(kind=="observe"){require_shape(value,{"kind"});return D::Observe{};}
    if(kind=="begin"){require_shape(value,{"kind","observation","node"});return D::Begin{{detail::handle(value.at("observation"))},detail::handle(value.at("node"))};}
    if(kind=="editText"){require_shape(value,{"kind","draft","baseText","text"});return D::EditText{{detail::handle(value.at("draft"))},detail::text(value.at("baseText")),detail::text(value.at("text"))};}
    if(kind=="selectText"){require_shape(value,{"kind","draft","anchor","caret"});return D::SelectText{{detail::handle(value.at("draft"))},{detail::offset(value.at("anchor")),detail::offset(value.at("caret"))}};}
    if(kind=="setChecked"){require_shape(value,{"kind","draft","checked"});return D::SetChecked{{detail::handle(value.at("draft"))},detail::boolean(value.at("checked"))};}
    if(kind=="setOption"){require_shape(value,{"kind","draft","node","selected"});return D::SetOption{{detail::handle(value.at("draft"))},detail::handle(value.at("node")),detail::boolean(value.at("selected"))};}
    require_shape(value,{"kind","draft"});const D::Draft draft{detail::handle(value.at("draft"))};
    if(kind=="apply")return D::Apply{draft};
    if(kind=="reload")return D::Reload{draft};
    if(kind=="reapply")return D::Reapply{draft};
    if(kind=="cancel")return D::Cancel{draft};
    if(kind=="finish")return D::Finish{draft};
    detail::invalid();
}
inline D::Intent parse_submit(const Json& value){
    surface_web::require_shape(value,{"type","version","intent"});
    if(surface_web::detail::text(value.at("type"),14,false)!="documentSubmit"||surface_web::detail::integer(value.at("version"),1)!=1)detail::invalid();
    (void)detail::checked(value,max_request_bytes);return parse_intent(value.at("intent"));
}
inline D::Ticket parse_take(const Json& value){
    surface_web::require_shape(value,{"type","version","ticket"});
    if(surface_web::detail::text(value.at("type"),12,false)!="documentTake"||surface_web::detail::integer(value.at("version"),1)!=1)detail::invalid();
    (void)detail::checked(value,max_request_bytes);return {detail::handle(value.at("ticket"))};
}
inline const char* admission(D::Admission value){return detail::enumeration(value,{{D::Admission::accepted,"accepted"},{D::Admission::busy,"busy"},{D::Admission::unavailable,"unavailable"},{D::Admission::stale,"stale"},{D::Admission::invalid,"invalid"},{D::Admission::limit,"limit"},{D::Admission::closed,"closed"}});}
inline Json json_draft(const D::DraftView& v){
    Json text=detail::text(v.text);if(v.selection.anchor>v.text.size()||v.selection.caret>v.text.size()||!gui_surface::valid_range(v.text,{std::min(v.selection.anchor,v.selection.caret),std::max(v.selection.anchor,v.selection.caret)}))detail::invalid();
    return Json::Object{{"id",detail::handle(v.id.value)},{"kind",detail::form_kind(v.kind)},{"phase",detail::draft_phase(v.phase)},{"text",std::move(text)},{"selection",Json::Object{{"anchor",double(v.selection.anchor)},{"caret",double(v.selection.caret)}}},{"checked",v.checked},{"dirty",v.dirty},{"applyQueued",v.apply_queued},{"option",v.option?Json{Json::Object{{"node",detail::handle(v.option->node)},{"selected",v.option->selected}}}:Json{}}};
}
inline Json json_state(const D::State& v){
    if(v.version!=1||(!v.publication_revision&&(v.observation||v.draft||v.document))||bool(v.observation)!=bool(v.document))detail::invalid();
    const auto phase=detail::enumeration(v.phase,{{D::Phase::idle,"idle"},{D::Phase::queued,"queued"},{D::Phase::waiting_native,"waitingNative"},{D::Phase::waiting_publication,"waitingPublication"},{D::Phase::waiting_ack,"waitingAck"},{D::Phase::waiting_take,"waitingTake"},{D::Phase::terminal,"terminal"}});
    return detail::checked(Json::Object{{"version",1},{"publicationRevision",std::to_string(v.publication_revision)},{"available",v.available},{"phase",phase},{"observation",detail::optional_handle(v.observation)},{"draft",v.draft?json_draft(*v.draft):Json{}},{"pending",detail::optional_handle(v.pending)},{"document",v.document?detail::document(*v.document):Json{}}},max_response_bytes);
}
inline Json json_completion(const D::Completion& v){return detail::checked(Json::Object{{"ticket",detail::handle(v.ticket.value)},{"outcome",detail::enumeration(v.outcome,{{D::Outcome::completed,"completed"},{D::Outcome::rejected,"rejected"},{D::Outcome::cancelled,"cancelled"},{D::Outcome::unknown,"unknown"}})},{"observation",detail::optional_handle(v.observation)},{"draft",v.draft?json_draft(*v.draft):Json{}},{"detail",detail::text(v.detail)}},max_response_bytes);}
inline Json json_reply(std::uint64_t sequence,bool take,D::Admission result,std::optional<D::Ticket> ticket,std::optional<D::Completion> completion={}){
    if(!sequence||(result==D::Admission::accepted)!=bool(ticket)||(completion&&(!take||!ticket||completion->ticket.value!=ticket->value)))detail::invalid();
    return Json::Object{{"sequence",detail::handle(sequence)},{"operation",take?"take":"submit"},{"admission",admission(result)},{"ticket",detail::optional_handle(ticket)},{"completion",completion?json_completion(*completion):Json{}}};
}
} // namespace foundation::host::document_web
