# HARn synchronized three-view VLM audit

Recorded: 2026-09-09 11:25 UTC / 2026-09-09 19:25 BJT

## Method

The pinned public `mlx-community/Qwen3-VL-4B-Instruct-4bit` checkpoint was given
three synchronized views of each HARn clip in a fixed order: Depth Color, IR,
and raw Depth. The prompt stated that all three non-RGB videos showed the same
action and required one exact answer letter. Seed, 1 FPS sampling, deterministic
temperature, parser, option rendering, and the action-first/subject-spread
selector matched the single-view baseline. All three modalities were required.

Model revision: `2fd8dacbdb8f1e54b8c005f081ec5bf79c56376b`.
Model manifest SHA-256:
`6f2156b299b448eb9e184f8b9775ef07d4c270de940a668b5d509da9248db5a4`.

## Smoke and implementation correction

The first `1 unit × 1 question` smoke did not produce a model output because
the generation interface accepts only a scalar FPS argument even though the
message formatter accepts one FPS value per video. The resulting TypeError and
empty output were excluded from metrics and candidates. Failed log SHA-256:
`27251bf43ac26ef1e42e6a92953ac65446b85dbb8cb9dfb90ac836808cd25905`.

The scalar-FPS correction was tested under a new run name on the identical QA,
`training_3591`. It produced valid exact answer `C`, which was correct; the
matched single-view prediction was incorrect. This was only an interface smoke,
not scientific evidence.

- Successful smoke log SHA-256:
  `f281c18c9fa3eec4e187445d16a3f46b033311ff5933f179715cc7f951a9c5be`.
- Successful smoke report SHA-256:
  `09a2290b094ed0145ede8899c06a27dac16dda43c8346f7c1e26303a535fb48a`.

## Frozen screen and complete validation subset

The frozen 18-row screen produced 18 valid predictions and no errors:

- Three-view: `15/18 = 0.8333333333`.
- Matched single-view: `12/18 = 0.6666666667`.
- Three-view-only correct: 4; single-view-only correct: 1.
- Screen log SHA-256:
  `0071a4c42812bc6e4c90596ef49b76479b4d2007c4ce604f4bf2f9e66c85d754`.
- Screen report SHA-256:
  `b89ddaf8ee80c9b89b169dbb0caecae7c61c0717b1cb65d92a717fd62ac4cf4f`.

The method therefore expanded to every three-view-complete recovered training
row. Results on 112 rows covering all 18 training subjects were:

- Three-view: `92/112 = 0.8214285714`.
- Matched single-view: `79/112 = 0.7053571429`.
- Three-view-only correct: 16; single-view-only correct: 3.
- Valid outputs: 112/112; errors: 0.
- RF + ExtraTrees + three-view agreement: `68/70 = 0.9714285714` correct.
- Among 28 such agreements differing from the public-graph OOF parent, 26 were
  correct and two were parent-correct.
- Full log SHA-256:
  `fe07976a0c26e6193aba5fba3d4a9e0b85e0b7d60cc206daa63f3a4335a3255e`.
- Full report SHA-256:
  `d857cfa97deb3fc13d4c10aa69332a32166737bfe753098152f93a9de4860fcd`.
- Validation script SHA-256:
  `3bd3ec02110db95c7995b0d927026d7ed71a1663a80860bed2e83ba496324543`.

## Official test stability gate

The validation-qualified method was applied once to all 27 of 51 official HARn
single-action rows whose recovered test units contain all three views. No test
answer was available or used.

- Attempts: 27.
- Valid exact outputs: 25.
- Empty outputs: 2 (`test_0493`, `test_0521`).
- Raised inference exceptions: 0.
- Test log SHA-256:
  `1122b7b20b23774ae6bf024322f5e4b505b99227b3a684ddbe642d33b29bd8ed`.
- Test report SHA-256:
  `d45e674c002806bf531e00f790bfd791f891e3df37d6c7cf7365087a4b225673`.
- Test script SHA-256:
  `2f77ba12b4ba42cf6e3e257aeaa63b121c12b92c603ec3db3da2092f3f8d0d05`.

Decision: `REJECTED_STABILITY`. Two repeated empty outputs from the same
three-view preprocessing root fail the exact nonempty-output gate. The root is
stopped without retries; empty outputs are excluded; the 25 valid test outputs
are not used to construct a partial candidate. No submission was made and the
selected final submissions remain unchanged.
