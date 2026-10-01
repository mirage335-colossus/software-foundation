# Validation record

This records observed checks of the generic reference implementation. Requirements,
workflow definitions and fixture success do not imply qualification on an untested
platform. Generated logs and temporary SDKs remain in ignored local output trees.
Release delivery must preserve its own exact, immutable input and evidence inventory.

The main environment is Debian 13 x86_64, GCC 14.2, CMake 3.31.6, Ninja 1.12.1 and
Python 3.13.5. Native GUI qualification also used an isolated Clang 19 toolchain,
verified toolkit inputs and a virtual display. No remote repository, hosted run,
public release or system package installation was created by this validation.

## Observed mechanisms

| Area | Executed evidence |
| --- | --- |
| Shared GUI | Six native hosts exercise one application, layout and shared smoke scenario; shared/native parity, event, service, transport and lifecycle checks passed |
| Browser GUI | Actual Firefox 153.4.0 and Chromium 154.0.8037.57 passed hosted and compiled Wasm interaction, accessible-name, prompt-cancel, geometry and capture checks; geometry agreed across transports and engines |
| Agent coordination | 233 individual contract tests passed without skips; separate 128-process shared-file and disjoint-file checks preserved exact contributions, revision chains, acknowledgments and ownership closure |
| Prepared browser SDK | Verified supplier archives, complete binary/source/checksum group, path-with-spaces relocation, frozen-cache C++ compilation, retained Node execution, unchanged file inventory and retained-source recipe reconstruction passed; actual CMake GUI build, Node GUI contract, core/CLI contracts and relocated installed consumer also passed using Emscripten 6.0.10 and Node 24.19.0 |
| Final browser SDK output | Both actual browser engines repeated interaction, accessible-name, prompt-cancel, capture and cleanup checks against the prepared SDK's compiled output; parsed geometry was equal across engines |
| Descendant lifetime | Private Linux child-subreaper tests cover detached sessions, nested supervisors, timeout, caller exit, bounded receipts and unchanged caller process state; 17 executed cases passed and one Windows-only case was explicitly excluded |
| Native SDK preparation | The pinned upstream/configuration overlay was resolved and checked; a full cold native compiler build was not run on this newer host |
| Dependency and release contracts | Safe archive, complete inventory, recipe identity, mandatory release-owned copies, full source binding, corruption rejection and retained recovery fixtures passed |
| Runtime inspection | Actual ELF fixtures test architecture, ABI ceilings and private direct/indirect loader resolution; PE fixtures test bounded parsing, architecture and normal/delayed dependency closure |
| Distribution | Seven actual Debian payload/signature/update tests and 17 Arch/Gentoo generation/channel tests passed; combined archives select the requested backend without compilation, preserve shared files and provenance, and reject unknown executables, rollback, tampering and same-version replacement |
| GitHub delivery | 29 offline lifecycle/transport fixtures passed; they exercise exact inventories, immutable bytes, retained certification and promotion rejection, without remote mutation |
| Documentation | Local destinations, heading anchors, strict JSON and requirement-to-code/test references checked |
| Workflows | YAML parsed locally; hosted execution remains a separate qualification |

The combined native Release run passed all 27 CTest entries, including the relocated
installed consumer. Its 23 inner Python suites recorded 387 executed passing cases
and one explicit native-Windows exclusion. No unexpected skips were accepted.
The address/undefined-behavior configuration passed both core and CLI checks.
Actual native and browser-target archives passed complete inventory verification,
relocated execution and independent installed-library consumer builds. The SDK
inventory remained unchanged throughout browser-target compilation and consumption.

Reuse evidence only for unchanged relevant code, configuration, dependencies and
environment; documentation edits do not establish a new runtime result. These are
local implementation checks, not a complete release-policy certification.

## Reproduce the integrated checks

```sh
python3 tools/build.py test release --full --jobs 2 --build-dir build/qualification/native
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
