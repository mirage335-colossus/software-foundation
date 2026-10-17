#include "native_engine_driver.hpp"
#include "appended_engine_abi.h"
#include "native_editor_codec.hpp"

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstring>
#include <limits>
#include <map>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>

namespace foundation::appended {
namespace {
using Span = std::span<const std::uint8_t>;
using Clock = std::chrono::steady_clock;
namespace editor_codec = foundation::ui::native_editor::codec;
constexpr std::uint64_t pixel_capabilities = 259;
constexpr std::size_t header_bytes = FOUNDATION_ENGINE_HEADER_BYTES;
constexpr std::size_t receipt_bytes = FOUNDATION_ENGINE_RECEIPT_BYTES;
constexpr std::array<std::uint8_t, 32> canonical_header{
    0xa8,0xe8,0x9d,0xa8,0x5d,0x34,0xb2,0x9a,0x4d,0x1b,0xc4,0x54,0x49,0x57,0x91,0xfa,
    0x60,0x4b,0x81,0xe3,0x47,0x7e,0x48,0xce,0x8c,0xa9,0x02,0xe4,0x33,0x3a,0x9c,0x0d};

bool nonzero(const auto& bytes) { return std::any_of(std::begin(bytes), std::end(bytes), [](auto b) { return b != 0; }); }
bool bytes_valid(const BibEngineBytesV1& bytes, std::uint64_t maximum) {
    return !bytes.reserved && bytes.length <= maximum && (!bytes.length || bytes.data) &&
        bytes.length <= std::numeric_limits<std::uintptr_t>::max() - reinterpret_cast<std::uintptr_t>(bytes.data);
}
bool limits_valid(const BibEngineLimitsV1& value) {
    return value.size == sizeof(value) && !value.reserved && value.maximum_command_bytes &&
        value.maximum_query_bytes && value.maximum_reply_bytes &&
        value.maximum_command_bytes <= 16 * 1024 * 1024 && value.maximum_query_bytes <= 16 * 1024 * 1024 &&
        value.maximum_reply_bytes <= 16 * 1024 * 1024 &&
        value.maximum_service_message_bytes >= FOUNDATION_APPENDED_ENVELOPE_BYTES + 320 &&
        value.maximum_service_message_bytes <= FOUNDATION_APPENDED_MAX_MESSAGE_BYTES &&
        value.maximum_retired_documents && value.maximum_retired_documents <= 8 &&
        value.maximum_inflight_resources && value.maximum_inflight_resources <= 64 &&
        value.maximum_resource_response_bytes && value.maximum_resource_response_bytes <= max_appended_file_bytes &&
        value.maximum_retained_resource_bytes >= value.maximum_resource_response_bytes &&
        value.maximum_retained_resource_bytes <= 128ULL * 1024 * 1024;
}
bool within(const BibEngineLimitsV1& selected, const BibEngineLimitsV1& maximum) {
    return selected.maximum_command_bytes <= maximum.maximum_command_bytes &&
        selected.maximum_query_bytes <= maximum.maximum_query_bytes && selected.maximum_reply_bytes <= maximum.maximum_reply_bytes &&
        selected.maximum_service_message_bytes <= maximum.maximum_service_message_bytes &&
        selected.maximum_retired_documents <= maximum.maximum_retired_documents &&
        selected.maximum_inflight_resources <= maximum.maximum_inflight_resources &&
        selected.maximum_resource_response_bytes <= maximum.maximum_resource_response_bytes &&
        selected.maximum_retained_resource_bytes <= maximum.maximum_retained_resource_bytes;
}
bool native_target(const BibEngineBuildV1& build) {
    if (build.pointer_bits != sizeof(void*) * 8) return false;
#if defined(_WIN32) && (defined(_M_X64) || defined(__x86_64__))
    return build.target_system == BIB_ENGINE_TARGET_WINDOWS && build.target_processor == BIB_ENGINE_CPU_X86_64;
#elif defined(__linux__) && defined(__x86_64__)
    return build.target_system == BIB_ENGINE_TARGET_LINUX && build.target_processor == BIB_ENGINE_CPU_X86_64;
#elif defined(__linux__) && defined(__aarch64__)
    return build.target_system == BIB_ENGINE_TARGET_LINUX && build.target_processor == BIB_ENGINE_CPU_AARCH64;
#else
    (void)build; return false;
#endif
}
std::uint64_t read(Span bytes, std::size_t offset, unsigned count) {
    if (offset > bytes.size() || count > bytes.size() - offset) throw std::runtime_error("native owner reply range");
    std::uint64_t result{};
    for (unsigned n = 0; n < count; ++n) result |= std::uint64_t(bytes[offset + n]) << (8 * n);
    return result;
}
void put(std::span<std::uint8_t> bytes, std::size_t offset, std::uint64_t value, unsigned count) {
    if (offset > bytes.size() || count > bytes.size() - offset) throw std::runtime_error("native owner request range");
    for (unsigned n = 0; n < count; ++n) bytes[offset + n] = static_cast<std::uint8_t>(value >> (8 * n));
}
Bytes integer(std::uint64_t value, unsigned count) { Bytes bytes(count); put(bytes, 0, value, count); return bytes; }
BibEngineDocumentV1 document(EngineIdentity value) { return {value.application_instance, value.document_sequence, value.service_generation}; }
bool same(const BibEngineDocumentV1& a, const BibEngineDocumentV1& b) {
    return a.application_instance == b.application_instance && a.document_sequence == b.document_sequence && a.service_generation == b.service_generation;
}
bool provider_status(std::int32_t status) { return status <= 0 && status >= BIB_ENGINE_PROCESS_EXIT_REQUIRED; }
} // namespace

NativeEngineProvider::NativeEngineProvider(BibEngineProviderV1 value, std::thread::id thread,
        engine_document::EngineDocumentProfileFacts profile, engine_editor::EngineEditorProfileFacts editor,
        engine_document_actions::EngineDocumentActionsProfileFacts actions)
    : table_(value), thread_(thread), document_profile_(std::move(profile)), editor_profile_(std::move(editor)),
      document_actions_profile_(std::move(actions)) {}
NativeEngineProvider NativeEngineProvider::checked(const BibEngineProviderV1& table, const NativeEngineExpectation& expected) {
    const auto& build = table.build;
    const auto& profile = expected.document_profile;
    const auto& editor = expected.editor_profile;
    const auto& actions = expected.document_actions_profile;
    const bool documents = profile.enabled || editor.enabled || actions.enabled;
    const auto& contract = actions.enabled ? actions.contract_sha256 :
        editor.enabled ? editor.contract_sha256 : profile.enabled ? profile.contract_sha256 : canonical_header;
    if ((actions.enabled && (profile != engine_document::EngineDocumentProfileFacts{} || editor != engine_editor::EngineEditorProfileFacts{})) ||
        (!actions.enabled && actions != engine_document_actions::EngineDocumentActionsProfileFacts{}) ||
        (actions.enabled && (!engine_document_actions::document_actions_profile_valid(actions) ||
            actions.target_system != expected.target_system || actions.target_processor != expected.target_processor ||
            actions.pointer_bits != expected.pointer_bits || actions.build_sha256 != expected.build_identity_sha256 ||
            actions.source_recipe_sha256 != expected.source_recipe_sha256 ||
            table.limits.maximum_command_bytes < BIB_ENGINE_EDITOR_MAX_WIRE_BYTES ||
            table.limits.maximum_command_bytes < BIB_ENGINE_DOCUMENT_V2_MAX_ACTION_BYTES ||
            table.limits.maximum_query_bytes < engine_editor::kQueryRequestMaximum ||
            table.limits.maximum_reply_bytes < engine_document_actions::kReplyCapacity)) ||
        (editor.enabled && profile != engine_document::EngineDocumentProfileFacts{}) ||
        (!editor.enabled && editor != engine_editor::EngineEditorProfileFacts{}) ||
        (!documents && profile != engine_document::EngineDocumentProfileFacts{}) ||
        (editor.enabled && (!engine_editor::editor_profile_valid(editor) ||
            editor.target_system != expected.target_system || editor.target_processor != expected.target_processor ||
            editor.pointer_bits != expected.pointer_bits || editor.build_sha256 != expected.build_identity_sha256 ||
            editor.source_recipe_sha256 != expected.source_recipe_sha256 ||
            table.limits.maximum_command_bytes < BIB_ENGINE_EDITOR_MAX_WIRE_BYTES ||
            table.limits.maximum_query_bytes < engine_editor::kQueryRequestMaximum ||
            table.limits.maximum_reply_bytes < engine_editor::kReplyCapacity)) ||
        (profile.enabled && (!engine_document::document_profile_valid(profile) ||
            profile.target_system != expected.target_system || profile.target_processor != expected.target_processor ||
            profile.pointer_bits != expected.pointer_bits || profile.build_sha256 != expected.build_identity_sha256 ||
            profile.source_recipe_sha256 != expected.source_recipe_sha256 ||
            table.limits.maximum_command_bytes < BIB_ENGINE_DOCUMENT_V2_MAX_ACTION_BYTES ||
            table.limits.maximum_query_bytes < BIB_ENGINE_DOCUMENT_V2_QUERY_BYTES ||
            table.limits.maximum_reply_bytes < BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY)) ||
        table.size != sizeof(table) || table.abi_major != BIB_ENGINE_ABI_MAJOR ||
        table.abi_minor != (documents ? BIB_ENGINE_DOCUMENT_V2_ABI_MINOR : BIB_ENGINE_ABI_MINOR) || table.reserved ||
        build.size != sizeof(build) || build.layout_revision != BIB_ENGINE_LAYOUT_V1 || build.reserved || !native_target(build) ||
        build.target_system != expected.target_system || build.target_processor != expected.target_processor || build.pointer_bits != expected.pointer_bits ||
        build.lifetime != BIB_ENGINE_LIFETIME_PROCESS || build.maximum_starts != 1 || build.fixed_viewport_width != 800 || build.fixed_viewport_height != 600 ||
        build.capabilities != (actions.enabled ? actions.provider_capabilities :
            editor.enabled ? editor.provider_capabilities : profile.enabled ? profile.provider_capabilities : pixel_capabilities) ||
        expected.contract_header_sha256 != contract ||
        !std::equal(contract.begin(), contract.end(), build.contract_header_sha256) ||
        !nonzero(expected.build_identity_sha256) || !nonzero(expected.source_recipe_sha256) ||
        !std::equal(expected.build_identity_sha256.begin(), expected.build_identity_sha256.end(), build.build_identity_sha256) ||
        !std::equal(expected.source_recipe_sha256.begin(), expected.source_recipe_sha256.end(), build.source_recipe_sha256) ||
        !limits_valid(table.limits) || !table.start || !table.advance || !table.current_document || !table.command || !table.query ||
        !table.deliver_services || !table.collect_service_ack || !table.dispose_retired_service_document)
        throw std::invalid_argument("native provider table does not match the exact selected C ABI/profile/target/pins");
    return NativeEngineProvider(table, std::this_thread::get_id(), profile, expected.editor_profile, actions);
}

struct NativeEngineDriver::Impl {
    struct Reply {
        EngineIdentity identity;
        std::uint64_t transfer{};
        std::uint32_t control{}, service{};
        Bytes payload;
    };
    struct Epoch {
        Impl* owner{};
        EngineIdentity identity;
        std::uint64_t number{};
        std::size_t leases{};
        bool occupied{}, retired{}, provider_retired{};
    };
    struct Lease { Epoch* epoch{}; std::uint64_t owner_lease{}; std::string mime; Bytes body; };
    const BibEngineProviderV1 provider;
    const engine_document::EngineDocumentProfileFacts document_profile;
    const engine_editor::EngineEditorProfileFacts editor_profile;
    const engine_document_actions::EngineDocumentActionsProfileFacts document_actions_profile;
    const std::shared_ptr<EngineOwner> kernel;
    const NativeEngineOptions options;
    const NativeEngineWake wake;
    const std::thread::id thread{std::this_thread::get_id()};
    BibEngineHostV1 callbacks{};
    std::atomic<NativeEngineState> state{NativeEngineState::bound};
    std::atomic<bool> advance_requested{}, close_requested{}, faulted{}, owner_notified{}, wake_enabled{true}, metadata_only{};
    std::atomic<std::int32_t> last_provider{};
    std::atomic<std::uint32_t> last_service{};
    bool started{}, active{}, pumping{}, physical{}, turn_attempted{}, callback_busy{}, seen_ready{}, owner_work_blocked{};
    std::uint32_t local_depth{};
    EngineIdentity turn_identity;
    std::uint64_t turn_transfer{};
    std::optional<Clock::time_point> timer, ready_deadline;
    Clock::time_point now{};
    std::map<std::uint64_t, EngineIdentity> generations;
    std::array<Epoch, 2> epochs{};
    std::map<std::uint64_t, Lease> leases;
    std::uint64_t next_lease{1}, retained_bytes{};
    EngineIdentity frame_identity;
    std::uint64_t frame_revision{}, source_frame_revision{};
    bool collecting{}, collection_required{}, ack_seen{};
    std::uint64_t expected_ack{}, observed_ack{};
    std::uint32_t expected_ack_status{}, observed_ack_status{};

