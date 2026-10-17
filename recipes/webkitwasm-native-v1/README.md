# Native CPU document-provider source candidate

This recipe preserves source for a native CPU WebCore/JSC provider, initially the
ABI1.1 document **pixel1795** profile. It does not supply a runnable provider,
native dependency baseline, retained SDK or
runtime proof. No native engine configure, compile or link has qualified these
sources. The application-side loader's mock-DSO checks are separate evidence.

The existing native consumer and terminal composition accept only an eligible
retained native group with independently pinned recipe, binary, proof and runtime
facts. This recipe cannot satisfy those requirements by inspecting source.
Native physical2003/editor2035 remain separate scope. Both/either/neither payload
modes and the portable C/C++/Rust module SDK are unchanged.

## Source selection

`source-imports.json` records the complete small source-delta tree, exact byte
hashes/modes, provenance, patches, helpers and selected notices. All materialized
inputs live in this recipe; neither ignored historical work directories nor a
Wasm SDK are required to inspect them. `provenance.json` records the previous
29-file Linux candidate, ten-file Windows overlay and released modern pixel
source identities. Original copyright/license headers remain intact.

The selected source combines:

- Twenty exact Linux CPU/Foundation engine leaves and nine exact Windows seams.
  CPU source selection excludes Skia/WebCore GPU, GL/EGL, accelerated display and
  recording paths. Native `PORT=Foundation` uses Generic RunLoop, native WTF OS
  services and worker threads, CLoop/static JSC and system malloc. The Linux-only
  configuration gates remain unchanged; Windows is still explicitly rejected.
- The released pixel provider's document publisher, form/session logic, value
  codec, resource/service adapters, Foundation guard and C interfaces. The same
  real Page/LocalFrame is intended to serve pixels and terminal document facts.
  Application behavior is not duplicated across GUI backends.
- The modern private RunLoop timer hook and five resource/service engine-source
  changes. The old public RunLoop header extension, legacy inline-HTML host,
  diagnostic probe and copied Wasm/JavaScript transport are excluded.
- A native copy of the shared neutral runtime: its diagnostic browser branch is
  removed, and its target gate explicitly requires the native 64-bit composition.
  No Page/DOM/renderer behavior is replaced by a mock. IDB teardown restores the
  real queued worker/semaphore order. `BibNativeMediaDisabled.cpp` supplies the
  disabled media flag without linking the browser media bridge. No native audio
  or video playback capability is advertised.

`patches/native-platform-engine.patch` applies to the pinned supplier-patched
WebKit. `patches/native-provider-runtime.patch` adapts the released modern pixel
wrapper. The original supplier patch is retained separately. Source imports and
patch pre/postimages are explicit: equal bytes do not authorize reusing Wasm
objects or invent native build provenance. These files are deltas, not complete
supplier source archives or a complete dependency/license closure.

Inspect the finite candidate without configuring an engine:

```sh
python3 recipes/webkitwasm-native-v1/inspect_sources.py \
  --repository-root /absolute/software-foundation \
  --source-map-sha256 EXACT_SOURCE_IMPORTS_SHA256
```

The result is `native-source-input-integrity-only` and always reports production
eligibility, engine runtime passes and kernel rebuild as false. The helper reads
only the pinned source map and its bounded declared inputs, plus this recipe's
small source namespace. It does not discover tools, scan SDKs/caches, extract
archives, run generators or mutate a retained source tree.
The current inspector requires POSIX file-mode/identity semantics; it does not
claim native Windows filesystem execution.

## Private provider graph and bootstrap

`cmake/native-provider.cmake` is a deferred provider graph for the selected
WebCore build. It creates a private shared library from a closed source list,
uses existing WebCore/JSC/WTF/PAL/Skia targets and checks their PIC policy. It
requires the explicit native CPU/CLoop configuration and matching native
dependency prefix/target. It performs no dependency fetching, preparation,
kernel build or fallback. Compiler and engine runtime flags remain private;
only the generic helper sources opt into exception support.

The graph requires explicitly pinned native binding source/header and generated
native metadata. `source/document-provider/runtime/BibNativeDocumentBinding.cpp`
adapts the released pixel callbacks. Its hidden C++ helper
`bib::provider_candidate::ensureNativeDocumentProviderBound()` uses the private
`source/native/BibNativeProviderOnce.hpp` controller. The first eligible getter
chooses the binding thread. Wrong major, null output, short capacity and maximum
minor below 1 reject before registration; maximum minor 1 or higher returns minor 1.
Registration runs before the Guard gate, uses nonblocking CAS and publishes
immutable State/owner or sticky failure with release/acquire ordering. Concurrent
or recursive binding returns REENTRANT; a ready getter on another thread returns
WRONG_THREAD. Exceptions are contained. Registration runs no Host/Page/VM/START,
resource lookup, author code or DSO constructor. The existing inert preflight
rejects a START from another thread before permanent commitment. The Guard also
rechecks published ownership after acquiring its gate, closing the phase 0 race
with an owner START. No public or private table layout changes.

