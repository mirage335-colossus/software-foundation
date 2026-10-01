# Building and installing

The maintained entry point is `build.sh`, a small shell launcher for
`tools/build.py`. CMake owns the dependency graph, compilation, installation,
and packaging. The wrapper provides predictable defaults and validation; it
must not become an independent build system. Read [testing](testing.md) for
test selection and [portability](portability.md) before promising that a
package runs on another computer.

## Prerequisites and working commands

Install Git, CMake 3.24 or newer, Ninja, Python 3.9 or newer, and a compiler with
the C++20 features used by this repository. Python runs developer helpers; the
installed CLI does not require Python. The default application has no
third-party application runtime dependencies. Compiler and operating-system
runtimes still apply. GUI integration is optional and has separate prerequisites.

```sh
./build.sh build dev --jobs 2
./build.sh test dev --label core --jobs 2
./build.sh test dev --full --jobs 2
./build.sh test asan --jobs 2
./build.sh package release --jobs 2
```

On Windows, start a terminal with the intended compiler environment initialized
and invoke the same helper directly:

```powershell
python tools/build.py build dev --jobs 2
python tools/build.py test dev --full --jobs 2
python tools/build.py package release --jobs 2
```

The sanitizer preset requires a supported compiler/runtime combination; do not
interpret rejection of an unsupported compiler as successful sanitizer coverage.
Use `python tools/build.py --help` for the current wrapper options. Paths and
arguments must be passed as arguments, never evaluated as shell text.

| Preset | Output directory | Purpose |
| --- | --- | --- |
| `dev` | `build/dev/` | Incremental native development and tests |
| `release` | `build/release/` | Optimized application and package candidate |
| `asan` | `build/asan/` | Instrumented development and regression tests |
| A preset with `--sdk PATH` | `build/PRESET-sdk/` | Explicit prepared SDK selection |

An explicit `--gui-source /absolute/path/to/pinned-checkout` adds the optional
GUI integration and a `-gui` directory suffix. Follow
[the GUI guide](gui-boundary.md) for extra native-host options. GUI distribution
is guarded by unresolved upstream package licensing. `package` requires a
Release configuration and all selected dependencies and notices.

`test` builds prerequisites before invoking CTest. Its default runs the complete
enabled local test suite. `--label fast`, `core`, `tools`, `integration`, or
`gui` selects a focused scope. A label that selects nothing must fail. An
optional feature's tests exist only when the feature is configured.

Direct CMake remains supported:

```sh
cmake --preset dev
cmake --build --preset dev --target foundation-tests --parallel 2
ctest --preset dev --output-on-failure --no-tests=error --parallel 2
cmake --install build/dev --prefix "$PWD/build/install"
```

The supplied presets use single-configuration Ninja. For Visual Studio or
Ninja Multi-Config, pass `--config Release` to build/install and `-C Release`
to CTest/CPack. Select one configuration consistently. Passing `-C Release`
to CPack cannot turn a single-configuration Debug tree into an optimized build;
configure and compile a Release tree first.

The installed CMake package exports `foundation::core`. A separate consumer
must use `find_package(Foundation CONFIG REQUIRED)` and link that target;
consumers must not copy internal include directories or compiler flags. The
integration checks exercise this installation boundary.

## One graph and deliberate configurations

Keep library sources in one reusable target. Link the CLI, tests, and optional
GUI to it. Compile shared GUI behavior once per compatible configuration and
reuse it across adapters. Do not maintain a separate hand-written source list
for every executable, test, and package. Target-scoped include directories,
compile features, definitions, and link requirements carry the contract.

A single build means one authoritative graph and entry point. Separate output
trees remain necessary for incompatible compilers, target architectures,
standard libraries, sanitizer settings, SDK identities, and generators. Never
change a configured tree from one such identity to another. A cached compiler
choice can survive changes to `CC` or `CXX`; a successful reconfiguration alone
does not prove the requested compiler took effect.

Use a fresh, explicitly named build directory through direct CMake when
experimenting with another toolchain. Keep generated files in `build/`. Do not
delete unrelated build trees to fix one stale cache. Record the affected tree,
preserve needed logs, and remove only the owned disposable output.

Configure-time build information should record source revision and dirty state,
compiler path/version, generator, target, build type, feature selection, and SDK
recipe identity. A release build must use clean, identified source. Dirty
development evidence needs a diff identity or file digests as well as a commit.
This provenance is not proof that rebuilding produces identical bytes.

## Faster iteration without changing behavior

