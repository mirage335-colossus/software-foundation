#include "appended_document_controller.hpp"

#include <gui/runtime.hpp>
#include <algorithm>
#include <cmath>
#include <deque>
#include <limits>
#include <stdexcept>
#include <thread>
#include <utility>

namespace foundation::ui {
namespace {
constexpr std::uint64_t safe_integer = 9007199254740991ULL;
void validate_viewport(DocumentViewport viewport) {
    if (!viewport.columns || viewport.columns > 500 || !viewport.drawable_rows || viewport.drawable_rows > 200)
        throw std::invalid_argument("Invalid drawable document viewport");
}
void validate_observation(const DocumentSemanticReply& reply) {
    if (!reply.epoch || reply.epoch > std::numeric_limits<std::uint32_t>::max() ||
        reply.metadata.size() > AppendedDocument::max_nodes || !reply.editor_state ||
        !reply.editor_state->revision || reply.editor_state->revision > std::uint32_t(std::numeric_limits<std::int32_t>::max()) ||
        reply.editor_state->flags > 31)
        throw std::invalid_argument("Invalid document observation");
    std::size_t bytes = 0;
    for (const auto& node : reply.metadata) {
        for (const auto* text : {&node.role, &node.display, &node.white_space}) {
            if (!gui::valid_utf8(*text) || text->size() > AppendedDocument::max_field_units * 4 ||
                text->size() > max_document_semantic_json_bytes - bytes)
                throw std::invalid_argument("Invalid document observation metadata");
            bytes += text->size();
        }
    }
    if (reply.original_selection) {
        const auto& rect = reply.original_selection->focus_rect;
        // Raw DOM observation coordinates are not GUI widget geometry. Long
        // pages may legitimately exceed the GUI coordinate budget.
        if (!std::isfinite(rect.x) || !std::isfinite(rect.y) || !std::isfinite(rect.width) ||
            !std::isfinite(rect.height) || rect.width < 0 || rect.height < 0)
            throw std::invalid_argument("Invalid document selection geometry");
    }
}
struct Flag {
    bool& value;
    explicit Flag(bool& flag) : value(flag) { value = true; }
    ~Flag() { value = false; }
};
} // namespace

struct AppendedDocumentController::Impl {
    struct Queued {
        DocumentVersion version;
        std::optional<DocumentIntent> intent;
        std::string row;
    };
    gui::Adapter& adapter;
    const std::thread::id owner = std::this_thread::get_id();
    const std::uint64_t generation;
    DocumentViewport viewport;
    AppendedDocument document;
    std::optional<DocumentSemanticReply> observation;
    std::optional<DocumentProjection> candidate, presented;
    gui::Snapshot view;
    std::deque<Queued> queue;
    std::optional<DocumentEngineRequest> outstanding;
    // A cursor through projected rows is disposable presentation state, not
    // an optimistic DOM focus/selection or a second editable document model.
    std::optional<std::string> cursor;
    std::uint64_t epoch = 1, revision = 0, request_id = 0;
    bool stopped = false, synchronized = false, refresh = true, suspended = false;
    bool dirty = true, pending = false, handling = false, building = false, presenting = false;
    std::string error;

