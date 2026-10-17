#include <foundation/appended/providers.hpp>
#include <foundation/appended/module.hpp>

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
std::uint64_t scalar(Span bytes) noexcept {
    std::uint64_t value = 0;
    for (std::size_t n = 0; n < bytes.size(); ++n) value |= std::uint64_t(bytes[n]) << (8 * n);
    return value;
}
bool name_valid(std::string_view name) noexcept {
    if (name.empty() || name.size() > FOUNDATION_PROVIDER_MAX_NAME_BYTES ||
        name.find('.') == std::string_view::npos) return false;
    bool first = true;
    for (const auto ch : name) {
        if (ch == '.') { if (first) return false; first = true; }
        else if (ch >= 'a' && ch <= 'z') first = false;
        else if (first || !((ch >= '0' && ch <= '9') || ch == '-' || ch == '_')) return false;
    }
    return !first;
}
bool schema_valid(const SchemaId& value) noexcept {
    return std::any_of(value.begin(), value.end(), [](auto byte) { return byte != 0; });
}
struct Fields {
    std::array<std::optional<FieldView>, 7> known{};
    const FieldView* get(std::uint16_t id) const noexcept {
        return known[id - 1] ? &*known[id - 1] : nullptr;
    }
    bool u32(std::uint16_t id, std::uint32_t& value) const noexcept {
        const auto* f = get(id); return f && read_u32(*f, value);
    }
    bool u64(std::uint16_t id, std::uint64_t& value) const noexcept {
        const auto* f = get(id); return f && read_u64(*f, value);
    }
};
/* This path is also used for RESPOND, after application effects. It validates
 * recursively without vector allocation and retains no borrowed field views. */
bool parse(Span bytes, std::uint16_t maximum_id, Fields& output) noexcept {
    if (validate_record_bytes(bytes) != CodecStatus::ok) return false;
    std::size_t offset = 0;
    while (offset < bytes.size()) {
        const auto id = static_cast<std::uint16_t>(scalar(bytes.subspan(offset, 2)));
        const auto type = static_cast<FieldType>(bytes[offset + 2]);
        const bool required = bytes[offset + 3] != 0;
        const auto size = static_cast<std::uint32_t>(scalar(bytes.subspan(offset + 4, 4)));
        if (id <= maximum_id) {
            if (!required) return false;
            output.known[id - 1] = FieldView{id, type, required, bytes.subspan(offset + 8, size)};
        } else if (required) return false;
        offset += 8 + size;
    }
    return true;
}
struct OwnedField { std::uint16_t id; FieldType type; Bytes bytes; };
Bytes record(std::initializer_list<OwnedField> fields) {
    std::array<FieldView, 7> views{};
    std::size_t count = 0;
    for (const auto& f : fields) views[count++] = {f.id, f.type, true, f.bytes};
    Bytes bytes;
    if (encode_record(std::span(views).first(count), bytes) != CodecStatus::ok)
        throw std::logic_error("invalid provider control record");
    return bytes;
}
Bytes text_bytes(std::string_view text) { return Bytes(text.begin(), text.end()); }
bool same(const ProviderRequest& left, const ProviderRequest& right) noexcept {
    return left.generation == right.generation && left.sequence == right.sequence &&
        left.provider == right.provider && left.operation == right.operation && left.payload == right.payload;
}
bool returned_status(std::uint32_t value) noexcept {
    return value <= FOUNDATION_APPENDED_SERVICE_UNCERTAIN && value != FOUNDATION_APPENDED_SERVICE_RESULT_AVAILABLE;
}
} // namespace

struct ModuleProviders::State {
    enum class Phase { registration, active, closed };
    struct Call {
        ProviderRequest request;
        ProviderOutcome outcome;
        std::size_t reservation{0}, response_bytes{0};
    };
    Module* module;
    Registry* registry;
    ProviderLimits limits;
    Phase phase{Phase::registration};
    std::thread::id owner{std::this_thread::get_id()};
    std::uint64_t service{0}, next_provider{1}, highest{0}, retired{0}, last_event_sequence{0};
    bool provider_exhausted{false}, invoking{false}, responded{false}, protocol_error{false};
    Call* current{nullptr};
    std::size_t retained_bytes{0};
    std::map<std::uint64_t, ProviderDescriptor> providers;
    std::map<std::uint64_t, Call> calls;
    EventSequence events;
    GenerationSource private_events;
    struct Invocation {
        State& self;
        explicit Invocation(State& value) : self(value) {
            self.invoking = true; self.current = nullptr;
            self.responded = false; self.protocol_error = false;
        }
        ~Invocation() { self.current = nullptr; self.invoking = false; }
    };

