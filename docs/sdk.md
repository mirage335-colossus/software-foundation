# Prepared SDKs and target sysroots

An SDK is a versioned developer input: host tools plus a controlled target
environment. Its host requirements describe where the tools run. Its target
requirements describe where the generated application runs. Keep these
contracts separate in metadata, documentation, and tests.

The default example builds with native tools. This repository also implements
pinned native source SDK preparation, WebAssembly build SDK preparation, Windows
dependency bases, immutable local base storage, strict installation and complete
release recovery. These are executable maintenance facilities. Compiled SDK
archives are generated outputs, not committed inputs. A runnable producer does
not establish that every host or target is qualified; record actual cold-build
and oldest-runtime results separately.

## SDK versus installed developer package

The installed `Foundation` CMake package contains the application library,
headers, and exported usage requirements. It is consumed with an existing
compiler. A target SDK additionally supplies or identifies compilers, binary
utilities, target headers/libraries, build-tool prerequisites, licenses, and
its compatibility baseline. Neither is an application runtime prerequisite.

```sh
./build.sh build dev --sdk /absolute/path/to/prepared-sdk --jobs 2
./build.sh test dev --sdk /absolute/path/to/prepared-sdk --jobs 2
./build.sh package release --sdk /absolute/path/to/prepared-sdk --jobs 2
```

These commands require a valid prepared SDK matching the toolchain file's
metadata contract. A foreign target requires a suitable test executor or native
test machine; do not run its executables on the build host by assumption.
The current consumer implementation and required fields are in
[`cmake/toolchains/sdk.cmake`](../cmake/toolchains/sdk.cmake).

The current manifest is `SDK_ROOT/sdk.json` with `schema_version: 1`, a nonempty
`recipe_id` containing a complete SHA-256, and a `target` object containing
`system: "Linux"` or `"Emscripten"`, `processor`,
`triple`, `sysroot`, and `cxx_compiler`. The last two are existing relative paths
whose resolved locations stay inside the SDK. The `files` object maps every
SDK file other than the root manifest to its SHA-256; the compiler must be
included. Native producer manifests also declare `target.c_compiler`, naming the
retained `<triple>-gcc` executable. The validator checks its containment and full
file inventory; CMake selects it again in nested compilation checks. Legacy
native manifests without this field support C++-only consumers; enabling C fails
instead of selecting a host compiler. Emscripten's retained rules explicitly select
its C and C++ wrappers. The wrapper verifies completeness and every digest before configuration
and retains the manifest digest in the build-tree identity.

Production manifests also carry host requirements, target runtime ceilings,
licenses, complete source-inventory identity, preparation kind, relocation policy
and separate host/target audit results. `sdk_verify.py --release` rejects missing
production evidence. Windows dependency bases deliberately name an external
Microsoft toolchain; they never claim to contain the compiler.

Review the supplier's complete installed shared-library inventory, including
optional facilities enabled by default and development aliases. Preserve static
linking inputs and developer debugging support. Source-proven private libc or
loader imports are accepted only in the exact declared SDK libc inventory, with
the matched provider, source/recipe identities, approved library locations,
byte-identical development aliases and runtime version checks. Arbitrary files
with private ABI requirements remain rejected, and application packages cannot
inherit this SDK allowance or bundle the target libc/loader.

## Linux SDK filenames and destination filesystems

Native Linux producers explicitly declare `path_policy: "linux-case-sensitive-v1"`
in the binary `sdk.json`. This policy requires both `host.system` and
`target.system` to be `Linux`. Linux target headers can contain distinct names
such as `xt_CONNMARK.h` and `xt_connmark.h`; both are required inputs. Preserve
both names and their complete bytes. Never omit or rename a header to accommodate
a filesystem or archive validator.

An absent `path_policy` retains the strict portable default. Unknown values,
non-Linux host/target combinations, and Windows dependency bases cannot select
the Linux policy. Source inventories, source archives, release asset names,
Windows and WebAssembly SDKs, and ordinary archive operations retain portable
case-insensitive collision checks. These checks include implicit directories,
file-versus-directory conflicts, and excluded manifest entries. Retained supplier
source archives are ordinary byte blobs inside the portable source group; they
are not unpacked there.

The binary SDK verifier reads one bounded, exact root `sdk.json` before applying
the declared policy to every archive member and complete file hash. Metadata
ordering does not affect policy selection. Exact duplicate names, traversal,
links, special entries, privileged modes and files used as directories remain
invalid under both policies. Inspection of a retained binary group is read-only
and may run on any supported host; installing or exporting a Linux-policy tree
requires Linux and a filesystem that preserves distinct names.

