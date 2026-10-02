# Signed immutable package releases

[`distribution.yml`](../.github/workflows/distribution.yml) wraps an existing,
certified application release as a separate package-manager release. It never
rebuilds application code, substitutes dependencies, appends package assets to the
application release, or changes Latest. Its default dispatch validates a plan only.
An explicit execute dispatch uses the protected `release-publisher` environment.

The source application must be an ordinary public release with the exact requested
inventory and a complete certificate attempt that reproduces against the current
release policy. The helper fetches and verifies the complete original delivery,
then repeats certificate verification before signing and before publication. A
passing workflow name, stored status or adjacent checksum alone cannot authorize
this operation. GUI material still requires resolved recorded redistribution terms.

Each target gets a distinct immutable tag:
`distro-VERSION-ARCH-rPACKAGE_RELEASE-sSEQUENCE`. APT files and Arch databases,
packages and signatures live directly at that release's download root. The full
signed native channel, Arch recipes and Gentoo overlay also live in
`channels.tar.gz`. The release remains a prerelease and is never selected as Latest.

All original delivery files are copied to assets named
`sha256-DIGEST-ORIGINAL_FILENAME`. This retains the original source archive, every
application archive and manifest, every exact SDK/dependency triplet and the original
release inventory. The selected certificate pair, frozen delivery descriptor,
current policy and complete packaging source archive are retained the same way.
Generated recipes point to those exact immutable HTTPS aliases; the archive used
for installation cannot drift when a supplier repository changes or disappears.

The packaging source is bound to its actual clean Git checkout, not a commit label.
The signed manifest retains the bounded raw commit object; verification reconstructs
Git blob and tree identities from every archived source byte and executable mode,
then verifies the tree and commit ID. Both supported Git object formats are covered.
This [Git object proof](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects)
remains checkable offline after the packaging checkout is unavailable.
Line-ending or executable-mode conversions that differ from the committed tree fail
closed; use the clean Linux packaging checkout supplied by the workflow.

The signed `distribution.json` binds every output byte, original application release
ID, certificate, target, complete backend selection and recipe reference. Verification
restores the application inventory, reproduces its certificate from retained
evidence, verifies both package channels and checks the flat downloads against their
signed originals. APT backend receipts must match the exact certified archive and
version. Each selected backend gets its own package with shared files preserved.

## Request and protected inputs

Use this complete JSON as the workflow's `request` input, replacing every identity
with the actual reviewed value. Obtain the packaging commit from the checked-out
revision; ordinary execution requires a clean checkout at that exact commit.

```json
{
  "schema_version": 1,
  "repository": "OWNER/REPOSITORY",
  "application_tag": "v1.2.3",
  "inventory_sha256": "EXACT_RELEASE_JSON_SHA256",
  "profile": "core",
  "certificate_run": "EXACT_CERTIFICATE_RUN",
  "certificate_attempt": 1,
  "certificate_sha256": "EXACT_CERTIFICATE_SHA256",
  "target": "linux-x86_64",
  "version": "1.2.3",
  "package_release": 1,
  "sequence": 1,
  "valid_days": 30,
  "trusted_fingerprint": "FULL_INDEPENDENTLY_TRUSTED_PRIMARY_FINGERPRINT",
  "license_files": ["share/doc/Foundation/LICENSE"],
  "runtime_dependencies": {
    "arch": ["glibc>=2.36"],
    "gentoo": [">=sys-libs/glibc-2.36"]
  },
  "packager_commit": "EXACT_PACKAGING_COMMIT"
}
```

The values above illustrate the schema and are deliberately not executable
identities. Use a profile actually declared in `docs/release-policy.json`. Supported
targets are `linux-x86_64` and `linux-aarch64`. The complete backend list comes from
the certified archive, not from an operator-provided subset. Review the retained
license list and host runtime prerequisites for that exact archive; GUI hosts also
need compatible display services, fonts and drivers. The helper preserves the
existing channel tools' ABI checks and redistribution gates.

