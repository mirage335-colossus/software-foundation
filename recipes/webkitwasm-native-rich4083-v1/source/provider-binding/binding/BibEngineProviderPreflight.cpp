// SPDX-License-Identifier: CC0-1.0
#include "BibEngineProviderPreflight.h"
#include "resource_url.hpp"
#include <array>
#include <cstdint>
#include <string_view>

namespace bib::provider_candidate {
namespace {
bool utf8(const BibEngineBytesV1& span) noexcept {
    if (span.reserved || (!span.data && span.length)) return false;
    std::uint32_t at = 0;
    while (at < span.length) {
        const auto first = span.data[at++];
        if (!first) return false;
        if (first < 0x80) continue;
        std::uint32_t value{}, minimum{}, count{};
        if (first >= 0xc2 && first <= 0xdf) { value=first&31u; minimum=0x80; count=1; }
        else if (first >= 0xe0 && first <= 0xef) { value=first&15u; minimum=0x800; count=2; }
        else if (first >= 0xf0 && first <= 0xf4) { value=first&7u; minimum=0x10000; count=3; }
        else return false;
        if (count > span.length-at) return false;
        while (count--) {
            const auto next=span.data[at++];
            if ((next&0xc0u)!=0x80u) return false;
            value=(value<<6)|(next&63u);
        }
        if (value<minimum || value>0x10ffff || (value>=0xd800 && value<=0xdfff)) return false;
    }
    return true;
}
}
bool actualResourceLimits(const BibEngineLimitsV1& limits) noexcept {
    // Same pure bounds as the exact legacy adapter, before callback retention.
    return limits.size>=sizeof(limits) && !limits.reserved
        && limits.maximum_inflight_resources && limits.maximum_inflight_resources<=4096
        && limits.maximum_resource_response_bytes && limits.maximum_resource_response_bytes<=64ull*1024*1024
        && limits.maximum_retained_resource_bytes>=limits.maximum_resource_response_bytes
        && limits.maximum_retained_resource_bytes<=256ull*1024*1024;
}
std::int32_t validateActualStart(const BibEngineStartV1& config) noexcept {
    constexpr auto mandatory=BIB_ENGINE_CAP_APP_BUNDLE|BIB_ENGINE_CAP_SERVICE_QUEUE;
    if (config.size<sizeof(config) || config.reserved0 || config.reserved1 || config.raster_output>1
        || (config.required_capabilities&mandatory)!=mandatory
        || config.entry_url.reserved || !config.entry_url.data || !config.entry_url.length
        || config.entry_url.length>4096 || config.persist_seed.length>12u*1024u*1024u
        || !utf8(config.entry_url) || !utf8(config.persist_seed)
        || config.limits.maximum_service_message_bytes<384 || !actualResourceLimits(config.limits)) return BIB_ENGINE_INVALID;
    std::array<char,64> authority{};
    constexpr char hex[]="0123456789abcdef";
    bool nonzero=false;
    for (unsigned i=0;i<32;++i) {
        const auto byte=config.application_package_sha256[i]; nonzero|=byte!=0;
        authority[i*2]=hex[byte>>4]; authority[i*2+1]=hex[byte&15u];
    }
    if (!nonzero) return BIB_ENGINE_INVALID;
    const std::string_view url(reinterpret_cast<const char*>(config.entry_url.data),config.entry_url.length);
    if (url.find_first_of("?#")!=std::string_view::npos) return BIB_ENGINE_INVALID;
    try {
        const auto parsed=foundation::appended::candidate::normalize_app_resource_url(url,{authority.data(),authority.size()});
        return parsed ? BIB_ENGINE_OK : BIB_ENGINE_INVALID;
    } catch (...) { return BIB_ENGINE_LIMIT; }
}
}
