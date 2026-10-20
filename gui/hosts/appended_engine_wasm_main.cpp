#include "host/browser.hpp"
#include "shared/appended_engine_abi.h"
#include "shared/appended_engine_application.hpp"
#include "shared/engine_primary_region_application.hpp"
#include "shared/appended_engine_module.hpp"
#include "shared/appended_demo_services.hpp"
#ifndef FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE
#define FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE 0
#endif
#if FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE < 0 || FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE > 3
#error "Document profile must be 0 (disabled), 1 (pixel1795), 2 (physical2003), or 3 (editor2035)"
#endif
#if FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE && defined(FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED) && FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED
#error "Document and legacy input profiles cannot be enabled together"
#endif
#if FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 1 || FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 2
#include <appended_engine_compiled_document_profile.hpp>
#elif FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 3
#include <appended_engine_compiled_editor_profile.hpp>
#endif
#if (defined(FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED) && FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED) || FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE >= 2
#include "host/browser_surface_composition.hpp"
#endif
#if defined(FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED) && FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED
#include "appended_engine_compiled_input_profile.hpp"
#endif

#include <algorithm>
#include <array>
#include <cstring>
#include <limits>
#include <memory>
#include <stdexcept>
#include <vector>
#ifdef __EMSCRIPTEN__
#include <emscripten/heap.h>
#endif

