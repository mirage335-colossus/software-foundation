# Rust appended guest crate

`foundation-appended` is an allocation-free `no_std` crate with no external
dependencies. Its guest profile is `wasm32v1-none`, edition 2021, Rust 1.84 or
newer, and aborting panics. This is a separate guest-toolchain requirement; it
does not change the ordinary kernel compiler baseline.

The crate decodes the 64-byte envelope, canonical bounded records, initialization
context and bootstrap discovery/control records. All integers are explicitly
little-endian. Local Rust layouts never form wire values. Unknown optional fields
remain readable; operation readers reject unknown must-understand fields.

`Client` uses the common runtime's generation-bound sequence source, shared with
other clients and guest languages. Its synchronous `invoke` borrows
initialized, nonoverlapping request and reply slices only until return. Callers
check the service status separately from transport success. Retained results use
the bootstrap read/release operations; acknowledge completed sequences to bound
the request ledger. The client never automatically retries an uncertain effect.

Link one final application `staticlib` with the SDK's common C guest runtime.
That runtime owns the public `foundation_app_*_v1` exports, its bounded allocator,
the single initialization attempt, constructor execution, dispatch and step
guards, and shutdown. Rust implements the four `foundation_guest_*` hooks and
supplies exactly one panic handler. The crate itself supplies neither an allocator
nor a panic handler. No Rust unwind crosses a hook.

Hook input is borrowed for the current invocation. `borrow_input` is unsafe:
the caller must establish allocation, initialization, lifetime and aliasing
guarantees. A linear-memory bounds check by itself does not establish a valid
Rust slice. Copy needed values before returning. Keep service work in the explicit
initializer rather than constructors.

The numeric binding in `src/abi.rs` is checked against the authoritative public
header. The pure codec tests are independent of the guest runtime. Actual guest
compilation, final import/export/feature auditing and execution require the
separately retained guest toolchain through the supported build wrapper.
