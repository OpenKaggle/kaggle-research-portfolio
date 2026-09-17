import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import test_finalize_oof  # noqa: E402
from finalize_oof_parent import finalize_parent  # noqa: E402


OFFICIAL_STATUS_SOURCE = "Official Kaggle kernel status and execution log APIs"
OFFICIAL_ACTIVITY_SOURCE = "Official authenticated Kaggle Notebook UI Logs page"


class FinalizeOOFParentTests(unittest.TestCase):
    def make_fixture(self, root: Path):
        base = test_finalize_oof.FinalizeOOFTests()
        run_dir, protocol, ledger = base.make_fixture(root)
        kernel = "owner/parent-oof"
        version = 12345
        run_url = f"https://www.kaggle.com/code/{kernel}/edit/run/{version}"

        activity = root / "activity.json"
        activity.write_text(
            json.dumps(
                {
                    "source": OFFICIAL_ACTIVITY_SOURCE,
                    "kernel": kernel,
                    "script_version_id": version,
                    "run_url": run_url,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        completion = root / "completion.json"
        completion.write_text(
            json.dumps(
                {
                    "source": OFFICIAL_STATUS_SOURCE,
                    "kernel": kernel,
                    "status": "COMPLETE",
                    "failure_message": None,
                    "log_api_error": None,
                    "script_version_id": version,
                    "run_url": run_url,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        metadata = root / "metadata.json"
        metadata.write_text(
            json.dumps(
                {
                    "id": kernel,
                    "is_private": True,
                    "enable_gpu": True,
                    "enable_internet": False,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        local_source = root / "local.py"
        remote_source = root / "remote.py"
        local_source.write_text("print('bound')\n", encoding="utf-8")
        remote_source.write_bytes(local_source.read_bytes())
        return (
            run_dir,
            protocol,
            ledger,
            activity,
            completion,
            local_source,
            remote_source,
            metadata,
        )

    def finalize(self, root: Path, fixture):
        (
            run_dir,
            protocol,
            ledger,
            activity,
            completion,
            local_source,
            remote_source,
            metadata,
        ) = fixture
        return finalize_parent(
            run_dir,
            protocol,
            activity,
            completion,
            local_source,
            remote_source,
            metadata,
            root / "validation.json",
            root / "analysis.json",
            root / "finalization.json",
            root / "binding.json",
            ledger,
        )

    def test_finalizes_only_exact_bound_parent_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.make_fixture(root)
            report, exit_code = self.finalize(root, fixture)
            self.assertEqual(exit_code, 0, report)
            self.assertEqual(report["status"], "accepted_parent_oof_finalization")
            self.assertEqual(report["script_version_id"], 12345)
            self.assertFalse(report["competition_submission_authorized"])
            with fixture[2].open(encoding="utf-8", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["outcome"], "OOF_VALIDATED_DIAGNOSTIC")

    def test_rejects_different_completed_version_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.make_fixture(root)
            completion = fixture[4]
            payload = json.loads(completion.read_text(encoding="utf-8"))
            payload["script_version_id"] += 1
            completion.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            before = fixture[2].read_bytes()
            with self.assertRaisesRegex(ValueError, "script version"):
                self.finalize(root, fixture)
            self.assertEqual(fixture[2].read_bytes(), before)
            self.assertFalse((root / "binding.json").exists())
            self.assertFalse((root / "validation.json").exists())


if __name__ == "__main__":
    unittest.main()
