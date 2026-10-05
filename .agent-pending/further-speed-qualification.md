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

Remaining hosted release work:

1. Historical distro predecessor tags are unavailable. The retained old Latest
   `release-37245250573-attempt-1` still has a reproduced complete certificate.
   Use the supported legacy distribution workflow to create new immutable r5/s5
   predecessor channels for x64 and ARM64, with the exact old certified bytes and
   a new clean pushed `packager_commit`. Ready request/dispatch templates and old
   certificate readback are in `.agent-work/artifacts/further-release-audit-20261005/`.
   Their native acceptance does not claim upgrades from the deleted tags. Runs
   `37352060627` (x64) and `37352082640` (ARM64) are in progress on `946007d`;
   do not launch duplicates or infer completion from successful planning.
2. Run `_release-latest.yml` with all-gui, Rust, exact retained recipes, package
   revision 6, the two newly accepted predecessor selectors and the explicitly
   configured pinned Windows graphics URL. Complete nested candidate, production,
   certification (including all eight native upgrades), promotion and final
   readback. Do not duplicate those workflows or reuse an incomplete attempt.
3. Record actual hosted identities and retire the applicable integrated-package
   obligation only after success. Observe normal cleanup during these runs;
   do not manufacture extra full runs solely to trigger cleanup.

Optional broader editor and full Windows offline GUI/host-bootstrap scope remains
separate, as documented in the existing pending records. Local passes and older
cloud receipts do not establish qualification of the new source.
