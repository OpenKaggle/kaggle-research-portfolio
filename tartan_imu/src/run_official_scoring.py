#!/usr/bin/env python3
"""Submit one frozen CSV to the organizer's official reporting scorer."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from gradio_client import Client, handle_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("submission", type=Path)
    parser.add_argument("--team", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    client = Client(
        "Tartan-IMU/imu_odometry_challenge_scoring",
        httpx_kwargs={"timeout": 180.0},
    )
    overall, platform, sequence, sequence_file, message = client.predict(
        file_obj=handle_file(str(args.submission.resolve())),
        team_raw=args.team,
        api_name="/run",
    )
    payload = {
        "team": args.team,
        "submission": str(args.submission),
        "overall_table": overall,
        "platform_table": platform,
        "sequence_table": sequence,
        "message": message,
    }
    (args.out_dir / "official_scoring_response.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )
    copied = shutil.copy2(sequence_file, args.out_dir / "official_per_sequence.csv")
    print(message)
    print(f"saved {copied}")


if __name__ == "__main__":
    main()
