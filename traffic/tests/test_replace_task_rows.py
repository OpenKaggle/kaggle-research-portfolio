from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "replace_task_rows.py"
SPEC = importlib.util.spec_from_file_location("replace_task_rows", MODULE_PATH)
replace_task_rows = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(replace_task_rows)


class ReplaceTaskRowsTests(unittest.TestCase):
    def test_replaces_only_queue_rows_and_normalizes_timestamp_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            anchor = root / "anchor.csv"
            anchor.write_text(
                "submission_id,task,speed_kmh,flow_vph,queue_pred,path_flow\n"
                "1,state,80,1000,0,0\n"
                "2,queue,0,0,0,0\n"
                "3,odme,0,0,0,12.5\n",
                encoding="utf-8",
            )
            key = root / "key.csv"
            key.write_text(
                "submission_id,task,panel,timestamp,station_id,link_id,mask_regime,window_id,departure_time,path_id\n"
                "1,state,P,2031-01-01T00:00:00Z,S,L,R1,,,\n"
                "2,queue,,2031-01-01T00:05:00Z,,L,,W,,\n"
                "3,odme,P,,,,,,,PM,P1\n",
                encoding="utf-8",
            )
            replacement = root / "queue.csv"
            replacement.write_text(
                "window_id,timestamp,link_id,queue_pred\n"
                "W,2031-01-01 00:05:00+00:00,L,1\n",
                encoding="utf-8",
            )
            output = root / "output.csv"
            report = replace_task_rows.replace_task(anchor, key, replacement, "queue", output)
            self.assertEqual(report["target_rows"], 1)
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                "submission_id,task,speed_kmh,flow_vph,queue_pred,path_flow\n"
                "1,state,80,1000,0,0\n"
                "2,queue,0,0,1,0\n"
                "3,odme,0,0,0,12.5\n",
            )

    def test_rejects_missing_replacement_key_without_leaving_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            anchor = root / "anchor.csv"
            anchor.write_text(
                "submission_id,task,speed_kmh,flow_vph,queue_pred,path_flow\n2,queue,0,0,0,0\n",
                encoding="utf-8",
            )
            key = root / "key.csv"
            key.write_text(
                "submission_id,task,window_id,timestamp,link_id\n2,queue,W,2031-01-01T00:05:00Z,L\n",
                encoding="utf-8",
            )
            replacement = root / "queue.csv"
            replacement.write_text(
                "window_id,timestamp,link_id,queue_pred\nX,2031-01-01T00:05:00Z,L,1\n",
                encoding="utf-8",
            )
            output = root / "output.csv"
            with self.assertRaisesRegex(ValueError, "replacement lacks key"):
                replace_task_rows.replace_task(anchor, key, replacement, "queue", output)
            self.assertFalse(output.exists())

    def test_preserves_identical_queue_row_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            anchor = root / "anchor.csv"
            anchor.write_text(
                "submission_id,task,speed_kmh,flow_vph,queue_pred,path_flow\n"
                "1,queue,0.0,0.0,1.0,0.0\n",
                encoding="utf-8",
            )
            key = root / "key.csv"
            key.write_text(
                "submission_id,task,window_id,timestamp,link_id\n"
                "1,queue,W,2031-01-01T00:05:00Z,L\n",
                encoding="utf-8",
            )
            replacement = root / "queue.csv"
            replacement.write_text(
                "window_id,timestamp,link_id,queue_pred\n"
                "W,2031-01-01T00:05:00Z,L,1\n",
                encoding="utf-8",
            )
            output = root / "output.csv"
            replace_task_rows.replace_task(anchor, key, replacement, "queue", output)
            self.assertEqual(output.read_bytes(), anchor.read_bytes())


if __name__ == "__main__":
    unittest.main()
