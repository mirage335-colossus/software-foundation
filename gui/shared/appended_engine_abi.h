#ifndef FOUNDATION_PRIVATE_APPENDED_ENGINE_ABI_H
#define FOUNDATION_PRIVATE_APPENDED_ENGINE_ABI_H

#include <stdint.h>

/* Private copied-owner bridge. This header is not part of the guest SDK.
 * Every integer in a record is little endian; no C struct is serialized.
 * Header: FKB1[4], version:u16, kind:u16, total:u32, flags:u32=0,
 * worker_epoch:u64, instance:u64, document:u64, service_generation:u64,
 * transfer:u64, source:u32, reserved:u32=0, payload_bytes:u32, reserved:u32=0.
 * A reply kind is request kind | 0x8000. Replies start with control:u32 and
 * service:u32 (the existing ServiceStatus domain), followed by operation data.
 * Unknown operations and insufficient complete reply space reject before effects.
 */
#define FOUNDATION_ENGINE_BRIDGE_VERSION UINT32_C(0x00010000)
#define FOUNDATION_ENGINE_RECORD_VERSION UINT16_C(1)
#define FOUNDATION_ENGINE_HEADER_BYTES UINT32_C(72)
#define FOUNDATION_ENGINE_RECEIPT_BYTES UINT32_C(80)
#define FOUNDATION_ENGINE_MAX_BODY_BYTES UINT32_C(1048576)
#define FOUNDATION_ENGINE_MAX_FRAME_BYTES UINT32_C(16777216)
#define FOUNDATION_ENGINE_REPLY_KIND UINT16_C(0x8000)
/* Additive document-profile-only bodies; unrelated message/frame bounds and
 * legacy physical command replies are unchanged. */
#define FOUNDATION_ENGINE_DOCUMENT_WORK_PREFIX_BYTES UINT32_C(56)
#define FOUNDATION_ENGINE_DOCUMENT_BEGIN_BYTES UINT32_C(16)
#define FOUNDATION_ENGINE_DOCUMENT_RESULT_PREFIX_BYTES UINT32_C(40)
#define FOUNDATION_ENGINE_DOCUMENT_MAX_RESULT_BODY_BYTES UINT32_C(1048616)
/* Separate explicitly selected editor2035 mailbox. Its provider payload is
 * the versioned editor binary codec, never JSON or a serialized C++ layout. */
#define FOUNDATION_ENGINE_EDITOR_WORK_PREFIX_BYTES UINT32_C(56)
#define FOUNDATION_ENGINE_EDITOR_BEGIN_BYTES UINT32_C(16)
#define FOUNDATION_ENGINE_EDITOR_RESULT_PREFIX_BYTES UINT32_C(40)
#define FOUNDATION_ENGINE_EDITOR_MAX_RESULT_BODY_BYTES UINT32_C(1048616)

