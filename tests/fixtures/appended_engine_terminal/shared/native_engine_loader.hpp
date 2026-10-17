// TEST ONLY: all physical load/provider boundaries are counters, never a DSO.
#pragma once
#include "state.hpp"
#include "shared/appended_engine_module.hpp"
#include <filesystem>
namespace foundation::appended {
struct Package { bool binary{}; };
// These legacy entry cases model web-primary startup, including a secondary
// binary provider. Real metadata validation is not exercised by this fixture.
enum class EngineStartupPrimary { web, compiled, binary };
inline EngineStartupPrimary read_engine_startup_primary(const Package&) { return EngineStartupPrimary::web; }
class ContainerError : public std::runtime_error { public: using std::runtime_error::runtime_error; };
struct EngineIdentity { std::uint64_t worker_epoch{1},application_instance{},document_sequence{},service_generation{}; };
struct EngineOwnerConfiguration {
    EngineStartupPrimary startup_primary = EngineStartupPrimary::web;
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
    std::unique_ptr<EngineModuleBinding> module_;
public:
    EngineOwner(Package p,EngineOwnerConfiguration c) : config_(std::move(c)) {
        auto& s=terminal_main_fixture::state; ++s.owners; terminal_main_fixture::event("owner");
        terminal_main_fixture::require(config_.startup_primary==EngineStartupPrimary::web,"terminal entry fixture only models web-primary startup");
        terminal_main_fixture::require(!config_.input_profile.enabled&&config_.abandon_closed_document_outcomes,"wrong Owner policy");
        terminal_main_fixture::require(config_.native_services.size()==1,"entry omitted or duplicated its application services");
        const auto& echo=config_.native_services.front();
        terminal_main_fixture::require(echo.descriptor.name=="demo.echo"&&echo.descriptor.major==1&&echo.descriptor.minor==0&&
            echo.descriptor.max_reply_bytes==1024&&bool(echo.handler),"entry changed the application echo contract");
        for(std::size_t i=0;i<echo.descriptor.schema.size();++i)
            terminal_main_fixture::require(echo.descriptor.schema[i]==static_cast<std::uint8_t>(i+1),"entry changed the application echo schema");
#if defined(FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE) && FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE
        terminal_main_fixture::require(config_.input_profile==engine_input::EngineSurfaceProfileFacts{}&&
            config_.document_profile==engine_document::EngineDocumentProfileFacts{}&&
            config_.editor_profile==engine_editor::EngineEditorProfileFacts{},"actions Owner inherited legacy facts");
        terminal_main_fixture::require(engine_document_actions::document_actions_profile_agrees(config_.document_actions_profile,s.actions_profile),"Owner lost compiled actions facts");
#else
        terminal_main_fixture::require(engine_document::document_profile_agrees(config_.document_profile,s.profile),"Owner lost compiled document facts");
#endif
        if(terminal_main_fixture::is("invalid-startup"))throw ContainerError("synthetic invalid startup");
        if(p.binary&&!config_.module_factory)throw ContainerError("binary payload needs explicit both capability");
    }
    void configure() {
        if(config_.module_factory)module_=config_.module_factory({}, {}, 1);
        configured_=terminal_main_fixture::state.configured;
    }
    bool configured() const { return configured_; }
    EngineStartupPrimary startup_primary() const noexcept { return config_.startup_primary; }
    std::shared_ptr<const EngineModuleView> binary_view() const noexcept { return {}; }
    void tick_binary_view() { throw std::logic_error("binary-primary view is not modeled by terminal entry fixture"); }
    EngineIdentity identity() const { return {1,terminal_main_fixture::state.adopt_identity?23u:0u,7,9}; }
};
struct NativeEngineExpectation {
    std::uint32_t target_system{},target_processor{},pointer_bits{};
    engine_document::Digest contract_header_sha256{},build_identity_sha256{},source_recipe_sha256{};
    engine_document::EngineDocumentProfileFacts document_profile;
    engine_editor::EngineEditorProfileFacts editor_profile;
    engine_document_actions::EngineDocumentActionsProfileFacts document_actions_profile;
};
struct NativeEngineLoadPlan { NativeEngineExpectation expectation; std::filesystem::path root; };
class NativeEngineLoadError : public std::runtime_error { public: using std::runtime_error::runtime_error; };
struct NativeEngineProvider {};
enum class NativeEngineState { bound,waiting_document,ready,closing,detached,blocked,process_exit_required };
struct NativeEngineOptions { BibEngineLimitsV1 limits{sizeof(BibEngineLimitsV1),65536,65536,65536,0,0,0,0,0,0}; };
struct NativeEngineWake { void* context{}; void (*post_owner_wake)(void*) noexcept{}; };
class NativeEngineDriver {
    std::shared_ptr<EngineOwner> owner_;
    NativeEngineState state_{NativeEngineState::bound};
public:
    NativeEngineWake wake;
    static NativeEngineDriver& bind_once(NativeEngineProvider,std::shared_ptr<EngineOwner> owner,NativeEngineOptions options,NativeEngineWake callback) {
        auto& s=terminal_main_fixture::state; ++s.bind; terminal_main_fixture::event("bind");
        terminal_main_fixture::require(options.limits.maximum_reply_bytes==BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY,"document reply capacity not fully reserved");
#if defined(FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE) && FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE
        terminal_main_fixture::require(options.limits.maximum_command_bytes==1048576&&options.limits.maximum_query_bytes==236&&
            options.limits.maximum_reply_bytes==1048576,"actions startup did not select exact command/query/reply capacities");
#else
        terminal_main_fixture::require(options.limits.maximum_command_bytes==65536&&options.limits.maximum_query_bytes==65536,"legacy command/query defaults changed");
#endif
        if(terminal_main_fixture::is("bind-failure"))throw NativeEngineLoadError("synthetic bind failure");
        auto* driver=new NativeEngineDriver; // Explicit process-life test shell, no real resource.
        driver->owner_=std::move(owner);driver->wake=callback;s.bound_owner=driver->owner_.get();s.bound_driver=driver;
        return *driver;
    }
    void start_once() {
        auto& s=terminal_main_fixture::state;++s.start;terminal_main_fixture::event("start");owner_->configure();
        state_=terminal_main_fixture::is("start-waiting")?NativeEngineState::waiting_document:NativeEngineState::ready;
        if(terminal_main_fixture::is("start-terminal"))state_=NativeEngineState::process_exit_required;
        if(terminal_main_fixture::is("start-blocked"))state_=NativeEngineState::blocked;
        if(terminal_main_fixture::is("start-bound"))state_=NativeEngineState::bound;
    }
    void request_close() noexcept {++terminal_main_fixture::state.close_requests;state_=NativeEngineState::closing;}
    void tick() {
        ++terminal_main_fixture::state.driver_ticks;
        if(terminal_main_fixture::is("close-terminal"))state_=NativeEngineState::process_exit_required;
        else if(terminal_main_fixture::is("close-blocked"))state_=NativeEngineState::blocked;
        else if(!terminal_main_fixture::is("unfinished-close"))state_=NativeEngineState::detached;
    }
    NativeEngineState state() const noexcept {return state_;}
    void state(NativeEngineState value) noexcept {state_=value;}
};
inline void verify_native_engine_load_plan(const NativeEngineLoadPlan&) {
    ++terminal_main_fixture::state.verify;terminal_main_fixture::event("verify");
    if(terminal_main_fixture::is("verify-failure"))throw NativeEngineLoadError("synthetic verify failure");
}
inline NativeEngineProvider load_native_engine(const NativeEngineLoadPlan&) {
    ++terminal_main_fixture::state.load;terminal_main_fixture::event("load");
    if(terminal_main_fixture::is("load-failure"))throw NativeEngineLoadError("synthetic load failure");
    return {};
}
} // namespace foundation::appended
