# Software Foundation

A generic reference repository for developing, testing, maintaining and delivering
software. The executable example is deliberately small: an owning, bounded record
collection, a command-line application, and an optional shared GUI application.
The engineering requirements apply to larger projects without prescribing their
features. C++20 and CMake make the build and binary compatibility examples concrete;
the ownership, testing, documentation and delivery rules apply across languages.

Start with the [requirements](docs/requirements.md), [repository map](docs/architecture.md),
and [documentation index](docs/README.md). Contributors and automated assistants
read [AGENTS.md](AGENTS.md) before editing shared resources.

## Run the example

Requires CMake 3.24+, Ninja, a C++20 compiler, and Python 3.9+ for tooling/tests.
On Windows, use a developer command prompt with MSVC and run the Python entry
point shown below. Configuring the project never downloads dependencies.

```sh
./build.sh
./build/dev/foundation-cli -- "First entry" "Second entry"
./build.sh test dev --label core --jobs 2
./build.sh test release --full --jobs 2
./build.sh package release --jobs 2
```

```powershell
python tools/build.py test release --full --jobs 2
python tools/build.py package release --jobs 2
```

The library installs as CMake package `Foundation`, target `foundation::core`.
[The external consumer](examples/consumer/CMakeLists.txt) demonstrates finding it
after installation. [COMPILE](COMPILE) is the short command reference;
[building](docs/building.md) explains configuration, concurrency and SDK use.

## What is executable here

| Area | Included example | Qualification boundary |
| --- | --- | --- |
| Application | Library, CLI, validation, owned data, stable IDs | A small teaching application, not a persistence service |
| Build | One CMake graph, presets, wrapper, focused prerequisite targets | One build tree per configuration and toolchain |
| Tests | Contract checks, tool regressions, installed consumer, disjoint shards | Full means all tests enabled in that configuration |
| GUI | One shared application using pinned terminal and framebuffer adapters; optional FLTK | See [GUI audit](docs/gui-audit.md) for vocabulary, display and dependency limits |
| SDK | Manifest validation and Linux target sysroot toolchain entry point | A prepared compiler/sysroot must be supplied; no compiled SDK is shipped |
| Packages | Native TGZ/ZIP, complete member inventory, relocation and consumer test | Native package is not an old-OS compatibility claim |
| CI | Lightweight automatic checks, manual full matrix, separate sanitizer lane | Workflow files are examples until executed on an actual remote |
| Coordination | Tested cooperative board with claims, handoff and job lifecycle | Shared filesystem coordination does not enforce source access permissions |
| Releases | Immutable asset, compatibility, source retention and package-repository requirements | No remote publication or signed package repository is configured |

[Validation](docs/validation.md) records what has actually run and what remains
unverified. Planned platforms and release gates are requirements, not claimed passes.

## Use this as a project specification

1. Adopt the repository map and replace the small application with your own.
2. Define supported environments and observable compatibility contracts before
   adding implementation. Keep interfaces independent of delivery mechanisms.
3. Fill dependency records, SDK recipes and release inventories with real pinned
   inputs. Do not carry example placeholders into published metadata.
4. Keep the short development loop and full qualification as explicit separate
   scopes. Preserve failures and omissions when reporting evidence.
5. Reuse the [GUI boundary](docs/gui-boundary.md) and the
   [shared-workspace protocol](docs/agent-coordination.md) when applicable.

The code and documentation authored in this repository use the [MIT license](LICENSE).
External dependencies retain their own terms; the [inventory](third_party/README.md)
records the optional GUI dependency's unresolved top-level license statement.
