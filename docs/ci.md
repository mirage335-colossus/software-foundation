# Continuous integration and rapid feedback

CI should answer a development question quickly and make the remaining
qualification obvious. Keep one tested set of build helpers for local and
hosted use. A workflow should select environments, pass inputs, schedule work,
and retain evidence; substantive validation belongs in versioned helper code.

The executable workflow examples are in [`.github/workflows/`](../.github/workflows/).
They are starting points for a newly hosted repository. Local success does not
prove that hosted jobs, permissions, runner labels, or release settings have
been exercised.

## Three distinct scopes

| Scope | Trigger and intent | Meaning of success |
| --- | --- | --- |
| Focused feedback | PRs, small pushes, or `devfast=true` manual selection | The selected inexpensive scope passed |
| Candidate regression | Completed changes and `devfast=false` | Every configured required source/platform scope passed |
| Release qualification | Exact candidate artifacts and source | The planned target/feature inventory passed against those bytes |

For a small project, full local tests may already be cheap enough for each PR.
Keep that simpler arrangement until measured cost warrants splitting it. When
adding `devfast`, make the shortened scope and omitted gates visible in the job
name and summary. Default manual candidate runs to full coverage. Do not let a
diagnostic run produce a release-eligibility result.

An AI agent can choose a focused workflow during diagnosis and a permitted
faster runner when it will reduce elapsed time. It must then complete applicable
candidate gates and wait for their actual outcomes. A queued, cancelled, skipped,
or incomplete job is not successful validation. A manually skipped automatic
run leaves a documented outstanding gate until equivalent evidence exists.

## Workflow structure

Use reusable workflows for repeated platform setup and a small explicit matrix
for target/configuration differences. Pass typed, validated inputs. A release
matrix comes from one checked inventory; do not maintain divergent lists in
producer jobs, packaging helpers, verification, and documentation.

Independent source test shards and package producers should start together.
Copied-package tests depend on the package producer, not on an unrelated slow
test suite. A final aggregation job must require all applicable results,
including failed or missing producer jobs. Guard against `needs`/`if` logic
accidentally skipping the very job that detects incomplete coverage.

Use `fail-fast: false` when independent matrix outcomes are useful for diagnosis.
Use a concurrency group to cancel obsolete branch feedback; include enough
scope/configuration identity that a short diagnostic cannot cancel a required
candidate run. Serialize release mutation with cancellation disabled so an
interrupted job cannot leave two publishers racing over one draft.

Prevent duplicate push and PR runs for the same purpose. Use path filters only
when the dependency relationship is understood. A shared header, build helper,
dependency recipe, workflow, or test-selector change can affect more than the
directory containing it. A required branch check must still reach a conclusive
status when path selection excludes expensive work.

Typed inputs, matrices, permissions, reusable workflows, and concurrency are
defined in the [GitHub workflow syntax reference](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax).

## Select runners deliberately

Use stable, explicit standard runner labels as defaults and record the actual
image/toolchain versions used. `latest` is a moving image selection. Runner
architecture must match the planned execution target unless a separately
declared cross-build and execution arrangement is used.

