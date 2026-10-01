# Working with simultaneous sessions

This workflow supports independent chats and tools sharing a checkout: Codex,
Anthropic desktop sessions, OpenRouter-compatible harnesses and writing subagents.
Every participant receives [AGENTS.md](../AGENTS.md), this guide, the absolute
checkout and the agreed absolute board path. No common parent, scheduler or
continuously running service is required. One independent writer owns each session
ID; a read-only helper can be recorded under its parent's scope.

The board coordinates cooperating filesystem users. It does not enforce access,
synchronize clones or prove an agent's factual statements. Use OS/harness access
controls when participants cannot reliably honor the protocol. Give such workers
private source and output access while denying shared checkout, board, build tree
and common Git mutations. A separate path alone is not enforcement. A qualified
participant performs the claimed integration and verifies the combined result.

## Start with a bounded inspection

1. Bind tools to the intended **absolute** checkout. Verify its physical location,
   branch/revision, worktree changes and staged changes. Preserve other authors'
   work; do not reset, stash, clean, blanket-stage or claim it as your own.
2. Agree on one board location. Default: `<checkout>/.agent-work/`. Separate
   worktrees/clones need an explicit shared absolute `--board` path. A typo must
   not silently create a second board. Only `init` creates a board. Verify ignore
   rules before using an in-repository board.
3. Read current metadata and **every complete claim**, including closed records
   and relevant releases. Inspect your inbox and task-relevant note metadata,
   then selected note bodies. Ignored files require explicit reads.
4. Register your unique session, exact task/approach, baseline, dependencies and
   next action. Claim scope before its first write. Initial registration uses
   memory/stdin; subsequent request files belong in already-claimed artifacts.
5. Choose per-session notes, outputs and build trees. A unique filename alone is
   not a claim. Directory claims cover future descendants; prefer exact files.

Bound returned output, not investigation depth. Read one relevant document or
source section per result, continuing after truncation. Discover note filenames
and titles before opening selected notes. Never relevance-filter ownership away.
Routine checkpoints use current state; they do not reread all instructions or
historical logs. There is no quota or extra permission step for normal research,
browsing, tools, delegation or read-only investigation.

## Directory and record contract

```text
.agent-work/                         # ignored; never application input
  state.json                         # one authoritative atomic snapshot
  registry.lock/                     # short-lived transaction mutex
    owner.json                       # acquisition token, host, PID and time
  notes/<session-id>/                 # compact temporary facts; claimed
  artifacts/<session-id>/             # requests, logs and disposable output; claimed
```

[`tools/agent_board.py`](../tools/agent_board.py) is a Python standard-library
example. Each session is a structured record inside `state.json`; all ownership,
release and inbox changes publish together. This avoids partial multi-file
transfers. It uses a short exclusive directory creation, validates the complete
snapshot, stages complete bytes inside the mutex, flushes them, atomically replaces
the snapshot, verifies saved bytes and verifies/removes only its own lock.
Successful receipts appear only after cleanup. No caller command runs under the
mutex. Do not edit registry state or lock files with ordinary editors.

The helper rejects unknown top-level board entries, unknown schema/record fields,
duplicate JSON keys, malformed metadata, partial claims, type mismatches, links,
conflicting claims and excessive input. Rejected records never disappear from
ownership consideration. Inspection fails closed and names the issue; investigate
it before shared writes. Notes and artifacts are not recursively ingested.

Capacity is deliberately explicit: a 4 MiB snapshot, 512 sessions, 128 scopes or
list items per session and 4,096 releases/messages each. Reaching a limit is an
error requiring reviewed retention maintenance, not permission to truncate. This
compact example favors clarity for small teams; it is not a high-volume service.

## Runnable command contract

Requires Python 3.9 or newer. JSON requests use stdin or `--input` with a claimed
regular file. `--root` defaults to the directory containing the repository's tools;
set it explicitly when acting on another checkout. An alternate `--board` must be
absolute and explicitly initialized. Examples below run from this checkout.

```sh
python3 -B tools/agent_board.py init <<'JSON'
{}
JSON
python3 -B tools/agent_board.py status <<'JSON'
{"offset":0,"limit":20}
JSON
```

