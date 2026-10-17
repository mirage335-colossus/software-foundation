// SPDX-License-Identifier: CC0-1.0
// NEW private source overlay. Not installed, parsed against WebCore or qualified.
#pragma once
#include <foundation/appended/engine_provider.h>
#include <cstdint>
#include <memory>

namespace bib::provider_candidate {
inline constexpr std::uint32_t document_physical_callbacks_version = 1;
struct DocumentPhysicalHooks {
    void* context{};
    bool (*on_owner)(void*) noexcept{};
    bool (*callback_faulted)(void*) noexcept{};
    void (*queue_wake)(void*) noexcept{};
    // Same retained Publisher, metadata only: no Frame/getter/Host/author entry.
    void (*invalidate_form_authority)(void*) noexcept{};
};
struct NativeDocumentPhysicalCallbacks {
    std::uint32_t size{}, version{};
    void* context{};
    // Inert advisory admission/reply verification for NEW2003 descriptor only.
    // ProviderGuard owns the outer Host TURN, global sequences and disposition.
    std::int32_t (*validate_cached_request)(void*, std::uint64_t worker,
        const BibEngineCommandV1*) noexcept{};
    std::int32_t (*validate_cached_reply)(void*, std::uint64_t worker,
        const BibEngineCommandV1*, const BibEngineBytesV1*) noexcept{};
    std::int32_t (*command)(void*, const BibEngineCommandV1*, BibEngineReplyBufferV1*,
        BibEngineCommandResultV1*) noexcept{};
    // Revokes portable context/capture; persistent high waters and the latest
    // original receipt survive. No DOM cancellation/cleanup is invented here.
    void (*invalidate_authority)(void*) noexcept{};
};
class ModernDocumentPhysicalProvider final {
public:
    // Metadata construction only, before binding the one NEW2003 provider.
    // BinderState retains this object with its single Session/Publisher for
    // process lifetime after binding. It owns no Page, Session or Host table.
    ModernDocumentPhysicalProvider(std::uint64_t worker, std::uint64_t instance, DocumentPhysicalHooks);
    ~ModernDocumentPhysicalProvider();
    ModernDocumentPhysicalProvider(const ModernDocumentPhysicalProvider&) = delete;
    ModernDocumentPhysicalProvider& operator=(const ModernDocumentPhysicalProvider&) = delete;
    NativeDocumentPhysicalCallbacks callbacks() noexcept;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
} // namespace bib::provider_candidate
