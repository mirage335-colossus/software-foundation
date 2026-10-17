// SPDX-License-Identifier: CC0-1.0
#pragma once

#include "appended_engine_application.hpp"
#include "engine_primary_application_policy.hpp"
#include <thread>

namespace foundation::ui {

// The bitmap root supplies the sole actual presenter and App close ledger.
// Startup, compiled feature, Module-view and service metadata policy is shared
// with the semantic root; neither root creates another Controller or Owner.
class EnginePrimaryRegionApplication : public AppendedEngineApplication {
public:
    template<class... Arguments>
    EnginePrimaryRegionApplication(gui::Adapter& adapter,
            std::shared_ptr<appended::EngineOwner> owner,Arguments&&... arguments)
        : AppendedEngineApplication(adapter,owner,std::forward<Arguments>(arguments)...,
              EnginePrimaryApplicationPolicy::initial_region(owner)),
          owner_(std::move(owner)), policy_(owner_,{
              [this] { return AppendedEngineApplication::take_compiled_event(); },
              [this](EngineRegionComposition value) { return AppendedEngineApplication::queue_compiled_region(std::move(value)); },
              [this] { return AppendedEngineApplication::compiled_region_published_revision(); },
              [this] { return AppendedEngineApplication::owned_service_ready(); },
              [this](bool active) { AppendedEngineApplication::set_owned_service_active(active); }}) {}

    // Logical source canvas, never an OS drawable-size or display-scale claim.
    static gui::Size initial_client_size(const std::shared_ptr<appended::EngineOwner>& owner) {
        const auto region=EnginePrimaryApplicationPolicy::initial_region(owner);
        return region ? region->compiled().client_size : gui::Size{800,600};
    }
    void handle(gui::Event value) {
        check_owner();
        if(std::holds_alternative<gui::CloseEvent>(value)) { shutdown(); return; }
        if(policy_.closing() || owner_->closed()) return;
        AppendedEngineApplication::handle(std::move(value));
    }
    void tick() {
        check_owner();
        if(owner_->closed()) shutdown();
        policy_.tick();
        // After detach the shared policy admits no guest work; the existing
        // App still drains its exact known checked head/publication metadata.
        AppendedEngineApplication::tick();
    }
    void set_owned_service_active(bool active) {
        check_owner(); policy_.set_external_service_active(active);
    }
    bool owned_service_pending() const noexcept {
        return thread_==std::this_thread::get_id() && policy_.service_pending();
    }
    std::optional<gui::ServiceRequest> next_service() {
        check_owner(); return policy_.next_service();
    }
    bool complete_service(gui::ServiceResult result) {
        check_owner(); return policy_.complete_service(std::move(result));
    }
    void shutdown() noexcept {
        if(thread_!=std::this_thread::get_id()) return;
        policy_.shutdown(); AppendedEngineApplication::shutdown();
    }
    bool shutdown_complete() const noexcept {
        return thread_==std::this_thread::get_id() && policy_.debt_complete() &&
            AppendedEngineApplication::shutdown_complete();
    }

private:
    void check_owner() const {
        if(thread_!=std::this_thread::get_id())
            throw std::logic_error("Primary region requires its serialized application owner");
    }
    const std::thread::id thread_=std::this_thread::get_id();
    const std::shared_ptr<appended::EngineOwner> owner_;
    EnginePrimaryApplicationPolicy policy_;
};

} // namespace foundation::ui
