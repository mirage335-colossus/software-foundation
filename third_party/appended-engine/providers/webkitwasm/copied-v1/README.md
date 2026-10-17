# Copied259 browser provider source snapshot

These fifteen reviewed files preserve the original `portable/` and `runtime/`
layout. They declare the private copied259 profile; promotion does not establish
an engine build, runtime behavior or a production retained SDK.

The full selected source mapping, frozen Foundation ABI1.0 support snapshot,
patches and applicable source notices are in the
[recipe snapshot](../../../../../recipes/webkitwasm-copied259-v1/README.md).
[Provenance](PROVENANCE.json) pins that mapping and the original fifteen-file
manifest. Native and physical-input successors are separate.

**CMake recovery layout:** install `runtime/embedder.cmake` into the recovered
wrapper's `src/embedder/` directory beside its `main.cpp`, resource and bridge
sources. Set `EMSCRIPTEN_EMBEDDER_CMAKE` to that recovered path, and separately
set `BIB_ENGINE_COPIED_SOURCE_ROOT` to the complete copied source root. Pointing
CMake directly at this directory's `runtime/embedder.cmake` gives an incorrect
`BIB_EMBEDDER_DIR`. This file has no tracked build-graph registration.

The Python metadata generator requires its adjacent template and complete,
separately staged retained recipe inputs. It writes only an explicitly owned,
disjoint build directory. The historical diagnostic recipe is a reference,
not a ready-to-run source root here.
