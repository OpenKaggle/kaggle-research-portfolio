#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/extract_owned_raw_features_v1.py"
SPEC = importlib.util.spec_from_file_location("owned_raw", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.path.insert(0, str(ROOT / "scripts"))
SPEC.loader.exec_module(MODULE)
FIXTURE = ROOT / "artifacts/fixtures/stage2_native_owned_raw_v1"


class OwnedRawPackageV1Test(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def copy_case(self, name: str = "renamed", target_name: str | None = None) -> Path:
        target = self.root / (target_name or name)
        shutil.copytree(FIXTURE / name, target, ignore=shutil.ignore_patterns("work", "predictions.csv"))
        return target

    def run_extract(
        self,
        case: Path,
        output_name: str = "features.npz",
        *,
        require_all: bool = True,
        allow_unlisted: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        command = [
                sys.executable,
                str(SCRIPT),
                "--sensor-root",
                str(case / "raw"),
                "--input-qa",
                str(case / "qa.csv"),
                "--output",
                str(self.root / output_name),
                "--report",
                str(self.root / (output_name + ".json")),
                "--require-manifest",
            ]
        if require_all:
            command.append("--require-all-clips")
        if allow_unlisted:
            command.append("--allow-manifest-unlisted-clips-as-all-missing")
        return subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
        )

    def assert_fails_closed(self, case: Path, phrase: str) -> None:
        result = self.run_extract(case)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(phrase.lower(), (result.stdout + result.stderr).lower())
        self.assertFalse((self.root / "features.npz").exists())

    def first_unit(self, case: Path) -> Path:
        units = MODULE.discover_units(case / "raw")
        return units[sorted(units)[0]]

    def test_missing_declared_file_fails_closed(self) -> None:
        case = self.copy_case()
        (self.first_unit(case) / "Radar" / "Radar.csv").unlink()
        self.assert_fails_closed(case, "missing or extra radar")

    def test_missing_manifest_declared_unit_fails_closed_even_when_unlisted_is_allowed(self) -> None:
        case = self.copy_case()
        shutil.rmtree(self.first_unit(case))
        result = self.run_extract(case, require_all=False, allow_unlisted=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("manifest-declared raw unit is missing", (result.stdout + result.stderr).lower())
        self.assertFalse((self.root / "features.npz").exists())

    def test_corrupt_file_fails_closed(self) -> None:
        case = self.copy_case()
        path = sorted((self.first_unit(case) / "Skeleton" / "predictions").glob("*.json"))[0]
        path.write_text("{not-json", encoding="utf-8")
        self.assert_fails_closed(case, "corrupt skeleton")

    def test_short_stream_fails_closed(self) -> None:
        case = self.copy_case()
        paths = sorted((self.first_unit(case) / "Skeleton" / "predictions").glob("*.json"))
        for path in paths[1:]:
            path.unlink()
        self.assert_fails_closed(case, "short, missing, or extra skeleton")

    def test_extra_file_fails_closed(self) -> None:
        case = self.copy_case()
        (self.first_unit(case) / "unexpected.txt").write_text("unexpected", encoding="utf-8")
        self.assert_fails_closed(case, "extra raw entry")

    def test_reordered_qa_and_manifest_are_byte_deterministic(self) -> None:
        first = self.copy_case()
        second = self.copy_case("renamed", "renamed_reordered")
        qa = pd.read_csv(second / "qa.csv", dtype=str, keep_default_na=False)
        qa.iloc[::-1].to_csv(second / "qa.csv", index=False)
        manifest_path = second / "raw/manifest_nonvisual.csv"
        manifest = pd.read_csv(manifest_path, dtype=str, keep_default_na=False)
        manifest.iloc[::-1].to_csv(manifest_path, index=False)
        run_a = self.run_extract(first, "ordered.npz")
        run_b = self.run_extract(second, "reordered.npz")
        self.assertEqual(run_a.returncode, 0, run_a.stderr)
        self.assertEqual(run_b.returncode, 0, run_b.stderr)
        self.assertEqual((self.root / "ordered.npz").read_bytes(), (self.root / "reordered.npz").read_bytes())

    def test_manifest_unlisted_clip_requires_explicit_all_missing_authorization(self) -> None:
        case = self.copy_case()
        qa = pd.read_csv(case / "qa.csv", dtype=str, keep_default_na=False)
        extra = qa.iloc[[0]].copy()
        extra["qa_id"] = "qa_with_legitimate_all_sensor_missing_clip"
        extra["path"] = "incoming_batch_alpha/no_sensor_clip/Depth/Depth.mp4"
        pd.concat([qa, extra], ignore_index=True).to_csv(case / "qa.csv", index=False)
        rejected = self.run_extract(case, "rejected.npz", require_all=False)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("explicit all-missing authorization required", (rejected.stdout + rejected.stderr).lower())
        accepted = self.run_extract(case, "accepted.npz", require_all=False, allow_unlisted=True)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        report = json.loads((self.root / "accepted.npz.json").read_text())
        self.assertEqual(report["manifest_unlisted_clips_treated_as_all_sensor_missing"], 1)

    def test_arbitrary_new_clip_cache_matches_official_twin(self) -> None:
        original = self.copy_case("original")
        renamed = self.copy_case("renamed")
        run_a = self.run_extract(original, "original.npz")
        run_b = self.run_extract(renamed, "renamed.npz")
        self.assertEqual(run_a.returncode, 0, run_a.stderr)
        self.assertEqual(run_b.returncode, 0, run_b.stderr)
        with np.load(self.root / "original.npz") as left, np.load(self.root / "renamed.npz") as right:
            for name in ("imu", "radar", "skeleton"):
                np.testing.assert_equal(left[name], right[name])
        left_prediction = pd.read_csv(FIXTURE / "original/predictions.csv")["prediction"].tolist()
        right_prediction = pd.read_csv(FIXTURE / "renamed/predictions.csv")["prediction"].tolist()
        self.assertEqual(left_prediction, right_prediction)
        report = json.loads((FIXTURE / "renamed/work/raw_feature_report.json").read_text())
        self.assertTrue(report["network_isolation"]["socket_probe_blocked"])
        self.assertEqual(report["unmatched_qa_clips"], 0)


if __name__ == "__main__":
    unittest.main()
