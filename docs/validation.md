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
| Browser engine qualification | Both actual browser engines repeated interaction, accessible-name, prompt-cancel, capture and cleanup checks against the prepared SDK's compiled output; parsed geometry was equal across engines |
| Descendant lifetime | Private Linux child-subreaper tests cover detached sessions, nested supervisors, timeout, caller exit, bounded receipts and unchanged caller process state; 20 executed cases passed and one Windows-only case was explicitly excluded |
| Native SDK preparation | All four pinned native core/GUI x86_64/ARM64 Buildroot configurations resolved with the intended static toolkit and generic CPU selection; 73 SDK, dependency, ABI and release contract cases passed; full cold compiler production requires the declared builder |
| Dependency and release contracts | Safe archive, complete inventory, recipe identity, mandatory release-owned copies, full source binding, corruption rejection and retained recovery fixtures passed |
| Runtime inspection | Actual ELF fixtures test architecture, ABI ceilings and private direct/indirect loader resolution; PE fixtures test bounded parsing, architecture and normal/delayed dependency closure |
| Distribution | Seven actual Debian payload/signature/update tests and 17 Arch/Gentoo generation/channel tests passed; combined archives select the requested backend without compilation, preserve shared files and provenance, and reject unknown executables, rollback, tampering and same-version replacement |
| GitHub delivery | 29 offline lifecycle/transport fixtures passed; they exercise exact inventories, immutable bytes, retained certification and promotion rejection, without remote mutation |
| Documentation | Local destinations, heading anchors, strict JSON and requirement-to-code/test references checked |
| Workflows | Eight workflows passed actionlint; 49 CI helper, 21 SDK-retention and 11 source-identity cases passed; hosted execution remains separate evidence |
| Installed documentation | Both manual pages passed formatting checks and relocated installation checks; Debian, Arch and Gentoo fixtures preserve variant-specific public manual names |
| Windows host graphics | 28 prerequisite fixtures and 15 artifact fixtures passed; exact pinned driver extraction, native WGL probing and cleanup passed; six actual Windows captures and complete prepared-SDK producer/consumer execution passed as recorded below |
| APT client adapter | Disposable-container preflight and descendant-timeout regressions passed; actual signed HTTPS install/update/tamper-rejection/removal passed in the hosted Bookworm workflow |

Combined native Release verification with distribution tests passed all 34 CTest
entries in one invocation, including the relocated installed consumer and both
manual pages. The signing suites used disposable local GnuPG agent sockets. Its
30 inner Python suites recorded 664 executed passing cases and two explicit
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

