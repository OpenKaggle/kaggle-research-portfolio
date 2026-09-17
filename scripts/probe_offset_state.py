from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd


DATA = Path("data/raw/rogii-wellbore-geology-prediction")
TRAIN = DATA / "train"
REPORT_DIR = Path("reports")
OUT_WELLS = REPORT_DIR / "rogii_offset_state_probe_by_well.csv"
OUT_SUMMARY = REPORT_DIR / "rogii_offset_state_probe_summary.csv"


def rmse(a: np.ndarray, b: np.ndarray) -> float:
    m = np.isfinite(a) & np.isfinite(b)
    if not m.any():
        return math.nan
    return float(np.sqrt(np.mean((a[m] - b[m]) ** 2)))


def predict_cumsum(
    z: np.ndarray,
    tvt_known: np.ndarray,
    ps: int,
    offset: float,
    z_sign: float,
) -> np.ndarray:
    pred = np.empty(len(z) - ps - 1, dtype=float)
    last = float(tvt_known[ps])
    if len(pred) == 0:
        return pred
    # Align first hidden row with the step from PS to PS+1.
    dtvt = z_sign * np.diff(z[ps : ps + 1 + len(pred)]) + offset
    return last + np.cumsum(dtvt)


def one_well(path: Path) -> dict[str, float | str | int]:
    well = path.name.replace("__horizontal_well.csv", "")
    df = pd.read_csv(path)
    known_mask = df["TVT_input"].notna().to_numpy()
    if known_mask.sum() < 20 or known_mask.all():
        return {"well": well, "status": "skip", "rows": 0}
    ps = int(np.flatnonzero(known_mask)[-1])
    hidden = np.arange(ps + 1, len(df))
    if len(hidden) == 0:
        return {"well": well, "status": "skip", "rows": 0}

    z = df["Z"].to_numpy(float)
    tvt = df["TVT"].to_numpy(float)
    tvt_in = df["TVT_input"].to_numpy(float)
    known = np.arange(0, ps + 1)

    y = tvt[hidden]
    last = np.full(len(hidden), tvt_in[ps], dtype=float)

    dz_k = np.diff(z[known])
    dtvt_k = np.diff(tvt_in[known])
    ok = np.isfinite(dz_k) & np.isfinite(dtvt_k)

    # Tail offset is less stale, but noisier.
    tail_n = min(500, max(20, ok.sum()))
    dz_tail = dz_k[-tail_n:]
    dtvt_tail = dtvt_k[-tail_n:]
    ok_tail = np.isfinite(dz_tail) & np.isfinite(dtvt_tail)

    result: dict[str, float | str | int] = {
        "well": well,
        "status": "ok",
        "rows": int(len(hidden)),
        "last_rmse": rmse(last, y),
    }

    # Oracle offset quantifies how valuable a correct offset/state classifier could be.
    grid = np.linspace(-1.2, 1.2, 241)
    for name, z_sign in [("negdz", -1.0), ("posdz", 1.0)]:
        prefix_offset = float(np.nanmedian(dtvt_k[ok] - z_sign * dz_k[ok])) if ok.sum() else 0.0
        pred_prefix = predict_cumsum(z, tvt_in, ps, prefix_offset, z_sign)

        tail_offset = (
            float(np.nanmedian(dtvt_tail[ok_tail] - z_sign * dz_tail[ok_tail]))
            if ok_tail.sum()
            else prefix_offset
        )
        pred_tail = predict_cumsum(z, tvt_in, ps, tail_offset, z_sign)

        oracle_scores = []
        for off in grid:
            oracle_scores.append(rmse(predict_cumsum(z, tvt_in, ps, float(off), z_sign), y))
        best_i = int(np.nanargmin(oracle_scores))
        oracle_offset = float(grid[best_i])
        pred_oracle = predict_cumsum(z, tvt_in, ps, oracle_offset, z_sign)

        result[f"{name}_prefix_offset"] = prefix_offset
        result[f"{name}_tail_offset"] = tail_offset
        result[f"{name}_oracle_offset"] = oracle_offset
        result[f"{name}_prefix_offset_rmse"] = rmse(pred_prefix, y)
        result[f"{name}_tail_offset_rmse"] = rmse(pred_tail, y)
        result[f"{name}_oracle_offset_rmse"] = rmse(pred_oracle, y)

    return result


def weighted_rmse(rows: pd.DataFrame, col: str) -> float:
    ok = rows["status"].eq("ok") & rows[col].notna()
    if not ok.any():
        return math.nan
    weights = rows.loc[ok, "rows"].to_numpy(float)
    vals = rows.loc[ok, col].to_numpy(float)
    return float(np.sqrt(np.average(vals**2, weights=weights)))


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows = [one_well(p) for p in sorted(TRAIN.glob("*__horizontal_well.csv"))]
    df = pd.DataFrame(rows)
    df.to_csv(OUT_WELLS, index=False)
    summary = []
    metric_cols = [
        "last_rmse",
        "negdz_prefix_offset_rmse",
        "negdz_tail_offset_rmse",
        "negdz_oracle_offset_rmse",
        "posdz_prefix_offset_rmse",
        "posdz_tail_offset_rmse",
        "posdz_oracle_offset_rmse",
    ]
    for col in metric_cols:
        ok = df["status"].eq("ok") & df[col].notna()
        summary.append(
            {
                "metric": col,
                "weighted_rmse": weighted_rmse(df, col),
                "mean_well_rmse": float(df.loc[ok, col].mean()),
                "median_well_rmse": float(df.loc[ok, col].median()),
            }
        )
    out = pd.DataFrame(summary)
    out.to_csv(OUT_SUMMARY, index=False)
    print(out.to_string(index=False))
    print(f"wrote {OUT_WELLS}")
    print(f"wrote {OUT_SUMMARY}")


if __name__ == "__main__":
    main()
