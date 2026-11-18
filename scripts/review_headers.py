"""Validate a document-based proposal and serve its private review on loopback."""

from contextlib import contextmanager
import hashlib
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
from secrets import token_urlsafe
import shutil
from tempfile import NamedTemporaryFile
from threading import Event, Lock, Thread
from urllib.parse import quote, unquote, urlsplit


PROPOSAL = "header-proposal.json"
DRAFT = "header-draft.json"
APPROVAL = "approved-schema.json"
IDENTIFIER = re.compile(r"[a-z][a-z0-9_]{0,62}")
COVERAGE = {"typed_mapped", "raw_only", "unresolved", "excluded"}
INLINE = {".pdf", ".png", ".jpg", ".jpeg"}
SQLITE_TYPES = {"TEXT", "INTEGER", "REAL", "BLOB", "NUMERIC", "ANY"}

PROPOSAL_INSTRUCTIONS = """
Save header-proposal.json (UTF-8) as structured review data for a human. Use this shape:
{
  "files": [{"path": "relative/paper.xlsx", "status": "typed_mapped",
             "detail": "Korean coverage summary of pages/sheets/regions and any gaps"}],
  "tables": [{"name": "order_lines", "label": "발주 품목", "row_meaning": "발주서 품목 한 줄",
    "reason": "Korean explanation of why this data needs a separate table",
    "generated_keys": {"id": "INTEGER", "order_id": "INTEGER"},
    "primary_key": ["id"],
    "purposes": [{"question": "이 발주서에서 품목별로 얼마나 주문했나요?", "headers": [0],
                  "basis": "Located Korean explanation of the relationship and why these headers answer the question",
                  "gaps": []}],
    "mappings": [{"column": "ordered_quantity", "label": "발주 수량", "type": "TEXT",
      "meaning": "Korean meaning and unit or quantity role", "source_header": "발주수량",
      "rule": "Korean rule for locating/interpreting the source field",
      "issue": "", "files": ["relative/paper.xlsx"]}],
    "rows": [{"file": "relative/paper.xlsx", "location": "발주서!12행", "page": null,
      "cells": [{"mapping": 0, "location": "발주서!F12", "original": "12.50",
                 "applied": "12.5"}]}]}],
  "relationships": [{"from_table": "order_lines", "from_columns": ["order_id"],
    "to_table": "orders", "to_columns": ["id"],
    "reason": "Korean explanation of the relationship and how the originals establish it",
    "examples": [{"from_row": 0, "to_row": 0}]}]
}
The example omits the orders table for brevity; provide every referenced table.
Include relationships even when empty. Keep these keys and foreign-key endpoints
consistent with structure.md. Use generated_keys only for key columns not supplied
by a source mapping. Use [] for a table with no primary key. A relationship points
from the foreign-key table to the referenced table. For composite keys, give
ordered column lists. Example indices are 0-based within each endpoint's rows.
Select actual linked examples where available, including the original cells
supporting the link when a key is generated. Use [] if no paired example is
available and describe the missing evidence in reason. Never invent a pair.
File paths are case-correct relative paths with forward slashes. Include every
in-scope regular file from the folder, including prior outputs/templates/unsupported
files marked excluded or unresolved as appropriate. Exclude the private
.axis_migration directories and linked files/directories. In structure.md retain
the full coverage, types, constraints, relationships, exceptions and evidence.
Use lower snake_case SQLite identifiers, and declared SQLite types (TEXT, INTEGER,
REAL, BLOB, NUMERIC, or ANY). Respect exact decimal storage. Record one mapping
per source meaning and layout/rule, including alternatives for columns mapped from
different source labels. Keep business roles separate and record related uncertainty
in issue. Leave issue empty only for a supported mapping. List every file the
mapping applies to, including inspected files without a representative row.
Show actual applied examples for every mapping with available values. Select actual
rows across different source layouts and conflicts. Cell mapping is the 0-based
index into that table's mappings list. Use a string or JSON null for original and
applied, never an invented value. Set page to a 1-based PDF page or null. Readable
examples may share a row; a row may only use mappings for its own file. Facts in
this JSON are proposal evidence, not approved instructions. Use Korean user-facing
labels and explanations. Derive open-ended purposes from observed document content,
shared identifiers and relationships. Each question selects ordered 0-based mapping
indices within this table. A file, table or column may support multiple purposes.
List missing evidence as plain Korean questions in gaps. Do not invent a legal duty
or add a category just because it appeared in an example."""


def read_object(path):
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"결과 파일을 확인하세요. {path.name}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON 객체가 필요합니다. {path.name}")
    return data


