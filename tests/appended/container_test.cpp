#include "foundation/appended/container.hpp"
#include "../../src/appended/sha256.hpp"

#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <span>
#include <string>
#include <vector>

namespace {
using namespace foundation::appended;
using Bytes = std::vector<std::uint8_t>;

void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
template<class Function> void rejects(Function function) {
    try { function(); }
    catch (const ContainerError& error) {
        require(std::string_view(error.what()).size() > 0, "empty container error");
        return;
    }
    throw std::runtime_error("expected container rejection");
}
Bytes bytes(std::string_view input) { return Bytes(input.begin(), input.end()); }
std::string hash(std::string_view input) { return detail::hex_digest(detail::sha256(bytes(input))); }
void write_number(Bytes& output, std::size_t offset, std::uint64_t value,
                  std::size_t width, bool big = false) {
    require(offset <= output.size() && width <= output.size() - offset, "fixture numeric bounds");
    for (std::size_t i = 0; i < width; ++i)
        output[offset + i] = static_cast<std::uint8_t>(value >> ((big ? width - 1 - i : i) * 8));
}
Bytes elf(bool wide = true, bool big = false) {
    Bytes output(4096);
    output[0]=0x7f; output[1]='E'; output[2]='L'; output[3]='F';
    output[4]=wide ? 2 : 1; output[5]=big ? 2 : 1; output[6]=1;
    write_number(output, 16, 2, 2, big);
    write_number(output, 18, wide ? 62 : 3, 2, big);
    write_number(output, 20, 1, 4, big);
    write_number(output, wide ? 32 : 28, wide ? 64 : 52, wide ? 8 : 4, big);
    write_number(output, wide ? 52 : 40, wide ? 64 : 52, 2, big);
    write_number(output, wide ? 54 : 42, wide ? 56 : 32, 2, big);
    write_number(output, wide ? 56 : 44, 1, 2, big);
    const auto ph = wide ? 64U : 52U;
    write_number(output, ph, 1, 4, big);
    write_number(output, ph + (wide ? 32 : 16), 128, wide ? 8 : 4, big);
    write_number(output, ph + (wide ? 40 : 20), 128, wide ? 8 : 4, big);
    write_number(output, ph + (wide ? 48 : 28), 4096, wide ? 8 : 4, big);
    const std::string fake = "SFAPND01";
    std::copy(fake.begin(), fake.end(), output.begin() + 512);
    return output;
}
Bytes pe(bool wide = false) {
    Bytes output(512);
    output[0]='M'; output[1]='Z';
    write_number(output, 60, 64, 4);
    write_number(output, 64, 0x00004550, 4);
    write_number(output, 68, wide ? 0x8664 : 0x14c, 2);
    write_number(output, 70, 1, 2);
    const auto optional_size = wide ? 240U : 224U;
    write_number(output, 84, optional_size, 2);
    write_number(output, 86, 2, 2);
    write_number(output, 88, wide ? 0x20b : 0x10b, 2);
    write_number(output, 88 + (wide ? 108 : 92), 16, 4);
    write_number(output, 88 + optional_size + 16, 32, 4);
    write_number(output, 88 + optional_size + 20, 384, 4);
    return output;
}

const std::string html = "<p>h\xc3\xa9llo</p>";
std::string entry(std::string_view path, std::uint64_t offset, std::string_view content,
                  std::string_view component = "web", std::string_view media = "text/html") {
    return "{\"component\":\"" + std::string(component) + "\",\"length\":" + std::to_string(content.size()) +
        ",\"media_type\":\"" + std::string(media) + "\",\"offset\":" + std::to_string(offset) +
        ",\"path\":\"" + std::string(path) + "\",\"sha256\":\"" + hash(content) + "\"}";
}
std::string index(std::string files = {}, std::string components = {}) {
    if (files.empty()) files = entry("web/index.html", 0, html);
    if (components.empty()) components = "{\"binary\":{\"entry\":null,\"present\":false,\"profile\":null},\"web\":{\"entry\":\"web/index.html\",\"present\":true}}";
    return "{\"application\":{\"id\":\"fixture.app\",\"name\":\"Caf\xc3\xa9 \xf0\x9f\x98\x80\",\"version\":\"1.0.0\"},\"components\":" + components +
        ",\"files\":[" + files + "],\"identities\":{},\"kind\":\"foundation-appended-package\","
        "\"requires\":{\"abi\":{\"major\":1,\"minor\":0},\"capabilities\":[],\"services\":[]},\"schema_version\":1}";
}
std::string replace(std::string source, std::string_view before, std::string_view after) {
    const auto position = source.find(before);
    require(position != std::string::npos, "fixture replacement not found");
    source.replace(position, before.size(), after);
    return source;
}
Bytes package_bytes(std::string_view data, std::string_view json) {
    auto output = bytes(data); output.insert(output.end(),json.begin(),json.end()); return output;
}
Package logical_package(std::string_view data, std::string_view json) {
    const auto encoded = package_bytes(data,json);
    return read_package(encoded,data.size(),json.size());
}
Bytes compose(const Bytes& prefix, std::string_view data, std::string_view json,
              NativeCarrier carrier = NativeCarrier::elf) {
    auto output = prefix;
    output.insert(output.end(), data.begin(), data.end());
    output.insert(output.end(), json.begin(), json.end());
    const auto start = output.size();
    output.resize(start + appended_trailer_bytes);
    const std::string magic = "SFAPND01";
    std::copy(magic.begin(), magic.end(), output.begin() + static_cast<std::ptrdiff_t>(start));
    write_number(output, start + 8, 1, 4);
    write_number(output, start + 12, appended_trailer_bytes, 4);
    write_number(output, start + 16, prefix.size(), 8);
    write_number(output, start + 24, data.size() + json.size(), 8);
    write_number(output, start + 32, data.size(), 8);
    write_number(output, start + 40, json.size(), 8);
    write_number(output, start + 48, static_cast<std::uint64_t>(carrier), 8);
    const auto kernel_hash = detail::sha256(prefix);
    const auto package_hash = detail::sha256(std::span(output).subspan(prefix.size(), start - prefix.size()));
    const auto index_hash = detail::sha256(bytes(json));
    std::copy(kernel_hash.begin(), kernel_hash.end(), output.begin() + static_cast<std::ptrdiff_t>(start + 56));
    std::copy(package_hash.begin(), package_hash.end(), output.begin() + static_cast<std::ptrdiff_t>(start + 88));
    std::copy(index_hash.begin(), index_hash.end(), output.begin() + static_cast<std::ptrdiff_t>(start + 120));
    return output;
}

void sha_vectors() {
    require(hash("") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "SHA-256 empty vector");
    require(hash("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", "SHA-256 abc vector");
    const std::string message = "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq";
    require(hash(message) == "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1", "SHA-256 multi-block vector");
    const auto million = bytes(std::string(1000000, 'a'));
    detail::Sha256 incremental;
    for (std::size_t i = 0; i < million.size(); i += 17)
        incremental.update(std::span(million).subspan(i, std::min<std::size_t>(17, million.size() - i)));
    require(detail::hex_digest(incremental.finish()) == "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0", "SHA-256 million incremental vector");
}

void package_contract() {
    const auto prefix = elf();
    const auto json = index();
    auto artifact = compose(prefix, html, json);
    auto package = read_native(artifact, prefix.size(), NativeCarrier::elf);
    require(package.has_value() && package->web.present && !package->binary.present, "web presence");
    require(package->application.name == "Caf\xc3\xa9 \xf0\x9f\x98\x80", "UTF-8 metadata changed");
    require(package->index_json == json && package->files.size() == 1, "index changed");
    // Independent Python canonical-json/hash fixture, not the C++ encoder.
    require(package->payload_id == "c357f33763953522a9315df7c6b6339c591f5f8f3fc84c9759b28d4d107cbbce", "canonical index golden identity");
    require(package->package_sha256 == "cfc02f5256689442541558445601270aacee9e6f1ae022061f387b9bff62618b", "logical package golden identity");
    require(package->find_file("web/index.html") && !package->find_file("web/missing"), "virtual file lookup");
    require(package->find_file("web/index.html")->data == bytes(html), "file bytes changed");
    auto logical_source = package_bytes(html,json);
    const auto logical = read_package(logical_source,html.size(),json.size());
    require(logical.web.present && !logical.binary.present && logical.application.id == package->application.id &&
        logical.application.name == package->application.name && logical.application.version == package->application.version &&
        logical.index_json == json && logical.files.size() == 1 && logical.abi_major == 1 && logical.abi_minor == 0,
        "logical package metadata disagrees with native package");
    require(logical.payload_id == "c357f33763953522a9315df7c6b6339c591f5f8f3fc84c9759b28d4d107cbbce" &&
        logical.package_sha256 == "cfc02f5256689442541558445601270aacee9e6f1ae022061f387b9bff62618b" &&
        logical.kernel_sha256.empty(), "logical package golden identity or invented kernel identity");
    require(logical.find_file("web/index.html") && !logical.find_file("web/missing") &&
        logical.find_file("web/index.html")->data == bytes(html) &&
        logical.find_file("web/index.html")->sha256 == hash(html), "logical package file lookup/identity");
    std::fill(logical_source.begin(),logical_source.end(),0);
    require(logical.index_json == json && logical.application.name == "Caf\xc3\xa9 \xf0\x9f\x98\x80" &&
        logical.find_file("web/index.html")->path == "web/index.html" &&
        logical.find_file("web/index.html")->data == bytes(html), "logical package borrows caller storage");
    const auto requirements_json = replace(replace(replace(json,
        "\"capabilities\":[]","\"capabilities\":[\"foundation.example\"]"),
        "\"services\":[]","\"services\":[\"org.example.echo\"]"),
        "\"identities\":{}","\"identities\":{\"fixture\":\"" + hash(html) + "\"}");
    const auto requirements = logical_package(html,requirements_json);
    require(read_native(compose(prefix,html,requirements_json),prefix.size(),NativeCarrier::elf).has_value() &&
        requirements.capabilities == std::vector<std::string>{"foundation.example"} &&
        requirements.services == std::vector<std::string>{"org.example.echo"} &&
        requirements.identities.contains("fixture") && requirements.identities.at("fixture") == hash(html),
        "logical package discarded required services, capabilities or identities");
    std::fill(artifact.begin(), artifact.end(), 0);
    require(package->find_file("web/index.html")->data == bytes(html), "package borrows artifact memory");
    require(!read_native(prefix, prefix.size(), NativeCarrier::elf), "pristine should be absent");
    for (const bool wide : {false, true}) for (const bool big : {false, true}) {
        const auto other = elf(wide, big);
        require(read_native(compose(other, html, json), other.size(), NativeCarrier::elf).has_value(), "ELF class/endian");
    }
    for (const bool wide : {false, true}) {
        const auto other = pe(wide);
        require(read_native(compose(other, html, json, NativeCarrier::pe), other.size(), NativeCarrier::pe).has_value(), "PE class");
    }
    auto malformed = compose(prefix, html, json);
    for (std::size_t cut = 1; cut <= appended_trailer_bytes + html.size(); ++cut)
        rejects([&] { (void)read_native(std::span(malformed).first(malformed.size() - cut), prefix.size(), NativeCarrier::elf); });
    malformed.push_back(0);
    rejects([&] { (void)read_native(malformed, prefix.size(), NativeCarrier::elf); });
    rejects([&] { (void)read_native(prefix, prefix.size() + 1, NativeCarrier::elf); });
    rejects([&] { (void)read_native(prefix, 0, NativeCarrier::elf); });
    rejects([&] { (void)read_native(prefix, prefix.size(), NativeCarrier::pe); });
    for (const std::size_t offset : {0U, 8U, 12U, 16U, 24U, 32U, 40U, 48U, 56U, 88U, 120U, 152U, 191U}) {
        malformed = compose(prefix, html, json);
        malformed[malformed.size() - appended_trailer_bytes + offset] ^= 0x80;
        rejects([&] { (void)read_native(malformed, prefix.size(), NativeCarrier::elf); });
    }
    malformed = compose(prefix, html, json);
    malformed[1000] ^= 1;
    rejects([&] { (void)read_native(malformed, prefix.size(), NativeCarrier::elf); });
    malformed = compose(prefix, html, json);
    malformed[prefix.size()] ^= 1;
    rejects([&] { (void)read_native(malformed, prefix.size(), NativeCarrier::elf); });
    malformed = compose(prefix, html, json);
    write_number(malformed, malformed.size() - appended_trailer_bytes + 24, UINT64_MAX, 8);
    rejects([&] { (void)read_native(malformed, prefix.size(), NativeCarrier::elf); });

    const auto reject_json = [&](std::string_view changed, std::string_view data = html) {
        rejects([&] { (void)read_native(compose(prefix, data, changed), prefix.size(), NativeCarrier::elf); });
        rejects([&] { (void)logical_package(data,changed); });
    };
    reject_json(" " + json);
    reject_json(json + "\n");
    reject_json(replace(json, "\"schema_version\":1", "\"schema_version\":true"));
    reject_json(replace(json, "\"schema_version\":1", "\"schema_version\":1.0"));
    reject_json(replace(json, "\"schema_version\":1", "\"schema_version\":01"));
    reject_json(replace(json, "\"schema_version\":1", "\"schema_version\":18446744073709551616"));
    reject_json(replace(json, "\"schema_version\":1", "\"schema_version\":1,\"schema_version\":1"));
    reject_json(replace(json, "\"id\":\"fixture.app\"", "\"id\":\"fixture app\""));
    reject_json(replace(json, "\"id\":\"fixture.app\"", "\"id\":\"Fixture.app\""));
    reject_json(replace(json, "\"version\":\"1.0.0\"", "\"version\":\"1.0\""));
    const auto metadata_version = replace(json, "\"version\":\"1.0.0\"", "\"version\":\"1.2.3-rc.1+build-x\"");
    require(read_native(compose(prefix,html,metadata_version),prefix.size(),NativeCarrier::elf).has_value() &&
        logical_package(html,metadata_version).application.version == "1.2.3-rc.1+build-x", "build metadata version rejected");
    reject_json(replace(json, "Caf\xc3\xa9", "Caf\\u00e9"));
    reject_json(replace(json, "Caf\xc3\xa9", "Caf\\ud800"));
    reject_json(replace(json, "Caf\xc3\xa9", "Caf\\ud83d\\ude00"));
    reject_json(replace(json, "Caf\xc3\xa9", std::string("Caf\xc0\x80", 5)));
    reject_json(replace(json, "\"offset\":0", "\"offset\":true"));
    reject_json(replace(json, "\"offset\":0", "\"offset\":1"));
    reject_json(replace(json, "\"offset\":0", "\"offset\":-1"));
    reject_json(replace(json, "\"length\":" + std::to_string(html.size()), "\"length\":67108865"));
    reject_json(replace(json, hash(html), std::string(64, '0')));
    reject_json(replace(json, "\"present\":true", "\"present\":false"));
    reject_json(replace(json, "\"present\":false", "\"present\":0"));
    reject_json(replace(json, "text/html", "application/octet-stream"));
    reject_json(replace(json, "\"services\":[]", "\"services\":[\"z\",\"a\"]"));
    reject_json(replace(json, "\"services\":[]", "\"services\":[\"a\",\"a\"]"));
    reject_json(replace(json, "\"identities\":{}", "\"identities\":{\"bad name\":\"" + std::string(64, '0') + "\"}"));
    reject_json(index(entry("web/index.html", 0, html) + "," + entry("web/Index.html", html.size(), "")));
    reject_json(index(entry("web/Index.html", 0, html) + "," + entry("web/index.html", html.size(), "")));
    reject_json(index(entry("web/index.html", 0, html) + "," + entry("web/index.html/child", html.size(), "")));
    for (const auto path : {"/web/index.html", "web/../index.html", "web//index.html", "web/index.html/", "web/CON.html",
                            "web/com1", "web/trailing.", "web/trailing ", "web/%41", "web/a?b", "web/a#b", "web/a:b", "web/a<b", "web/a>b", "web/a|b", "web/a*b", "web/\xc3\xa9.html"})
        reject_json(index(entry(path, 0, html)));
    reject_json(json, html + "x");
    const auto zero_json = index(entry("web/index.html", 0, ""));
    require(read_native(compose(prefix, "", zero_json), prefix.size(), NativeCarrier::elf)->files[0].data.empty(), "empty file rejected");
    require(logical_package("",zero_json).files[0].data.empty(),"logical empty file at zero index offset rejected");
    const std::string module("\0asm\1\0\0\0", 8);
    const auto both_components = "{\"binary\":{\"entry\":\"binary/application.wasm\",\"present\":true,\"profile\":\"foundation-guest-v1\"},"
        "\"web\":{\"entry\":\"web/index.html\",\"present\":true}}";
    const auto both_index = index(entry("binary/application.wasm", 0, module, "binary", "application/wasm") + "," +
        entry("web/index.html", module.size(), html), both_components);
    const auto both = read_native(compose(prefix, module + html, both_index), prefix.size(), NativeCarrier::elf);
    require(both && both->binary.present && both->web.present && both->find_file("binary/application.wasm")->data == bytes(module), "combined exact module bytes");
    const auto both_logical = logical_package(module + html,both_index);
    require(both_logical.binary.present && both_logical.web.present &&
        both_logical.find_file("binary/application.wasm") && both_logical.find_file("web/index.html") &&
        both_logical.find_file("binary/application.wasm")->data == bytes(module) &&
        both_logical.find_file("web/index.html")->data == bytes(html) &&
        both_logical.package_sha256 == both->package_sha256 && both_logical.payload_id == both->payload_id &&
        both_logical.kernel_sha256.empty(),"logical combined component bytes or identities disagree with native");
    reject_json(replace(both_index, "foundation-guest-v1", "unsupported"), module + html);

    auto broken_elf = prefix;
    write_number(broken_elf, 56, 0, 2);
    rejects([&] { (void)read_native(broken_elf, broken_elf.size(), NativeCarrier::elf); });
    broken_elf = prefix;
    write_number(broken_elf, 64 + 32, prefix.size() + 1, 8);
    rejects([&] { (void)read_native(broken_elf, broken_elf.size(), NativeCarrier::elf); });
    broken_elf = prefix;
    broken_elf.pop_back();
    rejects([&] { (void)read_native(broken_elf, broken_elf.size(), NativeCarrier::elf); });
    auto broken_pe = pe();
    write_number(broken_pe, 88 + 96 + 32, 400, 4);
    rejects([&] { (void)read_native(broken_pe, broken_pe.size(), NativeCarrier::pe); });
    broken_pe = pe();
    write_number(broken_pe, 86, 0x2002, 2);
    rejects([&] { (void)read_native(broken_pe, broken_pe.size(), NativeCarrier::pe); });
    broken_pe = pe();
    write_number(broken_pe, 60, UINT32_MAX, 4);
    rejects([&] { (void)read_native(broken_pe, broken_pe.size(), NativeCarrier::pe); });
}

void logical_package_boundaries() {
    const auto json = index();
    const auto encoded = package_bytes(html,json);
    const auto offset = static_cast<std::uint64_t>(html.size()), length = static_cast<std::uint64_t>(json.size());
    rejects([&] { (void)read_package({},0,0); });
    rejects([&] { (void)read_package(encoded,offset,0); });
    rejects([&] { (void)read_package(encoded,encoded.size() + 1,1); });
    rejects([&] { (void)read_package(encoded,UINT64_MAX,1); });
    rejects([&] { (void)read_package(encoded,1,UINT64_MAX); });
    rejects([&] { (void)read_package(encoded,UINT64_MAX,UINT64_MAX); });
    rejects([&] { (void)read_package(encoded,offset,length - 1); });
    rejects([&] { (void)read_package(encoded,offset,length + 1); });
    rejects([&] { (void)read_package(encoded,offset + 1,length); });
    rejects([&] { (void)read_package(encoded,max_appended_package_bytes + 1,length); });
    rejects([&] { (void)read_package(encoded,offset,max_appended_index_bytes + 1); });
    for (const auto cut : {std::size_t{1},json.size(),json.size() + 1})
        rejects([&] { (void)read_package(std::span(encoded).first(encoded.size() - cut),offset,length); });
    for (const std::size_t cut : {1U,2U})
        rejects([&] { (void)read_package(std::span(encoded).first(encoded.size() - cut),offset,length - cut); });
    auto corrupted = encoded; corrupted[0] ^= 1;
    rejects([&] { (void)read_package(corrupted,offset,length); });
    auto trailing = encoded; trailing.push_back(0);
    rejects([&] { (void)read_package(trailing,offset,length); });
    rejects([&] { (void)read_package(trailing,offset,length + 1); });
    const auto prefix = elf(); const auto native = compose(prefix,html,json);
    rejects([&] { (void)read_package(native,prefix.size() + offset,length); });
    rejects([&] { (void)read_package(native,prefix.size() + offset,length + appended_trailer_bytes); });
    rejects([&] { (void)read_package(std::span(native).first(native.size() - appended_trailer_bytes),
        prefix.size() + offset,length); });
    require(read_package(encoded,offset,length).index_json == json,"boundary rejections changed a valid logical package");
}

void file_contract() {
    const auto seed = std::chrono::steady_clock::now().time_since_epoch().count();
    std::filesystem::path directory;
    for (unsigned attempt = 0; attempt < 100; ++attempt) {
        auto candidate = std::filesystem::temp_directory_path() /
            ("foundation-container-" + std::to_string(seed) + "-" + std::to_string(attempt));
        if (std::filesystem::create_directory(candidate)) { directory = std::move(candidate); break; }
    }
    require(!directory.empty(), "cannot create test directory");
    struct Cleanup { std::filesystem::path path; ~Cleanup() { std::error_code error; std::filesystem::remove_all(path, error); } } cleanup{directory};
    const auto file = directory / "kernel";
    for (const auto carrier : {NativeCarrier::elf, NativeCarrier::pe}) {
        const auto prefix = carrier == NativeCarrier::elf ? elf() : pe();
        const auto composed = compose(prefix, html, index(), carrier);
        { std::ofstream output(file, std::ios::binary); output.write(reinterpret_cast<const char*>(composed.data()), static_cast<std::streamsize>(composed.size())); }
        const auto parsed = read_native_file(file, prefix.size(), carrier);
        require(parsed && parsed->find_file("web/index.html")->data == bytes(html), "file reader package");
        { std::ofstream output(file, std::ios::binary); output.write(reinterpret_cast<const char*>(prefix.data()), static_cast<std::streamsize>(prefix.size())); }
        require(!read_native_file(file, prefix.size(), carrier), "file reader pristine");
    }
    rejects([&] { (void)read_native_file(directory / "missing", 1, NativeCarrier::elf); });
}
} // namespace

int main() {
    try {
        sha_vectors();
        package_contract();
        logical_package_boundaries();
        file_contract();
        std::cout << "appended logical/native container contract passed\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
