from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from kaggle.api.kaggle_api_extended import KaggleApi
from kagglesdk.competitions.types.competition_api_service import ApiGetSubmissionRequest


COMPETITION = "rogii-wellbore-geology-prediction"

SUBMISSION_REFS = [
    53286289,  # H Blend Sidecar Codex v1 hidden-compatible
    53285564,  # AeroRidge v34 Codex kernel v1
    53285563,  # DWT LGB4 Codex kernel v1
    53285318,  # Ravaghi HC LGB4 Codex kernel v3
    53285597,  # Static writer, known hidden-format failure
]

KERNELS = [
    # Use the actual remote notebook ids returned by
    # `kaggle kernels list --mine -v`; several local metadata ids include a
    # `-codex` suffix that currently 404s via the status endpoint.
    "jahyee/rogii-h-blend-v1",
    "jahyee/rogii-plagiagia-top3-cbfix",
    "jahyee/rogii-biohack-fixed-weight-blend",
    "jahyee/rogii-suneet-lb900",
    "jahyee/rogii-afr1ste-pf-beam-tabicl",
    "jahyee/rogii-aidensong-sel15-rerun-codex",
    "jahyee/rogii-aidensong-genuine-pf-v2-codex",
    "jahyee/rogii-raunak-ultra-sub9-codex",
    "jahyee/rogii-k1nsom-lgb-relative-codex",
    "jahyee/rogii-torrreeesss-9637-gbdt-stack2-codex",
    "jahyee/rogii-sanidhya-9946-cpu",
    "jahyee/rogii-qujiahui-9608-cpu-codex",
    "jahyee/rogii-sunny-tvt-physical-codex",
    "jahyee/rogii-jamie-sunny-pf-v12-codex",
    "jahyee/rogii-typewell-gr-pf3-codex",
    "jahyee/rogii-byron-v42-codex",
    "jahyee/rogii-gruuby-baseline-9956-codex",
    "jahyee/rogii-kojimar-pf-beam-tabicl-codex",
    "jahyee/rogii-thbdh-v11-fresh-artifact-r2-codex",
    "jahyee/rogii-thbdh-v10-fresh-artifact-codex",
    "jahyee/rogii-zhen110-exact100-w100-codex",
    "jahyee/rogii-yoshi70-treeonly-blend-gc2-codex",
    "jahyee/rogii-zhen111-exact100-w280-codex",
]


def print_submissions() -> None:
    api = KaggleApi()
    api.authenticate()
    print("Official submissions")
    with api.build_kaggle_client() as kg:
        for ref in SUBMISSION_REFS:
            request = ApiGetSubmissionRequest()
            request.ref = ref
            submission = kg.competitions.competition_api_client.get_submission(request)
            print(
                f"{ref}: {submission.status} "
                f"public={submission.public_score!r} "
                f"error={submission.error_description!r} "
                f"desc={submission.description}"
            )


def print_kernels() -> None:
    kaggle = Path(".venv/bin/kaggle")
    if not kaggle.exists():
        kaggle = Path(sys.executable).with_name("kaggle")
    print("\nKernels")
    for kernel in KERNELS:
        result = subprocess.run(
            [str(kaggle), "kernels", "status", kernel],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        print(result.stdout.strip() or f"{kernel}: no output")


def main() -> None:
    print_submissions()
    print_kernels()


if __name__ == "__main__":
    main()
