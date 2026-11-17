"""Read-only, loopback-only SQLite table viewer using the standard library."""

import argparse
import csv
import html
import io
import json
import sqlite3
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit


def identifier(value):
    """Quote an already discovered SQLite identifier."""
    return '"' + value.replace('"', '""') + '"'


def csv_value(value):
    """Preserve null, empty strings, and literal backslashes distinctly."""
    return '\\N' if value is None else str(value).replace('\\', '\\\\')


STYLE = '''
*{box-sizing:border-box}html{scroll-behavior:smooth}body{font:14px/1.65 system-ui,sans-serif;margin:0;display:flex;min-height:100vh;color:#172033;background:#fff}
a{color:#194f88;text-underline-offset:3px}a:hover{color:#0b315c}a:focus-visible,input:focus-visible,button:focus-visible,summary:focus-visible{outline:3px solid #b87914;outline-offset:3px}
::selection{background:#d9e8ff;color:#172033}aside{width:254px;flex:none;background:#f2f5f9;border-right:1px solid #d7dfea;padding:24px 14px;position:sticky;top:0;height:100vh;overflow:auto}
aside h1{font-size:18px;margin:0 10px 22px}aside h2{font-size:12px;color:#536176;margin:24px 10px 8px}.table-link{display:block;padding:9px 10px;border-radius:6px;text-decoration:none;color:#26354b;overflow-wrap:anywhere;line-height:1.45}
.table-link:hover{background:#e2e9f2}.table-link.active{background:#d9e8ff;color:#12468b;font-weight:700}.table-link small{display:block;font-size:10px;font-weight:400;color:#536176;margin-top:3px}
main{min-width:0;flex:1;padding:32px 36px 64px}main>header{margin-bottom:26px}h2{margin:0 0 8px;font-size:26px;line-height:1.4}h3{font-size:19px;margin:32px 0 12px}h4{font-size:16px;margin:0 0 5px}.muted,.subtle{color:#536176}p{max-width:76ch;margin:8px 0 14px}.intro{font-size:15px}.overview{display:flex;gap:0;flex-wrap:wrap;border-top:1px solid #d7dfea;border-bottom:1px solid #d7dfea;margin:24px 0 30px}
.overview{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}.overview a{padding:18px 0;text-decoration:none}.overview strong{font-size:21px;color:#172033;font-variant-numeric:tabular-nums;margin-right:7px}.overview span{display:block;font-size:12px;color:#536176;margin-top:3px}
.notice{background:#fff6df;padding:18px 20px;margin:20px 0}.notice h3{margin:0 0 6px;font-size:16px}.notice p:last-child{margin-bottom:0}.jump{display:flex;flex-wrap:wrap;gap:8px 20px;margin:18px 0 26px}.jump a{font-size:13px}
.start-note{margin:18px 0}.start-note h3{margin:0 0 5px;font-size:16px}.dashboard-note{padding:9px 0;border-bottom:1px solid #d7dfea}.dashboard-note summary{font-weight:600}.dashboard-note p{padding:8px 0;margin:0}
.search{display:flex;align-items:center;flex-wrap:wrap;gap:10px;margin:24px 0}.search label{font-weight:600}.search input{font:inherit;padding:8px 11px;border:1px solid #aab7c8;border-radius:5px;min-width:240px;max-width:100%;caret-color:#194f88}.search button,.button{font:inherit;padding:8px 14px;border:1px solid #8da4bf;border-radius:5px;background:#f2f5f9;color:#173c65;text-decoration:none;cursor:pointer}.search button:hover,.button:hover{background:#e2e9f2}
.catalog-row{padding:22px 0;border-top:1px solid #d7dfea}.catalog-top{display:flex;align-items:baseline;justify-content:space-between;gap:18px}.count{white-space:nowrap;color:#536176;font-size:13px;font-variant-numeric:tabular-nums}.table-code{color:#536176;font-size:12px;overflow-wrap:anywhere}.catalog-row p{margin:6px 0 10px}.catalog-row details{margin-top:9px}summary{cursor:pointer;color:#194f88;width:fit-content}summary:hover{text-decoration:underline}.guide{background:#f5f7fa;padding:20px 24px;margin:18px 0 24px}.guide h3{margin:0 0 12px;font-size:16px}dl{margin:0}.guide dl,.catalog-row dl{display:grid;grid-template-columns:118px minmax(0,1fr);gap:10px 20px;max-width:1000px}dt{font-weight:600}dd{margin:0;max-width:78ch;overflow-wrap:anywhere}.related a{display:inline-block;margin:0 18px 4px 0}.toolbar{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:18px 0}
.column-label{display:block;white-space:normal;min-width:90px}.column-unit,.column-source{display:block;font-size:11px;font-weight:400;line-height:1.5;margin-top:4px;color:#536176;white-space:normal;overflow-wrap:anywhere}.column-help{font-size:12px;font-weight:400;display:inline-block;margin-top:5px}.unit-unknown{color:#805500}.column-guide{margin:20px 0}.column-guide>summary{font-weight:600}.column-guide>p{font-size:13px;color:#536176}.column-note{border-top:1px solid #d7dfea;padding:16px 0;scroll-margin-top:16px}.column-note:target{background:#fff6df}.column-note h4{font-size:14px}.column-note h4 small{display:block;font-size:12px;font-weight:400;color:#536176;overflow-wrap:anywhere}.column-note dl{display:grid;grid-template-columns:90px minmax(0,1fr);gap:6px 16px}.column-jump{display:inline-block;margin:8px 0}
table{border-collapse:collapse;font-variant-numeric:tabular-nums;font-size:13px;width:max-content;min-width:100%}th,td{border-bottom:1px solid #d7dfea;padding:10px 12px;text-align:left;white-space:pre-wrap;vertical-align:top}th{position:sticky;top:0;background:#edf2f7;color:#26354b;font-weight:600;z-index:1}td{min-width:110px;max-width:420px;overflow-wrap:anywhere}tbody tr:nth-child(even){background:#fafbfd}.grid{overflow:auto;max-height:72vh;margin:16px 0;border:1px solid #d7dfea}.pager{display:flex;gap:20px;margin-top:18px}em{color:#6b7280}.empty{padding:24px;background:#f5f7fa}.footer{font-size:12px;color:#536176;border-top:1px solid #d7dfea;margin-top:36px;padding-top:18px}
@media(max-width:900px){aside{width:205px}main{padding:26px 22px}.guide dl,.catalog-row dl{grid-template-columns:100px minmax(0,1fr)}}
@media(max-width:640px){body{display:block}aside{position:static;width:auto;height:auto;max-height:240px;border-right:0;border-bottom:1px solid #d7dfea;padding:14px}aside h1{margin:0 8px 8px}aside h2{margin:14px 8px 4px}main{padding:24px 16px}h2{font-size:23px}.overview{gap:12px}.overview strong{display:block;font-size:19px}.overview a{font-size:12px}.overview span{font-size:11px}.guide{padding:16px}.guide dl,.catalog-row dl{display:block}dt{margin:14px 0 4px}.catalog-top{align-items:flex-start}.search input{min-width:0;width:100%}.search{align-items:stretch}.grid{max-height:65vh}}
'''