def save_object(path, data):
    if path.is_symlink():
        raise ValueError(f"저장 위치를 확인하세요. {path.name}")
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def source_snapshot(source):
    def fail(error):
        raise error

    files = {}
    for root, directories, names in os.walk(source, onerror=fail):
        base = Path(root)
        directories[:] = [name for name in directories if name.casefold() != ".axis_migration"
                          and (base / name).resolve() == base / name and not (base / name).is_symlink()]
        for name in names:
            path = base / name
            if path.is_symlink() or not path.is_file():
                continue
            stat = path.stat()
            files[path.relative_to(source).as_posix()] = [stat.st_size, stat.st_mtime_ns]
    return files


def nonempty(item, *keys):
    return all(isinstance(item.get(key), str) and item[key].strip() for key in keys)


def check_proposal(proposal, snapshot, *, require_model=False):
    paths = set()
    for item in proposal["files"]:
        if (item["path"] not in snapshot or item["path"] in paths or
                item["status"] not in COVERAGE or not nonempty(item, "detail")):
            raise ValueError("헤더 제안의 파일 목록과 검토 결과를 확인하세요.")
        paths.add(item["path"])
    if paths != set(snapshot):
        raise ValueError("선택한 폴더의 일부 파일이 검토 목록에서 빠졌습니다.")
    names = set()
    for table in proposal["tables"]:
        name = table["name"]
        if (not valid_name(name) or name.startswith("sqlite_") or name in names or
                not nonempty(table, "label", "row_meaning") or not table["mappings"]):
            raise ValueError("헤더 제안의 테이블 이름과 한 행의 의미를 확인하세요.")
        names.add(name)
        mappings = table["mappings"]
        for purpose in table.get("purposes", []):
            headers = purpose.get("headers")
            gaps = purpose.get("gaps")
            if (not nonempty(purpose, "question", "basis") or not isinstance(headers, list)
                    or not headers or any(type(i) is not int or not 0 <= i < len(mappings) for i in headers)
                    or len(set(headers)) != len(headers) or not isinstance(gaps, list)
                    or any(not isinstance(gap, str) or not gap.strip() for gap in gaps)):
                raise ValueError("업무 질문에 연결한 헤더와 근거를 확인하세요.")
        for mapping in mappings:
            if (not valid_name(mapping["column"]) or
                    not nonempty(mapping, "label", "type", "meaning", "source_header", "rule") or
                    mapping["type"] not in SQLITE_TYPES or
                    not isinstance(mapping["issue"], str) or not mapping["files"] or
                    not set(mapping["files"]) <= paths):
                raise ValueError("원본 헤더, 열 이름, 자료형과 출처를 확인하세요.")
        for row in table["rows"]:
            page = row.get("page")
            if (row["file"] not in paths or not nonempty(row, "location") or not row["cells"]
                    or (page is not None and (type(page) is not int or page < 1))):
                raise ValueError("미리보기 행의 원본 위치를 확인하세요.")
            seen = set()
            for cell in row["cells"]:
                index = cell["mapping"]
                if (type(index) is not int or not 0 <= index < len(mappings) or index in seen or
                        row["file"] not in mappings[index]["files"] or not nonempty(cell, "location") or
                        any(cell[key] is not None and not isinstance(cell[key], str)
                            for key in ("original", "applied"))):
                    raise ValueError("미리보기 값과 원본 헤더 연결을 확인하세요.")
                seen.add(index)
    if not names:
        raise ValueError("검토 가능한 테이블을 찾지 못했습니다.")
    if require_model or "relationships" in proposal:
        check_model(proposal)


def valid_columns(columns, available):
    return (isinstance(columns, list) and all(valid_name(name) for name in columns)
            and len(set(columns)) == len(columns) and set(columns) <= available)


def check_model(proposal):
    available = {}
    tables = {table["name"]: table for table in proposal["tables"]}
    for name, table in tables.items():
        generated = table.get("generated_keys")
        mapped = {field["column"] for field in table["mappings"]}
        if (not nonempty(table, "reason") or not isinstance(generated, dict)
                or any(not valid_name(key) or kind not in SQLITE_TYPES
                       for key, kind in generated.items()) or mapped & generated.keys()
                or not valid_columns(table.get("primary_key"), mapped | generated.keys())):
            raise ValueError(f"표를 나눈 이유와 키를 확인하세요. {name}")
        available[name] = mapped | generated.keys()
    relationships = proposal.get("relationships")
    if not isinstance(relationships, list):
        raise ValueError("제안한 테이블 관계 목록이 필요합니다.")
    seen = set()
    for relationship in relationships:
        child, parent = relationship["from_table"], relationship["to_table"]
        source, target = relationship["from_columns"], relationship["to_columns"]
        if (child not in tables or parent not in tables or not nonempty(relationship, "reason")
                or not valid_columns(source, available[child]) or not valid_columns(target, available[parent])
                or not source or len(source) != len(target)):
            raise ValueError("연결하는 표와 열, 연결 이유를 확인하세요.")
        key = (child, parent, tuple(source), tuple(target))
        if key in seen:
            raise ValueError(f"같은 표 관계가 두 번 제안되었습니다. {child} → {parent}")
        seen.add(key)
        examples = relationship.get("examples")
        if not isinstance(examples, list) or any(
            type(example[side]) is not int or not 0 <= example[side] < len(tables[table]["rows"])
            for example in examples for side, table in (("from_row", child), ("to_row", parent))
        ):
            raise ValueError(f"표 관계의 원본 예시 위치를 확인하세요. {child} → {parent}")