    Impl(NativeEngineProvider value, std::shared_ptr<EngineOwner> owner, NativeEngineOptions config, NativeEngineWake notifier)
        : provider(value.table_), document_profile(std::move(value.document_profile_)), editor_profile(std::move(value.editor_profile_)),
          document_actions_profile(std::move(value.document_actions_profile_)), kernel(std::move(owner)), options(std::move(config)), wake(notifier) {
        if (value.thread_ != thread || !kernel || kernel->closed() || kernel->configured() || kernel->callback_depth() ||
            !limits_valid(options.limits) || !within(options.limits, provider.limits) ||
            !options.abandon_closed_document_outcomes ||
            options.ready_timeout.count() <= 0 || options.ready_timeout > std::chrono::hours(24) ||
            !options.maximum_steps_per_tick || options.maximum_steps_per_tick > 1024)
            throw std::invalid_argument("native driver requires an unconfigured owner and bounded matching policy");
        if (document_profile.enabled ?
                (!engine_document::document_profile_agrees(kernel->document_profile(), document_profile) ||
                 options.limits.maximum_command_bytes < BIB_ENGINE_DOCUMENT_V2_MAX_ACTION_BYTES ||
                 options.limits.maximum_query_bytes < BIB_ENGINE_DOCUMENT_V2_QUERY_BYTES ||
                 options.limits.maximum_reply_bytes < BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY) :
                kernel->document_profile() != engine_document::EngineDocumentProfileFacts{})
            throw std::invalid_argument("native driver and owner document profiles/limits must agree exactly");
        if (editor_profile.enabled ?
                (!engine_editor::editor_profile_agrees(kernel->editor_profile(), editor_profile) ||
                 options.limits.maximum_command_bytes < BIB_ENGINE_EDITOR_MAX_WIRE_BYTES ||
                 options.limits.maximum_query_bytes < engine_editor::kQueryRequestMaximum ||
                 options.limits.maximum_reply_bytes < engine_editor::kReplyCapacity) :
                kernel->editor_profile() != engine_editor::EngineEditorProfileFacts{})
            throw std::invalid_argument("native driver and owner editor profiles/limits must agree exactly");
        if (document_actions_profile.enabled ?
                (!engine_document_actions::document_actions_profile_agrees(kernel->document_actions_profile(), document_actions_profile) ||
                 options.limits.maximum_command_bytes < BIB_ENGINE_EDITOR_MAX_WIRE_BYTES ||
                 options.limits.maximum_command_bytes < BIB_ENGINE_DOCUMENT_V2_MAX_ACTION_BYTES ||
                 options.limits.maximum_query_bytes < engine_editor::kQueryRequestMaximum ||
                 options.limits.maximum_reply_bytes < engine_document_actions::kReplyCapacity) :
                kernel->document_actions_profile() != engine_document_actions::EngineDocumentActionsProfileFacts{})
            throw std::invalid_argument("native driver and owner document actions profiles/limits must agree exactly");
        for (auto& epoch : epochs) epoch.owner = this;
        callbacks = {sizeof(callbacks), BIB_ENGINE_ABI_MAJOR, editor_profile.enabled ? editor_profile.host_abi_minor : BIB_ENGINE_ABI_MINOR, 0, this,
            host_wake, host_timer, host_damage, nullptr, host_enter, host_leave, host_begin, host_close,
            host_submit, host_cancel, host_ack, host_begin_epoch, host_retire_epoch};
    }
    bool document_selected() const noexcept {
        return document_profile.enabled || editor_profile.enabled || document_actions_profile.enabled;
    }
    bool editor_selected() const noexcept { return editor_profile.enabled || document_actions_profile.enabled; }
    bool owner_thread() const noexcept { return thread == std::this_thread::get_id(); }
    void check_thread() const { if (!owner_thread()) throw std::logic_error("native driver requires its owner thread"); }
    void fail() noexcept {
        // Publish before exposing terminal Driver state, including foreign Host
        // callback failures. This retains evidence without an engine export.
        if (document_selected()) kernel->notify_document_terminal();
        faulted.store(true, std::memory_order_release);
        state.store(NativeEngineState::process_exit_required, std::memory_order_release);
        wake_enabled.store(false, std::memory_order_release);
    }
    void notify_owner() noexcept {
        if (!wake_enabled.load(std::memory_order_acquire)) return;
        if (!owner_notified.exchange(true, std::memory_order_acq_rel) && wake.post_owner_wake) wake.post_owner_wake(wake.context);
    }
    void schedule() noexcept {
        advance_requested.store(true, std::memory_order_release);
        notify_owner();
    }
    bool callback_ready() noexcept {
        if (!owner_thread() || !active || !local_depth || pumping || callback_busy || metadata_only.load() || faulted.load()) { fail(); return false; }
        return true;
    }
    Reply exchange(std::uint32_t operation, EngineIdentity identity, Span payload, std::uint64_t transfer,
                   std::uint32_t source, Bytes& input, Bytes& output) {
        if (!owner_thread() || payload.size() > FOUNDATION_ENGINE_MAX_FRAME_BYTES + 48 || output.size() < receipt_bytes ||
            input.capacity() < header_bytes + payload.size())
            throw std::runtime_error("invalid native owner dispatch");
        input.resize(header_bytes + payload.size()); // Reserved before any provider effect.
        std::fill_n(input.begin(), header_bytes, 0);
        input[0] = 'F'; input[1] = 'K'; input[2] = 'B'; input[3] = '1';
        put(input, 4, FOUNDATION_ENGINE_RECORD_VERSION, 2); put(input, 6, operation, 2);
        put(input, 8, input.size(), 4); put(input, 16, identity.worker_epoch, 8);
        put(input, 24, identity.application_instance, 8); put(input, 32, identity.document_sequence, 8);
        put(input, 40, identity.service_generation, 8); put(input, 48, transfer, 8);
        put(input, 56, source, 4); put(input, 64, payload.size(), 4);
        std::copy(payload.begin(), payload.end(), input.begin() + header_bytes);
        const auto count = kernel->dispatch(operation, input, output);
        if (count < static_cast<std::int32_t>(receipt_bytes) || static_cast<std::size_t>(count) > output.size())
            throw std::runtime_error("invalid native owner transport result");
        output.resize(static_cast<std::size_t>(count));
        if (output[0] != 'F' || output[1] != 'K' || output[2] != 'B' || output[3] != '1' ||
            read(output, 4, 2) != 1 || read(output, 6, 2) != (operation | FOUNDATION_ENGINE_REPLY_KIND) ||
            read(output, 8, 4) != output.size() || read(output, 12, 4) || read(output, 60, 4) || read(output, 68, 4) ||
            read(output, 64, 4) != output.size() - header_bytes || read(output, 56, 4) != source ||
            read(output, 72, 4) > FOUNDATION_ENGINE_INTERNAL || read(output, 76, 4) > FOUNDATION_APPENDED_SERVICE_UNCERTAIN)
            throw std::runtime_error("malformed native owner receipt");
        Reply reply{{read(output, 16, 8), read(output, 24, 8), read(output, 32, 8), read(output, 40, 8)},
            read(output, 48, 8), static_cast<std::uint32_t>(read(output, 72, 4)), static_cast<std::uint32_t>(read(output, 76, 4)), {}};
        if (reply.identity.worker_epoch != identity.worker_epoch) throw std::runtime_error("foreign native owner epoch");
        reply.payload.assign(output.begin() + receipt_bytes, output.end());
        last_service.store(reply.service);
        return reply;
    }
    Reply call(std::uint32_t operation, EngineIdentity identity, Span payload = {}, std::uint64_t transfer = 0,
               std::uint32_t source = 0, std::size_t capacity = FOUNDATION_ENGINE_MAX_BODY_BYTES + receipt_bytes) {
        if (!owner_thread() || payload.size() > FOUNDATION_ENGINE_MAX_FRAME_BYTES + 48 || capacity < receipt_bytes)
            throw std::runtime_error("invalid native owner dispatch");
        Bytes input(header_bytes + payload.size()), output(capacity);
        return exchange(operation, identity, payload, transfer, source, input, output);
    }
    static void require_ok(const Reply& reply) {
        if (reply.control != FOUNDATION_ENGINE_OK || reply.service != FOUNDATION_APPENDED_SERVICE_OK)
            throw std::runtime_error("native owner refused required operation");
    }
    void process_close() {
        if (!close_requested.exchange(false) || state.load() == NativeEngineState::closing) return;
        state.store(NativeEngineState::closing); timer.reset(); ready_deadline.reset();
        const auto closed = call(FOUNDATION_ENGINE_CLOSE, kernel->identity());
        if (closed.control != FOUNDATION_ENGINE_OK || (closed.service != 0 && closed.service != FOUNDATION_APPENDED_SERVICE_UNAVAILABLE))
            throw std::runtime_error("native close refused");
        // CLOSE retires all owner epochs, including a prospective epoch. Keep
        // each callback context until the provider also retires it and releases
        // its spans; a later disposal callback must not repeat owner retirement.
        for (auto& epoch : epochs) if (epoch.occupied) epoch.retired = true;
    }
    struct Operation {
        Impl& self;
        bool finished{};
        Operation(Impl& value, EngineIdentity identity, std::uint64_t transfer = 0) : self(value) {
            if (!self.owner_thread() || self.active || self.pumping || self.callback_busy || self.faulted.load())
                throw std::runtime_error("native provider reentry refused");
            self.active = true; self.local_depth = 0; self.physical = false; self.turn_attempted = false;
            self.turn_identity = identity; self.turn_transfer = transfer;
        }
        bool finish() noexcept {
            if (finished) return !self.faulted.load();
            finished = true;
            if (!self.faulted.load()) {
                if (self.local_depth || !self.physical) self.fail();
                else try { require_ok(self.call(FOUNDATION_ENGINE_TURN_LEAVE, self.turn_identity, {}, self.turn_transfer)); }
                     catch (...) { self.fail(); }
            }
            self.active = false; self.physical = false;
            return !self.faulted.load();
        }
        bool reject_before_entry() noexcept {
            if (finished || self.faulted.load() || self.turn_attempted || self.physical || self.local_depth) { self.fail(); return false; }
            // A known native pre-entry rejection has no Host TURN to leave.
            finished = true; self.active = false;
            return true;
        }
        ~Operation() { finish(); }
    };
    struct Callback {
        Impl& self;
        explicit Callback(Impl& owner) : self(owner) { self.callback_busy = true; }
        ~Callback() { self.callback_busy = false; }
    };
    struct MetadataOperation {
        Impl& self;
        explicit MetadataOperation(Impl& value) : self(value) {
            if (!self.owner_thread() || self.active || self.pumping || self.callback_busy || self.faulted.load())
                throw std::runtime_error("native metadata provider reentry refused");
            self.active = true;
            self.metadata_only.store(true);
        }
        ~MetadataOperation() {
            self.metadata_only.store(false);
            self.active = false;
        }
    };
    EngineIdentity generation(std::uint64_t value) const {
        const auto found = generations.find(value);
        if (found == generations.end()) throw std::runtime_error("unknown native service generation");
        return found->second;
    }
    static void BIB_ENGINE_CALL host_wake(void* context) noexcept {
        if (!context) return;
        auto& self = *static_cast<Impl*>(context);
        if (self.metadata_only.load()) { self.fail(); return; }
        self.schedule();
    }
    static std::uint32_t BIB_ENGINE_CALL host_enter(void* context) noexcept {
        if (!context) return FOUNDATION_APPENDED_SERVICE_UNAVAILABLE;
        auto& self = *static_cast<Impl*>(context);
        if (!self.owner_thread() || !self.active || self.pumping || self.callback_busy || self.metadata_only.load() || self.faulted.load() || self.local_depth == 64) {
            self.fail(); return FOUNDATION_APPENDED_SERVICE_UNAVAILABLE;
        }
        try {
            self.turn_attempted = true;
            if (!self.physical) {
                const auto reply = self.call(FOUNDATION_ENGINE_TURN_ENTER, self.turn_identity, {}, self.turn_transfer);
                if (reply.control != FOUNDATION_ENGINE_OK || reply.service != FOUNDATION_APPENDED_SERVICE_OK) return reply.service ? reply.service : FOUNDATION_APPENDED_SERVICE_UNAVAILABLE;
                self.physical = true;
            }
            ++self.local_depth;
            return FOUNDATION_APPENDED_SERVICE_OK;
        } catch (...) { self.fail(); return FOUNDATION_APPENDED_SERVICE_UNCERTAIN; }
    }
    static void BIB_ENGINE_CALL host_leave(void* context) noexcept {
        if (!context) return;
        auto& self = *static_cast<Impl*>(context);
        if (!self.owner_thread() || !self.active || self.callback_busy || self.metadata_only.load() || !self.local_depth || self.faulted.load()) { self.fail(); return; }
        --self.local_depth; // The outer operation owns the physical LEAVE.
    }
    static void BIB_ENGINE_CALL host_timer(void* context, double delay, std::uint32_t armed) noexcept {
        if (!context) return;
        auto& self = *static_cast<Impl*>(context);
        if (!self.callback_ready()) return;
        if (!std::isfinite(delay) || delay < 0 || armed > 1) { self.fail(); return; }
        const auto bounded = std::min(delay, 86400000.0);
        self.timer = armed ? std::optional(self.now + std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double, std::milli>(bounded))) : std::nullopt;
        self.notify_owner();
    }
    static std::uint64_t BIB_ENGINE_CALL host_begin(void* context, const BibEngineDocumentV1* prospective) noexcept {
        if (!context) return 0;
        auto& self = *static_cast<Impl*>(context);
        if (!self.callback_ready()) return 0;
        try {
            Callback guard(self);
            if (!prospective || !prospective->application_instance || !prospective->document_sequence || prospective->service_generation ||
                self.generations.size() >= self.options.limits.maximum_retired_documents + 1) return 0;
            const EngineIdentity identity{self.turn_identity.worker_epoch, prospective->application_instance, prospective->document_sequence, 0};
            const auto previous = self.kernel->identity();
            const auto reply = self.call(FOUNDATION_ENGINE_BEGIN_DOCUMENT, identity);
            if (reply.control != FOUNDATION_ENGINE_OK || reply.service) return 0;
            if (!reply.identity.service_generation || reply.identity.application_instance != identity.application_instance ||
                reply.identity.document_sequence != identity.document_sequence || !reply.payload.empty()) throw std::runtime_error("native document adoption mismatch");
            if (!self.generations.emplace(reply.identity.service_generation, reply.identity).second) throw std::runtime_error("reused native document generation");
            for (auto& epoch : self.epochs)
                if (epoch.occupied && previous.service_generation && epoch.identity.application_instance == previous.application_instance &&
                    epoch.identity.document_sequence == previous.document_sequence && previous != reply.identity) epoch.retired = true;
            self.notify_owner();
            return reply.identity.service_generation;
        } catch (...) { self.fail(); return 0; }
    }
    static void BIB_ENGINE_CALL host_close(void* context, std::uint64_t generation) noexcept {
        if (!context) return;
        auto& self = *static_cast<Impl*>(context);
        if (!self.callback_ready()) return;
        try {
            Callback guard(self);
            const auto identity = self.generation(generation);
            require_ok(self.call(FOUNDATION_ENGINE_CLOSE_DOCUMENT, identity));
            // The actual owner revokes/prunes this document's resource epochs
            // as part of CLOSE. A later explicit provider retirement is a known
            // idempotent notification, not authority to dispatch a stale epoch.
            for (auto& epoch : self.epochs)
                if (epoch.occupied && epoch.identity.application_instance == identity.application_instance &&
                    epoch.identity.document_sequence == identity.document_sequence) epoch.retired = true;
            self.notify_owner();
        }
        catch (...) { self.fail(); }
    }
    static std::uint32_t BIB_ENGINE_CALL host_submit(void* context, std::uint64_t generation, const BibEngineBytesV1* bytes, std::uint32_t source) noexcept {
        if (!context) return FOUNDATION_APPENDED_SERVICE_UNAVAILABLE;
        auto& self = *static_cast<Impl*>(context);
        if (!self.callback_ready()) return FOUNDATION_APPENDED_SERVICE_UNAVAILABLE;
        try {
            Callback guard(self);
            if (!bytes || !bytes_valid(*bytes, self.options.limits.maximum_service_message_bytes) || source > 2)
                return FOUNDATION_APPENDED_SERVICE_INVALID_REQUEST;
            const auto reply = self.call(FOUNDATION_ENGINE_SUBMIT, self.generation(generation), {bytes->data, bytes->length}, 0, source);
            if (reply.service == FOUNDATION_APPENDED_SERVICE_OK) self.notify_owner();
            return reply.service;
        } catch (...) { self.fail(); return FOUNDATION_APPENDED_SERVICE_UNCERTAIN; }
    }
    static std::uint32_t BIB_ENGINE_CALL host_cancel(void* context, std::uint64_t generation, std::uint64_t sequence) noexcept {
        if (!context) return FOUNDATION_APPENDED_SERVICE_UNAVAILABLE;
        auto& self = *static_cast<Impl*>(context);
        if (!self.callback_ready()) return FOUNDATION_APPENDED_SERVICE_UNAVAILABLE;
        try { Callback guard(self); const auto reply = self.call(FOUNDATION_ENGINE_CANCEL, self.generation(generation), integer(sequence, 8)); self.notify_owner(); return reply.service; }
        catch (...) { self.fail(); return FOUNDATION_APPENDED_SERVICE_UNCERTAIN; }
    }
    static std::uint32_t BIB_ENGINE_CALL host_ack(void* context, std::uint64_t generation, std::uint64_t through) noexcept {
        if (!context) return FOUNDATION_APPENDED_SERVICE_UNAVAILABLE;
        auto& self = *static_cast<Impl*>(context);
        if (!self.callback_ready()) return FOUNDATION_APPENDED_SERVICE_UNAVAILABLE;
        try {
            Callback guard(self);
            if (!self.collecting || generation != self.turn_identity.service_generation ||
                (self.collection_required && through != self.expected_ack) || self.ack_seen)
                throw std::runtime_error("unsolicited native ACK stage");
            const auto reply = self.call(FOUNDATION_ENGINE_STAGE_ACK, self.generation(generation), integer(through, 8));
            if (reply.control != FOUNDATION_ENGINE_OK || reply.service == FOUNDATION_APPENDED_SERVICE_UNCERTAIN)
                throw std::runtime_error("invalid native ACK stage receipt");
            self.ack_seen = true; self.observed_ack = through; self.observed_ack_status = reply.service;
            self.notify_owner();
            return reply.service;
        } catch (...) { self.fail(); return FOUNDATION_APPENDED_SERVICE_UNCERTAIN; }
    }
    static std::int32_t BIB_ENGINE_CALL host_begin_epoch(void* context, const BibEngineDocumentV1* prospective, BibEngineResourceEpochV1* output) noexcept {
        if (!context || !output) return BIB_ENGINE_INVALID;
        *output = {};
        auto& self = *static_cast<Impl*>(context);
        if (!self.callback_ready()) return BIB_ENGINE_INVALID;
        try {
            Callback guard(self);
            if (!prospective || !prospective->application_instance || !prospective->document_sequence || prospective->service_generation) return BIB_ENGINE_INVALID;
            auto slot = std::find_if(self.epochs.begin(), self.epochs.end(), [](const Epoch& epoch) {
                return !epoch.occupied || (epoch.retired && epoch.provider_retired && !epoch.leases);
            });
            if (slot == self.epochs.end()) return BIB_ENGINE_LIMIT;
            const EngineIdentity identity{self.turn_identity.worker_epoch, prospective->application_instance, prospective->document_sequence, 0};
            const auto reply = self.call(FOUNDATION_ENGINE_BEGIN_RESOURCE_EPOCH, identity);
            if (reply.control != FOUNDATION_ENGINE_OK || reply.service) return BIB_ENGINE_LIMIT;
            if (reply.payload.size() != 8 || !read(reply.payload, 0, 8)) throw std::runtime_error("invalid native resource epoch");
            *slot = {&self, identity, read(reply.payload, 0, 8), 0, true, false, false};
            *output = {sizeof(*output), 0, slot->number, &*slot, resource_resolve, resource_release};
            return BIB_ENGINE_OK;
        } catch (...) { self.fail(); return BIB_ENGINE_PROCESS_EXIT_REQUIRED; }
    }
    static void BIB_ENGINE_CALL host_retire_epoch(void* context, std::uint64_t number) noexcept {
        if (!context) return;
        auto& self = *static_cast<Impl*>(context);
        if (!self.callback_ready()) return;
        try {
            Callback guard(self);
            auto found = std::find_if(self.epochs.begin(), self.epochs.end(), [&](const Epoch& value) { return value.occupied && value.number == number; });
            if (found == self.epochs.end()) throw std::runtime_error("unknown native resource epoch retirement");
            if (!found->retired) require_ok(self.call(FOUNDATION_ENGINE_RETIRE_RESOURCE_EPOCH, found->identity, integer(number, 8)));
            found->retired = true; found->provider_retired = true;
            self.notify_owner();
        } catch (...) { self.fail(); }
    }
    void release_lease(std::map<std::uint64_t, Lease>::iterator found) {
        require_ok(call(FOUNDATION_ENGINE_RESOURCE_RELEASE, found->second.epoch->identity, integer(found->second.owner_lease, 8)));
        retained_bytes -= found->second.body.size(); --found->second.epoch->leases; leases.erase(found);
        notify_owner();
    }
    static std::int32_t BIB_ENGINE_CALL resource_resolve(void* context, const BibEngineResourceRequestV1* request, BibEngineResourceResponseV1* output) noexcept {
        if (!context || !output) return BIB_ENGINE_INVALID;
        *output = {};
        auto& epoch = *static_cast<Epoch*>(context); auto& self = *epoch.owner;
        if (!self.callback_ready()) return BIB_ENGINE_INVALID;
        std::uint64_t held_lease{};
        try {
            Callback guard(self);
            if (!request || request->size != sizeof(*request) || request->reserved || request->resource_epoch != epoch.number ||
                !request->method.length || !request->resolved_url.length ||
                !epoch.occupied || epoch.retired || !bytes_valid(request->method, 16) || !bytes_valid(request->resolved_url, 4096)) return BIB_ENGINE_INVALID;
            const std::string_view method(reinterpret_cast<const char*>(request->method.data), request->method.length);
            if (method != "GET" && method != "HEAD") return BIB_ENGINE_INVALID;
            if (self.leases.size() >= self.options.limits.maximum_inflight_resources || !self.next_lease) return BIB_ENGINE_LIMIT;
            Bytes payload(16 + request->resolved_url.length);
            put(payload, 0, epoch.number, 8); put(payload, 8, method == "HEAD", 4); put(payload, 12, request->resolved_url.length, 4);
            std::copy_n(request->resolved_url.data, request->resolved_url.length, payload.begin() + 16);
            const auto reply = self.call(FOUNDATION_ENGINE_RESOURCE_RESOLVE, epoch.identity, payload);
            require_ok(reply);
            if (reply.payload.size() < 32) throw std::runtime_error("short native resource metadata");
            const auto http = read(reply.payload, 0, 4), mime_length = read(reply.payload, 4, 4);
            const auto body_length = read(reply.payload, 8, 8), content_length = read(reply.payload, 16, 8);
            held_lease = read(reply.payload, 24, 8);
            if (mime_length > 127 || !mime_length || reply.payload.size() != 32 + mime_length || http < 200 || http > 599 || http / 100 == 3 ||
                (method == "HEAD" && body_length) || (method == "GET" && body_length != content_length))
                throw std::runtime_error("invalid native resource metadata");
            const std::string mime(reinterpret_cast<const char*>(reply.payload.data() + 32), static_cast<std::size_t>(mime_length));
            for (unsigned char c : mime) if (c < 0x21 || c > 0x7e) throw std::runtime_error("invalid native resource MIME");
            if (http != 200) {
                if (held_lease || body_length || content_length || mime != "text/plain") throw std::runtime_error("invalid native error resource");
                static constexpr std::uint8_t plain[] = "text/plain";
                *output = {sizeof(*output), static_cast<std::uint32_t>(http), 0, {plain, 10, 0}, nullptr, 0, 0};
                return BIB_ENGINE_OK;
            }
            if (!held_lease) throw std::runtime_error("native resource omitted lease");
            if (body_length > self.options.limits.maximum_resource_response_bytes || content_length > self.options.limits.maximum_resource_response_bytes ||
                body_length > self.options.limits.maximum_retained_resource_bytes - self.retained_bytes) {
                require_ok(self.call(FOUNDATION_ENGINE_RESOURCE_RELEASE, epoch.identity, integer(held_lease, 8)));
                held_lease = 0;
                return BIB_ENGINE_LIMIT;
            }
            Lease value{&epoch, held_lease, mime, Bytes(static_cast<std::size_t>(body_length))};
            for (std::uint64_t offset = 0; offset < body_length;) {
                const auto count = std::min<std::uint64_t>(FOUNDATION_ENGINE_MAX_BODY_BYTES, body_length - offset);
                Bytes chunk(20); put(chunk, 0, held_lease, 8); put(chunk, 8, offset, 8); put(chunk, 16, count, 4);
                const auto bytes = self.call(FOUNDATION_ENGINE_RESOURCE_READ, epoch.identity, chunk);
                require_ok(bytes);
                if (bytes.payload.size() != count) throw std::runtime_error("short native resource read");
                std::copy(bytes.payload.begin(), bytes.payload.end(), value.body.begin() + static_cast<std::ptrdiff_t>(offset)); offset += count;
            }
            const auto token = self.next_lease;
            self.next_lease = token == std::numeric_limits<std::uint64_t>::max() ? 0 : token + 1;
            auto [position, inserted] = self.leases.emplace(token, std::move(value));
            if (!inserted) throw std::runtime_error("reused native resource lease");
            held_lease = 0; ++epoch.leases; self.retained_bytes += body_length;
            const auto& retained = position->second;
            *output = {sizeof(*output), 200, token,
                {reinterpret_cast<const std::uint8_t*>(retained.mime.data()), static_cast<std::uint32_t>(retained.mime.size()), 0},
                retained.body.empty() ? nullptr : retained.body.data(), body_length, content_length};
            return BIB_ENGINE_OK;
        } catch (const std::bad_alloc&) {
            if (held_lease && !self.faulted.load()) try { require_ok(self.call(FOUNDATION_ENGINE_RESOURCE_RELEASE, epoch.identity, integer(held_lease, 8))); }
                catch (...) { self.fail(); }
            return self.faulted.load() ? BIB_ENGINE_PROCESS_EXIT_REQUIRED : BIB_ENGINE_LIMIT;
        } catch (...) { self.fail(); return BIB_ENGINE_PROCESS_EXIT_REQUIRED; }
    }
    static void BIB_ENGINE_CALL resource_release(void* context, std::uint64_t token) noexcept {
        if (!context) return;
        auto& epoch = *static_cast<Epoch*>(context); auto& self = *epoch.owner;
        if (!self.callback_ready()) return;
        try {
            Callback guard(self);
            const auto found = self.leases.find(token);
            if (!token || found == self.leases.end() || found->second.epoch != &epoch) throw std::runtime_error("unknown native resource release");
            self.release_lease(found);
        } catch (...) { self.fail(); }
    }
    static void BIB_ENGINE_CALL host_damage(void* context, const BibEngineDamageV1* damage) noexcept {
        if (!context) return;
        auto& self = *static_cast<Impl*>(context);
        if (!self.callback_ready()) return;
        try {
            Callback guard(self);
            if (!damage || damage->size != sizeof(*damage) || damage->format != 1 || damage->x < 0 || damage->y < 0 ||
                damage->width <= 0 || damage->height <= 0 || damage->x > 800 || damage->width > 800 - damage->x ||
                damage->y > 600 || damage->height > 600 - damage->y ||
                damage->stride_bytes != static_cast<std::uint32_t>(damage->width) * 4 ||
                damage->length != std::uint64_t(damage->stride_bytes) * static_cast<std::uint32_t>(damage->height) ||
                !damage->bytes || damage->length > std::numeric_limits<std::uintptr_t>::max() - reinterpret_cast<std::uintptr_t>(damage->bytes) ||
                !damage->frame_revision || damage->frame_revision <= self.source_frame_revision)
                throw std::runtime_error("invalid native raster damage");
            const auto found = self.generations.find(damage->document.service_generation);
            if (found == self.generations.end() || !same(document(found->second), damage->document) || found->second != self.kernel->identity())
                throw std::runtime_error("stale native raster document");
            const auto identity = found->second;
            const auto base = identity == self.frame_identity ? self.frame_revision : 0;
            if (!base && (damage->x || damage->y || damage->width != 800 || damage->height != 600))
                throw std::runtime_error("native first frame must cover the viewport");
            if (base == std::numeric_limits<std::uint64_t>::max()) throw std::runtime_error("native frame revisions exhausted");
            Bytes payload(48 + damage->length);
            put(payload, 0, 1, 4); put(payload, 4, 800, 4); put(payload, 8, 600, 4); put(payload, 12, damage->stride_bytes, 4);
            put(payload, 16, static_cast<std::uint32_t>(damage->x), 4); put(payload, 20, static_cast<std::uint32_t>(damage->y), 4);
            put(payload, 24, static_cast<std::uint32_t>(damage->width), 4); put(payload, 28, static_cast<std::uint32_t>(damage->height), 4);
            put(payload, 32, base, 8); put(payload, 40, base + 1, 8);
            for (std::size_t i = 3; i < damage->length; i += 4) if (damage->bytes[i] != 255) throw std::runtime_error("nonopaque native raster damage");
            std::copy_n(damage->bytes, damage->length, payload.begin() + 48);
            require_ok(self.call(FOUNDATION_ENGINE_FRAME_COMMIT, identity, payload, 0, 0, receipt_bytes));
            self.frame_identity = identity; self.frame_revision = base + 1; self.source_frame_revision = damage->frame_revision;
        } catch (...) { self.fail(); }
    }
    template<class F> std::int32_t invoke(EngineIdentity identity, std::uint64_t transfer, F&& function) {
        Operation turn(*this, identity, transfer);
        std::int32_t status = BIB_ENGINE_PROCESS_EXIT_REQUIRED;
        try { status = function(); if (!provider_status(status) || status == BIB_ENGINE_PROCESS_EXIT_REQUIRED) fail(); }
        catch (...) { fail(); }
        last_provider.store(status);
        if (!turn.finish()) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
        return status;
    }
    struct DocumentInvocation { std::int32_t status; bool completed_turn; };
    template<class F> DocumentInvocation invoke_document(EngineIdentity identity, std::uint64_t transfer,
                                                        bool metadata, bool allow_preentry, F&& function) {
        std::int32_t status = BIB_ENGINE_PROCESS_EXIT_REQUIRED;
        bool completed_turn{};
        if (metadata) {
            MetadataOperation operation(*this);
            try { status = function(); }
            catch (...) { fail(); }
            if (!provider_status(status)) fail();
        } else {
            Operation operation(*this, identity, transfer);
            try { status = function(); }
            catch (...) { fail(); } // No synthetic LEAVE/result after an uncertain unwind.
            if (!provider_status(status)) fail();
            if (!faulted.load()) {
                if (allow_preentry && status < BIB_ENGINE_OK && status != BIB_ENGINE_PROCESS_EXIT_REQUIRED && !turn_attempted && !physical && !local_depth) {
                    if (!operation.reject_before_entry()) fail();
                } else if (operation.finish()) completed_turn = true;
                else fail();
            }
        }
        last_provider.store(status);
        // A naturally returned -8 may have a complete owned unknown result.
        // Ordinary work needs its matching turn; metadata ACK needs none.
        // The caller retains that evidence and terminates without another entry.
        return {status, completed_turn};
    }
    std::uint32_t collect_ack(EngineIdentity identity, bool required, std::uint64_t through = 0, std::uint32_t status = 0) {
        collecting = true; collection_required = required; expected_ack = through; expected_ack_status = status; ack_seen = false;
        const auto native = document(identity);
        std::uint32_t actual = FOUNDATION_APPENDED_SERVICE_UNCERTAIN;
        try { actual = provider.collect_service_ack(&native); }
        catch (...) { fail(); }
        collecting = false;
        if (actual > FOUNDATION_APPENDED_SERVICE_UNCERTAIN || actual == FOUNDATION_APPENDED_SERVICE_UNCERTAIN ||
            (required && (!ack_seen || observed_ack != through || observed_ack_status != status || actual != status)) ||
            (!required && ((ack_seen && actual != observed_ack_status) || (!ack_seen && actual != 0 && actual != FOUNDATION_APPENDED_SERVICE_UNAVAILABLE))))
            fail();
        return actual;
    }
    bool current_ready() {
        BibEngineDocumentV1 current{};
        const auto identity = kernel->identity();
        const auto status = invoke(identity, 0, [&] { return provider.current_document(identity.application_instance, &current); });
        if (faulted.load()) return false;
        if (status == BIB_ENGINE_STALE) return false;
        if (status != BIB_ENGINE_OK || !current.application_instance || !current.document_sequence || !current.service_generation ||
            !same(current, document(kernel->identity()))) { fail(); return false; }
        const auto found = generations.find(current.service_generation);
        if (found == generations.end() || !same(current, document(found->second))) { fail(); return false; }
        seen_ready = true; ready_deadline.reset(); state.store(NativeEngineState::ready); advance_requested.store(true);
        return true;
    }
    bool retirement_step() {
        if (!options.abandon_closed_document_outcomes) return false;
        const auto identity = kernel->identity();
        const auto audit = call(FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT, identity);
        if (audit.control == FOUNDATION_ENGINE_OK) {
            if (!audit.transfer || !audit.identity.application_instance || !audit.identity.document_sequence || !audit.identity.service_generation)
                throw std::runtime_error("invalid native retirement audit identity");
            bool ack_receipt = false;
            Envelope envelope; Span ignored;
            if (decode_envelope(audit.payload, envelope, ignored) != CodecStatus::ok || envelope.kind != FOUNDATION_APPENDED_MESSAGE_COMPLETION) {
                if (audit.payload.size() != 92 || read(audit.payload, 6, 2) != (FOUNDATION_ENGINE_PEEK_ACK_RECEIPT | FOUNDATION_ENGINE_REPLY_KIND) ||
                    read(audit.payload, 8, 4) != 92 || read(audit.payload, 16, 8) != audit.identity.worker_epoch ||
                    read(audit.payload, 24, 8) != audit.identity.application_instance || read(audit.payload, 32, 8) != audit.identity.document_sequence ||
                    read(audit.payload, 40, 8) != audit.identity.service_generation || read(audit.payload, 88, 4) > 14)
                    throw std::runtime_error("invalid native retirement audit bytes");
                ack_receipt = true;
            } else if (envelope.generation != audit.identity.service_generation) throw std::runtime_error("foreign native retirement completion");
            if (options.observe_retirement) {
                Callback guard(*this);
                if (!options.observe_retirement({audit.identity, audit.transfer, ack_receipt, audit.payload})) {
                    state.store(NativeEngineState::blocked); return false;
                }
            }
            const auto result = call(FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT, audit.identity, integer(FOUNDATION_ENGINE_ABANDONED, 4), audit.transfer);
            if (result.service == FOUNDATION_APPENDED_SERVICE_UNCERTAIN) { fail(); return false; }
            if (result.control != FOUNDATION_ENGINE_OK || result.service) { state.store(NativeEngineState::blocked); return false; }
            return true;
        }
        if (audit.control != FOUNDATION_ENGINE_EMPTY) throw std::runtime_error("native retirement audit refused");
        const auto retired = call(FOUNDATION_ENGINE_PEEK_RETIRED_DOCUMENT, identity);
        if (retired.control == FOUNDATION_ENGINE_EMPTY) return false;
        require_ok(retired);
        if (!retired.transfer || !retired.payload.empty() || !retired.identity.service_generation) throw std::runtime_error("invalid retired native document");
        const auto status = invoke(retired.identity, retired.transfer, [&] {
            return provider.dispose_retired_service_document(retired.identity.application_instance, retired.identity.service_generation);
        });
        if (status != BIB_ENGINE_OK || faulted.load()) { fail(); return false; }
        require_ok(call(FOUNDATION_ENGINE_RETIRED_DOCUMENT_RESULT, retired.identity, integer(FOUNDATION_ENGINE_ACCEPTED, 4), retired.transfer));
        generations.erase(retired.identity.service_generation);
        return true;
    }
    static bool command_result_valid(const BibEngineReplyBufferV1& buffer,
            const BibEngineCommandResultV1& result, const Bytes& owned,
            std::uint64_t sequence, std::int32_t status) {
        // Disposition2 keeps bounded raw bytes/handled as forensic evidence.
        // Its caller settles UNKNOWN and exits; it never decodes semantic success.
        return provider_status(status) && buffer.size == sizeof(buffer) && buffer.capacity == owned.size() &&
            buffer.bytes == owned.data() && result.size == sizeof(result) && result.request_sequence == sequence &&
            result.disposition <= 2 && result.handled <= 1 && result.bytes_written <= owned.size() &&
            (result.disposition != 0 || (status != BIB_ENGINE_OK && !result.handled && !result.bytes_written)) &&
            (result.disposition != 1 || status == BIB_ENGINE_OK);
    }
    static void exact_empty(const Reply& reply, EngineIdentity identity, std::uint64_t transfer) {
        require_ok(reply);
        if (reply.identity != identity || reply.transfer != transfer || !reply.payload.empty())
            throw std::runtime_error("native owner changed the original work receipt");
    }
    bool document_step() {
        if (!document_selected()) return false;
        const auto pending = call(FOUNDATION_ENGINE_PEEK_DOCUMENT_WORK, kernel->identity(), {}, 0, 0,
            receipt_bytes + FOUNDATION_ENGINE_DOCUMENT_WORK_PREFIX_BYTES + BIB_ENGINE_DOCUMENT_V2_MAX_ACTION_BYTES);
        if (pending.control == FOUNDATION_ENGINE_EMPTY) {
            if ((pending.service != FOUNDATION_APPENDED_SERVICE_OK && pending.service != FOUNDATION_APPENDED_SERVICE_UNAVAILABLE) ||
                pending.transfer || !pending.payload.empty())
                throw std::runtime_error("malformed empty native document mailbox");
            if (pending.service == FOUNDATION_APPENDED_SERVICE_UNAVAILABLE) owner_work_blocked = true;
            return false;
        }
        require_ok(pending);
        constexpr auto prefix = FOUNDATION_ENGINE_DOCUMENT_WORK_PREFIX_BYTES;
        if (!pending.transfer || pending.payload.size() < prefix)
            throw std::runtime_error("short native document work");
        EngineDocumentWork work;
        work.target = {pending.identity.worker_epoch, pending.identity.application_instance,
            pending.identity.document_sequence, pending.identity.service_generation};
        work.kind = static_cast<EngineDocumentWorkKind>(read(pending.payload, 0, 4));
        work.operation = static_cast<std::uint32_t>(read(pending.payload, 4, 4));
        work.request_sequence = read(pending.payload, 8, 8);
        std::copy_n(pending.payload.begin() + 16, work.schema_sha256.size(), work.schema_sha256.begin());
        work.required_reply_capacity = static_cast<std::uint32_t>(read(pending.payload, 48, 4));
        const auto input_bytes = read(pending.payload, 52, 4);
        if (input_bytes > BIB_ENGINE_DOCUMENT_V2_MAX_ACTION_BYTES || pending.payload.size() != prefix + input_bytes)
            throw std::runtime_error("native document work extent mismatch");
        work.payload.assign(pending.payload.begin() + prefix, pending.payload.end());
        if (!valid_engine_document_work_shape(work) ||
            ((work.kind == EngineDocumentWorkKind::body_action || work.kind == EngineDocumentWorkKind::body_action_ack) &&
             !document_actions_profile.enabled) || work.required_reply_capacity > options.limits.maximum_reply_bytes ||
            work.payload.size() > (work.kind == EngineDocumentWorkKind::snapshot_query ?
                options.limits.maximum_query_bytes : options.limits.maximum_command_bytes))
            throw std::runtime_error("native document work does not match the admitted catalog");

        // The provider reply and final RESULT transport buffers are owned and
        // complete before claiming a possibly effectful request. No size probe.
        Bytes owned(work.required_reply_capacity);
        Bytes result_body(FOUNDATION_ENGINE_DOCUMENT_RESULT_PREFIX_BYTES + owned.size());
        Bytes result_input(header_bytes + result_body.size()), result_output(receipt_bytes);
        Bytes claim(FOUNDATION_ENGINE_DOCUMENT_BEGIN_BYTES);
        put(claim, 0, static_cast<std::uint32_t>(work.kind), 4);
        put(claim, 8, work.request_sequence, 8);
        exact_empty(call(FOUNDATION_ENGINE_BEGIN_DOCUMENT_WORK, pending.identity, claim, pending.transfer, 0, receipt_bytes),
            pending.identity, pending.transfer);

        BibEngineReplyBufferV1 buffer{sizeof(buffer), work.required_reply_capacity, owned.data()};
        std::int32_t status{};
        std::uint32_t disposition{}, handled{}, written{};
        std::uint64_t revision{};
        if (work.kind == EngineDocumentWorkKind::snapshot_query) {
            BibEngineQueryV1 request{};
            request.size = sizeof(request); request.kind = work.operation;
            request.expected = document(pending.identity);
            std::copy(work.schema_sha256.begin(), work.schema_sha256.end(), request.schema_sha256);
            request.payload = {work.payload.data(), static_cast<std::uint32_t>(work.payload.size()), 0};
            BibEngineQueryResultV1 result{sizeof(result), 0, {}, 0};
            const auto invocation = invoke_document(pending.identity, pending.transfer, false, true, [&] {
                return provider.query(&request, &buffer, &result);
            });
            status = invocation.status;
            if (faulted.load()) return false;
            const bool empty_document = !result.document.application_instance && !result.document.document_sequence && !result.document.service_generation;
            if (buffer.size != sizeof(buffer) || buffer.capacity != owned.size() || buffer.bytes != owned.data() ||
                result.size != sizeof(result) || result.bytes_written > owned.size() ||
                (status == BIB_ENGINE_OK ? (!result.bytes_written || !result.semantic_revision ||
                    !same(result.document, request.expected)) :
                    (result.bytes_written || result.semantic_revision || (!empty_document && !same(result.document, request.expected)))))
                throw std::runtime_error("malformed native document query result");
            written = result.bytes_written; revision = result.semantic_revision;
        } else {
            BibEngineCommandV1 request{};
            request.size = sizeof(request); request.operation = work.operation;
            request.expected = document(pending.identity); request.request_sequence = work.request_sequence;
            std::copy(work.schema_sha256.begin(), work.schema_sha256.end(), request.schema_sha256);
            request.payload = {work.payload.data(), static_cast<std::uint32_t>(work.payload.size()), 0};
            BibEngineCommandResultV1 result{sizeof(result), 0, 0, 0, 0};
            const auto invocation = invoke_document(pending.identity, pending.transfer, engine_document_ack_kind(work.kind), true, [&] {
                return provider.command(&request, &buffer, &result);
            });
            status = invocation.status;
            if (faulted.load()) return false;
            if (!command_result_valid(buffer, result, owned, work.request_sequence, status) ||
                (engine_document_action_kind(work.kind) && !invocation.completed_turn && result.disposition != 0))
                throw std::runtime_error("malformed native document command result");
            disposition = result.disposition; handled = result.handled; written = result.bytes_written;
            if (engine_document_ack_kind(work.kind) && status == BIB_ENGINE_OK && disposition == 1) {
                const auto ack = decode_engine_document_action_ack(Span(owned).first(written));
                if (handled || !ack || ack->original_action_sequence != read(work.payload, 0, 8))
                    throw std::runtime_error("malformed native document action ACK");
            }
        }
        put(result_body, 0, static_cast<std::uint32_t>(work.kind), 4);
        put(result_body, 8, work.request_sequence, 8);
        put(result_body, 16, static_cast<std::uint32_t>(status), 4);
        put(result_body, 20, disposition, 4); put(result_body, 24, written, 4);
        put(result_body, 28, handled, 4); put(result_body, 32, revision, 8);
        std::copy_n(owned.begin(), written, result_body.begin() + FOUNDATION_ENGINE_DOCUMENT_RESULT_PREFIX_BYTES);
        result_body.resize(FOUNDATION_ENGINE_DOCUMENT_RESULT_PREFIX_BYTES + written);
        exact_empty(exchange(FOUNDATION_ENGINE_DOCUMENT_WORK_RESULT, pending.identity, result_body, pending.transfer, 0,
            result_input, result_output), pending.identity, pending.transfer);
        if (status == BIB_ENGINE_PROCESS_EXIT_REQUIRED || disposition == 2) { fail(); return false; }
        notify_owner();
        return true;
    }
    bool physical_step() {
        if (!editor_selected() && (!document_profile.enabled || document_profile.kind != engine_document::ProfileKind::physical)) return false;
        // CLOSE revokes current service authority before owned editor9 cleanup
        // drains. A physical scheduler peek has no meaning without that domain.
        if (!kernel->identity().service_generation) return false;
        const auto pending = call(FOUNDATION_ENGINE_PEEK_INPUT, kernel->identity(), {}, 0, 0, receipt_bytes + 56 + 160);
        if (pending.control == FOUNDATION_ENGINE_EMPTY) {
            if (pending.service != FOUNDATION_APPENDED_SERVICE_UNAVAILABLE || pending.transfer || !pending.payload.empty())
                throw std::runtime_error("malformed empty native physical mailbox");
            return false;
        }
        require_ok(pending);
        if (!pending.transfer || pending.payload.size() < 56 || read(pending.payload, 4, 4))
            throw std::runtime_error("malformed native physical work");
        const auto operation = read(pending.payload, 0, 4), sequence = read(pending.payload, 8, 8);
        const auto capacity = read(pending.payload, 48, 4), count = read(pending.payload, 52, 4);
        const auto found = std::find_if(engine_input::kCommands.begin(), engine_input::kCommands.end(), [&](const auto& facts) {
            return facts.operation == operation;
        });
        if (found == engine_input::kCommands.end() || !sequence || sequence > BIB_ENGINE_DOCUMENT_V2_MAX_ORDINARY_SEQUENCE ||
            capacity != found->required_reply_capacity || !count || count > found->maximum_input_bytes ||
            pending.payload.size() != 56 + count ||
            !std::equal(found->schema_sha256.begin(), found->schema_sha256.end(), pending.payload.begin() + 16) ||
            !pending.identity.application_instance || !pending.identity.document_sequence || !pending.identity.service_generation)
            throw std::runtime_error("native physical work does not match the admitted catalog");
        Bytes owned(static_cast<std::size_t>(capacity)), result_body(24);
        Bytes result_input(header_bytes + result_body.size()), result_output(receipt_bytes + 24);
        BibEngineCommandV1 request{};
        request.size = sizeof(request); request.operation = static_cast<std::uint32_t>(operation);
        request.expected = document(pending.identity); request.request_sequence = sequence;
        std::copy(found->schema_sha256.begin(), found->schema_sha256.end(), request.schema_sha256);
        request.payload = {pending.payload.data() + 56, static_cast<std::uint32_t>(count), 0};
        BibEngineReplyBufferV1 buffer{sizeof(buffer), static_cast<std::uint32_t>(capacity), owned.data()};
        BibEngineCommandResultV1 result{sizeof(result), 0, 0, 0, 0};
        const auto invocation = invoke_document(pending.identity, pending.transfer, false, false, [&] {
            return provider.command(&request, &buffer, &result);
        });
        const auto status = invocation.status;
        if (faulted.load()) return false;
        if (!command_result_valid(buffer, result, owned, sequence, status) || result.bytes_written)
            throw std::runtime_error("malformed native physical command result");
        put(result_body, 0, static_cast<std::uint32_t>(status), 4); put(result_body, 4, result.disposition, 4);
        put(result_body, 8, sequence, 8); put(result_body, 20, result.handled, 4);
        exact_empty(exchange(FOUNDATION_ENGINE_COMMAND_RESULT, pending.identity, result_body, pending.transfer, 0,
            result_input, result_output), pending.identity, pending.transfer);
        if (status == BIB_ENGINE_PROCESS_EXIT_REQUIRED || result.disposition == 2) { fail(); return false; }
        notify_owner();
        return true;
    }
    bool editor_step() {
        if (!editor_selected()) return false;
        const auto pending = call(FOUNDATION_ENGINE_PEEK_EDITOR_WORK, kernel->identity(), {}, 0, 0,
            receipt_bytes + FOUNDATION_ENGINE_EDITOR_WORK_PREFIX_BYTES + BIB_ENGINE_EDITOR_MAX_WIRE_BYTES);
        if (pending.control == FOUNDATION_ENGINE_EMPTY) {
            if ((pending.service != FOUNDATION_APPENDED_SERVICE_OK && pending.service != FOUNDATION_APPENDED_SERVICE_UNAVAILABLE) ||
                pending.transfer || !pending.payload.empty())
                throw std::runtime_error("malformed empty native editor mailbox");
            if (pending.service == FOUNDATION_APPENDED_SERVICE_UNAVAILABLE) owner_work_blocked = true;
            return false;
        }
        require_ok(pending);
        constexpr auto prefix = FOUNDATION_ENGINE_EDITOR_WORK_PREFIX_BYTES;
        if (!pending.transfer || pending.payload.size() < prefix || !pending.identity.application_instance ||
            !pending.identity.document_sequence || !pending.identity.service_generation)
            throw std::runtime_error("short native editor work or missing original target");
        const auto kind = static_cast<EngineEditorWorkKind>(read(pending.payload, 0, 4));
        const auto operation = static_cast<std::uint32_t>(read(pending.payload, 4, 4));
        const auto sequence = read(pending.payload, 8, 8);
        const auto capacity = read(pending.payload, 48, 4), count = read(pending.payload, 52, 4);
        const bool query = kind == EngineEditorWorkKind::projection_query;
        const engine_editor::OperationFacts* facts{};
        if (query && operation == BIB_ENGINE_QUERY_EDITOR_PROJECTION_V1) {
            const auto found = std::find_if(engine_editor::kQueries.begin(), engine_editor::kQueries.end(), [&](const auto& value) {
                return value.operation == operation;
            });
            if (found != engine_editor::kQueries.end()) facts = &*found;
        } else if ((kind == EngineEditorWorkKind::observation && operation == BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1) ||
                   (kind == EngineEditorWorkKind::revoke && operation == BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1)) {
            const auto found = std::find_if(engine_editor::kCommands.begin(), engine_editor::kCommands.end(), [&](const auto& value) {
                return value.operation == operation;
            });
            if (found != engine_editor::kCommands.end()) facts = &*found;
        }
        if (!facts || !sequence || sequence > BIB_ENGINE_DOCUMENT_V2_MAX_ORDINARY_SEQUENCE ||
            !count || count > facts->maximum_input_bytes || pending.payload.size() != prefix + count ||
            capacity != facts->required_reply_capacity || capacity > options.limits.maximum_reply_bytes ||
            count > (query ? options.limits.maximum_query_bytes : options.limits.maximum_command_bytes) ||
            !std::equal(facts->schema_sha256.begin(), facts->schema_sha256.end(), pending.payload.begin() + 16))
            throw std::runtime_error("native editor work does not match its exact admitted catalog");
        const editor_codec::WireTarget target{pending.identity.worker_epoch, pending.identity.application_instance,
            pending.identity.document_sequence, pending.identity.service_generation, sequence};
        const auto payload = Span(pending.payload).subspan(prefix);
        editor_codec::ProjectionQuery projection_request;
        if (query) {
            if (!editor_codec::decode_projection_query(payload, projection_request) || projection_request.target != target)
                throw std::runtime_error("native editor projection request changed its original target/sequence");
        } else if (kind == EngineEditorWorkKind::observation) {
            editor_codec::NativeRequestEnvelope request;
            if (!editor_codec::decode_native_request(payload, request) || request.target != target)
                throw std::runtime_error("native editor observation request changed its original target/sequence");
        } else {
            editor_codec::RevocationEnvelope request;
            if (!editor_codec::decode_revocation(payload, request) || request.target != target)
                throw std::runtime_error("native editor revocation request changed its original target/sequence");
        }

        // Own the complete provider reply and final copied RESULT before the
        // one claim. No size probe, implicit retry or metadata-only ACK path.
        Bytes owned(static_cast<std::size_t>(capacity));
        Bytes result_body(FOUNDATION_ENGINE_EDITOR_RESULT_PREFIX_BYTES + owned.size());
        Bytes result_input(header_bytes + result_body.size()), result_output(receipt_bytes);
        Bytes claim(FOUNDATION_ENGINE_EDITOR_BEGIN_BYTES);
        put(claim, 0, static_cast<std::uint32_t>(kind), 4); put(claim, 8, sequence, 8);
        exact_empty(call(FOUNDATION_ENGINE_BEGIN_EDITOR_WORK, pending.identity, claim, pending.transfer, 0, receipt_bytes),
            pending.identity, pending.transfer);

        BibEngineReplyBufferV1 buffer{sizeof(buffer), static_cast<std::uint32_t>(capacity), owned.data()};
        std::int32_t status{};
        std::uint32_t disposition{}, written{}, handled{};
        std::uint64_t revision{};
        bool semantic_unknown{};
        if (query) {
            BibEngineQueryV1 request{};
            request.size = sizeof(request); request.kind = operation; request.expected = document(pending.identity);
            std::copy(facts->schema_sha256.begin(), facts->schema_sha256.end(), request.schema_sha256);
            request.payload = {pending.payload.data() + prefix, static_cast<std::uint32_t>(count), 0};
            BibEngineQueryResultV1 result{sizeof(result), 0, {}, 0};
            const auto invocation = invoke_document(pending.identity, pending.transfer, false, true, [&] {
                return provider.query(&request, &buffer, &result);
            });
            status = invocation.status;
            if (faulted.load()) return false;
            const bool empty_document = !result.document.application_instance && !result.document.document_sequence && !result.document.service_generation;
            if (buffer.size != sizeof(buffer) || buffer.capacity != owned.size() || buffer.bytes != owned.data() ||
                result.size != sizeof(result) || result.bytes_written > owned.size() ||
                (status == BIB_ENGINE_OK ? (!invocation.completed_turn || !result.bytes_written || !result.semantic_revision ||
                    !same(result.document, request.expected)) :
                    ((!empty_document && !same(result.document, request.expected)) ||
                     (status == BIB_ENGINE_PROCESS_EXIT_REQUIRED ? !invocation.completed_turn :
                      (result.bytes_written || result.semantic_revision)))))
                throw std::runtime_error("malformed native editor projection result");
            written = result.bytes_written; revision = result.semantic_revision;
            if (status == BIB_ENGINE_OK) {
                editor_codec::ProjectionReply reply;
                if (!editor_codec::decode_projection_reply(Span(owned).first(written), reply) || reply.target != target ||
                    reply.identity != projection_request.identity || reply.observation_revision != revision)
                    throw std::runtime_error("native editor projection reply changed its checked target/readback");
            }
        } else {
            BibEngineCommandV1 request{};
            request.size = sizeof(request); request.operation = operation; request.expected = document(pending.identity);
            request.request_sequence = sequence;
            std::copy(facts->schema_sha256.begin(), facts->schema_sha256.end(), request.schema_sha256);
            request.payload = {pending.payload.data() + prefix, static_cast<std::uint32_t>(count), 0};
            BibEngineCommandResultV1 result{sizeof(result), 0, 0, 0, 0};
            const auto invocation = invoke_document(pending.identity, pending.transfer, false, true, [&] {
                return provider.command(&request, &buffer, &result);
            });
            status = invocation.status;
            if (faulted.load()) return false;
            if (!command_result_valid(buffer, result, owned, sequence, status) ||
                (!invocation.completed_turn && result.disposition != 0))
                throw std::runtime_error("malformed native editor command result");
            disposition = result.disposition; written = result.bytes_written; handled = result.handled;
            if (status == BIB_ENGINE_OK && disposition == 1) {
                editor_codec::NativeResultEnvelope reply;
                if (!editor_codec::decode_native_result(Span(owned).first(written), reply) || reply.target != target)
                    throw std::runtime_error("native editor command reply changed its checked target/sequence");
                semantic_unknown = reply.result.outcome == foundation::ui::native_editor::Outcome::unknown;
            }
        }
        put(result_body, 0, static_cast<std::uint32_t>(kind), 4); put(result_body, 8, sequence, 8);
        put(result_body, 16, static_cast<std::uint32_t>(status), 4); put(result_body, 20, disposition, 4);
        put(result_body, 24, written, 4); put(result_body, 28, handled, 4); put(result_body, 32, revision, 8);
        std::copy_n(owned.begin(), written, result_body.begin() + FOUNDATION_ENGINE_EDITOR_RESULT_PREFIX_BYTES);
        result_body.resize(FOUNDATION_ENGINE_EDITOR_RESULT_PREFIX_BYTES + written);
        exact_empty(exchange(FOUNDATION_ENGINE_EDITOR_WORK_RESULT, pending.identity, result_body, pending.transfer, 0,
            result_input, result_output), pending.identity, pending.transfer);
        if (status == BIB_ENGINE_PROCESS_EXIT_REQUIRED || disposition == 2 || semantic_unknown) { fail(); return false; }
        notify_owner();
        return true;
    }
    bool queued_document_step() { return document_step() || physical_step() || editor_step(); }
    bool service_step() {
        if (retirement_step()) return true;
        if (state.load() == NativeEngineState::blocked || faulted.load()) return false;
        const auto identity = kernel->identity();
        if (!identity.service_generation) return queued_document_step();
        pumping = true;
        Reply pumped;
        try { pumped = call(FOUNDATION_ENGINE_PUMP_ONE, identity); pumping = false; }
        catch (...) { pumping = false; throw; }
        if (pumped.control == FOUNDATION_ENGINE_CONFLICT && pumped.service == FOUNDATION_APPENDED_SERVICE_UNAVAILABLE) {
            owner_work_blocked = document_selected();
            return queued_document_step();
        }
        require_ok_control(pumped);
        owner_work_blocked = false;
        if (pumped.service == FOUNDATION_APPENDED_SERVICE_UNCERTAIN) throw std::runtime_error("uncertain native service outcome");
        if (close_requested.load()) return false; // A just-finished native handler may revoke further work.
        const auto ack = call(FOUNDATION_ENGINE_PEEK_ACK_RECEIPT, identity);
        if (ack.control == FOUNDATION_ENGINE_OK) {
            if (ack.payload.size() != 12 || !ack.transfer || read(ack.payload, 8, 4) != ack.service) throw std::runtime_error("malformed native ACK receipt");
            const auto through = read(ack.payload, 0, 8);
            Operation turn(*this, ack.identity, ack.transfer);
            const auto actual = collect_ack(ack.identity, true, through, ack.service);
            if (!turn.finish()) return false;
            const auto disposition = actual == 0 ? FOUNDATION_ENGINE_ACCEPTED : FOUNDATION_ENGINE_REJECTED;
            require_ok(call(FOUNDATION_ENGINE_ACK_RECEIPT_RESULT, ack.identity, integer(disposition, 4), ack.transfer));
            if (actual) { last_service.store(actual); state.store(NativeEngineState::blocked); return false; }
            return true;
        }
        if (ack.control != FOUNDATION_ENGINE_EMPTY) throw std::runtime_error("native ACK mailbox refused");
        const auto delivery = call(FOUNDATION_ENGINE_PEEK_DELIVERY, identity);
        if (delivery.control == FOUNDATION_ENGINE_EMPTY) return queued_document_step();
        require_ok(delivery);
        if (!delivery.transfer || delivery.payload.size() > options.limits.maximum_service_message_bytes) throw std::runtime_error("malformed native completion");
        const auto native = document(delivery.identity);
        const BibEngineBytesV1 bytes{delivery.payload.data(), static_cast<std::uint32_t>(delivery.payload.size()), 0};
        const auto status = invoke(delivery.identity, delivery.transfer, [&] {
            const auto result = provider.deliver_services(&native, &bytes);
            if (result == BIB_ENGINE_OK) collect_ack(delivery.identity, false);
            return result;
        });
        if (faulted.load()) return false;
        const auto disposition = status == BIB_ENGINE_OK ? FOUNDATION_ENGINE_ACCEPTED : FOUNDATION_ENGINE_REJECTED;
        require_ok(call(FOUNDATION_ENGINE_DELIVERY_RESULT, delivery.identity, integer(disposition, 4), delivery.transfer));
        if (status != BIB_ENGINE_OK) { state.store(NativeEngineState::blocked); return false; }
        return true;
    }
    static void require_ok_control(const Reply& reply) {
        if (reply.control != FOUNDATION_ENGINE_OK) throw std::runtime_error("native owner control rejected");
    }
};

