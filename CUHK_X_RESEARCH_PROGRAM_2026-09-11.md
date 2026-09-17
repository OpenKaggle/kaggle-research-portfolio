# CUHK-X Research Program — 2026-09-11

## Program objective

The objective is not to maximize the current public leaderboard. It is to maximize the probability that team `Jiayi Du`:

1. enters the private-leaderboard Top 15 in at least one CUHK-X track;
2. survives the organizer's new-subject reproducibility verification;
3. has a technically defensible, licensable solution that can be packaged on short notice.

The official series has exactly two independent Kaggle competitions: Small Model (40-class cross-subject HAR) and Large Model (HAU/HARn VQA). Both Kaggle competitions are joined, and the official team registration for both tracks was confirmed on 2026-09-11 under the matching solo team name `Jiayi Du`.

Official challenge: <https://openaiotlab.github.io/CUHK-X-Challenge/>

## Decision update — 2026-09-11 13:53 CST

The original Large P1 verb–object–temporal screen is terminally rejected. Its apparent `33/48` versus `12/48` improvement is confounded by 28 invalid generic outputs, one invalid routed output, and a missing preregistered runner hash. It will not be retried or submitted.

The primary Large route is now `stage2_native_owned_v1`: an owned semantic base plus subject-disjoint HARn skeleton RF and HAU emotion ET/RF consensus. Across 4,087 training QA rows and 18 held-out subjects it improves from `0.56325` to `0.62197` (`+5.87pp`), with positive net gain for all 18 subjects and zero invalid predictions. Two network-blocked candidate builds are byte-identical and independent of fixed public 682-row predictions.

This candidate is not finalist-ready yet. Its current boundary starts from a precomputed nonvisual feature cache. Highest priority is now packaging the official raw sensor directory → feature extraction → owned builder → CSV path, with adversarial file tests and two clean byte-identical replays.

## Official format update — 2026-09-11 18:21 CST

Official challenge commit `2d6ecb4a548c24a2d4d335d7c4e5bf25cb2b08c6` replaces the previous verification wording. Top 15 teams must submit code, weights, inference script, README, final submission, and signed honor declaration by **2026-09-18 23:59 UTC+8**. The organizing committee then runs each package in a controlled environment and evaluates organizer-controlled private data worth 30% of final scoring. Top 6 are announced Oct 1; the technical report is due Oct 1 23:59 UTC+8; the Oct 12 Shanghai finals use 5-minute presentations plus 5-minute Q&A and no on-site private-test inference.

This resolves the previous 48-hour/Sep 22 deadline conflict and supersedes the conservative Sep 17 internal package assumption. It does not relax the Sep 15 18:00 CST research hard stop, the scientific gates, single-checkpoint constraint, deterministic raw-input replay, or license separation. Source receipt: `reports/cuhk_x_incremental_radar_round4_official_format_delta_2026-09-11.md`.

## Problem definition from the top down

### Common scientific problem

CUHK-X asks whether human activities can be recognized, understood, and reasoned about without RGB. The usable signals are Depth, Thermal, IR, Skeleton, IMU, and mmWave. The core difficulty is cross-subject generalization: apparent motion, sensor placement, body geometry, and environment differ between training and held-out people.

The scientific object is therefore not a row-wise classifier. It is a subject-robust model of:

- what action is happening;
- which object or body interaction distinguishes similar actions;
- when the decisive motion occurs;
- which modalities are present, missing, or unreliable;
- whether independent evidence sources agree.

### Small Model track

The output is one of 40 activity classes. The winning problem is efficient temporal representation plus robust multimodal fusion under a single-checkpoint constraint. The current organizer clarification allows INT8, but every inference-time learned weight must be packaged in one checkpoint smaller than 100 MB. The final inference model cannot be an LLM.

Public-rank gains are not trusted unless they survive subject-disjoint and clip-disjoint validation, deterministic offline inference, missing-modality tests, and the single-checkpoint audit.

### Large Model track

The output is multiple-choice VQA across action understanding and action reasoning. The model must combine visual temporal evidence, object interaction, question type, and nonvisual sensors. Large pretrained models and APIs are allowed, but a finalist system still has to run from new files and new IDs during verification.

The current `0.78070` submissions are useful private-leaderboard hedges, not sufficient scientific endpoints, because their base vector comes from a public prediction artifact without a complete model lineage. The priority is a Stage2-native system that generates every answer end-to-end for unseen IDs and clips.

