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
`channels.tar.gz`. The release starts as a prerelease and is never selected as Latest. Native client
acceptance can subsequently mark it qualified without changing any asset.

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
existing channel tools' ABI checks and redistribution gates. Current recipes derive
the minimum complete license list from the actual archive: the project license,
the bundled GUI lock and every notice it declares, and the dependency notice index
and every file it indexes. Listed bytes, sizes and data-file modes are verified;
omitted terms or unindexed dependency notices fail before signing. This applies
to core projections too, because their shared resources remain installed. Use
`distro_channel.required_license_files(payload)` on the verified archive payload
to construct the request; review additional project-specific terms when adopting
this example. The workflow accepts at most 32 KiB of UTF-8 request JSON and rejects
larger inputs before parsing. Serialize compactly, retain the complete notice list,
and measure the full dispatch input payload against GitHub's 65,535-character
limit, including any previous-channel selector.

Store the armored private signing key as the protected environment secret
`DISTRIBUTION_SIGNING_KEY`, and its independently reviewed full primary fingerprint
as `DISTRIBUTION_SIGNING_FINGERPRINT` in both the repository variables and the
`release-publisher` environment variables. Planning/native qualification and
protected publication must use the same independently trusted value. The workflow requires the request to match
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
native pacman or Portage install/update qualification. The native workflow below
provides those checks; report its actual result for the exact release before
advertising support. Public service behavior requires hosted execution.

## Native acceptance and normal updates

The [native client workflow](../.github/workflows/distro-check.yml) fetches the exact
published assets and reproduces their signature, package, source, SDK and application
certificate checks before installation. Debian Bookworm, Debian Trixie and Ubuntu
24.04 run natively on x86-64 and ARM64. Official Arch Linux and the current Gentoo
example image run on x86-64. Generating an ARM64 Arch/Gentoo recipe does not establish
native client support on those systems. Every backend in the selected archive must
install, retain its exact private files, launchers and manuals, pass its self-check,
accept a repeated repository refresh, and uninstall. An optional older `previous`
selection adds a real package-version upgrade using two published immutable releases.
Every previously present backend must have a strictly newer application version or
`package_release`; a sequence increase alone cannot qualify as a package upgrade.
Omitting it reports `upgrade_from: null`; repeated installation is not a version-upgrade claim.

For this publication workflow, renewing expiring metadata requires increasing both
`sequence` and `package_release`, even when the application archive is unchanged.
Each immutable distribution tag changes retained source/SDK URLs embedded in native
package provenance. Those changed package bytes must receive a new package release.
The lower-level channel updater can renew metadata alone only when the complete
package specifications, including their retained URLs, remain identical.

`distribution.yml` calls these checks after initially publishing the signed channel
as a prerelease. Only its protected acceptance job may mark that same unchanged
channel eligible for automatic tracking. This changes the channel's qualification
metadata, never its files, source tag or the application's Latest selection. Failed
checks leave a reviewable prerelease. Evidence uses the private draft-release transport,
with exact run/attempt/job/source binding and no Actions artifact storage. The public
qualification marker binds the required native result digests. It supplements the
signed payload and independent key trust; it is not a new signing authority.

For manual qualification, dispatch `distro-check.yml` with `channel` set to:

```json
{"tag":"distro-1.2.3-x86_64-r1-s1","manifest_sha256":"EXACT_DISTRIBUTION_JSON_SHA256","target":"linux-x86_64"}
```

Use `accept=false` for observation, or `accept=true` after reviewing the publication
operation. The latter uses the protected publisher environment. A retry must match
the recorded exact identity; different accepted evidence needs an explicit reviewed
lifecycle transition, not replacement in place.

