// SPDX-License-Identifier: CC0-1.0
// PRIVATE SOURCE CANDIDATE. No WebCore or actual-engine execution evidence.
#pragma once
#include <foundation/appended/engine_provider.h>
#include "legacy/BibAppResourceHost.h"
#include "legacy/BibFoundationServiceHost.h"
#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <thread>
#include <vector>

namespace bib::provider_candidate {

// The provider v1 proposal does not expose these two legacy facade bounds.
// Composition must supply its actual bounds rather than deriving invented ones.
struct ServiceRetentionLimits {
    std::uint32_t max_retained_calls{};
    std::uint32_t max_retained_bytes{};
};

// Owns exact copied legacy tables, never application/engine objects. Keep this
// nonmovable callback shell alive through the engine and every raw resource
// lease. No destructor/reset/unload operation is supplied by the provider ABI.
// All operations except schedule_owner belong to the construction thread.
class LegacyHostAdapters final {
public:
    LegacyHostAdapters(const BibEngineHostV1&, const BibEngineLimitsV1&,
        ServiceRetentionLimits);
    LegacyHostAdapters(const LegacyHostAdapters&) = delete;
    LegacyHostAdapters& operator=(const LegacyHostAdapters&) = delete;
    LegacyHostAdapters(LegacyHostAdapters&&) = delete;
    LegacyHostAdapters& operator=(LegacyHostAdapters&&) = delete;

    [[nodiscard]] bool valid() const noexcept { return valid_; }
    [[nodiscard]] bool supports_services() const noexcept;
    [[nodiscard]] bool supports_resources() const noexcept;
    // Use the composition-issued prospective identity for both independent
    // legacy begin callbacks. A resource epoch is never service authority.
    [[nodiscard]] std::int32_t set_prospective_document(const BibEngineDocumentV1&) noexcept;
    [[nodiscard]] BibFoundationServiceHostV1 service_hooks() noexcept;
    [[nodiscard]] BibAppResourceBundleHostV1 resource_bundle_hooks() noexcept;
    [[nodiscard]] std::size_t active_resource_contexts() const noexcept;
    [[nodiscard]] std::size_t outstanding_resource_leases() const noexcept;
    [[nodiscard]] std::uint64_t retained_raw_resource_bytes() const noexcept;
    [[nodiscard]] bool callback_faulted() const noexcept {
        return callback_faulted_.load(std::memory_order_relaxed);
    }

private:
    // Narrow standalone test peer exercises nonwrapping counter boundaries;
    // it adds no C callback or provider ABI surface.
    friend struct LegacyHostAdaptersTestAccess;
    struct EpochContext {
        LegacyHostAdapters* owner{};
        BibEngineResourceEpochV1 producer{};
        std::uint64_t legacy_epoch{};
        bool occupied{};
        bool retired{};
        bool resolving{};
        std::uint32_t outstanding{};
    };
    struct RawLease {
        std::uint64_t token{};
        std::uint64_t producer_lease{};
        std::uint64_t body_bytes{};
        EpochContext* epoch{};
    };
    struct CallbackScope {
        explicit CallbackScope(LegacyHostAdapters& owner) noexcept : owner_(owner) { ++owner_.callback_depth_; }
        ~CallbackScope() { --owner_.callback_depth_; }
        LegacyHostAdapters& owner_;
    };
    [[nodiscard]] bool owner_thread() const noexcept;
    [[nodiscard]] bool prospective_ready() const noexcept;
    void fault() noexcept { callback_faulted_.store(true, std::memory_order_relaxed); }
    void retire_producer(std::uint64_t) noexcept;
    void release_producer(EpochContext&, std::uint64_t) noexcept;
    void clear_retired(EpochContext&) noexcept;
    static std::uint32_t checked_service_status(std::uint32_t) noexcept;
    static std::uint32_t enter_engine(void*) noexcept;
    static void leave_engine(void*) noexcept;
    static std::uint64_t begin_document(void*) noexcept;
    static void close_document(void*, std::uint64_t) noexcept;
    static std::uint32_t submit(void*, std::uint64_t, const std::uint8_t*, std::uint32_t, std::uint32_t) noexcept;
    static std::uint32_t cancel(void*, std::uint64_t, std::uint64_t) noexcept;
    static std::uint32_t acknowledge(void*, std::uint64_t, std::uint64_t) noexcept;
    static void schedule_owner(void*) noexcept;
    static std::int32_t begin_epoch(void*, BibAppResourceHostV1*) noexcept;
    static void retire_epoch(void*, std::uint64_t) noexcept;
    static std::int32_t resolve(void*, const BibAppResourceRequestV1*, BibAppResourceResponseV1*) noexcept;
    static void release(void*, std::uint64_t) noexcept;

    const BibEngineHostV1 host_;
    const BibEngineLimitsV1 limits_;
    const ServiceRetentionLimits retention_;
    const std::thread::id thread_{std::this_thread::get_id()};
    const bool valid_;
    BibEngineDocumentV1 prospective_{};
    std::array<EpochContext, 2> epochs_{};
    // One bounded session-wide lease registry, shared across both contexts.
    // Allocation occurs only during construction, before table retention.
    std::vector<RawLease> leases_;
    std::uint64_t next_epoch_{1}; // Private legacy identity, never wraps/reuses.
    std::uint64_t next_lease_{1}; // zero is exhausted, never wraps or reuses.
    std::uint64_t raw_bytes_{};
    std::uint32_t callback_depth_{};
    bool beginning_epoch_{};
    std::atomic<bool> callback_faulted_{};
};
}
