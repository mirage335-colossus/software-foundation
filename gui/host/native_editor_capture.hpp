// SPDX-License-Identifier: CC0-1.0
#pragma once

#include <foundation/gui/surface_editor.hpp>
#include <functional>
#include <memory>
#include <optional>

namespace foundation::host {

struct NativeEditorEndpoint {
    std::function<std::optional<std::uint64_t>(gui_editor::Packet)> submit;
    std::function<std::optional<std::uint64_t>(gui_editor::Revocation)> revoke;
    std::function<std::optional<gui_editor::EditorCompletion>(std::uint64_t)> take;
    std::function<void()> resync;
    gui_editor::EditorTerminalHook terminal;
    bool bound() const noexcept {
        return submit && revoke && take && resync && terminal.notify;
    }
};

// Actual owned frontend facts, without a native token, provider revision,
// observation ID or predecessor. No text or default authority is inferred from
// keys. Source groups/transactions come from explicit native passages.
struct NativeEditorObservation {
    gui_editor::Kind kind{gui_editor::Kind::key};
    gui_editor::Authority authority{gui_editor::Authority::native};
    std::optional<std::uint64_t> group;
    bool group_end{false};
    std::uint64_t transaction{0};
    gui_editor::TextObservation before;
    std::optional<gui_editor::TextObservation> after;
    gui_editor::Data data{gui_editor::KeyData{}};
};

// Strict Unicode scalar conversion. Both helpers validate the complete UTF-8
// value and reject NUL, malformed bytes and split UTF-16 surrogate/scalar bounds.
// Direction is supplied by the actual frontend; neither helper guesses it.
gui_editor::TextObservation capture_native_editor_text(std::string value,
    std::size_t utf16_start, std::size_t utf16_end, gui_editor::Direction);
gui_editor::TextObservation capture_native_editor_text(std::string value,
    gui_surface::ByteRange, gui_editor::Direction);

// Serialized frontend observation collector. It owns only bounded provisional
// frontend values and causal correlation; the application's existing Controller
// remains the sole native editor authority. All endpoint calls except the trusted
// atomic terminal hook occur in normal-owner tick(), never in ingress methods.
class NativeEditorCapture final {
public:
    static constexpr std::size_t max_pending=64, max_bytes=1048576, max_text_bytes=65536;
    explicit NativeEditorCapture(NativeEditorEndpoint);
    ~NativeEditorCapture();
    NativeEditorCapture(const NativeEditorCapture&)=delete;
    NativeEditorCapture& operator=(const NativeEditorCapture&)=delete;

    // Called only after the complete publication was checked, rendered with an
    // exact receipt and committed by the surface owner. Native context must join
    // actual_pair; presentation-only aliases retain the original basis revision.
    bool install(gui_editor::EditorPublication,
                 std::optional<gui_surface::Identity> actual_pair);
    std::optional<std::uint64_t> observe(NativeEditorObservation);
    // Continue collecting actual frontend facts for the still-owned ready
    // Basis during an inert publication pause. No native submission or rebase;
    // suspended/retired authority rejects immediately. The same bounds apply.
    std::optional<std::uint64_t> observe_paused(NativeEditorObservation);
    // Local source/transaction correlation only, never provider authority.
    std::optional<std::uint64_t> next_passage();
    void pause();
    // Inert checked-publication gate; preserves manual pause state and owned
    // passages. A subsequent exact checked publication may release this gate.
    void pause_pending();
    bool resume(const gui_editor::Basis&);
    // Revokes ingress immediately and queues owned cleanup/resync for tick.
    // A submitted head and any unknown completion remain owned, never replayed.
    void retire(std::string reason);
    void tick();
    void close() noexcept;

    gui_editor::State state() const noexcept;
    bool paused() const noexcept;
    const gui_editor::CompositionFact* composition() const noexcept;
    const gui_editor::Basis* basis() const noexcept;
    const gui_editor::TextObservation* draft() const noexcept;
    // Retained observation heads or a queued owner cleanup/resync phase.
    std::size_t pending() const noexcept;
    std::size_t pending_bytes() const noexcept;
    const gui_editor::Packet* unresolved() const noexcept;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace foundation::host
