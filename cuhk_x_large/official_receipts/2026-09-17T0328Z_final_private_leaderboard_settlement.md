# CUHK-X Large final leaderboard settlement

- Checked at: 2026-09-17 03:28 UTC (2026-09-17 11:28 Asia/Shanghai)
- Competition: `cuhk-x-competition-large-model-track`
- Official deadline: 2026-09-15 23:59 UTC
- Current official state: closed; Kaggle presents only `Late Submission`
- Participating teams: 213
- Team: `Jiayi Du` (`jahyee`)

## Final result

- Private leaderboard score: `0.72647`
- Private leaderboard rank: `55 / 213`
- Public leaderboard score: `0.78070`
- Public leaderboard rank: `50 / 213`
- Published private Top-15 cutoff: `0.90882`
- Outcome: did not advance to the Top-15 Selection Stage.
- Recognition: rank `55 / 213 = 25.82%`; under the published `Top 30%` criterion this is provisionally the `Distinction` tier, subject to organizer confirmation.

## Selected submissions

The two final candidates frozen before the deadline were preserved:

1. `56122653` — `emotion_extratrees_rf_union_v1.csv`
   - public `0.78070`
   - private `0.72058`
2. `56108595` — `nonvisual_sensor_union_v1.csv`
   - public `0.78070`
   - private `0.72647`

The independent nonvisual union won the private comparison by `+0.00589`. The broader linked/visual/emotion union did not generalize better privately.

## Evidence and freeze

- Official evidence was read from the authenticated Kaggle API and the logged-in competition page.
- Kaggle CLI `competitions submissions` returned the per-submission public/private scores above.
- Kaggle CLI final/private leaderboard returned `Jiayi Du` at score `0.72647`; counting the ordered table gives rank `55`.
- The downloadable public leaderboard snapshot returned rank `50` at `0.78070`.
- No CUHK-X Large training or inference process was running at settlement time.
- Reproduction remains frozen at `reports/final_reproducibility_manifest_2026-09-11_v9.json`; no late submission or post-deadline candidate mutation was made.

## Interpretation

Public ties were correctly treated as non-diagnostic, but the chosen hedge still underperformed the competition frontier. The private result confirms that the compact sensor union was the better of the two selected candidates, while the added linked/visual/emotion overrides were not private-robust enough. Future work should retain the subject-disjoint validation and reproducibility harness, but replace the public-answer anchor with a stronger owned multimodal model before spending submission slots.