    State(Module& vm, Registry& kernel, EventSequence source, ProviderLimits bounds)
        : module(&vm), registry(&kernel), limits(bounds), events(std::move(source)) {}
    void check_owner() const {
        if (std::this_thread::get_id() != owner) throw std::logic_error("provider bridge requires its serialized owner");
    }
    bool gone() const noexcept {
        return phase == Phase::closed || registry->closed() || module->closed();
    }
    void close() noexcept { phase = Phase::closed; providers.clear(); }
    ProviderDiscovery find(const DiscoveryQuery& query) const {
        if (!name_valid(query.name) || query.major == 0 || query.minimum_minor > query.maximum_minor)
            return {ServiceStatus::invalid_request, 0, {}};
        bool named = false, versioned = false;
        ProviderDiscovery found;
        for (const auto& [handle, provider] : providers) {
            const auto& contract = provider.contract;
            if (contract.name != query.name) continue;
            named = true;
            if (contract.major != query.major || contract.minor < query.minimum_minor || contract.minor > query.maximum_minor) continue;
            versioned = true;
            if (query.schema && contract.schema != *query.schema) continue;
            if (found.status != ServiceStatus::ok || contract.minor > found.descriptor.contract.minor)
                found = {ServiceStatus::ok, handle, provider};
        }
        if (found.status != ServiceStatus::ok) found.status = versioned ? ServiceStatus::schema_mismatch :
            named ? ServiceStatus::unsupported_version : ServiceStatus::not_found;
        return found;
    }
    ServiceReply control(std::uint32_t operation, Span request, std::span<std::uint8_t> response) {
        check_owner();
        if (gone()) return {ServiceStatus::closed, 0};
        Fields fields;
        if (operation == FOUNDATION_PROVIDER_RESPOND) {
            if (!invoking || !current || phase != Phase::active || !module->invocation_active())
                return {ServiceStatus::invalid_request, 0};
            std::uint64_t invocation = 0, provider = 0;
            std::uint32_t status = 0;
            if (!parse(request, 4, fields) || !fields.u64(1, invocation) || !fields.u64(2, provider) || !fields.u32(3, status))
                return {ServiceStatus::invalid_request, 0};
            const auto* payload = fields.get(4);
            if (!payload || payload->type != FieldType::bytes) return {ServiceStatus::invalid_request, 0};
            if (invocation != current->request.sequence || provider != current->request.provider)
                return {ServiceStatus::invalid_handle, 0};
            if (responded) { protocol_error = true; return {ServiceStatus::conflict, 0}; }
            if (!returned_status(status) || payload->value.size() > current->outcome.payload.size() ||
                (status != FOUNDATION_APPENDED_SERVICE_OK && !payload->value.empty()))
                return {ServiceStatus::invalid_request, 0};
            std::copy(payload->value.begin(), payload->value.end(), current->outcome.payload.begin());
            current->outcome.status = static_cast<ServiceStatus>(status);
            current->response_bytes = payload->value.size(); responded = true;
            return {ServiceStatus::ok, 0};
        }
        if (operation == FOUNDATION_PROVIDER_REGISTER) {
            if (phase != Phase::registration || !module->initializing()) return {ServiceStatus::invalid_request, 0};
            std::uint32_t major = 0, minor = 0, maximum_request = 0, maximum_reply = 0;
            if (!parse(request, 6, fields) || !fields.u32(2, major) || !fields.u32(3, minor) ||
                !fields.u32(5, maximum_request) || !fields.u32(6, maximum_reply) || major == 0 || major > 65535 || minor > 65535)
                return {ServiceStatus::invalid_request, 0};
            const auto* name = fields.get(1); const auto* schema = fields.get(4);
            if (!name || name->type != FieldType::utf8 || !schema || schema->type != FieldType::bytes || schema->value.size() != 32)
                return {ServiceStatus::invalid_request, 0};
            const auto text = std::string_view(reinterpret_cast<const char*>(name->value.data()), name->value.size());
            if (!name_valid(text) || text.starts_with("foundation.")) return {ServiceStatus::invalid_request, 0};
            SchemaId identity{}; std::copy(schema->value.begin(), schema->value.end(), identity.begin());
            if (!schema_valid(identity)) return {ServiceStatus::invalid_request, 0};
            if (maximum_request > limits.max_payload_bytes || maximum_reply > limits.max_payload_bytes ||
                maximum_request > registry->limits().max_message_bytes - FOUNDATION_PROVIDER_CALL_OVERHEAD_BYTES ||
                maximum_reply > registry->limits().max_message_bytes - FOUNDATION_PROVIDER_RESPONSE_OVERHEAD_BYTES)
                return {ServiceStatus::limit_exceeded, 0};
            const DiscoveryQuery exact{text, static_cast<std::uint16_t>(major), static_cast<std::uint16_t>(minor),
                static_cast<std::uint16_t>(minor), {}};
            if (find(exact).status == ServiceStatus::ok || registry->discover(exact).status == ServiceStatus::ok)
                return {ServiceStatus::conflict, 0};
            if (providers.size() >= limits.max_providers || provider_exhausted) return {ServiceStatus::limit_exceeded, 0};
            const auto handle = next_provider;
            const auto encoded = record({{1, FieldType::u64, encode_u64(handle)}});
            if (encoded.size() > response.size()) return {ServiceStatus::internal_error, 0};
            ProviderDescriptor descriptor{{std::string(text), static_cast<std::uint16_t>(major), static_cast<std::uint16_t>(minor),
                identity, maximum_reply}, maximum_request};
            providers.emplace(handle, std::move(descriptor));
            if (next_provider == std::numeric_limits<std::uint64_t>::max()) provider_exhausted = true;
            else ++next_provider;
            std::copy(encoded.begin(), encoded.end(), response.begin());
            return {ServiceStatus::ok, static_cast<std::uint32_t>(encoded.size())};
        }
        if (operation == FOUNDATION_PROVIDER_DISCOVER) {
            std::uint32_t major = 0, low = 0, high = 0;
            if (!parse(request, 5, fields) || !fields.u32(2, major) || !fields.u32(3, low) || !fields.u32(4, high) ||
                major == 0 || major > 65535 || low > 65535 || high > 65535)
                return {ServiceStatus::invalid_request, 0};
            const auto* name = fields.get(1);
            if (!name || name->type != FieldType::utf8) return {ServiceStatus::invalid_request, 0};
            DiscoveryQuery query{std::string_view(reinterpret_cast<const char*>(name->value.data()), name->value.size()),
                static_cast<std::uint16_t>(major), static_cast<std::uint16_t>(low), static_cast<std::uint16_t>(high), {}};
            if (const auto* schema = fields.get(5)) {
                if (schema->type != FieldType::bytes || schema->value.size() != 32) return {ServiceStatus::invalid_request, 0};
                SchemaId expected{}; std::copy(schema->value.begin(), schema->value.end(), expected.begin()); query.schema = expected;
            }
            const auto found = find(query);
            if (found.status != ServiceStatus::ok) return {found.status, 0};
            const auto& c = found.descriptor.contract;
            const auto encoded = record({{1, FieldType::u64, encode_u64(found.handle)},
                {2, FieldType::utf8, text_bytes(c.name)}, {3, FieldType::u32, encode_u32(c.major)},
                {4, FieldType::u32, encode_u32(c.minor)}, {5, FieldType::bytes, Bytes(c.schema.begin(), c.schema.end())},
                {6, FieldType::u32, encode_u32(found.descriptor.max_request_bytes)}, {7, FieldType::u32, encode_u32(c.max_reply_bytes)}});
            if (encoded.size() > response.size()) return {ServiceStatus::internal_error, 0};
            std::copy(encoded.begin(), encoded.end(), response.begin());
            return {ServiceStatus::ok, static_cast<std::uint32_t>(encoded.size())};
        }
        return {ServiceStatus::unknown_operation, 0};
    }
};

