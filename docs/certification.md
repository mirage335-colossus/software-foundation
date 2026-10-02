# Certification of exact release bytes

Certification is a separate operation after assembling the immutable candidate.
It does not rebuild or replace the candidate's application assets. Source checks
compile the recorded application source; archive checks execute the supplied
archives; recovery checks install the retained SDK and reconstruct inputs without
the original base. A branch change cannot repair an earlier release.

The local [release assembler](../tools/release.py) validates and retains source,
application archives, member inventories and exact SDK binary/source/checksum
groups. [The certifier](../tools/certify_release.py) calls that verifier before and
after checking coverage. Its output must live outside the immutable release tree.
It never publishes, replaces assets or modifies a remote channel.

## Support inventory and frozen plans

[release-policy.json](release-policy.json) defines `core` and `all-gui` profiles.
They are required coverage, not a declaration that these environments have passed.
The all-GUI profile names every supported backend; unresolved supplier terms or
an unavailable target cannot be hidden by passing the smaller profile. Adapt the
policy to a new product's honest support promise before creating its release.
Keep named browser environments bound to specific engine/version combinations in
the actual runner configuration and report.

Every delivered target/backend needs source, archive and recovery checks. Linux
adds ABI and Debian package checks; old and newer user-space archive jobs remain
separate. Containers share their host kernel. They do not qualify a different
kernel, physical device, graphical session, or Windows client installation.

A coverage specification contains:

- `schema_version: 1`, `mode: release` and an explicit `checks` array.
- `subject.source_sha256`: the recorded source archive digest.
- `subject.inventory_sha256`: the SHA-256 of the exact `release.json` bytes.
- `subject.configuration_sha256`: `coverage.digest({"policy": POLICY, "profile": NAME})`.
- `inputs`: relative input filenames and exact digests to recheck before and after
  each command. Include the actual source/test/recipe inputs the command consumes.
- Each check has unique `id`, `scope`, `target`, `environment`, `backend`, boolean
  `required`, argument-array `argv`, positive `timeout_seconds` and
  `warning_seconds`, and `expected_tests`. A nonempty expected test list requires
  `junit`, a relative file inside that check's evidence directory. Every policy-required
  scope also declares `qualification: "qualification.json"`.

`argv` may use `{python}`, `{root}` and `{evidence}`. Execution uses no shell, runs
in the specified root, creates a fresh evidence directory, retains a bounded
console log, records host details and rechecks inputs. JUnit must contain exactly
the requested tests, with no duplicate, failed or skipped case. Commands without
JUnit can serve diagnostic commands. Release checks also need the bound receipt
from a self-verifying adapter. A successful empty command cannot qualify a release.

```sh
python3 tools/coverage.py freeze --spec build/check-spec.json --output build/check-plan.json
python3 tools/coverage.py run --plan build/check-plan.json --check CHECK_ID \
  --root . --run-id local-candidate --attempt 1 --output build/evidence/CHECK_ID-attempt1
python3 tools/coverage.py merge --plan build/check-plan.json --output build/coverage.json \
  build/evidence/*/result.json
python3 tools/certify_release.py --release dist/candidate \
  --policy docs/release-policy.json --profile core --plan build/check-plan.json \
  --output build/certification-run1.json build/evidence/*/result.json
```

Replace `CHECK_ID` with a check declared in the plan and run every check on its
named environment. Never run a Windows-labelled check on Linux and treat its label
as evidence. The producer records actual host identity; the orchestration layer
must provide the declared environment. Do not overwrite a result to retry: create
a new attempt directory. Aggregation uses one explicitly selected result per check
from the same run. A previous attempt may be reused only under the unchanged plan;
its actual attempt and logs remain visible.

## Authoritative check adapters

[`release_check.py`](../tools/release_check.py) implements `source`,
`archive`, `recovery`, native `abi` and disposable-container `apt` scopes. It verifies the candidate before and after
execution, checks actual target identity, and writes the receipt only after the
operation completes. For example, the argument array for a native archive check is:

```json
["{python}", "{root}/tools/release_check.py", "archive", "--release", "{root}/dist/candidate", "--target", "linux-x86_64", "--backend", "core", "--evidence", "{evidence}"]
```

Source qualification also builds a consumer against the exact delivered library
and CMake export, so success from a newly rebuilt SDK cannot hide a damaged shipped
SDK. Source and recovery scopes restore the exact source archive and matching retained
dependency groups, build the complete enabled source scope and preserve its JUnit
plus individual unit-case reports. Unexpected inner skips, missing prerequisites,
failed subtests and expected failures cannot be hidden inside a green CTest case.
Platform exclusions are explicit named cases in `run_tests.py` and stay visible
in receipts. Recovery receives only the candidate's retained input copies. Run it
inside an environment with network access disabled to establish an offline claim.

Native archive checks relocate and execute the exact CLI and selected GUI backend,
including its shared smoke scenario. ELF or PE audits inspect the shipped files.
Windows recovery checks the actual selected linker against the dependency producer
and supplies the verified restored export to the build. A Linux container receipt
records its real distribution; it does not turn a newer host kernel into an old one.

