# Temporal-VLM preregistered50 — blocked at the asset gate

Recorded: 2026-09-11 03:40 UTC / 2026-09-11 11:40 BJT

## Outcome

The comparison was preregistered and code-complete, but no new VLM inference
was started.  All 50 frozen HAU Depth videos are absent from the current
96 MiB HAU prefix.  The official 3,674,779,437-byte Google Drive archive is
still quota-limited; the safely retained prefix is 100,663,296 bytes.

Status: `BLOCKED_ASSET`.

No Kaggle submission was made.  No candidate CSV was created.  The cohort must
not be changed in response to this blocker or to any later observations.

## Frozen cohort

- 50 QA ids and 50 unique clips, with zero overlap against every historical
  VLM JSONL log available at freeze time.
- Source: HAU only; user8 excluded because previous HAU VLM work exposed 22
  user8 clips.
- Five tasks: 10 each of sequence, combination, multi, single, and emotion.
- Ten subjects: five from user1–9 and five from user16–24; each half has 25
  rows and each subject has one row from every task.

## Fixed experiment

- Model: the already-local Apache-2.0
  `mlx-community/Qwen3-VL-4B-Instruct-4bit`, pinned at revision
  `2fd8dacbdb8f1e54b8c005f081ec5bf79c56376b`.
- Shared coarse stage: 8 frames, 64 output tokens.
- Each answer arm: 16 frames, identical prompt, 32 output tokens,
  temperature 0.
- Uniform arm uses 16 uniformly spaced frames.  Localized arm uses 16 frames
  centered on up to two question-conditioned coarse indices.
- Promotion requires every preregistered gate, including +3/30 exact temporal
  answers versus uniform, nonnegative results in every temporal task, positive
  results in both subject halves, and a strong parent-disagreement gate.

The local Instruct model was deliberately retained rather than switching to a
Thinking checkpoint: this experiment isolates sampling as its only causal
variable.  The official Qwen Thinking model and the MLX community conversion
are both Apache-2.0, and the conversion is approximately 3.09 GB, but changing
the model here would confound the comparison and consume space while the
required HAU video is unavailable.

## Verification at stop

- Python syntax compile: pass for freezer and runner.
- Pure sampling/parser unit tests: pass (4 tests).
- Protocol lock: pass.
- Selection hash: pass.
- Historical artifact hashes: pass; zero mismatches.
- Historical overlap: 0 QA ids, 0 clips.
- Current frozen-video availability: 0/50; 50/50 missing.

Resume only after a full official HAU archive has passed size/CRC checks and the
50 frozen Depth paths are present.  The runner checks every path before loading
the model, so a partial asset cannot consume or contaminate the experiment.
