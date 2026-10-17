// SPDX-License-Identifier: CC0-1.0
// Standalone fake-owner tests only; no fake engine or WebCore implementation.
#include "LegacyHostAdapters.hpp"
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>

using bib::provider_candidate::LegacyHostAdapters;
using bib::provider_candidate::ServiceRetentionLimits;
namespace bib::provider_candidate {
struct LegacyHostAdaptersTestAccess {
    static void exhaust_after_next_identity(LegacyHostAdapters& adapter) noexcept {
        adapter.next_epoch_ = std::numeric_limits<std::uint64_t>::max();
        adapter.next_lease_ = std::numeric_limits<std::uint64_t>::max();
    }
};
}
namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
BibEngineLimitsV1 limits(std::uint32_t inflight = 4, std::uint64_t retained = 16) {
    return {sizeof(BibEngineLimitsV1), 1024, 1024, 1024, 4096, 3, inflight, 0, 8, retained};
}
constexpr ServiceRetentionLimits retention{7, 8192};
constexpr BibEngineDocumentV1 prospective{91, 17, 0};
struct FakeOwner {
    enum class ResponseMode {
        normal, rejected, throws_after_lease, bad_size, mime_reserved, redirect,
        null_mime, null_body, oversized_body, oversized_content, invalid_mime,
        wrong_get_length, head_has_body, http_not_found
    } mode{ResponseMode::normal};
    enum Throw : unsigned { enter_throw = 1, leave_throw = 2, begin_throw = 4,
        close_throw = 8, submit_throw = 16, cancel_throw = 32, ack_throw = 64, wake_throw = 128 };
    struct ProducerLease {
        bool active{};
        std::uint32_t released{};
        std::array<std::uint8_t, 10> mime{};
        std::array<std::uint8_t, 4> body{};
    };
    struct Epoch {
        FakeOwner* owner{};
        std::uint64_t number{};
        std::uint32_t retired{};
        std::uint32_t resolves{};
        std::uint32_t releases{};
        std::uint64_t next_lease{1};
        std::array<ProducerLease, 32> leases{};
    };
    std::array<Epoch, 16> epochs{};
    BibEngineDocumentV1 service_document{};
    BibEngineDocumentV1 resource_document{};
    BibEngineResourceRequestV1 last_request{};
    const std::uint8_t* submitted_pointer{};
    std::vector<std::uint8_t> owned_submission;
    std::uint64_t submitted_generation{};
    std::uint32_t submitted_source{};
    std::uint32_t submit_reserved{99};
    std::uint64_t closed_generation{};
    std::uint64_t cancelled_generation{};
    std::uint64_t cancelled_sequence{};
    std::uint64_t ack_generation{};
    std::uint64_t ack_through{};
    std::uint32_t ack_calls{};
    std::uint32_t ack_status{2};
    std::uint32_t submit_status{};
    std::uint32_t cancel_status{};
    std::uint32_t begin_calls{};
    std::uint32_t resource_begin_calls{};
    std::uint32_t enter_calls{};
    std::uint32_t enter_status{};
    std::uint32_t leave_calls{};
    std::uint32_t wake_calls{};
    std::uint64_t next_epoch{1};
    std::uint64_t duplicate_epoch{};
    bool malformed_begin{};
    bool throw_resource_begin{};
    bool reject_resource_begin{};
    std::int32_t resource_begin_status{};
    std::int32_t resource_resolve_status{};
    bool throw_release{};
    bool throw_retire{};
    bool reenter_resolve{};
    bool reenter_release{};
    BibAppResourceBundleHostV1 reentrant_bundle{};
    BibAppResourceHostV1 reentrant_epoch{};
    std::uint64_t reentrant_lease{};
    std::int32_t nested_resolve_status{};
    std::int32_t nested_begin_status{};
    unsigned throwing{};

