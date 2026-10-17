// SPDX-License-Identifier: CC0-1.0
#include "shared/appended_engine_abi.h"
#include "shared/appended_engine_input_codec.hpp"
#include "shared/engine_document_profile.hpp"
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

// Native source fixture only: actual host, Package, Owner, bitmap App and
// Browser composition; synthetic compiled facts and copied engine responses.
// This is not an admitted provider, SDK, browser or engine-runtime receipt.
extern "C" {
std::uint32_t gui_web_engine_bridge_v1();
std::uint32_t gui_web_engine_profile_v1();
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

namespace {
using namespace foundation::appended;
namespace doc = engine_document;
namespace input = engine_input;
using Span = std::span<const std::uint8_t>;
using Bytes = std::vector<std::uint8_t>;
using Json = gui::web_detail::Json;
std::size_t assertions{};
void check(bool value, const char* reason) { ++assertions; if (!value) throw std::runtime_error(reason); }
void put(std::span<std::uint8_t> out, std::size_t at, std::uint64_t value, unsigned width) {
    for (unsigned n = 0; n < width; ++n) out[at + n] = static_cast<std::uint8_t>(value >> (n * 8));
}
std::uint64_t get(Span in, std::size_t at, unsigned width) {
    check(at <= in.size() && width <= in.size() - at, "fixture receipt read exceeded its bounds");
    std::uint64_t value{};
    for (unsigned n = 0; n < width; ++n) value |= std::uint64_t(in[at + n]) << (n * 8);
    return value;
}
Span bytes(std::string_view value) { return {reinterpret_cast<const std::uint8_t*>(value.data()), value.size()}; }
struct Identity { std::uint64_t epoch{11}, application{}, document{}, generation{}; };
Bytes request(std::uint32_t operation, Identity id, Span body = {}, std::uint64_t transfer = 0) {
    Bytes out(72 + body.size()); std::copy_n("FKB1", 4, out.begin());
    put(out, 4, 1, 2); put(out, 6, operation, 2); put(out, 8, out.size(), 4);
    put(out, 16, id.epoch, 8); put(out, 24, id.application, 8); put(out, 32, id.document, 8);
    put(out, 40, id.generation, 8); put(out, 48, transfer, 8); put(out, 64, body.size(), 4);
    std::copy(body.begin(), body.end(), out.begin() + 72); return out;
}
Bytes bridge(std::uint32_t operation, Identity id = {}, Span body = {}, std::uint64_t transfer = 0) {
    const auto in = request(operation, id, body, transfer); Bytes out(8192, 0xa5);
    const auto size = gui_web_engine_dispatch_v1(operation, in.data(), in.size(), out.data(), out.size());
    check(size >= 80 && static_cast<std::size_t>(size) <= out.size(), "host did not return a bounded copied receipt");
    out.resize(static_cast<std::size_t>(size));
    check(get(out, 6, 2) == (operation | FOUNDATION_ENGINE_REPLY_KIND) && get(out, 8, 4) == out.size() &&
          get(out, 64, 4) == out.size() - 72, "host changed copied receipt framing");
    return out;
}
void accepted(const Bytes& out) {
    check(get(out, 72, 4) == FOUNDATION_ENGINE_OK && get(out, 76, 4) == 0,
          "host rejected an expected copied endpoint operation");
}
template<class F> void rejected(F&& action, const char* reason) {
    bool failed{}; try { action(); } catch (const std::exception&) { failed = true; }
    check(failed, reason);
}
std::string digest(const auto& value) { return detail::hex_digest(value); }
Json expected_profile(bool physical) {
    Json::Object result{{"schema_version", 1}, {"kind", "foundation-copied-engine-document-v2"},
        {"target", "browser-wasm32"}, {"binding", "copied-owner-bridge/direct-worker-document-v2"},
        {"pointer_bits", 32}, {"pthread", false}, {"shared_memory", false},
        {"bridge_abi", static_cast<int>(FOUNDATION_ENGINE_BRIDGE_VERSION)},
        {"capabilities", physical ? "2003" : "1795"}, {"contract_sha256", digest(doc::kContractSha256)},
        {"build_sha256", std::string(64, '1')}, {"source_recipe_sha256", std::string(64, '2')},
        {"provider_abi_major", 1}, {"provider_abi_minor", 1}, {"host_abi_major", 1}, {"host_abi_minor", 0},
        {"document_profile", std::string(physical ? doc::kPhysicalProfileName : doc::kPixelProfileName)},
        {"base_header_sha256", digest(doc::kBaseHeaderSha256)},
        {"extension_header_sha256", digest(doc::kExtensionHeaderSha256)},
        {"document_catalog_sha256", digest(doc::kCatalogSha256)}, {"document_schema_sha256", digest(doc::kSchema)},
        {"action_ack_schema_sha256", digest(doc::kAckSchema)}, {"viewport_width", 800}, {"viewport_height", 600}};
    if (physical) {
        result.emplace("command_catalog_sha256", digest(doc::kPhysicalCatalogSha256));
        result.emplace("surface_protocol_version", 1); result.emplace("surface_capabilities", "8225");
        result.emplace("mouse_input_version", 1); result.emplace("key_mapping_version", 1); result.emplace("display_scale", 1);
    }
    return result;
}
void legacy_input_getter(Bytes& out, const Bytes& untouched) {
    const auto count = gui_web_engine_input_describe_v1(out.data(), out.size());
    check(count > 0 && count < 4096, "explicit legacy467 host omitted its immutable input facts");
    const std::string value(reinterpret_cast<const char*>(out.data()), static_cast<std::size_t>(count));
    check(value.find('\0') == std::string::npos &&
          std::all_of(out.begin() + count, out.end(), [](auto c) { return c == 0xa5; }),
          "legacy467 getter changed trailing output bytes or added a terminator");
    const Json expected = Json::Object{{"schema_version", 1}, {"kind", "foundation-copied-engine-physical-v1"},
        {"target", "browser-wasm32"}, {"binding", "copied-owner-bridge/direct-worker-physical-v1"},
        {"pointer_bits", 32}, {"pthread", false}, {"shared_memory", false},
        {"bridge_abi", static_cast<int>(FOUNDATION_ENGINE_BRIDGE_VERSION)}, {"capabilities", "467"},
        {"contract_sha256", digest(input::kProviderContractSha256)}, {"build_sha256", std::string(64, '1')},
        {"source_recipe_sha256", std::string(64, '2')}, {"command_catalog_sha256", digest(input::kInputCatalogSha256)},
        {"surface_protocol_version", 1}, {"surface_capabilities", "8225"}, {"mouse_input_version", 1},
        {"key_mapping_version", 1}, {"viewport_width", 800}, {"viewport_height", 600}, {"display_scale", 1}};
    const auto parsed = gui::web_detail::Parser(value).parse();
    check(std::get<Json::Object>(parsed.value).size() == 20 &&
          gui::web_detail::encode(parsed) == gui::web_detail::encode(expected),
          "legacy467 getter fields, types or compiled facts changed during document integration");
    out = untouched;
    check(gui_web_engine_input_describe_v1(out.data(), static_cast<std::size_t>(count) - 1) == FOUNDATION_ENGINE_REPLY_TOO_SMALL &&
          out == untouched, "short legacy467 getter partially copied its description");
    check(gui_web_engine_input_describe_v1(nullptr, static_cast<std::size_t>(count)) == FOUNDATION_ENGINE_BAD_RECORD,
          "enabled legacy467 getter admitted a null output");
    check(gui_web_engine_input_describe_v1(out.data(), static_cast<std::size_t>(count)) == count &&
          std::equal(value.begin(), value.end(), out.begin()) && out[static_cast<std::size_t>(count)] == 0xa5,
          "legacy467 getter lost exact-capacity/canary compatibility");
    out = untouched;
}
void no_prepared_owner() {
    const auto in = request(FOUNDATION_ENGINE_PEEK_DOCUMENT_WORK, {}); Bytes out(160, 0xa5), original = out;
    check(gui_web_engine_dispatch_v1(FOUNDATION_ENGINE_PEEK_DOCUMENT_WORK, in.data(), in.size(), out.data(), out.size()) ==
          FOUNDATION_ENGINE_BAD_RECORD && out == original, "readonly getter prepared an Owner or changed its output");
    rejected([] { (void)gui_web_create("unprepared"); }, "readonly getter initialized a graphical runtime");
}
std::string getter(std::string_view mode) {
    Bytes out(4096, 0xa5), untouched = out;
    check(gui_web_engine_bridge_v1() == FOUNDATION_ENGINE_BRIDGE_VERSION, "compiled bridge marker changed");
#if defined(FOUNDATION_APPENDED_BINARY_CAPABILITY) && FOUNDATION_APPENDED_BINARY_CAPABILITY
    check(gui_web_engine_profile_v1() == 2, "document feature changed the binary-capable component marker");
#else
    check(gui_web_engine_profile_v1() == 1, "document feature changed the web-only component marker");
#endif
    if (mode == "legacy") legacy_input_getter(out, untouched);
    else check(gui_web_engine_input_describe_v1(out.data(), out.size()) == FOUNDATION_ENGINE_BAD_OPERATION && out == untouched,
               "document host fabricated a legacy467 input-profile getter");
    const auto count = gui_web_engine_document_describe_v1(out.data(), out.size());
    if (mode == "disabled" || mode == "legacy" || mode == "invalid") {
        check(count == FOUNDATION_ENGINE_BAD_OPERATION && out == untouched, "unsupported document facts were advertised or wrote output");
        check(gui_web_engine_document_describe_v1(nullptr, 0) == FOUNDATION_ENGINE_BAD_OPERATION,
              "unsupported document getter inferred a profile from its caller");
        no_prepared_owner(); return {};
    }
    check(count > 0 && count < 4096, "document getter did not return exact bounded JSON bytes");
    const std::string value(reinterpret_cast<const char*>(out.data()), static_cast<std::size_t>(count));
    check(value.find('\0') == std::string::npos &&
          std::all_of(out.begin() + count, out.end(), [](auto c) { return c == 0xa5; }),
          "document getter added a NUL or wrote beyond its reported exact bytes");
    const auto parsed = gui::web_detail::Parser(value).parse();
    check(std::get<Json::Object>(parsed.value).size() == (mode == "physical" ? 30 : 24) &&
          gui::web_detail::encode(parsed) == gui::web_detail::encode(expected_profile(mode == "physical")),
          "document getter JSON fields, types or exact compiled profile identity disagreed");
    out.assign(4096, 0xa5);
    check(gui_web_engine_document_describe_v1(out.data(), static_cast<std::size_t>(count) - 1) == FOUNDATION_ENGINE_REPLY_TOO_SMALL &&
          out == untouched, "short document getter partially copied its description");
    check(gui_web_engine_document_describe_v1(out.data(), 0) == FOUNDATION_ENGINE_REPLY_TOO_SMALL && out == untouched,
          "zero-capacity document getter changed caller bytes");
    check(gui_web_engine_document_describe_v1(nullptr, static_cast<std::size_t>(count)) == FOUNDATION_ENGINE_BAD_RECORD &&
          gui_web_engine_document_describe_v1(nullptr, 0) == FOUNDATION_ENGINE_BAD_RECORD,
          "enabled document getter admitted a null destination");
    auto* overflow = reinterpret_cast<unsigned char*>(std::numeric_limits<std::uintptr_t>::max() - 7);
    check(gui_web_engine_document_describe_v1(overflow, 16) == FOUNDATION_ENGINE_BAD_RECORD,
          "document getter admitted a wrapping caller range");
    check(gui_web_engine_document_describe_v1(out.data(), static_cast<std::size_t>(count)) == count &&
          std::equal(value.begin(), value.end(), out.begin()) && out[static_cast<std::size_t>(count)] == 0xa5,
          "exact-capacity document getter changed immutable facts or added a terminator");
    no_prepared_owner(); return value;
}

struct Carrier {
    const std::uint64_t prefix_length = 4096;
    const detail::Digest prefix_sha256 = detail::sha256(bytes("immutable synthetic HTML kernel"));
    Bytes suffix;
    std::string package_sha256;
    Carrier() {
        const std::string startup = "{\"kind\":\"foundation-appended-startup\",\"primary\":\"web\",\"schema_version\":1}";
        const std::string html = "<!doctype html><title>Document host fixture</title><p>actual bitmap</p>";
        const auto file = [](std::string_view path, std::string_view mime, std::size_t offset, std::string_view content) {
            return "{\"component\":\"web\",\"length\":" + std::to_string(content.size()) + ",\"media_type\":\"" +
                std::string(mime) + "\",\"offset\":" + std::to_string(offset) + ",\"path\":\"" + std::string(path) +
                "\",\"sha256\":\"" + detail::hex_digest(detail::sha256(bytes(content))) + "\"}";
        };
        const auto index = "{\"application\":{\"id\":\"org.example.document-host\",\"name\":\"Document host fixture\",\"version\":\"1.0.0\"},"
            "\"components\":{\"binary\":{\"entry\":null,\"present\":false,\"profile\":null},\"web\":{\"entry\":\"web/index.html\",\"present\":true}},"
            "\"files\":[" + file("web/.foundation/startup-v1.json", "application/json", 0, startup) + "," +
            file("web/index.html", "text/html", startup.size(), html) + "],\"identities\":{},\"kind\":\"foundation-appended-package\","
            "\"requires\":{\"abi\":{\"major\":1,\"minor\":0},\"capabilities\":[\"foundation.startup.v1\"],\"services\":[]},\"schema_version\":1}";
        suffix.insert(suffix.end(), startup.begin(), startup.end()); suffix.insert(suffix.end(), html.begin(), html.end());
        const auto index_offset = suffix.size(); suffix.insert(suffix.end(), index.begin(), index.end());
        const auto package_hash = detail::sha256(suffix), index_hash = detail::sha256(bytes(index));
        package_sha256 = detail::hex_digest(package_hash);
        const auto package_size = suffix.size(); suffix.resize(package_size + appended_trailer_bytes);
        auto trailer = std::span(suffix).subspan(package_size); std::copy_n("SFAPND01", 8, trailer.begin());
        put(trailer, 8, 1, 4); put(trailer, 12, appended_trailer_bytes, 4); put(trailer, 16, prefix_length, 8);
        put(trailer, 24, package_size, 8); put(trailer, 32, index_offset, 8); put(trailer, 40, index.size(), 8); put(trailer, 48, 3, 8);
        std::copy(prefix_sha256.begin(), prefix_sha256.end(), trailer.begin() + 56);
        std::copy(package_hash.begin(), package_hash.end(), trailer.begin() + 88);
        std::copy(index_hash.begin(), index_hash.end(), trailer.begin() + 120);
    }
    Bytes configure() const {
        Bytes body(40); put(body, 0, prefix_length, 8); std::copy(prefix_sha256.begin(), prefix_sha256.end(), body.begin() + 8);
        body.insert(body.end(), suffix.begin(), suffix.end()); return request(FOUNDATION_ENGINE_CONFIGURE, {}, body);
    }
};
Bytes frame(std::uint64_t base, std::uint8_t red) {
    Bytes out(48 + 800 * 600 * 4); put(out, 0, 1, 4); put(out, 4, 800, 4); put(out, 8, 600, 4); put(out, 12, 3200, 4);
    put(out, 24, 800, 4); put(out, 28, 600, 4); put(out, 32, base, 8); put(out, 40, base + 1, 8);
    for (std::size_t n = 48; n < out.size(); n += 4) { out[n] = red; out[n + 1] = 23; out[n + 2] = 45; out[n + 3] = 255; }
    return out;
}
Json state(std::string value, std::uint8_t red) {
    const auto marker = value.find("\"rgb\":\""); check(marker != std::string::npos, "typed bitmap browser did not publish actual copied pixels");
    const auto start = marker + 7, end = value.find('"', start);
    constexpr std::string_view alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    const std::array<char, 4> first{alphabet[red >> 2], alphabet[((red & 3) << 4) | (23 >> 4)], alphabet[((23 & 15) << 2) | (45 >> 6)], alphabet[45 & 63]};
    check(end != std::string::npos && end - start == 800 * 600 * 4 && value.compare(start, 4, first.data(), 4) == 0,
          "typed bitmap browser changed its owned RGB byte count or color");
    value.erase(start, end - start); // The inbound JSON parser has its independent 1 MiB request limit.
    const auto result = gui::web_detail::Parser(value).parse();
    check(result.at("error").str().empty() && result.at("snapshot").at("title").str() == "Document host fixture" &&
          result.at("snapshot").at("widgets").array().size() == 1 &&
          result.at("snapshot").at("widgets").array().front().at("kind").number() == static_cast<int>(gui::Kind::bitmap),
          "host selected a semantic projection or failed its actual bitmap publication");
    return result;
}
std::uint64_t browser_sequence = 1;
Json receive(Json operation, std::uint8_t red = 131) {
    const auto message = gui::web_detail::encode(Json::Object{{"epoch", "document-host"}, {"seq", std::to_string(browser_sequence++)},
        {"operation", std::move(operation)}});
    return state(gui_web_receive(message.c_str()), red);
}
Json poll(std::uint8_t red = 131) { return receive(Json::Object{{"type", "poll"}}, red); }
input::Command consume(Identity id) {
    const auto staged = bridge(FOUNDATION_ENGINE_PEEK_INPUT, id); accepted(staged);
    input::Command command;
    check(input::decode_command(Span(staged).subspan(80), command) == input::Status::ok,
          "actual host did not expose the complete physical command payload");
    check(bridge(FOUNDATION_ENGINE_PEEK_INPUT, id) == staged, "host reminted its immutable physical mailbox");
    const Identity target{get(staged, 16, 8), get(staged, 24, 8), get(staged, 32, 8), get(staged, 40, 8)};
    const auto transfer = get(staged, 48, 8); accepted(bridge(FOUNDATION_ENGINE_TURN_ENTER, target, {}, transfer));
    accepted(bridge(FOUNDATION_ENGINE_TURN_LEAVE, target, {}, transfer));
    Bytes outcome; check(input::encode_command_result({0, 1, command.request_sequence, 0, 0}, outcome) == input::Status::ok,
          "fixture copied command result was invalid");
    accepted(bridge(FOUNDATION_ENGINE_COMMAND_RESULT, target, outcome, transfer)); return command;
}
void physical_input(Identity id, const Json& initial) {
    check(std::holds_alternative<std::nullptr_t>(initial.at("surface").value), "unconnected physical host fabricated surface admission");
    check(get(bridge(FOUNDATION_ENGINE_PEEK_INPUT, id), 72, 4) == FOUNDATION_ENGINE_EMPTY,
          "physical host staged a context before its actual Browser surface connected");
    const auto connected = receive(Json::Object{{"type", "surfaceConnect"}, {"version", 1}, {"supported", "8225"}, {"mouseInputVersion", 1}});
    check(connected.at("surface").at("capabilities").at("supported").str() == "8225" &&
          connected.at("surface").at("capabilities").at("mouseInputVersion").number() == 1,
          "document2003 did not use the actual8225 Browser surface composition");
    const auto staged = poll();
    check(!staged.at("surface").at("presentation").at("available").boolean(),
          "physical Browser surface became available before provider context binding was consumed");
    const auto binding = consume(id); input::Focus focus;
    check(binding.operation == BIB_ENGINE_COMMAND_FOCUS && input::decode_focus(binding.payload, focus) == input::Status::ok &&
          focus.action == 1 && focus.input_context != 0 && focus.expected_context == 0,
          "physical host did not stage a fresh metadata context binding");
    auto paired = poll(); const auto& presentation = paired.at("surface").at("presentation");
    const auto& identity = presentation.at("identity");
    check(presentation.at("available").boolean() &&
          (gui::web_detail::integer(presentation.at("required")) & ~std::uint64_t{8225}) == 0 &&
          gui::web_detail::integer(identity.at("generation")) != 0 &&
          gui::web_detail::integer(identity.at("epoch")) != 0 &&
          gui::web_detail::integer(identity.at("context")) != 0 &&
          identity.at("context").str() == staged.at("surface").at("presentation").at("identity").at("context").str() &&
          identity.at("presentationRevision").str() == paired.at("snapshot").at("revision").str() &&
          gui::web_detail::encode(identity.at("owner")) == gui::web_detail::encode(paired.at("snapshot").at("widgets").array().front().at("key")),
          "physical host did not publish an exact live bitmap/surface pair after binding");
    (void)receive(Json::Object{{"type", "surfaceInput"}, {"identity", identity}, {"sequence", "1"},
        {"input", Json::Object{{"kind", "focus"}, {"focused", true}, {"active", true}, {"cause", "direct"}}}});
    (void)poll(); const auto focused = consume(id);
    check(focused.operation == BIB_ENGINE_COMMAND_FOCUS && input::decode_focus(focused.payload, focus) == input::Status::ok &&
          focus.action == 0 && focus.focused && focus.active, "physical Browser focus did not reach the real Owner mailbox");
    paired = poll();
    (void)receive(Json::Object{{"type", "surfaceInput"}, {"identity", paired.at("surface").at("presentation").at("identity")}, {"sequence", "2"},
        {"input", Json::Object{{"kind", "key"}, {"phase", "down"}, {"key", "z"}, {"code", "KeyZ"},
            {"location", 0}, {"modifiers", 0}, {"repeat", false}}}});
    (void)poll(); const auto keyed = consume(id); input::Key key;
    check(keyed.operation == BIB_ENGINE_COMMAND_KEY && input::decode_key(keyed.payload, key) == input::Status::ok &&
          key.key == "z" && key.code == "KeyZ" && key.input_context == focus.input_context,
          "document2003 surface forwarded no exact owned physical key command");
    (void)poll();
}
void configure_and_bitmap(std::string_view mode, const std::string& description) {
    const Carrier carrier; const auto in = carrier.configure(); Bytes out(8192, 0xa5), untouched = out;
    const auto configure = [&](Span value, std::size_t capacity) {
        return gui_web_engine_dispatch_v1(FOUNDATION_ENGINE_CONFIGURE, value.data(), value.size(), out.data(), capacity);
    };
    check(configure(in, 79) == FOUNDATION_ENGINE_REPLY_TOO_SMALL && out == untouched,
          "host initialized or wrote before a complete configure receipt fit");
    if (mode == "invalid") {
        check(configure(in, out.size()) == 80 && get(out, 72, 4) == FOUNDATION_ENGINE_UNSUPPORTED,
              "invalid generated document facts reached Package/Owner preparation");
        no_prepared_owner(); return;
    }
    check(configure(in, 80) == FOUNDATION_ENGINE_REPLY_TOO_SMALL && out == untouched,
          "host initialized before the complete Package metadata reply fit");
    auto corrupt = in; corrupt.back() ^= 1;
    check(configure(corrupt, out.size()) == 80 && get(out, 72, 4) == FOUNDATION_ENGINE_INVALID,
          "document host admitted corrupt carrier suffix bytes");
    no_prepared_owner();
    const auto size = configure(in, out.size());
    check(size > 80 && static_cast<std::size_t>(size) <= out.size() && get(out, 72, 4) == FOUNDATION_ENGINE_OK,
          "valid Package CONFIGURE failed after a rejected/undersized attempt");
    const auto metadata = gui::web_detail::Parser(std::string_view(reinterpret_cast<const char*>(out.data() + 80),
        static_cast<std::size_t>(size) - 80)).parse();
    check(metadata.at("application_name").str() == "Document host fixture" &&
          metadata.at("package_sha256").str() == carrier.package_sha256 &&
          metadata.at("entry_url").str() == "app://" + metadata.at("package_sha256").str() + "/web/index.html",
          "host metadata did not come from the verified actual HTML Package");
    check(configure(in, out.size()) == 80 && get(out, 72, 4) == FOUNDATION_ENGINE_CONFLICT,
          "host replaced an already configured Owner");
    if (mode != "disabled" && mode != "legacy") {
        const auto empty = bridge(FOUNDATION_ENGINE_PEEK_DOCUMENT_WORK);
        check(get(empty, 72, 4) == FOUNDATION_ENGINE_EMPTY && get(empty, 76, 4) == 0,
              "host CONFIGURE failed to give actual document facts to EngineOwner");
        rejected([] { (void)gui_web_create("too-early"); }, "document host created GUI before actual native document identity readiness");
    } else {
        const auto request_bytes = request(FOUNDATION_ENGINE_PEEK_DOCUMENT_WORK, {});
        check(gui_web_engine_dispatch_v1(FOUNDATION_ENGINE_PEEK_DOCUMENT_WORK, request_bytes.data(), request_bytes.size(), out.data(), out.size()) ==
              FOUNDATION_ENGINE_BAD_OPERATION, "default host silently enabled the new document route");
    }
    accepted(bridge(FOUNDATION_ENGINE_TURN_ENTER));
    const auto begun = bridge(FOUNDATION_ENGINE_BEGIN_DOCUMENT, {11, 17, 1, 0}); accepted(begun);
    const Identity id{11, 17, 1, get(begun, 40, 8)}; check(id.generation != 0, "actual Owner did not establish service generation");
    accepted(bridge(FOUNDATION_ENGINE_FRAME_COMMIT, id, frame(0, 131)));
    rejected([] { (void)gui_web_create("active-turn"); }, "host created or presented GUI inside native TURN");
    accepted(bridge(FOUNDATION_ENGINE_TURN_LEAVE));
    const auto initial = state(gui_web_create("document-host"), 131);
    if (mode == "physical" || mode == "legacy") physical_input(id, initial);
    else check(std::get<Json::Object>(initial.value).find("surface") == std::get<Json::Object>(initial.value).end(),
               "pixel/default host exposed a physical Browser composition");
    accepted(bridge(FOUNDATION_ENGINE_FRAME_COMMIT, id, frame(1, 141)));
    const auto next = poll(141);
    check(next.at("snapshot").at("widgets").array().front().at("image").at("revision").str() == "2",
          "ordinary Browser task did not publish the actual next copied frame");
    Bytes after(4096, 0xa5);
    const auto count = gui_web_engine_document_describe_v1(after.data(), after.size());
    check(mode == "disabled" || mode == "legacy" ? count == FOUNDATION_ENGINE_BAD_OPERATION :
          count == static_cast<std::int32_t>(description.size()) &&
          std::equal(description.begin(), description.end(), after.begin()), "CONFIGURE/runtime mutated immutable compiled document facts");
    gui_web_destroy();
}
} // namespace

int main(int argc, char** argv) {
    try {
        constexpr std::string_view default_mode =
#if defined(FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED) && FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED
            "legacy";
#else
            "disabled";
#endif
        const std::string_view mode = argc >= 2 ? argv[1] :
            FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 1 ? "pixel" :
            FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 2 ? "physical" : default_mode;
        check(argc <= 3 && (argc != 3 || std::string_view(argv[2]) == "--describe-only") &&
              (mode == "disabled" || mode == "pixel" || mode == "physical" || mode == "legacy" || mode == "invalid"), "unknown fixture profile selector");
        const auto description = getter(mode);
        if (argc == 3) { std::cout << description << '\n'; return 0; }
        configure_and_bitmap(mode, description);
        std::cout << "Document host " << mode << ": " << assertions << " assertions passed\n";
    } catch (const std::exception& error) {
        gui_web_destroy(); std::cerr << "Document host failure after " << assertions << " assertions: " << error.what() << '\n'; return 1;
    }
}
