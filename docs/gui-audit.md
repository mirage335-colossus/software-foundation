# GUI boundary audit and qualification

The consuming project integrates every host supplied by the pinned gui-boundary
revision: terminal, framebuffer output, FLTK, SDL window, Rev, hosted browser and
compiled browser Wasm. Every path composes the same application/core library and
shared layout. Ordinary changes within the existing public vocabulary require no
backend-specific feature implementation. This is a tested finite contract, not
a promise that every future OS facility or new control needs no adapter work.

## Inspected paths and resolved maintenance gaps

The review followed declarations through application publication, retained state,
input normalization, rendering, host event loops and service completion. It
included shared geometry/text/bitmap/runtime rules, all native adapters, terminal
mode management, framebuffer input/damage, both browser transports and renderer,
resource preparation, pinned dependency manifests and relevant conformance tests.

The public boundary supports groups, labels, buttons, toggles, choices, text,
lists, bitmaps and menus; shared logical bounds, clipping, scrolling, pages,
availability, stable identities, immutable image ownership and queued services.
Application identifiers occur only in shared code and fixtures. Native adapters
select behavior by generic widget kind and declared values.

This integration closes these practical consumer gaps:

- Every backend has an explicit build target, dependencies and host lifecycle;
  previously uncomposed paths are not left as references to a different example.
- Terminal/SDL platform runners accept a typed application. Maintained exact
  patches replace hardwired demonstration composition and remove SDL's
  demonstration-specific smoke actions; host qualification calls one shared
  application scenario and contains no feature dispatch.
- Native and Wasm browser bridges instantiate one runtime; both use identical
  verified DOM renderer/assets. The portable hosted transport avoids POSIX-only
  pipe readiness, bounds request/response queues and time, and reaps failed children.
- The feature fixture adds a real control at runtime and exercises its meaning
  through each selected adapter. Canonical serialization compares declarations,
  geometry, actions and values; a browser fixture compares actual DOM geometry.
- GUI install destinations exist behind reviewed lock metadata. Local development
  can build all hosts; an unresolved dependency license cannot silently turn into
  a redistributable binary package.

[Patch provenance and upgrade rules](../gui/patches/README.md) identify the exact
local adaptations. The source dependency remains unchanged. Upstreaming typed
runners and portable pipe handling would eliminate those maintained changes.

## Capability and fallback policy

| Concern | Shared contract and required behavior | Qualification limit |
| --- | --- | --- |
| Geometry | One logical layout; scale applies at the renderer; clipping/hit testing use the same resolved geometry | Native fonts and terminal cells need not have identical pixels |
| Input | Shared edit/selection normalization; stable record keys; stale generation/base rejection; disabled/hidden controls cannot act | Native IME, touch, drag capture and complex text need selected-platform checks/extensions |
| Text | UTF-8 at the boundary, explicit byte limits, common editor policy, visible rejection status from core validation | Bitmap font coverage is finite; this core intentionally accepts printable ASCII records |
| Accessibility | Shared labels/names, row descriptions, keyboard traversal, readable status text; browser uses semantic controls/ARIA | Accessible names alone do not qualify a screen reader; terminal/framebuffer/native accessibility bridges remain profile-specific |
| Services | Explicit request identity, exactly one accepted completion, cancel/error distinguished, late completion rejected after shutdown | Prompt is the common implemented service; file/location calls explicitly fail in these native hosts |
| Clipboard | Adapter/host owns platform access, application never receives native handles | FLTK/Rev expose host clipboard writes; SDL handles editor clipboard keys; browser permissions can reject requests |
| Rendering | Immutable frame ownership, revision/damage tracking, retry presentation without repeating core mutation | GPU drivers and physical high-DPI displays require native target qualification |
| Async work | UI thread owns adapters; workers publish owned values through shared runtime; close cancels queues | Never retain toolkit objects in workers or apply stale callbacks to recreated controls |
| Session lifecycle | New browser epoch on recreation, ordered operations, duplicate command suppression, bounded transport | Hosted server is loopback-only and is not a multiuser deployment framework |

Capabilities belong to the selected deployment profile, not toolkit-name branches
inside shared features. Before adding a service, state required semantics and
which profiles support it; supply a generic fallback or disable the shared action
with an explanation. Unsupported requests must complete with a visible error,
never claim success. A shared contract extension must land with all required
adapter implementations and fixtures before a feature depends on it.

Practical checks include unsupported file-service errors completed exactly once,
prompt cancellation, close with pending service, invalid core text and recovery,
stale events, browser retry/session isolation, transport timeout/blocked-pipe
cleanup, disabled-action behavior, resize/minimize recovery, frame lifetime and
injected presentation failure. The browser fixture verifies accessible control
and row names. It does not substitute for assistive-device testing.

Remaining vocabulary limits include multiwindow application coordination, rich
text, complex script shaping, drag capture, native accessibility trees, file
objects and more elaborate layout rules. If an adopted project needs them, extend
the common contract first and prove behavior in every required backend. Do not
invent unrelated backend-specific implementations to conceal an unsupported need.

## Executed verification

The local profile uses Debian 13 x86-64, Clang 19.1.7 and its matching module scanner,
CMake 3.31.6, Ninja, FLTK 1.3.11, SDL 2.32.4, system GLEW/FreeType and the pinned
Rev sources. Optional distribution packages were extracted into an isolated build
prefix; none are fetched by CMake. This newer development host does not establish
Debian 12 or any older release's binary baseline.

