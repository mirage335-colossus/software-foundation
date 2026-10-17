#![no_std]
#![deny(unsafe_op_in_unsafe_fn)]

//! Allocation-free codecs and synchronous kernel calls for appended guests.
//!
//! Every wire integer is explicitly encoded little-endian. These Rust types
//! are ordinary local values; their native representation is never transmitted.
//! The common guest runtime owns allocation and lifecycle exports. Applications
//! implement its four `foundation_guest_*` hooks and provide a panic handler.

pub mod abi;
pub mod record;
pub mod bootstrap;
pub mod providers;

use abi::*;

/// Trap the current guest without unwinding or making a service call.
/// The host must destroy the failed instance before executing more guest code.
#[cfg(all(target_arch = "wasm32", target_os = "none"))]
pub fn abort() -> ! {
    core::arch::wasm32::unreachable()
}

/// A malformed or unsupported byte representation. Decoders do not allocate.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CodecError {
    Truncated,
    LimitExceeded,
    InvalidValue,
    UnsupportedVersion,
    UnknownRequiredField,
}

/// Host values corresponding to the 64-byte envelope; never copy its layout.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Envelope {
    pub major: u16,
    pub minor: u16,
    pub kind: u32,
    pub flags: u32,
    pub generation: u64,
    pub sequence: u64,
    pub interface_handle: u64,
    pub operation: u32,
    pub service_status: u32,
    pub correlation: u64,
}

impl Envelope {
    pub const fn request(generation: u64, sequence: u64, interface_handle: u64,
                         operation: u32) -> Self {
        Self {
            major: ABI_MAJOR as u16, minor: ABI_MINOR as u16,
            kind: MESSAGE_REQUEST, flags: 0, generation, sequence,
            interface_handle, operation, service_status: SERVICE_OK, correlation: 0,
        }
    }

    /// Writes a complete message and returns its initialized byte count.
    /// The output is unchanged when validation or the capacity check fails.
    pub fn encode(self, payload: &[u8], output: &mut [u8]) -> Result<usize, CodecError> {
        self.validate(payload.len())?;
        if payload.len() > (MAX_MESSAGE_BYTES - ENVELOPE_BYTES) as usize {
            return Err(CodecError::LimitExceeded);
        }
        let total = ENVELOPE_BYTES as usize + payload.len();
        if output.len() < total { return Err(CodecError::Truncated); }
        output[..ENVELOPE_BYTES as usize].fill(0);
        write_u32(output, OFFSET_TOTAL as usize, total as u32);
        write_u16(output, OFFSET_MAJOR as usize, self.major);
        write_u16(output, OFFSET_MINOR as usize, self.minor);
        write_u32(output, OFFSET_KIND as usize, self.kind);
        write_u32(output, OFFSET_FLAGS as usize, self.flags);
        write_u64(output, OFFSET_GENERATION as usize, self.generation);
        write_u64(output, OFFSET_SEQUENCE as usize, self.sequence);
        write_u64(output, OFFSET_INTERFACE as usize, self.interface_handle);
        write_u32(output, OFFSET_OPERATION as usize, self.operation);
        write_u32(output, OFFSET_PAYLOAD as usize, payload.len() as u32);
        write_u32(output, OFFSET_STATUS as usize, self.service_status);
        write_u64(output, OFFSET_CORRELATION as usize, self.correlation);
        output[ENVELOPE_BYTES as usize..total].copy_from_slice(payload);
        Ok(total)
    }

