// SPDX-License-Identifier: CC0-1.0
#pragma once
#include "browser_surface_codec.hpp"
#include <foundation/gui/surface_editor.hpp>

namespace foundation::host::surface_editor_web {
namespace E = ::foundation::gui_editor;
using surface_web::Json;
namespace D = surface_web::detail;

inline bool null(const Json& value) noexcept { return std::holds_alternative<std::nullptr_t>(value.value); }
// Only consume a response produced by the retained WebSession serializer. Its
// large snapshot/surface values already exist as owned Json in the adapter; do
// not feed them back through the separate 1MiB incoming-operation parser.
inline Json response_metadata(std::string_view input) {
    if(input.size()>64u*1024u*1024u)D::invalid();
    std::size_t at=0;
    auto space=[&]{while(at<input.size()&&(input[at]==' '||input[at]=='\n'||input[at]=='\r'||input[at]=='\t'))++at;};
    auto string_end=[&]{
        if(at==input.size()||input[at++]!='"')D::invalid();
        while(at<input.size()){
            const char c=input[at++];
            if(c=='"')return;
            if(c=='\\'){if(at==input.size())D::invalid();++at;}
        }
        D::invalid();
    };
    space();if(at==input.size()||input[at++]!='{')D::invalid();
    Json::Object result;
    for(unsigned count=0;;++count){
        if(count>=7)D::invalid();
        space();const auto key_begin=at;string_end();
        const auto key=::gui::web_detail::Parser(input.substr(key_begin,at-key_begin)).parse().str();
        space();if(at==input.size()||input[at++]!=':')D::invalid();space();
        const auto begin=at;unsigned depth=0;
        while(at<input.size()){
            const char c=input[at];
            if(c=='"'){string_end();continue;}
            if(c=='{'||c=='['){if(++depth>64)D::invalid();++at;continue;}
            if(c=='}'||c==']'){if(!depth)break;--depth;++at;continue;}
            if(c==','&&!depth)break;
            ++at;
        }
        if(depth||at==input.size())D::invalid();
        Json value;
        if(key!="snapshot"&&key!="surface")value=::gui::web_detail::Parser(input.substr(begin,at-begin)).parse();
        if(!result.emplace(key,std::move(value)).second)D::invalid();
        if(input[at++]=='}')break;
    }
    space();if(at!=input.size())D::invalid();
    Json value{std::move(result)};
    surface_web::require_shape(value,{"epoch","ack","error","snapshot","surface","service","transfer"});
    return value;
}
inline std::optional<std::uint64_t> optional_id(const Json& value) {
    return null(value) ? std::nullopt : std::optional{D::decimal(value, true)};
}
inline E::Basis parse_basis(const Json& value) {
    surface_web::require_shape(value,{"token","identity","editorRevision","surrounding","selection","backward","composition"});
    E::Basis result{D::decimal(value.at("token"),true),D::identity(value.at("identity")),
        D::decimal(value.at("editorRevision"),true),D::text(value.at("surrounding"),65536),
        D::range(value.at("selection")),D::boolean(value.at("backward")),D::decimal(value.at("composition"))};
    if (!gui_surface::valid_range(result.surrounding,result.selection)) D::invalid();
    return result;
}
inline Json json_basis(const E::Basis& value) {
    return Json::Object{{"token",std::to_string(value.token)},{"identity",D::identity(value.identity)},
        {"editorRevision",std::to_string(value.editor_revision)},{"surrounding",value.surrounding},
        {"selection",D::range(value.selection)},{"backward",value.backward},{"composition",std::to_string(value.composition)}};
}
inline E::TextObservation parse_text(const Json& value) {
    surface_web::require_shape(value,{"value","selectionStart","selectionEnd","selectionDirection","selection","byteLength"});
    E::TextObservation result;
    result.value=D::text(value.at("value"),65536);
    result.selection_start=D::integer(value.at("selectionStart"),65536);
    result.selection_end=D::integer(value.at("selectionEnd"),65536);
    result.selection=D::range(value.at("selection"));
    result.byte_length=D::integer(value.at("byteLength"),65536);
    const auto& direction=D::text(value.at("selectionDirection"),8,false);
    if(direction=="forward")result.selection_direction=E::Direction::forward;
    else if(direction=="backward")result.selection_direction=E::Direction::backward;
    else if(direction=="none")result.selection_direction=E::Direction::none;
    else D::invalid();
    if(result.selection_start>result.selection_end||result.byte_length!=result.value.size()||
       !gui_surface::valid_range(result.value,result.selection))D::invalid();
    // Independently derive UTF-16 scalar boundaries from owned UTF-8 bytes.
    std::size_t unit=0;std::optional<std::size_t> begin,end;
    for(std::size_t i=0;;){
        if(unit==result.selection_start)begin=i;
        if(unit==result.selection_end)end=i;
        if(i==result.value.size())break;
        const auto c=static_cast<unsigned char>(result.value[i]);
        const auto count=c<0x80?1u:c<0xe0?2u:c<0xf0?3u:4u;
        i+=count;unit+=count==4?2:1;
    }
    if(!begin||!end||*begin!=result.selection.begin||*end!=result.selection.end)D::invalid();
    return result;
}
inline std::vector<std::uint64_t> source_groups(const Json& value) {
    const auto* array=std::get_if<Json::Array>(&value.value);
    if(!array||array->empty()||array->size()>8)D::invalid();
    std::vector<std::uint64_t> result;
    for(const auto& item:*array){auto id=D::decimal(item,true);if(std::find(result.begin(),result.end(),id)!=result.end())D::invalid();result.push_back(id);}
    return result;
}
inline E::KeyData parse_key(const Json& value,bool held=false) {
    const auto* object=std::get_if<Json::Object>(&value.value);if(!object)D::invalid();
    const bool grouped=held&&object->contains("group");
    if(grouped)surface_web::require_shape(value,{"phase","key","code","location","modifiers","repeat","isComposing","group"});
    else surface_web::require_shape(value,{"phase","key","code","location","modifiers","repeat","isComposing"});
    auto copy=std::get<Json::Object>(value.value);copy.emplace("kind","key");copy.erase("isComposing");
    if(grouped){(void)optional_id(value.at("group"));copy.erase("group");}
    E::KeyData result;result.transition=D::key(Json{std::move(copy)});result.is_composing=D::boolean(value.at("isComposing"));
    if(held&&result.transition.phase!=gui_surface::KeyPhase::down)D::invalid();
    return result;
}
inline E::Packet parse_packet(const Json& value) {
    surface_web::require_shape(value,{"type","session","basis","defaultToken","defaultDependencies","observation"});
    if(D::text(value.at("type"),17,false)!="editorObservation")D::invalid();
    E::Packet result;result.session=D::decimal(value.at("session"),true);result.basis=parse_basis(value.at("basis"));
    result.default_token=optional_id(value.at("defaultToken"));
    const auto* dependencies=std::get_if<Json::Array>(&value.at("defaultDependencies").value);
    if(!dependencies||dependencies->size()>8)D::invalid();
    for(const auto& dep:*dependencies){surface_web::require_shape(dep,{"group","token"});const auto group=D::decimal(dep.at("group"),true);
        if(std::any_of(result.default_dependencies.begin(),result.default_dependencies.end(),[&](const auto& old){return old.group==group;}))D::invalid();
        result.default_dependencies.push_back({group,D::decimal(dep.at("token"),true)});}
    const auto& raw=value.at("observation");surface_web::require_shape(raw,{"id","predecessor","kind","authority","group","groupEnd","transaction","before","after","data"});
    auto& observation=result.observation;observation.id=D::decimal(raw.at("id"),true);observation.predecessor=optional_id(raw.at("predecessor"));
    observation.group=optional_id(raw.at("group"));observation.group_end=D::boolean(raw.at("groupEnd"));observation.transaction=D::decimal(raw.at("transaction"));
    observation.before=parse_text(raw.at("before"));if(!null(raw.at("after")))observation.after=parse_text(raw.at("after"));
    const auto& authority=D::text(raw.at("authority"),11,false);
    if(authority=="native")observation.authority=E::Authority::native;
    else if(authority=="range")observation.authority=E::Authority::range;
    else if(authority=="default")observation.authority=E::Authority::default_action;
    else if(authority=="composition")observation.authority=E::Authority::composition;
    else D::invalid();
    const auto& kind=D::text(raw.at("kind"),11,false);const auto& data=raw.at("data");
    const auto* object=std::get_if<Json::Object>(&data.value);if(!object)D::invalid();const bool groups=object->contains("sourceGroups");
    if(kind=="key"){observation.kind=E::Kind::key;observation.data=parse_key(data);}
    else if(kind=="text"){
        if(groups)surface_web::require_shape(data,{"inputType","text","replacement","sourceGroups"});else surface_web::require_shape(data,{"inputType","text","replacement"});
        E::TextData text;text.input_type=D::text(data.at("inputType"),64,false);text.text=D::text(data.at("text"),65536);text.replacement=D::range(data.at("replacement"));
        if(!gui_surface::valid_range(observation.before.value,text.replacement))D::invalid();
        if(groups)text.source_groups=source_groups(data.at("sourceGroups"));
        observation.kind=E::Kind::text;observation.data=std::move(text);
    }else if(kind=="selection"){
        surface_web::require_shape(data,{"selection","backward"});E::SelectionData selection;selection.selection=D::range(data.at("selection"));selection.backward=D::boolean(data.at("backward"));
        if(!gui_surface::valid_range(observation.before.value,selection.selection))D::invalid();
        observation.kind=E::Kind::selection;observation.data=selection;
    }else if(kind=="composition"){
        E::CompositionData composition;const auto& op=D::text(data.at("operation"),6,false);
        if(op=="begin")composition.operation=gui_surface::CompositionOperation::begin;
        else if(op=="update")composition.operation=gui_surface::CompositionOperation::update;
        else if(op=="commit")composition.operation=gui_surface::CompositionOperation::commit;
        else if(op=="cancel")composition.operation=gui_surface::CompositionOperation::cancel;
        else D::invalid();
        if(op=="begin"){
            if(groups)surface_web::require_shape(data,{"operation","text","selection","replacement","sourceGroups"});else surface_web::require_shape(data,{"operation","text","selection","replacement"});
            composition.replacement=D::range(data.at("replacement"));
        }else surface_web::require_shape(data,{"operation","text","selection"});
        composition.text=D::text(data.at("text"),65536);composition.selection=D::range(data.at("selection"));
        if(!gui_surface::valid_range(composition.text,composition.selection)||(composition.replacement&&!gui_surface::valid_range(observation.before.value,*composition.replacement))||
            (composition.operation==gui_surface::CompositionOperation::cancel&&(!composition.text.empty()||composition.selection!=gui_surface::ByteRange{})))D::invalid();
        if(groups)composition.source_groups=source_groups(data.at("sourceGroups"));
        observation.kind=E::Kind::composition;observation.data=std::move(composition);
    }else D::invalid();
    return result;
}
inline E::Revocation parse_revocation(const Json& value) {
    surface_web::require_shape(value,{"reason","basis","composition","keys","incarnation"});
    E::Revocation result;result.reason=D::text(value.at("reason"),512);result.basis=parse_basis(value.at("basis"));
    result.incarnation=D::decimal(value.at("incarnation"),true);result.composition=optional_id(value.at("composition")).value_or(0);
    const auto* keys=std::get_if<Json::Array>(&value.at("keys").value);if(!keys||keys->size()>64)D::invalid();
    for(const auto& key:*keys)result.held_keys.push_back(parse_key(key,true));
    return result;
}
inline Json nullable(std::optional<std::uint64_t> value) { return value?Json{std::to_string(*value)}:Json{}; }
inline Json json_composition(const E::CompositionFact& value) {
    if(!value.transaction)D::invalid();
    const char* state=nullptr;
    switch(value.state){case E::CompositionState::pending:state="pending";break;case E::CompositionState::live:state="live";break;case E::CompositionState::ended:state="ended";break;default:D::invalid();}
    return Json::Object{{"transaction",std::to_string(value.transaction)},{"state",state}};
}
inline Json json_retirement(const E::RetirementReadback& value) {
    const char* availability=nullptr;
    switch(value.availability){case E::NativeAvailability::available:if(!value.authority_retired)D::invalid();availability="available";break;
        case E::NativeAvailability::noneditable:availability="noneditable";break;case E::NativeAvailability::unavailable:availability="unavailable";break;default:D::invalid();}
    if(!value.observation_revision||!value.readback_attested)D::invalid();
    (void)D::identity(D::identity(value.identity));
    Json result=Json::Object{{"availability",availability},{"identity",D::identity(value.identity)},
        {"observationRevision",std::to_string(value.observation_revision)},{"readbackAttested",true}};
    if(value.authority_retired)std::get<Json::Object>(result.value).emplace("authorityRetired",true);
    return result;
}
inline Json json_settlement(const E::Settlement& value) {
    if(!value.session||!value.id||!value.submitted_token||(value.predecessor&&!*value.predecessor))D::invalid();
    return Json::Object{{"session",std::to_string(value.session)},{"id",std::to_string(value.id)},
        {"predecessor",nullable(value.predecessor)},{"submittedToken",std::to_string(value.submitted_token)}};
}
inline Json json_settlement(const E::Receipt& value) {
    return json_settlement(E::Settlement{value.session,value.id,value.submitted_token,value.predecessor});
}
inline Json json_publication(const E::EditorPublication& value) {
    if(value.basis&&value.retirement)D::invalid();
    if(value.basis)(void)parse_basis(json_basis(*value.basis));
    return Json::Object{{"basis",value.basis?json_basis(*value.basis):Json{}},
        {"settlement",value.settlement?json_settlement(*value.settlement):Json{}},
        {"composition",value.composition?json_composition(*value.composition):Json{}},
        {"retirement",value.retirement?json_retirement(*value.retirement):Json{}}};
}
inline Json json_receipt(const E::Receipt& value) {
    (void)json_settlement(value);
    const char* outcome=nullptr;const char* continuity=nullptr;
    switch(value.outcome){case E::Outcome::applied:outcome="applied";break;case E::Outcome::cancelled:outcome="cancelled";break;case E::Outcome::rejected:outcome="rejected";break;case E::Outcome::unknown:outcome="unknown";break;default:D::invalid();}
    switch(value.continuity){case E::Continuity::same:continuity="same";break;case E::Continuity::key_retarget:continuity="key-retarget";break;case E::Continuity::replaced:continuity="replaced";break;default:D::invalid();}
    if(value.basis){(void)parse_basis(json_basis(*value.basis));if(value.retirement)D::invalid();}
    else if(value.outcome!=E::Outcome::unknown&&
        ((value.outcome!=E::Outcome::cancelled&&value.outcome!=E::Outcome::rejected&&value.outcome!=E::Outcome::applied)||value.continuity!=E::Continuity::replaced||
         value.default_token||(value.composition&&value.composition->state!=E::CompositionState::ended)||!value.retirement))D::invalid();
    Json token;if(value.default_token){if(!value.default_token->group||!value.default_token->token)D::invalid();
        token=Json::Object{{"group",std::to_string(value.default_token->group)},{"token",std::to_string(value.default_token->token)}};}
    return Json::Object{{"session",std::to_string(value.session)},{"id",std::to_string(value.id)},{"predecessor",nullable(value.predecessor)},
        {"submittedToken",std::to_string(value.submitted_token)},{"outcome",outcome},{"basis",value.basis?json_basis(*value.basis):Json{}},
        {"continuity",continuity},{"defaultToken",std::move(token)},{"composition",value.composition?json_composition(*value.composition):Json{}},
        {"retirement",value.retirement?json_retirement(*value.retirement):Json{}}};
}
inline Json json_completion(const E::EditorCompletion& value) {
    if(!value.ticket||value.result.detail.size()>4096||!gui_surface::valid_text(value.result.detail))D::invalid();
    const char* admission=nullptr;
    switch(value.result.admission){case E::Admission::completed:admission="completed";break;case E::Admission::rejected:admission="rejected";break;
        case E::Admission::busy:admission="busy";break;case E::Admission::unavailable:admission="unavailable";break;case E::Admission::terminal:admission="terminal";break;
        case E::Admission::awaiting_projection:admission="awaiting_projection";break;case E::Admission::prepared:admission="prepared";break;default:D::invalid();}
    return Json::Object{{"ticket",std::to_string(value.ticket)},{"admission",admission},
        {"receipt",value.result.receipt?json_receipt(*value.result.receipt):Json{}},{"detail",value.result.detail}};
}
} // namespace foundation::host::surface_editor_web
