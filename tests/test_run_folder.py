"""Check confirmed stage reuse and the actual loopback delivery."""

import json
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

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
                    workflow.save_object(run / workflow.PROPOSAL, {
                        "files": [{"path": "example.txt", "status": "typed_mapped", "detail": "Line 1"}],
                        "tables": [{
                            "name": "lines", "label": "내역", "row_meaning": "한 줄",
                            "purposes": [{"question": question, "headers": [0], "gaps": [],
                                          "basis": "거래처가 적힌 첫 줄"}
                                         for question in ("어느 업체가 공급했나요?", "업체별 내역은 무엇인가요?")],
                            "mappings": [{"column": "supplier", "label": "업체", "type": "TEXT",
                                          "meaning": "거래처 이름", "source_header": "supplier",
                                          "rule": "콜론 뒤 원문", "issue": "", "files": ["example.txt"]}],
                            "rows": [{"file": "example.txt", "location": "1행", "page": None,
                                      "cells": [{"mapping": 0, "location": "1행", "original": "Example",
                                                 "applied": "Example"}]}],
                        }],
                    })
                elif len(called) == 2:
                    self.assertIn("approved-schema.json", prompt)
                    self.assertEqual(workflow.read_object(run / workflow.APPROVAL)["tables"][0]
                                     ["mappings"][0]["column"], "vendor")
                    return {"state": "waiting", "reason": "원본 단위 확인"}
                else:
                    self.assertIn("개", prompt)
                    with closing(sqlite3.connect(run / "data.sqlite")) as db:
                        db.executescript("""
                            CREATE TABLE documents(id INTEGER PRIMARY KEY);
                            CREATE TABLE lines(id INTEGER PRIMARY KEY, doc INTEGER REFERENCES documents(id), vendor TEXT);
                            INSERT INTO documents VALUES (1);
                            INSERT INTO lines VALUES (1, 1, 'Example');
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

            review_visits = []

            def browser(url):
                if not urlsplit(url).query:
                    review_visits.append(url)
                    with urlopen(url, timeout=5) as response:
                        self.assertIn("헤더 검토", response.read().decode())
                    with urlopen(url + "source/example.txt", timeout=5) as response:
                        self.assertIn("supplier: Example", response.read().decode())
                    previous = {"lines": [{"column": "supplier", "action": "pending"}]}
                    updated = {"lines": [{"column": "vendor", "action": "use"}]}
                    split = urlsplit(url)

                    def post(route, decisions, prior):
                        request = Request(url + route,
                                          json.dumps({"decisions": decisions, "previous": prior}).encode(),
                                          headers={"Content-Type": "application/json",
                                                   "Origin": f"{split.scheme}://{split.netloc}"})
                        with urlopen(request, timeout=5) as response:
                            self.assertTrue(json.load(response)["saved"])

                    if len(review_visits) == 1:
                        with self.assertRaises(HTTPError) as rejected:
                            post("approve", previous, previous)
                        self.assertEqual(rejected.exception.code, 400)
                        rejected.exception.close()
                        post("draft", updated, previous)
                        raise KeyboardInterrupt
                    post("approve", updated, updated)
                    return
                base = url.split("?")[0]
                with urlopen(base + "?view=source-links&file=example.txt", timeout=5) as response:
                    page = response.read().decode()
                    for text in ("example.txt:1", "어느 업체가 공급했나요?", "업체별 내역은 무엇인가요?"):
                        self.assertIn(text, page)
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
                self.assertIn(str(run / workflow.DRAFT), workflow.read_status(run)["results"])
                self.assertFalse((run / "data.sqlite").exists())
                self.assertEqual(workflow.main(["--resume", str(run)]), 2)
                self.assertEqual(workflow.read_status(run)["stage"], "SQLite 변환과 검증")
                self.assertEqual(workflow.main(["--resume", str(run), "--answer", "개"]), 0)
                self.assertEqual(called, ["design", "migration", "migration"])
                saved = workflow.read_status(run)
                self.assertEqual(saved["state"], "completed")
                self.assertEqual(workflow.main(["--resume", str(run)]), 0)
                self.assertEqual(workflow.read_status(run), saved)
                self.assertEqual(len(called), 3)
                self.assertTrue((run / "export.sql").is_file())
