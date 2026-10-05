# Continuous integration and rapid feedback

CI should answer a development question quickly and make the remaining
qualification obvious. Keep one tested set of build helpers for local and
hosted use. A workflow should select environments, pass inputs, schedule work,
and retain evidence; substantive validation belongs in versioned helper code.

The executable workflow examples are in [`.github/workflows/`](../.github/workflows/).
They are starting points for a newly hosted repository. Local success does not
prove that hosted jobs, permissions, runner labels, or release settings have
been exercised.

Application workflow entry points default `core_provider` to `rust`, with an
explicit `cpp` compatibility choice. Linux development feedback declares its
distribution `rustc`/Cargo setup and selects the actual package tools; it also
runs an explicit Rust-free C++ smoke check. Candidate native release and ASan
jobs prepare pinned official host Rust inputs in a separate setup step before
application compilation. SDK application, native GUI, screenshot and Latest
consumers instead require exact already-retained Rust triplets matched to their
C++ target groups. SDK maintenance explicitly prepares and retains those groups
before consumer qualification. Missing groups fail clearly. Tool acquisition
belongs to declared workflow preparation, never normal configure/build/test/package.

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

For a host-specific Python contract failure, use the manual
[Host contract diagnostics workflow](../.github/workflows/host-contracts.yml). It
selects an already installed interpreter and repeats one complete suite without
rebuilding SDKs or applications. Every failure remains visible; later successful
repetitions cannot erase it. See [the diagnostic contract](testing.md#focused-host-diagnostics)
for runtime selection, bounded supervision and retained evidence.

## Complete candidate inventories

Each candidate source job freezes the complete configured CTest inventory and its
source, compiler, retained-input and configuration identities. The `tools` and
`integration` labels assign those disjoint scopes; every other registered test,
including an unlabelled new test, belongs to `core`. An empty or overlapping scope
fails planning. All three frozen plans must agree before aggregation can pass.
A `devfast` run executes only core and records the omitted scopes as diagnostic.

The candidate retains exact JUnit outcomes plus each Python suite's individual
case receipt. Aggregation rejects missing scopes, changed plans, missing or
skipped tests, altered JUnit, and incomplete inner-case inventories. The generated
`test-platform.json` records suites unsupported on that actual platform, while
inner receipts identify case-level exclusions. An optional suite that was never
enabled is not a platform exclusion or claimed coverage.

Push and PR feedback uses the `fast` label, including the core application,
documentation, build scheduling and dependency-free GUI boundary, source-group
and visual-comparison fixtures. These fixtures run without fetching a GUI supplier
or SDK. They catch helper and abstraction contract regressions; they do not replace
actual toolkit, display, browser or installed-package qualification. The ordinary
candidate still builds the core application; dispatched GUI qualification executes
the selected real backends with complete prepared inputs.

The development feedback workflow always starts and keeps its focused and
workflow-syntax check names conclusive. A local Git selector omits compilation,
GUI input downloads and workflow lint only when every changed path belongs to
its explicit list of non-installed narrative documents. It still checks document
links and JSON. Installed instructions, manuals, release policy, build scripts,
workflows, unknown paths, unavailable history and malformed events select full
feedback. PR selection compares the tested merge against its verified base
parent; moves include both old and new paths. No GitHub API listing or history
fetch is needed. Each existing job repeats only the cheap local selector, so
independent feedback jobs keep starting in parallel without a new setup barrier.
Candidate regression and certification never use this selector.

A separate automatic **Affected complete infrastructure suites** job selects
whole tooling suites using conservative source-reference dependencies and explicit
coupled domains. A shared, unknown, deleted or workflow input falls back to the
complete inventory. It runs at most two suites concurrently through the strict
case-outcome runner and process-tree owner, with individual deadlines and retained
receipts. Skips, orphaned writers, missing cases and timeouts cannot count as passes.
This protects SDK/release/coordination tooling on ordinary PR/main feedback without
forcing its complete suites into each local core iteration.

## Workflow structure

Use reusable workflows for repeated platform setup and a small explicit matrix
for target/configuration differences. Pass typed, validated inputs. A release
matrix comes from one checked inventory; do not maintain divergent lists in
producer jobs, packaging helpers, verification, and documentation.

Independent source test shards and package producers should start together.
Each target calls a reusable package workflow whose copied-package job depends
only on that target's producer. Each consumer still starts on a fresh runner;
it does not wait for other target packages or an unrelated slow test suite. A
final aggregation job must require all applicable results,
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

The manual candidate's `linux_pool=faster` input applies the configured per-target
allowlist: `FOUNDATION_FAST_LINUX_RUNNER`, `FOUNDATION_FAST_ARM_RUNNER` and
`FOUNDATION_FAST_WINDOWS_RUNNER`. Accepted labels start with `foundation-linux-`,
`foundation-arm-` and `foundation-windows-` respectively. Unconfigured targets keep
the standard runner; requesting faster mode with no configured target fails.
These variables are operator configuration, not executable event input. Actual
host checks still reject a wrong operating system or architecture.

The same validated pool selection is exposed by Latest, prepared-SDK application
production, SDK maintenance, native GUI and screenshot workflows. `jobs=auto`
uses each producer's available CPUs and RAM; a positive override remains explicit.
Feedback and sanitizer compilation also use automatic capacity while test
concurrency stays at two. Two independent distribution fixture suites can run
concurrently on their existing runner, retain separate complete receipts and
join before the required distribution gate. No package assertion is omitted.

Latest requests full candidate regression inside the SDK application workflow.
Regression and platform production start independently; assembly requires both
to succeed. The outer regression job verifies that nested result and never
runs a second candidate workflow. Failed, cancelled, skipped and missing nested
results prevent publication and certification. A standalone SDK application run
can explicitly enable this gate with `require_regression=true`.

Executed candidates assemble and publish in the same protected publisher job,
using the existing complete local validation and exact remote readback. This
avoids storing and downloading the full assembled candidate between jobs.
Preparation-only runs retain candidate controls for inspection; their source and
application archives already have separate handoffs, and SDKs remain in release
storage. Executed runs retain delivery receipts. Complete assembly dependency
verification remains required.

Before adding a larger runner, measure queue delay, setup, cold compilation,
incremental compilation, tests, artifact transfer, peak memory, total runner
minutes, and elapsed critical path. More CPUs will not speed up serial tests,
downloads, or jobs waiting on an unnecessary dependency. Set build jobs from
available resources and keep timing-sensitive test concurrency conservative.
Do not repeat successful qualification only to compare runner sizes unless that
measurement is itself requested work.

## Storage, caches, and SDK reuse

Routine source, application-package, regression and certification handoffs use
[bounded Actions artifacts](../tools/ci_artifacts.py). Durable public SDKs and
published application/certification assets use release storage. Small handoffs no
longer create private releases or re-query producer jobs through REST.

Each native artifact contains a complete hashed archive and manifest. There are
79 immutable slots per run attempt, with **378 MiB maximum combined content**
across their individual budgets, plus ZIP metadata overhead. Ordinary receipts
and individual check batches allow 2 MiB; source, application and native package
slots allow 16 MiB; complete certificates allow 24 MiB; application diagnostic
slots allow 8 MiB. Native file manifests allow 2 MiB within each slot's total
budget. The optional SDK-free candidate slot allows 64 MiB. SDK archives are
excluded. These are ceilings, not reserved storage or expected consumption. A
complete Rust all-GUI certificate handoff measured 23,500,974 bytes (about
22.4 MiB), including its 1,470,211-byte manifest and all 6,016 retained files.
Bound browser fixtures and screenshots remain part of the complete evidence.

Consumers download only the relevant slots from their exact executing Actions
run. Immutable artifact names and explicit workflow `needs` establish producer
ordering; the manifest records the observed producer outcome and this trust basis,
without claiming an independently queried numeric job identity. Consumers verify
repository, source, workflow, run, attempt, complete file inventory, sizes and hashes
before exposing bytes. Successful consumers require successful producers; the
certificate collector explicitly accepts failed check evidence while the final
qualification gate still rejects failed, skipped or incomplete required jobs.
Parallel jobs and all required logical checks remain.

Artifacts have **one-day retention**, GitHub's minimum automatic lifetime.
Large handoffs are deleted sooner at their final successful consumer:

| Handoff | Early deletion point |
| --- | --- |
| Source and application archives | Candidate publication and complete readback have succeeded; every producer and assembly consumer has finished |
| Certificate bundle | Public certificate attachment and readback have succeeded |
| Regression package archive | That target's fresh-package verification has succeeded; no release copy is required |

Small controls, receipts and diagnostics expire automatically. Preparation-only
source/application outputs and failed-consumer handoffs also keep their one-day
lifetime. A later failure can occur after an earlier handoff has been removed;
published copies and diagnostics remain available. `preserve_artifacts=true`
disables early deletion and is forwarded through nested release, regression and
package workflows. Promotion only produces small receipts, which always expire.

Cleanup uses exact upload IDs passed through workflow outputs and `needs`, with
no artifact listing. Distinct application matrix output names keep every target's
ID; assembly validates a complete map for its actual core or all-GUI inventory
before deletion. No missing ID causes a repository search or broader cleanup.
The complete all-GUI release deletes nine archives, leaving its 44 smaller artifacts
to expire. Each cleanup step is best-effort, limited to one minute, and never waits
for quota headroom or retries a mutation. There is no final sweep or extra cleanup
runner. Workflow history, unrelated artifacts and release assets remain intact.
Concurrent runs and preexisting artifacts still share the account allowance.

Unknown slots, oversize bundles and failed uploads fail visibly without silently
starting the expensive release relay. The composite actions expose an explicit
`allow-release-fallback` option for exceptional callers; routine workflows do not
enable it. No files are truncated. See [GitHub artifact retention](https://docs.github.com/en/actions/tutorials/store-and-share-data)
and [storage billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

[`ci_transport.py`](../tools/ci_transport.py) retains its legacy draft-release
protocol for explicitly retained SDK groups, historical replay and deliberately selected legacy bundles. Preparation-only
application runs retain candidate controls as native artifacts; their source and
application components already have separate handoffs, and SDKs remain public assets. The tag remains
`ci-RUN_ID-attempt-ATTEMPT`; draft transport is separate from public base and product
publication. Ordinary PR feedback stays read-only. Routine native handoffs use the
artifact path above, while public certificates retain their evidence independently
of that temporary copy.

Each named bundle uses a complete regular-file inventory, a deterministic tar
stream split into at most 512 MiB assets, and a bounded JSON manifest uploaded
**last**. Every file, ordered chunk and complete stream has a size and digest.
Release-bundle consumers verify the exact repository, workflow, source, run, attempt, completed
producer job, manifest asset ID/digest and all bytes before publishing a new local
output directory. The consumer rereads remote identities to detect replacement. Exact same-run
transfers share invariant workflow observations and pin the release ID after
discovery; historical cross-run reads retain the stricter original checks.
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
API requests are another shared budget. A standard workflow token has a
[1,000-request hourly repository limit](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api#primary-rate-limit-for-github_token-in-github-actions),
independent of release storage and runner concurrency. Count paginated inventory
reads, authenticated chunk downloads, provenance rechecks, upload lookups and
readback, including final aggregation. More runners cannot increase that quota.
Keep focused development checks small; complete release qualification still needs
its declared coverage. Group setup and transport where the tested identities agree.
Rate waits preserve required assertions; they do not turn unavailable work green.
The native artifact path removes the per-bundle release protocol and repeated
run/job lookups. Public payloads use credential-free release download URLs with
pinned sizes and hashes; private repositories keep authenticated asset downloads.
Certification preparation freezes a context-bound asset manifest once. Same-run
checks use that authenticated manifest and verify their selected bytes locally;
attachment and promotion still reconcile the complete remote identity. Historical
or unbound acquisition retains the strict independent remote checks. Artifact and
public download services still perform HTTP operations; fewer REST calls do not
mean zero transfers or unlimited service capacity.

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

## Manual artifact cleanup

Use **Actions → Delete temporary artifacts → Run workflow** to reclaim all current
Actions artifact storage for this repository. The manual-only
[cleanup workflow](../.github/workflows/cleanup-artifacts.yml) has no required
inputs and creates no artifacts of its own. It deletes Actions artifacts from all
runs, including diagnostics retained by `preserve_artifacts=true`; it preserves
workflow history, normal workflow logs, releases and SDK release assets.

Run it between builds and keep the repository idle until it finishes. Before any
deletion, the helper freezes the complete paginated artifact ID/size inventory,
then checks `requested`, `pending`, `waiting`, `queued` and `in_progress` workflow
runs. Any other active run aborts cleanup. This is a point-in-time guard, not a lock
on future workflow starts; artifacts uploaded after the frozen inventory are not
selected. Missing or inconsistent inventory data, or more than 10,000 artifacts,
fails before deletion.

The job summary reports selected and confirmed deleted counts and bytes. Deletes
are sequential, one second apart. An API error, expiration race or exhausted
quota stops the operation with partial progress; it does not retry a mutation or
wait for an hourly reset. The helper stops starting deletes after 25 minutes to
leave time for its final summary before the 30-minute job timeout. Progress is
also printed every 100 confirmed deletions. A later manual run can remove
anything remaining. An empty repository succeeds without deletion.

For `N > 0` artifacts, the normal request count is approximately
`N + ceil(N / 100) + 5`: one DELETE per artifact, one listing GET per 100 artifacts,
and five idle-check GETs. Thus 44 artifacts cost about 50 requests, and 440 cost
about 450. The five guard reads replace per-artifact producer/run lookups. Large
backlogs can exceed the available workflow-token quota and need another manual
run after capacity is available. This operation is optional maintenance; ordinary
builds retain their existing early deletion and one-day expiry policy.

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

The all-GUI policy retains **106 logical checks**, executed as **66 physical
operations**. A native source check builds and tests the complete delivered
backend inventory once per target/environment; recovery independently rebuilds
that same inventory from retained inputs. Each Linux ABI operation audits its
complete archive once. Native archive execution and package-manager checks remain
separate for each backend. Browser source and recovery operations remain distinct
for each required engine.

The workflow places those unchanged operations into **23 CI batches**, selected
by runner, container image, target, environment and scope. By default all planned
batches are eligible to run concurrently, subject to available runners and account
limits. Set the repository Actions variable `FOUNDATION_CERTIFICATION_JOBS` to a
positive integer from 1 to 256 to cap concurrent certification batches for a
constrained runner pool. Unset or `0` selects the actual batch count; a larger
value cannot add jobs. Invalid values fail before fetching candidate inputs.
The setting applies to both direct certification and the full Latest workflow's
reusable certification call. It does not change compiler/test concurrency,
coverage, artifact slots or request counts. Source and recovery remain independent. Each
batch downloads the frozen control bundle once and only the source, archive or SDK
components consumed by its checks. Recovery receives complete retained SDK groups;
ordinary source checks receive the compiled SDK and its complete checksum binding.
Transport names remain bounded and collision-checked. Each case keeps its original
identity, evidence directory and disposable environment. A failed case does not
suppress independent later cases, but any failure makes the batch fail.

Transport retains the complete tree of case directories in one evidence bundle
per batch. Aggregation restores each disjoint batch once and requires every
original logical result. The full frozen input map is retained even where a job
fetches only selected payloads; those actual bytes are checked before and after
execution. Scope separation increases the number of transport bundles while
reducing elapsed serialization and repeated large downloads. Measure API requests,
bytes and runner setup separately when tuning grouping.

The workflow gives each batch a 240-minute safety allowance, including quota waits.
Each case retains its separate 90-minute cap. These limits are failure bounds,
not expected durations. Exhausting a deadline leaves qualification incomplete.

A frozen `execution` group may share only identical source, release inventory,
dependency bytes, command, configuration, target, actual environment and scope.
Its receipt records the complete covered backend set, logical check IDs, actual
host, run and attempt, and all executed tests. After child writers stop, the
executor creates a separate logical result and qualification receipt for every
member, all bound to the same retained `execution.json`, logs and assertion bytes.
Every file remains in the physical leader's evidence directory and one complete
transport bundle; the certificate resolves each logical result there.

Aggregation rejects missing or differing backend coverage, inconsistent projected
receipts, another run/attempt, altered evidence, and reuse across source/recovery
scopes. The certifier additionally requires a group's backend set to equal the
entire delivered target inventory. A failed operation projects failure to every
member. This reduces repeated work without turning one backend-only execution
into claimed coverage for another backend.

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

Early failures may precede every test or graphics output. The application and
native GUI diagnostic selections therefore include the lifecycle's existing,
immutable `build/receipts/failure.json`. Explicit process-ownership and timeout
failures retain their original exception and traceback after the receipt is
written. The selections preserve that bounded receipt even when no downstream
output exists. Bundle paths follow the selected declarations'
common root, including declarations that match no file. A failed
application or native GUI selection uses `build` as its root: the receipt appears
as `receipts/failure.json`, even without downstream files; application evidence
appears beside it under `produced/`, and native GUI evidence under `native-gui/`. The receipt declaration is conditional on
failure, so successful runs retain their existing evidence layout. Inspect the
verified manifest when recovering failed evidence. Never substitute a recursive
build-tree upload or read mutable output beneath an uncertain writer. The failure
receipt grants no qualification or publication eligibility.

## Retained workflow validator

The automatic workflow syntax job requires actionlint 1.7.12. It first uses an
explicit `FOUNDATION_ACTIONLINT_EXECUTABLE` or installed `actionlint`. Otherwise
`FOUNDATION_ACTIONLINT_URL` must identify an operator-retained HTTPS copy of the
exact reviewed Linux x64 archive; its digest is fixed in
[`ci_plan.py`](../tools/ci_plan.py). Redirects must stay HTTPS, credentials in URLs
are rejected, transfer size is bounded, and the executable is extracted only
after digest verification. Missing configuration fails the mandatory check; there
is no implicit upstream download or skip.

Bootstrap the retained input through explicit maintenance: verify the pinned
archive, retain corresponding source, license and notices in durable release
storage, then configure its immutable URL. A GitHub hosted runner image's installed
tool is also acceptable when its version is verified. The lint receipt records
executable and workflow digests, and changes during execution invalidate it.
Lint and inexpensive source feedback use no release write credentials or Actions
artifact storage.

### Explicit validator mirror bootstrap

This is an operator maintenance procedure, never part of a PR or routine check.
Use a new owned directory and a new release tag. Set `REPOSITORY` to the destination
`owner/repository`, `PACKAGING_COMMIT` to its exact reviewed commit, and
`SUPPLIER_COMMIT` / `SOURCE_SHA256` to the independently reviewed actionlint 1.7.12
source revision and archive digest. Inspect the retained license and notices before
publication. Keep the source archive opaque rather than extracting an unchecked
tree. The binary archive's fixed digest is checked independently below.

```sh
set -eu
: "${REPOSITORY:?}" "${PACKAGING_COMMIT:?}" "${SUPPLIER_COMMIT:?}" "${SOURCE_SHA256:?}"
export REPOSITORY PACKAGING_COMMIT SUPPLIER_COMMIT SOURCE_SHA256
mkdir build/ci-tool-bootstrap
cd build/ci-tool-bootstrap
curl --fail --location --proto '=https' --proto-redir '=https' \
  https://github.com/rhysd/actionlint/releases/download/v1.7.12/actionlint_1.7.12_linux_amd64.tar.gz \
  --output actionlint_1.7.12_linux_amd64.tar.gz
curl --fail --location --proto '=https' --proto-redir '=https' \
  "https://github.com/rhysd/actionlint/archive/$SUPPLIER_COMMIT.tar.gz" \
  --output actionlint-source.tar.gz
python3 - <<'PYCODE'
import hashlib, json, os, pathlib, tarfile
p = pathlib.Path('.')
binary = p / 'actionlint_1.7.12_linux_amd64.tar.gz'
source = p / 'actionlint-source.tar.gz'
expected = {'actionlint_1.7.12_linux_amd64.tar.gz':
    '8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8',
    'actionlint-source.tar.gz': os.environ['SOURCE_SHA256']}
for name, digest in expected.items():
    if hashlib.sha256((p / name).read_bytes()).hexdigest() != digest:
        raise SystemExit('input digest differs: ' + name)
with tarfile.open(source) as archive:
    root = 'actionlint-' + os.environ['SUPPLIER_COMMIT']
    files = [x for x in archive if x.name in (root+'/LICENSE', root+'/LICENSE.txt')]
    if len(files) != 1 or not files[0].isfile() or files[0].size > 131072:
        raise SystemExit('review one bounded ordinary supplier license')
    (p / 'LICENSE.actionlint').write_bytes(archive.extractfile(files[0]).read())
(p / 'provenance.json').write_text(json.dumps({'version':'1.7.12',
    'supplier_commit':os.environ['SUPPLIER_COMMIT'], 'inputs':expected},indent=2)+'\n')
paths = [binary, source, p / 'LICENSE.actionlint', p / 'provenance.json']
(p / 'SHA256SUMS').write_text(''.join(hashlib.sha256(x.read_bytes()).hexdigest()+
    '  '+x.name+'\n' for x in paths))
PYCODE
```

Review that input inventory and license before executing the following publication
steps. This is a separate non-Latest tools release; application candidates and SDK
bases remain unchanged. Atomic tag creation must succeed for this attempt before
creating a draft. An existing tag, failed response or interrupted attempt requires
inspection and reconciliation; do not rerun draft creation, overwrite assets or
delete prior inputs to force success.

```sh
TOOL_TAG=ci-tools-actionlint-1.7.12
export TOOL_TAG
# Only confirmed success from this request authorizes the next create command.
gh api --method POST "repos/$REPOSITORY/git/refs" \
  -f "ref=refs/tags/$TOOL_TAG" -f "sha=$PACKAGING_COMMIT"
gh release create "$TOOL_TAG" --repo "$REPOSITORY" --verify-tag \
  --draft --prerelease --latest=false --title 'CI tools: actionlint 1.7.12' \
  --notes 'Reviewed immutable validator binary, source, license and provenance.'
gh release upload "$TOOL_TAG" --repo "$REPOSITORY" \
  actionlint_1.7.12_linux_amd64.tar.gz actionlint-source.tar.gz \
  LICENSE.actionlint provenance.json SHA256SUMS
mkdir readback
gh release download "$TOOL_TAG" --repo "$REPOSITORY" --dir readback
cmp SHA256SUMS readback/SHA256SUMS
(cd readback && sha256sum --check SHA256SUMS)
# Confirm the draft inventory contains exactly the five reviewed asset names,
# its tag still names PACKAGING_COMMIT, and every read-back check passed.
gh release edit "$TOOL_TAG" --repo "$REPOSITORY" --draft=false --prerelease --latest=false
gh variable set FOUNDATION_ACTIONLINT_URL --repo "$REPOSITORY" \
  --body "https://github.com/$REPOSITORY/releases/download/$TOOL_TAG/actionlint_1.7.12_linux_amd64.tar.gz"
```

The final routine check verifies the fixed archive digest again before using it.
Do not mirror a different binary under that name or update this tag in place; a
validator upgrade changes the reviewed source, notices, digest and version gate
as one change, followed by an independently named retained release.

## Evidence and maintenance

Every job should retain exact source revision, toolchain/dependency identities,
selected test inventory, command, exit status, machine-readable outcomes, and
timings. Include run ID and attempt. Aggregation follows
[the completeness rules](testing.md#inventory-driven-parallel-work).
This release aggregator requires a single complete run and attempt. A rerun cannot
borrow earlier successful checks or relabel them as newly executed; retained SDK
input replay is a separate operation that preserves its actual originating attempt.

Test workflow helpers locally with small fixtures for invalid inputs, empty
selections, missing result files, duplicate inventory entries, and interrupted
operations. Validate workflow syntax with an available maintained validator.
Treat hosted acceptance as an additional required check after local validation,
and periodically review runner images, action pins, timeouts, cache size,
retention, permissions, and obsolete matrix entries.


<a id="optional-rust-qualification"></a>

## Rust Qualification

[`rust-qualification.yml`](../.github/workflows/rust-qualification.yml) selects
four explicit lanes: native Linux x86_64, native Linux aarch64, native Windows
x86_64 and browser wasm32. It runs on `codex/rust-*` branch pushes and manual
dispatches. Rust is now the application default, while explicitly selected C++
feedback remains independent of Rust discovery and input preparation. The matrix binds an exact all-GUI C++ SDK recipe and matching
Rust producer recipe for each target; every lane records the actual source
commit, complete retained groups and selected configuration.

Its explicit preparation step fetches existing retained C++ groups and acquires
only recipe-pinned official Rust supplier archives before preparing the separate
extension. Later application, source-input replay and recovery steps consume
retained bytes. Ordinary application builds never fetch tools or crates.
Missing inputs and mismatched recipe/target identities fail without a supplier
or provider fallback. Compiler reconstruction from source is not a workflow gate
or claimed result; replay reassembles original retained compiler packages.

The implemented gates include complete configured source tests, package/installed
consumers, all applicable native backend checks, real browser checks and retained
recovery evidence. Linux lanes use their matching Bookworm architecture for the
application and a separate network-denied source-input replay and disconnected
acceptance. Windows adds native Debug/static-CRT consumer checks and a bounded
disconnected core/consumer/package check under an owned, disposable hosted
firewall boundary; that latter scope does not claim full offline GUI regression.
The Wasm lane uses the exact retained Rust/Emscripten tuple and separate real
Firefox/Chromium evidence. Browsers remain validation host prerequisites.

Always-run retention uses the existing run-scoped draft `bundle-store` transport
for available application archives, receipts, case inventories, browser evidence
and failure diagnostics. Once the recovery kit exists, the bundle also retains
its exact SDK/source input bytes. An earlier failed run may retain preparation
inventories and diagnostics without a complete input kit. A retained draft or
preparation receipt is not a target pass. The final verdict requires every planned
lane to succeed; cancelled, failed or incomplete jobs do not satisfy it. No stable
application release, base/Latest change or distro-channel promotion is performed
by this workflow.
[Run 37211392657](https://github.com/mirage335-colossus/software-foundation/actions/runs/37211392657)
at `41d28fec5481c77fc5b20e20808405ff3f83707a` completed all four producers and
the verdict successfully under the earlier explicit-Rust configuration policy.
That result does not relabel later default-policy edits as the same tested source.
[Validation](validation.md#optional-rust-qualification-2026-10-04)
records the executed scope, exact immutable pointers and evidence basis:
authenticated completed-job/run contexts, complete console logs and successful
fail-closed gates. Final small manifests were SHA-verified locally; the complete
payloads remain remotely retained, without local full-payload readback or an
accepted bundle claim. Earlier full-byte readbacks, local checks and failed or
cancelled attempts retain their original identities. A successful lane in a
failed matrix is not the complete four-target verdict. Windows checks reuse
selected Microsoft host tools; they do not prove installation or reinstallation
from retained installer media.

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
| `cleanup-artifacts.yml` | Manual deletion of the frozen Actions-artifact inventory after checking that other workflows are idle. Reports count and bytes; preserves run history and all release assets. |
| `_release-latest.yml` | The [Latest entry point](latest-release.md) invokes full regression, prepared-SDK application production, exact-byte certification and final promotion verification. Missing base recipes fail before work; preparation remains distinct from publication. |
| `screenshots.yml` | The [screenshot workflow](screenshots.md) builds all seven hosts from exact existing SDKs and a separately selected complete GUI source group, captures fresh initial views, retains the complete image gallery in a draft bundle, and optionally publishes a non-Latest gallery. Explicit retained-input recovery is separate from normal base selection. |
| `legacy-artifacts.yml` / `verify-retention.yml` | Preserve an explicit original archive selection privately, then independently read every byte back with exact producer identities and durable per-archive receipts. Neither workflow deletes originals or grants SDK qualification. |
| `sdk-import.yml` | Explicitly verify selected legacy SDK group/proof ZIPs and their original producer, preserve complete evidence, then emit draft bundles and the exact version-2 replay request. No cold build, certification or deletion. |
| `candidate.yml` | `devfast=false`, `include_arm=true` verifies independent Windows x64, Linux x64 and Linux ARM64 source scopes, native packages, fresh copies and actual signed APT installation/upgrade/rejection/removal in disposable Debian. It uses host toolchains and does not claim the older SDK baseline. |
| `sdk-maintenance.yml` | Select one target or `all`, the `core` or `all-gui` dependency profile, a bounded compile job count, and optionally `execute=true`. Select `source=auto` to verify and reuse the exact existing group, `base` to require it, or `rebuild` for explicit production. Linux producers run as an unprivileged account in Debian 12 on matching architecture; Windows selects its separate installed compiler and records provenance; Wasm retains its compiler and Node runtime. An always-run retention check verifies the selected current recipe and complete binary/source/checksum triplet before retaining reusable bytes, even after a consumer failure; its receipt is explicitly unqualified and grants no publication approval. Publication still requires successful relocated SDK, application, package and installed-consumer checks. The GUI profile additionally requires all selected GUI backend checks. |
| `gui-inputs.yml` | Explicitly acquire the pinned supplier checkout, export and verify a complete retained GUI group. Retain the complete group and inspection plan privately for exact future reuse, independently of SDK recipes. Public base publication still requires verified redistribution metadata and explicit execution. Normal capture consumes a selected existing group; it never silently clones a replacement. |
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

Linux certification executes declared package and source baselines in disposable
containers on matching native architecture. APT checks additionally require the
explicit disposable-runtime marker; never invoke that scope on a development
host. Container success establishes that user-space environment on the hosted
kernel, not every physical system.

Debian browser checks install its ordinary distribution packages only after
checking the actual distribution, architecture, root Docker marker and explicit
disposable-runtime flag. Ubuntu 24.04 hosted-web archive checks instead run on the
actual Ubuntu runner and inspect its existing `/usr/bin/firefox`. The helper
resolves the selected launcher to a supported native ELF executable, verifies its
architecture and matching launcher/native version, and records both file digests.
It neither adds a package repository nor installs a replacement browser. A missing,
ambiguous or unsupported prerequisite fails that lane. Both architectures retain
real Ubuntu browser assertions. Browsers remain external execution prerequisites
and never enter the compiler SDK.

A separate `browser-prerequisite-<batch>-<attempt>` draft bundle retains distinct
per-check receipts from `build/prerequisites/`. Each receipt records the plan/check,
run/attempt, actual package or inspected executable identity, architecture, origin
and browser version. Setup initially retains each receipt outside the qualification output directory,
which the checked runner must create afresh. After actual browser assertions, the
qualification helper validates and copies the receipt into its browser evidence
and binds its digest to the report. For an inspected host browser, executable
digests are rechecked after the actual browser assertions. Browser setup applies only to hosted-web
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
qualification using an already retained group. Both consume an exact existing GUI
group without supplier acquisition. Only `gui-inputs.yml` performs explicit source
maintenance. These results do not
certify redistribution or a complete release. Windows GUI qualification requires its actual native job and all internal tests
to pass on the exact revision; observed executions are recorded in [validation](validation.md). The ordinary candidate workflow verifies the core application only.

Cold Linux producers use an owning unprivileged account; never bypass supplier
root-user rejection. Root package-manager checks run only in explicitly disposable
containers. Any container Git trust exception names only its mounted checkout and
is written only to the container account, never the developer or runner host.

### Fast shared GUI execution

After publishing the reviewed GUI group into `base`, set repository variable
`FOUNDATION_GUI_GROUP` to its exact manifest digest. The `shared-gui` feedback job
then restores that group from this repository and compiles the shared application
once for terminal, framebuffer and hosted-web checks. It exercises real shared
feature/task behavior, renderer contracts, PTY and loopback paths without a target
SDK or native toolkit build. It never clones the GUI supplier. A missing variable
leaves this optional job unscheduled and supplies no GUI execution evidence; the
ordinary source guards still run. A configured but missing or changed group fails.
Native toolkit, browser/Wasm, baseline OS and release certification remain required
in their declared qualification workflows. Update the variable only after a
reviewed complete GUI-input publication when patches or supplier bytes change.

The Wasm Chromium-engine archive check runs on the ordinary Ubuntu 24.04 hosted
runner using its maintained Google Chrome installation and matching local
ChromeDriver. It records that actual browser identity; it does not claim to test
a Debian Chromium package. The host's browser namespace/AppArmor policy remains
active, and no sandbox-disabling argument or container security override is used.
Browser and driver executable hashes, architecture and matching major versions
are checked before execution; all retained executable hashes are checked again
after the browser assertions. Firefox distribution-runtime checks keep their
declared environments. These browsers remain test prerequisites outside SDKs.

Application producers exchange archive and descriptor filenames, not absolute
paths from their runners. The assembler validates each name as one portable
component and locates its ordinary file beside the restored producer descriptor.
It rejects drive paths, UNC paths, traversal, nested paths and reserved names
before writing an assembly specification. Consumer-local absolute paths may appear
in that temporary specification; the final release manifest uses portable names.
