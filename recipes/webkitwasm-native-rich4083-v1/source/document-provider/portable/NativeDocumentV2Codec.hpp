// SOURCE CANDIDATE ONLY. See WIRE.md; no actual provider operation assigned.
#pragma once
#include "NativeDocumentV2Types.hpp"
#include <utility>

namespace BIB::NativeDocumentV2 {
using Bytes = std::vector<std::uint8_t>;
enum class PacketKind : std::uint8_t { query = 1, action = 2, publication = 3, reply = 4, completion = 5 };
Bytes encodeQuery(const Query&);
Query decodeQuery(std::span<const std::uint8_t>);
Bytes encodeAction(const ActionRequest&);
ActionRequest decodeAction(std::span<const std::uint8_t>);
Bytes encodePublication(const OwnedPublication&);
OwnedPublication decodePublication(std::span<const std::uint8_t>);
// Standalone publication record for additive protocols: no NDV2 packet header,
// Query/Reply correlation or manufactured document request token.
inline constexpr std::size_t maxPublicationRecordBytes = 911505;
Bytes encodePublicationRecord(const OwnedPublication&);
OwnedPublication decodePublicationRecord(std::span<const std::uint8_t>);
Bytes encodeReply(const Reply&);
Reply decodeReply(std::span<const std::uint8_t>);
Bytes encodeCompletion(const Completion&);
Completion decodeCompletion(std::span<const std::uint8_t>);

// Fixed prefix admission does not allocate or inspect an action's effectful
// target. Call complete decodeAction + exact native guards before effects.
Query admitRequestPrefix(std::span<const std::uint8_t>, PacketKind, Identity expected);
// Capacity must be accepted BEFORE effects. This owns all 1MiB staging storage;
// fill/copy has no allocation if a valid <=maxReplyBytes packet is supplied.
class ReplyReservation {
public:
    explicit ReplyReservation(std::size_t destinationCapacity);
    void retain(std::span<const std::uint8_t>);
    std::span<const std::uint8_t> bytes() const noexcept;
private:
    Bytes storage_;
    std::size_t used_{0};
    bool retained_{false};
};
// Immutable publication staging: all validation/encoding/allocation precede
// commit. No native registry authority; Session commits its prepared state in
// the same no-throw phase. Exact owned bytes survive failed delivery/retry.
class PreparedPublication {
public:
    PreparedPublication(PreparedPublication&&) noexcept = default;
    PreparedPublication& operator=(PreparedPublication&&) noexcept = default;
    PreparedPublication(const PreparedPublication&) = delete;
    PreparedPublication& operator=(const PreparedPublication&) = delete;
    const std::shared_ptr<const OwnedPublication>& publication() const noexcept { return publication_; }
    const std::shared_ptr<const Bytes>& encoded() const noexcept { return encoded_; }
private:
    PreparedPublication() = default;
    PreparedPublication(std::shared_ptr<const OwnedPublication> p, std::shared_ptr<const Bytes> b)
        : publication_(std::move(p)), encoded_(std::move(b)) {}
    std::shared_ptr<const OwnedPublication> publication_;
    std::shared_ptr<const Bytes> encoded_;
    friend PreparedPublication preparePublication(OwnedPublication);
    friend class PublicationSlot;
};
PreparedPublication preparePublication(OwnedPublication);
class PublicationSlot {
public:
    // Empty/moved-from preparation is ignored; a token is consumed exactly once.
    void commit(PreparedPublication&&) noexcept;
    const PreparedPublication& current() const noexcept { return current_; }
private:
    PreparedPublication current_;
};
} // namespace BIB::NativeDocumentV2
