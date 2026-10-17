// Explicit nonproduction raw-candidate maintenance entry; not a retained SDK loader.
#include "common/raw_candidate_probe.hpp"
#include "native_engine_loader.hpp"
#if !defined(_WIN32) || !(defined(_M_X64) || defined(__x86_64__))
#error "The raw Windows candidate harness requires native Windows x64"
#endif
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <algorithm>
#include <charconv>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

namespace foundation::appended::native_engine_loader_detail {
// SAME implemented private loader source; its OS HMODULE is never unloaded.
void check_node(const std::filesystem::path&, bool, std::uint32_t, bool);
decltype(&bib_engine_get_provider_v1) acquire_factory(const std::filesystem::path&);
}
namespace {
namespace fs = std::filesystem;
using namespace foundation::appended;
std::string ascii(const wchar_t* value) {
    std::string out;
    for (; *value; ++value) {
        if (*value < 32 || *value > 126 || out.size() >= 4096) throw std::runtime_error("bounded ASCII runtime argument required");
        out += static_cast<char>(*value);
    }
    if (out.empty()) throw std::runtime_error("empty runtime argument");
    return out;
}
std::string pin(const wchar_t* input) {
    const auto value = ascii(input);
    if (value.size() != 64 || value == std::string(64, '0') || !std::all_of(value.begin(), value.end(),
            [](char c) { return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'); }))
        throw std::runtime_error("independent nonzero lowercase SHA256 runtime argument required");
    return value;
}
engine_document::Digest digest(const std::string& value) {
    engine_document::Digest out{};
    const auto digit = [](char c) { return c <= '9' ? c - '0' : c - 'a' + 10; };
    for (std::size_t i = 0; i != out.size(); ++i) out[i] = static_cast<std::uint8_t>(digit(value[i*2])*16 + digit(value[i*2+1]));
    return out;
}
std::uint64_t integer(const wchar_t* input) {
    const auto value = ascii(input); std::uint64_t out{};
    const auto result = std::from_chars(value.data(), value.data() + value.size(), out);
    if (result.ec != std::errc{} || result.ptr != value.data() + value.size() || !out ||
            (value.size() > 1 && value[0] == '0')) throw std::runtime_error("canonical nonzero runtime integer required");
    return out;
}
fs::path ordinary(const wchar_t* input) {
    const fs::path path(input);
    if (!path.is_absolute() || path != path.lexically_normal() || path == path.root_path())
        throw std::runtime_error("explicit normalized absolute runtime input required");
    auto current = path.root_path();
    native_engine_loader_detail::check_node(current, true, 0, false);
    for (const auto& component : path.relative_path()) {
        current /= component;
        native_engine_loader_detail::check_node(current, current != path, 0, false);
    }
    return path;
}
}
int wmain(int argc, wchar_t** argv) {
    try {
        // Exact finite controller-owned arguments; no arbitrary executable,
        // profile, script, callback or DLL-declared expectation is accepted.
        if (argc != 9) throw std::runtime_error("expected provider/package/index-offset/index-length/package-pin/recipe-pin/build-pin/nonce");
        const auto provider = ordinary(argv[1]), package = ordinary(argv[2]);
        const auto offset = integer(argv[3]), length = integer(argv[4]);
        const auto package_pin = pin(argv[5]), recipe_pin = pin(argv[6]), build_pin = pin(argv[7]), nonce = pin(argv[8]);
        const auto size = fs::file_size(package);
        if (!size || size > 4 * 1024 * 1024 || offset > size || length != size - offset)
            throw std::runtime_error("bounded exact package index suffix required");
        std::ifstream stream(package, std::ios::binary);
        if (!stream) throw std::runtime_error("cannot open held raw runtime package");
        std::vector<std::uint8_t> bytes(static_cast<std::size_t>(size));
        stream.read(reinterpret_cast<char*>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
        if (stream.gcount() != static_cast<std::streamsize>(bytes.size()) || stream.peek() != std::char_traits<char>::eof())
            throw std::runtime_error("raw runtime package EOF differs");
        const auto expected = raw_candidate::document_actions_expectation(BIB_ENGINE_TARGET_WINDOWS,
            BIB_ENGINE_CPU_X86_64, digest(recipe_pin), digest(build_pin));
        // The production retained loader remains unchanged and strict. This
        // explicitly named maintenance entry calls its same OS-acquisition leaf.
        const auto factory = native_engine_loader_detail::acquire_factory(provider);
        const auto result = raw_candidate::run_raw_candidate_offscreen_probe(factory, expected, bytes,
            {offset, length, package_pin});
        std::cout << "{\"schema_version\":1,\"kind\":\"foundation-raw-native-candidate-runtime-observations-v1\","
            "\"platform\":\"windows-x86_64\",\"process_id\":" << ::GetCurrentProcessId()
            << ",\"nonce\":\"" << nonce << "\",\"recipe_sha256\":\"" << recipe_pin
            << "\",\"provider_build_sha256\":\"" << build_pin << "\",\"package_sha256\":\"" << package_pin
            << "\",\"loader\":\"LoadLibraryExW-DLL_LOAD_DIR-SYSTEM32-process-lifetime\",\"observations\":";
        raw_candidate::write_observations_json(std::cout, result); std::cout << "}\n";
        std::cout.flush();
        if (!std::cout) throw std::runtime_error("raw runtime observation stream failed");
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "raw Windows candidate runtime: " << error.what() << '\n'; return 1;
    } catch (...) {
        std::cerr << "raw Windows candidate runtime: unknown terminal failure\n"; return 1;
    }
}
