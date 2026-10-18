# Appended application implementation plan

<a id="current-continuation-handoff"></a>

## Current continuation handoff — 2026-10-18 UTC

Read this section before the historical design below. It reconciles the user's
requirements, the implementation at `30a6221e`, the later disk-full incident audit
and the retained execution evidence. **The integrated rich HTML/JavaScript viewer
is unfinished.** The most recent engine preparation failed before compilation;
its successful source/metadata phases do not make that preparation eligible.
This handoff did not launch a build, copy, browser, test matrix or release.

### Reading order and authority

1. Read the current `AGENTS.md`, the active user instructions and
   `/home/user/.codex/delegation-kit/policy.md`, then [the index](README.md),
   [building](building.md), [testing](testing.md) and
   [pending-record rules](../.agent-pending/README.md).
2. Read this current section, [implemented tools and limits](appended-applications.md)
   and the current pointer in [pending qualification](../.agent-pending/appended-kernel-qualification.md).
3. Read [validation](appended-validation.md), especially its final D03 runtime,
   source repair and disk-full paragraphs. Use
   [engine feasibility](appended-web-feasibility.md) for supplier/baseline rationale,
   not as a command to repeat an old cold build.
4. Open only the named current receipts below before the affected next operation.
   The ignored `BASE/ROOT-CHECKPOINT.md` is a chronological research log, not a
   launch authority. Its old final entry at 21:22 UTC predates the actual launch
   and failure; a new handoff pointer is appended without rewriting that history.
5. Consult the historical design below for requirements/rationale and the actual
   schemas/source for implemented interfaces. Proposed names below are not API facts.

Paths in this section are relative to the absolute checkout
`/home/user/___quick/p/_cur/dataPump/_lessonsLearned/software-foundation` unless
explicitly absolute. Set these aliases only for navigation; none is a launch:

```sh
cd /home/user/___quick/p/_cur/dataPump/_lessonsLearned/software-foundation
repo=$(pwd -P)
base="$repo/.agent-work/appended-implementation-20261016"
repair="$base/runtime-D03-repair-v1"
prep="$repair/provider/selective-continuation-v1/preparation"
concrete="$repair/provider/selective-continuation-v1/concrete"
donor="$base/editor-publisher-successful-donor-proposal-v1"
old_candidate="$donor/concrete-v2"
harness="$base/editor-repaired51-candidate-proposal-v1/runtime-readiness-v1/harness-route-audit"
runtime="$harness/runtime-after-successful-donor-v1/runtime"
foundation_prep="$base/rich-ui-foundation-integration-preparation-v1/implementation-v1/diagnostic/original_stream_v2/notes/foundation-construction-implementation-v1/both36-preparation-v1"
```

`BASE`, `P`, `C`, `N`, `C2`, `H`, `RUN` and `B36` in older records mean respectively
`base`, `prep`, `concrete`, `donor`, `old_candidate`, `harness`, `runtime` and
`foundation_prep` above. The old accepted preparation under `donor` is a different
source identity from the failed D03 preparation under `prep`.

### Preserved user intent and acceptance criteria

- Support four independently forkable project modes: neither layer, web only,
  portable binary only, or both. Preserve `fork.sh`'s independent application
  snapshot/attribution behavior. The ordinary foundation project selects neither.
- Web application sources live in `src-web-appended/`. Trusted bundled offline
  HTML/CSS/JavaScript are application code with native service access, with no
  security boundary from the internal renderer. One internal browser framework
  must handle rich editing/contenteditable, selection, dynamic DOM, tabs,
  spreadsheet-like editable areas, buttons and asynchronous application updates.
  The user's later clarification supersedes the earlier plaintext-editing limit.
- Edge, Chrome, Firefox and ChatGPT Desktop's external browser are lightweight
  development/test hosts. They are not alternative internal application engines.
  Do not claim arbitrary external browser-framework compatibility from this.
- Keep layout, application behavior and device protocols on the insulated
  application side. Pages call application C/C++/Rust services; they contain no
  backend-specific GUI, USB, OS or browser/Wasm adapter code. The engine produces
  generic document/bitmap capabilities for the application's GUI backends.
  A USB UART calculator page may call native UART/processing services; it does
  not create controls in a separate backend-specific application GUI.
- TUI must run the same HTML/JavaScript document, with w3m-like readable text,
  controls, focus and selection. Some unsupported presentation may degrade or be
  ignored; rare explicit ignore hints are acceptable. Do not impose equal rich
  graphical fidelity or require a second application UI. The proposed comment
  markers in the conversation are examples, not an implemented parser contract.
- Portable application sources live in `src-bin-appended/` and use only C, C++
  and Rust. No JavaScript code, references, SDK dependency or developer workflow
  belongs in that tree. Development scripts in other languages do not justify
  adding runtime/SDK language dependencies. The binary layer needs no JS engine.
- Native services are exposed through the stable registered value ABI. Trusted
  access does not imply portable raw function pointers or C++/Rust object layouts.
  All desired application functions can receive deliberate service wrappers;
  code/capabilities absent from a retained kernel require explicit maintenance.
- Replacing, adding or removing a web payload must compile nothing. Changing a
  portable payload may compile only that small platform-independent module.
  Both preserve the retained kernel prefix exactly, for Linux, Windows, browser
  carriers and TUI. Missing or incompatible retained inputs fail with concrete
  maintenance needs; cache-hit kernel builds are still forbidden in iteration.
- CI must compose new payloads with authenticated previous binaries or supplied
  base-binary archives, removing/replacing the old appended part without a full
  rebuild. Preserve origin, profile, toolchain and qualification identities.
  A source/tooling checkpoint is not a qualified runnable release.

### Checkout, preservation and policy differences

The local `main` HEAD is
`30a6221ea6437e3aa9fcdf97c5af9c7641e44357`, subject
`WIP - preserve appended application layers and rich engine integration`, parent
`b7aa3234a52ab08250dc2e0901c8dd03dfc5f31f`. No push was performed by this task.
The local `origin/main` tracking ref also points at this HEAD at handoff; this
handoff did not fetch or establish current server state. The commit
preserved 1,338 changed paths; all 2,051 complete tracked files were verified
against raw working bytes and executable modes. Git's full object check exited
zero with only pre-existing dangling-object notices. These are preservation
checks, not build passes.

Before this handoff, the only dirty files were user-owned `AGENTS.md` and
`.codex/config.toml`: they raise configured concurrency from 24 to 36 and remove
the old default Sol/Ultra paragraph/settings. Preserve them. The committed policy
and older conversation excerpts describe 24/Sol/Ultra; they are historical
snapshots, not a directive to restore those defaults. This chat also supplied a
managed instruction to read the external delegation kit; the actual repository
file does not contain that block. Do not silently reconcile these files. Load
current active instructions in the new chat, preserve the selected primary
model, and apply the kit's explicit role assignments rather than inventing a new
global child-model default. Runtime capacity in this chat is 25 total agents,
including the primary; 36 is not an available runtime guarantee. Missing external
policy/roles on another machine is a transfer prerequisite, not permission to guess.

This handoff additionally edits this plan, the documentation index and the pending
record, and appends the ignored checkpoint. It does not commit, stage or push
those edits. Keep them together when transferring to another checkout.

`BKP=.agent-work/wip-commit-20261017T232413Z` retains `COMMIT-VERIFIED.json`,
`PRE-COMMIT-CHECKS.json`, `SOURCE-BEFORE.json`, `STAGE-INPUTS.json`, the original
index/status and `source-before.tar`. The tar is 119,582,720 bytes, SHA-256
`b531f0bc6a4e8435223ed2c1eeb4dae1d6b25f8b9a98942705fefe5c7d949df6`;
all 2,051 archived files were read back. This is a source backup, **not a backup
of the retained SDKs/build products/evidence**. Preserve both the tar and ignored
artifacts; do not use `git clean`, reset, prune, destructive checkout or blanket
cleanup. The intentional pinned source archive `third_party/wasm3/upstream.tar.gz`
is tracked; generated engine binaries are not.

The full staged whitespace check at the WIP commit failed (exit 2): 1,154 trailing
whitespace and 12 blank-EOF warnings across 61 files, mostly exact supplier
sources/patches. Four non-recipe EOF warnings remain in `document_endpoint.hpp`
and the Windows dependency helper files identified in `PRE-COMMIT-CHECKS.json`.
Bytes were intentionally preserved. Do not call that check passed or rewrite
supplier sources just to remove those warnings. No build/test was repeated for
the commit.

### Implemented work and remaining integration

Implemented source includes project modes and fork integration; append containers,
inspection/replacement and retained-prefix tooling; the wasm3 module loader and
bounded value ABI; service discovery and module-owned providers; C/C++/Rust guest
SDKs and generic views; retained-input/engine maintenance admission; CI selection
and composition tooling; generic document, bitmap, forms, editing and TUI contracts;
single-owner engine/Driver/GUI source composition; native Linux/Windows producer
source and dependency policy. Use [the implemented guide](appended-applications.md)
for exact supported commands and [ABI definitions](../abi/appended/v1/README.md)
for wire semantics.

These facts do **not** establish an integrated rich viewer. Actual retained-group
admission, the Foundation kernel construction and combined web/module execution
are still unrun for the current source. Native ports and actual same-document TUI
execution remain unfinished/unverified. Component/mock checks cannot close those
gaps. Deferred guest jobs and real UART device services are unfinished; there is
no automatic retry of uncertain external effects. Initial rich source limitations
include one web region, a fixed unscaled 800×600 engine pane, a view-only bare
framebuffer path and no Windows ARM64 qualification.

The latest production repair normalizes both focus-dependent editor bits 1 and
16 during Begin only. On the old engine, a second Begin after Finish/ACK changed
flags from 4 to 21; the old normalization produced expected 5 and rejected 21,
yielding genuine native uncertainty without a lease. Current active publishers:

| Source | SHA-256 / bytes |
| --- | --- |
| `recipes/webkitwasm-document-v2/source/native/NativeDocumentV2Publisher.cpp` | `0705d9421e853b7633cc2a3df2c0448b0b53da0daf48fd2e7158f98b341b0453` / 80,117 |
| `recipes/webkitwasm-native-rich4083-v1/source/document-provider/native/NativeDocumentV2Publisher.cpp` | `204b4b97d131081e9ee77f3fff05ed7147ee496a89b4e08e24e7a0b9cc6e2c1b` / 110,553 |

Composition/undo/redo/unknown bits, other capture fields, both full-state rereads,
actual EditorClient context and selection guards remain strict. The test generator
extracts the real production guard instead of duplicating its logic. The older
`webkitwasm-native-v1` producer still has the old guard; do not modify that separate
historical producer merely to make every filename agree. Follow the admitted map.
Source, map/provenance and both native profiles were joined and independently
reviewed; no engine artifact containing this repair has been produced.

### Latest failed operation and incident chronology

| UTC on 2026-10-17 | Observed event |
| --- | --- |
| 21:22 | Last old `ROOT-CHECKPOINT.md` entry; preparation not yet launched. |
| 21:25:59 | Root armed the bounded preparation; saved launch intent. |
| 21:26:11–21:26:19 | Source phase completed and closed successfully. |
| 21:26:26 | Actual session 1866 handle saved; this is bookkeeping after launch. |
| 21:26:48 | Metadata phase completed; copy phase started. |
| 21:28:38.792399 | Copy failed with `ENOSPC` while exclusively creating `PlatformTextTrack.h`; target absent. |
| 21:28:51.952572 | Overall failed result published; copy exited one, reaped, no outliving descendants. |
| 21:28:56 | Original outer caller returned one. Later normal tool startup also hit disk-full before commands started. |
| 22:58:18 | Subsequent machine boot; previous visible journal ends 21:42:34, not proof of exact shutdown time. |
| 23:08 onward | Read-only incident audit; later local WIP preservation commit. |

The failed target is under
`P/reuse-v1/third_party/WebKit/Source/WebCore/platform/graphics/PlatformTextTrack.h`.
The error occurred creating a new file, not truncating a maintained source.
The later `bwrap` complaint about `.agents` was sandbox startup failure; `.agents`
remained a directory. A separate initially empty Root handle record was repaired
and validated before the incident after a Python string/bytes serialization
mistake; it is not evidence of disk-induced truncation.

Original current execution records (do not rewrite):

| Record relative to `P` | SHA-256 |
| --- | --- |
| `root-arming-v1/ROOT-LAUNCH-INTENT.json` | `c7f937015d61dab7c57be40d52367f4b55a4af255a0bcdd0ce52679448cd4c17` |
| `root-arming-v1/ROOT-ACTUAL-HANDLE.json` | `6e6b632fb0eee80c43d286ac5dd6dd1b24275ff3c0fac3da9462490df7f217f7` |
| `actual-v1/RESULT.json` | `40e9702ef24b77d6db85e41a3f0d0e67d970e7523b6ccad195458e65063255b8` |
| `actual-v1/copy.log` | `7757e054f7945fdb9398a71fb260b69cbaece4abb19f893c9c448dab2c5370e4` |
| `actual-v1/copy-CLOSURE.json` | `cf35007e729d8c53f2ec5a4056058d7bf859275dc040c30a92dafa6b15ae87de` |

