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

## Artifacts, caches, and SDK reuse

Use a compiler cache to accelerate rebuilds and workflow artifacts to transport
finished packages and reports. Key caches by OS, architecture, compiler/runtime,
configuration, and dependency identity. Do not cache credentials. Restore caches
as untrusted accelerators whose absence or corruption must not weaken checks.

Never pass a configured build tree between runners as an ordinary shortcut.
Its absolute paths, compiler state, generator state, and timestamps can invalidate
results. Rebuild inexpensive targets or move finished immutable archives.
Already-compressed packages usually need no second compression in artifact
upload; retain failure logs even when a test job fails.

Prepared SDKs and dependency bundles use durable storage with exact identities.
Routine jobs fetch and verify them. Missing recipes fail early with an explicit
maintenance instruction. SDK compilation belongs in a separately dispatched
maintenance workflow, with [source preservation and relocation checks](sdk.md).

Set retention intentionally: short-lived diagnostic logs, longer candidate
reports, and durable release inputs/results. Do not assume an expiring Actions
artifact remains available to reproduce a supported release.

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

## Supplied workflow entry points

- `ci.yml`: inexpensive automatic feedback.
- `candidate.yml`: validated native runner inventory, disjoint core/tool/install
  scopes, independent portable packaging, fresh copied-package execution,
  instrumentation, signed-distribution fixtures and a complete final verdict.
  `devfast` runs only the declared focused selection; ARM omission is visible.
- `sdk-maintenance.yml`: explicitly dispatched cold SDK production on the old
  host baseline. A successful job retains the complete new recipe group for
  reviewed durable-base delivery.
- `sdk-application.yml`: consume an exact existing group from the base release;
  missing assets fail before compilation. Ordinary application work does not
  silently become SDK maintenance.

[`github_release.py`](../tools/github_release.py) provides checked durable delivery
operations and offline plans. Keep write credentials in a protected, separately
serialized publication job. A build workflow's green status cannot promote a
candidate. Follow [exact delivery and promotion](github-delivery.md) and
[certification](certification.md), preserving every selected result and its
run/attempt identity. All workflow definitions still require hosted qualification.
