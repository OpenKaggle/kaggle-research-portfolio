# Scouting ROI scoring backtest — 2026-10-29

Read-only backtest of the portfolio's scouting ROI scoring formula against the
actual outcomes of twelve campaign lines. Evidence grades follow the archive
convention: **Verified** = backed by a recorded receipt or an official reading;
**Unverified** = experience-based inference, pending validation. All judgment
baselines are anchored to the 2026-09-17 entry round; the CUHK and Kaggriculture
expectations are supplemented from a separate campaign record and the rolling
deadline-scan probability fields.

## 1. Backtest table (12 campaign lines)

| # | Line | Judgment at entry (2026-09-17 basis) | Expectation at entry (ceiling / rank band) | Actual outcome | Hit / miss | One-line attribution |
|---|---|---|---|---|---|---|
| 1 | TreeHSI | Continue only on a manifest event trigger, with a preregistered 0.15 score floor | Phase 2 package only on a "clear private-safe gain"; cash 0% (kudos-only) | Phase 2 submission 56503530 = 0.06404, below the 0.15 floor → sealed 2026-09-23 | **Partial hit** | The floor gate capped the loss at one submission (stop-loss worked), but the zero-prize line still consumed a submission slot, and the region-OOF→LB collapse (0.688→0.064) never downgraded the ceiling estimate |
| 2 | Kaggriculture | Tracked under a separate campaign record; snapshot fields: cash 0.5–2% from a rank-299 start, Points 40–70% | Extrapolated from a live rating of ~2024/2116 (2026-09-10) | q5 = 1236.1 / hybrid = 1065.3 settled scores; rank 3177/10148; books closed 2026-10-15 with no prize and no medal | **Miss** | Rating decays monotonically during the convergence period (2116→1236); extrapolating rank and medal probability from a single live reading was wrong on both counts — a repeat of the earlier Maze Crawler lesson that a single rating point is not causal |
| 3 | BioHub | Sealed early (0.944 public tie band + OOF 0.030 proxy) | cash <0.5%; Points 5–15%; occupancy 20–40% | 0.946, rank ~1385/3947 (drifted from 929); no prize, no medal | **Partial hit** | Cash was right; the Points band was overestimated — the crowded 0.942–0.946 public frontier was itself a tie-band signal that was never converted into a lower medal probability |
| 4 | CUHK Small | Closed, no reopen (2026-09-15); cash 1–3%, certificate 80–95% conditional on external registration plus one valid submission | Top-15 advancement threshold 0.84577 | Only a smoke-level submission; never reached the advancement zone; no prize | **Hit** | The small-field community cash band and the conditional blocker were both supported by the data |
| 5 | CUHK Large | Closed, no reopen; cash 1–5%; subject-disjoint (Fresh20) gate | A new VLM family had to pass the gate to advance | Two 0.78070 finalists delivered frozen; the Fresh20 net −1 gate rejected the family | **Hit** | The gate blocked a negative-gain method family; the cash band was correct |
| 6 | Traffic | Frozen guard until D-30; the 2026-10-15 review found all three unfreeze triggers false and kept the freeze | If 3–5 single-variable gains had accumulated to 0.75–0.77 → rank 250–300 (never triggered); local lower bound 0.0035 | 0.74733 unchanged: rank 38/65 → 342/457 → 506/661; the external prize-registration deadline (2026-10-25 AoE) passed unregistered and eligibility was forfeited | **Partial hit** | The freeze guard was correct (every audited opportunity had a lower bound below 0.0035); but the off-platform registration deadline was not monitored — the line's only prize channel failed silently, the single most expensive miss in the table |
| 7 | ARC2 | Switch lines → anchor first; second slot only at ≥29.0 | Public-method ceiling 31–33 ≈ rank 1200+; target was an "effective mid-table" position | Anchor 56287444 = 28.89, below the 29.0 floor; rank 1459/2888; no different-family candidate by 2026-10-25/28; seal scheduled for 2026-11-01 | **Hit** | The floor gate, the effective-mid-table ceiling, and the same-family/license/non-solution triple filter all held |
| 8 | Poker | Sealed (one-shot execution authorization consumed; execution incomplete) | cash <0.5% at the then-verified 0.44388; Top 3 required ~0.90 | Sealed with unknown termination; OOF 0.948 → LB 0.444 collapse | **Partial hit** | Cash was right, but the failure mode was infrastructure (a long run with no checkpointing; a process-group timeout killed the detached run), not science — the ROI card had no field for that |
| 9 | HOD | Sealed before entry (volume mount failed closed ×3; no attachment path in the submission UI) | cash 1–5% conditional on ≥0.64; occupancy 50–75% | Zero submissions; the 2026-09-24 deadline ended the line | **Hit (decision) / miss (band)** | "Decision gate before compute" stopped a 15.65 GB download and GPU spend; actual occupancy 0% fell below the band floor — platform-level inaccessibility of the "mount path missing" kind was not modeled |
| 10 | S6E9 | Sealed mid-line, preserving submission 56107927; do not chase 1e-4 leaderboard gaps | cash 0% (merchandise); stop unless an independent method family appears | 0.94636, rank 365/2117; frozen through the deadline | **Hit** | A 1e-4 gap × a 2117-team field → the sunk-cost stop was correct |
| 11 | TartanIMU | Delivery-only (0.315 behind the Top 10; not competitive) | cash 0%; workshop recognition 1–5%; compliant-package occupancy 20–40% | Delivery complete: the public repository and prediction endpoint answered (rechecked 2026-10-27) and the form receipt chain is complete; 0.63142 / 0.53485 | **Hit** | The "the only positive return is the deliverable, not the model" call was accurate; shifting the remaining budget to delivery preserved the recognition and receipt chain |
| 12 | ARC3 | Sealed (eligibility gate unclosed, no Join); 2026-10-15 local smoke run + preregistered gate | cash <1% (no differentiated interactive-agent evidence) | Local 24h baseline completed 4 levels vs 8 for the uniform-random control anchor → the gate FAILED and the line was sealed per the preregistered stop rule; the entry window closed 2026-10-26, making joining objectively impossible | **Hit** | The local gate stopped the $850k temptation before Join; the verdict was objectively confirmed when the entry window passed |

