// SPDX-License-Identifier: CC0-1.0
#pragma once
#include "appended_engine_application.hpp"
#include "compiled_region_feature.hpp"
#include <limits>
#include <stdexcept>
#include <utility>

namespace foundation::ui {
// Focused explicit compiled composition; the maintained private rich entry uses
// EnginePrimaryRegionApplication to select the actual Package startup intent.
class CompiledPrimaryRegionApplication : public AppendedEngineApplication {
public:
    template<class... Arguments>
    CompiledPrimaryRegionApplication(gui::Adapter& adapter,
            std::shared_ptr<appended::EngineOwner> owner, Arguments&&... arguments)
        : AppendedEngineApplication(adapter,require_primary(std::move(owner)),
            std::forward<Arguments>(arguments)...,make_region(1,0)) {}
    void tick() {
        while(auto intent=take_compiled_event()) feature_.accept(*intent);
        feature_.stage(*this); AppendedEngineApplication::tick();
    }
    std::uint64_t count() const noexcept { return feature_.count(); }
    static EngineRegionComposition make_region(std::uint64_t revision,std::uint64_t count) {
        return CompiledRegionFeature::make_region(revision,count);
    }
private:
    static std::shared_ptr<appended::EngineOwner> require_primary(std::shared_ptr<appended::EngineOwner> owner) {
        if(!owner || owner->startup_primary()!=appended::EngineStartupPrimary::compiled)
            throw std::invalid_argument("Compiled region root requires its explicit compiled startup Owner");
        return owner;
    }
    CompiledRegionFeature feature_;
};
} // namespace foundation::ui
