//! Additive synchronous module providers, defined by `abi/appended/providers/v1.json`.
//! This service uses the existing bootstrap, transport and lifecycle exports.
//! All buffers belong to the caller; no codec or service helper allocates.

use crate::{abi::*, bootstrap::DiscoveryQuery, record::{self, Field, Record}, CodecError,
    Envelope};
#[cfg(all(target_arch = "wasm32", target_os = "none"))]
use crate::{bootstrap::{self, Client}, CallError};

pub const SERVICE_NAME: &str = "foundation.providers";
pub const MAJOR: u32 = 1;
pub const MINOR: u32 = 0;
pub const REGISTER: u32 = 1;
pub const RESPOND: u32 = 2;
pub const DISCOVER: u32 = 3;
pub const EVENT_CALL: u32 = 1;
pub const MAX_PROVIDERS: u32 = 32;
pub const MAX_PAYLOAD_BYTES: u32 = 32768;
pub const MAX_RETAINED_CALLS: u32 = 64;
pub const MAX_RETAINED_BYTES: u32 = 1048576;
pub const MAX_NAME_BYTES: u32 = 128;
pub const SCHEMA_SHA256_HEX: &str = "846fd7a2aa16758db702aa30791730ab6de6635a50ba90234995cb06a7ec93de";
pub const SCHEMA: [u8; 32] = [
    0x84, 0x6f, 0xd7, 0xa2, 0xaa, 0x16, 0x75, 0x8d,
    0xb7, 0x02, 0xaa, 0x30, 0x79, 0x17, 0x30, 0xab,
    0x6d, 0xe6, 0x63, 0x5a, 0x50, 0xba, 0x90, 0x23,
    0x49, 0x95, 0xcb, 0x06, 0xa7, 0xec, 0x93, 0xde,
];

/// A borrowed application contract. Its name and schema are copied by the host.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Descriptor<'a> {
    pub name: &'a str,
    pub major: u32,
    pub minor: u32,
    pub schema: &'a [u8; 32],
    pub maximum_request_bytes: u32,
    pub maximum_reply_bytes: u32,
}

fn valid_name(name: &str) -> bool {
    if name.is_empty() || name.len() > MAX_NAME_BYTES as usize || !name.contains('.') {
        return false;
    }
    let mut first = true;
    for byte in name.bytes() {
        match byte {
            b'.' => { if first { return false; } first = true; },
            b'a'..=b'z' => first = false,
            b'0'..=b'9' | b'_' | b'-' if !first => {},
            _ => return false,
        }
    }
    !first
}

fn valid_query(query: DiscoveryQuery<'_>) -> bool {
    valid_name(query.name) && query.major != 0 && query.major <= u16::MAX as u32
        && query.maximum_minor <= u16::MAX as u32
        && query.minimum_minor <= query.maximum_minor
        && query.schema.is_none_or(|schema| schema.iter().any(|byte| *byte != 0))
}

/// Encodes registration fields, including zero-sized request/reply bounds.
/// Registration is permitted only in the application's initialize hook.
pub fn encode_registration(descriptor: Descriptor<'_>, output: &mut [u8]) -> Result<usize, CodecError> {
    if !valid_name(descriptor.name) || descriptor.name.starts_with("foundation.")
        || descriptor.major == 0 || descriptor.major > u16::MAX as u32
        || descriptor.minor > u16::MAX as u32
        || !descriptor.schema.iter().any(|byte| *byte != 0)
        || descriptor.maximum_request_bytes > MAX_PAYLOAD_BYTES
        || descriptor.maximum_reply_bytes > MAX_PAYLOAD_BYTES {
        return Err(CodecError::InvalidValue);
    }
    let major = descriptor.major.to_le_bytes();
    let minor = descriptor.minor.to_le_bytes();
    let request = descriptor.maximum_request_bytes.to_le_bytes();
    let reply = descriptor.maximum_reply_bytes.to_le_bytes();
    record::encode(&[
        Field::new(1, FIELD_UTF8 as u8, true, descriptor.name.as_bytes()),
        Field::new(2, FIELD_U32 as u8, true, &major),
        Field::new(3, FIELD_U32 as u8, true, &minor),
        Field::new(4, FIELD_BYTES as u8, true, descriptor.schema),
        Field::new(5, FIELD_U32 as u8, true, &request),
        Field::new(6, FIELD_U32 as u8, true, &reply),
    ], output)
}