`status` returns the current `revision`, `next_offset` and bounded entries. Follow
all pages, passing the same `revision` on later pages. A changed revision rejects
the next page: restart observation. Every returned session includes its whole
claim list. Release entries follow the sessions, including closed predecessors.
Use a smaller page size if an individual response is too large. `show` returns
one complete session; `inbox` returns paged messages without marking them processed.

```sh
python3 -B tools/agent_board.py show <<'JSON'
{"id":"editor-example"}
JSON
python3 -B tools/agent_board.py inbox <<'JSON'
{"id":"editor-example","offset":0,"limit":20}
JSON
```

Prepare a registration request from [the template](templates/session.json) in
memory. Replace its example revision and timestamp with the actual reviewed
revision and a concrete next check. The template is an input, not a second registry.
Choose a never-used ID, then call `register`. Closed IDs cannot reopen.

For a prepared registration request, run `python3 -B tools/agent_board.py register
--input /absolute/claimed/path/register.json`. When no artifact claim exists yet,
pass the prepared JSON directly through stdin instead. Do not overwrite the
tracked template to keep one session's private state.

Every mutation requires `id` and the current reviewed `revision`, including
registration. Values below illustrate a sequence; substitute actual receipt
revisions after each successful operation. Do not blindly refresh a rejected
request's revision: reread the changed state and replan first.

```sh
python3 -B tools/agent_board.py claim <<'JSON'
{"id":"editor-example","revision":1,"scopes":[
  {"kind":"file","value":"src/example.cpp"},
  {"kind":"directory","value":".agent-work/notes/editor-example"},
  {"kind":"directory","value":".agent-work/artifacts/editor-example"},
  {"kind":"directory","value":"build/agents/editor-example"},
  {"kind":"resource","value":"invariant:public-interface"}
]}
JSON
```

Scopes have exactly `kind` and `value`. File/directory values may be repository
relative on input; the saved record uses absolute physical paths. Resources use
exact agreed identifiers. There are no wildcard claims. File/directory kind is
checked against existing objects and rechecked when absent paths materialize.
Renames claim old and new paths; formatters and generators claim every possible
output. Claims overlap by path components, including directory descendants.
Conservative case/Unicode folding rejects ambiguous conflicts; it never grants
ownership of a different spelling. Links/reparse points are rejected. Mutable
hard-linked files are not independent copies; directory claims cannot enumerate
all such aliases, so prohibit hard-linked source snapshots.

Paths with trailing dots/spaces, reserved device components, alternate stream
separators, wildcard characters or control characters are rejected on every host.
Use agreed long physical names; do not mix Windows short aliases or other platform
aliases that portable path operations cannot reliably equate. Such environments
need an OS-specific verified adapter or independent copies before shared writes.

`claim`, `accept`, `job start` and `run` optionally accept reviewed inputs:

```json
{"inputs":[{"path":"include/example.hpp","sha256":"<exact lowercase digest>"},
           {"path":"new-file.txt","sha256":null}]}
```

Replace the placeholder before use. A null digest means observed absence. Inputs
are checked inside the transaction. A digest detects changed bytes; it does not
freeze an input, prove no edit/revert occurred or identify its previous owner.
Record the relevant revision, dirty hashes and ownership/integration assumptions.

## Dependency stability and shared resources

One writer per file applies even to separate functions and append-only summaries.
Disjoint files can still alter one public interface, data format, state transition
or other shared invariant. Record such read dependencies and integration order.
Use a named invariant resource when intermediate combinations would be unsafe,
or use isolated snapshots and one integrator. Before applying conclusions, reread
changed dependencies and replan; do not merely update a hash to silence a guard.

Tests/builds need stable source for their duration. Coordinate writers or make an
independent snapshot containing the intended dirty inputs. A worktree from a commit
omits uncommitted changes. Do not copy configured build trees between environments
and treat them as portable caches. Validate the integrated candidate, not just
independently passing branches. Shared caches need documented concurrency support
or their own resource claim.

Use agreed resources for non-file state, for example:

