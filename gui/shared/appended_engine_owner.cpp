#include "appended_engine_owner.hpp"
#include "appended_engine_abi.h"
#include "appended_engine_input_codec.hpp"
#include "engine_document_mailbox.hpp"
#include "native_editor_codec.hpp"
#include <foundation/appended/resource_url.hpp>

#include <algorithm>
#include <array>
#include <atomic>
#include <limits>
#include <map>
#include <mutex>
#include <new>
#include <stdexcept>
#include <string_view>
#include <thread>
#include <utility>

namespace foundation::appended {
namespace {
namespace editor_codec = foundation::ui::native_editor::codec;
namespace native_editor = foundation::ui::native_editor;
using Span = std::span<const std::uint8_t>;
constexpr std::size_t header_bytes = FOUNDATION_ENGINE_HEADER_BYTES;
constexpr std::size_t receipt_bytes = FOUNDATION_ENGINE_RECEIPT_BYTES;
constexpr std::size_t max_frame_bytes = 16 * 1024 * 1024;
constexpr std::uint64_t max_resource_bytes = 128ULL * 1024 * 1024;
constexpr std::string_view startup_path = "web/.foundation/startup-v1.json";
constexpr std::string_view composition_startup_path = "web/.foundation/startup-v2.json";
constexpr std::string_view startup_value =
    "{\"kind\":\"foundation-appended-startup\",\"primary\":\"web\",\"schema_version\":1}";

std::uint64_t get(Span bytes, std::size_t offset, unsigned count) noexcept {
    std::uint64_t value{};
    for (unsigned i = 0; i < count; ++i) value |= std::uint64_t(bytes[offset + i]) << (8 * i);
    return value;
}
void put(std::span<std::uint8_t> bytes, std::size_t offset, std::uint64_t value, unsigned count) noexcept {
    for (unsigned i = 0; i < count; ++i) bytes[offset + i] = static_cast<std::uint8_t>(value >> (8 * i));
}
struct Header {
    EngineIdentity identity;
    std::uint64_t transfer{};
    std::uint32_t source{};
};
bool decode(std::uint32_t op, Span bytes, Header& header, Span& payload) noexcept {
    if (bytes.size() < header_bytes || bytes[0] != 'F' || bytes[1] != 'K' ||
        bytes[2] != 'B' || bytes[3] != '1' || get(bytes, 4, 2) != 1 ||
        get(bytes, 6, 2) != op || get(bytes, 8, 4) != bytes.size() || get(bytes, 12, 4) ||
        get(bytes, 60, 4) || get(bytes, 64, 4) != bytes.size() - header_bytes || get(bytes, 68, 4)) return false;
    header = {{get(bytes, 16, 8), get(bytes, 24, 8), get(bytes, 32, 8), get(bytes, 40, 8)},
        get(bytes, 48, 8), static_cast<std::uint32_t>(get(bytes, 56, 4))};
    payload = bytes.subspan(header_bytes);
    return header.source <= 2 && (op == FOUNDATION_ENGINE_SUBMIT || header.source == 0);
}
std::int32_t reply(std::uint32_t op, const Header& header, std::span<std::uint8_t> output,
                   std::uint32_t control, ServiceStatus service, Span payload = {}) noexcept {
    const auto total = receipt_bytes + payload.size();
    if (output.size() < total) return FOUNDATION_ENGINE_REPLY_TOO_SMALL;
    std::fill_n(output.begin(), receipt_bytes, std::uint8_t{});
    output[0] = 'F'; output[1] = 'K'; output[2] = 'B'; output[3] = '1';
    put(output, 4, 1, 2); put(output, 6, op | FOUNDATION_ENGINE_REPLY_KIND, 2);
    put(output, 8, total, 4); put(output, 16, header.identity.worker_epoch, 8);
    put(output, 24, header.identity.application_instance, 8);
    put(output, 32, header.identity.document_sequence, 8);
    put(output, 40, header.identity.service_generation, 8);
    put(output, 48, header.transfer, 8); put(output, 56, header.source, 4);
    put(output, 64, total - header_bytes, 4); put(output, 72, control, 4);
    put(output, 76, static_cast<std::uint32_t>(service), 4);
    std::copy(payload.begin(), payload.end(), output.begin() + receipt_bytes);
    return static_cast<std::int32_t>(total);
}
bool contains(const std::vector<std::string>& values, std::string_view value) {
    return std::find(values.begin(), values.end(), value) != values.end();
}
struct StartupIntent {
    EngineStartupPrimary primary;
    bool composition;
    std::string_view path;
};
StartupIntent startup_intent(const Package& package) {
    const auto* old=package.find_file(startup_path);
    const auto* next=package.find_file(composition_startup_path);
    if(bool(old)==bool(next)) throw std::invalid_argument("Rich startup needs exactly one canonical metadata version");
    const auto* file=next ? next : old;
    if(file->component!="web" || file->media_type!="application/json")
        throw std::invalid_argument("Rich startup metadata must be a web application/json resource");
    const std::string_view value(reinterpret_cast<const char*>(file->data.data()),file->data.size());
    if(old && value==startup_value) return {EngineStartupPrimary::web,false,startup_path};
    if(next) {
        if(value=="{\"kind\":\"foundation-appended-startup\",\"primary\":\"web\",\"schema_version\":2}")
            return {EngineStartupPrimary::web,true,composition_startup_path};
        if(value=="{\"kind\":\"foundation-appended-startup\",\"primary\":\"compiled\",\"schema_version\":2}")
            return {EngineStartupPrimary::compiled,true,composition_startup_path};
        if(value=="{\"kind\":\"foundation-appended-startup\",\"primary\":\"binary\",\"schema_version\":2}")
            return {EngineStartupPrimary::binary,true,composition_startup_path};
    }
    throw std::invalid_argument("Selected retained rich generation does not support the canonical startup contract");
}
void validate_startup(const Package& package, const EngineOwnerConfiguration& config) {
    const auto startup=startup_intent(package);
    if(startup.primary!=config.startup_primary)
        throw std::invalid_argument("Package startup differs from the immutable application factory selection");
    if(!startup.composition && contains(package.capabilities,"foundation.gui-composition.v1"))
        throw std::invalid_argument("foundation.gui-composition.v1 requires canonical startup-v2 metadata");
    if(startup.composition && !contains(package.capabilities,"foundation.gui-composition.v1"))
        throw std::invalid_argument("Retained rich composition requires foundation.gui-composition.v1");
    if(config.startup_primary==EngineStartupPrimary::binary && (!package.binary.present || !config.module_factory ||
        !(contains(package.services,"foundation.view") && contains(package.capabilities,"foundation.view.v1"))))
        throw std::invalid_argument("Binary primary requires its actual shared Module view binding and foundation.view");
    if (!config.worker_epoch || !config.module_generation || package.abi_major != 1 || package.abi_minor != 0 ||
        !package.web.present || !package.web.entry)
        throw std::invalid_argument("rich kernel needs a verified Package with its embedded web region");
    if (config.startup_primary != EngineStartupPrimary::web && !contains(package.capabilities,"foundation.gui-composition.v1"))
        throw std::invalid_argument("Selected retained rich generation requires foundation.gui-composition.v1");
    if (!contains(package.capabilities, "foundation.startup.v1"))
        throw std::invalid_argument("rich kernel needs foundation.startup.v1 startup metadata");
    for (const auto& file : package.files) {
        std::string folded = file.path;
        for (auto& c : folded) if (c >= 'A' && c <= 'Z') c = static_cast<char>(c - 'A' + 'a');
        if ((folded == "web/.foundation" || folded.starts_with("web/.foundation/")) && file.path != startup.path)
            throw std::invalid_argument("unexpected reserved rich startup resource");
    }
    if (config.startup_primary != EngineStartupPrimary::binary &&
        (contains(package.services, "foundation.view") || contains(package.services, "foundation.view.v1") ||
         contains(package.capabilities, "foundation.view") || contains(package.capabilities, "foundation.view.v1")))
        throw std::invalid_argument("provider-only rich kernel does not implement foundation.view; kernel maintenance required");
    const auto* entry = package.find_file(*package.web.entry);
    if (!entry || entry->component != "web" || entry->media_type != "text/html")
        throw std::invalid_argument("rich kernel has no verified HTML entry");
    if (package.package_sha256.size() != 64 || !std::all_of(package.package_sha256.begin(), package.package_sha256.end(),
        [](char c) { return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'); }))
        throw std::invalid_argument("rich kernel Package has no canonical resource authority");
    if (package.binary.present && (!package.binary.entry || package.binary.profile != "foundation-guest-v1" ||
        !package.find_file(*package.binary.entry) || package.find_file(*package.binary.entry)->component != "binary"))
        throw std::invalid_argument("rich kernel has no verified provider-only binary entry");
    for (const auto& service : package.services) {
        const bool native = std::any_of(config.native_services.begin(), config.native_services.end(),
            [&](const auto& registration) { return registration.descriptor.name == service; });
        if (service != "foundation.kernel" && !(package.binary.present && service == "foundation.providers") &&
            !(config.startup_primary == EngineStartupPrimary::binary && service == "foundation.view") && !native)
            throw std::invalid_argument("required rich kernel service unavailable: " + service);
    }
    for (const auto& capability : package.capabilities)
        if (capability != "foundation.startup.v1" && capability != "foundation.gui-composition.v1" && !(package.binary.present && capability == "foundation.providers.v1") &&
            !(config.startup_primary == EngineStartupPrimary::binary && capability == "foundation.view.v1"))
            throw std::invalid_argument("required rich kernel capability unavailable: " + capability);
    if (config.services.max_message_bytes < FOUNDATION_APPENDED_ENVELOPE_BYTES + 320 ||
        config.services.max_message_bytes > FOUNDATION_APPENDED_MAX_MESSAGE_BYTES ||
        !config.services.max_retained_calls || config.services.max_retained_calls > 64 ||
        !config.services.max_retained_bytes || config.services.max_retained_bytes > 4 * FOUNDATION_APPENDED_MAX_MESSAGE_BYTES ||
        !config.services.max_service_handles || config.services.max_service_handles > 256)
        throw std::invalid_argument("rich service limits exceed the fixed bridge budget");
    if (config.input_profile.enabled && !engine_input::input_profile_valid(config.input_profile))
        throw std::invalid_argument("rich physical input needs exact maintained successor profile facts");
    if (config.document_profile.enabled && (!engine_document::document_profile_valid(config.document_profile) ||
        config.input_profile.enabled))
        throw std::invalid_argument("rich document input needs exact separate maintained successor profile facts");
    if (config.editor_profile.enabled && (!engine_editor::editor_profile_valid(config.editor_profile) ||
        config.input_profile.enabled || config.document_profile.enabled))
        throw std::invalid_argument("rich editor input needs exact independent maintained editor2035 facts");
    if (config.document_actions_profile.enabled &&
        (!engine_document_actions::document_actions_profile_valid(config.document_actions_profile) ||
         config.input_profile.enabled || config.document_profile.enabled || config.editor_profile.enabled))
        throw std::invalid_argument("rich document actions need exact independent maintained actions4083 facts");
    // Validate every startup-only registration with the actual transport before
    // an optional Module can initialize. This invokes no service handler.
    const WebServices validated(1, config.native_services, {}, config.services);
    if (package.binary.present && !config.module_factory)
        throw std::invalid_argument("rich binary component needs the retained optional module binding; kernel maintenance required");
}
} // namespace

struct EngineOwner::Impl {
    struct Document {
        EngineIdentity identity;
        std::unique_ptr<WebServices> services;
        std::map<std::uint64_t, bool> accepted;
        std::uint64_t highest{};
        bool retired{};
    };
    struct Delivery {
        Document* document{};
        std::uint64_t transfer{}, sequence{};
        Bytes bytes;
        bool frozen{};
    };
    struct Ack {
        Document* document{};
        std::uint64_t through{}, transfer{};
        ServiceStatus status{ServiceStatus::unavailable};
        bool applied{}, frozen{};
    };
    struct ResourceContext {
        EngineIdentity identity;
        std::size_t leases{};
        bool retired{};
    };
    struct ResourceLease {
        const PackageFile* file{};
        std::uint64_t epoch{};
        std::uint64_t body_bytes{};
    };
    struct RetiredTransfer { EngineIdentity identity; std::uint64_t transfer{}; };
    struct TerminalOutcome {
        EngineIdentity identity;
        std::uint64_t transfer{}, sequence{};
        bool ack_receipt{};
        Bytes bytes;
    };
    struct InputCommand {
        EngineIdentity target;
        std::uint64_t context{}, ticket{}, transfer{};
        engine_input::State next_state;
        Bytes bytes;
        bool lifecycle{}, retiring{}, exposed{}, entered{};
    };
    struct InputOutcome {
        EngineIdentity target;
        std::uint64_t transfer{}, ticket{};
        EngineInputOutcome value;
        std::array<std::uint8_t, engine_input::kCommandResultBytes> bytes{};
        bool has_result{};
    };
    struct NativeEffect {
        EngineNativeEffect value;
        std::uint64_t sequence{};
        bool acknowledged{}, completed{}, held{}, uncertain{};
    };
    struct DocumentWorkSlot {
        EngineDocumentDispatch dispatch;
        Bytes encoded;
        std::shared_ptr<EngineDocumentCompletion> completion;
        bool exposed{}, claimed{}, entered{}, returned{}, completed{}, action_acknowledged{};
    };
    struct EditorWorkSlot {
        EngineEditorDispatch dispatch;
        Bytes encoded;
        std::shared_ptr<EngineEditorCompletion> completion;
        std::array<std::uint8_t,FOUNDATION_ENGINE_EDITOR_RESULT_PREFIX_BYTES> forensic_prefix{};
        std::uint32_t forensic_prefix_bytes{};
        bool exposed{}, claimed{}, entered{}, returned{}, completed{}, result_fault{};
    };
    struct EditorRetirement {
        EngineEditorTarget target;
        native_editor::NativeRetireMaterial material;
        native_editor::Identity identity;
    };
    const Package package;
    const EngineOwnerConfiguration config;
    const std::thread::id thread{std::this_thread::get_id()};
    EngineIdentity current;
    EngineIdentity last_ready;
    std::array<Header, 64> turns{};
    std::uint32_t depth{};
    bool is_configured{}, is_closed{}, close_requested{}, pumping{}, failed{};
    std::uint64_t highest_document{};
    GenerationSource generations, resource_epochs, resource_leases;
    std::uint64_t next_transfer{1};
    std::unique_ptr<EngineModuleBinding> module;
    std::map<std::uint64_t, std::unique_ptr<Document>> documents;
    Document* active{};
    std::optional<Delivery> delivery;
    std::optional<Ack> ack;
    std::optional<TerminalOutcome> terminal;
    std::optional<RetiredTransfer> retirement, last_retirement, last_abandoned;
    std::map<std::uint64_t, ResourceContext> resources;
    std::map<std::uint64_t, ResourceLease> leases;
    std::uint64_t retained_resource_bytes{};
    std::optional<EngineFrame> frame;
    engine_input::State input_state;
    EngineIdentity input_target;
    GenerationSource input_sequences, native_effect_sequences;
    std::optional<InputCommand> input;
    std::optional<InputOutcome> input_outcome;
    std::optional<NativeEffect> effect;
    bool input_poisoned{}, module_closed{};
    engine_document::SequenceAllocator document_sequences;
    GenerationSource document_tickets;
    std::optional<std::uint64_t> document_reservation;
    EngineIdentity document_reservation_target;
    std::optional<DocumentWorkSlot> document_work, document_ack;
    std::optional<EditorWorkSlot> editor_work;
    GenerationSource editor_tickets;
    std::optional<std::uint64_t> editor_reservation;
    EngineIdentity editor_reservation_target;
    std::shared_ptr<const EngineEditorCompletion> editor_last_result;
    std::optional<EditorRetirement> editor_retirement;
    std::shared_ptr<const EngineDocumentCompletion> document_last_result, document_last_ack, document_ack_tombstone;
    std::uint64_t highest_safe_publication{}, highest_request_sequence{};
    std::atomic<bool> document_poisoned{};
    // Only already allocated owners can join this process-lived quarantine.
    // It has no container allocation or exit-time cleanup of engine owners.
    inline static std::atomic<bool> document_process_terminal{};
    // Admission linearizes at the flag check under this gate. An operation
    // admitted before terminal publication may finish naturally; its next
    // independent entry must check the flag again. This does not preempt it.
    inline static std::recursive_mutex document_admission_gate;
    inline static std::atomic<Impl*> quarantined_documents{};
    Impl* quarantine_next{};

    Impl(Package value, EngineOwnerConfiguration options)
        : package(std::move(value)), config(std::move(options)),
          current{config.worker_epoch, config.application_instance, 0, 0} {
        validate_startup(package, config);
        if (document_selected()) {
            std::lock_guard lock(document_admission_gate);
            if (document_process_terminal.load(std::memory_order_acquire))
                throw std::runtime_error("document engine process is terminal; process exit required");
        }
    }
    bool owner_thread() const noexcept { return thread == std::this_thread::get_id(); }
    bool blocked() const noexcept { return depth || pumping; }
    bool editor_selected() const noexcept { return config.editor_profile.enabled || config.document_actions_profile.enabled; }
    bool document_selected() const noexcept { return config.document_profile.enabled || editor_selected(); }
    bool document_barrier() const noexcept { return document_work || document_ack || document_reservation || editor_work || editor_reservation; }
    bool document_attempt() const noexcept {
        return (document_work && document_work->claimed && !document_work->completed) ||
            (document_ack && document_ack->claimed && !document_ack->completed) ||
            (editor_work && editor_work->claimed && !editor_work->completed);
    }
    bool barrier() const noexcept { return delivery || ack || terminal || retirement || input || document_barrier(); }
    bool physical_profile() const noexcept {
        return editor_selected() || config.input_profile.enabled || (config.document_profile.enabled &&
            config.document_profile.kind == engine_document::ProfileKind::physical);
    }
    bool document_terminal() const noexcept {
        return document_selected() && document_process_terminal.load(std::memory_order_acquire);
    }
    void notify_document_terminal() noexcept {
        if (!document_selected()) return;
        document_poisoned.store(true, std::memory_order_release);
        document_process_terminal.store(true, std::memory_order_release);
    }
    void poison_document() noexcept {
        notify_document_terminal();
        if (document_selected()) input_poisoned = true;
    }
    bool terminal_document_ownership() const noexcept {
        return document_selected() &&
            (document_poisoned || (editor_selected() && document_terminal()) || document_attempt() || editor_retirement || (input && input->entered) || depth || pumping ||
             (effect && effect->value.entered && (effect->held || effect->uncertain || !effect->completed)) ||
             (document_work && document_work->completed &&
              engine_document_action_kind(document_work->dispatch.work.kind) &&
              document_work->completion->outcome == EngineDocumentOutcome::consumed && !document_work->action_acknowledged));
    }
    void quarantine() noexcept {
        poison_document();
        auto* head = quarantined_documents.load(std::memory_order_relaxed);
        do { quarantine_next = head; }
        while (!quarantined_documents.compare_exchange_weak(head, this, std::memory_order_release, std::memory_order_relaxed));
    }
    bool input_enabled() const noexcept { return physical_profile() && !input_poisoned && !document_poisoned && !document_terminal() && !failed && !close_requested; }
    bool document_enabled() const noexcept { return document_selected() && !document_poisoned && !document_terminal() && !failed && !close_requested; }
    bool editor_enabled() const noexcept { return editor_selected() && !document_poisoned && !document_terminal() && !failed && !is_closed; }
    static EngineDocumentTarget document_target(EngineIdentity value) noexcept {
        return {value.worker_epoch, value.application_instance, value.document_sequence, value.service_generation};
    }
    static EngineIdentity engine_target(EngineDocumentTarget value) noexcept {
        return {value.worker_epoch, value.application_instance, value.document_sequence, value.service_generation};
    }
    static EngineEditorTarget editor_target(EngineIdentity value) noexcept {
        return {value.worker_epoch, value.application_instance, value.document_sequence, value.service_generation};
    }
    static EngineIdentity engine_target(EngineEditorTarget value) noexcept {
        return {value.worker_epoch, value.application_instance, value.document_sequence, value.service_generation};
    }
    EditorWorkSlot* editor_slot(const Header& header) noexcept {
        return editor_work && engine_target(editor_work->dispatch.work.target) == header.identity &&
            editor_work->dispatch.transfer == header.transfer ? &*editor_work : nullptr;
    }
    DocumentWorkSlot* document_slot(const Header& header) noexcept {
        for (auto* slot : {&document_work, &document_ack})
            if (*slot && engine_target((*slot)->dispatch.work.target) == header.identity &&
                (*slot)->dispatch.transfer == header.transfer) return &**slot;
        return nullptr;
    }
    bool document_holds(EngineIdentity target) const noexcept {
        return (document_work && engine_target(document_work->dispatch.work.target) == target) ||
            (document_ack && engine_target(document_ack->dispatch.work.target) == target) ||
            (editor_work && engine_target(editor_work->dispatch.work.target) == target) ||
            (editor_retirement && engine_target(editor_retirement->target) == target);
    }
    static bool ordinary_pending(const std::optional<DocumentWorkSlot>& slot) noexcept {
        return slot && !slot->completed;
    }
    bool document_entry_barrier() const noexcept {
        return ordinary_pending(document_work) || ordinary_pending(document_ack) || (editor_work && !editor_work->completed);
    }
    bool metadata_identity(const Header& header) const noexcept {
        return header.identity == current || (last_ready.service_generation && header.identity == last_ready);
    }
    bool retired_page_transactions_only() const noexcept {
        return config.abandon_closed_document_outcomes && !terminal && !retirement &&
            (!delivery || delivery->document->retired) && (!ack || ack->document->retired) &&
            !input && !document_barrier();
    }
    void cancel_input() noexcept {
        if (!input || input->entered) return;
        input_outcome = InputOutcome{input->target, input->transfer, input->ticket,
            {EngineInputCommandStatus::cancelled, 0, false}};
        input.reset();
    }
    void cancel_document_work(std::optional<DocumentWorkSlot>& slot) noexcept {
        if (!slot || slot->claimed || slot->completed) return;
        auto& value = *slot->completion;
        value.outcome = EngineDocumentOutcome::cancelled;
        value.provider_status = 0;
        value.provider_disposition = 0;
        value.handled = false;
        value.semantic_revision = 0;
        value.bytes.resize(0);
        slot->completed = true;
    }
    void cancel_editor_work() noexcept {
        if (!editor_work || editor_work->claimed || editor_work->completed) return;
        auto& value = *editor_work->completion;
        value.outcome = EngineEditorOutcome::cancelled;
        value.provider_status = 0; value.provider_disposition = 0;
        value.handled = false; value.semantic_revision = 0; value.bytes.resize(0);
        editor_work->completed = true;
    }
    std::optional<std::uint64_t> reserve_document_sequence() {
        if (!owner_thread() || !document_enabled() || !is_configured || blocked() ||
            !active || active->retired || document_work || document_ack || editor_work || editor_reservation || input || effect) return {};
        const auto value = document_sequences.reserve();
        if (value) {
            document_reservation = *value;
            document_reservation_target = active->identity;
            highest_request_sequence = *value;
        }
        return value;
    }
    bool cancel_document_sequence(std::uint64_t value) noexcept {
        if (!owner_thread() || !document_reservation || *document_reservation != value ||
            !document_sequences.cancel(value)) return false;
        document_reservation.reset();
        document_reservation_target = {};
        return true;
    }
    DocumentWorkSlot make_document_slot(EngineDocumentWork work) {
        // Both the immutable result owner and its complete provider capacity
        // exist before the work can be exposed or claimed by a driver.
        auto completion = std::make_shared<EngineDocumentCompletion>();
        completion->bytes.resize(work.required_reply_capacity);
        auto encoded = engine_document::encode_work(work);
        const auto ticket = document_tickets.next();
        const auto token = transfer();
        if (!ticket || !token) throw std::overflow_error("document mailbox identity exhausted");
        completion->target = work.target;
        completion->ticket = *ticket;
        completion->transfer = *token;
        completion->request_sequence = work.request_sequence;
        completion->kind = work.kind;
        return {{*ticket, *token, std::move(work)}, std::move(encoded), std::move(completion)};
    }
    EngineDocumentAdmission stage_document_work(EngineDocumentWork work) {
        if (!owner_thread() || !document_selected()) return {EngineDocumentAdmissionCode::unavailable};
        if (close_requested || is_closed || failed || document_poisoned || document_terminal()) return {EngineDocumentAdmissionCode::closed};
        if (!is_configured || effect) return {EngineDocumentAdmissionCode::unavailable};
        if (blocked() || document_work || document_ack || editor_work || editor_reservation || input) return {EngineDocumentAdmissionCode::busy};
        if (engine_document_ack_kind(work.kind) ||
            (work.kind == EngineDocumentWorkKind::body_action && !config.document_actions_profile.enabled) ||
            !engine_document::valid_work_join(work) ||
            !document_reservation || *document_reservation != work.request_sequence)
            return {EngineDocumentAdmissionCode::invalid};
        if (!active || active->retired || engine_target(work.target) != active->identity)
            return {EngineDocumentAdmissionCode::stale};
        auto slot = make_document_slot(std::move(work));
        if (!document_sequences.commit(slot.dispatch.work.request_sequence))
            throw std::logic_error("document reservation changed during serialized admission");
        document_reservation.reset();
        document_reservation_target = {};
        const auto ticket = slot.dispatch.ticket;
        document_work.emplace(std::move(slot));
        return {EngineDocumentAdmissionCode::admitted, ticket};
    }
    std::optional<std::uint64_t> reserve_editor_sequence() {
        if (!owner_thread() || !editor_enabled() || !is_configured || blocked() ||
            document_work || document_ack || document_reservation || editor_work || editor_reservation || input)
            return {};
        const bool retirement_only = close_requested || effect || !active || active->retired ||
            (editor_retirement && engine_target(editor_retirement->target) != active->identity);
        if (retirement_only && (!editor_retirement || (effect && (effect->value.entered || effect->acknowledged)))) return {};
        const auto target = retirement_only ? engine_target(editor_retirement->target) : active->identity;
        if (!document(Header{target})) return {};
        const auto value = document_sequences.reserve();
        if (value) {
            editor_reservation = *value; editor_reservation_target = target;
            highest_request_sequence = *value;
        }
        return value;
    }
    bool cancel_editor_sequence(std::uint64_t value) noexcept {
        if (!owner_thread() || !editor_reservation || *editor_reservation != value || !document_sequences.cancel(value)) return false;
        editor_reservation.reset(); editor_reservation_target = {};
        return true;
    }
    EditorWorkSlot make_editor_slot(EngineEditorWork work) {
        auto completion = std::make_shared<EngineEditorCompletion>();
        completion->bytes.resize(work.required_reply_capacity);
        auto encoded = encode_engine_editor_work(work);
        const auto ticket = editor_tickets.next(); const auto token = transfer();
        if (!ticket || !token) throw std::overflow_error("editor mailbox identity exhausted");
        completion->target = work.target; completion->ticket = *ticket; completion->transfer = *token;
        completion->request_sequence = work.request_sequence; completion->kind = work.kind;
        return {{*ticket,*token,std::move(work)},std::move(encoded),std::move(completion)};
    }
    EngineEditorAdmission stage_editor_work(EngineEditorWork work) {
        if (!owner_thread() || !editor_selected()) return {EngineEditorAdmissionCode::unavailable};
        if (!editor_enabled()) return {EngineEditorAdmissionCode::closed};
        if (!is_configured) return {EngineEditorAdmissionCode::unavailable};
        if (blocked() || document_work || document_ack || document_reservation || editor_work || input)
            return {EngineEditorAdmissionCode::busy};
        if (!valid_engine_editor_work_join(work) || !editor_reservation || *editor_reservation != work.request_sequence)
            return {EngineEditorAdmissionCode::invalid};
        const auto target = engine_target(work.target);
        if (target != editor_reservation_target || !document(Header{target})) return {EngineEditorAdmissionCode::stale};
        if (work.kind == EngineEditorWorkKind::revoke) {
            editor_codec::RevocationEnvelope request;
            if (!editor_codec::decode_revocation(work.payload, request) || !editor_retirement || editor_retirement->target != work.target ||
                request.request.material != editor_retirement->material || request.request.identity != editor_retirement->identity)
                return {EngineEditorAdmissionCode::invalid};
            if (effect && (effect->value.entered || effect->acknowledged))
                return {EngineEditorAdmissionCode::unavailable};
        } else {
            if (effect || close_requested) return {EngineEditorAdmissionCode::unavailable};
            if (!active || active->retired || active->identity != target) return {EngineEditorAdmissionCode::stale};
            const auto context = engine_editor_work_context(work);
            if (!context || !*context || input_target != target || *context != input_state.active_context)
                return {EngineEditorAdmissionCode::invalid};
            if (editor_retirement && editor_retirement->target != work.target) return {EngineEditorAdmissionCode::busy};
            if (work.kind == EngineEditorWorkKind::observation) {
                editor_codec::NativeRequestEnvelope request;
                if (!editor_codec::decode_native_request(work.payload, request) || !editor_retirement ||
                    request.request.resolved.retire != std::optional(editor_retirement->material) ||
                    request.request.resolved.identity != editor_retirement->identity)
                    return {EngineEditorAdmissionCode::invalid};
            }
        }
        auto slot = make_editor_slot(std::move(work));
        if (!document_sequences.commit(slot.dispatch.work.request_sequence)) throw std::logic_error("editor reservation changed during serialized admission");
        editor_reservation.reset(); editor_reservation_target = {};
        const auto ticket = slot.dispatch.ticket;
        editor_work.emplace(std::move(slot));
        return {EngineEditorAdmissionCode::admitted,ticket};
    }
    bool retained_action(EngineDocumentTarget target, std::uint64_t original, EngineDocumentWorkKind kind) const noexcept {
        return document_work && document_work->completed &&
            document_work->dispatch.work.kind == kind &&
            document_work->dispatch.work.target == target &&
            document_work->dispatch.work.request_sequence == original &&
            document_work->completion->outcome == EngineDocumentOutcome::consumed;
    }
    EngineDocumentAdmission stage_document_action_ack(EngineDocumentTarget target, std::uint64_t original,
            EngineDocumentWorkKind kind = EngineDocumentWorkKind::action_ack) {
        const bool body = kind == EngineDocumentWorkKind::body_action_ack;
        if (!owner_thread() || !document_selected() || (body && !config.document_actions_profile.enabled)) return {EngineDocumentAdmissionCode::unavailable};
        if (document_ack && document_ack->dispatch.work.kind == kind && document_ack->dispatch.work.target == target &&
            get(document_ack->dispatch.work.payload, 0, 8) == original) {
            if (document_terminal() && (!document_ack->completed ||
                document_ack->completion->outcome == EngineDocumentOutcome::unknown))
                return {EngineDocumentAdmissionCode::closed};
            return {EngineDocumentAdmissionCode::admitted, document_ack->dispatch.ticket};
        }
        for (const auto& cached : {document_last_ack, document_ack_tombstone}) {
            if (!cached || cached->kind != kind || cached->target != target || cached->outcome != EngineDocumentOutcome::consumed) continue;
            const auto receipt = decode_engine_document_action_ack(cached->bytes);
            if (receipt && receipt->original_action_sequence == original && receipt->code != EngineDocumentAckCode::stale)
                return {EngineDocumentAdmissionCode::admitted, cached->ticket};
        }
        if (failed || document_poisoned || document_terminal()) return {EngineDocumentAdmissionCode::closed};
        if (!is_configured || blocked() || input || document_ack || document_reservation || editor_work || editor_reservation ||
            (document_work && !document_work->completed)) return {EngineDocumentAdmissionCode::busy};
        if ((close_requested || is_closed) && !retained_action(target, original, engine_document_ack_action_kind(kind))) return {EngineDocumentAdmissionCode::closed};
        const auto payload = encode_engine_document_action_ack(original);
        if (!payload || original > highest_request_sequence || target.worker_epoch != config.worker_epoch || target.application_instance != current.application_instance ||
            !target.document_sequence || !target.service_generation) return {EngineDocumentAdmissionCode::invalid};
        EngineDocumentWork work{target, BIB_ENGINE_DOCUMENT_V2_MAX_ACK_SEQUENCE, kind,
            body ? BIB_ENGINE_COMMAND_ACK_DOCUMENT_ACTION_V1 : BIB_ENGINE_COMMAND_ACK_FORM_ACTION_V2,
            BIB_ENGINE_DOCUMENT_V2_ACK_REPLY_CAPACITY,
            body ? engine_document_actions::kAckSchema : engine_document::kAckSchema, Bytes(payload->begin(), payload->end())};
        if (!engine_document::valid_work_join(work)) return {EngineDocumentAdmissionCode::invalid};
        auto slot = make_document_slot(std::move(work));
        const auto sequence = document_sequences.issue_ack();
        if (!sequence) return {EngineDocumentAdmissionCode::busy};
        highest_request_sequence = *sequence;
        slot.dispatch.work.request_sequence = *sequence;
        slot.completion->request_sequence = *sequence;
        put(slot.encoded, 8, *sequence, 8);
        const auto ticket = slot.dispatch.ticket;
        document_ack.emplace(std::move(slot));
        return {EngineDocumentAdmissionCode::admitted, ticket};
    }
    void retire_input(EngineIdentity target) noexcept {
        if (document_reservation && document_reservation_target == target)
            (void)cancel_document_sequence(*document_reservation);
        if (editor_reservation && editor_reservation_target == target)
            (void)cancel_editor_sequence(*editor_reservation);
        if (input && input->target == target) cancel_input();
        if (input_target == target) {
            engine_input::retire_document(input_state);
            input_target = {};
        }
        if (effect && effect->value.target == target && !effect->value.entered) effect.reset();
        if (document_work && engine_target(document_work->dispatch.work.target) == target) cancel_document_work(document_work);
        if (editor_work && engine_target(editor_work->dispatch.work.target) == target) cancel_editor_work();
    }
    std::optional<EngineInputTicket> stage_command(EngineIdentity target, std::uint64_t context,
        std::uint32_t operation, const engine_input::Digest& schema, Bytes payload, bool lifecycle) {
        if (!owner_thread() || !physical_profile() || input_poisoned || document_poisoned || document_terminal() || failed || pumping || depth || input ||
            !is_configured || is_closed || !context) return {};
        Header header{target};
        auto* value = document(header);
        if (!value || value->retired || !active || active != value) return {};
        auto next_state = input_state;
        engine_input::Status status{engine_input::Status::invalid};
        bool retiring{};
        if (operation == 1 && !lifecycle && schema == engine_input::kKeySchema) {
            engine_input::Key key;
            status = engine_input::decode_key(payload, key);
            if (status == engine_input::Status::ok && key.input_context == context && input_target == target)
                status = engine_input::accept_key(next_state, key);
            else status = engine_input::Status::invalid;
        } else if (operation == 3 && schema == engine_input::kFocusSchema) {
            engine_input::Focus focus;
            status = engine_input::decode_focus(payload, focus);
            if (status != engine_input::Status::ok) return {};
            retiring = focus.action == 2;
            if ((retiring ? focus.expected_context : focus.input_context) != context || lifecycle != (focus.action != 0) ||
                (focus.action != 1 && input_target != target)) return {};
            status = engine_input::accept_focus(next_state, focus);
        } else if (operation == 5 && !lifecycle && schema == engine_input::kMouseSchema) {
            engine_input::Mouse mouse;
            status = engine_input::decode_mouse(payload, mouse);
            if (status == engine_input::Status::ok && mouse.input_context == context && input_target == target)
                status = engine_input::accept_mouse(next_state, mouse);
            else status = engine_input::Status::invalid;
        }
        if (status != engine_input::Status::ok || ((effect || close_requested) && !retiring) ||
            (document_selected() && (document_reservation || editor_reservation ||
             ((document_work || document_ack || editor_work) && (!retiring || document_entry_barrier()))))) return {};
        const auto ticket = document_selected() ? document_sequences.issue_physical() : input_sequences.next();
        if (!ticket || !next_transfer) return {};
        if (document_selected()) highest_request_sequence = *ticket;
        Bytes bytes;
        if (engine_input::encode_command({operation, *ticket, schema, std::move(payload)}, bytes) != engine_input::Status::ok)
            return {};
        const auto token = transfer();
        input.emplace(InputCommand{target, context, *ticket, *token, next_state, std::move(bytes), lifecycle, retiring});
        return ticket;
    }
    std::optional<std::uint64_t> transfer() noexcept {
        if (!next_transfer) return {};
        const auto value = next_transfer;
        next_transfer = value == std::numeric_limits<std::uint64_t>::max() ? 0 : value + 1;
        return value;
    }
    Header document_header(const Document& document, std::uint64_t transfer = 0) const noexcept {
        return {document.identity, transfer, 0};
    }
    Document* document(const Header& header) noexcept {
        const auto found = documents.find(header.identity.document_sequence);
        if (found == documents.end() || found->second->identity != header.identity) return nullptr;
        return found->second.get();
    }
    void prune() noexcept {
        for (auto it = documents.begin(); it != documents.end();) {
            auto* value = it->second.get();
            if (!config.abandon_closed_document_outcomes && value->retired && value->services->retained_call_count() == 0 &&
                (!delivery || delivery->document != value) && (!ack || ack->document != value) &&
                !document_holds(value->identity)) it = documents.erase(it);
            else ++it;
        }
        for (auto it = resources.begin(); it != resources.end();)
            if (it->second.retired && !it->second.leases) it = resources.erase(it); else ++it;
    }
    void retire(Document& value) noexcept {
        retire_input(value.identity);
        value.services->close(); value.retired = true;
        for (auto& [epoch, resource] : resources) {
            (void)epoch;
            if (resource.identity.application_instance == value.identity.application_instance &&
                resource.identity.document_sequence == value.identity.document_sequence) resource.retired = true;
        }
        if (active == &value) { active = nullptr; current.document_sequence = 0; current.service_generation = 0; }
        if (frame && frame->identity == value.identity) frame.reset();
    }
    void request_close() noexcept {
        close_requested = true;
        cancel_input();
        cancel_document_work(document_work);
        if (editor_work && editor_work->dispatch.work.kind != EngineEditorWorkKind::revoke) cancel_editor_work();
        if (document_reservation) (void)cancel_document_sequence(*document_reservation);
        if (editor_reservation) (void)cancel_editor_sequence(*editor_reservation);
        engine_input::retire_document(input_state);
        input_target = {};
        if (effect && !effect->value.entered) effect.reset();
        for (auto& [sequence, value] : documents) { (void)sequence; value->services->close(); value->retired = true; }
        for (auto& [epoch, resource] : resources) { (void)epoch; resource.retired = true; }
        current.document_sequence = 0; current.service_generation = 0;
        if (!blocked()) finish_close();
    }
    void finish_close() noexcept {
        if (document_poisoned || (editor_selected() && document_terminal()) || editor_retirement || (input && input->entered) || document_barrier() ||
            (document_selected() && effect && effect->value.entered &&
             (effect->held || effect->uncertain || !effect->completed))) return;
        if (module && (!document_selected() || !module_closed)) {
            if (document_selected()) module_closed = true;
            module->close();
        }
        active = nullptr; frame.reset();
        is_closed = leases.empty() && (!config.abandon_closed_document_outcomes ||
            (documents.empty() && !barrier()));
    }
    ServiceStatus initialize() {
        if (is_configured) return ServiceStatus::conflict;
        pumping = true;
        struct Guard { Impl& self; ~Guard() { self.pumping = false; if (self.close_requested) self.finish_close(); } } guard{*this};
        if (package.binary.present) {
            module = config.module_factory(package.find_file(*package.binary.entry)->data,
                config.native_services, config.module_generation);
            if (!module) throw std::runtime_error("retained optional module binding returned no owner");
            if (config.startup_primary == EngineStartupPrimary::binary && (!module->supports_view() || !module->view()))
                throw std::runtime_error("Selected retained binding does not implement the required binary primary view");
            const auto hooks = module->services();
            if (hooks.generation != config.module_generation || !hooks.discover || !hooks.invoke || !hooks.acknowledge || !hooks.sequence)
                throw std::runtime_error("retained optional module binding has incompatible persistent hooks");
        }
        is_configured = true;
        return close_requested ? ServiceStatus::closed : ServiceStatus::ok;
    }
    WebModuleServices module_binding() {
        return module ? module->services() : WebModuleServices{};
    }
    std::uint32_t begin(const Header& header, Header& result) {
        if (!header.identity.document_sequence || header.identity.service_generation ||
            header.identity.document_sequence <= highest_document) return FOUNDATION_ENGINE_STALE;
        prune();
        const auto retained = std::count_if(documents.begin(), documents.end(),
            [](const auto& item) { return item.second->retired; });
        if (retained >= 8 && active && (config.abandon_closed_document_outcomes || active->services->retained_call_count()))
            return FOUNDATION_ENGINE_LIMIT;
        const auto generation = generations.next();
        if (!generation) return FOUNDATION_ENGINE_LIMIT;
        // Allocation/setup precedes retiring the current queue; publication of
        // the new generation always follows closing the old actual WebServices.
        auto value = std::make_unique<Document>();
        value->identity = header.identity; value->identity.service_generation = *generation;
        value->services = std::make_unique<WebServices>(*generation, config.native_services, module_binding(), config.services);
        const auto [position, inserted] = documents.emplace(header.identity.document_sequence, std::move(value));
        if (!inserted) return FOUNDATION_ENGINE_CONFLICT;
        if (active) retire(*active);
        active = position->second.get(); current = active->identity;
        last_ready = current;
        for (auto& [epoch, resource] : resources) {
            (void)epoch;
            if (resource.identity.application_instance == current.application_instance &&
                resource.identity.document_sequence == current.document_sequence)
                resource.identity.service_generation = current.service_generation;
        }
        highest_document = current.document_sequence; result = document_header(*active);
        prune();
        return FOUNDATION_ENGINE_OK;
    }
    bool collect() {
        if (delivery || ack) return true;
        for (auto& [sequence, value] : documents) {
            (void)sequence;
            if (config.abandon_closed_document_outcomes && value->retired &&
                !(effect && !effect->completed && effect->value.target == value->identity)) continue;
            if (!next_transfer) return false;
            std::optional<Bytes> bytes;
            try { bytes = value->services->take_completion(); }
            catch (const std::bad_alloc&) { return false; }
            if (!bytes) continue;
            Envelope envelope; Span ignored;
            if (decode_envelope(*bytes, envelope, ignored) != CodecStatus::ok)
                throw std::logic_error("actual web queue returned a malformed completion");
            if (effect && !effect->completed &&
                effect->value.target == value->identity && envelope.generation == value->identity.service_generation &&
                envelope.sequence == effect->sequence) {
                effect->completed = true;
                if (effect->value.entered && envelope.service_status == FOUNDATION_APPENDED_SERVICE_UNCERTAIN) {
                    effect->uncertain = true;
                    input_poisoned = true;
                    poison_document();
                } else if (!effect->held) effect.reset();
            }
            delivery.emplace(Delivery{value.get(), *transfer(), envelope.sequence, std::move(*bytes), false});
            return true;
        }
        return true;
    }
    bool valid_resource_identity(const Header& header, const ResourceContext& resource) const noexcept {
        return resource.identity.worker_epoch == header.identity.worker_epoch &&
            resource.identity.application_instance == header.identity.application_instance &&
            resource.identity.document_sequence == header.identity.document_sequence &&
            (!header.identity.service_generation || resource.identity.service_generation == header.identity.service_generation);
    }
    std::uint32_t settle_document_result(const Header& header, Span payload) {
        if (payload.size() < FOUNDATION_ENGINE_DOCUMENT_RESULT_PREFIX_BYTES || get(payload, 4, 4))
            return FOUNDATION_ENGINE_INVALID;
        const auto kind_value = get(payload, 0, 4), sequence = get(payload, 8, 8);
        const auto wire_status = static_cast<std::uint32_t>(get(payload, 16, 4));
        const auto status = wire_status <= INT32_MAX ? static_cast<std::int32_t>(wire_status) :
            -1 - static_cast<std::int32_t>(UINT32_MAX - wire_status);
        const auto disposition = get(payload, 20, 4), written = get(payload, 24, 4), handled = get(payload, 28, 4);
        const auto semantic_revision = get(payload, 32, 8);
        if (kind_value < 1 || kind_value > (config.document_actions_profile.enabled ? 5 : 3) || !sequence || status > 0 || status < BIB_ENGINE_PROCESS_EXIT_REQUIRED ||
            disposition > 2 || handled > 1 || written != payload.size() - FOUNDATION_ENGINE_DOCUMENT_RESULT_PREFIX_BYTES)
            return FOUNDATION_ENGINE_INVALID;
        const auto kind = static_cast<EngineDocumentWorkKind>(kind_value);
        const auto bytes = payload.subspan(FOUNDATION_ENGINE_DOCUMENT_RESULT_PREFIX_BYTES);
        for (const auto& cached : {document_last_result, document_last_ack, document_ack_tombstone}) {
            if (!cached || engine_target(cached->target) != header.identity || cached->transfer != header.transfer ||
                cached->kind != kind || cached->request_sequence != sequence) continue;
            return cached->provider_status == status && cached->provider_disposition == disposition &&
                cached->handled == (handled != 0) && cached->semantic_revision == semantic_revision &&
                cached->bytes.size() == bytes.size() && std::equal(bytes.begin(), bytes.end(), cached->bytes.begin()) ?
                FOUNDATION_ENGINE_OK : FOUNDATION_ENGINE_CONFLICT;
        }
        auto* slot = document_slot(header);
        if (!slot || slot->completed || !slot->claimed || slot->dispatch.work.kind != kind ||
            slot->dispatch.work.request_sequence != sequence) return FOUNDATION_ENGINE_STALE;
        const bool known_preentry = !slot->entered && status < 0 && status != BIB_ENGINE_PROCESS_EXIT_REQUIRED &&
            !disposition && !written && !handled && !semantic_revision;
        if ((engine_document_ack_kind(kind) && slot->entered) ||
            (!engine_document_ack_kind(kind) &&
             ((slot->entered && !slot->returned) || (!slot->entered && !known_preentry))))
            return FOUNDATION_ENGINE_CONFLICT;
        EngineDocumentOutcome outcome;
        if (kind == EngineDocumentWorkKind::snapshot_query) {
            if (disposition || handled || (status && (written || semantic_revision)) ||
                (!status && (!semantic_revision || !engine_document::valid_reply_join(slot->dispatch.work, bytes)))) return FOUNDATION_ENGINE_INVALID;
            outcome = !status ? EngineDocumentOutcome::consumed : status == BIB_ENGINE_PROCESS_EXIT_REQUIRED ?
                EngineDocumentOutcome::unknown : EngineDocumentOutcome::rejected;
        } else {
            if (semantic_revision || (disposition == 1 && status != 0) || (disposition == 0 && status == 0) ||
                (disposition == 0 && (written || handled)) ||
                (disposition == 1 && !engine_document::valid_reply_join(slot->dispatch.work, bytes))) return FOUNDATION_ENGINE_INVALID;
            if (engine_document_ack_kind(kind) && disposition == 1 && handled) return FOUNDATION_ENGINE_INVALID;
            // A naturally returned unknown command keeps bounded opaque evidence.
            // It cannot establish a decoded form result or a checked ACK proof.
            outcome = disposition == 1 ? EngineDocumentOutcome::consumed :
                disposition == 2 || status == BIB_ENGINE_PROCESS_EXIT_REQUIRED ? EngineDocumentOutcome::unknown : EngineDocumentOutcome::rejected;
        }
        if (config.document_actions_profile.enabled && engine_document_ack_kind(kind) &&
            outcome == EngineDocumentOutcome::consumed) {
            const auto original = get(slot->dispatch.work.payload, 0, 8);
            const auto action_kind = engine_document_ack_action_kind(kind);
            bool foreign_family = document_work &&
                document_work->dispatch.work.target == slot->dispatch.work.target &&
                document_work->dispatch.work.request_sequence == original &&
                document_work->dispatch.work.kind != action_kind;
            // The original slot can already have been locally consumed. Its
            // retained successful receipt still proves the original family
            // and must not be replaced by a foreign-family success receipt.
            for (const auto& cached : {document_last_ack, document_ack_tombstone}) {
                if (!cached || cached->target != slot->dispatch.work.target || cached->kind == kind ||
                    cached->outcome != EngineDocumentOutcome::consumed) continue;
                const auto proof = decode_engine_document_action_ack(cached->bytes);
                if (proof && proof->original_action_sequence == original && proof->code != EngineDocumentAckCode::stale)
                    foreign_family = true;
            }
            const auto receipt = decode_engine_document_action_ack(bytes);
            if (foreign_family && receipt->code != EngineDocumentAckCode::stale) return FOUNDATION_ENGINE_INVALID;
        }
        if (written > slot->completion->bytes.size()) return FOUNDATION_ENGINE_LIMIT;
        auto& completion = *slot->completion;
        std::copy(bytes.begin(), bytes.end(), completion.bytes.begin());
        completion.bytes.resize(static_cast<std::size_t>(written));
        completion.outcome = outcome;
        completion.provider_status = status;
        completion.provider_disposition = static_cast<std::uint32_t>(disposition);
        completion.handled = handled != 0;
        completion.semantic_revision = semantic_revision;
        slot->completed = true;
        if (engine_document_ack_kind(kind)) {
            document_last_ack = slot->completion;
            if (outcome == EngineDocumentOutcome::consumed) {
                const auto receipt = decode_engine_document_action_ack(completion.bytes);
                if (receipt->code == EngineDocumentAckCode::retired) document_ack_tombstone = slot->completion;
                if (receipt->code != EngineDocumentAckCode::stale && retained_action(completion.target, receipt->original_action_sequence, engine_document_ack_action_kind(kind)))
                    document_work->action_acknowledged = true;
            }
        } else document_last_result = slot->completion;
        if (outcome == EngineDocumentOutcome::unknown) {
            poison_document();
            request_close();
        }
        return FOUNDATION_ENGINE_OK;
    }
    bool update_editor_retirement(const EngineEditorWork& work, EngineEditorReadback readback) {
        const bool retiring = readback.retired.has_value();
        if (retiring && (!editor_retirement || editor_retirement->target != work.target ||
                editor_retirement->material != *readback.retired)) return false;
        if (readback.retire) {
            if (readback.retire->input_context != readback.identity.context ||
                (retiring && readback.retire->token == readback.retired->token)) return false;
            if (editor_retirement && !retiring && (editor_retirement->target != work.target ||
                    editor_retirement->material.token != readback.retire->token ||
                    editor_retirement->material.input_context != readback.retire->input_context ||
                    !engine_editor_work_detail::same_context(editor_retirement->identity,readback.identity))) return false;
        }
        // Every check precedes mutation. The retained identity moves its already
        // owned string; no post-effect reservation or new native authority is made.
        if (retiring) editor_retirement.reset();
        if (readback.retire) editor_retirement = EditorRetirement{work.target,*readback.retire,std::move(readback.identity)};
        return true;
    }
    std::uint32_t settle_editor_result(const Header& header, Span payload) {
        auto* original=editor_slot(header);
        if (original && original->result_fault) return FOUNDATION_ENGINE_CLOSED;
        auto raw_fault = [&](std::uint32_t code) {
            if (original && original->claimed && !original->completed && original->entered && original->returned) {
                const auto prefix=std::min(payload.size(),original->forensic_prefix.size());
                std::copy_n(payload.begin(),prefix,original->forensic_prefix.begin());
                original->forensic_prefix_bytes=static_cast<std::uint32_t>(prefix);
                const auto body=payload.subspan(prefix);
                const auto count=std::min(body.size(),original->completion->bytes.size());
                std::copy_n(body.begin(),count,original->completion->bytes.begin());
                original->completion->bytes.resize(count);
                original->result_fault=true;
                poison_document(); request_close();
            }
            return code;
        };
        if (payload.size() < FOUNDATION_ENGINE_EDITOR_RESULT_PREFIX_BYTES || get(payload,4,4)) return raw_fault(FOUNDATION_ENGINE_INVALID);
        const auto kind_value=get(payload,0,4), sequence=get(payload,8,8);
        if (kind_value < 1 || kind_value > 3 || !sequence) return raw_fault(FOUNDATION_ENGINE_INVALID);
        const auto kind=static_cast<EngineEditorWorkKind>(kind_value);
        const auto wire_status=static_cast<std::uint32_t>(get(payload,16,4));
        const auto status=wire_status<=INT32_MAX ? static_cast<std::int32_t>(wire_status) :
            -1-static_cast<std::int32_t>(UINT32_MAX-wire_status);
        const auto disposition=get(payload,20,4), written=get(payload,24,4), handled=get(payload,28,4), revision=get(payload,32,8);
        const auto bytes=payload.subspan(FOUNDATION_ENGINE_EDITOR_RESULT_PREFIX_BYTES);
        if (editor_last_result && engine_target(editor_last_result->target)==header.identity &&
                editor_last_result->transfer==header.transfer && editor_last_result->kind==kind && editor_last_result->request_sequence==sequence) {
            const auto& cached=*editor_last_result;
            return cached.provider_status==status && cached.provider_disposition==disposition && cached.handled==(handled!=0) &&
                handled<=1 && cached.semantic_revision==revision && written==bytes.size() && cached.bytes.size()==bytes.size() &&
                std::equal(bytes.begin(),bytes.end(),cached.bytes.begin()) ? FOUNDATION_ENGINE_OK : FOUNDATION_ENGINE_CONFLICT;
        }
        auto* slot=editor_slot(header);
        if (!slot || !slot->claimed || slot->completed) return FOUNDATION_ENGINE_STALE;
        if (slot->dispatch.work.kind!=kind || slot->dispatch.work.request_sequence!=sequence)
            return raw_fault(FOUNDATION_ENGINE_INVALID);
        if (slot->result_fault) return FOUNDATION_ENGINE_CLOSED;
        auto retain = [&](EngineEditorOutcome outcome) {
            auto& value=*slot->completion;
            const auto count=std::min(bytes.size(),value.bytes.size());
            std::copy_n(bytes.begin(),count,value.bytes.begin()); value.bytes.resize(count);
            value.outcome=outcome; value.provider_status=status; value.provider_disposition=static_cast<std::uint32_t>(disposition);
            value.handled=handled!=0; value.semantic_revision=revision;
        };
        auto fault = [&](std::uint32_t code) {
            retain(EngineEditorOutcome::unknown); slot->result_fault=true;
            const auto count=std::min(payload.size(),slot->forensic_prefix.size());
            std::copy_n(payload.begin(),count,slot->forensic_prefix.begin());
            slot->forensic_prefix_bytes=static_cast<std::uint32_t>(count);
            poison_document(); request_close();
            return code;
        };
        if (status>0 || status<BIB_ENGINE_PROCESS_EXIT_REQUIRED || disposition>2 || handled>1 || written!=bytes.size() ||
                written>slot->completion->bytes.size()) return fault(FOUNDATION_ENGINE_INVALID);
        const bool known_preentry=!slot->entered && status<0 && status!=BIB_ENGINE_PROCESS_EXIT_REQUIRED &&
            !disposition && !written && !handled && !revision;
        // An early copied RESULT does not prove a provider has returned. Refuse
        // it without consuming the still-held claim; the Driver separately
        // terminates a real native attempt that returns without its TURN.
        if ((slot->entered && !slot->returned) || (!slot->entered && !known_preentry)) return FOUNDATION_ENGINE_CONFLICT;
        EngineEditorOutcome outcome;
        std::optional<EngineEditorReadback> checked;
        if (kind==EngineEditorWorkKind::projection_query) {
            if (disposition || handled || (status && status!=BIB_ENGINE_PROCESS_EXIT_REQUIRED && (written || revision)))
                return fault(FOUNDATION_ENGINE_INVALID);
            if (!status) {
                checked=checked_engine_editor_reply(slot->dispatch.work,bytes,revision);
                if (!checked) return fault(FOUNDATION_ENGINE_INVALID);
            }
            outcome=status==BIB_ENGINE_PROCESS_EXIT_REQUIRED ? EngineEditorOutcome::unknown :
                status ? EngineEditorOutcome::rejected : EngineEditorOutcome::consumed;
        } else {
            if (revision || (disposition==1 && status!=0) || (disposition==0 && (!status || written || handled)))
                return fault(FOUNDATION_ENGINE_INVALID);
            if (disposition==1) {
                checked=checked_engine_editor_reply(slot->dispatch.work,bytes,0);
                if (!checked) return fault(FOUNDATION_ENGINE_INVALID);
            }
            outcome=disposition==2 || status==BIB_ENGINE_PROCESS_EXIT_REQUIRED ? EngineEditorOutcome::unknown :
                disposition==1 ? EngineEditorOutcome::consumed : EngineEditorOutcome::rejected;
        }
        if (checked && checked->semantic_unknown) outcome=EngineEditorOutcome::unknown;
        if (checked && !checked->semantic_unknown && !update_editor_retirement(slot->dispatch.work,std::move(*checked)))
            return fault(FOUNDATION_ENGINE_INVALID);
        retain(outcome); slot->completed=true; editor_last_result=slot->completion;
        if (outcome==EngineEditorOutcome::unknown) { poison_document(); request_close(); }
        return FOUNDATION_ENGINE_OK;
    }
    std::int32_t dispatch(std::uint32_t op, const Header& header, Span payload, std::span<std::uint8_t> output) {
        Header response = header;
        auto result = [&](std::uint32_t control, ServiceStatus status = ServiceStatus::ok, Span body = {}) {
            return reply(op, response, output, control, status, body);
        };
        auto unavailable = [&] { return result(FOUNDATION_ENGINE_CONFLICT, ServiceStatus::unavailable); };
        if (!owner_thread()) return result(FOUNDATION_ENGINE_CONFLICT, ServiceStatus::unavailable);
        if (output.size() < receipt_bytes) return FOUNDATION_ENGINE_REPLY_TOO_SMALL;
        if (document_ack && document_ack->claimed && !document_ack->completed &&
            (op <= FOUNDATION_ENGINE_RESOURCE_RELEASE || op == FOUNDATION_ENGINE_FRAME_COMMIT ||
             op == FOUNDATION_ENGINE_BEGIN_RESOURCE_EPOCH || op == FOUNDATION_ENGINE_RETIRE_RESOURCE_EPOCH))
            return unavailable();
        if (header.identity.worker_epoch != config.worker_epoch) return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
        const bool leaving_initial = op == FOUNDATION_ENGINE_TURN_LEAVE && depth &&
            turns[depth - 1].identity == header.identity && turns[depth - 1].transfer == header.transfer;
        const bool initial_turn = op == FOUNDATION_ENGINE_TURN_ENTER && !current.application_instance && !header.identity.application_instance &&
            !header.identity.document_sequence && !header.identity.service_generation;
        const bool adoption = !current.application_instance && header.identity.application_instance && depth &&
            (op == FOUNDATION_ENGINE_BEGIN_DOCUMENT || op == FOUNDATION_ENGINE_BEGIN_RESOURCE_EPOCH) &&
            header.identity.document_sequence && !header.identity.service_generation;
        if (header.identity.application_instance != current.application_instance && !adoption && !leaving_initial)
            return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
        if (op != FOUNDATION_ENGINE_CONFIGURE && !is_configured) return result(FOUNDATION_ENGINE_CONFLICT, ServiceStatus::unavailable);
        const bool retirement_entry = op == FOUNDATION_ENGINE_TURN_ENTER && retirement &&
            header.identity == retirement->identity && header.transfer == retirement->transfer;
        const auto* editor_entry_slot = editor_slot(header);
        const bool editor_retirement_entry = op == FOUNDATION_ENGINE_TURN_ENTER && editor_entry_slot &&
            editor_entry_slot->dispatch.work.kind == EngineEditorWorkKind::revoke && editor_entry_slot->claimed &&
            !editor_entry_slot->completed && !editor_entry_slot->result_fault;
        const bool input_result = op == FOUNDATION_ENGINE_COMMAND_RESULT && physical_profile() &&
            ((input && input->entered && header.identity == input->target && header.transfer == input->transfer) ||
             (input_outcome && input_outcome->has_result && header.identity == input_outcome->target && header.transfer == input_outcome->transfer));
        const bool terminal_operation = op >= FOUNDATION_ENGINE_PEEK_RETIRED_DOCUMENT && op <= FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT;
        const bool document_operation = document_selected() && op >= FOUNDATION_ENGINE_PEEK_DOCUMENT_WORK &&
            op <= FOUNDATION_ENGINE_BEGIN_DOCUMENT_WORK;
        const bool editor_operation = editor_selected() && op >= FOUNDATION_ENGINE_PEEK_EDITOR_WORK &&
            op <= FOUNDATION_ENGINE_BEGIN_EDITOR_WORK;
        if (op != FOUNDATION_ENGINE_CLOSE && op != FOUNDATION_ENGINE_TURN_LEAVE && op != FOUNDATION_ENGINE_CLOSE_DOCUMENT &&
            op != FOUNDATION_ENGINE_RESOURCE_RELEASE && op != FOUNDATION_ENGINE_RETIRE_RESOURCE_EPOCH &&
            !terminal_operation && !retirement_entry && !editor_retirement_entry && !input_result && !document_operation && !editor_operation &&
            (is_closed || failed || close_requested))
            return result(FOUNDATION_ENGINE_CLOSED, ServiceStatus::closed);
        if (payload.size() > (op == FOUNDATION_ENGINE_FRAME_COMMIT ? max_frame_bytes + 48 :
            op == FOUNDATION_ENGINE_DOCUMENT_WORK_RESULT && document_selected() ?
                FOUNDATION_ENGINE_DOCUMENT_MAX_RESULT_BODY_BYTES :
            op == FOUNDATION_ENGINE_EDITOR_WORK_RESULT && editor_selected() ?
                FOUNDATION_ENGINE_EDITOR_MAX_RESULT_BODY_BYTES : FOUNDATION_ENGINE_MAX_BODY_BYTES))
            return result(FOUNDATION_ENGINE_LIMIT, ServiceStatus::limit_exceeded);
        const bool service_op = op == FOUNDATION_ENGINE_SUBMIT || op == FOUNDATION_ENGINE_CANCEL || op == FOUNDATION_ENGINE_STAGE_ACK;
        if (service_op && (!header.identity.service_generation || !document(header)))
            return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
        const bool scheduler_op = op == FOUNDATION_ENGINE_PUMP_ONE || op == FOUNDATION_ENGINE_PEEK_DELIVERY ||
            op == FOUNDATION_ENGINE_PEEK_ACK_RECEIPT || op == FOUNDATION_ENGINE_PEEK_INPUT;
        if (scheduler_op && (!header.identity.service_generation ||
            !((active && active->identity == header.identity) ||
              (delivery && delivery->document->identity == header.identity) ||
              (ack && ack->document->identity == header.identity) || (!active && document(header)))))
            return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
        if (header.transfer && op != FOUNDATION_ENGINE_TURN_ENTER && op != FOUNDATION_ENGINE_TURN_LEAVE &&
            op != FOUNDATION_ENGINE_DELIVERY_RESULT && op != FOUNDATION_ENGINE_ACK_RECEIPT_RESULT &&
            op != FOUNDATION_ENGINE_RETIRED_DOCUMENT_RESULT && op != FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT &&
            !(physical_profile() && op == FOUNDATION_ENGINE_COMMAND_RESULT) &&
            !(document_selected() && (op == FOUNDATION_ENGINE_DOCUMENT_WORK_RESULT || op == FOUNDATION_ENGINE_BEGIN_DOCUMENT_WORK)) &&
            !(editor_selected() && (op == FOUNDATION_ENGINE_EDITOR_WORK_RESULT || op == FOUNDATION_ENGINE_BEGIN_EDITOR_WORK)))
            return result(FOUNDATION_ENGINE_INVALID, ServiceStatus::invalid_request);
        switch (op) {
        case FOUNDATION_ENGINE_CONFIGURE:
            if (!payload.empty() || header.identity.document_sequence || header.identity.service_generation || header.transfer || depth)
                return result(FOUNDATION_ENGINE_INVALID, ServiceStatus::invalid_request);
            if (document_selected()) {
                std::lock_guard lock(document_admission_gate);
                if (document_terminal()) return result(FOUNDATION_ENGINE_CLOSED, ServiceStatus::closed);
                return result(FOUNDATION_ENGINE_OK, initialize());
            }
            return result(FOUNDATION_ENGINE_OK, initialize());
        case FOUNDATION_ENGINE_TURN_ENTER: {
            if (!payload.empty() || pumping || depth == turns.size()) return unavailable();
            if ((physical_profile() && input_poisoned) || document_poisoned || document_terminal()) return unavailable();
            const bool prospective_resource = !header.identity.service_generation &&
                std::any_of(resources.begin(), resources.end(), [&](const auto& item) {
                    return !item.second.retired && item.second.identity.worker_epoch == header.identity.worker_epoch &&
                        item.second.identity.application_instance == header.identity.application_instance &&
                        item.second.identity.document_sequence == header.identity.document_sequence &&
                        !item.second.identity.service_generation;
                });
            if (depth) {
                if (header.transfer != turns[0].transfer) return unavailable();
                if (header.identity != turns[depth - 1].identity && (!active || header.identity != active->identity))
                    return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
            } else if (delivery) {
                if (delivery->frozen || header.transfer != delivery->transfer || header.identity != delivery->document->identity) return unavailable();
            } else if (ack) {
                if (!ack->applied || ack->frozen || header.transfer != ack->transfer || header.identity != ack->document->identity) return unavailable();
            } else if (terminal) return unavailable();
            else if (retirement) {
                if (header.transfer != retirement->transfer || header.identity != retirement->identity) return unavailable();
            } else if (input) {
                if (!input->exposed || input->entered || header.transfer != input->transfer || header.identity != input->target ||
                    (effect && !input->retiring)) return unavailable();
            } else if (auto* slot = document_slot(header)) {
                if (engine_document_ack_kind(slot->dispatch.work.kind) || !slot->exposed || !slot->claimed ||
                    slot->entered || slot->completed) return unavailable();
            } else if (auto* slot = editor_slot(header)) {
                if (!slot->exposed || !slot->claimed || slot->entered || slot->completed || slot->result_fault ||
                    ((effect || close_requested) && slot->dispatch.work.kind != EngineEditorWorkKind::revoke)) return unavailable();
            } else if (document_barrier()) return unavailable();
            else if (effect) return unavailable();
            else if (header.transfer || (!initial_turn &&
                !((active && active->identity == header.identity) ||
                  prospective_resource || (!active && !header.identity.document_sequence && !header.identity.service_generation))))
                return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
            if (!depth && input && header.transfer == input->transfer && header.identity == input->target) input->entered = true;
            if (!depth) if (auto* slot = document_slot(header)) slot->entered = true;
            if (!depth) if (auto* slot = editor_slot(header)) slot->entered = true;
            turns[depth++] = header;
            return result(FOUNDATION_ENGINE_OK);
        }
        case FOUNDATION_ENGINE_TURN_LEAVE:
            if (!payload.empty() || !depth || turns[depth - 1].identity != header.identity || turns[depth - 1].transfer != header.transfer)
                return result(FOUNDATION_ENGINE_CONFLICT, ServiceStatus::unavailable);
            --depth;
            if (!depth) if (auto* slot = document_slot(header)) slot->returned = true;
            if (!depth) if (auto* slot = editor_slot(header)) slot->returned = true;
            if (!depth && close_requested) finish_close();
            return result(FOUNDATION_ENGINE_OK);
        case FOUNDATION_ENGINE_BEGIN_DOCUMENT: {
            const bool document_navigation = !document_ack && !input && !delivery && !ack && !terminal && !retirement &&
                ((document_work && (!document_work->claimed || document_work->completed || (document_work->entered && depth &&
                    turns[0].transfer == document_work->dispatch.transfer))) || (!document_work && document_reservation));
            const bool editor_navigation = !document_work && !document_ack && !input && !delivery && !ack && !terminal && !retirement &&
                ((editor_work && (!editor_work->claimed || editor_work->completed || (editor_work->entered && depth &&
                    turns[0].transfer == editor_work->dispatch.transfer))) || (!editor_work && editor_reservation));
            if (!payload.empty() || pumping || (barrier() && !retired_page_transactions_only() &&
                !(input && (!input->entered || (depth && turns[0].transfer == input->transfer)) &&
                  !delivery && !ack && !terminal && !retirement) && !document_navigation && !editor_navigation)) return unavailable();
            if (adoption) current.application_instance = header.identity.application_instance;
            return result(begin(header, response));
        }
        case FOUNDATION_ENGINE_CLOSE_DOCUMENT: {
            if (!payload.empty() || pumping) return unavailable();
            auto* value = document(header);
            if (!value) return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
            const auto retired = std::count_if(documents.begin(), documents.end(),
                [](const auto& item) { return item.second->retired; });
            if (!value->retired && retired >= 8 && (config.abandon_closed_document_outcomes || value->services->retained_call_count()))
                return result(FOUNDATION_ENGINE_LIMIT, ServiceStatus::limit_exceeded);
            retire(*value); prune(); return result(FOUNDATION_ENGINE_OK);
        }
        case FOUNDATION_ENGINE_SUBMIT: {
            auto* value = document(header);
            if (pumping) return unavailable();
            if (value->retired) return result(FOUNDATION_ENGINE_CLOSED, ServiceStatus::closed);
            Envelope envelope; Span ignored;
            if (decode_envelope(payload, envelope, ignored) != CodecStatus::ok || envelope.generation != header.identity.service_generation)
                return result(FOUNDATION_ENGINE_INVALID, ServiceStatus::invalid_request);
            if (ack && ack->document == value && envelope.sequence <= ack->through)
                return result(FOUNDATION_ENGINE_CONFLICT, ServiceStatus::conflict);
            const auto [position, inserted] = value->accepted.emplace(envelope.sequence, false);
            const auto status = value->services->submit(payload, static_cast<WebServiceSource>(header.source));
            if (status != ServiceStatus::ok) { if (inserted) value->accepted.erase(position); }
            else { position->second = false; value->highest = std::max(value->highest, envelope.sequence); }
            return result(FOUNDATION_ENGINE_OK, status);
        }
        case FOUNDATION_ENGINE_CANCEL:
            if (payload.size() != 8 || pumping) return unavailable();
            if (document(header)->retired) return result(FOUNDATION_ENGINE_CLOSED, ServiceStatus::closed);
            return result(FOUNDATION_ENGINE_OK, document(header)->services->cancel(header.identity.service_generation, get(payload, 0, 8)));
        case FOUNDATION_ENGINE_STAGE_ACK: {
            if (payload.size() != 8 || pumping) return unavailable();
            auto* value = document(header); const auto through = get(payload, 0, 8);
            if (!through || through > value->highest) return result(FOUNDATION_ENGINE_INVALID, ServiceStatus::invalid_request);
            if (ack) {
                if (ack->document == value && ack->through == through)
                    return result(FOUNDATION_ENGINE_OK, ack->applied ? ack->status : ServiceStatus::unavailable);
                return unavailable();
            }
            if (value->retired && config.abandon_closed_document_outcomes)
                return result(FOUNDATION_ENGINE_CLOSED, ServiceStatus::closed);
            for (const auto& [sequence, accepted] : value->accepted)
                if (sequence <= through && !accepted &&
                    (!delivery || delivery->document != value || delivery->sequence != sequence))
                    return result(FOUNDATION_ENGINE_CONFLICT, ServiceStatus::conflict);
            const auto value_transfer = transfer();
            if (!value_transfer) return result(FOUNDATION_ENGINE_LIMIT, ServiceStatus::limit_exceeded);
            ack.emplace(Ack{value, through, *value_transfer});
            return result(FOUNDATION_ENGINE_OK, ServiceStatus::unavailable);
        }
        case FOUNDATION_ENGINE_PUMP_ONE: {
            if (document_terminal()) return result(FOUNDATION_ENGINE_CLOSED, ServiceStatus::closed);
            if (!payload.empty() || blocked() || delivery || terminal || retirement) return unavailable();
            if ((input && input->entered) || document_attempt()) return unavailable();
            pumping = true;
            struct Guard { Impl& self; ~Guard() { self.pumping = false; if (self.close_requested) self.finish_close(); } } guard{*this};
            if (ack) {
                if (ack->applied) return unavailable();
                for (const auto& [sequence, accepted] : ack->document->accepted)
                    if (sequence <= ack->through && !accepted) return unavailable();
                // The immutable fixed receipt already has storage before ACK.
                ack->status = ack->document->services->acknowledge(ack->document->identity.service_generation, ack->through);
                ack->applied = true;
                if (ack->status == ServiceStatus::ok) {
                    auto& accepted = ack->document->accepted;
                    accepted.erase(accepted.begin(), accepted.upper_bound(ack->through));
                }
                return result(FOUNDATION_ENGINE_OK, ack->status);
            }
            if (!collect()) return result(FOUNDATION_ENGINE_LIMIT, ServiceStatus::limit_exceeded);
            if (delivery) return result(FOUNDATION_ENGINE_OK);
            if (!next_transfer) return result(FOUNDATION_ENGINE_LIMIT, ServiceStatus::limit_exceeded);
            ServiceStatus status = ServiceStatus::ok;
            for (auto& [sequence, value] : documents) {
                (void)sequence;
                if (value->retired) continue;
                if ((physical_profile() || document_selected()) && value->services->has_queued_calls()) {
                    if (!effect) {
                        const auto first = std::find_if(value->accepted.begin(), value->accepted.end(),
                            [](const auto& call) { return !call.second; });
                        const auto ticket = native_effect_sequences.next();
                        if (!ticket || first == value->accepted.end()) {
                            input_poisoned = true;
                            poison_document();
                            return result(FOUNDATION_ENGINE_INTERNAL, ServiceStatus::uncertain);
                        }
                        cancel_input();
                        cancel_document_work(document_work);
                        if (editor_work && editor_work->dispatch.work.kind != EngineEditorWorkKind::revoke) cancel_editor_work();
                        if (document_reservation && document_reservation_target == value->identity)
                            (void)cancel_document_sequence(*document_reservation);
                        if (editor_reservation && editor_reservation_target == value->identity)
                            (void)cancel_editor_sequence(*editor_reservation);
                        effect.emplace(NativeEffect{{*ticket, value->identity, input_state.active_context, false}, first->first});
                    }
                    if (effect->value.target != value->identity || effect->value.entered || !effect->acknowledged ||
                        input_state.active_context || input || document_barrier() || editor_retirement) return unavailable();
                    effect->value.entered = true;
                    status = value->services->pump(1);
                    if (!collect()) return result(FOUNDATION_ENGINE_LIMIT, ServiceStatus::limit_exceeded);
                    if (effect && effect->value.entered && !effect->completed) {
                        // Only this newly completed generation/sequence may
                        // resume input, never an unrelated or empty pump.
                        effect->uncertain = true;
                        input_poisoned = true;
                        poison_document();
                        return result(FOUNDATION_ENGINE_INTERNAL, ServiceStatus::uncertain);
                    }
                    if (effect && effect->uncertain) return result(FOUNDATION_ENGINE_INTERNAL, ServiceStatus::uncertain);
                } else {
                    if (input || document_barrier() || ((physical_profile() || document_selected()) && effect)) return unavailable();
                    status = value->services->pump(1);
                }
                break;
            }
            if (!collect()) return result(FOUNDATION_ENGINE_LIMIT, ServiceStatus::limit_exceeded);
            return result(FOUNDATION_ENGINE_OK, status);
        }
        case FOUNDATION_ENGINE_PEEK_DELIVERY:
            if (!payload.empty() || blocked()) return unavailable();
            if (!delivery) return result(FOUNDATION_ENGINE_EMPTY, ServiceStatus::unavailable);
            response = document_header(*delivery->document, delivery->transfer);
            return result(FOUNDATION_ENGINE_OK, ServiceStatus::ok, delivery->bytes);
        case FOUNDATION_ENGINE_PEEK_ACK_RECEIPT: {
            if (!payload.empty() || blocked()) return unavailable();
            if (!ack || !ack->applied) return result(FOUNDATION_ENGINE_EMPTY, ServiceStatus::unavailable);
            response = document_header(*ack->document, ack->transfer);
            std::array<std::uint8_t, 12> body{};
            put(body, 0, ack->through, 8); put(body, 8, static_cast<std::uint32_t>(ack->status), 4);
            return result(FOUNDATION_ENGINE_OK, ack->status, body);
        }
        case FOUNDATION_ENGINE_DELIVERY_RESULT:
        case FOUNDATION_ENGINE_ACK_RECEIPT_RESULT: {
            if (payload.size() != 4 || blocked()) return unavailable();
            const auto disposition = get(payload, 0, 4);
            if (disposition < FOUNDATION_ENGINE_ACCEPTED || disposition > FOUNDATION_ENGINE_RETRY)
                return result(FOUNDATION_ENGINE_INVALID, ServiceStatus::invalid_request);
            if (op == FOUNDATION_ENGINE_DELIVERY_RESULT) {
                if (!delivery || header.transfer != delivery->transfer || header.identity != delivery->document->identity)
                    return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
                if (disposition == FOUNDATION_ENGINE_ACCEPTED) {
                    delivery->document->accepted.at(delivery->sequence) = true; delivery.reset();
                } else delivery->frozen = disposition == FOUNDATION_ENGINE_REJECTED;
            } else {
                if (!ack || !ack->applied || header.transfer != ack->transfer || header.identity != ack->document->identity)
                    return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
                if (disposition == FOUNDATION_ENGINE_ACCEPTED) ack.reset();
                else ack->frozen = disposition == FOUNDATION_ENGINE_REJECTED;
            }
            prune(); return result(FOUNDATION_ENGINE_OK);
        }
        case FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT: {
            if (!config.abandon_closed_document_outcomes)
                return result(FOUNDATION_ENGINE_UNSUPPORTED, ServiceStatus::unavailable);
            if (!payload.empty() || blocked()) return unavailable();
            if (!metadata_identity(header)) return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
            if (input || document_attempt()) return result(FOUNDATION_ENGINE_EMPTY, ServiceStatus::unavailable);
            auto return_terminal = [&] {
                response = {terminal->identity, terminal->transfer, 0};
                return result(FOUNDATION_ENGINE_OK, ServiceStatus::ok, terminal->bytes);
            };
            if (terminal) return return_terminal();
            if (retirement || (delivery && !delivery->document->retired) || (ack && !ack->document->retired))
                return result(FOUNDATION_ENGINE_EMPTY, ServiceStatus::unavailable);
            // A retired page's unapplied ACK is only an intent. Its close has
            // revoked it even if its prefix was already retired previously.
            if (ack && !ack->applied) ack.reset();
            if (!next_transfer) return result(FOUNDATION_ENGINE_LIMIT, ServiceStatus::limit_exceeded);
            if (ack && ack->applied) {
                constexpr std::size_t bytes = receipt_bytes + 12;
                if (output.size() < receipt_bytes + bytes) return FOUNDATION_ENGINE_REPLY_TOO_SMALL;
                Bytes owned;
                try { owned.resize(bytes); }
                catch (const std::bad_alloc&) { return result(FOUNDATION_ENGINE_LIMIT, ServiceStatus::limit_exceeded); }
                std::array<std::uint8_t, 12> body{};
                put(body, 0, ack->through, 8); put(body, 8, static_cast<std::uint32_t>(ack->status), 4);
                reply(FOUNDATION_ENGINE_PEEK_ACK_RECEIPT, document_header(*ack->document, ack->transfer),
                    owned, FOUNDATION_ENGINE_OK, ack->status, body);
                terminal.emplace(TerminalOutcome{ack->document->identity, *transfer(), ack->through, true, std::move(owned)});
                ack.reset();
                return return_terminal();
            }
            for (auto& [document_sequence, value] : documents) {
                (void)document_sequence;
                if (!value->retired) continue;
                std::uint64_t sequence{}; std::uint32_t written{};
                const auto status = value->services->copy_closed_completion(output.subspan(receipt_bytes), sequence, written);
                if (status == ServiceStatus::not_found) continue;
                if (status == ServiceStatus::limit_exceeded) return FOUNDATION_ENGINE_REPLY_TOO_SMALL;
                if (status != ServiceStatus::ok) return result(FOUNDATION_ENGINE_CONFLICT, status);
                // The closed queue still owns every original outcome, including
                // a pending transport delivery. Audit its lowest actual prefix
                // first; abandoning a later delivery must not erase an earlier
                // already-delivered but unacknowledged result without copying it.
                delivery.reset();
                Bytes owned;
                try { owned.assign(output.begin() + receipt_bytes, output.begin() + receipt_bytes + written); }
                catch (const std::bad_alloc&) { return result(FOUNDATION_ENGINE_LIMIT, ServiceStatus::limit_exceeded); }
                terminal.emplace(TerminalOutcome{value->identity, *transfer(), sequence, false, std::move(owned)});
                return return_terminal();
            }
            return result(FOUNDATION_ENGINE_EMPTY, ServiceStatus::unavailable);
        }
        case FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT: {
            if (!config.abandon_closed_document_outcomes)
                return result(FOUNDATION_ENGINE_UNSUPPORTED, ServiceStatus::unavailable);
            if (payload.size() != 4 || blocked()) return unavailable();
            if (get(payload, 0, 4) != FOUNDATION_ENGINE_ABANDONED)
                return result(FOUNDATION_ENGINE_INVALID, ServiceStatus::invalid_request);
            if (last_abandoned && last_abandoned->identity == header.identity && last_abandoned->transfer == header.transfer)
                return result(FOUNDATION_ENGINE_OK);
            if (!terminal || terminal->identity != header.identity || terminal->transfer != header.transfer)
                return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
            if (!terminal->ack_receipt) {
                auto* value = document(header);
                if (!value || !value->retired) return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
                const auto status = value->services->acknowledge(header.identity.service_generation, terminal->sequence);
                if (status != ServiceStatus::ok) return result(FOUNDATION_ENGINE_CONFLICT, status);
                value->accepted.erase(value->accepted.begin(), value->accepted.upper_bound(terminal->sequence));
            }
            last_abandoned = RetiredTransfer{terminal->identity, terminal->transfer};
            terminal.reset(); prune();
            if (close_requested) finish_close();
            return result(FOUNDATION_ENGINE_OK);
        }
        case FOUNDATION_ENGINE_PEEK_RETIRED_DOCUMENT: {
            if (!config.abandon_closed_document_outcomes)
                return result(FOUNDATION_ENGINE_UNSUPPORTED, ServiceStatus::unavailable);
            if (!payload.empty() || blocked()) return unavailable();
            if (!metadata_identity(header)) return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
            if (!retirement) {
                if (delivery || ack || terminal || input || document_attempt()) return result(FOUNDATION_ENGINE_EMPTY, ServiceStatus::unavailable);
                for (const auto& [sequence, value] : documents) {
                    (void)sequence;
                    if (!value->retired || active == value.get() || !value->services->closed() ||
                        value->services->retained_call_count() || !value->accepted.empty() || document_holds(value->identity)) continue;
                    const auto issued = transfer();
                    if (!issued) return result(FOUNDATION_ENGINE_LIMIT, ServiceStatus::limit_exceeded);
                    retirement.emplace(RetiredTransfer{value->identity, *issued});
                    break;
                }
            }
            if (!retirement) return result(FOUNDATION_ENGINE_EMPTY, ServiceStatus::unavailable);
            response = {retirement->identity, retirement->transfer, 0};
            return result(FOUNDATION_ENGINE_OK);
        }
        case FOUNDATION_ENGINE_RETIRED_DOCUMENT_RESULT: {
            if (!config.abandon_closed_document_outcomes)
                return result(FOUNDATION_ENGINE_UNSUPPORTED, ServiceStatus::unavailable);
            if (payload.size() != 4 || blocked()) return unavailable();
            if (get(payload, 0, 4) != FOUNDATION_ENGINE_ACCEPTED)
                return result(FOUNDATION_ENGINE_INVALID, ServiceStatus::invalid_request);
            if (last_retirement && last_retirement->identity == header.identity && last_retirement->transfer == header.transfer)
                return result(FOUNDATION_ENGINE_OK);
            if (!retirement || retirement->identity != header.identity || retirement->transfer != header.transfer)
                return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
            const auto found = documents.find(header.identity.document_sequence);
            if (found == documents.end() || found->second->identity != header.identity || !found->second->retired ||
                found->second->services->retained_call_count() || document_holds(found->second->identity))
                return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
            last_retirement = retirement;
            retirement.reset(); documents.erase(found);
            if (close_requested) finish_close();
            return result(FOUNDATION_ENGINE_OK);
        }
        case FOUNDATION_ENGINE_BEGIN_RESOURCE_EPOCH: {
            if (!payload.empty() || pumping || !header.identity.application_instance || !header.identity.document_sequence ||
                header.identity.service_generation || header.identity.document_sequence < highest_document)
                return result(FOUNDATION_ENGINE_INVALID, ServiceStatus::invalid_request);
            if (output.size() < receipt_bytes + 8) return FOUNDATION_ENGINE_REPLY_TOO_SMALL;
            prune();
            if (resources.size() >= 2) return result(FOUNDATION_ENGINE_LIMIT, ServiceStatus::limit_exceeded);
            const auto epoch = resource_epochs.next();
            if (!epoch) return result(FOUNDATION_ENGINE_LIMIT, ServiceStatus::limit_exceeded);
            resources.emplace(*epoch, ResourceContext{header.identity});
            if (adoption) current.application_instance = header.identity.application_instance;
            std::array<std::uint8_t, 8> body{}; put(body, 0, *epoch, 8);
            return result(FOUNDATION_ENGINE_OK, ServiceStatus::ok, body);
        }
        case FOUNDATION_ENGINE_RETIRE_RESOURCE_EPOCH: {
            if (payload.size() != 8 || pumping) return unavailable();
            const auto found = resources.find(get(payload, 0, 8));
            if (found == resources.end() || !valid_resource_identity(header, found->second))
                return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
            found->second.retired = true; prune(); return result(FOUNDATION_ENGINE_OK);
        }
        case FOUNDATION_ENGINE_RESOURCE_RESOLVE: {
            if (payload.size() < 16 || get(payload, 12, 4) != payload.size() - 16 || get(payload, 12, 4) > 4096 || pumping)
                return result(FOUNDATION_ENGINE_INVALID, ServiceStatus::invalid_request);
            // Reserve the largest metadata response before issuing a lease.
            if (output.size() < receipt_bytes + 32 + 127) return FOUNDATION_ENGINE_REPLY_TOO_SMALL;
            const auto found = resources.find(get(payload, 0, 8));
            std::uint32_t http = 410;
            const PackageFile* file = nullptr;
            std::uint64_t lease{}, body_bytes{}, content_length{};
            std::string_view mime = "text/plain";
            if (found != resources.end() && valid_resource_identity(header, found->second) && !found->second.retired) {
                const auto method = get(payload, 8, 4);
                if (method > 1) http = 405;
                else {
                    const std::string_view url(reinterpret_cast<const char*>(payload.data() + 16), payload.size() - 16);
                    const auto normalized = normalize_app_resource_url(url, package.package_sha256);
                    if (!normalized) http = 403;
                    else {
                        file = package.find_file(normalized.path);
                        if (!file || file->component != "web") http = 404;
                        else if (file->data.size() > max_appended_file_bytes) http = 413;
                        else if (file->media_type.empty() || file->media_type.size() > 127) http = 500;
                        else {
                            body_bytes = method ? 0 : file->data.size(); content_length = file->data.size();
                            if (leases.size() >= 64 || body_bytes > max_resource_bytes - retained_resource_bytes) http = 503;
                            else if (const auto value = resource_leases.next()) {
                                leases.emplace(*value, ResourceLease{file, found->first, body_bytes});
                                ++found->second.leases; retained_resource_bytes += body_bytes;
                                lease = *value; mime = file->media_type; http = 200;
                            } else http = 503;
                        }
                    }
                }
            }
            if (http != 200) { body_bytes = 0; content_length = 0; }
            std::array<std::uint8_t, 159> body{};
            put(body, 0, http, 4); put(body, 4, mime.size(), 4); put(body, 8, body_bytes, 8);
            put(body, 16, content_length, 8); put(body, 24, lease, 8);
            std::copy(mime.begin(), mime.end(), body.begin() + 32);
            return result(FOUNDATION_ENGINE_OK, ServiceStatus::ok, Span(body).first(32 + mime.size()));
        }
        case FOUNDATION_ENGINE_RESOURCE_READ: {
            if (payload.size() != 20 || pumping) return unavailable();
            const auto count = get(payload, 16, 4), offset = get(payload, 8, 8);
            if (count > FOUNDATION_ENGINE_MAX_BODY_BYTES || output.size() < receipt_bytes + count)
                return count > FOUNDATION_ENGINE_MAX_BODY_BYTES ? result(FOUNDATION_ENGINE_LIMIT, ServiceStatus::limit_exceeded) : FOUNDATION_ENGINE_REPLY_TOO_SMALL;
            const auto found = leases.find(get(payload, 0, 8));
            if (found == leases.end()) return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
            const auto resource = resources.find(found->second.epoch);
            if (resource == resources.end() || !valid_resource_identity(header, resource->second) ||
                offset > found->second.body_bytes || count > found->second.body_bytes - offset)
                return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
            return result(FOUNDATION_ENGINE_OK, ServiceStatus::ok,
                Span(found->second.file->data).subspan(static_cast<std::size_t>(offset), static_cast<std::size_t>(count)));
        }
        case FOUNDATION_ENGINE_RESOURCE_RELEASE: {
            if (payload.size() != 8 || pumping) return unavailable();
            const auto found = leases.find(get(payload, 0, 8));
            if (found == leases.end()) return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
            const auto resource = resources.find(found->second.epoch);
            if (resource == resources.end() || !valid_resource_identity(header, resource->second))
                return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
            retained_resource_bytes -= found->second.body_bytes; --resource->second.leases;
            leases.erase(found); prune();
            if (close_requested && !blocked()) finish_close();
            return result(FOUNDATION_ENGINE_OK);
        }
        case FOUNDATION_ENGINE_FRAME_COMMIT: {
            if (payload.size() < 48 || pumping || !active || header.identity != active->identity)
                return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
            const auto format = get(payload, 0, 4), width = get(payload, 4, 4), height = get(payload, 8, 4), stride = get(payload, 12, 4);
            const auto x = get(payload, 16, 4), y = get(payload, 20, 4), rw = get(payload, 24, 4), rh = get(payload, 28, 4);
            const auto base = get(payload, 32, 8), revision = get(payload, 40, 8);
            if (format != 1 || width != 800 || height != 600 || !rw || !rh || x > width || rw > width - x || y > height || rh > height - y ||
                stride != rw * 4 || stride * rh != payload.size() - 48 || !revision || base == std::numeric_limits<std::uint64_t>::max() || revision != base + 1)
                return result(FOUNDATION_ENGINE_INVALID, ServiceStatus::invalid_request);
            if ((!frame && (base || x || y || rw != width || rh != height)) ||
                (frame && (frame->identity != header.identity || base != frame->frame_revision)))
                return result(FOUNDATION_ENGINE_CONFLICT, ServiceStatus::conflict);
            const auto pixels = payload.subspan(48);
            for (std::size_t i = 3; i < pixels.size(); i += 4)
                if (pixels[i] != 255) return result(FOUNDATION_ENGINE_UNSUPPORTED, ServiceStatus::unavailable);
            if (!frame) {
                EngineFrame initial{header.identity, static_cast<std::uint32_t>(width), static_cast<std::uint32_t>(height),
                    static_cast<std::uint32_t>(width * 4), revision, Bytes(static_cast<std::size_t>(width * height * 4))};
                frame.emplace(std::move(initial));
            }
            for (std::size_t row = 0; row < rh; ++row)
                std::copy_n(pixels.begin() + static_cast<std::ptrdiff_t>(row * stride), static_cast<std::size_t>(stride),
                    frame->rgba.begin() + static_cast<std::ptrdiff_t>((y + row) * width * 4 + x * 4));
            frame->frame_revision = revision;
            return result(FOUNDATION_ENGINE_OK);
        }
        case FOUNDATION_ENGINE_PEEK_INPUT:
            if (document_terminal()) return result(FOUNDATION_ENGINE_CLOSED, ServiceStatus::closed);
            if (!payload.empty() || blocked()) return unavailable();
            if (physical_profile() && active && header.identity != active->identity)
                return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
            if (!physical_profile() || !active || !input || input->entered || delivery || ack || terminal || retirement || document_entry_barrier() ||
                (effect && !input->retiring)) return result(FOUNDATION_ENGINE_EMPTY, ServiceStatus::unavailable);
            if (output.size() < receipt_bytes + input->bytes.size()) return FOUNDATION_ENGINE_REPLY_TOO_SMALL;
            response = {input->target, input->transfer, 0};
            input->exposed = true;
            return result(FOUNDATION_ENGINE_OK, ServiceStatus::ok, input->bytes);
        case FOUNDATION_ENGINE_COMMAND_RESULT: {
            if (!physical_profile()) return result(FOUNDATION_ENGINE_UNSUPPORTED, ServiceStatus::unavailable);
            if (output.size() < receipt_bytes + engine_input::kCommandResultBytes) return FOUNDATION_ENGINE_REPLY_TOO_SMALL;
            if (blocked()) return unavailable();
            engine_input::CommandResult completed;
            if (engine_input::decode_command_result(payload, completed) != engine_input::Status::ok)
                return result(FOUNDATION_ENGINE_INVALID, ServiceStatus::invalid_request);
            if (input_outcome && input_outcome->has_result && input_outcome->target == header.identity &&
                input_outcome->transfer == header.transfer && input_outcome->ticket == completed.request_sequence) {
                if (!std::equal(payload.begin(), payload.end(), input_outcome->bytes.begin()))
                    return result(FOUNDATION_ENGINE_CONFLICT, ServiceStatus::conflict);
                return result(FOUNDATION_ENGINE_OK);
            }
            if (!input || !input->entered || input->target != header.identity || input->transfer != header.transfer ||
                input->ticket != completed.request_sequence) return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
            const auto disposition = completed.disposition == 1 ? EngineInputCommandStatus::consumed :
                completed.disposition == 0 ? EngineInputCommandStatus::rejected : EngineInputCommandStatus::unknown;
            InputOutcome outcome{input->target, input->transfer, input->ticket,
                {disposition, completed.provider_status, completed.handled != 0}, {}, true};
            const bool stale_old_target = completed.disposition == 0 && completed.provider_status == -5 &&
                (!active || active->identity != input->target);
            std::copy(payload.begin(), payload.end(), outcome.bytes.begin());
            if (completed.disposition == 1) {
                input_state.highest_context = std::max(input_state.highest_context, input->next_state.highest_context);
                input_state.highest_capture_token = std::max(input_state.highest_capture_token, input->next_state.highest_capture_token);
                if (active && active->identity == input->target && !close_requested) {
                    input_state = input->next_state;
                    input_target = input_state.active_context ? input->target : EngineIdentity{};
                }
            } else if (!stale_old_target) {
                // Rejected commands are proven not entered but never replayed.
                // A catalog/context disagreement closes this input route.
                input_poisoned = true;
                engine_input::retire_document(input_state);
                input_target = {};
            }
            input_outcome = outcome;
            input.reset();
            if (completed.disposition == 2) poison_document();
            if (completed.disposition != 1 && !stale_old_target) request_close();
            if (close_requested) finish_close();
            return result(FOUNDATION_ENGINE_OK);
        }
        case FOUNDATION_ENGINE_PEEK_DOCUMENT_WORK: {
            if (!payload.empty() || blocked()) return unavailable();
            if (document_poisoned || document_terminal() || failed) return result(FOUNDATION_ENGINE_CLOSED, ServiceStatus::closed);
            if (!metadata_identity(header)) return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
            if (delivery || ack || terminal || retirement || input) return result(FOUNDATION_ENGINE_EMPTY, ServiceStatus::unavailable);
            const bool service_pending = std::any_of(documents.begin(), documents.end(), [](const auto& item) {
                return !item.second->retired && std::any_of(item.second->accepted.begin(), item.second->accepted.end(),
                    [](const auto& call) { return !call.second; });
            });
            auto* slot = document_ack && !document_ack->completed && !document_ack->claimed ? &*document_ack :
                document_work && !document_work->completed && !document_work->claimed ? &*document_work : nullptr;
            if (service_pending && (!slot || !engine_document_ack_kind(slot->dispatch.work.kind)))
                return result(FOUNDATION_ENGINE_EMPTY, ServiceStatus::unavailable);
            if (!slot) return result(FOUNDATION_ENGINE_EMPTY,
                document_barrier() || effect || close_requested || is_closed ? ServiceStatus::unavailable : ServiceStatus::ok);
            if (effect && !engine_document_ack_kind(slot->dispatch.work.kind))
                return result(FOUNDATION_ENGINE_EMPTY, ServiceStatus::unavailable);
            if (output.size() < receipt_bytes + slot->encoded.size()) return FOUNDATION_ENGINE_REPLY_TOO_SMALL;
            response = {engine_target(slot->dispatch.work.target), slot->dispatch.transfer, 0};
            slot->exposed = true;
            return result(FOUNDATION_ENGINE_OK, ServiceStatus::ok, slot->encoded);
        }
        case FOUNDATION_ENGINE_BEGIN_DOCUMENT_WORK: {
            if (payload.size() != FOUNDATION_ENGINE_DOCUMENT_BEGIN_BYTES || get(payload, 4, 4))
                return result(FOUNDATION_ENGINE_INVALID, ServiceStatus::invalid_request);
            if (blocked() || delivery || ack || terminal || retirement || input || document_poisoned || document_terminal() || failed) return unavailable();
            auto* slot = document_slot(header);
            if (!slot || slot->dispatch.work.kind != static_cast<EngineDocumentWorkKind>(get(payload, 0, 4)) ||
                slot->dispatch.work.request_sequence != get(payload, 8, 8))
                return result(FOUNDATION_ENGINE_STALE, ServiceStatus::invalid_handle);
            if (!slot->exposed || slot->claimed || slot->completed ||
                ((effect || close_requested) && !engine_document_ack_kind(slot->dispatch.work.kind))) return unavailable();
            slot->claimed = true;
            return result(FOUNDATION_ENGINE_OK);
        }
        case FOUNDATION_ENGINE_DOCUMENT_WORK_RESULT: {
            if (blocked()) return unavailable();
            const auto control = settle_document_result(header, payload);
            return result(control, control == FOUNDATION_ENGINE_OK ? ServiceStatus::ok :
                control == FOUNDATION_ENGINE_INVALID ? ServiceStatus::invalid_request : ServiceStatus::unavailable);
        }
        case FOUNDATION_ENGINE_PEEK_EDITOR_WORK: {
            if (!payload.empty() || blocked()) return unavailable();
            if (document_poisoned || document_terminal() || failed) return result(FOUNDATION_ENGINE_CLOSED,ServiceStatus::closed);
            if (!metadata_identity(header)) return result(FOUNDATION_ENGINE_STALE,ServiceStatus::invalid_handle);
            if (delivery || ack || terminal || retirement || input || document_work || document_ack || document_reservation)
                return result(FOUNDATION_ENGINE_EMPTY,ServiceStatus::unavailable);
            auto* slot=editor_work && !editor_work->completed && !editor_work->claimed ? &*editor_work : nullptr;
            const bool retiring=slot && slot->dispatch.work.kind==EngineEditorWorkKind::revoke;
            const bool service_pending=std::any_of(documents.begin(),documents.end(),[](const auto& item) {
                return !item.second->retired && std::any_of(item.second->accepted.begin(),item.second->accepted.end(),
                    [](const auto& call) { return !call.second; });
            });
            if (!slot || ((effect || close_requested || service_pending) && !retiring))
                return result(FOUNDATION_ENGINE_EMPTY,document_barrier() || effect || close_requested || is_closed || service_pending ?
                    ServiceStatus::unavailable : ServiceStatus::ok);
            if (effect && (effect->value.entered || effect->acknowledged))
                return result(FOUNDATION_ENGINE_EMPTY,ServiceStatus::unavailable);
            if (output.size()<receipt_bytes+slot->encoded.size()) return FOUNDATION_ENGINE_REPLY_TOO_SMALL;
            response={engine_target(slot->dispatch.work.target),slot->dispatch.transfer,0};
            slot->exposed=true;
            return result(FOUNDATION_ENGINE_OK,ServiceStatus::ok,slot->encoded);
        }
        case FOUNDATION_ENGINE_BEGIN_EDITOR_WORK: {
            if (payload.size()!=FOUNDATION_ENGINE_EDITOR_BEGIN_BYTES || get(payload,4,4))
                return result(FOUNDATION_ENGINE_INVALID,ServiceStatus::invalid_request);
            if (blocked() || delivery || ack || terminal || retirement || input || document_work || document_ack || document_reservation ||
                    document_poisoned || document_terminal() || failed) return unavailable();
            auto* slot=editor_slot(header);
            if (!slot || slot->dispatch.work.kind!=static_cast<EngineEditorWorkKind>(get(payload,0,4)) ||
                    slot->dispatch.work.request_sequence!=get(payload,8,8)) return result(FOUNDATION_ENGINE_STALE,ServiceStatus::invalid_handle);
            if (!slot->exposed || slot->claimed || slot->completed || slot->result_fault ||
                    ((effect || close_requested) && slot->dispatch.work.kind!=EngineEditorWorkKind::revoke)) return unavailable();
            if (effect && (effect->value.entered || effect->acknowledged)) return unavailable();
            slot->claimed=true;
            return result(FOUNDATION_ENGINE_OK);
        }
        case FOUNDATION_ENGINE_EDITOR_WORK_RESULT: {
            if (blocked()) return unavailable();
            const auto control=settle_editor_result(header,payload);
            return result(control,control==FOUNDATION_ENGINE_OK ? ServiceStatus::ok :
                control==FOUNDATION_ENGINE_INVALID ? ServiceStatus::invalid_request : ServiceStatus::unavailable);
        }
        case FOUNDATION_ENGINE_CLOSE:
            if (!payload.empty()) return result(FOUNDATION_ENGINE_INVALID, ServiceStatus::invalid_request);
            if (config.defer_copied_close_to_application && !close_requested && !is_closed)
                return result(FOUNDATION_ENGINE_OK, ServiceStatus::unavailable);
            request_close(); return result(FOUNDATION_ENGINE_OK, is_closed ? ServiceStatus::ok : ServiceStatus::unavailable);
        default: return FOUNDATION_ENGINE_BAD_OPERATION;
        }
    }
};

EngineOwner::EngineOwner(Package package, EngineOwnerConfiguration config)
    : impl_(std::make_unique<Impl>(std::move(package), std::move(config))) {}
EngineOwner::~EngineOwner() {
    if (impl_ && impl_->terminal_document_ownership()) {
        impl_->quarantine();
        (void)impl_.release();
        return;
    }
    close();
}
std::int32_t EngineOwner::dispatch(std::uint32_t op, Span input, std::span<std::uint8_t> output) noexcept {
    if (op < FOUNDATION_ENGINE_CONFIGURE || op > FOUNDATION_ENGINE_BEGIN_EDITOR_WORK ||
        (op >= FOUNDATION_ENGINE_PEEK_DOCUMENT_WORK && op <= FOUNDATION_ENGINE_BEGIN_DOCUMENT_WORK && !impl_->document_selected()) ||
        (op >= FOUNDATION_ENGINE_PEEK_EDITOR_WORK && !impl_->editor_selected())) return FOUNDATION_ENGINE_BAD_OPERATION;
    Header header; Span payload;
    if (!decode(op, input, header, payload)) return FOUNDATION_ENGINE_BAD_RECORD;
    // Spans can alias in a native test or host adapter. Never overwrite a request
    // or a borrowed resource body while producing its receipt.
    if (!input.empty() && !output.empty()) {
        const auto begin = reinterpret_cast<std::uintptr_t>(input.data());
        const auto end = begin + input.size();
        const auto destination = reinterpret_cast<std::uintptr_t>(output.data());
        if (end < begin || destination + output.size() < destination ||
            (destination < end && begin < destination + output.size())) return FOUNDATION_ENGINE_BAD_RECORD;
    }
    try { return impl_->dispatch(op, header, payload, output); }
    catch (...) {
        impl_->failed = true;
        impl_->poison_document();
        impl_->request_close();
        return reply(op, header, output, FOUNDATION_ENGINE_INTERNAL, ServiceStatus::uncertain);
    }
}
const Package& EngineOwner::package() const noexcept { return impl_->package; }
EngineIdentity EngineOwner::identity() const noexcept { return impl_->current; }
std::uint32_t EngineOwner::callback_depth() const noexcept { return impl_->depth; }
bool EngineOwner::configured() const noexcept { return impl_->is_configured; }
bool EngineOwner::closed() const noexcept { return impl_->is_closed; }
bool EngineOwner::has_module() const noexcept { return bool(impl_->module); }
const std::optional<EngineFrame>& EngineOwner::frame() const noexcept { return impl_->frame; }
bool EngineOwner::input_enabled() const noexcept { return impl_->input_enabled(); }
bool EngineOwner::input_suspended() const noexcept { return bool(impl_->effect) || !impl_->input_enabled(); }
std::optional<EngineInputTicket> EngineOwner::stage_command(EngineIdentity target,
    std::uint64_t context, std::uint32_t operation, const engine_input::Digest& schema,
    Bytes payload, bool lifecycle) noexcept {
    try { return impl_->stage_command(target, context, operation, schema, std::move(payload), lifecycle); }
    catch (...) { return {}; }
}
std::optional<EngineInputOutcome> EngineOwner::command_outcome(EngineInputTicket ticket) const noexcept {
    if (!impl_->owner_thread() || !ticket) return {};
    if (impl_->input && impl_->input->ticket == ticket) return EngineInputOutcome{};
    if (impl_->input_outcome && impl_->input_outcome->ticket == ticket) return impl_->input_outcome->value;
    return {};
}
void EngineOwner::cancel_input_context(EngineIdentity target, std::uint64_t context) noexcept {
    if (impl_->owner_thread() && impl_->input && impl_->input->target == target && impl_->input->context == context)
        impl_->cancel_input();
}
std::optional<EngineNativeEffect> EngineOwner::native_effect() const noexcept {
    if (!impl_->owner_thread() || !impl_->effect) return {};
    return impl_->effect->value;
}
bool EngineOwner::acknowledge_native_effect(std::uint64_t ticket) noexcept {
    if (!impl_->owner_thread() || impl_->document_selected() || !impl_->effect || impl_->effect->value.ticket != ticket ||
        impl_->effect->value.entered || impl_->effect->uncertain || impl_->blocked() || impl_->input ||
        impl_->input_state.active_context || impl_->close_requested) return false;
    impl_->effect->acknowledged = true;
    return true;
}
bool EngineOwner::hold_native_effect(std::uint64_t ticket) noexcept {
    if (!impl_->owner_thread() || !impl_->pumping || !impl_->effect || impl_->effect->value.ticket != ticket ||
        !impl_->effect->value.entered || impl_->effect->completed || impl_->effect->uncertain) return false;
    impl_->effect->held = true;
    return true;
}
bool EngineOwner::release_native_effect(std::uint64_t ticket) noexcept {
    if (!impl_->owner_thread() || !impl_->effect || impl_->effect->value.ticket != ticket ||
        !impl_->effect->value.entered || !impl_->effect->held || impl_->effect->uncertain) return false;
    impl_->effect->held = false;
    if (impl_->effect->completed) impl_->effect.reset();
    return true;
}
bool EngineOwner::document_enabled() const noexcept { return impl_->document_enabled(); }
bool EngineOwner::document_actions_enabled() const noexcept {
    return impl_->config.document_actions_profile.enabled && impl_->document_enabled();
}
const engine_document_actions::EngineDocumentActionsProfileFacts& EngineOwner::document_actions_profile() const noexcept {
    return impl_->config.document_actions_profile;
}
const engine_document::EngineDocumentProfileFacts& EngineOwner::document_profile() const noexcept {
    return impl_->config.document_profile;
}
void EngineOwner::notify_document_terminal() noexcept {
    impl_->notify_document_terminal();
}
std::optional<std::uint64_t> EngineOwner::reserve_document_sequence() {
    return impl_->reserve_document_sequence();
}
bool EngineOwner::cancel_document_sequence(std::uint64_t sequence) noexcept {
    return impl_->cancel_document_sequence(sequence);
}
EngineDocumentAdmission EngineOwner::stage_document_work(EngineDocumentWork work) noexcept {
    try { return impl_->stage_document_work(std::move(work)); }
    catch (const std::overflow_error&) { return {EngineDocumentAdmissionCode::exhausted}; }
    catch (const std::bad_alloc&) { return {EngineDocumentAdmissionCode::limit}; }
    catch (...) { return {EngineDocumentAdmissionCode::invalid}; }
}
std::shared_ptr<const EngineDocumentCompletion> EngineOwner::document_outcome(EngineDocumentTicket ticket) const noexcept {
    if (!impl_->owner_thread() || !ticket) return {};
    for (const auto* slot : {&impl_->document_work, &impl_->document_ack})
        if (*slot && (*slot)->dispatch.ticket == ticket)
            return (*slot)->completed ? (*slot)->completion : std::shared_ptr<const EngineDocumentCompletion>{};
    for (const auto& cached : {impl_->document_last_result, impl_->document_last_ack, impl_->document_ack_tombstone})
        if (cached && cached->ticket == ticket) return cached;
    return {};
}
bool EngineOwner::consume_document_outcome(EngineDocumentTicket ticket) noexcept {
    if (!impl_->owner_thread() || !ticket) return false;
    for (auto* slot : {&impl_->document_work, &impl_->document_ack}) {
        if (!*slot || (*slot)->dispatch.ticket != ticket) continue;
        if (!(*slot)->completed || (*slot)->completion->outcome == EngineDocumentOutcome::unknown ||
            (engine_document_action_kind((*slot)->dispatch.work.kind) &&
            (*slot)->completion->outcome == EngineDocumentOutcome::consumed && !(*slot)->action_acknowledged)) return false;
        slot->reset();
        impl_->prune();
        if (impl_->close_requested && !impl_->blocked()) impl_->finish_close();
        return true;
    }
    for (const auto& cached : {impl_->document_last_result, impl_->document_last_ack, impl_->document_ack_tombstone})
        if (cached && cached->ticket == ticket) return true;
    return false;
}
EngineDocumentAdmission EngineOwner::stage_document_action_ack(EngineDocumentTarget target, std::uint64_t sequence) noexcept {
    try { return impl_->stage_document_action_ack(target, sequence); }
    catch (const std::overflow_error&) { return {EngineDocumentAdmissionCode::exhausted}; }
    catch (const std::bad_alloc&) { return {EngineDocumentAdmissionCode::limit}; }
    catch (...) { return {EngineDocumentAdmissionCode::invalid}; }
}
EngineDocumentAdmission EngineOwner::stage_document_body_action_ack(EngineDocumentTarget target, std::uint64_t sequence) noexcept {
    try { return impl_->stage_document_action_ack(target, sequence, EngineDocumentWorkKind::body_action_ack); }
    catch (const std::overflow_error&) { return {EngineDocumentAdmissionCode::exhausted}; }
    catch (const std::bad_alloc&) { return {EngineDocumentAdmissionCode::limit}; }
    catch (...) { return {EngineDocumentAdmissionCode::invalid}; }
}
bool EngineOwner::editor_enabled() const noexcept { return impl_->editor_enabled(); }
const engine_editor::EngineEditorProfileFacts& EngineOwner::editor_profile() const noexcept { return impl_->config.editor_profile; }
std::optional<std::uint64_t> EngineOwner::reserve_editor_sequence() { return impl_->reserve_editor_sequence(); }
bool EngineOwner::cancel_editor_sequence(std::uint64_t sequence) noexcept { return impl_->cancel_editor_sequence(sequence); }
EngineEditorAdmission EngineOwner::stage_editor_work(EngineEditorWork work) noexcept {
    try { return impl_->stage_editor_work(std::move(work)); }
    catch (const std::overflow_error&) { return {EngineEditorAdmissionCode::exhausted}; }
    catch (const std::bad_alloc&) { return {EngineEditorAdmissionCode::limit}; }
    catch (...) { return {EngineEditorAdmissionCode::invalid}; }
}
std::shared_ptr<const EngineEditorCompletion> EngineOwner::editor_outcome(EngineEditorTicket ticket) const noexcept {
    if (!impl_->owner_thread() || !ticket) return {};
    if (impl_->editor_work && impl_->editor_work->dispatch.ticket==ticket)
        return impl_->editor_work->completed ? impl_->editor_work->completion : std::shared_ptr<const EngineEditorCompletion>{};
    return impl_->editor_last_result && impl_->editor_last_result->ticket==ticket ? impl_->editor_last_result :
        std::shared_ptr<const EngineEditorCompletion>{};
}
bool EngineOwner::consume_editor_outcome(EngineEditorTicket ticket) noexcept {
    if (!impl_->owner_thread() || !ticket) return false;
    if (impl_->editor_work && impl_->editor_work->dispatch.ticket==ticket) {
        if (!impl_->editor_work->completed || impl_->editor_work->completion->outcome==EngineEditorOutcome::unknown) return false;
        impl_->editor_last_result=impl_->editor_work->completion;
        impl_->editor_work.reset(); impl_->prune();
        if (impl_->close_requested && !impl_->blocked()) impl_->finish_close();
        return true;
    }
    return impl_->editor_last_result && impl_->editor_last_result->ticket==ticket;
}
bool EngineOwner::acknowledge_document_native_effect(std::uint64_t ticket, EngineDocumentTarget target,
    std::uint64_t publication_revision) noexcept {
    if (!impl_->owner_thread() || !impl_->document_selected() || !impl_->effect ||
        impl_->effect->value.ticket != ticket || impl_->effect->value.target != Impl::engine_target(target) ||
        impl_->effect->value.entered || impl_->effect->uncertain || impl_->blocked() || impl_->barrier() ||
        impl_->input_state.active_context || impl_->editor_retirement || impl_->close_requested || impl_->document_poisoned || impl_->document_terminal() ||
        !publication_revision || publication_revision <= impl_->highest_safe_publication) return false;
    impl_->highest_safe_publication = publication_revision;
    impl_->effect->acknowledged = true;
    return true;
}
EngineStartupPrimary read_engine_startup_primary(const Package& package) {
    return startup_intent(package).primary;
}
EngineStartupPrimary EngineOwner::startup_primary() const noexcept { return impl_->config.startup_primary; }
std::shared_ptr<const EngineModuleView> EngineOwner::binary_view() const noexcept {
    if (!impl_->owner_thread() || impl_->blocked() || !impl_->is_configured || impl_->failed ||
        impl_->close_requested || impl_->is_closed || !impl_->module || !impl_->module->supports_view()) return {};
    return impl_->module->view();
}
std::shared_ptr<const EngineModuleServiceRequest> EngineOwner::begin_binary_view_service() {
    return binary_view() ? impl_->module->begin_view_service() : nullptr;
}
std::shared_ptr<const EngineModuleServiceRequest> EngineOwner::current_binary_view_service() const noexcept {
    return binary_view() ? impl_->module->current_view_service() : nullptr;
}
bool EngineOwner::stage_binary_view_service_result(Span bytes) {
    return binary_view() && !bytes.empty() && bytes.size()<=1024*1024 && impl_->module->stage_view_service_result(bytes);
}
bool EngineOwner::acknowledge_binary_view(std::uint64_t revision) noexcept {
    if (!binary_view() || !revision) return false;
    return impl_->module->acknowledge_view(revision);
}
bool EngineOwner::stage_binary_view_event(std::uint64_t revision,Span bytes) {
    if (!binary_view() || impl_->effect || !revision || bytes.empty() || bytes.size() > 1024*1024) return false;
    return impl_->module->stage_view_event(revision,bytes);
}
void EngineOwner::tick_binary_view() {
    if (!binary_view() || impl_->effect) return;
    impl_->pumping = true;
    struct Guard { Impl& value; ~Guard() { value.pumping=false; if(value.close_requested)value.finish_close(); } } guard{*impl_};
    try { impl_->module->tick_view(); }
    catch (...) { impl_->failed=true; impl_->poison_document(); impl_->request_close(); throw; }
}

void EngineOwner::close() noexcept { if (impl_ && impl_->owner_thread()) impl_->request_close(); }
} // namespace foundation::appended
