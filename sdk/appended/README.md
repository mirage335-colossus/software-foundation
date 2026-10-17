# Portable guest SDK

The `foundation-guest-v1` profile uses scalar core wasm32 instructions, mutable
defined globals, one unshared bounded memory, the seven application exports and
the single `foundation.kernel.v1.call` import. The authoritative protocol lives
in `include/foundation/appended/abi.h` and `abi/appended/v1/`. The compiler copies
that header into a private binding snapshot; this directory does not allocate a
second set of protocol IDs. Final linked bytes pass `tools/appended_wasm.py`.

C11 and C++17 applications include `foundation/appended/guest.h` or `guest.hpp`.
The Rust crate is dependency-free `no_std`; it uses a separately retained
`wasm32v1-none` compiler and target library set. The ordinary kernel Rust baseline
is unchanged. This first profile supplies byte operations and codecs rather than
a full standard library. Floating-point library functions and richer libraries
need an explicitly qualified profile. C++ exceptions, RTTI, thread-local state,
unwinding, threads, and system calls are unsupported. Rust panics abort.
Use the SDK's `abort()` in a Rust panic handler; application source needs no
target-specific intrinsic or host-language shim.

The common C runtime owns allocation and lifecycle for every language. Override
the `foundation_guest_initialize`, `foundation_guest_dispatch`,
`foundation_guest_step`, and `foundation_guest_shutdown` hooks. Rust static
archives must define all four: their runtime object requires the real hooks, and
the linker selects only their needed archive members. Missing hooks fail linking
instead of silently retaining optional C defaults. Their input is
borrowed only until return. The public application exports accept scalar memory
offsets and counts. The host copies context/input into an allocation from the
same guest allocator and frees it after the hook returns.

The allocator works before initialization, returns 16-byte-aligned nonzero
offsets, and rejects zero-byte or exhausted allocations. Its fixed arena is
65536 bytes, including 16-byte block headers; the largest single allocation is
65520 bytes. Freed adjacent blocks coalesce. Free requires the original offset
and requested byte count; invalid frees are ignored. This profile does not grow
memory. Allocation remains available in constructors; ABI query and allocation
do not execute constructors or call services.

Initialization permits one attempt per instance, including malformed context.
The wrapper validates and binds the bootstrap context, runs C/C++ constructors
exactly once, then invokes the application initializer. Constructors may inspect
context and allocate; service calls are rejected until the initializer starts.
Keep service readiness work in the initializer. At most 32 static destructors
may register; exceeding that bound fails initialization. Normal shutdown invokes
the hook once and runs those destructors in reverse registration order. Service
calls are rejected during destructor execution. A trap or terminal error requires
host-owned cleanup and destruction of the instance; do not invoke more guest code.

`step(0)` returns idle without calling application code. Other budgets are
cooperative units supplied to the application hook. An interpreter fuel/time
budget must bound a hook that does not return; this wrapper cannot preempt it.
Requests use one shared nonwrapping sequence source across C, C++, and Rust.
The caller retains canonical bytes for deliberate retries and acknowledges
completed outcomes. Transport success and service success are distinct. Large
results require explicit bootstrap read/release calls.

Compile only the selected guest through the maintained wrapper:

```sh
./build.sh appended compile --source src-bin-appended --language c \
  --entry c/calculator.c --sdk /retained/guest-sdk.json \
  --output /owned/calculator.wasm --receipt /owned/calculator.json
./build.sh appended compile --source src-bin-appended --language c++ \
  --entry cpp/calculator.cpp --sdk /retained/guest-sdk.json \
  --output /owned/calculator-cpp.wasm --receipt /owned/calculator-cpp.json
./build.sh appended compile --source src-bin-appended/rust --language rust \
  --entry src/lib.rs --sdk /retained/rust-guest-sdk.json \
  --output /owned/calculator-rust.wasm --receipt /owned/calculator-rust.json
```

Output directories must already exist and outputs must be absent. Source and
tool inputs are rechecked before publication. Compilation uses a private source
snapshot, explicit include paths, fixed profile flags, offline tool inputs and
the final import/export/instruction audit. It invokes no kernel graph. No tools
are discovered or downloaded. Rust compilation invokes the retained compiler
directly and audits dependency files; package resolution is unnecessary.

For byte-exact recovery, source/binding paths map to
`/foundation/guest/work` and compiler-library paths to `/foundation/guest/sdk`.
Private copied files have the Unix epoch timestamp; the compiler environment
fixes `SOURCE_DATE_EPOCH=0` and `TZ=UTC`. File/date/time macros therefore describe
that reproducible snapshot, rather than the developer's directory or clock.
C/C++ use file, macro and debug prefix maps; Rust uses path remapping. Workspace
and SDK paths containing `=` are rejected because the shared prefix-map syntax
cannot represent them. Unsupported compiler flags fail; no alternate toolchain
or kernel build is selected.

