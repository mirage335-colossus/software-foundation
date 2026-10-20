#![no_std]
#![deny(unsafe_op_in_unsafe_fn)]

//! Combined portable Rust calculator and `org.example.increment` provider.

use foundation_appended::{
    abi::*, borrow_input,
    bootstrap::{self, Client, Context, DiscoveryQuery, BOOTSTRAP_SCHEMA},
    providers::{self, Descriptor, Scratch as ProviderScratch},
    record::{Field, Record}, view,
    CallError, Envelope,
};

static mut GENERATION: u64 = 0;
const INCREMENT_SCHEMA: [u8; 32] = [
    0x3f,0xe7,0xab,0x0d,0x3f,0x8f,0x76,0x49,0x9f,0x05,0x4c,0xa6,0xf2,0x9f,0x68,0xde,
    0xee,0x28,0x62,0x76,0x81,0xf7,0x92,0x31,0xaf,0x3b,0x09,0x5b,0x06,0x35,0xb2,0x46,
];
const INITIAL: &[u8] = b"0";

static mut CLIENT: Option<Client> = None;
static mut VIEW_HANDLE: u64 = 0;
static mut PROVIDER_SERVICE: Option<providers::Service> = None;
static mut PROVIDER_TOKEN: u64 = 0;
static mut REVISION: u64 = 0;
static mut INVOCATIONS: u32 = 0;
static mut CLIENT_WIDTH: f64 = 400.0;
static mut CLIENT_HEIGHT: f64 = 240.0;
static mut DISPLAY_SCALE: f64 = 1.0;
static mut LHS: [u8; 11] = [b'0', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
static mut LHS_LEN: usize = 1;
static mut RHS: [u8; 11] = [b'0', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
static mut RHS_LEN: usize = 1;
static mut RESULT: [u8; 64] = [b'P',b'r',b'e',b's',b's',b' ',b'S',b'u',b'm',0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0];
static mut RESULT_LEN: usize = 9;

fn failure(error: CallError) -> u32 {
    match error {
        CallError::Codec(_) => APP_INVALID_INPUT,
        CallError::Exhausted => APP_EXHAUSTED,
        _ => APP_FAILED,
    }
}

fn ack(client: &mut Client, sequence: u64) -> Result<(), CallError> {
    let mut request = [0; 1024];
    let mut reply = [0; 1024];
    client.acknowledge(sequence, &mut request, &mut reply)
}

fn invoke_view(client: &mut Client, handle: u64, payload: &[u8]) -> Result<(), CallError> {
    let mut request = [0; 8192];
    let mut reply = [0; 1024];
    let (envelope, accepted) = client.invoke(handle, view::REPLACE, payload, &mut request, &mut reply)?;
    if envelope.service_status != SERVICE_OK { return Err(CallError::Service(envelope.service_status)); }
    let record = Record::decode(accepted).map_err(CallError::Codec)?;
    let mut fields = record.fields();
    let field = fields.next().ok_or(CallError::UnexpectedReply)?;
    if field.id != 1 { return Err(CallError::UnexpectedReply); }
    let revision = field.u64().map_err(CallError::Codec)?;
    if fields.next().is_some() { return Err(CallError::UnexpectedReply); }
    // The host accepts exactly the next full snapshot revision.
    let expected = unsafe { REVISION.checked_add(1).ok_or(CallError::Exhausted)? };
    if revision != expected { return Err(CallError::UnexpectedReply); }
    unsafe { REVISION = revision; }
    ack(client, envelope.sequence)
}

fn publish(client: &mut Client, handle: u64) -> Result<(), CallError> {
    let (lhs, lhs_len, rhs, rhs_len, result, result_len, revision, width, height, scale) = unsafe {
        (LHS, LHS_LEN, RHS, RHS_LEN, RESULT, RESULT_LEN, REVISION, CLIENT_WIDTH, CLIENT_HEIGHT, DISPLAY_SCALE)
    };
    let mut widgets_bytes = [0; 4096];
    let mut widgets = view::ListBuilder::new(&mut widgets_bytes);
    add_widget(&mut widgets, "lhs", view::TEXT, 20.0, &lhs[..lhs_len], "Left operand")
        .map_err(CallError::Codec)?;
    add_widget(&mut widgets, "rhs", view::TEXT, 70.0, &rhs[..rhs_len], "Right operand")
        .map_err(CallError::Codec)?;
    add_widget(&mut widgets, "sum", view::BUTTON, 120.0, b"", "Sum").map_err(CallError::Codec)?;
    add_widget(&mut widgets, "result", view::LABEL, 170.0, &result[..result_len], "Result")
        .map_err(CallError::Codec)?;
    let widgets_len = widgets.finish().map_err(CallError::Codec)?;
    let mut payload = [0; 8192];
    let mut snapshot = view::Builder::new(&mut payload);
    snapshot.u64(1, revision).text(2, "Portable calculator")
        .number(3, width).number(4, height).number(5, scale)
        .list(6, &widgets_bytes[..widgets_len]);
    let payload_len = snapshot.finish().map_err(CallError::Codec)?;
    invoke_view(client, handle, &payload[..payload_len])
}

fn add_widget(list: &mut view::ListBuilder<'_>, id: &str, kind: u32, y: f64,
              value: &[u8], label: &str) -> Result<(), foundation_appended::CodecError> {
    let mut rect = [0; 64];
    let rect_len = view::rect(&mut rect, 20.0, y, 360.0, 32.0)?;
    let mut widget = [0; 512];
    let mut record = view::Builder::new(&mut widget);
    record.text(1, id).u64(2, 1).u32(3, kind).record(4, &rect[..rect_len])
        .text(7, core::str::from_utf8(value).map_err(|_| foundation_appended::CodecError::InvalidValue)?)
        .text(8, label);
    if kind == view::TEXT { record.u32(18, 10).u32(19, 2); }
    let length = record.finish()?;
    list.append(&widget[..length]);
    Ok(())
}

fn parse_decimal(value: &[u8]) -> Option<u32> {
    if value.is_empty() || value.len() > 10 { return None; }
    let mut number = 0u32;
    for byte in value {
        if !byte.is_ascii_digit() { return None; }
        number = number.checked_mul(10)?.checked_add((byte - b'0') as u32)?;
    }
    Some(number)
}

fn calculate() {
    let (lhs, lhs_len, rhs, rhs_len) = unsafe { (LHS, LHS_LEN, RHS, RHS_LEN) };
    let (sum, error): (Option<u32>, &[u8]) = match (parse_decimal(&lhs[..lhs_len]), parse_decimal(&rhs[..rhs_len])) {
        (Some(a), Some(b)) => (a.checked_add(b), b"Overflow"),
        _ => (None, b"Enter whole numbers from 0 to 4294967295"),
    };
    unsafe {
        if let Some(mut value) = sum {
            let mut reverse = [0; 10]; let mut length = 0;
            loop { reverse[length] = b'0' + (value % 10) as u8; length += 1; value /= 10; if value == 0 { break; } }
            for index in 0..length { RESULT[index] = reverse[length - index - 1]; }
            RESULT_LEN = length;
        } else {
            RESULT[..error.len()].copy_from_slice(error);
            RESULT_LEN = error.len();
        }
    }
}

fn initialize(context_bytes: &[u8]) -> Result<(), CallError> {
    let context = Context::decode(context_bytes).map_err(CallError::Codec)?;
    if context.bootstrap_schema != BOOTSTRAP_SCHEMA {
        return Err(CallError::Codec(foundation_appended::CodecError::InvalidValue));
    }
    let mut client = Client::new(context).map_err(CallError::Codec)?;
    let mut payload = [0; 1024];
    let mut request = [0; 2048];
    let mut reply = [0; 2048];
    let view_query = DiscoveryQuery { name: view::SERVICE_NAME, major: view::MAJOR,
        minimum_minor: view::MINOR, maximum_minor: view::MINOR, schema: Some(&view::SCHEMA) };
    let count = bootstrap::encode_discovery(view_query, &mut payload).map_err(CallError::Codec)?;
    let (found, bytes) = client.invoke(BOOTSTRAP_HANDLE, CONTROL_DISCOVER,
        &payload[..count], &mut request, &mut reply)?;
    if found.service_status != SERVICE_OK { return Err(CallError::Service(found.service_status)); }
    let view_service = bootstrap::Discovery::decode(bytes, view_query).map_err(CallError::Codec)?;
    if view_service.handle == 0 { return Err(CallError::UnexpectedReply); }
    ack(&mut client, found.sequence)?;

    let mut provider_scratch = ProviderScratch { payload: &mut payload, request: &mut request, reply: &mut reply };
    // Optional absence is returned only after its discovery ACK succeeds.
    let provider_service = providers::Service::discover_optional(&mut client, &mut provider_scratch)?;
    let provider_token = if let Some(service) = provider_service {
        let token = service.register(&mut client, Descriptor {
            name: "org.example.increment", major: 1, minor: 0, schema: &INCREMENT_SCHEMA,
            maximum_request_bytes: 4, maximum_reply_bytes: 8,
        }, &mut provider_scratch)?;
        if token == 0 || service.handle() == view_service.handle {
            return Err(CallError::UnexpectedReply);
        }
        token
    } else { 0 };
    unsafe {
        GENERATION = context.generation;
        VIEW_HANDLE = view_service.handle;
        PROVIDER_SERVICE = provider_service;
        PROVIDER_TOKEN = provider_token;
        CLIENT = Some(client);
    }
    let client = unsafe { CLIENT.as_mut().ok_or(CallError::UnexpectedReply)? };
    publish(client, view_service.handle)
}

fn dispatch(input: &[u8]) -> Result<(), CallError> {
    let (envelope, payload) = Envelope::decode(input).map_err(CallError::Codec)?;
    if envelope.kind != MESSAGE_EVENT || envelope.generation != unsafe { GENERATION } {
        return Err(CallError::Codec(foundation_appended::CodecError::InvalidValue));
    }
    if envelope.interface_handle == unsafe { PROVIDER_SERVICE.map_or(0, |s| s.handle()) } {
        let service = unsafe { PROVIDER_SERVICE.ok_or(CallError::UnexpectedReply)? };
        let call = service.decode_call(input).map_err(CallError::Codec)?;
        if call.provider != unsafe { PROVIDER_TOKEN } { return Err(CallError::Codec(foundation_appended::CodecError::InvalidValue)); }
        let mut result = [0; 8];
        let (status, length) = if call.operation != 1 {
            (SERVICE_UNKNOWN_OPERATION, 0)
        } else if call.payload.len() != 4 {
            (SERVICE_INVALID_REQUEST, 0)
        } else {
            let operand = u32::from_le_bytes(call.payload.try_into().map_err(|_| CallError::UnexpectedReply)?);
            let count = unsafe { INVOCATIONS.wrapping_add(1) };
            unsafe { INVOCATIONS = count; }
            result[..4].copy_from_slice(&operand.wrapping_add(1).to_le_bytes());
            result[4..].copy_from_slice(&count.to_le_bytes());
            (SERVICE_OK, 8)
        };
        let client = unsafe { CLIENT.as_mut().ok_or(CallError::UnexpectedReply)? };
        let mut payload = [0; 128]; let mut request = [0; 1024]; let mut reply = [0; 1024];
        service.respond(client, &call, status, &result[..length],
            &mut ProviderScratch { payload: &mut payload, request: &mut request, reply: &mut reply })?;
        return Ok(());
    }
    if envelope.interface_handle != unsafe { VIEW_HANDLE } || envelope.operation != 1 {
        return Err(CallError::Codec(foundation_appended::CodecError::InvalidValue));
    }
    let fields = Record::decode(payload).map_err(CallError::Codec)?;
    let mut revision = None; let mut kind = None; let mut target = None;
    let mut input_kind = None; let mut value = None; let mut base = None;
    let (mut width, mut height, mut scale) = unsafe { (CLIENT_WIDTH, CLIENT_HEIGHT, DISPLAY_SCALE) };
    for field in fields.fields() {
        match field.id {
            1 => revision = Some(field.u64().map_err(CallError::Codec)?),
            2 => kind = Some(field.u32().map_err(CallError::Codec)?),
            3 => {
                if field.field_type as u32 != FIELD_RECORD {
                    return Err(CallError::Codec(foundation_appended::CodecError::InvalidValue));
                }
                target = Some(field);
            },
            4 => input_kind = Some(field.u32().map_err(CallError::Codec)?),
            5 => value = Some(field.utf8().map_err(CallError::Codec)?.as_bytes()),
            6 => base = Some(field.utf8().map_err(CallError::Codec)?.as_bytes()),
            11..=13 => {
                if field.field_type as u32 != FIELD_F64 || field.value.len() != 8 {
                    return Err(CallError::Codec(foundation_appended::CodecError::InvalidValue));
                }
                let number = f64::from_le_bytes(field.value.try_into().map_err(|_| CallError::UnexpectedReply)?);
                if !number.is_finite() { return Err(CallError::Codec(foundation_appended::CodecError::InvalidValue)); }
                match field.id { 11 => width = number, 12 => height = number, _ => scale = number }
            },
            _ if field.must_understand => return Err(CallError::Codec(foundation_appended::CodecError::UnknownRequiredField)),
            _ => {},
        }
    }
    if revision != Some(unsafe { REVISION }) { return Err(CallError::Codec(foundation_appended::CodecError::InvalidValue)); }
    if kind == Some(3) {
        unsafe { CLIENT_WIDTH = width; CLIENT_HEIGHT = height; DISPLAY_SCALE = scale; }
        let client = unsafe { CLIENT.as_mut().ok_or(CallError::UnexpectedReply)? };
        return publish(client, unsafe { VIEW_HANDLE });
    }
    match (kind, input_kind) {
        (Some(1), Some(3)) => {
            let target = target.ok_or(CallError::UnexpectedReply)?;
            let id = target_record_id(target.value).map_err(CallError::Codec)?;
            let value = value.ok_or(CallError::UnexpectedReply)?;
            let base = base.ok_or(CallError::UnexpectedReply)?;
            if value.len() > 10 { return Err(CallError::Codec(foundation_appended::CodecError::InvalidValue)); }
            unsafe {
                let (buffer, length) = match id {
                    b"lhs" => (&mut LHS, &mut LHS_LEN),
                    b"rhs" => (&mut RHS, &mut RHS_LEN),
                    _ => return Err(CallError::Codec(foundation_appended::CodecError::InvalidValue)),
                };
                if &buffer[..*length] != base { return Err(CallError::Codec(foundation_appended::CodecError::InvalidValue)); }
                buffer[..value.len()].copy_from_slice(value);
                *length = value.len();
            }
        },
        (Some(1), Some(1)) if target.is_some_and(|t| target_record_id(t.value).ok() == Some(&b"sum"[..])) => calculate(),
        (Some(1), Some(7)) if target.is_some_and(|t| target_record_id(t.value).ok().is_some_and(|id| id == b"lhs" || id == b"rhs")) => calculate(),
        _ => return Err(CallError::Codec(foundation_appended::CodecError::InvalidValue)),
    }
    let client = unsafe { CLIENT.as_mut().ok_or(CallError::UnexpectedReply)? };
    publish(client, unsafe { VIEW_HANDLE })
}

fn target_record_id(bytes: &[u8]) -> Result<&[u8], foundation_appended::CodecError> {
    let record = Record::decode(bytes)?;
    let mut fields = record.fields();
    let id = fields.next().ok_or(foundation_appended::CodecError::InvalidValue)?;
    if id.id != 1 || fields.next().is_none_or(|g| g.id != 2 || g.u64().ok() != Some(1))
        || fields.next().is_some() { return Err(foundation_appended::CodecError::InvalidValue); }
    Ok(id.utf8()?.as_bytes())
}

#[no_mangle]
pub unsafe extern "C" fn foundation_guest_initialize(input: *const u8, bytes: u32) -> u32 {
    // SAFETY: common runtime owns the live allocation for this serialized hook.
    let input = match unsafe { borrow_input(input, bytes) } { Ok(v) => v, Err(_) => return APP_INVALID_INPUT };
    match initialize(input) { Ok(()) => APP_OK, Err(error) => failure(error) }
}

#[no_mangle]
pub unsafe extern "C" fn foundation_guest_dispatch(input: *const u8, bytes: u32) -> u32 {
    // SAFETY: common runtime owns the live allocation for this serialized hook.
    let input = match unsafe { borrow_input(input, bytes) } { Ok(v) => v, Err(_) => return APP_INVALID_INPUT };
    match dispatch(input) { Ok(()) => APP_OK, Err(error) => failure(error) }
}

#[no_mangle]
pub extern "C" fn foundation_guest_step(_budget_units: u32) -> u32 { STEP_IDLE }

#[no_mangle]
pub unsafe extern "C" fn foundation_guest_shutdown(_reason: u32) {
    unsafe { CLIENT = None; PROVIDER_SERVICE = None; VIEW_HANDLE = 0; PROVIDER_TOKEN = 0; REVISION = 0; GENERATION = 0; }
}

#[panic_handler]
fn panic(_info: &core::panic::PanicInfo<'_>) -> ! { foundation_appended::abort() }

// Keep the fixture's initial state explicit in source and host goldens.
const _: &[u8] = INITIAL;
