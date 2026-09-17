#!/usr/bin/env python3
"""Build the first owned ARC-AGI-2 Kaggle notebook candidate.

The public 11-hour hybrid is retained byte-for-byte except for a provenance
cell and a fixed, conservative selector choice.  The selector uses TRM only
when its epoch-2000 and epoch-4000 rank-one outputs agree; otherwise it keeps
NVARC rank two.  If both NVARC slots and TRM rank one duplicate the anchor,
distinct TRM rank two fills the otherwise wasted slot.  This choice is
label-free at competition rerun time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil


def source_text(cell: dict) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else source


def set_source(cell: dict, text: str) -> None:
    cell["source"] = text


def main() -> None:
    root = pathlib.Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-dir",
        type=pathlib.Path,
        default=root / "public_notebooks/hybrid_safe_11h",
    )
    parser.add_argument(
        "--out-dir",
        type=pathlib.Path,
        default=root / "candidate_notebooks/conservative_agreement_v1",
    )
    parser.add_argument("--owner", default="jahyee")
    parser.add_argument(
        "--benchmark-split",
        choices=("development", "holdout"),
        default="development",
    )
    parser.add_argument(
        "--stable-task-seed",
        action="store_true",
        help="replace Python's process-randomized hash with public BLAKE2b task seeding",
    )
    parser.add_argument(
        "--exact-blindspot-overlay",
        action="store_true",
        help="embed the V176 two-rule exact overlay after the conservative neural merge",
    )
    args = parser.parse_args()

    notebooks = sorted(args.source_dir.glob("*.ipynb"))
    if len(notebooks) != 1:
        raise SystemExit(f"expected one source notebook in {args.source_dir}, found {len(notebooks)}")
    metadata_path = args.source_dir / "kernel-metadata.json"
    if not metadata_path.is_file():
        raise SystemExit(f"missing {metadata_path}")

    notebook = json.loads(notebooks[0].read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    replaced_policy = 0
    replaced_labels = 0
    inserted_rank2_fallback = 0
    replaced_benchmark_split = 0
    replaced_task_seed = 0
    inserted_exact_overlay = 0
    for cell in notebook["cells"]:
        text = source_text(cell)
        if "'--policy', 'evidence'," in text:
            text = text.replace("'--policy', 'evidence',", "'--policy', 'agreement',")
            replaced_policy += 1
        if args.benchmark_split == "holdout" and "deterministic_order[:tasks_per_quartile]" in text:
            text = text.replace(
                "deterministic_order[:tasks_per_quartile]",
                "deterministic_order[tasks_per_quartile:2 * tasks_per_quartile]",
            )
            replaced_benchmark_split += 1
        if args.stable_task_seed and "seed=hash(bk) % 1024**2" in text:
            if "import gc\nimport os" not in text:
                raise RuntimeError("arc_solver import anchor missing")
            text = text.replace("import gc\nimport os", "import gc\nimport hashlib\nimport os")
            text = text.replace(
                "aug_dataset = aug_dataset.augment(seed=hash(bk) % 1024**2)",
                "stable_task_seed = int.from_bytes(\n"
                "                                hashlib.blake2b(\n"
                "                                    bk.encode('utf-8'), digest_size=8\n"
                "                                ).digest(), 'big'\n"
                "                            ) % 1024**2\n"
                "                            aug_dataset = aug_dataset.augment(seed=stable_task_seed)",
            )
            replaced_task_seed += 1
        substitutions = {
            "NVARC rank 1 plus TRM rank 1, with distinct fallbacks": (
                "NVARC rank 1 plus checkpoint-agreed TRM rank 1; otherwise NVARC rank 2"
            ),
            'benchmark_submissions["evidence_merge"]': (
                'benchmark_submissions["agreement_merge"]'
            ),
            'evidence_submission = load_submission(final_path)': (
                'agreement_submission = load_submission(final_path)'
            ),
            'benchmark_submissions["agreement_merge"] = evidence_submission': (
                'benchmark_submissions["agreement_merge"] = agreement_submission'
            ),
        }
        for old, new in substitutions.items():
            if old in text:
                text = text.replace(old, new)
                replaced_labels += 1
        merge_marker = "        ], check=True)\n        from trm_runtime import find_challenge, validate_submission"
        if "str(trm_source / 'merge_agreement.py')" in text and merge_marker in text:
            fallback = '''        ], check=True)

        # The upstream agreement policy falls back to the input grid when
        # NVARC1, NVARC2, and TRM1 are identical. Preserve two distinct
        # hypotheses by using valid TRM2 in exactly that otherwise-wasted case.
        agreement_submission = json.loads(final_path.read_text(encoding='utf-8'))
        nvarc_submission = json.loads(nvarc_path.read_text(encoding='utf-8'))
        trm_final_submission = json.loads(trm_final_path.read_text(encoding='utf-8'))
        rank2_fills = 0
        for task_id, rows in agreement_submission.items():
            for output_index, row in enumerate(rows):
                nrow = nvarc_submission[task_id][output_index]
                trow = trm_final_submission[task_id][output_index]
                anchor = nrow['attempt_1']
                if (
                    nrow['attempt_2'] == anchor
                    and trow['attempt_1'] == anchor
                    and trow['attempt_2'] != anchor
                ):
                    row['attempt_2'] = trow['attempt_2']
                    rank2_fills += 1
        final_path.write_text(json.dumps(agreement_submission), encoding='utf-8')
        print(f'Distinct TRM rank-two fallback fills: {rank2_fills}')

        from trm_runtime import find_challenge, validate_submission'''
            text = text.replace(merge_marker, fallback)
            inserted_rank2_fallback += 1
        overlay_marker = "    # Independent fail-closed schema validation, including the NVARC fallback."
        if args.exact_blindspot_overlay and overlay_marker in text:
            overlay = '''    # V176 exact overlay: the fixed rules see demonstrations and test inputs only.
    # Attempt one is immutable; attempt two changes only for one unique rule grid.
    exact_overlay_receipt = Path('/kaggle/working/exact-overlay-receipt.json')
    subprocess.run([
        sys.executable,
        '/kaggle/working/blindspot_exact_overlay.py',
        '--challenge', str(challenge_path),
        '--base', str(final_path),
        '--output', str(final_path),
        '--receipt', str(exact_overlay_receipt),
        '--rules',
        'scale_by_distinct_color_count',
        'reconstruct_centered_square_perimeters',
    ], check=True)
    print('Applied solution-blind V176 exact overlay')

'''
            text = text.replace(overlay_marker, overlay + overlay_marker)
            inserted_exact_overlay += 1
        if args.exact_blindspot_overlay:
            text = text.replace(
                'benchmark_submissions["agreement_merge"] = agreement_submission',
                'benchmark_submissions["agreement_exact_v176"] = agreement_submission',
            )
        set_source(cell, text)

    if replaced_policy != 1:
        raise RuntimeError(f"expected one selector replacement, found {replaced_policy}")
    if inserted_rank2_fallback != 1:
        raise RuntimeError(f"expected one rank-two fallback insertion, found {inserted_rank2_fallback}")
    if args.benchmark_split == "holdout" and replaced_benchmark_split != 1:
        raise RuntimeError(
            f"expected one holdout benchmark replacement, found {replaced_benchmark_split}"
        )
    if args.stable_task_seed and replaced_task_seed != 1:
        raise RuntimeError(f"expected one stable-seed replacement, found {replaced_task_seed}")
    if args.exact_blindspot_overlay and inserted_exact_overlay != 1:
        raise RuntimeError(
            f"expected one exact-overlay insertion, found {inserted_exact_overlay}"
        )
    if "evidence_submission" in "\n".join(source_text(cell) for cell in notebook["cells"]):
        raise RuntimeError("stale evidence_submission name remains")

    overlay_module = root / "public_assets/trm_source/blindspot_exact_overlay.py"
    overlay_sha256 = hashlib.sha256(overlay_module.read_bytes()).hexdigest()
    provenance = {
        "cell_type": "markdown",
        "metadata": {},
        "source": (
            f"# ARC2 conservative agreement "
            f"{'exact-overlay v3' if args.exact_blindspot_overlay else ('stable v2' if args.stable_task_seed else 'v1')}\n\n"
            "Owned orchestration candidate derived from Alissa King's public 11-hour "
            "NVARC/TRM notebook.  The neural generators, public inputs, licenses, and "
            "runtime guard are unchanged.  The only algorithmic change is a fixed "
            "label-free second-attempt policy: use TRM rank one only when epoch 2,000 "
            "and epoch 4,000 agree; otherwise retain NVARC rank two.  A distinct TRM "
            "rank-two grid fills the slot only when NVARC1, NVARC2, and TRM1 all "
            "duplicate one another.  Public-evaluation "
            f"solutions are never read during a competition rerun.  The normal-run "
            f"benchmark split is fixed to `{args.benchmark_split}` before any neural "
            "benchmark result is observed.  "
            + (
                "Augmentation scoring uses the public BLAKE2b task-ID seed instead of "
                "Python's process-randomized hash.\n"
                if args.stable_task_seed
                else "This control preserves the upstream process-randomized task hash.\n"
            )
            + (
                "After the neural merge, a frozen two-rule V176 overlay may replace only "
                "attempt two when one demonstration-exact grid is unique; attempt one is "
                "immutable. The rules were developed on the public-training development "
                "misses, so their 50/50 development result is post hoc and requires a "
                f"prospective sealed-holdout test. Embedded overlay SHA-256: `{overlay_sha256}`.\n"
                if args.exact_blindspot_overlay
                else ""
            )
        ),
    }
    notebook["cells"].insert(0, provenance)
    if args.exact_blindspot_overlay:
        notebook["cells"].insert(
            1,
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": (
                    "%%writefile /kaggle/working/blindspot_exact_overlay.py\n"
                    + overlay_module.read_text(encoding="utf-8")
                ),
            },
        )
        notebook.setdefault("metadata", {})["arc_exact_overlay"] = {
            "version": "v176",
            "source_sha256": overlay_sha256,
            "selection": "unique grid from fixed rules exact on every demonstration",
            "attempt_1_immutable": True,
            "development_status": "post_hoc_50_of_50_not_generalization_evidence",
            "sealed_holdout_status": "unopened",
        }

    base_slug = (
        "arc2-conservative-exact-overlay-v3"
        if args.exact_blindspot_overlay
        else (
            "arc2-conservative-agreement-stable-v2"
            if args.stable_task_seed
            else "arc2-conservative-agreement-v1"
        )
    )
    suffix = "" if args.benchmark_split == "development" else "-holdout"
    title_suffix = "" if args.benchmark_split == "development" else " Holdout"
    version_title = (
        "Exact Overlay V3"
        if args.exact_blindspot_overlay
        else ("Stable V2" if args.stable_task_seed else "V1")
    )
    # `id_no` is the upstream author's immutable kernel identifier. Carrying it
    # into a new owner/slug makes Kaggle treat SaveKernel as an unauthorized
    # update instead of a create operation.
    metadata.pop("id_no", None)
    metadata.update(
        {
            "id": f"{args.owner}/{base_slug}{suffix}",
            "title": f"ARC2 Conservative Agreement {version_title}{title_suffix}",
            "code_file": f"{base_slug}{suffix}.ipynb",
            "enable_gpu": True,
            "enable_internet": False,
            # Owned candidates remain private until the frozen validation gates
            # have passed and the owner explicitly chooses to publish them.
            "is_private": True,
        }
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    notebook_path = args.out_dir / metadata["code_file"]
    notebook_path.write_text(
        json.dumps(notebook, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    (args.out_dir / "kernel-metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    shutil.copy2(args.source_dir / "kernel-metadata.json", args.out_dir / "upstream-kernel-metadata.json")
    print(f"wrote {notebook_path}")
    print(
        f"selector replacements: {replaced_policy}; label cleanups: {replaced_labels}; "
        f"rank-two fallbacks: {inserted_rank2_fallback}; "
        f"exact overlay: {inserted_exact_overlay}; benchmark split: {args.benchmark_split}; "
        f"stable seed: {args.stable_task_seed}"
    )


if __name__ == "__main__":
    main()
