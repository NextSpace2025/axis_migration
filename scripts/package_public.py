#!/usr/bin/env python3
"""Build a public ZIP from the explicit release file manifest using only stdlib."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile

# Major variable: repository-owned configuration lists exact public paths.
MANIFEST_NAME = "public-files.json"


def public_payloads(root):
    """Method: validate release paths before reading any payload into the ZIP."""
    root = Path(root).resolve()
    manifest_path = root / MANIFEST_NAME
    if manifest_path.is_symlink():
        raise ValueError("The release manifest must be a regular local file.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    names = manifest.get("files") if isinstance(manifest, dict) else None
    if not isinstance(names, list) or not names:
        raise ValueError("The manifest must contain a non-empty files list.")
    payloads = {}
    for name in names:
        if not isinstance(name, str) or "\\" in name:
            raise ValueError("Manifest paths must be relative POSIX strings.")
        relative = PurePosixPath(name)
        if (relative.is_absolute() or not relative.parts or
                any(part in (".", "..") for part in relative.parts) or
                relative.as_posix() != name or name in payloads):
            raise ValueError("Manifest paths must be unique canonical relative paths.")
        if any(part.startswith(("_", ".")) for part in relative.parts):
            if name not in (".gitignore", ".gitattributes"):
                raise ValueError("Private or hidden paths cannot be released.")
        # Major variable: candidate is checked component-by-component against symlinks.
        candidate = root
        for component in relative.parts:
            candidate = candidate / component
            if candidate.is_symlink():
                raise ValueError("Release paths must not contain symlinks.")
        if not candidate.is_file() or not candidate.resolve().is_relative_to(root):
            raise ValueError("A listed public file is missing or outside the project.")
        if candidate.suffix.lower() in (".zip", ".db", ".sqlite", ".pyc"):
            raise ValueError("Archives, databases, and bytecode cannot be public inputs.")
        payload = candidate.read_bytes()
        payload.decode("utf-8-sig")
        payloads[name] = payload
    return payloads


def build_archive(root, output):
    """Method: write only validated payloads without overwriting an existing file."""
    payloads = public_payloads(root)
    output = Path(output)
    if output.suffix != ".zip":
        raise ValueError("Choose a .zip output file.")
    if output.resolve().is_relative_to(Path(root).resolve() / "_private"):
        raise ValueError("Choose a public output location outside _private.")
    output.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with output.open("xb") as destination:
            created = True
            with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
                for name, payload in sorted(payloads.items()):
                    archive.writestr(name, payload)
    except Exception:
        if created:
            output.unlink(missing_ok=True)
        raise
    return len(payloads)


def main():
    """Method: expose packaging as a CLI and emit a redacted structured run event."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path("dist/axis_migration.zip"))
    args = parser.parse_args()
    # Major variable: root is anchored to the script, independent of the caller's cwd.
    root = Path(__file__).resolve().parents[1]
    event = {"timestamp": datetime.now(timezone.utc).isoformat(),
             "action": "package_public", "input": {"manifest": MANIFEST_NAME},
             "result": None, "error": None}
    try:
        count = build_archive(root, args.output)
        event["result"] = {"archive": args.output.name, "files": count}
        status = 0
    except (OSError, ValueError) as error:
        # Avoid leaking filesystem paths or data from OS/decoder error messages.
        exists = isinstance(error, FileExistsError)
        event["error"] = {
            "type": type(error).__name__,
            "cause": "The output file already exists." if exists else
                     "Release inputs or the output destination could not be validated.",
            "resolution": "Choose a new output filename." if exists else
                          "Check the manifest, readable UTF-8 files, and a writable .zip destination."}
        status = 1
    print(json.dumps(event))
    return status


if __name__ == "__main__":
    raise SystemExit(main())

# 동작 설명: 공개 파일 목록을 검사해 ZIP을 만들고 결과를 기록합니다.
# 비공개 경로와 심볼릭 링크를 제외하며, 기존 출력 파일을 덮어쓰지 않습니다.
