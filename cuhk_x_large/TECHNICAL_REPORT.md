# CUHK-X Large Model Track — Technical Report

Snapshot date: 2026-09-11  
Competition deadline: 2026-09-15 15:55 UTC / 23:55 China Standard Time  
Kaggle team name: `Jiayi Du`

## Executive summary

The two currently selected Kaggle submissions remain conservative evidence unions over a publicly released compact-graph anchor. In parallel, a new fully owned Stage2-native candidate now generates all 682 answers from arbitrary QA rows and clip features without reading that anchor or any other fixed test-answer vector. Its selection and tuning use subject-disjoint validation with clips kept intact. Test labels, manual test annotation, row-level leaderboard inference, multiple accounts, and cross-team prediction sharing are prohibited and were not used.

The two explicitly selected Kaggle submissions are:

| Role | Submission | Candidate | Public score | SHA-256 |
|---|---:|---|---:|---|
| Primary | `56122653` | `emotion_extratrees_rf_union_v1.csv` | `0.78070` | `3a76a36e6d3060979370f5b598e090c0e2436689d9eda6b17416ae8bc0aee3e4` |
| Independent fallback | `56108595` | `nonvisual_sensor_union_v1.csv` | `0.78070` | `a5d300381a79e751c08c03a36036cf56137121fc3f987832e64062b534204702` |

The public-score tie is non-diagnostic. It was not used to infer split membership, row correctness, or thresholds.

## Data and licenses

- Official Kaggle QA metadata and sample submission are used under the competition rules.
- The official CUHK-X nonvisual supplement is used only for non-commercial competition/research purposes. Organizer ZIP SHA-256: `72f34e9f0005d2ee0fefe9a7687bd54fa6dbdf171b6112132523085fa7475afb`.
- The official test visual archive is complete, CRC-valid, and hashed as `a4ba8644208e08b0bf436c85e1bfcdf5342849675f0924285b481f6a2477f7a1`.
- The official HARn training visual archive is complete, CRC-valid, and hashed as `a972d644c1b536f836fe7e4d97ca560e04dc75e5657927b2290a63bc6add7a25`.
- The public Fususu anchor notebook is Apache-2.0 and is preserved with an exact source hash.
- The pinned visual checkpoint is `mlx-community/Qwen3-VL-4B-Instruct-4bit`, revision `2fd8dacbdb8f1e54b8c005f081ec5bf79c56376b`, Apache-2.0. All 16 local checkpoint files are independently hashed.
- Competition media and derived media are not redistributed.

## Frozen method

### 1. Public compact-graph anchor

The 682-row anchor is reproduced byte-for-byte from the released Apache-2.0 Kaggle notebook. It has submission evidence `56107594`, public `0.77777`, and SHA-256 `4e3391e70d0c8ff5a40efb7c317468e8eda3f84e27b40ab3c35ea735352fda9c`. Because the full training lineage of the public artifact is unavailable, it is treated as a leaderboard-verified anchor rather than a complete finalist solution by itself.

### 2. Nonvisual sensor union

Fixed RandomForest models consume official IMU, radar, and skeleton-derived statistics. Model selection uses 18 leave-one-subject-out folds and keeps clips intact. The HARn action expert reaches `0.76690`; the HAU emotion expert reaches `0.44870`. Only precommitted high-confidence/agreement gates are permitted to override the anchor. The disjoint union is submission `56108595` and is retained as the independent fallback.

### 3. Historical sensor/vision agreement component

The one-video Qwen3-VL protocol uses one preferred modality in order `Depth_Color`, `IR`, `Depth`, one frame per second, deterministic decoding, and a task-specific multiple-choice prompt. On the previously recovered labeled subset, a sensor/VLM agreement rule was qualified before test expansion. It contributed three new rows over the nonvisual union and one object row in the visual candidate. This is historical lineage already embedded in the submitted primary candidate; it is not reopened for new router mining.

The full official test action run later produced valid outputs on 51/51 rows with zero errors. Two additional test rows satisfy the old agreement condition, but no new candidate or submission was created because the refreshed subject-cluster validation rejected VLM promotion.

### 4. Linked HAU single-action constraint

For a clip with both combination and single-action questions, the combination prediction is converted to an action set and mapped to a unique single option only when exactly one single option is contained in that set. The logical upper-bound audit is `633/633`; deployed subject-disjoint structure is `601/620`. Requiring agreement with the independent sensor expert yields `8/8` accepted parent disagreements across seven subjects and `4/4` in each fixed parity cohort. This contributes one test row in submission `56122175`, which becomes the base for the final emotion union.

### 5. HAU emotion ExtraTrees/RandomForest consensus

