# Stage2 owned raw-input package gate

Decision: **technical raw-input gate PASS; finalist governance gate BLOCKED; no submission**.

The separate `inference_owned.sh` entry point discovers organizer IMU, radar,
and skeleton units from the raw directory, validates every selected declared
unit, recreates the fixed `[655, 84, 650]` feature schema, and invokes the
owned Stage2 builder. The legacy `inference.sh` remains byte-identical at
`4494830c630d8cf74e6c710e93d947686ec807a8765e3b66333d6de2e5e6339a`.

Two clean, network-blocked official runs each discovered 3,932 units, selected
195 units for 208 QA clips, hashed 22,661 raw files, and emitted a byte-identical
feature cache (`7fd99f6e...f3a8`). Their 682-row CSVs are byte-identical to the
existing, unsubmitted `stage2_native_owned_v1.csv` (`40361ab2...06b8`), with
zero invalid predictions. The 13 organizer test clips without any nonvisual
raw unit retain the frozen semantic fallback. Missing files inside a declared
unit never fall back silently.

Six raw-package tests pass: missing, corrupt, short, reordered, extra-file, and
arbitrary-new-clip. The arbitrary smoke replaces every QA ID and both clip
paths and preserves the five-row prediction sequence exactly.

This is not approval to submit or redistribute. Three governance boundaries
remain explicit and are not counted as a technical pass: conservatively use
`2026-09-17 15:55 UTC` for the conflicting post-competition package deadline;
the Small final inference no-LLM rule remains distinct from the host's allowance
for coding assistants during development; and the upstream README's MIT badge,
the current non-commercial data/source license, and the finalist Apache-2.0
source requirement are separate layers requiring release review.
