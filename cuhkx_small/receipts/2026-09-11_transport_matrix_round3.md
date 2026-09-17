# CUHK-X Small Track — transport matrix, round 3

Checked: `2026-09-11T05:34:43Z` / `2026-09-11 13:34:43 CST`.

## Decision

`BLOCKED_TRANSPORT / REJECT_NO_TEST_CANDIDATE`.

No source passed both the transport and license/provenance gates. No Thermal
training frame was accepted, neither P2 fold was fit, no test data or labels
were opened, and no Kaggle submission was created.

The three independent gates are:

- **Transport readiness — `BLOCKED`:** all organizer Google volumes are under
  quota, Baidu exposes no verifiable HTTP `dlink`, Hugging Face browser access
  is granted but the CLI token is absent, and the third-party Thermal copy
  fails licensing.
- **Scientific gate — `NOT_RUN_PAYLOAD_BLOCKED`:** P2 has no accepted sensor
  payload, so subjects 6 and 18 have no B0/P2 measurements. The earlier
  metadata-only smoke remains `REJECT` and is not scientific evidence.
- **Release gate — `REJECT_NO_TEST_CANDIDATE`:** no candidate has passed four
  LOSO folds, per-class/subject robustness, one-checkpoint size, license, and
  byte-identical inference requirements. Test inference and submission remain
  prohibited.

## Transport matrix

| Route | Read-only result | License/provenance result | Decision |
|---|---|---|---|
| Organizer Google Drive, all nine split volumes | Every volume returned HTTP 200, `text/html`, 2,009 bytes, no `Content-Range`, title `Google Drive - Quota exceeded` | First-party organizer link | `BLOCKED_QUOTA` |
| Organizer dataset browser | Its documented JSON API lists the Small `Train` directory, but that directory and the historical `CUHK-S/HAR`, `CUHK-S/source_data`, and `CUHK-X` paths all returned HTTP 200 empty arrays at `2026-09-11T06:33:53Z`; no `/data` object was requested | First-party organizer host | `OFFICIAL_PORTAL_EMPTY_LISTING` |
| Organizer Baidu Wangpan | Prior verified share/list/signing path still ends in an encrypted/client handoff rather than a normal range-capable HTTP `dlink`; no new retry was made | First-party organizer link | `BLOCKED_CLIENT_HANDOFF` |
| Organizer Hugging Face | The user explicitly authorized username/email sharing and browser access is granted; a commit-locked nine-volume manifest is ready, but the CLI has no token and token creation requires the user's own password confirmation | First-party and gated | `BLOCKED_CLI_TOKEN`, environment-only handoff ready |
| Public Kaggle `nimeshparmar/cuhk-thermal-dataset` | Public listing reports 3,623,043,290 bytes and exposes CUHK-X action/user/trial paths | Kaggle metadata claims CC0 while the organizer says the CUHK-X data is governed by CUHK-X License v2.0 and is not redistributable; uploader provides no authorization or provenance statement | `REJECT_LICENSE_CONFLICT` |
| Public Kaggle K-KUNO model dataset | Eight public files; two real weight files total 93,688,142 bytes | Mixed CUHK-X competition terms, AGPL-3.0 YOLO, MIT architecture, Apache-2.0 notebook; dataset metadata says `other` | `RESEARCH_ONLY`, not a candidate |
| Other public competition notebooks | Eleven notebooks inventoried; relevant Thermal/Skeleton/IMU notebooks publish code but no trained output weights or training payload | Notebook code is inspectable, but no additional accepted data source | `NO_PAYLOAD` |

## Google evidence and zero-cost retry

The machine-readable matrix is
`artifacts/transport/google_parts_2026-09d1.json`, SHA-256
`265cc04600b6235f8b7aa6ba6d6af8f5956785e04c0a48539b1319b9e6a6115b`.
All nine results are classified `GOOGLE_QUOTA`. Body SHA-256 values are kept in
that matrix; the values differ because Google's HTML contains a changing nonce,
while status, length, MIME type, title, and missing range header are identical.

`src/probe_google_training_parts.py`, SHA-256
`3df54c74727c4f8ba1bd057573b73210831bc35f72a5e7a07a1094a06b087f40`,
implements the next retry. It requests exactly byte zero from each volume,
caps every response body at 65,536 bytes, and returns success only when all
nine responses are HTTP 206 with exact `bytes 0-0/<manifest size>` ranges and a
one-byte non-HTML body. The observed blocked run transferred only 18,081 bytes
of quota pages.

