#include "native_engine_loader.hpp"
#include "sha256.hpp" // Existing private streaming helper; no core runtime link.

#include <algorithm>
#include <array>
#include <fstream>
#include <limits>
#include <map>
#include <set>
#include <string_view>

namespace foundation::appended {
namespace native_engine_loader_detail {
// Defined by exactly one native platform source. No unload primitive exists.
void check_node(const std::filesystem::path&, bool directory, std::uint32_t mode, bool compare_mode);
decltype(&bib_engine_get_provider_v1) acquire_factory(const std::filesystem::path&);
}
namespace {
namespace fs = std::filesystem;
using Digest = engine_document::Digest;
[[noreturn]] void fail(std::string message) {
    throw NativeEngineLoadError("native engine maintenance required: " + std::move(message));
}
bool nonzero(const Digest& value) {
    return std::any_of(value.begin(), value.end(), [](auto byte) { return byte != 0; });
}
std::string folded(std::string_view value) {
    std::string result(value);
    for (char& c : result) if (c >= 'A' && c <= 'Z') c = static_cast<char>(c - 'A' + 'a');
    return result;
}
void portable_path(std::string_view path) {
    if (path.empty() || path.size() > 4096 || path.front() == '/' || path.back() == '/')
        fail("invalid portable retained path");
    std::size_t start{};
    while (start < path.size()) {
        const auto end = path.find('/', start);
        const auto part = path.substr(start, end == path.npos ? path.size() - start : end - start);
        if (part.empty() || part == "." || part == ".." || part.back() == '.' || part.back() == ' ')
            fail("invalid retained path component");
        for (unsigned char c : part)
            if (c < 32 || c >= 127 || std::string_view("\\:<>\"|?*").find(static_cast<char>(c)) != std::string_view::npos)
                fail("nonportable retained path");
        auto stem = part.substr(0, part.find('.'));
        while (!stem.empty() && stem.back() == ' ') stem.remove_suffix(1);
        const auto device = folded(stem);
        if (device == "con" || device == "prn" || device == "aux" || device == "nul" ||
            device == "conin$" || device == "conout$" ||
            (device.size() == 4 && (device.starts_with("com") || device.starts_with("lpt")) && device[3] >= '1' && device[3] <= '9'))
            fail("reserved retained path component");
        if (end == path.npos) break;
        start = end + 1;
    }
}
void check_root(const fs::path& root) {
    if (!root.is_absolute() || root != root.lexically_normal() || root == root.root_path())
        fail("installed engine root must be an explicit normalized absolute directory");
    auto current = root.root_path();
    native_engine_loader_detail::check_node(current, true, 0, false);
    for (const auto& component : root.relative_path()) {
        current /= component;
        native_engine_loader_detail::check_node(current, true, 0, false);
    }
}
void host_target(const NativeEngineExpectation& expectation) {
#if defined(__linux__) && defined(__x86_64__)
    constexpr auto system = BIB_ENGINE_TARGET_LINUX, processor = BIB_ENGINE_CPU_X86_64;
#elif defined(__linux__) && defined(__aarch64__)
    constexpr auto system = BIB_ENGINE_TARGET_LINUX, processor = BIB_ENGINE_CPU_AARCH64;
#elif defined(_WIN32) && (defined(_M_X64) || defined(__x86_64__))
    constexpr auto system = BIB_ENGINE_TARGET_WINDOWS, processor = BIB_ENGINE_CPU_X86_64;
#else
    (void)expectation;
    fail("native engine load host is unsupported");
    return;
#endif
#if (defined(__linux__) && (defined(__x86_64__) || defined(__aarch64__))) || (defined(_WIN32) && (defined(_M_X64) || defined(__x86_64__)))
    if (expectation.target_system != system || expectation.target_processor != processor ||
        expectation.pointer_bits != sizeof(void*) * 8)
        fail("retained engine target does not match this native host");
#endif
}
Digest file_digest(const fs::path& path, std::uint64_t expected_bytes) {
    if (expected_bytes > std::numeric_limits<std::uint64_t>::max() / 8)
        fail("retained asset exceeds SHA256 length range");
    std::ifstream stream(path, std::ios::binary);
    if (!stream) fail("cannot read retained asset: " + path.string());
    detail::Sha256 hash;
    std::array<std::uint8_t, 65536> buffer{};
    std::uint64_t count{};
    while (stream) {
        stream.read(reinterpret_cast<char*>(buffer.data()), static_cast<std::streamsize>(buffer.size()));
        const auto read = stream.gcount();
        if (read < 0 || static_cast<std::uint64_t>(read) > expected_bytes - count)
            fail("retained asset byte count changed: " + path.string());
        count += static_cast<std::uint64_t>(read);
        hash.update(std::span(buffer).first(static_cast<std::size_t>(read)));
    }
    if (!stream.eof() || count != expected_bytes)
        fail("retained asset byte count mismatch: " + path.string());
    return hash.finish();
}
}

void verify_native_engine_load_plan(const NativeEngineLoadPlan& plan) {
    const auto& expected = plan.expectation;
    const auto& profile = expected.document_profile;
    const auto& actions = expected.document_actions_profile;
    const auto agrees = [&expected](const auto& facts) {
        return facts.target_system == expected.target_system && facts.target_processor == expected.target_processor &&
            facts.pointer_bits == expected.pointer_bits && facts.contract_sha256 == expected.contract_header_sha256 &&
            facts.build_sha256 == expected.build_identity_sha256 && facts.source_recipe_sha256 == expected.source_recipe_sha256;
    };
    const bool pixel_profile = expected.editor_profile == engine_editor::EngineEditorProfileFacts{} &&
        actions == engine_document_actions::EngineDocumentActionsProfileFacts{} &&
        engine_document::document_profile_valid(profile) && profile.kind == engine_document::ProfileKind::pixel && agrees(profile);
    const bool actions_profile = profile == engine_document::EngineDocumentProfileFacts{} &&
        expected.editor_profile == engine_editor::EngineEditorProfileFacts{} &&
        engine_document_actions::document_actions_profile_valid(actions) && agrees(actions);
    if (plan.schema_version != 1 || !nonzero(plan.pins.recipe) || !nonzero(plan.pins.binary_manifest) ||
        !nonzero(plan.pins.proof) || !nonzero(plan.pins.runtime) || plan.pins.recipe != expected.source_recipe_sha256 ||
        (!pixel_profile && !actions_profile))
        fail("compiled retained pins/exact ABI1.1 pixel1795 or document-actions4083 profile disagree");
    host_target(expected);
    portable_path(plan.provider_entry);
    if (expected.target_system == BIB_ENGINE_TARGET_WINDOWS) {
        if (!plan.provider_entry.ends_with(".dll")) fail("Windows provider entry must name an explicit DLL");
    } else {
        const auto so = plan.provider_entry.rfind(".so");
        if (so == std::string::npos || (so + 3 != plan.provider_entry.size() && plan.provider_entry[so + 3] != '.'))
            fail("Linux provider entry must name an explicit shared library");
        bool digit = false;
        for (std::size_t n = so + 3; n < plan.provider_entry.size(); ++n) {
            const auto c = plan.provider_entry[n];
            if (c == '.') { if (n != so + 3 && !digit) fail("invalid shared-library version"); digit = false; }
            else if (c >= '0' && c <= '9') digit = true;
            else fail("invalid shared-library version");
        }
        if (so + 3 != plan.provider_entry.size() && !digit) fail("invalid shared-library version");
    }
    if (plan.assets.empty() || plan.assets.size() > 65536 || plan.notices.empty())
        fail("complete retained asset/notice closure is missing");
    std::map<std::string, const NativeEngineLoadAsset*, std::less<>> inventory;
    std::set<std::string> aliases;
    std::string previous;
    for (const auto& asset : plan.assets) {
        portable_path(asset.path);
        const bool directory = asset.kind == NativeEngineLoadAssetKind::directory;
        if ((!directory && asset.kind != NativeEngineLoadAssetKind::file) || asset.path <= previous ||
            !aliases.insert(folded(asset.path)).second ||
            (directory ? asset.logical_mode != 0755 || asset.bytes || nonzero(asset.sha256) :
                (asset.logical_mode != 0644 && asset.logical_mode != 0755) || !nonzero(asset.sha256)))
            fail("invalid sorted retained asset/mode inventory");
        const auto separator = asset.path.rfind('/');
        if (separator != std::string::npos) {
            const auto parent = inventory.find(asset.path.substr(0, separator));
            if (parent == inventory.end() || parent->second->kind != NativeEngineLoadAssetKind::directory)
                fail("retained asset inventory omits an exact parent directory");
        }
        inventory.emplace(asset.path, &asset);
        previous = asset.path;
    }
    const auto entry = inventory.find(plan.provider_entry);
    if (entry == inventory.end() || entry->second->kind != NativeEngineLoadAssetKind::file)
        fail("provider entry is absent from the retained file closure");
    previous.clear();
    for (const auto& notice : plan.notices) {
        portable_path(notice);
        const auto item = inventory.find(notice);
        if (notice <= previous || notice == plan.provider_entry || item == inventory.end() || item->second->kind != NativeEngineLoadAssetKind::file)
            fail("invalid complete retained notice inventory");
        previous = notice;
    }
    check_root(plan.root);
    std::set<std::string> visited;
    const auto walk = [&](const auto& self, const fs::path& path, const std::string& prefix) -> void {
        for (const auto& child : fs::directory_iterator(path)) {
            const auto name = child.path().filename().generic_string();
            const auto relative = prefix.empty() ? name : prefix + "/" + name;
            portable_path(relative);
            const auto item = inventory.find(relative);
            if (item == inventory.end() || !visited.insert(relative).second)
                fail("installed engine closure has an unlisted entry: " + relative);
            const auto& asset = *item->second;
            const bool directory = asset.kind == NativeEngineLoadAssetKind::directory;
            native_engine_loader_detail::check_node(child.path(), directory, asset.logical_mode, true);
            if (directory) self(self, child.path(), relative);
            else if (file_digest(child.path(), asset.bytes) != asset.sha256)
                fail("retained asset checksum mismatch: " + relative);
        }
    };
    walk(walk, plan.root, {});
    if (visited.size() != inventory.size()) fail("installed engine closure omits a retained entry");
    // Hashes are consistency checks under the trusted no-writer contract, not a
    // race-proof filesystem/OS-loader security boundary.
    check_root(plan.root);
}

NativeEngineProvider load_native_engine(const NativeEngineLoadPlan& plan) {
    verify_native_engine_load_plan(plan);
    const auto factory = native_engine_loader_detail::acquire_factory(plan.root / fs::path(plan.provider_entry));
    BibEngineProviderV1 table{};
    std::int32_t status;
    try {
        status = factory(BIB_ENGINE_ABI_MAJOR, BIB_ENGINE_DOCUMENT_V2_ABI_MINOR, sizeof(table), &table);
    } catch (...) {
        fail("provider factory crossed the C ABI with an exception; acquired library remains process-lived");
    }
    if (status != BIB_ENGINE_OK)
        fail("provider factory rejected the exact ABI1.1 request; acquired library remains process-lived");
    auto provider = NativeEngineProvider::checked(table, plan.expectation);
    verify_native_engine_load_plan(plan);
    return provider;
}

} // namespace foundation::appended
