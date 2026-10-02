# Test selection, completeness, and execution cost

Use the least expensive check that can answer the current development question,
then run the required broader checks when the candidate is ready. A focused
pass proves only its named scope. A test plan must identify what is required
for the change and what remains outstanding.

## Everyday sequence

```sh
./build.sh test dev --label core --jobs 2
./build.sh test dev --full --jobs 2
./build.sh test asan --jobs 2
./build.sh package release --jobs 2
```

Choose the first label for the actual change: `core`, `tools`, `integration`, or
`gui`. `fast` is the inexpensive cross-cutting selection. These labels can
overlap; running several overlapping labels is not additional independent
coverage. The dependency-free GUI input and visual-comparison fixtures also belong
to `tools`, so ordinary native candidate jobs exercise them before any GUI SDK
preparation. Their `gui;focused` labels preserve targeted GUI selection; each
suite is registered once and records every case through the common test runner.
The wrapper rebuilds test prerequisites. Direct `ctest` alone does
not compile modified source.

| Change | First useful evidence | Candidate checks |
| --- | --- | --- |
| Library behavior or public contract | Reproducer and affected core tests | Full local suite; supported platform and sanitizer scopes |
| CLI parsing or output | CLI integration cases | Core and CLI regression; packaged executable checks |
| Build/helper logic | Small offline fixtures | Clean and incremental builds; install consumer; package checks |
| SDK/dependency recipe | Recipe/manifest fixtures | SDK host and target qualification; affected application matrix |
| Shared GUI behavior | Shared application and boundary tests | Every enabled adapter's contract, interaction, and layout checks |
| Backend adapter | Adapter conformance cases | Shared contract plus affected native backend execution |
| Documentation only | Links, commands, consistency | No unrelated expensive runtime matrix unless still outstanding |

During diagnosis, preserve a failing reproducer, fix the cause, and repeat that
scope. Do not continually rebuild SDKs or rerun every platform while the same
fault is unresolved. After completion, run the broader applicable gates once.
Reuse evidence only for unchanged source, configuration, dependency identity,
test inventory, and relevant environment. Record reused results explicitly.

## Test design

Assert public behavior and invariants. Use independent expected values,
boundary cases, invalid inputs, ownership/lifetime checks, cancellation, and
failure cleanup. A test that repeats the implementation cannot establish its
correctness. Keep pure library tests independent of the desktop, network,
clock, and installed application when those services are not under test.

Use unique temporary output directories and deterministic inputs. A test must
not overwrite another test's files, use a fixed shared port without coordination,
or depend on execution order. Always clean up owned resources, while retaining
diagnostics on failure. Set individual timeouts and test process exit status as
well as output. Test assertions must remain active in optimized builds. Visual
qualification rejects an interpreter started with assertions disabled; setting
Python optimization flags must never turn a failed comparison into a pass.

Tests shipped in a source archive must run without the original checkout or its
Git metadata. A fixture that exercises Git identity must create and commit its own
temporary repository; keep the production identity check real. Route CI output
files and other inherited output channels into the fixture's owned directory.
When repairing an archive-only failure, run the affected complete suite from a
fresh extraction outside any parent checkout and without `.git` before repeating
an expensive release workflow.
Never add fabricated repository metadata to a delivered archive or exclude a
required case to conceal the failure.

Keep contract regressions when refactoring. Modify an assertion only when the
intended public contract changes and the change is reviewed. Document numerical
tolerances and environment assumptions where relevant. Do not loosen a
correctness requirement merely to obtain a faster or green CI run.

## Inventory-driven parallel work

CTest's machine-readable inventory can support deterministic assignment:

```sh
ctest --test-dir build/dev --show-only=json-v1
ctest --test-dir build/dev --output-on-failure --no-tests=error \
  --output-junit build/dev/results.xml --parallel 2
```

