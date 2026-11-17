"""Release boundary tests, including private files, path escapes, and data loss."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

# Major variable: the source root remains independent of the test runner's cwd.
ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("package_public", ROOT / "scripts/package_public.py")
PACKAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGE)


class PublicReleaseTests(unittest.TestCase):
    """Class: ensure only explicitly selected public files enter an archive."""

    def test_archive_contains_exact_manifest_and_three_skills(self):
        """Method: package actual public files and verify release boundaries."""
        payloads = PACKAGE.public_payloads(ROOT)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "release.zip"
            self.assertEqual(PACKAGE.build_archive(ROOT, output), len(payloads))
            with ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(set(archive.namelist()), set(payloads))
                entries = {name for name in archive.namelist() if name.endswith("/SKILL.md")}
                self.assertEqual(entries, {
                    "construction-schema-design/SKILL.md",
                    "construction-data-migration/SKILL.md",
                    "construction-document-matching/SKILL.md"})
                self.assertFalse(any("_private" in name or "_backups" in name
                                     for name in archive.namelist()))
                for name, expected in payloads.items():
                    self.assertEqual(archive.read(name), expected)

    def test_unlisted_company_material_is_excluded(self):
        """Method: an unlisted private payload must not enter the ZIP."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "public.md").write_text("Public example")
            (root / "_private").mkdir()
            (root / "_private/company.md").write_text("SENSITIVE-COMPANY-NOTE")
            (root / "public-files.json").write_text(json.dumps({"files": ["public.md"]}))
            output = root / "release.zip"
            PACKAGE.build_archive(root, output)
            with ZipFile(output) as archive:
                self.assertEqual(archive.namelist(), ["public.md"])
                self.assertNotIn(b"SENSITIVE-COMPANY-NOTE", archive.read("public.md"))

    def test_invalid_manifests_fail_without_an_output(self):
        """Method: reject missing, private, duplicate, traversal, and invalid inputs."""
        cases = [[], ["missing.md"], ["../outside.md"], ["/absolute.md"],
                 ["_private/company.md"], ["ok.md", "ok.md"], [3],
                 ["./ok.md"], ["folder\\ok.md"], [".env"], ["old.zip"],
                 ["._ok.md"], ["old.ZIP"]]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ok.md").write_text("ok")
            (root / "old.zip").write_text("archive")
            (root / "old.ZIP").write_text("archive")
            for names in cases:
                with self.subTest(names=names):
                    (root / "public-files.json").write_text(json.dumps({"files": names}))
                    output = root / "release.zip"
                    with self.assertRaises(ValueError):
                        PACKAGE.build_archive(root, output)
                    self.assertFalse(output.exists())

    def test_symlinked_files_directories_and_manifest_are_rejected(self):
        """Method: a symlink must never redirect an allowlisted path."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "actual").mkdir()
            (root / "actual/example.md").write_text("private target")
            (root / "link.md").symlink_to(root / "actual/example.md")
            (root / "linked-dir").symlink_to(root / "actual", target_is_directory=True)
            manifest = root / "public-files.json"
            for name in ("link.md", "linked-dir/example.md"):
                manifest.write_text(json.dumps({"files": [name]}))
                with self.assertRaises(ValueError):
                    PACKAGE.public_payloads(root)
            manifest.unlink()
            (root / "actual/manifest.json").write_text('{"files":["actual/example.md"]}')
            manifest.symlink_to(root / "actual/manifest.json")
            with self.assertRaises(ValueError):
                PACKAGE.public_payloads(root)

    def test_existing_output_is_preserved(self):
        """Method: packaging must not overwrite an existing user's output."""
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "release.zip"
            output.write_bytes(b"existing output")
            with self.assertRaises(FileExistsError):
                PACKAGE.build_archive(ROOT, output)
            self.assertEqual(output.read_bytes(), b"existing output")

    def test_cli_failure_log_is_actionable_and_redacted(self):
        """Method: errors explain the cause and remedy without absolute paths."""
        with tempfile.TemporaryDirectory() as directory:
            for name, error_type in (("existing.zip", "FileExistsError"),
                                     ("invalid.txt", "ValueError")):
                output = Path(directory) / name
                if error_type == "FileExistsError":
                    output.write_bytes(b"keep")
                result = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/package_public.py"), "--output", str(output)],
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)
                event = json.loads(result.stdout)
                self.assertEqual(set(event), {"timestamp", "action", "input", "result", "error"})
                self.assertEqual(event["error"]["type"], error_type)
                self.assertTrue(event["error"]["cause"] and event["error"]["resolution"])
                self.assertNotIn(directory, result.stdout)


if __name__ == "__main__":
    unittest.main()

# 동작 설명: 비공개 자료와 잘못된 경로가 배포본에 들어가지 않는지 확인합니다.
# 기존 출력 보존과 실제 ZIP 파일 목록도 함께 검사합니다.