ModuleProviders::ModuleProviders(Module& module, Registry& registry, EventSequence events, ProviderLimits limits)
    : module_(module), registry_(registry) {
    if (!module.uses_registry(registry) || module.invocation_active() || module.initialized() || module.closed() ||
        registry.invocation_active() || registry.closed() || registry.limits().max_message_bytes < 320 ||
        registry.limits().max_retained_bytes < 256 || limits.max_providers == 0 || limits.max_providers > FOUNDATION_PROVIDER_MAX_PROVIDERS ||
        limits.max_payload_bytes > FOUNDATION_PROVIDER_MAX_PAYLOAD_BYTES || limits.max_retained_calls == 0 ||
        limits.max_retained_calls > FOUNDATION_PROVIDER_MAX_RETAINED_CALLS || limits.max_retained_bytes == 0 ||
        limits.max_retained_bytes > FOUNDATION_PROVIDER_MAX_RETAINED_BYTES)
        throw std::invalid_argument("invalid module provider binding, lifecycle or limits");
    state_ = std::make_shared<State>(module, registry, std::move(events), limits);
    ServiceDescriptor descriptor{FOUNDATION_PROVIDER_SERVICE_NAME, FOUNDATION_PROVIDER_MAJOR, FOUNDATION_PROVIDER_MINOR, schema(), 256};
    const auto owned = state_;
    const auto registered = registry.register_service(std::move(descriptor), [owned](auto operation, auto request, auto response) {
        return owned->control(operation, request, response);
    });
    if (registered.status != ServiceStatus::ok) throw std::runtime_error("could not register module provider control service");
    state_->service = registered.handle;
}
ModuleProviders::~ModuleProviders() { close(); }
ServiceStatus ModuleProviders::activate() {
    auto& s = *state_; s.check_owner();
    if (s.gone()) { s.close(); return ServiceStatus::closed; }
    if (module_.invocation_active() || registry_.invocation_active()) return ServiceStatus::unavailable;
    if (s.phase == State::Phase::active) return ServiceStatus::conflict;
    if (!module_.initialized()) return ServiceStatus::unavailable;
    // Native startup registration must not silently take an application route.
    for (const auto& [handle, provider] : s.providers) {
        (void)handle; const auto& c = provider.contract;
        if (registry_.discover({c.name, c.major, c.minor, c.minor, {}}).status == ServiceStatus::ok) {
            s.close(); module_.shutdown(FOUNDATION_APPENDED_SHUTDOWN_FAILED); return ServiceStatus::conflict;
        }
    }
    s.phase = State::Phase::active; return ServiceStatus::ok;
}
ProviderDiscovery ModuleProviders::discover(const DiscoveryQuery& query) const {
    const auto& s = *state_; s.check_owner();
    if (s.gone()) return {ServiceStatus::closed, 0, {}};
    if (s.phase != State::Phase::active) return {ServiceStatus::unavailable, 0, {}};
    return s.find(query);
}
ProviderOutcome ModuleProviders::invoke(const ProviderRequest& request) {
    auto& s = *state_; s.check_owner();
    if (request.generation != registry_.generation()) return {ServiceStatus::invalid_handle, {}};
    if (request.sequence == 0) return {ServiceStatus::invalid_request, {}};
    if (const auto old = s.calls.find(request.sequence); old != s.calls.end()) {
        if (!same(request, old->second.request)) return {ServiceStatus::conflict, {}};
        // No unfinished calls are observable through a recursive host request.
        if (s.invoking) return {ServiceStatus::unavailable, {}};
        return old->second.outcome;
    }
    if (request.sequence <= s.highest || request.sequence <= s.retired) return {ServiceStatus::expired, {}};
    if (s.gone()) { s.close(); return {ServiceStatus::closed, {}}; }
    if (s.phase != State::Phase::active || s.invoking || module_.invocation_active() || registry_.invocation_active())
        return {ServiceStatus::unavailable, {}};
    const auto provider = s.providers.find(request.provider);
    if (provider == s.providers.end()) return {ServiceStatus::invalid_handle, {}};
    const auto maximum_reply = provider->second.contract.max_reply_bytes;
    if (request.payload.size() > provider->second.max_request_bytes || request.payload.size() > s.limits.max_payload_bytes)
        return {ServiceStatus::limit_exceeded, {}};
    const auto reservation = request.payload.size() + maximum_reply;
    if (s.calls.size() >= s.limits.max_retained_calls || reservation > s.limits.max_retained_bytes - s.retained_bytes)
        return {ServiceStatus::limit_exceeded, {}};
    State::Invocation invocation(s);
    const auto payload = record({{1, FieldType::u64, encode_u64(request.provider)},
        {2, FieldType::u32, encode_u32(request.operation)}, {3, FieldType::bytes, request.payload}});
    if (payload.size() > registry_.limits().max_message_bytes - FOUNDATION_APPENDED_ENVELOPE_BYTES)
        return {ServiceStatus::limit_exceeded, {}};
    State::Call call; call.request = request; call.reservation = reservation;
    call.outcome.payload.resize(maximum_reply);
    ProviderOutcome returned; returned.payload.resize(maximum_reply);
    const auto sequence = s.events ? s.events() : s.private_events.next();
    if (!sequence || *sequence == 0 || *sequence <= s.last_event_sequence) {
        s.close(); module_.shutdown(FOUNDATION_APPENDED_SHUTDOWN_FAILED); return {ServiceStatus::limit_exceeded, {}};
    }
    s.last_event_sequence = *sequence;
    if (s.gone() || module_.invocation_active() || registry_.invocation_active())
        return {s.gone() ? ServiceStatus::closed : ServiceStatus::unavailable, {}};
    Envelope event; event.kind = FOUNDATION_APPENDED_MESSAGE_EVENT;
    event.sequence = *sequence; event.interface_handle = s.service; event.operation = FOUNDATION_PROVIDER_EVENT_CALL;
    event.generation = call.request.generation;
    event.correlation = call.request.sequence;
    Bytes encoded;
    if (encode_envelope(event, payload, encoded) != CodecStatus::ok) return {ServiceStatus::limit_exceeded, {}};
    const auto admitted_sequence = call.request.sequence;
    const auto [entry, inserted] = s.calls.emplace(admitted_sequence, std::move(call));
    if (!inserted) return {ServiceStatus::conflict, {}};
    s.highest = admitted_sequence; s.retained_bytes += reservation;
    s.current = &entry->second;
    bool failed = false;
    try {
        failed = module_.dispatch(encoded) != FOUNDATION_APPENDED_APP_OK || module_.closed() || registry_.closed();
    } catch (...) { failed = true; }
    auto& saved = entry->second;
    if (failed || !s.responded || s.protocol_error || s.phase == State::Phase::closed) {
        saved.outcome.status = ServiceStatus::uncertain; saved.response_bytes = 0;
        s.close();
    }
    saved.outcome.payload.resize(saved.response_bytes);
    returned.status = saved.outcome.status;
    std::copy(saved.outcome.payload.begin(), saved.outcome.payload.end(), returned.payload.begin());
    returned.payload.resize(saved.response_bytes);
    s.current = nullptr;
    if (s.phase == State::Phase::closed) module_.shutdown(FOUNDATION_APPENDED_SHUTDOWN_FAILED);
    return returned;
}
ServiceStatus ModuleProviders::acknowledge(std::uint64_t through) noexcept {
    auto& s = *state_;
    if (std::this_thread::get_id() != s.owner || s.invoking || module_.invocation_active() || registry_.invocation_active())
        return ServiceStatus::unavailable;
    if (through > s.highest) return ServiceStatus::invalid_request;
    auto current = s.calls.begin();
    while (current != s.calls.end() && current->first <= through) {
        s.retained_bytes -= current->second.reservation; current = s.calls.erase(current);
    }
    s.retired = std::max(s.retired, through); return ServiceStatus::ok;
}
void ModuleProviders::close() noexcept { if (state_) state_->close(); }
bool ModuleProviders::closed() const noexcept { return state_->gone(); }
std::uint64_t ModuleProviders::service_handle() const noexcept { return state_->service; }
std::size_t ModuleProviders::provider_count() const noexcept { return state_->providers.size(); }
std::size_t ModuleProviders::retained_call_count() const noexcept { return state_->calls.size(); }
const SchemaId& ModuleProviders::schema() noexcept {
    static constexpr SchemaId value{FOUNDATION_PROVIDER_SCHEMA_BYTES}; return value;
}
} // namespace foundation::appended
