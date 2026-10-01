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
be present. The GUI source is supplied through the documented optional
integration and is not vendored into this repository. Its license and complete
dependency inventory remain release prerequisites.

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
