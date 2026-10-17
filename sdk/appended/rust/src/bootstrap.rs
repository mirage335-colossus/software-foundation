//! Version-one bootstrap records. Wire IDs are defined by `abi/appended/v1/`.

use crate::{abi::*, record::{self, Field, Record}, CodecError, Envelope};
#[cfg(not(all(target_arch = "wasm32", target_os = "none")))]
use crate::Sequence;
#[cfg(all(target_arch = "wasm32", target_os = "none"))]
use crate::CallError;

/// SHA256 of the authoritative version-one bootstrap schema's exact bytes.
pub const BOOTSTRAP_SCHEMA: [u8; 32] = BOOTSTRAP_SCHEMA_BYTES;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Context {
    pub generation: u64,
    pub maximum_message_bytes: u32,
    pub bootstrap_schema: [u8; 32],
    pub maximum_retained_requests: u32,
    pub maximum_retained_results: u32,
    pub maximum_retained_bytes: u32,
}

impl Context {
    /// Copies the numeric context; no pointer into initialization input survives.
    pub fn decode(bytes: &[u8]) -> Result<Self, CodecError> {
        let record = Record::decode(bytes)?;
        let mut fields = record.fields();
        let mut take = |id| {
            let field = fields.next().ok_or(CodecError::InvalidValue)?;
            if field.id != id || !field.must_understand { return Err(CodecError::InvalidValue); }
            Ok(field)
        };
        let generation = take(1)?.u64()?;
        if take(2)?.u32()? != ABI_VERSION || take(3)?.u32()? != ENVELOPE_BYTES {
            return Err(CodecError::UnsupportedVersion);
        }
        let maximum_message_bytes = take(4)?.u32()?;
        let mut bootstrap_schema = [0; 32];
        let schema = take(5)?.bytes()?;
        if schema.len() != bootstrap_schema.len() { return Err(CodecError::InvalidValue); }
        bootstrap_schema.copy_from_slice(schema);
        let maximum_retained_requests = take(6)?.u32()?;
        let maximum_retained_results = take(7)?.u32()?;
        let maximum_retained_bytes = take(8)?.u32()?;
        for field in fields {
            if field.must_understand { return Err(CodecError::UnknownRequiredField); }
        }
        let context = Self { generation, maximum_message_bytes, bootstrap_schema,
            maximum_retained_requests, maximum_retained_results, maximum_retained_bytes };
        context.validate()?;
        Ok(context)
    }

    fn validate(self) -> Result<(), CodecError> {
        if self.generation == 0
            || !(ENVELOPE_BYTES..=MAX_MESSAGE_BYTES).contains(&self.maximum_message_bytes)
            || self.maximum_retained_requests < 2 || self.maximum_retained_results == 0
            || self.maximum_retained_bytes == 0 || self.bootstrap_schema != BOOTSTRAP_SCHEMA {
            return Err(CodecError::InvalidValue);
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug)]
pub struct DiscoveryQuery<'a> {
    pub name: &'a str,
    pub major: u32,
    pub minimum_minor: u32,
    pub maximum_minor: u32,
    pub schema: Option<&'a [u8; 32]>,
}

pub fn encode_discovery(query: DiscoveryQuery<'_>, output: &mut [u8]) -> Result<usize, CodecError> {
    if query.name.is_empty() || query.major == 0 || query.major > u16::MAX as u32
        || query.maximum_minor > u16::MAX as u32 || query.minimum_minor > query.maximum_minor {
        return Err(CodecError::InvalidValue);
    }
    let major = query.major.to_le_bytes();
    let low = query.minimum_minor.to_le_bytes();
    let high = query.maximum_minor.to_le_bytes();
    let mut fields = [
        Field::new(1, FIELD_UTF8 as u8, true, query.name.as_bytes()),
        Field::new(2, FIELD_U32 as u8, true, &major),
        Field::new(3, FIELD_U32 as u8, true, &low),
        Field::new(4, FIELD_U32 as u8, true, &high),
        Field::new(5, FIELD_BYTES as u8, true, &[]),
    ];
    let count = if let Some(schema) = query.schema { fields[4].value = schema; 5 } else { 4 };
    record::encode(&fields[..count], output)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Discovery {
    pub handle: u64,
    pub major: u32,
    pub minor: u32,
    pub schema: [u8; 32],
    pub maximum_reply_bytes: u32,
}

impl Discovery {
    /// Validates every required field and the negotiated contract.
    pub fn decode(bytes: &[u8], query: DiscoveryQuery<'_>) -> Result<Self, CodecError> {
        let record = Record::decode(bytes)?;
        let mut result = Self { handle: 0, major: 0, minor: 0, schema: [0; 32], maximum_reply_bytes: 0 };
        let mut present = 0u32;
        for field in record.fields() {
            if (1..=6).contains(&field.id) && !field.must_understand {
                return Err(CodecError::InvalidValue);
            }
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
                6 => result.maximum_reply_bytes = field.u32()?,
                _ => {
                    if field.must_understand { return Err(CodecError::UnknownRequiredField); }
                    continue;
                },
            }
            present |= 1 << (field.id - 1);
        }
        if present != 63 || (result.handle == 0 && query.name != BOOTSTRAP_NAME) || result.major != query.major
            || result.minor < query.minimum_minor || result.minor > query.maximum_minor
            || result.maximum_reply_bytes > MAX_MESSAGE_BYTES - ENVELOPE_BYTES
            || query.schema.is_some_and(|schema| *schema != result.schema) {
            return Err(CodecError::InvalidValue);
        }
        Ok(result)
    }
}