## Evidence hierarchy

Use evidence in this order:

1. official rules, host clarifications, data manifests, and organizer code interfaces;
2. the CUHK-X paper and primary research papers;
3. reproducible winning solutions from adjacent competitions;
4. Kaggle notebooks with source, weights, validation, and licensing that can be independently checked;
5. leaderboard movement only as a final whole-mechanism check.

Never use row-level leaderboard probing, test-label inference, random row validation, hidden caches, inaccessible weights, or unlicensed code as selection evidence.

The material search stops after two consecutive batches of at least five primary sources add no new method family or risk. That saturation condition was reached on 2026-09-11; broad searching is now replaced by targeted monitoring for official changes.

## Three active research routes

### P1 — Large: verb–object–temporal decomposition with sensor gating — rejected

Keep the existing Qwen3-VL-4B asset and change the reasoning structure rather than the backbone. Generate separate evidence for action/verb, manipulated object, and decisive temporal interval. Route by question type, then use independent sensor agreement as a promotion or veto signal.

Why this route: the frozen fresh evaluation showed action questions improving while object questions regressed. VideoGEM provides primary evidence that decomposing action, verb, and object prompts can improve action grounding without retraining a new foundation model.

Promotion gate:

- subject-blocked macro gain at least 2 percentage points;
- action and object strata both non-negative;
- worst-subject loss no worse than 3 points;
- zero invalid outputs under equal frame/token budget;
- one frozen fresh screen only after the training-side gate passes;
- complete network-free inference from new IDs and clips.

Failure of any gate means rejection and restoration of the current finalist hedge; no leaderboard probe follows.

That failure condition has occurred. P1 is retained only as a negative result and must not consume another fresh cohort.

Primary reference: <https://openaccess.thecvf.com/content/CVPR2025/html/Vogel_VideoGEM_Training-free_Action_Grounding_in_Videos_CVPR_2025_paper.html>

### P2 — Small: streaming Thermal/Depth/IR TSM + frame difference

Avoid a second heavy 3D backbone. Stream only the required modality members from the official archive, use a small 2D encoder, Temporal Shift Module, and explicit local/global frame differences. First establish a Thermal-only base; add Depth or IR only when fold-aligned evidence shows complementarity.

Why this route: the CUHK-X benchmark makes Thermal, Depth, and IR strong visual priors; TSM supplies temporal exchange at nearly zero parameter cost, and TDN supports explicit short- and long-range difference modeling. This route is compatible with limited disk space and a single sub-100 MB checkpoint.

Fast-kill gate:

- fixed four held-out subjects and identical clips against the current comparator;
- median improvement at least 2 points;
- at least three of four subjects non-negative;
- worst-subject loss no worse than 2 points;
- if both first folds improve by less than 1 point, stop immediately;
- FP32 checkpoint below 95 MB, or single-file INT8 below 100 MB with no more than 0.5-point validation loss;
- two offline inference runs must be byte-identical.

Primary references: <https://github.com/mit-han-lab/temporal-shift-module> and <https://openaccess.thecvf.com/content/CVPR2021/html/Wang_TDN_Temporal_Difference_Networks_for_Efficient_Action_Recognition_CVPR_2021_paper.html>

### P3 — Small: learned missing-modality token

This route cannot start until P2 independently passes. Add a learned token for missing modalities and random modality replacement during training. Change only the fusion head so that gains can be attributed cleanly.

Promotion gate:

- missing-modality subset improves by at least 4 points;
- overall accuracy improves by at least 1.5 points;
- complete-modality subset loses no more than 1 point;
- at least three of four held-out subjects improve;
- if the first two folds gain less than 2 points on missing inputs or lose more than 2 points on complete inputs, stop.

Only the paper's idea is used; implementation is clean-room until its code license is verified.

Primary reference: <https://www.openaccess.thecvf.com/content/CVPR2025W/MULA2025/html/Ramazanova_Exploring_Missing_Modality_in_Multimodal_Egocentric_Datasets_CVPRW_2025_paper.html>

## Four-day sprint and submission policy

### Sprint 1 — Sep 11 to Sep 12: close rejected work and prove the package boundary

