#pragma once

#include "appended_document_forms.hpp"
#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <vector>

namespace foundation::ui {

// Exact native session identity, issued outside this codec. Never derive these
// values from a v1 reply or replace them with a different local generation.
struct DocumentV2Identity {
    std::uint64_t application_instance{0}, service_generation{0}, document_sequence{0};
    bool operator==(const DocumentV2Identity&) const = default;
};
enum class DocumentV2RequestKind { snapshot_query, form_command };
struct DocumentV2Request {
    DocumentV2Identity identity;
    DocumentFormsRequest source;
    DocumentV2RequestKind kind{DocumentV2RequestKind::snapshot_query};
    std::vector<std::uint8_t> bytes;
};
struct DocumentV2NativeSelection {
    DocumentNativeSelection endpoints;
    std::optional<gui::Rect> focus_rect;
};
struct DocumentV2Publication {
    NativeFormsDocumentObservation observation;
    std::uint32_t native_degradation{0};
    std::optional<DocumentV2NativeSelection> selection;
};
enum class DocumentV2CompletionCode {
    ok, busy, unavailable, stale_document, stale_control, invalid_action,
    unsupported, limit, readback_failed
};
struct DocumentV2ActionStatus {
    DocumentV2CompletionCode code{DocumentV2CompletionCode::unavailable};
    bool effects_entered{false}, popup_opened{false};
};
struct DocumentV2Reply {
    DocumentFormsRequestToken token;
    // Query: publication only. Form: control/status and optional whole paired
    // readback. A form readback's body.request_id is ZERO: it is not a pending
    // controller query completion. The owner must obtain a fresh paired query.
    std::optional<DocumentV2Publication> publication;
    std::optional<DocumentFormsControlReply> control;
    std::optional<DocumentV2ActionStatus> action_status;
};

inline constexpr std::size_t max_document_v2_reply_bytes = 1024 * 1024;
inline constexpr std::size_t max_document_v2_action_bytes = 6246;

// NDV2 format 2, frozen schema f11fd061350f8d663dbcdec7cf0a063e4fb0ff3564d285076690f58e8a84143d.
// Owns and validates the complete input before returning. No engine, callback,
// transport, capability advertisement or retry occurs here. A body intent has
// no native-v2 wire operation and throws invalid_argument before encoding; it
// is known not executed. An action range needs the native editor's later scalar
// boundary check against its actual old buffer, which is absent from this input.
DocumentV2Request encode_appended_document_v2(DocumentV2Identity, const DocumentFormsRequest&);

// Strict owned decode. Checks the exact expected request, native joins, scalar
// Unicode, bounds and current consumer representability without remapping IDs,
// versions or older valid leases. Optional native geometry remains optional.
// Invalid input throws invalid_argument, publishing no partial observation.
DocumentV2Reply decode_appended_document_v2(std::span<const std::uint8_t>, const DocumentV2Request& expected);

// Strict canonical Publication payload record only: no packet header or query
// correlation is manufactured. Shares the exact query/form record validator;
// complete consumption and the proven 911505-byte payload bound are required.
// The returned body.request_id is ZERO. An additive action caller correlates
// through its own outer key and cannot manufacture an accepted query receipt.
inline constexpr std::size_t max_document_v2_publication_bytes = 911505;
DocumentV2Publication decode_appended_document_v2_publication(
    std::span<const std::uint8_t>, DocumentV2Identity);

} // namespace foundation::ui
