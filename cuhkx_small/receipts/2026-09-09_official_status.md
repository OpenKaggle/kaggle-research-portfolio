# Official status receipt

Receipt generated: `2026-09-08T21:52:17Z` / `2026-09-09T05:52:17+08:00`.

## Kaggle entry and timeline

- Browser confirmation after accepting the rules: `You have accepted the rules for this competition. Good luck!`
- Kaggle API competition ID: `150044`
- Final submission deadline: `2026-09-15 15:55:00 UTC` = `2026-09-15 23:55:00 Asia/Shanghai`
- API merger deadline: `2026-09-15 15:55:00 UTC`
- API new-entrant deadline: `None`; direct Join succeeded on 2026-09-08 UTC, so entry was still open at that time.
- Competition enabled: `2026-06-20 04:21:14.947000 UTC`
- Maximum daily submissions: `5`
- Maximum team size: `3`
- Maximum final submissions: `2` (rules page)
- Metric: classification accuracy (`CUHK-X- SM-Metric` in API)
- Submissions disabled: `False`
- Team count at query: `304`
- `userHasEntered`: `True`
- Kaggle team: `Jiayi Du`; one member, `Jiayi Du` / `jahyee`, team leader.

Timeline discrepancy to treat conservatively:

- Kaggle API reports the team-merger deadline equal to the final deadline.
- The organizer challenge site says team mergers lock seven days before the submission deadline, which implies `2026-09-08 15:55 UTC` / `23:55 Asia/Shanghai` and had already passed when this receipt was made.
- Do not assume a merge is still permitted without a successful Kaggle UI check or written organizer clarification.

## Rules and license gates

- Model size must be at most 100 MB.
- Allowed architecture families: CNN, RNN, Transformer.
- No large pretrained backbones.
- No closed-source APIs or LLMs for development.
- No API/LLM labeling of training data.
- No test labels in training and no manual labeling of test samples.
- No multi-account participation or inter-team collusion.
- Competition data: non-commercial research/academic/education only, not redistributable, subject to CUHK-X License v2.0 and access control.
- External data are allowed only under the stated reasonableness and licensing requirements.
- Private leaderboard determines Top 15 for selection; public leaderboard is reference only.
- Top 15 package due `2026-09-22 23:59 UTC`: training and inference code, checkpoint, `inference.sh`, README, signed honor declaration.
- Verification uses a recorded Zoom live run plus organizer reproduction; an accuracy gap greater than 10% from the private score causes disqualification.
- Finalists must open-source the winning solution under Apache 2.0, subject to the rules.

## Awards and later deliverables

- Private-LB Top 15: Selection Stage, 2026-09-16 through 2026-09-30.
- Top 6: UbiComp 2026 finals on 2026-10-11 in Shanghai (remote Zoom participation supported).
- Final scoring: private LB 20%, on-site private test 30%, reproducibility 10%, report 20%, presentation 10%, efficiency 10%.
- Cash pool per track: USD 10,000 (USD 6,000 / 3,000 / 1,000), decided at the finals rather than by Kaggle alone.
- Up to USD 500 travel reimbursement per in-person finalist team.
- Successful Participation certificate requires at least one valid submission.

## External registration

The organizer's registration form was visibly open at receipt time. It requires:

- Team Name — must exactly match Kaggle: `Jiayi Du`
- Contact Email
- Affiliation
- Country / Region
- Track: Small Model Track (HAR)
- Team member name(s), 1–3; first member is leader
- Optional faculty advisor
- Required agreement to competition rules and Kaggle Terms of Service

No closing date is stated on the form. It is still accepting input as of the receipt timestamp. No identity fields were invented or transmitted.

## Official dataset inventory

Kaggle hosts two CSV files only. The actual sensor archives are on organizer-linked mirrors.

- Training: `HAR.z01` through `HAR.z08` plus `HAR.zip`, split archive.
- Testing: `small_model_track_test.zip`.
- Class map: `class_mapping.csv`.
- Hugging Face current files total: 47,409,805,447 bytes (47.4 GB / 44.154 GiB) and gated on sharing contact information.
- Training split archive: 44,622,809,265 bytes (41.558 GiB); test archive: 2,786,949,673 bytes (2.596 GiB).
- Google Drive mirror was accessible; test archive displayed size: 2.6 GB.
- Modalities: `Depth_Color`, `IR`, `Thermal`, `IMU`, `Radar`, `Skeleton`; some clips omit modalities.
- Labels: training action-folder prefix, integer 0–39.
- Test set: 405 anonymized clips.
- Local disk free at audit: 34 GiB, insufficient for the full 47.4 GB mirror plus extraction/workspace overhead.
- Exact official mirror sizes and LFS SHA-256 values are recorded in `OFFICIAL_DATA_MANIFEST.csv`; they were read from the public Hugging Face metadata API without requesting gated access or sharing contact data.

## Organizer baseline and compute receipt

- Official repository: `https://github.com/openaiotlab/CUHK-X`
- Local path: `vendor/CUHK-X`
- Pinned commit: `df03910a6960db5af9179e370e130bf61d9616d0`
- Commit timestamp: `2026-09-07T15:10:46+08:00`
- Working tree after clone: clean; source is unmodified.
- Repository footprint: 203 MB.
- Repository license file SHA-256: `f91f3c1aee1491a919a88cf2cdcd247532ef0d21b2b412882163ccac5ea06a03`
- SM requirements SHA-256: `14429e8ae43fa2fff4fa6b8ea13188448974fea18f8cdc53afbb255b6146c4a1`
- Official SM code includes separate RGB/depth/IR/thermal, radar, skeleton, and IMU training paths. Only competition-permitted non-RGB inputs may be used.
- Local hardware: Apple M4 Max, 14 CPU cores, 36 GB unified memory.
- Existing campaign virtual environment: Python 3.13.2; PyTorch is not installed.
- Official pinned requirements target PyTorch 2.3.0 with CUDA 12 packages and recommend a CUDA GPU, so the current environment is not a ready reproduction environment.
- No dependencies were installed and no source files were edited, preserving the organizer baseline exactly and avoiding prohibited LLM-assisted development.

## Kaggle CSV manifest

| File | Bytes | Rows incl. header | SHA-256 |
|---|---:|---:|---|
| `cuhk-x-competition-small-model-track.zip` | 2,867 | n/a | `5cf44441014fd10fb7b1ec2818dc9e72b291aab063953316b4ea4f984df22a4c` |
| `test.csv` | 15,812 | 406 | `b96520369b3f48a94db04be44ba1f695629471488c69acf48c2a9f7ce47b3afb` |
| `sample_submission.csv` | 16,531 | 406 | `76aa7c2c4fc8759d31f2eda6d6f9fd22dfe3ad30f56d4752dd9ff8e586d25a1b` |

Actual schema is `path,prediction`, not the stale `id,label` wording shown in part of the Overview. Both files contain 405 data rows. The official sample passed all format gates: exact columns, unique/non-null paths, exact path order match, integer/non-null predictions, range 0–39, and all 40 classes represented.

## First valid submission

- Submission ID: `56107602`
- File: organizer-provided `sample_submission.csv`
- Submitted: `2026-09-08 21:47:36.180000 UTC`
- Description: `Official sample schema smoke test; organizer-provided predictions; no test-label use`
- Status: `COMPLETE`
- Public score: `0.03482`
- Private score: not yet available
- Daily quota used by this campaign at receipt time: `1 / 5`

This is a schema smoke test, not a trained model baseline. It is retained because it establishes a valid submission and the participation threshold without using prohibited development methods.