Make faster runners an optional configuration: an administrator supplies a
small allowlist of available runner labels/groups, and a manual input chooses
among those entries. Validate the selection before scheduling expensive jobs.
Do not invent universal names for larger runners or silently route untrusted
jobs to privileged self-hosted infrastructure. Availability, access, quotas,
and billing belong to the repository's runner configuration. See GitHub's
[larger runner documentation](https://docs.github.com/en/actions/how-tos/manage-runners/larger-runners).

Before adding a larger runner, measure queue delay, setup, cold compilation,
incremental compilation, tests, artifact transfer, peak memory, total runner
minutes, and elapsed critical path. More CPUs will not speed up serial tests,
downloads, or jobs waiting on an unnecessary dependency. Set build jobs from
available resources and keep timing-sensitive test concurrency conservative.
Do not repeat successful qualification only to compare runner sizes unless that
measurement is itself requested work.

## Storage, caches, and SDK reuse

These examples use **no Actions artifact uploads**, including screenshots, SDKs,
packages and diagnostic bundles. This keeps inherited private repositories within
small account allowances; GitHub currently lists 500 MB of Actions artifact
storage for its Free plan. See [the current billing limits](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
A public origin does not establish an adequate quota for private downstream use.
Do not introduce `upload-artifact`, Actions artifact ZIP transport or an unbounded
cache as an alternative large-file store.

[`ci_transport.py`](../tools/ci_transport.py) stores trusted manual-run outputs in
one **draft, non-Latest release per run and attempt**. The tag is
`ci-RUN_ID-attempt-ATTEMPT`; its source and repository identity are fixed. Drafts
are authenticated transport, not published application releases or SDK base
qualification. Changing a draft into a public release breaks the transport
contract. The helper never publishes, overwrites assets, deletes storage or moves
Latest. Ordinary PR feedback stays read-only and retains bounded text in logs.

Each named bundle uses a complete regular-file inventory, a deterministic tar
stream split into at most 512 MiB assets, and a bounded JSON manifest uploaded
**last**. Every file, ordered chunk and complete stream has a size and digest.
Consumers verify the exact repository, workflow, source, run, attempt, completed
producer job, manifest asset ID/digest and all bytes before publishing a new local
output directory. The consumer rereads remote identities to detect replacement.
GitHub draft listings require push access; qualify the actual consumer token,
including fetch-only jobs, and grant access only to trusted manual workflows.
Independent bundles share a draft but own disjoint asset names. Only the publisher
that receives confirmed successful atomic tag creation may initialize the draft;
GitHub permits multiple drafts for one tag. Other publishers wait through bounded
reads. A preexisting tag without a visible draft or an uncertain creation response
requires inspection or a new run attempt, never another draft-creation request.
Interrupted uploads reconcile identical bytes; inconsistent partial state requires inspection,
not deletion or replacement. An explicitly retained failed SDK producer can supply
verified bytes to a fresh consumer; it never grants qualification.

Only small JSON pointers go into job outputs and summaries. A pointer is not the
payload or qualification evidence. Reusable workflows bind the actual outer run's
workflow identity, and callers keep the returned manifest identity when replaying
another run. A rerun's new attempt is a separate store; it cannot silently borrow
an older attempt's successful job. See [SDK retention](sdk.md#retain-complete-sdk-bytes-after-a-consumer-failure)
for explicit cross-run selection and legacy migration.

For existing repositories, [explicit legacy preservation](legacy-artifacts.md)
retains selected exact opaque archives and their provenance before separately
reviewed cleanup. Its separate `verify-retention.yml` consumer reads every retained
byte back and checkpoints small receipts before releasing each archive from runner
disk. Neither workflow deletes originals or grants qualification.

Release transport avoids Actions artifact quota; it still consumes transfer,
runner disk and service resources. Budget bundle counts, bytes and retention.
Review draft inventories periodically. Delete only specifically approved expired
stores after confirming that no release, SDK replay or evidence record depends on
them. Preserve referenced inputs in durable base or release-owned copies first.
Never delete unknown drafts, active attempts or the sole surviving evidence.
Respect GitHub's [release asset API](https://docs.github.com/en/rest/releases/assets)
limits. Large files and SDKs never enter Git history.

An optional compiler cache may accelerate builds. Key it by OS, architecture,
compiler/runtime, configuration and dependency identity; bound its total size and
expiry separately. A cache miss or corruption must not weaken checks. Never cache
credentials or exchange configured build trees between runners: absolute paths,
compiler state, generator state and timestamps can invalidate results. Rebuild
inexpensive targets or transport finished verified archives.

Prepared SDKs and dependency bundles use durable storage with exact identities.
Routine jobs fetch and verify them. Missing recipes fail early with an explicit
maintenance instruction. SDK compilation belongs in a separately dispatched
maintenance workflow, with [source preservation and relocation checks](sdk.md).
Every binary release retains exact SDK binary/source/checksum copies; transport
storage and base availability are not substitutes for those copies.

## Credentials and untrusted input

Set workflow permissions to read-only by default. Grant write permission only
to the narrow publication job that needs it. Pin third-party actions to reviewed
full commit identifiers and annotate the intended release for maintainers.
Automate reviewed updates to those pins. Avoid persisted checkout credentials
when later steps do not need repository writes.

Keep event-derived text out of inline shell code. Pass it through environment
variables or structured helper arguments, validate the accepted grammar, and
quote shell expansions. Do not print tokens or signing material. Do not run
untrusted PR source with release credentials or in a privileged target-context
workflow. Protect publishing environments and runner groups according to the
repository's trust boundary. These precautions follow GitHub's
[secure use reference](https://docs.github.com/en/actions/reference/security/secure-use).

Use bounded setup retries for transient infrastructure failures, retaining the
error and attempt count. Install from the chosen supported package sources;
do not silently rewrite system package configuration or lower verification
requirements to make a job pass.

## Grouped qualification work

The current all-GUI policy retains every required backend row. Its native source
and recovery commands each build/test the complete delivered backend inventory;
ABI checks audit the complete native archive. These rows presently repeat some
identical work. Do not delete mandatory rows or relabel one backend's receipt as
another backend to reduce that cost.

A future grouped executor may share one immutable execution only when source,
release inventory, dependency bytes, build configuration, actual execution
platform, scope and required backend inventory are identical. It must record the
complete covered backend set and actual test inventory, preserve any required
per-backend assertions, and bind every projected backend result to that same
execution and its real run/attempt. Certification and merge validation must reject
missing backend coverage, changed inputs, different environments and reuse across
source/recovery scopes. Add those evidence-schema checks and negative fixtures
before consolidating policy rows; current required coverage remains unchanged.

## Windows graphics execution input

Native GUI checks use the [pinned external graphics prerequisite](windows-graphics.md)
on the declared Windows runner. The compiler SDK contains development dependencies;
the test runtime stays in a separate owned input directory. SDK maintenance
explicitly fetches its reviewed supplier archive. Ordinary `native-gui.yml` and
Windows GUI certification require `graphics_archive_url`, an operator-retained
HTTPS archive location. There is no automatic fallback to a live supplier URL.
The helper checks the pinned size and digest, rejects credentials and insecure
redirects, and keeps transient redirect query values out of receipts and logs.
Linux checks do not use this input.

Build GUI prerequisites in one configured tree, then stage the verified runtime
beside the native probe and GUI test executables. The selected compiler builds
the probe; the bounded process owner executes it and verifies the loaded module
paths, actual renderer and required graphics capabilities. Run the normal complete
GUI tests in that environment, preserving their real captures and checks. Only
after all child writers stop may staging remove its own runtime files. Uncertain
termination retains them and fails qualification. Packaging uses a clean runtime
state and never receives these test DLLs.

The workflows retain the graphics receipt, probe result, build/test diagnostics,
and actual visual capture evidence (`.json`, `.png`, `.ppm`, `.log`). The successful
GUI qualification receipt binds the capture and graphics receipt digests. The
archive, extracted DLLs, probe executable, GUI source and application executables
are excluded from those uploads. Maintainers must separately retain allowed
supplier inputs, source and notices and review redistribution terms before
operating an archive mirror. Qualification demonstrates the tested software
rendering environment; physical display and device checks remain separate.

## Evidence and maintenance

Every job should retain exact source revision, toolchain/dependency identities,
selected test inventory, command, exit status, machine-readable outcomes, and
timings. Include run ID and attempt. Aggregation follows
[the completeness rules](testing.md#inventory-driven-parallel-work).
If a rerun legitimately reuses earlier successful jobs, record their actual
originating attempts instead of relabeling them as newly executed.

Test workflow helpers locally with small fixtures for invalid inputs, empty
selections, missing result files, duplicate inventory entries, and interrupted
operations. Validate workflow syntax with an available maintained validator.
Treat hosted acceptance as an additional required check after local validation,
and periodically review runner images, action pins, timeouts, cache size,
retention, permissions, and obsolete matrix entries.


## Executable hosted lifecycle

Use the workflow revision itself as the packaging revision. All mutation jobs
checkout the same immutable `github.sha` as their read-only preparation jobs,
use the protected `release-publisher` environment, and share
`foundation-release-lifecycle` with cancellation disabled. Set that environment's
required reviewers and allowed branches before authorizing publication. Workflow
files cannot create those repository settings. The default `execute=false`
produces reviewable plans and may create private draft transport releases. It does
not publish application/base assets or change Latest. Trusted transport producers
need narrowly scoped `contents: write`; untrusted PR jobs do not receive it.

| Workflow | Inputs and resulting contract |
| --- | --- |
| `_release-latest.yml` | The [Latest entry point](latest-release.md) invokes full regression, prepared-SDK application production, exact-byte certification and final promotion verification. Missing base recipes fail before work; preparation remains distinct from publication. |
| `screenshots.yml` | The [screenshot workflow](screenshots.md) builds all seven hosts from exact existing SDKs, captures fresh initial views, retains the complete image gallery in a draft bundle, and optionally publishes a non-Latest gallery. Explicit retained-input recovery is separate from normal base selection. |
| `sdk-import.yml` | Explicitly verify selected legacy SDK group/proof ZIPs and their original producer, preserve complete evidence, then emit draft bundles and the exact version-2 replay request. No cold build, certification or deletion. |
| `candidate.yml` | `devfast=false`, `include_arm=true` verifies independent Windows x64, Linux x64 and Linux ARM64 source scopes, native packages, fresh copies and actual signed APT installation/upgrade/rejection/removal in disposable Debian. It uses host toolchains and does not claim the older SDK baseline. |
| `sdk-maintenance.yml` | Select one target or `all`, the `core` or `all-gui` dependency profile, a bounded compile job count, and optionally `execute=true`. Select `source=auto` to verify and reuse the exact existing group, `base` to require it, or `rebuild` for explicit production. Linux producers run as an unprivileged account in Debian 12 on matching architecture; Windows selects its separate installed compiler and records provenance; Wasm retains its compiler and Node runtime. An always-run retention check verifies the selected current recipe and complete binary/source/checksum triplet before retaining reusable bytes, even after a consumer failure; its receipt is explicitly unqualified and grants no publication approval. Publication still requires successful relocated SDK, application, package and installed-consumer checks. The GUI profile additionally requires all selected GUI backend checks. |
| `gui-inputs.yml` | Explicitly acquire the pinned supplier checkout, export and verify a complete retained GUI group. Upload the group only when its verified redistribution metadata allows it; otherwise retain only the inspection plan. Optional execution appends an eligible group to base. |
| `native-gui.yml` | Explicit maintenance/qualification on native Windows x64, Linux x64 or Linux ARM64. Fetch an exact GUI-capable SDK, acquire the pinned GUI inputs, and run all native backends. Windows also requires the explicit retained host graphics URL. Upload only test evidence; source and binaries remain runner-local. |
| `sdk-application.yml` | Supply `profile` and a JSON `recipes` object mapping every profile target to its exact 64-character recipe. Freeze one source archive, independently restore each existing dependency group and build/test/package on its target, then assemble a complete candidate. Optional execution publishes without selecting Latest. |
| `certify.yml` | Supply candidate `tag`, exact `release.json` `inventory` digest and policy `profile`. Download and revalidate remote identities, derive all checks from the support policy, execute independent exact-byte checks, retain every report and optionally append a new certificate attempt. |
| `promote.yml` | Supply the same candidate identity, policy profile, exact certification run/attempt and certificate JSON digest. The explicit mutation job revalidates the remote certificate, policy and asset IDs before setting Latest and verifying the resulting pointer. |

For example, `core` currently requires these recipe-map keys; replace each value
with a produced, verified recipe identity before dispatch:

```json
{
  "linux-x86_64": "<exact-64-character-recipe>",
  "linux-aarch64": "<exact-64-character-recipe>",
  "windows-x86_64": "<exact-64-character-recipe>"
}
```

The `all-gui` profile also requires `browser-wasm32` and `gui_group`, the exact
retained GUI manifest digest. Ordinary jobs fetch that complete group from base
and freeze its verified restored source into the application archive. They never
clone upstream or silently perform maintenance. Use SDK groups from the explicit
GUI-capable native recipes; the producer checks the required capability list. Publication preparation
fails early while redistribution terms remain unresolved; source-group inspection
and local development remain available. Native GUI dependency headers and libraries
must be present in each prepared target sysroot/export. Host libraries cannot
satisfy a missing target dependency. Browsers used for qualification come from the
execution environment, not from the compiler SDK.

Linux certification executes each declared baseline in a disposable container on
its native runner architecture. APT checks additionally require the explicit
disposable-runtime marker; never invoke that scope on a development host. Container
success establishes that user-space environment on the hosted kernel, not every
physical system. Browser setup validates the actual distribution, package and CPU
architecture, root Docker marker and explicit disposable-runtime flag before
changing package configuration. Debian browser checks use its distribution packages.
Ubuntu 24.04 hosted-web archive checks install Firefox from [Mozilla's official APT repository](https://support.mozilla.org/en-US/kb/install-firefox-linux):
the complete primary signing-key fingerprint must match the reviewed constant,
`Signed-By` scopes that key, and package-origin preferences exclude Ubuntu's Snap
transition. The chosen version must come from Mozilla's HTTPS origin before its
explicit version is installed; the harness uses `/usr/bin/firefox`. Both native
architectures keep their real Ubuntu runtime and browser assertions. Browsers are
external execution prerequisites and never enter the compiler SDK.

A separate `browser-prerequisite-<check>-<attempt>` draft bundle records the plan/check,
run/attempt, actual package versions and architecture, package policy and browser
version. Setup initially retains this receipt outside the qualification output directory,
which the checked runner must create afresh. After actual browser assertions, the
qualification helper validates and copies the receipt into its browser evidence
and binds its digest to the report. Browser setup applies only to hosted-web
archive checks and Wasm source/recovery/archive checks. Setup failure remains a failed job;
a package receipt alone is not browser qualification. Actual interactive assertions
and their bound reports remain required. Windows source and copied-archive checks use the recorded native
compiler and SDK, and the actual Windows runner image is checked by the certifier.

All steps obtain event-derived data through environment variables and argument
arrays. Package discovery excludes CPack's private staging tree; copied-package
validation rejects duplicate public names. Toolchain setup exports only compiler
variables and retains its selected versions without copying unrelated inherited
values into later step environments. Per-suite JSON and CTest failure logs are
uploaded even when the source shard fails.

Draft transport bundles identify the actual run and attempt. Rerunning only failed
jobs does not relabel earlier evidence: use a complete new attempt or explicitly
select and verify prior origins. Failure before a report exists leaves
certification incomplete. Complete failed reports can be retained and attached as
a new certificate attempt; they never permit promotion.

The local helpers and offline transport scenarios validate scheduling and
identity contracts. `actionlint` checks workflow syntax and expressions. Actual
runner setup, GitHub permissions, SDK compilation and service behavior require
successful jobs on the exact integrated commit. Inspect all mandatory jobs and
retained internal outcomes before reporting success; a successful feedback job
alone does not establish Windows or release qualification.

The GUI base adapter stores `gui-<manifest-digest>-inputs.tar.gz`,
`gui-<manifest-digest>-manifest.json` and `gui-<manifest-digest>-SHA256SUMS`. It
reconstructs their original names locally before complete group verification.
SDK and GUI groups coexist in base; adding one preserves every existing asset
ID and never advances Latest. Missing, partial, changed or inaccessible groups
stop ordinary consumers. Source-group maintenance retains only a non-source inspection plan when terms
are unresolved. Public release upload is redistribution too: unresolved source
groups and their binaries must not enter public releases, even when a separate
transport operation succeeds. The source-group workflow retains only its inspection
plan while its terms remain unresolved. An
execution request fails clearly instead of silently skipping this gate.

`source=auto` authorizes cold production only inside explicit SDK maintenance,
after a successful complete remote inventory proves that the base or recipe is
absent. A partial group, orphan tag, changed asset, malformed response, access
failure or network failure must be repaired; none becomes permission to rebuild.
The receipt distinguishes reuse, missing base, missing recipe and explicit rebuild.
Ordinary application workflows remain base-only. Rebuilding an existing recipe
never grants permission to replace its assets; publication checks identical bytes
or rejects the conflict.

The SDK maintenance GUI probe runs before base publication, so a first GUI-capable
SDK can be qualified without a preexisting base. `native-gui.yml` repeats that
qualification using an already retained group. Both acquire the supplier revision
only as explicitly dispatched maintenance, run source checks locally, and leave
unresolved source and binaries on the disposable runner. These results do not
certify redistribution or a complete release. Windows GUI qualification requires its actual native job and all internal tests
to pass on the exact revision; observed executions are recorded in [validation](validation.md). The ordinary candidate workflow verifies the core application only.

Cold Linux producers use an owning unprivileged account; never bypass supplier
root-user rejection. Root package-manager checks run only in explicitly disposable
containers. Any container Git trust exception names only its mounted checkout and
is written only to the container account, never the developer or runner host.