pub fn encode_result_read(handle: u64, offset: u32, count: u32, output: &mut [u8]) -> Result<usize, CodecError> {
    if handle == 0 { return Err(CodecError::InvalidValue); }
    let handle = handle.to_le_bytes();
    let offset = offset.to_le_bytes();
    let count = count.to_le_bytes();
    record::encode(&[Field::new(1, FIELD_U64 as u8, true, &handle),
        Field::new(2, FIELD_U32 as u8, true, &offset),
        Field::new(3, FIELD_U32 as u8, true, &count)], output)
}

pub fn encode_result_release(handle: u64, output: &mut [u8]) -> Result<usize, CodecError> {
    if handle == 0 { return Err(CodecError::InvalidValue); }
    let handle = handle.to_le_bytes();
    record::encode(&[Field::new(1, FIELD_U64 as u8, true, &handle)], output)
}

pub fn encode_acknowledge(through_sequence: u64, output: &mut [u8]) -> Result<usize, CodecError> {
    if through_sequence == 0 { return Err(CodecError::InvalidValue); }
    let through_sequence = through_sequence.to_le_bytes();
    record::encode(&[Field::new(1, FIELD_U64 as u8, true, &through_sequence)], output)
}

/// One serialized guest's context and nonwrapping outbound request sequence.
/// Input event sequences belong to their sender and must not drive this source.
pub struct Client {
    context: Context,
    #[cfg(not(all(target_arch = "wasm32", target_os = "none")))]
    sequence: Sequence,
    last_sequence: u64,
}

impl Client {
    pub fn new(context: Context) -> Result<Self, CodecError> {
        context.validate()?;
        Ok(Self { context,
            #[cfg(not(all(target_arch = "wasm32", target_os = "none")))]
            sequence: Sequence::new(),
            last_sequence: 0 })
    }
    pub fn context(&self) -> Context { self.context }
    pub fn last_sequence(&self) -> u64 { self.last_sequence }
    pub fn next_request(&mut self, handle: u64, operation: u32) -> Option<Envelope> {
        // C, C++ and every Rust Client share one runtime-owned sequence source.
        #[cfg(all(target_arch = "wasm32", target_os = "none"))]
        let sequence = unsafe { foundation_guest_next_sequence() };
        #[cfg(all(target_arch = "wasm32", target_os = "none"))]
        if sequence == 0 { return None; }
        #[cfg(not(all(target_arch = "wasm32", target_os = "none")))]
        let sequence = self.sequence.issue()?;
        self.last_sequence = sequence;
        Some(Envelope::request(self.context.generation, sequence, handle, operation))
    }

