from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "compare_merged_submissions.py"
SPEC = importlib.util.spec_from_file_location("compare_merged_submissions", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


class CompareMergedSubmissionTests(unittest.TestCase):
    def test_reports_isolated_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            anchor = root / "anchor.csv"
            candidate = root / "candidate.csv"
            header = "submission_id,task,speed_kmh,flow_vph,queue_pred,path_flow\n"
            anchor.write_text(header + "1,state,80,1000,0,0\n2,queue,0,0,1,0\n", encoding="utf-8")
            candidate.write_text(header + "1,state,80,1000,0,0\n2,queue,0,0,0,0\n", encoding="utf-8")
            report = module.compare(anchor, candidate)
            self.assertEqual(report["changed_rows"], 1)
            self.assertEqual(report["changed_rows_by_task"], {"queue": 1})
            self.assertEqual(report["changed_cells_by_column"], {"queue_pred": 1})

    def test_rejects_length_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            header = "submission_id,task,speed_kmh,flow_vph,queue_pred,path_flow\n"
            anchor = root / "anchor.csv"
            candidate = root / "candidate.csv"
            anchor.write_text(header + "1,state,80,1000,0,0\n", encoding="utf-8")
            candidate.write_text(header, encoding="utf-8")
            with self.assertRaises(ValueError):
                module.compare(anchor, candidate)


if __name__ == "__main__":
    unittest.main()
