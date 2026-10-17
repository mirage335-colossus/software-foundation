#pragma once

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <map>
#include <optional>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace foundation::appended {

enum class NativeCarrier : std::uint64_t { elf = 1, pe = 2 };

class ContainerError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

struct ApplicationIdentity {
    std::string id, name, version;
};

struct PackageComponent {
    bool present{false};
    std::optional<std::string> entry;
    std::optional<std::string> profile;
};

struct PackageFile {
    std::string path, component, media_type, sha256;
    std::vector<std::uint8_t> data;
};

// Owns verified resource bytes. No path is resolved against the host filesystem.
struct Package {
    ApplicationIdentity application;
    PackageComponent web, binary;
    std::uint32_t abi_major{1}, abi_minor{0};
    std::vector<std::string> services, capabilities;
    std::map<std::string, std::string, std::less<>> identities;
    std::vector<PackageFile> files;
    std::string index_json, payload_id, package_sha256, kernel_sha256;

    [[nodiscard]] const PackageFile* find_file(std::string_view path) const noexcept;
};

inline constexpr std::size_t appended_trailer_bytes = 192;
inline constexpr std::uint64_t max_appended_kernel_bytes = 512ULL * 1024 * 1024;
inline constexpr std::uint64_t max_appended_package_bytes = 256ULL * 1024 * 1024;
inline constexpr std::uint64_t max_appended_index_bytes = 4ULL * 1024 * 1024;
inline constexpr std::uint64_t max_appended_file_bytes = 64ULL * 1024 * 1024;
inline constexpr std::size_t max_appended_file_count = 4096;

// Reads ONLY logical resource data followed by its canonical index. The index
// must be the exact nonempty suffix; bytes are bounded before hashing/parsing.
// Returns fully owned, verified resource bytes and computed payload_id (index
// SHA-256) and package_sha256. kernel_sha256 remains empty. This does not inspect
// a carrier, prefix, trailer or filesystem, nor authenticate the supplied bytes;
// a carrier owner must verify those external boundaries/identities separately.
[[nodiscard]] Package read_package(
    std::span<const std::uint8_t> package, std::uint64_t index_offset,
    std::uint64_t index_length);

// pristine_length comes from immutable, finalized kernel metadata, never a magic
// scan or an untrusted trailer. Exact pristine length means absence; every extra
// byte must belong to a completely verified package. Missing/invalid bytes throw
// ContainerError. Hashes establish consistency, not independent authentication.
[[nodiscard]] std::optional<Package> read_native(
    std::span<const std::uint8_t> artifact, std::uint64_t pristine_length,
    NativeCarrier expected_carrier);

// Streams the bounded kernel prefix and allocates only the bounded suffix.
[[nodiscard]] std::optional<Package> read_native_file(
    const std::filesystem::path& artifact, std::uint64_t pristine_length,
    NativeCarrier expected_carrier);

} // namespace foundation::appended