fn checked_record(bytes: &[u8], maximum_id: u16) -> Result<Record<'_>, CodecError> {
    let record = Record::decode(bytes)?;
    for field in record.fields() {
        if field.id <= maximum_id && !field.must_understand {
            return Err(CodecError::InvalidValue);
        }
        if field.id > maximum_id && field.must_understand {
            return Err(CodecError::UnknownRequiredField);
        }
    }
    Ok(record)
}

/// Validates a registration reply and returns the generation-owned provider token.
pub fn decode_registration(bytes: &[u8]) -> Result<u64, CodecError> {
    let mut handle = None;
    for field in checked_record(bytes, 1)?.fields() {
        if field.id == 1 { handle = Some(field.u64()?); }
    }
    match handle {
        Some(handle) if handle != 0 => Ok(handle),
        _ => Err(CodecError::InvalidValue),
    }
}

pub fn encode_discovery(query: DiscoveryQuery<'_>, output: &mut [u8]) -> Result<usize, CodecError> {
    if !valid_query(query) { return Err(CodecError::InvalidValue); }
    // The additive discovery request has the same field layout as bootstrap.
    crate::bootstrap::encode_discovery(query, output)
}

/// Owned contract values; no discovery reply borrow survives acknowledgement.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Discovery {
    pub handle: u64,
    pub major: u32,
    pub minor: u32,
    pub schema: [u8; 32],
    pub maximum_request_bytes: u32,
    pub maximum_reply_bytes: u32,
}

impl Discovery {
    pub fn decode(bytes: &[u8], query: DiscoveryQuery<'_>) -> Result<Self, CodecError> {
        if !valid_query(query) { return Err(CodecError::InvalidValue); }
        let mut result = Self { handle: 0, major: 0, minor: 0, schema: [0; 32],
            maximum_request_bytes: 0, maximum_reply_bytes: 0 };
        let mut present = 0u32;
        for field in checked_record(bytes, 7)?.fields() {
            match field.id {
                1 => result.handle = field.u64()?,
                2 => if field.utf8()? != query.name { return Err(CodecError::InvalidValue); },
                3 => result.major = field.u32()?,
                4 => result.minor = field.u32()?,
                5 => {
                    let schema = field.bytes()?;
                    if schema.len() != 32 { return Err(CodecError::InvalidValue); }
                    result.schema.copy_from_slice(schema);
                },
                6 => result.maximum_request_bytes = field.u32()?,
                7 => result.maximum_reply_bytes = field.u32()?,
                _ => continue,
            }
            present |= 1 << (field.id - 1);
        }
        if present != 127 || result.handle == 0 || result.major != query.major
            || result.minor < query.minimum_minor || result.minor > query.maximum_minor
            || result.maximum_request_bytes > MAX_PAYLOAD_BYTES
            || result.maximum_reply_bytes > MAX_PAYLOAD_BYTES
            || !result.schema.iter().any(|byte| *byte != 0)
            || query.schema.is_some_and(|schema| *schema != result.schema) {
            return Err(CodecError::InvalidValue);
        }
        Ok(result)
    }
}

/// One borrowed host invocation. The invocation token is envelope correlation,
/// while the event's sequence belongs to the host's independent sequence source.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Call<'a> {
    pub invocation: u64,
    pub provider: u64,
    pub operation: u32,
    pub payload: &'a [u8],
    generation: u64,
    service_handle: u64,
}

