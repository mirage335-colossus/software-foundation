# Rust calculator guest

This `no_std` application uses the local `foundation-appended` crate and the
common C guest runtime. It needs the retained `wasm32v1-none` guest toolchain
(Rust 1.84 or newer), with aborting panics and no external crates.

Build through the supported wrapper with an existing private output directory
and an explicitly selected retained guest SDK descriptor:

```sh
./build.sh appended compile --source src-bin-appended/rust --language rust \
  --entry src/lib.rs --sdk /absolute/path/to/guest-sdk/sdk.json \
  --output /absolute/private/output/calculator-rust.wasm \
  --receipt /absolute/private/output/calculator-rust.json
```

Initialization discovers `foundation.diagnostics` version 1.0. Dispatch operation
1 accepts a canonical record with required `u32` fields 1 (`lhs`) and 2 (`rhs`).
The application computes a checked sum and sends diagnostics operation 1 a record
containing field 1 (`u32` result) and field 2 (`bool` overflow). Overflow produces
result zero and overflow true. It verifies the service's echoed record and
acknowledges completed outbound calls, including discovery.

The instance stores only owned numeric context, a discovered handle and its
last outbound sequence. It shares the common runtime's sequence source and
retains no input pointers. The common runtime owns
the public lifecycle exports and invokes the four Rust hooks in this crate.
The panic handler traps so host-owned cleanup can retire the failed instance.
