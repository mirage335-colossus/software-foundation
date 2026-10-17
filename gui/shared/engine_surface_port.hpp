// SPDX-License-Identifier: CC0-1.0
#pragma once

#include <foundation/gui/surface.hpp>
#include <gui/contract.hpp>
#include <cstdint>

namespace foundation::ui {

// Composition owns the concrete forwarding object. The adapter it refers to
// outlives this port and the application; no backend object enters shared code.
class EngineSurfacePort {
public:
    virtual ~EngineSurfacePort() = default;
    virtual const gui_surface::Capabilities& capabilities() const noexcept = 0;
    virtual std::uint64_t generation() const noexcept = 0;
    virtual gui_surface::CommitResult present_pair(gui::Snapshot,
                                                    const gui_surface::Presentation&) = 0;
    // Trusted application/native service state. False never resurrects retired
    // authority: a subsequent bind and paired publication are still required.
    virtual void set_owned_service_active(bool) = 0;
};

} // namespace foundation::ui
