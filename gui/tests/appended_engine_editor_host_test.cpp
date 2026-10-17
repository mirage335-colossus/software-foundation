// SPDX-License-Identifier: CC0-1.0
#include "shared/appended_engine_abi.h"
#include "shared/engine_editor_profile.hpp"
#include "../../src/appended/sha256.hpp"
#include <foundation/appended/container.hpp>
#include <gui/web.hpp>
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <limits>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

// Actual host read-only exports, with separately supplied synthetic compiled
// facts. This fixture is not an admitted SDK, provider or browser runtime.
extern "C" {
std::uint32_t gui_web_engine_bridge_v1();
std::uint32_t gui_web_engine_profile_v1();
std::int32_t gui_web_engine_editor_describe_v1(unsigned char*, std::size_t) noexcept;
std::int32_t gui_web_engine_document_describe_v1(unsigned char*, std::size_t) noexcept;
std::int32_t gui_web_engine_input_describe_v1(unsigned char*, std::size_t) noexcept;
std::int32_t gui_web_engine_dispatch_v1(std::uint32_t, const unsigned char*, std::size_t,
                                     unsigned char*, std::size_t) noexcept;
const char* gui_web_create(const char*);
const char* gui_web_receive(const char*);
void gui_web_destroy();
}
#ifndef FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE
#define FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE 0
#endif
#if FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 3
#include <appended_engine_compiled_editor_profile.hpp>
#elif FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE != 0
#error "This independent editor fixture selects only disabled or editor facts"
#endif