**Discrimination ledger: 7 hit / 4 partial hit / 1 miss (Kaggriculture).**
All nine stop-loss-class decisions (seal / freeze / floor / exclude) were
correct. Positive-allocation decisions number only two (TartanIMU, ARC2) — both
hits, but far too few to generalize from.

## 1b. Exclusion-class backtest (tracked-but-excluded lines)

| Line | Decision | Subsequent fact | Verdict |
|---|---|---|---|
| S6E10 | Excluded (2026-10-01) | 3391 teams, merchandise-only; never joined at zero cost; final deadline 2026-10-31 passing at review time | Hit |
| RSNA Knee | Backup only (skipped 2026-10-15) | Entry 2026-10-15 / final 2026-10-22 both passed; never joined; ~4700 teams and <0.5% cash | Hit (counterfactual unmeasurable; right-censored) |
| AI4S | Hold (external registration plus unresolved IP terms) | Final 2026-10-10 passed; never joined; IP terms never closed | Conditional hit |
| Pokemon TCG strategy | Excluded (entry closed 2026-09-06) | The eligibility fact-gate was correct | Hit |
| ARC3 | Not joined (local gate first) | Entry window closed 2026-10-26 plus local gate FAILED | Hit (objectively confirmed) |
| Housing / StudentSuccess / PostgreSQL ×2 / Gemma main track | Rule-based exclusions | None yet due (2026-11-10 to 2026-12-02) | Undecidable, pending |

Exclusion side: all five judgable rows hit, none overturned — exclusion
discrimination is better than participation-side discrimination.

## 2. Three findings

1. **Preregistered floor gates and cost gates are the single largest source of
   correct decisions** (direction Verified on a 12-line sample): the TreeHSI
   0.15 floor, the ARC2 29.0 floor, the Traffic 0.0035 local lower bound, the
   ARC3 preregistered gate, and the S6E9 sunk-cost stop — across at least five
   lines, the worst-case loss was locked to one submission or zero (Verified).
2. **"Decision gate before compute," plus delivery-only repositioning, converted
   dead ends into preserved assets** (Verified): HOD (the mount gate stopped a
   15.65 GB download and GPU spend), ARC3 (the local gate ran before Join), and
   TartanIMU (a 0.315 gap behind the Top 10 became a complete delivery chain
   with recognition intact).
3. **The recurring misses are systematic, not random** (Verified per instance):
   off-platform registration deadlines outside deadline monitoring (Traffic);
   infrastructure-failure modes with no ROI field (Poker, HOD mounts ×3, the
   ARC3 lf52 crash); single-reading rating extrapolation in game lines
   (Kaggriculture, repeating Maze Crawler); validation-proxy optimism with
   20–50 point OOF→LB collapses (TreeHSI 0.688→0.064, Poker 0.948→0.444); and
   snapshot-rank drift at constant score (Traffic 38/65→506/661 at 0.74733;
   BioHub 929→1385; ARC2 teams 2050→2888→3473), so rank bands must be corrected
   for team-count growth.

## 3. Scoring formula v2

The base is unchanged (fields: deadline distance, team count, prize pool,
additional deliverables, data scale and accessibility, compute shape, historical
strength match, public-pool health, 6h/24h/72h ceiling, risk, verdict). v2 adds
four field extensions plus ten calibration rules, each tagged with evidence and
grade.

**Field extensions**

- Team count → snapshot team count plus a **growth-corrected median team
  count** (remaining window × coefficient, see R8).
- Additional deliverables → itemized list, each flagged for whether it requires
  a **user legal action** (e.g., off-platform registration), each with its own
  deadline (including off-platform) entered into the terminal checklist.
- Data scale and accessibility → size plus **mount/attachment verification
  status** plus **resumable-run (checkpoint) capability**.
