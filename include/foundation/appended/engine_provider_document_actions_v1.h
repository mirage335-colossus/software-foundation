// SPDX-License-Identifier: CC0-1.0
// Additive source contract only. No installed/native capability is implied.
#ifndef FOUNDATION_APPENDED_ENGINE_PROVIDER_DOCUMENT_ACTIONS_V1_H
#define FOUNDATION_APPENDED_ENGINE_PROVIDER_DOCUMENT_ACTIONS_V1_H

#include "engine_provider_document_v2.h"

// Explicit kind4 only. Same provider ABI1.1 and host ABI1.0 C table layouts.
// Never infer this profile from a mask or widen an old profile/catalog.
#define BIB_ENGINE_DOCUMENT_ACTIONS_V1_ABI_MAJOR 1u
#define BIB_ENGINE_DOCUMENT_ACTIONS_V1_ABI_MINOR 1u
#define BIB_ENGINE_DOCUMENT_ACTIONS_V1_HOST_ABI_MAJOR 1u
#define BIB_ENGINE_DOCUMENT_ACTIONS_V1_HOST_ABI_MINOR 0u
#define BIB_ENGINE_CAP_DOCUMENT_ACTIONS_V1 (UINT64_C(1) << 11)
#define BIB_ENGINE_COMMAND_DOCUMENT_ACTION_V1 10u
#define BIB_ENGINE_COMMAND_ACK_DOCUMENT_ACTION_V1 11u
#define BIB_ENGINE_DOCUMENT_ACTIONS_V1_PROFILE_KIND 4u
#define BIB_ENGINE_DOCUMENT_ACTIONS_V1_PROVIDER_CAPABILITIES UINT64_C(4083)
#define BIB_ENGINE_DOCUMENT_ACTIONS_V1_PROFILE_NAME "foundation-engine-copied4083-ndv2-editor-document-actions-v1"
#define BIB_ENGINE_DOCUMENT_ACTIONS_V1_REQUEST_BYTES 128u
#define BIB_ENGINE_DOCUMENT_ACTIONS_V1_COMPLETION_PREFIX_BYTES 72u
#define BIB_ENGINE_DOCUMENT_ACTIONS_V1_MAX_PUBLICATION_BYTES 911505u
#define BIB_ENGINE_DOCUMENT_ACTIONS_V1_MAX_REPLY_BYTES 911577u
#define BIB_ENGINE_DOCUMENT_ACTIONS_V1_REPLY_CAPACITY 1048576u
#define BIB_ENGINE_DOCUMENT_ACTIONS_V1_ACK_REQUEST_BYTES 8u
#define BIB_ENGINE_DOCUMENT_ACTIONS_V1_ACK_RESULT_BYTES 16u
#define BIB_ENGINE_DOCUMENT_ACTIONS_V1_ACK_REPLY_CAPACITY 16u
#define BIB_ENGINE_DOCUMENT_ACTIONS_V1_MAX_ORDINARY_SEQUENCE (UINT64_MAX - UINT64_C(1))
#define BIB_ENGINE_DOCUMENT_ACTIONS_V1_MAX_ACK_SEQUENCE UINT64_MAX
#define BIB_ENGINE_DOCUMENT_ACTIONS_V1_SCHEMA_SHA256_HEX "b5603ec73b05ff2efb4b0a9405b98095789de4cc2a950e7b69813a1845cd9d64"
#define BIB_ENGINE_DOCUMENT_ACTIONS_V1_ACK_SCHEMA_SHA256_HEX "a4793ce28417ffa97b754344624c9d9d78093acba5792bde006c7b95482dfcbe"

// DAV1 v1 packet kinds1 request/2 completion. Header16: magic:u32LE,
// version:u16LE, kind:u8, flags:u8(0), full_length:u32LE, reserved:u32LE(0).
// Both keys: worker/app/document/service/ordinary-sequence/nested-token, six
// u64LE values. Focus0/activate1/select2 require nested!=0; chooser3 nested=0.
// Request Version generation=app, epoch=service, revision!=0; exact union and
// all zero padding are specified by the canonical binary-schema.json.
// Command10 requires the full Host->Bridge->common-VM-JSLock TURN. Reserve
// complete owned request/output/fallback storage before native entry; validate
// displayed Version and published weak node IDs on the actual same Page.
// Completion result/code/effects/presence/length are closed domains. Actual
// same-target NDV2 Publication RECORD follows (no NDV2 packet/query header).
// Body request_id remains0: an action never manufactures accepted_query.
// Context replacement is consumed effects-entered/code9/no old publication.
// Unknown outer transport is terminal, never a consumed semantic completion.
//
// ACK11 is only command10 metadata retirement. It never retires form6, performs
// DOM/layout/Session/Host TURN/Registry work, or resets the global sequence.
// Exact cached receipt keys precede current-target/high-water/exhaustion checks.
// Keep one global form6/body10 action slot; cross-family ACK is consumed STALE2
// and preserves that slot/proof. Preserve original success tombstone bytes;
// fresh code1 does not rewrite them. Ordinary MAX-1 leaves final ACKMAX headroom.
// ACK payload8: original sequence:u64LE. Reply16: original:u64LE, code:u32LE
// (retired0/already-retired1/stale2), reserved:u32LE(0). No ACK-of-ACK.
//
// New BuildV1.contract_header_sha256 binds canonical new contract.json, not
// this extension alone. Old header/contract/catalog/schema bytes stay frozen.
// This header deliberately embeds no self/composite/catalog/recipe digest.
#endif
