// SPDX-License-Identifier: CC0-1.0
#pragma once

#include "appended_binary_view_model.hpp"
#include <foundation/gui/surface.hpp>
#include <gui/contract.hpp>
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <stdexcept>
#include <string_view>
#include <type_traits>
#include <utility>

namespace foundation::ui {

// Private first successor: one unscaled fixed-profile rich region in a compiled
// root Snapshot. Coordinates are logical client units, never OS pixels. The
// generic renderer remains responsible for its actual display transform.
class EngineRegionComposition {
public:
    static constexpr std::string_view engine_id = "engine.frame";
    static constexpr std::string_view compiled_clip_id = "foundation.region.compiled.clip";
    static constexpr double width = 800, height = 600;

    EngineRegionComposition(gui::Snapshot compiled, gui::Rect pane)
        : EngineRegionComposition(std::move(compiled),pane,false) {}
    static EngineRegionComposition from_binary_view(const appended::EngineModuleView& model) {
        auto compiled=model.snapshot();
        const auto original=compiled.client_size;
        if(original.width<=0 || original.height<=0 || !compiled.revision)
            throw std::invalid_argument("Binary primary has no initial checked view");
        // Expanding the root canvas must not reveal binary content previously
        // clipped by its own client rectangle. One generic parent clip keeps
        // the original module coordinates and IDs unchanged.
        for(const auto& widget:compiled.widgets)
            if(widget.spec.key.id==compiled_clip_id) throw std::invalid_argument("Binary view collides with the compiled clip owner");
        for(const auto& command:compiled.commands)
            if(command.key.id==compiled_clip_id) throw std::invalid_argument("Binary command collides with the compiled clip owner");
        gui::Widget clip;
        clip.spec.key={std::string(compiled_clip_id),1};clip.spec.kind=gui::Kind::group;
        clip.state.bounds={0,0,original.width,original.height};
        for(auto& widget:compiled.widgets) if(widget.spec.parent.empty()) widget.spec.parent=clip.spec.key.id;
        compiled.widgets.insert(compiled.widgets.begin(),std::move(clip));
        compiled.client_size={original.width+width,std::max(original.height,height)};
        return EngineRegionComposition(std::move(compiled),{original.width,0,width,height},true);
    }
private:
    // Only the typed internally decoded source can retain bitmap callables.
    EngineRegionComposition(gui::Snapshot compiled,gui::Rect pane,bool decoded_images)
        : compiled_(std::move(compiled)), pane_(pane) {
        bound_storage(decoded_images);
        gui::validate_snapshot(compiled_);
        if (!compiled_.revision || compiled_.display_scale != 1 ||
            !finite(pane_) || pane_.width != width || pane_.height != height ||
            pane_.x < 0 || pane_.y < 0 ||
            pane_.x + width > compiled_.client_size.width ||
            pane_.y + height > compiled_.client_size.height)
            throw std::invalid_argument("Compiled rich region requires one unscaled800x600 pane in its fixed canvas");
        // IDs remain generic GUI identities. Reject collisions instead of
        // silently renaming references, commands, focus or event targets.
        for (const auto& widget : compiled_.widgets) {
            if (widget.spec.key.id == engine_id || widget.spec.parent == engine_id ||
                (!decoded_images && widget.spec.key.id==compiled_clip_id) ||
                intersects(widget.state.bounds, pane_))
                throw std::invalid_argument("Compiled widgets must have distinct IDs and stay outside the rich pane");
        }
        if (!compiled_.pages.empty() && intersects(compiled_.page_bar,pane_))
            throw std::invalid_argument("Compiled page chrome overlaps the rich pane");
        for (const auto& command : compiled_.commands)
            if (command.key.id == engine_id)
                throw std::invalid_argument("Compiled command collides with the rich owner");
    }

public:
    const gui::Snapshot& compiled() const noexcept { return compiled_; }
    const gui::Rect& pane() const noexcept { return pane_; }
    std::uint64_t revision() const noexcept { return compiled_.revision; }
    bool same_layout(const EngineRegionComposition& other) const noexcept {
        return pane_ == other.pane_ && compiled_.client_size == other.compiled_.client_size &&
            compiled_.display_scale == other.compiled_.display_scale;
    }
    bool captures_scroll(const gui::WidgetKey& key) const noexcept {
        return key.id!=compiled_clip_id;
    }
    bool owns(const gui::WidgetKey& key) const noexcept {
        return gui::find_widget(compiled_, key) || gui::find_command(compiled_, key);
    }
    bool owns_event(gui::Event& value, const gui::Snapshot& published, const gui::ScrollLookup& scroll) const {
        if (!gui::normalize_event(published, value, scroll)) return false;
        if (const auto* widget = std::get_if<gui::WidgetEvent>(&value)) return owns(widget->target);
        if (const auto* page = std::get_if<gui::PageEvent>(&value))
            return std::any_of(compiled_.pages.begin(), compiled_.pages.end(),
                [&](const auto& candidate) { return candidate.id == page->id; });
        return false;
    }
    gui::Snapshot compose(const gui::Snapshot& current, const gui::Widget* frame) const {
        auto result = compiled_;
        result.revision = current.revision;
        if (frame) {
            auto bitmap = *frame;
            bitmap.state.bounds = pane_;
            // No parent/page alias: the rich pane is a root sibling of the
            // compiled content and uses its own exact owner/generation.
            bitmap.spec.page.clear(); bitmap.spec.parent.clear();
            result.widgets.insert(result.widgets.begin(), std::move(bitmap));
        }
        gui::validate_snapshot(result);
        return result;
    }
    // Safe redaction is an internally valid root candidate, including all
    // references which could otherwise name a removed compiled widget.
    static void clear_content(gui::Snapshot& value) noexcept {
        value.widgets.clear(); value.commands.clear(); value.key_bindings.clear(); value.modal_root.reset();
    }
    gui_surface::Rect surface_bounds() const noexcept {
        return {pane_.x,pane_.y,pane_.width,pane_.height};
    }
    gui_surface::Rect caret_to_root(gui_surface::Rect value) const {
        if (!finite(value)) throw std::invalid_argument("Nonfinite rich caret");
        const auto right = std::clamp(value.x + value.width,0.0,width);
        const auto bottom = std::clamp(value.y + value.height,0.0,height);
        value.x = std::clamp(value.x,0.0,width); value.y = std::clamp(value.y,0.0,height);
        value.width = std::max(0.0,right-value.x); value.height = std::max(0.0,bottom-value.y);
        value.x += pane_.x; value.y += pane_.y;
        return value;
    }
    // SurfacePolicy already owns hit testing, identity and capture. Captured
    // continuations outside the pane must preserve their exact displacement.
    // Native cancel and keyboard-context placeholders have no coordinate.
    bool input_to_engine(gui_surface::AcceptedEvent& value) const noexcept {
        return std::visit([&](auto& input) {
            using T = std::decay_t<decltype(input)>;
            if constexpr (std::is_same_v<T,gui_surface::MouseTransition>) {
                if (input.phase == gui_surface::MousePhase::cancel ||
                    (input.phase == gui_surface::MousePhase::context &&
                     input.context_origin == gui_surface::ContextOrigin::keyboard)) return true;
                if (!std::isfinite(input.x) || !std::isfinite(input.y)) return false;
                input.x -= pane_.x; input.y -= pane_.y;
            } else if constexpr (std::is_same_v<T,gui_surface::PointerTransition>) {
                if (input.phase == gui_surface::PointerPhase::cancel) return true;
                if (!std::isfinite(input.x) || !std::isfinite(input.y)) return false;
                input.x -= pane_.x; input.y -= pane_.y;
            }
            return true;
        },value.event.input);
    }

private:
    // General compiled candidates cannot retain opaque paint callables. The
    // typed binary source owns only validated image_bitmap storage with its
    // existing262144byte total image and16MiB raster budgets. Metadata has a
    // separate fixed bound; the real engine frame keeps its existing budget.
    void bound_storage(bool decoded_images) {
        const std::size_t limit = (decoded_images ? 4 : 1) * 1024 * 1024;
        std::size_t used = sizeof(gui::Snapshot);
        const auto charge = [&](std::size_t amount) {
            if (amount > limit - used) throw std::invalid_argument("Compiled region exceeds its retained metadata budget");
            used += amount;
        };
        const auto text = [&](const std::string& value) { charge(value.capacity()); };
        const auto vector = [&](const auto& values) {
            if (values.capacity() > limit / sizeof(typename std::decay_t<decltype(values)>::value_type))
                throw std::invalid_argument("Compiled region allocation exceeds its retained budget");
            charge(values.capacity() * sizeof(typename std::decay_t<decltype(values)>::value_type));
        };
        if (compiled_.widgets.size() > 1024 || compiled_.commands.size() > 1024)
            throw std::invalid_argument("Compiled region exceeds its node limit");
        text(compiled_.title); if (compiled_.active_page) text(*compiled_.active_page);
        if (compiled_.modal_root) text(compiled_.modal_root->id);
        vector(compiled_.pages); vector(compiled_.widgets); vector(compiled_.commands); vector(compiled_.key_bindings);
        for (const auto& page : compiled_.pages) { text(page.id); text(page.label); }
        for (auto& widget : compiled_.widgets) {
            if (widget.spec.kind == gui::Kind::bitmap && !decoded_images)
                throw std::invalid_argument("Private compiled region does not admit opaque bitmap callbacks");
            if(widget.spec.kind!=gui::Kind::bitmap) widget.state.bitmap = {}; // No unused hidden callback lifetime.
            const auto& spec = widget.spec; const auto& state = widget.state;
            text(spec.key.id); text(spec.page); text(spec.parent); text(spec.binding); text(state.bitmap.source_id);
            for (const auto* value : {&state.label,&state.text,&state.help,&state.accessible_name,&state.placeholder,&state.display_text}) text(*value);
            if (state.selected) text(*state.selected);
            vector(state.options); vector(state.actions); vector(state.records);
            for (const auto& values : {&state.options,&state.actions})
                for (const auto& option : *values) { text(option.id); text(option.label); text(option.value); }
            for (const auto& record : state.records) {
                text(record.id); text(record.accessible_text); vector(record.cells);
                for (const auto& cell : record.cells) text(cell.text);
            }
        }
        for (const auto& command : compiled_.commands) {
            text(command.key.id); if (command.scope) text(command.scope->id);
        }
        for (const auto& binding : compiled_.key_bindings) {
            text(binding.target.id); if (binding.focus) text(binding.focus->id);
        }
    }
    template<class Rect> static bool finite(const Rect& value) noexcept {
        return std::isfinite(value.x) && std::isfinite(value.y) &&
            std::isfinite(value.width) && std::isfinite(value.height) &&
            value.width >= 0 && value.height >= 0;
    }
    static bool intersects(const gui::Rect& a,const gui::Rect& b) noexcept {
        return a.x < b.x+b.width && b.x < a.x+a.width &&
            a.y < b.y+b.height && b.y < a.y+a.height;
    }
    gui::Snapshot compiled_;
    gui::Rect pane_;
};

// A compiled intent retains the exact source candidate which owned its key.
// A successor must not reinterpret an old event against a replacement view.
// Conservative retained-allocation charge, including string capacities.
inline std::size_t compiled_region_event_charge(const gui::Event& event) noexcept {
    std::size_t total = sizeof(gui::Event);
    const auto add = [&](std::size_t amount) {
        if (amount > static_cast<std::size_t>(-1) - total) total = static_cast<std::size_t>(-1);
        else total += amount;
    };
    if (const auto* widget = std::get_if<gui::WidgetEvent>(&event)) {
        add(widget->target.id.capacity());
        std::visit([&](const auto& input) {
            if constexpr (requires { input.value.capacity(); }) add(input.value.capacity());
            if constexpr (requires { input.base_text.capacity(); }) add(input.base_text.capacity());
            if constexpr (requires { input.id.capacity(); }) add(input.id.capacity());
            if constexpr (requires { input.source; }) if (input.source) add(input.source->id.capacity());
        },widget->input);
    } else if (const auto* page = std::get_if<gui::PageEvent>(&event)) add(page->id.capacity());
    else if (const auto* shortcut = std::get_if<gui::ShortcutEvent>(&event))
        if (shortcut->source) add(shortcut->source->id.capacity());
    return total;
}

struct CompiledRegionEvent {
    std::uint64_t revision{};
    gui::Event event; // Composed, normalized admission value for compiled features.
    gui::Event raw_event; // Original boundary value, normalized once against the Module view.
    std::optional<gui::WidgetKey> focused;
    std::vector<std::pair<gui::WidgetKey,gui::Point>> scroll_offsets;
    std::size_t retained_bytes{};
};
inline std::size_t compiled_region_event_charge(const CompiledRegionEvent& value) noexcept {
    return value.retained_bytes;
}

} // namespace foundation::ui
