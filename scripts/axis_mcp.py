"""Local MCP entry point for the Axis folder migration workflow."""

from base64 import b64encode
from http.client import HTTPConnection, HTTPSConnection
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Lock
from typing import Any, Literal
from urllib.parse import urlencode, urlsplit

from run_folder import (HOSTED_RESULT, RESULT_STAGE, REVIEW_STAGE, new_run, read_object, read_status,
                        resume_context, save_object)


RUNNER = Path(__file__).with_name("run_folder.py")
jobs = {}
job_lock = Lock()


def absolute_path(value):
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("폴더의 절대 경로를 지정하세요.")
    return path.resolve(strict=True)


def run_path(run_dir):
    return resume_context(absolute_path(run_dir))[0]


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
                 local: Literal["ollama", "lmstudio"] | None = None,
                 publish: bool | None = None) -> dict[str, Any]:
    """Analyze a folder, then publish verified results if web settings exist. Set publish=false for local only."""
    if publish is None:
        publish = (RUNNER.parent.parent / "web" / ".env").is_file()
    return launch(new_run(absolute_path(input_dir), publish=publish), company=company, local=local)


def resume_folder(run_dir: str, company: str | None = None, answer: str | None = None) -> dict[str, Any]:
    """Resume a stopped local run with an optional answer, or reopen finished results."""
    run = run_path(run_dir)
    return launch(run, company=company, answer=answer)


def folder_status(run_dir: str) -> dict[str, Any]:
    """Read a local run's persisted status and return its active review or results URL."""
    run = run_path(run_dir)
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
    if data["status"] and data["status"]["state"] == "completed" and (run / HOSTED_RESULT).is_file():
        published = read_object(run / HOSTED_RESULT)
        data["local_viewer_url"] = data["viewer_url"]
        data["viewer_url"] = published["viewer_url"]
        data["lookup_code"] = published["code"]
    return data


def close_folder(run_dir: str) -> dict[str, Any]:
    """Close this MCP session's open browser review or result. Keep the saved run for resuming."""
    run = run_path(run_dir)
    with job_lock:
        job = jobs.get(run)
        if not job or job.poll() is not None or not (run / "active-view.json").exists():
            raise ValueError("이 MCP 연결에서 열어 둔 검토 또는 결과 화면이 없습니다.")
        status = read_status(run)
        if status["stage"] not in (REVIEW_STAGE, RESULT_STAGE) or status["state"] == "running":
            raise ValueError("검토 대기나 결과 표시 중에 화면을 닫을 수 있습니다.")
        save_object(run / "close-view.json", {"pid": job.pid})
    return {"requested": True, "run_dir": str(run)}


def run_analysis_test() -> dict[str, Any]:
    """Generate and store six synthetic numbers. Return a six-digit code and the matching page URL."""
    from dotenv import dotenv_values

    config = dotenv_values(RUNNER.parent.parent / "web" / ".env")
    url = os.environ.get("AXIS_VIEWER_URL") or config.get("AXIS_VIEWER_URL") or ""
    password = os.environ.get("AXIS_VIEWER_PASSWORD") or config.get("AXIS_VIEWER_PASSWORD") or ""
    target = urlsplit(url)
    if (not target.hostname or target.username or target.password or target.path not in ("", "/")
            or target.query or target.fragment or not (
                target.scheme == "https" or
                (target.scheme == "http" and target.hostname in ("localhost", "127.0.0.1", "::1"))
            )):
        raise ValueError("웹 뷰어의 기본 주소를 AXIS_VIEWER_URL에 설정하세요.")
    if len(password) < 16:
        raise ValueError("웹 뷰어와 동일한 AXIS_VIEWER_PASSWORD를 설정하세요.")
    connection_type = HTTPSConnection if target.scheme == "https" else HTTPConnection
    connection = connection_type(target.hostname, target.port, timeout=20)
    credentials = b64encode(("axis:" + password).encode("utf-8")).decode("ascii")
    try:
        connection.request("POST", "/api/analysis-test", body="{}", headers={
            "Authorization": "Basic " + credentials,
            "Content-Type": "application/json",
        })
        response = connection.getresponse()
        if response.status != 201:
            raise ValueError(f"테스트 결과 저장에 실패했습니다. 웹 뷰어 응답 코드 {response.status}.")
        data = json.loads(response.read(4096))
    except OSError as error:
        raise ValueError("웹 뷰어에 연결할 수 없습니다. 서버 주소와 실행 상태를 확인하세요.") from error
    finally:
        connection.close()

    code, numbers = data["code"], data["numbers"]
    if (not isinstance(code, str) or len(code) != 6 or not code.isascii() or not code.isdecimal()
            or not isinstance(numbers, list) or len(numbers) != 6
            or any(type(number) is not int or not 1 <= number <= 100 for number in numbers)):
        raise ValueError("웹 뷰어에서 유효한 테스트 결과를 받지 못했습니다.")
    return {"code": code, "numbers": numbers,
            "viewer_url": url.rstrip("/") + "/analysis-test?" + urlencode({"code": code})}


def main():
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as error:
        raise SystemExit('MCP SDK가 필요합니다. python -m pip install "mcp>=1.28,<2"') from error
    server = FastMCP("Axis Migration", instructions=(
        "Use start_folder for a requested local folder migration with the user's explicit absolute "
        "input path and reference company when known. The runner loads the bundled design skill. "
        "Use folder_status with the returned run_dir to follow progress and share the active review URL. "
        "The user confirms the structure in the browser before the runner loads the migration skill "
        "and converts to SQLite. Configured MCP runs upload approved results after verification; "
        "use folder_status to return the lookup_code and hosted viewer_url. Use publish=false for local-only runs. "
        "Use resume_folder to continue a stopped run or reopen results. Supply company or answer "
        "when the saved status requests it. Use close_folder to close an open review or result. "
        "Use run_analysis_test for synthetic web connectivity tests. Return its code and viewer URL."
    ))
    for tool in (start_folder, resume_folder, folder_status, close_folder, run_analysis_test):
        server.tool()(tool)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
