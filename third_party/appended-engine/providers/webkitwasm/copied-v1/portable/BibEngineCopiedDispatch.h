// SPDX-License-Identifier: CC0-1.0
// Source-only copied endpoint. Fake-provider tests do not qualify WebCore.
#pragma once
#include "BibEngineCopiedRecord.h"
#include "../runtime/BibEngineCopiedHost.h"
#include <foundation/appended/engine_provider.h>
#include <cstdint>
#include <span>
#include <string_view>
#include <thread>

namespace bib::copied {
[[nodiscard]] BibEngineLimitsV1 copiedLimits() noexcept;

class CopiedDispatch final {
public:
    // Composition owns these process-lived objects/bytes before marker access.
    CopiedDispatch(const BibEngineProviderV1&, CopiedHost&, std::string_view profile) noexcept;
    [[nodiscard]] std::uint32_t marker() const noexcept { return valid_ ? 65536u : 0u; }
    // Local spans only. The scalar Wasm wrapper separately proves actual memory
    // bounds before forming them. Every entered provider exception is terminal.
    std::int32_t dispatch(std::uint32_t, std::span<const std::uint8_t>,
        std::span<std::uint8_t>) noexcept;
private:
    BibEngineProviderV1 provider_{};
    CopiedHost& host_;
    std::string_view profile_;
    const std::thread::id owner_{std::this_thread::get_id()};
    bool valid_{}, active_{}, attempted_{}, started_{}, first_ready_{};
    std::uint64_t worker_{}, instance_{};
};
} // namespace bib::copied
