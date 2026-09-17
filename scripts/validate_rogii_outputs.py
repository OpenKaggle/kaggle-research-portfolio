from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_ROOT = Path("reports/kaggle_kernel_output")
DEFAULT_SAMPLE = Path("data/raw/rogii-wellbore-geology-prediction/sample_submission.csv")


def sha12(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def load_valid_submission(path: Path, sample: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    issues: list[str] = []
    try:
        df = pd.read_csv(path)
    except Exception as exc:  # pragma: no cover - diagnostic script
        return pd.DataFrame(), [f"read_error:{type(exc).__name__}"]

    if df.shape != sample.shape:
        issues.append(f"shape:{df.shape}")
    if list(df.columns) != list(sample.columns):
        issues.append(f"columns:{list(df.columns)}")
    if "id" in df and not df["id"].equals(sample["id"]):
        issues.append("id_order")
    if "tvt" not in df:
        issues.append("missing_tvt")
    else:
        tvt = pd.to_numeric(df["tvt"], errors="coerce")
        if not np.isfinite(tvt).all():
            issues.append("nonfinite")
        if float(tvt.std()) < 1e-9:
            issues.append("constant")
        # Visible public sample TVT predictions are around 10k-13k. Keep this as a
        # diagnostic warning, not a hard validator, because hidden ranges may differ.
        if float(tvt.max()) < 1000 or float(tvt.min()) < 1000:
            issues.append("suspicious_range")
        df["tvt"] = tvt
    return df, issues


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--sample", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument("--out", type=Path, default=Path("reports/rogii_output_validation.csv"))
    parser.add_argument("--pairs-out", type=Path, default=Path("reports/rogii_output_pairwise_rmse.csv"))
    args = parser.parse_args()

    sample = pd.read_csv(args.sample)
    rows: list[dict[str, object]] = []
    valid: dict[str, np.ndarray] = {}

    for path in sorted(args.root.glob("*/submission.csv")):
        name = path.parent.name
        df, issues = load_valid_submission(path, sample)
        row: dict[str, object] = {
            "name": name,
            "path": str(path),
            "sha12": sha12(path),
            "ok": not issues,
            "issues": ";".join(issues),
        }
        if "tvt" in df:
            tvt = df["tvt"].astype(float)
            row.update(
                {
                    "rows": len(df),
                    "min": float(tvt.min()),
                    "mean": float(tvt.mean()),
                    "max": float(tvt.max()),
                    "std": float(tvt.std()),
                }
            )
            if not issues:
                valid[name] = tvt.to_numpy(float)
        rows.append(row)

    report = pd.DataFrame(rows).sort_values(["ok", "name"], ascending=[False, True])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(args.out, index=False)

    pairs: list[dict[str, object]] = []
    names = sorted(valid)
    for i, left in enumerate(names):
        a = valid[left]
        for right in names[i + 1 :]:
            b = valid[right]
            diff = a - b
            pairs.append(
                {
                    "left": left,
                    "right": right,
                    "rmse": float(np.sqrt(np.mean(diff**2))),
                    "max_abs": float(np.max(np.abs(diff))),
                }
            )
    pd.DataFrame(pairs).sort_values("rmse").to_csv(args.pairs_out, index=False)

    print(f"Wrote {args.out} ({len(report)} outputs)")
    print(f"Wrote {args.pairs_out} ({len(pairs)} pairs)")
    print(report[["name", "ok", "issues", "min", "mean", "max", "std"]].to_string(index=False))


if __name__ == "__main__":
    main()
