#include "shared/appended_document_v2_codec.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <variant>
#include <vector>

namespace {
using namespace foundation::ui;
namespace F = foundation::appended;
using Bytes = std::vector<std::uint8_t>;
constexpr DocumentV2Identity identity{9,10,11};
constexpr F::FormVersion version{9,10,12};
constexpr std::uint64_t safe_integer = 9007199254740991ULL;
constexpr std::uint64_t wide = std::numeric_limits<std::uint64_t>::max();
std::size_t checks = 0;

void check(bool value, const char* message) {
    ++checks;
    if (!value) throw std::runtime_error(message);
}
template<class Function> void rejects(Function function, const char* message) {
    bool rejected = false;
    try { function(); } catch (const std::invalid_argument&) { rejected = true; }
    check(rejected,message);
}
Bytes hex(std::string_view text) {
    auto digit=[](char c)->unsigned {
        if (c>='0' && c<='9') return static_cast<unsigned>(c-'0');
        if (c>='a' && c<='f') return static_cast<unsigned>(c-'a'+10);
        throw std::runtime_error("Invalid fixed fixture hex");
    };
    check(text.size()%2==0,"Odd fixed fixture hex");
    Bytes bytes;
    for (std::size_t i=0;i<text.size();i+=2)
        bytes.push_back(static_cast<std::uint8_t>((digit(text[i])<<4)|digit(text[i+1])));
    return bytes;
}
void overwrite(Bytes& bytes, std::size_t position, std::uint64_t value, std::size_t count) {
    check(position<=bytes.size() && count<=bytes.size()-position,"Mutation exceeds fixed fixture");
    for (std::size_t i=0;i<count;++i) bytes[position+i]=static_cast<std::uint8_t>(value>>(8*i));
}

// Independent wire writers are confined to constructing test data. They use
// explicit schema tags, widths and ordering, never the consumer encoder.
struct Wire {
    Bytes bytes;
    void put(std::uint64_t value, std::size_t width) {
        for (std::size_t i=0;i<width;++i) bytes.push_back(static_cast<std::uint8_t>(value>>(8*i)));
    }
    void str(std::string_view text) { put(text.size(),4); bytes.insert(bytes.end(),text.begin(),text.end()); }
    void header(unsigned kind) { bytes={'N','D','V','2',2,0,static_cast<std::uint8_t>(kind),0}; }
    void id(DocumentV2Identity value) { put(value.application_instance,8); put(value.service_generation,8); put(value.document_sequence,8); }
    void ver(F::FormVersion value) { put(value.generation,8); put(value.epoch,8); put(value.revision,8); }
    void prefix(DocumentV2Identity value, std::uint64_t outer, std::uint64_t nested) { id(value); put(outer,8); put(nested,8); }
};
struct Node {
    std::uint64_t id{1}, parent{0};
    unsigned kind{1}, flags{0}, children{0};
    std::string tag{"div"}, text, name, value, href;
};
struct Metadata { std::uint64_t node; std::string role, display, whitespace; };
Bytes body_reply(const std::vector<Node>& nodes = {Node{}}, bool truncated = false,
                 std::uint64_t revision = 12, std::uint64_t editor_revision = 7,
                 DocumentV2Identity document = identity, std::uint64_t outer = 12,
                 std::uint64_t nested = 13, const std::vector<Metadata>& metadata = {},
                 std::uint32_t degradation = 0) {
    Wire w; w.header(4); w.prefix(document,outer,nested); w.id(document);
    w.ver({document.application_instance,document.service_generation,revision});
    w.put(truncated,1); w.put(editor_revision,8); w.put(0,8); w.put(0,4); w.put(degradation,4);
    w.put(nodes.size(),4); w.put(metadata.size(),4); w.put(0,4); w.put(0,1);
    for (const auto& n:nodes) {
        w.put(n.id,8); w.put(n.parent,8); w.put(n.kind,1); w.put(n.flags,1); w.put(n.children,4);
        for (const auto* s:{&n.tag,&n.text,&n.name,&n.value,&n.href}) w.str(*s);
    }
    for (const auto& m:metadata) { w.put(m.node,8); w.str(m.role); w.str(m.display); w.str(m.whitespace); }
    return std::move(w.bytes);
}
Node text_node(std::uint64_t id, std::uint64_t parent, std::string text) {
    Node n; n.id=id; n.parent=parent; n.kind=2; n.tag.clear(); n.text=std::move(text); return n;
}
DocumentFormsRequest query_source(DocumentV2Identity document = identity,
                                 std::uint64_t outer = 12, std::uint64_t nested = 13) {
    return {{document.application_instance,outer},DocumentEngineRequest{{document.application_instance,nested},{}}};
}
DocumentV2Request query(DocumentV2Identity document = identity,
                        std::uint64_t outer = 12, std::uint64_t nested = 13) {
    return encode_appended_document_v2(document,query_source(document,outer,nested));
}
DocumentFormsRequest command_source(F::FormAction action) {
    if (const auto* begin=std::get_if<F::BeginFormControl>(&action)) return {{9,12},*begin};
    if (const auto* finish=std::get_if<F::FinishFormControl>(&action)) return {{9,12},*finish};
    // This is a local modal lifetime; it is deliberately NOT native generation9.
    return {{9,12},F::FormDraftRequest{{41,42},std::move(action)}};
}
std::vector<F::FormAction> actions() {
    const F::FormLease text{{9,10,11},3,wide}, checked{{9,10,11},6,wide}, select{{9,10,11},8,wide};
    return {F::BeginFormControl{version,3},
        F::ReplaceFormText{text,{1,2,F::FormDirection::backward},"x\xf0\x9f\x99\x82"},
        F::SetFormChecked{checked,true},F::SetFormOption{select,103,true},
        F::OpenFormPopup{version,7},F::FinishFormControl{text}};
}
Bytes golden_action(unsigned tag) {
    Wire w; w.header(2); w.prefix(identity,12,0); w.put(tag,1);
    if (tag==0 || tag==4) { w.ver(version); w.put(tag==0?3:7,8); }
    else {
        w.ver({9,10,11}); w.put(tag==2?6:tag==3?8:3,8); w.put(wide,8);
        if (tag==1) { w.put(1,4); w.put(2,4); w.put(2,1); w.str("x\xf0\x9f\x99\x82"); }
        if (tag==2) w.put(1,1);
        if (tag==3) { w.put(103,8); w.put(1,1); }
    }
    return std::move(w.bytes);
}

// Fixed output of the separately frozen native portable codec, schema SHA256
// f11fd061350f8d663dbcdec7cf0a063e4fb0ff3564d285076690f58e8a84143d.
// 1593 bytes, SHA256334bdf7e03b52064a8263d1c29c1bbc073eb1af4d388cd53ba1aeab326bd03b1.
// This tracked test has no oracle header, link or ignored-path dependency.
Bytes rich_reply() {
    return hex(
        "4e4456320200040009000000000000000a000000000000000b000000000000000c00000000000000"
        "0d0000000000000009000000000000000a000000000000000b000000000000000900000000000000"
        "0a000000000000000c0000000000000000070000000000000003000000000000001f000000770000"
        "000d0000000500000009000000010200000000000000010100000002000000000000000103000000"
        "000100000000000000000000000000000001000c00000004000000626f6479000000000000000000"
        "0000000000000002000000000000000100000000000000020000000000000000000600000041f09f"
        "99824200000000000000000000000003000000000000000100000000000000010000000000050000"
        "00696e70757400000000040000004e616d6502000000686900000000040000000000000001000000"
        "0000000001000000000005000000696e70757400000000060000004e756d62657200000000000000"
        "00050000000000000001000000000000000100000000000800000074657874617265610000000005"
        "0000004e6f746573090000006c696e650a6e65787400000000060000000000000001000000000000"
        "0001000000000005000000696e707574000000000500000041677265650000000000000000070000"
        "000000000001000000000000000100000000000600000073656c65637400000000030000004f6e65"
        "0000000000000000080000000000000001000000000000000100000000000600000073656c656374"
        "00000000040000004d616e7900000000000000000900000000000000010000000000000001010000"
        "000005000000696e707574000000000000000000000000000000000a000000000000000100000000"
        "00000001020000000005000000696e707574000000000000000000000000000000000b0000000000"
        "0000010000000000000001000000000005000000696e7075740000000008000000526561646f6e6c"
        "79040000007361666500000000140000000000000000000000000000000100010000000700000073"
        "656374696f6e00000000000000000000000000000000150000000000000014000000000000000200"
        "0000000000000000100000007365636f6e6420706172616772617068000000000000000000000000"
        "0100000000000000040000006d61696e05000000626c6f636b080000007072652d77726170030000"
        "00000000000700000074657874626f780c000000696e6c696e652d626c6f636b060000006e6f726d"
        "616c060000000000000008000000636865636b626f780c000000696e6c696e652d626c6f636b0600"
        "00006e6f726d616c0b000000000000000700000074657874626f780c000000696e6c696e652d626c"
        "6f636b0c000000627265616b2d737061636573140000000000000006000000726567696f6e050000"
        "00626c6f636b030000007072650300000000000000002c1100000001010400000074657874040000"
        "004e616d6509000000000000000a000000000000000b000000000000000300000000000000ffffff"
        "ffffffffff0200000068690200000068690100000000020000000104000000000000000124110000"
        "000100060000006e756d626572060000004e756d62657200000000020000002d2e01020000000200"
        "00000005000000000000000224110000000100080000007465787461726561050000004e6f746573"
        "090000006c696e650a6e657874090000006c696e650a6e6578740100000000090000000206000000"
        "00000000032412000000020008000000636865636b626f7805000000416772656501010700000000"
        "00000004241400000003000a00000073656c6563742d6f6e65030000004f6e650202000000650000"
        "000000000001050000006669727374660000000000000002060000007365636f6e64080000000000"
        "000005241800000003000f00000073656c6563742d6d756c7469706c65040000004d616e79010200"
        "000067000000000000000105000000746869726468000000000000000006000000666f7572746809"
        "0000000000000006220000000000000800000070617373776f7264000000000a0000000000000007"
        "100000000000000400000066696c65000000000b0000000000000000260000000001000500000065"
        "6d61696c08000000526561646f6e6c790400000073616665040000007361666500"
    );
}
const DocumentV2Publication& publication(const DocumentV2Reply& value) {
    check(value.publication.has_value(),"Successful reply lost its paired publication");
    return *value.publication;
}
const F::FormControl& control(const DocumentV2Reply& value, std::uint64_t id) {
    const auto& controls=publication(value).observation.forms.controls;
    const auto found=std::find_if(controls.begin(),controls.end(),[&](const auto& c){return c.node==id;});
    check(found!=controls.end(),"Expected native form descriptor is absent"); return *found;
}
const DocumentNode& node(const DocumentV2Reply& value, std::uint64_t id) {
    const auto& snapshot=publication(value).observation.body.snapshot;
    check(snapshot.has_value(),"Successful reply lost its body");
    const auto found=std::find_if(snapshot->nodes.begin(),snapshot->nodes.end(),[&](const auto& n){return n.id==id;});
    check(found!=snapshot->nodes.end(),"Expected native body node is absent"); return *found;
}
Bytes completion(unsigned outcome, unsigned code, unsigned flags, const Bytes* reply = nullptr) {
    Wire w; w.header(5); w.prefix(identity,12,0);
    w.put(outcome,1); w.put(code,1); w.put(flags,1); w.put(reply!=nullptr,1);
    if (reply) {
        check(reply->size()>=48,"Invalid test completion publication source");
        w.bytes.insert(w.bytes.end(),reply->begin()+48,reply->end());
    }
    return std::move(w.bytes);
}
void malformed(Bytes bytes) {
    rejects([&]{(void)decode_appended_document_v2(bytes,query());},"Invalid native-v2 reply was accepted");
}

void golden_queries_and_actions() {
    const auto expected=hex("4e4456320200010009000000000000000a000000000000000b000000000000000c000000000000000d00000000000000");
    const auto encoded=query();
    check(encoded.bytes==expected && encoded.bytes.size()==48,"Query differs from independent fixed golden");
    check(encoded.identity==identity && encoded.kind==DocumentV2RequestKind::snapshot_query &&
          encoded.source.token==DocumentFormsRequestToken{9,12},"Query context was remapped");
    const auto values=actions();
    constexpr std::array<std::size_t,6> sizes{81,107,90,98,81,89};
    for (std::size_t i=0;i<values.size();++i) {
        const auto request=encode_appended_document_v2(identity,command_source(values[i]));
        check(request.bytes==golden_action(static_cast<unsigned>(i)),"Form action differs from independent golden bytes");
        check(request.bytes.size()==sizes[i] && request.kind==DocumentV2RequestKind::form_command,
              "Form action length or kind changed");
        check(request.bytes[40]==0 && request.bytes[48]==i,"Form action fabricated nested document correlation or changed tag");
        if (i>0 && i<5)
            check(std::get<F::FormDraftRequest>(request.source.action).token==F::FormDraftToken{41,42},
                  "Local draft token was conflated with the native session");
    }
    // Range1..2 cannot be checked against the ABSENT old buffer here. New text
    // contains a supplementary scalar; its scalar boundaries are unrelated.
    check(encode_appended_document_v2(identity,command_source(values[1])).bytes==golden_action(1),
          "Encoder invented an old-buffer scalar-boundary check");
}

void minimal_empty_and_forests() {
    const auto fixed=hex("4e4456320200040009000000000000000a000000000000000b000000000000000c000000000000000d0000000000000009000000000000000a000000000000000b0000000000000009000000000000000a000000000000000c00000000000000000c000000000000000000000000000000000000000000000001000000000000000000000000010000000000000000000000000000000100000000000300000064697600000000000000000000000000000000");
    check(fixed.size()==179,"Minimal fixed reply fixture changed");
    const auto decoded=decode_appended_document_v2(fixed,query());
    const auto& p=publication(decoded);
    check(decoded.token==DocumentFormsRequestToken{9,12} && !decoded.control && !decoded.action_status,
          "Query reply acquired form-completion fields");
    check(p.observation.protocol==2 && p.observation.publication==version && p.observation.forms.version==version &&
          p.observation.body.request_id==13 && p.observation.body.epoch==10,
          "Minimal reply did not preserve exact paired identities");
    check(node(decoded,1).tag=="div" && p.observation.forms.controls.empty() && !p.selection,
          "Minimal native root was altered");
    for (bool truncated:{false,true}) {
        const auto empty=decode_appended_document_v2(body_reply({},truncated,12,7,identity,12,13,{},truncated?8:0),query());
        const auto& b=*publication(empty).observation.body.snapshot;
        check(b.nodes.empty() && !b.active_node && !b.selection && b.truncated==truncated &&
              publication(empty).observation.forms.controls.empty(),"Empty native forest acquired synthetic state");
    }
    Node first; first.id=40; Node second; second.id=90; second.tag="section";
    const auto forest=decode_appended_document_v2(body_reply({first,second}),query());
    check(node(forest,40).parent==0 && node(forest,90).parent==0 &&
          publication(forest).observation.body.snapshot->nodes.size()==2,"Native forest was wrapped in an invented root");
}

void rich_joined_values() {
    auto wire=rich_reply(); check(wire.size()==1593,"Fixed rich native fixture changed");
    const auto result=decode_appended_document_v2(wire,query()); const auto& p=publication(result);
    const auto& body=p.observation.body;
    check(body.snapshot.has_value(),"Rich paired publication lost its body snapshot");
    const auto& snapshot=*body.snapshot;
    check(snapshot.version==DocumentVersion{9,10,12} && snapshot.nodes.size()==13 &&
          p.observation.forms.controls.size()==9 && p.observation.publication==p.observation.forms.version,
          "Rich native publication was split or narrowed");
    check(body.editor_state && body.editor_state->revision==7 && body.editor_state->flags==31 &&
          snapshot.active_node==3 && p.native_degradation==119,"Native editor or degradation state was lost");
    check(node(result,2).kind==DocumentNodeKind::text && node(result,2).text=="A\xf0\x9f\x99\x82" "B" &&
          node(result,20).parent==0 && node(result,21).parent==20,"Unicode text or second root changed");
    check(node(result,1).white_space==DocumentWhiteSpace::pre_wrap && node(result,20).white_space==DocumentWhiteSpace::pre &&
          node(result,11).white_space==DocumentWhiteSpace::pre_wrap && body.degraded.whitespace,
          "Computed whitespace or explicit fallback degradation was lost");
    check(p.selection && !p.selection->focus_rect && !body.original_selection && snapshot.selection &&
          snapshot.selection->anchor==DocumentPoint{2,1} && snapshot.selection->focus==DocumentPoint{2,3},
          "Absent native geometry was fabricated or valid text selection lost");
    check(p.selection->endpoints.anchor.kind==DocumentNativeOffsetKind::text_utf16,
          "Native text endpoint enum was copied with the wrong ordinal");
    check(control(result,3).lease==F::FormLease{{9,10,11},3,wide},"Older valid lease was rebased or opaque ID narrowed");
    const auto& number=std::get<F::FormTextState>(control(result,4).state);
    check(number.value.empty() && number.editing_text=="-." && node(result,4).value.empty(),
          "Numeric canonical value was replaced with native editing text");
    check(std::get<F::FormTextState>(control(result,5).state).value=="line\nnext" &&
          std::get<F::FormCheckState>(control(result,6).state)==F::FormCheckState{true,true},
          "Textarea or native indeterminate checkbox state was lost");
    check(control(result,7).kind==F::FormKind::select_one && control(result,8).kind==F::FormKind::select_many &&
          std::get<F::FormSelectState>(control(result,7).state).options[1].disabled &&
          std::get<F::FormSelectState>(control(result,8).state).options[0].node==103,
          "Native select state, option identity or capability kind changed");
    const auto& secure=control(result,9);
    check(node(result,9).masked && node(result,9).value.empty() && node(result,9).name.empty() &&
          secure.kind==F::FormKind::secure_readonly && std::holds_alternative<std::monostate>(secure.state) &&
          secure.label.empty() && !secure.lease && secure.capabilities==0,"Secure marker acquired state or authority");
    check(node(result,10).omitted && control(result,10).omitted && control(result,10).kind==F::FormKind::unsupported,
          "Omitted native descriptor was promoted to editable state");
    check(control(result,11).read_only && control(result,11).capabilities==0 && node(result,11).value=="safe",
          "Safe readonly canonical value was concealed or granted authority");
    const auto& metadata=body.metadata;
    const auto readonly=std::find_if(metadata.begin(),metadata.end(),[](const auto& m){return m.node==11;});
    const auto checked=std::find_if(metadata.begin(),metadata.end(),[](const auto& m){return m.node==6;});
    check(readonly!=metadata.end() && readonly->read_only && readonly->white_space=="break-spaces" &&
          checked!=metadata.end() && checked->checked,"Same-native-control readonly/checked metadata was not preserved");
    wire.assign(wire.size(),0);
    check(node(result,2).text=="A\xf0\x9f\x99\x82" "B","Decoded values alias caller-owned packet bytes");
}

void native_selection_representations() {
    auto element=rich_reply();
    overwrite(element,134,1,8); overwrite(element,142,2,1); overwrite(element,143,12,4);
    overwrite(element,147,1,8); overwrite(element,155,2,1); overwrite(element,156,12,4);
    const auto selected=decode_appended_document_v2(element,query()); const auto& e=publication(selected);
    check(e.selection && e.selection->endpoints.anchor.kind==DocumentNativeOffsetKind::element_child_index &&
          e.selection->endpoints.anchor.offset==12 && !e.observation.body.snapshot->selection &&
          e.observation.body.degraded.element_selection,"Actual child endpoint was inferred from projected children");
    auto bad=element; overwrite(bad,143,13,4); malformed(std::move(bad));
    bad=rich_reply(); overwrite(bad,143,2,4); malformed(std::move(bad));
    bad=rich_reply(); overwrite(bad,142,3,1); malformed(std::move(bad));
    bad=rich_reply(); overwrite(bad,134,9,8); malformed(std::move(bad));

    auto geometry=rich_reply(); Wire rect;
    for (double d:{1.0e12,-2.5,0.0,16.0}) rect.put(std::bit_cast<std::uint64_t>(d),8);
    overwrite(geometry,160,1,1); geometry.insert(geometry.begin()+161,rect.bytes.begin(),rect.bytes.end());
    const auto observed=decode_appended_document_v2(geometry,query()); const auto& p=publication(observed);
    check(p.selection && p.selection->focus_rect && p.selection->focus_rect->x==1.0e12 &&
          p.selection->focus_rect->y==-2.5 && p.selection->focus_rect->width==0 &&
          p.observation.body.original_selection && p.observation.body.original_selection->focus_rect.height==16,
          "Finite native observation geometry was lost or constrained as widget geometry");
    bad=geometry; overwrite(bad,161,std::bit_cast<std::uint64_t>(std::numeric_limits<double>::infinity()),8); malformed(std::move(bad));
    bad=geometry; overwrite(bad,177,std::bit_cast<std::uint64_t>(-1.0),8); malformed(std::move(bad));
    bad=rich_reply(); overwrite(bad,117,127,4); malformed(std::move(bad));
    bad=rich_reply(); overwrite(bad,96,1,1); malformed(std::move(bad));
}

void completion_outcomes_and_readback() {
    const auto values=actions(); const auto request=encode_appended_document_v2(identity,command_source(values[0]));
    const auto rich=rich_reply();
    const auto accepted=decode_appended_document_v2(completion(0,0,1,&rich),request);
    check(accepted.token==DocumentFormsRequestToken{9,12} && accepted.control && accepted.action_status &&
          accepted.control->outcome==F::FormDraftOutcome::accepted && accepted.control->update &&
          accepted.control->update->control.node==3 && accepted.control->update->version==version &&
          accepted.control->update->control.lease==F::FormLease{{9,10,11},3,wide},"Accepted completion lost exact native readback");
    check(publication(accepted).observation.body.request_id==0 && accepted.action_status->effects_entered &&
          accepted.action_status->code==DocumentV2CompletionCode::ok,"Form readback fabricated a document-query token");
    const auto unknown=decode_appended_document_v2(completion(2,8,1),request);
    check(unknown.control && unknown.control->outcome==F::FormDraftOutcome::unknown && !unknown.control->update &&
          !unknown.publication && unknown.action_status && unknown.action_status->effects_entered &&
          unknown.action_status->code==DocumentV2CompletionCode::readback_failed,"Unknown post-effect result was relabeled or given invented state");
    for (unsigned code=0;code<=8;++code) {
        const auto rejected=decode_appended_document_v2(completion(1,code,0),request);
        check(rejected.control && rejected.control->outcome==F::FormDraftOutcome::rejected &&
              !rejected.control->update && !rejected.publication && rejected.action_status &&
              !rejected.action_status->effects_entered && static_cast<unsigned>(rejected.action_status->code)==code,
              "Native no-effects rejection code was discarded");
    }
    const auto empty=body_reply();
    const auto missing=decode_appended_document_v2(completion(0,0,1,&empty),request);
    check(missing.control && missing.control->outcome==F::FormDraftOutcome::accepted && !missing.control->update &&
          missing.publication,"Missing native target acquired an invented FormUpdate");
    const auto popup_request=encode_appended_document_v2(identity,command_source(values[4]));
    const auto popup=decode_appended_document_v2(completion(0,0,3,&rich),popup_request);
    check(popup.action_status && popup.action_status->popup_opened && popup.control && popup.control->update &&
          popup.control->update->control.node==7,
          "Popup evidence or action-specific update target was lost");
    for (const auto& bad:{completion(0,0,0),completion(0,1,1,&rich),completion(1,8,1),completion(2,8,2),
                         completion(3,0,0),completion(1,9,0),completion(1,1,4)})
        rejects([&]{(void)decode_appended_document_v2(bad,request);},"Invalid completion status/effect/readback combination accepted");
    auto bad=completion(1,1,0); overwrite(bad,40,13,8);
    rejects([&]{(void)decode_appended_document_v2(bad,request);},"Form completion accepted fabricated nested document correlation");
    bad=completion(0,0,1,&rich); overwrite(bad,52,8,8);
    rejects([&]{(void)decode_appended_document_v2(bad,request);},"Form completion accepted foreign publication identity");
    rejects([&]{(void)decode_appended_document_v2(rich,request);},"Form request accepted a query reply envelope");
    rejects([&]{(void)decode_appended_document_v2(completion(0,0,1,&rich),query());},"Query accepted a form completion envelope");
}

void exact_request_context_and_input_rejection() {
    const auto wire=rich_reply(); const auto canonical=query();
    auto bad=canonical; bad.bytes[8]^=1;
    rejects([&]{(void)decode_appended_document_v2(wire,bad);},"Changed owned request bytes were trusted");
    bad=canonical; bad.identity.document_sequence++;
    rejects([&]{(void)decode_appended_document_v2(wire,bad);},"Changed expected identity was trusted");
    bad=canonical; bad.source.token.sequence++;
    rejects([&]{(void)decode_appended_document_v2(wire,bad);},"Changed outer source token was trusted");
    bad=canonical; bad.kind=DocumentV2RequestKind::form_command;
    rejects([&]{(void)decode_appended_document_v2(wire,bad);},"Changed expected request kind was trusted");
    bad=canonical; std::get<DocumentEngineRequest>(bad.source.action).token.id++;
    rejects([&]{(void)decode_appended_document_v2(wire,bad);},"Changed nested controller token was trusted");
    for (std::size_t offset:{8u,16u,24u,32u,40u,48u,56u,64u}) {
        auto changed=wire; overwrite(changed,offset,99,8); malformed(std::move(changed));
    }
    for (const auto document:{DocumentV2Identity{0,10,11},DocumentV2Identity{9,0,11},DocumentV2Identity{9,10,0}})
        rejects([&]{(void)encode_appended_document_v2(document,query_source(document));},"Zero native identity encoded");
    auto source=query_source(); source.token.sequence=0;
    rejects([&]{(void)encode_appended_document_v2(identity,source);},"Zero outer sequence encoded");
    source=query_source(); source.token.generation=8;
    rejects([&]{(void)encode_appended_document_v2(identity,source);},"Outer generation remapped to native instance");
    source=query_source(); std::get<DocumentEngineRequest>(source.action).token.generation=8;
    rejects([&]{(void)encode_appended_document_v2(identity,source);},"Nested controller generation remapped");
    source=query_source(); std::get<DocumentEngineRequest>(source.action).token.id=0;
    rejects([&]{(void)encode_appended_document_v2(identity,source);},"Zero nested query token encoded");
    for (const auto action:{DocumentAction::focus,DocumentAction::activate,DocumentAction::select}) {
        source=query_source(); std::get<DocumentEngineRequest>(source.action).intent=DocumentIntent{{9,10,12},action,3,{}};
        rejects([&]{(void)encode_appended_document_v2(identity,source);},"Unsupported body intent was fabricated as native-v2 form action");
    }
    auto values=actions();
    std::get<F::BeginFormControl>(values[0]).expected.generation=8;
    rejects([&]{(void)encode_appended_document_v2(identity,command_source(values[0]));},"Foreign action version encoded");
    auto replace=std::get<F::ReplaceFormText>(values[1]); replace.range={3,2,F::FormDirection::none};
    rejects([&]{(void)encode_appended_document_v2(identity,command_source(replace));},"Reversed native action range encoded");
    replace=std::get<F::ReplaceFormText>(values[1]); replace.range.end=2049;
    rejects([&]{(void)encode_appended_document_v2(identity,command_source(replace));},"Unbounded native action range encoded");
    replace=std::get<F::ReplaceFormText>(values[1]); replace.expected.id=0;
    rejects([&]{(void)encode_appended_document_v2(identity,command_source(replace));},"Zero native lease encoded");
    replace=std::get<F::ReplaceFormText>(values[1]); replace.text=std::string("a\0b",3);
    rejects([&]{(void)encode_appended_document_v2(identity,command_source(replace));},"NUL replacement text encoded");
}

void malformed_framing_and_primitive_fields() {
    const auto wire=rich_reply(); const auto expected=query();
    for (std::size_t size=0;size<wire.size();++size)
        rejects([&]{(void)decode_appended_document_v2(std::span<const std::uint8_t>(wire).first(size),expected);},
                "Truncated native-v2 packet accepted");
    auto bad=wire; bad.push_back(0); malformed(std::move(bad));
    for (std::size_t offset=0;offset<8;++offset) { bad=wire; bad[offset]^=0xff; malformed(std::move(bad)); }
    const auto request=encode_appended_document_v2(identity,command_source(actions()[0]));
    const auto complete=completion(0,0,1,&wire);
    for (std::size_t size=0;size<complete.size();++size)
        rejects([&]{(void)decode_appended_document_v2(std::span<const std::uint8_t>(complete).first(size),request);},
                "Truncated native-v2 completion accepted");
    for (const auto& [position,value]:std::array<std::pair<std::size_t,unsigned>,19>{{
            {96,2},{113,32},{117,128},{133,2},{142,3},{160,2},
            {177,3},{178,16},{1061,8},{1062,64},{1067,4},{1068,2},
            {1137,2},{1146,3},{1313,2},{1352,4},{1365,8},{1539+9,64},{1592,2}}}) {
        bad=wire; overwrite(bad,position,value,1); malformed(std::move(bad));
    }
    for (const auto position:{121u,125u,129u}) { bad=wire; overwrite(bad,position,2049,4); malformed(std::move(bad)); }
    for (const auto position:{183u,233u,848u,1069u,1353u}) {
        bad=wire; overwrite(bad,position,0xffffffffU,4); malformed(std::move(bad));
    }
    bad.assign(max_document_v2_reply_bytes+1,0); malformed(std::move(bad));
}

void strict_native_cross_joins_and_redaction() {
    const auto wire=rich_reply();
    for (const auto& [position,value,width]:std::array<std::array<std::uint64_t,3>,17>{{
            {207,1,8},{215,3,8},{161+18,9,4},{255+17,4,1},{281,'x',1},{294,'X',1},{302,'H',1},
            {877,1,8},{922,999,8},{1053,2,8},{580+17,0,1},{1479+10,1,4},
            {1511+9,0,1},{1531,'a',1},{1532,'b',1},{1539+10,17,4},{1383,3,1}}}) {
        auto bad=wire; overwrite(bad,static_cast<std::size_t>(position),value,static_cast<std::size_t>(width)); malformed(std::move(bad));
    }
    auto bad=wire; overwrite(bad,1375,101,8); malformed(std::move(bad));
    bad=wire; overwrite(bad,1365,5,1); malformed(std::move(bad));
    bad=wire; overwrite(bad,1085+16,13,8); malformed(std::move(bad));
    bad=wire; overwrite(bad,1085+24,4,8); malformed(std::move(bad));
    bad=wire; overwrite(bad,1507,1,4); bad.insert(bad.begin()+1511,'x'); malformed(std::move(bad));
    bad=wire; overwrite(bad,615,1,4); bad.insert(bad.begin()+619,'x'); malformed(std::move(bad));
    bad=wire;
    Bytes swapped; swapped.insert(swapped.end(),wire.begin()+1147,wire.begin()+1203);
    swapped.insert(swapped.end(),wire.begin()+1053,wire.begin()+1147);
    std::copy(swapped.begin(),swapped.end(),bad.begin()+1053); malformed(std::move(bad));
    Node first; first.children=1; Node child; child.id=2; child.parent=1; Node second; second.id=3;
    malformed(body_reply({first,child,second,text_node(4,1,"reentered closed subtree")}));
    auto missing=wire; overwrite(missing,129,0,4); missing.resize(1053); malformed(std::move(missing));
}

void bounded_unicode_and_independent_pools() {
    Node root; root.children=1;
    const auto field=[&](std::string value){return body_reply({root,text_node(2,1,std::move(value))});};
    for (const auto& invalid:{std::string("\0",1),std::string("\xc0\x80",2),std::string("\xed\xa0\x80",3),
                             std::string("\xf4\x90\x80\x80",4),std::string("\xf0\x9f",2)}) malformed(field(invalid));
    check(node(decode_appended_document_v2(field(std::string(2048,'x')),query()),2).text.size()==2048,
          "Exact UTF16 field boundary rejected");
    malformed(field(std::string(2049,'x')));
    std::string bmp, supplementary;
    for (unsigned i=0;i<2048;++i) bmp+="\xe0\xa0\x80";
    for (unsigned i=0;i<1024;++i) supplementary+="\xf0\x9f\x99\x82";
    check(node(decode_appended_document_v2(field(bmp),query()),2).text.size()==6144,
          "Exact maximum scalar UTF8 field rejected");
    check(node(decode_appended_document_v2(field(supplementary),query()),2).text.size()==4096,
          "Supplementary scalars charged as bytes rather than UTF16 units");
    supplementary+="\xf0\x9f\x99\x82"; malformed(field(supplementary));
    std::vector<Node> nodes; root.children=33; nodes.push_back(root);
    for (unsigned i=0;i<32;++i) nodes.push_back(text_node(i+2,1,std::string(2048,'x')));
    check(publication(decode_appended_document_v2(body_reply(nodes),query())).observation.body.snapshot->nodes.size()==33,
          "Exact independent body text pool rejected");
    nodes.push_back(text_node(34,1,"x")); malformed(body_reply(nodes));
    nodes.clear();
    for (unsigned i=0;i<32;++i) { Node n; n.id=i+1; n.tag=std::string(2048,'x'); nodes.push_back(std::move(n)); }
    check(publication(decode_appended_document_v2(body_reply(nodes),query())).observation.body.snapshot->nodes.size()==32,
          "Exact metadata/tag pool rejected");
    malformed(body_reply(nodes,false,12,7,identity,12,13,{{1,"x","",""}}));
    nodes.clear();
    for (unsigned i=0;i<256;++i) { Node n; n.id=i+1; n.parent=i; n.children=i==255?0:1; nodes.push_back(n); }
    check(publication(decode_appended_document_v2(body_reply(nodes),query())).observation.body.snapshot->nodes.size()==256,
          "Exact native tree depth rejected");
    nodes.back().children=1; Node extra; extra.id=257; extra.parent=256; nodes.push_back(extra); malformed(body_reply(nodes));
    root.children=8192; Node child; child.id=2; child.parent=1;
    check(publication(decode_appended_document_v2(body_reply({root,child}),query())).observation.body.snapshot->nodes.size()==2,
          "Actual unpublished child count was replaced with projected count");
    child.children=1; malformed(body_reply({root,child}));
}

void representability_and_full_width_opaque_values() {
    Node root; root.id=safe_integer;
    const DocumentV2Identity document{wide,std::numeric_limits<std::uint32_t>::max(),wide};
    const auto request=query(document,wide,safe_integer);
    const auto result=decode_appended_document_v2(body_reply({root},false,safe_integer,INT32_MAX,document,wide,safe_integer),request);
    check(result.token==DocumentFormsRequestToken{wide,wide} && publication(result).observation.publication.generation==wide &&
          publication(result).observation.publication.revision==safe_integer && node(result,safe_integer).id==safe_integer &&
          publication(result).observation.body.request_id==safe_integer,
          "Full64 opaque context or exact consumer boundary lost precision");
    malformed(body_reply({Node{}},false,safe_integer+1));
    malformed(body_reply({Node{}},false,12,std::uint64_t(INT32_MAX)+1));
    root.id=safe_integer+1; malformed(body_reply({root}));
    auto bad=rich_reply(); overwrite(bad,1357,safe_integer+1,8); malformed(std::move(bad));
    rejects([&]{(void)query(identity,12,safe_integer+1);},"Unrepresentable nested controller token encoded");
    const DocumentV2Identity epoch_overflow{9,std::uint64_t(UINT32_MAX)+1,11};
    rejects([&]{(void)query(epoch_overflow);},"Unrepresentable native epoch encoded");
    const auto values=actions(); auto source=command_source(values[1]); source.token.sequence=wide;
    const auto action=encode_appended_document_v2(identity,source);
    check(action.bytes[32]==255 && action.bytes[39]==255 && action.bytes[81]==255 && action.bytes[88]==255,
          "Opaque outer sequence or lease ID narrowed during encoding");
}

void truncated_forms_are_observations_only() {
    auto wire=rich_reply(); overwrite(wire,96,1,1); overwrite(wire,133,0,1);
    wire.erase(wire.begin()+134,wire.begin()+161);
    malformed(wire); // Selection is gone; retained capabilities alone are invalid.
    constexpr std::array<std::size_t,9> starts{1053,1147,1203,1276,1315,1394,1479,1511,1539};
    for (auto start:starts) overwrite(wire,start-27+10,0,4);
    overwrite(wire,1068-27,0,1); wire.erase(wire.begin()+1085-27,wire.begin()+1125-27);
    const auto result=decode_appended_document_v2(wire,query());
    check(publication(result).observation.body.snapshot->truncated && !publication(result).selection,
          "Valid truncated paired observation lost truncation state");
    for (const auto& c:publication(result).observation.forms.controls)
        check(c.capabilities==0 && !c.lease,"Truncated native observation granted editing authority");
    check(node(result,11).value=="safe","Truncation discarded safe readonly observed value");
}

// Independent wire writer exercises the ACTUAL GUI consumer, including the
// former blanket omitted-option authority refusal.
Bytes opaque_popup_reply(unsigned caps=20,bool multiple=false,bool menu=true,
                         std::string hidden_label={},bool complete=true,bool truncated=false) {
    Wire w;w.header(4);w.prefix(identity,12,13);w.id(identity);w.ver(version);
    w.put(truncated,1);w.put(1,8);w.put(0,8);w.put(0,4);w.put(0,4);
    w.put(1,4);w.put(0,4);w.put(1,4);w.put(0,1);
    w.put(1,8);w.put(0,8);w.put(1,1);w.put(0,1);w.put(3,4);
    for(const auto& text:{std::string("select"),std::string(),std::string("Visible menu"),std::string(),std::string()})w.str(text);
    w.put(1,8);w.put(multiple?5:4,1);w.put(4|(complete?32:0),1);w.put(caps,4);w.put(3,1);w.put(0,1);
    w.str(multiple?"select-multiple":"select-one");w.str("Visible menu");w.put((multiple?1:0)|(menu?2:0),1);w.put(3,4);
    w.put(2,8);w.put(1,1);w.str("Alpha");w.put(3,8);w.put(4,1);w.str(hidden_label);w.put(4,8);w.put(0,1);w.str("Omega");
    return std::move(w.bytes);
}
void opaque_single_popup_is_complete_but_redacted_and_never_a_multiselect_edit() {
    for(unsigned caps:{0u,4u,16u,20u}){
        const auto result=decode_appended_document_v2(opaque_popup_reply(caps),query());
        const auto& c=control(result,1);const auto& options=std::get<F::FormSelectState>(c.state).options;
        check(c.complete&&c.capabilities==caps&&options[1].omitted&&options[1].label.empty()&&options[0].selected,
            "GUI native codec lost complete redacted popup or manufactured option text");
    }
    for(auto wire:{opaque_popup_reply(20,false,true,"leak"),opaque_popup_reply(8),
        opaque_popup_reply(8,true,false),opaque_popup_reply(0,true,true),
        opaque_popup_reply(20,false,false),opaque_popup_reply(20,false,true,{},false),
        opaque_popup_reply(20,false,true,{},true,true)})
        rejects([&]{decode_appended_document_v2(wire,query());},"GUI accepted redacted non-popup authority or leaked option text");
    const auto old=decode_appended_document_v2(opaque_popup_reply(0,false,true,{},false),query());
    check(!control(old,1).complete&&!control(old,1).capabilities,"Original cap-free incomplete observation rejected");
}

} // namespace