| Path | Executed evidence |
| --- | --- |
| Terminal | Real process on private PTY; input, normal close and interruption restore modes; shared extension/geometry suites |
| Framebuffer | Real pixel renderer, pointer/keyboard input, shared extension, immutable frame and resize checks |
| SDL | Real SDL queue, text/key input, added control, resize, software texture upload and close using dummy video |
| Rev | Compiled 46 toolkit modules; real native callback paths and OpenGL capture under Xvfb; shared extension, services, close and serialized parity |
| FLTK | Actual native editor/button/list callbacks under Xvfb; shared extension, serialized parity, capture, unavailable-service error and pending-service shutdown |
| Hosted browser | Actual child and loopback sessions, identity/retry/security checks, child/worker cleanup; real Firefox/Chromium editing and prompt cancellation using copied assets |
| Wasm browser | Actual Emscripten 3.1.69 compilation and Node execution; real Firefox/Chromium editing, prompt cancellation and DOM geometry equality with hosted mode |

Firefox 153.4.0 ESR and Chromium 154.0.8037.57 rendered both transport modes
successfully. Shared DOM geometry also matched between those engines. Their captured
screens show the same ordered controls, spacing and logical sizing, with only the
transport status text differing. SDL/framebuffer and Rev captures retain the same
shared arrangement; native glyph rendering may differ. Captures are diagnostic
build artifacts, not golden images asserting exact pixels across machines.

The initial 20 native GUI checks passed. After adding installed qualification,
all six native executable smoke checks plus the four affected shared/parity/PTY/HTTP
checks passed, as did the rebuilt Wasm check, seven source/patch guards and the
separate actual Firefox/Chromium runs. Eleven unchanged pinned
upstream suites cover contract, bitmap, adapter, layout, runtime,
presentation, extension, interaction, framebuffer, terminal and web behavior.
The upstream DOM-renderer suite and local source/patch guards supplement them.
Tests that depend on a display, Node, browser or toolkit are explicit; an omitted
lane is missing evidence. See [build and test commands](gui-boundary.md#build-and-run)
and the optional real-browser command below.

```sh
python3 -B gui/tests/browser_test.py \
  --server build/gui-native/gui/web/serve.py \
  --executable build/gui-native/gui/foundation-gui-web \
  --wasm-dir build/gui-wasm/gui --output build/gui-browser-check
python3 -B gui/tests/browser_test.py --browser chromium \
  --browser-executable /path/to/chromium --driver /path/to/chromedriver \
  --mode hosted --server /copied/share/software-foundation/web/serve.py \
  --executable /copied/bin/foundation-gui-web --output build/chromium-hosted-check
python3 -B gui/tests/browser_test.py --browser firefox --firefox /path/to/firefox \
  --mode wasm --server /copied/share/software-foundation/web/serve.py \
  --wasm-dir /copied/share/software-foundation/web --output build/firefox-wasm-check
```

The browser fixture needs the explicitly selected browser, a matching ChromeDriver
for Chromium, and permission to bind private local sockets. Inputs are prepared
outside the fixture; it never installs browser packages. Chromium uses the
[documented driver setup](https://developer.chrome.com/docs/chromedriver/get-started)
and [WebDriver HTTP commands](https://www.w3.org/TR/webdriver2/).
`--mode hosted`, `--mode wasm` and default `--mode both` let artifact qualification
exercise each deliverable separately. Source-build server assets and Wasm modules
may reside in different directories. Installed modules and server assets share
`share/software-foundation/web`. The output directory must be new.

Only after successful checks and cleanup does the fixture publish
`qualification.json`: schema version `1`, status `passed`, engine, actual browser
version, selected mode, completed checks, explicit browser arguments and the
verified input SHA256 map. It rejects changed input bytes, saves captures and
`geometry.json`, removes its temporary profile and stops browser/server children.
Failure leaves no success receipt. Retain that receipt with the release's broader
environment and compatibility evidence. `FOUNDATION_GUI_CAPTURE_DIR` optionally saves native fixture captures
to an existing claimed output directory. Keep browser/display runs separate from
ordinary focused edit loops unless those paths changed.

Windows, ARM64, macOS, Debian 12 execution, physical GPU/input devices, screen
readers and browser engines beyond the two listed above were not qualified by this
local profile. Cross-platform code and CI recipes are implementation support;
release claims require execution in the actual declared profile.

## Distribution gate

The pinned dependency has no top-level license declaration. Its font, bundled
library and toolkit notices are separate and do not establish permission for the
whole GUI integration. The lock records `license: NOASSERTION` and
`redistribution.approved: false`. CMake propagates
`FOUNDATION_GUI_DISTRIBUTABLE=false`; packaging must reject GUI configurations.

After upstream supplies reviewed terms, update the dependency pin/inventory and
record every required license/notice under `redistribution.license_files`. Only
reviewed metadata with a declared license, approval and verified license files
activates installation. Native executables go under `bin`, browser assets/modules
under `share/software-foundation/web`, and dependency notices under the installed
documentation directory. Then verify the complete runtime library closure and
license bundle on every target before issuing release artifacts. No configure
switch waives this review.
