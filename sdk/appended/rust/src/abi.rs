//! Scalar constants corresponding to `include/foundation/appended/abi.h`.
//! The repository's binding conformance check compares these numeric values
//! against that authoritative header. Do not allocate wire IDs in this file.

pub const ABI_MAJOR: u32 = 1;
pub const ABI_MINOR: u32 = 0;
pub const ABI_VERSION: u32 = 0x00010000;
pub const ENVELOPE_BYTES: u32 = 64;
pub const MAX_MESSAGE_BYTES: u32 = 1048576;
pub const IMPORT_MODULE: &str = "foundation.kernel.v1";
pub const IMPORT_NAME: &str = "call";
pub const BOOTSTRAP_NAME: &str = "foundation.kernel";
pub const BOOTSTRAP_HANDLE: u64 = 0;
pub const BOOTSTRAP_SCHEMA_SHA256_HEX: &str = "47684bc0172f088d6805b7d49224f4975308e895f6e47824e51673ddd8b86890";
pub const BOOTSTRAP_SCHEMA_BYTES: [u8; 32] = [
    0x47, 0x68, 0x4b, 0xc0, 0x17, 0x2f, 0x08, 0x8d,
    0x68, 0x05, 0xb7, 0xd4, 0x92, 0x24, 0xf4, 0x97,
    0x53, 0x08, 0xe8, 0x95, 0xf6, 0xe4, 0x78, 0x24,
    0xe5, 0x16, 0x73, 0xdd, 0xd8, 0xb8, 0x68, 0x90,
];

pub const OFFSET_TOTAL: u32 = 0;
pub const OFFSET_MAJOR: u32 = 4;
pub const OFFSET_MINOR: u32 = 6;
pub const OFFSET_KIND: u32 = 8;
pub const OFFSET_FLAGS: u32 = 12;
pub const OFFSET_GENERATION: u32 = 16;
pub const OFFSET_SEQUENCE: u32 = 24;
pub const OFFSET_INTERFACE: u32 = 32;
pub const OFFSET_OPERATION: u32 = 40;
pub const OFFSET_PAYLOAD: u32 = 44;
pub const OFFSET_STATUS: u32 = 48;
pub const OFFSET_RESERVED: u32 = 52;
pub const OFFSET_CORRELATION: u32 = 56;

pub const MESSAGE_REQUEST: u32 = 1;
pub const MESSAGE_REPLY: u32 = 2;
pub const MESSAGE_EVENT: u32 = 3;
pub const MESSAGE_COMPLETION: u32 = 4;

pub const TRANSPORT_OK: u32 = 0;
pub const TRANSPORT_INVALID_RANGE: u32 = 1;
pub const TRANSPORT_REPLY_TOO_SMALL: u32 = 2;
pub const TRANSPORT_OVERLAP: u32 = 3;
pub const TRANSPORT_INVALID_ENVELOPE: u32 = 4;
pub const TRANSPORT_UNSUPPORTED_ENVELOPE: u32 = 5;
pub const TRANSPORT_STALE_GENERATION: u32 = 6;
pub const TRANSPORT_REPLAY: u32 = 7;
pub const TRANSPORT_EXHAUSTED: u32 = 8;
pub const TRANSPORT_INTERNAL_ERROR: u32 = 9;

pub const SERVICE_OK: u32 = 0;
pub const SERVICE_INVALID_REQUEST: u32 = 1;
pub const SERVICE_UNAVAILABLE: u32 = 2;
pub const SERVICE_NOT_FOUND: u32 = 3;
pub const SERVICE_UNSUPPORTED_VERSION: u32 = 4;
pub const SERVICE_SCHEMA_MISMATCH: u32 = 5;
pub const SERVICE_CONFLICT: u32 = 6;
pub const SERVICE_INVALID_HANDLE: u32 = 7;
pub const SERVICE_LIMIT_EXCEEDED: u32 = 8;
pub const SERVICE_UNKNOWN_OPERATION: u32 = 9;
pub const SERVICE_CLOSED: u32 = 10;
pub const SERVICE_INTERNAL_ERROR: u32 = 11;
pub const SERVICE_RESULT_AVAILABLE: u32 = 12;
pub const SERVICE_EXPIRED: u32 = 13;
pub const SERVICE_UNCERTAIN: u32 = 14;

pub const CONTROL_DISCOVER: u32 = 1;
pub const CONTROL_RESULT_READ: u32 = 2;
pub const CONTROL_RESULT_RELEASE: u32 = 3;
pub const CONTROL_LIMITS: u32 = 4;
pub const CONTROL_ACKNOWLEDGE: u32 = 5;

pub const APP_OK: u32 = 0;
pub const APP_INVALID_INPUT: u32 = 1;
pub const APP_FAILED: u32 = 2;
pub const APP_EXHAUSTED: u32 = 3;
pub const STEP_IDLE: u32 = 0;
pub const STEP_MORE: u32 = 1;
pub const STEP_FAILED: u32 = 2;
pub const STEP_EXHAUSTED: u32 = 3;
pub const SHUTDOWN_NORMAL: u32 = 0;
pub const SHUTDOWN_FAILED: u32 = 1;

pub const FIELD_U32: u32 = 1;
pub const FIELD_U64: u32 = 2;
pub const FIELD_I64: u32 = 3;
pub const FIELD_F64: u32 = 4;
pub const FIELD_BOOL: u32 = 5;
pub const FIELD_UTF8: u32 = 6;
pub const FIELD_BYTES: u32 = 7;
pub const FIELD_RECORD: u32 = 8;
pub const FIELD_RECORD_LIST: u32 = 9;
pub const FIELD_MUST_UNDERSTAND: u32 = 1;
