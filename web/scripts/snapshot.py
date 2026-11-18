"""Export a private viewer's read-only SQLite results as an import stream."""

import argparse
from contextlib import closing
import importlib.util
import json
from pathlib import Path, PureWindowsPath
import sys


def emit(kind, **data):
    print(json.dumps({"kind": kind, **data}, ensure_ascii=False, allow_nan=False))


def remove_machine_paths(value):
    """Use the filename when a path field points to a local machine."""
    if isinstance(value, dict):
        return {key: remove_machine_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [remove_machine_paths(item) for item in value]
    if isinstance(value, str) and PureWindowsPath(value).is_absolute():
        return PureWindowsPath(value).name
    return value


def snapshot(viewer, selected):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("axis_local_viewer", viewer)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    missing = set(selected) - module.DATASETS.keys()
    if missing:
        raise ValueError("Unknown dataset: " + ", ".join(sorted(missing)))
    for key in selected:
        dataset = module.DATASETS[key]
        table = "line_quantities" if key == "september" and "line_quantities" in dataset.tables else dataset.config["default_table"]
        if table not in dataset.tables:
            raise ValueError("Invalid landing table: " + table)
        emit("dataset", id=key, label=dataset.config["label"], description=dataset.config["description"],
             default_table=table, catalog=remove_machine_paths(dataset.catalog), graph=remove_machine_paths(dataset.graph))
        with closing(module.db_open(dataset.path)) as db:
            db.execute("BEGIN")
            if db.execute("PRAGMA quick_check").fetchall()[0][0] != "ok":
                raise ValueError("SQLite verification failed for " + key)
            for name, metadata in dataset.tables.items():
                emit("table", dataset=key, name=name, metadata=metadata)
                for item in db.execute("select rowid as _axis_rowid_, * from " + module.ident(name) + " order by rowid"):
                    row = dict(item)
                    row_key = str(row.pop("_axis_rowid_"))
                    binding = remove_machine_paths(dataset.binding(db, name, row))
                    values = remove_machine_paths({column: module.jsonable(value) for column, value in row.items()})
                    emit("row", dataset=key, table_name=name, row_key=row_key, payload=values, binding=binding,
                         file_ids=sorted({node for node in binding["node_ids"] if node in dataset.files}),
                         search_text="\n".join(str(value) for value in values.values() if value is not None))
    emit("complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("viewer", type=Path)
    parser.add_argument("datasets", nargs="+")
    args = parser.parse_args()
    snapshot(args.viewer.resolve(strict=True), list(dict.fromkeys(args.datasets)))
