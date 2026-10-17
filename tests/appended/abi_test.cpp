#include "foundation/appended/registry.hpp"

#include <algorithm>
#include <array>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

using namespace foundation::appended;
namespace {
void require(bool ok, const char* message) { if (!ok) throw std::runtime_error(message); }
Bytes hex(std::string_view input) {
    Bytes output;
    auto digit = [](char c) { return c <= '9' ? c - '0' : c - 'a' + 10; };
    for (std::size_t i = 0; i < input.size(); i += 2)
        output.push_back(static_cast<std::uint8_t>((digit(input[i]) << 4) | digit(input[i + 1])));
    return output;
}
void put32(Bytes& output, std::size_t offset, std::uint32_t value) {
    for (unsigned i = 0; i < 4; ++i) output[offset + i] = static_cast<std::uint8_t>(value >> (8 * i));
}
Bytes wrap(Bytes child) {
    Bytes output(8); output[0] = 1; output[2] = FOUNDATION_APPENDED_FIELD_RECORD; output[3] = 1;
    put32(output, 4, static_cast<std::uint32_t>(child.size()));
    output.insert(output.end(), child.begin(), child.end()); return output;
}
}
int main() {
    try {
        Envelope envelope;
        envelope.generation = UINT64_C(0x0102030405060708);
        envelope.sequence = UINT64_C(0x1112131415161718);
        envelope.interface_handle = UINT64_C(0x2122232425262728);
        envelope.operation = 0x31323334;
        const auto golden = hex(
            "4200000001000000010000000000000008070605040302011817161514131211"
            "2827262524232221343332310200000000000000000000000000000000000000aabb");
        const Bytes payload{0xaa, 0xbb};
        Bytes encoded;
        require(encode_envelope(envelope, payload, encoded) == CodecStatus::ok && encoded == golden,
            "envelope golden bytes changed");
        Envelope decoded;
        std::span<const std::uint8_t> decoded_payload;
        require(decode_envelope(golden, decoded, decoded_payload) == CodecStatus::ok &&
            decoded.generation == envelope.generation && decoded.interface_handle == envelope.interface_handle &&
            std::equal(decoded_payload.begin(), decoded_payload.end(), payload.begin(), payload.end()), "envelope decode");
        const auto original = decoded;
        for (std::size_t length = 0; length < 64; ++length)
            require(decode_envelope(std::span(golden).first(length), decoded, decoded_payload) == CodecStatus::truncated,
                "truncated envelope accepted");
        for (const std::size_t offset : {std::size_t(0), std::size_t(12), std::size_t(44), std::size_t(48), std::size_t(52), std::size_t(56)}) {
            auto bad = golden; bad[offset] ^= 1;
            require(decode_envelope(bad, decoded, decoded_payload) == CodecStatus::invalid_value &&
                decoded.generation == original.generation, "invalid envelope changed output");
        }
        auto bad = golden; bad[6] = 1;
        require(decode_envelope(bad, decoded, decoded_payload) == CodecStatus::unsupported_version, "unknown minor accepted");
        envelope.generation = 0; encoded = {42};
        require(encode_envelope(envelope, {}, encoded) == CodecStatus::invalid_value && encoded == Bytes{42},
            "invalid generation accepted or output changed");
        envelope.generation = 1; envelope.sequence = 1;
        Bytes oversized(FOUNDATION_APPENDED_MAX_MESSAGE_BYTES - 63);
        require(encode_envelope(envelope, oversized, encoded) == CodecStatus::limit_exceeded, "message limit not checked");
        encoded = payload;
        require(encode_envelope(envelope, encoded, encoded) == CodecStatus::ok && encoded[64] == 0xaa,
            "aliased envelope output lost input");
        envelope.kind = FOUNDATION_APPENDED_MESSAGE_REPLY;
        envelope.service_status = FOUNDATION_APPENDED_SERVICE_RESULT_AVAILABLE; envelope.correlation = 7;
        require(encode_envelope(envelope, {}, encoded) == CodecStatus::ok, "result reply rejected");
        require(encode_envelope(envelope, payload, encoded) == CodecStatus::invalid_value, "result reply contained payload");
        envelope.service_status = 99;
        require(encode_envelope(envelope, {}, encoded) == CodecStatus::invalid_value, "unknown service status accepted");

        require(valid_utf8(hex("41f09f988065cc81")), "valid astral/combining UTF-8 rejected");
        require(valid_utf8(Bytes{0}), "counted NUL rejected");
        for (const auto* text : {"c080", "eda080", "f4908080", "e282", "80", "f880808080"})
            require(!valid_utf8(hex(text)), "invalid UTF-8 accepted");
        const auto integer = encode_u32(0x12345678);
        const Bytes name{'h', 'i'};
        const std::array fields{FieldView{1, FieldType::u32, true, integer}, FieldView{2, FieldType::utf8, false, name}};
        require(encode_record(fields, encoded) == CodecStatus::ok && encoded == hex("01000101040000007856341202000600020000006869"),
            "record golden bytes changed");
        std::vector<FieldView> record;
        require(decode_record(encoded, record) == CodecStatus::ok && record.size() == 2, "record decode failed");
        std::uint32_t value = 0;
        require(read_u32(record[0], value) && value == 0x12345678 && !read_u32(record[1], value), "typed integer decode");
        auto duplicate = encoded; duplicate[12] = 1;
        require(decode_record(duplicate, record) == CodecStatus::invalid_value && record.size() == 2, "duplicate field accepted");
        bad = encoded; bad[3] = 2;
        require(decode_record(bad, record) == CodecStatus::invalid_value, "reserved field flag accepted");
        bad = hex("0100ff0002000000aabb");
        require(decode_record(bad, record) == CodecStatus::ok && static_cast<unsigned>(record[0].type) == 255,
            "unknown optional field lost");
        bad[3] = 1;
        require(decode_record(bad, record) == CodecStatus::unknown_required_field, "unknown required type accepted");
        for (const auto* text : {"0100010103000000010203", "010005010100000002", "0100060102000000c080",
                                 "0100040108000000010000000000f87f", "010009010400000001000000"})
            require(decode_record(hex(text), record) != CodecStatus::ok, "malformed typed field accepted");
        require(decode_record(hex("0100040108000000000000000000f87f"), record) == CodecStatus::ok,
            "canonical NaN rejected");
        require(decode_record(hex("01000901080000000100000000000000"), record) == CodecStatus::ok,
            "record list rejected");
        Bytes nested;
        for (unsigned depth = 1; depth < 8; ++depth) nested = wrap(std::move(nested));
        require(decode_record(nested, record) == CodecStatus::ok, "maximum nesting rejected");
        nested = wrap(std::move(nested));
        require(decode_record(nested, record) == CodecStatus::limit_exceeded, "nesting overflow accepted");
        GenerationSource generations(std::numeric_limits<std::uint64_t>::max());
        require(generations.next() == std::numeric_limits<std::uint64_t>::max() && !generations.next(), "generation wrapped");
        GenerationSource invalid(0); require(!invalid.next(), "zero generation issued");
        Bytes context;
        require(encode_init_context(7, Limits{}, context) == CodecStatus::ok &&
            decode_record(context, record) == CodecStatus::ok && record.size() == 8, "initialization context malformed");
        std::uint64_t generation = 0;
        require(read_u64(record[0], generation) && generation == 7 && record[4].value.size() == 32 &&
            std::equal(record[4].value.begin(), record[4].value.end(), bootstrap_schema().begin()), "initialization bootstrap identity");
        std::cout << "appended ABI codec contract passed\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
