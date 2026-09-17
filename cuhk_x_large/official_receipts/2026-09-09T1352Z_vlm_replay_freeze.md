# VLM deterministic replay and hard-freeze receipt

Recorded: 2026-09-09T13:52:00Z

## Small20 classification

- Protocol was frozen before the run: 20 unique QA rows, 10 subjects, one action and one object-interaction question per subject, deterministic label-independent selection.
- Protocol SHA-256: `cfcc3ac2ef8dde83ff30b60a5a1119806dab1ae1e68ef4d0349adb461f52229b`.
- Selection SHA-256: `c96d984b7af5bc8e712d951a8ac40dc1c247dfe7c1233520f4edff075e818041`.
- Runtime result: 20/20 inputs readable, 20/20 valid parses, zero implementation failures, zero retries.
- Independent historical-overlap check: all 20 QA/clip pairs already existed in the earlier `full122/object66` artifacts.
- Prompt SHA, video SHA, raw output, and parsed prediction match exactly on 20/20 rows.
- Classification: `PASS_ONLY_AS_REPRODUCIBILITY_PIPELINE_SMOKE`.
- Scientific decision: `REJECT_AS_NEW_PERFORMANCE_OR_PROMOTION_EVIDENCE`.

## Read-only historical taxonomy

- All 188 currently recovered labeled HARn action/object QA–clip pairs already appear in historical VLM artifacts; genuinely unseen eligible pairs: 0.
- Action direct output: VLM `87/122`, subject-disjoint parent `65/122`, row-level net `+22`; subject deltas are 10 positive, 5 negative, 3 tied, one-sided exact sign `p=0.15087890625`.
- Object direct output: VLM `26/66`, subject-disjoint parent `53/66`, net `-27`; subject deltas are 1 positive, 13 negative, 3 tied.
- These are post-hoc error-taxonomy results only. They cannot select, promote, or submit a router.
- Audit report SHA-256: `8ecc8ca036571f9c802905496029600daa708ccdd5942d27c2210987f1df7f91`.

## Full test action stability

- Complete-archive single-video run: 51/51 valid outputs, zero errors.
- Five rows satisfy the already historical sensor/VLM-parent-disagreement condition. Three were already deployed; two became visible only with complete test coverage.
- No new candidate was built and no submission was made.

## Hard stop

Direct VLM promotion and any new router direction are frozen. They may resume only after at least 20 labeled QA/clip pairs from genuinely new clips have never appeared in any historical VLM artifact and are evaluated under a pre-frozen, subject-clustered protocol. A passing screen would only trigger a larger fresh validation, never direct submission.
