# GUI ownership and integration

Application features have one implementation. Shared code owns state, commands,
labels, availability, rows, menus, layout and service intent. Adapters interpret
public declarations and return public input. A renderer understands a button;
it never understands a product command or privately recreates application layout.

This repository consumes [gui-boundary](https://github.com/mirage335-colossus/gui-boundary)
at the revision and SHA-256 inventory in [the lock](../third_party/gui-boundary.lock.json).
All seven provided host paths are integrated. The [audit](gui-audit.md) distinguishes
implemented paths, executed checks and remaining platform qualification work.
There is no second widget vocabulary or maintained renderer implementation here.

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
GUI library compiles, even with `BUILD_TESTING=OFF`; unchanged inputs reuse its stamp. [Shared application code](../gui/shared/application.cpp)
uses `foundation::Store`, the same core library as the CLI. The core owns record
validation, capacity, identities and mutation. Shared GUI code projects records
and owns editor state, error recovery, enabled actions, count, menu, heading prompt
and responsive layout. Its [header](../gui/shared/application.hpp) exposes only
`gui::Adapter`. No native object crosses into application code.

The shared library is linked into every selected executable. One native build
graph builds all selected native hosts and their tests; Emscripten uses a separate
toolchain build directory because its output is a different target platform.
Source changes and tests still use the same library and CMake definitions.

## Build and run

Acquire the locked revision as a preparation step. Configure/build never download
source, libraries, toolchains, fonts or browser modules.

```sh
git clone https://github.com/mirage335-colossus/gui-boundary.git /path/to/gui-boundary
git -C /path/to/gui-boundary checkout --detach bff416308f87dd0c1a7cc5b55476d757c971e879
cmake -S . -B build/gui -G Ninja -DCMAKE_BUILD_TYPE=Debug \
  -DFOUNDATION_BUILD_GUI=ON -DFOUNDATION_GUI_SOURCE=/path/to/gui-boundary
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
`FOUNDATION_GUI_HOST_TESTS=ON` to include private PTY (POSIX), loopback, SDL dummy
video and selected native-display checks. Run FLTK/Rev tests with a real display
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
  -DFOUNDATION_BUILD_GUI=ON -DFOUNDATION_GUI_SOURCE=/path/to/gui-boundary
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
is used. Native adapters and browser assets remain the pinned implementations.
The loopback transport uses one bounded worker per child, including bounded input,
output and deadlines, and terminates/reaps it during failure or release. It works
without POSIX-only pipe readiness operations.

The lock checks every consumed header, asset, test and build recipe even for a
source archive without Git metadata. Changed input triggers configure and fails
verification. Refresh the pin, hashes and patches only after reviewing an upgrade
and executing the affected host/conformance checks. Upstream has no declared
top-level license at this revision: local development is wired, GUI binary packaging
remains blocked until the owner supplies reviewed licensing terms. Separate font
or toolkit notices do not resolve that missing declaration.

## Adding a feature

1. Change the core library for new product meaning or validation.
2. Add shared declarations, stable keys, state bindings, action handling and layout.
3. Add a shared behavior/geometry scenario, including rejected and stale input.
4. Exercise that scenario through public events and actual selected host input.
5. Run the focused GUI tests; run broad upstream/native suites when changing the
   boundary, shared input/lifecycle rules, toolkit versions or release profile.

The remove-selected extension adds a real button after initial publication. Its
meaning and layout exist only in shared code. The fixture runs through terminal,
framebuffer, browser, FLTK, Rev and SDL paths without backend feature branches.
Canonical serialization compares declarations, logical geometry, actions and
values. Native glyph rasterization and terminal cell rounding are intentionally
qualified separately from declaration equality.

New rendering primitives, input models or OS services can require a public
contract extension. Specify semantics and fallback once, implement each selected
adapter and add conformance fixtures before exposing the capability in product
code. Never route a new feature by toolkit name in shared application code.