impl<'a> Call<'a> {
    pub fn decode(input: &'a [u8], generation: u64, service_handle: u64) -> Result<Self, CodecError> {
        let (envelope, payload) = Envelope::decode(input)?;
        if service_handle == 0 || envelope.kind != MESSAGE_EVENT
            || envelope.generation != generation || envelope.interface_handle != service_handle
            || envelope.operation != EVENT_CALL || envelope.service_status != SERVICE_OK
            || envelope.correlation == 0 {
            return Err(CodecError::InvalidValue);
        }
        let mut provider = None;
        let mut operation = None;
        let mut payload_bytes = None;
        for field in checked_record(payload, 3)?.fields() {
            match field.id {
                1 => provider = Some(field.u64()?),
                2 => operation = Some(field.u32()?),
                3 => payload_bytes = Some(field.bytes()?),
                _ => {},
            }
        }
        let provider = provider.ok_or(CodecError::InvalidValue)?;
        let payload = payload_bytes.ok_or(CodecError::InvalidValue)?;
        if provider == 0 { return Err(CodecError::InvalidValue); }
        if payload.len() > MAX_PAYLOAD_BYTES as usize { return Err(CodecError::LimitExceeded); }
        Ok(Self { invocation: envelope.correlation, provider,
            operation: operation.ok_or(CodecError::InvalidValue)?, payload,
            generation, service_handle })
    }
}

/// Encodes an explicit terminal response, retaining required field 4 even empty.
/// `RESULT_AVAILABLE` and nonempty error payloads are not provider responses.
pub fn encode_response(invocation: u64, provider: u64, status: u32, payload: &[u8],
                       output: &mut [u8]) -> Result<usize, CodecError> {
    if invocation == 0 || provider == 0 || status > SERVICE_UNCERTAIN
        || status == SERVICE_RESULT_AVAILABLE || (status != SERVICE_OK && !payload.is_empty()) {
        return Err(CodecError::InvalidValue);
    }
    if payload.len() > MAX_PAYLOAD_BYTES as usize { return Err(CodecError::LimitExceeded); }
    let invocation = invocation.to_le_bytes();
    let provider = provider.to_le_bytes();
    let status = status.to_le_bytes();
    record::encode(&[
        Field::new(1, FIELD_U64 as u8, true, &invocation),
        Field::new(2, FIELD_U64 as u8, true, &provider),
        Field::new(3, FIELD_U32 as u8, true, &status),
        Field::new(4, FIELD_BYTES as u8, true, payload),
    ], output)
}

/// Separate caller-provided record, complete request and complete reply buffers.
/// Successful helpers may overwrite all three, including acknowledgement bytes.
pub struct Scratch<'a> {
    pub payload: &'a mut [u8],
    pub request: &'a mut [u8],
    pub reply: &'a mut [u8],
}

/// A bootstrap-discovered provider gateway bound to one module generation.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Service {
    handle: u64,
    generation: u64,
}

