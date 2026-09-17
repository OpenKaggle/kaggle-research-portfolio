#!/usr/bin/env python3
"""Create and verify a closed manifest of campaign implementation and core receipts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import resource
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


MANIFEST_COLUMNS = ["category", "path", "size_bytes", "sha256"]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _peak_memory_mb() -> float:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return float(raw / (1024 * 1024) if platform.system() == "Darwin" else raw / 1024)


def _is_forbidden(path: str, prefixes: list[str]) -> bool:
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in prefixes)


def discover_manifest(
    traffic_root: Path, config: dict[str, object]
) -> tuple[list[dict[str, object]], list[str], int]:
    """Return deterministic manifest rows, validation errors, and valid receipt count."""
    root = traffic_root.resolve()
    errors: list[str] = []
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    forbidden = list(config["forbidden_path_prefixes"])

    def add(category: str, path: Path) -> None:
        try:
            relative = path.resolve().relative_to(root).as_posix()
        except ValueError:
            errors.append(f"path escapes traffic root: {path}")
            return
        if path.is_symlink():
            errors.append(f"manifest path may not be a symlink: {relative}")
            return
        if not path.is_file():
            errors.append(f"manifest path is not a file: {relative}")
            return
        if _is_forbidden(relative, forbidden):
            errors.append(f"manifest path crosses information boundary: {relative}")
            return
        if relative in seen:
            errors.append(f"manifest path appears more than once: {relative}")
            return
        seen.add(relative)
        rows.append({
            "category": category,
            "path": relative,
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        })

    for rule in config["manifest_rules"]:
        matches = sorted(
            (path for path in root.glob(rule["pattern"]) if path.is_file() or path.is_symlink()),
            key=lambda path: path.relative_to(root).as_posix(),
        )
        if len(matches) != int(rule["expected_count"]):
            errors.append(
                f"{rule['category']} pattern {rule['pattern']} matched {len(matches)} files; "
                f"expected {rule['expected_count']}"
            )
        for path in matches:
            add(str(rule["category"]), path)

    receipts_verified = 0
    for expected in config["canonical_receipts"]:
        relative = str(expected["path"])
        path = root / relative
        if not path.is_file():
            errors.append(f"canonical receipt missing: {relative}")
            continue
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"canonical receipt unreadable: {relative}: {error}")
            continue
        if receipt.get("status") != expected["status"]:
            errors.append(
                f"canonical receipt status mismatch: {relative}: "
                f"expected {expected['status']}, got {receipt.get('status')}"
            )
        elif "decision" in expected and receipt.get("decision") != expected["decision"]:
            errors.append(
                f"canonical receipt decision mismatch: {relative}: "
                f"expected {expected['decision']}, got {receipt.get('decision')}"
            )
        elif receipt.get("errors", []) != []:
            errors.append(f"canonical receipt reports errors: {relative}")
        else:
            receipts_verified += 1
        add("canonical_receipt", path)

    rows.sort(key=lambda row: (str(row["category"]), str(row["path"])))
    return rows, errors, receipts_verified


def _write_manifest(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def verify_current_manifest(traffic_root: Path, receipt_path: Path) -> list[str]:
    """Recompute the declared set and report drift from an immutable manifest receipt."""
    root = traffic_root.resolve()
    receipt_path = receipt_path.resolve()
    errors: list[str] = []
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"system manifest receipt unreadable: {error}"]
    if receipt.get("status") != "VALID" or receipt.get("errors") != []:
        errors.append("system manifest receipt is not VALID")
    contract_rel = receipt.get("contract_path")
    if not isinstance(contract_rel, str):
        return [*errors, "system manifest receipt has no contract_path"]
    contract_path = root / contract_rel
    if not contract_path.is_file():
        return [*errors, f"system manifest contract missing: {contract_rel}"]
    expected_contract_sha = receipt.get("inputs", {}).get(contract_rel)
    if _sha256(contract_path) != expected_contract_sha:
        return [*errors, "system manifest contract SHA drift"]
    try:
        config = json.loads(contract_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [*errors, f"system manifest contract is invalid JSON: {error}"]
    output_name = "system_implementation_manifest.csv"
    manifest_path = receipt_path.parent / output_name
    if not manifest_path.is_file():
        return [*errors, "system implementation manifest CSV is missing"]
    if _sha256(manifest_path) != receipt.get("outputs", {}).get(output_name):
        errors.append("system implementation manifest CSV SHA drift")
        return errors
    with manifest_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != MANIFEST_COLUMNS:
            errors.append("system implementation manifest CSV header mismatch")
            return errors
        recorded = list(reader)
    current, discovery_errors, receipts_verified = discover_manifest(root, config)
    errors.extend(discovery_errors)
    normalized_current = [
        {column: str(row[column]) for column in MANIFEST_COLUMNS} for row in current
    ]
    if recorded != normalized_current:
        errors.append("system implementation files differ from the recorded manifest")
    if len(recorded) != receipt.get("files_hashed"):
        errors.append("system implementation manifest row count disagrees with receipt")
    if receipts_verified != receipt.get("canonical_receipts_verified"):
        errors.append("canonical receipt count disagrees with system manifest receipt")
    return errors


def run(
    traffic_root: Path,
    config_path: Path,
    output_root: Path,
    activate: bool = False,
) -> dict[str, object]:
    started = time.perf_counter()
    if output_root.exists():
        raise ValueError("system manifest output root already exists; use a new path")
    root = traffic_root.resolve()
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    rows, errors, receipts_verified = discover_manifest(root, config)
    if any(config["information_boundary"].values()):
        errors.append("system manifest contract permits an information-boundary violation")
    official_head = subprocess.check_output(
        ["git", "-C", str(root / "official"), "rev-parse", "HEAD"], text=True
    ).strip()
    if official_head != config["official_code_commit"]:
        errors.append("official code commit mismatch")

    output_root.mkdir(parents=True)
    manifest_path = output_root / "system_implementation_manifest.csv"
    _write_manifest(manifest_path, rows)
    category_counts = dict(sorted(Counter(str(row["category"]) for row in rows).items()))
    contract_rel = config_path.relative_to(root).as_posix()
    receipt: dict[str, object] = {
        "status": "VALID" if not errors else "FAIL",
        "experiment": config["version"],
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "contract_path": contract_rel,
        "files_hashed": len(rows),
        "category_counts": category_counts,
        "canonical_receipts_verified": receipts_verified,
        "official_code_commit": official_head,
        "errors": errors,
        "information_boundary": dict(config["information_boundary"]),
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": _peak_memory_mb(),
        "inputs": {contract_rel: _sha256(config_path)},
        "outputs": {manifest_path.name: _sha256(manifest_path)},
        "decision": "IMPLEMENTATION_AND_EVIDENCE_SET_PINNED" if not errors else "MANIFEST_INVALID",
    }
    receipt_path = output_root / "system_implementation_manifest_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if activate:
        if errors:
            raise ValueError("cannot activate an invalid system implementation manifest")
        from evidence_registry import register_system_manifest

        register_system_manifest(root, receipt_path)
    print(json.dumps(receipt, indent=2))
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traffic-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "config"
        / "system_implementation_manifest_v1.json",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    receipt = run(
        args.traffic_root.resolve(), args.config.resolve(), args.output_root.resolve(), args.activate
    )
    if receipt["status"] != "VALID":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
