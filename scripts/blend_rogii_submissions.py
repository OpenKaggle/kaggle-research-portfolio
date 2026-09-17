from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUBMISSIONS_DIR = PROJECT_ROOT / "submissions"
REPORTS_DIR = PROJECT_ROOT / "reports"


@dataclass(frozen=True)
class BlendInput:
    path: Path
    weight: float


def parse_input(spec: str) -> BlendInput:
    if "=" not in spec:
        raise argparse.ArgumentTypeError(
            f"Invalid input {spec!r}; expected path=weight."
        )
    raw_path, raw_weight = spec.split("=", 1)
    path = Path(raw_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / raw_path
    try:
        weight = float(raw_weight)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid weight in {spec!r}."
        ) from exc
    return BlendInput(path=path, weight=weight)


def load_submission(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    expected = ["id", "tvt"]
    if list(df.columns) != expected:
        raise ValueError(f"{path} has columns {list(df.columns)}; expected {expected}.")
    if df["id"].duplicated().any():
        raise ValueError(f"{path} contains duplicated ids.")
    return df


def build_blend(inputs: list[BlendInput]) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not inputs:
        raise ValueError("At least one --input is required.")

    loaded: list[tuple[BlendInput, pd.DataFrame]] = [
        (item, load_submission(item.path)) for item in inputs
    ]
    base_ids = loaded[0][1]["id"]
    for item, df in loaded[1:]:
        if not df["id"].equals(base_ids):
            raise ValueError(f"id mismatch for {item.path}.")

    total_weight = sum(item.weight for item, _ in loaded)
    if total_weight == 0:
        raise ValueError("Sum of weights must be non-zero.")

    blend = loaded[0][1][["id"]].copy()
    weighted = pd.Series(0.0, index=blend.index)
    audit_rows: list[dict[str, object]] = []
    for item, df in loaded:
        norm_weight = item.weight / total_weight
        weighted += df["tvt"] * norm_weight
        audit_rows.append(
            {
                "file": str(item.path.relative_to(PROJECT_ROOT)),
                "raw_weight": item.weight,
                "normalized_weight": norm_weight,
                "rows": len(df),
                "mean": float(df["tvt"].mean()),
                "std": float(df["tvt"].std()),
                "min": float(df["tvt"].min()),
                "max": float(df["tvt"].max()),
            }
        )
    blend["tvt"] = weighted
    audit = pd.DataFrame(audit_rows)
    return blend, audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        action="append",
        type=parse_input,
        required=True,
        help="Input submission and weight in the form path=weight.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output CSV path, relative to project root unless absolute.",
    )
    parser.add_argument(
        "--audit-output",
        help="Optional audit CSV path, relative to project root unless absolute.",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / args.output
    audit_path = None
    if args.audit_output:
        audit_path = Path(args.audit_output)
        if not audit_path.is_absolute():
            audit_path = PROJECT_ROOT / args.audit_output

    blend, audit = build_blend(args.input)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    blend.to_csv(output_path, index=False)

    if audit_path is not None:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit.to_csv(audit_path, index=False)

    print(
        f"Wrote {output_path} rows={len(blend)} "
        f"mean={blend['tvt'].mean():.6f} std={blend['tvt'].std():.6f}"
    )
    print(audit.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
