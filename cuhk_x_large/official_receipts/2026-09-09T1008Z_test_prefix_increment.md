# Official test-prefix increment and no-change decision

Recorded: 2026-09-09 10:08 UTC

## Authorized archive recovery

- Source: the organizer's Google Drive test archive.
- Previous verified prefix: `1,140,850,688` bytes.
- Current verified prefix: `1,174,405,120 / 1,994,984,736` bytes.
- New verified range: `33,554,432` bytes.
- Prefix SHA-256:
  `1a377aec51bc7997e7489c7b203f03060e95ed022aac76b9c46f86ee636ec097`.
- The next range was stopped after Google returned its quota page; it was not
  treated as archive data and no alternate identity or restricted mirror was used.

The strict ZIP-prefix parser recovered only complete MP4 entries. The new
manifest contains 430 files across 119 of 208 official test units: 37 HARn and
82 HAU. This is an increase of 12 files and four test units. Manifest SHA-256:
`7e5ec38ec6f42bfd5e28804a59c1c45765c8feffd2f9c52309cef8d9c847d717`.
Extraction report SHA-256:
`dbc8bca28e77efec89c892c1497728356f7fad4181042a10ea06a4de1f6b35d4`.

## Incremental VLM evidence

The already-qualified 4B protocol was run only for newly available HARn rows.
Both outputs were valid and nonempty; neither used test labels:

- `test_0513` (single): VLM `A`, parent `C`, nominal sensor output `A`, but
  `sensor_present=false`; it is ineligible for a sensor/VLM consensus gate.
- `test_0529` (object interaction): VLM `B`, parent/sensor `C`, with a real
  sensor input; sensor and VLM disagree, so it is ineligible.

The reporting implementation was corrected so consensus requires
`sensor_present=true`. Corrected single coverage is 30/51, with 24 real-sensor
rows, 12 valid agreements, and three parent-disagreeing consensus rows. Corrected
object coverage is 11/21, with nine real-sensor rows, four agreements, and one
parent-disagreeing consensus row. All four qualified overrides were already in
the submitted v1 candidate.

- Inference script SHA-256:
  `c87905e8355225807cc204f919139ccb296855ded1ab6f512e302badd2743bd3`.
- Single prediction-log SHA-256:
  `cfccccf7ce50c079e8f03dd2c3d150d18367da6dfd29735d7ecbd33a715e072b`.
- Single report SHA-256:
  `6947da6ff222944881da49058aa68f946610893f302b0ee81a1aec5059b96f5c`.
- Object prediction-log SHA-256:
  `31c0575880c99feca126ec6d2b78d7614452279a364c230223e3d4706419770d`.
- Object report SHA-256:
  `50b678e82755c6d0ef2653c5de1a904dfa514173175c60b0baf6c64cf3e8fc57`.

## Candidate gate

`visual_sensor_consensus_v2.csv` passes the official 682-row schema validator
and is byte-identical to submitted v1 and Kaggle submission `56116980`:

`e54652a8746fca7d434a6a4bd162458448e709ff224b074ca37a0f538dec5463`

Candidate-builder SHA-256:
`948aab2b3f2a8898242675dee5a0bac4b44e33c53d43dc23913cb70c2e703a46`.
Candidate report SHA-256:
`6a7273518d10c65dccb36e63276f0d51813be3a932690ece3bc02ac979dd07af`.

Decision: `NO SUBMISSION`. The newly recovered evidence changes zero rows, so
a duplicate leaderboard submission would provide no information. Submission
`56116980` remains the current private-robustness candidate.

The live Kaggle submission list was rechecked after this decision. Submission
`56116980` remains complete at public score `0.78070`; rejected experiment
`56117539` remains complete at `0.72807`. No additional submission appears in
the list.
