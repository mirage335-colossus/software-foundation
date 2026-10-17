// SPDX-License-Identifier: CC0-1.0
#pragma once

#include "native_surface_composition.hpp"
#include "adapter.hpp"
#include <gui/framebuffer.hpp>
#include <functional>
#include <memory>


namespace foundation::host {

// One generic Snapshot rasterizer -> actual Rev bitmap upload/draw/readback.
// Frame revisions are never substituted for the caller's Snapshot revision.
class NativeRevSurfacePeer final {
public:
    NativeRevSurfacePeer(gui::FramebufferAdapter&, const NativeSurfaceWindow&,
        NativeSurfaceIngress, NativeSurfaceMode);
    ~NativeRevSurfacePeer();
    NativeRevSurfacePeer(const NativeRevSurfacePeer&)=delete;
    NativeRevSurfacePeer& operator=(const NativeRevSurfacePeer&)=delete;
    NativeSurfacePeer peer() const;
    bool pump();
    bool closed() const;
    bool close_requested() const;
    const std::string& error() const;
private:
    struct Impl;
    std::shared_ptr<Impl> impl_;
};

} // namespace foundation::host
