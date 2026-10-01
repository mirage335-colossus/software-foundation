# Validation record

This records observed checks of the generic reference implementation. Requirements,
workflow definitions and fixture success do not imply qualification on an untested
platform. Generated logs and temporary SDKs remain in ignored local output trees.
Release delivery must preserve its own exact, immutable input and evidence inventory.

The main environment is Debian 13 x86_64, GCC 14.2, CMake 3.31.6, Ninja 1.12.1 and
Python 3.13.5. Native GUI qualification also used an isolated Clang 19 toolchain,
verified toolkit inputs and a virtual display. A remote repository is configured.
Development feedback passed on the preceding revision; its first full hosted
candidate exposed Windows and package-discovery failures. Those failures produced
focused regressions and fixes. A subsequent hosted result must identify its exact
revision and scope before it supersedes that failure. No public release was
published by these local checks.

## Observed mechanisms

| Area | Executed evidence |
| --- | --- |
| Shared GUI | All seven hosts use one application-side widget/layout table; 28 native CTests passed, including actual framebuffer/FLTK/Rev captures at two sizes, with matching declarations and mean RGB error below 1.01/255; a retained offline source group passed 19 wrapper-driven GUI checks |
| Browser GUI | Actual Firefox 153.4.0 and Chromium 154.0.8037.57 passed hosted and compiled Wasm interaction, accessible-name, prompt-cancel, geometry and capture checks; geometry agreed across transports and engines |
| Agent coordination | 237 individual contract tests passed without skips; separate 128-process shared-file and disjoint-file checks preserved exact contributions, revision chains, acknowledgments and ownership closure |
| Prepared browser SDK | Verified supplier archives, complete binary/source/checksum group, path-with-spaces relocation, frozen-cache C++ compilation, retained Node execution, unchanged file inventory and retained-source recipe reconstruction passed; actual CMake GUI build, Node GUI contract, core/CLI contracts and relocated installed consumer also passed using Emscripten 6.0.10 and Node 24.19.0 |
| Final browser SDK output | Both actual browser engines repeated interaction, accessible-name, prompt-cancel, capture and cleanup checks against the prepared SDK's compiled output; parsed geometry was equal across engines |
| Descendant lifetime | Private Linux child-subreaper tests cover detached sessions, nested supervisors, timeout, caller exit, bounded receipts and unchanged caller process state; 20 executed cases passed and one Windows-only case was explicitly excluded |
| Native SDK preparation | All four pinned native core/GUI x86_64/ARM64 Buildroot configurations resolved with the intended static toolkit and generic CPU selection; 73 SDK, dependency, ABI and release contract cases passed; full cold compiler production requires the declared builder |
| Dependency and release contracts | Safe archive, complete inventory, recipe identity, mandatory release-owned copies, full source binding, corruption rejection and retained recovery fixtures passed |
| Runtime inspection | Actual ELF fixtures test architecture, ABI ceilings and private direct/indirect loader resolution; PE fixtures test bounded parsing, architecture and normal/delayed dependency closure |
| Distribution | Seven actual Debian payload/signature/update tests and 17 Arch/Gentoo generation/channel tests passed; combined archives select the requested backend without compilation, preserve shared files and provenance, and reject unknown executables, rollback, tampering and same-version replacement |
| GitHub delivery | 29 offline lifecycle/transport fixtures passed; they exercise exact inventories, immutable bytes, retained certification and promotion rejection, without remote mutation |
| Documentation | Local destinations, heading anchors, strict JSON and requirement-to-code/test references checked |
| Workflows | Eight workflows passed actionlint; 48 CI helper and 11 source-identity cases passed; hosted execution remains separate evidence |
| Installed documentation | Both manual pages passed formatting checks and relocated installation checks; Debian, Arch and Gentoo fixtures preserve variant-specific public manual names |
| Windows host graphics | 25 prerequisite fixtures and 15 artifact fixtures passed; exact pinned driver extraction and cleanup passed; native WGL probing and real Windows GUI captures require hosted execution |
| APT client adapter | Disposable-container preflight and descendant-timeout regressions passed; real signed HTTPS install/update/tamper-rejection/removal is required in the native Bookworm workflow |

The combined native Release run with distribution tests passed all 31 CTest
entries, including the relocated installed consumer and both manual pages. Its
27 inner Python suites recorded 567 executed passing cases and one explicit
native-Windows exclusion. No unexpected skips were accepted. The preceding
portable native archive also passed complete inventory verification, relocated
execution and an independent installed-library consumer build.

The preceding address/undefined-behavior configuration passed both core and CLI
checks; the relevant core implementation is unchanged. Actual prepared-SDK
browser-target compilation, archive execution and installed-library consumption
also passed. The SDK inventory remained unchanged throughout those operations.
Current GUI-only changes were qualified separately as described above.

Reuse evidence only for unchanged relevant code, configuration, dependencies and
environment; documentation edits do not establish a new runtime result. These are
local implementation checks, not a complete release-policy certification.

