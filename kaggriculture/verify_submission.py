"""Validate a Kaggriculture submission archive before any remote upload."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import tempfile
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path, PurePosixPath
from typing import Any

from kaggle_environments import make


LIMIT_BYTES = 100 * 1024 * 1024


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_archive(archive_path: Path) -> list[dict[str, Any]]:
    if archive_path.stat().st_size > LIMIT_BYTES:
        raise ValueError(f"archive exceeds 100 MiB: {archive_path.stat().st_size}")
    rows = []
    with tarfile.open(archive_path, "r:gz") as archive:
        names = archive.getnames()
        if "main.py" not in names:
            raise ValueError("submission root must contain main.py")
        if len(names) != len(set(names)):
            raise ValueError("archive contains duplicate member names")
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
                raise ValueError(f"unsafe or nested archive member: {member.name}")
            if not member.isfile():
                raise ValueError(f"archive member is not a regular file: {member.name}")
            source = archive.extractfile(member)
            if source is None:
                raise ValueError(f"could not read archive member: {member.name}")
            payload = source.read()
            rows.append({
                "path": member.name,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            })
    return sorted(rows, key=lambda row: row["path"])


def extract_checked(archive_path: Path, destination: Path) -> Path:
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            source = archive.extractfile(member)
            if source is None:
                raise ValueError(f"could not read archive member: {member.name}")
            (destination / member.name).write_bytes(source.read())
    main_path = destination / "main.py"
    compile(main_path.read_bytes(), "main.py", "exec")
    return main_path


def play(first: Path, second: Path, seed: int, episode_steps: int) -> dict[str, Any]:
    environment = make(
        "kaggriculture",
        configuration={"episodeSteps": episode_steps, "seed": seed},
        debug=True,
    )
    environment.run([str(first), str(second)])
    final = environment.steps[-1]
    rewards = [float(state.reward or 0.0) for state in final]
    statuses = [str(state.status) for state in final]
    if any(status != "DONE" for status in statuses):
        raise RuntimeError(f"non-DONE game for seed {seed}: {statuses}")
    return {
        "seed": seed,
        "first": first.parent.name,
        "second": second.parent.name,
        "rewards": rewards,
        "statuses": statuses,
        "margin_first": rewards[0] - rewards[1],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--opponent", action="append", type=Path, required=True)
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--episode-steps", type=int, default=720)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    archive_path = args.archive.resolve()
    opponents = [path.resolve() for path in args.opponent]
    if any(not path.is_file() or path.name != "main.py" for path in opponents):
        raise ValueError("each opponent must be an existing main.py")
    seeds = [int(value.strip()) for value in args.seeds.split(",") if value.strip()]
    if not seeds or len(seeds) != len(set(seeds)):
        raise ValueError("seeds must be a non-empty unique list")

    members = inspect_archive(archive_path)
    games = []
    with tempfile.TemporaryDirectory(prefix="kaggriculture_submission_") as raw_folder:
        folder = Path(raw_folder)
        candidate = extract_checked(archive_path, folder)
        for opponent in opponents:
            for seed in seeds:
                games.append(play(candidate, opponent, seed, args.episode_steps))
                games.append(play(opponent, candidate, seed, args.episode_steps))

    candidate_margins = []
    for game in games:
        margin = float(game["margin_first"])
        candidate_margins.append(margin if game["first"].startswith("kaggriculture_submission_") else -margin)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "environment": f"kaggle-environments=={version('kaggle-environments')}",
        "archive": {
            "path": str(archive_path),
            "bytes": archive_path.stat().st_size,
            "sha256": sha256(archive_path),
            "members": members,
        },
        "seeds": seeds,
        "opponents": [{"path": str(path), "sha256": sha256(path)} for path in opponents],
        "summary": {
            "games": len(games),
            "wins": sum(margin > 0 for margin in candidate_margins),
            "ties": sum(margin == 0 for margin in candidate_margins),
            "losses": sum(margin < 0 for margin in candidate_margins),
            "mean_margin": sum(candidate_margins) / len(candidate_margins),
            "worst_margin": min(candidate_margins),
            "all_done": True,
        },
        "games": games,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "summary": report["summary"], "sha256": sha256(output)}, indent=2))


if __name__ == "__main__":
    main()
