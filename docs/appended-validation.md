# Appended implementation checkpoint

## Current native runtime and neutral handoff — 2026-10-20 UTC

### S8 closed failure and current diagnosis — 2026-10-20 UTC

S8 (`72663`) is a closed failed partial Foundation23+3+6 run: caller 2 / capture-failed, outer owner 0 and natural closure after 387.719795s at 3,495,653,376-byte peak RSS. The controller failed on a per-file byte cap in `runCase`, not a timeout. All 196 inputs / 141,713,323 bytes were unchanged. Only E01 ran, producing 4,959 events, 66 case records, 34 GUI operations and 17 polls; E02–E23 were unreached, no E01 outcome was accepted, and the independent full reader did not run. [The closed failure record](../.agent-work/foundation-full-runtime-20261020-v8/ROOT-RUNTIME-FAILURE-v1.json) has SHA-256 `4f026063323df96b15174fd9c35b515f3b5cca2920363f3a3b7391321dd82b94`.

Root-accepted NC680 passive extraction found 15 focus attempts, all rejected `stale_identity` with `focused=false`; the last six used presentation revisions 23, 25, 27, 29, 31 and 33. Its seven-minute budget ended after the query-4 gap was identified, before an accepted focus or case outcome. NC674 component evidence does not prove actual finite focus recovery. NC685 is diagnosing the central browser/Host path; the `App.retry_presentation` full-document tick from `beforeinput` starvation explanation is a source hypothesis only. NC682's capacity proposal remains on hold and unselected. Do not raise the cap solely to mask the focus retry. F12 HOST/readback acceptance `bf4f1f75…`, engine65/12+Node, neutral28+6, separate export and native 5,344-assertion barrier evidence remain accepted and reused. Full-runtime predicates and global eligibility remain false. Current restart v11 is [the 23+3+6 packet](../.agent-work/appended-implementation-20261016/runtime-D03-repair-v1/runtime-composition-repair-v1/runtime-allowance-20261018-v1/native-runtime-v1/P01-keyboard-diagnosis-v1/P11-pointer-diagnosis-v1/retired-form-selective-execution-v1/RESTART-20261020-v11.json) (`5501a6a06b943855ee43edbfcffea7d18246509450b3f31c11131053bf3f18cc`). Resolve the focus and capture-cap diagnosis before another complete runtime/readback attempt.

<a id="f9-normal-host-both-refresh"></a>
<a id="f10-normal-host-both-refresh"></a>

### F10 normal HOST BOTH refresh — 2026-10-20 UTC

Root accepted the F10 HOST BOTH/editor construction and complete independent readback in [the F10 full-readback record](../.agent-work/appended-implementation-20261016/runtime-D03-repair-v1/runtime-composition-repair-v1/runtime-allowance-20261018-v1/native-runtime-v1/P01-keyboard-diagnosis-v1/P11-pointer-diagnosis-v1/retired-form-selective-execution-v1/foundation-conduit-host-refresh-v1/readback-execution-v1/ROOT-FULL-READBACK-ACCEPTANCE-v1.json), SHA-256 `72197f6ed308306bc705adfcca1ea4d197af3eadce7bd06fd7d2e167663b6fcc`. It binds 36 translation units, 18 archives, 73 captures, 2,103 raw / 2,748 configured source records, 19,423 SDK metadata rows and 96 retained engine originals. Reader `97292` closed naturally with status 0 in 69.63707604398951s at 724,627,456-byte peak RSS. This is construction/readback acceptance only; no F10 runtime or production eligibility is accepted.

Historical F9 acceptance remains bound to its prior HOST snapshot: [the F9 record](../.agent-work/appended-implementation-20261016/runtime-D03-repair-v1/runtime-composition-repair-v1/runtime-allowance-20261018-v1/native-runtime-v1/P01-keyboard-diagnosis-v1/P11-pointer-diagnosis-v1/retired-form-selective-execution-v1/foundation-normal-host-refresh-readback-execution-v2/ROOT-FULL-READBACK-ACCEPTANCE-v1.json), SHA-256 `084ad275e50bad5718cc0403eb7380472d2603f8c892d724782cf590bc7e6037`, binds 36 translation units, 18 archives, 73 captures, 2,103 raw / 2,748 configured source records (raw tree `09e3912a25542eb37455a30758029695686726eecf726e1c48dfd01c47c24b`), 19,423 SDK rows and 96 engine originals. Reader `63479` closed 0 in 77.828851582s at 664,719,360-byte peak RSS. Preserve F9's first reader failure `84395` (missing explicit grant for the added `source.json`) and the successful exact one-file-grant retry. F9 kernel Wasm/factory were `f8201ecd91aa7767bde2c81b5027214518112115d3a6184ba034fc386ed5c986` / `f7de2db03639a4671515a81c0375d9b7d8444ffdcd3dd3d4d2338af0210ea53f`; retained engine Wasm/factory `b9c724ba2ada4e7dd05823260c3d2bcbd670be2f880b8fab7779a2641ba84050` / `b28cf35022dc9e6ba65929e9f5c833afcb36b82e06591f2161ad7ede388fdb08` were reused unchanged. F10 remains the accepted normal HOST snapshot; the later D11 diagnostic construction/readback checkpoint is recorded below.

The shared browser-conduit repair (`7c478b32…`) passed 74 focused model tests and actual Firefox trusted composition commit plus Escape cancellation (`59397`, `78468`) with natural closure and a modeled receipt adapter. Root also accepted the actual Firefox window-deactivation component in [NC607](../.agent-work/appended-implementation-20261016/trusted-browser-window-deactivation-v1/NC607-v1/root-validation-recovery-v2/ROOT-ACCEPTANCE-v4.json), SHA-256 `d4de80f5ee065eff2cf31243fb95271594b2fa016c0870175a7269acdee428bf`: the trusted editor/window lost focus, `document.hasFocus()` was false, and the shared conduit became suspended. Its receipt adapter is modeled, so it does not establish Foundation/native receipts, E06 live TIP composition, native9/material paired retirements, or full runtime. Preserve the earlier F9 first readback failure (missing the explicit `source.json` grant) and the successful exact one-file retry as history. F10 uses the fixed qualified SourceRoot snapshot; this documentation update does not require another HOST/engine build. Native65/12 plus both Node negatives, neutral28+6 and separate export remain accepted and reused unchanged. NC589 confirms exact scoped engine-consumer eligibility on neutral28+6 (`f52af0fd…`); the global full-integration gate remains separate and false. NC585 is only two component cases / 5,344 assertions and its partial-order contract.

Remaining gates: Foundation23+3+6 composition with the current full preparer; trusted browser input and native proof/source-object joins; terminal/navigation reader integration; eligible Foundation receipts; ordinary public-host, QuotePad, viewer and performance evidence; native GUI and full product qualification. The accepted engine, Native65/12 with both Node negatives, neutral28+6 and separate export remain reused unchanged. Production eligibility remains false. Ordinary web edits remain packaging-only and compiled edits rebuild only the small portable module. Native orchestration remains active, without session/board/claim/lifecycle administration or aggregate attempt/time ceilings; retain resource protections and behavioral deadlines. Preserve the prior failures and historical evidence below.

### S4 full Foundation23+3+6 runtime and D11 construction/readback checkpoint — 2026-10-20 UTC

S4 (`94652` / `fdbed5`) failed with `Surface session admission is closed`: the original caller exited 2 while the outer owner returned 0 and closed naturally after 88.429694211s (3,195,813,888-byte peak RSS). All 196 inputs (141,611,880 bytes) were unchanged. Only E01 was reached: 1,329 events, nine case records and no outcome; E02–E23 were not reached. The accepted observer identifies kernel `gui_web_receive` call 657 at event 1331 on command turn 1330, but no JavaScript stack was captured; original boundary events 1330/1331 were not committed. A sixth poll is a source prediction only. See the [S4 failure record](../.agent-work/foundation-full-runtime-20261020-v4/ROOT-RUNTIME-FAILURE-v1.json) (`15eb4741…`). S3 was never armed or launched; preserve its root redundant-chmod physical-record failure.

D11 host diagnostic source `6af9e012…` adds bounded flags, first-failure, close and callback-site observation only; it does not fix admission behavior. Build `90059` (`f8dfb4`) closed naturally with caller 0, 36 translation units, 18 archives, one link and 73 captures at 703,336,448-byte peak RSS. Root accepted independent readback `34642` (`98593a`) in [the D11 record](../.agent-work/appended-implementation-20261016/runtime-D03-repair-v1/runtime-composition-repair-v1/runtime-allowance-20261018-v1/native-runtime-v1/P01-keyboard-diagnosis-v1/P11-pointer-diagnosis-v1/retired-form-selective-execution-v1/foundation-surface-admission-host-probe-v1/readback-execution-v1/ROOT-FULL-READBACK-ACCEPTANCE-v1.json) (`508fe04a…`; 87.479820s, 722,132,992-byte peak RSS): 2,103 raw and 2,748 configured source records, 19,423 SDK rows and 96 engine originals joined. The new kernel Wasm is 1,719,543 bytes (`5d0b0f40…`); the engine factory and Wasm were reused unchanged. This accepts construction/readback only. F11 still needs the complete 23+3+6 runtime and native/static/trusted/source-object/SDK/closure/readback conjunction; its source-bound packet and native proof are being prepared. Engine65/12+Node, neutral28+6, separate export and existing private C/Rust evidence remain reused unchanged, without reruns. Production eligibility remains false.

### S2 prior full Foundation23+3+6 runtime attempt — 2026-10-20 UTC

Root accepted the NC628 live-prefix repair and NC629 kernel-only scanner source repair for fresh source binding ([source acceptance](../.agent-work/foundation-full-runtime-20261020-v2/ROOT-SOURCE-ACCEPTANCE-v1.json), `a28ead82…`). Preparation `24969` (`1f2412`) was accepted for 50 files / 112,924,060 bytes, including 46 original suffix/index occurrences and the three JavaScript repairs. S2 runtime `25610` (`366822`) then failed in E01 with `Surface session admission is closed`; only 1,329 events and nine case records were captured, with no outcome. E02–E23 were not reached. Outer owner 0 closed naturally after 86.114902247s at 3,296,681,984-byte peak RSS; original caller exited 2. All 196 inputs (141,608,554 bytes) were unchanged. Independent extraction saw stale focus followed by open successful resync/poll and no captured native throw; the closure cause remains unresolved. NC637's bounded observer-origin probe is underway. Runtime and independent full readback remain unaccepted; the source repairs do not accept Foundation23+3+6 or production eligibility.

### S1 prior full Foundation runtime attempt — 2026-10-20 UTC

Under the already-authorized metadata512 profile, preparation `67409` (`fa5f67`) was separately accepted for 50 files / 112,922,832 bytes, including 46 original suffix/index occurrences. Fresh runtime `97528` (`a51cd8`) failed in E01 with `Actual Foundation begin/result ownership join is missing`; E02–E23 were not reached. E01 contains 1,197 events, 12 case records, five GUI operations and two polls. The outer owner returned 0 and closed naturally after 95.766s; all writers and descendants closed. The original caller exited 2 with capture-failed, so this is a failed partial run, not runtime acceptance. All 196 selected inputs (141,607,148 bytes) were unchanged. See the [closed failure record](../.agent-work/foundation-full-runtime-20261020-v1/ROOT-RUNTIME-FAILURE-v1.json) (`87ac2d4e…`). NC626 independently found successful same-owner begin/result pairs for query 4 and command 9, so the E01 failure does not establish that those pairs are absent. NC628's live-prefix/source diagnosis remains in progress. Separately, NC627 found a kernel-only scanner-policy mismatch; the NC629 source correction is pending. Full Foundation23+3+6 runtime/readback, public eligibility, and ordinary QuotePad, viewer and native-GUI qualification remain pending; production eligibility is false.

### PE31 runtime and readback checkpoint — 2026-10-20 UTC

Foundation8 construction/full readback (`b3669a5b…`), engine65/12 with both Node negatives, neutral28+6 and separate export remain accepted and reused. PE31 runtime `5266` closed naturally, caller/controller 0, in 199.907787300s at 3,173,257,216-byte peak RSS; all 124 inputs were unchanged (`c9207871…`). Independent reader `45366` closed naturally 0 (`f744ea`) in 57.929433067s at 531,873,792-byte peak RSS. Root accepted the complete partial-BOTH source/object/SDK/engine/package conjunction and all 12 static admission domains in [the full-readback record](../.agent-work/appended-implementation-20261016/runtime-D03-repair-v1/runtime-composition-repair-v1/runtime-allowance-20261018-v1/native-runtime-v1/P01-keyboard-diagnosis-v1/P11-pointer-diagnosis-v1/retired-form-selective-execution-v1/foundation-kernel-role-partial-readback-execution-v2/ROOT-FULL-READBACK-ACCEPTANCE-v1.json) (`eda07c35…`). This accepts the private partial-BOTH behavior: script-origin calculator/tabs/rich text, native echo+ACK, provider 41→42, compiled same-key 17+25→42, matching real `engine.frame`, and ordinary close. Preserve prior factory, metadata, frame and reader failures. Rust partial-BOTH host runtime is Root-accepted: actual runtime `93102` (`c583fc`) and independent full reader `85895` (`01ad55`) closed naturally with status 0. Runtime elapsed 201.523678465s at 3,173,765,120-byte peak RSS; reader elapsed 56.112416225s at 551,481,344-byte peak RSS. Root accepted all 12 static domains, full source/object/SDK/engine/package conjunction, unchanged 124 inputs, and final interpreting/stream rechecks in [full-readback acceptance record](../.agent-work/appended-implementation-20261016/runtime-D03-repair-v1/runtime-composition-repair-v1/runtime-allowance-20261018-v1/native-runtime-v1/P01-keyboard-diagnosis-v1/P11-pointer-diagnosis-v1/retired-form-selective-execution-v1/foundation-rust-memory-repair-readback-execution-v1/ROOT-FULL-READBACK-ACCEPTANCE-v1.json) (SHA-256 `ad701520b6e5843bd7ee2fdc43ebcad7f3e6222921973140369bc6730e442193`). The private Rust behavior includes script-origin calculator/tabs/rich text, native echo+ACK, provider 41→42, same-generation compiled 17+25→42 with a real frame, and natural close. Preserve the earlier `96217` out-of-gas, capacity/inline failures, receipt collision, setup failures, and NC569 suffix-binding failure as history. Separately, Root accepted the retained Rust TUI baseline in [.agent-work/appended-implementation-20261016/rust-retained-tui-application-v1/NC558-v1/root-repair-v2/ROOT-TUI-ACCEPTANCE-v1.json](../.agent-work/appended-implementation-20261016/rust-retained-tui-application-v1/NC558-v1/root-repair-v2/ROOT-TUI-ACCEPTANCE-v1.json) (`7cddbe33…`): optional-provider module `340c0340…` passed eight Node groups, the native provider-present probe, and a real PTY 17+25→42 run with natural Ctrl-Q exit and restored terminal settings. The NC574 edit-loop acceptance in [.agent-work/appended-implementation-20261016/rust-tui-application-edit-loop-v1/NC574-v1/ROOT-ACCEPTANCE-v1.json](../.agent-work/appended-implementation-20261016/rust-tui-application-edit-loop-v1/NC574-v1/ROOT-ACCEPTANCE-v1.json) (`cafce1fd…`) covers two checked-u32 edits producing 43 and 44; each passed eight Node groups, native-provider probing, and real TUI interaction. Compile/pack/inclusive save-to-visible-result-and-close times were 2.049951/0.171581/6.672135s and 1.910936/0.193674/6.346741s, within the 5s/1s/10s targets. These are two warm local TUI samples, not statistical, GUI, or browser qualification. The optional module is Node/native/TUI only; F8 partial-BOTH acceptance remains bound to the older required-gateway module `d6a86fe8…` and its separate record ([.agent-work/appended-implementation-20261016/runtime-D03-repair-v1/runtime-composition-repair-v1/runtime-allowance-20261018-v1/native-runtime-v1/P01-keyboard-diagnosis-v1/P11-pointer-diagnosis-v1/retired-form-selective-execution-v1/foundation-rust-memory-repair-readback-execution-v1/ROOT-FULL-READBACK-ACCEPTANCE-v1.json](../.agent-work/appended-implementation-20261016/runtime-D03-repair-v1/runtime-composition-repair-v1/runtime-allowance-20261018-v1/native-runtime-v1/P01-keyboard-diagnosis-v1/P11-pointer-diagnosis-v1/retired-form-selective-execution-v1/foundation-rust-memory-repair-readback-execution-v1/ROOT-FULL-READBACK-ACCEPTANCE-v1.json), `ad701520…`). QuotePad `3a4d8fa0…` is component acceptance only. Native GUI remains false; eligible public-browser ACK metrics remain unrun. Next is current-source HOST BOTH/editor refresh (36 TUs, 18 archives) using the retained engine and read-only guest SDK; full Foundation 23+3+6, ordinary public-host/browser/viewer and production qualification remain pending; production eligibility remains false. Ordinary rich-web edits remain packaging-only, and compiled edits rebuild only the small portable module.

### Foundation BOTH redaction checkpoint — 2026-10-20 UTC

Root accepted NC505’s central copied-close lifecycle repair: defer copied CLOSE until authentic editor retirement, then run trusted close; the bridge drains only exact owned context retirement while closing. Native Owner/codec fixtures passed 556 checks, the maintained bridge suite 66 cases, and the maintained Owner suite 16 groups / 6,680 assertions. PH27 source is accepted (`1ff1bcb6…`), including exact projection, decoder and four-resource admission. Preserve failed Foundation7 (`31382` / `2f9ab2`, `1c91d906…`) and the three closed readback failures: MR1 stale reader pin, MR2 construction-reader pin, MR3 (`31631` / `e8196b`) logic pin after 54.929799s. NC516’s monitor repair is accepted (`5a141611…`); its controlled GUI restore comparison reproduced old ENOENT and correct new traversal, without proving F7’s hidden original cause. Foundation8 construction `9783` closed 0 (`11253d`) naturally, reusing accepted 883-source preparation (`993bf0fd…`) for 36 TUs, 18 archives and 73 captures, at 668,241,920-byte peak RSS. NC524 corrected only two expected producer identities; real source-chain acceptance and three mismatch controls passed, with the first fixture failure preserved. Full independent readback `41381` closed 0 (`d03a3a`) naturally in 68.782192s at 679,002,112-byte peak RSS. Root accepted its complete source/object/SDK/engine conjunction and final record recheck at `E/foundation-close-monitor-readback-execution-v4/ROOT-FULL-READBACK-ACCEPTANCE-v1.json` (`b3669a5b…`), using request v6 (`38d67a2f…`) and driver (`198ff54c…`). No preparation or build was repeated for readback; retained engine and SDK were unchanged. Fresh PH27/F8 binding passed source/resource admission in 1.392s, independent 123-record physical review, preparation (1.845s) and verification of 23 prepared files. The passive-reader successor admits 60 sources / 1,829,100 bytes. Actual partial-BOTH runtime PE29 (`60761` / `e44020`) closed all writers naturally in 173.947405s at 3,264,040,960-byte peak RSS; its outer caller is 0, but its original controller is 2 and its seal is `capture-failed`. The page-close error is `Kernel terminal-outcome mailbox refused`, with 439.7s case / 732.3s whole allowance remaining. All 123 inputs (139,122,034 bytes) were unchanged. Preserve `E/foundation-partial-both-runtime-execution-v29/ROOT-ORIGINAL-CALLER-CLOSED-FAILURE-v1.json` (`4e11ec32…`). Root source-accepted NC531’s one-hunk central JS repair (`374a8d5c…`): retirement-mailbox probes while closing use last-ready authority. Actual Owner fixtures passed 601 assertions; the original Bridge comparison failed 1/67 while the candidate and maintained suite pass 67/67, preserving refusal controls. PE29’s numeric post-close refusal remains uncaptured. NC535 independently accepted exact preparer base-plus-delta projection for this private partial profile, with immutable F8 facts and a required Root check that final prepared bridge bytes match the candidate; NC528 does not independently rederive that projection. PH28 and fresh runtime binding are in progress without native recompilation. Rust PH27/F8 packaging and four-resource admission are source-accepted (`419bed27…`), reusing the unchanged 30,432-byte Rust module; actual Rust host runtime is unrun. Partial BOTH runtime is still unaccepted; full Foundation 23+3+6, native/TUI/Rust host runtime, viewer and production qualification remain incomplete. Ordinary web edits remain packaging only; compiled application edits rebuild only the small portable module.

The accepted engine 65-case / 12-batch runtime plus both Node negatives, neutral28+6 and separate export remain reused. Actual partial BOTH runtime is still unaccepted; production eligibility is false and the integrated viewer remains unfinished.

Preserve PE19 (`97256` / `a0ee1d`, wrong smoke options), PE20 (`13282` / `68ec3f`, strict wait over safe redaction) and PE21 (`85659` / `e62653`, `Widget generation was reused`). PE21 closed naturally after 67.1744s with 2,415 events, 31 GUI operations, 32 auxiliary records and 30 polls. Only its initial six-widget scene and later empty snapshots were serialized; the failing key/internal call and a restored scene were not captured. NC447 repairs the exact smoke options; NC451's prior empty-redaction wait remains accepted.

Root accepted and integrated NC457's central two-file resumable redaction repair: preserve compiled declarations and geometry, scrub state/callables, hide and disable controls/pages, clear hidden page labels and navigation authority, and retire `engine.frame`. Existing stale-generation, service, navigation and input gates remain. Its real MemoryAdapter fixture passed 41 checks. NC463's source classifier passed 29 inert cases including an actual patched WebAdapter serialization pair; Root froze PH21 with only `smoke_cases.mjs` changed (`325c568b…`) among its 18 selected files. Final same-key 17 + 25 → 42, native echo, provider, frame and ACK predicates and 32-poll / 96-operation limits remain unchanged.

Fresh Foundation construction `E/foundation-redaction-construction-v1` admits 883 source files (two changed, 881 unchanged) and preserves all 19,423 SDK facts. Caller `78949` closed 0 (`d5b9b9`) with 36 TUs, 18 archive create/index pairs, one link and 73 captures; the build reported success, streams closed naturally, and peak sampled RSS was 652,619,776 bytes. Independent full readback `89740` closed 0 (`8b2030`) in 65.790746910s at 700,121,088-byte peak RSS. Root accepted FR2 at `E/foundation-redaction-readback-execution-v2/ROOT-FULL-READBACK-ACCEPTANCE-v1.json` (`87064bf247737b6ae8901067b4f5fca3d10135bc58e16dd0668babf2a022a0bc`), bound to this construction. This accepts Foundation source/object/SDK/engine readback; it does not accept partial BOTH runtime. New Foundation Wasm is 1,711,841 bytes (`77414753…`); the retained engine and SDK were reused unchanged.

Preserve readback `19014` / `f88569` as a failed 10.0869s run: four unchanged helper records still selected the previous source root. The corrected physical bindings passed the actual reader boundary (old records reject, fresh four pass). NC467's fresh 69-input / 54-source PH21 binding passed source/resource admission and independent physical review; preparation `49297` and its independent verification passed. PE22 (`35634` / `f01780`) reached the restored controls and `lhs = 17`, but capture failed on a fractional timer delay: production emits finite binary64 delays while the old observer expected integers. Root accepted NC473's timer typing and bounded failure-context repair; PH22 is accepted. Root also accepted NC471's partial-readback source, which is ready with explicit Foundation6 bindings, but its actual readback has not run.

PE23 failed before runtime acceptance when the bounded output scan observed live `prefs.js` as REG/nlink=0. NC475 is Root-accepted: only live workspace/profile REG/nlink=0 permits three bounded reobservations, charging detached bytes; prelaunch and final closed scans remain strict. PE24 (`89502` / `aa29c3`) failed after 96.042s at 3,293,204,480-byte peak RSS: descendant closure inside the capture helper discarded the controller's original error channels, and no seal was produced. The outer process nevertheless closed naturally (primary 1, one child reaped, no termination or surviving descendants). Its prefix shows `lhs = 17` restored after 31 polls and a later `rhs = 25` request pending against snapshot `rhs = 0`; four timer callbacks include `4019355.9999465942` ms. This is partial evidence only, not runtime acceptance.

Root accepted NC480's failure-only diagnostics and controller phase/clock context (PH23), followed by NC487's smoke-pacing repair (PH24). PE25 (`17764` / `4473f5`) and PE26 (`6601` / `552c8b`) failed the 90s aggregate case-RPC deadline during `runCase`; NC492 confirmed PE26 had 12 polls versus PE25's 30 with the same 21 completed PUMPs, but no wall-time gain. Preserve PE27 (`50489` / `14bec4`) as a closed failed Take-phase assertion; NC497's failure-result admission and NC499's source-reviewed pending-phase correction retain the ticket, content and completion predicates. PE28 (`29097` / `12af5c`) captured auxiliary record 26's complete native report (calculation, tabs, rich text, echo and increment) and record 27's compiled `17 + 25 = 42` and frame; auxiliary records 28–29 describe one observed case with 23 operations / 18 polls. The Worker received a close command at event 3958 and the native CLOSE/free tail reached event 4018 by 228.585s; the prefix stayed stable through 595.249s. The shared 600s case clock expired at page-close with 295s left on the whole-run clock; this detects the stall but does not explain it. The caller closed 1 after 606.290s at 3,088,367,616-byte peak RSS; inner finish reported surviving descendants and no seal was produced. Independent postflight found all 123 inputs (139,088,775 bytes) and the outer owner unchanged. These observations are not runtime acceptance; NC506 independently matched all four closed stream files, all 492 chunks and 4,107 spans in the unsealed diagnostic; the final 14,914 records include a 42-byte timeout reason. This verifies captured observations without a successful seal or full state-machine acceptance. NC505's central close repair is source accepted; see the current construction/closure checkpoint above. NC489 failure-path RPC/collector wall- and CPU-time metrics remain accepted; NC491's PH25/new-owner profile allows only aggregate case and Worker 600s, inner 900s, outer 1200s and cleanup 15s, preserving individual Marionette 15s / Bridge 30s, startup/physical-timer deadlines and all byte, machine, GUI and poll predicates. NC494 passed physical review/admission for 123 inputs. FR2 Foundation construction/readback remains accepted; NC471's required full partial-reader execution is pending. NC501 Rust PH26 source and NC503 full-reader TAKE-phase source are accepted, but no Rust host or full Foundation runtime is accepted; full Foundation 23+3+6 and viewer/production qualification remain incomplete. NC493's E09/D03/D04/D05 schedule gaps and missing static admission require coherent full-family integration later, not an added gate on this partial-BOTH run. Ordinary rich web and portable C/C++/Rust work keeps the 5s compile / 10s inclusive fast-loop targets. Production eligibility remains false and the integrated viewer remains unfinished.

Full runtime caller `88524` closed 0 (`3e81f9`) in 167.2766838009993s: all 65 cases / 12 batches in the direct browser Worker passed, including cases with expected negative outcomes, along with both Node negative controls. All 47 inputs remained unchanged; two owners and two streams closed naturally and the monitor thread joined. Peak sampled RSS was 3,708,030,976 bytes; output was 211,516,169 bytes. Independent reader `21550` closed 0 (`349fae`) and accepted both outputs. Full readback `ROOT-FULL-READBACK-v1.json` has SHA-256 `8c89be49af69c96232c8a49c21eebdace32e39a13a5535f14fd3e4a2efc7f9dd`; neutral-closure readback `ROOT-NEUTRAL-CLOSURE-v1.json` has SHA-256 `d134c763feebb40289186015a0fd7a9efc80de6aa9833b07869db5278fd21d8a`. Runtime caller and independent reader are separate records. This supersedes the earlier failed full runtime `13400` at E09 for current acceptance; preserve it as a failure. Focused negative diagnostic `23995` passed three negative paths / 76 case assertions and remains partial evidence. NC283 fixed the E09 oracle to match the actual native boundary: terminal unknown is retained internally and returned in the owned outer response; this adapter has no inner-unknown body.

NC286's streamed-hash source-record repair is accepted, and the actual neutral request/binding passed. NC289's narrow logical `F01`→`D05` alias is accepted with both original F01 anchors preserved, not weakened. Stage `32630` closed 0 (`c1e42e`) in 10.529789499s, converting 381 source files / 617,388,940 bytes into 76 staged files / 291,929,178 bytes. Independent readback `84839` closed 0 (`43310a`) in 3.290980267s; Root acceptance `E/neutral-execution-v2/ROOT-STAGE-ACCEPTANCE-v1.json` has SHA-256 `7b915500a5afb9658bdd103310f3f1e0d13b2f5e5bb9372663ec3bdea34b9600`. Separate export `71765` closed 0 (`4a00f6`) in 31.191051768s at `EX=E/neutral-export-execution-v1`. Root accepted `EX/ROOT-EXPORT-ACCEPTANCE-v1.json` (SHA-256 `0a990abbd56e9d7717f4d26a6070c6fe069dc8c674db178b43ee388f1521cc36`). Independent reader `52010` closed 0 (`24525e`) in 15.122170330s at 202,629,120-byte RSS; its proposal log is `EX/export-readback-v1-owner/child.log`. It accepted exactly three files / 582,956,175 bytes, verified all four pins, target and paired SDK against the staged payload, and rehashed/postflight-checked the canonical eight helpers and group bytes. Strict-consumer byte/static contract eligibility is true; full integration and production remain false. Preserve the earlier source-test failure and request-size failures as history. The repair preserved all 381 source facts without raising a global cap.

Maintain the fast application loop with ordinary appended-web and portable C/C++/Rust work. Foundation source compatibility is accepted: NC291 v2 controller `ROOT-SOURCE-ACCEPTANCE-v2.json` (`9ba17a4e…`) reuses 30 baseline checks and adds four publication plus two refreshed packet checks; NC294 reader source acceptance is `4da41a7b…` with 12 focused checks; NC295 SDK wrapper source acceptance is `d5810f98…` with eight focused checks. The user authorized the Foundation BOTH host construction, required readback/runtime qualification and necessary scoped repairs. The concrete construction scope is `E/foundation-authorization-preparation-v1/SCOPE-COST-v3.json` (`827b25b6…`). First caller `85997` closed 125 before configure because the retained GUI archive omitted seven current patches. The reviewed reintegration repair produced 728 members (645 unchanged upstream / 83 current integration); four focused fixtures passed, and the previously failing default-group check passed after replacing the three bundled files. Fresh source admission independently verified 883 files with exactly three changed / 880 unchanged and preserved all 19,423 SDK rows. Second caller `57900` closed 125 (`9950ff`) during configure, before compilation: the supplier toolchain defaulted its processor label to `x86` while the verified manifest declares `wasm32`. NC307's project-wrapper repair is source accepted with a real compile-free CMake fixture (one test / 0.172s); it passes the manifest processor through the supplier's supported setting and preserves the strict editor guard and retained SDK. Foundation attempt 3 then configured successfully but caller `75621` closed 125 in the strict compile-database reader, before any target compiler or runtime ran (`E/foundation-wasm-processor-recovery-v1/ROOT-ORIGINAL-CALLER-CLOSED-FAILURE-v1.json`). The reader rejected normal CMake-exported commands because its argv parser requires separate `-MD`, `-MT` and `-MF` flags; the actual Ninja commands contain the capture wrapper and strict dependency group, which the exported rows omit. Metadata-only Ninja command extraction (`E/foundation-wasm-processor-recovery-v1/compile-database-diagnostic-v1/RESULT.json`, `ninja -t commands gui/gui_appended_engine_wasm.js`) completed in 0.010141s without compiling or executing a target. After removing the wrapper and strict dependency group, the independent source+object projection matched all 36 selected rows to the saved expanded Ninja commands; this establishes selection accounting, not successful build-command admission. Preserve the failure and natural owner/stream closure. Root owns NC313's reader repair in a fresh source directory; the out-of-scope baseline write was restored to SHA-256 `7894d8d0488af6c9e2a6259ad448080b4ba7d0e9dbba23d64a79aa6b86d30a23`, and the internal copy stayed unchanged. Next gate is the scoped Foundation retry through repaired reader, then independent readback and required runtime; user authorization covers these scoped operations and required repairs, so no further approval is needed. Attempt 4 (`54487`, closed 125 / `e58f1b`) reached a passed inner result, all 36 compiler invocations, 18 archive create/index pairs, one link and 73 original captures, with natural target closure and unchanged source/SDK snapshots. The original caller still failed outer capture validation, so this is not an accepted Foundation construction. A controlled comparison changed only the producer dictionary insertion order: JSON decoding reordered it, changing `include.cmake` and `c-rules.cmake`; restoring the original order matched all eight installed files. NC323's isolated deterministic-renderer repair preserves the four producer pin checks and passed two real-interface fixtures (0.046s), with independent Root review. The compile-database repair is source accepted after independent strong review and eight focused tests (0.184s); the versioned outer collector cohort passed source review and 13 fixtures. Foundation readback and construction remain accepted: caller `5954` closed 0 (`ecccd5`), Root acceptance `e0a6f68b…`; the live Q/S/SDK/engine/source-object conjunction and full physical input namespace were rechecked. The accepted engine65+12, Node checks, neutral28+6 and separate export were reused unchanged; no rebuild occurred. Partial BOTH runtime is still unaccepted. Preserve PE1–PE6: `20214` omitted explicit prepare; `96051` rejected Firefox’s normal profile symlink; `39894` saw socket inode 0; `97790` and `99824` closed outer 0 with controller 2/capture-failed; `23125` hit the 90s readiness deadline with no durable Worker/native events or cases. PE7 `55402` also closed outer 0 (`bd07ef`) in 5.81498s at 1,964,584,960-byte peak RSS, but controller 2/capture-failed “Actual page failed before ready,” with zero durable Worker starts, native events or cases; all owners closed naturally. The separate approval-review timeout created no process or assertions; its supported identical retry launched this one actual PE7 process and is not another product failure. PH4’s window pending-state fix from NC354 remains accepted. PH5 static observer import (NC365) and fresh v11 binding (`2dddd5b9…`, NC367) were accepted; explicit prepare `23513` closed 0 (`e40455`) and independent verification passed. NC361’s actual tiny-Worker diagnostic `10846` closed 0 (`eb126a`) in 12.379s: awaited top-level dynamic import lost the first attach while `onmessage` was null; static/inline valid observers attached in 4–9ms online/offline, while the wrong-source negative rejected; all owners closed and seven inputs stayed unchanged. This establishes the miniature Worker attachment boundary only; actual production Worker attachment/page readiness remains unproven, and the next page-error investigation NC369/370 is pending. Rust view module and Node vectors are accepted (`20015`, `fab179`; 19,095-byte module `5fb0d48f…`; 2.059s compile, 0.236s Node, 2.337s inclusive, within 5/10s targets). This is codec/module evidence only, without Foundation GUI or TUI runtime. NC357/NC363 source review and NC368 schema-identity regression are accepted; promoted fixtures and the SDK README API entry are retained. Production eligibility remains false and the integrated viewer unfinished. SDK and engine gaps cannot be cleared by resource-reader or forwarding fixtures. Historical 900/1200s maintenance ceilings remain superseded; application 5s compile / 10s inclusive targets and behavioral deadlines remain unchanged. The integrated viewer remains unfinished and production eligibility false. Existing preview evidence does not qualify pixels, trusted input or the retained viewer. The exact `72e6` current Rust module component runtime is accepted; this is not release qualification. NC284's actual six-edit portable behavior loop is accepted by Root (`A/portable-behavior-loop-source-v1/ROOT-ACTUAL-MEASUREMENT-ACCEPTANCE-v1.json`, SHA-256 `e88581d343ee0cadc7a59b6dbea3ddd0d3efa06d78b63adb2fdcade84f780df8`). Caller `11175` closed 0 (`3ec445`) in 23.412836876988877s with 48 natural-zero owners/logs and 24 typed console results, including overflow and the `u32` boundary. Two meaningful `+1` / `+2` edits per language yielded distinct C/C++/Rust module hashes and expected 43 / 44 values. Nearest-rank p95 compile / inclusive-loop seconds: C 1.061971857 / 3.642895028; C++ 0.865868485 / 3.666430836; Rust 1.896808826 / 4.502795587. All met per-language 5s compile / 10s inclusive targets. Peak child-tree RSS was 265,887,744 bytes under 1 GiB; 120s whole / 15s cleanup and 4 GiB disk floor held. The 83 input and 20 SDK-directory facts were unchanged; full-SDK byte verification was reused. Source `30df3cdc…` is Sol `7dc03b7d…` plus Root's disk-floor-only change 2 to 4 GiB; targets were unchanged. This validates only the local retained-console small guest-module component workflow (`be8af644`), not an integrated viewer, native GUI, TUI, Foundation or general statistical performance. No SDK maintenance or full-engine rebuild is in scope.

Current partial BOTH checkpoint: Root accepted PH7 harness source (`E/foundation-partial-both-harness-source-v7/ROOT-SOURCE-ACCEPTANCE-v1.json`, `2afec95b…`), including the generic Worker replay/observer integration. PE8 caller `52659` closed outer 0 (`8ff500`) in 5.17994118s at 1,876,127,744-byte peak sampled RSS, but the controller closed 2 with capture-failed at Marionette sequence 127: `Plain source prototype required`. One real Worker start was captured, with zero native events or cases; owners and writers closed naturally. This is attachment progress only, not partial BOTH runtime acceptance. PH8 realm fix and tests are pending; do not infer a result. Foundation readback and construction remain accepted and reused unchanged; the integrated viewer remains unfinished and production eligibility false.

PE9/PE10 continuation: PH8 source (`b0c82f9…`) passed NC380 review; actual PageRPC/page NodeVM sync/async realm comparisons pass the prior ACK boundary, but NodeVM is not Firefox/browser qualification. PE9 (`E/foundation-partial-both-runtime-execution-v9/ROOT-ORIGINAL-CALLER-CLOSED-FAILURE-v1.json`) caller `29804` closed outer 0 (`b13670`) in 6.641891378s at 1,828,757,504-byte peak RSS; controller 2 reported a generic observer failure before native events. Root accepted PH9 bounded-failure-detail source after NC390 review and four real producer/page fixtures (`E/foundation-partial-both-harness-source-v9/ROOT-SOURCE-ACCEPTANCE-v1.json`); predicates and resource caps remain unchanged. PE10 (`E/foundation-partial-both-runtime-execution-v10/ROOT-ORIGINAL-CALLER-CLOSED-FAILURE-v1.json`) caller `23742` closed outer 0 (`2bf068`) in 6.229234781s at 1,878,405,120-byte peak RSS; controller 2 capture-failed with `Aborted(\`Module.noInitialRun\` was supplied but \`noInitialRun\` not included in INCOMING_MODULE_JS_API)`. Each attempt captured one Worker start and zero native events/cases, with owners closing naturally. The actual cause is first native factory incoming-options incompatibility. Root/NC333 and NC392/394 are investigating a central repair; no repair, build or runtime acceptance is claimed. Foundation, engine65/12, neutral28/6 and separate export remain accepted/reused; viewer unfinished and production false.

