# Validation record

This file records observed checks for the local reference implementation. It does
not turn documented requirements or workflow definitions into platform support.
Commands assume the repository root. Generated evidence stays in ignored build
outputs; a release must retain its own immutable evidence inventory.

Environment: Linux x86_64, GCC 14.2.0, CMake 3.31.6, Ninja 1.12.1, Python 3.13.5.
The source of truth is the committed implementation accompanying this document.
No remote repository, hosted CI execution, public release or package repository
was created for this validation.

| Check | Observed result |
| --- | --- |
| Debug focused core build | 2/2 CTest contracts passed |
| Optional GUI application | Shared feature and actual terminal-host checks passed after integration with the core library |
| Pinned GUI contracts | Six upstream contract/adapter/layout/runtime/presentation/extension suites passed |
| GUI source and ownership guards | Four checks passed |
| GUI visual inspection | Generated framebuffer inspected; native toolkit visual parity remains unverified here |
| Coordination helper | 42 checks passed, including independent processes, publication faults, path aliases, stale observations and retained job ownership |
| Full core candidate | Release: 9/9 CTest cases passed |
| Native archive and installed consumer | TGZ inventory, safe extraction, relocation, CLI and external SDK consumer passed |
| Test-plan aggregation | Two disjoint shards covered all nine configured tests; complete merge passed |
| Sanitizer checks | Six tool/documentation cases passed in restricted execution; three runtime/consumer cases passed outside the tracing wrapper |
| Workflow files | YAML parsed locally; hosted execution remains unverified |
| Multiple configurations | Ninja Multi-Config Release core/consumer tests and CPack archive creation passed |

## Reproduce

```sh
./build.sh test dev --full --jobs 2
./build.sh test release --full --jobs 2
./build.sh test asan --full --jobs 2
./build.sh package release --jobs 2
python3 tools/check_docs.py
```

For archive and shard verification use [the tested command recipes](testing.md).
For the optional GUI use the exact [locked dependency and commands](gui-boundary.md).
Every new relevant source/configuration change invalidates the affected evidence;
reuse unaffected evidence with its actual scope stated.

The initial sanitizer runtime checks failed because the restricted execution
wrapper uses tracing that LeakSanitizer cannot operate under. The three affected
checks were rerun outside that wrapper with leak checking still enabled and all
passed. The original failures were environmental; they were not reported as passes.

## Limits that remain explicit

- Windows, Linux ARM64, older Linux runtime baselines and compiled target SDKs
  require native/target execution beyond this local environment.
- Hosted workflows are templates and need execution after repository hosting is
  configured. Their selected source checks do not certify a release.
- Optional native GUI toolkit dependencies and display environments were not
  available. The [GUI audit](gui-audit.md) records capability and licensing gaps;
  no optional GUI binary is packaged for redistribution.
- Sanitizers are extra evidence, not proof of absence of every memory or thread
  error. Performance or minimum-runtime claims require their own measured gates.
- The coordination helper is a cooperative local-filesystem protocol. It does
  not enforce source filesystem permissions against an uncooperative participant.
