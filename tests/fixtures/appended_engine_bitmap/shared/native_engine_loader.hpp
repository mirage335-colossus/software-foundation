// TEST ONLY: all physical load/provider boundaries are counters, never a DSO.
#pragma once
#include "state.hpp"
#include "shared/appended_engine_module.hpp"
#include <foundation/appended/registry.hpp> // Actual canonical UTF-8 declaration; abi.cpp supplies it.
#include <filesystem>
#include <gui/contract.hpp>
namespace foundation::appended {
struct Package { bool binary{}; struct Application { std::string name{"Bitmap entry fixture"}; } application; };
class ContainerError : public std::runtime_error { public: using std::runtime_error::runtime_error; };
// This old entry fixture models startup-v1/web only. Added metadata methods
// keep the real entry compileable without claiming compiled/binary view support.
enum class EngineStartupPrimary { web,compiled,binary };
inline EngineStartupPrimary read_engine_startup_primary(const Package&) { return EngineStartupPrimary::web; }
class EngineModuleView {
    gui::Snapshot unavailable_;
public:
    const gui::Snapshot& snapshot() const noexcept { return unavailable_; }
};
struct EngineIdentity { std::uint64_t worker_epoch{1},application_instance{},document_sequence{},service_generation{}; };
struct EngineOwnerConfiguration {
    EngineStartupPrimary startup_primary=EngineStartupPrimary::web;
    engine_document::EngineDocumentProfileFacts document_profile;
    engine_editor::EngineEditorProfileFacts editor_profile;
    engine_document_actions::EngineDocumentActionsProfileFacts document_actions_profile;
    engine_input::EngineSurfaceProfileFacts input_profile;
    bool abandon_closed_document_outcomes{};
    EngineModuleFactory module_factory;
    std::vector<NativeServiceRegistration> native_services;
};
class EngineOwner {
    EngineOwnerConfiguration config_;
    bool configured_{};
    bool binary_{};
    Package package_;
    std::unique_ptr<EngineModuleBinding> module_;
public:
    EngineOwner(Package p,EngineOwnerConfiguration c) : config_(std::move(c)),binary_(p.binary),package_(std::move(p)) {
        auto& s=bitmap_entry_fixture::state; ++s.owners; bitmap_entry_fixture::event("owner");
        bitmap_entry_fixture::require(s.self==1&&s.plans==1&&!s.verify&&!s.load,"Owner construction bypassed native admission ordering");
        s.constructed_owner=this;
        bitmap_entry_fixture::require(!config_.input_profile.enabled&&config_.abandon_closed_document_outcomes,"wrong Owner policy");
        bitmap_entry_fixture::require(config_.native_services.size()==1,"entry omitted or duplicated its application services");
        const auto& echo=config_.native_services.front();
        bitmap_entry_fixture::require(echo.descriptor.name=="demo.echo"&&echo.descriptor.major==1&&echo.descriptor.minor==0&&
            echo.descriptor.max_reply_bytes==1024&&bool(echo.handler),"entry changed the application echo contract");
        for(std::size_t i=0;i<echo.descriptor.schema.size();++i)
            bitmap_entry_fixture::require(echo.descriptor.schema[i]==static_cast<std::uint8_t>(i+1),"entry changed the application echo schema");
#if defined(FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE) && FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE
        bitmap_entry_fixture::require(config_.input_profile==engine_input::EngineSurfaceProfileFacts{}&&
            config_.document_profile==engine_document::EngineDocumentProfileFacts{}&&
            config_.editor_profile==engine_editor::EngineEditorProfileFacts{},"actions Owner inherited legacy facts");
        bitmap_entry_fixture::require(engine_document_actions::document_actions_profile_agrees(config_.document_actions_profile,s.actions_profile),"Owner lost compiled actions facts");
        const auto& selected=config_.document_actions_profile;
        bitmap_entry_fixture::require(static_cast<std::uint32_t>(selected.kind)==4&&selected.provider_capabilities==4083&&
            selected.surface_capabilities==8255&&selected.surface_protocol_version==2&&selected.editor_protocol_version==1,
            "actions fixture lost its independent literal profile pins");
#else
        bitmap_entry_fixture::require(config_.input_profile==engine_input::EngineSurfaceProfileFacts{}&&
            config_.editor_profile==engine_editor::EngineEditorProfileFacts{}&&
            config_.document_actions_profile==engine_document_actions::EngineDocumentActionsProfileFacts{},
            "pixel Owner inherited another selected or dirty inactive profile");
        bitmap_entry_fixture::require(engine_document::document_profile_agrees(config_.document_profile,s.profile),"Owner lost compiled document facts");
#endif
#if defined(FOUNDATION_APPENDED_BINARY_CAPABILITY) && FOUNDATION_APPENDED_BINARY_CAPABILITY
        bitmap_entry_fixture::require(bool(config_.module_factory),"explicitboth omitted its module factory");
#else
        bitmap_entry_fixture::require(!config_.module_factory,"web-only acquired a module factory");
#endif
        if(bitmap_entry_fixture::is("invalid-startup"))throw ContainerError("synthetic invalid startup");
        if(binary_&&!config_.module_factory)throw ContainerError("binary payload needs explicit both capability");
    }
    ~EngineOwner() { ++bitmap_entry_fixture::state.owner_destroys; }
    void configure() {
        auto& s=bitmap_entry_fixture::state;
        ++s.configures;
        bitmap_entry_fixture::require(s.configures==1,"Owner configured repeatedly");
        if(binary_&&config_.module_factory)module_=config_.module_factory({}, {}, 1);
        configured_=bitmap_entry_fixture::state.configured;
    }
    EngineStartupPrimary startup_primary() const noexcept { return config_.startup_primary; }
    std::shared_ptr<const EngineModuleView> binary_view() const noexcept { return {}; }
    void tick_binary_view() { throw std::logic_error("Binary view bootstrap is outside this old web-primary entry fixture"); }
    bool configured() const { return configured_; }
    bool closed() const { return false; }
    const Package& package() const noexcept { return package_; }
    void notify_document_terminal() noexcept { ++bitmap_entry_fixture::state.terminal_notifications; }
    EngineIdentity identity() const {
        const auto& s=bitmap_entry_fixture::state;
        const bool waiting=bitmap_entry_fixture::is("start-waiting");
        return {1,s.adopt_identity?23u:0u,waiting?0u:7u,waiting?0u:9u};
    }
};
struct NativeEngineExpectation {
    std::uint32_t target_system{},target_processor{},pointer_bits{};
    engine_document::Digest contract_header_sha256{},build_identity_sha256{},source_recipe_sha256{};
    engine_document::EngineDocumentProfileFacts document_profile;
    engine_editor::EngineEditorProfileFacts editor_profile;
    engine_document_actions::EngineDocumentActionsProfileFacts document_actions_profile;
    bool operator==(const NativeEngineExpectation&) const = default;
};
struct NativeEngineLoadPlan {
    NativeEngineExpectation expectation;
    std::filesystem::path root;
    bool operator==(const NativeEngineLoadPlan&) const = default;
};
inline std::optional<NativeEngineLoadPlan> fixture_verified_plan;
class NativeEngineLoadError : public std::runtime_error { public: using std::runtime_error::runtime_error; };
struct NativeEngineProvider { std::uint64_t token{}; };
enum class NativeEngineState { bound,waiting_document,ready,closing,detached,blocked,process_exit_required };
struct NativeEngineOptions { BibEngineLimitsV1 limits{sizeof(BibEngineLimitsV1),65536,65536,65536,0,0,0,0,0,0}; };
struct NativeEngineWake { void* context{}; void (*post_owner_wake)(void*) noexcept{}; };
class NativeEngineDriver {
    std::shared_ptr<EngineOwner> owner_;
    NativeEngineState state_{NativeEngineState::bound};
public:
    NativeEngineWake wake;
    static NativeEngineDriver& bind_once(NativeEngineProvider provider,std::shared_ptr<EngineOwner> owner,NativeEngineOptions options,NativeEngineWake callback) {
        auto& s=bitmap_entry_fixture::state; ++s.bind; bitmap_entry_fixture::event("bind");
        bitmap_entry_fixture::require(s.bind==1&&s.load==1&&provider.token==s.loaded_provider_token&&provider.token!=0,"bind repeated or substituted the loaded provider");
        bitmap_entry_fixture::require(owner.get()==s.constructed_owner,"bind substituted the configured Owner");
        bitmap_entry_fixture::require(options.limits.maximum_reply_bytes==BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY,"document reply capacity not fully reserved");
#if defined(FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE) && FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE
        bitmap_entry_fixture::require(options.limits.maximum_command_bytes==1048576&&options.limits.maximum_query_bytes==236&&
            options.limits.maximum_reply_bytes==1048576,"actions startup did not select exact command/query/reply capacities");
#else
        bitmap_entry_fixture::require(options.limits.maximum_command_bytes==65536&&options.limits.maximum_query_bytes==65536,"legacy command/query defaults changed");
#endif
        if(bitmap_entry_fixture::is("bind-failure"))throw NativeEngineLoadError("synthetic bind failure");
        auto* driver=new NativeEngineDriver; // Explicit process-life test shell, no real resource.
        driver->owner_=std::move(owner);driver->wake=callback;s.bound_owner=driver->owner_.get();s.bound_driver=driver;
        return *driver;
    }
    void start_once() {
        auto& s=bitmap_entry_fixture::state;++s.start;bitmap_entry_fixture::event("start");
        bitmap_entry_fixture::require(this==s.bound_driver&&s.start==1,"start replaced or restarted the bound Driver");
        owner_->configure();
        state_=bitmap_entry_fixture::is("start-waiting")?NativeEngineState::waiting_document:NativeEngineState::ready;
        if(bitmap_entry_fixture::is("start-terminal"))state_=NativeEngineState::process_exit_required;
        if(bitmap_entry_fixture::is("start-blocked"))state_=NativeEngineState::blocked;
        if(bitmap_entry_fixture::is("start-bound"))state_=NativeEngineState::bound;
    }
    void request_close() noexcept {auto& s=bitmap_entry_fixture::state;++s.close_requests;if(state_==NativeEngineState::process_exit_required||state_==NativeEngineState::blocked)s.forbidden_cleanup=true;state_=NativeEngineState::closing;}
    void tick() {
        ++bitmap_entry_fixture::state.driver_ticks;
        if(state_==NativeEngineState::process_exit_required||state_==NativeEngineState::blocked)bitmap_entry_fixture::state.forbidden_cleanup=true;
        if(bitmap_entry_fixture::is("close-terminal"))state_=NativeEngineState::process_exit_required;
        else if(bitmap_entry_fixture::is("close-blocked"))state_=NativeEngineState::blocked;
        else if(state_==NativeEngineState::closing&&!bitmap_entry_fixture::is("unfinished-close"))state_=NativeEngineState::detached;
    }
    void request_advance() noexcept { ++bitmap_entry_fixture::state.advance_requests; }
    std::shared_ptr<EngineOwner> owner() const noexcept { return owner_; }
    std::optional<std::chrono::steady_clock::time_point> deadline() const noexcept { return {}; }
    NativeEngineState state() const noexcept {return state_;}
    void state(NativeEngineState value) noexcept {state_=value;}
};
inline void verify_native_engine_load_plan(const NativeEngineLoadPlan& plan) {
    auto& s=bitmap_entry_fixture::state;
    bitmap_entry_fixture::require(s.self==1&&s.plans==1&&s.owners==1&&s.owner_destroys==0&&s.load==0,
        "native verification bypassed the live Owner startup gate");
    ++s.verify;bitmap_entry_fixture::event("verify");
    if(bitmap_entry_fixture::is("verify-failure"))throw NativeEngineLoadError("synthetic verify failure");
    fixture_verified_plan=plan;
}
inline NativeEngineProvider load_native_engine(const NativeEngineLoadPlan& plan) {
    auto& s=bitmap_entry_fixture::state;
    bitmap_entry_fixture::require(s.verify==1&&fixture_verified_plan&&*fixture_verified_plan==plan,
        "native load substituted or skipped the complete verified plan");
    ++s.load;bitmap_entry_fixture::event("load");
    if(bitmap_entry_fixture::is("load-failure"))throw NativeEngineLoadError("synthetic load failure");
    s.loaded_provider_token=0x4e4154495645424dULL;
    return NativeEngineProvider{s.loaded_provider_token};
}
} // namespace foundation::appended
