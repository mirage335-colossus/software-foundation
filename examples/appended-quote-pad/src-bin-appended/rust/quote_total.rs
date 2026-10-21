#![no_std]
#![deny(unsafe_op_in_unsafe_fn)]

use foundation_appended::{
    abi::*,
    bootstrap::{Client, Context},
    providers::{Descriptor, Scratch, Service},
    borrow_input, CallError,
};

const QUOTE_ADJUSTMENT: u32 = 1;
const PROVIDER_SCHEMA: [u8; 32] = [
    0xba,0xa7,0xae,0x88,0xe0,0x6a,0x98,0x59,
    0x99,0x0d,0x80,0xf9,0x9f,0x23,0x86,0xe0,
    0x19,0xde,0x22,0x3c,0x9b,0xb8,0xe5,0xa8,
    0x9f,0x4d,0x8f,0xd0,0xab,0x45,0x65,0x3f,
];

struct Application {
    client: Client,
    service: Service,
    provider: u64,
    invocation_count: u32,
}

// The common guest runtime serializes all lifecycle and dispatch hooks.
static mut APPLICATION: Option<Application> = None;

fn initialize(input: &[u8]) -> Result<Application, u32> {
    let context = Context::decode(input).map_err(|_| APP_INVALID_INPUT)?;
    let mut client = Client::new(context).map_err(|_| APP_INVALID_INPUT)?;
    let mut payload = [0; 256];
    let mut request = [0; 384];
    let mut reply = [0; 384];
    let mut scratch = Scratch { payload: &mut payload, request: &mut request, reply: &mut reply };

    let service = Service::discover(&mut client, &mut scratch).map_err(service_failure)?;
    let provider = service.register(&mut client, Descriptor {
        name: "org.example.quote.total",
        major: 1,
        minor: 0,
        schema: &PROVIDER_SCHEMA,
        maximum_request_bytes: 8,
        maximum_reply_bytes: 12,
    }, &mut scratch).map_err(service_failure)?;
    Ok(Application { client, service, provider, invocation_count: 0 })
}

fn dispatch(application: &mut Application, input: &[u8]) -> Result<(), u32> {
    let call = application.service.decode_call(input).map_err(|_| APP_INVALID_INPUT)?;
    if call.provider != application.provider {
        return Err(APP_INVALID_INPUT);
    }

    let mut result = [0; 12];
    let (status, result_bytes) = if call.operation != 1 {
        (SERVICE_UNKNOWN_OPERATION, 0)
    } else if call.payload.len() != 8 {
        (SERVICE_INVALID_REQUEST, 0)
    } else {
        let left = u32::from_le_bytes([call.payload[0], call.payload[1], call.payload[2], call.payload[3]]);
        let right = u32::from_le_bytes([call.payload[4], call.payload[5], call.payload[6], call.payload[7]]);
        let mut total = 0;
        let mut overflow = left > u32::MAX - right;
        if !overflow {
            total = left + right;
            overflow = total > u32::MAX - QUOTE_ADJUSTMENT;
            if !overflow { total += QUOTE_ADJUSTMENT; }
        }
        if overflow { total = 0; }

        application.invocation_count = application.invocation_count.wrapping_add(1);
        result[..4].copy_from_slice(&total.to_le_bytes());
        result[4..8].copy_from_slice(&(overflow as u32).to_le_bytes());
        result[8..].copy_from_slice(&application.invocation_count.to_le_bytes());
        (SERVICE_OK, result.len())
    };

    let mut payload = [0; 64];
    let mut request = [0; 128];
    let mut reply = [0; 128];
    let mut scratch = Scratch { payload: &mut payload, request: &mut request, reply: &mut reply };
    application.service.respond(&mut application.client, &call, status,
        &result[..result_bytes], &mut scratch).map_err(service_failure)
}

// Invalid caller bytes are classified where they are decoded. A malformed
// gateway reply, including a registration with a zero handle, is a failure.
fn service_failure(error: CallError) -> u32 {
    match error {
        CallError::Exhausted => APP_EXHAUSTED,
        _ => APP_FAILED,
    }
}

/// # Safety
/// The runtime lends an initialized guest allocation until this hook returns.
#[no_mangle]
pub unsafe extern "C" fn foundation_guest_initialize(input: *const u8, bytes: u32) -> u32 {
    // SAFETY: the common runtime guarantees the pointer and length pair.
    let input = match unsafe { borrow_input(input, bytes) } {
        Ok(input) => input,
        Err(_) => return APP_INVALID_INPUT,
    };
    match initialize(input) {
        Ok(application) => {
            // SAFETY: initialization is serialized and can only succeed once.
            unsafe { core::ptr::addr_of_mut!(APPLICATION).write(Some(application)); }
            APP_OK
        }
        Err(status) => status,
    }
}

/// # Safety
/// The runtime lends initialized input and serializes application hooks.
#[no_mangle]
pub unsafe extern "C" fn foundation_guest_dispatch(input: *const u8, bytes: u32) -> u32 {
    // SAFETY: the common runtime guarantees the pointer and length pair.
    let input = match unsafe { borrow_input(input, bytes) } {
        Ok(input) => input,
        Err(_) => return APP_INVALID_INPUT,
    };
    // SAFETY: no other hook overlaps this serialized mutable application borrow.
    let application = unsafe { (&mut *core::ptr::addr_of_mut!(APPLICATION)).as_mut() };
    let Some(application) = application else { return APP_FAILED; };
    match dispatch(application, input) {
        Ok(()) => APP_OK,
        Err(status) => status,
    }
}

#[no_mangle]
pub extern "C" fn foundation_guest_step(_budget_units: u32) -> u32 { STEP_IDLE }

/// # Safety
/// The runtime serializes shutdown after all application borrows have ended.
#[no_mangle]
pub unsafe extern "C" fn foundation_guest_shutdown(_reason: u32) {
    // SAFETY: shutdown cannot overlap another hook or leave application borrows.
    drop(unsafe { core::ptr::replace(core::ptr::addr_of_mut!(APPLICATION), None) });
}

#[panic_handler]
fn panic(_info: &core::panic::PanicInfo<'_>) -> ! { foundation_appended::abort() }
