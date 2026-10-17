# Windows x86_64 native engine dependency recipe

This directory implements a closed metadata scaffold for the exact Windows20
dependency selection. It is not executable: `executable_plan`, `build`,
`production_eligible`, `engine_execution` and `kernel_rebuild` are false.
Every supplier still needs Windows entrypoint review. `CMakeLists.txt` emits all
thirteen named `MissingInputs` before `project()`, language initialization or
compiler discovery. Its unreachable literal `project()` prevents CMake from
inserting an implicit compiler-discovery project before that gate. CMake was not
executed to check this source property.

`profile.json` fixes Windows/x86_64/`x86_64-pc-windows-msvc`, 64-bit pointers,
`woff2=OFF`, at most four jobs and exact retained archives with no fetch or
fallback. The intended native policy is clang-cl/lld-link, C++23, Release,
static libraries and the static Release CRT (`/MT`), no LTO, an x86_64 SSE2 CPU
floor and the separately unqualified Windows 10 1809 OS declaration. The inert
initial-cache template expresses part of that proposal through explicit program
placeholders. No program, SDK version, toolchain identity, Windows build command
or actual artifact path has been selected by this directory.

The source identities reuse only version, archive name, SHA256, byte count,
format and strip-prefix from
[`../webkitwasm-native-deps-linux-x86_64-v1/profile.json`](../webkitwasm-native-deps-linux-x86_64-v1/profile.json).
That metadata file's reviewed SHA256 is
`fe3df90a8567b811783e18906144bd2d44690207c68faa61322fe7b7fb303a53`.
This reuse does not admit or claim to have read those archive bodies. Linux
commands, build targets, artifact names, PIC, pkg-config and runtime policies
provide no Windows command authority and are not imported here.

| Supplier | Assigned Windows targets |
| --- | --- |
| ICU 77.1 | `ICU::data`, `ICU::i18n`, `ICU::uc` |
| zlib 1.3.1 | `ZLIB::ZLIB` |
| Brotli 1.1.0 | `Brotli::dec`, `Brotli::common` |
| libpng 1.6.43 | `PNG::PNG` |
| libjpeg-turbo 3.0.4 | `JPEG::JPEG` |
| WebP 1.4.0 | `WebP::libwebp`, `WebP::demux`, `WebP::sharpyuv` |
| HarfBuzz 9.0.0 | `HarfBuzz::HarfBuzz`, `HarfBuzz::ICU` |
| libxml2 2.12.9 | `LibXml2::LibXml2` |
| SQLite 3.46.1 | `SQLite3::SQLite3` |
| OpenSSL 3.5.0 | `OpenSSL::SSL`, `OpenSSL::Crypto` |
| nghttp2 1.64.0 | `FoundationNative::nghttp2` |
| libpsl 0.21.5 | `LibPSL::LibPSL` |
| curl 8.17.0 | `CURL::libcurl` |

Freetype and Fontconfig are absent. WOFF2 requires a separately versioned source
and reviewed command closure. All three WebP targets must use the same source
archive, extracted source inventory, configure/build instance, exact toolchain
and original receipt. `required_links` records only the known prerequisite that
libwebp retains sharpyuv and demux retains libwebp. These entries are not complete
ordered link maps. Actual Windows library filenames, includes, static macros,
ordered transitive/system links, header/data outputs and license/notice closure
remain to be derived from reviewed Windows supplier entrypoints and artifacts.

`source-review.json` deliberately gives every supplier `status=unreviewed`, empty
entrypoint/command/tool/patch arrays and a null artifact map. Empty arrays mean
the review has not identified those requirements; they do not establish that a
supplier needs no tools or patches. Review exact retained source members and
their bytes before admitting a literal configure/build/install/probe graph.
ICU, OpenSSL and libpsl need particular attention to their actual Windows routes.
If an entrypoint requires another tool, retain and independently pin that exact
build-only tool/runtime closure or report it as missing. No guessed command,
ambient package lookup, shell fallback or source download may fill this gap.

The single exported C callable in `static-closure-probe.cpp` returns an ABI tag;
its minimal executable `main()` checks that tag without calling a supplier API.
The source has not been compiled, linked or executed, and no runtime probe is
claimed.
A future useful static-closure probe needs reviewed actual linker argv with
`/WHOLEARCHIVE` for every one of the twenty exact selected static archives,
their complete ordered link closure and admitted toolchain/CRT inputs. Retain
actual compile/object/archive/link inputs, original logs, output hashes and
COFF/static-CRT/import/export inspection. Calling the tag function alone proves
no supplier linkage, runtime behavior or operating-system compatibility.

Three independent gaps remain: supplier command/patch/artifact review is
unfinished implementation; actual retained source, LLVM/MSVC/Windows SDK and
host-tool inventories must still be independently admitted; actual dependency
production and later engine/runtime/platform qualification have not run. A
source-metadata pass cannot close any of the latter gaps. The next action is an
explicitly scoped review of the thirteen exact suppliers' Windows entrypoint
bodies, followed by implementation and pure fixtures for the resulting commands.
Only after those prerequisites exist may a separately authorized native build
use the supported `tools/build.py` route described in
[appended applications](../../docs/appended-applications.md). There is no direct
CMake workaround for this missing recipe.

The controller also keeps original program-version admission explicitly
unfinished. Its native byte/inventory checker can inspect pinned executables,
CRT archives, complete runtime trees and the actual controller, but the existing
inventory provenance carries only hashed `original_reports`; there is no typed
original version-observation format or semantic reader binding all selected tool
versions to those executable bytes. Copying H's declared versions would not
reconstruct actual facts. The current native checker therefore raises
`windows-dependency-original-tool-version-observations`. The next source action
is to define and implement that bounded original evidence reader in the new
proof/controller modules, with exact per-role observation methods and original
tool/runtime/command/log/closed-owner joins. Select literal version commands or
native resource readers through that review; do not guess `--version` for every
tool. This is missing controller source and later original evidence, separate
from native filesystem or platform qualification.

The eventual original dependency receipt must join exact selection/plan bytes,
all recipe/helper/cache/source-review bytes, thirteen supplier replay receipts,
the independently reconstructed toolchain identity and actual owned command,
log, output and closed-process evidence. It must bind the final dependency
`inventory_subject_sha256` (inventory excluding `provenance`) and exact twenty
library map. Provenance may reference that receipt; final full inventory and
native-input manifest are written afterward. Do not put their later full hashes
back into the original receipt: preserve the acyclic direction
`H -> D/prefix/manifest -> R/S -> B/header/handoff`, where H is the independently
typed toolchain identity and D is the original dependency receipt.
An arbitrary hashed report or serialized closure flag is
not original producer evidence. Successful future admission would establish
only an unqualified dependency candidate; it cannot set engine execution,
eligible SDK, native runtime, kernel rebuild or release qualification facts.

The initial new dependency receipt and toolchain identity (D/H) schemas
conservatively accept ASCII Windows path declarations only and reject `~` short
name spellings. This avoids treating
Python Unicode case-folding as equivalent to native Windows path comparison. It
does not change the existing Windows input contract's UTF-8 path policy or
establish native path admission; that still requires the actual qualified
Windows verifier.

Implementation checks for this scaffold are pure metadata and source-text
checks only. No supplier entrypoint, SDK/tool/archive/product body, generated
command, compiler, CMake configure, build, runtime, network operation or binary
qualification was exercised. Existing deferred obligations remain in
[pending appended qualification](../../.agent-pending/appended-kernel-qualification.md).