**Observed integrity:** source output 368 files / 564,540,041 bytes and metadata
12 files / 106,263,995 bytes matched saved manifests. The partial copy's 37,650
files / 775,543,203 bytes matched hashes, lengths, modes, single-link and separate
inode checks, and the exact ordered prefix. Its 34 empty files were expected.
There are 5,129 absent file entries / 86,259,650 bytes, including the final proof
seal; the complete expected copy is 42,779 files / 861,802,853 bytes. There is no
`REUSE-COPY-RESULT.json`, `reuse-v1/reuse-proof.json` or
`ROOT-CALLER-CLOSED-ACCEPTED.json` for this preparation. New actual/retained plan
and candidate output directories under `C` were absent. No compiler/linker/SDK
program or subsequent runtime ran.

The audit also verified the maintained D03 source/test/metadata cohorts, 49
GUI/module/application sources, the earlier 171 candidate artifacts, runtime
capsule/inputs, all 19,426 paired Foundation SDK files / 2,871,026,200 bytes,
guest tool/input records and Windows sealed cohorts. A 1,532,710-file timestamp
census found no maintained Git-visible file changed in the incident window.
This supports **no observed loss in the audited source WIP**; it cannot establish
all unsaved editor buffers or historical bytes of unsealed files. Original
copy hashes/counts are evidence, not a qualification pass.

Storage was Btrfs `/dev/nvme0n1p3[/@rootfs]`: a prelaunch snapshot showed about
25 GB available; after reboot/audit about 31 GB, and this handoff about 30 GB.
Those observations do not explain the incident. Btrfs data/metadata allocation,
external consumption and exact exhaustion/recovery remain unknown; privileged
allocation/system-journal data were unavailable. `df -i` showing 0/0 is not proof
of inode exhaustion on Btrfs. Verify current allocation/capacity and jobs before
another copy. Do not infer space safety solely from the later free-byte number.

### Evidence ledger: passes, failures, unrun and deferred

All results below are **retained**, not rerun by this handoff. Source identity
comes from each receipt, not from the commit date. Byte/hash equality is needed
for reuse; where physical identity is part of admission, preserve/revalidate it.
Copying a checkout or SDK changes identity and cannot be repaired by restamping
old receipts. A changed source/test/config/dependency/environment invalidates only
the affected scope; retain original results with their original identities.

| Status / scope | Result and command authority | Evidence / reuse limit |
| --- | --- | --- |
| Passed: current D03 host checks | Session 80384, caller 0; 63 C++ checks (35 retained + 28 focus), 13 Python methods, zero skips. Exact supported command below. | `repair/provider/implementation/{FINAL-RELEASE.json,HOST-CHECK-v1.log,CALLER-CLOSED-v1.json}`; release `b90b0dd0b36792e664c0f5683f6a03f52516274b4a588b463d92db6165f48d2b`. GNU 14.2, Python 3.13.5, CMake 3.31.6/Ninja, Debug C++ provider; one host object/link, no engine. |
| Passed: source metadata | Session 20932, 44 tests, 1.238 s, failures/skips zero. Exact argv was not retained in the compact release/log; do not invent it. | `repair/provider/metadata/{CLOSED-RELEASE.json,document-sources-normal.log}`; release `158a6b3b96bf277bae3d515c24ba92f8086811cf2fe79c6e528326aad312eaea`; test module `tests/test_appended_engine_document_sources.py`. Native join `repair/native-profile-join/CLOSED.json` `cc3af533417e736804b9799911cbb5a1eb5e4bb239e1c9512f3bdb3c0b8d7634`. No SDK/compiler. |
| Passed: previous selective engine | Plan 45979 and build 6155: 49 object imports, two fresh units, five archive copies, zero repacks, one link; static inspection passed. Original commands are in `old_candidate` plan/build packets and command records. | `old_candidate/ROOT-CANDIDATE-CALLER-CLOSED-ACCEPTED.json` `4a72a630d52bd32181fbcbfdae78538daa94473e1a8d3209c3b3b996809df087`; original flat result `83613c5b5a4a784d41261184c798a40870fee3b7a69ae289cb0f9159f47d3b11`, 171 artifacts. This uses the old Publisher, not current `0705…`. |
| Passed: donor/capsule metadata | Donor capture 35055; capsule copy 84036, 2.935 s, 16 files / 164,721,294 bytes. Launch commands are in original launch intents; no SDK program/engine/browser. | `donor/donor-selection-v3/SUCCESSFUL-DONOR.json` `4b1e4b4d34ac631d2a78792f786b08a5f7986ab3d51995cae3d35a8de1acd251`; `base/root-donor-reader64-review-v1/ROOT-CAPSULE-COPY-ACCEPTANCE.json` `728ce27cb45835be425449b7a0e6b13e6a614a843293e782283e9091bb711a2e`. Fourteen original copies + two derived files; donor/commands external, not a seventeenth copy. |
| Failed: actual offline rich runtime | Session 41837, caller 1, 14.827 s: 31 original application assertions and D01's 51 controls passed; D03 failed second Begin after 10 query assertions. Two Node inert/refusal checks passed; zero browser batches completed. | `base/root-runtime-successful-donor-v1/{ROOT-LAUNCH-INTENT.json,ROOT-CALLER-CLOSED-FAILED.json}`; failed closure `9c06895ee4cc958a58cf6f5859a1e11acba5f422abdeba5bd033a7a612d783e1`; `runtime/actual-operation-v1/result.json` `f5998b69edf8489071720829ca10bbcc1d424b9b4b254d6866b40ae46c6f439b`. All 47 inputs unchanged, owners/streams/monitor closed; not a runtime pass. |
| Passed phases / failed whole: current preparation | Session 1866, caller 1, 160.889 s. Source and metadata closed 0; copy ENOSPC. Original exact phase argv is in `P/actual-v1/RESULT.json`; outer argv below is historical only. | Incident records above. No current-source engine object/link/runtime produced; incomplete copy is ineligible. |
| Passed: combined C guest production | Session 40480, caller 0, 1.279 s, four C compiles + one link. Exact commands/SDK joins in original module compile receipt and launch packet. | `foundation_prep/guest-compile-packet-v1/successor-v5/ROOT-CALLER-CLOSED-ACCEPTED.json` `8ea854422672eb1bbe1fc638de525b4c59f55577ef47d43cf237f11d6d7ccce9`; module `f608dce340e731a53f42da2ef3e436ee49c3f8dda3f16a82e5005643301b9588`, 13,660 bytes; receipt `1a97cf34ee5f01a4ca20e25872fa36e9c6095ae08c7579ff8add10b930510033`. Actual combined runtime unrun. |
| Passed compile / unrun tests: current Rust guest | Session 62993, caller 0, four commands, current canonical-field decoder. | `base/root-rust-sdk-compile-check-v1/{INTENT.json,CLOSED.json,calculator-rust.compile.json}`; module `72e6b87b7d62d38c7ac3f081ebb2497d1d53e3be9e4e44e4495d857e7a58e52e`, 17,898 bytes; receipt `d3ee8cbf3d3f5c18b4a9133250dcd67754c05adbbf80a414852e0f2e45041b78`. Rust 1.84 / wasm32v1-none. Current unit tests have zero executed assertions: matching host std absent. Current decoder runtime unrun; earlier checked-add/overflow execution belongs to older identity. |
| Passed: current four-mode package fixtures | Session 87214, 18 CLI calls: 17 success plus expected empty-neither refusal; web/binary/both pack/inspect/verify passed. Exact argv inventory retained. | `base/root-current-payload-pack-v1/successor-v2/{COMMANDS.json,RESULT.json,ROOT-INTAKE.json}`. Web 60,085 bytes, binary 14,597, both 74,103. Uses external `f608…` module; explicitly no source-to-module binding to copied examples. No carrier/engine/kernel runtime. |
| Passed components / unrun construction | Four document CTests: 432 assertions, session 25220; GUI semantic 744, bitmap 4 and terminal 6 checks have their separate mock identities. Foundation preparation has 18 inert + 4 cache + 7 host-token + 73 recorder cases; partial BOTH has 52 harness + 31 membership cases. | Detailed original identities/logs in validation and `foundation_prep`; no actual 36-TU Foundation construction, combined BOTH execution, eligible native provider or same-document TUI runtime pass. Do not total unrelated identities as one suite. |
| Passed source fixtures / unrun native | Windows final source tools: 139 canonical methods; retained-source inspection joins 197 inputs. Linux/native syntax scopes have separate outcomes. | Validation and Windows handoffs. No actual Windows provider/SDK or native application runtime. Native004 Combined syntax passed while Publisher failed; Native006 Publisher-only passed and does not rerun Combined. Copied syntax004 uncertainty remains quarantined, not repaired retroactively. |
| Deferred extensive qualification | Complete platform/backend, sanitizer/portability, SDK consumer, installed package, browser policy, certification, CI and release scopes. | Pending record/procedures. Not authorized merely by implementation, commit or handoff; no queued test is a pass. |

The exact passing D03 host command, **for reference, not a request to rerun**:

```sh
./build.sh test dev --core-provider cpp \
  --build-dir "$repair/provider/implementation/host-build-v1" \
  --build-jobs 1 --test-jobs 1 \
  --test foundation.appended.document-label-association \
  --test tools.document_label_association_fixture
```

The original failed preparation outer argv was
`/usr/bin/python3.13 -BE "$prep/run_preparation.py"`. **Do not execute it again.**
It takes no arguments, binds `PACKET_PIN` in source and refuses existing outputs.
Adding `--packet-sha256` supplies no gate; surplus argv is ignored. Its current
armed runner hash is `d47fa6375cf97aae1c7316d069d85c42165269720c656e3ec8c2505cfc40874c`;
packet `87af60cd94185ce5ff0dfcc4328bc30f6bf560a3dd7d2ce4659321cf92d0c8b3`,
catalog `3022e106323f409635db38c2fa08b520ecc1af8b454ca699c040427d45be9505`,
materializer `68c893ecd426a8b9248757ec431b31a2cd20d18491f89be493ec3d3cfced50d5`.
The final-disabled freeze is historical; Root's later arming intent is current.

The original runtime launch's exact argv/pins are in Root's intent above. Its
shape is `/usr/bin/python3.13 -BE ENTRY --packet PACKET --packet-sha256 SHA
--execute --root-authorization AUTH --root-authorization-sha256 SHA`, using the
natural relocated package. Do not add `-I`: that removes the required script
import directory. Old packet/auth/output paths are single-attempt history, not
reusable grants. Actual browser/Node IPC used an approved escalated loopback route
because the ordinary tool sandbox returned EPERM. That route needs the current
harness's actual permissions; do not silently substitute an unqualified launch.

### Retained inputs, known traps and transfer needs

- Keep all of `BASE`, its evidence/manifests and the existing SDK/tool roots named
  inside receipts. A Git clone or source tar alone cannot resume the selective
  path. The current SDK inventory was audited once; do not walk its 19,426 files
  again solely because a chat changed. Revalidate relevant admission inputs when
  state/environment changes or a new operation requires fresh physical facts.
- Current assembled source records are `P/sources-v1/recipe.json`
  `a2df92fd577865931f36d70f7262a95038e3ebb43bae3197e3e5154c241b29b3`,
  `sources.json` `64aa9022eafe5e68f23c1fa2742a7fa30110ed4105c36faf5feafa6052f27599`
  and `provenance/source-projection.json`
  `6fef5ea2d9e65ec0dc646bc51b7f864bbc17454324aa15ea99b99fd1f868c369`.
  Metadata is in `P/reuse-metadata-v1/{ASSEMBLY.json,metadata-root/}`. These remain
  valid observed phase outputs, not an accepted complete preparation.
- Old candidate Wasm is `d201800d2669be0d18e54c6d7182b1af6e03f03004c0b6a9c434e915103ef84f`
  / 109,675,754 bytes; factory
  `83fc7ea68abc2048bf899ad2dcf23a6139ba7d7d86c8ad198154d330a706ab7f`.
  It is a retained donor/diagnostic, not current repaired output or a release.