| Resource | Scope and rule |
| --- | --- |
| `git:common` | Shared index/ref/worktree administration; use a common identifier across related checkouts. |
| `build:integration` | A shared integration tree; per-session build directories are preferable. |
| `invariant:public-interface` | Coupled interface/consumer changes that must be integrated together. |
| `device:test-unit` | One externally shared test device or service slot. |
| `capacity:heavy-tests` | Agreed resource budget for memory/CPU-heavy suites. |

File claims do not protect Git operations that change several paths or common
metadata. Coordinate branch/index/ref changes and preserve staged work. No blanket
staging, resets or cleanup. Deadlocks are avoided by declaring/acquiring complete
needed scope in one transaction, releasing unnecessary scope, and agreeing an
order before waiting while holding resources. Continue independent useful work.

## Handoff and shared-file editing

Prepare content and evidence before taking a contested summary file. Acquire,
acknowledge, reread its current contents, edit, verify preservation, release and
notify. Release it before unrelated report formatting or session closure.

A normal `release` takes exact held `scopes`, `writers_stopped:true` and a factual
`disposition` describing retained changes, checks and remaining work. It writes an
explicit release record while removing ownership. Matching bytes never identify
the latest owner; inspect relevant release entries as well as the current claims.

A directed `handoff` adds `to`. It releases the sender's claim and records a pending
transfer for the recipient. The pending transfer blocks third-party acquisition
until `accept` or coordinated recovery. `accept` names `release` and a nonempty
`review` of predecessor/current inputs. It freshly checks conflicts, acquires the
exact scopes, records acceptance and publishes a correlated acknowledgment to the
sender together. Neither participant can close with an unresolved transfer.

```json
{"id":"editor-example","revision":2,"to":"reviewer-example",
 "scopes":[{"kind":"file","value":"src/example.cpp"}],
 "writers_stopped":true,"disposition":"Saved and checked; uncommitted change retained."}
```

Supply that request to `handoff` only after the named recipient has registered.
Then the recipient calls `accept` using the returned release ID, current revision
and actual review. A message alone, a promised future release, an outdated receipt
or an unrelated reply ID never grants ownership.

A parent directory claim must be narrowed before transferring one child. `narrow`
takes a held directory `parent`, the complete remaining child `scopes`,
`writers_stopped:true` and `disposition`. It replaces the parent reservation with
those contained scopes in one transaction and records the released parent. No
writer may still be editing the area being released.

Use `message` with `to`, bounded `body` and optional unique `message_id` for requests.
Bodies are immutable; duplicate IDs fail without replacement. Keep one current
request per scope and check the inbox before reporting blocked. Inbox discovery
is not processing: read the bodies, resolve relevant facts and record actual
processed message IDs/time at a checkpoint. Messages are local board entries and
do not automatically wake another chat or send email/notifications.

## Commands, checkpoints and closure

Before a command that can block or outlive its tool reply, claim its outputs,
working directories and shared resources. Register a `job` with `action:"start"`,
`job_id`, `scopes`, `command` and available `identity`. Record launch intent before
launch; update actual process/handle evidence in a checkpoint's progress when the
tool yields. Mark unknown identity explicitly rather than inventing it.

The optional `run` operation accepts an `argv` list, `scopes` and `job_id`. It
records launch first and invokes a foreground command without a shell, outside
the registry mutex. Acquisition/publication/cleanup failure prevents launch.

```json
{"id":"editor-example","revision":3,"job_id":"focused-check",
 "scopes":[{"kind":"directory","value":"build/agents/editor-example"}],
 "argv":["python3","-c","print('example foreground check')"]}
```

`run` returns the actual parent exit status, but deliberately retains the job even
on success. Inspect children, tools, inherited output streams and cleanup handlers.
Then use `job` with `action:"finish"`, the `job_id`, `writers_stopped:true` and an
accurate `result`. Parent exit does not prove children or final log writes stopped.
For asynchronous tools, use `job start`, ordinary harness execution, then the same
explicit reconciliation. The helper cannot supervise arbitrary descendant trees.
Do not detach untracked writers. Failed launches also need reconciliation.

