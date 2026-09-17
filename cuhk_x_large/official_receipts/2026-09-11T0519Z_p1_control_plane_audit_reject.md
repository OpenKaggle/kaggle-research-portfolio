# P1 control-plane audit — REJECT / no retry

The independent post-run control audit confirms that P1 remains rejected. Its 48-row manifest was label-blind and had zero overlap with the exposure union recorded at freeze time, but the later control plane requires an atomic exposure reservation and a label-blind minimum-frame receipt before freeze. Neither artifact existed for P1. A posthoc readability audit found all 48 videos readable with a minimum of four frames, but also correctly found all 48 rows now exposed; they cannot be retroactively reserved or rerun as fresh.

The original scientific failure independently remains sufficient: 28 generic invalids, one decomposed answer invalid, and one decomposed evidence-schema invalid against an invalid=0 gate. No test inference, candidate, leaderboard probe, or submission followed.

- Audit: `reports/p1_independent_control_audit_v1.json`
- Posthoc fail-closed check: `reports/p1_posthoc_control_plane_audit_exposure_reservation.json`
- Future atomic reservation tool: `scripts/reserve_vlm_fresh_cohort.py`
