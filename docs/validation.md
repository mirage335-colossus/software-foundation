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
| Windows host graphics | 28 prerequisite fixtures and 15 artifact fixtures passed; exact pinned driver extraction, native WGL probing and cleanup passed; six actual Windows captures passed corrected offline comparison, while complete updated SDK execution remains pending |
| APT client adapter | Disposable-container preflight and descendant-timeout regressions passed; actual signed HTTPS install/update/tamper-rejection/removal passed in the hosted Bookworm workflow |

Combined native Release verification with distribution tests passed all 34 CTest
entries in one invocation, including the relocated installed consumer and both
manual pages. The signing suites used disposable local GnuPG agent sockets. Its
30 inner Python suites recorded 650 executed passing cases and two explicit
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

Candidate [36914367685](https://github.com/mirage335-colossus/software-foundation/actions/runs/36914367685)
passed at `ec347ba63f6d9c80a7b82dff332490f72fb93ebc` on Windows x86_64,
Linux x86_64 and Linux ARM64. All source/tool, packaging, fresh copied-archive
consumer, sanitizer and distribution jobs succeeded. The disposable Bookworm
client check exercised signed HTTPS refresh, installation, exact payload
verification, execution, upgrade, tampered-signature rejection and removal.
These results qualify the recorded environments and inputs; they do not establish
every declared older-runtime baseline.

Browser SDK maintenance [36906409188](https://github.com/mirage335-colossus/software-foundation/actions/runs/36906409188)
passed at `43780010adc170848a094170ea1ac649c2dba497` with `execute=false`.
Production, relocated consumption, two core checks, 29 GUI/source checks and all
retention uploads succeeded. JUnit recorded no skipped checks; 572 tool cases
passed with two explicitly excluded native-Windows cases. Recipe
`52098b801a6a7fd8daac7657158a6a161cd5869ac231856962bc1a11e365fabb`
produced group artifact `11185901696`, proof `11185271833` and plan `11185426964`.
Proof and plan bytes were checksum-verified. This run exercised compiled Wasm
through retained Node; real Firefox and Chromium interactions remain the separate
supporting evidence above.

Windows production [36906320107](https://github.com/mirage335-colossus/software-foundation/actions/runs/36906320107)
completed a fresh offline dependency build with normalized LF recipe inputs and
retained a verified complete binary/source/checksum group. Its consumer failure
left that group explicitly unqualified. Explicit reuse verifies exact producer,
run, attempt, job, recipe, artifact and complete byte identities before running
fresh consumers; no different recipe or failed consumer is promoted implicitly.

Retained Windows retry [36913909389](https://github.com/mirage335-colossus/software-foundation/actions/runs/36913909389)
at `797d88210c6e6448818b971ff1b462d4a72ae272` passed both core checks and
48 of 50 CTests, including 25 of 27 GUI checks. All six installed host smoke tests,
FLTK/Rev/SDL host scenarios, shared-feature/parity checks, web host/renderer checks
and all eleven upstream suites passed. Actual WGL probing confirmed the pinned
Mesa driver, required context entries and buffer storage; loaded module identities
and cleanup passed. The failed job retained verified SDK inputs; its overall
result remains a failure.

The remaining source-group fixture failure occurred before assertions: host text
newline conversion differed from Git's committed bytes. Fixtures now write exact
bytes and configure their private repository explicitly, including logical
executable modes. Sixteen cases pass with inherited newline conversion and under
the logical Windows mode branch; the old fixture reproduces the observed failure.
Production complete-tree verification remains unchanged.

The visual failure counted only fully dark pixels, discarding native antialiased
ink. Measurement now uses declared foreground/background contrast for visible
extents and integrated ink, including all four supported text tones. Acceptance
bounds remain eight pixels for text extents, 0.45–2.2 for relative ink, and below
4/255 for mean channel error. Regression checks reject absent, faint, clipped,
moved and excessive text, altered palette/geometry, and assertion-disabled Python.
The corrected comparator passes all twelve retained Linux/Windows captures without
changing their bytes. Windows mean channel errors are 0.61927/255 and 1.41589/255
for FLTK at the two sizes, and 0.11736/255 and 0.33521/255 for Rev. Native font faces
and strokes differ within these bounds; this is close appearance, not pixel identity.
Re-evaluating retained images does not claim new native binary execution.

Dependency-free source-group and visual-metric suites now run once in ordinary
native candidate jobs, with individual case receipts and GUI-focused labels.
Their corrected native Windows execution and the complete prepared-SDK retry
remain separately required hosted results.

ARM64 maintenance [36904727103](https://github.com/mirage335-colossus/software-foundation/actions/runs/36904727103),
at `c87c6905fa9049ab7759e4ce797842e266965d38`, completed supplier compilation
and license-information collection, then failed before sealing on valid
case-distinct Linux headers. The exact supplier compatibility-link repair passed,
but this run produced no completed SDK group or consumer qualification. The
Linux-specific path-policy repair preserves required header names and bytes through
materialization, archive verification, installation and relocation. Its 184 affected
contract cases passed without skips; a separate actual-header fixture preserved
eight Linux UAPI headers and compiled and ran a consumer using both case-distinct
headers after relocation. Destination probes reject lossy filesystems before
copying inputs. Windows and ordinary archive policies remain strict.

A subsequent complete review of the pinned supplier's installed shared libraries
and actual build configuration identified two additional developer/runtime library
pairs requiring matched private libc/loader providers. The SDK-only inventory now
retains and checks them with exact names, locations, hashes, source/recipe identity
and byte-identical development aliases. Seventy-nine portability/SDK cases pass,
including old-code rejection, incorrect-provider cases and unchanged application
package rejection. No developer inputs were discarded. Replacement native
producers run at `769390b136d5d649de0605807344c758f89383a9`; their outcomes
remain pending.

The shared SDK helper changes create new recipe identities, including Windows and
WebAssembly recipes that retain those helpers. Earlier archives are never
relabeled. Complete production and consumption of the changed recipes require
new hosted results. Earlier checks remain supporting evidence only where relevant
inputs are unchanged. Requested, queued, running, cancelled and failed jobs are
not successful qualification. These observations do not establish that every SDK
passes, approve GUI redistribution, or authorize release publication.

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
