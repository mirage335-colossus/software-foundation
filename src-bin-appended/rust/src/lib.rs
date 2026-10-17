#![no_std]
#![deny(unsafe_op_in_unsafe_fn)]

//! Checked-u32 calculator with results sent through the diagnostics service.

use foundation_appended::{abi::*, bootstrap::{self, Client, Context, Discovery, DiscoveryQuery},
    record::{self, Field, Record}, borrow_input, CallError, CodecError, Envelope};

struct Application {
    client: Client,
    diagnostics: u64,
}

// The runtime admits one serialized invocation and forbids reentrant delivery.
// This contains owned scalars only; no initialization/message borrow survives.
static mut APPLICATION: Option<Application> = None;

fn initialize(input: &[u8]) -> Result<Application, CallError> {
    let context = Context::decode(input).map_err(CallError::Codec)?;
    let mut client = Client::new(context).map_err(CallError::Codec)?;
    let query = DiscoveryQuery { name: "foundation.diagnostics", major: 1,
        minimum_minor: 0, maximum_minor: 0, schema: None };
    let mut payload = [0; 128];
    let count = bootstrap::encode_discovery(query, &mut payload).map_err(CallError::Codec)?;
    let mut request = [0; 512];
    let mut reply = [0; 512];
    let (envelope, payload) = client.invoke(BOOTSTRAP_HANDLE, CONTROL_DISCOVER,
        &payload[..count], &mut request, &mut reply)?;
    if envelope.service_status != SERVICE_OK { return Err(CallError::Service(envelope.service_status)); }
    let diagnostics = Discovery::decode(payload, query).map_err(CallError::Codec)?.handle;
    client.acknowledge(envelope.sequence, &mut request, &mut reply)?;
    Ok(Application { client, diagnostics })
}

fn dispatch(application: &mut Application, input: &[u8]) -> Result<(), CallError> {
    let (envelope, payload) = Envelope::decode(input).map_err(CallError::Codec)?;
    if !matches!(envelope.kind, MESSAGE_REQUEST | MESSAGE_EVENT)
        || envelope.generation != application.client.context().generation
        || envelope.operation != 1 {
        return Err(CallError::Codec(CodecError::InvalidValue));
    }
    let record = Record::decode(payload).map_err(CallError::Codec)?;
    let mut lhs = None;
    let mut rhs = None;
    for field in record.fields() {
        match field.id {
            1 => lhs = Some(field.u32().map_err(CallError::Codec)?),
            2 => rhs = Some(field.u32().map_err(CallError::Codec)?),
            _ if field.must_understand => return Err(CallError::Codec(CodecError::UnknownRequiredField)),
            _ => {},
        }
    }
    let sum = lhs.ok_or(CallError::Codec(CodecError::InvalidValue))?
        .checked_add(rhs.ok_or(CallError::Codec(CodecError::InvalidValue))?);
    let value = sum.unwrap_or(0).to_le_bytes();
    let overflow = [u8::from(sum.is_none())];
    let mut result = [0; 21];
    let count = record::encode(&[
        Field::new(1, FIELD_U32 as u8, true, &value),
        Field::new(2, FIELD_BOOL as u8, true, &overflow),
    ], &mut result).map_err(CallError::Codec)?;
    let mut request = [0; 512];
    let mut reply = [0; 512];
    let (envelope, echoed) = application.client.invoke(application.diagnostics, 1,
        &result[..count], &mut request, &mut reply)?;
    if envelope.service_status != SERVICE_OK { return Err(CallError::Service(envelope.service_status)); }
    if echoed != &result[..count] { return Err(CallError::UnexpectedReply); }
    application.client.acknowledge(envelope.sequence, &mut request, &mut reply)
}

fn failure(error: CallError) -> u32 {
    match error {
        CallError::Codec(_) => APP_INVALID_INPUT,
        CallError::Exhausted => APP_EXHAUSTED,
        _ => APP_FAILED,
    }
}

/// # Safety
/// The runtime provides one initialized allocation borrowed until this returns.
/// It invokes this hook once, after binding context and running constructors.
#[no_mangle]
pub unsafe extern "C" fn foundation_guest_initialize(input: *const u8, bytes: u32) -> u32 {
    // SAFETY: the runtime guarantees the documented allocation and lifetime.
    let input = match unsafe { borrow_input(input, bytes) } {
        Ok(input) => input, Err(_) => return APP_INVALID_INPUT,
    };
    match initialize(input) {
        Ok(application) => {
            // SAFETY: this instance has one initialization attempt and one owner.
            unsafe { core::ptr::addr_of_mut!(APPLICATION).write(Some(application)); }
            APP_OK
        },
        Err(error) => failure(error),
    }
}

/// # Safety
/// The runtime lends initialized input for this call and serializes all hooks.
#[no_mangle]
pub unsafe extern "C" fn foundation_guest_dispatch(input: *const u8, bytes: u32) -> u32 {
    // SAFETY: the runtime guarantees the documented allocation and lifetime.
    let input = match unsafe { borrow_input(input, bytes) } {
        Ok(input) => input, Err(_) => return APP_INVALID_INPUT,
    };
    // SAFETY: no hook overlaps this invocation or retains an application borrow.
    let application = unsafe { (&mut *core::ptr::addr_of_mut!(APPLICATION)).as_mut() };
    let Some(application) = application else { return APP_FAILED; };
    match dispatch(application, input) { Ok(()) => APP_OK, Err(error) => failure(error) }
}

#[no_mangle]
pub extern "C" fn foundation_guest_step(_budget_units: u32) -> u32 { STEP_IDLE }

/// # Safety
/// The runtime serializes this hook after the last active application borrow.
#[no_mangle]
pub unsafe extern "C" fn foundation_guest_shutdown(_reason: u32) {
    // SAFETY: the runtime serializes shutdown after the final active invocation.
    drop(unsafe { core::ptr::replace(core::ptr::addr_of_mut!(APPLICATION), None) });
}

#[panic_handler]
fn panic(_info: &core::panic::PanicInfo<'_>) -> ! {
    foundation_appended::abort()
}
