#!/usr/bin/env python3
"""Audit the Biohub campaign's frozen evidence and cross-file consistency."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "artifacts" / "campaign_integrity.json"
OFFICIAL_METRIC_COMMIT = "075fc5f5a52d11077f9dc2b074644618f26939e2"
OFFICIAL_METRIC_HASHES = {
    "metrics.py": "cfdd596e3f8909cca14db0682889738b19ff75c3808b3773175aba9367ca7444",
    "division_metrics.py": "0635c38621a38f1eb4b55a302b4a817a88e9094930dfc2dab16faeeee60f4dc9",
}
OOF_LOCAL_TOOL_HASHES = {
    "validate_oof_receipt.py": "45a150b226f849199820f22a964aa5cf9093d4740618522829da41f84c0f373a",
    "analyze_oof.py": "1f8b798e8b6a0c42c58cc9f1a097331bc58f9b17cfba22613313e7bb49ea3565",
    "finalize_oof.py": "61bda1be136fc60228c2115ada0c203c00094e7cd5c52bb9fe73d49f7d0d4da6",
    "finalize_oof_parent.py": "7ea007f87a6e1baac84774538136c31d06c56cde11b885fa5680c754c1c97e76",
    "validate_oof_recovery.py": "127f09970f14f62c9fd4603ebbc1142b81cbc6c0536f3cea922d6563b66bc79f",
    "record_oof_terminal.py": "dacdec99b28f2b4fe4771b7018b1db990fc9389acc0b156432ae90e5cd0f6d7c",
    "record_oof_recovery_launch.py": "8144227ee2359f2cef874218d4db7b681af58c6048df83e38e6570741cfd30b3",
    "record_oof_recovery_terminal.py": "e1ebe5ad07fc6775e795f90916d1711281f5c9ff07bf67f6baa6c420df96d937",
    "finalize_oof_recovery.py": "9d0ddd33450cca0032b38830834e11bfd8a968d186cbe9b24ce887558ff81cb2",
}
OOF_STATUS_TOOL_HASHES = {
    "sync_kernel_status.py": "db8ad0de7e980c0869baf8d8ebe5999ea233fa177a7a0313993af9d581da7dbd",
}
OOF_RECOVERY_BUILD_HASHES = {
    "prepare_oof_kernel.py": "9439f8a735e449801e1a0c12d2d12f2ea5f601447488eef272709628799ca13e",
    "build_oof_recovery_protocol.py": "4ccb840c699ab1c41a24b8fa6d19d9520b006ce871063da3bd1abb2a3eec3a40",
}
OOF_RECOVERY_ARTIFACT_HASHES = {
    "artifacts/budgeted_embryo_oof_1ep_recovery.json": "42853eb6259d2f9eddc24229fe9d52ede1f4801d8eb745ea71c323db9e078692",
    "kernels/biohub_budgeted_embryo_oof_1ep_recovery/biohub-budgeted-embryo-oof-1ep.py": "973cefd41399001af64992595991b2c0c1c38f85dfd4765970688f8e750137aa",
    "kernels/biohub_budgeted_embryo_oof_1ep_recovery/kernel-metadata.json": "b674dc62036f7d0561519c66c908458ddfc2cd7f31f366eff3fc2e41c109d6ed",
}
OOF_RECOVERY_MONITORING_HASHES = {
    "official/oof_recovery_status_20260909T121825Z.json": "f3859a29a05cbbbbd7913365e549fb5a70d5e60810a9661b7fa31058f2a7ac59",
    "artifacts/oof_recovery_monitoring_attempt_20260909T121825Z.json": "a5174b5961b7dcc1bd768847c037eef33bcb227d92846132b9ef8ade2cd1f3f6",
}
BASELINE_DELIVERY_HASHES = {
    "official/baseline_kernel_environment_status.json": "80ca298cf71970ba5580eeba740f09fc5a18f6dcf533de60270bd602a5b789cd",
    "artifacts/baseline_winner_delivery_provenance.json": "a0c5f636f650d08c35c8d879de5b3b5d4066860936b76b8091ca0f64f90c5b7a",
    "artifacts/baseline_dependency_license_inventory.json": "751ad7bf075b2ec74edd651ba55f4519f7b2dac0cb90e5cb55cafed7b249f306",
    "artifacts/baseline_dependency_license_archive.json": "6a5f7c2209f6ce3b8be01b5f4dc91ee4e9778e986268f17c9f4b29085474a6ba",
    "THIRD_PARTY_NOTICES.md": "e4453002114f5d882df18a386cbe2e33a6a8dec93f58f3b1e96bff6ab68b7ba2",
}
BASELINE_OFFLINE_WHEEL_HASHES = {
    "polars": "ab10cac3f2d28a6e22e22bcac69c0e51fb33cd25aee1f45105782d4fe55a3e6a",
    "tracksdata": "5111a9058edb31272fd5c6d01ccfe6146cf190ed96b100cb3d27411a6a91ff4d",
    "zarr": "f78cdd3d9687ad0e9f9cba2c5683b64f0c52589c19f685eeabe872e93cc0d2c7",
    "pyscipopt": "faf86357d83772508c5b1925570ee7e08385fa1a736e0ee33bf0e5c421dd845f",
    "geff": "5db41be6a31712ed90e07e444293cfa943df00d3cebae25bf9657e65d317df79",
    "geff-spec": "2e1bd5ba5c6186cc5bac24f93ac74821f2c7e6ce2a7aa0af791c00b6203af80d",
    "ilpy": "1c8e53144eafdaa1e59103543b9f05d38dfbf5819944f8b5766bd8a6f08fd6ab",
    "imagecodecs": "6e9e57171ce7cdf884e7d45d25427f77275321a0ddbd26941c5c90b242d2b597",
    "rustworkx": "7e0c626f76bc71d414a02502be7ec0ac2dd6eca369886bc66a2650607f2d9de6",
    "numcodecs": "c3a09e22140f2c691f7df26303ff8fa2dadcf26d7d0828398c0bc09b69e5efa3",
    "donfig": "2a3175ce74a06109ff9307d90a230f81215cbac9a751f4d1c6194644b8204f9d",
    "bidict": "5dae8d4d79b552a71cbabc7deb25dfe8ce710b17ff41711e13010ead2abfc3e5",
}
BASELINE_LICENSE_ARCHIVE_HASHES = {
    "polars": "8296022372dc83cc8ef234b3d4889ef8f8b1779754a78bebf13d2c5178a6b4c4",
    "tracksdata": "4e459930bb13a7e0ebbf8acc0f0be1bb973d4f0d095a54e1bd52b7cc27101683",
    "zarr": "1d7756f33d3da20d53b162c2eb9beba91ee0dc1aeb4659728b6dc8f2f75941cb",
    "pyscipopt": "ffb8710b46948fa08719ef0304c4f203176820e3f0d42488e30a7bb2f0fb13a2",
    "geff": "e75280f92560ef1864671579d76126af02678a7334b7487f52aa837fae773529",
    "geff-spec": "e75280f92560ef1864671579d76126af02678a7334b7487f52aa837fae773529",
    "ilpy": "e0dbe127b8595602917cce7f44a050aa24e8ad7648a3e8686331210ff52944f7",
    "imagecodecs": "3cf196b1625812d2d119518294043e71017fe858355a58eb48e1e35b61213ce9",
    "rustworkx": "5df2a0d87d6c562f0ea11c688ac52532aa28d744cabc7994ff0537f64b3b3320",
    "numcodecs": "949cac68479e13b6c97924635150b4e1ef5e69766ad9e472ea85a08c1576bb96",
    "donfig": "c29730b23ddc3e2e7cc6f181ddfb56e781d11e856c20d635a5f01dc8bdb643c6",
    "bidict": "f3f53adcecaa48d73a66e238fa5ba906cb41876783b45d28a1346b3142eebd9a",
}
OOF_RECOVERY_FAILED_TERMINAL_STATUSES = {
    "ERROR",
    "CANCELLED",
    "CANCEL_ACKNOWLEDGED",
}
OOF_RECOVERY_TERMINAL_EVIDENCE_NAMES = {
    "budgeted_oof_protocol.json",
    "budgeted_oof_partial.json",
    "budgeted_oof_receipt.json",
    "fold_0_train.log",
    "fold_0_predict.log",
    "fold_1_train.log",
    "fold_1_predict.log",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def finite_float(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def normalized_oof_source_sha256(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    substitutions = (
        (r"^PROTOCOL = .*?$", "PROTOCOL = <NORMALIZED>"),
        (
            r'^SOURCE_PROTOCOL_SHA256 = "[0-9a-f]{64}"$',
            "SOURCE_PROTOCOL_SHA256 = <NORMALIZED>",
        ),
        (r'^METHOD = ".*?"$', "METHOD = <NORMALIZED>"),
    )
    for pattern, replacement in substitutions:
        source, count = re.subn(
            pattern, replacement, source, count=1, flags=re.MULTILINE
        )
        if count != 1:
            raise ValueError(f"could not normalize OOF source field: {pattern}")
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def notebook_code(path: Path) -> str:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    return "\n\n".join(
        "".join(cell.get("source", []))
        for cell in notebook.get("cells", [])
        if cell.get("cell_type") == "code"
    )


def main() -> None:
    checks = []
    warnings = []

    def check(name: str, condition: bool, evidence) -> None:
        checks.append({"name": name, "pass": bool(condition), "evidence": evidence})

    official = load_json("official/receipt.json")
    competition = official["cli_state"][0]
    check("entered", competition["userHasEntered"] is True, competition["userHasEntered"])
    check("rules_accepted", official["rules_acceptance"]["accepted"] is True, official["rules_acceptance"])
    check(
        "submissions_enabled",
        competition["submissionsDisabled"] is False,
        {"submissionsDisabled": competition["submissionsDisabled"]},
    )
    check("notebook_only", competition["isKernelsSubmissionsOnly"] is True, competition["isKernelsSubmissionsOnly"])
    check("daily_quota", competition["maxDailySubmissions"] == 5, competition["maxDailySubmissions"])
    check("team_limit", competition["maxTeamSize"] == 5, competition["maxTeamSize"])
    check("prize_pool", competition["reward"] == "60,000 Usd", competition["reward"])
    check("final_deadline", competition["deadline"] == "2026-09-29T23:59:00.000Z", competition["deadline"])
    check("entry_deadline", competition["newEntrantDeadline"] == "2026-09-22T23:59:00.000Z", competition["newEntrantDeadline"])
    check("merger_deadline", competition["mergerDeadline"] == "2026-09-22T23:59:00.000Z", competition["mergerDeadline"])
    eligibility = load_json("artifacts/personal_eligibility_checklist.json")
    expected_confirmation_ids = [
        "age_of_majority",
        "eligible_residence",
        "not_sanctioned",
        "employer_or_entity_consent",
        "tax_and_prize_documents",
    ]
    eligibility_rows = eligibility.get("required_personal_confirmations", [])
    check(
        "personal_eligibility_confirmation_gate",
        eligibility.get("competition") == "biohub-cell-tracking-during-development"
        and eligibility.get("status") == "user_confirmation_required"
        and eligibility.get("official_rules_path") == "official/pages/rules.md"
        and eligibility.get("official_rules_sha256")
        == sha256(ROOT / "official" / "pages" / "rules.md")
        and eligibility.get("entry_state", {}).get("kaggle_permitted_entry") is True
        and eligibility.get("entry_state", {}).get("rules_accepted") is True
        and eligibility.get("entry_state", {}).get("prize_eligibility_verified")
        is False
        and [row.get("id") for row in eligibility_rows]
        == expected_confirmation_ids
        and all(row.get("confirmed") is None for row in eligibility_rows)
        and eligibility.get("unresolved_confirmation_ids")
        == expected_confirmation_ids,
        {
            "status": eligibility.get("status"),
            "prize_eligibility_verified": eligibility.get("entry_state", {}).get(
                "prize_eligibility_verified"
            ),
            "unresolved_confirmation_ids": eligibility.get(
                "unresolved_confirmation_ids"
            ),
        },
    )
    warnings.append(
        "Personal age, residence, sanctions, employer-policy and tax eligibility cannot be verified from workspace evidence."
    )

    repro = load_json("kernels/biohub_0946_public_deps_repro/REPRO_RECEIPT.json")
    deliverables = load_json("artifacts/winner_deliverables_checklist.json")
    source_metadata_path = ROOT / deliverables["third_party_rights"][
        "source_metadata_path"
    ]
    source_metadata = json.loads(source_metadata_path.read_text(encoding="utf-8"))
    source_license_fields = {
        key: source_metadata.get(key)
        for key in ("license", "license_name", "license_type")
        if key in source_metadata
    }
    expected_deliverable_ids = [
        "winning_submission_and_source_mit_license",
        "final_model_code_and_documentation",
        "training_and_inference_code",
        "environment_and_resources",
        "detailed_methodology",
        "recorded_technical_discussion",
        "eligibility_license_release_and_tax_documents",
    ]
    expected_release_blockers = [
        "source_code_mit_grant_right_unverified",
        "final_submission_and_model_not_selected",
        "training_inference_environment_package_not_complete",
        "final_reproducibility_documentation_not_complete",
        "personal_eligibility_and_prize_documents_unconfirmed",
    ]
    winner_docs_path = ROOT / deliverables["official_evidence"][
        "winning_model_documentation_guidelines"
    ]["path"]
    winner_docs = json.loads(winner_docs_path.read_text(encoding="utf-8"))
    rights = deliverables.get("third_party_rights", {})
    source_license_receipt_path = ROOT / rights.get(
        "source_page_license_receipt_path", ""
    )
    source_license_receipt = json.loads(
        source_license_receipt_path.read_text(encoding="utf-8")
    )
    check(
        "winner_deliverables_readiness_gate",
        deliverables.get("competition")
        == "biohub-cell-tracking-during-development"
        and deliverables.get("status") == "not_winner_delivery_ready"
        and deliverables.get("winner_readiness_verified") is False
        and deliverables.get("official_evidence", {}).get("rules", {}).get(
            "sha256"
        )
        == sha256(ROOT / "official" / "pages" / "rules.md")
        and deliverables.get("official_evidence", {})
        .get("code_requirements", {})
        .get("sha256")
        == sha256(ROOT / "official" / "pages" / "code-requirements.md")
        and deliverables.get("official_evidence", {}).get("prizes", {}).get(
            "sha256"
        )
        == sha256(ROOT / "official" / "pages" / "prizes.md")
        and deliverables.get("official_evidence", {})
        .get("winning_model_documentation_guidelines", {})
        .get("source_url")
        == "https://www.kaggle.com/WinningModelDocumentationGuidelines"
        and winner_docs.get("source_url")
        == "https://www.kaggle.com/WinningModelDocumentationGuidelines"
        and deliverables.get("official_evidence", {})
        .get("winning_model_documentation_guidelines", {})
        .get("sha256")
        == sha256(winner_docs_path)
        and winner_docs.get("retrieved_via")
        == "Authenticated official Kaggle web UI"
        and [
            component.get("id")
            for component in winner_docs.get("standard_components", [])
        ]
        == ["model_summary", "submission_model", "winner_presentation"]
        and all(
            component.get("requirements")
            for component in winner_docs.get("standard_components", [])
        )
        and deliverables.get("official_evidence", {})
        .get("source_notebook_license", {})
        .get("source_url")
        == "https://www.kaggle.com/code/reyhanksatria/biohub-cell-tracking-0-946-lb"
        and deliverables.get("official_evidence", {})
        .get("source_notebook_license", {})
        .get("sha256")
        == sha256(source_license_receipt_path)
        and source_license_receipt.get("source")
        == "Authenticated official Kaggle Notebook page"
        and source_license_receipt.get("kernel")
        == "reyhanksatria/biohub-cell-tracking-0-946-lb"
        and source_license_receipt.get("visibility") == "public"
        and source_license_receipt.get("license_spdx_identifier")
        == "Apache-2.0"
        and [row.get("id") for row in deliverables.get("official_requirements", [])]
        == expected_deliverable_ids
        and rights.get("source_kernel")
        == "reyhanksatria/biohub-cell-tracking-0-946-lb"
        and rights.get("source_kernel_public") is True
        and rights.get("source_metadata_sha256") == sha256(source_metadata_path)
        and rights.get("source_notebook_sha256")
        == sha256(ROOT / rights["source_notebook_path"])
        and rights.get("source_metadata_license_field_present") is False
        and not source_license_fields
        and rights.get("competition_public_code_use_basis_verified") is True
        and rights.get("source_page_license_spdx_identifier") == "Apache-2.0"
        and rights.get("exact_inbound_license_identifier_verified") is True
        and rights.get("unrestricted_mit_relicensing_right_verified") is False
        and rights.get("external_datasets") == repro["datasets"]
        and all(
            item.get("access") == "public" and item.get("license") == "CC0-1.0"
            for item in rights.get("external_datasets", [])
        )
        and rights.get("baseline_dependency_license_archive_path")
        == "artifacts/baseline_dependency_license_archive.json"
        and rights.get("primary_wheel_license_text_archive_complete") is True
        and rights.get("bundled_component_license_archive_complete") is False
        and rights.get("dependency_license_text_archive_complete") is False
        and deliverables.get("release_blocker_ids") == expected_release_blockers,
        {
            "status": deliverables.get("status"),
            "winner_readiness_verified": deliverables.get(
                "winner_readiness_verified"
            ),
            "source_metadata_license_fields": source_license_fields,
            "source_page_license_spdx_identifier": source_license_receipt.get(
                "license_spdx_identifier"
            ),
            "unrestricted_mit_relicensing_right_verified": rights.get(
                "unrestricted_mit_relicensing_right_verified"
            ),
            "release_blocker_ids": deliverables.get("release_blocker_ids"),
        },
    )
    warnings.append(
        "Winner-delivery readiness is not verified: the reused public source notebook is verified as Apache-2.0, but an unrestricted MIT winner-license grant for all reused source portions and the final sponsor-ready code/documentation package remain unresolved."
    )
    baseline_delivery_status = load_json(
        "official/baseline_kernel_environment_status.json"
    )
    baseline_delivery = load_json(
        "artifacts/baseline_winner_delivery_provenance.json"
    )
    baseline_dependency_inventory = load_json(
        "artifacts/baseline_dependency_license_inventory.json"
    )
    baseline_dependency_archive = load_json(
        "artifacts/baseline_dependency_license_archive.json"
    )
    baseline_delivery_actual_hashes = {
        relative: sha256(ROOT / relative) for relative in BASELINE_DELIVERY_HASHES
    }
    baseline_kernel_metadata_path = (
        ROOT / "kernels" / "biohub_0946_public_deps_repro" / "kernel-metadata.json"
    )
    baseline_kernel_metadata = json.loads(
        baseline_kernel_metadata_path.read_text(encoding="utf-8")
    )
    primary_artifact_manifest = load_json("public_assets/primary/ARTIFACT_MANIFEST.json")
    deepcenter_artifact_manifest = load_json(
        "public_assets/deepcenter/ARTIFACT_MANIFEST.json"
    )
    secondary_artifact_manifest = load_json(
        "public_assets/secondary/ARTIFACT_MANIFEST.json"
    )
    baseline_model_artifacts = {
        item.get("role"): item for item in baseline_delivery.get("model_artifacts", [])
    }
    expected_offline_versions = {
        "polars": "1.42.0",
        "tracksdata": "0.1.0rc6.dev3+g980c2d30a",
        "zarr": "3.2.1",
        "pyscipopt": "6.2.1",
        "geff": "1.2.0.1.1",
        "geff-spec": "1.1.1",
        "ilpy": "0.6.0",
        "imagecodecs": "2026.6.26",
        "rustworkx": "0.18.0",
        "numcodecs": "0.15.1",
        "donfig": "0.8.1.post1",
        "bidict": "0.23.1",
    }
    expected_offline_licenses = {
        "polars": "MIT",
        "tracksdata": "BSD-3-Clause",
        "zarr": "MIT",
        "pyscipopt": "MIT",
        "geff": "MIT",
        "geff-spec": "MIT",
        "ilpy": "MIT",
        "imagecodecs": "BSD-3-Clause",
        "rustworkx": "Apache-2.0",
        "numcodecs": "MIT",
        "donfig": "MIT",
        "bidict": "MPL-2.0",
    }
    dependency_inventory_packages = {
        item.get("name").lower(): item
        for item in baseline_dependency_inventory.get("packages", [])
    }
    baseline_dependency_inventory_valid = bool(
        baseline_dependency_inventory.get("status")
        == "exact_package_license_identifiers_verified"
        and baseline_dependency_inventory.get("official_run_binding", {}).get(
            "kernel"
        )
        == "jahyee/biohub-0-946-public-dependencies-repro"
        and baseline_dependency_inventory.get("official_run_binding", {}).get(
            "script_version_id"
        )
        == 348360183
        and baseline_dependency_inventory.get("official_run_binding", {}).get(
            "official_log_sha256"
        )
        == baseline_delivery_status.get("log_sha256")
        and baseline_dependency_inventory.get("official_run_binding", {}).get(
            "official_status_receipt_sha256"
        )
        == sha256(ROOT / "official" / "baseline_kernel_environment_status.json")
        and set(dependency_inventory_packages) == set(expected_offline_versions)
        and all(
            dependency_inventory_packages[name].get("version") == version
            and dependency_inventory_packages[name].get("license_spdx")
            == expected_offline_licenses[name]
            and str(dependency_inventory_packages[name].get("evidence_url", "")).startswith(
                "https://"
            )
            for name, version in expected_offline_versions.items()
        )
        and dependency_inventory_packages["tracksdata"].get("license_blob_sha")
        == "628d10094787ea8072264ae33467fed8cf271014"
        and dependency_inventory_packages["ilpy"].get("license_blob_sha")
        == "438b882a93d285f55b73dd6a4f360dc352a5a1a5"
        and dependency_inventory_packages["rustworkx"].get("license_blob_sha")
        == "68c771a099958211169377d766a7389422f5573d"
        and baseline_dependency_inventory.get("summary", {}).get("packages") == 12
        and baseline_dependency_inventory.get("summary", {}).get("license_counts")
        == {"MIT": 8, "BSD-3-Clause": 2, "Apache-2.0": 1, "MPL-2.0": 1}
        and baseline_dependency_inventory.get("summary", {}).get(
            "license_identifiers_complete"
        )
        is True
        and baseline_dependency_inventory.get("summary", {}).get(
            "primary_wheel_license_text_archive_path"
        )
        == "artifacts/baseline_dependency_license_archive.json"
        and baseline_dependency_inventory.get("summary", {}).get(
            "primary_wheel_license_text_archive_complete"
        )
        is True
        and baseline_dependency_inventory.get("summary", {}).get(
            "bundled_component_license_archive_complete"
        )
        is False
        and baseline_dependency_inventory.get("summary", {}).get(
            "license_text_archive_complete"
        )
        is False
        and baseline_dependency_inventory.get("summary", {}).get(
            "base_image_dependency_licenses_in_scope"
        )
        is False
    )
    dependency_archive_packages = {
        item.get("name").lower(): item
        for item in baseline_dependency_archive.get("packages", [])
    }
    dependency_archive_file_hashes = {
        name: sha256(ROOT / item["archive_path"])
        for name, item in dependency_archive_packages.items()
        if item.get("archive_path") and (ROOT / item["archive_path"]).is_file()
    }
    dependency_archive_summary = baseline_dependency_archive.get("summary", {})
    dependency_archive_inspection = baseline_dependency_archive.get(
        "wheel_inspection", {}
    )
    dependency_archive_unresolved = baseline_dependency_archive.get(
        "unresolved_binary_component_scope", {}
    )
    baseline_dependency_archive_valid = bool(
        baseline_dependency_archive.get("official_run_binding", {}).get("experiment_id")
        == "BH-0001"
        and baseline_dependency_archive.get("official_run_binding", {}).get("kernel")
        == "jahyee/biohub-0-946-public-dependencies-repro"
        and baseline_dependency_archive.get("official_run_binding", {}).get(
            "script_version_id"
        )
        == 348360183
        and baseline_dependency_archive.get("official_run_binding", {}).get(
            "official_log_sha256"
        )
        == baseline_delivery_status.get("log_sha256")
        and baseline_dependency_archive.get("distribution_source", {}).get(
            "primary_kaggle_dataset"
        )
        == "pilkwang/biohub-tracking-support-pack-50ep-v1"
        and baseline_dependency_archive.get("distribution_source", {}).get(
            "mirror_kaggle_dataset"
        )
        == "pilkwang/biohub-temporal-unet3d-seed314159-v1"
        and baseline_dependency_archive.get("distribution_source", {}).get(
            "dataset_licenses"
        )
        == {
            "pilkwang/biohub-tracking-support-pack-50ep-v1": "CC0-1.0",
            "pilkwang/biohub-temporal-unet3d-seed314159-v1": "CC0-1.0",
        }
        and baseline_dependency_archive.get("distribution_source", {}).get(
            "primary_selected_by_bh0001"
        )
        is True
        and baseline_dependency_archive.get("distribution_source", {}).get(
            "primary_to_mirror_exact_wheel_matches"
        )
        == 12
        and baseline_dependency_archive.get("distribution_source", {}).get(
            "primary_to_mirror_exact_wheel_mismatches"
        )
        == 0
        and baseline_dependency_archive.get("distribution_source", {}).get(
            "primary_to_mirror_wheel_bytes_equal"
        )
        is True
        and baseline_dependency_archive.get("distribution_source", {}).get(
            "wheel_files_retained"
        )
        is False
        and set(dependency_archive_packages) == set(expected_offline_versions)
        and all(
            dependency_archive_packages[name].get("version") == version
            and dependency_archive_packages[name].get("wheel_sha256")
            == BASELINE_OFFLINE_WHEEL_HASHES[name]
            and dependency_archive_packages[name].get("archive_sha256")
            == BASELINE_LICENSE_ARCHIVE_HASHES[name]
            and dependency_archive_file_hashes.get(name)
            == BASELINE_LICENSE_ARCHIVE_HASHES[name]
            for name, version in expected_offline_versions.items()
        )
        and sum(
            item.get("byte_exact") is True
            for item in dependency_archive_packages.values()
        )
        == 9
        and sum(
            item.get("byte_exact") is False
            and item.get("normalization")
            == "A final LF was added; textual content is otherwise identical."
            for item in dependency_archive_packages.values()
        )
        == 3
        and dependency_archive_inspection.get(
            "packages_with_embedded_license_file"
        )
        == 12
        and dependency_archive_inspection.get("packages_expected") == 12
        and dependency_archive_inspection.get("named_notice_files_found") == 0
        and dependency_archive_inspection.get(
            "wheel_primary_license_texts_archived"
        )
        is True
        and dependency_archive_inspection.get("archive_files_present") == 12
        and dependency_archive_unresolved.get("complete") is False
        and "pyscipopt.libs/libscip-d031042e.so.10.0"
        in dependency_archive_unresolved.get("pyscipopt_native_files_observed", [])
        and dependency_archive_unresolved.get("imagecodecs_native_scope")
        and dependency_archive_summary.get("exact_wheels_verified") == 12
        and dependency_archive_summary.get(
            "primary_wheel_license_files_archived"
        )
        == 12
        and dependency_archive_summary.get(
            "primary_wheel_license_archive_complete"
        )
        is True
        and dependency_archive_summary.get(
            "bundled_component_license_archive_complete"
        )
        is False
        and dependency_archive_summary.get(
            "base_image_dependency_license_archive_complete"
        )
        is False
        and dependency_archive_summary.get("overall_license_text_archive_complete")
        is False
        and dependency_archive_summary.get("winner_delivery_ready") is False
    )
    baseline_execution = baseline_delivery.get("official_execution", {})
    baseline_environment = baseline_delivery.get("compute_environment", {})
    baseline_source = baseline_delivery.get("source_code", {})
    baseline_offline = baseline_delivery.get(
        "offline_packages_installed_by_the_notebook", {}
    )
    baseline_readiness = baseline_delivery.get("readiness", {})
    delivery_asset_rows = {
        item.get("id"): item
        for item in deliverables.get("current_machine_verifiable_assets", [])
    }
    primary_delivery = baseline_model_artifacts.get("primary_graph_generator", {})
    deepcenter_delivery = baseline_model_artifacts.get("auxiliary_center_prior", {})
    secondary_delivery = baseline_model_artifacts.get("secondary_graph_generator", {})
    baseline_delivery_valid = bool(
        baseline_delivery_actual_hashes == BASELINE_DELIVERY_HASHES
        and baseline_delivery.get("experiment_id") == "BH-0001"
        and baseline_execution.get("kernel")
        == "jahyee/biohub-0-946-public-dependencies-repro"
        and baseline_execution.get("script_version_id") == 348360183
        and baseline_execution.get("run_url")
        == "https://www.kaggle.com/code/jahyee/biohub-0-946-public-dependencies-repro/edit/run/348360183"
        and baseline_execution.get("status") == "COMPLETE"
        and baseline_execution.get("failure_message") is None
        and baseline_execution.get("log_api_error") is None
        and baseline_execution.get("status_receipt_sha256")
        == sha256(ROOT / baseline_execution["status_receipt_path"])
        and baseline_execution.get("official_log_lines")
        == baseline_delivery_status.get("log_lines")
        and baseline_execution.get("official_log_sha256")
        == baseline_delivery_status.get("log_sha256")
        and baseline_delivery_status.get("source")
        == "Official Kaggle kernel status and execution log APIs"
        and baseline_delivery_status.get("kernel") == baseline_execution.get("kernel")
        and baseline_delivery_status.get("script_version_id")
        == baseline_execution.get("script_version_id")
        and baseline_delivery_status.get("run_url") == baseline_execution.get("run_url")
        and baseline_delivery_status.get("status") == "COMPLETE"
        and baseline_delivery_status.get("failure_message") is None
        and baseline_delivery_status.get("log_api_error") is None
        and baseline_environment.get("kernel_metadata_sha256")
        == sha256(baseline_kernel_metadata_path)
        and baseline_environment.get("container_image")
        == baseline_kernel_metadata.get("docker_image")
        and baseline_environment.get("accelerator")
        == baseline_kernel_metadata.get("machine_shape")
        and baseline_environment.get("internet_enabled") is False
        and baseline_environment.get("base_image_package_freeze_available") is False
        and baseline_source.get("upstream_notebook_sha256")
        == sha256(ROOT / baseline_source["upstream_notebook_path"])
        and baseline_source.get("license_receipt_sha256")
        == sha256(ROOT / baseline_source["license_receipt_path"])
        and baseline_source.get("verified_inbound_license") == "Apache-2.0"
        and baseline_source.get("winner_mit_grant_right_verified") is False
        and primary_delivery.get("dataset_license") == "CC0-1.0"
        and primary_delivery.get("dataset_metadata_sha256")
        == sha256(ROOT / primary_delivery["dataset_metadata_path"])
        and primary_delivery.get("artifact_manifest_sha256")
        == sha256(ROOT / primary_delivery["artifact_manifest_path"])
        and primary_delivery.get("checkpoint_sha256")
        == primary_artifact_manifest["model"]["weight_sha256"]
        and deepcenter_delivery.get("dataset_license") == "CC0-1.0"
        and deepcenter_delivery.get("dataset_metadata_sha256")
        == sha256(ROOT / deepcenter_delivery["dataset_metadata_path"])
        and deepcenter_delivery.get("artifact_manifest_sha256")
        == sha256(ROOT / deepcenter_delivery["artifact_manifest_path"])
        and deepcenter_delivery.get("checkpoint_sha256")
        == deepcenter_artifact_manifest["model"]["best_checkpoint"]["sha256"]
        and secondary_delivery.get("dataset_license") == "CC0-1.0"
        and secondary_delivery.get("dataset_metadata_sha256")
        == sha256(ROOT / secondary_delivery["dataset_metadata_path"])
        and secondary_delivery.get("artifact_manifest_sha256")
        == sha256(ROOT / secondary_delivery["artifact_manifest_path"])
        and secondary_delivery.get("checkpoint_sha256")
        == secondary_artifact_manifest["model"]["weight_sha256"]
        and baseline_offline.get(
            "exact_versions_in_single_available_wheel_per_package"
        )
        == expected_offline_versions
        and baseline_offline.get("dependency_license_inventory_path")
        == "artifacts/baseline_dependency_license_inventory.json"
        and baseline_offline.get("dependency_license_archive_path")
        == "artifacts/baseline_dependency_license_archive.json"
        and baseline_offline.get("individual_dependency_license_inventory_complete")
        is True
        and baseline_offline.get("primary_wheel_license_text_archive_complete")
        is True
        and baseline_offline.get("bundled_component_license_archive_complete")
        is False
        and baseline_offline.get("license_text_archive_complete") is False
        and baseline_dependency_inventory_valid
        and baseline_dependency_archive_valid
        and baseline_readiness.get("status")
        == "provisional_not_winner_delivery_ready"
        and rights.get("baseline_delivery_provenance_path")
        == "artifacts/baseline_winner_delivery_provenance.json"
        and rights.get("third_party_notices_path") == "THIRD_PARTY_NOTICES.md"
        and rights.get("exact_container_image_and_offline_wheel_versions_recorded")
        is True
        and rights.get("base_image_package_freeze_recorded") is False
        and rights.get("individual_dependency_license_inventory_complete") is True
        and rights.get("dependency_license_text_archive_complete") is False
        and rights.get("baseline_dependency_license_inventory_path")
        == "artifacts/baseline_dependency_license_inventory.json"
        and rights.get("baseline_dependency_license_archive_path")
        == "artifacts/baseline_dependency_license_archive.json"
        and rights.get("primary_wheel_license_text_archive_complete") is True
        and rights.get("bundled_component_license_archive_complete") is False
        and delivery_asset_rows.get("baseline_official_environment_status", {}).get(
            "path"
        )
        == "official/baseline_kernel_environment_status.json"
        and delivery_asset_rows.get("baseline_delivery_provenance", {}).get("path")
        == "artifacts/baseline_winner_delivery_provenance.json"
        and delivery_asset_rows.get("third_party_notices_draft", {}).get("path")
        == "THIRD_PARTY_NOTICES.md"
        and delivery_asset_rows.get("baseline_dependency_license_inventory", {}).get(
            "path"
        )
        == "artifacts/baseline_dependency_license_inventory.json"
        and delivery_asset_rows.get("baseline_dependency_license_archive", {}).get(
            "path"
        )
        == "artifacts/baseline_dependency_license_archive.json"
    )
    check(
        "baseline_winner_delivery_provenance",
        baseline_delivery_valid,
        {
            "valid": baseline_delivery_valid,
            "kernel": baseline_execution.get("kernel"),
            "script_version_id": baseline_execution.get("script_version_id"),
            "status": baseline_execution.get("status"),
            "log_lines": baseline_execution.get("official_log_lines"),
            "container_image": baseline_environment.get("container_image"),
            "offline_package_versions": len(expected_offline_versions),
            "winner_delivery_ready": False,
            "hashes": baseline_delivery_actual_hashes,
        },
    )
    check(
        "baseline_offline_dependency_licenses",
        baseline_dependency_inventory_valid,
        {
            "valid": baseline_dependency_inventory_valid,
            "packages": len(dependency_inventory_packages),
            "license_counts": baseline_dependency_inventory.get("summary", {}).get(
                "license_counts"
            ),
            "license_identifiers_complete": baseline_dependency_inventory.get(
                "summary", {}
            ).get("license_identifiers_complete"),
            "primary_wheel_license_text_archive_complete": baseline_dependency_inventory.get(
                "summary", {}
            ).get("primary_wheel_license_text_archive_complete"),
            "license_text_archive_complete": baseline_dependency_inventory.get(
                "summary", {}
            ).get("license_text_archive_complete"),
        },
    )
    check(
        "baseline_offline_dependency_license_archive",
        baseline_dependency_archive_valid,
        {
            "valid": baseline_dependency_archive_valid,
            "exact_wheels_verified": dependency_archive_summary.get(
                "exact_wheels_verified"
            ),
            "primary_wheel_license_files_archived": dependency_archive_summary.get(
                "primary_wheel_license_files_archived"
            ),
            "byte_exact_files": dependency_archive_inspection.get(
                "byte_exact_files"
            ),
            "trailing_newline_normalized_files": dependency_archive_inspection.get(
                "trailing_newline_normalized_files"
            ),
            "bundled_component_license_archive_complete": dependency_archive_summary.get(
                "bundled_component_license_archive_complete"
            ),
            "base_image_dependency_license_archive_complete": dependency_archive_summary.get(
                "base_image_dependency_license_archive_complete"
            ),
        },
    )

    for page in official["pages"]:
        path = ROOT / page["path"]
        check(
            f"official_page:{page['name']}",
            path.is_file() and sha256(path) == page["sha256"],
            {"path": str(path.relative_to(ROOT)), "expected_sha256": page["sha256"]},
        )
    manifest_path = ROOT / official["files"]["manifest_path"]
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        manifest_rows = sum(1 for _ in csv.DictReader(handle))
    check(
        "official_file_manifest",
        sha256(manifest_path) == official["files"]["manifest_sha256"]
        and manifest_rows == official["files"]["count"],
        {
            "rows": manifest_rows,
            "bytes": official["files"]["total_bytes"],
            "sha256": sha256(manifest_path),
        },
    )

    metric_validation = load_json("artifacts/official_metric_validation.json")
    metric_root = ROOT / "official_repo" / "src" / "tracking_cellmot"
    actual_metric_hashes = {name: sha256(metric_root / name) for name in OFFICIAL_METRIC_HASHES}
    check(
        "official_metric_commit_and_license",
        metric_validation["official_repository_commit"] == OFFICIAL_METRIC_COMMIT
        and metric_validation["official_repository_license"] == "BSD-3-Clause",
        {
            "commit": metric_validation["official_repository_commit"],
            "license": metric_validation["official_repository_license"],
        },
    )
    check("official_metric_source_hashes", actual_metric_hashes == OFFICIAL_METRIC_HASHES, actual_metric_hashes)
    regression = metric_validation["core_metric_regression_tests"]
    check(
        "official_metric_regression_tests",
        metric_validation["status"] == "pass"
        and regression["status"] == "pass"
        and regression["passed"] == 102
        and regression["failed"] == 0,
        regression,
    )
    identity = metric_validation["complete_training_sample"]["identity_evaluation"]
    check(
        "official_metric_identity_fixture",
        identity["edge_jaccard"] == 1.0 and identity["node_recall"] == 1.0,
        identity,
    )

    repro = load_json("kernels/biohub_0946_public_deps_repro/REPRO_RECEIPT.json")
    source_notebook = ROOT / "public_notebooks" / "reyhanksatria_0946" / "biohub-cell-tracking-0-946-lb.ipynb"
    target_notebook = ROOT / "kernels" / "biohub_0946_public_deps_repro" / "biohub-0946-public-deps-repro.ipynb"
    check("baseline_source_notebook", sha256(source_notebook) == repro["source_notebook_sha256"], sha256(source_notebook))
    check("baseline_target_notebook", sha256(target_notebook) == repro["target_notebook_sha256"], sha256(target_notebook))
    check(
        "baseline_no_behavior_change",
        repro["behavioral_change"] == "none"
        and repro["dependency_path_substitution_only"] is True
        and repro["model_thresholds_changed"] is False,
        {
            "behavioral_change": repro["behavioral_change"],
            "dependency_path_substitution_only": repro["dependency_path_substitution_only"],
            "model_thresholds_changed": repro["model_thresholds_changed"],
        },
    )
    check(
        "baseline_dependencies_public_cc0",
        all(item["access"] == "public" and item["license"] == "CC0-1.0" for item in repro["datasets"]),
        repro["datasets"],
    )

    run = load_json("kaggle_runs/BH-0001/RUN_RECEIPT.json")
    submission_path = ROOT / "kaggle_runs" / "BH-0001" / "submission.csv"
    submission_validation = load_json("kaggle_runs/BH-0001/submission_validation.json")
    runtime_integrity = load_json("kaggle_runs/BH-0001/bidirectional_production_runtime_integrity.json")
    check("submission_hash", sha256(submission_path) == run["submission_sha256"], sha256(submission_path))
    check(
        "submission_schema_topology",
        submission_validation["valid"] is True
        and not submission_validation["errors"]
        and not submission_validation["warnings"]
        and submission_validation["rows"] == run["rows"]
        and len(submission_validation["datasets"]) == run["datasets"]
        and all(item["max_indegree"] <= 1 and item["max_outdegree"] <= 2 for item in submission_validation["topology"].values()),
        {
            "valid": submission_validation["valid"],
            "rows": submission_validation["rows"],
            "datasets": submission_validation["datasets"],
        },
    )
    check(
        "runtime_integrity",
        runtime_integrity["ground_truth_accessed"] is False
        and runtime_integrity["status"] == "complete_label_free_runtime_integrity",
        {
            "status": runtime_integrity["status"],
            "ground_truth_accessed": runtime_integrity["ground_truth_accessed"],
        },
    )
    check("runtime_under_limit", run["predict_runtime_seconds"] < 12 * 3600, run["predict_runtime_seconds"])

    submission_status = load_json("official/submission_56108120_status.json")
    public_score = finite_float(submission_status["public_score"])
    check(
        "official_submission_binding",
        submission_status["submission_id"] == run["official_submission_id"]
        and submission_status["script_version_id"] == run["kaggle_script_version_id"]
        and submission_status["is_frozen"] is True
        and submission_status["status"].lower() == run["official_submission_status"]
        and public_score == finite_float(run["public_score"]),
        {
            "submission_id": submission_status["submission_id"],
            "script_version_id": submission_status["script_version_id"],
            "is_frozen": submission_status["is_frozen"],
        },
    )
    check("official_submission_no_error", submission_status["error_description"] is None, submission_status["error_description"])
    check(
        "official_submission_state",
        submission_status["status"] in {"PENDING", "COMPLETE"}
        and (
            submission_status["status"] == "PENDING"
            or public_score is not None
        ),
        {
            "status": submission_status["status"],
            "public_score": submission_status["public_score"],
        },
    )
    if submission_status["status"] == "PENDING":
        warnings.append("Submission 56108120 is frozen and error-free but still awaiting an official score.")
    check(
        "baseline_promotion_gate",
        submission_status["status"] == "COMPLETE"
        and public_score is not None
        and public_score >= 0.942
        and run["promotion_gate_passed"] is True
        and finite_float(run["promotion_threshold"]) == 0.942,
        {
            "public_score": public_score,
            "threshold": run.get("promotion_threshold"),
            "passed": run.get("promotion_gate_passed"),
        },
    )

    leaderboard_receipt = load_json(
        "official/leaderboard_20260909T1113Z/receipt.json"
    )
    leaderboard_archive_path = ROOT / leaderboard_receipt["archive"]["path"]
    with zipfile.ZipFile(leaderboard_archive_path) as archive:
        member_names = archive.namelist()
        leaderboard_csv_bytes = archive.read(leaderboard_receipt["csv_member"]["name"])
    leaderboard_rows = list(
        csv.DictReader(io.StringIO(leaderboard_csv_bytes.decode("utf-8-sig")))
    )
    participant_rows = [
        row
        for row in leaderboard_rows
        if row.get("TeamMemberUserNames") == "jahyee"
    ]
    leaderboard_participant = leaderboard_receipt["participant"]
    leaderboard_reference = leaderboard_receipt["public_reference_points"]
    participant_row = participant_rows[0] if len(participant_rows) == 1 else {}
    check(
        "public_leaderboard_snapshot_binding",
        leaderboard_receipt.get("competition")
        == "biohub-cell-tracking-during-development"
        and leaderboard_receipt.get("scope") == "public_leaderboard_snapshot"
        and sha256(leaderboard_archive_path)
        == leaderboard_receipt["archive"]["sha256"]
        and member_names == [leaderboard_receipt["csv_member"]["name"]]
        and hashlib.sha256(leaderboard_csv_bytes).hexdigest()
        == leaderboard_receipt["csv_member"]["sha256"]
        and len(leaderboard_rows) == leaderboard_receipt["csv_member"]["team_rows"]
        and len(participant_rows) == 1
        and int(participant_row.get("TeamId", 0))
        == leaderboard_participant["team_id"]
        and participant_row.get("TeamName") == leaderboard_participant["team_name"]
        and int(participant_row.get("Rank", 0)) == leaderboard_participant["rank"]
        and finite_float(participant_row.get("Score"))
        == finite_float(leaderboard_participant["score"])
        and int(participant_row.get("SubmissionCount", 0))
        == leaderboard_participant["submission_count"]
        and leaderboard_participant["submission_count"] == 1
        and leaderboard_participant["rank"] == 360
        and leaderboard_receipt["csv_member"]["team_rows"] == 3290
        and finite_float(leaderboard_reference["rank_1_score"])
        == finite_float(leaderboard_rows[0]["Score"])
        and finite_float(leaderboard_reference["rank_7_score"])
        == finite_float(leaderboard_rows[6]["Score"])
        and finite_float(leaderboard_reference["rank_8_score"])
        == finite_float(leaderboard_rows[7]["Score"])
        and math.isclose(
            leaderboard_participant["top_percent_by_row_rank"],
            100 * leaderboard_participant["rank"] / len(leaderboard_rows),
            rel_tol=0,
            abs_tol=1e-10,
        )
        and sum(
            finite_float(row["Score"]) > leaderboard_participant["score"]
            for row in leaderboard_rows
        )
        == leaderboard_participant["teams_strictly_above_score"]
        and sum(
            finite_float(row["Score"]) == leaderboard_participant["score"]
            for row in leaderboard_rows
        )
        == leaderboard_participant["teams_at_same_score"],
        {
            "retrieved_at_utc": leaderboard_receipt.get("retrieved_at_utc"),
            "rank": leaderboard_participant.get("rank"),
            "teams": len(leaderboard_rows),
            "score": leaderboard_participant.get("score"),
            "rank_7_score": leaderboard_reference.get("rank_7_score"),
            "gap_to_rank_7_score": leaderboard_reference.get(
                "gap_to_rank_7_score"
            ),
        },
    )

    candidate_scout = load_json("artifacts/public_candidate_scout_20260909.json")
    candidate_rows = candidate_scout.get("candidates", [])
    candidate_by_kernel = {row.get("kernel"): row for row in candidate_rows}
    exploit_candidate = candidate_by_kernel.get("anvithpothula/biohub-0-95", {})
    locked_candidate = candidate_by_kernel.get(
        "zhuzhenghaomax/biohub-0-948-reproduction-20260901", {}
    )
    retained_candidate = candidate_by_kernel.get(
        "flexonafft/biohub-lineage-forge-precision-tracking", {}
    )
    exploit_code = notebook_code(ROOT / exploit_candidate["source_path"])
    locked_notebook = json.loads(
        (ROOT / locked_candidate["source_path"]).read_text(encoding="utf-8")
    )
    locked_codex = locked_notebook.get("metadata", {}).get("codex", {})
    selected_output_path = ROOT / retained_candidate["selected_output_path"]
    selected_output = json.loads(selected_output_path.read_text(encoding="utf-8"))
    sweep_output_path = ROOT / retained_candidate["sweep_output_path"]
    check(
        "public_candidate_scout_gate",
        candidate_scout.get("competition")
        == "biohub-cell-tracking-during-development"
        and candidate_scout.get("status") == "screened_no_submission_authorized"
        and candidate_scout.get("policy", {}).get("metric_exploits_allowed")
        is False
        and candidate_scout.get("policy", {}).get(
            "competition_submission_authorized"
        )
        is False
        and len(candidate_rows) == 3
        and all(
            sha256(ROOT / row["source_path"]) == row["source_sha256"]
            and sha256(ROOT / row["metadata_path"]) == row["metadata_sha256"]
            for row in candidate_rows
        )
        and exploit_candidate.get("official_public_score") == 0.877
        and exploit_candidate.get("disposition")
        == "rejected_metric_exploit_and_underperforms"
        and "time = -999 + 2 * index" in exploit_code
        and "-10000" in exploit_code
        and "new_edges" in exploit_code
        and locked_candidate.get("official_public_score") == 0.936
        and locked_candidate.get("disposition")
        == "rejected_underperforms_and_embedded_gate_closed"
        and locked_codex.get("status") == "candidate_unverified_locked"
        and locked_codex.get("authorization", {}).get("authorized") is False
        and retained_candidate.get("official_public_score") == 0.946
        and retained_candidate.get("disposition")
        == "retained_as_single_axis_diagnostic_only"
        and sha256(selected_output_path)
        == retained_candidate["selected_output_sha256"]
        and sha256(sweep_output_path) == retained_candidate["sweep_output_sha256"]
        and selected_output.get("selected") == "tight55"
        and selected_output.get("overrides")
        == {"MOTION_RELINK_TIGHT_UM": 5.5}
        and len(selected_output.get("held_out_stems", [])) == 8
        and finite_float(selected_output.get("base_proxy"))
        == finite_float(retained_candidate.get("source_base_proxy"))
        and finite_float(selected_output.get("selected_proxy"))
        == finite_float(retained_candidate.get("selected_proxy"))
        and candidate_scout.get("next_candidate", {}).get("single_axis")
        == "MOTION_RELINK_TIGHT_UM"
        and candidate_scout.get("next_candidate", {}).get("campaign_control_value")
        == 6.0
        and candidate_scout.get("next_candidate", {}).get("candidate_value")
        == 5.5
        and candidate_scout.get("next_candidate", {}).get(
            "competition_submission_authorized"
        )
        is False,
        {
            "rejected_metric_exploit": exploit_candidate.get("kernel"),
            "rejected_title_score_mismatch": locked_candidate.get("kernel"),
            "retained_diagnostic_kernel": retained_candidate.get("kernel"),
            "retained_official_public_score": retained_candidate.get(
                "official_public_score"
            ),
            "retained_single_axis": retained_candidate.get("selected_axis"),
            "competition_submission_authorized": candidate_scout.get(
                "policy", {}
            ).get("competition_submission_authorized"),
        },
    )

    with (ROOT / "SUBMISSION_LEDGER.csv").open(encoding="utf-8", newline="") as handle:
        submission_ledger = list(csv.DictReader(handle))
    ledger_submission = next(row for row in submission_ledger if row["submission_id"] == "56108120")
    check(
        "submission_ledger_binding",
        ledger_submission["experiment_id"] == "BH-0001"
        and ledger_submission["submission_sha256"] == run["submission_sha256"]
        and ledger_submission["status"] == submission_status["status"]
        and finite_float(ledger_submission["public_lb"]) == public_score,
        ledger_submission,
    )

    protocol_path = ROOT / "artifacts" / "budgeted_embryo_oof.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    oof_local = ROOT / "kernels" / "biohub_budgeted_embryo_oof" / "biohub-budgeted-embryo-oof.py"
    oof_remote = ROOT / "kaggle_runs" / "BH-0002-source" / "biohub-budgeted-embryo-oof-v1.py"
    check("oof_protocol_manifest", protocol["data_manifest_sha256"] == official["files"]["manifest_sha256"], protocol["data_manifest_sha256"])
    check("oof_remote_source", sha256(oof_local) == sha256(oof_remote), sha256(oof_local))
    check(
        "oof_protocol_disjoint",
        all(
            not (set(fold["train"]) & set(fold["monitor"]))
            and not (set(fold["train"]) & set(fold["holdout"]))
            and not (set(fold["monitor"]) & set(fold["holdout"]))
            for fold in protocol["folds"]
        ),
        [
            {
                "fold": fold["fold"],
                "train": len(fold["train"]),
                "monitor": len(fold["monitor"]),
                "holdout": len(fold["holdout"]),
            }
            for fold in protocol["folds"]
        ],
    )
    visible = set(protocol["selection"]["visible_test_copies_excluded"])
    check(
        "oof_visible_test_exclusion",
        all(not visible & (set(fold["monitor"]) | set(fold["holdout"])) for fold in protocol["folds"]),
        sorted(visible),
    )

    with (ROOT / "EXPERIMENT_LEDGER.csv").open(encoding="utf-8", newline="") as handle:
        experiment_ledger = list(csv.DictReader(handle))
    ledger_oof = next(row for row in experiment_ledger if row["experiment_id"] == "BH-0002")
    check("oof_ledger_code_hash", ledger_oof["code_version"] == sha256(oof_local), ledger_oof["code_version"])
    oof_status_path = ROOT / "official" / "oof_kernel_status.json"
    oof_status = json.loads(oof_status_path.read_text(encoding="utf-8"))
    oof_activity_path = ROOT / "official" / "oof_runtime_activity.json"
    oof_activity = json.loads(oof_activity_path.read_text(encoding="utf-8"))
    failed_terminal = oof_status["status"] in {
        "ERROR",
        "CANCELLED",
        "CANCEL_ACKNOWLEDGED",
    }
    terminal_path = ROOT / "artifacts" / "oof_terminal_disposition.json"
    terminal_disposition = (
        json.loads(terminal_path.read_text(encoding="utf-8"))
        if terminal_path.is_file()
        else None
    )
    terminal_disposition_valid = bool(
        terminal_disposition
        and terminal_disposition.get("status") == "accepted_terminal_failure"
        and terminal_disposition.get("experiment_id") == "BH-0002"
        and terminal_disposition.get("kernel") == oof_status["kernel"]
        and terminal_disposition.get("official_terminal_status")
        == oof_status["status"]
        and terminal_disposition.get("official_status_receipt_sha256")
        == sha256(oof_status_path)
        and terminal_disposition.get("activity_receipt_sha256")
        == sha256(oof_activity_path)
        and terminal_disposition.get("recovery_authorized") is True
    )
    live_or_completed_status_valid = (
        oof_status["status"] in {"RUNNING", "COMPLETE"}
        and oof_status["failure_message"] is None
    )
    check(
        "oof_official_status",
        oof_status["kernel"] == ledger_oof["kaggle_kernel"]
        and (live_or_completed_status_valid or terminal_disposition_valid)
        and oof_status["log_api_error"] is None,
        {
            "checked_at_utc": oof_status["checked_at_utc"],
            "status": oof_status["status"],
            "failure_message": oof_status["failure_message"],
            "log_available": oof_status["log_available"],
            "log_api_error": oof_status["log_api_error"],
        },
    )
    check(
        "oof_terminal_disposition",
        (not failed_terminal)
        or (
            terminal_disposition_valid
            and ledger_oof["outcome"]
            == terminal_disposition.get("ledger_outcome")
        ),
        (
            {"applicable": False, "official_status": oof_status["status"]}
            if not failed_terminal
            else {
                "applicable": True,
                "valid": terminal_disposition_valid,
                "official_status": oof_status["status"],
                "ledger_outcome": ledger_oof["outcome"],
                "receipt_path": "artifacts/oof_terminal_disposition.json",
            }
        ),
    )
    activity_observations = oof_activity["activity_observations"]
    activity_delta = oof_activity["activity_delta"]
    activity_common_valid = (
        oof_activity["kernel"] == ledger_oof["kaggle_kernel"]
        and oof_activity["source"]
        == "Official authenticated Kaggle Notebook UI Logs page"
        and len(activity_observations) >= 2
        and activity_delta["runtime_seconds"] > 0
        and activity_delta["log_items"] > 0
        and oof_activity["projection"]["assessment"] == "runtime_infeasible"
        and oof_activity["intervention"]["parallel_rerun_allowed"] is False
    )
    live_activity_valid = (
        oof_status["status"] == "RUNNING"
        and oof_activity["active"] is True
        and oof_activity["stalled"] is False
        and oof_activity["latest_activity_assessment"][
            "seconds_since_latest_log_count_growth"
        ]
        < oof_activity["stall_threshold_seconds"]
        and oof_activity["latest_activity_assessment"]["threshold_exceeded"]
        is False
    )
    historical_terminal_activity_valid = (
        failed_terminal and terminal_disposition_valid
    )
    check(
        "oof_runtime_activity",
        activity_common_valid
        and (live_activity_valid or historical_terminal_activity_valid),
        {
            "checked_at_utc": oof_activity["checked_at_utc"],
            "classification": oof_activity["classification"],
            "runtime_delta_seconds": activity_delta["runtime_seconds"],
            "log_item_delta": activity_delta["log_items"],
            "seconds_since_latest_log_count_growth": oof_activity[
                "latest_activity_assessment"
            ]["seconds_since_latest_log_count_growth"],
            "current_fold": oof_activity["latest_ui_observation"]["fold_index"],
            "completed_epochs": oof_activity["latest_ui_observation"]["completed_epochs"],
            "current_epoch": oof_activity["latest_ui_observation"]["current_epoch"],
            "current_batch": oof_activity["latest_ui_observation"]["current_batch"],
            "batches_per_epoch": oof_activity["latest_ui_observation"]["batches_per_epoch"],
            "projected_training_hours_two_folds": oof_activity["projection"]["projected_training_hours_two_folds"],
        },
    )
    if oof_status["status"] == "RUNNING":
        warnings.append(
            "BH-0002 is active rather than stalled, but its measured batch rate projects beyond the 12-hour limit; it is not promotion evidence and no parallel rerun is allowed."
        )
    elif failed_terminal:
        recovery_finalization_narrative_path = (
            ROOT / "artifacts" / "oof_recovery_finalization_binding.json"
        )
        if recovery_finalization_narrative_path.is_file():
            recovery_finalization_narrative = json.loads(
                recovery_finalization_narrative_path.read_text(encoding="utf-8")
            )
            warnings.append(
                "BH-0002 ended at the official runtime limit; BH-0003 is terminal "
                f"{recovery_finalization_narrative.get('official_kernel_status')} and "
                f"finalized as {recovery_finalization_narrative.get('ledger_outcome')} "
                "with submission and promotion unauthorized; finalization binding SHA-256 "
                f"{sha256(recovery_finalization_narrative_path)}."
            )
        elif (ROOT / "artifacts" / "oof_recovery_launch.json").is_file():
            warnings.append(
                "BH-0002 ended at the official runtime limit; the single authorized one-epoch recovery BH-0003 has been launched and is the only permitted recovery."
            )
        else:
            warnings.append(
                "BH-0002 ended in an official failed terminal state; the bound disposition authorizes only the predeclared one-epoch recovery."
            )
    elif oof_status["status"] == "COMPLETE":
        warnings.append(
            "BH-0002 completed and must pass downloaded-output finalization before any recovery or promotion decision."
        )
    actual_oof_tool_hashes = {
        name: sha256(ROOT / "src" / name) for name in OOF_LOCAL_TOOL_HASHES
    }
    check(
        "oof_local_tool_hashes",
        actual_oof_tool_hashes == OOF_LOCAL_TOOL_HASHES,
        actual_oof_tool_hashes,
    )
    actual_oof_status_tool_hashes = {
        name: sha256(ROOT / name) for name in OOF_STATUS_TOOL_HASHES
    }
    check(
        "oof_status_tool_hashes",
        actual_oof_status_tool_hashes == OOF_STATUS_TOOL_HASHES,
        actual_oof_status_tool_hashes,
    )
    actual_recovery_build_hashes = {
        name: sha256(ROOT / name) for name in OOF_RECOVERY_BUILD_HASHES
    }
    check(
        "oof_recovery_build_tool_hashes",
        actual_recovery_build_hashes == OOF_RECOVERY_BUILD_HASHES,
        actual_recovery_build_hashes,
    )
    actual_recovery_artifact_hashes = {
        relative: sha256(ROOT / relative)
        for relative in OOF_RECOVERY_ARTIFACT_HASHES
    }
    check(
        "oof_recovery_artifact_hashes",
        actual_recovery_artifact_hashes == OOF_RECOVERY_ARTIFACT_HASHES,
        actual_recovery_artifact_hashes,
    )
    parent_binding_path = ROOT / "artifacts" / "budgeted_oof_finalization_binding.json"
    parent_run_dir = ROOT / "kaggle_runs" / "BH-0002"
    parent_receipt_path = parent_run_dir / "budgeted_oof_receipt.json"
    parent_validation_path = ROOT / "artifacts" / "budgeted_oof_validation.json"
    parent_analysis_path = ROOT / "artifacts" / "budgeted_oof_analysis.json"
    parent_generic_finalization_path = ROOT / "artifacts" / "budgeted_oof_finalization.json"
    parent_metadata_path = ROOT / "kernels" / "biohub_budgeted_embryo_oof" / "kernel-metadata.json"
    parent_binding = (
        json.loads(parent_binding_path.read_text(encoding="utf-8"))
        if parent_binding_path.is_file()
        else None
    )
    parent_validation = (
        json.loads(parent_validation_path.read_text(encoding="utf-8"))
        if parent_validation_path.is_file()
        else None
    )
    parent_analysis = (
        json.loads(parent_analysis_path.read_text(encoding="utf-8"))
        if parent_analysis_path.is_file()
        else None
    )
    parent_generic_finalization = (
        json.loads(parent_generic_finalization_path.read_text(encoding="utf-8"))
        if parent_generic_finalization_path.is_file()
        else None
    )
    parent_finalization_artifacts = [
        parent_binding_path,
        parent_receipt_path,
        parent_validation_path,
        parent_analysis_path,
        parent_generic_finalization_path,
    ]
    parent_finalization_attempted = any(path.is_file() for path in parent_finalization_artifacts)
    parent_finalization_valid = bool(
        parent_binding
        and all(path.is_file() for path in parent_finalization_artifacts)
        and oof_status.get("status") == "COMPLETE"
        and oof_status.get("failure_message") is None
        and oof_status.get("log_api_error") is None
        and oof_status.get("script_version_id") == oof_activity.get("script_version_id")
        and oof_status.get("run_url") == oof_activity.get("run_url")
        and parent_binding.get("status") == "accepted_parent_oof_finalization"
        and parent_binding.get("experiment_id") == "BH-0002"
        and parent_binding.get("kernel") == ledger_oof["kaggle_kernel"]
        and parent_binding.get("script_version_id") == oof_activity.get("script_version_id")
        and parent_binding.get("run_url") == oof_activity.get("run_url")
        and parent_binding.get("official_kernel_status") == "COMPLETE"
        and parent_binding.get("activity_receipt_sha256")
        == sha256(ROOT / "official" / "oof_runtime_activity.json")
        and parent_binding.get("official_completion_status_sha256")
        == sha256(ROOT / "official" / "oof_kernel_status.json")
        and parent_binding.get("protocol_sha256") == sha256(protocol_path)
        and parent_binding.get("local_source_sha256") == sha256(oof_local)
        and parent_binding.get("pulled_remote_source_sha256") == sha256(oof_remote)
        and parent_binding.get("metadata_sha256") == sha256(parent_metadata_path)
        and parent_binding.get("oof_receipt_sha256") == sha256(parent_receipt_path)
        and parent_binding.get("validation_sha256") == sha256(parent_validation_path)
        and parent_binding.get("analysis_sha256") == sha256(parent_analysis_path)
        and parent_binding.get("finalization_sha256")
        == sha256(parent_generic_finalization_path)
        and parent_binding.get("validation_valid") is True
        and parent_binding.get("analysis_status") == "complete_diagnostic"
        and parent_binding.get("ledger_outcome") == "OOF_VALIDATED_DIAGNOSTIC"
        and parent_binding.get("competition_submission_authorized") is False
        and parent_binding.get("promotion_authorized") is False
        and parent_validation.get("valid") is True
        and parent_analysis.get("status") == "complete_diagnostic"
        and parent_analysis.get("submission_recommendation")
        == "diagnostic_only_do_not_submit"
        and parent_generic_finalization.get("status") == "complete"
        and parent_generic_finalization.get("experiment_id") == "BH-0002"
        and parent_generic_finalization.get("ledger_updated") is True
        and ledger_oof["outcome"] == "OOF_VALIDATED_DIAGNOSTIC"
        and finite_float(ledger_oof["offline_score"])
        == finite_float(parent_binding.get("combined_holdout_score"))
    )
    check(
        "oof_parent_finalization_binding",
        (not parent_finalization_attempted) or parent_finalization_valid,
        (
            {"applicable": False, "state": "not_finalized"}
            if not parent_finalization_attempted
            else {
                "applicable": True,
                "valid": parent_finalization_valid,
                "kernel": None if not parent_binding else parent_binding.get("kernel"),
                "script_version_id": (
                    None if not parent_binding else parent_binding.get("script_version_id")
                ),
                "submission_authorized": (
                    None
                    if not parent_binding
                    else parent_binding.get("competition_submission_authorized")
                ),
            }
        ),
    )
    recovery_protocol = load_json("artifacts/budgeted_embryo_oof_1ep_recovery.json")
    recovery_preflight = load_json("artifacts/oof_recovery_preflight.json")
    recovery_metadata = load_json(
        "kernels/biohub_budgeted_embryo_oof_1ep_recovery/kernel-metadata.json"
    )
    parent_failed_and_disposed = failed_terminal and terminal_disposition_valid
    check(
        "oof_recovery_runtime_and_launch_gate",
        recovery_protocol["training"]["epochs"] == 1
        and recovery_protocol["recovery_parent"]["protocol_sha256"]
        == sha256(protocol_path)
        and recovery_protocol["runtime_budget"]["passes_prelaunch_runtime_gate"]
        is True
        and recovery_protocol["runtime_budget"]["estimated_total_seconds_with_reserve"]
        < 12 * 3600
        and recovery_preflight["valid"] is True
        and recovery_preflight["current_parent_kernel_status"] == oof_status["status"]
        and recovery_preflight["launch_allowed"] is parent_failed_and_disposed
        and recovery_metadata["is_private"] is True
        and recovery_metadata["enable_gpu"] is True
        and recovery_metadata["enable_internet"] is False,
        {
            "parent_status": oof_status["status"],
            "launch_allowed": recovery_preflight["launch_allowed"],
            "estimated_total_hours_with_reserve": recovery_preflight[
                "estimated_total_hours_with_reserve"
            ],
            "headroom_hours": recovery_preflight["headroom_hours"],
            "epochs_per_fold": recovery_protocol["training"]["epochs"],
        },
    )
    parent_normalized_source_hash = normalized_oof_source_sha256(oof_local)
    recovery_normalized_source_hash = normalized_oof_source_sha256(
        ROOT
        / "kernels"
        / "biohub_budgeted_embryo_oof_1ep_recovery"
        / "biohub-budgeted-embryo-oof-1ep.py"
    )
    check(
        "oof_recovery_single_variable_contract",
        recovery_preflight.get("single_variable_contract") is True
        and recovery_preflight.get("changed_operational_fields")
        == ["training.epochs"]
        and recovery_preflight.get("parent_epochs") == 12
        and recovery_preflight.get("recovery_epochs") == 1
        and parent_normalized_source_hash == recovery_normalized_source_hash,
        {
            "single_variable_contract": recovery_preflight.get(
                "single_variable_contract"
            ),
            "changed_operational_fields": recovery_preflight.get(
                "changed_operational_fields"
            ),
            "parent_epochs": recovery_preflight.get("parent_epochs"),
            "recovery_epochs": recovery_preflight.get("recovery_epochs"),
            "parent_normalized_source_sha256": parent_normalized_source_hash,
            "recovery_normalized_source_sha256": recovery_normalized_source_hash,
        },
    )
    ledger_recovery = next(
        row for row in experiment_ledger if row["experiment_id"] == "BH-0003"
    )
    recovery_launch_path = ROOT / "artifacts" / "oof_recovery_launch.json"
    recovery_launch = (
        json.loads(recovery_launch_path.read_text(encoding="utf-8"))
        if recovery_launch_path.is_file()
        else None
    )
    recovery_remote_source = (
        ROOT
        / "kaggle_runs"
        / "BH-0003-source"
        / "biohub-budgeted-embryo-oof-1ep.py"
    )
    recovery_launch_status_path = (
        ROOT / "official" / "oof_recovery_launch_status.json"
    )
    recovery_launch_valid = bool(
        recovery_launch
        and recovery_remote_source.is_file()
        and recovery_launch_status_path.is_file()
        and recovery_launch.get("status") == "accepted_recovery_launch"
        and recovery_launch.get("experiment_id") == "BH-0003"
        and recovery_launch.get("kernel") == recovery_metadata["id"]
        and recovery_launch.get("local_source_sha256")
        == OOF_RECOVERY_ARTIFACT_HASHES[
            "kernels/biohub_budgeted_embryo_oof_1ep_recovery/biohub-budgeted-embryo-oof-1ep.py"
        ]
        and recovery_launch.get("pulled_remote_source_sha256")
        == sha256(recovery_remote_source)
        and recovery_launch.get("preflight_sha256")
        == sha256(ROOT / "artifacts" / "oof_recovery_preflight.json")
        and recovery_launch.get("official_status_receipt_sha256")
        == sha256(recovery_launch_status_path)
        and recovery_launch.get("competition_submission_authorized") is False
        and isinstance(recovery_launch.get("script_version_id"), int)
        and recovery_launch.get("script_version_id", 0) > 0
    )
    check(
        "oof_recovery_launch_binding",
        (not recovery_launch_path.is_file()) or recovery_launch_valid,
        (
            {"applicable": False, "state": "not_launched"}
            if not recovery_launch_path.is_file()
            else {
                "applicable": True,
                "valid": recovery_launch_valid,
                "kernel": recovery_launch.get("kernel"),
                "script_version_id": recovery_launch.get("script_version_id"),
                "remote_source_sha256": recovery_launch.get(
                    "pulled_remote_source_sha256"
                ),
            }
        ),
    )
    recovery_activity_path = (
        ROOT / "official" / "oof_recovery_runtime_activity.json"
    )
    recovery_activity = (
        json.loads(recovery_activity_path.read_text(encoding="utf-8"))
        if recovery_activity_path.is_file()
        else None
    )
    recovery_activity_valid = bool(
        recovery_activity
        and recovery_launch_valid
        and recovery_activity.get("source")
        == "Official authenticated Kaggle Notebook UI Logs page"
        and recovery_activity.get("kernel") == recovery_launch.get("kernel")
        and recovery_activity.get("script_version_id")
        == recovery_launch.get("script_version_id")
        and recovery_activity.get("run_url") == recovery_launch.get("run_url")
        and recovery_activity.get("accelerator") == "GPU T4 x2"
        and recovery_activity.get("output_bytes") == 0
        and recovery_activity.get("activity_observations")
        and recovery_activity["activity_observations"][0].get("runtime_seconds", 0)
        > 0
        and recovery_activity.get("classification")
        in {
            "ACTIVE_STARTUP",
            "ACTIVE",
            "ACTIVE_PROGRESS",
            "ACTIVE_BUT_RUNTIME_INFEASIBLE",
            "RUNTIME_LIMIT_CANCELLATION_ACKNOWLEDGED",
            "TERMINAL_FAILURE",
            "COMPLETE",
        }
        and isinstance(recovery_activity.get("active"), bool)
        and isinstance(recovery_activity.get("stalled"), bool)
        and recovery_activity.get("runtime_budget", {}).get("epochs_per_fold")
        == 1
        and recovery_activity.get("runtime_budget", {}).get(
            "estimated_total_hours_with_reserve"
        )
        < 12
        and recovery_activity.get("intervention", {}).get(
            "parallel_rerun_allowed"
        )
        is False
        and recovery_activity.get("intervention", {}).get(
            "competition_submission_authorized"
        )
        is False
    )
    check(
        "oof_recovery_activity_binding",
        (not recovery_launch_path.is_file())
        or (recovery_activity_path.is_file() and recovery_activity_valid),
        (
            {"applicable": False, "state": "not_launched"}
            if not recovery_launch_path.is_file()
            else {
                "applicable": True,
                "valid": recovery_activity_valid,
                "kernel": recovery_activity.get("kernel"),
                "script_version_id": recovery_activity.get("script_version_id"),
                "observations": len(recovery_activity["activity_observations"]),
                "runtime_seconds": recovery_activity[
                    "activity_observations"
                ][-1].get("runtime_seconds"),
                "runtime_delta_seconds": recovery_activity.get(
                    "activity_delta", {}
                ).get("runtime_seconds"),
                "classification": recovery_activity.get("classification"),
            }
        ),
    )
    recovery_monitoring_status_path = (
        ROOT / "official" / "oof_recovery_status_20260909T121825Z.json"
    )
    recovery_monitoring_attempt_path = (
        ROOT
        / "artifacts"
        / "oof_recovery_monitoring_attempt_20260909T121825Z.json"
    )
    recovery_monitoring_status = json.loads(
        recovery_monitoring_status_path.read_text(encoding="utf-8")
    )
    recovery_monitoring_attempt = json.loads(
        recovery_monitoring_attempt_path.read_text(encoding="utf-8")
    )
    actual_recovery_monitoring_hashes = {
        relative: sha256(ROOT / relative)
        for relative in OOF_RECOVERY_MONITORING_HASHES
    }
    monitoring_status_observation = recovery_monitoring_attempt[
        "official_status_observation"
    ]
    monitoring_ui_attempt = recovery_monitoring_attempt[
        "authenticated_ui_observation_attempt"
    ]
    monitoring_assessment = recovery_monitoring_attempt["assessment"]
    monitoring_intervention = recovery_monitoring_attempt["intervention"]
    recovery_monitoring_valid = bool(
        actual_recovery_monitoring_hashes == OOF_RECOVERY_MONITORING_HASHES
        and recovery_monitoring_attempt.get("experiment_id") == "BH-0003"
        and recovery_monitoring_attempt.get("kernel") == recovery_launch.get("kernel")
        and recovery_monitoring_attempt.get("script_version_id")
        == recovery_launch.get("script_version_id")
        and recovery_monitoring_attempt.get("run_url")
        == recovery_launch.get("run_url")
        and monitoring_status_observation.get("status_receipt_path")
        == "official/oof_recovery_status_20260909T121825Z.json"
        and monitoring_status_observation.get("status_receipt_sha256")
        == sha256(recovery_monitoring_status_path)
        and monitoring_status_observation.get("checked_at_utc")
        == recovery_monitoring_status.get("checked_at_utc")
        and monitoring_status_observation.get("status") == "RUNNING"
        and monitoring_status_observation.get("failure_message") is None
        and monitoring_status_observation.get("log_api_error") is None
        and recovery_monitoring_status.get("source")
        == "Official Kaggle kernel status and execution log APIs"
        and recovery_monitoring_status.get("kernel") == recovery_launch.get("kernel")
        and recovery_monitoring_status.get("script_version_id")
        == recovery_launch.get("script_version_id")
        and recovery_monitoring_status.get("run_url") == recovery_launch.get("run_url")
        and recovery_monitoring_status.get("status") == "RUNNING"
        and recovery_monitoring_status.get("failure_message") is None
        and recovery_monitoring_status.get("log_api_error") is None
        and monitoring_ui_attempt.get("attempted") is True
        and monitoring_ui_attempt.get("result") == "unavailable_mac_locked"
        and monitoring_ui_attempt.get("telemetry_observed") is False
        and monitoring_assessment.get("official_run_confirmed_live") is True
        and monitoring_assessment.get("stalled") is None
        and monitoring_assessment.get("classification")
        == "RUNNING_STATUS_CONFIRMED_TELEMETRY_UNAVAILABLE"
        and monitoring_intervention.get("cancelled") is False
        and monitoring_intervention.get("parallel_rerun_allowed") is False
        and monitoring_intervention.get("competition_submission_authorized") is False
    )
    check(
        "oof_recovery_locked_monitoring_snapshot",
        recovery_monitoring_valid,
        {
            "valid": recovery_monitoring_valid,
            "status_checked_at_utc": recovery_monitoring_status.get(
                "checked_at_utc"
            ),
            "official_status": recovery_monitoring_status.get("status"),
            "ui_result": monitoring_ui_attempt.get("result"),
            "stalled": monitoring_assessment.get("stalled"),
            "hashes": actual_recovery_monitoring_hashes,
        },
    )
    recovery_finalization_path = (
        ROOT / "artifacts" / "oof_recovery_finalization_binding.json"
    )
    recovery_completion_status_path = (
        ROOT / "official" / "oof_recovery_kernel_status.json"
    )
    recovery_run_dir = ROOT / "kaggle_runs" / "BH-0003"
    recovery_receipt_path = recovery_run_dir / "budgeted_oof_receipt.json"
    recovery_validation_path = (
        ROOT / "artifacts" / "budgeted_oof_1ep_recovery_validation.json"
    )
    recovery_analysis_path = (
        ROOT / "artifacts" / "budgeted_oof_1ep_recovery_analysis.json"
    )
    recovery_generic_finalization_path = (
        ROOT / "artifacts" / "budgeted_oof_1ep_recovery_finalization.json"
    )
    recovery_finalization = (
        json.loads(recovery_finalization_path.read_text(encoding="utf-8"))
        if recovery_finalization_path.is_file()
        else None
    )
    recovery_receipt = (
        json.loads(recovery_receipt_path.read_text(encoding="utf-8"))
        if recovery_receipt_path.is_file()
        else None
    )
    recovery_completion_status = (
        json.loads(recovery_completion_status_path.read_text(encoding="utf-8"))
        if recovery_completion_status_path.is_file()
        else None
    )
    recovery_terminal_path = (
        ROOT / "artifacts" / "oof_recovery_terminal_disposition.json"
    )
    recovery_terminal = (
        json.loads(recovery_terminal_path.read_text(encoding="utf-8"))
        if recovery_terminal_path.is_file()
        else None
    )
    recovery_status_is_failed_terminal = bool(
        recovery_completion_status
        and str(recovery_completion_status.get("status", "")).upper()
        in OOF_RECOVERY_FAILED_TERMINAL_STATUSES
    )
    recovery_terminal_output_dir = ROOT / "kaggle_runs" / "BH-0003-terminal"
    recovery_terminal_evidence = []
    if recovery_terminal_output_dir.is_dir():
        for path in sorted(recovery_terminal_output_dir.rglob("*")):
            if path.is_file() and path.name in OOF_RECOVERY_TERMINAL_EVIDENCE_NAMES:
                recovery_terminal_evidence.append(
                    {
                        "name": path.name,
                        "relative_path": str(path.relative_to(recovery_terminal_output_dir)),
                        "bytes": path.stat().st_size,
                        "sha256": sha256(path),
                    }
                )
    recovery_terminal_activity_hash = (
        recovery_terminal.get("activity_receipt_sha256")
        if recovery_terminal
        else None
    )
    recovery_terminal_activity_valid = bool(
        recovery_terminal_activity_hash is None
        or (
            recovery_activity_path.is_file()
            and recovery_terminal_activity_hash == sha256(recovery_activity_path)
        )
    )
    recovery_terminal_valid = bool(
        recovery_terminal
        and recovery_status_is_failed_terminal
        and recovery_launch_valid
        and recovery_completion_status_path.is_file()
        and recovery_terminal_output_dir.is_dir()
        and recovery_terminal.get("status")
        == "accepted_recovery_terminal_failure"
        and recovery_terminal.get("experiment_id") == "BH-0003"
        and recovery_terminal.get("kernel") == recovery_launch.get("kernel")
        and recovery_terminal.get("script_version_id")
        == recovery_launch.get("script_version_id")
        and recovery_terminal.get("run_url") == recovery_launch.get("run_url")
        and recovery_terminal.get("official_terminal_status")
        == str(recovery_completion_status.get("status", "")).upper()
        and recovery_terminal.get("ledger_outcome")
        in {"FAILED_RUNTIME_LIMIT", "FAILED_TERMINAL_ERROR", "CANCELLED"}
        and recovery_terminal.get("launch_receipt_sha256")
        == sha256(recovery_launch_path)
        and recovery_terminal.get("official_status_receipt_sha256")
        == sha256(recovery_completion_status_path)
        and recovery_terminal_activity_valid
        and recovery_terminal.get("evidence_files") == recovery_terminal_evidence
        and recovery_terminal.get("further_recovery_authorized") is False
        and recovery_terminal.get("competition_submission_authorized") is False
        and recovery_terminal.get("promotion_authorized") is False
        and recovery_completion_status.get("source")
        == "Official Kaggle kernel status and execution log APIs"
        and recovery_completion_status.get("kernel") == recovery_launch.get("kernel")
        and recovery_completion_status.get("script_version_id")
        == recovery_launch.get("script_version_id")
        and recovery_completion_status.get("run_url") == recovery_launch.get("run_url")
        and recovery_completion_status.get("log_api_error") is None
    )
    check(
        "oof_recovery_terminal_binding",
        (
            not recovery_status_is_failed_terminal
            and not recovery_terminal_path.is_file()
        )
        or recovery_terminal_valid,
        (
            {"applicable": False, "state": "no_failed_terminal_status"}
            if not recovery_status_is_failed_terminal
            and not recovery_terminal_path.is_file()
            else {
                "applicable": True,
                "valid": recovery_terminal_valid,
                "official_status": (
                    recovery_completion_status.get("status")
                    if recovery_completion_status
                    else None
                ),
                "ledger_outcome": (
                    recovery_terminal.get("ledger_outcome")
                    if recovery_terminal
                    else None
                ),
                "further_recovery_authorized": (
                    recovery_terminal.get("further_recovery_authorized")
                    if recovery_terminal
                    else None
                ),
            }
        ),
    )
    recovery_validation = (
        json.loads(recovery_validation_path.read_text(encoding="utf-8"))
        if recovery_validation_path.is_file()
        else None
    )
    recovery_analysis = (
        json.loads(recovery_analysis_path.read_text(encoding="utf-8"))
        if recovery_analysis_path.is_file()
        else None
    )
    recovery_generic_finalization = (
        json.loads(recovery_generic_finalization_path.read_text(encoding="utf-8"))
        if recovery_generic_finalization_path.is_file()
        else None
    )
    recovery_finalization_required_paths = [
        recovery_completion_status_path,
        recovery_receipt_path,
        recovery_validation_path,
        recovery_analysis_path,
        recovery_generic_finalization_path,
    ]
    recovery_finalization_valid = bool(
        recovery_finalization
        and recovery_launch_valid
        and all(path.is_file() for path in recovery_finalization_required_paths)
        and recovery_finalization.get("status")
        == "accepted_recovery_oof_finalization"
        and recovery_finalization.get("experiment_id") == "BH-0003"
        and recovery_finalization.get("kernel") == recovery_metadata["id"]
        and recovery_finalization.get("script_version_id")
        == recovery_launch.get("script_version_id")
        and recovery_finalization.get("run_url") == recovery_launch.get("run_url")
        and recovery_finalization.get("official_kernel_status") == "COMPLETE"
        and recovery_finalization.get("launch_receipt_sha256")
        == sha256(recovery_launch_path)
        and recovery_finalization.get("official_completion_status_sha256")
        == sha256(recovery_completion_status_path)
        and recovery_finalization.get("preflight_sha256")
        == sha256(ROOT / "artifacts" / "oof_recovery_preflight.json")
        and recovery_finalization.get("protocol_sha256")
        == OOF_RECOVERY_ARTIFACT_HASHES[
            "artifacts/budgeted_embryo_oof_1ep_recovery.json"
        ]
        and recovery_finalization.get("local_source_sha256")
        == OOF_RECOVERY_ARTIFACT_HASHES[
            "kernels/biohub_budgeted_embryo_oof_1ep_recovery/biohub-budgeted-embryo-oof-1ep.py"
        ]
        and recovery_finalization.get("pulled_remote_source_sha256")
        == sha256(recovery_remote_source)
        and recovery_finalization.get("oof_receipt_sha256")
        == sha256(recovery_receipt_path)
        and recovery_finalization.get("validation_sha256")
        == sha256(recovery_validation_path)
        and recovery_finalization.get("analysis_sha256")
        == sha256(recovery_analysis_path)
        and recovery_finalization.get("finalization_sha256")
        == sha256(recovery_generic_finalization_path)
        and recovery_finalization.get("validation_valid") is True
        and recovery_finalization.get("analysis_status") == "complete_diagnostic"
        and recovery_finalization.get("ledger_outcome")
        == "OOF_VALIDATED_DIAGNOSTIC"
        and recovery_finalization.get("competition_submission_authorized") is False
        and recovery_finalization.get("promotion_authorized") is False
        and recovery_completion_status.get("source")
        == "Official Kaggle kernel status and execution log APIs"
        and recovery_completion_status.get("kernel") == recovery_launch.get("kernel")
        and recovery_completion_status.get("status") == "COMPLETE"
        and recovery_completion_status.get("failure_message") is None
        and recovery_completion_status.get("log_api_error") is None
        and recovery_completion_status.get("script_version_id")
        == recovery_launch.get("script_version_id")
        and recovery_completion_status.get("run_url") == recovery_launch.get("run_url")
        and recovery_validation.get("valid") is True
        and recovery_analysis.get("status") == "complete_diagnostic"
        and recovery_analysis.get("submission_recommendation")
        == "diagnostic_only_do_not_submit"
        and recovery_generic_finalization.get("status") == "complete"
        and recovery_generic_finalization.get("experiment_id") == "BH-0003"
        and recovery_generic_finalization.get("ledger_updated") is True
        and recovery_generic_finalization.get("submission_recommendation")
        == "diagnostic_only_do_not_submit"
        and finite_float(recovery_finalization.get("combined_holdout_score"))
        == finite_float(recovery_analysis.get("combined_holdout_score"))
    )
    check(
        "oof_recovery_finalization_binding",
        (not recovery_finalization_path.is_file())
        or (not recovery_status_is_failed_terminal and recovery_finalization_valid),
        (
            {
                "applicable": False,
                "state": (
                    "terminal_failure_not_finalizable"
                    if recovery_status_is_failed_terminal
                    else "not_finalized"
                ),
            }
            if not recovery_finalization_path.is_file()
            else {
                "applicable": True,
                "valid": recovery_finalization_valid,
                "kernel": recovery_finalization.get("kernel"),
                "script_version_id": recovery_finalization.get("script_version_id"),
                "combined_holdout_score": recovery_finalization.get(
                    "combined_holdout_score"
                ),
                "submission_authorized": recovery_finalization.get(
                    "competition_submission_authorized"
                ),
            }
        ),
    )
    threshold_preregistration_path = (
        ROOT
        / "artifacts"
        / "detection_threshold_downward_calibration_preregistration.json"
    )
    threshold_preregistration = (
        json.loads(threshold_preregistration_path.read_text(encoding="utf-8"))
        if threshold_preregistration_path.is_file()
        else None
    )
    threshold_source = (
        threshold_preregistration.get("source_evidence", {})
        if threshold_preregistration
        else {}
    )
    threshold_change = (
        threshold_preregistration.get("single_changed_variable", {})
        if threshold_preregistration
        else {}
    )
    threshold_controls = (
        threshold_preregistration.get("frozen_controls", {})
        if threshold_preregistration
        else {}
    )
    threshold_gate = (
        threshold_preregistration.get("promotion_gate", {})
        if threshold_preregistration
        else {}
    )
    threshold_execution = (
        threshold_preregistration.get("execution_state", {})
        if threshold_preregistration
        else {}
    )
    threshold_preregistration_valid = bool(
        threshold_preregistration
        and recovery_finalization_valid
        and recovery_receipt
        and threshold_preregistration.get("experiment_id") == "BH-0004"
        and threshold_preregistration.get("status") == "PREREGISTERED_NO_RUN"
        and threshold_source.get("analysis_sha256") == sha256(recovery_analysis_path)
        and threshold_source.get("finalization_binding_sha256")
        == sha256(recovery_finalization_path)
        and threshold_source.get("baseline_protocol_sha256")
        == sha256(ROOT / "artifacts" / "budgeted_embryo_oof_1ep_recovery.json")
        and threshold_source.get("baseline_oof_receipt_sha256")
        == sha256(recovery_receipt_path)
        and threshold_change.get("name") == "detection_threshold"
        and threshold_change.get("direction") == "downward_calibration"
        and finite_float(threshold_change.get("baseline_value")) == 0.965
        and finite_float(threshold_change.get("preregistered_value")) == 0.95
        and threshold_controls.get("training")
        == "forbidden; reuse the exact two BH-0003 fold checkpoints"
        and threshold_controls.get("fold_0_weights_sha256")
        == recovery_receipt["folds"][0]["weights_sha256"]
        and threshold_controls.get("fold_1_weights_sha256")
        == recovery_receipt["folds"][1]["weights_sha256"]
        and threshold_controls.get("visible_test_copies") == "excluded"
        and threshold_controls.get("competition_test") == "must not be accessed"
        and threshold_gate.get("requires_both_embryo_directions") is True
        and threshold_gate.get("automatic_submission") is False
        and threshold_gate.get("automatic_promotion") is False
        and all(value is False for value in threshold_execution.values())
    )
    check(
        "detection_threshold_downward_calibration_preregistration",
        threshold_preregistration_valid,
        {
            "valid": threshold_preregistration_valid,
            "status": (
                None
                if not threshold_preregistration
                else threshold_preregistration.get("status")
            ),
            "sha256": (
                sha256(threshold_preregistration_path)
                if threshold_preregistration_path.is_file()
                else None
            ),
            "baseline_value": threshold_change.get("baseline_value"),
            "preregistered_value": threshold_change.get("preregistered_value"),
            "requires_both_embryo_directions": threshold_gate.get(
                "requires_both_embryo_directions"
            ),
            "training_started": threshold_execution.get("training_started"),
            "competition_submission_made": threshold_execution.get(
                "competition_submission_made"
            ),
        },
    )
    check(
        "oof_recovery_ledger_binding",
        ledger_recovery["code_version"]
        == OOF_RECOVERY_ARTIFACT_HASHES[
            "kernels/biohub_budgeted_embryo_oof_1ep_recovery/biohub-budgeted-embryo-oof-1ep.py"
        ]
        and ledger_recovery["kaggle_kernel"] == recovery_metadata["id"]
        and (
            (
                not recovery_launch_path.is_file()
                and ledger_recovery["outcome"] == "PREPARED_NOT_LAUNCHED"
            )
            or (
                recovery_launch_valid
                and not recovery_finalization_path.is_file()
                and not recovery_terminal_path.is_file()
                and ledger_recovery["outcome"]
                == recovery_launch.get("ledger_outcome")
            )
            or (
                recovery_terminal_valid
                and not recovery_finalization_path.is_file()
                and ledger_recovery["outcome"]
                == recovery_terminal.get("ledger_outcome")
            )
            or (
                recovery_finalization_valid
                and ledger_recovery["outcome"] == "OOF_VALIDATED_DIAGNOSTIC"
                and ledger_recovery["offline_score"]
                == f"{float(recovery_finalization['combined_holdout_score']):.9f}"
            )
        )
        and recovery_preflight["launch_allowed"]
        is parent_failed_and_disposed
        and "Prepared only" not in ledger_recovery["notes"]
        and "not pushed or launched" not in ledger_recovery["notes"]
        and "official recovery run 348522481" in ledger_recovery["notes"],
        {
            "kernel": ledger_recovery["kaggle_kernel"],
            "outcome": ledger_recovery["outcome"],
            "code_version": ledger_recovery["code_version"],
        },
    )

    failures = [item for item in checks if not item["pass"]]
    report = {
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if not failures else "fail",
        "checks_passed": len(checks) - len(failures),
        "checks_total": len(checks),
        "failures": failures,
        "warnings": warnings,
        "checks": checks,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
