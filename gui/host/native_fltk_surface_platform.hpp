// SPDX-License-Identifier: CC0-1.0
#pragma once

#include <foundation/gui/surface.hpp>
#include <foundation/gui/surface_editor.hpp>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <optional>
#include <string>
#include <vector>

namespace foundation::host {

// Owned native facts only. A passage is one observed native keyboard dispatch
// and its actual text/IME callbacks; it is not an editor authority or a guessed
// keyboard default. Platforms finish/copy their native passage before poll()
// publishes it on the serialized owner thread.
enum class FltkNativeEditKind { text, composition_begin, composition_update,
    composition_commit, composition_cancel, selection };
struct FltkNativeEdit {
    FltkNativeEditKind kind{FltkNativeEditKind::text};
    std::string text;
    // Actual native UTF-16 scalar boundaries: within preedit for composition,
    // or within the complete current frontend value for selection.
    std::size_t selection_start{}, selection_end{};
    bool backward{};
    std::uint64_t transaction{};
};
struct FltkNativePassage {
    std::optional<gui_surface::KeyTransition> key;
    std::vector<FltkNativeEdit> edits;
};
struct FltkNativeEditorConfiguration {
    gui_editor::TextObservation text;
    gui_surface::Rect caret;
    // An exact checked publication can refresh metadata without replacing an
    // OS preedit/draft that is causally ahead of the completed head.
    bool preserve_passage{};
};
struct FltkNativePlatformCallbacks {
    std::function<std::optional<gui_editor::TextObservation>()> surrounding;
    std::function<void(FltkNativePassage)> passage;
    std::function<void(std::string)> failure;
};
struct FltkNativeWindowFacts {
    std::int64_t drawable_width{}, drawable_height{};
    bool shown{}, foreground{}, focused{};
};

inline constexpr std::size_t fltk_native_max_passages=64;
inline constexpr std::size_t fltk_native_max_text_bytes=65536;

// A platform implementation named FltkNativePlatform is provided by the X11 or
// Win32 companion, with this interface:
//   (Fl_Window&, FltkNativePlatformCallbacks)
//   bool ready() const noexcept; bool editor_supported() const noexcept;
//   FltkNativeWindowFacts window_facts() const noexcept;
//   bool mouse_capture(bool acquire);
//   void editor(std::optional<FltkNativeEditorConfiguration>);
//   void foreground(bool); void suspend() noexcept; void poll();
// It owns only window-local keyboard/IME resources. Its callbacks never enter an
// application, provider or Registry directly. No global input-method disable,
// borrowed platform event, native pointer or platform handle crosses this leaf.

} // namespace foundation::host
