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
checks the locked, reviewed supplier permissions. `package` requires a
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

The wrapper budgets compilation and testing independently:

```sh
./build.sh test dev --build-jobs 4 --test-jobs 2 --label fast
```

For compilation, `--build-jobs` takes precedence over `--jobs`, then
`CMAKE_BUILD_PARALLEL_LEVEL`, then the resource detector. For tests,
`--test-jobs` takes precedence over `--jobs`, then `CTEST_PARALLEL_LEVEL`, then
an independent default of two. Every explicit limit must be positive. These
scheduling choices do not change the compiled configuration or require a new
build directory.

The detector combines available processors, Linux CPU affinity and container
quotas, and available host/container memory. It reserves one processor when
possible, reserves at least 256 MiB or ten percent of available memory, and
budgets 768 MiB per compile job. Unknown memory limits cap automatic compilation
at two; failed detection falls back to one. These are conservative estimates,
not a guarantee: large links, instrumented builds and simultaneous sessions can
need lower explicit limits. Measure and adjust for the actual machine.

CMake automatically uses an available `ccache` with Ninja or Makefiles when no
compiler launcher is already selected. It never installs or downloads the
cache tool. Set `-DFOUNDATION_COMPILER_CACHE=OFF` for a new direct-CMake tree to
disable automatic selection, or provide an explicit supported CMake compiler
launcher. Never enable cache settings that weaken dependency checking. A cache
miss must produce the same correct build as a cache hit. Keep cache storage
outside tracked source.

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

## Rootless native development dependencies

[`prepare_dependencies.py`](../tools/prepare_dependencies.py) can create a
native Linux development prefix from retained Debian archives without package
installation or administrator access. This is an optional local development
route. It does not replace an isolated release SDK or lower the host runtime
floor. Select exact package versions and architecture, retain the archives, and
review their source package provenance before preparation.

An input JSON file records every package's `package`, `source_package`, `version`,
`architecture` (`all` or the selected host architecture), local `.deb` filename,
`sha256` and upstream `url`. The top-level fields are `schema_version: 1`,
`architecture` in Debian vocabulary, `packages` and `runtime_libraries`.
Each runtime entry has `package`, `development`, `soname` and `link`: it connects
one extracted development linker alias to an installed architecture-qualified
runtime package with exactly the same version. Its physical file digest is
frozen and rechecked. Use an empty list when no host runtime aliases are needed.

```json
{
  "schema_version": 1,
  "architecture": "amd64",
  "packages": [{
    "package": "example-dev", "source_package": "example",
    "version": "1.0-1", "architecture": "amd64",
    "file": "example-dev_1.0-1_amd64.deb",
    "sha256": "REPLACE_WITH_THE_REVIEWED_ARCHIVE_SHA256",
    "url": "https://deb.debian.org/debian/pool/main/e/example/example-dev_1.0-1_amd64.deb"
  }],
  "runtime_libraries": [{
    "package": "example-runtime", "development": "example-dev",
    "soname": "libexample.so.1",
    "link": "usr/lib/x86_64-linux-gnu/libexample.so"
  }]
}
```

This illustrates the schema, not a downloadable package selection. Replace the
example with reviewed existing packages and exact archive digests.

```sh
python3 tools/prepare_dependencies.py prepare --manifest /owned/inputs.json   --packages /owned/retained-debs --output /owned/development-prefix
python3 tools/prepare_dependencies.py verify /owned/development-prefix
./build.sh build dev --dependency-prefix /owned/development-prefix   --build-dir /owned/native-build --build-jobs 2
```

Preparation is offline by default. A separate explicit `--download` operation
may fetch missing declared archives from Debian's approved HTTPS origin and
checks their digests before retaining them. Ordinary configure/build/test never
fetches. Preparation rejects path traversal, conflicting files, special entries
and escaping aliases; include all required archive closure, including shared
documentation needed by relative aliases. It retains the input manifest and
`.deb` files with a complete prepared-tree inventory.

The wrapper verifies the tree before and after use. Direct CMake supports
`-DFOUNDATION_DEPENDENCY_PREFIX=/owned/development-prefix`; it verifies before
discovery and again before compilation and installation. A changed prefix
selection requires a fresh build tree. Target SDKs and restored Windows
dependency groups cannot be combined with this native-only prefix. Development
inputs and host runtime upgrades must be deliberately re-prepared and rechecked.

## Installed dependency notices

Installation and packaging collect dependency terms into
`share/doc/Foundation/dependency-notices`, including a JSON inventory of notice
bytes and exact input providers. The SDK route copies every declared legal-info
file from the verified retained tree. The Windows dependency route checks each
selected port's exported copyright and includes transitive exported notices.
Native portable builds identify the selected static C++/compiler archives through
the compiler and resolve their exact distro ownership. Staged private runtime
libraries are resolved to their original providers and included too. Copyright
references to `/usr/share/common-licenses/NAME` require the corresponding complete
text. An SDK cannot satisfy a missing target notice using the host's license tree.

Bundled source dependencies register a verified notice with
`foundation_notice_file(absolute_path)`; its configure-time digest is rechecked
when installed. Native libraries without local distro ownership need a reviewed
`FOUNDATION_NOTICE_MANIFEST` passed to direct CMake. Its schema is
`{"schema_version":1,"components":[{"name":"example","inputs":["EXACT_LIBRARY_SHA256"],"notices":{"LICENSE":"EXACT_NOTICE_SHA256"}}]}`.
Notice paths are relative to that manifest and must remain inside its directory.
Every explicit component maps exact library bytes to exact complete notice files.
This also applies to static archives extracted into a rootless native prefix.

Missing, changed or ambiguous notice inputs fail packaging. Repeat installation
accepts only an identical existing notice directory; use a fresh owned prefix
for changed dependencies. Copying notices is a mechanical completeness check,
not a grant of redistribution permission. Review dependency terms and preserve
all existing publication gates, including the GUI supplier permission scope.

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

### Dependency policy in new CMake directories

Every target-bearing `CMakeLists.txt` below the root calls
`foundation_register_build_directory()` before defining targets or finding
packages. The root registers automatically. The policy captures imported target
paths, generator expressions and notices while their declaring directory is still
in scope; local imports can have the same name in separate directories. Final
configuration rejects an unregistered target directory. SDK containment runs before
compilation and installation, and imported-library bytes are checked again against
the configured identity. Do not make imports global or skip an inaccessible target
to work around this requirement.
