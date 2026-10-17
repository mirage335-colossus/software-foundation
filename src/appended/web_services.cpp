#include <foundation/appended/web_services.hpp>

#include <algorithm>
#include <array>
#include <limits>
#include <map>
#include <stdexcept>
#include <thread>
#include <utility>

namespace foundation::appended {
namespace {
using Span = std::span<const std::uint8_t>;
constexpr std::size_t header_bytes = FOUNDATION_APPENDED_ENVELOPE_BYTES;
constexpr std::size_t discovery_bytes = 320;

void put(std::span<std::uint8_t> bytes, std::uint64_t value) noexcept {
    for (std::size_t n = 0; n < bytes.size(); ++n) bytes[n] = static_cast<std::uint8_t>(value >> (8 * n));
}
std::uint32_t length(Span bytes) noexcept {
    return std::uint32_t(bytes[0]) | (std::uint32_t(bytes[1]) << 8) |
        (std::uint32_t(bytes[2]) << 16) | (std::uint32_t(bytes[3]) << 24);
}
struct OwnedField { std::uint16_t id; FieldType type; Bytes value; };
Bytes record(std::initializer_list<OwnedField> fields) {
    std::array<FieldView, 6> views{};
    std::size_t count = 0;
    for (const auto& field : fields) views[count++] = {field.id, field.type, true, field.value};
    Bytes output;
    if (encode_record(std::span(views).first(count), output) != CodecStatus::ok)
        throw std::logic_error("invalid web service record");
    return output;
}
bool parse_discovery(Span bytes, DiscoveryQuery& query) {
    std::vector<FieldView> fields;
    if (decode_record(bytes, fields) != CodecStatus::ok) return false;
    std::array<const FieldView*, 5> known{};
    for (const auto& field : fields) {
        if (field.id > known.size()) { if (field.must_understand) return false; }
        else { if (!field.must_understand) return false; known[field.id - 1] = &field; }
    }
    std::uint32_t major = 0, low = 0, high = 0;
    if (!known[0] || known[0]->type != FieldType::utf8 || !known[1] || !known[2] || !known[3] ||
        !read_u32(*known[1], major) || !read_u32(*known[2], low) || !read_u32(*known[3], high) ||
        major == 0 || major > 65535 || low > high || high > 65535) return false;
    query = {std::string_view(reinterpret_cast<const char*>(known[0]->value.data()), known[0]->value.size()),
        static_cast<std::uint16_t>(major), static_cast<std::uint16_t>(low), static_cast<std::uint16_t>(high), {}};
    if (known[4]) {
        if (known[4]->type != FieldType::bytes || known[4]->value.size() != 32) return false;
        SchemaId schema{}; std::copy(known[4]->value.begin(), known[4]->value.end(), schema.begin()); query.schema = schema;
    }
    return true;
}
Limits native_limits(const WebServiceLimits& bounds) {
    Limits limits;
    limits.max_message_bytes = bounds.max_message_bytes;
    limits.max_services = bounds.max_service_handles;
    limits.max_retained_requests = 2;
    limits.max_retained_results = 1;
    limits.max_retained_bytes = bounds.max_message_bytes;
    return limits;
}
bool valid_source(WebServiceSource source) noexcept {
    return source == WebServiceSource::automatic || source == WebServiceSource::native || source == WebServiceSource::module;
}
ServiceStatus missing(ServiceStatus native, ServiceStatus module) noexcept {
    if (native == ServiceStatus::closed && module == ServiceStatus::closed) return ServiceStatus::closed;
    if (native == ServiceStatus::invalid_request || module == ServiceStatus::invalid_request) return ServiceStatus::invalid_request;
    if (native == ServiceStatus::schema_mismatch || module == ServiceStatus::schema_mismatch) return ServiceStatus::schema_mismatch;
    if (native == ServiceStatus::unsupported_version || module == ServiceStatus::unsupported_version) return ServiceStatus::unsupported_version;
    if (native == ServiceStatus::unavailable || module == ServiceStatus::unavailable) return ServiceStatus::unavailable;
    return ServiceStatus::not_found;
}
} // namespace

ServiceStatus install_native_services(Registry& registry, std::span<const NativeServiceRegistration> services) {
    for (const auto& service : services) {
        const auto registered = registry.register_service(service.descriptor, service.handler);
        if (registered.status != ServiceStatus::ok) return registered.status;
    }
    return ServiceStatus::ok;
}

struct WebServices::Impl {
    enum class Phase { queued, running, ready };
    struct Route {
        WebServiceSource source;
        std::uint64_t underlying;
        ServiceDescriptor descriptor;
        std::uint32_t max_request;
    };
    struct Call {
        Bytes request, reply;
        Envelope envelope;
        WebServiceSource source;
        std::size_t reservation, max_reply;
        Phase phase{Phase::queued};
        bool delivered{false};
    };
    // The high-bit web domain also makes accidental raw native/provider handle
    // use fail at admission; only handles returned by this realm are routable.
    std::uint64_t generation, highest{0}, retired{0}, next_handle{UINT64_C(0x8000000000000000)}, last_provider_sequence{0};
    WebServiceLimits limits;
    Registry native;
    WebModuleServices module;
    GenerationSource native_sequence, private_provider_sequence;
    std::thread::id owner{std::this_thread::get_id()};
    bool is_closed{false}, pumping{false}, handles_exhausted{false};
    std::size_t callbacks{0}, retained_bytes{0};
    std::map<std::uint64_t, Route> routes;
    std::map<std::uint64_t, Call> calls;

