// SPDX-License-Identifier: CC0-1.0
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <string>
#include <string_view>

namespace foundation::appended::engine_input {

using Digest = std::array<std::uint8_t, 32>;

namespace detail {
consteval Digest digest(std::string_view text) {
    if (text.size() != 64) std::abort();
    Digest result{};
    for (std::size_t i = 0; i < result.size(); ++i) {
        auto digit = [](char c) consteval -> unsigned {
            if (c >= '0' && c <= '9') return static_cast<unsigned>(c - '0');
            if (c >= 'a' && c <= 'f') return static_cast<unsigned>(c - 'a' + 10);
            std::abort();
        };
        result[i] = static_cast<std::uint8_t>((digit(text[2 * i]) << 4) | digit(text[2 * i + 1]));
    }
    return result;
}
} // namespace detail

inline constexpr auto kKeySchema = detail::digest("86b7baad1c95bfb8de3e6b7a9a7c433b528278bbcf84199ca0b2b4ee6134dbc9");
inline constexpr auto kFocusSchema = detail::digest("eef60cda2aa7b791641b0e5082d551ec37c10b8d92ca4cc71f13be0af45321d9");
inline constexpr auto kMouseSchema = detail::digest("6a15d0e2f814564ce263824dd782335bb327b886e982aefec32476a29b0fd4a3");
inline constexpr auto kProviderContractSha256 = detail::digest("a8e89da85d34b29a4d1bc454495791fa604b81e3477e48ce8ca902e4333a9c0d");
// The named physical-v1 retained catalog must contain these exact approved
// catalog bytes. This digest alone supplies no execution/qualification proof.
inline constexpr auto kApprovedCatalogDesignSha256 = detail::digest("d244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b");
inline constexpr auto kInputCatalogSha256 = kApprovedCatalogDesignSha256;
inline constexpr std::string_view kInputProfileName = "foundation-engine-copied467-mouse-v1";
inline constexpr std::uint64_t kProviderCapabilities = 467;
inline constexpr std::uint64_t kSurfaceCapabilities = 8225;
inline constexpr std::uint32_t kSurfaceProtocolVersion = 1;
inline constexpr std::uint32_t kMouseInputVersion = 1;
inline constexpr std::uint32_t kRawKeyMappingRevision = 1;
inline constexpr std::uint32_t kRequiredReplyCapacity = 16;

struct OperationFacts {
    std::uint32_t operation{}, maximum_input_bytes{}, required_reply_capacity{};
    std::uint64_t capability{};
    Digest schema_sha256{};
    friend bool operator==(const OperationFacts&, const OperationFacts&) = default;
};

inline constexpr std::array<OperationFacts, 3> kCommands{{
    {1, 160, kRequiredReplyCapacity, 16, kKeySchema},
    {3, 32, kRequiredReplyCapacity, 64, kFocusSchema},
    {5, 80, kRequiredReplyCapacity, 128, kMouseSchema},
}};

// Composition supplies an immutable instance from explicitly maintained retained
// inputs. No enabled instance or guessed build/source pin is supplied.
// Actual read-only provider facts must agree before any Package/Page effects.
struct EngineSurfaceProfileFacts {
    bool enabled{};
    std::string name;
    Digest contract_sha256{}, build_sha256{}, source_recipe_sha256{}, catalog_sha256{};
    std::uint64_t provider_capabilities{}, surface_capabilities{};
    std::uint32_t surface_protocol_version{}, mouse_input_version{}, raw_key_mapping_revision{};
    std::uint32_t viewport_width{}, viewport_height{};
    double display_scale{};
    std::array<OperationFacts, 3> commands{};
    std::uint32_t query_count{};
    friend bool operator==(const EngineSurfaceProfileFacts&, const EngineSurfaceProfileFacts&) = default;
};

inline bool input_profile_valid(const EngineSurfaceProfileFacts& facts) noexcept {
    auto nonzero = [](const Digest& value) {
        for (auto byte : value) if (byte) return true;
        return false;
    };
    return facts.enabled && facts.name == kInputProfileName
        && facts.contract_sha256 == kProviderContractSha256
        && nonzero(facts.build_sha256) && nonzero(facts.source_recipe_sha256)
        && facts.catalog_sha256 == kInputCatalogSha256
        && facts.provider_capabilities == kProviderCapabilities
        && facts.surface_capabilities == kSurfaceCapabilities
        && facts.surface_protocol_version == kSurfaceProtocolVersion
        && facts.mouse_input_version == kMouseInputVersion
        && facts.raw_key_mapping_revision == kRawKeyMappingRevision
        && facts.viewport_width == 800 && facts.viewport_height == 600
        && facts.display_scale == 1 && facts.commands == kCommands && facts.query_count == 0;
}

inline bool input_profile_agrees(const EngineSurfaceProfileFacts& actual,
                                 const EngineSurfaceProfileFacts& expected) noexcept {
    return input_profile_valid(actual) && input_profile_valid(expected) && actual == expected;
}

} // namespace foundation::appended::engine_input
