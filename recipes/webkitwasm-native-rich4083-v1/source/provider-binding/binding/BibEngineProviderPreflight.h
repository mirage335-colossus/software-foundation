// SPDX-License-Identifier: CC0-1.0
#pragma once
#include <foundation/appended/engine_provider.h>
#include <cstdint>
namespace bib::provider_candidate {
bool actualResourceLimits(const BibEngineLimitsV1&) noexcept;
// Inert declaration validation only: no host argument and no resource lookup.
// Trusted composition already validated Package/entry; actual load may still
// fail after callback retention, requiring process exit.
std::int32_t validateActualStart(const BibEngineStartV1&) noexcept;
}
