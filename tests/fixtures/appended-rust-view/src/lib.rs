#![no_std]
#![deny(unsafe_op_in_unsafe_fn)]

//! Freestanding integration fixture for the public Rust foundation.view v1 builder.

use foundation_appended::{
    abi::*,
    borrow_input,
    bootstrap::{Client, Context, BOOTSTRAP_SCHEMA},
    record::Record,
    view::{Builder as RecordBuilder, ListBuilder},
    view,
    CallError,
};

const VIEW_HANDLE: u64 = 7;
const VIEW_OPERATION: u32 = view::REPLACE;
const WIDGET_GENERATION: u64 = 9_007_199_254_740_997;

static mut INITIALIZED: bool = false;

fn fixture() -> Result<(), CallError> {
    check_public_builder_vectors()?;

    let mut rect_bytes = [0; 64];
    let rect_len = view::rect(&mut rect_bytes, 0.10000000000000002, -2.5, 320.25, 48.5)
        .map_err(CallError::Codec)?;
    let mut widget_bytes = [0; 128];
    let widget_len = view::widget(
        &mut widget_bytes,
        "tile",
        WIDGET_GENERATION,
        view::BUTTON,
        &rect_bytes[..rect_len],
    )
    .map_err(CallError::Codec)?;
    let mut widgets_bytes = [0; 160];
    let mut widgets = ListBuilder::new(&mut widgets_bytes);
    widgets.append(&widget_bytes[..widget_len]);
    let widgets_len = widgets.finish().map_err(CallError::Codec)?;

    let mut payload = [0; 512];
    let mut replace = RecordBuilder::new(&mut payload);
    replace
        .u64(1, 0)
        .text(2, "Rust view fixture")
        .number(3, 400.5)
        .number(4, 240.25)
        .number(5, 1.25)
        .list(6, &widgets_bytes[..widgets_len]);
    let payload_len = replace.finish().map_err(CallError::Codec)?;

    let context = Context {
        generation: WIDGET_GENERATION,
        maximum_message_bytes: MAX_MESSAGE_BYTES,
        bootstrap_schema: BOOTSTRAP_SCHEMA,
        maximum_retained_requests: 8,
        maximum_retained_results: 4,
        maximum_retained_bytes: 4096,
    };
    let mut client = Client::new(context).map_err(CallError::Codec)?;
    let mut request = [0; 1024];
    let mut reply = [0; 256];
    let (envelope, accepted) = client.invoke(
        VIEW_HANDLE,
        VIEW_OPERATION,
        &payload[..payload_len],
        &mut request,
        &mut reply,
    )?;
    if envelope.service_status != SERVICE_OK {
        return Err(CallError::Service(envelope.service_status));
    }
    let accepted = Record::decode(accepted).map_err(CallError::Codec)?;
    let mut fields = accepted.fields();
    let revision = fields
        .next()
        .ok_or(CallError::UnexpectedReply)?
        .u64()
        .map_err(CallError::Codec)?;
    if revision != 1 || fields.next().is_some() {
        return Err(CallError::UnexpectedReply);
    }
    Ok(())
}

