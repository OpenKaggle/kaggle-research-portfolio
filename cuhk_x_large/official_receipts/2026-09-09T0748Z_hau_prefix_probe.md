# HAU visual prefix and rejection receipt

Recorded: 2026-09-09 07:48 UTC / 2026-09-09 15:48 BJT

- Official HAU ZIP prefix: `100663296 / 3674779437` bytes
- Prefix SHA-256: `dd55b53b944ec60e1f45a7dd5ae166e82674152465fd0b8fb5cc99c6c36ff138`
- Stop reason: Google Drive quota after three complete 32 MiB ranges
- Recovered: 85 CRC-checked videos, 22 training units
- Subject coverage: only `user8`
- Manifest SHA-256: `95fbe034dc95ff29a2b8cc00f1dc7d97eea4f63cecf2aca25c36bb8c4d9e336a`

Bounded zero-shot results:

- HAU single fixed probe: 4/8 (`0.50`)
- HAU emotion fixed probe: 4/8 (`0.50`)
- HAU emotion all recoverable rows: 7/22 (`0.3181818182`)
- Emotion sensor/VLM agreement: 6 rows, only 1 correct

The prefix has no subject diversity and the complete emotion result does not
support an agreement gate. Both HAU visual branches are rejected, no HAU test
prediction was generated, and submission `56116980` remains unchanged.
