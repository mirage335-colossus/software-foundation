// SPDX-License-Identifier: CC0-1.0
// New private editor2035 source candidate; actual WebCore compilation UNRUN.
#include "BibNativeEditorWireAdapter.hpp"
#include "BibNativeEditorBackend.hpp"
#include "native_editor_codec.hpp"
#include "engine_editor_pins.hpp"
#include <algorithm>
#include <atomic>
#include <cstring>
#include <limits>
#include <new>
#include <span>
#include <stdexcept>
#include <thread>
#include <type_traits>
#include <utility>
#include <variant>

namespace bib::provider_candidate {
namespace {
namespace N = foundation::ui::native_editor;
namespace C = N::codec;
using Span = std::span<const std::uint8_t>;
using Request = std::variant<C::ProjectionQuery, C::NativeRequestEnvelope, C::RevocationEnvelope>;
constexpr std::uint32_t command_domain = 0, query_domain = 1;
constexpr std::size_t native_outcome_offset = BIB_ENGINE_EDITOR_WIRE_HEADER_BYTES + 5 * sizeof(std::uint64_t);

bool bytes_valid(const BibEngineBytesV1* value, std::uint32_t maximum) noexcept {
    return value && !value->reserved && value->length && value->length <= maximum && value->data;
}
Span bytes(const BibEngineBytesV1& value) noexcept { return {value.data, value.length}; }
bool equal_bytes(Span left, Span right) noexcept {
    return left.size() == right.size() && std::equal(left.begin(), left.end(), right.begin());
}
bool schema_matches(const std::uint8_t* value) noexcept {
    return std::equal(foundation::appended::engine_editor::kSchema.begin(),
        foundation::appended::engine_editor::kSchema.end(), value);
}
bool same_owner(const N::Identity& a, const N::Identity& b) noexcept {
    return a.owner == b.owner && a.generation == b.generation && a.epoch == b.epoch;
}
bool same_context(const N::Identity& a, const N::Identity& b) noexcept {
    return same_owner(a, b) && a.context == b.context;
}
bool known(const N::NativeResult& value) noexcept {
    return value.outcome == N::Outcome::applied || value.outcome == N::Outcome::cancelled
        || value.outcome == N::Outcome::rejected;
}
bool known_wire_outcome(Span value) noexcept {
    if (value.size() < native_outcome_offset + 4) return false;
    std::uint32_t outcome{};
    for (unsigned i = 0; i < 4; ++i)
        outcome |= std::uint32_t(value[native_outcome_offset + i]) << (i * 8);
    return outcome <= 2; // Never deep-decode/normalize an unknown outcome3.
}
const C::WireTarget& target(const Request& request) {
    return std::visit([](const auto& value) -> const C::WireTarget& { return value.target; }, request);
}
const N::Identity& surface_identity(const Request& request) {
    return std::visit([](const auto& value) -> const N::Identity& {
        using T = std::decay_t<decltype(value)>;
        if constexpr (std::is_same_v<T, C::ProjectionQuery>) return value.identity;
        else if constexpr (std::is_same_v<T, C::NativeRequestEnvelope>) return value.request.resolved.identity;
        else return value.request.identity;
    }, request);
}
bool request_join(const C::NativeRequestEnvelope& value) noexcept {
    const auto& actual = value.request.resolved;
    const auto& basis = value.request.packet.basis;
    // Presentation revisions may differ across the separately owned query and
    // observation. Compare native/session authority without rewriting either.
    return same_context(actual.identity, basis.identity) && actual.editor_revision == basis.editor_revision
        && actual.surrounding == basis.surrounding && actual.selection == basis.selection
        && actual.backward == basis.backward && actual.composition == basis.composition;
}
bool query_reply_join(const C::ProjectionQuery& original, const C::ProjectionReply& reply) noexcept {
    if (reply.target != original.target || reply.identity != original.identity
        || !reply.readback_attested || !reply.observation_revision) return false;
    if (reply.state != C::ProjectionReply::State::available)
        return !reply.projection && (reply.state == C::ProjectionReply::State::noneditable
            || reply.state == C::ProjectionReply::State::unavailable);
    return reply.projection && reply.projection->identity == reply.identity
        && (!original.mapping_id || reply.projection->mapping_id == original.mapping_id);
}
bool base_result_join(const N::Identity& original, const N::NativeResult& result) noexcept {
    if (!known(result) || !result.readback_attested || !result.observation_revision
        || !same_owner(original, result.readback_identity)) return false;
    if (result.availability == N::NativeAvailability::available)
        return result.projection && result.projection->identity == result.readback_identity
            && result.projection->retire && (!result.retire || result.retire == result.projection->retire);
    return (result.availability == N::NativeAvailability::noneditable
        || result.availability == N::NativeAvailability::unavailable)
        && !result.projection && !result.allow_default && !result.key_retarget_attested;
}
bool apply_reply_join(const C::NativeRequestEnvelope& original, const N::NativeResult& result) noexcept {
    const auto& resolved = original.request.resolved;
    const auto& observed = original.request.packet.observation;
    if (!base_result_join(resolved.identity, result)) return false;
    if (result.retired && (!resolved.retire || result.retired != resolved.retire)) return false;
    if (result.availability != N::NativeAvailability::available) {
        if (result.outcome == N::Outcome::applied || result.continuity != N::Continuity::replaced) return false;
    } else {
        const auto& next = *result.projection;
        if (resolved.retire && (!next.retire
            || (next.retire->token != resolved.retire->token && !result.retired))) return false;
        if (result.retired && (!next.retire || next.retire->token == result.retired->token
            || (result.continuity != N::Continuity::key_retarget && result.continuity != N::Continuity::replaced))) return false;
        if (result.continuity == N::Continuity::same) {
            if (!same_context(resolved.identity, next.identity) || resolved.frame_id != next.frame_id) return false;
        } else if (result.continuity == N::Continuity::key_retarget) {
            if ((observed.authority != N::Authority::native && observed.authority != N::Authority::default_action)
                || !result.key_retarget_attested || result.changed_focused_frame || resolved.frame_id != next.frame_id
                || (observed.kind == N::Kind::key && !result.key_dispatch_attested)) return false;
        } else if (result.continuity != N::Continuity::replaced) return false;
    }
    const auto* composing = std::get_if<N::CompositionData>(&observed.data);
    const auto transaction = composing ? observed.transaction : resolved.composition;
    if (result.composition) {
        const auto& fact = *result.composition;
        if (!transaction || fact.transaction != transaction || !result.composition_readback_attested) return false;
        if (fact.state == N::CompositionState::live) {
            if (!result.projection || result.projection->composition != fact.transaction) return false;
        } else if (fact.state == N::CompositionState::pending || fact.state == N::CompositionState::ended) {
            if (result.projection && result.projection->composition) return false;
        } else return false;
    } else if ((result.projection && result.projection->composition) || resolved.composition
        || (composing && result.outcome == N::Outcome::applied)) return false;
    if (composing && result.outcome == N::Outcome::applied) {
        const bool ending = composing->operation == foundation::gui_surface::CompositionOperation::commit
            || composing->operation == foundation::gui_surface::CompositionOperation::cancel;
        if (!result.composition || ending != (result.composition->state == N::CompositionState::ended)) return false;
    }
    return true;
}
bool revoke_reply_join(const C::RevocationEnvelope& original, const N::NativeResult& result) noexcept {
    if (!base_result_join(original.request.identity, result) || result.outcome != N::Outcome::applied
        || !result.retired || *result.retired != original.request.material || result.allow_default
        || result.key_retarget_attested || result.key_dispatch_attested
        || (result.continuity != N::Continuity::same && result.continuity != N::Continuity::replaced)) return false;
    if (result.availability == N::NativeAvailability::available) {
        if (!result.composition_readback_attested || result.projection->composition
            || !result.projection->retire || result.projection->retire->token == result.retired->token
            || (result.continuity == N::Continuity::same
                && !same_context(original.request.identity, result.projection->identity))) return false;
    } else if (result.continuity != N::Continuity::replaced) return false;
    if (result.composition && (!original.request.material.composition || !result.composition_readback_attested
        || result.composition->transaction != original.request.material.composition
        || result.composition->state != N::CompositionState::ended)) return false;
    return !original.request.material.composition || (result.composition && result.composition_readback_attested);
}
} // namespace

struct NativeEditorWireAdapter::Impl final {
    struct Record {
        std::uint32_t domain{}, operation{};
        Request decoded;
        C::Bytes original, reply;
        // Allocate these slots before Backend entry; retain the actual result,
        // including unknown, even if later validation/serialization fails.
        std::optional<C::ProjectionReply> projection;
        std::optional<C::NativeResultEnvelope> native;
        bool complete{};
    };
    NativeEditorBackend& backend;
    const std::uint64_t worker, application;
    const std::thread::id owner{std::this_thread::get_id()};
    std::atomic<bool> poisoned{};
    std::uint64_t highest_sequence{}, metadata_epoch{1}, entered_epoch{};
    const N::Identity* entered{};
    std::unique_ptr<Record> retained;
    Impl(std::uint64_t w, std::uint64_t a, NativeEditorBackend& b) : backend(b), worker(w), application(a) {
        if (!worker || !application) throw std::invalid_argument("Zero native editor wire binding identity");
    }
    bool on_owner() const noexcept { return owner == std::this_thread::get_id(); }
    std::int32_t fail() noexcept { poisoned.store(true, std::memory_order_release); return BIB_ENGINE_PROCESS_EXIT_REQUIRED; }
    bool join(std::uint64_t w, const BibEngineDocumentV1* doc, std::uint64_t sequence, const C::WireTarget& t) const noexcept {
        return w == worker && doc && doc->application_instance == application && doc->document_sequence
            && doc->service_generation && sequence && sequence <= BIB_ENGINE_DOCUMENT_V2_MAX_ORDINARY_SEQUENCE
            && t.worker_epoch == worker && t.application_instance == application
            && t.document_sequence == doc->document_sequence && t.service_generation == doc->service_generation
            && t.request_sequence == sequence;
    }
    bool decode(std::uint32_t domain, std::uint32_t operation, const BibEngineBytesV1* input, Request& output) const {
        if (domain == query_domain && operation == BIB_ENGINE_QUERY_EDITOR_PROJECTION_V1
            && bytes_valid(input, BIB_ENGINE_EDITOR_MAX_QUERY_BYTES)) {
            C::ProjectionQuery value;
            if (!C::decode_projection_query(bytes(*input), value)) return false;
            output = std::move(value); return true;
        }
        if (domain != command_domain || !bytes_valid(input, BIB_ENGINE_EDITOR_MAX_WIRE_BYTES)) return false;
        if (operation == BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1) {
            C::NativeRequestEnvelope value;
            if (!C::decode_native_request(bytes(*input), value) || !request_join(value)) return false;
            output = std::move(value); return true;
        }
        if (operation == BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1) {
            C::RevocationEnvelope value;
            if (!C::decode_revocation(bytes(*input), value)) return false;
            output = std::move(value); return true;
        }
        return false;
    }
    bool destination(const BibEngineReplyBufferV1* value) const noexcept {
        return value && value->size >= sizeof(*value) && value->bytes
            && value->capacity >= BIB_ENGINE_EDITOR_REPLY_CAPACITY;
    }
    void prepare(std::uint32_t domain, std::uint32_t operation, const BibEngineBytesV1& input, Request decoded) {
        auto next = std::make_unique<Record>();
        next->domain = domain; next->operation = operation;
        next->decoded = std::move(decoded);
        next->original.assign(input.data, input.data + input.length);
        next->reply.resize(BIB_ENGINE_EDITOR_REPLY_CAPACITY);
        if (domain == query_domain) next->projection.emplace();
        else { next->native.emplace(); next->native->target = target(next->decoded); }
        retained = std::move(next); // No entered effect can discard this record.
        highest_sequence = target(retained->decoded).request_sequence;
    }
    struct Entered {
        Impl& self;
        explicit Entered(Impl& value) : self(value) {
            self.entered = &surface_identity(self.retained->decoded);
            self.entered_epoch = self.metadata_epoch;
        }
        ~Entered() { self.entered = nullptr; self.entered_epoch = 0; }
    };
    bool retain_encoded(const C::Bytes& encoded, BibEngineReplyBufferV1& output) {
        if (encoded.empty() || encoded.size() > retained->reply.size() || encoded.size() > output.capacity) return false;
        std::copy(encoded.begin(), encoded.end(), retained->reply.begin());
        retained->reply.resize(encoded.size());
        std::memcpy(output.bytes, retained->reply.data(), retained->reply.size());
        retained->complete = true;
        return true;
    }
};

NativeEditorWireAdapter::NativeEditorWireAdapter(std::uint64_t worker, std::uint64_t application, NativeEditorBackend& backend)
    : impl_(std::make_unique<Impl>(worker, application, backend)) { }
NativeEditorWireAdapter::~NativeEditorWireAdapter() = default; // Inert bytes only; no Backend cleanup.

std::int32_t NativeEditorWireAdapter::admit_request(std::uint64_t worker, const BibEngineDocumentV1* doc,
    std::uint32_t domain, std::uint32_t operation, std::uint64_t sequence, const BibEngineBytesV1* input) noexcept {
    const auto& self = *impl_;
    if (!self.on_owner()) return BIB_ENGINE_WRONG_THREAD;
    if (self.poisoned.load(std::memory_order_acquire)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    try {
        Request decoded;
        if (!self.decode(domain, operation, input, decoded) || !self.join(worker, doc, sequence, target(decoded))) return BIB_ENGINE_INVALID;
        if (self.entered || sequence <= self.highest_sequence) return BIB_ENGINE_STALE;
        return std::visit([&](const auto& value) { return self.backend.admit_metadata(value); }, decoded)
            ? BIB_ENGINE_OK : BIB_ENGINE_STALE;
    } catch (const std::bad_alloc&) { return BIB_ENGINE_LIMIT; }
    catch (...) { return BIB_ENGINE_INVALID; }
}

std::int32_t NativeEditorWireAdapter::validate_reply(std::uint64_t worker, const BibEngineDocumentV1* doc,
    std::uint32_t domain, std::uint32_t operation, std::uint64_t sequence,
    const BibEngineBytesV1* original, const BibEngineBytesV1* reply) noexcept {
    const auto& self = *impl_;
    if (!self.on_owner()) return BIB_ENGINE_WRONG_THREAD;
    if (self.poisoned.load(std::memory_order_acquire)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    try {
        const auto* record = self.retained.get();
        if (!record || !record->complete || self.entered || record->domain != domain || record->operation != operation
            || !self.join(worker, doc, sequence, target(record->decoded))
            || !bytes_valid(original, domain == query_domain ? BIB_ENGINE_EDITOR_MAX_QUERY_BYTES : BIB_ENGINE_EDITOR_MAX_WIRE_BYTES)
            || !bytes_valid(reply, BIB_ENGINE_EDITOR_REPLY_CAPACITY)
            || !equal_bytes(bytes(*original), record->original) || !equal_bytes(bytes(*reply), record->reply)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
        if (domain == query_domain) {
            const auto* request = std::get_if<C::ProjectionQuery>(&record->decoded);
            C::ProjectionReply decoded;
            return request && C::decode_projection_reply(bytes(*reply), decoded) && query_reply_join(*request, decoded)
                ? BIB_ENGINE_OK : BIB_ENGINE_PROCESS_EXIT_REQUIRED;
        }
        if (!known_wire_outcome(bytes(*reply))) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
        C::NativeResultEnvelope decoded;
        if (!C::decode_native_result(bytes(*reply), decoded) || decoded.target != target(record->decoded)
            || !known(decoded.result)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
        if (const auto* request = std::get_if<C::NativeRequestEnvelope>(&record->decoded))
            return apply_reply_join(*request, decoded.result) ? BIB_ENGINE_OK : BIB_ENGINE_PROCESS_EXIT_REQUIRED;
        const auto* request = std::get_if<C::RevocationEnvelope>(&record->decoded);
        return request && revoke_reply_join(*request, decoded.result) ? BIB_ENGINE_OK : BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    } catch (...) { return BIB_ENGINE_PROCESS_EXIT_REQUIRED; }
}

std::int32_t NativeEditorWireAdapter::project(std::uint64_t worker, const BibEngineQueryV1* request,
    BibEngineReplyBufferV1* output, BibEngineQueryResultV1* result) noexcept {
    auto& self = *impl_;
    if (!self.on_owner()) return BIB_ENGINE_WRONG_THREAD;
    if (self.poisoned.load(std::memory_order_acquire)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    try {
        Request decoded;
        if (self.entered || !request || request->size < sizeof(*request) || !result || result->size < sizeof(*result)
            || !self.destination(output) || !schema_matches(request->schema_sha256)
            || !self.decode(query_domain, request->kind, &request->payload, decoded)
            || !self.join(worker, &request->expected, target(decoded).request_sequence, target(decoded))
            || target(decoded).request_sequence <= self.highest_sequence) return self.fail();
        self.prepare(query_domain, request->kind, request->payload, std::move(decoded));
        Impl::Entered entered(self);
        const auto& original = std::get<C::ProjectionQuery>(self.retained->decoded);
        *self.retained->projection = self.backend.query(original);
        const auto& actual = *self.retained->projection;
        if (!query_reply_join(original, actual)) return self.fail();
        C::Bytes encoded;
        // Codec may still allocate while serializing. Failure after native entry
        // is terminal; the complete original and actual result remain owned.
        if (!C::encode_projection_reply(actual, encoded) || !self.retain_encoded(encoded, *output)) return self.fail();
        *result = {sizeof(*result), static_cast<std::uint32_t>(encoded.size()), request->expected, actual.observation_revision};
        return BIB_ENGINE_OK;
    } catch (...) { return self.fail(); }
}

std::int32_t NativeEditorWireAdapter::apply(std::uint64_t worker, const BibEngineCommandV1* request,
    BibEngineReplyBufferV1* output, BibEngineCommandResultV1* result) noexcept {
    auto& self = *impl_;
    if (!self.on_owner()) return BIB_ENGINE_WRONG_THREAD;
    if (self.poisoned.load(std::memory_order_acquire)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    try {
        Request decoded;
        if (self.entered || !request || request->size < sizeof(*request) || !result || result->size < sizeof(*result)
            || request->operation != BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1 || !self.destination(output)
            || !schema_matches(request->schema_sha256) || !self.decode(command_domain, request->operation, &request->payload, decoded)
            || !self.join(worker, &request->expected, request->request_sequence, target(decoded))
            || request->request_sequence <= self.highest_sequence) return self.fail();
        self.prepare(command_domain, request->operation, request->payload, std::move(decoded));
        Impl::Entered entered(self);
        const auto& original = std::get<C::NativeRequestEnvelope>(self.retained->decoded);
        self.retained->native->result = self.backend.apply_owned(original.request, original.target.request_sequence);
        const auto& actual = self.retained->native->result;
        if (!known(actual)) return self.fail(); // Never encode/decode an unknown result.
        if (!apply_reply_join(original, actual)) return self.fail();
        C::Bytes encoded;
        if (!C::encode_native_result(*self.retained->native, encoded) || !self.retain_encoded(encoded, *output)) return self.fail();
        // Outer handled has no exact separate native return fact. Never infer
        // it from applied/cancelled, default flags or successful void calls.
        *result = {sizeof(*result), 1, request->request_sequence, static_cast<std::uint32_t>(encoded.size()), 0};
        return BIB_ENGINE_OK;
    } catch (...) { return self.fail(); }
}

std::int32_t NativeEditorWireAdapter::revoke(std::uint64_t worker, const BibEngineCommandV1* request,
    BibEngineReplyBufferV1* output, BibEngineCommandResultV1* result) noexcept {
    auto& self = *impl_;
    if (!self.on_owner()) return BIB_ENGINE_WRONG_THREAD;
    if (self.poisoned.load(std::memory_order_acquire)) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
    try {
        Request decoded;
        if (self.entered || !request || request->size < sizeof(*request) || !result || result->size < sizeof(*result)
            || request->operation != BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1 || !self.destination(output)
            || !schema_matches(request->schema_sha256) || !self.decode(command_domain, request->operation, &request->payload, decoded)
            || !self.join(worker, &request->expected, request->request_sequence, target(decoded))
            || request->request_sequence <= self.highest_sequence) return self.fail();
        self.prepare(command_domain, request->operation, request->payload, std::move(decoded));
        Impl::Entered entered(self);
        const auto& original = std::get<C::RevocationEnvelope>(self.retained->decoded);
        self.retained->native->result = self.backend.revoke_owned(original.request, original.target.request_sequence);
        const auto& actual = self.retained->native->result;
        if (!known(actual)) return self.fail();
        if (!revoke_reply_join(original, actual)) return self.fail();
        C::Bytes encoded;
        if (!C::encode_native_result(*self.retained->native, encoded) || !self.retain_encoded(encoded, *output)) return self.fail();
        *result = {sizeof(*result), 1, request->request_sequence, static_cast<std::uint32_t>(encoded.size()), 0};
        return BIB_ENGINE_OK;
    } catch (...) { return self.fail(); }
}

std::optional<foundation::gui_surface::Identity> NativeEditorWireAdapter::entered_surface_identity(std::uint64_t context) const {
    const auto& self = *impl_;
    if (!self.on_owner() || self.poisoned.load(std::memory_order_acquire) || !context || !self.entered
        || self.entered_epoch != self.metadata_epoch || self.entered->context != context) return std::nullopt;
    return *self.entered;
}
void NativeEditorWireAdapter::invalidate_metadata() noexcept {
    auto& self = *impl_;
    if (!self.on_owner()) { (void)self.fail(); return; }
    if (self.metadata_epoch == std::numeric_limits<std::uint64_t>::max()) (void)self.fail();
    else ++self.metadata_epoch;
    // Preserve retained original/result bytes and unknown evidence. This call
    // revokes metadata only; the Backend retains its native retirement material.
    self.backend.invalidate_metadata();
}
} // namespace bib::provider_candidate
