from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


KERNEL_OUTPUTS = {
    # These slugs follow the actual remote notebook ids returned by
    # `kaggle kernels list --mine -v`; some local metadata ids include a
    # `-codex` suffix that Kaggle does not currently expose for the run.
    "jahyee/rogii-h-blend-v1": "h_blend_v1",
    "jahyee/rogii-plagiagia-top3-cbfix": "plagiagia_top3_cbfix_v1",
    "jahyee/rogii-biohack-fixed-weight-blend": "biohack_fixed_weight_blend_v1",
    "jahyee/rogii-suneet-lb900": "suneet_lb900_v2",
    "jahyee/rogii-afr1ste-pf-beam-tabicl": "afr1ste_pf_beam_tabicl_v1",
    "jahyee/rogii-aidensong-sel15-rerun-codex": "aidensong_sel15_v1",
    "jahyee/rogii-aidensong-genuine-pf-v2-codex": "aidensong_genuine_pf_v2_v1",
    "jahyee/rogii-raunak-ultra-sub9-codex": "raunak_ultra_sub9_v4",
    "jahyee/rogii-k1nsom-lgb-relative-codex": "k1nsom_lgb_relative_v1",
    "jahyee/rogii-torrreeesss-9637-gbdt-stack2-codex": "torrreeesss_9637_gbdt_stack2_v1",
    "jahyee/rogii-sanidhya-9946-cpu": "sanidhya_9946_cpu_v1",
    "jahyee/rogii-qujiahui-9608-cpu-codex": "qujiahui_9608_cpu_v1",
    "jahyee/rogii-sunny-tvt-physical-codex": "sunny_physical_v1",
    "jahyee/rogii-jamie-sunny-pf-v12-codex": "jamie_pf_v12_v1",
    "jahyee/rogii-typewell-gr-pf3-codex": "aliafzal_typewell_gr_pf3_v1",
    "jahyee/rogii-byron-v42-codex": "byron_v42_v1",
    "jahyee/rogii-gruuby-baseline-9956-codex": "gruuby_baseline_9956_v1",
    "jahyee/rogii-kojimar-pf-beam-tabicl-codex": "kojimar_pf_beam_tabicl_v1",
    "jahyee/rogii-thbdh-v11-fresh-artifact-r2-codex": "thbdh_v11_fresh_artifact_r2_v1",
    "jahyee/rogii-thbdh-v10-fresh-artifact-codex": "thbdh_v10_fresh_artifact_v1",
    "jahyee/rogii-zhen110-exact100-w100-codex": "zhen110_exact100_w100_v1",
    "jahyee/rogii-yoshi70-treeonly-blend-gc2-codex": "yoshi70_treeonly_blend_gc2_v1",
    "jahyee/rogii-zhen111-exact100-w280-codex": "zhen111_exact100_w280_v1",
}

OUT_ROOT = Path("reports/kaggle_kernel_output")
LOG_ROOT = Path("reports/kaggle_kernel_logs")


def kaggle_bin() -> Path:
    candidate = Path(".venv/bin/kaggle")
    if candidate.exists():
        return candidate
    return Path(sys.executable).with_name("kaggle")


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(kaggle_bin()), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def status(kernel: str) -> str:
    return run(["kernels", "status", kernel]).stdout.strip()


def download(kernel: str, output_name: str, force: bool) -> bool:
    out_dir = OUT_ROOT / output_name
    sub = out_dir / "submission.csv"
    if sub.exists() and not force:
        print(f"exists: {kernel} -> {sub}")
        return False
    out_dir.mkdir(parents=True, exist_ok=True)
    args = ["kernels", "output", kernel, "-p", str(out_dir)]
    if force:
        args.append("--force")
    result = run(args)
    print(result.stdout.strip())
    return result.returncode == 0


def save_logs(kernel: str, output_name: str) -> None:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    result = run(["kernels", "logs", kernel])
    log_path = LOG_ROOT / f"{output_name}.log"
    log_path.write_text(result.stdout)
    print(f"log: {kernel} -> {log_path}")


def validate_outputs() -> int:
    result = subprocess.run(
        [sys.executable, "scripts/validate_rogii_outputs.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    print(result.stdout.strip())
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--validate", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    downloaded = 0
    for kernel, output_name in KERNEL_OUTPUTS.items():
        st = status(kernel)
        print(f"{kernel}: {st}")
        if "KernelWorkerStatus.COMPLETE" in st:
            if download(kernel, output_name, args.force):
                downloaded += 1
        elif "KernelWorkerStatus.ERROR" in st or "KernelWorkerStatus.CANCEL" in st:
            save_logs(kernel, output_name)

    if args.validate:
        validate_outputs()
    print(f"downloaded={downloaded}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
