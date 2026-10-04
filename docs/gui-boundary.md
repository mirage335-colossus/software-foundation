# GUI ownership and integration

Application features have one implementation. Shared code owns state, commands,
labels, availability, rows, menus, layout and service intent. Adapters interpret
public declarations and return public input. A renderer understands a button;
it never understands a product command or privately recreates application layout.

This repository consumes [gui-boundary](https://github.com/mirage335-colossus/gui-boundary)
at the revision and SHA-256 inventory in [the lock](../third_party/gui-boundary.lock.json).
All seven provided host paths are integrated. The [audit](gui-audit.md) distinguishes
implemented paths, executed checks and remaining platform qualification work.
The complete backend source is an explicit retained dependency, with reviewed
adapter/runner patches in this repository. There is one public widget vocabulary;
there is no independently evolving copy of the upstream renderer tree.

## Dependency direction

```text
core library <- shared application and layout
                       | Snapshot / Event / Adapter
                       v
               public GUI boundary
                       |
             retained state and input rules
                       |
          native controls / terminal / pixels / browser
                       |
             platform event loop and services
```

Core headers are GUI independent. A source-boundary guard runs before the shared
GUI library compiles, even with `BUILD_TESTING=OFF`; unchanged inputs reuse its stamp.
The guard recursively checks C/C++ source/header variants under shared and host
trees, so moving a feature or adapter into a nested directory cannot evade the
application/backend separation checks. It also follows literal local includes through
helper headers, rejects computed includes on either side, and identifies concrete
backend aliases and domain dependencies. Only a composition root may include the
public application declaration. Its discovered local dependencies participate in
incremental guard invalidation. This source tripwire supplements executable
conformance and interface review; it is not a C++ parser. [Shared application code](../gui/shared/application.cpp)
uses `foundation::Store`, the same core library as the CLI. The core owns record
validation, capacity, identities and mutation. Shared GUI code projects records
and owns editor state, error recovery, enabled actions, count, menu, heading prompt
and responsive layout. The ordered [view definition](../gui/shared/view_definition.hpp)
is consumed by both widget construction and layout: control identity, kind, text,
font role, order and height have one declaration. Its [header](../gui/shared/application.hpp) exposes only
`gui::Adapter`. No native object crosses into application code.

The shared library is linked into every selected executable. One native build
graph builds all selected native hosts and their tests; Emscripten uses a separate
toolchain build directory because its output is a different target platform.
Source changes and tests still use the same library and CMake definitions.

## Shared bounded task and shutdown

The visible **Count text**, **Cancel task** and progress label are declared in the
same view table as the other controls. `Application` copies authoritative records
into [TextTask](../gui/shared/task.hpp), then applies owned progress values on the
UI thread. The value-only `TaskExecutor` interface selects native background
execution or cooperative stepping once per target platform; features and layout
are identical. Wasm uses cooperative work inside its existing module Worker.
Native applications use one persistent producer and a one-slot latest-progress
mailbox. A native work chunk covers at most 4096 bytes; cancellation/replacement
invalidates its generation without waiting in the event handler. Shutdown joins
the producer before its owned state is destroyed. No worker retains an adapter,
widget or application reference. The cooperative executor processes at most 256
bytes per tick and remains available for deterministic fixtures and embeddings.

Editing and clearing live records cannot change captured input. A new task has a
new generation; cancellation, restart and close reject late or repeated completion.
The bounded in-memory worker is not a promise that arbitrary external calls can
be interrupted. OS file services have a separate lifecycle described below.

The common native `Session` advances work through `Application::tick`; terminal
and SDL typed runners obey the same contract. Hosted and Wasm browsers use one
polling module, with at most one outstanding poll and no queued poll accumulation
on a failed connection. Only an authenticated, new, ordered poll advances work;
retrying the same operation does not repeat it. Navigation stops timers and the
resize observer, cancels a pending dialog, rejects queued input and releases the
session. Browser edits coalesce only when adjacent and compatible. An intervening
action or different control preserves the prior edit as an ordering barrier.

The [task fixture](../gui/tests/task_test.cpp) tests budgeted progress, copied
input, edits during work, cancel/restart, stale completion, malformed progress,
close and duplicate browser polling. Installed host checks run the same shared
start/cancel/restart/completion scenario. The actual browser fixture checks the
visible task through both transports; renderer fixtures force slow delivery and
check action order and prompt withdrawal. Native supplier FLTK, Rev and clipboard
conformance checks run against the selected adapters when host testing is enabled.
The Rev supplier fixture also runs at scale 1.25 and maps its bitmap sample points
from logical coordinates to actual physical pixels; expected colors do not change.

## Touch input and embedding a pixel display

Physical pointer input has press, move, release and cancel phases. The first
contact owns the gesture and captures an exact widget identity and generation.
Additional contacts cannot complete it. Moves and releases continue to reach that
owner outside its original bounds, while a removed, disabled, obscured or replaced
target, a modal transition, focus loss, resize or close revokes the old gesture.
A standard button activates once on a valid release; pressing or cancellation
cannot activate it. Raw pointer surfaces receive phases through the same public
contract, without application commands inside a renderer.

The SDL runner translates finger events into logical client coordinates. It
filters synthetic mouse events from touch and retains one contact across a drag.
Browser raw surfaces use pointer capture and the same ordered event vocabulary.
The [touch fixture](../tests/gui_touch.cpp), [browser fixture](../gui/tests/touch_test.mjs)
and [SDL translation fixture](../tests/gui_sdl_touch.cpp) exercise these rules.

[`FramebufferHost`](../gui/host/framebuffer.hpp) supplies an embedding composition
interface with `resize`, `contact`, `cancel` and `present`. A device driver provides
logical coordinates and consumes immutable RGB24 frames plus damage metadata;
the application and shared interaction policy remain unchanged. The caller owns
timing and calls the interface on one thread. Retained frame storage can outlive
presentation, and a failed display operation does not consume the frame revision.
The [fake input/display driver](../tests/gui_embedding.cpp) demonstrates this
without SDL, a window server or a hardware device. The optional host-side
[`copy_frame`](../gui/host/framebuffer_surface.hpp) converts damage into an owned
RGB24, RGBA8888, BGRA8888 or little-endian RGB565 surface with explicit stride.
It validates dimensions, storage, format and damage before any write; pixels
outside damage and row padding remain unchanged. The display must request full
damage when its storage is new or its last revision was skipped.

SDL drains at most 128 events or roughly 4 ms before its next tick and paint.
A continuously nonempty input queue therefore cannot indefinitely defer painting;
touch release/cancellation remains ordered and no event is dropped.

This is a porting seam for a touchscreen, VR panel or embedded display. A real
port still supplies calibrated input and display drivers, an appropriate C++20
runtime and sufficient memory. The example does not claim an Arduino board port
or hardware touchscreen qualification.

## Worker execution and an offline browser application

The Wasm host creates one dedicated module Worker for each application session.
The existing ordered Client envelopes cross a bounded message boundary; only one
request is outstanding. The client snapshots each accepted operation and bounds
it to 1 MiB, with an 8 MiB total including the in-flight operation. Adjacent
compatible edits coalesce without crossing action barriers; rejected work cannot
consume a sequence number or silently drop an earlier accepted action. C++
callbacks and ordinary application work execute away
from the browser UI thread. DOM rendering, user input and dialogs stay in the
browser thread. This complements bounded application work without adding pthreads,
SharedArrayBuffer, Asyncify or an audio loop.

Close waits for acknowledgment after C++ destruction. A bounded timeout or Worker
failure terminates the Worker, rejects pending work and requires a new session
with a new epoch. Startup failure, late responses and close during initialization
cannot revive an old session. See the [transport implementation](../gui/host/wasm_transport.mjs)
and [Worker ownership notes](../gui/host/wasm-worker.md).

A Wasm build also produces
`gui/wasm-package/software-foundation-wasm.html`, `web-manifest.json` and
`manifest.sha256`. The single HTML embeds the **generated patched** renderer,
transport, Worker, compiled factory, Wasm binary, styles and applicable notices.
It can be opened as a local file. Its content policy disables network connections;
module Blob URLs are owned and revoked by their creating lifetimes. Build it with:

```sh
./build.sh build release --gui --gui-backends wasm --sdk /absolute/prepared-sdk
```

The ordinary graph builds the package as `foundation-wasm-package`; it reuses the
same application target and prepared SDK. The package manifest binds every input
and the final HTML. Packaging does not download a runtime or a browser. Actual
browser checks remain necessary when changing a compiler, Worker lifecycle or
content policy; Node fixtures alone cannot qualify browser behavior.

## Bounded content services

**Actions → Import entries / Export entries** use generic `read_text` and
`write_text` capabilities, appended to the public service vocabulary without
changing existing numeric kinds. They carry owned UTF-8 content and a maximum
64 KiB limit. Application code receives no filesystem path, browser File or
native dialog. Import parses one printable-ASCII entry per line, supports CRLF,
and commits the complete replacement only after every record passes core
validation. Existing record IDs are not reused. A malformed/oversized import
leaves the collection unchanged; service IDs reject duplicate or stale replies.
Export uses the same core records and rejects content exceeding the service limit.

FLTK and Rev composition roots inject [`FileServices`](../gui/host/file_services.hpp)
through `NativeSession`. Their generic modal path prompt keeps paths on the host
side. One worker owns the selected path/content; the UI polls a value-only result.
Export exclusively creates a sibling temporary file and replaces the destination
only after a complete successful write. Failures/cancellation before that commit
remove the temporary file and preserve the destination. Cancellation after commit
cannot undo it or report it as unperformed. This is not a crash-durability promise.
Byte bounds and cancellation checks do not bound a stalled filesystem call;
shutdown deliberately joins it instead of detaching a writer. Applications needing
hard deadlines for hostile filesystems require a separately owned process or a
platform-specific cancellable I/O service. The generic embedding `Session` imports
no filesystem provider; terminal/framebuffer/SDL adapters report unavailable file
content services unless the embedding supplies one.

Browsers offer an explicit file input and Download button. The host bounds bytes
before decoding, rejects invalid UTF-8, preserves a leading BOM as content just
as the native reader does, aborts withdrawn dialogs and ignores late reads. Export success means a download was offered, not that the user saved it.
The shared status deliberately says “Export handed to host”. Both hosted and
single-file Wasm paths use the same helper with no network dependency.

## Browser presentation scheduling

Both transports accept receipts and authoritative state immediately, while the
presenter coalesces replaceable visual snapshots into one animation frame.
Service changes, errors, initial state and close flush ordering boundaries; actions,
service replies and acknowledgments are never dropped. Editor/focus completion
uses accepted state even before painting. Measurements reuse one probe, prune
obsolete cache identities and yield after 64 probes or 4 ms; stale continuations
cannot publish after replacement/close. List rows and cells retain their keyed
DOM identity across selection and content updates. These are general responsiveness
examples, independent of application-specific high-frame-rate computation.

## Complete offline GUI input group

[The source-group tool](../gui/source_group.py) exports every tracked file from the
clean pinned dependency, including all adapters, host code, tests, documentation,
font files and retained toolkit/library archives. It also retains the exact
Foundation dependency lock, integration patches and patch applicator. Git metadata,
build outputs and ignored local files are excluded. The group contains
`gui-inputs.tar.gz`, `manifest.json` and `SHA256SUMS`; it is a source input group,
not an SDK. The verified group is committed under
[`third_party/gui-inputs`](../third_party/gui-inputs/manifest.json), including
upstream's Rev sources, retained GLEW/FreeType archives and fonts. The FLTK
adapter is included; the FLTK library remains a distribution or SDK dependency. Compiler, platform headers
and toolkit dependencies come from distribution packages for ordinary native
Linux builds, or from an explicitly selected prepared [SDK](sdk.md).

```sh
./build.sh test dev --gui --gui-backends terminal,framebuffer,hosted-web --label gui
```

This command uses only checkout bytes and installed host packages. The group
stays compressed in source control and is restored once per owned GUI build tree;
unchanged restored files are verified and reused without rewriting them.
Ordinary core builds do not restore the group. Integrity checks still detect
changed retained or restored inputs. No SDK is built implicitly.

For a dependency upgrade or an explicitly maintained external group:

```sh
python3 -B gui/source_group.py export --source /path/to/gui-boundary \
  --output /path/to/retained-gui
python3 -B gui/source_group.py verify /path/to/retained-gui
python3 -B tools/build.py test dev --label gui --jobs 2 \
  --gui-input-group /path/to/retained-gui \
  --gui-backends terminal,framebuffer,hosted-web --build-dir build/gui-offline
```

Export verifies the clean Git revision and complete tree identity. Preserve exact
repository bytes when acquiring sources; disable automatic checkout newline
conversion with `git clone -c core.autocrlf=false`. Verification
checks every archive file's name, size, logical mode and SHA-256, rejects links,
duplicates, case collisions, unsupported entries, extra/missing inputs and bounded
size violations, then reconstructs the complete upstream Git tree identity from
bytes and modes. That tree must match the reviewed lock; changes to uncompiled
source are therefore detected too. Retained patches must match this checkout
exactly. Configuration mirrors the complete verified public-header closure into
the build tree before applying local contract extensions. This is required for
quoted sibling includes to use the same patched definitions in every caller. The group checksum detects transfer damage; the repository's reviewed
lock supplies input identity. Keep the group under the signed release inventory
when transferring it through a release channel.

The build wrapper restores into its owned build inputs before computing source
identity. With `-DFOUNDATION_BUILD_GUI=ON` and neither source selector, direct
CMake uses the checkout's bundled group. Explicit source/group selectors take
precedence; a missing or corrupt explicit input never falls back to the bundle.
Direct CMake consumers can select
`-DFOUNDATION_GUI_INPUT_GROUP=/path/to/retained-gui` instead of
`FOUNDATION_GUI_SOURCE`. Both routes use the same verification and atomic restore,
require no network or Git in the restored tree, and expose the verified upstream
source to the ordinary build graph. Repeating restore accepts only the exact
existing inventory; changed or foreign output is preserved and rejected. Select
a new owned destination after an intentional input upgrade. Windows retains Git
logical executable modes without relying on POSIX permission bits; native Windows
qualification remains a separate platform check.

For explicit restoration, use
`python3 -B gui/source_group.py restore /path/to/retained-gui --output /path/to/restored`.
Its JSON receipt records the `source` directory, group manifest SHA-256, revision
and redistribution status. Source exports retain this input as the GUI supplement;
prepared consumers use that retained input. Local retention and build remain
available independently of distribution permission. `verify --redistribution`
requires the reviewed dependency approval and complete notice inventory. The
current owner-specific approval is described in the [distribution gate](gui-audit.md#distribution-gate);
ordinary export does not grant a general downstream supplier license.

## Build and run

The bundled group supplies the locked revision. Configure/build never download
source, libraries, toolchains, fonts or browser modules. A separate pinned checkout
is only needed when deliberately maintaining or overriding that input.

```sh
cmake -S . -B build/gui -G Ninja -DCMAKE_BUILD_TYPE=Debug \
  -DFOUNDATION_BUILD_GUI=ON
cmake --build build/gui --target foundation-gui-tests --parallel 2
ctest --test-dir build/gui -L gui --output-on-failure --parallel 2
./build/gui/gui/foundation-gui-terminal
./build/gui/gui/foundation-gui-framebuffer build/gui/entry-list.ppm
python3 -B build/gui/gui/web/serve.py --executable build/gui/gui/foundation-gui-web
```

The last command prints a loopback browser URL. Stop it with Ctrl-C. Separate
tabs receive separate processes and random session identities. The server binds
only loopback; its exact Host/Origin checks and session tokens are not a deployed
multiuser authentication system. Do not expose it through a public proxy.

Every native executable accepts `--smoke-test` and `--self-check`. A fresh
application runs the same shared validation/edit/add/remove/resize scenario while
the host presents through its actual adapter, closes it, and emits exactly
`software-foundation gui smoke: ok` on success. Feature identities remain in
`Application::qualify`; hosts supply presentation steps only. Use a bounded process
timeout when qualifying copied artifacts. FLTK/Rev need a working display; SDL
needs its declared video driver. The terminal check renders real terminal rows
without requiring a TTY; the separate PTY suite qualifies terminal mode handling.
The framebuffer check renders pixels without creating an output file. The web
executable checks framed transport and acknowledgments; it does not replace a real
browser run. See [installed and browser evidence](gui-audit.md#executed-verification).

```sh
./build/gui/gui/foundation-gui-terminal --smoke-test
./build/gui/gui/foundation-gui-framebuffer --self-check
./build/gui/gui/foundation-gui-web --smoke-test
```

| Host | CMake selection | Executable/output | Required inputs |
| --- | --- | --- | --- |
| Terminal | `FOUNDATION_BUILD_GUI=ON` | `foundation-gui-terminal` | Interactive POSIX terminal or Windows console |
| Framebuffer image | Same | `foundation-gui-framebuffer OUTPUT.ppm` | No window system |
| FLTK | `FOUNDATION_GUI_FLTK=ON` | `foundation-gui-fltk` | FLTK development headers/libraries, native display |
| SDL window over framebuffer | `FOUNDATION_GUI_SDL=ON` | `foundation-gui-sdl` | SDL2 development package and video driver |
| Rev | `FOUNDATION_GUI_REV=ON` | `foundation-gui-rev` | Module compiler/scanner, OpenGL, Linux/X11 or Windows SDK |
| Hosted browser | `FOUNDATION_GUI_WEB=ON` (default) | `foundation-gui-web`, `web/serve.py` | Python 3.9+, current browser |
| Browser Wasm | Emscripten toolchain | target `foundation-gui-web-wasm`; `gui_web_wasm.js/.wasm` | Prepared Emscripten SDK, Node for tests, current browser |

With a multi-configuration generator, add `--config Debug` to builds and
`-C Debug` to CTest; use the configuration subdirectory for executable paths.
GUI test executables are excluded from ordinary product builds; build
`foundation-gui-tests` when selecting the GUI test label. Explicit toolkit options fail configuration if dependencies are missing. Missing
Node omits renderer/Wasm tests and is not a passing result. Set
`FOUNDATION_GUI_HOST_TESTS=ON` to include private PTY (POSIX), loopback and selected
native-display checks. Run SDL/FLTK/Rev tests with a real display
or an explicitly prepared X server. An absent test in `ctest -N` is missing coverage.

## Prepared platform dependencies

On Debian 12 Bookworm, the basic terminal/framebuffer/hosted-browser/FLTK/SDL
profile can use distribution packages:

```sh
sudo apt-get install build-essential cmake ninja-build python3 nodejs \
  libfltk1.3-dev libsdl2-dev xvfb xauth
```

This is a human preparation example, never a configure-time package installation.
Record the repository snapshot, package versions and dependency closure for a
reproducible SDK. Bookworm's base CMake/compiler do **not** satisfy the Rev module
profile: prepare CMake 3.28+ and Clang 19+ with matching `clang-scan-deps`, GCC 15+,
or a supported MSVC toolset. GCC 14 is rejected for this pinned toolkit. Linux Rev
also requires `libgl1-mesa-dev libx11-dev libxrandr-dev libxext-dev libglew-dev
libfreetype6-dev`; use a reviewed prepared toolchain with the chosen target
[sysroot](sdk.md), rather than silently increasing the binary OS baseline.

```sh
cmake -S . -B build/gui-native -G Ninja -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_CXX_COMPILER=clang++-19 \
  -DFOUNDATION_BUILD_GUI=ON -DFOUNDATION_GUI_SOURCE=/path/to/gui-boundary \
  -DFOUNDATION_GUI_FLTK=ON -DFOUNDATION_GUI_SDL=ON -DFOUNDATION_GUI_REV=ON \
  -DFOUNDATION_GUI_HOST_TESTS=ON
cmake --build build/gui-native --target foundation-gui-tests --parallel 2
xvfb-run -a ctest --test-dir build/gui-native -L gui --output-on-failure --parallel 2
```

Rev embeds preserved resources. `GUI_REV_BUNDLED_DEPS=ON` builds the pinned local
GLEW/FreeType archives through the upstream recipe (default on Windows); its
optional library discovery is disabled. The platform SDK still supplies OpenGL
and system window libraries. Source manifests verify the complete preserved Rev
and dependency inventories, including added/removed files. Toolkit C++23/module
settings stay on toolkit targets; core and public GUI code remain C++20.

On Windows, prepare Visual Studio 2022 17.6+ C++ desktop tools and the Windows SDK,
CMake 3.28+, Ninja when using that generator, Python, and optional Node. Supply
reviewed FLTK/SDL2 packages for the exact x64 or ARM64 toolchain through
`CMAKE_PREFIX_PATH`. Use matching architecture/runtime settings throughout;
`GUI_REV_BUNDLED_DEPS=ON` avoids mixing arbitrary GLEW/FreeType binaries. A Linux
build or Xvfb check does not qualify Windows or ARM64. Rev currently targets
Linux/X11 and Windows/OpenGL; macOS is not a supported Rev integration profile.

Wasm uses a separately prepared SDK, not the host's native sysroot:

```sh
emcmake cmake -S . -B build/gui-wasm -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DFOUNDATION_BUILD_GUI=ON
cmake --build build/gui-wasm --target foundation-gui-tests --parallel 2
ctest --test-dir build/gui-wasm -L gui --output-on-failure
python3 -B build/gui-wasm/gui/web/serve.py --wasm-dir build/gui-wasm/gui
```

Native hosts are not built in the Wasm configuration. The generated JavaScript
and module filenames match the shared browser loader. Both transport modes use
identical verified `renderer.mjs`, styles and document shell. Preserve SDK version,
compiler, linker, runtime and cache artifacts; SDK preparation may require network
access, ordinary builds must not. See [portability](portability.md) and
[release requirements](releases.md) for target qualification and packaging.

## Reusable host contract

[The typed contract](../gui/host/contract.hpp) requires construction with an adapter,
event handling, presentation retry and queued service request/completion. Native
sessions centralize service pumping and shutdown. [The browser runtime](../gui/host/browser.hpp)
is shared by the native bridge and Wasm composition roots. Hosts own platform
polling, surfaces, transport and resources; shared code owns all feature decisions.

Pinned terminal and SDL mechanics become typed runners through
[reviewed exact patches](../gui/patches/README.md). SDL test observers inject input
and inspect results; production uses a no-op observer. FLTK/Rev loops remain small
composition roots. No `Example` alias or replacement of an application include
is used. Native adapters and browser assets remain the pinned implementations, with the
reviewed generic FLTK appearance/focus patch applied in the build directory.
The loopback transport uses one bounded worker per child, including bounded input,
output and deadlines, and terminates/reaps it during failure or release. It works
without POSIX-only pipe readiness operations.

The lock checks every consumed header, asset, test and build recipe even for a
source archive without Git metadata. Changed input triggers configure and fails
verification. Refresh the pin, hashes and patches only after reviewing an upgrade
and executing the affected host/conformance checks. The pinned project-owned code
is dedicated under CC0-1.0; third-party code and generated font data retain their
separate terms. The reviewed Rev permission covers this repository's source releases
and compiled application binaries. The [distribution gate](gui-audit.md#distribution-gate)
records the exact scope and required notices. Downstream projects must establish
their own supplier permissions; this approval is not a general Rev license grant.

## Adding a feature

1. Change the core library for new product meaning or validation.
2. Add control declarations to `gui/shared/view_definition.hpp`; update shared
   state bindings and action handling in `gui/shared/application.cpp`. Construction
   and vertical layout consume that same ordered definition.
3. Add a shared behavior/geometry scenario, including rejected and stale input.
4. Exercise that scenario through public events and actual selected host input.
5. Run the focused GUI tests; run broad upstream/native suites when changing the
   boundary, shared input/lifecycle rules, toolkit versions or release profile.

The remove-selected extension adds a real button after initial publication. Its
meaning and layout exist only in shared code. The fixture runs through terminal,
framebuffer, browser, FLTK, Rev and SDL paths without backend feature branches.
Canonical serialization compares declarations, logical geometry, actions and
values. The native visual fixture also compares real framebuffer, FLTK and Rev
captures at normal and compact viewport sizes. It checks borders, shared fills,
visible text and bounded text placement, and proves rejection of erased labels,
wrong disabled colors and shifted controls. Native glyph rasterization and terminal cell rounding are intentionally
qualified separately from declaration equality.

Native screen captures require a display work area large enough for the decorated
window. As the [native fixture](../gui/tests/fltk_test.cpp) demonstrates, exercise
an initially off-screen position, then position and redraw the window and verify
that its entire client viewport is inside the available area before reading pixels.
An undersized display is a failed prerequisite. Off-screen black regions are
invalid capture data and do not establish a rendering difference. Preserve the
original captures, geometry diagnostics and existing comparison bounds; record the
qualified host scope in [validation](validation.md).

The pixel comparator requires one physical pixel per logical layout unit. Its
capture subprocesses select the retained Linux Rev toolkit's `REV_SCALE=1` input;
this does not change application startup or the parent environment. The separate
[Rev native fixture](../gui/tests/rev_test.cpp) verifies the host's actual scale,
physical capture dimensions and unchanged logical widget rectangles, including
non-unit-scale qualification. Captures are never cropped or resampled to pass a
comparison. Record both scales and dimensions when changing display prerequisites.

Portable SDL builds require the supplier's `SDL2::SDL2-static` target, including
its exported link dependencies. Hosts and native tests consume the same interface;
an unavailable static target fails configuration. Ordinary local builds retain the
supplier's shared target selection. Native host qualification explicitly selects
X11 on Linux and the Windows video driver on Windows, sharing the display lock
with other native fixtures. Supply the real display service (Xvfb is supported on
Linux); an unavailable display is a failed prerequisite. Neither SDK consumers
nor installed smoke checks assume that optional dummy/offscreen drivers exist.
The browser build does not enter these native checks.

New rendering primitives, input models or OS services can require a public
contract extension. Specify semantics and fallback once, implement each selected
adapter and add conformance fixtures before exposing the capability in product
code. Never route a new feature by toolkit name in shared application code.
