// SPDX-License-Identifier: CC0-1.0
#pragma once

#include <foundation/gui/surface_editor.hpp>
#include <memory>

namespace foundation::ui::native_editor {
using namespace foundation::gui_editor;

class Backend {
public:
    virtual ~Backend() = default;
    virtual std::optional<NativeProjection> project(std::uint64_t mapping_id) = 0;
    virtual NativeResult apply(const NativeRequest&) = 0;
    // Clear owned native modifier authority; cancel only the exact owned native
    // composition. Never fabricate author-visible keyup events during teardown.
    virtual NativeResult revoke(const Revocation&) = 0;
};

// Pure, bounded typed validation for the trusted ingress codecs. These do not
// grant native authority; causal admission still belongs to Controller.
bool valid_basis(const Basis&) noexcept;
bool valid_retire_material(const NativeRetireMaterial&) noexcept;
bool valid_projection(const NativeProjection&) noexcept;
bool valid_observation(const Observation&) noexcept;

// One serialized UI owner. Ingress/mailboxing and publication belong to the
// composition adapter. activate/process/project/apply must run after physical
// browser callbacks return. No callback is invoked by construction or accessors.
// process owns a packet before effects; every consumed outcome is never replayed.
class Controller {
public:
    static constexpr std::size_t max_text_bytes = 65536, max_default_groups = 64;
    static constexpr std::size_t max_dependencies = 8, max_packet_bytes = 1048576;

    Controller(); // Async owner: no native backend callbacks are installed here.
    explicit Controller(Backend&);
    ~Controller();
    Controller(const Controller&) = delete;
    Controller& operator=(const Controller&) = delete;
    std::optional<Basis> activate(NativeProjection);
    // Each ticket binds exactly one retained head across later owner turns.
    // Wrong/late tickets never consume the active head. The four split methods
    // never call Backend. Dispatch the returned effect once; uncertain delivery must
    // call notify_transport_failure rather than replay or manufacture a result.
    PreparedDispatch begin(Packet);
    PreparedDispatch begin_revocation(Revocation);
    PreparedDispatch supply_projection(std::uint64_t ticket, std::optional<NativeProjection>);
    // A null-basis retirement receipt releases editable admission, not native
    // cleanup obligations. The transport owner retains the original material
    // until exact provider closure is attested or owned retirement completes,
    // and must finish that handshake before releasing the receipt to the App.
    DispatchResult complete(std::uint64_t ticket, NativeResult);
    DispatchResult process(Packet);
    DispatchResult process_revocation(Revocation);
    // Trusted owner only: it has checked that native entry did not occur, or
    // transport was never submitted/claimed. Timeout, busy or service changes
    // while entry remains possible are insufficient; use unknown handling.
    DispatchResult cancel_unentered(std::uint64_t ticket);
    // Accept only actual external owned-retirement proof. This metadata-only
    // step issues no authority/receipt and preserves the original outcome.
    bool complete_external_retirement(const NativeRetireMaterial& expected, const NativeResult& checked) noexcept;
    // Read only after successful complete_external_retirement; the original
    // observation receipt remains forensic evidence and is never rewritten.
    const RetirementReadback* external_retirement() const noexcept;
    void revoke() noexcept;
    void close() noexcept;
    // Parent calls this if the actual checked native projection could not be
    // published. A completed native edit cannot become a reusable predecessor.
    void notify_publication_failure() noexcept;
    // Trusted transport must first correlate its currently active ticket. An
    // unrelated late transport failure must never cancel a newer active head.
    void notify_transport_failure() noexcept;

    const Basis* current_basis() const noexcept;
    const NativeProjection* current_projection() const noexcept;
    std::optional<CompositionFact> current_composition() const noexcept;
    State state() const noexcept;
    bool terminal() const noexcept;
    bool processing() const noexcept;
    bool awaiting_projection() const noexcept;
    bool awaiting_result() const noexcept;
    const Packet* unresolved() const noexcept;
    const Receipt* last_receipt() const noexcept;
    const Revocation* last_revocation() const noexcept;
    const std::string& last_error() const noexcept;
    std::size_t default_groups() const noexcept;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace foundation::ui::native_editor
