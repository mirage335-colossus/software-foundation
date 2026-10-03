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

## Offline checkout and retained SDK inputs (2026-10-03)

The completed implementation snapshot before this validation entry has source-tree
SHA-256 `9eb82e3315aed150828944e24bebf80f82574eb0a07801a03bc96dc4e27ffab3`
(311 source files). It includes offline release-recovery verification, opt-in
CTest stop-on-failure, the complete retained GUI group, explicit `--gui` selection,
direct CMake fallback and the optional Windows host-tool bootstrap helper.
The GUI group contains exactly three files totaling 5,961,400 bytes.

A clean source export without Git metadata or an external GUI supplement passed
in a fresh network namespace with only loopback available:

- Default Release `test --full`: 53/53 CTest entries, with 1,274 Python outcomes
  passed and two explicitly excluded native Windows cases.
- Release `test --gui --gui-backends terminal,framebuffer,hosted-web --label gui`:
  23/23 CTest entries; all 59 included Python outcomes passed.
- Repeating the GUI command left every restored file's modification time unchanged
  and Ninja reported no work. Cold build plus tests took 75.675 seconds; the repeat
  took 6.665 seconds with two compile/test workers.
- Direct CMake with `FOUNDATION_BUILD_GUI=ON` and no source selectors configured
  successfully using checkout-contained inputs. Default core GUI support stayed off.

A five-sample warm hashing comparison measured approximately 6.4 milliseconds of
additional source-hash time per pass for the retained group on this host. This is
an observation with uncontrolled OS caching, not a cross-machine timing guarantee.
Documentation and whitespace checks passed. Publication review verified every
implementation file still matched this tested snapshot; only this validation
entry was subsequently added.

The native Windows bootstrap's eight opt-in diagnostics were not executed here;
its three original retained ZIP hashes/layouts and source were inspected. Fresh
stock Bookworm, FLTK/SDL/Rev execution, prepared Wasm consumers and native Windows
remain outside this local qualification. No SDK recipe, hosted test matrix or
ordinary-build dependency preparation changed. Detailed raw results remain under
`build/agents/checkout-sdk-independence-v1/`; this maintained summary preserves the
observed scope independently of ignored local evidence.

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
Latest was unchanged. Native signed-channel acceptance requires its own completed
client evidence, recorded separately below. A real signed two-backend fixture reproduced the exact
failure before the correction and passed afterward; the complete affected suite
passed all 30 cases without exclusions. Signature, retained-reference and package
validation remain intact.