Browser source/recovery scopes use the retained Wasm SDK, execute the installed
consumer through its Node runtime, then run the rebuilt module in the selected
actual browser. Browser archive checks use copied assets and the harness preserved
in the exact source archive. Pass `--browser firefox --firefox /path/to/firefox` or
`--browser chromium --browser-executable /path/to/chromium --driver /path/to/chromedriver`.
The receipt retains engine/version, exact input hashes, interaction checks, geometry
and captures. Missing browsers fail; no browser is downloaded by qualification.
Desktop browsers remain host prerequisites, outside the compiler SDK. The explicit
CI prerequisite plan selects either existing host tools or a distribution package
and verified repository for the actual operating system. Native Ubuntu checks
inspect the installed browser and, for Chromium, ChromeDriver; they bind the actual
OS, architecture, versions and executable hashes without installing a browser.
Distribution checks retain package versions, repository policy and signing identity.
Both paths recheck the selected executable bytes after execution; neither
substitutes another distribution for the named check. Pass its receipt with
`--browser-prerequisite` and the frozen plan with
`--browser-prerequisite-plan`. The adapter checks the source/inventory, target,
backend, scope, plan, check, run and attempt, actual host and selected executable.
It then compares the observed browser version and preserves the unchanged receipt
as hashed evidence. A package-install log alone cannot certify browser behavior.

Windows Rev qualification uses a separately retained host graphics input through
`--windows-graphics-archive`. The application and SDK contain no software graphics
driver or desktop browser. The [Windows graphics prerequisite](windows-graphics.md)
is qualified with a real native WGL probe, exact loaded DLL paths and bytes, and
required capabilities before running unchanged GUI checks. Temporary driver staging
is confined to the disposable executable directories and removed only after every
owned child has stopped. Compiler/probe/test logs and final cleanup receipts stay
with the check; driver files are excluded from application archives. Failed graphics
setup is an incomplete qualification, never permission to skip appearance checks.

The `apt` adapter requires Linux running as root inside an explicitly selected
Docker/Podman container and `FOUNDATION_DISPOSABLE_CHECK=1`. It refuses ordinary
host use, already installed application packages and colliding payload paths.
Prepare `apt-get`, `dpkg-deb`, `gpg`, `gpgv`, `gpgconf` and `openssl` outside the
check. It packages the exact archive twice with increasing disposable packaging
versions, creates a temporary signing key and HTTPS loopback repository, validates
TLS against its own CA, and runs real APT refresh, installation, upgrade and purge.
Each installed file, version and runtime self-check must match; corrupted signed
metadata must fail specifically at signature validation. Private signing keys are
neither served nor retained in evidence. Cleanup stops the server and signing
agents; failure never produces a passing receipt. Retain `apt.log` with its bound
digest. These synthetic package versions qualify the delivery mechanism while
preserving the exact candidate archive, not an invented application-version upgrade.

Arch and Gentoo client install/update/remove scopes require native environment
adapters with the same receipt contract. The adapter must verify the candidate, execute that scope against its
exact assets and retain observations; a label or placeholder command is insufficient.
`qualification.json` contains schema version, source and inventory digests, target,
backend, scope, actual `coverage.host_identity()`, passing status, nonempty executed
assertion names, details, and a relative filename-to-digest `evidence` map. Source
receipts require exact nonempty test names and `source.junit.xml`. The policy is
intentionally unsatisfied until every promised environment supplies its real adapter
evidence. The [validation record](validation.md) states which environments were
actually exercised here.

Coverage owns the complete process tree until its writers stop. A private Linux
supervisor acts as a child subreaper, including nested sessions and process groups;
it does not change the shared agent harness. Windows children enter a kill-on-close
Job Object before execution. Other POSIX hosts require a qualified adapter. External
services and transferred output ownership require separate OS or harness confinement. A parent exit cannot
silently release a still-writing child.

## Gates and outcomes

The certifier rejects diagnostic mode, changed source/inventory/policy, missing
platforms or backends, duplicated scopes, mandatory scopes made optional, missing
results and altered evidence. It re-parses JUnit rather than trusting only a
summary's pass flag. Reports use distinct passing, failing and incomplete states.
Near-limit complete successes may produce `passed_with_warnings`; this does not
waive assertions. Required incompleteness always blocks the supplied policy.

The optional `--experiment` flag preserves successful evidence but prevents stable
promotion eligibility. An `eligible_for_promotion` result authorizes no action by
itself: maintainers still follow their release authorization and publication
procedure. Before promotion, re-read exact remote assets, tag/application identity,
certification run/attempt and current channel policy. After promotion, verify the
channel resolves to those same bytes. Serialize publishers without cancellation.

Hashes establish byte identity, not who created a result. Treat plans, trusted
runners, checkout permissions and signing credentials as part of the trust model.
Untrusted branch code cannot safely receive publication credentials or execute on
privileged workers. Preserve reports and logs durably beside the release while
keeping the immutable application inventory separate from appended certification
attempts. A failed later attempt stays visible alongside earlier evidence.
