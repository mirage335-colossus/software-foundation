# Adopted ordinary-source example

This small independent project consumes retained generated C++ from a form and
a flow. Build it without an editor executable, toolkit or Rust compiler:

```sh
cmake -S editor/examples/demo -B build/editor-demo -G Ninja
cmake --build build/editor-demo --parallel 2
build/editor-demo/foundation-editor-demo
```

The executable uses the display-free reference GUI adapter and checks real event
dispatch, dropdown replacement, text changes, button lockout and reliable GUI
completion messages. Its graph has two float input streams and four independently
accounted output streams: sum, difference, twice-rate trace, and half-rate integer
metrics. Tiny bounded queues exercise backpressure. The ordinary
`ordinary_algorithms.hpp` function object and `foreign.hpp` C ABI calls are injected
by `main.cpp`, used by factories in `blocks.cpp`, and return ordinary values.
`handlers.cpp` demonstrates helpers called from event code and stream processing
posting owned commands without borrowing the GUI model. Services outlive the
graph and its callbacks; the composition root joins before destruction.

Open `project.json` in the editor with this directory as workspace root. Form
widgets and flow blocks open `handlers.cpp` and `blocks.cpp` on double-click.
After design changes, Save/Generate before building. Editing ordinary C++ source
requires only the normal build. CMake compiles retained headers directly and never
runs the editor or generation; handwritten code is excluded from regeneration.

To demonstrate actual Rust linking when an existing native `rustc` is available,
compile the crate without Cargo or external dependencies and select its archive
in a separate demo build. These commands are explicit project development actions:

```sh
mkdir -p build/editor-demo-rust-input
rustc editor/examples/demo/rust/gain.rs --crate-name foundation_demo_gain \
  --crate-type staticlib --edition 2021 -C panic=abort -C opt-level=2 \
  -o build/editor-demo-rust-input/libfoundation_demo_gain.a
cmake -S editor/examples/demo -B build/editor-demo-rust -G Ninja \
  -DFOUNDATION_DEMO_RUST_ARCHIVE="$PWD/build/editor-demo-rust-input/libfoundation_demo_gain.a"
cmake --build build/editor-demo-rust --parallel 2
build/editor-demo-rust/foundation-editor-demo
```

The Rust shim exports the same scalar functions as the default C++ implementation.
It accepts an opaque owned-by-caller context and a synchronous C callback, showing
both directions of interoperability. The C++ callback is `noexcept`; exceptions
must be translated to explicit status inside any more elaborate callback.
This optional crate is not an editor dependency, SDK package or automatic build.
Target/toolchain selection and support qualification remain the project's normal
responsibility; these native commands do not establish other-platform evidence.