- Large: keep P1 terminally closed; finish the official raw-sensor-input -> owned features -> owned Stage2 builder -> CSV path. Add adversarial ordering/missing-file tests and require two clean byte-identical replays.
- Small: continue only legal payload transports and the zero-cost availability probe. Run the first two TSM folds only after an official or organizer-authorized payload passes provenance and quarantine checks.
- Research: monitor only official clarifications and implementation-critical sources.

Output: a release-gate receipt for Large and either a provenance-approved Small payload or an explicit transport-blocked receipt. No partial package is promoted.

### Sprint 2 — Sep 12 to Sep 13: complete honest validation

- Large: retain the completed subject/question slices; repair only failures found by the raw-input package harness. Do not open a new VLM cohort or restart P1.
- Small: finish four-subject validation, checkpoint-size audit, and deterministic inference replay.
- Start P3 only if P2 has already passed without using P3.

Output: at most one qualified Large mechanism and one qualified Small base mechanism.

### Sprint 3 — Sep 13 to Sep 14: robustness and packaging

- Build `inference.sh`, model manifest, licenses, exact environment pins, and raw-data-to-CSV dry-runs.
- Quantize Small only after the FP32 model is frozen.
- Stress missing/corrupt modalities and new file ordering.

Output: Stage2-native release candidates. Any result that cannot reproduce offline is discarded even if its public score is attractive.

### Sprint 4 — Sep 14 to Sep 15: sparse submissions and freeze

- Allow one Kaggle submission per independently qualified mechanism, not per row or threshold variation.
- Compare public movement only after the mechanism is frozen; do not tune back to the board.
- Retain the current two Large finalist selections unless a new candidate clears all evidence and reproducibility gates.
- Freeze final candidates, hashes, reports, and fallback artifacts before the deadline.

## Operational ownership

- `Kaggle DDL｜CUHK-X Large Model`: owned Stage2 raw-input packaging, adversarial package tests, and byte-identical clean replays. P1 is read-only negative evidence.
- `Kaggle DDL｜CUHK-X Small Model`: streaming data path, P2, conditional P3, single-checkpoint packaging.
- `Kaggle 战役｜调研与情报 A 组`: official-rule watch, source saturation, leaderboard threshold navigation, license risk.
- Root supervision: reject invalid evidence, prevent overlapping tests from being reused as fresh evidence, and control submission authorization.

Active monitors: Large every 2 hours, Small every 4 hours, research intelligence every 6 hours. Notifications are reserved for meaningful progress, failure, a qualified candidate, or required user action.

## Current rank gap and resource allocation

- Large: `0.78070`, approximately rank 39; current Top 15 threshold `0.90058`. This is the primary scientific route because all major HARn/test assets and the 4B model are already local.
- Small: only a `0.03482` format smoke; current Top 15 threshold `0.84577`. It has greater upside but starts behind and is disk-constrained, so it receives a strict streaming proof and fast-kill budget before full training.
- Current Top 6 thresholds are approximately `0.94152` for Large and `0.91542` for Small. These values guide qualification risk only; they are not model-selection targets.

After the user's explicit Small-track加码 on Sep 11, the pre-payload resource split is 45% Small legal transport, preregistration, and synthetic harness hardening; 40% Large package/next-mechanism work; and 15% official monitoring/governance. P1 receives 0% experimental budget and P3 remains at 0%. If a provenance-approved Small payload arrives, switch for the next 24 hours to 65% Small P2 folds and packaging, 25% Large, and 10% monitoring. P3 receives a bounded budget only after P2 passes its preregistered gate.

Small legal-data acquisition is itself fail-closed. As of 2026-09-11, Kaggle hosts only `test.csv` and `sample_submission.csv`; all nine organizer Google parts are quota-blocked; Baidu yields a client handoff; and the organizer's own public object API lists the Small Train and CUHK-S directories but returns empty file arrays. The official Hugging Face mirror is the remaining immediate route, but it explicitly shares the account email and username with the repository authors. No agent may click that agreement or transmit those identifiers without the user's destination-specific authorization.

The unified harness is the status authority. A research candidate may be described as scientifically valid after `.venv/bin/python scripts/run_cuhk_harness.py --deep` passes. It may be described as finalist-ready only after `.venv/bin/python scripts/run_cuhk_harness.py --release --deep` returns `PASS_RELEASE_READY`. Any manifest drift, incomplete raw-input path, or live edit fails closed and blocks submission authorization.
