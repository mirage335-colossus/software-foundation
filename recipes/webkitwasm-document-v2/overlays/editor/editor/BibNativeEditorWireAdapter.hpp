// SPDX-License-Identifier: CC0-1.0
// New private editor2035 source candidate; no actual-header/runtime proof.
#pragma once
#include "EnginePrivate.hpp"
#include <foundation/gui/surface_editor.hpp>
#include <cstdint>
#include <memory>
#include <optional>

namespace bib::provider_candidate {
class NativeEditorBackend;

// Binder State owns both Backend and Adapter permanently after successful bind.
// EngineEditorPrivateV1 has no separate context: its five binder thunks resolve
// the existing EnginePrivateV1.context to State, then call these methods.
class NativeEditorWireAdapter final {
public:
    NativeEditorWireAdapter(std::uint64_t worker_epoch,
        std::uint64_t application_instance, NativeEditorBackend&);
    ~NativeEditorWireAdapter();
    NativeEditorWireAdapter(const NativeEditorWireAdapter&) = delete;
    NativeEditorWireAdapter& operator=(const NativeEditorWireAdapter&) = delete;

    // Pure, bounded admission and deep validation. Neither callback invokes a
    // native getter/effect, publishes, retains new state or enters an engine.
    std::int32_t admit_request(std::uint64_t worker, const BibEngineDocumentV1*,
        std::uint32_t domain, std::uint32_t operation, std::uint64_t sequence,
        const BibEngineBytesV1*) noexcept;
    std::int32_t validate_reply(std::uint64_t worker, const BibEngineDocumentV1*,
        std::uint32_t domain, std::uint32_t operation, std::uint64_t sequence,
        const BibEngineBytesV1* original, const BibEngineBytesV1* reply) noexcept;

    // Actual operations only, inside the complete outer ProviderGuard turn.
    // Own input/output reservation before Backend entry. An unknown native
    // result or serialization failure is terminal, never a checked receipt.
    std::int32_t project(std::uint64_t worker, const BibEngineQueryV1*,
        BibEngineReplyBufferV1*, BibEngineQueryResultV1*) noexcept;
    std::int32_t apply(std::uint64_t worker, const BibEngineCommandV1*,
        BibEngineReplyBufferV1*, BibEngineCommandResultV1*) noexcept;
    std::int32_t revoke(std::uint64_t worker, const BibEngineCommandV1*,
        BibEngineReplyBufferV1*, BibEngineCommandResultV1*) noexcept;

    // Exact owned request metadata for Backend's surface_identity hook, only
    // while the actual call is entered and its native context still matches.
    // No GUI owner/presentation identity is fabricated. A copy may allocate;
    // any exception belongs to the enclosing actual-call terminal path.
    std::optional<foundation::gui_surface::Identity> entered_surface_identity(
        std::uint64_t native_context) const;

    // Revoke entered wire metadata and delegate Backend metadata invalidation
    // exactly once. Preserve original in-flight/returned evidence; no cleanup,
    // native callback, effect replay or second Controller is involved.
    void invalidate_metadata() noexcept;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
} // namespace bib::provider_candidate
