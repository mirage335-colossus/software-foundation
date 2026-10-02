# Initial application screenshots

The [screenshot workflow](../.github/workflows/screenshots.yml) builds this
application and captures seven actual surfaces: FLTK, Rev, the SDL window,
the terminal in xterm, the framebuffer, hosted browser rendering and browser
Wasm rendering. Each host starts with a fresh application. No editing scenario,
test-only application or copied image stands in for another backend.

Select existing Linux x64 GUI and browser SDK recipe digests from the dependency
base, a compile job count, and an optional new `screenshots-` tag. Missing SDKs
fail without starting a compiler-base build. Preparing or updating SDKs is a
separate explicit maintenance operation. The workflow acquires the reviewed GUI
source revision and checks its complete retained input group locally; it does
not publish that source or its application binaries.

The default `source=base` consumes only the exact public base. For recovery or
qualification before base publication, select `source=retained` and provide
`retained_inputs`, a JSON object with exactly `native` and `wasm` entries. Each
entry is the complete version-2 retained SDK request from the explicit SDK
producer/import workflow: repository, target, all-GUI profile, recipe, producer
run/job/attempt/source and both group/proof manifest IDs and digests. Neither
mode falls back to the other. Both selected origins are recorded in the gallery;
retained bytes remain explicitly unqualified for SDK publication. Legacy Actions
storage must first pass the explicit import workflow, never implicit retrieval.

The capture job uses the ordinary unprivileged Ubuntu runner account. It uses
prepared Bookworm SDKs for compilation and explicit distribution packages for the
display, software graphics, fonts and Selenium. Its installed Chromium or Chrome
and matching driver remain host prerequisites; no browser enters either SDK.
An [early sandbox and render probe](gallery-browser.md) must pass before SDK
acquisition or compilation. Capture keeps the browser sandbox enabled and changes
no host or container security policy. Compiler and capture children receive only
runtime paths and provenance, excluding transport credentials. The default native client and browser application area
are 640 by 480 pixels at scale one, on a private 96 DPI display. The terminal
uses 80 by 31 cells with its status row and border retained; its physical size
is recorded rather than cropped or stretched to resemble another renderer.

The collector checks that new native windows have painted, have the expected
size and remain stable before capture. Existing or ambiguous windows cannot be
selected. Browser capture waits for completed requests, loaded fonts/images,
the actual requested transport and a stable initial view. Both browser modes
must report the same widget geometry. The collector makes no application edits
and performs no resampling. Native font rendering may still differ.

All long build/capture commands run under the shared process-tree owner.
Application children, terminal children and browser descendants must stop
before successful collection. Failure preserves diagnostic outputs in the
owned work directory and does not replace an older gallery. The public output
directory is installed only after the complete new gallery validates.

## Retention and publication

`execute=false` builds, captures and retains the gallery in the run's private
draft release storage. It does write these private release assets; it does not
publish a screenshot release or move Latest. The pipeline uses no Actions
artifacts. Images and their accompanying metadata remain release assets even
when their compressed size would be small.

`execute=true` additionally invokes the protected `release-publisher`
environment. Configure its allowed branches and required reviewers in GitHub.
The publisher downloads the completed producer's verified bundle and requires
exactly seven PNGs, `BUILD.txt`, `screenshots.json` and `SHA256SUMS`. It rejects
extra files, changed image bytes, omitted surfaces and incomplete provenance.

Publication creates a new draft under a `screenshots-` tag fixed to the source
commit, uploads the complete inventory and downloads every uploaded asset for
verification. It then publishes a prerelease with Latest explicitly disabled
and verifies the final asset identities and pointer. An existing release/tag,
partial upload or uncertain remote outcome requires reconciliation; there is
no overwrite, delete or automatic resume. Screenshot publication shares the
application publisher lock but uses a distinct release namespace.

`screenshots.json` records the source commit and tree digest, actual executable
digests, both complete SDK triplets, reviewed GUI input identity, runtime/tool
versions, run/attempt, dimensions and image checksums. `BUILD.txt` is a short
human-readable companion. Source, executable files, SDK archives, browser
profiles and external graphics libraries are excluded from the public gallery.

Screenshots are visual documentation. They do not establish functional release
qualification, physical display compatibility or permission to redistribute
application dependencies. The existing GUI package licensing gate remains
independent of producing these images. Conformance captures and actual interaction
tests remain separate qualification evidence.

## Local use and checks

The [collector](../tools/screenshots.py) supports `collect` with exact existing
`--native-group`, `--native-recipe`, `--wasm-group`, `--wasm-recipe` and
`--gui-group` inputs, plus new `--work` and `--output` directories. Use Linux x64,
a clean source checkout, the declared display/runtime environment and the same
prerequisites as the workflow. `hosted` runs the complete unprivileged hosted-runtime
path and explicitly fetches its existing SDK inputs. `publish` plans by default;
only its `--execute` switch mutates a public release.

Run the [offline failure suite](../tests/test_screenshots.py) through the normal
tool-test runner. It covers complete inventories, changed images, nonblank
capture, startup/display failures, window ambiguity, process cleanup, immutable
publication, changed asset identity and partial-upload uncertainty. These mocks
do not qualify actual browser, toolkit, display or GitHub permission behavior;
the complete hosted screenshot job must pass on the intended source revision.
