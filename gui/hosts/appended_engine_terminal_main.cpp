// SPDX-License-Identifier: CC0-1.0
// Explicit native composition root. This entry does not produce or qualify an
// engine; its private header is generated only after retained native admission.
#ifndef FOUNDATION_APPENDED_ENGINE_NATIVE_PROFILE_ENABLED
#define FOUNDATION_APPENDED_ENGINE_NATIVE_PROFILE_ENABLED 0
#endif
#if FOUNDATION_APPENDED_ENGINE_NATIVE_PROFILE_ENABLED != 1
#error "Native document entry requires explicitly admitted native profile facts"
#endif
#ifndef FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE
#define FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE 0
#endif
#if FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE != 0 && FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE != 1
#error "Native document actions selector must be zero or one"
#endif
#if FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE && !defined(FOUNDATION_APPENDED_ENGINE_NATIVE_RUNTIME_HINT)
#error "Native document entry requires its compiled executable-relative runtime location"
#endif
#if defined(FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED) && FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED
#error "Native document entry cannot use the legacy physical input profile"
#endif

#include "host/contract.hpp"
#include "shared/semantic_primary_document_application.hpp"
#include "shared/native_engine_loader.hpp"
#include "shared/appended_engine_module.hpp"
#include "shared/appended_demo_services.hpp"
#include <foundation/appended/startup.hpp>
#include <appended_engine_compiled_native_profile.hpp>
#include "terminal_runner.hpp"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <filesystem>
#include <iostream>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string_view>
#include <thread>

