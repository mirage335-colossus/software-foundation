// SPDX-License-Identifier: CC0-1.0
#pragma once
#include "../state.hpp"
#include <filesystem>

namespace foundation::host {
struct NativeFramebufferOutput {
    std::function<NativeRenderReceipt(const gui::Frame&,std::uint64_t)> present;
};
inline NativeFramebufferOutput native_framebuffer_ppm_output(std::filesystem::path path) {
    ++bitmap_framebuffer_fixture::outputs;
    bitmap_framebuffer_fixture::require(!path.empty(),"framebuffer lost output path");
    return {[](const gui::Frame& frame,std::uint64_t revision) {
        ++bitmap_framebuffer_fixture::artifacts;
        bitmap_framebuffer_fixture::require(bitmap_framebuffer_fixture::closing&&frame.pixels&&
            frame.width==1&&frame.height==1&&frame.revision==41&&revision==73,
            "artifact was not retained first image after completed close");
        return NativeRenderReceipt{revision};
    }};
}
inline NativeSurfacePeer prepare_native_framebuffer_surface_peer(gui::Adapter&,
        const NativeSurfaceWindow&,NativeSurfaceIngress,NativeFramebufferOutput) {
    throw std::logic_error("render-loop fixture must not claim a real peer");
}
}
