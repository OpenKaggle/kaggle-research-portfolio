# HARn single-video mosaic audit receipt

Timestamp: 2026-09-09T11:47:34Z

## Method

- Model: `mlx-community/Qwen3-VL-4B-Instruct-4bit`
- Pinned revision: `2fd8dacbdb8f1e54b8c005f081ec5bf79c56376b`
- License: Apache-2.0
- Preprocessing: deterministic FFmpeg 2x2 mosaic with Depth Color top-left, IR top-right, raw Depth bottom-left, and a blank bottom-right panel.
- Synchronization checks: source width, height, frame rate, frame count, and duration must match; output width and height must double while frame rate and frame count remain unchanged.
- Inference: one video item, scalar 1 FPS sampling, temperature 0, exact option-letter parsing.

## Validation

- One-question smoke (`training_3591`): 1/1 valid and correct; the matched single-view answer was wrong.
- Frozen 18-row screen: 18/18 valid, zero errors, `13/18 = 0.72222`; matched single-view `0.66667`, matched three-video interface `0.83333`.
- Full validation: 112/112 valid, zero errors, `88/112 = 0.78571`; matched single-view `0.70536`, matched three-video interface `0.82143`; all 18 subjects and 12 actions represented.
- RF + ExtraTrees + mosaic consensus on rows differing from the public parent: `29/33 = 0.87879`, net `+26`, 16 subjects, worst-subject net `-1`. This fails the predeclared positive-per-subject candidate gate.

## Official test stability

- Eligible official test rows with all three views: 27 of 51 HARn single-action questions.
- `test_0473`: empty raw output, no runtime exception.
- `test_0474`: empty raw output, no runtime exception.
- The same independent mosaic preprocessing root failed twice consecutively. Execution stopped immediately after the second failure. No retry was made and the remaining 25 rows were not processed.
- Both invalid outputs are excluded from scientific results and from all candidates.

## Decision

`REJECTED_STABILITY`. No candidate file was built and no Kaggle submission was made. The current best submission and the explicit 2/2 final-candidate selection remain unchanged.

## Integrity

- Training script SHA-256: `7c2cae6b7fa094fe6844303ccf35d235915a26c6cb1654619252bf6fec49aea6`
- Test script SHA-256: `8d46917b2688ea0180daac01edb1174176ed9bc5cbaafb8c9d71653313c91c48`
- Smoke report SHA-256: `c9d47f70f46cc5351c4094947b0614976e0c1e2360b03ee5d46bb12a0c259184`
- Frozen-screen report SHA-256: `112a66978fa859b500ab5248f39a00a2dba47a994b7386ba124090a2600f96a7`
- Full-validation report SHA-256: `93bb590401b28f220566f691abbd9b129d95179bf08aaf6c019920076b58a956`
- Test report SHA-256: `202c92ec9deaf45a33a3a21beebac183fca94aeeb1f6a1bfa93e746cb4c0303f`
- Test prediction log SHA-256: `eb075d2626ab7edca94c91fa1b16a7ae252130414069db3f5fe78e087f2162c3`
