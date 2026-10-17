// SPDX-License-Identifier: CC0-1.0
// TEST ONLY: value/counter seams for the real native bitmap entry. No engine proof.
#pragma once
#include "shared/engine_document_profile.hpp"
#include "shared/engine_document_actions_profile.hpp"
#include <gui/contract.hpp>
#include <gui/runtime.hpp>
#include <chrono>
#include <functional>
#include <filesystem>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

namespace bitmap_entry_fixture {
inline std::string invariant_failure;
inline void require(bool value, const char* message) {
    if(!value){if(invariant_failure.empty())invariant_failure=message;throw std::runtime_error(message);}
}
inline std::filesystem::path runtime_root() {
#if defined(_WIN32)
    return "C:/fixture/runtime";
#else
    return "/fixture/runtime";
#endif
}
inline std::filesystem::path installed_root() { return runtime_root().parent_path()/"installed/runtime"; }
inline std::filesystem::path output_path() { return runtime_root().parent_path()/"output.ppm"; }
inline std::string utf8_bytes(const std::filesystem::path& path) {
    const auto bytes=path.generic_u8string();return {bytes.begin(),bytes.end()};
}
inline std::filesystem::path unicode_runtime_root() {
    return runtime_root().parent_path()/std::filesystem::path(u8"\u00E9-\u76EE\u5F55-\U0001F6F0");
}
inline std::filesystem::path unicode_output_path() {
    return runtime_root().parent_path()/std::filesystem::path(u8"\u00E9-\u8F93\u51FA-\U0001F680.ppm");
}
inline foundation::appended::engine_document::EngineDocumentProfileFacts facts() {
    namespace d = foundation::appended::engine_document;
    d::EngineDocumentProfileFacts f;
    f.enabled=true; f.kind=d::ProfileKind::pixel; f.name=d::kPixelProfileName;
    f.provider_abi_major=1; f.provider_abi_minor=1; f.host_abi_major=1;
    f.target_system=BIB_ENGINE_TARGET_LINUX; f.target_processor=BIB_ENGINE_CPU_X86_64; f.pointer_bits=64;
#if defined(_WIN32)
    f.target_system=BIB_ENGINE_TARGET_WINDOWS;
#elif defined(__aarch64__)
    f.target_processor=BIB_ENGINE_CPU_AARCH64;
#endif
    f.lifetime=BIB_ENGINE_LIFETIME_PROCESS; f.maximum_starts=1; f.viewport_width=800; f.viewport_height=600;
    f.provider_capabilities=d::kPixelCapabilities; f.base_header_sha256=d::kBaseHeaderSha256;
    f.extension_header_sha256=d::kExtensionHeaderSha256; f.contract_sha256=d::kContractSha256;
    f.catalog_sha256=d::kCatalogSha256; f.build_sha256[0]=1; f.source_recipe_sha256[0]=2;
    f.queries=d::kQueries; f.commands=d::kCommands; f.query_count=1; f.command_count=2;
    return f;
}
inline foundation::appended::engine_document_actions::EngineDocumentActionsProfileFacts actions_facts() {
    namespace a = foundation::appended::engine_document_actions;
    namespace d = foundation::appended::engine_document;
    namespace e = foundation::appended::engine_editor;
    a::EngineDocumentActionsProfileFacts f;
    f.enabled=true; f.kind=a::ProfileKind::document_actions; f.name=a::kProfileName;
    f.provider_abi_major=1; f.provider_abi_minor=1; f.host_abi_major=1;
    f.target_system=BIB_ENGINE_TARGET_LINUX; f.target_processor=BIB_ENGINE_CPU_X86_64; f.pointer_bits=64;
#if defined(_WIN32)
    f.target_system=BIB_ENGINE_TARGET_WINDOWS;
#elif defined(__aarch64__)
    f.target_processor=BIB_ENGINE_CPU_AARCH64;
#endif
    f.lifetime=BIB_ENGINE_LIFETIME_PROCESS; f.maximum_starts=1; f.viewport_width=800; f.viewport_height=600;
    f.provider_capabilities=a::kProviderCapabilities; f.surface_capabilities=a::kSurfaceCapabilities;
    f.surface_protocol_version=2; f.editor_protocol_version=BIB_ENGINE_EDITOR_PROTOCOL_VERSION;
    f.base_header_sha256=d::kBaseHeaderSha256; f.document_header_sha256=d::kExtensionHeaderSha256;
    f.document_contract_sha256=d::kContractSha256; f.document_catalog_sha256=d::kCatalogSha256;
    f.physical_catalog_sha256=d::kPhysicalCatalogSha256;
    f.editor_header_sha256=e::kHeaderSha256; f.editor_contract_sha256=e::kContractSha256;
    f.editor_catalog_sha256=e::kCatalogSha256; f.editor_schema_sha256=e::kSchema;
    f.actions_header_sha256=a::kHeaderSha256; f.contract_sha256=a::kContractSha256;
    f.catalog_sha256=a::kCatalogSha256; f.schema_sha256=a::kSchema; f.ack_schema_sha256=a::kAckSchema;
    f.build_sha256[0]=1; f.source_recipe_sha256[0]=2;
    f.queries=a::kQueries; f.commands=a::kCommands; f.query_count=2; f.command_count=9;
    return f;
}
// Every scalar/digest and every field of both queries/nine commands gets its
// own fresh-process disagreement; the production validator remains unchanged.
inline void alter_actions(foundation::appended::engine_document_actions::EngineDocumentActionsProfileFacts& f,int index) {
    switch(index){
    case 0:f.enabled=false;break;case 1:f.kind=foundation::appended::engine_document_actions::ProfileKind::disabled;break;
    case 2:f.name+="x";break;case 3:++f.provider_abi_major;break;case 4:++f.provider_abi_minor;break;
    case 5:++f.host_abi_major;break;case 6:++f.host_abi_minor;break;case 7:f.target_system=UINT32_MAX;break;
    case 8:f.target_processor=UINT32_MAX;break;case 9:++f.pointer_bits;break;case 10:++f.lifetime;break;
    case 11:++f.maximum_starts;break;case 12:++f.viewport_width;break;case 13:++f.viewport_height;break;
    case 14:++f.provider_capabilities;break;case 15:++f.surface_capabilities;break;
    case 16:++f.surface_protocol_version;break;case 17:++f.editor_protocol_version;break;
    case 18:f.base_header_sha256[0]^=1;break;case 19:f.document_header_sha256[0]^=1;break;
    case 20:f.document_contract_sha256[0]^=1;break;case 21:f.document_catalog_sha256[0]^=1;break;
    case 22:f.physical_catalog_sha256[0]^=1;break;case 23:f.editor_header_sha256[0]^=1;break;
    case 24:f.editor_contract_sha256[0]^=1;break;case 25:f.editor_catalog_sha256[0]^=1;break;
    case 26:f.editor_schema_sha256[0]^=1;break;case 27:f.actions_header_sha256[0]^=1;break;
    case 28:f.contract_sha256[0]^=1;break;case 29:f.catalog_sha256[0]^=1;break;
    case 30:f.schema_sha256[0]^=1;break;case 31:f.ack_schema_sha256[0]^=1;break;
    case 32:f.build_sha256[0]^=1;break;case 33:f.source_recipe_sha256.fill(0);break;
    case 34:++f.query_count;break;case 35:++f.command_count;break;
    default:
        require(index>=36&&index<=90,"invalid actions field selector");
        auto& operation=index<46?f.queries[static_cast<std::size_t>((index-36)/5)]:f.commands[static_cast<std::size_t>((index-46)/5)];
        switch((index<46?index-36:index-46)%5){
        case 0:++operation.operation;break;case 1:++operation.maximum_input_bytes;break;
        case 2:++operation.required_reply_capacity;break;case 3:++operation.capability;break;
        case 4:operation.schema_sha256[0]^=1;break;
        }
    }
}
struct State {
    std::string scenario, argv0, plan_root;
    foundation::appended::engine_document::EngineDocumentProfileFacts profile=facts();
    foundation::appended::engine_document_actions::EngineDocumentActionsProfileFacts actions_profile=actions_facts();
    int mismatch=-1;
    int actions_mismatch=-1;
    bool actions_rejected{};
    std::vector<std::string> events;
    unsigned self{},plans{},owners{},verify{},load{},bind{},start{},driver_ticks{},close_requests{},factories{};
    unsigned resolves{},advance_requests{},owner_destroys{},configures{},terminal_notifications{};
    unsigned metadata_settles{};
    unsigned renders{},pixels{},frame_requests{},connections{},surface_events{},surface_revocations{},application_attempts{};
    unsigned editor_submits{},editor_revokes{},editor_takes{},editor_resyncs{},facade_destroys{};
    bool expected_read_only{};
    std::string facade_kind;
    std::uint64_t loaded_provider_token{};
    void* constructed_owner{};
    bool forbidden_cleanup{};
    unsigned facades{},cells{},foreground{},facade_ticks{},shutdown{},retry{},qualify{},runner{},handled{},service_reads{},service_completions{};
    bool configured=true,adopt_identity=true,binary{},close_queued{},detached{},wake_cleared{};
    void* bound_owner{}; void* bound_driver{};
    std::function<void()> facade_wake,on_facade_tick,expire_close,terminal_notify;
};
inline State state;
inline void event(const char* name) { state.events.emplace_back(name); }
inline bool is(const char* name) { return state.scenario==name; }
class Adapter final : public gui::Adapter {
    bool closed_{};
    gui::Snapshot snapshot_;
public:
    explicit Adapter(gui::EventSink = {}) {}
    void present(gui::Snapshot value) override { snapshot_=std::move(value); }
    const gui::Snapshot& snapshot() const noexcept { return snapshot_; }
    gui::Size measure_text(const gui::TextMeasureRequest&) const override { return {}; }
    gui::Availability resolved_availability(const gui::WidgetKey&) const override { return {}; }
    std::optional<gui::WidgetKey> focused() const override { return {}; }
    bool focus(std::optional<gui::WidgetKey>) override { return false; }
    bool focus_next(bool) override { return false; }
    void scroll(const gui::WidgetKey&,gui::Point) override {}
    gui::Point scroll_offset(const gui::WidgetKey&) const override { return {}; }
    gui::TextSelection text_selection(const gui::WidgetKey&) const override { return {}; }
    void text_selection(const gui::WidgetKey&,gui::TextSelection) override {}
    bool open_popup(const gui::WidgetKey&) override { return false; }
    void close_popup(const gui::WidgetKey&) override {}
    void invalidate(const gui::WidgetKey&,gui::PixelRect) override {}
    bool closed() const override { return closed_; }
    void close() override { closed_=true; }
    bool service_active() const { return false; }
    void service(gui::ServiceRequest,std::function<void(gui::ServiceResult)>) { throw std::logic_error("fixture received unexpected native service"); }
};
} // namespace bitmap_entry_fixture