The final new expert is a pairwise option-ranking ExtraTrees model with fold-local median imputation, 500 trees, square-root feature sampling, minimum leaf size 2, balanced class weights, and seed `20260909`. It reaches `403/809 = 0.49815` over 18 subject-held-out folds, exceeding the independent RandomForest (`0.44870`) and XGBoost (`0.46477`) experts.

For rows where ExtraTrees and RandomForest agree and differ from the subject-disjoint parent, validation is `117/186 = 0.62903` versus parent `26/186`, net `+91`. Every subject is positive; fixed odd/even subject cohorts are net `+38/+53`; the exact sign probability is `2.76e-15`. Four new HAU emotion rows are added, producing submission `56122653`.

## Honest validation and rejected branches

- All model-selection validation is subject-disjoint where subject IDs exist; row-wise random splits are forbidden.
- Failed, empty, or invalid VLM outputs are excluded rather than counted as model predictions.
- The three-video and mosaic branches improved some historical validation metrics but each returned two empty outputs on official test; both independent preprocessing roots were stopped after their second failure and produced no candidate.
- A HAU multi-answer sensor overlay fell to public `0.72807` and was rejected without row-level follow-up probes.
- A HARn multimodal sensor expansion fell to `0.77777` and was rejected as a whole.
- The first Small20 audit was later proven to reuse 20/20 historical QA/clip pairs. It is retained only as a 20/20 deterministic pipeline replay and is not performance evidence.
- The 2026-09-11 tri-modal sensor--option semantics branch deliberately excluded the unknown-lineage 0.77777 vector and used the owned RF OOF as parent. Across 270 disagreements its candidate accuracy was only `0.37407` versus parent `0.32222`; fixed subject halves were net `+15/-1`, and the first trial-prefix environment proxy was also negative. Despite zero invalids, zero semantic mismatches across all 19,416 option permutations, and zero mismatches across 809 synonym rewrites, it failed the frozen `0.60` accuracy and both-halves-positive gates. It read no test QA and produced no test or candidate CSV.

## Fresh VLM validation and hard stop

Completion of the HARn archive yielded 374 labeled QA/clip pairs whose QA IDs and clips had never appeared in any prior VLM artifact. Before first inference, exactly 20 were frozen: ten subjects, one action and one object-interaction question per subject, with label-independent deterministic selection.

The fresh run had 20/20 readable inputs, 20/20 valid outputs, zero implementation failures, and no retries. Results were VLM `12/20` versus subject-disjoint parent `13/20`. Action was net `+3`, object interaction net `-4`; the fixed subject halves were net `+1/-2`; subject deltas were 2 positive, 3 negative, and 5 tied, giving one-sided exact sign `p=0.8125`.

Every precommitted promotion gate failed. Direct VLM and any new router direction are therefore frozen. These 20 rows must not be mined for a replacement rule. No candidate or submission was produced.

### Stage2-native owned route v1 (2026-09-11)

An independent candidate builder was implemented to remove the fixed 682-row Fususu vector from the inference path. Its owned floor is learned from organizer training QA, its HARn sensor expert uses the frozen leave-one-subject-out ExtraTrees chain, and its visual arm uses the pinned local Qwen3-VL-4B checkpoint. The route was frozen by task type: action questions allow a VLM/base veto over the sensor expert, while object-interaction questions require sensor/VLM agreement. Every row had the same eight-frame and eight-output-token budget. Promotion additionally required subject-blocked macro improvement of at least two percentage points, action and object nonnegative behavior, no subject losing more than three percentage points, positive fixed subject halves, and strong changed-row evidence.

The first 48-row cohort was invalidated before this branch ran because a concurrently written shared VLM log exposed seven of its QA/clip pairs. Those seven pairs were entered into an append-only exposure registry, all observed QA IDs and clips were excluded by both keys, and a replacement label-blind 48-row cohort was frozen without inspecting labels or results.

The network-isolation preflight passed and confirmed that neither a test inference log nor a candidate existed. The replacement run produced 35/35 valid outputs with zero logged inference errors, then reached an official five-frame clip at row 36 while the immutable loader required eight frames. Because adding a repeat-frame padding rule after fresh outputs existed would change the preregistered implementation, v1 failed closed. No incomplete-cohort accuracy was computed, the test visual pass never started, no candidate CSV was created, and no submission was attempted. A future padding-capable version must use a new protocol and exclude all 35 newly exposed QA IDs and clips.

### Full Stage2-native owned system v1 (2026-09-11)

