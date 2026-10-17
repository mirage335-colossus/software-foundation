// SPDX-License-Identifier: CC0-1.0
#pragma once

#include "engine_region_composition.hpp"
#include <limits>
#include <stdexcept>
#include <utility>

namespace foundation::ui {
// Shared compiled feature policy; no presenter, engine, controller or loop.
class CompiledRegionFeature {
public:
    bool accept(const CompiledRegionEvent& intent) {
        if(intent.revision!=revision_) return false;
        const auto* widget=std::get_if<gui::WidgetEvent>(&intent.event);
        if(!widget || widget->target!=gui::WidgetKey{"compiled.increment",1} ||
            !std::holds_alternative<gui::Activate>(widget->input)) return false;
        if(count_==std::numeric_limits<std::uint64_t>::max()) throw std::overflow_error("Compiled counter exhausted");
        ++count_; dirty_=true; return true;
    }
    template<class App> void stage(App& app) {
        if(!dirty_) return;
        if(revision_==std::numeric_limits<std::uint64_t>::max()) throw std::overflow_error("Compiled view revisions exhausted");
        if(app.queue_compiled_region(make_region(revision_+1,count_))) { ++revision_; dirty_=false; }
    }
    std::uint64_t count() const noexcept { return count_; }
    static EngineRegionComposition make_region(std::uint64_t revision,std::uint64_t count) {
        gui::Snapshot shell;
        shell.revision = revision; shell.title = "Compiled application with a rich region";
        shell.client_size = {1040,640}; shell.display_scale = 1;
        gui::Widget button;
        button.spec.key = {"compiled.increment",1}; button.spec.kind = gui::Kind::button;
        button.state.bounds = {20,20,180,36}; button.state.text = "Increment";
        shell.widgets.push_back(std::move(button));
        gui::Widget label;
        label.spec.key = {"compiled.count",1}; label.spec.kind = gui::Kind::label;
        label.state.bounds = {20,72,180,36}; label.state.text = "Count: " + std::to_string(count);
        shell.widgets.push_back(std::move(label));
        return {std::move(shell),{220,20,800,600}};
    }
private:
    std::uint64_t revision_=1,count_=0;
    bool dirty_=false;
};

} // namespace foundation::ui