Before copying supplier files or extracting an SDK, the implementation checks
each newly created destination directory with two exclusive case-distinct files.
It validates independent identities and bytes, then removes only verified owned
probe files. Payload copies also use exclusive creation. A filesystem that folds
these names is rejected before it can discard compiler inputs. If a probe entry
changes or cleanup becomes uncertain, the owned staging tree is preserved and
the reported path must be inspected before retrying; a failed attempt never
qualifies an installation. Do not relocate an SDK onto an unsupported mount.

Verification remains read-only: it checks current case lookup in every populated
directory and compares the complete exact-name inventory. Installation, binary
export and post-relocation resealing all use the same validated policy. A moved
SDK with recorded absolute locations must be reinstalled from its retained group;
changing a manifest field does not perform relocation. Paired-header regression
checks preserve both digests across deterministic export, byte-identical group
copy, installation, relocation and actual consumer compilation.

The policy and its helpers are producer recipe inputs. Introducing or changing
them creates new recipe identities for every recipe that retains those helpers;
old archives are never relabeled or treated as byte-equivalent. Filesystem fixture
success is separate from complete cold SDK preparation and target qualification.

## Recipe and archive identity

Track the recipe, not a large generated SDK tree. The recipe must identify every
direct and transitive source, bootstrap input, exact revision, source archive
digest, patch, configuration, and relevant build helper. Include host tools in
the inventory, including generators required only while preparing dependencies.
Content-address the recipe from normalized paths and complete input bytes.

Cross-host recipe identity requires identical checkout bytes, including line
endings. The project [attributes](../.gitattributes) pin owned text inputs,
including PowerShell helpers, to LF. Verify effective attributes and actual bytes
in existing worktrees before computing an identity or reusing a retained group;
a changed attribute does not rewrite an already checked-out file. Preserve exact
supplier bytes and retained source archives. Never normalize during hashing or
treat different recipe IDs as equivalent because only line endings differ.

Keep mutable build outcomes and qualification status in separate receipts bound
to the recipe and archive digests. They are not recipe inputs: recording a
successful cold build must not change the identity of the exact group it verified.

A recipe identifier is not an archive digest. Two cold builds of one recipe may
produce different bytes until reproducibility is demonstrated. Preserve the
actual archive SHA-256 alongside the recipe identifier. Never silently replace
different bytes published under an existing immutable recipe asset name.

Publish a matched group:

1. Compiled SDK archive for its host and target pair.
2. Complete source archive with recipe, helpers, patches, bootstrap inputs, and
   selected dependency downloads sufficient for an offline rebuild.
3. Checksum inventory for both archives, plus provenance and license inventory.

Keep prepared inputs in durable release storage or a maintained artifact store.
Actions caches and expiring workflow artifacts cannot be their only copy.
Every binary release MUST retain byte-for-byte copies of its exact required
SDK/dependency binary, source and checksum group. A pointer to a base, external
URL, workflow artifact or cache is never a substitute. `release.py assemble`
refuses missing groups, and `release.py recover` works using the release alone.

## Explicit preparation lifecycle

Separate fetch, build, export, install/relocate, verify, and publish operations.
Ordinary application configuration invokes none of them implicitly. Network
access belongs to explicit fetching; offline preparation fails on missing or
changed inputs. Reuse the exact verified prepared recipe during ordinary CI and
releases. A missing recipe requires explicit SDK maintenance.

Fetch into temporary files, verify expected digests, then publish atomically.
Bound retries and timeouts; retry a transient download failure without changing
the pinned source or silently substituting another version. Preserve the first
useful failure and final result. Never bless a downloaded digest as trusted
merely because it matches a checksum downloaded from the same untrusted source.

Validate archive entries before extraction: reject traversal, absolute output
paths, duplicate entries, unexpected special files, escaping links, and writes
through link parents. Install into a new owned staging directory; publish the
finished tree atomically. Preserve an existing valid installation if preparation
fails. Never recursively replace an unmanaged destination.

Relocation must be an explicit, verified operation for SDKs with embedded paths.
Record the installed root or otherwise verify relocatability. After moving an
SDK, rerun its relocation procedure and use a new application build tree.
Reject a changed SDK root or manifest digest in an existing tree.

## Isolate host tools from target dependencies

The toolchain must select its compiler and sysroot before CMake's `project()`
initializes languages. Set target system and processor explicitly. Search
programs in the host environment, while target headers, libraries, and package
metadata are restricted to the target root. Disable user/system CMake package
registries for isolated builds. Propagate required SDK variables into
`try_compile` projects and use toolchain-file-relative paths.

