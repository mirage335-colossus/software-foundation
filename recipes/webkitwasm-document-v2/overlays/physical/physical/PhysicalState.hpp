// SPDX-License-Identifier: CC0-1.0
#pragma once
#include "appended_engine_input_codec.hpp"
#include <foundation/appended/engine_provider_document_v2.h>
#include <array>
#include <algorithm>
#include <cstring>
#include <limits>
#include <utility>
#include <variant>

namespace bib::provider_candidate::document_physical {
namespace I = foundation::appended::engine_input;
inline bool same(BibEngineDocumentV1 a, BibEngineDocumentV1 b) noexcept {
    return a.application_instance==b.application_instance && a.document_sequence==b.document_sequence && a.service_generation==b.service_generation;
}
struct RequestKey {
    BibEngineDocumentV1 document{};
    std::uint64_t sequence{};
    std::uint32_t operation{}, length{};
    I::Digest schema{};
    std::array<std::uint8_t,I::kMaximumKeyBytes> payload{};
    bool matches(const RequestKey& other) const noexcept {
        return same(document,other.document) && sequence==other.sequence && operation==other.operation &&
            length==other.length && schema==other.schema && payload==other.payload;
    }
};
struct Prepared {
    RequestKey key;
    I::State previous, next;
    std::variant<I::Key,I::Focus,I::Mouse> input;
    std::uint64_t state_version{};
    BibEngineDocumentV1 previous_document{};
};
class PhysicalState final {
public:
    I::State input;
    BibEngineDocumentV1 document{};
    std::uint64_t highest_sequence{}, version{};
    RequestKey latest;
    bool completed{};
    static std::int32_t status(I::Status value) noexcept {
        switch(value) {
        case I::Status::ok:return BIB_ENGINE_OK;
        case I::Status::stale_context:return BIB_ENGINE_STALE;
        case I::Status::unsupported:return BIB_ENGINE_UNSUPPORTED;
        case I::Status::insufficient_capacity:return BIB_ENGINE_LIMIT;
        default:return BIB_ENGINE_INVALID;
        }
    }
    std::int32_t prepare(const BibEngineCommandV1& request, std::uint64_t instance,
        std::uint32_t capacity, Prepared& output) const {
        const auto* facts=I::operation_facts(request.operation);
        if (!facts) return BIB_ENGINE_UNSUPPORTED;
        if (version==UINT64_MAX) return BIB_ENGINE_LIMIT;
        if (request.size!=sizeof(request) || !request.expected.application_instance ||
            request.expected.application_instance!=instance || !request.expected.document_sequence ||
            !request.expected.service_generation || !request.request_sequence ||
            request.request_sequence>BIB_ENGINE_DOCUMENT_V2_MAX_ORDINARY_SEQUENCE ||
            request.payload.reserved || request.payload.length>facts->maximum_input_bytes ||
            (request.payload.length && !request.payload.data) ||
            request.payload.length>std::numeric_limits<std::uintptr_t>::max()-reinterpret_cast<std::uintptr_t>(request.payload.data) ||
            capacity<facts->required_reply_capacity ||
            std::memcmp(request.schema_sha256,facts->schema_sha256.data(),32)) return BIB_ENGINE_INVALID;
        if (request.request_sequence<=highest_sequence) return BIB_ENGINE_STALE;
        Prepared candidate;
        candidate.state_version=version; candidate.previous_document=document;
        candidate.previous=input;
        if (!same(document,request.expected)) I::retire_document(candidate.previous);
        candidate.next=candidate.previous;
        const std::span<const std::uint8_t> bytes{request.payload.data,request.payload.length};
        I::Status checked;
        if (request.operation==1) {
            I::Key key; checked=I::decode_key(bytes,key);
            if (checked==I::Status::ok) checked=I::accept_key(candidate.next,key);
            candidate.input=std::move(key);
        } else if (request.operation==3) {
            I::Focus focus; checked=I::decode_focus(bytes,focus);
            if (checked==I::Status::ok) checked=I::accept_focus(candidate.next,focus);
            candidate.input=focus;
        } else {
            I::Mouse mouse; checked=I::decode_mouse(bytes,mouse);
            if (checked==I::Status::ok) checked=I::accept_mouse(candidate.next,mouse);
            candidate.input=mouse;
        }
        if (checked!=I::Status::ok) return status(checked);
        candidate.key.document=request.expected; candidate.key.sequence=request.request_sequence;
        candidate.key.operation=request.operation; candidate.key.length=request.payload.length;
        std::copy(facts->schema_sha256.begin(),facts->schema_sha256.end(),candidate.key.schema.begin());
        std::copy(bytes.begin(),bytes.end(),candidate.key.payload.begin());
        output=std::move(candidate);
        return BIB_ENGINE_OK;
    }
    bool commit(const Prepared& prepared) noexcept {
        if (prepared.state_version!=version || !same(prepared.previous_document,document) ||
            prepared.key.sequence<=highest_sequence || version==UINT64_MAX) return false;
        // Before any native author callback. No allocation/decoding below.
        input=prepared.next; document=prepared.key.document; highest_sequence=prepared.key.sequence;
        latest=prepared.key; completed=false; ++version; return true;
    }
    bool finish(const RequestKey& key) noexcept {
        if (!latest.matches(key)) return false;
        completed=true; return true;
    }
    void invalidate() noexcept {
        I::retire_document(input); document={};
        // Exhaustion blocks every further prepare/commit; never wrap authority.
        if (version!=UINT64_MAX) ++version;
    }
    bool reply_matches(const BibEngineCommandV1& request, const BibEngineBytesV1& reply) const noexcept {
        if (!completed || request.payload.reserved || request.payload.length>latest.payload.size() ||
            (request.payload.length&&!request.payload.data) || reply.reserved || reply.length ||
            request.size!=sizeof(request) || !same(request.expected,latest.document) ||
            request.operation!=latest.operation || request.request_sequence!=latest.sequence ||
            request.payload.length!=latest.length || std::memcmp(request.schema_sha256,latest.schema.data(),32)) return false;
        return !request.payload.length || !std::memcmp(request.payload.data,latest.payload.data(),request.payload.length);
    }
};
} // namespace bib::provider_candidate::document_physical
