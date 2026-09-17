# Nonvisual supplement and RF v1 receipt

Recorded: 2026-09-08 22:45 UTC / 2026-09-09 06:45 BJT

## Official data artifact

- Source: organizer-listed public Google Drive mirror for `LMT_(IMU,Radar,Skeleton).zip`
- Bytes: `388866143`
- SHA-256: `72f34e9f0005d2ee0fefe9a7687bd54fa6dbdf171b6112132523085fa7475afb`
- Archive integrity: `unzip -t` passed with no errors
- Archive entries: `285502`
- Uncompressed bytes reported by `zipinfo`: `995453945`
- Embedded manifest SHA-256: `1dd612c2fa27afda08ce693f46b9c04ac04b5501a6e099af31a173558803bee6`

The embedded README says 3912 training and 208 testing units. The embedded
manifest actually lists 3932 units: 3737 training and 195 testing units that
have at least one nonvisual modality. File-presence counts exactly match the
manifest: IMU 3895, Radar 3905, Skeleton 3929. Fifty-eight IMU units contain
the declared CSV files but only headers and are treated as missing signals.

## Validation

- Design: 18-fold leave-one-subject-out; clips remain intact
- Seed: `20260909`
- Model: scikit-learn 1.8.0 RandomForestClassifier, 240 trees
- HAU features: IMU + Skeleton
- HARn features: Skeleton
- Radar: not used in v1
- OOF rows covered: 2180
- HARn single: 0.7668997669 overall; 0.5333333333 worst subject
- HAU emotion: 0.4487021014 overall; 0.3611111111 worst subject
- HAU single failed the parent comparison and was rejected

## Second submission

- Candidate: `nonvisual_rf_v1_harn_single_highconf.csv`
- Candidate SHA-256: `1154a175c51b989957206ba02d9091528ffe5a50eda9cc87da8221614d8cb300`
- Gate: HARn single, sensor present, confidence at least 0.30, expert disagrees with parent
- Changed rows: 1 (`test_0520`, `C` to `A`)
- Kaggle submission ref: `56108202`
- Submitted: 2026-09-08 22:43:45.990000 UTC / 2026-09-09 06:43:45.990000 BJT
- Status: COMPLETE
- Public score: `0.77777` (tie with parent)

Because the public leaderboard covers only about half the test data, a tie from
one changed row is not evidence about that row's correctness and is not used to
infer any hidden label.