    static FakeOwner& self(void* context) { return *static_cast<FakeOwner*>(context); }
    static std::uint32_t BIB_ENGINE_CALL enter(void* context) {
        auto& owner = self(context); ++owner.enter_calls;
        if (owner.throwing & enter_throw) throw std::runtime_error("enter");
        return owner.enter_status;
    }
    static void BIB_ENGINE_CALL leave(void* context) {
        auto& owner = self(context); ++owner.leave_calls;
        if (owner.throwing & leave_throw) throw std::runtime_error("leave");
    }
    static std::uint64_t BIB_ENGINE_CALL begin(void* context, const BibEngineDocumentV1* document) {
        auto& owner = self(context); ++owner.begin_calls; owner.service_document = *document;
        if (owner.throwing & begin_throw) throw std::runtime_error("begin");
        return 501;
    }
    static void BIB_ENGINE_CALL close(void* context, std::uint64_t generation) {
        auto& owner = self(context); owner.closed_generation = generation;
        if (owner.throwing & close_throw) throw std::runtime_error("close");
    }
    static std::uint32_t BIB_ENGINE_CALL submit(void* context, std::uint64_t generation,
        const BibEngineBytesV1* bytes, std::uint32_t source) {
        auto& owner = self(context);
        owner.submitted_generation = generation; owner.submitted_source = source;
        owner.submit_reserved = bytes->reserved; owner.submitted_pointer = bytes->data;
        owner.owned_submission.assign(bytes->data, bytes->data + bytes->length);
        if (owner.throwing & submit_throw) throw std::runtime_error("submit");
        return owner.submit_status;
    }
    static std::uint32_t BIB_ENGINE_CALL cancel(void* context, std::uint64_t generation, std::uint64_t sequence) {
        auto& owner = self(context); owner.cancelled_generation = generation; owner.cancelled_sequence = sequence;
        if (owner.throwing & cancel_throw) throw std::runtime_error("cancel");
        return owner.cancel_status;
    }
    static std::uint32_t BIB_ENGINE_CALL ack(void* context, std::uint64_t generation, std::uint64_t through) {
        auto& owner = self(context); ++owner.ack_calls;
        owner.ack_generation = generation; owner.ack_through = through;
        if (owner.throwing & ack_throw) throw std::runtime_error("ack");
        return owner.ack_status;
    }
    static void BIB_ENGINE_CALL wake(void* context) {
        auto& owner = self(context); ++owner.wake_calls;
        if (owner.throwing & wake_throw) throw std::runtime_error("wake");
    }
    static std::int32_t BIB_ENGINE_CALL begin_resource(void* context, const BibEngineDocumentV1* document,
        BibEngineResourceEpochV1* output) {
        auto& owner = self(context); ++owner.resource_begin_calls; owner.resource_document = *document;
        const auto number = owner.duplicate_epoch ? owner.duplicate_epoch : owner.next_epoch++;
        auto& epoch = owner.epochs.at(static_cast<std::size_t>(number));
        if (!owner.duplicate_epoch) { epoch.owner = &owner; epoch.number = number; }
        *output = {sizeof(*output), 0, number, &epoch, resolve, release};
        if (owner.malformed_begin) output->size = 0;
        if (owner.throw_resource_begin) throw std::runtime_error("begin resource");
        return owner.reject_resource_begin ? BIB_ENGINE_LIMIT : owner.resource_begin_status;
    }
    static void BIB_ENGINE_CALL retire_resource(void* context, std::uint64_t number) {
        auto& owner = self(context); ++owner.epochs.at(static_cast<std::size_t>(number)).retired;
        if (owner.throw_retire) throw std::runtime_error("retire");
    }
    static std::int32_t BIB_ENGINE_CALL resolve(void* context, const BibEngineResourceRequestV1* request,
        BibEngineResourceResponseV1* output) {
        auto& epoch = *static_cast<Epoch*>(context); auto& owner = *epoch.owner;
        ++epoch.resolves; owner.last_request = *request;
        if (owner.reenter_resolve) {
            owner.reentrant_bundle.retire_epoch(owner.reentrant_bundle.context, owner.reentrant_epoch.document_epoch);
            const BibAppResourceRequestV1 nested{sizeof(nested), BIB_APP_RESOURCE_HOST_VERSION,
                owner.reentrant_epoch.document_epoch, request->method.data, request->method.length,
                request->resolved_url.data, request->resolved_url.length};
            BibAppResourceResponseV1 nested_output{};
            owner.nested_resolve_status = owner.reentrant_epoch.resolve(owner.reentrant_epoch.context, &nested, &nested_output);
            BibAppResourceHostV1 nested_epoch{};
            owner.nested_begin_status = owner.reentrant_bundle.begin_epoch(owner.reentrant_bundle.context, &nested_epoch);
            owner.reentrant_epoch.release(owner.reentrant_epoch.context, owner.reentrant_lease);
        }
        if (owner.mode == ResponseMode::http_not_found) {
            static constexpr std::uint8_t plain[]{'t','e','x','t','/','p','l','a','i','n'};
            *output = {sizeof(*output), 404, 0, {plain, sizeof(plain), 0}, nullptr, 0, 0};
            return BIB_ENGINE_OK;
        }
        const auto number = epoch.next_lease++;
        auto& lease = epoch.leases.at(static_cast<std::size_t>(number));
        lease.active = true;
        std::memcpy(lease.mime.data(), "text/plain", lease.mime.size());
        std::memcpy(lease.body.data(), "data", lease.body.size());
        const bool head = request->method.length == 4 && std::memcmp(request->method.data, "HEAD", 4) == 0;
        *output = {sizeof(*output), 200, number,
            {lease.mime.data(), static_cast<std::uint32_t>(lease.mime.size()), 0},
            head ? nullptr : lease.body.data(), head ? 0U : lease.body.size(), lease.body.size()};
        switch (owner.mode) {
        case ResponseMode::normal: break;
        case ResponseMode::rejected: return BIB_ENGINE_LIMIT;
        case ResponseMode::throws_after_lease: throw std::runtime_error("resolve after lease");
        case ResponseMode::bad_size: output->size = 0; break;
        case ResponseMode::mime_reserved: output->mime.reserved = 1; break;
        case ResponseMode::redirect: output->status = 302; break;
        case ResponseMode::null_mime: output->mime.data = nullptr; break;
        case ResponseMode::null_body: output->body = nullptr; break;
        case ResponseMode::oversized_body: output->body_length = 9; break;
        case ResponseMode::oversized_content: output->content_length = 9; break;
        case ResponseMode::invalid_mime: lease.mime.fill('x'); break;
        case ResponseMode::wrong_get_length: output->content_length = 3; break;
        case ResponseMode::head_has_body: output->body = lease.body.data(); output->body_length = lease.body.size(); break;
        case ResponseMode::http_not_found: break;
        }
        return owner.resource_resolve_status;
    }
    static void BIB_ENGINE_CALL release(void* context, std::uint64_t number) {
        auto& epoch = *static_cast<Epoch*>(context);
        auto& lease = epoch.leases.at(static_cast<std::size_t>(number));
        ++epoch.releases; ++lease.released; lease.active = false;
        lease.mime.fill('!'); lease.body.fill('!');
        if (epoch.owner->reenter_release)
            epoch.owner->reentrant_bundle.retire_epoch(epoch.owner->reentrant_bundle.context,
                epoch.owner->reentrant_epoch.document_epoch);
        if (epoch.owner->throw_release) throw std::runtime_error("release");
    }
    BibEngineHostV1 host() {
        BibEngineHostV1 result{};
        result.size = sizeof(result); result.abi_major = BIB_ENGINE_ABI_MAJOR;
        result.abi_minor = BIB_ENGINE_ABI_MINOR; result.context = this;
        result.wake = wake; result.enter_engine = enter; result.leave_engine = leave;
        result.begin_service_document = begin; result.close_service_document = close;
        result.submit_service = submit; result.cancel_service = cancel; result.stage_service_ack = ack;
        result.begin_resource_epoch = begin_resource; result.retire_resource_epoch = retire_resource;
        return result;
    }
};
BibAppResourceHostV1 begin_epoch(LegacyHostAdapters& adapter) {
    const auto bundle = adapter.resource_bundle_hooks();
    BibAppResourceHostV1 epoch{};
    require(bundle.begin_epoch(bundle.context, &epoch) == BIB_ENGINE_OK, "begin epoch");
    return epoch;
}
BibAppResourceRequestV1 request(const BibAppResourceHostV1& epoch, const char* method = "GET") {
    static constexpr char url[] = "app://package/web/index.html";
    return {sizeof(BibAppResourceRequestV1), BIB_APP_RESOURCE_HOST_VERSION, epoch.document_epoch,
        reinterpret_cast<const std::uint8_t*>(method), static_cast<std::uint32_t>(std::strlen(method)),
        reinterpret_cast<const std::uint8_t*>(url), sizeof(url) - 1};
}
BibAppResourceResponseV1 get(const BibAppResourceHostV1& epoch) {
    auto input = request(epoch); BibAppResourceResponseV1 output{};
    require(epoch.resolve(epoch.context, &input, &output) == BIB_ENGINE_OK, "resolve accepted");
    return output;
}
void retire(LegacyHostAdapters& adapter, std::uint64_t value) {
    const auto bundle = adapter.resource_bundle_hooks(); bundle.retire_epoch(bundle.context, value);
}
void copied_tables_and_prospective() {
    FakeOwner owner; auto host = owner.host(); auto bound = limits();
    LegacyHostAdapters adapter(host, bound, retention);
    require(adapter.valid() && adapter.supports_services() && adapter.supports_resources(), "complete callbacks supported");
    require(adapter.service_hooks().begin_document(adapter.service_hooks().context) == 0, "no prospective service admission");
    BibAppResourceHostV1 empty{}; const auto initial_bundle = adapter.resource_bundle_hooks();
    require(initial_bundle.begin_epoch(initial_bundle.context, &empty) == BIB_ENGINE_INVALID, "no prospective resource admission");
    require(owner.begin_calls == 0 && owner.resource_begin_calls == 0, "unready has no callback");
    require(adapter.set_prospective_document(prospective) == BIB_ENGINE_OK, "set prospective");
    require(adapter.set_prospective_document({91, 18, 501}) == BIB_ENGINE_INVALID &&
        adapter.set_prospective_document({0, 18, 0}) == BIB_ENGINE_INVALID, "invalid prospective does not replace valid identity");
    host.context = nullptr; host.begin_service_document = nullptr; bound.maximum_resource_response_bytes = 99;
    const auto services = adapter.service_hooks();
    require(services.size == sizeof(services) && services.version == 1, "exact service layout");
    require(services.max_message_bytes == 4096 && services.max_retained_calls == 7 &&
        services.max_retained_bytes == 8192 && services.max_retired_documents == 3, "exact service limits");
    require(services.begin_document(services.context) == 501, "copied begin callback");
    require(owner.service_document.application_instance == 91 && owner.service_document.document_sequence == 17 &&
        owner.service_document.service_generation == 0, "service prospective identity");
    const auto epoch = begin_epoch(adapter); const auto bundle = adapter.resource_bundle_hooks();
    require(bundle.size == sizeof(bundle) && bundle.version == 1 && !bundle.reserved &&
        bundle.max_response_bytes == 8 && bundle.max_inflight == 4 && bundle.max_retained_bytes == 16, "exact bundle layout and copied limits");
    require(epoch.size == sizeof(epoch) && epoch.version == 1 && !epoch.reserved &&
        epoch.max_response_bytes == 8 && epoch.max_inflight == 4 && epoch.max_retained_bytes == 16, "exact epoch layout and limits");
    require(owner.resource_document.application_instance == 91 && owner.resource_document.document_sequence == 17 &&
        owner.resource_document.service_generation == 0, "resource prospective identity");
    retire(adapter, epoch.document_epoch);
}
void service_spans_and_staged_ack() {
    FakeOwner owner; LegacyHostAdapters adapter(owner.host(), limits(), retention);
    require(adapter.set_prospective_document(prospective) == 0, "prospective");
    const auto hooks = adapter.service_hooks();
    std::array<std::uint8_t, 4> payload{1, 2, 3, 4};
    require(hooks.submit(hooks.context, 501, payload.data(), payload.size(), 2) == 0, "submit status");
    require(owner.submitted_pointer == payload.data() && owner.submit_reserved == 0 &&
        owner.submitted_generation == 501 && owner.submitted_source == 2, "borrowed span transformed");
    payload.fill(9); require(owner.owned_submission == std::vector<std::uint8_t>({1, 2, 3, 4}), "owner copies before admission returns");
    require(hooks.cancel(hooks.context, 501, 71) == 0 && owner.cancelled_generation == 501 && owner.cancelled_sequence == 71, "cancel forwards");
    require(hooks.acknowledge(hooks.context, 501, 71) == 2, "ACK returns unavailable while staged");
    owner.ack_status = 13;
    require(hooks.acknowledge(hooks.context, 501, 71) == 13, "ACK returns actual cached non-OK receipt");
    owner.ack_status = 0;
    require(hooks.acknowledge(hooks.context, 501, 71) == 0 && owner.ack_calls == 3 &&
        owner.ack_generation == 501 && owner.ack_through == 71, "ACK exact receipt identity");
    require(hooks.submit(hooks.context, 501, nullptr, 1, 0) == 1 &&
        hooks.submit(hooks.context, 501, payload.data(), 4097, 0) == 8 &&
        hooks.cancel(hooks.context, 0, 1) == 1 && hooks.acknowledge(hooks.context, 1, 0) == 1, "invalid services refuse before callbacks");
    hooks.close_document(hooks.context, 501); require(owner.closed_generation == 501, "close forwards");
}
void service_exception_containment() {
    FakeOwner owner; LegacyHostAdapters adapter(owner.host(), limits(), retention);
    require(adapter.set_prospective_document(prospective) == 0, "prospective");
    const auto hooks = adapter.service_hooks(); std::uint8_t payload{7};
    owner.throwing = FakeOwner::enter_throw; require(hooks.enter_engine(hooks.context) == 14, "enter exception rejects with uncertain status, never OK");
    owner.throwing = FakeOwner::leave_throw; hooks.leave_engine(hooks.context);
    owner.throwing = FakeOwner::begin_throw; require(hooks.begin_document(hooks.context) == 0, "begin exception rejects");
    owner.throwing = FakeOwner::close_throw; hooks.close_document(hooks.context, 501);
    owner.throwing = FakeOwner::submit_throw; require(hooks.submit(hooks.context, 501, &payload, 1, 0) == 14, "submit exception uncertain");
    owner.throwing = FakeOwner::cancel_throw; require(hooks.cancel(hooks.context, 501, 1) == 14, "cancel exception uncertain");
    owner.throwing = FakeOwner::ack_throw; require(hooks.acknowledge(hooks.context, 501, 1) == 14, "ACK exception uncertain");
    owner.throwing = 0; owner.submit_status = 99; owner.cancel_status = 99; owner.ack_status = 99;
    require(hooks.submit(hooks.context, 501, &payload, 1, 0) == 14 && hooks.cancel(hooks.context, 501, 1) == 14 &&
        hooks.acknowledge(hooks.context, 501, 1) == 14, "invalid service statuses uncertain");
    owner.throwing = FakeOwner::wake_throw; hooks.schedule_owner(hooks.context);
    require(adapter.callback_faulted(), "callback faults retained");
}
void optional_callbacks_and_thread() {
    FakeOwner owner; auto host = owner.host(); host.submit_service = nullptr; host.begin_resource_epoch = nullptr;
    LegacyHostAdapters adapter(host, limits(), retention);
    require(adapter.valid() && !adapter.supports_services() && !adapter.supports_resources(), "absent backend unsupported");
    const auto hooks = adapter.service_hooks();
    require(hooks.submit(hooks.context, 501, nullptr, 0, 0) == 2 && hooks.acknowledge(hooks.context, 501, 1) == 2 &&
        hooks.begin_document(hooks.context) == 0, "absent services unavailable");
    const auto bundle = adapter.resource_bundle_hooks(); BibAppResourceHostV1 output{};
    require(bundle.begin_epoch(bundle.context, &output) == BIB_ENGINE_UNSUPPORTED && output.size == 0, "absent resources reject and clear");
    std::int32_t worker_result{}; std::uint32_t submit_result{};
    std::thread worker([&] {
        worker_result = adapter.set_prospective_document(prospective);
        submit_result = hooks.submit(hooks.context, 501, nullptr, 0, 0);
        hooks.schedule_owner(hooks.context);
    });
    worker.join();
    require(worker_result == BIB_ENGINE_WRONG_THREAD && submit_result == 6 && owner.wake_calls == 1, "owner callbacks guarded and wake worker-safe");
}
void resource_transform_and_lease_lifetime() {
    FakeOwner owner; LegacyHostAdapters adapter(owner.host(), limits(), retention);
    require(adapter.set_prospective_document(prospective) == 0, "prospective");
    const auto epoch = begin_epoch(adapter); auto input = request(epoch); BibAppResourceResponseV1 response{};
    require(epoch.resolve(epoch.context, &input, &response) == 0, "resource success");
    require(owner.last_request.size == sizeof(BibEngineResourceRequestV1) && !owner.last_request.reserved &&
        owner.last_request.resource_epoch == epoch.document_epoch && !owner.last_request.method.reserved &&
        !owner.last_request.resolved_url.reserved && owner.last_request.method.data == input.method &&
        owner.last_request.resolved_url.data == input.resolved_url, "request explicitly transformed and borrowed");
    require(response.size == sizeof(response) && response.version == 1 && response.status == 200 &&
        response.mime_length == 10 && response.body_length == 4 && response.content_length == 4 && response.lease, "response explicitly transformed");
    auto& producer = owner.epochs[epoch.document_epoch];
    require(producer.releases == 0 && adapter.outstanding_resource_leases() == 1 && adapter.retained_raw_resource_bytes() == 4, "lease remains raw after resolve");
    retire(adapter, epoch.document_epoch); retire(adapter, epoch.document_epoch);
    require(producer.retired == 1 && adapter.active_resource_contexts() == 1 &&
        std::memcmp(response.body, "data", 4) == 0 && std::memcmp(response.mime, "text/plain", 10) == 0, "retire forwards once while spans remain live");
    BibAppResourceResponseV1 rejected{};
    require(epoch.resolve(epoch.context, &input, &rejected) == BIB_ENGINE_STALE && producer.resolves == 1, "retired admission closed");
    const std::string copied_body(reinterpret_cast<const char*>(response.body), response.body_length);
    const std::string copied_mime(reinterpret_cast<const char*>(response.mime), response.mime_length);
    epoch.release(epoch.context, response.lease); epoch.release(epoch.context, response.lease);
    require(producer.releases == 1 && producer.leases[1].released == 1 && copied_body == "data" && copied_mime == "text/plain", "copy precedes exactly-once producer release");
    require(adapter.active_resource_contexts() == 0 && adapter.outstanding_resource_leases() == 0 && !adapter.retained_raw_resource_bytes(), "final lease frees retired wrapper");
}
void two_contexts_and_collision_protection() {
    FakeOwner owner; LegacyHostAdapters adapter(owner.host(), limits(), retention);
    require(adapter.set_prospective_document(prospective) == 0, "prospective");
    const auto a = begin_epoch(adapter); const auto b = begin_epoch(adapter);
    const auto ar = get(a); const auto br = get(b);
    require(ar.lease != br.lease && owner.epochs[1].leases[1].active && owner.epochs[2].leases[1].active, "same producer IDs wrapped distinctly");
    retire(adapter, a.document_epoch);
    const auto bundle = adapter.resource_bundle_hooks(); BibAppResourceHostV1 refused{}; refused.size = 999;
    require(bundle.begin_epoch(bundle.context, &refused) == BIB_ENGINE_LIMIT && refused.size == 0 && owner.resource_begin_calls == 2, "retired leased epoch counts toward two contexts");
    b.release(b.context, ar.lease); require(owner.epochs[1].releases == 0 && owner.epochs[2].releases == 0, "wrong-context lease ignored");
    a.release(a.context, ar.lease); require(owner.epochs[1].releases == 1 && owner.epochs[2].releases == 0, "old producer context selected");
    const auto c = begin_epoch(adapter);
    require(c.document_epoch == 3 && adapter.active_resource_contexts() == 2, "released slot reusable");
    a.release(a.context, ar.lease); require(owner.epochs[3].releases == 0, "stale duplicate release cannot hit reused context");
    auto stale = request(a); BibAppResourceResponseV1 stale_output{};
    require(a.resolve(a.context, &stale, &stale_output) == BIB_ENGINE_STALE && owner.epochs[3].resolves == 0, "stale table cannot resolve reused context");
    b.release(b.context, br.lease); retire(adapter, b.document_epoch); retire(adapter, c.document_epoch);
    require(adapter.active_resource_contexts() == 0, "all contexts drained");
}
void malformed_and_rejected_leases() {
    const std::array modes{FakeOwner::ResponseMode::rejected, FakeOwner::ResponseMode::throws_after_lease,
        FakeOwner::ResponseMode::bad_size, FakeOwner::ResponseMode::mime_reserved,
        FakeOwner::ResponseMode::redirect, FakeOwner::ResponseMode::null_mime,
        FakeOwner::ResponseMode::null_body, FakeOwner::ResponseMode::oversized_body,
        FakeOwner::ResponseMode::oversized_content, FakeOwner::ResponseMode::invalid_mime,
        FakeOwner::ResponseMode::wrong_get_length, FakeOwner::ResponseMode::head_has_body};
    for (const auto mode : modes) {
        FakeOwner owner; owner.mode = mode; LegacyHostAdapters adapter(owner.host(), limits(), retention);
        require(adapter.set_prospective_document(prospective) == 0, "prospective");
        const auto epoch = begin_epoch(adapter); auto input = request(epoch, mode == FakeOwner::ResponseMode::head_has_body ? "HEAD" : "GET");
        BibAppResourceResponseV1 output{}; output.size = 999; output.lease = 999;
        require(epoch.resolve(epoch.context, &input, &output) != 0 && !output.size && !output.lease, "bad response rejects with cleared output");
        require(owner.epochs[1].releases == 1 && owner.epochs[1].leases[1].released == 1 &&
            !adapter.outstanding_resource_leases() && !adapter.retained_raw_resource_bytes(), "every malformed/rejected producer lease released once");
        retire(adapter, 1); require(!adapter.active_resource_contexts(), "bad response context still retires");
    }
}
void resource_shared_inflight_limit() {
    FakeOwner owner; LegacyHostAdapters adapter(owner.host(), limits(2), retention);
    require(adapter.set_prospective_document(prospective) == 0, "prospective");
    const auto a = begin_epoch(adapter); const auto b = begin_epoch(adapter); const auto ar = get(a); const auto br = get(b);
    auto input = request(b); BibAppResourceResponseV1 output{};
    require(b.resolve(b.context, &input, &output) == BIB_ENGINE_LIMIT && owner.epochs[2].resolves == 1, "one inflight registry spans epochs");
    retire(adapter, 1); require(b.resolve(b.context, &input, &output) == BIB_ENGINE_LIMIT, "retirement does not reset inflight budget");
    a.release(a.context, ar.lease); const auto next = get(b); b.release(b.context, next.lease); b.release(b.context, br.lease); retire(adapter, 2);
}
void resource_shared_raw_byte_limit() {
    FakeOwner owner; LegacyHostAdapters adapter(owner.host(), limits(4, 8), retention);
    require(adapter.set_prospective_document(prospective) == 0, "prospective");
    const auto a = begin_epoch(adapter); const auto b = begin_epoch(adapter); const auto ar = get(a); const auto br = get(b);
    auto input = request(b); BibAppResourceResponseV1 output{};
    require(b.resolve(b.context, &input, &output) == BIB_ENGINE_LIMIT && owner.epochs[2].releases == 1 &&
        adapter.retained_raw_resource_bytes() == 8, "excess raw body lease released without resetting shared bytes");
    retire(adapter, 1); require(adapter.retained_raw_resource_bytes() == 8, "retire keeps raw body charge");
    a.release(a.context, ar.lease); const auto next = get(b); b.release(b.context, next.lease); b.release(b.context, br.lease); retire(adapter, 2);
    require(!adapter.retained_raw_resource_bytes(), "raw byte budget drained");
}
void invalid_admission_cleanup() {
    for (int mode = 0; mode != 3; ++mode) {
        FakeOwner owner; owner.malformed_begin = mode == 0; owner.throw_resource_begin = mode == 1; owner.reject_resource_begin = mode == 2;
        LegacyHostAdapters adapter(owner.host(), limits(), retention);
        require(adapter.set_prospective_document(prospective) == 0, "prospective");
        const auto bundle = adapter.resource_bundle_hooks(); BibAppResourceHostV1 output{}; output.size = 99;
        require(bundle.begin_epoch(bundle.context, &output) != 0 && !output.size && owner.epochs[1].retired == 1 &&
            !adapter.active_resource_contexts(), "malformed/refused newly-created epoch quarantined");
    }
    FakeOwner owner; LegacyHostAdapters adapter(owner.host(), limits(), retention);
    require(adapter.set_prospective_document(prospective) == 0, "prospective");
    const auto live = begin_epoch(adapter); owner.duplicate_epoch = live.document_epoch;
    const auto bundle = adapter.resource_bundle_hooks(); BibAppResourceHostV1 output{};
    require(bundle.begin_epoch(bundle.context, &output) == BIB_ENGINE_INVALID && owner.epochs[1].retired == 0 &&
        adapter.active_resource_contexts() == 1, "duplicate epoch refusal preserves existing context");
    retire(adapter, live.document_epoch);
}
void translated_resource_epochs_and_exhaustion() {
    {
        FakeOwner owner; owner.next_epoch = 7;
        LegacyHostAdapters adapter(owner.host(), limits(), retention);
        require(adapter.set_prospective_document(prospective) == 0, "prospective");
        const auto high = begin_epoch(adapter); owner.next_epoch = 3; const auto low = begin_epoch(adapter);
        require(high.document_epoch == 1 && low.document_epoch == 2, "legacy epochs issued without assuming producer numeric order");
        const auto response = get(low);
        require(owner.last_request.resource_epoch == 3 && owner.epochs[3].resolves == 1, "request uses exact lower producer epoch");
        retire(adapter, high.document_epoch); retire(adapter, low.document_epoch);
        require(owner.epochs[7].retired == 1 && owner.epochs[3].retired == 1 && adapter.active_resource_contexts() == 1,
            "retirement translates exact producer epochs and holds lower epoch raw lease");
        low.release(low.context, response.lease);
        require(owner.epochs[3].releases == 1 && !adapter.active_resource_contexts(), "lower producer lease released on correct copied context");
    }
    {
        FakeOwner owner; LegacyHostAdapters adapter(owner.host(), limits(), retention);
        require(adapter.set_prospective_document(prospective) == 0, "prospective");
        bib::provider_candidate::LegacyHostAdaptersTestAccess::exhaust_after_next_identity(adapter);
        const auto last = begin_epoch(adapter); const auto response = get(last);
        require(last.document_epoch == std::numeric_limits<std::uint64_t>::max() &&
            response.lease == std::numeric_limits<std::uint64_t>::max(), "last nonzero counter identities issued once");
        last.release(last.context, response.lease);
        auto input = request(last); BibAppResourceResponseV1 output{};
        require(last.resolve(last.context, &input, &output) == BIB_ENGINE_LIMIT && owner.epochs[1].resolves == 1,
            "exhausted lease counter refuses without producer work");
        retire(adapter, last.document_epoch);
        const auto bundle = adapter.resource_bundle_hooks(); BibAppResourceHostV1 next{}; next.size = 99;
        require(bundle.begin_epoch(bundle.context, &next) == BIB_ENGINE_LIMIT && !next.size && owner.resource_begin_calls == 1,
            "exhausted epoch counter refuses without host work or reuse");
    }
}
void resource_callback_exception_containment() {
    FakeOwner owner; LegacyHostAdapters adapter(owner.host(), limits(), retention);
    require(adapter.set_prospective_document(prospective) == 0, "prospective");
    const auto epoch = begin_epoch(adapter); const auto response = get(epoch);
    owner.throw_retire = true; retire(adapter, epoch.document_epoch); retire(adapter, epoch.document_epoch);
    owner.throw_release = true; epoch.release(epoch.context, response.lease); epoch.release(epoch.context, response.lease);
    require(owner.epochs[1].retired == 1 && owner.epochs[1].releases == 1 && adapter.callback_faulted() &&
        !adapter.active_resource_contexts(), "throwing release/retire contained with no repeated effect");
}
void prohibited_resource_callback_reentry() {
    FakeOwner owner; LegacyHostAdapters adapter(owner.host(), limits(), retention);
    require(adapter.set_prospective_document(prospective) == 0, "prospective");
    const auto epoch = begin_epoch(adapter); const auto first = get(epoch);
    owner.reentrant_bundle = adapter.resource_bundle_hooks(); owner.reentrant_epoch = epoch;
    owner.reentrant_lease = first.lease; owner.reenter_resolve = true;
    const auto second = get(epoch);
    require(owner.nested_resolve_status == BIB_ENGINE_REENTRANT && owner.nested_begin_status == BIB_ENGINE_REENTRANT &&
        owner.epochs[1].retired == 0 && owner.epochs[1].releases == 0 && adapter.outstanding_resource_leases() == 2,
        "resolve callback cannot reenter, retire or release an existing lease");
    owner.reenter_resolve = false; owner.reenter_release = true;
    epoch.release(epoch.context, first.lease); epoch.release(epoch.context, second.lease);
    require(owner.epochs[1].retired == 0 && owner.epochs[1].releases == 2 && adapter.active_resource_contexts() == 1,
        "release callback cannot retire before its outer release returns");
    owner.reenter_release = false; retire(adapter, 1); retire(adapter, 1);
    require(owner.epochs[1].retired == 1 && !adapter.active_resource_contexts(), "valid later retirement forwards once");
}
void valid_head_and_request_rejections() {
    FakeOwner owner; LegacyHostAdapters adapter(owner.host(), limits(), retention);
    require(adapter.set_prospective_document(prospective) == 0, "prospective");
    const auto epoch = begin_epoch(adapter); auto head = request(epoch, "HEAD"); BibAppResourceResponseV1 response{};
    require(epoch.resolve(epoch.context, &head, &response) == 0 && !response.body_length && response.content_length == 4 && response.lease, "HEAD preserves content length without body");
    epoch.release(epoch.context, response.lease);
    auto bad = request(epoch); bad.version = 2;
    require(epoch.resolve(epoch.context, &bad, &response) == BIB_ENGINE_INVALID, "bad version rejected");
    bad = request(epoch); bad.method = nullptr;
    require(epoch.resolve(epoch.context, &bad, &response) == BIB_ENGINE_INVALID, "null nonempty request rejected");
    bad = request(epoch, "POST");
    require(epoch.resolve(epoch.context, &bad, &response) == BIB_ENGINE_INVALID && owner.epochs[1].resolves == 1, "unsupported method rejected before producer");
    owner.mode = FakeOwner::ResponseMode::http_not_found; auto missing = request(epoch);
    require(epoch.resolve(epoch.context, &missing, &response) == 0 && response.status == 404 &&
        !response.lease && !response.body_length, "HTTP error remains successful transport with static unleased MIME");
    epoch.release(epoch.context, 0); require(owner.epochs[1].releases == 1, "zero lease never released to producer");
    retire(adapter, 1);
}
void service_enter_status_domain() {
    FakeOwner owner; LegacyHostAdapters adapter(owner.host(), limits(), retention);
    auto hooks=adapter.service_hooks();
    require(hooks.enter_engine(hooks.context)==0,"real legacy ServiceStatus OK admits");
    owner.enter_status=2;require(hooks.enter_engine(hooks.context)==2,"unavailable remains nonzero rejection");
    owner.enter_status=14;require(hooks.enter_engine(hooks.context)==14,"uncertain remains nonzero rejection");
    owner.enter_status=99;require(hooks.enter_engine(hooks.context)==14,"invalid status becomes uncertain, never OK");
    require(hooks.enter_engine(nullptr)==2,"invalid callback context rejects with nonzero status");
}
void resource_transport_and_prefix_validation() {
    FakeOwner owner; LegacyHostAdapters adapter(owner.host(), limits(), retention);
    require(adapter.set_prospective_document(prospective) == 0, "prospective");
    auto bundle = adapter.resource_bundle_hooks(); BibAppResourceHostV1 failed{};
    owner.resource_begin_status = 14;
    require(bundle.begin_epoch(bundle.context, &failed) == BIB_ENGINE_INVALID && owner.epochs[1].retired == 1, "positive transport status rejected and epoch retired");
    owner.resource_begin_status = -99;
    require(bundle.begin_epoch(bundle.context, &failed) == BIB_ENGINE_INVALID && owner.epochs[2].retired == 1, "unknown transport status normalized");
    owner.resource_begin_status = 0; auto epoch = begin_epoch(adapter);
    auto incoming = request(epoch); incoming.size = sizeof(std::uint32_t); incoming.document_epoch = 999;
    BibAppResourceResponseV1 response{};
    require(epoch.resolve(epoch.context, &incoming, &response) == BIB_ENGINE_INVALID && owner.epochs[3].resolves == 0, "prefix rejected before reading later authority or producer invocation");
    incoming = request(epoch); owner.resource_resolve_status = 14;
    require(epoch.resolve(epoch.context, &incoming, &response) == BIB_ENGINE_INVALID && owner.epochs[3].releases == 1, "positive response transport preserves release obligation");
    owner.resource_resolve_status = -99;
    require(epoch.resolve(epoch.context, &incoming, &response) == BIB_ENGINE_INVALID && owner.epochs[3].releases == 2, "unknown response transport preserves release obligation");
    retire(adapter, epoch.document_epoch);
}
void invalid_limits_have_no_support() {
    FakeOwner owner;
    for (int mode = 0; mode != 5; ++mode) {
        auto bound = limits();
        if (mode == 0) bound.maximum_inflight_resources = 4097;
        if (mode == 1) bound.maximum_resource_response_bytes = 64ULL * 1024 * 1024 + 1;
        if (mode == 2) bound.maximum_retained_resource_bytes = 256ULL * 1024 * 1024 + 1;
        if (mode == 3) bound.maximum_retained_resource_bytes = 7;
        if (mode == 4) bound.reserved = 1;
        LegacyHostAdapters adapter(owner.host(), bound, retention);
        require(!adapter.supports_resources(), "invalid resource bounds do not gain support");
    }
    auto bound = limits(); bound.maximum_service_message_bytes = 383;
    LegacyHostAdapters adapter(owner.host(), bound, retention);
    require(!adapter.supports_services(), "invalid service bounds do not gain support");
    LegacyHostAdapters no_retention(owner.host(), limits(), {});
    require(!no_retention.supports_services(), "retention bounds must be provided explicitly");
}
}
int main() {
    const std::array<std::pair<const char*, void(*)()>, 17> cases{{
        {"copied tables and prospective identity", copied_tables_and_prospective},
        {"service spans and staged ACK receipts", service_spans_and_staged_ack},
        {"service callback exception containment", service_exception_containment},
        {"optional callbacks and owner thread", optional_callbacks_and_thread},
        {"resource transform and raw lease lifetime", resource_transform_and_lease_lifetime},
        {"two resource contexts and lease collision protection", two_contexts_and_collision_protection},
        {"malformed and rejected response leases", malformed_and_rejected_leases},
        {"session inflight limit", resource_shared_inflight_limit},
        {"session raw byte limit", resource_shared_raw_byte_limit},
        {"invalid epoch admission cleanup", invalid_admission_cleanup},
        {"translated resource epochs and counter exhaustion", translated_resource_epochs_and_exhaustion},
        {"resource callback exception containment", resource_callback_exception_containment},
        {"prohibited resource callback reentry", prohibited_resource_callback_reentry},
        {"HEAD and invalid request handling", valid_head_and_request_rejections},
        {"resource status domain and request prefix", resource_transport_and_prefix_validation},
        {"service enter status domain", service_enter_status_domain},
        {"invalid resource and service limits", invalid_limits_have_no_support}
    }};
    std::size_t passed{};
    for (const auto& [name, run] : cases) {
        try { run(); ++passed; }
        catch (const std::exception& error) { std::cerr << "FAIL " << name << ": " << error.what() << '\n'; return 1; }
    }
    std::cout << "PASS " << passed << " standalone legacy-adapter fake-owner cases\n";
}
