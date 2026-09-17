# Rules and registration audit

Checked through 2026-09-09 in Asia/Shanghai. Kaggle's competition pages and accepted
rules are controlling if a conflict remains.

## Registration status

The authenticated Kaggle CLI returned `userHasEntered=True` on 2026-09-09 for
both:

- `arc-prize-2026-arc-agi-2` — 1,884 teams at the verification snapshot;
- `arc-prize-2026-paper-track` — 176 teams at the verification snapshot.

The ARC sync script then downloaded and hashed all six competition files, and
the Paper Track's authenticated `NOTE.md` download succeeded. These are
independent access checks consistent with accepted rules. The account-side join
was performed outside this paper task; this task records the resulting binding
state and will not repeat or alter it. Read-only inspection of both authenticated
Team pages on 2026-09-09 shows the same team name (`Jiayi Du`), sole member
(`jahyee`), and leader on both tracks. Recheck immediately before submission;
no team setting was changed during this audit.

## Deadlines

| Event | UTC | Asia/Shanghai |
| --- | --- | --- |
| ARC-AGI-2 entry and team merger | 2026-10-26 23:59 | 2026-10-27 07:59 |
| ARC-AGI-2 final notebook | 2026-11-02 23:59 | 2026-11-03 07:59 |
| Paper Track final Writeup on Kaggle | 2026-11-09 23:59 | 2026-11-10 07:59 |
| Internal paper hard stop | 2026-11-08 23:59 | 2026-11-09 07:59 |

The current public Kaggle Paper Track timeline and the prior authenticated
Kaggle snapshot both say November 9 at 23:59 UTC. The ARC Prize overview still
says “November 8, 2026 - Papers due.” Kaggle is the competition-specific
submission surface, but this project retains November 8 at 23:59 UTC as its
conservative internal hard stop while the one-day cross-site discrepancy
remains.

## Paper submission format

A valid final submission must be a submitted (not draft) Kaggle Writeup with:

1. A title, subtitle, selected ARC-AGI-2 track, and no more than 1,500 words.
2. A Media Gallery; a cover image is mandatory.
3. A public Kaggle Notebook in Project Links. A private Kaggle resource
   attached to a public Writeup becomes public after the deadline.
4. The matching ARC-AGI-2 submission ID so Accuracy can be taken from the
   code submission.
5. Optionally, a publicly accessible PDF/project link without login or paywall.

The host asks for Abstract, Introduction, Prior Work, Approach, Results, and
Conclusion; results should include public-evaluation and Kaggle scores and
should not present training-set performance as the result.

## Scoring

The final score is the equal-weight average of six 0–5 ratings:

| Dimension | Evidence this project must produce |
| --- | --- |
| Accuracy | Exact pass@2 leaderboard result tied to the public notebook |
| Universality | Same selector/safety mechanism across solver families and task types |
| Progress | Measured closure of the candidate-union/selection gap |
| Theory | Why evidence, diversity, and abstention should reduce error |
| Completeness | Full algorithm, compute, data boundary, ablations, and failures |
| Novelty | Risk-controlled two-attempt allocation, not a copied ensemble |

First/second/third paper prizes are $50,000/$20,000/$5,000. Papers above 4.5
on the rubric may share a discretionary $375,000 pool. Rubric evaluations are
not released. The Kaggle overview says an earlier submission wins a tie.

## Team and authorship constraints

- Paper Track maximum team size: 8.
- The Paper Track team must match the team that makes the linked ARC-AGI-2 or
  ARC-AGI-3 submission.
- ARC-AGI-2 maximum team size: 5. Therefore the effective maximum for this
  ARC-AGI-2 paper is **5**, not 8.
- Every member must join individually before joining the team; one person may
  use only one Kaggle account and may belong to only one team.
- During the competition, competition code cannot be privately shared outside
  the official team. Public sharing must comply with the rules.
- Now that both tracks are joined, freeze the intended member list before any
  team change or linked submission. Also freeze author order, contribution
  statement, and employer/institution permission where applicable. The rules
  do not prescribe academic author order, so this remains an internal decision.

## Open-source and license requirements

- Paper Track winner license: CC BY 4.0 for the winning submission and source
  used to generate it under Kaggle's specific rules.
- ARC Prize's general 2026 rule additionally requires submitter-authored code
  and methods under a permissive public-domain-style license such as CC0 or
  MIT-0, and third-party work under a license allowing public sharing.
- Project policy: release original orchestration and selector code under
  MIT-0; license the paper/writeup and required winning submission under CC BY
  4.0; preserve all third-party notices and licenses. Seek clarification before
  submission if Kaggle expects a different dual-license form.
- ARC-AGI-2 data are Apache-2.0. Every external model/data/tool must be public,
  reasonably accessible, and license-compatible. Record exact versions and
  hashes before a result is admitted.
- A winner must provide complete code/documentation sufficient to reproduce
  the result and may be asked to participate in a recorded discussion.

## Linked code constraints relevant to the paper

- ARC-AGI-2 is a notebook-only competition, CPU/GPU runtime at most 12 hours,
  internet disabled, with freely and publicly available external data and
  pretrained models allowed.
- The output file is `submission.json`; every hidden task and test output must
  include exactly `attempt_1` and `attempt_2` grids in the correct order.
- The score is exact-match pass@2 averaged over task test outputs.
- ARC-AGI-2 allows one submission per day and two selected final submissions.

## Official sources

- https://www.kaggle.com/competitions/arc-prize-2026-paper-track/overview/abstract
- https://www.kaggle.com/competitions/arc-prize-2026-paper-track/rules
- https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/overview/code-requirements
- https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/rules
- https://arcprize.org/competitions/2026
- https://arcprize.org/competitions/2026/paper
