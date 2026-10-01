# Development requirements

Read [the documentation index](docs/README.md), then the pages relevant to the
change. Build through [the supported entry point](docs/building.md). Keep public
interfaces, compatibility promises and tests consistent with the implementation.
User instructions and the harness's governing rules remain authoritative.

## Simultaneous sessions

Follow [agent coordination](docs/agent-coordination.md) before shared edits or
shared build/Git operations. Give each independent writer this file, that guide,
the absolute checkout and the agreed absolute board path. This includes separate
Codex chats, Anthropic desktop sessions, OpenRouter-compatible harnesses and
writing subagents. Passive read-only tools do not need their own session.

- Use the ignored `.agent-work/` directory for current ownership, temporary notes
  and per-session artifacts. One independent writer owns each session identity.
  Use the checked helper; do not implement ad hoc lock/unlock shell sequences.
- Discover complete claims, relevant releases and your inbox before acquisition.
  Bounded output must not hide owners or truncate a claim list. Unknown, corrupt
  or inaccessible data blocks affected shared writes; it never means free scope.
- Claim each file, directory and resource before writing, including unique notes,
  logs, build outputs and temporary directories. One writer per file. Claim both
  sides of a rename. Protect common Git state and shared build trees explicitly.
- Keep the registry mutex brief. File/resource claims persist after that mutex
  closes. A message, old timestamp, missing PID or empty lock never grants scope.
  Handoffs require an explicit release, fresh acquisition and acknowledgment.
- After a rejected or uncertain operation, stop its dependent saves, notices and
  launches. Inspect authoritative saved state before retrying uncertain results.
  Preserve foreign edits, staged work, processes, notes and uncommitted changes.
- Recheck input bytes and shared interface assumptions before applying an edit.
  Disjoint files can change the same invariant. Stabilize inputs during tests or
  use an isolated copy containing the intended uncommitted changes.
- Record launch intent before long commands, actual yielded handles when known,
  and completion at the next checkpoint. Finish children, open output streams,
  queued saves and cleanup writers before release. Parent exit alone is not proof.
- Replace current progress, jobs, blockers and next action together; record actual
  progress/inbox event times separately from publication time. Release a finished
  shared file before unrelated reporting. Use a new ID after closure or recovery.
- Keep useful unresolved findings in owned notes: evidence, environment, source
  and access date, confidence, failed attempts, next probe and removal conditions.
  Promote verified durable knowledge into tracked documentation/tests.
- Follow [lifecycle and recovery](docs/agent-lifecycle.md) for overdue ownership,
  interrupted jobs and eligible 30-day cleanup. Never automatically steal claims.
- Coordination is cooperative. For participants that may bypass it, enforce
  private checkout/output access or read-only access through the harness or OS.
  A separate directory, stronger model, clean merge or passing tests does not
  establish exclusion before writes. Qualified participants integrate shared work.

Coordination adds no research quota, approval step, extra reports or limitation on
normal browsing, delegation and tools. Continue independent useful work when one
scope is contested. Bind every filesystem tool and subprocess to its intended
absolute checkout; another tool's current directory does not carry over.

## Efficient implementation and verification

Use the smallest test that can discriminate the suspected cause. Run the affected
test group after a fix, then the required broader checks for the final candidate;
see [testing stages](docs/testing.md). Documentation changes need proportionate
checks. Do not repeatedly run expensive full suites while diagnosing one fault.
Do not invent weaker assertions, remove cases or count skipped/queued/cancelled
checks as passes to shorten iteration time.

Reuse evidence only for identical relevant source, configuration, dependencies
and environment. Name omitted coverage and its reason. Setup failure before test
assertions is zero executed assertions. Repair verified prerequisites, then rerun
the blocked scope. Separate observations from hypotheses and use a discriminating
probe before repeating a failed workaround. Preserve concise failure evidence.

Parallelize independent compilation and tests within CPU/memory limits. Use
per-session build directories and logs. A focused `devfast` configuration and an
explicitly selected faster CI runner are valid development tools when available;
restore required normal coverage before delivery. Avoid duplicate CI dispatches
for the same candidate. Wait for final results and inspect internal skips.

Keep application behavior and feature layout on the insulated side of the GUI
boundary. Backend adapters implement generic capabilities. Extend shared contracts
and shared tests when a new feature needs a capability; do not duplicate feature
logic across backend-specific code. Preserve the stated build and binary support
baselines, dependency provenance, SDK consumer checks and release evidence.

Before finishing, inspect the actual diff, verify observable consumer behavior,
update the relevant documentation and record exact validation with material limits.
Never stage unrelated work or publish external changes without task authorization.
