// SPDX-License-Identifier: CC0-1.0
// New optional actual-engine source overlay. Not compiled/runtime qualified.
#pragma once
#include "EnginePrivate.hpp"
#include "LegacyHostAdapters.hpp"
namespace bib::provider_candidate {
enum class DocumentBindingProfile : std::uint32_t { pixel = 1, physical = 2 };
// One-shot metadata composition, before the public getter/START. The exact
// nonzero Worker epoch and explicit profile are supplied by the isolated Worker
// bootstrap. Physical2003 composes the released modern native callbacks with the
// SAME Page/Session/Publisher; pixel1795 stays distinct with no input handlers.
// No profile is inferred from capability bits and no downgrade is performed.
std::int32_t bindActualWebCoreDocumentProvider(const BibEngineBuildV1&,
    const BibEngineLimitsV1&, ServiceRetentionLimits, std::uint64_t worker_epoch,
    DocumentBindingProfile = DocumentBindingProfile::pixel) noexcept;
}
