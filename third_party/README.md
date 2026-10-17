# Dependency records

This directory holds dependency identity and maintenance information. The
default core library and CLI do not vendor third-party application libraries.
Compiler, standard-library, operating-system, build-tool, and optional GUI
requirements are documented separately from that statement.

[`dependencies.json`](dependencies.json) is the machine-readable inventory.
[`docs/dependencies.md`](../docs/dependencies.md) defines required provenance,
license, integration, and upgrade records. Copy
[`docs/templates/dependency.md`](../docs/templates/dependency.md) when adding a
dependency and link its record from the inventory.

For vendored source, use `third_party/NAME/` and keep exact upstream notices.
Keep local patches in a documented series with upstream context. For prepared
SDKs, retain recipes under an explicitly named tracked subdirectory and put
downloaded/generated files in ignored storage. Do not check a compiled SDK into
Git. Ordinary CMake configuration must not fetch dependencies.

Optional external checkouts must be explicitly selected and pinned. Do not
silently discover a sibling repository and use whichever revision happens to
be present. GUI builds default to the complete preserved source group in
[`gui-inputs/`](gui-inputs/), so ordinary Linux builds need only the checkout and
the documented distribution build/development packages. An explicitly selected
source checkout or input group takes precedence. The default core-only build
does not restore or verify this optional group.

## Preserved GUI source

`gui-inputs/` contains byte-identical `gui-inputs.tar.gz`, `manifest.json` and
`SHA256SUMS` from the reviewed group for gui-boundary revision
`7a704f73e563a167ea335dd23ccd9f383ebec274`. The manifest SHA-256 is
`5eec1117f0f075e74860a5d6daa5e795ca24abb0c5010a011d257f941e5ed373`.
It preserves the complete supplier tree, notices, retained Rev/GLEW/FreeType
inputs, and this project's exact integration lock and patches. FLTK and SDL2 for
ordinary Linux builds come from distribution development packages; prepared SDK
builds use their retained SDK libraries. This group contains no compiled SDK.

Verify with `python3 -B gui/source_group.py verify third_party/gui-inputs`.
The strict three-file directory must contain no extra documentation or outputs.
To upgrade, review the upstream revision, licenses, complete source tree and
integration changes using [the dependency procedure](../docs/dependencies.md);
update the lock/patches together, export a fresh group using
[the GUI source-group tool](../docs/gui-boundary.md#complete-offline-gui-input-group),
verify it against the updated checkout, and replace all three files together.
Run the source-group fixtures and affected GUI build/tests before delivery.
Keep exact supplier notices and owner-specific Rev permission scope; this
retention does not grant downstream users new supplier permissions.

## Prepared input producers

`third_party/sdk/` contains separate native source, browser-target and Windows
dependency recipes. Producing code lives under `tools/`; generated caches and
archives belong under ignored, owned build directories or a durable external
store. The native recipe pins maintained old-runtime sources and recent tools.
The browser recipe preserves exact precompiled upstream inputs explicitly. The
Windows recipe keeps Microsoft host tools separate from redistributable inputs.

Every prepared group contains matched binary/source/checksum assets and complete
inner inventories. Every binary release retains its own exact copies. See
[the SDK lifecycle](../docs/sdk.md) and [release assembly](../docs/releases.md).

## Optional rich-engine inputs

[The retained engine format](appended-engine/README.md) defines complete
source/binary/checksum groups and strict integrity, export and restore tooling.
These groups keep a future engine's C++23 producer separate from the C++20
application host and bind its exact sources, patches, tools, data and notices.
The reviewed [copied259 source projection](../recipes/webkitwasm-copied259-v1/README.md)
preserves the selected implementation and provenance. The actual
[baseline engine probe](../docs/appended-web-feasibility.md) supplies diagnostic
evidence; production build/import integration and runtime qualification remain
in progress. Ordinary configuration acquires no engine inputs.
