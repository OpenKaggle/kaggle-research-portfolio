#!/usr/bin/env python3
"""Extract Markdown and Python cells from a Jupyter notebook for review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("notebook", type=Path)
    args = parser.parse_args()

    notebook = json.loads(args.notebook.read_text(encoding="utf-8"))
    code_path = args.notebook.with_suffix(".py")
    markdown_path = args.notebook.with_suffix(".md")

    code_parts = []
    markdown_parts = []
    for index, cell in enumerate(notebook.get("cells", [])):
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        if cell.get("cell_type") == "code":
            code_parts.append(f"# %% [cell {index}]\n{source.rstrip()}\n")
        elif cell.get("cell_type") == "markdown":
            markdown_parts.append(f"<!-- cell {index} -->\n{source.rstrip()}\n")

    code_path.write_text("\n".join(code_parts), encoding="utf-8")
    markdown_path.write_text("\n".join(markdown_parts), encoding="utf-8")
    print(f"code={code_path} cells={len(code_parts)}")
    print(f"markdown={markdown_path} cells={len(markdown_parts)}")


if __name__ == "__main__":
    main()