`checkpoint` replaces the complete current `state`, `progress`, `checks`,
`blockers`, `next_action`, `next_check`, `dependencies` and `disposition`. It may
advance actual `progress_at` and `inbox_at` and mark `processed_messages` by ID.
Omitting event times preserves them. A publication timestamp is not progress;
printing an inbox is not understanding its messages. Replace obsolete job/blocker
claims in prose as well as structured fields. Short synchronous commands join the
next checkpoint; no per-command journal is required.

A complete checkpoint request looks like this (substitute actual revision, time,
results and omitted coverage):

```json
{"id":"editor-example","revision":4,"state":"active",
 "progress":"Focused verification finished; integration review remains.",
 "checks":["Focused behavior check: passed; broader regression: pending."],
 "blockers":[],"next_action":"Review consumers, then run required regression coverage.",
 "next_check":"2030-01-01T12:05:00+00:00","dependencies":[],
 "disposition":"Own changes remain uncommitted; existing unrelated work preserved."}
```

To reconcile the example foreground job, call `job` with:

```json
{"id":"editor-example","revision":5,"job_id":"focused-check","action":"finish",
 "writers_stopped":true,"result":"Exit 0; verified no remaining child or output writers."}
```

Before pausing, release unneeded claims and say why retained scope is needed. To
close, reconcile all jobs and handoffs, finish evidence and every output writer,
release remaining claims and call `close` with terminal `state` (`done`, `failed`
or `cancelled`), `writers_stopped:true`, `result` and `disposition`. A failed test
is not automatically a failed whole session. Terminal records retain outcome and
30-day retention metadata. Output from release/close belongs in the harness or
memory, never redirected into an artifact being released by that same operation.

After a `release` for every remaining exact scope, a terminal request is:

```json
{"id":"editor-example","revision":7,"state":"done","writers_stopped":true,
 "result":"Requested change and applicable checks complete; see maintained evidence.",
 "disposition":"Changed files remain uncommitted for the named integrator; no pending transfer."}
```

## Failure behavior and portability limits

| Result | Required response |
| --- | --- |
| `busy` with `uncertain:false` | Bounded exponential backoff with jitter, or independent work. Never steal a lock. |
| `stale` with `uncertain:false` | Reread ownership/releases/inputs and rebuild the request after review. |
| Conflict, invalid data or capacity | Resolve that exact condition; do not spin or treat incomplete state as free. |
| Any `uncertain:true` | Stop dependent writes, acknowledgments and launches. Reconcile saved state and lock/job/output evidence before retry. |
| Process/test failure | Record the real result and remaining coverage; retain scope until its writers stop. |

A suitable busy delay starts around 25–50 ms and doubles to a 2–4 second jittered
window, with a bounded attempt count and overall deadline. No fairness or throughput
guarantee follows. The example intentionally uses a conservative global revision;
unrelated updates can invalidate review. A larger implementation may use scoped
review fingerprints only if it still scans all claims and preserves relevant
input ownership, unknown data and unchanged-byte release history.

The code uses stdlib operations available on Linux, macOS and Windows, rejects
links/reparse points and avoids POSIX-only locks. It assumes a reliable local
filesystem supporting exclusive directory creation and atomic replacement on one
volume. Actual qualification must run the tests on each chosen OS/filesystem;
source portability alone is not execution evidence. Cloud synchronization is not
a lock, and network filesystem semantics require separate qualification. Cross-host
boards require reliable shared storage and agreed physical resource identity.

The helper provides cooperative safety, atomic visibility and bounded machine
validation. It does not provide hostile-writer protection, power-loss durability,
truthful human/agent assertions, enforced Git isolation, source editor interception
or automatic recovery. It does not infer liveness from a transient tool PID. Use
[the lifecycle procedures](agent-lifecycle.md) for ambiguity and maintenance.

Run its focused regression suite with:

```sh
python3 -B -m unittest discover -s tests -p 'test_agent*.py'
```

Keep these tests in automatic tooling CI: real independent-process contention,
interrupted mutexes, stale input/revision checks, source-kind changes, atomic
handoffs, complete discovery, pending output lifetimes and injected publication/
cleanup failures matter more than tests that merely duplicate internal code.
