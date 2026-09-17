# Visual-sensor consensus submission receipt

Recorded: 2026-09-09 07:34 UTC / 2026-09-09 15:34 BJT

## Official test data prefix

- Official archive: `large_model_track_test.zip`
- Verified prefix bytes: `1140850688 / 1994984736` (`57.1859%`)
- Prefix SHA-256: `f793041698f51cbcd6ebef962a57dd8fee337c9022852a0d8c7efddf73358342`
- Stop reason: Google Drive quota response after the last complete 32 MiB range
- Recovered videos: 418
- Recovered units: 115/208 (35 HARn, 80 HAU)
- Per-file verification: raw DEFLATE stream reached EOF; signed data descriptor compressed size, uncompressed size, and CRC32 matched
- Manifest SHA-256: `385a31a1350d1226f6d6ad83dcbb13d6c90b33d969df8e23c5bb36894c783bd9`
- Extraction report SHA-256: `7c9ac599a7b64a7fad0c278ca1c35bd357135d90bc628a6a2200a75fb8f12381`

## Label-free test inference

- HARn single coverage: 29/51; all 29 outputs valid
- HARn object-interaction coverage: 10/21; all 10 outputs valid
- Action sensor/VLM consensus differing from frozen parent: 3 rows
- Object sensor/VLM consensus differing from frozen parent: 1 row
- Every consensus row requires `sensor_present=true`
- No test answer was read, reconstructed, or inferred

## Candidate and submission

- Candidate: `visual_sensor_consensus_v1.csv`
- Candidate SHA-256: `e54652a8746fca7d434a6a4bd162458448e709ff224b074ca37a0f538dec5463`
- Candidate MD5: `bcc8faedf753e607a10259ba67e3c982`
- Schema validator: PASS; 682 IDs in official order; category grammar PASS
- Changes versus frozen parent: 7
- New changes versus prior nonvisual union: 3
- Kaggle submission ref: `56116980`
- Submitted: 2026-09-09 07:33:43.213 UTC / 2026-09-09 15:33:43.213 BJT
- Status: COMPLETE
- Public score: `0.78070`

The first upload attempt terminated with an SSL EOF before Kaggle created a
submission; the submission list confirmed absence. A single retry succeeded,
and the list confirms exactly one new submission. The public tie does not reveal
whether any changed row is public or private and is not used to infer labels.
