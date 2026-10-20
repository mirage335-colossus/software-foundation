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

## `foundation.view` v1 records

The `view` module provides allocation-free builders for the published
`foundation.view` v1 wire records. `view::rect` and `view::widget` write into
caller-owned byte buffers; `view::Builder` and `view::ListBuilder` compose
canonical TLV records and record lists in the same way. Check every `finish`
result and submit only a successful buffer. A failed append poisons its builder
and preserves its first error.

View numbers are finite IEEE-754 `f64` values encoded as exact little-endian
bits. Integer generations remain `u64` throughout record construction. Nested
record validation accounts for the outer record's depth, so a child that fits
when standalone may exceed the limit when wrapped. The public API and validation
are implemented in [`src/view.rs`](src/view.rs), against the published
[`foundation.view` v1 schema](../../../abi/appended/view/v1.json).

These builders encode view records; they do not discover a service or choose a
handle. An application first uses the bootstrap discovery flow in `bootstrap`
to negotiate `foundation.view` version 1 and its schema identity, then sends the
encoded replacement to the returned interface handle with operation
`view::REPLACE`.

The reusable guest and Node host fixture lives in
[`tests/fixtures/appended-rust-view`](../../../tests/fixtures/appended-rust-view).
It compares complete rect, widget and replacement bytes against fixed goldens
and exercises nested-depth, capacity, nonfinite-number and error-retention
vectors through the actual guest lifecycle. Compile only its Rust source using
an explicitly selected retained guest SDK descriptor; the source directory
contains only `lib.rs`, while output paths are outside it and must be absent:

```sh
./build.sh appended compile \
  --source "$PWD/tests/fixtures/appended-rust-view/src" \
  --entry lib.rs --language rust \
  --sdk /absolute/path/to/retained-rust-guest-sdk.json \
  --output /absolute/path/to/output/rust-view-fixture.wasm \
  --receipt /absolute/path/to/output/rust-view-fixture.compile.json
node tests/fixtures/appended-rust-view/run.mjs \
  /absolute/path/to/output/rust-view-fixture.wasm
```

This fixture qualifies the Rust view codec/module boundary only. It does not
establish Foundation GUI, terminal, browser, or release-runtime acceptance.

## Rust calculator and optional providers

The [portable calculator fixture](../../../tests/fixtures/appended-rust-both/README.md)
uses the same view behavior on GUI and terminal hosts. `Service::discover_optional`
returns `Ok(None)` only for an absent provider gateway whose completed discovery
has been successfully acknowledged. Transport, decode and ACK failures remain
errors. `Service::discover` retains its required-service semantics.

The current successor passed complete Wasm wire goldens, both original negatives,
five optional-gateway vectors, a real native provider probe and actual retained
Linux TUI 17 + 25 → 42 with natural shutdown and restored terminal settings. The
module compiled in 1.950 seconds; packaging took 0.138 seconds. These are single
samples. The earlier exact required-gateway module separately passed private
Foundation partial-BOTH runtime/readback. Full public-host/browser, native GUI,
viewer and cross-platform qualification remain pending; see the fixture's limits.
