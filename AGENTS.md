# Development requirements

Read [the documentation index](docs/README.md) and relevant topic pages before
changing the project. Build through [the supported entry point](docs/building.md).
Keep public interfaces, compatibility promises and tests consistent with the
implementation. User instructions and the harness's governing rules remain
authoritative.

## Parallel work

For substantial work, use native managed subagents for useful, independent
assignments when available, up to 36 open children. Give each writer a disjoint
file or component scope; keep shared interfaces, tightly coupled changes and
final integration with the primary agent. Preserve concurrent edits and account
for shared resources. Reuse stable source and validation evidence; pending review
is not integration approval.

## Outputs and historical material

Reuse stable purpose-specific build directories; serialize work that shares a
tree. Remove obsolete binaries, packages, CMake/Ninja state, caches and generated
configuration. Retain only current compatible SDK/engine inputs or records needed
for unfinished implementation, pending qualification or an unresolved failure.
Keep each record concise: source identity, verified outcome, remaining work and
next action. Reference immutable shared inputs instead of copying trees. A past
result does not qualify changed source.

Use native managed coordination only: no session registries, boards, filesystem
claims or new `.agent-work/` material. Selected retained inputs keep their existing
paths; the current handoff identifies their purpose.

Search current tracked source normally. Consult a named retained input or record
when relevant; do not recursively search build/history trees for instructions or
inventory old runs. Historical documentation is optional, not a startup reading
list. Do not compress routine build output for hypothetical recovery. Keep restart
notes in the relevant plan or pending record.

## Development checks and manual qualification

Run inexpensive checks that address the current change. Defer costly full
regressions, broad platform/backend matrices and complete release certification
to applicable [pending qualification](.agent-pending/README.md) records by default.
Start extensive final qualification only when implementation is stable and the
user has requested either that qualification or an operation requiring it.
Stability alone is not authorization. Explicit expensive diagnostics may happen earlier.
Requests to implement, fix, review, commit, merge or push do not authorize extensive
qualification; a qualified binary release request does. Requesting the usual
GitHub Actions binary-build and certification workflows authorizes their complete
applicable workflows without separate approval for ordinary steps.

Explain the uncertainty, why cheaper checks cannot resolve it, and expected cost
before requesting an unauthorized expensive diagnostic. Once authorized, finish
the applicable workflow without repeated approval requests. Required gates precede
binary publication and package-channel promotion. Ordinary source commits and
pushes do not require complete release qualification.

Inspect relevant pending records when starting, substantially resuming or changing
scope. Reuse reviewed information unless its inputs may have changed. Record what
passed, omitted coverage and why, what remains unverified, and the next manual
command or request. Unexecuted, skipped, queued or cancelled checks are not passes.
Distinguish implementation gaps and known failures from completed implementation
awaiting qualification. See the [pending-record guide](.agent-pending/README.md).

## Implementation integrity

Use the [testing stages](docs/testing.md) and the qualification policy above.
Reuse evidence only for identical relevant source, configuration, dependencies,
test inventory and environment. A setup failure before assertions executes zero
assertions. Repair verified prerequisites and rerun the blocked scope. Preserve
failure evidence and use a discriminating check before repeating a workaround.
Do not weaken assertions or remove cases to shorten iteration time.

Keep application behavior and feature layout on the insulated side of the GUI
boundary. Backend adapters implement generic capabilities; extend shared
contracts and tests when a feature needs one. Preserve build and binary support
baselines, dependency provenance, SDK consumer checks and release evidence.

For appended applications, use the [implemented payload tools](docs/appended-applications.md)
and retained-kernel route. Web-resource changes do not compile modules; portable
module changes may compile only that module. Payload work does not authorize
configuring, compiling, linking or installing the retained kernel, including on a
cache hit. Missing or incompatible retained inputs fail with concrete maintenance
needs and never fall back to a full build. Initial or changed kernel capabilities
require the explicit `--kernel-maintenance --appended-profile` operation for the
selected profile, under the qualification policy above. The separate explicit
`engine-maintenance` producer may use only its admitted retained baseline; payload
work does not authorize it or a full engine rebuild. Do not describe the rich web
engine as implemented until its documented feasibility and integration gates pass.

Before handoff, inspect the diff, check observable consumer behavior, update
relevant documentation and record exact validation with material limits. Do not
stage unrelated work or publish external changes without task authorization.

## Release preferences and trust

Strongly prefer GitHub-hosted Actions for release builds and publication. Local
release builds and publication remain permitted but strongly discouraged.
The project places greater trust in provider-managed build infrastructure and its
applicable integrity protections,
based on longstanding runner observations. Accept this trust assumption during
routine work without repeated hardware investigations or new attestation
requirements; self-hosted Actions runners do not establish the same environment.

Preserve qualification and provenance requirements on either route, recording
build origin separately from upload location. Prefer authenticated retained CI
artifacts when identity and qualification still apply, and verified retained
base-release SDKs matching the target, profile and toolchain. Add no approval
steps beyond the qualification trigger, task authorization and existing release
controls. Optional improvements are listed in [FURTHER-agents.txt](FURTHER-agents.txt).
