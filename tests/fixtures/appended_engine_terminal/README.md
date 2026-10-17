# Terminal main fixtures

These headers replace only external composition/loader/startup/runner boundaries
while `tests/appended_engine_terminal_main_test.cpp` includes the real native
terminal main. The actual document/actions profile validators, public provider C headers,
host contract and retained GUI contract/runtime headers remain in the compile.
Synthetic identities and mock providers supply no eligible engine or runtime proof.

Compile strict C++20 with this directory before `gui/`, `gui/shared/`, `include/`,
`abi/appended/` and the selected retained GUI include directory. Define
`FOUNDATION_APPENDED_ENGINE_NATIVE_PROFILE_ENABLED=1`. The web executable deliberately
has no definition of `make_engine_module_binding`, so a stray production reference
fails to link. Defining `FOUNDATION_APPENDED_BINARY_CAPABILITY=1` supplies the counted
fixture implementation and exercises explicit both injection.
The actions fixture also needs the quoted compile definition
`FOUNDATION_APPENDED_ENGINE_NATIVE_RUNTIME_HINT="../share/software-foundation/engine-native"`.
`default-runtime` verifies that the installed executable-relative resolver runs
before payload admission and supplies the generated plan root;
`default-runtime-failure` stops before the payload read. Explicit overrides and
CLI/help errors must never call that resolver. `actions-cli-missing` supplies the
flag without its required directory argument. The old pixel `cli-missing` still
rejects an invocation with no arguments; the installed default is actions-only.

Define `FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE=1` separately
for the explicit kind4/capabilities4083 branch. Its generated-header overlay
exposes only `compiled_native_engine_document_actions_profile`; the ordinary
branch exposes only `compiled_native_engine_document_profile`. Successful
compilation therefore checks that each entry branch needs only its selected
typed facts. An absent or zero actions selector preserves the pixel branch.

Each invocation takes one case name and must run in a fresh process. Cases cover
CLI/help; payload/startup ordering; `profile-0` through `profile-36` joins; native
pixel-only constraints; verification/load/bind failures; ready/waiting and actual
Owner identity; wrapper hooks and queued worker wake; complete/terminal/blocked/
expired shutdown; and binary payload mode. `tty-return-failure` models the ordinary
runner's returned setup error. `tty-failure` and `tty-nonstd` model exceptions
escaping that runner boundary, rather than claiming the actual runner fails to
catch ordinary terminal setup exceptions.

Actions builds reuse the ordinary lifecycle/CLI/binary cases, excluding the old
`cli-missing`, `profile-*`, `physical-profile`, `browser-profile` and `invalid-profile` selectors.
`actions-plan-0` through `actions-plan-90` independently change every facts field
and every query/command subfield in the expectation; `actions-plan-91` through
`actions-plan-96` change the six target/hash joins. `actions-facts-0` through
`actions-facts-90` independently corrupt the compiled facts. `actions-browser`
rejects an otherwise valid browser profile. `actions-legacy-document`,
`actions-legacy-editor` and their `-dirty` variants reject active and disabled
nondefault old facts before Owner construction or verification/loading. Valid
`actions-linux-arm64` and `actions-windows` exercise the other native fact triples
with mock boundaries; they are not actual cross-platform runtime tests. The
Driver seam checks exact command/query/reply capacities 1048576/236/1048576 and
the Owner seam checks that only the actions profile is configured.

The expired-close case changes the injected binding's deadline through a test-only
callback; it never waits ten seconds or weakens the production close budget.
The only mock work scheduler is a normal `tick`; callback hooks and worker wake
must not invoke it synchronously. No provider ACK, unload, destroy or engine API
is available to these fixtures.

Separate negative compiles omit the native macro, set it to zero, or select the
legacy input macro. Those are compiler-rejection checks with zero runtime cases.
An actions selector outside zero/one must also fail compilation.
`nm` proves only this main-with-mocks closure has no web factory reference; it is
not a whole-kernel or interpreter-free production link proof.
