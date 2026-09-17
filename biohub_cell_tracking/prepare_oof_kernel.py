#!/usr/bin/env python3
"""Build the private Kaggle kernel for budgeted embryo-isolated OOF."""

from __future__ import annotations

import argparse
import json
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PROTOCOL_PATH = ROOT / "artifacts" / "budgeted_embryo_oof.json"
OFFICIAL_METRICS_PATH = ROOT / "official_repo" / "src" / "tracking_cellmot" / "metrics.py"
OFFICIAL_DIVISION_METRICS_PATH = ROOT / "official_repo" / "src" / "tracking_cellmot" / "division_metrics.py"
KERNEL_DIR = ROOT / "kernels" / "biohub_budgeted_embryo_oof"
KERNEL_FILE = KERNEL_DIR / "biohub-budgeted-embryo-oof.py"
METADATA_FILE = KERNEL_DIR / "kernel-metadata.json"

TEMPLATE = r'''"""Budgeted two-fold embryo-isolated OOF for Biohub cell tracking."""

from __future__ import annotations

import contextlib
import gc
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


PROTOCOL = json.loads(__PROTOCOL_JSON__)
SOURCE_PROTOCOL_SHA256 = "__PROTOCOL_SOURCE_SHA256__"
OFFICIAL_METRICS_SOURCE = __OFFICIAL_METRICS_SOURCE__
OFFICIAL_DIVISION_METRICS_SOURCE = __OFFICIAL_DIVISION_METRICS_SOURCE__
OFFICIAL_METRIC_COMMIT = "075fc5f5a52d11077f9dc2b074644618f26939e2"
EXPECTED_OFFICIAL_METRIC_SHA256 = {
    "metrics.py": "cfdd596e3f8909cca14db0682889738b19ff75c3808b3773175aba9367ca7444",
    "division_metrics.py": "0635c38621a38f1eb4b55a302b4a817a88e9094930dfc2dab16faeeee60f4dc9",
}
WORKING = Path("/kaggle/working")
INPUT = Path("/kaggle/input")
TRAIN_DIR = INPUT / "competitions" / "biohub-cell-tracking-during-development" / "train"
REPO_DIR = WORKING / "budgeted_oof_repo"
METHOD = "__METHOD__"
EXPECTED_SUPPORT_MANIFEST_SHA256 = "7f01c0b2f9491606a1b543339e072230e25317d9c70fb9a18aea59e002a995eb"
EXPECTED_SOURCE_SHA256 = {
    "scripts/train_unet_transformer.py": "c4f6317736bb3bb1ec8f3f6e9a6d935a463e3f0f1f685481b2d13218d35dc9ea",
    "scripts/predict_unet_transformer.py": "c44e771ba5980b820f93091e03a303c25dfe8f3232e501f54dc9565731c234b9",
    "scripts/evaluate.py": "614813cc51c3581c6ccda4bb20725a19da8ecac4a27620654bfca58319cffa3c",
}
PACKAGE_NAMES = [
    "tracksdata", "zarr", "pyscipopt", "geff", "geff-spec", "ilpy",
    "polars", "polars-runtime-32", "blosc2", "dask", "imagecodecs",
    "pyarrow", "rustworkx", "sqlalchemy", "donfig", "google-crc32c",
    "numcodecs",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def hash_names(names: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(names)).encode()).hexdigest()


def find_support_root() -> Path:
    matches = []
    for path in INPUT.rglob("ARTIFACT_MANIFEST.json"):
        if sha256(path) == EXPECTED_SUPPORT_MANIFEST_SHA256:
            matches.append(path.parent)
    if len(matches) != 1:
        raise RuntimeError(f"Expected one pinned support artifact, found {matches}")
    return matches[0]


class Tee:
    def __init__(self, stream, path: Path):
        self.stream = stream
        self.handle = path.open("w", encoding="utf-8")

    def write(self, value: str):
        self.stream.write(value)
        self.handle.write(value)
        self.handle.flush()
        return len(value)

    def flush(self):
        self.stream.flush()
        self.handle.flush()

    def close(self):
        self.handle.close()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    import numpy as np
    import torch

    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True, warn_only=True)


def score_predictions(prediction_dir: Path, holdout: list[str]) -> tuple[list[dict], dict]:
    import tracksdata as td
    from geff import GeffMetadata
    from biohub_tracking.metrics import evaluate, node_recall, per_sample_metrics, summarise

    rows = []
    details = []
    for name in holdout:
        pred_result = td.graph.IndexedRXGraph.from_geff(prediction_dir / f"{name}.geff")
        gt_result = td.graph.IndexedRXGraph.from_geff(TRAIN_DIR / f"{name}.geff")
        pred = pred_result[0] if isinstance(pred_result, tuple) else pred_result
        gt = gt_result[0] if isinstance(gt_result, tuple) else gt_result
        counts = evaluate(
            pred, gt, scale=(1.625, 0.40625, 0.40625), max_distance=7.0
        )
        recall = node_recall(pred, gt) if pred.num_nodes() and pred.num_edges() else 0.0
        meta = GeffMetadata.read(TRAIN_DIR / f"{name}.geff")
        n_total = float((meta.extra or {}).get("estimated_number_of_nodes", float("nan")))
        row = per_sample_metrics(counts, n_total, recall)
        rows.append(row)
        details.append({"dataset": name, **row})
        print(
            f"OOF {name}: edge={counts.edge_tp}/{counts.edge_fp}/{counts.edge_fn} "
            f"division={counts.division_tp}/{counts.division_fp}/{counts.division_fn} "
            f"node_recall={recall:.6f}",
            flush=True,
        )
    return details, summarise(rows)


def main() -> None:
    started = time.time()
    if not TRAIN_DIR.is_dir():
        raise FileNotFoundError(TRAIN_DIR)
    support_root = find_support_root()
    print("Pinned support root:", support_root, flush=True)
    subprocess.check_call(
        [
            sys.executable, "-m", "pip", "install", "--no-index",
            "--find-links", str(support_root / "wheels"), *PACKAGE_NAMES,
        ]
    )

    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
    shutil.copytree(support_root / "repo", REPO_DIR)
    for relative, expected in EXPECTED_SOURCE_SHA256.items():
        actual = sha256(REPO_DIR / relative)
        if actual != expected:
            raise RuntimeError(f"Source checksum mismatch for {relative}: {actual}")
    metric_dir = REPO_DIR / "src" / "biohub_tracking"
    (metric_dir / "metrics.py").write_text(OFFICIAL_METRICS_SOURCE, encoding="utf-8")
    (metric_dir / "division_metrics.py").write_text(
        OFFICIAL_DIVISION_METRICS_SOURCE, encoding="utf-8"
    )
    for name, expected in EXPECTED_OFFICIAL_METRIC_SHA256.items():
        actual = sha256(metric_dir / name)
        if actual != expected:
            raise RuntimeError(f"Official metric checksum mismatch for {name}: {actual}")

    scripts_dir = REPO_DIR / "scripts"
    sys.path[:0] = [str(REPO_DIR / "src"), str(scripts_dir)]
    os.chdir(REPO_DIR)

    available = sorted(path.name.removesuffix(".zarr") for path in TRAIN_DIR.glob("*.zarr"))
    by_embryo = {
        embryo: sorted(name for name in available if name.startswith(f"{embryo}_"))
        for embryo in ("44b6", "6bba")
    }
    expected_all_hashes = {
        "44b6": "9a38aeec8ed9ac8433e480b854ef185b4886cb839a5dc1770e01cfc582113e42",
        "6bba": "bad2d65342f49bbf5adfc7005519430d029c78c65907fd6a2cb311da553698a5",
    }
    for embryo, expected in expected_all_hashes.items():
        actual = hash_names(by_embryo[embryo])
        if actual != expected:
            raise RuntimeError(f"Competition data inventory mismatch for {embryo}: {actual}")

    visible_test_copies = set(PROTOCOL["selection"]["visible_test_copies_excluded"])
    for fold in PROTOCOL["folds"]:
        train_set = set(fold["train"])
        monitor_set = set(fold["monitor"])
        holdout_set = set(fold["holdout"])
        if train_set & monitor_set or train_set & holdout_set or monitor_set & holdout_set:
            raise RuntimeError(f"Fold {fold['fold']} is not disjoint")
        if visible_test_copies & monitor_set or visible_test_copies & holdout_set:
            raise RuntimeError(f"Fold {fold['fold']} uses visible-test copies for evaluation")
        if not all(name.startswith(f"{fold['train_embryo']}_") for name in train_set | monitor_set):
            raise RuntimeError(f"Fold {fold['fold']} train/monitor embryo mismatch")
        if not all(name.startswith(f"{fold['validation_embryo']}_") for name in holdout_set):
            raise RuntimeError(f"Fold {fold['fold']} holdout embryo mismatch")

    training_splits = [
        {"split": fold["fold"], "train": fold["train"], "test": fold["monitor"]}
        for fold in PROTOCOL["folds"]
    ]
    inference_splits = [
        {"split": fold["fold"], "train": [], "test": fold["holdout"]}
        for fold in PROTOCOL["folds"]
    ]
    training_splits_path = REPO_DIR / "budgeted_oof_training_splits.json"
    inference_splits_path = REPO_DIR / "budgeted_oof_inference_splits.json"
    training_splits_path.write_text(json.dumps(training_splits, indent=2) + "\n")
    inference_splits_path.write_text(json.dumps(inference_splits, indent=2) + "\n")
    (WORKING / "budgeted_oof_protocol.json").write_text(
        json.dumps(PROTOCOL, indent=2) + "\n"
    )

    from train_unet_transformer import train
    from predict_unet_transformer import PredictConfig, predict

    fold_receipts = []
    all_detail_rows = []
    all_metric_rows = []
    for fold in PROTOCOL["folds"]:
        fold_index = int(fold["fold"])
        fold_started = time.time()
        seed_everything(int(fold["seed"]))
        train_log_path = WORKING / f"fold_{fold_index}_train.log"
        train_tee = Tee(sys.stdout, train_log_path)
        with contextlib.redirect_stdout(train_tee):
            model = train(
                data_dir=TRAIN_DIR,
                fold=fold_index,
                splits_file=training_splits_path,
                method=METHOD,
                n_epochs=int(PROTOCOL["training"]["epochs"]),
                lr=float(PROTOCOL["training"]["learning_rate"]),
                batch_size=int(PROTOCOL["training"]["batch_size"]),
                num_workers=4,
                unet_out_channels=32,
                unet_layers=[32, 64, 128],
                downsample=(1, 4, 4),
                det_loss_weight=1.0,
                det_neg_weight=0.01,
                seed=int(fold["seed"]),
                augmentations=[],
                window_size=2,
                pool_kernel_um=5.0,
                data_parallel=True,
            )
        train_tee.close()
        del model
        gc.collect()
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass

        weight_path = REPO_DIR / "weights" / METHOD / f"split_{fold_index}" / "edge_predictor_best.pth"
        if not weight_path.is_file():
            raise FileNotFoundError(weight_path)
        predict_log_path = WORKING / f"fold_{fold_index}_predict.log"
        predict_tee = Tee(sys.stdout, predict_log_path)
        predict_started = time.time()
        with contextlib.redirect_stdout(predict_tee):
            predict(
                data_dir=TRAIN_DIR,
                fold=fold_index,
                splits_file=inference_splits_path,
                weights_path=weight_path,
                cfg=PredictConfig(
                    det_threshold=0.965,
                    use_ilp=True,
                    ilp_edge_weight=-1.0,
                    ilp_appearance_weight=0.0,
                    ilp_disappearance_weight=2.0,
                    ilp_division_weight=1.0,
                ),
                method=METHOD,
                debug_video=None,
                unet_batch_size=4,
                video_slice=None,
                evaluate=False,
            )
        predict_tee.close()

        prediction_matches = sorted(
            REPO_DIR.glob(f"predictions/*/{METHOD}/split_{fold_index}")
        )
        if len(prediction_matches) != 1:
            raise RuntimeError(f"Expected one prediction directory, found {prediction_matches}")
        details, summary = score_predictions(prediction_matches[0], fold["holdout"])
        all_detail_rows.extend({"fold": fold_index, **row} for row in details)
        all_metric_rows.extend(details)
        train_text = train_log_path.read_text(encoding="utf-8")
        best_matches = re.findall(r"Best score \(acc\*recall\): ([0-9.]+)", train_text)
        fold_receipts.append(
            {
                "fold": fold_index,
                "seed": fold["seed"],
                "train_embryo": fold["train_embryo"],
                "holdout_embryo": fold["validation_embryo"],
                "train_datasets": len(fold["train"]),
                "monitor_datasets": len(fold["monitor"]),
                "holdout_datasets": len(fold["holdout"]),
                "monitor_best_acc_times_recall": float(best_matches[-1]) if best_matches else None,
                "holdout_summary": summary,
                "weights_sha256": sha256(weight_path),
                "train_log_sha256": sha256(train_log_path),
                "predict_log_sha256": sha256(predict_log_path),
                "prediction_seconds": time.time() - predict_started,
                "fold_seconds": time.time() - fold_started,
            }
        )
        partial = {
            "status": "running",
            "completed_folds": len(fold_receipts),
            "folds": fold_receipts,
            "per_sample": all_detail_rows,
        }
        (WORKING / "budgeted_oof_partial.json").write_text(
            json.dumps(partial, indent=2, allow_nan=True) + "\n"
        )

    from biohub_tracking.metrics import summarise
    combined_rows = [
        {key: value for key, value in row.items() if key not in {"dataset", "fold"}}
        for row in all_detail_rows
    ]
    receipt = {
        "status": "complete",
        "source_protocol_sha256": SOURCE_PROTOCOL_SHA256,
        "embedded_protocol_canonical_sha256": hashlib.sha256(
            json.dumps(PROTOCOL, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest(),
        "support_manifest_sha256": EXPECTED_SUPPORT_MANIFEST_SHA256,
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "official_metric_commit": OFFICIAL_METRIC_COMMIT,
        "official_metric_sha256": EXPECTED_OFFICIAL_METRIC_SHA256,
        "ground_truth_scope": "official train only",
        "competition_test_accessed": False,
        "visible_test_copies_used_for_monitor_or_holdout": False,
        "folds": fold_receipts,
        "combined_holdout_summary": summarise(combined_rows),
        "per_sample": all_detail_rows,
        "total_seconds": time.time() - started,
    }
    receipt_path = WORKING / "budgeted_oof_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, allow_nan=True) + "\n")
    print(json.dumps(receipt, indent=2, allow_nan=True), flush=True)


if __name__ == "__main__":
    main()
'''


