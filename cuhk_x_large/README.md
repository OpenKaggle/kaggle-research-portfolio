# CUHK-X Large Model Track campaign

Competition: <https://www.kaggle.com/competitions/cuhk-x-competition-large-model-track>

## Current state

- Final settlement (checked 2026-09-17): the competition closed at 2026-09-15 23:59 UTC. Team `Jiayi Du` finished private rank `55/213` with `0.72647` and public rank `50/213` with `0.78070`; this missed the private Top 15 (`0.90882` cutoff). By the published Top-30% recognition rule, `55/213 = 25.82%` is provisionally the `Distinction` tier, pending organizer confirmation. The two frozen finalists were `56122653` (private `0.72058`) and `56108595` (private `0.72647`), so the independent nonvisual union was the better private hedge. No post-deadline mutation or late submission was made; see `official_receipts/2026-09-17T0328Z_final_private_leaderboard_settlement.md`.
- Kaggle rules accepted and competition joined on 2026-09-08 UTC.
- Kaggle team name: `Jiayi Du`.
- Official challenge-site registration was confirmed on 2026-09-11 at 04:22 UTC for the solo team `Jiayi Du`, covering both the Large and Small Model tracks. The registered affiliation is `Stiftung Louisenlund`, country/region is `Germany`, and faculty advisor is blank.
- Kaggle metadata package downloaded and hashed under `data/raw/kaggle/` (ignored from version control because competition data may not be redistributed).
- Official nonvisual supplement downloaded, integrity-tested, extracted, and converted to hashed feature caches. The organizer ZIP hash is `72f34e9f0005d2ee0fefe9a7687bd54fa6dbdf171b6112132523085fa7475afb`.
- All seven notebooks in the official Kaggle competition listing are preserved under `public_baselines/` with downloaded metadata and source hashes. The last unaudited notebook (Chaitanya Jamble) reports only `0.2388` row-wise OOF and violates the subject-disjoint selection standard, so it contributes no candidate.
- First valid Kaggle submission `56107594` scored `0.77777`. A one-row, high-confidence HARn sensor candidate `56108202` tied `0.77777`; the tie is treated as non-diagnostic because the changed row may be outside the public split.
- The RF/XGBoost HAU-emotion consensus submission `56108577` improved the public score to `0.78070`. The four-row disjoint sensor union `56108595` retained `0.78070`.
- Submission `56116980` adds the pre-qualified visual/sensor agreement mechanism, changes seven rows versus the frozen parent, and also scores `0.78070`. It is the current private-robustness candidate; the public tie is treated as non-diagnostic.
- Submission `56117539` tested a subject-disjoint HAU multi-answer sensor overlay and fell to `0.72807`; the branch is rejected. Its compact-graph OOF parent was structurally mismatched to the actual submitted anchor (93.45% versus 40.97% one-letter predictions), so no leaderboard threshold tuning will be attempted and `56116980` remains the current candidate.
- Submission `56120755` tested two additional HARn single-action rows supported by subject-disjoint RF/ExtraTrees sensor agreement, with available VLM disagreement used only as a veto. Despite strong training evidence (`164/184 = 0.89130` accepted-gate accuracy; all 18 subjects positive), it scored `0.77777`, below `56116980`. The whole sensor-only expansion is rejected without row-level leaderboard inference or follow-up probes.
- Submission `56122175` adds one HAU single-action change derived from a label-free within-clip combination-to-single constraint and confirmed by an independent sensor model. The logical rule is `633/633` with ground-truth source answers; deployed subject-disjoint OOF structure is `601/620`; the parent-disagreement sensor-consensus gate is `8/8` versus parent `0/8`, split `4/4` in both fixed odd/even subject cohorts. It tied the best public score at `0.78070`; the tie is non-diagnostic and the method is kept for private robustness.
- Submission `56122653` adds four HAU-emotion rows supported by a new fold-local-imputed pairwise ExtraTrees expert agreeing with the independent RF expert. ExtraTrees reaches `0.49815` across 18 subject-held-out folds; the ET/RF parent-disagreement gate is `117/186 = 0.62903` versus parent `26/186`, net `+91`, with every subject positive and fixed odd/even cohorts net `+38/+53`. It also tied `0.78070`; no row-level inference is made from the tie. All five 2026-09-09 submission slots are now used.
- Kaggle final-candidate selection is explicitly set to `2/2`: `56122653` (linked-question, visual/sensor, and ET/RF emotion union) and `56108595` (independent nonvisual union). A fresh page reload confirmed the persisted selection; it may be updated only if a later candidate clears the same evidence gates.
- The current reproducibility freeze is the versioned v9 manifest under `reports/final_reproducibility_manifest_2026-09-11_v9.json`. It preserves the two selected Kaggle finalists and owned candidate hash, freezes the strengthened raw-input verifier, 8/8 fail-closed package tests, and two byte-identical full replays. The technical package passes; finalist release remains blocked only on the two explicit license decisions in `reports/stage2_native_owned_release_manifest_v1.json`. P2 is not frozen and no Kaggle submission followed.
- The official HARn visual ZIP is complete at exactly `1,956,322,919` bytes, passed a full ZIP CRC test, and has SHA-256 `a972d644c1b536f836fe7e4d97ca560e04dc75e5657927b2290a63bc6add7a25`. Strict extraction recovered 1,524 videos for all 524/524 official HARn training units into an independently hashed manifest.
- A CRC-checked subset recovered from the HARn prefix contains 475 videos for 165 labeled clips, spanning all 18 subjects and 13 actions. It is sufficient for honest local visual validation while the complete archives remain unavailable.
- The pinned, ungated Apache-2.0 `mlx-community/Qwen3-VL-4B-Instruct-4bit` checkpoint is complete and hashed. Zero-shot validation on all 122 recoverable HARn single-action questions scores `0.71311`; all outputs are valid. The sensor and VLM agree on 67 rows at `0.92537` conditional accuracy, making agreement a qualified test-time gate once the official test visual archive is complete.
- A synchronized Depth Color + IR + Depth prompt substantially improved the same 4B model on all 112 three-view-complete validation rows (`0.82143` versus matched single-view `0.70536`; 112/112 valid). It was nevertheless rejected at the deployment stability gate: two of 27 official test attempts returned empty output. The same preprocessing root was stopped without retries, all empty outputs were excluded, and no multiview candidate was built.
- A separate deterministic single-video 2x2 mosaic (Depth Color, IR, Depth, blank) also cleared its 1-question smoke and frozen 18-row screen, then scored `0.78571` on all 112 validation rows versus matched single-view `0.70536` (112/112 valid). It did not improve the existing sensor gate: RF/ExtraTrees/mosaic parent-disagreement consensus was `29/33 = 0.87879` with worst-subject net `-1`. On official test, the first two eligible rows (`test_0473`, `test_0474`) both returned empty output. The independent mosaic root was stopped after its second failure, the invalid outputs were excluded, and no candidate was built.
- The official test ZIP is complete at exactly `1,994,984,736` bytes, SHA-256 `a4ba8644208e08b0bf436c85e1bfcdf5342849675f0924285b481f6a2477f7a1`, and passed a full ZIP CRC test. Strict extraction recovered 754 videos covering all 208/208 official test units; the hashed manifest is `cache/test_visual_manifest.json`.
- The existing single-video test protocol produced valid outputs for all 51/51 HARn action questions with zero errors. Five rows satisfy the historical sensor/VLM-parent-disagreement rule; three were already deployed and two are newly visible. No new candidate was built: the subsequent subject-cluster audit freezes VLM promotion, and no leaderboard slot remains on 2026-09-09.
- A pre-inference-frozen 20-row replay (10 subjects, 10 action + 10 object questions) had 20/20 readable and valid outputs with zero implementation failures, but all 20 QA/clip pairs had already appeared in `full122/object66`; prompt, video, raw output, and prediction match 20/20. It is retained only as a deterministic pipeline replay and is rejected as new performance evidence.
- Completing HARn yielded 374 genuinely unseen labeled QA/clip pairs. A fresh 20-row screen was frozen before first inference with zero QA or clip overlap: 10 subjects, one action and one object question per subject, with a subject-level exact-sign primary gate and hard rejection on any negative subject. The pipeline passed 20/20 reads and parses with zero implementation failures, but scientific evidence failed every promotion gate: VLM `12/20` versus subject-disjoint parent `13/20`, action net `+3`, object net `-4`, fixed halves net `+1/-2`, subject deltas `2` positive/`3` negative/`5` tied, exact `p=0.8125`. Decision: `REJECT_AND_REFREEZE_VLM`; no router mining, candidate, or submission is allowed from these rows.
- A separately preregistered HAU-emotion sensor--option semantics branch excluded the unknown-lineage 0.77777 vector and compared against the owned RF OOF. Three independently fit IMU/radar/skeleton option-rankers produced 270 disagreements: candidate `101/270 = 0.37407` versus parent `87/270 = 0.32222`, with fixed subject halves net `+15/-1` and trial-prefix environment proxies net `-1/+7/+8`. Although all 19,416 option-permutation checks, 809 synonym rewrites, and invalid-output checks passed, the `>=0.60` disagreement-accuracy and both-halves-positive gates failed. Decision: `REJECT_NO_TEST_NO_SUBMISSION`; no test QA was read and no candidate was built.
- The full Stage2-native owned core is independent of the public fixed 682-row answer vector. Across all 4,087 training QA rows in 18 subject-held-out folds, it improves from an owned semantic base `0.56325` to `0.62197` (`+240`, or `+5.87pp`); fixed subject halves are `+127/+113`, every subject is non-negative, all 98,088 option-permutation checks match, and invalids are zero. The optional all-missing-skeleton Qwen fallback was rejected at `18/40 = 0.45` with one invalid and is not deployed.
- Two independent network-blocked builds of `candidates/stage2_native_owned_v1.csv` are byte-identical at SHA-256 `40361ab2b6a87d5b73da3114aada27b982b37c09d205864ec8ed272701ae06b8`. All 682 IDs and answer grammars pass; 559 rows use the owned semantic base, 41 use HARn skeleton RF, and 82 use HAU emotion ET–RF consensus. A six-row/two-clip smoke replaced every QA ID and clip key and reproduced identical predictions from the same features under new unit keys. This candidate has not been submitted and does not replace the currently selected finalists.
- The TimeLogic-inspired timestamp evidence-seeking increment remains preregistered but unrun: its 50-row HAU screen requires ten non-user8 subjects, while the local HAU visual payload currently contains only the partial user8 prefix. The paper is treated as a CVPR 2026 challenge-solution report with `77.13` reported AvgAcc, not as verified winner evidence or an exact-reproduction claim.
- P1's sole fresh verb–object–temporal decomposition screen used 48 previously unexposed QA/clip pairs with equal model/video/frame/token budgets and action/object × subject-half stratification. Although the routed arm was `33/48` versus generic `12/48`, the generic comparator produced 28 invalid parses and the decomposed arm produced one invalid answer/schema. The frozen invalid=0 gate rejected P1 as comparator-confounded. An independent control audit also found that the screen predates the new pre-freeze atomic-reservation and separate minimum-frame-receipt controls; this cannot be repaired after exposure. P1 is terminally rejected with no retry, test inference, candidate mutation, or leaderboard probe.
- The canonical shared VLM exposure registry is `artifacts/manifests/vlm_exposure_registry.jsonl`; a row-level conservative audit registry is also kept at `reports/vlm_exposure_registry.jsonl`. Future fresh screens must call `scripts/reserve_vlm_fresh_cohort.py` for a label-blind readability/minimum-frame preflight and atomic locked reservation; any conflict or parse failure rejects the cohort before freeze.
- The handoff includes `TECHNICAL_REPORT.md`, exact Python package pins in `requirements-repro.txt`, the unchanged network-free `inference.sh` for the two selected legacy candidates, and a separate `inference_owned.sh` that rebuilds the owned Stage2 candidate from organizer raw IMU/radar/skeleton inputs. The owned raw-input path passes its technical replay gate. The earlier package deadline is enforced conservatively and the Small no-LLM inference scope is separated from development tooling; the candidate remains unsubmitted and not finalist-ready until participant-source Apache-2.0 approval and organizer-only derived-model delivery terms are confirmed.
- The HAU ZIP is resumable at `100663296 / 3674779437` bytes. Its current prefix covers only `user8`; bounded visual probes failed the evidence gate, so no HAU test predictions were produced.
- Expanded user8 visual probes also rejected HAU multi (`0.22727`) and combination (`0.59091`); sequence was stopped after eight repeated invalid outputs. No invalid or empty output is included in any candidate.
- An official organizer-hosted dataset browser was audited but its Large Model Track directories currently list no files. The official Baidu mirror is blocked by the browser site-safety policy, Hugging Face requires contact-data sharing, and Google Drive remains the only authorized resumable route currently available.
- The pinned public Apache-2.0 8B Qwen3-VL checkpoint is complete and fully hashed (`5,776,633,051` bytes; manifest SHA-256 `92e4b276b3f04fcdca7b89e91d612b7b63da1ceb128dea58635c4b5c01fd0c44`). Its frozen 18-row screen scored `0.55556`, below the matched 4B result `0.61111`, so the 8B route is rejected before full or test inference.
- A deterministic linked-question audit found a sequence-option overlap rule that is 100% correct on 126 eligible training combination rows, but the frozen anchor already matches all 16 unique test inferences. The analogous multi rule scores only `0.65556` and is rejected.
- The existing `DDL｜CUHK Large 2小时推进` heartbeat is active; no duplicate automation was created.