enum FoundationEngineOperation {
    FOUNDATION_ENGINE_CONFIGURE = 1,
    FOUNDATION_ENGINE_TURN_ENTER = 2,
    FOUNDATION_ENGINE_TURN_LEAVE = 3,
    FOUNDATION_ENGINE_BEGIN_DOCUMENT = 4,
    FOUNDATION_ENGINE_CLOSE_DOCUMENT = 5,
    FOUNDATION_ENGINE_SUBMIT = 6,
    FOUNDATION_ENGINE_CANCEL = 7,
    FOUNDATION_ENGINE_STAGE_ACK = 8,
    FOUNDATION_ENGINE_RESOURCE_RESOLVE = 9,
    FOUNDATION_ENGINE_RESOURCE_READ = 10,
    FOUNDATION_ENGINE_RESOURCE_RELEASE = 11,
    FOUNDATION_ENGINE_PUMP_ONE = 12,
    FOUNDATION_ENGINE_PEEK_DELIVERY = 13,
    FOUNDATION_ENGINE_PEEK_ACK_RECEIPT = 14,
    FOUNDATION_ENGINE_PEEK_INPUT = 15,
    FOUNDATION_ENGINE_DELIVERY_RESULT = 16,
    FOUNDATION_ENGINE_ACK_RECEIPT_RESULT = 17,
    FOUNDATION_ENGINE_FRAME_COMMIT = 18,
    FOUNDATION_ENGINE_COMMAND_RESULT = 19,
    FOUNDATION_ENGINE_CLOSE = 20,
    FOUNDATION_ENGINE_BEGIN_RESOURCE_EPOCH = 21,
    FOUNDATION_ENGINE_RETIRE_RESOURCE_EPOCH = 22,
    FOUNDATION_ENGINE_PEEK_RETIRED_DOCUMENT = 23,
    FOUNDATION_ENGINE_RETIRED_DOCUMENT_RESULT = 24,
    FOUNDATION_ENGINE_PEEK_RETIREMENT_AUDIT = 25,
    FOUNDATION_ENGINE_RETIREMENT_AUDIT_RESULT = 26,
    FOUNDATION_ENGINE_PEEK_DOCUMENT_WORK = 27,
    FOUNDATION_ENGINE_DOCUMENT_WORK_RESULT = 28,
    FOUNDATION_ENGINE_BEGIN_DOCUMENT_WORK = 29,
    FOUNDATION_ENGINE_PEEK_EDITOR_WORK = 30,
    FOUNDATION_ENGINE_EDITOR_WORK_RESULT = 31,
    FOUNDATION_ENGINE_BEGIN_EDITOR_WORK = 32
};
enum FoundationEngineControlStatus {
    FOUNDATION_ENGINE_OK = 0, FOUNDATION_ENGINE_EMPTY = 1,
    FOUNDATION_ENGINE_INVALID = 2, FOUNDATION_ENGINE_STALE = 3,
    FOUNDATION_ENGINE_LIMIT = 4, FOUNDATION_ENGINE_CONFLICT = 5,
    FOUNDATION_ENGINE_CLOSED = 6, FOUNDATION_ENGINE_UNSUPPORTED = 7,
    FOUNDATION_ENGINE_INTERNAL = 8
};
enum FoundationEngineTransferResult {
    FOUNDATION_ENGINE_ACCEPTED = 1,
    FOUNDATION_ENGINE_REJECTED = 2,
    FOUNDATION_ENGINE_RETRY = 3,
    FOUNDATION_ENGINE_ABANDONED = 4
};
/* Proposed retained-engine copied endpoint contract, not an implementation or
 * qualified-engine claim. Engine receipts use common service status zero;
 * callback replies retain their distinct actual kernel ServiceStatus domain.
 * DESCRIBE is read-only: no callbacks, Package effects or process commitment.
 * START body is provider_status:i32,phase:u32; it is attempted once and never
 * replayed to recover failure/uncertainty. A successful pending start may still
 * have generation zero; CURRENT_DOCUMENT establishes actual readiness later.
 * DELIVERY/COLLECT body is disposition:u32 (1/2), mapped only after an actual
 * provider status; malformed/uncertain results terminate the worker.
 * Every execution/disposal turn
 * includes native TURN_ENTER/LEAVE across locks and microtask destructors.
 * DISPOSE_RETIRED returns an exact signed provider status:u32 in its receipt
 * body; only status zero permits kernel RETIRED_DOCUMENT_RESULT acceptance.
 * Native TURN returns ServiceStatus (zero OK), never Boolean. The entire native
 * scope retains the dispatch's exact target/transfer, including old retirement
 * identity during disposal; adoption cannot rewrite its eventual TURN_LEAVE. */
/* An explicitly maintained physical-input successor also implements COMMAND4:
 * operation:u32,reserved:u32=0,request_sequence:u64,schema_sha256[32],
 * reply_capacity:u32=16,payload_bytes:u32,payload[exact], at most 216 body bytes.
 * Its reply body is provider_status:i32,disposition:u32 (0 rejected,1 consumed,
 * 2 consumed-unknown),request_sequence:u64,bytes_written:u32=0,handled:u32(0/1).
 * The complete 104-byte receipt capacity precedes actual engine entry. The
 * immutable original copied259 profile keeps its empty input catalog. */
