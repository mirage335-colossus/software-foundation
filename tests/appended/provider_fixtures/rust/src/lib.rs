#![no_std]
#![deny(unsafe_op_in_unsafe_fn)]

//! Real provider guest for the shared `../contract.txt` language fixture.

use foundation_appended::{abi::*, bootstrap::{Client, Context, DiscoveryQuery}, providers::{Descriptor, Scratch, Service},
    borrow_input, CallError, CodecError};

// SHA256 of tests/appended/provider_fixtures/contract.txt, not the gateway schema.
const CONTRACT_SCHEMA: [u8; 32] = [
    0x3f, 0xe7, 0xab, 0x0d, 0x3f, 0x8f, 0x76, 0x49,
    0x9f, 0x05, 0x4c, 0xa6, 0xf2, 0x9f, 0x68, 0xde,
    0xee, 0x28, 0x62, 0x76, 0x81, 0xf7, 0x92, 0x31,
    0xaf, 0x3b, 0x09, 0x5b, 0x06, 0x35, 0xb2, 0x46,
];

struct Application {
    client: Client,
    service: Service,
    provider: u64,
    invocation_count: u32,
}

// The common runtime serializes every hook and rejects reentrant delivery.
static mut APPLICATION: Option<Application> = None;

fn initialize(input: &[u8]) -> Result<Application, CallError> {
    let context = Context::decode(input).map_err(CallError::Codec)?;
    let mut client = Client::new(context).map_err(CallError::Codec)?;
    let mut payload = [0; 256];
    let mut request = [0; 384];
    let mut reply = [0; 384];
    let mut scratch = Scratch { payload: &mut payload, request: &mut request, reply: &mut reply };
    let service = Service::discover(&mut client, &mut scratch)?;
    let provider = service.register(&mut client, Descriptor { name: "org.example.increment",
        major: 1, minor: 0, schema: &CONTRACT_SCHEMA, maximum_request_bytes: 4,
        maximum_reply_bytes: 8 }, &mut scratch)?;
    let discovered = service.find(&mut client, DiscoveryQuery { name: "org.example.increment",
        major: 1, minimum_minor: 0, maximum_minor: 0, schema: Some(&CONTRACT_SCHEMA) }, &mut scratch)?;
    if discovered.handle != provider || discovered.maximum_request_bytes != 4
        || discovered.maximum_reply_bytes != 8 {
        return Err(CallError::UnexpectedReply);
    }
    Ok(Application { client, service, provider, invocation_count: 0 })
}

fn dispatch(application: &mut Application, input: &[u8]) -> Result<(), CallError> {
    let call = application.service.decode_call(input).map_err(CallError::Codec)?;
    if call.provider != application.provider {
        return Err(CallError::Codec(CodecError::InvalidValue));
    }
    let mut result = [0; 8];
    let (status, result_bytes) = if call.operation != 1 {
        (SERVICE_UNKNOWN_OPERATION, 0)
    } else if call.payload.len() != 4 {
        (SERVICE_INVALID_REQUEST, 0)
    } else {
        let operand = u32::from_le_bytes([call.payload[0], call.payload[1], call.payload[2], call.payload[3]]);
        application.invocation_count = application.invocation_count.wrapping_add(1);
        result[..4].copy_from_slice(&operand.wrapping_add(1).to_le_bytes());
        result[4..].copy_from_slice(&application.invocation_count.to_le_bytes());
        (SERVICE_OK, 8)
    };
    let mut payload = [0; 64];
    let mut request = [0; 128];
    let mut reply = [0; 128];
    let mut scratch = Scratch { payload: &mut payload, request: &mut request, reply: &mut reply };
    application.service.respond(&mut application.client, &call, status, &result[..result_bytes], &mut scratch)
}

fn failure(error: CallError) -> u32 {
    match error {
        CallError::Codec(_) => APP_INVALID_INPUT,
        CallError::Exhausted => APP_EXHAUSTED,
        _ => APP_FAILED,
    }
}

/// # Safety
/// The common runtime lends one initialized allocation until this hook returns.
#[no_mangle]
pub unsafe extern "C" fn foundation_guest_initialize(input: *const u8, bytes: u32) -> u32 {
    // SAFETY: guaranteed by this hook's runtime allocation contract.
    let input = match unsafe { borrow_input(input, bytes) } {
        Ok(input) => input, Err(_) => return APP_INVALID_INPUT,
    };
    match initialize(input) {
        Ok(application) => {
            // SAFETY: one initialization attempt and one serialized owner.
            unsafe { core::ptr::addr_of_mut!(APPLICATION).write(Some(application)); }
            APP_OK
        },
        Err(error) => failure(error),
    }
}

/// # Safety
/// The runtime lends initialized input and serializes every application hook.
#[no_mangle]
pub unsafe extern "C" fn foundation_guest_dispatch(input: *const u8, bytes: u32) -> u32 {
    // SAFETY: guaranteed by this hook's runtime allocation contract.
    let input = match unsafe { borrow_input(input, bytes) } {
        Ok(input) => input, Err(_) => return APP_INVALID_INPUT,
    };
    // SAFETY: no other hook overlaps or retains this mutable application borrow.
    let application = unsafe { (&mut *core::ptr::addr_of_mut!(APPLICATION)).as_mut() };
    let Some(application) = application else { return APP_FAILED; };
    match dispatch(application, input) { Ok(()) => APP_OK, Err(error) => failure(error) }
}

#[no_mangle]
pub extern "C" fn foundation_guest_step(_budget_units: u32) -> u32 { STEP_IDLE }

/// # Safety
/// The runtime serializes shutdown after the final application borrow ends.
#[no_mangle]
pub unsafe extern "C" fn foundation_guest_shutdown(_reason: u32) {
    // SAFETY: shutdown cannot overlap another hook or leave application borrows.
    drop(unsafe { core::ptr::replace(core::ptr::addr_of_mut!(APPLICATION), None) });
}

#[panic_handler]
fn panic(_info: &core::panic::PanicInfo<'_>) -> ! { foundation_appended::abort() }
