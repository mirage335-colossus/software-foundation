// SPDX-License-Identifier: CC0-1.0
// Bare framebuffer output is a view-only saved image, not an input device.
#include "appended_engine_native_entry.hpp"
#include "host/native_framebuffer_surface_peer.hpp"
#include "host/native_session.hpp"
#include <gui/framebuffer.hpp>

namespace {
using Clock = std::chrono::steady_clock;
void wait_turn(const foundation::host::RunnerState& state, Clock::time_point limit) {
    const auto now = Clock::now();
    auto until = std::min(limit, now + std::chrono::milliseconds(30));
    if (state.deadline) until = std::min(until, *state.deadline);
    // A retained expired deadline selects another ordinary bounded turn rather
    // than a hot loop. No provider call or completion is synthesized here.
    if (until <= now) until = std::min(limit, now + std::chrono::milliseconds(1));
    if (until > now) std::this_thread::sleep_until(until);
}
int render(foundation::host::native_bitmap_entry::Factory factory,
           const foundation::host::native_bitmap_entry::Invocation& invocation) {
    namespace host = foundation::host;
    namespace entry = host::native_bitmap_entry;
    if (!invocation.output || factory.mode != host::NativeSurfaceMode::none)
        throw std::invalid_argument("Bare framebuffer needs an explicit view-only output");
    const auto path = *invocation.output;
    auto output = host::native_framebuffer_ppm_output(path);
    factory.prepare_peer = [output](gui::Adapter& adapter, const host::NativeSurfaceWindow& window,
                                    host::NativeSurfaceIngress ingress) mutable {
        return host::prepare_native_framebuffer_surface_peer(adapter, window, std::move(ingress), output);
    };
    gui::Frame retained;
    std::uint64_t retained_snapshot_revision{};
    bool detached{}, failed{};
    {
        using Session = host::NativeSession<entry::PreparedApplication, gui::FramebufferAdapter, entry::Factory>;
        Session session(std::move(factory));
        // The actual prepared framebuffer peer already reports its configured
        // device canvas and output activity from activate() after Session arm.
        // It has no OS focus, input device or editor capability to advertise.
        session.application.request_frame();
        const auto first_frame_limit = Clock::now() + std::chrono::seconds(30);
        while (Clock::now() < first_frame_limit) {
            session.tick();
            const auto state = session.runner_state();
            if (state.exit_code) { failed = true; break; }
            if (session.application.frame_ready()) {
                retained = session.adapter.frame();
                retained_snapshot_revision = session.surface().snapshot().revision;
                break;
            }
            if (state.close_requested || state.close_complete) break;
            wait_turn(state, first_frame_limit);
        }
        // Keep the concrete renderer alive throughout real App/Driver retirement.
        // Missing frames, blocked state and timeouts are failures, not successes.
        session.application.shutdown();
        const auto close_limit = Clock::now() + std::chrono::seconds(10);
        for (;;) {
            const auto state = session.runner_state();
            if (state.exit_code) failed = true;
            if (state.close_complete) { detached = true; break; }
            if (failed || Clock::now() >= close_limit) break;
            session.tick();
            wait_turn(session.runner_state(), close_limit);
        }
    }
    if (failed || !detached || !retained_snapshot_revision || !retained.pixels || retained.pixels->empty()) {
        std::cerr << "No complete native framebuffer image or graceful close; state is retained until process exit.\n";
        return 1;
    }
    // Rendering redaction/close may have changed the live output. After actual
    // detach, save the immutable first page image as the requested artifact.
    // It establishes no active Surface authority or engine effect receipt.
    auto saved = host::native_framebuffer_ppm_output(path);
    const auto receipt = saved.present(retained, retained_snapshot_revision);
    if (receipt.snapshot_revision != retained_snapshot_revision)
        throw std::runtime_error("Framebuffer artifact did not complete");
    std::cout << "Rendered view-only native frame " << retained.width << 'x' << retained.height << '\n';
    return 0;
}
} // namespace

int main(int argc, char** argv) {
    namespace entry = foundation::host::native_bitmap_entry;
    return entry::run(argc, argv, {.read_only = true, .output_required = true}, render);
}
