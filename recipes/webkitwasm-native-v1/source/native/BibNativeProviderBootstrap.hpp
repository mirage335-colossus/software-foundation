// SPDX-License-Identifier: CC0-1.0
// Private native provider interface. No additional exported registration ABI.
#pragma once
#include <cstdint>

namespace bib::provider_candidate {
// Called by the provider-side getter BEFORE its Runtime::Gate is acquired.
// One-shot registration retains exact native metadata/handlers and returns an
// existing BIB_ENGINE_* status. It must serialize concurrent/reentrant getter
// calls, contain exceptions, preserve terminal failure and intended owner-thread
// identity, and reuse the original successful binding on repeated getters.
// It performs no Host callback, Page/VM initialization, author script, resources,
// START or engine work. Never call it from a DSO constructor/loader-lock hook.
// This hidden C++ helper is not an additional exported ABI. The sole public
// provider entry remains bib_engine_get_provider_v1. Native runtime is unqualified.
[[nodiscard]] std::int32_t ensureNativeDocumentProviderBound() noexcept;
}
