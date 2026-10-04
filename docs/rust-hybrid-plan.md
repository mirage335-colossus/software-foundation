# Optional Rust integration research and plan

Research date: 2026-10-04. Repository inspected at
`45b27ebc36feabdb772ae99edb2f86dca2c6b093`.

This is a proposal, not implemented Rust support or platform qualification. It
evaluates hybrid Rust/C++ against this example's portability, offline supply,
shared GUI, build-speed and delivery requirements. Existing support claims remain
in [portability](portability.md) and [validation](validation.md).

## Recommendation

Add Rust as an optional implementation of a small application component, behind
a private C ABI and the existing C++ interface. Keep the C++ implementation as
the default and the complete compatibility route. Start with stable Rust 1.63,
edition 2021, no external application crates, and an allocation-free `no_std`
component. Let CMake own the application graph and final link; invoke retained
Rust tools as a subordinate build step. Preserve the current SDK, test, package
and release machinery.

This can preserve every currently supported frontend and platform by retaining
the C++ route. It cannot honestly promise that Rust itself will build on every
C++ target, every OS, or every Arduino board under the same old-package-only
constraint. Rust target support, packaged target libraries, ABI compatibility,
GUI availability and actual execution evidence are separate requirements.

The strongest initial opportunity is native Linux x86_64 and aarch64. Native
Windows MSVC, the existing Emscripten application, and selected microcontrollers
need additional SDK work. AVR and vendor-specific embedded toolchains should
remain outside the first supported Rust profile.

The current example is very small. Rewriting its store merely to use Rust would
add more machinery than application value. A narrow pilot can establish a useful
reference pattern; expansion should depend on measured maintenance benefits for
bounded parsers, codecs or state transitions with meaningful safety requirements.

## What the kernel example establishes

