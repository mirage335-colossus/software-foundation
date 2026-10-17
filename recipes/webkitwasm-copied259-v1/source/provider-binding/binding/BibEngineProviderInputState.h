// SPDX-License-Identifier: CC0-1.0
// Private source candidate: scalar state tests do not qualify WebCore behavior.
#pragma once
#include "BibEngineProviderCodec.h"

namespace bib::provider_candidate {
// One negotiated mouse, never a general raw-pointer/surface capability. Wire
// buttons follow DOM bits: left=1, right=2, middle=4; button ordinals are 0/1/2.
class MouseState final {
public:
    [[nodiscard]] bool accepts(const codec::MouseInput& input) const noexcept {
        using codec::MousePhase;
        if (input.logical_pointer_id != 1 || input.button > 2 || (input.buttons & ~7u)) return false;
        constexpr unsigned bits[] { 1u, 4u, 2u };
        const auto bit = bits[input.button];
        switch (input.phase) {
        case MousePhase::down: return !(buttons_ & bit) && input.buttons == (buttons_ | bit);
        case MousePhase::up: return (buttons_ & bit) && input.buttons == (buttons_ & ~bit);
        case MousePhase::move:
        case MousePhase::wheel: return input.buttons == buttons_;
        case MousePhase::cancel: return !input.buttons;
        }
        return false;
    }
    // Call only immediately before the first engine effect. No replay/rollback
    // after author JS has run, including navigation during cancel dispatch.
    void consume(const codec::MouseInput& input) noexcept {
        buttons_ = input.buttons; x_ = input.x; y_ = input.y;
    }
    void clear() noexcept { buttons_ = 0; }
    [[nodiscard]] unsigned buttons() const noexcept { return buttons_; }
    [[nodiscard]] double x() const noexcept { return x_; }
    [[nodiscard]] double y() const noexcept { return y_; }
private:
    unsigned buttons_{};
    double x_{}, y_{};
};
}
