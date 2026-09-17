from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.model_selection import GroupKFold


sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate_rogii_structured_selector as structured  # noqa: E402
import generate_rogii_candidate_paths as candgen  # noqa: E402
import train_rogii_segment_selector as segsel  # noqa: E402


REPORT_DIR = Path("reports")


def well_data_from_cache(
    wids: list[str],
    cache_dir: Path,
    segment_length: int,
    seed: int,
) -> dict[str, dict[str, object]]:
    structured_args = argparse.Namespace(
        split="train",
        include_segment_grid=True,
        include_dwt_bundle=True,
        include_pf_frontier=True,
        pf_particles=100,
        pf_frontier_seeds=4,
        seed=seed,
        cache_dir=cache_dir,
        refresh_cache=False,
    )
    out: dict[str, dict[str, object]] = {}
    for wid in wids:
        hw, tw = candgen.load_well(candgen.TRAIN, wid)
        ctx = candgen.hidden_context(hw)
        cache_path = structured.cache_path(structured_args, wid)
        if not cache_path.exists():
            raise FileNotFoundError(
                f"missing cached candidates for {wid}: {cache_path}. "
                "Run train_rogii_segment_selector.py once to populate cache."
            )
        with np.load(cache_path, allow_pickle=True) as data:
            names = data["names"].astype(str).tolist()
            families = data["families"].astype(str).tolist()
            tvt = data["tvt"].astype(np.float64)
        hidden_idx = np.asarray(ctx["hidden_idx"], dtype=int)
        out[wid] = {
            "names": names,
            "families": families,
            "tvt": tvt,
            "c": tvt + hw["Z"].to_numpy(float)[hidden_idx][None, :],
            "y": hw["TVT"].to_numpy(float)[hidden_idx],
            "z": hw["Z"].to_numpy(float)[hidden_idx],
            "segments": [
                (start, min(len(hidden_idx), start + segment_length))
                for start in range(0, len(hidden_idx), segment_length)
            ],
        }
    return out


def topn_mask(scores: pd.Series, frame: pd.DataFrame, n: int) -> np.ndarray:
    tmp = frame[["well", "segment_id"]].copy()
    tmp["_score"] = scores.to_numpy(float)
    keep_idx = (
        tmp.sort_values(["well", "segment_id", "_score"])
        .groupby(["well", "segment_id"], sort=False)
        .head(n)
        .index
    )
    mask = np.zeros(len(frame), dtype=bool)
    positions = frame.index.get_indexer(keep_idx)
    mask[positions[positions >= 0]] = True
    return mask


