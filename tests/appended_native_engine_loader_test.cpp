// Linux component fixtures use actual small DSOs and the actual table checker.
// Runtime-constructed test plans/pins cannot qualify a retained native engine.
#include "native_engine_loader.hpp"
#include "sha256.hpp"

#include <algorithm>
#include <array>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>

#if defined(__linux__)
#include <dlfcn.h>
#include <sys/stat.h>
#endif
namespace {
using namespace foundation::appended;
namespace fs = std::filesystem;
namespace doc = engine_document;
std::size_t assertions{};
void check(bool value, const char* message) {
    ++assertions;
    if (!value) throw std::runtime_error(message);
}
template<class F> void rejected(F call, std::string_view fragment = {}) {
    bool failed{};
    try { call(); }
    catch (const std::exception& error) {
        failed = true;
        check(fragment.empty() || std::string_view(error.what()).find(fragment) != std::string_view::npos,
            "rejection did not identify the intended prerequisite");
    }
    check(failed, "invalid load plan/provider was accepted");
}
doc::Digest hash(const fs::path& path) {
    std::ifstream stream(path, std::ios::binary);
    check(bool(stream), "fixture file read failed");
    detail::Sha256 value;
    std::array<std::uint8_t, 4096> bytes{};
    while (stream) {
        stream.read(reinterpret_cast<char*>(bytes.data()), bytes.size());
        value.update(std::span(bytes).first(static_cast<std::size_t>(stream.gcount())));
    }
    check(stream.eof(), "fixture hash read failed");
    return value.finish();
}
doc::EngineDocumentProfileFacts profile() {
    doc::EngineDocumentProfileFacts facts;
    facts.enabled = true; facts.kind = doc::ProfileKind::pixel; facts.name = doc::kPixelProfileName;
    facts.provider_abi_major = 1; facts.provider_abi_minor = 1;
    facts.host_abi_major = 1; facts.host_abi_minor = 0;
#if defined(__linux__)
    facts.target_system = BIB_ENGINE_TARGET_LINUX;
#elif defined(_WIN32)
    facts.target_system = BIB_ENGINE_TARGET_WINDOWS;
#endif
#if defined(__aarch64__)
    facts.target_processor = BIB_ENGINE_CPU_AARCH64;
#else
    facts.target_processor = BIB_ENGINE_CPU_X86_64;
#endif
    facts.pointer_bits = sizeof(void*) * 8; facts.lifetime = BIB_ENGINE_LIFETIME_PROCESS;
    facts.maximum_starts = 1; facts.viewport_width = 800; facts.viewport_height = 600;
    facts.provider_capabilities = doc::kPixelCapabilities;
    facts.base_header_sha256 = doc::kBaseHeaderSha256; facts.extension_header_sha256 = doc::kExtensionHeaderSha256;
    facts.contract_sha256 = doc::kContractSha256; facts.catalog_sha256 = doc::kCatalogSha256;
    facts.build_sha256.fill(0x41); facts.source_recipe_sha256.fill(0x42);
    facts.queries = doc::kQueries; facts.commands = doc::kCommands; facts.query_count = 1; facts.command_count = 2;
    check(doc::document_profile_valid(facts), "fixture exact source profile invalid");
    return facts;
}
NativeEngineLoadPlan make_plan(const fs::path& root, const fs::path& fixture) {
    check(!fs::exists(root), "each fixture requires a fresh private output root");
    fs::create_directories(root / "bin"); fs::create_directories(root / "data");
    fs::create_directory(root / "empty");
    fs::copy_file(fixture, root / "bin/provider.so");
    std::ofstream(root / "NOTICE", std::ios::binary) << "synthetic fixture notice\n";
    std::ofstream(root / "data/config", std::ios::binary) << "not a native engine SDK\n";
    NativeEngineLoadPlan plan;
    plan.root = root; plan.provider_entry = "bin/provider.so";
    plan.pins.recipe.fill(0x42); plan.pins.binary_manifest.fill(0x43);
    plan.pins.proof.fill(0x44); plan.pins.runtime.fill(0x45);
    const auto facts = profile();
    plan.expectation = {facts.target_system, facts.target_processor, facts.pointer_bits,
        facts.contract_sha256, facts.build_sha256, facts.source_recipe_sha256, facts, {}, {}};
    for (const auto& [name, directory] : std::array<std::pair<const char*, bool>, 6>{{
            {"NOTICE", false}, {"bin", true}, {"bin/provider.so", false},
            {"data", true}, {"data/config", false}, {"empty", true}}}) {
        const auto path = root / name;
        const auto mode = directory || std::string_view(name) == "bin/provider.so" ? 0755 : 0644;
        fs::permissions(path, static_cast<fs::perms>(mode), fs::perm_options::replace);
        plan.assets.push_back({name, directory ? NativeEngineLoadAssetKind::directory : NativeEngineLoadAssetKind::file,
            static_cast<std::uint32_t>(mode), directory ? 0 : fs::file_size(path), directory ? doc::Digest{} : hash(path)});
    }
    plan.notices = {"NOTICE"};
    return plan;
}
engine_document_actions::EngineDocumentActionsProfileFacts actions_profile() {
    namespace actions = engine_document_actions;
    namespace editor = engine_editor;
    actions::EngineDocumentActionsProfileFacts facts;
    facts.enabled = true; facts.kind = actions::ProfileKind::document_actions; facts.name = actions::kProfileName;
    facts.provider_abi_major = 1; facts.provider_abi_minor = 1;
    facts.host_abi_major = 1; facts.host_abi_minor = 0;
#if defined(__linux__)
    facts.target_system = BIB_ENGINE_TARGET_LINUX;
#elif defined(_WIN32)
    facts.target_system = BIB_ENGINE_TARGET_WINDOWS;
#endif
#if defined(__aarch64__)
    facts.target_processor = BIB_ENGINE_CPU_AARCH64;
#else
    facts.target_processor = BIB_ENGINE_CPU_X86_64;
#endif
    facts.pointer_bits = sizeof(void*) * 8; facts.lifetime = BIB_ENGINE_LIFETIME_PROCESS;
    facts.maximum_starts = 1; facts.viewport_width = 800; facts.viewport_height = 600;
    facts.provider_capabilities = actions::kProviderCapabilities; facts.surface_capabilities = actions::kSurfaceCapabilities;
    facts.surface_protocol_version = 2; facts.editor_protocol_version = BIB_ENGINE_EDITOR_PROTOCOL_VERSION;
    facts.base_header_sha256 = doc::kBaseHeaderSha256; facts.document_header_sha256 = doc::kExtensionHeaderSha256;
    facts.document_contract_sha256 = doc::kContractSha256; facts.document_catalog_sha256 = doc::kCatalogSha256;
    facts.physical_catalog_sha256 = doc::kPhysicalCatalogSha256;
    facts.editor_header_sha256 = editor::kHeaderSha256; facts.editor_contract_sha256 = editor::kContractSha256;
    facts.editor_catalog_sha256 = editor::kCatalogSha256; facts.editor_schema_sha256 = editor::kSchema;
    facts.actions_header_sha256 = actions::kHeaderSha256; facts.contract_sha256 = actions::kContractSha256;
    facts.catalog_sha256 = actions::kCatalogSha256; facts.schema_sha256 = actions::kSchema; facts.ack_schema_sha256 = actions::kAckSchema;
    facts.build_sha256.fill(0x41); facts.source_recipe_sha256.fill(0x42);
    facts.queries = actions::kQueries; facts.commands = actions::kCommands;
    facts.query_count = 2; facts.command_count = 9;
    check(actions::document_actions_profile_valid(facts), "fixture independent actions source profile invalid");
    return facts;
}
NativeEngineLoadPlan make_actions_plan(const fs::path& root, const fs::path& fixture) {
    auto plan = make_plan(root, fixture);
    const auto facts = actions_profile();
    plan.expectation = {facts.target_system, facts.target_processor, facts.pointer_bits,
        facts.contract_sha256, facts.build_sha256, facts.source_recipe_sha256, {}, {}, facts};
    return plan;
}
#if defined(__linux__)
void* resident(const NativeEngineLoadPlan& plan) {
    // Test observation only, with the same explicit absolute entry. Like the
    // product loader, this intentionally never decrements the acquired handle.
    return ::dlopen((plan.root / plan.provider_entry).c_str(), RTLD_NOLOAD | RTLD_NOW | RTLD_LOCAL);
}
unsigned counter(void* handle, const char* name) {
    void* address = ::dlsym(handle, name);
    check(address != nullptr, "fixture counter symbol absent");
    unsigned (*function)(){};
    static_assert(sizeof(function) == sizeof(address));
    std::memcpy(&function, &address, sizeof(function));
    return function();
}
#endif
void run(std::string_view scenario, NativeEngineLoadPlan plan) {
    verify_native_engine_load_plan(plan);
#if defined(__linux__)
    check(resident(plan) == nullptr, "integrity-only verification loaded the provider");
#endif
    if (scenario == "valid") {
        { const auto provider = load_native_engine(plan); (void)provider; }
#if defined(__linux__)
        void* handle = resident(plan);
        check(handle != nullptr, "successful loaded provider was unloaded");
        check(counter(handle, "bib_loader_fixture_getters") == 1, "getter request was retried/probed");
        check(counter(handle, "bib_loader_fixture_starts") == 0, "loader called START");
#endif
    } else if (scenario == "missing-symbol" || scenario == "wrong-table" || scenario == "getter-reject" || scenario == "getter-throw" || scenario == "getter-mutates") {
        if (scenario == "getter-mutates") {
#if defined(__linux__)
            check(::setenv("BIB_LOADER_FIXTURE_MUTATE_NOTICE", (plan.root / "NOTICE").c_str(), 1) == 0, "fixture environment failed");
#endif
        }
        rejected([&] { (void)load_native_engine(plan); });
#if defined(__linux__)
        void* handle = resident(plan);
        check(handle != nullptr, "acquired invalid provider was unloaded");
        check(counter(handle, "bib_loader_fixture_starts") == 0, "failed loader called START");
        check(counter(handle, "bib_loader_fixture_getters") == (scenario == "missing-symbol" ? 0U : 1U), "invalid provider getter was replayed");
#endif
    } else {
        if (scenario == "missing-pin") plan.pins.runtime = {};
        else if (scenario == "recipe-pin") plan.pins.recipe[0] ^= 1;
        else if (scenario == "build-expectation") plan.expectation.build_identity_sha256[0] ^= 1;
        else if (scenario == "legacy-profile") plan.expectation.document_profile = {};
        else if (scenario == "physical-profile") {
            auto& p = plan.expectation.document_profile;
            p.kind = doc::ProfileKind::physical; p.name = doc::kPhysicalProfileName;
            p.provider_capabilities = doc::kPhysicalCapabilities; p.physical_catalog_sha256 = doc::kPhysicalCatalogSha256;
        } else if (scenario == "wrong-target") {
            plan.expectation.document_profile.target_system = plan.expectation.target_system = BIB_ENGINE_TARGET_BROWSER_WASM;
            plan.expectation.document_profile.target_processor = plan.expectation.target_processor = BIB_ENGINE_CPU_WASM32;
            plan.expectation.document_profile.pointer_bits = plan.expectation.pointer_bits = 32;
        } else if (scenario == "relative-root") plan.root = plan.root.filename();
        else if (scenario == "traversal-entry") plan.provider_entry = "bin/../provider.so";
        else if (scenario == "unlisted-entry") plan.provider_entry = "bin/other.so";
        else if (scenario == "alias-case") plan.assets.insert(plan.assets.begin(), {"Bin", NativeEngineLoadAssetKind::directory, 0755, 0, {}});
        else if (scenario == "missing-parent") plan.assets.erase(plan.assets.begin() + 1);
        else if (scenario == "missing-file") fs::remove(plan.root / "data/config");
        else if (scenario == "extra-file") std::ofstream(plan.root / "unlisted") << 'x';
        else if (scenario == "extra-directory") fs::create_directory(plan.root / "unlisted");
        else if (scenario == "hash") std::ofstream(plan.root / "data/config", std::ios::binary | std::ios::in) << 'X';
        else if (scenario == "short-file") fs::resize_file(plan.root / "data/config", 1);
        else if (scenario == "long-file") std::ofstream(plan.root / "data/config", std::ios::binary | std::ios::app) << '!';
        else if (scenario == "mode") fs::permissions(plan.root / "data/config", fs::perms::owner_read, fs::perm_options::replace);
        else if (scenario == "missing-notice") plan.notices = {};
        else if (scenario == "reserved-path") plan.assets.front().path = "CON.txt";
        else if (scenario == "reserved-spaced-stem") plan.assets.front().path = "CON .txt";
        else if (scenario == "symlink-file") { fs::remove(plan.root / "data/config"); fs::create_symlink(plan.root / "NOTICE", plan.root / "data/config"); }
        else if (scenario == "symlink-directory") { fs::remove(plan.root / "empty"); fs::create_directory_symlink(plan.root / "data", plan.root / "empty"); }
        else if (scenario == "symlink-root") { const auto link = fs::path(plan.root.string() + "-link"); fs::create_directory_symlink(plan.root, link); plan.root = link; }
        else if (scenario == "hardlink") { fs::remove(plan.root / "data/config"); fs::create_hard_link(plan.root / "NOTICE", plan.root / "data/config"); }
        else if (scenario == "special-file") {
#if defined(__linux__)
            fs::remove(plan.root / "data/config");
            check(::mkfifo((plan.root / "data/config").c_str(), 0644) == 0, "fixture FIFO creation failed");
#endif
        } else throw std::runtime_error("unknown loader fixture case");
        rejected([&] { (void)load_native_engine(plan); },
            scenario == "reserved-path" || scenario == "reserved-spaced-stem" ? "reserved retained path component" : "");
#if defined(__linux__)
        check(resident(plan) == nullptr, "invalid preflight loaded a provider");
#endif
    }
}
void run_actions_preflight(std::string_view scenario, const NativeEngineLoadPlan& plan) {
    verify_native_engine_load_plan(plan);
#if defined(__linux__)
    check(resident(plan) == nullptr, "actions integrity verification loaded the provider");
#endif
    const auto reject_plan = [&](const NativeEngineLoadPlan& broken) {
        rejected([&] { (void)load_native_engine(broken); });
#if defined(__linux__)
        check(resident(plan) == nullptr, "invalid actions preflight acquired a provider");
#endif
    };
    const auto mutate = [&](auto change) {
        auto broken = plan;
        change(broken);
        reject_plan(broken);
    };
    using Facts = engine_document_actions::EngineDocumentActionsProfileFacts;
    if (scenario == "profile-fields") {
        mutate([](auto& p) { p.expectation.document_actions_profile.enabled = false; });
        mutate([](auto& p) { p.expectation.document_actions_profile.kind = engine_document_actions::ProfileKind::disabled; });
        mutate([](auto& p) { p.expectation.document_actions_profile.name += 'x'; });
        for (const auto member : std::array{
                &Facts::provider_abi_major, &Facts::provider_abi_minor, &Facts::host_abi_major, &Facts::host_abi_minor,
                &Facts::target_system, &Facts::target_processor, &Facts::pointer_bits, &Facts::lifetime, &Facts::maximum_starts,
                &Facts::viewport_width, &Facts::viewport_height, &Facts::surface_protocol_version, &Facts::editor_protocol_version,
                &Facts::query_count, &Facts::command_count})
            mutate([member](auto& p) { ++(p.expectation.document_actions_profile.*member); });
        for (const auto member : std::array{&Facts::provider_capabilities, &Facts::surface_capabilities})
            mutate([member](auto& p) { (p.expectation.document_actions_profile.*member) ^= 1; });
        for (const auto member : std::array{
                &Facts::base_header_sha256, &Facts::document_header_sha256, &Facts::document_contract_sha256,
                &Facts::document_catalog_sha256, &Facts::physical_catalog_sha256, &Facts::editor_header_sha256,
                &Facts::editor_contract_sha256, &Facts::editor_catalog_sha256, &Facts::editor_schema_sha256,
                &Facts::actions_header_sha256, &Facts::contract_sha256, &Facts::catalog_sha256,
                &Facts::schema_sha256, &Facts::ack_schema_sha256, &Facts::build_sha256, &Facts::source_recipe_sha256})
            mutate([member](auto& p) { (p.expectation.document_actions_profile.*member)[0] ^= 1; });
        const auto operation_mutations = [&](auto array_member, std::size_t count) {
            for (std::size_t index = 0; index < count; ++index) {
                for (const auto member : std::array{&doc::OperationFacts::operation,
                        &doc::OperationFacts::maximum_input_bytes, &doc::OperationFacts::required_reply_capacity})
                    mutate([=](auto& p) { ++((p.expectation.document_actions_profile.*array_member)[index].*member); });
                mutate([=](auto& p) { (p.expectation.document_actions_profile.*array_member)[index].capability ^= 1; });
                mutate([=](auto& p) { (p.expectation.document_actions_profile.*array_member)[index].schema_sha256[0] ^= 1; });
            }
        };
        operation_mutations(&Facts::queries, 2);
        operation_mutations(&Facts::commands, 9);
    } else if (scenario == "plan-fields") {
        mutate([](auto& p) { ++p.schema_version; });
        for (const auto member : std::array{&NativeEngineLoadPins::recipe, &NativeEngineLoadPins::binary_manifest,
                &NativeEngineLoadPins::proof, &NativeEngineLoadPins::runtime})
            mutate([member](auto& p) { p.pins.*member = {}; });
        mutate([](auto& p) { p.pins.recipe[0] ^= 1; });
        for (const auto member : std::array{&NativeEngineExpectation::target_system,
                &NativeEngineExpectation::target_processor, &NativeEngineExpectation::pointer_bits})
            mutate([member](auto& p) { ++(p.expectation.*member); });
        for (const auto member : std::array{&NativeEngineExpectation::contract_header_sha256,
                &NativeEngineExpectation::build_identity_sha256, &NativeEngineExpectation::source_recipe_sha256})
            mutate([member](auto& p) { (p.expectation.*member)[0] ^= 1; });
        mutate([](auto& p) {
            auto& f = p.expectation.document_actions_profile;
            f.target_system = p.expectation.target_system = BIB_ENGINE_TARGET_BROWSER_WASM;
            f.target_processor = p.expectation.target_processor = BIB_ENGINE_CPU_WASM32;
            f.pointer_bits = p.expectation.pointer_bits = 32;
        });
    } else if (scenario == "inactive-profiles") {
        mutate([](auto& p) { p.expectation.document_profile = profile(); });
        mutate([](auto& p) {
            auto& f = p.expectation.document_profile;
            f = profile(); f.kind = doc::ProfileKind::physical; f.name = doc::kPhysicalProfileName;
            f.provider_capabilities = doc::kPhysicalCapabilities; f.physical_catalog_sha256 = doc::kPhysicalCatalogSha256;
        });
        mutate([](auto& p) { p.expectation.document_profile.name = "disabled facts are not default"; });
        mutate([](auto& p) { p.expectation.editor_profile.enabled = true; });
        mutate([](auto& p) { p.expectation.editor_profile.name = "disabled facts are not default"; });
        mutate([](auto& p) { p.expectation.document_actions_profile = {}; });
        auto legacy = plan;
        const auto facts = profile();
        legacy.expectation = {facts.target_system, facts.target_processor, facts.pointer_bits,
            facts.contract_sha256, facts.build_sha256, facts.source_recipe_sha256, facts, {}, {}};
        verify_native_engine_load_plan(legacy);
        auto broken = legacy;
        broken.expectation.editor_profile.name = "disabled facts are not default";
        reject_plan(broken);
        broken = legacy;
        broken.expectation.document_actions_profile.name = "disabled facts are not default";
        reject_plan(broken);
    } else throw std::runtime_error("unknown actions preflight case");
}
}
int main(int argc, char** argv) {
    try {
        check(argc == 4, "usage: loader-test CASE FRESH-ROOT FIXTURE-DSO");
        const std::string_view scenario = argv[1];
        if (scenario.starts_with("actions-")) {
            const auto selected = scenario.substr(8);
            auto plan = make_actions_plan(fs::path(argv[2]), fs::path(argv[3]));
            if (selected == "profile-fields" || selected == "plan-fields" || selected == "inactive-profiles")
                run_actions_preflight(selected, plan);
            else if (selected == "old-table" || selected == "command-limit" || selected == "query-limit" || selected == "reply-limit")
                run("wrong-table", std::move(plan));
            else if (selected == "larger-limits") run("valid", std::move(plan));
            else run(selected, std::move(plan));
        } else if (scenario == "pixel-actions-table")
            run("wrong-table", make_plan(fs::path(argv[2]), fs::path(argv[3])));
        else run(argv[1], make_plan(fs::path(argv[2]), fs::path(argv[3])));
        std::cout << "PASS " << argv[1] << " assertions=" << assertions << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL " << (argc > 1 ? argv[1] : "setup") << ": " << error.what() << '\n';
        return 1;
    }
}
