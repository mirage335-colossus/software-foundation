#include "shared/appended_engine_application.hpp"
#include "shared/appended_engine_abi.h"
#include "../../src/appended/sha256.hpp"

#include <gui/retained_adapter.hpp>
#include <gui/web.hpp>
#include <algorithm>
#include <array>
#include <iostream>
#include <stdexcept>
#include <utility>

extern "C" {
std::uint32_t gui_web_engine_bridge_v1();
std::uint32_t gui_web_engine_profile_v1();
std::int32_t gui_web_engine_input_describe_v1(unsigned char*, std::size_t) noexcept;
std::int32_t gui_web_engine_dispatch_v1(std::uint32_t, const unsigned char*, std::size_t,
                                        unsigned char*, std::size_t) noexcept;
const char* gui_web_create(const char*);
const char* gui_web_receive(const char*);
void gui_web_destroy();
}

namespace {
using namespace foundation::appended;
using foundation::ui::AppendedEngineApplication;
using foundation::ui::prepare_engine_html_package;
using Span = std::span<const std::uint8_t>;
void check(bool condition, const char* message) { if (!condition) throw std::runtime_error(message); }
void put(std::span<std::uint8_t> bytes, std::size_t offset, std::uint64_t value, std::size_t width) {
    for (std::size_t n = 0; n < width; ++n) bytes[offset + n] = static_cast<std::uint8_t>(value >> (8 * n));
}
std::uint64_t get(Span bytes, std::size_t offset, std::size_t width) {
    std::uint64_t value = 0;
    for (std::size_t n = 0; n < width; ++n) value |= std::uint64_t(bytes[offset + n]) << (8 * n);
    return value;
}
Span span(std::string_view text) { return {reinterpret_cast<const std::uint8_t*>(text.data()), text.size()}; }
Bytes request(std::uint32_t operation, EngineIdentity identity, Span body = {}) {
    Bytes bytes(FOUNDATION_ENGINE_HEADER_BYTES + body.size());
    bytes[0] = 'F'; bytes[1] = 'K'; bytes[2] = 'B'; bytes[3] = '1';
    put(bytes, 4, 1, 2); put(bytes, 6, operation, 2); put(bytes, 8, bytes.size(), 4);
    put(bytes, 16, identity.worker_epoch, 8); put(bytes, 24, identity.application_instance, 8);
    put(bytes, 32, identity.document_sequence, 8); put(bytes, 40, identity.service_generation, 8);
    put(bytes, 64, body.size(), 4);
    std::copy(body.begin(), body.end(), bytes.begin() + FOUNDATION_ENGINE_HEADER_BYTES);
    return bytes;
}
Bytes invoke(EngineOwner& owner, std::uint32_t operation, EngineIdentity identity, Span body = {}) {
    const auto input = request(operation, identity, body);
    Bytes output(FOUNDATION_ENGINE_RECEIPT_BYTES);
    const auto count = owner.dispatch(operation, input, output);
    check(count == FOUNDATION_ENGINE_RECEIPT_BYTES, "actual owner did not return a complete receipt");
    return output;
}
void accepted(EngineOwner& owner, std::uint32_t operation, EngineIdentity identity, Span body = {}) {
    const auto reply = invoke(owner, operation, identity, body);
    check(get(reply, 72, 4) == FOUNDATION_ENGINE_OK && get(reply, 76, 4) == 0,
          "actual owner rejected an expected accepted operation");
}

struct Fixture {
    const std::uint64_t prefix_length = 4096;
    const detail::Digest prefix_sha256 = detail::sha256(span("immutable HTML kernel"));
    Bytes suffix;
    Fixture() {
        const std::string startup = "{\"kind\":\"foundation-appended-startup\",\"primary\":\"web\",\"schema_version\":1}";
        const std::string html = "<!doctype html><title>Owned fixture</title><p>pixels only</p>";
        const auto file = [](std::string_view path, std::string_view mime, std::size_t offset, std::string_view bytes) {
            return "{\"component\":\"web\",\"length\":" + std::to_string(bytes.size()) +
                ",\"media_type\":\"" + std::string(mime) + "\",\"offset\":" + std::to_string(offset) +
                ",\"path\":\"" + std::string(path) + "\",\"sha256\":\"" +
                detail::hex_digest(detail::sha256(span(bytes))) + "\"}";
        };
        const auto index = "{\"application\":{\"id\":\"org.example.engine\",\"name\":\"Owned fixture\",\"version\":\"1.0.0\"},"
            "\"components\":{\"binary\":{\"entry\":null,\"present\":false,\"profile\":null},"
            "\"web\":{\"entry\":\"web/index.html\",\"present\":true}},\"files\":[" +
            file("web/.foundation/startup-v1.json", "application/json", 0, startup) + "," +
            file("web/index.html", "text/html", startup.size(), html) +
            "],\"identities\":{},\"kind\":\"foundation-appended-package\",\"requires\":{\"abi\":{\"major\":1,\"minor\":0},"
            "\"capabilities\":[\"foundation.startup.v1\"],\"services\":[]},\"schema_version\":1}";
        suffix.insert(suffix.end(), startup.begin(), startup.end());
        suffix.insert(suffix.end(), html.begin(), html.end());
        const auto index_offset = suffix.size();
        suffix.insert(suffix.end(), index.begin(), index.end());
        const auto package_hash = detail::sha256(suffix), index_hash = detail::sha256(span(index));
        const auto package_size = suffix.size();
        suffix.resize(package_size + appended_trailer_bytes);
        auto trailer = std::span(suffix).subspan(package_size);
        const std::string magic = "SFAPND01";
        std::copy(magic.begin(), magic.end(), trailer.begin());
        put(trailer, 8, 1, 4); put(trailer, 12, appended_trailer_bytes, 4);
        put(trailer, 16, prefix_length, 8); put(trailer, 24, package_size, 8);
        put(trailer, 32, index_offset, 8); put(trailer, 40, index.size(), 8); put(trailer, 48, 3, 8);
        std::copy(prefix_sha256.begin(), prefix_sha256.end(), trailer.begin() + 56);
        std::copy(package_hash.begin(), package_hash.end(), trailer.begin() + 88);
        std::copy(index_hash.begin(), index_hash.end(), trailer.begin() + 120);
    }
    Package package() const { return prepare_engine_html_package(suffix, prefix_length, prefix_sha256); }
    Bytes configure() const {
        Bytes body(40); put(body, 0, prefix_length, 8);
        std::copy(prefix_sha256.begin(), prefix_sha256.end(), body.begin() + 8);
        body.insert(body.end(), suffix.begin(), suffix.end());
        return request(FOUNDATION_ENGINE_CONFIGURE, {11, 0, 0, 0}, body);
    }
};

void suffix_validation() {
    Fixture fixture;
    auto package = fixture.package();
    check(package.files.size() == 2 && package.web.entry == "web/index.html" &&
          package.kernel_sha256 == detail::hex_digest(fixture.prefix_sha256),
          "HTML preparation did not retain the actual shared reader's package");
    std::fill(fixture.suffix.begin(), fixture.suffix.begin() + 8, 0xff);
    check(package.find_file("web/.foundation/startup-v1.json")->data.front() == '{',
          "prepared package borrowed the untrusted carrier suffix");
    const auto invalid = [](const Fixture& value, Span bytes, std::uint64_t prefix) {
        bool failed = false;
        try { (void)prepare_engine_html_package(bytes, prefix, value.prefix_sha256); }
        catch (const ContainerError&) { failed = true; }
        check(failed, "corrupt HTML suffix was admitted");
    };
    Fixture valid;
    invalid(valid, Span(valid.suffix).first(100), valid.prefix_length);
    invalid(valid, valid.suffix, valid.prefix_length + 1);
    invalid(valid, valid.suffix, max_appended_kernel_bytes + 1);
    const auto trailer = valid.suffix.size() - appended_trailer_bytes;
    for (const auto offset : std::array<std::size_t, 10>{0, trailer, trailer + 8, trailer + 12,
             trailer + 24, trailer + 32, trailer + 48, trailer + 56, trailer + 88, trailer + 152}) {
        auto corrupt = valid.suffix; corrupt[offset] ^= 1;
        invalid(valid, corrupt, valid.prefix_length);
    }
    auto corrupt_index_hash = valid.suffix; corrupt_index_hash[trailer + 120] ^= 1;
    invalid(valid, corrupt_index_hash, valid.prefix_length);
}

std::shared_ptr<EngineOwner> owner(const Fixture& fixture) {
    EngineOwnerConfiguration configuration; configuration.worker_epoch = 11;
    auto result = std::make_shared<EngineOwner>(fixture.package(), configuration);
    accepted(*result, FOUNDATION_ENGINE_CONFIGURE, {11, 0, 0, 0});
    accepted(*result, FOUNDATION_ENGINE_TURN_ENTER, {11, 0, 0, 0});
    accepted(*result, FOUNDATION_ENGINE_BEGIN_DOCUMENT, {11, 17, 1, 0});
    accepted(*result, FOUNDATION_ENGINE_TURN_LEAVE, {11, 0, 0, 0});
    return result;
}
Bytes full_frame(std::uint64_t base, std::uint8_t red) {
    Bytes body(48 + 800 * 600 * 4);
    put(body, 0, 1, 4); put(body, 4, 800, 4); put(body, 8, 600, 4); put(body, 12, 3200, 4);
    put(body, 24, 800, 4); put(body, 28, 600, 4); put(body, 32, base, 8); put(body, 40, base + 1, 8);
    for (std::size_t n = 48; n < body.size(); n += 4) {
        body[n] = red; body[n + 1] = 23; body[n + 2] = 45; body[n + 3] = 255;
    }
    return body;
}
std::array<std::uint8_t, 3> first_pixel(const gui::Snapshot& view) {
    check(view.widgets.size() == 1, "rich application did not publish exactly one ordinary bitmap");
    const auto& widget = view.widgets.front();
    check(widget.spec.kind == gui::Kind::bitmap && !widget.spec.pointer_input && !widget.spec.context_input &&
          widget.state.actions.empty() && view.client_size == gui::Size{800, 600},
          "rich application advertised an unsupported physical surface capability");
    std::array<std::uint8_t, 3> pixel{}; bool painted = false;
    widget.state.bitmap.source.paint({800, 600, {0, 0, 1, 1}, gui::PixelFormat::rgb24},
        [&](unsigned x, unsigned y, gui::PixelBlock block) {
            check(x == 0 && y == 0 && block.bytes.size() >= 3, "copied frame paint changed its damage origin");
            std::copy_n(block.bytes.begin(), 3, pixel.begin()); painted = true;
        });
    check(painted, "copied frame source did not paint"); return pixel;
}
class FailingAdapter final : public gui::RetainedAdapter {
public:
    bool fail_next{};
    void present(gui::Snapshot snapshot) override {
        if (std::exchange(fail_next, false)) throw std::runtime_error("injected rich presentation failure");
        gui::RetainedAdapter::present(std::move(snapshot));
    }
};
void frame_publishing_and_retry() {
    Fixture fixture; auto engine = owner(fixture); FailingAdapter adapter;
    AppendedEngineApplication application(adapter, engine);
    check(application.view().widgets.empty() && AppendedEngineApplication::physical_surface_capabilities() == 0,
          "rich application fabricated a frame or unsupported capability");
    const auto id = engine->identity();
    auto bytes = full_frame(0, 61);
    accepted(*engine, FOUNDATION_ENGINE_TURN_ENTER, id);
    accepted(*engine, FOUNDATION_ENGINE_FRAME_COMMIT, id, bytes);
    application.tick();
    check(adapter.snapshot().widgets.empty(), "engine callback published into an adapter before turn return");
    accepted(*engine, FOUNDATION_ENGINE_TURN_LEAVE, id);
    application.tick();
    const auto initial = application.view();
    check(first_pixel(initial) == std::array<std::uint8_t, 3>{61, 23, 45}, "opaque engine frame lost RGB bytes");
    std::fill(bytes.begin(), bytes.end(), 0xff);
    check(first_pixel(initial)[0] == 61, "GUI snapshot borrowed the frame transfer buffer");
    bytes = full_frame(1, 71);
    accepted(*engine, FOUNDATION_ENGINE_FRAME_COMMIT, id, bytes);
    adapter.fail_next = true; bool failed = false;
    try { application.tick(); } catch (const std::runtime_error&) { failed = true; }
    check(failed && application.presentation_pending() && first_pixel(adapter.snapshot())[0] == 61 &&
          first_pixel(application.view())[0] == 71, "presentation failure lost the committed owned frame");
    const auto revision = application.view().revision, epoch = application.input_epoch();
    application.retry_presentation(); application.tick();
    check(!application.presentation_pending() && application.view().revision == revision &&
          application.input_epoch() == epoch && engine->frame()->frame_revision == 2 &&
          first_pixel(adapter.snapshot())[0] == 71 && first_pixel(initial)[0] == 61,
          "rich presentation retry reran an engine effect or mutated an older frame");
    bytes = full_frame(2, 81); bytes[51] = 254;
    const auto rejected = invoke(*engine, FOUNDATION_ENGINE_FRAME_COMMIT, id, bytes);
    check(get(rejected, 72, 4) == FOUNDATION_ENGINE_UNSUPPORTED && engine->frame()->frame_revision == 2,
          "nonopaque RGBA replaced an accepted frame");
    application.handle(gui::ResizeEvent{{1000, 700}, 2});
    check(application.view().client_size == gui::Size{800, 600}, "fixed profile accepted an unsupported resize");
    accepted(*engine, FOUNDATION_ENGINE_BEGIN_DOCUMENT, {11, 17, 2, 0});
    application.tick(); check(application.view().widgets.empty(), "new document retained the old document frame");
    bytes = full_frame(0, 91); accepted(*engine, FOUNDATION_ENGINE_FRAME_COMMIT, engine->identity(), bytes);
    application.tick(); check(first_pixel(adapter.snapshot())[0] == 91, "new document could not replace the bitmap lifetime");
    const auto second = engine->identity();
    accepted(*engine, FOUNDATION_ENGINE_FRAME_COMMIT, second, full_frame(1, 99));
    adapter.fail_next = true; failed = false;
    try { application.tick(); } catch (const std::runtime_error&) { failed = true; }
    check(failed && application.presentation_pending(), "active-turn shutdown fixture has no pending frame");
    accepted(*engine, FOUNDATION_ENGINE_TURN_ENTER, second);
    application.handle(gui::CloseEvent{});
    check(!engine->closed() && !adapter.closed(), "rich shutdown tore down an active native turn");
    const auto after_close = invoke(*engine, FOUNDATION_ENGINE_FRAME_COMMIT, second, full_frame(2, 101));
    check(get(after_close, 72, 4) == FOUNDATION_ENGINE_CLOSED,
          "rich shutdown did not revoke engine admission during the active turn");
    accepted(*engine, FOUNDATION_ENGINE_TURN_LEAVE, second);
    application.retry_presentation();
    check(engine->closed() && adapter.closed(), "rich application shutdown left its owner or adapter open");
}

void host_preparation() {
    Fixture fixture; const auto input = fixture.configure(); Bytes output(2048);
    const auto untouched = output;
    check(gui_web_engine_input_describe_v1(output.data(), output.size()) == FOUNDATION_ENGINE_BAD_OPERATION &&
          output == untouched,
          "default bitmap host advertised or mutated an unsupported physical profile");
    check(gui_web_engine_bridge_v1() == FOUNDATION_ENGINE_BRIDGE_VERSION, "rich producer marker changed");
#if defined(FOUNDATION_APPENDED_BINARY_CAPABILITY) && FOUNDATION_APPENDED_BINARY_CAPABILITY
    check(gui_web_engine_profile_v1() == 2, "binary-capable rich host did not report its immutable profile");
#else
    check(gui_web_engine_profile_v1() == 1, "VM-free rich host did not report its immutable profile");
#endif
    auto call = [&](Span bytes, std::size_t capacity) {
        return gui_web_engine_dispatch_v1(FOUNDATION_ENGINE_CONFIGURE, bytes.data(), bytes.size(), output.data(), capacity);
    };
    check(call(input, FOUNDATION_ENGINE_RECEIPT_BYTES - 1) == FOUNDATION_ENGINE_REPLY_TOO_SMALL,
          "host accepted an incomplete receipt destination");
    check(call(input, FOUNDATION_ENGINE_RECEIPT_BYTES) == FOUNDATION_ENGINE_REPLY_TOO_SMALL,
          "host initialized before the complete configure metadata reply fit");
    auto corrupt = input; corrupt.back() = 1;
    check(call(corrupt, output.size()) == FOUNDATION_ENGINE_RECEIPT_BYTES && get(output, 72, 4) == FOUNDATION_ENGINE_INVALID,
          "host admitted corrupt raw suffix bytes");
    const auto count = call(input, output.size());
    check(count > static_cast<std::int32_t>(FOUNDATION_ENGINE_RECEIPT_BYTES) && get(output, 72, 4) == FOUNDATION_ENGINE_OK,
          "undersized/corrupt preparation attempt had an effect on a later valid configure");
    const auto metadata = gui::web_detail::Parser(std::string_view(
        reinterpret_cast<const char*>(output.data() + FOUNDATION_ENGINE_RECEIPT_BYTES),
        static_cast<std::size_t>(count) - FOUNDATION_ENGINE_RECEIPT_BYTES)).parse();
    check(metadata.at("application_name").str() == "Owned fixture" &&
          metadata.at("entry_url").str() == "app://" + fixture.package().package_sha256 + "/web/index.html",
          "host configure metadata did not come from the shared verified Package");
    check(call(input, output.size()) == FOUNDATION_ENGINE_RECEIPT_BYTES && get(output, 72, 4) == FOUNDATION_ENGINE_CONFLICT,
          "host replaced a prepared owner");
    const auto initial = gui::web_detail::Parser(gui_web_create("rich-test")).parse();
    check(initial.at("snapshot").at("title").str() == "Owned fixture", "generic browser did not consume the rich application");
    auto bridge = [&](std::uint32_t operation, EngineIdentity identity, Span body = {}) {
        const auto bytes = request(operation, identity, body);
        const auto result = gui_web_engine_dispatch_v1(operation, bytes.data(), bytes.size(), output.data(), output.size());
        check(result == FOUNDATION_ENGINE_RECEIPT_BYTES && get(output, 72, 4) == FOUNDATION_ENGINE_OK,
              "host copied-owner operation was rejected");
    };
    bridge(FOUNDATION_ENGINE_TURN_ENTER, {11, 0, 0, 0});
    bridge(FOUNDATION_ENGINE_BEGIN_DOCUMENT, {11, 17, 1, 0});
    const EngineIdentity identity{11, 17, 1, get(output, 40, 8)};
    bridge(FOUNDATION_ENGINE_FRAME_COMMIT, identity, full_frame(0, 131));
    bridge(FOUNDATION_ENGINE_TURN_LEAVE, {11, 0, 0, 0});
    const auto before_poll = gui::web_detail::Parser(gui_web_receive(
        "{\"epoch\":\"other\",\"seq\":\"1\",\"operation\":{\"type\":\"poll\"}}")).parse();
    check(before_poll.at("snapshot").at("widgets").array().empty(),
          "bridge callback presented before the later owner/browser task");
    std::string state = gui_web_receive(
        "{\"epoch\":\"rich-test\",\"seq\":\"1\",\"operation\":{\"type\":\"poll\"}}");
    // The public parser bounds incoming operations to 1 MiB. Outgoing bitmap
    // states have their separate larger budget; inspect their owned RGB value
    // before parsing the small remaining structure with that request parser.
    const auto rgb_field = state.find("\"rgb\":\"");
    check(rgb_field != std::string::npos, "later browser poll omitted its copied RGB image");
    const auto rgb_start = rgb_field + 7, rgb_end = state.find('"', rgb_start);
    check(rgb_end != std::string::npos && rgb_end - rgb_start == 800 * 600 * 4 &&
          state.compare(rgb_start, 4, "gxct") == 0,
          "later browser state changed its fixed-profile copied RGB bytes");
    state.erase(rgb_start, rgb_end - rgb_start);
    const auto after_poll = gui::web_detail::Parser(state).parse();
    check(after_poll.at("snapshot").at("widgets").array().size() == 1,
          "later browser poll did not publish the accepted engine frame");
    gui_web_destroy();
}
} // namespace

int main() {
    try {
        suffix_validation(); frame_publishing_and_retry(); host_preparation();
        std::cout << "Rich GUI copied frames, turn barrier, retry and canonical HTML preparation passed\n";
    } catch (const std::exception& error) {
        gui_web_destroy(); std::cerr << error.what() << '\n'; return 1;
    }
}
