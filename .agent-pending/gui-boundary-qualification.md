# Generic GUI boundary qualification

Implementation is based on `4bf00e10fb9ed58a0363499ec3dac3b43a0c81c5`
with uncommitted generic boundary, adapter, browser and archive-privacy changes.
The supplier revision remains `7a704f73e563a167ea335dd23ccd9f383ebec274`;
the refreshed retained GUI manifest SHA-256 is
`5eec1117f0f075e74860a5d6daa5e795ca24abb0c5010a011d257f941e5ed373`.
The complete source and per-command evidence are retained under
`.agent-work/artifacts/generic-gui-port-20261015/` with their original identities.

The changes cover native focus/press ownership and Escape, shortcut precedence,
context intent, nested/wrapped scrolling, bitmap and idle-rendering work, optional
focused commands, masked single-line text and text frames. Browser wheel intents
preserve order and retry identity; context routing crosses inert decorations.
Environment files and their editor artifacts are excluded from source archives.
Feature meaning and layout remain in shared application code; adapters implement
only generic capabilities. Trailing defaults preserve ordinary source declarations,
while changed C++ object layouts require rebuilding adapters and consumers together.
Rev masked editing remains explicitly unavailable through its safe placeholder.

## Focused development checks

Implemented work passed focused development checks on Linux x86-64, using the
C++ core provider, GCC 14.2.0, FLTK 1.3.11, SDL 2.32.4 and private Xvfb 21.1.16.
The checked source snapshot was
`dfa51c3605c3148960057c19c2b92f8c9ccaa89cfb651d3f41b7193f52b57908`;
only this qualification note changed after those implementation checks.
`checked-source.json` and `checked-source.tar.gz` in the evidence directory retain
that complete original inventory and source.

- 45 focused CTest entries passed, including shared contracts, browser-model
  routing/queue tests, masked SDL clipboard protection and GUI boundary checks.
- 13 native/host CTest entries passed under private Xvfb, including the FLTK
  focus/input, context, scoped-command, masked-input, wheel, bitmap and actual
  wrapped-text scroll fixtures, the supplier FLTK fixture, SDL and host startup.
- The ordinary retained-input path passed GUI parity and source identity; the
  latter suite contains 16 cases. Eleven existing supplier contract/adapter
  fixtures and the existing renderer fixture also passed against those inputs.
- Across those selections, 71 distinct CTest entries passed with zero skipped
  entries. Exact commands, environment, output and JUnit are retained in the
  evidence directory; repeated parity execution is counted once.
- Retained-input integrity, exact patch composition, GUI insulation and diff
  whitespace checks passed. Documentation validation passed in a verified clean
  source snapshot. The working-tree documentation scan instead encounters existing
  ignored tutorial scratch/virtual-environment links; those files were untouched.

Private development prerequisites were extracted without a system installation.
Initial missing SDL header/shared-library links and an Xvfb readiness-pipe lifetime
error were repaired before their affected checks passed; earlier setup failures
remain in the evidence directory and are not passing evidence. These prerequisites
are not a qualified dependency SDK. Browser model fixtures do not execute a real
browser, and Xvfb provides no window manager. Earlier release/GUI receipts retain
their original identities and do not qualify this changed boundary.

## Deferred extensive qualification

These scopes await an explicit qualification request; no background job is queued:

- Actual window-manager focus, minimize/restore and virtual-desktop behavior.
  Synthetic native events under Xvfb alone cannot establish these behaviors.
- Actual Chromium and Firefox execution in standalone and isolated hosted/Wasm
  paths for the changed input, context, clipboard, appearance and wheel behavior.
- Affected supported native Windows, ARM64 and Rev execution, with each target's
  verified dependencies, compiler and display. Local Linux results do not qualify
  those targets or the older supported operating-system/runtime floor.
- Applicable SDK-consumer, package and binary-release checks before any qualified
  binary delivery. Ordinary source editing does not authorize a release matrix.

Follow [testing stages](../docs/testing.md),
[GUI contracts and native prerequisites](../docs/gui-boundary.md) and
[browser qualification](../docs/browser-embedding.md#threat-scope-and-qualification).
The next manual action is to request the affected platform/browser qualification.
On a suitably prepared Linux desktop, its local GUI scope starts with:

```sh
./build.sh test dev --gui --host-tests \
  --gui-backends terminal,framebuffer,fltk,sdl,hosted-web \
  --build-dir build/gui-qualification --label gui
```

That command does not substitute for the separate browser, Rev or other-target
procedures and must retain its own exact source/environment evidence.