def candidate_recall(frame: pd.DataFrame, score_col: str, top_ns: list[int]) -> pd.DataFrame:
    rows = []
    ordered = frame.sort_values(["well", "segment_id", score_col])
    segment_rows = frame.groupby(["well", "segment_id"]).segment_rows.first()
    for top_n in top_ns:
        top = ordered.groupby(["well", "segment_id"], sort=False).head(top_n)
        best = top.groupby(["well", "segment_id"]).target_rmse.min()
        rows.append(
            {
                "top_n": top_n,
                "reachable_rmse": float(
                    np.sqrt(np.average(best.to_numpy(float) ** 2, weights=segment_rows.loc[best.index]))
                ),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features-in", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--first-target", choices=["rank"], default="rank")
    parser.add_argument(
        "--second-target",
        choices=["rank", "relative_rmse", "log_relative_rmse", "log_rmse"],
        default="relative_rmse",
    )
    parser.add_argument("--shortlist", type=int, default=64)
    parser.add_argument("--top-k", type=int, default=32)
    parser.add_argument("--n-estimators-first", type=int, default=350)
    parser.add_argument("--n-estimators-second", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20260606)
    parser.add_argument("--cache-dir", type=Path, default=REPORT_DIR / "rogii_candidate_cache")
    parser.add_argument(
        "--oof-out",
        type=Path,
        default=REPORT_DIR / "rogii_two_stage_segment_oof50.parquet",
    )
    parser.add_argument(
        "--by-well-out",
        type=Path,
        default=REPORT_DIR / "rogii_two_stage_segment_by_well50.csv",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=REPORT_DIR / "rogii_two_stage_segment_summary50.csv",
    )
    parser.add_argument(
        "--recall-out",
        type=Path,
        default=REPORT_DIR / "rogii_two_stage_segment_recall50.csv",
    )
    args = parser.parse_args()

    features = pd.read_parquet(args.features_in)
    if args.limit:
        keep_wells = features["well"].drop_duplicates().head(args.limit)
        features = features[features["well"].isin(keep_wells)].reset_index(drop=True)
    X, categorical = segsel.design_matrix(features, use_candidate_category=True)
    y_first = segsel.regression_target(features, args.first_target)
    y_second = segsel.regression_target(features, args.second_target)
    groups = features["well"].to_numpy(str)
    wids = features["well"].drop_duplicates().tolist()
    well_data = well_data_from_cache(wids, args.cache_dir, 128, args.seed)

    first_scores = np.full(len(features), np.nan, dtype=float)
    second_scores = np.full(len(features), np.nan, dtype=float)
    shortlisted = np.zeros(len(features), dtype=bool)
    gkf = GroupKFold(n_splits=min(args.folds, len(wids)))
    for fold, (train_idx, valid_idx) in enumerate(gkf.split(X, y_first, groups), start=1):
        first = LGBMRegressor(
            objective="regression",
            learning_rate=0.035,
            n_estimators=args.n_estimators_first,
            num_leaves=31,
            min_child_samples=30,
            subsample=0.9,
            colsample_bytree=0.85,
            random_state=args.seed + fold,
            verbose=-1,
        )
        first.fit(
            X.iloc[train_idx],
            y_first[train_idx],
            sample_weight=features.iloc[train_idx]["segment_rows"].to_numpy(float),
            categorical_feature=categorical,
        )
        train_first = first.predict(X.iloc[train_idx])
        valid_first = first.predict(X.iloc[valid_idx])
        first_scores[valid_idx] = valid_first

        train_frame = features.iloc[train_idx].reset_index(drop=True)
        valid_frame = features.iloc[valid_idx].reset_index(drop=True)
        train_short = topn_mask(pd.Series(train_first), train_frame, args.shortlist)
        valid_short = topn_mask(pd.Series(valid_first), valid_frame, args.shortlist)
        train_short_idx = train_idx[train_short]
        valid_short_idx = valid_idx[valid_short]
        shortlisted[valid_short_idx] = True

        second = LGBMRegressor(
            objective="regression",
            learning_rate=0.025,
            n_estimators=args.n_estimators_second,
            num_leaves=31,
            min_child_samples=15,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=args.seed + 100 + fold,
            verbose=-1,
        )
        second.fit(
            X.iloc[train_short_idx],
            y_second[train_short_idx],
            sample_weight=features.iloc[train_short_idx]["segment_rows"].to_numpy(float),
            categorical_feature=categorical,
        )
        second_scores[valid_short_idx] = second.predict(X.iloc[valid_short_idx])
        print(
            f"fold {fold}/{gkf.n_splits} done; "
            f"train_short={len(train_short_idx)} valid_short={len(valid_short_idx)}",
            flush=True,
        )

    scored = features.copy()
    scored["first_score"] = first_scores
    scored["second_score"] = second_scores
    scored["shortlisted"] = shortlisted
    scored["pred_score"] = np.where(shortlisted, second_scores, np.inf)

    result_rows: list[dict[str, object]] = []
    dp_configs = [
        (0.00, 0.00, 0.00),
        (0.02, 0.05, 0.02),
        (0.05, 0.10, 0.05),
        (0.10, 0.20, 0.10),
    ]
    for wid, group in scored.groupby("well", sort=False):
        data = well_data[wid]
        valid_group = group[group["shortlisted"]].copy()
        methods: list[tuple[str, list[int]]] = [
            ("two_stage_independent", segsel.decode_independent(valid_group))
        ]
        for jump, slope, switch in dp_configs:
            selected = segsel.decode_dp(
                valid_group,
                data,
                args.top_k,
                jump,
                slope,
                switch,
            )
            methods.append((f"two_stage_dp_j{jump:g}_s{slope:g}_x{switch:g}", selected))
        for method, selected in methods:
            pred = segsel.stitch_prediction(selected, data)
            result_rows.append(
                {
                    "well": wid,
                    "method": method,
                    "rmse": candgen.rmse(pred, np.asarray(data["y"], dtype=float)),
                    "hidden_rows": len(data["y"]),
                    "switches": int(np.sum(np.diff(selected) != 0)),
                }
            )

    args.oof_out.parent.mkdir(parents=True, exist_ok=True)
    scored.to_parquet(args.oof_out, index=False)
    by_well = pd.DataFrame(result_rows)
    by_well.to_csv(args.by_well_out, index=False)
    summary = segsel.summarize_methods(result_rows)
    summary.to_csv(args.summary_out, index=False)
    recall = candidate_recall(scored, "pred_score", [1, 2, 4, 8, 16, 32, 64])
    recall.to_csv(args.recall_out, index=False)
    print(summary.to_string(index=False))
    print(recall.to_string(index=False))
    print(f"wrote {args.oof_out}")
    print(f"wrote {args.by_well_out}")
    print(f"wrote {args.summary_out}")
    print(f"wrote {args.recall_out}")


if __name__ == "__main__":
    main()
