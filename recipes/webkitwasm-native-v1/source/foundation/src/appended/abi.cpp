#include "foundation/appended/registry.hpp"

#include <algorithm>
#include <limits>

namespace foundation::appended {
namespace {
constexpr std::size_t header_bytes = FOUNDATION_APPENDED_ENVELOPE_BYTES;
constexpr std::size_t max_bytes = FOUNDATION_APPENDED_MAX_MESSAGE_BYTES;
std::uint64_t load(std::span<const std::uint8_t> bytes) noexcept {
    std::uint64_t value = 0;
    for (std::size_t i = 0; i < bytes.size(); ++i)
        value |= static_cast<std::uint64_t>(bytes[i]) << (8 * i);
    return value;
}
void store(std::span<std::uint8_t> bytes, std::uint64_t value) noexcept {
    for (std::size_t i = 0; i < bytes.size(); ++i)
        bytes[i] = static_cast<std::uint8_t>(value >> (8 * i));
}
CodecStatus check_envelope(const Envelope& envelope, std::size_t payload) noexcept {
    if (envelope.major != 1 || envelope.minor != 0) return CodecStatus::unsupported_version;
    if (envelope.kind < FOUNDATION_APPENDED_MESSAGE_REQUEST ||
        envelope.kind > FOUNDATION_APPENDED_MESSAGE_COMPLETION || envelope.flags != 0 ||
        envelope.generation == 0 || envelope.sequence == 0 ||
        envelope.service_status > FOUNDATION_APPENDED_SERVICE_UNCERTAIN)
        return CodecStatus::invalid_value;
    if (envelope.kind == FOUNDATION_APPENDED_MESSAGE_REQUEST &&
        (envelope.service_status != 0 || envelope.correlation != 0))
        return CodecStatus::invalid_value;
    if (envelope.kind == FOUNDATION_APPENDED_MESSAGE_REPLY) {
        if (envelope.service_status == FOUNDATION_APPENDED_SERVICE_RESULT_AVAILABLE) {
            if (envelope.correlation == 0 || payload != 0) return CodecStatus::invalid_value;
        } else if (envelope.correlation != 0) return CodecStatus::invalid_value;
    }
    return CodecStatus::ok;
}
CodecStatus validate_record(std::span<const std::uint8_t> bytes, unsigned depth,
                            std::vector<FieldView>* output) {
    if (bytes.size() > max_bytes || depth > 8) return CodecStatus::limit_exceeded;
    std::size_t offset = 0, count = 0;
    std::uint16_t previous = 0;
    while (offset < bytes.size()) {
        if (bytes.size() - offset < 8) return CodecStatus::truncated;
        const auto id = static_cast<std::uint16_t>(load(bytes.subspan(offset, 2)));
        const auto type = bytes[offset + 2];
        const auto flags = bytes[offset + 3];
        const auto size = static_cast<std::uint32_t>(load(bytes.subspan(offset + 4, 4)));
        if (id <= previous || flags > 1) return CodecStatus::invalid_value;
        if (++count > 64) return CodecStatus::limit_exceeded;
        offset += 8;
        if (size > bytes.size() - offset) return CodecStatus::truncated;
        const auto value = bytes.subspan(offset, size);
        switch (static_cast<FieldType>(type)) {
        case FieldType::u32:
            if (size != 4) return CodecStatus::invalid_value;
            break;
        case FieldType::u64: case FieldType::i64:
            if (size != 8) return CodecStatus::invalid_value;
            break;
        case FieldType::f64: {
            if (size != 8) return CodecStatus::invalid_value;
            const auto bits = load(value);
            if ((bits & UINT64_C(0x7ff0000000000000)) == UINT64_C(0x7ff0000000000000) &&
                (bits & UINT64_C(0x000fffffffffffff)) != 0 &&
                bits != UINT64_C(0x7ff8000000000000)) return CodecStatus::invalid_value;
            break;
        }
        case FieldType::boolean:
            if (size != 1 || value[0] > 1) return CodecStatus::invalid_value;
            break;
        case FieldType::utf8:
            if (!valid_utf8(value)) return CodecStatus::invalid_value;
            break;
        case FieldType::bytes: break;
        case FieldType::record: {
            const auto status = validate_record(value, depth + 1, nullptr);
            if (status != CodecStatus::ok) return status;
            break;
        }
        case FieldType::record_list: {
            if (size < 4) return CodecStatus::truncated;
            const auto records = static_cast<std::uint32_t>(load(value.first(4)));
            if (records > 1024) return CodecStatus::limit_exceeded;
            std::size_t cursor = 4;
            for (std::uint32_t i = 0; i < records; ++i) {
                if (value.size() - cursor < 4) return CodecStatus::truncated;
                const auto length = static_cast<std::uint32_t>(load(value.subspan(cursor, 4)));
                cursor += 4;
                if (length > value.size() - cursor) return CodecStatus::truncated;
                const auto status = validate_record(value.subspan(cursor, length), depth + 1, nullptr);
                if (status != CodecStatus::ok) return status;
                cursor += length;
            }
            if (cursor != value.size()) return CodecStatus::invalid_value;
            break;
        }
        default:
            if (flags != 0) return CodecStatus::unknown_required_field;
            break;
        }
        if (output) output->push_back({id, static_cast<FieldType>(type), flags != 0, value});
        previous = id;
        offset += size;
    }
    return CodecStatus::ok;
}
} // namespace

bool valid_utf8(std::span<const std::uint8_t> bytes) noexcept {
    std::size_t i = 0;
    while (i < bytes.size()) {
        const auto first = bytes[i++];
        if (first < 0x80) continue;
        unsigned continuation;
        std::uint32_t code, minimum;
        if (first >= 0xc2 && first <= 0xdf) {
            continuation = 1; code = first & 0x1f; minimum = 0x80;
        } else if (first >= 0xe0 && first <= 0xef) {
            continuation = 2; code = first & 0x0f; minimum = 0x800;
        } else if (first >= 0xf0 && first <= 0xf4) {
            continuation = 3; code = first & 0x07; minimum = 0x10000;
        } else return false;
        if (continuation > bytes.size() - i) return false;
        for (unsigned n = 0; n < continuation; ++n) {
            const auto next = bytes[i++];
            if ((next & 0xc0) != 0x80) return false;
            code = (code << 6) | (next & 0x3f);
        }
        if (code < minimum || code > 0x10ffff || (code >= 0xd800 && code <= 0xdfff)) return false;
    }
    return true;
}
CodecStatus encode_envelope(const Envelope& envelope, std::span<const std::uint8_t> payload,
                            Bytes& output) {
    if (payload.size() > max_bytes - header_bytes) return CodecStatus::limit_exceeded;
    const auto status = check_envelope(envelope, payload.size());
    if (status != CodecStatus::ok) return status;
    Bytes candidate(header_bytes + payload.size(), 0);
    const auto bytes = std::span<std::uint8_t>(candidate);
    store(bytes.subspan(0, 4), candidate.size());
    store(bytes.subspan(4, 2), envelope.major); store(bytes.subspan(6, 2), envelope.minor);
    store(bytes.subspan(8, 4), envelope.kind); store(bytes.subspan(12, 4), envelope.flags);
    store(bytes.subspan(16, 8), envelope.generation); store(bytes.subspan(24, 8), envelope.sequence);
    store(bytes.subspan(32, 8), envelope.interface_handle); store(bytes.subspan(40, 4), envelope.operation);
    store(bytes.subspan(44, 4), payload.size()); store(bytes.subspan(48, 4), envelope.service_status);
    store(bytes.subspan(56, 8), envelope.correlation);
    std::copy(payload.begin(), payload.end(), candidate.begin() + header_bytes);
    output.swap(candidate);
    return CodecStatus::ok;
}
CodecStatus decode_envelope(std::span<const std::uint8_t> input, Envelope& output,
                            std::span<const std::uint8_t>& payload) noexcept {
    if (input.size() < header_bytes) return CodecStatus::truncated;
    if (input.size() > max_bytes) return CodecStatus::limit_exceeded;
    if (load(input.first(4)) != input.size() || load(input.subspan(44, 4)) != input.size() - header_bytes ||
        load(input.subspan(52, 4)) != 0) return CodecStatus::invalid_value;
    Envelope candidate;
    candidate.major = static_cast<std::uint16_t>(load(input.subspan(4, 2)));
    candidate.minor = static_cast<std::uint16_t>(load(input.subspan(6, 2)));
    candidate.kind = static_cast<std::uint32_t>(load(input.subspan(8, 4)));
    candidate.flags = static_cast<std::uint32_t>(load(input.subspan(12, 4)));
    candidate.generation = load(input.subspan(16, 8)); candidate.sequence = load(input.subspan(24, 8));
    candidate.interface_handle = load(input.subspan(32, 8));
    candidate.operation = static_cast<std::uint32_t>(load(input.subspan(40, 4)));
    candidate.service_status = static_cast<std::uint32_t>(load(input.subspan(48, 4)));
    candidate.correlation = load(input.subspan(56, 8));
    const auto status = check_envelope(candidate, input.size() - header_bytes);
    if (status != CodecStatus::ok) return status;
    output = candidate;
    payload = input.subspan(header_bytes);
    return CodecStatus::ok;
}
CodecStatus encode_record(std::span<const FieldView> fields, Bytes& output) {
    if (fields.size() > 64) return CodecStatus::limit_exceeded;
    std::size_t total = 0;
    for (const auto& field : fields) {
        if (field.value.size() > max_bytes - 8 || total > max_bytes - 8 - field.value.size())
            return CodecStatus::limit_exceeded;
        total += 8 + field.value.size();
    }
    Bytes candidate(total);
    auto bytes = std::span<std::uint8_t>(candidate);
    std::size_t offset = 0;
    for (const auto& field : fields) {
        store(bytes.subspan(offset, 2), field.id);
        candidate[offset + 2] = static_cast<std::uint8_t>(field.type);
        candidate[offset + 3] = field.must_understand ? 1 : 0;
        store(bytes.subspan(offset + 4, 4), field.value.size());
        std::copy(field.value.begin(), field.value.end(), candidate.begin() + offset + 8);
        offset += 8 + field.value.size();
    }
    const auto status = validate_record(candidate, 1, nullptr);
    if (status != CodecStatus::ok) return status;
    output.swap(candidate);
    return CodecStatus::ok;
}
CodecStatus decode_record(std::span<const std::uint8_t> bytes, std::vector<FieldView>& output) {
    std::vector<FieldView> candidate;
    const auto status = validate_record(bytes, 1, &candidate);
    if (status != CodecStatus::ok) return status;
    output.swap(candidate);
    return CodecStatus::ok;
}
CodecStatus validate_record_bytes(std::span<const std::uint8_t> bytes) noexcept {
    return validate_record(bytes, 1, nullptr);
}
bool read_u32(const FieldView& field, std::uint32_t& value) noexcept {
    if (field.type != FieldType::u32 || field.value.size() != 4) return false;
    value = static_cast<std::uint32_t>(load(field.value)); return true;
}
bool read_u64(const FieldView& field, std::uint64_t& value) noexcept {
    if (field.type != FieldType::u64 || field.value.size() != 8) return false;
    value = load(field.value); return true;
}
Bytes encode_u32(std::uint32_t value) { Bytes output(4); store(output, value); return output; }
Bytes encode_u64(std::uint64_t value) { Bytes output(8); store(output, value); return output; }
GenerationSource::GenerationSource(std::uint64_t first) : next_(first) {
    if (first == 0) exhausted_ = true;
}
std::optional<std::uint64_t> GenerationSource::next() noexcept {
    if (exhausted_) return std::nullopt;
    const auto result = next_;
    if (next_ == std::numeric_limits<std::uint64_t>::max()) exhausted_ = true;
    else ++next_;
    return result;
}
} // namespace foundation::appended
