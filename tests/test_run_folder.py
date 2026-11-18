"""Check confirmed stage reuse and the actual loopback delivery."""

import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_folder as workflow


class WorkflowTests(unittest.TestCase):
    def test_resume_migration_and_reopen_without_rereading_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "문서"
            source.mkdir()
            (source / "example.txt").write_text("supplier: Example", encoding="utf-8")
            called = []

            def agent(prompt, run, metadata):
                called.append(metadata["stage"])
                if metadata["stage"] == "design":
                    (run / "structure.md").write_text("Example contract", encoding="utf-8")
                elif len(called) == 2:
                    return {"state": "waiting", "reason": "원본 단위 확인"}
                else:
                    self.assertIn("개", prompt)
                    with sqlite3.connect(run / "data.sqlite") as db:
                        db.executescript("""
                            CREATE TABLE documents(id INTEGER PRIMARY KEY);
                            CREATE TABLE lines(id INTEGER PRIMARY KEY, doc INTEGER REFERENCES documents(id));
                            INSERT INTO documents VALUES (1);
                            INSERT INTO lines VALUES (1, 1);
                        """)
                    (run / "validation.md").write_text("Checked sample", encoding="utf-8")
                    (run / "viewer.json").write_text(json.dumps({
                        "primary_table": "lines",
                        "catalog": {"tables": {"documents": {"title": "문서"}, "lines": {"title": "내역"}}},
                        "files": [{"path": "example.txt", "description": "거래 자료", "status": "typed_mapped"}],
                        "relationships": [{"file": "example.txt", "kind": "업체", "name": "Example",
                                           "evidence": "example.txt:1", "status": "candidate"}],
                    }), encoding="utf-8")
                return {"state": "ready", "reason": ""}

            def browser(url):
                base = url.split("?")[0]
                with urlopen(base + "?view=source-links&file=example.txt", timeout=5) as response:
                    self.assertIn("example.txt:1", response.read().decode())
                with urlopen(base + "?view=table-links", timeout=5) as response:
                    page = response.read().decode()
                    self.assertIn('?table=documents', page)
                    self.assertIn(" → ", page)
                raise KeyboardInterrupt

            with patch.object(workflow, "run_agent", side_effect=agent), patch.object(
                    workflow.webbrowser, "open", side_effect=browser):
                self.assertEqual(workflow.main(["--input", str(source), "--company", "Example"]), 2)
                run = next((source.parent / "output" / source.name).iterdir())
                self.assertEqual(workflow.read_status(run)["state"], "waiting")
                self.assertEqual(workflow.main(["--resume", str(run), "--answer", "개"]), 0)
                self.assertEqual(called, ["design", "migration", "migration"])
                saved = workflow.read_status(run)
                self.assertEqual(saved["state"], "completed")
                self.assertEqual(workflow.main(["--resume", str(run)]), 0)
                self.assertEqual(workflow.read_status(run), saved)
                self.assertEqual(len(called), 3)
                self.assertTrue((run / "export.sql").is_file())