namespace {
namespace appended = foundation::appended;
namespace document = foundation::appended::engine_document;
using Clock = std::chrono::steady_clock;
constexpr auto close_budget = std::chrono::seconds(10);

// A provider may wake from a worker. Its callback never captures a Session,
// Adapter, facade or stack object and only requests a later polling-loop turn.
// Exactly one Driver can bind in a process; its token has the same lifetime.
struct WakeToken { std::atomic<bool> pending{false}; };
struct Prepared {
    std::shared_ptr<appended::EngineOwner> owner;
    appended::NativeEngineDriver& driver;
    WakeToken& wake;
    std::optional<Clock::time_point> close_deadline;
    bool application_attempted{}, application_complete{};
    void closing() noexcept {
        if (!close_deadline) close_deadline = Clock::now() + close_budget;
    }
};
Prepared* prepared{}; // Scoped injection, never a page/transport-selected owner.

class PreparedApplication final {
    Prepared& binding_;
    foundation::ui::SemanticPrimaryDocumentApplication composition_;
    static Prepared& binding() {
        if (!prepared) throw std::logic_error("Native document composition was not prepared");
        prepared->application_attempted=true; // Before constructing a retained composition.
        return *prepared;
    }
public:
    explicit PreparedApplication(gui::Adapter& adapter)
        : binding_(binding()), composition_(adapter, binding_.owner, binding_.driver,
            [token = &binding_.wake] { token->pending.store(true, std::memory_order_release); }) {}
    ~PreparedApplication() { binding_.application_complete=composition_.shutdown_complete(); }
    void handle(gui::Event event) { composition_.handle(std::move(event)); }
    void tick() {
        binding_.wake.pending.store(false, std::memory_order_release);
        composition_.tick();
    }
    void shutdown() noexcept { binding_.closing(); composition_.shutdown(); }
    void retry_presentation() { composition_.retry_presentation(); }
    void qualify(const std::function<void()>& present) { composition_.qualify(present); }
    std::optional<gui::ServiceRequest> next_service() { return composition_.next_service(); }
    bool complete_service(gui::ServiceResult result) { return composition_.complete_service(std::move(result)); }
    void drawable_cells(std::int64_t columns, std::int64_t rows) { composition_.drawable_cells(columns, rows); }
    void foreground(bool value) { composition_.foreground(value); }
    foundation::host::RunnerState runner_state() const noexcept {
        const auto state = composition_.native_state();
        foundation::host::RunnerState result;
        result.close_requested = composition_.closed();
        result.close_complete = composition_.shutdown_complete();
        result.exit_code = state == appended::NativeEngineState::process_exit_required ||
            state == appended::NativeEngineState::blocked ? 1 : 0;
        result.deadline = composition_.deadline();
        if (binding_.close_deadline && (!result.deadline || *binding_.close_deadline < *result.deadline))
            result.deadline = binding_.close_deadline;
        if (binding_.wake.pending.load(std::memory_order_acquire)) {
            const auto now = Clock::now();
            if (!result.deadline || now < *result.deadline) result.deadline = now;
        }
        return result;
    }
};
static_assert(foundation::host::Application<PreparedApplication>);

void check_profile(const appended::NativeEngineLoadPlan& plan) {
#if FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE
    namespace actions = appended::engine_document_actions;
    const auto& facts = appended::compiled_native_engine_document_actions_profile;
    const auto& expected = plan.expectation;
    if (!actions::document_actions_profile_valid(facts) ||
        facts.target_system == BIB_ENGINE_TARGET_BROWSER_WASM ||
        !actions::document_actions_profile_agrees(expected.document_actions_profile, facts) ||
        expected.document_profile != document::EngineDocumentProfileFacts{} ||
        expected.editor_profile != appended::engine_editor::EngineEditorProfileFacts{} ||
        expected.target_system != facts.target_system || expected.target_processor != facts.target_processor ||
        expected.pointer_bits != facts.pointer_bits || expected.contract_header_sha256 != facts.contract_sha256 ||
        expected.build_identity_sha256 != facts.build_sha256 || expected.source_recipe_sha256 != facts.source_recipe_sha256)
        throw appended::NativeEngineLoadError("Native terminal needs exact admitted document-actions4083 plan/profile agreement");
#else
    const auto& facts = appended::compiled_native_engine_document_profile;
    const auto& expected = plan.expectation;
    if (!document::document_profile_valid(facts) || facts.kind != document::ProfileKind::pixel ||
        facts.target_system == BIB_ENGINE_TARGET_BROWSER_WASM ||
        !document::document_profile_agrees(expected.document_profile, facts) ||
        expected.target_system != facts.target_system || expected.target_processor != facts.target_processor ||
        expected.pointer_bits != facts.pointer_bits || expected.contract_header_sha256 != facts.contract_sha256 ||
        expected.build_identity_sha256 != facts.build_sha256 || expected.source_recipe_sha256 != facts.source_recipe_sha256)
        throw appended::NativeEngineLoadError("Native terminal needs exact admitted pixel1795 plan/profile agreement");
#endif
}

int finish_close(Prepared& binding, int result) {
    if (binding.application_attempted && !binding.application_complete) {
        // This only queues close and wakes its owner; no Driver turn or provider
        // export may bypass the retained root's outstanding application debt.
        const auto state = binding.driver.state();
        if (state != appended::NativeEngineState::detached &&
                state != appended::NativeEngineState::process_exit_required && state != appended::NativeEngineState::blocked)
            binding.driver.request_close();
        // The complete root, Adapter bridge and actual outstanding UI debt are
        // process-retained. An outer fallback must not bypass its offer freeze.
        std::cerr << "Semantic application close remains owned; no fallback provider entry.\n";
        return 1;
    }
    const auto state = binding.driver.state();
    if (state == appended::NativeEngineState::detached) return result;
    if (state != appended::NativeEngineState::process_exit_required && state != appended::NativeEngineState::blocked) {
        binding.closing();
        binding.driver.request_close();
        // This also covers setup/TTY failure before a Session exists. These are
        // ordinary serialized Driver turns, not synthetic result/ACK cleanup.
        while (Clock::now() < *binding.close_deadline) {
            binding.driver.tick();
            const auto current = binding.driver.state();
            if (current == appended::NativeEngineState::detached) return result;
            if (current == appended::NativeEngineState::process_exit_required || current == appended::NativeEngineState::blocked) break;
            std::this_thread::sleep_until(std::min(*binding.close_deadline, Clock::now() + std::chrono::milliseconds(30)));
        }
    }
    std::cerr << "Native document close is unresolved; provider state is retained until process exit.\n";
    return 1;
}

std::filesystem::path runtime_root(int argc, char** argv) {
#if FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE
    if (argc == 1) return appended::self_relative_path(std::filesystem::path(u8"" FOUNDATION_APPENDED_ENGINE_NATIVE_RUNTIME_HINT));
    if (argc != 3 || std::string_view(argv[1]) != "--engine-runtime-root")
        throw std::invalid_argument("Usage: appended-engine-terminal [--engine-runtime-root ABSOLUTE_DIRECTORY]");
#else
    if (argc != 3 || std::string_view(argv[1]) != "--engine-runtime-root")
        throw std::invalid_argument("Usage: appended-engine-terminal --engine-runtime-root ABSOLUTE_DIRECTORY");
#endif
    const std::filesystem::path root(argv[2]);
    if (!root.is_absolute() || root.lexically_normal() != root)
        throw std::invalid_argument("Engine runtime root must be an explicit normalized absolute directory");
    return root;
}
} // namespace

