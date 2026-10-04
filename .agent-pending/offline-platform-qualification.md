# Remaining native offline platform qualification

Implementation started from `2cc4ea9fddddcb2ea963a56de6b9b375a09a83fd`.
The new disconnected-build input contract preserves Linux x86_64, Linux aarch64,
browser wasm32 and native Windows x86_64 support. It does not introduce cross-host
SDK support. See [disconnected builds](../docs/offline-builds.md),
[SDK use](../docs/sdk.md) and the current [validation record](../docs/validation.md).

The x86_64 Bookworm native case passed SDK restoration, a fresh application build,
core tests, portable packaging, installed consumer, ABI audit and all six installed
GUI smoke checks. Its original immutable source and per-phase receipts are under
`.agent-work/artifacts/sol-ultra-implementation-v1/offline-bookworm-final/`.
Those receipts retain their original source identity; they are not evidence for a
later changed source snapshot. Wasm and browser results are recorded separately in
the validation record.

Two applicable scopes are blocked on environments, rather than awaiting further
authorization:

- Native Linux aarch64: a prepared native aarch64 Bookworm host/rootfs or immutable
  local image and complete retained SDK group matching recipe
  `afe8d1ba004206fcf234376a2110e69c4e9e1ef6b373e7afe23afe8497f8e4de`.
  Run the documented `tools/offline_acceptance.py run` command with a new output
  directory and a native aarch64 plan. Its default host selection must remain
  complete, with all six native backends. Do not substitute x86_64 emulation for a
  native qualification claim.
- Native Windows x86_64: a supported Windows host, the complete Microsoft offline
  installer layout and selected installed compiler/Windows SDK components, plus
  the retained dependency group matching recipe
  `da0aa41ad58536497e23503b4ca778521e47cbd412c5b944490aa3c4d535bf0a`.
  Follow the existing [Windows offline prerequisite procedure](../docs/sdk.md#windows-dependency-base-and-separately-installed-host-tools)
  with external networking unavailable, fresh build/HOME/temp directories and
  no undeclared caches. The Linux Bookworm namespace launcher is not a Windows
  isolation adapter. Record build, packaging, installed-consumer and all six GUI
  runtime results separately.

The next manual action is to provide either missing native environment and execute
its corresponding procedure against a newly identified source snapshot. No native
ARM/Windows execution, new hosted CI result or release publication is claimed by
the current local evidence. Existing release/certification gates still apply.
