# Extended HAU visual-probe receipt

Recorded: 2026-09-09 08:19 UTC

The fixed, pinned Qwen3-VL visual route was extended only to the remaining HAU
question grammars present in the CRC-checked training prefix. All recovered
clips belong to `user8`, so these are bounded rejection screens rather than
full subject-disjoint validation.

## Multi

- Rows: 22; valid nonempty exact-grammar outputs: 22; errors: 0.
- Exact-match accuracy: `0.2272727273`.
- All 22 predictions contained one letter, confirming that this zero-shot
  prompt did not solve answer-set cardinality.
- Prediction log SHA-256: `c4fbf0eabcb1ad079316811408bcd0980eef7660552a0a06e521d9daacc9b7fc`.
- Report SHA-256: `e14454640ac485e1ea62cacfa0cbbd976ddb5c45a204fbec424606f6d237a153`.
- Decision: `REJECTED`; no test inference.

## Combination

- Rows: 22; valid nonempty exact-letter outputs: 22; errors: 0.
- Accuracy: `0.5909090909`, below the compact graph's 18-fold OOF accuracy
  of `0.8354430380` for HAU combination.
- Prediction log SHA-256: `9f0ab16550981373bebdf04163afe3c2ce66db87721eb4eb55fa13b6fbe9907a`.
- Report SHA-256: `b75190a6b831afc181d756e792b985f6f8685b9d7355549074cef7a20d4e1483`.
- Decision: `REJECTED`; no test inference.

## Sequence

- Eligible recovered rows: 10; attempted before stop: 8.
- All eight raw responses were nonempty but used space-separated letters;
  the exact competition parser therefore returned empty predictions.
- Repeated invalid output triggered the stop rule. These rows are excluded
  from accuracy calculations and from every candidate; no retry was made.
- Partial prediction log SHA-256: `c9ce79ac13462f1b7494e81aa4653bd613014d462091f6eda062ce8240e982a3`.
- Decision: `REJECTED`; no test inference.

## Reproducibility

- Script SHA-256: `af3c8276ed0f558e7766c4e3246285a1682819929ddb33f6a2a279df79ff9457`.
- Model revision: `2fd8dacbdb8f1e54b8c005f081ec5bf79c56376b`.
- Model manifest SHA-256: `6f2156b299b448eb9e184f8b9775ef07d4c270de940a668b5d509da9248db5a4`.
- Visual manifest SHA-256: `95fbe034dc95ff29a2b8cc00f1dc7d97eea4f63cecf2aca25c36bb8c4d9e336a`.
- No test answer was accessed or inferred.