PE11–PE14 continuation: PE11 (`E/foundation-partial-both-runtime-execution-v11/ROOT-ORIGINAL-CALLER-CLOSED-FAILURE-v1.json`) caller `9464` closed outer 0 (`e37a88`), after six native events; the ACK reader rejected the missing `liveevent_view` composition export. PH11 repaired the source boundary. PE12 (`E/foundation-partial-both-runtime-execution-v12/ROOT-ORIGINAL-CALLER-CLOSED-FAILURE-v1.json`) caller `39683` (`7e43df`) and PE13 (`E/foundation-partial-both-runtime-execution-v13/ROOT-ORIGINAL-CALLER-CLOSED-FAILURE-v1.json`) caller `68705` (`a4363d`) reached 15 native events before the observer refused dependent-metadata reservation. PE13 controller 2 capture-failed in 8.195424921s at 2,719,985,664-byte peak RSS: `bytes=260598+4096/262144; records=120+1/128`. Each run captured one Worker start and no completed cases; all owners closed naturally. None accepts partial BOTH runtime. PH13 (`E/foundation-partial-both-harness-source-v13/ROOT-SOURCE-ACCEPTANCE-v1.json`) accepts NC414’s bounded reservation repair: 1,024 bytes per span declaration and 2,048 bytes per held output, with the 262,144-byte, 128-record and 16-MiB caps unchanged. Four actual-observer API fixtures preserved exact packet bytes and order; seven boundary controls and finite serialization bounds passed. PE14 caller `42975` closed outer 0 (`602f22`) in 6.702979416s at 2,846,896,128-byte peak RSS, with controller 2/capture-failed before any case: `bytes=78891+1024/262144; records=128+1/128`, call 36/event 76. This crosses the previous byte-reservation failure and confirms synchronous pending-record pressure. Source trace finds no await between engine factory completion and endpoint setup/inspect/configure/start. NC418 owns the private checkpoint repair; no further runtime result is inferred.

Historical profile/runtime checkpoint (PE15–PE18): User authorization for `foundation-original-stream-32m-both-partial-metadata512-v2` remains recorded in `E/foundation-capture-profile-v2-preparation-v1/USER-PROFILE-AUTHORIZATION-v1.json`; preserve the earlier 128-profile failure. PE15 (`E/foundation-partial-both-runtime-execution-v15/ROOT-ORIGINAL-CALLER-CLOSED-FAILURE-v1.json`, caller `73937`/`a2031c`) and PE16 (`E/foundation-partial-both-runtime-execution-v16/ROOT-ORIGINAL-CALLER-CLOSED-FAILURE-v1.json`, `39649`/`b590e9`) passed CONFIGURE (296 bytes plus two frees), then failed controller capture after 50 events and zero cases. PE16 traced engine START call 25/op 1 → RESOURCE_RELEASE call 53/op 11 → denied kernel malloc-credit reservation 128+2; 81,222 metadata and 1,138,672 queued bytes fit the byte caps. PE17 (`E/foundation-partial-both-runtime-execution-v17/ROOT-ORIGINAL-CALLER-CLOSED-FAILURE-v1.json`, `92153`/`ee5a41`) under the authorized 512 profile passed the prior START-count boundary but failed at ADVANCE op 2/call 87: `bytes=261830+1024/262144; records=430+1/512` (128 calls total), with 50 events and zero cases. Preserve each failed run; none is runtime acceptance. PE18 (`E/foundation-partial-both-runtime-execution-v18/ROOT-ORIGINAL-CALLER-CLOSED-FAILURE-v1.json`) caller `55322` closed outer 0 (`56be58`) in 11.752735262s at 2,988,097,536-byte peak RSS, with controller 2/capture-failed, 316 events, six timers, zero cases, no cleanup and natural owner/writer closure. Failure: `Native GUI return is not owned by this actual command turn`; init was event 1, GUI create entered/returned at 315/316 after `await bridge.ready` with the turn null, and ready at event 317 was not durable. Do not weaken ownership predicates. PH18 source acceptance (`E/foundation-partial-both-harness-source-v18/ROOT-SOURCE-ACCEPTANCE-v1.json`; canonical Worker `6273b9c0…`) accepts NC418-v3’s exact-init-object, one-shot `beforeOwnerTask(action, actualInitMessage)` repair, independently reviewed by NC442. It restores command-turn ownership only for synchronous GUI create/ready; queued/startup async gates and watchdog are unchanged. Source checks passed (56 maintained Worker, five observer-init, nine scheduler, two Worker-init, exact projector); runtime remains unaccepted. This history predates PE19–PE21, documented above. The integrated viewer remains unfinished and production eligibility false.
Rust BOTH component (`A/rust-both-application-v1/ROOT-COMPONENT-ACCEPTANCE-v1.json`) and packaging (`A/rust-both-payload-adapter-v1/ROOT-PACKAGING-ACCEPTANCE-v1.json`) are accepted: Root promotion review `1aae61…` confirmed the three promoted source/golden files are byte-identical. The [repository fixture](../tests/fixtures/appended-rust-both/README.md) uses source `521db0b2…` and module `4cf3f3c6…`; the guest component passed 12 view goldens, 38 typed host calls, provider cases and two terminal negatives after one 2.687s compile. Packaging completed in 0.154s without guest compile or engine/kernel build. This remains component/package evidence only: no Foundation Rust, native or TUI runtime, and no inclusive 10-second flow, was qualified. Foundation build/full readback and engine65/12, neutral28/6 and separate export remain accepted and reused without rebuild. Native-only coordination applies; superseded cumulative caps do not apply, and retained-kernel/SDK maintenance, publication and full-engine rebuild remain out of scope. The integrated viewer remains unfinished and production eligibility false.

## Retired-form validation checkpoint — 2026-10-19 UTC

The accepted input-method candidate/capsule remain `a328a82e…` / `b1640613…`. D06 partial runtime `72119` failed in 14.298s at `D06/actual-native-stale-before-effects`; Node negatives, input integrity and natural closure passed. Full 65-case / 12-batch runtime remains unrun. Preserve this failure and diagnose retired-lease behavior before retry.

Source-only evidence: Guard preflight acceptance `aae075f8…` covers 67 canonical plus 65 actual-editor-overlay native fixtures, not Wasm runtime. Editor/native catalogues `705dac95…` / `fa450dac…` passed 52 editor and 342 native catalogue checks. Producer v2 `f6d16bd1…` and retained-form reader source `cd0b84a8…` are accepted. Input package accepts 381 physical files; original `42087` completed the 373-input assembly with producer exit 0 in 6.1968s, then its outer caller failed unchanged-prelink metadata admission before any of six sidecar writes. Preserve it. The narrow prelink correction passed 19 focused checks and independent NC262 review `5e956f40…`; metadata recovery/readback `99258` closed 0 in 3.622s / 2.137s without rerunning assembly.

Selective plan `E=D/retired-form-selective-execution-v1`, caller `11571`, closed 0 (`ecfe23`) in 204.1149s (producer 182.5295725s, peak RSS 611,553,280 bytes); 135,886 physical facts were unchanged. Plan SHA-256 `6d91a5e2319708bb95f98c0d90f826f23a719f00ee6e9fd504b3c0badcfc40b5`. Supported full-plan verification `74432` and independent plan readback `75608` closed 0 in 187.1067s and 11.5511s; command projection passed. Selective build `11620` closed 0 (`a7879b`) in 1,223.009s at 2,449,780,736-byte peak RSS; no new engine runtime has run. Subsequent gates: fresh capsule, causal D06 partial, full runtime/readback, neutral28+6 and separate export; Foundation still needs concrete scope/cost and separate authority. Viewer unfinished; production eligibility false. Native/main-agent orchestration only applies; no board/claim protocol. Justified in-scope retries have no cumulative caps, with machine protections and per-behavior deadlines retained. Source-only acceptance authorizes no SDK maintenance, full-engine rebuild or Git operation.

Independent candidate readback `96481` closed 1 (`0aa58a`) after 17.2525s at the reader’s incorrect all-52-direct-objects predicate. The actual ledger equals the accepted projection: 37 direct objects and 15 archive-only selected objects. Preserve this failed output and the successful build; isolated reader recovery is in progress, with five actual-metadata interface tests passing. No candidate, capsule or runtime acceptance follows from this partial readback.

## Input-method execution checkpoint — 2026-10-19 UTC

Candidate `N` is accepted after build `8260` (closed 0 / `608c02`, 1,243.652298s, peak RSS 2,428,235,776 bytes): main + Shim compiled, 50 imports, five archive copies, zero repacks, one link. Its plan hash is `62b781943494d766688679a148b0a4bc27c63e1693e6bbf2a261eb624698df0a`. Passive readback `81894` and Root readback `90883` both closed 0 with caller 0; Root verified 124,325 files, 8,631 directories and 174 artifacts. Candidate acceptance `N/ROOT-CANDIDATE-CALLER-CLOSED-ACCEPTED.json` is `a328a82ea65e0f58248f86ebc6bbf6e04d04238b7bb3d42c1e3572be0bb6b68e`. The original readback `18669` guard failure remains preserved; its exact-filename correction had independent Sol review.

Capsule `X=N/capsule-runtime-execution-v1` (`58729`) closed 0 with caller 0; independent copy readback accepted 16 distinct copies / 168,789,551 bytes (`X/ROOT-CAPSULE-COPY-ACCEPTANCE.json`, `b1640613384d2d96e0ed326f3a320ce3b821b5203270658499f75fab931b3132`). Preserve the first capsule parent-setup refusal and corrected empty-parent setup; no source-build retry occurred. Full packet `X/RUNTIME-PACKET-CANDIDATE-v1.json` is `308c8e0c…` (65 cases / 12 batches); partial packet `X/D06-PARTIAL-PACKET-v1.json` is `7e5a0eba…`. NC242 independent physical review passed in 3.0676s for all 47 inputs. D06 partial runtime `72119` closed 1 (`8da60d`) in 14.298337s at `D06/actual-native-stale-before-effects` (`53302a1cfb9a6a650a19ac12a2d03b5c7edc296bc1cd0f4066924415f905e586`). Node2 passed; all inputs were unchanged and owners, streams and the monitor thread closed naturally. Full-runtime execution remains unrun; diagnose the retired-lease result before a fresh reviewed retry. Earlier readback failure and accepted reader/case/peer findings remain in NC234/NC218/NC226. Viewer, production eligibility, neutral/export and Foundation gates remain incomplete. User's native-agent orchestration-only override applies; historical board claims and cumulative attempt/time caps are not gates. Preserve per-behavior deadlines, resource bounds and coverage predicates. This checkpoint does not authorize SDK maintenance.

## Current successor-navigation checkpoint — 2026-10-19 UTC

Selective build `66597` closed 0 in 1,232.840s. Independent candidate reader `49372` closed 0 in 90.208s; Root rechecked all 174 artifacts and 129,990 readback facts before accepting candidate `b54335756ec47ca63432f079775a472635af07492210ba17005e578add234485`. It compiles only Unified13 and the metadata Shim, imports 50 objects, copies five archives, repacks none and links once. The accepted 16-copy capsule is `00ed675b…`; no retained SDK, kernel or full engine rebuild was performed. Earlier binding, reader and projection failures remain preserved. The corrected six-test command projection includes the direct Theme link input and matches the actual command ledger; the successful build was reused for that reader repair.

Complete runtime `87839` closed 1 in 172.967s (`558e6c56e4846c84467e40db741802bdc60f051f50fcc1cb8a08b133bd3bd12e`). Seven batches pass, including P11 keyboard (190 assertions), P11 pointer (164), E6a cancellation (82) and E8b (48). D06 in the eighth batch fails the successor-BEGIN observer; four later batches remain unobserved. Node's two negatives pass. All 47 inputs were unchanged, owners and streams closed naturally and the monitor thread joined; sampled peak RSS was 3,717,586,944 bytes. This is a failed complete gate, not runtime acceptance.

Saved-trace diagnosis proves actual old-document CLOSE (peer serial 1443) followed by successful successor BEGIN (1446). The observer incorrectly requires a replacement event emitted only while the old document remains open; it also returns wrapped trace rows where the case expects raw lifecycle events. `D06-CLOSED-TRACE-CAUSE-v1.json` (`27b2fc44…`) records this evidence and corrects the initial extraction that missed successor document 2. The observer/case repair is source accepted (`1e0faaa1…`), with truthful close/replacement evidence and the unchanged 15s wait. Fresh D06 diagnostic `65502` closed 1 in 11.965s after successor BEGIN, lifecycle ordering and successor JSC service passed; its first native successor query returned terminal uncertainty. A second diagnostic, `57112`, changed only Worker exception observation (46 physical facts unchanged) and closed 1 in 14.046s. It captured `authoritative input-method state unavailable`, followed by `v2 current capture unavailable` (`D06-NATIVE-QUERY-CAUSE-v1.json`, `0563a9f3…`). Both failures and natural closure/input-integrity evidence are preserved. A central native-client lifecycle reset is now source accepted (`539a2dd0…`, header `283876d4…`), retaining the accessor’s foreign/expired unknown behavior outside a retirement event. Actual main-TU syntax `77672` closed 0 in 12.709s, peak 1,306,435,584 bytes, with all 2,476 dependencies and 2,173 frozen cache entries unchanged (`f36ca474…`). Earlier resource preflight `8722` refused before any compiler launch; its failure remains recorded. Accepted dependency evidence limits the next build to main plus Shim, importing 50 objects including the repaired Unified13, with five archive copies and no repack. Source-catalogue admission and the reviewed selective producer are being completed before a fresh plan/build/readback and D06/full-runtime gates; there is no new engine runtime acceptance. Accepted source-only neutral28+6, staged-tree readback and separate-export preparation remain unexecuted. Foundation still needs concrete scope/cost and separate authority; the viewer is unfinished and production eligibility remains false. Native subagent coordination applies, without the superseded separate-chat administration or aggregate attempt/time ceilings.

## Prior select-event continuation — 2026-10-19 UTC

The prior paired runtime established the P11 history dependency: pointer alone passed 177 assertions, while keyboard followed by pointer passed the keyboard cases and reproduced the missing input/change pair. Root accepted the central `HTMLSelectElement` selection-baseline repair (`ccabb685…`, acceptance `aee6871e…`), which restores the current-value baseline before committing the immediate user-initiated changed selection. Seven structural checks and 28 extracted-method checks passed. The actual Unified13 syntax compiler completed in 22.451s (caller `82670` closed 0); all 3,170 depfile facts and 2,173 cache entries were unchanged.

Fresh-source readback `80619` closed 0 in 1.2396s for 375 files; accepted preparation reused the existing 861.8 MB reuse tree without a clone. Plan producer `47423` closed 0 in 183.949s, full verification `46790` closed 0 in 204.222s, and independent plan reader `30344` closed 0 in 11.751s. Root accepted plan SHA-256 `2c65205cb0112b94a0e5b5522fed0d08bd52d9e602395bff7d17c25205884029`. The plan selects two fresh units (Unified13 and Shim), 50 imports including main, 52 objects, five archive copies, zero repacks and one link; 129,974 verification facts remained unchanged.

Selective build `66597` is still running with one job, 4 GiB RSS, 24 processes, 8 GiB output/growth caps, 4 GiB free-disk floor, and 14,400s inner / 16,200s outer watchdogs. The invalid relative-path build binding remains preserved; the corrected real-binder fixture passed and v2 is bound. This was a binding failure, not a compiler failure. Root also corrected the relocated adapter's duplicated selective-execution output guard after a real CLI-forwarding fixture exposed it; the fixture now passes under sourceACKv2 (`39ae8403…`). Its private configuration is now ready; build completion remains unverified. No built candidate, capsule, or runtime result has been accepted for this repair. The complete runtime gate remains 65 cases / 12 batches, followed by independent readback; neutral28+6 and separate export remain subsequent gates. Foundation needs concrete scope/cost and separate authority. Aggregate attempt/time ceilings are superseded. Retained SDK/kernel maintenance, full-engine rebuilds and Git publication remain outside this task's authority; production eligibility remains false.

## Latest focused checkpoint — 2026-10-19 UTC

### Current showPicker continuation — 2026-10-19 UTC

The preceding actual runtime, `68992`, closed 1 / `452762` at P11 (`showPicker` unavailable) after four complete batches / 48 passed cases; the full 65-case / 12-batch runtime remains failed and incomplete. Source tracing identifies `SelectShowPickerEnabled`, which defaults false and is not enabled by the prior direct Page startup. The accepted central startup repair (`d86c1384…`) enables it. The real main-TU syntax check passed in 12.313s, preserving 2,476 original depfile inputs and 2,173 cache entries; new engine/runtime behavior is not yet established.

The prior retained Theme build is `54226` / `cd3d23`, independently read back and accepted for its two fresh units, 50 imports, 52 selected objects and 174 artifacts. Accepted preparation produced a fresh 371-entry source package and complete 42,779-file / 861,802,853-byte reuse clone; source/copy owner `66565` closed 0 / `f2ff74` in 32.3448s, with independent owner `21866` closed 0 / `fc97ba` in 17.9191s. Only two cloned metadata files changed; raw51 SHA-256 is `686817b20bb8a311e9ec8c7d72addd455896805cdd6b5010ce3a51ce0a0ae569`, and the exact inverse restores `4ba…`. NC177 Root accepted 390 focused catalogue tests; this is not engine evidence.

The execution directory (`E`) is `.agent-work/appended-implementation-20261016/runtime-D03-repair-v1/runtime-composition-repair-v1/runtime-allowance-20261018-v1/native-runtime-v1/P01-keyboard-diagnosis-v1/showpicker-selective-execution-v1`. The accepted fresh plan is `8750` closed 0 / `4a9cba` (producer 186.625s; outer 194.186s), SHA-256 `6dffb6317a425b782980794271c2f0fe782abd93ec21c1e06f763775579a9746`; full verification `74342` closed 0 / `0130d6` in 174.610s and independent plan readback `9388` closed 0 / `d44063` in 9.12265s accepted all 127,043 physical facts. Root acceptance is `E/ROOT-PLAN-ACCEPTED-v1.json`, SHA-256 `abba25daf821b1267f0669fce7e278d2b5170ce949c47cf29d24d2c92405fc67`. Exact command projection `85028` closed 0 / `f50e5c` in 4.528s: two fresh units (main + Shim), 50 imports, 52 selected objects, five archive copies, zero repacks and one link.

Selective build `21606` closed 0 / `c3e835` in 1,204.591s, with peak sampled RSS 2,438,197,248 bytes and all 127,051 input physical facts unchanged; the owner and log closed naturally. Build receipt SHA-256 is `7d242e23aa78254c9ec143bde2e71aa49def041c6ad7d96f6c639dddc7f4d23d`. The first passive reader `28888` closed 1 / `a8a371` after 30.812s on a stale protected-header donor-root accessor (`bindings`), before publishing acceptance. The original failure and sources are preserved. Root repaired this accessor through the accepted showPicker compiler-root helper; a 0.686s real-metadata check reproduced the old error and verified the exact three header sets across five source roots. Independent NC195 review caught and resolved a stale output-path guard before launch; eight focused interface tests passed. Fresh passive reader `9846` closed 0 / `57f48c` in 89.126s. Root rechecked all 174 artifact identities and the complete input freeze; candidate acceptance SHA-256 is `476393e2498ce17ac9d33dbb8567d67c57741c868bac7674b65a05a10c82a342`. Fresh capsule owner `5578` closed 0 / `3454ac` in 3.480s; independent reader `f4af16` accepted 16 distinct copies / 168,159,769 bytes (`4f040081…`). The bound 47-input packet (`876777fb…`) passed independent physical/configuration admission. Actual runtime `39302` then closed 1 / `a37c03` in 148.697s at `popup.P11.pointer.selection-input-once`; result SHA-256 is `d64e89fe10d6dd31989d7cd63f55321f4d6c5d733132e53aec05c31da3e84425`. Four batches / 48 cases completed; P11 keyboard now passes, while the pointer successor changes `next-alpha` to `next-beta` without its expected input/change pair. All inputs remained unchanged and owners, streams and monitor thread closed naturally; sampled peak RSS was 3,604,119,552 bytes. Full runtime acceptance remains failed. The separate two-batch history comparison `10609` closed 1 / `eb80ff` in 24.128s: pointer alone passed 177 assertions; keyboard then pointer passed keyboard and reproduced the missing-event failure. All 47 inputs remained unchanged and owners, streams and the monitor thread closed naturally. This partial diagnostic supports a selection-history dependency and cannot qualify the complete gate. Root source-accepted the central guarded selection-baseline repair (`ccabb685…`, acceptance `aee6871e…`); seven structural checks and 28 extracted-method checks passed. The original host observer setup failure is preserved. Real Unified13 compilation and engine behavior remain unverified; the new selective lane must freshly compile Unified13 plus the metadata Shim, import 50 unchanged objects and verify direct ownership before the copied archives. Current maintenance watchdogs are 14,400s inner / 16,200s outer, with one build job, 4 GiB RSS, 24 processes, 8 GiB output/growth caps and 4 GiB disk floor. Earlier incidental maintenance and cumulative budgets are superseded; resource protections and behavioral deadlines remain. Do not rebuild the retained SDK, kernel or full engine. NC181 (`8bf32de9`), repaired NC185 (`ef48cb78`, independent NC195 `7b50c69b`), NC187 (`34e3262d`) and neutral NC190 (`8d820f6c`) source successors are accepted. The neutral execution binder NC194 is also source accepted (`1892be75…`); its original local error and subsequent Sol review corrections remain preserved, and no actual neutral binding has run. Required next gates remain causal P11 pointer repair, complete 65-case / 12-batch runtime and independent readback; then neutral28+6 and separate export. Foundation still needs concrete scope/cost and separate authority. Preserve all behavior deadlines and final predicates. The integrated viewer is unfinished and production eligibility remains false. The user's native-only coordination override remains active; no board/session/claim/lifecycle administration applies.

The source/plan prerequisites remain accepted: mixed-origin ownership repair
`bcd60bec…` / `df8d25…`, 51 focused tests, fresh plan `21814` (`b814d4b7…`),
full verification `66465`, independent readback `86972` and real-TU probe
`50041` / readback `81536`. The original failed plan `13522` and probe
`86558` retain their failures. Their complete evidence remains below and in
the continuation plan.

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

