# CUHK-X Small Model Track — post-competition closeout

Verified: 2026-09-17 03:33 CST (Asia/Shanghai)

## Final competition state

- Kaggle competition: `cuhk-x-competition-small-model-track`.
- Kaggle API deadline: `2026-09-15 23:59:00`.
- Kaggle UI state: **competition completed**; the private leaderboard states
  that it reflects the final standings. The page still offers a **Late
  Submission** action, but that cannot change the official final ranking and
  must not be used as a continuation of the campaign.
- Final field: 326 teams.
- Team: `Jiayi Du`, team ID `16856843`, user `jahyee`.
- Only official submission: ID `56107602`, submitted
  `2026-09-08 21:47:36.180000Z`.
- Submission source: organizer `sample_submission.csv`, SHA-256
  `76aa7c2c4fc8759d31f2eda6d6f9fd22dfe3ad30f56d4752dd9ff8e586d25a1b`.
- Final public score/rank: `0.03482`, `309/326`.
- Final private score/rank: `0.04901`, `305/326`.
- Result: not Top 15 and not promoted to the Selection Stage. No learned model
  was represented by the submission.

Evidence sources used during this closeout:

1. authenticated Kaggle submissions API;
2. authenticated Kaggle private leaderboard UI, which showed team rank 305;
3. Kaggle downloadable public leaderboard generated
   `2026-09-16T19:28:06`, which showed public rank 309; and
4. local `SUBMISSION_LOG.csv`, reconciled to the final public/private scores.

## P2 Thermal run disposition

The P2 command previously launched against the official eight-frame Thermal
subset did not produce an auditable completion.

Closeout checks found:

- no running `train_p2_thermal_tsm.py` process;
- no `cuhkx_small/artifacts/p2_thermal_tsm/` directory;
- no `run_binding.json`;
- no `progress.json`;
- no atomic per-fold receipt;
- no P2 `report.json`;
- no learned P2 checkpoint; and
- no later Small-track Kaggle submission.

The preserved data and source do not reveal whether the old process was killed,
crashed, or ended with an error before publishing its first safe receipt.
Therefore the only defensible state is:

`NOT_COMPLETED_UNKNOWN_TERMINATION`

This is **not** evidence that TSM/signed frame differences failed. It means the
preregistered comparison was never observed. Its two-fold fast-kill and
four-fold promotion conditions were never evaluated. S2 Thermal+IMU and S3
robustness augmentation therefore remained locked.

No test archive was extracted for this experiment, no test label was read, and
no submission was created from it.

## Preserved result and data inventory

### Accepted official-data transport result

- Receipt:
  `artifacts/transport/google_p2_thermal_8f_extraction.json`
- Receipt SHA-256:
  `8758cbcc7a10cb2abf232e6b2448d544c91a64a0772df72f2bc29e48aa502c75`
- Status: `EXTRACTED_AND_CRC_VERIFIED`
- Thermal clips: 2,891
- Selected frame files: 22,734
- Selected payload bytes: 397,884,606
- Local root: `data/raw/p2_thermal_8f/HAR/data/Thermal`
- `test_data_read=false`; `submission_created=false`.

### Completed negative-control result

- `artifacts/imu_length_smoke/report.json`
- `artifacts/imu_length_smoke/checkpoint.joblib`
- Conclusion preserved from the original receipt: the metadata-only IMU smoke
  underperformed its majority control and remains `REJECT`. It is a pipeline
  control, not a candidate.

### P2 learned-result inventory

None. There is no P2 fold metric, report, or checkpoint to report, compare, or
promote.

## Reproducibility verification

On 2026-09-17, the full local Small-track test discovery completed:

```text
Ran 25 tests in 21.784s
OK
```

The passing suite covers the selective ZIP64 transport, bounded/authenticated
range handling, CRC-safe resume, quarantined-mirror rejection, frozen subject
and clip leakage checks, modality masks, sensor order/scaling, static offline
inference restrictions, single-checkpoint packaging, P2 sampling/difference
channels/TSM behavior, deterministic replay, run binding, atomic progress/fold
receipts, and CPU thread binding.

Pinned reusable source hashes:

- `src/train_p2_thermal_tsm.py`:
  `dde5d472c42a1450b5d86f35c0e334a917dfc110b857e5de0896f92adf4a8dad`
- `src/test_train_p2_thermal_tsm.py`:
  `39aa7ddb78680224d65f5f11df1ec95e258a9e7f0a6ad0de600366658e52e5fc`
- `src/selective_split_zip.py`:
  `5cb007eeb2c478a51914b3f5003b1b4694004c5dec9528a100832d8cc36c6483`
- `src/small_boundary_harness.py`:
  `2bf91c6e6df8aef7e6dac57e4ce9ba30ac4814f86fa7f4d0d1bbe5171be828ca`

## Scientific conclusion

The campaign established transport integrity and a strong fail-closed
experimental harness, but did not establish a Small-track model result. The
only scientifically valid conclusions are:

1. the official Thermal subset can be acquired selectively and reproducibly;
2. the P2 comparison can be run under subject-disjoint, clip-disjoint,
   test-blind controls;
3. the actual B0-versus-P2 effect remains unknown; and
4. the Kaggle smoke score says nothing about the quality of P2 because P2 was
   never submitted.

## Next-edition handoff

If a future CUHK-X edition has compatible rules/data, reuse the assets in this
order:

1. Treat the current Thermal root as a versioned cache only after rechecking
   the extraction receipt and organizer permission for the new edition.
2. Run the frozen two-fold B0/P2 quick-kill on a machine with observable epoch
   progress and safe receipts. Do not infer a result from process runtime.
3. Continue to four folds only under the preregistered gate; preserve subjects
   9 and 24 as untouched confirmation subjects.
4. Unlock Thermal+IMU only after a real four-fold P2 pass.
5. Generate test predictions only from a promoted, reproducible,
   single-checkpoint candidate under the then-current rules.

Do not resume official submissions for the 2026 competition; it is closed.
