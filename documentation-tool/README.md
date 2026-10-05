# software-foundation edit maps

A separate, manually invoked documentation generator answering **what do I edit
to make this change?** in a changing `software-foundation` checkout. Its starting
view is a graphical edit path, with source details underneath. It produces an
offline HTML explorer, four linked PDF handbooks, and a machine-readable source
snapshot. It requires no AI, API
key, service, compiler, CMake configuration, compile database, or application build.

The generator is versioned in the separate **`documentation-tool/` directory**.
Its virtual environment and generated snapshots stay outside the application
repository. Running it never edits application code, build definitions, CI
workflows, regression tests, Git state, or agent coordination records. There is
deliberately no build hook, watcher, scheduled job, or automatic refresh.

## Run only when a new snapshot is wanted

From a checkout containing `documentation-tool/`, prepare an independent
environment once:

```sh
python3 -m venv ../software-foundation-docmap-env
../software-foundation-docmap-env/bin/python -m pip install -r documentation-tool/requirements.txt
```

Then invoke explicitly whenever new documentation is wanted:

```sh
../software-foundation-docmap-env/bin/python -B documentation-tool/docmap.py
```

The containing checkout is the default source. Every run creates a **new**
timestamped directory under the sibling `<checkout-name>-documentation/snapshots/`
and prints its location. The tool excludes its own directory from the source
inventory. Open `index.html` directly in a browser. No web server is needed.

The tool can also live outside a checkout. In the original standalone layout,
`software-foundation-docmap/` defaults to its sibling `software-foundation/` as
source and creates snapshots under the tool's own `snapshots/` directory. Its
existing `.venv/bin/python -B docmap.py` invocation still works.

To choose the locations explicitly:

```sh
../software-foundation-docmap-env/bin/python -B documentation-tool/docmap.py \
  --source . \
  --output ../software-foundation-documentation/manual-snapshot
```

Existing output directories are refused, even if empty. Output inside the source
tree, or a parent containing the source tree, is refused. These checks also
resolve symlinks. The versioned tool can read its containing checkout; it cannot
write documentation into it. Keep the Python environment outside the checkout
and use `-B` as shown above.

For HTML/JSON only, add `--no-pdf`. Additional exclusions can be specified as
source-relative paths, for example `--exclude tests --exclude .github`.
Files larger than 4 MiB are reported as skipped; adjust `--max-file-mb` if needed.

The documentation is a navigation snapshot and may not be kept up to date.
Regenerate explicitly when its broad map stops being useful. It records the
capture time, per-file hashes, parser versions, coverage gaps, and a combined
hash of the captured files. It detects edits to captured files during collection,
but it cannot guarantee an atomic repository snapshot while other agents work.

## Start with the change you want

**Add a widget, a click event, and a helper beneath the event.** The first diagram
leads from the row in `view_definition.hpp`, through target-ID routing in
`Application::handle`, to the new handler and its helper. A decision splits
UI-specific behavior in `Application` from reusable domain behavior in the core.
Conditional steps cover state projection in `publish` and registration of a
genuinely new `.cpp` file. Existing event forwarding and table-driven layout are
marked **REUSE**. Proposed function names are marked **NEW**.

**Make a new source file compile.** This diagram asks which module owns
the code, then points to the exact core, GUI, CLI, or host target source list.
Rust module declarations and header-only changes have their own branches.
Adding a method inside an existing compiled `.cpp` requires no source-list edit.

**Place a widget in the right position and page.** This diagram makes the current
single-panel arrangement explicit: declaration order controls vertical order;
the row sets height; `publish` owns spacing and composed bounds; `add` currently
parents every non-root widget to the first root group. Custom rows or groups need
matching changes to declarations, parents, and the shared layout tree. A widget
ID prefix does not assign a page.

