# SDK and workflow cleanup: hosted observation

Implementation is based on `ea0e17f` plus the local 2026-10-05 cleanup/capacity
changes. The affected offline suites passed 433 cases in 26.7 seconds; the added
private-budget projection case also passed. Focused CI-selection tests, workflow
lint, documentation validation and whitespace checks passed. These checks exercise
growth, complete inventories, provenance, precise deletions, retries, active
consumers and storage-pressure failures. No SDK
rebuild, full qualification, remote publication or deletion was run for this edit.

On the next separately authorized normal workflow/publication, observe the new
SDK same-slot retirement receipt and successful full-run cleanup summary. The
completion hook requires the changed workflows on the default branch; the first
marked run establishes a baseline and the next matching full run can prune it.
Confirm current evidence, unrelated releases and retained SDK drafts survive.
Do not manufacture additional expensive runs solely for this observation.

Before private operation, complete the account checks in
[the storage budget](../docs/ci.md#private-account-storage-budget): private Packages
inventory was inaccessible, and existing nonzero spending caps do not enforce
the user's included-only storage policy. No billing settings were changed.
Hosted execution and a zero-overage private-account configuration are unverified,
not passing qualification or authorization for paid storage.
