"""Synchronize our Kaggriculture submissions, replays, and owned-agent logs.

This is a read-only remote operation. It never submits or changes a Kaggle
entry. Replay metadata can contain the hidden environment seed; this tool
deliberately excludes that field from every derived report.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import math
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE / "remote"
DEFAULT_MANIFEST = DEFAULT_ROOT / "submissions.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def percentile(values: Iterable[float], fraction: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def run_kaggle(binary: Path, arguments: list[str]) -> str:
    command = [str(binary), *arguments]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"Kaggle command failed ({result.returncode}): {' '.join(arguments)}\n{detail}")
    return result.stdout


def parse_csv_output(text: str, header_prefix: str) -> list[dict[str, str]]:
    lines = text.splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line.startswith(header_prefix))
    except StopIteration:
        return []
    return list(csv.DictReader(lines[start:]))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text.rstrip() + "\n", encoding="utf-8")
    temporary.replace(path)


def reusable_episode_summary(
    cached: dict[str, Any] | None,
    episode_row: dict[str, str],
    replay_path: Path,
) -> bool:
    """Return whether an immutable completed episode can reuse its prior summary.

    Replays are keyed by Kaggle episode id.  Once the episode metadata is
    unchanged and every locally referenced owned artifact still exists, parsing
    the hundreds-of-MiB replay again cannot add information.  A missing artifact
    or metadata change deliberately falls back to the normal parse/download
    path.
    """
    if not isinstance(cached, dict) or cached.get("all_done") is not True or not replay_path.exists():
        return False
    expected = {
        "episode_id": int(episode_row["id"]),
        "create_time": episode_row.get("createTime"),
        "end_time": episode_row.get("endTime"),
        "state": episode_row.get("state"),
        "type": episode_row.get("type"),
    }
    if any(cached.get(key) != value for key, value in expected.items()):
        return False
    replay = cached.get("replay")
    if not isinstance(replay, dict) or not replay.get("sha256"):
        return False
    owned_seats = cached.get("owned_seats")
    owned_logs = cached.get("owned_logs")
    if not isinstance(owned_seats, list) or not isinstance(owned_logs, dict):
        return False
    for seat in owned_seats:
        log_summary = owned_logs.get(str(seat))
        if not isinstance(log_summary, dict) or not log_summary.get("path"):
            return False
        if not Path(log_summary["path"]).exists():
            return False
    return True


def flatten_log_records(value: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(value, dict):
        records.append(value)
    elif isinstance(value, list):
        for item in value:
            records.extend(flatten_log_records(item))
    return records


def summarize_log(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = flatten_log_records(payload)
    durations = [float(row["duration"]) for row in records if isinstance(row.get("duration"), (int, float))]
    stdout = [str(row.get("stdout") or "") for row in records]
    stderr = [str(row.get("stderr") or "") for row in records]
    return {
        "path": str(path),
        "sha256": sha256(path),
        "records": len(records),
        "duration_seconds": {
            "total": sum(durations),
            "p95": percentile(durations, 0.95),
            "max": max(durations) if durations else None,
        },
        "stdout_nonempty_records": sum(bool(value.strip()) for value in stdout),
        "stdout_characters": sum(len(value) for value in stdout),
        "stderr_nonempty_records": sum(bool(value.strip()) for value in stderr),
        "stderr_characters": sum(len(value) for value in stderr),
    }


def replay_team_names(replay: dict[str, Any]) -> list[str]:
    info = replay.get("info") if isinstance(replay.get("info"), dict) else {}
    names = info.get("TeamNames")
    if isinstance(names, list) and all(isinstance(name, str) for name in names):
        return names
    agents = info.get("Agents")
    if isinstance(agents, list):
        return [str(agent.get("Name") or "") if isinstance(agent, dict) else "" for agent in agents]
    return []


def infer_owned_seats(replay: dict[str, Any], owned_names: set[str]) -> list[int]:
    return [index for index, name in enumerate(replay_team_names(replay)) if name in owned_names]


def first_two_public_shops(replay: dict[str, Any]) -> list[dict[str, Any]]:
    unlocked: list[dict[str, Any]] = []
    for step_index, states in enumerate(replay.get("steps", [])):
        if not isinstance(states, list) or not states:
            continue
        state = states[0] if isinstance(states[0], dict) else {}
        observation = state.get("observation") if isinstance(state.get("observation"), dict) else {}
        town = observation.get("town") if isinstance(observation.get("town"), dict) else {}
        shops = town.get("unlocked_shops")
        if not isinstance(shops, list):
            continue
        while len(unlocked) < min(2, len(shops)):
            unlocked.append({"shop": str(shops[len(unlocked)]), "step": step_index})
        if len(unlocked) == 2:
            break
    return unlocked


def summarize_replay(
    path: Path,
    replay: dict[str, Any],
    episode_row: dict[str, str],
    owned_names: set[str],
    log_summaries: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    info = replay.get("info") if isinstance(replay.get("info"), dict) else {}
    episode_id = int(info.get("EpisodeId") or episode_row["id"])
    team_names = replay_team_names(replay)
    owned_seats = infer_owned_seats(replay, owned_names)
    rewards = [float(value) if value is not None else None for value in replay.get("rewards", [])]
    statuses = [str(value) for value in replay.get("statuses", [])]
    episode_type = episode_row.get("type", "")

    outcome = None
    margin = None
    owned_seat = None
    if len(owned_seats) == 1 and len(rewards) == 2 and all(value is not None for value in rewards):
        owned_seat = owned_seats[0]
        opponent_seat = 1 - owned_seat
        margin = float(rewards[owned_seat]) - float(rewards[opponent_seat])
        outcome = "win" if margin > 0 else "loss" if margin < 0 else "tie"
    elif len(owned_seats) == len(rewards) and owned_seats:
        outcome = "validation_self_play"
    public_shops = first_two_public_shops(replay)
    first_shop = public_shops[0] if public_shops else {"shop": None, "step": None}
    second_shop = public_shops[1] if len(public_shops) > 1 else {"shop": None, "step": None}

    # Do not copy info.seed or configuration.seed into this derived record.
    return {
        "episode_id": episode_id,
        "type": episode_type,
        "state": episode_row.get("state"),
        "create_time": episode_row.get("createTime"),
        "end_time": episode_row.get("endTime"),
        "environment": replay.get("name"),
        "environment_version": replay.get("version"),
        "episode_steps": len(replay.get("steps", [])),
        "team_names": team_names,
        "owned_seats": owned_seats,
        "owned_seat": owned_seat,
        "opponent_names": [name for index, name in enumerate(team_names) if index not in owned_seats],
        "public_context": {
            "first_unlocked_shop": first_shop["shop"],
            "first_unlocked_shop_step": first_shop["step"],
            "second_unlocked_shop": second_shop["shop"],
            "second_unlocked_shop_step": second_shop["step"],
        },
        "rewards": rewards,
        "statuses": statuses,
        "all_done": bool(statuses) and all(status == "DONE" for status in statuses),
        "outcome": outcome,
        "margin": margin,
        "replay": {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)},
        "owned_logs": {str(seat): summary for seat, summary in sorted(log_summaries.items())},
    }


def aggregate_submission(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [episode for episode in episodes if episode.get("outcome") in {"win", "tie", "loss"}]
    margins = [float(episode["margin"]) for episode in scored]
    seats: dict[int, list[dict[str, Any]]] = defaultdict(list)
    opponents: dict[str, list[dict[str, Any]]] = defaultdict(list)
    first_shops: dict[str, list[dict[str, Any]]] = defaultdict(list)
    second_shops: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for episode in scored:
        seats[int(episode["owned_seat"])].append(episode)
        opponent = " | ".join(str(name) for name in episode.get("opponent_names", [])) or "unknown"
        opponents[opponent].append(episode)
        public_context = episode.get("public_context", {})
        first_shops[str(public_context.get("first_unlocked_shop") or "unknown")].append(episode)
        second_shops[str(public_context.get("second_unlocked_shop") or "unknown")].append(episode)

    def record(rows: list[dict[str, Any]]) -> dict[str, Any]:
        row_margins = [float(row["margin"]) for row in rows]
        wins = sum(row["outcome"] == "win" for row in rows)
        ties = sum(row["outcome"] == "tie" for row in rows)
        losses = sum(row["outcome"] == "loss" for row in rows)
        return {
            "games": len(rows),
            "wins": wins,
            "ties": ties,
            "losses": losses,
            "score_win_rate": (wins + 0.5 * ties) / len(rows) if rows else None,
            "mean_margin": sum(row_margins) / len(row_margins) if row_margins else None,
            "p10_margin": percentile(row_margins, 0.10),
            "worst_margin": min(row_margins) if row_margins else None,
        }

    logs = [summary for episode in episodes for summary in episode.get("owned_logs", {}).values()]
    return {
        "episodes": len(episodes),
        "validation_self_play": sum(episode.get("outcome") == "validation_self_play" for episode in episodes),
        "unscored_or_unknown_owner": sum(episode.get("outcome") is None for episode in episodes),
        "non_done": sum(not episode.get("all_done") for episode in episodes),
        "evaluation": record(scored),
        "seat": {str(seat): record(rows) for seat, rows in sorted(seats.items())},
        "opponents": {opponent: record(rows) for opponent, rows in sorted(opponents.items())},
        "first_shops": {shop: record(rows) for shop, rows in sorted(first_shops.items())},
        "second_shops": {shop: record(rows) for shop, rows in sorted(second_shops.items())},
        "logs": {
            "files": len(logs),
            "stderr_nonempty_records": sum(int(log["stderr_nonempty_records"]) for log in logs),
            "stdout_nonempty_records": sum(int(log["stdout_nonempty_records"]) for log in logs),
            "max_action_duration_seconds": max(
                (float(log["duration_seconds"]["max"]) for log in logs if log["duration_seconds"]["max"] is not None),
                default=None,
            ),
        },
        "margin_count": len(margins),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--kaggle-bin", type=Path, default=Path(sys.executable).with_name("kaggle"))
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument(
        "--offline-snapshots",
        action="store_true",
        help="rebuild the derived report from saved CSV/replay/log artifacts without network",
    )
    parser.add_argument("--worker-replay", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-episode-row", help=argparse.SUPPRESS)
    parser.add_argument("--worker-owned-names", help=argparse.SUPPRESS)
    args = parser.parse_args()

    # A replay expands to hundreds of MiB of Python objects. Parse each replay
    # in a short-lived child so a long sync never accumulates JSON allocator
    # arenas across dozens of episodes.
    if args.worker_replay is not None:
        if args.worker_episode_row is None or args.worker_owned_names is None:
            raise ValueError("worker replay mode requires episode row and owned names")
        replay_path = args.worker_replay.resolve()
        replay = json.loads(replay_path.read_text(encoding="utf-8"))
        episode_row = json.loads(args.worker_episode_row)
        owned_names = set(json.loads(args.worker_owned_names))
        print(json.dumps(summarize_replay(replay_path, replay, episode_row, owned_names, {})))
        return

    manifest = json.loads(args.manifest.resolve().read_text(encoding="utf-8"))
    competition = str(manifest["competition"])
    owned_names = {str(name) for name in manifest.get("team_names", [])}
    submissions = manifest.get("submissions", [])
    root = args.output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    # The app heartbeat and a manual refresh can overlap. Serialize complete
    # syncs so an older remote snapshot can never overwrite a newer one.
    lock_handle = (root / ".sync.lock").open("a+", encoding="utf-8")
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
    replay_folder = root / "replays"
    log_folder = root / "logs"
    snapshot_folder = root / "snapshots"
    for folder in (replay_folder, log_folder, snapshot_folder):
        folder.mkdir(parents=True, exist_ok=True)

    report_path = root / "summary_latest.json"
    previous_report: dict[str, Any] = {}
    if report_path.exists():
        try:
            loaded = json.loads(report_path.read_text(encoding="utf-8"))
            # Incomplete runs are still useful caches for episodes whose replay
            # and owned logs are present.  reusable_episode_summary() rejects
            # exactly the affected rows and rebuilds only those artifacts.
            if isinstance(loaded, dict):
                previous_report = loaded
        except (OSError, json.JSONDecodeError):
            previous_report = {}
    previous_by_submission = {
        int(row["id"]): {
            int(episode["episode_id"]): episode
            for episode in row.get("episodes", [])
            if isinstance(episode, dict) and isinstance(episode.get("episode_id"), int)
        }
        for row in previous_report.get("submissions", [])
        if isinstance(row, dict) and str(row.get("id", "")).isdigit()
    }

    submission_snapshot = snapshot_folder / "submissions_latest.csv"
    if args.offline_snapshots:
        submission_csv = submission_snapshot.read_text(encoding="utf-8")
    else:
        submission_csv = run_kaggle(args.kaggle_bin, ["competitions", "submissions", "-c", competition, "--csv"])
        write_text(submission_snapshot, submission_csv)
    remote_rows = parse_csv_output(submission_csv, "ref,")
    remote_by_id = {int(row["ref"]): row for row in remote_rows}

    report_submissions = []
    download_errors = []
    for submission in submissions:
        submission_id = int(submission["id"])
        cached_episodes = previous_by_submission.get(submission_id, {})
        episodes_snapshot = snapshot_folder / f"episodes_{submission_id}_latest.csv"
        if args.offline_snapshots:
            episodes_csv = episodes_snapshot.read_text(encoding="utf-8")
        else:
            episodes_csv = run_kaggle(
                args.kaggle_bin,
                ["competitions", "episodes", str(submission_id), "--csv", "--quiet"],
            )
            write_text(episodes_snapshot, episodes_csv)
        episode_rows = parse_csv_output(episodes_csv, "id,")
        episode_summaries = []
        for episode_row in episode_rows:
            episode_id = int(episode_row["id"])
            replay_path = replay_folder / f"episode-{episode_id}-replay.json"
            if not replay_path.exists() and not args.no_download and not args.offline_snapshots:
                try:
                    run_kaggle(
                        args.kaggle_bin,
                        ["competitions", "replay", str(episode_id), "-p", str(replay_folder), "--quiet"],
                    )
                except RuntimeError as error:
                    download_errors.append({"episode_id": episode_id, "artifact": "replay", "error": str(error)})
            if not replay_path.exists():
                continue

            cached_summary = cached_episodes.get(episode_id)
            if reusable_episode_summary(cached_summary, episode_row, replay_path):
                episode_summaries.append(cached_summary)
                continue

            worker = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--worker-replay",
                    str(replay_path),
                    "--worker-episode-row",
                    json.dumps(episode_row),
                    "--worker-owned-names",
                    json.dumps(sorted(owned_names)),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if worker.returncode:
                raise RuntimeError(
                    f"replay worker failed for episode {episode_id}: {(worker.stderr or worker.stdout).strip()}"
                )
            episode_summary = json.loads(worker.stdout)
            owned_seats = [int(seat) for seat in episode_summary["owned_seats"]]
            log_summaries = {}
            for seat in owned_seats:
                log_path = log_folder / f"episode-{episode_id}-agent-{seat}-logs.json"
                if not log_path.exists() and not args.no_download and not args.offline_snapshots:
                    try:
                        run_kaggle(
                            args.kaggle_bin,
                            ["competitions", "logs", str(episode_id), str(seat), "-p", str(log_folder), "--quiet"],
                        )
                    except RuntimeError as error:
                        download_errors.append(
                            {"episode_id": episode_id, "artifact": f"owned_log_seat_{seat}", "error": str(error)}
                        )
                if log_path.exists():
                    log_summaries[seat] = summarize_log(log_path)
            episode_summary["owned_logs"] = {
                str(seat): summary for seat, summary in sorted(log_summaries.items())
            }
            episode_summaries.append(episode_summary)

        remote = remote_by_id.get(submission_id, {})
        report_submissions.append(
            {
                **submission,
                "remote": {
                    "status": remote.get("status"),
                    "public_score": remote.get("publicScore"),
                    "private_score": remote.get("privateScore"),
                    "date": remote.get("date"),
                },
                "summary": aggregate_submission(episode_summaries),
                "episodes": episode_summaries,
            }
        )

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "competition": competition,
        "policy": {
            "remote_operations": "read_only",
            "downloads": "replays and logs for owned seats only",
            "hidden_seed_recorded": False,
        },
        "submissions": report_submissions,
        "download_errors": download_errors,
    }
    rendered = json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    write_text(report_path, rendered)
    print(
        json.dumps(
            {
                "output": str(report_path),
                "sha256": sha256(report_path),
                "submissions": [
                    {
                        "id": row["id"],
                        "label": row["label"],
                        "status": row["remote"]["status"],
                        "score": row["remote"]["public_score"],
                        "episodes": row["summary"]["episodes"],
                        "evaluation": row["summary"]["evaluation"],
                    }
                    for row in report_submissions
                ],
                "download_errors": len(download_errors),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
