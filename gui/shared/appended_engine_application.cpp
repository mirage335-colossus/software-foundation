#include "appended_engine_application.hpp"
#include "appended_engine_input_codec.hpp"
#include "native_editor_codec.hpp"
#include "engine_document_broker.hpp"

#include <algorithm>
#include <atomic>
#include <deque>
#include <limits>
#include <stdexcept>
#include <thread>
#include <type_traits>

namespace foundation::ui {
namespace {
using Span = std::span<const std::uint8_t>;
constexpr std::uint32_t frame_width = 800, frame_height = 600;
namespace ne = native_editor;
namespace ec = native_editor::codec;

std::uint64_t little(Span bytes, std::size_t offset, std::size_t width) {
    std::uint64_t value = 0;
    for (std::size_t n = 0; n < width; ++n) value |= std::uint64_t(bytes[offset + n]) << (8 * n);
    return value;
}
std::string hex(Span bytes) {
    constexpr char digits[] = "0123456789abcdef";
    std::string result; result.reserve(bytes.size() * 2);
    for (const auto byte : bytes) { result += digits[byte >> 4]; result += digits[byte & 15]; }
    return result;
}
void require(bool condition, const char* message) {
    if (!condition) throw appended::ContainerError(message);
}

gui::BitmapSource copied_frame(const appended::EngineFrame& frame) {
    if (frame.width != frame_width || frame.height != frame_height ||
        frame.stride != frame_width * 4 || frame.rgba.size() != std::size_t{frame.stride} * frame.height ||
        frame.frame_revision == 0)
        throw std::invalid_argument("Invalid fixed-profile engine frame");
    appended::Bytes pixels(std::size_t{frame_width} * frame_height * 3);
    for (std::size_t source = 0, target = 0; source < frame.rgba.size(); source += 4, target += 3) {
        if (frame.rgba[source + 3] != 255) throw std::invalid_argument("Engine frame must be opaque RGBA8");
        std::copy_n(frame.rgba.data() + source, 3, pixels.data() + target);
    }
    gui::BitmapImage image(frame_width, frame_height, gui::PixelFormat::rgb24);
    image.blit(0, 0, {frame_width, frame_height, std::size_t{frame_width} * 3,
                      gui::PixelFormat::rgb24, pixels});
    return gui::image_bitmap(std::move(image));
}
std::string frame_source(const appended::EngineIdentity& id) {
    return "engine-frame-" + std::to_string(id.worker_epoch) + "-" +
        std::to_string(id.application_instance) + "-" + std::to_string(id.document_sequence) + "-" +
        std::to_string(id.service_generation);
}
} // namespace

appended::Package prepare_engine_html_package(Span suffix, std::uint64_t expected_prefix_length,
                                             std::span<const std::uint8_t, 32> expected_prefix_sha256) {
    using namespace appended;
    require(expected_prefix_length != 0 && expected_prefix_length <= max_appended_kernel_bytes,
            "Invalid HTML kernel prefix length");
    require(suffix.size() >= appended_trailer_bytes &&
            suffix.size() <= max_appended_package_bytes + appended_trailer_bytes,
            "Invalid HTML appended suffix length");
    const auto trailer = suffix.last(appended_trailer_bytes);
    constexpr std::array<std::uint8_t, 8> magic{'S', 'F', 'A', 'P', 'N', 'D', '0', '1'};
    require(std::equal(magic.begin(), magic.end(), trailer.begin()), "Invalid HTML appended trailer magic");
    require(little(trailer, 8, 4) == 1 && little(trailer, 12, 4) == appended_trailer_bytes,
            "Unsupported HTML appended trailer version");
    require(little(trailer, 16, 8) == expected_prefix_length, "HTML kernel prefix length mismatch");
    require(little(trailer, 48, 8) == 3, "HTML appended carrier mismatch");
    const auto package_size = little(trailer, 24, 8);
    const auto index_offset = little(trailer, 32, 8), index_size = little(trailer, 40, 8);
    require(package_size <= max_appended_package_bytes && package_size == suffix.size() - appended_trailer_bytes &&
            index_size != 0 && index_size <= max_appended_index_bytes && index_offset <= package_size &&
            index_size == package_size - index_offset, "Invalid HTML appended package bounds");
    require(std::all_of(trailer.begin() + 152, trailer.end(), [](auto value) { return value == 0; }),
            "Nonzero HTML appended trailer reserved bytes");
    require(std::equal(expected_prefix_sha256.begin(), expected_prefix_sha256.end(), trailer.begin() + 56),
            "HTML kernel prefix SHA-256 mismatch");
    auto package = read_package(suffix.first(static_cast<std::size_t>(package_size)), index_offset, index_size);
    require(package.package_sha256 == hex(trailer.subspan(88, 32)), "HTML package SHA-256 mismatch");
    require(package.payload_id == hex(trailer.subspan(120, 32)), "HTML index SHA-256 mismatch");
    package.kernel_sha256 = hex(expected_prefix_sha256);
    return package;
}

struct AppendedEngineApplication::Impl {
    struct PhysicalRequirements {
        std::uint64_t capabilities{};
        std::uint32_t mouse_version{};
    };
    gui::Adapter& adapter;
    std::shared_ptr<appended::EngineOwner> owner;
    std::unique_ptr<EngineSurfacePort> surface;
    const PhysicalRequirements physical;
    const bool document_mode;
    const bool editor_mode = false;
    EngineEditorPort* editor_port = nullptr;
    std::unique_ptr<ne::NativeEditorContextAdapter> editor;
    std::unique_ptr<EngineDocumentBroker> document;
    bool document_closed_cleanly = false;
    std::atomic<bool> editor_publisher_closed{false};
    bool editor_refresh = true, editor_discovery = true, editor_checked = false;
    bool editor_body_keys = false, editor_physical_admitted = false;
    std::optional<ne::EditorPublication> editor_publication;
    std::optional<ne::NativeProjection> editor_projection;
    struct EditorFlight {
        ne::ContextRequest request;
        appended::EngineEditorWork work;
        appended::EngineEditorTicket ticket{};
    };
    std::optional<EditorFlight> editor_flight;
    appended::EngineIdentity editor_target;
    std::deque<std::pair<std::uint64_t, std::uint64_t>> editor_heads;
    std::optional<std::uint64_t> active_editor_head;
    bool editor_head_published = false, editor_idle_deferred = false;
    std::uint64_t next_ingress = 1;
    Impl* retained_next = nullptr;
    static void retain(Impl* value) noexcept {
        value->editor_publisher_closed.store(true, std::memory_order_release);
        value->editor->notify_terminal();
        static std::atomic<Impl*> retained{};
        auto* head = retained.load(std::memory_order_acquire);
        do { value->retained_next = head; }
        while (!retained.compare_exchange_weak(head, value, std::memory_order_release, std::memory_order_acquire));
    }
    gui::Snapshot view;
    std::optional<EngineRegionComposition> region, queued_region;
    std::deque<CompiledRegionEvent> compiled_events;
    std::size_t compiled_event_bytes = 0;
    std::uint64_t region_published = 0;
    bool region_drawn = false;
    appended::EngineIdentity identity;
    const std::thread::id thread = std::this_thread::get_id();
    std::uint64_t frame_revision = 0, input_epoch = 1, next_context = 1, published_revision = 0, last_sequence = 0;
    std::uint64_t bitmap_generation = 0, next_bitmap_generation = 1;
    bool pending = true, stopped = false, presenting = false, stop_requested = false;
    bool connected = false, input_failed = false, service_active = false, effect_suspended = false, retirement_requested = false;
    std::optional<std::uint64_t> effect_ticket;
    appended::EngineIdentity effect_target, rearm_target;
    std::uint64_t safe_effect_revision = 0, rearm_frame_revision = 0;
    bool effect_acknowledged = false, redacted = false, rearm_waiting = false, terminal_requested = false;
    bool service_gate_pending = false, service_gate_value = false;
    std::optional<gui_surface::Capabilities> connection;
    struct Mapping {
        gui_surface::Identity gui;
        appended::EngineIdentity engine;
        std::uint64_t input_context{};
    };
    std::optional<Mapping> context, published;
    struct BodyKey {
        Mapping mapping;
        gui_surface::KeyTransition key;
    };
    struct BodyKeyCommand {
        std::size_t slot{};
        bool release{}, newly_owned{};
        BodyKey value;
    };
    std::array<std::optional<BodyKey>, 64> held_body_keys;
    std::optional<BodyKeyCommand> body_key_command;
    bool body_focus_loss = false, editor_navigation_pending = false;
    bool bound = false, retiring = false;
    appended::engine_input::State input_state;
    enum class CommandKind { bind, retire, input };
    std::optional<appended::EngineInputTicket> ticket;
    CommandKind command_kind = CommandKind::input;
    struct Queued {
        gui_surface::AcceptedEvent accepted;
        Mapping mapping;
        std::size_t charge{};
        std::uint64_t ingress{};
    };
    std::deque<Queued> queue;
    std::size_t queue_bytes = 0;
    static constexpr std::size_t max_events = 64, max_queue_bytes = 1024 * 1024;