int main(int argc, char** argv) {
    if (argc == 2 && std::string_view(argv[1]) == "--help") {
#if FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE
        std::cout << "Usage: " << argv[0] << " [--engine-runtime-root ABSOLUTE_DIRECTORY]\n"
#else
        std::cout << "Usage: " << argv[0] << " --engine-runtime-root ABSOLUTE_DIRECTORY\n"
#endif
                  << "Uses the verified native appended payload and an independently admitted engine closure.\n";
        return 0;
    }
    try {
        const auto root = runtime_root(argc, argv);
        // load_self uses the common strict native-carrier file reader. Never
        // pass an HTML suffix/logical Package directly to this native entry.
        auto package = appended::load_self();
        if (!package) throw appended::ContainerError("No appended application; compose a native payload before running this kernel");
        auto plan = appended::compiled_native_engine_load_plan(root);
        if (plan.root != root) throw appended::NativeEngineLoadError("Compiled plan changed the explicit engine runtime root");
        check_profile(plan);
        appended::EngineOwnerConfiguration configuration;
        configuration.native_services = foundation::ui::demo_native_services();
        configuration.startup_primary = appended::read_engine_startup_primary(*package);
#if FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE
        configuration.document_actions_profile = appended::compiled_native_engine_document_actions_profile;
#else
        configuration.document_profile = appended::compiled_native_engine_document_profile;
#endif
        configuration.abandon_closed_document_outcomes = true;
#if defined(FOUNDATION_APPENDED_BINARY_CAPABILITY) && FOUNDATION_APPENDED_BINARY_CAPABILITY
        configuration.module_factory = configuration.startup_primary==appended::EngineStartupPrimary::binary ?
            appended::make_engine_binary_view_module_binding : appended::make_engine_module_binding;
#endif
        // Owner validates startup/required services and optional binary support
        // before loading a DSO (whose loader constructors may have effects).
        auto owner = std::make_shared<appended::EngineOwner>(std::move(*package), std::move(configuration));
        appended::verify_native_engine_load_plan(plan);
        auto provider = appended::load_native_engine(plan);
        auto* wake = new WakeToken; // Held by the process-lived callback shell.
        appended::NativeEngineOptions options;
#if FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE
        options.limits.maximum_command_bytes = BIB_ENGINE_EDITOR_MAX_WIRE_BYTES;
        options.limits.maximum_query_bytes = BIB_ENGINE_EDITOR_MAX_QUERY_BYTES;
        options.limits.maximum_reply_bytes = appended::engine_document_actions::kReplyCapacity;
#else
        options.limits.maximum_reply_bytes = BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY;
#endif
        auto& driver = appended::NativeEngineDriver::bind_once(std::move(provider), owner, options,
            {wake, [](void* value) noexcept {
                static_cast<WakeToken*>(value)->pending.store(true, std::memory_order_release);
            }});
        Prepared binding{std::move(owner), driver, *wake, {}};
        driver.start_once();
        if ((driver.state() != appended::NativeEngineState::ready && driver.state() != appended::NativeEngineState::waiting_document) ||
            !binding.owner->configured() || !binding.owner->identity().application_instance) {
            std::cerr << "Native document provider did not establish its started Owner identity.\n";
            return finish_close(binding, 1);
        }
        if (binding.owner->startup_primary()==appended::EngineStartupPrimary::binary) {
            auto view=binding.owner->binary_view();
            if (view && !view->snapshot().revision) {
                binding.owner->tick_binary_view(); view=binding.owner->binary_view();
            }
            if (!view || !view->snapshot().revision)
                throw std::runtime_error("Binary primary did not publish its initial single-Module view");
        }
        struct Injection {
            explicit Injection(Prepared& value) {
                if (prepared) throw std::logic_error("Native application injection already active");
                prepared = &value;
            }
            ~Injection() { prepared = nullptr; }
        } injection(binding);
        // The root consumes only its runtime-root argument. The ordinary runner
        // sees its original no-argument CLI and owns terminal modes/polling.
        int result = 1;
        try { result = foundation::host::run_terminal<PreparedApplication>(1, argv); }
        catch (const std::exception& error) { std::cerr << "Native terminal runner: " << error.what() << '\n'; }
        catch (...) { std::cerr << "Native terminal runner failed with an unknown exception.\n"; }
        return finish_close(binding, result);
    } catch (const std::exception& error) {
        std::cerr << "Native appended terminal: " << error.what() << '\n';
        return 1;
    }
}
