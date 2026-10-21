# Development requirements

Read [the documentation index](docs/README.md), then the pages relevant to the
change. Build through [the supported entry point](docs/building.md). Keep public
interfaces, compatibility promises and tests consistent with the implementation.
User instructions and the harness's governing rules remain authoritative.

## Parallel subagents

For substantial tasks, identify useful independent workstreams and delegate them
concurrently. Use up to 36 concurrently open spawned subagents, excluding the
primary agent, when the runtime permits and there is enough independent work.
Parallelize investigation, implementation, focused validation, documentation and
review as useful; avoid serializing independent work merely to conserve slots.
Partition edits by non-overlapping files/components and coordinate shared resources
and invariants under the project's applicable coordination requirements. The
primary agent integrates results, resolves conflicts and performs final validation.

## Development checks and manual qualification

During implementation, run inexpensive, meaningful checks that discriminate the
change and resolve immediate uncertainties. An inexpensive complete local suite
may be appropriate. By default, defer costly full regressions, broad platform or
backend matrices and complete release certification to tracked
[pending qualification](.agent-pending/README.md).

Normally start extensive final qualification only when **both implementation has
stabilized and the user explicitly requests extensive validation or a release
operation requiring it**. Stability alone is not authorization. Explicit requests
for expensive diagnostics or exploration may precede stabilization. Generic
requests to implement, fix, review, commit, merge or push do not authorize extensive
qualification; a request for a qualified binary release does. Asking for the usual
GitHub Actions binary-build and certification workflows to pass authorizes the
applicable complete workflow, even if it takes an hour or more, without separate
approval for its ordinary steps. For an unauthorized expensive diagnostic, explain
the uncertainty, why cheaper checks cannot resolve it and expected cost before
requesting execution.

Inspect relevant pending records at task start, substantive resume or scope change;
reuse reviewed information unless relevant state may have changed. At implementation
handoff, identify what passed, what remains unverified and the next manual command
or request. Clearly distinguish unfinished implementation, known failures and
implemented work awaiting extensive qualification. Unexecuted, skipped, queued or
cancelled checks are never passes. Follow the linked pending-record guide rather
than creating obligations for every available test.

Once authorized, complete the applicable workflow without repeated permission
requests. Batch independent work, reuse applicable verified results with their
original identities, avoid duplicate launches and supervise running jobs with
appropriately spaced status checks. Required gates still precede binary-release
publication and package-channel promotion; pending gates mean pending publication.
Ordinary source commits and pushes do not require complete release qualification.

## Parallel work

Use native managed subagents for independent, bounded work when useful. Give each
writer a clear, disjoint file or component scope, and keep shared interfaces and
tightly coupled changes with the integrating supervisor. Preserve concurrent edits
and coordinate directly with the assigned writers. Serialize work that uses a
shared build tree, or use a purpose-specific directory under `build/` for each
independent build or test run. Reuse a stable purpose-specific directory for
ordinary incremental builds; do not accumulate date- or attempt-named trees by
default. After a completed check, remove disposable generated binaries, object
trees and package copies when they are no longer needed, while retaining its
concise result, exact commands and source identity in existing validation or
pending-qualification records. Retain an engine, kernel or SDK baseline only when
it is deliberately current and its exact source, configuration and provenance are
recorded; retire a replaced baseline after its successor is accepted. Historical
validation results record past runs and do not prove an old binary is rerunnable.
Put concise, durable restart notes in the existing plan or pending-qualification
documents.
Historical `.agent-work/` records are archival evidence and need no exhaustive
inventory or active administration. Their disposable generated outputs follow
the same retention policy; preserving a result does not require keeping its binary.

## Implementation integrity

Use [testing stages](docs/testing.md) under the manual-qualification policy above.
Documentation changes need proportionate checks. Do not repeatedly run expensive
full suites while diagnosing one fault, weaken assertions or remove cases to
shorten iteration time.

Reuse evidence only for identical relevant source, configuration, dependencies
and environment. Name omitted coverage and its reason. Setup failure before test
assertions is zero executed assertions. Repair verified prerequisites, then rerun
the blocked scope. Separate observations from hypotheses and use a discriminating
probe before repeating a failed workaround. Preserve concise failure evidence.

Parallelize independent compilation and tests within CPU/memory limits. Use
per-session build directories and logs. A focused `devfast` configuration and an
explicitly selected faster CI runner are valid development tools when available;
restore required normal coverage before qualified binary delivery. Wait for final
results of authorized checks and inspect internal skips.

Keep application behavior and feature layout on the insulated side of the GUI
boundary. Backend adapters implement generic capabilities. Extend shared contracts
and shared tests when a new feature needs a capability; do not duplicate feature
logic across backend-specific code. Preserve the stated build and binary support
baselines, dependency provenance, SDK consumer checks and release evidence.

For appended applications, use the [implemented payload tools](docs/appended-applications.md)
and retained-kernel route. Web-resource changes must not compile modules; portable
module changes may compile only that module. Neither kind authorizes configuring,
compiling, linking or installing the retained kernel, including cache-hit builds.
Missing/incompatible retained inputs must fail with concrete maintenance needs,
never fall back to a full build. Initial or changed kernel capabilities use the
explicit `--kernel-maintenance --appended-profile` operation for the selected
profile and the existing manual-qualification policy. The separate explicit
`engine-maintenance` producer may only use its admitted retained baseline;
payload iteration never authorizes it or a full engine rebuild. Do not describe
the rich web engine as implemented until its documented feasibility and
integration gates pass.

Before finishing, inspect the actual diff, verify observable consumer behavior,
update the relevant documentation and record exact validation with material limits.
Never stage unrelated work or publish external changes without task authorization.

## Release preferences and trust

Strongly prefer GitHub-hosted Actions for release builds and publication. Local
release builds and publication remain permitted but strongly discouraged. Hosted
publication typically avoids slow workstation transfers. Based on the maintainer's
longstanding runner observations, the project places greater trust in provider-managed
build infrastructure and its Intel TXT, AMD SEV and/or other applicable integrity
protections. Accept this project trust assumption during routine work without
repeated hardware investigations or new attestation requirements; self-hosted
Actions runners do not establish the same environment.

Preserve qualification and provenance requirements on either route, recording build
origin separately from upload location. Prefer authenticated retained CI artifacts
when their identities and qualification remain applicable, and verified retained
base-release SDKs matching the required target, profile and toolchain constraints.
Add no approval ceremony beyond the manual-qualification trigger, task authorization
and existing applicable release controls. Optional future improvements are listed
in [FURTHER-agents.txt](FURTHER-agents.txt).