The project helper may wrap these operations; the underlying features are
documented in [CTest 3.24](https://cmake.org/cmake/help/v3.24/manual/ctest.1.html).
Before running a shard, record the complete inventory, selected names, source
revision, configuration, and shard rule. For a required distributed suite:

1. Every enabled required test belongs to exactly one shard for that scope.
2. Selection is deterministic and duplicate test names are rejected.
3. Every shard reports exact executed names and outcomes, not only a zero exit.
4. Aggregation rejects missing, duplicate, unexpected, skipped, or stale cases.
5. The union of shard results equals the expected inventory before success.

A newly added test must be assigned automatically to a documented default
scope or rejected as unassigned. An empty shard is either explicitly declared
valid in the plan or an error. A selector typo must not produce a green job.
Delete a prior run's result file before execution so it cannot satisfy a later
failed attempt.

The supplied [`tools/test_plan.py`](../tools/test_plan.py) freezes the test
inventory and source identity, runs disjoint selections, and rejects incomplete
aggregation. It incrementally rebuilds `foundation-tests` before planning and
before each shard run, preventing an old executable from representing newly
edited source. Plans bind the complete source snapshot, including configured GUI
sources, current compiler bytes and resolved path, normalized complete CMake cache,
build metadata, test definitions, and verified SDK/dependency/GUI input inventories.
Shards recheck these before rebuilding prerequisites, after compilation, and after
test execution; changed inputs invalidate the plan. Retained SDK CMake/CTest and
environment are used when configured. Direct native CMake trees remain supported;
prepared external groups require their verified wrapper metadata.
Prior result and aggregate files are removed before an attempt so a failed run
cannot leave an earlier successful receipt available for reuse. Completed records
are published atomically. This example runs two shards
sequentially so their use is safe in one owned local build tree:

```sh
cmake --preset release
cmake --build build/release --target foundation-tests --parallel 2
python3 tools/test_plan.py plan --build build/release --shards 2 --output build/plan.json
python3 tools/test_plan.py run --build build/release --plan build/plan.json \
  --shard 0 --jobs 2 --output build/result-0.json
python3 tools/test_plan.py run --build build/release --plan build/plan.json \
  --shard 1 --jobs 2 --output build/result-1.json
python3 tools/test_plan.py merge --plan build/plan.json --output build/coverage.json \
  build/result-0.json build/result-1.json
```

For simultaneous execution, give each shard its own build tree or runner and
unique output. Match the frozen source/configuration and planned inventory.
Do not launch multiple CTest writers against one tree's `Testing/` directory.
Distributed production plans can add weighted assignment based on recorded
durations while preserving the same input and completeness checks.

For tests divided internally across workers, retain every required case and
input identifier. Aggregate original raw results before applying any combined
acceptance criterion. Averaging independently rounded shard summaries can change
the decision. Validate missing/duplicate inputs and preserve the original
per-case and combined gates. Test partition planning with tiny fixtures before
running the expensive work.

## Resource management

Build concurrency, concurrent test processes, and each test's internal workers
multiply. Budget CPU and memory across all three. Use CTest `PROCESSORS`,
`RUN_SERIAL`, `RESOURCE_LOCK`, or resource groups when appropriate; these are
local scheduler controls, not cross-machine locks. A long serial test can run
on its own CI runner while independent suites execute elsewhere.

Separate package production from expensive regression work so copied-package
checks can start as soon as the archive exists. All required outcomes must
still reach the final gate. Prefer modest repeated compilation to transferring
configured build trees whose absolute paths and toolchain state are not
portable. Measure total runner minutes as well as elapsed critical-path time.

Do not run timing-sensitive checks under simultaneous heavy builds unless that
contention is the condition being tested. Instrumented execution and software
GUI rendering can be much slower. Keep real behavioral deadlines separate from
the outer computation allowance. Adjust an outer allowance only with evidence;
retain all correctness and cancellation assertions.

## Result vocabulary and failure handling

Use `passed`, `failed`, `skipped`, `incomplete`, and `not_run` distinctly. A
cancelled job, unavailable target, omitted sanitizer scope, exhausted work
allowance, or external timeout is never a pass. A successful near-timeout case
can emit a timing warning. A progressing but unfinished case is incomplete.
This example's required gates fail if mandatory coverage is incomplete.

If a product permits a narrow environmental exception, define a typed error
classifier, exact affected scope, evidence, owner, expiry/recheck condition,
and release consequence in advance. Preserve unrelated mandatory checks. Do
not accept all crashes, all graphics errors, or any timeout under one label.
Reports must enumerate omitted coverage even when the enclosing workflow is
allowed to finish successfully under its documented policy.

On failure, retain console logs, selected inventory, machine-readable outcomes,
configuration, and timing. Run the focused reproducer while fixing the failure,
then rerun the affected complete gate. Retry infrastructure failures only with
a bounded policy and keep both attempts visible. Repeating until one attempt
passes is not a substitute for investigating a flaky assertion.

## AI-agent requirements

Agents must state the affected scope, use the smallest meaningful checks during
editing, and broaden validation at the candidate checkpoint. They must not
claim full validation from `devfast`, a subset, an old build tree, or another
revision. Recheck [coordination](agent-coordination.md) before launching shared
builds or long tests. Record process identity and owned output paths if a job
outlives a tool response; do not launch duplicate work because the tool yielded.

For each completed change, report commands, actual pass/failure status, omitted
coverage, and remaining external qualification. Use the
[validation template](templates/validation.md) for durable evidence and the
ignored coordination directory for transient investigation notes.

## Unit-case evidence and release attempts

CMake runs each Python suite through [`run_tests.py`](../tools/run_tests.py).
The helper discovers its complete case inventory, records each outcome and exposes
narrow platform exclusions separately. Missing fixture privileges or tools are
incomplete coverage and return failure. Unittest's successful process exit after
an internal skip cannot become a complete passing receipt. Optimized C++ tests use
explicit checks rather than assertions removed by the compiler.

For multi-environment release work use [the frozen coverage and certification
protocol](certification.md). Its immutable attempt directories and supervised
process trees add source/asset/policy identity to the local CTest shard mechanism.
Neither local helper authorizes concurrent writes to a common build directory.


## Focused host diagnostics

The manual [Host contract diagnostics workflow](../.github/workflows/host-contracts.yml)
runs one complete `process_tree`, `windows_graphics`, `ci_plan`, `github_release`
or `ci_transport` unit suite directly on a Windows x64, Linux x64 or Linux ARM64
runner. The opt-in `windows_hosts` suite requires Windows and exercises the actual
installed MSVC compiler and Firefox. It compiles the same native probe with the
same arguments and process owner as graphics qualification, then separately opens
an automation session, checks a simple page and verifies immediate profile removal
after browser shutdown. It acquires no SDK or graphics driver and does not execute
the graphics probe. These cases live outside ordinary unit-test discovery and
CMake coverage; ordinary unit tests must not require installed browsers or MSVC.
Select `runner-default`, Python `3.12` or `3.14`, and 1, 5 or 20 repetitions. Explicit versions resolve only the highest complete stable patch in
`RUNNER_TOOL_CACHE`; an unavailable or mismatched native interpreter fails without
downloading Python. The default uses the workflow shell's existing interpreter.

[`host_contracts.py`](../tools/host_contracts.py) records the selected executable,
its SHA256, reported Python version and architecture, runner image, source hashes
and exact workflow revision. Every repetition retains the complete `run_tests.py`
case inventory and console log. A failure stays failed even when later repetitions
pass; missing inventories, internal skips, timeouts and incomplete repetitions
cannot pass. Each suite has a 120-second execution limit and the complete run has
a 50-minute limit. Cleanup must stop and join supervised writers before another
repetition starts; uncertain cleanup stops the run and permits retention only of
the failed summary, never potentially active child logs or inventories.

Give each process tree the same lifetime as the resources it can write. An outer
test-runner supervisor cannot protect an inner temporary profile that the test
deletes before it exits. Browser and driver wrappers must stop and join their own
descendants before closing logs, copying evidence or removing temporary files.
If that join is uncertain, preserve the workspace and fail the check. Test the
case where a child keeps writing after its primary process has exited; waiting for
the primary alone does not establish cleanup.

On Windows, the process supervisor pins descendant identities and waits for their
handles to become signaled after Job Object termination, under the same bounded
deadline as parent cleanup. An empty active-process count alone cannot establish
that child output handles have closed. Membership changes, inaccessible identities
and cleanup failures remain failures. The native regression observes the exact
child handle and immediately renames and removes its output after cleanup; it does
not hide uncertain shutdown behind a delay or deletion retry. When a command
exits with a live Windows descendant, the failure retains the first verified
member identity, process image or query error, wait state and bounded membership
counts. Later process exit cannot erase that observation. Diagnose the observed
helper before changing compiler options; an unrelated telemetry switch or a
passing retry does not establish the cause. The native compiler has an explicit
[exact-helper completion policy](windows-graphics.md#bounded-test-environment) for
its identified optional telemetry child. This verifies every live member and
terminates and joins it before reading output; it does not relax ordinary command
completion or accept unclassified descendants.

The workflow always attempts to retain `result.json` and each repetition's logs
and inventory through the existing lifecycle `bundle-store`, using the run-scoped
`host-contracts-ATTEMPT` bundle. It needs repository contents write permission only
for that retained evidence transport; the test step receives no token. Failed runs
can be inspected with the [same exact bundle recovery](github-delivery.md) as other
lifecycle evidence. No Actions artifact storage or prepared SDK build is required.
These diagnostic receipts never satisfy source, package or release qualification;
repeat the required complete gate after a diagnostic correction.
