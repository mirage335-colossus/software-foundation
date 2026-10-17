// SPDX-License-Identifier: CC0-1.0
#include "LegacyHostAdapters.hpp"
#include <algorithm>
#include <limits>
#include <string_view>

namespace bib::provider_candidate {
namespace {
constexpr std::uint32_t service_invalid = 1;
constexpr std::uint32_t service_unavailable = 2;
constexpr std::uint32_t service_conflict = 6;
constexpr std::uint32_t service_limit = 8;
constexpr std::uint32_t service_uncertain = 14;
constexpr std::uint64_t maximum_response = 64ULL * 1024 * 1024;
constexpr std::uint64_t maximum_retained = 256ULL * 1024 * 1024;
std::int32_t transport_status(std::int32_t status) noexcept {
    return status <= 0 && status >= BIB_ENGINE_PROCESS_EXIT_REQUIRED ? status : BIB_ENGINE_INVALID;
}
bool valid_resource_limits(const BibEngineLimitsV1& limits) noexcept {
    return limits.maximum_inflight_resources && limits.maximum_inflight_resources <= 4096 &&
        limits.maximum_resource_response_bytes && limits.maximum_resource_response_bytes <= maximum_response &&
        limits.maximum_retained_resource_bytes >= limits.maximum_resource_response_bytes &&
        limits.maximum_retained_resource_bytes <= maximum_retained;
}
bool valid_mime(const BibEngineBytesV1& mime) noexcept {
    if (mime.reserved || !mime.data || !mime.length || mime.length > 127) return false;
    const std::string_view value(reinterpret_cast<const char*>(mime.data), mime.length);
    const auto slash = value.find('/');
    return slash != std::string_view::npos && slash && slash + 1 < value.size() &&
        value.find('/', slash + 1) == std::string_view::npos &&
        std::all_of(value.begin(), value.end(), [](char c) {
            return (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') ||
                c == '.' || c == '+' || c == '-' || c == '/';
        });
}
bool valid_prospective(const BibEngineDocumentV1& document) noexcept {
    return document.application_instance && document.document_sequence && !document.service_generation;
}
}

LegacyHostAdapters::LegacyHostAdapters(const BibEngineHostV1& host, const BibEngineLimitsV1& limits,
    ServiceRetentionLimits retention)
    : host_(host), limits_(limits), retention_(retention),
      valid_(host.size >= sizeof(host) && host.abi_major == BIB_ENGINE_ABI_MAJOR &&
          host.abi_minor == BIB_ENGINE_ABI_MINOR && !host.reserved &&
          limits.size >= sizeof(limits) && !limits.reserved),
      leases_(valid_ && valid_resource_limits(limits) ? limits.maximum_inflight_resources : 0) {
    for (auto& epoch : epochs_) epoch.owner = this;
}

bool LegacyHostAdapters::supports_services() const noexcept {
    return valid_ && limits_.maximum_service_message_bytes >= 384 &&
        limits_.maximum_service_message_bytes <= BIB_FOUNDATION_SERVICE_MAX_MESSAGE &&
        limits_.maximum_retired_documents && limits_.maximum_retired_documents <= 64 &&
        retention_.max_retained_calls && retention_.max_retained_bytes >= 64 &&
        host_.enter_engine && host_.leave_engine && host_.begin_service_document &&
        host_.close_service_document && host_.submit_service && host_.cancel_service &&
        host_.stage_service_ack && host_.wake;
}
bool LegacyHostAdapters::supports_resources() const noexcept {
    return valid_ && valid_resource_limits(limits_) && host_.begin_resource_epoch && host_.retire_resource_epoch;
}
bool LegacyHostAdapters::owner_thread() const noexcept { return thread_ == std::this_thread::get_id(); }
bool LegacyHostAdapters::prospective_ready() const noexcept { return valid_prospective(prospective_); }
std::int32_t LegacyHostAdapters::set_prospective_document(const BibEngineDocumentV1& document) noexcept {
    if (!owner_thread()) return BIB_ENGINE_WRONG_THREAD;
    if (callback_depth_) return BIB_ENGINE_REENTRANT;
    if (!valid_ || !valid_prospective(document)) return BIB_ENGINE_INVALID;
    prospective_ = document;
    return BIB_ENGINE_OK;
}
BibFoundationServiceHostV1 LegacyHostAdapters::service_hooks() noexcept {
    return {sizeof(BibFoundationServiceHostV1), BIB_FOUNDATION_SERVICE_HOST_VERSION,
        limits_.maximum_service_message_bytes, retention_.max_retained_calls, retention_.max_retained_bytes,
        limits_.maximum_retired_documents, this, enter_engine, leave_engine, begin_document, close_document,
        submit, cancel, acknowledge, schedule_owner};
}
BibAppResourceBundleHostV1 LegacyHostAdapters::resource_bundle_hooks() noexcept {
    return {sizeof(BibAppResourceBundleHostV1), BIB_APP_RESOURCE_BUNDLE_HOST_VERSION,
        limits_.maximum_resource_response_bytes, limits_.maximum_inflight_resources, 0,
        limits_.maximum_retained_resource_bytes, this, begin_epoch, retire_epoch};
}
std::size_t LegacyHostAdapters::active_resource_contexts() const noexcept {
    if (!owner_thread()) return 0;
    return static_cast<std::size_t>(std::count_if(epochs_.begin(), epochs_.end(),
        [](const auto& epoch) { return epoch.occupied; }));
}
std::size_t LegacyHostAdapters::outstanding_resource_leases() const noexcept {
    if (!owner_thread()) return 0;
    return static_cast<std::size_t>(std::count_if(leases_.begin(), leases_.end(),
        [](const auto& lease) { return lease.token != 0; }));
}
std::uint64_t LegacyHostAdapters::retained_raw_resource_bytes() const noexcept {
    return owner_thread() ? raw_bytes_ : 0;
}
std::uint32_t LegacyHostAdapters::checked_service_status(std::uint32_t status) noexcept {
    return status <= service_uncertain ? status : service_uncertain;
}

std::uint32_t LegacyHostAdapters::enter_engine(void* context) noexcept {
    if (!context) return service_unavailable;
    auto& self = *static_cast<LegacyHostAdapters*>(context);
    if (!self.owner_thread() || !self.valid_ || !self.host_.enter_engine || self.callback_depth_) return service_unavailable;
    CallbackScope scope(self);
    try { return checked_service_status(self.host_.enter_engine(self.host_.context)); }
    catch (...) { self.fault(); return service_uncertain; }
}
void LegacyHostAdapters::leave_engine(void* context) noexcept {
    if (!context) return;
    auto& self = *static_cast<LegacyHostAdapters*>(context);
    if (!self.owner_thread() || !self.valid_ || !self.host_.leave_engine || self.callback_depth_) return;
    CallbackScope scope(self);
    try { self.host_.leave_engine(self.host_.context); } catch (...) { self.fault(); }
}
std::uint64_t LegacyHostAdapters::begin_document(void* context) noexcept {
    if (!context) return 0;
    auto& self = *static_cast<LegacyHostAdapters*>(context);
    if (!self.owner_thread() || !self.supports_services() || !self.prospective_ready() || self.callback_depth_) return 0;
    const auto prospective = self.prospective_;
    CallbackScope scope(self);
    try { return self.host_.begin_service_document(self.host_.context, &prospective); }
    catch (...) { self.fault(); return 0; }
}
void LegacyHostAdapters::close_document(void* context, std::uint64_t generation) noexcept {
    if (!context || !generation) return;
    auto& self = *static_cast<LegacyHostAdapters*>(context);
    if (!self.owner_thread() || !self.valid_ || !self.host_.close_service_document || self.callback_depth_) return;
    CallbackScope scope(self);
    try { self.host_.close_service_document(self.host_.context, generation); } catch (...) { self.fault(); }
}
std::uint32_t LegacyHostAdapters::submit(void* context, std::uint64_t generation,
    const std::uint8_t* bytes, std::uint32_t length, std::uint32_t source) noexcept {
    if (!context) return service_unavailable;
    auto& self = *static_cast<LegacyHostAdapters*>(context);
    if (!self.owner_thread() || self.callback_depth_) return service_conflict;
    if (!self.supports_services()) return service_unavailable;
    if (!generation || (!bytes && length) || source > 2) return service_invalid;
    if (length > self.limits_.maximum_service_message_bytes) return service_limit;
    const BibEngineBytesV1 span{bytes, length, 0};
    CallbackScope scope(self);
    try { return checked_service_status(self.host_.submit_service(self.host_.context, generation, &span, source)); }
    catch (...) { self.fault(); return service_uncertain; }
}
std::uint32_t LegacyHostAdapters::cancel(void* context, std::uint64_t generation, std::uint64_t sequence) noexcept {
    if (!context) return service_unavailable;
    auto& self = *static_cast<LegacyHostAdapters*>(context);
    if (!self.owner_thread() || self.callback_depth_) return service_conflict;
    if (!self.supports_services()) return service_unavailable;
    if (!generation || !sequence) return service_invalid;
    CallbackScope scope(self);
    try { return checked_service_status(self.host_.cancel_service(self.host_.context, generation, sequence)); }
    catch (...) { self.fault(); return service_uncertain; }
}
std::uint32_t LegacyHostAdapters::acknowledge(void* context, std::uint64_t generation, std::uint64_t through) noexcept {
    if (!context) return service_unavailable;
    auto& self = *static_cast<LegacyHostAdapters*>(context);
    if (!self.owner_thread() || self.callback_depth_) return service_conflict;
    if (!self.supports_services()) return service_unavailable;
    if (!generation || !through) return service_invalid;
    CallbackScope scope(self);
    // This must return the staged operation's actual status. The first call can
    // return UNAVAILABLE; a later call returns the owner's cached ACK receipt.
    try { return checked_service_status(self.host_.stage_service_ack(self.host_.context, generation, through)); }
    catch (...) { self.fault(); return service_uncertain; }
}
void LegacyHostAdapters::schedule_owner(void* context) noexcept {
    if (!context) return;
    auto& self = *static_cast<LegacyHostAdapters*>(context);
    if (!self.valid_ || !self.host_.wake) return;
    // wake may originate on a worker: touch no owner-thread bookkeeping here.
    try { self.host_.wake(self.host_.context); } catch (...) { self.fault(); }
}

void LegacyHostAdapters::retire_producer(std::uint64_t epoch) noexcept {
    CallbackScope scope(*this);
    try { host_.retire_resource_epoch(host_.context, epoch); } catch (...) { fault(); }
}
void LegacyHostAdapters::release_producer(EpochContext& epoch, std::uint64_t lease) noexcept {
    if (!lease) return;
    CallbackScope scope(*this);
    try { epoch.producer.release(epoch.producer.context, lease); } catch (...) { fault(); }
}
void LegacyHostAdapters::clear_retired(EpochContext& epoch) noexcept {
    if (epoch.retired && !epoch.outstanding && !epoch.resolving) {
        epoch = {};
        epoch.owner = this;
    }
}
std::int32_t LegacyHostAdapters::begin_epoch(void* context, BibAppResourceHostV1* out) noexcept {
    if (!out) return BIB_ENGINE_INVALID;
    *out = {};
    if (!context) return BIB_ENGINE_INVALID;
    auto& self = *static_cast<LegacyHostAdapters*>(context);
    if (!self.owner_thread()) return BIB_ENGINE_WRONG_THREAD;
    if (self.callback_depth_ || self.beginning_epoch_) return BIB_ENGINE_REENTRANT;
    if (!self.supports_resources()) return BIB_ENGINE_UNSUPPORTED;
    if (!self.prospective_ready()) return BIB_ENGINE_INVALID;
    if (!self.next_epoch_) return BIB_ENGINE_LIMIT;
    auto slot = std::find_if(self.epochs_.begin(), self.epochs_.end(), [](const auto& epoch) { return !epoch.occupied; });
    if (slot == self.epochs_.end()) return BIB_ENGINE_LIMIT;
    BibEngineResourceEpochV1 producer{};
    const auto prospective = self.prospective_;
    std::int32_t status = BIB_ENGINE_INVALID;
    self.beginning_epoch_ = true;
    {
        CallbackScope scope(self);
        try { status = transport_status(self.host_.begin_resource_epoch(self.host_.context, &prospective, &producer)); }
        catch (...) { self.fault(); }
    }
    self.beginning_epoch_ = false;
    // The producer promises fresh private epochs, without numeric ordering.
    // Refuse a duplicate live producer value without closing existing scope.
    // Legacy identities are issued separately, so its tables never reuse an
    // epoch even when fresh producer values arrive in decreasing order.
    const bool distinct = producer.resource_epoch && std::none_of(self.epochs_.begin(), self.epochs_.end(),
        [&](const auto& epoch) { return epoch.occupied && epoch.producer.resource_epoch == producer.resource_epoch; });
    if (status != BIB_ENGINE_OK || producer.size != sizeof(producer) || producer.reserved ||
        !distinct || !producer.resolve || !producer.release) {
        if (distinct) self.retire_producer(producer.resource_epoch);
        return status == BIB_ENGINE_OK ? BIB_ENGINE_INVALID : status;
    }
    slot->producer = producer;
    slot->legacy_epoch = self.next_epoch_;
    self.next_epoch_ = self.next_epoch_ == std::numeric_limits<std::uint64_t>::max() ? 0 : self.next_epoch_ + 1;
    slot->occupied = true;
    *out = {sizeof(*out), BIB_APP_RESOURCE_HOST_VERSION, slot->legacy_epoch,
        self.limits_.maximum_resource_response_bytes, self.limits_.maximum_inflight_resources, 0,
        self.limits_.maximum_retained_resource_bytes, &*slot, resolve, release};
    return BIB_ENGINE_OK;
}
void LegacyHostAdapters::retire_epoch(void* context, std::uint64_t value) noexcept {
    if (!context || !value) return;
    auto& self = *static_cast<LegacyHostAdapters*>(context);
    if (!self.owner_thread() || self.callback_depth_ || !self.supports_resources()) return;
    for (auto& epoch : self.epochs_) {
        if (!epoch.occupied || epoch.legacy_epoch != value || epoch.retired || epoch.resolving) continue;
        // Forward closure once now; the producer contract retains raw spans and
        // its own context through release, while this wrapper also stays alive.
        epoch.retired = true;
        self.retire_producer(epoch.producer.resource_epoch);
        self.clear_retired(epoch);
        return;
    }
}
std::int32_t LegacyHostAdapters::resolve(void* context, const BibAppResourceRequestV1* request,
    BibAppResourceResponseV1* out) noexcept {
    if (!out) return BIB_ENGINE_INVALID;
    *out = {};
    if (!context || !request) return BIB_ENGINE_INVALID;
    auto& epoch = *static_cast<EpochContext*>(context);
    auto& self = *epoch.owner;
    if (!self.owner_thread()) return BIB_ENGINE_WRONG_THREAD;
    if (self.callback_depth_ || epoch.resolving) return BIB_ENGINE_REENTRANT;
    if (request->size != sizeof(*request) || request->version != BIB_APP_RESOURCE_HOST_VERSION ||
        request->method_length > 16 || request->resolved_url_length > 4096 ||
        (!request->method && request->method_length) || (!request->resolved_url && request->resolved_url_length)) return BIB_ENGINE_INVALID;
    if (!epoch.occupied || epoch.retired || request->document_epoch != epoch.legacy_epoch) return BIB_ENGINE_STALE;
    const std::string_view method(request->method ? reinterpret_cast<const char*>(request->method) : "", request->method_length);
    if (method != "GET" && method != "HEAD") return BIB_ENGINE_INVALID;
    auto lease_slot = std::find_if(self.leases_.begin(), self.leases_.end(), [](const auto& lease) { return !lease.token; });
    if (lease_slot == self.leases_.end() || !self.next_lease_) return BIB_ENGINE_LIMIT;
    const BibEngineResourceRequestV1 translated{sizeof(translated), 0, epoch.producer.resource_epoch,
        {request->method, request->method_length, 0}, {request->resolved_url, request->resolved_url_length, 0}};
    BibEngineResourceResponseV1 response{};
    std::int32_t status = BIB_ENGINE_INVALID;
    epoch.resolving = true;
    {
        CallbackScope scope(self);
        try { status = transport_status(epoch.producer.resolve(epoch.producer.context, &translated, &response)); }
        catch (...) { self.fault(); }
    }
    const bool valid_response = status == BIB_ENGINE_OK && response.size == sizeof(response) &&
        response.status >= 200 && response.status <= 599 && response.status / 100 != 3 &&
        response.body_length <= self.limits_.maximum_resource_response_bytes &&
        response.content_length <= self.limits_.maximum_resource_response_bytes &&
        (!response.body_length || response.body) && valid_mime(response.mime) &&
        (method != "HEAD" || !response.body_length) &&
        (method != "GET" || response.body_length == response.content_length);
    const bool fits = response.body_length <= self.limits_.maximum_retained_resource_bytes - self.raw_bytes_;
    if (!valid_response || !fits) {
        // Even a callback that sets a lease and then throws/rejects transfers a
        // release obligation. Keep the context pinned through that release.
        self.release_producer(epoch, response.lease);
        epoch.resolving = false;
        return status != BIB_ENGINE_OK ? status : (!fits ? BIB_ENGINE_LIMIT : BIB_ENGINE_INVALID);
    }
    std::uint64_t token{};
    if (response.lease) {
        token = self.next_lease_;
        self.next_lease_ = token == std::numeric_limits<std::uint64_t>::max() ? 0 : token + 1;
        *lease_slot = {token, response.lease, response.body_length, &epoch};
        ++epoch.outstanding;
        self.raw_bytes_ += response.body_length;
    }
    *out = {sizeof(*out), BIB_APP_RESOURCE_HOST_VERSION, response.status, response.mime.length,
        response.mime.data, response.body, response.body_length, response.content_length, token};
    epoch.resolving = false;
    return BIB_ENGINE_OK;
}
void LegacyHostAdapters::release(void* context, std::uint64_t token) noexcept {
    if (!context || !token) return;
    auto& epoch = *static_cast<EpochContext*>(context);
    auto& self = *epoch.owner;
    if (!self.owner_thread() || self.callback_depth_) return;
    auto found = std::find_if(self.leases_.begin(), self.leases_.end(), [&](const auto& lease) {
        return lease.token == token && lease.epoch == &epoch;
    });
    if (found == self.leases_.end()) return;
    const auto held = *found;
    // Consume before invoking producer code: throws/reentrancy cannot release
    // the same producer lease twice. Context reuse follows callback completion.
    *found = {};
    self.raw_bytes_ -= held.body_bytes;
    self.release_producer(epoch, held.producer_lease);
    --epoch.outstanding;
    self.clear_retired(epoch);
}
}
