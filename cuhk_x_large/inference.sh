#!/usr/bin/env bash
set -euo pipefail

campaign_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$campaign_root"

python_bin="${CUHK_PYTHON:-../.venv/bin/python}"
if [[ ! -x "$python_bin" ]]; then
  echo "Python environment not found or not executable: $python_bin" >&2
  exit 1
fi

"$python_bin" scripts/reproduce_public_077777.py
"$python_bin" scripts/build_sensor_union_candidate.py
"$python_bin" scripts/build_visual_sensor_candidate.py
"$python_bin" scripts/build_hau_linked_single_consensus.py
"$python_bin" scripts/build_emotion_extratrees_rf_union.py

"$python_bin" scripts/validate_submission.py candidates/emotion_extratrees_rf_union_v1.csv
"$python_bin" scripts/validate_submission.py candidates/nonvisual_sensor_union_v1.csv

primary_sha="$(shasum -a 256 candidates/emotion_extratrees_rf_union_v1.csv | awk '{print $1}')"
fallback_sha="$(shasum -a 256 candidates/nonvisual_sensor_union_v1.csv | awk '{print $1}')"
expected_primary="3a76a36e6d3060979370f5b598e090c0e2436689d9eda6b17416ae8bc0aee3e4"
expected_fallback="a5d300381a79e751c08c03a36036cf56137121fc3f987832e64062b534204702"

if [[ "$primary_sha" != "$expected_primary" ]]; then
  echo "Primary candidate hash mismatch: $primary_sha" >&2
  exit 1
fi
if [[ "$fallback_sha" != "$expected_fallback" ]]; then
  echo "Fallback candidate hash mismatch: $fallback_sha" >&2
  exit 1
fi

echo "PASS primary=$primary_sha"
echo "PASS fallback=$fallback_sha"
echo "No network request or competition submission was performed."