namespace {
using foundation::appended::EngineOwner;
using foundation::appended::EngineOwnerConfiguration;
using foundation::appended::ServiceStatus;
using Bytes = std::vector<std::uint8_t>;
using Span = std::span<const std::uint8_t>;
constexpr std::size_t header_bytes = FOUNDATION_ENGINE_HEADER_BYTES;
constexpr std::size_t receipt_bytes = FOUNDATION_ENGINE_RECEIPT_BYTES;
constexpr std::size_t configure_metadata_bytes = 40;
constexpr std::size_t max_configure_bytes = header_bytes + configure_metadata_bytes +
    foundation::appended::max_appended_package_bytes + foundation::appended::appended_trailer_bytes;
std::shared_ptr<EngineOwner> prepared_owner;
const foundation::appended::engine_input::EngineSurfaceProfileFacts& input_profile() {
#if defined(FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED) && FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED
    return foundation::appended::engine_input::compiled_engine_surface_profile;
#else
    static const foundation::appended::engine_input::EngineSurfaceProfileFacts disabled;
    return disabled;
#endif
}
#if FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 1 || FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 2
const foundation::appended::engine_document::EngineDocumentProfileFacts& document_profile() {
    return foundation::appended::engine_document::compiled_engine_document_profile;
}
bool document_profile_valid() noexcept {
    namespace document = foundation::appended::engine_document;
    const auto& facts = document_profile();
    constexpr auto kind = FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 1 ? document::ProfileKind::pixel : document::ProfileKind::physical;
    return document::document_profile_valid(facts) && facts.kind == kind &&
        facts.target_system == BIB_ENGINE_TARGET_BROWSER_WASM && facts.target_processor == BIB_ENGINE_CPU_WASM32 && facts.pointer_bits == 32;
}
#elif FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 3
const foundation::appended::engine_editor::EngineEditorProfileFacts& editor_profile() {
    return foundation::appended::engine_editor::compiled_engine_editor_profile;
}
bool editor_profile_valid() noexcept {
    namespace editor = foundation::appended::engine_editor;
    const auto& facts = editor_profile();
    return editor::editor_profile_valid(facts) &&
        facts.target_system == BIB_ENGINE_TARGET_BROWSER_WASM && facts.target_processor == BIB_ENGINE_CPU_WASM32 && facts.pointer_bits == 32;
}
#endif
#if (defined(FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED) && FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED) || FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 2
class BrowserEngineSurfacePort final : public foundation::ui::EngineSurfacePort {
    foundation::host::BrowserSurfaceAdapter& adapter_;
public:
    explicit BrowserEngineSurfacePort(foundation::host::BrowserSurfaceAdapter& value) : adapter_(value) {}
    const foundation::gui_surface::Capabilities& capabilities() const noexcept override { return adapter_.capabilities(); }
    std::uint64_t generation() const noexcept override { return adapter_.generation(); }
    foundation::gui_surface::CommitResult present_pair(gui::Snapshot snapshot,
            const foundation::gui_surface::Presentation& presentation) override {
        return adapter_.present_pair(std::move(snapshot), presentation);
    }
    void set_owned_service_active(bool active) override { adapter_.set_owned_service_active(active); }
};
std::unique_ptr<foundation::ui::EngineSurfacePort> make_surface_port(gui::Adapter& adapter) {
    auto* browser = dynamic_cast<foundation::host::BrowserSurfaceAdapter*>(&adapter);
    if (!browser) throw std::invalid_argument("Rich physical input requires its composition-owned surface port");
    return std::make_unique<BrowserEngineSurfacePort>(*browser);
}
#elif FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE != 3
std::unique_ptr<foundation::ui::EngineSurfacePort> make_surface_port(gui::Adapter&) { return {}; }
#endif
#if FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 3
class BrowserEngineEditorPort final : public foundation::ui::EngineEditorPort {
    foundation::host::BrowserSurfaceAdapter& adapter_;
public:
    explicit BrowserEngineEditorPort(foundation::host::BrowserSurfaceAdapter& value) : adapter_(value) {}
    const foundation::gui_surface::Capabilities& capabilities() const noexcept override { return adapter_.capabilities(); }
    std::uint64_t generation() const noexcept override { return adapter_.generation(); }
    foundation::gui_surface::CommitResult present_pair(gui::Snapshot snapshot,
            const foundation::gui_surface::Presentation& presentation) override {
        return adapter_.present_pair(std::move(snapshot), presentation);
    }
    foundation::gui_surface::CommitResult present_editor_pair(gui::Snapshot snapshot,
            const foundation::gui_surface::Presentation& presentation,
            std::optional<foundation::gui_editor::EditorPublication> publication,
            std::optional<foundation::gui_editor::CompositionFact> composition) override {
        return adapter_.present_editor_pair(std::move(snapshot), presentation,
            std::move(publication), std::move(composition));
    }
    foundation::gui_surface::CommitResult present_editor_retirement(gui::Snapshot snapshot,
            foundation::gui_editor::EditorPublication publication) override {
        return adapter_.present_editor_retirement(std::move(snapshot), std::move(publication));
    }
    void set_owned_service_active(bool active) override { adapter_.set_owned_service_active(active); }
};
foundation::ui::BoundEngineEditorPort make_editor_port(gui::Adapter& adapter) {
    auto* browser = dynamic_cast<foundation::host::BrowserSurfaceAdapter*>(&adapter);
    if (!browser || !browser->editor_endpoint_bound())
        throw std::invalid_argument("Rich editor input requires its composition-owned bound editor port");
    return {std::make_unique<BrowserEngineEditorPort>(*browser)};
}
#endif
// Private maintained rich-entry successor. Startup intent is admitted by the
// shared owner/root. Web primary keeps its original null-region behavior.
class PreparedApplication final : public foundation::ui::EnginePrimaryRegionApplication {
public:
    explicit PreparedApplication(gui::Adapter& adapter)
#if FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 3
        : EnginePrimaryRegionApplication(adapter, prepared_owner, editor_profile(), make_editor_port(adapter)) {}
#elif FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE
        : EnginePrimaryRegionApplication(adapter, prepared_owner, document_profile(), make_surface_port(adapter)) {}
#else
        : EnginePrimaryRegionApplication(adapter, prepared_owner, make_surface_port(adapter), input_profile()) {}
#endif
};
#if (defined(FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED) && FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED) || FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE >= 2
using Runtime = foundation::host::Browser<PreparedApplication, foundation::host::BrowserSurfaceComposition>;
#else
using Runtime = foundation::host::Browser<PreparedApplication>;
#endif
std::unique_ptr<Runtime> runtime;
bool runtime_close_requested = false;
std::string response;
std::uint64_t next_runtime = 1;

std::uint64_t little(Span input, std::size_t offset, std::size_t width) {
    std::uint64_t result = 0;
    for (std::size_t n = 0; n < width; ++n) result |= std::uint64_t(input[offset + n]) << (8 * n);
    return result;
}
void put(std::span<std::uint8_t> output, std::size_t offset, std::uint64_t value, std::size_t width) {
    for (std::size_t n = 0; n < width; ++n) output[offset + n] = static_cast<std::uint8_t>(value >> (8 * n));
}
bool local_range(const void* pointer, std::size_t length) noexcept {
    if (!pointer) return length == 0;
    const auto start = reinterpret_cast<std::uintptr_t>(pointer);
    if (length > std::numeric_limits<std::uintptr_t>::max() - start) return false;
#ifdef __EMSCRIPTEN__
    const auto heap = emscripten_get_heap_size();
    if (start > heap || length > heap - start) return false;
#endif
    return true;
}
bool disjoint(const void* input, std::size_t n, const void* output, std::size_t capacity) noexcept {
    const auto first = reinterpret_cast<std::uintptr_t>(input), second = reinterpret_cast<std::uintptr_t>(output);
    return first <= second ? n <= second - first : capacity <= first - second;
}
bool configure_header(Span input) {
    return input.size() >= header_bytes && input.size() <= max_configure_bytes &&
        input[0] == 'F' && input[1] == 'K' && input[2] == 'B' && input[3] == '1' &&
        little(input, 4, 2) == FOUNDATION_ENGINE_RECORD_VERSION &&
        little(input, 6, 2) == FOUNDATION_ENGINE_CONFIGURE && little(input, 8, 4) == input.size() &&
        little(input, 12, 4) == 0 && little(input, 16, 8) != 0 &&
        little(input, 24, 8) == 0 && little(input, 32, 8) == 0 && little(input, 40, 8) == 0 &&
        little(input, 48, 8) == 0 && little(input, 56, 4) == 0 && little(input, 60, 4) == 0 &&
        little(input, 64, 4) == input.size() - header_bytes && little(input, 68, 4) == 0 &&
        input.size() >= header_bytes + configure_metadata_bytes + foundation::appended::appended_trailer_bytes;
}
std::int32_t receipt(Span input, std::span<std::uint8_t> output, std::uint32_t control, ServiceStatus service) {
    if (output.size() < receipt_bytes) return FOUNDATION_ENGINE_REPLY_TOO_SMALL;
    std::copy_n(input.begin(), header_bytes, output.begin());
    put(output, 6, FOUNDATION_ENGINE_CONFIGURE | FOUNDATION_ENGINE_REPLY_KIND, 2);
    put(output, 8, receipt_bytes, 4); put(output, 64, receipt_bytes - header_bytes, 4);
    put(output, header_bytes, control, 4); put(output, header_bytes + 4, static_cast<std::uint32_t>(service), 4);
    return static_cast<std::int32_t>(receipt_bytes);
}
std::int32_t configure(Span input, std::span<std::uint8_t> output) {
    if (!configure_header(input)) return FOUNDATION_ENGINE_BAD_RECORD;
    if (output.size() < receipt_bytes) return FOUNDATION_ENGINE_REPLY_TOO_SMALL;
#if defined(FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED) && FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED
    if (!foundation::appended::engine_input::input_profile_valid(input_profile()))
        return receipt(input, output, FOUNDATION_ENGINE_UNSUPPORTED, ServiceStatus::unavailable);
#endif
#if FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 1 || FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 2
    if (!document_profile_valid())
        return receipt(input, output, FOUNDATION_ENGINE_UNSUPPORTED, ServiceStatus::unavailable);
#elif FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 3
    if (!editor_profile_valid())
        return receipt(input, output, FOUNDATION_ENGINE_UNSUPPORTED, ServiceStatus::unavailable);
#endif
    if (runtime || prepared_owner) return receipt(input, output, FOUNDATION_ENGINE_CONFLICT, ServiceStatus::conflict);
    try {
        const auto body = input.subspan(header_bytes);
        std::array<std::uint8_t, 32> prefix_sha256{};
        std::copy_n(body.begin() + 8, prefix_sha256.size(), prefix_sha256.begin());
        auto package = foundation::ui::prepare_engine_html_package(body.subspan(configure_metadata_bytes),
                                                                  little(body, 0, 8), prefix_sha256);
        if (!package.web.present || !package.web.entry)
            return receipt(input, output, FOUNDATION_ENGINE_INVALID, ServiceStatus::invalid_request);
        const auto metadata = gui::web_detail::encode(gui::web_detail::Json::Object{
            {"application_name", package.application.name},
            {"package_sha256", package.package_sha256},
            {"entry_url", "app://" + package.package_sha256 + "/" + *package.web.entry}});
        const auto required = receipt_bytes + metadata.size();
        // Check complete success space before module construction/init or any
        // native handler can run. A retry cannot repeat an accepted effect.
        if (output.size() < required) return FOUNDATION_ENGINE_REPLY_TOO_SMALL;
        EngineOwnerConfiguration configuration;
        configuration.startup_primary = foundation::appended::read_engine_startup_primary(package);
        configuration.native_services = foundation::ui::demo_native_services();
        configuration.worker_epoch = little(input, 16, 8);
        configuration.abandon_closed_document_outcomes = true;
        configuration.defer_copied_close_to_application = true;
#if FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 3
        configuration.editor_profile = editor_profile();
#elif FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE
        configuration.document_profile = document_profile();
#else
        configuration.input_profile = input_profile();
#endif
#if defined(FOUNDATION_APPENDED_BINARY_CAPABILITY) && FOUNDATION_APPENDED_BINARY_CAPABILITY
        configuration.module_factory = configuration.startup_primary == foundation::appended::EngineStartupPrimary::binary
            ? foundation::appended::make_engine_binary_view_module_binding
            : foundation::appended::make_engine_module_binding;
#endif
        auto owner = std::make_shared<EngineOwner>(std::move(package), std::move(configuration));
        // Consume the binary startup slot before the one admitted factory/
        // guest initialization. A failed attempt remains a closed prepared
        // owner, so retrying CONFIGURE cannot repeat an initialization effect.
        if(owner->startup_primary()==foundation::appended::EngineStartupPrimary::binary) prepared_owner=owner;
        std::array<std::uint8_t, header_bytes> request{};
        std::copy_n(input.begin(), header_bytes, request.begin());
        put(request, 8, header_bytes, 4); put(request, 64, 0, 4);
        std::array<std::uint8_t, receipt_bytes> reply{};
        const auto result = owner->dispatch(FOUNDATION_ENGINE_CONFIGURE, request, reply);
        if (result < 0) return result;
        if (result != static_cast<std::int32_t>(receipt_bytes)) return FOUNDATION_ENGINE_EXCEPTION;
        std::copy(reply.begin(), reply.end(), output.begin());
        if (little(reply, header_bytes, 4) != FOUNDATION_ENGINE_OK ||
            little(reply, header_bytes + 4, 4) != static_cast<std::uint32_t>(ServiceStatus::ok) ||
            !owner->configured()) return result;
        if(owner->startup_primary() == foundation::appended::EngineStartupPrimary::binary) {
            // CONFIGURE already accepted the one actual Module initialization.
            // Reserve that attempt before any bounded bootstrap step, including
            // failure, so another CONFIGURE cannot repeat its guest effects.
            prepared_owner=owner;
            try {
                auto model=owner->binary_view();
                if(model && !model->snapshot().revision) owner->tick_binary_view();
                model=owner->binary_view();
                if(!model || !model->snapshot().revision)
                    throw std::invalid_argument("Binary primary needs an actual initial view after one bounded bootstrap step");
            } catch(...) { owner->close(); throw; }
        }
        std::copy(metadata.begin(), metadata.end(), output.begin() + receipt_bytes);
        put(output, 8, required, 4); put(output, 64, required - header_bytes, 4);
        prepared_owner = std::move(owner);
        return static_cast<std::int32_t>(required);
    } catch (const foundation::appended::ContainerError&) {
        return receipt(input, output, FOUNDATION_ENGINE_INVALID, ServiceStatus::invalid_request);
    } catch (const std::invalid_argument&) {
        return receipt(input, output, FOUNDATION_ENGINE_INVALID, ServiceStatus::invalid_request);
    } catch (...) {
        return receipt(input, output, FOUNDATION_ENGINE_INTERNAL, ServiceStatus::internal_error);
    }
}
} // namespace