**Add a page tab and place its contents.** The current application initializes no
tabs, although the retained GUI contract supports them. The chart shows the first
implementation path: declare pages and an active page, add explicit page/parent
membership, compose page contents and visible tab-bar geometry, handle `PageEvent`,
keep focus consistent, and reuse generic adapter rendering. Once that shared
support exists, another tab adds a page entry and its owned content. This means
page tabs, not the keyboard Tab key used to move focus.

**Change validation or a business rule.** Follow the public contract, Store's
validation before mutation, equivalent Rust/C++ text providers, mirrored limits,
and the existing error/status consumers. Provider and capacity edits are
conditional on which rule changes.

**Edit the selected entry.** Add shared Update intent and resolve selection to a
stable record ID, then reuse the existing `Store::update` operation. Handle its
false return and invalid-input exception, and project the result. This avoids
mistaking a copied snapshot or a row index for the authoritative record.

**Add a menu command or keyboard shortcut.** Declare an option, route it to one
shared helper, and optionally reuse that helper from a button and a supported
key binding. The chart identifies normalization, current-button requirements,
and the pinned shortcut vocabulary.

**Change background work, cancellation and progress.** Follow the result contract,
bounded computation, owned input capture, executor scheduling, completion guards
and shared lifecycle. A different result meaning may require changing guards
that currently assume a byte count.

**Change import/export format.** Follow shared serialization and atomic parsing,
transfer bounds and freshness checks, generic byte transport, and honest status.
The chart explains why import preserves monotonic IDs and export completion
means host handoff rather than a durable-save guarantee.

Click a box to see **what to change, why it belongs there, the exact source
location, and an existing code example**. Follow the deeper links to the actual
function, its callers/callees, or captured source. The companion runtime diagram
traces the existing Add button through `append_entry`, `Store::add`, and
`Store::validate`; publication is shown as a later call from `handle`.

Dense examples have **Parameters explained** guides next to the relevant edit
steps. Each guide includes a readable synopsis, numbered field names, types,
meanings and defaults, followed by a filled multiline example with labels beside
its values. The guides cover `ViewDefinition`, `gui::Page`, `gui::Rect`,
widget page/parent assignments, CMake `target_sources`, `gui::KeyBinding`, and
`Store::update`. The PDF links each
step to a deduplicated parameter-reference appendix and back again.

Reading notation is labeled separately from usable C++/CMake fragments. C++
aggregate fields are shown in declaration order; proposed page/parent additions
are not presented as existing `ViewDefinition` fields. The guides check their
source anchors, including complete aggregate declarations, so field-order drift
shows a review warning. Their explanations are curated local data in
`parameter_guides.py`, not AI-generated at documentation build time.

These edit recipes encode project ownership deliberately; an arbitrary desired
feature cannot be inferred reliably from syntax alone. The separate
`change_maps.py` and `behavior_paths.py` contain these small, reviewable recipes. Generation resolves
their source anchors and snippets against the captured code, without AI.
Missing or ambiguous anchors display **Source anchor changed; review required**.
The arrows distinguish prospective edit dependencies from the existing runtime
example. They do not claim every marked function must change for every feature.

## Follow what runs when

The explorer's **What runs when…** scenarios illustrate existing code paths for
compilation, testing, release, startup, an Add-button click, import and export.
Choose a scenario, then follow its arrows and click a function or process box
for the captured implementation and source evidence. Source and function views
provide a return link to the originating scenario step.

The charts distinguish a direct **function call**, a **subprocess/command**,
an **event or asynchronous completion**, a **conditional branch**, a
**return**, and a **local step/sequence**. For example, `append_entry` calls `Store::add`;
publication occurs after returning to `Application::handle`. File transfer
crosses a host-service boundary before `complete_service` processes the result.
The release scenario distinguishes local packaging from hosted publication.

These are curated, source-backed representative paths, not recorded executions.
Compiler target selection and platform branches remain conditional. Missing
source anchors remain visible as review items. Generating the charts never
invokes any command shown in them, including builds, tests, or release tools.

## Supporting reference views