    Impl(gui::Adapter& value, std::uint64_t instance, DocumentViewport size)
        : adapter(value), generation(instance), viewport(size) {
        if (!generation) throw std::invalid_argument("Document generation is zero");
        validate_viewport(size);
    }
    void require_owner() const {
        if (owner != std::this_thread::get_id()) throw std::logic_error("Document controller has a different owner");
    }
    void require_quiet() const {
        require_owner();
        if (handling || building || presenting) throw std::logic_error("Reentrant document controller operation");
    }
    void stop() noexcept {
        stopped = true; synchronized = false; refresh = suspended = false; dirty = pending = false;
        epoch = std::numeric_limits<std::uint64_t>::max();
        queue.clear(); outstanding.reset(); candidate.reset(); presented.reset(); cursor.reset(); observation.reset();
    }
    void advance_epoch() {
        if (epoch >= std::numeric_limits<std::uint64_t>::max() - 1) {
            stop(); throw std::overflow_error("Document input epoch exhausted");
        }
        ++epoch;
    }
    bool usable_input() const {
        return !stopped && !adapter.closed() && synchronized && !outstanding && !dirty && !pending &&
            !building && !presenting && presented && candidate &&
            presented->version == candidate->version;
    }
    bool enqueue(Queued value) {
        if (queue.size() == max_queued_intents) {
            stop(); return false;
        }
        queue.push_back(std::move(value)); return true;
    }
    void handle(gui::Event event) {
        require_owner();
        if (std::holds_alternative<gui::CloseEvent>(event)) { stop(); return; }
        if (handling || !usable_input()) return;
        // Scroll lookup is a host call. Keep the validation input alive even
        // if a host closes the controller while answering that observation.
        const auto projection = *presented;
        Flag callback(handling);
        if (!gui::normalize_event(projection.view, event,
            [&](const gui::WidgetKey& key) { return adapter.scroll_offset(key); })) return;
        if (stopped || adapter.closed()) return;
        const auto* widget = std::get_if<gui::WidgetEvent>(&event);
        if (!widget) return; // Geometry is supplied explicitly by the host.
        if (const auto* selected = std::get_if<gui::SelectRecord>(&widget->input)) {
            const auto row = std::find_if(projection.rows.begin(), projection.rows.end(),
                [&](const DocumentRow& value) { return value.id == selected->id; });
            if (row == projection.rows.end()) return;
            auto intent = document.intent(projection, row->id, DocumentAction::focus);
            // Prose navigation only selects a disposable projected row.
            enqueue({projection.version, std::move(intent), row->id});
        } else if (const auto* activated = std::get_if<gui::ActivateRecord>(&widget->input)) {
            if (auto intent = document.intent(projection, activated->id, DocumentAction::activate))
                enqueue({projection.version, std::move(intent), {}});
        }
    }
    void build() {
        if (!dirty || stopped || adapter.closed()) return;
        Flag callback(building);
        std::optional<DocumentProjection> projection;
        gui::Snapshot next;
        if (document.snapshot() && viewport.columns >= 2 && viewport.drawable_rows >= 2) {
            projection = document.project(viewport.columns, viewport.drawable_rows,
                [&](const gui::TextMeasureRequest& request) { return adapter.measure_text(request); });
            if (cursor) {
                const auto found = std::find_if(projection->rows.begin(), projection->rows.end(),
                    [&](const DocumentRow& row) { return row.id == *cursor; });
                if (found != projection->rows.end()) projection->view.widgets.front().state.selected = *cursor;
                else cursor.reset();
            }
            next = projection->view;
        } else {
            const auto cell = adapter.measure_text({"M", {}, gui::coordinate_limit, 1, gui::TextWrap::none});
            if (!std::isfinite(cell.width) || cell.width <= 0 || cell.width > 4096 ||
                !std::isfinite(cell.height) || cell.height <= 0 || cell.height > 4096)
                throw std::invalid_argument("Invalid document cell measurement");
            next.title = document.snapshot() ? "Document viewport is too small" : "Awaiting document snapshot";
            next.client_size = {double(viewport.columns) * cell.width, double(viewport.drawable_rows) * cell.height};
            if (document.snapshot()) {
                // Retain the GUI lifetime while too small. Removing the list
                // and later restoring its same generation would reuse a retired
                // WidgetKey in adapters that enforce lifetime identities.
                gui::Widget dormant;
                dormant.spec.key = {"appended/document/" + std::to_string(document.snapshot()->version.epoch), generation};
                dormant.spec.kind = gui::Kind::list; dormant.spec.row_height = cell.height;
                dormant.state.bounds = {0, 0, next.client_size.width, next.client_size.height};
                dormant.state.visible = false; dormant.state.enabled = false;
                next.widgets.push_back(std::move(dormant));
            }
        }
        if (stopped || adapter.closed()) return;
        if (revision == std::numeric_limits<std::uint64_t>::max()) {
            stop(); throw std::overflow_error("Document presentation revision exhausted");
        }
        next.revision = ++revision;
        gui::validate_snapshot(next);
        if (projection) projection->view.revision = next.revision;
        candidate = std::move(projection); view = std::move(next); dirty = false; pending = true;
    }
    void present() {
        if (!stopped && adapter.closed()) stop();
        if (!pending || stopped) return;
        // Reserve the commit copy before entering a script/native-capable
        // adapter. Allocation failure cannot claim an unowned presented view.
        auto commit = candidate;
        Flag callback(presenting);
        adapter.present(view);
        if (stopped || adapter.closed()) return;
        presented = std::move(commit); pending = false;
    }
    void tick() {
        require_quiet();
        if (stopped || adapter.closed()) { if (!stopped) stop(); return; }
        if (!outstanding && synchronized && !pending && !dirty) {
            while (!queue.empty() && !queue.front().intent) {
                auto queued = std::move(queue.front()); queue.pop_front();
                if (document.snapshot() && queued.version == document.snapshot()->version) {
                    cursor = std::move(queued.row); dirty = true;
                }
            }
        }
        build(); present();
    }
    std::optional<DocumentEngineRequest> next() {
        require_quiet();
        if (stopped || adapter.closed()) { if (!stopped) stop(); return std::nullopt; }
        if (outstanding) return std::nullopt;
        std::optional<DocumentIntent> intent;
        if (usable_input()) {
            while (!queue.empty()) {
                if (!queue.front().intent) return std::nullopt; // Owner tick handles local navigation.
                auto queued = std::move(queue.front()); queue.pop_front();
                if (document.current(*queued.intent)) { intent = std::move(queued.intent); break; }
            }
        }
        if (!intent && !refresh) return std::nullopt;
        if (request_id == safe_integer) { stop(); throw std::overflow_error("Document request identity exhausted"); }
        DocumentEngineRequest request{{generation, request_id + 1}, std::move(intent)};
        // Own both copies BEFORE admitting an action. The caller owns its
        // return value; the controller retains the identity until completion.
        auto retained = request;
        if (request.intent) advance_epoch();
        outstanding = std::move(retained); ++request_id; refresh = false;
        return request;
    }
    void failed(bool action, const char* message) {
        synchronized = suspended = false; queue.clear(); cursor.reset();
        refresh = refresh || action; error = message;
    }
    bool complete(DocumentRequestToken token, DocumentSemanticReply reply) {
        require_quiet();
        if (!stopped && adapter.closed()) stop();
        if (stopped || !outstanding || outstanding->token != token) return false;
        const bool action = outstanding->intent.has_value();
        outstanding.reset(); // Never leave a consumed effect eligible for retry.
        suspended = false;
        if (reply.request_id != token.id || token.generation != generation) {
            failed(action, "Mismatched document completion"); return true;
        }
        if (!reply.error_code.empty()) {
            failed(action, reply.error_code == "stale-view" ? "stale-view" : "Document engine rejected request");
            return true;
        }
        try {
            if (!reply.snapshot || !reply.editor_state || reply.snapshot->version.generation != generation ||
                reply.epoch != reply.snapshot->version.epoch)
                throw std::invalid_argument("Invalid document completion");
            validate_observation(reply);
            // Validate into owned temporary state before replacing the accepted
            // document. The decoded native selection/metadata do not grant edit
            // powers or become an optimistic selection in the GUI adapter.
            AppendedDocument accepted = document;
            accepted.accept(*reply.snapshot);
            const bool retain_cursor = !action && document.snapshot() &&
                document.snapshot()->version.epoch == accepted.snapshot()->version.epoch &&
                document.snapshot()->active_node == accepted.snapshot()->active_node;
            advance_epoch(); document = std::move(accepted);
            observation = std::move(reply);
            if (action) queue.clear();
            else std::erase_if(queue, [&](const Queued& queued) { return queued.version != document.snapshot()->version; });
            if (!retain_cursor) cursor.reset();
            synchronized = true; error.clear(); dirty = true;
        } catch (const std::invalid_argument&) {
            failed(action, "Malformed document completion");
        } catch (...) {
            stop(); throw;
        }
        return true;
    }
};

AppendedDocumentController::AppendedDocumentController(gui::Adapter& adapter, std::uint64_t generation, DocumentViewport viewport)
    : impl_(std::make_unique<Impl>(adapter, generation, viewport)) {}
AppendedDocumentController::~AppendedDocumentController() { shutdown(); }
void AppendedDocumentController::handle(gui::Event event) { impl_->handle(std::move(event)); }
bool AppendedDocumentController::queue_selection(DocumentSelection selection) {
    impl_->require_quiet();
    if (!impl_->usable_input()) return false;
    auto intent = impl_->document.select(*impl_->presented, selection);
    return intent && impl_->enqueue({intent->version, std::move(intent), {}});
}
void AppendedDocumentController::viewport(DocumentViewport viewport) {
    impl_->require_quiet(); validate_viewport(viewport);
    if (impl_->stopped || impl_->viewport == viewport) return;
    if (viewport.columns < 2 || viewport.drawable_rows < 2) impl_->queue.clear();
    impl_->viewport = viewport; impl_->dirty = true;
}
void AppendedDocumentController::request_snapshot() {
    impl_->require_quiet();
    if (!impl_->stopped) { impl_->refresh = true; impl_->suspended = false; }
}
bool AppendedDocumentController::suspend_input() {
    impl_->require_owner();
    if (impl_->handling || impl_->building || impl_->presenting || !impl_->usable_input() || !impl_->queue.empty())
        return false;
    impl_->advance_epoch();
    impl_->synchronized = false;
    impl_->refresh = false;
    impl_->suspended = true;
    return true;
}
bool AppendedDocumentController::resume_input(DocumentVersion version) {
    impl_->require_owner();
    if (impl_->handling || impl_->building || impl_->presenting || impl_->stopped || impl_->adapter.closed() ||
        !impl_->suspended || impl_->synchronized || impl_->refresh || impl_->outstanding ||
        impl_->dirty || impl_->pending || !impl_->queue.empty() || !impl_->presented || !impl_->candidate ||
        impl_->presented->version != version || impl_->candidate->version != version) return false;
    impl_->advance_epoch();
    impl_->suspended = false; impl_->synchronized = true;
    return true;
}
void AppendedDocumentController::tick() { impl_->tick(); }
void AppendedDocumentController::retry_presentation() {
    impl_->require_quiet(); impl_->present();
}
std::optional<DocumentEngineRequest> AppendedDocumentController::next_request() { return impl_->next(); }
bool AppendedDocumentController::complete_request(DocumentRequestToken token, DocumentSemanticReply reply) {
    return impl_->complete(token, std::move(reply));
}
bool AppendedDocumentController::fail_request(DocumentRequestToken token, DocumentRequestFailure failure) {
    impl_->require_quiet();
    if (!impl_->stopped && impl_->adapter.closed()) impl_->stop();
    if (impl_->stopped || !impl_->outstanding || impl_->outstanding->token != token) return false;
    const bool action = impl_->outstanding->intent.has_value(); impl_->outstanding.reset();
    impl_->failed(action, failure == DocumentRequestFailure::known_rejected ? "Document request rejected" : "Document outcome is unknown");
    return true;
}
bool AppendedDocumentController::consume_request_without_publication(DocumentRequestToken token) {
    impl_->require_quiet();
    if (!impl_->stopped && impl_->adapter.closed()) impl_->stop();
    if (impl_->stopped || !impl_->outstanding || impl_->outstanding->token != token ||
        !impl_->outstanding->intent) return false;
    impl_->outstanding.reset();
    impl_->queue.clear(); impl_->cursor.reset();
    impl_->advance_epoch();
    impl_->synchronized = impl_->suspended = false; impl_->refresh = true; impl_->error.clear();
    return true;
}
void AppendedDocumentController::shutdown() noexcept { if (impl_) impl_->stop(); }
const gui::Snapshot& AppendedDocumentController::view() const noexcept { return impl_->view; }
std::uint64_t AppendedDocumentController::input_epoch() const noexcept { return impl_->epoch; }
bool AppendedDocumentController::presentation_pending() const noexcept { return impl_->dirty || impl_->pending; }
bool AppendedDocumentController::synchronized() const noexcept { return impl_->synchronized; }
bool AppendedDocumentController::closed() const noexcept { return impl_->stopped; }
const std::string& AppendedDocumentController::last_error() const noexcept { return impl_->error; }
const DocumentSemanticReply* AppendedDocumentController::observation() const noexcept {
    return impl_->observation ? &*impl_->observation : nullptr;
}
const DocumentProjection* AppendedDocumentController::candidate_projection() const noexcept {
    return impl_->candidate ? &*impl_->candidate : nullptr;
}

} // namespace foundation::ui