extern "C" {
// Private producer marker for this separate rich host. It never changes the
// accepted binary host or portable guest's exports.
std::uint32_t gui_web_engine_bridge_v1() { return FOUNDATION_ENGINE_BRIDGE_VERSION; }
std::uint32_t gui_web_engine_profile_v1() {
#if defined(FOUNDATION_APPENDED_BINARY_CAPABILITY) && FOUNDATION_APPENDED_BINARY_CAPABILITY
    return 2;
#else
    return 1;
#endif
}
// Typed Foundation GUI composition facts. This describes actually bound
// factories in this source generation, never the requested payload mode.
std::int32_t gui_web_application_composition_v1() {
#if defined(FOUNDATION_APPENDED_BINARY_CAPABILITY) && FOUNDATION_APPENDED_BINARY_CAPABILITY
    return 7; // Compiled primary, actual single-Module binary view, one web region.
#else
    return 5; // Compiled primary and one web region; no binary factory reference.
#endif
}
// Read-only compiled facts, available before CONFIGURE or an engine factory.
// Only the explicitly selected, fully verified generated header can supply
// these facts. A symbol or an existing physical profile never selects NDV2.
std::int32_t gui_web_engine_document_describe_v1(unsigned char* output, std::size_t capacity) noexcept {
#if FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 1 || FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 2
    if (!document_profile_valid()) return FOUNDATION_ENGINE_BAD_OPERATION;
    if (!output || !local_range(output, capacity)) return FOUNDATION_ENGINE_BAD_RECORD;
    try {
        namespace document = foundation::appended::engine_document;
        const auto& facts = document_profile();
        const auto digest = [](const auto& bytes) {
            constexpr char digits[] = "0123456789abcdef";
            std::string result; result.reserve(bytes.size() * 2);
            for (const auto byte : bytes) { result += digits[byte >> 4]; result += digits[byte & 15]; }
            return result;
        };
        gui::web_detail::Json::Object fields{
            {"schema_version", 1}, {"kind", "foundation-copied-engine-document-v2"},
            {"target", "browser-wasm32"}, {"binding", "copied-owner-bridge/direct-worker-document-v2"},
            {"pointer_bits", static_cast<int>(facts.pointer_bits)}, {"pthread", false}, {"shared_memory", false},
            {"bridge_abi", static_cast<int>(FOUNDATION_ENGINE_BRIDGE_VERSION)},
            {"capabilities", std::to_string(facts.provider_capabilities)},
            {"contract_sha256", digest(facts.contract_sha256)}, {"build_sha256", digest(facts.build_sha256)},
            {"source_recipe_sha256", digest(facts.source_recipe_sha256)},
            {"provider_abi_major", static_cast<int>(facts.provider_abi_major)},
            {"provider_abi_minor", static_cast<int>(facts.provider_abi_minor)},
            {"host_abi_major", static_cast<int>(facts.host_abi_major)}, {"host_abi_minor", static_cast<int>(facts.host_abi_minor)},
            {"document_profile", facts.name}, {"base_header_sha256", digest(facts.base_header_sha256)},
            {"extension_header_sha256", digest(facts.extension_header_sha256)},
            {"document_catalog_sha256", digest(facts.catalog_sha256)},
            {"document_schema_sha256", digest(document::kSchema)}, {"action_ack_schema_sha256", digest(document::kAckSchema)},
            {"viewport_width", static_cast<int>(facts.viewport_width)}, {"viewport_height", static_cast<int>(facts.viewport_height)}};
#if FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 2
        fields.emplace("command_catalog_sha256", digest(facts.physical_catalog_sha256));
        fields.emplace("surface_protocol_version", static_cast<int>(foundation::appended::engine_input::kSurfaceProtocolVersion));
        fields.emplace("surface_capabilities", std::to_string(foundation::appended::engine_input::kSurfaceCapabilities));
        fields.emplace("mouse_input_version", static_cast<int>(foundation::appended::engine_input::kMouseInputVersion));
        fields.emplace("key_mapping_version", static_cast<int>(foundation::appended::engine_input::kRawKeyMappingRevision));
        fields.emplace("display_scale", 1.0);
#endif
        const auto description = gui::web_detail::encode(gui::web_detail::Json(std::move(fields)));
        if (description.empty() || description.size() >= 4096) return FOUNDATION_ENGINE_EXCEPTION;
        if (capacity < description.size()) return FOUNDATION_ENGINE_REPLY_TOO_SMALL;
        std::copy(description.begin(), description.end(), output);
        return static_cast<std::int32_t>(description.size());
    } catch (...) { return FOUNDATION_ENGINE_EXCEPTION; }
#else
    (void)output; (void)capacity;
    return FOUNDATION_ENGINE_BAD_OPERATION;
#endif
}
// The editor descriptor has a distinct schema and entry point. In particular,
// selector3 never advertises an old1795/2003 or physical467 descriptor.
std::int32_t gui_web_engine_editor_describe_v1(unsigned char* output, std::size_t capacity) noexcept {
#if FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 3
    if (!editor_profile_valid()) return FOUNDATION_ENGINE_BAD_OPERATION;
    if (!output || !local_range(output, capacity)) return FOUNDATION_ENGINE_BAD_RECORD;
    try {
        namespace editor = foundation::appended::engine_editor;
        namespace document = foundation::appended::engine_document;
        const auto& facts = editor_profile();
        const auto digest = [](const auto& bytes) {
            constexpr char digits[] = "0123456789abcdef";
            std::string result; result.reserve(bytes.size() * 2);
            for (const auto byte : bytes) { result += digits[byte >> 4]; result += digits[byte & 15]; }
            return result;
        };
        const auto description = gui::web_detail::encode(gui::web_detail::Json::Object{
            {"schema_version", 1}, {"kind", "foundation-copied-engine-editor-v1"},
            {"target", "browser-wasm32"}, {"binding", "copied-owner-bridge/direct-worker-editor-v1"},
            {"pointer_bits", static_cast<int>(facts.pointer_bits)}, {"pthread", false}, {"shared_memory", false},
            {"bridge_abi", static_cast<int>(FOUNDATION_ENGINE_BRIDGE_VERSION)},
            {"capabilities", std::to_string(facts.provider_capabilities)},
            {"contract_sha256", digest(facts.contract_sha256)}, {"build_sha256", digest(facts.build_sha256)},
            {"source_recipe_sha256", digest(facts.source_recipe_sha256)},
            {"provider_abi_major", static_cast<int>(facts.provider_abi_major)},
            {"provider_abi_minor", static_cast<int>(facts.provider_abi_minor)},
            {"host_abi_major", static_cast<int>(facts.host_abi_major)}, {"host_abi_minor", static_cast<int>(facts.host_abi_minor)},
            {"editor_profile", facts.name}, {"base_header_sha256", digest(facts.base_header_sha256)},
            {"document_header_sha256", digest(facts.document_header_sha256)},
            {"document_contract_sha256", digest(facts.document_contract_sha256)},
            {"document_catalog_sha256", digest(facts.document_catalog_sha256)},
            {"physical_catalog_sha256", digest(facts.physical_catalog_sha256)},
            {"editor_header_sha256", digest(facts.editor_header_sha256)},
            {"editor_catalog_sha256", digest(facts.catalog_sha256)}, {"editor_schema_sha256", digest(facts.schema_sha256)},
            {"document_schema_sha256", digest(document::kSchema)}, {"action_ack_schema_sha256", digest(document::kAckSchema)},
            {"viewport_width", static_cast<int>(facts.viewport_width)}, {"viewport_height", static_cast<int>(facts.viewport_height)},
            {"surface_protocol_version", static_cast<int>(facts.surface_protocol_version)},
            {"surface_capabilities", std::to_string(facts.surface_capabilities)},
            {"mouse_input_version", static_cast<int>(foundation::appended::engine_input::kMouseInputVersion)},
            {"key_mapping_version", static_cast<int>(foundation::appended::engine_input::kRawKeyMappingRevision)},
            {"editor_protocol_version", static_cast<int>(facts.editor_protocol_version)}, {"display_scale", 1},
            {"editor_query_max_bytes", static_cast<int>(editor::kQueryRequestMaximum)},
            {"editor_reply_capacity", static_cast<int>(editor::kReplyCapacity)},
            {"editor_command_max_bytes", static_cast<int>(BIB_ENGINE_EDITOR_MAX_WIRE_BYTES)}});
        if (description.empty() || description.size() >= 4096) return FOUNDATION_ENGINE_EXCEPTION;
        if (capacity < description.size()) return FOUNDATION_ENGINE_REPLY_TOO_SMALL;
        std::copy(description.begin(), description.end(), output);
        return static_cast<std::int32_t>(description.size());
    } catch (...) { return FOUNDATION_ENGINE_EXCEPTION; }
#else
    (void)output; (void)capacity;
    return FOUNDATION_ENGINE_BAD_OPERATION;
#endif
}
// The default host deliberately has no physical profile to describe.
std::int32_t gui_web_engine_input_describe_v1(unsigned char* output, std::size_t capacity) noexcept {
    const auto& facts = input_profile();
    if (!foundation::appended::engine_input::input_profile_valid(facts)) return FOUNDATION_ENGINE_BAD_OPERATION;
    if (!output || !local_range(output, capacity)) return FOUNDATION_ENGINE_BAD_RECORD;
    try {
        const auto digest = [](const auto& bytes) {
            constexpr char digits[] = "0123456789abcdef";
            std::string result; result.reserve(bytes.size() * 2);
            for (const auto byte : bytes) { result += digits[byte >> 4]; result += digits[byte & 15]; }
            return result;
        };
        const auto description = gui::web_detail::encode(gui::web_detail::Json::Object{
            {"schema_version", 1}, {"kind", "foundation-copied-engine-physical-v1"},
            {"target", "browser-wasm32"}, {"binding", "copied-owner-bridge/direct-worker-physical-v1"},
            {"pointer_bits", 32}, {"pthread", false}, {"shared_memory", false},
            {"bridge_abi", static_cast<int>(FOUNDATION_ENGINE_BRIDGE_VERSION)}, {"capabilities", std::to_string(facts.provider_capabilities)},
            {"contract_sha256", digest(facts.contract_sha256)}, {"build_sha256", digest(facts.build_sha256)},
            {"source_recipe_sha256", digest(facts.source_recipe_sha256)}, {"command_catalog_sha256", digest(facts.catalog_sha256)},
            {"surface_protocol_version", static_cast<int>(facts.surface_protocol_version)},
            {"surface_capabilities", std::to_string(facts.surface_capabilities)},
            {"mouse_input_version", static_cast<int>(facts.mouse_input_version)}, {"key_mapping_version", static_cast<int>(facts.raw_key_mapping_revision)},
            {"viewport_width", static_cast<int>(facts.viewport_width)}, {"viewport_height", static_cast<int>(facts.viewport_height)}, {"display_scale", facts.display_scale}});
        if (description.empty() || description.size() >= 4096) return FOUNDATION_ENGINE_EXCEPTION;
        if (capacity < description.size()) return FOUNDATION_ENGINE_REPLY_TOO_SMALL;
        std::copy(description.begin(), description.end(), output);
        return static_cast<std::int32_t>(description.size());
    } catch (...) { return FOUNDATION_ENGINE_EXCEPTION; }
}
std::int32_t gui_web_engine_dispatch_v1(std::uint32_t operation, const unsigned char* input,
        std::size_t length, unsigned char* output, std::size_t capacity) noexcept {
    if (!local_range(input, length) || !local_range(output, capacity) ||
        !disjoint(input, length, output, capacity) || !input || !output)
        return FOUNDATION_ENGINE_BAD_RECORD;
    if (operation == FOUNDATION_ENGINE_CONFIGURE) {
        if (length > max_configure_bytes) return FOUNDATION_ENGINE_BAD_RECORD;
        return configure({input, length}, {output, capacity});
    }
    if (length > header_bytes + 16u * 1024u * 1024u || length < header_bytes)
        return FOUNDATION_ENGINE_BAD_RECORD;
    if (!prepared_owner) return FOUNDATION_ENGINE_BAD_RECORD;
    // TURN_LEAVE can still be executing inside the engine's host callback when
    // native depth reaches zero. The base Worker schedules an ordinary browser
    // tick after the engine export returns; bridge callbacks never present.
    const auto written = prepared_owner->dispatch(operation, {input, length}, {output, capacity});
    // A validated close first retires the application's actual editor/input
    // authority while its sole presenter still exists. Owner CLOSE alone can
    // remain pending on that material; destroy cannot precede its native revoke.
    const bool collected = operation == FOUNDATION_ENGINE_COMMAND_RESULT ||
        operation == FOUNDATION_ENGINE_DOCUMENT_WORK_RESULT ||
        operation == FOUNDATION_ENGINE_EDITOR_WORK_RESULT ||
        operation == FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT ||
        operation == FOUNDATION_ENGINE_RETIRED_DOCUMENT_RESULT;
    if (written >= static_cast<std::int32_t>(receipt_bytes) &&
        little({output, static_cast<std::size_t>(written)}, 72, 4) == FOUNDATION_ENGINE_OK &&
        (operation == FOUNDATION_ENGINE_CLOSE || (runtime_close_requested && collected &&
            little({output, static_cast<std::size_t>(written)}, 76, 4) == 0))) {
        runtime_close_requested = true;
        // Native TURN_LEAVE may still be inside an engine callback. Application
        // work is drained only at the following ordinary owner/result boundary.
        if (!runtime && operation == FOUNDATION_ENGINE_CLOSE) {
            prepared_owner->close();
            return prepared_owner->dispatch(operation, {input, length}, {output, capacity});
        }
        if (runtime && prepared_owner->callback_depth() == 0) {
            try {
                runtime->application().shutdown();
                if (!runtime->application().shutdown_complete()) runtime->application().tick();
                if (operation == FOUNDATION_ENGINE_CLOSE && !runtime->application().shutdown_complete())
                    put({output, static_cast<std::size_t>(written)}, 76,
                        static_cast<std::uint32_t>(ServiceStatus::unavailable), 4);
            } catch (...) {
                prepared_owner->notify_document_terminal();
                return FOUNDATION_ENGINE_EXCEPTION;
            }
        }
    }
    return written;
}
void gui_web_destroy() {
    if (prepared_owner && prepared_owner->callback_depth() != 0) { prepared_owner->close(); return; }
    runtime.reset();
    if (prepared_owner) prepared_owner->close();
    // A binary-primary guest may already have executed initialization effects,
    // including a failed attempt. The same rich worker cannot reinterpret
    // destroy as permission to initialize that accepted attempt again.
    if(prepared_owner && prepared_owner->startup_primary()==foundation::appended::EngineStartupPrimary::binary) {
        response.clear(); return; // Inert process-held startup slot.
    }
    prepared_owner.reset(); response.clear();
}
const char* gui_web_create(const char* epoch) {
    if (runtime) throw std::runtime_error("Rich application session is already initialized");
    if (!prepared_owner || !prepared_owner->configured() || prepared_owner->closed())
        throw std::runtime_error("No rich application was prepared");
    if (prepared_owner->callback_depth() != 0) throw std::runtime_error("Rich engine callback is still active");
#if FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 3
    const auto identity = prepared_owner->identity();
    if (!editor_profile_valid() || !prepared_owner->editor_enabled() ||
        !foundation::appended::engine_editor::editor_profile_agrees(editor_profile(), prepared_owner->editor_profile()) ||
        prepared_owner->document_profile().enabled || !identity.worker_epoch || !identity.application_instance ||
        !identity.document_sequence || !identity.service_generation)
        throw std::runtime_error("No ready editor engine identity was prepared");
#elif FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE
    const auto identity = prepared_owner->identity();
    if (!document_profile_valid() || !prepared_owner->document_enabled() || !identity.worker_epoch ||
        !identity.application_instance || !identity.document_sequence || !identity.service_generation)
        throw std::runtime_error("No ready document engine identity was prepared");
#endif
    const auto name = epoch && *epoch ? std::string(epoch) : "appended-engine-" + std::to_string(next_runtime++);
#if defined(FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED) && FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED
    runtime = std::make_unique<Runtime>(name, foundation::host::BrowserSurfaceComposition(
        input_profile().surface_capabilities, foundation::host::surface_web::Profile::mouse_v1, {},{},false,
        prepared_owner->startup_primary()!=foundation::appended::EngineStartupPrimary::web));
#elif FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 2
    runtime = std::make_unique<Runtime>(name, foundation::host::BrowserSurfaceComposition(
        foundation::appended::engine_input::kSurfaceCapabilities, foundation::host::surface_web::Profile::mouse_v1, {},{},false,
        prepared_owner->startup_primary()!=foundation::appended::EngineStartupPrimary::web));
#elif FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE == 3
    foundation::host::BrowserEditorEndpoint endpoint;
    endpoint.profile = "editor_v1";
    endpoint.protocol = editor_profile().surface_protocol_version;
    endpoint.capabilities = editor_profile().surface_capabilities;
    // The global owning pointer outlives Runtime, including construction unwind.
    // This local kernel callback publishes only atomic terminal metadata.
    endpoint.terminal = {prepared_owner.get(), [](void* context) noexcept {
        static_cast<EngineOwner*>(context)->notify_document_terminal();
    }};
    runtime = std::make_unique<Runtime>(name, foundation::host::BrowserSurfaceComposition(
        editor_profile().surface_capabilities, foundation::host::surface_web::Profile::editor_v1,
        std::move(endpoint), foundation::host::BrowserDocumentEndpoint{}, true,
        prepared_owner->startup_primary()!=foundation::appended::EngineStartupPrimary::web));
#else
    runtime = std::make_unique<Runtime>(name);
#endif
    runtime_close_requested = false;
    response = runtime->initial(); return response.c_str();
}
const char* gui_web_receive(const char* message) {
    if (!runtime) throw std::runtime_error("Rich application session is not initialized");
    if (prepared_owner->callback_depth() != 0) throw std::runtime_error("Rich engine callback is still active");
    response = runtime->receive(message ? message : ""); return response.c_str();
}
}
