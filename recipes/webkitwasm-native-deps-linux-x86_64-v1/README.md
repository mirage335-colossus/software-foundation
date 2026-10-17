# Candidate Linux x86_64 native dependency recipe

This separate, offline CMake superbuild describes fifteen pinned retained source
archives for the native engine prototype. It has not been configured, compiled,
linked or run against a real native toolchain. Its presence does not establish a
native prefix, an eligible SDK, runtime compatibility or redistribution closure.
The supported wrapper prepares and pins these sources and every tool, sysroot,
asset and notice before selecting this recipe. Actual build execution requires
the separately bounded native diagnostic authorization.

`profile.json` is the fixed source and static link contract. Its component order
is also the component install order: each project depends on its immediate
predecessor, including installation. Each child build receives exactly four jobs;
there can be only one child build at a time. The outer graph uses no compiler and
provides the `native-dependencies` target. Configure, build and installation
are CMake graph operations. There is no fetch, source patch, recovery build,
package-manager invocation or global installation.

The generated `-C` cache supplies the exact common names in `cmake_inputs`, plus
the seventeen `private_runtime.cmake_inputs` only for the explicit private SDK
toolchain kind. `NATIVE_PIC_RUNTIME_MODE` is `generic-pic-v1` for the original
toolchain formats or `private-static-gcc-sdk-v1` for that private kind; a missing
private selection fails instead of switching modes. `SOURCE_*`
paths name writable, fully admitted extractions with their archive strip prefix
already removed. `NATIVE_WORK` contains fresh child build trees; `NATIVE_PREFIX`
is their private output. They must be disjoint from source/toolchain inputs.
`NATIVE_TOOLCHAIN` and `NATIVE_SYSROOT` identify the admitted native compiler
configuration and actual target sysroot. `PROGRAM_*` names ordinary retained host
programs, without program discovery. The orchestrator fences PATH to the admitted
program directories and supplies the fixed native environment. Compiler flags are
the fixed `-fPIC -march=x86-64 -mtune=generic` baseline; the sysroot is passed
explicitly to both CMake and non-CMake children. No `-static` linker policy is
used: it would disable OpenSSL's native thread/PIC configuration. The generated
flag strings append `--sysroot=ABSOLUTE_ADMITTED_SYSROOT`. Producer output,
sysroot and program paths are restricted to absolute `/[A-Za-z0-9_./+\-]+`
literal shell words at this boundary because the retained make/configure
programs place them in shell command text. CMake cache literal values also reject
`|`, the private ExternalProject list separator.
GNU make receives the admitted `SHELL` explicitly. Upstream CMake/Ninja shell
execution additionally needs the declared build host OS runtime; static input
admission does not establish complete process/runtime qualification.

CMake children search only the private prefix and declared sysroot for headers,
libraries and packages. Optional dependencies are explicitly disabled. pkg-config
has one private `PKG_CONFIG_LIBDIR` and no ambient path/sysroot override. Autotools
receives explicit native CC/CXX/AR/RANLIB, Python, Perl, gperf and static dependency
closures. The admitted PATH is also necessary for upstream bare helper names.
Autoconf option checking is fatal, so an unrecognized reviewed switch cannot
silently continue to compilation.
No default host font, certificate, json-c, Expat, IDN, SSH, HTTP/3 or optional TLS
implementation is selected.

Only selected static archives, headers and `.pc` metadata are staged by the
recipe-owned install adapter. zlib's unconditional shared target, Brotli's encoder
and CLI, and upstream global install targets are never selected. ICU builds its
native generators because static data packaging requires them; they are not
installed. Fontconfig likewise builds only its required code generators and
library, and never runs `fc-cache`. WebP retains `sharpyuv` because `libwebp` links
it. JPEG and OpenSSL assembly are disabled as an initial fixed capability choice.
The WebP source dispatch policy retains its upstream per-source CPU checks under
the global SSE2 baseline; this still needs real CPU/runtime qualification.

The selected retained Fontconfig XML, fonts, ICU data, CA bundle and notice list
are copied without modification. Their original manifests remain the authority
for bytes, origin and licensing. The prefix contains no installed executable or
generated system font cache. It retains the selected Fontconfig XML at
`etc/fonts/fonts.conf`; the actual native consumer must explicitly select this
configuration, its private cache and retained fonts. Copying data does not prove
ICU initialization, font discovery or TLS behavior.

