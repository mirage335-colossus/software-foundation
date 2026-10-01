# Releases, distribution, and qualification

A release is an identified set of source, binaries, dependencies, documentation,
and evidence. Build and verify that set before making it the default download.
Preserve the exact released bytes; a later branch fix does not repair an older
download.

The example supports local packaging and candidate workflow artifacts. It does
not create a public GitHub release, operate a Debian repository, or establish
multi-platform support merely by containing a workflow. The procedures below
are requirements for adopting those delivery mechanisms.

Local packaging uses `./build.sh package release --jobs 2` and writes to
`build/release/packages/`. The default is TGZ on Unix-like systems and ZIP on
Windows. The exact filename comes from CPack's project version, target system,
and processor. Inspect and verify the emitted archive explicitly:

```sh
python3 tools/artifact.py create PATH_TO_LOCAL_ARCHIVE --manifest build/package.json
python3 tools/artifact.py verify PATH_TO_LOCAL_ARCHIVE --manifest build/package.json
```

Replace `PATH_TO_LOCAL_ARCHIVE` with the actual generated filename. `create`
records the local producer's archive digest and member inventory; it does not
authenticate a downloaded archive. `verify` checks that identity, rejects unsafe
members, relocates the package into a path containing spaces, runs the CLI, and
builds an independent installed-library consumer. The current helper intentionally
accepts only ordinary files/directories and bounded archive sizes. It does not
yet perform a complete older-runtime ABI audit, native GUI qualification, or
Debian installation testing. Those remain release adoption requirements below.

Optional GUI source integration currently has unresolved upstream package
licensing. GUI executables are for local evaluation, have no install rules, and
cannot be included by the example's package command. Resolve the documented
license prerequisite before implementing a complete GUI release matrix.

## Target and asset inventory

Start with Linux `x86_64`, Linux `aarch64`, and Windows `x86_64` when those
platforms are relevant to the product. Choose explicit minimum runtimes and
test hosts using [the portability contract](portability.md). Do not advertise
targets that have only compiled or have no current qualification.

Generate a release matrix from one manifest containing target OS, architecture,
runtime baseline, feature selection, and GUI backend. Every enabled backend
needs a complete deliverable and the same shared functionality tests. Omit a
backend only through an explicit support decision; a missing asset must not
quietly reduce the promised inventory.

Use unambiguous names, for example:

```text
foundation-VERSION-linux-x86_64-cli.tar.gz
foundation-VERSION-linux-aarch64-cli.tar.gz
foundation-VERSION-windows-x86_64-cli.zip
foundation-VERSION-linux-x86_64-BACKEND.tar.gz
foundation-VERSION-source.tar.gz
release-manifest.json
SHA256SUMS
validation-RUN-ATTEMPT.json
```

`VERSION`, `BACKEND`, `RUN`, and `ATTEMPT` are placeholders to be filled by a
publisher. Backend packages must have separate extraction/install locations if
they coexist. Keep an identical application core and shared behavior in each.
Do not maintain separate feature implementations for release variants.

Include CLI and enabled GUI executables, runtime libraries, required resources,
user documentation, build provenance, dependency inventory, license notices,
and an internal file manifest. Include public headers, libraries, and CMake
exports in the developer package when they are supported deliverables. Keep
large optional diagnostic material separate from ordinary end-user packages.

## Identity and versioning

Record a clean source commit, packaging recipe commit, version, target matrix,
SDK/dependency recipe and archive digests, toolchain versions, build inputs,
creation time with timezone, run ID, and attempt. If repackaging existing binary
bytes, retain their original source and artifact identity and record the new
packager separately. Never describe the packager commit as the application
source when they differ.

Use a monotonically ordered version appropriate to each package manager. A
display label need not be the package version, but the mapping must be explicit.
If timestamps enter ordering, use UTC and a collision-resistant run identity;
local clock changes must not reverse version order. Tags identify fixed source
or recipe commits, never a moving branch.

The [release manifest template](templates/release-manifest.json) intentionally
contains unset values and an empty inventory. Fill and validate it for a real
candidate; it is not evidence of a release.

## Build once, inspect the delivered archives

Prepare required SDK recipes explicitly before application release work. Build
all planned producers against their exact inputs. Keep package producers
independent from expensive regression jobs where possible; join every required
result at the release gate.

For every archive:

1. Verify its digest and expected inventory before extraction or execution.
2. Reject unsafe paths, duplicate members, escaping links, unexpected special
   files, and invalid permissions.
