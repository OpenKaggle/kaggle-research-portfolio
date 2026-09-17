# First valid submission receipt

- Competition: `cuhk-x-competition-large-model-track`
- Submission time: 2026-09-08 21:47:07 UTC / 2026-09-09 05:47:07 Beijing time
- Kaggle submission ref: `56107594`
- File: `public_fususu_077777.csv`
- Candidate SHA-256: `4e3391e70d0c8ff5a40efb7c317468e8eda3f84e27b40ab3c35ea735352fda9c`
- Candidate MD5: `8f997f262e7be646296442148dc8e64f`
- Status: `SubmissionStatus.COMPLETE`
- Public score: `0.77777`
- Private score: not available before competition close
- Description: `public Fususu 0.77777 anchor; exact Apache-2.0 released predictions; schema+grammar+hash audited`

Gate receipt:

1. Schema/ID: 682 rows; exact `qa_id,prediction` header; IDs unique and in official test order.
2. Grammar: all 682 predictions valid for their declared category.
3. Leakage: artifact came from the competition's public Kaggle Notebook `phuongncn/lb-0-77777-exact-submission-research-handoff`; notebook states that the payload contains predictions only and no hidden labels/manual test labeling. Static code audit found no ground-truth/test-answer access in the exact-artifact path.
4. Stability: deterministic byte reproduction matched the notebook's expected MD5 exactly.
5. Rules/license: source notebook releases original code under Apache-2.0 and is publicly available to all competitors through Kaggle. No competition data were redistributed.

Limit: the notebook does not include its full sensor-specialist checkpoints or OOF lineage. This submission is a leaderboard-verified public anchor, not an independently reproducible finalist package. It must remain the parent until a candidate passes honest subject/clip-disjoint validation.

