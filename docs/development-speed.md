# Fast development and complete qualification

Use the smallest scope that can answer the current development question. Reserve
complete platform and release qualification for a finished candidate. A diagnostic
pass identifies its selected scope and cannot make a release eligible.

## Local iteration

```sh
./build.sh
./build.sh test dev --label core
./build.sh test dev --label tools
./build.sh test dev --label gui --gui
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
only their declared prerequisites. The per-test prerequisite registry also makes
ordinary local shards selective: planning requires no compilation, and running a
shard builds only its own targets. Local core-labelled tests no longer compile
unrelated GUI hosts; candidate core coverage still includes the configured GUI
checks. The complete generated test declarations,
configuration and source identity remain frozen so an unbuilt executable from a
different scope does not hide a new test or change the aggregation identity.

Source archives prune generated build, coordination and Python cache directories
before walking the tree. The complete selected source inventory and before/after
mutation checks still apply; only adjacent duplicate identity work is removed.
A plain build uses its post-compilation source observation as its final one;
testing and packaging keep a separate observation after those operations.
Candidate test planning reads CTest declarations once per phase and shares that
observation across inventory, prerequisite and configuration binding. It still
observes the declarations afresh after compilation and after tests; it does not
cache evidence across a mutation boundary.

Retained GUI verification streams file contents in bounded chunks while computing
SHA-256 and the upstream Git blob identity together. It retains digest records,
not every expanded source file. Compressed group files are hashed once per guarded
observation; file identity/version reconciliation still rejects inputs changed
during verification. Restore also checks the complete existing output inventory
before reuse. There is no persistent trust cache or bypass for a warm checkout.

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
by this diagnostic selection. Ordinary Linux GUI feedback consumes the retained
checkout input through `--gui`, without a repository-variable gate or release API
lookup. Each fresh copied-package check waits only for its
own target producer, while retaining a separate fresh runner.

Complete certification keeps every required logical result. Native source checks
share one build across the selected backends in that target/environment; recovery
is a separate reconstruction. Both use the build wrapper's resource-aware test
worker default independently of compiler parallelism. Archive qualification combines
member inventory with extraction or small metadata inspection; it does not extract
the complete application merely to read build information. Exact payload hashes,
safe member checks and before/after qualification validation remain required. Independent source, recovery, archive, ABI, browser
and package operations occupy 23 scope-separated batches, all eligible to run
concurrently by default in the complete all-GUI plan. The optional repository
variable `FOUNDATION_CERTIFICATION_JOBS` lowers the job limit for constrained pools;
unset or `0` uses the full planned batch count. Actual concurrency still depends
on runner/account capacity. Transport grouping follows required
inputs rather than forcing unrelated operations through one serial batch.

The complete Latest flow overlaps native regression with application producers.
Publication still requires successful regression. Assembly and publication share
one job so an executing release does not upload and download a complete temporary
candidate between those steps. Diagnostic preparation can still retain a private
candidate. Cold SDK maintenance uses explicit runner selection and the same
automatic compiler budget as ordinary application builds.

Certification retries can adopt authenticated, successful whole batches from a
prior attempt while executing incomplete batches again. Original controls and
evidence retain their original attempt identity; the new attempt cannot relabel
or overwrite them. See [the retry contract](certification.md) for the exact
checks and failure rules.

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
fetch selected original candidate assets directly. Their authenticated same-run
manifest supplies pinned IDs, locations, sizes and hashes; each consumer hashes
all selected bytes before exposure without rediscovering the complete release.
Final publication stages reconcile the remote inventory and tag. Preparation inspects the source archive for compatibility;
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

Routine same-run source, package, receipt and certificate transfers use native
Actions artifacts. Their finite slot budgets total at most 370 MiB per attempt;
the complete certificate can use a 16 MiB slot. Producer/consumer REST provenance
queries are replaced by the exact executing Actions context, immutable names,
workflow dependencies and explicit outcomes. Complete local hash and safe archive
validation remain. SDK archives stay in release storage.

The final consumer deletes only larger handoffs after its verification succeeds;
small receipts and diagnostics expire after one day. Published copies replace
source/application and certificate handoffs; regression packages need only their
fresh-package check. Select `preserve_artifacts=true` to disable early deletion,
including nested workflows. Failed consumers and preparation-only source/application
outputs keep one-day retention. Native failures are explicit; the costly private
release fallback requires deliberate opt-in. See the [storage contract](ci.md#storage-caches-and-sdk-reuse).

Historical cross-run and explicitly requested private release transport retain
strict remote producer verification, bounded parallel downloads and deterministic
low-cost compression. Routine same-run handoffs no longer take that path.
Certification planning freezes the public inventory once, distributes its small
controls through Actions, and consumers download only their selected published
assets. Each consumer verifies the source context, pinned size and hash before
using the bytes. Publication, attachment, promotion and independent final
verification retain their remote boundary checks.

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
The earlier bounded-evidence design modeled about 610 transport REST calls and
750–1,150 for the full public application release. Native handoffs now remove the
routine relay and its producer queries; shared certification discovery removes
repeated remote snapshots. In the retained 23-batch shape, 69 control-provenance
reads and 161 repeated candidate metadata reads disappear; 87 payload acquisitions
use public download URLs instead of authenticated REST requests when the repository
is public. File transfers and local verification still occur.

The complete public all-GUI application release using already-published SDKs models
**189 quota-counted REST operations**, or **180** with `preserve_artifacts=true`.
The retained shape has 23 initial public assets and 53 temporary artifacts:

| Stage | Modeled REST operations |
| --- | ---: |
| Initial preflight | 9 |
| Candidate regression handoffs | 0 |
| GUI inputs, four build SDK fetches and one assembly SDK batch | 42 |
| Candidate publication and complete draft readback | 66 |
| Certification planning and certificate attachment | 22 |
| Promotion planning and promotion | 22 |
| Independent Latest verification | 19 |
| Cleanup: nine direct-ID deletions, no listing | 9 |
| **Total** | **189** |

This is a code-derived estimate, about **75–84% below** the previous full-release
range, not a hosted measurement or guaranteed ceiling. It assumes public assets,
one-page inventories and successful first attempts. Assembly shares one in-process
base-release inventory across its four SDK recipes and performs one fresh final
reconciliation, reducing their metadata reads from 28 to seven. Every SDK payload
is still verified and downloads retain bounded parallelism. Each completed SDK
starts verification while other SDKs continue downloading, using separate pools
of at most four transfer workers and four verification workers. All writers join
before cleanup, and no output becomes available until every verification and the
fresh remote reconciliation pass. No cross-job artifact,
persistent cache or extra upload is introduced.

Write headroom normally uses quota headers from existing API responses. A bounded
fallback probe covers missing, stale or exhausted observations; other jobs can
consume quota between any observation and the next request. The previous model
had about 29 separate quota probes, which do not consume the primary core quota.
That remains a conservative allowance when usable headers are unavailable, rather
than an unconditional cost. Actual probe counts depend on responses and elapsed
time; response reuse removes most routine probes, not a guaranteed fixed number.
Actions artifact-service calls and public file downloads remain network work.
Four Windows graphics consumers add eight REST operations if configured with
an authenticated release-asset URL instead of a direct public URL. Private
repositories retain approximately 127 authenticated downloads, bringing the
comparable total to about 316 before that graphics adjustment. Cold SDK publication,
optional distribution workflows, additional assets, retries, visibility polling
and pagination cost more.

Early deletion replaces the previous 54-call sweep with nine direct-ID calls:
one source, four applications, three regression packages and one certificate.
Small receipts and diagnostics (44 artifacts in this shape) simply expire. The
five-item publication cleanup adds four seconds of deliberate mutation spacing,
plus request latency. The other four deletions are single-item operations at their
own final consumers. Independent jobs remain parallel, and the extra cleanup
runners and final 52-second deletion sequence are gone. Preservation disables all
nine deletions, reducing the estimate to 180. No cleanup waits for an hourly quota
reset. This reduces cleanup calls by about 83% and the immediately preceding
255-call release estimate to 210 (about 18%); the shared assembly inventory
then removes a further 21 calls to reach 189.

For occasional repository-wide reclamation, run the
[manual artifact cleanup workflow](ci.md#manual-artifact-cleanup) between builds.
It freezes all current artifact IDs, performs five active-run checks and deletes
that snapshot one artifact per request. Its cost is separate from routine release
accounting; it never runs automatically after development work.

One day is the [minimum automatic artifact retention](https://github.com/actions/upload-artifact/blob/v4.6.2/action.yml);
shorter lifetimes require explicit deletion. The maximum allowed content across
all 79 slots is 370 MiB per attempt, plus small outer archive overhead; ordinary
runs use fewer slots and bytes. Early deletion shortens archive storage duration,
but retained receipts and concurrent attempts can still accumulate storage.

GitHub documents a normal `GITHUB_TOKEN` limit of
[1,000 requests per hour per repository](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api#primary-rate-limit-for-github_token-in-github-actions)
and recommends [spacing mutations and avoiding unnecessary polling](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api).
The new public release estimate uses about a fifth of that hourly allowance;
other runs share it. Record actual response counters and elapsed time on the next
ordinary hosted run; do not launch duplicate releases merely to measure the
optimization. See [validation](validation.md) for executed checks and limitations.

A native refresh still verifies the unified package-channel archive. Splitting it
into separately signed frontend projections would change the compatibility and
verification contracts; that further optimization is not implemented. First public
package-channel delivery also retains full source/SDK recovery bytes and verifies
their upload. These remain real transfer costs.

The [portable qualification commands](certification.md#file-based-commands-for-another-ci-or-a-local-scheduler)
separate local planning, prerequisite setup and supervised execution from the
provider adapter. They require no GitHub metadata requests once inputs are local.
This preserves the all-GUI plan's 106 logical checks, 66 physical executions and
23 hosted batches, as well as grouped builds, selective SDK transfers and bounded
parallel downloads. It introduces no additional artifact, worker or persistent
cache. Timings, console logs, JUnit, prerequisite evidence and exact input checks
remain available for diagnosis by developers and agents. Existing hosted producer
checks and certification-before-promotion ordering remain in the provider adapter.

This portability extraction does not remove publication or transport operations:
the complete public release model remains 189 quota-counted requests (180 with
preservation). It does not establish a further hosted elapsed-time improvement.
An alternative CI scheduler can reuse these commands without implementing GitHub's
artifact and release API, while retaining the same evidence and parallel work.

Use [testing](testing.md) for completeness rules, [CI](ci.md) for workflow inputs,
[certification](certification.md) for exact-byte checks and [distribution release](distribution-release.md)
for native channel acceptance. Actual observations and unexecuted platform limits
belong in [validation](validation.md); structural transfer reductions do not by
themselves establish a new hosted elapsed-time result.

## Focused supplier diagnostics and retry reuse

Before a compiler or Rev update triggers a complete graphics build, use the
[small actual-module diagnostic](../tests/rev_style_probe/README.md). It consumes
verified retained GUI inputs, compiles four production modules, and executes the
comparison/layout regressions without acquiring dependencies or opening a display.
Its result is diagnostic evidence, not GUI or release qualification.

An unchanged frozen qualification plan can explicitly [adopt successful results
from an earlier attempt](certification.md#explicit-prior-attempt-adoption).
Original receipts, attempts, host identities and evidence remain intact. Bare
mixed-attempt aggregation still fails. Hosted artifact acquisition does not
implicitly trust earlier attempts; a scheduler must authenticate the selected
producer and supply the exact retained files before using the adoption commands.

A single slow suite can eventually use internal case/seed partitioning and original
raw-result aggregation as described in [testing](testing.md). Add that mechanism
only when current timings justify it. Existing CTest-level parallelism remains the
default; no cases, statistical gates or real-time deadlines are weakened.

## Exact local checks and infrastructure feedback

Use `./build.sh test dev --test core.store` (repeat `--test` for multiple names)
when one registered contract discriminates the issue. Fixture dependencies and
compiled prerequisites are resolved from the same configured CTest graph; no
second miniature project is created. Broaden to the affected full label and normal
candidate coverage after the fix. Automatic changed-infrastructure feedback uses
whole suites and conservative dependency closure; it is independent of local
core/GUI feedback and cannot substitute for required release coverage.

`./build.sh portable-package` is the deliberate Release + portable runtime +
relocated archive/installed-consumer verification operation. It does not add
packaging or full regression work to ordinary builds. Native SDK runtime output
checks hash only the selected executable/private closure during incremental
validation, while the existing shared SDK input guard retains full-input authority.
