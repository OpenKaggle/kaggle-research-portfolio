"""Safely extract newly audited public Kaggriculture agents without execution."""

from __future__ import annotations

import ast
import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Spec:
    notebook: str
    mode: str
    cell: int | None = None
    expected_files: tuple[str, ...] = ("main.py",)


SPECS = {
    "farming_score_v4": Spec(
        "reference/farming_score_v4/farming-score-v4-a-better-shop.ipynb",
        "main_b64",
        cell=5,
    ),
    "conservative_market_v5": Spec(
        "reference/conservative_market_v5/kaggriculture-conservative-market-router-v5.ipynb",
        "writefiles",
        expected_files=("main.py",),
    ),
    "last_mile_harvest": Spec(
        "reference/last_mile_harvest/kaggriculture-last-mile-harvest-planner.ipynb",
        "writefiles",
        expected_files=(
            "LICENSE.txt",
            "NOTICE.txt",
            "main.py",
            "policy.py",
            "settings.json",
            "tapes.json",
            "terminal_planner.py",
            "thomas_parent.py",
            "trees.json",
            "unit_model.py",
        ),
    ),
    "nagatakengo_v57": Spec(
        "reference/nagatakengo/kaggriculture.ipynb",
        "writefiles",
        expected_files=("main.py",),
    ),
}


def source_text(cell: dict) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else str(source)


def literal_assignment(module: ast.Module, name: str):
    for node in module.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise ValueError(f"literal assignment {name!r} not found")


def extract_main_b64(notebook: dict, spec: Spec) -> dict[str, bytes]:
    if spec.cell is None:
        raise ValueError("main_b64 mode requires a cell")
    module = ast.parse(source_text(notebook["cells"][spec.cell]))
    payload = literal_assignment(module, "MAIN_B64")
    expected = str(literal_assignment(module, "EXPECTED_SOURCE_SHA256"))
    source = base64.b64decode(payload)
    actual = hashlib.sha256(source).hexdigest()
    if actual != expected:
        raise ValueError(f"embedded source digest mismatch: {actual} != {expected}")
    return {"main.py": source}


def extract_writefiles(notebook: dict) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        source = source_text(cell)
        first, separator, body = source.partition("\n")
        if not separator or not first.strip().startswith("%%writefile "):
            continue
        name = first.strip().removeprefix("%%writefile ").strip()
        path = Path(name)
        if not name or path.name != name or name in files:
            raise ValueError(f"unsafe or duplicate writefile target: {name!r}")
        files[name] = body.encode("utf-8")
    return files


def main() -> None:
    for name, spec in SPECS.items():
        notebook_path = ROOT / spec.notebook
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        if spec.mode == "main_b64":
            files = extract_main_b64(notebook, spec)
        elif spec.mode == "writefiles":
            files = extract_writefiles(notebook)
        else:
            raise ValueError(f"unsupported extraction mode: {spec.mode}")
        if name == "last_mile_harvest":
            settings = literal_assignment(ast.parse(source_text(notebook["cells"][5])), "SETTINGS")
            files["settings.json"] = (
                json.dumps(
                    settings,
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=False,
                    allow_nan=False,
                )
                + "\n"
            ).encode("utf-8")
        if tuple(sorted(files)) != tuple(sorted(spec.expected_files)):
            raise ValueError(
                f"{name}: expected {sorted(spec.expected_files)}, found {sorted(files)}"
            )
        for filename, payload in files.items():
            if filename.endswith(".py"):
                compile(payload, f"{name}/{filename}", "exec")
            elif filename.endswith(".json"):
                json.loads(payload)
        destination = ROOT / "agents" / name
        destination.mkdir(parents=True, exist_ok=True)
        for filename, payload in files.items():
            (destination / filename).write_bytes(payload)
        manifest = {
            filename: {
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            for filename, payload in sorted(files.items())
        }
        print(json.dumps({
            "agent": name,
            "notebook_sha256": hashlib.sha256(notebook_path.read_bytes()).hexdigest(),
            "files": manifest,
        }, sort_keys=True))


if __name__ == "__main__":
    main()