def escape(value):
    """Keep source and catalog prose as plain, untrusted text."""
    return html.escape(str(value), quote=True)


def table_info(catalog, name):
    """Use external, evidence-backed descriptions without inventing meanings."""
    return catalog.get('tables', {}).get(name, {})


def table_groups(catalog, tables):
    """Group discovered tables only; stale catalog entries never become links."""
    groups = {}
    for name in tables:
        group = table_info(catalog, name).get('group', '그 밖의 테이블')
        groups.setdefault(group, []).append(name)
    order = catalog.get('group_order', [])
    return [(group, groups[group]) for group in order if group in groups] + [
        (group, names) for group, names in groups.items() if group not in order]


def table_guide(catalog, name, tables, heading=True):
    """Explain purpose, grain, safe readings, and limits beside actual rows."""
    info = table_info(catalog, name)
    if not info:
        return '<p class="muted">이 테이블의 업무 설명은 아직 등록되지 않았습니다. 열 이름만으로 의미를 확정하지 마세요.</p>'
    items = [('생긴 이유', 'why'), ('한 행의 의미', 'row_meaning'),
             ('가능한 해석', 'interpretation'), ('주의할 점', 'caution'), ('설명 근거', 'evidence')]
    description = ''.join('<dt>' + label + '</dt><dd>' + escape(info[key]) + '</dd>'
                          for label, key in items if info.get(key))
    related = ''.join('<a href="/?table=' + quote(other, safe='') + '">' +
                      escape(table_info(catalog, other).get('title', other)) + '</a>'
                      for other in info.get('related', []) if other in tables)
    if related:
        description += '<dt>함께 볼 표</dt><dd class="related">' + related + '</dd>'
    return ('<h3>이 테이블을 읽는 방법</h3>' if heading else '') + '<dl>' + description + '</dl>'


