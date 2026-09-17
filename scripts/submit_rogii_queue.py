from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


COMPETITION = "rogii-wellbore-geology-prediction"


@dataclass(frozen=True)
class SubmitItem:
    kernel: str
    version: int
    file: str
    message: str


QUEUE = [
    SubmitItem(
        "jahyee/rogii-h-blend-v1",
        1,
        "submission.csv",
        "H Blend v1 Codex dynamic hidden-compatible",
    ),
    SubmitItem(
        "jahyee/rogii-suneet-lb900",
        2,
        "submission.csv",
        "Suneet LB900 v2 Codex dynamic patched valid",
    ),
    SubmitItem(
        "jahyee/rogii-afr1ste-pf-beam-tabicl",
        1,
        "submission.csv",
        "Afr1ste PF Beam TabICL Codex dynamic",
    ),
    SubmitItem(
        "jahyee/rogii-aidensong-genuine-pf-v2-codex",
        1,
        "submission.csv",
        "AidenSong Genuine PF v2 Codex dynamic",
    ),
    SubmitItem(
        "jahyee/rogii-k1nsom-lgb-relative-codex",
        1,
        "submission.csv",
        "K1nsom LGB relative Codex dynamic low-priority",
    ),
]


def kaggle_bin() -> Path:
    candidate = Path(".venv/bin/kaggle")
    if candidate.exists():
        return candidate
    return Path(sys.executable).with_name("kaggle")


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(kaggle_bin()), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def print_recent_submissions() -> None:
    result = run(["competitions", "submissions", "-c", COMPETITION, "-v"])
    print(result.stdout.strip())


def submit(item: SubmitItem, dry_run: bool) -> int:
    cmd = [
        "competitions",
        "submit",
        "-c",
        COMPETITION,
        "-k",
        item.kernel,
        "-v",
        str(item.version),
        "-f",
        item.file,
        "-m",
        item.message,
    ]
    print(" ".join([str(kaggle_bin()), *cmd]))
    if dry_run:
        return 0
    result = run(cmd)
    print(result.stdout.strip())
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Actually submit to Kaggle.")
    parser.add_argument("--limit", type=int, default=1, help="Number of queued submissions to send.")
    parser.add_argument("--start", type=int, default=0, help="Zero-based queue offset.")
    parser.add_argument("--show-current", action="store_true")
    args = parser.parse_args()

    dry_run = not args.execute
    if args.show_current or dry_run:
        print_recent_submissions()

    items = QUEUE[args.start : args.start + args.limit]
    if not items:
        print("No queued items selected.")
        return 0

    rc = 0
    for item in items:
        rc = max(rc, submit(item, dry_run=dry_run))
    if dry_run:
        print("dry-run only; add --execute after quota reset to submit.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
