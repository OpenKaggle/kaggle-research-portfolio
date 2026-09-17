#!/usr/bin/env python3
"""Persist a compact receipt from Kaggle's official kernel status and log APIs."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def status_name(status: object) -> str:
    name = getattr(status, "name", None)
    if isinstance(name, str):
        return name
    return str(status).rsplit(".", 1)[-1]


def build_receipt(
    kernel: str,
    status: object,
    failure_message: str | None,
    logs: str | None,
    checked_at_utc: str,
    script_version_id: int | None = None,
    run_url: str | None = None,
) -> dict:
    if (script_version_id is None) != (run_url is None):
        raise ValueError("script version ID and run URL must be supplied together")
    if script_version_id is not None:
        if not isinstance(script_version_id, int) or script_version_id <= 0:
            raise ValueError("script version ID must be a positive integer")
        owner, kernel_slug = kernel.split("/", 1)
        expected_path = f"/code/{owner}/{kernel_slug}"
        expected_suffix = f"/edit/run/{script_version_id}"
        if expected_path not in run_url or expected_suffix not in run_url:
            raise ValueError("run URL does not match kernel and script version ID")
    log_text = logs or ""
    lines = log_text.splitlines()
    receipt = {
        "checked_at_utc": checked_at_utc,
        "kernel": kernel,
        "status": status_name(status),
        "failure_message": failure_message or None,
        "log_available": bool(log_text),
        "log_lines": len(lines),
        "log_sha256": hashlib.sha256(log_text.encode("utf-8")).hexdigest()
        if log_text
        else None,
        "log_tail": lines[-30:],
        "source": "Official Kaggle kernel status and execution log APIs",
    }
    if script_version_id is not None:
        receipt["script_version_id"] = script_version_id
        receipt["run_url"] = run_url
    return receipt


def main() -> None:
    from kaggle.api.kaggle_api_extended import KaggleApi

    parser = argparse.ArgumentParser()
    parser.add_argument("kernel")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "official" / "oof_kernel_status.json"
    )
    parser.add_argument("--script-version-id", type=int)
    parser.add_argument("--run-url")
    args = parser.parse_args()

    api = KaggleApi()
    api.authenticate()
    response = api.kernels_status(args.kernel)
    try:
        logs = api.kernels_logs(args.kernel)
    except Exception as error:  # Status evidence remains useful if log streaming lags.
        logs = None
        log_error = f"{type(error).__name__}: {error}"
    else:
        log_error = None
    receipt = build_receipt(
        args.kernel,
        response.status,
        getattr(response, "failure_message", None),
        logs,
        datetime.now(timezone.utc).isoformat(),
        args.script_version_id,
        args.run_url,
    )
    receipt["log_api_error"] = log_error
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(f".{args.output.name}.tmp")
    temporary.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    temporary.replace(args.output)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
