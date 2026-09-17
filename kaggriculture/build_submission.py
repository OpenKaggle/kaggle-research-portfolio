"""Build a deterministic Kaggriculture submission archive."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import tarfile
from pathlib import Path


ALLOWED_SUFFIXES = {".py", ".json", ".pkl", ".joblib", ".npy", ".npz"}
LIMIT_BYTES = 100 * 1024 * 1024


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("agent_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    agent_dir = args.agent_dir.resolve()
    files = sorted(
        path
        for path in agent_dir.iterdir()
        if path.is_file() and path.suffix in ALLOWED_SUFFIXES
    )
    if not any(path.name == "main.py" for path in files):
        raise ValueError("Submission root must contain main.py")
    compile((agent_dir / "main.py").read_bytes(), "main.py", "exec")

    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w") as archive:
        for path in files:
            payload = path.read_bytes()
            info = tarfile.TarInfo(path.name)
            info.size = len(payload)
            info.mode = 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(payload))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            compressed.write(tar_buffer.getvalue())
    size = args.output.stat().st_size
    if size > LIMIT_BYTES:
        raise ValueError(f"Submission is too large: {size} bytes")
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(f"{args.output}: {size} bytes sha256={digest}")


if __name__ == "__main__":
    main()
