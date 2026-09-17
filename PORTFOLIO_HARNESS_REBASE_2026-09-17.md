# Kaggle portfolio harness rebase — 2026-09-17

This document replaces the implicit rule “an old task is still running, so keep
optimizing it” with a fail-closed portfolio contract.  It generalizes the
useful parts of the CUHK harness (complete test discovery, immutable exposure
tracking, manifest hashes, and separate research/release states) without
carrying CUHK-specific assumptions into unrelated competitions.

## 1. One candidate, six independent gates

Every candidate must have one immutable candidate ID and pass these gates in
order.  A later gate cannot repair or silently waive an earlier failure.

1. **Portfolio gate** — official deadline/status, team eligibility, remaining
   submissions, resource budget, and a single falsifiable question are frozen.
2. **Data/governance gate** — official source is actually available; license,
   external-data and privacy rules are recorded; train/validation/test boundaries
   are machine checked.  A missing mount is not a model failure.
3. **Scientific gate** — metric implementation, split rationale, negative
   controls, worst-group/time/seed results, coverage and uncertainty are stored
   in a structured receipt.  One aggregate OOF number is insufficient.
4. **Adversarial gate** — at least one plausible shortcut or targeted counter is
   tested.  Examples: opponent-specific routing for Kaggriculture, time-direction
   shift for Poker, scene leakage for HSI, and exposed-example reuse for ARC/CUHK.
5. **Release gate** — inference starts from the real raw input; schema/order,
   row coverage, deterministic replay, runtime/memory, artifact hashes, package
   licenses and network policy pass independently of the research score.
6. **Submission gate** — the exact frozen artifact is linked to its receipt;
   submission is allowed at most once per genuinely new mechanism.  Public-LB
   movement may validate transport, but may not retune rows, thresholds or data.

Valid terminal states are explicit: `PASS`, `REJECT_SCIENCE`,
`BLOCKED_INFRASTRUCTURE`, `BLOCKED_GOVERNANCE`, `SEALED_DEADLINE`, and
`SEALED_LOW_VALUE`.  `UNKNOWN`, a missing receipt, or a killed process can never
be reported as a scientific rejection or success.

## 2. Required candidate receipt

Each active line must emit one machine-readable receipt with at least:

- competition, candidate ID, parent candidate and exactly one changed mechanism;
- official deadline/status snapshot and rules/source identifiers;
- code, data, split, model and output hashes;
- legal/external-data declaration and exposure/probe declaration;
- primary metric plus worst group, seed/time/seat variance and negative controls;
- row/ID/schema/coverage checks, runtime, memory, accelerator and network use;
- pre-registered go/no-go thresholds and the resulting terminal state;
- submission authorization (`true/false`), submission ID if any, and stop reason.

Markdown narratives may explain a result, but they do not replace this receipt.

## 3. Retry and search budget

- Infrastructure: one diagnosis plus one single-variable repair.  A second
  same-class failure becomes `BLOCKED_INFRASTRUCTURE`; do not rename paths and
  rerun indefinitely.
- Research: one mechanism, one sealed comparison pool, and a predeclared seed or
  fold budget.  Thresholds cannot be lowered after seeing the result.
- Leaderboard: no row-level probing.  A second submission is justified only by a
  new mechanism that independently passed all offline gates.
- Discovery: stop broad literature/community scans after two consecutive batches
  add no route-changing mechanism.  Resume only for a rule, data, reproducible
  code, license, or deadline delta.
- Compute: a running process without heartbeat, output manifest and hard timeout
  is invalid work.  Failed or killed jobs must emit an incomplete-run receipt.

## 4. Current portfolio bindings

| Line | Harness state on 2026-09-17 | Next authorized transition |
|---|---|---|
| CUHK Small | `SEALED_DEADLINE`; P2 run ended without a result receipt | Archive and migrate lessons only |
| CUHK Large | `SEALED_DEADLINE`; private 0.72647, rank 55/213 | Preserve v9 reproducibility freeze |
| Kaggriculture | Pipe-7 fails adversarial opponent gate (Market Smart 8–10); factorial identifies post-hoc `q5_reorder` | No upload; any new campaign must use the frozen independent 72-game gate |
| TartanIMU | Research/release artifact frozen; delivery incomplete | Publish verified frozen assets and transmit final report/form only |
| Poker | v4.2 one-time execution stopped after 2/5 folds with no terminal metric | `INCOMPLETE_UNKNOWN_TERMINATION`; sealed, no rerun or submission |
| HOD 2026 | `BLOCKED_INFRASTRUCTURE`: official UI exposes data/download but no notebook attachment route | Sealed unless an official auditable transport appears |
| Tree HSI | Phase-1 OOF contradicted by public 0.10387; Phase-2 manifest not released | Event-only wait; dynamic contract gate is ready and tested |
| ARC-AGI-2 | No trusted current anchor | One exact public strong-baseline anchor, one dependency repair maximum |
| ARC Paper | Delivery/evidence line only | Accept claims only from independent, reproduced ARC evidence |
| Biohub / S6E9 / Traffic | `SEALED_LOW_VALUE` under current evidence/time budget | Reopen only on route-changing official evidence |
| ROGII / Nemotron / Maze / NeuroGolf | `SEALED_DEADLINE` | Archive only |

## 5. Supervision contract

Recurring monitors may observe deadlines, official deltas and already-running
bounded work; they cannot lower gates, start new model families, join a new event,
or submit.  Each active competition has one executor and one next action.  A
supervisor reports only a meaningful delta, terminal outcome, failure requiring
intervention, or a concrete user action.  Unchanged state stays quiet.

The portfolio-level decision ledger is
`PORTFOLIO_CONTROL_PLANE_2026-09-17.md`.  Competition-specific receipts remain
the source of truth for measurements; this harness defines how those receipts
are allowed to change portfolio state.