If a native check exposes a verifier or test-harness defect after publication,
preserve the signed channel assets and their original packaging source tag. Fix
and review the consumer-side defect, then dispatch the native workflow against
the same exact channel with the corrected checkout. All required native jobs must
pass in one qualifier run before acceptance. The public marker binds that
qualifier revision independently of the packaging revision retained by the signed
manifest. This permits requalification of unchanged packages without regenerating
signatures or replacing public bytes; it does not repair a defective payload.
Changed package contents require a new package release and immutable tag.

[`distro_client.py`](../tools/distro_client.py) provides normal client refresh through
Python, GnuPG and standard HTTPS. Public retrieval requires no GitHub account or
third-party Git hosting service beyond the project's own retained release. Install
an operator-trusted copy of the source tool tree and its `docs/release-policy.json`
at a persistent path, preserving the relative `tools`, `docs` and `third_party` paths.
Do not download and execute a changing remote helper during refresh.

The public client uses the REST API for complete release and asset metadata, then
fetches file bytes from their canonical public release URLs. Routing every retained
SDK, source, package and evidence file through the unauthenticated asset API can
exceed its hourly quota in a single refresh. The client binds each download ID to
the observed repository, tag, name, size and digest; limits HTTPS redirects and
transfer duration; stages fresh bytes; and verifies the full signed channel before
activation. Public data downloads do not require a GitHub token. Metadata calls
still share the public API budget, so bound refresh frequency across clients and
preserve the last verified generation when retrieval fails.

Create a root-owned configuration outside the tool tree:

```json
{
  "schema_version": 1,
  "repository": "OWNER/REPOSITORY",
  "target": "linux-x86_64",
  "trusted_fingerprint": "FULL_INDEPENDENTLY_TRUSTED_PRIMARY_FINGERPRINT",
  "policy_sha256": "EXACT_REVIEWED_POLICY_SHA256",
  "selection": {"tag":"distro-1.2.3-x86_64-r1-s1","manifest_sha256":"EXACT_DISTRIBUTION_JSON_SHA256"},
  "location": "/var/lib/software-foundation-channel"
}
```

`selection: {"track":"qualified"}` explicitly opts into subsequent qualified
channels for the same target. Discovery is only a candidate lookup: all assets,
signatures, certificate evidence, target and policy are verified before activation.
The first trusted selection still requires independent freshness review. Once a
channel is accepted, sequence rollback, package removal, version downgrade and
same-version byte replacement are rejected. Trust-key or policy updates require an
operator-reviewed configuration change. Expired metadata fails; refresh signing
metadata with a new sequence and immutable tag before its expiry.

```sh
sudo python3 -B /opt/foundation-tools/tools/distro_client.py refresh --config /etc/foundation-channel.json
python3 -B /opt/foundation-tools/tools/distro_client.py config --config /etc/foundation-channel.json --kind apt
python3 -B /opt/foundation-tools/tools/distro_client.py config --config /etc/foundation-channel.json --kind arch
```

Install the printed APT stanza in a dedicated `.sources` file, or the Arch stanza
in a dedicated file included by `pacman.conf`. Import and locally trust the same
independently verified key with `pacman-key` before installation. Both frontends use
the locally retained signed repository through a single managed `current` pointer.
Run the refresh command before `apt-get update` or `pacman -Syu`, or schedule that
same explicit command using the host's service manager. A failed refresh preserves
the previous pointer; do not proceed to an intended upgrade as though it succeeded.
Ordinary package updates can continue using an unexpired retained generation when
network access is unavailable. This service is opt-in; application installation
never adds a timer or modifies package-manager configuration on its own.

For Gentoo, the installed source tree must remain at its trusted path:

```sh
sudo python3 -B /opt/foundation-tools/tools/distro_client.py install-portage --config /etc/foundation-channel.json
sudo emaint sync -r software-foundation-bin
```

