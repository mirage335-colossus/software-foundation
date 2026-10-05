# Resource-aware verification and hosted release qualification

Implementation commit `3d1ba14` adds resource-aware nested test budgets, isolated
Linux certification cases, bounded initial release discovery recovery and proper
Python module-fixture registration. Existing CPU/RAM growth headroom, complete
inventories, provider selection and publication gates remain in place.

Local verification on 2026-10-05 passed 66 complete tooling suites: 1,855 cases
with three explicit platform exclusions. Five signing suites initially failed
because the sandbox blocked GPG's helper; their complete reruns with the required
process access passed. A new serial-case regression initially assumed no inherited
CTest environment; its behavior-based correction passed all 116 CI-plan cases
under a one-worker inherited budget. Earlier failed receipts remain preserved.
The fresh supported-wrapper Rust core build passed four cases, the headless editor
passed all ten suites, actionlint passed all 21 workflows, and documentation and
whitespace checks passed. Exact local receipts and file hashes are in
`.agent-work/artifacts/further-root-20261005/local-validation.json` and the
corresponding focused workstream directories. Docker is absent locally; fresh
container mount and cleanup behavior still requires hosted qualification.

The user explicitly authorized the `main` push and complete hosted qualification
on 2026-10-05. Implementation and its local evidence were pushed as
`946007da9328e78cdc1380cd0238c9740f435042`.
[Development feedback 37351942831](https://github.com/mirage335-colossus/software-foundation/actions/runs/37351942831)
passed: all application/GUI/tooling jobs at attempt 1, and the failed validator
job at attempt 2 after restoring its deleted retained prerequisite. The new
[immutable validator mirror](https://github.com/mirage335-colossus/software-foundation/releases/tag/ci-tools-actionlint-1.7.12-20261005)
retains the exact reviewed upstream binary, source, MIT license and provenance;
all five assets passed byte-for-byte readback. No validator was rebuilt locally.

Early native Windows diagnostics at that same source passed without exclusions
or skips: [planner run 37352186436](https://github.com/mirage335-colossus/software-foundation/actions/runs/37352186436)
passed 54 cases and [orchestration run 37352211039](https://github.com/mirage335-colossus/software-foundation/actions/runs/37352211039)
passed 116. Complete retained bundles were authenticated and SHA-verified. These
diagnostic receipts do not replace full release qualification.

[Screenshot run 37352058694](https://github.com/mirage335-colossus/software-foundation/actions/runs/37352058694)
passed all three jobs on the same source and published the exact ten-file Rust
native/Wasm gallery as `screenshots-37352058694-attempt-1`. Its manifest, digests,
run/source binding and seven actual surfaces were verified; README integration is
`2371ad4d820073919f7c38c68d3785ec2eaae632`. It retains the original capture source.

Earlier completed prerequisite: GUI maintenance
[37350603497](https://github.com/mirage335-colossus/software-foundation/actions/runs/37350603497)
passed on `d516febe135066c811860e3a40968224f74913f1`, publishing the then-selected GUI
group `2dcef6393d9ad9a4c41c8a819f3e836ace78af4c19eb4be7496b9ca41fac78cd`.
All four C++ and four Rust retained groups remain available. The supported
maintenance helper retired only the verified superseded GUI slot; it did not
rebuild SDKs or retire unrelated SDK groups.

Both legacy predecessor workflows completed at attempt 1: x64
[37352060627](https://github.com/mirage335-colossus/software-foundation/actions/runs/37352060627)
passed all nine jobs and five native frontends; ARM64
[37352082640](https://github.com/mirage335-colossus/software-foundation/actions/runs/37352082640)
passed all seven jobs and three native frontends. Protected acceptance, trusted
signatures, complete unchanged 82-asset inventories and direct tag/source binding
were independently verified. Their application bytes remain the old certified
`release-37245250573-attempt-1`; packaging source remains `946007d`. Neither became
Latest. The accepted r5/s5 selectors and signed manifest digests are retained in
`.agent-work/artifacts/further-release-audit-20261005/accepted-predecessors.json`.
They establish initial native channels, not upgrades from deleted historical tags.

Full Latest run
[37358862485](https://github.com/mirage335-colossus/software-foundation/actions/runs/37358862485)
on `2371ad4` failed before builds or candidate publication: the complete all-GUI
source handoff exceeded its 24 MiB slot. Exact local reproduction measured
27,277,415 bytes including manifest and recipes. The generated documentation
explorer accounts for the growth. The repair increases only the source slot to 40 MiB, preserves complete source
and strict fallback policy, and recalculates storage operating examples while
retaining at least 100 MiB private Free reserve.
Source budget evidence is in `build/further-capacity-source-budget-20261005/`.
The unsuccessful run and its skipped downstream stages are not qualification.

The capacity repair was pushed as `b6d192d`; development feedback
[37359628830](https://github.com/mirage335-colossus/software-foundation/actions/runs/37359628830)
passed all four jobs. Fresh Latest
[37359677255](https://github.com/mirage335-colossus/software-foundation/actions/runs/37359677255)
passed source handoff and nineteen jobs, but application production and Windows
tooling failed before publication. Linux x64, ARM64, Wasm and Windows tooling
logs identified an undeclared PyYAML import in the cleanup workflow wiring test.
Its repaired standard-library wiring checks pass all 21 cases with site packages
disabled and reject eleven unsafe workflow mutations. Windows application diagnostics
also exposed a mocked assembly fixture inheriting `PACKAGE_REPOSITORY=true`;
explicit fixture isolation passed all 39 workflow-storage cases under that hostile
ambient setting. Production package gates remain unchanged. The real FLTK failure
was traced to three inbound native focus handlers overwriting retained focus while
a prompt closed. The repaired native fixture and supplier checks passed 2/2 with
Rust and a retained SDK; the final teardown regression fails against the original
adapter. GUI boundary (39 cases) and source-group (25 cases) checks passed. The new
verified GUI group is `bf9a364b252e94ed507a4f8af66e9e48c4b29f64357ee171a256f1108206650b`.
Evidence is in `.agent-work/artifacts/further-windows-focus-20261005/completion.json`.
The failed run does not qualify the changed source. Repairs were pushed as
`2e33720a73f0686dc1ffe72992dfb52e472cd059`; development feedback
[37363600149](https://github.com/mirage335-colossus/software-foundation/actions/runs/37363600149)
passed all four jobs at attempt 1 on that exact source.

Completed repaired prerequisites on the same `2e33720` source:

- GUI maintenance
  [37363634930](https://github.com/mirage335-colossus/software-foundation/actions/runs/37363634930),
  attempt 3, published the complete `bf9a364b…` group. Its full bytes were
  independently verified, and all 24 retained C++/Rust SDK assets survived with
  unchanged identities, sizes and digests.
- Native Windows GUI
  [37363626265](https://github.com/mirage335-colossus/software-foundation/actions/runs/37363626265),
  serialized attempt 4, passed with Rust recipe
  `e224a3b622d0af5e40b511d67f8bfa6426abdd35b54756cc7f6343d15c01eebe`.
  Complete retained evidence has 104 unique JUnit cases, zero failures/errors/
  skips, relocated-SDK and all-native-GUI checks. Its Rust SDK manifest SHA256 is
  `aaf12d56c3cab1ca0fafac0cb045a69120aa84e5438b5d90f46d155b2d272dcf`.

Both prerequisites' attempts 1 and 2 failed during the provider's runner-allocation
incident, executing zero steps; qualification/publication was skipped. Native
attempt 3 subsequently failed during setup because simultaneous base GUI
publication changed the frozen complete inventory; it executed zero native tests.
Publication completed before serialized native attempt 4. Preserve the inventory
guard and serialize base publication before SDK consumption; a partial inventory
or a weakened guard is not a recovery. Exact attempts, source/group identity,
complete payload evidence and survivor verification are recorded in
`.agent-work/artifacts/further-release-audit-20261005/gui-bf9a-prerequisites-final-verification.json`.

Full Latest
[37383219288](https://github.com/mirage335-colossus/software-foundation/actions/runs/37383219288),
attempt 1 on `2e33720a73f0686dc1ffe72992dfb52e472cd059`, ran with
all-gui/Rust, package revision 6, the two accepted exact predecessor selectors,
retained SDK recipes and pinned Windows graphics input. All four application
producers and the full regression passed, but assembly failed before signing or
candidate publication because its signing-key expression resolved empty. The
named secret exists only in the protected `release-publisher` environment, and
deployment metadata confirms that assembly selected that environment. Diagnosis
inspected only secret metadata and availability booleans. Bounded hosted availability probe
[37385671588](https://github.com/mirage335-colossus/software-foundation/actions/runs/37385671588)
on `cfcab000c8fcb96f8bf42677c7881ef6b3efafd9` passed all five jobs. Direct protected
access succeeded; both undeclared and declared reusable calls without a mapping
reported absence; the declared call with an explicit named mapping succeeded.
Only presence/agreement booleans were emitted. The repair preserves the protected
environment and bounded key guard, adding only the demonstrated named handoff
and optional declaration. Temporary probe workflows are removed after this
evidence is retained. Certification and promotion did not execute; the
failed run is not release qualification. Exact failure evidence is retained in
`.agent-work/artifacts/further-release-audit-20261005/latest-37383219288-attempt-1-failure-analysis.json`.

The signing repair was pushed as `d4a94574129165264bce8b43b000a5ff0cbcb4da`;
development feedback [37385962730](https://github.com/mirage335-colossus/software-foundation/actions/runs/37385962730)
passed all four jobs. Fresh full Latest
[37385992507](https://github.com/mirage335-colossus/software-foundation/actions/runs/37385992507)
then exposed a Windows-only setup error in the newly added signing-guard test:
the synthetic oversized key exceeded Windows' 32,767-character environment
variable limit before the production guard executed. The repaired fixture uses
an isolated dictionary, preserving every assertion and the production key bound;
all 20 cases passed locally, and a discriminating probe confirms zero native
environment writes. Remaining producers were cancelled after the mandatory
regression failed; this run cannot qualify a release. Validate the repaired suite
with the bounded native host diagnostic before another full release.

Intermediate diagnostic-source CI [37385654742](https://github.com/mirage335-colossus/software-foundation/actions/runs/37385654742)
also exposed a timing-dependent test isolation bug: its global sleep mock counted
GPG subprocess polling as network retry waits. A scoped transport clock preserves
all assertions without changing subprocess timing; the complete signed-client
suite passed 57/57 with no exclusions. This test-only correction is included with
the portable signing fixture. Production transport and signing behavior remain
unchanged.

Refreshed screenshot
[37383282720](https://github.com/mirage335-colossus/software-foundation/actions/runs/37383282720)
on the same source passed all three jobs and published
`screenshots-37383282720-attempt-1`. All ten files passed complete digest and
identity verification, all seven views were inspected, and the README gallery
was refreshed with its original source identity. Finish nested
regression, production, complete certification (all eight real native upgrades),
promotion and final readback. Preserve each attempt's identity; do not duplicate
nested workflows or combine incomplete attempts. Only then record actual results
and retire applicable integrated-package qualification. Observe normal cleanup;
do not manufacture extra full runs solely to trigger deletion.

Optional broader editor and full Windows offline GUI/host-bootstrap scope remains
separate, as documented in the existing pending records. Local passes and older
cloud receipts do not establish qualification of the new source.