A separate full-system route was then preregistered over all 4,087 training QA rows and 1,333 intact clips. The base decoder is implemented locally and fits only fold-training option correctness counts, option-set memory, HAU within-clip option-text support, multi-answer size priors, and sequence pairwise precedence. It does not import a public notebook or prediction vector. Two owned sensor overlays are permitted: HARn single-action skeleton RandomForest predictions when a finite skeleton row exists, and HAU emotion predictions only when independently trained ExtraTrees and RandomForest experts agree.

Across 18 leave-one-subject-out folds, the semantic base scores `2302/4087 = 0.56325` and the complete owned system scores `2542/4087 = 0.62197`, net `+240` or `+5.87` percentage points. Fixed subject halves are `+127/+113`; all 18 subjects are non-negative and the worst is `+4`. HARn single reaches `0.78555`. On 186 HAU emotion rows changed by ET–RF consensus, the candidate is `117/186 = 0.62903` versus base `26/186 = 0.13978`, net `+91`. All 24 global A/B/C/D permutations were inverted and compared across 98,088 row checks with zero mismatches; invalid predictions were zero. Every frozen core gate passed.

The optional Qwen missing-sensor fallback was tested on the complete label-independent 40-row missing-skeleton cohort. It scored `18/40 = 0.45`, produced one invalid output, and split `0.35714/0.50` across the fixed subject halves. It therefore failed its frozen `0.60` accuracy, `1.00` valid-rate, and both-halves gates even though it gained eight correct rows over the semantic base. Qwen is diagnostic-only and has no effect on the owned candidate.

Two independent network-blocked test builds then generated identical 682-row files with SHA-256 `40361ab2b6a87d5b73da3114aada27b982b37c09d205864ec8ed272701ae06b8`. The candidate contains 559 semantic-base rows, 41 HARn skeleton-RF rows, and 82 HAU emotion ET–RF consensus rows; all 682 IDs and category grammars pass. A second smoke replaced every QA ID and clip key across six rows/two clips while registering the identical features under new unit keys; predictions remained identical by row with zero invalids. Thus inference is independent of known ID/key strings once a new clip has been featurized. The candidate is `candidates/stage2_native_owned_v1.csv`. It has not been submitted and does not replace either currently selected Kaggle finalist.

The remaining raw-input boundary was subsequently closed technically through the separate `inference_owned.sh` entry point; legacy `inference.sh` remains unchanged. The new path discovers IMU, radar, and skeleton unit directories without assuming `LM_test_*` IDs, validates declared/raw inventory before extraction, reuses the exact owned feature definitions, and calls the same owned builder. Two clean network-blocked official runs each selected 195 raw units for 208 clips, hashed 22,661 files, emitted byte-identical 195-row feature caches (`7fd99f6e...f3a8`), and reproduced the existing 682-row candidate byte-for-byte. All selected-unit features exactly equal the corresponding rows in the earlier full cache. The 13 official clips absent from both the organizer manifest and raw tree retain the semantic fallback only through an explicit all-sensor-missing authorization; a missing file or unit declared by the manifest fails closed. Eight tests cover a missing declared file, missing manifest-declared unit, corrupt JSON, short skeleton stream, extra file, reordered QA/manifest, an unlisted clip without explicit authorization, and arbitrary new QA/clip identifiers. The renamed two-clip raw fixture changes every QA ID and clip path while preserving the five predictions exactly.

The TimeLogic CVPR 2026 challenge-solution report is recorded only as method inspiration: question-type routing, timestamped coarse evidence, and fixed-budget dense resampling near candidate boundaries. Its reported `77.13` official-test AvgAcc is not described here as a verified winning rank, and no official code was found. An earlier 50-row HAU comparison was frozen, but it is not currently runnable because the local HAU visual payload contains only the partial `user8` prefix while the frozen screen deliberately uses ten other subjects. Following the P1 invalid-output rejection, no further prompt-mining run or substitute cohort was opened.

### P1 verb–object–temporal decomposition screen

P1 was implemented as a clean-room prompt-structure experiment inspired by VideoGEM's action/verb/object decomposition, with a temporal evidence field and the existing sensor promotion/veto rule. This is not claimed as an exact reproduction of VideoGEM or TimeLogic. The sole 48-row screen excluded every QA ID and clip in the frozen exposure/log/manifest union and contained 12 rows in each action/object × subject-half stratum. Generic and decomposed arms used the same local Qwen revision, video, 1 FPS, 48-token maximum, and temperature zero.

The routed decomposed arm was `33/48` versus generic `12/48`, with action `+3`, object `+18`, and subject halves `+11/+10`. The mechanism was nevertheless rejected: the generic arm had 28 invalid answer parses and the decomposed arm had one invalid answer/evidence schema. Because invalid output had a frozen maximum of zero, the apparent gain is comparator-format-confounded and not promotable. No test inference, candidate mutation, leaderboard probe, or submission followed. All 48 rows were added to the shared exposure registry.

