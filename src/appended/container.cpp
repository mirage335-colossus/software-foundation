#include "foundation/appended/container.hpp"
#include "sha256.hpp"

#include <algorithm>
#include <array>
#include <fstream>
#include <initializer_list>
#include <limits>
#include <set>
#include <type_traits>
#include <utility>
#include <variant>

namespace foundation::appended {
namespace {
[[noreturn]] void fail(const char* message) { throw ContainerError(message); }

std::uint64_t little(std::span<const std::uint8_t> bytes, std::size_t offset,
                     std::size_t width) {
    if (offset > bytes.size() || width > bytes.size() - offset)
        fail("truncated native carrier");
    std::uint64_t value = 0;
    for (std::size_t i = 0; i < width; ++i)
        value |= static_cast<std::uint64_t>(bytes[offset + i]) << (8 * i);
    return value;
}

bool utf8(std::string_view text) noexcept {
    std::size_t i = 0;
    while (i < text.size()) {
        const auto first = static_cast<unsigned char>(text[i++]);
        if (first < 0x80) continue;
        unsigned count = 0;
        std::uint32_t value = 0, minimum = 0;
        if (first >= 0xc2 && first <= 0xdf) { count=1; value=first&31; minimum=0x80; }
        else if (first >= 0xe0 && first <= 0xef) { count=2; value=first&15; minimum=0x800; }
        else if (first >= 0xf0 && first <= 0xf4) { count=3; value=first&7; minimum=0x10000; }
        else return false;
        if (count > text.size() - i) return false;
        for (unsigned j = 0; j < count; ++j) {
            const auto next = static_cast<unsigned char>(text[i++]);
            if ((next & 0xc0) != 0x80) return false;
            value = (value << 6) | (next & 63);
        }
        if (value < minimum || value > 0x10ffff || (value >= 0xd800 && value <= 0xdfff))
            return false;
    }
    return true;
}

void append_utf8(std::string& output, std::uint32_t value) {
    if (value < 0x80) output.push_back(static_cast<char>(value));
    else if (value < 0x800) {
        output.push_back(static_cast<char>(0xc0 | (value >> 6)));
        output.push_back(static_cast<char>(0x80 | (value & 63)));
    } else if (value < 0x10000) {
        output.push_back(static_cast<char>(0xe0 | (value >> 12)));
        output.push_back(static_cast<char>(0x80 | ((value >> 6) & 63)));
        output.push_back(static_cast<char>(0x80 | (value & 63)));
    } else {
        output.push_back(static_cast<char>(0xf0 | (value >> 18)));
        output.push_back(static_cast<char>(0x80 | ((value >> 12) & 63)));
        output.push_back(static_cast<char>(0x80 | ((value >> 6) & 63)));
        output.push_back(static_cast<char>(0x80 | (value & 63)));
    }
}

// The package index is a small integer-only JSON dialect. The parser preserves
// types and rejects duplicate keys before schema interpretation. Comparing its
// canonical encoding also rejects whitespace, alternative escapes and key order.
struct Json {
    using Array = std::vector<Json>;
    using Object = std::vector<std::pair<std::string, Json>>;
    std::variant<std::nullptr_t, bool, std::uint64_t, std::string, Array, Object> value;
};

class JsonParser {
public:
    explicit JsonParser(std::string_view input) : input_(input) {}
    Json parse() {
        auto result = parse_value(0);
        if (position_ != input_.size()) fail("invalid index JSON trailing bytes");
        return result;
    }
private:
    char take() {
        if (position_ == input_.size()) fail("truncated index JSON");
        return input_[position_++];
    }
    bool consume(char value) {
        if (position_ < input_.size() && input_[position_] == value) {
            ++position_;
            return true;
        }
        return false;
    }
    void literal(std::string_view expected) {
        if (input_.substr(position_, expected.size()) != expected) fail("invalid index JSON literal");
        position_ += expected.size();
    }
    unsigned hex4() {
        unsigned result = 0;
        for (unsigned i = 0; i < 4; ++i) {
            const auto ch = take();
            unsigned digit = 0;
            if (ch >= '0' && ch <= '9') digit = static_cast<unsigned>(ch - '0');
            else if (ch >= 'a' && ch <= 'f') digit = static_cast<unsigned>(ch - 'a' + 10);
            else if (ch >= 'A' && ch <= 'F') digit = static_cast<unsigned>(ch - 'A' + 10);
            else fail("invalid index JSON escape");
            result = (result << 4) | digit;
        }
        return result;
    }
    std::string string() {
        if (take() != '"') fail("expected index JSON string");
        std::string output;
        while (true) {
            const auto ch = take();
            if (ch == '"') break;
            if (static_cast<unsigned char>(ch) < 32) fail("control byte in index JSON string");
            if (ch != '\\') { output.push_back(ch); continue; }
            switch (take()) {
            case '"': output.push_back('"'); break;
            case '\\': output.push_back('\\'); break;
            case '/': output.push_back('/'); break;
            case 'b': output.push_back('\b'); break;
            case 'f': output.push_back('\f'); break;
            case 'n': output.push_back('\n'); break;
            case 'r': output.push_back('\r'); break;
            case 't': output.push_back('\t'); break;
            case 'u': {
                auto value = hex4();
                if (value >= 0xd800 && value <= 0xdbff) {
                    if (take() != '\\' || take() != 'u') fail("unpaired index JSON surrogate");
                    const auto low = hex4();
                    if (low < 0xdc00 || low > 0xdfff) fail("unpaired index JSON surrogate");
                    value = 0x10000 + ((value - 0xd800) << 10) + low - 0xdc00;
                } else if (value >= 0xdc00 && value <= 0xdfff) fail("unpaired index JSON surrogate");
                append_utf8(output, value);
                break;
            }
            default: fail("invalid index JSON escape");
            }
        }
        if (!utf8(output)) fail("invalid UTF-8 in index JSON");
        return output;
    }
    Json parse_value(unsigned depth) {
        if (depth > 16) fail("index JSON exceeds depth limit");
        // No valid schema-1 index approaches this count: 4096 file objects and
        // their seven scalar fields account for fewer than 33000 values.
        if (++nodes_ > 100000) fail("index JSON exceeds value limit");
        if (position_ == input_.size()) fail("truncated index JSON");
        switch (input_[position_]) {
        case 'n': literal("null"); return Json{nullptr};
        case 't': literal("true"); return Json{true};
        case 'f': literal("false"); return Json{false};
        case '"': return Json{string()};
        case '[': {
            ++position_;
            Json::Array array;
            if (consume(']')) return Json{std::move(array)};
            do { array.push_back(parse_value(depth + 1)); } while (consume(','));
            if (!consume(']')) fail("invalid index JSON array");
            return Json{std::move(array)};
        }
        case '{': {
            ++position_;
            Json::Object object;
            if (consume('}')) return Json{std::move(object)};
            do {
                auto key = string();
                if (!object.empty() && key <= object.back().first)
                    fail("duplicate or unordered index JSON key");
                if (!consume(':')) fail("invalid index JSON object");
                auto value = parse_value(depth + 1);
                object.emplace_back(std::move(key), std::move(value));
            } while (consume(','));
            if (!consume('}')) fail("invalid index JSON object");
            return Json{std::move(object)};
        }
        default: {
            const auto first = input_[position_];
            if (first < '0' || first > '9') fail("index JSON requires unsigned integers");
            std::uint64_t number = 0;
            do {
                const auto digit = static_cast<unsigned>(input_[position_++] - '0');
                if (number > (std::numeric_limits<std::uint64_t>::max() - digit) / 10)
                    fail("index JSON integer overflow");
                number = number * 10 + digit;
                if (first == '0') break;
            } while (position_ < input_.size() && input_[position_] >= '0' && input_[position_] <= '9');
            return Json{number};
        }
        }
    }
    std::string_view input_;
    std::size_t position_{0}, nodes_{0};
};

void encode_string(std::string_view input, std::string& output) {
    constexpr char hex[] = "0123456789abcdef";
    output.push_back('"');
    for (const auto ch : input) {
        switch (ch) {
        case '"': output += "\\\""; break;
        case '\\': output += "\\\\"; break;
        case '\b': output += "\\b"; break;
        case '\f': output += "\\f"; break;
        case '\n': output += "\\n"; break;
        case '\r': output += "\\r"; break;
        case '\t': output += "\\t"; break;
        default: {
            const auto byte = static_cast<unsigned char>(ch);
            if (byte < 32) {
                output += "\\u00";
                output.push_back(hex[byte >> 4]);
                output.push_back(hex[byte & 15]);
            } else output.push_back(ch);
        }
        }
    }
    output.push_back('"');
}

void encode_json(const Json& input, std::string& output) {
    std::visit([&output](const auto& value) {
        using T = std::decay_t<decltype(value)>;
        if constexpr (std::is_same_v<T, std::nullptr_t>) output += "null";
        else if constexpr (std::is_same_v<T, bool>) output += value ? "true" : "false";
        else if constexpr (std::is_same_v<T, std::uint64_t>) output += std::to_string(value);
        else if constexpr (std::is_same_v<T, std::string>) encode_string(value, output);
        else if constexpr (std::is_same_v<T, Json::Array>) {
            output.push_back('[');
            bool first = true;
            for (const auto& item : value) {
                if (!first) output.push_back(',');
                first = false;
                encode_json(item, output);
            }
            output.push_back(']');
        } else {
            output.push_back('{');
            bool first = true;
            for (const auto& [key, item] : value) {
                if (!first) output.push_back(',');
                first = false;
                encode_string(key, output);
                output.push_back(':');
                encode_json(item, output);
            }
            output.push_back('}');
        }
    }, input.value);
}

template<class T> const T& as(const Json& value) {
    const auto* result = std::get_if<T>(&value.value);
    if (!result) fail("invalid index JSON field type");
    return *result;
}

const Json& field(const Json& object, std::string_view name) {
    const auto& values = as<Json::Object>(object);
    const auto found = std::lower_bound(values.begin(), values.end(), name,
        [](const auto& item, std::string_view key) { return item.first < key; });
    if (found == values.end() || found->first != name) fail("missing package index field");
    return found->second;
}

void fields(const Json& object, std::initializer_list<std::string_view> names) {
    const auto& values = as<Json::Object>(object);
    if (values.size() != names.size()) fail("unexpected package index fields");
    for (const auto name : names) (void)field(object, name);
}

const std::string& text_field(const Json& object, std::string_view name) {
    return as<std::string>(field(object, name));
}
std::uint64_t integer_field(const Json& object, std::string_view name) {
    return as<std::uint64_t>(field(object, name));
}
std::optional<std::string> optional_text(const Json& value) {
    if (std::holds_alternative<std::nullptr_t>(value.value)) return std::nullopt;
    return as<std::string>(value);
}

void digest_text(std::string_view digest) {
    if (digest.size() != 64 || !std::all_of(digest.begin(), digest.end(), [](char ch) {
            return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f'); }))
        fail("invalid package SHA-256 text");
}

void bounded_text(std::string_view value, std::size_t maximum) {
    if (value.empty() || value.size() > maximum ||
        std::any_of(value.begin(), value.end(), [](unsigned char ch) { return ch < 32 || ch == 127; }))
        fail("invalid package metadata text");
}

void name_text(std::string_view value) {
    if (value.empty() || value.size() > 128 ||
        !((value.front() >= 'A' && value.front() <= 'Z') ||
          (value.front() >= 'a' && value.front() <= 'z') ||
          (value.front() >= '0' && value.front() <= '9')) ||
        !std::all_of(value.begin(), value.end(), [](char ch) {
            return (ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z') ||
                   (ch >= '0' && ch <= '9') || ch == '_' || ch == '.' || ch == '-'; }))
        fail("invalid package identity name");
}

void application_id(std::string_view value) {
    const auto lower = [](char ch) { return ch >= 'a' && ch <= 'z'; };
    const auto digit = [](char ch) { return ch >= '0' && ch <= '9'; };
    if (value.empty() || value.size() > 256 || !lower(value.front())) fail("invalid package application id");
    bool separator = false, need_segment = false;
    for (const auto ch : value) {
        if (lower(ch) || digit(ch)) need_segment = false;
        else if ((ch == '.' || ch == '-') && !need_segment) { separator = true; need_segment = true; }
        else fail("invalid package application id");
    }
    if (!separator || need_segment) fail("invalid package application id");
}

void application_version(std::string_view value) {
    if (value.empty() || value.size() > 128) fail("invalid package application version");
    const auto digit = [](char ch) { return ch >= '0' && ch <= '9'; };
    const auto alnum = [digit](char ch) {
        return digit(ch) || (ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z');
    };
    std::size_t position = 0;
    for (unsigned part = 0; part < 3; ++part) {
        const auto start = position;
        while (position < value.size() && digit(value[position])) ++position;
        if (start == position) fail("invalid package application version");
        if (part < 2 && (position == value.size() || value[position++] != '.'))
            fail("invalid package application version");
    }
    const auto suffix = [&] {
        do {
            const auto start = position;
            while (position < value.size() && alnum(value[position])) ++position;
            if (start == position) fail("invalid package application version");
            if (position == value.size() || (value[position] != '.' && value[position] != '-')) break;
            ++position;
        } while (true);
    };
    if (position < value.size() && value[position] == '-') { ++position; suffix(); }
    if (position < value.size() && value[position] == '+') { ++position; suffix(); }
    if (position != value.size()) fail("invalid package application version");
}

std::string path_key(std::string_view path) {
    if (path.empty() || path.size() > 240 || path.front() == '/' || path.back() == '/')
        fail("invalid package resource path");
    unsigned depth = 0;
    std::size_t start = 0;
    std::string folded;
    folded.reserve(path.size());
    for (const auto ch : path) {
        const auto byte = static_cast<unsigned char>(ch);
        if (byte < 32 || byte >= 127 || ch == '%' || ch == '?' || ch == '#' || ch == ':' || ch == '\\' ||
            ch == '<' || ch == '>' || ch == '"' || ch == '|' || ch == '*')
            fail("invalid package resource path");
        folded.push_back(ch >= 'A' && ch <= 'Z' ? static_cast<char>(ch - 'A' + 'a') : ch);
    }
    while (start < path.size()) {
        const auto end = path.find('/', start);
        const auto part = path.substr(start, end == std::string_view::npos ? end : end - start);
        if (part.empty() || part == "." || part == ".." || part.back() == '.' || part.back() == ' ' || ++depth > 16)
            fail("invalid package resource path");
        const auto folded_part = std::string_view(folded).substr(start, part.size());
        const auto base = folded_part.substr(0, folded_part.find('.'));
        if (base == "con" || base == "prn" || base == "aux" || base == "nul" ||
            (base.size() == 4 && (base.starts_with("com") || base.starts_with("lpt")) && base[3] >= '1' && base[3] <= '9'))
            fail("reserved package resource path");
        if (end == std::string_view::npos) break;
        start = end + 1;
    }
    return folded;
}

std::vector<std::string> string_list(const Json& value) {
    const auto& list = as<Json::Array>(value);
    if (list.size() > 4096) fail("package requirements exceed count limit");
    std::vector<std::string> output;
    std::set<std::string> seen;
    for (const auto& item : list) {
        auto entry = as<std::string>(item);
        name_text(entry);
        if ((!output.empty() && entry <= output.back()) || !seen.insert(entry).second)
            fail("duplicate or unordered package requirement");
        output.push_back(std::move(entry));
    }
    return output;
}

PackageComponent component(const Json& value, bool binary) {
    if (binary) fields(value, {"present", "entry", "profile"});
    else fields(value, {"present", "entry"});
    PackageComponent result;
    result.present = as<bool>(field(value, "present"));
    result.entry = optional_text(field(value, "entry"));
    if (binary) result.profile = optional_text(field(value, "profile"));
    if (result.present != result.entry.has_value()) fail("inconsistent package component entry");
    if (result.entry) {
        (void)path_key(*result.entry);
        if (!result.entry->starts_with(binary ? "binary/" : "web/"))
            fail("component entry has wrong path prefix");
    }
    if (binary && (result.present != result.profile.has_value() ||
        (result.profile && *result.profile != "foundation-guest-v1")))
        fail("unsupported package binary profile");
    return result;
}

Package parse_index(std::span<const std::uint8_t> package, std::size_t index_offset) {
    const std::string index(reinterpret_cast<const char*>(package.data() + index_offset),
                            package.size() - index_offset);
    const auto json = JsonParser(index).parse();
    std::string canonical;
    canonical.reserve(index.size());
    encode_json(json, canonical);
    if (canonical != index) fail("noncanonical package index JSON");
    fields(json, {"schema_version", "kind", "application", "components", "requires", "identities", "files"});
    if (integer_field(json, "schema_version") != 1 || text_field(json, "kind") != "foundation-appended-package")
        fail("unsupported package index schema");
    Package result;
    result.index_json = index;
    const auto& application = field(json, "application");
    fields(application, {"id", "name", "version"});
    result.application = {text_field(application, "id"), text_field(application, "name"), text_field(application, "version")};
    application_id(result.application.id);
    bounded_text(result.application.name, 256);
    for (std::size_t i = 0; i + 1 < result.application.name.size(); ++i)
        if (static_cast<unsigned char>(result.application.name[i]) == 0xc2 &&
            static_cast<unsigned char>(result.application.name[i + 1]) >= 0x80 &&
            static_cast<unsigned char>(result.application.name[i + 1]) <= 0x9f)
            fail("invalid package metadata text");
    application_version(result.application.version);
    const auto& components = field(json, "components");
    fields(components, {"web", "binary"});
    result.web = component(field(components, "web"), false);
    result.binary = component(field(components, "binary"), true);
    const auto& requires_value = field(json, "requires");
    fields(requires_value, {"abi", "services", "capabilities"});
    const auto& abi = field(requires_value, "abi");
    fields(abi, {"major", "minor"});
    const auto major = integer_field(abi, "major"), minor = integer_field(abi, "minor");
    if (major == 0 || major > 65535 || minor > 65535) fail("invalid package ABI requirement");
    result.abi_major = static_cast<std::uint32_t>(major);
    result.abi_minor = static_cast<std::uint32_t>(minor);
    result.services = string_list(field(requires_value, "services"));
    result.capabilities = string_list(field(requires_value, "capabilities"));
    const auto& identities = as<Json::Object>(field(json, "identities"));
    if (identities.size() > 128) fail("package identities exceed count limit");
    for (const auto& [name, value] : identities) {
        name_text(name);
        const auto& hash = as<std::string>(value);
        digest_text(hash);
        result.identities.emplace(name, hash);
    }
    const auto& files = as<Json::Array>(field(json, "files"));
    if (files.empty() || files.size() > max_appended_file_count) fail("package files exceed count limit");
    std::uint64_t next_offset = 0;
    std::string previous;
    std::set<std::string> aliases;
    std::size_t web_count = 0, binary_count = 0;
    for (const auto& item : files) {
        fields(item, {"path", "component", "offset", "length", "media_type", "sha256"});
        PackageFile file;
        file.path = text_field(item, "path");
        file.component = text_field(item, "component");
        file.media_type = text_field(item, "media_type");
        file.sha256 = text_field(item, "sha256");
        const auto folded = path_key(file.path);
        if ((!previous.empty() && file.path <= previous) || !aliases.insert(folded).second)
            fail("duplicate, aliased or unordered package path");
        previous = file.path;
        if (file.component == "web" && file.path.starts_with("web/")) ++web_count;
        else if (file.component == "binary" && file.path == "binary/application.wasm") ++binary_count;
        else fail("invalid package file component");
        const auto slash = file.media_type.find('/');
        if (slash == std::string::npos || slash == 0 || slash + 1 == file.media_type.size() ||
            file.media_type.find('/', slash + 1) != std::string::npos ||
            !std::all_of(file.media_type.begin(), file.media_type.end(), [](char ch) {
                return (ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9') ||
                       ch == '.' || ch == '+' || ch == '-' || ch == '/'; }))
            fail("invalid package media type");
        digest_text(file.sha256);
        const auto offset = integer_field(item, "offset"), length = integer_field(item, "length");
        if (offset != next_offset || length > max_appended_file_bytes ||
            offset > index_offset || length > index_offset - offset)
            fail("invalid package file range");
        const auto bytes = package.subspan(static_cast<std::size_t>(offset), static_cast<std::size_t>(length));
        if (detail::hex_digest(detail::sha256(bytes)) != file.sha256) fail("package file SHA-256 mismatch");
        file.data.assign(bytes.begin(), bytes.end());
        result.files.push_back(std::move(file));
        next_offset += length;
    }
    if (next_offset != index_offset) fail("unindexed package data bytes");
    for (const auto& alias : aliases) {
        auto slash = alias.find('/');
        while (slash != std::string::npos) {
            if (aliases.contains(alias.substr(0, slash))) fail("package file/directory alias");
            slash = alias.find('/', slash + 1);
        }
    }
    if (result.web.present != (web_count > 0) || result.binary.present != (binary_count == 1) || binary_count > 1)
        fail("package presence disagrees with files");
    if (result.web.entry) {
        const auto* entry = result.find_file(*result.web.entry);
        if (!entry) fail("missing web entry file");
        if (entry->media_type != "text/html") fail("web entry must be text/html");
        if (!utf8(std::string_view(entry->data.empty() ? "" : reinterpret_cast<const char*>(entry->data.data()), entry->data.size())))
            fail("web entry must be UTF-8");
    }
    if (result.binary.entry && (*result.binary.entry != "binary/application.wasm" || !result.find_file(*result.binary.entry)))
        fail("missing binary entry file");
    if (result.binary.entry && result.find_file(*result.binary.entry)->media_type != "application/wasm")
        fail("binary entry must be application/wasm");
    if (!result.web.present && !result.binary.present) fail("empty appended package");
    return result;
}

template<class Reader>
void validate_carrier(std::uint64_t prefix_size, Reader read, NativeCarrier expected) {
    const auto header = read(0, static_cast<std::size_t>(std::min<std::uint64_t>(prefix_size, 64)));
    if (expected == NativeCarrier::elf) {
        if (header.size() < 52 || header[0] != 0x7f || header[1] != 'E' || header[2] != 'L' || header[3] != 'F' ||
            (header[4] != 1 && header[4] != 2) || (header[5] != 1 && header[5] != 2) || header[6] != 1)
            fail("invalid ELF kernel carrier");
        const bool wide = header[4] == 2, big = header[5] == 2;
        if (wide && header.size() < 64) fail("truncated ELF64 header");
        const auto number = [big](std::span<const std::uint8_t> input, std::size_t offset, std::size_t width) {
            if (!big) return little(input, offset, width);
            if (offset > input.size() || width > input.size() - offset) fail("truncated native carrier");
            std::uint64_t value = 0;
            for (std::size_t i = 0; i < width; ++i) value = (value << 8) | input[offset + i];
            return value;
        };
        const auto type = number(header, 16, 2);
        const auto table_offset = number(header, wide ? 32 : 28, wide ? 8 : 4);
        const auto entry_size = number(header, wide ? 54 : 42, 2);
        const auto count = number(header, wide ? 56 : 44, 2);
        if ((type != 2 && type != 3) || count == 0 || count > 4096 || entry_size != (wide ? 56U : 32U) ||
            table_offset > prefix_size || count * entry_size > prefix_size - table_offset)
            fail("invalid ELF program-header table");
        const auto table = read(table_offset, static_cast<std::size_t>(count * entry_size));
        std::size_t loads = 0;
        for (std::size_t i = 0; i < count; ++i) {
            const auto ph = std::span(table).subspan(i * static_cast<std::size_t>(entry_size), static_cast<std::size_t>(entry_size));
            if (number(ph, 0, 4) != 1) continue;
            ++loads;
            const auto offset = number(ph, wide ? 8 : 4, wide ? 8 : 4);
            const auto length = number(ph, wide ? 32 : 16, wide ? 8 : 4);
            const auto memory_length = number(ph, wide ? 40 : 20, wide ? 8 : 4);
            const auto align = number(ph, wide ? 48 : 28, wide ? 8 : 4);
            if (offset > prefix_size || length > prefix_size - offset || length > memory_length || align > (1U << 30) ||
                (align != 0 && (align & (align - 1)) != 0)) fail("invalid ELF load extent");
            const auto rounding = std::max<std::uint64_t>(4096, align);
            if ((offset + length + rounding - 1) / rounding * rounding > prefix_size)
                fail("ELF kernel lacks finalized load padding");
        }
        if (loads == 0) fail("ELF kernel has no loadable segments");
    } else if (expected == NativeCarrier::pe) {
        if (header.size() < 64 || header[0] != 'M' || header[1] != 'Z') fail("invalid PE kernel carrier");
        const auto pe = little(header, 60, 4);
        if (pe > prefix_size || prefix_size - pe < 24) fail("invalid PE header range");
        const auto fixed = read(pe, 24);
        if (little(fixed, 0, 4) != 0x00004550) fail("invalid PE kernel signature");
        const auto count = little(fixed, 6, 2), optional_size = little(fixed, 20, 2);
        const auto flags = little(fixed, 22, 2);
        if ((flags & 2) == 0 || (flags & 0x2000) != 0 || count == 0 || count > 96 ||
            optional_size < 2 || optional_size > prefix_size - pe - 24)
            fail("invalid PE optional header range");
        const auto optional = read(pe + 24, static_cast<std::size_t>(optional_size));
        const auto magic = little(optional, 0, 2);
        const auto directory = magic == 0x10b ? 96U : magic == 0x20b ? 112U : 0U;
        if (directory == 0 || optional_size < directory) fail("unsupported PE optional header");
        const auto directories = little(optional, directory - 4, 4);
        if (directories > 16 || directories * 8 > optional_size - directory)
            fail("invalid PE data-directory bounds");
        if (directories > 4 && (little(optional, directory + 32, 4) != 0 || little(optional, directory + 36, 4) != 0))
            fail("signed PE kernels are unsupported");
        const auto section_offset = pe + 24 + optional_size;
        if (count * 40 > prefix_size - section_offset) fail("truncated PE section table");
        const auto sections = read(section_offset, static_cast<std::size_t>(count * 40));
        for (std::size_t i = 0; i < count; ++i) {
            const auto offset = little(sections, i * 40 + 20, 4), length = little(sections, i * 40 + 16, 4);
            if (offset > prefix_size || length > prefix_size - offset) fail("invalid PE section extent");
        }
    } else fail("unsupported native carrier");
}

Package parse_suffix(std::span<const std::uint8_t> suffix, std::uint64_t pristine_length,
                     NativeCarrier expected, const detail::Digest& kernel_hash) {
    if (suffix.size() < appended_trailer_bytes) fail("truncated appended trailer");
    const auto trailer = suffix.last(appended_trailer_bytes);
    constexpr std::array<std::uint8_t, 8> magic{'S','F','A','P','N','D','0','1'};
    if (!std::equal(magic.begin(), magic.end(), trailer.begin())) fail("invalid appended trailer magic");
    if (little(trailer, 8, 4) != 1 || little(trailer, 12, 4) != appended_trailer_bytes)
        fail("unsupported appended trailer version");
    if (little(trailer, 16, 8) != pristine_length) fail("appended kernel length mismatch");
    const auto package_size = little(trailer, 24, 8);
    const auto index_offset = little(trailer, 32, 8), index_size = little(trailer, 40, 8);
    if (little(trailer, 48, 8) != static_cast<std::uint64_t>(expected)) fail("appended carrier mismatch");
    if (package_size > max_appended_package_bytes || package_size != suffix.size() - appended_trailer_bytes ||
        index_size == 0 || index_size > max_appended_index_bytes || index_offset > package_size ||
        index_size != package_size - index_offset)
        fail("invalid appended package bounds");
    if (!std::all_of(trailer.begin() + 152, trailer.end(), [](auto byte) { return byte == 0; }))
        fail("nonzero appended trailer reserved bytes");
    if (!std::equal(kernel_hash.begin(), kernel_hash.end(), trailer.begin() + 56))
        fail("appended kernel SHA-256 mismatch");
    const auto package = suffix.first(static_cast<std::size_t>(package_size));
    const auto package_hash = detail::sha256(package);
    if (!std::equal(package_hash.begin(), package_hash.end(), trailer.begin() + 88))
        fail("appended package SHA-256 mismatch");
    const auto index_hash = detail::sha256(package.subspan(static_cast<std::size_t>(index_offset)));
    if (!std::equal(index_hash.begin(), index_hash.end(), trailer.begin() + 120))
        fail("appended index SHA-256 mismatch");
    auto result = parse_index(package, static_cast<std::size_t>(index_offset));
    result.kernel_sha256 = detail::hex_digest(kernel_hash);
    result.package_sha256 = detail::hex_digest(package_hash);
    result.payload_id = detail::hex_digest(index_hash);
    return result;
}

void read_exact(std::ifstream& stream, std::span<std::uint8_t> output) {
    if (output.empty()) return;
    if (!stream.read(reinterpret_cast<char*>(output.data()), static_cast<std::streamsize>(output.size())))
        fail("cannot read complete native artifact");
}
} // namespace

const PackageFile* Package::find_file(std::string_view path) const noexcept {
    const auto found = std::lower_bound(files.begin(), files.end(), path,
        [](const PackageFile& file, std::string_view value) { return file.path < value; });
    return found != files.end() && found->path == path ? &*found : nullptr;
}

Package read_package(std::span<const std::uint8_t> package,
                     std::uint64_t index_offset, std::uint64_t index_length) {
    // Validate by subtraction before any narrowing, subspan, parse or hash.
    // No addition of caller-controlled 64-bit boundaries can wrap here.
    if (package.size() > max_appended_package_bytes || index_length == 0 ||
        index_length > max_appended_index_bytes || index_offset > package.size() ||
        index_length != package.size() - index_offset)
        fail("invalid logical package bounds");
    const auto offset = static_cast<std::size_t>(index_offset);
    auto result = parse_index(package, offset);
    result.payload_id = detail::hex_digest(detail::sha256(package.subspan(offset)));
    result.package_sha256 = detail::hex_digest(detail::sha256(package));
    return result;
}

std::optional<Package> read_native(std::span<const std::uint8_t> artifact,
                                 std::uint64_t pristine_length, NativeCarrier expected_carrier) {
    if (pristine_length == 0 || pristine_length > max_appended_kernel_bytes || pristine_length > artifact.size()) fail("invalid pristine kernel boundary");
    const auto prefix = artifact.first(static_cast<std::size_t>(pristine_length));
    const auto reader = [prefix](std::uint64_t offset, std::size_t length) {
        if (offset > prefix.size() || length > prefix.size() - offset) fail("invalid native header range");
        const auto bytes = prefix.subspan(static_cast<std::size_t>(offset), length);
        return std::vector<std::uint8_t>(bytes.begin(), bytes.end());
    };
    validate_carrier(pristine_length, reader, expected_carrier);
    if (artifact.size() == pristine_length) return std::nullopt;
    const auto suffix = artifact.subspan(static_cast<std::size_t>(pristine_length));
    if (suffix.size() > max_appended_package_bytes + appended_trailer_bytes) fail("appended suffix exceeds size limit");
    return parse_suffix(suffix, pristine_length, expected_carrier, detail::sha256(prefix));
}

std::optional<Package> read_native_file(const std::filesystem::path& artifact,
                                      std::uint64_t pristine_length, NativeCarrier expected_carrier) {
    std::ifstream stream(artifact, std::ios::binary | std::ios::ate);
    if (!stream) fail("cannot open native artifact");
    const auto end = stream.tellg();
    if (end < 0) fail("cannot determine native artifact size");
    const auto size = static_cast<std::uint64_t>(end);
    if (pristine_length == 0 || pristine_length > max_appended_kernel_bytes || pristine_length > size) fail("invalid pristine kernel boundary");
    const auto suffix_size = size - pristine_length;
    if (suffix_size > max_appended_package_bytes + appended_trailer_bytes) fail("appended suffix exceeds size limit");
    stream.seekg(0);
    const auto reader = [&stream, pristine_length](std::uint64_t offset, std::size_t length) {
        if (offset > pristine_length || length > pristine_length - offset) fail("invalid native header range");
        stream.clear();
        stream.seekg(static_cast<std::streamoff>(offset));
        std::vector<std::uint8_t> output(length);
        read_exact(stream, output);
        return output;
    };
    validate_carrier(pristine_length, reader, expected_carrier);
    if (suffix_size == 0) {
        stream.clear();
        stream.seekg(0, std::ios::end);
        if (stream.tellg() != end) fail("native artifact changed during read");
        return std::nullopt;
    }
    stream.clear();
    stream.seekg(0);
    detail::Sha256 hash;
    std::array<std::uint8_t, 65536> block{};
    auto remaining = pristine_length;
    while (remaining > 0) {
        const auto length = static_cast<std::size_t>(std::min<std::uint64_t>(remaining, block.size()));
        read_exact(stream, std::span(block).first(length));
        hash.update(std::span(block).first(length));
        remaining -= length;
    }
    std::vector<std::uint8_t> suffix(static_cast<std::size_t>(suffix_size));
    read_exact(stream, suffix);
    if (stream.peek() != std::char_traits<char>::eof()) fail("native artifact changed during read");
    return parse_suffix(suffix, pristine_length, expected_carrier, hash.finish());
}
} // namespace foundation::appended