impl Service {
    pub fn handle(self) -> u64 { self.handle }
    pub fn decode_call<'a>(self, input: &'a [u8]) -> Result<Call<'a>, CodecError> {
        Call::decode(input, self.generation, self.handle)
    }

    /// Uses the exact service schema via ordinary bootstrap discovery.
    /// Every completed outcome is acknowledged using this same client.
    #[cfg(all(target_arch = "wasm32", target_os = "none"))]
    pub fn discover(client: &mut Client, scratch: &mut Scratch<'_>) -> Result<Self, CallError> {
        Self::discover_optional(client, scratch)?.ok_or(CallError::Service(SERVICE_NOT_FOUND))
    }

    /// Return `None` only for an absent gateway whose completed discovery was
    /// successfully acknowledged. An acknowledgement failure always stays an
    /// error, even when its status is itself `SERVICE_NOT_FOUND`.
    #[cfg(all(target_arch = "wasm32", target_os = "none"))]
    pub fn discover_optional(client: &mut Client, scratch: &mut Scratch<'_>) -> Result<Option<Self>, CallError> {
        let query = DiscoveryQuery { name: SERVICE_NAME, major: MAJOR,
            minimum_minor: MINOR, maximum_minor: MINOR, schema: Some(&SCHEMA) };
        let count = bootstrap::encode_discovery(query, scratch.payload).map_err(CallError::Codec)?;
        let (envelope, payload) = client.invoke(BOOTSTRAP_HANDLE, CONTROL_DISCOVER,
            &scratch.payload[..count], scratch.request, scratch.reply)?;
        let result = completed(envelope, payload, |bytes| {
            checked_record(bytes, 6).map_err(CallError::Codec)?;
            bootstrap::Discovery::decode(bytes, query).map(|found| Self {
                handle: found.handle, generation: client.context().generation,
            }).map_err(CallError::Codec)
        });
        let optional = match result {
            Ok(service) => Ok(Some(service)),
            Err(CallError::Service(SERVICE_NOT_FOUND)) => Ok(None),
            Err(error) => Err(error),
        };
        retire(client, envelope.sequence, optional, scratch)
    }

    #[cfg(all(target_arch = "wasm32", target_os = "none"))]
    fn check_client(self, client: &Client) -> Result<(), CallError> {
        if self.handle == 0 || self.generation != client.context().generation {
            return Err(CallError::Codec(CodecError::InvalidValue));
        }
        Ok(())
    }

    /// Registers during initialization. The returned token is not a native
    /// Registry service handle and must be matched against incoming calls.
    #[cfg(all(target_arch = "wasm32", target_os = "none"))]
    pub fn register(self, client: &mut Client, descriptor: Descriptor<'_>, scratch: &mut Scratch<'_>)
        -> Result<u64, CallError> {
        self.check_client(client)?;
        let count = encode_registration(descriptor, scratch.payload).map_err(CallError::Codec)?;
        let (envelope, payload) = client.invoke(self.handle, REGISTER, &scratch.payload[..count],
            scratch.request, scratch.reply)?;
        let result = completed(envelope, payload, |bytes| decode_registration(bytes).map_err(CallError::Codec));
        retire(client, envelope.sequence, result, scratch)
    }

    /// Queries a module-owned contract through the provider gateway.
    #[cfg(all(target_arch = "wasm32", target_os = "none"))]
    pub fn find(self, client: &mut Client, query: DiscoveryQuery<'_>, scratch: &mut Scratch<'_>)
        -> Result<Discovery, CallError> {
        self.check_client(client)?;
        let count = encode_discovery(query, scratch.payload).map_err(CallError::Codec)?;
        let (envelope, payload) = client.invoke(self.handle, DISCOVER, &scratch.payload[..count],
            scratch.request, scratch.reply)?;
        let result = completed(envelope, payload, |bytes| Discovery::decode(bytes, query).map_err(CallError::Codec));
        retire(client, envelope.sequence, result, scratch)
    }

    /// Sends exactly one response during the active dispatch and acknowledges
    /// gateway completion. Acceptance remains provisional until dispatch/free
    /// return successfully. No helper retries an invocation or creates a client.
    #[cfg(all(target_arch = "wasm32", target_os = "none"))]
    pub fn respond(self, client: &mut Client, call: &Call<'_>, status: u32, payload: &[u8],
                   scratch: &mut Scratch<'_>) -> Result<(), CallError> {
        self.check_client(client)?;
        if call.generation != self.generation || call.service_handle != self.handle {
            return Err(CallError::Codec(CodecError::InvalidValue));
        }
        let count = encode_response(call.invocation, call.provider, status, payload, scratch.payload)
            .map_err(CallError::Codec)?;
        let (envelope, payload) = client.invoke(self.handle, RESPOND, &scratch.payload[..count],
            scratch.request, scratch.reply)?;
        let result = completed(envelope, payload, |bytes| if bytes.is_empty() { Ok(()) }
            else { Err(CallError::UnexpectedReply) });
        retire(client, envelope.sequence, result, scratch)
    }
}

#[cfg(all(target_arch = "wasm32", target_os = "none"))]
fn completed<T>(envelope: Envelope, payload: &[u8], decode: impl FnOnce(&[u8]) -> Result<T, CallError>)
    -> Result<T, CallError> {
    if envelope.service_status == SERVICE_OK { return decode(payload); }
    if envelope.service_status == SERVICE_RESULT_AVAILABLE || !payload.is_empty() {
        return Err(CallError::UnexpectedReply);
    }
    Err(CallError::Service(envelope.service_status))
}

