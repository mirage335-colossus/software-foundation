# Quote Pad appended application

Quote Pad is an ordinary `org.example.quote-pad` project in BOTH mode with the
web page as startup. The page provides Quote and Notes tabs, a checked-total
form, editable quote and notes areas, and Bold and Undo controls. Its portable C
provider computes `left + right + QUOTE_ADJUSTMENT` using checked uint32
arithmetic and reports the call count. The provider schema is in
`src-bin-appended/provider-schema.json`.

The HTML, CSS and JavaScript live under `src-web-appended/`; portable C source
lives under `src-bin-appended/`. Tests and the planned interaction outline are
outside the binary source root. No JavaScript dependencies or backend-specific
page code are required.

This example was promoted from the accepted NC571-v1 component at
`.agent-work/appended-implementation-20261016/ordinary-quote-pad-application-v1/NC571-v1`.
Its source manifest SHA-256 is
`9f78925b6e7051084201a3d95214a6b6a213cc6cd3934a731c8354f62e675b74`; its
component acceptance is `strong-v1/ROOT-ACCEPTANCE-v1.json` (SHA-256
`3a4d8fa057ebea34a56bcfc8e5f71ce72484e3692471e75907b2c329b14cd272`). The
selected NC625-v1 package-only preparation is documented at
`.agent-work/appended-implementation-20261016/ordinary-quote-pad-public-preparation-v1/NC625-v1/PREPARATION.md`.
It identifies the provider-requiring package (SHA-256
`0016c3c2417aa245ac6af4f1045a2cdb082a3bb5cbb71e4c9022840e1cba5740`); the
sibling package without provider declarations is not the selected one.

These records establish component source and package verification only. The
package has no independently pinned kernel or artifact and is not runnable.
This promotion does not claim a public launch, engine integration, browser
behavior, performance, or release qualification. The source-side protocol and
actual-Wasm fixtures passed in the accepted preparation; the latter uses a
modeled serialized owner and does not establish native-owner or browser
behavior. `scenarios/quote-pad-edit-plan.json` is explicitly non-executable and
is a planning aid, not a public launch packet or qualification schema.

## Build and inspect

From the repository root, inspect the example or rewrite its configuration:

```sh
./build.sh project inspect --root examples/appended-quote-pad --json
./build.sh project configure --root examples/appended-quote-pad --mode both \
  --application-id org.example.quote-pad --name 'Quote Pad' --version 0.1.0 \
  --web-source src-web-appended --web-entry index.html \
  --binary-source src-bin-appended --primary web --kernel-profile both
```

Compile the portable provider with an explicitly verified guest SDK as described
in [the appended SDK guide](../../sdk/appended/README.md):

```sh
mkdir -p build/quotepad-example
./build.sh appended compile --source examples/appended-quote-pad/src-bin-appended \
  --language c --entry c/quote_total.c --sdk /path/to/verified-guest-sdk/sdk.json \
  --output build/quotepad-example/quote-pad.wasm \
  --receipt build/quotepad-example/quote-pad.compile.json
```

### C++ and Rust providers

The equivalent C++17 and allocation-free Rust providers use the same pinned
schema, checked uint32 arithmetic and serialized lifecycle as the C provider.
Select one module when packing. The Rust SDK descriptor must additionally pin
the supported `wasm32v1-none` compiler and target libraries.

```sh
mkdir -p build/quotepad-cpp build/quotepad-rust
./build.sh appended compile --source examples/appended-quote-pad/src-bin-appended/cpp \
  --language c++ --entry quote_total.cpp --sdk /path/to/verified-guest-sdk/sdk.json \
  --output build/quotepad-cpp/quote-pad.wasm \
  --receipt build/quotepad-cpp/quote-pad.compile.json
./build.sh appended compile --source examples/appended-quote-pad/src-bin-appended/rust \
  --language rust --entry quote_total.rs --sdk /path/to/verified-rust-guest-sdk/sdk.json \
  --output build/quotepad-rust/quote-pad.wasm \
  --receipt build/quotepad-rust/quote-pad.compile.json
```

Each provider starts with `QUOTE_ADJUSTMENT` equal to 1, giving 43 for operands
20 and 22. Change it to 2 in a separate source copy and compile to a new output
to get 44. This edit compiles only the selected portable module. It needs no
script runtime or package manager. Node is used only by the optional development
fixtures below.

The same actual-Wasm fixture accepts either language's adjustment-one and
adjustment-two modules. For example, after compiling both C++ variants:

```sh
node examples/appended-quote-pad/tests/quote-pad-wasm.test.mjs \
  gui/host/appended_web_services.mjs \
  build/quotepad-cpp/quote-pad.wasm \
  build/quotepad-cpp/quote-pad-adjustment-two.wasm \
  build/quotepad-cpp/quote-pad-wasm-report.json
```

### Package the selected provider

Pack with the module-provider capability declared, then verify the package:

```sh
./build.sh appended pack --project-root examples/appended-quote-pad \
  --binary-module build/quotepad-example/quote-pad.wasm \
  --require-service foundation.providers \
  --require-capability foundation.providers.v1 \
  --output build/quotepad-example/quote-pad.sfapp
./build.sh appended verify --input build/quotepad-example/quote-pad.sfapp \
  --expected-mode both
```

The focused Node protocol fixture can run without compiling a module:

```sh
node examples/appended-quote-pad/tests/quote-pad-protocol.test.mjs
```

The actual-Wasm fixture additionally needs the compiled modules and maintained
public facade; see its usage message for the exact argument order. It checks the
guest SDK and public facade over a modeled owner only. Neither fixture
qualifies native kernel or browser execution.