int main() {
    const std::array<std::pair<std::string_view,void(*)()>,12> tests{{
        {"opaque_single_popup_is_complete_but_redacted_and_never_a_multiselect_edit",opaque_single_popup_is_complete_but_redacted_and_never_a_multiselect_edit},
        {"golden_queries_and_actions",golden_queries_and_actions},
        {"minimal_empty_and_forests",minimal_empty_and_forests},
        {"rich_joined_values",rich_joined_values},
        {"native_selection_representations",native_selection_representations},
        {"completion_outcomes_and_readback",completion_outcomes_and_readback},
        {"exact_request_context_and_input_rejection",exact_request_context_and_input_rejection},
        {"malformed_framing_and_primitive_fields",malformed_framing_and_primitive_fields},
        {"strict_native_cross_joins_and_redaction",strict_native_cross_joins_and_redaction},
        {"bounded_unicode_and_independent_pools",bounded_unicode_and_independent_pools},
        {"representability_and_full_width_opaque_values",representability_and_full_width_opaque_values},
        {"truncated_forms_are_observations_only",truncated_forms_are_observations_only}}};
    unsigned failed=0;
    for (const auto& [name,test]:tests) {
        try { test(); std::cout<<"PASS "<<name<<'\n'; }
        catch (const std::exception& e) { ++failed; std::cerr<<"FAIL "<<name<<": "<<e.what()<<'\n'; }
    }
    std::cout<<"SUMMARY cases="<<tests.size()<<" failed="<<failed<<" checks="<<checks<<'\n';
    return failed?1:0;
}
