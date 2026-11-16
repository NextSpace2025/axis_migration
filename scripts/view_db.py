"""Read-only, loopback-only SQLite table viewer using the standard library."""

import argparse
import csv
import html
import io
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit


def identifier(value):
    """Quote an already discovered SQLite identifier."""
    return '"' + value.replace('"', '""') + '"'


def csv_value(value):
    """Preserve null, empty strings, and literal backslashes distinctly."""
    return '\\N' if value is None else str(value).replace('\\', '\\\\')


def make_handler(database, page_size):
    """Bind one trusted database path and pagination configuration."""
    class Viewer(BaseHTTPRequestHandler):
        """Serve escaped tables and exports without accepting mutations."""

        def do_GET(self):
            """Handle a read request; restrict browser cross-origin access."""
            allowed = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != allowed:
                self.send_error(403, 'Open the printed loopback URL.')
                return
            if self.headers.get('Sec-Fetch-Site') == 'cross-site':
                self.send_error(403, 'Cross-site requests are disabled.')
                return
            try:
                with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
                    db.execute('PRAGMA query_only = ON')
                    self.render(db)
            except (ValueError, sqlite3.Error):
                self.send_error(400, 'Unable to read this request. Check the table, page, and database.')

        def render(self, db):
            """Render a table page or serialize the selected export."""
            request = urlsplit(self.path)
            if request.path not in ('/', '/csv', '/sql'):
                self.send_error(404)
                return
            tables = [row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )]
            params = parse_qs(request.query)
            table = params.get('table', [tables[0] if tables else ''])[0]
            if request.path == '/sql':
                self.reply('\n'.join(db.iterdump()), 'application/sql', 'export.sql')
                return
            if not tables:
                self.reply('<h1>No tables in this database</h1>', 'text/html')
                return
            if table not in tables:
                raise ValueError('Unknown table')
            page = int(params.get('page', ['0'])[0])
            if page < 0 or page > 1000000:
                raise ValueError('Invalid page')
            query = 'SELECT * FROM ' + identifier(table)
            if request.path == '/csv':
                cursor = db.execute(query)
                output = io.StringIO(newline='')
                writer = csv.writer(output)
                writer.writerow([column[0] for column in cursor.description])
                writer.writerows([csv_value(value) for value in row] for row in cursor)
                self.reply('\ufeff' + output.getvalue(), 'text/csv', 'table.csv')
                return
            cursor = db.execute(query + ' LIMIT ? OFFSET ?', (page_size + 1, page * page_size))
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
            escape = lambda value: html.escape(str(value), quote=True)
            options = ''.join('<option value="' + escape(name) + '"' +
                              (' selected' if name == table else '') + '>' + escape(name) + '</option>' for name in tables)
            header = ''.join('<th>' + escape(name) + '</th>' for name in columns)
            body = ''.join('<tr>' + ''.join('<td>' + ('<em>NULL</em>' if value is None else escape(value)) +
                          '</td>' for value in row) + '</tr>' for row in rows[:page_size])
            link = '/?table=' + quote(table, safe='') + '&page='
            navigation = (f'<a href="{link}{page-1}">Previous</a> ' if page else '')
            if len(rows) > page_size:
                navigation += f'<a href="{link}{page+1}">Next</a>'
            self.reply('<!doctype html><html lang="en"><meta charset="utf-8">'
                       '<meta name="viewport" content="width=device-width,initial-scale=1">'
                       '<title>Axis Migration</title><style>body{font:14px system-ui;margin:24px}'
                       'table{border-collapse:collapse}th,td{border:1px solid #aaa;padding:8px;text-align:left;white-space:pre-wrap}'
                       'th{position:sticky;top:0;background:#eee} .grid{overflow:auto;margin:16px 0}a{margin-right:16px}'
                       'td{min-width:100px;max-width:400px;overflow-wrap:anywhere}</style>'
                       '<h1>Axis Migration</h1><form><label>Table <select name="table">' + options +
                       '</select></label> <button>View</button></form><p>Read-only · Page ' + str(page+1) +
                       '</p><a href="/csv?table=' + quote(table, safe='') + '">Download CSV</a>'
                       '<a href="/sql">Download SQL</a><div class="grid"><table><thead><tr>' + header +
                       '</tr></thead><tbody>' + body + '</tbody></table></div>' + navigation + '</html>', 'text/html')

        def reply(self, content, mime, filename=None):
            """Send private, non-cacheable content with a restrictive browser policy."""
            data = content.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', mime + '; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'")
            if filename:
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format, *args):
            """Avoid logging query strings containing company table names."""
            pass

    return Viewer


def main():
    """Start the local read-only viewer with explicit configuration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--page-size', type=int, default=100)
    args = parser.parse_args()
    database = args.database.resolve()
    if not database.is_file() or not 1 <= args.page_size <= 1000:
        parser.error('Provide an existing database and a page size from 1 to 1000.')
    # Browser preconnections must not block subsequent table requests.
    with ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(database, args.page_size)) as server:
        print(f'Open http://127.0.0.1:{server.server_port} — Ctrl+C to stop.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()

# 동작 설명: 지정한 SQLite 파일을 읽기 전용으로 열어 로컬 표와 다운로드를 제공합니다.
# 원본 변경이나 외부 전송 없이 표 선택, 페이지 이동, CSV·SQL 저장을 지원합니다.
