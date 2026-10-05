# Integrated application-release package qualification

The source change starts from `c88fb7988037d38ca1685f9a22ff0ea604b04179` and adopts
the [application-release package layout](../docs/distribution-release.md#application-release-packages)
for the next rebuild. Signed packages are prepared before the application
candidate's inventory and checksums are frozen, then delivered and certified as
part of that complete release. This replaces the separate mirror route.

The user requested source changes only, with no test executions, Actions runs or live
consolidation. No package build, signing, integrated native check or release
execution for this layout is recorded. Static integration review is complete:
17 Python files and 24 embedded Python blocks parse with Python 3.9 grammar,
four workflow YAML files parse, local reusable-workflow inputs match their
declarations, and whitespace checks pass. Regression cases were added but not
executed. Complete native/release qualification remains deferred until explicitly
requested. Earlier [mirror publication and public client checks](../docs/validation.md#stable-package-repository-urls-2026-10-05)
and immutable-channel installation/upgrade receipts keep their original scope;
they do not establish qualification of the new inventory layout.

Required qualification covers the complete candidate inventory, signed
`packages.json`, combined APT assets for both architectures, x86_64 Arch assets
and both signed native bundles. All eight native frontends must install each
declared backend, verify the actual version and payload, exercise the application,
refresh the repository, upgrade from the exact predecessor and uninstall. These
are Debian Bookworm, Debian Trixie and Ubuntu 24.04 APT on both Linux targets,
plus Arch and Gentoo on x86_64. There is no ARM64 Arch/Gentoo support claim.

Supply `package_release` in 1..999999, increasing it for same-version package
changes, and `previous_packages` with exact selectors for both Linux targets.
The first integrated release can use the existing accepted immutable-channel
selectors. Later integrated predecessors add `"format":"release-packages"`
and pin their exact application tag and `packages.json` digest. Require real
native upgrade evidence on every frontend and a complete eligible certificate
before promotion. See [Latest inputs and executable ordering](../docs/latest-release.md).

Integrated native evidence currently requires fresh preparation and all eight
native jobs in the same certification attempt. A failed-jobs-only rerun that
keeps an earlier preparation attempt fails closed; use a full certification
rerun with fresh preparation. Historical application-only adoption is unchanged.

The old mirror obligation to preserve prior payloads after replacing remote
indexes is superseded by the new complete application-release layout. It was
not executed or counted as passed. No published mirror or historical release
has been consolidated, removed or modified by this source change.

Next manual action: explicitly request the full integrated Latest rebuild and
native predecessor-upgrade qualification after implementation is ready, with
reviewed exact SDK recipes, predecessor selectors and protected signing inputs.
This record does not schedule or authorize that execution now.
