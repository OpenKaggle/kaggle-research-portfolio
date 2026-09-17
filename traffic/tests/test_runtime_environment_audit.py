import sys
import tempfile
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from runtime_environment_audit import (  # noqa: E402
    normalize_package_name,
    parse_requirements_lock,
)


class RuntimeEnvironmentAuditTest(unittest.TestCase):
    def test_lock_requires_exact_unique_pins(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "requirements.lock"
            path.write_text("# direct\nNumPy==2.4.6\nscikit_learn==1.8.0\n")
            self.assertEqual(
                parse_requirements_lock(path),
                {"numpy": "2.4.6", "scikit-learn": "1.8.0"},
            )
            path.write_text("numpy>=2\n")
            with self.assertRaises(ValueError):
                parse_requirements_lock(path)

    def test_normalizes_python_distribution_names(self):
        self.assertEqual(normalize_package_name("scikit_learn"), "scikit-learn")
        self.assertEqual(normalize_package_name("SCIKIT.LEARN"), "scikit-learn")


if __name__ == "__main__":
    unittest.main()
