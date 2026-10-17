# WebkitWasm copied259 source and recipe snapshot

This is a reviewed source snapshot for the initial browser copied259 provider.
It is not a production retained engine group or a self-contained runnable source
recipe. No large archives, SDK, generated metadata header, engine factory or Wasm
binary are included.

**Preserve the CMake recovery layout.** The exact copied provider
[`runtime/embedder.cmake`](../../third_party/appended-engine/providers/webkitwasm/copied-v1/runtime/embedder.cmake)
bytes must be installed at recovered `source/wrapper/src/embedder/embedder.cmake`,
beside the wrapper `main.cpp`, resource and bridge files. Set
`EMSCRIPTEN_EMBEDDER_CMAKE` to that recovered file. Its `BIB_EMBEDDER_DIR` derives
from its own location; selecting the tracked provider's runtime directory directly
is incorrect. Set `BIB_ENGINE_COPIED_SOURCE_ROOT` separately to recovered
`source/copied-provider`; the Foundation and binding roots are recovered
`source/foundation` and `source/provider-binding`. Generated metadata belongs
outside retained sources and inside the explicit CMake binary root.

## Exact source projection

[`source-projection.json`](source-projection.json) is the canonical 75-file map:
fifteen provider files remain under
[`copied-v1`](../../third_party/appended-engine/providers/webkitwasm/copied-v1/README.md),
while the other sixty retain their composition-relative paths under `source/`.
The groups are copied-provider15, engine6, Foundation8, binding10 and wrapper36.
Every entry binds its tracked path, retained path, exact hash, byte count, role
and mode. The frozen Foundation support includes both the provider ABI1.0 header
and copied bridge header plus the dependency-neutral guard/adapters; it imports
no Module/VM owner. Live public headers remain separately owned and must not be
assumed identical just because the pathname agrees.

Reconstruction must recover the separately pinned selected supplier snapshots,
apply the retained supplier port patch once with the measured 68 pre/postimages,
then place these 75 verified final files at the mapped retained paths. Historical
COMPOSITION stages are provenance, not an instruction to replay unavailable
intermediate patches. The selected pristine supplier scope is Source/, Tools/
and root files, with eight exact approved upstream relative links inside its
opaque nested archive; a future scoped extractor must enforce safe targets and
must not follow output links. No archive or extractor is supplied here.

The exact supplier patch is
[`source/wrapper/src/patches/webkit-emscripten.patch`](source/wrapper/src/patches/webkit-emscripten.patch).
The exact
[copied15 patch](patches/copied-wasm-shim-v1.patch) preserves its historical
preimage requirements. Final mapped source files are authoritative for this
snapshot. The copied provider's `portable/` and `runtime/` sibling layout and the
generator's adjacent template must remain intact.

Neutral production selects `BIB_ENGINE_PROVIDER_NEUTRAL=ON` and explicitly
`BIB_PTHREAD=OFF`. The three `source/wrapper/src/spike/` files are historical
snapshot inputs and must never be selected by this target. The older
`source/provider-binding/binding/BibEngineProviderBinding.cpp` is also a
historical replaced binding: the copied target selects
`runtime/BibCopiedPixelBinding.cpp`. Retention does not advertise its unselected
raw native-command catalog. The copied profile declares capabilities259,
bridge65536 and ABI1.0; native service inventory is empty and physical input
capabilities remain zero. These source declarations are not runtime proof.

## Diagnostic identity and limits

[`diagnostic/recipe.json`](diagnostic/recipe.json),
[`diagnostic/sources.json`](diagnostic/sources.json) and
[`diagnostic/prelink-plan.json`](diagnostic/prelink-plan.json) preserve exact
historical bytes from actual local input preparation. They retain their original
input paths and are **not runnable at this directory**. Their original hashes,
actual source-derived provider-build/header identities and limitations are in
[`diagnostic/identities.json`](diagnostic/identities.json). The generated header
and provider-build artifact are deliberately external.

The historical identity used a verified external paired SDK, selected pristine
supplier archive, dependency/host-tool archives, 32 data files and exact producer
helpers. Those bytes are not all included here. The original SDK bootstrap group
location remains unresolved. Baseline thin archives require their complete
member-object, header and configuration closure; copying five `.a` files alone
is insufficient. The compiled ICU lookup still binds its original virtual
filename; staged host paths cannot silently retarget it. This snapshot makes no
standalone SDK/host recovery or redistribution qualification claim.

Metadata generation processed source bytes and profile constants only: it loaded
no engine/Wasm factory, created no Page and executed no author JavaScript. No
actual copied-engine runtime, binary manifest/group, provider proof or consumer
eligibility follows from those hashes. Native/physical successors and future
public ABI changes remain distinct.

## Notices and explicit maintenance boundary

[`notices/INDEX.json`](notices/INDEX.json) maps eleven selected
Foundation/wrapper/WebKit/Skia source notices copied from the actual retained
notice closure. All original source copyright/license headers remain intact.
This selection is not the full forty-notice dependency/host closure and is not a
license verdict. Any distribution needs the actual linkage's complete sources,
notices and applicable qualification.

A future supported explicit engine-maintenance producer must first validate the
complete independently pinned retained source inventory and paired SDK, recover
this selected source graph in owned storage, generate real metadata, compile/link
the neutral target and retain actual artifact/runtime evidence. It must emit a
new recipe identity when paths or inputs change. This source promotion adds no
such entry point, network action, CMake registration or build fallback. Ordinary
neither/binary graphs and payload append/strip/reappend routes remain unchanged;
payload actions cannot authorize engine or kernel production.