#[cfg(all(target_arch = "wasm32", target_os = "none"))]
fn retire<T>(client: &mut Client, sequence: u64, result: Result<T, CallError>, scratch: &mut Scratch<'_>)
    -> Result<T, CallError> {
    if result.is_ok() || matches!(result, Err(CallError::Service(_))) {
        client.acknowledge(sequence, scratch.request, scratch.reply)?;
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    const TEST_SCHEMA: [u8; 32] = [1; 32];
    fn descriptor() -> Descriptor<'static> {
        Descriptor { name: "org.example.increment", major: 1, minor: 0, schema: &TEST_SCHEMA,
            maximum_request_bytes: 4, maximum_reply_bytes: 8 }
    }

    #[test]
    fn registration_has_canonical_required_fields_and_bounds() {
        let mut output = [0; 256];
        let count = encode_registration(descriptor(), &mut output).unwrap();
        let mut fields = Record::decode(&output[..count]).unwrap().fields();
        assert_eq!(fields.next().unwrap().utf8(), Ok("org.example.increment"));
        assert_eq!(fields.next().unwrap().u32(), Ok(1));
        assert_eq!(fields.next().unwrap().u32(), Ok(0));
        assert_eq!(fields.next().unwrap().bytes(), Ok(&TEST_SCHEMA[..]));
        assert_eq!(fields.next().unwrap().u32(), Ok(4));
        assert_eq!(fields.next().unwrap().u32(), Ok(8));
        assert_eq!(fields.next(), None);
        assert!(Record::decode(&output[..count]).unwrap().fields().all(|field| field.must_understand));
        for name in ["foundation.custom", "single", "org..bad", "Org.bad", "org.2bad", "org.bad."] {
            let mut invalid = descriptor(); invalid.name = name;
            let mut untouched = [0xa5; 256];
            assert_eq!(encode_registration(invalid, &mut untouched), Err(CodecError::InvalidValue));
            assert_eq!(untouched, [0xa5; 256]);
        }
        let mut invalid = descriptor(); invalid.maximum_reply_bytes = MAX_PAYLOAD_BYTES + 1;
        assert_eq!(encode_registration(invalid, &mut output), Err(CodecError::InvalidValue));
        invalid = descriptor(); invalid.schema = &[0; 32];
        assert_eq!(encode_registration(invalid, &mut output), Err(CodecError::InvalidValue));
        let mut short = [0xa5; 1];
        assert_eq!(encode_registration(descriptor(), &mut short), Err(CodecError::Truncated));
        assert_eq!(short, [0xa5]);
    }

    #[test]
    fn registration_reply_skips_optional_extensions_and_rejects_required_changes() {
        let token = 9u64.to_le_bytes();
        let mut output = [0; 64];
        let count = record::encode(&[Field::new(1, FIELD_U64 as u8, true, &token),
            Field::new(8, 200, false, &[3])], &mut output).unwrap();
        assert_eq!(decode_registration(&output[..count]), Ok(9));
        output[3] = 0;
        assert_eq!(decode_registration(&output[..count]), Err(CodecError::InvalidValue));
        output[3] = 1; output[19] = 1;
        assert_eq!(decode_registration(&output[..count]), Err(CodecError::UnknownRequiredField));
        assert_eq!(decode_registration(&[]), Err(CodecError::InvalidValue));
        output[..16].fill(0); output[..8].copy_from_slice(&[1, 0, 2, 1, 8, 0, 0, 0]);
        assert_eq!(decode_registration(&output[..16]), Err(CodecError::InvalidValue));
    }

    #[test]
    fn event_binds_service_generation_and_invocation_with_required_fields() {
        let provider = 7u64.to_le_bytes();
        let operation = 1u32.to_le_bytes();
        let mut record = [0; 64];
        let count = record::encode(&[Field::new(1, FIELD_U64 as u8, true, &provider),
            Field::new(2, FIELD_U32 as u8, true, &operation),
            Field::new(3, FIELD_BYTES as u8, true, &[0xff, 0, 0, 0])], &mut record).unwrap();
        let mut event = Envelope::request(5, 99, 6, EVENT_CALL);
        event.kind = MESSAGE_EVENT; event.correlation = 42;
        let mut input = [0; 128];
        let bytes = event.encode(&record[..count], &mut input).unwrap();
        let call = Call::decode(&input[..bytes], 5, 6).unwrap();
        assert_eq!((call.invocation, call.provider, call.operation), (42, 7, 1));
        assert_eq!(call.payload, &[0xff, 0, 0, 0]);
        assert_eq!(Call::decode(&input[..bytes], 4, 6), Err(CodecError::InvalidValue));
        assert_eq!(Call::decode(&input[..bytes], 5, 8), Err(CodecError::InvalidValue));
        event.correlation = 0;
        event.encode(&record[..count], &mut input).unwrap();
        assert_eq!(Call::decode(&input[..bytes], 5, 6), Err(CodecError::InvalidValue));
        event.correlation = 42; record[3] = 0;
        event.encode(&record[..count], &mut input).unwrap();
        assert_eq!(Call::decode(&input[..bytes], 5, 6), Err(CodecError::InvalidValue));
        event.kind = MESSAGE_REQUEST; event.correlation = 0;
        event.encode(&record[..count], &mut input).unwrap();
        assert_eq!(Call::decode(&input[..bytes], 5, 6), Err(CodecError::InvalidValue));
    }

    #[test]
    fn responses_include_empty_payload_and_reject_nonterminal_shapes() {
        let mut output = [0; 64];
        assert_eq!(encode_response(1, 2, SERVICE_UNKNOWN_OPERATION, &[], &mut output), Ok(52));
        assert_eq!(&output[44..52], &[4, 0, 7, 1, 0, 0, 0, 0]);
        let fields = Record::decode(&output[..52]).unwrap().fields();
        assert!(fields.into_iter().all(|field| field.must_understand));
        for (invocation, provider, status, payload) in [
            (0, 2, SERVICE_OK, &[][..]), (1, 0, SERVICE_OK, &[][..]),
            (1, 2, SERVICE_RESULT_AVAILABLE, &[][..]), (1, 2, SERVICE_UNCERTAIN + 1, &[][..]),
            (1, 2, SERVICE_INVALID_REQUEST, &[1][..]),
        ] {
            let mut untouched = [0xa5; 64];
            assert_eq!(encode_response(invocation, provider, status, payload, &mut untouched),
                Err(CodecError::InvalidValue));
            assert_eq!(untouched, [0xa5; 64]);
        }
    }

    #[test]
    fn provider_discovery_checks_exact_contract_and_required_presence() {
        let query = DiscoveryQuery { name: "org.example.increment", major: 1,
            minimum_minor: 0, maximum_minor: 2, schema: Some(&TEST_SCHEMA) };
        let token = 10u64.to_le_bytes();
        let one = 1u32.to_le_bytes();
        let request = 4u32.to_le_bytes();
        let reply = 8u32.to_le_bytes();
        let fields = [Field::new(1, FIELD_U64 as u8, true, &token),
            Field::new(2, FIELD_UTF8 as u8, true, query.name.as_bytes()),
            Field::new(3, FIELD_U32 as u8, true, &one),
            Field::new(4, FIELD_U32 as u8, true, &one),
            Field::new(5, FIELD_BYTES as u8, true, &TEST_SCHEMA),
            Field::new(6, FIELD_U32 as u8, true, &request),
            Field::new(7, FIELD_U32 as u8, true, &reply)];
        let mut output = [0; 256];
        let count = record::encode(&fields, &mut output).unwrap();
        assert_eq!(Discovery::decode(&output[..count], query), Ok(Discovery { handle: 10,
            major: 1, minor: 1, schema: TEST_SCHEMA, maximum_request_bytes: 4, maximum_reply_bytes: 8 }));
        let mut mismatch = query; mismatch.schema = Some(&[2; 32]);
        assert_eq!(Discovery::decode(&output[..count], mismatch), Err(CodecError::InvalidValue));
        assert_eq!(Discovery::decode(&output[..count - 12], query), Err(CodecError::InvalidValue));
        output[3] = 0;
        assert_eq!(Discovery::decode(&output[..count], query), Err(CodecError::InvalidValue));
    }
}
