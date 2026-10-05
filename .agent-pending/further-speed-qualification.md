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
run/source binding and seven actual surfaces are checked before README integration.

Completed prerequisite: GUI maintenance
[37350603497](https://github.com/mirage335-colossus/software-foundation/actions/runs/37350603497)
passed on `d516febe135066c811860e3a40968224f74913f1`, publishing exact current GUI
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
Cloud GUI input publication and fresh Windows GUI qualification remain required
before another complete release. The failed run does not qualify the changed source.

Remaining authorized work is a fresh `_release-latest.yml` from the repaired
pushed source, all-gui/Rust, package revision 6, the two accepted exact predecessor
selectors, retained SDK recipes and pinned Windows graphics input. Complete
nested regression, production, certification (all eight real native upgrades),
promotion and final readback. Preserve each attempt's identity; do not duplicate
nested workflows or combine incomplete attempts. Then record actual results and
retire applicable integrated-package qualification. Observe normal cleanup;
do not manufacture extra full runs solely to trigger deletion.

Optional broader editor and full Windows offline GUI/host-bootstrap scope remains
separate, as documented in the existing pending records. Local passes and older
cloud receipts do not establish qualification of the new source.
