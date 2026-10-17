// SPDX-License-Identifier: CC0-1.0
// Scalar conversion only. Caller authenticates current native readiness first.
#pragma once
#include <foundation/appended/engine_provider.h>
#include <cstdint>
#include <type_traits>

namespace BIB {
static_assert(sizeof(std::uint64_t) == 8);
static_assert(std::is_same_v<decltype(BibEngineDocumentV1::application_instance), std::uint64_t>);
static_assert(std::is_same_v<decltype(BibEngineDocumentV1::document_sequence), std::uint64_t>);
static_assert(std::is_same_v<decltype(BibEngineDocumentV1::service_generation), std::uint64_t>);
static_assert(sizeof(BibEngineDocumentV1) == 3 * sizeof(std::uint64_t));
static_assert(std::is_trivially_copyable_v<BibEngineDocumentV1>);

// A template avoids importing WebCore headers merely to name the private
// BibAppDocumentIdentityV1. Instantiation checks its exact three canonical field
// types. No second public schema or resource-epoch conversion is introduced.
template<class PrivateIdentity>
[[nodiscard]] inline constexpr BibEngineDocumentV1 bibProviderProjectDocument(
    const PrivateIdentity& identity) noexcept
{
    static_assert(std::is_same_v<decltype(identity.application_instance), std::uint64_t>);
    static_assert(std::is_same_v<decltype(identity.document_sequence), std::uint64_t>);
    static_assert(std::is_same_v<decltype(identity.service_generation), std::uint64_t>);
    return {identity.application_instance, identity.document_sequence, identity.service_generation};
}
}