- Current metadata readers are the donor-64-MiB successor under
  `foundation_prep/successful-donor-intake-successor-v1/donor-descriptor-64m-successor-v1/`.
  Its capsule `contracts.py` is `856eb7e6bbf4ff7564841c502699e9c9a37ea2297c9550ebbaa055a10e449768`;
  runtime contracts are `cfe22f4e4513aa494d5b6a03e31d89e10d5e752f086445b419b7bd9fbca7c886`.
  Older 8-MiB donor readers reject the actual 19-MiB descriptor. Only donor
  metadata gets 64 MiB; command/legacy limits stay 8 MiB. Do not enlarge unrelated
  payload limits or recapture the successful donor merely to resume.
- The preliminary `C` plan/build packets and `SOURCE-FREEZE.json` are disabled
  templates awaiting actual accepted new prep/physical pins. They are not launched
  jobs. Read their handoff before binding a successor; don't alias the old plan.
- A metadata catalog race was explicitly reconciled before launch: original
  `bace…` catalog path was replaced under an already-issued grant by `59b…`,
  with old bytes retained as a read-only preimage. Root accepted exactly three
  changed control rows, later mechanically armed to `3022…`. Do not claim the
  old path/inode remained immutable, revert it or restamp historical evidence.
- The runtime `actual-uncertainty-dispatch-return` event only observes native
  uncertainty. The initial fault-injection hypothesis was retracted. Do not
  disable the case, replay its uncertain native action or weaken Begin guards.
- The earlier C guest wrapper failures (exit 137; then a short-lived PID RSS
  sampling race) remain failed; the narrow known-owned-PID ENOENT repair has its
  own passed successor. Preserve the original failures and qualified helpers.
- Minor stale prose: `docs/ci.md` says “no setup barrier” although four jobs depend
  on `retained-selection`. Treat workflow/source as authority; this editorial
  inconsistency was not fixed during the WIP commit. An older whole-repo docs
  check had nine unrelated generated-link failures; it is not a passing result.
- A transfer to another checkout/machine requires the ignored retained roots,
  external delegation policy/roles and matched tools, plus new checked identity
  admission. Do not make moved files eligible by rewriting old physical records.
  Missing retained inputs are a concrete recovery need, never a full-build trigger.

### Ownership, authorization and resource ceilings

All recorded old implementation writers released their scopes/read holds; their
jobs/streams were closed before this handoff. No old tool session is resumable
after the reboot. Old principal workstreams were `appended_browser_kernel`
(engine/GUI/native sources), `document_source_refresh` (capsule/runtime/Foundation)
and `windows_engine_path` (Windows/profile joins). They are historical owners,
not grants to a new chat. The handoff used two bounded read-only reviewers; Root
owns only the documentation/checkpoint edits. No implementation job was launched.
Check current jobs/claims and acquire fresh ownership before writes. A restricted
PID namespace is not a host-wide absence proof. Do not infer release from a stale
timestamp. Use the existing coordination mode/records; independent writers or
uncertain ownership require the checked shared protocol, never a second board.

The user's implementation authorization and explicit **“Run the bounded engine
probe”** permit the reviewed retained selective diagnostic and necessary focused
repairs, within its established scope. No repeated permission is needed for that
same concrete bounded work after safe prerequisites and source review. This is
not authorization for a cold native/dependency/engine build, automatic fallback,
broad regression matrix, publishing, Actions launch or a qualified release.
Generic WIP commit/handoff requests add no extensive-qualification authority.
Prepare a concrete scope/cost and request only genuinely additional expensive work.

| Operation | Existing ceiling / invariant |
| --- | --- |
| Preparation | 600 s whole, 15 s cleanup; source 180 s, metadata 90 s, copy 120 s. Output source 1 GiB, metadata 256 MiB, copy 2 GiB, evidence 16 MiB, phase log 2 MiB. No compiler/linker/SDK program. |
| Selective plan | 240 s work + 15 s cleanup; metadata-only, no compiler or linker. |
| Selective build | 3,300 s work + 30 s cleanup, 2,700 s inner build, jobs 1, sampled RSS 4 GiB, 24 processes, growth 8 GiB; minimum free 4 GiB and launch free 16 GiB. Storage incident requires additional current Btrfs confidence, not a budget increase. |
| Offline runtime | One attempt; 360 s whole / 330 activity / 15 cleanup / 15 postflight; 180 s aggregate Worker, 90 startup, 30 Node; sampled RSS 4 GiB, output 512 MiB. Exactly 65 cases / 12 batches; no retry of uncertain effects. |

Record launch intent before each long command, actual yielded handle when known,
then original caller exit and qualified closure at the next checkpoint. Finish
children, streams, monitors and queued writes before release. Reuse reviewed
helpers/contracts; do not grow another evidence framework to restart one copy.

### Dependency-ordered safe resume

The following passive commands inspect state; they do not rerun tests or builds:

```sh
git status --short --branch
git log -1 --format=fuller
git diff -- AGENTS.md .codex/config.toml
df -h "$repo"
findmnt -T "$repo" -o SOURCE,FSTYPE,OPTIONS
sed -n '1,200p' "$prep/actual-v1/RESULT.json"
sed -n '1,200p' "$prep/root-arming-v1/ROOT-LAUNCH-INTENT.json"
sed -n '1,160p' "$concrete/HANDOFF.md"
```

Use actual host/process and Btrfs allocation information available to the current
harness; do not run a new multi-million-file census. Preserve any unexpected
changes/owners and resolve the affected scope before launching. Then:

1. **Recover preparation only.** Establish storage capacity/allocation and fresh
   exclusive output ownership. Preserve failed `P` and all old donor products.
   Design the smallest checked fresh-namespace copy/preparation continuation from
   the existing reviewed helpers. Valid source/metadata phase outputs may be
   reused only with complete current admission/binding; the partial copy cannot.
   Review a concrete packet/pins/absence guards before arming. Do not merely change
   `ARMED`, rerun `P`, resume copying in place or add a cold-build fallback.
   Completion: all expected copied inputs plus final proof, natural closures,
   unchanged inputs and independent Root closed preparation acceptance equivalent
   to old `07706204…`, for the current repair/source identity.
2. **Bind and run the compile-free selective plan.** Refresh `C`'s disabled
   templates to accepted current source/proof/output paths and actual physical
   facts. Completion: closed accepted plan explicitly admits 49 old objects/five
   archives and plans only two fresh units, zero archive repacks and one link.
   Unexpected recompilation is a failed prerequisite, not permission to proceed.
3. **Produce the repaired candidate.** Within existing caps, import those 49
   objects, compile only Publisher + document shim, copy five archives and link
   once. Completion: original flat caller result, strict inspection and Root's
   exact 17-field/171-artifact readback; no aliases to old candidate receipts.
   Candidate records must retain original closed/plan/maintenance/inspection/
   commands/donor lineage and complete hashes/physical facts. Production eligible
   stays false until downstream gates pass.
4. **Bind metadata capsule and repeat the same actual offline protocol once.**
   Use the released 64-MiB donor readers and qualified relocated supervisor;
   update data bindings, not case expectations. Preserve 65 cases: 13 positive,
   10 clipboard, 15 editor, editor/form uncertainty, navigation, 10 popup-A,
   10 popup-B, cancel positive/unknown, raster-off and Worker failure. Obtain a
   fresh Root packet/auth/output identity and approved actual loopback route.
   Completion: every named case/batch executes and passes; input postflight,
   natural closure, output/RSS limits and full cleanup pass. D03 must reach
   typedRead/replacement successfully; a partial assertion count is insufficient.
5. **Admit the real neutral group.** After actual runtime passes, execute the
   retained 28 + 6 neutral controls and derive the four independent recipe,
   manifest, proof and runtime pins. Completion: eligible retained group through
   the existing strict consumer; never use `--developer-unqualified` to invent
   missing runtime/profile facts.
6. **Construct Foundation from the retained SDK.** Follow the settled Foundation
   preparation under `B36`, using its source projection/SDK authority. Planned
   work is 36 units (22 C++, 14 C), 18 archives and 73 recorder captures, with no
   engine rebuild. Do not recopy all 883 isolated source files merely because
   unrelated top-level docs/registration changed. Reconcile the known scoped
   input projection; fail on relevant mismatches. Completion: actual supported
   construction, compiled profile/DESCRIBE match and closed Foundation receipt.
7. **Run the retained partial BOTH integration.** Reuse the accepted `f608…` C
   guest and its original compile receipt, one EngineOwner/module binding and
   one presenter/outer loop. The prepared scenario checks provider echo/ingress,
   startup ownership and bitmap presentation. Completion is the actual declared
   partial scenario, not full E01/all 32 features; keep that distinction recorded.
8. **Finish native/TUI and application behavior.** Identify remaining actual
   provider/SDK/Loader → Driver → semantic/bitmap gaps. Native cold production
   needs separate authorization/cost if required. Demonstrate rich edits,
   asynchronous application/native calls and same-document TUI behavior through
   the insulated boundary. Add missing capabilities generically, without putting
   feature layout in backend adapters or JS in the portable SDK.
9. **Qualify/deliver only when requested.** Reuse valid focused evidence; perform
   applicable complete platform/SDK/package/browser/release gates under an
   explicit extensive-validation or release request. Prove web edits invoke zero
   compilation, portable edits compile only the module, all four modes preserve
   exact retained prefixes and CI composition uses eligible retained binaries.
   Pending gates mean pending publication. No push or publication is implied here.

## Historical design and original implementation plan

Historical status, 2026-10-16: proposal and implementation handoff. No appended runtime,
payload compiler, container format or composition release workflow is implemented
by this document. Subsequent implementation is recorded in
[current tools and limits](appended-applications.md); consult that page and the
actual schemas rather than treating every proposed stage below as complete.
Names, schemas, signatures and commands explicitly described as
proposed below are design inputs, not existing interfaces or passing evidence.

Implement two independently optional application layers above reusable compiled
kernel binaries: rich offline HTML/CSS/JavaScript from `src-web-appended/`, and
portable C/C++/Rust modules from `src-bin-appended/`. Once a compatible kernel has
been built, replacing either payload must preserve its exact bytes and must not
compile or relink any kernel. Ordinary applications using neither layer remain
supported without either layer's runtime or SDK dependencies.

The original handoff was intended to be sufficient for an implementing agent, including
GPT-6.1 Sol at Ultra effort, without access to the preceding conversation. User
requirements and the repository's governing instructions remain authoritative.
The original planning request authorized planning and documentation. A subsequent
request authorized implementation; current implemented behavior and remaining gaps
are recorded in [appended applications](appended-applications.md). Extensive
qualification, costly engine probes, CI dispatch and publication retain their
separate authorization rules.

## Historical reading and execution order

