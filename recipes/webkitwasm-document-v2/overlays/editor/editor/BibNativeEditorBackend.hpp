// SPDX-License-Identifier: CC0-1.0
// NEW source-only opt-in editor backend. Actual WebCore syntax/runtime UNRUN.
#pragma once
#include "native_editor_controller.hpp"
#include "native_editor_codec.hpp"
#include <foundation/appended/engine_provider.h>
#include <functional>
#include <memory>

namespace bib::provider_candidate {
struct NativeEditorHooks {
    void* context{};
    bool (*on_owner)(void*) noexcept{};
    bool (*callback_faulted)(void*) noexcept{};
    void (*queue_wake)(void*) noexcept{};
    void (*invalidate_form_authority)(void*) noexcept{};
    // Inert inspection of the SAME ModernDocumentPhysicalProvider state. No
    // independent physical context/highwater registry is created by this backend.
    bool (*physical_authority)(void*,const BibEngineDocumentV1*,std::uint64_t*) noexcept{};
    // Trusted metadata join, not an engine/Host call. The composition allocates
    // the exact current surface owner/generation/epoch and presentation revision;
    // input_context is the existing committed physical-input context.
    std::function<std::optional<foundation::gui_surface::Identity>(std::uint64_t native_context)> surface_identity;
};
class NativeEditorBackend final : public foundation::ui::native_editor::Backend {
public:
    NativeEditorBackend(std::uint64_t worker,std::uint64_t application,NativeEditorHooks);
    ~NativeEditorBackend();
    NativeEditorBackend(const NativeEditorBackend&)=delete;
    NativeEditorBackend& operator=(const NativeEditorBackend&)=delete;
    // mapping0 is an explicit owner projection request. Nonzero resolves ONLY
    // that exact retained native range; a coincident equal string is insufficient.
    std::optional<foundation::ui::native_editor::NativeProjection> project(std::uint64_t mapping) override;
    foundation::ui::native_editor::NativeResult apply(const foundation::ui::native_editor::NativeRequest&) override;
    foundation::ui::native_editor::NativeResult revoke(const foundation::ui::native_editor::Revocation&) override;
    // Production wire entrypoints. Queries carry the owner's exact presentation
    // metadata; sequence is the provider's ordinary global sequence, never a JS id.
    foundation::ui::native_editor::codec::ProjectionReply query(const foundation::ui::native_editor::codec::ProjectionQuery&);
    foundation::ui::native_editor::NativeResult apply_owned(const foundation::ui::native_editor::NativeRequest&,std::uint64_t provider_sequence);
    foundation::ui::native_editor::NativeResult revoke_owned(const foundation::ui::native_editor::NativeRevocationRequest&,std::uint64_t provider_sequence);
    // Inert cached-state admission only: no Bridge, Frame, DOM or Host getter.
    bool admit_metadata(const foundation::ui::native_editor::codec::ProjectionQuery&) const noexcept;
    bool admit_metadata(const foundation::ui::native_editor::codec::NativeRequestEnvelope&) const noexcept;
    bool admit_metadata(const foundation::ui::native_editor::codec::RevocationEnvelope&) const noexcept;
    // Lifecycle/physical-effect metadata revocation only. Retains native
    // retirement material; no DOM cancellation, getter, Host call or cleanup.
    void invalidate_metadata() noexcept;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
}
