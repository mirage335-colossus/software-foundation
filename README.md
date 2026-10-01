# Software Foundation

A generic reference repository for developing, testing, maintaining and delivering
software. The application is deliberately domain-neutral: an owning, bounded record
collection, a command-line application, and an optional shared GUI application.
The engineering mechanisms are comprehensive: application size does not reduce
coordination, supply, recovery or qualification requirements. C++20 and CMake make the build and binary compatibility examples concrete;
the ownership, testing, documentation and delivery rules apply across languages.

Start with the [engineering contract](docs/engineering-contract.md),
[requirements and practice map](docs/requirements.md), [repository map](docs/architecture.md),
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
| Application | Library, CLI, validation, owned data, stable IDs | Bounded in-memory record contract with explicit failure guarantees |
| Build | One CMake graph, presets, wrapper, focused prerequisite targets | One build tree per configuration and toolchain |
| Tests | Contract checks, tool regressions, installed consumer, disjoint shards | Full means all tests enabled in that configuration |
| GUI | All seven hosts use one feature/controller/layout; native, browser and Wasm fixtures | [GUI audit](docs/gui-audit.md) records actual coverage and the unresolved redistribution gate |
| SDK | Source producer, strict prepared-input archives, source replay, relocation, host/target checks, Windows and browser recipes | Cold native SDK production requires the declared Bookworm builder |
| Packages | Native TGZ/ZIP, full member inventory, runtime closure/ABI audits, relocation and external consumer | A native build alone cannot establish an older runtime floor |
| CI | Disjoint source scopes, independent producers/copied-package jobs, explicit faster pools, sanitizer and supply checks | Hosted workflows need execution on a configured remote before claiming hosted qualification |
| Coordination | Scoped review, guarded saves, descriptor-relative atomic publication, handoffs, lifecycle and concurrency tests | Unsupported filesystem APIs require a qualified adapter or enforced private checkouts |
| Releases | Immutable complete groups, mandatory per-release copies, offline recovery and exact-byte certification | No remote is configured or publication performed |
| Distribution | Debian, Arch and Gentoo wrapping, signed indexes, payload verification, atomic update/rollback checks | Native installation remains a separately named qualification scope |

[Validation](docs/validation.md) records what has actually run and what remains
unverified. Planned platforms and release gates are requirements, not claimed passes.

The [practice map](docs/practice-map.json) provides requirement-to-implementation-to-test
navigation. It is checked for missing references, and does not substitute for the
[actual validation record](docs/validation.md).

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
