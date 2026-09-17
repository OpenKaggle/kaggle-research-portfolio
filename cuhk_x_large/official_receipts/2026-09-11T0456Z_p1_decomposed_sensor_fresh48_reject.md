# P1 verb–object–temporal decomposition + sensor gating — REJECT receipt

- Terminal time: 2026-09-11T04:56:38Z (2026-09-11 12:56:38 CST)
- Decision: `REJECT_P1_NO_TEST_NO_SUBMISSION`
- Freshness: 48 QA rows / 48 clips with zero conflict against the frozen exposure/log/manifest union at inference start.
- Stratification: 12 rows in each action/object × subject-half stratum.
- Pairing: identical local Qwen3-VL-4B revision, Depth video, 1 FPS, 48 generation-token maximum, and temperature 0 for generic and decomposed arms.
- Network: disabled before model import/load; socket probe blocked.

Observed routed results were candidate 33/48 versus equal-budget generic 12/48, net +21. Action was +3, object +18, subject halves +11/+10, and worst-subject delta was 0. However, the frozen gate required zero invalids. Generic produced 28/48 invalid answer parses; the decomposed arm produced 1/48 invalid answer and 1/48 invalid evidence schema. The apparently large gain is therefore confounded by comparator format failure and is not promotable.

Artifacts:

- `reports/p1_decomposed_sensor_fresh48_v1_protocol.json` — SHA256 `e547c24f90fa412b763fee8437975d58bd1c7cd68fe50a5368d14e60e0ee89c5`
- `artifacts/manifests/p1_decomposed_sensor_fresh48_v1.csv` — SHA256 `a829fece2c2ed85f0ba59a2f6765c8dc767542e3153c35bdc4dd8d37486323e5`
- `reports/p1_decomposed_sensor_fresh48_v1_validation.json` — SHA256 `daec1dbe0730f38dc277c8c997e92cca794bf1d06f4d0ea41ffeee971d69b8f8`
- `artifacts/vlm/p1_decomposed_sensor_fresh48_v1.jsonl` — SHA256 `d6916e14aad5bac523ff062b6a8bfe5d4b178b8e3e12e33365baf3b24370dbd8`
- `reports/vlm_exposure_registry.jsonl` — the entire screen is now ineligible for future fresh evidence.

No prompt edit, parser relaxation, test inference, candidate mutation, or leaderboard probe follows this failure. The already qualified Stage2-native core remains unchanged.