- Ceiling → tagged with the **validation-proxy type** (region-OOF / temporal
  fold / none).

**Calibration rules (10 new: 7 Verified / 3 Unverified)**

| # | Rule | Grade | Evidence |
|---|---|---|---|
| R1 | If additional deliverables include off-platform registration or a user legal action, downgrade the verdict one tier (pursue → conditional watch → excluded) and enter that deadline as an independent item in the scan and the daily terminal checklist | Verified | Traffic prize registration forfeited; CUHK certificate conditional channel; AI4S IP unresolved |
| R2 | For fields above 3000 teams with no differentiated mechanism, tag the ceiling "effective mid-table" and compute rank bands against the growth-corrected median team count | Verified | ARC2 ceiling 31–33 ≈ rank 1200+ vs actual 1459; BioHub 929→1385; Traffic zero-score drift 342→506 |
| R3 | In game/adversarial lines, never extrapolate rank or prize probability from a live rating; take the lower bound of the cash band and estimate Points from the convergence-period rank distribution | Verified | Kaggriculture rank 299→3177; Maze Crawler rating noise z=1.15 |
| R4 | If mount/attachment is unverified, halve the occupancy upper bound; for long runs without checkpointing, price the line as a one-shot bet (failure = zero, no partial-credit) | Verified | HOD mount failures ×3 (occupancy 50–75% → 0%); Poker incomplete termination; ARC3 lf52 crash |
| R5 | If the validation proxy has not been tested across domains (across scenes or across time), downgrade the ceiling one tier and tag the proxy type | Verified | TreeHSI OOF 0.688 → LB 0.064; Poker OOF 0.948 → LB 0.444 |
| R6 | Zero-prize lines (kudos/swag only) do not consume submission slots; only read-only or delivery actions are allowed; submission slots are reserved for prize-bearing lines | Verified | TreeHSI kudos-only still spent a Phase 2 submission; S6E9 / S6E10 seal/exclude calls correct |
| R7 | Make floor gates plus a one-submission budget the **default configuration** (not a per-line negotiation): every pursued line must pre-write a score floor and a ≤N-submission budget at entry | Unverified | Shared pattern across TreeHSI 0.15 / ARC2 29.0 / Traffic 0.0035 / the ARC3 preregistered gate; "default" is an ordering judgment, n=12 is not enough |
| R8 | Growth-correction coefficients: early-window small community competitions ×5–10; featured/research ×1.3–1.7 (over a remaining 45-day window) | Unverified (direction Verified) | Traffic 65→661 (×10); ARC2 2050→3473 (×1.7); BioHub 3617→3947 (×1.09 in 12 days); only 4–5 data points for the extrapolation |
| R9 | Delivery-only trigger: if the gap to the Top 10 exceeds 50% of the validation proxy's range, or the remaining time is shorter than the minimum credible improvement cycle, switch directly to delivery-only | Verified | TartanIMU (0.315 gap → delivery preserved the recognition chain); Traffic (a 0.033 gap exceeded the sum of all single-variable lower bounds) |
| R10 | Normalize the ROI denominator: expected reward × hit probability ÷ remaining usable budget, with the hit probability computed from the growth-corrected median rank (not the snapshot rank) | Unverified | Only two positive-allocation rows (TartanIMU, ARC2) exist, so the coefficient cannot be calibrated; the direction is supported by the conservative bias in finding 3 |

## Limitations

1. **Sample size.** The main table has 12 rows, of which only 2 are
   positive-allocation decisions; the probability bands (e.g., "5–15%") are
   heuristic scan estimates, not calibrated probabilities. The backtest can
   validate direction, not calibration.
2. **No counterfactual for exclusions.** The five exclusion-side hits have no
   counterfactual (whether joining would really have ended worse is unknowable);
   the Housing/PostgreSQL/Gemma lines are not yet due and remain pending. Four
   historical generations (NeuroGolf 6260.89, ROGII 9.150/9.416, Nemotron
   0.864/0.852, Maze Crawler) predate the current rule set and contribute only
   post-hoc sealed verdicts, so they are cited as evidence (e.g., R3/Maze)
   rather than counted as backtest rows.
3. **Two versions of the decision rules.** The 2026-09-17 version (science
   gates first, six-gate harness) and the 2026-10-15 revision (tiered
   priorities, offline-autonomy boundaries) are different rule sets. This table
   anchors every judgment to the 2026-09-17 entry round and uses the 10-15
   revision only to confirm "maintain"-class decisions. The probability fields
   are a rolling snapshot (checked 2026-10-27); for already-sealed lines they
   are post-hoc descriptions and are used only as auxiliary evidence.
4. **Measurement is intervention.** The existence of a floor gate itself
   changes the outcome (without the 0.15 floor, TreeHSI might have submitted
   repeatedly). The backtest therefore estimates the joint discrimination of
   "formula + execution discipline" and cannot attribute it to the formula as a
   single factor.
5. The CUHK lines were tracked under a separate campaign record, so their
   entry-time expectations mix sources slightly differently from the main
   record.
