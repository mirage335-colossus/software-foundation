# GUI integration audit

Scope: the pinned gui-boundary revision
`bff416308f87dd0c1a7cc5b55476d757c971e879` and the consuming example in this
repository. These findings describe inspectable responsibilities and current
verification, not an assurance about every possible future UI requirement.

## Source and call-path review

| Path inspected | Responsibility traced | Conclusion |
| --- | --- | --- |
| `include/gui/contract.hpp` | Snapshot validation, generation keys, effective availability, event normalization, adapter interface | Shared vocabulary contains no toolkit or application type |
| `include/gui/memory_adapter.hpp`, `retained_adapter.hpp` | Snapshot staging, generation history, focus, text selection, options, rows, scroll and render ownership | Common mechanics are reused by concrete renderers |
| `include/gui/interaction.hpp` | Software keys, pointer handling, editing, list navigation and prompt state | Terminal and framebuffer share interaction policy |
| `include/gui/layout.hpp`, `presentation.hpp` | Measured allocation, parent clipping, page placement, drawing order, modal scope | Layout and composition remain shared values |
| `include/gui/runtime.hpp` | Service IDs and completion, shutdown, bounded owner-thread queue | Side-effect lifetime and UI-thread ownership are explicit |
| `include/gui/terminal.hpp`, `backends/terminal/main.cpp` | Cell projection, input decoding, platform I/O, bounded pending output, restoration | Generic adapter; host composition is coupled to the upstream example |
| `include/gui/framebuffer.hpp`, `backends/framebuffer/` | Shared interaction to RGB frames, retained pixels and damage, image and SDL hosts | No feature IDs needed to render or interact |
| `backends/fltk/adapter.hpp` | Native callbacks to shared events, retained reconciliation, text metrics, clipping, prompt and clipboard | Native mechanics stay below the boundary |
| `backends/rev/adapter.hpp`, `adapter.cpp`, clipboard implementation | Private toolkit types, native controls, texture upload, platform service lifetime | Public adapter facade does not expose toolkit modules |
| `include/gui/web.hpp`, `backends/web/` | Sequenced input, bounded decoding, epochs, acknowledgments, measurements, DOM updates, native/module roots | One browser renderer and protocol serve two execution arrangements |
| `examples/application.hpp`, conformance and extension tests | Shared commands/layout to snapshots, normalized input back to state, feature extension across adapters | Existing vocabulary supports feature development on the insulated side |

The reference source for each path is the
[pinned upstream tree](https://github.com/mirage335-colossus/gui-boundary/tree/bff416308f87dd0c1a7cc5b55476d757c971e879).
Review also covered the upstream specification, layout, runtime, bitmap,
adapter, feature, conformance, font, build and running guides. The cross-reference
checks follow calls from application publication into retained state and
rendering, and from actual renderer input back through common normalization into
the application. A native callback's successful delivery is distinct from the
application accepting its effect.

## What this example establishes

Record state and validation reside in the same `foundation::Store` library used
by the CLI. GUI behavior and geometry reside in `gui/shared/`, which projects
core records and displays core validation errors. Its feature extension adds a button, availability rule, command,
and layout allocation without changing backend code. Both concrete adapters
produce the same declarations and rectangles, accept edits through their own
input mechanisms, and reach the same state. All upstream renderers remain
unchanged. The optional FLTK composition uses that same library.

The integration imports verified upstream inputs directly, builds the shared
application once, and makes dependency upgrades explicit. It does not copy
renderers into this repository. Its one generated host adaptation changes only
the application include/type binding and fails closed if that source shape or
any pinned input changes.

This is evidence for the finite supported widget and service vocabulary. It is
not a promise that drag capture, every text system, every platform service, or
arbitrary future interaction can be added without a public contract extension.

## Crucial remaining information and capabilities

| Finding | Practical consequence | Required action before claiming support |
| --- | --- | --- |
| No top-level upstream license declaration in the pinned tree | A source pin and public availability do not establish binary redistribution terms | Obtain upstream licensing and review dependency notices; GUI binaries remain excluded from packages |
| Upstream hosts directly construct their example; no installed CMake package/exported integration contract | Downstream reuse needs a small reviewed composition patch | Keep the pinned patch here; an upstream generic runner/factory and installable target would improve maintenance |
| No universal accessibility or input-method implementation across all profiles | A framebuffer or terminal does not acquire OS accessibility merely by carrying descriptive strings | Declare target capabilities and qualify screen readers, keyboard operation and input methods on each shipping host |
| Bundled software font has limited character coverage and no comprehensive shaping | Stored UTF-8 can remain correct while unsupported text uses a replacement glyph | Use the paired measurement/drawing extension for required scripts and verify caret/selection behavior |
| Terminal cells and native glyph metrics differ | Pixel identity is not achievable across every profile | Require common logical composition and usability, then review captures at matching dimensions |
| Browser text metrics arrive asynchronously | Initial layout can be provisional | Preserve measurement identity and recompose shared layout after valid replies |
| Browser host is a local demonstration transport; supported services are narrower than the vocabulary | An available enum value is not evidence of a working file chooser or deployment service | Publish a backend capability table and explicit errors; specify richer services before use |
| Pointer capture/dragging, touch, rich text, native trees, multiple windows and richer file transport are outside the finite core | These features cannot truthfully be promised as shared-only edits today | Extend public semantics and conformance for every supported adapter before introducing them |
| Layout lacks universal minimum-size negotiation and docking | Complex resizable interfaces need additional allocation policy | Add reusable shared layout policy and narrow/long-text tests; do not author separate backend arrangements |
| Optional native and browser checks need actual target environments | Linux source inspection or memory tests do not qualify a Windows desktop or a browser | Record real target build, input, visual, service and shutdown evidence with each release |

These are explicit adoption limits, not reasons to duplicate ordinary features
inside adapters. No feature-specific renderer dispatch was found in the inspected
generic adapters, and the provided feature-extension checks require none.
Full production suitability depends on the chosen requirements and evidence for
the supported platforms.

## Verification of this consuming example

The local Linux build used GCC 14.2, C++20, CMake and Ninja. The following checks
were run against the pinned dependency and the consuming code:

- The shared application, real terminal executable and framebuffer executable
  compiled in one build configuration.
- The shared feature scenario passed through terminal and framebuffer input,
  including core validation and recovery, stale-value rejection, added feature behavior, geometry equality,
  exactly-once service completion, resize, frame lifetime, close and failure recovery.
- The six upstream contract, retained-adapter, layout, runtime, presentation and
  cross-renderer extension suites passed.
- Four source-boundary/lock checks passed, including deliberately invalid
  dependency examples.
- The actual terminal process passed private pseudo-terminal editing, normal
  exit, and interruption/restoration checks.
- A generated 640 by 480 framebuffer image was inspected for alignment,
  clipping, labels and readable controls.

Optional FLTK, Rev, SDL, a real browser, a compiled browser module, Windows,
macOS, hardware display drivers, native input methods and screen readers were
not qualified by these checks. The selected upstream extension suite exercises
browser semantics but is not a real-browser rendering test. The optional FLTK
composition is provided for target-host verification; this environment did not
provide its development package or display runner.

To reproduce the relevant local profile, follow [the integration commands](gui-boundary.md#build-and-run)
and turn on `FOUNDATION_GUI_HOST_TESTS`. Preserve current test output and the
exact source/configuration alongside any release claim. Do not replace fresh
evidence with this prose after changing the dependency or application.
