# Appended rich web engine feasibility

Source/API audit and authorized bounded probe, 2026-10-16. **The isolated
WebkitWasm prototype compiled and passed 18 actual-engine assertions in Node and
18 in an offline Firefox `file://` page.** This establishes a useful Wasm engine
lead. The combined native/browser/terminal feasibility gate remains open; no
production rich-engine dependency or supported platform matrix is qualified.
This record supports the [implementation plan](appended-application-plan.md#feasibility-gate-before-engine-commitment).

The required combination remains one internal HTML/CSS/JavaScript document and
event model on Linux x86_64/aarch64, Windows x86_64 and browser Wasm; styled
multi-node `contenteditable` with selection, formatting, clipboard, undo/redo and
IME; offline single-file/direct-file browser delivery; and a useful terminal
presentation of the same running document without a display server, GPU or
hidden graphical window. Terminal presentation may degrade while preserving rich
data. Platform WebViews, outer-browser application execution, static forms and
plaintext editor substitution do not resolve this gate.

## Candidate findings and source identities

| Candidate inspected | Useful evidence | Remaining gate |
| --- | --- | --- |
| Servo `4ba7263c55803faf7a341dd7aeda81f82d23f6a8`, manifest version 0.7.0 | Native embedding, input/IME controls, custom resources, AccessKit updates/actions and software rendering. | No supported full-engine browser-Wasm build established. Rich editing and terminal behavior need actual fixtures. |
| WebKit/WPE 2.54 documentation; WebKit API snapshot `bde098c73a9d44593053b603b50cfdc2776e060c` | Rich WebCore/JSC, embedding/editing APIs and built-in headless output. | WPE is a Linux port; no upstream browser-Wasm port in the reviewed inventory. Native helper processes and dependency closure need porting. |
| Ladybird `0b49ee4c305017969c45620253465dd67f348805` | Native Linux x86_64/arm64 and Windows x86_64 CI, CPU/headless mode, editing/IME and semantic interfaces. | Browser-Wasm engine build unsupported in reviewed sources; process, IPC, event-loop and stack/GC adaptation required. |
| WebkitWasm `68c618544e1f8af18ebce346281a6a49766aa194` | Patched non-pthread CPU engine compiled; rich editing and same-document semantic fixture passed in Node and offline Firefox. | Native ports, actual terminal integration, complete input/resources/services and a production retained SDK remain unfinished. |
| Firefox Wasm wrapper `bc69aaa5e2c5388bcf93a43b975b490bb940f4c0`, engine `2e1e835a5da5907e5ceef19aade58a7493f1e34d` | Actual windowless Gecko/SpiderMonkey in Wasm, software painting and live DOM evaluation. | Mandatory pthread/shared-memory deployment conflicts with direct-file delivery; IME/native/terminal integration also incomplete. |

Servo's pinned [workspace manifest](https://github.com/servo/servo/blob/4ba7263c55803faf7a341dd7aeda81f82d23f6a8/Cargo.toml)
declares MPL-2.0, Rust edition 2024 and MSRV 1.88. Its
[engine manifest](https://github.com/servo/servo/blob/4ba7263c55803faf7a341dd7aeda81f82d23f6a8/components/servo/Cargo.toml)
retains the native rendering/script infrastructure. Current
[embedding documentation](https://doc.servo.org/servo/) exposes useful native seams,
but [software rendering](https://doc.servo.org/servo/struct.SoftwareRenderingContext.html)
means software OpenGL, not a proven graphics-free semantic mode. Rich editing
has progressed: official [May](https://servo.org/blog/2026/06/30/may-in-servo/)
and [July](https://servo.org/blog/2026/08/31/july-in-servo/) 2026 reports describe
additional editing commands. The upstream
[Wasm discussion and clarification](https://github.com/servo/servo/discussions/39232)
distinguish compiling Stylo from compiling the complete Servo engine. None of
these observations establishes the required rich-editor or browser-Wasm fixture.

WPE's [headless implementation](https://github.com/WebKit/WebKit/blob/bde098c73a9d44593053b603b50cfdc2776e060c/Source/WebKit/WPEPlatform/wpe/headless/WPEDisplayHeadless.cpp)
means that requiring a visible Wayland compositor would be an obsolete objection.
Its [build configuration](https://github.com/WebKit/WebKit/blob/bde098c73a9d44593053b603b50cfdc2776e060c/Source/cmake/OptionsWPE.cmake)
still needs native threads, GLib/GioUnix, libsoup and graphics dependencies.
Headless rendered buffers are not a terminal projection. The
[public API](https://github.com/WebKit/WebKit/blob/bde098c73a9d44593053b603b50cfdc2776e060c/Source/WebKit/UIProcess/API/glib/WebKitWebView.h.in)
has JavaScript evaluation and editing facilities; a same-session semantic bridge
is plausible implementation work. The [official ports](https://docs.webkit.org/Ports/Introduction.html)
do not establish an upstream browser-Wasm engine port.

Ladybird's pinned [CI](https://github.com/LadybirdBrowser/ladybird/blob/0b49ee4c305017969c45620253465dd67f348805/.github/workflows/ci.yml)
and [view interface](https://github.com/LadybirdBrowser/ladybird/blob/0b49ee4c305017969c45620253465dd67f348805/Libraries/LibWebView/ViewImplementation.h)
provide stronger native evidence than older platform descriptions. Its WebView
interface belongs to its own engine. However, native
[helper-process launch](https://github.com/LadybirdBrowser/ladybird/blob/0b49ee4c305017969c45620253465dd67f348805/Libraries/LibWebView/HelperProcess.cpp)
and [stack handling](https://github.com/LadybirdBrowser/ladybird/blob/0b49ee4c305017969c45620253465dd67f348805/AK/StackInfo.cpp)
remain porting inputs. Running guest Wasm in Ladybird is not compiling Ladybird
to Wasm. Its [build instructions](https://github.com/LadybirdBrowser/ladybird/blob/0b49ee4c305017969c45620253465dd67f348805/Documentation/BuildInstructionsLadybird.md)
require newer tools than the ordinary foundation core; its core is BSD-2-Clause
with separate dependency terms. An optional engine toolchain must preserve the
project's existing build and binary baselines.

Firefox Wasm's pinned [build](https://github.com/HeyPuter/firefox-wasm/blob/bc69aaa5e2c5388bcf93a43b975b490bb940f4c0/gecko.js/build-lib.sh)
uses `-pthread`, `PTHREAD_POOL_SIZE=20` and `PROXY_TO_PTHREAD`. Its
[configuration](https://github.com/HeyPuter/firefox-wasm/blob/bc69aaa5e2c5388bcf93a43b975b490bb940f4c0/mozconfig.full.emscripten)
records problems with single-threaded startup. Disabling content-visible shared
memory does not remove these engine threads. Emscripten
[requires isolation headers for deployed pthreads](https://emscripten.org/docs/porting/pthreads.html),
so a costly Gecko build cannot resolve the current direct-file conflict. Its
[input bridge](https://github.com/HeyPuter/firefox-wasm/blob/bc69aaa5e2c5388bcf93a43b975b490bb940f4c0/gecko.js/js/index.ts)
does not supply composition-event transfer. A live-DOM terminal adapter remains
unimplemented despite useful evaluation and paint-suppression hooks.

Small components are not complete substitutes. [QuickJS](https://bellard.org/quickjs/quickjs.html)
provides an embeddable language runtime; [litehtml](https://github.com/litehtml/litehtml)
provides HTML/CSS layout. Their combination does not supply the required browser
DOM, rich editing transactions, selection and IME implementation.
[Blitz](https://github.com/DioxusLabs/blitz) has portable HTML/CSS components but
its reviewed documentation explicitly lacks JavaScript bindings; adding QuickJS
would still leave the required web/editing model to implement. These were
component-level exclusions, not pinned dependency selections.

## WebkitWasm: concrete missing integration

The [pinned bootstrap](https://github.com/theogbob/WebkitWasm/blob/68c618544e1f8af18ebce346281a6a49766aa194/tools/bootstrap.sh)
selects WebKit `aec9d2ad958e716ab4bca4bf03007e6edac7323f`
(`webkitglib/2.52`) and Emscripten 6.0.0. This is a custom single-process
WebCore/JSC embedding, not stock WPE. Its
[build configuration](https://github.com/theogbob/WebkitWasm/blob/68c618544e1f8af18ebce346281a6a49766aa194/src/embedder/embedder.cmake)
implements `BIB_PTHREAD=0`; its runtime implements CPU Skia raster mode. Threads
and a GPU are therefore not intrinsic requirements of this candidate. The
original supplier Node offscreen gate disables guest scripts. The separate
script-enabled local fixture below exercises the actual internal JSC session;
it does not implement a terminal frontend.

The [editor client](https://github.com/theogbob/WebkitWasm/blob/68c618544e1f8af18ebce346281a6a49766aa194/src/embedder/BibPageClients.h#L210)
has empty `registerUndoStep`, `registerRedoStep`, `clearUndoRedoOperations`,
`undo` and `redo`; `canUndo`/`canRedo` return false. Composition lifecycle,
`handleInputMethodKeydown`, `setInputMethodState`, content/selection-change and
client pasteboard callbacks also do no work. The
[browser input path](https://github.com/theogbob/WebkitWasm/blob/68c618544e1f8af18ebce346281a6a49766aa194/web/browser.html#L818)
lacks composition events and drops Ctrl/Meta combinations. These are unfinished
implementation, not merely tests awaiting execution. WebCore's pinned
[Editor API](https://github.com/WebKit/WebKit/blob/aec9d2ad958e716ab4bca4bf03007e6edac7323f/Source/WebCore/editing/Editor.h)
already provides composition set/confirm/cancel and editing machinery.

The [accessibility patch](https://github.com/theogbob/WebkitWasm/blob/68c618544e1f8af18ebce346281a6a49766aa194/src/patches/webkit-emscripten.patch#L648)
drops platform notifications. However,
[`bib_eval`](https://github.com/theogbob/WebkitWasm/blob/68c618544e1f8af18ebce346281a6a49766aa194/src/embedder/main.cpp#L1600)
evaluates in the live internal frame. The isolated prototype below exports
bounded live DOM/computed-style values, stable node handles and semantic actions
from that frame. Those actual engine exports passed the focused fixture.
Terminal reflow, rendering and interaction with that same session remain
unfinished; a second application DOM is not an acceptable substitute.

The [host loader](https://github.com/theogbob/WebkitWasm/blob/68c618544e1f8af18ebce346281a6a49766aa194/web/browser.html#L1083)
loads separate JavaScript/Wasm and imports/fetches resources. A non-pthread
build removes one deployment obstacle. The isolated local loader below proves
one closed single-file fixture in Firefox, while complete payload resource
integration remains unfinished. No working native Windows/Linux recipe for this
custom embedder was established;
its Emscripten host calls need separating from the shared WebCore adapter.

## Authorized bounded engine result

The user explicitly authorized the costed cold preparation/build and focused
editing/offline probe. The isolated, ignored evidence root is
`.agent-work/appended-implementation-20261016/webkit-engine-probe/`; `PROBE.md`
and `receipts/jobs.json` record exact commands, yielded handles, failures,
repairs and completion. These local artifacts are unshipped experimental inputs,
not a retained production SDK. No retained foundation kernel was configured,
compiled, linked or installed by this probe.

Source and tool identities:

| Input | Exact identity |
| --- | --- |
| Wrapper | `68c618544e1f8af18ebce346281a6a49766aa194`; complete 3,303,872-byte archive SHA-256 `66fcda8af76d3dd51419b9622c1a58e3dd61a1c0344194cfbd49ca246989b949` |
| WebKit | `aec9d2ad958e716ab4bca4bf03007e6edac7323f`; shallow blob-filtered checkout of `Source`, `Tools` and root files; supplier port patch SHA-256 `f25940d21c8ba37d62a6d48ea6da25053af1559bde323d0bfc9ba25cad2bca84` |
| Actual toolchain | Retained Emscripten 6.0.10-git/LLVM 24, Emscripten commit `d6c521a7f05449857c76bd99e396895583cf2083`; supplier recipe expects 6.0.0 |
| Retained SDK manifest | SHA-256 `217e8ee79c8f825e52cf92338a841cd7c79836666aaee7cbd1f41ee9e070920a`; 19,425 declared file hashes plus `sdk.json` |
| Final wrapper inventory | `receipts/wrapper-inputs-final.json`, SHA-256 `aa379dc16fae82e676e0dd19666b6afb58cd05c4e6d15929f6f6c427490db6ec` |
| Pinned API adaptation patch | `patches/0004-pinned-webcore-api-compatibility.patch`, SHA-256 `b02931284680867b04356a410bb52ffe22c5f31962dfd49fe4810d59edae5afd` |

<a id="source-only-prototype-checkpoint"></a>

The original source-only prototype remains frozen in adjacent
`webkit-prototype/PROTOTYPE.md`. Its `CHECKPOINT.json` SHA-256 is
`7f405efe1dba8d05e6b4fdfc9b6b45fc856989eef8be0c95cd33fd378609bef6`.
Three patches implement undo-step ownership/callbacks, UTF-16 composition and
same-document semantic exports, plus host transport. Their earlier 33 fake
interface/helper cases were source-only evidence. The separate engine probe
compiled and executed adapted versions of those WebCore-facing changes.

The actual-header check first rejected `event.ctrlKey()`; pinned WebCore exposes
`controlKey()`. The repair preceded normal compilation of `main.cpp`. The API
adaptation also replaces absent `StringBuilder.appendNumber` and uses empty
public `Editor.setComposition` to delete pending preedit: public
`cancelComposition` deliberately retains that text. Restoration of originally
selected rich content on cancellation remains unproved. Exact patch replay and
postimage checks passed. The build controller reported its changed launch
inventory instead of hiding the repair; `engine-input-reconciliation.json`
then verified the sole changed launch input, compile timing, final artifacts and
all 68 supplier-touched WebKit source files. The actual engine child exited zero.

All pinned dependency tiers built privately. Cold-bootstrap libpsl tools needed
ICU C++ runtime linkage; fontconfig tools needed the static FreeType/Brotli link
closure. Original failures and focused repairs remain recorded. Supplier
bootstrap was not used; Brotli was prepared before FreeType, dependencies used
at most four jobs, and the single engine build used three. Private Ruby/gperf,
Perl modules, fonts and dependency sources were retained with provenance; no
global SDK or distribution package installation occurred.

The non-pthread, CPU-rendered, script-enabled WebCore/JSC build completed in
**148.3 minutes**, including 190 seconds of configuration. It compiled and linked
the selected WTF, JavaScriptCore, Skia, PAL, WebCore and embedder graph. The local
engine duration exceeded the supplier's 1.5–2-hour estimate. At the final evidence
inventory this private tree contained about 3.91 GB of allocated regular-file
data, including logs and the offline HTML; this excludes the reused retained
SDK and other agents' scopes. Whole-host sampling recorded at least 4.36 GB
available memory during sampled periods; this is not process peak RSS.

| Output | Bytes | SHA-256 |
| --- | ---: | --- |
| `embedder.js` | 247,662 | `22643e9c6606aae5c3fafb313a1e51d04abd7b67406e25c35cb2c7fb896505fa` |
| `embedder.wasm` | 108,967,399 | `04d5ad068394e072f645e628b4a16b72fc92f5d6b9fb92a99eb62a745e03da9f` |
| Passing offline HTML | 145,549,252 | `c9daba4d523dd62d6d767b4e45e0f3ea2907f72bb99c281f277a95d3538718bf` |

`run-node-probe.py` passed **18/18** assertions using retained Node 24.19.0 in
2.49 seconds. `tests/probe-firefox.py` passed **18/18** using Firefox 153.5.0
(build ID 20261006170429) in 14.85 seconds, opening the assembled HTML through
`file://` with `crossOriginIsolated == false`. The same actual Wasm engine
performed both runs. Outer-host JavaScript transports inputs and retained engine
bytes; application evaluation occurs in internal JSC.

The fixture verifies CPU pixels, styled multi-node content and selection,
UTF-16 surrogate-boundary rejection, stale session/view rejection, Japanese and
emoji composition commit, keyboard undo/redo preserving exact `strong`/`em`
structure, cancellation at a caret, semantic omission and asynchronous
Promise/DOM-timer activation. The 800×600 RGBA outputs are byte-identical across
Node/Firefox: SHA-256
`a9e0fd47560ead5a9fa669b9e4ff0e4f89a1c03533350f1aa335f2fa500b4d0a`.
The inspected browser screenshot shows styled text, emoji, a button and the
presentation-only omitted subtree. Japanese DOM commit does not prove CJK glyph
coverage or physical OS IME event capture.

The first Firefox attempt failed during setup with **zero assertions**, because
this generated glue ignores `Module.wasmBinary`. The actual supported
`Module.instantiateWasm` hook now receives owned inline Wasm bytes. That loader
repair changed no engine source, JavaScript artifact or Wasm bytes. Failure input,
log and repair patch are retained. In the passing run, page `fetch`, XHR,
WebSocket, Worker and SharedWorker construction were blocked before engine
initialization; attempted calls and resource timing entries were both empty.
Actual post-link inspection found no separate `.data` package: ICU, fonts,
fontconfig and CA inputs were embedded. This proves the closed fixture, not
arbitrary appended-package resources or every production CSP.

The retained SDK's manifest files remained byte-identical. Our final link's
`tools/file_packager` child nevertheless added 13 Python bytecode files: its
`python -E` ignores `PYTHONDONTWRITEBYTECODE` and omits the compiler launcher's
`-B`. Exact bytes/physical identities and a forensic ZIP were preserved; after
all known readers stopped, only those 13 known-own files were removed with
explicit coordination authorization. Complete original file inventory was
**restored**, not continuously unchanged. `sdk-after-restoration.json` passes
all 19,425 hashes and the complete 19,426-file path inventory. Future links need
a private launcher/SDK clone that forces `-B` or a private Python cache prefix;
the original entrypoints remain unchanged.

The stopped read freeze `receipts/service-syntax-read-freeze-003.json` has
SHA-256 `95d18a80dcab66783362733e0ba7c85da1c6f5718dbd14e1c238c3a10a294752`.
It pins the complete 7,077-header post-build map, all 15 embedder files,
driver/configuration including root `cmakeconfig.h`, stopped Ninja graph/log and
the 2,022-file private cache
seed. The earlier 7,065-header prerequisite subset remains byte-identical; the
12 additional headers comprise two logged outputs and ten pinned generator
byproducts with completed-generator evidence. This receipt releases no new
compiler operation by itself.

<a id="next-bounded-port-prototype"></a>

## Remaining implementation and qualification gates

The passing experiment resolves the selected Wasm rich-editing/offline fixture,
not the combined P1W feasibility gate. Node is a headless **Wasm** host; it does
not establish native C++ support. An independent uncompiled native candidate
covers host seams, POSIX/CLoop and CPU-only Skia configuration, timer deadlines
and queued IDB teardown. Native Linux x86_64/aarch64, Windows, dependency closure,
reusable teardown and actual SDK consumers still need implementation and real
execution. No separate costly native build was launched.

Next implementation work must preserve the complete original rich requirements:

1. Finish common/native/browser host adapters, resize and reusable shutdown;
   generic physical key/modifier, OS IME, focus and clipboard routing; selection
   and rich preedit cancellation restoration. The current probe is one fixed
   800×600 page and does not prove the complete forms/editing matrix.
2. Connect semantic exports to actual terminal reflow, cells and actions from the
   same internal engine session. Existing typed codec/reflow utilities and fake
   fixtures do not constitute an integrated rich terminal application.
3. Complete immutable appended-package resource resolution and the actual
   foundation service binding before first author script, with completions after
   the engine turn. Source-only resource/service overlays and syntax checks do
   not prove an integrated loader or kernel-service execution.
4. Produce an application-neutral retained engine SDK/factory and integrate it
   through the supported build/retained-kernel route. The diagnostic baseline is
   non-modularized CommonJS glue and must not be relabeled as that production
   factory. Missing retained inputs must still fail without rebuilding a kernel.
5. Run focused actual integration checks after those changes. Broader native,
   browser, SDK and release qualification remains a separate stage under the
   [manual-qualification policy](../AGENTS.md#development-checks-and-manual-qualification).
   Unexecuted scopes are not passes, and unfinished integration is not merely
   pending certification.

A private default-off JSC service candidate passed actual-header syntax checks
for its main and bridge translation units, after a preserved missing
`LocalFrameInlines.h` failure and one-include repair. It was not linked or run.
The combined resource/service bootstrap and provider successors are independent
source work, outside the baseline identities above.

For future cold-probe budgeting, upstream's pinned
[build notes](https://github.com/theogbob/WebkitWasm/blob/68c618544e1f8af18ebce346281a6a49766aa194/BUILD.md)
report about 15 GB and 30–90 minutes of preparation, then 1.5–2 hours for a full
mode-changing rebuild and approximately 5 GB compiler memory with four jobs.
These remain supplier observations, not guarantees; the measured local engine
build above took longer. Its pinned
[license file](https://github.com/theogbob/WebkitWasm/blob/68c618544e1f8af18ebce346281a6a49766aa194/LICENSING.md)
permits redistribution subject to retained notices/disclaimer; the README's
instruction to choose a license is stale. WebKit and dependencies retain their
separate [licensing obligations](https://docs.webkit.org/Other/Licensing.html).
