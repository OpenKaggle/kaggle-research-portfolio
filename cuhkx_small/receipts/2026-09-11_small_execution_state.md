# CUHK-X Small Track — controlled execution state

Checked: `2026-09-11T05:57:09Z` / `2026-09-11 13:57:09 CST`.

This is an append-only status receipt under `../../CUHK_X_CONTROL_PLANE.md`.
It records control state only and is not evidence of model progress.

## Three independent gates

- **Transport — `BLOCKED`:** no official or organizer-authorized,
  provenance-accepted minimum training payload is readable through the current
  legal public transports.
- **Scientific — `NOT_RUN_PAYLOAD_BLOCKED`:** no accepted raw Thermal frame is
  present, so neither frozen P2 subject 6 nor subject 18 has been fit. The
  rejected metadata-only IMU smoke is not scientific evidence.
- **Release — `REJECT_NO_TEST_CANDIDATE`:** no Small candidate has passed the
  four-subject, one-checkpoint, licensing, and deterministic-replay gates.

These states are deliberately independent. Harness or implementation progress
cannot turn the scientific or release gate green without an accepted real
sensor payload and the preregistered measurements.

## Isolation and research-only assets

- `data/public_mirror/cuhk-thermal-dataset.zip` remains an incomplete,
  unextracted, unused quarantine artifact. SHA-256:
  `bf772d205d0439546bba2b64c8f1fdbe3d01f549f6ef4dab319530bea011ebe0`.
- Its fail-closed sentinel is `data/public_mirror/QUARANTINED.json`. SHA-256:
  `5c19163285865831cf0c2a6d2139338b9d9e2d7f715e8292a42fb369b2b2e954`.
- P2 discovery rejects every path containing a `public_mirror` component; the
  dedicated regression test passes.
- K-KUNO and its AGPL YOLO weight remain research-audit material only. They
  were not executed, copied into P2, combined into a checkpoint, or repackaged.
- Hugging Face and other contact-information-gated routes remain disabled
  without explicit user authorization for the exact destination.

## Frozen path and current bindings

The experiment order remains Thermal payload verification, subjects 6 and 18
fast-kill, then subjects 5 and 21 only if the two-fold screen passes, followed
by the single-checkpoint size audit and two byte-identical offline replays.
P3 remains locked until P2 independently passes its full gate.

Current hashes after the quarantine guard was added:

- frozen P2 preregistration:
  `70d6e3fc28be25f3729e95099258a6fcc04d244f6d5c5f1142717ced50933c59`;
- P2 training implementation:
  `5145ba41e3e4a8a1286f97163fd85293d885e7acd042da88ea4b9a0af519e71a`;
- P2 tests:
  `d1b0473fbd0f646b44b207cf6884fcec50f681a1f4293c9ad1cf74f953d796ce`;
- selective reader:
  `36d4ff5027950c46ba8da0efb6148c3e8ec680d9eab4116b91def022ca0fb55e`;
- source manifest:
  `968442812f149491a15936e4dde08bdf852f3d1d5ef2356e0e1a354d1d0f39e4`.

The implementation/test hashes above supersede the pre-quarantine hash lines
in `2026-09-11_p2_tsm_scaffold.md`; the frozen preregistration is unchanged.

## Unified harness result before this receipt

`.venv/bin/python scripts/run_cuhk_harness.py --deep` executed all six Small
tests successfully, including the quarantine regression. The campaign-wide
harness returned `FAIL_SCIENTIFIC_HARNESS` only because the active Large branch
had two known v7 manifest size/hash drifts. This is an expected global
fail-closed condition and does not constitute either Small progress or a Small
failure.

No test data was opened, no prediction was generated, and no submission was
made.
