#include "foundation/appended/registry.hpp"

#include <algorithm>
#include <limits>
#include <map>
#include <stdexcept>
#include <utility>

namespace foundation::appended {
namespace {
constexpr auto header_bytes = FOUNDATION_APPENDED_ENVELOPE_BYTES;
void put(std::span<std::uint8_t> bytes, std::uint64_t value) noexcept {
    for (std::size_t i = 0; i < bytes.size(); ++i) bytes[i] = static_cast<std::uint8_t>(value >> (8 * i));
}
bool valid_name(std::string_view name) noexcept {
    if (name.size() > 128 || name.empty() || name.find('.') == std::string_view::npos) return false;
    bool first = true;
    for (const auto ch : name) {
        if (ch == '.') { if (first) return false; first = true; continue; }
        if (ch >= 'a' && ch <= 'z') { first = false; continue; }
        if (!first && ((ch >= '0' && ch <= '9') || ch == '_' || ch == '-')) continue;
        return false;
    }
    return !first;
}
bool valid_schema(const SchemaId& schema) noexcept {
    return std::any_of(schema.begin(), schema.end(), [](auto byte) { return byte != 0; });
}
ServiceDescriptor bootstrap_descriptor() {
    return {FOUNDATION_APPENDED_BOOTSTRAP_NAME, 1, 0, bootstrap_schema(), 256};
}
bool known_status(ServiceStatus status) noexcept {
    return static_cast<std::uint32_t>(status) <= FOUNDATION_APPENDED_SERVICE_UNCERTAIN &&
        status != ServiceStatus::result_available;
}
struct OwnedField { std::uint16_t id; FieldType type; Bytes value; };
Bytes record(std::initializer_list<OwnedField> fields) {
    std::vector<FieldView> views;
    for (const auto& field : fields) views.push_back({field.id, field.type, true, field.value});
    Bytes output;
    if (encode_record(views, output) != CodecStatus::ok) throw std::logic_error("invalid built-in record");
    return output;
}
Bytes text_bytes(std::string_view text) { return Bytes(text.begin(), text.end()); }
bool parse(std::span<const std::uint8_t> payload, std::vector<FieldView>& fields,
           std::uint16_t max_id) {
    if (decode_record(payload, fields) != CodecStatus::ok) return false;
    for (const auto& field : fields)
        if ((field.id > max_id && field.must_understand) ||
            (field.id <= max_id && !field.must_understand)) return false;
    return true;
}
const FieldView* field(const std::vector<FieldView>& fields, std::uint16_t id) noexcept {
    for (const auto& item : fields) if (item.id == id) return &item;
    return nullptr;
}
bool u32(const std::vector<FieldView>& fields, std::uint16_t id, std::uint32_t& value) noexcept {
    const auto* item = field(fields, id); return item && read_u32(*item, value);
}
bool u64(const std::vector<FieldView>& fields, std::uint16_t id, std::uint64_t& value) noexcept {
    const auto* item = field(fields, id); return item && read_u64(*item, value);
}
void write_reply(std::span<std::uint8_t> destination, const Envelope& request,
                 ServiceStatus status, std::span<const std::uint8_t> payload,
                 std::uint64_t correlation = 0) noexcept {
    std::fill(destination.begin(), destination.begin() + header_bytes, 0);
    put(destination.subspan(0, 4), header_bytes + payload.size());
    put(destination.subspan(4, 2), 1); put(destination.subspan(8, 4), FOUNDATION_APPENDED_MESSAGE_REPLY);
    put(destination.subspan(16, 8), request.generation); put(destination.subspan(24, 8), request.sequence);
    put(destination.subspan(32, 8), request.interface_handle); put(destination.subspan(40, 4), request.operation);
    put(destination.subspan(44, 4), payload.size()); put(destination.subspan(48, 4), static_cast<std::uint32_t>(status));
    put(destination.subspan(56, 8), correlation);
    std::copy(payload.begin(), payload.end(), destination.begin() + header_bytes);
}
} // namespace

struct Registry::Impl {
    struct Accounting { std::size_t bytes{0}; };
    struct Result {
        std::shared_ptr<Accounting> accounting;
        Bytes storage;
        std::uint64_t handle{0};
        std::size_t bytes{0};
        bool exposed{false}, released{false};
        Result(std::shared_ptr<Accounting> account, std::size_t reserve, std::uint64_t id)
            : accounting(std::move(account)), storage(reserve), handle(id) { accounting->bytes += storage.size(); }
        ~Result() { accounting->bytes -= storage.size(); }
    };
    struct Service { ServiceDescriptor descriptor; ServiceHandler handler; };
    struct Outcome {
        Bytes request;
        ServiceStatus status{ServiceStatus::ok};
        std::shared_ptr<Result> result;
        std::size_t offset{0}, bytes{0};
        bool read_slice{false};
    };
    std::uint64_t generation, next_handle{1}, highest{0}, retired{0};
    Limits limits;
    bool is_closed{false}, busy{false}, close_pending{false}, handle_exhausted{false};
    std::map<std::uint64_t, Service> services;
    std::map<std::uint64_t, std::shared_ptr<Result>> results;
    std::map<std::uint64_t, Outcome> outcomes;
    std::shared_ptr<Accounting> accounting{std::make_shared<Accounting>()};