    Impl(gui::Adapter& value, std::shared_ptr<appended::EngineOwner> engine,
         std::unique_ptr<EngineSurfacePort> port = {},
         appended::engine_input::EngineSurfaceProfileFacts facts = {},
         std::optional<EngineRegionComposition> initial = {})
        : adapter(value), owner(std::move(engine)), surface(std::move(port)),
          physical{facts.surface_capabilities, facts.mouse_input_version}, document_mode(false), region(std::move(initial)) {
        if (!owner || !owner->configured() || owner->closed())
            throw std::invalid_argument("No configured rich engine owner");
        if (owner->document_profile().enabled || owner->editor_profile().enabled ||
            owner->document_actions_enabled() || owner->document_actions_profile().enabled)
            throw std::invalid_argument("Document engine requires its typed bitmap composition");
        if (facts.enabled && (!surface || !appended::engine_input::input_profile_valid(facts) ||
                                !surface->generation() || !owner->input_enabled()))
            throw std::invalid_argument("Invalid compiled engine input profile or surface port");
        if (surface && !facts.enabled) surface.reset();
        initialize_view();
    }
    Impl(gui::Adapter& value, std::shared_ptr<appended::EngineOwner> engine,
         const appended::engine_editor::EngineEditorProfileFacts& facts, BoundEngineEditorPort port,
         std::optional<EngineRegionComposition> initial = {})
        : adapter(value), owner(std::move(engine)), surface(std::move(port.port)),
          physical{appended::engine_editor::kSurfaceCapabilities, 1}, document_mode(true), editor_mode(true), region(std::move(initial)) {
        if (!owner || !owner->configured() || owner->closed() || !owner->editor_enabled() ||
            owner->document_actions_profile().enabled ||
            !appended::engine_editor::editor_profile_agrees(facts, owner->editor_profile()) ||
            !surface || !surface->generation() || !owner->input_enabled())
            throw std::invalid_argument("Invalid compiled editor profile, owner agreement or bound port");
        initialize_editor();
        document = std::make_unique<EngineDocumentBroker>(owner, facts);
    }
    Impl(gui::Adapter& value, std::shared_ptr<appended::EngineOwner> engine,
         const appended::engine_document_actions::EngineDocumentActionsProfileFacts& facts, BoundEngineEditorPort port,
         std::optional<EngineRegionComposition> initial = {})
        : adapter(value), owner(std::move(engine)), surface(std::move(port.port)),
          physical{appended::engine_document_actions::kSurfaceCapabilities, 1}, document_mode(true), editor_mode(true), region(std::move(initial)) {
        require_actions_profile(facts);
        if (!owner->editor_enabled() || !owner->input_enabled() || !surface || !surface->generation())
            throw std::invalid_argument("Invalid actions editor owner or bound port");
        initialize_editor();
    }
    Impl(gui::Adapter& value, std::shared_ptr<appended::EngineOwner> engine,
         const appended::engine_document_actions::EngineDocumentActionsProfileFacts& facts, ReadOnlyEngineBitmap,
         std::optional<EngineRegionComposition> initial = {})
        : adapter(value), owner(std::move(engine)), physical{}, document_mode(true), region(std::move(initial)) {
        require_actions_profile(facts);
        initialize_view();
        view.title += " (view only)";
    }
    void require_actions_profile(const appended::engine_document_actions::EngineDocumentActionsProfileFacts& facts) const {
        if (!owner || !owner->configured() || owner->closed() || !owner->document_actions_enabled() ||
            owner->document_profile().enabled || owner->editor_profile().enabled ||
            !appended::engine_document_actions::document_actions_profile_valid(facts) ||
            !appended::engine_document_actions::document_actions_profile_agrees(facts, owner->document_actions_profile()))
            throw std::invalid_argument("Invalid compiled actions profile or owner agreement");
        // The independently admitted Owner also requires legacy input facts to
        // be disabled. No old profile is synthesized for this composition.
    }
    void initialize_editor() {
        const auto& caps = surface->capabilities();
        if (gui_surface::validate_capabilities(caps) != gui_surface::Status::ok ||
            !((caps.supported == 0 && caps.mouse_input_version == 0) ||
              (caps.supported == physical.capabilities && caps.mouse_input_version == physical.mouse_version)))
            throw std::invalid_argument("Invalid editor surface port capabilities");
        editor_port = static_cast<EngineEditorPort*>(surface.get());
        initialize_view();
        editor = std::make_unique<ne::NativeEditorContextAdapter>(
            [this](const ne::EditorPublication& publication) { return publish_editor(publication); },
            ne::EditorTerminalHook{owner.get(), [](void* value) noexcept {
                static_cast<appended::EngineOwner*>(value)->notify_document_terminal();
            }});
    }
    bool document_enabled() const noexcept { return editor_mode ? owner->editor_enabled() : owner->document_enabled(); }
    static appended::EngineEditorTarget editor_target_of(const appended::EngineIdentity& value) noexcept {
        return {value.worker_epoch, value.application_instance, value.document_sequence, value.service_generation};
    }
    bool physical_ready() const noexcept {
        return surface && connected && !view.modal_root && !stop_requested && !editor_navigation_pending && !input_failed && !service_active && !effect_suspended && bound && !retiring &&
            !redacted && !rearm_waiting && !retirement_requested && context && owner->input_enabled() &&
            owner->identity() == context->engine && !document_form_gate();
    }
    bool document_form_gate() const noexcept { return document && document->form_gate_required(); }
    using DocumentCandidate = std::shared_ptr<const EngineDocumentBroker::Publication>;
    DocumentCandidate document_candidate() const {
        return document ? document->publication_candidate() : DocumentCandidate{};
    }
    void commit_document(const DocumentCandidate& candidate) {
        // Terminal redaction must still reach the sole presenter, while the
        // unaccepted semantic candidate remains forensic evidence. Terminal
        // Owner admission can never authorize that candidate's publication.
        if (!candidate || document->terminal()) return;
        // Retirement flags can settle before this exact candidate is shown.
        // Classify the immutable empty redaction itself; transient App state
        // cannot authorize publishing an older candidate with native content.
        const auto& state = candidate->state;
        const bool safe = !state.available && !state.observation && !state.document && !state.draft;
        const auto kind = safe ? EngineDocumentBroker::CommitKind::safe_redaction :
                                 EngineDocumentBroker::CommitKind::normal;
        if (!document->publication_committed(candidate, view.revision, kind)) {
            document->notify_terminal();
            throw std::runtime_error("Document candidate lost its accepted paired publication");
        }
    }
    void progress_document() {
        if (!document) return;
        if (document_form_gate() && !retirement_requested && (context || !editor_retired())) request_retirement();
        document->form_admission_ready(!context && !ticket && editor_retired() && !active_editor_head &&
            !service_active && !effect_suspended && !redacted && !editor_navigation_pending && !stop_requested);
        document->tick();
        if (document_candidate()) pending = true;
    }
    void invalidate_editor(bool discovery = false) noexcept {
        if (!editor_mode) return;
        editor_refresh = true;
        editor_discovery = editor_discovery || discovery;
        if (editor_head_published && !retirement_requested && !stop_requested && !editor_navigation_pending &&
            !redacted && !service_active && !effect_suspended) {
            // A completed head's exact checked pair remains available to the
            // metadata Take, including Browser.receive's pre-Take retry tick.
            editor_idle_deferred = true; return;
        }
        editor_checked = false; editor_body_keys = false;
        // Editor discovery does not retire the independent physical context.
        // Keep its focus/capture and owned ingress while body keys are gated.
        pending = true;
    }
    void retire_editor() noexcept {
        if (!editor) return;
        invalidate_editor(true);
        (void)editor->request_retirement();
    }
    bool editor_retired() const noexcept {
        return !editor || (!editor_flight && !editor->retirement_pending() && !editor->terminal() &&
                          (!editor_projection || !editor_projection->retire));
    }
    bool publish_editor(const ne::EditorPublication& value) {
        if (editor_publisher_closed.load(std::memory_order_acquire) || !editor_port || stopped || presenting ||
            owner->callback_depth() || adapter.closed()) return false;
        // Prepare all retained copies before the externally observable commit.
        auto publication = value;
        std::optional<ne::NativeProjection> projection;
        if (const auto* checked = editor->projection()) projection = *checked;
        if (value.basis && (!projection || !context || !same_context(value.basis->identity, context->gui) ||
                            !same_context(projection->identity, value.basis->identity))) return false;
        if ((redacted || service_active || effect_suspended || retirement_requested || editor_navigation_pending) && value.basis) return false;
        // Close has already retired the public physical context. Commit the
        // checked native closure with empty pixels, without reintroducing that
        // context through another paired presentation.
        if (stop_requested && !value.basis && value.retirement) { EngineRegionComposition::clear_content(view); region_drawn = false; }
        if (view.revision <= published_revision) {
            if (view.revision == std::numeric_limits<std::uint64_t>::max() || input_epoch == std::numeric_limits<std::uint64_t>::max())
                throw std::overflow_error("Rich editor presentation generations exhausted");
            ++view.revision; ++input_epoch;
        }
        presenting = true;
        const auto document_publication = document_candidate();
        try {
            gui_surface::CommitResult result;
            if (!has_frame()) {
                if (value.basis || !value.retirement) { presenting = false; return false; }
                result = editor_port->present_editor_retirement(view, value);
                published.reset();
            } else {
                if (!context) { presenting = false; return false; }
                auto pair = editor_pair(value, projection);
                result = editor_port->present_editor_pair(view, pair, value, value.composition);
                if (result.status == gui_surface::Status::ok) {
                    context->gui = pair.identity;
                    if (pair.available) published = *context; else published.reset();
                    editor_physical_admitted = pair.available;
                }
            }
            if (result.status != gui_surface::Status::ok) { presenting = false; return false; }
            commit_document(document_publication);
            editor_publication = std::move(publication); editor_projection = std::move(projection);
            editor_checked = true;
            editor_body_keys = !value.basis && value.retirement && !value.retirement->authority_retired &&
                value.retirement->availability == ne::NativeAvailability::noneditable;
            if (value.retirement && value.retirement->authority_retired) { editor_refresh = true; editor_discovery = true; }
            else if (!editor_discovery) editor_refresh = false;
            published_revision = view.revision; region_committed(); pending = false; presenting = false;
            if (redacted && effect_ticket && !terminal_requested && !stop_requested) {
                const auto effect = owner->native_effect();
                if (effect && effect->ticket == *effect_ticket && effect->target == effect_target && !effect->entered && document_enabled())
                    safe_effect_revision = published_revision;
            }
            if (value.settlement && active_editor_head) editor_head_published = true;
            return true;
        } catch (...) { presenting = false; throw; }
    }
    gui_surface::Presentation editor_pair(const ne::EditorPublication& publication,
                                          const std::optional<ne::NativeProjection>& projection) const {
        gui_surface::Presentation pair;
        pair.identity = context->gui; pair.identity.presentation_revision = view.revision;
        pair.bounds = pair.clip = pane_bounds(); pair.display_scale = 1;
        const bool checked_null = !publication.basis && publication.retirement &&
            !publication.retirement->authority_retired &&
            publication.retirement->availability == ne::NativeAvailability::noneditable;
        // Owned retirement does not imply current physical availability. An
        // unavailable readback cannot retain an older admitted declaration.
        const bool pending_editor = !publication.basis &&
            (!publication.retirement || (publication.retirement->authority_retired &&
                publication.retirement->availability != ne::NativeAvailability::unavailable));
        pair.available = !view.modal_root && physical_ready() && (publication.basis.has_value() || checked_null ||
                                              (pending_editor && editor_physical_admitted));
        pair.keys.fallback = gui_surface::Capture::capture;
        if (publication.basis && projection) {
            const auto& basis = *publication.basis;
            pair.editor = gui_surface::EditorContext{basis.editor_revision, basis.composition, basis.surrounding,
                basis.selection, basis.backward, region ? region->caret_to_root(projection->caret) : projection->caret, projection->editable, projection->input_purpose};
        }
        return pair;
    }
    void settle_editor() {
        if (!editor_flight) return;
        const auto result = owner->editor_outcome(editor_flight->ticket);
        if (!result) return;
        const auto& flight = *editor_flight;
        if (result->ticket != flight.ticket || result->target != flight.work.target ||
            result->request_sequence != flight.work.request_sequence || result->kind != flight.work.kind || !result->transfer) {
            editor->notify_transport_failure(flight.request.ticket); return;
        }
        bool accepted = false;
        if (result->outcome == appended::EngineEditorOutcome::cancelled) {
            if (result->provider_status || result->provider_disposition || result->handled || result->semantic_revision || !result->bytes.empty()) {
                editor->notify_transport_failure(flight.request.ticket); return;
            }
            accepted = editor->cancel_unentered(flight.request.ticket);
        } else if (result->outcome == appended::EngineEditorOutcome::consumed && !result->provider_status) {
            // Prepare the latest actual same-document pixels before the
            // adapter atomically commits this known head/result. No presenter
            // callback or native entry occurs while copying the candidate.
            try {
                if (!redacted && !service_active && !effect_suspended && !stop_requested && !editor_head_published) {
                    if (owner->identity() == identity) collect();
                    else if (has_frame()) {
                        if (view.revision == std::numeric_limits<std::uint64_t>::max() || input_epoch == std::numeric_limits<std::uint64_t>::max())
                            throw std::overflow_error("Rich editor result navigation generations exhausted");
                        editor_navigation_pending = true; redact_view();
                        ++view.revision; ++input_epoch; pending = true;
                    }
                }
            } catch (...) { editor->notify_transport_failure(flight.request.ticket); return; }
            if (flight.request.kind == ne::ContextRequest::Kind::projection) {
                ec::ProjectionReply reply;
                const ec::WireTarget target{flight.work.target.worker_epoch, flight.work.target.application_instance,
                    flight.work.target.document_sequence, flight.work.target.service_generation, flight.work.request_sequence};
                if (!ec::decode_projection_reply(result->bytes, reply) || reply.target != target ||
                    reply.observation_revision != result->semantic_revision) {
                    editor->notify_transport_failure(flight.request.ticket); return;
                }
                std::optional<ne::RetirementReadback> retirement;
                if (!reply.projection) retirement = ne::RetirementReadback{
                    reply.state == ec::ProjectionReply::State::noneditable ? ne::NativeAvailability::noneditable : ne::NativeAvailability::unavailable,
                    reply.identity, reply.observation_revision, reply.readback_attested};
                accepted = editor->supply_projection(flight.request.ticket, std::move(reply.projection), std::move(retirement));
            } else {
                ec::NativeResultEnvelope reply;
                const ec::WireTarget target{flight.work.target.worker_epoch, flight.work.target.application_instance,
                    flight.work.target.document_sequence, flight.work.target.service_generation, flight.work.request_sequence};
                if (!ec::decode_native_result(result->bytes, reply) || reply.target != target || result->semantic_revision) {
                    editor->notify_transport_failure(flight.request.ticket); return;
                }
                accepted = editor->complete(flight.request.ticket, std::move(reply.result));
            }
        } else {
            editor->notify_transport_failure(flight.request.ticket); return;
        }
        // Even a consumed callback can expose a terminal native/publication
        // failure. Retain the Owner's immutable bytes in that case.
        if (!accepted || editor->terminal()) { editor->notify_transport_failure(flight.request.ticket); return; }
        if (!owner->consume_editor_outcome(flight.ticket)) { editor->notify_terminal(); return; }
        editor_flight.reset();
    }
    void stage_editor() {
        if (!editor || editor_flight || ticket || editor->terminal()) return;
        if (editor_head_published && !retirement_requested && !redacted && !service_active &&
            !effect_suspended && !stop_requested && !editor_navigation_pending) return;
        if (editor_refresh && physical_ready() && !service_active && !effect_suspended && !redacted && !retirement_requested) {
            if (editor_discovery ? editor->request_projection() : editor->request_refresh()) {
                editor_refresh = false; editor_discovery = false;
            }
        }
        auto request = editor->prepare([this] {
            if (active_editor_head || !physical_ready() || !editor_checked || editor_heads.empty() ||
                (!queue.empty() && queue.front().ingress < editor_heads.front().second)) return false;
            // The adapter invokes this only for a fresh retained browser head.
            // Once begun, all of its projection/effect/retirement stages remain
            // ahead of later ordinary physical ingress.
            active_editor_head = editor_heads.front().first;
            editor_heads.pop_front(); return true;
        });
        if (!request) return;
        const bool cleanup = request->kind == ne::ContextRequest::Kind::revoke;
        if (!cleanup && (!physical_ready() || service_active || effect_suspended || redacted || retirement_requested)) {
            (void)editor->defer(request->ticket); return;
        }
        try {
            const auto sequence = owner->reserve_editor_sequence();
            if (!sequence) { (void)editor->defer(request->ticket); return; }
            struct Reservation {
                appended::EngineOwner& owner;
                std::uint64_t sequence;
                ~Reservation() { (void)owner.cancel_editor_sequence(sequence); }
            } reservation{*owner, *sequence};
            appended::EngineEditorWork work;
            const auto target = request->kind == ne::ContextRequest::Kind::projection ? context->engine : editor_target;
            work.target = editor_target_of(target); work.request_sequence = *sequence;
            const ec::WireTarget wire{target.worker_epoch, target.application_instance, target.document_sequence,
                target.service_generation, *sequence};
            bool encoded = false;
            if (request->kind == ne::ContextRequest::Kind::projection) {
                work.kind = appended::EngineEditorWorkKind::projection_query; work.operation = BIB_ENGINE_QUERY_EDITOR_PROJECTION_V1;
                encoded = ec::encode_projection_query({wire, context->gui, request->mapping_id}, work.payload);
            } else if (request->kind == ne::ContextRequest::Kind::observation && request->request) {
                work.kind = appended::EngineEditorWorkKind::observation; work.operation = BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1;
                encoded = ec::encode_native_request({wire, *request->request}, work.payload);
            } else if (cleanup && request->retirement) {
                work.kind = appended::EngineEditorWorkKind::revoke; work.operation = BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1;
                encoded = ec::encode_revocation({wire, *request->retirement}, work.payload);
            }
            const appended::engine_editor::OperationFacts* facts = nullptr;
            if (work.kind == appended::EngineEditorWorkKind::projection_query) {
                for (const auto& item : appended::engine_editor::kQueries) if (item.operation == work.operation) facts = &item;
            } else for (const auto& item : appended::engine_editor::kCommands) if (item.operation == work.operation) facts = &item;
            if (!encoded || !facts) {
                (void)owner->cancel_editor_sequence(*sequence); editor->notify_transport_failure(request->ticket); return;
            }
            work.required_reply_capacity = facts->required_reply_capacity; work.schema_sha256 = facts->schema_sha256;
            auto retained = work;
            const auto admission = owner->stage_editor_work(std::move(work));
            if (admission.code == appended::EngineEditorAdmissionCode::admitted) {
                editor_target = target;
                editor_flight = EditorFlight{std::move(*request), std::move(retained), admission.ticket};
            } else {
                (void)owner->cancel_editor_sequence(*sequence);
                if (admission.code == appended::EngineEditorAdmissionCode::busy || admission.code == appended::EngineEditorAdmissionCode::unavailable)
                    (void)editor->defer(request->ticket);
                else editor->notify_transport_failure(request->ticket);
            }
        } catch (...) { editor->notify_transport_failure(request->ticket); }
    }
    Impl(gui::Adapter& value, std::shared_ptr<appended::EngineOwner> engine,
         const appended::engine_document::EngineDocumentProfileFacts& facts,
         std::unique_ptr<EngineSurfacePort> port, std::optional<EngineRegionComposition> initial = {})
        : adapter(value), owner(std::move(engine)), surface(std::move(port)),
          physical{surface ? appended::engine_input::kSurfaceCapabilities : 0,
                   surface ? appended::engine_input::kMouseInputVersion : 0}, document_mode(true), region(std::move(initial)) {
        if (!owner || !owner->configured() || owner->closed() || !owner->document_enabled() ||
            owner->document_actions_profile().enabled ||
            !appended::engine_document::document_profile_agrees(facts, owner->document_profile()))
            throw std::invalid_argument("Invalid compiled document profile or owner agreement");
        if (surface) {
            const auto& caps = surface->capabilities();
            // Browser constructs its App before CONNECT. Only the precise
            // unnegotiated state is allowed until the owned callback arrives.
            const bool unnegotiated = caps.supported == 0 && caps.mouse_input_version == 0;
            const bool negotiated = caps.supported == physical.capabilities && caps.mouse_input_version == physical.mouse_version;
            if (facts.kind != appended::engine_document::ProfileKind::physical || !surface->generation() ||
                !owner->input_enabled() || gui_surface::validate_capabilities(caps) != gui_surface::Status::ok ||
                (!unnegotiated && !negotiated))
                throw std::invalid_argument("Invalid document physical surface port");
        }
        initialize_view();
    }
    void initialize_view() {
        view.title = owner->package().application.name;
        view.client_size = {frame_width, frame_height};
        view.revision = 1;
        identity = owner->identity();
        if (region) { view = region->compose(view, nullptr); region_drawn = true; }
    }
    const gui::Widget* frame_widget() const noexcept {
        for (const auto& widget : view.widgets)
            if (widget.spec.key.id == EngineRegionComposition::engine_id) return &widget;
        return nullptr;
    }
    bool has_frame() const noexcept { return frame_widget() != nullptr; }
    gui_surface::Rect pane_bounds() const noexcept {
        return region ? region->surface_bounds() : gui_surface::Rect{0,0,frame_width,frame_height};
    }
    void region_committed() noexcept {
        if (region && region_drawn) region_published = region->revision();
    }
    void apply_region() {
        if (queued_region && queued_region->compiled().modal_root && !active_editor_head &&
            (context || ticket || !editor_retired())) {
            // Before a compiled modal can become visible, drain the same real
            // editor/input retirement used by trusted service suspension. A
            // later modal removal needs a fresh bind, never the old capture.
            if (!retirement_requested) request_retirement();
            return;
        }
        if (!queued_region || presenting || stop_requested || redacted || effect_suspended ||
            retirement_requested || editor_navigation_pending || active_editor_head ||
            (editor && editor->retirement_pending()) || owner->callback_depth()) return;
        auto next = queued_region->compose(view, frame_widget());
        if (view.revision == std::numeric_limits<std::uint64_t>::max() || input_epoch == std::numeric_limits<std::uint64_t>::max())
            throw std::overflow_error("Compiled region presentation exhausted");
        next.revision = view.revision + 1;
        region = std::move(queued_region); queued_region.reset();
        view = std::move(next); region_drawn = true; ++input_epoch; pending = true;
    }
    void check_thread() const {
        if (std::this_thread::get_id() != thread) throw std::logic_error("Rich application requires its event-loop owner");
    }
    static bool same_context(const gui_surface::Identity& a, const gui_surface::Identity& b) noexcept {
        return a.owner == b.owner && a.generation == b.generation && a.epoch == b.epoch && a.context == b.context;
    }
    static bool same_key(const gui_surface::KeyTransition& a, const gui_surface::KeyTransition& b) noexcept {
        // The physical code remains stable when a modifier changes the logical
        // key between down and its real release. Empty codes use Policy's key
        // fallback; the actual up value/modifiers are forwarded unchanged.
        return a.location == b.location && a.code == b.code && (!a.code.empty() || a.key == b.key);
    }
    static bool same_body_key(const BodyKey& held, const Mapping& mapping,
                              const gui_surface::KeyTransition& key) noexcept {
        return held.mapping.engine == mapping.engine && held.mapping.input_context == mapping.input_context &&
            same_context(held.mapping.gui, mapping.gui) && same_key(held.key, key);
    }
    std::optional<std::size_t> owned_body_key(const Mapping& mapping, const gui_surface::KeyTransition& key) const noexcept {
        for (std::size_t index = 0; index < held_body_keys.size(); ++index)
            if (held_body_keys[index] && same_body_key(*held_body_keys[index], mapping, key)) return index;
        return {};
    }
    bool pending_body_release(const Mapping& mapping, const gui_surface::KeyTransition& key) const noexcept {
        if (key.phase != gui_surface::KeyPhase::up) return false;
        if (body_key_command && !body_key_command->release && same_body_key(body_key_command->value, mapping, key)) return true;
        for (const auto& queued : queue) {
            const auto* down = std::get_if<gui_surface::KeyTransition>(&queued.accepted.event.input);
            if (down && down->phase == gui_surface::KeyPhase::down && same_key(*down, key) &&
                queued.mapping.engine == mapping.engine && queued.mapping.input_context == mapping.input_context &&
                same_context(queued.mapping.gui, mapping.gui)) return true;
        }
        return false;
    }
    void clear_body_keys() noexcept {
        for (auto& key : held_body_keys) key.reset();
    }
    void clear_queue() noexcept { queue.clear(); queue_bytes = 0; }
    void request_retirement(bool failed = false) noexcept {
        input_failed = input_failed || failed;
        retirement_requested = true; pending = true;
        published.reset();
        if (editor_mode) editor_physical_admitted = false;
        clear_queue();
        retire_editor();
    }
    void revoke(gui_surface::Revocation value) noexcept {
        // An identity-only revocation is significant, including mouse-only
        // captures for which Revocation::empty() intentionally returns true.
        if (value.identity && context && same_context(*value.identity, context->gui)) request_retirement();
    }
    void stop() noexcept {
        if (stopped) return;
        if (!stop_requested || !editor_mode) {
            stop_requested = true;
            if (document) {
                try { document->suspend(EngineDocumentBroker::Suspension::closing); }
                catch (...) { document->notify_terminal(); }
            }
            request_retirement();
        }
        if (document && !document->terminal() && document->pending()) return;
        if (editor) {
            // A known receipt is still local metadata after the provider has
            // detached. Its exact checked publication must survive until Take.
            if (!editor->terminal() && !terminal_requested && active_editor_head) return;
            if (!editor->terminal() && document_enabled()) {
                // Normal close is a metadata request. Actual retirement drains
                // only from later ordinary ticks, while the presenter exists.
                if (context || ticket || !editor_retired()) return;
            }
            editor_publisher_closed.store(true, std::memory_order_release);
            editor->close();
        }
        if (document && !document->terminal() && !document->pending()) {
            // Closing the Owner disables its document admission. Remember the
            // already settled local ledger before that normal lifecycle edge;
            // disabled admission after close is not a new unknown outcome.
            document->shutdown(); document_closed_cleanly = true;
        }
        owner->close();
        if (presenting || owner->callback_depth() != 0) return;
        if (!stopped) { stopped = true; pending = false; }
        try { adapter.close(); } catch (...) {}
    }
    bool input_ready() const noexcept {
        return physical_ready() && (!editor_mode || editor_physical_admitted);
    }
    bool stage(std::uint32_t operation, const appended::engine_input::Digest& schema,
               appended::Bytes bytes, CommandKind kind, bool lifecycle) {
        if (!context || ticket) return false;
        auto result = owner->stage_command(context->engine, context->input_context,
                                          operation, schema, std::move(bytes), lifecycle);
        if (!result) return false;
        ticket = *result; command_kind = kind; return true;
    }
    void settle() {
        if (!ticket) return;
        const auto result = owner->command_outcome(*ticket);
        if (!result || result->status == appended::EngineInputCommandStatus::pending) return;
        ticket.reset();
        const bool consumed = result->status == appended::EngineInputCommandStatus::consumed && result->provider_status == 0;
        auto key = std::move(body_key_command); body_key_command.reset();
        const bool focus_loss = body_focus_loss; body_focus_loss = false;
        if (command_kind == CommandKind::bind) {
            bound = consumed;
            if (consumed && context) {
                if (editor_mode) clear_body_keys();
                appended::engine_input::Focus bind{1, 0, 0, 0, context->input_context, 0};
                if (appended::engine_input::accept_focus(input_state, bind) != appended::engine_input::Status::ok)
                    request_retirement(true);
                pending = true;
            } else if (retirement_requested && result->status == appended::EngineInputCommandStatus::cancelled) {
                context.reset(); bound = false; pending = true;
            } else request_retirement(true);
        } else if (command_kind == CommandKind::retire) {
            appended::engine_input::retire_document(input_state);
            bound = false; retiring = false; context.reset(); pending = true;
            if (editor_mode && consumed) clear_body_keys();
            if (!consumed && result->status != appended::EngineInputCommandStatus::cancelled) input_failed = true;
        } else if (!consumed && !(retirement_requested && result->status == appended::EngineInputCommandStatus::cancelled))
            request_retirement(true);
        else if (editor_mode && consumed) {
            if (focus_loss) clear_body_keys();
            if (key) {
                if (key->release) held_body_keys[key->slot].reset();
                else if (key->newly_owned) held_body_keys[key->slot] = std::move(key->value);
            }
            invalidate_editor();
        }
    }
    void redact_view(bool terminal = false) noexcept {
        if (region && !terminal) EngineRegionComposition::redact_content(view);
        else EngineRegionComposition::clear_content(view);
        region_drawn = false;
    }
    void redact_document(bool terminal = false) {
        if (document && !redacted) document->suspend(EngineDocumentBroker::Suspension::service);
        request_retirement();
        if (view.revision == std::numeric_limits<std::uint64_t>::max() || input_epoch == std::numeric_limits<std::uint64_t>::max())
            throw std::overflow_error("Rich redaction generations exhausted");
        ++view.revision; ++input_epoch;
        redact_view(terminal);
        redacted = true; rearm_waiting = false; pending = true;
    }
    void retry_service_gate() {
        if (!surface || !service_gate_pending) return;
        surface->set_owned_service_active(service_gate_value);
        service_gate_pending = false;
    }
    void set_service_gate(bool value) {
        if (!surface) return;
        service_gate_value = value; service_gate_pending = true;
        retry_service_gate();
    }
    void observe_document_effect() {
        const auto effect = owner->native_effect();
        if (effect && (!effect_ticket || *effect_ticket != effect->ticket)) {
            // The owned redacted candidate must exist even if the port setter
            // throws. A separately retained gate intent retries on a later tick.
            redact_document();
            effect_ticket = effect->ticket; effect_target = effect->target;
            safe_effect_revision = 0; effect_acknowledged = false; effect_suspended = true;
            // Revoke immediately, before any successful publication can admit
            // the handler. The callback itself never invokes a native effect.
            set_service_gate(true);
        } else if (!effect && effect_ticket) {
            effect_ticket.reset(); effect_target = {};
            safe_effect_revision = 0; effect_acknowledged = false; effect_suspended = false;
            set_service_gate(service_active);
        }
        retry_service_gate();
        if (!redacted || effect || service_active) return;
        const auto current = owner->identity();
        const auto& frame = owner->frame();
        if (!rearm_waiting) {
            // Sample at the observed completion/UI-release edge, including
            // frames committed while held. Those cannot rearm the page.
            rearm_target = current;
            rearm_frame_revision = frame && frame->identity == current ? frame->frame_revision : 0;
            rearm_waiting = true;
            return;
        }
        if (!frame || frame->identity != current || !current.application_instance || !current.document_sequence ||
            !current.service_generation || (current == rearm_target && frame->frame_revision <= rearm_frame_revision)) return;
        // This is an actual newly committed Owner frame, never a local redraw.
        // The real provider must render/copy one after post-release ADVANCE,
        // even when pixels did not change; that runtime contract is separate.
        redacted = false; rearm_waiting = false; pending = true;
    }
    void observe_editor_navigation() {
        if (!editor) return;
        if (owner->identity() != identity && (context || !editor_retired() || editor_head_published)) {
            if (document && !editor_navigation_pending) document->suspend(EngineDocumentBroker::Suspension::navigation);
            // Historical9 is restricted to the exact previously checked
            // provider material and OLD full transport target. It enters under
            // the Owner's inert admission/full TURN and never touches new DOM.
            editor_navigation_pending = !editor_retired() || editor_head_published;
            request_retirement();
            if (has_frame()) {
                if (view.revision == std::numeric_limits<std::uint64_t>::max() || input_epoch == std::numeric_limits<std::uint64_t>::max())
                    throw std::overflow_error("Rich editor navigation generations exhausted");
                redact_view(); ++view.revision; ++input_epoch; pending = true;
            }
        } else if (editor_navigation_pending && editor_retired()) {
            editor_navigation_pending = false; pending = true;
        }
    }
    void terminal_document() {
        if (document) document->notify_terminal();
        if (!terminal_requested) {
            redact_document(true);
            terminal_requested = true; input_failed = true;
            set_service_gate(true);
        }
        retry_service_gate();
        if (adapter.closed()) { stop(); return; }
        publish();
        if (!pending) stop();
    }
    void lifecycle(bool observe_effect = true) {
        if (document_mode && observe_effect) observe_document_effect();
        if (!surface) return;
        if (!document_mode) {
            const auto effect = owner->native_effect();
            if (effect && (!effect_ticket || *effect_ticket != effect->ticket)) {
                effect_ticket = effect->ticket; effect_suspended = true;
                request_retirement();
                surface->set_owned_service_active(true);
            } else if (!effect && effect_ticket) {
                effect_ticket.reset(); effect_suspended = false;
                surface->set_owned_service_active(service_active); pending = true;
            }
        }
        settle();
        if (connection) {
            const auto offered = *connection; connection.reset();
            if (connected || gui_surface::validate_capabilities(offered) != gui_surface::Status::ok ||
                offered != surface->capabilities() ||
                (offered.supported & physical.capabilities) != physical.capabilities ||
                (document_mode && offered.supported != physical.capabilities) ||
                offered.mouse_input_version != physical.mouse_version) request_retirement(true);
            else { connected = true; pending = true; }
        }
        if (context && context->engine != owner->identity()) request_retirement();
        if (retirement_requested && context) {
            if (editor_mode && !editor_retired()) return;
            if (ticket && command_kind == CommandKind::retire) return;
            owner->cancel_input_context(context->engine, context->input_context);
            settle();
            if (ticket) return; // An entered command retains its exact outcome.
            published.reset();
            if (!bound || context->engine != owner->identity() || !owner->input_enabled()) {
                appended::engine_input::retire_document(input_state);
                if (editor_mode) clear_body_keys();
                bound = false; retiring = false; context.reset(); pending = true;
            } else {
                appended::engine_input::Focus retire{2, 0, 0, 3, 0, context->input_context};
                appended::Bytes bytes;
                if (appended::engine_input::encode_focus(retire, bytes) != appended::engine_input::Status::ok ||
                    !stage(3, appended::engine_input::kFocusSchema, std::move(bytes), CommandKind::retire, true)) return;
                retiring = true; pending = true; return;
            }
        }
        if (retirement_requested && !context && !ticket) retirement_requested = false;
        if (context && !ticket && !bound && !retiring && !retirement_requested && !document_form_gate()) {
            appended::engine_input::Focus bind{1, 0, 0, 0, context->input_context, 0};
            appended::Bytes bytes;
            if (appended::engine_input::encode_focus(bind, bytes) != appended::engine_input::Status::ok)
                request_retirement(true);
            else stage(3, appended::engine_input::kFocusSchema, std::move(bytes), CommandKind::bind, true);
            return;
        }
        if (ticket || context || stop_requested || editor_navigation_pending || document_form_gate() || (editor_mode && editor_head_published) || !connected || input_failed || service_active || effect_suspended || redacted || rearm_waiting || owner->input_suspended() || !owner->input_enabled() ||
            !frame_revision || !has_frame() || view.modal_root ||
            (queued_region && queued_region->compiled().modal_root)) return;
        if (!next_context) { request_retirement(true); return; }
        const auto allocated = next_context;
        next_context = allocated == std::numeric_limits<std::uint64_t>::max() ? 0 : allocated + 1;
        Mapping mapping;
        mapping.engine = identity; mapping.input_context = allocated;
        mapping.gui = {{frame_widget()->spec.key.id, frame_widget()->spec.key.generation},
                       view.revision, surface->generation(), 1, allocated};
        context = std::move(mapping);
        appended::engine_input::Focus bind{1, 0, 0, 0, allocated, 0};
        appended::Bytes bytes;
        if (appended::engine_input::encode_focus(bind, bytes) != appended::engine_input::Status::ok ||
            !stage(3, appended::engine_input::kFocusSchema, std::move(bytes), CommandKind::bind, true)) {
            // A busy owner has not consumed the bind. Retain its context and
            // retry staging metadata on a later normal owner task.
        }
        pending = true;
    }
    void drain() {
        if (ticket || editor_flight || active_editor_head || (editor && editor->retirement_pending()) || !input_ready() || queue.empty()) return;
        if (editor && !editor_heads.empty() && editor_heads.front().second < queue.front().ingress) return;
        auto work = std::move(queue.front()); queue.pop_front(); queue_bytes -= work.charge;
        const auto* release = std::get_if<gui_surface::KeyTransition>(&work.accepted.event.input);
        const bool release_alias = editor_mode && release && release->phase == gui_surface::KeyPhase::up &&
            work.accepted.event.identity.presentation_revision &&
            same_context(work.accepted.event.identity, work.mapping.gui) && owned_body_key(work.mapping, *release);
        if (!context || work.mapping.engine != context->engine || work.mapping.input_context != context->input_context ||
            !same_context(work.mapping.gui, context->gui) ||
            (work.accepted.event.identity != work.mapping.gui && !release_alias) ||
            work.mapping.engine != owner->identity()) { request_retirement(true); return; }
        std::optional<BodyKeyCommand> key_command;
        bool focus_loss = false;
        if (editor_mode) {
            if (const auto* key = std::get_if<gui_surface::KeyTransition>(&work.accepted.event.input)) {
                const auto held = owned_body_key(work.mapping, *key);
                const bool release = key->phase == gui_surface::KeyPhase::up;
                if (release && !held) return;
                if (!release && (!editor_checked || !editor_body_keys)) return;
                if (!release && key->repeat && !held) return;
                std::optional<std::size_t> slot = held;
                if (!slot) {
                    for (std::size_t index = 0; index < held_body_keys.size(); ++index)
                        if (!held_body_keys[index]) { slot = index; break; }
                }
                if (!slot) { request_retirement(true); return; }
                // Retain all fallible strings before the Owner accepts entry.
                key_command = BodyKeyCommand{*slot, release, !held, {work.mapping, *key}};
            } else if (const auto* focus = std::get_if<gui_surface::FocusChange>(&work.accepted.event.input))
                focus_loss = !focus->focused || !focus->active;
        }
        appended::Bytes bytes;
        std::uint32_t operation = 0;
        const appended::engine_input::Digest* schema = nullptr;
        auto next = input_state;
        const auto status = std::visit([&](const auto& input) {
            using T = std::decay_t<decltype(input)>;
            using namespace appended::engine_input;
            if constexpr (std::is_same_v<T, gui_surface::KeyTransition>) {
                Key key{static_cast<std::uint32_t>(input.phase), input.location, input.modifiers,
                        input.repeat ? 1u : 0u, work.mapping.input_context, input.key, input.code};
                auto result = accept_key(next, key); operation = 1; schema = &kKeySchema;
                return result == Status::ok ? encode_key(key, bytes) : result;
            } else if constexpr (std::is_same_v<T, gui_surface::FocusChange>) {
                Focus focus{0, input.focused ? 1u : 0u, input.active ? 1u : 0u,
                            static_cast<std::uint32_t>(input.cause), work.mapping.input_context, work.mapping.input_context};
                auto result = accept_focus(next, focus); operation = 3; schema = &kFocusSchema;
                return result == Status::ok ? encode_focus(focus, bytes) : result;
            } else if constexpr (std::is_same_v<T, gui_surface::MouseTransition>) {
                if (input.version != physical.mouse_version) return Status::unsupported;
                Mouse mouse{static_cast<std::uint32_t>(input.phase), input.button, input.buttons, input.clicks,
                            input.modifiers, static_cast<std::uint32_t>(input.context_origin), work.mapping.input_context,
                            input.capture_token, input.x, input.y, input.wheel_x, input.wheel_y};
                auto result = accept_mouse(next, mouse); operation = 5; schema = &kMouseSchema;
                return result == Status::ok ? encode_mouse(mouse, bytes) : result;
            } else return Status::unsupported;
        }, work.accepted.event.input);
        if (status != appended::engine_input::Status::ok || !schema) {
            request_retirement(true); return;
        }
        if (!stage(operation, *schema, std::move(bytes), CommandKind::input, false)) {
            if (editor_mode) {
                // No entry was accepted. Preserve the exact physical ingress
                // behind a busy Owner rather than inventing a completion.
                const auto charge = work.charge;
                try { queue.push_front(std::move(work)); queue_bytes += charge; }
                catch (...) { request_retirement(true); throw; }
                return;
            }
            request_retirement(true); return;
        }
        if (editor_mode) {
            body_key_command = std::move(key_command); body_focus_loss = focus_loss;
            // Busy metadata has no native entry. Fence editor admission only
            // once this physical attempt is accepted, so an unchanged retained
            // body down cannot invalidate its own eligibility on a retry.
            invalidate_editor();
        }
        input_state = next;
    }
    void publish() {
        if (!terminal_requested && !presenting && owner->callback_depth() == 0 &&
            ((!editor_mode && stop_requested) || owner->closed())) { stop(); return; }
        if (!pending || stopped || presenting || adapter.closed() || owner->callback_depth() != 0) return;
        // Checked editor9 must publish against the still-current Surface
        // context before physical3 retires it. A pre9 legacy publication would
        // irrevocably revoke that context and make the checked pair stale.
        if (editor_mode && (document_form_gate() || view.modal_root ||
            (queued_region && queued_region->compiled().modal_root)) && retirement_requested && !editor_retired() &&
            !redacted && !service_active && !effect_suspended && !terminal_requested && !stop_requested) return;
        if (editor_head_published && !terminal_requested && !editor->retirement_pending()) {
            // Internal Focus retirement/readiness can settle without erasing a
            // head's already committed checked pair. Trusted retirement which
            // still owes checked9 may publish its redacted candidate first.
            if (view.revision > published_revision && editor_publication && !editor_publication->basis &&
                editor_publication->retirement) {
                // Already checked closure can accompany a later safe empty
                // Snapshot without minting another native proof or losing the
                // exact head tag which metadata Take still must join.
                presenting = true;
                try {
                    const auto result = editor_port->present_editor_retirement(view, *editor_publication);
                    if (result.status != gui_surface::Status::ok) {
                        editor->notify_terminal();
                        throw std::runtime_error("Retained editor head retirement publication failed");
                    }
                    published_revision = view.revision; published.reset();
                    if (redacted && effect_ticket && !stop_requested) safe_effect_revision = published_revision;
                    presenting = false;
                } catch (...) { presenting = false; editor->notify_terminal(); throw; }
            }
            pending = bool(document_candidate()); return;
        }
        if (view.revision <= published_revision) {
            if (view.revision == std::numeric_limits<std::uint64_t>::max() || input_epoch == std::numeric_limits<std::uint64_t>::max())
                throw std::overflow_error("Rich presentation generations exhausted");
            ++view.revision; ++input_epoch;
        }
        presenting = true;
        const auto document_publication = document_candidate();
        try {
            if (surface && connected && context && has_frame() && !input_failed && !redacted && !terminal_requested && !retirement_requested && !retiring) {
                gui_surface::Presentation pair;
                pair.identity = context->gui; pair.identity.presentation_revision = view.revision;
                pair.bounds = pair.clip = pane_bounds();
                pair.display_scale = 1; pair.available = input_ready() && !view.modal_root;
                pair.keys.fallback = gui_surface::Capture::capture;
                gui_surface::CommitResult result;
                if (editor_mode) {
                    if (editor_checked && editor_publication) pair = editor_pair(*editor_publication, editor_projection);
                    else pair.available = !view.modal_root && physical_ready() && editor_physical_admitted;
                    result = editor_port->present_editor_pair(view, pair,
                        editor_checked ? editor_publication : std::nullopt,
                        editor_checked && editor_publication ? editor_publication->composition : std::nullopt);
                } else result = surface->present_pair(view, pair);
                if (result.status != gui_surface::Status::ok) {
                    request_retirement(true);
                    throw std::runtime_error("Rich surface paired publication failed");
                }
                if (pair.available) { context->gui = pair.identity; published = *context; }
                else published.reset();
                // Unavailable bind staging is expected. It revokes the previous
                // GUI declaration, never the provider context being bound.
                if (pair.available) revoke(std::move(result.revoked));
            } else { adapter.present(view); published.reset(); }
            commit_document(document_publication);
            published_revision = view.revision; region_committed();
            pending = false; presenting = false;
            if (document_mode && redacted && !terminal_requested && !stop_requested && effect_ticket) {
                const auto effect = owner->native_effect();
                if (effect && effect->ticket == *effect_ticket && effect->target == effect_target &&
                    !effect->entered && document_enabled()) safe_effect_revision = published_revision;
            }
        } catch (...) {
            presenting = false;
            // A redacted publication cannot restore input authority. Retain
            // its candidate for retry without poisoning a fresh later bind.
            // Failure of an available pair still closes the physical route.
            if (surface) request_retirement(!(document_mode && redacted));
            if (stop_requested) stop();
            throw;
        }
        if (stop_requested) stop();
    }
    void collect() {
        if (stopped || presenting || owner->callback_depth() != 0) return;
        if (stop_requested || owner->closed()) { stop(); return; }
        if (editor_head_published) {
            const auto& latest = owner->frame();
            if (owner->identity() != identity || (latest && (latest->identity != identity || latest->frame_revision != frame_revision)))
                editor_idle_deferred = true;
            return;
        }
        if (document_mode && redacted) return;
        const auto current = owner->identity();
        const auto& frame = owner->frame();
        if (editor_navigation_pending) return;
        if (!frame && current == identity) return;
        if (frame && current == identity && frame->identity == current && frame->frame_revision == frame_revision) return;
        if (frame && (frame->identity != current || !current.worker_epoch || !current.application_instance ||
                      !current.document_sequence || !current.service_generation))
            throw std::invalid_argument("Engine frame identity is stale or incomplete");
        if (view.revision == std::numeric_limits<std::uint64_t>::max() || input_epoch == std::numeric_limits<std::uint64_t>::max())
            throw std::overflow_error("Rich presentation generations exhausted");
        if (context && current != identity) request_retirement();
        auto next = view; next.widgets.clear();
        if (frame) {
            if (document_mode && (current != identity || !has_frame())) {
                // Redaction ends the retained widget's lifetime. Its next GUI
                // generation is independent of the unchanged native document.
                if (!next_bitmap_generation) throw std::overflow_error("Rich bitmap generations exhausted");
                bitmap_generation = next_bitmap_generation;
                next_bitmap_generation = bitmap_generation == std::numeric_limits<std::uint64_t>::max() ? 0 : bitmap_generation + 1;
            }
            gui::Widget widget;
            widget.spec.key = {"engine.frame", document_mode ? bitmap_generation : current.service_generation};
            widget.spec.kind = gui::Kind::bitmap;
            widget.spec.pointer_input = false; widget.spec.context_input = false;
            widget.state.bounds = {0, 0, frame_width, frame_height};
            widget.state.accessible_name = view.title;
            widget.state.bitmap = {frame_source(current), frame->frame_revision, copied_frame(*frame)};
            next.widgets.push_back(std::move(widget));
        }
        if (region) {
            const auto* bitmap = next.widgets.empty() ? nullptr : &next.widgets.front();
            next = region->compose(next, bitmap); region_drawn = true;
        }
        ++next.revision; gui::validate_snapshot(next);
        identity = current; frame_revision = frame ? frame->frame_revision : 0;
        if (editor_mode) invalidate_editor();
        ++input_epoch; view = std::move(next); pending = true;
    }
    void tick() {
        if (presenting || owner->callback_depth() != 0 || stopped) return;
        apply_region();
        if (document_mode) {
            if (editor_mode && stop_requested && owner->closed()) {
                // Owner closure is known native completion, not an implicit
                // frontend Take. This branch may only drain local metadata.
                if (terminal_requested || input_failed || editor->terminal() || editor_flight || ticket || !editor_retired()) {
                    terminal_document(); return;
                }
                if (active_editor_head) {
                    if (!editor_head_published || !editor_publication || !editor_publication->settlement ||
                        editor_publication->basis || !editor_publication->retirement ||
                        !editor_publication->retirement->readback_attested) terminal_document();
                    return;
                }
                if (editor->pending()) return; // Abandoned metadata remains an honest close barrier.
                appended::engine_input::retire_document(input_state);
                clear_body_keys(); clear_queue(); published.reset(); context.reset();
                bound = false; retiring = false; retirement_requested = false;
                stop(); return;
            }
            if (!document_enabled() || (editor && editor->terminal()) || (document && document->terminal())) { terminal_document(); return; }
            if (adapter.closed()) {
                // The sole presenter is gone. Discard local page pixels and
                // request only metadata closure; this is no publication proof.
                EngineRegionComposition::clear_content(view); region_drawn = false;
                if (editor) editor->notify_terminal();
                stop(); return;
            }
            // Observe native suspension before copying any page pixels. This
            // also runs for the1795/no-port bitmap observation composition.
            if (editor_mode) settle_editor();
            if (editor && editor->terminal()) { terminal_document(); return; }
            // This observation must precede redaction/close collection skips.
            // An admitted Native8 completion first gets to supply real retired
            // proof; no new independent native attempt occurs here.
            if (editor_mode) observe_editor_navigation();
            observe_document_effect();
            progress_document();
            if (!stop_requested) collect();
            if (editor && editor->terminal()) { terminal_document(); return; }
            if (!stopped) lifecycle(false);
        } else {
            collect();
            if (!stopped) lifecycle();
        }
        if (stopped) return;
        if (editor_mode) stage_editor();
        if (editor && editor->terminal()) { terminal_document(); return; }
        progress_document();
        if (document && document->terminal()) { terminal_document(); return; }
        drain(); publish();
        // A successful unavailable/legacy publication precedes trusted native
        // handler readiness. This metadata acknowledgment never calls a handler.
        if (effect_ticket && !pending && !context && !ticket && editor_retired() &&
            (!document || document->native_effect_quiescent())) {
            if (document_mode) {
                if (!effect_acknowledged && redacted && safe_effect_revision && !service_gate_pending && !terminal_requested &&
                    owner->acknowledge_document_native_effect(*effect_ticket,
                        {effect_target.worker_epoch,effect_target.application_instance,
                         effect_target.document_sequence,effect_target.service_generation}, safe_effect_revision))
                    effect_acknowledged = true;
            } else (void)owner->acknowledge_native_effect(*effect_ticket);
        }
        if (editor_mode && stop_requested && !context && !ticket && editor_retired()) stop();
    }
    void input(gui_surface::AcceptedEvent value) {
        if (!published || input_failed || retirement_requested || stopped) return;
        const auto* release = std::get_if<gui_surface::KeyTransition>(&value.event.input);
        const bool release_alias = editor_mode && release && release->phase == gui_surface::KeyPhase::up &&
            value.event.identity.presentation_revision && same_context(value.event.identity, published->gui) &&
            (owned_body_key(*published, *release) || pending_body_release(*published, *release));
        // The trusted Surface preserves a real release's original identity.
        // Only its presentation revision may alias the current physical pair;
        // dispatch still requires our consumed DOWN's full native ownership.
        if ((value.event.identity != published->gui && !release_alias) ||
            !value.event.sequence || value.event.sequence <= last_sequence) return;
        last_sequence = value.event.sequence;
        if (value.revoked.identity && same_context(*value.revoked.identity, published->gui)) {
            request_retirement(); return;
        }
        if (value.revoked.composition || value.revoked.popup || !value.revoked.held_keys.empty()) {
            request_retirement(true); return;
        }
        // Revocation was handled above. An unrelated old identity supplies no
        // authority and must not retain uncharged optional string allocations.
        value.revoked = {};
        if (region && !region->input_to_engine(value)) { request_retirement(true); return; }
        std::size_t charge = sizeof(Queued);
        const auto add_charge = [&](std::size_t bytes) {
            if (bytes > max_queue_bytes - charge) return false;
            charge += bytes; return true;
        };
        if (!add_charge(value.event.identity.owner.id.capacity()) || !add_charge(published->gui.owner.id.capacity()) ||
            value.revoked.held_keys.capacity() > (max_queue_bytes - charge) / sizeof(gui_surface::KeyTransition) ||
            !add_charge(value.revoked.held_keys.capacity() * sizeof(gui_surface::KeyTransition))) {
            request_retirement(true); return;
        }
        if (const auto* key = std::get_if<gui_surface::KeyTransition>(&value.event.input)) {
            if (editor_mode && (!editor_checked || !editor_body_keys) &&
                !(key->phase == gui_surface::KeyPhase::up &&
                  (owned_body_key(*published, *key) || pending_body_release(*published, *key)))) return;
            if (key->key.size() > 64 || key->code.size() > 64) { request_retirement(true); return; }
            if (!add_charge(key->key.capacity()) || !add_charge(key->code.capacity())) {
                request_retirement(true); return;
            }
        } else if (!std::holds_alternative<gui_surface::FocusChange>(value.event.input) &&
                   !std::holds_alternative<gui_surface::MouseTransition>(value.event.input)) { request_retirement(true); return; }
        if (queue.size() >= max_events || charge > max_queue_bytes - queue_bytes) { request_retirement(true); return; }
        if (editor_mode && !next_ingress) { editor->notify_terminal(); return; }
        const auto ingress = editor_mode ? next_ingress : 0;
        if (editor_mode) next_ingress = ingress == std::numeric_limits<std::uint64_t>::max() ? 0 : ingress + 1;
        try { queue.push_back({std::move(value), *published, charge, ingress}); queue_bytes += charge; }
        catch (...) { request_retirement(true); throw; }
    }
    std::optional<std::uint64_t> remember_editor_head(std::optional<std::uint64_t> ticket) {
        if (!ticket) return {};
        if (!next_ingress || editor_heads.size() >= max_events) { editor->notify_terminal(); return {}; }
        const auto ingress = next_ingress;
        next_ingress = ingress == std::numeric_limits<std::uint64_t>::max() ? 0 : ingress + 1;
        try { editor_heads.emplace_back(*ticket, ingress); }
        catch (...) { editor->notify_terminal(); throw; }
        return ticket;
    }
};

AppendedEngineApplication::AppendedEngineApplication(gui::Adapter& adapter,
        std::shared_ptr<appended::EngineOwner> owner, std::optional<EngineRegionComposition> region)
    : impl_(std::make_unique<Impl>(adapter, std::move(owner), nullptr, appended::engine_input::EngineSurfaceProfileFacts{}, std::move(region))) {
    impl_->collect(); impl_->publish();
}
AppendedEngineApplication::AppendedEngineApplication(gui::Adapter& adapter,
        std::shared_ptr<appended::EngineOwner> owner,
        const appended::engine_document::EngineDocumentProfileFacts& facts,
        std::unique_ptr<EngineSurfacePort> port, std::optional<EngineRegionComposition> region)
    : impl_(std::make_unique<Impl>(adapter, std::move(owner), facts, std::move(port), std::move(region))) {
    impl_->tick();
}
AppendedEngineApplication::AppendedEngineApplication(gui::Adapter& adapter,
        std::shared_ptr<appended::EngineOwner> owner, std::unique_ptr<EngineSurfacePort> port,
        const appended::engine_input::EngineSurfaceProfileFacts& facts, std::optional<EngineRegionComposition> region)
    : impl_(std::make_unique<Impl>(adapter, std::move(owner), std::move(port), facts, std::move(region))) {
    impl_->collect(); impl_->publish();
}
AppendedEngineApplication::AppendedEngineApplication(gui::Adapter& adapter,
        std::shared_ptr<appended::EngineOwner> owner,
        const appended::engine_editor::EngineEditorProfileFacts& facts, BoundEngineEditorPort port,
         std::optional<EngineRegionComposition> region)
    : impl_(std::make_unique<Impl>(adapter, std::move(owner), facts, std::move(port), std::move(region))) {
    try { impl_->tick(); }
    catch (...) { Impl::retain(impl_.release()); throw; }
}
AppendedEngineApplication::AppendedEngineApplication(gui::Adapter& adapter,
        std::shared_ptr<appended::EngineOwner> owner,
        const appended::engine_document_actions::EngineDocumentActionsProfileFacts& facts, BoundEngineEditorPort port,
         std::optional<EngineRegionComposition> region)
    : impl_(std::make_unique<Impl>(adapter, std::move(owner), facts, std::move(port), std::move(region))) {
    try { impl_->tick(); }
    catch (...) { Impl::retain(impl_.release()); throw; }
}
AppendedEngineApplication::AppendedEngineApplication(gui::Adapter& adapter,
        std::shared_ptr<appended::EngineOwner> owner,
        const appended::engine_document_actions::EngineDocumentActionsProfileFacts& facts, ReadOnlyEngineBitmap tag,
        std::optional<EngineRegionComposition> region)
    : impl_(std::make_unique<Impl>(adapter, std::move(owner), facts, tag, std::move(region))) {
    impl_->tick();
}
AppendedEngineApplication::~AppendedEngineApplication() {
    shutdown();
    if (impl_ && impl_->editor && (!impl_->stopped || impl_->editor->terminal() || impl_->editor_flight ||
                                impl_->editor->pending() || (impl_->editor_projection && impl_->editor_projection->retire) ||
                                (impl_->document && (impl_->document->pending() ||
                                    (!impl_->document_closed_cleanly && impl_->document->terminal()))))) {
        // A callback captures this exact Impl and its stable Owner. Keep their
        // complete lifetime together; no allocation or process-exit cleanup is
        // registered, and the closed publisher cannot touch a dead GUI adapter.
        Impl::retain(impl_.release());
    }
}
const gui::Snapshot& AppendedEngineApplication::view() const noexcept { return impl_->view; }
void AppendedEngineApplication::handle(gui::Event event) {
    impl_->check_thread();
    if (std::holds_alternative<gui::CloseEvent>(event)) { impl_->stop(); return; }
    if (!impl_->region || !impl_->region_drawn || impl_->stop_requested || impl_->stopped || impl_->presenting ||
        impl_->service_active || impl_->effect_suspended || impl_->redacted || impl_->terminal_requested ||
        impl_->owner->callback_depth() || impl_->pending || impl_->adapter.closed() ||
        impl_->region_published != impl_->region->revision()) return;
    auto raw_event=event;
    if (!impl_->region->owns_event(event, impl_->view,
        [&](const gui::WidgetKey& key) { return impl_->adapter.scroll_offset(key); })) return;
    if (const auto* widget = std::get_if<gui::WidgetEvent>(&event)) {
        if (gui::find_command(impl_->view,widget->target)) {
            const auto* activation = std::get_if<gui::Activate>(&widget->input);
            if (!activation || !activation->source || impl_->adapter.focused() != activation->source) return;
        }
    }
    CompiledRegionEvent owned;
    owned.revision=impl_->region->revision(); owned.event=std::move(event); owned.raw_event=std::move(raw_event);
    owned.focused=impl_->adapter.focused();
    std::size_t charge=compiled_region_event_charge(owned.event);
    if(charge>Impl::max_queue_bytes-sizeof(CompiledRegionEvent)) return;
    charge+=sizeof(CompiledRegionEvent);
    const auto add=[&](std::size_t amount) {
        if (amount > Impl::max_queue_bytes-charge) return false;
        charge+=amount; return true;
    };
    if (!add(compiled_region_event_charge(owned.raw_event)) ||
        (owned.focused && !add(owned.focused->id.capacity()))) return;
    // Capture the exact native presentation facts now; binary guest work later
    // must never retarget an old intent using newer focus or scroll positions.
    for (const auto& widget:impl_->region->compiled().widgets) if(widget.spec.kind==gui::Kind::group && impl_->region->captures_scroll(widget.spec.key))
        owned.scroll_offsets.emplace_back(widget.spec.key,impl_->adapter.scroll_offset(widget.spec.key));
    if (owned.scroll_offsets.capacity() > Impl::max_queue_bytes/sizeof(decltype(owned.scroll_offsets)::value_type) ||
        !add(owned.scroll_offsets.capacity()*sizeof(decltype(owned.scroll_offsets)::value_type))) return;
    for(const auto& offset:owned.scroll_offsets) if(!add(offset.first.id.capacity())) return;
    if (impl_->compiled_events.size()==Impl::max_events || charge>Impl::max_queue_bytes-impl_->compiled_event_bytes) return;
    owned.retained_bytes=charge;
    impl_->compiled_events.push_back(std::move(owned)); impl_->compiled_event_bytes+=charge;
}
bool AppendedEngineApplication::queue_compiled_region(EngineRegionComposition value) {
    impl_->check_thread();
    if (!impl_->region || impl_->stop_requested || impl_->stopped || impl_->presenting ||
        !impl_->region->same_layout(value) || value.revision() <= impl_->region->revision() ||
        (impl_->queued_region && value.revision() <= impl_->queued_region->revision())) return false;
    impl_->queued_region = std::move(value); return true;
}
std::optional<CompiledRegionEvent> AppendedEngineApplication::take_compiled_event() {
    impl_->check_thread();
    if (impl_->stop_requested || impl_->stopped || impl_->presenting || impl_->service_active || impl_->effect_suspended ||
        impl_->redacted || impl_->terminal_requested || impl_->owner->callback_depth() || impl_->compiled_events.empty()) return {};
    auto result = std::move(impl_->compiled_events.front()); impl_->compiled_events.pop_front();
    impl_->compiled_event_bytes -= compiled_region_event_charge(result); return result;
}
std::uint64_t AppendedEngineApplication::compiled_region_published_revision() const noexcept { return impl_->region_published; }

void AppendedEngineApplication::tick() { impl_->check_thread(); impl_->tick(); }
void AppendedEngineApplication::shutdown() noexcept { if (impl_) impl_->stop(); }
void AppendedEngineApplication::retry_presentation() {
    impl_->check_thread();
    if (impl_->document_mode) impl_->tick();
    else impl_->publish();
}
std::optional<gui::ServiceRequest> AppendedEngineApplication::next_service() { return std::nullopt; }
bool AppendedEngineApplication::complete_service(gui::ServiceResult) { return false; }
void AppendedEngineApplication::qualify(const std::function<void()>& present) {
    impl_->check_thread(); retry_presentation(); if (present) present();
}
bool AppendedEngineApplication::presentation_pending() const noexcept { return impl_->pending; }
bool AppendedEngineApplication::shutdown_complete() const noexcept {
    return impl_->stopped && !impl_->terminal_requested && !impl_->input_failed && !impl_->ticket &&
        !impl_->editor_flight && !impl_->active_editor_head &&
        (!impl_->editor || (!impl_->editor->terminal() && !impl_->editor->pending())) &&
        (!impl_->document || (impl_->document_closed_cleanly && !impl_->document->pending()));
}
std::uint64_t AppendedEngineApplication::input_epoch() const noexcept { return impl_->input_epoch; }

void AppendedEngineApplication::surface_connected(gui_surface::Capabilities value) {
    impl_->check_thread();
    if (!impl_->surface || impl_->stopped || impl_->connection || impl_->connected) return;
    impl_->connection = std::move(value);
}
void AppendedEngineApplication::surface_input(gui_surface::AcceptedEvent value) {
    impl_->check_thread(); impl_->input(std::move(value));
}
void AppendedEngineApplication::surface_revoked(gui_surface::Revocation value) {
    impl_->check_thread(); impl_->revoke(std::move(value));
}
void AppendedEngineApplication::set_owned_service_active(bool active) {
    impl_->check_thread();
    if (!impl_->document_mode) {
        if (impl_->service_active == active) return;
        if (!impl_->surface) { impl_->service_active=active; return; }
        if (impl_->presenting || impl_->owner->callback_depth())
            throw std::logic_error("Native service suspension requires a normal owner task");
        impl_->service_active = active;
        if (active) impl_->request_retirement();
        impl_->surface->set_owned_service_active(active || impl_->effect_suspended);
        impl_->pending = true; impl_->lifecycle(); return;
    }
    if (impl_->stopped || impl_->stop_requested) return;
    if (impl_->presenting || impl_->owner->callback_depth())
        throw std::logic_error("Native service suspension requires a normal owner task");
    if (!impl_->document_enabled()) { impl_->terminal_document(); return; }
    if (impl_->service_active == active) {
        if (impl_->service_gate_pending) impl_->lifecycle();
        return;
    }
    if (active) {
        impl_->redact_document();
    }
    impl_->service_active = active;
    impl_->set_service_gate(active || impl_->effect_suspended);
    impl_->pending = true;
    impl_->lifecycle();
}

bool AppendedEngineApplication::owned_service_ready() const noexcept {
    return std::this_thread::get_id()==impl_->thread && impl_->service_active && !impl_->effect_suspended &&
        !impl_->owner->native_effect() && !impl_->stop_requested &&
        !impl_->stopped && !impl_->presenting && !impl_->owner->callback_depth() && !impl_->pending &&
        !impl_->context && !impl_->ticket && !impl_->editor_flight && !impl_->active_editor_head && impl_->editor_retired() &&
        (!impl_->document || impl_->document->native_effect_quiescent());
}

std::optional<std::uint64_t> AppendedEngineApplication::editor_submit(ne::Packet value) {
    if (!impl_->editor || impl_->editor_publisher_closed.load(std::memory_order_acquire)) return {};
    if (std::this_thread::get_id() != impl_->thread) { impl_->editor->notify_terminal(); return {}; }
    if (impl_->stop_requested) return {};
    if (impl_->document_form_gate()) return {};
    const auto ticket = impl_->editor->submit(std::move(value));
    return impl_->remember_editor_head(ticket);
}
std::optional<std::uint64_t> AppendedEngineApplication::editor_revoke(ne::Revocation value) {
    if (!impl_->editor || impl_->editor_publisher_closed.load(std::memory_order_acquire)) return {};
    if (std::this_thread::get_id() != impl_->thread) { impl_->editor->notify_terminal(); return {}; }
    if (impl_->stop_requested) return {};
    if (impl_->document_form_gate()) return {};
    const auto ticket = impl_->editor->queue_revoke(std::move(value));
    return impl_->remember_editor_head(ticket);
}
std::optional<ne::EditorCompletion> AppendedEngineApplication::editor_take(std::uint64_t ticket) {
    if (!impl_->editor || impl_->editor_publisher_closed.load(std::memory_order_acquire)) return {};
    if (std::this_thread::get_id() != impl_->thread) { impl_->editor->notify_terminal(); return {}; }
    if (impl_->presenting) return {};
    // Session already guards the browser callback. Entering the ContextAdapter
    // callback guard here would prevent its metadata-only completion take.
    auto result = impl_->editor->take_completion(ticket);
    if (result && impl_->active_editor_head == ticket) {
        impl_->active_editor_head.reset(); impl_->editor_head_published = false;
        if (impl_->editor_idle_deferred) {
            impl_->editor_idle_deferred = false;
            impl_->invalidate_editor(impl_->editor_discovery);
        }
    }
    return result;
}
void AppendedEngineApplication::editor_resync() {
    if (!impl_->editor || impl_->editor_publisher_closed.load(std::memory_order_acquire)) return;
    if (std::this_thread::get_id() != impl_->thread) { impl_->editor->notify_terminal(); return; }
    if (impl_->stop_requested) return;
    impl_->invalidate_editor(true);
}

gui_document::Submission AppendedEngineApplication::document_submit(gui_document::Intent value) {
    if (!impl_->document) return {gui_document::Admission::unavailable,{}};
    if (std::this_thread::get_id() != impl_->thread) {
        impl_->document->notify_terminal(); return {gui_document::Admission::closed,{}};
    }
    if (impl_->stopped || impl_->stop_requested || impl_->terminal_requested)
        return {gui_document::Admission::closed,{}};
    if (impl_->presenting || impl_->service_active || impl_->effect_suspended || impl_->redacted ||
        impl_->rearm_waiting || impl_->editor_navigation_pending)
        return {gui_document::Admission::unavailable,{}};
    return impl_->document->submit(std::move(value));
}
std::optional<gui_document::Completion> AppendedEngineApplication::document_take(gui_document::Ticket value) {
    if (!impl_->document || impl_->presenting) return {};
    if (std::this_thread::get_id() != impl_->thread) { impl_->document->notify_terminal(); return {}; }
    return impl_->document->take(value);
}
gui_document::State AppendedEngineApplication::document_state() const {
    if (!impl_->document) return {};
    impl_->check_thread();
    auto value = impl_->document->state();
    if (impl_->stopped || impl_->stop_requested || impl_->service_active || impl_->effect_suspended ||
        impl_->redacted || impl_->rearm_waiting || impl_->editor_navigation_pending) value.available = false;
    return value;
}
gui_document::TerminalHook AppendedEngineApplication::document_terminal() noexcept {
    return {impl_->owner.get(), [](void* value) noexcept {
        static_cast<appended::EngineOwner*>(value)->notify_document_terminal();
    }};
}

} // namespace foundation::ui
