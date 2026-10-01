# Reviewed integration changes

These unified diffs adapt the pinned public repository in the build directory.
The original source tree is never edited. The dependency lock verifies every
input; `apply.py` additionally requires exact hunk positions and context. There
is no fuzzy application, type alias to an upstream demonstration, or application
identity inside a renderer.

- `terminal-runner.patch` exposes `run_terminal<App>` under the typed host
  contract. Terminal setup, input, output bounds and restoration stay upstream.
- `sdl-runner.patch` exposes `run_sdl<App, Observer>`. It removes the upstream
  demonstration's test actions and accepts a test observer. Production uses a
  no-op observer. Input translation, texture upload, damage and window handling
  remain upstream. The test observer lives with tests and is never in product code.
- `rev-build.patch` consumes explicit verified source paths and creates reusable
  toolkit/adapter targets, without the upstream demonstration or install rules.
- `rev-dependencies.patch` passes the preserved archive root explicitly to the
  upstream GLEW/FreeType recipe.
- `fltk-appearance.patch` renders generic groups, buttons, toggles and menus with
  the shared flat palette, border and font roles. It uses a monospaced font class
  throughout, including measurement, and clears native focus when requested.
  Native button/editor callbacks and keyboard handling remain in the toolkit.
  No application identity or command occurs in this adapter patch. Real native
  control, toggle, focus and pixel-comparison fixtures protect its behavior.

- `contract-portability.patch` makes the upstream synchronous text acknowledgment
  test capture an explicitly declared pointer, then assigns it after construction.
  The adapter constructor only stores the handler. A guard rejects any callback
  before assignment; the original event-delivery and selection assertions remain.
  This avoids MSVC's rejection of self-reference from the initializer's implicit
  capture. Only the generated test is patched. Remove this adaptation when the
  pinned upstream uses a supported capture and passes the same Windows test.

- `adapter-portability.patch` applies the same explicit target binding to the
  metrics callback. Mutation and recursive measurement still execute inside the
  callback and must be rejected by the adapter's original guards. Constructor
  timing, exception recovery and all original assertions remain checked. Remove
  it when the pinned upstream passes these checks with supported MSVC captures.

Small FLTK/Rev loops and the two browser composition roots implement the common
host contract directly. `host/browser.hpp` is the single native/Wasm runtime.
The portable loopback transport replaces only the pinned server's pipe session
class; its existing assets, HTTP checks and session registry are reused.

For an upgrade, review upstream changes, refresh the pin and hashes, regenerate
and inspect each diff, and run every selected host/conformance check. Never
refresh hashes just to bypass a mismatch. Upstreaming typed runners, portable
pipe transport and shared appearance roles would remove these local adaptations. Their provenance
is the locked gui-boundary revision; its unresolved license also applies to
changes derived from its code. Do not redistribute GUI binaries until resolved.
