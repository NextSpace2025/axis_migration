"""Exercise the local viewer with a disposable synthetic database."""
import importlib.util
import sqlite3
import tempfile
import threading
import socket
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# Package-relative locations keep tests independent of workstation paths.
ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('viewer', ROOT / 'scripts/view_db.py')
VIEWER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VIEWER)


class ViewerTests(unittest.TestCase):
    """Verify output escaping, export, pagination, and access boundaries."""

    def test_local_viewer(self):
        """Read a sample database without altering its bytes."""
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / 'sample.sqlite'
            with sqlite3.connect(database) as db:
                db.execute('CREATE TABLE sample (value TEXT)')
                db.executemany('INSERT INTO sample VALUES (?)', [('<script>x</script>',), (None,), ('',)])
            original = database.read_bytes()
            server = ThreadingHTTPServer(('127.0.0.1', 0), VIEWER.make_handler(database, 1))
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            idle = socket.create_connection(server.server_address, timeout=3)
            base = f'http://127.0.0.1:{server.server_port}'
            try:
                with urlopen(base, timeout=3) as response:
                    page = response.read().decode()
                self.assertIn('&lt;script&gt;', page)
                self.assertIn('Next', page)
                with urlopen(base + '/csv') as response:
                    self.assertIn('\\N', response.read().decode())
                with urlopen(base + '/sql') as response:
                    exported = response.read().decode()
                with sqlite3.connect(':memory:') as restored:
                    restored.executescript(exported)
                    self.assertEqual(restored.execute('SELECT COUNT(*) FROM sample').fetchone()[0], 3)
                for path in ('/?table=missing', '/?page=-1'):
                    with self.assertRaises(HTTPError) as failure:
                        urlopen(base + path)
                    self.assertEqual(failure.exception.code, 400)
                with self.assertRaises(HTTPError) as failure:
                    urlopen(Request(base, headers={'Host': 'untrusted.example'}))
                self.assertEqual(failure.exception.code, 403)
                self.assertEqual(database.read_bytes(), original)
            finally:
                idle.close()
                server.shutdown()
                worker.join()
                server.server_close()


if __name__ == '__main__':
    unittest.main()

# 동작 설명: 임시 가상 DB로 조회·다운로드·오류 처리를 검사하고 원본 보존을 확인합니다.
