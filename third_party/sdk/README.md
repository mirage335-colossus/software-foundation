# Pinned source SDK recipe

`recipe.json` pins Buildroot 2026.08 and a maintained glibc 2.36 source revision by
complete SHA-256. `config` selects GCC 15, C++ support and native CMake, Ninja and
Python. The recipe is application-independent. It carries no optional GUI library;
extensions must add selected library recipes, upstream notices and qualification.

The producing host baseline is Debian 12 Bookworm x86_64. Bootstrap tools come
from ordinary distro packages listed in `recipe.json`; no retired distro mirror
is needed. Explicit preparation fetches upstream archives once and preserves all
resolved inputs. Application jobs consume the retained compiled SDK. The native
SDK target remains glibc 2.36 even though its compiler is newer.

The full recipe identity includes every producing helper as well as both recipe
files. `distro_sdk.py fetch` stores selected transitive downloads and a resolution
record. `build` verifies those bytes, disables upstream download commands, builds
the compiler and target libraries, preserves legal notices, inspects imported ABI
requirements, and exports the binary/source/checksum group. No missing input may
silently trigger a newer version or a cold build during application CI.

This recipe's cold build has not yet been qualified in this repository. Pinned
inputs and implemented commands are reproducible maintenance inputs, not evidence
that a toolchain has passed its host/runtime matrix. Publish a base only after
fresh installation, relocation, compiler smoke and native oldest-host checks.

See [the SDK lifecycle](../../docs/sdk.md) for complete commands and recovery.
