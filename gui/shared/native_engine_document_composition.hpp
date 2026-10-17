#pragma once

#include "appended_document.hpp"
#include "native_engine_driver.hpp"
#include <gui/contract.hpp>
#include <gui/runtime.hpp>

#include <chrono>
#include <cstdint>
#include <functional>
#include <memory>
#include <optional>
#include <string>

namespace foundation::ui {

// Serialized native composition, with the existing document application as its
// sole presenter. The caller has already verified/loaded/bound/started the
// pixel1795 or independent document-actions4083 provider and supplied the real
// Owner, native Registry and optional Module.
// This facade never loads, starts, replaces or unloads an engine.
class NativeEngineDocumentComposition final {
public:
    using Clock = std::chrono::steady_clock;
    // Post a later owner-loop turn only. This may be called from a worker.
    // The caller keeps this facade alive during every method/callback/worker;
    // arbitrary self-destruction from a callback is not supported.
    // Synchronously pumping tick from this callback is refused.
    using PostOwnerWake = std::function<void()>;

    NativeEngineDocumentComposition(gui::Adapter&,
        std::shared_ptr<appended::EngineOwner>, appended::NativeEngineDriver&,
        PostOwnerWake = {});
    // Drain normal close through bounded tick calls until native_state() is
    // detached. An unresolved close or process-terminal state retains the whole
    // composition until process exit; destruction never forces ACK or unload.
    // In particular, close with an admitted document result may stay closing
    // with retained evidence; this facade does not synthesize its retirement.
    ~NativeEngineDocumentComposition();
    NativeEngineDocumentComposition(const NativeEngineDocumentComposition&) = delete;
    NativeEngineDocumentComposition& operator=(const NativeEngineDocumentComposition&) = delete;

    // Actual drawable terminal cells, with all chrome already excluded by the
    // caller. No ResizeEvent/minimum logical canvas is used as a substitute.
    // Zero, negative or out-of-range cells suspend the existing presenter; no
    // presenter is created until the first valid 1..500 by 1..200 dimensions.
    void drawable_cells(std::int64_t columns, std::int64_t drawable_rows);
    void foreground(bool);
    // Internal admission/publication hold; actual foreground/cell facts remain
    // unchanged. An actual outstanding external UI offer freezes Driver entry.
    void set_owned_service_active(bool);
    bool owned_service_ready() const noexcept;
    void set_owned_service_offered(bool);
    void wake() noexcept; // Schedule only; safe from a worker while alive.
    void handle(gui::Event); // Adapter callback entry: no Driver/provider entry.
    // Explicit host-supplied native DOM text endpoints for document-actions4083.
    // Value staging only; the existing App validates the committed body and
    // later tick enters the Driver after all Adapter callbacks have returned.
    bool queue_selection(DocumentSelection);

    // Call only after Adapter/Registry callbacks have returned. One bounded
    // stage -> Driver -> settle cycle; ACK/new work staged by settle waits for
    // a later tick. The caller retains its ordinary bounded loop and observes
    // deadline(); this function has no internal busy/retry loop.
    void tick(Clock::time_point now = Clock::now());
    void retry_presentation(); // Presenter only; never enters the Driver.
    void qualify(const std::function<void()>& present);
    void shutdown() noexcept; // Queue close only, never an engine export.

    const gui::Snapshot& view() const noexcept;
    std::uint64_t input_epoch() const noexcept;
    // Publication debt only, not proof that the Driver/Owner has no pending
    // service, timer, query or action-ACK work. It must not select a busy loop.
    bool presentation_pending() const noexcept;
    bool body_ready() const noexcept;
    bool modal_open() const noexcept;
    bool closed() const noexcept;
    const std::string& last_error() const noexcept;
    appended::NativeEngineState native_state() const noexcept;
    // Earliest Driver or 250ms readonly observation deadline. Observations use
    // the same paired query and coalesce behind native work, publication retry
    // and modal drafts. Background/invalid cells/close disable their deadline.
    // Call tick at this deadline even when no Adapter event has arrived.
    std::optional<Clock::time_point> deadline() const noexcept;

    // Application GUI services remain empty: actual native services are owned
    // by the injected Owner/Registry and drained only by the Driver.
    std::optional<gui::ServiceRequest> next_service();
    bool complete_service(gui::ServiceResult);

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace foundation::ui
