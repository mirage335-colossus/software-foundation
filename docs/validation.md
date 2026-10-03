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
explicit. The current delivery record below distinguishes public publication from
earlier private preparation and local fixtures.

## Current public delivery evidence (2026-10-03)

The four SDK base qualification and public publication runs completed successfully:
[Linux x64](https://github.com/mirage335-colossus/software-foundation/actions/runs/36979799032),
[Linux ARM64](https://github.com/mirage335-colossus/software-foundation/actions/runs/36979801780),
[Windows x64](https://github.com/mirage335-colossus/software-foundation/actions/runs/36977319633)
and [Wasm](https://github.com/mirage335-colossus/software-foundation/actions/runs/36977322721).
Their publication receipts were independently fetched and checked. The consumer
selectors identify these retained recipes exactly:

| Target | SDK recipe SHA-256 |
| --- | --- |
| Linux x64 | `bdd39974a891e6161d667bbaa0ff2c1894fe9f188ed76d47d1ad6c896972c9f8` |
| Linux ARM64 | `88c7d871f5cf6210cb4dac6874e666a275dd5f359d42439369a7206b39dbe109` |
| Windows x64 | `cd16aeb6bd2dff13115d456ffbea2d166db37427106a5e03961926f840f10feb` |
| Wasm | `783adcbd828ccd3dce72fefa575755d0d94f4eec528634bd4a9bdce7341356d5` |

The [GUI source publication](https://github.com/mirage335-colossus/software-foundation/actions/runs/36979568787)
also passed and was independently read back. Its group identity is
`10d22dd104c3c3de38b979b5c5d9b6d3e9cea827d0dc748b87d97baee081c8b3`.
New producer code can define a new recipe identity without invalidating an explicit
consumer selection of verified retained bytes; never relabel an old archive.

The [public screenshot run](https://github.com/mirage335-colossus/software-foundation/actions/runs/36977734580)
passed and published [seven actual backend captures](https://github.com/mirage335-colossus/software-foundation/releases/tag/screenshots-36977734580-attempt-1).
The publication receipt and images were independently downloaded and verified.
Framebuffer, FLTK and Rev captures show the same geometry and palette, with small
native-font rendering differences. The gallery also contains SDL, terminal,
hosted web and Wasm captures. Browser tooling is a host prerequisite, outside the
SDK and application payload. The gallery separately verified the browser's
namespace and seccomp sandbox; that evidence does not imply that every other
browser test performs the same sandbox-status probe.

The [complete Latest workflow](https://github.com/mirage335-colossus/software-foundation/actions/runs/37070391587)
passed all 45 jobs at `4787098055de7190da730a577d6e0946c8849f2d` and
published [the certified application release](https://github.com/mirage335-colossus/software-foundation/releases/tag/release-37070391587-attempt-1).
All eleven certification batches passed: 106 logical checks across 66 physical
executions, with no warnings or omitted requirements. The policy covers Linux
x64 and ARM64, Windows x64, and Wasm; its recorded environments include Debian
12 and 13, Ubuntu 24.04, Windows Server 2022, Chromium and Firefox. The 106 checks
comprise 44 archive, 19 source, 19 recovery, 12 ABI and 12 APT results.

| Exact delivery identity | SHA-256 |
| --- | --- |
| Release inventory | `b386888b83f234662662c22683c72de3b93824a7aa789569411e0d2061fa2c4e` |
| Certificate | `273aa9762ea2b474125d568eec57cf75ace01729c08f90b593fa2dc87af1291d` |
| Final Latest receipt | `a6a15a755f94e2a11d34c61f3015f83372a205e29f6e916fdc93d3e4dc7cab0d` |

The final receipt was independently fetched from successful job `111096703678`;
the remote Latest endpoint identified ordinary public release `402199557`, with
25 assets. Independent certificate readback reproduced all 106 results, rehashed
2,761 evidence files and confirmed the original 23 asset identities were unchanged.
It rehashed 55 source inputs and checked 22 payload input identities against retained
metadata; the hosted jobs performed the full payload download and execution.
This bounded independent audit is not a second local replay of all payloads or
evidence of a separately network-disabled recovery run.

The [focused Windows GUI run](https://github.com/mirage335-colossus/software-foundation/actions/runs/37069286298),
release producer and published-release certification all passed. The producer and
each source/recovery execution passed 68 CTest entries and 721 tool cases, with 60
explicit platform exclusions. Certification passed all 18 Windows logical checks,
including six archive backends and installed consumers. The verified static SDK
configuration, graphics cleanup and private compiler-owner completion all passed;
no incomplete cleanup was observed. These results qualify the recorded toolset and
runner, not every older Windows client or an exhaustive process/network trace.

Application delivery, full release certification and signed package-channel
installation are separate qualifications. The first live signed-channel run
[37087057851](https://github.com/mirage335-colossus/software-foundation/actions/runs/37087057851)
failed during preparation when a per-reference loop replaced the callable needed
for the next backend. It created no channel release or tag, and the application
Latest was unchanged. Native signed-channel acceptance remains pending its own
completed client evidence. A real signed two-backend fixture reproduced the exact
failure before the correction and passed afterward; the complete affected suite
passed all 30 cases without exclusions. Signature, retained-reference and package
validation remain intact.

Earlier application runs remain useful failure evidence; none are relabeled as
successful qualification. Run
[36994657303](https://github.com/mirage335-colossus/software-foundation/actions/runs/36994657303)
passed the complete source gates, four application producers and assembly, then
stopped when its first normal candidate was observed as Latest despite the false
publication request. The exact release was reconciled and changed to prerelease;
its source tag and all 23 assets were preserved and the Latest endpoint was
independently confirmed absent. Candidate publication now requires prerelease
status until certified promotion. This failed run is not qualification evidence
for certification or Latest. The later all-GUI candidate
[37025224490](https://github.com/mirage335-colossus/software-foundation/actions/runs/37025224490)
passed source gates, all four producers, assembly and public candidate readback.
Seven of eleven certification batches passed; four correctly failed on the source
fixture and Windows lifetime defects described below. Its failed certificate was
attached immutably, promotion was skipped and the final verdict failed. These
results are preserved, not counted as successful release qualification. The later
successful Latest evidence is recorded above; native signed channels have their
own distinct client requirements.

The subsequent candidate
[37045706923](https://github.com/mirage335-colossus/software-foundation/actions/runs/37045706923)
at `52c5adf12c665c5743395bfe0677c33c7126d366` passed all six Windows
archive checks. Its source and recovery executions each passed all 67 CTest entries
and all 31 tool suites: 693 executed cases passed, with 60 declared platform
exclusions. Their retained evidence hashes were independently verified. Both outer
executions nevertheless failed strict completion: the source command left VCTIP
and another unclassified process alive; recovery left the selected toolset's
MSPDBSRV alive. The inner passes do not establish complete release qualification.
This exposed compiler-capable build and installed-consumer commands outside the
existing narrow graphics-probe owner. Its failed certificate was attached immutably,
promotion was skipped, and independent readback verified the public evidence bytes,
original asset digests and prerelease status. The candidate remains ineligible for promotion.

The next run,
[37061687505](https://github.com/mirage335-colossus/software-foundation/actions/runs/37061687505),
stopped at its Windows source gate before building release archives. A new unit
fixture compared the temporary directory's short Windows path with its canonical
expanded path. The fixture now canonicalizes its own root before testing exact
selected-toolkit identity; production validation and the independently qualified
native compiler-service behavior are unchanged.

Run [37064137298](https://github.com/mirage335-colossus/software-foundation/actions/runs/37064137298)
passed the full source gates. The Windows tools inventory was independently
verified: 709 executed cases passed across 32 suites, with 60 declared platform
exclusions; all 33 CTest entries passed. Its three non-Windows producers passed.
The Windows producer compiled its targets but rejected a surviving versioned
package-manager executable. Inspection of the exact retained integration script
found its default post-build `z-applocal` hook. The observed temporary executable
path also matches the supplier's background metrics implementation; the child
command line and any completed network request were not captured. This is a
failed producer, with no candidate assembled or promoted. Static SDK consumers
now explicitly disable the unnecessary deployment hooks and metrics. The later
native producer, source and recovery verification recorded above passed with
those settings.

## Native process cleanup evidence

The strengthened Windows process test observes the exact descendant handle,
confirms Job Object membership and requires it to be signaled before termination
returns. This exposed a real cleanup race; an empty active-process count alone did
not prove that every observed child had finished. The implementation now pins and
joins descendant handles under one deadline, detects membership uncertainty and
preserves cleanup failures instead of reporting later success.

At `73f364feb08da1743fef52820ededd046bc801fd`, focused native diagnostics passed
20 complete repetitions on both
[Python 3.12.10](https://github.com/mirage335-colossus/software-foundation/actions/runs/37024667217)
and [Python 3.14.7](https://github.com/mirage335-colossus/software-foundation/actions/runs/37024672042).
Each run recorded 720 passed cases and 140 explicit Linux-only exclusions, with no
failed or internally skipped executed cases. Both complete inventories were
independently fetched and verified against the exact source hashes, interpreter
binary and version. These focused diagnostics establish the observed cleanup
behavior; they do not replace the complete release gates.

A later full candidate exposed two separate paths: delivered source tests assumed
a Git checkout, and a browser wrapper deleted its profile before all descendants
finished. The source fixture now creates its own temporary Git repository; the
production Git check remains intact. A discriminating source-archive check outside
all Git ancestors failed before the correction and passed afterward. Browser and
driver wrappers now own and join their inner process trees before copying logs or
removing profiles, with uncertain cleanup preserved as failure.

The focused [native Windows host diagnostic](https://github.com/mirage335-colossus/software-foundation/actions/runs/37041245500)
at `59ec5f6390d0fd8a8fe72172c153173b06597552` passed Firefox 156.0.1
automation and immediate profile removal. The compiler case failed and retained
the exact verified Job member: MSVC 14.44.35207 `vctip.exe`, observed executable
with wait state 258 after `cl.exe` exited. This identifies a compiler helper
lifetime issue; it is not a passing compiler or release qualification. The failed
bundle was independently fetched and all twelve consumed source hashes checked.

At `356e0cb29d8762ae6deddceb537bee9451945cad`, the corrected production
compiler path passed [one native diagnostic](https://github.com/mirage335-colossus/software-foundation/actions/runs/37044777895),
then twenty complete repetitions each on
[Python 3.12.10](https://github.com/mirage335-colossus/software-foundation/actions/runs/37045035782)
and [Python 3.14.7](https://github.com/mirage335-colossus/software-foundation/actions/runs/37045040414).
Each repeated run passed all forty cases without exclusions or internal skips.
Every compiler case actually terminated and joined the exact selected VCTIP helper
and verified x64 PE output; every Firefox 156.0.1 case completed automation and
immediate profile removal. Both bundles were independently fetched, with all
twelve consumed source hashes and complete case inventories checked. Their Windows
runner image was `20260927.320.1`. The compiler-specific helper policy preserves
strict completion for other commands; these diagnostics do not replace full
release qualification.

At `7abbdaaf3566ca733a88ff8551204b533cac0915`, explicit build owners
passed [one native check](https://github.com/mirage335-colossus/software-foundation/actions/runs/37060552322)
and twenty repetitions each on
[Python 3.12.10](https://github.com/mirage335-colossus/software-foundation/actions/runs/37061018594)
and [Python 3.14.7](https://github.com/mirage335-colossus/software-foundation/actions/runs/37061021979).
Each repeated run passed all sixty cases without exclusions or internal skips;
all thirteen consumed source hashes were independently checked. Every repetition
created two concurrent private PDB servers, pinned the control server's exact
handle, and proved it remained alive through the other owner's cleanup and a
second compile. Both owners then joined their selected helpers and immediately
released their output directories. The graphics compiler and Firefox cleanup
cases also passed. The selected toolset was MSVC 14.44.35207 on runner image
`20260927.320.1`. These results qualify the observed endpoint isolation and
cleanup behavior for these inputs; complete release certification remains a
separate gate.

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
Subsequent integration passed all 41 CTest entries in one invocation: 832 inner
Python cases passed, with two explicit native-Windows exclusions and no unexpected
skips. This includes 36 transport, 31 delivery, 24 signed-distribution, 20 browser
prerequisite and 13 opaque-preservation cases. Workflow syntax and documentation
checks passed. The distribution cases include actual signed packages, exact Git
source proofs, certificate replay and uncertain-creation recovery. The separately
added retention verifier passed all thirteen cases through its registered CTest
entry, with no exclusions or skips.

Candidate [36943440689](https://github.com/mirage335-colossus/software-foundation/actions/runs/36943440689)
passed all nineteen jobs at `fd646d616c129a6fede37e0ea7e7522d90565970`, including
concurrent draft transport and fresh Linux x64, Linux ARM64 and Windows x64 archive
consumers. GitHub permits duplicate draft tags: confirmed atomic tag creation now
selects the sole initializer, with bounded read-only visibility reconciliation.

Expanded candidate [36948123794](https://github.com/mirage335-colossus/software-foundation/actions/runs/36948123794)
passed at `2bd67a29dd3a6c3d91fbae32757bad29c3860797`, including the
signed-distribution suite and three native archive consumers. All nineteen jobs
passed: Linux x64 and ARM64 each recorded 784 passing Python cases, Windows x64
recorded 529, and no incomplete or skipped case outcomes were accepted. Platform
exclusions remain explicit. The distribution job passed 7 Debian, 17 Arch/Gentoo
and 24 publication cases plus the actual signed Bookworm client transaction.

All four exact legacy SDK imports passed at
`2332d31e77e5b632e3f7d8a7b5031153e794e9dc`: browser
[36942942745](https://github.com/mirage335-colossus/software-foundation/actions/runs/36942942745),
Linux ARM64 [36942949383](https://github.com/mirage335-colossus/software-foundation/actions/runs/36942949383),
Linux x64 [36942956015](https://github.com/mirage335-colossus/software-foundation/actions/runs/36942956015)
and Windows x64 [36942962164](https://github.com/mirage335-colossus/software-foundation/actions/runs/36942962164).
Each retained complete original proof bytes and emitted exact version-2 replay
identities; import establishes storage preservation, not new SDK qualification.
The full manifests and completed producer identities were independently checked.

Opaque preservation [36943434563](https://github.com/mirage335-colossus/software-foundation/actions/runs/36943434563)
retained 35 selected archives totaling 18,494,607,185 bytes in private draft bundles.
Independent [readback 36949071982](https://github.com/mirage335-colossus/software-foundation/actions/runs/36949071982)
passed for all 35 archives at `c2281bba00804bd7186f332098ff25576feded0a`.
The complete report and every receipt were fetched and bound to manifest asset
`604516921`, SHA-256 `94234661c4c45a96404f8115360cd5528d4df9d2216d833f4e6bcaef9a32feb4`.
After rechecking all original identities, a separately reviewed manual operation
deleted exactly those 35 originals and independently confirmed their absence.
The remaining API inventory contains 225 artifacts totaling 18,809,636 bytes,
with none at or above 1,000,000 bytes. The private preservation release retains
manual audit asset `604540708` (`cleanup-receipt.json`), SHA-256
`d834b495d696aa3ae42ad43ddc780d9a6d5f328d4cfe00789d57b03bf1a3f5f4`;
its complete uploaded bytes were independently read back. No workflow run,
unrelated artifact or preserved release bundle was deleted. No SDK recipe or
retained SDK group bytes changed in this update.

GUI source maintenance [36949360683](https://github.com/mirage335-colossus/software-foundation/actions/runs/36949360683)
retained the complete exact source group privately at
`8e0bd09bebf2fc16b35dd94750c7293a35ced1d9`; its bytes were independently fetched
and verified. The first host-browser gallery attempt passed its actual sandbox
and rendering preflight, then stopped because the restricted Wasm build path lacked
distro CMake. The repaired path installs ordinary host CMake/Ninja and explicitly
joins its authenticated virtual display. Thirty-three focused gallery cases passed,
with no skips, alongside actual local authenticated display, success/failure cleanup,
4 MiB log-cap and surviving-descendant rejection checks.

Hosted gallery [36951973933](https://github.com/mirage335-colossus/software-foundation/actions/runs/36951973933)
passed at `217ff90d01c25c419fc4e621515579f30668984e`. All seven actual surfaces
were independently downloaded, checksum-verified and visually inspected. FLTK,
Rev, SDL and framebuffer have closely matching layout; hosted web and Wasm agree
in widget geometry and appearance. The terminal preserves the shared controls
in its cell layout at 644 by 531 pixels; the other six images are 640 by 480.
The ordinary Chrome 154.0.8037.57 host passed namespace and seccomp sandbox
checks, and its authenticated 96-DPI Xvfb session reports joined cleanup.
Gallery manifest asset `604563666` has SHA-256
`9c9535b491791ade577c70a32b060b644bc40717d290f543e22efd361c7ad240`;
the separately verified private diagnostics bind the exact retained GUI selector
and contain no private display authorization file. `execute=false` retained
private evidence and a publication plan; it did not publish a public gallery.
At that revision, public base/application/certification/promotion execution was
a separate, unexecuted scope. See the current delivery record for later evidence.

Final candidate [36951980262](https://github.com/mirage335-colossus/software-foundation/actions/runs/36951980262)
passed all nineteen jobs at `217ff90d01c25c419fc4e621515579f30668984e`.
Linux x64 and ARM64 each passed 813 Python cases; Windows x64 passed 558.
All 33 screenshot fixtures passed on each native platform. Platform exclusions
were explicit, with no failed, skipped or incomplete case outcomes. The separate
distribution job passed all 48 cases and the actual signed HTTPS Debian client
transaction, including upgrade, tamper rejection and removal.

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
  kernels. The WebAssembly toolchain uses retained upstream binaries; its native source
  rebuild is not supplied by that recipe. Source availability is documented separately.
- At that baseline, GUI redistribution was blocked by unresolved upstream terms;
  the subsequently reviewed permission scope is recorded in [the GUI audit](gui-audit.md).
  Local compilation and tests do not approve binary redistribution.
- Arch and Gentoo client installation/update/removal require disposable native
  package-manager environments; their signed-channel fixtures are distinct
  evidence. The executed Debian client result is limited to its recorded host.
- SDK and gallery publication credentials were exercised as recorded above.
  Live signed package channels need their own native-client evidence. An adopted
  repository must qualify its own permissions and external services.
- Shared-source coordination requires the stated filesystem primitives and
  cooperative writers. Uncooperative participants need enforced private access.
- Real devices, assistive technology, every desktop/window-manager combination,
  long-duration operation and workload performance need separately specified checks.
  Passing this record is not a guarantee for every future feature or environment.
