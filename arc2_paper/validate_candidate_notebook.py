#!/usr/bin/env python3
"""Static preflight for the owned ARC-AGI-2 Kaggle notebook candidate."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import pathlib


REQUIRED_DATASETS = {
    "christopherdaleman/arc-proof-search-trm-2026-source",
    "cpmpml/arc-prize-trm-031",
}
REQUIRED_MODELS = {
    "sorokin/qwen3_4b_grids15_sft139/Transformers/bfloat16/1",
}


def source_text(cell: dict) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else source


def validate_python_cell(text: str, cell_index: int) -> None:
    stripped = text.lstrip()
    if stripped.startswith("%%writefile "):
        _, _, payload = stripped.partition("\n")
        ast.parse(payload, filename=f"notebook-cell-{cell_index}-writefile")
    elif not stripped.startswith(("!", "%")):
        ast.parse(text, filename=f"notebook-cell-{cell_index}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_dir", type=pathlib.Path)
    args = parser.parse_args()

    metadata_path = args.candidate_dir / "kernel-metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    notebook_path = args.candidate_dir / metadata["code_file"]
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    code = "\n".join(
        source_text(cell) for cell in notebook["cells"] if cell.get("cell_type") == "code"
    )

    assert metadata["id"].startswith("jahyee/")
    assert "id_no" not in metadata, "owned candidate must not inherit an upstream kernel id"
    assert metadata["is_private"] is True, "owned pre-submission candidate must be private"
    assert metadata["enable_gpu"] is True
    assert metadata["enable_internet"] is False
    assert set(metadata["dataset_sources"]) == REQUIRED_DATASETS
    assert set(metadata["model_sources"]) == REQUIRED_MODELS
    assert metadata["competition_sources"] == ["arc-prize-2026-arc-agi-2"]
    assert code.count("'--policy', 'agreement',") == 1
    assert "'--policy', 'evidence'," not in code
    assert "KAGGLE_IS_COMPETITION_RERUN" in code
    assert "global_end_time = time.time() + 11 * 3600" in code
    assert "/kaggle/working/submission.json" in code
    assert "set(final_submission) == set(challenges)" in code
    assert "Distinct TRM rank-two fallback fills" in code
    assert "arc-agi_evaluation_solutions.json" in code
    assert "if not rerun_mode" in code or "not competition_rerun" in code
    if "stable-v2" in metadata["id"]:
        assert "hashlib.blake2b" in code
        assert "seed=hash(bk) % 1024**2" not in code
    if "exact-overlay-v3" in metadata["id"]:
        assert "hashlib.blake2b" in code
        assert "seed=hash(bk) % 1024**2" not in code
        assert code.count("%%writefile /kaggle/working/blindspot_exact_overlay.py") == 1
        assert code.count("Applied solution-blind V176 exact overlay") == 1
        assert "--base', str(final_path)" in code
        assert "--output', str(final_path)" in code
        assert "scale_by_distinct_color_count" in code
        assert "reconstruct_centered_square_perimeters" in code
        overlay_metadata = notebook["metadata"]["arc_exact_overlay"]
        assert overlay_metadata["version"] == "v176"
        assert overlay_metadata["attempt_1_immutable"] is True
        overlay_cells = [
            source_text(cell)
            for cell in notebook["cells"]
            if source_text(cell).startswith(
                "%%writefile /kaggle/working/blindspot_exact_overlay.py\n"
            )
        ]
        assert len(overlay_cells) == 1
        _, _, overlay_source = overlay_cells[0].partition("\n")
        assert hashlib.sha256(overlay_source.encode("utf-8")).hexdigest() == overlay_metadata[
            "source_sha256"
        ]
        assert "_solutions.json" not in overlay_source
        assert "submission[task_id][output_index][\"attempt_2\"] = prediction" in overlay_source
        assert "submission[task_id][output_index][\"attempt_1\"] =" not in overlay_source

    for index, cell in enumerate(notebook["cells"]):
        if cell.get("cell_type") == "code":
            validate_python_cell(source_text(cell), index)

    print(
        json.dumps(
            {
                "candidate": str(notebook_path),
                "cells": len(notebook["cells"]),
                "selector": (
                    "checkpoint agreement -> TRM1; otherwise NVARC2; distinct TRM2 only "
                    "for a duplicated slot; optional unique exact overlay when embedded"
                ),
                "internet": metadata["enable_internet"],
                "gpu": metadata["enable_gpu"],
                "private": metadata["is_private"],
                "status": "static_preflight_passed",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