The corrected publication run
[37089527346](https://github.com/mirage335-colossus/software-foundation/actions/runs/37089527346)
at `ab095d83f2dfa77caa11e303e1ae52d38530fe16` published the unchanged
certified application bytes in the signed x64 package prerelease
`distro-0.1.0-x86_64-r1-s1`. Its manifest identity is
`43eaa54dfab1cc1204b7d5e81172a6c6b4b08ce789901f46cc73de9eea46701f`.
Native Debian Bookworm, Debian Trixie and Ubuntu checks passed; Arch and Gentoo
failed after successful signature checks when reading decoded cleartext output.
Arch GnuPG 2.4.9-3 returned exactly one terminal LF fewer than the signed Release;
this was reproduced with the distribution verifier and its published patch.
Gentoo GnuPG 2.5.21 left the requested decoded filename absent, consistent with
its deferred named-output finalization. The failed run did not accept the channel.
Its immutable signed bytes are preserved. The later-discovered Gentoo recipe
defect described below means this revision remains permanently unaccepted; a
consumer-side correction cannot repair that signed payload.
The correction captures checked verifier stdout and allows only the observed
terminal framing LF difference while retaining both signatures and exact detached
content authentication. Ten affected cases passed with stock GnuPG; 59 APT, native
channel and distribution cases passed using the extracted official Arch verifier,
with no exclusions. The isolated verifier used the Debian host runtime with
Arch's matching private libassuan; this is not native Arch installation qualification.

Native-only requalification
[37095133010](https://github.com/mirage335-colossus/software-foundation/actions/runs/37095133010)
at `592ee7bb69c63e9eda4c30be5b161e870c1187cc` passed all three APT
clients. Arch passed signed-distribution verification, then failed strict process
completion after `pacman-key --init` returned while descendants remained alive.
This is separate from metadata verification and does not qualify native Arch
installation. Its retained failed evidence preserves the keyring initialization
output. The correction groups initialization, import and local trust in one
dedicated worker, shuts down only its container-owned GPG home, then joins every
adopted child before exiting. The outer strict supervisor is unchanged. Twelve
focused cases passed, including the original unmanaged-daemon failure, corrected
completion and an unrelated keyring whose same daemon identity remains usable.
That local regression does not replace native Arch package-manager qualification.
Gentoo passed signed-distribution verification and prepared activation, then its
first `emaint sync` failed on an unauthenticated metadata request with HTTP 403
rate-limit status. The existing verified generation was preserved. The retained
error does not identify the endpoint or rate headers, so it does not establish
whether a primary shared-IP quota or secondary limit caused the refusal. The
client already obtains asset bytes through public release URLs; a one-page exact
refresh needs six REST metadata requests, separate from those data transfers.
The bounded public retry correction passed 31 focused client cases, including
rate recovery, exhausted budgets, complete-pagination restart and preservation of
an actual signed active generation. Those local tests use controlled responses;
they do not establish that the hosted runner's public quota is available.

Native-only requalification
[37097683752](https://github.com/mirage335-colossus/software-foundation/actions/runs/37097683752)
at `1d96a7c1e30966074af867c8c596456b1ecb51c3` passed native Arch
and all three APT clients. Gentoo completed prerequisite installation but its first
public `emaint sync` rejected asset metadata; acceptance was skipped. Independent
metadata readback identified fourteen Debian filenames whose plus signs are
correctly percent-encoded as `%2B` in GitHub's public download URLs. The client
incorrectly compared those URLs against unencoded path components. A focused
regression reproduced the error before correction; all 32 public-client cases
passed after canonical component encoding, with no exclusions. The checks still
reject foreign, double-encoded, slash-substituted or query-modified URLs and verify
exact downloaded size/digest before activation. One fixture attempt placed a
private test key inside the checkout and correctly failed the key-location guard;
the complete successful run used an owned temporary root outside the checkout.
These local results do not relabel the failed native run or establish Gentoo
installation. The subsequent native-only run
[37099357741](https://github.com/mirage335-colossus/software-foundation/actions/runs/37099357741)
at `ecbc3eba735ae343158cf5eb3a2136f1199b2dea` passed the three APT
clients and Arch, then was cancelled before acceptance after the immutable
recipe defect below was identified. Its cancellation is not a qualification pass.

ARM publication
[37095147094](https://github.com/mirage335-colossus/software-foundation/actions/runs/37095147094)
at `592ee7bb69c63e9eda4c30be5b161e870c1187cc` completed package
preparation but GitHub rejected its first tag creation and failure retention with
HTTP 403 while primary quota remained positive. Independent authenticated readback
found neither its channel tag/release nor its transport tag/release. Default-branch
workflow bytes changed during preparation, which is consistent with GitHub's
[workflow-write permission restriction](https://docs.github.com/en/rest/releases/releases#create-a-release);
the retained response omitted the error message, so the exact cause is unproven.
No native qualification ran and no signed channel was published by this attempt.
The replacement uses the current workflow revision and preserves the certified
application inputs. Running replacements are not qualification evidence.

A subsequent upgrade-path review found that Arch payload checks alone could
accept unchanged installed files without proving a package-revision advance.
The correction queries every installed backend's native package version after
each round and rejects stale, duplicate, missing or foreign package records.
Acceptance also checks the exact requested predecessor tag and manifest digest.
All 14 focused native-checker cases passed without exclusions on the Linux host
with private GnuPG sockets available. An earlier sandboxed attempt could not start
the unrelated-keyring fixture and failed; it is not counted as passed coverage.
These regressions do not replace the required live two-revision native upgrade.

Inspection against Gentoo's EAPI 8 preparation contract found that the existing
schema-3 recipe omitted the required `eapply_user` call. A phase-invariant fixture
reproduced old-recipe failure and corrected schema-4 success. New production now
emits schema 4; complete schemas 1–3 inventory hashes are unchanged, and a real
signed schema-3 channel still replays exactly through the current verifier.
All 21 recipe and 31 distribution cases passed without exclusions. Native Portage
configuration also now names each selected package's exact license token rather
than an unsupported partial token glob; all 15 checker cases passed. The combined
recipe, distribution, checker and public-client snapshot passed all 99 cases with
no exclusions. These fixes
do not make the historical x64 r1 recipe installable: it remains unqualified for
Gentoo. A new immutable revision must establish the first successful installation,
followed by a newer revision for actual cross-frontend upgrade qualification.

Corrected x64 publication
[37100870828](https://github.com/mirage335-colossus/software-foundation/actions/runs/37100870828)
at `a3a214a88d61db2cf0e534830fccbad7ff9df4e0` published
`distro-0.1.0-x86_64-r2-s2`, with manifest
`d309a5902bac556b17f9a8e46ca5e40518dc4ca1bbcbf505a6d8537c53e587ee`.
All three APT checks and Arch passed. Gentoo synced the signed channel and
successfully prepared, installed into the staging tree and created the schema-4
core binary package. Its first native `emerge` then rejected Mesa's dependency on
`libglvnd[X]` because the minimal host's provider lacked that USE selection.
Acceptance was skipped; successful recipe preparation is not completed native
installation. This run left the signed revision unchanged and unaccepted.

A resolver-only comparison used the exact failed job's retained Gentoo stage3
and Portage image identities, the same five signed runtime atoms and strict
binary-only options. The baseline reproduced the `libglvnd[X]` refusal; adding
only `media-libs/libglvnd X` resolved 30 binary packages. The observed binary
index digest was
`9c00a3191248fbbf8308900031b784fd7ec34c8d7cd85acfa4eb891ac328df13`.
Both comparisons used the same private namespace root user/group accommodation
and joined all descendants. No dependency or application was installed or
compiled; this probe establishes dependency resolution, not native acceptance.
The focused checker suite passed all 16 cases with no exclusions, including
configuration ordering, preservation of unrelated settings and propagation of a
missing-binary failure.

Requalification
[37108497393](https://github.com/mirage335-colossus/software-foundation/actions/runs/37108497393)
at `cb2072c9384d9a3abdfd5081e2a1ccc4fdcd159a` subsequently passed all seven jobs
and accepted the same
[`distro-0.1.0-x86_64-r2-s2`](https://github.com/mirage335-colossus/software-foundation/releases/tag/distro-0.1.0-x86_64-r2-s2).
All three APT environments, Arch and Gentoo installed every selected variant,
verified exact payloads and self-checks, repeated the native update/refresh, and
removed the packages. Independent readback verified the signature, all five
native receipts and the exact acceptance marker. Comparison with the original
pre-qualification snapshot confirmed release ID `402367320` and all 70 asset IDs,
names, sizes and digests were unchanged. Packaging remains bound to
`a3a214a88d61db2cf0e534830fccbad7ff9df4e0`; qualification uses the later corrected
helper. Latest remains `402199557`. This is the first accepted x64 installation;
its receipts record `upgrade_from: null` and establish initial installation only.
The later r2-to-r3 upgrade evidence is recorded below.

The corrected Gentoo native step in
[run 37108497393](https://github.com/mirage335-colossus/software-foundation/actions/runs/37108497393)
passed in 48 minutes 23 seconds. Its two-revision path repeats the complete channel
verification and installation sequence. The upgrade-only Gentoo budget therefore
allows 150 minutes inside a 180-minute job; other scopes and individual native
verification command deadlines remain unchanged. A focused negative control with
the previous fixed deadline rejected the Gentoo upgrade case. The updated fixture
exercises timeout cleanup for all three frontend kinds, with and without a prior
revision; all 16 checker cases passed without exclusions. Workflow lint and
Python 3.9 syntax checks passed. No timeout failure is claimed for the completed
initial run, and a larger limit does not qualify an unexecuted upgrade.

The x64 r3 publication and upgrade run
[37112267197](https://github.com/mirage335-colossus/software-foundation/actions/runs/37112267197)
at `d8295ec1724ee1a8da26b4d07a22d9c5ed564cac` published the signed revision
`distro-0.1.0-x86_64-r3-s3`, manifest
`383f1bc7e510bc2a375d86ab3364adc7af6507e85d1a8af1bb6ddea170816a32`.
All three APT environments and Arch passed the actual r2-to-r3 upgrade. Gentoo
installed all seven variants at both native versions (`0.1.0-r1` then `0.1.0-r2`,
corresponding to channel package releases 2 and 3). Its fourth and final repository
sync returned HTTP 500 before the second round's payload/self-check verification
and removal. No complete Gentoo receipt was produced and acceptance was skipped.
This was a failed public read, not an execution-budget timeout. The exact failing
URL was not retained; the raw error shape is consistent with the public asset
retrieval path. Independent evidence review rehashed the complete failed bundle,
and remote readback confirmed the original r3 and accepted r2 inventories of 70
assets each were unchanged.

The public client now applies its bounded GET retry policy to transient server
responses on metadata and asset reads. An identical HTTP-500-then-valid-body
comparison failed with the old client after one GET and no destination; the
corrected client returned exact bytes after two GETs and closed the failed
response. The focused suite passed all 43 cases with
no exclusions: recovery and exhaustion for each selected HTTP status, full-page
restart, shared wait limits, whole-transfer deadlines, closed partial responses,
unchanged permission/origin/content checks and preservation of a real signed active
generation. These controlled cases do not qualify the incomplete native upgrade;
that requires a subsequent complete run against the unchanged signed revision.

The initial ARM64 signed channel
[`distro-0.1.0-aarch64-r1-s1`](https://github.com/mirage335-colossus/software-foundation/releases/tag/distro-0.1.0-aarch64-r1-s1)
was accepted by
[run 37098054299](https://github.com/mirage335-colossus/software-foundation/actions/runs/37098054299),
with all seven jobs successful. Packaging and qualification both used
`1d96a7c1e30966074af867c8c596456b1ecb51c3`; the signed manifest is
`dac4345be2d503ace832a53972cd8f7d647131a3ce54ee8d607072f819694152`.
Native Debian Bookworm, Debian Trixie and Ubuntu 24.04 each installed every selected
backend, checked exact payloads and self-checks, refreshed repeatedly and removed
the packages. Independent readback verified the trusted signature, all 70 remote
asset identities, all three native receipts and their exact acceptance marker;
the application's Latest release remained `402199557`. Hosted jobs replayed the
complete payload; the independent readback checked signed controls and retained
native evidence. This initial installation records `upgrade_from: null` and does
not establish a version upgrade. ARM64 Arch/Gentoo frontends remain outside the
native matrix.

The subsequent ARM64 channel
[`distro-0.1.0-aarch64-r2-s2`](https://github.com/mirage335-colossus/software-foundation/releases/tag/distro-0.1.0-aarch64-r2-s2)
passed all seven jobs in
[run 37103102371](https://github.com/mirage335-colossus/software-foundation/actions/runs/37103102371)
at `a3a214a88d61db2cf0e534830fccbad7ff9df4e0`. Its signed manifest is
`57d7632206b6a329d386a1b954d08a396acc2949291b578e19c5506d04966544`.
Every APT environment installed and checked all seven variants at `0.1.0+r1`,
upgraded them to `0.1.0+r2`, repeated the refresh/install operation, checked exact
payloads and self-checks, then removed them. The exact accepted r1 tag and manifest
are recorded in every upgrade receipt. Independent readback and peer review
reconciled both 70-asset inventories, signatures and native receipt identities;
application/SDK input identities were unchanged, and Latest remained `402199557`.
This establishes the observed ARM64 APT version upgrade.

Native-only requalification of
[`distro-0.1.0-x86_64-r3-s3`](https://github.com/mirage335-colossus/software-foundation/releases/tag/distro-0.1.0-x86_64-r3-s3)
subsequently passed all seven jobs in
[run 37121695761](https://github.com/mirage335-colossus/software-foundation/actions/runs/37121695761)
at `6b911833bc6e2eb17058bb1e65d1eb6b0e701968`. Its original packaging revision
remains `d8295ec1724ee1a8da26b4d07a22d9c5ed564cac`, and its signed manifest
remains `383f1bc7e510bc2a375d86ab3364adc7af6507e85d1a8af1bb6ddea170816a32`.
Debian Bookworm, Debian Trixie, Ubuntu 24.04, Arch and Gentoo each installed and
checked all seven variants from accepted channel r2, upgraded to r3, repeated
repository refreshes, verified exact package versions, payloads and self-checks,
then removed the packages. APT repeated exact-version installation requests;
Arch repeated `pacman -Syu`.
The native version transitions were `0.1.0+r2` to `0.1.0+r3` for APT,
`0.1.0-2` to `0.1.0-3` for Arch, and `0.1.0-r1` to `0.1.0-r2` for Gentoo.
Every receipt binds the exact accepted r2 tag and manifest recorded above.

Independent readback verified both trusted signed manifests, complete remote
asset inventories, all five native receipts and the exact acceptance marker.
Comparison with the original r3 publication snapshot confirmed all 70 asset IDs,
names, sizes and digests were preserved. A further readback confirmed the accepted
r2 predecessor's 70 assets and the application's Latest release `402199557` with
all 25 assets were unchanged. It also rechecked source tags and release bodies.
Hosted native jobs replayed full payloads; this independent audit checked signed
controls, retained execution evidence and remote metadata without repeating the
multi-gigabyte payload replay locally. Application and SDK input identities were
unchanged by these package revisions.

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
A fresh API inventory on 2026-10-03 at 11:11 UTC confirmed 225 artifacts totaling
18,809,636 bytes; the largest was 461,803 bytes, with none at or above 1,000,000
bytes. The private preservation release retains
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

## Development speed validation

The development-speed changes were checked from an isolated source snapshot on
2026-10-03 with the installed Linux x86-64 compiler and distribution tools. All
50 native CTest entries passed, including 1,138 applicable cases in the registered
unit suites. Two explicitly native Windows cases were excluded on Linux. The
first sandboxed build/check run took 32.77 seconds and passed 45 entries; its five
signing suites could not start GPG's Unix sockets. Those same frozen fixtures
passed in 10.57 seconds when local sockets were permitted. They use disposable
keys and mocked remote services, with no package installation or publication.

A real configure-only candidate followed by a scoped core build/check took
1.88 seconds. Its complete plan identity remained unchanged after compilation.
The tools prerequisite target built no application executables. A separately
archived baseline release/fast build with two compile and two test jobs took
6.29 seconds; these are different selected scopes, not a same-workload speedup
ratio. Documentation validation, Python parsing, workflow lint and whitespace
checks passed.

Accounting against a retained signed x86-64 channel reduces native fetch from
3,728,405,200 bytes across 70 assets to 165,787,187 bytes across four assets
(95.55% less). An unchanged refresh transfers 209,337 bytes of signed controls
and revalidates its stored channel. This is an inventory-derived transfer count,
not a hosted elapsed-time measurement. Full publication/recovery retains the
complete inputs. Complete all-GUI certification still requires 106 logical
checks and 66 physical operations, scheduled as 23 scope-separated batches with
up to eight running concurrently.

The updated workflows have not yet been timed or qualified on hosted Windows,
ARM64 or browser runners. Their local validators and fixture coverage do not
replace those execution environments. The archived-builder compatibility path,
missing remote digests, tampered selected payloads, failed refresh preservation
and rejection of partial native acceptance were exercised locally.

## Transfer and scheduling follow-up validation

A further isolated native run on 2026-10-03 configured, compiled and exercised
51 CTest entries in 40.81 seconds using eight compile jobs and two test jobs.
Integration exposed two outdated workflow contract expectations and one retry
fixture that reached its request deadline before its intended wait-budget limit.
Those fixtures were corrected and only the two affected suites were rerun:
23 workflow-storage cases and 44 signed-client cases passed. Combined with the
unchanged production-code results, all 1,198 applicable registered unit cases
passed; two explicitly native Windows cases remained excluded on Linux. The
native application, install consumer, documentation, workflow lint, Python syntax,
whitespace and generic-name checks passed. Signing fixtures used disposable keys
and local sockets with mocked remotes; no packages were installed or published.

A one-page transport fixture measured 12 metadata reads for eight grouped bundle
fetches, versus 96 when fetched separately. Eight-bundle publication used 18
metadata reads on creation and 16 on an identical retry. These counts exclude
asset downloads/uploads and initialization POSTs; real pagination adds requests.
Exact scope selection, changed identities, collisions, failed parallel transfers,
immutable retries, compression bounds, and joined workers were checked. The
production upload path uses a validated release ID without another tag lookup.
Success diagnostics retained controls and receipts; failed-publication selection
retained complete prepared payloads.

These results do not measure hosted throughput, real Docker bootstrap reuse,
Windows/ARM64 execution, cold SDK construction or complete GUI/browser operation.
The full release still retains required recovery inputs and can exceed one shared
API quota window. Reduced byte and request counts are structural improvements,
not a claim that a particular hosted elapsed time has been achieved.

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
- Signed-channel initial installation and actual version upgrades passed on x64
  Debian Bookworm, Debian Trixie, Ubuntu 24.04, Arch and Gentoo, and on ARM64
  Debian Bookworm, Debian Trixie and Ubuntu 24.04, as recorded above.
  Arch/Gentoo native checks are scoped to x64; generating their ARM64 recipes
  does not qualify those frontends. Historical x64 r1 remains unaccepted.
- SDK, gallery and signed-channel publication credentials were exercised
  as recorded above. An adopted repository must qualify its own permissions,
  signing trust and external services.
- Shared-source coordination requires the stated filesystem primitives and
  cooperative writers. Uncooperative participants need enforced private access.
- Real devices, assistive technology, every desktop/window-manager combination,
  long-duration operation and workload performance need separately specified checks.
  Passing this record is not a guarantee for every future feature or environment.

## October 2026 development iteration and direct certification inputs

The next optimization pass was qualified from an isolated copy of the working
source based on `5cda8ec5cd887d73b387243668f317aa7f4093b5`. All **52 CTest
entries passed**, including **1,235 applicable unit cases** and two explicitly
inapplicable native Windows cases on the Linux host. The complete case inventory
and exclusions were identical in the two-worker and four-worker runs.

| Native Release scope with distribution fixtures | Two test workers | Four test workers |
| --- | ---: | ---: |
| CTest elapsed time | 42.16 seconds | 24.67 seconds |
| Configure/build/test wrapper | 43.516 seconds | 25.131 seconds |

CTest used approximately **41.5 percent less elapsed time**, or **1.71 times the
throughput**, in this single comparison. Compilation used eight jobs; the second
run reused the configured build. Comparing CTest separately excludes that build
warmup difference. The resource detector selected four automatic test workers on
this host; smaller CPU/memory budgets still select fewer. These are local native
measurements, not hosted, GUI SDK or cross-platform release timing.

The first four-worker run exposed a new aggregation fixture that mocked away its
working-directory change and left output outside its temporary tree. Only the
fixture was corrected: it now uses its real temporary directory, restores the
caller directory, and checks all three written summaries. Its complete 26-case
suite passed twice from the same working directory, then the complete four-worker
run passed. Production behavior and test inventory were unchanged by that repair.
Signed fixtures required permission to create disposable local GnuPG sockets;
the sandbox denied that prerequisite before signed assertions in the first
focused attempt. The permitted local run passed using fake GitHub transport.

Focused transport, release, distribution, source-identity, build-capacity, change
selection and direct-input tests cover hashes, remote mutation, missing scopes,
failed uploads, late destination collisions and fresh consumer boundaries.
All workflow files passed the retained validator; documentation, Python syntax,
whitespace and generic-name checks passed.
No commit, push, hosted dispatch, real package installation or public release was
performed during this pass.

Certification now retains authenticated controls and fetches selected original
published inputs directly. For the retained roughly 3.5 GB candidate this avoids
approximately 7 GB of intermediate download/reupload traffic. The request model
estimates about 70 fewer metadata/bundle requests plus roughly 20 preparation
payload downloads, rather than assuming every saved byte removes an API request.
Each batch still independently verifies complete public release identity. Quota
stalls remain possible; the next hosted run can account for actual responses,
transferred bytes and waits through sanitized process metrics.

Exact source identities, test reports, fixture correction, request-model references
and measurement limits are retained in
`build/agents/development-speed-v3/final-validation.json`. Full hosted duration
remains unmeasured. Target-specific signed distribution recovery inventories,
per-format signed projections and a new private transport trust protocol were
not introduced; their compatibility and identity contracts require separate work.


## Bounded evidence artifacts and lower transport cost

The 2026-10-03 transport pass replaces the blanket Actions-artifact prohibition
for selected small regression and certification evidence. The complete selection
is limited to 62 immutable slots per run attempt, at most 2 MiB each, with one-day
retention. Oversized bundles and failed artifact uploads preserve complete release
fallback. SDK/application archives continue to use release storage. Downloads
verify context, actual producer identity/completion, whole archives and all member
hashes; corrupt artifacts cannot silently fall back. Mixed inputs remain private
until every selected input passes. Historical cross-run transport keeps its
stricter checks.

The same 23-batch model estimates roughly **1,650 to 610 transport API calls**,
about **63% fewer**, including the large combined certificate's release fallback.
This excludes Actions runtime storage traffic, public SDK/release operations,
initial draft creation, pagination and retries. It is not a hosted measurement or
a guarantee of staying within one quota window. Retained evidence is about 9 MB
compressed in total; representative individual reports are about 257 KB and
seven-backend groups about 1.8 MB. The complete certificate appropriately exceeds
the small-artifact cap and remains in release storage.

Local archive qualification now combines inventory with extraction or small
build-record inspection: a native archive check uses three application archive
decompression passes instead of six and removes two complete temporary package
extractions. All backend checks and final payload verification remain. Source and
recovery testing uses the wrapper's resource-aware worker default independently
of compile parallelism.

The final isolated source snapshot passed **53/53 CTest entries**, including the
optional signed distribution fixtures, in **33.32 seconds** with eight compiler
and four test workers. Its receipts account for **1,269 passed Python cases** and
two explicit native-Windows exclusions on Linux. Workflow lint, Python 3.9 grammar,
documentation and whitespace checks passed. An initial 47/48 native pass exposed
one fixture that asserted the old workflow transport layout; its replacement
asserts bounded control publication and preservation of evidence/prerequisites.
The final run includes that corrected test and all five optional distro suites.

The source manifest, receipts and limitations are retained in
`build/agents/artifact-speed-integration-v1/validation.json`; the detailed request
model is `.agent-work/artifacts/release-api-v4/request-model.json`. No hosted run,
public release, push or SDK rebuild was performed. Actual all-platform wall time
and account quota use remain to be measured on the next ordinary hosted run.


## Native routine transport and shared public discovery

The later 2026-10-03 simplification supersedes the preceding 62-slot storage
policy and 750–1,150 complete-release request estimate. Routine application,
package, source and certification handoffs now use native Actions artifacts.
The full certificate fits a dedicated 16 MiB slot; all 79 available slots total
at most 370 MiB of content per attempt, plus outer archive overhead. SDK archives
remain in release storage, including during preparation-only application runs.
There is no automatic private-release fallback in routine workflows.

Same-run consumers trust exact executing Actions context, immutable artifact
names and explicit workflow dependencies, then verify complete local bytes.
Certification shares one frozen public inventory. Offline transport fixtures
confirm that the retained 23 public certification batches need no authenticated
REST requests for their 87 payload acquisitions. Published-release boundary
checks, complete first-publication byte readback and strict historical replay
remain. A bounded independent review found no actionable issue in credential-free
public redirects or context-bound frozen controls.

The final applicable local coverage is **54 CTest entries**, including all five
optional distribution suites, with **1,301 passed Python cases** and two explicit
native-Windows exclusions on Linux. The isolated full run took **30.91 seconds**:
52 suites passed and two failed because fixture expectations still described the
old workflow transport or release-list endpoint. Only those fixtures changed;
their signed-byte, isolated-consumer and active-generation assertions remain.
Both affected suites then passed in **6.29 seconds**. Unchanged production source
and the other 52 passing suites were not rerun. Earlier affected checks also
caught an old step-title assertion and a repository-visibility mock omission;
the final complete coverage includes their corrected contracts.

All workflow files passed actionlint. Documentation validation, whitespace checks,
117 Python files parsed with Python 3.9 grammar, and the generic-name scan passed.
The tested snapshot matches implementation source; only final explanatory
documentation changed afterward. Reports and exact source hashes are retained in
`build/agents/transport-simple-integration-v1/validation.json` and its source
manifest. Signed local fixtures used disposable GnuPG sockets and fake remote
transport; no hosted job, public upload, SDK rebuild, commit or push was performed.

The [current request accounting](development-speed.md#account-for-the-actual-critical-path)
models **255 primary-quota operations** for a complete public warm-SDK release,
or **201** when temporary artifacts expire instead of being deleted immediately.
This includes 53 artifacts and 54 cleanup calls. Approximately 29 quota-preflight
HTTP requests and native artifact/public download traffic are additional network
operations. Authenticated graphics URLs can add eight quota operations; private
repositories, retries, extra pages and cold publication cost more. Cleanup spaces
its 53 deletions over at least 52 seconds, after the final consumer, and never
waits for a quota reset. Failed runs keep one-day diagnostics.
These are code-derived costs, not a newly measured hosted duration or quota result.


## Delete larger handoffs at their last consumer

The next 2026-10-03 pass replaces whole-attempt cleanup with direct upload IDs.
Source and application archives are removed after verified candidate publication
and its delivery receipt; the certificate is removed after verified attachment
and its receipt. Each regression package is removed after its fresh-package check.
Small receipts and diagnostics expire after one day. Preparation-only application
outputs and failed-consumer handoffs remain available; `preserve_artifacts=true`
reaches all nested consumers and disables early deletion.

Cleanup performs one DELETE per unique supplied ID, with no inventory listing,
quota probe, retry, or quota-headroom wait. Empty arrays perform no remote work;
missing, malformed and partially invalid arrays fail before any mutation. Distinct
matrix outputs preserve all target IDs; the assembly selector requires the exact
core or all-GUI target set and rejects missing, duplicate or foreign IDs. Cleanup
runs after the final receipt upload so a receipt failure preserves rerun inputs.
Independent job scheduling and all qualification gates remain intact.

All **68 affected offline tests passed in 1.801 seconds**. The isolated complete
native regression, including all five optional distribution suites, then passed
**54/54 CTest entries in 29.69 seconds**. After the final receipt/cleanup ordering
adjustment, the three affected workflow suites passed again in **1.16 seconds**;
unchanged suites were not repeated. Final receipts contain **1,303 passed Python
cases**, with two explicitly inapplicable native-Windows cases on Linux.
Workflow lint, documentation, whitespace, Python 3.9 grammar and generic-name
checks passed. Independent read-only review found no actionable issue in matrix
ID propagation, final-consumer barriers, preservation or permission inheritance.

The complete public warm-SDK all-GUI request model is now **210 quota-counted
operations**, including nine targeted deletions, compared with 255 including the
previous 54-call cleanup. Explicit preservation remains 201. Approximately 29
primary-unmetered quota probes and Actions/public-download network traffic remain.
The five-item publication cleanup uses four seconds of deliberate mutation spacing;
the three package deletions and certificate deletion are single-item operations.
Small retained artifacts expire without cleanup API calls. These are code-derived
costs, not newly measured hosted latency or quota consumption.

The final source manifest, full-run manifest, receipts and logs are recorded in
`build/agents/artifact-consumer-integration-v1/validation.json`. Only final validation
documentation changed after the tested snapshot. No hosted workflow, actual remote
artifact deletion, public upload, SDK rebuild, commit or push was performed.


## Manual repository artifact cleanup

The 2026-10-03 manual maintenance addition deletes a frozen, fully paginated
Actions-artifact inventory while preserving workflow runs, normal logs and release
assets. Before deleting, it checks all five active workflow statuses and refuses
other runs. This observation does not lock out future workflow starts. Deletion
has one-second spacing, no mutation retry or quota wait, a 25-minute loop budget,
and confirmed count/byte reporting. It is not called by routine development jobs.

All **15 focused offline helper tests passed**. The isolated integrated native
suite, including all five optional distribution suites, passed **55/55 CTest
entries in 30.57 seconds**, with **1,319 passed Python cases** and two explicitly
inapplicable native-Windows cases on Linux. Coverage includes complete pagination,
all busy statuses, changing or malformed inventories, duplicate IDs, partial
failure, real transport handling of a 404, exact request counts, bounded progress,
and deadline reporting. Workflow lint, documentation validation, whitespace,
119 Python files parsed with Python 3.9 grammar, and the generic-name scan passed.
Independent read-only review found no actionable issue.

Exact source hashes, local receipts and the log are recorded in
`build/agents/manual-artifact-cleanup-v1/validation.json`. Only this validation
record changed after the tested source snapshot. No hosted workflow, remote
artifact deletion, commit or push was performed. For a nonempty inventory of
`N` artifacts, the normal API cost is `N + ceil(N / 100) + 5`; an empty inventory
requires one GET. This optional maintenance cost does not change routine release
request accounting.


## Share SDK metadata within assembly

The next 2026-10-03 change batches assembly's four SDK recipes behind one complete
in-memory base-release inventory and one fresh final reconciliation. Downloads
and group verification retain four-worker parallelism. Every file still passes
its size/hash and SDK checks. All groups stay in temporary staging until the
whole batch succeeds. There is no additional workflow job, artifact upload,
cross-job metadata handoff or persistent cache.

Release clients reuse valid core-quota response headers for up to 30 seconds,
with conservative local write admissions. Fallback probes are serialized within
the client and bounded by the existing request deadline, including lock wait.
A fresh adequate probe can admit a write despite a lower local estimate, avoiding
an unnecessary reset wait. Unknown or stale observations retain fallback checks;
failed mutations are never replayed.

The isolated full native regression, including all five optional distribution
suites, passed **55/55 CTest entries in 30.56 seconds**, with **1,338
passed Python cases** and two explicit native-Windows exclusions on Linux.
The 19 new cases cover exact batch request counts, four simultaneous transfers,
changed metadata, corrupt bytes, staging cleanup after joined workers, workflow
ordering, header reuse, concurrent fallback, stale observations, bounded waits,
and uncertain mutations. Workflow lint, documentation, whitespace, Python 3.9
grammar for 119 files and the generic-name scan passed. Independent read-only
review found no actionable issue.

The public warm-SDK complete-release model falls from 210 to **189 quota-counted
requests**, or **180** with preservation. Assembly metadata reads fall from 28
to seven for four recipes and one-page inventories. The former 29 quota-probe
requests become conditional fallback traffic; there is no guaranteed fixed count.
These are code-derived savings, not hosted measurements. Evidence and exact source
hashes are retained in `build/agents/sdk-metadata-batch-v1/validation.json`.
Only this validation documentation changed after the tested snapshot. No hosted
workflow, real remote operation, SDK rebuild, commit or push was performed.


## Portable qualification commands

The 2026-10-03 incremental extraction provides file-based plan, list, prerequisite
and execution commands through `tools/qualification_tasks.py`. The core planner
requires no provider files or GitHub context. Hosted scheduling, authenticated
transport and publication stay in their adapter. Browser receipts now bind to
explicit plan/check/run/attempt values supplied only to supervised children.
The all-GUI coverage remains **106 logical checks, 66 physical executions and
23 hosted batches**, with grouped work, selective payloads and full diagnostics.

The isolated final native regression, including all five optional distribution
suites, passed **56/56 CTest entries in 31.55 seconds**, with **1,357 passed Python
cases** and the same two explicit native-Windows exclusions on Linux. The 19 new
cases cover provider-free planning and real child execution, altered input and
identity rejection, grouped report inventory, explicit browser setup and hosted
boundary delegation. An initial full run exposed a missing receipt-parent creation
and an outdated writer mock; the old behavior was restored, the fixture updated,
and all 22 affected cases plus the complete final suite passed without removing
assertions. Workflow lint, documentation, whitespace, Python 3.9 grammar for 122
files and the generic-name scan passed. Independent integration review found no
actionable issue before that final tested compatibility repair.

Exact source hashes, reports and retained failure/final logs are recorded in
`build/agents/portable-qualification-v1/validation.json`. Only this validation
record changed after the final tested snapshot. No hosted workflow, real remote
API operation, SDK rebuild, commit or push was performed. This extraction adds
no artifact handoff or API request: the existing public complete-release model
remains **189**, or **180** with preservation. These local tests establish the
command boundary and preserved contracts, not a new hosted elapsed-time result
or qualification of another provider's runners and transport.


## Restore SDK overlap and certification concurrency

The next 2026-10-03 change starts verification of each fully downloaded SDK while
other SDK downloads continue. Separate pools retain at most four transfer workers
and four verification workers. Both pools finish before failed staging cleanup;
all verification and the final shared remote reconciliation must pass before the
output directory becomes available. The four-recipe metadata cost remains seven
reads, with no additional transfer, artifact or persistent cache.

Certification now makes every planned batch eligible by default: all 23 batches
for the current all-GUI policy. The repository Actions variable
`FOUNDATION_CERTIFICATION_JOBS` optionally caps jobs for constrained runner pools;
unset or `0` uses the actual matrix count. Invalid values fail before remote input
acquisition. Runner/account availability still controls actual concurrency. Batch
identity, artifact slots, coverage and publication gates remain unchanged.

The final isolated native regression, including all five optional distribution
suites, passed **56/56 CTest entries in 30.96 seconds**, with **1,364 passed Python
cases** and two explicit native-Windows exclusions on Linux. Seven new cases cover
real thread ordering for overlapping download/verification, independent worker
bounds, joining writers after failure in either stage, full-matrix/default and
lower-cap scheduling, invalid settings and empty matrix rejection. Existing exact
API-count, tamper and output-publication checks also passed. Focused runs passed
105/105 SDK delivery cases and 38/38 workflow storage cases. Independent read-only
review, workflow lint, documentation, whitespace, Python 3.9 grammar for 122 files
and the generic-name scan passed.

Exact source hashes and reports are recorded in
`build/agents/concurrency-restore-v1/validation.json`. Only this validation record
changed after the tested snapshot. No hosted workflow, real remote API operation,
SDK rebuild, commit or push was performed. The public complete-release estimate
remains **189 requests**, or **180** with preservation. Greater job concurrency
changes request timing, not its normal total; hosted elapsed-time improvement and
burst behavior require observation during an ordinary run.


## Restore audited development and portability gaps

The 2026-10-03 implementation adds complete explicit test prerequisites. Planning
requires no compilation in registered builds, ordinary shards compile only their
selected targets, and script-only selections invoke no build. Candidate core
ownership still includes enabled GUI tests. Missing declarations and changed
inventories fail instead of silently reducing coverage. Deferred directory-local
label collection preserves the CMake 3.24 baseline; the optional Rev module probe
separately requires CMake 3.28+ and a suitable installed module compiler.

Explicit prior-attempt adoption preserves original successful receipts, attempt
numbers, hosts and evidence bytes. Qualification, certification, certificate
bundling and independent remote reconstruction validate that selection. Ordinary
mixed-attempt aggregation still fails. Existing hosted workflows do not yet
acquire and authenticate earlier-attempt artifacts automatically; this addition
provides the explicit local/alternative-scheduler command and consumer boundary.

The isolated native regression, including all five optional distribution suites,
passed **58/58 CTest entries in 30.26 seconds**, with **1,396 passed Python cases**
and two explicit native-Windows exclusions on Linux. Terminal, framebuffer and
hosted-web GUI checks passed **25/25 entries in 5.08 seconds** using the unchanged
retained GUI group. Address/undefined-behavior sanitizer core checks passed **2/2**
with leak detection enabled. The small actual Rev probe compiled four pinned
production modules and passed both comparison/layout cases with Clang 19 in
**6.21 seconds**; its 16 helper cases also passed in the native suite.

Final review preserved the existing application-wide static-archive symbol hiding;
installed consumers receive narrower GNU-runtime hiding so their own archive APIs
remain available. After that localized correction, a fresh isolated portable
Release archive build passed, core checks passed **2/2**, and the installed consumer
plus runtime/plugin integration passed **2/2 in 5.04 seconds**. The runtime fixture
includes bundled-shared and exported-static negative controls, relocated execution,
installed library consumption and stale-header-probe rejection. Other implementation
bytes are unchanged from the preceding native/GUI/sanitizer runs and were not
needlessly retested. Exact snapshot differences are retained with the results.

The first full run exposed an extracted GUI CMake fixture missing the new helper;
loading the actual helper repaired it without changing its assertions. A separate
review caught and removed a CMake 3.28-only property API. GnuPG socket setup and
LeakSanitizer failed under the execution sandbox; discriminating native runs
confirmed those restrictions, and the affected checks passed with local sockets
and normal process inspection available. No signing or sanitizer checks were
weakened. Workflow lint, documentation, whitespace and Python 3.9 grammar for
126 source files passed.

Evidence, commands and exact source hashes are recorded in
`build/agents/audit-integration-v1/validation.json`, with frozen source manifests
and retained failure/final logs below that directory. Only this final validation
record changed after the final source snapshot. Native Windows wide-argument
conversion is registered but was not executed locally; ARM64, Wasm, FLTK/SDL/Rev
native surfaces and actual hosted workflows were not rerun. CMake 3.24/3.25 was
reviewed for API compatibility, not executed on this host. No SDK rebuild, dependency
acquisition, remote publication, commit or push was performed. These checks do not
establish a new hosted elapsed-time measurement or broaden the existing platform
support claims. Internal case/seed partitioning remains conditional on measured
need; current complete CTest-level parallelism is retained.