This was the initial planning sequence. Resume from the
[current continuation handoff](#current-continuation-handoff); do not restart
settled dependency/ABI/container investigations or use old model defaults.

1. Read [AGENTS](../AGENTS.md), the [documentation index](README.md),
   [architecture](architecture.md), [GUI boundary](gui-boundary.md),
   [building](building.md), [testing](testing.md) and relevant pending records.
2. Read the requirements, four modes and feasibility gates below before selecting
   dependencies or writing implementation. A familiar library is not evidence
   that it meets the combined requirements.
3. Follow the staged work packages. The binary ABI, project configuration and
   packaging work can progress independently of rich-engine feasibility; do not
   claim the complete feature finished while that gate remains unresolved.
4. Preserve source identities, existing dirty work and ownership. Use the
   applicable coordination mode. Delegate disjoint workstreams concurrently,
   using the repository's configured model and effort defaults.
5. During a later implementation request, run discriminating focused checks.
   Extensive platform/release qualification follows the manual authorization
   policy; this plan creates no background jobs or blanket qualification approval.

Navigation: [requirements](#requirements-and-nonnegotiable-boundaries),
[current code](#current-repository-integration-points),
[project modes](#project-modes-and-forked-applications),
[architecture](#runtime-architecture-and-ownership),
[web framework](#rich-web-framework-and-terminal-presentation),
[binary ABI](#portable-binary-profile-and-application-abi),
[containers and releases](#append-containers-and-release-composition),
[work packages](#implementation-work-packages),
[acceptance](#acceptance-and-validation),
[agent handoff](#instructions-for-the-implementing-agent).

## Requirements and nonnegotiable boundaries

| ID | Required behavior | Acceptance owner |
| --- | --- | --- |
| A01 | Support neither payload, web only, binary only and both in independent projects created with `fork.sh`. | Configuration, fork and mode tests |
| A02 | Keep application behavior, layout, conditional UI and device-protocol meaning on the application side of the GUI boundary. | Insulation checks and runtime fixtures |
| A03 | Web applications contain no GUI-backend, OS-device-driver or browser-Wasm implementation code. HTML controls are translated automatically. | Identical-bundle execution and source/dependency checks |
| A04 | Use one internal web framework/document and event model, including rich editing. External browsers are development/test hosts. | Rich-engine feasibility and conformance |
| A05 | Include rich `contenteditable`, dynamic DOM, tabs, editable spreadsheet-like areas, selection-driven updates and asynchronous interactions. A calculator alone is insufficient. | Rich editor and spreadsheet fixtures |
| A06 | Provide w3m-like terminal presentation of the same document and running application. Degradation and rare optional exclusion hints are allowed. | Terminal interaction fixtures |
| A07 | `src-bin-appended/` developer code uses only C/C++/Rust; its tree never contains or refers to JavaScript code. No script glue or web-toolchain dependency enters the binary developer SDK. | Binary source/SDK audit and isolated build/run |
| A08 | Compile the binary payload once to a documented portable format, with the same module bytes usable by every compatible supported target. | Module hash and runtime conformance |
| A09 | Both payloads are trusted application code with access to the exported application service surface. This is an ABI/insulation boundary, not a hostile-code security boundary. | ABI and service fixtures |
| A10 | Append, remove and replace payloads without compiling, linking or rewriting the retained kernel prefix. Never accumulate old payloads. | Composer and carrier tests |
| A11 | Reuse authenticated prior compatible release kernels or a pinned kernel tar/zip. Missing/incompatible inputs fail without an automatic rebuild. | CLI and Actions process/inventory tests |
| A12 | Keep optional dependency closure small. A language used in CI does not justify shipping its runtime, package manager or SDK to application developers. | Mode-specific dependency inventories |
| A13 | Preserve offline operation, existing support baselines and recovery/provenance requirements. | Resource, dependency and release checks |
| A14 | Make build classification and agent guidance enforce payload-only iteration, with full kernel work only when affected implementation requires it. | Change-selector and wrapper tests |

"Full access" means that any application function can be deliberately exposed
through the stable service interface, without a plugin permission ceremony.
Native classes, templates, allocator state, Rust layouts and raw function pointers
are not portable call representations. Register/generated-wrap the needed native
functions and keep them reachable during linking. A retained kernel cannot supply
functionality that was never compiled into it. Adding such functionality needs a
new kernel generation; new application behavior composed from existing services
does not. Browser-hosted services remain subject to the actual browser/OS
capabilities; return generic unsupported/permission/error results through the
service API instead of requiring platform branches in the payload.

The user accepted a documented internal web platform, but subsequently required
rich functionality. Do not revert to plaintext-only editing or static forms.
Supporting every arbitrary third-party browser framework is not a requirement:
software-foundation provides one maintained internal framework. Edge, Chrome,
Firefox and the embedded browser available in ChatGPT Desktop are relevant
external lightweight development/test hosts. Do not infer the latter's engine or
privileged integration from its product name.

## Current repository integration points

Planning baseline: `b7aa3234a52ab08250dc2e0901c8dd03dfc5f31f`.
Reinspect current source before implementation; file contents may have advanced.

| Existing location | Relevant behavior and required integration |
| --- | --- |
| [gui/shared/application.hpp](../gui/shared/application.hpp), [application.cpp](../gui/shared/application.cpp) | Shared application state, events, tasks and services. Add a separate appended composition implementation; keep the ordinary example path working. |
| [gui/host/contract.hpp](../gui/host/contract.hpp), [browser.hpp](../gui/host/browser.hpp) | Generic `Application`, `Session` and `Browser<App>` seams. Reuse these for lifecycle/event integration. |
| [gui/hosts/wasm_main.cpp](../gui/hosts/wasm_main.cpp), [gui/CMakeLists.txt](../gui/CMakeLists.txt) | Existing browser create/receive/destroy exports and target graph. Generic module/resource loading must be prepared in the kernel once. |
| [gui/check_boundary.py](../gui/check_boundary.py), [boundary tests](../tests/test_gui_boundary.py) | Extend scanning/dependency coverage to the new application and runtime scopes; do not create an insulation blind spot. |
| [browser embedding](browser-embedding.md), [gui/host/browser_embedding.mjs](../gui/host/browser_embedding.mjs) | Existing isolated output renderer, trusted parent and Worker. Trusted appended code belongs on the application side, not in the isolated renderer iframe. |
| [src/text_validation.h](../src/text_validation.h), [Rust policy](rust-hybrid-plan.md) | Existing private static native C ABI, not a portable plugin ABI. Preserve its baseline and treat guest SDK policy separately. |
| [tools/build.py](../tools/build.py), [CMakeLists.txt](../CMakeLists.txt) | Supported entry point and target graph. Add explicit appended actions without bypassing the established build system. |
| [tools/package_wasm.py](../tools/package_wasm.py), [tools/import_wasm.py](../tools/import_wasm.py), [cmake/ImportWasm.cmake](../cmake/ImportWasm.cmake) | Current browser package and native import bind complete source identities. New composition schemas must preserve legacy verification. |
| [tools/source_identity.py](../tools/source_identity.py), [tools/release.py](../tools/release.py), [tools/github_release.py](../tools/github_release.py) | Complete source/artifact checks cannot simply be skipped to reuse kernels. Add explicit component/composition identities. |
| [tools/ci_changes.py](../tools/ci_changes.py), [tools/ci_plan.py](../tools/ci_plan.py) | Unknown paths/missing comparison evidence currently select broad work. Add precise payload classification and a retained-only route that never escalates to kernel builds. |
| [.github/scripts/lifecycle.py](../.github/scripts/lifecycle.py), [Latest workflow](../.github/workflows/_release-latest.yml) | Existing release route invokes application producers and full gates. Add a separate composition route with its own truthful evidence policy. |
| [fork.sh](../fork.sh), [tests/test_fork.py](../tests/test_fork.py), [fork documentation](../README.md#start-a-new-repository) | Exact source tree in a new independent root, no remote/ancestry dependency. Optional configuration must preserve this behavior. |

At the initial planning baseline, no embedded HTML engine, appended executable
loader, stable portable module ABI or UART service was found. The subsequent
loader/ABI/provider implementation is recorded in
[current tools and limits](appended-applications.md). The current GUI C++
contract requires matching builds when layouts change; do not publish it as the
new binary ABI. Current native/browser bitmap paths are not complete rich-editor
input or accessibility interfaces. The existing terminal adapter maps generic
views to cells; it does not implement HTML document reflow.

The [pending GUI qualification](../.agent-pending/gui-boundary-qualification.md)
and [offline qualification](../.agent-pending/offline-platform-qualification.md)
retain their original sources and limits. They do not qualify these proposed
features. Planning gaps belong here; create new pending qualification records only
for applicable implementation handoffs under the pending-record guide.

## Project modes and forked applications

Use a proposed tracked `foundation-project.json` as the single application
configuration consumed by the wrapper, CMake configuration, packaging and Actions.
Choose equivalent naming before implementation if established repository practice
requires it; do not create competing configuration authorities. Missing new
configuration must preserve existing ordinary build behavior.

Proposed illustrative shape, not an implemented schema:

```json
{
  "schema_version": 1,
  "application": {
    "id": "org.example.instrument",
    "name": "Instrument",
    "version": "0.1.0"
  },
  "appended": {
    "web": {"enabled": false, "source": "src-web-appended"},
    "binary": {"enabled": false, "source": "src-bin-appended"}
  },
  "startup": {"primary": "compiled"},
  "kernel": {"selection": "project", "profile": "minimal"}
}
```

Validate unknown fields/versions, duplicate JSON keys, paths and inconsistent
combinations. An enabled source must exist; a disabled source need not exist and
must not be inspected as a prerequisite. Example directories do not enable a
feature. An enabled web component must have valid declared entry points and an
enabled binary component must produce a verified portable module; directory
existence alone is insufficient. Keep product identity, enabled payloads, selected
platforms/backends and kernel capability profile as separate dimensions.

| Mode | Application source roots | Smallest required kernel capabilities |
| --- | --- | --- |
| Neither | Ordinary `src/`, `rust/`, shared GUI code as selected | Existing compiled application, no appended loaders/runtimes |
| Web only | Ordinary sources plus `src-web-appended/` | Resource container and rich web framework, no appended-module SDK/runtime requirement |
| Binary only | Ordinary sources plus `src-bin-appended/` | Portable module runtime, service ABI and optional generic view bridge; no website or JavaScript engine requirement |
| Both | Ordinary sources plus both payload roots | Both capabilities and their shared service registry |

In binary-only mode, GUI code is written through C/C++/Rust view bindings.
It must not secretly generate or require a script application. In web-only mode,
the page can call compiled kernel functions directly through the website bridge.
Neither mode requires a dummy payload for the other. Either layer can be combined
with compiled application functionality; they need not replace the entire product.

Payload presence is independent of compiled capabilities. A deliberately selected
`both` kernel may ship one or no payloads, but removing a payload does not remove
its already-linked runtime. Default to the smallest compatible retained profile;
do not silently ship both runtimes for convenience. If a profile is unavailable,
report that fact without invoking a compiler. Enabling a missing capability needs
a different prebuilt kernel or an explicit kernel-maintenance operation.

Preserve `fork.sh`'s root tree/index, independent complete history, no-remote and
provenance behavior. Configuration convenience options, if added, make reviewable
post-snapshot working-tree edits just as attribution edits do today. They do not
rewrite the root snapshot or prune source during cloning. The foundation's default
is neither; forks of customized projects normally retain their tracked settings.
Keep traditional Bourne/Dash support; a convenience selector must not add a web
toolchain or new interpreter prerequisite to forking.

`PROJECT_NAME` currently affects destination/output, not every product identifier.
Implement product naming deliberately across archive/package names, launchers,
desktop metadata, install namespace and release destinations. Preserve stable
internal ABI identifiers and original kernel provenance. Runtime display names
and application version can come from the composition descriptor; do not patch
retained executable bytes to rebrand them. OS metadata baked into a binary remains
part of that kernel's identity and may require a separately produced kernel.

A fork may select a verified software-foundation kernel or a project-owned kernel.
Keep the kernel download source (explicit repository/release/asset hashes or local
tar/zip) separate from the downstream publication repository and credentials.
Never infer a remote from the discarded clone location or publish upstream.
Do not require upstream Git ancestry: the source commit object is intentionally
absent from the independent fork. Match verified component contents and contracts.
Retain notices, reconstruction inputs and applicable redistribution conditions.

## Runtime architecture and ownership

```text
src-web-appended/                 src-bin-appended/
HTML / CSS / JS / resources       C / C++ / Rust -> portable module
            |                                  |
 shared web framework                    module runtime
 DOM / editing / events                         |
            |                                   |
 website-only binding ---- stable application service registry
            |                                   |
 shared presentation       generic value-based view declarations
            +----------------+------------------+
                             |
                   AppendedApplication
             generic Snapshot / Event / services
                             |
                    existing GUI adapters

Kernel application services -> generic device/platform providers
```

Proposed ownership map:

| Scope | Responsibility |
| --- | --- |
| `src-web-appended/` | Product pages, scripts, styling and resource manifest only |
| `src-bin-appended/` | Product C/C++/Rust sources and necessary language/build metadata only |
| `src/appended/` | Kernel-owned container reader, dispatcher, registry, module-runtime adapter and lifecycle |
| `src/appended/web/` | One selected web framework integration, resource resolver, rich editing and graphical/text presentation |
| `include/foundation/appended/` | Public project-owned value interfaces and stable C ABI |
| `abi/appended/v1/` | Kernel-provided transport/service/view schemas and operation ID ledgers, outside payload source roots |
| `sdk/appended/` | Generated C/C++/Rust guest bindings and lean guest library recipe |
| `gui/shared/appended_application.*` | Application composition implementing the generic host concept |
| `tools/appended_*.py` | Build-wrapper helpers, packing, identity, verification and dependency checks; existing Python tooling does not become a shipped app runtime |
| `tests/appended/` and `tests/test_appended_*.py` | Contract, runtime, carrier, build-policy and mode tests |

Do not put engine/loader/ABI implementation in either payload source root: that
would make the rebuild classifier unsound. Hide dependency headers and types
behind project-owned interfaces. Extend generic capabilities and shared tests
before adding adapter support; no adapter may recognize an application command,
cell name, UART protocol, page URL or selected product feature.

Startup order is deterministic: verify composition and compatibility; create the
registry and native services; load/validate modules; initialize module service
providers; create the selected primary application/view; then execute website
entry scripts and deliver ordinary input. Manifest-declared required providers
must be ready before use. Conflicting provider registrations, dependency cycles
or multiple unspecified primary owners are startup errors. Optional services use
explicit unavailable results. Module-to-module callbacks are queued, not recursive.

One application/session owns scheduling, views and shutdown. Both payloads may
provide UI regions or background services, but do not own competing host loops.
Close cancels new work and invalidates callbacks before unloading instances.
Initially require a controlled application restart to activate replacements.
In-process hot swapping and persistent-state migration are separate later work;
strict file replacement does not require either feature.

## Rich web framework and terminal presentation

### Feasibility gate before engine commitment

No researched rich engine is yet verified for this project's full native and
browser-Wasm requirements. Do not treat native embedding, or an engine's ability
to execute guest Wasm, as proof that the engine itself builds into Wasm.

| Candidate | Useful evidence | Required unresolved proof |
| --- | --- | --- |
| Servo | Embedding API and software-rendered output | Current rich editing and a viable engine-to-Wasm build under the project's deployment/baseline constraints |
| WebKit/WPE | Native offscreen rich web integration | Common required native targets, browser-Wasm port and acceptable dependency/runtime closure |
| Ladybird | Rich editing work and painted/semantic view interfaces | Stable embedding/baselines, browser-Wasm portability and maintainability |
| QuickJS plus litehtml | Small language/layout components | A complete maintained rich DOM/editing implementation; these components alone do not satisfy the requirement |

First perform a source/dependency/API audit for exact candidate revisions. Record
licenses, compiler floors, processes, threads, graphics requirements, fonts,
memory, approximate preparation/build cost and missing APIs. Do not launch a
costly engine build merely because a candidate is familiar. For expensive probes,
explain the unanswered question, why cheaper checks cannot resolve it and expected
cost, then follow the repository authorization policy.

A bounded prototype must prove native and browser-Wasm startup, built-in resource
loading, script execution, application-owned rendering and rich editing. Include
actual input, not screenshots of static markup. It must also prove extraction of
a usable terminal document view and execution with the current offline packaging
contract. The TUI path must work without a display server, GPU or hidden graphical
window. Choose and pin one implementation only after these results exist.

Stop dependent web implementation if a candidate requires different browser-only
application code, platform WebViews, plaintext-only substitution, online service
dependencies or silent removal of supported targets. Record the failed candidate,
evidence and next probe. Continue independent binary/packaging work. If none meets
the requirements, report the specific porting/dependency tradeoff for a user
decision; do not silently relax requirements or pretend selection is complete.

### Required web behavior

The framework contract must define supported HTML/CSS/DOM behavior with executable
fixtures. Include DOM queries; create/remove/replace; text/value/attribute/class
updates; event propagation and ordering; batched layout invalidation; forms;
tables; scrolling; tabs; focus and selection; and stable identity through updates.
Specify layout features used by the shipped examples, including responsive
arrangement and overflow. Unsupported features have documented behavior.

Rich editing includes a styled multi-node `contenteditable` document, caret/range
selection across nodes, insertion/deletion, declared formatting operations,
clipboard text and supported rich formats, undo/redo and IME composition. Preserve
selection/caret/scroll across unrelated DOM updates. Replacing a selected subtree
must have defined focus and edit-transaction behavior. Do not substitute a textarea
or reconstruct the entire editor from flattened text to pass the fixture.

Treat pasted markup as document data, not as new trusted application source.
Specify supported formatting, resource handling and clipboard size limits; pasting
must not execute scripts or fetch remote resources implicitly. The application's
trusted status does not turn clipboard contents into executable code.

The spreadsheet fixture contains at least two tabs, editable cells, cell/range
selection, keyboard navigation, a selection-dependent formula/status area,
add/remove-row controls, scrolling/virtualization and an asynchronous service
operation updating selected data. Model state survives tab switches and virtual
row recycling. Distinguish cell identity from visible row indexes. Define edit
commit/cancel and late-result behavior when selection changes while work runs.
Spreadsheet formulas/feature policy belong to application code, not adapters.

AJAX-like behavior means asynchronous updates without page reload. Provide
Promises, bounded timers/jobs and asynchronous application calls. A proposed
`app:/` resource scheme resolves solely within the payload filesystem; it is not
an Internet proxy or implicit filesystem path. Bundle fonts, images, modules and
styles. Resolve imports and relative URLs predictably; reject missing resources
with useful diagnostics. Normal execution must not acquire dependencies or fetch
CDNs. Internet networking is not required by this request.

The website-only service binding is outside `src-bin-appended/` and its SDK.
It adapts the same typed registry used by native and portable functions. It may
turn an asynchronous service job into a Promise and streamed results into bounded
events. Errors reject with stable codes; navigation/close invalidates old results.
The page never handles native transport tokens, concrete GUI widgets or browser
Wasm-module instantiation.

### Generic GUI extensions

Audit the selected engine's requirements against the current public boundary.
Existing bitmap/pointer support alone does not supply:

- Arbitrary key transitions, repeat, modifier distinctions and consumption rules.
- Text composition/preedit, replacement ranges, surrounding text or IME caret geometry.
- Application-visible focus/blur and window activation lifecycle.
- Typed clipboard read/paste and rich-format transfer.
- A semantic/accessibility subtree with roles, relationships, text ranges and actions.
- Efficient damage/tile/resource updates for large high-DPI surfaces.

Add these as generic versioned capabilities where required, with shared tests
and explicit adapter capability reporting. Preserve existing retained-input
generation, clipping, modality, shortcut and stale-event rules. Handle coordinate
conversion between logical viewport, physical pixels and document coordinates
once in the runtime, with a consistent inverse for hit testing.

Declare generic key/default-action capture policy before the physical event: a
browser parent cannot wait for a Worker round trip before deciding whether to
prevent its own default action. The internal engine then performs its document's
editing/navigation defaults. Specify conversion among UTF-8 byte offsets, DOM
UTF-16 offsets, Unicode code points and grapheme boundaries; test astral and
combining characters through selection and IME. Focus loss cancels composition
and held-key state. Publishing a new frame must not steal focus or activate a
background window or virtual desktop.

The reviewed browser output path has a 16 MiB aggregate bitmap budget and sends
full visible bitmap data in snapshots. A 1920 by 1080 RGB surface at scale 2 is
about 24.9 MB before serialization. Reinspect current limits, then design bounded
dirty tiles/resource reuse and viewport behavior; do not simply raise every cap
or retransmit an unbounded full frame on every keystroke. Measure input latency,
memory and transport sizes. GPU/VR/DSP workloads remain kernel services with
batched data/opaque resource handles rather than per-pixel language calls.
Bind each damage update to a frame/resource revision and its expected base
revision; validate tile bounds and budgets before application. A stale or missing
base requires bounded resynchronization, not partially applying an invalid frame.

### Terminal behavior

Produce a w3m-like text presentation from the same DOM, script session, service
state and editing model. Reflow to terminal width, use readable text and links,
map forms/actions to keyboard navigation, and render tables in a useful bounded
form. Graphical formatting, effects and pointer-only interactions may degrade or
be omitted. Application authors choose the useful terminal scope; full graphical
parity is not a release requirement for every application.

Prefer a rare standard HTML attribute such as
`data-foundation-tui="omit"` for explicit exclusions. It affects presentation,
focus and navigation only; underlying nodes and scripts remain present. Children
inserted later inherit the presentation rule. If comment-marker syntax is also
provided, parse it into the same well-defined rule, validate nesting and test
minification/DOM mutation behavior. Do not silently remove scripts or create a
second application DOM. No terminal-specific script implementation is required.

When rich editing cannot be represented in the terminal, display it readably or
offer supported text edits while preserving the rich underlying document. Never
save flattened text over rich data accidentally. Explicit readonly degradation
is preferable to claiming an edit capability that corrupts formatting.

### Browser and device integration

Trusted appended code runs alongside application authority, outside the existing
isolated renderer iframe. Preserve the existing renderer isolation contract; it
is a different boundary from the trusted application ABI. Do not change its CSP
or move application scripts into it merely to make the new layer work.

External browsers can host the retained kernel preview/inspector. A direct page
preview with mocked services is useful but must identify mocked calls and is not
internal-engine conformance evidence. Keep preview plumbing outside application
pages and outside the binary developer tree/SDK.

Preserve current single-file/offline/direct-file browser behavior. A threading-
dependent engine may require cross-origin isolation and server headers unavailable
to that route; this is a feasibility conflict to resolve, not permission to drop
the route. No service worker or local network server is required for ordinary
offline use. A development server may remain an optional convenience.

Device services expose generic enumerate/choose/open/exchange/subscribe/cancel/
close operations and higher-level application processing functions. Real UART is
new functionality, so start with a deterministic fake provider, then implement
native and supported browser providers through the same contract. Bound queues,
framing, timeouts and backpressure; distinguish bytes from decoded strings.
Preserve disconnect and partial-write outcomes. Browser chooser APIs may require
transient user activation: do not assume a Worker round trip preserves it. A
generic authoritative parent-owned chooser/Connect action may satisfy that
requirement without any browser-specific page code. Physical device qualification
is separate from fake-provider passes.

## Portable binary profile and application ABI

### Developer boundary and compiler profile

`src-bin-appended/` contains C/C++/Rust application code and necessary language/
build metadata. It must not contain JavaScript files, snippets, generated glue,
script references, web examples, npm manifests, `wasm-bindgen`, `js-sys` or
`web-sys` dependencies. Put boundary checks and explanatory web-integration
documentation outside this tree. The generated binary SDK consists of C headers,
C++ wrappers, a Rust crate, required language libraries and identified compiler
tools; no web engine, browser bindings, Node/npm or Emscripten installation is
required by its developer workflow.

Proposed universal payload: core wasm32, one bounded unshared linear memory,
explicit imports, fixed scalar signatures and an identified conservative feature
profile. Initially exclude native dynamic libraries, architecture-specific AOT,
threads, SIMD, exception unwinding and implicit WASI. Validate the final module
and all linked libraries rather than relying on application compiler flags.
Reject Wasm start sections. All initialization uses the explicit exports below,
after memory and instance binding are established.

Use pinned LLVM/LLD for freestanding C/C++ and a separately retained Rust guest
target/profile. Supply necessary allocation, byte/string and math functions as
small pinned portable libraries. C++ exceptions/RTTI and Rust panic policy must
be explicit. Rust `wasm32v1-none` is a candidate for conservative `core`/`alloc`,
but requires a newer guest compiler than the existing kernel Rust 1.63 baseline.
Do not silently change that baseline. Host tool executables may differ by
developer OS while producing the same supported guest format.

If a richer standard library is needed, qualify it as an explicit additional
profile with its complete imports and dependency closure. A WASI toolchain does
not make operating-system functions automatically available in browsers. Keep
device/filesystem/platform operations behind kernel services. A guest-only build
must not invoke the kernel CMake graph or recompile unrelated libraries; use a
small isolated guest target graph through the supported wrapper.

### Runtime choice gate

Prefer shared C/C++/Rust module-loading and dispatch implementation across kernel
targets if a focused prototype proves it. A C interpreter compiled into the
browser kernel can avoid per-module script glue, but its size/performance and
compiler compatibility must be measured.

WAMR has native embedding APIs but its documented platform list does not establish
a browser-Wasm port. wasm3 has an upstream Emscripten route, but maintenance,
feature and baseline suitability still require review. No runtime is selected by
this plan. Freeze a pinned choice after identical C/C++/Rust guest fixtures work
with host imports on native and browser kernels. Keep the runtime behind a
private adapter so its types never define the public ABI.

If a browser-native Wasm adapter proves necessary, keep it entirely within the
existing kernel host implementation, with no generated script payload or binary
SDK dependency. It must not become an excuse for requiring JavaScript in binary
development. A binary-only native kernel must operate without a JavaScript engine.

### Proposed ABI version 1

Use one small import namespace and one transport gateway:

```c
/* Import module "foundation.kernel.v1", name "call".
   Values are guest-memory offsets/counts, not native addresses. */
uint32_t foundation_kernel_call_v1(
    uint32_t request_offset, uint32_t request_bytes,
    uint32_t reply_offset, uint32_t reply_capacity);
```

Return a transport status, separate from the service result. Validate all ranges
using overflow-safe subtraction checks before reading/writing. Require space for
the fixed reply header before any effect. Large results return an opaque result
handle with explicit read/release operations, so a caller never repeats a mutation
merely to discover output size. Buffers are borrowed only for a call; asynchronous
work copies needed data. Reject overlapping request/reply ranges before effects.
Never retain guest addresses across invocations.

Proposed canonical envelope, 64 bytes, little-endian:

| Offset | Field |
| --- | --- |
| 0 | Total bytes, `u32` |
| 4, 6 | Envelope major/minor, `u16`, `u16` |
| 8, 12 | Message kind and flags, `u32`, `u32` |
| 16 | Kernel-issued module instance generation, `u64` |
| 24 | Request/event sequence, `u64` |
| 32 | Session-local registered interface handle, `u64` |
| 40, 44 | Operation ID and payload bytes, `u32`, `u32` |
| 48, 52 | Service status and reserved-zero, `u32`, `u32` |
| 56 | Correlation/job ID, `u64` |

Define complete payload encoding before freezing v1: fixed-width integers,
explicit floating-point representation where used, UTF-8 strings, length-prefixed
bytes, bounded records/lists and opaque handles. Generate codecs from the schema;
never copy compiler structs into the wire representation. Record field IDs,
required/optional fields, length/depth limits, duplicate-field behavior and rules
for unknown optional fields. Retain golden byte vectors and independent decoder
fixtures. A small generated codec avoids a general language runtime dependency.

Reserve interface handle zero for versioned kernel discovery/control operations;
its fixed bootstrap schema is part of the transport SDK. The initialization
context supplies the instance generation and bootstrap version/limits before any
discovery call. The kernel assigns other session-local handles; never persist
those handles in payloads.

Discover interfaces by namespaced name, major/minor version and the canonical
schema identity of the negotiated version. A newer provider may advertise older
supported contracts explicitly. The same name/version with different schema
identities is a conflict; adding optional fields in a new version must not reject
every older client solely because the provider's newest schema hash changed.
Track stable operation/field IDs within each interface and never reuse them.
Conflicting providers for the same required interface fail deterministically.
Version negotiation selects a supported contract, not a guessed memory layout.

Forks/modules own their application service namespaces and schemas without a
global allocation service. Keep these schemas with the appropriate application
component, generate endpoint codecs, and route opaque bounded messages through
the existing kernel registry. Adding a module-defined interface does not modify
kernel-owned schema ledgers or require kernel code generation/recompilation.
New native kernel implementations or transport capabilities remain kernel changes.

Proposed guest exports, all scalar-signature:

```c
uint32_t foundation_app_abi_v1(void);
uint32_t foundation_app_alloc_v1(uint32_t bytes);
void foundation_app_free_v1(uint32_t offset, uint32_t bytes);
uint32_t foundation_app_init_v1(uint32_t offset, uint32_t bytes);
uint32_t foundation_app_dispatch_v1(uint32_t offset, uint32_t bytes);
uint32_t foundation_app_step_v1(uint32_t budget_units);
void foundation_app_shutdown_v1(uint32_t reason);
```

Export the single linear memory as `memory`; validate every required export name
and signature before invoking any guest code. Encode the ABI query as
`(major << 16) | minor`. The ABI query and allocation/free exports must work before
application initialization and must not call application services. Allocation
returns a nonzero offset aligned to at least 16 bytes, or zero for failure;
define zero-size behavior and maximum allocation in the SDK contract.

Allocator support initializes lazily in the allocation export, or otherwise before
its first use, independently of application initialization. SDK startup then runs
C/C++ constructors and any Rust application startup exactly once inside the
initialization wrapper, after the context is bound and before the application
initializer. Constructors
must not depend on external service readiness; perform such work in the explicit
application initializer. Define one initialization attempt per instance and
destroy a failed instance rather than invoking it again. Freeze numeric status
values before v1: init/dispatch return success or a declared terminal error;
step returns idle, more-work or a declared error. Reserved values are errors.

The kernel allocates guest storage through the guest allocator, copies input,
invokes the entry point and frees that storage through the same allocator. The
guest must copy any data it needs afterward.
Kernel objects stay kernel-owned behind typed generation-bound handles. Define
generation/sequence overflow as instance exhaustion, never wrap into valid IDs.
Memory growth invalidates cached host views; refresh them before access.

Transport errors include invalid range, malformed envelope, unsupported ABI and
resource limit. Service errors include invalid argument, unavailable capability,
missing object, stale handle, busy, cancelled, shutdown, I/O failure and uncertain
external outcome. Unknown statuses are errors. Catch native language exceptions
inside adapters; no C++ exception or Rust unwind crosses the ABI.

Every mutating request has a nonzero ID scoped to the module generation. New IDs
are strictly increasing; retries reuse an already admitted ID. Identical live
retries return the recorded outcome; reuse with different canonical bytes fails.
Retain outcomes and their result objects until explicit acknowledgment/release.
Define acknowledgments for contiguous completed request ranges, including how
unused sequence gaps are closed; never advance a retirement watermark past an
unfinished request. Retired IDs return an expired result and never execute again.
Bound retained requests/results and reject new work before effects when capacity
is exhausted; do not evict unacknowledged outcomes to admit more mutations. This
is not crash-proof exactly-once device I/O: after an ambiguous external effect,
return an uncertain outcome and do not retry blindly.

Short operations may complete synchronously. Blocking work returns a job handle
and later ordered events. Cancellation invalidates result acceptance and prevents
new work; it does not claim to undo committed external effects. Provider calls and
module-to-module calls use queued dispatch rather than reentrant guest execution.
Callbacks generated during a call are delivered only after it returns. Give every
module one serialized owner and explicit queue limits/backpressure.

On shutdown, stop new input and provider calls, cancel jobs, finish the current
invocation, request guest shutdown, invalidate/drain callbacks, join owned workers,
release resources and unload. During guest shutdown allow bounded cancel/release
cleanup calls while rejecting new ordinary work. Pending calls to a disappearing
provider receive terminal cancelled/unavailable results before their handles are
retired. After a guest trap, perform host-owned cleanup and skip all further guest
code, including allocator/free exports. Interpreter timeouts are abort/recovery
mechanisms unless resumable execution is explicitly supported. They cannot interrupt an arbitrary
blocking native callback. Cooperative `step` budgets alone cannot preempt a loop
that never returns; qualify interruption and responsiveness deliberately.

### Binary UI and service integration

Expose versioned generic view transactions through the ABI. They carry widget/
resource identities and generations, layout values, commands, text, bitmaps and
availability. The kernel validates a complete transaction before atomically
materializing `gui::Snapshot`; invalid input leaves the previous view intact.
Generic events and service results return through ordered dispatch.

No native `gui::Snapshot` layout crosses the ABI. Appended binary code owns its
UI behavior and layout in C/C++/Rust. It can also register callable services without
owning a view. Shared capabilities may grow with explicit schema versions and
adapter conformance; an old kernel rejects unsupported required capabilities
before launching the application. Binary-only UI must not depend on HTML parsing,
JavaScript or a hidden website. Richer generic document/plot services can be
independent capabilities where needed.

Native functions register through an internal table containing interface version,
schemas, handler and thread affinity. Registration keeps implementations live
through link-time optimization. Module providers register typed descriptors and
receive calls as events. The separate website binding calls the same registry.
This supports page-to-module-to-kernel and module-to-module paths without putting
script concepts into binary application source or bindings.

## Append containers and release composition

### Three identities and recoverable inputs

Use versioned kernel, payload and composition descriptors. Keep legacy schemas
under their existing rules rather than weakening their validation.

Proposed `kernel.json` binds the accepted ABI/append profiles; target CPU/OS/runtime
floor; GUI backend and capability inventory; complete finalized executable
lengths/hashes; runtime libraries, exports, headers and notices; original complete
source archive/commit; kernel build-input inventory; configuration and exact
compiler/SDK recipe and archive identities; and original producer repository,
workflow revision, run, attempt and job. A recipe identifier alone is not an
archive checksum. Retain binary/source/checksum groups required for recovery.

Define the kernel build-input inventory as a reviewed content projection that
excludes replaceable payload inputs and purely packaging/product metadata. Include
loaders, runtime, trusted browser glue, generic adapters, kernel-owned ABI/view
contracts, relevant build helpers, patches and configuration. Application-owned
module/service schemas and endpoint codecs are payload inputs when they use
existing transport capabilities; they must not enter the kernel projection merely
because they describe an interface. Additions, removals and file modes matter.
Unknown inputs cannot silently disappear from the projection. The original full
source archive remains separate and unchanged.

Proposed payload index binds explicit component presence; application identity and
version; entry points; required ABI/services/capabilities; guest instruction and
library profile; resource limits; input/source/compile identities; and every file's
canonical path, offset, length, media/type and SHA-256. Its data area contains web
resources and precompiled portable module bytes, never native SDK tools. Sources,
compiler inputs and recovery material are also retained by the release inventory;
they need not all be loaded as executable resources.
Presence declarations, files, entry points and provider registrations must agree.
Reject an index that declares a component absent while retaining its content.
Disabling one component removes all of its previous content during recomposition
and preserves the other component's exact files unless it is also being updated.

The composition record binds downstream project/source/version, packaging code
and configuration, exact kernel descriptors and original evidence, payload/index
hashes, each output's carrier/prefix/final hashes, complete archive member
inventories and the applicable composition qualification policy. Preserve original
`build-info.txt`; add application/composition metadata separately. A new application
commit must not be substituted for the old kernel's source identity. The new
qualification certificate is produced after subject bytes are frozen and remains
outside the subject inventory. It binds the composition record and frozen release
inventory; neither includes that new certificate's hash. Existing kernel
certificates can be referenced because they already exist independently.

Avoid self-hash cycles: derive `kernel_id` from a defined intrinsic object and hash
complete descriptor bytes separately; a certificate references those identities
without being inserted back into the object it certifies. Derive `payload_id` from
canonical index bytes and record the complete package hash externally. Final file
hashes belong in the external composition/release inventory, not inside the same
file's hashed bytes. Write explicit dependency diagrams and golden manifest
fixtures before implementation to prevent accidental circular definitions.

### Logical package and native trailer

Proposed v1 logical package uses no internal compression:

```text
package = file data in canonical path order + canonical JSON index
native artifact = exact finalized kernel prefix + package + fixed trailer
```

Specify canonical UTF-8 JSON serialization, object ordering, integer-only sizes,
duplicate-field rejection and the exact bytes covered by each digest. External
tar/zip compression is separate. The same logical package hash must appear in
every target carrier. Appending does not convert guest code into native objects.
Carrier-specific trailer/framing bytes never enter `payload_id` or the logical
package hash; exercise this separation in cross-carrier golden vectors.

Proposed fixed trailer: 192 bytes, little-endian.

| Field | Bytes |
| --- | --- |
| Magic `SFAPND01` | 8 |
| Format version | 4 |
| Trailer size, exactly 192 | 4 |
| Original kernel prefix length | 8 |
| Package length | 8 |
| Index offset relative to package start | 8 |
| Index length | 8 |
| Carrier identifier | 8 |
| Kernel prefix SHA-256 | 32 |
| Package SHA-256 | 32 |
| Index SHA-256 | 32 |
| Reserved, all zero | 40 |

For native carriers require `file_size == kernel_length + package_length + 192`,
with overflow checked before addition/allocation. The index ends exactly at
package end. Entries cover the permitted data region without overlap, duplicate
ownership or unexplained bytes. Define package/index/file/count/depth limits in
the format contract before freezing v1; derive usable values from the fixtures.
Do not allocate from unvalidated counts or expand unbounded data.

Use canonical portable resource paths. Reject absolute/drive paths, traversal,
backslashes, NUL/control characters, duplicate or case/normalization aliases,
escaping links and unsupported special files. Define filename encoding and URL
resolution together. Runtime resource access uses the indexed virtual filesystem,
not archive extraction into executable search paths. Verify canonical bytes before
handing modules to runtimes that may require writable/mutable input buffers.

A digest inside a trailer detects inconsistency but is not independent
authentication. The composer verifies trusted pinned descriptors/inventories;
release authentication covers the complete output. This preserves provenance
without inventing a hostile-application permission boundary.

For no payloads, use the pristine kernel with no application suffix. The loader
must not infer legitimate absence merely from missing trailer magic. For native
carriers, initial kernel production establishes an authoritative pristine byte
length in fixed-size read-only metadata, finalized after installation/stripping
and before hashing the kernel. Composition never patches it. This length needs no
self-hash; independent descriptors carry the completed kernel hash. Exercise the
stamping/length algorithm with reference fixtures in P1C, then require actual
stamped-kernel loader execution in P6 before finalizing the production format.
Exact pristine length means absent; extra or missing bytes must pass the recognized
carrier rules or fail. A partial package whose entire trailer was truncated must
therefore fail.

An entirely removed suffix is indistinguishable from a legitimately pristine
base unless an independent launch/install descriptor requires a payload. Where
that expectation exists, missing required components fail explicitly. Without
it, a loader-capable kernel may legitimately start in neither mode. Recognized
corrupt/unsupported appended content never falls back to the built-in demo.

### Carrier adapters

**ELF:** preserve the entire finalized executable, not just loadable segments.
Produce any required padding beyond page-rounded `PT_LOAD` file extents during
initial kernel production and include it in the immutable identity. Do not run
strip, relink, rewrite RPATH or reconstruct a supposed base from section guesses.

**Windows PE:** the current repository does not implement Authenticode. A strict
raw-overlay v1 can use verified unsigned PE kernels plus authenticated complete
release/package inventories. Reject unsupported signed inputs; never remove
certificates, edit security-directory fields or exploit certificate padding.
Ordinary post-sign appending is not an Authenticode-preserving contract. If future
requirements include signing each final executable, explicitly resolve the
immutable-prefix conflict. A sidecar may be an additional delivery option but
does not satisfy the requested strict-append deliverable by itself.

**Offline HTML:** prepare an immutable shell/bootstrap that accepts a canonical
suffix without HTML error recovery; use legal optional end-tag omission for the
pristine shell and define the exact grammar before implementation. Append an inert
ASCII data block containing base64(package plus trailer) and a canonical ending.
The fixed bootstrap waits for parsing, permits zero recognized blocks when absence
is allowed, requires exactly one when a payload is present or independently
required, and rejects duplicates. It bounds encoded size before decoding and
checks the package/ABI before use. Payload markup remains data until
the internal framework consumes it. Base64 prevents embedded HTML terminators
from escaping the block. Kernel Wasm, script glue and loader bytes stay unchanged.
The external verifier checks raw prefix bytes; DOM `outerHTML` is not an exact
serialization of the original file. Direct-file runtime loading must not require
fetching its own file through APIs unavailable in that environment.
DOM-only runtime validation covers the recognized decoded package, block count,
limits and compatibility; it does not prove the raw prefix, canonical raw tail or
absence of arbitrary unrecognized trailing bytes. Those checks require the
external raw-file verifier. When neither a recognized block nor an independent
expected-mode requirement is available, the runtime can only treat the shell as
pristine; it cannot detect a completely removed suffix. Document this limitation
rather than promising raw-byte self-verification through the DOM.

**Direct Wasm, if offered:** append a valid final named custom section: section
ID zero, canonical ULEB length, encoded owned section name, package and trailer.
Preserve the original valid module prefix and its unrelated custom sections.
Require exactly one owned final section; stripping removes its complete framing.
Account for section framing in size checks instead of applying the native EOF
equation unchanged. Arbitrary trailing binary data is invalid. The selected
browser host supplies extracted resources to the existing application-side loader.

### Replacement and output safety

Consume final installed/package kernels, not build-tree executables. Current
installation can rewrite Linux runtime paths, so retained-only composition must
not invoke CMake install/CPack or their application build prerequisites.

For a pristine base, verify the complete archive/member inventory, selected
kernel descriptor and exact executable size/hash before composing. For an old
composed release, first verify its whole inventory and recognized carrier, then
verify its prefix against the independently pinned kernel descriptor. Retain
exactly that prefix, replace the complete owned suffix and verify the new output.
Do not scan arbitrary bytes for a plausible magic value or trust an old footer's
unverified length as authority. Replacement must never stack application packages.

Write to a new exclusively created temporary output under the owned destination
parent. Recheck source identity before exposing the result, verify the complete
new output and publish without clobbering an existing destination. Checking for
absence followed by an overwriting rename is insufficient. Preserve originals
on every failure; clean up only owned temporary files. Do not modify a running
executable in place. Installation/activation uses a verified new artifact and
controlled relaunch. Replacing a payload does not imply live state migration.

### Supported entry points to add

The following grammar is proposed, not currently runnable:

```text
./build.sh project configure [identity and component options]
./build.sh appended inspect [input/configuration options]
./build.sh appended compile [guest sources, pinned guest SDK, output]
./build.sh appended pack [web sources, precompiled module, output]
./build.sh appended verify [package/artifact, trusted manifest options]
./build.sh appended strip [composed input, pinned kernel, new output]
./build.sh appended compose [verified kernel, package, new output]
./build.sh appended prepare-release [frozen selectors, new output]
```

Extend `tools/build.py` through the existing shell entry point; Windows invokes
the same Python helper directly as today. `inspect` is read-only. `compile` builds
only the portable guest in a separate target tree. `pack` accepts already prepared
inputs and invokes no compiler. `verify` reports both internal consistency and
whether an independently trusted identity was supplied. `strip`, `compose` and
`prepare-release` require pinned input identities and new output destinations.
Kernel maintenance remains an explicit build operation using the supported graph;
do not overload these actions with implicit kernel production.

Module compilation may be an explicit stage in a composition workflow. The pure
composition job must never invoke kernel configure/compiler/linker/install tools;
enforce this with process guards and byte identities, optionally restricted tool
access. Hosted runners may already have compilers installed. Web-only packaging
must also work without the guest toolchain. Defaults never fetch missing SDKs.
Return clear diagnostics with missing capability/profile/service information and
the explicit next maintenance action, not a suggestion to rebuild everything.

### CI classification and release flow

Add a retained-only composition workflow and integrate it with the existing
visible release entry point. Preserve current kernel production and legacy release
schemas. Do not dispatch existing full application producers merely to obtain an
archive that could be composed from retained bytes.

1. Freeze downstream configuration, complete source, enabled components and exact
   kernel source selectors. Resolve immutable release/inventory/asset identities.
2. Acquire retained kernels read-only from the explicit source repository or local
   bundle; verify requested target/backend/profile inventory and compatibility.
3. Compile the portable module once, only if required; record its SDK, source,
   feature/import validation and byte hash.
4. Pack one logical application package and compose it into all selected carriers.
5. Verify exact prefixes and unchanged runtime members; prepare all application,
   package, recovery/source, notice and provenance assets, including any package
   signatures, without rebuilding application kernels.
6. Freeze the complete candidate inventory and composition record. If the user's
   release request authorizes candidate publication, publish it through the
   downstream protected lifecycle for exact remote-byte qualification. Authorization
   for extensive validation alone does not authorize publication: retain a
   local/private candidate in that case and report the resulting coverage limits.
7. Execute required runtime, browser, install/upgrade, packaging and recovery
   checks against those frozen bytes. Earlier development checks remain useful
   but cannot substitute for final-package checks.
8. Retain/attach the new certificate and evidence outside the frozen subject
   inventory. Revalidate identities and completed gates before promotion.

Reuse existing protected-publisher locking, authenticated acquisition/readback,
immutable publication and promotion mechanics with new versioned composition
validators. Do not route through unchanged full-source/recovery/application
producer gates: current prepared-package and qualification paths may invoke native
builds or reject cross-release identities. Extend those policies explicitly.

Separate upstream read credentials/selector from downstream repository, tags,
package identities and signing credentials. Existing helpers commonly use
`GITHUB_REPOSITORY` for both acquisition and publication; extend that explicitly.
Acquisition failure must not select another unpinned source or publish upstream.

Update ordinary feedback selection as well as release workflows. New payload paths
must not fall through `tools/ci_changes.py` into full native/shared-GUI builds.
For independent fork roots or unavailable Git comparison history, compare the
complete current kernel input inventory against the pinned kernel descriptor.
Git ancestry is an optimization, not the compatibility proof.

| Change | Allowed default action in appended workflow |
| --- | --- |
| Web HTML/CSS/JS/assets | Resource checks, pack, compose, affected retained-runtime checks |
| Binary C/C++/Rust | One guest compile/link, ABI checks, pack, compose, affected runtime checks |
| Product metadata or composition helper | Appropriate tooling/composition checks; unchanged kernel stays retained |
| Module-owned service schemas using the existing ABI | Regenerate endpoint bindings/compile affected payloads, compose and run contract/runtime checks; no kernel code generation |
| Combined known web, binary and product changes with identical kernel inputs | Aggregate the applicable payload/tooling actions; retained-only eligibility remains valid |
| Loader, engine, ABI implementation, native service, GUI contract, kernel dependency or build input | Report kernel maintenance required; build affected kernels only through an explicit maintenance operation |
| Unknown/unclassified input, mixed changes altering kernel inputs, or missing base | Fail eligibility with concrete differences; no automatic fallback build |
| Neither mode, ordinary native source edit | Existing focused conventional build behavior, respecting normal qualification policy |

Tests must observe process invocations and byte identities, not infer absence of
rebuilds from elapsed time. Repeated compiler invocations that happen to hit a
cache still violate the no-kernel-compilation composition contract.

### Qualification and recovery policy

Existing complete-source certificates and same-run retry adoption do not express
cross-release component reuse. Add a versioned composition policy. Keep original
kernel source/recovery/ABI/consumer evidence bound to its original inputs,
environment and attempts. New evidence binds that eligible kernel identity to
the new payload, package, application behavior and full output hashes.

Unchanged kernel qualification does not qualify new script/module behavior.
Payload changes still need affected application, lifecycle, browser, install and
upgrade checks. Those checks can execute retained binaries without recompiling
them. Initial loader/runtime/ABI work needs new kernel qualification when that
extensive execution is authorized. Pending required gates prevent publication or
promotion; ordinary source commits do not require a complete release matrix.

Recovery must support recompiling a guest from its retained SDK/source and
recomposing from retained kernels without a native platform build. Separately
retain the inputs needed to reconstruct kernels under their original policies.
Do not relabel recomposition as kernel reconstruction or skip missing source/
dependency groups. Older package schemas keep their original rules and claims.

## Implementation work packages

The following stages describe future implementation. Completion means the listed
deliverable and focused evidence exist; a planning note or compiling stub is not
completion. Record durable decisions in the relevant maintained contract, keeping
this document a proposal until replaced by implemented procedures/evidence.

| Stage | Deliverable and dependency | Concrete completion criterion |
| --- | --- | --- |
| P0 | Freeze requirements, current source baseline, four modes, source/dependency projection and work ownership. No runtime prerequisites. | Reviewed configuration/ABI/container sketches, complete requirement-to-test map, existing behavior unchanged. |
| P1W | Rich-engine source audit and bounded native/Wasm feasibility; depends on P0. | One pinned candidate passes actual rich editing/rendering/resource/semantic probes, with dependency costs and offline constraints recorded; otherwise a concrete unresolved gate. |
| P1B | Portable-runtime and guest-SDK feasibility; independent of P1W after P0. | Same C/C++/Rust/mixed-ABI fixtures run natively and in browser-Wasm with host imports, bounded execution and no binary-developer web dependency. |
| P1C | Container/reference verifier and profile/config fixtures; independent of engine selection. | Golden packages, reference stamping/boundary fixtures, explicit runtime/external-verifier limits, safe strip/reappend and four-mode identity/dependency tests pass without compiling kernels. Actual loader execution belongs to P6; no production format/release claims yet. |
| P2B | Freeze v1 wire, service, binary-view and guest-profile contracts after P1B and the relevant interface audit; independent of P1W. | Bootstrap, codecs, ownership, generation/version/errors and independent golden vectors reviewed; later web capabilities cannot silently change this ABI. |
| P2W | Freeze rich-document/input/semantic/damage capabilities after successful P1W, building on P2B's versioning rules. | Engine requirements map to reviewed generic extensions and actual input/resource conformance cases. |
| P3 | Registry, dispatch, module lifecycle, generic binary UI and source/SDK guards. Depends on P2B. | Binary-only app runs through generic hosts with async services, traps, cleanup and no website engine. |
| P4 | Rich web runtime plus generic input, semantics and damage transport. Depends on successful P1W and P2W. | Full rich editor/spreadsheet fixtures work on focused native/browser paths without product behavior in adapters. |
| P5 | Text reflow/TUI presentation and selected generic adapter extensions. Can run in parallel with P3/P4 after contracts stabilize. | Useful common-document terminal operation, honest degradation and optional hints; generic input/capability conformance. |
| P6 | Production append loaders/carriers and startup composition. Uses P1C, P3/P4 as enabled. | Actual stamped-kernel loader execution before production format finalization; neither/either/both startup, absence/corruption behavior within each carrier's stated validation limits, dependency readiness, same package hash across carriers and exact prefix preservation. |
| P7 | Wrapper, independent project identity, fork convenience if desired and retained-only CI. Uses P6 and frozen manifests. | Forked applications select all four modes; payload edits launch no kernel compiler and wrong bases fail clearly. |
| P8 | Component qualification/recovery and release integration. Uses stable implementations and explicit release/qualification authorization for costly execution. | Required actual-target checks and source/recovery/inventory gates pass for claimed artifacts before publication. |

File-level work allocation:

| Workstream | Primary edit scope | Required shared agreement |
| --- | --- | --- |
| Project/configuration/fork | New project parser/schema, `fork.sh`, README fork section, `tests/test_fork.py` | Config schema, default neither, exact-root invariant and package identities |
| ABI/codecs/bindings | `abi/appended/v1/`, public headers, generated guest C/C++/Rust bindings, codec fixtures | Numeric IDs, wire representation, namespace discovery, ownership and lifecycle |
| Module runtime/SDK | Private runtime adapter, guest SDK recipe, dependencies and module fixtures | Guest profile/imports, interruption semantics, output inventory |
| Service/lifecycle/view bridge | Registry/dispatcher/module files, `gui/shared/appended_application.*` | Ordered calls, atomic views, startup/shutdown ownership |
| Web engine | `src/appended/web/` integration and supplier recipe/patches | One authoritative document, resources, node handles and semantic extraction |
| Rich input/semantics | Generic boundary patches/contracts and shared input fixtures | Keyboard default policy, IME encodings, focus, clipboard and accessibility |
| Presentation/TUI | Damage/tile bridge and text presentation, distinct files | Resource revisions, budgets, hit testing, terminal degradation rules |
| Adapter implementers | Separately assigned FLTK, Rev, SDL/framebuffer, terminal and browser adapter files/patches | Frozen generic contracts and conformance cases; no feature logic |
| Composer/manifests | New append tools, source identity and archive/package helpers | Exact bytes, canonical serialization, carrier framing and no-clobber publication |
| CI/release | Classifier/planner, lifecycle helpers, workflows, certification policy | Component identities, no implicit rebuilds, upstream read/downstream write separation |
| Integration/tests/docs | Final merged checks and maintained documentation | Original evidence identities, exact scope and deferred qualification |

Assign one integrator to shared `CMakeLists.txt`, `gui/CMakeLists.txt`, dependency
locks, schema ledgers and workflow entry points. Others submit required changes to
that owner. Do not let multiple writers edit separate regions of the same file
without the repository's supported coordination. Treat browser transport/frame
contracts and ABI/schema changes as shared invariants even when files are disjoint.
Use up to the allowed concurrency when useful, not a fixed mandatory agent count.

Maintain patches and retained supplier recipes, not generated restored headers
under `build/`. Update public docs, CLI help and installed instructions with actual
implementation. Add an appropriate entry to [requirements](requirements.md) and
the practice map only when concrete code/test homes exist; do not add nonexistent
paths to the map during planning.

## Acceptance and validation

The first useful checks should be cheap and independent of physical displays:
schema/codec/container vectors, mode/config/parser fixtures, process-invocation
guards, source boundaries and fake-service lifecycle tests. Engine feasibility
requires real engine execution; mock passes cannot substitute for it. GUI behavior
requires selected actual hosts; screenshots alone do not prove input semantics.

| Family | Discriminating acceptance cases |
| --- | --- |
| Four modes | Neither/either/both; absent disabled roots; no tool discovery/download or runtime dependency for disabled features; binary-only UI and web-only direct kernel call. |
| Fork adoption | Exact initial tree/index/new root/no remote; optional reviewable settings; local offline source; source and downstream identities independent; no ancestor requirement. |
| ABI versions | Bootstrap before discovery; old module/new compatible kernel; incompatible major; missing required/optional service; provider collision/cycle; version-specific schema identity; payload-owned interfaces added without kernel generation; field/operation additions and unknown statuses. |
| Wire/ownership | Overflow/range errors, malformed UTF-8/records, output sizing before effects, memory growth, stale/expired handles, wrong instance and allocator ownership. |
| Effects/lifecycle | Identical/conflicting retries; retired IDs; queue saturation before effects; no reentrant guest callback; cancel/restart; trap; close during work; uncertain external write; no surviving workers. |
| Binary portability | C, C++, Rust and mixed scalar-ABI fixtures; same module hash across hosts; final import/feature/export audit; pre-init allocation and constructors exactly once; native SDK build/run without Node/Emscripten/script engine; browser execution uses only retained base-owned bootstrap/adapter code. |
| Generic views | Atomic valid/invalid replacement, widget generations, stale events, commands, focus/selection, bitmaps/resources and services through C/C++/Rust with no HTML dependency. |
| Rich editor | Styled multi-node ranges; insertion/deletion; paragraph split/merge; formatting; plain/rich paste; undo/redo; IME cancel/commit; emoji/combining text; preservation across DOM mutation. |
| Spreadsheet | Two tabs; editable and virtualized cells; stable identity/ranges; keyboard commit/cancel; selection-driven state; add/remove rows; async results across tab/selection changes. |
| TUI | Same JS/services/document; text reflow; usable forms/links/table navigation; no required hints; optional omission/nesting/mutation; formatting preserved despite degraded presentation. |
| Resource/offline | All fonts/scripts/styles/images bundled; local URI resolution; no implicit Internet fetch; missing resource errors; standalone/isolated hosted and direct-file browser paths as affected. |
| Device services | Fake framing/backpressure/timeouts/partial write/disconnect; cancellation and stale results; actual native/browser provider execution separately identified. |
| Rendering/input | High DPI and resize; tile/resource revisions and resync; transport limits; keyboard defaults; focus loss; clipboard limits; no focus stealing or background-window activation. |
| Determinism/replacement | Identical package bytes; strip returns exact base; repeated replacements leave one suffix; removing one component removes all of its files while preserving the other; every target uses the same logical package; empty mode is pristine. |
| Malformed carriers | Truncation including complete trailer loss with residual payload; authoritative native pristine boundary; expected-mode/absence checks; overflow/size/version/reserved errors; overlap/path aliases; corrupt hashes; embedded fake magic; duplicate HTML blocks; malformed Wasm lengths; invalid/unrecognized raw tails checked externally where runtime cannot; unsupported signed PE. |
| Output safety | Existing or concurrently appearing output; linked path; changed source; partial failure; no clobber; inputs preserved; only owned temporary cleanup. |
| Provenance/CI | Original source/build-info/SDK hashes retained; one-byte kernel change blocks reuse; added/deleted/mode-changed inputs included; independent root and mixed edits classified; no kernel compile/install process. |
| Delivery/recovery | Actual package inventory and install/upgrade/removal; original certificate references; fresh composition policy; recompose offline from retained inputs; missing dependencies fail. |

Extend existing suites where they own behavior: `test_build`, `test_ci_changes`,
`test_source_identity`, `test_gui_boundary`, `test_fork`, `test_artifact`,
`test_package_wasm`, `test_import_wasm`, `test_release`, `test_ci_plan`,
`test_github_release`, `test_certification`, `test_release_packages` and
`test_latest_release`. Add focused appended-specific tests for genuinely new
contracts; do not duplicate implementation logic in the assertions.

Register focused checks through the supported graph/runner. Once names exist,
select them with the existing `./build.sh test dev --test NAME` mechanism or the
new explicitly implemented retained-runtime test action. Do not publish commands
with invented test names as if they already run. The wrapper may build test
prerequisites; pure composition/retained-runtime checks must be isolated from
kernel prerequisites so that verification cannot secretly trigger a rebuild.

For extensive qualification, use supported native Linux x86_64 and aarch64,
Windows x86_64 and browser wasm32 targets with their actual selected backends and
original baselines. TUI/hosted browser are frontend choices, not extra CPU targets.
Recheck the current inventory instead of hardcoding an obsolete matrix. Actual
Edge/Chrome/Firefox and the accessible Desktop embedded browser need their own
observed results for claimed support; Chromium alone is not execution evidence
for every named product. Do not add new OS support claims implicitly.

Measure guest compile/link, pack/compose, payload size, per-target kernel growth,
load time, peak memory, host-call latency, input latency, repaint/transport volume
and retained resource growth. Separate cold SDK preparation from warm iterations.
Measure representative small C/C++/Rust modules and the rich fixture, then set
reviewed regression thresholds. "Tiny", "fast" and "portable" are goals until
the corresponding measurements/execution support them. A cache hit is not proof
that a forbidden build invocation was avoided.

At each implementation handoff identify source/configuration/SDK identities,
commands, actual results and omissions. A setup failure means no affected
assertions executed. Track applicable deferred expensive work under
[pending qualification](../.agent-pending/README.md), distinguishing missing
implementation from implemented-but-unqualified behavior. No failure, skip or
unexecuted plan counts as a pass.

Documentation-only validation for this proposal checks links, headings, examples,
internal consistency and the actual diff. No application build is needed to
validate prose. The delivery message records the checks actually run.

<a id="instructions-for-the-implementing-agent"></a>

## Historical instructions for the original implementing agent

The following preserves the original implementation brief. It is not the current
paste-ready resume prompt: its P0/P1 restarts and model-default references are
superseded by the [current continuation handoff](#current-continuation-handoff).

> Read `AGENTS.md`, `docs/README.md` and
> `docs/appended-application-plan.md` completely. Treat the document as a proposal
> with mandatory user requirements, not evidence of existing features. Inspect
> current source, dirty work, relevant pending records and coordination state.
> Preserve the ordinary neither-payload application and all four independent
> project modes. Work through P0 and the independent P1 feasibility/format tracks
> before committing to a rich engine or stable ABI. Delegate disjoint work using
> the repository's model/effort defaults and coordinate shared contracts/files.
>
> Rich editing, the same internal framework on native and browser-Wasm, and strict
> append/reuse are requirements. Do not silently substitute plaintext forms,
> per-platform WebViews, outer-browser application execution, native per-platform
> payload libraries, or sidecars as the only append solution. Binary application
> developers use only C/C++/Rust and must never need or reference JavaScript code
> in `src-bin-appended/` or its SDK. Keep the separate website bridge outside it.
>
> Keep kernel implementation outside both payload roots. Add typed generic
> services and view contracts; no application-specific behavior enters adapters.
> No trusted-application sandbox or per-function permission ceremony is required.
> Missing native functions and host capability restrictions must be reported
> honestly through the stable interface.
>
> Use the supported build entry point for actual compilation. Compose from
> verified final kernels without compiler/linker/install invocation. A missing or
> incompatible base must report kernel maintenance required, never trigger it
> automatically. Preserve original kernel source/SDK/evidence and bind new payload
> and composition identities separately. Honor fork independence and keep upstream
> downloads separate from downstream publication.
>
> Run the smallest checks that discriminate each change. Costly engine builds,
> full platform matrices and release certification need the repository's explicit
> authorization trigger. If a required engine/runtime feasibility gate fails,
> record its evidence and continue independent useful work; report the unresolved
> tradeoff rather than weakening the requirement. Inspect the integrated diff,
> update maintained contracts/procedures, and hand off exact passes, failures,
> missing implementation and pending qualification separately.

The initial brief also asked, before beginning code, for a note identifying: selected
starting commit; active four-mode defaults; proposed work owners; the first engine
and module-runtime audit/probe; available retained SDKs; expected cost; and the
first focused checks. This is ordinary implementation planning, not an extra
approval ritual. Ask only where the user must resolve a requirement conflict or
authorize an expensive scope under existing policy.

Later update agent guidance with enforceable rules: payload-only changes use the
retained route; web changes do not compile modules; module changes do not build
kernels; unknown eligibility fails explicitly; and kernel changes name the exact
invalidated inputs. Do not change `AGENTS.md` merely to claim this proposal is
already implemented.

## Reference evidence for open technical choices

Primary references reviewed during planning on 2026-10-16. Mutable upstream
documentation is background for selection, not a pinned dependency or proof of
this repository's execution. Pin exact sources and recheck when implementing.

- [QuickJS embedding API](https://www.bellard.org/quickjs/quickjs.html#C-API)
  and [litehtml](https://github.com/litehtml/litehtml) describe language/layout
  components; they do not establish the complete rich editing integration here.
- [Servo embedding](https://doc.servo.org/servo/) and its
  [Wasm portability discussion](https://github.com/servo/servo/discussions/28070)
  with [later clarification](https://github.com/servo/servo/discussions/39232)
  distinguish native embedding from compiling the engine to Wasm.
- [WebKit ports](https://docs.webkit.org/Ports/Introduction.html) and
  [WPE platform integration](https://wpewebkit.org/reference/2.54.0/wpe-platform-2.0/tutorial-platform.html)
  describe native integration; [Ladybird editing work](https://ladybird.org/newsletter/2026-07-31/)
  is relevant candidate evidence, not a platform qualification result here.
- [Emscripten pthreads](https://emscripten.org/docs/porting/pthreads.html)
  explain deployment constraints that a rich-engine port must reconcile with
  offline/direct-file delivery.
- [WAMR supported platforms](https://github.com/wasm-micro-runtime/wasm-micro-runtime#supported-architectures-and-platforms)
  and [wasm3's Emscripten route](https://github.com/wasm3/wasm3/blob/main/platforms/emscripten/README.md)
  inform the module-runtime gate. Neither is selected or measured here.
- [LLD WebAssembly](https://lld.llvm.org/WebAssembly.html),
  [Rust wasm32v1-none](https://doc.rust-lang.org/rustc/platform-support/wasm32v1-none.html)
  and [Rust C ABI changes](https://blog.rust-lang.org/2025/04/04/c-abi-changes-for-wasm32-unknown-unknown/)
  support explicit target/feature control and avoiding aggregate-by-value ABI assumptions.
- [ELF program headers](https://gabi.xinuos.com/elf/07-pheader.html),
  [WebAssembly binary modules](https://webassembly.github.io/spec/core/binary/modules.html#custom-section)
  and [Microsoft PE signatures](https://learn.microsoft.com/en-us/windows/win32/secbp/understanding-pe-signatures)
  inform carrier validation; actual target execution remains required.
- [Web Serial](https://wicg.github.io/serial/) documents browser capability and
  activation requirements; a portable service API cannot bypass them.
