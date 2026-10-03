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
`--jobs N` remains an explicit override for both. Without a test override, the
resource detector admits up to four workers; smaller CPU/memory budgets reduce it.
Keep tests bounded for their
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

Source archives prune generated build, coordination and Python cache directories
before walking the tree. The complete selected source inventory and before/after
mutation checks still apply; only adjacent duplicate identity work is removed.

## Hosted scheduling

Leave compile limits at `auto` unless the machine has an explicit workload budget.
The hosted entry points use the same CPU/RAM detector as local builds. Select an
administrator-configured faster runner pool when available; platform-specific
allowlists preserve target architecture and trust boundaries. Independent jobs
have separate outputs and run concurrently within the configured job limit.

Development feedback uses an explicit safe list of narrative documents to omit
compile, GUI downloads and workflow syntax work for documentation-only changes.
Each existing parallel job selects its scope from local Git without API calls or
another serial runner. Missing history, changed policy/manuals and unknown paths
select full feedback. Complete candidate and release workflows remain unchanged
by this diagnostic selection. Each fresh copied-package check waits only for its
own target producer, while retaining a separate fresh runner.

Complete certification keeps every required logical result. Native source checks
share one build across the selected backends in that target/environment; recovery
is a separate reconstruction. Both use the build wrapper's resource-aware test
worker default independently of compiler parallelism. Archive qualification combines
member inventory with extraction or small metadata inspection; it does not extract
the complete application merely to read build information. Exact payload hashes,
safe member checks and before/after qualification validation remain required. Independent source, recovery, archive, ABI, browser
and package operations occupy 23 scope-separated batches, with up to eight running
concurrently in the complete all-GUI plan. Transport grouping follows required
inputs rather than forcing unrelated operations through one serial batch.

The complete Latest flow overlaps native regression with application producers.
Publication still requires successful regression. Assembly and publication share
one job so an executing release does not upload and download a complete temporary
candidate between those steps. Diagnostic preparation can still retain a private
candidate. Cold SDK maintenance uses explicit runner selection and the same
automatic compiler budget as ordinary application builds.

## Transfer only consumed inputs

Freeze the complete release inventory and delivery identity once. Each check
receives the exact source, application archive, SDK or browser harness it consumes.
Ordinary source consumers use the matching compiled SDK and checksum; recovery
receives the full retained binary/source/checksum group and verifies reconstruction
without the base release. Existing archived builders that require complete groups
retain that input contract; the frozen plan records `sdk_payload: complete`. Omitted
payloads remain identified by the frozen metadata,
and cannot be substituted or represented as executed coverage.

Certification preparation retains only authenticated frozen controls. Checks
fetch selected original candidate assets directly, verifying the complete frozen
release inventory and tag before and after transfer and hashing all selected
bytes before exposure. Preparation inspects the source archive for compatibility;
it no longer downloads and republishes every SDK and application payload through
private transport. Source and recovery still consume their complete declared inputs.

Publication verifies uploaded bytes. Later lifecycle steps reconcile the complete
remote asset inventory, immutable identities and SHA-256 digests, verify the
selected certificate and transfer the controls/evidence they actually consume.
A missing digest, changed identity or inconsistent inventory is a failure. Full
local assembly and recovery validation continue to require their complete inputs.
This avoids repeatedly downloading unchanged SDKs to record a result or move the
Latest pointer. Signed package-channel preparation consumes the complete retained
application once, then reuses its checked certificate and reconciles remote
identities. Publication uses those retained bytes; an identical published retry
checks the complete remote inventory without downloading every SDK again. A new
publication still reads every uploaded byte back before completion. After success,
private diagnostics retain signed controls and the publication receipt; they do
not upload a second complete public channel. A failed publication retains the
complete prepared bytes for reconciliation.

Native package installation verifies signed channel controls, all remote asset
identities and the complete selected native package channel. It does not repeat
compiler SDK recovery. An unchanged verified channel fetches only its signed controls and reuses its
exact active bytes; an upgrade reuses only matching immutable asset hashes. Failed refreshes
preserve the previous installation. Focused distro diagnostics run the selected
clients; complete acceptance still requires every declared client receipt.

Disposable Gentoo checks use bounded parallel package work and avoid durability
syncs for a container that will be discarded. These settings are scoped to that
verification container, not ordinary users' installed package-manager settings.

## Bound setup and evidence overhead

