#pragma once

#include "appended_document_codec.hpp"
#include <gui/contract.hpp>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>
#include <string>

namespace foundation::ui {

// The composition owner supplies ACTUAL drawable cells, excluding terminal
// chrome. Logical ResizeEvent dimensions may include a larger minimum canvas.
struct DocumentViewport {
    std::size_t columns = 80, drawable_rows = 23;
    bool operator==(const DocumentViewport&) const = default;
};
struct DocumentRequestToken {
    std::uint64_t generation = 0, id = 0;
    bool operator==(const DocumentRequestToken&) const = default;
};
struct DocumentEngineRequest {
    DocumentRequestToken token;
    // Absent means snapshot. Actions carry the EXACT displayed DOM version;
    // the engine must sync its live state and check this version atomically.
    std::optional<DocumentIntent> intent;
};
enum class DocumentRequestFailure { known_rejected, unknown };

// Serialized UI-owner controller for disposable values exported by ONE engine
// document. It neither owns an engine nor interprets HTML, script or edits.
// Adapter callbacks call handle() only; the owner calls tick()/next_request()
// after those callbacks return, executes the returned request, then supplies an
// owned decoded completion. There is at most one outstanding engine request.
// The owner must use a fresh nonzero generation for every replacement engine.
class AppendedDocumentController {
public:
    static constexpr std::size_t max_queued_intents = 32;

    AppendedDocumentController(gui::Adapter&, std::uint64_t generation, DocumentViewport);
    ~AppendedDocumentController();
    AppendedDocumentController(const AppendedDocumentController&) = delete;
    AppendedDocumentController& operator=(const AppendedDocumentController&) = delete;

    void handle(gui::Event);
    // Explicit composition-owned DOM text points. The list projection cannot
    // read a physical text selection through Adapter::text_selection().
    bool queue_selection(DocumentSelection);
    // 1..500 columns, 1..200 drawable rows. A dimension below two presents a
    // noninteractive notice instead of inventing a larger terminal viewport.
    void viewport(DocumentViewport);
    void request_snapshot();
    // Yield only an exact committed idle view. Refusal preserves queued and
    // already-returned work. Success revokes input and automatic refresh; the
    // owner explicitly request_snapshot() after its serialized operation ends.
    bool suspend_input();
    // Reverse only an explicit suspension of this exact unchanged displayed
    // version, with no queued work, refresh or presentation debt. This permits
    // a local modal Cancel to restore input without inventing an observation.
    // Any native uncertainty instead requires a fresh snapshot.
    bool resume_input(DocumentVersion);
    // Only local navigation, reflow and presentation; never calls an engine.
    void tick();
    // Retries the already-owned presentation. Failure propagates, retains the
    // candidate, and cannot repeat a DOM action or arm input for a failed view.
    void retry_presentation();
    std::optional<DocumentEngineRequest> next_request();
    // False means a foreign/duplicate token; the outstanding request is intact.
    // True consumes the matching request, including producer errors/malformed
    // replies. Inspect synchronized()/last_error() for its outcome. All action
    // failures discard queued input and seek a fresh snapshot, never a replay.
    bool complete_request(DocumentRequestToken, DocumentSemanticReply);
    bool fail_request(DocumentRequestToken, DocumentRequestFailure);
    // Consume only the exact outstanding action when the owner has a certain
    // completion without a same-document publication. This is reason-neutral:
    // no observed result or failure is invented. Discard queued old input,
    // revoke its epoch and seek a fresh snapshot before restoring input.
    // False preserves a foreign/duplicate token or an outstanding snapshot.
    bool consume_request_without_publication(DocumentRequestToken);
    // Revokes input/outstanding completions immediately. No adapter or engine
    // destruction occurs here, so CloseEvent is safe inside an adapter callback.
    void shutdown() noexcept;

    const gui::Snapshot& view() const noexcept;
    std::uint64_t input_epoch() const noexcept;
    bool presentation_pending() const noexcept;
    bool synchronized() const noexcept;
    bool closed() const noexcept;
    const std::string& last_error() const noexcept;
    // Complete owned last accepted engine update, including native selection
    // geometry/degradation. It remains an observation, never an edit authority.
    const DocumentSemanticReply* observation() const noexcept;
    // Readonly owned candidate (possibly awaiting publication). Copy any row
    // bindings before external callbacks; subsequent controller mutation revokes
    // this pointer. Publication still needs tick()/retry_presentation() ACK.
    const DocumentProjection* candidate_projection() const noexcept;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace foundation::ui
