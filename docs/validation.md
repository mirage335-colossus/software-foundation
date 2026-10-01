# Validation record

This records observed checks of the generic reference implementation. Requirements,
workflow definitions and fixture success do not imply qualification on an untested
platform. Generated logs and temporary SDKs remain in ignored local output trees.
Release delivery must preserve its own exact, immutable input and evidence inventory.

The main environment is Debian 13 x86_64, GCC 14.2, CMake 3.31.6, Ninja 1.12.1 and
Python 3.13.5. Native GUI qualification also used an isolated Clang 19 toolchain,
verified toolkit inputs and a virtual display. A remote repository is configured.
Observed hosted results below identify exact revisions and scopes. Earlier
failures produced focused regressions and repairs; unqualified scopes remain
explicit. No public release was published by these checks.

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
| Workflows | Eight workflows passed actionlint; 49 CI helper, 21 SDK-retention and 11 source-identity cases passed; hosted execution remains separate evidence |
| Installed documentation | Both manual pages passed formatting checks and relocated installation checks; Debian, Arch and Gentoo fixtures preserve variant-specific public manual names |
| Windows host graphics | 25 prerequisite fixtures and 15 artifact fixtures passed; exact pinned driver extraction and cleanup passed; native WGL probing and real Windows GUI captures require hosted execution |
| APT client adapter | Disposable-container preflight and descendant-timeout regressions passed; actual signed HTTPS install/update/tamper-rejection/removal passed in the hosted Bookworm workflow |

Combined native Release verification with distribution tests passed all 32 CTest
entries in one invocation, including the relocated installed consumer and both
manual pages. The signing suites used disposable local GnuPG agent sockets. Its
28 inner Python suites recorded 607 executed passing cases and two explicit
native-Windows exclusions.
The selected-linker native case passed separately on Windows as recorded below.
No unexpected skips were accepted. The preceding
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

