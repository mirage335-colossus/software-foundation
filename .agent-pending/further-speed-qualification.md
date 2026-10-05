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

The user has requested complete hosted qualification and cloud-built releases.
Automatic approval review rejected the direct default-branch push, requiring
explicit authorization for the `main` mutation. That authorization is pending;
implementation is committed locally, while new-source hosted execution and the
README screenshot refresh have not run. No rejected push was worked around.

Completed prerequisite: GUI maintenance
[37350603497](https://github.com/mirage335-colossus/software-foundation/actions/runs/37350603497)
passed on `d516febe135066c811860e3a40968224f74913f1`, publishing exact current GUI
group `2dcef6393d9ad9a4c41c8a819f3e836ace78af4c19eb4be7496b9ca41fac78cd`.
All four C++ and four Rust retained groups remain available. The supported
maintenance helper retired only the verified superseded GUI slot; it did not
rebuild SDKs or retire unrelated SDK groups.

Next steps after authorized push:

1. Require green development feedback on the pushed source. Use the prepared
   screenshot inputs in `.agent-work/artifacts/further-screenshots-20261005/`
   with `core_provider=rust` and `execute=true`; verify and inspect the complete
   cloud-created gallery before replacing its ten README assets/provenance files.
2. Historical distro predecessor tags are unavailable. The retained old Latest
   `release-37245250573-attempt-1` still has a reproduced complete certificate.
   Use the supported legacy distribution workflow to create new immutable r5/s5
   predecessor channels for x64 and ARM64, with the exact old certified bytes and
   a new clean pushed `packager_commit`. Ready request/dispatch templates and old
   certificate readback are in `.agent-work/artifacts/further-release-audit-20261005/`.
   Their native acceptance does not claim upgrades from the deleted tags.
3. Run `_release-latest.yml` with all-gui, Rust, exact retained recipes, package
   revision 6, the two newly accepted predecessor selectors and the explicitly
   configured pinned Windows graphics URL. Complete nested candidate, production,
   certification (including all eight native upgrades), promotion and final
   readback. Do not duplicate those workflows or reuse an incomplete attempt.
4. Record actual hosted identities and retire the applicable integrated-package
   obligation only after success. Observe normal cleanup during these runs;
   do not manufacture extra full runs solely to trigger cleanup.

Optional broader editor and full Windows offline GUI/host-bootstrap scope remains
separate, as documented in the existing pending records. Local passes and older
cloud receipts do not establish qualification of the new source.
