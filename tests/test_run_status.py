"""Private status persistence and truthful CLI delivery."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/run_status.py'
SPEC = importlib.util.spec_from_file_location('run_status', SCRIPT)
STATUS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STATUS)


class RunStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name).resolve()
        (self.run / 'report.md').write_text('Synthetic review', encoding='utf-8')
        (self.run / 'data.sqlite').write_bytes(b'keep-existing-db')

    def write(self, **changes):
        args = dict(state='running', stage='모델 검토', summary='자료 검토', checks='not_run')
        args.update(changes)
        return STATUS.write_status(self.run, **args)

    def cli(self, *args):
        return subprocess.run([sys.executable, '-X', 'utf8', str(SCRIPT), *args],
                              cwd=self.run, capture_output=True, text=True, encoding='utf-8')

    def test_history_roundtrip_preserves_findings_and_database(self):
        self.write()
        self.write(state='waiting', checks='passed', results=['report.md'],
                   pending=['헤더 확인'], next_action='헤더를 확인하세요.')
        completed = self.write(state='completed', checks='passed', results=['report.md'],
                               issues=['미확정 값은 보존했습니다.'])
        self.assertEqual(STATUS.read_status(self.run), completed)
        events = [json.loads(s) for s in (self.run / 'run.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual([e['result']['state'] for e in events], ['running', 'waiting', 'completed'])
        self.assertEqual(completed['results'], [str(self.run / 'report.md')])
        self.assertEqual((self.run / 'data.sqlite').read_bytes(), b'keep-existing-db')

    def test_incomplete_work_cannot_replace_running_with_complete(self):
        self.write()
        for changes in (dict(checks='not_run'), dict(checks='failed'), dict(pending=['결정']),
                        dict(error='실행 실패'), dict(results=[]), dict(results=['missing.md'])):
            args = dict(state='completed', checks='passed', results=['report.md'])
            args.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.write(**args)
        self.assertEqual(STATUS.read_status(self.run)['state'], 'running')

    def test_blocking_states_require_cause_and_next_step(self):
        for changes in (dict(state='waiting'), dict(state='waiting', pending=['자료 필요']),
                        dict(state='error'), dict(state='error', error='실패'), dict(checks='failed')):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.write(**changes)
        self.assertFalse((self.run / 'status.json').exists())

    def test_missing_artifact_does_not_show_as_complete(self):
        self.write(state='completed', checks='not_required', results=['report.md'])
        (self.run / 'report.md').unlink()
        with self.assertRaises(ValueError):
            STATUS.read_status(self.run)

    def test_explicit_external_folder_and_external_results_required(self):
        for path in (Path('.'), SCRIPT.parent, self.run / 'missing'):
            with self.subTest(path=path), self.assertRaises((ValueError, OSError)):
                STATUS.write_status(path, state='running', stage='test', summary='test', checks='not_run')
        with self.assertRaises(ValueError):
            self.write(state='completed', checks='passed', results=[str(SCRIPT)])

    def test_failed_replace_keeps_previous_status_and_cleans_temporary_file(self):
        before = self.write()
        with patch.object(STATUS.os, 'replace', side_effect=OSError('disk unavailable')):
            with self.assertRaises(OSError):
                self.write(state='completed', checks='passed', results=['report.md'])
        self.assertEqual(STATUS.read_status(self.run), before)
        self.assertFalse(list(self.run.glob('.status-*')))

    def test_cli_saved_states_and_resume_from_another_cwd(self):
        for state, label, extra in (
                ('completed', '완료', ['--result', 'report.md']),
                ('waiting', '확인 대기', ['--pending', '헤더 확인', '--next', '헤더를 확인하세요.']),
                ('error', '오류', ['--error', '파일 읽기 실패', '--next', '접근 권한을 확인하세요.'])):
            command = self.cli('write', '--run', str(self.run), '--state', state,
                               '--stage', '검토', '--summary', '실제 상태',
                               '--checks', 'failed' if state == 'error' else 'passed', *extra)
            self.assertEqual(command.returncode, 0, command.stderr)
            shown = self.cli('show', '--run', str(self.run))
            self.assertEqual(shown.returncode, 0, shown.stderr)
            self.assertIn('Axis · ' + label + ' · 검토', shown.stdout)
            self.assertEqual(json.loads(self.cli('show', '--run', str(self.run), '--json').stdout)['state'], state)
        self.write()
        self.assertEqual(STATUS.read_status(self.run)['state'], 'running')

    def test_corrupt_or_absent_state_is_not_silent_success(self):
        for text in (None, 'not json', '[]', '{"schema_version": 99}'):
            if text is not None:
                (self.run / 'status.json').write_text(text, encoding='utf-8')
            result = self.cli('show', '--run', str(self.run))
            self.assertEqual(result.returncode, 1)
            self.assertIn('상태 기록 오류', result.stderr)
            self.assertNotIn('Axis · 완료', result.stdout)


if __name__ == '__main__':
    unittest.main()