## Compliance guardrails

- Competition data are for non-commercial research/competition use only and must not be redistributed.
- Never use hidden/test answers, manually label test questions, infer row labels from leaderboard probes, use multiple accounts, or collude across teams.
- Large pretrained models and reasonably accessible external APIs are allowed in this track.
- Any finalist solution must be reproducible; record model/data versions, licenses, seeds, runtime, offline validation, and submission IDs from the first run.
- Validation must keep clips intact and use subject-disjoint folds where subject IDs are available. Row-wise random splits are prohibited for model selection.
- A candidate may be submitted only after schema/ID, leakage, stability, and rules gates pass.
- An overlay comparison is valid only when the OOF parent reproduces the submitted parent's output structure (including answer cardinality for set-valued categories); relative gains against a mismatched proxy cannot qualify a submission.

## Reproduce and validate the first public anchor

```bash
python scripts/reproduce_public_077777.py
python scripts/validate_submission.py candidates/public_fususu_077777.csv
```

The first anchor is the exact 682-row prediction artifact publicly released by team Fususu in an Apache-2.0 Kaggle notebook. The notebook records Kaggle submission ref `55125358` and public score `0.77777`. It does not release the full training/checkpoint lineage, so it is a leaderboard-verified anchor, not a reproducible finalist solution.

