# Retained rich-engine integrity format

This directory contains the Stage A retained-input tools and a reviewed
[copied259 provider source snapshot](providers/webkitwasm/copied-v1/README.md).
Its [75-file recipe projection](../../recipes/webkitwasm-copied259-v1/README.md)
retains the selected wrapper, engine patches and binding sources with provenance
and selected notices. The complete supplier archives and generated engine binary
are external retained inputs. There is no production-eligible engine group.
An explicit [bounded maintenance producer](../../docs/appended-applications.md#explicit-retained-engine-maintenance)
now has a supported entry point and focused fixture checks; it has not built an
actual candidate, and its required successor/reuse closure is not yet sealed.
The actual baseline probe and its
limits are recorded in [engine feasibility](../../docs/appended-web-feasibility.md).

`tools/appended_engine_manifest.py` checks strict recipe, source and binary
contracts. `tools/appended_engine_sdk.py` verifies, exports and restores complete
retained groups. Every successful result says
`"scope": "retained-byte-integrity-only"`. A valid fixture or manifest proves
neither that its producer ran nor that its engine, ABI, declared features,
runtime baseline or application connection works. Runtime proof and kernel
capability publication require their actual implementation and original evidence.

The source implements Linux and Windows host adapters. Linux checks actual
normalized modes and publishes through `renameat2(RENAME_NOREPLACE)`, failing
closed when unavailable. Windows recomputes all bytes, names and entry types
while retaining explicit logical mode authority from the complete manifest or
producer recipe; it never guesses executable bits from filenames or `st_mode`.
Every existing ancestor and visited entry is checked before traversal; links,
junctions and all reparse attributes are rejected, and unavailable Windows
reparse metadata fails closed. Windows publication uses same-parent `os.rename`
without replacement or copy fallback. Python specifies refusal of an existing
Windows destination in its [rename contract](https://docs.python.org/3.9/library/os.html#os.rename).
Actual Windows filesystem visibility, junction and locked-file execution still
require native qualification. No additional product permission boundary is
introduced.

## Complete retained group

For the full lowercase SHA-256 recipe identity `ID`, a group contains exactly:

```text
engine-ID-binary.tar.gz
engine-ID-sources.tar.gz
engine-ID-SHA256SUMS
```

The checksum file contains exactly the two archive SHA-256 values, binary first,
with two spaces before each filename and a final newline. Archives contain only
ordinary files and explicit directories, with complete inventories and no links,
special files, traversal, case aliases or file/directory conflicts. Portable
paths use ASCII names and exclude Windows reserved names and punctuation.
Every directory uses logical mode 0755 and every file uses 0644 or 0755;
root manifests use 0644. POSIX producers must normalize their owned trees
before sealing them. Windows carries these portable modes from explicit checked
metadata; the values do not describe NTFS ACLs or actual POSIX execute bits. Empty
directories and modes are inventoried and retained. Archive members are sorted
and have fixed timestamps for deterministic packaging of identical inputs.

The binary root contains `engine-sdk.json`. The source root contains
`sources.json` and exact `recipe.json` bytes. Each complete inventory has `files`
(relative path to SHA-256), sorted unique `directories` (including empty ones)
and `modes` (integer mode for every inventoried file/directory). The root
manifest is omitted from its own inventory and independently required as 0644.
Unknown manifest fields, duplicate JSON keys, bool values in integer fields,
nonfinite JSON values and incomplete/extra input trees fail verification.

Recipe identity is the SHA-256 of the exact retained `recipe.json` bytes. Those
bytes bind every expected producer input's path, hash, role and mode, together
with suppliers, patches, target, tools and provider contract. The binary binds
the exact source-manifest SHA-256 as well. Reformatting a retained recipe changes
its identity; re-encoding a source manifest changes its binary binding. The
producer version is 1, and exact helper bytes belong to the source recipe.

## Source recipe and manifests

`recipe.json` has these exact fields:

| Field | Contract |
| --- | --- |
| `schema_version`, `producer_version` | Integer 1 |
| `kind` | `foundation-appended-engine-recipe` |
| `target` | Explicit `system`, `processor`, `triple`, `pointer_bits` |
| `toolchain` | Explicit `cxx_standard`, `identity_sha256`, `runtime_policy`, `paired_sdk_sha256`, `target_baseline` |
| `options` | `script_enabled: true`, `rendering: cpu`, explicit `thread_model` |
| `provider` | `format`, `binding`, `abi_major`, `abi_minor`, `header`, `header_sha256` |
| `suppliers` | Exactly `wrapper` and `engine`, each with HTTPS `repository`, full 40-character `commit`, retained `archive` path |
| `inputs` | Every retained producer file, keyed by path; each value has exact `sha256`, `role`, integer `mode` |
| `patches` | Ordered records with `path`, `tree`, complete `preimages` and `postimages` |
| `licenses` | Nonempty sorted unique retained notice/license paths |

Input roles are `source`, `patch`, `tool`, `bootstrap`, `data`, `license`,
`helper`, `config` and `interface`. Supplier archives must be source inputs;
every listed license must be a license input; the provider header must match an
interface input. Every patch input must occur exactly once in the ordered
series. Each patch names `wrapper` or `engine` and identical nonempty sets of
preimage/postimage paths. A null image represents an added/deleted file; both
images cannot be null. These are checked input contracts, not an invocation of
patch or proof that a source archive has a sufficient build closure.

The complete exact helpers are mandatory `helper` inputs:

```text
tools/appended_engine_manifest.py
tools/appended_engine_sdk.py
tools/dependency_archive.py
```

`sources.json` has exactly `schema_version`, `kind`, `producer_version`,
`recipe_id`, `files`, `directories`, `modes`. Kind is
`foundation-appended-engine-sources`; both version integers are 1. Its file
inventory is exactly every recipe input plus `recipe.json`. The retained recipe
identity and every hash/mode are recomputed, rather than trusting matching
identity strings in two manifests.

Recipe review must retain all actual compiler/SDK/bootstrap archives, host
generators, dependency/data/font inputs, corresponding sources, licenses,
integration helpers and patches needed for the declared offline recovery scope.
An upstream URL, sparse checkout, manually invented digest or unverified cache
is insufficient. These format tools cannot determine semantic build closure or
redistribution rights from a set of hashes. Preserve the supplier's exact
notices and satisfy the actual linkage's source/relinking obligations before
distribution. Follow [dependency maintenance](../../docs/dependencies.md) and
the [existing SDK lifecycle](../../docs/sdk.md).

## Binary manifest

`engine-sdk.json` has exactly `schema_version`, `kind`, `producer_version`,
`recipe_id`, `sources_sha256`, `target`, `toolchain`, `options`, `provider`,
`licenses`, `build`, `files`, `directories`, `modes`. Versions are integer 1 and
kind is `foundation-appended-engine`. Group verification compares target,
toolchain, options, provider ABI/header/binding and licenses to the retained
recipe; binary notices must have the same bytes as retained source notices.
`build` contains a nonempty `origin` description and an inventoried
`link_receipt` path. Receipt bytes are retained evidence supplied by the producer;
these integrity tools do not authenticate the producer or certify that receipt.

Target metadata currently accepts Linux x86_64/aarch64, Windows x86_64 and
Emscripten wasm32, with explicit triples and correct 64/32-bit data models. This
is a metadata vocabulary, not a support matrix. Engine internals declare their
isolated C++23 toolchain. Native `runtime_policy` is `private-native` with null
`paired_sdk_sha256`; browser policy is `paired-emscripten` with an explicit paired
SDK SHA-256. `identity_sha256` and `target_baseline` remain explicit producer
constraints. Script execution is enabled, rendering is CPU, and thread model is
`native` or browser `single`. None of these declarations substitutes for import,
runtime, CPU or actual engine behavior checks.

The binary `provider` adds `entry` and nonempty sorted unique `assets` to the
source provider fields. Its header digest must match the complete inventory.
Linux `native-shared` entries name an explicit `.so` (optionally versioned);
Windows entries name a `.dll` and include a `.lib` import library among assets.
Native binding is `c-abi`. Browser `browser-module` entries name `.js`/`.mjs`
and include at least one explicit `.wasm` asset. Browser binding is
`copied-owner-bridge` or `linked-owner`; the latter vocabulary is retained for
honest producer descriptions, not selected as the production direction. Runtime
assets, the ABI header, notices and link receipt must have distinct roles and
exist in the complete inventory.

The preferred production direction is an application-neutral engine extension:
native C callbacks into the actual C++20 kernel owner, and a bounded copied-value
bridge between separate browser engine/kernel Wasm instances. Each instance has
its own heap; C pointers/function pointers cannot cross between them. Engine
trampolines stage copied admission, leave the complete engine/JSC turn, then the
host drives the actual kernel WebServices/Registry/Module owner before a later
protected engine delivery/ACK receipt. Generic outer JavaScript transports
values and pixels without executing application JavaScript or creating an
application DOM. The current diagnostic demo Registry is not that integration.
Persistent module sequences and the shared copied-result ACK broker survive
document replacement. Actual transport implementation remains Stage B work.

## Integrity commands and publication behavior

The supported build wrapper dispatches these integrity actions before native
toolchain selection. They do not configure or compile anything:

```sh
./build.sh engine-sdk recipe-id --root /owned/engine-sources
./build.sh engine-sdk verify-inputs --root /owned/engine-sources
./build.sh engine-sdk verify-sources --root /owned/engine-sources
./build.sh engine-sdk verify --root /owned/engine-binary --recipe EXACT_RECIPE --manifest-sha256 EXACT_BINARY_MANIFEST_SHA256
./build.sh engine-sdk export-group --binary /owned/engine-binary --sources /owned/engine-sources --output /owned/new-group
./build.sh engine-sdk verify-group --group /owned/new-group --recipe EXACT_RECIPE
./build.sh engine-sdk restore --group /owned/new-group --recipe EXACT_RECIPE --output /owned/new-binary
./build.sh engine-sdk restore-sources --group /owned/new-group --recipe EXACT_RECIPE --output /owned/new-sources
```

`verify-sources` also accepts an exact `--manifest-sha256`; irrelevant arguments
are rejected for each action, so an explicit pin cannot be silently ignored.
Python callers can additionally pin exact target and toolchain identity through
`verify_engine`. A production consumer must select independent trusted pins.
Successful unpinned verification alone establishes internal consistency.

Output parents must already be ordinary unlinked directories. Outputs must be
new, outside retained input trees, including when an existing destination is an
empty directory, dangling symlink or broken junction. Occupancy is checked with
`lstat`, and publication remains the final no-replace arbiter. Export rechecks original inputs and staged
archive inventories. Restore first verifies the complete group, copies it into
fresh private storage, verifies that copy, extracts only the selected member,
and verifies the restored manifest, complete bytes/directories/modes before
no-replace publication from a direct sibling staging root. The identified
ordinary output parent is rechecked before that move. Linux atomic visibility
uses its declared primitive; Windows filesystem visibility still requires actual
qualification. After successful publication, cleanup never visits the old
staging name. Failure cleanup requires the original directory identity; unknown
or changed identities are preserved with an explicit failure. Preexisting
outputs remain intact. No repair, replacement, network fallback or
engine/tool execution is performed. `fetch` and `build` are rejected actions.

The focused fixtures in `tests/test_appended_engine_sdk.py` use marker supplier
inputs, a small inert JS asset and minimal Wasm bytes. They establish only these
integrity/failure behaviors and never execute an engine or qualify a platform.
Simulated Windows mode/reparse/publication cases run on Linux and are explicitly
source/plumbing checks. Native Windows execution, including real junctions,
locked files and competing publications, has not run. The original Linux Stage A
33-test receipt retains its original source identity separately from later host
adapter checks.

## Root integration still required

The root integration dispatches `engine-sdk` before native/provider selection
and registers `tools.appended_engine_sdk` on Linux. Other hosts have an explicit
coverage exclusion while native host qualification remains pending; that
exclusion is not a passing Windows test. Native Windows can invoke the same
integrity parser through `python tools/build.py engine-sdk ...`; actual Windows
filesystem execution has not been observed. The reviewed source projection and
historical diagnostic recipe now retain exact source identities. The diagnostic
recipe is not runnable from its tracked location and does not establish complete
offline SDK recovery or a production retained group.

Stage B must implement the provider, real copied browser bridge, installed native
C ABI/asset package and retained kernel composition before enabling a rich-web
profile. Bind original runtime evidence to the actual provider ABI/features and
binary/asset closure. Keep `foundation::core`, the ordinary `none`/`binary`
graphs and C++20 baseline independent. Engine source/helper/patch inputs remain
conservatively protected kernel inputs. Payload compile/pack/compose must never
start engine/kernel production, including cache-hit work. Missing retained inputs
must fail with concrete maintenance needs. Extensive qualification follows the
existing [pending/manual policy](../../.agent-pending/README.md), separately from
these source-only tools.
