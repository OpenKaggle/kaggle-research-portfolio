"""Safely unpack allow-listed public agents without executing notebook cells."""

from __future__ import annotations

import ast
import base64
import hashlib
import io
import json
import tarfile
import zlib
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class PackedAgent:
    notebook: str
    cell_index: int
    encoding: str
    variable: str | None
    expected_sha256: str | None


SPECS = {
    "market_hysteresis": PackedAgent(
        "reference/market_hysteresis/v29-r1-adaptive-market-hysteresis.ipynb",
        1,
        "zlib_b64",
        "PAYLOAD",
        "c4a6964cec3c1c99207c32bb1fd91e53c3ec01e6890da5734331cbeab1cc1267",
    ),
    "minimax_v58": PackedAgent(
        "reference/minimax_v58/238-238-known-streams-v58-minimax-closed-loop.ipynb",
        9,
        "zlib_b85",
        "payload",
        "b041058ec187a8d0a01edc0eab8de068b53deca3e6c1973faf74ace6916ddcb9",
    ),
    "shape_shop_pasture": PackedAgent(
        "reference/shape_shop_pasture/shape-the-shop-work-the-pasture-kaggriculture.ipynb",
        9,
        "b64",
        "MAIN_B64",
        "2b97e2c653018ac4aeffb8463ec91c8f26b097b4cef81289acc25ccdbc68f916",
    ),
    "shop_router_0908": PackedAgent(
        "reference/shop_router_0908/shop-router-0908.ipynb",
        1,
        "tar_b64_call",
        None,
        None,
    ),
}


def source_text(cell: dict) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else str(source)


def literal_assignment(module: ast.Module, name: str) -> str | bytes:
    for node in module.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if isinstance(value, (str, bytes)):
                return value
    raise ValueError(f"Literal assignment {name!r} was not found")


def tar_payload_literal(module: ast.Module) -> str | bytes:
    """Find Path(...).write_bytes(base64.b64decode(<literal>))."""
    matches: list[str | bytes] = []
    for node in ast.walk(module):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "write_bytes" or len(node.args) != 1:
            continue
        decode = node.args[0]
        if not isinstance(decode, ast.Call) or len(decode.args) != 1:
            continue
        if not isinstance(decode.func, ast.Attribute) or decode.func.attr != "b64decode":
            continue
        value = ast.literal_eval(decode.args[0])
        if isinstance(value, (str, bytes)):
            matches.append(value)
    if len(matches) != 1:
        raise ValueError(f"Expected one literal archive payload, found {len(matches)}")
    return matches[0]


def decode_agent(spec: PackedAgent) -> dict[str, bytes]:
    notebook_path = ROOT / spec.notebook
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    source = source_text(notebook["cells"][spec.cell_index])
    module = ast.parse(source, filename=str(notebook_path))

    if spec.encoding == "tar_b64_call":
        archive_bytes = base64.b64decode(tar_payload_literal(module))
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
            names = archive.getnames()
            allowed = {"main.py", "observation.py", "model.json", "actions.json"}
            if set(names) != allowed or any(Path(name).name != name for name in names):
                raise ValueError(f"Unexpected archive members: {names}")
            files: dict[str, bytes] = {}
            for name in names:
                handle = archive.extractfile(name)
                if handle is None:
                    raise ValueError(f"{name} is missing from archive")
                files[name] = handle.read()
            return files

    if spec.variable is None:
        raise ValueError("Packed variable is required")
    payload = literal_assignment(module, spec.variable)
    if spec.encoding == "zlib_b64":
        return {"main.py": zlib.decompress(base64.b64decode(payload))}
    if spec.encoding == "zlib_b85":
        return {"main.py": zlib.decompress(base64.b85decode(payload))}
    if spec.encoding == "b64":
        return {"main.py": base64.b64decode(payload)}
    raise ValueError(f"Unsupported encoding: {spec.encoding}")


def main() -> None:
    for name, spec in SPECS.items():
        files = decode_agent(spec)
        source = files["main.py"]
        digest = hashlib.sha256(source).hexdigest()
        if spec.expected_sha256 and digest != spec.expected_sha256:
            raise ValueError(
                f"Digest mismatch for {name}: expected {spec.expected_sha256}, got {digest}"
            )
        compile(source, f"{name}/main.py", "exec")
        destination_root = ROOT / "agents" / name
        destination_root.mkdir(parents=True, exist_ok=True)
        for filename, data in files.items():
            (destination_root / filename).write_bytes(data)
        print(
            f"{name}: {len(source)} main.py bytes sha256={digest} "
            f"files={','.join(sorted(files))}"
        )


if __name__ == "__main__":
    main()