    /// Decodes one whole message. Returned payload borrows only `input`.
    pub fn decode(input: &[u8]) -> Result<(Self, &[u8]), CodecError> {
        if input.len() < ENVELOPE_BYTES as usize { return Err(CodecError::Truncated); }
        if input.len() > MAX_MESSAGE_BYTES as usize { return Err(CodecError::LimitExceeded); }
        let total = read_u32(input, OFFSET_TOTAL as usize) as usize;
        if total != input.len() || read_u32(input, OFFSET_PAYLOAD as usize) as usize
            != input.len() - ENVELOPE_BYTES as usize
            || read_u32(input, OFFSET_RESERVED as usize) != 0 {
            return Err(CodecError::InvalidValue);
        }
        let envelope = Self {
            major: read_u16(input, OFFSET_MAJOR as usize),
            minor: read_u16(input, OFFSET_MINOR as usize),
            kind: read_u32(input, OFFSET_KIND as usize),
            flags: read_u32(input, OFFSET_FLAGS as usize),
            generation: read_u64(input, OFFSET_GENERATION as usize),
            sequence: read_u64(input, OFFSET_SEQUENCE as usize),
            interface_handle: read_u64(input, OFFSET_INTERFACE as usize),
            operation: read_u32(input, OFFSET_OPERATION as usize),
            service_status: read_u32(input, OFFSET_STATUS as usize),
            correlation: read_u64(input, OFFSET_CORRELATION as usize),
        };
        envelope.validate(input.len() - ENVELOPE_BYTES as usize)?;
        Ok((envelope, &input[ENVELOPE_BYTES as usize..]))
    }

    fn validate(self, payload_bytes: usize) -> Result<(), CodecError> {
        if self.major != ABI_MAJOR as u16 || self.minor > ABI_MINOR as u16 {
            return Err(CodecError::UnsupportedVersion);
        }
        if !(MESSAGE_REQUEST..=MESSAGE_COMPLETION).contains(&self.kind)
            || self.flags != 0 || self.service_status > SERVICE_UNCERTAIN
            || self.generation == 0 || self.sequence == 0
            || (self.kind == MESSAGE_REQUEST && (self.service_status != 0 || self.correlation != 0))
            || (self.kind == MESSAGE_REPLY && self.service_status == SERVICE_RESULT_AVAILABLE
                && (self.correlation == 0 || payload_bytes != 0))
            || (self.kind == MESSAGE_REPLY && self.service_status != SERVICE_RESULT_AVAILABLE
                && self.correlation != 0) {
            return Err(CodecError::InvalidValue);
        }
        Ok(())
    }
}

/// Sequence IDs are never reused or wrapped. Exhaustion destroys the instance.
#[derive(Debug)]
pub struct Sequence {
    next: u64,
    exhausted: bool,
}

impl Sequence {
    pub const fn new() -> Self { Self { next: 1, exhausted: false } }
    pub fn issue(&mut self) -> Option<u64> {
        if self.exhausted { return None; }
        let value = self.next;
        if value == u64::MAX { self.exhausted = true; } else { self.next += 1; }
        Some(value)
    }
}

impl Default for Sequence {
    fn default() -> Self { Self::new() }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CallError {
    Transport(u32),
    Codec(CodecError),
    UnexpectedReply,
    Service(u32),
    Exhausted,
}

/// Borrow one runtime-provided initialized input allocation for this invocation.
///
/// # Safety
/// `input` must denote `bytes` initialized bytes in one live allocation, with no
/// mutable alias for the lifetime chosen by the caller. The allocation must stay
/// valid until the returned borrow ends, and must not cross an invocation.
/// A linear-memory bounds check alone is insufficient to establish this contract.
pub unsafe fn borrow_input<'a>(input: *const u8, bytes: u32) -> Result<&'a [u8], CodecError> {
    if bytes == 0 { return Ok(&[]); }
    if input.is_null() { return Err(CodecError::InvalidValue); }
    if bytes > MAX_MESSAGE_BYTES { return Err(CodecError::LimitExceeded); }
    // SAFETY: required of the hook implementation by the function contract.
    Ok(unsafe { core::slice::from_raw_parts(input, bytes as usize) })
}

/// Makes one synchronous call. The host borrows both buffers only until return.
/// Replies are validated and tied to this request before being exposed.
#[cfg(all(target_arch = "wasm32", target_os = "none"))]
pub fn call<'a>(request: &[u8], reply: &'a mut [u8]) -> Result<(Envelope, &'a [u8]), CallError> {
    let (sent, _) = Envelope::decode(request).map_err(CallError::Codec)?;
    if sent.kind != MESSAGE_REQUEST || request.len() > u32::MAX as usize
        || reply.len() > MAX_MESSAGE_BYTES as usize {
        return Err(CallError::Codec(CodecError::InvalidValue));
    }
    if reply.len() < ENVELOPE_BYTES as usize {
        return Err(CallError::Codec(CodecError::Truncated));
    }
    // The safe borrows guarantee valid nonoverlapping allocations. The common
    // runtime enforces the lifecycle guard before reaching the sole transport
    // import. In particular, constructors cannot call application services.
    let status = unsafe { foundation_guest_call(request.as_ptr(),
        request.len() as u32, reply.as_mut_ptr(), reply.len() as u32) };
    if status != TRANSPORT_OK { return Err(CallError::Transport(status)); }
    let total = read_u32(reply, OFFSET_TOTAL as usize) as usize;
    if total < ENVELOPE_BYTES as usize || total > reply.len() {
        return Err(CallError::UnexpectedReply);
    }
    let (received, payload) = Envelope::decode(&reply[..total]).map_err(CallError::Codec)?;
    if received.kind != MESSAGE_REPLY || received.generation != sent.generation
        || received.sequence != sent.sequence || received.interface_handle != sent.interface_handle
        || received.operation != sent.operation {
        return Err(CallError::UnexpectedReply);
    }
    Ok((received, payload))
}