/* Additive document-profile QUERY5 copied request: kind:u32,reserved:u32=0,
 * schema_sha256[32],reply_capacity:u32,payload_bytes:u32,payload[exact] (48-byte
 * prefix). Only native query3 is admitted. Reply: provider_status:i32,
 * bytes_written:u32,semantic_revision:u64,payload[exact] (16-byte prefix).
 * The full 1048672-byte copied reply is reserved before capture. Command4
 * retains its 56-byte request and 24-byte reply prefixes. Original copied259
 * QUERY5 remains unsupported; this does not change the base public C ABI. */
enum FoundationRetainedEngineOperation {
    FOUNDATION_RETAINED_ENGINE_DESCRIBE = 0,
    FOUNDATION_RETAINED_ENGINE_START = 1,
    FOUNDATION_RETAINED_ENGINE_ADVANCE = 2,
    FOUNDATION_RETAINED_ENGINE_CURRENT_DOCUMENT = 3,
    FOUNDATION_RETAINED_ENGINE_COMMAND = 4,
    FOUNDATION_RETAINED_ENGINE_QUERY = 5,
    FOUNDATION_RETAINED_ENGINE_DELIVER_SERVICES = 6,
    FOUNDATION_RETAINED_ENGINE_COLLECT_ACK = 7,
    FOUNDATION_RETAINED_ENGINE_DISPOSE_RETIRED = 8
};
/* Copied engine host notifications: WAKE has no record and only schedules a
 * later owner task; TIMER is finite delay_ms:f64 + armed:u32 (0/1); PERSISTENCE
 * is an opaque bounded copied snapshot. None enters an engine recursively. */