Candidate [36924389077](https://github.com/mirage335-colossus/software-foundation/actions/runs/36924389077)
passed all nineteen jobs at `140fa016ed2fb7b2b7b6c551782ef83d2a201b9b` on
Windows x86_64, Linux x86_64 and Linux ARM64. Source/tool, packaging, fresh
copied-archive consumer, sanitizer and distribution jobs succeeded. The disposable
Bookworm client exercised signed HTTPS refresh, installation, exact payload
verification, execution, upgrade, tampered-signature rejection and removal.
The corrected ABI fixture passed all 32 cases on native ARM64 with no exclusions;
its complete proof artifact `11192659299` was downloaded and checksum-verified.
These results qualify their exact inputs and environments, not every older runtime.

Prepared-SDK maintenance
[36922792668](https://github.com/mirage335-colossus/software-foundation/actions/runs/36922792668)
runs at `1126cdc3bbb7834a1200904f6ede6bad1f663451`, with all-GUI profiles and
`execute=false`. The later `140fa01` changes only documentation and the portable
ABI fixture. All seven recipe identities were recomputed; producer inputs remain
unchanged. Each target below needs its own completed result.

| Target | Observed producer and consumer result | Exact recipe |
| --- | --- | --- |
| Browser Wasm | Passed job `110572738346`; two core checks, 30 GUI/source checks, 629 tool cases; two explicit Windows-only exclusions, zero JUnit skips | `783adcbd828ccd3dce72fefa575755d0d94f4eec528634bd4a9bdce7341356d5` |
| Windows x86_64 | Passed job `110572738161`; two core checks, 51 GUI/source checks including 26 GUI checks, 385 tool cases; 55 explicit platform exclusions, zero JUnit skips | `cd16aeb6bd2dff13115d456ffbea2d166db37427106a5e03961926f840f10feb` |
| Linux x86_64 | Sealed complete group; core consumer passed 2/2. GUI/source passed 54/58; corrected consumer retry pending | `bdd39974a891e6161d667bbaa0ff2c1894fe9f188ed76d47d1ad6c896972c9f8` |
| Linux ARM64 | Sealed complete group; core consumer passed 2/2. GUI/source passed 53/58; corrected consumer retry pending | `88c7d871f5cf6210cb4dac6874e666a275dd5f359d42439369a7206b39dbe109` |

The browser run compiled and executed Wasm through retained Node, relocated its
SDK and passed an installed-library consumer. It did not exercise a browser
engine; Firefox and Chromium results above remain separate supporting evidence.
Group `11193236422`, proof `11193336352` and plan `11193201470` identify this
result. Proof and plan ZIP bytes and the canonical plan digest were independently
verified; all inner case statuses and explicit exclusions were inspected.

Windows qualified a fresh offline dependency build, relocated SDK/core consumer,
six installed host smoke tests, FLTK/Rev/SDL scenarios, shared-feature/parity,
web host/renderer and upstream contract suites. Native process tests passed all
25 applicable cases, including eight joined-child completion iterations and
breakaway rejection. Source-group and visual-metric suites passed all 16 and nine
cases respectively. Group `11194256132`, proof `11194445468` and plan `11194370726`
identify this result; proof and plan ZIP bytes and canonical plan digest were
independently verified.

Actual WGL probing confirmed OpenGL 4.6 through the pinned Mesa 26.2.3 driver,
required context entries and buffer storage. Exact loaded DLL identities matched,
all 24 bound graphics evidence hashes matched, and cleanup removed the prerequisite.
All six real captures passed the unchanged visual limits. Mean channel errors
relative to the framebuffer were 0.61927/255 and 1.41589/255 for FLTK at the two
sizes, and 0.11736/255 and 0.33521/255 for Rev. Native font faces and strokes differ
within the stated bounds; this is close appearance, not pixel identity.

For the completed Windows and browser SDK checks, the full binary/source/checksum triplet agrees across
retention, core/GUI consumer receipts and publication plan. Large group ZIP
identities were checked against GitHub metadata without downloading them again.
Retention is deliberately marked `unqualified` and `publication_approved=false`;
separate passed consumer receipts establish the recorded checks. `execute=false`
plans do not publish a base release or qualify publication credentials.

The native Linux GUI consumers exposed shared SDL selection, native capture
scaling and an unnecessary optional SSL import in a mocked cleanup fixture.
ARM64 also encountered the old linker-option fixture already corrected in the
candidate above. Both sealed groups remain available for exact retained-input
retries. Fresh-runner retries must also pass the new producer-path isolation
guard before their consumer receipts and publication plans can qualify.

Earlier failures produced tracked regressions for exact source bytes and native
paths, case-distinct Linux SDK inputs, complete private-runtime inventories,
[known ABI capability floors](portability.md#enforced-baseline-and-runtime-closure),
Windows process completion and [native capture prerequisites](gui-boundary.md).
The ABI reader rejects unknown named capabilities and requirements above the
baseline; a controlled real ELF import fixture works with baseline linkers on
both Linux architectures. Separate local packed-relocation execution demonstrated
the original named-capability rejection and corrected acceptance. Neither fixture
alone qualifies a complete SDK or an older target runtime.

Requested, running, cancelled and failed jobs never count as successful
qualification. These observations do not approve GUI redistribution or authorize
release publication.

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