Full candidate [36898077179](https://github.com/mirage335-colossus/software-foundation/actions/runs/36898077179)
passed at `ac8ca19867b832ba33dae6cc2bc5abcbb46047a5` on Windows x86_64,
Linux x86_64 and Linux ARM64. Native source/tool suites, independent packaging,
fresh copied-archive execution and sanitizer checks passed. The real Debian client
receipt records signed HTTPS refresh, installation, exact payload verification,
runtime execution, upgrade, tampered-signature rejection and removal. This
supersedes earlier candidate failures for those exact scopes and inputs.

The browser job of SDK maintenance [36898087108](https://github.com/mirage335-colossus/software-foundation/actions/runs/36898087108)
passed at `ac8ca19867b832ba33dae6cc2bc5abcbb46047a5` with `execute=false`.
Production, two core and 29 GUI/source consumer checks, and all three artifact
uploads succeeded. This also qualified the container builder's host UID/GID mapping and
readable retained output. Actual browser-engine interactions remain the separately
observed scope recorded above; this maintenance run did not execute browser engines.

Windows SDK maintenance [36892089929](https://github.com/mirage335-colossus/software-foundation/actions/runs/36892089929)
completed the maintenance download closure, fresh offline build and export of all
17 dependencies, then failed before consumer execution because a linker help
command returned a nonzero status. Consumers now use validated native PE file
version inspection. The real selected-linker test passed on the Windows tools job
of [36896590427](https://github.com/mirage335-colossus/software-foundation/actions/runs/36896590427)
at `25a674d6c564b6068c0c73c0ee0e2fd6c2444062`: the build suite recorded 12 passes
and no exclusions. That candidate exposed one short-path fixture mismatch;
correcting it preserves the producer's existing canonical-path behavior.

The Windows job of maintenance run `36898087108` then completed SDK production
and both core consumer checks. Its GUI compilation exposed Windows header macros
colliding with standard C++ minimum/maximum calls. The shared GUI interface now
sets `NOMINMAX` for all Windows consumers; 15 boundary tests passed, including
actual CMake direct/transitive consumers and removal controls. Native GUI execution
still needs a successful retry. The failed job retained a verified complete SDK
group with an explicitly unqualified receipt; retaining those bytes does not make
the failed consumer checks pass.

Retained Windows retry [36903597192](https://github.com/mirage335-colossus/software-foundation/actions/runs/36903597192)
at `49e3178f0ef83fa98a139acd52aee1c569d0918b` verified the exact prior
producer/artifacts, restored the complete SDK, and passed both core checks without
cold SDK production. The GUI macro repair compiled successfully. MSVC then rejected
an upstream test callback's self-reference during its adapter's initialization;
review identified a second matching test. Reviewed generated-source adaptations
preserve both tests' event, selection, mutation and recursion assertions. Native
execution of those corrected GUI tests remains necessary. Both actual generated
contract/adapter executables passed locally, with all original assertions and
supplier bytes preserved; the 16 boundary fixtures also passed.

The same candidate's Windows tools job exposed ZIP-name normalization in a malformed
archive fixture. Recovery now checks original stored member names before Python's
host-dependent cleanup; fixtures preserve raw backslash and NUL names in both ZIP
headers. The 21 retention tests and 49 CI tests pass locally, with a failing old-code
control; the corrected Windows tools suite still requires its hosted result.

PowerShell checkout attributes now require LF. The earlier Windows CRLF checkout
had changed the exact SDK recipe identity despite the same Git revision. Every
Windows producer helper has matching LF attributes and bytes; the CRLF control
reproduces the prior identity. A freshly normalized Windows group must be produced,
rather than treating different recipe bytes as interchangeable.

The initial ARM64 cold build completed compilation, the SDK target and supplier
license-information collection, then rejected runtime-only skeleton aliases during
assembly. The subsequent source review identified additional target-only libc
programs/modules and required development-library aliases. Exact source-bound
omission and identical-provider checks preserve compiler inputs and strict
application ABI policy; 39 SDK and 27 actual-ELF/portability fixture cases passed.
Corrected native production and all GUI consumers still require hosted results.

Twenty-one complete-group retention and recovery tests verify that a consumer failure
remains a failure while checked binary/source/checksum bytes can be retained and
explicitly reused. Producer, artifact, recipe, receipt and complete byte identities
are verified before fresh consumers run. The latest combined verification
passed all 16 GUI boundary, 49 CI and 21 retention cases. Their receipt remains
explicitly unqualified; no failed-run artifact becomes a qualified base automatically.

The ARM64 producer in maintenance run `36898087108` completed compilation and
supplier license-information collection, then rejected a supplier directory-link
cycle before SDK sealing. This failed scope has no completed group or consumer
qualification. Exact pinned supplier initialization rules reproduce the host
`usr -> .` compatibility cycle for both native architectures. Native assembly now
validates and removes only that alias; 42 SDK tests and both supplier-rule fixtures
pass while preserving target inputs and arbitrary-cycle rejection. Complete
corrected native producers still need hosted qualification.

A requested, queued or running job is not successful qualification. Evidence is
reused only for identical relevant inputs; the latest repairs still need their
prepared-SDK hosted checks. No release publication is authorized by these runs.

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

- Native Windows and ARM64 core/tool/package execution is recorded above.
  Prepared GUI SDKs, the oldest declared Windows runtime, and older Linux
  user-space/kernel combinations need their own actual environments. Mocked
  format/API checks do not replace those results.
- The cold native source SDK recipe requires an actual Debian 12 Bookworm builder.
  Browser SDK tools are retained upstream binaries; their native source rebuild
  is not supplied by that recipe. Source availability is documented separately.
- GUI redistribution remains blocked by unresolved upstream top-level terms.
  Local compilation and tests do not approve binary redistribution.
- Arch and Gentoo client installation/update/removal require disposable native
  package-manager environments; their signed-channel fixtures are distinct
  evidence. The executed Debian client result is limited to its recorded host.
- Hosted CI, GitHub permissions/API behavior, publication credentials and live
  package channels need deployment qualification in the adopted repository.
- Shared-source coordination requires the stated filesystem primitives and
  cooperative writers. Uncooperative participants need enforced private access.
- Real devices, assistive technology, every desktop/window-manager combination,
  long-duration operation and workload performance need separately specified checks.
  Passing this record is not a guarantee for every future feature or environment.
