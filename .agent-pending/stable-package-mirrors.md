# Native stable package mirror upgrade qualification

Implementation starts from `1ad167aa741c07d9f8d33b56239b271913cd66d5`.
The [stable mirror design](../docs/distribution-release.md#stable-package-mirrors)
preserves the accepted immutable signed channels and their existing qualification.
Both mirrors are deployed. Their signed assets match the accepted immutable
channels, whose original native installation/upgrade qualification remains valid.
Fresh public APT and pacman refresh/download checks and Gentoo authenticated
qualified-channel refresh passed. Native installation and upgrade through two
generations of the permanent URLs have not been executed. See the exact
[publication and validation record](../docs/validation.md#stable-package-repository-urls-2026-10-05).

Implementation `84a599e2d4608bd7b6acbd992939f62b574c7c73` was followed by the
bounded manual publication route in `e5022ab7a748d1fdba0b047bdb8902db02e0d5f6`
and the Arch instruction correction in `c3b889b5327397828ce3bcb75594b092913c816b`.
Final local validation on 2026-10-05 passed nine mirror cases and one real signed
native-acceptance fixture, with no skips. Workflow isolation, YAML, embedded Python
and documentation checks passed. These focused checks do not establish native
stable-URL upgrade qualification.

One qualification obligation remains: run the existing required native A-to-B
installation and upgrade procedure with APT on its declared x86_64 and aarch64
hosts and pacman on qualified x86_64, configuring each permanent mirror URL only
once. Confirm signed metadata and package verification, the newer installed
versions, unchanged configuration between revisions, and retrieval of the retained
older versioned payload after index replacement. Use the existing
[native client procedure](../docs/distribution-release.md#native-acceptance-and-normal-updates)
and retain exact application/channel identities, mirror state, qualifier revision
and workflow evidence. This does not add an ARM64 Arch support claim.

Next manual action: explicitly request native stable-URL A-to-B qualification
when the next accepted generation is ready. Do not roll application Latest or
production repository indexes backward to manufacture a historical transition.
The user explicitly excluded long Actions jobs from the current publication;
only three publication jobs ran, each under two minutes. No further workflow
launch is requested by this record.
