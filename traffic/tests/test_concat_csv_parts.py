import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from concat_csv_parts import concatenate  # noqa: E402


class ConcatCsvPartsTest(unittest.TestCase):
    def test_keeps_one_matching_header(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            a, b, out = root / "a.csv", root / "b.csv", root / "out.csv"
            a.write_text("x,y\n1,2\n", encoding="utf-8")
            b.write_text("x,y\n3,4\n", encoding="utf-8")
            self.assertEqual(concatenate([a, b], out), 2)
            self.assertEqual(out.read_text(encoding="utf-8"), "x,y\n1,2\n3,4\n")

    def test_rejects_header_mismatch(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            a, b, out = root / "a.csv", root / "b.csv", root / "out.csv"
            a.write_text("x,y\n1,2\n", encoding="utf-8")
            b.write_text("x,z\n3,4\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "header mismatch"):
                concatenate([a, b], out)


if __name__ == "__main__":
    unittest.main()
