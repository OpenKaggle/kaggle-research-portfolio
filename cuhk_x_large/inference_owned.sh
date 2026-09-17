#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$BASE_DIR/../.venv/bin/python}"
SENSOR_ROOT="$BASE_DIR/data/raw/nonvisual/LMT_(IMU,Radar,Skeleton)"
INPUT_QA="$BASE_DIR/data/raw/kaggle/test_qa.csv"
SAMPLE_ORDER="$BASE_DIR/data/raw/kaggle/sample_submission.csv"
OUTPUT="$BASE_DIR/candidates/stage2_native_owned_raw_v1.csv"
WORK_DIR="$BASE_DIR/artifacts/dry_runs/stage2_native_owned_raw_v1"
MANIFEST=""
REQUIRE_ALL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sensor-root) SENSOR_ROOT="$2"; shift 2 ;;
    --input-qa) INPUT_QA="$2"; shift 2 ;;
    --sample-order) SAMPLE_ORDER="$2"; shift 2 ;;
    --no-sample-order) SAMPLE_ORDER=""; shift ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --work-dir) WORK_DIR="$2"; shift 2 ;;
    --manifest) MANIFEST="$2"; shift 2 ;;
    --require-all-clips) REQUIRE_ALL=1; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "$WORK_DIR" "$(dirname "$OUTPUT")"
export PYTHONHASHSEED=0
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export NO_PROXY='*'
export no_proxy='*'
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

extract_args=(
  "$PYTHON_BIN" "$BASE_DIR/scripts/extract_owned_raw_features_v1.py"
  --sensor-root "$SENSOR_ROOT"
  --input-qa "$INPUT_QA"
  --output "$WORK_DIR/nonvisual_features.npz"
  --report "$WORK_DIR/raw_feature_report.json"
  --require-manifest
  --allow-manifest-unlisted-clips-as-all-missing
)
if [[ -n "$MANIFEST" ]]; then
  extract_args+=(--manifest "$MANIFEST")
fi
if [[ "$REQUIRE_ALL" -eq 1 ]]; then
  extract_args+=(--require-all-clips)
fi
"${extract_args[@]}"

build_args=(
  "$PYTHON_BIN" "$BASE_DIR/scripts/build_stage2_native_candidate_v1.py"
  --input-qa "$INPUT_QA"
  --features "$WORK_DIR/nonvisual_features.npz"
  --output "$OUTPUT"
  --report "$WORK_DIR/candidate_report.json"
)
if [[ -n "$SAMPLE_ORDER" ]]; then
  build_args+=(--sample-order "$SAMPLE_ORDER")
fi
"${build_args[@]}"

echo "Owned raw-input candidate: $OUTPUT"
