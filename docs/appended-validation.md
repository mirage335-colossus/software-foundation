# Appended implementation checkpoint

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
