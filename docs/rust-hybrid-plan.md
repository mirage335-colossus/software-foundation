# Optional Rust/C++ implementation

Implementation date: 2026-10-04. This document supersedes the research proposal
written against `45b27ebc36feabdb772ae99edb2f86dca2c6b093`. Implementation started
from `8854f4fb9026c21d72d9066f6afffca7bd17bf31`. Contracts and execution evidence
are separate below: existing C++ release evidence in [validation](validation.md)
does not automatically qualify Rust binaries.

## Decision

Rust is an explicitly selected implementation of one shared application
component. C++ remains the complete default. The public C++ API, application
behavior, GUI feature layout and package formats are unchanged. Ordinary C++
builds do not discover or require Rust tools.

The initial Rust component uses stable Rust 1.63, edition 2021, a format-3
lockfile and no external application crates. It has no build scripts, procedural
macros, allocator, OS calls, threads or retained pointers. CMake owns the final
link; Cargo is only a subordinate producer of an identified static archive.

This follows the kernel's incremental adoption and reviewed foreign interfaces,
not its build machinery or target promises. See the
[kernel abstraction guidance](https://docs.kernel.org/6.15/rust/general-information.html)
and [architecture restrictions](https://docs.kernel.org/rust/arch-support.html).
Safe Rust cannot repair invalid pointers from C++ or an unsound foreign interface.

## Shared component

```text
CLI and all selected shared GUI frontends
                  |
          foundation::Store
                  |
 foundation::detail::validate_text
                  |
       private versioned C ABI
          /               \
   C++ provider       Rust provider
```

The component validates printable ASCII text. Empty text, text longer than 256
bytes and bytes outside inclusive ASCII 32 through 126 retain the existing
errors. Length checks precede byte checks; validation precedes mutation. C++
continues to own strings, records, allocation, exceptions, IDs and GUI objects.
`include/foundation/store.hpp` is unchanged.

FLTK, Rev, SDL, TUI, framebuffer and hosted web all use the existing shared
application/core. Browser Wasm uses that same core in its existing Emscripten
module. No adapter duplicates validation or implements Rust-specific features.
Hosted web is a native server; browser Wasm is a separate target ABI.

### Foreign interface

`src/text_validation.h` is private, not an installed public API. It accepts
`const uint8_t *` and `size_t`, corresponding to `*const u8` and `usize`, and
returns a `uint32_t`/`u32` status:

| Value | Meaning |
| --- | --- |
| 0 | Valid text |
| 1 | Invalid length, checked first |
| 2 | Invalid ASCII byte |
| 3 | Null pointer with an otherwise acceptable length |

For an accepted length the caller must provide initialized, readable bytes in
one live allocation, unchanged for the call. Neither provider changes, frees
or retains that buffer. Invalid lengths are rejected before dereferencing or
constructing a slice. Pointer validity beyond null cannot be checked generally.
See the [slice contract](https://doc.rust-lang.org/std/slice/fn.from_raw_parts.html)
and [Rust FFI guidance](https://doc.rust-lang.org/nomicon/ffi.html).

C++ translates expected status codes to existing exceptions after Rust returns.
Unknown statuses fail closed. No strings, vectors, native enums, trait objects,
exceptions or language-owned allocations cross the boundary. This does not make
the installed C++ classes a stable cross-compiler ABI.

Production Rust is `no_std` with `panic=abort`, one code-generation unit and no
LTO. Its panic handler invokes a non-returning C++ `noexcept` abort hook. Expected
input errors return values; a panic terminates the process/module. No unwinding
or recovery crosses languages. The C++ forwarder and panic hook share a
translation unit so static archive extraction resolves the callback correctly.
Native Rust unit tests use a separate standard test harness/output tree; that
harness is not the production panic policy.

## Configuration

The supported wrapper selects `--core-provider cpp|rust`, default `cpp`, and
`--rust-sdk /absolute/path`. Direct CMake exposes
`FOUNDATION_CORE_PROVIDER=cpp|rust` and `FOUNDATION_RUST_SDK_ROOT`. There is no
automatic provider. Missing tools, missing target libraries, changed identities
or incompatible SDK pairs fail; they never select C++ silently.

```sh
python3 tools/build.py test dev --build-dir build/cpp --label core
python3 tools/build.py test dev --core-provider rust \
  --rust-sdk /absolute/rust-sdk --build-dir build/rust-dev --label core
python3 tools/build.py test release --core-provider rust \
  --sdk /absolute/cpp-sdk --rust-sdk /absolute/rust-sdk \
  --gui --build-dir build/rust-release --test core.text_validation
```

Paths are already prepared inputs, not download requests. Windows uses
`--windows-dependencies` for prepared C++ dependencies. Browser builds pair the
Emscripten `--sdk` with its Rust extension. [Building](building.md) gives backend,
test and package commands. Changing provider/toolchain requires a fresh compatible
tree; native and Wasm ABIs necessarily use separate trees.

Native Linux development without a C++ SDK may explicitly use installed distro
tools. Portable/release, Windows and browser profiles require retained tools.
Rustup proxies are not accepted as selected compiler executables. Actual Rust
1.63 execution, not just `rust-version`, verifies source compatibility with the
[Bookworm compiler baseline](https://packages.debian.org/bookworm/rustc).
Record [Cargo's package version](https://packages.debian.org/bookworm/cargo)
separately from its executable version.

### Build and installation

One Rust archive per target/configuration is reused by every frontend. Debug
and Release have separate output directories, including multi-config CMake.
`tools/rust_build.py` binds source/manifests/lockfile, compiler, Cargo, target
libraries, flags, notices and output in a receipt. Only an explicitly registered
generated archive in the owned build tree is exempted from configure-time
imported-library hashing; all other SDK/imported-path checks remain.

Cargo runs with a private home/output directory, frozen inputs, offline mode,
explicit compiler/sysroot and one job. Ambient Cargo configuration, wrappers and
uncontrolled flags are rejected. Metadata verifies the exact dependency-free
workspace. No normal configure/build/test/package action acquires missing inputs.

Installation verifies the receipt and ships the finished Rust archive, native
link requirements and notices alongside the C++ archive. The installed CMake
package imports that archive before its exported core. It has no SDK/build-tree
paths or compiler-facing `.rlib` dependency and never invokes Rust tools.
Relocation tests shadow Rust commands with failing launchers. Consumers still
need a compatible C++ compiler/runtime, exactly as before.

The existing wrapper retains CPU/memory budgeting. Cargo's single job prevents
nested parallelism from multiplying the CMake budget. Existing process-tree and
Windows compiler-session ownership cover compiler subprocesses. Test discovery,
focused selections, disjoint shards and source-bound evidence reuse include the
new provider and inputs; different providers cannot reuse behavior evidence.

## Target contracts

| Target | Rust integration contract |
| --- | --- |
| Linux x86_64 | GNU target, generic CPU, existing glibc/private C++ runtime floors and final ELF audit |
| Linux aarch64 | Native GNU target and matching aarch64 libraries; x86_64 execution is not ARM runtime evidence |
| Windows x86_64 | Native MSVC final link, official MSVC Rust target libraries, existing static CRT policy and native execution |
| Browser wasm32 | `wasm32-unknown-emscripten`, exact Rust 1.63/core/builtins plus retained Emscripten 6.0.10 tuple, native Wasm objects, no LTO or pthreads |

CMake 3.24, Python 3.9 and existing Bookworm build-host/runtime floors remain.
Compiler executables have host requirements, and `no_std` alone does not prove
the final executable has no libc requirements. Final runtime audits still apply.
Other OSes/CPUs, musl, Windows ARM64 and Arduino firmware are not qualified by
this implementation. This narrower Rust list does not restrict the C++ route.

### Browser decision

There is no wasm-bindgen, `wasm32-unknown-unknown` substitution or second Rust
browser module. C++ and Rust code link into the existing application module.
Rust 1.63 uses LLVM 14 and the retained Emscripten SDK uses a newer LLVM; their
bitcode is not interchangeable. The link consumes native Wasm objects with LTO
disabled and fatal signature warnings. The exact compiler, libraries, SDK recipe
and exception/link settings form one qualification tuple. Upgrades require new
ABI and browser evidence, as cautioned by
[Rust's Emscripten guidance](https://doc.rust-lang.org/rustc/platform-support/wasm32-unknown-emscripten.html#emscripten-abi-compatibility).

## SDK and recovery

This task permits free-to-use official Rust distributions alongside distro and
Microsoft tools, superseding the proposal's distro-only supplier restriction.
No third-party application crate or repository is added. Acquisition is an
explicit SDK preparation operation, separate from ordinary application work.

`tools/rust_sdk.py` and `third_party/rust/*.json` define a separate extension.
`rust-sdk.json` records compiler, Cargo, target, host, licenses and a complete
inventory. Retained groups contain binary/source archives and checksums under
an exact recipe ID. Existing C++ SDKs retain their schema/identity; Wasm binds
the exact C++ SDK recipe as well.

```sh
python3 tools/rust_sdk.py fetch --recipe third_party/rust/linux-x86_64.json \
  --inputs /absolute/rust-inputs
python3 tools/rust_sdk.py prepare --recipe third_party/rust/linux-x86_64.json \
  --inputs /absolute/rust-inputs --output /absolute/new-rust-group
python3 tools/rust_sdk.py recipe-id --recipe third_party/rust/linux-x86_64.json
python3 tools/rust_sdk.py restore --group /absolute/rust-group \
  --recipe EXACT_RECIPE_ID --output /absolute/new-rust-sdk --execute
python3 tools/rust_sdk.py restore-sources --group /absolute/rust-group \
  --recipe EXACT_RECIPE_ID --output /absolute/recovered-rust-sources
```

Only `fetch` downloads. `prepare` needs all pinned supplier bytes already
present. Wasm also requires `--cpp-sdk /absolute/emscripten-sdk`. Source recovery
retains exact sources, supplier inputs, bootstrap metadata/binaries, recipes,
hashes and licenses. It is not a compiler build command.

Three distinct claims are recorded:

1. **Offline application build:** retained tools/targets run configure, compile,
   test and package with network access denied.
2. **Retained-toolchain restoration:** original binary inputs are verified,
   restored and executed without downloads.
3. **Compiler reconstruction from source:** compiler/LLVM/Cargo and their entire
   bootstrap closure are rebuilt and validated. This is not claimed here.

A source archive or `stage0.json` is not proof of compiler reconstruction. The
manifest states this bounded recovery scope. A complete source producer requires
separate qualification and considerably more resources.

Release metadata identifies the provider and Rust inputs. Application packages
contain finished binaries/archives and notices, not a runtime Rust installer.
Existing Debian, Arch and Gentoo mechanisms wrap verified payloads; package
installation requires no Cargo or crates.io. Rust retained groups accompany
dependency recovery inputs. Duplicate-target and promotion gates remain intact.
No stable publication or repository promotion is authorized by this task.

## Qualification evidence

Initial discriminating checks passed during implementation:

- Default C++ core tests with no Rust tools on the host PATH; missing-Rust and
  in-place provider-change rejection.
- Installed/relocated C++ consumer with Rust commands shadowed to fail.
- Existing C++ runtime fixture's dynamic/export negative controls, protected
  runtime and changed-header rejection after extracting the validator.
- Rust 1.63/Emscripten 6.0.10 mixed probe: 1,352 Node assertions, primitive ABI
  checks and intentional Rust panic reaching C++ abort.
- Actual Rust source, C++ bridge and exhaustive boundary tests linked and ran
  in Node in Debug and Release; retained SDK/cache inventories unchanged.
- Namespace/container adapter unit tests and a derived, verified Bookworm rootfs
  prepared without modifying the original boundary.

These preliminary results do not establish the full Windows/Linux backend,
browser UI, disconnected application/package or SDK replay matrix. Final
qualification must name every executed gate and exact inputs. Unexecuted,
skipped or compile-only targets are not runtime passes.

## Future portable logic

Arduino is not an implementation target. The bounded byte/status leaf and C++
equivalent are a starting point for selected firmware functionality, not the
entire desktop Store or GUI stack. Future MFD menus/state transitions should
use explicit bounded inputs/outputs behind the feature abstraction, with board
adapters providing display, input and device services. Each board needs its own
memory, target-library, interrupt, panic and mixed-link qualification.

Expand Rust where a meaningful component benefits from its ownership/type
checking. Measure iteration time, test cost, review effort and defects before
claiming fewer AI tokens or lower maintenance. Two providers and another SDK
have a real cost. Agents must coordinate shared ABI/build invariants and freeze
relevant inputs during qualification under the existing
[coordination policy](agent-coordination.md).
