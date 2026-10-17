// NEW successor overlay. Engine-private; no GUI/shared or author JS dependency.
#pragma once
#include "NativeFormsV2Combined.hpp"
#include "../portable/NativeDocumentV2Codec.hpp"
#include <WebCore/HTMLLabelElement.h>

namespace BIB::FormsV2Combined {
enum class CachedRequestStatus { ok, invalid, stale, busy, unsupported, limit };
struct PublisherHooks {
    // Select the actual ready main LocalFrame; identity still comes ONLY from
    // appResourcesDocumentIdentity against its exact current Document/loader.
    std::function<RefPtr<WebCore::LocalFrame>()> currentFrame;
    // EFFECTFUL native layout/style checkpoint of this already-resolved exact
    // context. Called only inside the backend's existing full Host -> Bridge ->
    // common-VM JSLock turn; never by cached admission, reply checks or ACK.
    // The callback fences the same main frame/document/resource before/after;
    // false/unknown rejects capture. Publisher independently rechecks identity.
    std::function<bool(const Context&)> captureCheckpoint;
};
class Publisher final {
public:
    Publisher(Session&, PublisherHooks);
    ~Publisher();
    Publisher(const Publisher&) = delete;
    Publisher& operator=(const Publisher&) = delete;
    // Reuses the SAME immutable pair when complete private evidence proves
    // equality. Unsupported private style republishes cap-free observations.
    std::shared_ptr<const N::OwnedPublication> refreshAndCopy();
    std::shared_ptr<const N::ReplyReservation> queryPacket(std::span<const uint8_t>, size_t capacity);
    std::shared_ptr<const N::ReplyReservation> executePacket(std::span<const uint8_t>, size_t capacity);
    // Bounded owned-data advisory checks only. The binding validates immutable
    // worker/owner and deep-decodes the exact request before calling this API.
    // No live native getter/hook, refresh, checkpoint, mutation or authority claim.
    CachedRequestStatus inspectCachedRequest(const N::Query&,
        const std::optional<N::ActionRequest>&) const;
    bool matchesOwnedReply(const N::Query&, std::span<const uint8_t>) const;
    // Binding checks owner/worker. Metadata-only exact ACK, including after
    // admission/counter retirement. No Session::thread()/hooks or live access.
    bool retireActionMetadata(const N::Identity&, uint64_t sequence,
        std::span<const uint8_t> exactInput) noexcept;
    // Same serialized owner; lifecycle notifications need no live getter/hook.
    // Revoke native references/authority, preserving portable history, retained
    // action result, action high-water and every Session/Publisher counter.
    void invalidateAuthority() noexcept;
    const N::PreparedPublication& historical() const noexcept { return slot.current(); }
private:
    struct CapturedBody {
        N::OwnedPublication publication;
        std::unique_ptr<Session::PreparedRead> read;
        RefPtr<WebCore::Element> focused;
        std::vector<Session::LabelState> labels;
        bool editorEditable { false };
    };
    struct Retained {
        N::Query request;
        N::Bytes input;
        std::shared_ptr<N::ReplyReservation> completion;
    };
    std::optional<Context> exactContext() const;
    bool checkpoint(const Context&);
    void restrictPopup(Session::Capture&) const;
    CapturedBody capture(const Context&, N::ReadBudget&, const Session::PreparedRead* seed = nullptr);
    bool refresh(bool trustedAction, std::optional<uint64_t> issueLease = {}, bool force = false,
        const Session::Capture* focusBaseline = nullptr);
    bool commitCaptured(CapturedBody&, std::optional<uint64_t>, bool force, const Session::Capture*);
    std::optional<Session::Capture> registerFacade(WebCore::HTMLFormControlElement&, bool graphical);
    std::vector<Session::LabelState> captureLabels(Session::PreparedRead&,
        const std::vector<RefPtr<WebCore::HTMLLabelElement>>&, N::ReadBudget&, uint32_t& degradation);
    N::Completion executeAndReadback(const N::ActionRequest&);
    N::Completion begin(const N::ActionRequest&, const F::BeginFormControl&);
    N::Completion open(const N::ActionRequest&, const F::OpenFormPopup&);
    N::Completion apply(const N::ActionRequest&, const F::FormLease&);
    void revoke() noexcept;
    bool afterEffects(const Context&, uint64_t, uint64_t node, bool lease, N::Completion&);
    bool samePublic(const N::OwnedPublication&, const N::OwnedPublication&) const;
    void bodyControl(const Session::Capture&, N::Node&, N::ReadBudget&);
    void selection(CapturedBody&, N::ReadBudget&);
    N::Completion failure(const N::Query&, N::CompletionCode, bool effects = false) const;

    Session& session;
    PublisherHooks hooks;
    N::PublicationSlot slot;
    N::Counter revisions, editorRevisions;
    RefPtr<WebCore::Element> publishedFocus;
    std::vector<Session::LabelState> publishedLabels;
    bool publishedEditable { false }, enteredEffects { false };
    std::optional<Retained> retained;
    uint64_t actionHighWater { 0 };
};
} // namespace BIB::FormsV2Combined
