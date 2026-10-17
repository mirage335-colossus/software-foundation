// SPDX-License-Identifier: CC0-1.0
// Source-only copied bridge codec; no JSC, host imports or provider calls.
#include "BibEngineCopiedRecord.h"
#include <foundation/appended/engine_provider_document_v2.h>

#include <algorithm>
#include <limits>
#include <utility>

namespace bib::copied {
namespace {

using Bytes = std::span<const std::uint8_t>;
using MutableBytes = std::span<std::uint8_t>;

std::uint64_t get(Bytes bytes, std::size_t offset, unsigned count) noexcept {
    std::uint64_t value = 0;
    for (unsigned index = 0; index < count; ++index)
        value |= static_cast<std::uint64_t>(bytes[offset + index]) << (8 * index);
    return value;
}

void put(MutableBytes bytes, std::size_t offset, std::uint64_t value,
    unsigned count) noexcept {
    for (unsigned index = 0; index < count; ++index)
        bytes[offset + index] = static_cast<std::uint8_t>(value >> (8 * index));
}

bool overlap(Bytes input, MutableBytes output) noexcept {
    if (input.empty() || output.empty()) return false;
    const auto left = reinterpret_cast<std::uintptr_t>(input.data());
    const auto right = reinterpret_cast<std::uintptr_t>(output.data());
    // Difference comparisons avoid end-address overflow even for hostile spans.
    return left <= right ? right - left < input.size() : left - right < output.size();
}

bool validRecordFields(const Record& record) noexcept {
    return record.op <= 0xffff && record.worker && record.source <= 2 &&
        (record.body.empty() || record.body.data()) &&
        record.body.size() <= std::numeric_limits<std::uint32_t>::max() - headerBytes;
}

void writeHeader(const Record& record, std::size_t bodyBytes,
    MutableBytes output) noexcept {
    std::fill_n(output.begin(), headerBytes, std::uint8_t{});
    output[0] = 'F'; output[1] = 'K'; output[2] = 'B'; output[3] = '1';
    put(output, 4, 1, 2); put(output, 6, record.op, 2);
    put(output, 8, headerBytes + bodyBytes, 4);
    put(output, 16, record.worker, 8); put(output, 24, record.instance, 8);
    put(output, 32, record.document, 8); put(output, 40, record.generation, 8);
    put(output, 48, record.transfer, 8); put(output, 56, record.source, 4);
    put(output, 64, bodyBytes, 4);
}

int hex(char ch) noexcept {
    if (ch >= '0' && ch <= '9') return ch - '0';
    if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
    if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
    return -1;
}

bool digest(std::string_view text) noexcept {
    bool nonzero = false;
    if (text.size() != 64) return false;
    for (const auto ch : text) {
        if (!((ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f'))) return false;
        nonzero = nonzero || ch != '0';
    }
    return nonzero;
}

bool scalar(Bytes bytes, std::size_t& position, std::uint32_t& value) noexcept {
    if (position == bytes.size()) return false;
    const auto first = bytes[position++];
    value = first;
    if (first < 0x80) return true;
    unsigned following = 0;
    std::uint32_t minimum = 0;
    if (first >= 0xc2 && first <= 0xdf) {
        following = 1; minimum = 0x80; value = first & 0x1f;
    } else if (first >= 0xe0 && first <= 0xef) {
        following = 2; minimum = 0x800; value = first & 0x0f;
    } else if (first >= 0xf0 && first <= 0xf4) {
        following = 3; minimum = 0x10000; value = first & 0x07;
    } else return false;
    if (following > bytes.size() - position) return false;
    for (unsigned index = 0; index < following; ++index) {
        const auto next = bytes[position++];
        if ((next & 0xc0) != 0x80) return false;
        value = (value << 6) | (next & 0x3f);
    }
    return value >= minimum && value <= 0x10ffff &&
        !(value >= 0xd800 && value <= 0xdfff);
}

bool unreserved(unsigned char ch) noexcept {
    return (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') ||
        (ch >= '0' && ch <= '9') || ch == '-' || ch == '.' || ch == '_' || ch == '~';
}

bool equalFold(std::string_view left, std::string_view right) noexcept {
    if (left.size() != right.size()) return false;
    for (std::size_t index = 0; index < left.size(); ++index) {
        const auto ch = left[index];
        const auto folded = ch >= 'A' && ch <= 'Z' ? static_cast<char>(ch - 'A' + 'a') : ch;
        if (folded != right[index]) return false;
    }
    return true;
}

bool dosName(std::string_view segment) noexcept {
    const auto base = segment.substr(0, segment.find('.'));
    if (equalFold(base, "con") || equalFold(base, "prn") ||
        equalFold(base, "aux") || equalFold(base, "nul")) return true;
    if (base.size() < 4 ||
        (!equalFold(base.substr(0, 3), "com") && !equalFold(base.substr(0, 3), "lpt")))
        return false;
    const auto suffix = base.substr(3);
    return (suffix.size() == 1 && suffix[0] >= '1' && suffix[0] <= '9') ||
        suffix == "\xc2\xb9" || suffix == "\xc2\xb2" || suffix == "\xc2\xb3";
}

class StartParser {
public:
    explicit StartParser(Bytes bytes)
        : text_(reinterpret_cast<const char*>(bytes.data()), bytes.size()) { }

    Status parse(Start& output, std::string_view selected = "259", bool* raster = nullptr) {
        skip();
        if (!take('{')) return Status::invalid;
        skip();
        std::uint32_t seen = 0;
        std::string package;
        Start candidate;
        bool rasterValue = true;
        for (unsigned index = 0; index < 7; ++index) {
            std::string key;
            if (!string(key, 21, Status::invalid)) return status_;
            skip();
            if (!take(':')) return Status::invalid;
            skip();
            unsigned field = 7;
            constexpr std::array<std::string_view, 7> keys{
                "raster_output", "width", "height", "entry_url", "package_sha256",
                "required_capabilities", "persistence_seed"};
            for (unsigned item = 0; item < keys.size(); ++item)
                if (key == keys[item]) field = item;
            if (field == 7 || (seen & (1u << field))) return Status::invalid;
            seen |= 1u << field;
            switch (field) {
            case 0:
                if (token("true")) rasterValue = true;
                else if (raster && token("false")) rasterValue = false;
                else return Status::invalid;
                break;
            case 1: if (!token("800")) return Status::invalid; break;
            case 2: if (!token("600")) return Status::invalid; break;
            case 3:
                if (!string(candidate.entry, maxEntryBytes, Status::limit)) return status_;
                break;
            case 4:
                if (!string(package, 64, Status::invalid)) return status_;
                break;
            case 5: {
                std::string capabilities;
                if (!string(capabilities, selected.size(), Status::invalid)) return status_;
                if (capabilities != selected) return Status::invalid;
                break;
            }
            case 6: {
                std::string seed;
                if (!string(seed, 0, Status::invalid)) return status_;
                break;
            }
            default: return Status::invalid;
            }
            skip();
            if (!take(index == 6 ? '}' : ',')) return Status::invalid;
            skip();
        }
        if (seen != 0x7f || position_ != text_.size() || !digest(package) ||
            !validEntryURL(candidate.entry, package)) return Status::invalid;
        for (std::size_t index = 0; index < candidate.packageSHA.size(); ++index)
            candidate.packageSHA[index] = static_cast<std::uint8_t>(
                (hex(package[2 * index]) << 4) | hex(package[2 * index + 1]));
        output = std::move(candidate);
        if (raster) *raster = rasterValue;
        return Status::ok;
    }

private:
    void skip() noexcept {
        while (position_ < text_.size()) {
            const auto ch = text_[position_];
            if (ch != ' ' && ch != '\t' && ch != '\n' && ch != '\r') break;
            ++position_;
        }
    }

    bool take(char ch) noexcept {
        if (position_ == text_.size() || text_[position_] != ch) return false;
        ++position_;
        return true;
    }

    bool token(std::string_view value) noexcept {
        if (!text_.substr(position_).starts_with(value)) return false;
        position_ += value.size();
        return true;
    }

    bool hexQuad(std::uint32_t& value) noexcept {
        if (text_.size() - position_ < 4) return false;
        value = 0;
        for (unsigned index = 0; index < 4; ++index) {
            const auto nibble = hex(text_[position_++]);
            if (nibble < 0) return false;
            value = (value << 4) | static_cast<std::uint32_t>(nibble);
        }
        return true;
    }

    bool append(std::string& output, char ch, std::size_t maximum, Status overflow) {
        if (output.size() == maximum) { status_ = overflow; return false; }
        output.push_back(ch);
        return true;
    }

    bool appendScalar(std::string& output, std::uint32_t value,
        std::size_t maximum, Status overflow) {
        if (!value) return false;
        std::array<char, 4> encoded{};
        std::size_t length = 0;
        if (value < 0x80) encoded[length++] = static_cast<char>(value);
        else if (value < 0x800) {
            encoded[length++] = static_cast<char>(0xc0 | (value >> 6));
            encoded[length++] = static_cast<char>(0x80 | (value & 0x3f));
        } else if (value < 0x10000) {
            encoded[length++] = static_cast<char>(0xe0 | (value >> 12));
            encoded[length++] = static_cast<char>(0x80 | ((value >> 6) & 0x3f));
            encoded[length++] = static_cast<char>(0x80 | (value & 0x3f));
        } else {
            encoded[length++] = static_cast<char>(0xf0 | (value >> 18));
            encoded[length++] = static_cast<char>(0x80 | ((value >> 12) & 0x3f));
            encoded[length++] = static_cast<char>(0x80 | ((value >> 6) & 0x3f));
            encoded[length++] = static_cast<char>(0x80 | (value & 0x3f));
        }
        if (length > maximum - output.size()) { status_ = overflow; return false; }
        output.append(encoded.data(), length);
        return true;
    }

    bool string(std::string& output, std::size_t maximum, Status overflow) {
        if (!take('"')) return false;
        while (position_ < text_.size()) {
            const auto ch = static_cast<unsigned char>(text_[position_++]);
            if (ch == '"') return true;
            if (ch < 0x20) return false;
            if (ch != '\\') {
                if (!append(output, static_cast<char>(ch), maximum, overflow)) return false;
                continue;
            }
            if (position_ == text_.size()) return false;
            const auto escape = text_[position_++];
            char decoded = 0;
            switch (escape) {
            case '"': decoded = '"'; break;
            case '\\': decoded = '\\'; break;
            case '/': decoded = '/'; break;
            case 'b': decoded = '\b'; break;
            case 'f': decoded = '\f'; break;
            case 'n': decoded = '\n'; break;
            case 'r': decoded = '\r'; break;
            case 't': decoded = '\t'; break;
            case 'u': {
                std::uint32_t value = 0;
                if (!hexQuad(value)) return false;
                if (value >= 0xd800 && value <= 0xdbff) {
                    std::uint32_t low = 0;
                    if (!take('\\') || !take('u') || !hexQuad(low) ||
                        low < 0xdc00 || low > 0xdfff) return false;
                    value = 0x10000 + ((value - 0xd800) << 10) + (low - 0xdc00);
                } else if (value >= 0xdc00 && value <= 0xdfff) return false;
                if (!appendScalar(output, value, maximum, overflow)) return false;
                continue;
            }
            default: return false;
            }
            if (!append(output, decoded, maximum, overflow)) return false;
        }
        return false;
    }

    std::string_view text_;
    std::size_t position_{};
    Status status_{Status::invalid};
};

} // namespace

Status readRecord(std::uint32_t expectedOp, Bytes input, Record& output) noexcept {
    if (expectedOp > 0xffff || input.size() < headerBytes || !input.data() ||
        input.size() > std::numeric_limits<std::uint32_t>::max() ||
        input[0] != 'F' || input[1] != 'K' || input[2] != 'B' || input[3] != '1' ||
        get(input, 4, 2) != 1 || get(input, 6, 2) != expectedOp ||
        get(input, 8, 4) != input.size() || get(input, 12, 4) ||
        get(input, 60, 4) || get(input, 68, 4) ||
        get(input, 64, 4) != input.size() - headerBytes ||
        !get(input, 16, 8) || get(input, 56, 4) > 2) return Status::invalid;
    Record candidate{expectedOp, get(input, 16, 8), get(input, 24, 8),
        get(input, 32, 8), get(input, 40, 8), get(input, 48, 8),
        static_cast<std::uint32_t>(get(input, 56, 4)), input.subspan(headerBytes)};
    output = candidate;
    return Status::ok;
}

Status readReceipt(std::uint32_t requestOp, Bytes input, Record& output,
    std::uint32_t& control, std::uint32_t& service) noexcept {
    if (requestOp >= 0x8000 || input.size() < receiptBytes) return Status::invalid;
    Record candidate;
    if (readRecord(requestOp | 0x8000, input, candidate) != Status::ok) return Status::invalid;
    const auto observedControl = static_cast<std::uint32_t>(get(candidate.body, 0, 4));
    const auto observedService = static_cast<std::uint32_t>(get(candidate.body, 4, 4));
    if (observedControl > 8 || observedService > 14) return Status::invalid;
    candidate.op = requestOp;
    candidate.body = candidate.body.subspan(8);
    output = candidate;
    control = observedControl;
    service = observedService;
    return Status::ok;
}

bool validEngineRequest(const Record& record) noexcept {
    if (!validRecordFields(record) || record.op > 8 || record.source ||
        record.body.size() > maxBodyBytes ||
        (record.document && !record.instance) ||
        (record.generation && (!record.instance || !record.document))) return false;
    if (record.op == 0 || record.op == 1) {
        if (record.instance || record.document || record.generation || record.transfer) return false;
        return record.op == 0 ? record.body.empty() : !record.body.empty();
    }
    if (record.op <= 5) return !record.transfer && record.body.empty();
    if (!record.instance || !record.document || !record.generation || !record.transfer) return false;
    if (record.op == 6) return record.body.size() >= 64;
    if (record.op == 7) return record.body.size() == 12 && get(record.body, 0, 8) &&
        get(record.body, 8, 4) <= 14;
    return record.body.empty();
}

std::size_t requiredEngineReplyBytes(std::uint32_t op) noexcept {
    if (op == 0) return receiptBytes + 1024;
    if (op == 1) return receiptBytes + 8;
    if (op <= 5) return receiptBytes;
    if (op <= 8) return receiptBytes + 4;
    return 0;
}

Status writeRecord(const Record& record, MutableBytes output,
    std::size_t& written) noexcept {
    if (!validRecordFields(record) || (!output.empty() && !output.data())) return Status::invalid;
    const auto total = headerBytes + record.body.size();
    if (output.size() < total) return Status::limit;
    if (overlap(record.body, output.first(total))) return Status::invalid;
    writeHeader(record, record.body.size(), output);
    std::copy(record.body.begin(), record.body.end(), output.begin() + headerBytes);
    written = total;
    return Status::ok;
}

Status writeReceipt(const Record& record, std::uint32_t control,
    std::uint32_t service, Bytes body, MutableBytes output,
    std::size_t& written) noexcept {
    if (record.op >= 0x8000 || control > 8 || service > 14 ||
        (!body.empty() && !body.data()) ||
        body.size() > std::numeric_limits<std::uint32_t>::max() - receiptBytes ||
        (!output.empty() && !output.data())) return Status::invalid;
    Record response = record;
    response.op |= 0x8000;
    response.body = body;
    if (!validRecordFields(response)) return Status::invalid;
    const auto total = receiptBytes + body.size();
    if (output.size() < total) return Status::limit;
    if (overlap(body, output.first(total))) return Status::invalid;
    writeHeader(response, body.size() + 8, output);
    put(output, 72, control, 4); put(output, 76, service, 4);
    std::copy(body.begin(), body.end(), output.begin() + receiptBytes);
    written = total;
    return Status::ok;
}

Status writeReply(const Record& record, std::uint32_t control, Bytes body,
    MutableBytes output, std::size_t& written) noexcept {
    return writeReceipt(record, control, 0, body, output, written);
}

bool validUTF8(Bytes input) noexcept {
    if (!input.empty() && !input.data()) return false;
    std::size_t position = 0;
    while (position < input.size()) {
        std::uint32_t value = 0;
        if (!scalar(input, position, value)) return false;
    }
    return true;
}

bool validEntryURL(std::string_view entry, std::string_view packageSHA) noexcept {
    if (entry.size() > maxEntryBytes || !digest(packageSHA) ||
        !entry.starts_with("app://") || entry.size() <= 71 ||
        entry.substr(6, 64) != packageSHA || entry[70] != '/' ||
        entry.find_first_of("?#") != std::string_view::npos) return false;
    const auto encoded = entry.substr(71);
    std::array<std::uint8_t, 240> path{};
    std::size_t length = 0;
    for (std::size_t position = 0; position < encoded.size(); ++position) {
        auto byte = static_cast<unsigned char>(encoded[position]);
        if (byte == '%') {
            if (encoded.size() - position < 3) return false;
            const auto high = hex(encoded[position + 1]);
            const auto low = hex(encoded[position + 2]);
            if (high < 0 || low < 0) return false;
            byte = static_cast<unsigned char>((high << 4) | low);
            if (byte == '/' || byte == '\\' || byte == '%' || unreserved(byte)) return false;
            position += 2;
        } else if (byte == ' ') return false;
        if (length == path.size() || byte == '\\' || byte == ':' || byte == '%' ||
            byte == '?' || byte == '#' || byte == '<' || byte == '>' || byte == '"' ||
            byte == '|' || byte == '*') return false;
        path[length++] = byte;
    }
    const Bytes bytes(path.data(), length);
    std::size_t position = 0;
    while (position < length) {
        std::uint32_t value = 0;
        if (!scalar(bytes, position, value) || value < 0x20 ||
            (value >= 0x7f && value <= 0x9f)) return false;
    }
    const std::string_view text(reinterpret_cast<const char*>(path.data()), length);
    if (!text.starts_with("web/")) return false;
    std::size_t start = 0;
    unsigned depth = 0;
    while (start <= text.size()) {
        const auto end = text.find('/', start);
        const auto segment = text.substr(start, end == std::string_view::npos ? end : end - start);
        if (segment.empty() || segment == "." || segment == ".." ||
            segment.back() == '.' || segment.back() == ' ' || dosName(segment) || ++depth > 16)
            return false;
        if (end == std::string_view::npos) break;
        start = end + 1;
    }
    return true;
}

Status decodeStart(Bytes input, Start& output) noexcept {
    if (input.size() > maxBodyBytes) return Status::limit;
    if (input.empty() || !input.data() || !validUTF8(input)) return Status::invalid;
    try {
        return StartParser(input).parse(output);
    } catch (...) {
        return Status::limit;
    }
}

Status decodeDocumentStart(Bytes input, DocumentStart& output, DocumentWireProfile profile) noexcept {
    if (profile!=DocumentWireProfile::pixel && profile!=DocumentWireProfile::physical) return Status::invalid;
    if (input.size() > maxBodyBytes) return Status::limit;
    if (input.empty() || !input.data() || !validUTF8(input)) return Status::invalid;
    try {
        DocumentStart candidate;
        const auto status=StartParser(input).parse(candidate,profile==DocumentWireProfile::physical?"2003":"1795",&candidate.raster_output);
        if (status==Status::ok) output=std::move(candidate);
        return status;
    } catch (...) { return Status::limit; }
}

Status decodeDocumentOperation(const Record& r, DocumentWireOperation& output, DocumentWireProfile profile) noexcept {
    if (profile!=DocumentWireProfile::pixel && profile!=DocumentWireProfile::physical) return Status::invalid;
    if ((r.op!=4 && r.op!=5) || !validRecordFields(r) || r.source || !r.instance ||
        !r.document || !r.generation || !r.transfer || r.body.size()>maxBodyBytes)
        return Status::invalid;
    const bool query=r.op==5;
    const auto prefix=query?48u:56u;
    if (r.body.size()<prefix || get(r.body,4,4)) return Status::invalid;
    DocumentWireOperation c;
    c.query=query; c.operation=static_cast<std::uint32_t>(get(r.body,0,4));
    c.sequence=query?0:get(r.body,8,8);
    c.capacity=static_cast<std::uint32_t>(get(r.body,query?40:48,4));
    const auto length=get(r.body,query?44:52,4);
    if (length!=r.body.size()-prefix) return Status::invalid;
    std::copy_n(r.body.begin()+(query?8:16),32,c.schema.begin());
    c.payload=r.body.subspan(prefix);
    const auto schemaMatches=[&](std::string_view wanted) noexcept {
        for (std::size_t i=0;i<32;++i)
            if (c.schema[i]!=static_cast<unsigned>((hex(wanted[2*i])<<4)|hex(wanted[2*i+1]))) return false;
        return true;
    };
    if (!query && (c.operation==1 || c.operation==3 || c.operation==5)) {
        c.physical=true;
        const auto schema=c.operation==1?"86b7baad1c95bfb8de3e6b7a9a7c433b528278bbcf84199ca0b2b4ee6134dbc9":
            c.operation==3?"eef60cda2aa7b791641b0e5082d551ec37c10b8d92ca4cc71f13be0af45321d9":
                          "6a15d0e2f814564ce263824dd782335bb327b886e982aefec32476a29b0fd4a3";
        if (profile!=DocumentWireProfile::physical || !c.sequence || c.sequence==UINT64_MAX ||
            c.capacity!=16 || !schemaMatches(schema) ||
            (c.operation==1?(length<33 || length>160):length!=(c.operation==3?32u:80u))) return Status::invalid;
    } else if (!query && c.operation==BIB_ENGINE_COMMAND_ACK_FORM_ACTION_V2) {
        c.metadata_ack=true;
        if (!c.sequence || c.capacity!=16 || length!=8 ||
            !schemaMatches(BIB_ENGINE_DOCUMENT_V2_ACK_SCHEMA_SHA256_HEX)) return Status::invalid;
        const auto original=get(c.payload,0,8);
        if (!original || original==UINT64_MAX || c.sequence<=original) return Status::invalid;
    } else {
        if (c.operation!=(query?BIB_ENGINE_QUERY_DOCUMENT_FORMS_V2:BIB_ENGINE_COMMAND_FORM_ACTION_V2) ||
            c.capacity!=maxBodyBytes || !schemaMatches(BIB_ENGINE_DOCUMENT_V2_SCHEMA_SHA256_HEX) ||
            (query?length!=48:length<81 || length>6246)) return Status::invalid;
        const auto p=c.payload;
        if (get(p,0,4)!=0x3256444e || get(p,4,2)!=2 || p[6]!=(query?1:2) || p[7] ||
            get(p,8,8)!=r.instance || get(p,16,8)!=r.generation || get(p,24,8)!=r.document)
            return Status::invalid;
        const auto sequence=get(p,32,8), nested=get(p,40,8);
        if (!sequence || sequence==UINT64_MAX || (query?!nested:nested!=0 || c.sequence!=sequence))
            return Status::invalid;
        if (query) c.sequence=sequence;
    }
    output=c;
    return Status::ok;
}

bool validDocumentEngineRequest(const Record& r, DocumentWireProfile profile) noexcept {
    if (profile!=DocumentWireProfile::pixel && profile!=DocumentWireProfile::physical) return false;
    if (r.op!=4 && r.op!=5) return validEngineRequest(r);
    DocumentWireOperation operation;
    return decodeDocumentOperation(r,operation,profile)==Status::ok;
}
std::size_t requiredDocumentEngineReplyBytes(const Record& r, DocumentWireProfile profile) noexcept {
    if (!validDocumentEngineRequest(r,profile)) return 0;
    if (r.op==0) return receiptBytes+maxDocumentFactsBytes;
    if (r.op==4 || r.op==5) {
        DocumentWireOperation operation;
        if (decodeDocumentOperation(r,operation,profile)!=Status::ok) return 0;
        return receiptBytes+(operation.query?16:24)+(operation.physical?0:operation.capacity);
    }
    return requiredEngineReplyBytes(r.op);
}

} // namespace bib::copied
