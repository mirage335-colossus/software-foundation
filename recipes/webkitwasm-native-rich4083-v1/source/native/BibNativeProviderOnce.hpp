// SPDX-License-Identifier: CC0-1.0
// Private native binding controller; not a public ABI.
#pragma once
#include <foundation/appended/engine_provider.h>
#include <atomic>
#include <cstdint>
#include <new>

namespace bib::provider_candidate {
class NativeProviderOnce final {
public:
    constexpr NativeProviderOnce() noexcept = default;
    NativeProviderOnce(const NativeProviderOnce&) = delete;
    NativeProviderOnce& operator=(const NativeProviderOnce&) = delete;

    // bind is private metadata-only registration. onOwner is an inert, noexcept
    // comparison of the published binding's immutable thread identity. Neither
    // callback may invoke Host, Page, VM, resource lookup, author script or START.
    template<class Bind, class Owner>
    std::int32_t ensure(Bind&& bind, Owner&& onOwner) noexcept
    {
        static_assert(noexcept(onOwner()), "Native owner predicate must be inert/noexcept");
        auto observed = phase.load(std::memory_order_acquire);
        if (observed != Phase::unbound)
            return observedStatus(observed, onOwner);
        if (!phase.compare_exchange_strong(observed, Phase::binding,
                std::memory_order_acq_rel, std::memory_order_acquire))
            return observedStatus(observed, onOwner);

        std::int32_t status;
        try {
            status = bind();
        } catch (const std::bad_alloc&) {
            status = BIB_ENGINE_LIMIT;
        } catch (...) {
            status = BIB_ENGINE_PROCESS_EXIT_REQUIRED;
        }
        if (status > BIB_ENGINE_OK || status < BIB_ENGINE_PROCESS_EXIT_REQUIRED)
            status = BIB_ENGINE_PROCESS_EXIT_REQUIRED;
        if (status == BIB_ENGINE_OK && !onOwner())
            status = BIB_ENGINE_PROCESS_EXIT_REQUIRED;
        if (status == BIB_ENGINE_OK) {
            // The winning thread has published State, immutable owner and all
            // retained handlers before other calls may examine that State.
            phase.store(Phase::ready, std::memory_order_release);
        } else {
            terminalStatus = status;
            phase.store(Phase::failed, std::memory_order_release);
        }
        return status;
    }

private:
    enum class Phase : std::uint8_t { unbound, binding, ready, failed };
    template<class Owner>
    std::int32_t observedStatus(Phase observed, Owner& onOwner) const noexcept
    {
        if (observed == Phase::ready)
            return onOwner() ? BIB_ENGINE_OK : BIB_ENGINE_WRONG_THREAD;
        if (observed == Phase::failed)
            return terminalStatus;
        // No waiting or retrying a factory while another/reentrant call owns it.
        return BIB_ENGINE_REENTRANT;
    }
    std::atomic<Phase> phase{Phase::unbound};
    // Written once before release-publishing failed; read after acquire only.
    std::int32_t terminalStatus{BIB_ENGINE_UNSUPPORTED};
};
}
