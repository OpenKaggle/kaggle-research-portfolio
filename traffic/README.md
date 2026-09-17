# IEEE Big Data Traffic Flow Bench attack workspace

This directory isolates the new campaign from the older ROGII work.

Competition deadline: **2026-11-07 06:55 UTC / 14:55 Asia/Shanghai**. The 2026-09-09 10:57:40 UTC external checkpoint reports 34 teams and public top-three scores of 0.92332, 0.92116, and 0.89922; the account remains rank 17 at 0.74733 with exactly three completed submissions, and both official remote HEAD and main still match the pinned local commit. The timestamped campaign snapshot and gates are frozen in `artifacts/campaign_status.json`.

## Current state

- Official code is pinned locally under `official/`.
- The public Notebook's best V32 source and its EDA companion are archived under `public_notebooks/`. Its complete public run artifact is also present: 6,985,307 rows, IDs 1 through 6,985,307, with 6,740,599 state rows, 174,000 queue rows, and 70,708 ODME rows. Kaggle reports 0.71846 for the Notebook's best V32 run.
- The Kaggle account has accepted the competition rules and API authentication is working. The official 8.90 GiB archive is downloaded and unpacked under `data/kaggle_public`; its archive SHA-256 is `aa122173...b30d8d`.
- The full public release audit is valid with zero errors: exactly 9,698 files and 10 panels; all daily partitions are complete; all four Parquet families have one schema variant; State/Queue/ODME templates contain 6,740,599 / 174,000 / 70,708 rows with no duplicate or missing natural keys; their total closes exactly to the 6,985,307-row official key. The receipt is `artifacts/public_release_audit.json`.
- The exact V32 artifact is the account's first completed anchor: Kaggle submission `56106600`, public score `0.71846`, an exact reproduction of the source run. Its local streaming audit is saved in `artifacts/v32_public_anchor_validation.json`.
- The first isolated Queue correction is complete: submission `56107311`, public score `0.74210` (`+0.02364`). It changes exactly 160 `queue_pred` cells from 1 to 0 and leaves every State/ODME row and every other Queue row byte-identical. This passes the preregistered `+0.015` continue gate; the more complex Queue trend/shockwave variants remain frozen because they lost on the sealed train-only proxy.
- The first ODME regularization ablation is complete: submission `56108199`, public score `0.74733` (`+0.00523` over the Queue parent and `+0.02887` over V32), rank 17 of 34 at the latest snapshot. It changes only the 70,708 ODME `path_flow` cells by reducing `lambda` from 20 to 5; all 20 panel-split released-count fits improve, while State and Queue remain byte-identical to `56107311`.
- The frozen best now has a direct V32-to-current cell-level lineage receipt. All 6,985,307 rows compare cleanly: exactly 160 Queue cells change from 1 to 0, all 70,708 ODME `path_flow` cells change, and none of the 6,740,599 State rows changes. A fresh official-key/schema/domain validation reproduces SHA-256 `c3aea84e...8ef8fa`. The receipt is `artifacts/current_best_lineage_audit_v1/current_best_lineage_receipt.json`.
- The complete frozen transformation has also been replayed from the pinned V32 anchor and released inputs. The replay regenerated the Queue correction, recomputed all 20 lambda-5 ODME panel-splits with the original solver settings, merged and validated all 6,985,307 rows, and produced a byte-identical SHA-256 `c3aea84e...8ef8fa` in 153.91 seconds at 434.16 MB peak memory. The pinned recipe is `config/current_best_freeze_v1.json`; the receipt is `artifacts/current_best_full_replay_v1/current_best_full_replay_receipt.json`.
- The immediate continuation below `lambda=5` is stopped: `lambda=1` failed the 300-iteration numerical gate, while a stable `lambda=2.5` one-panel smoke test improved the worst split `S_link` by only `+0.001274`, below the preregistered `+0.005` expansion gate. No additional ODME candidate was submitted.
- A 7,089,289-target grouped temporal diagnostic is reproducible but invalidated as the campaign control: its rolling exact-seven-day fallback lets later holdout days use earlier unmasked labels from the same month, while Kaggle reveals no validation/private labels. Its `0.908699` / `0.911208` State and `0.986222` / `0.986445` public-FD figures therefore cannot gate a deployable candidate. The next control must freeze its historical profile strictly before each holdout block.
- The authoritative deployable State control now mirrors the current V32 submission while freezing its historical profile before each holdout month: January uses 214 earlier train days and February uses 245. It scores `0.908792` development and `0.911292` confirmation under the official State hierarchy, and `0.986250` / `0.986470` on the public FD branch, over the same 7,089,289 targets with all 60 panel-regime groups populated and zero missing. A 5,884-cell validation-day replay matches every archived key and all speeds; one flow differs by only `0.104587 vph` due to the archived Kaggle runtime. Receipts are under `artifacts/task1_grouped_v32_frozen_profile_control_v1/`.
- The proposed two-mode directional filter is also stopped before implementation. An input-only scan of all released validation/private masks passed the preregistered observability gate on only 10 of 20 panel-splits; maximum adjacent released-link spacing is `7.771 km`, and the weakest split has only `73.9499%` two-direction coverage within 3 km. No target truth or submission was used. The receipt is `artifacts/task1_directional_observability_preflight_v1/task1_directional_observability_receipt.json`.
- Robust historical-profile work is stopped as irrelevant before fitting: the exact V32 source-order audit shows that `0` of all `6,740,599` validation/private State targets reach the profile. Same-day temporal interpolation completes `99.995253%`; lexical spatial fallback supplies only the remaining 320 cells. Changing profile estimators therefore cannot move the submission under the released masks.
- A fresh one-variable mode-preserving interpolation family is also stopped. On `D7_I10_E`, development selected the exact V32 linear control; moving toward nearest-observation fill reduced State monotonically, and pure nearest lost `-0.021596` development / `-0.017527` confirmation while FD moved by less than `0.00017`. No all-panel candidate or submission was made.
- Queue ongoing-trend crossings are stopped as an isolated family. Steps 2–4 tied the disabled persistence control on development; although step 3 improved confirmation proxy from `0.505043` to `0.528761`, only two of eight panels benefited. Selecting it from confirmation would violate the sealed selection rule, so the proven off-by-one Queue candidate remains frozen and no submission slot was used.
- The A-team mask-matched nonlinear State residual family produced genuine but insufficient signal on `D7_I10_E`: January selected full correction; February improved every day, gaining `+0.004528` State, `+0.005370` transition-State, and `+0.001432` public FD. The preregistered expansion floor was `+0.01` State, and the observed State-only total implication is only `+0.001585`, so the family is frozen without all-panel expansion or submission. All training labels came from the published train tree; no scored-split labels were used.
- A read-only component opportunity audit now prevents low-value leaderboard probing. No independent remaining family has an honest local total-score lower bound above the fixed `0.0035` submission-cost floor. State has `0.031048` observable theoretical headroom but its best recent one-panel signal is only `0.001585`; public FD has at most `0.000677` left, and even perfecting lambda-5 `S_link` can add at most `0.000254`. Public ODME operators leave `94.44%–98.02%` of path space in the nullspace, so hidden-component upside is not treated as evidence. The decision is to hold submission `56108199` without a new experiment or submission.
- The deadline-aware campaign audit is now `READY`: 24 checks pass with no warnings or failures. Its live-clock v8 receipt was activated and registered automatically. It re-hashes the 9.56 GB archive, verifies the pinned official-code HEAD, runtime environment, and closed implementation manifest, hashes both the current-best and fallback submission files against their Kaggle ledger receipts, closes the four-task baseline contract and three-stage submission-attribution chain, enforces the D-30/D-14/D-7/D-3 activity policy, and validates the pre-D-3 selection control. Seven runtime/memory fields not captured by early legacy runs are covered by a separate deterministic replay receipt; original ledger cells remain untouched so current-machine measurements are never presented as historical measurements. D-30 is 2026-10-08 14:55 China time, D-14 is 2026-10-24, D-7 is 2026-10-31, and D-3 is 2026-11-04; current evidence already satisfies the first three technical gates, while final selection remains deliberately not complete before its time boundary.
- The D-3 selector has passed a full dry-run against the real campaign state, including dynamic consumption of the latest activated readiness SHA. It selects existing submission `56108199` at `0.74733`, retains `56107311` as fallback, verifies both local artifact SHAs plus the frozen lineage/replay/readiness receipt SHAs, and finds no late-experiment violations. Non-dry selection requires `--as-of` to match the live system clock within a 15-minute age and 60-second future-skew window and must consume a D-3 `READY_FOR_FINAL_SELECTION` receipt no more than 15 minutes old. A D-3 simulation proves the handshake has exactly one pending check before selection. The preview remains explicitly `PREVIEW_READY_NOT_FINAL`; it neither performs a Kaggle action nor marks the campaign complete.
- Lifecycle evidence registration is now automated and retry-safe. `audit-campaign --activate` atomically pins a live audit in campaign status and appends its experiment-ledger row; a successful non-dry `select-final` registers its own final receipt. Existing receipt paths are immutable, repeated registration is idempotent, and simulated/stale audit times cannot be activated. An isolated 14-test receipt proves the mechanism without changing the live status or either ledger.
- Method-family stopping policy is now machine-verified rather than inferred from a count. Three task-stream sequences prove two consecutive non-improvements followed by a switch or freeze: initial State topology/smoothing, post-anchor Queue breadth/trend, and ODME lambda-1/lambda-2.5. Three earlier State/Physics failures then trigger the recorded A-group nonlinear-residual proposal; it was evaluated with public-train labels only and frozen below its preregistered expansion gate. Every event is locked to its original receipt SHA.
- The complete submission workflow is now closed by one attribution audit. For V32 anchor `56106600`, Queue-only `56107311`, and ODME-only `56108199`, it verifies the hypothesis/evaluator ledger text, original and replay-backed resource evidence, local receipts, 6,985,307-row official-key validation, artifact SHA, Kaggle receipt, and exact task-isolated diff. Decimal accounting closes `+0.02364 + 0.00523 = +0.02887`; all private and organizer-only metrics remain blank or null.
- A separate SHA-bound four-task baseline contract now computes the cross-corridor evidence instead of trusting ledger prose. State covers 60 panel-regime holdouts and 7,089,289 target cells; Queue verifies exactly 10 `1→0` changes in each of 16 eligible panel-splits; ODME pairs lambda 5 against lambda 20 across all 20 panel-splits and every `S_link` delta is positive. Physics records only the public FD branch, while official Queue truth, LWR boundary flux, full Physics, and hidden ODME metrics remain null.
- The reproducible runtime is pinned independently of the untouched official repository: CPython 3.13.2 plus the exact ten-package dependency closure in `requirements.lock`, on Darwin arm64 with Accelerate BLAS/LAPACK. Runtime v3 verifies all eleven unified commands, Pandas/PyArrow roundtrip, SciPy nonnegative least squares, the State nonlinear-model dependency, resource sampling, and the complete 64-test suite without reading competition data or submission artifacts.
- The implementation itself is now one closed, machine-verifiable set rather than an implicit directory snapshot. `system_implementation_manifest_v1` hashes the unified entry point, dependency lock, all 9 configs, 35 source files, 25 test files, this README, and 15 canonical receipts: 87 files in total. Every campaign readiness run recomputes the declared path set and all hashes, so a modified, added, removed, symlinked, stale, or boundary-crossing file fails the gate. The manifest never reads competition data, submitted CSV content, hidden labels, or hidden metrics.
- Lifecycle milestones are now executable policy rather than labels. Three SHA-bound receipts prove the four-task baseline predates D-30, candidate freeze predates D-14, and byte-identical replay predates D-7. Every current and future ledger row is classified: candidate tuning and new submissions are rejected from D-14, D-7 admits only reproduction and integrity work, and D-3 admits only documented bugfixes, final selection, reproduction, readiness, and read-only integrity checks. Eight synthetic enforcement probes cover both allowed and rejected actions.
- The local environment already has compatible `pandas`, `numpy`, `scipy`, and `pyarrow` versions.