def column_info(catalog, table, column):
    """Look up table-specific meanings; the same raw name may have different units."""
    return table_info(catalog, table).get('columns', {}).get(column, {})


def column_header(catalog, table, column, index, page):
    """Display Korean labels and units while retaining the source identifier."""
    info = column_info(catalog, table, column)
    if not info:
        return '<th scope="col">' + escape(column) + '</th>'
    unit_class = ' unit-unknown' if info.get('unit_status') == 'unconfirmed' else ''
    link = '/?table=' + quote(table, safe='') + '&page=' + str(page) + '&columns=open#column-' + str(index)
    return '<th scope="col"><span class="column-label">' + escape(info.get('label', column)) + '</span><span class="column-unit' + unit_class + '">단위: ' + escape(info.get('unit', '미확정')) + '</span><small class="column-source">' + escape(column) + '</small><a class="column-help" href="' + link + '">뜻·단위</a></th>'


def column_guide(catalog, table, columns, opened=False):
    """Explain every actual column in order, including explicitly missing metadata."""
    result = '<details class="column-guide" id="column-guide"' + (' open' if opened else '') + '><summary>컬럼 뜻과 단위 보기 · ' + str(len(columns)) + '개</summary><p>표시는 한글로 바꾸고 DB의 원래 컬럼명은 함께 남겼습니다. 수량과 가격 기준이 같다고 가정하지 않으며, 미확정 단위는 추정해서 채우지 않습니다. CSV·SQL 다운로드는 기존 컬럼명을 유지합니다.</p>'
    for index, column in enumerate(columns):
        info = column_info(catalog, table, column)
        result += '<section class="column-note" id="column-' + str(index) + '"><h4>' + escape(info.get('label', column)) + '<small>' + escape(column) + '</small></h4><dl>'
        for title, key, fallback in [('뜻', 'description', '컬럼 설명이 아직 등록되지 않았습니다. 원문 위치와 모델을 확인하세요.'),
                                     ('단위', 'unit', '미확정'), ('읽을 때 주의', 'notes', ''), ('단위 근거', 'unit_basis', '')]:
            value = info.get(key, fallback)
            if value:
                result += '<dt>' + title + '</dt><dd>' + escape(value) + '</dd>'
        result += '</dl><a class="column-jump" href="#table-data">데이터 표로 돌아가기</a></section>'
    return result + '</details>'