An independent control-plane audit also rejects P1 permanently. The cohort had zero overlap with the exposure union available at selection time, but it predates the stricter requirement for an atomic registry reservation and a separate label-blind minimum-frame receipt before protocol freeze. A post-hoc audit found all 48 videos readable with at least four frames and, correctly, found 48/48 conflicts after the completed run. That cannot retroactively qualify the evidence or make the cohort fresh again. Future cohorts must use `scripts/reserve_vlm_fresh_cohort.py`, which locks and rechecks both registries, manifests, and logs before appending an atomic reservation.

A second independent metrics audit reproduced the routed totals exactly: `33/48` versus `12/48`, action `+3`, object `+18`, fixed halves `+11/+10`, subject-macro gain `+0.37778`, and worst-subject delta `0.0`. All 48 videos were readable and hash-matched; paired generic/decomposed calls had identical per-QA video, 1 FPS, 48-token ceiling, model revision, temperature, sensor/base OOF, thresholds, and route. Derived frame counts range from 4 to 12 across QAs, but are identical within each prompt pair. The audit also confirmed 28 generic invalid answers, one decomposed invalid answer, one decomposed schema failure, and no preregistered runner hash. Accordingly, the large apparent gain remains output-format/truncation-confounded and P1 is rejected. Temporal evidence is also weakly differentiated: 44/48 outputs say `throughout`, and these model-generated buckets are descriptive rather than independent temporal ground truth.

Before proposing any P2 cohort, a label-blind video-readiness scan filtered the registry-v2 exposure union and inspected only identifiers, task type, subject, and media metadata. It found 218 unexposed HARn QA rows across 214 clips; every row was readable and matched the organizer manifest hash, while 206 rows have at least eight frames. The twelve shorter rows are excluded before selection, preventing another mid-screen fixed-frame failure. The proposed next protocol would consume all scarce eligible object-interaction rows, add deterministic single-action rows to balance subject halves and duration quartiles, put the final answer before evidence to prevent truncation, freeze exact eight-frame indices and token budget, and atomically reserve QA/clip pairs. It is only a proposal: no cohort was frozen and no new inference was run.

## Reproduction

The runtime used Python `3.13.2` with exact package versions in `requirements-repro.txt`. Upstream OOF predictions, fitted checkpoints, VLM logs, candidate reports, source hashes, data manifests, and official receipts are included in the reproducibility manifest. Competition data remain local and are intentionally excluded from redistribution.

Run final deterministic assembly from the campaign directory:

```bash
./inference.sh
```

This command performs no network requests and no competition submission. It reproduces the public anchor, rebuilds the nonvisual union, historical visual/sensor candidate, linked-question candidate, and final emotion union, validates both selected candidates against official local metadata, and fails unless their SHA-256 values exactly match the frozen values.

Run the independent owned raw-input path with:

```bash
./inference_owned.sh
```

It does not modify the two selected legacy submissions or submit to Kaggle. Its output is required to remain byte-identical to the existing unsubmitted owned candidate.

The current versioned reproducibility manifest and its independent verification report are under `reports/final_reproducibility_manifest_2026-09-11_v9.json` and `reports/final_reproducibility_verification_2026-09-11_v9.json`. The two selected-submission hashes and owned research-candidate hash remain unchanged. V9 includes the strengthened fail-closed raw package and verifier, all eight adversarial tests, both full clean replays, the explicit release-license manifest, the fixture evidence, and the earlier exposure-controlled research record. No Kaggle submission followed.

## Registration and remaining operational item

Kaggle rules are accepted, the competition is joined, and the external organizer registration was confirmed at `2026-09-11T04:22:09Z` for the solo team `Jiayi Du`, affiliation `Stiftung Louisenlund`, country/region `Germany`, both Large and Small tracks, and no faculty advisor. The contact email remains masked in repository text; the confirmation receipt is `official_receipts/2026-09-11T0422Z_official_team_registration.md`.

The owned CSV now has a technically complete raw-input path, but this does not authorize a submission or finalist release. The deadline conflict is operationally resolved by enforcing the earlier `2026-09-17 15:55 UTC` cutoff, and the Small final-inference no-LLM restriction is kept separate from development-time coding-assistant permission. The remaining release blockers are explicit participant approval to publish the clean-room source subset under Apache-2.0 and confirmation of organizer-only delivery terms for participant-trained model files derived from non-redistributable data. Raw organizer data are not redistributed.