Linux demonstrates incremental mixed-language development and carefully reviewed
bindings wrapped in safe abstractions. Kernel Rust uses `no_std`; that does not
mean arbitrary Rust libraries work in the kernel. Its supported Rust architecture
set also has explicit restrictions. These are useful architectural lessons, not
proof of universal target support. See the versioned
[kernel abstraction guidance](https://docs.kernel.org/6.15/rust/general-information.html)
and [current architecture restrictions](https://docs.kernel.org/rust/arch-support.html).

For this application, adopt the narrow interfaces and incremental adoption. Keep
the established CMake/Python orchestration. There is no reason to inherit kernel
configuration, kernel-specific APIs or the kernel's evolving compiler requirements.
Do not require generated bindings over the entire C++ API: its classes, templates,
standard-library objects and exception behavior are a much wider integration
surface than the proposed handful of C functions.

Memory safety is conditional at the language boundary. Safe Rust can prevent many
invalid lifetime and aliasing operations inside the component; it cannot repair
an invalid pointer supplied by C++, unsound FFI code, a faulty device driver or
an incorrect application algorithm.

## Existing foundations and supply limits

The current [architecture](architecture.md) already gives this proposal a suitable
home. `foundation_core` is compiled once per configured tree; the CLI and shared
GUI use it. [Store](../include/foundation/store.hpp) owns strings and records;
its [implementation](../src/store.cpp) validates text before changing state.
GUI adapters own platform behavior, while the application owns feature meaning.

The following distinctions must remain visible in any Rust support statement:

| Promise | What it requires |
| --- | --- |
| Old build host | Compiler executables and their host dependencies run on the declared oldest host |
| Old runtime | Every final executable and private library satisfies the declared target ABI and CPU floor |
| Offline application build | Complete retained inputs, empty ambient caches, no download or dependency repair during configure/build |
| Allowed suppliers only | Every added tool, crate and bootstrap input comes from the permitted distribution or Microsoft source |
| Offline SDK reconstruction | Complete source, patches, compiler bootstrap inputs and recipes rebuild the retained toolchain within a specified boundary |

Offline retention and restricted suppliers are not interchangeable. The existing
[native SDK producer](sdk.md#native-source-producer-and-bookworm-bootstrap) uses
a newer GCC toolchain on a Bookworm host with a Bookworm-compatible target. The
[Rev profile](gui-boundary.md#prepared-platform-dependencies) needs newer module
tools than stock Bookworm supplies. The Wasm SDK retains compiler/bootstrap
binaries and does not claim to rebuild every one of them from native source.
Those existing qualifications must not be restated as an all-components,
stock-Bookworm-packages-only guarantee.

Use the following policy for this proposal: add no supplier exception for the
initial Linux Rust profile. For another profile, first demonstrate that its full
Rust closure is available within the allowed suppliers. Otherwise keep that
profile C++ and document the optional retained-toolchain alternative. A retained
upstream archive solves recurring internet dependence but does not, by itself,
satisfy the stricter supplier condition.

### Bookworm baseline

Debian Bookworm publishes Rust compiler and standard-library packages at
`1.63.0+dfsg1-2`. Its Cargo package has the Debian version `0.66.0+ds1-1`;
record the installed `cargo --version` separately rather than using the package
version as the executable's version. Native amd64 and arm64 packages make these
the natural first profiles. See [rustc](https://packages.debian.org/bookworm/rustc)
and [Cargo](https://packages.debian.org/bookworm/cargo).

Proposed source rules:

- Set `rust-version = "1.63"`, `edition = "2021"` and resolver 2 explicitly.
- Generate and verify a lockfile format readable by the baseline Cargo. Do not
  silently rewrite it using a newer developer installation.
- Keep external crate dependencies, build scripts and procedural macros absent
  for the pilot. Standard/compiler support libraries still belong in the SDK inventory.
- Compile with the actual minimum toolchain in CI. A manifest's `rust-version`
  field does not prove source or standard-library API compatibility.
- Keep rustfmt, Clippy and editor integrations optional for building the product;
  pin the versions used by any mandatory style checks.
- Review maintained distro security updates separately from the minimum language
  version. Preserving old source compatibility is not a reason to freeze known defects.

The Rust compiler, its `core`/`std` libraries, compiler-builtins and associated
metadata form a matched toolchain. A collection of `.rlib` files from another
compiler version is not a portable substitute. A C-facing finished archive has
a different compatibility boundary from a Rust compiler-facing library.

Use version-appropriate syntax too: current documentation can show edition 2024
attributes and newer APIs that do not compile on 1.63. Newer Cargo lock formats
and build-script directives must not enter the baseline accidentally.

## Proposed application boundary

The dependency direction remains:

```text
CLI and all shared GUI feature code
                  |
          foundation::Store
                  |
      private component interface
             /          \
    C++ implementation   C ABI adapter -> safe Rust component
                  |
        existing OS and GUI services
```

Choose the implementation at configure time. Proposed names below are design
examples and are not available commands or options yet:

```text
FOUNDATION_CORE_PROVIDER=cpp    default, no Rust discovery or tools required
FOUNDATION_CORE_PROVIDER=rust   explicit, requires the selected complete Rust SDK
```

Do not use an automatic provider mode. An explicitly requested Rust configuration
with missing inputs must fail clearly; it must not silently test or ship C++.
Changing provider or toolchain changes build identity and requires a compatible
fresh tree. Production binaries contain one provider. Differential test executables
can link separately named implementations solely for comparison.

### First component

Extract the existing printable-ASCII text validation into a private bounded
operation. Preserve its length limit, accepted bytes, validation order, failure
messages, and the store's unchanged-state guarantees. Retain allocation, ID
management, exceptions, storage and GUI objects in C++ for this pilot. The same
small validation function is practical to exercise on an embedded board without
porting the desktop store.

An illustrative ABI is:

```c
/* Private ABI proposal, not a new public Foundation interface. */
uint32_t foundation_text_validate_v1(const uint8_t *bytes, size_t length);
```

The header needs ordinary C/C++ linkage guards and explicit numeric result codes.
The C++ adapter translates these results into the existing errors only after Rust
returns. Unknown status values are internal failures, never success. Preserve
the public installed C++ API and its existing compiler/runtime qualification.
The internal C interface does not retroactively make `foundation::Store` a stable
cross-compiler binary interface.

For later, larger components, use caller-owned output buffers and checked lengths
or opaque handles with paired owner-side release functions. Avoid allocating in
one language and freeing in the other. Specify output-on-error behavior before
implementation so partial results cannot be mistaken for successful state.

### FFI rules

- Pass pointers, explicit lengths and fixed-width scalar results. Keep `size_t`
  for in-process lengths with the matching Rust `usize`; persisted formats need
  independently specified widths and byte order.
- Do not pass C++ strings, vectors, exceptions, Rust `String`/`Vec`/`Result`, trait
  objects, native enums, `bool`, or structures by value across the first ABI.
- Reject lengths zero or greater than 256 before constructing a Rust slice.
  For accepted lengths, require a nonnull pointer to initialized bytes in one live
  allocation, unchanged until return. Runtime checks cannot establish arbitrary
  pointer validity or exclusive ownership. Even an empty slice cannot be constructed
  from null; see the [slice safety contract](https://doc.rust-lang.org/std/slice/fn.from_raw_parts.html).
- Keep borrowed buffers within the call. No retained pointers, callbacks, global
  mutable state, asynchronous work or device interrupts in the initial component.
- Isolate `unsafe` in the adapter, document each obligation, and enable
  `unsafe_op_in_unsafe_fn` checking. Keep the actual algorithm safe Rust.
- Represent expected input failures as values. Do not unwind across the boundary
  in either direction; C++ wrappers that Rust calls must contain their exceptions.

These rules follow the boundary hazards described in the
[Rust FFI guidance](https://doc.rust-lang.org/nomicon/ffi.html), with additional
restrictions chosen here to reduce the integration surface. Check actual
[type layout](https://doc.rust-lang.org/reference/type-layout.html) and
[foreign calling conventions](https://doc.rust-lang.org/reference/items/external-blocks.html)
when expanding the interface; Rust's native ABI is not a stable foreign interface.

### Panic and runtime policy

For the initial allocation-free static library, propose `#![no_std]` and an
explicit abort panic strategy. Provide one small, reviewed panic handler per final
Rust component profile, calling a nonreturning host failure hook or the board's
defined fault path. Do not print, allocate or recursively panic in that handler.
A normal validation error must never use this path. Abort is process termination,
not graceful recovery; embedded behavior must be specified and tested separately.

`no_std` is not an assurance of zero support code. The output can still need
compiler-builtins, memory routines, arithmetic helpers or target-specific runtime
symbols. Inventory unresolved references and satisfy them from the verified target
toolchain, accounting for the [core library requirements](https://doc.rust-lang.org/core/index.html).
Host-side Rust unit tests may use `std` and must then exclude the custom no_std panic
handler to avoid duplicate panic implementations. The delivered static-library
profile and handler must also be linked and exercised through the C++ caller so
host tests cannot hide this gap.

An optional future `std` component could reduce application complexity for richer
desktop logic. It would need its own allocator, panic, OS API and native-library
audit. Do not add an async runtime or a Rust GUI toolkit to establish this pilot.

## Backend and platform feasibility

### GUI backends

| Backend | Proposed treatment | Qualification needed for Rust selection |
| --- | --- | --- |
| FLTK | Keep current native adapter and shared application | Link and exercise the shared operation in the installed native host |
| Rev | Keep current renderer/module toolchain | Same shared operation plus existing Rev runtime/graphics coverage; Rust does not lower Rev prerequisites |
| SDL | Keep current window/framebuffer adapter | Native integration and installed smoke behavior |
| TUI | Keep current terminal adapter | Same core operation; retain console/PTY input and rendering checks |
| Framebuffer | Keep current software rendering path | Deterministic image/behavior checks; physical device support remains separate |
| Hosted web | Keep native server-side application and existing browser protocol | Native Rust build plus existing browser/security contract checks |
| Browser Wasm | Keep C++ initially; qualify a matched Emscripten Rust profile separately | C ABI, runtime settings, Node tests and real browser execution |

No adapter should branch on the core language. The existing shared GUI boundary
guards must include new Rust/application source paths where applicable, so a new
language cannot bypass the architectural rule. Backend availability remains
limited by that backend's OS, graphics, browser or terminal requirements. Rust
does not make a desktop toolkit available on a microcontroller.

### Operating systems and processors

All Rust entries below are feasibility assessments, not executed results.

| Target | Assessment | Initial decision |
| --- | --- | --- |
| Linux x86_64 GNU | Native Bookworm Rust package route; audit final linkage against existing SDK | First Rust pilot |
| Linux aarch64 GNU | Native Bookworm route; separate compiler/SDK and native execution | Second required Linux Rust qualification |
| Native Windows x86_64 MSVC | Technically suitable Rust target, but matching native Rust compiler/library supply must be retained and justified | Keep C++ until that closure and runtime policy are qualified |
| Browser wasm32 Emscripten | Possible with deliberately matched Rust/Emscripten inputs; not supplied by Bookworm's Wasm std package | Keep C++ until a separate SDK experiment passes |
| Other Linux architectures | Evaluate compiler version, distro target libraries, ABI, atomics and native execution individually | Preserve C++ route; do not infer support from target-list output |
| musl, BSD, Android or macOS | Separate ABI/SDK/host-service and packaging work | Outside current release commitments |
| Bare-metal MCU | Small no_std component possible on selected targets; no desktop OS/services | Separate board profile and example |

Rust's [target tiers](https://doc.rust-lang.org/rustc/platform-support.html) describe
upstream build/test and tool availability; they do not qualify this application.
Consult the table for the exact compiler release as well as current documentation.
A target recognized by the compiler can still lack packaged target libraries or
an allowed source-reconstruction path.

For Linux, keep the project's glibc 2.36 and other runtime ceilings, generic CPU
baseline, loader closure, symbol visibility and relocation checks. Link Rust through
the same selected C++ linker/sysroot policy. Audit the Rust compiler's own host
libraries separately from application target libraries. Rust's upstream runtime
floor is not a substitute for auditing the distro-built archive and final binary.

For Windows, use the MSVC Rust target with the current MSVC application profile;
align static/shared CRT choice and inspect actual imports. Bookworm's
[Windows standard-library package](https://packages.debian.org/bookworm/libstd-rust-dev-windows)
is for GNU Windows targets, not the existing MSVC profile. Microsoft C++ Build
Tools alone do not establish a complete Rust toolchain. An upstream Rust installer
may be free, but is not thereby Microsoft-supplied. A Linux-built no_std MSVC
archive is a possible separate producer experiment, not native Windows source-build
support; upstream [MSVC target guidance](https://doc.rust-lang.org/rustc/platform-support/windows-msvc.html)
does not support cross-host compilation. Do not silently switch the application
to MinGW to evade this gap. Any helper that launches the native compiler or linker
must preserve the project's `tools/windows_compiler.py` verification, including
direct-CMake entry paths.

If "MS freeware" means any free-to-use Windows development tool rather than
Microsoft-supplied software specifically, an exact retained upstream Rust toolchain
is a practical candidate. It still needs offline installer/component retention and
qualification. The stricter Microsoft-only interpretation leaves the supplier gap
above; neither interpretation permits automatic toolchain downloads during builds.

macOS also needs an Apple SDK and applicable toolchain terms; a literal restriction
to Linux-distribution and Microsoft inputs cannot be assumed to cover native Mac
development. Preserving the current C++ path does not add a macOS qualification
that this repository has never claimed.

### WebAssembly detail

Bookworm's [Wasm library package](https://packages.debian.org/bookworm/libdevel/libstd-rust-dev-wasm32)
contains `wasm32-unknown-unknown` and the then-named `wasm32-wasi`, not
`wasm32-unknown-emscripten`. These targets are not interchangeable.

The [Rust Emscripten target documentation](https://doc.rust-lang.org/rustc/platform-support/wasm32-unknown-emscripten.html)
warns that Emscripten versions and settings can change the ABI, including exception
and JavaScript integer handling. Its suggested std reconstruction route uses
nightly `build-std`. Treat matching compiler, target libraries, Emscripten, flags,
linker, prepared cache and browser feature baseline as one SDK recipe. Do not
introduce that nightly reconstruction into ordinary application builds.

An allocation-free component reduces the runtime surface but does not establish
compatibility of its `core`, object format or ABI. Test this route in SDK
maintenance before declaring it supported. The project can remain fully functional
with the C++ provider in Wasm while using Rust natively.

Do not simply insert a Bookworm `wasm32-unknown-unknown` archive into the existing
Emscripten link. Rust documents historical C ABI differences for this target in
its [ABI migration discussion](https://blog.rust-lang.org/2025/04/04/c-abi-changes-for-wasm32-unknown-unknown/).
Scalar-only functions avoid some problems but do not qualify arbitrary mixed
objects, memory management, stack conventions or runtime flags.

A separate Rust Wasm module communicating through JavaScript is an alternative,
but adds another module, memory/serialization contract and loading failure path.
It should only be chosen for a concrete application need. It is a poor default
for this project's single-build and low-fragility goals. WASI is likewise not a
drop-in replacement for the existing browser and DOM integration.

## Offline Rust SDK design

Extend the existing SDK schema with an optional Rust section and profile-specific
required fields. Old C++ SDK manifests remain valid for C++ selection; a Rust
request against one fails as incomplete. The schema evolution needs explicit
version handling and tests, not ambient compiler discovery.

| Inventory area | Required contents |
| --- | --- |
| Host tools | Exact rustc and Cargo binaries, host triple, executable versions, hashes, dynamic dependency closure, minimum host runtime, optional pinned style tools |
| Rust target libraries | Exact matching core/std/alloc as applicable, compiler-builtins, target triple, compiler identity and target feature policy |
| Native target inputs | Existing C/C++ toolchain, libc/CRT, linker and native sysroot, with approved paths and hashes |
| Source inputs | Rust project source, compatible Cargo.lock, permitted crate source if later introduced, distro source and patches, notices |
| Reconstruction | Distro package archives/metadata and dependency closure; source archives and bootstrap chain for whatever producer claims to rebuild |
| Configuration | Edition, minimum Rust version, panic/CRT/CPU/optimization settings, enabled features, final-link policy, build-host versus target-tool roles |
| Provenance | Package supplier/version/architecture, source recipe, input manifests and qualification receipts, matching existing retained groups |

Rust's `--sysroot` selects Rust target libraries, whereas the C/C++ sysroot supplies
native headers and libraries. Record both explicitly. Pointing both compilers at
the same arbitrary directory is not a cross-compilation design. Build scripts
and procedural macros, if later permitted, execute for the build host, even when
the application targets another architecture.

The source producer must retain all inputs needed to reproduce its stated layer.
Distinguish restoring distro compiler packages, rebuilding application Rust, and
rebuilding rustc itself. The last needs a suitable bootstrap compiler and complete
Rust/LLVM build inputs; it is expensive SDK maintenance, never a normal build step.
Do not call retained binaries proof of compiler source reconstruction.

### Cargo without network dependence

Cargo is useful for dependency identity, incremental compilation, profiles and
unit tests even with no external crates. It does not have to acquire inputs online.
[Cargo documents](https://doc.rust-lang.org/cargo/commands/cargo-build.html) that
`--frozen` combines the locked and offline modes. The proposed subordinate build
uses it with explicit manifest, target, output directory and selected local tools.

Direct `rustc` invocation is a viable alternative for a single dependency-free
crate and would remove Cargo from that production step. It moves profile, input
tracking and test orchestration into project code. Prefer the small Cargo route
unless a measured problem justifies maintaining those details locally. Neither
choice requires a registry connection.

For the pilot, retain only workspace/path dependencies and reject path escapes.
If later crates are justified, prefer the approved distro source closure and a
retained directory source. Verify all transitive versions, patches and minimum
compiler requirements. [Cargo source replacement](https://doc.rust-lang.org/cargo/reference/source-replacement.html)
requires care with modified sources; distro patches and checksum handling must be
preserved through a documented mechanism. A directory copied from a developer's
cache is not a supplier or provenance record.

Use the existing disconnected acceptance boundary as the stronger check:

1. Restore a verified, read-only SDK and retained sources into a fresh environment.
2. Select actual retained binaries by absolute path; do not invoke a rustup proxy
   that can select or install a different toolchain.
3. Give Cargo a private home/output tree and controlled environment. Reject
   unapproved `RUSTFLAGS`, wrappers, linker overrides, target settings and source
   replacement. Account for Cargo configuration in ancestor directories as well
   as its home; `--manifest-path` alone does not isolate configuration.
4. Build with a frozen lockfile and no external network access. Build scripts are
   programs: Cargo's offline flag alone is not a network sandbox for their children.
5. Recheck physical paths, source/tool/library hashes and complete artifact identity.
6. Repeat from an extracted surviving release, with original supplier services and
   the original SDK-base release unavailable.

The [Cargo configuration hierarchy](https://doc.rust-lang.org/cargo/reference/config.html)
is relevant to step 3. Extend the current CMake input checks into the Rust helper;
CMake's imported-library checks cannot inspect arbitrary files a custom command reads.

No `rustup update`, `cargo install`, registry fetch, `git clone`, `build-std` or
compiler bootstrap belongs in configure, ordinary build, package install or user
startup. Missing inputs get an actionable preparation error.

## One build graph and installed consumers

Keep `build.sh` and `tools/build.py` as the entry points. CMake 3.24 must remain
sufficient for the ordinary core build. Add a small local CMake module/helper for
the Rust static library rather than introducing a new fetched build integration.

The wrapper selects provider, verified SDK, target and profile. CMake arranges
one Cargo workspace build per compatible configuration and Rust target, imports
its native archive, then links `foundation_core`, the CLI and selected GUI hosts.
Do not launch Cargo once per executable or GUI backend.

Use a Rust `staticlib` for the non-Rust final link. Its native dependencies still
need explicit linkage; `--print=native-static-libs` helps discover them. A `.rlib`
is not the installed C++ consumer artifact. These distinctions are specified in
the [Rust linkage reference](https://doc.rust-lang.org/reference/linkage.html).

The implementation must handle source/header/manifest/lock/config changes,
toolchain changes, removed output files and Debug/Release separation. Register
real outputs/byproducts and dependencies; do not leave a timestamp-only command
that misses new Rust modules. A lightweight Cargo freshness check is acceptable
when the dependency closure cannot yet be expressed completely, provided it does
not rewrite unchanged outputs or force all consumers to relink.

There is a concrete existing policy interaction to solve:
[BuildPolicy.cmake](../cmake/BuildPolicy.cmake) hashes imported libraries at
configure time, and [DependencyPaths.cmake](../cmake/DependencyPaths.cmake)
restricts SDK library inputs to the sysroot. A generated Cargo archive does not
exist yet and belongs in the owned build tree. Add a narrow generated-application
artifact contract with declared producer, dependencies, allowed physical location
and a verified build receipt. Keep retained Rust target libraries under their
separate SDK inventory. Do not globally allow arbitrary build-tree libraries.

The native imported-library notice path also needs to distinguish this generated
application archive from a distro-owned supplier archive. Bind embedded Rust
library/crate notices explicitly; querying `dpkg` for the generated archive will
not establish its provenance. Keep all Cargo output below `build/`, not a default
`rust/target/` tree that could enter the source identity inventory.

The installed `foundation::core` target must carry the required private archive
and native link requirements transitively. Install the Rust archive alongside the
C++ archive and define an install-relative imported dependency in the package
configuration, or deliberately produce a combined archive with equivalent tests.
The first option is simpler initially. Stage the imported archive separately;
the existing `install(TARGETS ...)` path cannot simply install an imported build
target. Define its installed dependency before loading `FoundationTargets.cmake`.
Do not expose absolute SDK/build paths.
An installed C++ consumer must link without Cargo or rustc installed.

Retain symbol-hiding policy for application binaries and deliberate exports for
consumers. Inspect archive extraction/link order, PIC requirements and static
runtime behavior. Use one final Rust archive per component graph to avoid
accidentally bundling incompatible copies of runtime support.

Disable cross-language LTO initially. Ordinary native object linkage permits
Rust/LLVM objects to cooperate with the existing GCC or MSVC final link when the
target ABI matches. Cross-language LLVM bitcode optimization imposes extra version
and linker constraints, documented in the
[Rust LTO guide](https://doc.rust-lang.org/rustc/linker-plugin-lto.html).

One graph means one compatible target/configuration, not one set of object files
for Linux, Windows, Wasm and an MCU. A single wrapper command may orchestrate those
separate trees, but cannot remove their incompatible ABIs or qualification duties.

## Compilation and testing cost

Retain the existing [development-speed policy](development-speed.md), focused
prerequisite targets and complete disjoint [test planning](testing.md). Rust should
join those mechanisms rather than create a second default CI pipeline.

### Concurrency and incremental work

Extend `tools/build_capacity.py` so C++ compilation, Cargo/rustc code generation,
linking and test workers share CPU and memory limits. An outer Ninja `-j N` plus
an unconstrained inner Cargo `-j N` can exceed the intended budget. A Ninja pool
limits command count, not all threads launched inside a compiler.

For the baseline, start with one Rust build edge and Cargo `--jobs 1`, controlled
jobserver inheritance, and reserved capacity or a serialized Rust phase where
needed. Account for compiler/codegen threads as well as crate jobs. Preserve
parallel C++ compilation. Benchmark before adopting more complex jobserver
integration. CMake's explicit `JOB_SERVER_AWARE` support begins at 3.28 and is
ignored by Ninja, so it cannot solve the 3.24/Ninja baseline. See
[Rust jobserver guidance](https://doc.rust-lang.org/rustc/jobserver.html).

Do not assume `--jobs 1` overrides an inherited external jobserver. Qualify the
pinned Cargo's behavior and sanitize unowned jobserver advertisements in bounded
mode; a future shared-jobserver mode must deliberately inherit a verified budget.

Cache only as an acceleration: scope Cargo output to compiler hash, target,
profile, features, flags, source/lock identity and SDK. Do not share writable
Cargo target trees between independent agents or incompatible builds. Support
both an incremental development profile and a reproducible release profile.
Avoid many tiny crates, large generic expansions and procedural macro stacks until
actual build measurements justify them.

### Test selection

| Change or gate | Minimum useful scope |
| --- | --- |
| Rust algorithm only | Baseline-compiler unit tests, C ABI contract, fixed independent expected cases, C++/Rust differential corpus |
| C++ adapter or FFI header | Both providers' core/CLI tests, pointer/length/error contract, installed consumer |
| Shared GUI behavior | Existing shared GUI contract plus affected native/browser host; verify selected provider is actually linked |
| Backend adapter only | Existing backend-specific checks and shared contract; do not rebuild unrelated Rust SDKs |
| Build or SDK helper | Focused helper failures, clean/incremental behavior, wrong tool/target rejection and disconnected build |
| Compiler, CRT, target, ABI or dependency change | Affected target's full linkage, runtime, package, recovery and frontend qualification |
| Qualified release | Every shipped target/provider/backend and required package channel, exact-byte evidence and existing promotion gates |

Keep expected results independent of either implementation: agreement between two
implementations can reproduce the same mistake. Cover every input byte, boundary
lengths, null/zero conventions, overflow checks, state unchanged on rejection,
repeated calls and real C++ invocation. Do not deliberately dereference arbitrary
invalid pointers as an ordinary correctness test; that violates the caller contract.

Register Rust tests with CTest and the existing prerequisite map. Enumerate cases
and preserve nonzero failures, skipped scopes and zero-test errors. Do not let a
passing aggregate hide filtered-out Rust tests. Frozen shard inventories and merge
rules should include provider and Rust toolchain identity.

C++ sanitizers do not automatically instrument Rust. Stable baseline builds must
not claim full cross-language sanitizer coverage. Optional matching-toolchain
sanitizers, fuzzing and Miri can add diagnostic evidence where available; tools
requiring newer/nightly or additional suppliers are not default build prerequisites
and do not replace real foreign-caller tests.

### CI and release work reuse

Use `ci_changes.py` and `ci_plan.py` to select focused scopes, then reuse the
existing prepared-SDK, candidate and certification lifecycle. Build each selected
native provider once with all compatible native backends. Run backend tests against
those outputs rather than recompiling the core per host.

The default C++ route needs a clean lane where Rust tools and caches are absent.
Linux Rust needs the baseline compiler lane and native architecture coverage.
Windows/Wasm/MCU lanes enter only after their SDK experiments qualify. Routine
pull requests can use representative affected coverage; they cannot label that
subset complete release certification. Reuse evidence only when its relevant
source, flags, SDK, environment and case inventory still match.

Avoid publishing the full product of provider x architecture x backend x distro
package. Keep existing C++ distribution as the initial stable release and an
explicit Rust candidate where needed. If Rust becomes a normal provider for a
qualified target later, select one ordinary published provider there and retain
targeted C++ fallback regression coverage. Any additionally shipped provider
requires its own identity and applicable evidence.

Current `tools/release.py` and `tools/ci_plan.py` reject duplicate target entries.
Use one provider per target in a candidate initially, with a separate experimental
candidate when comparing providers. Supporting two provider variants for one target
inside a release would require deliberate manifest, artifact-name and policy changes.

Retain the project's GitHub-hosted runner preference and current
[CI storage policy](ci.md#storage-caches-and-sdk-reuse): bounded Actions artifacts
for routine handoffs, durable release storage for published inputs and outputs,
and draft transport only in its retained SDK/historical/selected legacy scopes.
Restore Rust from verified SDK groups; do not add a moving toolchain download
action to ordinary jobs. Hosted CI itself uses GitHub services, so its orchestration
is not an offline promise; the application build inside the prepared disconnected
boundary is. PRs must not trigger compiler SDK rebuilds merely because application
Rust changed.

## Distribution and runtime packages

Debian, Arch and Gentoo binary channels can continue wrapping the same certified
application payload. They need not compile Rust, install Cargo or contact a Rust
registry. Add Rust notices and any actual runtime closure to the existing package
inventory. A statically linked Rust component usually removes a separate Rust
shared-library installation requirement, but final dynamic imports remain subject
to audit.

Extend `build-info.txt` and release manifests with provider, Rust compiler/target,
profile/flags, lock digest and Rust SDK recipe identity. Bind these into source
replay, recovery and package verification. Separate variant names only when both
variants are intentionally distributed; never replace same-version payload bytes
or lose the identity while repackaging.

A source-based Gentoo ebuild or source package is a different offer from the
existing binary wrapper: it must declare compiler requirements and ship the full
offline Rust source closure. No post-install compilation or fetch hooks should
be introduced into existing binary channels. Signing, immutable payload URLs,
repository consistency, rollback protection and native package-manager checks
remain necessary regardless of implementation language. Preserve the existing
by-hash, atomic-service or tested bounded-retry choices; release assets alone do
not establish atomic multi-file index updates. See [release policy](releases.md).

## Arduino feasibility and integration

Apply the longstanding [selective porting intent](portability.md#arduino-as-a-selective-porting-target):
Arduino is a destination for selected application functionality, with useful
commonality retained so the example provides a starting point, including MFD
menus. Scope the Rust pilot to a component needed by such a port.

Arduino C++ compatibility does not automatically confer Rust compatibility. The
board selects its processor, ABI, C library, linker script, startup code, core,
upload tools and often a vendor compiler. A board's marketing name or the presence
of `extern "C"` says little about that complete closure.

The practical hybrid arrangement is:

```text
Arduino sketch and setup/loop in C++
                 |
      small C-compatible header
                 |
      precompiled Rust static library
                 |
       bounded safe computation

C++ retains board initialization, interrupts, drivers, Serial and allocation.
```

Use the same pure operation tested on desktop, with no heap, threads, filesystem,
network, retained callback or `std` requirement. For resource-bearing
features introduced later, use fixed-capacity storage and caller-provided buffers.
Keep interrupts and any critical-section protocol under one documented owner.
Avoid mandatory atomic operations, including assumptions about 64-bit atomics.

The current desktop `Store` uses dynamic strings/vectors and C++ exceptions; it
is not an Arduino library. Full store or GUI support would be a separate bounded
embedded API and memory-budget project. The pilot demonstrates reusable logic,
not seven GUI backends running on a small MCU.

### Board families

| Family | Rust integration outlook | Policy under the stated constraints |
| --- | --- | --- |
| SAMD21 Cortex-M0+ | Small Thumb no_std leaf is a sensible first pilot | Conditional on retained matching target core/compiler support and Arduino core/tool closure |
| RP2040 Cortex-M0+ | Similar CPU opportunity, different board startup/core/tooling | Second possible pilot; do not assume SAMD archive/recipe is automatically interchangeable |
| Cortex-M4/M7 boards; UNO R4 specifically uses Cortex-M4 | Potentially suitable, with exact FPU/float ABI and memory settings | Qualify each board/core profile; do not select hard-float merely from CPU capability |
| RISC-V Arduino-compatible boards | Some upstream bare-metal target support; extension/ABI/vendor SDK differences matter | Later per-board work, not a general compatibility promise |
| Classic AVR UNO/Nano/Mega | Current upstream Rust support needs special target/core preparation | Keep C++ by default; experimental maintained SDK only |
| Xtensa ESP32 variants | Vendor Rust/toolchain requirements differ from ordinary upstream target support | Outside initial distro-only profile; distinguish from RISC-V ESP32 variants |
| RP2350 | Select Cortex-M33 or Hazard3 RISC-V explicitly; board age alone does not determine compiler requirements | Separate board/architecture profile; verify compiler target/features and libraries before requiring a newer toolchain |

The exact board choice remains open until the producer can demonstrate all allowed
inputs. The first investigation should check SAMD21 target-library supply before
spending effort on a board demo. Compiler target recognition alone does not provide
a `libcore` archive. Distro ARM GCC packages likewise do not provide Rust target
libraries. Any custom core reconstruction must be explicit SDK maintenance and
must be proven possible with the retained compiler/source inputs.

Bookworm [rust-src](https://packages.debian.org/bookworm/rust-src) supplies source,
not compiled MCU libraries. Cargo's [build-std](https://doc.rust-lang.org/cargo/reference/unstable.html#build-std)
is an unstable nightly facility. `RUSTC_BOOTSTRAP=1` is not a supported stable
escape hatch for this baseline. Current [AVR target guidance](https://doc.rust-lang.org/rustc/platform-support/avr-none.html)
requires building core, selecting the MCU and using avr-gcc support. Current
[Xtensa target guidance](https://doc.rust-lang.org/rustc/platform-support/xtensa.html)
lists targets but directs users to an Xtensa-enabled compiler channel. These are
reasons for explicit toolchain profiles, not ordinary portable-build assumptions.

For board/ISA references, consult the [Rust ARM target guidance](https://doc.rust-lang.org/rustc/platform-support/arm-none-eabi.html),
[Arduino UNO R4 hardware](https://docs.arduino.cc/hardware/uno-r4-minima/),
[Raspberry Pi MCU documentation](https://www.raspberrypi.com/documentation/microcontrollers/pico-series.html)
and [Espressif Rust toolchains](https://docs.espressif.com/projects/rust/book/getting-started/toolchain.html).
These describe present targets and hardware, not measured Rust 1.63 compatibility.

### Arduino library and producer workflow

Arduino supports precompiled archives in architecture-specific library folders.
Its `precompiled=true` mode can combine source wrappers with archives; `full` mode
can bypass source compilation when a matching archive exists. CPU and float-ABI
directory selection is documented in the
[Arduino library specification](https://docs.arduino.cc/arduino-cli/library-specification).

Use a narrowly supported mixed library with a C/C++ wrapper and one verified Rust
archive for each accepted board recipe. Validate complete board/core/compiler/ABI
identity before selecting an archive; folder names alone do not express all of
it. Avoid `architectures=*` as a claim of Rust support. Missing requested Rust
archives must fail clearly. An explicitly selected C++ fallback can be supplied
as a separate profile rather than silently chosen by the builder.

Support two distinct user paths: sketch consumers can use a retained archive
without Rust installed; component developers rebuild that archive through the
project's offline SDK producer. Keep Cargo out of Arduino's automatic sketch
preprocessing. One wrapper command can coordinate the producer and Arduino CLI
for a selected board while preserving each tool's dependency graph.

Check the pinned [Arduino platform recipe](https://docs.arduino.cc/arduino-cli/platform-specification/)
actually forwards `compiler.libraries.ldflags` into its final link. Archive
support varies with builder/platform version; selecting the documented folder
layout alone does not prove that the archive reaches the final firmware.

Retain the Arduino core, platform/board definitions, headers, compiler/binutils,
upload utilities and licenses in addition to Rust. Board Manager caches and URLs
alone do not establish recovery. Do not run core or library installation during
an ordinary firmware build. Board packages unavailable from allowed suppliers
remain another explicit supply gap, even if the Rust function itself has no crates.

Inspect final ELF architecture/attributes, startup ownership, unresolved symbols,
archive ordering, section garbage collection, compiler-builtins/libgcc overlap,
stack/RAM/flash usage and panic behavior. Disable cross-language LTO initially;
GCC and Rust LLVM bitcode are not a common archive format for whole-program LTO.
No heap is not the same as bounded stack use. Exercise the actual board through
serial test vectors, repeated calls, boundary inputs and the selected reset/fault
path. Emulation and host tests are useful evidence but cannot qualify uploading,
startup, interrupts, timing or physical peripherals.

Record the exact FQBN (fully qualified board name), core and toolchain recipe,
`rustc -vV`, `rustc --print target-list`, selected target `--print cfg` output,
and matching target-library inventory. Keep the first RP2040 experiment on one
core; multicore synchronization would add a separate hardware contract.

## AI agent workflow and development benefit

Keep one owner for the C header, provider contract and SDK schema while parallel
agents implement the Rust component, C++ adapter, build integration and independent
tests in disjoint scopes. Agree on errors, ownership and identity before parallel
edits. Use existing coordination rules and private output trees; do not migrate
the coordination tools to Rust as part of this work.

Provide one short task entry point containing the minimum Rust version, forbidden
implicit downloads, FFI invariants and focused test command. Compiler diagnostics
and unit tests should be accessible through the existing wrapper. Agents should
not independently add convenience crates or broaden the target matrix.

The expected benefit is fewer memory/lifetime defects and more compiler feedback
inside sufficiently substantial Rust components. Token or elapsed-time savings
are hypotheses, not properties of the language. Track comparable tasks: time to
first passing change, compiler/test iterations, agent tokens when available,
review corrections, clean/incremental build time, binary size and peak memory.
Retain a small Rust surface only if those benefits justify its build/FFI burden.

## Implementation sequence and acceptance gates

The following phases are a future implementation plan. Commands/options and new
paths in this section are proposed. No compiler installation, CI dispatch, release
publication or extensive platform testing is part of this research change.

| Phase | Deliverable | Completion criterion |
| --- | --- | --- |
| 1 | Freeze private validation contract, provider names and source baseline | C++ behavior documented with independent expected cases; no public API change |
| 2 | Linux x86_64 Rust leaf and C++ adapter | Actual Rust 1.63 build; FFI/core/CLI parity; C++ build works with Rust absent |
| 3 | CMake/wrapper, installed package and Rust SDK inventory | Clean/incremental/multi-config tests; relocated C++ consumer needs no Rust tools; invalid SDK rejected |
| 4 | Bookworm offline and Linux aarch64 profiles | Fresh disconnected builds and applicable native runtime/ABI/GUI checks on both architectures |
| 5 | CI selection and release/package integration | Provider identity cannot disappear in artifacts; source replay/recovery and selected package gates pass |
| 6 | Windows MSVC and Emscripten experiments, independently | Each obtains an allowed complete SDK closure and passes its ABI/runtime/consumer/backend checks, or remains C++ |
| 7 | One Arduino board pilot | Rebuildable offline archive, complete board recipe, measured memory use and actual board tests |
| 8 | Evaluate expansion | Evidence shows enough safety/development value to justify another component; retain rollback and fallback coverage |

Phases 1-3 should remain small enough to review before platform expansion. Start
phase 6 supply investigations early because a missing compiler/target-library
source can stop those profiles regardless of application progress. Do not make
successful Linux adoption conditional on promising every future target.

### Repository changes to make later

| Existing or proposed path | Intended responsibility |
| --- | --- |
| `src/store.cpp`, proposed private header/adapter | Call selected validation provider, preserve current public behavior |
| Proposed `rust/` workspace | Safe component, narrow FFI, pinned manifest/lock, unit tests and profile policy |
| `CMakeLists.txt`, proposed `cmake/RustComponent.cmake` | Optional discovery, one Rust build edge, final linkage and CTest prerequisites |
| `cmake/FoundationConfig.cmake.in`, install fixtures | Install-relative archive requirements and consumer without Rust installed |
| `tools/build.py`, `tools/build_capacity.py` | Provider/config identity, controlled environment and shared resource budget |
| Proposed `tools/rust_build.py` | Baseline-compatible Cargo invocation, input checks, outputs and native linkage receipt |
| `tools/sdk_manifest.py`, `sdk_verify.py`, SDK producers and recipes | Optional Rust inventory, retained closures, preparation and replay |
| `tools/offline_inputs.json`, `offline_acceptance.py` | Declared Rust inputs and disconnected selected-provider acceptance |
| `tools/ci_changes.py`, `ci_plan.py`, `test_plan.py` | Focused scopes, test inventories and provider-aware evidence |
| `tools/release.py`, `release_check.py`, certification/package helpers | Provider/toolchain identity, exact archive and source recovery validation |
| GUI boundary guards and existing contract tests | Shared behavior and no toolkit coupling from new source paths |
| Proposed board example and embedded SDK recipe | Selected MCU library, source rebuild and hardware evidence |
| Existing build/SDK/portability/dependency docs | Update only when implementation and evidence support new claims |

Names are integration suggestions, not a requirement to create every file. Use
existing helpers where they can express the added contract without competing
inventories. Source-identity discovery must include Rust manifests, locks, source,
configuration and any retained inputs; verify that behavior instead of assuming it.

### Stop conditions and rollback

Keep a profile C++ when Rust would require an unapproved supplier, raise its host
or runtime floor, need nightly during normal builds, or lack a reproducible target
library closure. Fixing a source port does not waive these conditions. Retain the
old qualified SDK and immutable release while introducing a new recipe.

Within a qualified target, rollback selects the C++ provider and rebuilds through
its existing contract. It does not swap an archive in place or reuse evidence
from different binary bytes. A new feature intended to work on all retained targets
must have equivalent C++ behavior where Rust is unavailable; otherwise declare that
feature's narrower support explicitly before implementation.

## Evidence and remaining research

This document combines repository inspection with the linked official Rust, Linux,
Debian and Arduino sources. External documentation was consulted on 2026-10-04;
rolling pages describe current guidance, and should not be read as a Rust 1.63
feature list. Exact SDK production must use version-bound source and package data.

No hybrid binary has been built or benchmarked for this proposal. No Windows,
Wasm or board archive has been qualified. The existing
[pending offline platform record](../.agent-pending/offline-platform-qualification.md)
also records native ARM64/Windows disconnected-environment gaps for the current
C++ work; this proposal does not erase or satisfy those records.

The first implementation should resolve the selected no_std archive's actual
native symbol closure and old-toolchain behavior. Windows needs a justified
compiler/target-library supplier; Emscripten needs a matched target-library recipe;
the Arduino pilot needs an obtainable bare-metal core and board package closure.
These are concrete experiments with pass/fail criteria, not reasons to promise
universal support in advance.