enum FoundationRetainedEngineHostOperation {
    FOUNDATION_RETAINED_ENGINE_HOST_WAKE = 256,
    FOUNDATION_RETAINED_ENGINE_HOST_TIMER = 257,
    FOUNDATION_RETAINED_ENGINE_HOST_PERSISTENCE = 258
};
enum FoundationEngineTransportError {
    FOUNDATION_ENGINE_BAD_RECORD = -1,
    FOUNDATION_ENGINE_REPLY_TOO_SMALL = -2,
    FOUNDATION_ENGINE_BAD_OPERATION = -3,
    FOUNDATION_ENGINE_EXCEPTION = -4
};
/* CONFIGURE, TURN_*, BEGIN/CLOSE_DOCUMENT, PUMP, PEEK_* and CLOSE: empty.
 * SUBMIT: exact existing v1 request envelope; source=0 automatic/1 native/2 module.
 * CANCEL/STAGE_ACK: sequence:u64. Staging returns service UNAVAILABLE until pump.
 * Repeating the exact staged ACK identity/through after the actual ACK returns
 * its cached actual status without reapplying it or consuming its receipt;
 * ACK_RECEIPT_RESULT alone consumes normal ACK collection.
 * DELIVERY_RESULT/ACK_RECEIPT_RESULT: disposition:u32; transfer matches the peek.
 * Successor PEEK_INPUT15: empty. The immutable request body and exact target /
 * unique transfer above are exposed non-destructively after service barriers.
 * COMMAND_RESULT19: exact 24-byte COMMAND result body under that target/transfer,
 * only after its complete TURN returned. Reserve 104 output bytes before
 * settling; success returns the common empty receipt. The latest exact result
 * duplicate is idempotent. A consumed/unhandled or unknown command never retries.
 * BEGIN_RESOURCE_EPOCH: empty; reply data is independently issued epoch:u64.
 * RETIRE_RESOURCE_EPOCH: epoch:u64. Resources never grant service authority.
 * RESOURCE_RESOLVE: resource_epoch:u64,method:u32 (0 GET,1 HEAD),
 * url_bytes:u32, UTF-8 URL.
 * Reply data: http_status:u32,mime_bytes:u32,body_bytes:u64,content_length:u64,
 * lease:u64, MIME bytes (<=127). RESOURCE_READ: lease:u64,offset:u64,count:u32;
 * reply data is exactly count copied bytes. RESOURCE_RELEASE: lease:u64.
 * FRAME_COMMIT: format:u32=1 RGBA8,width:u32,height:u32,stride:u32,x:u32,y:u32,
 * rect_width:u32,rect_height:u32,base_revision:u64,new_revision:u64,RGBA bytes.
 * Fixed initial viewport 800x600; every accepted pixel has alpha=255.
 * Peek reply data is the exact completion envelope, or ACK through_sequence:u64
 * and actual ACK service_status:u32. Empty peeks return control EMPTY.
 * Successful BEGIN replies issue service_generation in the header; generation
 * zero is accepted only for CONFIGURE, BEGIN and prospective TURN/resource ops.
 * Resource epochs have their own nonwrapping domain, separate from document
 * sequence, application instance and actual service generation.
 * PEEK_RETIREMENT_AUDIT: empty, trusted immutable configured owner abandonment
 * only. Reply header has the old exact identity and a unique transfer; body is
 * the unchanged canonical v1 COMPLETION, or an unchanged FKB1 PEEK_ACK_RECEIPT
 * reply (92 bytes) for an already-attempted ACK. Common service status is OK;
 * original outcome/ACK status remains in the copied body. PEEK never ACKs.
 * RETIREMENT_AUDIT_RESULT: old identity/transfer, disposition:u32=ABANDONED(4).
 * Completion abandonment applies actual queue ACK, returning its ServiceStatus;
 * failure retains the same slot for explicit collection retry. ACK receipts are
 * abandoned without reapplying their ACK. The latest successful exact duplicate
 * is idempotent; older results expire. No page callback or effect replay occurs.
 * PEEK_RETIRED_DOCUMENT: empty; eligible only after old queue calls and all
 * delivery/ACK/audit transactions settle. Reply old nonzero identity/unique
 * transfer, empty body. RETIRED_DOCUMENT_RESULT: matching old identity/transfer,
 * disposition:u32=ACCEPTED(1), after a later guarded native disposal succeeds.
 * Its latest exact accepted duplicate is idempotent; failures never retry an
 * engine disposal. Both PEEK operations accept only exact current/last-ready
 * metadata identity, including generation zero before readiness; they do not
 * grant service authority. Resource leases retain independent epoch authority.
 *
 * Explicit ABI1.1 document profiles ONLY (disabled profiles keep BAD_OPERATION):
 * PEEK_DOCUMENT_WORK27: empty scheduler metadata request under current/last-ready
 * authority. A non-destructive success returns the ORIGINAL full target and
 * unique transfer, with body kind:u32 (1 query,2 form,3 action-ACK),operation:u32,
 * request_sequence:u64,schema_sha256[32],reply_capacity:u32,payload_bytes:u32,
 * payload[exact]. The full owned provider reply is reserved before eligibility:
 * query/form1048576, action-ACK16. Complete copied engine slots are respectively
 * 1048672 (80+16+1048576),1048680 (80+24+1048576),120 (80+24+16).
 * BEGIN_DOCUMENT_WORK29: original target/transfer and body kind:u32,reserved:u32=0,
 * request_sequence:u64. A complete common receipt must fit before marking the
 * attempt claimed. It requires a preceding complete PEEK and is never replayed
 * into another provider call. Query/form may then open exactly one matching
 * outer TURN and must leave it before RESULT. ACK7 is metadata-only and MUST
 * NOT invoke any Host/engine callback, so it uses this explicit claim instead.
 * DOCUMENT_WORK_RESULT28: original target/transfer, body kind:u32,reserved:u32=0,
 * request_sequence:u64,provider_status:i32,provider_disposition:u32,
 * bytes_written:u32,handled:u32,semantic_revision:u64,bytes[exact].
 * Query has disposition0/handled0; command semantic_revision is0. The signed
 * native status, command disposition and semantic NDV2 outcome are distinct.
 * Only this operation admits a1048576+40-byte body. It settles only after the
 * provider, final TURN/free scopes and export returned, never from a callback.
 * A latest exact result duplicate is idempotent; changed/expired keys reject.
 * After a naturally balanced returned command, disposition2 may retain bounded
 * raw bytes and handled0/1 exactly as opaque forensic evidence. They are never
 * NDV2/ACK-decoded or retirement proof: the outcome is unknown/process-terminal,
 * with no action retry, ACK cleanup or further provider entry. Rejected
 * disposition0 remains canonical zero bytes/handled0. An unbalanced turn/trap
 * never manufactures RESULT or LEAVE. Known ACK success below stays strict.
 * Local immutable completion redelivery never repeats a native action.
 * PEEK27 EMPTY/service OK means no engine-entry barrier; EMPTY/service
 * UNAVAILABLE means retained work/reservation, input, effect or service
 * transaction still prevents entry. Poisoned endpoints report CLOSED. This
 * distinction belongs only to the additive document profiles, not old peeks.
 * ACK7 request is8-byte original action sequence; checked result16 contains
 * original:u64,code:u32 (0 retired,1 already retired,2 stale),reserved:u32=0.
 * Actual status0/disposition1/handled0/bytes16 and exact original full identity
 * are required. Code2 never releases another action. Final ACK may use MAX;
 * ordinary work stops at MAX-1. Exact cached receipt replay allocates no new
 * sequence. All identities survive navigation/close until checked settlement;
 * no resource epoch, GUI generation or input_context supplies document authority.
 */
