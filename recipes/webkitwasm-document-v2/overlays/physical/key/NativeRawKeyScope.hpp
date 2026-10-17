// SPDX-License-Identifier: CC0-1.0
#pragma once
#include <cstdint>
namespace foundation::appended::ndv2_physical {
enum class LocationResult : int { invalid = -1, inactive = 0, applied = 1 };
// The native owner retains the canonical atom, fresh non-atom marker and actual
// event/frame/document/view. This tiny portable state machine is shared with
// strict standalone tests; it is not a substitute for those engine objects.
class MarkerLocationGate final {
public:
    MarkerLocationGate(const void* marker, std::uint32_t location) noexcept
        : marker_(marker), location_(location) { }
    MarkerLocationGate(const MarkerLocationGate&) = delete;
    MarkerLocationGate& operator=(const MarkerLocationGate&) = delete;
    LocationResult consume(const void* marker, bool record_matches,
        bool authority_valid, unsigned& output) noexcept {
        // Distinct same-value/native ordinary events cannot borrow this scope.
        if (marker != marker_) return LocationResult::inactive;
        if (!marker_ || location_ > 3 || consumed_ || !record_matches || !authority_valid)
            return LocationResult::invalid;
        consumed_ = true; // Before author dispatch and before publishing location.
        output = location_;
        return LocationResult::applied;
    }
private:
    const void* marker_{};
    std::uint32_t location_{};
    bool consumed_{};
};
} // namespace foundation::appended::ndv2_physical
