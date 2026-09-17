# CUHK-X Small Model — research and split sprint

Checked: `2026-09-11` Asia/Shanghai. This is an offline promotion-gate receipt.
No test prediction or Kaggle submission was created.

## Rule boundary used

The official host's discussion clarifications are controlling:

- AI coding assistants are allowed for writing/debugging; the final inference
  model cannot be an LLM:
  https://www.kaggle.com/competitions/cuhk-x-competition-small-model-track/discussion/724942
- All weights loaded at inference, including every ensemble member, must be
  bundled into one checkpoint smaller than 100 MB. Quantization is allowed:
  https://www.kaggle.com/competitions/cuhk-x-competition-small-model-track/discussion/729056
- External data and pretrained models are permitted when publicly obtainable
  through reasonable effort and disclosed in the report:
  https://www.kaggle.com/competitions/cuhk-x-competition-small-model-track/discussion/724404

## Research decision

The CUHK-X paper reports single-modality HAR results of Thermal 92.57%, Depth
90.46%, IR 90.22%, Skeleton 79.08%, Radar 46.63%, and IMU 45.52%. These are the
authors' benchmark results, not our validation results.

Three candidate research routes were compared:

1. **Thermal clip CNN — first acquisition/training priority.** It aligns with
   the strongest modality in the original paper. Uniform temporal sampling,
   a small frame encoder, and clip-level logit pooling are the shortest route
   to an independent candidate. The training payload for Thermal is about
   3.52 GB, so selective acquisition is practical once the archive directory
   endpoint works again.
2. **Skeleton + IMU temporal encoders with late fusion and modality dropout —
   second priority.** It is much smaller in storage and naturally supports the
   missing/empty-sensor cases observed in test. ActionMAE is primary evidence
   that random modality dropping and feature-level transformer fusion improve
   missing-modality robustness. Its reference implementation is MIT-licensed,
   but no code was copied. The public Kaggle `Skeleton + IMU Specialist`
   notebook has 0 executed cells and 0 outputs, so it is a sketch, not evidence.
3. **Depth + IR compact video CNN — deferred.** It is promising, but more
   expensive locally. The public YOLO/R(2+1)D family has unavailable weights,
   incomplete split evidence, and a two-file weight package; its public score
   is not used as an offline tuning target.

Primary sources:

- CUHK-X paper: https://arxiv.org/abs/2512.07136
- Organizer repository: https://github.com/openaiotlab/CUHK-X
- ActionMAE paper: https://arxiv.org/abs/2211.13916
- ActionMAE official repository: https://github.com/sangminwoo/ActionMAE
- HAMLET multimodal-attention paper: https://arxiv.org/abs/2008.01148

## Data and compute gate

- Full stored training payload: 41.427 GiB; retain-plus-extract minimum:
  82.985 GiB before experiment headroom.
- Free local space at check: 37 GiB.
- Training payload-ready clips: 0.
- Official Google Drive returned `Google Drive - Quota exceeded` for a bounded
  central-directory request on this run. The official Hugging Face mirror
  returned HTTP 401 pending its contact-sharing gate. No large archive was
  downloaded.
- Test archive remains complete and unextracted: 2,786,949,673 bytes,
  SHA-256 `d1b490dad87555802f213d8645ca828ed28bc94d7555f2971f11e946460db0ab`.
- Host: Apple M4 Max, 14 CPU cores, 36 GB unified memory, Python 3.13.2.
  NumPy/pandas/scikit-learn/SciPy are present; PyTorch and MLX are absent.
- Organizer code remains reference-only because CUHK-X License v2.0's
  non-commercial code term is operationally incompatible with the required
  Apache-2.0 finalist release without written clarification.

## Implemented minimum closure

`src/audit_subject_splits.py` is an original Apache-2.0 audit utility. It reads
the organizer-published IMU index only. It does not inspect test content, train
a model, or generate predictions.

Input:

- `vendor/CUHK-X/SM/Code/imu/data_imu/activity_40/dataset_fold_1.csv`
- SHA-256:
  `b8899369d158c8fe6c8c20fce1bed21a8340026c541013b6c90f7cd5595b0f6b`
- 2,768 clips, 18 training subjects, 40 classes.

The utility validates three fixed six-subject folds, each containing three
subjects from users 1–9 and three from users 16–24:

| Fold | Validation subjects | Train / valid clips | Env split | Subject overlap | Clip overlap | Classes present |
|---|---|---:|---:|---:|---:|---:|
| 0 | 3,6,9,18,21,24 | 1,808 / 960 | 495 / 465 | 0 | 0 | 40 |
| 1 | 2,5,8,17,20,23 | 1,933 / 835 | 395 / 440 | 0 | 0 | 39 (class 25 absent) |
| 2 | 1,4,7,16,19,22 | 1,795 / 973 | 431 / 542 | 0 | 0 | 40 |

The deterministic constant train-majority control predicts class 36. Its
validation accuracy is 12.50%, 8.86%, and 12.13%; macro recall is 2.50%, 2.56%,
and 2.50%. Per-subject and per-environment values are emitted by the script.
The class-25 absence in fold 1 must be handled explicitly in any macro report.

Reproduce:

```bash
python3 cuhkx_small/src/audit_subject_splits.py \
  cuhkx_small/vendor/CUHK-X/SM/Code/imu/data_imu/activity_40/dataset_fold_1.csv
```

## Promotion decision

No real model was trained. Therefore parameter count, checkpoint bytes,
per-subject/per-class/per-environment model accuracy, latency, and
missing-modality robustness are unavailable. Projected numbers and public-LB
claims are not accepted as substitutes.

A future route may generate a test candidate only after it records:

1. one checkpoint `<100,000,000` bytes containing every inference weight,
   plus exact parameter count and SHA-256;
2. overall accuracy and macro recall plus every subject, class, and environment
   slice on these subject- and clip-disjoint folds;
3. comparison with the constant control and a same-modality simple CNN;
4. each single-modality-drop condition and the actual missing/empty conditions;
5. memory, latency, and an under-two-hour reproducible inference run; and
6. model selection that never uses the public leaderboard.

Decision: **REJECT_NO_TEST_CANDIDATE**. The blocking cause is missing training
payload and runtime, not the obsolete AI-assistant interpretation.
