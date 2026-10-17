#pragma once

#include "foundation/appended/container.hpp"

#include <cstdint>
#include <filesystem>
#include <optional>

namespace foundation::appended {

// This implementation belongs only in loader-enabled native kernels. Its one
// read-only boundary stamp must be finalized by the explicit producer after all
// installation/stripping and before composition. The default application does
// not link this object or acquire an appended runtime dependency.
[[nodiscard]] std::uint64_t self_pristine_length() noexcept;

// Resolve an existing installed path from this exact running image, independent
// of argv, PATH and the working directory. The compiled hint must be nonempty,
// relative and NUL-free; parent components are permitted for bindir/datadir
// layouts. Canonicalize the OS image path, then normalize its parent/hint join.
// Missing/unresolvable image or installed paths throw without a fallback.
[[nodiscard]] std::filesystem::path self_relative_path(const std::filesystem::path& compiled_relative_hint);

// Locate this exact running image through a private generic host provider and
// verify its complete suffix against the immutable boundary. Exact pristine
// length returns nullopt. Unsealed, truncated and malformed images throw;
// recognized corruption never falls back to an ordinary application.
[[nodiscard]] std::optional<Package> load_self();

} // namespace foundation::appended
