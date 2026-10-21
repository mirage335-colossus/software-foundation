# Appended application implementation plan

<a id="current-continuation-handoff"></a>

Local `.agent-work/` archives are optional and are not required for repository documentation validation.

## Current continuation handoff — 2026-10-20 UTC

### Cleanup checkpoint — 2026-10-20 America/Chicago

The user has stopped appended-application implementation for now and requested
cleanup only. Do not resume builds or acceptance runs without a new request.
The initial cleanup started from `c6dcfae251ae251dbbe93529699136792d1686b2` and is
now included in `73fbdbb984c00518203f168616e5e2ef165c9716`. The support-file cleanup
and documentation corrections below are subsequent local changes.

- Removed obsolete cross-harness coordination tools, dedicated tests, CI wiring,
  guides and active instructions. Use native managed subagents with disjoint
  scopes. `.agent-work/` is historical evidence, not an active registry.
- Reuse stable, purpose-specific build directories. Remove completed disposable
  binaries, object trees and package copies; preserve useful source, concise
  results, failures, commands and pending qualification. Only explicitly current
  SDK/engine baselines remain reusable. Old result records do not qualify new
  source, and intentionally deleted historical binaries must be rebuilt.
- Focus/input ordering repair is implemented; six native fixtures passed.
  F13 scoped Foundation construction and independent full readback passed
  (`build/appended-continuation/readback-execution-v1/ROOT-FULL-READBACK-ACCEPTANCE-v1.json`).
  This establishes construction only. Its generated host binaries are disposable;
  no complete Foundation23+3+6 or public browser runtime passed.
- Maintained [QuotePad](../examples/appended-quote-pad/README.md) now includes
  C/C++/Rust providers. Actual-Wasm fixtures pass totals43/44 and seven negative
  contexts using a modeled serialized owner; compile/pack measurements are in
  `build/quotepad-languages/strong/RESULT.json`. Generated modules/packages are
  disposable test outputs, not retained application releases.
- Public viewer observation and schema3 physical-input source is prepared.
  `build/public-application-integration/CLEANUP-HANDOFF-v2.json` records46 passing
  checker tests and a **known unrepaired signed/fractional JSON boundary gap**.
  Scenario templates are unexecuted; no browser/application acceptance is implied.
- Receipt converter source in `tools/appended_foundation_receipt.py` is partial,
  untested and not registered. `build/appended-runtime/` preserves prepared reader
  sources and seven passing pure witness fixtures. Resume by completing/reviewing
  these sources, then construct a fresh host and perform complete runtime/readback.
- Signal notebook (`src-web-appended/`) preserves the broader spreadsheet,
  dropdown, dynamic-DOM, rich-editing and native/module-service example. Native
  HTML TUI still needs a real admitted native engine group; the available retained
  engine is wasm32. Do not substitute browser qualification for native/TUI gates.

All managed writers and checks closed before binary cleanup. Removed 84,764
obsolete generated files (79.988 GiB logical bytes). Cleanup tooling checks passed:
CI classification 63, host contracts 26, test runner 8, documentation and diff checks.
Exact deletion scope/counts and retained baseline paths are in
`build/cleanup-validation/binary-cleanup-result.json`; the per-file deletion list
is in the same directory. Sources, historical results, useful unfinished plans,
generic process supervision and pending qualification remain. No full engine
rebuild, SDK mutation, staging, commit, push or publication occurred.

The follow-up removed another 114,041 files (16.895 GiB logical bytes): 12 obsolete
SDK/sysroot support trees, 33 identical WebKit source-archive copies and 15 old
SDK source-archive copies whose hashes match retained public release assets.
One canonical WebKit source archive, all five selected current SDK/engine roots,
and the selected engine records remain. The executed removal receipt is
`build/cleanup-validation/support-cleanup-result.json`. Retention is per compatible
target/profile/toolchain, not simply the newest timestamp across all platforms.

