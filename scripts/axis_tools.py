"""Read-only check tools for the stage agent, bound to one run directory.

run_folder.py passes this stdio server to `codex exec`. It never starts or
controls runs; run_folder.py still makes the final verification.
"""

import argparse
from pathlib import Path
import sqlite3

from run_folder import resume_context, verify


def verify_db(run):
    try:
        primary, catalog = verify(run, export=False)
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as error:
        return {"ok": False, "problem": f"{type(error).__name__}: {error}"}
    return {"ok": True, "primary_table": primary, "tables": sorted(catalog["tables"])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    run, _ = resume_context(parser.parse_args(argv).run)
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as error:
        raise SystemExit("MCP SDK가 필요합니다. python -m pip install mcp") from error
    server = FastMCP("Axis Tools")

    @server.tool(name="verify_db")
    def verify_this_run() -> dict:
        """Check this run's data.sqlite, viewer.json and approved schema the same way the
        final step will. Call before returning ready; fix every reported problem."""
        return verify_db(run)

    server.run(transport="stdio")


if __name__ == "__main__":
    main()