The standalone source entry point is:

```sh
python3 tools/appended_engine_native_dependencies.py plan \
  --selection /ABS/selection.json --selection-sha256 EXACT_SHA256 \
  --output /ABS/fresh-plan
PYTHONDONTWRITEBYTECODE=1 /ABS/admitted-python tools/appended_engine_native_dependencies.py build \
  --plan /ABS/fresh-plan/plan.json --plan-sha256 EXACT_SHA256 \
  --output /ABS/fresh-build
```

The supported root dispatcher is a separate integration. `plan` is passive and
never configures or builds. `build` remains the separately authorized costly
native diagnostic; the commands above are syntax, not execution evidence.
The build controller's resolved executable must exactly match the selected
`host_tools.programs.python` and its admitted runtime inventories. Bytecode
writing must already be disabled before invocation, so retained SDK trees stay
unchanged. The supported wrapper form sets
`PYTHONDONTWRITEBYTECODE=1 PYTHON=/ABS/admitted-python` before `./build.sh
native-engine-dependencies build ...`. A mismatch fails before preparation,
output creation or any subprocess; passive planning does not require that
controller. The original build receipt records its actual path, pinned bytes,
no-bytecode policy and selected runtime closure.

Selection v1 has exactly `schema_version`, `kind`, `target`, `archives`,
`toolchain`, `host_tools`, `assets` and `phase_limits`. Its kind is
`foundation-native-engine-dependencies-selection-v1`; each input is an
independently pinned document reference. The sources document has exactly
`schema_version`, `kind`, `archives` and `notices`, with kind
`foundation-native-engine-dependency-sources-v1`. Its archive map has the fifteen
logical component keys in this profile. Each archive entry has exactly `path`,
`sha256`, `bytes`, `format`, `strip_prefix` and `normalizations`. The last is an
explicit map of stripped link member to stripped ordinary target, permitting
only direct same-archive link-to-regular materialization with no chains. It
never grants general dereferencing. Original notices form a required nonempty
list of pinned references. Unknown/missing roles and unsafe source projections
fail admission before any native graph.

Every plan also pins the fixed thirteen recipe files, eight producer helpers,
`tools/appended_engine_native_sdk.py` and
`recipes/webkitwasm-native-rich4083-v1/producer/native-sdk-toolchain.cmake.in`.
The last two are transitive source controls of the optional SDK-backed input
parser, and remain in the fixed closure for explicit-toolchain selections too.
Their original bytes and physical identities participate in capture, recheck
and plan verification. This source-only authority does not relax the strict
mode or inventory rules for retained SDK, prefix or asset inputs.
The original twenty-three source-control names retain their exact original
capture authority. Eleven shared controls additionally participate in
every plan: `private-cpp-runtime-policy-v1.json`, `native-private-runtime.cmake`
and `verify-provider.cmake` in the native rich recipe's `producer` directory,
`tools/appended_engine_native_original_proof.py`, and
`tools/appended_engine_native_prototype.py`, plus
`tools/appended_engine_native_role7.py` and the `tools/role7/` package's
`__init__.py`, `common.py`, `observer.py`, `capture.py` and `os_origins.py`.
The passive original-proof and ROLE7 consumers are retained as transitive source
controls; retaining them does not establish an original host, package or
observation proof. These eleven use the same fixed
native twenty-file authority as the toolchain parser; policy capture through
both paths must agree. Both toolchain and host parsing receive the caller's
explicit repository root. An SDK-backed controller records the original Python
interpreter binding and validated runtime facts without requiring a redundant
legacy module inventory.

The phase limits bind `prepare_seconds`, `configure_seconds`, `build_seconds`,
`cleanup_seconds`, `maximum_jobs`, `maximum_output_bytes`, `minimum_free_bytes`
and `maximum_process_tree_bytes`. The aggregate compilation cap is exactly four;
the wrapper runs the serialized superbuild with one outer job. Time, output,
space and process-tree limits are declared bounds, not measured resource facts.

