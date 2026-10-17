// SPDX-License-Identifier: CC0-1.0
// New optional actual-engine source overlay. Not compiled/runtime qualified.
#pragma once
#include "EnginePrivate.hpp"
#include "LegacyHostAdapters.hpp"
namespace bib::provider_candidate {
enum class DocumentBindingProfile : std::uint32_t { pixel = 1, physical = 2 };
// One-shot metadata composition, before the public getter/START. The exact
// nonzero Worker epoch is supplied by the isolated Worker bootstrap, never
// inferred from a document or a JS-number conversion. Profile2003 is unsupported
// until a real modern physical provider is implemented; no silent downgrade.
std::int32_t bindActualWebCoreDocumentProvider(const BibEngineBuildV1&,
    const BibEngineLimitsV1&, ServiceRetentionLimits, std::uint64_t worker_epoch,
    DocumentBindingProfile = DocumentBindingProfile::pixel) noexcept;
}
