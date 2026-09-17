# CUHK-X Small Track — P2 TSM scaffold verification

Completed: 2026-09-11 12:58 CST, after the P2 gate was frozen and before any
official visual training member became available.

## Implementation

- `src/selective_split_zip.py` performs split-ZIP/ZIP64 range reads,
  deterministic per-clip midpoint selection, path and format checks, CRC-32
  verification, atomic writes, and valid-output reuse.
- `config/training_split_drive.json` pins all nine official public Google Drive
  volumes plus audited IMU, Thermal, Depth_Color, and IR inventories.
- `src/train_p2_thermal_tsm.py` implements the frozen MobileNetV3-Small
  comparator and P2 candidate without importing organizer or third-party TSM
  code.
- `src/test_selective_split_zip.py` and
  `src/test_train_p2_thermal_tsm.py` exercise both paths locally.

The P2 candidate has 1,558,856 parameters / 6,235,424 raw FP32 parameter bytes.
An untrained serialization audit produced one 6,376,779-byte checkpoint, well
inside the frozen 95,000,000-byte FP32 ceiling. A trained checkpoint is not
created unless all four accuracy gates pass.

The comparator and candidate have exactly the same MobileNetV3-Small topology,
parameter count, initial state, optimizer, fixed schedule, clips, and frame
indices. The comparator supplies `[frame, zero, zero]` and no temporal shift;
the candidate supplies `[frame, positive_delta, negative_delta]` and applies
zero-parameter bidirectional shifts before the frozen non-downsampling inverted
residual blocks.

## Verification

Six tests pass in the active environment:

1. target-only extraction from a real local multi-volume stored ZIP;
2. cross-volume payload reading, CRC verification, and reuse;
3. ZIP64 end-record and locator parsing;
4. deterministic midpoint frame selection; and
5. 40-class Thermal discovery/loading, aspect-preserving center padding,
   comparator/candidate forward passes, one-epoch optimization, single-file
   checkpoint serialization/load, and two byte-identical CPU prediction files;
6. fail-closed rejection of every data root below a `public_mirror` path, so a
   quarantined third-party payload cannot enter P2 discovery.

Source hashes:

- selective reader: `36d4ff5027950c46ba8da0efb6148c3e8ec680d9eab4116b91def022ca0fb55e`;
- reader tests: `3fe58f4b210b3dda7b94dbb7a98b002703ce28bd326c72dc1b1f9b0bd8fd6631`;
- P2 training: `5145ba41e3e4a8a1286f97163fd85293d885e7acd042da88ea4b9a0af519e71a`;
- P2 tests: `d1b0473fbd0f646b44b207cf6884fcec50f681a1f4293c9ad1cf74f953d796ce`;
- source manifest: `968442812f149491a15936e4dde08bdf852f3d1d5ef2356e0e1a354d1d0f39e4`;
- frozen preregistration: `70d6e3fc28be25f3729e95099258a6fcc04d244f6d5c5f1142717ced50933c59`.

Installed package metadata reports torch 2.14.0 under an aggregate SPDX
expression of Apache/BSD/BSL/MIT/LLVM-exception components, Pillow 12.2.0 as
MIT-CMU, and NumPy 2.4.6 as an aggregate BSD/0BSD/MIT/Zlib/CC0 expression.
The implementation itself is marked Apache-2.0 and uses no pretrained weight.

## Real-run status

`PREREGISTERED_PAYLOAD_BLOCKED`.

Google still returns its quota HTML before the central directory can be
cached; Baidu's anonymous route exposes only a client handoff, and Hugging Face
would require unapproved contact sharing. Therefore no official Thermal frame
has been retained and neither subject 6 nor subject 18 has been fit. P2 is not
passed or rejected, Depth/IR and P3 remain locked, and no test prediction or
submission is authorized.