3. Extract to a new owned directory with spaces in its path.
4. Verify the internal file manifest, required notices/resources, and build
   identity; reject unexpected as well as missing files.
5. Audit runtime requirements and dependencies across the entire package.
6. Run representative functionality on each claimed target baseline without
   development paths or development libraries providing accidental support.
7. Verify every enabled GUI backend's interaction and layout contract.
8. Install the developer package and build an independent consumer if shipped.

Checksums prove byte identity against an expected inventory; they do not by
themselves establish the publisher's identity. Publish an authenticated inventory
or supported release provenance mechanism with a documented trust root.
Keep the source and dependency archives required to reconstruct the package.

## Qualification and publication order

Create a draft release or local candidate. Freeze its asset inventory and compute
the manifest/inventory digest before qualification. Each report must identify
the exact source, target, archive hashes, inventory digest, checks, outcomes,
omitted scopes, run, and attempt. A report for another revision or different
bytes cannot satisfy the gate.

Require applicable source regression, installation/relocation, target-baseline,
all-backend, and distribution-install checks. `devfast` and branch diagnostics
never qualify a release. Failures and incomplete mandatory coverage keep the
candidate from becoming the default download. Preserve any accepted narrow
exception and its omitted scope explicitly under a pre-existing policy.

After qualification, publish the checked draft and then verify remotely that the
intended assets, digests, tag commit, release state, and default-download pointer
match the expected release. Do not assume an upload command's success proves
complete publication. On partial failure, inspect actual state and resume
idempotently; never overwrite a conflicting asset to hide a mismatch.

Choose an immutability policy before designing report uploads. GitHub immutable
releases require all assets to be attached before publication; later reports
must live in another durable location linked by the original inventory digest.
If immutable releases are disabled, keep application assets immutable by policy
and append uniquely named qualification reports. See GitHub's
[release management](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
and [immutable release guidance](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases).

Prereleases remain separate from the ordinary update channel. Publishing or
qualifying an experiment must not move the stable default pointer. A corrected
release gets a new version/tag and new binaries. Retain prior supported releases
and required SDK inputs according to a stated retention policy.

## Debian packages and a repository hosted as release assets

A `.deb` download is an installable package, not by itself an APT repository.
CPack can create a package; operating an update repository additionally requires
package indexes, repository metadata, signatures, a trusted public key, stable
URLs, and installation/upgrade tests.

A flat repository can contain `Packages`, `Packages.gz`, `Release`, `InRelease`,
`Release.gpg`, a public archive key, a `.sources` example, and the `.deb` assets.
The signed `Release` metadata identifies index digests; indexes identify package
digests and locations. Bind the client to the repository's key with `Signed-By`
and document verification of the complete trusted key fingerprint. Do not ask
users to disable authentication. See Debian's
[APT authentication documentation](https://manpages.debian.org/stable/apt/apt-secure.8.en.html).

Use `amd64` and `arm64` in Debian metadata, mapped explicitly from the archive
architecture names. Package names and installation paths should permit intended
backend coexistence without colliding wrappers or private libraries. Declare
host runtime dependencies accurately. Verify ownership, executable bits,
directory traversal permissions, desktop integration, and uninstall behavior
as an ordinary user. A restrictive signing-job umask must not make installed
directories inaccessible.

Keep private signing material in the publisher's protected secret store. Import
it only into an ephemeral restricted directory, verify the expected public-key
identity, avoid logging its content, and remove temporary material on exit.
Publish rotation, expiry, revocation, and recovery procedures before operating
the channel.

Immutable version URLs are simplest for consistent snapshots. If a moving
default URL exposes repository indexes, make package `Filename` entries point
to immutable release URLs. Also address races between metadata and index fetches
through by-hash support, an atomic repository service, or tested bounded retry
behavior. Do not claim a release-assets-only arrangement has atomic multi-file
updates without evidence. Preserve enough earlier versions for in-flight clients.

Test clean installation, update from a supported prior version, intended backend
coexistence, removal, and corrupted/untrusted metadata. Do not equate a valid
signature with application correctness. Other distribution formats require their
own native metadata, trust, upgrade, and uninstall checks; reusing payload bytes
does not qualify those delivery channels automatically.

## Release checklist ownership

Assign one publisher for shared remote state. Other agents may build independent
owned targets and submit hash-bound results. The publisher verifies inventory
completeness, gathers applicable evidence, and records publication results.
Release automation needs explicit repository permissions and credentials; a
generic template must not contain real keys, tokens, or account-specific runner
names. See [CI](ci.md) and [agent coordination](agent-coordination.md).