Run the data readiness check after the package finishes downloading and unpacking:

```bash
.venv/bin/python traffic/run.py doctor --release-root /path/to/kaggle_public
```

Build all validation and private rows with the first queue improvement:

```bash
.venv/bin/python traffic/run.py build \
  --release-root /path/to/kaggle_public \
  --queue-method shockwave \
  --output-root traffic/artifacts/shockwave_v1
```

The merged upload will be `traffic/artifacts/shockwave_v1/submission.csv`. Do not submit it without first checking task row counts against the current `submission_key.csv`.

Run dependency-free smoke tests with:

```bash
.venv/bin/python -m unittest discover -s traffic/tests -v
```

Rebuild the frozen best into a temporary work directory and retain only the small evidence reports with:

```bash
.venv/bin/python traffic/run.py reproduce-current-best \
  --release-root traffic/data/kaggle_public \
  --output-root /tmp/traffic_current_best_replay \
  --evidence-root traffic/artifacts/current_best_full_replay_v1
```

The command aborts unless the official commit, submission key, V32 anchor, Queue source, both ODME split files, merged task lineage, and final 6,985,307-row SHA all match the frozen configuration.

Recheck the runtime, closed implementation manifest, four-task baseline contract, ordered method-family policy, and complete three-submission attribution chain through the unified entry point:

