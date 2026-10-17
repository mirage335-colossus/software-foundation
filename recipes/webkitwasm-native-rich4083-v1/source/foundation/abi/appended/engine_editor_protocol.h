/* SPDX-License-Identifier: CC0-1.0 */
#ifndef FOUNDATION_ENGINE_EDITOR_PROTOCOL_V1_H
#define FOUNDATION_ENGINE_EDITOR_PROTOCOL_V1_H
#include <stdint.h>
/* Additive explicit2035 contract. Never activates base operation2. All three
 * native operations require a full Host TURN and an exact ordinary sequence.
 * The copied transport keeps its existing outer COMMAND/QUERY operations. */
#define BIB_ENGINE_EDITOR_PROTOCOL_VERSION UINT32_C(1)
#define BIB_ENGINE_EDITOR_CAPABILITIES UINT64_C(2035)
#define BIB_ENGINE_EDITOR_SURFACE_CAPABILITIES UINT64_C(8255)
#define BIB_ENGINE_EDITOR_SURFACE_PROTOCOL_VERSION UINT32_C(2)
#define BIB_ENGINE_QUERY_EDITOR_PROJECTION_V1 UINT32_C(4)
#define BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1 UINT32_C(8)
#define BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1 UINT32_C(9)
#define BIB_ENGINE_EDITOR_WIRE_HEADER_BYTES UINT32_C(16)
#define BIB_ENGINE_EDITOR_MAX_WIRE_BYTES UINT32_C(1048576)
#define BIB_ENGINE_EDITOR_REPLY_CAPACITY BIB_ENGINE_EDITOR_MAX_WIRE_BYTES
#define BIB_ENGINE_EDITOR_MAX_QUERY_BYTES UINT32_C(236)
#define BIB_ENGINE_EDITOR_MAX_TEXT_BYTES UINT32_C(65536)
#define BIB_ENGINE_EDITOR_MAX_OWNER_BYTES UINT32_C(128)
#define BIB_ENGINE_EDITOR_MAX_REASON_BYTES UINT32_C(512)
#define BIB_ENGINE_EDITOR_MAX_KEY_BYTES UINT32_C(64)
#define BIB_ENGINE_EDITOR_MAX_GROUPS UINT32_C(64)
#define BIB_ENGINE_EDITOR_MAX_DEPENDENCIES UINT32_C(8)
/* bytes0..7 = {'B','I','B','E','D','V','1',0}; kind LEu16 at8,
 * flags LEu16 zero at10, complete encoded length LEu32 at12. No trailing bytes.
 * Booleans are exact0/1 bytes; enum values and every UTF/count/range are closed.
 * Never serialize C/C++ structure layout, pointers, padding or function tables. */
/* Every request body starts with five LEu64s: worker_epoch, application_instance,
 * document_sequence, service_generation, request_sequence (offsets16..55).
 * Query replies put actual observation_revision at16, then the same five-field
 * key at24..63. Command replies put that key at16..55. Deep validation joins
 * the complete key to the outer C request and compiled worker; no GUI revision
 * or mapping/session ID substitutes for the ordinary provider sequence. */
#define BIB_ENGINE_EDITOR_WIRE_PROJECTION_QUERY UINT32_C(1)
#define BIB_ENGINE_EDITOR_WIRE_PROJECTION_REPLY UINT32_C(2)
#define BIB_ENGINE_EDITOR_WIRE_NATIVE_REQUEST UINT32_C(3)
#define BIB_ENGINE_EDITOR_WIRE_NATIVE_RESULT UINT32_C(4)
#define BIB_ENGINE_EDITOR_WIRE_REVOCATION UINT32_C(5)
/* Bounds include encoded header. Existing copied request prefix sizes remain
 * command56/query48; only this explicit editor catalog admits these maxima. */
#define BIB_ENGINE_EDITOR_COPIED_COMMAND_MAX_BYTES (UINT32_C(56) + BIB_ENGINE_EDITOR_MAX_WIRE_BYTES)
#define BIB_ENGINE_EDITOR_COPIED_QUERY_MAX_BYTES (UINT32_C(48) + BIB_ENGINE_EDITOR_MAX_QUERY_BYTES)
#define BIB_ENGINE_EDITOR_COPIED_COMMAND_REPLY_CAPACITY (UINT32_C(80) + UINT32_C(24) + BIB_ENGINE_EDITOR_REPLY_CAPACITY)
#define BIB_ENGINE_EDITOR_COPIED_QUERY_REPLY_CAPACITY (UINT32_C(80) + UINT32_C(16) + BIB_ENGINE_EDITOR_REPLY_CAPACITY)
#endif
