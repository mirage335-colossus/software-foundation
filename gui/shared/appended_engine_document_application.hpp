#pragma once

#include "appended_document_controller.hpp"
#include <foundation/gui/document_endpoint.hpp>
#include <gui/runtime.hpp>
#include <functional>
#include <memory>
#include <optional>
#include <string>

namespace foundation::appended { class EngineOwner; }

namespace foundation::ui {

// One same-document terminal application and Forms compositor for the lifetime
// of an application_instance. The injected Owner outlives all retained work.
// This adapter only stages copied values after GUI/Registry callbacks return;
// it neither owns an engine nor supplies a provider/HTML parser/second DOM.
class AppendedEngineDocumentApplication {
public:
    AppendedEngineDocumentApplication(gui::Adapter&,
        std::shared_ptr<appended::EngineOwner>, DocumentViewport);
    ~AppendedEngineDocumentApplication();
    AppendedEngineDocumentApplication(const AppendedEngineDocumentApplication&) = delete;
    AppendedEngineDocumentApplication& operator=(const AppendedEngineDocumentApplication&) = delete;

    const gui::Snapshot& view() const noexcept;
    void handle(gui::Event);
    // Explicit host-supplied DOM text endpoints, not an inferred physical
    // terminal selection gesture. Staged only against the committed body.
    bool queue_selection(DocumentSelection);
    void tick();
    void retry_presentation();
    void viewport(DocumentViewport);
    void foreground(bool);
    // Internal application admission hold, separate from actual OS foreground.
    // Readiness means existing Forms/Broker/publication/effect debt settled.
    void set_owned_service_active(bool);
    bool owned_service_ready() const noexcept;
    // Coalesced readonly hint, never a native-effect publication acknowledgement.
    void request_observation();
    void shutdown() noexcept;
    bool presentation_pending() const noexcept;
    bool closed() const noexcept;
    bool body_ready() const noexcept;
    bool modal_open() const noexcept;
    std::uint64_t input_epoch() const noexcept;
    const std::string& last_error() const noexcept;
    // Metadata-only failure notification while the injected Owner remains alive.
    gui_document::TerminalHook document_terminal() noexcept;

    // Native services belong to Owner/Registry, not GUI service simulation.
    std::optional<gui::ServiceRequest> next_service();
    bool complete_service(gui::ServiceResult);
    void qualify(const std::function<void()>& present);
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace foundation::ui
