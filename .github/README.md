# Workflow examples

These files become usable after this local repository is hosted on GitHub.
`ci.yml` gives inexpensive automatic feedback for pull requests and main-branch
pushes. `candidate.yml` is manual, defaults to full selected-platform tests,
checks actual target architecture, and creates verified native archive artifacts.
Neither workflow publishes releases or establishes an older-runtime baseline.

Manual candidate inputs:

| Input | Default | Effect |
| --- | --- | --- |
| `devfast` | `false` | `true` runs focused core diagnostics and omits packaging/sanitizers |
| `linux_pool` | `standard` | `faster` selects one administrator-configured larger Linux runner |
| `build_jobs` | `2` | Choose 2, 4 or 8 compiler jobs; tests retain two concurrent slots |
| `include_arm` | `true` | Include the Linux ARM64 runner alongside Linux/Windows x64 |

To enable `faster`, configure repository variable `FOUNDATION_FAST_LINUX_RUNNER`
with the authorized larger GitHub-hosted x64 Linux runner label. The example
requires its name to begin `foundation-linux-`. This variable is the allowlisted
choice, not an arbitrary workflow input. Confirm image prerequisites, access,
quotas and cost before configuring the pool. Missing configuration fails early.
The default uses standard runners and requires no such variable.

After hosting, a development diagnostic can be dispatched with:

```sh
gh workflow run candidate.yml --ref YOUR_BRANCH \
  -f devfast=true -f linux_pool=faster -f build_jobs=8 -f include_arm=false
```

Replace `YOUR_BRANCH` with the intended ref. Record and check the resulting
run's actual commit; wait for completion and inspect logs. Once the fix is ready,
run the default full candidate scope or reuse equivalent current evidence.
`devfast` is never release qualification. Agents can choose permitted faster
runners when justified by elapsed time, without inventing new runner access.

Action revisions are full commit pins checked against the upstream repositories:
[checkout v7.0.1](https://github.com/actions/checkout/tree/3d3c42e5aac5ba805825da76410c181273ba90b1)
and [upload-artifact v7.0.1](https://github.com/actions/upload-artifact/tree/043fb46d1a93c77aae656e7c1c64a875d1fc6a0a).
Dependabot proposes monthly updates; review requirements and run checks before
merging. Runner software still changes independently and must be recorded per run.

The Windows setup helper imports the selected MSVC developer environment into
later steps. It does not redistribute compiler tooling. Build and package
prerequisites must already be present on custom runner images.

See [CI requirements](../docs/ci.md) for source isolation, complete aggregation,
permissions, caches, SDK reuse and production publishing requirements.
