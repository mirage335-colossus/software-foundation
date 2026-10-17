// SPDX-License-Identifier: CC0-1.0
#include "shared/document_action_v1_codec.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <cstdint>
#include <iostream>
#include <limits>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace {
using namespace foundation::ui;
namespace F = foundation::appended;
using Bytes = std::vector<std::uint8_t>;
constexpr std::uint64_t safe_integer = 9007199254740991ULL;
constexpr std::uint64_t wide = std::numeric_limits<std::uint64_t>::max();
constexpr DocumentActionV1Key key{8,9,11,10,12,13};
constexpr DocumentVersion version{9,10,12};
constexpr DocumentV2Identity native_identity{9,10,11};
std::size_t checks{};
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
    const auto digit=[](char c)->unsigned {
        if (c>='0' && c<='9') return static_cast<unsigned>(c-'0');
        if (c>='a' && c<='f') return static_cast<unsigned>(c-'a'+10);
        throw std::runtime_error("Invalid test fixture hex");
    };
    check(text.size()%2==0,"Odd test fixture hex");
    Bytes result;
    for (std::size_t at=0;at<text.size();at+=2)
        result.push_back(static_cast<std::uint8_t>((digit(text[at])<<4)|digit(text[at+1])));
    return result;
}
void overwrite(Bytes& bytes, std::size_t at, std::uint64_t value, unsigned width) {
    check(at<=bytes.size() && width<=bytes.size()-at,"Test fixture write outside bytes");
    for (unsigned i=0;i<width;++i) bytes[at+i]=static_cast<std::uint8_t>(value>>(8*i));
}
Bytes owned(const DocumentActionV1Request& request) { return {request.bytes.begin(),request.bytes.end()}; }
DocumentActionV1Key action_key(unsigned tag) { auto result=key; if (tag==3) result.nested_request_id=0; return result; }
DocumentActionV1 action(unsigned tag) {
    switch (tag) {
    case 0: return DocumentActionV1Focus{3};
    case 1: return DocumentActionV1Activate{7};
    case 2: return DocumentActionV1Select{{{2,1,DocumentNativeOffsetKind::text_utf16},
                                        {20,8192,DocumentNativeOffsetKind::element_child_index}}};
    case 3: return DocumentActionV1ChooseSingleOption{7,101};
    default: throw std::runtime_error("Invalid fixture action");
    }
}
DocumentActionV1Request request(unsigned tag=0) { return encode_document_action_v1(action_key(tag),version,action(tag)); }
// Independent literal schema fixtures. Enum ordinals, field ordering and union
// padding do not come from the production encoder or a C++ object layout.
Bytes golden_request(unsigned tag) {
    switch (tag) {
    case 0: return hex(
        "4441563101000100800000000000000008000000000000000900000000000000"
        "0b000000000000000a000000000000000c000000000000000d00000000000000"
        "09000000000000000a000000000000000c000000000000000000000000000000"
        "0300000000000000000000000000000000000000000000000000000000000000");
    case 1: return hex(
        "4441563101000100800000000000000008000000000000000900000000000000"
        "0b000000000000000a000000000000000c000000000000000d00000000000000"
        "09000000000000000a000000000000000c000000000000000100000000000000"
        "0700000000000000000000000000000000000000000000000000000000000000");
    case 2: return hex(
        "4441563101000100800000000000000008000000000000000900000000000000"
        "0b000000000000000a000000000000000c000000000000000d00000000000000"
        "09000000000000000a000000000000000c000000000000000200000000000000"
        "0200000000000000010100000014000000000000000200200000000000000000");
    case 3: return hex(
        "4441563101000100800000000000000008000000000000000900000000000000"
        "0b000000000000000a000000000000000c000000000000000000000000000000"
        "09000000000000000a000000000000000c000000000000000300000000000000"
        "0700000000000000650000000000000000000000000000000000000000000000");
    default: throw std::runtime_error("Invalid golden action tag");
    }
}
// This writer constructs test data only, from literal offsets and widths in
// binary-schema.json. It never calls the product completion encoder.
Bytes completion(unsigned result, unsigned code, unsigned effects, const Bytes& record={},
                 DocumentActionV1Key correlation=key) {
    Bytes bytes(72+record.size());
    bytes[0]='D'; bytes[1]='A'; bytes[2]='V'; bytes[3]='1';
    overwrite(bytes,4,1,2); overwrite(bytes,6,2,1); overwrite(bytes,8,bytes.size(),4);
    overwrite(bytes,16,correlation.worker_epoch,8); overwrite(bytes,24,correlation.application_instance,8);
    overwrite(bytes,32,correlation.document_sequence,8); overwrite(bytes,40,correlation.service_generation,8);
    overwrite(bytes,48,correlation.request_sequence,8); overwrite(bytes,56,correlation.nested_request_id,8);
    overwrite(bytes,64,result,1); overwrite(bytes,65,code,1); overwrite(bytes,66,effects,1);
    overwrite(bytes,67,!record.empty(),1); overwrite(bytes,68,record.size(),4);
    std::copy(record.begin(),record.end(),bytes.begin()+72);
    return bytes;
}
// Fixed independently generated native NDV2 reply, 1593 bytes, SHA256
// 334bdf7e03b52064a8263d1c29c1bbc073eb1af4d388cd53ba1aeab326bd03b1.
// The test extracts its Publication record; product code receives no Query.
Bytes rich_fixture_reply() {
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

Bytes rich_record() {
    const auto bytes=rich_fixture_reply();
    check(bytes.size()==1593,"Independent rich NDV2 fixture changed");
    return {bytes.begin()+48,bytes.end()};
}
const DocumentNode& node(const DocumentV2Publication& publication, std::uint64_t id) {
    const auto& nodes=publication.observation.body.snapshot->nodes;
    const auto found=std::find_if(nodes.begin(),nodes.end(),[&](const auto& value){return value.id==id;});
    check(found!=nodes.end(),"Expected publication node is absent"); return *found;
}
const F::FormControl& control(const DocumentV2Publication& publication, std::uint64_t id) {
    const auto& controls=publication.observation.forms.controls;
    const auto found=std::find_if(controls.begin(),controls.end(),[&](const auto& value){return value.node==id;});
    check(found!=controls.end(),"Expected publication control is absent"); return *found;
}
void invalid_request(const Bytes& bytes) {
    rejects([&]{(void)decode_document_action_v1_request(bytes);},"Malformed DAV1 request accepted");
}
void invalid_record(const Bytes& bytes) {
    rejects([&]{(void)decode_appended_document_v2_publication(bytes,native_identity);},"Malformed NDV2 Publication record accepted");
    const auto wire=completion(0,0,1,bytes);
    rejects([&]{(void)decode_document_action_v1_reply(wire,request());},"Malformed DAV1 readback accepted");
    rejects([&]{(void)encode_document_action_v1_reply(request(),DocumentActionV1Result::completed,
        DocumentActionV1Code::ok,true,bytes);},"Malformed readback serialized");
}
void golden_actions_and_padding() {
    for (unsigned tag=0;tag<4;++tag) {
        const auto wire=golden_request(tag), encoded=owned(request(tag));
        check(wire.size()==128 && encoded==wire,"DAV1 action differs from literal128-byte fixture");
        const auto decoded=decode_document_action_v1_request(wire);
        check(decoded.key==action_key(tag) && decoded.expected==version && decoded.action==action(tag) &&
              owned(decoded)==wire,"DAV1 action decode changed key/version/variant");
        for (std::size_t size=0;size<wire.size();++size)
            invalid_request({wire.begin(),wire.begin()+size});
        auto bad=wire; bad.push_back(0); invalid_request(bad);
        for (std::size_t at=0;at<16;++at) { bad=wire; bad[at]^=0xff; invalid_request(bad); }
        for (std::size_t at=89;at<96;++at) { bad=wire; bad[at]=1; invalid_request(bad); }
        const std::size_t padding=tag==2?122:tag==3?112:104;
        for (std::size_t at=padding;at<128;++at) { bad=wire; bad[at]=1; invalid_request(bad); }
    }
    auto bad=golden_request(0); overwrite(bad,88,4,1); invalid_request(bad);
    bad=golden_request(0); overwrite(bad,88,255,1); invalid_request(bad);
    for (const auto at:{64u,72u,80u}) { bad=golden_request(0); overwrite(bad,at,0,8); invalid_request(bad); }
    bad=golden_request(0); overwrite(bad,64,8,8); invalid_request(bad);
    bad=golden_request(0); overwrite(bad,72,11,8); invalid_request(bad);
    bad=golden_request(0); overwrite(bad,80,safe_integer+1,8); invalid_request(bad);
}
void identity_and_endpoint_domains() {
    for (const auto at:{16u,24u,32u,40u,48u}) {
        auto bad=golden_request(0); overwrite(bad,at,0,8); invalid_request(bad);
    }
    for (const auto& [at,value]:std::array<std::pair<std::size_t,std::uint64_t>,4>{{
            {40,std::uint64_t(UINT32_MAX)+1},{48,wide},{56,safe_integer+1},{56,0}}}) {
        auto bad=golden_request(0); overwrite(bad,at,value,8); invalid_request(bad);
    }
    auto bad=golden_request(3); overwrite(bad,56,13,8); invalid_request(bad);
    for (unsigned tag=0;tag<4;++tag) {
        for (const auto value:{std::uint64_t(0),safe_integer+1}) {
            bad=golden_request(tag); overwrite(bad,96,value,8); invalid_request(bad);
            if (tag==3) { bad=golden_request(tag); overwrite(bad,104,value,8); invalid_request(bad); }
            if (tag==2) { bad=golden_request(tag); overwrite(bad,109,value,8); invalid_request(bad); }
        }
    }
    for (const auto at:{104u,117u}) for (unsigned kind:{0u,3u,255u}) {
        bad=golden_request(2); overwrite(bad,at,kind,1); invalid_request(bad);
    }
    bad=golden_request(2); overwrite(bad,105,2049,4); invalid_request(bad);
    bad=golden_request(2); overwrite(bad,118,8193,4); invalid_request(bad);
    auto selection=std::get<DocumentActionV1Select>(action(2));
    selection.selection.anchor.offset=2048;
    check(std::get<DocumentActionV1Select>(encode_document_action_v1(key,version,selection).action).selection==selection.selection,
          "Exact representable endpoint limits rejected");
    selection.selection.anchor.offset=2049;
    rejects([&]{(void)encode_document_action_v1(key,version,selection);},"Unbounded typed text endpoint encoded");
    selection=std::get<DocumentActionV1Select>(action(2)); selection.selection.focus.offset=8193;
    rejects([&]{(void)encode_document_action_v1(key,version,selection);},"Unbounded typed child endpoint encoded");
    selection=std::get<DocumentActionV1Select>(action(2)); selection.selection.anchor.kind=static_cast<DocumentNativeOffsetKind>(2);
    rejects([&]{(void)encode_document_action_v1(key,version,selection);},"Unknown typed endpoint kind encoded");
    rejects([&]{(void)encode_document_action_v1(key,version,DocumentActionV1Focus{0});},"Zero typed action target encoded");
    rejects([&]{(void)encode_document_action_v1(action_key(3),version,DocumentActionV1ChooseSingleOption{7,0});},
            "Zero typed option target encoded");
    auto chooser_key=key;
    rejects([&]{(void)encode_document_action_v1(chooser_key,version,action(3));},"Chooser acquired nested Controller token");
    chooser_key.nested_request_id=0;
    rejects([&]{(void)encode_document_action_v1(chooser_key,version,action(0));},"Body action lost nested Controller token");
    const DocumentActionV1Key large{wide,wide,wide,UINT32_MAX,wide-1,safe_integer};
    const DocumentVersion large_version{wide,UINT32_MAX,safe_integer};
    const auto encoded=encode_document_action_v1(large,large_version,DocumentActionV1Focus{safe_integer});
    const auto decoded=decode_document_action_v1_request(encoded.bytes);
    check(decoded.key==large && decoded.expected==large_version &&
          std::get<DocumentActionV1Focus>(decoded.action).node==safe_integer,
          "Full64 identity/ordinary MAX-1 or consumer integer boundary narrowed");
}
bool legal_status(unsigned result, unsigned code, unsigned effects, bool present) {
    return (result==0 && code==0 && effects==1 && present) ||
        (result==1 && code==9 && effects==1 && !present) ||
        (result==2 && code>=1 && code<=8 && effects==0 && !present) ||
        (result==3 && code==8 && effects==1);
}
void completion_status_domains() {
    const auto record=rich_record();
    const auto expected=request();
    for (unsigned result=0;result<=4;++result) for (unsigned code=0;code<=10;++code)
    for (unsigned effects=0;effects<=2;++effects) for (bool present:{false,true}) {
        const Bytes payload=present?record:Bytes{};
        const auto wire=completion(result,code,effects,payload);
        const auto outcome=static_cast<DocumentActionV1Result>(result);
        const auto status=static_cast<DocumentActionV1Code>(code);
        if (legal_status(result,code,effects,present)) {
            const auto decoded=decode_document_action_v1_reply(wire,expected);
            check(static_cast<unsigned>(decoded.result)==result && static_cast<unsigned>(decoded.code)==code &&
                  decoded.effects_entered==(effects!=0) && decoded.publication.has_value()==present &&
                  decoded.key==key && decoded.publication_record==payload,
                  "DAV1 completion result domain changed");
            check(encode_document_action_v1_reply(expected,outcome,status,effects!=0,payload)==wire,
                  "DAV1 completion serializer differs from independent field fixture");
        } else {
            rejects([&]{(void)decode_document_action_v1_reply(wire,expected);},"Illegal DAV1 result/code/effect/readback tuple accepted");
            if (effects<=1) rejects([&]{(void)encode_document_action_v1_reply(expected,outcome,status,effects!=0,payload);},
                "Illegal DAV1 result/code/effect/readback tuple serialized");
        }
    }
    const auto wire=completion(2,1,0);
    check(wire==hex("4441563101000200480000000000000008000000000000000900000000000000"
                    "0b000000000000000a000000000000000c000000000000000d00000000000000"
                    "0201000000000000"),"Independent72-byte pre-entry completion fixture changed");
    for (std::size_t size=0;size<72;++size)
        rejects([&]{(void)decode_document_action_v1_reply(std::span<const std::uint8_t>(wire).first(size),expected);},
                "Truncated DAV1 completion prefix accepted");
    for (std::size_t at=0;at<16;++at) {
        auto bad=wire; bad[at]^=0xff;
        rejects([&]{(void)decode_document_action_v1_reply(bad,expected);},"Malformed DAV1 completion header accepted");
    }
    for (const auto at:{16u,24u,32u,40u,48u,56u}) {
        auto bad=wire; bad[at]^=1;
        rejects([&]{(void)decode_document_action_v1_reply(bad,expected);},"Foreign field of six-part DAV1 reply key accepted");
    }
    auto bad=wire; bad.push_back(0);
    rejects([&]{(void)decode_document_action_v1_reply(bad,expected);},"Trailing DAV1 completion byte accepted");
    for (const auto& [at,value]:std::array<std::pair<std::size_t,unsigned>,4>{{{66,2},{67,2},{67,1},{68,1}}}) {
        bad=wire; overwrite(bad,at,value,1);
        rejects([&]{(void)decode_document_action_v1_reply(bad,expected);},"Noncanonical completion flags/presence/extent accepted");
    }
    bad=completion(0,0,1,record); overwrite(bad,68,record.size()-1,4);
    rejects([&]{(void)decode_document_action_v1_reply(bad,expected);},"Incorrect Publication record extent accepted");
    bad=completion(0,0,1,record); overwrite(bad,67,0,1);
    rejects([&]{(void)decode_document_action_v1_reply(bad,expected);},"Absent flag conceals Publication record bytes");
    bad.assign(max_document_action_v1_reply_bytes+1,0);
    rejects([&]{(void)decode_document_action_v1_reply(bad,expected);},"Oversized DAV1 completion accepted");
    const Bytes oversized(BIB_ENGINE_DOCUMENT_ACTIONS_V1_MAX_PUBLICATION_BYTES+1,0);
    rejects([&]{(void)encode_document_action_v1_reply(expected,DocumentActionV1Result::completed,DocumentActionV1Code::ok,true,oversized);},
            "Oversized Publication record serialized");
}
void expected_request_integrity_and_readback_identity() {
    const auto record=rich_record(), wire=completion(0,0,1,record);
    auto expected=request();
    for (unsigned mutation=0;mutation<4;++mutation) {
        auto changed=expected;
        if (mutation==0) changed.bytes[89]=1;
        else if (mutation==1) ++changed.key.worker_epoch;
        else if (mutation==2) ++changed.expected.revision;
        else changed.action=DocumentActionV1Focus{4};
        rejects([&]{(void)decode_document_action_v1_reply(wire,changed);},"Tampered expected request accepted during readback");
        rejects([&]{(void)encode_document_action_v1_reply(changed,DocumentActionV1Result::completed,DocumentActionV1Code::ok,true,record);},
                "Tampered expected request accepted during serialization");
    }
    for (const auto at:{0u,8u,16u,24u,32u}) {
        auto changed=record; changed[at]^=1;
        invalid_record(changed);
    }
    auto earlier=record; overwrite(earlier,40,11,8);
    check(decode_appended_document_v2_publication(earlier,native_identity).observation.publication.revision==11,
          "Payload parser incorrectly invented displayed freshness context");
    rejects([&]{(void)decode_document_action_v1_reply(completion(0,0,1,earlier),expected);},
            "Readback older than displayed publication accepted");
    rejects([&]{(void)encode_document_action_v1_reply(expected,DocumentActionV1Result::completed,DocumentActionV1Code::ok,true,earlier);},
            "Readback older than displayed publication serialized");
    auto later=record; overwrite(later,40,13,8);
    check(decode_document_action_v1_reply(completion(0,0,1,later),expected).publication->observation.publication.revision==13,
          "Newer actual readback rejected");
    const auto chooser=request(3);
    const auto chosen=decode_document_action_v1_reply(completion(0,0,1,record,chooser.key),chooser);
    check(chosen.key.nested_request_id==0 && chosen.publication->observation.body.request_id==0,
          "Chooser readback fabricated Controller completion token");
    const auto entire_reply=rich_fixture_reply();
    rejects([&]{(void)decode_appended_document_v2_publication(entire_reply,native_identity);},
            "Payload parser accepted NDV2 packet header/Query wrapper");
}
void independent_rich_payload_and_ownership() {
    auto record=rich_record();
    const auto parsed=decode_appended_document_v2_publication(record,native_identity);
    const auto& body=parsed.observation.body;
    check(body.request_id==0 && body.epoch==10 && body.snapshot &&
          body.snapshot->version==version && body.snapshot->nodes.size()==13 && parsed.observation.forms.controls.size()==9,
          "Direct Publication parser changed paired body/forms identity");
    check(body.editor_state && body.editor_state->revision==7 && body.editor_state->flags==31 &&
          body.snapshot->active_node==3 && parsed.native_degradation==119,
          "Direct Publication parser lost authoritative editor/degradation values");
    check(parsed.selection && !parsed.selection->focus_rect && !body.original_selection && body.snapshot->selection &&
          body.snapshot->selection->anchor==DocumentPoint{2,1} && body.snapshot->selection->focus==DocumentPoint{2,3},
          "Direct parser invented geometry or changed UTF16 selection");
    check(node(parsed,2).text=="A\xf0\x9f\x99\x82" "B" && node(parsed,20).parent==0,
          "Scalar text or native forest root changed");
    check(control(parsed,3).lease==F::FormLease{{9,10,11},3,wide},"Older valid native lease rebased or opaque ID narrowed");
    const auto& number=std::get<F::FormTextState>(control(parsed,4).state);
    check(number.value.empty() && number.editing_text=="-." && node(parsed,4).value.empty(),
          "Numeric canonical value replaced with editing buffer");
    check(control(parsed,9).kind==F::FormKind::secure_readonly && control(parsed,9).label.empty() &&
          std::holds_alternative<std::monostate>(control(parsed,9).state) && node(parsed,9).masked && node(parsed,9).value.empty(),
          "Secure marker retained private state");
    check(node(parsed,11).value=="safe" && control(parsed,11).read_only && !control(parsed,11).capabilities,
          "Safe readonly value hidden or granted authority");
    auto wire=completion(0,0,1,record);
    const auto decoded=decode_document_action_v1_reply(wire,request());
    check(decoded.publication && decoded.publication->observation.body.request_id==0 && decoded.publication_record==record,
          "Action readback became query completion or lost exact raw record");
    std::fill(record.begin(),record.end(),0); std::fill(wire.begin(),wire.end(),0);
    check(node(*decoded.publication,2).text=="A\xf0\x9f\x99\x82" "B" && decoded.publication_record==rich_record(),
          "DAV1 decoded publication aliases caller-owned bytes");
    const auto fixture=rich_record();
    for (std::size_t size=0;size<fixture.size();++size) {
        const std::span<const std::uint8_t> prefix(fixture.data(),size);
        rejects([&]{(void)decode_appended_document_v2_publication(prefix,native_identity);},"Truncated Publication record accepted");
    }
    auto bad=fixture; bad.push_back(0); invalid_record(bad);
    for (const auto& [absolute,value,width]:std::array<std::array<std::uint64_t,3>,31>{{
        {96,2,1},{113,32,1},{117,128,1},{133,2,1},{142,3,1},{160,2,1},
        {177,3,1},{178,16,1},{1061,8,1},{1062,64,1},{1067,4,1},{1068,2,1},
        {1137,2,1},{1146,3,1},{1313,2,1},{1352,4,1},{1365,8,1},{1592,2,1},
        {207,1,8},{215,3,8},{179,9,4},{272,4,1},{281,'x',1},{294,'X',1},{302,'H',1},
        {877,1,8},{922,999,8},{1053,2,8},{597,0,1},{1489,1,4},{1383,3,1}}}) {
        bad=fixture; overwrite(bad,static_cast<std::size_t>(absolute)-48,value,static_cast<unsigned>(width)); invalid_record(bad);
    }
    for (const auto absolute:{121u,125u,129u}) {
        bad=fixture; overwrite(bad,absolute-48,2049,4); invalid_record(bad);
    }
    for (const auto absolute:{183u,233u,848u,1069u,1353u}) {
        bad=fixture; overwrite(bad,absolute-48,0xffffffffU,4); invalid_record(bad);
    }
    bad=fixture; overwrite(bad,1357-48,safe_integer+1,8); invalid_record(bad);
    bad=fixture; overwrite(bad,1101-48,13,8); invalid_record(bad); // Lease newer than publication.
    bad=fixture; overwrite(bad,1109-48,4,8); invalid_record(bad); // Lease for another control.
}
struct Wire {
    Bytes bytes;
    void put(std::uint64_t value, unsigned width) {
        for (unsigned i=0;i<width;++i) bytes.push_back(static_cast<std::uint8_t>(value>>(8*i)));
    }
    void str(std::string_view value) { put(value.size(),4); bytes.insert(bytes.end(),value.begin(),value.end()); }
};
struct NativeNode {
    std::uint64_t id{1}, parent{};
    unsigned kind{1}, flags{}, children{};
    std::string tag{"div"}, text, name, value, href;
};
struct NativeMetadata { std::uint64_t node; std::string role, display, whitespace; };
struct NativePoint { std::uint64_t node; unsigned kind; std::uint32_t offset; };
struct NativeSelection {
    NativePoint anchor, focus;
    std::optional<std::array<double,4>> geometry;
};
Bytes body_record(const std::vector<NativeNode>& nodes={NativeNode{}},
                  const std::vector<NativeMetadata>& metadata={},
                  const std::optional<NativeSelection>& selection={}, bool truncated=false,
                  std::uint32_t degradation=0, std::uint64_t active=0) {
    Wire w;
    for (auto value:{std::uint64_t(9),std::uint64_t(10),std::uint64_t(11),
                    std::uint64_t(9),std::uint64_t(10),std::uint64_t(12)}) w.put(value,8);
    w.put(truncated,1); w.put(7,8); w.put(active,8); w.put(0,4); w.put(degradation,4);
    w.put(nodes.size(),4); w.put(metadata.size(),4); w.put(0,4); w.put(selection.has_value(),1);
    if (selection) {
        for (const auto& point:{selection->anchor,selection->focus}) { w.put(point.node,8); w.put(point.kind,1); w.put(point.offset,4); }
        w.put(selection->geometry.has_value(),1);
        if (selection->geometry) for (double value:*selection->geometry) w.put(std::bit_cast<std::uint64_t>(value),8);
    }
    for (const auto& n:nodes) {
        w.put(n.id,8); w.put(n.parent,8); w.put(n.kind,1); w.put(n.flags,1); w.put(n.children,4);
        for (const auto* text:{&n.tag,&n.text,&n.name,&n.value,&n.href}) w.str(*text);
    }
    for (const auto& m:metadata) { w.put(m.node,8); w.str(m.role); w.str(m.display); w.str(m.whitespace); }
    return std::move(w.bytes);
}
NativeNode text_node(std::uint64_t id, std::uint64_t parent, std::string text) {
    NativeNode value; value.id=id; value.parent=parent; value.kind=2; value.tag.clear(); value.text=std::move(text); return value;
}
void body_scalar_child_and_budget_invariants() {
    for (bool truncated:{false,true}) {
        const auto parsed=decode_appended_document_v2_publication(body_record({}, {}, {},truncated),native_identity);
        check(parsed.observation.body.snapshot->nodes.empty() && parsed.observation.body.snapshot->truncated==truncated &&
              parsed.observation.forms.controls.empty() && !parsed.selection,"Empty Publication acquired synthetic state");
    }
    NativeNode root; root.children=8;
    const auto text=text_node(2,1,"A\xf0\x9f\x99\x82" "B");
    NativeSelection child{{1,2,8},{1,2,0},{}};
    const auto child_record=body_record({root,text},{},child);
    const auto decoded=decode_document_action_v1_reply(completion(0,0,1,child_record),request());
    check(decoded.publication && decoded.publication->selection->endpoints.anchor.offset==8 &&
          decoded.publication->observation.body.degraded.element_selection && decoded.publication_record==child_record,
          "Actual child count replaced with projected count or original record lost");
    check(encode_document_action_v1_reply(request(),DocumentActionV1Result::completed,DocumentActionV1Code::ok,true,
          decoded.publication_record)==completion(0,0,1,child_record),"Child-count readback failed exact serialization");
    child.anchor.offset=9; invalid_record(body_record({root,text},{},child));
    NativeSelection scalar{{2,1,1},{2,1,3},{}};
    check(decode_appended_document_v2_publication(body_record({root,text},{},scalar),native_identity).selection.has_value(),
          "Valid supplementary-scalar endpoints rejected");
    scalar.focus.offset=2; invalid_record(body_record({root,text},{},scalar));
    scalar.focus.offset=5; invalid_record(body_record({root,text},{},scalar));
    scalar.focus={1,1,0}; invalid_record(body_record({root,text},{},scalar));
    scalar.focus={2,2,0}; invalid_record(body_record({root,text},{},scalar));
    scalar.focus={2,1,3}; invalid_record(body_record({root,text},{},scalar,true));
    invalid_record(body_record({root,text},{},scalar,false,8));
    scalar.geometry=std::array<double,4>{-1,2,0,3};
    check(decode_appended_document_v2_publication(body_record({root,text},{},scalar),native_identity).selection->focus_rect.has_value(),
          "Finite native geometry with negative origin rejected");
    scalar.geometry=std::array<double,4>{0,0,-1,1}; invalid_record(body_record({root,text},{},scalar));
    scalar.geometry=std::array<double,4>{0,0,1,std::numeric_limits<double>::infinity()}; invalid_record(body_record({root,text},{},scalar));
    NativeNode another; another.id=3;
    invalid_record(body_record({root,text,another,text_node(4,1,"closed subtree")}));
    auto no_children=root; no_children.children=0; invalid_record(body_record({no_children,text}));
    auto bad_text=text; bad_text.flags=4; invalid_record(body_record({root,bad_text}));
    bad_text=text; bad_text.children=1; invalid_record(body_record({root,bad_text}));
    auto omitted=root; omitted.flags=2; invalid_record(body_record({omitted,text}));
    omitted.children=0; omitted.text="hidden"; invalid_record(body_record({omitted}));
    omitted.text.clear(); omitted.flags|=8; invalid_record(body_record({omitted}));
    invalid_record(body_record({root,text},{{2,"role","",""}}));
    invalid_record(body_record({root,text},{{1,"role","",""},{1,"again","",""}}));
    invalid_record(body_record({root,another},{{3,"role","",""},{1,"earlier","",""}}));
    invalid_record(body_record({},{{1,"role","",""}}));
    invalid_record(body_record({}, {}, {},false,0,1));
    for (const auto& invalid:{std::string("\0",1),std::string("\xc0\x80",2),std::string("\xed\xa0\x80",3),
                             std::string("\xf4\x90\x80\x80",4),std::string("\xf0\x9f",2),std::string(2049,'x')})
        invalid_record(body_record({root,text_node(2,1,invalid)}));
    std::string bmp, supplementary;
    for (unsigned i=0;i<2048;++i) bmp+="\xe0\xa0\x80";
    for (unsigned i=0;i<1024;++i) supplementary+="\xf0\x9f\x99\x82";
    check(node(decode_appended_document_v2_publication(body_record({root,text_node(2,1,bmp)}),native_identity),2).text.size()==6144,
          "Exact6144-byte scalar field rejected");
    check(node(decode_appended_document_v2_publication(body_record({root,text_node(2,1,supplementary)}),native_identity),2).text.size()==4096,
          "Supplementary scalar field charged as bytes");
    supplementary+="\xf0\x9f\x99\x82"; invalid_record(body_record({root,text_node(2,1,supplementary)}));
    std::vector<NativeNode> nodes; root.children=33; nodes.push_back(root);
    for (unsigned i=0;i<32;++i) nodes.push_back(text_node(i+2,1,std::string(2048,'x')));
    check(decode_appended_document_v2_publication(body_record(nodes),native_identity).observation.body.snapshot->nodes.size()==33,
          "Exact65536-unit body pool rejected");
    nodes.push_back(text_node(34,1,"x")); invalid_record(body_record(nodes));
    nodes.clear();
    for (unsigned i=0;i<32;++i) { NativeNode n; n.id=i+1; n.tag=std::string(2048,'x'); nodes.push_back(std::move(n)); }
    check(decode_appended_document_v2_publication(body_record(nodes),native_identity).observation.body.snapshot->nodes.size()==32,
          "Separate65536-unit metadata/tag pool rejected");
    invalid_record(body_record(nodes,{{1,"x","",""}}));
    nodes.clear();
    for (unsigned i=0;i<256;++i) { NativeNode n; n.id=i+1; n.parent=i; n.children=i==255?0:1; nodes.push_back(n); }
    check(decode_appended_document_v2_publication(body_record(nodes),native_identity).observation.body.snapshot->nodes.size()==256,
          "Exact native depth256 rejected");
    nodes.back().children=1; NativeNode extra; extra.id=257; extra.parent=256; nodes.push_back(extra); invalid_record(body_record(nodes));
    root.children=8192; NativeNode leaf; leaf.id=2; leaf.parent=1;
    check(decode_appended_document_v2_publication(body_record({root,leaf}),native_identity).observation.body.snapshot->nodes.size()==2,
          "Exact8192 actual-child budget rejected");
    leaf.children=1; invalid_record(body_record({root,leaf}));
}
void ack_payload_domain() {
    check(!encode_document_action_v1_ack(0) && !encode_document_action_v1_ack(wide),"ACK accepted zero or final reserved original sequence");
    const std::array<std::uint8_t,8> original_one{1,0,0,0,0,0,0,0};
    const auto encoded_one=encode_document_action_v1_ack(1);
    check(encoded_one && *encoded_one==original_one,
          "ACK request differs from explicit8-byte fixture");
    const auto maximum=encode_document_action_v1_ack(wide-1);
    check(maximum && (*maximum)[0]==254 && std::all_of(maximum->begin()+1,maximum->end(),[](auto byte){return byte==255;}),
          "ACK original MAX-1 narrowed");
    for (unsigned code=0;code<=2;++code) {
        Bytes bytes(16); overwrite(bytes,0,wide-1,8); overwrite(bytes,8,code,4);
        const auto decoded=decode_document_action_v1_ack(bytes);
        check(decoded && decoded->original_action_sequence==wide-1 && static_cast<unsigned>(decoded->code)==code,
              "ACK result code conflated with semantic/provider status");
        for (std::size_t size=0;size<16;++size)
            check(!decode_document_action_v1_ack(std::span<const std::uint8_t>(bytes).first(size)),"Truncated ACK result accepted");
        auto bad=bytes; bad.push_back(0); check(!decode_document_action_v1_ack(bad),"Trailing ACK result byte accepted");
        for (std::size_t at=12;at<16;++at) { bad=bytes; bad[at]=1; check(!decode_document_action_v1_ack(bad),"Nonzero ACK reserved byte accepted"); }
        for (const auto original:{std::uint64_t(0),wide}) { bad=bytes; overwrite(bad,0,original,8); check(!decode_document_action_v1_ack(bad),"ACK result accepted invalid original sequence"); }
    }
    auto invalid=hex("01000000000000000300000000000000");
    check(!decode_document_action_v1_ack(invalid),"Unknown ACK code accepted");
    check(!decode_document_action_v1_ack(completion(2,1,0)),"DAV1 semantic completion accepted as ACK result");
    check(!decode_document_action_v1_ack(*encode_document_action_v1_ack(1)),"ACK request accepted as ACK result");
    rejects([&]{(void)decode_document_action_v1_reply(invalid,request());},"ACK result accepted as DAV1 semantic completion");
}
} // namespace

int main() {
    try {
        golden_actions_and_padding();
        identity_and_endpoint_domains();
        completion_status_domains();
        expected_request_integrity_and_readback_identity();
        independent_rich_payload_and_ownership();
        body_scalar_child_and_budget_invariants();
        ack_payload_domain();
        std::cout << "document_action_v1_codec_test: " << checks << " checks passed\n";
    } catch (const std::exception& error) {
        std::cerr << "document_action_v1_codec_test: " << error.what() << '\n';
        return 1;
    }
}