def make_handler(database, page_size, catalog=None):
    """Bind one trusted database path and pagination configuration."""
    catalog = catalog or {}
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
                with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
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
            page = int(params.get('page', ['0'])[0])
            if page < 0 or page > 1000000:
                raise ValueError('Invalid page')
            dashboard = request.path == '/' and (params.get('view') == ['dashboard'] or
                        (catalog and 'table' not in params))
            if dashboard:
                self.dashboard(db, tables, params.get('q', [''])[0][:200])
                return
            if table not in tables:
                raise ValueError('Unknown table')
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
            header = ''.join(column_header(catalog, table, name, index, page) for index, name in enumerate(columns))
            body = ''.join('<tr>' + ''.join('<td>' + ('<em>NULL</em>' if value is None else escape(value)) +
                          '</td>' for value in row) + '</tr>' for row in rows[:page_size])
            link = '/?table=' + quote(table, safe='') + '&page='
            navigation = (f'<a href="{link}{page-1}">Previous</a> ' if page else '')
            if len(rows) > page_size:
                navigation += f'<a href="{link}{page+1}">Next</a>'
            info = table_info(catalog, table)
            title = info.get('title', table)
            description = ('<p class="table-code">' + escape(table) + '</p>') if title != table else ''
            count = db.execute('SELECT COUNT(*) FROM ' + identifier(table)).fetchone()[0]
            empty = '<p class="empty">현재 저장된 행이 없습니다. 이 구조가 있다는 것만으로 원본에 해당 업무가 없다고 판단할 수는 없습니다.</p>' if not count else ''
            content = '<header><h2>' + escape(title) + '</h2>' + description + '<p class="muted">읽기 전용 · ' + f'{count:,}' + '행 · 페이지 ' + str(page+1) + '</p></header>'
            content += '<section class="guide" aria-label="테이블 설명">' + table_guide(catalog, table, tables) + '</section>'
            content += column_guide(catalog, table, columns, params.get('columns') == ['open'])
            content += '<div class="toolbar"><a class="button" href="/csv?table=' + quote(table, safe='') + '">Download CSV</a><a href="/sql">Download SQL</a><a href="/?view=dashboard">대시보드로 돌아가기</a></div>'
            content += empty + '<div class="grid" id="table-data" tabindex="0" role="region" aria-label="테이블 데이터"><table><thead><tr>' + header + '</tr></thead><tbody>' + body + '</tbody></table></div><nav class="pager" aria-label="페이지 이동">' + navigation + '</nav>'
            self.shell(tables, table, content)

        def dashboard(self, db, tables, search):
            """Render an explained catalog; row counts never imply transaction totals."""
            counts = {name: db.execute('SELECT COUNT(*) FROM ' + identifier(name)).fetchone()[0] for name in tables}
            groups = table_groups(catalog, tables)
            content = '<header><h2>' + escape(catalog.get('title', '자료 대시보드')) + '</h2><p class="intro">' + escape(catalog.get('description', '테이블을 고르기 전에 자료의 의미와 범위를 확인하세요.')) + '</p></header>'
            overview = []
            for item in catalog.get('overview', []):
                name = item.get('table')
                if name in counts:
                    overview.append('<a href="/?table=' + quote(name, safe='') + '"><strong>' + f'{counts[name]:,}' + '</strong>' + escape(item.get('label', name)) + '<span>' + escape(item.get('note', '')) + '</span></a>')
            if overview:
                content += '<div class="overview" aria-label="현재 자료 범위">' + ''.join(overview) + '</div>'
            for i, item in enumerate(catalog.get('notices', [])):
                if i == 0:
                    content += '<section class="start-note"><h3>' + escape(item['title']) + '</h3><p>' + escape(item['text']) + '</p></section>'
                else:
                    content += '<details class="dashboard-note"><summary>' + escape(item['title']) + '</summary><p>' + escape(item['text']) + '</p></details>'
            content += '<nav class="jump" aria-label="테이블 분류">' + ''.join('<a href="#group-' + str(i) + '">' + escape(group) + '</a>' for i, (group, _) in enumerate(groups)) + '</nav>'
            content += '<form class="search" method="get"><input type="hidden" name="view" value="dashboard"><label for="table-search">테이블 찾기</label><input id="table-search" name="q" value="' + escape(search) + '" placeholder="예: 세금계산서, 검증, 단위"><button type="submit">찾기</button>' + ('<a href="/?view=dashboard">전체 보기</a>' if search else '') + '</form>'
            matches = 0
            for i, (group, names) in enumerate(groups):
                selected = [name for name in names if not search or search.casefold() in (name + ' ' + ' '.join(str(v) for v in table_info(catalog, name).values())).casefold()]
                if not selected:
                    continue
                content += '<section id="group-' + str(i) + '"><h3>' + escape(group) + '</h3>'
                for name in selected:
                    matches += 1
                    info = table_info(catalog, name)
                    column_link = ('<a class="column-jump" href="/?table=' + quote(name, safe='') + '&columns=open#column-guide">컬럼 뜻·단위 ' + str(len(info['columns'])) + '개 보기</a>') if info.get('columns') else ''
                    content += '<article class="catalog-row"><div class="catalog-top"><div><h4><a href="/?table=' + quote(name, safe='') + '">' + escape(info.get('title', name)) + '</a></h4><span class="table-code">' + escape(name) + '</span></div><span class="count">' + f'{counts[name]:,}' + '행</span></div><p>' + escape(info.get('why', '이 테이블의 업무 설명은 아직 등록되지 않았습니다.')) + '</p><details><summary>한 행의 의미와 해석 보기</summary>' + table_guide(catalog, name, tables, heading=False) + '</details>' + column_link + '</article>'
                content += '</section>'
            if not matches:
                content += '<p class="empty">검색 조건에 맞는 테이블이 없습니다. 다른 단어로 찾거나 전체 보기를 선택하세요.</p>'
            content += '<p class="footer">행 수는 각 테이블의 저장 단위입니다. 서로 다른 표의 행 수나 금액을 합쳐 거래 건수·총비용으로 해석하지 마세요. 원문과 데이터베이스는 읽기 전용으로 표시합니다.</p>'
            self.shell(tables, None, content)

        def shell(self, tables, selected, content):
            """Keep navigation, descriptions, and data in one local surface."""
            options = '<a class="table-link' + (' active' if selected is None else '') + '" href="/?view=dashboard">대시보드</a>'
            for group, names in table_groups(catalog, tables):
                options += '<h2>' + escape(group) + '</h2>'
                for name in names:
                    title = table_info(catalog, name).get('title', name)
                    label = escape(title) + ('<small>' + escape(name) + '</small>' if title != name else '')
                    options += '<a class="table-link' + (' active' if name == selected else '') + '" href="/?table=' + quote(name, safe='') + '"' + (' aria-current="page"' if name == selected else '') + '>' + label + '</a>'
            self.reply('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + escape(catalog.get('title', 'Axis Migration')) + '</title><style>' + STYLE + '</style></head><body><aside><h1>Axis Migration</h1><nav aria-label="테이블 목록">' + options + '</nav></aside><main>' + content + '</main></body></html>', 'text/html')

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
    parser.add_argument('--catalog', type=Path, help='Private JSON table descriptions, stored outside the public package.')
    args = parser.parse_args()
    database = args.database.resolve()
    if not database.is_file() or not 1 <= args.page_size <= 1000:
        parser.error('Provide an existing database and a page size from 1 to 1000.')
    catalog = {}
    if args.catalog:
        try:
            catalog = json.loads(args.catalog.read_text(encoding='utf-8'))
            if not isinstance(catalog, dict) or not isinstance(catalog.get('tables', {}), dict):
                raise ValueError('Invalid catalog')
        except (OSError, ValueError):
            parser.error('Provide a readable JSON catalog with a tables object.')
    # Browser preconnections must not block subsequent table requests.
    with ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(database, args.page_size, catalog)) as server:
        print(f'Open http://127.0.0.1:{server.server_port} — Ctrl+C to stop.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()

# 동작 설명: 지정한 SQLite 파일을 읽기 전용으로 열어 로컬 표와 다운로드를 제공합니다.
# 원본 변경이나 외부 전송 없이 표 선택, 페이지 이동, CSV·SQL 저장을 지원합니다.
