# Documentation index

Each topic has one maintained home. Requirements describe expected behavior;
implementation references explain current code; validation records establish
what was observed. A proposed platform or procedure is not execution evidence.

| Topic | Start here |
| --- | --- |
| Build and run an example | [CLI commands](../COMPILE), [desktop GUI](../COMPILE-gui), [browser GUI](../COMPILE-web), [view screenshots](screenshots.md#view-screenshots), [capture commands](../SCREENSHOTS) |
| Scope and specification | [Engineering contract](engineering-contract.md), [requirements](requirements.md), [practice map](practice-map.json), [architecture and directory map](architecture.md) |
| Build and SDK | [Building](building.md), [offline application builds](offline-builds.md), [SDK](sdk.md), [portability](portability.md), [COMPILE](../COMPILE) |
| Proposed Rust integration | [Research, portability assessment and phased hybrid Rust plan](rust-hybrid-plan.md) |
| Verification speed and coverage | [Development speed](development-speed.md), [testing](testing.md), [CI](ci.md), [workflow examples](../.github/WORKFLOWS.md), [legacy archive preservation](legacy-artifacts.md), [validation](validation.md) |
| Dependency maintenance | [Dependency requirements](dependencies.md), [inventory](../third_party/README.md) |
| Installed manuals | [Manual sources and preview](man/README.md) |
| Interfaces | [GUI contract and integration](gui-boundary.md), [browser embedding](browser-embedding.md), [GUI audit](gui-audit.md), [Windows graphics prerequisite](windows-graphics.md), [core source](../include/foundation/store.hpp) |
| Collaboration | [Agent requirements](../AGENTS.md), [coordination](agent-coordination.md), [checked operation recipes](agent-recipes.md), [lifecycle](agent-lifecycle.md), [optional cooperation evaluation](agent-evaluation.md) |
| Delivery | [Release requirements](releases.md), [certification](certification.md), [Debian distribution](distribution.md), [Arch and Gentoo channels](distro-channels.md), [GitHub delivery](github-delivery.md), [signed package release workflow and native clients](distribution-release.md), [Latest workflow](latest-release.md), [screenshots](screenshots.md), [browser prerequisite](gallery-browser.md), [installed package instructions](installed.md), [RELEASE](../RELEASE) |
| Sustained maintenance | [Engineering practices](maintenance.md), [documentation rules](documentation.md) |
| Reusable forms | [Decision](templates/decision.md), [dependency](templates/dependency.md), [temporary note](templates/temporary-note.md), [validation](templates/validation.md), [release inventory](templates/release-manifest.json) |

Search current source and the relevant topic before opening large logs. Follow
linked contracts through callers and tests; do not treat this index as a limit on
investigation. Update the relevant topic and backlinks when adding documents.
