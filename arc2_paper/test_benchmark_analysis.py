#!/usr/bin/env python3
"""Small end-to-end regression for benchmark and paired-oracle analysis."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def main() -> None:
    arc_root = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="arc2-benchmark-analysis-") as raw:
        run_dir = Path(raw)
        challenges = {
            "0a1b2c3d": {
                "train": [{"input": [[0]], "output": [[1]]}],
                "test": [{"input": [[0]]}],
            },
            "1a2b3c4d": {
                "train": [{"input": [[0]], "output": [[2]]}],
                "test": [{"input": [[0]]}],
            },
        }
        solutions = {"0a1b2c3d": [[[1]]], "1a2b3c4d": [[[2]]]}
        anchor = {
            "0a1b2c3d": [{"attempt_1": [[1]], "attempt_2": [[0]]}],
            "1a2b3c4d": [{"attempt_1": [[0]], "attempt_2": [[1]]}],
        }
        method = {
            "0a1b2c3d": [{"attempt_1": [[1]], "attempt_2": [[0]]}],
            "1a2b3c4d": [{"attempt_1": [[0]], "attempt_2": [[2]]}],
        }
        write(run_dir / "benchmark_challenges.json", challenges)
        write(run_dir / "benchmark_solutions.json", solutions)
        for name in ("nvarc_kgmon.json", "nvarc_portfolio.json", "nvarc_full_probmul_3.json"):
            write(run_dir / name, anchor)
        write(run_dir / "trm_submission_final.json", method)
        write(run_dir / "submission.json", method)

        analyzed = subprocess.run(
            [sys.executable, str(arc_root / "analyze_kaggle_benchmark.py"), str(run_dir)],
            check=True,
            capture_output=True,
            text=True,
        )
        summary = json.loads(analyzed.stdout)
        assert summary["anchor_pass2"] == 1
        assert summary["method_pass2"] == 2
        assert summary["oracle_pool_pass2"] == 2
        assert summary["development_gate"]["passes"] is True

        paired = subprocess.run(
            [
                sys.executable,
                str(arc_root / "paper/tools/analyze_paired_results.py"),
                str(run_dir / "analysis/paired_results.csv"),
                "--bootstrap-replicates",
                "1000",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        paired_summary = json.loads(paired.stdout)
        assert paired_summary["oracle_pool_rate"] == 1.0
        assert paired_summary["oracle_gap_recovery"] == 1.0
    print("benchmark analysis regression passed")


if __name__ == "__main__":
    main()
