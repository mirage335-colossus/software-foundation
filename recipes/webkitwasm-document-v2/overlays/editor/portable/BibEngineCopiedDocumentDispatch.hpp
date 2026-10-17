// SPDX-License-Identifier: CC0-1.0
// Source-only document-profile successor; pure mock tests are not engine proof.
#pragma once
#include "BibEngineCopiedRecord.h"
#include "../runtime/BibEngineCopiedHost.h"
#include <foundation/appended/engine_provider_document_v2.h>
#include <span>
#include <string>
#include <string_view>
#include <thread>
#include <vector>

namespace bib::copied {
// Preserve the existing no-argument symbol and source defaults.
[[nodiscard]] BibEngineLimitsV1 documentCopiedLimits() noexcept;
[[nodiscard]] BibEngineLimitsV1 documentCopiedLimits(DocumentWireProfile) noexcept;

class CopiedDocumentDispatch final {
public:
    // worker is the exact immutable value from the composition's one configure
    // attempt. Facts and the provider C table are owned copies. Profile selection
    // must match the generated composition and exact1795/2003/2035 facts.
    CopiedDocumentDispatch(const BibEngineProviderV1&, CopiedHost&,
        std::string_view exact_profile_facts, std::uint64_t worker,
        DocumentWireProfile=DocumentWireProfile::pixel) noexcept;
    [[nodiscard]] std::uint32_t marker() const noexcept { return valid_&&!host_.poisoned()?65536u:0u; }
    std::int32_t dispatch(std::uint32_t, std::span<const std::uint8_t>,
        std::span<std::uint8_t>) noexcept;
private:
    BibEngineProviderV1 provider_{};
    CopiedHost& host_;
    std::string facts_;
    const std::thread::id owner_{std::this_thread::get_id()};
    const std::uint64_t worker_;
    const DocumentWireProfile profile_;
    bool valid_{}, active_{}, attempted_{}, started_{}, first_ready_{}, raster_output_{true};
    std::uint64_t instance_{};
    // Complete owned input and result staging precede provider entry. An
    // uncertain result leaves these exact buffers frozen for forensic evidence;
    // the process-lived dispatcher is never reset/destroyed to recover it.
    std::vector<std::uint8_t> input_, result_;
};
} // namespace bib::copied
