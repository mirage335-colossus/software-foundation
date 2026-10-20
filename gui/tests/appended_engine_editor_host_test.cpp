// SPDX-License-Identifier: CC0-1.0
#include "shared/appended_engine_abi.h"
#include "shared/engine_editor_profile.hpp"
#include "shared/appended_engine_input_codec.hpp"
#include "shared/engine_editor_work.hpp"
#include "shared/native_editor_codec.hpp"
#include "../../src/appended/sha256.hpp"
#include <foundation/appended/container.hpp>
#include <gui/web.hpp>
#include <algorithm>
#include <array>
#include <cstdint>
#include <functional>
#include <iostream>
#include <limits>
#include <optional>
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
struct PhysicalReply {
    std::int32_t provider_status{};
    std::uint32_t disposition{1};
    std::uint32_t handled{};
};
struct EditorWorkView {
    std::uint64_t worker_epoch{}, application{}, document{}, generation{}, transfer{}, request_sequence{};
    std::uint32_t kind{}, operation{}, required_reply_capacity{};
    std::array<std::uint8_t, 32> schema{};
    Bytes payload;
};
struct EditorReply {
    std::int32_t provider_status{};
    std::uint32_t disposition{}, handled{};
    std::uint64_t semantic_revision{};
    Bytes payload;
};
struct ReplayHooks {
    std::function<PhysicalReply(const foundation::appended::engine_input::Command&)> physical;
    std::function<EditorReply(const EditorWorkView&)> query4;
    std::function<EditorReply(const EditorWorkView&)> native9;
    std::function<void(std::string_view)> after_cleanup_poll;
    std::function<void(std::string_view)> after_recovery_poll;
    std::function<EditorReply(const EditorWorkView&)> query4_recovery;
};
// Actual host composition with a verified in-memory Package and explicitly
// synthetic copied engine replies. No engine, DSO, SDK or browser is launched.
void ready_editor_composition(const ReplayHooks& hooks = {}) {
    using namespace foundation::appended;
    using Span = std::span<const std::uint8_t>;
    check(!hooks.query4 || static_cast<bool>(hooks.physical), "query4 replay requires the actual physical bind step");
    check(!hooks.native9 || static_cast<bool>(hooks.query4), "native9 replay requires the initial actual query4 step");
    check(!hooks.query4_recovery || static_cast<bool>(hooks.native9), "query4 recovery requires the preceding actual native9 step");
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
    struct Identity { std::uint64_t application{}, document{}, generation{}, worker_epoch{11}; };
    const auto request = [&](std::uint32_t operation, Identity id, Span body, std::uint64_t transfer = 0) {
        Bytes out(72 + body.size()); std::copy_n("FKB1", 4, out.begin());
        put(out, 4, 1, 2); put(out, 6, operation, 2); put(out, 8, out.size(), 4); put(out, 16, id.worker_epoch, 8);
        put(out, 24, id.application, 8); put(out, 32, id.document, 8); put(out, 40, id.generation, 8);
        put(out, 48, transfer, 8); put(out, 64, body.size(), 4); std::copy(body.begin(), body.end(), out.begin() + 72); return out;
    };
    const auto bridge = [&](std::uint32_t operation, Identity id, Span body, std::uint64_t transfer = 0) {
        const auto in = request(operation, id, body, transfer); Bytes out(8192);
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
    const auto receive_raw = [&](Json operation) {
        const auto envelope = gui::web_detail::encode(Json::Object{{"epoch", "editor-host"}, {"seq", std::to_string(++sequence)}, {"operation", std::move(operation)}});
        return std::string(gui_web_receive(envelope.c_str()));
    };
    const auto receive = [&](Json operation) {
        return state(receive_raw(std::move(operation)));
    };
    const auto connected = receive(Json::Object{{"type", "surfaceConnect"}, {"version", 2}, {"profile", "editor_v1"}, {"supported", "8255"}, {"mouseInputVersion", 1}});
    check(connected.at("surface").at("capabilities").at("supported").str() == "8255", "editor host silently selected a legacy capability profile");
    if (hooks.physical) {
        (void)receive(Json::Object{{"type", "poll"}}); // Consume queued CONNECT before peeking actual bind.
        const auto pending = bridge(FOUNDATION_ENGINE_PEEK_INPUT, id, {});
        check(get(pending, 72, 4) == FOUNDATION_ENGINE_OK, "expected pending actual physical bind");
        const auto target = Identity{get(pending, 24, 8), get(pending, 32, 8), get(pending, 40, 8), get(pending, 16, 8)};
        const auto transfer = get(pending, 48, 8);
        check(transfer != 0 && pending.size() > FOUNDATION_ENGINE_RECEIPT_BYTES,
            "physical PEEK omitted its exact target, transfer, or command");
        foundation::appended::engine_input::Command command;
        const Span command_bytes{pending.data() + FOUNDATION_ENGINE_RECEIPT_BYTES, pending.size() - FOUNDATION_ENGINE_RECEIPT_BYTES};
        check(foundation::appended::engine_input::decode_command(command_bytes, command) ==
            foundation::appended::engine_input::Status::ok, "physical PEEK returned malformed command");
        const auto reply = hooks.physical(command);
        accepted(bridge(FOUNDATION_ENGINE_TURN_ENTER, target, {}, transfer));
        accepted(bridge(FOUNDATION_ENGINE_TURN_LEAVE, target, {}, transfer));
        Bytes result(24); put(result, 0, static_cast<std::uint32_t>(reply.provider_status), 4);
        put(result, 4, reply.disposition, 4); put(result, 8, command.request_sequence, 8);
        put(result, 20, reply.handled, 4);
        accepted(bridge(FOUNDATION_ENGINE_COMMAND_RESULT, target, result, transfer));
        (void)receive(Json::Object{{"type", "poll"}});
    }
    const auto pump_editor = [&](bool query4,
        const std::function<EditorReply(const EditorWorkView&)>* override_handler = nullptr) {
        if (query4 ? !(override_handler || hooks.query4) : !hooks.native9) return false;
        const auto pending = bridge(FOUNDATION_ENGINE_PEEK_EDITOR_WORK, id, {});
        if (get(pending, 72, 4) == FOUNDATION_ENGINE_EMPTY) return false;
        check(get(pending, 72, 4) == FOUNDATION_ENGINE_OK && pending.size() >=
            FOUNDATION_ENGINE_RECEIPT_BYTES + FOUNDATION_ENGINE_EDITOR_WORK_PREFIX_BYTES, "actual editor work had invalid framing");
        EditorWorkView work;
        work.worker_epoch = get(pending, 16, 8); work.application = get(pending, 24, 8);
        work.document = get(pending, 32, 8); work.generation = get(pending, 40, 8);
        work.transfer = get(pending, 48, 8); work.kind = static_cast<std::uint32_t>(get(pending, 80, 4));
        work.operation = static_cast<std::uint32_t>(get(pending, 84, 4));
        work.request_sequence = get(pending, 88, 8);
        std::copy_n(pending.begin() + 96, work.schema.size(), work.schema.begin());
        work.required_reply_capacity = static_cast<std::uint32_t>(get(pending, 128, 4));
        const auto payload_bytes = get(pending, 132, 4);
        check(work.worker_epoch && work.application && work.document && work.generation && work.transfer &&
            work.request_sequence && payload_bytes == pending.size() - FOUNDATION_ENGINE_RECEIPT_BYTES - FOUNDATION_ENGINE_EDITOR_WORK_PREFIX_BYTES,
            "editor PEEK omitted its exact target, transfer, sequence, or bounded payload");
        work.payload.assign(pending.begin() + FOUNDATION_ENGINE_RECEIPT_BYTES + FOUNDATION_ENGINE_EDITOR_WORK_PREFIX_BYTES, pending.end());
        const bool is_query4 = work.kind == static_cast<std::uint32_t>(foundation::appended::EngineEditorWorkKind::projection_query) &&
            work.operation == BIB_ENGINE_QUERY_EDITOR_PROJECTION_V1;
        const std::function<EditorReply(const EditorWorkView&)>* handler{};
        if (is_query4) handler = override_handler ? override_handler : &hooks.query4;
        else if (work.kind == static_cast<std::uint32_t>(foundation::appended::EngineEditorWorkKind::revoke) &&
            work.operation == BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1) handler = &hooks.native9;
        check(handler && static_cast<bool>(*handler), "actual editor work did not match an installed query4/native9 hook");
        check(query4 == is_query4, "editor work arrived at the wrong replay checkpoint");
        const auto reply = (*handler)(work);
        Bytes claim(FOUNDATION_ENGINE_EDITOR_BEGIN_BYTES);
        put(claim, 0, work.kind, 4); put(claim, 8, work.request_sequence, 8);
        const Identity target{work.application, work.document, work.generation, work.worker_epoch};
        accepted(bridge(FOUNDATION_ENGINE_BEGIN_EDITOR_WORK, target, claim, work.transfer));
        accepted(bridge(FOUNDATION_ENGINE_TURN_ENTER, target, {}, work.transfer));
        accepted(bridge(FOUNDATION_ENGINE_TURN_LEAVE, target, {}, work.transfer));
        Bytes result(FOUNDATION_ENGINE_EDITOR_RESULT_PREFIX_BYTES + reply.payload.size());
        put(result, 0, work.kind, 4); put(result, 8, work.request_sequence, 8);
        put(result, 16, static_cast<std::uint32_t>(reply.provider_status), 4);
        put(result, 20, reply.disposition, 4); put(result, 24, reply.payload.size(), 4);
        put(result, 28, reply.handled, 4); put(result, 32, reply.semantic_revision, 8);
        std::copy(reply.payload.begin(), reply.payload.end(), result.begin() + FOUNDATION_ENGINE_EDITOR_RESULT_PREFIX_BYTES);
        accepted(bridge(FOUNDATION_ENGINE_EDITOR_WORK_RESULT, target, result, work.transfer));
        return true;
    };
    const bool replayed_query4 = pump_editor(true);
    check(!hooks.query4 || replayed_query4, "configured query4 hook received no actual query4 request");
    const auto expected_resync_sequence = std::to_string(sequence + 1);
    const auto resync = receive(Json::Object{{"type", "editorResync"}});
    check(resync.at("editorReply").at("type").str() == "editorResync" &&
        resync.at("editorReply").at("sequence").str() == expected_resync_sequence,
        "actual editor Session did not route its metadata-only App endpoint");
    const auto pending = bridge(FOUNDATION_ENGINE_PEEK_EDITOR_WORK, id, {});
    check(get(pending, 72, 4) == FOUNDATION_ENGINE_EMPTY, "editor metadata ingress synchronously entered provider work");
    if (hooks.native9) (void)receive(Json::Object{{"type", "poll"}});
    const bool replayed_native9 = pump_editor(false);
    check(!hooks.native9 || replayed_native9, "configured native9 hook received no actual cleanup request");
    if (hooks.after_cleanup_poll || hooks.query4_recovery) {
        const auto response = receive_raw(Json::Object{{"type", "poll"}});
        if (hooks.after_cleanup_poll) hooks.after_cleanup_poll(response);
    }
    if (hooks.query4_recovery) {
        const bool replayed = pump_editor(true, &hooks.query4_recovery);
        check(replayed, "query4 recovery hook received no actual fresh query4 request");
        const auto response = receive_raw(Json::Object{{"type", "poll"}});
        if (hooks.after_recovery_poll) hooks.after_recovery_poll(response);
    }
    gui_web_destroy(); unprepared();
}
namespace ne = foundation::ui::native_editor;
namespace codec = ne::codec;
gui::web_detail::Json public_metadata(std::string_view raw) {
    std::string text(raw);
    const auto marker=text.find("\"rgb\":\"");
    check(marker!=std::string::npos,"causal response lost its actual bitmap");
    const auto start=marker+7,end=text.find('"',start);
    check(end!=std::string::npos && end-start==800*600*4 && text.compare(start,4,"gxct")==0,
          "causal response changed its actual copied RGB image");
    text.erase(start,end-start);
    return gui::web_detail::Parser(text).parse();
}
codec::WireTarget target_of(const EditorWorkView& w) {
    return {w.worker_epoch,w.application,w.document,w.generation,w.request_sequence};
}
void causal_replay(bool unavailable) {
    std::optional<ne::NativeProjection> live;
    unsigned queries{}, revocations{}, physicals{}, cleanup_checks{}, recoveries{};
    ReplayHooks hooks;
    hooks.physical = [&](const foundation::appended::engine_input::Command& command) {
        namespace input=foundation::appended::engine_input;
        input::Focus focus;
        check(command.operation==3 && input::decode_focus(command.payload,focus)==input::Status::ok &&
              focus.action==1 && focus.input_context,"expected actual physical bind command");
        ++physicals;return PhysicalReply{};
    };
    const auto query = [&](const EditorWorkView& w) {
        codec::ProjectionQuery request;
        check(codec::decode_projection_query(w.payload,request) && request.target==target_of(w),
              "query4 lost actual full target/sequence");
        check(request.identity.owner.id=="engine.frame" && request.identity.context && request.identity.generation &&
              request.identity.epoch && request.identity.presentation_revision,"query4 lacks actual GUI identity");
        ne::NativeProjection projection;
        projection.identity=request.identity;projection.editor_revision=1;
        projection.surrounding="ordinary text";projection.selection={0,0};
        projection.mapping_id=1;projection.frame_id=1;projection.readback_attested=true;
        projection.caret={12,24,1,18};projection.editable=true;projection.input_purpose="text";
        projection.retire=ne::NativeRetireMaterial{std::uint64_t(queries+1),1,request.identity.context,0};
        check(!request.mapping_id || request.mapping_id==projection.mapping_id,"query4 unexpectedly changed mapping");
        codec::ProjectionReply reply;
        reply.state=codec::ProjectionReply::State::available;reply.target=request.target;
        reply.identity=request.identity;reply.observation_revision=std::uint64_t(queries+2);reply.readback_attested=true;
        reply.projection=projection;EditorReply encoded;encoded.semantic_revision=reply.observation_revision;
        check(codec::encode_projection_reply(reply,encoded.payload),"real codec refused controlled query4");
        live=projection;++queries;return encoded;
    };
    hooks.query4=query;
    hooks.native9=[&](const EditorWorkView& w) {
        codec::RevocationEnvelope request;
        check(codec::decode_revocation(w.payload,request) && request.target==target_of(w) && live &&
              request.request.material==live->retire && request.request.identity==live->identity,
              "native9 lost exact provider material/target/sequence/identity");
        check(!request.request.observed,"causal native9 must be cleanup-only with no browser head");
        ne::NativeResult result;
        result.outcome=ne::Outcome::applied;result.continuity=ne::Continuity::replaced;
        result.availability=unavailable?ne::NativeAvailability::unavailable:ne::NativeAvailability::noneditable;
        result.observation_revision=3;result.readback_identity=request.request.identity;
        result.readback_attested=true;result.retired=request.request.material;
        EditorReply encoded;encoded.disposition=1;
        check(codec::encode_native_result({request.target,result},encoded.payload),"real codec refused exact applied native9");
        ne::NativeResult invalid=result;invalid.availability=ne::NativeAvailability::available;
        Bytes rejected;
        check(!codec::encode_native_result({request.target,invalid},rejected),
              "available without projection was incorrectly used as a valid control");
        ++revocations;live.reset();return encoded;
    };
    hooks.after_cleanup_poll=[&](std::string_view raw) {
        const auto value=public_metadata(raw);
        check(value.at("error").str().empty() && !value.at("snapshot").at("closed").boolean(),
              "known unavailable retirement closed the real application");
        check(value.at("surface").at("presentation").at("available").boolean()==!unavailable,
              "paired physical availability contradicts checked native retirement");
        const auto& editor=value.at("editor");
        check(std::holds_alternative<std::nullptr_t>(editor.at("basis").value),"cleanup invented an editor basis");
        const auto& retirement=editor.at("retirement");
        check(retirement.at("availability").str()==(unavailable?"unavailable":"noneditable") &&
              retirement.at("authorityRetired").boolean() && retirement.at("readbackAttested").boolean() &&
              retirement.at("observationRevision").str()=="3","actual paired retirement proof was lost");
        ++cleanup_checks;
        std::cout << "{\"phase\":\"after_cleanup\",\"closed\":false,\"available\":"
                  << (!unavailable?"true":"false") << ",\"retirement\":\""
                  << (unavailable?"unavailable":"noneditable") << "\"}\n";
    };
    hooks.query4_recovery=query;
    hooks.after_recovery_poll=[&](std::string_view raw) {
        const auto value=public_metadata(raw);
        check(value.at("error").str().empty() && !value.at("snapshot").at("closed").boolean() &&
              value.at("surface").at("presentation").at("available").boolean(),
              "fresh ordinary query4 did not recover real open physical presentation");
        check(!std::holds_alternative<std::nullptr_t>(value.at("editor").at("basis").value),
              "fresh actual editable query4 did not publish a basis");
        ++recoveries;
        std::cout << "{\"phase\":\"after_recovery\",\"closed\":false,\"available\":true,\"basis\":true}\n";
    };
    ready_editor_composition(hooks);
    check(physicals==1 && queries==2 && revocations==1 && cleanup_checks==1 && recoveries==1,
          "causal replay skipped or replayed an actual physical/query/native operation");
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
        if (argc != 2) throw std::invalid_argument("expected one editor host fixture mode");
        const std::string_view mode(argv[1]);
        if (mode == "valid" || mode == "unavailable") run(mode == "valid");
#if FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 3
        else if (mode == "unavailable-retirement") causal_replay(true);
        else if (mode == "noneditable-retirement") causal_replay(false);
#endif
        else throw std::invalid_argument("expected valid, unavailable, unavailable-retirement, or noneditable-retirement fixture mode");
        std::cout << "editor host readonly checks: " << assertions << '\n';
        return 0;
    } catch (const std::exception& error) { gui_web_destroy(); std::cerr << error.what() << '\n'; return 1; }
}
