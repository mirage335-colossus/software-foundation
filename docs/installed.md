# Installed Software Foundation package

This native package contains `foundation-cli`, the static developer library,
public headers, a CMake package export, build information and license notices.
It does not install a background service or modify system configuration.

Extract the archive into a directory you own. Run `bin/foundation-cli --help`
(or `bin/foundation-cli.exe --help` on Windows) from that directory. Use
`--version`, `--self-check`, or `-- "First entry" "Second entry"` to exercise it.
The collection is in-memory; it does not persist records. Remove the extracted
directory to uninstall an archive installation. Do not overwrite a separately
managed installation with an extracted archive.

`build-info.txt` records the producing compiler and target. A native build does
not imply support for older operating-system runtimes. Use the release's stated
compatibility matrix and validation report when deploying to another system.

## Developer package

With a matching C++20 toolchain, configure your consumer with
`-DCMAKE_PREFIX_PATH=/absolute/extracted/prefix` and use:

```cmake
find_package(Foundation 0.1 CONFIG REQUIRED)
add_executable(example main.cpp)
target_link_libraries(example PRIVATE foundation::core)
```

Include `<foundation/store.hpp>` and `<foundation/version.hpp>`. The collection
owns its data, returns independent copies, accepts 1–256 printable ASCII bytes
per record, and requires caller-serialized access. Invalid input throws; IDs are
stable for the lifetime of each collection. The static C++ library requires a
compatible compiler, standard library and runtime configuration. This package
is not a standalone compiler/sysroot SDK.

The accompanying `LICENSE` applies to this package's own code.
`third_party/dependencies.json` records dependency status. Optional GUI adapters
are not included. The matching source repository provides the full development
specification, tests and reproducible build instructions.
