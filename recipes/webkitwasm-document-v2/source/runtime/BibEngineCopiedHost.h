// SPDX-License-Identifier: CC0-1.0
// Source-only successor. No WebCore or generated-Wasm qualification implied.
#pragma once
#include <foundation/appended/engine_provider.h>
#include "../portable/BibEngineCopiedRecord.h"
#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <span>
#include <thread>
#include <vector>

namespace bib::copied {

// Import arguments always name this engine's own memory. The JS adapter copies
// them to/from the independently owned kernel instance before returning.
using HostImport = std::int32_t (*)(void*, std::uint32_t, const std::uint8_t*,
    std::uint32_t, std::uint8_t*, std::uint32_t);
// Must terminate without C++ unwinding. A returning callback is followed by abort.
using HostFatal = void (*)(void*, const char*) noexcept;

struct AckObservation {
    std::uint32_t count{};
    BibEngineDocumentV1 document{};
    std::uint64_t through{};
    std::uint32_t status{};
    std::uint32_t control{};
};

// Process-lived callback shell. Never destroy/reset it after provider retention.
// Except WAKE, every method and callback runs on the construction thread.
class CopiedHost final {
public:
    using Import = HostImport;
    using Fatal = HostFatal;
    CopiedHost(Import, Fatal, void* context) noexcept;
    CopiedHost(const CopiedHost&) = delete;
    CopiedHost& operator=(const CopiedHost&) = delete;

    bool begin_dispatch(const Record&) noexcept;
    // Document action ACK has no native/Host turn or callback authority.
    bool begin_metadata_dispatch(const Record&) noexcept;
    // A naturally returned uncertain receipt may be copied for forensic use.
    // Only immutable owned evidence and process termination remain afterward.
    void poison_after_result() noexcept { poisoned_.store(true,std::memory_order_relaxed); }
    void end_dispatch() noexcept;
    const BibEngineHostV1& table() const noexcept { return table_; }
    BibEngineDocumentV1 current_identity() const noexcept { return current_; }
    bool poisoned() const noexcept { return poisoned_.load(std::memory_order_relaxed); }
    // The shim holds this outer scope across DELIVER and its initial collector.
    // Actual ProviderGuard/Bridge scopes nest inside it, without remote reentry.
    std::uint32_t enter_engine() noexcept;
    void leave_engine() noexcept;
    void clear_ack_observation() noexcept { ack_ = {}; }
    AckObservation ack_observation() const noexcept { return ack_; }
    // Called only after the real provider successfully disposes this old tuple.
    bool forget_disposed_document(const BibEngineDocumentV1&) noexcept;
    [[noreturn]] void fail(const char*) noexcept;

    std::size_t active_resource_contexts() const noexcept;
    std::size_t outstanding_resource_leases() const noexcept;
    std::uint64_t retained_resource_bytes() const noexcept { return retained_bytes_; }
    std::uint32_t local_depth() const noexcept { return depth_; }

private:
    struct Document {
        BibEngineDocumentV1 identity{};
        std::uint64_t frame{};
        bool closed{};
    };
    struct Epoch {
        CopiedHost* owner{};
        BibEngineDocumentV1 identity{};
        std::uint64_t token{};
        std::uint32_t leases{};
        bool retired{};
    };
    struct Lease {
        Epoch* epoch{};
        std::uint64_t token{}, kernel_token{};
        std::vector<std::uint8_t> body;
        std::array<std::uint8_t, 127> mime{};
        std::uint32_t mime_length{};
    };
    struct Receipt {
        Record record;
        std::uint32_t control{}, service{};
    };
    Receipt rpc(std::uint32_t, const BibEngineDocumentV1&, std::uint64_t transfer,
        std::uint32_t source, std::span<const std::uint8_t> body,
        std::span<std::uint8_t> request, std::span<std::uint8_t> response,
        bool begin_document = false) noexcept;
    void require_callback() noexcept;
    void adopt(const BibEngineDocumentV1&) noexcept;
    Document* document(std::uint64_t) noexcept;
    Epoch* epoch(std::uint64_t) noexcept;
    void clear_retired(Epoch&) noexcept;
    void retire_document_resources(const BibEngineDocumentV1&) noexcept;
    void release_kernel(Epoch&, std::uint64_t) noexcept;
    std::uint32_t service(std::uint32_t, std::uint64_t, std::uint64_t,
        const BibEngineBytesV1*, std::uint32_t) noexcept;
    std::uint64_t begin_document(const BibEngineDocumentV1*) noexcept;
    void close_document(std::uint64_t) noexcept;
    std::int32_t begin_epoch(const BibEngineDocumentV1*, BibEngineResourceEpochV1*) noexcept;
    void retire_epoch(std::uint64_t) noexcept;
    std::int32_t resolve(Epoch&, const BibEngineResourceRequestV1*, BibEngineResourceResponseV1*) noexcept;
    void release(Epoch&, std::uint64_t) noexcept;
    void damage(const BibEngineDamageV1*) noexcept;
    void timer(double, std::uint32_t) noexcept;
    void wake() noexcept;

    static void BIB_ENGINE_CALL c_wake(void*) noexcept;
    static void BIB_ENGINE_CALL c_timer(void*, double, std::uint32_t) noexcept;
    static void BIB_ENGINE_CALL c_damage(void*, const BibEngineDamageV1*) noexcept;
    static std::uint32_t BIB_ENGINE_CALL c_enter(void*) noexcept;
    static void BIB_ENGINE_CALL c_leave(void*) noexcept;
    static std::uint64_t BIB_ENGINE_CALL c_begin(void*, const BibEngineDocumentV1*) noexcept;
    static void BIB_ENGINE_CALL c_close(void*, std::uint64_t) noexcept;
    static std::uint32_t BIB_ENGINE_CALL c_submit(void*, std::uint64_t, const BibEngineBytesV1*, std::uint32_t) noexcept;
    static std::uint32_t BIB_ENGINE_CALL c_cancel(void*, std::uint64_t, std::uint64_t) noexcept;
    static std::uint32_t BIB_ENGINE_CALL c_ack(void*, std::uint64_t, std::uint64_t) noexcept;
    static std::int32_t BIB_ENGINE_CALL c_begin_epoch(void*, const BibEngineDocumentV1*, BibEngineResourceEpochV1*) noexcept;
    static void BIB_ENGINE_CALL c_retire_epoch(void*, std::uint64_t) noexcept;
    static std::int32_t BIB_ENGINE_CALL c_resolve(void*, const BibEngineResourceRequestV1*, BibEngineResourceResponseV1*) noexcept;
    static void BIB_ENGINE_CALL c_release(void*, std::uint64_t) noexcept;

    Import import_;
    Fatal fatal_;
    void* context_;
    const std::thread::id thread_{std::this_thread::get_id()};
    BibEngineHostV1 table_{};
    std::atomic<bool> poisoned_{};
    std::atomic<bool> metadata_only_{};
    bool active_{}, importing_{};
    std::uint32_t depth_{};
    std::uint64_t worker_{}, transfer_{}, next_lease_{1}, retained_bytes_{}, producer_revision_{}, highest_document_sequence_{};
    BibEngineDocumentV1 dispatch_{}, current_{};
    AckObservation ack_{};
    // One current + eight retired service documents, two independent contexts.
    std::array<Document, 9> documents_{};
    std::array<Epoch, 2> epochs_{};
    std::array<Lease, 64> leases_{};
};
} // namespace bib::copied