The [latest continuation checkpoint](appended-application-plan.md#latest-continuation-checkpoint--2026-10-19-utc)
supersedes older current-state wording below. Source `9d5d434c…` adds four
headers; its implementation body is unchanged. Source acceptance retains
380 tests with zero skips. Real-TU differential `35262` / `43177b`
reproduced four baseline undefined-inline errors and accepted the repair.
Its 224.854s total versus the old failed-build handle-to-result interval of
771.435s is specific defect-feedback evidence.

Preparation `52904` and readback `27213` accepted 369 source files,
12 metadata files and 42,779 reuse files (`910584d9…`). Binder `28640`
and physical admission `50696` passed. Plan `86057` closed 0 / `309554`;
independent readback `93935` closed 0 / `b3df9e`, accepting plan
`70485f92…` (`6aee128a…`) with unchanged inputs and natural closure.
Selective build `40718` closed 0 / `6d4dc7`; independent readback `89476`
closed 0 / `a3c613` accepted all 167 artifacts, 51 dependency closures, six
fresh units, 45 imports, five archive copies, zero repacks and one link
(`1f4feabd…`). Capsule `84784` and independent readback `67884` accepted 16
independent copies / 163,087,928 bytes (`cd3c0372…`).
Runtime `70059` closed 1 / `c5f1fe` in 1.211s at private-helper path admission,
before Node/browser/engine launch: zero cases and batches. Driver preflight
`inputs_unchanged=false` is preserved; independent postclose readback verified
all 47 physical/hash facts unchanged (`39ef3861…`). A two-helper-only binding
passed real loader/configuration and negative checks in 1.757s; independent
review `23060` closed 0 / `a3da89` accepted `754aefa8…`. Fresh runtime
`50492` closed 1 / `f47da6` in 95.915s at the same P01 keyboard-popup
predicate after 38 cases / three batches and Node2. Independent closed-failure
readback `56890` closed 0 / `03feb4` revalidated completed original predicates,
the failed P01 predicate, all 47 unchanged inputs and natural closure
(`d1dc743f…`). A partial observer diagnostic `85730` closed 1 / `d6fe42` in 13.156s;
independent readback `37247` closed 0 / `5f9a47` verified trusted Space
keypress on the focused select, `defaultPrevented=false`, all 47 unchanged
inputs and natural closure (`3bd29648…`). Accepted link symbols select fresh
keypress code and the old theme’s false menu-key policy. The source-derived
actual/proposed theme fixture passed 145 checks and independent review,
within its stated host model boundary. The Space-only override `b6720505…`
is prepared, uncompiled. A distinct Theme+metadata-Shim selective successor
with 50 imports / 52 selected objects still needs source admission. The
13.156s diagnostic saved 82.759s against the full path to P01; no application
loop or complete-gate speed claim follows. Full
65-case / 12-batch runtime acceptance is still open. Runtime `95094` remains a closed failure at P01
after 38 cases / three batches, Node2 and author31. No failed result is
superseded by a source or metadata pass. Application-loop timings, the
integrated viewer and production eligibility remain unverified.

Development work started from `b7aa3234a52ab08250dc2e0901c8dd03dfc5f31f`
with the uncommitted implementation plan and index. Source changes are not a
qualified binary release. [Implemented tools and limits](appended-applications.md)
distinguish current behavior from [the full plan](appended-application-plan.md).

## Focused development observations

The first native supported-wrapper build on Linux x86_64 used GCC 14.2.0,
C++20, the explicit C++ core compatibility provider and the optional binary
profile. The interpreter compiled from its pinned, checked source without a
dependency fetch. ABI/registry/container contracts and real executable sealing,
append loading, expected-mode and corruption checks passed. The first module
suite stopped at an invalid all-zero fixture service schema. After correcting
that fixture, its data-segment terminators also required repair. Neither attempt
established a passing interpreter suite. Final integrated results are recorded
below only after their actual execution.

Freestanding LLVM 24 compiled the C and C++ calculator clients and a C generic
view calculator through `./build.sh appended compile`. Their final bytecode
passed the shared `foundation-guest-v1` validator. The Rust guest was subsequently compiled and executed with a separately retained
Rust 1.84.0 target, as recorded below; the ordinary kernel Rust baseline remains
unchanged.

The bundled website passed 17 direct-file interaction checks in Firefox
153.5.0esr, including calculator directions/errors, stable focused editing,
spreadsheet tabs/formulas/row changes, asynchronous stale-result rejection,
styled multi-node editing, Unicode insertion, undo/redo and responsive layout.
The source-bound receipt and desktop/narrow images remain under
`.agent-work/appended-web-preview-final-q0mzlqg_/`. This is an external-preview
result, not internal-engine, TUI or other-browser execution evidence.

## Verified binary carriers and tools

Two immutable development source snapshots separate compiled and packaging
observations. They are complete source identities, not Git commits or release
certificates:

| Snapshot | Complete tree SHA-256 | Source archive SHA-256 |
| --- | --- | --- |
| Native and browser C++ carrier build | `1e965309868d0e47cb9740abd2ee2cab08352f40d8b6a8e86c55a60f9ab0f434` | `f0f8cd8bd36e6f5ab3f9e1ad8d72d90125b235828ae1dd68e1c792b7ff2a5dd5` |
| Fixed browser bootstrap and packaging | `25f0859d9ddde425f305c28773e1ef399b68a653cf1b8e93c4cc86b5ac3cd724` | `0acc26e41b8dfe3af586eeef0139014eecf27d75e0d8cafe4e790ad2802caeb7` |

The native supported-wrapper configure and specific CMake builds used GCC 14.2.0,
Debug, C++20 and the explicit C++ core provider. Six focused CTests passed without
skips: ABI, registry, container, module, executable kernel and generic appended
GUI application. The kernel test included six real executable cases. Another 49
end-to-end assertions exercised the actual compiled C and C++ calculators,
dispatching 7 + 35 through the native service and obtaining 42, replacing the C
payload with C++, verifying exactly one suffix, and stripping back to the exact
finalized kernel bytes/hash. A real 80×31 PTY edited the generic view calculator,
displayed 42, exited cleanly and restored terminal attributes and file flags.
Python audit hooks prohibited child-process creation during every payload
operation and observed zero attempts. These were development build outputs,
not installed or release-qualified carriers.

The native evidence summary is retained at
`.agent-work/appended-implementation-20261016/native-carrier-e2e/qualification-summary.json`
(SHA-256 `3fd40119a2cb314f91d1ec1cbb575c3960b1b7da40a47583dd3e711f26c0e643`).
It binds commands, source/module/output hashes, six-test JUnit and PTY evidence.
The actual view calculator module was 10,577 bytes, SHA-256
`8269ba360dae403356147af8b76293c5519dc4dd1e9b250c5430fa062593c0a9`.
The earlier actual-module memory-adapter check also passed more than 64
acknowledged calls, including stale generation/base-edit rejection.

An actual Rust 1.84.0/`wasm32v1-none` guest build exposed an archive-link defect:
forcing the complete static archive selected unrelated native members in the
supplier's target library. Simply dropping whole-archive linked the optional C
no-op hooks instead of the Rust application. The repaired Rust route requires
all four application hooks from the C runtime and links the archive lazily.
Actual operation results, rather than link success alone, established the fix.
After moving the target-specific panic intrinsic into the SDK's `abort()` helper,
the final supported-wrapper Rust module was 18,399 bytes, SHA-256
`96714fdafda7f44aadb15ba7c7ebc3593f1a0b27401204110758ab5c611f2a03`.
It passed the profile validator and actual native service execution for
7 + 35 → 42, 1 + 2 → 3 and `UINT32_MAX + 1` → zero with overflow. Removing the
shutdown hook failed with its specific undefined symbol and published neither
module nor receipt. Recompiling C and C++ produced byte-identical previous
modules. The isolated 38-file tool inventory retains the official exact release
manifest/component hashes and compiler/target inputs; no global installation or
kernel rebuild occurred. Evidence remains under
`.agent-work/appended-implementation-20261016/rust-guest-probe/`, including
`insulated-rust.compile.json` and `insulated-runtime/runtime-receipt.json`. The compile
receipt SHA-256 is
`c057903ba0e40051d5efe6f387983bad3b8120304fcc920b8c789e4de247e21a`.
The consolidated findings receipt is
`43587731fc5c39bd43d3e65acc7e9bd983cabe8252b78b62f8607afe8a6ca57e`.

The browser target built with the retained Emscripten 6.0.10/LLVM 24 SDK, recipe
`9c0a7de7b155052360b352c18345583c2ce4a264ec64f6e9e270eeabeb6ffb60`,
manifest SHA-256
`217e8ee79c8f825e52cf92338a841cd7c79836666aaee7cbd1f41ee9e070920a`.
Its first actual Firefox launch exposed stack exhaustion in a repeated-group
base64 regex on the large kernel asset. A bounded character scan plus exact
base64 round trip repaired that decoder, with a large-input/canonical-padding
regression. No interpreter change or C++ rebuild was needed. Packaging retained
the original compiled-source identity separately; all 237 C/C++ source/header
inputs compared identically between the two snapshots.

Actual headless Firefox 153.5.0 on Linux opened the final HTML directly via
`file://`. Pristine/stripped files reported no payload without starting a guest
frame. Both composed and stripped/reappended documents accepted 7 and 35 and
rendered 42 through the generic GUI. Their screenshots matched. The same module
bytes ran in the native terminal and browser interpreter. Composition, replacement
and stripping invoked no compiler and restored the exact HTML prefix. Final
artifact SHA-256 was
`8a9e2b32ba6917f890e184475ca2f8d71fa37346da8a8741f65127814e384507`;
pristine prefix SHA-256 was
`478de8633c907d7893f401fdb58c20146df9559f0e9a1643f6c36e2e310d9d2f`.
Receipts remain under
`.agent-work/appended-implementation-20261016/browser-carrier-e2e/fixed/` and
`firefox-fixed-1/`. The consolidated `browser-evidence.json` SHA-256 is
`49786bbf8e88cb1cd3263c2291d563016bb75229f251c448e571b345e53ab32d`.
This verifies the binary-defined view carrier; it does not
verify an internal HTML document engine.

Independent module/interpreter profile checks on earlier unchanged runtime
snapshot `17710418d0253d15e5251d56c2175807c4dc4fba1c66ecdd051f1e996343a378`
passed native, Node/Wasm and actual Firefox execution. Python/native profile
parity had 41 cases, zero mismatches, plus seven actual SDK module files. Exact
source, patch, checker and Wasm identities remain in
`.agent-work/appended-implementation-20261016/runtime-probe/runtime-evidence.json`
and `wasm-validator/parity-17710418.json`. Those receipts retain their original
identities; later source is not substituted for it.

An earlier focused tooling checkpoint passed 187 appended project/container/ABI-policy/
compile/validator/kernel/supplier/recovery entry cases (the compile suite grew from
13 to 14 cases after the Rust link correction; policy now has 28 cases),
50 CI-selector cases,
20 source-identity cases, 42 GUI-boundary cases, 16 legacy browser-packaging cases
and 11 appended-browser packaging/transport cases. The registered build suite
passed 37 applicable cases; its one native Windows linker case was explicitly
excluded on Linux, not passed. Direct unittest discovery initially selected that
inapplicable case; the maintained platform-aware runner resolved the invocation.
The install prerequisite map was configured afresh and includes the optional
kernel for exact `integration.install` selection; a full installed-package check
was not run.

The ordinary neither-payload C++ configuration passed `core.cli` and `core.store`
through the supported wrapper. Its target graph had no appended runtime targets
and did not enable a C compiler. The insulation audit passed 22 files with no
violations. Documentation links/JSON/practice references passed on a clean
complete source snapshot; the live checkout's unrelated ignored tutorial work
contains nine pre-existing broken links and is not used as clean-source evidence.

## Application provider development checks

The additive `foundation.providers` service and C/C++/Rust bindings were checked
without changing bootstrap ABI v1 or the seven scalar application exports.
On complete source snapshot
`f5e229cdabc9028818b04dcd8907451ed846801ed345205fd4f90a9a2d745699`,
the supported native wrapper passed `appended.abi`, `appended.registry`,
`appended.module` and `appended.providers`. All five provider SDK cases then
passed with zero skips: two exact binding/contract checks and three actual
compiler/interpreter cases, one for each language. These execute registered
functions, owned discovery, errors, replay and ACK behavior; link success alone
is insufficient. Receipts and exact compiler/module identities are retained in
`.agent-work/appended-implementation-20261016/provider-sdk/validation-result.json`
and its `real/` directory.

The final callback/bounds/sequence implementation passed `appended.providers`
on snapshot
`0c250afc06d43bc80781f18d4c95f224d570ad51b69ad8c18c3f2818558988be`.
All three previously compiled guest modules also passed against that runner,
without recompilation. Evidence is
`module-provider-design/abi-bridge-v1/native-v2-executions.json` under the same
ignored implementation evidence root. Later integrated console/GUI tests and
the explicit recursive-entry regression require their own snapshot; these
earlier results are not relabeled as coverage of later source.

The integrated native host check used complete source tree
`79a5b4a6f522a49df30935af0c18c2ebb9ae054575f5b4dec89328d841630321`,
archive SHA-256
`0a3160d30e01a8b7838ce25fa21db5e8bade7b45561928d36caa1fd18374eafe`.
All seven selected ABI/registry/container/module/provider/kernel/GUI suites
passed with zero skips. Provider tests cover direct recursive entry rejection,
shared GUI event ordering, replay/ACK, failed presentation recovery, closed
adapters and exception-safe ACK. The separate console invocation ran 13 cases,
including all three retained C/C++/Rust provider modules, default/explicit
operations, successful and error responses, requirements preflight and malformed
arguments. No guest module was recompiled for these consumer checks. The retained
compiled view calculator also passed actual edits, addition and acknowledged
transactions against the new native GUI host.

On that snapshot, tooling discovered 197 cases: 194 executed and passed, with
three explicit SDK-dependent compiler cases skipped in that invocation. Their
separate actual SDK evidence is recorded above; skips are not passes. All 50 CI
selector cases, 42 GUI boundary cases and clean-snapshot documentation checks
also passed. Exact commands, identities and logs remain under
`.agent-work/appended-implementation-20261016/provider-integration/`. A receipt
serialization error after the tooling tests completed was repaired from the
complete saved runner summary without rerunning or relabeling tests.

The provider-capable browser kernel was compiled and packaged from that same
original snapshot in optimized Release mode (`-O3`, the normal project's
`ASSERTIONS=1`, and `-lexports.js`). Actual Wasm exports contain
`gui_web_providers_v1`, returning `65536`. The production factory SHA-256 is
`a12de2659a065849bed177eaf335ef71bc16203e9dec3ad253b3faf283dc1d25`;
Wasm SHA-256 is
`efe1aca88f73049a1dee75f9066cf96ec41f1368e464246caa9e6dfac36af781`.
Direct-file Firefox 153.5.0 produced 42 after editing 7 and 35, both before and
after byte-identical recomposition. Strip restored the exact prefix
`3ad6397ac20b2ef89f2f0c125a58b2980bd734c6b647ebe90c47d696248b1acd`.
No guest or kernel compiler ran during packaging/replacement.

The first registered GUI Node test failed before assertions: its CommonJS
generated `.js` runner inherited the production directory's ES-module policy.
The unchanged JavaScript/Wasm passed a private `.cjs` launch. The permanent
test-only CMake suffix fix was then staged as separate complete source identity
`609ebd1ef309c2abaf5d00d0b304e687e239c3bc07dcde2c56ec3a5f02684939`.
Only the test was relinked; both registered provider and GUI Node tests passed
with zero skips. Production JavaScript/Wasm remained unchanged and retain their
original source identity. A separate optional external C fixture Node setup
failed before assertions; optional external C++/Rust Node cases were not run.
They are not credited as passes. Native execution of those exact modules is
recorded above.

Complete original and private SDK inventories and bytes were rechecked after
the build: all 19,425 files matched, with no hardlinked regular-file identities
between the trees. The consolidated receipt is
`.agent-work/appended-implementation-20261016/provider-browser/evidence.json`,
SHA-256 `da4aab9b4b5cfdcaf7844c450ab3c736c9a3bcef142d00b96c4f12ef9dd828a7`.

## Same-document projection utility checks

The unconnected C++ semantic projection utility first passed its focused native
test on tree
`19aa464663ef0288e2395117acf7ba4d00e2c0be35d92d9df7b95c94eb993357`.
A subsequent bounded probe demonstrated that valid zero-width text could cause
about 4 GB of repeated measurement input. The implementation now enforces a
64 MiB work budget before line reconstruction, preserves the retained prefix and
marks the view incomplete. The actual counting-callback regression stops early
if the budget is violated; it does not execute an unrestricted multi-gigabyte
timing test. A large ordinary-text case still must complete.

That fix passed the supported focused native test and the optimized Wasm/Node
test with zero skips, on repository tree
`1827e3ffc856a17b7d25c3274439f2b0a9aabcb212ae0474b665ca4905f5d2e6`,
archive SHA-256
`046d3e15038e05ffda27fa36b794d901bb61ce9c4168c3aea4e12810e2753fdc`.
The wrapper's separate combined source identity, including the verified extracted
GUI supplement, is
`08be2bbd6a21b2c7a08be65f68802b1775f32eaf0a2bb8a399e1fe73a6aeffc4`.
Only the new utility, test and boundary prerequisite built; no retained kernel,
engine, interpreter or guest module was rebuilt. The Node test took 1.87 seconds.
The private SDK remained byte/inventory-identical. Its receipt is
`.agent-work/appended-implementation-20261016/provider-browser/document-receipt.json`,
SHA-256 `7f54cf61ee83230119a67cf84f17d0464af538b6ab3d78951a8a3be060b2729b`.
Native logs are under `document-integration/`. These tests exercise projection,
source ranges, actions and bounds; they do not run WebCore or establish a
connected HTML TUI browser.

## Semantic codec and controller checks

The first combined codec/controller snapshot
`80fa9257ce4b352e005531ef6f8e2400fcb145dce55bd5ba7c9181d065c9d498`
passed both focused native tests with zero skips. Review then identified valid
producer cases requiring support: empty visibility-filtered output, several
visible element roots and a full text budget with separately emitted tag names.
These were repaired without synthetic node IDs or changed UTF-16 ranges.

The updated three native tests passed with zero skips on source
`0ae9ff049606ad233483fe11bea38fd908a8351aa8b496efe194ffba1d91d888`,
archive SHA-256
`b07f0516626934bd6c984bde96e3d662f1ce007fedaecad35562e8c04b19693f`.
The projection, codec and controller tests took 7.72, 0.47 and 0.04 seconds.
They cover actual producer-shaped JSON, bounds, selection offset kinds,
degradation, queued-action revocation, exact-version requests, unknown-outcome
resynchronization, presentation retry and empty/forest transitions through the
real terminal adapter. Raw finite DOM caret coordinates outside GUI bounds are
retained as metadata. Only document/boundary/test prerequisites built; no engine,
interpreter, kernel executable or guest was compiled. Exact receipts remain in
`.agent-work/appended-implementation-20261016/document-controller-integration/`.
These are disconnected component tests; they establish no live HTML TUI browser.

The same three tests subsequently passed in optimized Wasm/Node, with zero skips
and four-byte pointers, on that unchanged source/archive. This includes the
codec's actual floating-point `from_chars` path. The supported build took 191.55
seconds with two jobs and selected only document/boundary/test prerequisites;
no engine, interpreter, host kernel or guest compiled. Complete SDK inventories
and retained production outputs remained unchanged. The receipt is
`provider-browser/document-controller-receipt.json`, SHA-256
`ae87b618d8e102fe60dbbf6cafa1659494275b80a057f7dca9dd745889e0de7e`.
A collector incorrectly assumed the boundary was an archive library after the
tests passed; correcting that evidence query required no rebuild or test rerun.

## Queued website service transport checks

The two new native transport tests passed with zero skips on isolated source
`5222f064ae8ed0b6baf7a1508092fefd5bdfec77c0424232b3744f89caeda682`,
archive SHA-256
`be1e982e36c01f613193a5e789cc5f5c6a366df413e0cd1f89fe02158785bf79`.
This source overlays the transport, its tests and CMake wiring onto the preceding
projection snapshot; the separately changing JavaScript facade and semantic
decoder were not included or tested by this invocation.

`appended.web_services` exercises owned request/completion values, separate
native ledgers, deferred engine callbacks, real module-provider dispatch,
discovery, replay, cancellation, acknowledgement and closed/uncertain outcomes.
`appended.web_services_native` links and executes using only the transport and
value-ABI libraries. Its complete Ninja command closure excludes the module,
provider and interpreter libraries; the linked executable has no defined
Module, ModuleProviders or wasm3 symbols. This proves the transport's independent
link closure, not a configured rich web-only kernel.

The initial native build failed before assertions because a test helper named
`exchange` lost overload resolution to `std::exchange` for a temporary argument.
Renaming that helper repaired the test; runtime implementation was unchanged.
The focused retry built only affected test prerequisites. Receipts and the
link-closure evidence are under
`.agent-work/appended-implementation-20261016/web-services-integration/`.
Neither test enters WebCore or establishes an internal-engine service binding.

The website facade subsequently passed its registered Node test: 19 cases,
zero skips/cancellations, including Buffer/typed-array ownership and simulated
allocation failures. The facade and fixture were added as source
`46cb8bfbb0e1b6b1db72de0d44b1e776ce8cb5a5a9c0ea3443d0b64d2221daa8`,
archive SHA-256
`09465634013e756dfa9aef33d957a0eb1b9b5ac2f3b5cbcddd1b97060385c3dd`.
Its C++ inputs remain identical to the preceding native test. This also passed
both optimized C++ Wasm/Node transport tests with zero skips. Actual four-byte
pointer compilation preserves the native-only ABI/transport link closure;
the other test deliberately includes provider/module/interpreter prerequisites.
The SDK and retained production kernel outputs remained unchanged. An initial
Wasm invocation failed before configuration/assertions because the core-only
Wasm selector was absent; adding `--gui-backends wasm` corrected the command.
No GUI, engine, host-kernel executable or guest compilation was selected.
The consolidated Wasm receipt is `provider-browser/web-services-receipt.json`,
SHA-256 `7b48b4ad5ba5080a882d5a29a510214476606c28c2eb62f81aaf687ca78c040d`.
The JavaScript fixture uses a fake admission adapter, not a live HTML engine.

## Counter payload and browser-adapter development checks

The new `src-bin-appended/c/provider_counter.c` example, SHA-256
`3e18eb4bceaa9e33a0359b44f3c2da62bf50ddd1b2c84b0638df6e4a56a4bf3c`,
compiled through `build.sh appended compile` with the retained three-tool guest
SDK in 4.19 seconds. Its 8,695-byte module SHA-256 is
`4ae62889185dbf52dba6b327c135b644cce5b1320d04aa3c0c610696b6cdc19f`.
The existing native provider test's `--external` path passed discovery, actual
invocation, identical replay, conflicting retry, acknowledgement and retirement
against that module in 0.04 seconds. All input, SDK, binding and retained runner
bytes remained unchanged. No kernel compiled. The complete commands and hashes
are in `counter-example/execution.json`, SHA-256
`59dfa3da0d6a5df0064b457c35d480a86725cbdc1856b2b101d3d5e64018722c`.
This establishes the C provider, not the pending internal-engine connection to
the website's service panel.

Independent recovery review then demonstrated that file macros could embed the
compiler's random scratch directory. The compiler now remaps source/binding/SDK
paths, fixes snapshot timestamps and controls the clock environment. Two actual
supported C compiles used identical main/header bytes in different physical
directories, source timestamps from 1980 and 2030, and opposite ambient timezone
and `SOURCE_DATE_EPOCH` values. Both retained file/base-file/date/time/timestamp
macros and produced identical modules and compile receipts, with no private path
in the module. They took 2.69 and 2.45 seconds; module SHA-256 is
`c801a94641a5d3e54359f964c1ab880d37fdf09ec4989b580b8d7a10ac880a40`.
Compiler helper SHA-256 was
`3dc79626eb698973169d959748a975f78493240e8df00bee3411364d88235a42`.
The original failing evidence was preserved. The repaired probe receipt is
`qualification-independent-review/determinism/evidence.json`, SHA-256
`865ddac348596aeb27945d6ff510e22654d394c7c6b4f52fa5a46e098025545f`.
These are two compiler reproducibility checks, with unchanged SDK bytes; they
execute no guest and establish no Rust, kernel or release qualification.

A separate physical development check exercised the browser qualification
adapter's direct-file boundary with the unchanged retained calculator carrier
`8fa5945d808669a1f2f94b569972d0a79e02cbb80570b10cd3e452fa69aa11a7`.
Firefox 153.5.0 passed the enforced-offline positive control (`NS_ERROR_OFFLINE`),
sandbox check, edits of 7 and 35, result 42, normal quit and natural complete
process-tree join. Two earlier attempts rejected shutdown because Firefox's idle
forkserver survived the primary process; both failures and successful cleanup
are retained. Disabling that optimization in the private test profile resolved
the probe without weakening process-join checks. The physical receipt is
`provider-browser/composition-browser-design/physical-2/receipt.json`, SHA-256
`daa0b5393b01046dd948e5f4281308f80b387deb5aa1b1e596a662b5a83b7716`.
This is focused development evidence, not an executed composition policy or
release certificate. Chromium remains unsupported by the current adapter.

## Portable forms and surface policy checks

Two later isolated snapshots passed the supported native Debug and optimized
Wasm/Node checks on 2026-10-16. Each invocation selected exactly one registered
CTest test, with zero failures or skips. These are portable component tests;
they establish no engine-backed native forms, connected GUI/surface adapter or
browser execution.

The typed forms/draft utility, `appended.document_forms`, used the 910-file tree
`92cc392d880104f4a76746f4087b5dc31eabc3223a9d19a25e1403b96a92a632`,
archive SHA-256
`2696ba8912f057e12e5266ac74de43245f3753c026fef654c5db2cc57d39deeb`.
Its 14 unconditional test functions also ran in the optimized fixture; they are
not 14 separate CTest tests. Native and Wasm test times were 0.0064 and 0.0794
seconds; complete supported commands took 8.55 and 81.32 seconds. The selected
Wasm closure contained forms, ABI/registry and the fixture, with only the forms
and value-ABI archives. Original receipts are
`document-forms-integration/native-run.json`, SHA-256
`c2909f293ec8ab5ec241877c03c345a7f109c0ba3c4863c51ae45993baedea05`,
and `provider-browser/document-forms-receipt.json`, SHA-256
`499e48c24a64d79115199c95a9d9cae88040463d56661eed107ef2db36531c94`.

The generic surface policy, `foundation.gui.surface`, used the 913-file tree
`5db8de9a315c0a92220684d1685b2723b07c1d853971863fc4b5f7c28f54f48c`,
archive SHA-256
`ebe4f61b036c25286f219ceba8547300b26d9e70b8804fc33ff754d705345f82`.
Its eight test groups cover policy transactions, identities, input, composition,
popups, clipboard and bounds. Native and Wasm test times were 0.0039 and 0.0667
seconds; supported commands took 4.92 and 63.24 seconds. Only surface policy and
its fixture compiled, linking the independent surface archive. Original receipts
are `surface-integration/native-run.json`, SHA-256
`c18d3a1a615d147851009a1400926783cf3593e41e24f2a1927ca61fd70572f4`,
and `provider-browser/surface-receipt.json`, SHA-256
`84a271692da54335508d59cc6a81b3781ab5c69520eb0773052a94c939a80574`.

The surface allocation gate covers ordinary scalar/array `new` around
`noexcept` commit and result movement. It excludes direct `malloc`, does not
explicitly replace aligned/nothrow overloads and has no positive interception
control. An unexpected allocation inside `noexcept` would terminate; the actual
test process exited zero. This is partial gate coverage, not a comprehensive
allocation-free proof.

Native commands used GNU 14.2.0, the explicit C++ provider and binary maintenance
profile. Both Wasm commands used the retained Emscripten 6.0.10-git SDK and Node
v24.19.0, `-O3 -DNDEBUG`, compile/link exceptions, normal `-sASSERTIONS=1` and
four-byte pointers. Their `--gui-backends wasm` selector did not enable GUI.
The SDK recipe/manifest identities are the exact pair recorded above; both
19,425-file original/private inventories and retained production JavaScript/Wasm
remained unchanged, with zero original-SDK invocations. The binary configuration
still declared unrelated VM targets and verified pinned wasm3 source; selected
compilation included no interpreter, engine, host kernel or guest module. These
results establish neither physical adapter input nor connected forms/surface
presentation, carrier packaging, a platform matrix or release qualification.

## Retained-engine integrity and entry checks

The [retained-engine tools](../third_party/appended-engine/README.md) passed 50
focused cases on Linux in 2.278 seconds, with zero skips or exclusions. The
manifest helper SHA-256 was
`6807d4471349f0bb8972ea7dbc257c6b8c8b79530ee32f9dcbca84750680952a`;
the group/export/restore helper SHA-256 was
`c04d7de7bcf5387eec890533af314cca3e999a55f1b6dc66d49a3a52581a842e`;
the test SHA-256 was
`8aa9936ae728c98ff8616442ca852bc70ed31a99c287eeccd6231a694a0f9140`.
The source freeze, `engine-build-integration/STAGE-A-V2-FREEZE.json`, SHA-256
`8a95d7c0b0f525c07dc2911272df32dec74315f388bccbd8193fe96f866bfe5b`,
binds exact source copies and `tests-windows-adapter-v2.json`, SHA-256
`f47c65f33b138ff750aa0be2e8b1e45cafc1e07ae4dcd557150d36d33f0b8c10`.
The preceding 33-case Linux receipt retains its original source identity.

The fixtures check strict source/binary/checksum binding, directories and modes,
corruption, pins, passive CLI behavior, private restoration, reparse rejection,
no-replace publication and identity-bound cleanup. Windows mode/reparse/move
branches were simulated on Linux. Native Windows junction, competing
publication, locked-file and filesystem-visibility behavior remain unexecuted.
The fixture assets are inert markers, not engines. Success means retained byte
integrity only; no real production engine recipe, provider ABI, runtime behavior
or kernel capability was qualified, and no engine/kernel build or download ran.

The separate root entry report, `engine-entry-test-report.json`, SHA-256
`2ee28a2d3ad93ff552af0c5686a219a5c0c27dcf040a810921a4620d70a414d3`,
records six passing Linux cases with no exclusions. These mock dispatch and
early failure, including `engine-sdk` routing before native tools and refusal of
unavailable rich-web maintenance. The report has no immutable source binding.
At documentation time, `tests/test_appended_entry.py` had SHA-256
`62fcc363893ca2db0ea3c8be6224aac339a6e4053078bd4135f51b07993392ba`
and `tools/build.py` had SHA-256
`20804970b42cb247502d6c9ceaeecb02b6d2965532b3cbedc56e4561a2f39c52`;
these observations do not retroactively bind the earlier run. The separate
frozen SDK record also retains the actual successful
`./build.sh engine-sdk --help` invocation; it started no producer.

The subsequent selected-profile entry checkpoint passed ten cases with zero
skips/exclusions: `engine-entry-profile-final-report.json`, SHA-256
`f37ef79007b27d8493aff843cf0ef3403673ac3938dc6cc9d56f4b61ddc5eeb6`.
That report retains its earlier binary-maintenance admission behavior; it does
not claim the later rich admission route or an actual rich kernel build.

## Rich-browser integration tooling and component checks

These later observations retain separate source identities from the preceding
214-case composition-tool group, 50-case retained-engine integrity group and
earlier entry reports. All paths below are relative to
`.agent-work/appended-implementation-20261016/`. They are development evidence,
not production engine or release qualification.

The strict consumer passed 37 cases with zero skips/exclusions in 0.548 seconds;
the separate pure rich producer passed 29 in 1.971 seconds. Their source/API
freeze is `contract-review/rich-producer-design/IMPLEMENTATION-HANDOFF.json`,
SHA-256
`390d1be606194dc7969b90cd58a7013c6d6192dd33d547bbc04f86af47d36a90`.
The original reports are `consumer/checks-4.json` and `producer/checks-2.json`
under that handoff directory. Consumer source SHA-256 is
`6f15dbb76ea43209c2d6853788af9fec42ac9d21809708006533fa40d2bbc4f8`;
producer source SHA-256 is
`dad9e006825b84f37a6651c388783a316495b135d7bc57fef70bf21744818fd5`.
The fixtures exercise four independent pins, typed static Wasm facts, immutable
owned evidence, runtime eligibility, compiled-profile receipts, exact asset and
notice closure, canonical prefix verification and append/strip/reappend.
Build/SDK/network sentinels observed no launches. Explicit parser fixtures remain
production-ineligible, including with `--developer-unqualified`. No real neutral
engine group or Foundation runtime receipt was generated.

Later root invocations passed 29 rich-producer cases against the then-current
host inputs and 19 separate surface-bundle cases, with zero skips/exclusions.
Reports are `rich-producer-current-host-report.json`, SHA-256
`39a4bd88b75e474ba6f45916c41a8c63b60dc9f7922f30a74542bfbcc529a5df`,
and `surface-bundle-current-graph-report.json`, SHA-256
`170384d5ddbc88fab833fbd9a31b41759dd38622b885cb3d07a48898702a4531`.
The bundle tests include actual retained renderer patch assembly; they do not
execute an engine or establish physical input. These outcome reports have no
complete immutable source binding and do not supersede the original frozen
consumer/producer receipts. The old binary producer inventory and child graph
remain distinct from `renderer_surface_child_bundle.mjs`.

The extended supported-entry suite passed 20 cases with zero skips/exclusions:
`rich-admission-route-final.json`, SHA-256
`3d5f37c737245b8aa45709de86d2fb94df655d9098e4a98be40b61dc0d3ffdc9`.
It covers all four pins, exact target/SDK forwarding, selected profiles, early
ineligible-input failure, changed-input rechecks and pure payload dispatch.
Direct-CMake tests use a compiler-free fixture. The report is an outcome record,
not a full frozen-source receipt. Earlier six- and ten-case entry runs retain
their original identities; their counts are not relabeled as twenty.
The later dangling-project-configuration correction passed all 22 entry cases,
with zero skips, in 0.999 seconds. Genuine configuration absence retains ordinary
build admission; a dangling link fails before supported-wrapper job/tool selection
and is also rejected by direct CMake. The direct-CMake fixture enables no
languages. Its outcome record is `fork-consumer-audit/fix-report.json`, SHA-256
`9cb1cb03245b669912e7df79a76ba282d614cd5dfe9ab1ee5f348e62e7a8a664`;
it records the exact three corrected source hashes separately from earlier runs.

The preceding four-mode consumer check created independent local forks, configured
all four modes, and packed the three payload-bearing modes. A repeated
both/web/binary/neither/both composition chain and stripping preserved the exact
synthetic kernel prefix and removed stale components. A poisoned tool search path
recorded zero configuration, compiler, linker or install invocations. This is
packaging and fork evidence using synthetic ELF/guest fixtures, without executable
startup or rich-engine integration. The original source freeze and commands are
retained in `fork-consumer-audit/completed/report.json`, SHA-256
`06695d39d6f09840a6ac24756b627d1da4141f9edf2b6121e811d839f2773ba1`.

`cmake-graph-split/RESULT.json`, SHA-256
`16a4331354f962eb4bf71c4435f09502d4563244a7da8e732ba9c13f070a6b43`,
records fifteen `LANGUAGES NONE` mocked graph scenarios on its five recorded
CMake source hashes. They verify absent optional graphs, web without Module/VM,
the optional both leaf, preserved binary closure and rejection guards. No
compiler, SDK or engine ran. Later GUI CMake edits are outside that snapshot.
Actual wrapper admission verifies before build-program discovery; direct
production CMake verification occurs after compiler initialization and before
the optional graph. No actual rich maintenance build has passed.

The stricter retained-source CI selector separately passed 58 cases with zero
skips/exclusions in 49.828 seconds, recorded in
`contract-review/ci-changes-1.json`. It requires the authenticated full descriptor
for profile/components/baseline-ABI reuse; partial source inventories cannot
grant eligibility. Without actual package requirements the CLI explicitly
reports `package_requirements_checked=false`. This is distinct from the older
50-case CI observation and does not certify a concrete composition.

The supported native provider-helper integration passed 25 registered CTests,
zero skips, on complete source tree
`89acc8f6668f092afb7013a3b133a9e026d093adabe327e85b024d3ff3bd9ffa`,
archive SHA-256
`b588a91624950ee5ff2f9af29fd01df91d69e0657998c578508e0bfa03904a15`.
Its freeze is `provider-guard-integration/PROVIDER-GUARD-INTEGRATION-FREEZE.json`,
SHA-256
`3a461b50206413ddf27147cd33a225172b07684fc82b1003de79b9531f14e1ac`.
Only generic guard/adapter fixtures compiled; private engine/host owners were
fakes and the unbound getter remained `UNSUPPORTED`. No actual WebCore provider,
native DSO, copied Wasm composition, kernel, guest or interpreter was built.

The supported native forms/controller integration passed two registered CTests,
zero skips, on tree
`7cb46f04ba947cc583c5b9bc5657460c28fdc371956892371bae82df50f8fb53`,
archive SHA-256
`2d38b3ab958170aa03460f309d37c0c6faa9a81a8d1e07b9bdf9913fb3d7d253`.
Its freeze is
`document-compositor-integration/DOCUMENT-COMPOSITOR-INTEGRATION-FREEZE.json`,
SHA-256
`677528e7214fedf3be7289bad692c1f08184cfffd713c20e1d67df176158fcb6`.
The real retained terminal adapter consumed mocked native/document replies;
only nine ABI/registry/forms/document/fixture sources compiled. Later
unknown-completion fixes changed compositor/test bytes and passed 27 standalone
scenario iterations with no skips, using strict C++20 and the real terminal
adapter: `html-tui-design/forms/compositor/unknown-completion-check-20261016/FINAL-UNKNOWN-COMPLETION.json`,
SHA-256
`a2bcbe7f39163662167145e387d0751d02d6519a9c6dca3a2e26852aa11adddb`.
Those corrections are included in the later eighteen-test snapshot below;
the earlier two-test receipt is not reassigned to it. Neither component check
establishes connected HTML TUI, real native form actions, a physical PTY or
engine-backed presentation.

The actual native engine-owner fixture passed sixteen groups; its web partition
linked with zero Module/VM symbols. Separate App/host web/both v7 fixtures passed
the compiled-profile marker checks. Their original evidence remains
`provider-browser/engine-kernel-bridge-design/IMPLEMENTATION-HANDOFF.json`,
SHA-256
`41dc4c295686c247c394116181c403df2e2eaf0f737046338a21cc234631cf53`,
and `provider-browser/engine-application-implementation/FINAL-v7.json`.
Later Browser lifetime/composition changes passed eleven strict C++ runtime
groups with actual retained/patched GUI headers. Explicit own-Wasm lookups
passed sixteen Node Worker/suffix-verifier cases using fake factories,
dispatchers and allocators, including eager Blob lookup and revocation. The
unchanged copied bridge retains its separate 39-case result. The addendum is
`provider-browser/engine-kernel-bridge-design/IMPLEMENTATION-ADDENDUM-own-lookup-browser-composition.json`,
SHA-256
`1c19bb77bf8cda270fd772e7d606efde73d82c9b6d03f55a2225906f60813969`.
The earlier App/host v7 result uses the older Browser header; it does not cover
the later header closure. None of these fixtures executes the actual neutral
engine, C++ Wasm cross-instance binding or complete browser application.

The supported Linux x86_64 GNU 14.2 Debug wrapper subsequently passed all eighteen
selected CTests, with zero failures, skips or disabled tests, on the 991-file tree
`a52336f7047baa372c2e49808561fd3e93a9d25528be83ad689d775143c495bc`,
archive SHA-256
`a38e928c85206c57d60b40de9ae99d4c8ffa164dc03351f549516d6d3812842b`.
The frozen receipt is
`engine-gui-graph-integration/ENGINE-GUI-GRAPH-INTEGRATION-FREEZE-v2.json`,
SHA-256
`63a0e99697f3509cee75fdf24da97403c5423334cd72930cb4beac6fbf6361bc`.
This covers the generic owner, web/both App/host fixtures, Browser lifetime,
surface/renderer contracts, copied bridge/Worker and forms compositor. The
web-only owner and application command closures contain no VM sources; actual
defined-symbol checks found zero module-binding, Module and wasm3 matches.
The combined fixture deliberately compiled and exercised the actual optional
module/provider/interpreter leaf. A source-identical output-retention-only
two-test operation captured all 39 bridge and 16 Worker TAP cases passing with
zero skips, after the main JUnit truncated their stdout.

These are native and Node component fixtures with mocked engine/native replies,
not a real WebCore provider, Foundation Wasm build, browser/PTY host, guest build,
SDK consumer or platform/release qualification. The source archive and all 66
recorded build products remained byte-identical. Four active documentation files were captured once as
narrative observations, not current-document identities. The subsequent
read-only-values compositor change (`4c3c9c509ebcf4bed62542dffce9102a8d4f1b0ac7b96a5d6dc63bbc4171e749`,
test `67cc4e59e9b0fb1385578b4531b209fa3b50eeae61c95038d9f3c46e6a51cf49`)
is outside this snapshot. Its single supported
`foundation.gui.appended-document-forms` rebuild subsequently passed with zero
failures or skips: 25.813 seconds for the operation, 0.786 seconds for the test.
That 991-file tree is
`51d46d0210d3351365db9472b3db28ec0eed4b8b0b619e6eb23d6479d0f2c67c`,
archive `8bfe2408523fb842695e1702f6537807f626661c8462f6dce7e715572c8f33aa`.
It differs from the eighteen-test source by exactly those two files. The
operation built eight component/test objects, six archives and one executable;
it built no kernel, VM, guest or engine. The receipt is
`document-readonly-values-integration/READONLY-VALUES-INTEGRATION-FREEZE.json`,
SHA-256 `43de71053fa8ae00b7576b6649d3dec4b3ec69a4b5ffeb65d51cad96eeeffbc5`.
The eighteen earlier passes retain their original identity.

A separate real Firefox 153.5.0 surface probe passed exactly two affected
gates: balanced pointer press/release on first native iframe focus, and capture
outside the owner clip. Receipt
`browser-surface-design/pointer-focus-fix/firefox-05/result.json` has SHA-256
`a69fe9272093d8ce4c5082ac2b10b2169fa64202bd7ff2644c3853633b7c65df`.
The frozen `browser_surface.mjs` SHA-256 is
`a11df1e67d44427d5f35cd65864c5f0c9ca033a22a339f34c37d38aebe0c0e8c`;
the surface bundle is
`94bee3209170b77e379c9c99e7d43ad835e460bc0e87d1dc4cb203b0ebd00ac3`.
Cleanup completed with no errors. Earlier `firefox-03`/`firefox-04` partial
results retain their own graphs and are not a complete current-graph pass.
This generic Session/renderer fixture executes no HTML engine and enables no
production-engine physical capability.

### Frozen physical-input and NDV2 component successors

The following freezes record later component work separately from the preceding
eighteen-test integration, single read-only-values compositor test, pixel259
driver and Firefox observations. Each receipt retains its own dependency graph;
these standalone results do not themselves establish an integrated runtime pass.
The later supported component graph below has its own frozen source identity.
All paths remain relative to `.agent-work/appended-implementation-20261016/`.

The 22-file physical-input source handoff is
`provider-browser/physical-input-implementation/IMPLEMENTATION-HANDOFF.json`,
SHA-256
`cafcd445857020df1b1456d37b226646cd6fcef5e3b764909141b31dcbbb06c6`.
The strict portable codec passed eight groups / 1,868 assertions. Four native
owner binaries passed: VM-free web owner, the actual optional Module/wasm3 leaf,
native queued services and eight new physical-input groups containing 8,162
require calls. The web-only defined-symbol check found zero Module,
ModuleProviders and wasm3/factory entries. Application `native-v6` passed four
actual Owner/PolicyPort input groups plus the existing bitmap App/host consumer;
it covers native-effect admission, explicit UI hold and bounded revocation queues.
The opt-in host syntax fixture passed web-only and optional-binary variants
against the frozen Surface wrapper, with compiled profile facts disabled.
These are host fixtures, not an enabled physical runtime.

The final transport follow-up passed 27 Node input/bootstrap cases with zero
skips and two syntax checks. Its earlier 39-case bridge and 22-case Worker
results keep their original v1 identities; they were not rerun for this follow-up.
The handoff also records 430 private supplier-codec checks; copied-dispatcher,
record-fixture and nine expected-abort results reuse their unchanged original
002 proof. Actual key-marker allocation/interning/copy/one-shot binding and the
two changed WebCore keyboard translation units were not compiled or DOM-tested
by this source handoff. No actual engine, browser, SDK or Foundation kernel
operation ran in this successor scope.

The separate nineteen-file generic mouse successor freeze is
`browser-surface-design/mouse-successor/FROZEN-v2.json`, SHA-256
`86326e5067ad3850a17024f9ad5bb230491c70c001bd9b4b72f1cfb15ef5f333`.
Its handoff records eleven strict pure-Policy groups, standalone C++/Node codec
checks and ten actual SurfaceSession/Policy fixture groups. Eleven Browser
composition groups reuse identical relevant inputs from their original receipt.
The Node physical model passed ten legacy and ten mouse groups; protocol,
channel, successor renderer/frame and unchanged legacy embedding checks also
passed, with no executed cases skipped. The fake frame lacks the native context
classifier and proves the truthful reduced capability, not classifier acceptance.
The opt-in `mouse_v1` ceiling is 8225; legacy defaults remain unchanged. This
component freeze predates the later partial Firefox mouse probe recorded below;
Chromium/Edge context classification remains implementation work. Earlier
Firefox receipts are not relabeled.

The later actual Firefox 153.5.0 mouse probe, `firefox-02`, completed two of seven
gates: native-classified first-focus balanced capture, and left/right chord plus
partial/outside/final release. Gate three timed out waiting for native Shift+F10
context; gates four through seven were unexecuted. Under
`browser-surface-design/mouse-browser-probe/`, `firefox-02/result.json` has SHA-256
`9faacd8312f73c748c1fc2bed0b41b5015544b3996a67a75034a785e1273aabd`,
binding snapshot `a31b15dd52d0911681dd989c43cb9ec9bb05bc85955ecac9b08f9e6dfb2c2fc5`.
The separate `operation-02-analysis/firefox-diagnostic-01/result.json`, SHA-256
`7587f7b3636fd7a155585fed214dfeb4ae78caa06501f6ad7e529b19fb7e219d`,
completed exactly three observations in 9.3627 seconds. Native keyboard context
events were absent in the ordinary parent, idle owned child and held owned
child. Cleanup completed without errors. These are three observations and zero
qualification passes; they establish no adapter-classification failure or cause
for the absent native event. The seven-gate qualification remains incomplete.

A separate remaining-gates run passed gate four (wheel) and failed gate five
waiting for capture cancellation; gates six and seven were unexecuted. Its
`operation-03-analysis/remaining-gates-source/firefox-remaining-01/result.json`
has SHA-256
`cda6a01d7f7d8fcfa87fbee862c5ad2edacda53d27825ca120c77b8d737fc549`.
It completed in 12.686 seconds with unchanged inputs and no cleanup errors.
The later two-condition capture diagnostic completed two observations in 6.837
seconds: early release lacked an observed native capture activation; release
after trusted capture activation produced canonical cancellation and completed
the four original gate-five assertions. This supports an activation prerequisite
for the fixture setup, without establishing an adapter defect. Session 9355's
`operation-05-capture-diagnostic-source/ROOT-CLOSED-RESULT.json` has SHA-256
`c6a0686ff42cd5ac98505f71bc4c7997833dce37d91cfa933857911cdc46345a`;
its `firefox-capture-diagnostic-01/result.json` has SHA-256
`de875a007a7d60488efbd428bccf6974c3c1d89888c38d5c36872e7eb543983e`.
Inputs stayed unchanged and cleanup completed. These are zero new qualification
gates: the original gate-three and gate-five failures remain, gates six/seven
remain unexecuted, and the seven-gate result remains false. Source-only analysis
`operation-06-analysis/FROZEN.json`, SHA-256
`a38dbc24f42e341933542ff93d6af6902972e264ad23db48062811710e8f1488`,
proposes preserving all thirteen original assertions with revised setup; it
supplies no new execution or production-engine capability.

The later versioned `native-activation-v1` selected run executed gates five,
six and seven in 7.281 seconds. All three passed, with unchanged input pins and
no cleanup errors. Its original thirteen assertions were preserved; each gate
first observed trusted native capture activation, a held move and the matching
accepted identity before retirement. The result is
`operation-07-remaining-5-7-source/firefox-remaining-5-7-01/result.json`, SHA-256
`07e3bd8073153d0a6829bdf294b53ea01d6345e3277cf6eb79bacb30cad0c7f6`.
Independent read-only review checked the actual observations and setup joins.
These are three selected generic surface passes on the new setup. The original
gate-three/five failures retain their identities, the seven-gate result remains
false, and no production-engine capability follows.

The three-file NDV2 consumer freeze is
`web-host-seams/popup-candidate/combined-v2/consumer-codec-design/FINAL-FREEZE.json`,
SHA-256
`59db4a3f9c77a431c53add6f7db168c3587adb1153799dacc77af9d599a29f04`.
Final strict C++20 attempt 03 passed eleven cases / 3,627 assertions and 276
independent native/consumer interoperability checks, with zero failures/skips.
All 34 inputs stayed unchanged. Seven exact successful objects were reused with
their original input/command provenance; the changed codec object was rebuilt.
Attempt 01 failed test-table compilation before runtime assertions, and attempt
02 exposed a missing encoder epoch guard; those failures retain their original
identities. The final guard correction did not remove assertions. This is a
value codec; it does not itself connect a provider. Later Owner/Driver/application
component delivery has separate evidence below; actual provider buffers, native
body actions and shared popups remain unfinished implementation. The frozen
native schema is
`f11fd061350f8d663dbcdec7cf0a063e4fb0ff3564d285076690f58e8a84143d`.

These source/component freezes produce no eligible physical engine SDK, real
Foundation runtime receipt, new-profile browser proof or release qualification.
Committed text/IME/editor contexts, selection, clipboard and popup integration
remain mandatory later implementation; generic touch/pen/multipointer and the
old raw-pointer capability are not advertised by the new mouse profile.

### Supported input and NDV2 component graph

A separate supported-entry Linux x86_64 GNU 14.2 Debug operation passed all 43
selected CTests, with zero failures, skips or disabled tests. Configure took
5.976 seconds and the build/test operation 66.722 seconds. Its 1,007-file tree is
`e337eac0e26ff9f37d1261ccdcf03ba8777c6e2c25b6e5c43e8187bf4e7e59f5`,
archive SHA-256
`c5943c5ed1a47676d60b71dca686e701e9e16bb4500ff9a18266a25d91cf3b6d`.
The receipt is
`input-codec-graph-integration/INPUT-CODEC-GRAPH-INTEGRATION-FREEZE.json`, SHA-256
`4310d7d445c13446ed9c7e17088ee610b785e0e1e3880851262efdd024a49332`.
This source combines the frozen native-driver input with 53 controlled released
overlays; later top-level build-entry/physical-admission edits and promoted
provider/recipe sources are outside the checked graph.

The graph built 46 objects: 24 strict C++20, eight GNU C++20 and fourteen C99;
fifteen archives and fourteen executables account for 75 recorded products.
Input codec passed eight groups / 1,868 assertions, input owner eight groups /
8,162 assertions, and NDV2 consumer eleven cases / 3,627 assertions. Full captured
TAP output confirms 39 bridge, 27 input-transport and 22 Worker subtests passing,
with zero failed, skipped, cancelled or todo cases. These 88 inner subtests belong
to three of the 43 CTests and are not added to the CTest count.

Defined-symbol checks on the web owner/application, input application, NDV2 codec
and base-driver executables found zero Module, wasm3, module-binding and Store
matches. Each of the three deliberate `both` owner/application/driver closures
contained 143 Module, 87 wasm3 and one module-binding match, with zero Store
matches. Thus the optional module/provider/interpreter leaf was actually compiled
and exercised only in those combined regressions.

The supervising root independently rechecked all 1,007 source files, 53 controlled
capture files, 44 evidence files, 75 products, the archive and 43 JUnit cases.
`input-codec-graph-integration/ROOT-REVIEW.json` has SHA-256
`544c0d299840cba99870a350d4fec2b528bc742fc3c2f1e2bf352e1b78189c4a`.
Mock providers/native replies and Node fake factories remain fixtures. No actual
engine/browser, SDK consumer, Foundation Wasm/production kernel, guest producer,
Store/core application, install/package or release operation ran. This pass
qualifies neither later working-tree successors nor any production physical
capability. Earlier 18-, one- and twenty-test receipts keep their own identities.

### Physical admission and document scheduling checks

The explicit physical-input consumer and pure rich-carrier tooling passed 48
and 45 cases respectively, with zero skips. Their four-file handoff is
`provider-browser/physical-admission/HANDOFF.json`, SHA-256
`bdd726c359738bab3f11163499be6b229dcef79d2b32f967a28341af6cb26788`.
The separate five-file CMake/wrapper admission handoff,
`physical-cmake-admission/FINAL.json`, SHA-256
`af0de3479bba75991fc8eb6ae713f7c091779fc7c2c474825862309fd5c76b43`,
records 37 entry/private-header fixture cases, zero skips, and four strict C++20
generated-header groups. Header receipt `run-v1/HEADER-RECEIPT.json` beneath that
directory has SHA-256
`7186087195418a800f5438bb14933acd88967d72d314c11824edd4416c6cc893`.
These use synthetic static pins and compiler-free admission fixtures; the header
fixture compiles only the standard-library/private-profile closure. They create
no eligible physical retained group, enabled runtime or Foundation kernel proof.

The additive [document-v2 contract](../abi/engine/document-v2/contract.json)
and pure profile/work/ACK values have a separate eight-new-file handoff,
`ndv2-owner-wiring-design/COMMON-CONTRACT-HANDOFF.md`, SHA-256
`af5aaf8ebd20dc6a1f24aafb8aedaf5f6188dbb0c9861b972a62c30d9ee42c0d`.
Strict C11/C++20 compile and execution checks and all seven pure Python cases
passed on the unchanged nine-file closure, including the original base header.
The validation receipt is `common-validation/validation.json` beneath that
directory, SHA-256
`8b7dcac13ef81680e34ed17c01b004f06a801b799e793f2cc12dd21be1f7e647`.
This is source-contract and byte-codec evidence, not an Owner, Driver, provider
connection or cross-target ABI qualification.

A supported Linux GNU Debug operation then passed six exact CTests: document
forms, document header contract, and the document-contract, entry, consumer and
rich-carrier tooling suites. All 137 Python cases passed (7 + 37 + 48 + 45), with
no exclusions or incomplete cases; all six CTests had zero failures, skips or
disabled tests. Forms passed 34 named cases / 4,678 assertions
through the real retained terminal adapter and owned native mocks. Configure
took 5.626 seconds and build/tests 39.477 seconds. The 1,114-file tree is
`895511c9cd824d6f14047c7c1d932771dac3b583e04d49b5d51d63170d7e9e5a`,
archive SHA-256
`2dceb6ea570d1d525afe6dfa0d172a370dcc430a1d28e41f1f0635b96a32957e`.
Receipt
`document-seam-tool-integration/DOCUMENT-SEAM-TOOL-INTEGRATION-FREEZE.json`
has SHA-256
`556dc25a3e119b8ab38624df5f1447462c8f1ef33fdd8a9b27620f48df97e7f2`.

That source adds 126 explicitly released overlays to the preceding 1,007-file
snapshot, including the promoted copied259 source/recipe inventory. It retains
the older Owner/private ABI and excludes the active mailbox and maintenance
producer. Only nine objects, six archives and two executables built; both symbol
closures exclude Owner, Module, wasm3 and Store. All 47 GUI-boundary cases passed
in 15.703 seconds, and the global documentation check passed in 1.218 seconds
only inside this isolated complete snapshot. Two passive audit-script errors
were corrected and preserved before compilation; no implementation test failed.
Source, archive, evidence and all seventeen products remained unchanged. There
was no real engine/provider, SDK, production kernel, guest, physical adapter,
browser, installation/package or release execution.
The root independently rechecked all 1,114 source files, archive, 46 evidence
files, seventeen products, six JUnit cases and complete Python case results.
`document-seam-tool-integration/ROOT-REVIEW.json` has SHA-256
`e44033822a7b4ada2538fdeeb3497df209287deb14ee672f70062dd265e9600e`.

### Supported document-v2 component integration

A separately frozen Linux x86_64 GNU 14.2 Debug snapshot passed all 156 selected
CTests, with zero failures, skips or disabled tests. Configure took 6.379 seconds
and build/tests 101.694 seconds. Its 1,126-file source tree is
`0632cd0a0da9300dd02d50837c469eef03286c8e11495b66e2d4f55bcf797566`,
archive SHA-256
`c7dccdfa943548a53e38462a35a851d8cf8c8d111d5cafbee8c5cf8a1c13ebf9`.
Receipt `ndv2-components-supported/NDV2-COMPONENTS-SUPPORTED-FREEZE.json`
has SHA-256
`b05805373014a6ad4489022df756eead8d89646a5c107f407379e7dbfccbe8fb`.
It starts from the unchanged 1,118-file source and captures 42 explicitly
released files; 37 differ from that base. Later component repairs below are
outside this supported pass.

Complete inner results include 121 Node subtests (bridge 40, Worker 30, input
transport 51), all with zero failures, skips, cancellations or todo cases; and
70 Python cases (maintenance 25, entry 38, document contract seven), with zero
excluded or incomplete cases. Forms passed 48 cases / 5,187 assertions; the
document application passed eighteen fresh processes / 3,272 assertions.
Owner passed thirteen CTest invocations, containing ten normal groups / 9,673
assertions and twelve terminal processes. Native Driver passed 26 document and
nineteen legacy processes. Guard passed 39 document and 25 legacy/header/adapter
scopes; the adapter fixture contains seventeen inner cases. Inner case counts
are not additional CTests. All 47 GUI-boundary unittest methods passed, and the
generic boundary guard separately executed successfully. The complete isolated
source documentation check passed. No checks were skipped.

The selected prerequisites built 39 objects (25 strict C++20, thirteen GNU
C++20, one C11), sixteen archives and eighteen executables. All eighteen defined
symbol scans found zero Module, wasm3, module-binding, Store or actual engine
definitions. The 73 products, 59 evidence files, source and archive stayed
unchanged through final readback; all jobs and streams closed. An initial
reporter incorrectly expected 48 unittest methods; the preserved failure was
corrected to the actual 47 methods plus the separately executed guard without
changing or rerunning tests.

This is supported component integration using real terminal/Registry components
and mock engine completions/providers. It covers Owner `4eb8284a…`, Driver
`7952a2f0…`, Guard `0079d5fd…`, bridge `2d38c754…` and Worker `55486e8e…`
on the final private ABI. It ran no actual engine/browser/native port, SDK
consumer, production Foundation kernel, guest producer, install/package or
release qualification. It establishes no connected engine-backed HTML TUI.
Earlier six-, two- and 43-test receipts retain their original identities.

### Subsequent document-v2 component repairs

The browser opaque-result repair has its own six-file handoff,
`ndv2-browser-transport-v2/HANDOFF.md`, SHA-256
`20fe00d5e4f684bf7700acfdd178a9dd3d62c1d033b6e88c7d3c06220527636b`.
Its `validation.json`, SHA-256
`91180c0e5c135438011dc650efd95016db6ca35e5771871dafe28f05f0baa7b1`,
records 124 passing Node cases (40 + 30 + 54), zero failures/skips/cancelled/todo,
and three passing syntax checks. The repaired bridge is
`0b4aecf4e7cc6153a27b56a23934c47113b28a9e51497f313236e2aab3d51fa5`.
The new input suite against preserved old bridge `2d38c754…` produced 52 passes
and two expected failures; those failures discriminate the repair and are not
added passing cases. Factory/allocator/Owner/provider fakes and tiny Wasm memories
establish bounded opaque evidence forwarding, not a real C++/engine runtime.

The separate terminal-notification Owner handoff,
`ndv2-owner-terminal-notification/HANDOFF.json`, SHA-256
`634327b066af58a551826573631eb7d5b36a25c01aa506516d7509d0de86d32c`,
records nineteen standalone invocations: seventeen document invocations / 10,641
assertions, legacy physical / 8,162 assertions and legacy web. All passed with
zero skips. The first attempt lacked an inherited private header and executed
zero assertions; the complete second attempt preserves that setup failure.
The native terminal successor freeze,
`native-document-terminal-notification/FINAL-FREEZE.json`, SHA-256
`0691d1cea4e1bcde4aa97e0006e5f0e7fbae42f54f49b4d5452ff8d176604434`,
records 46 passing fresh processes (27 document, nineteen legacy), no failures,
skips or unexecuted cases, and an old-Driver counterfactual failure. Its
`component-001/RESULT.json` has SHA-256
`da162b9b6702586ec79c7e4ec967854540b04a3466fc031f19a859a4c0fabae4`.
These are standalone real Registry/WebServices and mock-provider checks with
no VM symbols, actual engine/native loader or retained SDK execution.

The physical-result Guard repair separately rejects nonzero known physical
payloads before private reply validation. Its
`document-provider-physical-result-fix/FINAL-FREEZE.json`, SHA-256
`aec733ffbc25836dfaa857153ce3d4c4622c6574b0c37cdff1dd2d268e090350`,
records Guard `dcac577c…` with 40 document and 23 legacy fresh-process groups
passing, zero skips. `strict-01/result.json` has SHA-256
`877c96c1fb3d57f4f59f63ed67a5660ea31869d02a5f3f1aacd091e4d317e2d9`.
The new fixture fails as expected against old Guard `0079d5fd…`; that failure
is separate from the current passing cases. No actual provider ran. None of
these later repairs is covered by the preceding 156-CTest source identity;
their combined supported integration has the separate successor identity below.

### Supported loader, bitmap and document successor

The later Linux x86_64 GNU Debug snapshot passed all 205 exact selected CTests,
with zero failures, skips, disabled or incomplete cases. Its 1,139-file source
tree is `23de4d8c551e465deb10afb48d61d22a9186de5e183d0074d189b28fc8f5ba76`,
archive SHA-256
`e50b1c0fb302affe599a0d6e38053641261f8b8188bf1f081ad7a22f5df3f380`.
Receipt `ndv2-components-supported-v3/NDV2-COMPONENTS-SUPPORTED-V3-FREEZE.json`
has SHA-256
`094ad67fb6b9897036432124f22b8deefd240d3bb1ba07f524b499fd810b5762`.
Configure took 5.578 seconds and supported build/tests 108.634 seconds; native
completion was 124.668 seconds into the authorized 240-second scope, using two
compile and two test jobs. Every supervisor, child and output stream closed.

The repaired Owner passed ten normal groups and sixteen fresh terminal
invocations / 10,641 assertions; Native Driver passed 27 document invocations /
1,802 checks and nineteen legacy invocations. Guard passed forty document and
23 legacy invocations; those fixtures provide no assertion counter. TUI AppDoc
passed eighteen cases / 3,272 assertions. Loader passed 32 fresh groups / 440
assertions, its native document facade eleven invocations / 574 assertions, and
the bitmap App nine normal groups plus five fresh selectors / 1,442 assertions.
Physical Owner passed eight groups / 8,162 assertions; Web Owner's VM-free check
passed. Bridge/input transport passed forty/54 complete TAP cases; editor text
passed 51 checks, both existing codec/protocol fixtures passed, and twelve actual
C++ serializer outputs passed the Node decoder. These inner counts are not
additional CTests.

All 47 boundary unittest methods passed with zero exclusions. The actual generic
build guard also passed; its relative and absolute Ninja output names denote
one physical execution, giving 48 boundary checks at those stated granularities.
The complete isolated-source documentation check passed. The exact prerequisite
union built 44 objects, eighteen archives, fourteen executables and six mock
provider DSOs. New sources use strict C++20; retained sources preserve their
prior dialects (35 strict and nine GNU C++20 commands). All twenty executable/DSO
symbol scans found zero Module, wasm3, module-binding, Store or actual engine
definitions. No startup, core, guest or actual engine implementation was selected.

Root independently rehashed all 56 evidence files, 82 products and the complete
source/archive: 1,139 source files plus one `source.json` metadata file.
`ndv2-components-supported-v3/ROOT-REVIEW.json` has SHA-256
`eb65ea202123bce6241a699e694c31500336a3c1947b87954b54c2d466c9b152`.
The older 156-test source and unchanged broader seventy helper cases, Forms,
contract and Worker evidence retain their original identities; they were not
rerun or relabeled. Later Worker/bootstrap, admission, native host and provider
binding streams were deliberately excluded from this capture. This is component
integration with mock providers, not an eligible engine SDK or connected runtime.

The preceding 1,139-file attempt remains failed under tree `6c5e47b4…` and
`ndv2-components-supported-v2/NDV2-COMPONENTS-SUPPORTED-V2-FAILURE-FREEZE.json`,
SHA-256 `ede5864453671dfcfbda4057985867dba6be97e57c221f792b5a7c55777f6d11`.
Its generic guard rejected `windows.h` in the shared Windows loader source;
zero of 205 CTests started. One parallel ABI object compiled, with no linked
outputs. V3 moved both OS implementation files byte-identically to
`src/appended/` and changed only their CMake paths; it did not exempt the header
from the guard. The failed build, earlier live-source stability failure and
private auditor expectation failure keep their original failed identities.

A later native-composition boundary check is separate:
`ROOT-NATIVE-COMPOSITION-BOUNDARY.json`, SHA-256
`585f514bd08e4062fbe28115c7c92236b85ec7b86f92e9a4f983ed1d0f85d045`,
records 47 passing methods, zero skips, in 18.099 seconds on guard `9af1cfd0…`
and tests `5602edc7…`. The 205-test source instead uses guard `525ad367…` and
tests `4b75aaa5…`. This later source-boundary check supplies no new native runtime
or supported component-graph proof.

### Supported maintenance-entry fixtures and remaining blockers

The later supported two-CTest run passed all 38 entry and fifteen maintenance
cases, with zero failures, disabled tests, skips, exclusions or incomplete cases.
Configure took 1.769
seconds and testing 28.970 seconds. Its 1,118-file tree is
`69b20c989f34b12fdc5b14e9e19b15f3dfe347fc4f7fdee824e45b5417e9af55`,
archive SHA-256
`27ad1927c9296097a777581d777fc9e9360397cd40d2db1ddc19ab105f5bc186`.
Receipt `maintenance-entry-integration/MAINTENANCE-ENTRY-INTEGRATION-FREEZE.json`
has SHA-256
`237c930c00e545b735d6753152245dc06ac81509edc7f065a8d95858eb9da91c`.
Exactly seven files overlay the preceding snapshot; its six-test receipt remains
unchanged. The selected prerequisite union was empty, with no application
objects, archives or executables and no root Ninja build log. Ordinary native
CMake compiler discovery/ABI probes were explicitly permitted. Maintenance
CMake/Ninja tests used `LANGUAGES NONE` and Python fake tools; no actual SDK,
engine compiler, archiver, linker, factory or runtime ran. GUI-boundary and
documentation checks were not repeated.
The independent root recheck covered all 1,118 source files, archive, 29 evidence
files, two JUnit cases and all 53 Python outcomes, with zero compiled products.
`maintenance-entry-integration/ROOT-REVIEW.json` has SHA-256
`5cb15739d9dc323ded72dbb5ccca293fffc84c77072b36b73b790a62f7cf98b8`.

Those 53 passes bind the older maintenance producer
`34dc61c4385ec4c223212d45fc4f6ebc5a257b712291f757093333a5e398ee50`.
Its four-file `engine-maintenance-entry-design/SOURCE-FREEZE.json` has SHA-256
`7f0660ed78fd6b5f495a48d410a5f5e7e89cf125f49ffe84960d783d0284cc5f`.
Independent `maintenance-producer-review/REVIEW.json`, SHA-256
`129477e3cb68aa6d2954f62b09b6adb43e75ee8700972b249e1d0a205a89b2b9`,
subsequently identified three implementation blockers: filename/auxiliary
arguments outside the admitted input closure, missing transitive
`tools/browser_bundle.py` input, and Emscripten `NO_` aliases bypassing fixed
effective settings. A separate repaired four-file source freeze,
`engine-maintenance-entry-design/SOURCE-FREEZE-v2.json`, SHA-256
`2af2c86b021bb2ef12aee0e96148f34aec0b9e2aedda809cb425ff1dc6f779ff`,
records nineteen standalone fixture cases passing in 26.645 seconds, zero skips.
Independent successor review
`maintenance-producer-review/successor-v2/REVIEW.json`, SHA-256
`8812a88c5b379a1bbed3d4ccbcb3867270b84cb96b57139d785da27c63fd30d5`,
closed all three findings on the same four source pins. Its four focused cases
and nested fourteen negative-argument / three expansion probes passed; no cases
were skipped. The review reused the nineteen-case receipt without rerunning that
complete suite. This establishes readiness only within the reviewed producer
scope, with no new supported graph at that review, paired-SDK behavior, actual
engine operation or production eligibility. The old 53 passes retain their older source identity.

The later maintenance-only strict JSON repair has its own
`engine-maintenance-entry-design/SOURCE-FREEZE-v4.json`, SHA-256
`4a078cee92e5b85df594d156592403f9c2d7ee9a85a4bca8cb75231fd79bd9df`.
Its 25 standalone cases passed with zero skips; the same frozen producer/tests
then passed within the 156-CTest component snapshot above. The repair admits a
64 MiB maintenance document without weakening the separate 32 MiB global
manifest bound or strict duplicate/nonfinite JSON rejection. It changes no
old 53-case or nineteen-case receipt.

The separate source-only retained successor freeze,
`retained-producer-successor-v4/FINAL-FREEZE.json`, SHA-256
`1aeafc62fbfcf7401112218a31a6857ec3576a547cb773ac4b38c5a4eb359ce3`,
records public source verification and pure metadata generation, with no test
suite rerun or actual producer operation. Its pins are R
`099fbeee3bbcca16f9e0b48e0d003620f36610bc494477c41203c969e511568b`, S
`dc4dd223d9c799478fd8f4e6e50b553c5f56dd928730fa7c3aaa7f18f270d5f4`, B
`22f736166666c1586548954ca7a0242417c0b38105fb9de703f1bdae4d1c62f9`, H
`dcfd4cfe53497999ae0248045605adccc2422506d3ce8e380325a4b65d41e265`.
The 245-file source manifest / 243 recipe inputs preserve the eighty projected
source IDs. Portable reuse closure remains unsealed and production eligibility
is false. No actual SDK scan, engine build/cache/compiler/archive/link, factory,
runtime, eligible candidate or retained group resulted.

### Document-profile Worker and admission fixtures

The separately frozen document Worker successor passed all 39 Node cases and
two syntax checks, zero skips; all thirty legacy cases remain in that suite.
`ndv2-worker-bootstrap-v1/HANDOFF.md` has SHA-256
`68fda6fcf903fddf277e3055c5d7387bc018f3c1bbbe4c0ce418d4287c4f635f`;
its `validation.json` is
`6f28bf0df876b80957449ddc535c729a71aadfef1c4345a22873cb52d16c2cbf`.
The thirty-file isolated closure checks owned facts, full-width Worker identity,
one configure call, ordering and no cleanup after uncertainty, using fake
factories, allocators and dispatchers. A filtered positive against old Worker
`55486e8e…` failed as expected; its 38 filtered skips are not passes. This new
Worker is outside the 205-test source and proves no actual provider bootstrap.

The new pure document contract, consumer and profile generator passed 69 Python
cases (eighteen/thirty/21), zero skips, in a seventeen-file isolated closure.
`ndv2-admission-tooling-implementation/HANDOFF.md` has SHA-256
`5ac0f0b3e9445968db88b1f46f94a2904d2d9d572956456cb2ec95a1d762a309`;
`python-v1/validation.json` is
`c101b23061f05f0eac93c5866dcc2d20bf73a07036a78b91eb103193e3cbd3fa`.
Two synthetic generated headers also passed strict C++20 compile/run checks.
Parser groups remain ineligible; generator positives use explicitly synthetic
trusted inspection mocks. No actual group, engine, SDK or Foundation runtime
was produced or executed.

The separate document carrier passed 37 Python cases, zero skips, in 4.306
seconds on its 25-file isolated closure.
`ndv2-document-carrier-v1/HANDOFF.md` has SHA-256
`77515a31932dead92aeff8fe6bc756a8049bc95fba16fc8a9511fc85a28e19d4`;
`python-v2/validation.json` is
`f9023bbb75ddba97c98b107cfe50caae7537f13b669cda24923e4898af5edf57`.
The first 35-pass/two-failure run remains preserved: two test mutation defects
were repaired with explicit preconditions; producer bytes were unchanged.
Fixtures are inert parser-only, with synthetic in-memory predicate/publication
checks. No actual eligible document group, Foundation receipt or package was
created. Entry/CMake/bundler integration and real runtime evidence remain separate.

Native document admission has its own 85 passing Python cases (24 binary
parser, 34 consumer, 27 generator), zero skips, plus three strict host C++20
generated-header syntax checks. These cover synthetic Linux x86_64/aarch64 and
Windows x86_64 profile constants, not execution on those targets.
`native-document-admission/HANDOFF.md` has SHA-256
`ddb77d3d2d684db78445beded7a5d1eee3eea075a5bb698f6ed48f87e1211973`;
its `FINAL-FREEZE.json` is
`75c4782cfd3c5fca59a5d18cc2b3bdef3060fca991328c5a05738b332fd09f35`.
The consumer/generator implementation admits pixel1795 only and requires real
independent native loader/dependency/runtime evidence; parser fixtures cannot
supply it. No native SDK, provider getter, DSO or actual engine was loaded by
these checks. Native port/build/main integration and runtime qualification are
not established by these source/tooling fixtures. All eleven legacy held helpers
retain their original bytes in these new partitions.

The released entry-routing successor has a different 1,147-file source, tree
`68c73d7eac083c4c731b83d003b04b16d137fea699c76114651a18af8ff71b22`.
Its supported ordinary none-profile run passed three selected tooling CTests /
82 Python methods (38 entry, fifteen rich entry, 29 SDK-helper), zero skips,
exclusions or disabled/incomplete cases, in 4.041 seconds. The compiled
prerequisite union was empty; only normal native compiler discovery/ABI probes
ran, with no application products. `native-entry-routing/FINAL.json` has SHA-256
`686e07b9445c703a48a2ef43303e5872a81b86bb8092b06c71a1bc38285e3398`.
It adds explicit document/native selectors and strict retained target/SDK joins;
Windows APIs/toolkit selection use mocks on Linux. New GUI/host fragments were
not overlaid, so their combined projection/runtime remains separate. This
1,147-file tooling proof does not extend or relabel the 1,139-file 205-test proof.

## Actual baseline engine and later syntax observations

The native pixel259 driver passed twenty supported native CTests with zero
failures, disabled tests or skips: nineteen fresh mock-provider processes and
one case using the actual Module/wasm3 leaf. Configuration took 2.069 seconds;
the test/build operation took 13.744 seconds. Source tree
`9a02d419ab7a2b6919a30657bcf054b197df8965136ac150cfbcb6aa2a01fa47`
contains 994 files; archive SHA-256 is
`800d4695b2a63f7d71f9a8098f46eaecf40d443c49a0a6acf3e6ab9d752aba1e`.
It adds the three driver/test files and five recorded build-entry/CMake overlays
to the earlier eighteen-test source. All 27 driver input pins matched. The
selected graph built 26 objects (12 strict C++20, 14 C99), ten archives and two
executables. The base executable has zero Module/wasm3/binding symbols; the
combined executable contains the actual leaf. Receipt
`native-driver-integration/NATIVE-DRIVER-INTEGRATION-FREEZE.json` has SHA-256
`468a2a1d7f7c7898f528f692c5a8c3be60926c46324449547fd9f2ebb61140ee`.
Independent passive review rechecked all 994 extracted source hashes, the
archive, 30 evidence files, 38 build products and twenty JUnit cases. These
results bind the frozen original owner/WebServices closure, not the developing
physical successor. No GUI, real engine/provider, OS loader, native SDK, guest
producer or production kernel ran. A real nonzero Registry ACK failure was not
induced by these fixtures.

The later copied-factory glue smoke used a tiny C fixture and the exact frozen
neutral link flags, pre-JS and JS-library inputs. One compile passed in 1.269
seconds; 37 actual assertions passed in an offline Firefox dedicated Worker in
4.100 seconds. They cover owned bytes, custom host import and copying, signed
32-bit arguments, actual heap growth, deferred main and terminal failures. Full
SDK inventories remained unchanged. Receipt
`copied-factory-glue-smoke/RECEIPT.json` has SHA-256
`64fc070188d801ae52fdcc9f33b90c228c0ccc1daaddaa475fc4ef1577500a73`.
This compiled no WebCore, provider or Foundation owner/kernel and embedded no
engine data. Shared-buffer and other Worker-context negative cases did not run;
the tiny fixture does not prove real engine constructor or startup behavior.

The authorized baseline WebKit/Wasm build and link completed in 148.3 minutes.
Its actual internal engine passed eighteen assertions in Node 24.19.0 and
eighteen in offline Firefox 153.5.0, including styled editing, semantic values,
asynchronous activation and matching CPU pixels. The first Firefox setup failed
before assertions; the owned-byte `instantiateWasm` harness repair changed no
engine bytes. [The engine audit](appended-web-feasibility.md#authorized-bounded-engine-result)
is authoritative for complete source/artifact identities, measured sizes,
provenance, SDK bytecode cleanup/restoration and material limits. This is the
diagnostic CommonJS baseline, not an eligible neutral provider SDK, native port,
physical OS IME check or connected HTML TUI.

After the fresh stopped-input freeze, three combined resource/service wrapper
translation units passed actual-header syntax checks, all compiler exits zero
and no surviving children. Total session time was 88.399 seconds. Receipt
`offline-resource-design/combined-bootstrap/syntax-stage1-fresh/run-001/stage1-receipt.json`
has SHA-256
`de404902ecf2318550dcbf704715faedb7f13f3ae64be094680b43bd7c9eddda`.
Postflight verified complete frozen SDK/header/base inputs unchanged. The
selected scope excludes the five core patches, `EmbedderStrategies`, optional
shim, configuration, Ninja, object generation, linking and runtime execution.
It cannot qualify the later ignored source-only actual provider or version-two
document/form work.

The later native004 syntax retry selected exactly two translation units from the
repaired `native-v2-source-004.tar.gz` under
`web-host-seams/popup-candidate/combined-v2/exporter-implementation/native004-repair/`,
SHA-256
`e58cbe009d708d6ab990d21c4ca7ef7c65d69524ec3c6b63ebfea14ecdeaf200`.
`NativeFormsV2Combined` passed in 62.244 seconds; `NativeDocumentV2Publisher`
failed in 52.864 seconds with a fatal `WebCore/ElementRareData.h` include-not-found
diagnostic. This does not establish whether source absence or include context
caused the failure.
Both selected commands ran; the retry remains failed. Postflight input/cache
checks passed. Receipt
`html-tui-native-syntax-design-v2/syntax-001/syntax-receipt.json` has SHA-256
`edd1141efb9c2615d051086ece2930e63f45a3c4c1bd83de2b3b20331c0d69b4`.
The root's closed summary is `html-tui-native-syntax-design-v2/ROOT-CLOSED-RESULT.json`,
SHA-256 `f4d8cbb69468b3bef89f9f8005a19f7848607be91424e627c435e38a1efb1a76`.
Earlier native003 failures retain their original source identities.

The separate Native006 Publisher-only syntax scope subsequently passed against
actual Emscripten WebCore headers in 38.678 compiler seconds / 185.898 session
seconds. Its Publisher source is
`b856023620151bbc80017780c87ce303f89610789270a1e2a84e593e16a80a0e`.
`native-publisher-syntax-design-v4/ROOT-CLOSED-RESULT.json` has SHA-256
`f2f260940228e8bfc48622feb266a0df4f2a7e955a8d497b420b28efaad613e0`;
its `syntax-001/syntax-receipt.json` has SHA-256
`d251453a5d0a47db5a820cb8ecdda0cd969949a8525402a89470c284009eeeb2`.
Independent `RESULT-REVIEW.json`, SHA-256
`e222f101ce36dc0bd20673defd202998d5472952f751490a57400569f576d778`,
confirmed the selected command, unchanged recorded source/SDK/cache inputs,
complete postflight, reaping and EOF. The generated/forwarded-header inventory
does not completely inventory transitive vendor/sysroot headers; execution also
relied on root-held immutable baseline/SDK/header/seed scopes. Combined retains
its original Native004 62.244-second pass and was not rerun or relabeled.
Neither syntax scope generates objects or proves link/runtime/native-port behavior.

The separately reviewed copied-composition continuation selected thirteen syntax
commands on `copied-wasm-composition-v2/COMPOSITION.json`, SHA-256
`d0dbb93eb2a1d07a079f3a5dd1edeba50016974449baa97f05d8b898791dd043`,
beneath `web-engine-service-adapter/provider-candidate/`. Its first command,
`BibCopiedPixelBinding`, failed in 52.218 seconds with an undefined-inline
diagnostic for `LocalFrame::view()`. The remaining twelve commands were unexecuted;
postflight input/cache checks passed. The corresponding
`syntax-003/syntax-receipt.json` has SHA-256
`b93922a70c6f456427415f44368da753400b0631a4d6d8ae3857e46606e54a17`;
`ROOT-CLOSED-RESULT.json` has SHA-256
`3fc8a1f3826ce224be750bb089914820e6dcc9171a522a98e0d067b5335ad558`.
These earlier syntax attempts generated no objects, link, engine runtime or
native-port proof.

The later copied syntax004 scope remains **failed and unqualified**. Eleven
per-command receipts observed compiler exit zero and quiescence; command 21 has
uncertain cleanup, command 22 was unexecuted, and full postflight did not pass.
Those eleven observations are not a qualified thirteen-command pass. Analysis
identified synchronous persistence of the giant aggregate receipt inside
supervision callbacks and stale deadline checks; exact per-write latency was
not separately instrumented. Original outputs and their scope remain
quarantined. `copied-syntax004-supervision-analysis/HANDOFF.json` has SHA-256
`e7dd547ac85dec78396b2a4e265b58a8f8aea459538033885c82f6902a9bc6e2`.
The narrow read-only host probe found no matching process, but could not map
the old session to its namespace/cgroup or establish teardown. Its
`copied-syntax004-host-recovery-design/PROBE.json` has SHA-256
`da04b12d72fa1efa264007ae6b84dff6ce6231c110afa124afb1bdf9c6534a47`.
No original process was signalled or reclaimed by those analyses.

A separate two-command continuation was prepared under
`web-engine-service-adapter/provider-candidate/copied-syntax-remaining-design/`.
Its `CHECKPOINT.json`, SHA-256
`33daf4816b9425e4e0c1aec13f1340ad6317460262295c39532381f98ad7babe`,
and `runner/QUALIFICATION.json`, SHA-256
`a27010a75355e992acc7aa1042b25771352e069d80365dd5f49861c6c0d11b15`,
record 209 passing helper cases with zero skips, using synthetic inputs and
small Python child trees. The subsequently reviewed actual continuation, session
76715, passed both selected units: SharedWorker in 12.516 supervised seconds and
RunLoopGeneric in 2.911 seconds. Total session time was 167.347 seconds, including
input inventories, copying and evidence. Both processes were reaped, streams
closed and complete recorded input verification matched before/after. The
compact aggregate SHA-256 is
`6157c8b94fb4a8e0960d9e682e4e77fe8de1921d739770fb7a43ddcf31060f09`;
`ROOT-CLOSED-RESULT.json` has SHA-256
`05385ad9066366efe708a724ac6d4db128f46efbb90272717729dea1516be2cc`.
Independent review checked the new receipts, including exact verification-value
equality. These two syntax passes cannot repair the old cleanup evidence,
relabel its eleven observations, or establish objects, linking, a runnable
factory, SDK eligibility or native ports.

## Later loader, bitmap and editor component checks

The process-lived native loader passed 32 fresh Linux fixture processes / 440
assertions in 6.028 seconds, with zero skips. Its ten strict C++20 compilations
included six small mock DSOs; nine unchanged neutral objects were reused only
after actual dependency-byte checks. It obtains and checks the actual C table
without START and retains acquired handles on failure. The source freeze is
`native-engine-loader-implementation/FINAL-FREEZE.json`, SHA-256
`ab2b08a964ebc6ec19df4d572564955e5a5369e8413cc91c609081ab1d44ad9d`.
Windows loading has source review only; no actual native engine, SDK, dependency
isolation or supported host entry was exercised.

The typed document bitmap application passed six new invocations / 1,442
assertions and both affected legacy application checks, zero skips. Tests use
the actual RetainedAdapter, Owner, Registry and Surface Policy with a copied
mock provider. They cover redaction, debt-aware readiness, fresh-frame rearm,
setter exceptions and closed-presenter handling. Source review is clear;
`ndv2-bitmap-app/HANDOFF.json` has SHA-256
`737e5100a41e81032ebda6af202916135c619564036d7b7bd8f21cf73c4b8896`.
The released 1795 source successor now selects the post-release raster helper,
but its actual compilation, frame delivery and GUI rearm remain unproved;
these component passes establish no runnable engine UI.

That successor, `ndv2-provider-binding-design/implementation/versions/0002-document-raster/FINAL-FREEZE.json`,
has SHA-256 `36e207813db6bbbd907adf7465db5fdf630ad84b93f30a441c1e7728111cd7f0`.
It changes exactly three files in an 83-file source projection and selects the
sole document advance helper; the original mock/bootstrap evidence excludes
those three changed native files. The separately released physical capsule,
`ndv2-physical-provider/FINAL-FREEZE.json`, SHA-256
`527d201c4d8c065ab50d7671a2dbdf2763260304beb8ea0d88ba3ee48c21682a`,
passed seven portable groups / 1,284 assertions and eight separate pure key
groups / 24,780 assertions. Its actual WebCore physical/key/render paths remain
unparsed, uncompiled, unlinked and unexecuted. A complete current 2003 binding and
actual full owned frame commit/rearm still require implementation and evidence.

The generic browser editor value codecs passed strict C++20 tests, Node protocol
tests, 128 feature-subset negotiations, twelve actual C++-to-JavaScript fixture
joins and twenty affected legacy physical-model groups. They encode existing
text/composition/selection values under an explicit editor profile. Their later
supported registration is covered by the separate 205-test successor above.
No production editor profile is enabled. Evidence remains under
`browser-editor-codec/` with its original source identities.

The new generic editor controller and conduit separately passed 108 Node cases
(68 controller, forty conduit), zero skips. Frozen
`browser-editor-conduit/implementation-v2/HANDOFF.json` has SHA-256
`e7f77e8376b411f6ab4d740d164d2ad3fa96319b9bb925c68dd173299fe22a6e`;
its seven-file JavaScript closure includes main `8292db32…`. The 51 unchanged
helper checks are reused separately, not added as newly executed cases. Tests
use fake DOM trust and diagnostic tokens; the native key-outcome overlay has
textual application proof only, with zero compiler/runtime assertions.
These generic modules are implemented, but main/HostAdapter/Owner observation
ingress, native projection/default outcomes, catalog/binding integration and
trusted browser/OS IME behavior remain unproved or unfinished. Moving successor
integration is excluded from this frozen 108-case identity.

The retained reuse core also passed an exact bounded copy/readback: 42,755 files,
1,699 directories and 753,710,818 bytes, without configure/compile/link or SDK/cache
actions. `retained-baseline-reuse-design/CORE-COPY-RECEIPT.json` has SHA-256
`f1ae3d22af9d00b681818b95da0d1caee6257af63d3f2f2009caf7c9b78e2a91`.
The copy remains unpublished and ineligible. The later actual producer attempt
below does not supply its missing production/runtime qualification.

### Actual retained-baseline candidate failure

The first actual retained-baseline candidate operation, session 32535, closed
with a compile failure after 289.582 seconds, without outliving descendants or
supervisor error. `retained-engine-candidate-review/actual-v1/FAILURE-FREEZE.json`
has SHA-256
`2be5f6e1af4e3028b811eb41da10b0da93388995153c8f59ab5bfdb248be25ad`.
It binds 38 files / 507,460,487 bytes. Actual metadata matched B `22f73616…` and
H `dcfd4cfe…`; JavaScriptCore/PAL repack member readbacks and the
`RunLoopGeneric.cpp.o` compile completed. Two unified owners,
`68aea4ac-18` and `be65d27a-7`, failed on duplicate WebCore definitions reached
through separately materialized source/PrivateHeaders/DerivedSources aliases.
No link, factory or runtime ran; production eligibility remains false.

Full postfailure frozen-plan verification passed in 40.727 seconds; the original
90,286 SDK/reuse/source/helper inputs remained unchanged. The first relative-path
postverification setup failure executed zero assertions and remains preserved.
A narrow header-identity correction and discriminating failed-TU probe have
separate successor evidence below. This closed failure is neither a pending
session nor a passing engine candidate, and supplies no parsing/runtime proof
for the newer 1795/2003 source capsules.

### Header identity diagnostic and retained successor

The one-TU successor diagnostic, session 74167, passed syntax-only compilation
of the formerly failing `UnifiedSource-be65d27a-7` through the 4,153-class VFS
header view: 35.499 compiler seconds / 37.595 whole-session seconds. Its process
was reaped, streams closed and named source, overlay, launcher, SDK-manifest and
private-cache inputs matched before/after. Receipt
`retained-header-identity-fix/syntax-one-tu-v2/ROOT-CLOSED.json` has SHA-256
`fd55540b9b4fd0100d0be7332dc21f64bced66c16251c7af9aa80159698f2ce1`.
The first diagnostic's AST setup failure launched no compiler and remains
preserved. This pass generated no object, link, factory or runtime result and
does not repair the original candidate or quarantined syntax004 evidence.

A new independent source/reuse copy then closed successfully in 36.656 seconds.
It verified 43,013 copied files / 1,342,909,437 bytes, preserved original input
identities and performed no SDK/cache or build action.
`retained-header-identity-successor-v1/FINAL-FREEZE.json` has SHA-256
`4a8e98ad4d66ade83df019595f5f1ce3e5069ff50cfe322ba669dad5ce5682fa`;
its new recipe is R `a3d7e44c…`, source manifest S `cfb285eb…` and reuse proof
`1493a959…`. The separate actual supported pure-plan operation passed in
52.363 seconds with closed processes and no outliving descendants. Its
`ROOT-PLAN-RESULT.json` has SHA-256
`8e51904e1817aa6aab059327a3dcbb2bfe8c36ae9a9f82c8ce61b5ea7f056d82`,
binding plan `c3b09aa36303e3ab42159feaf85d766e5bfd9fc129a1b9eccd08de8f3794134e`.
Candidate v2, session 15294, subsequently closed failed in 387.578 seconds.
All six selected core owners compiled; the regular archive parser rejected
LLVM's internal NUL alignment in the WTF index. Its failure freeze is
`retained-header-identity-successor-v1/root-candidate-v2/FAILURE-FREEZE.json`,
SHA-256 `6b1344b1234e70a34d7cca8f5d8f5c0553fac229cc77d46883f8585650702ba1`.
Full frozen input postverification passed in 65.925 seconds. The minimal parser
repair preserves count/member-offset checks and permits only the actual one-byte
alignment form; all 39 maintenance methods passed on that repair, zero skips.
No wrapper/link/runtime result belongs to v2.

The independent v3 source/reuse copy passed in 48.445 seconds, preserving
43,013 files / 1,342,911,491 bytes. Its supported pure plan passed in 57.086
seconds: R `511efb58…`, S `314a4071…`, plan
`5de39529c46d4fa24d1bc7e2796c9c0201c796da245669ffc164f7934dcee2c5`.
The actual v3 build, session 54174, closed failed in 629.254 seconds with no
outliving descendants, deadline expiration or supervisor error. All 24 selected
objects compiled, all five regular archive repacks/readbacks passed, and the
actual link completed in 196.989 seconds. Static inspection then rejected
renamed raw Wasm exports. The generated factory's JavaScript names do not satisfy
that raw ABI requirement; inspection was not relaxed.

Failure freeze
`retained-archive-alignment-successor-v1/root-candidate-v3/FAILURE-FREEZE.json`,
SHA-256 `04fea03d5e29f8473a2297b49528477abaf3cf20842846c02d21deacff3a15d2`,
binds 76 records / 410,952,516 bytes. The 108,896,213-byte Wasm has SHA-256
`04c939aeaf069a3c8727e37a7e9248299095b594057ac9905d7c679f3b3d5d48`.
Complete frozen source/reuse/SDK postverification passed in 59.334 seconds.
The required `-lexports.js` repair and checked reuse of 23 unchanged original
objects are separate implementation work; only the metadata shim's actual
depfile includes the new generated build identity. No passing producer receipt
or runtime binding was created for v3. All eight copied runtime checks remain
not-run, and production eligibility remains false.

### Modern document source and maintenance fixtures

The separately frozen modern document assembly 0003 contains 98 source files,
27 direct translation units and nine engine replacement postimages.
`ndv2-provider-binding-design/implementation/versions/0003-document-physical/FINAL-FREEZE.json`
has SHA-256 `749d0efcaa72dae08f671070b7cde4e5142a8a8bc20d8747199518037756e686`.
Its portable dispatcher passed 1,580 checks across 29 fixture runtime cases and
its bootstrap passed 42 synthetic Python methods, all with zero skips. These
join explicit pixel1795/physical2003 source and 24/30-field host facts; they
parse or execute no actual WebCore provider. Earlier binding/bootstrap failures
retain their original identities. The assembly's inherited production metadata
shape gap was explicitly recorded, not counted as passing production generation.

The separate document metadata adapter passed 23 synthetic cases, zero skips,
in 0.858 seconds; `document-provider-maintenance-plan-v1/metadata-python-v2/validation.json`
has SHA-256 `68883c77ed5c6c04d7f6645328194797423a8c449f87a468b32305c330321a36`.
Its earlier fixture-directory-mode setup failures remain preserved. The new
document maintenance planner/driver separately passed 23 focused fixture cases,
zero skips; `driver/HANDOFF.json` has SHA-256
`e3ab6ab51ec34a35778a4b12bcbffe4d746cdaf70860d26c35dd6bff95481ee9`,
and `driver/fixture-v1/result.json` is
`362bfc40674f7f05bbb63ad7d950c7b7501558f17b1c9eec922408d4421b0cb2`.
Its explicit pixel/physical graphs select 23+6 / 27+9 objects. These source and
synthetic metadata/planner results perform no actual retained document admission,
plan, SDK/cache operation, WebCore compilation, link or runtime; original context
and header-identity evidence still require assembly for those profiles. The
legacy copied259 pure-plan pass above does not qualify either document profile.
Later modern source/maintenance/reuse fixtures passed 83 cases with zero skips,
with their source integration frozen in
`document-provider-maintenance-plan-v1/SOURCE-INTEGRATION-HANDOFF-v2.json`,
SHA-256 `88bd6c6e523441f79c5ab5f4b33c7a3e24fcb494e0f3f2289dfe1c95cc8030ae`.
An actual source-only pixel assembly then passed in 4.276 seconds: 301 inputs /
562,659,063 bytes, R `17e8758e…`, S `b6cfa6f6…`. This copied retained data and
performed no SDK/toolchain action, extraction or engine compilation. Its old
link policy remains historical. A subsequent exact-once export-switch repair
passed 34 maintenance and 29 reuse fixture cases, zero skips, receipt
`retained-raw-exports-repair-v1/modern-flags/VALIDATION.json`, SHA-256
`92d6b0c0d0746ad1ebba7c96f797e5408cadc2c5c9a7d18d204be9df4af69a21`.
No actual modern reuse generation, SDK admission, compiler, link or runtime
belongs to those earlier identities. The refreshed pixel source group later
passed complete readback in 5.374 seconds, R `058ab44c…`, S `530acf2b…`, retaining
301 inputs / 562,659,719 bytes and changing only the intended three tool/profile
inputs. Its freeze is `document-source-refresh-v2/FINAL-FREEZE.json`, SHA-256
`952c86fcb76d50302ff448387c3028bb8d2daf34c342c31de617c1a4d7b284d6`.
Root independently verified all thirteen frozen evidence records and the complete
source inventory. The supported `document-plan|document-build` aliases separately
passed eleven dispatch/help/parser cases with no subprocesses, skips or native
toolchain selection; handoff `document-entry-routing/HANDOFF.json` has SHA-256
`f3e979a2d20f7e250a390e195b95d18d8e290958b22c6762b5d6da024117398c`.
The subsequent actual pixel reuse-metadata preparation passed in 24.316 seconds,
with closed processes and all 29 named inputs unchanged. Its nine-file fragment
and assembly total 103,977,514 bytes; freeze
`document-reuse-preparation-v2/FINAL-ACTUAL-FREEZE.json` has SHA-256
`cbf18f1f24b055495c8586acc4ff8991cc19673c3c292b35239da476feb5df84`.
The new proof `79cc8bcc…` describes 29 selected objects, six archive replacements
and 2,070 retained opaque members. Root independently verified all 24 frozen
records and nine outputs. This is an incomplete metadata fragment: no complete
reuse tree, actual document plan, SDK program, compiler, link or runtime resulted.

### Editor source and portable component successors

The explicit rich-editor2035 source assembly 0004 is frozen in
`ndv2-provider-binding-design/implementation/versions/0004-editor-v1/FINAL-FREEZE.json`,
SHA-256 `091cf595380de9e7eebff6926dc5024124625ebb7a0eea0b35bff460765f364d`.
Its 119 files contain 31 direct translation units, eleven engine replacement
postimages and two added vendor headers. The 599,931-byte source archive has
SHA-256 `750b051bd43c5cc677913961e96f9041199fa58227f9eb3daa72963945005779`.
Independent postchecking verified every path, byte, mode and provenance join.
The current historical-retirement dispatcher passed seven portable cases / 667
checks; current bootstrap deltas passed sixteen C++, 32 Node and 41 Python
checks. Earlier dispatcher and bootstrap proofs retain their original inputs.
None parses or compiles actual WebCore; source preparation is not a native or
browser editor runtime pass.

The portable ContextAdapter successor passed 41 cases / 1,404 assertions with
zero skips or warnings. Its freeze is
`native-editor-context-adapter-component-003/successor-2/FINAL-FREEZE.json`,
SHA-256 `28a7ac23ede7e6f22915823ef049206933710eb1c948c2dbbebbb02c27195971`.
The generic Browser Surface separately passed twelve editor groups / 112
assertions plus its two legacy executables, zero skips; freeze
`browser-editor-surface-implementation/FINAL-FREEZE.json` has SHA-256
`c016d077ff3dd2506d532c685b0919e1f00d7ff369b7d047ce3bdddfeefd008e`.
These use real portable policy/controller code with explicit provider fixtures;
they establish neither actual engine editing nor browser/OS IME behavior.
Supported combined editor integration, connected HTML TUI and native ports remain
implementation work without actual editor/IME runtime evidence or an enabled
production profile.

The final generic JavaScript editor successor passed 312 Node cases, zero skips,
on its twelve-file source/test closure. Its handoff is
`browser-editor-conduit/inert-admission-v7/HANDOFF.json`, SHA-256
`56321ee0f0f80b2ff3f9e0a659632a508b544c4d6450825e553c212afd269aa7`.
It preserves queued work during inert publication gaps and requires fresh checked
authority before resuming input. Separately, the combined endpoint/bootstrap/
generated-bundle fixture batch passed sixty numbered cases and its legacy channel
fixture, zero skips, failures or timeouts. Receipt
`copied259-editor-frontend-v1/final-v2/TEST-RECEIPT.json` has SHA-256
`c9130d34afe4609cb369546d2808aeff0742d75d4d7e2447d992bea09f6c9672`;
source freeze `ed1238f7…` binds 58 canonical inputs and fourteen generated assets.
Root independently verified both copies of all 58 inputs, fourteen assets and
twelve logs. The selected 201,640-byte bundle has SHA-256
`d6dd841f5b043f6fceb31eb605f4ca389f3a9573a1a47642eb9637acf938c27a`.
The generated module graph ran against explicit DOM/port fakes. No actual browser,
Worker, C++ Session, engine, SDK or compiler ran in either JavaScript proof.

### CPP-only editor source and isolated recipe successor

The immutable 119-file 0004 assembly above retains its original identity. Its
separate CPP-only successor 0005 contains 118 projected source files plus two
original-header verification files outside the compiler projection: 31 direct
units, eleven engine CPP postimages, 64 headers and twelve data inputs. Four
CPP inputs change and one private scalar/scope helper is added; 113 projected
files remain byte-identical to 0004. Both original core headers and all old
member signatures are restored exactly. Private free-function observers wrap
one existing native dispatch, with exact owner/event identity, one claim,
nested-call shadowing and scoped unwind restoration. There is no class-layout,
inline-definition or ODR/header compatibility waiver. The
0005 freeze (`.agent-work/appended-implementation-20261016/ndv2-provider-binding-design/implementation/versions/0005-cpp-only-outcome/FINAL-FREEZE.json`)
has SHA-256 `333e266aa571cc04690e12ff6e836c7ccdee3618415cf08265894b66fa124d7f`.
Its actual pure-header test passed thirteen cases / 107 runtime checks and eight
compile-time assertions, zero skips; 492 static identity/wiring checks also
passed. No actual WebCore CPP or header was parsed or compiled by this scope.

The independently reviewed
owner proof (`.agent-work/appended-implementation-20261016/editor-provider-maintenance-design/owner-proof/HANDOFF-001.json`),
SHA-256 `4f1aded565d1b88319aebb700cd9393b29d099805429782489b66c82eb2d2493`,
joins complete eight-sibling order, original commands, physical aliases and
archive tuples: Element.cpp belongs to UnifiedSource-be65d27a-9.cpp at WebCore
ordinal 602; EventHandler.cpp belongs to UnifiedSource-767013ce-4.cpp at ordinal
721. The two unchanged header identities are joined separately. This is finite
metadata/tiny-source evidence, not an invented historical dependency graph or
proof that opaque old header consumers were rebuilt.

The subsequent
isolated recipe implementation (`.agent-work/appended-implementation-20261016/editor-recipe-implementation/FINAL-FREEZE.json`),
SHA-256 `64ef18777703f1b3a0d5139cfb64ae4050989f16520f5037e8179524a2c11d97`,
freezes 57 proposed postimages: fourteen existing replacements and 43 new files.
It adds explicit editor enum 3 / capability 2035, exact 38-field facts and the
separate thirteen-field editor Build/configuration/provider contract. Pixel and
physical generated spelling, facts and plans are preserved; their adapter-row
hash changes create truthful new source identities. All 134 joined pure fixture
methods passed, zero failures/errors/skips, with 214 isolated input hashes
unchanged. A separate postflight corrected the checker's misclassification of
its exact owned runner; the original receipt and earlier prerequisite failures
remain preserved. The postimages are not promoted while the fifteen producer
inputs remain read-held for the actual pixel operation. No actual source/reuse
admission, SDK tool, WebCore compiler, link or runtime belongs to this packet.

### TUI action, editor host and neutral component observations

The first two TUI action scopes are frozen in
their combined handoff (`.agent-work/appended-implementation-20261016/tui-document-actions/FINAL-FREEZE.json`),
SHA-256 `d38e9c1fe848b464640145a1c60935f5c9970979544e708c9d23a1235e5e240c`.
The coalesced observation poll passed sixteen component cases / 815 assertions,
preserving the eleven old case bodies. The new document-action codec passed
seven groups / 9,352 checks, the unchanged old codec eleven groups / 3,627
checks, and metadata five methods, zero skips. These establish polling and the
explicit 4083 action contract/codecs, not connected native link/button/focus/
selection/single-select runtime behavior. The later UI, transport and native
source scopes are implemented with separate component evidence below; no
engine-backed TUI runtime pass is claimed.

The TUI consumer freeze (`.agent-work/appended-implementation-20261016/tui-action-consumers/FINAL-FREEZE.json`)
`321fa070…` records seventeen Controller groups, 53 Forms cases / 5,506
assertions and 24 App processes / 4,192 assertions, zero skips. The
transport freeze (`.agent-work/appended-implementation-20261016/tui-action-transport/FINAL-FREEZE.json`)
`fe39d23f…` records fifty fresh processes, including the independent actions
Owner and twenty Driver cases plus the preserved old Owner/Driver/editor scopes.
Command10 and its separate ACK11, global form/body debt, single-select chooser,
focus/activation/selection and fresh paired-query gates are implemented. A
separate passive finalizer corrected a dependency-key normalization error after
all fifty cases had passed; it did not rerun or relabel the original aggregate.

The native document facade (`.agent-work/appended-implementation-20261016/native-document-actions-composition/FINAL-FREEZE.json`)
`79b119b9…` passed 21 processes / 1,128 assertions, preserving all sixteen old
case bodies / 815 assertions and adding five cases / 313 assertions. Its exact
4083 admission is independent of old pixel facts. The successor reused twenty
verified objects, compiled zero objects and linked once in 3.463 seconds. The
previous attempt's three successful compiles and postflight failure remain
separate. These checks use mock providers and establish no actual WebCore/native
DSO, installed runtime, GUI backend or HTML TUI qualification.

The separate
editor App/host handoff (`.agent-work/appended-implementation-20261016/ndv2-editor-host/FINAL-HANDOFF.json`)
has SHA-256 `f649f722553ca4f89060ab15e9ffe27a9594ed9e6254818fb26d326399d7ff8b`.
Its actual App passed fourteen fresh processes / 18,972 assertions, the actual
host C API four processes / 81 assertions and generic composition seven groups /
161 assertions, zero skips. Real Owner/Registry/Adapter code used explicit mock
producer facts and callbacks; the exact C++ facts range also passed the actual
JavaScript decoder. Four symbol closures excluded VM/Module definitions. These
own-pin component results ran no actual engine, browser, SDK or kernel and do
not replace the older App/component receipts.

The original neutral editor supported run remains aggregate-failed: all six
inner CTests passed, but its result parser misread the codec's
`SUMMARY cases=16 failed=0 checks=26193`. Passive postflight 001 also remains
failed at its eleven-only dependency-record assertion. The separately versioned
passive postflight 002 (`.agent-work/appended-implementation-20261016/editor-neutral-supported-integration/postflight-002/ROOT-CLOSED-RESULT.json`)
closed passed, session 41167 / 8.4559 seconds, with result SHA-256
`d0bba36bead5f82917292934532a33e043130436e09eaff931f0e8021ced560e`
and outer SHA-256
`28f5c13f36a5e511f12e7cd385098ccd4fb5f21a771febb93d1937b43329ea02`.
It reused the original six exact CTest XML/stdout results without rerunning a
test, build or binary. The audit checked all eleven compiler and six linker
dependency records, source/cache identities, four archives, six executables and
symbol closures. New product digests belong to this closed-artifact postflight;
the original failed aggregates and their capture/provenance limits are preserved.
No App, Owner, Driver, actual engine, browser or OS IME runtime was qualified.

### Native source and current retained-producer operations

The frozen native recipe's 95 source files passed thirteen source tests,
including seven LANGUAGES NONE/intercepted CMake policy cases, zero skips. Its
source handoff (`.agent-work/appended-implementation-20261016/native-engine-source-implementation/HANDOFF.json`)
has SHA-256 `4d0f5ba506e0f1a67ac28571aa6d90f36ee4d12771ed87d40902558a47d37f74`.
This is source evidence only. The subsequent
bootstrap design handoff (`.agent-work/appended-implementation-20261016/native-engine-bootstrap-design/HANDOFF.json`),
SHA-256 `3bf870658dc153a948f63974a4c102556713c66529c32d8a28b7611285b72548`,
records no executed fixture tests. The subsequent
Source3 implementation (`.agent-work/appended-implementation-20261016/native-engine-bootstrap-implementation/HANDOFF.json`)
freezes 127 source files / 2,680,357 bytes, source freeze `58a5d8ab…` and map
`9ffcf873…`. Its 45 pure metadata tests and 21 fresh Guard/one-shot-bootstrap
cases plus generated native64 header compile passed. The old-Gate
counterfactual failed as expected. The original setup failure executed zero
runtime cases; its preserved successor corrected directory enumeration and file
modes without weakening inventory checks. No actual WebCore/native provider DSO,
SDK production or native runtime was built. The pixel recipe stays frozen; the
new native4083 recipe and native bitmap host integration are separate source
work, with actual runtime and platform qualification still outstanding.

The separate legacy raw-export successor
source-copy operation (`.agent-work/appended-implementation-20261016/retained-raw-exports-materializer-v1/ROOT-CLOSED-RESULT.json`)
closed passed, session 14045 / 35.527 seconds: 43,083 files / 1,390,262,636 bytes.
Its result SHA-256 is
`8328f52504b9b5b0ac04e501bdecc34f6b0589799da056320e0722bfb63a6160`.
Its separate pure plan (`.agent-work/appended-implementation-20261016/raw-export-successor-plan-v1/ROOT-CLOSED-RESULT.json`)
passed in 88.404 seconds, plan `ff2259a6…`. The subsequent
raw-export candidate (`.agent-work/appended-implementation-20261016/raw-export-successor-candidate-v1/ROOT-CLOSED-RESULT.json`)
closed passed, session 56469 / 773.274 seconds. It imported 23 checked original
objects, compiled only the metadata shim, updated/read back five archives and
linked once. Static inspection verified the required raw Wasm exports; result
`f58ec9e8…`, build receipt `d0450a12…`, inspection `98bc506a…`. The actual factory
is `0a3d0fe4…` and Wasm `8b6615b2…`. Complete retained namespaces and canonical
producer pins remained unchanged. This new pass leaves the failed v3 evidence
unchanged and supplies no runtime, Foundation kernel or eligible SDK proof.

The actual supported modern pixel
pure plan (`.agent-work/appended-implementation-20261016/document-pixel-plan-v2/ROOT-CLOSED-RESULT.json`)
passed, session 38401 / 95.2607 seconds, binding plan SHA-256
`1223f748831ef73379d69eb51ab08448e5dc4693477c175cc6f2ba5db1c7f8c7`.
It admitted the exact maintained source/SDK/reuse inputs for 29 selected objects
and six replacements without executing an SDK program. The subsequent bounded
29-object candidate (`.agent-work/appended-implementation-20261016/document-pixel-candidate-review-v2/supervision-v3/ROOT-CLOSED-RESULT.json`)
closed passed, session 61022 / 944.988 seconds: all 29 compiles, five archive
updates/readbacks, one link and strict static inspection. Its outer result is
`8bfec6e3…`, build receipt `995f9300…` and inspection `f7f0b5c5…`; actual factory
`3d2fd0e4…`, Wasm `3efe36cf…`. Root independently checked the primary artifact
hashes, nineteen producer/entry pins and clean closure. These are actual
retained incremental engine builds, not a native OS port, editor2035 build,
Foundation kernel, runtime or release qualification.

Both producers released their canonical input holds after closed postflight.
Root then promoted all 57 exact editor postimages (fourteen matching preimages
and 43 new targets), with complete byte readback in
the promotion receipt (`.agent-work/appended-implementation-20261016/editor-recipe-implementation/ROOT-PROMOTED.json`).
The original 134 pure-case receipt retains its isolated source identity; promotion
did not run an editor producer or compiler. New editor source/reuse preparation
and a separate bounded runtime probe are subsequent operations.

Runtime attempt 3015 closed failed after 2.959 seconds: the two Node inert-import
and unsupported-environment controls passed with zero Wasm instantiations,
compilations or host/network callbacks; the sandbox denied Firefox's local
Marionette socket before browser creation. Browser assertions executed: zero.
All writers closed and all 54 input identities/bytes remained unchanged.

The separately authorized v2 runtime closed failed, session 21465 / 23.310
seconds, result `24112583…`. Firefox's native offline control returned
`NS_ERROR_OFFLINE`. The genuine DedicatedWorker engine passed all 31 author-page
assertions, including rich editing, Unicode, spreadsheet changes, timers,
resources, native-service calls and raster output. Its first native document
query returned an uncertain failure; forms and close checks did not run. All 62
input records remained unchanged and all writers closed. Source diagnosis found
that the fixture's displayed debug text exceeded the public text-field bound;
clipping it visually did not reduce the DOM text length.

The separate v3 discriminator (`.agent-work/appended-implementation-20261016/runtime-query-diagnosis-v1/runtime-v3/actual-runtime-v3/result.json`)
closed failed, session 51908 / 18.720 seconds, result
`03917932b899081cdf8bbaab8c2e1f0769ffcd7cdea860e45dcc6c0d20764e47`.
Only its displayed debug summary was shortened; the full report and all 31
author assertions passed again. The native document query then succeeded with a
7,546-byte paired document/control publication. The first native Begin request
returned an entered, indeterminate completion with a new publication, so later
edit, acknowledgement and close checks remained unexecuted. The source and
decoded publications identify focus changing the control's selection as a
sufficient cause; the first rejected capture was not logged. All 87 inputs
remained unchanged, processes and streams closed, and sampled peak RSS was
619,679,744 bytes. These are actual WebCore/JavaScriptCore observations with an
identified JavaScript host ABI peer, not a Foundation kernel or a passing
runtime aggregate. The shorter fixture is not a general long-text repair.

The subsequent joined Publisher successor integrated thirteen canonical files,
freeze `7241dcb0…`: shared Publisher `7d0b0ac9…`, native4083 Publisher `42fbb32a…`.
It bounds public text at a scalar boundary, publishes truncation without edit
authority, and admits Begin's selection change only after a second stable native
range witness. All other control/private comparisons remain exact. Eight
normal/optimized source/metadata invocations passed 268 unittest executions,
zero skips; all 134 historical inputs, including the old native pixel recipe's
121 files, stayed unchanged. The first check setup put temporary fixture outputs
inside the retained input root and correctly failed its alias guard. Its repaired
successor used an owned external temporary directory; no validator or assertion
was weakened. The new WebCore C++ still needs its actual retained compile/runtime.

The independent native4083 source release packet froze 205 files,
`65273f48…`. Its 57 metadata and thirteen source tests passed; nineteen inert
CMake configurations parsed the 28-TU graph without a C++ compiler. A separate
bounded Guard/bootstrap component compiled ten TUs and passed 21 fresh cases,
the expected old-Gate counterfactual and generated native64 header compilation.
It built no WebCore/native DSO or eligible SDK. The original pixel recipe's 121
files remained unchanged. Generic native Surface/capture pause handling passed
six Surface groups, three session groups and seventeen capture cases on freeze
`cc7b5dc1…`; this is component evidence, not OS input/IME qualification. Native
bitmap entry/adapters and metadata-aware close integration are ongoing work.
The source audit also found that native select popups and the selected
clipboard implementation were empty stubs. Their portable engine-side
implementations remain prerequisites, separate from release qualification.

The later generic native GUI integration passed a focused supported-entry scope
of 61 CTests, zero skips. Its aggregate receipt (`.agent-work/appended-implementation-20261016/native-gui-supported-v3/ROOT-AGGREGATE.json`)
has SHA-256 `1322936760329c178c7fe0e2dd53da6f38d4a12ebe5e74289a863462e977d9b6`.
Original source `83df5405…` compiled 37 C/C++ units and passed sixty checks;
the framebuffer fixture stopped before assertions because its registration
omitted the output directory. Only that CTest command changed in successor
`ef3c1a49…`. Its corrected supported-entry check passed all 69 assertions with
no compiler/link work, retaining the sixty original results and their identities.
The actual prerequisite inventory contained no guest VM or rich-engine compiler.
An earlier snapshot setup lacked the complete default GUI archive inventory and
stopped before CMake; the actual run used the separately verified supplier tree
`f0d23fe8…`. All processes/streams closed and frozen source/GUI inputs stayed
unchanged during each run. This covers Surface/capture/framebuffer, legacy
provider guards, nine4083 App cases, twelve native bitmap facade cases and
selected entry/UTF-8/close paths. It executes no native toolkit, rich provider,
Windows, OS IME, eligible SDK or release matrix.

Separate source-bound components passed 749 entry cases, seventeen SDL groups /
202 assertions, eleven FLTK frontend cases / 67 assertions, ten FLTK close-loop
groups / 3,264 assertions, and seventy Rev fake-window assertions. Real retained
headers and typed-runner declarations parsed; ordinary runner bodies remained
unchanged. Those explicit mocks/header checks do not prove a real window, Rev
module graph, native rendering, XIM/IMM or Windows operation. The portable
clipboard postimages subsequently passed thirty std-only cases / 776 assertions
in their isolated packet; that observation supplied no WebCore compilation or
actual clipboard runtime evidence.

The subsequent shared UI union is now canonical, freeze `5f0bf939…`: 52 source
destinations, nine metadata files, two recipe READMEs and four focused test files.
Normal/optimized runs passed 194 source/metadata tests with zero skips in 7.546
seconds. The popup owner/controller separately passed nineteen cases / 145
checks and 49 cases / 2,873 checks with exceptions and RTTI disabled. The native
recipe rejects a shared/imported WebCore target so its private callbacks have one
static link owner. Pixel-only sources and joined Publisher repairs stayed intact.
The rich profiles select 45 physical or 51 editor objects; editor preparation
declares 365 inputs and 367 physical files; subsequent assembly is recorded below.
Root independently reread all 67 installed files with unchanged hashes, modes
and physical identities, receipt `4e118de0…`. Editor source authority is
`f314602a…`. These are source/component passes, not a passing rich-engine runtime. The shared
owner has one process lifetime: navigation preserves clipboard values, while
ordinary view close does not claim synchronous clipboard clearing.

Fresh retained preparation then passed in 86.303 seconds, caller session 6947 /
exit zero, with all three phase owners and streams closed cleanly. It assembled
365 inputs / 367 files and independently copied 42,779 reuse files / 861,802,853
bytes, preserving 2,076 original archive members and selecting 51 objects with
sixteen whole-owner replacements. Actual recipe `18454771…`, source manifest
`82f94be1…` and reuse proof `b616f79a…` are bound by Root's closed receipt
`09e629311a1aa8edb665b554eb730303850958c7a140304d7e9a546fed536f5b`.
No SDK program, compiler, linker or runtime ran; actual WebCore compilation and
runtime checks remain outstanding.

Fresh SDK admission subsequently passed in 17.458 seconds: 19,426 files /
2,871,026,200 bytes were checked against the maintained verifier and fresh
physical/hash facts. Exactly three qualified compiler-tool hardlinks are allowed
only in that SDK; source/reuse files retain their ordinary-file rule. The initial
admission failed before verification because its generic rule rejected those
known hardlinks; it remains a failed attempt. Fresh SDK freeze SHA-256 is
`70a212519bfa3a953b083f440ecd0e80f6754feb2f542ddb6d618ec48a36846b`.
No SDK program ran.

The concrete compile-free editor plan then passed, actual session 58104 / exit
zero, within its 240-second activity bound, with clean owner closure and unchanged
62,607-file input postflight. Exact elapsed time was not recorded. Plan SHA-256
is `3484aa4430c6f2aaca95f1f2ea19689652d08e45e3655d6c4becaf31d62db177`
(15,132,900 bytes). It selects 35 direct units and sixteen whole-owner replacements,
preserving 2,060 opaque archive members. Root closure is
`.agent-work/appended-implementation-20261016/editor-rich-ui-actual-plan-root-v1/CLOSED-RESULT.json`,
SHA-256 `ee56cf0a8e952fa982e4441f9be5849fae04cef3e5c3cea85fdb80ac471b6f8a`.
This is a plan pass, with no compiler, linker, runtime or production eligibility.

The first actual 51-unit build attempt, session 34446, then failed before any
C++ compilation. Metadata generation correctly required the four editor input
files to have the `interface` role; the prepared recipe declared them as `source`.
Their paths and hashes were present and correct. One JavaScriptCore archive
repack/readback ran in parallel before Ninja stopped. The actual shell time was
495.299 seconds. The owner closed with primary exit one, no outliving descendants
or cleanup error, and the complete 62,614-input postflight passed. This is a
failed build, not an engine pass. Its original outputs and input identities remain
preserved under
`.agent-work/appended-implementation-20261016/editor-rich-ui-actual-build-root-v1/FAILED-RESULT.json`;
the original controller result has SHA-256
`67bb0356b0d84348048cea325f445c37eca6d3514ec3d0b081eeb249942afe6b`.
The subsequent fix changes only those four import-map roles to `interface` and
adds strict path/role/hash admission before expensive source, SDK or reuse walks.
The source, maintenance and metadata suites passed 37, 42 and 32 tests respectively,
zero skips. A real maintained-map → assembler → unchanged generator test first
failed on the old roles, then passed with the correction. Independent source
review is
`.agent-work/appended-implementation-20261016/editor-rich-ui-candidate-proposal-v1/successorfix-v1/review/REVIEW.json`,
SHA-256 `b7c0c853c20ce747fa3d07b09b867531ffcb09e6e4f606a24607254ffb7beaba`.
Fresh preparation then passed in 88.247 seconds, actual session 13259 / exit zero.
All three supervisors closed cleanly. The actual retained generator admitted all
eleven interface paths, roles and hashes after source assembly and before reuse
metadata/copy. New recipe SHA-256 is
`c748f946947e19fbb2ad06b769cc545b5369b5a124b8cbc2d57b2d265c4e1fd1`;
source-manifest SHA-256 is
`dc447d4ba3cb154e7fafcb305e098d54b9f6790d6cee4d6d85068be72bad1061`.
The prepared source has 365 inputs / 367 files; the independent reuse copy has
42,779 files / 861,802,853 bytes. Its newly derived proof remains the same
`b616f79a…` because the compiled source selection and reuse authority did not
change. Root closure is
`.agent-work/appended-implementation-20261016/editor-interface-role-preparation-root-v1/CLOSED-RESULT.json`,
SHA-256 `1fa91988f6dbe489d5ffe0ef520258566fb84fe7d43c6a526d1d35b7a047cd7a`.
The corrected compile-free plan then passed in 146.889 seconds, actual session
63730 / exit zero, with clean owner closure and complete 62,609-input postflight.
Plan SHA-256 is
`47133177a210903fc1a70e7940b84e11da5ec21d6dda9f311a631710002ccc62`
(15,132,912 bytes). It retains the 35 direct / sixteen replacement selection and
2,060 opaque archive members. Root closure is
`.agent-work/appended-implementation-20261016/editor-interface-role-plan-root-v1/CLOSED-RESULT.json`,
SHA-256 `810f8331fa4702be6742dcfec3479c9a5999646b9906d5d0a25551351787d9b5`.
The corrected build, actual session 43733, subsequently closed failed in 533.598
seconds. Metadata admission and two translation units completed; the clipboard
translation unit rejected a named lambda because this WebKit version's
`WTF::Function` converting constructor accepts rvalues only. All 62,616 frozen
inputs passed postflight, with no outliving descendants or open writers. Result
SHA-256 is `cefb515eea80ff5cc5c7b48b2a7ab0c8ad3434c53b0e143a48c121516689f02d`;
Root failure closure is
`.agent-work/appended-implementation-20261016/editor-interface-role-build-root-v1/FAILED-RESULT.json`,
SHA-256 `e99af1d3a0c7071d66644c27e3f5763ab5e9f5a4ee70924208f2e022a22a99c1`.
The same repair was applied to the native and Wasm clipboard sources. A separate
actual-header object check then passed in 11.309 seconds, with unchanged 2,527
dependency/control files and retained-input continuity; it performed no archive,
link or runtime operation. Its Root closure is
`.agent-work/appended-implementation-20261016/editor-interface-role-build-root-v1/SINGLE-TU-CLOSED-RESULT.json`,
SHA-256 `ef94adb997db22fa1250f8433e12c97f461a0e18ccd7c0ff8d478d40b037b1ca`.
The repair's six import/projection/provenance maps and the native profile were
then updated without changing unrelated rows. Focused source, maintenance and
metadata checks passed 111 normal and 111 optimized tests, zero skips. Their
result SHA-256 is
`b44e0bf9cdd6f64d81330e56ebe47e5ad56618b59d3d34d2a1690b2f453a673c`;
the final source release is
`d5d3b0e0a3650ca864e71174d76f93edc64c15a6a413a155fe3cf7876a39f2db`.
Fresh source/reuse preparation then passed in 90.432 seconds, actual session
50153 / exit zero, with clean closure of all three supervisors and admission of
all eleven interfaces. The actual recipe is
`54a788dee93793a5600ee1d44c78d7380f2c402e873bc808b51ccd3e5936cf13`;
source manifest is
`a49621cf9adabfffbb0e22cf3d09e61b8828a7c1ee5ab20fcbdc87b34bd4b742`.
The 365 inputs produce 367 files / 564,411,698 bytes. The independent reuse copy
contains 42,779 files / 861,802,853 bytes and a newly derived proof
`f7d6dd6b1bd82e022d809d67b3d298bb7255f7ef5cd73ed1417b3cc30dd242bc`.
Root closure is
`.agent-work/appended-implementation-20261016/editor-clipboard-successor-preparation-root-v1/CLOSED-RESULT.json`,
SHA-256 `27ab8032c902792cf6b20998c7fc16a92d51f3f63109b61b2505a095629d31ad`.
Preparation executed no SDK program or compiler.
Its compile-free plan passed in 161.009 seconds, actual session 23435 / exit zero,
with all 62,612 frozen inputs unchanged and clean supervisor closure. Plan SHA-256
is `aafb6bd64a4977250e44a6bdac55d5c3b08a3fe76352ba9dd3e967dff9101e12`
(15,132,932 bytes), retaining the same 35 direct units, sixteen replacements and
2,060 opaque members. Root closure is
`.agent-work/appended-implementation-20261016/editor-clipboard-successor-plan-root-v1/CLOSED-RESULT.json`,
SHA-256 `498231e8f6e56c4009943a0b2463173565af22078cbec8c384b310157493925c`.
The fresh 51-unit incremental build, session 65363, closed failed after 725.110
seconds, using two jobs, a 2,700-second inner deadline and a 3,300-second enclosing
deadline with thirty seconds for cleanup. Its armed packet is
`c3325d05de7086b970ceabd21acd5680496be1f5687cc822856bfc2ae827ebb8`.
Independent command reconstruction compared all 19,141 compiler tokens, 39
metadata tokens, 186 linker tokens and 2,076 ordered archive members. This
build completed configure and left 26 object files before the physical adapter
failed compilation: two calls to its namespace helper were hidden by inherited
members, and the wheel-processing enum definition was not included. All frozen
input postflight checks passed; the qualified child exited one with no outliving
descendants or ownership errors. Root failure receipt is
`1dd51140d6765493ea4859b48ccf5f328ddb8f420e1ada2f39905e18dcff6db1`.
The three maintained physical-provider copies now qualify the namespace helper
and include `ScrollingCoordinatorTypes.h`. Source/provenance checks passed 37
normal and 37 optimized cases, zero skips, with all 210 recorded inputs unchanged;
source release is
`6c5f326eaa1378f81e39dddf676b83b2a868efb9b5d223d72e07a13b063c11cc`.
The next actual-header probe, session 16713, closed failed in 9.861 seconds.
Only the primary physical-provider unit ran; the other 24 were not executed.
The original four errors were fixed, but `Frame::page()` and `LocalFrame::view()`
needed their inline-definition headers. Its qualified compiler owner closed,
with no outliving descendants or ownership errors. Both fresh-input checks and
all 62,619 held-file / 3,785-directory continuity checks passed. Root failure
receipt is `e5dc688e780954ed5781a6c081a79d66203e9bb88854fde3ac64c6ac4d5610f6`;
result is `b9c07c8b895a26754caece60741be61ec2316255f61c08d43c53bc0c87a8ddf3`.

The three maintained copies now also include `DocumentPage.h` and
`DocumentView.h`. That separate source successor passed 37 normal and 37
optimized source/provenance cases, zero skips, with 210 inputs unchanged;
release is `040c706bb1f81b020af44664560d722618fc37fda2354117c47edd37491441a6`.
The next actual-header probe, session 33218, closed failed in 24.419 seconds.
The physical provider compiled successfully. The document publisher then failed
with two incomplete-type errors involving `TextControlInnerTextElement`; the
concurrently admitted `main.cpp` was terminated and joined, and the other 22
units did not execute. All compiler owners and streams closed, with unchanged
1,617 freshly hashed inputs and all 62,619 held files / 3,785 directories.
Result is `089aa5b0b978fcb3b06af7135aca1181ac1ed30fc364cdd1ec0981a170125bc0`;
Root failure receipt is
`fc4fb3dbeed7c4037f09ecdd740b5d931192cb80b47d2d2cfa810567ff409007`.
No configure, archive, link or runtime step ran in either probe, and their
objects are not admitted for reuse.

The active document-v2 and native rich publishers now include
`TextControlInnerElements.h`; the unused legacy publisher remains unchanged.
The source/provenance successor passed 37 normal and 37 optimized cases, zero
skips, with 210 inputs unchanged; release is
`b3b2ca57ffa321b258e7fe281a060a3ba4839b170ece9b047425ccecf73f24bb`.
Actual probe 71154 subsequently compiled both the physical provider and
publisher, then failed in `main.cpp`: its portable digest header used `throw`
under `-fno-exceptions`, and an optional page identifier was treated as a value.
The bridge sibling was terminated and joined; 21 units remained unexecuted.
The run closed in 30.259 seconds, with all 1,620 fresh inputs and 62,619 held
files / 3,785 directories unchanged. Result is
`4c0d8e71083f3dccf6a51d74e04b9f69cdce4beb459c6359a12351e0c11fdf43`;
Root failure receipt is
`4f6999b7441eb8245f6ed7fc3f3e20fb6e7cb16ba36e14d62def08bdb053da54`.
No configuration, archive, link, runtime or object-reuse admission occurred.

A source repair replaced the invalid constant-evaluation throws with compile-time
rejection compatible with `-fno-exceptions`, and checked the optional page
identifier before dereferencing it. The five maintained source sites and derived
records passed 39 normal and 39 optimized source cases, with zero skips. Six
standard-only compiler checks also passed, including four expected rejections of
invalid digest literals; source release is
`6114fd1cb9f4a609ad747ab1f9e2ceef801d09683196957a4a33e04f7ea3eb7c`.

Actual probe 64277 then passed fourteen units, including the repaired main, before
`NativeRawKeyDispatch.cpp` failed at two uses of `WTF::Latin1Character`: the
retained engine declares that type in the global namespace. The forms sibling
was terminated and joined; nine units were unexecuted. All sixteen admitted
compiler owners and streams closed in 72.944 seconds. The 1,628 fresh inputs and
62,619 held files / 3,785 directories matched before and after. Result is
`345704fb95ff489ba3aee7adba8ec03f82a15296b25c1ab7b714f48407277d71`;
Root failure receipt is
`3e3f41c0554876121a4cb6b16a0dea41ca51034ab93495f9dde091d9b0db17dc`.
The raw-key repair adds the defining header and uses the retained engine's
global type. Its successor passed 40 normal and 40 optimized source cases, zero
skips. Actual probe 60542 subsequently passed seventeen units, including raw-key,
then failed in `BibNativeEditorBackend.cpp` at a nonexistent singular header name.
The forms sibling was terminated and joined; six units did not execute. All
nineteen owners and streams closed in 73.040 seconds, with 1,632 fresh inputs and
62,619 held files / 3,785 directories unchanged. Result is
`87f45663813eac08dd4bcaedcb8d082204712e96c36811a0c2748150af808283`;
Root failure receipt is
`102f8ffe6b75529454f28a1edb482ad1fff4ec8654932db15f3cea814c6da15f`.

Both active editor copies now include `TextControlInnerElements.h`. The source
successor passed 41 normal and 41 optimized cases, zero skips; release is
`2ddd19e30c141379fa84916abb78d1c9a0ffd58c909d4520da028f967be2660e`.
The normal tests completed and their owner closed, but the reporting controller
then looked for the wrong output filename. Its failure remains preserved; the
completed normal output was recovered without repeating the tests. Only the
optimized run has a separately retained complete supervisor report. Neither
source pass compiles the repaired backend. Actual probe 77118 then closed failed
in 24.571 seconds at one C++ variable redefinition in the primary editor unit:
the text-event `if` initializer remains in scope through the composition `else`
branch. The other 24 units did not execute. Its qualified owner and log closed,
with all 1,635 fresh inputs and 62,619 held files / 3,785 directories unchanged.
Root checked every reported product; failure receipt is
`c3fd65dd6b77d79b3ac01a44d32ca4170ed290e10e75aa1880738e7cdf20464a`.
The composition-local rename is now implemented in both active copies and passed
42 normal and 42 optimized source cases, zero skips, with both qualified
supervisor reports retained and all 234 snapshot inputs unchanged. Source release
is `742dd6150df7bd127e49414541cb899d3bde028241fb7df2c0763c329db5b2b8`.
Actual probe 82501 subsequently closed failed in 21.626 seconds: the local scope
error was fixed, but three inline definitions were missing for `Frame::page`,
`LocalFrame::view` and `Element::hasAttributeWithoutSynchronization`. Only the
primary editor unit ran; the other 24 did not execute. All owners/streams closed,
1,635 fresh inputs and the complete held namespace matched, and every reported
product hash was checked. Root failure receipt is
`b6f3789945246c2fc5d24946d4dc92e1a77c697a31cc090265c6aa4ffe7efc38`.
The defining-header repair then passed 43 normal and 43 optimized source cases,
zero skips, with both qualified supervisor reports and 234 unchanged inputs.
Source release is
`352e3a4e229b513d650534d6b94d9b4439fda70c8b3bf7093c95dd0b5ef6f546`.
Actual probe 60883 compiled the editor backend, wire adapter, codec, text
projection and UI owner successfully. It then failed at five missing inline
definition headers in the popup adapter. The forms sibling was terminated and
joined; its incomplete compile is not a pass, and eighteen units did not execute.
All seven owners and logs closed in 40.728 seconds, with 1,635 fresh inputs and
the complete 62,619-file / 3,785-directory held namespace unchanged. Root checked
every reported product's bytes and hash. Result is
`98e7ea2f52ef9934c0c909e249eff5a4cc71ae1a811782b24788ad5e53b19e6b`;
Root failure closure is
`1bb66c5966d1dc67d4f2b32e6c62a3e0a79acd0de788d6463f147ceeb417f4fc`.
The popup successor adds only the five defining headers in both active copies.
Its nine-file source/metadata/fixture change passed 44 normal and 44 optimized
source cases, zero skips, with all 235 snapshot files unchanged. Source release
is `bb718170a2f0c6712e668e5702faff7fcba7bee99240647db58053a88d4b74f0`.
The complete focused batch, session 12732, then passed all 25 C++ units in
126.131 seconds. All owners and logs closed naturally, with zero failures or
outliving descendants. Preflight and postflight matched: 1,638 freshly hashed
files / 176,647,622 bytes plus the complete 62,619-file / 3,785-directory held
namespace. Root reread every reported object, dependency file and log: 75
products / 13,308,493 bytes, all matching their hashes. Peak aggregate RSS was
2,891,370,496 bytes. Result is
`d5fbc70699916653fef7ff56dfaddf318f095bea43e223d100775b2d2a9e4839`;
Root closure is
`f934771d21582559a39474c84b36b2936c1ee66bdda33eaa87c61578c06390b0`.
This proves the focused source compatibility gate; it executes no configure,
archive, link or runtime. These probe objects are not admitted for reuse.
Reviewed continuation, complete engine link and runtime remain unfinished.

A separate read-only audit resolved 5,154 dependency paths for the 26 completed
objects. It identified 25 reuse candidates, including all sixteen engine
replacements. The metadata shim needs recompilation because it includes the
changed generated profile identity. Audit evidence is
`a292f4861c9c1bbd75c03875ec59786e3c66ac2bf0a2f74948de901b502ba6f6`.
This audit does not admit those objects for reuse. A later check found that the
portable-header change falls inside the captured searched namespace of 23 of
those objects. The strict continuation policy excludes them. A subsequent bounded
read of the two remaining compiler scripts closed failed: the retained
`RunLoopGeneric.cpp.o-ed54643.sh` is absent. Neither object was admitted; the first
script observation did not complete its transaction. The reader exited one with
one reaped process, no outliving descendants or supervisor error, and closed
streams. Result is
`03834c5f1adb79bd7c7d592851dcace2d72597af0a4ee47cb4626507b5d39f5a`;
actual tool closure is
`3acbfc573a106bd670fc5fe2e3135f16bec19a2fbdfba25888baf1804d5b3d35`.
The successor must compile all 51 selected units against the retained engine
base. No historical artifact repair, automatic reuse or cold fallback is allowed.
Complete link and runtime checks remain unfinished.

The reviewed continuation helper and CMake graph are now integrated, alongside
the private configure-include API and six explicit Windows command routes in the
supported build entry. Canonical checks passed 29 normal and 29 optimized
continuation cases, 42 document-maintenance cases and 37 build-helper cases.
One native Win32 case was explicitly excluded on Linux. Seven actual `build.sh`
help dispatches passed without configuring or invoking an engine compiler.
Promotion is `4973d1a66708deaa3babde1494671628c5980a314306adfce68023475e010992`;
focused checks are
`b54c146d246879e399dc5cde23aefe416095d7f905da4627b23a47c5fda6f1ff`.
These source checks do not establish an engine link or runtime.

A narrow maintenance-supervision successor now retains the actual owner and log
when settlement is uncertain, validates the complete supervisor report before
closure, and permits only one bounded cleanup before natural settlement begins.
Only the existing `_supervise` function changes; six baseline functions are AST
identical. Sixteen normal and sixteen optimized inert cases passed, and the
promoted source passed the existing 42 maintenance tests in 0.099 seconds.
Promotion is
`7fcfd53eaa9319deeafa0e85d36d3e638a91b2e28d33e4267b5976a6096080ed`.
No engine configuration or compilation ran in these checks.

The subsequent preparation, session 63075, passed in 120.965 seconds. Its source,
metadata and independent reuse-copy phases all closed naturally at zero, with
strict supervisor reports and all 246 frozen physical input facts unchanged.
The fresh recipe contains 365 inputs /367 physical files; the reuse copy contains
42,779 independent files /861,802,853 bytes. Root checked 18 named result metadata
records /30,083,362 bytes, including the complete original copy receipt and its
row counts. It did not repeat all 42,779 product body hashes. Result is
`7573bd431a128a76cd012ea9d340ee3fa7f52d9f12c277fe8ae969e9cc60bec9`;
Root acceptance is
`866110b4993d3bc98b25dbee07519129fcfb813cedfe7a0865f922bd31eb76c8`.
This executed source assembly, metadata derivation and copying only.

The subsequent compile-free plan, session 61856, passed within its 240-second
work limit. Its original supervisor report records one reaped process, no error,
outliving descendants or termination, and closed owner/log streams. Full frozen
postflight passed for 62,614 files and 3,785 directories; peak sampled aggregate
RSS was 376,795,136 bytes. The emitted 15,132,984-byte plan selects 35 direct
objects plus 16 engine replacements and retains 2,060 unchanged archive members.
Plan SHA-256 is
`953a4f47bc524d7410c58710f49b5254bf44e0821255b650bfd409c75eb4b8f7`;
result is `28cb719801836cedc5bc28245ced57e1bde205914325a0b65b8a357aeca0bad4`;
Root acceptance is
`e132a9b5e73066f836d4c03559b97e3ba7ee2e4012a670be4ba0676d494bc861`.
All 51 units were selected for fresh compilation. The bounded build, session
24546, failed at its combined aggregate RSS/process limit under the reviewed
two-job, 2,700-second inner /3,300-second outer limits. Its last accepted sampled
RSS was 4,280,528,896 bytes; the rejecting sample was not persisted, so this does
not identify which part of the combined limit fired. The original cleanup report
records primary return -9, ten reaped processes, termination, no outliving
descendants and no supervisor error. Owner/log closure and complete input
identity/namespace postflight passed. Result SHA-256 is
`07b77fbb0d38479d323678c77eaea00438c3e852a4d51d580eba0019aa5c5e09`;
Root failure observation is
`d71c64639b41b6f6efd3ce23bbd0c1368c9cb9d362a163d4290bdd51881384fc`.
Configuration completed and compilation began; no complete compiler/link pass,
partial-object admission or runtime pass is claimed. The separate one-job
successor, session 6290, completed all 51 fresh compilations and linked in a fresh
output tree, with zero imported objects. Its
2,700-second inner /3,300-second outer work limits, single 30-second cleanup and
resource caps remained unchanged. The maintained build returned zero with natural
process closure; complete input postflight passed and peak aggregate RSS was
2,736,087,040 bytes. Its outer readback failed because the checker still expected
`--parallel 2`, while the actual command correctly used `--parallel 1`.
The original failed outer result is
`3b247bde2be45115d6141d5d6d2ed17c2fcbf5993873a001035543f2d4dd4107`;
Root execution observation is
`6fe22d439e8fbaa6076edb3fbf89de45e46ea1df6f1b9a65bad4bb1bc48f2b00`.
The corrected passive readback, session 81951, subsequently passed against those
same closed artifacts without compilation. It checked all 51 objects, five
archive reports, 2,060 unchanged retained members and the static Wasm/factory
contracts. Caller, child and logs closed naturally; input postflight passed.
Peak aggregate RSS was 285,134,848 bytes and explicit reads totaled 520,717,067
bytes. Root acceptance is
`fda45ea612c3b1ed86ed3b0edc98fb631fc64caeb8d27562c2a44fab849a9bb1`.
The original outer failure retains its identity. Runtime remains unrun.

The isolated binary-view model and old application check, session 2662, passed
two CTests containing twelve model cases and six existing application cases,
with zero skips, in 43.655 seconds. Source facts remained unchanged and the
actual owner and logs closed naturally. Receipt is
`4c777954bf944768a885f1b6355a404b72d4848b0ca3d3297b4bb26deb01e8b3`.
The initial attempt stopped at a constness compile error before CTest; it remains
a zero-case failure. These focused results do not establish the rich engine,
combined kernel, guest compiler or browser runtime.

The concrete module-binding check, session 78932, then passed seven cases in one
CTest, zero skips, in 37.715 seconds. It exercises one real tiny Wasm module's
provider, view, service, publication acknowledgement and failure paths. The same
C++ leaf also compiled with view capability disabled and without GUI includes.
Natural owner/log closure and unchanged source checks passed. Root acceptance is
`847aefb6f8e5b5b2074a1b85634f068b2cc36065b69dafb1fec7eaba97c11370`.
This focused fixture does not execute the rich engine or combined kernel.

The separate recorder-only CMake/Ninja attempt, session 28246, passed once with
all 48 original-command captures joined: 19 compiles, 14 archive creations,
14 index operations and one link. All 51 supervisor reports and logs closed at
zero; eleven selected sources, three host tools and the armed input remained
unchanged. The parent reread 407 saved records. Combined outputs were 1,413,674
bytes /449 files. Root checked all seven named result metadata records and
accepted the closed index
`37d87f9cb4f3ea3608f7924087c7da3549d2c93945c53d0cd0df5700edbbb173`;
Root acceptance is
`5ebade19601c2876bc3de56dc0434e78dda0d71f447ecccde033c0170a51cd2c`.
The initial passive readback selected the factory path instead of the Wasm path;
its failure is preserved, and the corrected read required no tool rerun.
Only inert recorder objects and markers were produced. Original-engine and SDK
identity bindings, real Foundation compilation and runtime remain unfinished;
these captures create no production eligibility.

The combined-profile recorder check, session 68568, also passed. Its 73 calls
were 36 compilations (14 C and 22 C++), 18 archive creations, 18 index operations
and one link. The parent checked the original argument/cwd joins, all 76 strict
closure reports and unchanged eleven sources/three host tools. Final closed
storage was 2,250,890 bytes across 683 files; the earlier inner storage snapshot
retains its original identity. Root acceptance is
`7e36ddb93962e1ab4716a51f054d9b0167d61037c82595d02ae01f4fe825f153`.
These are inert tool calls: the actual SDK, Foundation compilation and runtime
remain separate checks. The parent reader's initial attempt to reopen depfiles
already consumed by Ninja is preserved; the corrected read follows the existing
immutable depfile-copy and historical archive-create/index contract.

A later source audit found that the private construction helper's unconditional
SDK implicit-link barrier exceeded the maintained contract. The maintained SDK
verifier checks the complete inventory; the Foundation receipt requires its SDK
identity and target, source identity, actual artifacts and runtime checks. It
does not require a trace of every consumed SDK file or archive member. The private
helper now has a source-reviewed successor using that existing contract, with
original command, environment and closed-build facts. Seventeen focused inert
cases passed, zero skips, on source `e3125b4a…`; result is
`ae3caf6d01743e77e71958f1592454bbd32a27ea71ae238341829cad8a4e64e9`.
Those cases exercise source joins, ownership barriers and removal of only the
private SDK gap; they do not supply a successful actual SDK/construction binding.
The original web-only evidence is not a BOTH build. Public validation and runtime
requirements remain unchanged. The unused tap prototype is neither qualified nor
activated.

The first native producer's source fixtures passed 66 normal and 66 optimized
cases; the input adapter passed 88 + 88, dependency producer 72 + 72 and SDK
adapter 67 + 67, with zero skips and unchanged declared inputs for each run.
These results cover synthetic inputs and inert inspection scripts. Later private
C++ runtime and diagnostic-host additions have separate source-bound passes:

- Prototype runtime repairs: 90 normal + 90 optimized tests, 9.836 seconds;
  closed dependency-inspection selector: 92 + 92, 10.094 seconds.
- Input-helper runtime hooks: 95 + 95, 4.308 and 4.521 seconds.
- SDK runtime/cohort and raw-output bounds: 89 + 89, 49.201 seconds aggregate.
- Dependency runtime/PIC handoff: 86 + 86, 3.823 seconds aggregate. The initial
  85-pass/one-failed quoting fixture remains preserved separately.

All these pairs have zero skips and unchanged declared input identities. Their
separate receipts and source closures are joined in
`native-prototype-decision-v1/private-cpp-runtime-implementation-v1/DOC-SNIPPET-SOURCE-JOIN-v2.md`,
SHA-256 `79a461aab61d98eeb12edd3808b524d154e31fb3df2a6b47735bf9a07ad39c72`.
Earlier input/SDK receipts retain their earlier selector identities. These checks
establish no native SDK program, dependency build, engine build or DSO execution.
The later source-role repair accepts only the canonical repository `tools/sdk.py`
under its repository-file contract, retaining its actual physical mode; SDK assets
and unrelated helpers retain their strict role checks. Explicit repository-root
forwarding has a separate fixture. That source passed 94 normal + 94 optimized
SDK cases and 96 + 96 input cases in 69.347 seconds, zero skips, with all 228
recorded source inputs unchanged. Closure is
`ef50d4af2449143f331c15fb340ee33b4e93082a5c2597b8276085cd1d96c29e`;
result is `58d95743a93dc0a2822e46fa42f4c5b9e020000f42b172d7f2e7fe886a350fae`.
The 380 registered executions used fake SDKs; actual restored-SDK admission and
native runtime are not established by them.

The two explicit native command routes passed ten normal and ten optimized
dispatch cases in 0.990 seconds, including named missing inputs and no implicit
builder fallback. Linux registration and non-Linux exclusion of the five new
tool suites passed inert CMake script checks; no compiler was initialized.

A separate read of the retained Linux SDK archive completed in 5.425 seconds,
verifying its complete compressed SHA-256 and retaining only the original
`sdk.json`. Its original metadata SHA-256 is
`dcb6d8dd7c13310b41fe13aae0a926b23c60de6c412d779122fa2cb879f1c894`.
It identifies the Buildroot compiler/sysroot and static runtime archive
candidates. That metadata read executed no SDK program and established no
restoration, inner library-body verification, compiler selection, shared-library
PIC suitability or native runtime behavior.

The subsequent supported SDK restoration attempt, session 5572, closed with
exit one after 54.445 seconds. Its enclosing and inner owners and logs closed
without uncertain ownership. The installation supervisor reported
`ProcessLookupError: [Errno 3] No such process` while sampling owned processes;
SDK success and an SDK-tool failure are both unestablished. Verification did not
run. The failed output remains preserved under
`native-prototype-decision-v1/toolchain-admission/sdk-restoration-implementation-v1/`;
Root failure receipt SHA-256 is
`49f1fd00d195ffaa3af41741ec46f7b9f365926f8245e5dda16f55b3e292c5af`.
The narrow two-sampler repair passed eleven pure tests. The separately reviewed
retry, session 76416, then passed the supported install and `sdk.py verify
--release` in 96.464 seconds. Installation took 82.028 seconds and verification
5.871 seconds, with clean process/log closure and the supported C++20 smoke test.
The installed SDK contains 1,244,479,505 bytes; all 272 original relocation
postimages passed. Manifest SHA-256 is
`03a037ab97a11d453056bdbf0f89398f9aac42bf20219e20aa6283e528c26cdf`;
Root closure is
`8ff93a05903d57facebba61136460cac85703a7d38c8b96cbd584c81d293bbfc`.
This establishes supported restoration only. Native producer SDK/runtime
admission and the dependency/engine builds remain unverified; the retained
producer remains unqualified for publication.

The producer's generated-manifest repair separately passed 99 normal + 99
optimized SDK cases and 103 normal + 103 optimized input cases, with zero skips.
These are 404 source-fixture executions across their original separate receipts;
an earlier enclosing run exhausted its budget and remains failed. The repair
admits the installer's independently pinned `sdk.json` at physical mode `0600`
through an explicit metadata role while retaining strict SDK asset rules.
Actual observer attempt 89250 then closed failed in 1.116 seconds, before either
compiler query: its SDK walk rejected the installed root's physical directory
mode. A bounded metadata-only discriminator found `0775` on the root and nine
manifest-derived first-level directories, consistent with the supported
extractor's umask inheritance. It made no recursive walk or SDK program call.
The typed repair now derives the exact SDK parent-directory set from the
independently pinned manifest, retains physical identity/mode facts and emits
logical `0755` for physical `0755` or `0775`. Generic inventory rules remain
unchanged. SDK source tests passed 105 normal and 105 optimized cases. Input
tests passed 118 normal cases and a separate optimized-only 118-case run against
the same source and complete case inventory. Join receipt is
`536ad877937a5d208600bc75fde73447f4609bb416fbfd860cfb00cfb1ae5583`.
The earlier 117-case fixture/stale-map failure and later enclosing timeout remain
failed; neither was relabeled by this join. A new observer/controller pair also
passed 120 synthetic executions with zero skips, closure
`517783cf4ef80c3a19bd412a921ee4a7d2b7dc104fc15563cd3142fff68d8739`.
These source checks execute no actual SDK queries. Actual observer 57867 later
completed both linker-path queries with zero exits and the same inventoried
linker. The inner observer closed after 58.991 seconds, but the enclosing
60-second deadline expired during final verification. The overall attempt is a
closed failure, with no accepted enclosing postflight receipt. Its completed
query observations and later named-source checks remain separate diagnostic
facts; they do not establish passing SDK/runtime admission.

A separate postflight-only record check then passed in 0.616 seconds, with a zero
actual exit, closed owner/log and unchanged declared inputs. It checked all
seventeen original named records, the completed inner result, original query
observations and raw streams, reading 29,590,569 bytes including repeats. No SDK
walk, compiler query or linker-body read was repeated. Record receipt is
`972dbd8f0bfe3fc56b688ede729a28a528550c250a9a1a59eb498fdd4a2309d2`;
qualified tool closure is
`f0ed5c256cf40280fdf7f04e180f64bc9ff9ced25c8a99563b40180a95c5cdd5`.
This separately joins the completed original observations; observer 57867 remains
failed. It creates no SDK admission, native build or production eligibility.

The later fixed nine-tool observation check passed in session 85226: nineteen
new metadata queries and two retained linker facts, with natural process/log
closure and complete SDK inventory/directory and selected-source postflight.
Work took 91.271 seconds; peak sampled aggregate RSS was 232,706,048 bytes.
Root acceptance is
`5b204df53fbeaf8f058c0dece0d3ad6647376863d09e93c63b8a334e40a0ff50`.
The preceding attempt, session 24032, remains failed: its final pkg-config query
could not find `dirname`, and a separate loop-variable bug selected the wrong
output directory. The successor fixes those two defects, exposing only the
explicit retained utility to that one query. This establishes the recorded
program metadata; SDK admission, native compilation and runtime remain separate.

The joined native-input source then passed 153 normal plus 153 optimized input
cases and 87 normal plus 87 optimized dependency cases, session 24062, in 32.868
seconds. All 246 selected physical facts remained unchanged, with zero skips and
closed owners/logs. Source release is
`cf26a7be50ac8bb2807f8a35ed737653a0bac5e59c5fd05f440fcd49cdee0fc1`;
closure is
`c2ca9bc5e6fc2ed39b6a14f6ded8da1674b866bfc9c72e729907ffc19ef46295`.
The source provides the explicit diagnostic-host branch, capture-owned supplier
record parser and normalized interpreter-data helper. Original diagnostic source
and launch authority remain absent and reject before extension-body traversal.
These fixtures establish no actual SDK program, native dependency build or engine
execution; the earlier SDK checks retain their separate source identities.

The native current-source API was subsequently extracted into a capture-owned
immutable value and a separate pure composition with a genuine original-source
projection. The promoted source passed all 166 registered input tests, with zero
skips, in 14.166 seconds; thirteen focused private cases also passed normally and
optimized. Promotion is
`8285fce1f95ee6ebd8f90e55b4771ac779d04328f8933bf9f7897544d9e0ae3c`;
canonical regression closure is
`1290289e65c0a14e4d2fcfff181dcd1006ceb0ddef298c956673ca9c2757abed`.
The first bounded current-capture attempt, session 99274, failed with `owned
process RSS unavailable`; that failure and its unaccepted outputs are preserved.
The narrow supervisor correction passed its focused normal and optimized cases.
It treats an exited process without an RSS reading as an incomplete observation,
and still requires actual process and log closure. The retry, session 37981,
passed: 197 mapped inputs, 157 overlays and 14 producer records were captured,
with all 212 worker inputs unchanged. The closed receipt is
`e2b8fe13fec16ad8a455c484a0ab651d72196842993374e5dfe845482bf02d0b`;
Root acceptance is
`59ab16a239fa7168744042e16518fb33cfbc59c0df020eb662f8cbb818d84574`.
Its saved success records do not contain the original six-field process report
or an exact elapsed time; neither is reconstructed. This establishes the bounded
current-source capture only. A subsequent same-process composition attempt,
session 30040, failed because its summary exceeded the 512 KiB limit. Its monitor
also refused a missing live-process RSS reading; the rejecting raw sample was
not persisted, so its PID/state/transition remain unknown. Qualified cleanup and
owner/log closure were confirmed. No summary was accepted. A separate compact
successor passed in session 98621 without increasing the 512 KiB limit. Its
6,404-byte summary joins the genuine same-process original 71,250-file projection
with the current 197-input map and 157 overlays. All 24 source and 249 metadata
postflight facts remained unchanged; 2,301 complete RSS samples peaked at
608,628,736 bytes. Parent closure is
`19e9a5e55db9c0230ba91462f255f49f5db1f2701c2735b7a15b6e4caff0a1f7`;
Root intake is
`5e91fad2bef8dffc1fe7f0d744642e67b27c4cac155f0133d26672b547651440`.
The saved result omits the original six-field process report and exact elapsed
time; neither is reconstructed. Reviewed strict closure order and the actual
zero caller exit establish the bounded closure. Source assembly, patch execution,
SDK admission and the native build remain unrun; production eligibility is false.

A separate bounded compressed-source copy, session 46792, passed in 1.364
seconds. Its independent 351,016,770-byte destination has the original archive
SHA-256 `ffc02dcdbd7fa2a58f72b4fb7f8cd5404df15bb8e6a348cd42206f1d4c7c76b8`.
All owners and streams closed and recorded inputs remained unchanged. Copy
receipt is `df7f56ba480259baac12bff36c8e6127accbbfae2d3e82e8176ea8fd8bf33929`;
Root closure is
`ff9e15982ec7db0498e00eefb6dacbce07f3ed78cbb110e3eec381bcb734fd77`.
This copied compressed bytes only; archive extraction, complete source admission
and native dependency or engine builds did not run.

A subsequent bounded admission, session 95611, passed in 48.707 seconds. It
hashed and checked the complete original engine/wrapper archive members and
provenance: 71,250 projected files / 1,090,762,998 logical bytes. Owners and logs
closed cleanly, all 59 named inputs remained unchanged, and no extraction, patch
execution, SDK program or compiler ran. Parent closure is
`5a0101a4bb6b4463a773a1e29a3768eb99bac50485b016fe1165aebcf2c4ab9f`;
the complete projection is
`88203ec0a3045db2692b9d865ea2c2ff2d0e3e1eea054ddb38e4c419c7f647cb`.
Root independently checked the closed metadata joins and projection counts in
receipt `0c9eb5415e0a67ee650f60332e44f6d159ada4dba74ebacfdb5797b1e3391750`.
This establishes the original source baseline. The separate session 98621 above
checked its same-process composition with the captured current inputs. Toolchain
and dependency admission and native execution remain unverified; native build
and production eligibility remain false.

A separate supplier-source investigation, session 48532, passed in 2.171 seconds
with qualified process/log closure and unchanged selected source inputs. It
inventoried effective tar-member metadata from exactly three retained archives:
ICU 2,595 members, OpenSSL 6,007 and libpsl 2,385. All original compressed hashes
were checked. Bodies were decoded and discarded; no extraction, compilation or
member-body collection occurred. Root result is
`4f7b18f881507096228326ed303d408f0fd302dadd40e59b8e29fa9e6f05d7f6`;
original inventory receipt is
`46b6a745274919f359c2ff77d5e11c34bb7c498b93ab7ddae2df80933a8c2a72`.
These effective inventories do not certify physical tar-header traces, gzip
trailers, supplier recipes, source admission or a Windows build. Exact member
body review and recipe implementation remain separate work.

A separate selected-body capture, session 31247, passed in 4.137 seconds with
qualified closure and unchanged selected source inputs. It retained exactly 64
ordinary supplier files / 838,296 bytes as detached data: ICU 20, OpenSSL 24 and
libpsl 20. Every selection joined the effective member ordinal and header fields;
member names were never used as output paths. Root checked all 65 output files,
including the receipt, against their byte counts and hashes. Result is
`843170a63a04ab6e283a0f7405fc1829968c8e709a3db8d47aeb6fd0c306d714`;
original receipt is
`5ba4684a018cc8334e0a180fa63c08789d451e0d7f3493546cc6b6919624ecae`.
The captured files were not executed. Their source review is in progress;
complete supplier recipes, native source admission and Windows builds remain
unfinished.

A further exact two-member OpenSSL read, session 72435, passed in 1.469 seconds
with closed owner/log streams and unchanged declared inputs. It retained 6,345
source bytes plus a receipt; all three output hashes were checked. Result is
`7f8cb3ab12d77cd933ec224ef75bd9aff2291eba4f4a44bb68fb810b2677096f`;
actual tool closure is
`2f7b56dd12232f5df2ea9cf8579e8b9f4b888ee710556d963de3b5451482d23c`.
The clang-cl configuration contains ARM targets only; the crypto build graph
gates CPUID assembly and uplink separately. These are source observations, not
Windows toolchain admission or executed supplier recipes.

The TUI input-button successor passed two supported component tests in 16.646
seconds: 58 Forms cases / 5,997 assertions and the Owner command-10/ACK-11 case /
579 assertions, with no skips or disabled tests. It covers button/reset/submit,
same-version activation, backpressure, capability loss and no action replay.
The tests caught and repaired a zero-generation cover after nonmodal capability
loss. The initial retained-GUI setup failure executed no assertions; validation
used the documented explicit source route with verified upstream and current
patches. Handoff SHA-256 is
`dbde8bb646f8837ed49636afae947583b119c7c3c7a9755ca2a5df5322e403ac`
under `.agent-work/appended-implementation-20261016/html-tui-input-buttons-v1/`.
These tests use native reply fixtures, not an actual native HTML engine.

The application-owned C++ `demo.echo` registration is shared by the browser,
terminal and native bitmap entry points. Its initial inline factory passed the
real Registry/WebServices checks and 23 selected entry mock cases after eleven
strict compilations; its earlier dependency-path recorder failure remains
preserved before any links or assertions.

The boundary fix then moved the factory body into one shared C++ library and
admitted its exact declaration/factory only to direct composition roots. Fresh
component checks passed twelve strict compilations, five links and 24 executions
in 16.080 seconds, with source postflight unchanged and all writers closed.
Receipt SHA-256 is
`ce9ac28d06d89066d8bdf08cfcc65225ceb10b5f202523da4654b92d7099c718`.
The boundary scanner passed. All 54 registered boundary tests passed in normal
and optimized Python, with zero skips, exclusions or incomplete cases; test times
were 11.319 and 11.660 seconds. Their identical case receipt is
`6d403ca74ca417cd9963a01d94e11d93eccaad601d4a26d1903728643feb0cc2`.
The original six scanner violations and the first full-suite result (47 passing,
seven failing fixture methods) remain preserved. The successor repairs actual
fixture prerequisites and narrows one source assertion to permit exactly the
existing generic Surface selector. The nine-file handoff is
`.agent-work/appended-implementation-20261016/demo-services-boundary-fix-v1/HANDOFF.json`,
SHA-256 `f13a306804b88428e9ab861899a0573408814a77d5ab1374abfea628892867f2`.
These are separate component and compiler-free declaration checks, not the earlier
61-test graph, an actual toolkit window, or a website-to-Foundation C++ round trip.

The private browser bridge now offers explicit selector-only replay of its owned
completed form/ACK records through the actual command endpoint. It retains bounded
form/latest-ACK/success-tombstone slots, serializes replay, forbids every callback,
compares exact replies before cleanup and preserves ordinary sequence/turn gates.
Inner unknown and malformed completion prefixes stop further engine exports;
twelve malformed variants cover that early rejection. The final bridge fixture
passed 63 cases, zero skips, in 1.968 seconds with twelve inputs and four native
source references unchanged. Receipt SHA-256 is
`8c62951d5f07f5e0218268d177656cf88689cd2cd2b5e951d34c0b411d52c95e`;
source/test SHA-256 are
`1d5897cdf8eeff32e8f6602f280bd51b09fdd1e47acf9011ae8c67c26bf0ee3a` /
`5666cdd3f9988ee3d2b8e91be5551ba05b735a09f3a615f38d17320daf5de72a`.
Prior observations keep their source identities. These JavaScript dispatcher
fixtures do not prove actual ProviderGuard cache replay or an engine runtime.

The later ten-supplier effective-header capture passed once in 2.332 seconds.
All ten inventories and the receipt were independently rehashed after clean
owner/log closure: eleven outputs /2,305,996 bytes, including 2,291,528 bytes of
inventories. Frozen sources, archive physical identities, qualified Python and
the process owner remained unchanged. Result is
`d41ce1f78edb7eb3b6ecd1ecf28cbc8253c49c48726432ab9d205aa2b9eb5394`;
actual tool closure is
`72ca29defaeccdb1f1b3eb6edafc206f847330ea46a9670ff2996db41b2a0c2c`;
Root acceptance is
`90978649e50f51cdbac432bf0d6d220ed3110a878b923e09765df6c8ad05f755`.
This decoded and discarded ordinary payloads, including ZIP payloads, to produce
effective header metadata. It retained no supplier bodies and performed no
source admission, supplier execution, SDK query or compilation.

The subsequent detached source capture passed once in 3.601 seconds. It retained
exactly fifty selected bodies /1,275,825 bytes from the same ten archives, with
clean original owner/log/tool closure, one reaped process and no error,
outliving descendants or termination. All fifty bodies and their receipt were
independently rehashed after closure: 51 outputs /1,315,810 bytes. Source, archive,
Python and process-owner physical identities remained unchanged. Result is
`25bcb1c7059ad0941cff087de0048945a5ea7f9d4f3ab4bb2aa8cace3cb822a9`;
actual tool closure is
`aab6e81d95041b5f34fe59a172e28c52d60329a73026a8db4b55cb972593b0a3`;
Root acceptance is
`8f7a2a3199573ed7697b20f782e07627e233ee32f5b4b91f3cded1561bb3e978`.
These are detached, untrusted source data for recipe review. No supplier code
executed, source tree was assembled or SDK/native build was admitted.

## Current-checkout retained composition checks

The separate `prepare-checkout` helper passed its complete 45-case registered
suite in normal Python (10.987 seconds) and optimized Python (10.329 seconds),
with zero skips, exclusions or incomplete cases. Both sessions closed exit zero.
The identical per-case receipts have SHA-256
`4a4853178a47ecc4f9af4919ce1faf3777aad2da99b7b716a27f3231bc7929b4`.
Source SHA-256 is
`c48f23f517ebf5912887e93336cb7e98ecf7e688e93ccae0703b92290b67af84`;
fixture SHA-256 is
`cff7e4f64f8a0d28e3ea87da3bf29e707df05eb7b20ea6d196fc156391987a6a`.
The 39 finite inputs and complete selected SDK-binding inventory stayed unchanged.
The handoff and final input freeze are under
`.agent-work/appended-implementation-20261016/appended-requirements-integration-review-v1/checkout-implementation/`.

These fixtures use the actual unchanged candidate composer and verify all four
component choices, current resource edits, guest-proof correlations, exact
retained reference closure, unique and repeated-reference byte bounds, input and
publication races, Git aliases, mode handling and absence of unrelated sibling
reads. Process, network, compiler and SDK operations are fatal sentinels. The
compilation receipts in these fixtures are synthetic; no actual producer,
compiler, SDK, engine, network, Actions, release or runtime qualification ran.
Python 3.9 grammar was accepted; execution used Python 3.13.5. Native Windows
execution remains unverified. The checkout suite is registered only on Linux;
other platforms receive an explicit inventory exclusion for its POSIX mode,
identity, symlink and owned-descriptor cases. Actual extracted Linux and Windows
CMake registration branches passed separately, without compiler discovery,
configuration or native Windows execution. Their receipt is
`.agent-work/appended-implementation-20261016/checkout-registration-v1/RESULT.json`,
SHA-256 `00085767ff99a354c305086fd38528b54c87b5f328014cf624faf38afd41a543`.
The pure CI request suite remains registered on every supported host.
Preparation leaves qualification incomplete.

The CI selector successor passed 63 cases in normal Python (47.530 seconds) and
optimized Python (46.685 seconds), with zero skips, exclusions or incomplete
cases and both sessions closed. Its per-case receipt SHA-256 is
`658e64420a515ba86f38e301e160c9fd4177eb787a9eb8d302ef3c6f401a1545`;
all 256 frozen inputs stayed unchanged. Selector source SHA-256 is
`087685fc4b62a78c631777f7f8e2389d34c23c02eea3b72ea50e7486af263039`;
fixture SHA-256 is
`53141a239f67e2e0d63c8458a848cdeba951a1a1682487ab31602ab0ad335d50`.
The original 61-case normal/optimized attempts each had two dependency-selection
failures and remain failed. The repair separates selected test names from changed
production modules while preserving genuine consumer edges. New collision and
transitive-module cases preserve the existing agent-edit isolation assertion;
the actual retained-feedback path still selects only its nine tooling suites.
The final-source acquisition helper separately passed its 22-case normal and
optimized suites with 57 unchanged inputs. Earlier policy and Latest checks keep
their own source identities. No hosted workflow was dispatched or linted with
actionlint, which was unavailable. None of these fixtures establishes acquisition,
application execution or release eligibility.

Independent read-only review found the documented checkout/comparison/CI
interfaces consistent with released source. The repository documentation checker
was rerun after those edits and still failed on the same nine links under
unrelated generated `tutorial-video/.work/` trees; this is not a passing complete
documentation check. No new maintained-document link failure was reported.

## Shared document broker integration checks

The later focused broker/browser snapshot compiled 31 objects, eighteen archives
and nine test executables. All 79 selected CTests executed: 63 passed and sixteen
failed, with zero skips or disabled cases. Actual session 18162 closed with exit
one after 58.056 seconds; its qualified process tree and streams closed without
outliving descendants or ownership errors. JUnit SHA-256 is
`4f35754ac60a6fdfa82d92d3e367919e4112c57e7b573916d4e0a2eb6352f5d7`;
enclosing result is
`87127e71d758543f3c039d6193f71a9dd39829806dd7414a02c74103561613f6`.
This is a failed suite, not an integration pass.

The failures exposed lease retention during readonly queries, editor/physical
retirement publication order, redaction bookkeeping and failure handling before
supplier exception conversion. One browser fixture also used the wrong import
path. Fixes retain the original assertions. The two
preceding attempts stopped during compilation after 32.700 and 81.941 seconds,
respectively, and executed no CTest assertions; those failures are preserved.
No actual browser, rich engine or SDK ran in these component checks.

The repaired snapshot subsequently executed all 79 CTests successfully in session
33916, with zero skips. Its enclosing check still failed: a later CTest inventory
command overwrote `LastTest.log`, and JUnit had truncated six inner outputs.
Original JUnit is
`a8d692adfa90e2c2e776a01f9e423bf6e53c147ccd499d94c31a0c6b62c0d9c0`;
that failed enclosing result remains unchanged.

A separate six-test run, session 70318, then passed in 6.106 seconds using the
same existing binaries, with no configuration or compilation. It retained full
JUnit and original test-log output before any inventory command. Strict checks
joined the 73 complete original outputs with six fresh complete outputs, all
79 unique tests with zero inner skips. The 862 copied source files, 434 selected
live files, 645 GUI inputs and 58 compiled artifacts remained unchanged through
this checkpoint. Closure is
`fac05eb7488bcca1d06cee44cf5e5a18662d69f0a8566d0cc4ac4d3b2f65126f`;
combined facts are
`ba6f60edd75ec1824fdbf2ad2f24e28e680f5befd12c05442be5a746deaa9eba`.
This completes the component output checks for source seal
`33f5208ebb2f74bbc7f06488e584e079d8689a3488975fe7be990bf1e461d78e`.
It is not another 79-test execution or an actual rich-engine runtime check.

A later broker successor bounds its origin-bound lease ledger before effects,
retires accepted finished leases and lets readonly queries refresh existing
authority. Its focused 46-test check, session 14357, stopped during configuration
in 2.785 seconds because the retained snapshot lacked nine newly registered,
unselected test-script paths. Zero compiler or CTest assertions executed. Failure
closure is `f86e6e3c1e758f159dd8954f03ff789c767cf6998f566cd60e4b8ccf337dfb18`.
The exact nine prerequisites were subsequently captured as independent immutable
copies, with unchanged original identities; receipt is
`471619b9acb7ba0f38273b41ada1903afdab34bcf79165c52a68add97936ad3f`.
The next focused attempt, session 65839, closed failed in 2.580 seconds before
CMake, compilation or test assertions. The supported wrapper detected the partial
cache left by failed configuration: `CMAKE_NUMBER_OF_MAKEFILES` changed from two
to one, while the previous successful configuration stamp stayed unchanged.
Failure closure is
`894215ae6a99235f8de275ca44ceb339b830a832bf928f29f7700416489e8fc7`.
A subsequent metadata-only repair restored the exact independently archived
pre-failure cache bytes, preserving the failed cache and leaving the configuration
stamp untouched. All 871 copied sources, 434 plus two selected live inputs,
58 products and other six build records matched before and after; repair closure
is `4dc7e2d0cdf3fab8c3df7d7f7789eabcac08161d42e2a5aad67586de4fc62bad`.
The next supported focused run, session 84273, compiled the selected targets and
passed all 46 CTests: 22 broker and 24 application-document tests, with zero
failures, errors or skips. The three new ledger cases executed 153, 98,662 and
198,762 assertions. Its enclosing operation nevertheless closed failed in 82.010
seconds: postflight compared the generated prerequisite registry's pre-test
physical identity after supported test reconfiguration legitimately rewrote its
timestamps. Its body, length, path, inode, mode and other indexed facts matched.
The strict full original JUnit and archived LastTest checks passed before this
failure. Closed index is
`7e8e512d1ada384378a1322e59705407bb5554fa5f8534e2e8682bd2e8a7a51b`;
original failure closure is
`0f51036aaf50f422155ac18a918aa507dcc637e2bec3aee1646dd020e35fd4a0`.
The first separate passive verifier closed failed in 0.839 seconds: its command
comparison confused a Python tuple with the corresponding saved JSON array.
The exact original command bytes matched the canonical encoded expectation.
After that one-comparison repair, passive session 60099 passed in 4.943 seconds,
with qualified owner/log closure and a complete independent post-closure reread.
It checked all original 46 full outputs, 871 copied sources, 434 plus two selected
live inputs, 645 GUI files, tools, current cache/stamp, 37 focused products and
21 unchanged outside products. Only the exact indexed same-byte registry
timestamp transition was accepted. No tests, configuration or compiler ran.
Closed checkpoint is
`ea8557b078ceac1e590ba2ea241878b2c5e20b2ef96097e5909bc26dc85359b7`;
complete facts are
`e093948deda97dfe4535f301b54146282a33075f30ce946440afa6ad3215796a`.
This joins the original 46 test passes with separate successful full postflight;
both original enclosing failures remain failed. The earlier 79-case evidence
covers its original source only.

## Implementation and qualification limits

The final focused composition-tool group passed 214 cases with zero skips or
exclusions: release 32, qualification 36, fixed checker 23, delivery 31, guest
recovery 18, archive lifecycle 22, compiler 31 and browser adapter 21. All 71
captured source, binding, ABI and workflow files remained unchanged. The common
runner retained per-case outcomes, logs and exact source copies under
`composition-certificate-design/notes/final-focused-20261016T221953876860Z/`.
Its summary SHA-256 is
`0afeaecb1b41a4546a6eb1920bc1c165d025152bc6321616c2956d0f40f80a55`;
input manifest SHA-256 is
`3c4b1b42043ea54826c195e3c8abc1cbb744aa5ae03c55e77bb402e22b60e806`.
Independent final review closed without remaining important findings; its receipt
is `qualification-independent-review/review.json`, SHA-256
`4f1c404237fc6a4ae4a172a782dac429f22367528e91d57f4de223b13ab6e0d7`.
These fixture tests run no actual composition release policy, kernel build, SDK
build/download, browser or publication. The separate real C and Firefox probes
above retain their original source identities.

A separate Chromium instrumentation successor passed 61 combined browser and
archive-lifecycle fixture cases, zero skips, errors or failures, in
17.970948503 seconds. Physical socket creation and subprocess launches were
globally forbidden. The actual fixed adapter sequence ran through fake HTTP and
native boundaries; the cases also checked independently pinned browser/driver
inputs, root/frame/blob-Worker resource witnesses, native-state readback,
descendant inventories, cleanup and installed-archive preservation. All six
named source inputs remained unchanged. AST comparison preserved all 21 prior
browser case bodies and all 22 prior install case bodies.
The receipt is
`chromium-release-adapter/checks-final-v1/summary.json`, SHA-256
`2349085ea9454db7c2d1f3922edf47a8462ec545bc11565f506367c131424039`;
the adjacent `source-pins.json` and `tests.log` identify its inputs and cases.
The implementation handoff is `chromium-release-adapter/HANDOFF.md`, SHA-256
`1cc1fac8c7bce020aa419bc2a02ce6e967e9e1e3f1f01fc918924af789f3d207`.
An earlier 30-case attempt had one failure and one error when native unlimited
throughput values conflicted with the canonical evidence format; the successor
uses finite positive online throughput. That failed attempt is not a pass.
No actual Chromium, ChromeDriver, resource listener, network probe, installation
or composition qualification ran. Native endpoint availability, direct-file
canaries under the selected browser's local-network policy and natural process
closure remain unverified. This successor does not relabel the earlier 214-case
observation or its original source identities.

No runnable integrated rich web engine or connected engine-backed HTML TUI
exists. [The engine audit](appended-web-feasibility.md) records the completed
baseline experiment and source-known remaining implementation. A copied
provider/factory connected to the real runtime, production retained group,
native ports, connected TUI/forms and complete physical input remain
implementation gaps, not tests awaiting final qualification. Document-v2
Owner/Driver mailboxes, the new TUI application, Forms accepted-query delivery
and NDV2 JavaScript transport now have the frozen 205-CTest successor integration
and earlier separately identified checks above. Those mock-provider/component
passes establish no actual factory/runtime connection, eligible SDK or connected
HTML TUI/native-form implementation. Committed text/IME/editor contexts,
selection, clipboard and popup integration also remain unfinished. The diagnostic
baseline's eighteen Node and eighteen Firefox assertions retain their original
factory/artifact identities.

A frozen source-only rich-engine candidate patch series passed exact offline replay and
33 fake-interface helper cases. Its
[checkpoint](appended-web-feasibility.md#source-only-prototype-checkpoint) records
that original evidence separately from adaptations and compilation of the
completed baseline probe.

The binary service dispatcher and application providers are synchronous. Deferred
guest jobs and USB UART implementations remain unfinished. An additive
composition certificate/delivery framework and initial generic gate adapters now
exist. Native Linux, Linux Firefox and Linux Chromium archive instrumentation
have implementations; HTML archive lifecycle checks currently require stateless
applications. Actual Chromium verification and original-kernel/composition
qualification remain outstanding. The policy's mandatory actual Chromium gate
has not been executed or passed.
The manual Actions workflow has not been dispatched. Existing release evidence
retains its original identities.

Actual supported ARM64, Windows, oldest-runtime/CPU, complete graphical-adapter,
SDK-consumer/package and release certification are separate extensive scopes.
They are not authorized merely by the implementation request. Applicable deferred
work is tracked under [appended binary-kernel qualification](../.agent-pending/appended-kernel-qualification.md).

The bounded native SDK metadata read passed after correcting one private
record's declared mode from `0644` to its actual `0664`. The failed first attempt
remains preserved. The successful successor read the same eight metadata records
twice (7,116,006 bytes), closed at zero in 0.626 seconds and left all selected
source/control facts unchanged. Its original supervisor report records one reaped
process, no error, outliving descendants or termination, with owner and log closed.
Result is `b0eff8c5ac01f4cf8faf634931f40c9766155ee4dcdef57d569688c4efc03c3e`;
parent closure is
`1ac58df13bb1e48db0cd78a4772f88a3ff2c6ed523e8a531fb33f0b277f4664b`.
This identifies tool candidates and missing original observations; it does not
admit the SDK or run SDK programs, a native compiler, PIC checks or a native engine.

## Windows producer source tools

The Windows source contract, POSIX source/metadata handoff and native candidate
planner/static inspector use the common rich4083 engine graph. The dependency
importer now declares WebP's `sharpyuv` target and link requirement. The final
source packet is
`f9392c315b1ba4406d1529854b6ebfe7915545ff2e4d90d29050f275230357e3`;
Root independently rechecked all thirteen source/successor records, 616,911 bytes.
The contract passed 25 normal and 25 optimized cases, handoff twenty cases, and
candidate adapter 62 cases, all zero skips. Independent review closed handoff
identity/output-overlap findings and three PE/COFF bounds findings; the packet
preserves original test identities. These are synthetic source checks.
The three suites are registered on Linux with explicit exclusions on other hosts.
Two exact-block CMake script checks passed for those branches without initializing
a compiler; registration receipt is
`142fb4f0d91231982b40de6aa0b354b80a5a9dda6ec26a26c45f38b8e741ea4d`.

The subsequent maintained Windows implementation supplies handle-relative native
publication, original supplier extraction/overlay replay and the static `/MT`
dependency producer and proof routes. The current schema-two request selects
the H2/D3/G2/W2 contracts; thirteen fixed supplier factories cover twenty static
libraries. Original retained observations and current bytes are still required
for admission. The legacy source-only route retains its original behavior.
Final promotion `ce8f60d3b518883126f0731e48802b34216813a3c1786eb81bc65fd2ad9c075a`
binds 91 files. Its final canonical checks passed 139 normal methods, with zero
failures, skips or exclusions: 54 dependency, fifteen support, four tool-version
and 66 prototype cases. The cold synthetic-PE CLI, unknown-facade refusal and both
supported help dispatches also passed. Original check closure is
`f44fe1f1738d91849851d67698e98086f249ac24fc6fa718be2728f1e367f51b`.
These are tooling observations. Actual Windows input admission, compilation,
linking, installation, engine runtime, eligible SDK and platform/release
qualification remain unrun.

## Shared process ownership and build-entry integration

The maintained process helper now exposes bounded observation/control interfaces
and optional Windows Job process limits. Linux live observations remain
incomplete and do not claim an atomic process census. The supported build entry
loads the Windows compiler helper only when that build path executes, preserving
the standalone producer's explicit module ownership.

The affected maintained suites passed 170 applicable cases: 46 observation/control,
eight test-runner, 27 host-contract, 38 build-entry and 51 process-lifetime cases.
The new import regression executed an isolated real import; Linux lifetime cases
used actual supervised subprocesses. Two native Windows cases were explicitly
excluded on Linux. Receipt
`010453aba23007ebf87cac56f9eef2a65ffb4409f79f7a4a661600d3dc392db6`
binds the seven promoted source files and five complete case inventories.
The opt-in Windows process-cap/publication/source-reader diagnostics and broad
platform qualification remain unrun.

The test-only successor then added an absent-host-API fixture and passed all 47
observation/control cases. It supplies the fake pipe API explicitly, without
requiring that Linux API to exist on the test host. CMake now registers that
suite in the ordinary graph and the maintained ROLE7 suite in the existing Linux
native-tooling selection. The earlier 170-case result retains its original
seven-file source identity.

The independently copied runtime subject capsule also completed in session
51824, caller zero, with no child programs or engine execution. Root independently
hashed all sixteen copies /141,145,788 bytes and checked their unique physical
identities, exact namespace and unchanged eighteen original input identities.
Result `50cb23b24714c742c3af07fb8a90876c51aabaa5c3d6af1e49f88fbad7a54b7f`
and acceptance
`ca88c82c9da70d75330dc687ff244f21feddc201c4ead162e0c755c0ddf91d45`
identify this copy operation. It preserves the failed original6290 and separate
accepted passive81951 evidence. Runtime execution and production eligibility
remain unproved by the copy.

The first copied-engine runtime attempt, session 2264, closed failed after
4.611 seconds during Firefox startup. Its two Node inert-import/environment-refusal
assertions passed; no browser page case or native transaction ran. The saved
failure is `Marionette connection closed`. The sampled driver/descendant RSS
reached 1,638,723,584 bytes, exceeding the 1.5 GiB limit. The reviewed watchdog
path shuts down the socket and settles its owner after that bound is exceeded;
the original result did not save the watchdog's separate failure string or raw
rejecting sample. Both process owners and logs closed, the monitor thread joined,
and all 48 input physical facts remained unchanged. Result
`e6795cb080921e21366c298eb14212654ad10096355cfb5b1ce2e7a9421a84a4`
and Root closure
`e851e50536598d26243f7f070c25aaf1f1e9b68426af2984fd9dddd1c6a7017e`
preserve the failure. A bounded resource/reporting successor is implementation
work; the rich runtime and neutral qualification gates remain unpassed.

The maintained Linux ROLE7 integration was also promoted: native producer
retention now covers twenty controls; dependency retention keeps its original
twenty-three controls plus eleven shared controls. Twenty-six normal and
twenty-six optimized private cases passed, followed by 26 cases against the
maintained paths. Root rechecked all fourteen promoted source hashes and physical
facts and the complete canonical inventory in receipt
`563185bb4db5c606a19f6dda145fa78cd81f594abcc78738bec8cc76b66b8fad`.
The original 166 input test bodies remain byte-exact. These are inert source
fixtures: genuine complete host/runtime/provider and original ROLE7/OS records
remain missing; real collection, target C++ runtime/PIC, native builds and release
qualification remain unrun.

The separate 3 GiB/reporting successor, session 87153, also closed failed, after
14.150 seconds. Its sampled RSS reached 3,297,832,960 bytes. No browser batch
completed; partial case execution is unknown. Node's two inert-import/refusal
assertions passed. Owners/logs and the monitor joined, and all 48 input physical
facts remained unchanged. The added `guard_failure` field was overwritten by the
transport handler, so both saved reasons are transport failures. Result
`daa8a9f639d393c83943377c1a0b7c394f184fc5fae36b140bf43b672425e14f`
and Root closure
`aebe6e99e6a556949653170eff88ca07ec068c63562c628cd62214357f77f619`
preserve this failure.

A separate 4 MiB fabricated-data experiment found a narrow transport allocation
problem. `Uint8Array.from(atob(text), callback)` used 217,632 KiB peak RSS in Node,
versus 74,060 KiB for an indexed byte loop; both produced the same SHA-256 and
rejected invalid base64. Receipt
`4c62d6d44b4b863ea58b3d85f5a0807a0075d6cbeee83909d7d119696eb72342`
identifies this diagnostic. It ran no engine or browser and is not a Firefox
memory measurement. The next source successor keeps 3 GiB and every original
case/time bound while correcting the large page decoder and preserving the
first watchdog reason.

The indexed-decoder successor, session 12986, still failed at the unchanged
3 GiB RSS bound after 9.096 seconds. This time both saved failure fields correctly
identify the first cause. Peak sampled RSS was 3,258,998,784 bytes. No browser
batch completed; partial execution is unknown. Node's two negative/import checks
passed, owners and logs closed, the monitor joined, and all 48 physical input
facts matched. Result
`6dc23fb84a45c66ac69cd474d6eed40dedf630ba07a15d15c55ab43261bc7032`
and Root closure
`1f2d6cb1ec4973b5335b32174f77291b1e966a878600e4b718633f7c241c3ac0`
preserve that failure.

The subsequent diagnostic run, session 25276, retained the same cases and time
bounds, added command/per-process RSS observations, and used a 4 GiB aggregate
limit. It reached the compiled engine and failed after 11.745 seconds on
`Existing service/action work must settle before new native work`, with no
watchdog failure. Peak RSS was 3,428,134,912 bytes. The original positive-batch
observation is retained, but no whole browser batch was accepted. Node's two
checks passed and all owners, logs, monitor and 48-input postflight closed.
Root closure
`8677698d666ce0a0ea5d8eeb85a149482f960c1ca812e39ee5f91eda19aa4b3b`
records this genuine ordering failure. No engine recompilation accompanied these
runtime attempts.

The reviewed action-settlement successor, session 13928, then closed failed
after 18.741 seconds on `D01/bounded-native-text-control`, with no watchdog
failure and peak RSS 3,498,881,024 bytes. It retained every original case and
bound, correcting the probe's startup/intent settlement, action acknowledgment
order and raw/decoded ACK-field checks. The original positive-batch observation
is retained; no whole browser batch passed. Owners, logs and monitor closed and
Root checked all 48 physical input facts. Result
`2d9b86d8be2ca423d28dc2737fe371aa6dd3834c5538560aff46dae96876c569`
and Root closure
`ee7d7526fd82d68f0b530bb9fe192f615420d1a4d61a421efc11cedeb104209d`
preserve the failed control assertion for exact state/decoder comparison.

The corresponding maintained appended-browser bootstrap and ordinary Wasm
packager now use indexed base64 byte decoding. Their existing seventeen tests
passed without exclusions or skips, including canonical encoding and size-bound
checks. Receipt
`cb24bba88387748130031f2209920e0d5bb7a675f669d1eede0d310e000ce66e`
binds those source changes. This is packaging/transport evidence, not an engine
runtime pass.

The composition metadata and matching maintained tests were then consolidated.
The rich packager passed 55 cases in session 69609, the document/editor packager
80 in session 86833, and the Worker 49 in session 77577, all zero skips. These
are three source-specific observations, not a fresh 184-case batch. The two
intermediate failed batches remain preserved: one fixture changed an inventoried
leaf after sealing its fake bundle, and a new Worker test omitted the legitimate
post-readiness create call. Their narrow fixture repairs retained the production
checks. The engine packager's extracted indexed decoder also passed five small
Node checks; three focused container/CLI checks passed separately. Root rehashed
all ten final source/test files (501,461 bytes) and their physical identities
against handoff
`677fbe3aa5c2201c0658295462c5ddf63275b6569ac2cf0631b51d387931597d`.
No compiler, SDK program, browser or engine ran in these source checks.

Two rich-packager test methods were subsequently strengthened with otherwise
eligible pure-policy baselines. Both passed in a focused run; the other 53
methods and production inputs were unchanged. Final handoff
`331a989227470b2d9e5fab687311eefecc6bf9bfb115f87a581b6650375b4d5d`
binds all ten files; Root checked their hashes and physical facts again. These
counterfactual fixtures create no eligible runtime artifact.

Six focused semantic-root and owned-service CTests passed 606 assertions with
zero skips in 24.324 seconds. They cover publication, queries, acknowledgments,
and native work accepted both before and after a retained terminal action. The
fix invalidates that action while native work is pending. Receipt
`c82d47bb9572e3be88c767eb9b749215e11a77f58e8ebaeed1565881dd23fdca`
retains the earlier genuine component failure. These tests use component
providers and do not qualify the rich engine or a native port.

The other six semantic-root cases completed separately: five passed 112
assertions, and the final terminal-pan case passed 26 after supplying its
missing button-label field. The original pan failure remains preserved; no
production geometry changed. Final pan receipt is
`3b4fa3d7067b945706b9b7bc7d9fb926ef8999c20ad7a9c1757a3c07898a927b`.
Together these observations cover twelve CTests and 744 assertions, with zero
skips, across their original source generations rather than one fresh run.
Four bitmap-region/service-poll/close CTests also passed after moving the
fixture's oversized allocation instead of copying it into a smaller buffer.
The production retained-capacity guard was unchanged and the earlier failure
remains retained. The subsequent canonical source/test consolidation is recorded
below.

The maintained Windows publication/source-replay/preparation integration passed
five affected inert methods in normal and optimized Python (ten executions,
zero skips), plus an ordinary import smoke check for all five public modules.
Root rechecked the five source/test bodies and their physical identities against
promotion receipt
`482e0b6b513ee14e907b4be6e1ad4d50d73d725a1f5fca0cd9363e0ff5632104`.
The later dependency/prototype source integration is recorded under
[Windows producer source tools](#windows-producer-source-tools). Actual Windows
native qualification remains unrun.

The shared GUI/TUI composition is now consolidated in 49 maintained files.
Release `c682377d3a8329e7bba08e5a12d39350c5569f8be5a1b71d41ee16bd0e5ae341`
binds the final source generation; Root rechecked every body hash and seven
physical identity fields. Six focused terminal-close cases passed with no skips,
including the queued-close path and already detached or blocked paths. The
canonical boundary guard, two affected boundary tests and registration checks
also passed. The earlier model, Module, semantic and bitmap observations keep
their original source identities; this is not a fresh complete GUI run or an
actual engine, native or TUI qualification.

The subsequent isolated document composition check passed four exact CTests and
432 assertions without skips. It compiled nineteen small C++ objects and linked
the selected fixture; no engine, application kernel, interpreter provider or SDK
was built. Caller closure
`9bab7dcd82dcc31468ccd8517b3092089d9bb37f3b90bc10fda6e84c2d86a78a`
records the 70.991-second attempt. Independent readback matched its 896 source
and 645 GUI manifest entries. The original configuration failure is preserved;
the successful successor added the five missing tooling prerequisites only.

The private source-object construction adapter also passed 31 inert checks
(25 adapter and six SDK-inventory-capacity cases), with zero failures or skips.
Both supervised commands closed naturally and all thirteen source inputs stayed
unchanged. Result
`0c830716b37d1fa47fbf25ad34aa8f5726e38e29f3637bb2d73a80ac8cd5a7c3`
does not establish actual Foundation construction or combined browser execution.

The actual combined C guest subsequently compiled through the supported entry
point: four C compiles and one link completed in 1.279 seconds. The 13,660-byte
module has SHA-256
`f608dce340e731a53f42da2ef3e436ee49c3f8dda3f16a82e5005643301b9588`
and passed the `foundation-guest-v1` audit. Original producer receipt is
`1a97cf34ee5f01a4ca20e25872fa36e9c6095ae08c7579ff8add10b930510033`;
Root caller acceptance is
`8ea854422672eb1bbe1fc638de525b4c59f55577ef47d43cf237f11d6d7ccce9`.
All selected source, bindings and SDK checks passed. Diagnosis corrected an
overly strict supervision counter check; a later attempt identified a vanished-PID
RSS sampling race. The original failures remain preserved without inferring the
unavailable first report. The successful attempt
observed 115,937,280 bytes peak RSS and one vanished sampled PID, with explicitly
non-atomic coverage. It built no kernel or engine and executed no guest runtime.

A subsequent current-payload check exercised all four project modes through
eighteen supported commands. Web, binary and combined packages passed inspection
and verification; all resource bytes matched the bundled pages and the accepted
13,660-byte guest. Neither mode correctly rejected an empty package and required
no disabled source directories. Both startup formats were checked. Result
`062098724435726fcac3b9089fa6016ef042d6819d0b80fefda9777e483f7188`
records seventeen successful commands and that one expected refusal. This checked
standalone packaging only, without a compiler, SDK program, carrier composition,
kernel build or runtime execution.

The failed runtime control assertion was traced to ordinary labels in hidden
tab panels. Missing label-association evidence incorrectly made unrelated visible
controls incomplete. The maintained Publisher repair preserves bounded native
association evidence while keeping hidden content private and uncertain or
affected controls non-actionable. Both active producer recipes now contain the
repair. The supported entry point passed two exact CTests: 35 checks of code
extracted from the actual Publisher and eleven generator tests, with zero skips.
Only the generated host fixture was compiled and linked. Receipt
`09e1a2f78b3e52e1845027d8a48d183845a7ca2e0b1b0e2c1ca7e76d6e7b8458`
binds the unchanged five inputs and test products. This establishes the focused
source behavior; the later selective build below is separate evidence and actual
execution of the repaired engine remains pending.
Dependency inspection limits the intended engine repair to two affected
translation units, metadata generation and one link, with no archive rebuild.
Reusing the other completed objects requires the separate strict donor
continuation and its exact source, flags and header joins, recorded below.

The completed-donor continuation is now in the maintained producer and source
assembler. Its registered fixtures passed 37 donor and eight assembly cases
normally and under optimized Python, without skips. A subsequent supported-entry
selection passed both suites plus four portable Windows tool-version cases:
three CTests and 49 methods, zero skips, in 4.12 seconds. That selection configured
the ordinary graph and ran scripts without a compiler or linker invocation.
The first actual donor metadata capture, session 31178, then closed failed:
the selector rejected a variable escape in a generated Ninja output header.
Its caller returned one, the supervised reader closed naturally, and all selected
input identities stayed unchanged. No descriptor was published and no compiler
ran. The grammar repair then reached complete metadata construction, where the
prototype's 16 MiB output cap proved insufficient. The final bounded capture,
session 35055, passed with a 64 MiB metadata envelope: 19,488,621 bytes for the
descriptor, 14,274,053 for the sidecar and 3,792,754 for its receipt. This fits the
producer's existing document limit; application and payload limits are unchanged.
Root acceptance
`c68a8c3247c7a340b1f0bb1e7387539d58d6a9bf02f590eff6d5680daabf9b6a`
records caller exit zero, 802,311,728 input bytes, one Ninja stream pass and
unchanged postflight for all 6,458 captured file identities. The capture read no
object/archive bodies and admitted no reusable object.

The subsequent source, metadata and retained-input preparation completed in
126.859 seconds, with caller exit zero and three natural supervised closures.
Root acceptance
`07706204c287b2b08ed134c28ea370004b8e76cd59d37e9c38a0df264e5a83fe`
binds the original result, unchanged 250 frozen input identities, all 368 assembled
source files and the 42,779 independently copied files (861,802,853 bytes).
No SDK program, configuration, compiler, linker or runtime ran. Actual completed
donor admission, the two translation units and relink were still unexecuted.

The first continuation plan attempt stopped during its outer preflight: the
checker incorrectly treated the Ninja log's full file record as a short
reference. Caller exit was one and all 68,283 file and 3,797 directory identities
remained unchanged. No supervised plan program, output directory, compiler or
linker was created. The narrow checker correction is separate from this
preserved failed attempt.

The corrected checker passed seventeen focused cases normally and under optimized
Python, plus coverage against the captured metadata. Plan session 45979 then
passed within its 240-second bound, with natural process closure and unchanged
input postflight. Root acceptance
`c4bf657519330795fe2e379aafcddd8f70be9ec591d8a6339c8fae7e181c8442`
rechecked all 68,283 file and 3,797 directory identities and binds the actual
38,566,314-byte plan
`e32db8b2d03e4833dd058e473e360b1feee62246ee3521f93aad7171f632aa35`.
The plan admits 49 completed objects and five archives, leaving two compiles,
zero archive repacks and one link. These are planned actions; no new object,
archive copy, compilation, link or runtime resulted from planning.

Actual build session 6155 subsequently closed with caller exit zero, natural
supervision and unchanged input postflight. It copied 49 admitted objects and
five archives, compiled only the Publisher and document shim, regenerated
metadata and linked once, with no archive repack or full-engine fallback.
Static factory/Wasm inspection and all 2,076 archive-member joins passed.
Root acceptance
`4a72a630d52bd32181fbcbfdae78538daa94473e1a8d3209c3b3b996809df087`
independently rechecked all 68,290 file and 3,799 directory identities, the three
complete immutable namespaces, 26 control-source hashes and all 171 artifact
identities. The original flat caller result is
`83613c5b5a4a784d41261184c798a40870fee3b7a69ae289cb0f9159f47d3b11`;
its sampled aggregate RSS peaked at 2,460,487,680 bytes within the 4 GiB bound.
The new 109,675,754-byte Wasm is
`d201800d2669be0d18e54c6d7182b1af6e03f03004c0b6a9c434e915103ef84f`.
This closes selective candidate production. Complete runtime verification,
retained-group admission and actual Foundation/combined execution remain
prerequisites; production eligibility remains false.

The downstream metadata reader needed a donor-specific 64 MiB allowance for the
19,488,621-byte descriptor. Commands and legacy lineage retain their 8 MiB limits.
Seven focused synthetic controls passed, without skips, and the actual metadata
copy closed naturally in 2.935 seconds. Root acceptance
`728ce27cb45835be425449b7a0e6b13e6a614a843293e782283e9091bb711a2e`
independently checked all sixteen copied files (164,721,294 bytes), their complete
namespace, the fourteen original joins and two external lineage records. This
operation ran no compiler, SDK program, engine or browser.

The resulting 65-case runtime attempt, session 41837, then closed failed in
14.827 seconds. All 31 original application assertions and D01's 51 native-control
assertions passed, confirming progress beyond the earlier completeness failure.
D03 failed while beginning a second native form session after D01 finished and
acknowledged its first session; no D03 text replacement was reached. The original
native completion reported an uncertain outcome and the bridge refused replay.
No browser batch completed. Both Node inert/refusal assertions passed, and all
owners, streams and the monitor thread closed. There was no watchdog failure;
sampled aggregate RSS peaked at 3,595,816,960 bytes within 4 GiB. Root closure
`9c06895ee4cc958a58cf6f5859a1e11acba5f422abdeba5bd033a7a612d783e1`
rechecked all 47 input hashes and physical identities. The original failure and
observations remain unchanged. Source review isolated the second Begin's focus
transition: editor flags change from `4` to `21`, preserving undo availability
while enabling editing and input methods. The Begin guard normalized editing's
bit `1` but rejected the related input-method bit `16`.

Both maintained publishers now normalize those two focus-dependent flags for
Begin alone. Full editor-state resampling, native selection/context validation,
composition, undo, redo and the other capture comparisons remain unchanged.
Supported session 80384 passed both existing focused CTests: 63 extracted-source
C++ checks (35 retained and 28 focus checks) and 13 generator tests, with no skips.
The generator copies the actual production guard into its dependency-boundary
fixture. Source release is
`b90b0dd0b36792e664c0f5683f6a03f52516274b4a588b463d92db6165f48d2b`;
Root checked all fourteen released source/evidence facts and all nine check-input
hashes and physical identities. Forty-four source-metadata tests also passed.
The two native profiles changed only their provenance/source-map hashes; Root
verified both inverse byte comparisons. These checks ran no engine or SDK
program. A separately identified selective candidate and actual runtime are next;
retained-group, Foundation and combined execution remain unrun.

The D03 successor's bounded preparation, session 1866, then closed failed in
160.889 seconds on 2026-10-17 at 21:28:51 UTC. Source assembly completed with
368 files / 564,540,041 bytes, and metadata completed with twelve files /
106,263,995 bytes. The retained-input copy failed with `ENOSPC` at
21:28:38.792399 UTC while exclusively creating `PlatformTextTrack.h`; the target
was not created. The copy process exited one, was reaped, and left no outliving
descendants. Original `actual-v1/RESULT.json` is
`40e9702ef24b77d6db85e41a3f0d0e67d970e7523b6ccad195458e65063255b8`
under `.agent-work/appended-implementation-20261016/runtime-D03-repair-v1/provider/selective-continuation-v1/preparation/`.
No copy completion receipt, final proof seal or Root acceptance exists. No
configure, compiler, linker, SDK program or new runtime ran in this preparation.

A read-only post-incident audit on 2026-10-17 found all 37,650 existing copied
files / 775,543,203 bytes matched their expected hashes, sizes and modes. They
form the exact ordered copy prefix; 5,129 files / 86,259,650 bytes were never
copied. The 34 empty files are expected originals, not truncated writes. The new
source and metadata outputs also matched their manifests and saved records.
Earlier candidate 6155's 171 artifacts, the capsule/runtime inputs, 19,426 paired
SDK files and audited maintained source cohorts remained intact. Git's full
object check passed. A timestamp census covered 1,532,710 files; no Git-visible
maintained file had an incident-window modification/change timestamp. These
integrity observations are not build or runtime qualification, and unsealed
files lack universal pre-incident byte baselines. The main ignored checkpoint
predates the launch; the surviving launch intent and failed result establish the
actual latest state. Recover preparation in a separately identified output scope
after checking storage prerequisites. The partial copy is ineligible; the
selective build and unchanged bounded runtime cases remain unrun for this repair.

The shared native recipe also now permits the retained OpenSSL Windows
requirement `gdi32`, with the final Publisher, source map, provenance and both
platform profiles joined consistently. Final release
`7bbe31bce83fc5ebf5550b8cd7696cc078eda37220450635e8f7b25e1bd1b0d0`
records 25 normal and 25 optimized inert checks, the 197-input inspection and the
single affected ROLE7 fixture pass. Historical H1/D2 policy remains unchanged.
No SDK program, native compiler or actual Windows provider ran in these checks.

The retained-checkout composer now forwards the configured primary to the same
startup packer used by ordinary packing. Eligible web, compiled and binary
primary fixtures preserve the retained prefix; incompatible composition/view
capabilities still fail. All 48 registered checkout tests passed normally and
under optimized Python, with no skips or exclusions. Root read the complete
delta and rechecked all eighteen source hashes and physical identities plus
both full result inventories in acceptance
`ddfc283ed51097bd1e36871f562a80dc94a2579a9e8ace002743d9a16576510c`.
These pure fixtures forbid compiler, SDK, network and process use. They establish
checkout/packing parity, without qualifying an actual rich runtime or retained
production kernel.

A later SDK consumer audit corrected Rust discovery reply decoding to require
the canonical flag on each known field, matching the C binding and bootstrap
schema. The regression source covers all six missing flags, a valid reply and
an unknown optional field. A subsequent supported compile of the current Rust
example passed using that corrected SDK source and the retained Rust 1.84 tools,
producing an audited 17,898-byte module
`72e6b87b7d62d38c7ac3f081ebb2497d1d53e3be9e4e44e4495d857e7a58e52e`.
Its Rust unit test remains unexecuted because the host standard libraries are
absent. The target compilation is not a unit-test or runtime pass. No toolchain,
kernel or engine was rebuilt or downloaded for this check.


## Fresh D03 preparation recovery

On 2026-10-18 UTC the continuation found clean HEAD `a3e31fd` (the documentation
handoff successor to `30a6221e`), verified current Btrfs allocation and host-visible
jobs, reviewed the complete coordination claims and acquired a fresh output.
All 250 original frozen input hashes and physical identities were unchanged.
Detailed Btrfs device ioctls were unavailable; the original ENOSPC cause remains
unknown. No original output, ignored evidence or retained SDK was removed.

The new `preparation-recovery-v1/execution-v1/` uses the reviewed original
algorithms with fresh paths/pins, unchanged resource caps and exactly two replaced
local frozen rows. Its source and metadata phases were reassembled, and the entire
retained-input copy was independently created; the failed preparation 1866 and
its partial copy were not consumed. A guarded artifact-edit refusal occurred
before mutation; the disabled draft controls remain preserved and the execution
controls were created exclusively as new files. Independent strong review passed
the exact byte/AST/packet projection before launch.

Actual preparation **1570** closed with caller zero (`828423`) in 118.457506299
seconds. All three phase owners closed naturally with zero exits. Root's independent
readback **53212** closed zero (`a19e8f`) in 49.536 seconds, checking complete
namespaces, modes, full hashes and physical identities for 368 source files /
564,540,041 bytes, 12 metadata files / 106,264,070 bytes, and 42,779 copy files /
861,802,853 bytes. All 250 original inputs and five execution controls/packet
files remained unchanged. Current source pins remain `a2df92fd…` / `64aa9022…` /
`6fef5ea2…`; actual proof is
`6039e0aaf2d0f268b25ff2ef32301de0095c17b215662144e863fb5709d92c32`,
with inventory `74648ccc09afd04972a5dfe9ef7161900c6692bbe2990e17dd9d3c04818a9fc5`.

Evidence under
`.agent-work/appended-implementation-20261016/runtime-D03-repair-v1/provider/selective-continuation-v1/preparation-recovery-v1/`:
`ROOT-LAUNCH-INTENT.json`, `ROOT-ACTUAL-HANDLE.json`, `ROOT-CALLER-RESULT.json`,
`ROOT-READBACK-INTENT.json`, `ROOT-READBACK-HANDLE.json`, `ROOT-READBACK-CLOSED.json`;
original `execution-v1/actual-v1/RESULT.json` is
`39c5b2a380cf6f2468bc4e63ff83eee57708f253d0df16723c7c80deebf0fd4b`,
closed `execution-v1/ROOT-CALLER-CLOSED-ACCEPTED.json` is
`f4377906f8ec75414591bd68f25474ec0f9e809964fa8cc7dfe86acc482ec33a`.
No configure, compiler, linker, SDK program or runtime ran. There are no completed
engine imports and production eligibility remains false. Fresh selective planning,
two-unit production, unchanged actual runtime cases, neutral admission, Foundation
construction and partial BOTH execution remain dependency-ordered prerequisites.


## Fresh D03 selective candidate and trace-limited runtime

The 2026-10-18 recovery then completed the fresh selective plan and current-source
candidate under the original retained 49-import / two-fresh-unit / five-archive /
zero-repack / one-link contract. Plan 17883 and independent readback 76598 closed
zero. Candidate 94609 closed zero (`57b809`); peak aggregate RSS was 2,428,121,088
bytes under 4 GiB. Independent Root 32461 closed zero (`3ee810`) and rechecked all
171 artifact hashes/physical identities, exact 17-field acceptance, 68,348 file /
3,799 directory input identities, 28 source hashes and exact command/accounting
lineage. No retained kernel was built and no release qualification was run.

Under `runtime-D03-repair-v1/provider/selective-continuation-v1/concrete-recovery-v1/execution-v1/`,
plan is `4f19b383f6f828160f1400b87923b960687e52a3787782127a146f500153d7a0`,
actual candidate result `306c83168af9280bf1aa14c999d0901983f043dad0a636339d4aa3840b6111cd`,
maintenance build `25036087459756741159848f868682d1eb0db981d84960474626ebf51d48c02c`,
and Root candidate acceptance `4d0ccd2fde7921becb4d132a162c32c3dd7184364ff90eb791b376841a454663`.
Factory is `4685254b…`; Wasm is `68193e59db6eb86af2a66dd615b73409677201348b9f67cb326eeb39e8f0cf36`
(109,675,840 bytes). Current Publisher 0705d942 is included; production eligible is false.

Fresh metadata-only capsule 3086 closed zero in 1.735 seconds, followed by an
independent fullhash/physical/complete-namespace Root readback: 16 distinct copies /
164,728,184 bytes, originals unchanged. The producer result is `c9715acd…` and
Root copy acceptance `8f76d89f…`, under `runtime-D03-repair-v1/runtime-recovery-v1/`.
The two lineage records remained external. This copy executed no SDK or engine.

The fresh 47-input runtime packet passed shape admission. Actual approved
Firefox/Node attempt 86329 closed one (`04b4a7`) after 20.161931327 seconds with
`Bounded Worker trace`. Result is `runtime/actual-operation-v1/result.json`,
`88696cb47a622f054a958d90020037c99bebd5ef81b0bbe7e905920ef6151299`;
raw positive observation is `b2c543fabaa495f3ef1595aae63d7aa5b31d032a82eab52d4aab0f55ef92381a`,
13,372,113 bytes. Both Node negative assertions passed, all 47 inputs remained
unchanged, owners/logs/watchdog thread closed, and guard failure was null.
Sampled RSS 3,695,534,080 bytes and output 220,598,251 bytes remained below caps.

Zero browser batches passed. The failed positive observation records 13 mandatory,
31 author and 442 case-assertion rows true: D01=51, D03=85, D04=87, I01=108 and
I02=111. Only D01/D03/D04/I01 completed; I02 remained running. Eight later positive
cases and all other eleven batches are absent. Trace has 12,815 rows. Partial
observed counts were 50 ordinary, two metadata replays, 1,480 exports and 295
dispatches; zero aggregate totals reflect zero accepted batches. These are
observations of an incomplete failed batch, not an accepted rich runtime.

External caller and independent coverage are saved in
`ROOT-RUNTIME-CALLER-CLOSED-FAILURE.json` and `ROOT-RUNTIME-FAILURE-COVERAGE-READBACK.json`
beside the runtime packet. The original 41837 failure remains intact. Next is a
focused trace-producer repair preserving bounds, assertions and all 65 cases /
12 batches, followed by a separately bound fresh runtime attempt. The accepted
candidate/capsule may be reused with their original applicable identities. Neutral
admission, Foundation construction, partial BOTH and integrated application behavior
remain unrun; broad qualification remains deferred to explicit authorization.


## Trace projection repair and I04 runtime failure

A source-only Worker repair preserves native/peer behavior and all case expectations
while omitting redundant outer non-SUBMIT request/reply trace copies. Required raw
SUBMIT pairs, semantic/native rows and notifications remain. Canonical trace byte
accounting preserves 8 MiB / 16,000 and conservatively budgets floating tokens.
Source `a8d498f550735f1130d1e2649e6ba0755b1185b945166cc888a4282a59b1be25`
and focused tests/patch are under `runtime-D03-repair-v1/runtime-trace-projection-v1/`.
Pure tests passed 2,073 vectors plus byte/row boundaries, notification/actual-event
preservation, exact reverse patch and syntax-only full Worker. They did not run
an engine. Saved-prefix projection was 7,167 rows / 2,895,208 canonical bytes.

Fresh source-bound runtime 97809 reused the accepted engine/capsule, with all other
19 source roles, fixtures/tools, cases and bounds unchanged. Shape admission passed;
the original actual caller closed one (`7a7579`) after 21.802950001 seconds with
`I04/after-lifecycle-old-C8/actual-native-STALE-before-TURN`. Zero batches passed.
Result `runtime-recovery-v1/runtime/actual-operation-v2/result.json` is
`713b238a6cb3df86c67d6b841be2a1b1b9c339897872d6f209bbffe5cee01986`;
positive observation `687fc00988990416aebb0bcddf605c3a6e3aa7cf172b806229f2d6a25357babc`
is 7,525,122 bytes. Trace 10,160 rows / 3,980,076 canonical bytes stayed within
unchanged limits. Node negative controls passed, all 47 inputs were unchanged,
owners/logs/watchdog closed and guard failure was null. Sampled RSS 3,472,936,960
and output 207,207,488 bytes stayed below caps.

D01/D03/D04/I01/I02 completed in the failed first observation. I04 failed; seven
later positive cases and eleven other batches are absent. Mandatory 13 and author
31 assertions were true; 607 emitted case rows include one failure. Partial counts
were 71 ordinary, two metadata replays, 2,082 exports and 415 dispatches. There is
no accepted rich runtime. External caller and independent coverage/physical checks
are in `ROOT-RUNTIME-TRACE-v2-CALLER-CLOSED-FAILURE.json`. Old failed outputs remain
immutable. The next focused gate is I04's stale-before-TURN product/identity
diagnosis, followed by only the affected supported production refresh. No broader
regression, neutral admission, Foundation construction or release qualification ran.


## I04 guard preflight repair and native host checks

The three active Guards add C8-only inert admission against copied metadata before
host TURN, preserving the in-TURN recheck, Gate/barrier precedence, exception
poisoning and legacy revoke9 path. Canonical/native Guard hash is `3aebfcc5…`;
editor-overlay hash is `6ec65468…`. Their current source has not been compiled into
a Wasm candidate or run in the actual engine.

The supported native `build.sh test dev --core-provider cpp` route now registers
the local provider fixtures under profile-none. Only ten local C++ translation
units, five local archives and the fake fixture executable compiled. Independent
Ninja/cache readback confirms no kernel, VM, container or owner target, and `all`
remains core plus CLI. The C11 test still requires a profile enabling C.

Two original setup failures executed zero assertions. First executed run90088
closed one with80/82 passes; run50694 closed one with81/82 passes. They exposed
old admission/TURN count expectations. The historical fake retains native metadata
after document navigation, so its C8 preflight succeeds before the original
in-TURN document check rejects; this differs from I04's stale native capture.
Exact assertions were corrected without removing effects/sequence/legacy checks.

Final22409 closed zero at `d1b95a`,6.212878763s: **82/82 passed, zero skips**.
This covers stale preflight without TURN/effects/sequence consumption, successful
double admission, unchanged-identity invalidation on entry, both exception paths,
owned payload/reentry and historical9. Evidence under
`runtime-D03-repair-v1/runtime-recovery-v1/host-check-v3/`:
`PLAN.json` SHA `f53a924202c00a517e4375dd26863011988db27201dac8f70848a2cc074b34bf`,
`CALLER-CLOSED.json` SHA `b3144e7c3bd91cd4f8d56125133e3a2d7d3b248d9d6017c87467ba397abbbc2f`,
`ROOT-DEPENDENCY-READBACK.json` SHA `2e2dff0f82748875eba2946d826760f03aa9808139269cef4e3621a849e6452b`.
All source freezes matched and all Root test children/streams closed before
workload release. The old failed1866 and closed runtime97809 remain immutable.
An explicit48-import/three-fresh/170-artifact successor is required before a new
engine runtime; the original49/two/171 receipts cannot cover changed Guard bytes.


## I04 selective contracts and first fresh preparation refusal

The source-only Guard metadata preserves the document historical compile map and
profile byte-for-byte and the native original/adapted predecessors. Final maintained
driver checks passed 45 document-source and eight successful-helper selection cases;
four unchanged native-source cases remain applicable. The compiler-free CMake
recorder passed ten cases after its complete fragment/install-path prerequisites
and exact four-target pixel/actions inventory were repaired. Its original failures
(7, then 6 setup failures, then one stale inventory assertion) remain preserved.
No compiler was invoked by these CMake recorder cases.

The explicit guard-repair donor/plan/build lane passed 58 donor and 49 maintenance
cases, zero skips. It preserves the old 49/2 lane and admits only ordered48 imports,
three fresh direct units, five archive copies, zero repacks and one link. New private
readers passed40 tiny inert cases, preserving old49/2/171 while admitting48/3/170
and rejecting crossed kinds, summary tags, helper roles and source pins. Reader v1's
summary mismatch was reproduced and corrected in a fresh v2; all old files remain
unchanged. Seven padded descriptor tests were not executed. Root independently
reviewed source diffs and final pins; no new engine build/runtime is established.

Current private reader is `0801ee71debb8e12018eeabfdb21faa0c963504052d5681f4619f77cd8288c04`
(73,208 bytes); runtime contract is `450c46f2…` (50,321 bytes). Their source and40-case
evidence are under `runtime-D03-repair-v1/i04-reader-contract-v2/`. Producer evidence
is `i04-selective-contract-v1/HANDOFF.json` SHA `2693a59de7d5e79efb6b8d60dfd0e40a09201aeca3615debc78f4805db5fec93`.
Final Root source/CMake check records are in `runtime-recovery-v1/final-focused-checks-v1/`.

Fresh preparation6762 launched only after full hash/physical review of255 frozen
inputs, current storage/ownership and exact control diffs. Packet5162e216 retained
all250 predecessor paths:245 facts unchanged, five tracked inputs updated and five
explicit bindings added. Original donor4b1e4b4d changed only kind and removal of the
Guard import row (new descriptor3706a739). Source authority's16 mappings stayed exact.

Original caller closed **one**,848537,31.279604267s. Source and metadata each closed
naturally zero:368 source files/564,545,824 bytes;12 metadata files/106,263,977 bytes.
Copy returned1 at its exact old packet-kind guard before creating any copy output.
There was no ENOSPC, SDK program, compiler, linker, accepted preparation or Root pass.
All255 frozen hashes/physical facts were independently unchanged; process/log
writers closed. Preserve the failed scope and never rerun its armed entry.

Result `preparation-guard-repair-v1/execution-v1/actual-v1/RESULT.json` is
`3a1379f6f38bafe198e696c6d73d24c277af22c8138c0b38837f36801c1791c5`; its
`ROOT-CALLER-CLOSED-FAILURE.json` records the cause and closure. R/S are8f3f9ac8/faaf4eb3,
projection233b7879; metadata fragment proof eaa0e586 is not a complete reuse tree.
A fresh v2 strict kind repair must pass the established three-phase operation and
independent full readback; no failed receipt or partial output becomes eligible.


## I04 fresh preparation accepted — 2026-10-18 UTC

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

Evidence is under `runtime-D03-repair-v1/preparation-guard-repair-v2/execution-v1/`:

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

## I04 selective plan accepted; candidate build pending

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
`runtime-D03-repair-v1/concrete-guard-repair-v1/execution-v1/`:

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

## Current Guard candidate accepted; ordered-trace runtime refusal

Selective candidate **17972** closed zero (`c200ff`) with 48 independent object
imports, Publisher + shim + Guard compiled, five copied archives, zero repacks and
one link. Static inspection and complete input postflight passed. Peak aggregate
RSS was 2,451,759,104 bytes and the 170 recorded artifacts total 439,014,233 bytes.
Independent Root **1567** closed zero (`984f8e`), full-hashing all 170 artifacts,
checking independent output inodes, 68,352 file / 3,799 directory identities and
canonical source hashes. All children, streams and monitors closed. This is an
accepted current-Guard Wasm build; production eligibility remains false.

Evidence is under `runtime-D03-repair-v1/concrete-guard-repair-v1/execution-v1/`:

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
under `runtime-D03-repair-v1/runtime-guard-repair-v1/`. Donor and command lineage remain external.

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

Runtime result `runtime-D03-repair-v1/runtime-guard-repair-v1/runtime/actual-operation-v1/result.json`
is `ced613226d55bbc439d9519eee5512760c4ca52f22575959cea66e137928a280`;
positive observation is `119c1342fd017b3b40c119f16d19a2fe6f21c1ac9b4d5cf0d71649710eb38fcf`.
`ROOT-RUNTIME-CALLER-CLOSED-FAILURE.json` (`a8f779b5…`) records independent postflight,
partial request counts (96 ordinary, two replays, 2,702 exports / 539 dispatches)
and closure. Do not resume this Worker or relabel the failed history. Next is a
reviewed serial-field repair and one fresh same-protocol packet/grant/output.
Neutral admission and Foundation/partial BOTH remain runtime dependent and unrun.

<a id="trace-serial-repair-and-native-composition-cancellation-failure"></a>

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

<a id="fresh-composition-context-preparation-v2"></a>

### Fresh composition-context preparation v2 — accepted P3 preparation — 2026-10-18 UTC

Corrected current-helper preparation scope
`repair/composition-context-preparation-v2/preparation/execution-v1/` passed:
original caller **3007** closed naturally with exit zero, chunk `641a62`, in
**97.618891616 seconds**, with all three phases naturally closed at zero. Independent
Root readback **14272** closed zero, chunk `cc547c`, after full namespace, hash and
physical-identity readback: 369 source files / 564,595,000 bytes, 12 metadata files /
106,264,034 bytes and 42,779 copied files / 861,802,853 bytes. All 363 frozen inputs
and eight controls remained unchanged. No failed packet or partial copy was consumed.

Accepted Root receipt `preparation/execution-v1/ROOT-CALLER-CLOSED-ACCEPTED.json`
has SHA-256 `c2c385194f7d1e9af6add5782b7415f3d42b8c462fb35dd8f6cc154ffd6e8f07`.
The previous P1 acceptance `b7698c509283db411c227d44ebb36fa5847f71f16536ee4924ebb7d8e5eff211`
continues to identify its original helper/source only. Current R/S are
`4fac58dd33a4d7d7e875eb7912d7506082ec2906cc551e55547ae20a3a825fe9` /
`bc4ea6776ee399094bd52db7c61e1b2ab449cff9a2568d1ced585b6f4e5bb994`; reuse proof
is `f20ccc597e8972f2343a90e7aeaf84be81afc12386b341b4ec85d723d782df47`. Frozen
helper `796994d6cee59ed86e6ab35a598285d8190847cc554bed2b2067b39a4d944998` and test
`0611e4bc31ca518df7e0faea62a0e3ceb622c40a182427245a685075abb116c9` passed all 71
registered maintenance cases with zero exclusions. The earlier `707b37` frontgate
failure remains a zero-phase/output failure and its packet remains unusable.

This accepts preparation only. Next is the compile-free 51-object plan; if accepted,
the proposed candidate is 46 imports / five fresh units / five archive copies / zero
repacks / one link, with all 168 artifacts read back under existing caps. Current
source compilation, candidate/runtime, neutral and Foundation work remain
unverified. The integrated rich viewer is unfinished; production eligibility is
false.

<a id="current-helper-plan-26403-failure"></a>

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


<a id="e8b-transport-source-accepted"></a>

### E8b direct copied-transport diagnostic — source accepted, runtime unrun

This is the historical source-only checkpoint. The diagnostic later passed in
runtime53325; use [the latest runtime and packet status](#trace-allocation-runtime-92393)
for the failed runtime92393 and reviewed successor awaiting execution approval.

Current checkout verification found `main` at
`8cc8863f283f8b6972be6bbe383051419c7c6153`, parent `a3e31fd…`. The prior 40 dirty
files and eight added files are committed; the earlier five untracked entries
included a directory. This agent did not stage or create that commit. Before
handoff edits, index/worktree were clean. Passive reconciliation rechecked all
12 native/18 metadata facts, the three diagnostic sources and all 47 previous
runtime input hashes/physical facts unchanged. `HANDOFF-STATE-20261018-v1.json`
under `repair/runtime-recovery-v1/` has SHA-256
`b4132c92500d5a041996bb296f39941afd3cdbd3a12d5cc7ca121d01d7c10e9a` and exact
historical argv. No build or expensive validation ran for this handoff.

Runtime33101 remains failed with its original integer caller1/`370bc5` and
`240b2de9…` result. E6a's82 assertions passed; E8b's malformed-body dispatch did
not record its signed return. Native source predicts -1 before host turn entry.
A separate negative copied-export diagnostic now preserves the normal endpoint,
bridge and supervisor, both original mutations and post-query native-state
comparisons. It uses the complete1,048,680B reserve, validates current target and
owned spans after growth, records the actual signed return, verifies canary,
callbacks/authority/inventory and complete audit prefix/exact two boundary rows,
and stops further exports after uncertainty. No native code or SDK changed.

Stable assignment `luna-editor-transport-probe-20261018-v1` retained deadline
2026-10-18T09:59:44.106394Z and repairs_used0. Its incomplete Luna patch and two
unauthorized direct syntax-check reports were stopped and preserved under
`repair/runtime-recovery-v1/E8B-LUNA-ORIGINAL-v1/`; neither zero is acceptance.
Sol took over that same assignment through source/test completion. The completed
three files under `repair/runtime-editor-transport-probe-v1/` are:

| File | SHA-256 / bytes |
| --- | --- |
| `worker_native_malformed_probe_v1.mjs` | `5768019f3db47288204c89958adcb32f34c40bffa8d25c2d7720ea5bc2ba8dca` /57,203 |
| `editor_cases_native_malformed_v1.mjs` | `860c86bd5877f15edca621913dfbc41f66b8236d5d1c3ab0df09818218de9bce` /33,474 |
| `test_native_malformed_probe.py` | `bdb8148603a106a8778944b91f838e2b1af7791c0d19aa50ffa1daa1046a7050` /24,316 |

Exact authorized source command, cwd the absolute checkout:

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3.13 -B \
  .agent-work/appended-implementation-20261016/runtime-D03-repair-v1/runtime-recovery-v1/run_editor_transport_source_checks_v1.py
```

Original run51199 closed1/`f06677`: fake bump allocator exhausted its heap on the
second probe; the production helper refused the invalid allocation. Failed source
and log remain in `failed-check-v1/`. Run11159 closed0/`b0cf07`,139vectors, then
strong review found fake terminal=false concealed actual terminal=null. That
version remains in `reviewed-check-v2/`. Final run1329 closed0/`32e90c`,139vectors,
with actual peer shape joined to source and original observations. Pure tests
extract the production context callsite, makeContext, hook, witness, dispatch,
helper and E8b body into fake-module checks; they execute no whole Worker, engine,
SDK or browser. They cover capacity-before-malformed ordering, allocation growth,
shared/foreign/overlapping memory, callback/audit/authority drift, unexpected
returns and cleanup traps. The unchanged supervisor counter gate passes against
the original two histories without relabeling their failed runtime.

Final source freeze is `fedc90ef78614bb9a44787db7ac83d30875bbca590856ac5b022b58d3961db5c`;
checks `37e99c59fb7a917e95c5776c529f7590c6236821b11a4066e932e0d6b1f83410`;
patch `76f1dcd8ad9e7124b69a21d813b6713d513ee9444999a9c57b542a0c84b3877c`;
handoff `18a091c1781ae93ab3c3479c5fc127eb992fa28c4c195b98e8a77a667380ffaf`.
Root independently reviewed actual behavior, wiring, memory/uncertainty handling,
full audit accounting and test scope. Removing only the diagnostic additions
reconstructs the complete original Worker byte-for-byte; fixture bytes outside
E8b and both mutation closures remain exact. Root acceptance at09:49:48UTC is
`repair/runtime-recovery-v1/E8B-ROOT-INDEPENDENT-SOURCE-ACCEPTANCE-v1.json`, SHA-256
`df355cae85560995de1fd8c543c272511e902992cb1e3e05c9ae3a096e93d4d7`.
This proves source acceptance, not actual negative return or runtime acceptance.

All source writers/processes/streams are closed; the managed Sol record explicitly
released scope with terminal `20081289…`. Final Root handoff releases its claims
separately. No fresh repaired packet, grant or runtime output was created. Next:
new-session acquisition and reviewed two-role/47-input binding, one unchanged-cap
actual runtime, complete independent readback, then neutral28+6 and separate
export. Foundation construction and partial BOTH/native/TUI/Rust-runtime work
remain unrun; extensive qualification remains deferred under its authorization
rules. Use the [latest continuation checkpoint](appended-application-plan.md#new-main-chat-checkpoint)
for complete limits, ownership and dependency order.


<a id="e8b-runtime-passed-c02-clipboard-expectation"></a>

### Actual runtime continuation — E8b passed, rich clipboard expectation repaired — 2026-10-18 UTC

This historical entry records runtime53325. The later
[trace allocation entry](#trace-allocation-runtime-92393) supersedes its pending
next-action statements; the C02 and C08 successors already ran and failed.
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

The exact runtime command is retained in
`repair/runtime-composition-repair-v1/ROOT-RUNTIME-LAUNCH-INTENT-E8B-v1.json`;
its packet is `RUNTIME-PACKET-E8B-v1.json` and grant
`ROOT-AUTHORIZATION-E8B-v1.json`. All new binding, original caller, failure
readback, Unicode observations and C02 source checks are under that runtime
scope's `e8b-continuation-v1/`. They preserve runtime33101 and every earlier failure.
The separate C02 source check used `/usr/bin/node --check` on the new fixture
only; it launched no Worker, native engine or browser. The source-chain and exact
reverse checks ran through Root's owned Python stdin diagnostic (47586e); fresh
packet shape admission closed zero (522b1a). No complete-runtime or neutral pass
is claimed from these checks.

<a id="trace-allocation-runtime-92393"></a>

### Runtime92393 trace failure and reviewed allocation successor

This supersedes pending next-action statements in the runtime53325/C02 entry.
C02 successor39290 exited 1 / `5e3008` after 86.257982148s, result `5f869c16…`:
C02 passed, then C08's small native cut target expectation failed. Source-derived
selection targeting explains the carrier event; the new fixture gives it a unique
ID and retains all root-input, source deletion/preservation and clipboard checks.

C08 successor92393 exited 1 / `9fb246` after 101.806910276s, result
`76118d2c9478da29dc257c9abbc7b9c08fdaebd99a14e82bd48d24712794d6ed`.
Two batches/28 cases passed their original full predicates. Clipboard nine cases
through C08 completed, including rejected-write source preservation, but C10 was
running when the unchanged 16,000-row trace cap failed. Its 208 emitted assertions
contained no false result; that does not accept the incomplete batch. Nine later
batches were unreached. Node2 passed; all owners/streams/thread closed and 47 inputs
and control hashes remained exact. Independent Root readback32667 / `73c9630`
confirmed closed failure. Peak sampled RSS/output: 3,258,871,808 / 239,638,064 bytes.
Original caller failure and all original bytes remain immutable.

Independent trace analysis found zero empty posted owner pairs; active owner
boundaries must remain. C04 accounts for approximately 2,989 rows and begins with
its own reset/real-copy seed. The accepted source repair selects exactly full10,
C04-only or remaining9, moves C04 after editor's original15, and enforces physical/
document allocations 16+144=160. Counted worst cases14/79 fit those allocations.
Every case body/assertion and longtext byte reverse exactly to the original.
Final Worker `c6a2c26d…` / clipboard `bf4baa3a…` passed syntax and independent
strong review. Actual extracted-function checks f378f3 passed3 admitted groups,
28 invalid groups and3 budget boundaries. Earlier test-generation failure17ade1
and rejected sparse-array selectorv1 are preserved; they are not passes.

Compact supervisor `4acd14b6…` changes only the future batch save call to compact
ASCII JSON with finite numbers and LF through the existing guarded raw save.
Full reverse preserves canonical size checks, trace limits, validators, schemas
and control serialization. Source checker0 / `bb2feb` passed16 value/type vectors,
3 nonfinite refusals and3 closed-report lossless round trips. Closed reports total
27,005,257 compact bytes; this is not complete32MiB neutral evidence. Worker
handoff failures and repair1 are retained in `runtime-report-compact-v1/`; Root
completed strong takeover metadata at17:23:56.953414UTC, before the unchanged
17:28:58.428927 deadline. No checker rerun or runtime occurred for that assignment.

Fresh packet `04aa4c7e…`, closure `211cf99e…`, binds47 inputs/191,366,289B/20roles.
Eight facts change from C08 (two JS roles and six driver copies);39 facts/12roles,
all six fixtures, native candidate/capsule, subject and limits remain exact.
All65 unique cases occur once across12 batches. Only C04 allocation/family changes;
all other batch fields and expected-negative/original31 predicates remain exact.
Fresh driver-v2 has the qualified HERE/vendor layout and original helper bytes.
Shape0 / `f6bacb` and independent complete47 physical/hash review accepted.
The first binding setup685d7e failed before packet save; subsequent discriminating
read80e1e1 verified guarded facts/hashes and a fresh driver copy was used. Initial
unused copies remain unconsumed by execution.

Evidence: `current_runtime/e8b-continuation-v1/trace-allocation-v1/` contains
`SOURCE-CHECKS-v1.json`, `PURE-CHECKS-v2.json`, `SPARSE-REPAIR-CHECKS-v1.json`,
`BINDING-SHAPE-v1.json`, `INDEPENDENT-REVIEW-v1.json` and
`NEXT-RUNTIME-REQUEST-v2.json`. Fresh v5 is absent and no execution grant/intent
exists. Another actual attempt requires explicit authorization: the original
maximum-one limit was exhausted and source repairs did not extend it. The request
preserves all existing360/330/180/90/30/15s,4GiB/512MiB bounds and allows one attempt,
with no retry. Complete originalcaller0/65/12/Node/closure/unchanged-input and
independent readback predicates remain unrun. Neutral/export/Foundation are gated;
production eligibility remains false.

<a id="runtime-a01-native-popup-capability"></a>

### A01 under the five-attempt allowance: closed popup failure

The current [continuation checkpoint](appended-application-plan.md#native-popup-capability-current)
supersedes earlier pending-runtime authority statements. Fresh grant
`ROOT-AUTHORIZATION-A01-v1.json` (`a51f3ed9…`) and reviewed intent authorized exact
packet `04aa4c7e…`. Original caller9828 closed1 / `ca4650`; driver92.037884498s,
external caller92.217s, charged92.218s. Full result
`6c9ed6bd9f54b701f1b4dd4189532bfea26c277d96598297bd880225cd7f1730`
accepts positive13/editor16/clipboard9 and fails popup.P00's unique native label.
Guard failure is null. Node2 passed; owners/streams/thread closed and all47 inputs
stayed unchanged. Independent readback0 / `2161ed` revalidated original predicates
and closure. Eight later batches were unreached. Four attempts/1,707.782s remain.

Pure decoder `ff431f` read the original3234-byte native publication: truncationfalse,
degradation28; primary31 and successor50 were unnamed, incomplete and cap-free;
primary option43/44 were omitted with empty labels. No engine was launched by that
decoder. Frozen Publisher0705d942 rejects an earlier secure input before private
ID comparison; Forms2bc9f9ce intentionally revokes whole-select authority for any
omitted option. Types63a435cd, GUI codec and peer share the old prohibition. The
user selected central native repair preserving ordinary web compatibility and
the full gate. No application layout workaround or refusal qualification is armed.

The vanilla comparison68829 closed0 / `c5f96a`, 2.604s, with one joined owner,
closed log and watchdog. Label association and computed styles were observed;
all plain-control key positives were inert. It is partial comparison evidence,
not keyboard behavior or appended runtime acceptance. The original evidence is
`current_runtime/runtime-allowance-20261018-v1/ordinary-select-firefox-v1/RESULT.json`.

Lossless codec source05e2a71b and isolated wiringv2 passed independent strong
review. Contracts0c8c9f1b preserve the original prefix; supervisor98fb6d28 only
wraps compact batch serialization; adapter884bfacf validates2..128 reports and
raw hashes/32MiB aggregate before reconstruction; gates8bd60c96 keeps original
predicates and raw evidence references. Focused source check3550 closed0 / `be626f`
in2.674s; source9b74ee94/receiptb3385d4a passed ten discriminating boundaries,
four exact original-report roundtrips and38 original case predicates. Encoded
sizes578851/364726/669835/47458 preserve every original byte. Popup remains failed.
Complete12-batch fit is unverified. Initial47 input verification plus final
preparation/result reread is not a new full47-input postflight. Original standalone
8/9 test failure, repaired9/92/0, repair1 and distinct setup recoveries are preserved.
Source pins remain unbound; no new runtime, stage/export or Foundation operation ran.

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
launch and tool discovery explicitly forbidden. Rich/native catalogs passed
source review and eight registered suites were reconciled: seven passed initially;
Windows source replay passed all 92 cases after an exact module-pin and fixture
wiring repair. The original 7/8 aggregate failure remains evidence.

The original S4 source cohort failed independent review on four concrete
issues; its closure and deadline remain intact. Root's successor corrected
bounded reads, per-compiler cache ownership, descriptor binding and all-five
P5 cache closure. The accepted routed tree changed only 19 old-S4 path literals
across eight of 23 copied control files. Its final unarmed 27-file physical map
is `ROUTED-FROZEN-CONTROL-SOURCES-v4.json` (`b2e6b4ec…`); the v3 controller's
preparation marker now matches the actual retained owner. Inexpensive source and
real-interface groups passed: inherited 18, strong controls nine, routed seven,
budget 21 and controller 15. The two initial route-test fixture errors are
preserved. No actual maintenance process or repaired engine runtime ran.

The unissued `DISABLED-NATIVE-SCOPE-COST-v7.json` covers one preparation
(600+15s), one plan (240+15s), one five-unit selective build (3,300+30s),
independent readbacks (450s total) and one shared metadata/control allowance
(150s) within **4,800s / 80 minutes**. Jobs1, 4GiB sampled RSS, 24 processes,
8GiB build output/disk growth, 16GiB available at plan/build launch and 4GiB
minimum free during execution are bounded. The source-only routed manifest
`ROUTED-EXECUTION-MANIFEST-v2.json` names 15 fresh outputs and exact owner
markers. Actual product-output caps remain with inner controls; the outer cycle
checks same-filesystem disk growth, RSS and process count. No candidate, capsule,
runtime or maintenance build has run; retained SDK `217e8ee7…` is unchanged.
Four runtime attempts / 1,707.782 seconds remain.

Current focused evidence is in `current_runtime/runtime-allowance-20261018-v1/`:
`NATIVE-MAIN-INTEGRATION-v2.json`, `FOCUSED-ORIGINAL-CALLERS-v2.json`,
`GUI-VALUE-FIXTURE-INTEGRATION-v2.json`, `gui-fixtures-v2/original-caller.log`,
`MAINTAINED-CATALOG-PURE-ADMISSION-v1.json` and
`codec-wiring-v4/ORIGINAL-ARTIFACT-CHECKS-v1.json`. The v4 adapter `99342306…`
passed independent review and two positive / 18 negative pure vectors. Original
report paths, bytes and hashes now join the physical closure before any read or
inflation; actual neutral stage/export remains unrun. This does not replace the
original full runtime gate or its failed result.

## Approved native preparation and closed metadata failure — 2026-10-18

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

Exact evidence is in
`current_runtime/runtime-allowance-20261018-v1/native-cycle-supervisor-v1/`:
`authorized-execution-v1/FAILED-CYCLE-CLOSURE-v1.json`,
`route-v2/controls/preparation/execution-v1/ROOT-CALLER-CLOSED-ACCEPTED.json`,
`authorized-execution-v1/metadata-interface-fixtures-v1/result-v3.json` and
`authorized-execution-v1/recovery-proposal-v1/DISABLED-RECOVERY-SCOPE-COST-v2.json`
(`6600fb0f…`). The complete candidate/dependency/capsule and 65-case/12-batch
runtime acceptance gates are unchanged.

### Native plan P5 product-index admission repair — 2026-10-18

The reviewed consumed-input projection retained all46 original depfiles and8,298
dependency paths without increasing the64MiB document limit. Binder31846 closed0 /
`daaef0`; its57,699,371-byte freeze contains72,021 files /5,946 directories, all
independently checked. Compile-free plan70628 closed1 /`b4af66` naturally after
206.928s: `Successful donor P5 product index differs`. Both supervisors closed
naturally and input postflight passed; no compiler, link or engine launched.

The original pinned Root receipt hashes compact ASCII JSON plus one newline;
the producer omitted that newline. The accepted168-row table is84,862 encoded
bytes with SHA-256 `babc9694ba2fad7f1160ceaa9630b8247f5762f3c8b3e7059c0f20f9cec639f8`.
Helper correction`87dbd55e…` and regression`cfc05431…` passed independent review.
Concurrent donor87 /maintenance80 tests passed. Actual `_p5_metadata` admission
passed in0.830s, caller48681 closed0 /`523a5d`, using real pinned metadata with
subprocess launches forbidden. No artifact-body readback or engine ran in that
probe. Fresh route-v4 controls passed four real-interface fixture methods in
three concurrent isolated groups. The original fixture setup errors and corrected
scout escaping calculation remain preserved; neither changes product evidence.

Fresh source preparation must carry the corrected helper. The old accepted
preparation, failed plan and failed metadata cycles remain immutable. Exact
receipts are under the native supervisor's `authorized-execution-v1/`:
`inventory-execution-v3/PLAN-CALLER-CLOSED-FAILURE-v1.json` and
`ACTUAL-P5-METADATA-INTERFACE-v1.json`. These checks do not qualify a repaired
candidate, capsule or complete65-case/12-batch runtime. Standing user authority
removes cumulative time and attempt caps while retaining all per-job limits,
performance criteria, closure/readback gates and SDK/kernel/full-build restrictions.

### Route-v4 plan timeout and explicit physical recovery — 2026-10-18

Preparation26271 closed0 /`29327a` in101.855450539s. Independent readback78654
closed0 /`2c91bb` and accepted369 source files, the complete42,779-file reuse
copy, all385 frozen inputs and natural closure. Receipt`a638a9f3…` and binder45987
closed0 /`bfad94` are reusable for those exact inputs. The57,704,007-byte freeze
contains72,027 files /5,946 directories, including all46 original depfiles and
8,298 dependency paths. No compiler, linker or engine ran.

Plan49830 exceeded its unchanged240+15s limit. The inner controller terminated
and joined its producer, returning a closed failed result with deadline and
postflight timeout errors. The outer nested guard retained its controller/log
even after its private supervisor exited naturally with primary1, reaped1, no
surviving descendants and no error. No passing plan was produced.

An independently reviewed explicit recovery pinned the original boot, namespace,
process start/argv/UID identities and process handles. It durably captured the
original private report, stopped only the parked controller and verified namespace
exit. Original caller49830 then closed137 /`ca251b`; final read-only inventory
confirmed no remaining namespace members. Immutable ledger state012
(`f55fa3bd…`) records terminal failure with closed=false, preserving the missing
original qualified controller closure separately from proven physical recovery.
Recovery13 real pipe/pidfd fixtures passed; original fixture failures and an
unrelated-host-service preflight permission failure remain retained. The reviewed
namespace-depth correction passed own-namespace and host read-only fixtures.

Evidence: native supervisor`authorized-execution-v1/index-recovery-v2/host-recovery-v1/`,
especially`ORIGINAL-CALLER-CLOSED-FAILURE.json`,`FINAL-HOST-NAMESPACE-EMPTY.json`
and`fixtures/result_v3.json`. A partial cost diagnostic and bounded watchdog
lifecycle repair are pending. All complete candidate, capsule, runtime and
production eligibility gates remain open.


### Closed phase baseline and maintenance watchdog clarification — 2026-10-19

The latest original plan83182 closed1 under its historical240s limit. Producer
exit0 and native plan verification succeeded; the postflight guard detected the
deadline. All owners, writer threads and logs closed correctly. Its terminal
failed ledger and outputs remain preserved. Preparation70505 and independent
readback52105 accepted receipt`52a20231…`; no replacement preparation is needed.

A source-reviewed, isolated480+15s diagnostic used that exact preparation and all
original inputs/predicates. Original caller32467 closed0 /`b46b06` in262.95s;
inner and outer owners closed naturally with zero exit. Root independently
checked the closed logs, original plan digest`fd3c9c0c…` and phase records. This
is **diagnostic evidence only**, never an accepted plan or build input.

| Boundary | Measured elapsed seconds |
| --- | ---: |
| Outer initial admission | 0.035 |
| Inner initial admission | 4.934 |
| Preflight, including full guard | 52.736 |
| Producer through qualified settlement | 159.078 |
| Plan verification | 1.328 |
| Postflight, including full guard | 42.444 |
| Inner final publication | 0.003 |
| Outer final publication | 0.004 |

The full guards took47.654s and42.274s and each freshly hashed all72,036 files /
6,333,024,204 bytes. Their combined CPU time was82.620s; producer child CPU was
153.627s. Postflight started at218.269s, leaving21.731s under the historical240s
limit. This supports CPU work before and during postflight as the cause; it
excludes a producer stall, metadata admission alone or expensive plan verification
as sufficient explanations for this run. Producer subroutine attribution remains
source-derived. The balanced full guard comparison was prepared and its real
interface fixtures passed, but **was not launched** after the human priority
clarification; no full-inventory optimization saving is claimed.

That clarification authorizes revising maintenance and aggregate qualification
ceilings. Chosen operational watchdogs are plan900+30s, selective build7200+60s
(inner6000s/jobs1), whole cycle14400s and metadata600s. Bind enclosing and inner
controllers consistently. Preserve RSS/process/disk/output protections, all exact
input and correctness checks, closure/readback and individual behavior timing
assertions. Measure the everyday packaging-only web and small portable-module
edit loops after reaching the working retained base. Retained SDKs remain
read-only; no full engine/kernel fallback or Git publication is authorized.

Evidence under the native supervisor: `phase-baseline-diagnostic-v1/`
`ROOT-CALLER-CLOSED-DIAGNOSTIC.json` (`f636ffc6…`), `experiment/child-phases.jsonl`,
`plan-differential-diagnosis-v1/MAINTENANCE-WATCHDOG-AUTHORITY-v1.json`, and
`guard-full-comparison-v1/launcher-review-v1/ROOT-fixtures-v1/RESULT.json`.


### Unfrozen-ancestor optimization regression and settled restoration — 2026-10-19

Plan75861 closed1 /`8a7b2c` in234.740s with natural inner and outer closure.
Producer exit0 and verification succeeded; postflight failed with `Ancestor
physical identity changed during freeze guard`. Immutable failed state004 is
`0378e333…`; no readback/build was authorized from that plan. Root checked all
72,036 file and5,946 frozen-directory identity7 records and found no changes.
The only ancestor version in the observed postproducer failure window was the
unfrozen `.agent-work` board root, matching the checked registry mutex timestamp.
Root did not rehash every input byte in that diagnostic.

The independent owner reproduced this with the real `agent_session.registry_mutex`
and small frozen fixtures: old and restored guards pass unrelated sibling-lock
creation/removal, while the optimized guard fails. All variants reject actual
frozen-file, namespace and mode changes. Root independently reran all21 cases
(`73a95d`,0.221s). `runner_controls_restored.py` (`021d1bfa…`) is exact settled
`2619961f…` except operational budget constants. The extra unfrozen-ancestor
version check was not an original acceptance predicate.

Evidence: `freeze-guard-repair-v1/failure-diagnosis-v1/{HANDOFF.json,ROOT-RESULT-v1.json}`
and `authorized-execution-v1/freeze-guard-cycle-v1/PLAN-CALLER-CLOSED-FAILURE.json`.
Fresh route-v8 source-map`cacd2814…`, independent source acceptance`fadfcd24…`,
and packet/physical acceptance`d0350f` preceded plan97781. It closed0 /
`943ea1` in248.033s with natural inner/outer closure, joined writers and
unchanged-input postflight. Independent Root reader64744 closed0 / `f96632`,
accepting `08fdb8ec…` after72,036 file and5,946 directory identity checks.
Pure projection `2c803f` retained all51 actions/2,076 archive members; metadata
assembly `b69946` and build binder33042 / `93315e` passed. Root independent
build-packet review28949 / `415220` passed in11.455s:72,045 files,5,948
directories,6,371,110,337 logical bytes and29 source hashes. The first
review-only caller59698 / `88c0de` failed before publication when the diagnostic
loaded both full freezes into one256MiB reader; a separate bounded predecessor
comparison corrected that setup without changing final gates. Failure evidence:
`retained-base-cycle-v1/ROOT-BUILD-REVIEW-SETUP-FAILURE-v1.json`.

Actual selective build1411 closed1 / `e9af8f` in1326.807s on packet
`f3b65179…`, grant `4ae59674…`, step `d55f7d11…`. Producer0 and
configure/build children0 had natural closure; all writers and logs closed;
unchanged-input postflight passed. Peak outer sampled RSS:2,463,899,648 bytes.
Candidate readback failed on an explicit recipe configuration reference absent
from Shim's depfile. Failure manifest `BUILD-CALLER-CLOSED-FAILURE-v1.json`
(`bf2a2bf8…`) and terminal state012 preserve this failure. Independent NC-R47
parsed every51 depfile:21 missing references, all exact
`reuse/build/webcore/cmakeconfig.h` / `59b4e3b7…`; no source or unified-member
omission. The older accepted Shim depfile has the same omission.
`prepare_reuse.py:629` binds this configuration to every unit; the maintained
producer at `_composition_prior_headers` explicitly describes recipe inputs as
distinct from the compiler header census.

Root's source correction `840ac7f3…` /105,507 bytes changes only
`native_capability_dependency_owners`: this exact configuration may lack a
depfile token, but frozen presence/hash remain mandatory; source, unified and
other dependency membership plus complete51 ownership/cache/VFS gates remain.
The diagnostic original22421 closed0 / `122062` in41.459993s after reading
168 artifacts /455,949,577 bytes,51 depfiles /20,269,748 bytes and2,734
cache files /16,476,241 bytes. All51 passed. This is **diagnostic only**, not
candidate acceptance. `native-config-binding-repair-v1/ROOT-CLOSED-51-RESULT-v1.json`
records it. Independent source review NC-R51 accepted the exact840 source.
Root's strong fixture takeover original23631 closed0 / `5ca173` in117.023954s:
the complete51 baseline and all nine mutation negatives passed. Original setup
and repair1 failures remain preserved. The result emitter's source pin is null;
Root independently binds840 in `ROOT-ACCEPTANCE-v1.json` (`83c929a7…`).
The fresh route-v9/C2 source review NC-R52 passed all five groups, with its
condition closed by this acceptance. Binder84261 closed0 / `e01e9d`; independent
physical review75955 closed0 / `5845be` in11.077s checked72,036 files /5,946
directories and28 source hashes. Packet `d61163f6…` and grant `dda0f6a1…`
are published. Full plan original1827 closed0 / `769e7f` in275.933s,
with natural closure and unchanged inputs. Independent Root23831 closed0 /
`f27848`, acceptance `e63958da…`; the37,387,345-byte plan SHA`fd3c9c0c…`
is identical to the historical accepted plan. The following pure projection
closed1 / `c6731a` in0.583s at its first save because the required output
parent was absent. No projection output or SDK operation occurred; C2 state008
remains terminal failed. The parent is now ordinary and empty; a fresh four-step
continuation reuses the accepted plan/readback. NC-R55 independently accepted
the exact four-step order and actual transition/refusal fixtures. Fresh grant
`e37f13b3…` was issued and initialized0 / `65b4f2`. Projection closed0 /
`77ff40` in0.512s; metadata assembly closed0 / `73af5f` in0.0119s;
build binder92244 closed0 / `0d6060`. Root physical review73849 closed0 /
`4de6ee` in11.267s, checking72,045 files /5,948 directories and every prior
freeze fact. Fresh build packet`15fe7e4d…` / grant`5b375f58…` is published.
Selective build original83868 closed0 / `9e3256` in1,372.544s under the original machine protections. Peak sampled RSS was2,442,215,424 bytes. Independent Root28478 closed0 / `323e7e`, accepting all168 artifacts /51 depfiles and full input/VFS/natural-closure predicates (`79f94be9…`). Preparation and full plan were not repeated. A missing parent stopped
ledger initialization before ledger creation; that setup failure is preserved,
the owned parent was created, and initialization closed0 / `4280aa`.
The fresh four-step C3 ledger is complete; no old failed result or ledger is resumed. It reuses
preparation70505 and the newly accepted plan, with five fresh units /46 imported
objects /five imported archives /one link /168 expected artifacts. Neither a
failed plan nor diagnostic plan is consumed. Runtime cohort source/layout review
NC-R38 passed. Capsule owner71796 closed0 / `6a9416`; independent readback`a0d299bf…` accepted16 distinct copies /163,589,359 bytes. Runtimepacket`4685c592…` passed independent47-input/20-role review`e8b3f105…` and actual metadata admission/configuration in1.7755s. Original56261 closed1 / `244e2a` after1.1025s: the loader required local private helper copies but packet paths retained their prior exact-byte locations. Node/browser/engine were not launched; zero cases ran; postflight was unexecuted, not passed. The original result and caller remain immutable. A fresh exact-copy placement recovery is exercising the real helper loader before another reviewed runtime launch. No complete runtime acceptance is claimed.
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


Separately, runtime aggregate watchdog sources900/840/540s passed five Guard
checks with startup90s, Node30s, protocol15s, cleanup15s and postflight15s
preserved. Root retained the fixed native helper`8b0d27b3…`; unnecessary modified
helper snapshots are excluded. These source checks are not runtime acceptance
and do not establish application startup/interaction performance.
