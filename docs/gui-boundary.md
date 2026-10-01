# GUI ownership and integration

Application features have one implementation. Their state, commands, labels,
availability, rows, menus, layout, and service intent belong in shared code.
Backends interpret generic declarations and return generic input. A backend may
understand a button or a text editor; it must never understand an application's
named command or privately reconstruct its layout.

This repository reuses the public C++20 contract and concrete adapters from
[gui-boundary](https://github.com/mirage335-colossus/gui-boundary), pinned in
[the dependency lock](../third_party/gui-boundary.lock.json). It does not maintain
a second widget vocabulary or renderer implementation. Read the explicit
[audit and remaining limits](gui-audit.md) before choosing supported platforms.

## Dependency direction

```text
core functionality       shared application and layout
        ^                  | Snapshot / Event / Adapter
        |                  v
        +------------ public GUI boundary
                           |
                 retained state and input rules
                           |
              native controls / terminal / pixels / browser
                           |
                 platform event loop and services
```

Keep core headers free of GUI dependencies. Shared application headers use
public boundary types and ordinary values. Composition roots construct an
application and an adapter and connect their event channels. The application
never chooses its renderer, imports a toolkit, or receives a native object.
Link the shared application library once into each enabled executable, using one
CMake configuration and one build graph for a target platform.

## Executable example

[The shared entry application](../gui/shared/application.cpp) calls the same
`foundation::Store` library as the CLI. The core owns record validation, capacity,
stable identities, and mutation. Shared GUI code projects its records and owns
editing, availability, a count, validation status, a menu, a heading prompt, and
responsive layout. [Its public header](../gui/shared/application.hpp)
exposes only the common adapter. The optional remove feature is added by a
shared method; the cross-backend test enables it after the initial view exists.

The interactive terminal uses upstream terminal mode management, byte decoding,
keyboard input, drawing, bounded output, and restoration unchanged. The
framebuffer host writes an actual complete RGB frame. The optional FLTK host
uses real native controls. All three compose the same shared application.
The framebuffer executable is an image-output host, not an interactive desktop
window; the upstream SDL host supplies the latter when an application needs it.

The terminal and FLTK composition roots in the pinned dependency directly name
its example. [The CMake integration](../gui/CMakeLists.txt) verifies the dependency
files and then replaces exactly one include with our application's header and
one type alias in a generated build file. It refuses a missing or repeated
include. No maintained copy of platform code or feature-dependent renderer
branch is introduced. When upgrading, review that narrow composition patch
alongside the upstream host changes. A reusable upstream host runner would
remove the need for this integration patch.

## Build and run

Acquire the explicit revision outside this repository, or use an already
available verified checkout. Downloading is a preparation step; configure and
build never fetch dependencies implicitly.

```sh
git clone https://github.com/mirage335-colossus/gui-boundary.git /path/to/gui-boundary
git -C /path/to/gui-boundary checkout --detach bff416308f87dd0c1a7cc5b55476d757c971e879
cmake -S . -B build/gui -DCMAKE_BUILD_TYPE=Debug \
  -DFOUNDATION_BUILD_GUI=ON -DFOUNDATION_GUI_SOURCE=/path/to/gui-boundary
cmake --build build/gui --parallel 2
ctest --test-dir build/gui -L gui --output-on-failure --parallel 2
./build/gui/gui/foundation-gui-terminal
./build/gui/gui/foundation-gui-framebuffer build/gui/entry-list.ppm
```

Use `--config Debug` for builds and `-C Debug` for CTest with a multi-configuration generator, and run the executable
from its `Debug` directory. Enable `FOUNDATION_GUI_FLTK=ON` when FLTK development
files and a display are available. That option adds `foundation-gui-fltk` to the
same build. Enable `FOUNDATION_GUI_HOST_TESTS=ON` on a POSIX host to register the
real terminal test on a private pseudo-terminal. Optional tests absent from
`ctest -N` are omitted coverage, not passes.

The lock checks every consumed public header, generated font data, host input,
upstream test and font notice by SHA-256, including archives without Git metadata.
Editing a consumed input triggers configure and rejects an unreviewed change.
The dependency currently has no top-level license declaration; local integration
is separate from authorization to redistribute it. GUI outputs have no install
rules, and package creation refuses GUI-enabled builds pending that clarification.

The example editor accepts valid UTF-8 at the boundary, with the core's 256-byte
input limit. The example Store deliberately accepts printable ASCII records.
Rejected values remain editable and the shared status label displays the core
error; no backend performs a competing validation rule. This distinction lets
an application change its data contract without modifying native input code.

## Contract requirements

| Area | Required ownership and behavior |
| --- | --- |
| State | Shared code owns accepted values and commands; widgets are projections |
| Identity | Nonempty opaque IDs, monotonically new generations after replacement; no behavior from captions |
| Publication | Owned snapshots, validated completely before retained state changes; programmatic updates emit no user commands |
| Input | Exact originating key, stable option/row IDs, shared eligibility checks, authoritative revalidation of queued events |
| Text | Literal UTF-8, explicit byte limits, read-only and submission policy, byte-based selection conversion, committed input validation |
| Selection | Surviving row IDs keep selection through reorder; stale or disabled rows and options cannot activate |
| Geometry | Shared logical rectangles, content extents, page positions, modal scope and clipping; adapters convert to their device units |
| Measurement | Adapter measures with its drawing font; shared layout decides allocation; delayed metrics trigger shared recomposition |
| Scrolling | Generic retained offsets, clamping, nested translation, and follow-tail policy; no feature-specific scroll rules |
| Services | Owned request/result IDs, exactly one consumed completion, explicit success/cancel/error, declared unavailable services |
| Workers | Bounded messages to the owner UI thread, explicit rejection/backpressure, cancellation and join before destruction |
| Rendering | Owned resources, explicit source revision, damage relative to the consumer's last frame, retry or explicit failure |
| Lifetime | Close remains possible after render failure; late callbacks lose authority; native object replacement retires callbacks |
| Accessibility | Shared meaningful labels and keyboard access; actual host assistive-technology behavior needs platform validation |

Authoritative state can advance before the screen. The entry application keeps
accepted text when a presentation fails, remembers pending presentation, and
retries without repeating the command. Closing bypasses painting. The same rule
applies to accepted service replies: retrying the display must not rerun a file
operation, clipboard operation, or other side effect.

Use immutable values across asynchronous boundaries. Native callbacks cannot
retain borrowed text, application references beyond their lifetime, or native
positions that become invalid after rebuilding controls. Queue capacity,
per-item size, revision lifetime and cancellation behavior belong in the
contract. Arbitrary toolkit pointers and application-specific escape hatches
defeat the boundary and are not acceptable shortcuts.

## Similar layout across backends

Declare structure, ordering, logical sizes, spacing, palette and content clipping
once. Backend hosts may quantize or scale those rectangles; they may not replace
them with an independently authored terminal menu or toolkit form arrangement.
Measure text with the same provider that draws it. Retain both the unscrolled
content extent and the visible viewport so clipping does not alter meaning.

At matching client sizes, compare control ordering, rectangles, rows, page
navigation, modal reachability and disabled state. Test narrow and minimized
views, high display scaling, changed text, nested scrolling, and long entries.
Native borders, fonts and terminal cells can differ while layout and behavior
remain consistent. Exact native glyph pixels are not a portable contract.

## Adding or changing a feature

1. Change the core operation, if one is needed, and its shared application handler.
2. Declare the control, stable identity, value, label, help, availability, and
   layout on the shared side.
3. Normalize input through the common contract and recheck current state before
   performing the operation.
4. Extend the shared behavioral scenario. Run it through several real adapter
   input boundaries, not just direct calls to the handler.
5. Verify matching declarations and geometry. Exercise the affected native host
   when focus, text entry, services, measurement or lifecycle is involved.
6. Confirm renderer and host diffs contain no feature implementation. A test
   fixture may mention feature identities; reusable renderers must not.

A new command, menu item, ordinary panel, list field or composed modal needs no
backend feature code within the supported vocabulary. A new primitive, gesture,
service capability or multi-window lifetime is a boundary extension: specify it
once, implement generic mechanics in each supported adapter, and add common
conformance checks. Do not hide an unsupported requirement as a private backend
branch and claim it is insulated.

## Verification

[The executable scenario](../gui/tests/application_test.cpp) edits and adds
entries through terminal bytes and framebuffer input, adds the remove feature,
checks stable selection and stale edits, exercises service identity, resize,
retained frame ownership, shutdown and presentation recovery, then compares
layout and resulting state. The injected failure fixture tests a behavior that
ordinary success-only screenshots cannot establish.

[The source guard](../tests/test_gui_boundary.py) rejects concrete backend
dependencies in shared code and application identities in maintained host code.
Its deliberate invalid examples check that the guard itself detects violations.
This guard is a useful tripwire, not a proof of every possible indirect
dependency. Behavioral scenarios and review remain necessary.

Six pinned upstream suites exercise the wider vocabulary, including an unrelated
application extension through memory, terminal, framebuffer and browser
adapters. The [real terminal check](../gui/tests/terminal_host_test.py) separately
verifies process I/O and restoration after normal exit and interruption.
Use the upstream native, browser, SDL, module and clipboard suites for targets
you intend to support; a passing semantic test does not substitute for them.

## Upgrade procedure

Record the upstream revision, local composition patch and required compiler in
the dependency inventory. Review changed public contracts and supported service
profiles; then review all adapter translations of changed semantics. Update the
lock from reviewed bytes, compile the shared library without toolkit includes,
run the common and adapter-specific suites, and capture matching views.
Preserve third-party font notices in every approved binary distribution. Never
silence a lock mismatch by updating hashes without reviewing the change.

Use [the build guide](building.md), [dependency requirements](dependencies.md),
and [release requirements](releases.md) alongside this boundary contract.
