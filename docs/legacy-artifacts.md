# Preserve explicitly selected legacy archives

The manual `legacy-artifacts.yml` workflow moves no application or dependency into
an approved release. It preserves exact old Actions archive bytes in private draft
release storage so a separately reviewed cleanup can proceed without losing records.
It never discovers a replacement selection, extracts ZIP contents, executes archived
files, assesses qualification, or deletes original artifacts.

Provide an explicit JSON list in the workflow's `artifacts` input:

```json
[
  {
    "artifact_id": 123,
    "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "run_id": 456,
    "source_commit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "name": "selected-evidence",
    "size": 1024
  }
]
```

Replace every example value with an independently reviewed exact API identity.
`size` is the complete downloaded ZIP size in bytes; `sha256` is its digest, with
no prefix. The selected run and artifact must identify this repository and its
head repository. Expired, changed, duplicate or mismatched entries fail closed.
The helper compares original metadata before and after download and verifies the
complete bytes. It does not interpret members of the archive.

The list is limited to 100 entries, 16 GiB per archive and 64 GiB total. Each ZIP
is staged separately, then stored as `archive.zip` beside `origin.json` in bundle
`legacy-artifact-ID`. The origin includes the request and observed original run and
artifact metadata. Per-archive pointer receipts are written before owned temporary
staging is removed. A failure preserves incomplete staging and all earlier receipts;
the workflow summary lists completed bundles without claiming overall success.

The final `legacy-preservation` bundle contains the exact request and complete pointer
inventory. Its returned manifest pointer binds the current manual job separately
from the original producer. Storage stays a draft and never changes Latest. See
[CI storage](ci.md) for permissions and branch prerequisites.

Before any separately authorized deletion, an independent operator must fetch the
completed preservation bundle through `tools/ci_transport.py fetch` with its exact
run, attempt, source, workflow, manifest ID and digest, then fetch each referenced
per-archive bundle and recompute `archive.zip` size and SHA-256 against the original
request. Bind `origin.json` to its receipt digest as well. For an incomplete import,
fetch only explicitly recorded successful pointers with `--allow-failed`; that flag
permits storage recovery and grants no qualification. Do not execute or extract the
opaque ZIP during this check. Retain the verified mapping in durable evidence before
requesting cleanup of exact original IDs. There is no cleanup command in this helper.

This preserves old bytes and their provenance. Ordinary SDK consumers still require
the structured [SDK import](sdk.md) and normal consumer checks; opaque archives are
never an automatic build input or fallback. Unresolved redistribution terms remain
unresolved, and private retention does not authorize public distribution.