- From the task maps, open the reference inventory and entry points, then drill down through
  a component, file, object, and function. Every level has an upward route.
- Search symbols and paths, inspect callers and callees, and follow source-line
  links within the captured source. The exported directory is self-contained.
- Inspect function control structures: conditions, branches, loops, returns,
  exception handling, and nested blocks. Source remains the final reference.
- Read the build map for target/source relationships, declared links, options,
  presets, and toolchain files, without configuring any of them.
- Use the extension guide to find the existing targets for a new C++ file, the
  Rust module boundary, shared GUI feature ownership, and runtime entry points.

The default print collection has four linked volumes:

- `pdf/00-edit-paths.pdf` starts with a task index, then provides the charts,
  actions, ownership rationales, source links and parameter reference. It is the
  primary printable entry point.
- `pdf/01-code-walkthroughs.pdf` follows the chart references into captured
  functions and types: signatures, ownership/member information, full bodies,
  structural control outlines, and named caller/callee candidates. It also
  provides source context for chart anchors outside those symbols. The scope is
  the edit paths, with links to the full explorer inventory.
- `pdf/02-compiler-reference.pdf` provides declared targets with source/link
  arguments, options/defaults, toolchain assignments, presets, Cargo data,
  helper declarations and compiler/link configuration context. Conditions and
  variables remain symbolic, just as they do in the explorer.
- `pdf/03-execution-flows.pdf` provides the **What runs when…** flowcharts, with
  named calls and process/event boundaries, a scenario index, linked explanations
  and source evidence. It is a graphical companion to the code walkthroughs.

The edit steps and explorer offer **Read in PDF** links to exact reference pages
where available. The reference books link back to the edit guide and to their
explorer views. Full source bodies and control outlines are retained in the
walkthroughs; candidate-call tables identify any display limits explicitly.
Add `--reference-handbooks` only when you also want six broad inventory volumes
for toolchain, core/CLI, GUI/browser, developer tools, tests/examples, and the
overall file inventory. Detailed explorer views can also be browser-printed.
Keep the `pdf/` folder beside `index.html`; relative cross-file
links depend on PDF viewer support and may require downloading/opening locally.

## What the diagrams mean

