# Official test prefix increment and no-change receipt

Recorded: 2026-09-09T11:53:49Z

## Download and extraction

- Official source: organizer-linked Google Drive file `large_model_track_test.zip` (`1JFG1tTsfzZR84XSwZ1GB6MkXj9UP8opw`).
- One additional verified 32 MiB byte range was appended. Google then returned its HTML quota page for the next requested range, which was rejected.
- Verified contiguous prefix: `1,207,959,552 / 1,994,984,736` bytes (`60.5498%`).
- Prefix SHA-256: `ede336d6b36904aff254459216496aec8fc58a90242e8eca49063fa72ccf99b5`.
- Complete extracted videos: 450 across 124/208 official test units (39 HARn, 85 HAU).
- The first incomplete entry begins at `large_model_track_test/LM_test_0061/Depth/Depth.mp4`; it was not extracted or used.
- Manifest SHA-256: `b7c01918cb7b55f3df77257c151fbf267b1dcba471e0fb3f6baa1501954806f5`.
- Extraction report SHA-256: `4a0babbc0ebca679212a2becb93652f8ec8c5f2a1c15bd73351b375bffe174c9`.

## Incremental label-free inference

- HARn single coverage increased from 30/51 to 31/51. New `test_0517` output: A, valid, zero error.
- HARn object-interaction coverage increased from 11/21 to 12/21. New `test_0526` output: C, valid, zero error.
- `test_0517`: sensor-present flag is false; public parent and submitted v1 are already A. It cannot qualify.
- `test_0526`: sensor and VLM agree on C, but the public parent and submitted v1 are already C. It creates no change.
- Single report SHA-256: `cb42fe1d33a987ac45be4cc66266ad0aca24738fb6c56ee31b9cdce0a02186ee`.
- Object report SHA-256: `3a5dc3c57126f79650be0417b99941cfb46329c02596c20ec2cf601e762738b9`.

## Candidate decision

- The frozen validation-qualified gate still yields exactly the four existing visual/sensor consensus overrides.
- Rebuilt candidate SHA-256: `e54652a8746fca7d434a6a4bd162458448e709ff224b074ca37a0f538dec5463`.
- This is byte-identical to submitted candidate `56116980`; zero new rows differ.
- Decision: `NO_CHANGE`. No redundant Kaggle submission was made, and the explicit final-candidate selection remains unchanged.
