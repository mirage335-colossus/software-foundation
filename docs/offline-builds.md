# Disconnected application builds

Ordinary application builds consume prepared inputs through
[`tools/build.py`](../tools/build.py), normally launched by `build.sh`.
[`tools/offline_acceptance.py`](../tools/offline_acceptance.py) restores retained
SDK bytes and calls that entry point inside a disconnected Debian 12 Bookworm
boundary. It does not fetch inputs, install distribution packages, clone a
supplier checkout, substitute an SDK or reconstruct a compiler. Preparation and
SDK maintenance have their existing homes in [SDKs](sdk.md) and
[dependencies](dependencies.md).

## Complete inputs

The machine-readable contract is
[`tools/offline_inputs.json`](../tools/offline_inputs.json). Keep these categories
distinct when assembling a kit:

| Category | Required contents |
| --- | --- |
| Application source | Complete checkout, including `third_party/gui-inputs`, reviewed patches, fonts and notices for selected GUI hosts |
| Selected retained group | Binary archive, source/bootstrap archive and complete `SHA256SUMS`, all matching one exact recipe identity |
| Native SDK contents | Matching native compiler/linker, target sysroot, selected toolkits, notices and every declared `sdk.json` host tool |
| Wasm SDK contents | Emscripten, LLVM, Binaryen, Node, configuration, prepared frozen `EM_CACHE` and notices |
| Distribution host tools | Shell, Python, Git, CMake and Ninja where not retained; native inspection/package tools and relocation utilities listed in the inventory |
| Acceptance host | Prepared Bookworm image or root filesystem, plus the selected isolation adapter's setup tools and declared runtime/display prerequisites |
| Separate validation/delivery tools | Browsers and drivers, JavaScript test tools when not already supplied, display services, and package/signing tools for the requested checks |

A URL, recipe or hash without the matching retained bytes is incomplete. The
precompiled compiler archives retained by an SDK recipe are build inputs; their
upstream download URLs do not create an ordinary-build network dependency.
Browser engines are validation prerequisites and do not enter the compiler SDK.
Missing or corrupt contents require explicit preparation before a new attempt.