The [Development feedback run for 73fbdbb](https://github.com/mirage335-colossus/software-foundation/actions/runs/39537683170)
failed documentation checks because 39 links required ignored local archives.
Those references now remain as labeled archive paths; documentation validation
passed both locally and in a copy containing tracked files only. The checker was
not weakened. Other infrastructure failures remain: output replacement ownership,
SDK source-insulation policy applied to README text, runner tool/environment
assumptions, and changed source/schema/workflow expectations. Investigate these
with their focused suites before another complete release attempt; they have not
been repaired or rerun here.

Next simplification priorities, without resuming implementation in this cleanup:

1. Maintain one explicit current baseline selection per target/profile/toolchain
   and one reusable output tree per compatible configuration. Delete superseded
   local copies after their final consumer; retain results and provenance.
2. Make this handoff the current-state entry point and treat the chronology below
   as history. Preserve unfinished product plans and failure evidence without
   requiring every future task to rediscover them.
3. Complete the maintained public appended runner using the prepared QuotePad,
   provider, viewer and runtime work. Keep web edits packaging-only and compiled
   edits limited to the small module; preserve all acceptance predicates.
4. Restore ordinary release feedback separately from unfinished rich-runtime
   qualification. Use the existing [Latest release workflow](latest-release.md)
   to build candidates once, certify their exact bytes and promote after gates
   pass. Appended composition currently produces unqualified candidates; it is
   not a shortcut around release certification.

Earlier checkpoints below are historical, including their superseded execution
instructions and references to removed disposable output files.

### S8 closed Foundation runtime failure and focus diagnosis — 2026-10-20 UTC

The ordinary appended application loop remains active: rich-web edits package HTML/CSS/JS resources only, and compiled C/C++/Rust edits rebuild only the small portable module. S8 (`72663`) closed failed: caller 2 / capture-failed, outer owner 0, natural closure after 387.719795s at 3,495,653,376-byte peak RSS. The controller hit an instrumentation per-file byte cap in `runCase`, not an elapsed-time watchdog. All 196 inputs (141,713,323 bytes) were unchanged. E01 captured 4,959 events, 66 case records, 34 GUI operations and 17 polls; E02–E23 were unreached, no E01 case outcome was accepted, and the independent full reader did not run. See the S8 failure record (local archive path: `.agent-work/foundation-full-runtime-20261020-v8/ROOT-RUNTIME-FAILURE-v1.json`) (SHA-256 `4f026063323df96b15174fd9c35b515f3b5cca2920363f3a3b7391321dd82b94`).

Root-accepted NC680 passive extraction of the closed stream found all 15 focus attempts returned `stale_identity` with `focused=false`; the last six used presentation revisions 23, 25, 27, 29, 31 and 33. Its seven-minute budget ended after identifying the query-4 gap and did not recover an accepted focus or case outcome. NC674 source/component acceptance therefore does not establish actual finite focus recovery. NC685's central browser/Host diagnosis is in progress; the candidate explanation that `App.retry_presentation` full-document ticks from `beforeinput` can starve admission remains a source hypothesis, not an established cause or repair. NC682's capacity proposal is on hold and has not been selected. F12 HOST/readback acceptance `bf4f1f75…`, engine65/12 with both Node negatives, neutral28+6, separate export and native 5,344-assertion barrier evidence remain reused unchanged. All full-runtime predicates and global eligibility remain false. The next source snapshot is restart v11 (local archive path: `.agent-work/appended-implementation-20261016/runtime-D03-repair-v1/runtime-composition-repair-v1/runtime-allowance-20261018-v1/native-runtime-v1/P01-keyboard-diagnosis-v1/P11-pointer-diagnosis-v1/retired-form-selective-execution-v1/RESTART-20261020-v11.json`), SHA-256 `5501a6a06b943855ee43edbfcffea7d18246509450b3f31c11131053bf3f18cc`; resolve the focus and capture-cap diagnosis before the next complete 23+3+6 runtime/readback gate. Do not infer a future pass.

### F10 normal HOST BOTH refresh — 2026-10-20 UTC

Root accepted F10 HOST BOTH/editor construction and full independent readback in the F10 acceptance record (local archive path: `.agent-work/appended-implementation-20261016/runtime-D03-repair-v1/runtime-composition-repair-v1/runtime-allowance-20261018-v1/native-runtime-v1/P01-keyboard-diagnosis-v1/P11-pointer-diagnosis-v1/retired-form-selective-execution-v1/foundation-conduit-host-refresh-v1/readback-execution-v1/ROOT-FULL-READBACK-ACCEPTANCE-v1.json`), SHA-256 `72197f6ed308306bc705adfcca1ea4d197af3eadce7bd06fd7d2e167663b6fcc`. It binds 36 translation units, 18 archives, 73 captures, 2,103 raw / 2,748 configured source records, 19,423 SDK metadata rows and 96 retained engine originals. Reader `97292` closed naturally with status 0 in 69.637076s at 724,627,456-byte peak RSS. This accepts construction and full readback only; runtime and production eligibility remain false.

The shared browser-conduit repair (`7c478b32…`) passed 74 focused model tests and actual Firefox trusted composition commit plus Escape cancellation (`59397`, `78468`), with natural closure and a modeled receipt adapter. The later actual Firefox window-deactivation component is Root-accepted in NC607 (local archive path: `.agent-work/appended-implementation-20261016/trusted-browser-window-deactivation-v1/NC607-v1/root-validation-recovery-v2/ROOT-ACCEPTANCE-v4.json`), SHA-256 `d4de80f5ee065eff2cf31243fb95271594b2fa016c0870175a7269acdee428bf`: trusted editor/window blur, `document.hasFocus() == false` and shared conduit suspension were observed. Its receipt adapter remains modeled; it establishes no Foundation/native receipt or full runtime behavior. The F9 first readback failure (`84395`, missing explicit grant for the added `source.json`) and its successful one-file-grant retry remain historical. F10 used the fixed qualified SourceRoot snapshot; this documentation update does not change it or call for another HOST/engine build. Native65/12 with both Node negatives, neutral28+6 and separate export remain accepted and reused unchanged. Scoped engine-consumer eligibility is true on the exact neutral28+6 evidence (`f52af0fd…`); the separate global full-integration gate remains false. The native barrier component (NC585) establishes only two cases / 5,344 assertions and its partial-order contract.

Remaining gates are Foundation23+3+6 composition with the current full preparer; trusted browser input and native proof/source-object joins; terminal/navigation reader integration; eligible Foundation receipts; ordinary public-host, QuotePad, viewer and performance evidence; native GUI and full product qualification. Production eligibility remains false. The accepted engine, Native65/12 with both Node negatives, neutral28+6 and separate export remain reused unchanged. Ordinary web edits remain packaging-only; compiled application edits rebuild only the small portable module. Native orchestration remains the active coordination override, without session/board/claim/lifecycle administration or aggregate attempt/time ceilings; resource protections and behavioral deadlines remain. See the [validation checkpoint](appended-validation.md#f10-normal-host-both-refresh) and [pending qualification](../.agent-pending/appended-kernel-qualification.md).

### S4 full Foundation23+3+6 runtime and D11 construction/readback checkpoint — 2026-10-20 UTC

S4 (`94652` / `fdbed5`) failed with `Surface session admission is closed`: the original caller exited 2 while the outer owner returned 0 and closed naturally after 88.429694211s (3,195,813,888-byte peak RSS). All 196 inputs (141,611,880 bytes) were unchanged. Only E01 was reached: 1,329 events, nine case records and no outcome; E02–E23 were not reached. The accepted observer identifies kernel `gui_web_receive` call 657 at event 1331 on command turn 1330, but no JavaScript stack was captured; original boundary events 1330/1331 were not committed. A sixth poll is a source prediction only. See the S4 failure record (local archive path: `.agent-work/foundation-full-runtime-20261020-v4/ROOT-RUNTIME-FAILURE-v1.json`) (`15eb4741…`). S3 was never armed or launched; preserve its root redundant-chmod physical-record failure.

D11 host diagnostic source `6af9e012…` adds bounded flags, first-failure, close and callback-site observation only; it does not fix admission behavior. Build `90059` (`f8dfb4`) closed naturally with caller 0, 36 translation units, 18 archives, one link and 73 captures at 703,336,448-byte peak RSS. Root accepted independent readback `34642` (`98593a`) in the D11 record (local archive path: `.agent-work/appended-implementation-20261016/runtime-D03-repair-v1/runtime-composition-repair-v1/runtime-allowance-20261018-v1/native-runtime-v1/P01-keyboard-diagnosis-v1/P11-pointer-diagnosis-v1/retired-form-selective-execution-v1/foundation-surface-admission-host-probe-v1/readback-execution-v1/ROOT-FULL-READBACK-ACCEPTANCE-v1.json`) (`508fe04a…`; 87.479820s, 722,132,992-byte peak RSS): 2,103 raw and 2,748 configured source records, 19,423 SDK rows and 96 engine originals joined. The new kernel Wasm is 1,719,543 bytes (`5d0b0f40…`); the engine factory and Wasm were reused unchanged. This accepts construction/readback only. F11 still needs the complete 23+3+6 runtime and native/static/trusted/source-object/SDK/closure/readback conjunction; its source-bound packet and native proof are being prepared. Engine65/12+Node, neutral28+6, separate export and existing private C/Rust evidence remain reused unchanged, without reruns. Production eligibility remains false.

### S2 prior full Foundation23+3+6 runtime attempt — 2026-10-20 UTC

Root accepted the NC628 live-prefix repair and NC629 kernel-only scanner source repair for fresh source binding (source acceptance (local archive path: `.agent-work/foundation-full-runtime-20261020-v2/ROOT-SOURCE-ACCEPTANCE-v1.json`), `a28ead82…`). Preparation `24969` (`1f2412`) was accepted for 50 files / 112,924,060 bytes, including 46 original suffix/index occurrences and the three JavaScript repairs. S2 runtime `25610` (`366822`) then failed in E01 with `Surface session admission is closed`; only 1,329 events and nine case records were captured, with no outcome. E02–E23 were not reached. Outer owner 0 closed naturally after 86.114902247s at 3,296,681,984-byte peak RSS; original caller exited 2. All 196 inputs (141,608,554 bytes) were unchanged. Independent extraction saw stale focus followed by open successful resync/poll and no captured native throw; the closure cause remains unresolved. NC637's bounded observer-origin probe is underway. Runtime and independent full readback remain unaccepted; the source repairs do not accept Foundation23+3+6 or production eligibility.

### S1 prior full Foundation runtime attempt — 2026-10-20 UTC

Under the already-authorized metadata512 profile, preparation `67409` (`fa5f67`) was separately accepted for 50 files / 112,922,832 bytes, including 46 original suffix/index occurrences. Fresh runtime `97528` (`a51cd8`) failed in E01 with `Actual Foundation begin/result ownership join is missing`; E02–E23 were not reached. E01 contains 1,197 events, 12 case records, five GUI operations and two polls. The outer owner returned 0 and closed naturally after 95.766s; all writers and descendants closed. The original caller exited 2 with capture-failed, so this is a failed partial run, not runtime acceptance. All 196 selected inputs (141,607,148 bytes) were unchanged. See the closed failure record (local archive path: `.agent-work/foundation-full-runtime-20261020-v1/ROOT-RUNTIME-FAILURE-v1.json`) (`87ac2d4e…`). NC626 independently found successful same-owner begin/result pairs for query 4 and command 9, so the E01 failure does not establish that those pairs are absent. NC628's live-prefix/source diagnosis remains in progress. Separately, NC627 found a kernel-only scanner-policy mismatch; the NC629 source correction is pending. Full Foundation23+3+6 runtime/readback, public eligibility, and ordinary QuotePad, viewer and native-GUI qualification remain pending; production eligibility is false.

### PE31 partial BOTH checkpoint — 2026-10-20 UTC

Foundation8 construction/full readback (`b3669a5b…`), engine65/12 with both Node negatives, neutral28+6 and separate export remain accepted and reused. PE31 runtime `5266` closed naturally with caller/controller 0 in 199.907787300s at 3,173,257,216-byte peak RSS; all 124 inputs stayed unchanged (`c9207871…`). Independent reader `45366` closed naturally 0 (`f744ea`) in 57.929433067s at 531,873,792-byte peak RSS; Root accepted the complete partial-BOTH source/object/SDK/engine/package conjunction and all 12 static admission domains in the full-readback record (local archive path: `.agent-work/appended-implementation-20261016/runtime-D03-repair-v1/runtime-composition-repair-v1/runtime-allowance-20261018-v1/native-runtime-v1/P01-keyboard-diagnosis-v1/P11-pointer-diagnosis-v1/retired-form-selective-execution-v1/foundation-kernel-role-partial-readback-execution-v2/ROOT-FULL-READBACK-ACCEPTANCE-v1.json`) (`eda07c35…`). PE31 now qualifies this private partial-BOTH runtime: script-origin web calculator/tabs/rich text, native echo and ACK, provider 41→42, compiled same-key 17+25→42, matching real `engine.frame`, and ordinary native/Worker close. Preserve earlier factory, metadata, frame and reader failures as history. Rust partial-BOTH host runtime is now Root-accepted: runtime `93102` (`c583fc`) and independent reader `85895` (`01ad55`) both closed naturally with status 0; runtime elapsed 201.523678465s (peak RSS 3,173,765,120 bytes), reader elapsed 56.112416225s (peak RSS 551,481,344 bytes). The accepted record binds the complete source/object/SDK/engine/package conjunction, all 12 admission domains, all 124 unchanged inputs, and final interpreting/stream rechecks (full-readback acceptance record (local archive path: `.agent-work/appended-implementation-20261016/runtime-D03-repair-v1/runtime-composition-repair-v1/runtime-allowance-20261018-v1/native-runtime-v1/P01-keyboard-diagnosis-v1/P11-pointer-diagnosis-v1/retired-form-selective-execution-v1/foundation-rust-memory-repair-readback-execution-v1/ROOT-FULL-READBACK-ACCEPTANCE-v1.json`), SHA-256 `ad701520b6e5843bd7ee2fdc43ebcad7f3e6222921973140369bc6730e442193`). Accepted behavior is script-origin calculator/tabs/rich text, native echo+ACK and provider 41→42, same-generation compiled 17+25→42 with a real frame, and natural close. Prior startup/capacity/inline traps and binding failures remain history. Separately, Root accepted the retained Rust TUI baseline in `.agent-work/appended-implementation-20261016/rust-retained-tui-application-v1/NC558-v1/root-repair-v2/ROOT-TUI-ACCEPTANCE-v1.json` (local archive) (`7cddbe33…`): optional-provider module `340c0340…` passed eight Node groups, the native provider-present probe, and a real PTY 17+25→42 run with natural Ctrl-Q exit and restored terminal settings. The NC574 edit-loop acceptance in `.agent-work/appended-implementation-20261016/rust-tui-application-edit-loop-v1/NC574-v1/ROOT-ACCEPTANCE-v1.json` (local archive) (`cafce1fd…`) covers two checked-u32 edits producing 43 and 44; each passed eight Node groups, native-provider probing, and real TUI interaction. Compile/pack/inclusive save-to-visible-result-and-close times were 2.049951/0.171581/6.672135s and 1.910936/0.193674/6.346741s, within the 5s/1s/10s targets. These are two warm local TUI samples, not statistical, GUI, or browser qualification. The optional module is Node/native/TUI only; F8 partial-BOTH acceptance remains bound to the older required-gateway module `d6a86fe8…` and its separate record (`.agent-work/appended-implementation-20261016/runtime-D03-repair-v1/runtime-composition-repair-v1/runtime-allowance-20261018-v1/native-runtime-v1/P01-keyboard-diagnosis-v1/P11-pointer-diagnosis-v1/retired-form-selective-execution-v1/foundation-rust-memory-repair-readback-execution-v1/ROOT-FULL-READBACK-ACCEPTANCE-v1.json` (local archive), `ad701520…`). QuotePad `3a4d8fa0…` is component acceptance only. Native GUI remains false; eligible public-browser ACK metrics remain unrun. Next is current-source HOST BOTH/editor refresh (36 TUs, 18 archives) using the retained engine and read-only guest SDK; full Foundation 23+3+6, ordinary public-host/browser/viewer and production gates remain pending; production eligibility is false. Ordinary HTML/CSS/JS edits remain packaging-only and compiled application edits rebuild only the small portable module.

### Foundation BOTH redaction checkpoint — 2026-10-20 UTC

Root accepted NC505’s central copied-close lifecycle repair: defer copied CLOSE until authentic editor retirement, then run trusted close; the bridge drains only exact owned context retirement while closing. Native Owner/codec fixtures passed 556 checks, the maintained bridge suite 66 cases, and the maintained Owner suite 16 groups / 6,680 assertions. PH27 source is accepted (`1ff1bcb6…`), including exact projection, decoder and four-resource admission. Preserve failed Foundation7 (`31382` / `2f9ab2`, `1c91d906…`) and the three closed readback failures: MR1 stale reader pin, MR2 construction-reader pin, MR3 (`31631` / `e8196b`) logic pin after 54.929799s. NC516’s monitor repair is accepted (`5a141611…`); its controlled GUI restore comparison reproduced old ENOENT and correct new traversal, without proving F7’s hidden original cause. Foundation8 construction `9783` closed 0 (`11253d`) naturally, reusing accepted 883-source preparation (`993bf0fd…`) for 36 TUs, 18 archives and 73 captures, at 668,241,920-byte peak RSS. NC524 corrected only two expected producer identities; real source-chain acceptance and three mismatch controls passed, with the first fixture failure preserved. Full independent readback `41381` closed 0 (`d03a3a`) naturally in 68.782192s at 679,002,112-byte peak RSS. Root accepted its complete source/object/SDK/engine conjunction and final record recheck at `E/foundation-close-monitor-readback-execution-v4/ROOT-FULL-READBACK-ACCEPTANCE-v1.json` (`b3669a5b…`), using request v6 (`38d67a2f…`) and driver (`198ff54c…`). No preparation or build was repeated for readback; retained engine and SDK were unchanged. Fresh PH27/F8 binding passed source/resource admission in 1.392s, independent 123-record physical review, preparation (1.845s) and verification of 23 prepared files. The passive-reader successor admits 60 sources / 1,829,100 bytes. Actual partial-BOTH runtime PE29 (`60761` / `e44020`) closed all writers naturally in 173.947405s at 3,264,040,960-byte peak RSS; its outer caller is 0, but its original controller is 2 and its seal is `capture-failed`. The page-close error is `Kernel terminal-outcome mailbox refused`, with 439.7s case / 732.3s whole allowance remaining. All 123 inputs (139,122,034 bytes) were unchanged. Preserve `E/foundation-partial-both-runtime-execution-v29/ROOT-ORIGINAL-CALLER-CLOSED-FAILURE-v1.json` (`4e11ec32…`). Root source-accepted NC531’s one-hunk central JS repair (`374a8d5c…`): retirement-mailbox probes while closing use last-ready authority. Actual Owner fixtures passed 601 assertions; the original Bridge comparison failed 1/67 while the candidate and maintained suite pass 67/67, preserving refusal controls. PE29’s numeric post-close refusal remains uncaptured. NC535 independently accepted exact preparer base-plus-delta projection for this private partial profile, with immutable F8 facts and a required Root check that final prepared bridge bytes match the candidate; NC528 does not independently rederive that projection. PH28 and fresh runtime binding are in progress without native recompilation. Rust PH27/F8 packaging and four-resource admission are source-accepted (`419bed27…`), reusing the unchanged 30,432-byte Rust module; actual Rust host runtime is unrun. Partial BOTH runtime is still unaccepted; full Foundation 23+3+6, native/TUI/Rust host runtime, viewer and production qualification remain incomplete. Ordinary web edits remain packaging only; compiled application edits rebuild only the small portable module.

The accepted engine 65-case / 12-batch runtime plus both Node negatives, neutral28+6 and separate export remain reused. Actual partial BOTH runtime is still unaccepted; production eligibility is false and the integrated viewer remains unfinished.

Preserve PE19 (`97256` / `a0ee1d`, wrong smoke options), PE20 (`13282` / `68ec3f`, strict wait over safe redaction) and PE21 (`85659` / `e62653`, `Widget generation was reused`). PE21 closed naturally after 67.1744s with 2,415 events, 31 GUI operations, 32 auxiliary records and 30 polls. Only its initial six-widget scene and later empty snapshots were serialized; the failing key/internal call and a restored scene were not captured. NC447 repairs the exact smoke options; NC451's prior empty-redaction wait remains accepted.

Root accepted and integrated NC457's central two-file resumable redaction repair: preserve compiled declarations and geometry, scrub state/callables, hide and disable controls/pages, clear hidden page labels and navigation authority, and retire `engine.frame`. Existing stale-generation, service, navigation and input gates remain. Its real MemoryAdapter fixture passed 41 checks. NC463's source classifier passed 29 inert cases including an actual patched WebAdapter serialization pair; Root froze PH21 with only `smoke_cases.mjs` changed (`325c568b…`) among its 18 selected files. Final same-key 17 + 25 → 42, native echo, provider, frame and ACK predicates and 32-poll / 96-operation limits remain unchanged.

Fresh Foundation construction `E/foundation-redaction-construction-v1` admits 883 source files (two changed, 881 unchanged) and preserves all 19,423 SDK facts. Caller `78949` closed 0 (`d5b9b9`) with 36 TUs, 18 archive create/index pairs, one link and 73 captures; the build reported success, streams closed naturally, and peak sampled RSS was 652,619,776 bytes. Independent full readback `89740` closed 0 (`8b2030`) in 65.790746910s at 700,121,088-byte peak RSS. Root accepted FR2 at `E/foundation-redaction-readback-execution-v2/ROOT-FULL-READBACK-ACCEPTANCE-v1.json` (`87064bf247737b6ae8901067b4f5fca3d10135bc58e16dd0668babf2a022a0bc`), bound to this construction. This accepts Foundation source/object/SDK/engine readback; it does not accept partial BOTH runtime. New Foundation Wasm is 1,711,841 bytes (`77414753…`); the retained engine and SDK were reused unchanged.

Preserve readback `19014` / `f88569` as a failed 10.0869s run: four unchanged helper records still selected the previous source root. The corrected physical bindings passed the actual reader boundary (old records reject, fresh four pass). NC467's fresh 69-input / 54-source PH21 binding passed source/resource admission and independent physical review; preparation `49297` and its independent verification passed. PE22 (`35634` / `f01780`) reached the restored controls and `lhs = 17`, but capture failed on a fractional timer delay: production emits finite binary64 delays while the old observer expected integers. Root accepted NC473's timer typing and bounded failure-context repair; PH22 is accepted. Root also accepted NC471's partial-readback source, which is ready with explicit Foundation6 bindings, but its actual readback has not run.

PE23 failed before runtime acceptance when the bounded output scan observed live `prefs.js` as REG/nlink=0. NC475 is Root-accepted: only live workspace/profile REG/nlink=0 permits three bounded reobservations, charging detached bytes; prelaunch and final closed scans remain strict. PE24 (`89502` / `aa29c3`) failed after 96.042s at 3,293,204,480-byte peak RSS: descendant closure inside the capture helper discarded the controller's original error channels, and no seal was produced. The outer process nevertheless closed naturally (primary 1, one child reaped, no termination or surviving descendants). Its prefix shows `lhs = 17` restored after 31 polls and a later `rhs = 25` request pending against snapshot `rhs = 0`; four timer callbacks include `4019355.9999465942` ms. This is partial evidence only, not runtime acceptance.

Root accepted NC480's failure-only diagnostics and controller phase/clock context (PH23), followed by NC487's smoke-pacing repair (PH24). PE25 (`17764` / `4473f5`) and PE26 (`6601` / `552c8b`) failed the 90s aggregate case-RPC deadline during `runCase`; NC492 confirmed PE26 had 12 polls versus PE25's 30 with the same 21 completed PUMPs, but no wall-time gain. Preserve PE27 (`50489` / `14bec4`) as a closed failed Take-phase assertion; NC497's failure-result admission and NC499's source-reviewed pending-phase correction retain the ticket, content and completion predicates. PE28 (`29097` / `12af5c`) captured auxiliary record 26's complete native report (calculation, tabs, rich text, echo and increment) and record 27's compiled `17 + 25 = 42` and frame; auxiliary records 28–29 describe one observed case with 23 operations / 18 polls. The Worker received a close command at event 3958 and the native CLOSE/free tail reached event 4018 by 228.585s; the prefix stayed stable through 595.249s. The shared 600s case clock expired at page-close with 295s left on the whole-run clock; this detects the stall but does not explain it. The caller closed 1 after 606.290s at 3,088,367,616-byte peak RSS; inner finish reported surviving descendants and no seal was produced. Independent postflight found all 123 inputs (139,088,775 bytes) and the outer owner unchanged. These observations are not runtime acceptance; NC506 independently matched all four closed stream files, all 492 chunks and 4,107 spans in the unsealed diagnostic; the final 14,914 records include a 42-byte timeout reason. This verifies captured observations without a successful seal or full state-machine acceptance. NC505's central close repair is source accepted; see the current construction/closure checkpoint above. NC489 failure-path RPC/collector wall- and CPU-time metrics remain accepted; NC491's PH25/new-owner profile allows only aggregate case and Worker 600s, inner 900s, outer 1200s and cleanup 15s, preserving individual Marionette 15s / Bridge 30s, startup/physical-timer deadlines and all byte, machine, GUI and poll predicates. NC494 passed physical review/admission for 123 inputs. FR2 Foundation construction/readback remains accepted; NC471's required full partial-reader execution is pending. NC501 Rust PH26 source and NC503 full-reader TAKE-phase source are accepted, but no Rust host or full Foundation runtime is accepted; full Foundation 23+3+6 and viewer/production qualification remain incomplete. NC493's E09/D03/D04/D05 schedule gaps and missing static admission require coherent full-family integration later, not an added gate on this partial-BOTH run. Ordinary rich web and portable C/C++/Rust work keeps the 5s compile / 10s inclusive fast-loop targets. Production eligibility remains false and the integrated viewer remains unfinished.

The accepted full native runtime is `E/runtime-editor-terminal-recovery-v1/operation-v1`, original runtime caller `88524` closed 0 (`3e81f9`) in 167.2766838009993s. It passed all 65 cases / 12 batches in the direct browser Worker, including expected-negative cases; both Node negative controls also passed. All 47 physical inputs were unchanged, two owners and two streams closed naturally, and the monitor thread joined. Peak sampled RSS was 3,708,030,976 bytes and output was 211,516,169 bytes. Independent reader `21550` closed 0 (`349fae`) and accepted both outputs. The Root full readback `ROOT-FULL-READBACK-v1.json` has SHA-256 `8c89be49af69c96232c8a49c21eebdace32e39a13a5535f14fd3e4a2efc7f9dd`; neutral-closure readback `ROOT-NEUTRAL-CLOSURE-v1.json` has SHA-256 `d134c763feebb40289186015a0fd7a9efc80de6aa9833b07869db5278fd21d8a`. The original runtime caller and independent reader are separate records. Full runtime `13400` failed at E09 and remains preserved as a failed run. Focused negative diagnostic `23995` passed three negative paths / 76 case assertions; it is partial evidence, not the full gate. NC283 corrected only E09's mistaken inner-unknown-receipt assumption: the native wire adapter intentionally returns terminal uncertainty in the owned outer response and has no inner-unknown body.

NC286's streamed-hash source-record repair is accepted, and the actual neutral request/binding passed. NC289's narrow logical `F01`→`D05` alias is accepted with the original two F01 anchors preserved, not weakened. Stage `32630` closed 0 (`c1e42e`) in 10.529789499s: 381 source files / 617,388,940 bytes produced 76 staged files / 291,929,178 bytes. Independent readback `84839` closed 0 (`43310a`) in 3.290980267s; Root accepted `E/neutral-execution-v2/ROOT-STAGE-ACCEPTANCE-v1.json` (SHA-256 `7b915500a5afb9658bdd103310f3f1e0d13b2f5e5bb9372663ec3bdea34b9600`). Separate export `71765` closed 0 (`4a00f6`) in 31.191051768s at `EX=E/neutral-export-execution-v1`. Root accepted `EX/ROOT-EXPORT-ACCEPTANCE-v1.json` (SHA-256 `0a990abbd56e9d7717f4d26a6070c6fe069dc8c674db178b43ee388f1521cc36`). Independent reader `52010` closed 0 (`24525e`) in 15.122170330s at 202,629,120-byte RSS; its proposal log is `EX/export-readback-v1-owner/child.log`. It accepted exactly three files / 582,956,175 bytes, verified all four pins, target and paired SDK against the staged payload, and rehashed/postflight-checked the canonical eight helpers and group bytes. Strict-consumer byte/static contract eligibility is true; full integration and production remain false. Preserve the earlier 24-test source diagnostic and the two request-size failures as history; no global cap was raised and all 381 source facts were preserved.

Continue the current fast application loop: ordinary appended-web and portable C/C++/Rust work remain in scope. Foundation source compatibility is accepted: NC291 v2 controller `ROOT-SOURCE-ACCEPTANCE-v2.json` (`9ba17a4e…`) reuses 30 baseline checks and adds four publication plus two refreshed packet checks; NC294 reader source acceptance is `4da41a7b…` with 12 focused checks; NC295 SDK wrapper source acceptance is `d5810f98…` with eight focused checks. The user authorized the Foundation BOTH host construction, required readback/runtime qualification and necessary scoped repairs. The concrete construction scope is `E/foundation-authorization-preparation-v1/SCOPE-COST-v3.json` (`827b25b6…`). First caller `85997` closed 125 before configure because the retained GUI archive omitted seven current patches. The reviewed reintegration repair produced 728 members (645 unchanged upstream / 83 current integration); four focused fixtures passed, and the previously failing default-group check passed after replacing the three bundled files. Fresh source admission independently verified 883 files with exactly three changed / 880 unchanged and preserved all 19,423 SDK rows. Second caller `57900` closed 125 (`9950ff`) during configure, before compilation: the supplier toolchain defaulted its processor label to `x86` while the verified manifest declares `wasm32`. NC307's project-wrapper repair is source accepted with a real compile-free CMake fixture (one test / 0.172s); it passes the manifest processor through the supplier's supported setting and preserves the strict editor guard and retained SDK. Foundation attempt 3 then configured successfully but caller `75621` closed 125 in the strict compile-database reader, before any target compiler or runtime ran (`E/foundation-wasm-processor-recovery-v1/ROOT-ORIGINAL-CALLER-CLOSED-FAILURE-v1.json`). The reader rejected normal CMake-exported commands because its argv parser requires separate `-MD`, `-MT` and `-MF` flags; the actual Ninja commands contain the capture wrapper and strict dependency group, which the exported rows omit. Metadata-only Ninja command extraction (`E/foundation-wasm-processor-recovery-v1/compile-database-diagnostic-v1/RESULT.json`, `ninja -t commands gui/gui_appended_engine_wasm.js`) completed in 0.010141s without compiling or executing a target. After removing the wrapper and strict dependency group, the independent source+object projection matched all 36 selected rows to the saved expanded Ninja commands; this establishes selection accounting, not successful build-command admission. Preserve the failure and natural owner/stream closure. Root owns NC313's reader repair in a fresh source directory; the out-of-scope baseline write was restored to SHA-256 `7894d8d0488af6c9e2a6259ad448080b4ba7d0e9dbba23d64a79aa6b86d30a23`, and the internal copy stayed unchanged. Next gate is the scoped Foundation retry through repaired reader, then independent readback and required runtime; user authorization covers these scoped operations and required repairs, so no further approval is needed. Attempt 4 (`54487`, closed 125 / `e58f1b`) reached a passed inner result, all 36 compiler invocations, 18 archive create/index pairs, one link and 73 original captures, with natural target closure and unchanged source/SDK snapshots. The original caller still failed outer capture validation, so this is not an accepted Foundation construction. A controlled comparison changed only the producer dictionary insertion order: JSON decoding reordered it, changing `include.cmake` and `c-rules.cmake`; restoring the original order matched all eight installed files. NC323's isolated deterministic-renderer repair preserves the four producer pin checks and passed two real-interface fixtures (0.046s), with independent Root review. The compile-database repair is source accepted after independent strong review and eight focused tests (0.184s); the versioned outer collector cohort passed source review and 13 fixtures. Foundation readback and construction remain accepted: caller `5954` closed 0 (`ecccd5`), Root acceptance `e0a6f68b…`; the live Q/S/SDK/engine/source-object conjunction and full physical input namespace were rechecked. The accepted engine65+12, Node checks, neutral28+6 and separate export were reused unchanged; no rebuild occurred. Partial BOTH runtime is still unaccepted. Preserve PE1–PE6: `20214` omitted explicit prepare; `96051` rejected Firefox’s normal profile symlink; `39894` saw socket inode 0; `97790` and `99824` closed outer 0 with controller 2/capture-failed; `23125` hit the 90s readiness deadline with no durable Worker/native events or cases. PE7 `55402` also closed outer 0 (`bd07ef`) in 5.81498s at 1,964,584,960-byte peak RSS, but controller 2/capture-failed “Actual page failed before ready,” with zero durable Worker starts, native events or cases; all owners closed naturally. The separate approval-review timeout created no process or assertions; its supported identical retry launched this one actual PE7 process and is not another product failure. PH4’s window pending-state fix from NC354 remains accepted. PH5 static observer import (NC365) and fresh v11 binding (`2dddd5b9…`, NC367) were accepted; explicit prepare `23513` closed 0 (`e40455`) and independent verification passed. NC361’s actual tiny-Worker diagnostic `10846` closed 0 (`eb126a`) in 12.379s: awaited top-level dynamic import lost the first attach while `onmessage` was null; static/inline valid observers attached in 4–9ms online/offline, while the wrong-source negative rejected; all owners closed and seven inputs stayed unchanged. This establishes the miniature Worker attachment boundary only; actual production Worker attachment/page readiness remains unproven, and the next page-error investigation NC369/370 is pending. Rust view module and Node vectors are accepted (`20015`, `fab179`; 19,095-byte module `5fb0d48f…`; 2.059s compile, 0.236s Node, 2.337s inclusive, within 5/10s targets). This is codec/module evidence only, without Foundation GUI or TUI runtime. NC357/NC363 source review and NC368 schema-identity regression are accepted; promoted fixtures and the SDK README API entry are retained. Production eligibility remains false and the integrated viewer unfinished. SDK and engine gaps cannot be cleared by resource-reader or forwarding fixtures. Historical 900/1200s maintenance ceilings remain superseded; application 5s compile / 10s inclusive targets and behavioral deadlines remain unchanged. The integrated viewer is unfinished and production eligibility remains false. Preserve performance-evidence limits: the accepted preview-only evidence does not qualify pixels, trusted input or the retained integrated viewer. The exact `72e6` current Rust module component runtime is accepted; this is not release qualification. NC284's actual six-edit portable behavior loop is now accepted. Root acceptance `A/portable-behavior-loop-source-v1/ROOT-ACTUAL-MEASUREMENT-ACCEPTANCE-v1.json` SHA-256 is `e88581d343ee0cadc7a59b6dbea3ddd0d3efa06d78b63adb2fdcade84f780df8`. Caller `11175` closed 0 (`3ec445`) in 23.412836876988877s; all 48 owners/logs closed naturally. The retained console returned 24 typed results, including overflow and the `u32` boundary. Two meaningful `+1` / `+2` edits in each of C, C++ and Rust produced distinct module hashes and expected values 43 / 44. Nearest-rank p95 compile times were C 1.061971857s, C++ 0.865868485s and Rust 1.896808826s; inclusive loop times were 3.642895028s, 3.666430836s and 4.502795587s. Each language met its 5s compile / 10s inclusive target. Peak child-tree RSS was 265,887,744 bytes (under 1 GiB); the 120s whole / 15s cleanup limit and 4 GiB disk floor held. All 83 input facts and 20 SDK-directory facts were unchanged; compiler full-SDK byte verification was reused. Accepted source `30df3cdc…` is Sol source `7dc03b7d…` plus Root's disk-floor-only change from 2 to 4 GiB; targets were unchanged. This local-console component workflow compiled, packed, composed, verified and ran only the small guest module on retained console `be8af644`; it establishes no integrated viewer, native GUI, TUI, Foundation or general statistical qualification. No SDK maintenance, full-engine rebuild or Git publication is authorized by this handoff.

Current partial BOTH checkpoint: Root accepted PH7 harness source (`E/foundation-partial-both-harness-source-v7/ROOT-SOURCE-ACCEPTANCE-v1.json`, `2afec95b…`), including the generic Worker replay/observer integration. PE8 caller `52659` closed outer 0 (`8ff500`) in 5.17994118s at 1,876,127,744-byte peak sampled RSS, but the controller closed 2 with capture-failed at Marionette sequence 127: `Plain source prototype required`. One real Worker start was captured, with zero native events or cases; owners and writers closed naturally. This is attachment progress only, not partial BOTH runtime acceptance. PH8 realm fix and tests are pending; do not infer a result. Foundation readback and construction remain accepted and reused unchanged; the integrated viewer remains unfinished and production eligibility false.

PE9/PE10 continuation: PH8 source (`b0c82f9…`) passed NC380 review; actual PageRPC/page NodeVM sync/async realm comparisons pass the prior ACK boundary, but NodeVM is not Firefox/browser qualification. PE9 (`E/foundation-partial-both-runtime-execution-v9/ROOT-ORIGINAL-CALLER-CLOSED-FAILURE-v1.json`) caller `29804` closed outer 0 (`b13670`) in 6.641891378s at 1,828,757,504-byte peak RSS; controller 2 reported a generic observer failure before native events. Root accepted PH9 bounded-failure-detail source after NC390 review and four real producer/page fixtures (`E/foundation-partial-both-harness-source-v9/ROOT-SOURCE-ACCEPTANCE-v1.json`); predicates and resource caps remain unchanged. PE10 (`E/foundation-partial-both-runtime-execution-v10/ROOT-ORIGINAL-CALLER-CLOSED-FAILURE-v1.json`) caller `23742` closed outer 0 (`2bf068`) in 6.229234781s at 1,878,405,120-byte peak RSS; controller 2 capture-failed with `Aborted(\`Module.noInitialRun\` was supplied but \`noInitialRun\` not included in INCOMING_MODULE_JS_API)`. Each attempt captured one Worker start and zero native events/cases, with owners closing naturally. The actual cause is first native factory incoming-options incompatibility. Root/NC333 and NC392/394 are investigating a central repair; no repair, build or runtime acceptance is claimed. Foundation, engine65/12, neutral28/6 and separate export remain accepted/reused; viewer unfinished and production false.

PE11–PE14 continuation: PE11 (`E/foundation-partial-both-runtime-execution-v11/ROOT-ORIGINAL-CALLER-CLOSED-FAILURE-v1.json`) caller `9464` closed outer 0 (`e37a88`), after six native events; the ACK reader rejected the missing `liveevent_view` composition export. PH11 repaired the source boundary. PE12 (`E/foundation-partial-both-runtime-execution-v12/ROOT-ORIGINAL-CALLER-CLOSED-FAILURE-v1.json`) caller `39683` (`7e43df`) and PE13 (`E/foundation-partial-both-runtime-execution-v13/ROOT-ORIGINAL-CALLER-CLOSED-FAILURE-v1.json`) caller `68705` (`a4363d`) reached 15 native events before the observer refused dependent-metadata reservation. PE13 controller 2 capture-failed in 8.195424921s at 2,719,985,664-byte peak RSS: `bytes=260598+4096/262144; records=120+1/128`. Each run captured one Worker start and no completed cases; all owners closed naturally. None accepts partial BOTH runtime. PH13 (`E/foundation-partial-both-harness-source-v13/ROOT-SOURCE-ACCEPTANCE-v1.json`) accepts NC414’s bounded reservation repair: 1,024 bytes per span declaration and 2,048 bytes per held output, with the 262,144-byte, 128-record and 16-MiB caps unchanged. Four actual-observer API fixtures preserved exact packet bytes and order; seven boundary controls and finite serialization bounds passed. PE14 caller `42975` closed outer 0 (`602f22`) in 6.702979416s at 2,846,896,128-byte peak RSS, with controller 2/capture-failed before any case: `bytes=78891+1024/262144; records=128+1/128`, call 36/event 76. This crosses the previous byte-reservation failure and confirms synchronous pending-record pressure. Source trace finds no await between engine factory completion and endpoint setup/inspect/configure/start. NC418 owns the private checkpoint repair; no further runtime result is inferred.

Historical profile/runtime checkpoint (PE15–PE18): User authorization for `foundation-original-stream-32m-both-partial-metadata512-v2` remains recorded in `E/foundation-capture-profile-v2-preparation-v1/USER-PROFILE-AUTHORIZATION-v1.json`; preserve the earlier 128-profile failure. PE15 (`E/foundation-partial-both-runtime-execution-v15/ROOT-ORIGINAL-CALLER-CLOSED-FAILURE-v1.json`, caller `73937`/`a2031c`) and PE16 (`E/foundation-partial-both-runtime-execution-v16/ROOT-ORIGINAL-CALLER-CLOSED-FAILURE-v1.json`, `39649`/`b590e9`) passed CONFIGURE (296 bytes plus two frees), then failed controller capture after 50 events and zero cases. PE16 traced engine START call 25/op 1 → RESOURCE_RELEASE call 53/op 11 → denied kernel malloc-credit reservation 128+2; 81,222 metadata and 1,138,672 queued bytes fit the byte caps. PE17 (`E/foundation-partial-both-runtime-execution-v17/ROOT-ORIGINAL-CALLER-CLOSED-FAILURE-v1.json`, `92153`/`ee5a41`) under the authorized 512 profile passed the prior START-count boundary but failed at ADVANCE op 2/call 87: `bytes=261830+1024/262144; records=430+1/512` (128 calls total), with 50 events and zero cases. Preserve each failed run; none is runtime acceptance. PE18 (`E/foundation-partial-both-runtime-execution-v18/ROOT-ORIGINAL-CALLER-CLOSED-FAILURE-v1.json`) caller `55322` closed outer 0 (`56be58`) in 11.752735262s at 2,988,097,536-byte peak RSS, with controller 2/capture-failed, 316 events, six timers, zero cases, no cleanup and natural owner/writer closure. Failure: `Native GUI return is not owned by this actual command turn`; init was event 1, GUI create entered/returned at 315/316 after `await bridge.ready` with the turn null, and ready at event 317 was not durable. Do not weaken ownership predicates. PH18 source acceptance (`E/foundation-partial-both-harness-source-v18/ROOT-SOURCE-ACCEPTANCE-v1.json`; canonical Worker `6273b9c0…`) accepts NC418-v3’s exact-init-object, one-shot `beforeOwnerTask(action, actualInitMessage)` repair, independently reviewed by NC442. It restores command-turn ownership only for synchronous GUI create/ready; queued/startup async gates and watchdog are unchanged. Source checks passed (56 maintained Worker, five observer-init, nine scheduler, two Worker-init, exact projector); runtime remains unaccepted. This historical checkpoint predates PE19–PE21, documented above. The integrated viewer remains unfinished and production eligibility false.
Rust BOTH component (`A/rust-both-application-v1/ROOT-COMPONENT-ACCEPTANCE-v1.json`) and packaging (`A/rust-both-payload-adapter-v1/ROOT-PACKAGING-ACCEPTANCE-v1.json`) are accepted: Root promotion review `1aae61…` confirmed the three promoted source/golden files are byte-identical. The [repository fixture](../tests/fixtures/appended-rust-both/README.md) uses source `521db0b2…` and module `4cf3f3c6…`; the guest component passed 12 view goldens, 38 typed host calls, provider cases and two terminal negatives after one 2.687s compile. Packaging completed in 0.154s without guest compile or engine/kernel build. This remains component/package evidence only: no Foundation Rust, native or TUI runtime, and no inclusive 10-second flow, was qualified. Foundation build/full readback and engine65/12, neutral28/6 and separate export remain accepted and reused without rebuild. Native-only coordination applies; superseded cumulative caps do not apply, and retained-kernel/SDK maintenance, publication and full-engine rebuild remain out of scope. The integrated viewer remains unfinished and production eligibility false.

## Retired-form continuation checkpoint — 2026-10-19 UTC

The prior input-method candidate remains accepted (`a328a82e…`) with its copied capsule (`b1640613…`), but D06 runtime `72119` failed in 14.298s at `D06/actual-native-stale-before-effects`; both Node negatives, unchanged-input checks and natural closure passed. The 65-case / 12-batch runtime was not run. Preserve that result and diagnose the retired-lease path before retrying.

The new central Guard preflight is source accepted (`A/retired-form-preflight-source-v1/ROOT-SOURCE-ACCEPTANCE-v1.json`, `aae075f8…`): 67 canonical and 65 actual-editor-overlay native fixtures pass; this is not Wasm runtime evidence. Editor/native catalogue acceptances are `705dac95…` / `fa450dac…`, with 52 editor and 342 native catalogue checks passing. Producer source v2 is accepted (`A/retired-form-producer-source-v1/ROOT-SOURCE-ACCEPTANCE-v2.json`, `f6d16bd1…`); the retained-form runtime reader is source accepted (`D/retained-form-runtime-reader-source-v1`, `cd0b84a8…`).

Input preparation now accepts 381 physical files. Original preparation `42087` completed the 373-input assembly with producer exit 0 in 6.1968s, then its outer caller closed 1 during unchanged-prelink metadata admission, before any of six sidecar writes; preserve the failure and complete assembly. The narrow unchanged-prelink allowance passed 19 focused checks and independent NC262 review (`5e956f40…`). Metadata recovery and independent readback (`99258`) closed 0 in 3.622s and 2.137s without repeating assembly. Selective plan `E=D/retired-form-selective-execution-v1`, caller `11571`, closed 0 (`ecfe23`) in 204.1149s (producer 182.5295725s; peak RSS 611,553,280 bytes), with 135,886 physical input facts unchanged. Plan SHA-256: `6d91a5e2319708bb95f98c0d90f826f23a719f00ee6e9fd504b3c0badcfc40b5`.

Supported full-plan verification `74432` and independent plan readback `75608` closed 0 in 187.1067s and 11.5511s; command projection passed. Selective build `11620` closed 0 (`a7879b`) in 1,223.009s at 2,449,780,736-byte peak RSS with the accepted Guard + Shim fresh units, 50 imports including main and Unified13, five archive copies, zero repacks, one link and 174-artifact closure; no new engine runtime has run. Then continue with fresh capsule, causal D06 partial, complete 65-case / 12-batch runtime and independent readback, neutral28+6 and separate export. Foundation requires concrete scope/cost and separate authority. The viewer remains unfinished and production eligibility false. Current authority is native/main-agent orchestration only; no board/claim protocol applies. Justified in-scope retries are not subject to cumulative attempt/time caps; retain machine protections and each behavior deadline. Source-only work grants no SDK maintenance, full-engine rebuild or Git operations.

Independent candidate readback `96481` closed 1 (`0aa58a`) after 17.2525s at the reader’s incorrect all-52-direct-objects predicate. The actual ledger equals the accepted projection: 37 direct objects and 15 archive-only selected objects. Preserve this failed output and the successful build; isolated reader recovery is in progress, with five actual-metadata interface tests passing. No candidate, capsule or runtime acceptance follows from this partial readback.

## Input-method continuation checkpoint — 2026-10-19 UTC

The accepted input-method candidate is `N`, under `.agent-work/appended-implementation-20261016/runtime-D03-repair-v1/runtime-composition-repair-v1/runtime-allowance-20261018-v1/native-runtime-v1/P01-keyboard-diagnosis-v1/P11-pointer-diagnosis-v1/input-method-selective-execution-v1`. Original build `8260` closed 0 (`608c02`) in 1,243.652298s at 2,428,235,776-byte peak RSS: two fresh units (main + Shim), 50 imports, five archive copies, no repacks, one link. Plan SHA-256 is `62b781943494d766688679a148b0a4bc27c63e1693e6bbf2a261eb624698df0a`. The first readback's 18669 guard failure remains preserved; the exact-filename guard correction was independently Sol-reviewed. Passive readback `81894` closed 0 (`bd4591`) with caller 0 in 99.6959s. Root reader `90883` closed 0 (`34d878`), caller 0, and accepted 124,325 files, 8,631 directories and 174 artifacts in 36.7843s. Candidate acceptance is `N/ROOT-CANDIDATE-CALLER-CLOSED-ACCEPTED.json`, SHA-256 `a328a82ea65e0f58248f86ebc6bbf6e04d04238b7bb3d42c1e3572be0bb6b68e`.

Capsule `X=N/capsule-runtime-execution-v1` (`58729`) closed 0 (`bbd157`) with caller 0; independent readback accepted 16 distinct copies totaling 168,789,551 bytes. Acceptance is `X/ROOT-CAPSULE-COPY-ACCEPTANCE.json`, SHA-256 `b1640613384d2d96e0ed326f3a320ce3b821b5203270658499f75fab931b3132`. The first capsule parent-setup refusal is preserved; the empty-parent correction required no source-build retry. Full packet `X/RUNTIME-PACKET-CANDIDATE-v1.json` is `308c8e0c…` (65 cases / 12 batches); partial packet `X/D06-PARTIAL-PACKET-v1.json` is `7e5a0eba…` and retains the original D06 predicates. Independent NC242 physical source review passed in 3.0676s across all 47 inputs. D06 partial runtime `72119` closed 1 (`8da60d`) in 14.298337s at `D06/actual-native-stale-before-effects`; result SHA-256 is `53302a1cfb9a6a650a19ac12a2d03b5c7edc296bc1cd0f4066924415f905e586`. Both Node negatives passed; inputs were unchanged, owners and streams closed naturally, and the monitor thread joined. Current full-runtime execution remains unrun. Preserve this failure and diagnose the actual retired-lease result before another runtime. Keep the original runtime readback failure, input identities and accepted reader/case/peer findings recorded in NC234/NC218/NC226. The reader/header283 changes are accepted. Viewer completion, production eligibility and neutral/export/Foundation gates remain outstanding; no SDK maintenance is in scope.

The active user override is native-agent orchestration only; historical board claims are not gates. Incidental maintenance watch limits and cumulative attempt/time caps are superseded by generous maintenance watchdogs and meaningful application fast-path targets. Preserve each behavior deadline, resource bound and coverage predicate. Continue ordinary rich-web and portable-module iteration without SDK maintenance.

## Current successor-navigation checkpoint — 2026-10-19 UTC

Selective build `66597` closed 0 in 1,232.840s. Independent candidate reader `49372` closed 0 in 90.208s; Root rechecked all 174 artifacts and 129,990 readback facts before accepting candidate `b54335756ec47ca63432f079775a472635af07492210ba17005e578add234485`. It compiles only Unified13 and the metadata Shim, imports 50 objects, copies five archives, repacks none and links once. The accepted 16-copy capsule is `00ed675b…`; no retained SDK, kernel or full engine rebuild was performed. Earlier binding, reader and projection failures remain preserved. The corrected six-test command projection includes the direct Theme link input and matches the actual command ledger; the successful build was reused for that reader repair.

Complete runtime `87839` closed 1 in 172.967s (`558e6c56e4846c84467e40db741802bdc60f051f50fcc1cb8a08b133bd3bd12e`). Seven batches pass, including P11 keyboard (190 assertions), P11 pointer (164), E6a cancellation (82) and E8b (48). D06 in the eighth batch fails the successor-BEGIN observer; four later batches remain unobserved. Node's two negatives pass. All 47 inputs were unchanged, owners and streams closed naturally and the monitor thread joined; sampled peak RSS was 3,717,586,944 bytes. This is a failed complete gate, not runtime acceptance.

Saved-trace diagnosis proves actual old-document CLOSE (peer serial 1443) followed by successful successor BEGIN (1446). The observer incorrectly requires a replacement event emitted only while the old document remains open; it also returns wrapped trace rows where the case expects raw lifecycle events. `D06-CLOSED-TRACE-CAUSE-v1.json` (`27b2fc44…`) records this evidence and corrects the initial extraction that missed successor document 2. The observer/case repair is source accepted (`1e0faaa1…`), with truthful close/replacement evidence and the unchanged 15s wait. Fresh D06 diagnostic `65502` closed 1 in 11.965s after successor BEGIN, lifecycle ordering and successor JSC service passed; its first native successor query returned terminal uncertainty. A second diagnostic, `57112`, changed only Worker exception observation (46 physical facts unchanged) and closed 1 in 14.046s. It captured `authoritative input-method state unavailable`, followed by `v2 current capture unavailable` (`D06-NATIVE-QUERY-CAUSE-v1.json`, `0563a9f3…`). Both failures and natural closure/input-integrity evidence are preserved. A central native-client lifecycle reset is now source accepted (`539a2dd0…`, header `283876d4…`), retaining the accessor’s foreign/expired unknown behavior outside a retirement event. Actual main-TU syntax `77672` closed 0 in 12.709s, peak 1,306,435,584 bytes, with all 2,476 dependencies and 2,173 frozen cache entries unchanged (`f36ca474…`). Earlier resource preflight `8722` refused before any compiler launch; its failure remains recorded. Accepted dependency evidence limits the next build to main plus Shim, importing 50 objects including the repaired Unified13, with five archive copies and no repack. Source-catalogue admission and the reviewed selective producer are being completed before a fresh plan/build/readback and D06/full-runtime gates; there is no new engine runtime acceptance. Accepted source-only neutral28+6, staged-tree readback and separate-export preparation remain unexecuted. Foundation still needs concrete scope/cost and separate authority; the viewer is unfinished and production eligibility remains false. Native subagent coordination applies, without the superseded separate-chat administration or aggregate attempt/time ceilings.

## Prior select-event continuation — 2026-10-19 UTC

The current repair targets the history-dependent P11 pointer failure. In the prior paired run, pointer alone passed 177 assertions; keyboard followed by pointer passed the keyboard cases and then reproduced the missing input/change events. The accepted central `HTMLSelectElement` repair (`ccabb685…`, Root acceptance `aee6871e…`) restores the current-value baseline before committing an immediate changed selection initiated by the user. Seven structural checks and 28 extracted-method checks passed. The real Unified13 syntax compiler completed in 22.451s (caller `82670` closed 0); its 3,170 depfile facts and 2,173 cache entries remained unchanged.

The fresh 375-file source package was independently read back by `80619` (closed 0, 1.2396s); accepted preparation reused the existing 861.8 MB reuse tree without cloning. Plan producer `47423` closed 0 in 183.949s, full verification `46790` closed 0 in 204.222s, and independent plan reader `30344` closed 0 in 11.751s. Root accepted `retained-plan-v1/plan.json` (`2c65205c…`): two fresh units (Unified13 and Shim), 50 imports including main, 52 selected objects, five archive copies, zero repacks, one link, and all 129,974 verification facts unchanged.

The current selective build is `66597`, still running under one job, 4 GiB RSS, 24 processes, 8 GiB output and growth caps, a 4 GiB free-disk floor, and 14,400s inner / 16,200s outer watchdogs. The earlier invalid relative-path build binding is preserved; the corrected real-binder fixture passed and v2 is bound, so that incident is not a compiler failure. Root also corrected the relocated adapter's duplicated selective-execution output guard after a real CLI-forwarding fixture exposed it; the fixture now passes under sourceACKv2 (`39ae8403…`). Its private configuration is now ready; build completion remains unverified. No candidate, capsule, or runtime acceptance exists for this repair yet. After build acceptance, run the complete 65-case / 12-batch runtime and independent readback; then continue the already-defined neutral28+6 and separate export gates. Foundation still requires concrete scope/cost and separate authority before it proceeds. The viewer remains unfinished and production eligibility remains false. Use native subagent coordination. Aggregate attempt/time ceilings are superseded; retained SDK/kernel maintenance, full-engine rebuilds and Git publication remain outside this task's authority.

## Latest continuation checkpoint — 2026-10-19 UTC

### Current showPicker continuation — 2026-10-19 UTC

The preceding actual runtime, `68992`, closed 1 / `452762` at P11 (`showPicker` unavailable) after four complete batches / 48 passed cases; the full 65-case / 12-batch runtime remains failed and incomplete. Source tracing identifies `SelectShowPickerEnabled`, which defaults false and is not enabled by the prior direct Page startup. The accepted central startup repair (`d86c1384…`) enables it. The real main-TU syntax check passed in 12.313s, preserving 2,476 original depfile inputs and 2,173 cache entries; new engine/runtime behavior is not yet established.

The prior retained Theme build is `54226` / `cd3d23`, independently read back and accepted for its two fresh units, 50 imports, 52 selected objects and 174 artifacts. Accepted preparation produced a fresh 371-entry source package and complete 42,779-file / 861,802,853-byte reuse clone; source/copy owner `66565` closed 0 / `f2ff74` in 32.3448s, with independent owner `21866` closed 0 / `fc97ba` in 17.9191s. Only two cloned metadata files changed; raw51 SHA-256 is `686817b20bb8a311e9ec8c7d72addd455896805cdd6b5010ce3a51ce0a0ae569`, and the exact inverse restores `4ba…`. NC177 Root accepted 390 focused catalogue tests; this is not engine evidence.

The execution directory (`E`) is `.agent-work/appended-implementation-20261016/runtime-D03-repair-v1/runtime-composition-repair-v1/runtime-allowance-20261018-v1/native-runtime-v1/P01-keyboard-diagnosis-v1/showpicker-selective-execution-v1`. The accepted fresh plan is `8750` closed 0 / `4a9cba` (producer 186.625s; outer 194.186s), SHA-256 `6dffb6317a425b782980794271c2f0fe782abd93ec21c1e06f763775579a9746`; full verification `74342` closed 0 / `0130d6` in 174.610s and independent plan readback `9388` closed 0 / `d44063` in 9.12265s accepted all 127,043 physical facts. Root acceptance is `E/ROOT-PLAN-ACCEPTED-v1.json`, SHA-256 `abba25daf821b1267f0669fce7e278d2b5170ce949c47cf29d24d2c92405fc67`. Exact command projection `85028` closed 0 / `f50e5c` in 4.528s: two fresh units (main + Shim), 50 imports, 52 selected objects, five archive copies, zero repacks and one link.

Selective build `21606` closed 0 / `c3e835` in 1,204.591s, with peak sampled RSS 2,438,197,248 bytes and all 127,051 input physical facts unchanged; the owner and log closed naturally. Build receipt SHA-256 is `7d242e23aa78254c9ec143bde2e71aa49def041c6ad7d96f6c639dddc7f4d23d`. The first passive reader `28888` closed 1 / `a8a371` after 30.812s on a stale protected-header donor-root accessor (`bindings`), before publishing acceptance. The original failure and sources are preserved. Root repaired this accessor through the accepted showPicker compiler-root helper; a 0.686s real-metadata check reproduced the old error and verified the exact three header sets across five source roots. Independent NC195 review caught and resolved a stale output-path guard before launch; eight focused interface tests passed. Fresh passive reader `9846` closed 0 / `57f48c` in 89.126s. Root rechecked all 174 artifact identities and the complete input freeze; candidate acceptance SHA-256 is `476393e2498ce17ac9d33dbb8567d67c57741c868bac7674b65a05a10c82a342`. Fresh capsule owner `5578` closed 0 / `3454ac` in 3.480s; independent reader `f4af16` accepted 16 distinct copies / 168,159,769 bytes (`4f040081…`). The bound 47-input packet (`876777fb…`) passed independent physical/configuration admission. Actual runtime `39302` then closed 1 / `a37c03` in 148.697s at `popup.P11.pointer.selection-input-once`; result SHA-256 is `d64e89fe10d6dd31989d7cd63f55321f4d6c5d733132e53aec05c31da3e84425`. Four batches / 48 cases completed; P11 keyboard now passes, while the pointer successor changes `next-alpha` to `next-beta` without its expected input/change pair. All inputs remained unchanged and owners, streams and monitor thread closed naturally; sampled peak RSS was 3,604,119,552 bytes. Full runtime acceptance remains failed. The separate two-batch history comparison `10609` closed 1 / `eb80ff` in 24.128s: pointer alone passed 177 assertions; keyboard then pointer passed keyboard and reproduced the missing-event failure. All 47 inputs remained unchanged and owners, streams and the monitor thread closed naturally. This partial diagnostic supports a selection-history dependency and cannot qualify the complete gate. Root source-accepted the central guarded selection-baseline repair (`ccabb685…`, acceptance `aee6871e…`); seven structural checks and 28 extracted-method checks passed. The original host observer setup failure is preserved. Real Unified13 compilation and engine behavior remain unverified; the new selective lane must freshly compile Unified13 plus the metadata Shim, import 50 unchanged objects and verify direct ownership before the copied archives. Current maintenance watchdogs are 14,400s inner / 16,200s outer, with one build job, 4 GiB RSS, 24 processes, 8 GiB output/growth caps and 4 GiB disk floor. Earlier incidental maintenance and cumulative budgets are superseded; resource protections and behavioral deadlines remain. Do not rebuild the retained SDK, kernel or full engine. NC181 (`8bf32de9`), repaired NC185 (`ef48cb78`, independent NC195 `7b50c69b`), NC187 (`34e3262d`) and neutral NC190 (`8d820f6c`) source successors are accepted. The neutral execution binder NC194 is also source accepted (`1892be75…`); its original local error and subsequent Sol review corrections remain preserved, and no actual neutral binding has run. Required next gates remain causal P11 pointer repair, complete 65-case / 12-batch runtime and independent readback; then neutral28+6 and separate export. Foundation still needs concrete scope/cost and separate authority. Preserve all behavior deadlines and final predicates. The integrated viewer is unfinished and production eligibility remains false. The user's native-only coordination override remains active; no board/session/claim/lifecycle administration applies.

The Theme source repair is accepted: `tools/appended_engine_successful_donor.py`
(`bcd60bec…`) and `tools/appended_engine_theme_successor.py` (`df8d25…`)
preserve the default schema while retaining each origin's authenticated
dependency references. The original plan failure `13522` / `a935a1` remains
closed 1 after 331.474s, with 66,418 inputs unchanged; targeted reproduction
took 0.985s and 51 focused tests passed in 3.462s. Do not relabel that failure.

Fresh compile-free plan `21814` closed 0 after 250.147s, peak sampled RSS
747,393,024 bytes, retaining all 66,418 input identities and writing plan
`b814d4b7…`. Full-plan verification `66465` closed 0 / `388cb2` in
255.527s; independent readback `86972` closed 0 / `7db7a0` accepted the
complete plan and unchanged inputs (`8fb829c8…`).

Selective Theme build `54226` closed 0 / `cd3d23` in 1,589.035s, peak
sampled RSS 2,432,389,120 bytes. It compiled two fresh units (Theme and
metadata Shim), imported 50 objects, selected 52 objects, copied five archives,
repacked none and linked once. Full independent readback `37572` closed 0 /
`362c6f` in 68.282s, verifying all 174 artifacts and all 73,492 file / 6,147
directory input identities. Root final acceptance `0fe2184d…` was published
only after original caller zero and the complete physical readback.

The first reader `45210` remains closed 1: its dependency parser omitted
869 authenticated SDK cache seed aliases, although the compiler used the
matching private-cache copies. The strong repair `71fdbc57…` preserves the
existing SHA/size/mode checks, per-object compiler ownership and literal
non-cache dependency checks. Four focused regressions and the actual complete
52-object metadata check passed; no engine rebuild was needed for this repair.
The accepted validator/runtime cohort is `theme-runtime-source-v2`.

Separate capsule owner `91212` closed 0 / `67a288`; independent reader
`b6a137` closed 0 and accepted 16 distinct copies / 167,945,869 bytes
(`ea0ea1eb…`). Packet `b99a4a6b…` passed full physical admission and
independent review. Runtime `26277` closed 1 / `3b7a6e` in 1.817s: Node2
passed, while the restricted execution sandbox denied the local automation
socket before any browser case. The same bind probe failed inside that sandbox
and passed outside; no engine source change was needed for this setup failure.

Fresh packet `d7623626…` changes only the output namespace; admission
`41885` closed 0 / `7708a4`, followed by independent recovery review
`5044ccb5…`. The authorized browser invocation `50436` closed 1 / `554924`
in 112.530s at `Bounded Worker trace`. Three batches passed. The original
popup-a report records P00–P04 and P05.empty passed, including P01 keyboard
opening and P02 hidden-option navigation; P05.unidentified remained running.
Its 12,890-event trace occupied 8,384,670 bytes of the 8 MiB diagnostic budget.
All 47 inputs were unchanged and owners, streams and guard thread closed.
Independent failed-run review accepted the completed predicates and diagnosed
diagnostic trace exhaustion. The lossless repair doubles only trace capacity
to 16 MiB / 32,768 events; the 24 MiB whole-observation bound and all case,
batch, resource and behavior predicates remain unchanged. Real allocator
boundaries and saved original reports passed focused source checks and review.

Fresh packet `53c9d9e5…` passed physical admission and independent review
(`7fc06a7e…`). Runtime `68992` closed 1 / `452762` in 125.490s at
`Actual author showPicker API unavailable` in P11.keyboard. Four complete
batches passed all 48 cases, including all ten popup-a cases and E8b; Node2
and author31 passed. Popup-a retained 17,129 contiguous events / 10,425,892
trace bytes. Popup-b preserves four completed prefix cases; P11 and later
cases remain unqualified. Independent review `1e9fce9a…` revalidated the
original predicates, all 47 unchanged physical inputs and qualified process,
stream and watchdog closure. The final page-closure assertion was unreached.
The full 65-case / 12-batch runtime has not passed.

The actual embedded WebCore/JSC page exposes no select `showPicker` method.
Retained IDL and generated bindings contain it but gate it on the default-false
`SelectShowPickerEnabled` setting. Direct Page initialization currently sets
scripts/storage/idle features before frame initialization without enabling this
setting. A central startup repair and Theme52 selective successor (fresh
main.cpp plus metadata Shim, 50 imports) are being prepared; neither is built
or accepted yet. The outer Firefox page is the Worker transport, not the app DOM.

Small standalone edit-loop diagnostics passed: three web-resource packages
in 0.069–0.083s; two C module compiles in approximately 1.060s each; two C++
module compiles in 1.062s and 1.057s; two Rust module compiles in 2.073s and
1.870s. These compiled edits only add comments. Supported CLI receipts and
complete production SDK checks establish the small-module paths for these
fixtures, with natural process closure, not general performance acceptance.
The real six-resource rich-web fixture (1,543,773 baseline bytes) subsequently
passed three packaging-only HTML/CSS/JS edits in 0.08512s, 0.08195s and
0.08413s against a fixed 1.000s pack target. Exact resource/package readback
passed; the Python CLI observer and source route audit found no child compiler
or retained-component build. This observer does not cover shell bootstrap as
an exhaustive OS process ledger. Application startup/interaction targets and
integrated Foundation behavior remain pending on a working base.

Current Rust module `72e6b87b…` (17,898 bytes, application source `574ef580…`)
now passed three typed dispatches through retained console carrier `be8af644…`:
7+35=42, 1+2=3 and checked u32 overflow. Caller `6685` closed 0 / `16d894`;
pack, compose, verify and all three owners/logs closed, with eight input facts
rechecked. This is current-module component evidence, distinct from historical
module `96714fda…`. It does not accept Foundation, TUI, the integrated viewer
or host unit tests (still zero). No retained component was rebuilt.

The full 65-case / 12-batch runtime and independent readback, neutral28+6,
separate export, Foundation and remaining application work are still pending.
The viewer remains unfinished and production eligibility is false. Reuse the
accepted preparation, plan and build; preserve all original failures and
retained SDKs. Machine protections and behavior-specific deadlines remain;
incidental maintenance and aggregate qualification ceilings were superseded.

Only this chat and its managed subagents are writing. The user's native
orchestration override supersedes the historical separate-chat protocol;
old coordination records are retained as evidence without administrative gates.

This checkpoint supersedes older uses of “current” below. Git main is
`1660716ce6f5f59d2603859548e1eb18589938aa`,
`WIP - Preserve current appended application work`. The preservation commit
captured 57 files; ignored evidence, generated binaries and retained SDKs remain
outside Git. A later 18-file include/catalogue repair comprises 17 modified
tracked files and one new helper. CPP `9d5d434c…` adds four definition headers
while preserving the `ee79…` implementation body. Source acceptance
`8e1e2877…` retains 380 passing tests with zero skips.

Failed build `74326` / `16e3e0` exposed four undefined-inline errors.
The real-TU differential `35262` / `43177b` reproduced those four errors
and accepted the repaired TU with the original flags and VFS. Its 224.854s
total versus the old build handle-to-result interval of 771.435s measures
feedback for this defect, not total build or application-loop performance.
Failed outputs remain retained and were not consumed.

Fresh preparation `52904` / `8b7f2d` and independent readback
`27213` / `464efc` accepted 369 sources / 564,670,593 bytes, 12 metadata
files and 42,779 reuse files / 861,802,853 bytes, with 411 unchanged inputs
(`910584d9…`). Reuse that preparation. Binder `28640` / `7d86c2` and
physical admission `50696` / `cf005f` passed. Plan `86057` closed 0 /
`309554`; independent readback `93935` closed 0 / `b3df9e`, accepting
plan `70485f92…` and all input/process checks (`6aee128a…`).
The selective build remains six fresh units, 45 imports, 51 objects, five
archive copies, zero repacks, one link and 167 artifacts, with one build job.

Selective build `40718` closed 0 / `6d4dc7`; independent candidate readback
`89476` closed 0 / `a3c613` accepted all 167 artifacts, 51 dependencies,
six fresh compiles, 45 imports, five archive copies, zero repacks and one link
(`1f4feabd…`). The separately copied 16-file capsule was accepted after
`84784` closed 0 / `a49f70` and independent readback `67884` closed 0 /
`a385cf` (`cd3c0372…`). Reuse this candidate and capsule.

Runtime `70059` closed 1 / `c5f1fe` in 1.211s before Node, browser or
engine assertions: two helper paths failed the new driver’s private-directory
admission. Zero cases and batches executed. The driver retained preflight
`inputs_unchanged=false`; independent postclose readback verified all 47
physical/hash facts unchanged (`39ef3861…`). The two-helper-only correction
passed the real loader, negative boundaries and full configuration in 1.757s;
independent review `23060` closed 0 / `a3da89` accepted packet `754aefa8…`.
Fresh runtime `50492` closed 1 / `f47da6` in 95.915s at the same P01
keyboard-popup predicate after 38 cases / three batches and Node2. Independent
closed-failure readback `56890` closed 0 / `03feb4` revalidated those original
predicates, the failed P01 predicate, all 47 unchanged inputs and natural
closure (`d1dc743f…`). The failure is retained; no unchanged retry is planned.
The focused observer diagnostic `85730` closed 1 / `d6fe42` in 13.156s;
independent readback `37247` closed 0 / `5f9a47` verified its trusted Space
keypress on the focused select, with `defaultPrevented=false`, unchanged
inputs and natural closure (`3bd29648…`). This is partial diagnosis, not
runtime acceptance. The accepted link map selects the fresh keypress helper,
but the Emscripten theme inherits false popup keyboard capabilities. A
controlled source fixture passed 145 checks with the original policy closed
and a Space-only override open; independent strong review accepted its model
limits. The prepared override is `b6720505…`; Arrow policy remains false.
A distinct selective successor will need fresh Theme and metadata Shim,
50 imports and 52 selected objects; exact final inventory and source admission
remain pending. No SDK mutation or full engine rebuild is selected.
The focused feedback saved 82.759s against the 95.915s full path to P01; this
measures this diagnosis, not application editing or complete qualification.
The complete runtime remains pending. Earlier runtime `95094`
closed 1 / `00a07d` after 38 cases in three batches, Node2 and author31,
failing `popup.P01.default.native-key-popup-open`; eight later batches were
unreached. Preserve that failure. Full 65-case / 12-batch predicates,
expected negatives, original caller zero, unchanged inputs, natural closure
and independent readback remain mandatory.

The rich viewer is unfinished and production eligibility is false. The next
accepted retained base must demonstrate packaging-only web edits, small-module-only
C/C++/Rust rebuilds and responsive startup/interaction. Those everyday workflow
measurements remain pending. Incidental short maintenance and aggregate
qualification ceilings were superseded by operational watchdog authority;
machine protections and behavior-specific deadlines remain required.

## Current continuation handoff — 2026-10-18 UTC

The current checkout is `8cc8863f283f8b6972be6bbe383051419c7c6153`.
**The integrated rich HTML/JavaScript viewer is unfinished.** Both Backend copies
now include the inline definition header (`d14dab28…`); earlier P4 evidence retains
its original `4f72` source identity. Root and independent source review accepted
125 unique / 128 ordered ASTs and 95 source-only checks for the P5 controls.
Current preparation, the compile-free plan, five-unit native candidate, VFS,
168-artifact readback and capsule remain accepted for their original identities.
The latest reviewed runtime A01 passed 38 cases in three batches, then exposed
native dropdown label/projection defects. Central native repair and a distinct
selective producer lane are integrated with focused host checks passing. Fresh
native preparation and readback passed. After metadata binding repairs, a fresh
compile-free plan failed at the P5 product-index admission; its independently
reviewed newline correction now passes the real metadata interface. Route-v4
preparation and independent readback accepted that correction. Its compile-free
plan exceeded the unchanged 240+15s limit; explicit reviewed recovery closed the
parked outer caller with 137. The failed plan and immutable ledger remain retained. Standing user authority
permits repeated in-scope diagnostics, selective builds and acceptance runs without
cumulative time or attempt caps. Later authority below replaces incidental short
maintenance and aggregate qualification ceilings with operational watchdogs. Runtime,
neutral and Foundation gates remain open. Production eligibility is false.

<a id="new-main-chat-checkpoint"></a>

<a id="native-popup-capability-current"></a>

### Current runtime allowance and central dropdown repair

The historical A01 grant replaced the earlier one-additional-attempt restriction
with **five additional reviewed engine launches and 1,800 cumulative runtime
seconds**, across packet changes. Standing authority below supersedes those
cumulative and attempt limits. That historical grant used 360s whole, 330s activity and 180s aggregate
Worker. Later authority below permits revised aggregate operational watchdogs;
90s startup, 30s Node, 15s cleanup and postflight, 4GiB sampled RSS and
512MiB output remain required. Actual engine diagnostics count; inexpensive source checks do not.
Failures require preserved results, a discriminating diagnosis, justified repair,
review, fresh binding, technical grant and intent before another attempt.

Allowance attempt **A01**, original caller **9828**, closed **1 / `ca4650`** on
the reviewed `04aa4c7e…` packet. Positive13, editor16 and clipboard9 passed their
original full predicates: **38 cases / three batches**, including E8b and C10.
Popup-a failed at `popup.P00.default.native-control-unique`; eight later batches
were unreached. Node2 negatives passed. Independent closed-failure readback
0 / `2161ed` verified original predicates, 47 unchanged inputs, packet/grant and
closed owners, streams and watchdog. Result SHA-256 is
`6c9ed6bd9f54b701f1b4dd4189532bfea26c277d96598297bd880225cd7f1730`.
Driver elapsed was 92.037884498s; conservative original-caller charge is
**92.218s**. `ALLOWANCE-v3.json` recorded **four attempts / 1,707.782s remaining** before
standing authority superseded cumulative limits.
All earlier failures remain immutable; this is not complete runtime acceptance.

The native publication has two distinct integration defects. A password input
earlier in the document stops bounded explicit label association, leaving ordinary
later dropdowns unnamed. Separately, the retained forms producer makes an entire
select incomplete when an option is hidden. The user selected a **central native
capability repair**, preserving all 65 cases / 12 batches and meaningful original
predicates. Ordinary dropdown refusal, widget rewrites and unusual document
arrangements are not the intended successful outcome. The standing goal is ordinary
HTML/CSS/JavaScript compatibility with minimal porting, shared GUI behavior,
packaging-only web edits and small-module-only compiled application edits.

Strong design preserves password redaction and bounded first-ID semantics while
allowing private ID-only label association. CSS-only hidden single-select options
may stay publicly redacted while the control retains only popup/finish authority;
unsafe, unknown-style, author-omitted, inert and multi-select mutation paths remain
capability-free. Portable validation, GUI codec/chooser and diagnostic peer must
agree. WebCore rendering and popup row eligibility remain unchanged. The reviewed native and consumer sources are now integrated; focused
host behavior passed. The repaired engine has partial actual runtime evidence below; complete runtime acceptance remains open.

A vanilla Firefox comparison closed 0 / `c5f96a` in 2.604s without loading an
appended engine or Wasm. It confirmed ordinary label association and requested
styles. Every keyboard positive control was inert, so it supplies **zero keyboard
behavior evidence**. The pinned WebCore popup owner independently establishes the
port's intended hidden-row policy. No engine attempt was charged for this partial
comparison.

The reviewed source-only lossless report codec preserves every original byte,
assertion, trace and pixel. Accepted wiring retains the original 24MiB canonical
guard and 32MiB raw aggregate cap, checks complete raw hashes/count/aggregate
before inflation, and supplies only a trusted pinned decoder. Focused strong checks
0 / `be626f` passed ten boundary/admission probes, four exact-byte roundtrips and
the original 38 accepted-case predicates; the popup failure stays failed. The
three accepted reports shrink from 30,094,325 to 1,613,412 bytes. Complete 12-batch
fit and new source pins remain unverified/unbound. Standalone Luna test evidence
9 tests / 92 assertions and the original test failure, repair1 and validation
recoveries remain retained. The strong proof verifies all 47 inputs initially;
its final reread covers preparation files and the result, not a new 47-input
postflight. A01's independent closure supplies that separate postflight evidence.

Native v3 source map `969ca78d…` and the distinct P5-derived producer map
`bdfa2465…` passed independent source review and were integrated. Four producer
suites, six native host fixtures, 13 pure admission tests and 13 peer codec checks
passed. The actual GUI codec and forms tests also passed: 12 cases / 3,651 checks
and 59 cases / 6,019 assertions. Native completions in the forms tests are owned
mocks. The GUI fixtures now run in an ordinary native development tree using the
same production code, without selecting an appended profile or maintaining a
kernel. Original setup failures and source-review findings remain preserved.

The selective successor is **five fresh units / 46 imports / 168 artifacts**:
Publisher, NativeForms, portable Types, the generated-metadata shim and PopupOwner.
Imports retain 43 legacy compilation origins plus the three actual P5 Guard,
Backend and main origins. Both the historical composition lane and this native
lane have 5/46 counts; their memberships and kinds remain distinct. All 51
objects, five archive copies, zero repacks and one link remain required.

Active editor, physical and pixel source catalogs now describe their affected
native bodies with explicit successor records preserving complete predecessors;
historical capsule source maps, profiles and compile provenance stay unchanged.
Pure maintained-source admission passed for all three selections, with program
launch and tool discovery explicitly forbidden. Rich/native successor catalogs
were integrated and independently source reviewed. The eight registered source
suites initially passed seven; Windows replay failed one case and one fixture
setup, then the focused repair passed all 92 cases. The original failed aggregate
remains retained. New candidate admission now derives every P5 cache dependency
from all five original depfiles and requires cache, original SDK and current SDK
facts plus ancestor directories before complete 51-depfile acceptance.

The original S4 source proposal failed independent review on bounded metadata
reads, compiler cache ownership, circular descriptor binding and missing P5 cache
inputs. Its source, four findings and original deadline remain retained. Root's
strong successor repaired those seams. A fresh routed, unarmed control tree
replaces only 19 old-S4 path literals across eight of 23 copied control files;
independent source/physical review accepted it. The final 27-file physical map
is `ROUTED-FROZEN-CONTROL-SOURCES-v4.json` (`b2e6b4ec…`), including the
independently reviewed v3 cycle controller. Its preparation uncertainty channel
points to the actual retained-owner marker; plan/build also monitor the actual
producer uncertainty channels. Seven route checks exercised the descriptor's
real bounded Reader and the entry/binder paths. The independent inherited 18,
strong controls nine, budget 21 and v3 fake-owner/controller 15 checks passed.
Two route-test fixture errors remain recorded before correction. These are
source/interface checks; no engine or maintenance operation ran.

The user approved the cost-v7 selective cycle. Fresh descriptor and packet
creation passed, then preparation caller **51585 closed 0 / `e09093`** in
98.824456s. Source assembly contains 367 inputs / 369 files / 564,645,818 bytes;
the complete independent reuse copy contains 42,779 files / 861,802,853 bytes.
All three phase owners closed naturally, with no SDK program or compiler.
Independent Root readback **43633 closed 0 / `2fe7d4`** accepted the complete
source/metadata/copy namespaces and original caller, with unchanged inputs.

The next metadata binder **27035 closed 1 / `2fadb0`** before writing a plan
candidate: it copied a physical file fact where `validators.native_contracts`
requires the exact path/hash reference. Closure and input postflight passed;
no plan, compiler, link or engine runtime launched. The terminal failed ledger
is preserved. A preceding cheap interface check also found a legitimate empty
SDK cache header; its admission now requires the exact empty-content hash.
The reference projection repair `72e9999b…` passed independent source review.
Current-route fixtures passed eight executable interface checks and one source
assertion in three parallel groups. Original fixture failures and NC-R01's
original deadline / repair1 / Root takeover remain recorded.

The user subsequently authorized autonomous repeated focused diagnostics,
selective builds and acceptance runs within the agreed scope, without cumulative
time or attempt limits. All existing per-job timeouts, resource/performance
limits and correctness gates remain; failed results require a concrete cause,
discriminating probe or justified repair before repetition. SDK/kernel maintenance,
full engine rebuilds and Git publication remain restricted. The reviewed recovery
reuses accepted preparation. Its stricter **4,119.518s** inclusive job ceiling and
**132.312s** metadata ceiling remain for this job, after deducting the failed
cycle's 680.482s / 17.688s; these are no longer cumulative human allowances.
The current recovery permits one plan and one selective build;
local caps total 3,945s. Existing 240+15s plan, 3,300+30s build / 2,700s inner,
450s original total readback allowances (preparation already completed), jobs1,
4GiB RSS, 24 processes, 8GiB build output/disk growth, 16GiB launch headroom and
4GiB running free floor are preserved. The unarmed recovery controller binds
the original closed failure and accepted preparation; 34 parallel interface
checks and seven independent stage-shape checks passed. The original failed
ledger remains terminal; the fresh grant is `ab458502…`, sourced from
`authorized-execution-v1/HUMAN-AUTHORITY-v2.json`. Retained SDK `217e8ee7…`
remains read-only. No repaired candidate, capsule or runtime has run yet. The
previous four-attempt / 1,707.782s balance is historical; cumulative restrictions
are superseded, while all per-attempt limits remain unchanged.

A second binder failed before launch because the inherited freeze exceeded its
64MiB document bound. A reviewed projection retained every consumed predecessor
input, all 46 original depfiles and all 8,298 dependency paths; no document limit
was raised. Binder **31846 closed 0 / `daaef0`**, producing a 57,699,371-byte freeze
with 72,021 files / 5,946 directories. Independent review checked every identity.
The subsequent plan **70628 closed 1 / `b4af66`** naturally in 206.928s:
`Successful donor P5 product index differs`. No compiler, link or engine launched;
input postflight and closure passed. The helper omitted the original Root index's
terminal newline. Its correction `87dbd55e…` and regression `cfc05431…` passed
independent review, 87 donor / 80 maintenance tests, and the real pinned metadata
interface in 0.830s with program launches forbidden. Fresh route-v4 source controls
passed four interface checks in three concurrent groups. The original preparation
and failed outputs remain immutable. Route-v4 preparation26271 and independent
readback78654 accepted the corrected helper; binder45987 passed. Plan49830 then
timed out under the unchanged240+15s limit. Its inner owner cleaned up, but the
outer nested guard parked despite the eventual complete subtree exit. Reviewed
Root recovery captured the final supervisor report, stopped only the pinned
parked controller, and confirmed an empty namespace; original caller closed137 /
`ca251b`. Ledger state012 preserves failed status and closed=false because the
original controller did not publish its qualified closure. Recovery API fixtures
passed13 cases; all original fixture and preflight failures remain retained.
The later route-v5 plan83182 also failed at its original240s gate, but its
reviewed watchdog closed every owner and stream correctly. Producer exit0 and
plan verification succeeded; postflight reported the deadline. Fresh preparation
70505 and independent readback52105 accepted receipt`52a20231…`; reuse it without
another preparation. Its original failure and terminal ledger remain immutable.

The isolated phase diagnostic32467 closed0 on2026-10-19UTC in262.95s, with full
input checks, original plan predicates and natural closure. It is **diagnostic,
not an accepted plan**. Admission took4.93s, preflight52.74s, producer159.08s
(153.63s child CPU), verification1.33s and postflight42.44s. The two complete
72,036-file /6,333,024,204-byte guards took47.65s and42.27s. This establishes
slow completion and upstream CPU cost rather than a stalled postflight. Evidence:
`phase-baseline-diagnostic-v1/ROOT-CALLER-CLOSED-DIAGNOSTIC.json` (`f636ffc6…`).

The latest human direction supersedes the historical short maintenance and
aggregate qualification ceilings. Generous operational watchdogs are now being
bound consistently: plan900+30s, selective build7200+60s (inner6000s/jobs1),
cycle14400s and metadata600s. Resource protections, exact correctness, input
integrity, natural closure and independent readback remain required. Individual
behavior deadlines remain required. The unlaunched full guard timing comparison
was stopped; no full-inventory optimization speedup is claimed. Prioritize the
working retained base, then measure packaging-only web edits, small portable
module rebuilds, startup and interaction. No repaired candidate or complete
runtime is accepted.

The first generous-watchdog plan75861 closed1 naturally after234.740s. Its
producer and verification passed; the new cached guard rejected a version change
of the **unfrozen** `.agent-work` ancestor during a checked coordination mutex.
Root found no identity changes in any72,036 frozen files or5,946 directories.
Twenty-one differential fixtures, including the actual registry helper, reproduced
the false positive while retaining rejection of frozen-file, namespace and mode
mutations. The optimized guard is ineligible. Restore settled`2619961f…` logic
with only operational budget constants changed (`021d1bfa…`). All original full
hash, file/directory identity and complete input-namespace checks remain required.
Fresh route-v8 and `authorized-execution-v1/retained-base-cycle-v1` have independent
source/physical acceptance. Plan97781 closed0 / `943ea1` in248.033s with
natural closure and unchanged-input postflight. Independent Root readback64744
closed0 / `f96632`, accepting receipt `08fdb8ec…` and all72,036 file /5,946
directory identities. The pure projection preserves five compiles,46 imports,
five archive imports and one link. Build binder33042 closed0 / `93315e`;
Root physical review28949 closed0 / `415220` in11.455s, joining72,045 files /
5,948 directories and every predecessor fact. Its first review-only invocation
59698 exceeded the256MiB metadata reader cap because it unnecessarily loaded
both freezes together; the corrected comparison uses a separate bounded reader.
No build had launched during that setup failure.

Selective build1411 closed1 / `e9af8f` after1326.807s on packet `f3b65179…`.
Its producer and configure/build children exited0 naturally, all writers closed,
input postflight passed and peak outer sampled RSS was2,463,899,648 bytes.
The candidate verifier rejected an unused recipe-wide `cmakeconfig.h` binding.
All51 depfiles show21 such configuration omissions and no missing source or
unified-member reference. The earlier accepted Shim also omits this config;
the maintained producer explicitly distinguishes recipe inputs from a compiler
header census. Root's narrow correction `840ac7f3…` keeps the configuration's
frozen presence/hash, all source/unified/other dependency tokens and full51
ownership/VFS/cache checks. A diagnostic over all168 artifacts /51 depfiles /
2,734 cache files passed in41.46s. Independent strong source review accepted
this correction; Root's actual51 baseline and nine negative fixtures then passed
in117.024s, original caller23631 closed0 / `5ca173`. The original fixture
failures, repair1 and strong takeover remain recorded. Root source acceptance
is `83c929a7…`; this accepts the verifier correction, not a candidate. The original failed RESULT and terminal ledger stay immutable.
Fresh route-v9 full plan1827 closed0 / `769e7f` in275.933s; Root23831
accepted`e63958da…`. Its plan bytes remain SHA`fd3c9c0c…`. The following
pure projection failed at a missing output parent before any output; C2 stays
terminal failed. The parent is repaired; NC-R55 accepted the fresh four-step
continuation. Projection and build metadata passed; binder92244 and physical
review73849 closed0. Selective build83868 closed0 / `9e3256` in1,372.544s on packet`15fe7e4d…`,
with72,045 frozen files /5,948 directories and unchanged predecessor facts.
It reuses the accepted plan/readback and preparation under generous maintenance
watchdogs, jobs1 and all original machine protections.
Independent Root28478 closed0 / `323e7e` and accepted repaired candidate`79f94be9…`, including all168 artifacts/51 depfiles, unchanged inputs and natural closure. Preparation70505 remains reused. Failed75861 and its
terminal ledger remain immutable. The independently reviewed runtime source
cohort uses900/840/540s aggregate watchdogs and the original `8b0d27b3…`
helper. Capsule71796 closed0 and independent readback accepted16 distinct copies /163,589,359 bytes (`a0d299bf…`). Fresh runtimepacket`4685c592…` passed47-input physical/source review and real metadata admission; original56261 then closed1 / `244e2a` after1.103s at private-helper placement, before Node/browser/engine or any case. Exact helper relocation and real-loader checks are underway. The failed result remains immutable. Complete runtime acceptance remains open.
The subsequent exact-byte helper placement passed the real loader and all47
physical checks (Root `ec82167b…`). Original48330 then closed1 before
Firefox because the execution sandbox denied socket creation; Node2 and all47
unchanged inputs/closure passed. A discriminating socket probe reproduced that
restriction, and the tool-reviewed local-browser route admitted loopback sockets.
Fresh output-only packet`62390cc9…` ran as original95094, closing1 /
`00a07d` in93.482s. Positive13, editor16 and clipboard9 passed all
38 original predicates, including author31; Node2 passed. Dropdown P00 now passes
its own popup/selection/overlay checks, but P01 fails at
`popup.P01.default.native-key-popup-open`. Eight later batches were
unreached. Independent closed-failure readback`8ca559d5…` revalidated
all38, full47 physical inputs, reports and natural owner/stream/thread closure.
The case sends raw Space keydown only; WebCore's select menu opens Space in its
keypress branch, while the public raw-key path deliberately supplies no committed
text. A central control-default repair is under diagnosis; assertions and all65
cases/12 batches remain required. No new full retry is justified yet. Neutral28+6
and separate export remain blocked on complete runtime acceptance. All three new
failed outputs are immutable; the accepted native candidate/capsule are reused.



Exact evidence is in
`current_runtime/runtime-allowance-20261018-v1/native-cycle-supervisor-v1/`:
`authorized-execution-v1/FAILED-CYCLE-CLOSURE-v1.json`,
`route-v2/controls/preparation/execution-v1/ROOT-CALLER-CLOSED-ACCEPTED.json`,
`authorized-execution-v1/metadata-interface-fixtures-v1/result-v3.json` and
`authorized-execution-v1/recovery-proposal-v1/DISABLED-RECOVERY-SCOPE-COST-v2.json`
(`6600fb0f…`). The complete candidate/dependency/capsule and 65-case/12-batch
runtime acceptance gates are unchanged.

Current evidence is under `current_runtime/runtime-allowance-20261018-v1/`:
`AUTHORITY-v1.json`, `ALLOWANCE-v3.json`, `A01-ORIGINAL-CALLER-COMPLETION-v1.json`,
`A01-ROOT-CLOSED-FAILURE-READBACK-v1.json`,
`CODEC-PREPARATION-ACCEPTANCE-v1.json` and `VANILLA-CALLER-COMPLETION-v1.json`.
Native postimages are under `repair/native-popup-capability-preparation-v1/`;
producer postimages under `repair/native-capability-producer-preparation-v1/`.
The next acceptance sequence remains runtime → neutral28+6 → separate export →
Foundation → partial BOTH → remaining native/TUI/Rust implementation. Foundation's
900/1200/30/jobs2 limits remain proposals, not a grant. Production eligibility is
false; the integrated viewer remains unfinished. No retained SDK was modified.

<a id="trace-allocation-ready-additional-runtime-approval"></a>

The latest metadata adapter is v4 `99342306…`, independently accepted. It joins
strict three-field original producer records to nine-field physical closure and
copied-input facts, including exact original paths, and rejects excess, duplicate
or substituted reports before reading or inflating them. Two positive and 18
negative pure vectors passed 0 / `6d0674`. Codec sources and the earlier four
lossless roundtrips / 38-case predicate evidence are unchanged. Actual neutral
stage/export and complete 12-batch encoded fit remain unexecuted. Original stale
checker-pin and detached-manifest reporting errors remain retained; the corrected
source catalog excludes its own entry.


### Historical trace allocation repair — before the new allowance

This historical checkpoint preceded A01 and the new allowance above. Its original failures remain immutable:

| Original caller | Result and elapsed time | Accepted progress and failure |
| --- | --- | --- |
| 53325, exit 1 / `c8f614` | `58141554…`, 41.849226811s | Positive13/editor15 accepted; C02 rich-space expectation failed. |
| 39290, exit 1 / `5e3008` | `5f869c16…`, 86.257982148s | C02 passed; C08 small cut event-target expectation failed. |
| 92393, exit 1 / `9fb246` | `76118d2c…`, 101.806910276s | Positive13/editor15 accepted; clipboard nine cases through C08 completed; C10 hit the 16,000-row trace cap. |

The last attempt emitted no false clipboard assertion before the trace failure.
Nine later batches were unreached. Node's two negatives passed. Independent Root
readback 32667 / `73c9630` checked both accepted batches with original predicates,
all 47 input facts/control hashes and closed owners, streams and watchdog thread.
Peak sampled RSS/output were 3,258,871,808 / 239,638,064 bytes. This is closed
failure evidence, not clipboard-batch or overall runtime acceptance.

C02's strict rich expectation now preserves native U+00A0 interchange behavior;
plain expectations retain U+0020. C08 now observes the uniquely identified selected
carrier as the native cut target while retaining root beforeinput/input, deletion,
HTML digest and prior-clipboard predicates. Both repairs passed their actual
cases in 92393. No native source rebuild was needed.

The final trace repair preserves every case body, assertion and trace row. It moves
independent C04 after the original 15 editor cases, with an explicit closed
clipboard selector. Only all ten, C04 alone, or the remaining nine in original
order are admitted. Allocations 16 + 144 preserve the aggregate 160 clipboard
physical/document transaction ceiling; counted worst cases are 14 and 79.
Source checks admitted three groups, rejected 28 invalid selections including
sparse/inherited arrays, and enforced three budget boundaries. Initial selector
v1's sparse-array defect and test-generation failure are retained as failures.
Final source pins are Worker `c6a2c26d…` and clipboard `bf4baa3a…`.

The separate compact serializer (`4acd14b6…`) changes only future batch JSON
serialization. Its full reverse, 16 value/type vectors, three nonfinite refusals
and three closed-report round trips passed. Canonical guards, validators and all
limits remain exact. The worker's two handoff-writing failures and consumed
repair1 remain recorded; Root completed metadata by strong takeover before the
original 17:28:58.428927 UTC deadline. Final sources passed independent strong review.

Fresh `current_runtime/RUNTIME-PACKET-TRACE-ALLOCATION-v1.json` is
`04aa4c7ea99fe432a774b8954b0c01bf130089cc516df21f50410e091cbbc460`;
closure `211cf99e…` contains 47 inputs / 191,366,289 bytes / 20 roles. Relative to
C08, eight facts changed: Worker, clipboard and six coherent driver copies. The
other 39 facts/12 roles, all six fixtures, candidate/capsule, subject, 65 unique
cases, 12 batches and caps remain exact. Shape f6bacb and independent physical/hash
review passed. The fresh v5 output is absent; no grant or launch intent was issued.
Evidence is under `current_runtime/e8b-continuation-v1/trace-allocation-v1/`:
`BINDING-SHAPE-v1.json`, `INDEPENDENT-REVIEW-v1.json` and
`NEXT-RUNTIME-REQUEST-v2.json`.

**Next action:** obtain explicit authorization for one additional attempt of this
reviewed packet. Root incorrectly treated source repairs as allowing new attempts;
that did not extend the user's original maximum-one limit. The requested attempt
keeps 360s whole / 330s activity / 180s aggregate Worker / 90s startup / 30s Node /
15s cleanup and postflight / 4GiB sampled RSS / 512MiB output, with no automatic
retry. After approval, a new session must acquire scope and recheck the frozen
facts before issuing a fresh exact technical grant/intent. Original caller0, all
65 cases/12 complete predicates including negatives, Node negatives, natural
closure and independent unchanged-input/readback acceptance remain mandatory.

Neutral28+6 and separate export still require complete runtime acceptance.
The neutral execution copy must address its 64MiB link-map read bound for the
accepted 112,608,469-byte map without changing checksum/global budgets. Full
original-plus-derived report compliance with the unchanged 32MiB cap is unverified;
compact serialization alone proves no complete-report fit. Foundation's proposed
900/1200/30/jobs2 operation remains unissued, with concrete scope/cost and separate
authorization required. No neutral/export/Foundation or retained kernel/engine/SDK
operation ran. The viewer and remaining native/TUI/Rust work remain unfinished.

### Historical runtime53325 checkpoint — E8b passed, C02 source repair

This historical entry records runtime53325. The reviewed trace allocation entry
above supersedes its next-action statements; the C02 and C08 successors already
ran and failed. Do not replay their armed packets or outputs.
Fresh packet `47684624…` replaced only the accepted Worker/editor roles; all other
45 facts and 18 roles, the candidate/capsule, 65 cases, 12 batches and limits
remained exact. Root and independent strong review accepted all 47 physical/hash
facts; shape admission passed. Fresh grant `3f8fe934…` and launch intent
`3be80259…` bound the separate `runtime/actual-operation-v2` output.

Actual runtime **53325** closed **1** (`c8f614`) after **41.849226811 seconds**:
`C02-rich-native-text`. All 13 positive and 15 editor cases passed, including all
38 E8b assertions and actual signed `-1` for both malformed bodies. E6a remains
passed. Clipboard was the third, failed batch; nine later batches were unreached.
Node's two negatives passed. Independent Root readback **77909** closed zero
(`b2552e`), revalidated both accepted batches with the original predicates, all
47 input facts and packet/grant hashes, and two owner/two stream/watchdog closures.
Peak sampled RSS/output were 3,510,722,560 / 227,909,981 bytes, within the original
caps. Result `58141554e2c8b522395bdba118a75c0eaec74c963b5e3b57d03d4897a7ab2c84`
and `current_runtime/e8b-continuation-v1/ROOT-CLOSED-FAILURE-READBACK-v1.json`
retain the original failed attempt; it is not overall runtime acceptance.

Strong diagnosis found a fixture expectation mismatch with the existing native
clipboard contract. WebCore rich interchange converts the fixture's standalone
U+0020 text node to an Apple-converted-space U+00A0; paste removes the wrapper
while preserving its text. The observed rich value was `Bold🙂\u00a0italicé`;
the plain MIME value remained `Bold🙂 italicé`. The original serialized HTML
was not retained, so the intermediate wrapper is a source-derived explanation.
The frozen serializer/insertion source and original clipboard design require
preserving WebCore strings without normalization. No engine defect is established.

Root prepared `current_runtime/e8b-continuation-v1/clipboard_cases_native_interchange_v1.mjs`
(`de8791aa…`, 18,708 bytes): only C02's exact rich expectation and two explanatory
comments changed. Full reverse projection recovers all 18,552 original bytes;
the four ordinary-space plain/Shift-paste/DataTransfer expectations, every other
assertion, event/format check and case order remain exact. Source-chain pins and
syntax passed; this is source evidence. Fresh single-role packet `1a8acdf1…`
passed shape admission; its other 46 facts/19 roles and all caps remain exact.
Independent review, a separate exact grant/intent and actual runtime are still
required for that successor. No native compilation, capsule recopy, kernel/SDK
operation, neutral stage/export or Foundation operation ran. Do not replay either
old armed packet/output. Neutral28+6 and separate export still require a complete
runtime pass; Foundation limits remain unissued proposals. Production eligibility
is false and the integrated viewer remains unfinished.

### Verified continuation checkpoint — 2026-10-18

This checkpoint supersedes older uses of “current”, “running”, “unverified” and
“next” in the chronological evidence below. Keep those original observations and
receipts; use the latest applicable source/configuration identity for execution.
The objective remains working appended web and portable C/C++/Rust applications,
including the internal rich viewer and actual Foundation/module integration.
Malformed-input, failure-injection, Wasm, ownership and local-browser probes are
ordinary correctness tests of this project's own components.

**Checkout and transfer.** The observed branch is `main`, HEAD
`8cc8863f283f8b6972be6bbe383051419c7c6153`, parent `a3e31fd…`, subject
`WIP: continue appended application engine integration`. This commit appeared
outside this agent's operations. It contains the previous 40 modified files and
eight added files (the earlier five untracked entries included a directory).
The earlier `a3e31fd` / 40-dirty-plus-five-untracked snapshot is stale. Index and
worktree were clean before these handoff edits. This handoff changes only this
plan, the validation record and the pending record, plus ignored coordination
artifacts; it stages, commits, pushes and publishes nothing. Recheck live status
on resume. No remote fetch or server-state claim is implied.

Passive reconciliation rechecked all 12 native-source and 18 metadata physical/
byte facts, the three accepted diagnostic sources, and all 47 prior runtime input
facts without a mismatch. Source helper `401e88d0…`, both Backends `d14dab28…`,
source imports `1a83bda5…` and projection `3714fdd9…` also match current HEAD bytes.
The commit does not require another preparation, native build or capsule copy.
Older freeze files' source-only “unverified” status strings describe their own
observation time; later candidate receipts establish the subsequent static pass.
The passive state, exact historical argv and SDK identity are in
`root_evidence/HANDOFF-STATE-20261018-v1.json` (`b4132c92…`).

Use these navigation names; they do not launch anything:

```sh
cd /home/user/___quick/p/_cur/dataPump/_lessonsLearned/software-foundation
repo=$(pwd -P)
appended_evidence="$repo/.agent-work/appended-implementation-20261016"
appended_repair="$appended_evidence/runtime-D03-repair-v1"
current_candidate="$appended_repair/composition-inline-preparation-v1/selective/execution-v1"
current_runtime="$appended_repair/runtime-composition-repair-v1"
transport_probe="$appended_repair/runtime-editor-transport-probe-v1"
root_evidence="$appended_repair/runtime-recovery-v1"
neutral_source="$appended_repair/neutral-composition-repair-v1/final-v1"
foundation_proposal="$appended_repair/foundation-current-config-proposal-v1"
```

Do not confuse `current_runtime` with `H` in older records: that older alias means
another harness tree. Keep all ignored evidence and retained inputs. The paired
SDK is `/home/user/___quick/p/_cur/dataPump/_lessonsLearned/software-foundation/.agent-work/artifacts/gui-worker-v1/sdk`,
manifest `217e8ee79c8f825e52cf92338a841cd7c79836666aaee7cbd1f41ee9e070920a`.
The candidate private cache/configuration is under
`current_candidate/retained-editor-candidate-v1/private/`. The admitted baseline
is `appended_evidence/webkit-engine-probe/wrapper`; the successful donor descriptor
remains the original `747858f1…` under `composition-preparation-v1/preparation/`.
Do not walk the full SDK again solely because the chat changed. A source clone
without these ignored roots cannot resume this route. Moving them changes
physical identities: obtain new checked admission; never restamp old receipts or
fall back to a full supplier/kernel build.

#### Implemented behavior and actual evidence

Project selection, four-mode packaging/verification, the binary VM/service and
module-provider interfaces, C/C++/Rust guest bindings and retained payload tools
are implemented. Native journal, Guard, source-metadata and build-system repairs
are preserved in HEAD. Application behavior stays on the insulated side of the
GUI boundary; adapters implement generic capabilities. These facts do not prove
the integrated rich viewer, native/TUI behavior or the current Rust decoder runtime.

| State | Actual result | Authoritative evidence and reuse boundary |
| --- | --- | --- |
| Passed, focused source | 73 maintenance cases; separate 65 document/native/bootstrap cases, zero exclusions; 21 journal fixture checks with their original fake-step identity. | Helper `401e…`, tests `e765…`; source-suite receipt `952cf53e…`, final source acceptance `9e141ba8…`; named validation entries below. FakeStep coverage is not WebCore runtime coverage. |
| Passed, P5 preparation | 67862 closed 0/`803dde`; Root 6158 closed 0/`067f01`. 369 source, 12 metadata and 42,779 copied files; 363 inputs/eight controls unchanged. | `composition-inline-preparation-v1/preparation/execution-v1/ROOT-CALLER-CLOSED-ACCEPTED.json`, `c7ca7998…`. Source recipe `9bf770ed…`, source manifest `b9c04048…`, proof `13d551d5…`. Reuse directly. |
| Passed, compile-free plan | 70848 closed 0/`a805ee`; Root 77786 closed 0/`e088ca`. | `current_candidate/retained-plan-v1/plan.json`, `40af90e6…`; Root plan acceptance `4fa9b124…`. Planning alone is not compilation. |
| Passed, native/static candidate | 4865 closed 0/`59428c`; five compilations, 46 imports, five archive copies, zero repacks, one link, 2,060 opaque members unchanged. Root 11922 closed 0/`c0fda6` accepted exact 17 fields/all 168 artifacts. VFS/five-depfile 67340 closed 0/`b1b754`, 4,171 mappings and five actual fresh owners. | Result `f210dc0b…`; `current_candidate/ROOT-CANDIDATE-CALLER-CLOSED-ACCEPTED.json`, `b0454685…`; separate `composition-inline-preparation-v1/selective/ROOT-ACTUAL-VFS-FIVE-DEPFILE-GATE-v1.json`, `f0e4344c…`; combined Root `bc87b6a7…`. Current inputs still match. |
| Passed, capsule | 38638 closed 0/`e9ce28`; Root readback 0/`ee0415`; 16 independent copies/163,069,449 bytes and two external lineage records. | `current_runtime/ROOT-CAPSULE-COPY-ACCEPTANCE.json`, `bac68c23…`; producer `8e01f23e…`. Reuse the existing capsule; do not recopy it. |
| Failed, actual runtime | 33101 closed 1/`370bc5`, 36.78813448 s: `Actual provider dispatch count`. Positive 13 cases accepted; editor E1a through E8a, 14 cases, passed. E6a's 82 assertions include no committed preedit. E8b remained running; other ten batches unreached. Two Node negatives passed. | `current_runtime/runtime/actual-operation-v1/result.json`, `240b2de9…`; Root closed failure/coverage `root_evidence/ROOT-P5-RUNTIME-CALLER-CLOSED-FAILURE-v1.json`, `0a6d4bba…`. All owners/streams/thread closed and 47 inputs unchanged. Do not relabel it. |
| Passed, repair source only | Final runner 1329 closed 0/`32e90c`, 139 pure vectors. Root independently accepted source at 09:49:48 UTC, before original 09:59:44.106394 deadline. | `transport_probe/{SOURCE-FREEZE-v1.json,CHECKS-v1.json,HANDOFF-v1.md}`; Root `root_evidence/E8B-ROOT-INDEPENDENT-SOURCE-ACCEPTANCE-v1.json`, `df355cae…`. No execution of the repaired Worker/native engine occurred. |
| Unrun/incomplete | Fresh repaired runtime, neutral stage/export, actual Foundation, partial BOTH, native/TUI integration; current Rust decoder runtime and host tests. | Runtime packet/grant/output for the repair do not yet exist. Foundation proposal is disabled. Rust module `72e6b87b…` compiled, but matching host std was absent: zero host-test assertions executed. |
| Deferred | Full platform/backend, sanitizer, SDK-consumer, package/certification/release matrices and publication. | Applicable pending records; implementation/handoff is not authorization for extensive qualification. |

Native cancellation was repaired with the transaction-owned native inverse and
root selection. Its targeted E6a runtime observation passed; the entire editor
batch did not. Author callbacks may legitimately change markup, so do not infer a
blanket post-callback DOM-shape guarantee. The earlier 35714 failure
`E6a/no-committed-preedit` remains distinct from 33101's E8b failure.

#### Ready diagnostic repair, commands and preserved failures

Strong diagnosis established that the native copied dispatcher deep-validates
malformed editor bytes before host `begin_dispatch`. The failed observation did
not record its signed return; `-1` is a source-derived prediction, not an observed
runtime result. E8b had sent those bytes through a normal claimed endpoint whose
rejection is terminal. The repair adds a distinct direct negative diagnostic;
it leaves the normal endpoint, bridge, supervisor and production native code
unchanged. It supplies the full 1,048,680-byte reply reserve, authenticates the
full target/schema, accepts only actual signed `-1`, requires an unchanged output
canary, no callbacks/work/authority/inventory changes and exactly two native audit
boundary rows, and prohibits cleanup exports after uncertainty. Both original
mutations and subsequent native-state queries remain.

Accepted immutable source facts:

| File under transport_probe | SHA-256 / bytes |
| --- | --- |
| `worker_native_malformed_probe_v1.mjs` | `5768019f3db47288204c89958adcb32f34c40bffa8d25c2d7720ea5bc2ba8dca` / 57,203 |
| `editor_cases_native_malformed_v1.mjs` | `860c86bd5877f15edca621913dfbc41f66b8236d5d1c3ab0df09818218de9bce` / 33,474 |
| `test_native_malformed_probe.py` | `bdb8148603a106a8778944b91f838e2b1af7791c0d19aa50ffa1daa1046a7050` / 24,316 |

The exact authorized source command, already passed and reusable for these bytes,
was, from the absolute checkout:

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3.13 -B \
  .agent-work/appended-implementation-20261016/runtime-D03-repair-v1/runtime-recovery-v1/run_editor_transport_source_checks_v1.py
```

It checks syntax and extracts the actual context callsite, helper, witness,
dispatch and E8b body into a pure fake-module test. It does not import the whole
Worker, instantiate the engine, use an SDK or launch a browser. Session 51199
failed 1/`f06677` because the fake bump allocator did not grow; its failing sources
and log remain in `failed-check-v1/`. Session 11159 passed 0/`b0cf07`, then strong
review found its fake `terminal=false` hid the actual `terminal=null` shape. That
version is preserved in `reviewed-check-v2/`; final 1329 covers the corrected
shape. Assertions and mandatory runtime gates were not weakened.

Exact prior build/plan argv are preserved in
`current_candidate/ROOT-{PLAN,BUILD}-REVIEW.json` (`packet_projection.argv`), with
actual finite commands in `build-command-derivation-v1/EXPECTED_COMMANDS-v1.json`
and the candidate's `evidence/commands.json`. Exact runtime argv, environment and
pins are in `current_runtime/ROOT-RUNTIME-LAUNCH-INTENT-v1.json`, its caller log,
packet and authorization; the passive handoff-state JSON also indexes argv.
These are historical commands and immutable outputs, not instructions to rerun
an already armed operation. Preparation 1866/ENOSPC and its partial copy remain
ineligible. Preserve P2/P3 failed plans, P4 build 67381's undefined-inline failure,
all original trace/Guard/composition/runtime failures and their original sources.

#### Delegation and coordination at transfer

Keep the selected primary model and effort; do not infer them from child roles.
Re-read `/home/user/.codex/delegation-kit/policy.md` and its `agents/` role files.
The installed policy hash at verification was `44451350…`; roles remained
`luna_worker`/`luna_scout` = `gpt-6-luna`, high, and `sol_expert` = `gpt-6.1-sol`,
ultra. Configuration was not changed. Use the native role selector plus explicit
model/effort and `fork_turns=none` where needed. Workers do not delegate. Consider
Luna first for substantial bounded implementation with settled contracts,
ownership and supervisor-verified authorized checks; Root/Sol retains consequential
ambiguity, ownership, shared contracts and final integration. Avoid artificial
splitting. Strong takeovers stay strong-owned through their assignment completion.

- Independently accepted Luna work: the pure VFS predicate `93529f3d…` passed Root's
  95 synthetic checks and actual 67340 VFS/five-depfile gate; P5 evidence-doc patch
  `528daca2…` passed independent Root review `73a698a2…` and guarded integration.
- P5 controls assignment `luna-inline-controls-20261018-v1` required Sol takeover
  after its generator failure and substantive binding omissions. Original patch,
  failures, repair allowance and 08:13:31.405922 deadline remain; strong completion
  preceded that deadline. Do not report those controls as an accepted Luna patch.
- Earlier `luna-doc-reconcile-20261018-v1` was also completed by Root takeover;
  preserve its closed record and original repair history. The separate accepted
  P5 documentation assignment retained its own 08:53:14.319406 deadline/repair0.
  Its original slow checker exited 130 without acceptance. Root recorded same-
  assignment validation blocked/ready recovery and fixed checker setup; the
  candidate did not change and its repair/deadline was not reset.
- `luna-editor-transport-probe-20261018-v1` stopped incomplete after two direct
  Node syntax commands outside its sole authorized runner. Their reported zeros
  are not acceptance. Original candidates `da6a8a6c…`/`cdb21930…`, diffs and reports
  remain under `root_evidence/E8B-LUNA-ORIGINAL-v1/`. Sol took over the same
  assignment, repaired wiring/capacity/ownership/audit handling, and completed the
  final 139 vectors and Root review. Original deadline 09:59:44.106394 UTC and
  repair0 are preserved. The completed assignment must not be returned to Luna.
  A genuinely separate downstream binding task can be considered anew.

The complete-record board is the absolute checkout's `.agent-work`; there is no
`state.json` migration or second registry to create. Use checked session/review/
publish/edit helpers and the current recipes. The final Root and Sol records carry
explicit releases. Sol's terminal record is `20081289…`, release
`sol-editor-transport-probe-takeover-20261018-v1-final`. Root never acquired this
released probe scope and did not bind a new runtime. Its own final record releases
all held input/output/doc/workload claims after handoff saves finish. No actual
job remains; 33101 and all three source-check attempts are closed. Old “51199
live” checkpoint prose is stale and superseded by final evidence. Read the final
records/inboxes and acquire with a **new** session ID; never resume a closed ID or
infer ownership from a timestamp/PID. The unrelated malformed Gentoo handoff row
is retained and manually reviewed as released/unrelated, not silently repaired.

Root source acceptance preceded the deadline; administrative releases occurred
later during this handoff. Snapshot/clock observations do not change the original
assignment budget. `.agent-work` and SDK contents remain essential even though
Git ignores them. A new checkout/machine needs these inputs, the external policy,
matched tools and new physical admission. No unresolved source decision currently
blocks the next fresh runtime binding; tools/permissions must still be checked.

#### Dependency-ordered execution for the next main chat

1. **Ready and already authorized: fresh metadata binding.** Inspect current
   instructions, HEAD/diff, complete claims/releases/inbox and input facts. Acquire
   the released probe inputs, current runtime output/control scope and the shared
   workload resource as required. Bind a new packet from the accepted 33101 packet,
   replacing only the `worker` and `editor_cases` role paths/records with the two
   accepted files above, recomputing the complete 47-input closure and choosing a
   fresh absent output. The other 45 input facts, 18 source roles, accepted
   candidate/capsule, fixtures/tools, 65 cases/12 batches and caps must remain exact.
   Recommended unused names at inspection: `current_runtime/RUNTIME-PACKET-E8B-v1.json`,
   `ROOT-AUTHORIZATION-E8B-v1.json`, `runtime/actual-operation-v2`. Recheck absence.
   Do not rewrite the old packet/grant or consume any failed partial build/copy.
   Run the driver with `--packet NEW --packet-sha256 EXACT` **without** `--execute`
   for compile-free shape admission. Review all 47 hashes/physical facts, subject,
   route and source changes; then create the exact new technical grant and launch
   intent. Do not build, link, recopy the capsule or rerun the pure139 merely to bind.
2. **Ready after that review, existing bounded authority: one actual runtime.**
   Use the same absolute checkout, `/usr/bin/python3.13 -B`, current driver,
   newly pinned packet/grant and the already admitted local Firefox/Node route.
   The existing “Run the bounded engine probe” authority covers necessary focused
   repairs and a fresh reviewed operation, not unchanged retries. Limits remain
   360s whole, 330 activity, 15 cleanup, 15 postflight, 180 aggregate Worker,
   90 startup, 30 Node, 4GiB sampled RSS, 512MiB output, maximum one attempt.
   No SDK/compiler/kernel/engine production is part of this operation. Record
   launch intent, actual yielded handle and final original caller exit. Require
   integer caller0, report passed=true/no failure, all 12 ordered batches and all
   65 selected cases, Node's two negatives, natural owner/stream/thread closure,
   complete unchanged-input postflight and Root independent readback. Reuse the
   unchanged supervisor's terminal and genuine-Worker-failure validators for
   expected-negative cases; do not replace them with ordinary success predicates.
   A failure
   remains failed: preserve full observations, isolate its cause with cheap
   discriminating probes, repair within authority, then review a fresh scope.
3. **Technical prerequisite: neutral staging and export.** Only a complete runtime
   pass permits a new execution copy of `neutral_source`. Root must create the
   independently checked runtime receipt and exact seven-field
   `root-closed-neutral-runtime-v1` closure required by `issuer/neutral_group/adapter.py`:
   kind, result_sha256, caller_observed_exit, writers_closed, inputs_unchanged,
   subject, original_reports. Keep detailed caller/47-input/readback evidence in
   a separate Root record; do not add fields to that strict schema. Bind original
   batch reports plus browser/driver, commands/link map, all five compiled object
   facts, three import-receipt/retained-depfile provenance pairs and six adapter
   source records. The seven actual bindings are still None. Backend/main pins
   are unset; Worker/editor pins still describe old bytes. Fill them from accepted
   current evidence, never guesses; rebind the changed pins.py record. The old
   14-check receipt proves only the released disabled source. Review/check the
   fresh binding separately, retaining unchanged algorithms and predicates.
   Existing limits: 300s, 32GiB logical reads, 2GiB output, at most 128 reports/
   32MiB aggregate and 12 batches. Require actual 28 requirements plus six
   bootstrap/START predicates, natural closure and independent readback, then a
   **separate export grant** and actual strict-consumer acceptance. Derive all four
   recipe/manifest/proof/runtime pins from accepted products. No production claim yet.
4. **Additional expensive work requires its concrete authorization: Foundation.**
   After runtime and neutral acceptance, reconcile the disabled Foundation884
   proposal with the current top-level CMake pin and admitted SDK/source projection.
   It proposes 36 TUs (22 C++, 14 C), 18 archives and 73 recorder captures, no engine
   rebuild. The proposed 900s configure /1200s build /30s cleanup /jobs2 ceilings
   are not an issued grant. Prepare the exact scope, cost, inputs and packet before
   requesting genuinely additional expensive work. No Foundation copy/configure/
   capture/build was launched. Reuse unchanged retained TU bodies, archives,
   generated inputs and metadata; do not recopy the source tree for unrelated docs.
5. **Prerequisites then remaining implementation:** construct and qualify the
   actual selected Foundation profile/DESCRIBE, run the retained partial BOTH
   scenario with C guest `f608dce3…` and one EngineOwner/module/presenter loop,
   then finish outstanding native/TUI and application behavior through generic
   contracts. The pure partial-BOTH fixtures and old C compile are reusable for
   their own identities, not actual integration. Execute the current Rust decoder
   and applicable tests once its retained runtime/host prerequisites exist; the
   current Rust compile alone is insufficient. Cold native/dependency/SDK production
   outside the bounded retained route needs a concrete additional cost/authorization.
6. **Optional/deferred qualification:** perform applicable complete platform,
   portability, SDK-consumer, package, browser-policy, certification and release
   workflows only under their manual authorization trigger. Do not stage/push/
   publish, dispatch Actions or change SDK/delegation configuration from this handoff.

The next main chat should execute ready authorized work through these acceptance
observations, then continue the dependency chain. A plan, source patch, successful
compile, partial batch or offer to continue does not complete the software goal.
A working result means actual application behavior in the selected modes,
compatible retained kernels/SDK consumers, demonstrable rich web/native service
and GUI/TUI behavior, portable guest execution, and payload-only iteration that
performs zero retained-kernel/engine rebuilds. Preserve the detailed acceptance
requirements below and the explicit limitations of each retained result.

### Earlier continuation evidence

The following chronological records preserve each original source and outcome.
The verified checkpoint above controls the next action.

### Fresh preparation recovery — 2026-10-18 UTC

The continuation found a clean checkout at
`a3e31fdff294bf755bcded9b8b4df8577c3113e5`, one documentation/policy handoff commit
after `30a6221e`. No implementation-source delta was introduced by that commit.
All 250 original frozen preparation inputs still matched their hashes and
physical identities. The complete 196-record board had no claims; a new checked
session acquired only the fresh output, with independent helpers read-only.
Host-visible process inspection found no retained preparation/compiler job.
Current Btrfs data/metadata allocation, reserve and free-space observations
supported the bounded copy. Detailed device ioctls remained unavailable, and the
original ENOSPC cause remains unknown. No cleanup or retained-SDK mutation occurred.

The fresh scope is
`base/runtime-D03-repair-v1/provider/selective-continuation-v1/preparation-recovery-v1/`;
its immutable final controls and actual products are in `execution-v1/`.
The original failed `prep` and its partial copy were neither resumed nor consumed.
A guarded editor refused replacing artifact controls before mutation; disabled
controls were preserved, and final controls were exclusively created in the new
execution namespace. Independent review confirmed unchanged executable definitions,
unchanged caps/history/donor, 248 identical frozen rows and exactly two local
control substitutions. No admission semantics or resource limit was relaxed.

Actual preparation session **1570** closed with original caller exit zero,
completion chunk `828423`, in **118.457506299 seconds**. Source, metadata and copy
all closed naturally with zero exit. Independent Root readback session **53212**
closed zero, chunk `a19e8f`, in 49.536 seconds: 368 source files / 564,540,041 bytes,
12 metadata files / 106,264,070 bytes and all 42,779 copied files / 861,802,853 bytes
passed complete namespace, mode, hash and physical-identity checks. All 250 frozen
inputs and five final control/packet files remained unchanged. The retained source
recipe/source/projection pins remain `a2df92fd…`, `64aa9022…`, `6fef5ea2…`;
actual reuse proof is
`6039e0aaf2d0f268b25ff2ef32301de0095c17b215662144e863fb5709d92c32`.

The original fresh result is `execution-v1/actual-v1/RESULT.json`, SHA-256
`39c5b2a380cf6f2468bc4e63ff83eee57708f253d0df16723c7c80deebf0fd4b`.
Closed Root acceptance is `execution-v1/ROOT-CALLER-CLOSED-ACCEPTED.json`, SHA-256
`f4377906f8ec75414591bd68f25474ec0f9e809964fa8cc7dfe86acc482ec33a`.
The fresh packet is `28e18e204f4612dce3ce66419e73b131b802f3471730116ac85d3bc6bbe50c80`.
Original caller/launch/readback records are retained beside `execution-v1`.
All preparation writers released their scope after closure; the products remain
immutable. This is preparation acceptance, with no completed engine imports,
compiler, linker, SDK program, browser or runtime execution and no production
eligibility. [The validation record](appended-validation.md#fresh-d03-preparation-recovery)
retains its exact scope.

### Fresh selective candidate and closed runtime failure — 2026-10-18 UTC

Fresh selective work is under
`repair/provider/selective-continuation-v1/concrete-recovery-v1/` (`D` below), with
its concrete execution files in `D/execution-v1/` (`E`). The original disabled
controls and all old preparation/candidate receipts remain immutable. Only fresh
paths, actual proof/physical facts and reviewed literal gates/pins were bound;
producer algorithms, SDK admission, donor and resource limits were unchanged.

Compile-free plan **17883** closed zero (`d556cc`). Independent Root **76598**
closed zero (`af0a3b`), rechecking 68,340 file and 3,797 directory identities and
27 source hashes. Plan `E/retained-plan-v1/plan.json` is
`4f19b383f6f828160f1400b87923b960687e52a3787782127a146f500153d7a0`;
Root plan acceptance is
`f8538b7a8f7c85d287d7ffd4e51a9a880fd1a5359e5c1b885e9e8ad4effe0bf8`.
The finite command derivation admitted exactly two fresh units, 49 object imports,
five archive copies, zero repacks and one link. Its five-role command ledger is
`c37dd3a7ddf4d6a4cb6df585a5ae2fdefd818addae565a19522548e9d975adf8`.

Actual candidate **94609** closed zero (`57b809`), with natural qualified closure,
51 objects, five archive reports and 2,060 unchanged opaque members. The original
3300-second work / 30-second cleanup / 2700-second inner / jobs-one, 4-GiB RSS and
8-GiB output/growth limits held; observed peak aggregate RSS was 2,428,121,088 bytes.
Only Publisher and document shim compiled. Independent Root **32461** closed zero
(`3ee810`): exact 17-field acceptance, all 171 artifact full hashes/physical
identities, 68,348 file and 3,799 directory input identities, 28 source hashes,
exact ordered accounting/commands and complete lineage passed. Key records:

| Record relative to E | SHA-256 |
| --- | --- |
| `actual-candidate-v1/RESULT.json` | `306c83168af9280bf1aa14c999d0901983f043dad0a636339d4aa3840b6111cd` |
| `retained-editor-candidate-v1/maintenance-build.json` | `25036087459756741159848f868682d1eb0db981d84960474626ebf51d48c02c` |
| `ROOT-CANDIDATE-CALLER-CLOSED-ACCEPTED.json` | `4d0ccd2fde7921becb4d132a162c32c3dd7184364ff90eb791b376841a454663` |

The resulting factory is `4685254b…`; Wasm is
`68193e59db6eb86af2a66dd615b73409677201348b9f67cb326eeb39e8f0cf36`,
109,675,840 bytes. This candidate contains current Publisher `0705d942…`.
Production eligibility remains false. The accepted output scope was released
with all writers/streams closed; preserve its inputs and artifacts for reuse.

Runtime recovery is `repair/runtime-recovery-v1/` (`R`). Qualified metadata-only
copy **3086** closed zero (`2a9b4b`) in 1.735 seconds. Independent Root readback
closed zero (`1a53d6`): 14 originals plus two derived files, 16 distinct read-only
copies / 164,728,184 bytes, exact complete namespace and full facts passed.
Commands/donor remain two external lineage records. Producer result is
`c9715acdd08ba009b5ede5ef17c7c05d28718021a6ff4478806dc65631a90136`;
`R/ROOT-CAPSULE-COPY-ACCEPTANCE.json` is
`8f76d89fd036d5a9a49f436d3c9c73ed7224d573490304726f2a039791a93d86`.
No SDK/compiler/engine ran during this copy.

Fresh runtime packet `5b945067…`, authorization `0fa0da31…` and output were
independently reviewed: all 47 input physical facts, unchanged 20 source roles,
fixtures/tools, 65 cases / 12 batches, expectations and original caps. Shape
admission passed (`dccf44`). Actual approved Firefox/Node loopback attempt
**86329** closed **one** (`04b4a7`) after **20.161931327 seconds**:
`Bounded Worker trace`, zero accepted batches. Original saved result is
`R/runtime/actual-operation-v1/result.json`, SHA-256
`88696cb47a622f054a958d90020037c99bebd5ef81b0bbe7e905920ef6151299`;
positive observation is `b2c543fabaa495f3ef1595aae63d7aa5b31d032a82eab52d4aab0f55ef92381a`.
Both Node negative controls passed. All inputs were unchanged, owners/logs and
watchdog thread closed, guard failure was absent; sampled RSS 3,695,534,080 bytes
and output 220,598,251 bytes stayed below 4 GiB / 512 MiB.

The failed positive observation contains 13 mandatory, 31 author and 442 emitted
case-assertion rows, all true. D01 (51), D03 (85), D04 (87) and I01 (108) completed;
I02 emitted 111 rows but remained running when the trace bound stopped it. Eight
later positive cases and the other eleven batches have no observations. Its
12,815 trace rows and partial request counts are retained, not a browser pass;
top-level zero request totals mean no batch was accepted, not no native activity.
`R/ROOT-RUNTIME-CALLER-CLOSED-FAILURE.json` and
`R/ROOT-RUNTIME-FAILURE-COVERAGE-READBACK.json` preserve the external caller and
coverage. Original failed runtime 41837 remains unchanged.

### Trace repair and current I04 failure — 2026-10-18 UTC

The first trace failure was its byte ceiling: 12,815 rows consumed 8,388,586 of
8,388,608 compact-accounted bytes; the consumer's canonical representation was
already 9,856,114 bytes. Redundant outer peer request/reply copies dominated,
including pinned resource hex. A new immutable Worker in
`repair/runtime-trace-projection-v1/worker_probe_trace_projection_v1.mjs`, SHA-256
`a8d498f550735f1130d1e2649e6ba0755b1185b945166cc888a4282a59b1be25`, omits only
outer non-SUBMIT transport duplicates. All semantic peer events, raw SUBMIT pairs,
actual export/dispatch/callback/owned-result rows and every notification remain.
Peer behavior/internal transcript, case expectations and all caps are unchanged.
Byte accounting now includes canonical ASCII/indentation/list overhead; finite
floating tokens reserve a conservative 24 bytes. It never relaxes 8 MiB / 16,000.

Focused pure metadata checks passed 2,073 vectors, exact byte/row acceptance and
next-append rejection, Unicode/numeric edges, notifications, whole-Worker syntax
only, reverse projection and complete saved-trace projection. The known prefix
became 7,167 rows / 2,895,208 canonical bytes with all four actual event families
unchanged. Test/source/patch and exact limits are in that directory's `CHECKS.json`
(`f8e06ad1…`) and `HANDOFF.md`. No engine or Worker was executed by those checks.
Root reviewed the full diff/test and searched the exact 20 source-role files for
consumers; supervisor request/order guards remain strict.

Fresh packet `b1ad26aa…` and authorization `688e8d49…` change only the Worker role
and physical/hash row, recomputed 47-input closure and fresh output. The accepted
candidate and 16-file capsule were reused without build or copy. All other 19
source roles, fixtures/tools, 65 cases / 12 batches and caps were unchanged.
A mistyped pin failed shape-only admission before execution; corrected admission
passed (`92171b`). A later checkpoint-argument error refused publication; Root
recorded the orchestration error, rechecked the unchanged valid ownership and
saved the original actual handle. Neither error launched a second runtime.

Actual approved attempt **97809** closed **one** (`7a7579`) in **21.802950001 s**.
It passed the earlier trace point, then failed
`I04/after-lifecycle-old-C8/actual-native-STALE-before-TURN`.
`R/runtime/actual-operation-v2/result.json` is
`713b238a6cb3df86c67d6b841be2a1b1b9c339897872d6f209bbffe5cee01986`;
raw positive observation is
`687fc00988990416aebb0bcddf605c3a6e3aa7cf172b806229f2d6a25357babc`,
7,525,122 bytes. Trace is 10,160 rows / 3,980,076 canonical bytes, below unchanged
limits. Node negative controls passed; inputs, owners/logs and watchdog postflight
closed unchanged, guard failure absent. Sampled peaks were 3,472,936,960 bytes RSS
and 207,207,488 bytes output, below 4 GiB / 512 MiB.

There are zero accepted browser batches. D01/D03/D04/I01/I02 completed in the
failed positive observation; I04 failed. It records 13 mandatory and 31 author
assertions true, plus 607 emitted case rows with one failed assertion. Seven later
positive cases and the other eleven batches remain unobserved. Partial request
counts are 71 ordinary, two metadata replays, 2,082 exports and 415 dispatches;
zero aggregate totals do not mean no native activity. External caller, exact
coverage and all 47 physical input rechecks are retained in
`R/ROOT-RUNTIME-TRACE-v2-CALLER-CLOSED-FAILURE.json`. Never resume the failed Worker.

**Next:** repair the Worker fixture-intent trace serial field, then repeat the
unchanged runtime with a fresh packet/grant/output and Worker. The current Guard
candidate and capsule are accepted and unchanged; reuse them without rebuilding
or recopying. Preserve all assertions/cases and caps and all failed outputs.
Neutral admission, Foundation construction, partial BOTH and native/TUI/application
integration remain runtime dependent and unrun.


### I04 guard repair and focused host checks — 2026-10-18 UTC

I04's old C8 capture returned STALE only after host TURN entry. The three active
Guard sources now preflight C8's already-owned inert admission metadata before
TURN, while retaining the original in-TURN admission for host-entry races. The
Gate, sequence/form barriers, copied payload, current-document check, exception
poisoning and historical revoke9 route remain enforced. No public ABI changed.
Canonical/native Guard is `3aebfcc5b4e838846f23a5c9c61a62acc51fecc73541fd58deaa9c157308b0ff`;
editor-overlay Guard is `6ec6546880d6736311ab8def5563da79a870dd1f68b56fdcbe947835acf817a8`.

The ordinary native profile now exposes these inert fixtures through the supported
`build.sh test` entry. Its three value/codecs leaves and provider/actions targets
are excluded from the default build; the configured `all` target still contains
only core and CLI. No kernel, VM, retained SDK or supplier engine target was
configured or compiled. The C11 fixture remains on profiles that enable C.

Initial setup attempts executed zero assertions: profile-none omitted the fixture,
and selecting binary was refused by its kernel-maintenance prerequisite. After
fixing the test graph, runs 90088 and 50694 executed 82 cases with respectively two
and one failed old count assertions. The historical fake keeps native metadata
valid across document navigation, so its C8 still reaches the original in-TURN
document check; only its extra inert admission count changes. Those failures and
all original assertions remain preserved in the evidence. Final **22409** closed
zero (`d1b95a`) in **6.212878763 seconds**: **82/82 editor Guard cases passed, zero
skips**, including stale rejection without TURN/effects/sequence consumption,
same-identity metadata invalidation on entry, both exception boundaries, copied
payload/reentry and historical revoke9 coverage. Independent dependency/source
readback passed (`ea58ef`). Full commands and frozen hashes are in
`R/host-check-v3/PLAN.json` (`f53a9242…`); closed caller is `b3144e7c…` and dependency
readback `2e2dff0f…`.

Candidate 94609 predates this Guard repair. It remains accepted only for its
original source identity; **the new Guard has no current-source Wasm build or
runtime evidence**. Source metadata and the explicit selective successor are
implemented; their focused evidence and fresh preparation failure follow below.
A new accepted recipe/manifest/projection/proof and independent output scope are
still required; never rebind old receipts or consume failed1866's partial copy.

Source metadata now marks the Guard as a source-only successor while retaining
historical document compile-map/profile bytes and native predecessor lineage.
Final pure checks passed 45 document-source, four native-source, eight helper
selection and ten compiler-free CMake recorder cases, with zero skips. Earlier
fixture setup/count failures are preserved; the recorder now includes its full
fragment closure, standard full install paths and both pixel/actions inventories.
The host 82-case result remains applicable to unchanged Guard source.

The maintained producer now has explicit `successful-donor-guard-repair` descriptor,
plan and build kinds, selected with `--successful-donor-guard-repair` alongside the
pinned successful donor. Its 58 donor and 49 maintenance cases passed. The old
49-import / two-fresh / 171-artifact lane remains strict. The new lane requires
48 imports, Publisher + shim + Guard fresh, five archive copies, zero repacks,
one link and 170 artifacts. Fresh private capsule/runtime readers have matching
Root/configuration/summary kinds and a distinct pinned helper role; 40 tiny inert
cases passed, including both crossed-summary rejections. Their v1 summary-tag
mismatch was caught before use and preserved. No padded descriptor test, SDK
program, current-Guard Wasm compile or runtime was executed by these checks.

Fresh preparation **6762** used a new reviewed 255-input packet and closed one
(`848537`) in **31.279604267 s**. Source assembly (368 files / 564,545,824 bytes)
and metadata (12 files / 106,263,977 bytes) closed naturally with zero exit.
Copy refused the new packet kind before writing any copied data: its successor
materializer still contained the predecessor's exact kind comparison. This was
a missed contract refresh, not ENOSPC. No copy directory/receipt or overall Root
acceptance exists. All 255 input hashes/physical facts were unchanged and all
writers closed; preserve this failed scope without rerunning its armed entry.
Original result is
`repair/preparation-guard-repair-v1/execution-v1/actual-v1/RESULT.json`, SHA-256
`3a1379f6f38bafe198e696c6d73d24c277af22c8138c0b38837f36801c1791c5`.
Its `ROOT-CALLER-CLOSED-FAILURE.json` records the independent postflight. A separate
v2 scope corrects the exact kind gate and must pass fresh bounded preparation,
Root full readback and compile-free plan before compilation. Existing user
authority covers this necessary focused repair under unchanged caps; no human
two-unit restriction was recorded. Root still reviews/binds each concrete launch.




### I04 fresh preparation accepted — 2026-10-18 UTC

The separate v2 preparation corrects only the copy materializer's exact packet-kind
comparison, with fresh control/output paths. Root reviewed all 255 input hashes and
physical identities, the control projections and current storage (38,436,728,832
bytes available); the original ENOSPC cause remains unknown. Failed 6762 and 1866
remain immutable and neither partial output was consumed.

Actual **85828** closed zero (`edcb3a`) in **92.657658530 seconds**. Source, metadata
and copy all closed naturally with zero exit, one reaped child each and no outliving
writers. Independent Root **88406** closed zero (`d3ac48`) in **10.472246394 seconds**:
368 source files / 564,545,824 bytes, 12 metadata files / 106,263,977 bytes and all
42,779 copied files / 861,802,853 bytes passed complete namespace, mode, hash and
physical-identity readback. All 255 frozen inputs and six execution controls stayed
unchanged. No SDK program, compiler, linker or runtime ran.

Evidence is under `repair/preparation-guard-repair-v2/execution-v1/`:

| Receipt | SHA-256 |
| --- | --- |
| `actual-v1/RESULT.json` | `0a0029c90e79a8f031c6bdbaa65e56e2e94a7a82e111ca0f4256d040a508e9a8` |
| `ROOT-CALLER-CLOSED-ACCEPTED.json` | `81ff3d1cc900471792dcb49b737bb757e83332477236d0412f0ce24a0d30c1e0` |
| `REUSE-COPY-RESULT.json` | `9dfcb3c50762b032bf94ed2448a676d57b0bfe467bc0075c7d31cd99aa0d06b8` |

Recipe/source pins are `8f3f9ac8…` / `faaf4eb3…`, projection `233b7879…` and complete
reuse proof `eaa0e586198949adf352e60f724fb35d168c78d5d9d2ec31b8067d89585a6864`.
These matching source/metadata bytes have fresh accepted physical/output identities;
the failed v1 receipts remain failed. Next is the compile-free 48-import / three-fresh
plan, then the bounded candidate and unchanged 65-case / 12-batch runtime. The new
Guard still has no current-source Wasm/runtime evidence.

### I04 selective plan accepted; candidate build pending

The compile-free Guard successor plan **19842** closed zero (`201719`), with
48 imported objects, three fresh direct units, five archive copies, zero repacks
and one planned link. All 51 selected objects, 35 direct objects, 16 inherited
replacements and 2,060 opaque members remained fixed. The qualified child closed
naturally (one reaped child, no termination or outliving descendants), input
postflight passed and peak aggregate RSS was 460,173,312 bytes.

Independent Root **56691** closed zero (`71838f`), rechecking 68,344 file and 3,797
directory identities, the complete plan namespace and canonical source hashes.
The original SDK admission97501 and SDK freeze70a212 retain their original identities;
no second SDK census or SDK program ran. Evidence is in
`repair/concrete-guard-repair-v1/execution-v1/`:

| Receipt | SHA-256 |
| --- | --- |
| `retained-plan-v1/plan.json` (38,289,292 bytes) | `339986220c9d798710bffbebfc7c74b3b6cd1feef5eefd8306471f3b01a2c9c9` |
| `actual-plan-v1/RESULT.json` | `bcbd3d543e500ba87cc8a15526a7ccc47b700492d407148c8093759bba3a6902` |
| `ROOT-PLAN-CALLER-CLOSED-ACCEPTED.json` | `5a748e9ca2d152a5524a78eb7743e407bda591617397f9456f9bea3047f35a60` |

Pure command derivation passed (`421354`), including exact three-unit vectors,
48 imports, five archive copies and lossless expansion of all 2,076 archive members.
Commands are `de9d86015b91b0714b0642c4ea8dec810493d99adc6c53f8d0c86892a06ce673`.
The first projection attempt (`2b9561`) failed before any output because Root had
omitted its empty metadata output directory; the preserved v2 changes only that
evidence path and creates its new parent. It invokes no SDK program.

Build binding **11725** closed zero (`bee087`); Root independently rechecked its
68,352 files / 3,799 directories and unchanged source hashes. The exact eight
file/two directory additions bind the accepted plan, closed log and command ledger.
Current storage was 37,624,377,344 bytes available. Candidate **17972** was launched
once with packet `952caf046dd45513534a2fa4c2bc35fd2f5d8884d027c21cb7c776053dd1c2ee`,
one job, 2,700-second inner / 3,300-second outer work / 30-second cleanup limits,
4-GiB RSS and 8-GiB output/growth caps. **It is not yet a passed build.** No new
current-Guard runtime or neutral admission is established.

Disabled capsule/runtime successor controls passed independent source review,
including the corrected supervisor-relative helper paths. The neutral successor
passed 21 tiny inert checks and independent review while preserving the exact
28+6 evaluator, limits and true-runtime/zero-caller prerequisites. These source
checks launch no capsule, browser, neutral stage, Foundation or partial BOTH job.

### Current Guard candidate accepted; ordered-trace runtime refusal

Selective candidate **17972** closed zero (`c200ff`) with 48 independent object
imports, Publisher + shim + Guard compiled, five copied archives, zero repacks and
one link. Static inspection and complete input postflight passed. Peak aggregate
RSS was 2,451,759,104 bytes and the 170 recorded artifacts total 439,014,233 bytes.
Independent Root **1567** closed zero (`984f8e`), full-hashing all 170 artifacts,
checking independent output inodes, 68,352 file / 3,799 directory identities and
canonical source hashes. All children, streams and monitors closed. This is an
accepted current-Guard Wasm build; production eligibility remains false.

Evidence is under `repair/concrete-guard-repair-v1/execution-v1/`:

| Receipt / artifact | SHA-256 |
| --- | --- |
| `actual-candidate-v1/RESULT.json` | `3ddfc76d1eba3718b72a20afbe7d219fe5d8c40350c3a0dd5bacfd976086eeb0` |
| `ROOT-CANDIDATE-CALLER-CLOSED-ACCEPTED.json` | `bc43878909677dc5fa942cc37b53ab0ca4f594074d3c77822d7cd6ace9601bca` |
| `maintenance-build.json` | `abf7ee4a84531bb0be50495b2dbd0858dc641f37f2ea3858d5c651624331c45b` |
| Wasm (109,676,080 bytes) | `70a7b495f44aa107cb5af54fbaf851590cc9ea075f12dc13d95a3efc227c22a9` |
| Factory (210,415 bytes) | `a387affe89a4e9a253289f8a83a1bce1f4dcb6557935091df2ff3cdfa370c468` |

Fresh capsule **83707** closed zero (`785b9e`) in 1.405978802 seconds. Independent
Root readback closed zero (`76bdf4`): 16 copies / 164,443,788 bytes, exact complete
namespace, independent inodes and full input/source/hash joins passed. Capsule
producer is `c2b74d06c4fb9be644cd07e5eb68820ce904d160224ea16dc3194e071a17da9b`;
Root acceptance is `192fb3c98eb08fbe1c3cb180f1b10ef4b2fc9764dd66798f3b4d7b3360769810`
under `repair/runtime-guard-repair-v1/`. Donor and command lineage remain external.

Fresh runtime **7008** closed one (`745c6a`) in **28.156387774 seconds**:
`Actual request trace is not a bounded ordered history`. All 13 positive cases,
including I04 stale-before-TURN, reported passed: 768 case assertions, 17 mandatory
and 31 original author assertions were true. **Zero batches were accepted** and
the remaining 11 batches were not executed. Node's two negative controls passed.
All owners/streams/thread closed, all 47 input full hashes/physical facts stayed
unchanged, guard failure was null, and RSS/output remained within bounds
(3,563,900,928 / 207,230,311 bytes).

The trace had 13,358 rows and 6,015,136 canonical encoded bytes, within 16,000 /
8 MiB. Exactly 66 `actual-JSC-fixture-intent` rows replaced the outer trace serial
with the fixture's own intent counter: event details are spread after the history
serial. The first wrong row is position837 with serial1. Preserve that counter
separately as `intent_serial`; retain strict history ordering, all native evidence,
cases and caps. This is a source-only Worker repair; the accepted candidate and
capsule are unchanged and need no rebuild or copy.

Runtime result `repair/runtime-guard-repair-v1/runtime/actual-operation-v1/result.json`
is `ced613226d55bbc439d9519eee5512760c4ca52f22575959cea66e137928a280`;
positive observation is `119c1342fd017b3b40c119f16d19a2fe6f21c1ac9b4d5cf0d71649710eb38fcf`.
`ROOT-RUNTIME-CALLER-CLOSED-FAILURE.json` (`a8f779b5…`) records independent postflight,
partial request counts (96 ordinary, two replays, 2,702 exports / 539 dispatches)
and closure. Do not resume this Worker or relabel the failed history. Next is a
reviewed serial-field repair and one fresh same-protocol packet/grant/output.
Neutral admission and Foundation/partial BOTH remain runtime dependent and unrun.

### Trace serial repair and native composition cancellation failure — 2026-10-18 UTC

The fresh Worker changes only the fixture-intent detail key `serial` to
`intent_serial` (+7 bytes). Its SHA-256 is
`0b502ce16671c319eb25276aa4ed0f1729dc49efd1793c9970561cf5b4753d75` (45,526 bytes).
The extracted actual-callsite regression reproduces queued counter1 versus outer
history8, reconstructs all13,358 saved rows through the unchanged supervisor gate,
and preserves all66 intent counters; the other13,292 rows are identical. Its original
caller closed zero (`ac5645`), and all2,073 retained budget vectors/boundaries passed.
The projected history is6,016,935 bytes, below the unchanged8MiB/16,000-row caps.
Independent source review verified the exact one-line change and all14 frozen facts.
This pure projection did not relabel the failed7008 observation.

Root bound a fresh47-input packet (193,762,377 bytes), changing only the Worker fact,
its role and the absent `runtime/actual-operation-v2` output. The other46 input facts,
19 roles, accepted candidate/capsule,65 cases/12 batches and all limits were exact.
No compiler, engine build or capsule copy ran. Packet is
`ad91aa667492f3a7dc514a851fcb2086967be3a962275a1f42d8845bc4a38892`;
Root grant is`8f59de71ba1d9d74862d3528def2803870eec3e68b1c08f3e700f3083e4aa6d8`.

Actual runtime **35714** closed one (`5c7d8a`) in **32.829287534 seconds**.
The positive batch was accepted: the strict ordered-history gate now passes.
The editor batch passed E1a/E1b/E2a/E2b/E3a/E3b/E4a/E5a/E5b and failed
`E6a/no-committed-preedit`. The native query after composition cancellation still
contains `cancel:仮`; the composition-ended assertion passed. This is an observed
failure, pending focused cause analysis. **One of12 batches is accepted; the full
runtime remains failed.** The remaining ten batches were not reached. Node's two
negative controls passed. All owners, streams and the supervisor thread closed;
Root independently rehashed and checked physical facts for all47 inputs unchanged.
Peak sampled RSS/output were3,297,701,888 /219,718,049 bytes, within existing caps.

Evidence under `runtime-D03-repair-v1/runtime-guard-repair-v1/`:

| Receipt / observation | SHA-256 |
| --- | --- |
| `runtime/actual-operation-v2/result.json` | `1bdccee7635a60ea4ea5497485353230b09b829a80b4154831912efb001cc22e` |
| `runtime/actual-operation-v2/batch-positive.json` | `6d9a35f20a026259197358dceda3368c542cab3195512c41bc919ba19b43e4e0` |
| `runtime/actual-operation-v2/batch-editor-native.json` | `8eb02f769070d2870b77e236528a968b455f163a35a1ab529a190378e302571a` |
| `ROOT-RUNTIME-TRACE-SERIAL-CALLER-CLOSED-FAILURE-v1.json` | `9d829ac76f9ccc50c4bd6a90e9afc42c4ec7e22bced9942b37a046726b8608bd` |

Preserve both failed runtime outputs. Next is focused native composition cancellation
analysis/repair, then a reviewed fresh same-protocol attempt after relevant checks.
Neutral admission, Foundation construction and partial BOTH remain runtime dependent
and unexecuted. The integrated viewer is unfinished.


The native cause is now established. Public `Editor.cancelComposition()` ends the
composition while retaining marked text, as the earlier feasibility record already
explained. The shared capture contract requires restoration of the original value,
including text replaced by composition. Empty deletion and cloned rich fragments
cannot meet that requirement. Root approved the source-only transaction-owned
native inverse design (`composition-cancel-design-v1/DESIGN.md`, SHA-256
`d6ed0c07b2859d0354a04769bae346440944d74ebad9cb7bd7e372e8eb5c68d3`;
Root review `ca9f7b53a361cb14784d9ec0447493f8fcfb8fa7c9e86ad4a9e316be037f11df`).
The native source implementation is frozen under
`composition-native-rollback-v1/SOURCE-FREEZE-v3.json`, SHA-256
`14ddceead900b12953c6fbffa68723a6ce7e1d3d35fe8a0b0345557ef5d6aef4`.
Fresh supported host session45401 closed zero (`beb293`): all21 journal checks
passed with zero exclusions, including the no-exceptions/no-RTTI fixture (1.78s
CTest). These use FakeStep bookkeeping; they do not compile or execute WebCore.
The editor main and three private headers now live under the editor overlay.
Shared pixel/physical main and headers retain exact HEAD bytes. No repaired
native engine candidate is established.

The design retains one exact pending undo step and an independent root selection,
checks authority around author callbacks, and restores through native inverse
commands. Cancellation uses native `beforeinput/historyUndo`, composition-end and
`input/historyUndo` events; this does not establish OS IME event equivalence.
Unknown or partially verified effects are quarantined without replay. Owned9
cleanup must preserve the original authority and must not steal focus.

The reviewed dependency proposal adds Backend and main to the three existing
fresh units: **46 imports / five fresh units / 168 artifacts**, with five copied
archives, zero repacks and one link. Only main may depend on the changed private
PageClients/UndoHistory headers; the new private composition bridge may occur only
in Backend and main. Old two/three-unit lanes, historical profile/map pins, ABI,
opaque engine inputs, VFS and all resource caps stay strict. Producer/readers,
source metadata and fresh controls use separate explicit branches. The maintained
producer passed132 pure tests, the RC3 readers66 inert checks and disabled
controls78 checks; independent producer review found no consequential code defect.
Fresh controls must freeze the five historical excluded-unit depfiles as well as
the46 imported rows. Final source metadata and Windows catalogue dispatch are
published and independently reviewed:159 editor inputs and198 native inputs
(158 native source files). The three registered pure source suites passed65/65
with no exclusions. Original document1316 retains39/46 plus seven checkout-ancestor
TMPDIR refusals; document-only43479 passed46/46 after a checked external-scratch
probe and no source/assertion changes. Native15 and bootstrap4 results were reused.
Final metadata freeze is `composition-source-metadata-v1/FINAL-FREEZE-v1.json`,
SHA-256 `a381ab12c3e31e19f8578ae150c77a5b26ce554ba9906e071fa1491fa7b2821d`.
Actual
API linkage, layout/focus behavior, inverse restoration and the five fresh depfiles
remain acceptance gates. Fresh five-unit preparation has passed as recorded
below; its plan, build and runtime remain unexecuted. Native inverse restoration is fenced around callbacks, but a synchronous
input handler may legitimately change same-text markup afterward; no unconditional
post-callback DOM-shape guarantee has been qualified. The original starting
selection is restored after the low-level inverse before native publication;
actual layout, focus and callback behavior still require the bounded runtime.
Neutral/Foundation/partial BOTH remain unrun.

The unarmed Foundation884 proposal also needs a fresh top-level CMake input pin:
the new focused journal test registration changed that file. Its proposed
900/1200/30/jobs2 limits remain proposals; no Foundation grant is implied.

<a id="fresh-composition-preparation-recovery"></a>

### Fresh composition preparation recovery — 2026-10-18 UTC

Fresh scope `repair/composition-preparation-v1/preparation/execution-v1/` passed
actual preparation **90712**, original caller zero (`99b782`), in **91.923987731 seconds**. All
source, metadata and copy phases closed naturally with zero exit. Independent
Root readback **65753** closed zero (`1401f8`) in **9.987983872 seconds**: complete namespaces and full hashes
passed for 369 source files / 564,592,040 bytes, 12 metadata files / 106,264,010 bytes and
42,779 copied files / 861,802,853 bytes. All 329 frozen inputs and eight execution controls
remained unchanged. Old failed preparations and partial copies were not consumed.

`ROOT-CALLER-CLOSED-ACCEPTED.json` is
`b7698c509283db411c227d44ebb36fa5847f71f16536ee4924ebb7d8e5eff211`.
Current R/S are `f9e9b3af789d2eda506ba27cc33485509b19c5d99ee47708fd7a107214267c73`
and `37bc3ed5edc267d007a073efe4fbaaae08e19bf5c3418bc18903afd43ca2e0cb`;
reuse proof is `f20ccc597e8972f2343a90e7aeaf84be81afc12386b341b4ec85d723d782df47`.
All preparation/readback writers and streams are closed; these outputs are now
immutable inputs. This accepts preparation only. The first current compile-free
plan, session **77199**, closed one (`9ab719`) after the planning child rejected
`Composition include namespace/physical-header/VFS context differs`. No plan was
produced and compilation did not start. Result
`8b95d1abd1fa12e92c8bf3474d679a627efa7fe86a0233e67b21eca1767970bc`
records natural primary exit one, joined writers and passed frozen-input
postflight. Its packet and outputs are retained and must not be rerun.

The failure came from deriving search context from only the 46 imported
objects. Making main fresh removed its two unique dependency-parent directories:
`Skia/Headers/top/skia/effects` and `WTF/Headers/wtf/unix`. The composition-only
correction retains the complete authenticated original51 dependency coordinates
and all current object arguments. It reproduces the original 413 directories;
all 4,171 normalized VFS mappings and the physical-header table remain unchanged.
The exact context matcher and imported46 admission are unchanged.

The corrected helper is `796994d6cee59ed86e6ab35a598285d8190847cc554bed2b2067b39a4d944998`.
All 71 registered maintenance cases passed with zero exclusions (session58156,
caller zero, chunk332760), including construction-level coverage for main-only
leaf directories and original frozen/relocation/private-cache joins. Independent
source review checked all 5,342 historical metadata joins. No six published
source/native JSON files require refresh; the assembler separately captures the
changed helper. The accepted preparation still embeds its original helper and
cannot serve the corrected producer. Fresh disabled controls are being prepared
in `repair/composition-context-preparation-v1/`. Its metadata-only builder passed
and sealed 354 frozen inputs, but the first runner command closed one (`707b37`)
at the initial intent check, before creating any source, metadata, copy or phase
output. The runner expected a scope-local descriptor while the packet correctly
selected the exact immutable predecessor descriptor. Failure448fa207 preserves
the caller and zero-phase evidence. The old packet must not be rerun.

A fresh `repair/composition-context-preparation-v2/` control scope corrects that
single path predicate and adds a concrete packet-shaped intent test. The reviewed
helper and six catalogues remain unchanged. Fresh recipe/manifest, metadata and
preparation acceptance must precede another plan.

The intended actions remain 51 selected objects, 46 imports, five fresh units,
five archive copies, zero repacks, one link and readback of all 168 artifacts under
the existing caps. Current-source compilation and runtime remain unverified;
production eligibility remains false.


### Fresh composition-context preparation v2 — accepted P3 preparation — 2026-10-18 UTC

The corrected current-helper preparation in
`repair/composition-context-preparation-v2/preparation/execution-v1/` was accepted.
Original caller **3007** closed naturally with exit zero, completion chunk `641a62`,
in **97.618891616 seconds**; all three phases closed naturally with zero exit.
Independent Root readback **14272** closed zero, chunk `cc547c`, after full readback
of 369 source files / 564,595,000 bytes, 12 metadata files / 106,264,034 bytes and
42,779 copied files / 861,802,853 bytes. All 363 frozen inputs and eight execution
controls remained unchanged. No old failed packet or partial copy was consumed.

Root acceptance is `preparation/execution-v1/ROOT-CALLER-CLOSED-ACCEPTED.json`,
SHA-256 `c2c385194f7d1e9af6add5782b7415f3d42b8c462fb35dd8f6cc154ffd6e8f07`.
The original P1 preparation acceptance `b7698c509283db411c227d44ebb36fa5847f71f16536ee4924ebb7d8e5eff211` remains tied to its original helper/source identity; this P3 receipt does not restamp it.
Current R/S are `4fac58dd33a4d7d7e875eb7912d7506082ec2906cc551e55547ae20a3a825fe9`
and `bc4ea6776ee399094bd52db7c61e1b2ab449cff9a2568d1ced585b6f4e5bb994`; reuse
proof is `f20ccc597e8972f2343a90e7aeaf84be81afc12386b341b4ec85d723d782df47`.
The corrected helper `796994d6cee59ed86e6ab35a598285d8190847cc554bed2b2067b39a4d944998`
and test `0611e4bc31ca518df7e0faea62a0e3ceb622c40a182427245a685075abb116c9` are
frozen; all 71 registered maintenance cases passed with zero exclusions. The
original P2 frontgate failure `707b37` remains preserved with zero phases/output;
its rejected packet is not reusable.

Next is the dependency-ordered, compile-free 51-object plan, followed only after
acceptance by 46 imports, five fresh units, five archive copies, zero repacks,
one link and readback of 168 artifacts under existing caps. Current-source
compilation, candidate/runtime, neutral and Foundation work remain pending or
unverified. The integrated rich viewer is unfinished and production eligibility
remains false. [Validation evidence](appended-validation.md#fresh-composition-context-preparation-v2) records the exact acceptance.

### Current-helper compile-free plan failure — 2026-10-18 UTC

The P3 preparation acceptance above remains valid for helper `796994d6…`.
A fresh compile-free plan caller **26403** closed one (`db536c`) with
`Invalid composition context dependency fields`. No plan was produced and no
compiler ran. All owners and streams closed naturally; the supervisor reported
primary exit one, no lingering descendants or termination, and the full frozen
input/namespace postflight passed. The failed packet and outputs remain immutable.
Result is `830226acf3f0def1ac7cd937fcd3a5025a6d055d804ad7c87dc699a535a3ca34`;
the 53-byte child log is `3211b0998f064f09b33588385c1f961c58c221844aba483c127d8b9c93625717`.

The original 51 depfiles contain 5,349 distinct dependency keys, while their
retained sidecar contains 5,342 rows. Seven fresh-unit dependencies have no
sidecar row: Publisher/shim sources and headers, three WebCore headers and the
shim's generated metadata header. The prior context review covered the sidecar,
missing these seven keys. Strict authentication of that separate partition and
an actual-metadata regression probe must precede a new physical preparation and
plan. Current-source compilation/runtime remain unverified; production eligibility
is false and the integrated viewer is unfinished.

<a id="seven-input-context-source-repair"></a>

### Seven-input context source repair — 2026-10-18 UTC

The strict repair is now frozen as helper
`401e88d0bb9d559b8d00b78012f05fd7e693252041a7a513b796438aa51f51b8`
and tests `e765b56031bef299124e2571025190ffc4fc2346d4f9c47ce8037b323d97ff2f`.
The helper authenticates the six retained coordinates against exact original
owners, frozen facts, old namespace pins and current inventory coordinates.
It classifies the generated header using the admitted 112-product metadata,
requires Shim-only ownership and excludes that coordinate without reading or
importing its old body. Unknown, partial or extra missing-input sets fail.
The old context matchers and other lanes remain unchanged.

The supported focused suite **80499** closed zero (`01eb2a`): **73/73 cases,
zero exclusions**, 0.46 seconds (the original 71 cases plus two new cases with
15 negative variants). Independent strong source review found no blocker.
A separate metadata-only construction probe **64357** closed zero (`9caa6b`) in
9.199689536 seconds. It parsed the five original depfiles, reconstructed the actual
5,349-key union, independently reconstructed the current physical-header/VFS view,
and passed the unchanged context and direct-source delta gates: **413 directories,
4,171 mappings**, physical digest
`0f413062843fc4a36bbed92676d0a607f87dc09771becfb8715a49e007f1d6d0`.
Fourteen actual-metadata negative cases and an upstream generated-record pin-tamper
check passed. No SDK payload, unlisted payload or old generated-header body was read.
Two original-header and four alias hashes reused accepted fullhash evidence;
the probe does not provide a new physical SDK qualification or engine runtime.

Current source freeze is
`repair/runtime-recovery-v1/missing-seven-repair-v1/ROOT-SOURCE-FREEZE-v2.json`,
SHA-256 `6859921696524dc9d67483a6a5c8cc0db309dfdddf50add1bb4d72b0c3f9fcca`.
The probe result is `c1159393a071bdcb4fcf883aff0903b08ff025c1ff1ff2a44dad415629bdc2d2`.
Fresh disabled controls are being prepared in
`repair/composition-context-preparation-v3/` (P4). New physical preparation and
independent acceptance must precede another compile-free plan. No current-401e
plan, five-unit compilation or runtime is accepted. The viewer remains unfinished
and production eligibility is false.

<a id="fresh-current-401e-preparation-accepted"></a>

### Fresh current-401e preparation accepted — 2026-10-18 UTC

P4 scope `repair/composition-context-preparation-v3/preparation/execution-v1/`
passed its single fresh preparation attempt. Original caller **76300** closed
naturally with exit zero (`cf1c16`) in **90.239807475 seconds**; source, metadata
and copy all closed naturally at zero. Independent Root readback **38868** closed
zero (`f66e9a`), accepting all complete namespaces and full hashes: **369 source
files / 564,597,526 bytes; 12 metadata files / 106,264,034 bytes; 42,779 copied
files / 861,802,853 bytes**. All 363 frozen inputs and eight controls were unchanged.
No SDK program, compiler, linker or runtime ran, and no failed partial copy was used.

Accepted receipt `preparation/execution-v1/ROOT-CALLER-CLOSED-ACCEPTED.json` is
`376623a2bc3eecb567989a21f0d522a72ffdd261690bbf1e28cfbc3127195196`.
The original result is `9317c2c57ce2ff13c5f898699e2e43b9ea87ada3ac0133d60f4e3be92d24b513`.
Current recipe/manifest are
`a76949efb3f2395897adebd87b593429a8f31b3075a36005a9059641acff00fa` /
`2219a5f1c29accacec15ff352a35ac71e59a848b1294f5eeb036ec5303a38b6c`;
reuse proof remains `f20ccc597e8972f2343a90e7aeaf84be81afc12386b341b4ec85d723d782df47`.
This acceptance binds helper `401e88d0…`; P3's `c2c38519…` acceptance continues
to identify its original `796994d6…` source. Failed plan26403 and all prior failed
packets remain immutable.

The current compile-free plan is now accepted below. Five-unit compilation,
168-artifact readback, actual VFS/depfile ownership, capsule, runtime, neutral and
Foundation acceptance remain pending. The integrated viewer is unfinished and
production eligibility remains false.

<a id="fresh-current-401e-plan-accepted"></a>

### Fresh current-401e plan accepted; build failed — 2026-10-18 UTC

P4 compile-free plan **6003** closed naturally with exit zero (`10fe16`), and
independent Root readback **5501** closed zero (`c6fba2`). Plan
`selective/execution-v1/retained-plan-v1/plan.json` is
`cf4ae7af8e46b99e9d13b8f62d6a8b0423bf3e11a6b4179ffed42ec70beaf0a3`;
Root acceptance is
`30dfe41e834465cec5511b01f025c99b4bfc6d7fb0f894073171d16934f134be`.
The exact planned partition is **51 selected, 46 imports, five fresh units,
five archive copies, zero repacks and one link**. All 68,442 frozen file and
3,797 directory identities and 27 control-source hashes were rechecked. This
accepts the current `401e88d0…` plan; it does not accept compiled output or runtime.

The lossless command ledger is `9d719bd1368e440d0d0666e78bb2c032105812f94d9ed6c544f4510987079d78`.
The first command derivation lacked its fresh output directory, and the first
build-metadata invocation passed a relative path where an absolute path was
required. Both failed before candidate output or compilation; their original
logs remain immutable. Supervisor setup recovery used each same assignment,
recorded blocked/ready states and changed no producer source or repair allowance.
The corrected metadata invocations passed.

Root and independent strong review accepted the fresh build packet
`e2c41bb38b1b18d4539a25c59e3be953ea70a6ec258e8dfb784b281688191af9`,
with 68,451 file / 3,799 directory identities, current source/header facts and
unchanged resource caps. Its single actual build, original caller **67381**,
closed naturally with exit one (`66caaf`); result is
`e31bce280abd0b6912ed9691e08fc72d081654d9b22fc2f6201b59417cdebfa3`.
Configuration passed. Ninja failed at step 22/59 compiling
`BibNativeEditorBackend.cpp`: the new guard calls `FrameDestructionObserver::frame()`
through `Document`, but its inline definition was not included. Frozen postflight
passed and all writers joined; peak aggregate RSS was 1,695,993,856 bytes. No link,
168-artifact acceptance, VFS/depfile acceptance, capsule or runtime pass exists.
The complete failed output and controls remain immutable.

Root's continuing Sol-owned source repair adds only
`#include "FrameDestructionObserverInlines.h"` to both backend copies, now
`d14dab28100d3689d9a04aa4a81290b50cf24cd3e00a34b2f8402d9eeca9da60` /
61,375 bytes. Function bodies and flags are unchanged; exact retained declaration
and definition explain the compiler failure. Independent review accepted this
source-only fix. The refreshed metadata changes only 11 paths; seven other prior
paths retain exact bytes and physical identities. Both historical reverse tables
and all existing origins remain exact; reader functions and assertions are unchanged.

<a id="inline-include-source-acceptance"></a>

The supported complete source suites then passed: original caller **84029** closed
zero (`92d476`), **46 document + 15 native-source + 4 bootstrap = 65 cases, zero
exclusions**, in 1.60 CTest seconds. The owned external temporary directory avoided
the known ancestor-alias prerequisite and was removed empty after all fixtures
closed. All 18 metadata and 12 native-source facts remained unchanged. Source
receipt is `952cf53e39daa0f4b607c2ba72cea7aaf0ae7a8f029ab524a7df22637e3be29a`;
Root final source-only acceptance is
`9e141ba835e0923996d416c17d84352025d0be8338231a94594f0965971cf477`.
Fresh N4 source freeze is `d21be21d93c8878908292b0136a9f28981e8f79c8d6a828b84d4b469f07cdb00`;
integrated metadata freeze is `aba8b420c6a8bb5fc911a4a46843dc7c3151b42899085b6779877cffdea0b7b6`.
The N4 file is `repair/composition-native-rollback-v1/SOURCE-FREEZE-v4.json`;
the metadata file is
`repair/runtime-recovery-v1/INLINE-INCLUDE-INTEGRATED-METADATA-FREEZE-v1.json`.

Fresh P5 controls in `repair/composition-inline-preparation-v1/` bind the Backend
inline-header repair (`d14dab28…`, 61,375 bytes in both copies) and helper
`401e88d0…`. Root and independent review accepted 125 unique / 128 ordered ASTs
and 95 source-only checks. The original
`luna-inline-controls-20261018-v1` generator failure happened before
candidate writes; Root found path/input-binding omissions and required a Sol
takeover of that same assignment. That failure, original patch and deadline remain
preserved, with zero repairs used. Sol completed the controls at 08:02:34 UTC,
before the unchanged 08:13:31.405922 UTC deadline. P4 evidence still belongs to
its original `4f72` source.

<a id="fresh-inline-preparation-accepted"></a>

The fresh composition-inline preparation was accepted after actual session 67862
and independent Root readback 6158. All three phases closed naturally with zero
exit; 363 frozen inputs, eight controls, 369 source files, 12 metadata files and
42,779 retained copies passed complete hash, mode, namespace and physical-identity
readback. The accepted result is `a06cadf792ecea14d48d9092ba6095ead8edca419a78dc5cc173eb29b07b93af`;
Root acceptance is `c7ca799818bafca63b33aa21b4a77aa7070f03819ebd7c1a336f37edcc990e13`.
The original result and Root receipt are `preparation/execution-v1/actual-v1/RESULT.json`
and `preparation/execution-v1/ROOT-CALLER-CLOSED-ACCEPTED.json` in the P5 scope.
This was preparation only and ran no compiler or linker.

<a id="fresh-inline-plan-accepted"></a>

The fresh selective compile-free plan was accepted after session 70848 and Root
review 77786. Its 51 selected entries comprise 46 imports and five fresh entries,
with five archive copies, zero repacks and one planned link. The accepted plan is
`40af90e69176f4a65003e820439d82cf8f4b9eaafb45bd7b1b30ac699679ddfd`; Root
acceptance is `4fa9b124aab5715b80ca1d0694419d1e289825fa3a1ce30cc8648ae3e50919bf`.
The plan and Root receipt are `selective/execution-v1/retained-plan-v1/plan.json`
and `selective/execution-v1/ROOT-PLAN-CALLER-CLOSED-ACCEPTED.json`.
<a id="fresh-inline-candidate-accepted"></a>

The subsequent selected build **4865** closed zero (`59428c`). Exactly five units
compiled, 46 objects were imported, five archives were copied, zero were repacked
and one link completed. All 2,060 opaque archive members were unchanged. Independent
Root **11922** closed zero (`c0fda6`), accepting the exact 17-field receipt and all
168 artifact hashes/physical identities. The separate VFS/five-depfile gate
**67340** closed zero (`b1b754`): all 4,171 mappings exclude the three protected
headers at both endpoints, and all five actual fresh dependency owners passed.
The original first gate-wrapper failure (`601aaf`, Path instead of strict string)
remains preserved; only the wrapper argument was corrected, with no predicate or
build rerun. The Luna predicate was independently reviewed before use.

The original build result is
`selective/execution-v1/actual-candidate-v1/RESULT.json`, SHA-256
`f210dc0bc9ea624c5bf0c5c3bf467b0d1d4551472f0d601fd1c4117013227c89`.
Root candidate acceptance is `b045468573caca84a9d4430d4acf284ca54f6bf015ea5be51a736f374364cc3a`;
the separate VFS receipt is `f0e4344c2a17972c365209f1fdc59ac3d8363235ee8bf027acd8a9ca96f10471`.
Both are under the P5 `selective/` scope. The combined static-gate receipt is
`repair/runtime-recovery-v1/P5-CURRENT-CANDIDATE-ALL-GATES-ACCEPTED-v1.json`
(`bc87b6a72f5bf0e6db35bb38b743fca25929e9e673807d7968c60b29b04ce5e5`).

Fresh metadata-only capsule **38638** closed zero (`e9ce28`) in 1.583 seconds;
independent Root readback closed zero (`ee0415`). All 16 independent copies /
163,069,449 bytes, original inputs and two external lineage records passed complete
hash, namespace and physical checks. The producer result is
`8e01f23ee7b9815ac6410468efc1d967fd7afd124983bf0d585c5120827d292c`;
Root capsule acceptance is `bac68c23462f17e676327fc074c5dcfe49bf46c9e3a231b5f2c13dce1aa1d0c2`.
These are `repair/runtime-composition-repair-v1/capsule/operation-v1/RESULT.json`
and `repair/runtime-composition-repair-v1/ROOT-CAPSULE-COPY-ACCEPTANCE.json`.
No engine/compiler/SDK program ran during this copy.

<a id="fresh-inline-runtime-failure"></a>

The fresh 47-input / 65-case / 12-batch runtime **33101** closed **one** (`370bc5`)
in **36.78813448 seconds**, failing `Actual provider dispatch count`. One batch
was accepted: all 13 positive cases passed. The editor observation completed
E1a through E8a (14 cases), including all **82 E6a assertions** and
`E6a/no-committed-preedit`; E8b remained running with no emitted case assertions.
All 743 emitted editor case assertions were true, but its batch was rejected.
The other ten batches were not reached. Node's two negative controls passed.
All owners, streams and the watchdog thread closed, and Root independently
rehashed all 47 inputs and physical identities unchanged. Sampled RSS/output were
3,366,293,504 / 219,757,021 bytes, below unchanged 4-GiB / 512-MiB limits.

The original result is
`repair/runtime-composition-repair-v1/runtime/actual-operation-v1/result.json`,
SHA-256 `240b2de90af81b201d05079823f696c6bf2f88dc4203d157fdde105c9c8cde92`.
Closed failure/coverage and all 47 postflight facts are retained in
`repair/runtime-recovery-v1/ROOT-P5-RUNTIME-CALLER-CLOSED-FAILURE-v1.json`, SHA-256
`0a6d4bba5d1dab80564be3aa454eac60f0ff959b1215a2132585e6fcb19d0603`.

Strong diagnosis found a probe/transport mismatch: the native copied dispatcher
rejects malformed editor bytes before opening a host turn, while the normal
claimed endpoint requires a valid reply. Its predicted signed return is `-1`;
that return was not recorded by this failed observation. The distinct negative
copied-export diagnostic is now source-complete after the same-assignment Sol
takeover. Final authorized runner1329 closed0/`32e90c`,139purevectors; Root independently
accepted exact source and physical facts (`df355cae…`) before the original deadline.
The original incomplete Luna patch, unauthorized direct syntax checks and both
earlier check versions remain preserved. Normal endpoint/bridge checks remain
strict. No repaired runtime packet/grant/output has been created; actual runtime,
neutral and Foundation acceptance remain pending. The integrated viewer is
unfinished and production eligibility is false. See
[the source-only acceptance](appended-validation.md#e8b-transport-source-accepted).

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

This is the original 2026-10-17 preservation snapshot. The verified checkpoint
above supersedes its HEAD, worktree and runtime-capacity observations.

At that earlier handoff, local `main` HEAD was
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
global child-model default. Runtime capacity at that earlier handoff was 25 total agents,
including the primary. Inspect the active client for current capacity; neither
that old count nor a configured maximum guarantees available slots. Missing external
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
reviewed. The original handoff had no engine artifact containing this repair;
the separately accepted recovery candidate above now contains it.

### Original failed preparation and incident chronology

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

These original D03 input notes retain their historical identities. Use the latest
P5/RC3 and probe facts above for current admission, rather than the old failed P.

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

This is the earlier preparation-to-build sequence. Current P5 preparation, plan,
build and capsule are now accepted. Follow the verified checkpoint above; do not
repeat these completed steps merely to reach the next runtime gate.

Recovery has completed steps 1–3 and the metadata copy in step 4 using the new
receipts above. Step 4 passed the earlier trace point and exposed I04. Its Guard
source repair now passes all 82 focused host cases; source metadata and the
explicit three-unit producer/reader successor pass focused checks. Preparation6762
then exposed a copy kind-gate omission; fresh v2 preparation85828 and Root88406
now passed. The compile-free three-unit plan and current-Guard candidate also
passed. Runtime35714 now accepts the positive batch and exposes the editor E6a
composition-cancellation failure; that focused repair is the next gate.
The original recipes below describe the two-unit predecessor only. Preserve their
receipts and reusable dependencies; use fresh source/proof/output identities for
the Guard successor. No downstream runtime-dependent gate has passed.

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
