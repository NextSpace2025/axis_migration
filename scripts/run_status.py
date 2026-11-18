#!/usr/bin/env python3
"""Persist and display a private run's actual progress and handoff state."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile


PACKAGE = Path(__file__).resolve().parents[1]
LABELS = {"running": "진행 중", "completed": "완료", "waiting": "확인 대기", "error": "오류"}
CHECKS = ("passed", "not_required", "not_run", "failed")


def run_path(value):
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("결과 폴더는 절대 경로로 지정하세요.")
    path = path.resolve(strict=True)
    if not path.is_dir() or path.is_relative_to(PACKAGE):
        raise ValueError("공개 패키지 밖의 기존 결과 폴더를 지정하세요.")
    for name in ("status.json", "run.jsonl"):
        if (path / name).is_symlink():
            raise ValueError("상태 파일과 실행 기록은 심볼릭 링크일 수 없습니다.")
    return path


def validate(record):
    if not isinstance(record, dict):
        raise ValueError("상태 기록은 JSON 객체여야 합니다.")
    if record.get("schema_version") != 1 or record.get("state") not in LABELS:
        raise ValueError("지원하지 않는 상태 기록입니다.")
    if record.get("checks") not in CHECKS:
        raise ValueError("실제로 수행한 검증 상태를 지정하세요.")
    if not all(isinstance(record.get(k), str) and record[k].strip()
               for k in ("stage", "summary", "run_dir", "updated_at")):
        raise ValueError("단계와 작업 요약이 필요합니다.")
    for key in ("results", "pending", "issues"):
        if not isinstance(record.get(key), list) or any(
                not isinstance(v, str) or not v.strip() for v in record[key]):
            raise ValueError("결과·대기·검토사항은 비어 있지 않은 문자열 목록이어야 합니다.")
    state = record["state"]
    if state == "completed" and (record["pending"] or record.get("error") or
                                  record["checks"] not in ("passed", "not_required")):
        raise ValueError("미수행·실패한 필수 검증이나 대기 항목이 있으면 완료로 기록할 수 없습니다.")
    if state == "completed" and not record["results"]:
        raise ValueError("완료 상태에는 실제 결과 파일이 필요합니다.")
    if state == "waiting" and not record["pending"]:
        raise ValueError("확인 대기에는 확인받을 내용이 필요합니다.")
    if state == "error" and not (
            isinstance(record.get("error"), str) and record["error"].strip()):
        raise ValueError("오류 상태에는 원인이 필요합니다.")
    if state in ("waiting", "error") and not (
            isinstance(record.get("next_action"), str) and record["next_action"].strip()):
        raise ValueError("확인 대기·오류에는 구체적인 다음 조치가 필요합니다.")
    if record["checks"] == "failed" and state != "error":
        raise ValueError("작업을 막는 필수 검증 실패는 오류로 기록하세요.")
    if record.get("error") and state != "error":
        raise ValueError("실행 오류가 남아 있으면 오류 상태로 기록하세요.")
    if record.get("next_action") is not None and not isinstance(record["next_action"], str):
        raise ValueError("다음 조치는 문자열이어야 합니다.")


def read_status(run):
    run = run_path(run)
    record = json.loads((run / "status.json").read_text(encoding="utf-8"))
    validate(record)
    if record["run_dir"] != str(run):
        raise ValueError("상태 기록의 결과 폴더와 요청한 폴더가 다릅니다.")
    # Recheck delivery paths: a previously completed run can have missing artifacts.
    for result in record["results"]:
        if not Path(result).is_file():
            raise ValueError("기록된 결과 파일을 찾을 수 없습니다: " + result)
    return record


def write_status(run, *, state, stage, summary, checks, results=(), pending=(),
                 issues=(), error=None, next_action=None):
    run = run_path(run)
    paths = []
    for value in results:
        path = Path(value)
        path = (run / path).resolve() if not path.is_absolute() else path.resolve()
        if not path.is_file() or path.is_relative_to(PACKAGE):
            raise ValueError("공개 패키지 밖의 실제 결과 파일을 지정하세요: " + str(path))
        paths.append(str(path))
    record = dict(schema_version=1, updated_at=datetime.now(timezone.utc).isoformat(),
                  run_dir=str(run), state=state, stage=stage, summary=summary,
                  checks=checks, results=paths, pending=list(pending), issues=list(issues),
                  error=error, next_action=next_action)
    validate(record)
    # shortcut: one writer per run; concurrent jobs must use separate run folders.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=run,
                                         prefix=".status-", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(record, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        event = {"timestamp": record["updated_at"], "action": "run_status",
                 "input": {}, "result": record, "error": error}
        with (run / "run.jsonl").open("a", encoding="utf-8") as log:
            log.write(json.dumps(event, ensure_ascii=False) + "\n")
        os.replace(temporary, run / "status.json")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    saved = read_status(run)
    if saved != record:
        raise ValueError("저장한 상태가 기록 내용과 일치하지 않습니다.")
    return saved


def render(record):
    lines = [f"Axis · {LABELS[record['state']]} · {record['stage']}", record["summary"]]
    if record["state"] == "running":
        lines.append("종료가 확인되지 않았습니다. 중단 후에는 실제 진행 상태를 확인하세요.")
    for title, key in (("결과", "results"), ("확인 대기", "pending"), ("검토사항", "issues")):
        lines.extend(f"{title}: {value}" for value in record[key])
    if record.get("error"):
        lines.append("원인: " + record["error"])
    if record.get("next_action"):
        lines.append("다음 조치: " + record["next_action"])
    lines.append("상태 기록: " + str(Path(record["run_dir"]) / "status.json"))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("write", "show"):
        command = sub.add_parser(name)
        command.add_argument("--run", required=True, type=Path)
        command.add_argument("--json", action="store_true")
        if name == "write":
            command.add_argument("--state", required=True, choices=LABELS)
            command.add_argument("--stage", required=True)
            command.add_argument("--summary", required=True)
            command.add_argument("--checks", required=True, choices=CHECKS)
            command.add_argument("--result", action="append", default=[])
            command.add_argument("--pending", action="append", default=[])
            command.add_argument("--issue", action="append", default=[])
            command.add_argument("--error")
            command.add_argument("--next", dest="next_action")
    args = parser.parse_args(argv)
    try:
        if args.action == "show":
            record = read_status(args.run)
        else:
            record = write_status(args.run, state=args.state, stage=args.stage,
                                  summary=args.summary, checks=args.checks,
                                  results=args.result, pending=args.pending,
                                  issues=args.issue, error=args.error,
                                  next_action=args.next_action)
        print(json.dumps(record, ensure_ascii=False) if args.json else render(record))
    except (OSError, ValueError, TypeError) as error:
        parser.exit(1, "Axis · 상태 기록 오류: " + str(error) + "\n저장 위치와 기록 내용을 확인하세요.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