fn check_public_builder_vectors() -> Result<(), CallError> {
    // A record that is seven levels deep becomes the allowed eighth level
    // when used as a record field or a record-list entry.
    let mut depth_seven = [0; 256];
    let depth_seven_len = nested_record(7, &mut depth_seven).map_err(CallError::Codec)?;
    let mut wrapped = [0; 512];
    let mut record_wrapper = RecordBuilder::new(&mut wrapped);
    record_wrapper.record(1, &depth_seven[..depth_seven_len]);
    record_wrapper.finish().map_err(CallError::Codec)?;

    let mut child_list_bytes = [0; 320];
    let mut child_list = ListBuilder::new(&mut child_list_bytes);
    child_list.append(&depth_seven[..depth_seven_len]);
    let child_list_len = child_list.finish().map_err(CallError::Codec)?;
    let mut list_wrapper = [0; 384];
    let mut list_record = RecordBuilder::new(&mut list_wrapper);
    list_record.list(1, &child_list_bytes[..child_list_len]);
    list_record.finish().map_err(CallError::Codec)?;

    // A depth-eight child would become depth nine through either wrapper.
    let mut depth_eight = [0; 320];
    let depth_eight_len = nested_record(8, &mut depth_eight).map_err(CallError::Codec)?;
    let mut rejected_record = [0; 384];
    let mut record_wrapper = RecordBuilder::new(&mut rejected_record);
    record_wrapper.record(1, &depth_eight[..depth_eight_len]);
    if record_wrapper.finish() != Err(foundation_appended::CodecError::LimitExceeded) {
        return Err(CallError::UnexpectedReply);
    }

    let mut deep_list_bytes = [0; 384];
    let mut deep_list = ListBuilder::new(&mut deep_list_bytes);
    deep_list.append(&depth_eight[..depth_eight_len]);
    let deep_list_len = deep_list.finish().map_err(CallError::Codec)?;
    let mut rejected_list = [0; 448];
    let mut list_wrapper = RecordBuilder::new(&mut rejected_list);
    list_wrapper.list(1, &deep_list_bytes[..deep_list_len]);
    if list_wrapper.finish() != Err(foundation_appended::CodecError::LimitExceeded) {
        return Err(CallError::UnexpectedReply);
    }

    let mut short = [0; 15];
    if view::rect(&mut short, 1.0, 2.0, 3.0, 4.0)
        != Err(foundation_appended::CodecError::Truncated)
    {
        return Err(CallError::UnexpectedReply);
    }

    let mut poisoned = [0; 32];
    let mut first_error = RecordBuilder::new(&mut poisoned);
    first_error.number(1, f64::INFINITY).u32(2, 7);
    if first_error.finish() != Err(foundation_appended::CodecError::InvalidValue) {
        return Err(CallError::UnexpectedReply);
    }
    Ok(())
}

fn nested_record(depth: u32, output: &mut [u8]) -> Result<usize, foundation_appended::CodecError> {
    if depth == 0 {
        return Err(foundation_appended::CodecError::InvalidValue);
    }
    if depth == 1 {
        let mut leaf = RecordBuilder::new(output);
        leaf.u32(1, 1);
        return leaf.finish();
    }
    let mut child = [0; 320];
    let child_len = nested_record(depth - 1, &mut child)?;
    let mut wrapper = RecordBuilder::new(output);
    wrapper.record(1, &child[..child_len]);
    wrapper.finish()
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
    // SAFETY: the common runtime guarantees the documented allocation lifetime.
    let input = match unsafe { borrow_input(input, bytes) } {
        Ok(input) => input,
        Err(_) => return APP_INVALID_INPUT,
    };
    if Context::decode(input).is_err() {
        return APP_INVALID_INPUT;
    }
    match fixture() {
        Ok(()) => {
            // SAFETY: runtime lifecycle permits one serialized initialization.
            unsafe { core::ptr::addr_of_mut!(INITIALIZED).write(true) };
            APP_OK
        }
        Err(error) => failure(error),
    }
}

/// # Safety
/// The common runtime lends initialized input and serializes all hooks.
#[no_mangle]
pub unsafe extern "C" fn foundation_guest_dispatch(input: *const u8, bytes: u32) -> u32 {
    // SAFETY: the common runtime guarantees the documented allocation lifetime.
    if unsafe { borrow_input(input, bytes) }.is_err() {
        return APP_INVALID_INPUT;
    }
    // SAFETY: no application hook overlaps this invocation.
    if !unsafe { *core::ptr::addr_of!(INITIALIZED) } {
        return APP_FAILED;
    }
    APP_OK
}

#[no_mangle]
pub extern "C" fn foundation_guest_step(_budget_units: u32) -> u32 {
    STEP_IDLE
}

/// # Safety
/// Runtime serializes shutdown after the last active application borrow.
#[no_mangle]
pub unsafe extern "C" fn foundation_guest_shutdown(_reason: u32) {
    // SAFETY: shutdown is serialized after the last application invocation.
    unsafe { core::ptr::addr_of_mut!(INITIALIZED).write(false) };
}

#[panic_handler]
fn panic(_info: &core::panic::PanicInfo<'_>) -> ! {
    foundation_appended::abort()
}
