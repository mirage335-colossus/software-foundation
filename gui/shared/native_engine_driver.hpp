#pragma once

#include "appended_engine_owner.hpp"
#include <foundation/appended/engine_provider.h>

#include <array>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <memory>
#include <optional>
#include <span>
#include <thread>

namespace foundation::appended {

// Private metadata matching only. Neither this value nor a mock C table proves
// that an artifact/SDK/runtime was verified. Native production admission and OS
// loading remain unavailable; no engine-private C++ header is consumed here.
struct NativeEngineExpectation {
    std::uint32_t target_system{}, target_processor{}, pointer_bits{};
    std::array<std::uint8_t, 32> contract_header_sha256{};
    std::array<std::uint8_t, 32> build_identity_sha256{};
    std::array<std::uint8_t, 32> source_recipe_sha256{};
    // Explicit ABI1.1 profile only. The default keeps exact legacy pixel259
    // admission; these source facts are not artifact/runtime qualification.
    engine_document::EngineDocumentProfileFacts document_profile;
    // Separate explicit editor2035 selection. Existing document/input facts
    // remain disabled in this selection and never gain editor authority.
    engine_editor::EngineEditorProfileFacts editor_profile;
    // Independent explicit kind4/4083 selection; all legacy profile facts stay disabled.
    engine_document_actions::EngineDocumentActionsProfileFacts document_actions_profile;
};

class NativeEngineProvider final {
public:
    static NativeEngineProvider checked(const BibEngineProviderV1&, const NativeEngineExpectation&);
private:
    BibEngineProviderV1 table_{};
    std::thread::id thread_;
    engine_document::EngineDocumentProfileFacts document_profile_;
    engine_editor::EngineEditorProfileFacts editor_profile_;
    engine_document_actions::EngineDocumentActionsProfileFacts document_actions_profile_;
    NativeEngineProvider(BibEngineProviderV1, std::thread::id,
        engine_document::EngineDocumentProfileFacts, engine_editor::EngineEditorProfileFacts,
        engine_document_actions::EngineDocumentActionsProfileFacts);
    friend class NativeEngineDriver;
};

// blocked retains a known rejected collection; this first stage has no implicit
// retry. Explicit close can retire it; uncertainty instead requires process exit.
enum class NativeEngineState { bound, waiting_document, ready, closing, detached, blocked, process_exit_required };
struct NativeEngineAudit {
    EngineIdentity identity;
    std::uint64_t transfer{};
    bool ack_receipt{};
    std::span<const std::uint8_t> original;
};
struct NativeEngineOptions {
    BibEngineLimitsV1 limits{sizeof(BibEngineLimitsV1), 65536, 65536, 65536,
        FOUNDATION_APPENDED_MAX_MESSAGE_BYTES, 8, 64, 0,
        max_appended_file_bytes, 128ULL * 1024 * 1024};
    std::chrono::milliseconds ready_timeout{30000};
    std::size_t maximum_steps_per_tick{16};
    // Explicit immutable trusted-owner policy. No external audit queue/history
    // is required: the owner retains the exact original bounded slot until the
    // chosen decision succeeds. An optional observer can copy/refuse that slot.
    // The first native driver requires true; retention is a future policy.
    bool abandon_closed_document_outcomes{true};
    std::function<bool(const NativeEngineAudit&)> observe_retirement;
};
struct NativeEngineWake {
    void* context{};
    void (*post_owner_wake)(void*) noexcept{}; // Schedule only; may run on a worker.
};

// Serialized C++20 consumer of the actual EngineOwner. One successful bind and
// one START per process. The callback shell, Package, service captures and table
// stay alive until process exit; closing a GUI is not provider destruction.
class NativeEngineDriver final {
public:
    static NativeEngineDriver& bind_once(NativeEngineProvider,
        std::shared_ptr<EngineOwner>, NativeEngineOptions = {}, NativeEngineWake = {});
    NativeEngineDriver(const NativeEngineDriver&) = delete;
    NativeEngineDriver& operator=(const NativeEngineDriver&) = delete;

    void start_once(std::chrono::steady_clock::time_point now = std::chrono::steady_clock::now());
    void tick(std::chrono::steady_clock::time_point now = std::chrono::steady_clock::now());
    void request_advance() noexcept;
    void request_close() noexcept; // Queue/revoke only; never enters the provider.
    NativeEngineState state() const noexcept;
    std::optional<std::chrono::steady_clock::time_point> deadline() const noexcept;
    std::shared_ptr<EngineOwner> owner() const noexcept;
    std::int32_t last_provider_status() const noexcept;
    std::uint32_t last_service_status() const noexcept;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
    explicit NativeEngineDriver(std::unique_ptr<Impl>);
    ~NativeEngineDriver(); // Intentionally unavailable: no unload/reset/teardown.
};

} // namespace foundation::appended
