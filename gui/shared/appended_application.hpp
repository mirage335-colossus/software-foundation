#pragma once

#include <foundation/appended/registry.hpp>
#include <foundation/appended/providers.hpp>
#include <gui/contract.hpp>
#include <gui/runtime.hpp>
#include <functional>
#include <memory>

namespace foundation::ui {

// The binary application owns all feature meaning and layout. This bridge only
// translates the versioned foundation.view value contract into the public GUI
// contract. It has one event-loop owner; no guest invocation is reentrant.
class AppendedApplication {
public:
    // Loads the verified binary component of this sealed, composed executable.
    explicit AppendedApplication(gui::Adapter& adapter);
    // The instance copies module bytes. Useful for embeddings and focused tests.
    // Generation zero requests the next kernel-issued instance generation.
    AppendedApplication(gui::Adapter& adapter, std::span<const std::uint8_t> module,
                        std::uint64_t generation = 0);
    ~AppendedApplication();
    AppendedApplication(const AppendedApplication&) = delete;
    AppendedApplication& operator=(const AppendedApplication&) = delete;

    const gui::Snapshot& view() const noexcept;
    void handle(gui::Event event);
    void tick();
    void shutdown() noexcept;
    void retry_presentation();
    std::optional<gui::ServiceRequest> next_service();
    bool complete_service(gui::ServiceResult result);
    // Composition-root API for other application layers. Calls must run after
    // renderer/native callbacks return, on the same serialized event-loop owner.
    // Provider and view events share one outbound sequence. Outcomes own bytes
    // and remain replayable until the owner explicitly acknowledges them.
    appended::ProviderDiscovery discover_provider(const appended::DiscoveryQuery&) const;
    appended::ProviderOutcome invoke_provider(const appended::ProviderRequest&);
    appended::ServiceStatus acknowledge_provider(std::uint64_t through_sequence) noexcept;
    void qualify(const std::function<void()>& present);
    bool presentation_pending() const noexcept;
    std::uint64_t input_epoch() const noexcept;
    std::uint64_t generation() const noexcept;

    static const appended::SchemaId& view_schema() noexcept;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace foundation::ui
