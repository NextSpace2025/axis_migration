"""MCP run tracking must survive an MCP server restart while the runner keeps going."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import axis_mcp
import run_folder as workflow

HOLD_LOCK = """
import sqlite3, sys
lock = sqlite3.connect(sys.argv[1])
lock.execute("BEGIN IMMEDIATE")
print("locked", flush=True)
sys.stdin.read()
"""


class McpTrackingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        source = Path(self.directory.name) / "문서"
        source.mkdir()
        self.run = workflow.new_run(source)
        workflow.write_status(self.run, state="waiting", stage=workflow.REVIEW_STAGE,
                              summary="검토 대기", checks="not_run",
                              pending=["브라우저에서 데이터 구조 확정"],
                              next_action="검토 주소에서 구조를 확정하세요.")
        patcher = patch.dict(axis_mcp.jobs, clear=True)  # a freshly restarted MCP server
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.directory.cleanup()

    def hold_lock(self):
        runner = subprocess.Popen([sys.executable, "-c", HOLD_LOCK, str(self.run / workflow.LOCK)],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.addCleanup(runner.wait)
        self.addCleanup(runner.stdin.close)
        self.assertEqual(runner.stdout.readline().strip(), "locked")
        return runner

    def test_runner_started_by_an_earlier_server_is_still_found_and_closable(self):
        runner = self.hold_lock()
        workflow.save_object(self.run / workflow.ACTIVE_VIEW,
                             {"url": "http://127.0.0.1:9/review/", "pid": runner.pid})
        status = axis_mcp.folder_status(str(self.run))
        self.assertTrue(status["worker_active"])
        self.assertEqual(status["viewer_url"], "http://127.0.0.1:9/review/")
        with self.assertRaisesRegex(ValueError, "이미 열려"):
            axis_mcp.resume_folder(str(self.run))
        self.assertEqual(axis_mcp.close_folder(str(self.run))["requested"], True)
        self.assertEqual(workflow.read_object(self.run / workflow.CLOSE_VIEW), {"pid": runner.pid})

    def test_view_left_by_a_dead_runner_is_not_reported(self):
        runner = self.hold_lock()
        workflow.save_object(self.run / workflow.ACTIVE_VIEW,
                             {"url": "http://127.0.0.1:9/review/", "pid": runner.pid})
        runner.kill()
        runner.wait()
        status = axis_mcp.folder_status(str(self.run))
        self.assertFalse(status["worker_active"])
        self.assertIsNone(status["viewer_url"])
        with self.assertRaisesRegex(ValueError, "열려 있는"):
            axis_mcp.close_folder(str(self.run))

    def test_probe_neither_creates_the_lock_nor_blocks_the_runner(self):
        self.assertFalse(workflow.worker_running(self.run))
        self.assertFalse((self.run / workflow.LOCK).exists())
        (self.run / workflow.LOCK).touch()
        self.assertFalse(workflow.worker_running(self.run))
        runner = self.hold_lock()
        self.assertTrue(workflow.worker_running(self.run))
        self.assertIsNone(runner.poll())


if __name__ == "__main__":
    unittest.main()