/* Explicit typed editor2035 selection ONLY; older profiles keep BAD_OPERATION.
 * PEEK_EDITOR_WORK30: empty current/last-ready metadata request. Success retains
 * the original complete target/unique transfer and owns this56-byte prefix:
 * kind:u32(1 projection4,2 observation8,3 revoke9),operation:u32,sequence:u64,
 * schema_sha256[32],reply_capacity:u32,payload_bytes:u32,payload[exact].
 * Provider payloads use the separate versioned manual-LE editor codec; all
 * include the original worker/application/document/service/sequence tuple.
 * Query4 is bounded236 bytes; command8/9 and every provider reply are <=1MiB.
 * BEGIN_EDITOR_WORK32: original target/transfer, kind:u32,reserved:u32=0,
 * sequence:u64. A prior complete PEEK/full80-byte receipt precedes claiming.
 * All three operations require one complete matching Host TURN. A canonical
 * known pre-entry negative (-1..-7, zero result fields) may have no TURN.
 * EDITOR_WORK_RESULT31: original target/transfer, kind:u32,reserved:u32=0,
 * sequence:u64,status:i32,disposition:u32,written:u32,handled:u32,
 * semantic_revision:u64,bytes[exact] (40-byte prefix, max1048616-byte body).
 * Query disposition/handled are0; successful revision equals the exact native
 * observation_revision. Commands have revision0. Status0/disposition1 command
 * bytes require the exact checked editor receipt; consumed is not semantic
 * editor success. Naturally returned status-8 queries and disposition2 commands
 * preserve bounded opaque bytes, then make the process terminal. Inner semantic
 * unknown likewise retains original transport facts without retirement proof.
 * A trap/unbalanced TURN never fabricates RESULT/LEAVE. After a balanced TURN,
 * the original header/transfer identifies the claim: malformed body kind/seq or
 * receipt poisons it, retains raw prefix/body, and cannot be corrected/retried.
 * Foreign outer headers/transfers remain stale. Completed exact local duplicate
 * RESULT is idempotent; changed duplicates conflict without a provider replay.
 * The separate editor reservation shares ordinary ordering with form/physical
 * work; native8/9 have no ACK/cache. Pending form6 debt drains exact ACK7 first.
 * Pending native effect/close admits only9 with previously checked provider-owned
 * retirement material. Successful exact retired proof, local collection and
 * actual physical focus retirement precede native-effect publication ACK.
 * Original old-target retirement never retargets a replacement document; only
 * actual already-retired attestation/valid old-context lifecycle proves cleanup.
 * STALE, timeout, cancellation or a renderer field never supplies that proof.
 * EMPTY/service OK means no entry barrier; EMPTY/service UNAVAILABLE retains
 * shared work/reservation/effect debt. Aggregate barriers across all lanes while
 * still allowing an eligible retirement lane to drain. Poison reports CLOSED.
 */
#endif
