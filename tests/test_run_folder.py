"""Check confirmed stage reuse and the actual loopback delivery."""

import json
from contextlib import closing
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_folder as workflow


class WorkflowTests(unittest.TestCase):
    def test_add_documents_to_existing_ledger_and_skip_repeated_bytes_after_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "문서"
            source.mkdir()
            original = source / "발주.txt"
            original.write_text("발주 수량 4", encoding="utf-8")
            run = workflow.new_run(source)
            original_snapshot = workflow.source_snapshot(source)
            metadata = {**workflow.read_object(run / "workflow.json"), "company": "Example",
                        "stage": "viewer", "snapshot": original_snapshot}
            workflow.save_object(run / "workflow.json", metadata)
            workflow.save_object(run / workflow.APPROVAL, {
                "files": [{"path": original.name}],
                "tables": [{"name": "lines", "mappings": [
                    {"column": "quantity", "type": "INTEGER", "action": "use"}]}],
            })
            workflow.save_object(run / "viewer.json", {
                "primary_table": "lines", "catalog": {"tables": {}}, "relationships": [],
                "files": [{"path": original.name, "status": "typed_mapped", "description": "발주서"}],
            })
            workflow.save_object(run / workflow.PROPOSAL, {})
            for name in ("structure.md", "validation.md"):
                (run / name).write_text("Checked", encoding="utf-8")
            with closing(sqlite3.connect(run / "data.sqlite")) as db:
                db.executescript("CREATE TABLE lines(source TEXT, quantity INTEGER);"
                                 "INSERT INTO lines VALUES ('발주.txt:1', 4), ('발주.txt:1', 4);")
            statement = source / "거래명세서.txt"
            statement.write_text("납품 수량 2", encoding="utf-8")
            bad = source / "잘못된명세서.txt"
            bad.write_text("납품 수량 9", encoding="utf-8")
            later = source / "다음주 명세서.txt"
            calls = []

            def agent(prompt, batch, _metadata):
                self.assertIn("construction-data-migration/SKILL.md", prompt)
                self.assertEqual(workflow.read_object(batch / workflow.APPROVAL),
                                 workflow.read_object(run / workflow.APPROVAL))
                (name,) = workflow.read_object(batch / workflow.APPEND_SCOPE)["new_files"]
                calls.append(name)
                with closing(sqlite3.connect(batch / "data.sqlite")) as db, db:
                    if name == bad.name:
                        db.execute("DELETE FROM lines WHERE rowid = 1")
                    db.execute("INSERT INTO lines VALUES (?, ?)", (name + ":1", 2))
                config = workflow.read_object(batch / "viewer.json")
                config["files"].append({"path": name, "status": "typed_mapped", "description": "거래명세서"})
                workflow.save_object(batch / "viewer.json", config)
                (batch / "validation.md").write_text("Checked append", encoding="utf-8")
                return {"state": "ready", "reason": ""}

            def browser(url):
                base = url.split("?")[0]
                with urlopen(url, timeout=5) as response:
                    self.assertIn('href="/add-documents"', response.read().decode())
                with urlopen(base + "add-documents", timeout=5) as response:
                    form = response.read().decode()
                token = re.search(r'name="token" value="([^"]+)"', form)[1]

                def post(name):
                    request = Request(base + "add-documents",
                                      urlencode({"token": token, "file": name}).encode(),
                                      headers={"Origin": base.rstrip("/")})
                    with urlopen(request, timeout=8) as response:
                        return response.read().decode()

                if not calls:
                    self.assertIn("서류 1개를 장부에 추가했습니다.", post(statement.name))
                    self.assertIn("이미 반영한 파일 1개", post(statement.name))
                    self.assertIn("기존 장부의 값 또는 행이 바뀌었습니다.", post(bad.name))
                    expected = []
                else:
                    self.assertIn("이미 반영한 파일 1개", post("이름만 바꾼 명세서.txt"))
                    self.assertIn("서류 1개를 장부에 추가했습니다.", post(later.name))
                    expected = ["다음주 명세서.txt:1,2"]
                with urlopen(base + "csv?table=lines", timeout=5) as response:
                    rows = response.read().decode("utf-8-sig").splitlines()
                self.assertEqual(rows, ["source,quantity", "발주.txt:1,4", "발주.txt:1,4", "거래명세서.txt:1,2",
                                        *expected])
                raise KeyboardInterrupt

            with patch.object(workflow, "run_agent", side_effect=agent), patch.object(
                    workflow.webbrowser, "open", side_effect=browser):
                self.assertEqual(workflow.main(["--resume", str(run)]), 0)
                duplicate = source / "이름만 바꾼 명세서.txt"
                duplicate.write_bytes(statement.read_bytes())
                later.write_text("다음 주 납품 수량 2", encoding="utf-8")
                self.assertEqual(workflow.main(["--resume", str(run)]), 0)
            self.assertEqual(calls, [statement.name, bad.name, later.name])
            current = run.parent / workflow.read_object(run / workflow.LEDGER)["version"]
            self.assertEqual(workflow.read_status(current)["state"], "completed")
            with closing(sqlite3.connect(run / "data.sqlite")) as db:
                self.assertEqual(db.execute("SELECT sum(quantity) FROM lines").fetchone(), (8,))

    def test_resume_migration_and_reopen_without_rereading_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "문서"
            source.mkdir()
            (source / "example.txt").write_text("supplier: Example\nnumber: DOC-1", encoding="utf-8")
            called = []

            def agent(prompt, run, metadata):
                called.append(metadata["stage"])
                if metadata["stage"] == "design":
                    self.assertIn("construction-schema-design/SKILL.md", prompt)
                    (run / "structure.md").write_text("Example contract", encoding="utf-8")
                    workflow.save_object(run / workflow.PROPOSAL, {
                        "files": [{"path": "example.txt", "status": "typed_mapped", "detail": "Line 1"}],
                        "tables": [{
                            "name": "lines", "label": "내역", "row_meaning": "한 줄",
                            "reason": "한 문서에 여러 내역이 들어갑니다.",
                            "generated_keys": {"id": "INTEGER", "doc": "INTEGER"},
                            "primary_key": ["id"],
                            "purposes": [{"question": question, "headers": [0], "gaps": [],
                                          "basis": "거래처가 적힌 첫 줄"}
                                         for question in ("어느 업체가 공급했나요?", "업체별 내역은 무엇인가요?")],
                            "mappings": [{"column": "supplier", "label": "업체", "type": "TEXT",
                                          "meaning": "거래처 이름", "source_header": "supplier",
                                          "rule": "콜론 뒤 원문", "issue": "", "files": ["example.txt"]}],
                            "rows": [{"file": "example.txt", "location": "1행", "page": None,
                                      "cells": [{"mapping": 0, "location": "1행", "original": "Example",
                                                 "applied": "Example"}]}],
                        }, {
                            "name": "documents", "label": "문서", "row_meaning": "원본 문서 하나",
                            "reason": "문서 번호를 문서마다 한 번 저장합니다.",
                            "generated_keys": {"id": "INTEGER"},
                            "primary_key": ["id"],
                            "mappings": [{"column": "number", "label": "문서 번호", "type": "TEXT",
                                          "meaning": "원본 문서 번호", "source_header": "number",
                                          "rule": "파일에서 문서 번호를 읽음", "issue": "",
                                          "files": ["example.txt"]}],
                            "rows": [{"file": "example.txt", "location": "2행", "page": None,
                                      "cells": [{"mapping": 0, "location": "2행", "original": "DOC-1",
                                                 "applied": "DOC-1"}]}],
                        }],
                        "relationships": [{
                            "from_table": "lines", "from_columns": ["doc"],
                            "to_table": "documents", "to_columns": ["id"],
                            "reason": "내역은 같은 원본에 적힌 문서 번호를 참조합니다.",
                            "examples": [{"from_row": 0, "to_row": 0}],
                        }],
                    })
                elif len(called) == 2:
                    self.assertIn("construction-data-migration/SKILL.md", prompt)
                    self.assertIn("approved-schema.json", prompt)
                    approval = workflow.read_object(run / workflow.APPROVAL)
                    self.assertEqual(approval["tables"][0]["mappings"][0]["column"], "vendor")
                    self.assertEqual(approval["relationships"][0]["from_columns"], ["doc"])
                    return {"state": "waiting", "reason": "원본 단위 확인"}
                else:
                    self.assertIn("개", prompt)
                    with closing(sqlite3.connect(run / "data.sqlite")) as db:
                        db.executescript("""
                            CREATE TABLE documents(id INTEGER PRIMARY KEY, number TEXT);
                            CREATE TABLE lines(id INTEGER PRIMARY KEY, doc INTEGER REFERENCES documents(id), vendor TEXT);
                            INSERT INTO documents VALUES (1, 'DOC-1');
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
                        page = response.read().decode()
                        self.assertIn("관계도", page)
                        self.assertIn("내역은 같은 원본에 적힌 문서 번호를 참조합니다.", page)
                    with urlopen(url + "source/example.txt", timeout=5) as response:
                        self.assertIn("supplier: Example", response.read().decode())
                    previous = {"lines": [{"column": "supplier", "action": "pending"}],
                                "documents": [{"column": "number", "action": "pending"}]}
                    updated = {"lines": [{"column": "vendor", "action": "use"}],
                               "documents": [{"column": "number", "action": "use"}]}
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

    def test_renamed_composite_relationship_must_exist_in_sqlite(self):
        proposal = {"relationships": [{
            "from_table": "lines", "from_columns": ["source", "order_no"],
            "to_table": "orders", "to_columns": ["site", "number"],
        }]}
        tables = [{
            "name": "orders", "generated_keys": {"site": "TEXT", "number": "TEXT"},
            "primary_key": ["site", "number"], "mappings": [],
        }, {
            "name": "lines", "generated_keys": {"source": "TEXT"}, "primary_key": [],
            "mappings": [{"proposed_column": "order_no", "column": "order_number",
                          "type": "TEXT", "action": "use"}],
        }]
        model = workflow.approved_model(proposal, tables)
        self.assertEqual(model["relationships"][0]["from_columns"], ["source", "order_number"])
        approved = {"tables": tables, **model}
        with closing(sqlite3.connect(":memory:")) as db:
            db.executescript("""
                CREATE TABLE orders(site TEXT, number TEXT, PRIMARY KEY(site, number));
                CREATE TABLE lines(source TEXT, order_number TEXT);
            """)
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
            with self.assertRaisesRegex(ValueError, "확정한 외래 키가 SQLite에 없습니다"):
                workflow.verify_model(db, approved)
            db.executescript("""
                DROP TABLE lines;
                CREATE TABLE lines(source TEXT, order_number TEXT,
                    FOREIGN KEY(source, order_number) REFERENCES orders);
            """)
            workflow.verify_model(db, approved)
        tables[1]["mappings"][0]["action"] = "raw_only"
        with self.assertRaisesRegex(ValueError, "lines.order_no"):
            workflow.approved_model(proposal, tables)
