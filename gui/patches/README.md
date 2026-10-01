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

Small FLTK/Rev loops and the two browser composition roots implement the common
host contract directly. `host/browser.hpp` is the single native/Wasm runtime.
The portable loopback transport replaces only the pinned server's pipe session
class; its existing assets, HTTP checks and session registry are reused.

For an upgrade, review upstream changes, refresh the pin and hashes, regenerate
and inspect each diff, and run every selected host/conformance check. Never
refresh hashes just to bypass a mismatch. Upstreaming typed runners and portable
pipe transport would remove these local integration changes. Their provenance
is the locked gui-boundary revision; its unresolved license also applies to
changes derived from its code. Do not redistribute GUI binaries until resolved.
