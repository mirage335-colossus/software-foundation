// SPDX-License-Identifier: CC0-1.0
// Additive document-provider source contract. No installed capability is implied.
#ifndef FOUNDATION_APPENDED_ENGINE_PROVIDER_DOCUMENT_V2_H
#define FOUNDATION_APPENDED_ENGINE_PROVIDER_DOCUMENT_V2_H

#include "engine_provider.h"

// The canonical base header/ABI1.0 is unchanged. This selects an explicit NEW
// provider profile using the same C table layouts, never a minor0 downgrade.
// Its getter requires maximum_minor>=1 and returns provider table minor1.
// Host callbacks still use the exact base ABI1.0 table (no added callback).
#define BIB_ENGINE_DOCUMENT_V2_ABI_MAJOR 1u
#define BIB_ENGINE_DOCUMENT_V2_ABI_MINOR 1u
#define BIB_ENGINE_DOCUMENT_V2_HOST_ABI_MAJOR 1u
#define BIB_ENGINE_DOCUMENT_V2_HOST_ABI_MINOR 0u
#define BIB_ENGINE_CAP_SEMANTIC_SNAPSHOT_V2 (UINT64_C(1) << 9)
#define BIB_ENGINE_CAP_FORM_ACTION_V2 (UINT64_C(1) << 10)
#define BIB_ENGINE_QUERY_DOCUMENT_FORMS_V2 3u
#define BIB_ENGINE_COMMAND_FORM_ACTION_V2 6u
#define BIB_ENGINE_COMMAND_ACK_FORM_ACTION_V2 7u

#define BIB_ENGINE_DOCUMENT_V2_QUERY_BYTES 48u
#define BIB_ENGINE_DOCUMENT_V2_MAX_ACTION_BYTES 6246u
#define BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY 1048576u
#define BIB_ENGINE_DOCUMENT_V2_ACK_REQUEST_BYTES 8u
#define BIB_ENGINE_DOCUMENT_V2_ACK_REPLY_CAPACITY 16u
#define BIB_ENGINE_DOCUMENT_V2_ACK_RESULT_BYTES 16u
#define BIB_ENGINE_DOCUMENT_V2_ACK_SEQUENCE_OFFSET 0u
#define BIB_ENGINE_DOCUMENT_V2_ACK_CODE_OFFSET 8u
#define BIB_ENGINE_DOCUMENT_V2_ACK_RESERVED_OFFSET 12u
#define BIB_ENGINE_DOCUMENT_V2_ACK_RETIRED 0u
#define BIB_ENGINE_DOCUMENT_V2_ACK_ALREADY_RETIRED 1u
#define BIB_ENGINE_DOCUMENT_V2_ACK_STALE 2u
#define BIB_ENGINE_DOCUMENT_V2_MAX_ORDINARY_SEQUENCE (UINT64_MAX - UINT64_C(1))
#define BIB_ENGINE_DOCUMENT_V2_MAX_ACK_SEQUENCE UINT64_MAX

#define BIB_ENGINE_DOCUMENT_V2_SCHEMA_SHA256_HEX "f11fd061350f8d663dbcdec7cf0a063e4fb0ff3564d285076690f58e8a84143d"
#define BIB_ENGINE_DOCUMENT_V2_ACK_SCHEMA_SHA256_HEX "1eb6c2d4f56acebc1423d9e2b5bf9a1717a99963a5c3f11f4b9d7b0fe33b50f5"
#define BIB_ENGINE_DOCUMENT_V2_BASE_HEADER_SHA256_HEX "a8e89da85d34b29a4d1bc454495791fa604b81e3477e48ce8ca902e4333a9c0d"

// ACK7 payload: original_action_sequence:u64LE in 1..MAX_ORDINARY_SEQUENCE.
// Validate all input and reserve the full 16-byte reply before admission.
// First match a retained exact ACK request key: return its IDENTICAL bytes,
// including an old-document STALE result, before current-document/high-water/
// exhaustion checks and without another engine entry or high-water change. An uncached sequence <= high-water rejects pre-entry as
// BIB_ENGINE_STALE, disposition0, bytes0. Never reconstruct an expired success.
// Fresh command sequence exceeds global high-water and original action sequence.
// Result16: original_sequence:u64LE, code:u32LE, reserved:u32LE(0).
// Checked metadata result: provider_status0/disposition1/handled0/bytes16.
// Fresh unmatched ACK returns STALE2; retain the owner's original action result.
// Code0/1 cleanup for any document requires the exact retained outcome or
// latest retirement proof. A fresh unmatched old identity returns STALE2. STALE
// never clears an action or another retirement proof.
// Keep one action, one latest ACK reply (code0/1/2), and one latest retirement
// tombstone holding the original successful ACK full key plus exact code0 bytes.
// Fresh duplicate code1 cannot rewrite those original code0 bytes. Only a new
// code0 retirement replaces the tombstone. ACK requires no ACK-of-ACK.
// Ordinary sequences leave headroom for final ACK at MAX. Afterwards stop new
// work; exact cached receipt redelivery remains possible. Never wrap or reset.
// No DOM/Registry/host callback runs during ACK encoding or retirement.
//
// New-profile BuildV1.contract_header_sha256 is the SHA256 of canonical
// abi/engine/document-v2/contract.json, binding base+extension exact byte hashes.
// The extension cannot embed its own/composite/catalog/recipe digest. Legacy
// BuildV1 retains the canonical base digest. Manifest single-file header_sha256
// continues to mean that file's bytes; it is not silently a composite digest.
#endif