```bash
.venv/bin/python traffic/run.py audit-runtime \
  --output-root /tmp/traffic_runtime_recheck

.venv/bin/python traffic/run.py audit-system-manifest \
  --output-root /tmp/traffic_system_manifest_recheck

.venv/bin/python traffic/run.py audit-four-tasks \
  --output-root /tmp/traffic_four_task_recheck

.venv/bin/python traffic/run.py audit-method-policy \
  --output-root /tmp/traffic_method_policy_recheck

.venv/bin/python traffic/run.py audit-submission-attribution \
  --output-root /tmp/traffic_submission_attribution_recheck

.venv/bin/python traffic/run.py audit-lifecycle-policy \
  --as-of 2026-09-09T20:14:34+08:00 \
  --output-root /tmp/traffic_lifecycle_policy_recheck
```

All six output directories are immutable receipts and therefore must be new on every run. The system-manifest audit reads only implementation, documentation, and receipt files. The attribution audit streams the three full submission files and confirms the exact single-task diffs, official-key validation, Kaggle receipts, and Decimal score closure without reading private scores or hidden labels.

Audit the complete campaign evidence and deadline phase with an explicit timestamp:

```bash
.venv/bin/python traffic/run.py audit-campaign \
  --release-root traffic/data/kaggle_public \
  --as-of 2026-09-09T16:22:07+08:00 \
  --output-root /tmp/traffic_readiness_preview_2026-09-09T162207 \
  --verify-archive
```