Native distribution builds remain supported without a retained SDK. They use the
checkout, its complete GUI source group when enabled, and the selected
distribution compiler/toolkit package closure. The ordinary core minimum remains
Python 3.9, CMake 3.24 and the required C++20 compiler features. Rev requires the
newer module toolchain documented in [GUI platform dependencies](gui-boundary.md#prepared-platform-dependencies).

## Native host and target selection

| Build host | Acceptance target | Build-tree contents |
| --- | --- | --- |
| Bookworm Linux x86_64 | `linux-x86_64` | Core/CLI and terminal, framebuffer, FLTK, Rev, SDL and hosted-web in one native tree |
| Bookworm Linux aarch64 | `linux-aarch64` | Core/CLI and the same six native hosts in one native tree |
| Bookworm Linux x86_64 | `browser-wasm32` | Core/CLI and Wasm GUI in a separate Emscripten tree |
| Supported native Windows x86_64 | `windows-x86_64` | Core/CLI and the same six native hosts, through the Windows route |

The Bookworm launcher accepts host-native Linux cases only. On x86_64 its default
selection requires both native and Wasm cases; on aarch64 it requires the native
case. `--case` selects a diagnostic subset, recorded as such. It never establishes
qualification for an unavailable architecture. Windows retains its separate
[offline host-tool and dependency procedure](sdk.md#windows-dependency-base-and-separately-installed-host-tools),
including the complete Microsoft installer layout/component configuration,
installed matching compiler/Windows SDK and retained graphics prerequisites.
This contract adds no cross-host SDK support.

## Prepare the boundary, then run acceptance

Prepare and identify the Bookworm environment before invoking the runner. For
Docker, supply the exact immutable ID of an image already present locally. The
adapter uses `--network=none` and `--pull=never`. For the namespace adapter, retain
a complete rootfs receipt and its sibling inventory: architecture, Bookworm
`os-release`, package provenance, every file/link/mode and the expected mount
points. [`offline_namespace.py`](../tools/offline_namespace.py) verifies these
inputs before establishing user, mount, PID and network namespaces. A missing
namespace capability is a failed prerequisite; there is no online or unisolated
fallback.

A plan uses structured JSON fields and canonical absolute paths. This example
is incomplete until the group recipes and image ID are replaced with exact
64-character lowercase SHA-256 identities and the paths name retained inputs:

```json
{
  "schema_version": 1,
  "isolation": {
    "kind": "docker",
    "image": "sha256:REPLACE_WITH_PREPARED_LOCAL_IMAGE_ID"
  },
  "cases": [
    {
      "target": "linux-x86_64",
      "group": "/owned/retained/native-gui-group",
      "recipe": "REPLACE_WITH_EXACT_NATIVE_RECIPE_ID"
    },
    {
      "target": "browser-wasm32",
      "group": "/owned/retained/wasm-group",
      "recipe": "REPLACE_WITH_EXACT_WASM_RECIPE_ID"
    }
  ]
}
```

The namespace alternative replaces only `isolation` with:

```json
{
  "kind": "namespace",
  "rootfs": "/owned/prepared/bookworm-rootfs",
  "manifest": "/owned/prepared/bookworm-rootfs.json",
  "manifest_sha256": "REPLACE_WITH_EXACT_ROOTFS_RECEIPT_SHA256"
}
```

```sh
python3 -B tools/offline_acceptance.py run \
  --plan /owned/offline-plan.json --output /owned/new-offline-acceptance --jobs 2
```

The output directory must be new and disjoint from retained groups. The runner
freezes a complete source snapshot, projects source and group inputs read-only,
and creates fresh build, HOME, temporary and cache paths. It does not expose a
sibling supplier checkout, host HOME, credentials, ambient cache or Docker
socket to the application child. The restored SDK becomes read-only for execution.
Boundary probes run both in the application environment and a child process;
non-loopback access, unexpected interfaces or application capabilities fail
before compiling. Compiler caching is disabled. Wasm retains its prepared SDK
cache through `EM_CACHE` and `EM_FROZEN_CACHE=1`.

Within the same boundary, each case restores/verifies the group and runs release
build, core tests and packaging through `tools/build.py`. Native cases use all
six GUI backends in one compatible tree. Archive verification exercises the
installed CLI and installed CMake consumer; native Linux explicitly requests the
ABI audit and separately exercises all six installed GUI smoke checks. Wasm
uses its distinct toolchain tree and package/consumer checks. A missing tool,
wrong architecture/capability, changed source/SDK, stale build identity, missing
Wasm cache or invalid imported Wasm package fails with a diagnostic. The runner
never repairs inputs through a download or alternate SDK.

For a focused diagnosis, append, for example, `--case linux-x86_64`. The summary
then records incomplete host coverage when the Wasm case was omitted.

## Receipts and qualification limits

The output retains `acceptance.json`, the frozen source and plan, and per-target
`request.json`, `stage.json`, `execute.json`, `acceptance.log` and core JUnit
results. Receipts bind source-tree identity, exact group/recipe/archive hashes,
SDK manifest and Wasm cache identity, host-tool and package provenance, Bookworm
OS, isolation configuration/probes, requested backends, commands/results and
package hashes. Read phase results when the aggregate failed; an attempted or
unexecuted phase is never a pass.

A successful receipt establishes the recorded application build, installed
consumer, native ABI and smoke scope in its exact environment. Full regressions,
other native architectures, Windows execution and actual browser security remain
separate qualification. [Browser embedding](browser-embedding.md) describes that
boundary; [validation](validation.md) records actual observed results. Build,
runtime and package compatibility claims must retain their separate evidence.
