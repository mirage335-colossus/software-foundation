#include "foundation/appended/startup.hpp"

#include <algorithm>
#include <filesystem>
#include <stdexcept>
#include <string>
#include <vector>

#ifdef _WIN32
#include <windows.h>
#endif

// This is finalized exactly once by the explicit producer operation, after all
// installation/stripping. Composition only copies the resulting immutable prefix.
// Read through volatile so the compiler cannot fold the initially zero boundary.
#if defined(_MSC_VER)
#pragma section(".rdata", read)
__declspec(allocate(".rdata"))
#elif defined(__GNUC__)
__attribute__((used, section(".rodata")))
#endif
alignas(8) extern const unsigned char foundation_appended_boundary[16] = {
    'S', 'F', 'K', 'E', 'R', 'N', '0', '1', 0, 0, 0, 0, 0, 0, 0, 0
};

namespace foundation::appended {
namespace {
std::filesystem::path executable_path() {
#ifdef _WIN32
    std::vector<wchar_t> path(256);
    for (;;) {
        const DWORD length = GetModuleFileNameW(nullptr, path.data(), static_cast<DWORD>(path.size()));
        if (length == 0) throw std::runtime_error("could not locate the running kernel");
        if (length < path.size()) return std::filesystem::path(std::wstring(path.data(), length));
        if (path.size() >= 32768) throw std::runtime_error("running kernel path exceeds the host limit");
        path.resize(std::min<std::size_t>(32768, path.size() * 2));
    }
#elif defined(__linux__)
    // The OS-owned link continues to identify this exact image after rename.
    return "/proc/self/exe";
#else
    throw std::runtime_error("the appended kernel has no qualified self-path provider on this host");
#endif
}

constexpr NativeCarrier native_carrier() {
#ifdef _WIN32
    return NativeCarrier::pe;
#else
    return NativeCarrier::elf;
#endif
}
} // namespace

std::uint64_t self_pristine_length() noexcept {
    const volatile unsigned char* bytes = foundation_appended_boundary;
    std::uint64_t result = 0;
    for (unsigned int i = 0; i != 8; ++i)
        result |= static_cast<std::uint64_t>(bytes[8 + i]) << (8 * i);
    return result;
}

std::filesystem::path self_relative_path(const std::filesystem::path& compiled_relative_hint) {
    const auto& hint = compiled_relative_hint.native();
    if (hint.empty() || compiled_relative_hint.has_root_path() ||
        hint.find(std::filesystem::path::value_type{}) != hint.npos)
        throw std::invalid_argument("compiled installed path hint must be nonempty, relative and NUL-free");
    const auto os_image = executable_path();
    if (!os_image.is_absolute())
        throw std::runtime_error("the running kernel path provider returned no absolute image path");
    std::error_code error;
    const auto image = std::filesystem::canonical(os_image, error);
    if (error)
        throw std::runtime_error("could not resolve the running kernel image: " + error.message());
    const auto installed = (image.parent_path() / compiled_relative_hint).lexically_normal();
    const auto state = std::filesystem::status(installed, error);
    if (error || !std::filesystem::exists(state))
        throw std::runtime_error("compiled installed path relative to the running kernel is unavailable" +
            (error ? ": " + error.message() : std::string{}));
    return installed;
}

std::optional<Package> load_self() {
    const auto boundary = self_pristine_length();
    if (boundary == 0)
        throw std::runtime_error("kernel boundary is unsealed; use the explicit appended kernel-seal producer operation");
    return read_native_file(executable_path(), boundary, native_carrier());
}
} // namespace foundation::appended