    Impl(std::uint64_t gen, Limits bounds) : generation(gen), limits(bounds) {}
    void advance_handle() noexcept {
        if (next_handle == std::numeric_limits<std::uint64_t>::max()) handle_exhausted = true;
        else ++next_handle;
    }
    void retire(std::uint64_t through) noexcept {
        auto it = outcomes.begin();
        while (it != outcomes.end() && it->first <= through) {
            const auto& result = it->second.result;
            if (result && !result->exposed && !it->second.read_slice) results.erase(result->handle);
            it = outcomes.erase(it);
        }
        retired = std::max(retired, through);
    }
    void reply(std::span<std::uint8_t> destination, const Envelope& request, Outcome& outcome) noexcept {
        if (outcome.result && outcome.result->released) {
            write_reply(destination, request, ServiceStatus::expired, {}); return;
        }
        if (outcome.bytes > destination.size() - header_bytes) {
            /* Read slices are checked before admission and must never create a
             * second retained handle for an already-retained result. */
            if (outcome.read_slice) {
                write_reply(destination, request, ServiceStatus::invalid_request, {}); return;
            }
            outcome.result->exposed = true;
            write_reply(destination, request, ServiceStatus::result_available, {}, outcome.result->handle);
        } else {
            const auto bytes = outcome.result ? std::span<const std::uint8_t>(outcome.result->storage)
                .subspan(outcome.offset, outcome.bytes) : std::span<const std::uint8_t>{};
            write_reply(destination, request, outcome.status, bytes);
        }
    }
};

Registry::Registry(std::uint64_t generation, Limits limits) {
    if (generation == 0 || limits.max_message_bytes < header_bytes ||
        limits.max_message_bytes > FOUNDATION_APPENDED_MAX_MESSAGE_BYTES ||
        limits.max_services == 0 || limits.max_retained_requests < 2 ||
        limits.max_retained_results == 0 || limits.max_retained_bytes == 0 ||
        limits.max_retained_bytes > FOUNDATION_APPENDED_MAX_MESSAGE_BYTES)
        throw std::invalid_argument("invalid appended registry limits or generation");
    impl_ = std::make_unique<Impl>(generation, limits);
}
Registry::~Registry() = default;
Registry::Registry(Registry&&) noexcept = default;
Registry& Registry::operator=(Registry&&) noexcept = default;
std::uint64_t Registry::generation() const noexcept { return impl_->generation; }
const Limits& Registry::limits() const noexcept { return impl_->limits; }
std::size_t Registry::retained_result_count() const noexcept { return impl_->results.size(); }
bool Registry::closed() const noexcept { return impl_->is_closed; }
bool Registry::invocation_active() const noexcept { return impl_->busy; }
void Registry::close() noexcept {
    if (impl_->busy) { impl_->close_pending = true; return; }
    impl_->is_closed = true;
    for (const auto& [id, result] : impl_->results) { (void)id; result->released = true; }
    impl_->outcomes.clear(); impl_->results.clear(); impl_->services.clear();
}
DiscoveryResult Registry::register_service(ServiceDescriptor descriptor, ServiceHandler handler) {
    auto& state = *impl_;
    if (state.is_closed || state.busy) return {ServiceStatus::closed, 0, {}};
    if (!valid_name(descriptor.name) || descriptor.name == FOUNDATION_APPENDED_BOOTSTRAP_NAME ||
        descriptor.name.starts_with("foundation.kernel.") || descriptor.major == 0 ||
        !valid_schema(descriptor.schema) || !handler ||
        descriptor.max_reply_bytes > state.limits.max_message_bytes - header_bytes ||
        descriptor.max_reply_bytes > state.limits.max_retained_bytes)
        return {ServiceStatus::invalid_request, 0, {}};
    for (const auto& [handle, service] : state.services) {
        (void)handle;
        if (service.descriptor.name == descriptor.name && service.descriptor.major == descriptor.major &&
            service.descriptor.minor == descriptor.minor) return {ServiceStatus::conflict, 0, {}};
    }
    if (state.services.size() >= state.limits.max_services || state.handle_exhausted)
        return {ServiceStatus::limit_exceeded, 0, {}};
    const auto handle = state.next_handle;
    auto result = DiscoveryResult{ServiceStatus::ok, handle, descriptor};
    state.services.emplace(handle, Impl::Service{std::move(descriptor), std::move(handler)});
    state.advance_handle(); return result;
}
DiscoveryResult Registry::discover(const DiscoveryQuery& query) const {
    const auto& state = *impl_;
    if (state.is_closed) return {ServiceStatus::closed, 0, {}};
    if (!valid_name(query.name) || query.major == 0 || query.minimum_minor > query.maximum_minor)
        return {ServiceStatus::invalid_request, 0, {}};
    bool named = false, versioned = false;
    DiscoveryResult result;
    const auto consider = [&](std::uint64_t handle, const ServiceDescriptor& descriptor) {
        if (descriptor.name != query.name) return;
        named = true;
        if (descriptor.major != query.major || descriptor.minor < query.minimum_minor ||
            descriptor.minor > query.maximum_minor) return;
        versioned = true;
        if (query.schema && descriptor.schema != *query.schema) return;
        if (result.status != ServiceStatus::ok || descriptor.minor > result.descriptor.minor)
            result = {ServiceStatus::ok, handle, descriptor};
    };
    auto bootstrap = bootstrap_descriptor();
    bootstrap.max_reply_bytes = std::min(bootstrap.max_reply_bytes, state.limits.max_message_bytes - header_bytes);
    consider(0, bootstrap);
    for (const auto& [handle, service] : state.services) consider(handle, service.descriptor);
    if (result.status != ServiceStatus::ok) result.status = versioned ? ServiceStatus::schema_mismatch :
        named ? ServiceStatus::unsupported_version : ServiceStatus::not_found;
    return result;
}

TransportStatus Registry::call(std::span<std::uint8_t> memory, std::uint32_t request_offset,
    std::uint32_t request_bytes, std::uint32_t reply_offset, std::uint32_t reply_capacity) noexcept {
    auto& state = *impl_;
    if (state.busy) return TransportStatus::internal_error;
    if (request_offset > memory.size() || request_bytes > memory.size() - request_offset ||
        reply_offset > memory.size() || reply_capacity > memory.size() - reply_offset)
        return TransportStatus::invalid_range;
    if (reply_capacity < header_bytes) return TransportStatus::reply_too_small;
    if (request_offset < static_cast<std::uint64_t>(reply_offset) + reply_capacity &&
        reply_offset < static_cast<std::uint64_t>(request_offset) + request_bytes)
        return TransportStatus::overlap;
    if (request_bytes > state.limits.max_message_bytes) return TransportStatus::invalid_envelope;
    const auto request = std::span<const std::uint8_t>(memory).subspan(request_offset, request_bytes);
    const auto destination = memory.subspan(reply_offset, reply_capacity);
    Envelope envelope;
    std::span<const std::uint8_t> payload;
    const auto decoded = decode_envelope(request, envelope, payload);
    if (decoded == CodecStatus::unsupported_version) return TransportStatus::unsupported_envelope;
    if (decoded != CodecStatus::ok || envelope.kind != FOUNDATION_APPENDED_MESSAGE_REQUEST)
        return TransportStatus::invalid_envelope;
    if (envelope.generation != state.generation) return TransportStatus::stale_generation;
    try {
        if (state.is_closed) { write_reply(destination, envelope, ServiceStatus::closed, {}); return TransportStatus::ok; }
        if (const auto prior = state.outcomes.find(envelope.sequence); prior != state.outcomes.end()) {
            if (!std::equal(request.begin(), request.end(), prior->second.request.begin(), prior->second.request.end()))
                return TransportStatus::replay;
            state.reply(destination, envelope, prior->second); return TransportStatus::ok;
        }
        if (envelope.sequence <= state.highest || envelope.sequence <= state.retired) {
            write_reply(destination, envelope, ServiceStatus::expired, {}); return TransportStatus::ok;
        }
        if (state.highest == std::numeric_limits<std::uint64_t>::max() || state.handle_exhausted)
            return TransportStatus::exhausted;

        Impl::Outcome outcome;
        outcome.request.assign(request.begin(), request.end());
        Bytes prepared;
        std::uint32_t reserve = 0;
        std::uint64_t ack = 0, release = 0;
        Impl::Service* provider = nullptr;
        bool acknowledge = false;
        if (envelope.interface_handle != 0) {
            const auto service = state.services.find(envelope.interface_handle);
            if (service == state.services.end()) outcome.status = ServiceStatus::invalid_handle;
            else { provider = &service->second; reserve = provider->descriptor.max_reply_bytes; }
        } else {
            std::vector<FieldView> fields;
            switch (envelope.operation) {
            case FOUNDATION_APPENDED_CONTROL_DISCOVER: {
                std::uint32_t major = 0, minimum = 0, maximum = 0;
                if (!parse(payload, fields, 5) || !u32(fields, 2, major) || !u32(fields, 3, minimum) ||
                    !u32(fields, 4, maximum) || major > 65535 || minimum > 65535 || maximum > 65535) {
                    outcome.status = ServiceStatus::invalid_request; break;
                }
                const auto* name = field(fields, 1);
                if (!name || name->type != FieldType::utf8) { outcome.status = ServiceStatus::invalid_request; break; }
                DiscoveryQuery query{std::string_view(reinterpret_cast<const char*>(name->value.data()), name->value.size()),
                    static_cast<std::uint16_t>(major), static_cast<std::uint16_t>(minimum), static_cast<std::uint16_t>(maximum), {}};
                if (const auto* schema = field(fields, 5)) {
                    if (schema->type != FieldType::bytes || schema->value.size() != 32) {
                        outcome.status = ServiceStatus::invalid_request; break;
                    }
                    SchemaId expected{}; std::copy(schema->value.begin(), schema->value.end(), expected.begin()); query.schema = expected;
                }
                const auto found = discover(query);
                outcome.status = found.status;
                if (found.status == ServiceStatus::ok) prepared = record({
                    {1, FieldType::u64, encode_u64(found.handle)}, {2, FieldType::utf8, text_bytes(found.descriptor.name)},
                    {3, FieldType::u32, encode_u32(found.descriptor.major)}, {4, FieldType::u32, encode_u32(found.descriptor.minor)},
                    {5, FieldType::bytes, Bytes(found.descriptor.schema.begin(), found.descriptor.schema.end())},
                    {6, FieldType::u32, encode_u32(found.descriptor.max_reply_bytes)}});
                break;
            }
            case FOUNDATION_APPENDED_CONTROL_RESULT_READ: {
                std::uint64_t handle = 0; std::uint32_t offset = 0, count = 0;
                if (!parse(payload, fields, 3) || !u64(fields, 1, handle) || !u32(fields, 2, offset) || !u32(fields, 3, count)) {
                    outcome.status = ServiceStatus::invalid_request; break;
                }
                const auto found = state.results.find(handle);
                if (found == state.results.end() || !found->second->exposed) {
                    outcome.status = ServiceStatus::invalid_handle; break;
                }
                if (offset > found->second->bytes || count > found->second->bytes - offset || count > reply_capacity - header_bytes ||
                    count > state.limits.max_message_bytes - header_bytes) {
                    outcome.status = ServiceStatus::invalid_request; break;
                }
                outcome.result = found->second; outcome.offset = offset; outcome.bytes = count; outcome.read_slice = true;
                break;
            }
            case FOUNDATION_APPENDED_CONTROL_RESULT_RELEASE:
                if (!parse(payload, fields, 1) || !u64(fields, 1, release)) outcome.status = ServiceStatus::invalid_request;
                else if (const auto found = state.results.find(release);
                         found == state.results.end() || !found->second->exposed) outcome.status = ServiceStatus::invalid_handle;
                break;
            case FOUNDATION_APPENDED_CONTROL_LIMITS:
                if (!parse(payload, fields, 0)) outcome.status = ServiceStatus::invalid_request;
                else if (encode_init_context(state.generation, state.limits, prepared) != CodecStatus::ok)
                    outcome.status = ServiceStatus::internal_error;
                break;
            case FOUNDATION_APPENDED_CONTROL_ACKNOWLEDGE:
                if (!parse(payload, fields, 1) || !u64(fields, 1, ack) || ack > state.highest || ack >= envelope.sequence)
                    outcome.status = ServiceStatus::invalid_request;
                else acknowledge = true;
                break;
            default: outcome.status = ServiceStatus::unknown_operation; break;
            }
            reserve = static_cast<std::uint32_t>(prepared.size());
        }
        std::size_t retiring = 0;
        if (acknowledge) for (const auto& [sequence, prior] : state.outcomes) { (void)prior; if (sequence <= ack) ++retiring; }
        if (reserve > state.limits.max_message_bytes - header_bytes ||
            state.outcomes.size() - retiring >= state.limits.max_retained_requests ||
            (reserve > 0 && (state.results.size() >= state.limits.max_retained_results ||
             reserve > state.limits.max_retained_bytes - state.accounting->bytes))) {
            write_reply(destination, envelope, ServiceStatus::limit_exceeded, {}); return TransportStatus::ok;
        }
        std::uint64_t result_handle = 0;
        if (reserve > 0) {
            result_handle = state.next_handle;
            outcome.result = std::make_shared<Impl::Result>(state.accounting, reserve, result_handle);
            std::copy(prepared.begin(), prepared.end(), outcome.result->storage.begin());
            outcome.bytes = prepared.size(); outcome.result->bytes = outcome.bytes;
            state.results.emplace(result_handle, outcome.result);
        }
        std::map<std::uint64_t, Impl::Outcome>::iterator admitted;
        try { admitted = state.outcomes.emplace(envelope.sequence, std::move(outcome)).first; }
        catch (...) { if (result_handle != 0) state.results.erase(result_handle); throw; }
        state.highest = envelope.sequence;
        if (result_handle != 0) state.advance_handle();
        auto& saved = admitted->second;
        if (acknowledge) state.retire(ack);
        if (saved.status == ServiceStatus::ok && release != 0) {
            const auto found = state.results.find(release);
            found->second->released = true; state.results.erase(found);
        }
        if (provider) {
            state.busy = true;
            ServiceReply response;
            try {
                response = provider->handler(envelope.operation,
                    std::span<const std::uint8_t>(saved.request).subspan(header_bytes),
                    saved.result ? std::span<std::uint8_t>(saved.result->storage) : std::span<std::uint8_t>{});
            } catch (...) { response = {ServiceStatus::uncertain, 0}; }
            state.busy = false;
            if (!known_status(response.status) || response.bytes > reserve ||
                (response.status != ServiceStatus::ok && response.bytes != 0)) response = {ServiceStatus::internal_error, 0};
            saved.status = response.status; saved.bytes = response.bytes;
            if (saved.result) saved.result->bytes = response.bytes;
        }
        if (saved.result && saved.bytes == 0 && !saved.read_slice) {
            state.results.erase(saved.result->handle); saved.result.reset();
        }
        state.reply(destination, envelope, saved);
        if (state.close_pending) close();
        return TransportStatus::ok;
    } catch (...) { state.busy = false; return TransportStatus::internal_error; }
}

CodecStatus encode_init_context(std::uint64_t generation, const Limits& limits, Bytes& output) {
    if (generation == 0) return CodecStatus::invalid_value;
    auto candidate = record({{1, FieldType::u64, encode_u64(generation)},
        {2, FieldType::u32, encode_u32(FOUNDATION_APPENDED_ABI_VERSION)},
        {3, FieldType::u32, encode_u32(header_bytes)}, {4, FieldType::u32, encode_u32(limits.max_message_bytes)},
        {5, FieldType::bytes, Bytes(bootstrap_schema().begin(), bootstrap_schema().end())},
        {6, FieldType::u32, encode_u32(limits.max_retained_requests)},
        {7, FieldType::u32, encode_u32(limits.max_retained_results)},
        {8, FieldType::u32, encode_u32(limits.max_retained_bytes)}});
    output.swap(candidate); return CodecStatus::ok;
}
/* SHA-256 of the exact canonical bootstrap.json file in abi/appended/v1. */
const SchemaId& bootstrap_schema() noexcept {
    static constexpr SchemaId schema = {FOUNDATION_APPENDED_BOOTSTRAP_SCHEMA_BYTES};
    return schema;
}
} // namespace foundation::appended
