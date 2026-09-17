"""Extract plainly embedded Kaggriculture agents from audited public notebooks.

The extractor deliberately supports only explicit ``%%writefile``/``%%agentfile``
cells.  It never executes notebook code.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCES = {
    "salem_2900": ROOT
    / "reference/salem_2900/kaggriculture-2900.ipynb",
    "public_state_955": ROOT
    / "reference/public_state_955/kaggriculture-95-5-win-rate-via-replay-routing.ipynb",
}
ALLOWED_MAGICS = ("%%writefile main.py", "%%agentfile")


def cell_text(cell: dict) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else str(source)


def extract_source(notebook_path: Path) -> str:
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    matches: list[str] = []
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        source = cell_text(cell)
        first_line, separator, body = source.partition("\n")
        if separator and first_line.strip() in ALLOWED_MAGICS:
            matches.append(body)
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one explicit agent cell in {notebook_path}, "
            f"found {len(matches)}"
        )
    compile(matches[0], str(notebook_path), "exec")
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("names", nargs="*", choices=sorted(SOURCES))
    args = parser.parse_args()
    selected = args.names or list(SOURCES)
    output_root = ROOT / "agents"
    for name in selected:
        destination = output_root / name / "main.py"
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = extract_source(SOURCES[name])
        destination.write_text(source, encoding="utf-8")
        print(f"{name}: {destination.relative_to(ROOT)} ({len(source)} chars)")


if __name__ == "__main__":
    main()
