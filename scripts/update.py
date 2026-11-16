"""Explicit GitHub stable-tag updates with local backup and rollback."""
import argparse
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Only explicit stable release tags participate in version selection.
TAG = re.compile(r'v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')
REQUIRED = ('VERSION', 'AGENTS.md', 'scripts/update.py',
            'construction-schema-design/SKILL.md',
            'construction-data-migration/SKILL.md', 'output/agents.md')


def git(*arguments):
    """Run git without a shell and report failures without continuing."""
    return subprocess.run(['git', *arguments], check=True, capture_output=True,
                          text=True, timeout=120).stdout.strip()


def repository(value):
    """Accept only an explicit GitHub owner/repository identifier."""
    if not value or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', value):
        raise ValueError('Set repository to a GitHub owner/repository in update-config.json or use --repo.')
    return 'https://github.com/' + value + '.git'


def release_tags(url):
    """Return stable semantic version tags sorted numerically."""
    tags = [line.split('refs/tags/', 1)[1] for line in
            git('ls-remote', '--tags', '--refs', url).splitlines() if 'refs/tags/' in line]
    return sorted((tag for tag in tags if TAG.fullmatch(tag)),
                  key=lambda tag: tuple(map(int, TAG.fullmatch(tag).groups())))


def validate(folder, tag=None):
    """Verify a package before any installed files are moved."""
    for path in folder.rglob('*'):
        if path.is_symlink():
            raise ValueError('Release contains a symbolic link; installation stopped.')
    if not all((folder / name).is_file() for name in REQUIRED):
        raise ValueError('Release must contain Axis Migration at repository root.')
    version = (folder / 'VERSION').read_text().strip()
    if not TAG.fullmatch('v' + version) or (tag and tag != 'v' + version):
        raise ValueError('VERSION does not match the stable release tag.')
    return version


def preserve(current, staged):
    """Carry local data forward without replacing the release instruction file."""
    for name in ('config', 'output'):
        source = current / name
        if source.exists():
            for path in source.rglob('*'):
                if path.is_symlink():
                    raise ValueError('Local data contains a symlink; move it outside the package first.')
            shutil.copytree(source, staged / name, dirs_exist_ok=True,
                            ignore=lambda directory, names: ['agents.md']
                            if Path(directory) == source and name == 'output' else [])
    config = current / 'update-config.json'
    if config.exists():
        shutil.copy2(config, staged / config.name)


def install(current, staged):
    """Swap a validated tree; restore the previous tree if the swap fails."""
    preserve(current, staged)
    backup = current.parent / (current.name + '.backup-' +
                              datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    current.rename(backup)
    try:
        staged.rename(current)
    except BaseException:
        backup.rename(current)
        raise
    return backup


def main():
    """Check, update, or roll back only after an explicit command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'update', 'rollback'))
    parser.add_argument('--repo', help='GitHub owner/repository')
    parser.add_argument('--version', help='Stable tag such as v0.1.1; default: latest stable tag')
    parser.add_argument('--backup', type=Path, help='Backup directory for rollback')
    args = parser.parse_args()
    current = Path(__file__).resolve().parents[1]
    try:
        installed = validate(current)
        if args.action == 'rollback':
            if not args.backup:
                raise ValueError('Provide --backup with the saved installation directory.')
            source = args.backup.resolve()
            if source.parent != current.parent or not source.name.startswith(current.name + '.backup-'):
                raise ValueError('Choose a sibling backup created by this updater.')
            validate(source)
            with tempfile.TemporaryDirectory(dir=current.parent, prefix='.axis-stage-') as temporary:
                staged = Path(temporary) / 'package'
                shutil.copytree(source, staged)
                backup = install(current, staged)
        else:
            config = json.loads((current / 'update-config.json').read_text())
            url = repository(args.repo or config.get('repository'))
            tags = release_tags(url)
            tag = args.version or (tags[-1] if tags else None)
            if not tag or tag not in tags:
                raise ValueError('No matching stable version tag is published.')
            print(f'Installed: {installed}; selected: {tag}')
            if args.action == 'check' or tag == 'v' + installed:
                return
            if tuple(map(int, tag[1:].split('.'))) < tuple(map(int, installed.split('.'))):
                raise ValueError('Use rollback for a downgrade.')
            if (current / '.git').exists() and git('-C', str(current), 'status', '--porcelain'):
                raise ValueError('Installation has local changes. Commit or save them before updating.')
            with tempfile.TemporaryDirectory(dir=current.parent, prefix='.axis-stage-') as temporary:
                staged = Path(temporary) / 'package'
                git('clone', '--depth', '1', '--branch', tag, '--', url, str(staged))
                validate(staged, tag)
                shutil.rmtree(staged / '.git')
                backup = install(current, staged)
        print(f'Installed: {(current / "VERSION").read_text().strip()}')
        print(f'Backup: {backup}')
        print('Restart the agent session and the local viewer. Existing databases were not migrated.')
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f'Update stopped: {error}\nResolve the cause and retry; retained backups are not deleted.\n')


if __name__ == '__main__':
    main()

# 동작 설명: 안정 버전 태그를 확인하고 설치본을 백업한 뒤 교체합니다.
# 회사 설정과 결과 데이터는 유지하며, 오류 시 기존 설치본을 복구합니다.
