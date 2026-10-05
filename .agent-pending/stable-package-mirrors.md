# Native stable package mirror upgrade qualification

Implementation starts from `1ad167aa741c07d9f8d33b56239b271913cd66d5`.
The [stable mirror design](../docs/distribution-release.md#stable-package-mirrors)
preserves the accepted immutable signed channels and their existing qualification.
The new mirrors are not yet deployed; native installation and upgrade through their
permanent URLs have not been executed. Focused implementation results belong with
the final integration revision and do not establish native qualification.

Local validation on 2026-10-05 passed nine focused cases with no skips: eight
offline mirror lifecycle cases and the existing native-acceptance fixture extended
through mirror publication using real disposable GPG signatures and Debian package
bytes. GitHub transport was mocked. Workflow YAML, embedded Python, acceptance
ordering and repository documentation checks passed. The tested helper SHA256 is
`977026bfac26f3d47e014d6025b20ee0da800527647d7ddea11c690c6867934e`;
`tests/test_distribution_release.py` SHA256 is
`68c6e5dbe3a34671432130c00dbb0bc9e0546ba93ee526ed70dc15b48c344cee`.

One qualification obligation remains: run the existing required native A-to-B
installation and upgrade procedure with APT on its declared x86_64 and aarch64
hosts and pacman on qualified x86_64, configuring each permanent mirror URL only
once. Confirm signed metadata and package verification, the newer installed
versions, unchanged configuration between revisions, and retrieval of the retained
older versioned payload after index replacement. Use the existing
[native client procedure](../docs/distribution-release.md#native-acceptance-and-normal-updates)
and retain exact application/channel identities, mirror state, qualifier revision
and workflow evidence. This does not add an ARM64 Arch support claim.

Next manual action: request native stable-URL A-to-B qualification after the
implementation and deployment are ready. This record does not request or authorize
a workflow launch or live publication now.