Use the retained SDK's compiler and tools for SDK consumers; fetch and verify its
binary archive and checksum without downloading reconstruction sources for every
producer. Assembly and recovery continue to require the complete group. Container
prerequisites follow the actual action and test scope, avoiding development
packages for archive or ABI-only checks.

Small same-run receipts and certification evidence use one-day Actions artifacts.
A complete bundle is capped at 2 MiB; 62 immutable slots cap each attempt at
124 MiB plus archive overhead. Oversized evidence and storage-service upload
failures fall back to complete release bundles. SDK and application payloads never
use this small-file allowance. Consumers share run/producer observations and
verify all local bytes; the [storage contract](ci.md#storage-caches-and-sdk-reuse)
explains retention, bounds and failure behavior.

Private release transport supports deterministic low-cost compression for text evidence,
while already-compressed package and SDK archives retain their ordinary encoding.
Consumers fetch up to four independent chunks concurrently and reconstruct them
in their authenticated order. Related bundles share complete run, producer and
asset inventories at the start and end of one transfer transaction. Check jobs
authenticate their controls, then fetch selected published candidate assets.
Candidate aggregation and certification evidence collection each fetch related
bundles together; application producers publish their output and diagnostics
together. Downloads remain quarantined until the final checks
pass, and publication writes manifest commit markers after all payloads verify.
This reduces repeated API reads as well as bytes. Source identities, completed
producer checks and whole-file hashes still apply. Keep actual network operations
bounded across nested callers and join every worker before cleanup on failure. Uploads use the already
validated release ID, avoiding another tag lookup for every asset. Even with
these reductions, a complete all-platform release may cross a shared API quota
window; grouped transfers do not create additional repository capacity.

Single-part bundles use a private staging rename instead of another complete
archive copy; whole-archive and member hash checks still run. Base SDK transfers
run concurrently within the network bound, with checksum publication after both
payload uploads finish. Reusing an unchanged published SDK reconciles the complete
asset IDs, sizes and digests against the verified local group without downloading
it again. First publication still downloads and validates the complete new group.

The [APT bootstrap helper](../tools/ci-apt.sh) preserves signed distribution sources
and uses bounded mirror/network recovery. Each installation refreshes strict
indexes; only recognized transient acquisition failures retry. Authentication,
hash, package-resolution and installation failures remain fatal. This policy is
for disposable CI bootstrap and qualification, and does not rewrite an ordinary
user's repositories through the application.

## Account for the actual critical path

Measure configure/build/test time separately from downloads, setup, evidence
transfer and publication. Parallel runner minutes and elapsed wall time are
different quantities. Record the source, configuration, selected scope and runner
when comparing measurements. Retained-input changes or a cold SDK rebuild are
separate costs, not normal application iteration. Native package qualification
writes `command-timings.json`, including failed commands, alongside its complete
command log. This separates dependency setup, install, repeated refresh and removal
costs instead of attributing the entire job to signing.

The lifecycle and transport CLIs emit sanitized per-process request metrics to
stderr: observed API responses (each pagination page), separate primary-unmetered
quota probes, CLI calls, transferred bytes, request-slot wait and retry wait.
These counters add no requests. CLI and wait seconds accumulate across workers;
they are not end-to-end wall time. Lost responses and legacy CLI uploads can make
observed response counts lower than actual API consumption. Use the accompanying
observed quota headers and job timestamps when accounting for a hosted run.
Direct candidate reads remove a large byte relay but still require independent
identity observations in each job. The current protocol therefore does not promise
a complete release within one repository quota window.

The bounded-evidence transport model estimates about 1,650 to 610 API calls for
the same full regression/application/certification transport shape, approximately
63% fewer. The combined certificate uses release fallback in this estimate.
Public release operations, retries, pagination and Actions storage-service calls
are additional costs. This is a structural estimate, not measured hosted time or
a guarantee against shared quota exhaustion. See [validation](validation.md) for
executed local checks and retained-model assumptions.

A native refresh still verifies the unified package-channel archive. Splitting it
into separately signed frontend projections would change the compatibility and
verification contracts; that further optimization is not implemented. First public
package-channel delivery also retains full source/SDK recovery bytes and verifies
their upload. These remain real transfer costs.

Use [testing](testing.md) for completeness rules, [CI](ci.md) for workflow inputs,
[certification](certification.md) for exact-byte checks and [distribution release](distribution-release.md)
for native channel acceptance. Actual observations and unexecuted platform limits
belong in [validation](validation.md); structural transfer reductions do not by
themselves establish a new hosted elapsed-time result.
