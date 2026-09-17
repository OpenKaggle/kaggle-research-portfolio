# VLM exposure governance v2

This mechanism prevents a QA or clip that has appeared in any local VLM run or
frozen selection artifact from being reused as fresh evidence.

## Required order before a new cohort is frozen

Write the proposal into the unscanned `work/proposed_cohorts/` staging
directory first. Do not place it in `artifacts/manifests/` until the gate
passes, because another thread's background scan must not mistake an unchecked
proposal for an accepted selection. Then, from `cuhk_x_large`, run:

```bash
python3 scripts/vlm_exposure_registry_v2.py check --cohort work/proposed_cohorts/NEW_COHORT.csv
```

- Exit `0` with `PASS_FRESH_RESERVED` means the cohort shared neither a QA ID
  nor a canonical clip ID with the registry, and the clean cohort was reserved
  atomically in the append-only registry.
- Exit `3` with `REJECT_CONFLICT` means the cohort is not fresh. Do not refill
  it after viewing outcomes; create a new precommitted selection from the
  still-unexposed pool and run the gate again.
- Exit `2` with `STOP` means a source, registry, or cohort could not be parsed.
  This is a fail-closed condition.

The gate refreshes the registry before checking. Its file lock makes the
conflict-check plus reservation atomic across local processes, so two threads
cannot reserve the same QA/clip union simultaneously.

Only after `PASS_FRESH_RESERVED` may the normal freeze step copy the exact,
unchanged cohort bytes into `artifacts/manifests/` and bind their SHA-256 in a
protocol. A changed cohort is a new proposal and must pass a new reservation.

## Registry refresh and audit

```bash
python3 scripts/vlm_exposure_registry_v2.py scan
```

The scanner covers `artifacts/vlm/*.jsonl`, structural files in
`artifacts/manifests`, and report files whose names contain `manifest`,
`protocol`, `validation`, `cohort`, or `frozen`. It only appends unseen events;
an idempotent rerun leaves the registry bytes and SHA-256 unchanged.

Registry events contain identifiers, source location and hashes, evidence kind,
and only a boolean indicating whether a prediction exists. Answer/label,
correctness, raw model output, and prediction values are never copied.
