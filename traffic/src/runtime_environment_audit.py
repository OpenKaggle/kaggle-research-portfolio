#!/usr/bin/env python3
"""Verify the pinned Python environment and every campaign entry-point capability."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import resource
import subprocess
import sys
import tempfile
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path


LOCK_LINE = re.compile(r"^(?P<name>[A-Za-z0-9_.-]+)==(?P<version>[^\s]+)$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _peak_memory_mb() -> float:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return float(raw / (1024 * 1024) if platform.system() == "Darwin" else raw / 1024)


def normalize_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_requirements_lock(path: Path) -> dict[str, str]:
    packages: dict[str, str] = {}
    for line_number, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = LOCK_LINE.fullmatch(line)
        if not match:
            raise ValueError(f"requirements lock line {line_number} is not an exact pin")
        name = normalize_package_name(match.group("name"))
        if name in packages:
            raise ValueError(f"duplicate locked package: {name}")
        packages[name] = match.group("version")
    return packages


def run(traffic_root: Path, config_path: Path, output_root: Path) -> dict[str, object]:
    started = time.perf_counter()
    if output_root.exists():
        raise ValueError("runtime audit output root already exists; use a new path")
    config = json.loads(config_path.read_text())
    lock_path = traffic_root / config["requirements_lock_path"]
    errors: list[str] = []
    capability_rows: list[dict[str, str]] = []

    def capability(name: str, operation) -> None:
        try:
            detail = str(operation())
        except Exception as error:  # capability failures belong in the receipt
            errors.append(f"{name}: {type(error).__name__}: {error}")
            capability_rows.append({"capability": name, "status": "FAIL", "detail": str(error)})
        else:
            capability_rows.append({"capability": name, "status": "PASS", "detail": detail})

    actual_python = {
        "implementation": platform.python_implementation(),
        "version": platform.python_version(),
    }
    if actual_python != config["python"]:
        errors.append(f"Python contract mismatch: expected {config['python']}, got {actual_python}")
    actual_pip = importlib.metadata.version("pip")
    if actual_pip != config["pip_version"]:
        errors.append(f"pip contract mismatch: expected {config['pip_version']}, got {actual_pip}")

    lock_sha = _sha256(lock_path)
    if lock_sha != config["requirements_lock_sha256"]:
        errors.append("requirements.lock SHA mismatch")
    locked = parse_requirements_lock(lock_path)
    expected_packages = {
        normalize_package_name(name): version
        for group in (config["direct_packages"], config["transitive_packages"])
        for name, version in group.items()
    }
    if locked != expected_packages:
        errors.append("requirements.lock contents do not exactly match the package contract")
    actual_packages: dict[str, str] = {}
    for name, expected in expected_packages.items():
        try:
            actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            actual = "MISSING"
        actual_packages[name] = actual
        if actual != expected:
            errors.append(f"package mismatch for {name}: expected {expected}, got {actual}")

    os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")
    import numpy as np
    import pandas as pd
    import psutil
    from scipy.optimize import nnls
    from sklearn.ensemble import HistGradientBoostingRegressor

    numpy_config = np.__config__.show(mode="dicts")
    build_dependencies = numpy_config.get("Build Dependencies", {})
    actual_platform = {
        "system": platform.system(),
        "machine": platform.machine(),
        "numpy_blas": build_dependencies.get("blas", {}).get("name"),
        "numpy_lapack": build_dependencies.get("lapack", {}).get("name"),
    }
    if actual_platform != config["platform"]:
        errors.append(f"numerical platform mismatch: expected {config['platform']}, got {actual_platform}")

    capability(
        "numpy_finite_array",
        lambda: "finite float64 arithmetic"
        if np.isfinite(np.array([1.0, 2.0], dtype=np.float64)).all()
        else (_ for _ in ()).throw(ValueError("nonfinite NumPy smoke result")),
    )

    def parquet_roundtrip() -> str:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "smoke.parquet"
            expected = pd.DataFrame({"panel": ["P1", "P2"], "value": [1.25, 2.5]})
            expected.to_parquet(path, index=False, engine="pyarrow")
            actual = pd.read_parquet(path, engine="pyarrow")
            if not actual.equals(expected):
                raise ValueError("Pandas/PyArrow roundtrip changed values or dtypes")
        return "Pandas/PyArrow value-and-dtype roundtrip"

    capability("pandas_pyarrow_roundtrip", parquet_roundtrip)

    def scipy_nnls() -> str:
        solution, residual = nnls(np.eye(2), np.array([1.0, 2.0]))
        if residual != 0.0 or not np.array_equal(solution, np.array([1.0, 2.0])):
            raise ValueError("SciPy NNLS smoke solution mismatch")
        return "exact nonnegative identity solve"

    capability("scipy_nonnegative_least_squares", scipy_nnls)

    def sklearn_histogram() -> str:
        features = np.arange(16, dtype=np.float64).reshape(-1, 1)
        target = np.sin(features[:, 0] / 3.0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = HistGradientBoostingRegressor(max_iter=3, random_state=0).fit(features, target)
        prediction = model.predict(features)
        if prediction.shape != target.shape or not np.isfinite(prediction).all():
            raise ValueError("scikit-learn histogram booster returned invalid predictions")
        return "deterministic finite HistGradientBoostingRegressor smoke fit"

    capability("sklearn_hist_gradient_boosting", sklearn_histogram)
    def psutil_sampling() -> str:
        if psutil.Process().memory_info().rss <= 0:
            raise ValueError("nonpositive RSS")
        return "positive current-process RSS sampled"

    capability("psutil_process_sampling", psutil_sampling)

    run_path = traffic_root / "run.py"

    def entrypoint_help() -> str:
        for command in config["entrypoint_commands"]:
            result = subprocess.run(
                [sys.executable, str(run_path), command, "--help"],
                cwd=traffic_root.parent,
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0 or f"usage: run.py {command}" not in result.stdout:
                raise ValueError(f"entry point unavailable: {command}")
        return f"{len(config['entrypoint_commands'])} command help contracts"

    capability("campaign_entrypoints", entrypoint_help)

    test_count = 0

    def unittest_suite() -> str:
        nonlocal test_count
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                str(traffic_root / "tests"),
                "-v",
            ],
            cwd=traffic_root.parent,
            text=True,
            capture_output=True,
            check=False,
        )
        combined = result.stdout + "\n" + result.stderr
        match = re.search(r"Ran (\d+) tests?", combined)
        test_count = int(match.group(1)) if match else 0
        if result.returncode != 0 or test_count < config["minimum_unittests"] or "\nOK\n" not in combined:
            raise ValueError(
                f"unit suite failed or incomplete: exit={result.returncode} tests={test_count}"
            )
        return f"{test_count} tests passed"

    capability("full_unittest_suite", unittest_suite)
    observed_capabilities = {row["capability"] for row in capability_rows if row["status"] == "PASS"}
    if not set(config["required_capabilities"]).issubset(observed_capabilities):
        errors.append("one or more required runtime capabilities did not pass")
    official_head = subprocess.check_output(
        ["git", "-C", str(traffic_root / "official"), "rev-parse", "HEAD"], text=True
    ).strip()
    if official_head != config["official_code_commit"]:
        errors.append("official code commit mismatch")

    output_root.mkdir(parents=True)
    capability_path = output_root / "runtime_capabilities.csv"
    with capability_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["capability", "status", "detail"])
        writer.writeheader()
        writer.writerows(capability_rows)
    receipt: dict[str, object] = {
        "status": "VALID" if not errors else "FAIL",
        "experiment": config["version"].replace("_contract_", "_audit_"),
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "errors": errors,
        "python": actual_python,
        "pip_version": actual_pip,
        "packages": actual_packages,
        "platform": actual_platform,
        "entrypoint_commands_verified": len(config["entrypoint_commands"]),
        "capabilities_passed": sum(row["status"] == "PASS" for row in capability_rows),
        "capabilities_failed": sum(row["status"] == "FAIL" for row in capability_rows),
        "unittests_passed": test_count,
        "official_code_commit": official_head,
        "information_boundary": {
            "competition_data_read": False,
            "submission_artifact_read": False,
            "hidden_label_or_metric_read": False,
            "external_action_performed": False,
        },
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": _peak_memory_mb(),
        "inputs": {
            config_path.name: _sha256(config_path),
            config["requirements_lock_path"]: lock_sha,
            "run.py": _sha256(run_path),
            "src/runtime_environment_audit.py": _sha256(Path(__file__).resolve()),
        },
        "outputs": {capability_path.name: _sha256(capability_path)},
        "decision": "PINNED_RUNTIME_READY_FOR_REPRODUCTION",
    }
    receipt_path = output_root / "runtime_environment_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traffic-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "config" / "runtime_environment_contract_v1.json",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    receipt = run(args.traffic_root.resolve(), args.config.resolve(), args.output_root.resolve())
    if receipt["status"] != "VALID":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
