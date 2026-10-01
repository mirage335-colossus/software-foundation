# Prepared SDKs and target sysroots

An SDK is a versioned developer input: host tools plus a controlled target
environment. Its host requirements describe where the tools run. Its target
requirements describe where the generated application runs. Keep these
contracts separate in metadata, documentation, and tests.

The default example builds with native tools. Its SDK toolchain entry point
demonstrates consuming explicitly prepared inputs; this repository does not ship
a compiled compiler, a complete production sysroot, or evidence that an older
runtime has been qualified. The requirements below describe how to extend it
into a maintained SDK supply process.

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
`recipe_id`, and a `target` object containing `system: "Linux"`, `processor`,
`triple`, `sysroot`, and `cxx_compiler`. The last two are existing relative paths
whose resolved locations stay inside the SDK. The `files` object maps every
SDK file other than the root manifest to its SHA-256; the compiler must be
included. The wrapper verifies completeness and every digest before configuration
and retains the manifest digest in the build-tree identity.

The schema is a deliberately small consumer contract. Production manifests
also need explicit host requirements, target runtime ceiling, licenses, recipe
provenance, archive identity, and relocation policy described below. Merely
providing the minimum fields does not qualify an SDK for release use.

## Recipe and archive identity

Track the recipe, not a large generated SDK tree. The recipe must identify every
direct and transitive source, bootstrap input, exact revision, source archive
digest, patch, configuration, and relevant build helper. Include host tools in
the inventory, including generators required only while preparing dependencies.
Content-address the recipe from normalized paths and complete input bytes.

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
Application releases should retain their exact required SDK/dependency group
or an equivalently durable independently retained reference. A surviving source
and binary release should be recoverable when a convenience dependency index
is unavailable.

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
