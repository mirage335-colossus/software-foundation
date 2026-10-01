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

## Delivery workflow expansion

The current update replaces Actions artifact transport with per-run private draft
release bundles, adds explicit legacy SDK migration, an initial seven-host gallery
workflow and the `_Publish new Latest release` orchestration. The local focused
checks passed 32 transport, 108 workflow/retention, 30 GitHub delivery and 22 GUI
boundary cases. The boundary cases include actual incremental CMake rebuilds when
nested headers are added or changed. Documentation links and workflow syntax pass.
The screenshot and Latest suites passed 17 and 10 cases respectively. Combined
Release verification with distribution enabled passed all 38 CTest entries across
one complete invocation and one targeted rerun: 770 inner Python cases passed,
with two explicit native-Windows exclusions and no unexpected skips. The rerun
made the new incremental-header fixture timestamp deterministically newer than
its build stamp; all dependency-rejection assertions remain in place.
New hosted transfer, screenshot and complete lifecycle results are pending; the
older executions below establish only their recorded revisions and scopes.
No SDK recipe or retained group bytes changed in this update.

## Observed mechanisms

| Area | Executed evidence |
| --- | --- |
| Shared GUI | All seven hosts use one application-side widget/layout table; 28 native CTests passed, including actual framebuffer/FLTK/Rev captures at two sizes, with matching declarations and mean RGB error below 1.01/255; a retained offline source group passed 19 wrapper-driven GUI checks |
| Browser GUI | Actual Firefox 153.4.0 and Chromium 154.0.8037.57 passed hosted and compiled Wasm interaction, accessible-name, prompt-cancel, geometry and capture checks; geometry agreed across transports and engines |
| Agent coordination | 237 individual contract tests passed without skips; separate 128-process shared-file and disjoint-file checks preserved exact contributions, revision chains, acknowledgments and ownership closure |
| Prepared browser SDK | Verified supplier archives, complete binary/source/checksum group, path-with-spaces relocation, frozen-cache C++ compilation, retained Node execution, unchanged file inventory and retained-source recipe reconstruction passed; actual CMake GUI build, Node GUI contract, core/CLI contracts and relocated installed consumer also passed using Emscripten 6.0.10 and Node 24.19.0 |
| Browser engine qualification | Both actual browser engines repeated interaction, accessible-name, prompt-cancel, capture and cleanup checks against the prepared SDK's compiled output; parsed geometry was equal across engines |
| Descendant lifetime | Private Linux child-subreaper tests cover detached sessions, nested supervisors, timeout, caller exit, bounded receipts and unchanged caller process state; 20 executed cases passed and one Windows-only case was explicitly excluded |
| Native SDK preparation | All four pinned native core/GUI configurations resolved; actual all-GUI x86_64/ARM64 source production ran in Debian 12 Bookworm and sealed complete groups; exact fresh-runner consumer results appear below |
| Dependency and release contracts | Safe archive, complete inventory, recipe identity, mandatory release-owned copies, full source binding, corruption rejection and retained recovery fixtures passed |
| Runtime inspection | Actual ELF fixtures test architecture, ABI ceilings and private direct/indirect loader resolution; PE fixtures test bounded parsing, architecture and normal/delayed dependency closure |
| Distribution | Seven actual Debian payload/signature/update tests and 17 Arch/Gentoo generation/channel tests passed; combined archives select the requested backend without compilation, preserve shared files and provenance, and reject unknown executables, rollback, tampering and same-version replacement |
| GitHub delivery | 29 offline lifecycle/transport fixtures passed; they exercise exact inventories, immutable bytes, retained certification and promotion rejection, without remote mutation |
| Documentation | Local destinations, heading anchors, strict JSON and requirement-to-code/test references checked |
| Workflows | Eight workflows passed actionlint; 49 CI helper, 39 SDK-retention and 11 source-identity cases passed; hosted execution remains separate evidence |
| Installed documentation | Both manual pages passed formatting checks and relocated installation checks; Debian, Arch and Gentoo fixtures preserve variant-specific public manual names |
| Windows host graphics | 28 prerequisite fixtures and 15 artifact fixtures passed; exact pinned driver extraction, native WGL probing and cleanup passed; six actual Windows captures passed; complete prepared-SDK execution is reported with its exact replay status below |
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