Run from the campaign root:

```text
python3 cuhkx_small/src/probe_google_training_parts.py \
  cuhkx_small/config/training_split_drive.json \
  --output cuhkx_small/artifacts/transport/google_parts_latest.json
```

Only an `ALL_RANGE_READY` result permits the already-tested selective reader to
request the complete central directory and at most eight frozen midpoint frames
per Thermal clip. Any non-206 response stops before payload acquisition.

## Third-party Thermal mirror quarantine

Dataset metadata was downloaded before payload use:

- Kaggle dataset ID `11627098`, owner `nimeshparmar`, title
  `HAR Thermal Dataset`, updated `2026-08-12`;
- metadata SHA-256
  `e2c3cfda48440a639a2adaabc22af4f9b92d1c79220b6a0087776a2bba61aef9`;
- metadata description is empty and declares `CC0-1.0`;
- the first public file page contains paths such as
  `Thermal/Thermal/0_Wash_face/user16/...`, showing that it is a redistribution
  of the competition taxonomy rather than an independently documented source.

A download began while verifying whether this could be a legitimate public
transport mirror. It was stopped as soon as the license conflict was confirmed.
The incomplete 1,191,182,336-byte file is retained at
`data/public_mirror/cuhk-thermal-dataset.zip`, SHA-256
`bf772d205d0439546bba2b64c8f1fdbe3d01f549f6ef4dab319530bea011ebe0`.
It has no ZIP central directory, was not extracted, was not read by a model,
and is excluded from every experiment. It must not be resumed unless the
organizer explicitly confirms this exact Kaggle dataset as an authorized
mirror.

The machine-readable quarantine sentinel is
`data/public_mirror/QUARANTINED.json`, SHA-256
`5c19163285865831cf0c2a6d2139338b9d9e2d7f715e8292a42fb369b2b2e954`.
It records the stable partial-file size/hash and sets extraction, training, and
resume authorization to false. In addition, `discover_clips` now rejects every
path containing a `public_mirror` component. The dedicated regression test and
the five existing engineering tests pass: six tests total in 12.550 seconds.

The dormant clean-room audit utilities
`src/audit_kaggle_thermal_dataset.py` and
`src/prepare_kaggle_thermal_midpoints.py` are Apache-2.0 and fail closed on
unsafe paths, unexpected subjects/classes, or disagreement with the official
201,466-file / 3,524,685,759-byte Thermal inventory. They do not authorize the
rejected mirror.

## Public model and notebook audit

The previously reported-unavailable K-KUNO model dataset is currently readable
through the Kaggle API. The superseding details are recorded in
`2026-09-11_public_baseline_gate_audit.md`.

- `ensemble_packed.pt`: 88,074,378 bytes, SHA-256
  `1bef2e215fc100acf571b90370a8353574fdad6951b0f75f6e3404521643322f`;
- `yolo11n.pt`: 5,613,764 bytes, SHA-256
  `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`;
- the first file contains two packed R(2+1)D fold states at int5/int6; the
  second contains detector weights, so the published graph violates the
  one-checkpoint gate even though the total is below 100,000,000 bytes;
- only two aggregate parent fold accuracies are supplied. There is no frozen
  clip manifest, four-LOSO result, per-subject result, per-class result, or
  independently reproduced offline inference.

The `CUHK X 14th Place 0.8 Thermal Baseline` source was also pinned at SHA-256
`533d41409ff6dc1ddcba17dbba6fc2bc12b9688eeb4add2c23f42976f8f07428`.
It is a useful subject-wise Thermal method description, but its public runtime
attaches no training dataset and emits no trained checkpoint. It therefore
does not unblock P2.

## Resume gate

On a future `ALL_RANGE_READY` Google probe:

1. acquire only the organizer-linked central directory and frozen Thermal
   midpoint members;
2. require exact geometry, full Thermal inventory, safe paths, per-member
   size/CRC checks, and atomic/reusable writes;
3. run B0 versus P2 only on frozen subjects 6 and 18 first;
4. stop if both gains are below +0.01;
5. do not open test data or create a submission unless the complete four-fold,
   checkpoint, quantization, license, and deterministic-output gates pass.
