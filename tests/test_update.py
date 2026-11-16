"""Offline update and rollback preservation checks."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('updater', Path(__file__).resolve().parents[1] / 'scripts/update.py')
UPDATER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPDATER)


class UpdateTests(unittest.TestCase):
    """Check release validation and recoverable installation changes."""

    def test_versions(self):
        """Ignore prereleases and sort stable tags numerically."""
        with patch.object(UPDATER, 'git', return_value='a\trefs/tags/v0.9.0\nb\trefs/tags/v0.10.0\nc\trefs/tags/v1.0.0-rc1'):
            self.assertEqual(UPDATER.release_tags('unused'), ['v0.9.0', 'v0.10.0'])
        with self.assertRaises(ValueError):
            UPDATER.repository('../../bad')

    def test_swap_and_rollback(self):
        """Keep current data and release-specific instructions through rollback."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            current, staged = root / 'axis', root / 'stage'
            for target, value in ((current, 'old'), (staged, 'new')):
                (target / 'output').mkdir(parents=True)
                (target / 'output/agents.md').write_text(value)
                (target / 'VERSION').write_text(value)
            (current / 'output/data.sqlite').write_bytes(b'user-data')
            (current / 'config').mkdir()
            (current / 'config/company.json').write_text('{}')
            backup = UPDATER.install(current, staged)
            self.assertEqual((current / 'output/data.sqlite').read_bytes(), b'user-data')
            self.assertEqual((current / 'output/agents.md').read_text(), 'new')
            self.assertEqual((backup / 'VERSION').read_text(), 'old')
            (current / 'output/data.sqlite').write_bytes(b'new-data')
            UPDATER.install(current, backup)
            self.assertEqual((current / 'VERSION').read_text(), 'old')
            self.assertEqual((current / 'output/data.sqlite').read_bytes(), b'new-data')
            self.assertTrue((current / 'config/company.json').exists())

    def test_failed_swap_restores_installation(self):
        """A failed second rename leaves the original installation in place."""
        with tempfile.TemporaryDirectory() as folder:
            current = Path(folder) / 'axis'
            current.mkdir()
            (current / 'VERSION').write_text('old')
            with self.assertRaises(FileNotFoundError):
                UPDATER.install(current, Path(folder) / 'missing')
            self.assertEqual((current / 'VERSION').read_text(), 'old')

    def test_invalid_release(self):
        """Reject incomplete releases before modifying an installation."""
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                UPDATER.validate(Path(folder), 'v0.2.0')


if __name__ == '__main__':
    unittest.main()

# 동작 설명: 네트워크 없이 버전 선택, 데이터 보존, 복구와 실패 처리를 검증합니다.
