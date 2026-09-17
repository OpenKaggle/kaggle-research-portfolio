# CUHK-X Small — Hugging Face safe handoff, round 5

Prepared: 2026-09-11 UTC, after the user explicitly authorized sharing the
current Hugging Face username and email with the official repository authors
and the browser displayed granted access.

## Decision

`READY_FOR_ENV_TOKEN / BLOCKED_CLI_CREDENTIAL / NO_DATA_FILE_REQUESTED`.

The browser-side gate is complete. The remaining external blocker is a CLI
Bearer token: Hugging Face requires the user to confirm their own password to
create/view one. This work did not ask for, read, type, copy, or store that
password or a token. No anonymous resolver request, 401 response body,
training/test payload, test label, or Kaggle submission was requested.

## Official repository lock

Public repository metadata and tree APIs identify:

- repository: `Kevin-Pal/CUHK-X_Small_Model_Track`;
- immutable revision:
  `ca37a2e9c6a06271309be03bbfbe16f29e40d8b4`;
- state: public metadata, `gated=auto`, browser access granted;
- training paths: `Small-Model-Track/Training/data/HAR.z01` through
  `HAR.z08`, plus `HAR.zip`;
- training volume bytes: eight times `5,368,709,120`, plus
  `1,673,136,305`, total `44,622,809,265` bytes.

The gated API redacts the LFS `oid` and Xet hash without command-line
authentication. Each tree entry nevertheless exposes a security-report URL
whose content hash matches the SHA-256 already recorded for the same file on
the organizer's Google mirror. All nine path, size, and SHA-256 triples match
the earlier first-party manifest exactly.

The new manifest is
`config/training_split_huggingface.json`, SHA-256
`0875cab524517f34c962ca2695ed82cc5719b76da789c9dcc6c765897d462de0`.
Every resolver URL is pinned to the immutable revision, never `main`. The file
contains only the environment-variable name `CUHKX_HF_TOKEN`; it contains no
credential or user identity value.

## Environment-only transport boundary

`src/selective_split_zip.py`, SHA-256
`14da077fa5d2a2ec1e6413fb643dc9b3cee5b50ca499372ac11650af1c6857e3`,
now enforces:

1. Bearer secrets can only be read from a strict uppercase environment-variable
   name; a token-like command argument such as `hf_...` is rejected as an
   invalid variable name;
2. the secret value is read immediately before a request and is not stored in
   the reader, manifest, report, or exception;
3. a missing/empty variable fails before `urlopen`;
4. HTTP 401/403 fails once without retrying or reading the error response body;
5. a nominally successful response is read for at most requested bytes plus
   one, so an ignored Range cannot stream a whole multi-GB volume;
6. only HTTP 206 plus exact `Content-Range`, total volume size, and body length
   is accepted; and
7. existing path, ZIP64 geometry, safe-name, stored-member, size, CRC, atomic
   write, and quarantine controls remain active.

Synthetic tests demonstrate missing-auth rejection before the network, exact
Bearer and Range headers, non-retention of the secret, one-shot 401 rejection,
bounded HTTP 200 rejection, and valid 206 acceptance. Tests never contact
Hugging Face.

## Central directory and subject 6/18 byte plan

The immutable ZIP64 geometry fixes the first authenticated transfer exactly:

- final-part tail: `131,072` bytes;
- ZIP64 record prefix: `56` bytes;
- central directory: `73,843,427` bytes at disk 8 offset `1,599,292,780`;
- total control-plane bytes before member-header planning: `73,974,555` bytes.

The reader now supports repeated prefixes, an exact subject filter, and
`--exact-range-plan`. That mode parses the central directory, probes only each
selected member's local header/name/extra fields, and calculates exact payload
bytes and member spans per split volume without reading a payload byte.

The preregistered validation subjects contain 196 indexed clips for user 6 and
184 for user 18. Before the central directory is available, the only honest
static bounds are therefore at most `3,040` selected Thermal frames
(`380 * 8`) and at most `760` IMU files (`380 * 2`). Official missing-modality
patterns will reduce these counts. Their exact selected file count, payload
bytes, local-header probe bytes, and per-volume allocation cannot be recovered
from the deleted 2026-09-09 central-directory probe and are intentionally not
invented while CLI authentication is absent.

Once the user places a token in the process environment outside this task, the
following read-only command computes those exact 6/18 values and downloads no
member payload:

```text
.venv/bin/python cuhkx_small/src/selective_split_zip.py \
  cuhkx_small/config/training_split_huggingface.json \
  cuhkx_small/data/official_hf_subject_plan \
  --prefix HAR/data/Thermal/ \
  --prefix HAR/data/IMU/ \
  --subjects 6,18 \
  --frames-per-clip 8 \
  --central-directory-cache cuhkx_small/artifacts/transport/hf_central_directory.bin \
  --report cuhkx_small/artifacts/transport/hf_subjects_6_18_plan.json \
  --index-only --exact-range-plan --max-range-bytes 16777216 \
  --bearer-token-env CUHKX_HF_TOKEN
```

The report must say `payload_downloaded=false`. A failed auth or Range check
cannot create a valid central-directory cache or plan receipt.

Subjects 6 and 18 alone are a validation slice, not a trainable LOSO fast-kill:
each LOSO fold trains on the other 17 subjects, so even the first honest S1
fold requires the full 18-subject Thermal union. Its acquisition ceiling is at
most eight frames from each of 2,891 Thermal groups (`<=23,128` files). IMU is
not required for S1; the full exact IMU budget remains 5,806 files and
74,079,366 payload bytes, and stays locked until S1 passes.

## Verification

`src/test_selective_split_zip.py`, SHA-256
`c1db839764f88c35c7f4b703d1115e6f37fb3666f842938563b229409825c88d`,
contains six selective-reader tests, all passing locally. The campaign-wide
deep harness also passed with exit code 0: Large unit tests `20/20`, Large
plain-function tests `10/10`, Small tests `15/15`, all three candidate grammar
checks, the 235-file deep reproducibility manifest, the 1,265-event exposure
registry, and the Small boundary audit passed. Its final state is correctly
`PASS_RESEARCH_BLOCK_RELEASE`, not release-ready.
