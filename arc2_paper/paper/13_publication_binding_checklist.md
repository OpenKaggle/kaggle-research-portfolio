# Publication binding and disclosure checklist

Both competitions are joined, so the paper is now in binding execution state.
Nothing in this file authorizes a submission; it prevents an otherwise strong
Writeup from failing format, identity, permission, or publication checks.

The public Kaggle Paper Track timeline now independently confirms the prior
authenticated deadline snapshot: November 9, 2026 at 23:59 UTC. The internal
November 8 at 23:59 UTC safety cutoff remains because the ARC Prize overview
still displays November 8.

## Required links and identities

| Item | Frozen value | Status |
| --- | --- | --- |
| Paper Track team name/members | `Jiayi Du`; sole member/leader `jahyee` | verified 2026-09-09 |
| ARC-AGI-2 team name/members | `Jiayi Du`; sole member/leader `jahyee` | verified 2026-09-09 |
| Public Kaggle notebook URL |  | missing |
| Public notebook version |  | missing |
| ARC submission ID |  | missing |
| Submitted `submission.json` SHA-256 |  | missing |
| Source repository URL/commit |  | missing |
| Optional public PDF/project URL |  | optional |
| Final Writeup URL/version |  | missing |

The Paper and linked ARC teams must match exactly. Do not infer team identity
from a notebook slug or local credential; record the visible Kaggle team pages.
The 2026-09-09 read-only snapshot satisfies this check; repeat it immediately
before binding the final submission ID.

## Cover and media

- [ ] Mandatory cover image attached in the Kaggle Media Gallery.
- [x] Frozen cover candidate exists at `media/cover_candidate_v2.png`, SHA-256
  `a1b96ee8da0ae8f49869b1413701e83b958826d9ac7111cf808a1c2c0da851be`;
  generation prompt, alt text, and visual/public-risk audit are recorded in
  `media/cover_manifest.md`.
- [x] Cover depicts heterogeneous candidates → demonstration-only evidence →
  two attempts, with the anchor fallback visually explicit.
- [x] Cover contains no unverified score, rank, prize, logo endorsement, or
  copyrighted puzzle screenshot without permission.
- [ ] Figure 1 decomposes anchor pass@2, net gain, and selector regret.
- [ ] Figure 2 is included only if the risk-coverage or failure-composition
  result adds evidence within the 1,500-word budget.
- [ ] Figure source data and rendering script hashes are recorded.
- [x] Alt text remains understandable without color alone.

## Public notebook binding

- [ ] Notebook is derived from the exact scored version, not a cleaned but
  behaviorally different rewrite.
- [ ] Notebook is public and accessible without a private dataset dependency.
- [ ] Internet is disabled and four-L4/runtime details match the receipt.
- [ ] Attached model/data/source versions match the release manifest.
- [ ] Every dependency declared by the exact notebook metadata has a current
  public-access and license receipt. The V3 inventory is exact but currently
  fails closed on `christopherdaleman/arc-proof-search-trm-2026-source` and
  `sorokin/pip-install-unsloth-flash-patch`.
- [ ] The linked ARC submission ID was produced by this notebook version.
- [ ] Projection fields and historical source-reported scores are labeled and
  cannot be mistaken for the linked score.
- [ ] Candidate, selector, evaluator, and submission receipts are downloadable.

## Disclosure and license gate

The rules warn that private resources attached to a public winning Writeup may
become public after the deadline. Before binding any resource:

- [x] Dated audit `14_license_and_public_risk_audit.md` separates directly
  evidenced licenses from declarations and missing release artifacts.
- [ ] remove credentials, tokens, cookies, local usernames, absolute paths,
  private URLs, employer material, and unrelated personal data;
- [ ] confirm every model, dataset, font, icon, image, and code dependency may
  be redistributed under the intended public release;
- [ ] preserve Apache-2.0, MIT, MIT-0, CC0, CC BY, and other notices;
- [ ] release original orchestration/selector code under MIT-0 and the
  paper/writeup under CC BY 4.0, subject to final rule recheck;
- [ ] keep evaluator-only public labels out of deployable feature and selector
  artifacts even though those labels are publicly downloadable;
- [ ] obtain every author and institution/employer approval.
- [x] Exact public-access/license receipts are frozen for the TRM checkpoint
  and Qwen fine-tune; the antlr4 4.9.3 exact-tag license is bundled and hashed.
- [x] Exact-file preflight allowlist rejects run dumps, evaluator material,
  caches, downloaded weights, local user paths, credentials, evaluator labels,
  and notebook outputs; its V2-smoke manifest passes with zero violations.
- [x] A separate V3 dependency auditor proves the local notebook, metadata,
  preregistration, and dependency set match exactly; it reports the two
  unverified external inputs above instead of silently omitting them.
- [ ] Repeat that audit on the final scored notebook/source package in
  `FINAL_RELEASE_CANDIDATE` mode and inspect every reported exception.
- [ ] recheck generated-cover service terms and do not claim exclusive rights
  or third-party endorsement without a supporting grant.

## Final platform audit

- [x] Deterministic local Writeup preflight passes at 1,217 words against the
  1,450-word safety target, with six required sections, nine claim bindings,
  zero training-performance mentions, and all evidence IDs resolved; it
  correctly reports five dimensions as not final and three remaining
  placeholders.
- [ ] Platform word count is ≤1,500 after captions and rendered text are added.
- [ ] Title, subtitle, selected ARC track, cover, media, notebook, submission ID,
  and project links are all populated.
- [ ] Every numerical sentence resolves to a frozen evidence-registry ID.
- [x] Training/development performance is kept in internal engineering receipts
  and rejected by the Writeup auditor, following the official Paper guidance.
- [x] The three-stage execution contract passes structurally while reporting
  `pipeline_complete=false`; it requires a hash-bound terminal smoke receipt
  before development and cannot treat this structural pass as result evidence.
- [x] The aggregate submission-readiness audit hash-binds every local gate and
  reports `final_ready=false`; its eight blocker classes include unsupported
  rubric dimensions, incomplete pipeline/release/dependencies/bindings,
  missing platform receipts, and unapproved authorship/IP fields.
- [ ] Facts, inferences, limitations, and future work are linguistically distinct.
- [ ] No hidden test label, private competition code, or unsupported manual
  override is exposed.
- [ ] Writeup is submitted, not left in draft.
- [ ] Immutable screenshots/receipts capture the final page and links.