## Hosted candidate and maintenance observations

Candidate [36887644570](https://github.com/mirage335-colossus/software-foundation/actions/runs/36887644570)
executed revision `bb1e775e4a02336e349aa2ed54c24a1c311fd76d` on Linux x86_64,
Linux ARM64 and Windows x86_64. Native core and installed-consumer checks,
independent packages, copied-archive execution and sanitizer checks passed.
Linux tool suites passed. Windows tool suites exposed optimistic readers blocking
atomic registry replacement and nonportable fixture paths; the Debian integration
found private permissions on public installed metadata. The overall run failed.

Focused repairs preserve strict inventory and mutation checks. The public runtime
metadata now uses `0644` and its runtime directory uses `0755`, including under
`umask 077`; private records retain `0600`. Fixtures now match the
producer's canonical physical roots and portable inventory separators. Local
verification of those repairs passed 46 coordination, 42 CI, 24 portability, 32 SDK
and 17 test-plan cases with no exclusions.

Candidate [36889414403](https://github.com/mirage335-colossus/software-foundation/actions/runs/36889414403)
at `f9b7bc6035669b542be8b738bdfcc8ce1c4a6606` confirmed the Windows fixture
repairs, but deterministic open-reader replacement tests exposed the remaining
Windows primitive limitation. The compatibility board now serializes complete
reads and writes with one brief, thread-owned mutex; its 46 local coordination cases and 15
migration cases passed, including a real reader/writer overlap test. APT reached
actual package retrieval and exposed unsupported absolute payload URLs. The
repository now uses relative payload paths and immutable source URIs; 15 release
adapter and seven signed repository cases passed locally. These repairs still
require a later native hosted result before either failed run is superseded.

Prepared-SDK maintenance
[36887657215](https://github.com/mirage335-colossus/software-foundation/actions/runs/36887657215)
uses `profile=all-gui`, all targets and `execute=false`. Its Windows startup exposed
a missing graphics-cache directory before acquisition; that caller now creates the
directory, and regressions cover both acquisition paths and a conflicting file.
The browser producer and all 28 GUI consumer CTests passed, but artifact upload
failed because container output belonged to a different user from the host runner.
The container workflows now bind the unprivileged builder to the host UID/GID and
preserve exact artifact bytes and modes. Eleven Linux container-helper cases passed,
including actual same-owner transfers of private files; different-UID Docker
execution remains hosted qualification. Forty-eight CI helper cases passed with
the shared Windows GUI probe/test/cleanup adapter also used before packaging.
Native cold builds remained in progress.
Windows-only maintenance [36889465586](https://github.com/mirage335-colossus/software-foundation/actions/runs/36889465586)
passed graphics acquisition, then the cold offline dependency build correctly
rejected a missing late build-tool download. Explicit maintenance now traverses
full dependency installation to retain those late inputs, discards its compiled
output, and still requires a separate fresh offline build. All 33 local SDK cases
passed, including late-input retention and failed-preparation rejection.
A requested, queued or running job is not successful qualification, and no release
publication is authorized by these checks.

## Reproduce the integrated checks

```sh
python3 tools/build.py test release --full --distribution-tests --jobs 2 --build-dir build/qualification/native
python3 tools/build.py test asan --label core --jobs 2 --build-dir build/qualification/asan
python3 tools/build.py package release --portable --jobs 2 --build-dir build/qualification/package
python3 tools/check_docs.py
```

Use [the archive and shard recipes](testing.md), [prepared SDK commands](sdk.md),
[GUI qualification commands](gui-boundary.md) and [certification adapters](certification.md)
for their exact prerequisites and identities. Repository signing tests require local
GPG agent sockets; a restricted wrapper which forbids them cannot qualify that
scope. The fixtures use disposable keys and never install or publish packages.

## Material limits

- Native Windows and ARM64 execution, Windows toolchain selection and Job Object
  behavior, and older Linux user-space/kernel combinations require their actual
  environments. Mocked format/API checks are not native execution.
- The cold native source SDK recipe requires an actual Debian 12 Bookworm builder.
  Browser SDK tools are retained upstream binaries; their native source rebuild
  is not supplied by that recipe. Source availability is documented separately.
- GUI redistribution remains blocked by unresolved upstream top-level terms.
  Local compilation and tests do not approve binary redistribution.
- Arch, Gentoo and Debian client installation/update/removal require disposable
  native package-manager environments. Signed-channel fixtures are distinct evidence.
- Hosted CI, GitHub permissions/API behavior, publication credentials and live
  package channels need deployment qualification in the adopted repository.
- Shared-source coordination requires the stated filesystem primitives and
  cooperative writers. Uncooperative participants need enforced private access.
- Real devices, assistive technology, every desktop/window-manager combination,
  long-duration operation and workload performance need separately specified checks.
  Passing this record is not a guarantee for every future feature or environment.