The adapter invokes the same authenticated refresh and activates the complete
binary overlay. Ebuilds wrap retained application bytes with empty compilation
phases; resolve host prerequisites through a configured binary package repository.
Version-3 recipes exclude the private application and manual directories from
Portage's compression transformations so installed-byte checks remain meaningful.
Version-1/2 template verification remains unchanged. Keep Portage's generated caches
outside the authenticated channel tree; modifications to a retained generation
fail the next refresh instead of silently becoming trusted input.

The refresh lock serializes cooperating callers. New complete generations are
verified before the atomic pointer replacement; old generations are kept for
inspection. A directory-sync failure after replacement is reported as uncertain:
inspect `current` and the retained manifests before retrying. The helper is not a
security boundary against another root process, and it does not garbage-collect
old SDK/source archives. Explicitly budget local disk space and retire only
unreferenced generations after stopping client writers.

### Repository trust configuration

The current repository distribution signing fingerprint is
`EF876322B5CE4782062CB3E991649063150BC781`. The private signing key is supplied only
through the `release-publisher` environment secret `DISTRIBUTION_SIGNING_KEY`; the
matching public fingerprint is configured as `DISTRIBUTION_SIGNING_FINGERPRINT`
in both repository and protected-environment variables.
This environment accepts the `main` branch. A project copied from this example
must generate its own key, configure its own independent trust value, and keep
a private recovery backup outside source control and release assets. Never copy
this fingerprint as authority for a different project's packages. Public releases
carry the corresponding verification key alongside signed metadata.

Native package metadata declares host services per backend: hosted web requires
Python, while Rev and SDL require a Mesa GLX vendor implementation. The signed
Arch/Gentoo request must include the union of the selected backend requirements;
for the complete GUI profile this is `glibc>=2.36`, `python`, `mesa`, `fontconfig`,
`ttf-dejavu` on Arch, and `>=sys-libs/glibc-2.36`, `dev-lang/python`,
`media-libs/mesa[X,opengl]`, `media-libs/fontconfig`, `media-fonts/dejavu` on Gentoo.
Debian metadata selects `python3`, `libglx-mesa0`, `fontconfig-config` and
`fonts-dejavu-core` where needed alongside glibc. Font configuration and font data
are runtime resources: bundling the client library alone does not provide them.
The native test bootstrap supplies verification/display infrastructure, but does
not explicitly install the vendor driver. Python also runs the verification
harness, so metadata checks establish its declared dependency and an installed
HTTP session test exercises the actual hosted-web wrapper. Private runtime
libraries remain bound to the original archive inventory.

Native container checks use an authenticated, job-owned Xvfb server supplied by the
runner's distribution. Only its own Unix socket and read-only authorization file
enter the container; no desktop session or host-wide authorization bypass is used.
Container names and labels bind cleanup ownership, containers stop before the
display server is joined, and display lifecycle evidence accompanies the native
receipt. This makes the display service explicit while keeping package-manager
and client-library verification native to each tested distribution. Gentoo
prerequisites remain binary-only even when optional display-wrapper packages are
absent from its current binary repository.

APT metadata verification requires both the cleartext and detached signatures
from the independently trusted key. Capture decoded cleartext from a successful
`gpgv --output -` invocation: named-output finalization differs between versions.
The detached signature authenticates the exact canonical `Release` bytes. Some
providers include the cleartext framing newline in decoded output and others
exclude it; the comparison permits only that one terminal LF difference in either
direction. Other whitespace, line-ending or content changes fail. Keep tests for
both provider directions and invalid signatures when upgrading signing tools;
never substitute broad whitespace normalization for exact content checks.

All native qualification frontends verify the complete signed distribution,
including its Debian packages. The disposable Arch and Gentoo environments
therefore install their distribution-provided `dpkg` verifier alongside signing
tools before running client checks. Gentoo obtains these prerequisites from its
configured binary repository with source-build fallback disabled.

Minimal distribution images may suppress manual-page installation globally. The
disposable native checks explicitly restore man-page extraction through the
package manager configuration before installation; they still compare every
public manual and private payload file with the authenticated package inventory.
