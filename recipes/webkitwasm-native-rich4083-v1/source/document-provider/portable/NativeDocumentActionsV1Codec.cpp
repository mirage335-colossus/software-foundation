// SPDX-License-Identifier: CC0-1.0
#include "NativeDocumentActionsV1Codec.hpp"

#include <algorithm>
#include <limits>
#include <stdexcept>
#include <type_traits>

namespace BIB::NativeDocumentActionsV1 {
namespace {
constexpr std::uint32_t magic = 0x31564144;
constexpr std::size_t prefixBytes = BIB_ENGINE_DOCUMENT_ACTIONS_V1_COMPLETION_PREFIX_BYTES;
static_assert(N::maxPublicationRecordBytes == BIB_ENGINE_DOCUMENT_ACTIONS_V1_MAX_PUBLICATION_BYTES);
static_assert(prefixBytes + N::maxPublicationRecordBytes == maxReplyBytes);
void require(bool ok, const char* message) { if (!ok) throw std::invalid_argument(message); }
void keyValid(Key key) {
    require(key.worker_epoch && key.application_instance && key.document_sequence && key.service_generation &&
        key.service_generation <= UINT32_MAX && key.request_sequence &&
        key.request_sequence <= BIB_ENGINE_DOCUMENT_ACTIONS_V1_MAX_ORDINARY_SEQUENCE &&
        key.nested_request_id <= N::maxConsumerInteger, "invalid document-action identity");
}
void nodeValid(std::uint64_t node) {
    require(node && node <= N::maxConsumerInteger, "unrepresentable document-action node");
}
void endpointValid(N::Endpoint point) {
    nodeValid(point.node);
    switch (point.kind) {
    case N::EndpointKind::text_utf16:
        require(point.offset <= N::maxFieldUnits, "document-action text offset exceeds bound"); break;
    case N::EndpointKind::element_child:
        require(point.offset <= N::maxTraversal, "document-action child offset exceeds bound"); break;
    default: throw std::invalid_argument("unknown document-action endpoint kind");
    }
}
void put(std::span<std::uint8_t> bytes, std::size_t at, std::uint64_t value, unsigned width) {
    for (unsigned i=0; i<width; ++i) bytes[at+i]=static_cast<std::uint8_t>(value >> (8*i));
}
std::uint64_t get(std::span<const std::uint8_t> bytes, std::size_t at, unsigned width) {
    require(at<=bytes.size() && width<=bytes.size()-at, "short document-action packet");
    std::uint64_t result{};
    for (unsigned i=0; i<width; ++i) result |= std::uint64_t(bytes[at+i]) << (8*i);
    return result;
}
void header(std::span<std::uint8_t> bytes, unsigned kind) {
    put(bytes,0,magic,4); put(bytes,4,1,2); put(bytes,6,kind,1); put(bytes,8,bytes.size(),4);
}
void headerValid(std::span<const std::uint8_t> bytes, unsigned kind) {
    require(bytes.size()>=16 && get(bytes,0,4)==magic && get(bytes,4,2)==1 &&
        get(bytes,6,1)==kind && !get(bytes,7,1) && get(bytes,8,4)==bytes.size() && !get(bytes,12,4),
        "unknown or noncanonical document-action header");
}
void putKey(std::span<std::uint8_t> bytes, Key key) {
    put(bytes,16,key.worker_epoch,8); put(bytes,24,key.application_instance,8);
    put(bytes,32,key.document_sequence,8); put(bytes,40,key.service_generation,8);
    put(bytes,48,key.request_sequence,8); put(bytes,56,key.nested_request_id,8);
}
Key getKey(std::span<const std::uint8_t> bytes) {
    return {get(bytes,16,8),get(bytes,24,8),get(bytes,32,8),get(bytes,40,8),get(bytes,48,8),get(bytes,56,8)};
}
void putEndpoint(std::span<std::uint8_t> bytes, std::size_t at, N::Endpoint point) {
    put(bytes,at,point.node,8); put(bytes,at+8,static_cast<unsigned>(point.kind),1); put(bytes,at+9,point.offset,4);
}
N::Endpoint getEndpoint(std::span<const std::uint8_t> bytes, std::size_t at) {
    const auto kind=get(bytes,at+8,1); require(kind==1 || kind==2, "unknown document-action endpoint kind");
    return {get(bytes,at,8),static_cast<N::EndpointKind>(kind),static_cast<std::uint32_t>(get(bytes,at+9,4))};
}
void expectedValid(const Request& expected) {
    const auto canonical=encodeRequest(expected.key,expected.expected,expected.action);
    require(canonical.bytes==expected.bytes, "changed expected document-action request");
}
void statusValid(Result result, Code code, bool effects, bool publication) {
    switch (result) {
    case Result::completed:
        require(code==Code::ok && effects && publication, "completed document-action lacks actual readback"); break;
    case Result::completed_needs_current_observation:
        require(code==Code::context_replaced && effects && !publication, "invalid context-replaced document-action"); break;
    case Result::rejected:
        require(static_cast<unsigned>(code)>=1 && static_cast<unsigned>(code)<=8 && !effects && !publication,
            "invalid pre-entry document-action rejection"); break;
    case Result::indeterminate:
        require(code==Code::readback_failed && effects, "invalid post-effect document-action uncertainty"); break;
    default: throw std::invalid_argument("unknown document-action result");
    }
}
// The native NDV2 record retains full-width identities. DAV1 has the existing
// consumer bounds without fabricating an NDV2 Query/Reply or a nested token.
void publicationValid(const N::OwnedPublication& publication, const Request& request) {
    require(publication.identity==identity(request.key), "foreign document-action publication identity");
    require(publication.version.revision>=request.expected.revision &&
        publication.version.revision<=N::maxConsumerInteger, "document-action readback revision is unrepresentable or stale");
    require(publication.editor.revision<=static_cast<std::uint64_t>(std::numeric_limits<std::int32_t>::max()),
        "unrepresentable document-action editor revision");
    for (const auto& node:publication.nodes) {
        nodeValid(node.id);
        require(node.parent<=N::maxConsumerInteger, "unrepresentable document-action parent");
    }
    for (const auto& control:publication.forms.controls) {
        nodeValid(control.node);
        if (control.lease) {
            nodeValid(control.lease->node);
            require(control.lease->captured.revision<=N::maxConsumerInteger, "unrepresentable document-action lease revision");
        }
        if (const auto* select=std::get_if<F::FormSelectState>(&control.state))
            for (const auto& option:select->options) nodeValid(option.node);
    }
}
} // namespace

N::Identity identity(Key key) noexcept { return {key.application_instance,key.service_generation,key.document_sequence}; }
Request encodeRequest(Key key, F::FormVersion expected, const Action& action) {
    keyValid(key);
    require(expected.generation==key.application_instance && expected.epoch==key.service_generation &&
        expected.revision && expected.revision<=N::maxConsumerInteger, "document-action displayed Version mismatch");
    require(!action.valueless_by_exception(), "valueless document-action");
    const bool chooser=std::holds_alternative<ChooseSingleOption>(action);
    require(chooser ? key.nested_request_id==0 : key.nested_request_id!=0, "document-action nested-token domain mismatch");
    Request result; result.key=key; result.expected=expected;
    header(result.bytes,1); putKey(result.bytes,key);
    put(result.bytes,64,expected.generation,8); put(result.bytes,72,expected.epoch,8); put(result.bytes,80,expected.revision,8);
    std::visit([&](const auto& value) {
        using T=std::decay_t<decltype(value)>;
        if constexpr (std::is_same_v<T,Select>) {
            endpointValid(value.anchor); endpointValid(value.focus);
            put(result.bytes,88,2,1); putEndpoint(result.bytes,96,value.anchor); putEndpoint(result.bytes,109,value.focus);
        } else {
            nodeValid(value.node); put(result.bytes,96,value.node,8);
            if constexpr (std::is_same_v<T,Focus>) put(result.bytes,88,0,1);
            else if constexpr (std::is_same_v<T,Activate>) put(result.bytes,88,1,1);
            else { nodeValid(value.option); put(result.bytes,88,3,1); put(result.bytes,104,value.option,8); }
        }
    },action);
    result.action=action; return result;
}
Request decodeRequest(std::span<const std::uint8_t> bytes) {
    require(bytes.size()==BIB_ENGINE_DOCUMENT_ACTIONS_V1_REQUEST_BYTES, "document-action request must be exactly 128 bytes");
    headerValid(bytes,1); const auto key=getKey(bytes);
    const F::FormVersion expected{get(bytes,64,8),get(bytes,72,8),get(bytes,80,8)};
    Action action;
    switch (get(bytes,88,1)) {
    case 0: action=Focus{get(bytes,96,8)}; break;
    case 1: action=Activate{get(bytes,96,8)}; break;
    case 2: action=Select{getEndpoint(bytes,96),getEndpoint(bytes,109)}; break;
    case 3: action=ChooseSingleOption{get(bytes,96,8),get(bytes,104,8)}; break;
    default: throw std::invalid_argument("unknown document-action tag");
    }
    auto result=encodeRequest(key,expected,action);
    require(std::equal(bytes.begin(),bytes.end(),result.bytes.begin()), "nonzero document-action padding");
    return result;
}
Bytes encodeCompletion(const Request& expected, const Completion& completion) {
    expectedValid(expected);
    require(completion.key==expected.key, "foreign document-action completion key");
    statusValid(completion.result,completion.code,completion.effects_entered,completion.publication.has_value());
    Bytes record;
    if (completion.publication) {
        publicationValid(*completion.publication,expected);
        record=N::encodePublicationRecord(*completion.publication);
    }
    Bytes bytes(prefixBytes+record.size()); header(bytes,2); putKey(bytes,completion.key);
    put(bytes,64,static_cast<unsigned>(completion.result),1); put(bytes,65,static_cast<unsigned>(completion.code),1);
    put(bytes,66,completion.effects_entered,1); put(bytes,67,!record.empty(),1); put(bytes,68,record.size(),4);
    std::copy(record.begin(),record.end(),bytes.begin()+prefixBytes); return bytes;
}
Completion decodeCompletion(std::span<const std::uint8_t> bytes, const Request& expected) {
    expectedValid(expected);
    require(bytes.size()>=prefixBytes && bytes.size()<=maxReplyBytes, "document-action completion byte bound exceeded");
    headerValid(bytes,2); const auto key=getKey(bytes); require(key==expected.key, "foreign document-action completion key");
    const auto result=get(bytes,64,1), code=get(bytes,65,1), flags=get(bytes,66,1), present=get(bytes,67,1), length=get(bytes,68,4);
    require(result<=3 && code<=9 && flags<=1 && present<=1 && length==bytes.size()-prefixBytes &&
        (present!=0)==(length!=0), "noncanonical document-action completion");
    Completion completion; completion.key=key; completion.result=static_cast<Result>(result);
    completion.code=static_cast<Code>(code); completion.effects_entered=flags!=0;
    statusValid(completion.result,completion.code,completion.effects_entered,present!=0);
    if (present) {
        completion.publication=N::decodePublicationRecord(bytes.subspan(prefixBytes));
        publicationValid(*completion.publication,expected);
    }
    return completion;
}
} // namespace BIB::NativeDocumentActionsV1