The audit checks the D-30 four-task baselines, D-14 freeze evidence, D-7 byte-identical replay, ledgers, receipts, public archive, and no-hidden-label boundary. Historical resource fields that were never captured remain blank in the original ledger; a deterministic replay receipt covers them without presenting current-machine measurements as historical facts.

At a live milestone, register the audit atomically by using a new output directory and `--activate`. For example, at D-30:

```bash
.venv/bin/python traffic/run.py audit-campaign \
  --release-root traffic/data/kaggle_public \
  --as-of 2026-10-08T14:55:00+08:00 \
  --output-root traffic/artifacts/campaign_readiness_D30_2026-10-08 \
  --verify-archive \
  --activate
```

Activation timestamps must match the live clock within 15 minutes and may not be more than 60 seconds ahead. Never reuse an output directory for a new receipt; retrying an activated receipt only verifies or recovers the same registration.

Preview the D-3 final selection gate without making it final:

```bash
.venv/bin/python traffic/run.py select-final \
  --as-of 2026-09-09T18:16:18+08:00 \
  --output-root /tmp/traffic_final_selection_preview_2026-09-09T181618 \
  --dry-run
```

Before D-3 the command refuses non-dry runs. For non-dry selection the supplied timestamp must match the live clock, preventing future-date simulation from becoming a final receipt. At D-3 first run `audit-campaign --activate`; when its only pending check is final selection it returns and registers `READY_FOR_FINAL_SELECTION`. Run `select-final` without `--dry-run` within 15 minutes; it registers the final receipt automatically. Then rerun `audit-campaign --activate` in a new output directory for the postselection `READY` result. Any late experiment outside explicit bugfix, reproduction, readiness, or final-selection work is rejected. Selection is internal and does not perform a Kaggle mutation.

Strictly validate any merged submission (and, once downloaded, align it to the official key) with:

```bash
.venv/bin/python traffic/src/validate_submission.py \
  --submission /path/to/submission.csv \
  --key traffic/data/kaggle_public/submission_key.csv \
  --report traffic/artifacts/<experiment>_validation.json
```

Every experiment and Kaggle receipt is recorded in `artifacts/experiment_ledger.csv` and `artifacts/submission_ledger.csv`.

## Score accounting

```bash
.venv/bin/python traffic/src/scorecard.py --official-baseline
```

Official reference baseline:

