# Windows candidate adapter

`tools/appended_engine_windows_prototype.py` implements finite Windows command
planning, retained byte/inventory consistency checks, static PE/COFF inspection,
and Windows Job Object supervision. It consumes the separate POSIX-prepared
immutable handoff without regenerating or rewriting its R/S/B metadata, generated
header, or Windows dependency paths. The templates configure the existing
`PORT=Foundation` WebCore/JavaScriptCore/provider graph with native x64 clang-cl,
lld-link, C++23, Release, `/MT`, and an SSE2 baseline. Individually dispatched
source leaves retain their existing source properties.

This is unfinished producer implementation. Every plan reports
`executable_plan=false`, `build=false`, `production_eligible=false`,
`native_runtime_qualified=false`, `engine_execution=false`, and
`kernel_rebuild=false`. `build` first requires a native Windows x64 Python host,
rechecks its selected inputs, then raises named `MissingInputs` before creating a
directory, opening an output log, or launching a program. Three implementation
admissions remain absent:

- A project-qualified Windows handle-relative, reparse-safe, durable publication
  adapter with identity checks and no replacement of existing paths. POSIX
  publication helpers, caller booleans, and self-declared qualification records
  cannot supply this authority.
- Original supplier extraction and reviewed overlay replay admission for the
  handed-off assembled source. An independently pinned inventory establishes
  transfer consistency, not supplier replay.
- The original complete native dependency producer proof, including static
  Release CRT provenance. COFF byte checks and retained provenance references
  cannot establish that execution or qualification.

No release SDK, runtime proof, provider execution, native compile, or native
Windows qualification has been produced by this work.

## Inputs and passive commands

The selection is a closed JSON object:

```json
{
  "schema_version": 1,
  "kind": "foundation-native-engine-windows-prototype-selection-v1",
  "handoff": {"root": "C:/retained/windows-handoff", "sha256": "INDEPENDENT_HANDOFF_PIN"},
  "admission": {"path": "C:/records/windows-admission.json", "sha256": "INDEPENDENT_ADMISSION_PIN"},
  "output_root": "C:/private/fresh-candidate",
  "phase_limits": {
    "configure_seconds": 1800,
    "build_seconds": 14400,
    "cleanup_seconds": 30,
    "maximum_jobs": 4,
    "maximum_processes": 256,
    "maximum_output_bytes": 68719476736,
    "maximum_log_bytes": 67108864
  }
}
```

Pins are exact nonzero lowercase SHA256 values; the uppercase names above are
explanatory placeholders and fail validation. Paths use the shared canonical
local Windows path policy. Output must be disjoint from the handoff, selection,
admission, every inventory/provenance record, all referenced original source,
notice and report paths, and all retained input roots. This includes original
authority files stored outside those roots. Plans retain the complete protected
path list, print JSON to stdout and do not save it.

```powershell
python -B tools/appended_engine_windows_prototype.py plan --selection C:/records/selection.json --selection-sha256 EXACT_SELECTION_PIN
python -B tools/appended_engine_windows_prototype.py inspect-provider --provider C:/candidate/provider.dll --provider-sha256 EXACT_PROVIDER_PIN
```

The admission record has kind
`foundation-native-engine-windows-admission-v1`, schema version 1, the shared
Windows target, and exact `handoff_sha256`, `recipe_sha256`, `sources_sha256`,
`provider_build_sha256`, `metadata_header_sha256`, and
`toolchain_identity_sha256` joins. Its finite `inventories` map has exactly
`llvm`, `msvc_stl`, `windows_sdk`, `host_generators`, `native_dependencies`, and
`product_assets`. Each value is an independently pinned `{path, sha256}` record.
`programs` and `program_versions` have exactly `compiler`, `linker`, `archiver`,
`resource_compiler`, `manifest_tool`, `cmake`, `ninja`, `python`, `perl`, `ruby`,
and `gperf`. Programs are pinned ordinary PE32+ x64 executable files. LLVM tools
must share the native input manifest's exact release. Additional fields are
`builtins` (a pinned LLVM static archive), `crt_libraries` (exactly `libcmt`,
`libcpmt`, `libvcruntime`, `libucrt`, `oldnames`, each pinned), explicit
`include_directories`, `library_directories`, and `system_root`.

Each inventory has kind `foundation-windows-retained-inventory-v1`, schema
version 1, its exact `role`, shared `target`, canonical `root`, explicit `version`,
complete `files` mapping relative paths to `{sha256, bytes}`, sorted complete
`directories`, and a pinned `provenance` reference. Files, directories, casing,
sizes, hashes, reparse points and extra entries are checked. Provenance has kind
`foundation-windows-retained-provenance-v1`, schema version 1, matching `role`
and `target`, `inventory_subject_sha256` (SHA256 of the canonical inventory
without its `provenance` field), and nonempty bounded arrays of pinned original
`sources`, `notices`, and `original_reports`. Those original bytes are read and
hashed; a status string does not replace them. These schemas intentionally do not
claim supplier replay or qualification.

Private tool/runtime DLLs need unique inventory identities and explicit loader
search locations. Forwarded exports, bound imports, delayed imports and CLR
metadata require a separately reviewed policy. Static dependency archives reject
thin archives, foreign/import objects, aliased names, dynamic/debug CRT requests,
and linker directives that can select ambient paths or outputs. Ordinary COFF
and BigObj validate primary/auxiliary symbol boundaries and relocation symbol
indices; relocation-overflow sections fail closed. Both
Microsoft archive linker-index forms are bounded and checked.

## Validation boundary

The focused command is:

```sh
python3 -B -m unittest discover -s tests -p test_appended_engine_windows_prototype.py -v
```

The fixtures use tiny synthetic PE/COFF bytes, temporary metadata, and mocked
Job owners. They never launch a compiler, host generator, SDK utility, provider,
or native build. `run_owned` requires a caller-owned private tree and binary log;
it supervises through `process_tree`, checks wall/output/log/process-count
bounds, calls `finish` before accepting parent success, and joins/closes the Job.
Uncertain launch, cleanup or close retains explicit output ownership and permits
no success receipt. It makes no memory-limit claim. Real Windows publication,
toolchains, supplier/dependency replay, full compile/link, final PE inspection,
runtime gates and retained-SDK admission remain separate unfinished work or
applicable manual qualification, as described above.
