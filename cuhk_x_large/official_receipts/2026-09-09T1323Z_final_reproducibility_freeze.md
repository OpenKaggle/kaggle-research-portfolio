# Final reproducibility freeze receipt

Recorded: 2026-09-09T13:23:00Z

Historical status: this is the first freeze. The subsequently completed official test archive and deterministic VLM replay audit are intentionally outside this snapshot. The versioned v2 manifest supersedes it for the current workspace state.

## Frozen selection

- Primary Kaggle selection: submission `56122653`, candidate `candidates/emotion_extratrees_rf_union_v1.csv`, SHA-256 `3a76a36e6d3060979370f5b598e090c0e2436689d9eda6b17416ae8bc0aee3e4`, public score `0.78070`.
- Independent fallback selection: submission `56108595`, candidate `candidates/nonvisual_sensor_union_v1.csv`, SHA-256 `a5d300381a79e751c08c03a36036cf56137121fc3f987832e64062b534204702`, public score `0.78070`.
- The Kaggle UI was previously reloaded and confirmed both selections persisted (`2/2`).

## Freeze and independent verification

- Manifest: `reports/final_reproducibility_manifest_2026-09-09.json`.
- Manifest SHA-256: `b5ad21e638d47b8fb0fc406a59cb7442635a921bd2c969a99c6cbcbb1d252c4d`.
- Independent verification report: `reports/final_reproducibility_verification_2026-09-09.json`.
- Verification report SHA-256: `a0659db50b25e031d942c58db96b536c7457f84bbc8ba771cdd91cd6bc46461d`.
- Verification status: `PASS` at `2026-09-09T13:23:57.328367+00:00`.
- Verified project artifacts: 64/64 by exact byte length and SHA-256.
- Verified pinned Qwen3-VL-4B checkpoint files: 16/16 by exact byte length and SHA-256.
- Verified selected candidates: 2/2, each exactly 682 rows with official test ID/order and category answer grammar.
- Verified experiment log: 49 rows, each satisfying the fixed 16-column schema; both selected submission references are present.

## Reproduction code

- Manifest builder: `scripts/build_final_repro_manifest.py`, SHA-256 `ef784570f7ee0814a716eca6e1ee217f2afc640262ee0304a26d5d8779fbe53f`.
- Independent verifier: `scripts/verify_final_repro_manifest.py`, SHA-256 `92fa60b50234a0eb30a1cf672d4c617ef43b2b11573848400e43973f958010b2`.
- The manifest records Python and relevant package versions, the pinned model revision/license, artifact lineage, the fixed selected submission references, and the exact verification command.

## Remaining external action

The official external registration remains incomplete because automation does not have the user's real contact email, affiliation, country/region, or exact team member name(s). Team name must remain exactly `Jiayi Du`. No identity values were fabricated and no registration terms were accepted on the user's behalf.