Before installation, the adapter checks the child's selected static/native
options and generated feature headers, including curl's HTTP/2/TLS/PSL/Brotli/
zlib/native-thread features and Fontconfig's libxml2/no-json-c choice. Missing
outputs or an unexpected feature fail the graph. These checks are configuration
checks, not archive architecture/PIC proof.

After all fifteen components install, the serial `native-pic` CMake child links
`foundation-native-dependencies-pic-check`. It places every object from all 22
declared archives inside one GNU whole-archive group, using the admitted C++
compiler/sysroot with `-Wl,-z,defs` and `-Wl,-z,text`. The final system links are
exactly `Threads::Threads`, `m`, `dl`, `rt` and `atomic`. An archive cannot be
omitted to recover from an undefined symbol, duplicate symbol or relocation
failure. Its output is
`NATIVE_WORK/pic/libfoundation-native-dependencies-pic-check.so`; it is never
installed, loaded or run. `profile.json` binds the complete ordered target list,
output and link policy in `pic_check`.

The PIC child records `ordered-archives.txt` and, only after a successful link,
uses the admitted Ninja's nonexecuting `-t commands` query to save
`pic-commands.log` plus `pic-commands.stderr.log`. This CMake-owned post-build
step uses no shell redirection. The build also prints its verbose command. The
parent producer must bind all 22 actual ordered archive hashes, that command
evidence, DSO hash and admitted inspection-tool outputs for ELF header, dynamic
dependencies and relocations. It must reject text relocations and unadmitted
runtime dependencies before recording a successful PIC gate. This gate proves
the actual combined link only; it supplies no native API/runtime/font/TLS result.
The parent publishes the complete prefix inventory and original build receipt
only after all graph and inspection steps pass. It retains failure logs and
rejects partial prefixes. This recipe never writes `engine-sdk.json` or an
eligibility/qualification assertion.

The private SDK toolchain adds a target-local policy to this same all-member
PIC target. It uses the shared `bib_apply_private_cpp_runtime` function and the
validated five SDK runtime/startup files, with `-static-libstdc++`,
`-static-libgcc`, hidden archive exports, GNU `--trace` and a link map. Component
builds keep their original flags. The map is fixed at
`NATIVE_WORK/pic/evidence/dependency-runtime-link.map`. CMake derives a fixed
67-byte export policy from the captured PIC source, exposing only
`foundation_native_dependency_pic_probe`; no public provider ABI is claimed.
The exact selected runtime files must occur in both actual trace and map;
foreign static runtimes and shared C++/unwind libraries fail the shared pure
prototype verifier. No runtime archive is placed in the dependency whole-archive
group, which remains exactly the same twenty-two archives.

After linking, the producer invokes the captured shared CMake ELF verifier with
the closed `dependencies-pic-v1` selector, admitted inspector and original
runtime allowlist. Its dynamic-symbol, dynamic-section and version checks must
pass, including the private runtime's GLIBC 2.36 baseline, before the producer
can record `pic: true` or publish `dependencies.json`. The private PIC receipt
binds the selection, actual ordered archive inputs, trace/map, export-map bytes,
DSO, verifier source and inspection logs. Its kind differs from the original
generic PIC receipt. Both modes leave the DSO unloaded and unexecuted; neither
proves native engine behavior, complete toolchain qualification or release
eligibility. The implementation has only pure and fake-process validation until
an explicitly authorized real dependency build completes these gates.

The option spellings were reviewed against the retained archive source tables on
2026-10-17. Native configure/link behavior, generated public header closure,
static system-library closure, relocatability, full license obligations and
runtime initialization remain unexecuted. Unexpected supplier requirements are
concrete maintenance failures; they do not authorize an ambient dependency or a
fallback patch.

The final finite target/helper reads retained twelve exact member pins in
`source-review.json`. Each serial archive-reader attempt had a 55-second hard
limit. The initial eight-member read took 0.981 seconds and matched all four
original archive pins. A subsequent curl helper read saved three named members
then stopped because the exact requested `FindLibPSL.cmake` spelling was absent;
the saved root callsite established `FindLibpsl.cmake`, which a separately granted
single-member read retained in 0.145 seconds. This history is preserved. The
reads performed zero native configure, compiler, link, runtime or test calls.
They establish selected target names, generator order and curl's actual generated
feature macros and library-discovery variable names; they supply no build pass.