Use incremental builds and the smallest affected target or test label while
editing. Change a public header only when the public contract changes: unnecessary
header dependencies expand recompilation. Disable unused upstream examples and
tools. Generate `compile_commands.json` for accurate editor and analysis input.

Treat compilation and testing as separate resource budgets. Start conservatively
with `--jobs 2`; increase after measuring available CPU and memory. Large link
steps and instrumented builds can use much more memory than ordinary compilation.
Concurrent agents share the same machine's limits. If separate compile/test
limits are needed, use direct `cmake --build --parallel N` and
`ctest --parallel M`, or the separate environment controls below.

The wrapper also honors `CMAKE_BUILD_PARALLEL_LEVEL` for compilation and
`CTEST_PARALLEL_LEVEL` for tests when `--jobs` is absent. An explicit `--jobs N`
sets both. Its automatic compile limit is conservative and capped; it is not
a measurement of free memory or a guarantee against oversubscription.

Compiler caches are optional performance aids. Configure a supported CMake
compiler launcher explicitly, preserve compiler identity in cache keys, and
never enable settings that weaken dependency checking. A cache miss must produce
the same correct build as a cache hit. Keep caches outside tracked source.

Measure clean and incremental builds, a representative source edit, a public
header edit, and test startup independently. Report compiler, configuration,
available memory, concurrency, and cache status with timings. Adopt precompiled
headers, unity compilation, or link-time optimization only when measurements
justify their complexity and independent builds still pass.

## Offline and portable operation

Configuration and ordinary builds must not download dependencies, install
packages, modify a prepared SDK, or require administrator access. Preparation
is an explicit operation with documented inputs and checksum verification.
Missing inputs produce an actionable error. See [dependencies](dependencies.md)
and [SDKs](sdk.md).

Build a copied checkout and an installed consumer from paths containing spaces.
Avoid hard-coded home directories, `/tmp` include aliases, absolute development
RPATHs, and implicit access to a sibling checkout. A dependency with stricter
path restrictions must reject them at its own preparation boundary and document
that limit; do not impose the restriction on the whole application unnecessarily.

All source and build-tree writes follow [agent coordination](agent-coordination.md).
Claim the output tree for configure, build, test, package, and cleanup together.
Do not run a build against files another session may still modify; use a stable
snapshot or an agreed integration checkpoint.

## Before changing the build

Check command-line diagnostics, path handling, compiler/SDK changes, offline
behavior, a clean build, an incremental build, installation, and an independent
consumer as relevant. Document new options, dependencies, output paths, and
compatibility effects together with the implementation. Do not raise the stated
minimum CMake, Python, or compiler requirement accidentally by adopting a newer
API without a guard.

The preset format and toolchain behavior are defined in the
[CMake 3.24 documentation](https://cmake.org/cmake/help/v3.24/manual/cmake-presets.7.html)
and [toolchain manual](https://cmake.org/cmake/help/v3.24/manual/cmake-toolchains.7.html).

## Explicit output, portability and host-check controls

Use `--build-dir /owned/build-tree` for an independently claimed session tree.
The wrapper still binds it to the exact compiler, SDK, feature choices and
configuration; a different identity requires a fresh tree. Do not share one
build directory between simultaneous writers.

`--portable` selects generic CPU code and the chosen static C++/compiler-runtime
policy. It cannot lower libc requirements by itself. Linux release candidates
must use the qualified glibc 2.36 sysroot, then pass `verify_abi.py` against every
ELF file. A modern native compiler on a newer distro remains a development
configuration until that inspection and oldest-host execution pass.

`--gui-backends` explicitly selects optional backends from the wrapper's checked
inventory. `--host-tests` enables real GUI host execution and requires GUI input;
run it only where the corresponding display/browser prerequisites are available.
`--distribution-tests` enables additional packaging/tool checks. These controls
reduce development work without claiming omitted coverage as successful.

```sh
./build.sh test dev --build-dir /owned/session-build --label core --jobs 2
./build.sh test release --build-dir /owned/release-build --sdk /owned/sdk --portable --full --jobs 2
./build.sh package release --build-dir /owned/release-build --sdk /owned/sdk --portable --jobs 2
```

Native Windows dependency groups are separate from compiler/sysroot SDKs. Use
`--dependency-group PATH` to bind an exact verified group; its recipe is read
from the complete group's checksum filename. After restoring it with
`sdk_windows.py install`, add `--windows-dependencies RESTORED_PATH` to consume
its checked CMake prefix. Initialize the separately installed Microsoft toolchain
first. The package build
record identifies the dependency recipe for mandatory release retention. See the
[Windows base contract](sdk.md#windows-dependency-base-and-separately-installed-host-tools).