Store the armored private signing key as the protected environment secret
`DISTRIBUTION_SIGNING_KEY`, and its independently reviewed full primary fingerprint
as `DISTRIBUTION_SIGNING_FINGERPRINT`. The workflow requires the request to match
that fingerprint. Key bytes are removed from the process environment before child
commands run, written only to a private temporary file outside the checkout, and
deleted after local signing. Outputs and transport bundles contain only public
verification material. Use a dedicated signing key; rotate trust through a reviewed
transition, never by trusting whatever key accompanies a download.

The Debian version is `VERSION+rPACKAGE_RELEASE`; Arch uses
`VERSION-PACKAGE_RELEASE`, and Gentoo uses the existing reviewed revision mapping.
Increase the application version or package release when package bytes change.
Increase sequence for a fresh signed metadata publication. A new immutable tag is
required for new signatures or expiry dates; identical prepared bytes may be retried.

## Local and remote operations

```sh
python3 tools/distribution_release.py plan --request request.json
python3 tools/distribution_release.py prepare --request request.json \
  --output build/distribution --signing-key /secure/private.asc
python3 tools/distribution_release.py verify --directory build/distribution \
  --trusted-fingerprint FULL_PRIMARY_FINGERPRINT
python3 tools/distribution_release.py publish --directory build/distribution \
  --trusted-fingerprint FULL_PRIMARY_FINGERPRINT
```

`prepare` performs read-only remote retrieval and local signing. `publish` prints
its plan unless `--execute` is explicitly supplied. Publication checks the current
remote application and certificate again, creates a draft, uploads without
overwrite, downloads every asset and reruns signature and channel verification
before exposing the release. Lost responses or incomplete uploads preserve their
draft state. Only confirmed fresh atomic tag creation permits one draft creation;
other writers and uncertain responses use bounded reads. An orphan tag without a
visible draft requires explicit reconciliation, never another creation request.
Retry the identical prepared directory to reconcile exact bytes; do not
regenerate it with new timestamps under the same tag. A public incomplete or changed
release is rejected and is never repaired automatically.

```sh
python3 tools/distribution_release.py fetch --repository OWNER/REPOSITORY \
  --tag distro-1.2.3-x86_64-r1-s1 --manifest-sha256 EXACT_MANIFEST_SHA256 \
  --output build/verified-channel --trusted-fingerprint FULL_PRIMARY_FINGERPRINT
```

Fetch requires the exact manifest digest and independent fingerprint. It rejects
unexpected files, changed asset IDs during retrieval, missing evidence, wrong policy,
expired channels and a package release selected as Latest. `INSTALL.md` contains
the actual immutable URL, key fingerprint, APT source stanza, Arch configuration
and Gentoo overlay activation instructions. The managed overlay location is
`ACTIVATION_ROOT/current/gentoo`, with automatic external sync disabled. Keep previously accepted channel state
and apply the existing tools' rollback checks before moving a client to another
tag; signed bytes alone cannot establish freshness for a newly introduced client.

The implementation preflights GitHub's per-asset limit and the 1,000-asset bound
before remote mutation. Each direct package/source/dependency asset must be smaller
than 2 GiB; oversize input fails with no partially published channel. Existing native
channel generation additionally enforces its 256 MiB complete-channel bound.
The repository configuration follows the [pacman configuration contract](https://man.archlinux.org/man/core/pacman/pacman.conf.5.en); both package and database signatures are mandatory.
No Actions artifacts are uploaded. A final private CI bundle retains the prepared
assets or completed failure state for reconciliation, using the shared chunked
draft-release transport. Signing keys are never selected for that bundle.

Local fixtures use actual ELF executables, Debian packages and disposable signing
keys, plus a mocked GitHub service. They cover signature and inventory tampering,
source/certificate closure, publication planning, private partial failure,
idempotent recovery and complete downloaded verification. This does not establish
native pacman or Portage install/update qualification; add the exact acceptance
checks described in [distribution](distribution.md) before advertising those
platforms. Public service behavior also requires an explicit hosted qualification.
