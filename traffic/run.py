#!/usr/bin/env python3
"""One reproducible local entry point for the TrafficFlowBench campaign."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OFFICIAL = ROOT / "official"
PYTHON = Path(sys.executable)


def _release_problems(release: Path) -> list[str]:
    required = [
        release / "config" / "corridors.json",
        release / "corridors",
        release / "task1",
        release / "task2",
        release / "task4",
        release / "submission_key.csv",
    ]
    return [str(path) for path in required if not path.exists()]


def doctor(release: Path) -> int:
    print(f"official_code={OFFICIAL}")
    print(f"official_commit={subprocess.check_output(['git', '-C', str(OFFICIAL), 'rev-parse', 'HEAD'], text=True).strip()}")
    print(f"release_root={release}")
    missing = _release_problems(release)
    if missing:
        print("status=BLOCKED_DATA")
        print("missing:")
        for path in missing:
            print(f"  - {path}")
        print("The release is incomplete at this path; finish downloading/unpacking the Kaggle package, then rerun doctor.")
        return 2
    manifest = json.loads((release / "config" / "corridors.json").read_text(encoding="utf-8"))
    print("status=READY")
    print(f"panels={len(manifest['panels'])}")
    return 0


def _run(*args: str) -> None:
    print("RUN", " ".join(args), flush=True)
    subprocess.run(args, cwd=OFFICIAL, check=True)


def _concat_csv(inputs: list[Path], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    header: str | None = None
    with output.open("w", encoding="utf-8", newline="") as sink:
        for path in inputs:
            with path.open("r", encoding="utf-8", newline="") as source:
                current = source.readline()
                if header is None:
                    header = current
                    sink.write(current)
                elif current != header:
                    raise ValueError(f"CSV header mismatch in {path}")
                shutil.copyfileobj(source, sink)


def build(release: Path, output_root: Path, queue_method: str) -> None:
    missing = _release_problems(release)
    if missing:
        raise SystemExit("Release is incomplete. Run `python traffic/run.py doctor --release-root ...` first.")
    splits = ["validation", "private"]
    output_root.mkdir(parents=True, exist_ok=True)
    state_parts: list[Path] = []
    queue_parts: list[Path] = []
    odme_parts: list[Path] = []
    for split in splits:
        state = output_root / f"state_{split}.csv"
        _run(
            str(PYTHON), "src/task1/build_task1_baseline_submission.py",
            "--release-root", str(release), "--split", split, "--output", str(state),
        )
        state_parts.append(state)

        queue = output_root / f"queue_{split}.csv"
        queue_script = (
            ROOT / "src" / "queue_shockwave.py"
            if queue_method == "shockwave"
            else OFFICIAL / "src" / "task2" / "build_task2_persistence_submission.py"
        )
        _run(
            str(PYTHON), str(queue_script), "--release-root", str(release),
            "--split", split, "--output", str(queue),
        )
        queue_parts.append(queue)

        task4_root = output_root / f"task4_{split}"
        _run(
            str(PYTHON), "src/task4/build_task4_odme_artifacts.py",
            "--release-root", str(release), "--split", split, "--output-root", str(task4_root),
        )
        odme_parts.append(task4_root / "baseline_submission.csv")

    state = output_root / "state_submission.csv"
    queue = output_root / "queue_submission.csv"
    odme = output_root / "odme_submission.csv"
    _concat_csv(state_parts, state)
    _concat_csv(queue_parts, queue)
    _concat_csv(odme_parts, odme)
    _run(
        str(PYTHON), "src/merge_submissions.py",
        "--state", str(state), "--queue", str(queue), "--odme", str(odme),
        "--key", str(release / "submission_key.csv"), "--output", str(output_root / "submission.csv"),
    )


def reproduce_current_best(
    release: Path,
    config: Path,
    output_root: Path,
    evidence_root: Path,
) -> None:
    missing = _release_problems(release)
    if missing:
        raise SystemExit("Release is incomplete. Run `python traffic/run.py doctor --release-root ...` first.")
    subprocess.run(
        [
            str(PYTHON),
            str(ROOT / "src" / "reproduce_current_best.py"),
            "--release-root", str(release),
            "--config", str(config),
            "--output-root", str(output_root),
            "--evidence-root", str(evidence_root),
        ],
        cwd=ROOT,
        check=True,
    )


def audit_evidence(script: str, config: Path, output_root: Path) -> None:
    subprocess.run(
        [
            str(PYTHON),
            str(ROOT / "src" / script),
            "--traffic-root", str(ROOT),
            "--config", str(config),
            "--output-root", str(output_root),
        ],
        cwd=ROOT,
        check=True,
    )


def audit_lifecycle_policy(config: Path, as_of: str, output_root: Path) -> None:
    subprocess.run(
        [
            str(PYTHON),
            str(ROOT / "src" / "lifecycle_policy_audit.py"),
            "--traffic-root", str(ROOT),
            "--config", str(config),
            "--as-of", as_of,
            "--output-root", str(output_root),
        ],
        cwd=ROOT,
        check=True,
    )


def audit_system_manifest(config: Path, output_root: Path, activate: bool) -> None:
    command = [
        str(PYTHON),
        str(ROOT / "src" / "system_implementation_manifest_audit.py"),
        "--traffic-root", str(ROOT),
        "--config", str(config),
        "--output-root", str(output_root),
    ]
    if activate:
        command.append("--activate")
    subprocess.run(command, cwd=ROOT, check=True)


def audit_campaign(
    release: Path,
    as_of: str,
    output_root: Path,
    verify_archive: bool,
    activate: bool,
) -> None:
    command = [
        str(PYTHON),
        str(ROOT / "src" / "campaign_readiness_audit.py"),
        "--traffic-root", str(ROOT),
        "--release-root", str(release),
        "--as-of", as_of,
        "--output-root", str(output_root),
    ]
    if verify_archive:
        command.append("--verify-archive")
    if activate:
        command.append("--activate")
    subprocess.run(command, cwd=ROOT, check=True)


def select_final(as_of: str, output_root: Path, dry_run: bool) -> None:
    command = [
        str(PYTHON),
        str(ROOT / "src" / "final_submission_selector.py"),
        "--traffic-root", str(ROOT),
        "--as-of", as_of,
        "--output-root", str(output_root),
    ]
    if dry_run:
        command.append("--dry-run")
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    commands = (
        "doctor", "build", "reproduce-current-best", "audit-runtime",
        "audit-system-manifest", "audit-four-tasks", "audit-method-policy",
        "audit-submission-attribution", "audit-lifecycle-policy", "audit-campaign",
        "select-final",
    )
    for command in commands:
        child = sub.add_parser(command)
        if command in {"doctor", "build", "reproduce-current-best", "audit-campaign"}:
            child.add_argument("--release-root", type=Path, required=True)
        if command == "build":
            child.add_argument("--output-root", type=Path, default=ROOT / "artifacts" / "baseline")
            child.add_argument("--queue-method", choices=["persistence", "shockwave"], default="shockwave")
        elif command == "reproduce-current-best":
            child.add_argument("--output-root", type=Path, required=True)
            child.add_argument(
                "--evidence-root",
                type=Path,
                default=ROOT / "artifacts" / "current_best_full_replay_v1",
            )
            child.add_argument(
                "--config",
                type=Path,
                default=ROOT / "config" / "current_best_freeze_v1.json",
            )
        elif command == "audit-four-tasks":
            child.add_argument("--output-root", type=Path, required=True)
            child.add_argument(
                "--config",
                type=Path,
                default=ROOT / "config" / "four_task_baseline_contract_v1.json",
            )
        elif command == "audit-runtime":
            child.add_argument("--output-root", type=Path, required=True)
            child.add_argument(
                "--config",
                type=Path,
                default=ROOT / "config" / "runtime_environment_contract_v3.json",
            )
        elif command == "audit-system-manifest":
            child.add_argument("--output-root", type=Path, required=True)
            child.add_argument("--activate", action="store_true")
            child.add_argument(
                "--config",
                type=Path,
                default=ROOT / "config" / "system_implementation_manifest_v1.json",
            )
        elif command == "audit-method-policy":
            child.add_argument("--output-root", type=Path, required=True)
            child.add_argument(
                "--config",
                type=Path,
                default=ROOT / "config" / "method_family_policy_v1.json",
            )
        elif command == "audit-submission-attribution":
            child.add_argument("--output-root", type=Path, required=True)
            child.add_argument(
                "--config",
                type=Path,
                default=ROOT / "config" / "submission_attribution_chain_v1.json",
            )
        elif command == "audit-lifecycle-policy":
            child.add_argument("--as-of", required=True)
            child.add_argument("--output-root", type=Path, required=True)
            child.add_argument(
                "--config",
                type=Path,
                default=ROOT / "config" / "lifecycle_policy_v1.json",
            )
        elif command == "audit-campaign":
            child.add_argument("--as-of", required=True)
            child.add_argument(
                "--output-root",
                type=Path,
                default=ROOT / "artifacts" / "campaign_readiness_audit_v1",
            )
            child.add_argument("--verify-archive", action="store_true")
            child.add_argument("--activate", action="store_true")
        elif command == "select-final":
            child.add_argument("--as-of", required=True)
            child.add_argument("--output-root", type=Path, required=True)
            child.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.command == "doctor":
        raise SystemExit(doctor(args.release_root.resolve()))
    if args.command == "build":
        build(args.release_root.resolve(), args.output_root.resolve(), args.queue_method)
    elif args.command == "reproduce-current-best":
        reproduce_current_best(
            args.release_root.resolve(),
            args.config.resolve(),
            args.output_root.resolve(),
            args.evidence_root.resolve(),
        )
    elif args.command == "audit-four-tasks":
        audit_evidence(
            "four_task_baseline_audit.py", args.config.resolve(), args.output_root.resolve()
        )
    elif args.command == "audit-runtime":
        audit_evidence(
            "runtime_environment_audit.py", args.config.resolve(), args.output_root.resolve()
        )
    elif args.command == "audit-system-manifest":
        audit_system_manifest(args.config.resolve(), args.output_root.resolve(), args.activate)
    elif args.command == "audit-method-policy":
        audit_evidence(
            "method_family_policy_audit.py", args.config.resolve(), args.output_root.resolve()
        )
    elif args.command == "audit-submission-attribution":
        audit_evidence(
            "submission_attribution_audit.py", args.config.resolve(), args.output_root.resolve()
        )
    elif args.command == "audit-lifecycle-policy":
        audit_lifecycle_policy(args.config.resolve(), args.as_of, args.output_root.resolve())
    elif args.command == "audit-campaign":
        audit_campaign(
            args.release_root.resolve(),
            args.as_of,
            args.output_root.resolve(),
            args.verify_archive,
            args.activate,
        )
    else:
        select_final(args.as_of, args.output_root.resolve(), args.dry_run)


if __name__ == "__main__":
    main()
