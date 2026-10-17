// SPDX-License-Identifier: CC0-1.0
// Source-only real-WebCore adapter; no linked/runnable provider is claimed.
#pragma once
#include "EnginePrivate.hpp"
#include "LegacyHostAdapters.hpp"
namespace bib::provider_candidate {
// Called once by future engine-local copied dispatcher composition BEFORE the
// public getter. Metadata must describe this exact qualified provider build;
// nonzero hashes are supplied by the builder, never invented in this source.
// This function is engine-private C++, never a host/guest SDK symbol.
std::int32_t bindActualWebCoreProvider(const BibEngineBuildV1&,
    const BibEngineLimitsV1&, ServiceRetentionLimits) noexcept;
}
