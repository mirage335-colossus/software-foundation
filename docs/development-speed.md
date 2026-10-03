# Fast development and complete qualification

Use the smallest scope that can answer the current development question. Reserve
complete platform and release qualification for a finished candidate. A diagnostic
pass identifies its selected scope and cannot make a release eligible.

## Local iteration

```sh
./build.sh
./build.sh test dev --label core
./build.sh test dev --label tools
./build.sh test dev --label gui --gui-input-group /absolute/retained-gui-inputs
./build.sh test release --full
```

Compilation automatically uses the available CPU and memory budget. Explicit
`--build-jobs N` overrides it; `--test-jobs N` controls test concurrency separately.
`--jobs N` remains an explicit override for both. Keep tests bounded for their
actual memory, process and real-time requirements. A faster machine alone does
not justify changing an assertion or deadline.

CMake owns one native graph: the core and shared GUI libraries compile once and
all selected hosts link them. Reuse the same configuration for incremental edits.
Different target architectures, SDK identities and sanitizer configurations use
separate trees. Optional compiler caching remains an optimization, not a required
supplier or a substitute for verifying the selected source and toolchain.

The build wrapper can configure without compiling. Candidate scopes then compile
only their declared prerequisites. The complete generated test declarations,
configuration and source identity remain frozen so an unbuilt executable from a
different scope does not hide a new test or change the aggregation identity.

## Hosted scheduling

Leave compile limits at `auto` unless the machine has an explicit workload budget.
The hosted entry points use the same CPU/RAM detector as local builds. Select an
administrator-configured faster runner pool when available; platform-specific
allowlists preserve target architecture and trust boundaries. Independent jobs
have separate outputs and run concurrently within the configured job limit.

Complete certification keeps every required logical result. Native source checks
share one build across the selected backends in that target/environment; recovery
is a separate reconstruction. Independent source, recovery, archive, ABI, browser
and package operations occupy 23 scope-separated batches, with up to eight running
concurrently in the complete all-GUI plan. Transport grouping follows required
inputs rather than forcing unrelated operations through one serial batch.

## Transfer only consumed inputs

Freeze the complete release inventory and delivery identity once. Each check
receives the exact source, application archive, SDK or browser harness it consumes.
Ordinary source consumers use the matching compiled SDK and checksum; recovery
receives the full retained binary/source/checksum group and verifies reconstruction
without the base release. Existing archived builders that require complete groups
retain that input contract; the frozen plan records `sdk_payload: complete`. Omitted
payloads remain identified by the frozen metadata,
and cannot be substituted or represented as executed coverage.

Publication verifies uploaded bytes. Later lifecycle steps reconcile the complete
remote asset inventory, immutable identities and SHA-256 digests, verify the
selected certificate and transfer the controls/evidence they actually consume.
A missing digest, changed identity or inconsistent inventory is a failure. Full
local assembly and recovery validation continue to require their complete inputs.
This avoids repeatedly downloading unchanged SDKs to record a result or move the
Latest pointer.

Native package installation verifies signed channel controls, all remote asset
identities and the complete selected native package channel. It does not repeat
compiler SDK recovery. An unchanged verified channel fetches only its signed controls and reuses its
exact active bytes; an upgrade reuses only matching immutable asset hashes. Failed refreshes
preserve the previous installation. Focused distro diagnostics run the selected
clients; complete acceptance still requires every declared client receipt.

Disposable Gentoo checks use bounded parallel package work and avoid durability
syncs for a container that will be discarded. These settings are scoped to that
verification container, not ordinary users' installed package-manager settings.

## Account for the actual critical path

Measure configure/build/test time separately from downloads, setup, evidence
transfer and publication. Parallel runner minutes and elapsed wall time are
different quantities. Record the source, configuration, selected scope and runner
when comparing measurements. Retained-input changes or a cold SDK rebuild are
separate costs, not normal application iteration.

Use [testing](testing.md) for completeness rules, [CI](ci.md) for workflow inputs,
[certification](certification.md) for exact-byte checks and [distribution release](distribution-release.md)
for native channel acceptance. Actual observations and unexecuted platform limits
belong in [validation](validation.md); structural transfer reductions do not by
themselves establish a new hosted elapsed-time result.