def build_kernel(
    protocol_path: Path,
    kernel_dir: Path,
    kernel_id: str,
    title: str,
    code_file: str,
    method: str,
) -> tuple[Path, Path]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol_json = json.dumps(protocol, separators=(",", ":"), sort_keys=True)
    kernel_text = TEMPLATE.replace("__PROTOCOL_JSON__", repr(protocol_json))
    protocol_sha256 = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    kernel_text = kernel_text.replace("__PROTOCOL_SOURCE_SHA256__", protocol_sha256)
    kernel_text = kernel_text.replace("__METHOD__", method)
    kernel_text = kernel_text.replace(
        "__OFFICIAL_METRICS_SOURCE__",
        repr(OFFICIAL_METRICS_PATH.read_text(encoding="utf-8")),
    )
    kernel_text = kernel_text.replace(
        "__OFFICIAL_DIVISION_METRICS_SOURCE__",
        repr(OFFICIAL_DIVISION_METRICS_PATH.read_text(encoding="utf-8")),
    )
    kernel_file = kernel_dir / code_file
    metadata_file = kernel_dir / "kernel-metadata.json"
    metadata = {
        "id": kernel_id,
        "title": title,
        "code_file": kernel_file.name,
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": True,
        "enable_tpu": False,
        "enable_internet": False,
        "keywords": ["gpu", "cross-validation"],
        "dataset_sources": [
            "pilkwang/biohub-temporal-unet3d-seed314159-v1"
        ],
        "kernel_sources": [],
        "competition_sources": [
            "biohub-cell-tracking-during-development"
        ],
        "model_sources": [],
        "docker_image": "gcr.io/kaggle-private-byod/python@sha256:37c64f7dd9c54116ecd1bcc88817c5469b88387388fade02bfa8bf3fc647d461",
        "machine_shape": "NvidiaTeslaT4",
    }
    kernel_dir.mkdir(parents=True, exist_ok=True)
    kernel_file.write_text(kernel_text, encoding="utf-8")
    metadata_file.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return kernel_file, metadata_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=PROTOCOL_PATH)
    parser.add_argument("--kernel-dir", type=Path, default=KERNEL_DIR)
    parser.add_argument(
        "--kernel-id", default="jahyee/biohub-budgeted-embryo-oof-v1"
    )
    parser.add_argument("--title", default="Biohub Budgeted Embryo OOF V1")
    parser.add_argument("--code-file", default=KERNEL_FILE.name)
    parser.add_argument("--method", default="budgeted_embryo_oof_12ep")
    args = parser.parse_args()
    kernel_file, metadata_file = build_kernel(
        args.protocol,
        args.kernel_dir,
        args.kernel_id,
        args.title,
        args.code_file,
        args.method,
    )
    print(kernel_file)
    print(metadata_file)


if __name__ == "__main__":
    main()