`prelink-config.json` fixes native provider maxima and service retention at 64
calls/4194304 bytes. It must be an input of the actual native source recipe R.
Command/query maxima are 65536 bytes; the unchanged document operation catalog
retains its 6246/48 byte bounds. Runtime application/worker IDs are fresh monotonic
nonzero process identities; generated metadata never chooses them.

The pure `runtime/generate_native_metadata.py` verifies a complete independently
pinned retained source group, native R, exact original provider-build B, source
inputs, pinned helpers/ABI facts and fixed config. It emits a fresh header in an
empty private mode 0700 output directory. R must include these logical inputs:

```
source/native/runtime/generate_native_metadata.py
source/native/runtime/native-provider-metadata.h.in
source/native/prelink-config.json
```

Execute that exact R-pinned generator, with B outside retained sources:

```sh
python3 /retained/native/source/native/runtime/generate_native_metadata.py \
  --source-root /retained/native --recipe-sha256 EXACT_R \
  --source-manifest-sha256 EXACT_S \
  --provider-build /private/build/provider-build.json \
  --provider-build-sha256 EXACT_B --output-root /private/build/generated
```

The header joins native64 target/layout, ABI/catalog/composite contract, R/B,
source-input and toolchain digests with constexpr checks. It is generated after
B and never becomes an R input. No unresolved template or placeholder digest is
accepted. The source-candidate `source-imports.json` is not R. A Wasm recipe,
synthetic fixture or source inspection cannot replace actual native provenance.
Generation reads and hashes the complete source group twice (bounded 32 GiB/pass,
8 GiB/file); it builds nothing and always reports production eligibility false.
Publication enumerates through fresh descriptors opened from the retained
directory inode, covering filesystems with stale listings on reused descriptors;
unexpected files and changed identities still reject publication.
The sole public entry remains `bib_engine_get_provider_v1`.

The graph's Linux export map restricts the public provider export to that getter
and requests an unresolved-symbol link failure. Actual ELF/PE imports, export
sets, dependency isolation, runtime floors and complete data/font/notices still
require real native inspection and runtime evidence. A CMake policy fixture is
not a successful provider link.

The native engine needs an explicit native C++23 toolchain and target-qualified
dependency closure. The source selects ICU/HarfBuzz, Linux FreeType/Fontconfig,
image/storage/curl/OpenSSL/PSL/nghttp2/Brotli dependencies; it does not supply or
certify them. Windows seams additionally require a clang-cl/MSVC STL/Windows SDK
and CRT policy, native DirectWrite/font/source selection and dependency closure
before its configure gate can be enabled. A native Wasm object is not produced
by changing the target label of a retained browser object.

## Iteration and remaining work

Ordinary web-resource and portable-module iteration must continue through the
[payload tools](../../docs/appended-applications.md) using finalized kernels.
This recipe has no ordinary application-build registration. Initial or changed
kernel capabilities use explicit kernel maintenance; engine maintenance is a
separate operation with admitted inputs. Missing native baseline/retained recipe must
report concrete maintenance needs and never trigger a cold native build.

The native binding source remains uncompiled against WebCore. Actual dependency
preparation and native configure/compile/
link/runtime require a separately costed, authorized scope. The previous 148.3
minute Wasm probe is historical evidence, not a native build estimate. Linux
x86_64/aarch64 and Windows need their own actual evidence; full platform/release
qualification follows the project's manual-qualification policy.

`tests/test_appended_engine_native_sources.py` checks source integrity, exclusions,
native leaf policy and inert CMake selection. These are component/source tests;
they do not create an eligible native provider or connected HTML TUI runtime.
`tests/test_appended_engine_native_metadata.py` uses tiny synthetic R/B groups to
check generation/failure handling. `tests/test_appended_engine_native_bootstrap.py`
provides pure source checks and a separately selected bounded actual-Guard/Once
fake-native probe; its source/compiler/output closure and negative counterfactual
are retained under the caller's fresh output directory:

```sh
python3 tests/test_appended_engine_native_bootstrap.py \
  --bounded-output /absolute/private/new-evidence-directory
```

The focused probe is Linux-only, caps compilation at two jobs and 90 seconds,
compiles no WebCore or provider DSO, and cannot qualify runtime integration.
Its exact Guard pins and reversible fixture-only scheduler instrumentation must
be reviewed together when the Guard changes. No scheduler hook is shipped.