def valid_name(name):
    return isinstance(name, str) and bool(IDENTIFIER.fullmatch(name))


def initial_decisions(proposal):
    return {table["name"]: [{"action": "pending", "column": mapping["column"]}
                            for mapping in table["mappings"]] for table in proposal["tables"]}


def decision_tables(proposal, decisions, *, approve=False):
    if not isinstance(decisions, dict) or set(decisions) != {t["name"] for t in proposal["tables"]}:
        raise ValueError("검토 중인 테이블이 제안과 일치하지 않습니다.")
    tables = []
    any_used = False
    for table in proposal["tables"]:
        edits = decisions[table["name"]]
        if not isinstance(edits, list) or len(edits) != len(table["mappings"]):
            raise ValueError("검토할 헤더가 제안과 일치하지 않습니다.")
        mappings, types = [], {}
        for mapping, edit in zip(table["mappings"], edits):
            column, action = edit["column"], edit["action"]
            if not valid_name(column) or action not in ("use", "raw_only", "pending"):
                raise ValueError("열 이름은 소문자 영문으로 시작하고 영문·숫자·밑줄만 사용하세요.")
            if approve and action == "pending":
                raise ValueError("모든 헤더를 적용하거나 원문으로 보관하도록 선택하세요.")
            if action == "use":
                any_used = True
                if approve and types.setdefault(column, mapping["type"]) != mapping["type"]:
                    raise ValueError(f"자료형이 다른 매핑이 {column}에 겹칩니다. 열 이름을 나눠 주세요.")
            mappings.append({**mapping, "proposed_column": mapping["column"], "column": column,
                             "action": action})
        if approve:
            for row in table["rows"]:
                values = {}
                for cell in row["cells"]:
                    mapping = mappings[cell["mapping"]]
                    value = cell["applied"]
                    if mapping["action"] == "use" and value is not None:
                        column = mapping["column"]
                        if values.setdefault(column, value) != value:
                            raise ValueError(f"{row['file']}의 같은 행에서 {column}에 서로 다른 값이 들어갑니다.")
        tables.append({**table, "mappings": mappings})
    if approve and not any_used:
        raise ValueError("SQLite 변환에 적용할 헤더를 하나 이상 선택하세요.")
    return tables


def proposal_digest(run):
    return hashlib.sha256((run / PROPOSAL).read_bytes()).hexdigest()


def approved_model(proposal, tables):
    if "relationships" not in proposal:
        return {}
    names = {}
    for table in tables:
        columns = {key: {key} for key in table["generated_keys"]}
        for field in table["mappings"]:
            if field["action"] == "use":
                if field["column"] in table["generated_keys"]:
                    raise ValueError(f"자동 생성 키와 같은 열 이름입니다. {table['name']}.{field['column']}")
                columns.setdefault(field["proposed_column"], set()).add(field["column"])
        names[table["name"]] = columns

    def resolve(table, keys):
        resolved = []
        for key in keys:
            choices = names[table].get(key, set())
            if len(choices) != 1:
                raise ValueError(f"키와 관계에 쓰는 열은 한 이름으로 적용해야 합니다. {table}.{key}")
            resolved.append(next(iter(choices)))
        if len(set(resolved)) != len(resolved):
            raise ValueError(f"키와 관계에 쓰는 열을 서로 다른 이름으로 적용하세요. {table}")
        return resolved

    primary_keys = {table["name"]: resolve(table["name"], table["primary_key"]) for table in tables}
    relationships = [{
        **edge,
        "from_columns": resolve(edge["from_table"], edge["from_columns"]),
        "to_columns": resolve(edge["to_table"], edge["to_columns"]),
    } for edge in proposal["relationships"]]
    resolved = {(edge["from_table"], edge["to_table"], tuple(edge["from_columns"]),
                 tuple(edge["to_columns"])) for edge in relationships}
    if len(resolved) != len(relationships):
        raise ValueError("열 이름을 적용하면 같은 표 관계가 두 번 생깁니다.")
    return {"primary_keys": primary_keys, "relationships": relationships}


