"""Stream an approved Axis run without copying source files to the hosted viewer."""

from collections import defaultdict
from contextlib import closing
from hashlib import sha256
from pathlib import Path, PurePosixPath
import re
import sqlite3
import sys
from urllib.parse import urlencode

from snapshot import emit, remove_machine_paths

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from run_folder import APPROVAL, LEDGER, checked_approval, identifier, read_object, resume_context, verify
from view_db import column_info, table_info


def relative(value):
    return value.replace("\\", "/") if isinstance(value, str) else ""


def graph_data(files, relationships):
    nodes = []
    file_nodes = {}
    for number, file in enumerate(files, 1):
        source = relative(file["path"])
        node = {"id": f"F{number}", "kind": "file", "label": PurePosixPath(source).name,
                "relativePath": source, "sourcePath": source, "note": file["description"]}
        file_nodes[source] = node
        nodes.append(node)
    terms = {}
    edges = []
    for number, link in enumerate(relationships, 1):
        key = link["kind"], link["name"]
        if key not in terms:
            target = {"id": f"T{len(terms)+1}", "label": link["name"],
                      "kind": "company" if link["kind"] == "업체" else "site"}
            terms[key] = target
            nodes.append(target)
        file = file_nodes[relative(link["file"])]
        edges.append({"id": f"E{number}", "from": file["id"], "to": terms[key]["id"],
                      "label": link["kind"], "status": "observed" if link["status"] == "confirmed" else "candidate",
                      "note": link["evidence"], "evidence": [{"source_id": file["id"], "basis": link["evidence"]}]})
    return {"nodes": nodes, "edges": edges, "counts": {"files": len(file_nodes)}}, file_nodes


def stored_value(value):
    if isinstance(value, bytes):
        return value.hex()
    if type(value) is int and abs(value) > 2**53 - 1:
        return str(value)
    return remove_machine_paths(value)


def source_entry(row, file_nodes):
    path = relative(row.get("source_file") or row.get("source_path") or row.get("relative_path"))
    file = file_nodes.get(path)
    if file:
        return file["id"], path, str(row.get("source_location") or row.get("location") or "")


def row_binding(key, row, file_nodes, references):
    direct = source_entry(row, file_nodes)
    document = row.get("document_id")
    line = row.get("line_id")
    related = references.get((document, line), []) if document is not None else []
    entries = [direct] if direct else related
    sources = [{"node_id": file_id, "label": path, "location": location,
                "url": "source.html?" + urlencode({"dataset": key, "id": file_id})}
               for file_id, path, location in dict.fromkeys(entries)]
    ids = sorted({source["node_id"] for source in sources})
    return {"node_ids": ids, "sources": sources,
            "location": sources[0]["location"] if sources else ""}


def current_version(run):
    """Return the run folder holding the latest verified ledger rows."""
    if not (run / LEDGER).is_file():
        return run
    current = run.parent / read_object(run / LEDGER)["version"]
    if current == run:
        return run
    if (current.parent != run.parent or current.resolve(strict=True) != current
            or read_object(current / "workflow.json").get("ledger") != run.name):
        raise ValueError("장부의 결과 폴더를 확인하세요.")
    return current


def snapshot_folder(path):
    run, source = resume_context(path)
    workflow = read_object(run / "workflow.json")
    key = workflow.get("hosted_dataset", "")
    if (workflow.get("stage") != "viewer" or not workflow.get("header_review")
            or not re.fullmatch(r"run-[a-f0-9]{32}", key)):
        raise ValueError("검토 승인과 SQLite 검증을 마친 배포 대상 작업이 필요합니다.")
    data = current_version(run)
    if data == run:
        checked_approval(run, source, workflow["snapshot"])
        primary, catalog = verify(run, export=False)
    else:
        # A ledger version keeps the first approval unchanged and covers every hashed document.
        if read_object(data / APPROVAL) != read_object(run / APPROVAL):
            raise ValueError("장부 버전의 확정 구조가 처음 승인한 구조와 다릅니다.")
        primary, catalog = verify(data, export=False, expected_paths=set(read_object(run / LEDGER)["hashes"]))
    graph, file_nodes = graph_data(catalog.pop("source_files"), catalog.pop("source_relationships"))
    if catalog.get("purpose_tables"):
        catalog["purpose_tables"] = [{k: v for k, v in t.items() if k != "rows"} for t in catalog["purpose_tables"]]
    digest = sha256()
    for name in ("data.sqlite", "viewer.json", APPROVAL):
        with (data / name).open("rb") as stream:
            digest.update(name.encode())
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    label = f"{source.parent.name} / {source.name}" if re.fullmatch(r"\d{1,2}월", source.name) else source.name
    emit("dataset", id=key, label=label, description=f"검토를 마친 파일 {len(file_nodes)}개",
         default_table=primary, catalog=remove_machine_paths(catalog), graph=remove_machine_paths(graph),
         snapshot_sha256=digest.hexdigest())

    with closing(sqlite3.connect((data / "data.sqlite").as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN")
        names = [row[0] for row in db.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        references = defaultdict(list)
        if "source_references" in names:
            for record in db.execute("SELECT * FROM source_references"):
                row = dict(record)
                entry = source_entry(row, file_nodes)
                document = row.get("document_id")
                if entry and document is not None:
                    references[(document, row.get("line_id"))].append(entry)
        for name in names:
            table = identifier(name)
            info = table_info(catalog, name)
            total = db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            columns = [{"name": col[1], **column_info(catalog, name, col[1])}
                       for col in db.execute(f"PRAGMA table_info({table})")]
            guide = {k: info.get(k, "") for k in ("why", "row_meaning", "interpretation", "caution")}
            emit("table", dataset=key, name=name, metadata=remove_machine_paths({
                "name": name, "title": info.get("title", name), "group": info.get("group", "내역"),
                "count": total, "columns": columns, "guide": guide,
            }))
            for number, item in enumerate(db.execute(f"SELECT * FROM {table}"), 1):
                row = dict(item)
                binding = row_binding(key, row, file_nodes, references)
                values = {col: stored_value(val) for col, val in row.items()}
                emit("row", dataset=key, table_name=name, row_key=str(number), payload=values, binding=binding,
                     file_ids=binding["node_ids"], search_text="\n".join(str(v) for v in values.values() if v is not None))
    emit("complete")


if __name__ == "__main__":
    snapshot_folder(Path(sys.argv[1]))
