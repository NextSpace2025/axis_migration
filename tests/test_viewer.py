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
                db.execute('CREATE TABLE "other & table" (value TEXT)')
                db.executemany('INSERT INTO sample VALUES (?)', [('<script>x</script>',), (None,), ('',)])
            db.close()
            original = database.read_bytes()
            server = ThreadingHTTPServer(('127.0.0.1', 0), VIEWER.make_handler(database, 1))
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            idle = socket.create_connection(server.server_address, timeout=3)
            base = f'http://127.0.0.1:{server.server_port}'
            try:
                with urlopen(base + '/?table=sample', timeout=3) as response:
                    page = response.read().decode()
                self.assertIn('&lt;script&gt;', page)
                self.assertIn('Next', page)
                self.assertIn('aria-label="테이블 목록"', page)
                self.assertIn('other &amp; table</a>', page)
                with urlopen(base + '/?table=other%20%26%20table') as response:
                    other_page = response.read().decode()
                self.assertIn('class="table-link active" href="/?table=other%20%26%20table"', other_page)
                self.assertIn('<h2>other &amp; table</h2>', other_page)
                with urlopen(base + '/csv?table=sample') as response:
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

    def test_explained_dashboard_and_search(self):
        """Keep catalog text escaped, search useful, and the database immutable."""
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / 'sample.sqlite'
            with sqlite3.connect(database) as db:
                db.execute('CREATE TABLE invoices (amount TEXT)')
                db.execute('CREATE TABLE empty_table (value TEXT)')
                db.executemany('INSERT INTO invoices VALUES (?)', [('12500',), ('-100',)])
            db.close()
            original = database.read_bytes()
            catalog = {'title': '자료 설명', 'group_order': ['업무 자료'],
                       'overview': [{'table': 'invoices', 'label': '건 증빙'},
                                    {'table': 'missing', 'label': '없는 자료'}],
                       'tables': {'invoices': {'title': '계산서', 'group': '업무 자료',
                           'why': '금액 <script>bad</script> 분리',
                           'row_meaning': '문서 하나', 'interpretation': '계산서 구성 확인',
                           'caution': '지급 확정 아님', 'evidence': '실제 원문 위치',
                           'columns': {'amount': {'label': '금액', 'description': '문서의 <금액> 원문 값',
                               'unit': '문서 통화 (미확정)', 'unit_status': 'unconfirmed',
                               'notes': '통화를 임의로 가정하지 않음', 'unit_basis': '원문 표기 기준'}},
                           'related': ['empty_table', 'missing']}}}
            server = ThreadingHTTPServer(('127.0.0.1', 0), VIEWER.make_handler(database, 10, catalog))
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            base = f'http://127.0.0.1:{server.server_port}'
            try:
                def read(path):
                    with urlopen(base + path, timeout=3) as response:
                        self.assertIn("default-src 'none'", response.headers['Content-Security-Policy'])
                        return response.read().decode()
                dashboard = read('/')
                self.assertIn('<strong>2</strong>건 증빙', dashboard)
                self.assertIn('&lt;script&gt;bad&lt;/script&gt;', dashboard)
                self.assertNotIn('<script>', dashboard)
                self.assertIn('empty_table', dashboard)
                self.assertNotIn('/?table=missing', dashboard)
                self.assertIn('한 행의 의미', dashboard)
                page = read('/?table=invoices')
                self.assertIn('<h2>계산서</h2>', page)
                self.assertIn('가능한 해석', page)
                self.assertIn('지급 확정 아님', page)
                self.assertIn('12500', page)
                self.assertIn('<span class="column-label">금액</span>', page)
                self.assertIn('문서의 &lt;금액&gt; 원문 값', page)
                self.assertIn('단위: 문서 통화 (미확정)', page)
                self.assertIn('unit-unknown', page)
                self.assertIn('&columns=open#column-0', page)
                opened = read('/?table=invoices&columns=open')
                self.assertIn('id="column-guide" open', opened)
                self.assertIn('단위 근거', opened)
                with urlopen(base + '/csv?table=invoices') as response:
                    self.assertEqual(response.read().decode('utf-8-sig').splitlines()[0], 'amount')
                filtered = read('/?view=dashboard&q=invoices')
                self.assertEqual(filtered.count('class="catalog-row"'), 1)
                empty = read('/?view=dashboard&q=nonexistent')
                self.assertIn('검색 조건에 맞는 테이블이 없습니다', empty)
                self.assertEqual(empty.count('class="catalog-row"'), 0)
                escaped = read('/?view=dashboard&q=%22%3E%3Cscript%3E')
                self.assertNotIn('value=""><script>', escaped)
                self.assertIn('현재 저장된 행이 없습니다', read('/?table=empty_table'))
                self.assertEqual(database.read_bytes(), original)
            finally:
                server.shutdown()
                worker.join()
                server.server_close()


if __name__ == '__main__':
    unittest.main()

# 동작 설명: 임시 가상 DB로 조회·다운로드·오류 처리를 검사하고 원본 보존을 확인합니다.
