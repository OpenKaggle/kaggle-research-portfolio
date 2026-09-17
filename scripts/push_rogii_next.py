from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


GPU_RUNNING = [
    # Observed remote slugs from `kaggle kernels list --mine -v`.
    "jahyee/rogii-plagiagia-top3-cbfix",
    "jahyee/rogii-biohack-fixed-weight-blend",
]

CPU_RUNNING = [
    "jahyee/rogii-suneet-lb900",
    "jahyee/rogii-raunak-ultra-sub9-codex",
    "jahyee/rogii-torrreeesss-9637-gbdt-stack2-codex",
    "jahyee/rogii-sanidhya-9946-cpu",
    "jahyee/rogii-qujiahui-9608-cpu-codex",
    "jahyee/rogii-thbdh-v11-fresh-artifact-r2-codex",
]

GPU_QUEUE = [
    "kernels/aliafzal_fresh_codex",
    "kernels/byron_v42_codex",
    "kernels/gruuby_baseline_9956_codex",
    "kernels/kojimar_pf_beam_tabicl_codex",
    "kernels/needless_score_10081_rank32",
    "kernels/thbdh_v4_aeroridge_cache_tabicl",
    "kernels/safar_lb9633",
    "kernels/agentzz_super_solution_top3",
    "kernels/zhen_exp119_ajay_cached_lgbcb",
]

CPU_QUEUE = [
    "kernels/thbdh_v11_fresh_artifact_infer",
    "kernels/thbdh_v10_fresh_artifact_infer",
    "kernels/praxel_zhen110_exact100_w100_codex",
    "kernels/yoshi70_ulas_treeonly_blend_gc2_codex",
    "kernels/praxel_zhen111_exact100_w280_codex",
    "kernels/tasmim_9804_cpu_codex",
    "kernels/shiny_triple_signal_beam_pf_lgb",
    "kernels/rishabh_v5_typewellwindowstats",
    "kernels/konbu_plane_fit_formation_top_knn",
    "kernels/llkh0a_lgbm_aug_online_training",
    "kernels/llkh0a_lgbm_aug",
    "kernels/shiny_better_baseline_particle_filter",
    "kernels/yuki_lgbm_gr_typewell_corr",
    "kernels/qiyue_pf_physical_submission",
]

RUNNING_MARKERS = {
    "KernelWorkerStatus.RUNNING",
    "KernelWorkerStatus.QUEUED",
    "KernelWorkerStatus.PREPARING",
}


def kaggle_bin() -> Path:
    candidate = Path(".venv/bin/kaggle")
    if candidate.exists():
        return candidate
    return Path(sys.executable).with_name("kaggle")


def kernel_status(kernel: str) -> str:
    result = subprocess.run(
        [str(kaggle_bin()), "kernels", "status", kernel],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return result.stdout.strip()


def is_running(status: str) -> bool:
    return any(marker in status for marker in RUNNING_MARKERS)


def read_kernel_id(folder: str) -> str:
    metadata = Path(folder) / "kernel-metadata.json"
    with metadata.open() as f:
        return json.load(f)["id"]


def first_uncreated(queue: list[str]) -> str | None:
    for folder in queue:
        kernel_id = read_kernel_id(folder)
        status = kernel_status(kernel_id)
        if "COMPLETE" in status or "RUNNING" in status or "QUEUED" in status or "PREPARING" in status:
            print(f"skip {folder}: {kernel_id} already has status: {status}")
            continue
        return folder
    return None


def push(folder: str, dry_run: bool) -> int:
    kernel_id = read_kernel_id(folder)
    print(f"next: {folder} -> {kernel_id}")
    if dry_run:
        return 0
    result = subprocess.run(
        [str(kaggle_bin()), "kernels", "push", "-p", folder],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    print(result.stdout.strip())
    return result.returncode


def maybe_push(kind: str, dry_run: bool) -> int:
    if kind == "gpu":
        running = [(k, kernel_status(k)) for k in GPU_RUNNING]
        active = [(k, s) for k, s in running if is_running(s)]
        print(f"gpu active={len(active)}/2")
        for k, s in running:
            print(f"  {k}: {s}")
        if len(active) >= 2:
            print("GPU batch is full; not pushing.")
            return 0
        folder = first_uncreated(GPU_QUEUE)
    else:
        running = [(k, kernel_status(k)) for k in CPU_RUNNING]
        active = [(k, s) for k, s in running if is_running(s)]
        print(f"cpu active={len(active)}/5")
        for k, s in running:
            print(f"  {k}: {s}")
        if len(active) >= 5:
            print("CPU batch is full; not pushing.")
            return 0
        folder = first_uncreated(CPU_QUEUE)

    if folder is None:
        print(f"No {kind} candidate left in queue.")
        return 0
    return push(folder, dry_run)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=["gpu", "cpu", "both"], default="both")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rc = 0
    kinds = ["gpu", "cpu"] if args.kind == "both" else [args.kind]
    for kind in kinds:
        rc = max(rc, maybe_push(kind, args.dry_run))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
