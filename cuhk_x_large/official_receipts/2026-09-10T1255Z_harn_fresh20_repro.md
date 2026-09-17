# Complete HARn, Fresh20 decision, and finalist handoff receipt

Recorded: 2026-09-10T12:55:00Z

## Complete HARn archive and extraction

- Official organizer Google Drive archive size: `1,956,322,919` bytes.
- Full archive SHA-256: `a972d644c1b536f836fe7e4d97ca560e04dc75e5657927b2290a63bc6add7a25`.
- Full ZIP CRC test: PASS.
- Strict extraction: 1,524 videos, 356,408,651 extracted bytes, 524/524 official HARn training units, 18 subjects.
- Full visual manifest: `cache/harn_visual_manifest.json`, SHA-256 `e31e3b7c6f3799f8dd179e01577409ae45721b06d33e37c6f80b8366534021e2`.
- Extraction report SHA-256: `fb22d4b9ccc514be584d0f30942d538c22618716b878aece428a147358c442f4`.

## Genuinely fresh validation freeze

- Historical inventory was frozen and hashed before selection.
- Eligible rows whose QA ID and clip were both absent from all historical VLM artifacts: 374 across 18 subjects.
- Frozen screen: 20 unique QA IDs and 20 unique clips, ten subjects, one action and one object-interaction row per subject.
- Selected QA overlap with history: 0; selected clip overlap with history: 0.
- Protocol SHA-256: `ef71bd50cd29e31d1e89aee6af68bbe34b0c6ace5cfe86c9b04101ceb5a7c408`.
- Selection SHA-256: `ce3dd7b7373ef55ec2beadeb84aa2a0e8ef2c1025a9a3a4d3706111227526537`.

## Fresh20 result and decision

- Input/read pass: 20/20; valid parsed output: 20/20; implementation failures: 0; retries: 0.
- VLM: `12/20 = 0.60000`; subject-disjoint parent: `13/20 = 0.65000`; overall net `-1`.
- Action: net `+3`; object interaction: net `-4`.
- Fixed five-subject halves: net `+1` and `-2`.
- Subject deltas: 2 positive, 3 negative, 5 tied; one-sided exact sign `p=0.8125`.
- Every precommitted promotion gate failed.
- Decision: `REJECT_AND_REFREEZE_VLM`.
- Candidate: NONE. Submission: PROHIBITED and not performed.
- Prediction log SHA-256: `49322840722b880d324a49fdbb99031902d01168534201ddd96060446729a67d`.
- Report SHA-256: `f709b47a0743582789d03f5e94599522bf96a94295ed6fd2e302402bdfa07703`.

## Finalist handoff

- Added `TECHNICAL_REPORT.md`, SHA-256 `cdb55c7c86e92bbc073b37ed5d33abf88b883ab37efe70bbb32a13185d79896f`.
- Added `requirements-repro.txt`, SHA-256 `8d3f57d9d2debd4e22865306ae7a40986dcfb90846a3dbb4fee8d365207c4934`.
- Added executable `inference.sh`, SHA-256 `4494830c630d8cf74e6c710e93d947686ec807a8765e3b66333d6de2e5e6339a`.
- A clean `inference.sh` run completed in 4.167 seconds, made no network request and no submission, and reproduced both selected candidates exactly:
  - Primary `56122653`: SHA-256 `3a76a36e6d3060979370f5b598e090c0e2436689d9eda6b17416ae8bc0aee3e4`.
  - Fallback `56108595`: SHA-256 `a5d300381a79e751c08c03a36036cf56137121fc3f987832e64062b534204702`.