Reject conflicting `CC`, `CXX`, compiler options, and ambient include/library
search overrides. Configure `pkg-config` with the target sysroot and target
metadata directories; clear host metadata paths. Validate both lexical paths
and resolved links so a supposedly contained dependency cannot escape to the
host. A target library must never be taken from a host directory as fallback.
These distinctions follow the
[CMake toolchain model](https://cmake.org/cmake/help/v3.24/manual/cmake-toolchains.7.html).

Keep compile capability probes separate from executable probes. Cross builds
may compile a check that they cannot execute. Either provide a declared test
executor or record runtime checks as unavailable. Do not globally disable linker
checks to make a broken toolchain configure successfully.

## New tools with an older target runtime

Build target libraries against the selected older runtime headers and libraries,
even if the compiler itself is recent. A recent compiler may change default
language dialects, diagnostics, or linker behavior; supply the dependency's
documented dialect and narrowly justified compatibility fixes. Scope those
settings to the affected dependency, retain the patch, and verify its expected
upstream context before applying it.

Do not transplant the entire configuration from an unrelated newer dependency
version. Recheck licenses, source inventory, configure options, and upstream
maintenance status. Keep auxiliary host generators on the versions they require;
an older target library does not imply every host generator must use that same
source snapshot.

Audit SDK host tools as well as target libraries. A target ABI ceiling can pass
while the compiler, build system, or a compiler helper fails to start on the
advertised build host. If private host C++ runtime files are bundled, distinguish
them from target files and verify that each resolves its own dependencies after
relocation. Never classify every file outside the sysroot as a host file without
accounting for target compiler-support libraries stored elsewhere.

Sanitizer use requires matching target runtimes in the SDK. If absent, reject
instrumented SDK builds with an explanation; do not borrow host runtimes.
Test SDK-built developer executables too. They may require runtime staging even
before packaging, and build-tree search paths must not accidentally select a
target C runtime incompatible with the host loader.

## Qualification and maintenance

Qualify the actual installed archive, not the builder's pre-export directory:

- Verify every retained source and archive digest and the recipe identity.
- Run host tools on the oldest declared build host after relocation.
- Compile, link, and execute a representative C++20 consumer on the target.
- Inspect every shipped target binary's architecture and runtime requirements.
- Build the application offline; test its normal and installed forms.
- Build and test every enabled GUI backend and any dynamic loading paths.
- Restore from the source archive into an empty cache with networking disabled.

Record exact commands, observed results, and omitted scope using the
[validation template](templates/validation.md). Maintain separate fast fixture
tests for recipe identity, path containment, interrupted installation, changed
manifests, missing archives, and corruption. These checks can run on every
relevant change without rebuilding a compiler.

An upgrade creates a new recipe identity, archives, and qualification record.
Keep the previous group available for supported releases. Follow the dependency
[upgrade procedure](dependencies.md) and the application
[release procedure](releases.md) for downstream requalification.

## Native source producer and Bookworm bootstrap

[`third_party/sdk/recipe.json`](../third_party/sdk/recipe.json) pins Buildroot,
a maintained glibc 2.36 input and all direct digests. Buildroot pins the selected
transitive source inputs. The recipe selects GCC 15 and a glibc 2.36 target; its
host tools are built on Debian 12 Bookworm. `distro_sdk.py` rejects a different
production builder. Install the recipe's listed bootstrap packages once using
the ordinary Debian package manager. Preparation needs no retired distro mirror.

```sh
python3 tools/distro_sdk.py bootstrap
python3 tools/distro_sdk.py recipe-id
python3 tools/distro_sdk.py fetch --cache /owned/sdk-cache --jobs 2
python3 tools/distro_sdk.py verify-inputs --cache /owned/sdk-cache
python3 tools/distro_sdk.py build --cache /owned/sdk-cache --output /owned/sdk-group --jobs 2
```

`fetch` is the explicit network operation. `build` verifies all retained input
hashes, the retained dependency-resolution digest and complete resolved download
inventory, then disables every Buildroot download command. A missing input fails;
the producer never substitutes a moving upstream version. Use an OS network
restriction when demonstrating disconnected recovery, as disabled application
download commands alone do not establish network isolation.

A development sysroot is not a bootable operating-system image. Assembly omits
virtual runtime directories and the pinned skeleton's mount-table and resolver
aliases (`etc/mtab` and `etc/resolv.conf`). Validate both exact supplier link targets
before removing either; a changed target, redirected parent or unexpected regular
file is a maintenance decision, not permission to discard it. All other unresolved
or escaping aliases still fail materialization. Never resolve a target runtime
service through the build host's filesystem or relax general link validation to
make a supplier skeleton copy succeed.

The supplier's host root has a separate legacy alias, `usr -> .`, created by
Buildroot's `package/skeleton/skeleton.mk`. Native assembly validates that exact
link after compilation and legal-information collection, then omits it before
materialization. A replacement directory/file or any other link target fails with
an explicit `usr` diagnostic. Host tools already live directly under the host
root; the target's real `sysroot/usr` and normal library aliases remain compiler
inputs. This exception does not permit arbitrary ancestor cycles. It is confined
to the native producer and does not change other SDK producers or identities.

The compiler SDK also omits a reviewed, source-bound set of target OS programs
and conversion modules. Host tools, target headers and link libraries,
`fltk-config` and `sdl2-config` remain. New libc source identities require an
explicit inventory review. Omission records name every removed path and preserve
the supplier relocation entries for retained files.

The x86_64 recipe is the default. The native ARM64 recipe is
[`aarch64/recipe.json`](../third_party/sdk/aarch64/recipe.json); pass it with
`--recipe` to every producer command on a Debian 12 ARM64 host. It selects the
same maintained runtime and newer compiler, with a checked generic CPU override.
Its tools run on ARM64, and its outputs target ARM64. Neither recipe silently
executes foreign binaries or claims emulation as native qualification.

The source group includes the recipe, overlay, exact preparation helpers, selected
source downloads, resolution record, input inventory and available project license.
Restore it into a fresh tree and replay using those retained helpers, not a newer
checkout. `export-sources` can preserve the fetched inputs before a cold build:

```sh
python3 tools/distro_sdk.py export-sources --cache /owned/sdk-cache --output /owned/source-inputs
python3 /owned/restored/tools/distro_sdk.py build \
  --recipe /owned/restored/recipe/recipe.json --cache /owned/restored/cache \
  --output /owned/rebuilt-group --jobs 2
```

A cold compiler build is deliberately separate from routine application jobs.
The compiler's C++ language support does not imply a newer target libc. The
narrow libc dialect override is checked against the pinned upstream context.
Host CMake, Ninja, Python and pkg-config are explicitly selected; they cannot
disappear merely because the builder already has suitable tools.

## Immutable base, installation and reuse

A group contains exactly `sdk-<recipe>-binary.tar.gz`,
`sdk-<recipe>-sources.tar.gz` and `sdk-<recipe>-SHA256SUMS`. Both outer hashes and
both complete inner inventories are checked. Their internal recipe identities
and the binary's recorded source-inventory hash must agree. Full recipe IDs
include producing helper bytes; archive hashes identify actual output bytes.

```sh
python3 tools/dependency_store.py put --base /owned/base --group /owned/sdk-group --recipe <recipe>
python3 tools/dependency_store.py fetch --base /owned/base --recipe <recipe> --output /owned/fetched-group
python3 tools/sdk.py install --group /owned/fetched-group --recipe <recipe> --output /owned/installed-sdk
python3 tools/sdk.py verify /owned/installed-sdk --release
python3 tools/sdk.py smoke /owned/installed-sdk --work /owned/compiler-smoke
./build.sh test release --sdk /owned/installed-sdk --portable --full --jobs 2
```

`put` reuses identical bytes and rejects a conflicting immutable recipe. `fetch`
only copies an existing exact group: it cannot build, download or choose a newer
recipe. The local base format can be transported to a durable release store by
an explicitly authorized publisher. These tools never publish remotely.

Generated archives contain ordinary files only, with sorted entries, stable
modes, normalized owner/time metadata and a deterministic gzip header. Supplier
links must resolve inside their tree before materialization. Extraction rejects
links, traversal, duplicate/case-ambiguous entries, privileged modes, parent/file
collisions and excessive size before creating the final destination.

Installation refuses an existing destination. Buildroot relocation runs at the
new final root, records that root and the original archive digest, then rehashes
the installed tree. A moved installation must be reinstalled from the retained
archive. Compiler smoke compiles C++20 code, audits the generated ELF and executes
it in a clean environment. WebAssembly SDK smoke uses its retained Node executor.
Diagnostic fixtures can be installed with `--diagnostic`, but cannot satisfy
release-readiness validation.

## WebAssembly build SDK and separate browser validation

[`third_party/sdk/wasm.json`](../third_party/sdk/wasm.json) pins Emscripten, its
compiler bundle and Node by exact archive digests. This SDK builds WebAssembly
applications. Node runs compiler support code and command-line checks; it is not
a desktop browser and is not an end-user prerequisite for a browser application.
The SDK includes no Chromium, Firefox, browser profile, or browser installer.
Use ordinary distro browsers or separately installed no-cost browsers for GUI
validation, with their versions recorded in that validation environment. Do not
add browsers to a compiler recipe merely to run GUI tests. Preparation consumes retained
inputs, warms the declared C++ library/exception configuration, and verifies a
second compile using a frozen cache. Ordinary compiles fail when a new library
variant is needed; change and prepare the recipe deliberately.

```sh
python3 tools/sdk_wasm.py fetch --inputs /owned/browser-inputs
python3 tools/sdk_wasm.py recipe-id
python3 tools/sdk_wasm.py prepare --inputs /owned/browser-inputs --output /owned/browser-group
python3 tools/dependency_store.py put --base /owned/base --group /owned/browser-group --recipe <recipe>
python3 tools/sdk.py install --group /owned/browser-group --recipe <recipe> --output /owned/browser-sdk
python3 tools/sdk_wasm.py smoke --root /owned/browser-sdk --output /owned/browser-smoke
```

The source group retains the exact upstream source and precompiled compiler/Node
archives used. It supports disconnected replay from those inputs; it does not
claim to rebuild LLVM, Binaryen or Node from their native source. Python 3.10 or
newer remains a host prerequisite for this supplier version. The pinned prepared
launcher change adds Python's `-B` option, because the supplier's `-E` option
ignores environment-only bytecode controls. Original archives, producer code and
the changed entry-point inventory remain available in the group. A JavaScript executor check does not establish
browser layout, resource-loading, worker, accessibility or interaction coverage.
Those require the separate browser execution matrix.

## Windows dependency base and separately installed host tools

[`windows-toolchain.json`](../third_party/sdk/windows-toolchain.json) selects v143,
x64, static CRT and an explicit Windows SDK. `select-windows-toolchain.ps1`
inventories installed components, prefers the supported installed toolset, and
fails instead of silently switching to a newer ABI family. `ci_windows.ps1`
initializes that exact environment and reports its compiler/linker details.
Consumers inspect the selected native Microsoft linker file through the shared
[`windows_toolchain.py`](../tools/windows_toolchain.py) adapter. It checks the
selected toolset path, x64 executable identity, Microsoft version resource and
unchanged file bytes, then enforces the recorded minimum linker version. A help
command exit status is not a version probe. The ordinary Windows tools suite
exercises the actual native resource API before expensive SDK production.

[`windows-base.json`](../third_party/sdk/windows-base.json) pins the upstream
package-manager revision, target triplet, ports, Debug/Release variants, runtime
policy and disabled LTO. The default core needs no external libraries, so its
complete base can be produced without inventing a third-party dependency:

```powershell
./tools/ci_windows.ps1
python tools/sdk_windows.py recipe-id
python tools/sdk_windows.py empty-base --provenance producer.json --output prepared-group
```

`producer.json` contains the exact recipe fields plus `linker_version` and
`windows_sdk` observed from the selected installed tools. The SDK version must
match the pinned policy. Nonempty port recipes also require `tools_version` and
`installation_path` from that selection; the producer checks the actual active
linker before building. Initialize that environment before invoking the producer.

The same executable lifecycle handles empty and nonempty port selections:

```powershell
python tools/sdk_windows.py fetch --provenance producer.json --cache retained-inputs --jobs 2
python tools/sdk_windows.py verify-inputs --cache retained-inputs
python tools/sdk_windows.py build --provenance producer.json --cache retained-inputs --output prepared-group --jobs 2
```

`fetch` is the explicit network operation. For a nonempty recipe it resolves the
full pinned vcpkg commit, retains its Git source archive and bootstrap executable,
and collects the dependency/tool download cache through a complete maintenance
installation. This also reaches downloads requested during configuration or
compilation, including build tools omitted by `--only-downloads`. Its generated
triplet fixes the selected v143 tools, Windows SDK, static CRT/libraries, both
configurations and no LTO. The maintenance installation is discarded; its compiled
outputs are never reused as proof of the independent cold offline build. This
extra work belongs to preparing a new base, and is amortized by reusing that exact
base for ordinary application builds. The empty core recipe fetches no package
manager or external libraries.

`build` verifies every retained input and restores a fresh supplier tree. It
clears remote binary-cache settings and inherited overlays, disables new asset
downloads with `--no-downloads` and `clear;x-block-origin`, then creates a raw
export with transitive libraries and integration files. Required selected-port
notices and installed inventory records are checked before archive assembly.
A source group retains the complete cache, exact recipe, host policy and helpers;
restore with `sdk.py restore-sources` and run its retained `sdk_windows.py build`
using `--recipe-file restored/recipe/windows-base.json --cache restored/cache`.
Microsoft host tools still come from the separately retained installer layout.

A successful `--only-downloads` operation alone does not establish source closure:
some port recipes fetch additional inputs later. The fresh offline build must
pass before publication. A missing late input requires explicit maintenance of
the selected recipe/cache and a new complete qualification attempt; never enable
network fallback in `build`. See the supplier's
[download controls](https://learn.microsoft.com/en-us/vcpkg/commands/install),
[asset caching](https://learn.microsoft.com/en-us/vcpkg/users/assetcaching), and
[raw export contract](https://learn.microsoft.com/en-us/vcpkg/commands/export).

For a separately reviewed export, the lower-level assembly command remains:

```powershell
python tools/sdk_windows.py assemble --export-root prepared-export --source-root retained-inputs --provenance producer.json --output prepared-group
python tools/sdk_windows.py install --group prepared-group --recipe <recipe> --output installed-base --linker-version <actual-linker-version>
python tools/build.py test release --dependency-group prepared-group --windows-dependencies installed-base --portable --full
```

The nonempty export provenance includes complete `files` and `source_files`
digest maps and must agree with the pinned recipe. Archives preserve both code
and corresponding licenses; record the exact exported package-manager checkout,
port recipes and input downloads in the source tree. Consumers must use a linker
at least as recent as the producing linker. Runtime, configuration and LTO rules
are checked rather than inferred from an archive filename.

The shipped example can use the no-cost Community edition where its terms
permit, or Build Tools for qualifying open-source use. No paid IDE feature is
required. Eligibility is governed by Microsoft
[licensing guidance](https://www.microsoft.com/licensing/guidance/Visual-Studio);
availability without a purchase does not grant unrestricted use.

Microsoft compiler and Windows SDK installation media are not dependency-base
contents. Offline setup of a host without them requires a separately retained,
complete Microsoft offline installer layout, with its component configuration,
installer version, checksums and local verification result. Install from that
layout using the supplier
[offline procedure](https://learn.microsoft.com/en-us/visualstudio/install/create-an-offline-installation-of-visual-studio).
Do not retain only an online bootstrap executable. Tool availability and an edition's
license eligibility are separate questions; this repository does not certify
eligibility for every organization. Native Windows execution remains required.

Prepared SDK trees remain immutable during ordinary builds. Tool environments and
WebAssembly compiler wrappers disable Python bytecode writes, WebAssembly library caches
are frozen, and production installation rechecks the complete inventory after
compiler smoke. A successful program run followed by changed SDK files is a
failed installation. Do not repair such a failure by accepting newly generated
files into the old published recipe; prepare and qualify a new immutable group.

## Exclude producer paths during SDK qualification

Maintenance moves any existing `build/sdk-inputs` tree into a fresh private sibling
before SDK installation, compiler smoke, the core package consumer and the GUI
consumer. Both consumers must succeed while the original path is absent. The
orchestrator checks absence and directory identity around each consumer and only
restores the original tree after all checks complete. A fresh `source=base` or
`source=retained` job records initial absence instead; an unexpectedly present
producer tree is isolated by the same procedure. This prevents the consumer from
silently satisfying absolute paths through the original compiler or target files.

`build/sdk-isolation.json` records the exact recipe, group digests, workflow commit,
run and attempt, initial state, checked boundaries and restoration outcome. It is
retained in the SDK proof artifact. Consumer `qualification.json` files include
its SHA-256 and are published only after successful guard exit; the publication
plan follows those receipts. A failed consumer or filesystem operation emits a
failed isolation receipt, when its original parent remains accessible, and preserves
the quarantined tree. A recreated original
path, changed directory identity, link/reparse point or failed restoration stops
qualification without overwriting or deleting either tree. Inspect the receipt,
stop all relevant writers, reconcile both locations, and use a new owned output
for a retry; do not automatically remove a conflicting directory.

This check relies on exclusive ownership of the job workspace and synchronous
consumers; it is not confinement of hostile processes or proof against every
ambient host dependency. Native Linux compiler outputs and supplier trees remain
inside the isolated cache. Windows producer temporary checkouts and WebAssembly
preparation trees have already been removed on producer return; their retained
cache is isolated too. Selected Microsoft tools, operating-system prerequisites
and the separate GUI input group remain intentional external inputs. SDK host
Python supplies the declared build functionality; features needing optional
extensions must probe those extensions explicitly. Mocked fixtures should not
accidentally require optional extensions. Maintenance and actual HTTPS distribution
checks require a host Python with working TLS support. A fresh
runner consuming an exact retained group supplies stronger separation from the
producer host. Changing only this orchestration leaves SDK recipe identities and
archived binary/source bytes unchanged.

## Qualification boundaries for the supplied recipes

The executable tests cover corruption, incomplete inventories, host/target
selection, fresh offline Windows command construction, retained-source replay,
relocation and immutable installation. The two native Buildroot configurations
are checked against their pinned source. Configuration success and mocked
supplier execution do not establish a cold compiler or Windows library build.
Record native Bookworm x86_64/ARM64 cold-build results, actual Windows producer
results and oldest-host execution before claiming those facilities qualified.
The WebAssembly compiler/Node preparation is a separate qualification scope from
the ordinary Chromium/Firefox validation-host matrix. Each release must identify
which exact retained recipe groups and actual execution records it uses.


## Select a complete dependency profile

Keep the small default core build independent of native GUI libraries. A release
that enables all native backends must select the matching GUI profile before
fetching or preparing its dependency group:

| Native host and target | Core recipe | All-native-GUI recipe |
| --- | --- | --- |
| Debian 12 x86_64 | `third_party/sdk/recipe.json` | `third_party/sdk/gui-x86_64/recipe.json` |
| Debian 12 ARM64 | `third_party/sdk/aarch64/recipe.json` | `third_party/sdk/gui-aarch64/recipe.json` |
| Windows x64 | `third_party/sdk/windows-base.json` | `third_party/sdk/windows-gui/windows-base.json` |

Use `--recipe` for each native producer command and `--recipe-file` for each
Windows producer command. Pass the same selected recipe throughout fetch,
verification, build and identity calculation. Every profile has its own immutable
recipe ID. An all-GUI release cannot substitute the smaller core group.

The native GUI profile selects FLTK, SDL2 with X11, X11 development libraries,
and GLVND OpenGL dispatch libraries. Required selections are checked after real
Buildroot configuration; disappearing options fail preparation. Upstream
Buildroot recipes pin their full transitive inputs, and `legal-info` supplies
their notices. FLTK is built as a static toolkit so its C++ objects use the
application's chosen static compiler runtime. The selected Buildroot recipe pins
FLTK 1.3.7 for the compatible 1.3 API baseline. Upstream marks the 1.3 series
end-of-life; see the [supplier release status](https://www.fltk.org/software.php).
Review fixes and the supported distro's maintenance separately, and upgrade the
pinned toolkit through the documented dependency procedure when appropriate.
A newer toolkit is not required merely to build this generic example.
The Windows GUI profile selects `fltk[core]` and `sdl2[core]` with
the common static runtime/toolset policy. Its OpenGL development interface comes
from the pinned Windows SDK. The retained GUI source group already contains the
exact GLEW and FreeType inputs compiled by its adapter; do not compile duplicate
copies into the dependency base.

The native GUI runtime requires an X11 service and a compatible installed OpenGL
vendor driver. GLVND dispatch libraries may select that driver at runtime; it is
an explicit host service, outside the private application library inventory.
Test the exact package on both the oldest declared host and the intended display
hosts. The SDK does not include an X server, desktop browser, or vendor driver.
Prepared manifests record the profile's `capabilities` and `runtime_host_services`;
qualification still requires actual builds and execution of every selected host.

The SDK-only libc audit binds its ordinary files, target architecture, retained
source digest and complete recipe identity to one sysroot. It permits the private
interface only between the declared libc cohort and its matching loader, checks
numeric runtime versions, and rejects changed files, wrong locations or missing
providers. Materialized libc development aliases must have exactly the same
bytes as their retained versioned provider. Application package audits retain
their strict private-interface and
bundled-libc rejection. This distinction is required to inspect a compiler
sysroot without weakening the deployed application's runtime policy.

## Retain complete SDK bytes after a consumer failure

SDK maintenance runs a separate retention check even when production or consumer
qualification fails. It recomputes the recipe for the selected target and profile,
checks the selected origin, and verifies the exact binary/source/checksum triplet,
including both complete inner inventories. Only a successful check permits the
`sdk-group-<target>-<attempt>` workflow artifact to upload. Missing, partial,
unexpected or changed bytes produce no retention success output.

The sibling `sdk-proof-<target>-<attempt>` artifact includes `sdk-retention.json`.
It binds the target, profile, recipe, source commit, run, attempt and every group
file digest. Its `qualification` is always `unqualified`, and
`publication_approved` is false: this receipt establishes reusable bytes, not a
working consumer. Existing consumer failures remain failures. The publisher still
needs successful producer jobs and explicit execution authorization.

For a local retry, select an exact repository, maintenance run, source commit,
target and attempt. Inspect its identity and download its exact named artifacts
into new private directories; do not select the newest similarly named artifact.
The examples below use Windows and a placeholder complete recipe ID. Replace all
uppercase placeholders with the reviewed values before running commands.

```text
gh run view RUN_ID --repo OWNER/REPOSITORY --json headSha,status,conclusion,event,workflowName,url
gh run download RUN_ID --repo OWNER/REPOSITORY --name sdk-group-windows-x86_64-ATTEMPT --dir build/retry/group
gh run download RUN_ID --repo OWNER/REPOSITORY --name sdk-proof-windows-x86_64-ATTEMPT --dir build/retry/proof
python tools/sdk_windows.py recipe-id --recipe-file third_party/sdk/windows-gui/windows-base.json
python tools/dependency_store.py verify --group build/retry/group --recipe RECIPE
```

Use `third_party/sdk/windows-base.json` for the core profile. Confirm the printed
recipe matches the receipt and the selected checkout's recipe, and compare the
verification output's three file digests with the receipt. Find the receipt inside
the downloaded proof artifact; its relative directory depends on which evidence
files were present. A mismatch requires investigation rather than relabelling the
group. A workflow artifact from another repository or source commit is not trusted
merely because its filenames and self-contained checksums match.

On a matching Windows host, select the pinned external compiler in PowerShell,
then install the dependencies into a new location and run a fresh consumer:

```powershell
./tools/ci_windows.ps1 -Output build/retry/windows-toolchain.json
$selected = Get-Content build/retry/windows-toolchain.json -Raw | ConvertFrom-Json
python tools/sdk_windows.py install --group build/retry/group --recipe RECIPE --output build/retry/dependencies --linker-version $selected.LinkerVersion
python tools/build.py test release --windows-dependencies build/retry/dependencies --dependency-group build/retry/group --build-dir build/retry/core-build --portable --full --jobs 2
```

The core check does not qualify GUI capabilities. To rerun the existing complete
GUI consumer, supply the separately retained GUI input group and pinned external
host graphics archive. In the same selected compiler environment:

```text
python -c "import sys; from pathlib import Path; sys.path.insert(0, 'tools'); import ci_plan; ci_plan.prepared_check('windows-x86_64', 'RECIPE', Path('build/retry/group'), Path('build/retry/gui-check'), 2, gui_group=Path('RETAINED_GUI_GROUP'), graphics_archive=Path('RETAINED_GRAPHICS_ARCHIVE'))"
```

That command verifies and relocates the SDK, builds in one tree, probes actual
host graphics, runs the complete GUI checks and removes its temporary driver
files before reporting success. It does not download missing inputs. GUI inputs
and host graphics remain subject to their separate retention and redistribution
rules.

For a matching Linux host, verify the group as above and use the existing SDK
consumer commands:

```text
python tools/sdk.py install --group build/retry/group --recipe RECIPE --output build/retry/sdk
python tools/sdk.py verify build/retry/sdk --release
python tools/build.py test release --sdk build/retry/sdk --build-dir build/retry/native-build --portable --full --jobs 2
```

Choose a new output directory for every attempt and preserve failure evidence.
Native GUI and browser requirements still need their relevant full consumers.
Hosted `source=auto` and `source=base` continue to use qualified base storage;
artifact reuse requires the separate explicit `source=retained` selection.
A retained group or local retry does not itself authorize base publication.

For a hosted retry, select `source=retained`, one exact `target`, its `profile`,
and an explicit `retained_input` JSON object. This is separate from ordinary
base selection; there is no fallback from failed download or validation to a cold
build. All fields below are required. Replace the illustrative IDs and full-length
hexadecimal values with the reviewed producer and artifact identities:

```json
{
  "schema_version": 1,
  "repository": "OWNER/REPOSITORY",
  "target": "windows-x86_64",
  "profile": "all-gui",
  "recipe_id": "REPLACE_WITH_64_LOWERCASE_HEX_DIGITS",
  "run_id": 123,
  "source_commit": "REPLACE_WITH_EXACT_PRODUCER_COMMIT",
  "attempt": 1,
  "job_id": 456,
  "group": {"id": 789, "sha256": "REPLACE_WITH_GROUP_ZIP_SHA256"},
  "proof": {"id": 790, "sha256": "REPLACE_WITH_PROOF_ZIP_SHA256"}
}
```

Read the exact job and artifact metadata through the authenticated GitHub API.
The artifact digest describes the entire transport ZIP; it differs from the
binary/source archive digests inside `sdk-retention.json`. A retry uses the current
checkout's recipe and new consumer source. Its declared producer commit identifies
the earlier checkout that created the retained SDK. The recipes must still match;
a changed producer recipe requires another appropriate group or explicit rebuild.

[`ci_plan.retained_sdk`](../tools/ci_plan.py) checks the repository's numeric and
text identity, the producer's head repository and source commit, exact maintenance
workflow and attempt, completed target job, and the artifacts' immutable IDs,
names, digests, size limits and creation times within that job. The producer job
may have failed its consumers while sibling jobs are still running. A running,
cancelled or timed-out producer is not accepted. Overall run success is neither
required nor inferred. The existing successful-run download interface is unchanged.

Both ZIP hashes are checked before their contents are used. Every member is
validated for portable paths, entry type, duplicate/case aliases and size limits.
Only the two bounded JSON proof records are read; other proof reports are never
extracted. The group must contain exactly three ordinary SDK files, and both
inner inventories and the receipt's exact hashes are verified. Remote identities
are reread before a new group directory is published. Missing, changed, expired,
ambiguous or partial inputs fail without any cold-build fallback.

The new `sdk-origin.json` retains the complete selected request, immutable artifact
metadata, producer job and prior unqualified receipt. Core and, when selected,
complete GUI consumers then run again with the current application sources.
The GUI input and host graphics prerequisites remain explicit maintenance steps;
reusing SDK bytes does not suppress them. A fresh failure stays failed and can
retain only another unqualified group. Base publication still requires successful
current consumers and the independent explicit `execute` gate.
