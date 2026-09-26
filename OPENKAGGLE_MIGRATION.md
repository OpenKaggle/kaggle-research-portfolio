# OpenKaggle migration record

## Preserved source history

The organization repository was created by mirroring the public history of
`Jah-yee/kaggle-research-portfolio`. The imported `main` branch ended at:

```text
33ee5bfc2fc2b4b6aff9610cc61c509fa4fc2b29
```

The matching remote hash was read back from `openkaggle/kaggle-research-portfolio`
before organization-only documentation was added. The personal repository was
left intact; this record is a content-preserving mirror, not a claim that GitHub
issues, stars, permissions, or ownership metadata were transferred.

## Why the portfolio is being split

The original repository is a cross-competition index and compact source
archive. Competition-level repositories make status, licensing, provenance,
and reproduction instructions easier to review without splitting large binary
files merely to evade hosting limits.

The split repositories intentionally omit raw competition inputs, model
weights, generated submissions, virtual environments, caches, and other bytes
whose redistribution or ordinary Git hosting is inappropriate. Their public
archive and provenance files describe the boundary explicitly.

## Verification standard

A migration is considered complete only after the organization branch hash is
read back and a fresh clone can resolve the published commit. Local workspaces
with uncommitted work or unique unarchived payloads remain protected until that
condition and their separate artifact-recovery requirements are satisfied.
