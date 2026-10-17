// SPDX-License-Identifier: CC0-1.0
#include "document_action_v1_codec.hpp"

#include <algorithm>
#include <stdexcept>
#include <type_traits>

namespace foundation::ui {
namespace {
constexpr std::uint64_t safe_integer = 9007199254740991ULL;
constexpr std::uint32_t magic = 0x31564144;
void require(bool ok, const char* message) { if (!ok) throw std::invalid_argument(message); }
void key_valid(DocumentActionV1Key key) {
    require(key.worker_epoch && key.application_instance && key.document_sequence && key.service_generation &&
        key.service_generation <= UINT32_MAX && key.request_sequence &&
        key.request_sequence <= BIB_ENGINE_DOCUMENT_ACTIONS_V1_MAX_ORDINARY_SEQUENCE &&
        key.nested_request_id <= safe_integer, "Invalid document-action identity");
}
void node_valid(std::uint64_t node) {
    require(node && node <= safe_integer, "Unrepresentable document-action node");
}
void point_valid(DocumentNativePoint point) {
    node_valid(point.node);
    switch (point.kind) {
    case DocumentNativeOffsetKind::text_utf16:
        require(point.offset <= 2048, "Document-action text offset exceeds consumer bound"); break;
    case DocumentNativeOffsetKind::element_child_index:
        require(point.offset <= 8192, "Document-action child offset exceeds traversal bound"); break;
    default: throw std::invalid_argument("Unknown document-action endpoint kind");
    }
}
void put(std::span<std::uint8_t> bytes, std::size_t at, std::uint64_t value, unsigned width) {
    for (unsigned i=0; i<width; ++i) bytes[at+i]=static_cast<std::uint8_t>(value >> (8*i));
}
std::uint64_t get(std::span<const std::uint8_t> bytes, std::size_t at, unsigned width) {
    require(at<=bytes.size() && width<=bytes.size()-at, "Short document-action packet");
    std::uint64_t result{};
    for (unsigned i=0; i<width; ++i) result |= std::uint64_t(bytes[at+i]) << (8*i);
    return result;
}
void header(std::span<std::uint8_t> bytes, unsigned kind) {
    put(bytes,0,magic,4); put(bytes,4,1,2); put(bytes,6,kind,1); put(bytes,8,bytes.size(),4);
}
void header_valid(std::span<const std::uint8_t> bytes, unsigned kind) {
    require(bytes.size()>=16 && get(bytes,0,4)==magic && get(bytes,4,2)==1 &&
        get(bytes,6,1)==kind && !get(bytes,7,1) && get(bytes,8,4)==bytes.size() && !get(bytes,12,4),
        "Unknown or noncanonical document-action header");
}
void put_key(std::span<std::uint8_t> bytes, DocumentActionV1Key key) {
    put(bytes,16,key.worker_epoch,8); put(bytes,24,key.application_instance,8);
    put(bytes,32,key.document_sequence,8); put(bytes,40,key.service_generation,8);
    put(bytes,48,key.request_sequence,8); put(bytes,56,key.nested_request_id,8);
}
DocumentActionV1Key get_key(std::span<const std::uint8_t> bytes) {
    return {get(bytes,16,8),get(bytes,24,8),get(bytes,32,8),get(bytes,40,8),get(bytes,48,8),get(bytes,56,8)};
}
void put_point(std::span<std::uint8_t> bytes, std::size_t at, DocumentNativePoint point) {
    put(bytes,at,point.node,8); put(bytes,at+8,point.kind==DocumentNativeOffsetKind::text_utf16?1:2,1);
    put(bytes,at+9,point.offset,4);
}
DocumentNativePoint get_point(std::span<const std::uint8_t> bytes, std::size_t at) {
    const auto kind=get(bytes,at+8,1); require(kind==1 || kind==2, "Unknown document-action endpoint kind");
    return {get(bytes,at,8),static_cast<std::uint32_t>(get(bytes,at+9,4)),
        kind==1?DocumentNativeOffsetKind::text_utf16:DocumentNativeOffsetKind::element_child_index};
}
void expected_valid(const DocumentActionV1Request& expected) {
    const auto canonical=encode_document_action_v1(expected.key,expected.expected,expected.action);
    require(canonical.bytes==expected.bytes, "Changed expected document-action request");
}
void status_valid(DocumentActionV1Result result, DocumentActionV1Code code, bool effects, bool publication) {
    switch (result) {
    case DocumentActionV1Result::completed:
        require(code==DocumentActionV1Code::ok && effects && publication, "Completed document-action lacks actual readback"); break;
    case DocumentActionV1Result::completed_needs_current_observation:
        require(code==DocumentActionV1Code::context_replaced && effects && !publication, "Invalid context-replaced document-action"); break;
    case DocumentActionV1Result::rejected:
        require(static_cast<unsigned>(code)>=1 && static_cast<unsigned>(code)<=8 && !effects && !publication,
            "Invalid pre-entry document-action rejection"); break;
    case DocumentActionV1Result::indeterminate:
        require(code==DocumentActionV1Code::readback_failed && effects, "Invalid post-effect document-action uncertainty"); break;
    default: throw std::invalid_argument("Unknown document-action result");
    }
}
DocumentV2Identity identity(DocumentActionV1Key key) {
    return {key.application_instance,key.service_generation,key.document_sequence};
}
} // namespace

DocumentActionV1Request encode_document_action_v1(DocumentActionV1Key key, DocumentVersion expected, const DocumentActionV1& action) {
    key_valid(key);
    require(expected.generation==key.application_instance && expected.epoch==key.service_generation &&
        expected.revision && expected.revision<=safe_integer, "Document-action displayed Version mismatch");
    require(!action.valueless_by_exception(), "Valueless document-action");
    const bool chooser=std::holds_alternative<DocumentActionV1ChooseSingleOption>(action);
    require(chooser ? key.nested_request_id==0 : key.nested_request_id!=0, "Document-action nested-token domain mismatch");
    DocumentActionV1Request result; result.key=key; result.expected=expected;
    header(result.bytes,1); put_key(result.bytes,key);
    put(result.bytes,64,expected.generation,8); put(result.bytes,72,expected.epoch,8); put(result.bytes,80,expected.revision,8);
    std::visit([&](const auto& value) {
        using T=std::decay_t<decltype(value)>;
        if constexpr (std::is_same_v<T,DocumentActionV1Select>) {
            point_valid(value.selection.anchor); point_valid(value.selection.focus);
            put(result.bytes,88,2,1); put_point(result.bytes,96,value.selection.anchor); put_point(result.bytes,109,value.selection.focus);
        } else {
            node_valid(value.node); put(result.bytes,96,value.node,8);
            if constexpr (std::is_same_v<T,DocumentActionV1Focus>) put(result.bytes,88,0,1);
            else if constexpr (std::is_same_v<T,DocumentActionV1Activate>) put(result.bytes,88,1,1);
            else { node_valid(value.option); put(result.bytes,88,3,1); put(result.bytes,104,value.option,8); }
        }
    },action);
    result.action=action; return result;
}

DocumentActionV1Request decode_document_action_v1_request(std::span<const std::uint8_t> bytes) {
    require(bytes.size()==BIB_ENGINE_DOCUMENT_ACTIONS_V1_REQUEST_BYTES, "Document-action request must be exactly128 bytes");
    header_valid(bytes,1); const auto key=get_key(bytes);
    const DocumentVersion expected{get(bytes,64,8),get(bytes,72,8),get(bytes,80,8)};
    DocumentActionV1 action;
    switch (get(bytes,88,1)) {
    case 0: action=DocumentActionV1Focus{get(bytes,96,8)}; break;
    case 1: action=DocumentActionV1Activate{get(bytes,96,8)}; break;
    case 2: action=DocumentActionV1Select{{get_point(bytes,96),get_point(bytes,109)}}; break;
    case 3: action=DocumentActionV1ChooseSingleOption{get(bytes,96,8),get(bytes,104,8)}; break;
    default: throw std::invalid_argument("Unknown document-action tag");
    }
    auto result=encode_document_action_v1(key,expected,action);
    require(std::equal(bytes.begin(),bytes.end(),result.bytes.begin()), "Nonzero document-action padding");
    return result;
}

DocumentActionV1Reply decode_document_action_v1_reply(std::span<const std::uint8_t> bytes, const DocumentActionV1Request& expected) {
    expected_valid(expected);
    require(bytes.size()>=72 && bytes.size()<=max_document_action_v1_reply_bytes, "Document-action reply byte bound exceeded");
    header_valid(bytes,2); const auto key=get_key(bytes); require(key==expected.key, "Foreign document-action reply key");
    const auto result=get(bytes,64,1), code=get(bytes,65,1), flags=get(bytes,66,1), present=get(bytes,67,1), length=get(bytes,68,4);
    require(result<=3 && code<=9 && flags<=1 && present<=1 && length==bytes.size()-72 &&
        (present!=0)==(length!=0), "Noncanonical document-action completion");
    DocumentActionV1Reply reply; reply.key=key; reply.result=static_cast<DocumentActionV1Result>(result);
    reply.code=static_cast<DocumentActionV1Code>(code); reply.effects_entered=flags!=0;
    status_valid(reply.result,reply.code,reply.effects_entered,present!=0);
    if (present) {
        reply.publication=decode_appended_document_v2_publication(bytes.subspan(72),identity(key));
        require(reply.publication->observation.publication.revision>=expected.expected.revision,
            "Document-action readback precedes displayed publication");
        reply.publication_record.assign(bytes.begin()+72,bytes.end());
    }
    return reply;
}

std::vector<std::uint8_t> encode_document_action_v1_reply(const DocumentActionV1Request& expected,
    DocumentActionV1Result result, DocumentActionV1Code code, bool effects, std::span<const std::uint8_t> record) {
    expected_valid(expected);
    require(record.size()<=max_document_v2_publication_bytes, "Document-action publication byte bound exceeded");
    status_valid(result,code,effects,!record.empty());
    if (!record.empty()) {
        const auto publication=decode_appended_document_v2_publication(record,identity(expected.key));
        require(publication.observation.publication.revision>=expected.expected.revision,
            "Document-action readback precedes displayed publication");
    }
    std::vector<std::uint8_t> bytes(72+record.size()); header(bytes,2); put_key(bytes,expected.key);
    put(bytes,64,static_cast<unsigned>(result),1); put(bytes,65,static_cast<unsigned>(code),1);
    put(bytes,66,effects,1); put(bytes,67,!record.empty(),1); put(bytes,68,record.size(),4);
    std::copy(record.begin(),record.end(),bytes.begin()+72); return bytes;
}

std::optional<std::array<std::uint8_t, 8>> encode_document_action_v1_ack(std::uint64_t original) noexcept {
    if (!original || original>BIB_ENGINE_DOCUMENT_ACTIONS_V1_MAX_ORDINARY_SEQUENCE) return std::nullopt;
    std::array<std::uint8_t,8> bytes{};
    for (unsigned i=0;i<8;++i) bytes[i]=static_cast<std::uint8_t>(original >> (8*i));
    return bytes;
}
std::optional<DocumentActionV1Ack> decode_document_action_v1_ack(std::span<const std::uint8_t> bytes) noexcept {
    if (bytes.size()!=16) return std::nullopt;
    std::uint64_t original{}; std::uint32_t code{}, reserved{};
    for (unsigned i=0;i<8;++i) original |= std::uint64_t(bytes[i]) << (8*i);
    for (unsigned i=0;i<4;++i) { code |= std::uint32_t(bytes[8+i]) << (8*i); reserved |= std::uint32_t(bytes[12+i]) << (8*i); }
    if (!original || original>BIB_ENGINE_DOCUMENT_ACTIONS_V1_MAX_ORDINARY_SEQUENCE || code>2 || reserved) return std::nullopt;
    return DocumentActionV1Ack{original,static_cast<DocumentActionV1AckCode>(code)};
}
} // namespace foundation::ui
