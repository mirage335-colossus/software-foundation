# Optional portable guest interpreter

The binary appended kernel privately embeds the C99 wasm3 interpreter from
[`wasm3/wasm3`](https://github.com/wasm3/wasm3), reviewed 2026-10-16 at exact
commit `28ecb9af6d2040e474a70f7cb7f43666740141fb` (upstream development version
0.9.0). The complete unchanged supplier archive is `upstream.tar.gz`, SHA-256
`5ecbb8851bd9acb54a83be10f0536167cb0da13b007406578761672b0bd94b18`.
Its canonical immutable acquisition URL is in `manifest.json`. The archive is
retained for recovery; configuration never downloads or executes it.

`source/` contains every top-level upstream core `.c`/`.h` file except the
`m3_api_*` host adapters. The source has the single explicit patch below. The build names fourteen
core C translation units explicitly; no WASI, libc import adapter, CLI, UVWASI,
libuv, platform example, snapshot facility or additional package is enabled.
The complete archive retains omitted source/build/test/maintenance information.
`manifest.json` and `SHA256SUMS` identify every retained compiler input, both
notices and the recovery archive; only these two inventories and this note are
excluded from their own inventory. Run `python3 tools/appended_wasm3.py` to
verify them. Supplier headers remain private to the runtime adapter.

wasm3 is MIT-licensed; retain `LICENSE` with binary and source distributions.
The disabled snapshot source includes an xxHash-derived implementation identified
upstream as xxHash 0.8.3, BSD-2-Clause. Its complete supplier license is also
retained as `XXHASH-LICENSE`, obtained from the upstream
[`v0.8.3` license](https://github.com/Cyan4973/xxHash/blob/v0.8.3/LICENSE).
Retaining both notices avoids omitting attribution from the recovery source.
`patches/0001-widen-slot-usage.patch` widens private compiler allocation-use
counters from 8 to 16 bits and changes their overflow guard correspondingly.
At the pinned upstream revision, a valid function with 256 references to the
same local across a block fails compilation with `slot usage count overflow`;
the documented operand limit is 1024. The private compilation height is 4096,
so a 16-bit counter has room for every possible live compiler stack reference.
The change adds 8192 bytes to private per-runtime compilation bookkeeping and
does not alter the guest ABI or interpreter execution slots. Regression fixtures
cover 255, 256 and 1024 aliases, and reject 1025 operands.

The original archive stays unchanged. The patch SHA-256 is
`865ddbe08d1c01cd9907fa3b60d8c68f75d2366f9eaba7282e5d2d128c6b9b90`.
The source checker verifies the pinned original archive, applies the two exact
line replacements in memory with one required match each, and compares every
patched source file. It also binds the retained unified diff and rejects missing,
changed or undeclared patches. No patch command runs during configuration.
Upstream context is the pinned `source/m3_compile.h` allocation-use array and
`source/m3_compile.c` `IncrementSlotUsageCount`; this is a local integration fix,
not an asserted upstream fix. Remove the patch after a reviewed upstream revision
supports the same capacity and the focused parity fixtures pass.

The adapter accepts only `foundation-guest-v1`: core Wasm version 1, MVP scalar
instructions and mutable globals, one bounded unshared linear memory, optional
bounded MVP funcref table, explicit gateway import and seven scalar exports.
Start sections, implicit WASI and proposal instructions are rejected before
instantiation. The runtime disables proposal features and snapshots at compilation,
compiles every function with upstream type validation before querying the ABI,
and uses memory/table, native-stack and per-invocation gas limits. The payload
and application services are trusted code; this is not a hostile-code boundary.
Modules are at most 4 MiB, memory at most 256 pages (16 MiB), and tables at most
8192 entries. Each function has at most 1024 parameters plus locals and at most
1024 operands, separately; control depth includes the function frame and is at
most 512. Compiler bookkeeping has additional private capacity for block result
slots. Execution uses a 256 KiB interpreter value stack, a 128 KiB native stack
budget and ten million gas units per ABI invocation. These are bounded initial
profile choices, not performance or hostile-input isolation claims.
Custom section payloads remain opaque. The private execution copy omits optional
`name` metadata so a malformed debug-name payload cannot reject an otherwise
valid module. Original module files and their identities are unchanged.

Native and browser kernels share this C/C++ adapter. Emscripten is a kernel
build input only. Guest developers use identified LLVM/LLD or the separate Rust
guest compiler through the binary SDK; they need no script glue or web SDK.
The neither-payload configuration has no interpreter dependency.

Upstream documents a minimal-maintenance policy, although the selected revision
includes newer validation and resource-limit work. Historical 0.5.0 defects and
open supplier reports are not presumed fixed by a newer version number. Upgrade
review must inspect upstream issues/release notes, compare complete source and
license inventories, preserve exact provenance, audit newly enabled instructions
and APIs, and repeat native and browser service/lifecycle/resource-limit fixtures.
No broad Wasm conformance, hostile-input security, performance, Windows or ARM64
qualification is established by the focused implementation checks. Packaging and
release qualification remain governed by the project's ordinary requirements.

The application maintainers own this integration. Recheck it whenever supplier,
compiler, host baseline, guest profile, memory/gas/stack policy or service ABI
changes. Focused compilation covers fourteen small C units plus the adapter;
it does not build a compiler SDK or run the supplier's full platform matrix.
