# Appended applications

The project/configuration, container,
portable-module, retained-candidate and strict rich-browser producer tools
described here are implemented. The complete
[rich web application plan](appended-application-plan.md#current-continuation-handoff)
is still in progress. Retained-engine and private partial-BOTH runtime checks
have passed, but complete Foundation runtime and ordinary public application
integration remain unaccepted. The current handoff and
[validation record](appended-validation.md) distinguish those results from the
earlier [engine feasibility work](appended-web-feasibility.md).
Packaging HTML resources does not establish execution.

The ordinary project has no `foundation-project.json` and selects neither layer.
Its application binaries and runtime dependencies retain their ordinary path.
The optional binary kernel uses a pinned wasm3 interpreter and project-owned
service/view interfaces. Developer/build Python is not a shipped application
runtime; the C/C++/Rust guest SDK requires no script runtime or package manager.

## Select an independent application

The maintained [QuotePad example](../examples/appended-quote-pad/README.md)
combines ordinary HTML/CSS/JavaScript forms, tabs and rich editing with a small
portable C provider. Its README gives component checks and packaging commands,
and identifies the remaining public-host qualification.

`fork.sh` preserves its exact initial snapshot, independent root, absent remote
and reviewable attribution edits. Configure the application after forking:

```sh
./build.sh project inspect --json
./build.sh project configure --mode binary --application-id org.example.meter \
  --name Meter --version 0.1.0
```

The supported modes are `neither`, `web`, `binary` and `both`. Configuring a mode
does not build, download or instantiate its runtime. Enabled source roots must
exist; the web component requires a declared existing entry file. Disabled roots
are not prerequisites. Binary module readiness remains unverified until compilation
and packing validate an actual module. Source directories alone never prove it.
Standalone configuration and packing accept custom source roots; retained-kernel
eligibility and CI reuse currently require `src-web-appended` and `src-bin-appended`.

`kernel.profile` is independent of payload presence: `auto`, `minimal`, `web`,
`binary` or `both`. A deliberately selected superset remains selected when removing
a component. Removing payloads cannot remove already-linked runtimes. A profile
with insufficient capabilities fails. Product identity, startup owner, source
selection and retained-kernel provenance are separate settings.
Maintenance admission respects the selected profile even after all payloads have
been removed. An explicit profile cannot silently become a smaller kernel build;
the supported wrapper admits web-bearing maintenance only with an independently
pinned compatible neutral engine group and paired browser SDK, before native
toolchain discovery. No eligible production group or runtime proof exists yet.

The native kernel currently implements the binary capability. `web`/`both` remain
valid project and package modes but need an actual compatible engine-bearing
kernel before execution. Conventional native build commands in an appended project
require an explicit maintenance flag; they never silently rebuild for payload edits.

## Portable module development

Application code belongs in `src-bin-appended/`. C and C++ bindings are in
`sdk/appended/include/`; the allocation-free Rust crate is in
`sdk/appended/rust/`. The SDK common C runtime owns allocation, startup and the
seven scalar entry points. All public wire values use explicit little-endian
encoding, not native structure layouts.

Supply an explicitly pinned guest SDK manifest to the compile tool. It inventories
all tool/target-library files; no toolchain is downloaded or selected from PATH.
The current freestanding C/C++ path uses LLVM/LLD. The separate Rust guest profile
requires Rust 1.84 or newer with `wasm32v1-none`; this does not change the kernel's
Rust 1.63 policy. See [the SDK instructions](../sdk/appended/README.md).

```sh
./build.sh appended compile --source src-bin-appended --language c \
  --entry c/calculator.c --sdk /retained/guest-sdk/sdk.json \
  --output build/calculator.wasm --receipt build/calculator.compile.json
```

`foundation-guest-v1` is core wasm32 MVP scalar instructions plus mutable globals:
one defined, exported, finitely bounded unshared memory; at most one finite table;
the exact scalar exports; and at most the one `foundation.kernel.v1/call` import.
The profile excludes WASI, start sections, threads, SIMD, exception proposals,
multivalue and proposal-prefixed instructions. Limits include 4 MiB module bytes,
256 memory pages and 8192 table entries. Canonical LEB and complete instruction
typing are checked. The native interpreter independently checks actual input
bytes and validates every body before invoking the ABI query.

The service gateway discovers versioned namespaced native services. Handle zero
is bootstrap control; other handles are instance-local. Bounded canonical records,
generation checks, result ownership, identical-request replay and explicit ACK
retirement are implemented. Keep application protocol/layout decisions on this
side of the GUI boundary. Any native function needs a deliberate service wrapper;
a retained kernel cannot provide code absent from that kernel.

The dispatcher and module-owned providers are synchronous and serialized. Deferred
guest jobs and device UART implementations remain unfinished. There is no automatic
retry of uncertain external effects and no promise of crash-proof exactly-once I/O.
See [the wire contract](../abi/appended/v1/README.md) for implemented statuses,
bootstrap schemas and golden vectors.

## Module-owned application providers

`foundation.providers` version 1.0 lets a module deliberately register its own
namespaced application contracts during initialization. Each contract declares
its major/minor version, schema identity and maximum request/reply sizes;
`foundation.*` remains reserved for kernel interfaces. Provider handles belong to
one module generation and are distinct from native Registry handles. Registering
an application contract does not install a native service callback for that name.
See [the provider schema](../abi/appended/providers/v1.json),
[C constants](../include/foundation/appended/provider_abi.h) and
[host interface](../include/foundation/appended/providers.hpp).

The composition owner constructs `ModuleProviders` after `Module`, before module
initialization, using exactly the same Registry. Initialize the module, then
activate its providers. Keep that Registry alive through both objects and destroy
the provider bridge before the Module. All operations use the same serialized
owner; the owner and Module must remain alive throughout callbacks and complete
public invocations. Recursive shutdown requests are allowed; recursive destruction
is not.

Discovery matches the application name, major, minor range and optional exact
schema. Invocation carries the module generation, a host request sequence,
provider handle, operation and bounded payload. The module must explicitly
respond exactly once during that dispatch, including an explicit empty payload
when appropriate. A response is provisional until the whole guest dispatch and
guest free complete successfully. Missing responses, traps, failures after a
response or a fresh duplicate response cannot become success. Deferred provider
jobs, cancellation, module-to-module calls and hot replacement are not implemented.

Host invocation replay is separate from guest gateway replay. An identical
retained host retry returns its saved outcome without executing the provider
again; conflicting bytes fail, and acknowledged or skipped old sequences expire.
The owner explicitly retires outcomes with `acknowledge(through_sequence)`.
Default bounds are 32 registered providers, 32 KiB payloads, 64 retained calls and
1 MiB retained request/reply reservations. Registration and response SDK helpers
also acknowledge their completed gateway outcomes in the application's single
gateway sequence domain.

The [GUI composition API](../gui/shared/appended_application.hpp) exposes
`discover_provider`, `invoke_provider` and `acknowledge_provider`; provider and
view events share one outbound sequence, and returned outcomes own their bytes.
A composition owner queues a provider request until its renderer/native/engine
callback returns, invokes it outside every active Registry or Module invocation,
then delivers completion after `invoke` returns. The provider bridge does not
supply that queue or permit synchronous engine reentry. A future website binding
must follow this ordering; the rich HTML engine and that binding remain unfinished.
Application provider code and its C/C++/Rust SDK need no JavaScript.

`src-bin-appended/c/provider_counter.c` is a small provider-only example. Compile
it with `--entry c/provider_counter.c` instead of the calculator entry. It
registers `org.example.increment` 1.0: operation one accepts a little-endian
32-bit unsigned operand and returns its incremented value and invocation count,
both modulo 2^32. The website fixture can discover this optional provider
independently of the native echo service; neither action requires page code
for a GUI backend or module runtime.

## Produce a kernel once

An existing release without append support cannot gain it merely by appending.
Initial binary capabilities require an explicit source build:

```sh
./build.sh build dev --appended-profile binary --kernel-maintenance \
  --build-dir build/appended-native
```

Select the normal provider/SDK inputs required by [building](building.md).
For focused native checks when intentionally using the compatibility provider,
add `--core-provider cpp`. No default provider is changed by this feature.
The optional interpreter source is checked before configuration; missing or
changed inputs fail without acquisition. Its exact full upstream archive,
reviewed two-line compiler-counter patch, derived compilation sources and notices
are retained in
[third_party/wasm3](../third_party/wasm3/README.md).

Finalize a freshly produced **installed** executable after strip/install/RPATH
operations. This one-time producer step writes a reserved read-only pristine-size
stamp, adds any required ELF padding and records the complete final hash:

```sh
./build.sh appended kernel-seal --input /owned/installed/bin/foundation-appended-kernel \
  --output build/retained/kernel --descriptor build/retained/kernel.json \
  --service foundation.diagnostics --service foundation.providers \
  --capability foundation.providers.v1 \
  --source-root "$PWD" --developer-unqualified
```

`--developer-unqualified` explicitly records development origin; it supplies no
release qualification or source-to-binary reconstruction proof. A production
producer supplies its actual provenance. Re-sealing a finalized or composed
artifact is rejected. Both output paths must be new and outside source inputs.
Retain the descriptor's independent SHA-256 pin along with the artifact and its
original source, SDK, archive/runtime inventory and evidence.
Declare only services/capabilities actually compiled into that kernel. Supplying
`--service` replaces the console diagnostics default; `foundation.kernel` is
always included. These declarations do not add code to an older retained kernel.

The console kernel verifies self bytes/metadata, initializes a module and exposes
`foundation.diagnostics` for a generic service-call demonstration. `--inspect`
shows verified package metadata without executing code; `--expect-mode` makes a
missing required component fail. `--dispatch-hex` sends a complete typed event
envelope; a raw text argument is not the calculator record format.
It also supports `--provider NAME [--provider-operation N]
[--provider-payload-hex HEX]`. This console entry discovers application contract
version 1.0; operation defaults to 1 and payload defaults to empty. An explicit
operation must be a positive uint32. It prints the provider name, numeric service
status and hexadecimal result, then acknowledges the outcome. Provider calls
cannot be combined with dispatch, inspect or help in the same invocation.

## Pack, replace and strip

```sh
./build.sh appended pack --project-root "$PWD" --binary-module build/calculator.wasm \
  --output build/application.sfapp
./build.sh appended compose --input /retained/kernel \
  --kernel-descriptor /retained/kernel.json \
  --kernel-descriptor-sha256 EXACT_DESCRIPTOR_SHA256 \
  --package build/application.sfapp --output build/meter
./build.sh appended verify --input build/meter \
  --kernel-descriptor /retained/kernel.json \
  --kernel-descriptor-sha256 EXACT_DESCRIPTOR_SHA256 --expected-mode binary
```

Packing can declare required kernel services and capabilities with repeatable
`--require-service NAME` and `--require-capability NAME`. Names must be distinct;
duplicates fail. `--require-abi-minor MINOR` defaults to 0 and accepts 0 through
65535, with ABI major fixed at 1. For a module using application providers, add
`--require-service foundation.providers --require-capability
foundation.providers.v1` to its pack command. A module using generic views can
also require `foundation.view` and `foundation.view.v1`.

These are explicit package requirements, not capabilities inferred from module
bytes or supplied by packing. Required service names identify kernel gateway
services; application provider contracts are discovered separately through
`ModuleProviders`. Composition checks the requirements against the pinned kernel
descriptor, and startup checks actual availability.

Web-only packing omits `--binary-module`; both mode requires it. The compiler is
never invoked by packing. Use the previous verified composed file as `--input`
to replace its complete owned suffix. This preserves the pinned kernel prefix
and leaves exactly one package. Removing one component removes all its previous
files while preserving unchanged files in the other. `compose --no-payload`
returns the pristine kernel, as does `strip`:

```sh
./build.sh appended strip --input build/meter \
  --kernel-descriptor /retained/kernel.json \
  --kernel-descriptor-sha256 EXACT_DESCRIPTOR_SHA256 --output build/pristine
```

All operations preserve inputs and publish new outputs without overwriting an
existing or concurrently appearing destination. They do not configure, compile,
link, install, strip or rewrite the retained kernel. Missing/mismatched profiles,
services, hashes or source eligibility fail with maintenance needs.

The opt-in `pack --rich-startup` route additionally requires a configured web or
both project with an explicit `startup.primary` of `web`, `compiled` or `binary`.
Ordinary web-primary packing generates `web/.foundation/startup-v1.json` and
requires `foundation.startup.v1`. Compiled or binary primary generates
`web/.foundation/startup-v2.json` and additionally requires
`foundation.gui-composition.v1`; an explicit composition capability selects
version two for web primary too. Binary primary requires both components, the
`foundation.view` service and `foundation.view.v1` capability. These ordinary
hashed resources select startup without changing the package format. User
sources cannot occupy the reserved namespace, including empty directories or
case aliases. Web and compiled primary can use the binary as a service provider,
but cannot require secondary binary views. The runtime validates the metadata
before creating a module or page, and composition checks the retained kernel's
actual capabilities. The integrated production rich runtime remains unfinished;
this packaging option supplies neither an engine nor a compatible retained
kernel. Legacy packing, including binary package bytes, does not implicitly add
this resource.

The C++ [logical reader](../include/foundation/appended/container.hpp)
`read_package` verifies bounded data/index bytes and owns all resource copies.
Its package and index hashes describe those logical bytes; `kernel_sha256` is
empty. Callers must separately check carrier/trailer framing and prefix identity.
Reading decoded browser bytes cannot authenticate the original HTML prefix;
the external raw-file verifier still performs that check.

The native format supports stamped ELF and unsigned executable PE. Authenticode
inputs, DLLs and arbitrary native overlays are rejected. Native absence is known
from the producer-established pristine boundary; partial/truncated suffixes fail.
Completely removing a suffix is indistinguishable from a pristine kernel unless
an independent expected-mode requirement exists.

The HTML format uses an immutable shell, an inert base64 package/trailer block
and canonical ending. The binary browser producer below supplies an executable
shell; a minimal reference shell is also available for container tests. The same
logical package hash spans native and HTML carriers; framing does not enter the
payload identity. DOM-only code cannot prove raw file prefix/tail integrity.
External verification checks complete bytes. The binary browser GUI does not
supply an internal HTML engine for web payloads. Direct raw-Wasm carriers are not
offered.

## Portable binary views

`foundation.view` exposes generic GUI values through the same versioned gateway.
The module supplies widget state and layout; the kernel translates those values
into the existing shared GUI contract. The C example
[`view_calculator.c`](../src-bin-appended/c/view_calculator.c) has two editable
fields, a Sum button and a result. It contains no backend or browser code.

The initial view capability implements atomic full snapshots with revision and
generation checks, common controls, pages, menus, shortcuts, immutable bitmap
resources and queued generic host-service completions. Presentation occurs after
the module invocation returns. Adapter failure can retry presentation without
repeating guest work. The [wire schema](../abi/appended/view/v1.json) lists precise
limits and the operations not yet implemented, including imperative focus,
selection, scrolling, palette changes and text measurement.

Build a terminal carrier once by adding `--gui --gui-backends terminal` to the
explicit binary kernel build. Seal the installed `foundation-appended-terminal`
with `--service foundation.view --service foundation.providers --capability
foundation.view.v1 --capability foundation.providers.v1`. Pack the compiled
`c/view_calculator.c` module and compose it
with that retained carrier. Ordinary terminal adapter controls and focus apply.
This is a binary-defined view, independent of the unfinished HTML TUI renderer.

For an offline browser carrier, initially build the explicit binary profile with
`--gui --gui-backends wasm --sdk /retained/browser-sdk`. Its target
`foundation-gui-appended-web-wasm` uses the same C++ interpreter and view service.
Finalize its already compiled outputs in a new directory:

```sh
./build.sh appended browser-kernel --assets build/browser/gui/web \
  --module-dir build/browser/gui --source-root "$PWD" \
  --output build/retained-browser --sdk /retained/browser-sdk \
  --notice foundation=LICENSE --notice gui-boundary=/retained/gui/LICENSE \
  --notice wasm3=third_party/wasm3/LICENSE \
  --notice xxhash=third_party/wasm3/XXHASH-LICENSE
```

The producer retains the exact compiled assets, notices and observed source/SDK
identities in `foundation-appended-browser.html` and `kernel.json`. It neither
builds nor downloads anything and does not prove source-to-binary reconstruction.
For a newly compiled provider-capable browser kernel, add `--providers` to the
initial producer command. That policy includes `foundation.providers` and
`foundation.providers.v1` alongside the view service/capability. The producer
requires an actual Wasm function export named `gui_web_providers_v1`; its current
kernel implementation returns `0x00010000`. The producer inspects the export
section without executing that function or certifying its return value. An older
compiled base without the export cannot acquire the provider capability through
new metadata or appended bytes.

Use `browser-kernel --output build/retained-browser --verify` to check its inventory.
Verification detects the retained known policy; `--providers --verify` is rejected.
Compose the portable binary with that HTML prefix using the ordinary descriptor
pin. The resulting single HTML file opens offline and executes the portable
module in the shared interpreter. Web payloads remain explicitly unsupported.
Removing the binary displays an empty-kernel status without starting a module.
Browser-specific Worker and DOM transport stay in the kernel; no JavaScript is
added to the guest source or SDK.

## Explicit retained engine maintenance

`engine-maintenance` is a separate developer operation for the initial copied259
engine candidate. It requires prepared, independently pinned source and SDK
inputs plus a complete retained baseline reuse proof. It has no cold-build,
download or supplier-build fallback. Payload and `engine-sdk` integrity actions
never dispatch to it.

```sh
./build.sh engine-maintenance plan \
  --profile webkitwasm-copied259-v1 \
  --sources /retained/successor-sources --recipe-sha256 NEW_R --sources-sha256 NEW_S \
  --projection /retained/successor-sources/provenance/source-projection.json \
  --projection-sha256 EXACT_PROJECTION \
  --sdk /retained/paired-sdk --sdk-manifest-sha256 EXACT_SDK \
  --reuse-root /retained/baseline --reuse-proof /retained/baseline/reuse-proof.json \
  --reuse-proof-sha256 EXACT_REUSE --output /owned/new-engine-plan
./build.sh engine-maintenance build \
  --plan /owned/new-engine-plan/plan.json --plan-sha256 EXACT_PLAN \
  --output /owned/new-engine-candidate --jobs 2 --timeout-seconds 1800
```

`plan` verifies inputs without launching programs. Only the explicit `build`
action invokes the maintained CMake graph: 24 selected objects, five regular
archive repacks with ordered-member readback, one neutral factory link and
artifact inspection. Frozen private cache copies and an owned Python launcher
keep the original SDK read only, including child tools that use Python's `-E`.
The graph does not configure the supplier engine or the Foundation application.
Host CMake, Ninja and Python are explicit pinned developer prerequisites.

The candidate receipt always says `production_eligible: false`. This operation
does not produce runtime proof, an eligible retained SDK or a kernel. Its current
source has focused fixture and independent review evidence. The first actual
build failed on copied header aliases; a later attempt compiled the repaired
owners and exposed an archive-index alignment issue. The third attempt compiled
all 24 selected objects, verified all five archives and linked, then failed
static inspection because required Wasm exports had been renamed. The supported
linker switch preserving those names is being integrated; no actual copied
runtime check has run. These closed failures and historical recipes retain
their own identities. See [current validation](appended-validation.md)
and the [retained-input format](../third_party/appended-engine/README.md).

The separate document-v2 producer uses the same supported entry point:

```sh
./build.sh engine-maintenance document-plan --help
./build.sh engine-maintenance document-build \
  --plan /owned/new-document-plan/plan.json --plan-sha256 EXACT_DOCUMENT_PLAN \
  --output /owned/new-document-candidate --jobs 2 --timeout-seconds 1800
```

`document-plan` requires an explicit pixel/physical/editor selection, its retained
profile, complete source/projection pins, paired SDK and reuse-proof pins.
It launches no programs. `document-build` accepts only that independently pinned
plan and selects its closed incremental graph; it has no supplier-build or
ordinary application-build fallback. These aliases dispatch before native
provider/toolchain selection. The source-only assembly and synthetic planner
checks do not establish an actual document-engine build or runtime result.

The editor successful-donor continuation has three explicit contracts. The original
`--successful-donor` lane imports49 objects and compiles Publisher plus document
shim. `--successful-donor-guard-repair` uses its distinct guard-repair descriptor,
48imports/3fresh/170artifacts. The separately selected
`--successful-donor-composition-repair` requires
`foundation-document-v2-successful-donor-composition-repair-v1`, adds Backend and
main to the fresh units and admits46 ordered imports/5fresh/168artifacts. All
retain51 selected objects, five archive copies, zero repacks and one link, with
strict distinct plan/build/Root kinds. Historical receipts retain their identities.

The composition branch permits exactly the reviewed Backend/main body changes,
two main-only private header changes and one new Backend/main bridge header.
It preserves the pinned SDK, opaque dependencies, include search and VFS. Search
context uses the complete authenticated original51 dependency coordinates,
including directories used only by fresh units. Root readback must parse all five
fresh depfiles and prove those header owners.
Editor-specific source origins preserve pixel/physical profile bytes. These are
retained selective maintenance routes with no supplier or kernel build fallback.
Refresh source/helper/proof pins and complete the reviewed bounded launch before
execution. The Guard candidate has accepted Wasm build evidence; its complete
runtime failed composition cancellation. The source repair passes focused host
journal checks, while the new five-unit candidate and runtime remain unverified;
see the [current handoff](appended-application-plan.md#current-continuation-handoff).

## Initial rich browser producer

The separate rich route has source admission, a retained-engine consumer and a
pure single-file carrier producer. It is **not currently runnable end to end**:
no production-eligible neutral engine group and matching Foundation runtime
receipt have been produced. The successful diagnostic engine prototype is not
that group. Source-only native provider and version-two document/form candidates
are also not runnable retained engines.

Initial Foundation maintenance accepts only `web` or `both`, with GUI enabled,
the Wasm browser backend and a verified paired Emscripten wasm32 SDK. It consumes
an already retained application-neutral engine; it never compiles or fetches that
engine. The wrapper verifies the complete group and all four independent pins
before discovering build programs or configuring. Direct CMake rechecks the
consumer after compiler initialization and before creating the optional graph;
a cached verification boolean cannot bypass that check. Missing or incompatible
inputs report concrete maintenance needs without selecting a fallback build.

The current copied document/editor profile has a fixed 800 by 600 engine
viewport and no resize promise. Its start parser, build facts and first-frame
contract enforce those dimensions. Variable engine viewport support remains
implementation work requiring an explicit compatible contract extension. A
small-viewport popup test cannot be reported as passing on this profile; the
shared popup owner's small-viewport component checks do not supply that runtime
capability.

The selected document renderer also emits a full viewport rectangle on advance.
Its source does not establish a partial-damage path for scrolling. Full-frame
rendering and the generic dirty-region helper must not be reported as a verified
partial-damage implementation. The diagnostic probe records that limitation
separately from its mandatory neutral-engine checks.

Once real eligible inputs exist, the explicit maintenance command has this shape.
Each hash variable must contain the independently obtained hash of the named
retained document; these are required inputs, not example passing proofs:

```sh
./build.sh build release --core-provider cpp --sdk /retained/browser-sdk \
  --gui --gui-backends wasm --kernel-maintenance --appended-profile web \
  --engine-group /retained/neutral-engine \
  --engine-recipe-sha256 "$ENGINE_RECIPE_SHA256" \
  --engine-manifest-sha256 "$ENGINE_MANIFEST_SHA256" \
  --engine-proof-sha256 "$ENGINE_PROOF_SHA256" \
  --engine-runtime-sha256 "$ENGINE_RUNTIME_SHA256" \
  --build-dir build/appended-engine
```

`web` links the package/native-service owner without `Module`, module providers
or wasm3. `both` adds the deliberate module binding and interpreter leaf. The
ordinary neither graph and existing binary producers remain separate. The
new host emits `gui_appended_engine_wasm.js` and
`gui_appended_engine_wasm.wasm`. Its read-only
`gui_web_engine_profile_v1()` export returns 1 for `web` and 2 for `both`.

The [consumer](../tools/appended_engine_consumer.py) extends retained byte
integrity with exact provider/build/runtime evidence, actual typed Wasm
imports/exports/memory facts and an inert ES-module factory policy. Recipe,
binary manifest, provider proof and runtime report each need their own pin;
`engine-sdk` integrity inspection alone grants no production eligibility. The
initial copied bridge uses ABI `0x00010000`, provider ABI 1.0 and exact effective
capabilities 259. The application composition roots register the shared
`demo.echo` native service described below. A raw provider's wider catalog or a
metadata flag cannot add implemented services.

Foundation kernel factories have a separate dependency policy from retained
engine factories. The rich producers accept dependency-free ES modules and the
reviewed Emscripten `web,worker,node` adapter shape: generated `globalThis` Node
detection, guarded `createRequire` from `node:module`, and guarded builtin reads
from `node:fs`, `node:path` and `node:url`. No general dynamic import, arbitrary
require, altered guard, CommonJS export or additional child-module edge is
admitted. The generated Node guard permits its single initializer and fixed
boolean tests; writes, aliases, shadow bindings, destructuring and property uses
of that guard name reject. Other generator shapes require a reviewed policy
extension. Inspection
checks a temporary lexical projection and leaves the retained factory bytes
unchanged. It records the Node dependencies explicitly; runtime inertness still
requires the separately pinned observations. The engine and browser child-module
scanners retain their existing stricter policies.

After explicit Foundation maintenance and real runtime checks, retain a separate
Foundation receipt and its independent hash. It must bind the actual factory and
Wasm bytes, full target and paired SDK, source projection, typed exports, the
observed compiled-profile query before configuration and the matching engine
`DESCRIBE` result. No receipt generator or successful real receipt is claimed
here. The pure [rich producer](../tools/package_appended_engine_wasm.py) then
uses those already produced inputs:

```sh
./build.sh appended rich-browser-kernel --assets build/appended-engine/gui/web \
  --kernel-module-dir build/appended-engine/gui --source-root "$PWD" --profile web \
  --engine-group /retained/neutral-engine \
  --engine-recipe-sha256 "$ENGINE_RECIPE_SHA256" \
  --engine-manifest-sha256 "$ENGINE_MANIFEST_SHA256" \
  --engine-proof-sha256 "$ENGINE_PROOF_SHA256" \
  --engine-runtime-sha256 "$ENGINE_RUNTIME_SHA256" \
  --kernel-receipt /retained/proofs/foundation-web.json \
  --kernel-receipt-sha256 "$FOUNDATION_KERNEL_RECEIPT_SHA256" \
  --notice foundation=LICENSE --developer-unqualified \
  --output build/retained-rich-web
./build.sh appended rich-browser-kernel --verify --output build/retained-rich-web \
  --descriptor-sha256 "$RICH_DESCRIPTOR_SHA256"
```

The initial producer requires `--developer-unqualified`. This records development
origin and skips only final release certification; it cannot skip engine,
Foundation, compiled-profile or runtime facts. Parser fixtures remain
production-ineligible. Verification reads retained policy; production flags
cannot upgrade it. The output inventory is exactly
`foundation-appended-engine-browser.html`, `kernel.json` and `manifest.sha256`.

The immutable prefix contains separate Foundation and neutral-engine factories
and Wasm assets, fixed modules, original reports and notices. One direct Worker
owns both instances; the known Wasm lookup names are explicit, with no inferred
basename or network fallback. Unknown lookups fail. External `.data` packages
currently reject pending an owned-byte preload path. Exact artifact lengths and
separate role limits are checked; provisional ceilings are not measurements of
a production neutral engine. The entire encoded prefix must fit the 512 MiB
carrier limit. Its new `renderer_surface_child_bundle.mjs` is separate from the
unchanged binary child graph and producer inventory. Ordinary compose, strip and
reappend retain the exact prefix and replace only the owned suffix.

The document-v2 source route is selected separately with
`--engine-document-profile pixel` (1795) or `physical` (2003) during browser kernel
maintenance. It uses its own verified compiled facts and the
[`document-browser-kernel` producer](../tools/package_appended_engine_document_wasm.py).
That pure packaging action requires the same independent engine pins plus a
document runtime receipt and an explicit `--document-profile pixel|physical`.
It cannot promote parser fixtures or rebuild an engine. Its entry and packaging
tests passed; an eligible document engine and Foundation runtime receipt remain
unavailable.

The separate native source route selects `--engine-native-document-profile pixel`
or the independent `--engine-native-actions-profile document-actions-v1`, with an
existing matching Linux SDK or verified Windows dependency export. These selectors
are mutually exclusive with each other and the browser/legacy physical selectors.
They require their own retained facts and runtime inventory. Pixel1795 is
view-only; document-actions4083 supplies the shared document, physical-input and
editor contract. A selector cannot substitute fixture facts for a provider.

The graph creates `foundation-appended-engine-terminal` and
`foundation-appended-engine-framebuffer`, plus `foundation-appended-engine-sdl`,
`foundation-appended-engine-fltk` and `foundation-appended-engine-rev` for selected
native GUI backends. The bitmap hosts share one application composition and
engine. The bare framebuffer entry requires an output PPM path and is always
view-only; windowed4083 hosts can select `--view-only` explicitly. Only `both`
links the guest module binding. Ordinary GUI hosts retain their existing behavior.

At launch, `--engine-runtime-root ABSOLUTE_DIRECTORY` explicitly selects the
verified runtime inventory. New bitmap entries and the4083 terminal entry
otherwise use the compiled executable-relative installed resource location.
Explicit runtime/output paths use UTF-8; the new Windows bitmap entry reads the
original UTF-16 command line before conversion. Lookup does not depend on the
working directory. These sources and focused components do not establish an
eligible native provider, connected HTML TUI, actual window rendering or OS IME
qualification; the [validation record](history/appended-validation-2026-10.md#native-source-and-current-retained-producer-operations)
keeps those limits separate.
These are one-time kernel maintenance routes. Ordinary payload composition
continues to reuse finalized binaries without configure, compile, link or install.

The ordinary copied259 composition advertises no physical input capability.
The opt-in `foundation-engine-copied467-mouse-v1` source successor implements
bounded key/focus/mouse codecs, owner admission/retirement, a generic SurfacePort
and separate physical Worker/bootstrap selection. Its owner, application, codec
and transport checks are component evidence; the ordinary copied259/bitmap path
and disabled compiled facts remain the defaults. The generic `mouse_v1` surface
successor is separately opt-in and retains the legacy profile. Its frozen source
checks do not extend the earlier affected-gate Firefox result to this new graph.

Select this distinct producer path with `--engine-physical-input` during explicit
Foundation web/both maintenance, then `--physical-input` on the pure carrier
producer. Use its complete generated `gui/web-physical` asset directory.
Admission requires the exact physical engine catalog/profile, the actual
read-only compiled input-profile query before engine creation, and original
physical runtime observations bound to every host asset. The private generated
header lives in `appended-engine-physical-input/` inside the build tree. These
checks cannot turn a fixture into an eligible physical engine. The four
producer/consumer files passed 93 focused tooling cases; build admission passed
37 entry cases and a separate strict C++20 generated-header fixture.

Actual engine/provider binding, committed text/IME/editor contexts, selection,
clipboard, popups, native and terminal integration remain unfinished. Reviewed
provider/recipe source and diagnostic metadata are not a production retained SDK
or a runnable kernel. Neither metadata nor a producer seal can turn these gaps
into capabilities. See the
[frozen component results](history/appended-validation-2026-10.md#frozen-physical-input-and-ndv2-component-successors).

A later frozen Linux x86_64 supported-entry graph passed 43 selected component
CTests with no failures, skips or disabled tests, including input owner/codec,
NDV2 values, generic surfaces and affected owner/application/native-driver paths.
Its mocked providers and Node fixtures do not establish an actual engine, browser,
SDK or production kernel. Later build-entry/physical-admission changes are outside
that source identity. See the [supported graph receipt](history/appended-validation-2026-10.md#supported-input-and-ndv2-component-graph).

## Same-document terminal projection utility

[`AppendedDocument`](../gui/shared/appended_document.hpp) consumes disposable
semantic values from one running document; it does not parse HTML or own a
second editable text model. The C++ utility produces generic readable list rows,
link/button controls and original node/source ranges. Generation, epoch and
revision checks reject stale focus, activation and UTF-16 selection intents.
Omission and masked content are preserved. Forms and rich content are presented
read only; actions are returned to the owner rather than executing an engine
inside adapter callbacks.

The caller supplies actual viewport columns/rows and public text measurement.
This avoids treating the terminal adapter's minimum logical canvas as its true
width. Bounds include 2,048 nodes, 65,536 UTF-16 text units, 8,192 rows and a
64 MiB budget for repeated text measurement. Exhaustion retains the displayed
prefix and shows an incomplete-document notice; it does not alter the DOM.

[`The semantic decoder`](../gui/shared/appended_document_codec.hpp) consumes the
exact source-prototype JSON schema with byte, depth, value and Unicode limits.
It preserves editor state, form metadata and native selection offset kinds;
unsupported selections and whitespace have explicit degradation. Empty and
visibility-filtered element forests retain their actual node identities. Tag
names have a separate field bound from the producer's aggregate text budget.

The separate [version-two value codec](../gui/shared/appended_document_v2_codec.hpp)
encodes compositor requests and decodes whole paired document/form publications
against the exact native session identity and NDV2 schema. Unsupported body
actions and values unrepresentable by the current consumer fail explicitly; the
codec does not call an engine or substitute a form action. Its focused and
independent interoperability fixtures passed; actual provider copy buffers,
owner query scheduling and compositor delivery remain unverified against a
real native engine. The component composition below wires their source path.

[`The shared controller`](../gui/shared/appended_document_controller.hpp) owns
decoded snapshots and queues exact-version intents during adapter callbacks.
The composition owner drains requests and returns owned completions outside
those callbacks. Unknown action outcomes cause resynchronization without action
replay; failed presentation can be retried independently. The owner supplies
actual drawable cells and a fresh generation for each replacement document.

The separate [typed form utility](../include/foundation/appended/document_forms.hpp)
defines version-two observations, opaque native leases and deferred form actions.
Its bounded draft helper publishes local text edits synchronously so batched
terminal typing retains the correct source caret. Apply, Reload and Reapply are
explicit; stale or uncertain outcomes preserve the draft and never repeat an
effect. Native values, focus and sanitization remain authoritative. Secure
controls expose no value or selection. This utility has no engine or GUI adapter
and does not extend the strict version-one JSON decoder.

The [forms compositor](../gui/shared/appended_document_forms.hpp) joins body
projection and local form drafts through one presenter and input owner, using
exact native leases and owned deferred completions. Its component checks use
the real retained terminal adapter with mocked native engine replies. Later
unknown-completion corrections have separate standalone and supported native
graph evidence. A subsequent read-only-values correction passed its single
supported compositor rebuild and test; the earlier snapshots retain their
original identities. None establishes an engine connection.

With document-actions-v1, published input controls of type `button`, `reset` and
`submit` use typed activation with their exact observed document version. The
same global reservation, command-10/ACK-11 settlement and fresh-query barrier
apply without creating an editing lease or modal draft. Ordinary button elements
keep their existing body-action route. This addition passed the supported forms
and Owner/wire component checks with mocked native replies; real HTML TUI
execution still requires the native provider.

The native [C-table driver](../gui/shared/native_engine_driver.hpp) consumes
the neutral owner with process-lived callbacks, copied resources and pixels,
deferred native services, ACK receipts and bounded retirement. Its document-v2
path and the [native composition](../gui/shared/native_engine_document_composition.hpp)
now connect the Owner, Driver and terminal presenter in component tests. The
[native loader](../gui/shared/native_engine_loader.hpp) verifies the retained
runtime inventory and C table before startup. Its OS implementations live in
`src/appended/`; generic GUI code contains no OS loading implementation. The
205-test supported component run covers these paths with mock providers. It does
not establish an eligible native engine SDK or an actual HTML TUI runtime. The
older pixel259 evidence keeps its original source identity.

The separately negotiated [surface policy](../include/foundation/gui/surface.hpp)
defines generic key/text/IME, pointer, clipboard and popup values without changing
the existing GUI or guest ABI layouts. It stages presentations, rejects retired
contexts and returns consumed input for later engine dispatch. The generic
browser Session/channel and separate surface renderer now implement a negotiated
key/focus/pointer seam; first-focus balanced pointer and outside-clip capture
passed an affected-gate Firefox probe. This does not enable production-engine
physical capabilities or establish complete adapter input and engine mapping.

These components do not yet establish a working HTML TUI browser. The
[native terminal entry](../gui/hosts/appended_engine_terminal_main.cpp) and
opt-in runner hooks supply the composition source, actual drawable-cell reports,
foreground state and orderly close handling. The entry still needs an eligible
native provider and actual engine runtime validation. Physical rich editing,
complete body actions and native clipboard/popup integration remain unfinished.
They introduce no HTML engine or script runtime into the binary profile and are
excluded from ordinary builds until a consumer selects them. Their focused
native checks are:

```sh
./build.sh test dev --core-provider cpp --gui --gui-backends terminal \
  --kernel-maintenance --appended-profile binary \
  --test foundation.gui.appended-document \
  --test foundation.gui.appended-document-codec \
  --test foundation.gui.appended-document-controller
```

## Queued website service transport

[`WebServices`](../include/foundation/appended/web_services.hpp) provides the
engine-independent transport for a document's native and optional module calls.
It owns a separate native registry and exposes opaque website handles through
the existing discovery schema. Reusable native registrations can deliberately
install the same application wrappers into the website and binary registries;
their request counters and retained results remain independent.

The shared application factory registers `demo.echo` version 1.0 in the browser,
terminal and native composition roots. Operation one echoes at most 1,024 request
bytes; other operations and oversized requests fail before copying. The factory
is an application-owned C++ leaf, independent of the engine and module runtime.
Its native component checks do not establish an actual website-to-Foundation
round trip; that connection still needs the engine and Foundation runtime probe.

Engine callbacks only submit copied requests or control admission. The owner
pumps services after leaving the callback, then delivers owned completion
envelopes after the pump returns. Requests, maximum replies and retention are
bounded before effects; replay, cancellation, acknowledgement and document
replacement have explicit outcomes. Optional module hooks are bound by the
composition root. The transport library links only the value ABI and registry,
so native website services do not require the portable-module interpreter.

The website-only [`JavaScript facade`](../gui/host/appended_web_services.mjs)
provides asynchronous discovery and calls over this transport, preserving
64-bit identities as `bigint`. It is separate from the C/C++/Rust binary SDK.
Generic owner and copied-Worker composition source now connects this transport
to the host boundary. The actual internal-engine binding and its complete
lifecycle execution remain unfinished; their presence does not make the website
runnable inside a kernel.

The selected bitmap/editor application also lacks the shared document
query/form/acknowledgement composition. The terminal document application has
that state machine, but attaching it to the same browser adapter would create
competing presenters. A shared C++ broker and generic typed endpoint remain
implementation work before the browser's combined Foundation runtime checks can
pass. Direct engine calls or neutral host-peer observations cannot supply that
application evidence.

The optional [engine provider contract](../include/foundation/appended/engine_provider.h)
is a separate C host interface, outside the portable module SDK. Versioned values
and copied callbacks isolate the kernel's C++20 runtime from the engine's private
toolchain. Its [guard and adapters](../third_party/appended-engine/PROVIDER-NOTES.md)
check startup lifetime, bounded operations and exact document identities; they
provide no WebCore implementation. Unbound lookup returns `UNSUPPORTED`. Native
DSO/runtime isolation and the actual browser engine binding still require
implementation and execution evidence.

## Retained CI and recoverable candidates

The feedback selector recognizes active appended projects and compares complete
kernel content/mode inventories to a pinned descriptor, without requiring Git
ancestry. Supply `--kernel-descriptor` and `--kernel-descriptor-sha256` to
`tools/ci_changes.py`, or their `FOUNDATION_APPENDED_KERNEL_DESCRIPTOR` and
`FOUNDATION_APPENDED_KERNEL_DESCRIPTOR_SHA256` environment equivalents.
Eligibility also checks the authenticated descriptor's selected profile,
components and baseline ABI. A source inventory alone supplies diagnostics and
cannot grant reuse. Without actual package requirements, the CLI explicitly
reports `package_requirements_checked=false`; composition must still check all
required services, capabilities and ABI minor. API callers may supply bounded
`payload_requirements` for those additional checks.
The current tooling uses `foundation-appended-kernel-v2` input projections.
Reviewed guest-only SDK/compiler files and the pure CI selector are outside that
projection. Their full source and compile/SDK receipt identities still change;
SDK insulation, binding conformance and module-input checks remain required.
Unknown SDK files, root ABI/schema files, validators, native code and supplier
notices remain kernel inputs. Earlier unqualified v1 development descriptors
require an independently issued v2 projection from retained original kernel
source; neither automatic metadata migration nor a kernel rebuild is implied.
Browser inventory verification can still check historical v1 bytes and their
original non-provider policy read-only. That integrity check grants no current
v2 retained-source eligibility and cannot upgrade the old policy to providers.
This tooling projection is separate from carrier format one and service ABI one.

The explicit comparison policy
`foundation-appended-kernel-v2-acquisition-selection-v1` also accepts the canonical
`kernel.selection` change between `project` and `foundation`, provided the profile,
fixed source roots and every other byte and executable mode match. It preserves
the original descriptor/source identities and the distinct `expected_sha256` and
raw `actual_sha256`. Diagnostics retain the actual configuration difference and
add `comparison_policy`, `comparison_sha256` and
`selection_metadata_difference`; check `eligible` rather than assuming that an
empty difference list grants reuse. Profile, component, service, capability and
ABI checks remain independent requirements. This is a specific acquisition
comparison, with no general ignore option or automatic metadata migration.

Unknown/changed kernel inputs and missing pins report maintenance required with
native build flags false. They never select a fallback build. Known inactive
payload-only changes select tooling checks without compiling a module or kernel.

```sh
./build.sh appended policy audit --root "$PWD"
./build.sh appended policy identity --root "$PWD"
./build.sh appended prepare-release --selection /owned/selection.json \
  --output build/composed-candidate
```

The versioned selection explicitly pins each kernel archive, complete member
inventory, descriptor, original source, reconstruction inputs and existing
evidence, plus the downstream complete source and optional application package.
One package can be composed into several selected runtime members; other archive
members, modes and directories retain their exact contents. A null payload
supports neither mode. Recipe script bytes and input groups are retained for
byte-exact recovery. `verify-candidate` checks the candidate inventory;
`verify-composition` additionally checks its semantic subject, selected runtime
prefixes, package and unchanged archive closure. Use each action's `--help` for
the required independent pins.

[The manual Actions workflow](../.github/workflows/appended-compose.yml) acquires
an explicit authenticated retained input group and uploads a candidate artifact.
It does not install a compiler/SDK, invoke native build tools, create a release
or promote a package channel. Upstream acquisition credentials are confined to
that step and independent of downstream publication. A retained acquisition
receipt records the exact source release/asset and observed Actions origin.

### Pack current checkout files against retained carriers

The separate pure preparation operation captures the current application files:

```sh
./build.sh appended prepare-checkout --project-root . \
  --request /owned/checkout-request.json --output build/checkout-candidate
```

It does not run Git, discover a compiler/SDK, configure, compile, link, install or
contact a remote. Its `foundation-appended-checkout-filesystem-v1` source policy
uses the existing no-Git selector and source exclusions. Unknown nonexcluded
files, including files hidden by Git ignore rules, participate in the actual
filesystem capture. Links, special entries, portable path aliases and changing
inputs fail. Logical executable modes use actual stat bits, or validated retained
`source.json` authority on Windows. This policy does not claim a live Git inventory.

Use this exact separate request schema:

```json
{
  "schema_version": 1,
  "kind": "foundation-appended-checkout-request",
  "selection": {"path": "retained/selection.json", "sha256": "INDEPENDENT-64-HEX-PIN"},
  "binary": null
}
```

Paths are portable canonical relative paths resolved from the request's parent.
An optional `requires` field uses the existing strict package requirements
object. `neither` emits a null payload and removes an existing appended suffix.
`web` packs current resources without guest compiler/SDK prerequisites.
Binary and both modes require `binary` to contain `module` and `proof` references,
each with `path` and an independently reviewed `sha256`. The proof must be the
actual separately produced `compile_guest` receipt. Current guest source,
language-specific bindings, helper/validator hashes, module bytes and fresh Wasm
audit must match it. Original SDK, host and command provenance is retained without
executing those tools. A missing or stale proof directs the developer to compile
only the guest separately. An unchanged guest can be reused while editing pages.
The existing selected-source insulation checks run before packing.

The acquired input group stays unchanged. The new group preserves the exact
strict selection reference closure and original selected JSON: source, payload,
kernel archives/inventories/descriptors/original source, and reconstruction and
evidence references. Unrelated sibling files are not read or copied. Unique
capture counts/bytes and composition-consumption bytes, counting repeated
references, are bounded before delegation to the unchanged composer. Capture and
composer buffers coexist; these input bounds are not a single process RSS limit.
The group also contains the current source/package, a new strict old-schema
selection, original request/proof and an unqualified candidate under `candidate/`.
`checkout.json` is published last, with source policy, insulation, retained
identities, comparison diagnostics and a complete output inventory. Existing
candidate/composition/qualification schemas are unchanged. Preparation does not
establish release qualification.

The manual workflow defaults `payload_source` to `frozen-group`. Select `checkout`
to pack the actual checked-out application against the independently authenticated
retained group. `checkout_binary` is JSON `null` for neither/web, or the pinned
module/proof pair inside that group. Optional `checkout_requires` supplies the
strict ABI/service/capability requirements object; `null` uses existing defaults.
Only candidates and recovery inputs are uploaded. Rich startup still requires
web-primary startup; compiled/binary-primary rich startup remains unfinished.

Preparation uses same-filesystem hardlink publication. Directory mode changes
require an owned directory descriptor, `O_NOFOLLOW` and `os.fchmod`; missing safe
facilities fail with concrete maintenance needs. Native Windows execution of this
new helper remains unverified. Retained Windows mode fixtures establish logical
metadata behavior only. A Linux hosted runner can prepare PE, ELF and HTML
carriers independently of their target OS. Existing pack/compose routes retain
their recorded coverage.

### Automatic feedback and ordinary Latest

Active appended or nonminimal projects can provide the user-owned optional
`.github/appended-retained.json`; no enabled request is supplied in this
repository. Its separate exact schema is:

```json
{
  "schema_version": 1,
  "kind": "foundation-appended-retained-request",
  "source_repository": "OWNER/REPOSITORY",
  "source_tag": "EXACT-PUBLISHED-TAG",
  "source_release_id": 123,
  "source_commit": "EXACT-LOWERCASE-40-HEX-COMMIT",
  "asset": "retained-inputs.tar.gz",
  "asset_sha256": "INDEPENDENT-64-HEX-ARCHIVE-PIN",
  "selection_sha256": "INDEPENDENT-64-HEX-SELECTION-PIN",
  "kernel_id": "EXACT-SELECTION-KERNEL-ID"
}
```

One shared CI job acquires the authenticated exact group once and exports only
the selected original descriptor. All four feedback checks require successful
selection and use the same descriptor/hash, including the changed-tools rerun.
Missing or inaccessible inputs report maintenance required with build/gui false.
PR acquisition uses only read-only `github.token`; inaccessible private
cross-repository inputs receive no secret fallback. Ordinary/minimal projects
ignore the request and retain normal feedback. `ci.yml` remains a conservative v2
kernel input; old descriptors inventorying a different workflow are not reissued
automatically. Payload editing never authorizes rebuilding an admitted carrier.

Ordinary Latest preflight rejects appended payloads or a selected nonminimal
profile before remote, matrix or producer operations and directs the user to the
retained workflow. Missing configuration or neither/minimal retains ordinary
Latest behavior. Publication and qualification requirements remain unchanged.

The additive [qualification framework](../tools/appended_qualification.py)
requires an independently pinned proof for each original qualified, sealed
kernel. It matches final prefix bytes, native closure, original SDK and source,
target/backend/baseline and the appended loader/profile/ABI contract. An old
ordinary application certificate or source projection alone is insufficient.
Original reports keep their identities. New composition checks run under a
separate frozen plan and produce an external certificate without changing the
candidate's original incomplete marker.

[The composition policy](appended-release-policy.json) declares limited binary
profiles and required assertions; it is not evidence or execution authorization.
Freeze actual commands and consumed inputs, run the named checks, then certify:

```sh
./build.sh appended qualification freeze --help
./build.sh appended qualification run --help
./build.sh appended qualification certify --help
./build.sh appended qualification verify-certificate --help
```

The [delivery adapter](../tools/appended_delivery.py) keeps application,
packager and original-kernel provenance separate. Candidate publication,
certificate attachment and promotion are explicit operations, dry-run by
default. Promotion rechecks remote bytes and reproduces the certificate; the
legacy release path is unchanged. No publication is authorized by preparation
or certification alone.

**Actual composition qualification and publication eligibility remain pending.**
Current development kernels have no original appended-kernel qualification proof.
Generic guest-recovery, archive upgrade/removal and final-HTML browser adapters
have implementations and focused development checks. The Linux Firefox adapter
uses a pinned executable and private offline profile. The Linux Chromium adapter
is also implemented, with an additional independently pinned native ChromeDriver
selected by the scenario's `browser.driver` object (`executable` and `sha256`).
It checks the actual browser/driver images, owned process ancestry and matching
major versions. Its separate tool-owned resource witness requires successful
online requests and blocked offline requests from a root document, opaque frame
and blob Worker, with native offline-state readback and joined listener/process
owners. This is test instrumentation; the application still opens directly from
its unchanged final HTML file. Both adapters use existing generic widgets and
permit one edit per widget before an application acknowledgement.

The adapter also admits an eligible HTML BOTH carrier through a separately
frozen schema-2 scenario. Its [identity schema](../tests/fixtures/appended-rich-both-browser-scenario.schema.json)
binds the retained prefix, engine, Foundation receipt, payload and exact public
inspection-source cohort. Input uses ordered WebDriver pointer and keyboard
actions on generic compiled controls. Focused admission/action fixtures pass;
actual public BOTH browser execution remains pending an eligible retained base.
Recorded DOM spans do not establish visible startup, warm reload, native
publication/ACK or rich-frame interaction latency; those metrics remain pending.

The additive [schema-3 rich surface scenario](../tests/fixtures/appended-rich-surface-browser-scenario.schema.json)
addresses the retained engine's `engine.frame` canvas. It keeps the schema-2
identity pins and independently pins the new physical-action helper. Click,
wheel, key chords and scalar typing use WebDriver input at the current accepted
surface owner and canvas geometry. Generations are resolved for each action;
service retirement can replace a bitmap's generation. The engine viewport is
currently 800×600, so ordinary scrolling or keyboard navigation may be needed
to reach a page's editor.

The editor renderer exposes the generic read-only
`foundationRichSurfaceObserver.read()` and `observeDocument()` API inside its
isolated frame. The latter uses the existing serialized native Observe/Take
route; reading cached values alone does not refresh document state. The
observation distinguishes accepted metadata from an actual canvas render.
Fixed native predicates cover visible text, uniquely labeled form values,
named descendant text, representable native selection and explicit rich tags.
They reject unavailable, erroneous, truncated or mismatched publications.
Per-step screenshots accompany assertions; a `capture` step is review evidence
and cannot itself satisfy an application assertion. A bold tag assertion applies
only when the native document actually exports that tag; it does not infer
computed font weight for an arbitrary styled span.

This source path has focused component checks, but requires a freshly bound
host asset graph and eligible retained receipt before public execution. It does
not change the pending complete Foundation runtime gate or establish a public
QuotePad run. QuotePad's checked adjustment-one and adjustment-two modules produce
43 and 44 for inputs 20 and 22. Native observation spans remain distinct from
input-to-frame causal latency and native service ACK measurements; unavailable
required measurements stay pending. Host observation changes require explicit
host maintenance and fresh source/resource binding, while ordinary application
HTML/CSS/JavaScript edits remain packaging-only.

The Chromium successor passed focused synthetic checks; no actual Chromium or
ChromeDriver execution has verified its native endpoints, direct-file canaries
or natural shutdown. Unsupported facts fail explicitly. HTML archive lifecycle
checks remain limited to stateless applications. The mandatory actual Chromium
gate and original-kernel/composition qualification are still unexecuted; web/both
runtime integration also remains unfinished. Neither unit fixtures nor candidate
integrity qualify a release.

## Rich website fixture and remaining work

`src-web-appended/` contains a bundled calculator, two editable spreadsheet tabs
and a styled rich editor. It uses ordinary HTML/CSS/JavaScript without backend
branches, external frameworks, CDNs or a build step. Opening `index.html` directly
in an external browser is a development preview. The unavailable service panel
does not report a mock native success.

The first external Firefox preview exercised actual editing, formatting,
undo/redo, spreadsheet state and local asynchronous updates. This establishes
only the named external-browser fixture. It does not establish native engine,
TUI, Edge, Chrome or Desktop embedded-browser support.

The bounded non-pthread CPU engine prototype compiled and passed 18 actual-engine
assertions in Node and 18 in offline Firefox. That diagnostic baseline establishes
the selected editing/rendering fixture, with its original source and artifacts.
It is not the neutral copied-provider factory consumed by the new producer.
Three later resource/service wrapper translation units passed actual-header
syntax checks, without compiling the five core patches or optional shim,
generating objects, linking or executing a new runtime.
Later service/resource, terminal, physical-input and native-port sources now have
shared compositions and focused source/component checks recorded in
[appended validation](appended-validation.md). Actual rich Foundation integration
and browser/TUI/native execution remain unfinished or unverified. A selective
compiled-provider successor passed the earlier control-completeness case and
the original application assertions, then failed while reopening a native form
session. Its Begin-only focus-state correction passed focused production-source
regressions; a new selective candidate and actual runtime check remain pending.
Its subsequent retained-input preparation failed on disk allocation before any
compilation; the incomplete copy is ineligible. The incident audit found the
checked source WIP and earlier retained artifacts intact.
See [the detailed audit](appended-web-feasibility.md#next-bounded-port-prototype).
No extensive platform qualification is implied here.

Focused CTests are registered as `appended.abi`, `appended.registry`,
`appended.container`, `appended.module`, `appended.providers`, `appended.kernel`,
`appended.web_services`, `appended.web_services_native`
and `appended.document_forms`; `foundation.gui.surface` checks the independent
input policy. Input/NDV2 component checks also include
`appended.engine-input-codec`, `appended.engine-input-owner`,
`foundation.gui.appended-engine-input-application`,
`foundation.gui.appended-engine-input-transport` and
`foundation.gui.appended-document-v2-codec`. Tooling checks use
the `tools.appended_*`
suites. Select actual test names through `./build.sh test dev --test NAME` with
the matching configured profile. Current validation and remaining extensive
scopes are recorded in [the implementation checkpoint](appended-validation.md)
and [pending binary-kernel qualification](../.agent-pending/appended-kernel-qualification.md).