    /// Performs no automatic retry. Preserve canonical request bytes for an
    /// intentional retry of an admitted operation with the same sequence.
    #[cfg(all(target_arch = "wasm32", target_os = "none"))]
    pub fn invoke<'a>(&mut self, handle: u64, operation: u32, payload: &[u8],
                      request: &mut [u8], reply: &'a mut [u8]) -> Result<(Envelope, &'a [u8]), CallError> {
        if payload.len() > (self.context.maximum_message_bytes - ENVELOPE_BYTES) as usize {
            return Err(CallError::Codec(CodecError::LimitExceeded));
        }
        let envelope = self.next_request(handle, operation).ok_or(CallError::Exhausted)?;
        let count = envelope.encode(payload, request).map_err(CallError::Codec)?;
        let reply_capacity = reply.len().min(self.context.maximum_message_bytes as usize);
        crate::call(&request[..count], &mut reply[..reply_capacity])
    }

    /// Retires completed requests through `through_sequence`. The acknowledgement
    /// itself remains live until a later acknowledgement retires it.
    #[cfg(all(target_arch = "wasm32", target_os = "none"))]
    pub fn acknowledge(&mut self, through_sequence: u64, request: &mut [u8], reply: &mut [u8])
        -> Result<(), CallError> {
        if through_sequence == 0 || through_sequence > self.last_sequence {
            return Err(CallError::Codec(CodecError::InvalidValue));
        }
        let mut payload = [0; 16];
        let count = encode_acknowledge(through_sequence, &mut payload).map_err(CallError::Codec)?;
        let (envelope, payload) = self.invoke(BOOTSTRAP_HANDLE, CONTROL_ACKNOWLEDGE,
            &payload[..count], request, reply)?;
        if envelope.service_status != SERVICE_OK { return Err(CallError::Service(envelope.service_status)); }
        if !payload.is_empty() { return Err(CallError::UnexpectedReply); }
        Ok(())
    }
}

#[cfg(all(target_arch = "wasm32", target_os = "none"))]
extern "C" {
    fn foundation_guest_next_sequence() -> u64;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn discovery_golden_request() {
        let query = DiscoveryQuery { name: "x", major: 1, minimum_minor: 0, maximum_minor: 0, schema: None };
        let mut output = [0; 45];
        assert_eq!(encode_discovery(query, &mut output), Ok(45));
        assert_eq!(&output[..9], &[1, 0, 6, 1, 1, 0, 0, 0, b'x']);
        assert_eq!(&output[9..21], &[2, 0, 1, 1, 4, 0, 0, 0, 1, 0, 0, 0]);
        assert_eq!(&output[33..45], &[4, 0, 1, 1, 4, 0, 0, 0, 0, 0, 0, 0]);
    }

    #[test]
    fn discovery_reply_requires_flags_on_every_known_field() {
        let schema = [0x5a; 32];
        let query = DiscoveryQuery { name: "org.example.meter", major: 1,
            minimum_minor: 0, maximum_minor: 3, schema: Some(&schema) };
        let handle = 42u64.to_le_bytes();
        let major = 1u32.to_le_bytes();
        let minor = 2u32.to_le_bytes();
        let maximum_reply = 1024u32.to_le_bytes();
        let mut fields = [
            Field::new(1, FIELD_U64 as u8, true, &handle),
            Field::new(2, FIELD_UTF8 as u8, true, query.name.as_bytes()),
            Field::new(3, FIELD_U32 as u8, true, &major),
            Field::new(4, FIELD_U32 as u8, true, &minor),
            Field::new(5, FIELD_BYTES as u8, true, &schema),
            Field::new(6, FIELD_U32 as u8, true, &maximum_reply),
        ];
        let expected = Discovery { handle: 42, major: 1, minor: 2, schema, maximum_reply_bytes: 1024 };
        let mut output = [0; 256];
        let count = record::encode(&fields, &mut output).unwrap();
        assert_eq!(Discovery::decode(&output[..count], query), Ok(expected));
        for index in 0..fields.len() {
            fields[index].must_understand = false;
            let count = record::encode(&fields, &mut output).unwrap();
            assert_eq!(Discovery::decode(&output[..count], query), Err(CodecError::InvalidValue),
                       "discovery field {}", fields[index].id);
            fields[index].must_understand = true;
        }
        let extended = [fields[0], fields[1], fields[2], fields[3], fields[4], fields[5],
            Field::new(7, FIELD_BYTES as u8, false, &[])];
        let count = record::encode(&extended, &mut output).unwrap();
        assert_eq!(Discovery::decode(&output[..count], query), Ok(expected));
    }

    #[test]
    fn bootstrap_handle_and_bad_acknowledgement() {
        let mut output = [0xa5; 16];
        assert_eq!(encode_acknowledge(0, &mut output), Err(CodecError::InvalidValue));
        assert_eq!(output, [0xa5; 16]);
        assert_eq!(encode_result_release(9, &mut output), Ok(16));
        assert_eq!(output, [1, 0, 2, 1, 8, 0, 0, 0, 9, 0, 0, 0, 0, 0, 0, 0]);
    }
}
