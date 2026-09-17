# CUHK-X control plane

Updated: 2026-09-11 CST

This ledger defines “full coverage” operationally. It means every official competition surface, every listed Kaggle public notebook/discussion, every local experiment/exposure, and every finalist requirement has an owner and a refresh rule. It does not mean indiscriminately scraping the whole web.

## Coverage matrix

| Surface | Coverage | Owner | Refresh / stop rule | Escalation trigger |
|---|---|---|---|---|
| Official registration and team identity | Complete for both tracks | Root | Recheck only on organizer email or mismatch | Team-name/certificate/contact mismatch |
| Official challenge site, rules, timeline, finals format | Full first-party inventory; format commit `2d6ecb4` pinned | Research radar | Diff every 6 hours | Rule, deadline, package, or eligibility change |
| Kaggle Small/Large leaderboard | Full rank snapshots, no row inference | Research radar | Every 6 hours and final-day checkpoints | Top-15 threshold movement or selection change |
| Kaggle discussions and host replies | All current threads inventoried | Research radar | Incremental scan; host replies prioritized | New clarification affecting model/data/submission |
| Kaggle public notebooks and outputs | All listed notebooks inventoried | Research radar + track owner | Incremental scan with source/license/provenance checks | New reproducible method, payload, or weight |
| Official GitHub/release/issues | Current main and v1.0.0 pinned | Research radar | Commit/release diff every 6 hours | New inference path, checkpoint, license, or data link |
| Primary research and adjacent winning solutions | Saturated method-family search | Research radar | Targeted only; stop after two no-novelty batches | Evidence that changes P1/P2/P3 priority |
| Large VLM exposure and fresh-evidence governance | 30/30 logs scanned; append-only registry active | Large audit owner | Scan before every cohort freeze and after every run | Any QA/clip collision or parse failure |
| Large P1 scientific route | Rejected; independent science/control audit complete, no retry | Large experiment owner | Terminal unless the user authorizes a genuinely new mechanism | Existing invalid output, missing pre-freeze atomic reservation, or exposed-cohort reuse |
| Small P2 scientific route | Preregistered, payload blocked | Small experiment owner | Retry legal public transports; two-fold fast-kill on payload arrival | Payload arrival, quota recovery, or gate failure |
| Small P3 missing-modality route | Conditional, not started | Small experiment owner | May start only after P2 passes independently | P2 full gate passes |
| Kaggle submissions and final selection | Large 2/2 selected; Small smoke only | Root | One mechanism per submission; hashes before submit | Offline gate passes and slot is available |
| Stage 2 package | Official deadline `2026-09-18 23:59 UTC+8`; committee-controlled run plus 30% private-data evaluation. Large v9 freeze: 235/235 deep hash PASS, owned raw-input technical package PASS, release-license review blocked; Small pending candidate | Track owners | Run quick harness after material changes, deep harness after freeze changes, release+deep before any finalist-ready claim | License/rule conflict, missing asset, network dependency, hash/size mismatch |

## Third-round saturation and governance watch

- The third CUHK-X incremental radar closed on 2026-09-11 after checking 39 primary or official sources. It found no route-level addition; broad discovery remains stopped.
- Escalate only a rule, deadline, leaderboard-threshold, host clarification, reproducible-code, or licensing change that would alter P1/P2/P3, finalist readiness, or Top-15 risk.
- Technical and governance decisions use separate fields: `technical_status` and `governance_status`. A technical `PASS` must never convert governance `UNKNOWN` or `BLOCKED` to `PASS`.

The governance controls and open release risk are:

1. Post-competition package deadline conflict: authoritatively resolved by official challenge commit `2d6ecb4` on 2026-09-11. The binding verification-package deadline is `2026-09-18 23:59 UTC+8` (`2026-09-18 15:59 UTC`); the prior conservative Sep 17 cutoff is superseded.
2. Small model scope: resolved by separation. Final inference remains non-LLM; host permission for development-time coding assistants does not alter that inference constraint, and the Large owned candidate has no Qwen prediction effect.
3. Release license layers remain open: obtain explicit participant approval to publish the clean-room source subset under Apache-2.0 and confirm organizer-only delivery terms for participant-trained model files derived from non-redistributable organizer data.

## Parallel execution

- Research radar subagent: official/community/research diffs and source inventory.
- Small subagent: transport matrix, minimum payload acquisition, P2 fast-kill, checkpoint compliance.
- Large subagent: independent P1 audit, exposure check, Stage2-native promotion decision.
- Root: conflict arbitration, evidence freshness, submissions, final candidate freeze, and cross-task status.

Separate persistent Codex tasks remain the user-facing workspaces:

- `Kaggle DDL｜CUHK-X Large Model`
- `Kaggle DDL｜CUHK-X Small Model`
- `Kaggle 战役｜调研与情报 A 组`

## Active recurring supervision

- Large experiment monitor: every 2 hours.
- Small experiment and data monitor: every 4 hours.
- Research/rules/leaderboard monitor: every 6 hours.

Unchanged state stays quiet. Notifications are emitted only for a qualified candidate, meaningful score/rule/data change, failure requiring intervention, or user action.

## Non-negotiable controls

1. New Large cohorts must pass the atomic exposure-registry reservation before freezing.
2. Data readability and minimum-frame checks happen label-blind before a cohort is reserved.
3. No experiment may reuse exposed QA/clip pairs as fresh evidence.
4. Small must use subject-disjoint and clip-disjoint validation and one inference checkpoint below 100 MB.
5. Public leaderboard movement never licenses row-level follow-up probes.
6. No contact information is sent to Hugging Face or another third party without explicit user authorization for that destination.
7. Failed or incomplete cohorts produce a rejection receipt, not a partial metric.

## Unified read-only harness

Run the complete current research check with:

```bash
.venv/bin/python scripts/run_cuhk_harness.py --deep
```

The harness automatically selects the newest versioned Large reproducibility manifest, runs all class-based tests, executes pytest-style zero-argument tests without requiring pytest, runs the Small track tests in the dependency-pinned project environment, validates all three current Large candidates, rehashes the full manifest inventory, audits the exposure registry, and distinguishes research validity from finalist-package readiness.

Current package status: Large v9 binds and deep-verifies 235/235 artifacts. The owned raw-input path, eight adversarial tests, and two clean replays pass technically. The official `2026-09-18 23:59 UTC+8` package deadline and Small/Large model-scope separation are enforced. Overall release remains blocked only by explicit participant Apache-2.0 approval and organizer-only delivery terms for the derived model files. The unified harness reports those license decisions as release blockers rather than technical failures.

The Sep 11 incremental radar found no route-changing external evidence. Its unresolved governance items are tracked in the dedicated section above and remain outside every technical `PASS`.

The next targeted scan found a decision-grade official format delta at commit `2d6ecb4`: Top 15 packages are due Sep 18 23:59 UTC+8, the committee runs solutions in a controlled environment, and organizer-controlled private data contributes 30% of final scoring. Small's public Top-15 threshold also moved from `0.83582` to `0.84577`; this changes qualification risk, not the frozen scientific route. Full receipt: `reports/cuhk_x_incremental_radar_round4_official_format_delta_2026-09-11.md`.

For Large, `cuhk_x_large/scripts/reserve_vlm_fresh_cohort.py` is the fail-closed reservation entry point. A post-hoc audit never converts an exposed cohort into fresh evidence. The owned Stage2 CSV now reproduces twice byte-for-byte from raw organizer sensor input, remains unsubmitted, and must not be promoted through unresolved governance.