namespace {
using Bytes = std::vector<std::uint8_t>;
using Json = gui::web_detail::Json;
std::size_t assertions{};
void check(bool value, const char* message) {
    ++assertions;
    if (!value) throw std::runtime_error(message);
}
std::string digest(const auto& value) {
    constexpr char digits[] = "0123456789abcdef";
    std::string result;
    for (auto byte : value) { result += digits[byte >> 4]; result += digits[byte & 15]; }
    return result;
}
#if FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 3
Json expected() {
    namespace editor = foundation::appended::engine_editor;
    namespace document = foundation::appended::engine_document;
    const auto& facts = editor::compiled_engine_editor_profile;
    return Json::Object{
        {"schema_version", 1}, {"kind", "foundation-copied-engine-editor-v1"},
        {"target", "browser-wasm32"}, {"binding", "copied-owner-bridge/direct-worker-editor-v1"},
        {"pointer_bits", 32}, {"pthread", false}, {"shared_memory", false},
        {"bridge_abi", 65536}, {"capabilities", "2035"},
        {"contract_sha256", digest(editor::kContractSha256)},
        {"build_sha256", digest(facts.build_sha256)}, {"source_recipe_sha256", digest(facts.source_recipe_sha256)},
        {"provider_abi_major", 1}, {"provider_abi_minor", 1}, {"host_abi_major", 1}, {"host_abi_minor", 0},
        {"editor_profile", std::string(editor::kProfileName)},
        {"base_header_sha256", digest(document::kBaseHeaderSha256)},
        {"document_header_sha256", digest(document::kExtensionHeaderSha256)},
        {"document_contract_sha256", digest(document::kContractSha256)},
        {"document_catalog_sha256", digest(document::kCatalogSha256)},
        {"physical_catalog_sha256", digest(document::kPhysicalCatalogSha256)},
        {"editor_header_sha256", digest(editor::kHeaderSha256)},
        {"editor_catalog_sha256", digest(editor::kCatalogSha256)}, {"editor_schema_sha256", digest(editor::kSchema)},
        {"document_schema_sha256", digest(document::kSchema)}, {"action_ack_schema_sha256", digest(document::kAckSchema)},
        {"viewport_width", 800}, {"viewport_height", 600}, {"surface_protocol_version", 2},
        {"surface_capabilities", "8255"}, {"mouse_input_version", 1}, {"key_mapping_version", 1},
        {"editor_protocol_version", 1}, {"display_scale", 1}, {"editor_query_max_bytes", 236},
        {"editor_reply_capacity", 1048576}, {"editor_command_max_bytes", 1048576}};
}
#endif
void unprepared() {
    std::array<std::uint8_t, FOUNDATION_ENGINE_HEADER_BYTES> request{};
    std::copy_n("FKB1", 4, request.begin());
    const auto put = [&](std::size_t at, std::uint64_t value, unsigned width) {
        for (unsigned n = 0; n < width; ++n) request[at + n] = static_cast<std::uint8_t>(value >> (8 * n));
    };
    put(4, FOUNDATION_ENGINE_RECORD_VERSION, 2);
    put(6, FOUNDATION_ENGINE_PEEK_DOCUMENT_WORK, 2);
    put(8, request.size(), 4); put(16, 11, 8);
    std::array<std::uint8_t, 160> output{}; output.fill(0xa5); const auto original = output;
    check(gui_web_engine_dispatch_v1(FOUNDATION_ENGINE_PEEK_DOCUMENT_WORK, request.data(), request.size(),
        output.data(), output.size()) == FOUNDATION_ENGINE_BAD_RECORD && output == original,
        "read-only facts prepared an Owner or modified a work receipt");
    bool rejected{};
    try { (void)gui_web_create("read-only-editor"); } catch (const std::exception&) { rejected = true; }
    check(rejected, "read-only facts initialized an application");
}
#if FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 3
// Actual host composition with a verified in-memory Package and explicitly
// synthetic copied engine replies. No engine, DSO, SDK or browser is launched.
void ready_editor_composition() {
    using namespace foundation::appended;
    using Span = std::span<const std::uint8_t>;
    const auto bytes = [](std::string_view text) { return Span{reinterpret_cast<const std::uint8_t*>(text.data()), text.size()}; };
    const auto put = [](std::span<std::uint8_t> out, std::size_t at, std::uint64_t value, unsigned width) {
        for (unsigned n = 0; n < width; ++n) out[at + n] = static_cast<std::uint8_t>(value >> (8 * n));
    };
    const auto get = [](Span in, std::size_t at, unsigned width) {
        check(at <= in.size() && width <= in.size() - at, "editor fixture receipt bounds");
        std::uint64_t value{};
        for (unsigned n = 0; n < width; ++n) value |= std::uint64_t(in[at + n]) << (8 * n);
        return value;
    };
    struct Identity { std::uint64_t application{}, document{}, generation{}; };
    const auto request = [&](std::uint32_t operation, Identity id, Span body) {
        Bytes out(72 + body.size()); std::copy_n("FKB1", 4, out.begin());
        put(out, 4, 1, 2); put(out, 6, operation, 2); put(out, 8, out.size(), 4); put(out, 16, 11, 8);
        put(out, 24, id.application, 8); put(out, 32, id.document, 8); put(out, 40, id.generation, 8);
        put(out, 64, body.size(), 4); std::copy(body.begin(), body.end(), out.begin() + 72); return out;
    };
    const auto bridge = [&](std::uint32_t operation, Identity id, Span body) {
        const auto in = request(operation, id, body); Bytes out(8192);
        const auto count = gui_web_engine_dispatch_v1(operation, in.data(), in.size(), out.data(), out.size());
        check(count >= 80 && static_cast<std::size_t>(count) <= out.size(), "editor host rejected copied receipt framing");
        out.resize(static_cast<std::size_t>(count)); return out;
    };
    const auto accepted = [&](Span out) {
        check(get(out, 72, 4) == FOUNDATION_ENGINE_OK && get(out, 76, 4) == 0, "editor host rejected copied startup work");
    };
    const std::string startup = "{\"kind\":\"foundation-appended-startup\",\"primary\":\"web\",\"schema_version\":1}";
    const std::string html = "<!doctype html><title>Editor host fixture</title><input value=\"internal page\">";
    const auto file = [&](std::string_view path, std::string_view mime, std::size_t offset, std::string_view content) {
        return "{\"component\":\"web\",\"length\":" + std::to_string(content.size()) + ",\"media_type\":\"" + std::string(mime) +
            "\",\"offset\":" + std::to_string(offset) + ",\"path\":\"" + std::string(path) + "\",\"sha256\":\"" +
            detail::hex_digest(detail::sha256(bytes(content))) + "\"}";
    };
    const auto index = "{\"application\":{\"id\":\"org.example.editor-host\",\"name\":\"Editor host fixture\",\"version\":\"1.0.0\"},"
        "\"components\":{\"binary\":{\"entry\":null,\"present\":false,\"profile\":null},\"web\":{\"entry\":\"web/index.html\",\"present\":true}},"
        "\"files\":[" + file("web/.foundation/startup-v1.json", "application/json", 0, startup) + "," +
        file("web/index.html", "text/html", startup.size(), html) + "],\"identities\":{},\"kind\":\"foundation-appended-package\","
        "\"requires\":{\"abi\":{\"major\":1,\"minor\":0},\"capabilities\":[\"foundation.startup.v1\"],\"services\":[]},\"schema_version\":1}";
    Bytes suffix(startup.begin(), startup.end()); suffix.insert(suffix.end(), html.begin(), html.end());
    const auto index_offset = suffix.size(); suffix.insert(suffix.end(), index.begin(), index.end());
    const auto package_hash = detail::sha256(suffix), index_hash = detail::sha256(bytes(index));
    const auto prefix_hash = detail::sha256(bytes("synthetic immutable editor kernel"));
    const auto package_size = suffix.size(); suffix.resize(package_size + appended_trailer_bytes);
    auto trailer = std::span(suffix).subspan(package_size); std::copy_n("SFAPND01", 8, trailer.begin());
    put(trailer, 8, 1, 4); put(trailer, 12, appended_trailer_bytes, 4); put(trailer, 16, 4096, 8);
    put(trailer, 24, package_size, 8); put(trailer, 32, index_offset, 8); put(trailer, 40, index.size(), 8); put(trailer, 48, 3, 8);
    std::copy(prefix_hash.begin(), prefix_hash.end(), trailer.begin() + 56);
    std::copy(package_hash.begin(), package_hash.end(), trailer.begin() + 88); std::copy(index_hash.begin(), index_hash.end(), trailer.begin() + 120);
    Bytes body(40); put(body, 0, 4096, 8); std::copy(prefix_hash.begin(), prefix_hash.end(), body.begin() + 8);
    body.insert(body.end(), suffix.begin(), suffix.end()); accepted(bridge(FOUNDATION_ENGINE_CONFIGURE, {}, body));
    bool early_rejected{};
    try { (void)gui_web_create("too-early-editor"); } catch (const std::exception&) { early_rejected = true; }
    check(early_rejected, "editor host created the typed App without a ready engine identity");
    accepted(bridge(FOUNDATION_ENGINE_TURN_ENTER, {}, {}));
    const auto begun = bridge(FOUNDATION_ENGINE_BEGIN_DOCUMENT, {17, 1, 0}, {}); accepted(begun);
    const Identity id{17, 1, get(begun, 40, 8)}; check(id.generation != 0, "editor Owner omitted its real service generation");
    Bytes frame(48 + 800 * 600 * 4); put(frame, 0, 1, 4); put(frame, 4, 800, 4); put(frame, 8, 600, 4); put(frame, 12, 3200, 4);
    put(frame, 24, 800, 4); put(frame, 28, 600, 4); put(frame, 40, 1, 8);
    for (std::size_t n = 48; n < frame.size(); n += 4) { frame[n] = 131; frame[n + 1] = 23; frame[n + 2] = 45; frame[n + 3] = 255; }
    accepted(bridge(FOUNDATION_ENGINE_FRAME_COMMIT, id, frame)); accepted(bridge(FOUNDATION_ENGINE_TURN_LEAVE, {}, {}));
    const auto state = [&](std::string text, bool has_connection = true) {
        const auto marker = text.find("\"rgb\":\""); check(marker != std::string::npos, "editor App did not publish its actual copied bitmap");
        const auto start = marker + 7, end = text.find('"', start);
        check(end != std::string::npos && end - start == 800 * 600 * 4 && text.compare(start, 4, "gxct") == 0,
            "editor App changed its actual copied RGB image");
        text.erase(start, end - start); const auto value = gui::web_detail::Parser(text).parse();
        check(value.at("error").str().empty() && value.at("snapshot").at("title").str() == "Editor host fixture" &&
            value.at("snapshot").at("widgets").array().size() == 1 && value.at("snapshot").at("widgets").array().front().at("kind").number() == static_cast<int>(gui::Kind::bitmap),
            "editor host selected a different App or failed the actual bitmap publication");
        if (has_connection)
            check(value.at("surface").at("version").number() == 2 && value.at("surface").at("profile").str() == "editor_v1",
                "editor host did not select its actual explicit generic editor composition");
        else check(std::holds_alternative<std::nullptr_t>(value.at("surface").value),
            "editor host advertised surface authority before an actual connection");
        return value;
    };
    (void)state(gui_web_create("editor-host"), false);
    std::uint64_t sequence{};
    const auto receive = [&](Json operation) {
        const auto envelope = gui::web_detail::encode(Json::Object{{"epoch", "editor-host"}, {"seq", std::to_string(++sequence)}, {"operation", std::move(operation)}});
        return state(gui_web_receive(envelope.c_str()));
    };
    const auto connected = receive(Json::Object{{"type", "surfaceConnect"}, {"version", 2}, {"profile", "editor_v1"}, {"supported", "8255"}, {"mouseInputVersion", 1}});
    check(connected.at("surface").at("capabilities").at("supported").str() == "8255", "editor host silently selected a legacy capability profile");
    const auto resync = receive(Json::Object{{"type", "editorResync"}});
    check(resync.at("editorReply").at("type").str() == "editorResync" && resync.at("editorReply").at("sequence").str() == "2",
        "actual editor Session did not route its metadata-only App endpoint");
    const auto pending = bridge(FOUNDATION_ENGINE_PEEK_EDITOR_WORK, id, {});
    check(get(pending, 72, 4) == FOUNDATION_ENGINE_EMPTY, "editor metadata ingress synchronously entered provider work");
    gui_web_destroy(); unprepared();
}
#endif
void run(bool valid) {
    Bytes output(4096, 0xa5); const auto original = output;
    check(gui_web_engine_bridge_v1() == 65536, "editor selection changed the copied bridge marker");
#if defined(FOUNDATION_APPENDED_BINARY_CAPABILITY) && FOUNDATION_APPENDED_BINARY_CAPABILITY
    check(gui_web_engine_profile_v1() == 2, "editor selection changed the both component marker");
#else
    check(gui_web_engine_profile_v1() == 1, "editor selection changed the web component marker");
#endif
    check(gui_web_engine_input_describe_v1(output.data(), output.size()) == FOUNDATION_ENGINE_BAD_OPERATION &&
        output == original, "editor host advertised legacy 467 input facts");
    check(gui_web_engine_document_describe_v1(output.data(), output.size()) == FOUNDATION_ENGINE_BAD_OPERATION &&
        output == original, "editor host advertised legacy 1795/2003 document facts");
    const auto count = gui_web_engine_editor_describe_v1(output.data(), output.size());
    if (!valid) {
        check(count == FOUNDATION_ENGINE_BAD_OPERATION && output == original,
            "disabled or invalid editor facts were advertised");
        check(gui_web_engine_editor_describe_v1(nullptr, 0) == FOUNDATION_ENGINE_BAD_OPERATION,
            "disabled facts inferred an editor profile from output arguments");
        unprepared(); return;
    }
#if FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 3
    check(count > 0 && count < 4096, "editor getter omitted bounded raw JSON");
    const std::string description(reinterpret_cast<const char*>(output.data()), static_cast<std::size_t>(count));
    check(description.find('\0') == std::string::npos &&
        std::all_of(output.begin() + count, output.end(), [](auto byte) { return byte == 0xa5; }),
        "editor getter wrote a NUL or crossed its reported byte range");
    const auto parsed = gui::web_detail::Parser(description).parse();
    check(std::get<Json::Object>(parsed.value).size() == 38 &&
        gui::web_detail::encode(parsed) == gui::web_detail::encode(expected()),
        "editor getter differs from the independent 38-field profile contract");
    check(description.find("\"display_scale\":1,") != std::string::npos,
        "editor getter did not encode its fixed display scale as integer 1");
    output = original;
    check(gui_web_engine_editor_describe_v1(output.data(), static_cast<std::size_t>(count) - 1) ==
        FOUNDATION_ENGINE_REPLY_TOO_SMALL && output == original, "short editor getter partially wrote output");
    check(gui_web_engine_editor_describe_v1(output.data(), 0) == FOUNDATION_ENGINE_REPLY_TOO_SMALL && output == original,
        "zero-capacity editor getter changed output");
    check(gui_web_engine_editor_describe_v1(nullptr, static_cast<std::size_t>(count)) == FOUNDATION_ENGINE_BAD_RECORD &&
        gui_web_engine_editor_describe_v1(nullptr, 0) == FOUNDATION_ENGINE_BAD_RECORD,
        "enabled editor getter admitted a null destination");
    auto* overflow = reinterpret_cast<unsigned char*>(std::numeric_limits<std::uintptr_t>::max() - 7);
    check(gui_web_engine_editor_describe_v1(overflow, 16) == FOUNDATION_ENGINE_BAD_RECORD,
        "editor getter admitted a wrapping output span");
    check(gui_web_engine_editor_describe_v1(output.data(), static_cast<std::size_t>(count)) == count &&
        std::equal(description.begin(), description.end(), output.begin()) && output[static_cast<std::size_t>(count)] == 0xa5,
        "exact-capacity editor getter changed facts or its output canary");
    unprepared();
    std::cout << description << '\n';
    ready_editor_composition();
#else
    throw std::runtime_error("disabled fixture cannot expect valid editor facts");
#endif
}
} // namespace
int main(int argc, char** argv) {
    try {
        if (argc != 2 || (std::string_view(argv[1]) != "valid" && std::string_view(argv[1]) != "unavailable"))
            throw std::invalid_argument("expected valid or unavailable fixture mode");
        run(std::string_view(argv[1]) == "valid");
        std::cout << "editor host readonly checks: " << assertions << '\n';
        return 0;
    } catch (const std::exception& error) { gui_web_destroy(); std::cerr << error.what() << '\n'; return 1; }
}