NativeEngineDriver::NativeEngineDriver(std::unique_ptr<Impl> value) : impl_(std::move(value)) {}
NativeEngineDriver::~NativeEngineDriver() = default;
NativeEngineDriver& NativeEngineDriver::bind_once(NativeEngineProvider provider, std::shared_ptr<EngineOwner> owner,
        NativeEngineOptions options, NativeEngineWake wake) {
    auto implementation = std::make_unique<Impl>(std::move(provider), std::move(owner), std::move(options), wake);
    static std::atomic_flag attempted = ATOMIC_FLAG_INIT;
    if (attempted.test_and_set()) throw std::logic_error("native provider binding is process-lived and cannot be replaced");
    // Intentionally process-lived; no static destructor races provider workers.
    return *new NativeEngineDriver(std::move(implementation));
}
void NativeEngineDriver::start_once(Clock::time_point now) {
    auto& self = *impl_; self.check_thread();
    if (self.started || self.state.load() != NativeEngineState::bound) throw std::logic_error("native provider START cannot be replayed");
    self.started = true; self.now = now;
    if (self.close_requested.load()) {
        self.kernel->close(); self.state.store(NativeEngineState::detached); self.wake_enabled.store(false); return;
    }
    try {
        Impl::require_ok(self.call(FOUNDATION_ENGINE_CONFIGURE, self.kernel->identity()));
        if (self.options.abandon_closed_document_outcomes) {
            const auto audit = self.call(FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT, self.kernel->identity());
            if (audit.control != FOUNDATION_ENGINE_EMPTY) throw std::runtime_error("native owner immutable abandonment policy mismatch");
        }
        if (self.close_requested.load()) {
            self.kernel->close(); self.state.store(NativeEngineState::detached); self.wake_enabled.store(false); return;
        }
        const auto& package = self.kernel->package();
        const auto entry = "app://" + package.package_sha256 + "/" + *package.web.entry;
        BibEngineStartV1 configuration{};
        configuration.size = sizeof(configuration); configuration.raster_output = 1;
        configuration.required_capabilities = self.document_actions_profile.enabled ? self.document_actions_profile.provider_capabilities :
            self.editor_profile.enabled ? self.editor_profile.provider_capabilities :
            self.document_profile.enabled ? self.document_profile.provider_capabilities : pixel_capabilities;
        configuration.limits = self.options.limits;
        configuration.entry_url = {reinterpret_cast<const std::uint8_t*>(entry.data()), static_cast<std::uint32_t>(entry.size()), 0};
        if (package.package_sha256.size() != 64) throw std::runtime_error("invalid native Package digest");
        for (std::size_t n = 0; n < 32; ++n) {
            auto digit = [](char c) -> unsigned { if (c >= '0' && c <= '9') return static_cast<unsigned>(c - '0'); if (c >= 'a' && c <= 'f') return static_cast<unsigned>(c - 'a' + 10); throw std::runtime_error("invalid native Package digest"); };
            configuration.application_package_sha256[n] = static_cast<std::uint8_t>((digit(package.package_sha256[n * 2]) << 4) | digit(package.package_sha256[n * 2 + 1]));
        }
        BibEngineStartResultV1 result{sizeof(result), 0, 0};
        const auto status = self.invoke(self.kernel->identity(), 0, [&] { return self.provider.start(&self.callbacks, &configuration, &result); });
        if (status != BIB_ENGINE_OK || self.faulted.load() || result.size != sizeof(result) || result.phase != BIB_ENGINE_START_READY ||
            !result.application_instance || result.application_instance != self.kernel->identity().application_instance) { self.fail(); return; }
        self.state.store(NativeEngineState::waiting_document); self.ready_deadline = now + self.options.ready_timeout;
        self.current_ready();
        self.notify_owner();
    } catch (...) { self.fail(); }
}
void NativeEngineDriver::tick(Clock::time_point now) {
    auto& self = *impl_; self.check_thread();
    if (self.active || self.pumping || self.callback_busy) throw std::logic_error("native tick cannot enter from callbacks");
    // A delivered wake is consumed even when this state needs no provider work.
    // Later explicit close/advance requests must be able to post a fresh wake.
    self.owner_notified.store(false, std::memory_order_release);
    const auto state = self.state.load();
    if (state == NativeEngineState::bound) {
        if (self.close_requested.exchange(false)) { self.kernel->close(); self.state.store(NativeEngineState::detached); self.wake_enabled.store(false); }
        return;
    }
    if (state == NativeEngineState::detached || state == NativeEngineState::process_exit_required ||
        (state == NativeEngineState::blocked && !self.close_requested.load())) return;
    self.now = now;
    self.owner_work_blocked = false;
    try {
        self.process_close();
        if (self.state.load() == NativeEngineState::waiting_document) {
            if (self.ready_deadline && now >= *self.ready_deadline) { self.fail(); return; }
            if (!self.current_ready()) {
                if (self.faulted.load()) return;
                self.process_close();
                if (self.state.load() != NativeEngineState::closing) {
                    const BibEngineAdvanceV1 advance{sizeof(advance), 0, self.kernel->identity().application_instance};
                    if (self.invoke(self.kernel->identity(), 0, [&] { return self.provider.advance(&advance); }) != BIB_ENGINE_OK) self.fail();
                    return;
                }
            }
        }
        std::size_t count{};
        for (; count < self.options.maximum_steps_per_tick && !self.faulted.load(); ++count) {
            self.process_close();
            if (!self.service_step()) break;
        }
        if (count == self.options.maximum_steps_per_tick && !self.faulted.load()) {
            self.notify_owner(); return; // Settle exact delivery/ACK barriers before another engine advance.
        }
        if (self.faulted.load() || self.state.load() == NativeEngineState::blocked) return;
        self.process_close();
        if (self.state.load() == NativeEngineState::closing) {
            if (self.kernel->closed()) { self.state.store(NativeEngineState::detached); self.wake_enabled.store(false); }
            else if (self.generations.empty() && !self.leases.empty()) self.fail(); // No v1 shutdown can reclaim provider-held spans.
            return;
        }
        // An owned document result/reservation is a real engine-entry barrier.
        // Keep a requested advance pending until its sole presenter settles it.
        if (self.owner_work_blocked) return;
        const bool timed = self.timer && now >= *self.timer;
        if (timed) self.timer.reset();
        if (timed || self.advance_requested.exchange(false)) {
            const BibEngineAdvanceV1 advance{sizeof(advance), self.seen_ready ? 1U : 0U, self.kernel->identity().application_instance};
            if (self.invoke(self.kernel->identity(), 0, [&] { return self.provider.advance(&advance); }) != BIB_ENGINE_OK) self.fail();
        }
    } catch (...) { self.fail(); }
}
void NativeEngineDriver::request_advance() noexcept { impl_->schedule(); }
void NativeEngineDriver::request_close() noexcept { impl_->close_requested.store(true); impl_->schedule(); }
NativeEngineState NativeEngineDriver::state() const noexcept { return impl_->state.load(); }
std::optional<Clock::time_point> NativeEngineDriver::deadline() const noexcept {
    const auto state = impl_->state.load();
    if (state == NativeEngineState::detached || state == NativeEngineState::process_exit_required || state == NativeEngineState::blocked) return {};
    if (impl_->ready_deadline && impl_->timer) return std::min(*impl_->ready_deadline, *impl_->timer);
    return impl_->ready_deadline ? impl_->ready_deadline : impl_->timer;
}
std::shared_ptr<EngineOwner> NativeEngineDriver::owner() const noexcept { return impl_->kernel; }
std::int32_t NativeEngineDriver::last_provider_status() const noexcept { return impl_->last_provider.load(); }
std::uint32_t NativeEngineDriver::last_service_status() const noexcept { return impl_->last_service.load(); }

} // namespace foundation::appended
