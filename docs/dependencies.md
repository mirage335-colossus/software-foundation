# Third-party dependencies and upgrades

A dependency must remain identifiable and maintainable after its original
integrator leaves. Keep a machine-readable inventory in
[`third_party/dependencies.json`](../third_party/dependencies.json) and concise
maintenance notes for each selected dependency. Preserve upstream license and
notice files with the source and all applicable binary distributions.

The default library and CLI use the C++ standard library and platform/compiler
runtimes. They have no added third-party application runtime dependency. Optional
GUI integration consumes a separately prepared checkout, with its own source,
toolchain, runtime, and redistribution requirements. Build/test tools are still
dependencies and must be identified in environment records.

## Required record

Use [the dependency template](templates/dependency.md). At minimum record:

| Field | Required information |
| --- | --- |
| Supplier | Upstream project, canonical repository/homepage, release and issue locations |
| Identity | Human version, full resolved commit, source archive URL and SHA-256 |
| Acquisition | Vendored subset, submodule, system package, prepared bundle, or SDK; explicit preparation command |
| Scope | Files included/omitted, features enabled/disabled, direct and transitive dependencies |
| Licensing | SPDX identifier when known, exact license/notice paths, modifications, redistribution status |
| Changes | Ordered patches, rationale, upstream issue/commit, removal condition, patch digests |
| Build | Supported compiler/runtime/configuration, required host tools, offline recipe, install layout |
| Consumers | Targets and call sites using it, API/ownership/error assumptions, adapter boundary |
| Upgrade | Review steps, compatibility risks, affected tests, package/SDK requalification |
| Ownership | Responsible maintainer, last reviewed date, outstanding limitations and recheck trigger |

Resolve an annotated Git tag to its commit with `git rev-parse 'TAG^{commit}'`
in a verified upstream checkout. Record the resulting full commit rather than
only a mutable branch or tag name. A source archive digest identifies its bytes;
a commit identifies repository content. Retain both when available.

For distribution packages, record supplier/repository snapshot, package version,
architecture, source package, archive digest, and how license/source material is
retained. A list of package names alone is not enough to reproduce a release.
For system runtime prerequisites, state tested versions and compatibility limits
without pretending those files are vendored.

## Source and integration boundaries

Prefer the smallest maintainable dependency set. Do not copy a large upstream
tree when only a small documented subset is used, but retain all required source,
licenses, build metadata, and upgrade context. Document omissions so an upgrade
does not accidentally discard a new required file.

Keep third-party headers out of application public interfaces when a small
adapter can hide them. Do not leak toolkit classes, allocator assumptions, or
dependency-specific error types through a general application contract. Review
the callers and callees: changes in lifetime, callback timing, threading,
ownership, encoding, or error behavior can break a consumer even if it compiles.

Keep upstream code close to its original form. Prefer a versioned patch series
or isolated adapter over undocumented edits. Apply patches with exact context
and fail if the expected upstream content changed. Never silently skip a failed
patch or suppress all warnings globally to accept an upgrade.

Default configuration must not fetch the network. Provide an explicit
preparation step and pinned inputs, then support offline configuration/build.
Local caches must be ignored, durable enough for ordinary development, and
separate from tracked recipes. Do not rely on ephemeral `/tmp` aliases or
unidentified binaries recovered from an old application installation.

## Upgrade procedure

1. Identify current consumers and preserve the current lock/manifest and test
   results. Read upstream release notes, migration notes, and maintenance notices.
2. Select an exact maintained version or commit. Verify provenance and archive
   digests through the established trust process; review new transitive inputs.
3. Compare the included source subset, licenses, options, public interfaces,
   generated files, minimum tools, and runtime requirements.
4. Reapply or retire each local patch deliberately. Record upstream fixes and
   retain a regression for each behavior the application depends on.
5. Trace every affected call path through the adapter and its callers. Update
   ownership, lifetime, error, concurrency, and resource handling as required.
6. Run focused integration tests, then the applicable normal regression matrix,
   installation checks, SDK qualification, and exact-package compatibility tests.
7. Update the machine inventory, maintenance note, notices, recipe identities,
   source archives, and build/release documentation in the same change.
8. Preserve the previous prepared inputs for supported releases and publish new
   immutable recipe assets. Document rollback to the prior complete set.

A dependency upgrade can raise the runtime baseline even when application code
is unchanged. Reaudit every delivered runtime file. A warning-free compilation
does not prove that all downstream assumptions still hold.

## Licensing and redistribution

Record the actual upstream terms; do not infer a license from a public repository,
a familiar project name, or a dependency's dependency. If required terms are
absent or unresolved, mark redistribution blocked and omit the affected binary
from distributable output until resolved. Local technical evaluation does not
establish redistribution permission.

Retain source and modifications where the applicable terms require them; satisfy
required notices, attribution, and relinking/source obligations for the actual
linkage used. An SDK includes host tools and target libraries that may have
different obligations. Keep private credentials out of sources, archives, and
build logs. Document a contact and process for reported dependency defects.

The inventory must distinguish shipped dependencies from development tools,
optional integrations, and proposed dependencies. Do not fill an empty field
with an invented license, supplier, tested platform, or digest merely to satisfy
a checklist.

## Durable recovery

Keep exact source inputs, patches, recipes, and binary archive digests together.
An upstream URL may disappear. A binary release should retain its required
prepared dependency group or a durable independent reference and documented
recovery procedure. Test reconstruction from the retained source inventory in
an empty, offline cache when qualifying a new SDK recipe. See [SDKs](sdk.md).

Temporary investigation findings belong in the ignored coordination notes with
source URL/date, dependency revision, affected environments, evidence, confidence,
and recheck condition. Promote durable verified findings into this inventory,
maintenance documentation, and regression tests. Community workarounds remain
hypotheses until validated against the pinned dependency and current callers.
