// SPDX-License-Identifier: CC0-1.0
#pragma once
// Native bitmap composition root only. Retained admission generates the private
// profile. This entry never builds/fetches an engine or evaluates application JS.
#ifndef FOUNDATION_APPENDED_ENGINE_NATIVE_PROFILE_ENABLED
#define FOUNDATION_APPENDED_ENGINE_NATIVE_PROFILE_ENABLED 0
#endif
#if FOUNDATION_APPENDED_ENGINE_NATIVE_PROFILE_ENABLED != 1
#error "Native bitmap entry requires explicit retained native admission"
#endif
#ifndef FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE
#define FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE 0
#endif
#if FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE != 0 && FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE != 1
#error "Unknown native bitmap document profile"
#endif
#ifndef FOUNDATION_APPENDED_ENGINE_NATIVE_RUNTIME_HINT
#error "Native bitmap entry requires its compiled installed runtime hint"
#endif
#if defined(FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED) && FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED
#error "Native bitmap entry cannot use legacy physical input facts"
#endif

#include "host/native_surface_composition.hpp"
#include "shared/native_engine_bitmap_composition.hpp"
#include "shared/native_engine_loader.hpp"
#include "shared/appended_engine_module.hpp"
#include "shared/appended_demo_services.hpp"
#include <foundation/appended/startup.hpp>
#include <appended_engine_compiled_native_profile.hpp>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <functional>
#include <iostream>
#include <memory>
#include <optional>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <utility>

