from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import axis_tools


class VerifyDbTest(unittest.TestCase):
    def test_reports_missing_result_instead_of_raising(self):
        with tempfile.TemporaryDirectory() as folder:
            result = axis_tools.verify_db(Path(folder))
        self.assertFalse(result["ok"])
        self.assertIn("structure.md", result["problem"])


if __name__ == "__main__":
    unittest.main()
