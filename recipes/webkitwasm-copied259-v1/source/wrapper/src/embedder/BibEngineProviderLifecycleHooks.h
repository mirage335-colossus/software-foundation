// SPDX-License-Identifier: CC0-1.0
// Private source composition hook; never an application or public engine ABI.
#pragma once
#include <cstdint>

namespace BIB {
// Use the already-reserved canonical document sequence for the adapter's next
// resource/service begin callback. Application instance comes from composition;
// resource epochs and author data never select this identity.
[[nodiscard]] bool bibProviderSetProspectiveDocument(std::uint64_t document_sequence) noexcept;
// True only for the captured initial context after its exact GET entry has an
// already-copied 200 text/html reply. Never pumps the loop or resolves resources.
[[nodiscard]] bool bibProviderInitialEntryConfirmed() noexcept;
// Owner-only asynchronous initial-load state: 0 pending, 1 selected with copied
// entry proof, -1 known terminal initial failure. Success survives navigation.
[[nodiscard]] std::int32_t bibProviderInitialLoadStatus() noexcept;
}