The compiler SDK descriptor has this shape. Replace every digest with the
reviewed SHA256 of the exact retained bytes:

```json
{
  "schema_version": 1,
  "profile": "foundation-guest-v1",
  "root": "guest-tools",
  "tools": {"clang": "bin/clang", "clangxx": "bin/clang++", "wasm_ld": "bin/wasm-ld"},
  "inventory": {
    "bin/clang": {"sha256": "REVIEWED_SHA256", "executable": true},
    "bin/clang++": {"sha256": "REVIEWED_SHA256", "executable": true},
    "bin/wasm-ld": {"sha256": "REVIEWED_SHA256", "executable": true}
  }
}
```

`root` is absolute or relative to the descriptor. Keep the descriptor outside
that root to avoid a self-hash cycle. `inventory` must describe every regular
file in the dedicated tool tree, including relevant compiler libraries and
target libraries; undeclared files or links fail verification. Host operating
system runtime libraries remain prerequisites. The receipt records host system
and architecture, compiler descriptor/inventory, source and binding identities,
commands, final module digest and audit. Retain the descriptor and tool inputs
with the receipt for recovery.

A Rust descriptor additionally names `rustc` in `tools` and sets `rust_sysroot`
to an inventoried relative directory containing
`lib/rustlib/wasm32v1-none/lib/libcore-*.rlib` and
`libcompiler_builtins-*.rlib`. Supply the actual compiler, its runtime closure,
and target libraries in the complete inventory. Missing Rust inputs fail with
an actionable error. C and C++ have been compiled with retained LLVM 24 in the
initial focused probe. A separate retained Rust 1.84.0/`wasm32v1-none` tool set
also compiled the actual Rust example and executed its checked-addition and
overflow paths through the native kernel. See
[the development evidence](../../docs/appended-validation.md); this is not
complete toolchain or platform qualification.

The calculator examples are service clients. They accept operation 1 with two
required `u32` operand fields, compute checked addition, and send the result plus
overflow flag through `foundation.diagnostics` version 1.0 operation 1. Overflow
returns zero and a true flag. They acknowledge completed calls. The C++ example
also checks constructor count, bound generation, and constructor allocation.
They do not implement a view or module service registration.

Application functions can also be exported through `foundation.providers` 1.0.
Include `foundation/appended/providers.h` (C), `providers.hpp` (C++) or the
Rust crate's `providers` module. The compiler snapshots the authoritative
`include/foundation/appended/provider_abi.h` alongside `abi.h`; the additive
service does not change the seven guest exports or introduce another import.
The [wire contract](../../abi/appended/providers/v1.json) defines registration,
discovery, invocation events and explicit responses.

Register each namespaced application contract during initialization, with its
version, schema digest and request/reply limits. Dispatch the provider CALL
event through the binding, perform the operation in C/C++/Rust, and respond once
before dispatch returns. The host queues work until its current renderer/native
callback ends. Provider handles belong to this catalog and must not be passed
to native Registry calls. Guest control calls share the same request sequence
and ACK machinery as other native services; host provider requests have a
separate replay ledger. No JavaScript is required by these bindings or fixtures.

The [C](../../tests/appended/provider_fixtures/c/provider.c),
[C++](../../tests/appended/provider_fixtures/cpp/provider.cpp) and
[Rust](../../tests/appended/provider_fixtures/rust/src/lib.rs) fixtures implement
the same schema-pinned increment operation. They demonstrate registration,
discovery, explicit response, error handling and acknowledged control calls.
The generic host interface is
[`ModuleProviders`](../../include/foundation/appended/providers.hpp); owners must
outlive every invocation and callback, including guest allocation and free.
Recursive shutdown is deferred, but destroying an active owner is forbidden.

For a binary GUI application, compile the separate `c/view_calculator.c` entry
instead. It discovers the exact `foundation.view` version-one schema and uses
`view.h` builders to submit a complete snapshot. Two text inputs, a Sum button
and a result label keep feature behavior in the guest. Editing retains the
authoritative revision and widget generations; activation or Enter computes
checked addition. Input, state and layout contain no adapter types. Every
accepted replacement advances the revision and acknowledges its request.

```sh
./build.sh appended compile --source src-bin-appended --language c \
  --entry c/view_calculator.c --sdk /retained/guest-sdk.json \
  --output /owned/view-calculator.wasm --receipt /owned/view-calculator.json
```

`view.h` is an allocation-free C interface that C++ can also include. Its schema
identity is checked against `abi/appended/view/v1.json`. It supplies canonical
record/list, number, rectangle and widget builders. Builder failure produces
`UINT32_MAX`; never submit that buffer. The version-one view interface supports
full snapshots rather than imperative focus, selection, or scrolling commands.