namespace foundation::host::native_bitmap_entry {
namespace appended = ::foundation::appended;
namespace document = appended::engine_document;
namespace actions = appended::engine_document_actions;
using Clock = std::chrono::steady_clock;

struct EntryOptions {
    bool read_only{};
    bool output_required{}; // The bare framebuffer host has an explicit output.
};
struct Invocation {
    std::filesystem::path runtime_root;
    std::optional<std::filesystem::path> output;
    bool read_only{};
};
inline std::filesystem::path argument_path(std::string_view value) {
    if (value.empty() || value.find('\0') != std::string_view::npos ||
            !appended::valid_utf8({reinterpret_cast<const std::uint8_t*>(value.data()), value.size()}))
        throw std::invalid_argument("Native bitmap paths must be nonempty UTF-8");
    return std::filesystem::path(std::u8string(value.begin(), value.end()));
}
inline Invocation arguments(int argc, char** argv, EntryOptions options) {
    if (argc < 1 || argc > 8) throw std::invalid_argument("Invalid native bitmap arguments");
    Invocation result; result.read_only = options.read_only;
    bool have_root{}, have_view_only{};
    for (int index = 1; index < argc; ++index) {
        const std::string_view argument(argv[index]);
        if (argument == "--engine-runtime-root") {
            if (have_root || ++index == argc) throw std::invalid_argument("Expected one absolute engine runtime root");
            result.runtime_root = argument_path(argv[index]); have_root = true;
            if (!result.runtime_root.is_absolute() || result.runtime_root.lexically_normal() != result.runtime_root)
                throw std::invalid_argument("Engine runtime root must be normalized and absolute");
        } else if (argument == "--view-only") {
            if (have_view_only) throw std::invalid_argument("Duplicate view-only option");
            have_view_only = true; result.read_only = true;
        } else if (options.output_required && !result.output && !argument.empty() && argument.front() != '-') {
            result.output = argument_path(argument);
        } else throw std::invalid_argument("Unknown native bitmap argument");
    }
    if (options.output_required && !result.output) throw std::invalid_argument("Expected framebuffer output path");
    if (!have_root) result.runtime_root = appended::self_relative_path(std::filesystem::path(u8"" FOUNDATION_APPENDED_ENGINE_NATIVE_RUNTIME_HINT));
    if (!result.runtime_root.is_absolute() || result.runtime_root.lexically_normal() != result.runtime_root)
        throw std::invalid_argument("Installed engine runtime root is not normalized and absolute");
#if !FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE
    result.read_only = true; // The separately admitted pixel1795 profile has no input.
#endif
    return result;
}
inline void check_profile(const appended::NativeEngineLoadPlan& plan) {
    const auto& expected = plan.expectation;
#if FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE
    const auto& facts = appended::compiled_native_engine_document_actions_profile;
    const bool valid = actions::document_actions_profile_valid(facts) &&
        actions::document_actions_profile_agrees(facts, expected.document_actions_profile) &&
        expected.document_profile == document::EngineDocumentProfileFacts{} &&
        expected.editor_profile == appended::engine_editor::EngineEditorProfileFacts{};
#else
    const auto& facts = appended::compiled_native_engine_document_profile;
    const bool valid = document::document_profile_valid(facts) && facts.kind == document::ProfileKind::pixel &&
        document::document_profile_agrees(facts, expected.document_profile) &&
        expected.editor_profile == appended::engine_editor::EngineEditorProfileFacts{} &&
        expected.document_actions_profile == actions::EngineDocumentActionsProfileFacts{};
#endif
    if (!valid || facts.target_system == BIB_ENGINE_TARGET_BROWSER_WASM ||
        facts.pointer_bits != sizeof(void*) * 8 || expected.target_system != facts.target_system ||
        expected.target_processor != facts.target_processor || expected.pointer_bits != facts.pointer_bits ||
        expected.contract_header_sha256 != facts.contract_sha256 ||
        expected.build_identity_sha256 != facts.build_sha256 || expected.source_recipe_sha256 != facts.source_recipe_sha256)
        throw appended::NativeEngineLoadError("Native bitmap needs its exact admitted native plan/profile");
#if defined(_WIN32)
    if (facts.target_system != BIB_ENGINE_TARGET_WINDOWS || facts.target_processor != BIB_ENGINE_CPU_X86_64)
        throw appended::NativeEngineLoadError("Native bitmap profile does not match this Windows host");
#elif defined(__linux__) && defined(__aarch64__)
    if (facts.target_system != BIB_ENGINE_TARGET_LINUX || facts.target_processor != BIB_ENGINE_CPU_AARCH64)
        throw appended::NativeEngineLoadError("Native bitmap profile does not match this Linux host");
#elif defined(__linux__) && defined(__x86_64__)
    if (facts.target_system != BIB_ENGINE_TARGET_LINUX || facts.target_processor != BIB_ENGINE_CPU_X86_64)
        throw appended::NativeEngineLoadError("Native bitmap profile does not match this Linux host");
#else
    throw appended::NativeEngineLoadError("Native bitmap host has no admitted platform profile");
#endif
}

// These callbacks contain weak generic publication handles only. Process-lived
// App/retirement retention can never keep a borrowed native window alive.
class NativeEngineEditorPort final : public ui::EngineEditorPort {
    NativeSurfacePublisher publisher_;
public:
    explicit NativeEngineEditorPort(NativeSurfacePublisher publisher) : publisher_(std::move(publisher)) {
        if (!publisher_.generation || !publisher_.present_pair || !publisher_.present_editor_pair ||
            !publisher_.present_editor_retirement || !publisher_.set_owned_service_active)
            throw std::invalid_argument("Native editor publication handle is incomplete");
    }
    const gui_surface::Capabilities& capabilities() const noexcept override { return publisher_.capabilities; }
    std::uint64_t generation() const noexcept override { return publisher_.generation; }
    gui_surface::CommitResult present_pair(gui::Snapshot snapshot, const gui_surface::Presentation& presentation) override {
        return publisher_.present_pair(std::move(snapshot), presentation);
    }
    gui_surface::CommitResult present_editor_pair(gui::Snapshot snapshot, const gui_surface::Presentation& presentation,
            std::optional<gui_editor::EditorPublication> publication,
            std::optional<gui_editor::CompositionFact> composition) override {
        return publisher_.present_editor_pair(std::move(snapshot), presentation, std::move(publication), std::move(composition));
    }
    gui_surface::CommitResult present_editor_retirement(gui::Snapshot snapshot, gui_editor::EditorPublication publication) override {
        return publisher_.present_editor_retirement(std::move(snapshot), std::move(publication));
    }
    void set_owned_service_active(bool value) override {
        if (!publisher_.set_owned_service_active(value)) throw std::logic_error("Native surface publisher is closed");
    }
};
struct WakeToken { std::atomic<bool> pending{false}; };
struct Prepared {
    std::shared_ptr<appended::EngineOwner> owner;
    appended::NativeEngineDriver& driver;
    WakeToken& wake; // Allocated before bind and intentionally process-held.
    bool read_only{}, application_attempted{}, application_complete{};
};
class PreparedApplication final {
    Prepared& binding_;
    std::unique_ptr<ui::NativeEngineBitmapComposition> composition_;
    static std::unique_ptr<ui::NativeEngineBitmapComposition> compose(NativeSurfaceAdapter& adapter, Prepared& value) {
        const auto post = [token = &value.wake] { token->pending.store(true, std::memory_order_release); };
#if FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE
        const auto& facts = appended::compiled_native_engine_document_actions_profile;
        if (value.read_only)
            return std::make_unique<ui::NativeEngineBitmapComposition>(adapter, value.owner, value.driver,
                facts, ui::ReadOnlyEngineBitmap{}, post);
        if (!adapter.editor_endpoint_bound()) throw std::invalid_argument("Native backend has no bound editor endpoint");
        return std::make_unique<ui::NativeEngineBitmapComposition>(adapter, value.owner, value.driver, facts,
            ui::BoundEngineEditorPort{std::make_unique<NativeEngineEditorPort>(adapter.publisher())}, post);
#else
        return std::make_unique<ui::NativeEngineBitmapComposition>(adapter, value.owner, value.driver,
            appended::compiled_native_engine_document_profile, ui::ReadOnlyEngineBitmap{}, post);
#endif
    }
public:
    PreparedApplication(NativeSurfaceAdapter& adapter, Prepared& binding)
        : binding_(binding), composition_(compose(adapter, binding)) {}
    ~PreparedApplication() { binding_.application_complete = composition_->close_complete(); }
    void handle(gui::Event value) { composition_->handle(std::move(value)); }
    void tick() { binding_.wake.pending.store(false, std::memory_order_release); composition_->tick(); }
    void shutdown() noexcept { composition_->shutdown(); }
    void retry_presentation() { composition_->retry_presentation(); }
    void qualify(const std::function<void()>& present) { composition_->qualify(present); }
    std::optional<gui::ServiceRequest> next_service() { return composition_->next_service(); }
    bool complete_service(gui::ServiceResult value) { return composition_->complete_service(std::move(value)); }
    void drawable_pixels(std::int64_t width, std::int64_t height) { composition_->drawable_pixels(width, height); }
    void foreground(bool value) { composition_->foreground(value); }
    void request_frame() noexcept { composition_->request_frame(); }
    bool frame_ready() const noexcept { return composition_->frame_ready(); }
    std::uint64_t input_epoch() const noexcept { return composition_->input_epoch(); }
    bool presentation_pending() const noexcept { return composition_->presentation_pending(); }
    RunnerState runner_state() const noexcept {
        const auto state = composition_->native_state();
        RunnerState value{composition_->closed(), composition_->close_complete(),
            state == appended::NativeEngineState::process_exit_required || state == appended::NativeEngineState::blocked ||
                composition_->close_timed_out() ? 1 : 0, composition_->deadline()};
        if (binding_.wake.pending.load(std::memory_order_acquire)) {
            const auto now = Clock::now(); if (!value.deadline || now < *value.deadline) value.deadline = now;
        }
        return value;
    }
    void surface_connected(gui_surface::Capabilities value) { composition_->surface_connected(std::move(value)); }
    void surface_input(gui_surface::AcceptedEvent value) { composition_->surface_input(std::move(value)); }
    void surface_revoked(gui_surface::Revocation value) { composition_->surface_revoked(std::move(value)); }
    std::optional<std::uint64_t> editor_submit(gui_editor::Packet value) { return composition_->editor_submit(std::move(value)); }
    std::optional<std::uint64_t> editor_revoke(gui_editor::Revocation value) { return composition_->editor_revoke(std::move(value)); }
    std::optional<gui_editor::EditorCompletion> editor_take(std::uint64_t ticket) { return composition_->editor_take(ticket); }
    void editor_resync() { composition_->editor_resync(); }
};
static_assert(NativeSurfaceApplication<PreparedApplication>);
using Factory = NativeSurfaceSessionFactory<PreparedApplication>;

inline int finish_close(Prepared& binding, int result) {
    auto state = binding.driver.state();
    // Provider detachment does not settle a submitted editor head. The runner
    // must finish that local metadata drain before destroying its application.
    if (state == appended::NativeEngineState::detached &&
            (!binding.application_attempted || binding.application_complete)) return result;
    // Once a GUI/App was attempted its facade owns real retirement. A runner
    // must drain it while its renderer exists. Never enter exports after that
    // facade/window has gone just to convert an abandoned close into success.
    if (!binding.application_attempted && state != appended::NativeEngineState::process_exit_required &&
            state != appended::NativeEngineState::blocked) {
        binding.driver.request_close(); const auto deadline = Clock::now() + std::chrono::seconds(10);
        while (Clock::now() < deadline) {
            binding.driver.tick(); state = binding.driver.state();
            if (state == appended::NativeEngineState::detached) return result;
            if (state == appended::NativeEngineState::process_exit_required || state == appended::NativeEngineState::blocked) break;
            std::this_thread::sleep_until(std::min(deadline, Clock::now() + std::chrono::milliseconds(30)));
        }
    }
    std::cerr << "Native bitmap close remains unresolved; state is retained until process exit.\n";
    return 1;
}

// Runner receives a fully prepared value factory and root-selected invocation.
// Its typed backend supplies prepare_peer; it must use the bounded runner-state
// close protocol while the concrete renderer/window is still alive.
template<class Runner> int run(int argc, char** argv, EntryOptions options, Runner&& runner) {
    if (argc == 2 && std::string_view(argv[1]) == "--help") {
        std::cout << "Usage: " << argv[0] << " [--engine-runtime-root ABSOLUTE_DIRECTORY] [--view-only]"
                  << (options.output_required ? " OUTPUT.ppm\n" : "\n")
                  << "Uses the verified native payload and independently admitted engine closure.\n";
        return 0;
    }
    try {
        const auto invocation = arguments(argc, argv, options);
        auto package = appended::load_self();
        if (!package) throw appended::ContainerError("No appended application; compose a native payload before running this kernel");
        auto plan = appended::compiled_native_engine_load_plan(invocation.runtime_root);
        if (plan.root != invocation.runtime_root) throw appended::NativeEngineLoadError("Compiled plan changed the explicit runtime root");
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
        auto owner = std::make_shared<appended::EngineOwner>(std::move(*package), std::move(configuration));
        appended::verify_native_engine_load_plan(plan);
        auto provider = appended::load_native_engine(plan);
        auto* wake = new WakeToken;
        appended::NativeEngineOptions native_options;
#if FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE
        native_options.limits.maximum_command_bytes = BIB_ENGINE_EDITOR_MAX_WIRE_BYTES;
        native_options.limits.maximum_query_bytes = BIB_ENGINE_EDITOR_MAX_QUERY_BYTES;
        native_options.limits.maximum_reply_bytes = actions::kReplyCapacity;
#else
        native_options.limits.maximum_reply_bytes = BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY;
#endif
        auto& driver = appended::NativeEngineDriver::bind_once(std::move(provider), owner, native_options,
            {wake, [](void* value) noexcept { static_cast<WakeToken*>(value)->pending.store(true, std::memory_order_release); }});
        Prepared binding{std::move(owner), driver, *wake, invocation.read_only, false, false};
        int result = 1;
        try {
            driver.start_once();
            if ((driver.state() != appended::NativeEngineState::ready && driver.state() != appended::NativeEngineState::waiting_document) ||
                    !binding.owner->configured() || !binding.owner->identity().application_instance)
                throw std::runtime_error("Native bitmap provider did not establish its started Owner identity");
            if (binding.owner->startup_primary()==appended::EngineStartupPrimary::binary) {
                auto view=binding.owner->binary_view();
                if (view && !view->snapshot().revision) {
                    // One bounded explicit startup turn, before any presenter
                    // exists. Read-only model getters never initialize a guest.
                    binding.owner->tick_binary_view(); view=binding.owner->binary_view();
                }
                if (!view || !view->snapshot().revision)
                    throw std::runtime_error("Binary primary did not publish its initial single-Module view");
            }
            const auto canvas=ui::EnginePrimaryRegionApplication::initial_client_size(binding.owner);
            Factory factory;
            // Explicit source canvas; the peer still supplies actual drawable
            // extent, letterbox/clip and native physical-coordinate facts.
            factory.window = {binding.owner->package().application.name + (binding.read_only ? " (view only)" : ""),
                canvas.width, canvas.height, 1};
            factory.mode = binding.read_only ? NativeSurfaceMode::none : NativeSurfaceMode::editor_v1;
            if (!binding.read_only) factory.editor.terminal = {binding.owner.get(), [](void* value) noexcept {
                static_cast<appended::EngineOwner*>(value)->notify_document_terminal(); }};
            factory.application = [&binding](NativeSurfaceAdapter& adapter) {
                binding.application_attempted = true;
                binding.application_complete = false;
                return std::make_unique<PreparedApplication>(adapter, binding);
            };
            result = std::invoke(std::forward<Runner>(runner), std::move(factory), invocation);
            if (!binding.application_attempted) throw std::runtime_error("Native runner did not construct the prepared application");
        } catch (const std::exception& error) { std::cerr << error.what() << '\n'; result = 1; }
        catch (...) { std::cerr << "Native bitmap runner failed with a nonstandard exception.\n"; result = 1; }
        return finish_close(binding, result);
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
    catch (...) { std::cerr << "Native bitmap preparation failed with a nonstandard exception.\n"; return 1; }
}

} // namespace foundation::host::native_bitmap_entry
