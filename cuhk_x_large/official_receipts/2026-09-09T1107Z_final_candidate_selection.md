# Kaggle final-candidate selection receipt

Recorded: 2026-09-09 11:07 UTC / 2026-09-09 19:07 BJT

The official Kaggle Submissions page states that up to two submissions may be
selected for the final leaderboard and that Kaggle otherwise auto-selects from
the best public-scoring submissions. Three campaign submissions currently tie
at public score `0.78070`, so relying on automatic tie-breaking would not
preserve the intended private-robustness choices.

The final-candidate selection was explicitly set to `2/2`:

| Submission | Artifact | Public score | Rationale |
|---|---|---:|---|
| `56116980` | `visual_sensor_consensus_v1.csv` | `0.78070` | Primary candidate; seven gated changes including visual/sensor agreement |
| `56108595` | `nonvisual_sensor_union_v1.csv` | `0.78070` | Independent fallback; four disjoint, subject-validated sensor changes |

The page was then loaded in a new browser tab. The fresh authoritative state
still showed `2/2`; the two selected rows lacked the page's `select ...` action,
while every unselected submission retained it. This confirms that the selection
persisted server-side rather than only in local page state.

Rejected submission `56120755` (`0.77777`) and rejected multi-answer submission
`56117539` (`0.72807`) remain unselected. No submission content or score was
changed by this operation. If a later candidate passes the documented offline,
rules, stability, and schema gates, this selection can be updated before the
2026-09-15 15:55 UTC deadline.