#[cfg(all(target_arch = "wasm32", target_os = "none"))]
extern "C" {
    fn foundation_guest_call(request: *const u8, request_bytes: u32,
                            reply: *mut u8, reply_capacity: u32) -> u32;
}

pub(crate) fn read_u16(bytes: &[u8], at: usize) -> u16 {
    u16::from_le_bytes([bytes[at], bytes[at + 1]])
}
pub(crate) fn read_u32(bytes: &[u8], at: usize) -> u32 {
    u32::from_le_bytes([bytes[at], bytes[at + 1], bytes[at + 2], bytes[at + 3]])
}
pub(crate) fn read_u64(bytes: &[u8], at: usize) -> u64 {
    u64::from_le_bytes([bytes[at], bytes[at + 1], bytes[at + 2], bytes[at + 3],
        bytes[at + 4], bytes[at + 5], bytes[at + 6], bytes[at + 7]])
}
pub(crate) fn write_u16(bytes: &mut [u8], at: usize, value: u16) {
    bytes[at..at + 2].copy_from_slice(&value.to_le_bytes());
}
pub(crate) fn write_u32(bytes: &mut [u8], at: usize, value: u32) {
    bytes[at..at + 4].copy_from_slice(&value.to_le_bytes());
}
pub(crate) fn write_u64(bytes: &mut [u8], at: usize, value: u64) {
    bytes[at..at + 8].copy_from_slice(&value.to_le_bytes());
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn envelope_is_canonical_little_endian() {
        let envelope = Envelope::request(0x0807060504030201, 9, 10, 11);
        let mut encoded = [0xa5; 68];
        assert_eq!(envelope.encode(&[0xaa, 0xbb, 0xcc, 0xdd], &mut encoded), Ok(68));
        assert_eq!(&encoded[..16], &[68, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0]);
        assert_eq!(&encoded[16..24], &[1, 2, 3, 4, 5, 6, 7, 8]);
        assert_eq!(Envelope::decode(&encoded), Ok((envelope, &[0xaa, 0xbb, 0xcc, 0xdd][..])));
        encoded[52] = 1;
        assert_eq!(Envelope::decode(&encoded), Err(CodecError::InvalidValue));
    }

    #[test]
    fn failed_encode_keeps_output() {
        let mut output = [0xa5; 63];
        assert_eq!(Envelope::request(1, 1, 0, 1).encode(&[], &mut output), Err(CodecError::Truncated));
        assert_eq!(output, [0xa5; 63]);
    }

    #[test]
    fn unknown_status_is_an_error() {
        let mut envelope = Envelope::request(1, 1, 0, 1);
        envelope.service_status = SERVICE_UNCERTAIN + 1;
        assert_eq!(envelope.encode(&[], &mut [0; 64]), Err(CodecError::InvalidValue));
    }

    #[test]
    fn sequence_exhaustion_never_wraps() {
        let mut sequence = Sequence { next: u64::MAX, exhausted: false };
        assert_eq!(sequence.issue(), Some(u64::MAX));
        assert_eq!(sequence.issue(), None);
    }
}