## Local sensor validation

```bash
python scripts/extract_nonvisual_features.py
python scripts/run_sensor_oof.py
python scripts/build_sensor_error_report.py
```

The current honest 18-fold leave-one-subject-out results are `0.76690` for the HARn single-action sensor expert and `0.44870` for the HAU emotion expert. HAU single-action sensor overrides failed the parent comparison and are rejected. Full metrics, per-subject results, confidence bands, error types, hashes, versions, and checkpoint hashes are under `reports/` and `experiment_log.csv`.

The pairwise option-ranking XGBoost emotion expert reaches `0.46477` overall
and `0.38889` on the worst subject. Requiring agreement with the independent
RF expert produced three test overrides and the first public-score gain.

The later tri-modal option-semantics experiment is a strict negative result, not
a new candidate. Reproduce its training-only validation with
`python scripts/run_sensor_option_semantics_v1.py`; the frozen protocol, result,
replay verification, and rejection receipt are under `reports/` and
`official_receipts/`.

## Official registration

Form: <https://openaiotlab.github.io/CUHK-X-Challenge/#registration>

Completed at `2026-09-11T04:22:09Z`. The website returned: “Registration confirmed — your team has been saved to our records.” The Kaggle team and official registration both use the exact team name `Jiayi Du`. Contact email is kept masked in the repository; see `official_receipts/2026-09-11T0422Z_official_team_registration.md`.