    Impl(std::uint64_t epoch, WebServiceLimits bounds, WebModuleServices binding)
        : generation(epoch), limits(bounds), native(epoch, native_limits(bounds)), module(std::move(binding)) {}
    void check_owner() const {
        if (owner != std::this_thread::get_id()) throw std::logic_error("web services require their serialized owner");
    }
    bool blocked() const noexcept { return callbacks != 0 || pumping; }
    void finish(Call& call, ServiceStatus status, Span payload = {}) noexcept {
        if (static_cast<std::uint32_t>(status) > FOUNDATION_APPENDED_SERVICE_UNCERTAIN ||
            status == ServiceStatus::result_available) status = ServiceStatus::internal_error;
        if (status != ServiceStatus::ok) payload = {};
        if (payload.size() > call.max_reply) { status = ServiceStatus::internal_error; payload = {}; }
        // Header was encoded and all storage reserved at admission. Updating its
        // scalar length/status fields cannot allocate after a service effect.
        auto output = std::span<std::uint8_t>(call.reply);
        std::copy(payload.begin(), payload.end(), output.begin() + header_bytes);
        put(output.subspan(FOUNDATION_APPENDED_OFFSET_TOTAL, 4), header_bytes + payload.size());
        put(output.subspan(FOUNDATION_APPENDED_OFFSET_PAYLOAD, 4), payload.size());
        put(output.subspan(FOUNDATION_APPENDED_OFFSET_STATUS, 4), static_cast<std::uint32_t>(status));
        call.reply.resize(header_bytes + payload.size());
        call.phase = Phase::ready; call.delivered = false;
    }
    void settle_closed() noexcept {
        for (auto& [sequence, call] : calls) {
            (void)sequence;
            if (call.phase == Phase::queued) finish(call, ServiceStatus::closed);
        }
        if (!pumping) native.close();
    }
    ServiceStatus discover(Call& call, Span payload) {
        DiscoveryQuery query;
        if (!parse_discovery(payload, query)) return ServiceStatus::invalid_request;
        const bool use_native = call.source != WebServiceSource::module;
        const bool use_module = call.source != WebServiceSource::native && bool(module.discover);
        const auto host = use_native ? native.discover(query) : DiscoveryResult{};
        const auto guest = use_module ? module.discover(query) : ProviderDiscovery{};
        if (host.status != ServiceStatus::ok && guest.status != ServiceStatus::ok)
            return missing(host.status, guest.status);
        WebServiceSource source;
        ServiceDescriptor descriptor;
        std::uint64_t underlying;
        std::uint32_t max_request;
        if (host.status == ServiceStatus::ok && guest.status == ServiceStatus::ok &&
            host.descriptor.minor == guest.descriptor.contract.minor) return ServiceStatus::conflict;
        if (guest.status != ServiceStatus::ok || (host.status == ServiceStatus::ok &&
            host.descriptor.minor > guest.descriptor.contract.minor)) {
            // Kernel bootstrap is a transport endpoint, not a page service.
            if (host.handle == 0) return ServiceStatus::not_found;
            source = WebServiceSource::native; descriptor = host.descriptor; underlying = host.handle;
            max_request = limits.max_message_bytes - header_bytes;
        } else {
            source = WebServiceSource::module; descriptor = guest.descriptor.contract; underlying = guest.handle;
            max_request = guest.descriptor.max_request_bytes;
        }
        if (!underlying || descriptor.max_reply_bytes > limits.max_message_bytes - header_bytes)
            return ServiceStatus::limit_exceeded;
        std::uint64_t handle = 0;
        for (const auto& [id, route] : routes)
            if (route.source == source && route.underlying == underlying) { handle = id; break; }
        if (!handle) {
            if (routes.size() >= limits.max_service_handles || handles_exhausted) return ServiceStatus::limit_exceeded;
            handle = next_handle;
        }
        const auto encoded = record({{1, FieldType::u64, encode_u64(handle)},
            {2, FieldType::utf8, Bytes(descriptor.name.begin(), descriptor.name.end())},
            {3, FieldType::u32, encode_u32(descriptor.major)}, {4, FieldType::u32, encode_u32(descriptor.minor)},
            {5, FieldType::bytes, Bytes(descriptor.schema.begin(), descriptor.schema.end())},
            {6, FieldType::u32, encode_u32(descriptor.max_reply_bytes)}});
        if (!routes.contains(handle)) {
            routes.emplace(handle, Route{source, underlying, std::move(descriptor), max_request});
            if (next_handle == std::numeric_limits<std::uint64_t>::max()) handles_exhausted = true;
            else ++next_handle;
        }
        finish(call, ServiceStatus::ok, encoded); return ServiceStatus::ok;
    }
    ServiceStatus invoke_native(Call& call, const Route& route, Span payload) {
        // Reserve the complete exchange and subsequent ACK before entering the
        // native handler. Backend ACK can retire only this private ledger.
        const auto sequence = native_sequence.next();
        const auto ack_sequence = native_sequence.next();
        if (!sequence || !ack_sequence) return ServiceStatus::limit_exceeded;
        Envelope request = call.envelope;
        request.generation = generation; request.sequence = *sequence; request.interface_handle = route.underlying;
        Bytes encoded;
        if (encode_envelope(request, payload, encoded) != CodecStatus::ok) return ServiceStatus::invalid_request;
        const auto capacity = header_bytes + route.descriptor.max_reply_bytes;
        const auto reply_offset = encoded.size();
        Bytes memory(reply_offset + capacity);
        std::copy(encoded.begin(), encoded.end(), memory.begin());
        const auto ack_payload = record({{1, FieldType::u64, encode_u64(*sequence)}});
        Envelope ack; ack.generation = generation; ack.sequence = *ack_sequence;
        ack.operation = FOUNDATION_APPENDED_CONTROL_ACKNOWLEDGE;
        Bytes ack_memory;
        if (encode_envelope(ack, ack_payload, ack_memory) != CodecStatus::ok) return ServiceStatus::internal_error;
        const auto ack_reply_offset = ack_memory.size(); ack_memory.resize(ack_reply_offset + header_bytes);
        const auto transport = native.call(memory, 0, static_cast<std::uint32_t>(encoded.size()),
            static_cast<std::uint32_t>(reply_offset), static_cast<std::uint32_t>(capacity));
        if (transport != TransportStatus::ok) {
            // Transport INTERNAL_ERROR may follow admission; do not execute a
            // fresh request in an attempt to reconstruct the external effect.
            finish(call, transport == TransportStatus::internal_error ? ServiceStatus::uncertain : ServiceStatus::internal_error);
            is_closed = true; return ServiceStatus::ok;
        }
        const auto output = Span(memory).subspan(reply_offset, capacity);
        const auto bytes = length(output);
        Envelope response; Span result;
        if (bytes > capacity || decode_envelope(output.first(bytes), response, result) != CodecStatus::ok ||
            response.kind != FOUNDATION_APPENDED_MESSAGE_REPLY || response.sequence != *sequence ||
            response.generation != generation || response.interface_handle != route.underlying ||
            response.operation != request.operation || response.service_status == FOUNDATION_APPENDED_SERVICE_RESULT_AVAILABLE) {
            finish(call, ServiceStatus::uncertain); is_closed = true; return ServiceStatus::ok;
        }
        finish(call, static_cast<ServiceStatus>(response.service_status), result);
        if (!native.closed()) {
            const auto status = native.call(ack_memory, 0, static_cast<std::uint32_t>(ack_reply_offset),
                static_cast<std::uint32_t>(ack_reply_offset), header_bytes);
            Envelope acknowledged; Span ignored;
            if (status != TransportStatus::ok ||
                decode_envelope(Span(ack_memory).subspan(ack_reply_offset), acknowledged, ignored) != CodecStatus::ok ||
                acknowledged.service_status != FOUNDATION_APPENDED_SERVICE_OK) is_closed = true;
        }
        return ServiceStatus::ok;
    }
    ServiceStatus invoke_module(Call& call, const Route& route, Span payload) {
        if (!module.invoke) return ServiceStatus::closed;
        const auto sequence = module.sequence ? module.sequence() : private_provider_sequence.next();
        if (!sequence || *sequence == 0 || *sequence <= last_provider_sequence) {
            is_closed = true; return ServiceStatus::limit_exceeded;
        }
        last_provider_sequence = *sequence;
        if (is_closed) return ServiceStatus::closed;
        ProviderRequest request{module.generation, *sequence, route.underlying, call.envelope.operation,
            Bytes(payload.begin(), payload.end())};
        // ModuleProviders reserves its own request/result/event storage before
        // dispatch; the web completion was already reserved by submit.
        auto outcome = module.invoke(request);
        finish(call, outcome.status, outcome.payload);
        const auto acknowledged = module.acknowledge(*sequence);
        // An unadmitted backend call has no outcome to retire. Shared owners
        // may defer prefix retirement after recording this copied-outcome notice.
        if (acknowledged != ServiceStatus::ok && acknowledged != ServiceStatus::closed &&
            acknowledged != ServiceStatus::invalid_request && acknowledged != ServiceStatus::unavailable) is_closed = true;
        return ServiceStatus::ok;
    }
};

WebServices::WebServices(std::uint64_t generation, std::span<const NativeServiceRegistration> native_services,
                         WebModuleServices module, WebServiceLimits limits) {
    if (!generation || limits.max_message_bytes < header_bytes + discovery_bytes ||
        limits.max_message_bytes > FOUNDATION_APPENDED_MAX_MESSAGE_BYTES || !limits.max_retained_calls ||
        !limits.max_retained_bytes || !limits.max_service_handles ||
        (bool(module.discover) != bool(module.invoke)) || (bool(module.invoke) != bool(module.acknowledge)) ||
        (module.invoke && !module.generation) || (!module.invoke && (module.generation || module.sequence)))
        throw std::invalid_argument("invalid web service epoch, binding or limits");
    impl_ = std::make_unique<Impl>(generation, limits, std::move(module));
    if (install_native_services(impl_->native, native_services) != ServiceStatus::ok)
        throw std::invalid_argument("invalid or conflicting web native service registration");
}
WebServices::~WebServices() = default;
WebServices::CallbackScope::CallbackScope(WebServices& owner) : owner_(owner) {
    owner_.impl_->check_owner();
    if (owner_.impl_->pumping) throw std::logic_error("engine reentry during web service pump");
    ++owner_.impl_->callbacks;
}
WebServices::CallbackScope::~CallbackScope() { --owner_.impl_->callbacks; }

ServiceStatus WebServices::submit(Span request, WebServiceSource source) {
    auto& state = *impl_; state.check_owner();
    if (!valid_source(source) || request.size() > state.limits.max_message_bytes) return ServiceStatus::invalid_request;
    Envelope envelope; Span payload;
    if (decode_envelope(request, envelope, payload) != CodecStatus::ok ||
        envelope.kind != FOUNDATION_APPENDED_MESSAGE_REQUEST) return ServiceStatus::invalid_request;
    if (envelope.generation != state.generation) return ServiceStatus::invalid_handle;
    if (const auto prior = state.calls.find(envelope.sequence); prior != state.calls.end()) {
        if (prior->second.source != source || !std::equal(request.begin(), request.end(),
            prior->second.request.begin(), prior->second.request.end())) return ServiceStatus::conflict;
        if (prior->second.phase == Impl::Phase::ready) prior->second.delivered = false;
        return ServiceStatus::ok;
    }
    if (envelope.sequence <= state.highest || envelope.sequence <= state.retired) return ServiceStatus::expired;
    if (state.is_closed) return ServiceStatus::closed;
    std::size_t max_reply = 0;
    if (!envelope.interface_handle) {
        if (envelope.operation != FOUNDATION_APPENDED_CONTROL_DISCOVER) return ServiceStatus::unknown_operation;
        max_reply = discovery_bytes;
    } else if (const auto route = state.routes.find(envelope.interface_handle); route != state.routes.end()) {
        if (source != WebServiceSource::automatic && source != route->second.source) return ServiceStatus::invalid_handle;
        if (payload.size() > route->second.max_request) return ServiceStatus::limit_exceeded;
        max_reply = route->second.descriptor.max_reply_bytes;
    } else return ServiceStatus::invalid_handle;
    const auto reservation = request.size() + header_bytes + max_reply;
    if (state.calls.size() >= state.limits.max_retained_calls ||
        reservation > state.limits.max_retained_bytes - state.retained_bytes) return ServiceStatus::limit_exceeded;
    Impl::Call call;
    call.request.assign(request.begin(), request.end()); call.envelope = envelope;
    call.source = source; call.reservation = reservation; call.max_reply = max_reply;
    auto reply = envelope; reply.kind = FOUNDATION_APPENDED_MESSAGE_COMPLETION;
    if (encode_envelope(reply, {}, call.reply) != CodecStatus::ok) return ServiceStatus::invalid_request;
    call.reply.resize(header_bytes + max_reply);
    state.calls.emplace(envelope.sequence, std::move(call));
    state.highest = envelope.sequence; state.retained_bytes += reservation;
    return ServiceStatus::ok;
}
ServiceStatus WebServices::cancel(std::uint64_t generation, std::uint64_t sequence) {
    auto& state = *impl_; state.check_owner();
    if (generation != state.generation) return ServiceStatus::invalid_handle;
    const auto found = state.calls.find(sequence);
    if (found == state.calls.end()) return sequence <= state.highest ? ServiceStatus::expired : ServiceStatus::not_found;
    if (found->second.phase != Impl::Phase::queued) return ServiceStatus::conflict;
    state.finish(found->second, ServiceStatus::closed); return ServiceStatus::ok;
}
ServiceStatus WebServices::pump(std::size_t maximum_calls) {
    auto& state = *impl_; state.check_owner();
    if (state.blocked()) return ServiceStatus::unavailable;
    if (state.is_closed) { state.settle_closed(); return ServiceStatus::closed; }
    state.pumping = true;
    struct Guard { Impl& state; ~Guard() { state.pumping = false; if (state.is_closed) state.settle_closed(); } } guard{state};
    std::size_t processed = 0;
    for (auto& [sequence, call] : state.calls) {
        (void)sequence;
        if (processed == maximum_calls || state.is_closed) break;
        if (call.phase != Impl::Phase::queued) continue;
        ++processed; call.phase = Impl::Phase::running;
        const auto payload = Span(call.request).subspan(header_bytes);
        try {
            ServiceStatus status;
            if (!call.envelope.interface_handle) status = state.discover(call, payload);
            else if (const auto route = state.routes.find(call.envelope.interface_handle); route == state.routes.end())
                status = ServiceStatus::invalid_handle;
            else status = route->second.source == WebServiceSource::native ?
                state.invoke_native(call, route->second, payload) : state.invoke_module(call, route->second, payload);
            if (call.phase == Impl::Phase::running) state.finish(call, status);
        } catch (...) {
            // The exact failure point may follow a native/guest effect. Retain a
            // terminal outcome rather than admitting an automatic retry. A
            // failed retirement notice must preserve an already copied result.
            if (call.phase != Impl::Phase::ready) state.finish(call, ServiceStatus::uncertain);
            state.is_closed = true;
        }
    }
    return ServiceStatus::ok;
}
std::optional<Bytes> WebServices::take_completion() {
    auto& state = *impl_; state.check_owner();
    if (state.blocked()) return {};
    for (auto& [sequence, call] : state.calls) {
        (void)sequence;
        if (call.phase != Impl::Phase::ready || call.delivered) continue;
        Bytes returned = call.reply; call.delivered = true; return returned;
    }
    return {};
}
ServiceStatus WebServices::copy_closed_completion(std::span<std::uint8_t> output,
    std::uint64_t& sequence, std::uint32_t& written) const noexcept {
    const auto& state = *impl_;
    if (state.owner != std::this_thread::get_id() || state.blocked()) return ServiceStatus::unavailable;
    if (!state.is_closed) return ServiceStatus::conflict;
    if (state.calls.empty()) return ServiceStatus::not_found;
    const auto& [id, call] = *state.calls.begin();
    if (call.phase != Impl::Phase::ready) return ServiceStatus::unavailable;
    if (output.size() < call.reply.size()) return ServiceStatus::limit_exceeded;
    std::copy(call.reply.begin(), call.reply.end(), output.begin());
    sequence = id; written = static_cast<std::uint32_t>(call.reply.size());
    return ServiceStatus::ok;
}
ServiceStatus WebServices::acknowledge(std::uint64_t generation, std::uint64_t through) {
    auto& state = *impl_; state.check_owner();
    if (generation != state.generation) return ServiceStatus::invalid_handle;
    if (state.blocked()) return ServiceStatus::unavailable;
    if (through > state.highest) return ServiceStatus::invalid_request;
    for (const auto& [sequence, call] : state.calls) {
        if (sequence > through) break;
        if (call.phase != Impl::Phase::ready) return ServiceStatus::conflict;
    }
    auto call = state.calls.begin();
    while (call != state.calls.end() && call->first <= through) {
        state.retained_bytes -= call->second.reservation; call = state.calls.erase(call);
    }
    state.retired = std::max(state.retired, through); return ServiceStatus::ok;
}
void WebServices::close() noexcept {
    if (!impl_ || impl_->owner != std::this_thread::get_id()) return;
    impl_->is_closed = true; impl_->settle_closed();
}
bool WebServices::closed() const noexcept { return impl_->is_closed; }
std::uint64_t WebServices::generation() const noexcept { return impl_->generation; }
bool WebServices::has_queued_calls() const noexcept {
    return std::any_of(impl_->calls.begin(), impl_->calls.end(), [](const auto& entry) {
        return entry.second.phase == Impl::Phase::queued;
    });
}
std::size_t WebServices::retained_call_count() const noexcept { return impl_->calls.size(); }
std::size_t WebServices::retained_bytes() const noexcept { return impl_->retained_bytes; }

} // namespace foundation::appended