| Task | Weight | Baseline | Weighted contribution |
|---|---:|---:|---:|
| State reconstruction | 0.35 | 0.6903 | 0.241605 |
| Queue | 0.30 | 0.2518 | 0.075540 |
| Physics | 0.15 | 0.3467 | 0.052005 |
| ODME | 0.20 | 0.5904 | 0.118080 |
| Total | 1.00 | 0.4872 | 0.487230 |

Task 1 can be scored honestly on public train. Task 2 labels and Task 3 organizer boundary flows are withheld. Task 4 can only be checked honestly for `S_link`, one quarter of its component. Unknown values should remain unknown locally rather than being presented as validation scores.

## First attack

The highest-return first experiment is Queue v1, not a broad four-task rewrite:

1. Preserve persistence for ongoing queues.
2. Extrapolate robust link-speed trends to the queue cutoff.
3. For onset windows, select the most plausible link using current distance to cutoff, deceleration, and train-only recurrent risk.
4. Permit one topology-aware upstream shockwave step only when the upstream sensor is already within 20% of cutoff and slowing.

This directly challenges the public Notebook's hard-coded two bottlenecks per corridor and its nominal `T+30` onset. Its implementation measures the horizon from the final history timestamp (`T-5`), so `>=30 minutes` actually turns on at both `T+25` and `T+30`; exactly 80 windows in the downloaded V32 output have the resulting four positive cells. Queue v1 ranks the six requested timestamps directly, removing that off-by-one. It is data-driven per window and has lower private-month overfit risk. The public Notebook's claims of offline Queue IoU and full ODME cannot be reproduced from the released truth: those labels/components are explicitly withheld, so its 0.71846 leaderboard score is the only reliable total.

Physics should be attacked through Task 1. The next implementation after data access is a bounded conservation projection applied only to masked flow cells, using observed neighboring link states and valid ramp readings. It must be gated on Task 1 RMSE, because a smoother that improves apparent continuity while erasing congestion will lose both state accuracy and organizer-side LWR score.

Two one-corridor State/Physics probes are already closed. Topology-residual interpolation regressed confirmation `S_state` by `-0.030723`, and V32-style density smoothing regressed it by `-0.0000155`; neither may be scaled. The next State experiment must therefore retain temporal reconstruction as its control and earn its place on grouped corridors rather than reopen either stopped family.

A subsequent read-only audit found no stable global bias to calibrate. Its 82,127 sealed target cells show that rare congestion-state switches dominate the remaining speed error (confirmation RMSE `6.99 km/h` in congested cells versus `1.64` in free flow). That is a hypothesis generator only—the audit covers one panel—so no new State candidate will be packaged until the full release permits grouped-corridor confirmation.

The first grouped follow-up used `v_cut = 0.60 * released free_speed_kmh` and a `>50%` link-period availability guard, without fitting cutoffs from truth. A 10-panel, two-block smoke audit retained 100% of eligible target cells but violated the preregistered no-reversal rule: cutoff-relative loss concentration was worse on several panel-splits, with a minimum lift delta of `-1.781729`. The cutoff-gated event family is stopped before candidate generation.

The proposed two-state filter failed its prerequisite input-only observability gate and is frozen without prediction. Separately, the first full grouped temporal diagnostic exposed a deployment mismatch in its rolling seven-day fallback and is not a valid control. The replacement control must mirror Kaggle conditions: build its weekday/time profile only from dates before the holdout boundary, freeze that profile for the entire block, then use only values visible in each masked target day. Target truth may score the finished predictions only.

## Continue/stop gate

- Reproduce official historical mean and 0.4872 leaderboard baseline first.
- Reproduce the public 0.71846 Notebook without editing it.
- Queue off-by-one v1 passed its continue gate: `0.74210 - 0.71846 = +0.02364`, from exactly 160 changed cells. Further Queue work must remain single-variable; the losing complex trend/shockwave variants stay frozen.
- A follow-up top-1 versus top-2 onset-breadth probe failed locally (`-0.08333` on development and tied on confirmation, one panel only). Queue is frozen at the proven off-by-one candidate until genuinely independent evidence appears; no third submission slot was used.
- A Task 1/physics projection continues only if grouped train `S_state` does not fall more than 0.005 and the public total gains at least +0.010.
- Target for the 72-hour gate remains total >=0.78. Otherwise park the competition as a low-frequency side line.