Candidate [36930890192](https://github.com/mirage335-colossus/software-foundation/actions/runs/36930890192)
passed all nineteen jobs at `44a8687afc60ad630e0d96bf6147814a13189c99` on
Windows x86_64, Linux x86_64 and Linux ARM64. Source/tool, packaging, fresh
copied-archive consumer, sanitizer and distribution jobs succeeded. The disposable
Bookworm client exercised signed HTTPS refresh, installation, exact payload
verification, execution, upgrade, tampered-signature rejection and removal.
The corrected ABI fixture passed all 32 cases on native ARM64 with no exclusions.
The preceding fixture proof was independently checksum-verified; its source is
unchanged in this candidate.
These results qualify their exact inputs and environments, not every older runtime.

Cold SDK maintenance
[36922792668](https://github.com/mirage335-colossus/software-foundation/actions/runs/36922792668)
at `1126cdc3bbb7834a1200904f6ede6bad1f663451` produced complete sealed groups for
all four targets below. Subsequent checks reuse those exact binary/source/checksum
triplets on fresh runners; they neither rebuild nor relabel the SDKs. Recipe inputs
and all seven recipe identities remain unchanged.

The browser replay uses `44a8687afc60ad630e0d96bf6147814a13189c99`. Linux native
replays use `c137d29f383afc643dac384edd0bd425129127d5`; the Windows replay uses
`e2d14be3d21c5a0cbe98bdce9fcd4bb7b53192c4`. Changes after the candidate select
native SDL test drivers and repair configuration-aware CTest fixture discovery.
The core/package/sanitizer/APT implementations and the browser implementation
remain unchanged; their preceding successful checks apply to those same relevant
inputs. Every maintenance run uses `execute=false`.

| Target and replay | Observed result | Exact recipe |
| --- | --- | --- |
| [Browser Wasm 36930860584](https://github.com/mirage335-colossus/software-foundation/actions/runs/36930860584) | Passed: two core checks, 30 GUI/source checks, 651 tool cases; two explicit Windows-only exclusions, zero JUnit skips | `783adcbd828ccd3dce72fefa575755d0d94f4eec528634bd4a9bdce7341356d5` |
| [Windows x86_64 36935214911](https://github.com/mirage335-colossus/software-foundation/actions/runs/36935214911) | Passed: two core checks, 51 GUI/source checks, 409 tool cases; 55 explicit platform exclusions, zero JUnit skips; actual Windows SDL driver | `cd16aeb6bd2dff13115d456ffbea2d166db37427106a5e03961926f840f10feb` |
| [Linux x86_64 36933074074](https://github.com/mirage335-colossus/software-foundation/actions/runs/36933074074) | Passed: two core checks, 58 GUI/source checks, 663 tool cases; two explicit Windows-only exclusions, zero JUnit skips; actual X11 SDL driver | `bdd39974a891e6161d667bbaa0ff2c1894fe9f188ed76d47d1ad6c896972c9f8` |
| [Linux ARM64 36933047430](https://github.com/mirage335-colossus/software-foundation/actions/runs/36933047430) | Passed: two core checks, 58 GUI/source checks, 663 tool cases; two explicit Windows-only exclusions, zero JUnit skips; actual X11 SDL driver | `88c7d871f5cf6210cb4dac6874e666a275dd5f359d42439369a7206b39dbe109` |

The browser run compiled and executed Wasm through retained Node, relocated its
SDK and passed an installed-library consumer. It did not exercise a browser
engine; Firefox and Chromium results above remain separate supporting evidence.
Group `11196926091`, proof `11196850985` and plan `11196681188` identify this
result. Proof and plan ZIP bytes, canonical plan digest, every inner case and
explicit exclusion were independently verified. Both consumer receipts bind the
passed isolation receipt; the original producer path remained absent throughout.

Both Linux replays passed all checks with the actual X11 SDL driver. Their six
framebuffer/FLTK/Rev captures have identical shared declarations at 800×640 and
480×360. Mean channel errors against framebuffer were 0.27826/0.59174 for FLTK
and 0.11736/0.33521 for Rev, with unchanged bounds. Raw capture hashes and
comparison assertions were independently checked. Both core and GUI receipts
bind a passed isolation receipt with all four checkpoints complete.

Windows passed all 51 GUI/source checks, including 26 GUI checks, and both
configuration-aware discovery fixtures. Installed SDL and its interaction scenario
executed with the actual `windows` driver. The six captures and all 24 bound
graphics evidence hashes were independently verified. Exact loaded WGL DLL paths
and locked hashes matched; graphics prerequisite cleanup completed. Mean channel
errors against framebuffer were 0.61927/1.41589 for FLTK and 0.11736/0.33521 for
Rev at the two sizes. Native fonts differ within the unchanged comparison bounds.
Both consumer receipts bind a passed isolation receipt with all four checkpoints
complete.

The following artifact identities supplement the exact replay links above:

| Target | Complete group | Verified proof ZIP | Verified plan ZIP |
| --- | --- | --- | --- |
| Browser Wasm | `11196926091` | `11196850985` | `11196681188` |
| Linux x86_64 | `11196364488` | `11196349636` | `11196329556` |
| Linux ARM64 | `11196973595` | `11196654515` | `11196834046` |
| Windows x86_64 | `11198750342` | `11198735489` | `11198615462` |

For all four completed replays, the full binary/source/checksum triplet agrees
across origin, retention, isolation, core/GUI consumer receipts and publication
plan. Proof and plan ZIP digests and canonical plan hashes were independently
verified. Large group ZIP identities were checked against GitHub metadata without
redundant downloads; each actual replay restored and checked the complete bytes.
Retention is deliberately marked `unqualified` and `publication_approved=false`;
separate passed consumer receipts establish the recorded checks. `execute=false`
plans do not publish a base release or qualify publication credentials.

Concrete failures produced tracked regressions for exact source bytes and native
paths, case-distinct SDK inputs, complete private-runtime inventories,
[known ABI capability floors](portability.md#enforced-baseline-and-runtime-closure),
Windows process completion, optional test-runtime extensions,
[producer-path isolation](sdk.md#exclude-producer-paths-during-sdk-qualification),
and [native capture/display prerequisites](gui-boundary.md). The ABI reader rejects
unknown named capabilities and requirements above the baseline; its controlled
real ELF import fixture works with baseline linkers on both Linux architectures.
Separate local packed-relocation execution demonstrated the original rejection
and corrected acceptance. Neither fixture alone qualifies a complete SDK or an
older target runtime. Native visual comparisons preserve raw captures and
unchanged bounds; separately executed scale checks preserve logical geometry.

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

- Prepared SDK checks qualify their exact recipes and observed environments.
  A tested all-GUI recipe does not qualify different core-only or future recipe
  identities. The oldest declared Windows runtime and older Linux user-space/kernel
  combinations still need their own actual environments; mocked checks cannot
  replace them.
- Native source production used actual Debian 12 Bookworm containers on hosted
  kernels. Browser SDK tools are retained upstream binaries; their native source
  rebuild is not supplied by that recipe. Source availability is documented separately.
- GUI redistribution remains blocked by unresolved upstream top-level terms.
  Local compilation and tests do not approve binary redistribution.
- Arch and Gentoo client installation/update/removal require disposable native
  package-manager environments; their signed-channel fixtures are distinct
  evidence. The executed Debian client result is limited to its recorded host.
- Publication credentials and live package channels were not exercised. An
  adopted repository must qualify its own permissions and external services.
- Shared-source coordination requires the stated filesystem primitives and
  cooperative writers. Uncooperative participants need enforced private access.
- Real devices, assistive technology, every desktop/window-manager combination,
  long-duration operation and workload performance need separately specified checks.
  Passing this record is not a guarantee for every future feature or environment.