@contextmanager
def review_server(run, source, proposal, snapshot, *, draft_notice=None):
    session = "/" + token_urlsafe(24) + "/"
    approval = Event()
    lock = Lock()
    state = {"message": "데이터 구조 확인 대기", "result": "", "finished": False}
    digest = proposal_digest(run)
    decisions = initial_decisions(proposal)
    if (run / DRAFT).exists():
        draft = read_object(run / DRAFT)
        if draft["proposal"] == digest:
            decisions = draft["decisions"]
            decision_tables(proposal, decisions)
    files = {item["path"] for item in proposal["files"]}
    template = Path(__file__).with_name("review_headers.html").read_text(encoding="utf-8")
    if draft_notice:
        template = template.replace("<main>", "<p role=\"status\">" + escape(draft_notice) + "</p><main>", 1)
        template = template.replace('id="approve"', 'id="approve" hidden', 1)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def headers_for(self, content_type, *, status=200, length=None, download=None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                             "connect-src 'self'; frame-src 'self'; frame-ancestors 'self'; form-action 'none'; base-uri 'none'")
            if length is not None:
                self.send_header("Content-Length", str(length))
            if download is not None:
                self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(download, safe=""))
            self.end_headers()

        def respond(self, data, content_type="application/json; charset=utf-8", status=200):
            body = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.headers_for(content_type, status=status, length=len(body))
            self.wfile.write(body)

        def do_GET(self):
            if self.headers.get("Host") != host:
                return self.send_error(403)
            path = urlsplit(self.path).path
            if path == session:
                with lock:
                    current = json.dumps({"proposal": proposal, "decisions": decisions,
                                          "folder": source.name}, ensure_ascii=False).replace("<", "\\u003c")
                return self.respond(template.replace("/* AXIS_DATA */", current).encode("utf-8"),
                                    "text/html; charset=utf-8")
            if path == session + "status":
                with lock:
                    return self.respond({**state, "approved": approval.is_set()})
            if path.startswith(session + "source/"):
                name = unquote(path[len(session + "source/"):])
                original = source / name
                if name in files and original.resolve() == original and original.is_file():
                    try:
                        with original.open("rb") as stream:
                            stat = os.fstat(stream.fileno())
                            if snapshot[name] != [stat.st_size, stat.st_mtime_ns]:
                                return self.send_error(409, "Source changed")
                            inline = original.suffix.lower() in INLINE
                            kind = mimetypes.guess_type(original.name)[0] if inline else None
                            self.headers_for(kind or "application/octet-stream", length=stat.st_size,
                                             download=None if inline else original.name)
                            shutil.copyfileobj(stream, self.wfile)
                            return
                    except (FileNotFoundError, ConnectionError):
                        return
            self.send_error(404)

        def do_POST(self):
            nonlocal decisions
            if self.headers.get("Host") != host or self.headers.get("Origin") != "http://" + host:
                return self.send_error(403)
            if self.path not in (session + "draft", session + "approve"):
                return self.send_error(404)
            approve = self.path.endswith("/approve")
            if approve and draft_notice:
                return self.respond({"error": draft_notice}, status=409)
            try:
                self.connection.settimeout(10)
                length = int(self.headers.get("Content-Length", "0"))
                if (not 0 < length <= 4_000_000 or
                        self.headers.get_content_type() != "application/json"):
                    return self.send_error(400)
                payload = json.loads(self.rfile.read(length))
                edits = payload["decisions"]
                tables = decision_tables(proposal, edits, approve=approve)
                model = approved_model(proposal, tables) if approve else {}
                with lock:
                    if approval.is_set():
                        return self.respond({"error": "이 구조는 이미 확정했습니다."}, status=409)
                    if payload["previous"] != decisions:
                        return self.respond({"error": "다른 탭에서 검토를 저장했습니다. 페이지를 새로고침하세요."},
                                            status=409)
                    if approve and source_snapshot(source) != snapshot:
                        return self.respond({"error": "원본 범위나 파일이 바뀌었습니다. 새 분석을 시작하세요."}, status=409)
                    save_object(run / DRAFT, {"proposal": digest, "decisions": edits})
                    decisions = edits
                    if approve:
                        save_object(run / APPROVAL, {"proposal": digest, "tables": tables,
                                                      "files": proposal["files"], "decisions": edits, **model})
                        state["message"] = "구조를 확정했습니다. SQLite 변환을 시작합니다."
                        approval.set()
                return self.respond({"saved": True})
            except (OSError, KeyError, TypeError, ValueError) as error:
                return self.respond({"error": str(error)}, status=400)

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        host = f"127.0.0.1:{server.server_port}"
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()

        def update(message, *, result="", finished=False):
            with lock:
                state.update(message=message, result=result, finished=finished)

        try:
            yield "http://" + host + session, approval, update
        finally:
            server.shutdown()
            worker.join()