[Tree-sitter](https://github.com/tree-sitter/py-tree-sitter) reads C/C++, Rust,
Python, JavaScript, and shell syntax without compiling or executing source.
The CMake readers inventory command declarations and lexical control nesting. JSON/TOML
provide configuration context. Other text is available as captured source.

Function and class locations are syntax-derived. Call links are **name-based
candidates**, not proof of runtime dispatch. Control diagrams describe source
structure, not a compiler-validated control-flow graph. Preprocessor branches,
macros, templates, overloads, virtual calls, callbacks, generated code, language
extensions, implicit exceptions and dynamic imports prevent complete static
resolution. Parse errors and unresolved calls are visible, rather than silently
reported as complete analysis. The C++ grammar also indexes C-like files; it is
not a language-standard conformance check.

CMake conditions, functions, variables, generator expressions and loops remain
symbolic. A source declaration may be conditional, and a helper declaration may
represent several generated targets. The generator does not claim that these
are the targets of any particular configured build.

By default `build/`, `third_party/`, caches, Git internals, agent work directories,
and symlinks are excluded. For page/tab and parameter guidance, the tool reads four selected
GUI contract/example files from the pinned local source archive into memory;
they appear under `@gui-boundary/` with archive provenance. These supplier files
are evidence, not application edit targets. Archives are never extracted,
dependency sources never restored, and patches never applied. Other adapter code
can therefore appear as external/unresolved references. Tests are indexed for navigation but
never run. PowerShell, patches, workflows, non-CMake configuration and documentation
have text/declaration views rather than full function-control analysis. The coverage
page and `atlas.json` list omissions, parsing warnings and excluded directories.

This scope is intentional: answer “where should I start editing?” with modest
local prerequisites. [Doxygen](https://www.doxygen.nl/manual/diagrams.html) is an
alternative for API documentation and call/class diagrams; this tool combines
the mixed-language source map with repository-specific build and extension
guidance. The project-specific prose lives in `navigation_guide.py` and must be
reviewed if ownership conventions change.

## Set up on another computer

Use Python 3.11 or newer and a private environment outside the source checkout.
For the versioned `documentation-tool/` layout, use the setup commands at the top
of this document. For a separately copied tool directory outside the checkout:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements.txt
.venv/bin/python -B docmap.py --source /path/to/software-foundation
```

On Windows use `.venv\Scripts\python.exe` in place of `.venv/bin/python`.
Setup downloads prebuilt parser/PDF libraries; **generation itself is offline**.
No Graphviz, Doxygen, LaTeX or application SDK is needed. For a disconnected
machine, first download wheels on a machine with the same OS, CPU and Python:

```sh
python3 -m pip download --only-binary=:all: -r requirements.txt -d wheels
.venv/bin/python -m pip install --no-index --find-links wheels -r requirements.txt
```

Do not add this command to CMake, build scripts, GitHub Actions or regression
test runners. Invoke it only when a person or agent explicitly wants updated
documentation.

## Tool layout

`docmap.py` owns read-only collection, snapshot metadata, conservative candidate
call linking, and output-path checks. `syntax_scan.py` reads syntax trees;
`build_map.py` inventories build declarations; `change_maps.py` and `behavior_paths.py` supply the
task-first edit paths; `source_anchors.py` verifies curated source references.
`flow_maps.py`, `workflow_flows.py`, and `runtime_flows.py` supply the existing
call/process/event scenarios. `parameter_guides.py` explains
dense examples with labeled fields and values; `navigation_guide.py` supplies
project navigation guidance with evidence lines resolved against the snapshot.
`render_html.py`, `explorer.js`, and `explorer.css` provide the browser explorer;
`supplier_reference.py` captures the bounded retained GUI contract evidence.
`render_change_pdf.py` creates the primary edit-path guide;
`render_walkthrough_pdf.py` and `render_compiler_pdf.py` create its deeper linked
references. `render_flow_pdf.py` creates the graphical execution companion.
`render_pdf.py` creates the optional inventory volumes.
`atlas.json` retains the complete
analysis and captured text without requiring either presentation layer.

## Snapshots and verification

Generated snapshots are deliberately not committed. Each output has `index.html`
and, by default, the four PDFs described above. The prepared external tool directory
also retains earlier snapshots, including `2026-10-04-edit-paths` and the expanded
`2026-10-04-placement-tabs` guide. `2026-10-04-developer-handbooks` contains the
expanded three-volume collection and the five behavior workflows.
`2026-10-04-execution-flows` adds the fourth volume and seven source-backed
execution scenarios to the explorer.

Generator-only checks passed for source/output isolation, symlink and FIFO
handling, parser fixtures, unique symbol IDs, source spans, call targets, guide
references, HTML route logic and escaping, cross-file class membership, PDF
bookmarks, and reference links. Representative final PDF pages were rendered
and visually inspected. Eight C++ files contain recoverable syntax limitations;
the coverage report also records lexical CMake notices and symbolic-build limits.

The expanded collection was generated through the packaged CLI; HTML-only mode
was also checked. All ten edit maps, seven execution scenarios, seven parameter guides, exact PDF page mappings,
cross-file PDF links, internal bookmarks, source routes, and annotation bounds
passed focused checks. Full selected source bodies and indexed flow labels were
checked for presence; call-table omission counts are explicit. The application
source fingerprint was unchanged by generation.

The available in-app browser blocked local `file:` URLs, so live browser layout
and interaction were not visually verified here. JavaScript syntax and route
logic were checked independently; open the explorer in your own browser for
that final visual check. No application build, application script, regression
test, Git mutation, or workflow was invoked by the documentation generator.
