"""Optional local MCP entry point for the same Axis folder workflow."""

import os
from pathlib import Path
import subprocess
import sys
from threading import Lock
from typing import Any, Literal

from run_folder import new_run, read_object, read_status, resume_context, save_object


RUNNER = Path(__file__).with_name("run_folder.py")
jobs = {}
job_lock = Lock()


def absolute_path(value):
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("폴더의 절대 경로를 지정하세요.")
    return path.resolve(strict=True)


def launch(run, company=None, answer=None, local=None):
    command = [sys.executable, "-u", str(RUNNER), "--resume", str(run), "--no-browser"]
    for option, value in (("--company", company), ("--answer", answer), ("--local", local)):
        if value:
            command.append(f"{option}={value}")
    log = run / "runner.log"
    with job_lock:
        if run in jobs and jobs[run].poll() is None:
            raise ValueError("이 작업이 이미 열려 있습니다. 작업 상태에서 주소를 확인하세요.")
        if log.resolve() != log or log.is_symlink():
            raise ValueError("실행 로그의 저장 위치를 확인하세요.")
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {
            "start_new_session": True}
        with log.open("ab") as stream:
            jobs[run] = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream,
                                         stderr=subprocess.STDOUT, **options)
    return {"run_dir": str(run), "log": str(log)}


def start_folder(input_dir: str, company: str | None = None,
                 local: Literal["ollama", "lmstudio"] | None = None) -> dict[str, Any]:
    """Start a local run on the user's explicitly selected folder. Poll folder_status for the review URL."""
    return launch(new_run(absolute_path(input_dir)), company=company, local=local)


def resume_folder(run_dir: str, company: str | None = None, answer: str | None = None) -> dict[str, Any]:
    """Resume a stopped local run with an optional answer, or reopen finished results."""
    run, _ = resume_context(absolute_path(run_dir))
    return launch(run, company=company, answer=answer)


def folder_status(run_dir: str) -> dict[str, Any]:
    """Read a local run's persisted status and return its active review or results URL."""
    run, _ = resume_context(absolute_path(run_dir))
    with job_lock:
        job = jobs.get(run)
        exit_code = job.poll() if job else None
    data = {"run_dir": str(run), "worker_active": bool(job and exit_code is None),
            "exit_code": exit_code, "status": None, "viewer_url": None}
    if (run / "status.json").exists():
        data["status"] = read_status(run)
    link = run / "active-view.json"
    if data["worker_active"] and link.is_file():
        try:
            view = read_object(link)
        except (FileNotFoundError, ValueError):
            if not link.exists():
                return data
            raise
        if view["pid"] == job.pid:
            data["viewer_url"] = view["url"]
    return data


def close_folder(run_dir: str) -> dict[str, Any]:
    """Close this MCP session's open browser review or result. Keep the saved run for resuming."""
    run, _ = resume_context(absolute_path(run_dir))
    with job_lock:
        job = jobs.get(run)
        if not job or job.poll() is not None or not (run / "active-view.json").exists():
            raise ValueError("이 MCP 연결에서 열어 둔 검토 또는 결과 화면이 없습니다.")
        status = read_status(run)
        if status["stage"] not in ("헤더와 적용값 검토", "결과 화면") or status["state"] == "running":
            raise ValueError("검토 대기나 결과 표시 중에 화면을 닫을 수 있습니다.")
        save_object(run / "close-view.json", {"pid": job.pid})
    return {"requested": True, "run_dir": str(run)}


def main():
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as error:
        raise SystemExit("MCP SDK가 필요합니다. python -m pip install mcp") from error
    server = FastMCP("Axis Migration")
    for tool in (start_folder, resume_folder, folder_status, close_folder):
        server.tool()(tool)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
